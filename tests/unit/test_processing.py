"""Live pairing and missing-target checks, without opening a camera."""
from concurrent.futures import ThreadPoolExecutor
import time
import unittest

import numpy as np

from guidewire.pairing import PairBuffer
from guidewire.processing import extract, process_pair
from tests.helpers import synthetic_stereo


class LiveChecks(unittest.TestCase):
    def test_overexposed_ir_is_rejected_before_curve_extraction(self):
        with self.assertRaisesRegex(ValueError, "overexposed"):
            extract(np.full((100, 100), 255, np.uint8), "ir")

    def test_wait_for_bracket_then_select_nearest_and_skip_processed(self):
        buffer = PairBuffer()
        buffer.add("rgb", 200_000, "color")
        buffer.add("ir", 90_000, "older")
        self.assertIsNone(buffer.latest())
        buffer.add("ir", 290_000, "nearer")
        pair = buffer.latest()
        self.assertEqual(pair["ir"], "nearer")
        self.assertIsNone(buffer.latest(pair["rgb_timestamp_us"]))

    def test_reject_stale_and_excessive_gap(self):
        buffer = PairBuffer()
        old = time.monotonic()-4
        buffer.add("rgb", 200_000, None, old)
        buffer.add("ir", 190_000, None, old)
        buffer.add("ir", 210_000, None, old)
        self.assertIsNone(buffer.latest())
        buffer = PairBuffer()
        buffer.add("rgb", 500_000, None)
        buffer.add("ir", 100_000, None)
        buffer.add("ir", 900_000, None)
        self.assertIsNone(buffer.latest())

    def test_latest_pair_wins_and_duplicates_are_ignored(self):
        buffer = PairBuffer()
        for timestamp in (100_000, 300_000, 500_000):
            buffer.add("rgb", timestamp, timestamp)
            buffer.add("ir", timestamp, timestamp)
        buffer.add("rgb", 500_000, "duplicate")
        self.assertEqual(buffer.latest()["rgb"], 500_000)
        self.assertEqual(buffer.frames_received, 6)

    def test_missing_target_produces_empty_result(self):
        pair = {"rgb": np.zeros((100, 100, 3), np.uint8),
                "ir": np.zeros((100, 100), np.uint8),
                "rgb_timestamp_us": 200_000, "ir_timestamp_us": 290_000,
                "received_at": time.monotonic()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = process_pair(pair, synthetic_stereo(), pool)
        self.assertEqual(result["status"], "no_reliable_reconstruction")
        self.assertEqual(result["matches"], [])
        self.assertEqual(len(result["errors"]), 2)
        self.assertEqual(result["pair_gap_ms"], -90.)


if __name__ == "__main__":
    unittest.main()
