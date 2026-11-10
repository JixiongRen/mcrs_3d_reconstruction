"""Run the bounded capture-processing-display loop at a target update rate."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import threading
import time

import cv2
import numpy as np

from ..camera import open_camera, acquire, restore_exposure
from ..pairing import PairBuffer
from ..processing import process_pair
from ..results import serializable, snapshot
from ..visualization import Display


def process_latest(buffer, stereo, hz, stop, state, lock, output):
    last_timestamp, next_start, sequence = -1, 0., 0
    completed = deque(maxlen=10)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool, (output / "updates.jsonl").open("w", encoding="utf-8") as log:
            while not stop.is_set():
                if stop.wait(max(0, next_start-time.monotonic())):
                    break
                pair = buffer.latest(last_timestamp)
                if pair is None:
                    stop.wait(.03)
                    continue
                start = time.monotonic()
                result = process_pair(pair, stereo, pool)
                last_timestamp = pair["rgb_timestamp_us"]
                next_start = max(start+1/hz, time.monotonic())
                sequence += 1
                completed.append(result["finished_at"])
                result["sequence"] = sequence
                result["actual_hz"] = ((len(completed)-1)/(completed[-1]-completed[0])) if len(completed) > 1 else 0.
                row = {"sequence": sequence, "status": result["status"], "points": len(result["matches"]),
                       "compute_s": result["compute_s"], "actual_hz": result["actual_hz"],
                       "pair_gap_ms": result["pair_gap_ms"], "rgb_timestamp_us": result["rgb_timestamp_us"],
                       "ir_timestamp_us": result["ir_timestamp_us"],
                       "received_to_result_s": result["finished_at"]-result["received_at"],
                       "completed_monotonic": result["finished_at"], "errors": result["errors"]}
                log.write(json.dumps(row)+"\n")
                log.flush()
                (output / "latest_result.json").write_text(json.dumps(serializable(result), indent=2), encoding="utf-8")
                print(f"update={sequence} {result['status']} points={row['points']} compute={row['compute_s']:.3f}s rate={row['actual_hz']:.2f}Hz gap={row['pair_gap_ms']:.1f}ms", flush=True)
                with lock:
                    state["result"] = result
    except Exception as exc:
        state["error"] = repr(exc)
        stop.set()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=1.)
    parser.add_argument("--duration", type=float, default=0., help="Seconds after camera start; 0 runs until closed")
    parser.add_argument("--ir-exposure", type=int, default=300, help="Temporary IR exposure in SDK units; original restored on exit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.hz <= 0 or args.duration < 0 or args.ir_exposure <= 0:
        parser.error("hz/exposure must be positive and duration nonnegative")
    cv2.setNumThreads(2)
    output = args.output or Path("outputs/captures") / ("live_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    context, pipeline, stereo, metadata = open_camera(args.ir_exposure)
    metadata["target_processing_hz"] = args.hz
    metadata["started_local"] = datetime.now().isoformat()
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    stop, lock, buffer = threading.Event(), threading.Lock(), PairBuffer()
    state, shown, result, saved_first = {}, 0, None, False
    reader = threading.Thread(target=acquire, args=(pipeline, buffer, stop), name="camera-reader")
    worker = threading.Thread(target=process_latest, args=(buffer, stereo, args.hz, stop, state, lock, output), name="reconstruction")
    title = "Gemini 2 - Live RGB IR Reconstruction"
    started, reason = time.monotonic(), "window_closed"
    try:
        display = Display()
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(title, 1280, 825)
        reader.start()
        worker.start()
        print(f"LIVE: {metadata['device']} output={output.resolve()}", flush=True)
        while not stop.is_set():
            with lock:
                latest = state.get("result")
            if latest is not None and latest["sequence"] != shown:
                result, shown = latest, latest["sequence"]
                display.update(result)
                canvas = display.compose(result, args.hz)
                cv2.imwrite(str(output / "latest_preview.jpg"), canvas)
                if shown == 1:
                    snapshot(output, result, canvas, "first_result")
                if result["matches"] and not saved_first:
                    snapshot(output, result, canvas, "first_valid")
                    saved_first = True
            canvas = display.compose(result, args.hz, buffer.error or state.get("error"))
            cv2.imshow(title, canvas)
            key = cv2.waitKey(25) & 0xFF
            if key in (ord('q'), 27) or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                reason = "user_closed"
                break
            if key == ord('s') and result is not None and time.monotonic()-result["received_at"] <= 3:
                snapshot(output, result, canvas, "snapshot_"+datetime.now().strftime("%H%M%S_%f"))
            if args.duration and time.monotonic()-started >= args.duration:
                reason = "duration_completed"
                break
            if time.monotonic()-buffer.last_received > 12:
                reason = "camera_frame_timeout"
                break
            if result is None and time.monotonic()-started > 15:
                reason = "no_usable_timestamp_pair"
                break
    except KeyboardInterrupt:
        reason = "keyboard_interrupt"
    finally:
        stop.set()
        if worker.ident:
            worker.join()
        if reader.ident:
            reader.join()
        if buffer.error or state.get("error"):
            reason = "camera_or_processing_error"
        try:
            pipeline.stop()
        except Exception as exc:
            state["error"] = f"Camera stop failed: {exc}"
            reason = "camera_stop_error"
        try:
            restore_exposure(pipeline, metadata)
        except Exception as exc:
            metadata["ir_exposure_restored"] = False
            state["error"] = f"IR exposure restore failed: {exc}"
            reason = "camera_restore_error"
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        cv2.destroyAllWindows()
        rows = [json.loads(line) for line in (output / "updates.jsonl").read_text().splitlines()] if (output / "updates.jsonl").exists() else []
        summary = {"stop_reason": reason, "elapsed_s": time.monotonic()-started,
                   "updates": len(rows), "updates_with_3d": sum(r["points"] > 0 for r in rows),
                   "camera_frames_received": buffer.frames_received, "error": buffer.error or state.get("error"),
                   "observed_update_hz": (len(rows)-1)/(rows[-1]["completed_monotonic"]-rows[0]["completed_monotonic"]) if len(rows) > 1 else 0.,
                   "median_compute_s": float(np.median([r["compute_s"] for r in rows])) if rows else None}
        (output / "session_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary), flush=True)
    if summary["error"] or reason in ("camera_frame_timeout", "no_usable_timestamp_pair"):
        raise SystemExit(1)
