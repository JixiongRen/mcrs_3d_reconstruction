"""Experimental dark-wire hypotheses; shadow alternatives remain unvalidated."""
import argparse
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..segmentation import dark_wire_candidates
from ..stereo import Stereo
from ..matching import match_curves


def analyze(rgb_image, ir_image, stereo, output):
    output.mkdir(parents=True, exist_ok=True)
    curves = {"rgb": dark_wire_candidates(rgb_image, "rgb"), "ir": dark_wire_candidates(ir_image, "ir")}
    result = {"status": "diagnostic_hypotheses_only", "hypotheses": [],
              "candidate_counts": {k: len(v) for k, v in curves.items()},
              "limitations": ["No automatic shadow disambiguation or ground truth",
                              "RGB uses strongest dark ridge; background may be selected",
                              "Original epipolar angle and fragment rejection remain enabled"]}
    # Current scene has one dominant dark wire in RGB. IR alternatives are all
    # retained, rather than choosing the largest dark shadow as the wire.
    if curves["rgb"]:
        rgb = curves["rgb"][0]
        for index, ir in enumerate(curves["ir"]):
            matches, rejected = match_curves(rgb["points"], rgb["arc"], ir["points"], ir["arc"], stereo)
            row = {"ir_candidate": index, "matches": matches, "rejected_count": len(rejected)}
            if matches:
                xyz = np.array([m["xyz_mm"] for m in matches])
                row["z_range_mm"] = [float(xyz[:, 2].min()), float(xyz[:, 2].max())]
                row["rgb_coverage_fraction"] = len(matches)/len(rgb["points"])
            result["hypotheses"].append(row)
    np.savez_compressed(output / "centerline_candidates.npz",
                        **{f"{name}_{i}": c["points"] for name, group in curves.items() for i, c in enumerate(group)})
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, name, image in zip(axes, ("rgb", "ir"), (rgb_image, ir_image)):
        ax.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if name == "rgb" else image, cmap="gray")
        for i, c in enumerate(curves[name]):
            if name == "rgb" and i > 0:
                continue
            xy = c["points"]
            ax.plot(*xy.T, lw=1, label=f"candidate {i}")
            ax.text(*xy[0], str(i), color="red")
        ax.set_title(name.upper()+" dark-line candidates")
        ax.legend(fontsize=7)
        ax.axis("off")
    fig.suptitle("Dark-wire diagnostic: IR includes possible shadows; no candidate certified")
    fig.tight_layout()
    fig.savefig(output / "candidates.png", dpi=130)
    plt.close(fig)
    for row in result["hypotheses"]:
        if not row["matches"]:
            continue
        matches = row["matches"]
        xyz = np.array([m["xyz_mm"] for m in matches])
        fig = plt.figure(figsize=(11, 5))
        ax = fig.add_subplot(121)
        ax.imshow(ir_image, cmap="gray")
        c = curves["ir"][row["ir_candidate"]]["points"]
        ax.plot(*c.T, color="lime", lw=1)
        xy = np.array([m["ir"] for m in matches])
        ax.scatter(*xy.T, s=5, color="red")
        lo, hi = c.min(0)-20, c.max(0)+20
        ax.set(xlim=(lo[0], hi[0]), ylim=(hi[1], lo[1]), title="IR candidate + accepted local matches")
        ax = fig.add_subplot(122, projection="3d")
        ax.scatter(*xyz.T, s=10, c=np.arange(len(xyz)), cmap="viridis")
        ax.set(xlabel="X [mm]", ylabel="Y [mm]", zlabel="Z [mm]", title="Unvalidated XYZ hypothesis")
        ax.set_box_aspect(np.maximum(np.ptp(xyz, axis=0), 1))
        fig.suptitle(f"IR candidate {row['ir_candidate']}: {len(matches)} points; may include shadow mismatch")
        fig.tight_layout()
        fig.savefig(output / f"hypothesis_{row['ir_candidate']}.png", dpi=140)
        plt.close(fig)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Live capture directory containing metadata.json")
    parser.add_argument("--pair", default="first_result", help="Subdirectory with rgb.jpg and ir.png")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cv2.setNumThreads(2)
    metadata = json.loads((args.capture / "metadata.json").read_text(encoding="utf-8"))
    rgb = cv2.imread(str(args.capture / args.pair / "rgb.jpg"))
    ir = cv2.imread(str(args.capture / args.pair / "ir.png"), cv2.IMREAD_GRAYSCALE)
    if rgb is None or ir is None:
        parser.error("Missing rgb.jpg or ir.png")
    result = analyze(rgb, ir, Stereo(metadata, metadata["checked_profile"]),
                     args.output or Path("outputs/black_wire") / args.capture.name)
    print(json.dumps({"candidates": result["candidate_counts"], "hypotheses": [
        {"ir_candidate": r["ir_candidate"], "points": len(r["matches"]), "z_range_mm": r.get("z_range_mm")}
        for r in result["hypotheses"]]}, indent=2))
