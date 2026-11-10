import unittest
import cv2
import numpy as np
from guidewire.centerline import centerline, resample
from guidewire.matching import match_curves
from guidewire.segmentation import segment
from tests.helpers import synthetic_stereo


class OfflineChecks(unittest.TestCase):
    def test_small_tip_loop_does_not_absorb_free_endpoint(self):
        mask = np.zeros((200, 100), np.uint8)
        cv2.line(mask, (50, 30), (50, 180), 1, 3)
        cv2.circle(mask, (50, 25), 5, 1, 1)
        cv2.line(mask, (50, 20), (50, 12), 1, 1)
        path, _ = centerline(mask)
        self.assertGreater(np.ptp(path[:, 1]), 140)

    def test_curved_stereo_matches_recover_known_geometry(self):
        stereo = synthetic_stereo()
        t = np.linspace(0, 1, 500)
        truth = np.c_[60*t, -15+45*np.sin(np.pi*t), np.full(len(t), 100.)]
        rgb_raw, ir_raw = stereo.reproject(truth)
        rgb, rgb_arc = resample(rgb_raw, 5)
        ir, ir_arc = resample(ir_raw, 2)
        matches, rejected = match_curves(rgb, rgb_arc, ir, ir_arc, stereo)
        self.assertGreater(len(matches), 50)
        self.assertGreater(len(rejected), 0)  # Near-horizontal bend is deliberately omitted.
        points = np.array([m["xyz_mm"] for m in matches])
        np.testing.assert_allclose(points[:, 2], 100., atol=.2)
        self.assertTrue(np.all(np.diff([m["ir_arc_px"] for m in matches]) > 0))
        self.assertTrue(np.any(points[:, 0] < 20) and np.any(points[:, 0] > 40))

    def test_horizontal_curve_is_not_fabricated_into_depth(self):
        stereo = synthetic_stereo()
        points = np.c_[np.linspace(0, 60, 200), np.full(200, 10.), np.full(200, 100.)]
        rgb_raw, ir_raw = stereo.reproject(points)
        rgb, rgb_arc = resample(rgb_raw, 5)
        ir, ir_arc = resample(ir_raw, 2)
        matches, _ = match_curves(rgb, rgb_arc, ir, ir_arc, stereo)
        self.assertEqual(matches, [])

    def test_ir_bright_tube_wins_over_dark_shadow(self):
        image = np.full((400, 500), 30, np.uint8)
        t = np.linspace(0, 1, 250)
        # Separate parallel traces isolate bright/dark discrimination from the
        # distinct problem of overlapping curves and correspondence ambiguity.
        target = np.c_[150+120*t, 60+250*t].astype(np.int32)
        cv2.polylines(image, [target-np.array([60, 0])], False, 0, 10)
        cv2.polylines(image, [target], False, 180, 10)
        mask, _ = segment(image, "ir")
        path, _ = centerline(mask)
        distances = np.linalg.norm(path[:, None]-target[None], axis=2).min(axis=1)
        self.assertLess(np.percentile(distances, 95), 4)

    def test_missing_tube_rejects_instead_of_returning_points(self):
        with self.assertRaises(ValueError):
            segment(np.zeros((100, 100, 3), np.uint8), "rgb")
        with self.assertRaises(ValueError):
            segment(np.zeros((100, 100), np.uint8), "ir")
