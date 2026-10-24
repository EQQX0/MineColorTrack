"""Background worker: capture -> detect -> track -> effects, handed to the GUI as a Result."""
import threading
import time

import cv2
import mss
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage

from . import vision, winplat

_MSS = getattr(mss, "MSS", None) or mss.mss   # mss 10 renamed the factory


def to_qimage(bgr):
    if bgr is None:
        return None
    if bgr.ndim == 2:
        h, w = bgr.shape
        return QImage(np.ascontiguousarray(bgr).data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class Result:
    """One processed frame. Coordinates are in captured-frame pixels."""
    __slots__ = ("rect", "frame_size", "tracks", "frame_img", "preview_img", "fps", "count")

    def __init__(self):
        self.rect = None
        self.frame_size = (1, 1)
        self.tracks = []            # (x, y, w, h, held, name, outline_hex)
        self.frame_img = self.preview_img = None
        self.fps = 0.0
        self.count = 0


def clamp_rect(rect, bounds):
    x, y, w, h = rect
    bx, by, bw, bh = bounds
    x0, y0 = max(x, bx), max(y, by)
    x1, y1 = min(x + w, bx + bw), min(y + h, by + bh)
    if x1 - x0 < 16 or y1 - y0 < 16:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


class Engine(QObject):
    result = pyqtSignal(object)
    status = pyqtSignal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.want_frame = False         # mirror mode needs the raw frame image
        self.preview_target = None      # index of target whose mask to preview
        self.last_frame = None          # latest raw BGR frame, for the colour picker
        self.last_rect = None
        self._tracker = vision.Tracker()
        self._thread = None
        self._stop = threading.Event()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._tracker.reset()
        self._thread = threading.Thread(target=self._run, name="MineColorTrackEngine", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def reset_tracking(self):
        self._tracker.reset()

    def resolve_rect(self, sct):
        cap = self.cfg.capture
        bounds = sct.monitors[0]
        bounds = (bounds["left"], bounds["top"], bounds["width"], bounds["height"])
        if cap.source == "window":
            rect = winplat.find_window(cap.window_title, cap.window_exe)
            if rect is None:
                if not winplat.IS_WIN:
                    msg = "Watching a window only works on Windows. Choose a monitor instead."
                elif not (cap.window_title or cap.window_exe):
                    msg = "Choose a window on the Watch page."
                else:
                    msg = "Waiting for the window \u201c%s\u201d. Open it and make sure it is not minimised." % (
                        cap.window_title or cap.window_exe)
                return None, msg
        elif cap.source == "monitor":
            idx = cap.monitor if 1 <= cap.monitor < len(sct.monitors) else 1
            m = sct.monitors[idx]
            rect = (m["left"], m["top"], m["width"], m["height"])
        else:
            rect = tuple(cap.region)
        rect = clamp_rect(rect, bounds)
        return rect, (None if rect else "Capture area is off screen or too small.")

    def _run(self):
        try:
            with _MSS() as sct:
                self._loop(sct)
        except Exception as exc:  # report instead of dying silently
            self.status.emit("Capture stopped: %s" % exc)

    def _loop(self, sct):
        rect, msg, next_lookup = None, None, 0.0
        fps_avg, last = 0.0, time.perf_counter()
        while not self._stop.is_set():
            t0 = time.perf_counter()
            if t0 >= next_lookup or rect is None:
                rect, msg = self.resolve_rect(sct)
                next_lookup = t0 + 0.5
                if rect is None:
                    self.status.emit(msg)
                    self._stop.wait(0.5)
                    continue
            shot = sct.grab({"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]})
            frame = np.ascontiguousarray(np.asarray(shot)[:, :, :3])
            self.last_frame, self.last_rect = frame, rect
            self.result.emit(self.process(frame, rect))

            now = time.perf_counter()
            dt = now - last
            last = now
            fps_avg = (0.9 * fps_avg + 0.1 / dt) if fps_avg else 1.0 / max(dt, 1e-6)
            self._fps = fps_avg
            budget = 1.0 / max(1, self.cfg.capture.fps)
            self._stop.wait(max(0.0, budget - (time.perf_counter() - t0)))

    def process(self, frame, rect):
        prof = self.cfg.profile
        targets = list(prof.targets)
        scale = self.cfg.capture.scale / 100.0
        blobs, small, _ = vision.detect(frame, targets, prof.tracking, scale)
        tracks = self._tracker.update(blobs, prof.tracking.smoothing, prof.tracking.hold_frames)

        res = Result()
        res.rect = rect
        h, w = frame.shape[:2]
        res.frame_size = (w, h)
        res.fps = getattr(self, "_fps", 0.0)
        for t in tracks:
            if t.target >= len(targets):
                continue
            tg = targets[t.target]
            res.tracks.append((*t.box.tolist(), t.missed > 0, tg.name, tg.outline_color))
        res.count = sum(1 for t in tracks if t.missed == 0)

        if self.want_frame:
            res.frame_img = to_qimage(frame)

        pi = self.preview_target
        if pi is not None and 0 <= pi < len(targets):
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            pm = vision.target_mask(hsv, targets[pi])
            ph = 180
            pw = max(1, int(pm.shape[1] * ph / pm.shape[0]))
            res.preview_img = to_qimage(cv2.resize(pm, (pw, ph), interpolation=cv2.INTER_NEAREST))
        return res


def grab_once(cfg):
    """One frame of the configured capture area (used by pickers when the engine is stopped)."""
    eng = Engine(cfg)
    with _MSS() as sct:
        rect, msg = eng.resolve_rect(sct)
        if rect is None:
            return None, None, msg
        shot = sct.grab({"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]})
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3]), rect, None


def grab_monitor(index):
    """Screenshot of one monitor plus its physical rect."""
    with _MSS() as sct:
        idx = index if 1 <= index < len(sct.monitors) else 1
        m = sct.monitors[idx]
        shot = sct.grab(m)
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3]), (m["left"], m["top"], m["width"], m["height"])


def monitor_names():
    with _MSS() as sct:
        return ["%d: %dx%d at (%d, %d)" % (i, m["width"], m["height"], m["left"], m["top"])
                for i, m in enumerate(sct.monitors) if i > 0]


def grab_monitor_rect(index):
    with _MSS() as sct:
        m = sct.monitors[index if 1 <= index < len(sct.monitors) else 1]
        return (m["left"], m["top"], m["width"], m["height"])


def grab_rect(rect):
    with _MSS() as sct:
        shot = sct.grab({"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]})
        return np.asarray(shot)[:, :, :3]
