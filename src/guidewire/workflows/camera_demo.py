"""Enumerate devices or preview/decode native RGB and depth."""
import argparse
import time

import cv2
import numpy as np

from ..camera import select_profile, color_to_bgr, depth_to_image


def main():
    import pyorbbecsdk as ob
    color_formats = (ob.OBFormat.MJPG, ob.OBFormat.RGB, ob.OBFormat.BGR, ob.OBFormat.YUYV, ob.OBFormat.YUY2)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="List devices and exit")
    parser.add_argument("--frames", type=int, metavar="N",
                        help="Decode N RGB/depth frame pairs without opening a GUI")
    args = parser.parse_args()
    if args.frames is not None and args.frames <= 0:
        parser.error("--frames must be a positive integer")

    context = ob.Context()
    devices = context.query_devices()
    if devices.get_count() == 0:
        print("No Orbbec camera found. Connect Gemini 2 and check its USB cable.")
        return 1
    for i in range(devices.get_count()):
        info = devices.get_device_by_index(i).get_device_info()
        print(f"[{i}] {info.get_name()} | serial={info.get_serial_number()} | "
              f"firmware={info.get_firmware_version()} | {info.get_connection_type()}",
              flush=True)
    if args.list_devices:
        return 0

    device = devices.get_device_by_index(0)
    connection = device.get_device_info().get_connection_type()
    fps = 15 if "2.0" in connection else 30
    pipeline = ob.Pipeline(device)
    config = ob.Config()
    config.enable_stream(select_profile(
        pipeline, ob.OBSensorType.DEPTH_SENSOR, 640, 400, ob.OBFormat.Y16,
        (ob.OBFormat.Y16,), fps))
    config.enable_stream(select_profile(
        pipeline, ob.OBSensorType.COLOR_SENSOR, 640, 480, ob.OBFormat.MJPG,
        color_formats, fps))
    config.set_frame_aggregate_output_mode(ob.OBFrameAggregateOutputMode.FULL_FRAME_REQUIRE)
    started = False
    try:
        pipeline.start(config)
        started = True
        print("Streaming; press Q/Esc in a preview window or Ctrl+C to stop.", flush=True)
        count = 0
        last_pair = time.monotonic()
        while args.frames is None or count < args.frames:
            frames = pipeline.wait_for_frames(1000)
            color = frames.get_color_frame() if frames else None
            depth = frames.get_depth_frame() if frames else None
            if color is None or depth is None:
                if time.monotonic() - last_pair > 10:
                    raise RuntimeError("No complete RGB/depth frame pair for 10 seconds. "
                                       "Check USB connection and close other camera applications.")
                continue
            last_pair = time.monotonic()
            bgr = color_to_bgr(color)
            depth_mm, depth_image = depth_to_image(depth)
            count += 1
            if count == 1 or (args.frames is not None and count == args.frames):
                print(f"Frame {count}: color={bgr.shape[1]}x{bgr.shape[0]}, "
                      f"depth={depth_mm.shape[1]}x{depth_mm.shape[0]}, "
                      f"depth_scale={depth.get_depth_scale()} mm/unit, "
                      f"valid_depth_pixels={np.count_nonzero(depth_mm)}", flush=True)
            if args.frames is None:
                cv2.imshow("Gemini 2 RGB", bgr)
                cv2.imshow("Gemini 2 depth (0.2-5 m)", depth_image)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
        print(f"Decoded {count} RGB/depth frame pairs.", flush=True)
    finally:
        if started:
            pipeline.stop()
        if args.frames is None:
            cv2.destroyAllWindows()
    return 0
