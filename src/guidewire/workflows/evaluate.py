"""Post-hoc manual comparison; manual points never feed reconstruction."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def point_curve_distance(point, curve):
    edges = np.diff(curve, axis=0)
    alpha = np.sum((point-curve[:-1])*edges, axis=1)/np.maximum(np.sum(edges**2, axis=1), 1e-12)
    projected = curve[:-1] + np.clip(alpha, 0, 1)[:, None]*edges
    return float(np.linalg.norm(projected-point, axis=1).min())


def evaluate(capture, output):
    batch = json.loads((output / "batch_summary.json").read_text())
    reference = next(row for row in batch if row["rgb_frame"] == 50)
    folder = output / f"rgb_0050_ir_{reference['ir_frame']:04d}"
    auto = json.loads((folder / "result.json").read_text())
    manual = json.loads((capture / "triangulation/result.json").read_text())
    curves = np.load(folder / "centerlines.npz")
    xy = np.array([m["rgb"] for m in auto["matches"]])
    xyz = np.array([m["xyz_mm"] for m in auto["matches"]])
    comparisons = []
    for point in manual["points"]:
        rgb_point = np.array([point["rgb_u"], point["rgb_v"]])
        ir_point = np.array([point["ir_u"], point["ir_v"]])
        distances = np.linalg.norm(xy-rgb_point, axis=1)
        k = distances.argmin()
        row = {"manual_id": point["id"],
               "manual_rgb_distance_to_auto_centerline_px": point_curve_distance(rgb_point, curves["rgb"]),
               "manual_ir_distance_to_auto_centerline_px": point_curve_distance(ir_point, curves["ir"]),
               "nearest_accepted_rgb_distance_px": float(distances[k]),
               "covered_within_8px": bool(distances[k] <= 8)}
        if row["covered_within_8px"]:
            manual_xyz = np.array([point["X_mm"], point["Y_mm"], point["Z_mm"]])
            row["auto_minus_manual_Z_mm"] = float(xyz[k, 2]-manual_xyz[2])
            row["auto_manual_XYZ_distance_mm"] = float(np.linalg.norm(xyz[k]-manual_xyz))
        comparisons.append(row)
    covered = [r for r in comparisons if r["covered_within_8px"]]
    temporal = []
    for row in batch:
        if row.get("status") != "partial_reconstruction" or row["rgb_frame"] == 50:
            continue
        result = json.loads((output / f"rgb_{row['rgb_frame']:04d}_ir_{row['ir_frame']:04d}" / "result.json").read_text())
        other_xy = np.array([m["rgb"] for m in result["matches"]])
        other_xyz = np.array([m["xyz_mm"] for m in result["matches"]])
        distances = np.linalg.norm(xy[:, None]-other_xy[None], axis=2)
        nearest = distances.argmin(axis=1)
        valid = distances[np.arange(len(xy)), nearest] <= 5
        difference = abs(other_xyz[nearest[valid], 2]-xyz[valid, 2])
        temporal.append({"rgb_frame": row["rgb_frame"], "nearby_rgb_comparisons_within_5px": int(valid.sum()),
                         "absolute_Z_difference_mm_median_p95": np.percentile(difference, [50, 95]).tolist() if len(difference) else None})
    summary = {"manual_comparison_not_ground_truth": comparisons,
               "manual_points_covered_within_8px": len(covered), "manual_point_count": len(comparisons),
               "covered_auto_manual_XYZ_distance_mm_median_max": [float(np.median([r["auto_manual_XYZ_distance_mm"] for r in covered])), float(max(r["auto_manual_XYZ_distance_mm"] for r in covered))] if covered else None,
               "temporal_comparisons_not_accuracy": temporal,
               "development_rgb_frames": [50, 10, 80, 140], "additional_validation_rgb_frames": [20, 100, 120],
               "limitations": ["Manual estimates are uncertain and not ground truth.",
                               "Nearest image points can differ along the physical catheter; distances do not establish reconstruction accuracy.",
                               "Temporal comparisons use nearby RGB positions, not independently verified material-point tracking.",
                               "All frames are from one recording; no generalization claim to other colors, objects or backgrounds."]}
    (output / "evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    manual_xyz = np.array([[p['X_mm'], p['Y_mm'], p['Z_mm']] for p in manual["points"]])
    for ax, (a, b) in zip(axes, [(0, 1), (0, 2)]):
        ax.scatter(xyz[:, a], xyz[:, b], s=9, label="Automatic accepted points")
        ax.scatter(manual_xyz[:, a], manual_xyz[:, b], marker="x", s=50, c="red", label="Manual estimates (not truth)")
        for j, point in enumerate(manual_xyz):
            ax.annotate(str(j+1), (point[a], point[b]), xytext=(4, 4), textcoords="offset points", fontsize=8)
        ax.set(xlabel=f"{'XYZ'[a]} [mm]", ylabel=f"{'XYZ'[b]} [mm]")
        if b == 1:
            ax.invert_yaxis()
        ax.grid(alpha=.3)
        ax.legend(fontsize=8)
    fig.suptitle("Automatic vs prior manual estimates: comparison, not an accuracy test")
    fig.tight_layout()
    fig.savefig(output / "manual_comparison.png", dpi=150)
    plt.close(fig)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evaluate(args.capture, args.output)
