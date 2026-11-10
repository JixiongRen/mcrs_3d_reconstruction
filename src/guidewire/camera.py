"""Gemini 2 hardware access and frame decoding; SDK is loaded on demand."""
import time

import cv2
import numpy as np

from .stereo import Stereo


def describe(profile):
    return (f"{profile.get_width()}x{profile.get_height()} "
            f"{profile.get_format()} @{profile.get_fps()}fps")


def select_profile(pipeline, sensor, width, height, preferred, supported, fps):
    profiles = pipeline.get_stream_profile_list(sensor)
    candidates = [profiles.get_stream_profile_by_index(i).as_video_stream_profile()
                  for i in range(profiles.get_count())]
    decodable = [p for p in candidates if p.get_format() in supported]
    if not decodable:
        available = ", ".join(describe(p) for p in candidates)
        raise RuntimeError(f"No decodable {sensor} profile; available: {available}")
    selected = min(decodable, key=lambda p: (
        (p.get_width(), p.get_height()) != (width, height),
        p.get_format() != preferred,
        abs(p.get_fps() - fps),
        abs(p.get_width() * p.get_height() - width * height),
    ))
    print(f"{sensor}: {describe(selected)}", flush=True)
    return selected


def color_to_bgr(frame):
    import pyorbbecsdk as ob
    data = np.frombuffer(frame.get_data(), dtype=np.uint8)
    height, width = frame.get_height(), frame.get_width()
    fmt = frame.get_format()
    if fmt == ob.OBFormat.MJPG:
        bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError("Could not decode the MJPG color frame.")
        return bgr
    if fmt in (ob.OBFormat.YUYV, ob.OBFormat.YUY2):
        return cv2.cvtColor(data.reshape(height, width, 2), cv2.COLOR_YUV2BGR_YUY2)
    image = data.reshape(height, width, 3)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if fmt == ob.OBFormat.RGB else image


def depth_to_image(frame):
    raw = np.frombuffer(frame.get_data(), dtype=np.uint16).reshape(
        frame.get_height(), frame.get_width())
    depth_mm = raw.astype(np.float32) * frame.get_depth_scale()
    # Fixed 200-5000 mm display range; zero depth means invalid.
    values = (np.clip((depth_mm - 200) / 4800, 0, 1) * 255).astype(np.uint8)
    image = cv2.applyColorMap(255 - values, cv2.COLORMAP_JET)
    image[raw == 0] = 0
    return depth_mm, image


def open_camera(ir_exposure=300):
    import pyorbbecsdk as ob
    context = ob.Context()
    devices = context.query_devices()
    if devices.get_count() == 0:
        raise RuntimeError("No Gemini 2 found. Close other camera apps and check USB.")
    device = devices.get_device_by_index(0)
    pipeline, config = ob.Pipeline(device), ob.Config()
    profiles = {}
    for name, sensor, width, height, fmt in (
        ("rgb", ob.OBSensorType.COLOR_SENSOR, 1920, 1080, ob.OBFormat.MJPG),
        ("depth", ob.OBSensorType.DEPTH_SENSOR, 1280, 800, ob.OBFormat.Y16),
        ("ir", ob.OBSensorType.IR_SENSOR, 1280, 800, ob.OBFormat.Y8),
    ):
        profile = pipeline.get_stream_profile_list(sensor).get_video_stream_profile(width, height, fmt, 5)
        profiles[name] = profile
        config.enable_stream(profile)
    config.set_frame_aggregate_output_mode(ob.OBFrameAggregateOutputMode.FULL_FRAME_REQUIRE)
    pipeline.disable_frame_sync()
    # Retain the proven stream profiles; reconstruction never uses depth pixels.
    pipeline.start(config)
    exposure_original, auto_original = None, None
    try:
        # Lower exposure avoids the saturated background seen after reconnect.
        # Keep the projector, gain and LDP safety protection unchanged.
        auto_original = device.get_bool_property(ob.OBPropertyID.OB_PROP_IR_AUTO_EXPOSURE_BOOL)
        exposure_original = device.get_int_property(ob.OBPropertyID.OB_PROP_IR_EXPOSURE_INT)
        device.set_bool_property(ob.OBPropertyID.OB_PROP_IR_AUTO_EXPOSURE_BOOL, False)
        device.set_int_property(ob.OBPropertyID.OB_PROP_IR_EXPOSURE_INT, ir_exposure)
        def fields(obj, names):
            return {name: getattr(obj, name) for name in names.split()}
        ir_depth = profiles["ir"].get_extrinsic_to(profiles["depth"])
        depth_rgb = profiles["depth"].get_extrinsic_to(profiles["rgb"])
        ir_rgb = profiles["ir"].get_extrinsic_to(profiles["rgb"])
        c = {"rgb_intrinsic": fields(profiles["rgb"].get_intrinsic(), "fx fy cx cy width height"),
             "ir_intrinsic": fields(profiles["ir"].get_intrinsic(), "fx fy cx cy width height"),
             "rgb_distortion": fields(profiles["rgb"].get_distortion(), "k1 k2 k3 k4 k5 k6 p1 p2"),
             "depth_to_rgb_rotation": np.asarray(depth_rgb.rot).tolist(),
             "depth_to_rgb_translation": np.asarray(depth_rgb.transform).tolist(),
             "ir_to_depth_rotation": np.asarray(ir_depth.rot).tolist(),
             "ir_to_depth_translation": np.asarray(ir_depth.transform).tolist()}
        checked = {"ir_distortion": fields(profiles["ir"].get_distortion(), "k1 k2 k3 k4 k5 k6 p1 p2"),
                   "ir_to_rgb_rotation": np.asarray(ir_rgb.rot).tolist(),
                   "ir_to_rgb_translation": np.asarray(ir_rgb.transform).tolist()}
        info = device.get_device_info()
        metadata = {"device": {"name": info.get_name(), "serial": info.get_serial_number(),
                               "firmware": info.get_firmware_version(), "connection": info.get_connection_type()},
                    "calibration": c, "checked_profile": checked, "acquisition_fps": 5,
                    "sdk_frame_sync_enabled": False, "depth_pixels_used": False,
                    "ir_exposure_original": exposure_original, "ir_auto_exposure_original": auto_original,
                    "ir_exposure_during_capture": device.get_int_property(ob.OBPropertyID.OB_PROP_IR_EXPOSURE_INT),
                    "ir_median_filter_size": 7}
        stereo = Stereo(metadata, checked)
    except Exception:
        pipeline.stop()
        if exposure_original is not None:
            device.set_int_property(ob.OBPropertyID.OB_PROP_IR_EXPOSURE_INT, exposure_original)
        if auto_original is not None:
            device.set_bool_property(ob.OBPropertyID.OB_PROP_IR_AUTO_EXPOSURE_BOOL, auto_original)
        raise
    return context, pipeline, stereo, metadata


def acquire(pipeline, buffer, stop):
    try:
        while not stop.is_set():
            # The SDK's blocking wait can hold the Python GIL. Short polling
            # plus Event.wait lets reconstruction and the UI actually run.
            frames = pipeline.wait_for_frames(1)
            if frames is None:
                stop.wait(.01)
                continue
            color, ir = frames.get_color_frame(), frames.get_ir_frame()
            received = time.monotonic()
            if color is not None:
                buffer.add("rgb", color.get_timestamp_us(), color_to_bgr(color).copy(), received)
            if ir is not None:
                image = np.frombuffer(ir.get_data(), np.uint8).reshape(ir.get_height(), ir.get_width()).copy()
                buffer.add("ir", ir.get_timestamp_us(), image, received)
    except Exception as exc:
        buffer.error = repr(exc)
        stop.set()


def restore_exposure(pipeline, metadata):
    """Restore and verify original settings; SDK clamping remains an explicit error."""
    import pyorbbecsdk as ob
    device = pipeline.get_device()
    device.set_int_property(ob.OBPropertyID.OB_PROP_IR_EXPOSURE_INT, metadata["ir_exposure_original"])
    device.set_bool_property(ob.OBPropertyID.OB_PROP_IR_AUTO_EXPOSURE_BOOL, metadata["ir_auto_exposure_original"])
    metadata["ir_exposure_restored"] = (
        device.get_int_property(ob.OBPropertyID.OB_PROP_IR_EXPOSURE_INT) == metadata["ir_exposure_original"] and
        device.get_bool_property(ob.OBPropertyID.OB_PROP_IR_AUTO_EXPOSURE_BOOL) == metadata["ir_auto_exposure_original"])
    if not metadata["ir_exposure_restored"]:
        raise RuntimeError("Exposure readback differs from original")
