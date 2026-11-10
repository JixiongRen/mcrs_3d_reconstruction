"""Compare preserved camera data against numerical baselines taken before refactoring."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

import cv2
import numpy as np

from guidewire.centerline import centerline, resample
from guidewire.matching import match_curves
from guidewire.processing import process_pair
from guidewire.segmentation import segment, dark_wire_candidates
from guidewire.stereo import Stereo

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/fixtures"


class RegressionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cv2.setNumThreads(2)
        cls.expected = json.loads((DATA / "expected.json").read_text())

    def test_retained_inputs_match_preservation_manifest(self):
        manifest = json.loads((ROOT / "docs/cleanup_manifest.json").read_text())
        for row in manifest["retained_files"]:
            with self.subTest(file=row["destination"]):
                self.assertEqual(hashlib.sha256((ROOT / row["destination"]).read_bytes()).hexdigest(), row["sha256"])

    def test_seven_catheter_pairs_preserve_matches_and_xyz(self):
        capture = DATA / "catheter_static"
        metadata = json.loads((capture / "metadata.json").read_text())
        checked = json.loads((capture / "triangulation/profile_calibration_check.json").read_text())
        stereo = Stereo(metadata, checked)
        with np.load(capture / "expected_xyz.npz") as expected_xyz:
            for rgb_id, expected in self.expected["catheter"].items():
                with self.subTest(rgb=rgb_id):
                    rgb_image = cv2.imread(str(capture / f"{int(rgb_id):04d}_rgb.jpg"))
                    ir_image = cv2.imread(str(capture / f"{expected['ir_index']:04d}_ir.png"), 0)
                    rgb, rgb_arc = resample(centerline(segment(rgb_image, "rgb")[0])[0], 5)
                    ir, ir_arc = resample(centerline(segment(ir_image, "ir")[0])[0], 2)
                    matches, _ = match_curves(rgb, rgb_arc, ir, ir_arc, stereo)
                    self.assertEqual(len(matches), expected["matches"])
                    np.testing.assert_allclose([m["xyz_mm"] for m in matches], expected_xyz[f"xyz_{rgb_id}"], atol=1e-8, rtol=0)

    def test_black_wire_alternatives_are_preserved(self):
        capture = DATA / "black_wire_horizontal"
        metadata = json.loads((capture / "metadata.json").read_text())
        stereo = Stereo(metadata, metadata["checked_profile"])
        rgb = dark_wire_candidates(cv2.imread(str(capture / "first_result/rgb.jpg")), "rgb")[0]
        infrared = dark_wire_candidates(cv2.imread(str(capture / "first_result/ir.png"), 0), "ir")
        self.assertEqual(len(infrared), len(self.expected["wire"]))
        for ir, expected in zip(infrared, self.expected["wire"]):
            matches, _ = match_curves(rgb["points"], rgb["arc"], ir["points"], ir["arc"], stereo)
            self.assertEqual(len(matches), expected["matches"])
            np.testing.assert_allclose([m["xyz_mm"] for m in matches], expected["xyz"], atol=1e-8, rtol=0)

    def test_live_processing_and_overexposure_rejection(self):
        for name, valid in (("catheter_live", True), ("catheter_tip_loop", True), ("ir_overexposed", False)):
            with self.subTest(fixture=name):
                capture = DATA / name
                metadata = json.loads((capture / "metadata.json").read_text())
                prior = json.loads((capture / "first_result/result.json").read_text())
                pair = {"rgb": cv2.imread(str(capture / "first_result/rgb.jpg")),
                        "ir": cv2.imread(str(capture / "first_result/ir.png"), 0),
                        "rgb_timestamp_us": prior["rgb_timestamp_us"],
                        "ir_timestamp_us": prior["ir_timestamp_us"], "received_at": time.monotonic()}
                with ThreadPoolExecutor(max_workers=2) as pool:
                    result = process_pair(pair, Stereo(metadata, metadata["checked_profile"]), pool)
                self.assertEqual(bool(result["matches"]), valid)
                if not valid:
                    self.assertIn("overexposed", ";".join(result["errors"]))

    def test_processing_import_does_not_load_camera_sdk_or_plotting(self):
        check = subprocess.run([sys.executable, "-c",
            "import sys; import guidewire.processing; import guidewire.stereo; "
            "assert 'pyorbbecsdk' not in sys.modules; assert 'matplotlib.pyplot' not in sys.modules"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(check.returncode, 0, check.stderr)
