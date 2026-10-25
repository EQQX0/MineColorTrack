# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Colour detection and box tracking.

Everything here is plain numpy/OpenCV so it can be tested without a screen.
"""
from dataclasses import dataclass

import cv2
import numpy as np


def hex_to_bgr(value):
    v = value.lstrip("#")
    if len(v) != 6:
        return (255, 0, 255)
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    return (b, g, r)


def bgr_to_hex(bgr):
    b, g, r = (int(x) for x in bgr)
    return "#%02X%02X%02X" % (r, g, b)


def hex_to_hsv(value):
    """OpenCV HSV: hue 0-179, saturation 0-255, value 0-255."""
    px = np.uint8([[hex_to_bgr(value)]])
    h, s, v = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0]
    return int(h), int(s), int(v)


def _kernel(radius):
    d = 2 * int(radius) + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d))


def target_mask(hsv, target):
    """255 where a pixel is within the target's colour range."""
    h, s, _ = hex_to_hsv(target.color)
    s_lo, s_hi = round(target.sat_min * 2.55), round(target.sat_max * 2.55)
    v_lo, v_hi = round(target.val_min * 2.55), round(target.val_max * 2.55)
    tol = int(round(target.hue_tol / 2))           # degrees -> OpenCV hue units
    if s < 38 or tol >= 90:                         # greys/whites have no meaningful hue
        ranges = [(0, 179)]
    elif h - tol < 0:
        ranges = [(h - tol + 180, 179), (0, h + tol)]
    elif h + tol > 179:
        ranges = [(h - tol, 179), (0, h + tol - 180)]
    else:
        ranges = [(h - tol, h + tol)]
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in ranges:
        mask |= cv2.inRange(hsv, (lo, s_lo, v_lo), (hi, s_hi, v_hi))
    return mask


@dataclass
class Blob:
    target: int
    x: float
    y: float
    w: float
    h: float
    area: int


def detect(frame_bgr, targets, tracking, scale):
    """Find coloured blobs.

    Returns (blobs in full-frame pixel coords, small frame, combined mask at small scale).
    """
    scale = max(0.1, min(1.0, scale))
    small = frame_bgr if scale >= 0.999 else cv2.resize(
        frame_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    combined = np.zeros(small.shape[:2], np.uint8)
    merge = max(1, int(round(tracking.merge_distance * scale)))
    blobs = []
    for i, t in enumerate(targets):
        if not t.enabled:
            continue
        m = target_mask(hsv, t)
        if tracking.noise_filter > 0:
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, _kernel(tracking.noise_filter))
        ys, xs = np.nonzero(m)
        if len(xs) == 0:
            continue
        combined |= m
        grouped = cv2.dilate(m, _kernel(merge))
        n, labels, _, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)
        lab = labels[ys, xs]
        counts = np.bincount(lab, minlength=n)
        x0 = np.full(n, np.iinfo(np.int32).max); np.minimum.at(x0, lab, xs)
        y0 = np.full(n, np.iinfo(np.int32).max); np.minimum.at(y0, lab, ys)
        x1 = np.full(n, -1); np.maximum.at(x1, lab, xs)
        y1 = np.full(n, -1); np.maximum.at(y1, lab, ys)
        area_k = scale * scale
        for j in range(1, n):
            a = counts[j] / area_k
            if a < t.min_area or (t.max_area and a > t.max_area):
                continue
            blobs.append(Blob(i, x0[j] / scale, y0[j] / scale,
                              (x1[j] - x0[j] + 1) / scale, (y1[j] - y0[j] + 1) / scale, int(a)))
    return blobs, small, combined


class Track:
    __slots__ = ("id", "target", "box", "area", "missed")

    def __init__(self, tid, blob):
        self.id, self.target, self.area, self.missed = tid, blob.target, blob.area, 0
        self.box = np.array([blob.x, blob.y, blob.w, blob.h], float)


def _match_score(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = min(ax + aw, bx + bw) - max(ax, bx)
    ih = min(ay + ah, by + bh) - max(ay, by)
    if iw > 0 and ih > 0:
        inter = iw * ih
        return 1.0 + inter / (aw * ah + bw * bh - inter)
    dist = np.hypot((ax + aw / 2) - (bx + bw / 2), (ay + ah / 2) - (by + bh / 2))
    limit = 0.75 * max(aw, ah, bw, bh)
    return 1.0 - dist / limit if dist < limit else 0.0


class Tracker:
    """Keeps boxes steady between frames so outlines do not flicker."""

    def __init__(self):
        self.tracks = []
        self._next = 1

    def reset(self):
        self.tracks = []

    def update(self, blobs, smoothing, hold_frames):
        alpha = 1.0 - 0.9 * max(0, min(100, smoothing)) / 100.0
        pairs = []
        for ti, t in enumerate(self.tracks):
            for bi, b in enumerate(blobs):
                if b.target == t.target:
                    s = _match_score(t.box, (b.x, b.y, b.w, b.h))
                    if s > 0:
                        pairs.append((s, ti, bi))
        pairs.sort(reverse=True)
        used_t, used_b = set(), set()
        for _, ti, bi in pairs:
            if ti in used_t or bi in used_b:
                continue
            used_t.add(ti)
            used_b.add(bi)
            t, b = self.tracks[ti], blobs[bi]
            t.box = alpha * np.array([b.x, b.y, b.w, b.h]) + (1 - alpha) * t.box
            t.area, t.missed = b.area, 0
        for ti, t in enumerate(self.tracks):
            if ti not in used_t:
                t.missed += 1
        self.tracks = [t for t in self.tracks if t.missed <= hold_frames]
        for bi, b in enumerate(blobs):
            if bi not in used_b:
                self.tracks.append(Track(self._next, b))
                self._next += 1
        return list(self.tracks)


def patch_stats(frame_bgr, x, y, radius=4):
    """Average colour around a clicked pixel plus suggested tolerances for it."""
    h, w = frame_bgr.shape[:2]
    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    patch = frame_bgr[y0:y1, x0:x1].reshape(-1, 3)
    hsv = cv2.cvtColor(patch.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float)
    centre = hsv[(min(y, h - 1) - y0) * (x1 - x0) + (min(x, w - 1) - x0)]
    # keep only pixels like the clicked one, so eyes/shadows/background in the patch don't loosen the range
    dh = np.abs(((hsv[:, 0] - centre[0]) + 90) % 180 - 90)    # circular hue distance
    keep = (dh <= 10) & (np.abs(hsv[:, 1] - centre[1]) < 70) & (np.abs(hsv[:, 2] - centre[2]) < 70)
    if keep.sum() >= 3:
        patch, hsv, dh = patch[keep], hsv[keep], dh[keep]
    mean = patch.mean(axis=0)
    hue_tol = int(min(45, max(8, np.percentile(dh, 90) * 2 + 6)))
    sat_min = int(max(5, np.percentile(hsv[:, 1], 10) / 2.55 - 12))
    val_min = int(max(5, np.percentile(hsv[:, 2], 10) / 2.55 - 12))
    return bgr_to_hex(mean), hue_tol, sat_min, val_min
