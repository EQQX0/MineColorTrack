# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic blocky Minecraft-like frame for tests (BGR numpy array)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, B = 640, 360, 20


def make_scene(seed=3):
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(120 + 60 * t), int(170 + 50 * t), int(235 + 10 * t)))

    def block(x, y, c, s=B, jit=10):
        c = tuple(int(np.clip(v + rng.integers(-jit, jit), 0, 255)) for v in c)
        d.rectangle([x, y, x + s - 1, y + s - 1], fill=c)
        d.rectangle([x, y, x + s - 1, y + s - 1], outline=tuple(max(0, v - 25) for v in c))

    heights = [200, 200, 190, 190, 180, 180, 180, 190, 200, 200, 210, 210, 200, 190, 190, 200,
               200, 210, 220, 220, 210, 200, 200, 190, 190, 190, 200, 210, 210, 200, 200, 200]
    for i, h in enumerate(heights):
        block(i * B, h, (141, 182, 80))
        for y in range(h + B, H, B):
            block(i * B, y, (134, 96, 67))

    def tree(x, base):
        for k in range(4):
            block(x, base - B * (k + 1), (102, 81, 51))
        for dx in (-2, -1, 0, 1, 2):
            for dy in (4, 5, 6):
                block(x + dx * B, base - B * dy, (47, 95, 42))

    tree(3 * B, 190)
    tree(26 * B, 190)

    def creeper(x, feet, s):
        for r in range(8):
            for c in range(4):
                block(x + c * s, feet - (r + 1) * s, (80, 200, 75), s, jit=14)
        for (c, r) in [(0, 6), (3, 6), (1, 5), (2, 5), (1, 4), (2, 4)]:
            d.rectangle([x + c * s, feet - (r + 1) * s, x + c * s + s - 1, feet - r * s - 1], fill=(30, 40, 30))

    def pig(x, feet, s):
        for r in range(3):
            for c in range(6):
                block(x + c * s, feet - (r + 1) * s, (240, 160, 160), s)

    creeper(372, 180, 6)
    creeper(150, 190, 3)
    pig(470, 200, 6)
    fog = Image.new("RGB", (W, H), (190, 205, 220))
    img = Image.blend(img, fog, 0.18).filter(ImageFilter.GaussianBlur(0.6))
    return np.asarray(img)[:, :, ::-1].copy()


# where the two creepers are, as (x, y, w, h)
CREEPERS = [(372, 132, 24, 48), (150, 166, 12, 24)]
