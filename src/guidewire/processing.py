"""Process one RGB/IR pair without camera access, persistence or plotting."""
import time

import cv2
import numpy as np

from .segmentation import segment
from .centerline import centerline, resample
from .matching import match_curves


def extract(image, modality):
    if modality == "ir" and np.mean(image >= 250) > .05:
        raise ValueError("IR overexposed (>5% saturated); reconstruction withheld")
    if modality == "ir":
        image = cv2.medianBlur(image, 7)  # Suppress projector speckles before ridge extraction.
    mask, _ = segment(image, modality)
    path, reason = centerline(mask)
    points, arc = resample(path, 5 if modality == "rgb" else 2)
    return points, arc, reason


def process_pair(pair, stereo, pool):
    started = time.monotonic()
    futures = {name: pool.submit(extract, pair[name], name) for name in ("rgb", "ir")}
    result = {**pair, "matches": [], "rejections": [], "errors": [], "curves": {}}
    extracted = {}
    for name, future in futures.items():
        try:
            points, arc, reason = future.result()
            extracted[name] = points, arc
            result["curves"][name] = points
            result[f"{name}_stop"] = reason
        except ValueError as exc:
            result["errors"].append(f"{name.upper()}: {exc}")
    if len(extracted) == 2:
        rgb, rgb_arc = extracted["rgb"]
        ir, ir_arc = extracted["ir"]
        result["matches"], result["rejections"] = match_curves(rgb, rgb_arc, ir, ir_arc, stereo)
    result["status"] = "partial_reconstruction" if result["matches"] else "no_reliable_reconstruction"
    result["compute_s"] = time.monotonic()-started
    result["finished_at"] = time.monotonic()
    result["pair_gap_ms"] = (pair["rgb_timestamp_us"]-pair["ir_timestamp_us"])/1000
    return result
