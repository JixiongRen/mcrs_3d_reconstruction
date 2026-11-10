"""Reconstruct saved native RGB/IR frames and write inspectable outputs."""
import argparse
import csv
import json
from pathlib import Path
import time

import cv2
import numpy as np

from ..segmentation import segment
from ..centerline import centerline, resample
from ..stereo import Stereo
from ..matching import match_curves
from ..visualization import save_plots


def run(capture, indices, output):
    metadata = json.loads((capture / "metadata.json").read_text())
    checked = json.loads((capture / "triangulation/profile_calibration_check.json").read_text())
    stereo = Stereo(metadata, checked)
    frames = metadata["frames"]
    reports = []
    for index in indices:
        started = time.perf_counter()
        frame = next(f for f in frames if f["index"] == index)
        if frame["color_timestamp_us"] <= 0:
            raise ValueError("RGB timestamp is invalid")
        paired = min(frames, key=lambda f: abs(f["ir_timestamp_us"]-frame["color_timestamp_us"]))
        ir_index = paired["index"]
        out = output / f"rgb_{index:04d}_ir_{ir_index:04d}"
        out.mkdir(parents=True, exist_ok=True)
        # Prevent plots/points from a prior successful run surviving a rejected rerun.
        for name in ("automatic_matches.png", "automatic_3d.png", "points_3d.csv",
                     "centerlines.npz", "rgb_mask.png", "ir_mask.png", "result.json"):
            (out / name).unlink(missing_ok=True)
        rgb_image = cv2.imread(str(capture / f"{index:04d}_rgb.jpg"))
        ir_image = cv2.imread(str(capture / f"{ir_index:04d}_ir.png"), cv2.IMREAD_GRAYSCALE)
        try:
            rgb_mask, _ = segment(rgb_image, "rgb")
            ir_mask, _ = segment(ir_image, "ir")
            rgb_path, rgb_stop = centerline(rgb_mask)
            ir_path, ir_stop = centerline(ir_mask)
        except ValueError as exc:
            failure = {"rgb_frame": index, "ir_frame": ir_index, "status": "extraction_rejected", "error": str(exc)}
            (out / "result.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
            reports.append(failure)
            print(json.dumps(failure), flush=True)
            continue
        rgb, rgb_arc = resample(rgb_path, 5)
        ir, ir_arc = resample(ir_path, 2)
        accepted, rejected = match_curves(rgb, rgb_arc, ir, ir_arc, stereo)
        report = {"status": "partial_reconstruction" if accepted else "no_accepted_matches", "rgb_frame": index, "ir_frame": ir_index,
                  "rgb_minus_ir_ms": (frame["color_timestamp_us"]-paired["ir_timestamp_us"])/1000,
                  "rgb_centerline_points": len(rgb), "ir_centerline_points": len(ir),
                  "rgb_centerline_length_px": float(rgb_arc[-1]), "ir_centerline_length_px": float(ir_arc[-1]),
                  "rgb_stop": rgb_stop, "ir_stop": ir_stop,
                  "accepted_points": len(accepted), "rejected_points": len(rejected),
                  "coordinate_system": "IR camera X right, Y down, Z forward; millimetres",
                  "limitations": ["Tuned for a blue catheter and the current static tabletop scene; not a general guidewire detector.",
                                  "Largest RGB color component, strongest integrated IR bright ridge, and uppermost free endpoint are scene assumptions; no manual coordinates or ROIs used.",
                                  "IR bright-ridge threshold can truncate faint portions; no gap filling performed.",
                                  "Near-tangent epipolar intersections and ambiguous/unsorted matches are rejected.",
                                  "Match fragments shorter than five samples are rejected rather than bridged.",
                                  "Reprojection errors are constrained by matching and are not independent accuracy evidence.",
                                  "Timestamp pairing does not synchronize exposure; factory calibration is not independently validated.",
                                  "Skeleton coordinates have pixel-scale noise; no 3D smoothing or catheter length constraint is used."],
                  "matches": accepted, "rejections": rejected}
        if accepted:
            xyz = np.array([a["xyz_mm"] for a in accepted])
            projected_rgb, projected_ir = stereo.reproject(xyz)
            report["z_range_mm"] = [float(xyz[:, 2].min()), float(xyz[:, 2].max())]
            report["max_reprojection_error_rgb_ir_px"] = [float(np.linalg.norm(projected_rgb-np.array([a["rgb"] for a in accepted]), axis=1).max()), float(np.linalg.norm(projected_ir-np.array([a["ir"] for a in accepted]), axis=1).max())]
            with (out / "points_3d.csv").open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["rgb_sample_index", "rgb_u", "rgb_v", "ir_u", "ir_v", "X_mm", "Y_mm", "Z_mm", "crossing_sine"])
                writer.writerows([[a["rgb_index"], *a["rgb"], *a["ir"], *a["xyz_mm"], a["crossing_sine"]] for a in accepted])
        cv2.imwrite(str(out / "rgb_mask.png"), rgb_mask*255)
        cv2.imwrite(str(out / "ir_mask.png"), ir_mask*255)
        np.savez_compressed(out / "centerlines.npz", rgb=rgb, ir=ir, rgb_arc=rgb_arc, ir_arc=ir_arc)
        report["compute_seconds_before_plotting"] = time.perf_counter()-started
        save_plots(out, rgb_image, ir_image, rgb, ir, accepted, rejected)
        (out / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        compact = {k: v for k, v in report.items() if k not in ("matches", "rejections", "limitations")}
        reports.append(compact)
        print(json.dumps(compact), flush=True)
    (output / "batch_summary.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--frames", nargs="+", type=int, default=[50])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run(args.capture, args.frames, args.output or Path("outputs/offline") / args.capture.name)
