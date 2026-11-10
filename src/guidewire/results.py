"""Result serialization and explicit image snapshots."""
import json

import cv2
import numpy as np


def serializable(result):
    return {key: (value.tolist() if isinstance(value, np.ndarray) else value)
            for key, value in result.items() if key not in ("rgb", "ir", "curves", "received_at", "finished_at")}


def snapshot(output, result, canvas, name):
    folder = output / name
    folder.mkdir(exist_ok=True)
    cv2.imwrite(str(folder / "rgb.jpg"), result["rgb"])
    cv2.imwrite(str(folder / "ir.png"), result["ir"])
    cv2.imwrite(str(folder / "display.jpg"), canvas)
    (folder / "result.json").write_text(json.dumps(serializable(result), indent=2), encoding="utf-8")
    np.savez_compressed(folder / "centerlines.npz", **result["curves"])
