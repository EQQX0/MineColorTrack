# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Write what the engine detects to a file, live, for other programs to read.

detections.json   the newest frame only, replaced in one step so a reader never sees half a file
detections.jsonl  optional: every frame, one JSON object per line, appended
"""
import json
import os
import threading
import time
from collections import deque


def record(res, frame_no):
    """One engine Result as a plain dict. Coordinates: x, y, w, h are captured-frame pixels
    (top-left corner), screen_x and screen_y are the same corner on the screen."""
    left, top = (res.rect[0], res.rect[1]) if res.rect else (0, 0)
    items = []
    for i, (x, y, w, h, held, name, _colour) in enumerate(res.tracks):
        kind = res.kinds[i] if i < len(res.kinds) else "colour"
        items.append({
            "name": name, "kind": kind,
            "x": round(x, 1), "y": round(y, 1), "w": round(w, 1), "h": round(h, 1),
            "cx": round(x + w / 2.0, 1), "cy": round(y + h / 2.0, 1),
            "screen_x": round(left + x, 1), "screen_y": round(top + y, 1),
            "lost": bool(held),          # true = not seen this frame, still kept for a moment
        })
    return {
        "t": round(time.time(), 3), "frame": frame_no, "fps": round(res.fps, 1),
        "capture_rect": list(res.rect) if res.rect else None,
        "frame_size": list(res.frame_size),
        "count": res.count, "detections": items,
    }


class DetectionWriter:
    """Hands records to a background thread so the capture loop never waits for the disk."""

    def __init__(self, path, history=False):
        self.path = path
        self.history_path = os.path.splitext(path)[0] + ".jsonl" if history else None
        self._queue = deque(maxlen=2000)
        self._wake = threading.Event()
        self._stop = False
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="MineColorTrackExport", daemon=True)
        self._thread.start()

    def push(self, rec):
        self._queue.append(rec)
        self._wake.set()

    def close(self):
        self._stop = True
        self._wake.set()
        self._thread.join(timeout=2)

    def _run(self):
        while True:
            self._wake.wait()
            self._wake.clear()
            batch = []
            while self._queue:
                batch.append(self._queue.popleft())
            if batch:
                try:
                    self._write(batch)
                except OSError:
                    pass                  # file busy or folder gone: skip, the next frame tries again
            if self._stop and not self._queue:
                return

    def _write(self, batch):
        lines = [json.dumps(r, separators=(",", ":")) for r in batch]
        tmp = self.path + ".tmp"
        for attempt in range(5):          # Windows refuses the swap while a reader has the file open
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(lines[-1])
                os.replace(tmp, self.path)
                break
            except PermissionError:
                time.sleep(0.005 * (attempt + 1))
        if self.history_path:
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
