"""Bounded timestamp pairing, independent of camera SDK and processing."""
from collections import deque
import threading
import time


class PairBuffer:
    def __init__(self):
        self.rgb, self.ir = deque(maxlen=12), deque(maxlen=12)
        self.lock = threading.Lock()
        self.last_received = time.monotonic()
        self.frames_received = 0
        self.error = None

    def add(self, modality, timestamp, image, received=None):
        if timestamp <= 0:
            return
        received = time.monotonic() if received is None else received
        with self.lock:
            queue = self.rgb if modality == "rgb" else self.ir
            if queue and timestamp <= queue[-1][0]:
                return
            queue.append((timestamp, received, image))
            self.last_received = received
            self.frames_received += 1

    def latest(self, after_timestamp=-1):
        with self.lock:
            if not self.ir:
                return None
            for color in reversed(self.rgb):
                if color[0] <= after_timestamp:
                    break
                # Wait for IR on both sides; do not pair prematurely to old IR.
                if not (self.ir[0][0] <= color[0] <= self.ir[-1][0]):
                    continue
                infrared = min(self.ir, key=lambda frame: abs(frame[0]-color[0]))
                if abs(color[0]-infrared[0]) > 120_000:
                    continue
                if time.monotonic()-min(color[1], infrared[1]) > 1.5:
                    continue
                return {"rgb": color[2], "ir": infrared[2], "rgb_timestamp_us": color[0],
                        "ir_timestamp_us": infrared[0], "received_at": min(color[1], infrared[1])}
        return None
