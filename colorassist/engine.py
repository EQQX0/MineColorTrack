# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Background worker: capture -> colour and AI detection -> tracking, handed to the GUI as a Result."""
import os
import threading
import time

import cv2
import mss
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage

from . import capture, config, detection_log, detector, vision, winplat

_MSS = getattr(mss, "MSS", None) or mss.mss   # mss 10 renamed the factory
ENTITY_BASE = 1000                              # tracker ids at or above this are AI entities, below are colour targets
PALETTE = ["#FFE600", "#00E5FF", "#FF3DFF", "#FF8A00", "#7CFF4F", "#FF4F6E", "#9D7CFF", "#FFFFFF"]
# Milliseconds per frame are measured for these stages ("draw" adds the window's painting, measured by the view)
STAGES = ("capture", "colour", "preprocess", "inference", "postprocess", "draw")
BUILDING = "Building engine, this can take a few minutes"


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
    __slots__ = ("rect", "frame_size", "tracks", "frame_img", "preview_img", "fps", "count", "ai_device",
                 "ai_label", "ai_error", "ai_status", "ai_notice", "capture", "timings", "kinds")

    def __init__(self):
        self.rect = None
        self.frame_size = (1, 1)
        self.tracks = []            # (x, y, w, h, held, name, outline_hex)
        self.kinds = []             # "colour" or "entity", one per track
        self.frame_img = self.preview_img = None
        self.fps = 0.0
        self.count = 0
        self.ai_device = None       # "GPU"/"CPU" while a model runs
        self.ai_label = None        # where it runs, e.g. "TensorRT FP16 (NVIDIA)"
        self.ai_error = None        # the model cannot be used
        self.ai_status = None       # loading or building, e.g. BUILDING
        self.ai_notice = None       # devices that were skipped, and why
        self.capture = ""           # which capture method produced the frame
        self.timings = {}           # stage -> milliseconds, averaged over recent frames


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

    def __init__(self, cfg, cache_dir=None):
        super().__init__()
        self.cfg = cfg
        self.cache_dir = cache_dir or config.trt_cache_dir()   # TensorRT engines, built once per model and GPU
        self.want_frame = False         # mirror mode needs the raw frame image
        self.preview_target = None      # index of target whose mask to preview
        self.last_frame = None          # latest raw BGR frame, for the colour picker
        self.last_rect = None
        self._tracker = vision.Tracker()
        self._detector = None
        self._detector_key = None
        self._detector_error = None
        self._loading_key = None        # model being loaded in the background, and what to tell the person
        self._ai_status = None
        self._load_lock = threading.Lock()
        self._ms = {}                   # running averages of the stage times
        self._thread = None
        self._stop = threading.Event()
        self._writer = None             # live detections file, see detection_log
        self._writer_key = None
        self._frame_no = 0

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
        self._close_export()

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
            cap = capture.get(self.cfg.capture.method)
            tg = time.perf_counter()
            frame = cap.grab(rect)
            grabbed = time.perf_counter()
            self.last_frame, self.last_rect = frame, rect
            res = self.process(frame, rect, capture_ms=(grabbed - tg) * 1000.0)
            res.capture = cap.label
            self._export(res)
            self.result.emit(res)

            now = time.perf_counter()
            dt = now - last
            last = now
            fps_avg = (0.9 * fps_avg + 0.1 / dt) if fps_avg else 1.0 / max(dt, 1e-6)
            self._fps = fps_avg
            budget = 1.0 / max(1, self.cfg.capture.fps)
            self._stop.wait(max(0.0, budget - (time.perf_counter() - t0)))

    def _close_export(self):
        if self._writer is not None:
            self._writer.close()
        self._writer, self._writer_key = None, None

    def _export(self, res):
        """Write this frame's detections to the live file when Settings > export is on."""
        ex = self.cfg.export
        key = (ex.path, ex.history) if ex.enabled else None
        if key != self._writer_key:                   # switched on, off or moved while running
            self._close_export()
            self._writer_key = key
            if key:
                path = ex.path or os.path.join(os.path.dirname(self.cache_dir), "detections.json")
                try:
                    self._writer = detection_log.DetectionWriter(path, ex.history)
                except OSError as exc:
                    self.status.emit("Cannot write the detections file: %s" % exc)
        if self._writer is not None:
            self._frame_no += 1
            self._writer.push(detection_log.record(res, self._frame_no))

    def _load(self, key):
        path, device, fp16, cache_dir = key
        det, error = None, None
        try:
            det = detector.Detector(path, device, fp16, cache_dir)
        except Exception as exc:              # bad file, missing runtime, unsupported model...
            error = str(exc)
        with self._load_lock:
            if self._loading_key in (None, key):      # not replaced by newer settings meanwhile
                self._detector, self._detector_error, self._detector_key = det, error, key
                self._loading_key, self._ai_status = None, None

    def _get_detector(self, path, device, fp16):
        key = (path, device, fp16, self.cache_dir)
        if key == self._detector_key:
            return self._detector
        if threading.current_thread() is not self._thread:
            self._load(key)                   # a one-off call (mct detect, tests): load right here
            return self._detector
        with self._load_lock:                 # live capture: load in the background, colour targets keep going
            if key != self._loading_key:
                self._loading_key = key
                try:
                    build = detector.needs_trt_build(path, device, fp16, self.cache_dir)
                except Exception:
                    build = False
                self._ai_status = BUILDING if build else "Loading the AI model"
                threading.Thread(target=self._load, args=(key,), name="MineColorTrackModel", daemon=True).start()
        return None

    def _average(self, ms):
        """Smooth the stage times over recent frames; stages not measured this frame are dropped."""
        old = self._ms
        self._ms = {k: (0.9 * old[k] + 0.1 * v) if k in old else v for k, v in ms.items()}
        return {k: round(v, 2) for k, v in self._ms.items()}

    def process(self, frame, rect, capture_ms=None):
        prof = self.cfg.profile
        targets = list(prof.targets)
        scale = self.cfg.capture.scale / 100.0
        ms = {} if capture_ms is None else {"capture": capture_ms}
        t = time.perf_counter()
        blobs, small, _ = vision.detect(frame, targets, prof.tracking, scale)
        ms["colour"] = (time.perf_counter() - t) * 1000.0

        res = Result()
        det_cfg = prof.detection
        names, entities = [], {}
        if det_cfg.enabled and det_cfg.model_path:
            det = self._get_detector(det_cfg.model_path, self.cfg.ai.device, self.cfg.ai.tensorrt_fp16)
            if det is None and self._loading_key is not None:
                res.ai_status = self._ai_status
            else:
                res.ai_error = self._detector_error
            if det is not None:
                res.ai_device, res.ai_label, res.ai_notice = det.device, det.device_label, det.notice
                names = det.names
                entities = {e.name: e for e in det_cfg.entities}
                allowed = {i for i, n in enumerate(names) if n not in entities or entities[n].enabled}
                if allowed:
                    for d in det.detect(frame, conf=max(1, det_cfg.confidence) / 100.0, allowed=allowed):
                        blobs.append(vision.Blob(ENTITY_BASE + d.cls, d.x, d.y, d.w, d.h, int(d.w * d.h)))
                    ms.update(det.last_ms)
        t_track = time.perf_counter()
        fh, fw = frame.shape[:2]
        cap = self.cfg.capture
        if cap.focus_shape != "off":                  # only look in the middle zone
            blobs = [b for b in blobs if vision.focus_contains(cap.focus_shape, cap.focus_size, fw, fh,
                                                                b.x + b.w / 2.0, b.y + b.h / 2.0)]
        tracks = self._tracker.update(blobs, prof.tracking.smoothing, prof.tracking.hold_frames)

        res.rect = rect
        h, w = frame.shape[:2]
        res.frame_size = (w, h)
        res.fps = getattr(self, "_fps", 0.0)
        for t in tracks:
            if t.target >= ENTITY_BASE:
                cls = t.target - ENTITY_BASE
                if cls >= len(names):
                    continue
                ent = entities.get(names[cls])
                colour = ent.outline_color if ent else PALETTE[cls % len(PALETTE)]
                res.tracks.append((*t.box.tolist(), t.missed > 0, names[cls], colour))
                res.kinds.append("entity")
                continue
            if t.target >= len(targets):
                continue
            tg = targets[t.target]
            res.tracks.append((*t.box.tolist(), t.missed > 0, tg.name, tg.outline_color))
            res.kinds.append("colour")
        res.count = sum(1 for t in tracks if t.missed == 0)
        ms["postprocess"] = ms.get("postprocess", 0.0) + (time.perf_counter() - t_track) * 1000.0

        t = time.perf_counter()
        if self.want_frame:
            res.frame_img = to_qimage(frame)

        pi = self.preview_target
        if pi is not None and 0 <= pi < len(targets):
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            pm = vision.target_mask(hsv, targets[pi])
            ph = 180
            pw = max(1, int(pm.shape[1] * ph / pm.shape[0]))
            res.preview_img = to_qimage(cv2.resize(pm, (pw, ph), interpolation=cv2.INTER_NEAREST))
        ms["draw"] = (time.perf_counter() - t) * 1000.0     # picture conversion; the view adds its painting
        res.timings = self._average(ms)
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


def grab_rect(rect, method=None):
    """One picture of a rect; with `method`, through that capture method (the overlay self-test needs this)."""
    if method:
        return capture.get(method).grab(rect)
    with _MSS() as sct:
        shot = sct.grab({"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]})
        return np.asarray(shot)[:, :, :3]
