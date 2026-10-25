# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Screen capture back-ends.

- "fast": Windows Desktop Duplication (DXGI) through the dxcam library. Reads the GPU's finished desktop image,
  so it keeps up with high frame rates.
- "compatible": classic GDI screen copy through mss. Works everywhere, slower for big areas.
- "auto": fast when it works on this PC, otherwise compatible.

All rectangles are physical screen pixels (x, y, w, h) on the virtual desktop. Frames are BGR numpy arrays.
"""
import threading
import time

import mss
import numpy as np

try:
    import dxcam
except Exception:          # not Windows, or not installed
    dxcam = None

_MSS = getattr(mss, "MSS", None) or mss.mss   # mss 10 renamed the factory


class CaptureError(Exception):
    def __init__(self, message, temporary=False):
        super().__init__(message)
        self.temporary = temporary          # True: use the compatible method for this one picture only


class MssCapture:
    name = "compatible"
    label = "compatible screen copy"

    def __init__(self):
        self._local = threading.local()      # mss handles are per thread

    def _sct(self):
        sct = getattr(self._local, "sct", None)
        if sct is None:
            sct = self._local.sct = _MSS()
        return sct

    def grab(self, rect):
        x, y, w, h = (int(v) for v in rect)
        shot = self._sct().grab({"left": x, "top": y, "width": w, "height": h})
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3])

    def close(self):
        sct = getattr(self._local, "sct", None)
        if sct is not None:
            sct.close()
            self._local.sct = None


class DxgiCapture:
    name = "fast"
    label = "fast capture (Desktop Duplication)"

    def __init__(self):
        if dxcam is None:
            raise CaptureError("Fast capture needs Windows and the dxcam library.")
        self._lock = threading.Lock()
        self.outputs = []                     # (left, top, right, bottom, camera)
        lines = [ln for ln in dxcam.output_info().splitlines() if ln.startswith("Device[")]
        for ln in lines:
            d = int(ln.split("Device[")[1].split("]")[0])
            o = int(ln.split("Output[")[1].split("]")[0])
            try:
                cam = dxcam.create(device_idx=d, output_idx=o, output_color="BGR")
                dc = cam._output.desc.DesktopCoordinates
                self.outputs.append((dc.left, dc.top, dc.right, dc.bottom, cam))
            except Exception:
                continue
        if not self.outputs:
            raise CaptureError("No screen could be opened for fast capture.")

    def _output_for(self, rect):
        x, y, w, h = rect
        best, area = None, 0
        for out in self.outputs:
            l, t, r, b, _ = out
            ow = min(x + w, r) - max(x, l)
            oh = min(y + h, b) - max(y, t)
            if ow > 0 and oh > 0 and ow * oh > area:
                best, area = out, ow * oh
        return best, area

    def grab(self, rect, timeout=0.25):
        x, y, w, h = (int(v) for v in rect)
        out, area = self._output_for((x, y, w, h))
        if out is None:
            raise CaptureError("The capture area is not on any screen.")
        if area < w * h:
            raise CaptureError("The capture area spans more than one screen.", temporary=True)
        l, t, _, _, cam = out
        region = (x - l, y - t, x - l + w, y - t + h)
        end = time.perf_counter() + timeout
        with self._lock:
            while True:
                # new_frame_only=False: when nothing changed on screen, reuse the last picture of this area
                frame = cam.grab(region=region, new_frame_only=False)
                if frame is not None:
                    return np.ascontiguousarray(frame[:, :, :3])
                if time.perf_counter() > end:
                    raise CaptureError("Fast capture returned no new picture yet.", temporary=True)
                time.sleep(0.005)

    def close(self):
        for *_, cam in self.outputs:
            try:
                cam.release()
            except Exception:
                pass
        self.outputs = []


class AutoCapture:
    """Fast capture with an automatic, permanent switch to the compatible one if it fails."""

    def __init__(self, prefer_fast=True):
        self.compat = MssCapture()
        self.fast = None
        self.problem = None
        if prefer_fast:
            try:
                self.fast = DxgiCapture()
            except Exception as exc:
                self.problem = str(exc)

    @property
    def name(self):
        return self.fast.name if self.fast else self.compat.name

    @property
    def label(self):
        return self.fast.label if self.fast else self.compat.label

    def grab(self, rect):
        if self.fast is not None:
            try:
                return self.fast.grab(rect)
            except CaptureError as exc:
                if exc.temporary:
                    return self.compat.grab(rect)          # just this picture
                self.problem = str(exc)
            except Exception as exc:                        # driver/device lost etc.
                self.problem = str(exc)
            self.fast.close()
            self.fast = None
        return self.compat.grab(rect)

    def close(self):
        if self.fast:
            self.fast.close()
        self.compat.close()


_shared = {}
_shared_lock = threading.Lock()


def get(method):
    """Shared capture object for a method ("auto", "fast" or "compatible")."""
    with _shared_lock:
        cap = _shared.get(method)
        if cap is None:
            if method == "compatible":
                cap = AutoCapture(prefer_fast=False)
            else:
                cap = AutoCapture(prefer_fast=True)
            _shared[method] = cap
        return cap


def fast_available():
    return dxcam is not None


def benchmark(cap, rect, n=30):
    """Average milliseconds per grab."""
    cap.grab(rect)
    t = time.perf_counter()
    for _ in range(n):
        cap.grab(rect)
    return (time.perf_counter() - t) / n * 1000.0
