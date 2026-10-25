# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Draws the app icon (colorassist/assets/icon.png and icon.ico). Run once; the outputs are committed."""
import os

from PIL import Image, ImageDraw

S = 512
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "colorassist", "assets")
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([16, 16, S - 16, S - 16], radius=110, fill=(20, 22, 27, 255))

# creeper-like face made of blocks (6 x 6)
greens = [(74, 222, 128), (62, 196, 110), (88, 230, 140), (54, 178, 98)]
n, cell = 6, 34
x0 = y0 = 256 - n * cell // 2
for r in range(n):
    for c in range(n):
        col = greens[(r * 3 + c * 5) % 4]
        d.rectangle([x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell - 3, y0 + (r + 1) * cell - 3], fill=col)
dark = (16, 28, 20)
for (c, r) in [(1, 1), (4, 1), (2, 3), (3, 3), (1, 4), (2, 4), (3, 4), (4, 4), (1, 5), (4, 5)]:
    d.rectangle([x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell - 3, y0 + (r + 1) * cell - 3], fill=dark)

# magenta tracking brackets
m, k, w = (255, 0, 255), 70, 22
L, T, R, B = 96, 96, S - 96, S - 96
for (cx, cy, dx, dy) in ((L, T, 1, 1), (R, T, -1, 1), (L, B, 1, -1), (R, B, -1, -1)):
    d.line([(cx, cy), (cx + dx * k, cy)], fill=m, width=w)
    d.line([(cx, cy), (cx, cy + dy * k)], fill=m, width=w)
    d.rectangle([cx - w // 2, cy - w // 2, cx + w // 2, cy + w // 2], fill=m)

img.resize((256, 256), Image.LANCZOS).save(os.path.join(root, "icon.png"))
img.save(os.path.join(root, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written to", os.path.abspath(root))
