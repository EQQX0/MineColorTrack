# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs a YOLO object-detection model (.onnx, e.g. trained with the Colab notebook) on captured frames.

Supports Ultralytics exports in both output layouts:
  - (1, 4 + classes, anchors): boxes as centre x, centre y, width, height plus a score per class (needs NMS)
  - (1, max_detections, 6): end-to-end boxes as x1, y1, x2, y2, score, class

The model runs on the fastest ONNX Runtime execution provider that works on this PC, tried in this order:
TensorRT, CUDA (both NVIDIA, need the onnxruntime-gpu package plus NVIDIA's libraries), DirectML (any DirectX 12
graphics card, onnxruntime-directml package) and the processor. A provider that is missing or fails to start is
logged and skipped.
"""
import ast
import contextlib
import glob
import hashlib
import io
import logging
import os
import sys
import time

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:          # the app still works without it; detection is then unavailable
    ort = None

log = logging.getLogger("minecolortrack.ai")

# (setting value, ONNX Runtime provider name, name shown to people), fastest first
PROVIDERS = (
    ("tensorrt", "TensorrtExecutionProvider", "TensorRT"),
    ("cuda", "CUDAExecutionProvider", "CUDA"),
    ("directml", "DmlExecutionProvider", "DirectML"),
    ("cpu", "CPUExecutionProvider", "processor (CPU)"),
)
DEVICES = ("auto",) + tuple(p[0] for p in PROVIDERS)
_ORT_NAME = {p[0]: p[1] for p in PROVIDERS}
_LABEL = {p[0]: p[2] for p in PROVIDERS}


class ModelError(Exception):
    pass


@contextlib.contextmanager
def _ort_output_to_log():
    """ONNX Runtime prints provider fallbacks ("EP Error ... Falling back") to standard output, which would spoil
    the `mct` tool's JSON. Catch that text and keep it in the log instead."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            yield
    finally:
        text = " ".join(buf.getvalue().split())
        if text:
            log.info("onnxruntime: %s", text[:2000])


def available():
    return ort is not None


def available_providers():
    return list(ort.get_available_providers()) if ort is not None else []


def runtime_package(have=None):
    """Which ONNX Runtime build is installed: 'gpu' (NVIDIA), 'directml', 'cpu', or None if none is."""
    have = available_providers() if have is None else have
    if not have:
        return None
    if "CUDAExecutionProvider" in have or "TensorrtExecutionProvider" in have:
        return "gpu"
    return "directml" if "DmlExecutionProvider" in have else "cpu"


def plan(device="auto"):
    """Providers to try for a device setting, best first, as [(key, ort_name)], plus notes for the person when
    the requested one is not part of the installed ONNX Runtime."""
    have = available_providers()
    keys = [p[0] for p in PROVIDERS]
    start = keys.index(device) if device in keys else 0
    chain = [(k, n) for k, n, _ in PROVIDERS[start:] if n in have]
    if not chain or chain[-1][0] != "cpu":
        chain.append(("cpu", "CPUExecutionProvider"))       # part of every ONNX Runtime build
    notes = []
    if device in ("tensorrt", "cuda") and _ORT_NAME[device] not in have:
        notes.append("%s needs the NVIDIA build of ONNX Runtime (onnxruntime-gpu); this copy of MineColorTrack "
                     "has the %s build. See README: NVIDIA acceleration." % (_LABEL[device],
                                                                             _package_label(have)))
    elif device == "directml" and "DmlExecutionProvider" not in have:
        notes.append("DirectML needs the onnxruntime-directml package (Windows), which is not installed.")
    elif device == "auto" and runtime_package(have) == "directml" and nvidia_driver_present():
        notes.append("NVIDIA graphics card found. TensorRT and CUDA can be faster than DirectML; they need the "
                     "NVIDIA build of ONNX Runtime (see README: NVIDIA acceleration).")
    return chain, notes


def _package_label(have):
    return {"gpu": "NVIDIA", "directml": "DirectML", "cpu": "processor-only"}[runtime_package(have) or "cpu"]


# ---------------------------------------------------------------- NVIDIA libraries (diagnosis only)
def cuda_build_version():
    """CUDA version the installed onnxruntime-gpu was built with, e.g. '12.8' or '13.0' (None if unknown)."""
    try:
        from onnxruntime.capi import build_and_package_info as info
        v = getattr(info, "cuda_version", None)
        if v:
            return str(v)
    except Exception:
        pass
    if ort is None:
        return None
    try:
        major, minor = (int(x) for x in ort.__version__.split(".")[:2])
    except ValueError:
        return None
    return "13.0" if (major, minor) >= (1, 27) else "12.8"   # PyPI defaults, per the ONNX Runtime CUDA docs


def _lib_names(key, cuda):
    """Library files a provider loads, by platform: [(file, what it is)]."""
    major = (cuda or "12").split(".")[0]
    if sys.platform == "win32":
        names = [("nvcuda.dll", "NVIDIA graphics driver"), ("cudart64_%s.dll" % major, "CUDA %s runtime" % major),
                 ("cublas64_%s.dll" % major, "CUDA %s cuBLAS" % major), ("cudnn64_9.dll", "cuDNN 9")]
        if key == "tensorrt":
            names.append(("nvinfer_10.dll", "TensorRT 10"))
    else:
        names = [("libcuda.so.1", "NVIDIA graphics driver"), ("libcudart.so.%s" % major, "CUDA %s runtime" % major),
                 ("libcublas.so.%s" % major, "CUDA %s cuBLAS" % major), ("libcudnn.so.9", "cuDNN 9")]
        if key == "tensorrt":
            names.append(("libnvinfer.so.10", "TensorRT 10"))
    return names


def _loadable(name):
    import ctypes
    try:
        (ctypes.WinDLL if sys.platform == "win32" else ctypes.CDLL)(name)
        return True
    except OSError:
        return False


def missing_libraries(key, loader=_loadable):
    """NVIDIA libraries that cannot be loaded for 'cuda' or 'tensorrt', as human-readable names."""
    return ["%s (%s)" % (what, name) for name, what in _lib_names(key, cuda_build_version()) if not loader(name)]


def nvidia_driver_present():
    if sys.platform == "win32":
        return os.path.exists(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvcuda.dll"))
    return False


def requirements_text(key):
    cuda = cuda_build_version() or "12.8"
    major = cuda.split(".")[0]
    driver = ("NVIDIA driver 570.65 or newer" if major == "12" else "an NVIDIA driver from the 580 series or newer")
    text = "%s needs an NVIDIA graphics card with %s, CUDA %s or newer %s.x and cuDNN 9" % (
        _LABEL[key], driver, cuda, major)
    if key == "tensorrt":
        text += ", plus TensorRT 10 for CUDA %s" % major
    return text + ". The folders holding their DLLs must be on PATH (or install onnxruntime-gpu[cuda,cudnn])."


def explain_failure(key, error, loader=_loadable, names=None):
    """A friendly sentence for a provider that did not start. `names`: what to call it ("TensorRT and CUDA")."""
    names = names or _LABEL[key]
    if key in ("tensorrt", "cuda"):
        missing = missing_libraries(key, loader)
        why = _short(error, 120)
        if missing:
            why = "missing %s; %s" % (", ".join(missing), why)
        return "%s could not start (%s). %s" % (names, why, requirements_text(key))
    return "%s could not start (%s)." % (names, _short(error))


def _short(error, limit=160):
    text = " ".join(str(error).split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


# ---------------------------------------------------------------- TensorRT engine cache
def trt_cache_folder(model_path, cache_dir, fp16):
    """One folder per model file content and precision, so a changed model never reuses an old engine."""
    h = hashlib.sha1()
    with open(model_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return os.path.join(cache_dir, "%s_%s" % (h.hexdigest()[:16], "fp16" if fp16 else "fp32"))


def trt_engine_cached(model_path, cache_dir, fp16):
    try:
        return bool(glob.glob(os.path.join(trt_cache_folder(model_path, cache_dir, fp16), "*.engine")))
    except OSError:
        return False


def needs_trt_build(model_path, device, fp16, cache_dir):
    """True when loading this model will build a TensorRT engine first (minutes, once per model and GPU)."""
    chain, _ = plan(device)
    return (chain[0][0] == "tensorrt" and bool(cache_dir) and os.path.isfile(model_path)
            and not trt_engine_cached(model_path, cache_dir, fp16))


# ---------------------------------------------------------------- model
def _parse_names(meta, count):
    raw = meta.get("names")
    names = {}
    if raw:
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, dict):
                names = {int(k): str(v) for k, v in parsed.items()}
            elif isinstance(parsed, (list, tuple)):
                names = {i: str(v) for i, v in enumerate(parsed)}
        except (ValueError, SyntaxError):
            names = {}
    return [names.get(i, "class %d" % i) for i in range(count)]


class Detection:
    __slots__ = ("cls", "x", "y", "w", "h", "conf")

    def __init__(self, cls, x, y, w, h, conf):
        self.cls, self.x, self.y, self.w, self.h, self.conf = cls, x, y, w, h, conf


class Detector:
    """`device`: 'auto' (fastest that works), or 'tensorrt', 'cuda', 'directml', 'cpu' to start the search there.
    `fp16`: let TensorRT use half precision. `cache_dir`: where TensorRT keeps built engines (None: no cache).
    `warmup`: run once on a blank picture, so slow first-time work (TensorRT engine build) happens now."""

    def __init__(self, path, device="auto", fp16=True, cache_dir=None, warmup=True):
        if ort is None:
            raise ModelError("The AI runtime (onnxruntime) is not installed.")
        if not os.path.isfile(path):
            raise ModelError("Model file not found: %s" % path)
        self.path = path
        self.fp16 = fp16
        self.cache_dir = cache_dir
        self.last_ms = {}
        self.fallbacks = []                   # (provider key, friendly message) for providers that did not start
        self._errors = {}
        try:                                  # read the model on the processor first: a bad file fails here, once
            probe = ort.InferenceSession(path, sess_options=self._options("cpu"), providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise ModelError("Could not open the model: %s" % _short(exc, 300))
        self._read_model(probe)

        chain, self.notes = plan(device)
        if chain[0][0] in ("tensorrt", "cuda") and hasattr(ort, "preload_dlls"):
            try:                              # finds CUDA/cuDNN installed as pip packages (onnxruntime-gpu >= 1.21)
                with _ort_output_to_log():
                    ort.preload_dlls()
            except Exception as exc:
                log.info("preload_dlls: %s", exc)
        have = available_providers()
        self.session = None
        for key, name in chain:
            if key == "cpu":
                self.session, self.provider = probe, "cpu"
                if warmup:
                    self._warmup()
                break
            try:
                sess = self._open(key, name, have)
                self.session, self.provider = sess, key
                if warmup:
                    self._warmup()
                break
            except Exception as exc:
                self.session = None
                self._errors[key] = exc
                self.fallbacks.append((key, explain_failure(key, exc)))
                log.warning("AI provider %s failed for %s: %s", name, os.path.basename(path), exc)
        if self.fallbacks:
            log.warning("AI model %s runs on %s", os.path.basename(path), self.device_label)
        self.device = "CPU" if self.provider == "cpu" else "GPU"

    @property
    def device_label(self):
        if self.provider == "tensorrt":
            return "TensorRT %s (NVIDIA)" % ("FP16" if self.fp16 else "FP32")
        if self.provider == "cuda":
            return "CUDA (NVIDIA)"
        if self.provider == "directml":
            return "DirectML (graphics card)"
        return "processor (CPU)"

    @property
    def notice(self):
        """What to tell the person about providers that were skipped, or None."""
        parts = list(self.notes)
        nvidia = [k for k, _ in self.fallbacks if k in ("tensorrt", "cuda")]
        if nvidia:                        # one sentence for both NVIDIA providers: they need the same libraries
            parts.append(explain_failure(nvidia[0], self._errors[nvidia[0]],
                                         names=" and ".join(_LABEL[k] for k in nvidia)))
        parts += [m for k, m in self.fallbacks if k not in nvidia]
        if not parts:
            return None
        return " ".join(parts) + " Using %s." % self.device_label

    @staticmethod
    def _options(key):
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        if key == "directml":           # DirectML does not support memory patterns or parallel execution
            opts.enable_mem_pattern = False
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return opts

    def _open(self, key, name, have):
        if key == "tensorrt":
            trt = {"trt_fp16_enable": bool(self.fp16)}
            if self.cache_dir:
                folder = trt_cache_folder(self.path, self.cache_dir, self.fp16)
                os.makedirs(folder, exist_ok=True)
                trt.update(trt_engine_cache_enable=True, trt_engine_cache_path=folder,
                           trt_timing_cache_enable=True, trt_timing_cache_path=self.cache_dir)
            providers = [(name, trt)]
            if "CUDAExecutionProvider" in have:          # runs any layers TensorRT cannot
                providers.append("CUDAExecutionProvider")
        else:
            providers = [name]
        providers.append("CPUExecutionProvider")
        with _ort_output_to_log():
            sess = ort.InferenceSession(self.path, sess_options=self._options(key), providers=providers)
        active = sess.get_providers()
        if not active or active[0] != name:          # ONNX Runtime quietly fell back to another provider
            raise RuntimeError("ONNX Runtime started %s instead" % (active[0] if active else "nothing"))
        return sess

    def _read_model(self, session):
        inp = session.get_inputs()[0]
        self.input_name = inp.name
        shape = inp.shape
        if len(shape) != 4:
            raise ModelError("This is not an image detection model (input shape %s)." % (shape,))
        meta = dict(session.get_modelmeta().custom_metadata_map)
        size = None
        if meta.get("imgsz"):
            try:
                size = ast.literal_eval(meta["imgsz"])
            except (ValueError, SyntaxError):
                size = None
        h = shape[2] if isinstance(shape[2], int) else (size[0] if size else 640)
        w = shape[3] if isinstance(shape[3], int) else (size[1] if size else 640)
        self.size = (int(h), int(w))
        out = session.get_outputs()[0].shape
        if len(out) != 3:
            raise ModelError("Unsupported model output %s. Export a YOLO detection model to ONNX." % (out,))
        # standard exports have thousands of anchors in the last axis; end-to-end ones have exactly 6 values per box
        self.end2end = out[2] == 6
        if self.end2end:
            try:
                count = len(ast.literal_eval(meta.get("names", "{}"))) or 1
            except (ValueError, SyntaxError):
                count = 1
        else:
            if not isinstance(out[1], int) or out[1] <= 4:
                raise ModelError("Unsupported model output %s." % (out,))
            count = out[1] - 4
        self.names = _parse_names(meta, count)

    def _warmup(self):
        h, w = self.size
        self.session.run(None, {self.input_name: np.zeros((1, 3, h, w), np.float32)})

    def _letterbox(self, frame):
        th, tw = self.size
        h, w = frame.shape[:2]
        r = min(tw / w, th / h)
        nw, nh = int(round(w * r)), int(round(h * r))
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((th, tw, 3), 114, np.uint8)
        px, py = (tw - nw) // 2, (th - nh) // 2
        canvas[py:py + nh, px:px + nw] = resized
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        return blob.transpose(2, 0, 1)[None], r, px, py

    def detect(self, frame_bgr, conf=0.4, iou=0.5, allowed=None):
        """Detections in frame pixels. `allowed`: set of class indexes to keep (None = all).
        Time per stage in milliseconds is left in `last_ms`."""
        t0 = time.perf_counter()
        blob, r, px, py = self._letterbox(frame_bgr)
        t1 = time.perf_counter()
        out = self.session.run(None, {self.input_name: blob})[0][0]
        t2 = time.perf_counter()
        if self.end2end:
            boxes = out[:, :4].astype(np.float32)
            scores = out[:, 4]
            cls = out[:, 5].astype(int)
            keep = scores >= conf
            boxes, scores, cls = boxes[keep], scores[keep], cls[keep]
            xyxy = boxes
        else:
            pred = out.T                                 # anchors x (4 + classes)
            cls_scores = pred[:, 4:]
            cls = cls_scores.argmax(axis=1)
            scores = cls_scores[np.arange(len(cls)), cls]
            keep = scores >= conf
            pred, scores, cls = pred[keep], scores[keep], cls[keep]
            cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
            xyxy = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], axis=1)
            if len(xyxy):
                # class-aware NMS: shift boxes of different classes apart so they never suppress each other
                offs = cls[:, None].astype(np.float32) * 4096.0
                rects = np.concatenate([xyxy[:, :2] + offs, xyxy[:, 2:] - xyxy[:, :2]], axis=1)
                idx = cv2.dnn.NMSBoxes(rects.tolist(), scores.astype(float).tolist(), conf, iou)
                idx = np.array(idx).reshape(-1) if len(idx) else np.array([], int)
                xyxy, scores, cls = xyxy[idx], scores[idx], cls[idx]
        fh, fw = frame_bgr.shape[:2]
        dets = []
        for (x1, y1, x2, y2), s, c in zip(xyxy, scores, cls):
            if allowed is not None and int(c) not in allowed:
                continue
            x1 = max(0.0, (x1 - px) / r)
            y1 = max(0.0, (y1 - py) / r)
            x2 = min(float(fw), (x2 - px) / r)
            y2 = min(float(fh), (y2 - py) / r)
            if x2 - x1 >= 2 and y2 - y1 >= 2:
                dets.append(Detection(int(c), x1, y1, x2 - x1, y2 - y1, float(s)))
        t3 = time.perf_counter()
        self.last_ms = {"preprocess": (t1 - t0) * 1000.0, "inference": (t2 - t1) * 1000.0,
                        "postprocess": (t3 - t2) * 1000.0}
        return dets


def _iou(a, b):
    ix = max(0.0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
    iy = max(0.0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def compare_detections(reference, other, min_iou=0.5):
    """How close two detection lists are (for example TensorRT FP16 against processor FP32 on the same picture):
    pairs of the same class with the best overlap, the largest box edge shift in pixels and confidence change."""
    left = list(other)
    matched, shift, conf_diff, worst_iou = 0, 0.0, 0.0, 1.0
    for a in sorted(reference, key=lambda d: -d.conf):
        best, best_iou = None, min_iou
        for b in left:
            if b.cls == a.cls:
                v = _iou(a, b)
                if v >= best_iou:
                    best, best_iou = b, v
        if best is None:
            continue
        left.remove(best)
        matched += 1
        worst_iou = min(worst_iou, best_iou)
        shift = max(shift, abs(a.x - best.x), abs(a.y - best.y),
                    abs(a.x + a.w - best.x - best.w), abs(a.y + a.h - best.y - best.h))
        conf_diff = max(conf_diff, abs(a.conf - best.conf))
    return {"reference": len(reference), "other": len(other), "matched": matched,
            "missing": len(reference) - matched, "extra": len(left), "max_shift_px": round(shift, 2),
            "max_confidence_change": round(conf_diff, 4), "min_iou": round(worst_iou if matched else 0.0, 4)}


def benchmark(path, image, runs=50, cache_dir=None, conf=0.4, devices=None):
    """Time each device on one picture and compare its boxes with the processor's FP32 result (the reference).
    Returns a list with one entry per device: load time, ms per stage, detections, and the comparison."""
    have = available_providers()
    variants = [("cpu", False)]
    for key, name, _ in PROVIDERS:
        if key != "cpu" and name in have:
            variants += [("tensorrt", True), ("tensorrt", False)] if key == "tensorrt" else [(key, False)]
    if devices:
        variants = [v for v in variants if v[0] == "cpu" or v[0] in devices]
    results, reference = [], None
    for key, fp16 in variants:
        entry = {"device": key, "fp16": fp16}
        t = time.perf_counter()
        det = Detector(path, device=key, fp16=fp16, cache_dir=cache_dir)
        entry["load_seconds"] = round(time.perf_counter() - t, 2)
        if det.provider != key:
            entry["skipped"] = det.notice or "did not start"
            results.append(entry)
            continue
        found = det.detect(image, conf=conf)
        totals = dict.fromkeys(("preprocess", "inference", "postprocess"), 0.0)
        for _ in range(max(1, runs)):
            found = det.detect(image, conf=conf)
            for k in totals:
                totals[k] += det.last_ms[k]
        entry["label"] = det.device_label
        entry["ms"] = {k: round(v / max(1, runs), 3) for k, v in totals.items()}
        entry["ms"]["total"] = round(sum(entry["ms"].values()), 3)
        entry["detections"] = len(found)
        if reference is None:
            reference = found
        else:
            entry["vs_cpu_fp32"] = compare_detections(reference, found)
        results.append(entry)
    return results
