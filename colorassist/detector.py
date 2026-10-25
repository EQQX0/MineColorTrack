# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs a YOLO object-detection model (.onnx, e.g. trained with the Colab notebook) on captured frames.

Supports Ultralytics exports in both output layouts:
  - (1, 4 + classes, anchors): boxes as centre x, centre y, width, height plus a score per class (needs NMS)
  - (1, max_detections, 6): end-to-end boxes as x1, y1, x2, y2, score, class
"""
import ast
import os

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:          # the app still works without it; detection is then unavailable
    ort = None


class ModelError(Exception):
    pass


def available():
    return ort is not None


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
    def __init__(self, path, prefer_gpu=True):
        if ort is None:
            raise ModelError("The AI runtime (onnxruntime) is not installed.")
        if not os.path.isfile(path):
            raise ModelError("Model file not found: %s" % path)
        providers = ["CPUExecutionProvider"]
        if prefer_gpu:
            for p in ("DmlExecutionProvider", "CUDAExecutionProvider"):
                if p in ort.get_available_providers():
                    providers.insert(0, p)
                    break
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        try:
            self.session = ort.InferenceSession(path, sess_options=opts, providers=providers)
        except Exception as exc:
            if providers[0] != "CPUExecutionProvider":          # GPU failed: try CPU
                self.session = ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])
            else:
                raise ModelError("Could not open the model: %s" % exc)
        self.path = path
        self.device = "GPU" if self.session.get_providers()[0] != "CPUExecutionProvider" else "CPU"
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        shape = inp.shape
        if len(shape) != 4:
            raise ModelError("This is not an image detection model (input shape %s)." % (shape,))
        meta = dict(self.session.get_modelmeta().custom_metadata_map)
        size = None
        if meta.get("imgsz"):
            try:
                size = ast.literal_eval(meta["imgsz"])
            except (ValueError, SyntaxError):
                size = None
        h = shape[2] if isinstance(shape[2], int) else (size[0] if size else 640)
        w = shape[3] if isinstance(shape[3], int) else (size[1] if size else 640)
        self.size = (int(h), int(w))
        out = self.session.get_outputs()[0].shape
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
        """Detections in frame pixels. `allowed`: set of class indexes to keep (None = all)."""
        blob, r, px, py = self._letterbox(frame_bgr)
        out = self.session.run(None, {self.input_name: blob})[0][0]
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
        return dets
