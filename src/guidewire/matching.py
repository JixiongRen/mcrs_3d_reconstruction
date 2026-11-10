"""Ordered epipolar matching with ambiguity and degeneracy rejection."""
import cv2
import numpy as np


def match_curves(rgb, rgb_arc, ir, ir_arc, stereo):
    lines = stereo.lines(rgb)
    # Estimate orientation across 24 px of arc; adjacent skeleton pixels have
    # quantized directions that falsely make a horizontal bend look matchable.
    positions = np.arange(len(ir))
    tangent = ir[np.minimum(positions+6, len(ir)-1)]-ir[np.maximum(positions-6, 0)]
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1)[:, None], 1e-9)
    norm_rgb = cv2.undistortPoints(rgb[:, None], stereo.kr, stereo.dr)[:, 0]
    rgb_positions = np.arange(len(rgb))
    rgb_tangent = norm_rgb[np.minimum(rgb_positions+3, len(rgb)-1)]-norm_rgb[np.maximum(rgb_positions-3, 0)]
    rgb_tangent /= np.maximum(np.linalg.norm(rgb_tangent, axis=1)[:, None], 1e-9)
    accepted, rejected = [], []
    last_i, last_s = None, None
    for i, line in enumerate(lines):
        signed = ir @ line[:2] + line[2]
        crossings = np.flatnonzero(signed[:-1]*signed[1:] <= 0)
        candidates = []
        for k in crossings:
            denominator = signed[k]-signed[k+1]
            if abs(denominator) < 1e-9:
                continue
            alpha = signed[k]/denominator
            s = ir_arc[k] + alpha*(ir_arc[k+1]-ir_arc[k])
            xy = ir[k] + alpha*(ir[k+1]-ir[k])
            direction = (1-alpha)*tangent[k]+alpha*tangent[k+1]
            # Intersection of curve and epipolar line becomes unstable near tangency.
            sine = abs(direction @ line[:2]) / max(np.linalg.norm(direction), 1e-9)
            ir_ray = np.linalg.solve(stereo.ki, np.r_[xy, 1.])
            rgb_line = stereo.e @ ir_ray
            rgb_sine = abs(rgb_tangent[i] @ rgb_line[:2]) / max(np.linalg.norm(rgb_line[:2]), 1e-9)
            if min(sine, rgb_sine) < .35:
                continue
            point = stereo.triangulate(rgb[i:i+1], xy[None])[0]
            if not np.isfinite(point).all() or point[2] <= 0 or (stereo.r @ point + stereo.t)[2] <= 0:
                continue
            if last_i is None:
                cost = s
            else:
                expected = (rgb_arc[i]-rgb_arc[last_i])*stereo.scale
                delta = s-last_s
                if not (.25*expected <= delta <= 2.5*expected):
                    continue
                cost = abs(delta-expected)
            candidates.append((cost, s, xy, point, sine))
        candidates.sort(key=lambda c: c[0])
        if not candidates:
            rejected.append({"rgb_index": i, "reason": "no_positive_ordered_non_tangent_match"})
            continue
        if len(candidates) > 1 and abs(candidates[0][0]-candidates[1][0]) < 3:
            rejected.append({"rgb_index": i, "reason": "ambiguous_candidates"})
            continue
        _, s, xy, point, sine = candidates[0]
        accepted.append({"rgb_index": i, "rgb": rgb[i].tolist(), "ir": xy.tolist(),
                         "xyz_mm": point.tolist(), "ir_arc_px": float(s), "crossing_sine": float(sine)})
        last_i, last_s = i, s
    # Do not present isolated fragments as supported reconstructions.
    if accepted:
        indices = np.array([a["rgb_index"] for a in accepted])
        groups = np.split(np.arange(len(accepted)), np.flatnonzero(np.diff(indices) > 1)+1)
        keep = []
        for group in groups:
            if len(group) >= 5:
                keep.extend(accepted[j] for j in group)
            else:
                rejected.extend({"rgb_index": accepted[j]["rgb_index"], "reason": "isolated_match_fragment"} for j in group)
        accepted = keep
    rejected.sort(key=lambda r: r["rgb_index"])
    return accepted, rejected
