# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end check of the AI pipeline: label -> export zip -> the Colab notebook's own code -> ONNX -> Detector.

Slow (trains a small model on the CPU) and needs `ultralytics`, so it only runs when MCT_E2E=1:
    MCT_E2E=1 python -m pytest tests/test_training_e2e.py -s
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytestmark = pytest.mark.skipif(not os.environ.get("MCT_E2E"), reason="set MCT_E2E=1 to run the slow training test")

from colorassist.dataset import Dataset  # noqa: E402
from colorassist.detector import Detector  # noqa: E402

NOTEBOOK = os.path.join(os.path.dirname(__file__), "..", "colorassist", "assets", "train_minecolortrack.ipynb")


def sprite(kind, s, rng):
    """A blocky creeper (4x8 cells) or pig (6x4 cells) of cell size s, with slight colour noise."""
    if kind == "creeper":
        h, w, base = 8, 4, (75, 200, 80)
        img = np.zeros((h * s, w * s, 3), np.uint8)
        for r in range(h):
            for c in range(w):
                img[r * s:(r + 1) * s, c * s:(c + 1) * s] = np.clip(np.array(base) + rng.integers(-15, 15, 3), 0, 255)
        for (c, r) in [(0, 1), (3, 1), (1, 2), (2, 2), (1, 3), (2, 3)]:
            img[r * s:(r + 1) * s, c * s:(c + 1) * s] = (30, 40, 30)
    else:
        h, w, base = 4, 6, (160, 160, 240)
        img = np.zeros((h * s, w * s, 3), np.uint8)
        for r in range(h):
            for c in range(w):
                img[r * s:(r + 1) * s, c * s:(c + 1) * s] = np.clip(np.array(base) + rng.integers(-12, 12, 3), 0, 255)
        img[s:2 * s, 4 * s:5 * s] = (40, 40, 60)
    return img


def scene(rng, n_objects):
    """Random blocky landscape with creepers and pigs; returns image and YOLO boxes."""
    H, W = 320, 480
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (235, 190, 130)                                     # sky (BGR)
    ground = rng.integers(170, 230)
    for x in range(0, W, 20):
        g = ground + rng.integers(-2, 3) * 20
        img[g:g + 20, x:x + 20] = np.clip(np.array((80, 180, 140)) + rng.integers(-20, 20, 3), 0, 255)  # grass
        img[g + 20:, x:x + 20] = np.clip(np.array((67, 96, 134)) + rng.integers(-15, 15, 3), 0, 255)    # dirt
    if rng.random() < 0.6:                                        # green leaves: the classic false alarm
        lx, ly = rng.integers(0, W - 100), rng.integers(10, 80)
        img[ly:ly + 60, lx:lx + 100] = np.clip(np.array((42, 95, 47)) + rng.integers(-10, 10, 3), 0, 255)
    boxes = []
    for _ in range(n_objects):
        kind = "creeper" if rng.random() < 0.5 else "pig"
        spr = sprite(kind, int(rng.integers(3, 9)), rng)
        sh, sw = spr.shape[:2]
        x, y = int(rng.integers(0, W - sw)), int(rng.integers(20, H - sh))
        img[y:y + sh, x:x + sw] = spr
        boxes.append((0 if kind == "creeper" else 1, (x + sw / 2) / W, (y + sh / 2) / H, sw / W, sh / H))
    return img, boxes


def run_notebook(zip_path, workdir, epochs):
    with open(NOTEBOOK, encoding="utf-8") as fh:
        nb = json.load(fh)
    env = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(line for line in cell["source"] if not line.rstrip().endswith("# colab-only"))
        if "MODEL =" in src:                     # settings cell: same names, values for a quick CPU run
            src += '\nEPOCHS = %d\nIMAGE_SIZE = 320\nDATA_DIR = %r\nZIP_PATH = %r\n' % (
                epochs, os.path.join(workdir, "mct_dataset"), zip_path)
        exec(compile(src, "notebook", "exec"), env)
    return env["FINAL"]


def test_label_export_train_detect(tmp_path):
    rng = np.random.default_rng(7)
    ds = Dataset(str(tmp_path / "dataset"))
    ds.add_class("creeper")
    ds.add_class("pig")
    for i in range(70):
        img, boxes = scene(rng, int(rng.integers(0, 4)))      # some pictures have nothing: backgrounds
        stem = ds.add_image(img)
        ds.save_boxes(stem, boxes)
    st = ds.stats()
    assert st["labelled"] == 70 and st["backgrounds"] > 0
    summary = ds.export_zip(str(tmp_path / "export.zip"), notebook=NOTEBOOK)
    assert summary["classes"] == ["creeper", "pig"]

    os.chdir(tmp_path)
    onnx_path = run_notebook(str(tmp_path / "export.zip"), str(tmp_path), epochs=int(os.environ.get("MCT_EPOCHS", 25)))
    det = Detector(onnx_path, prefer_gpu=False)
    assert det.names == ["creeper", "pig"]

    found = total = 0
    for _ in range(10):
        img, boxes = scene(rng, 2)
        dets = det.detect(img, conf=0.25)
        total += len(boxes)
        for c, cx, cy, w, h in boxes:
            gx, gy = cx * img.shape[1], cy * img.shape[0]
            if any(d.cls == c and abs(d.x + d.w / 2 - gx) < max(12, w * img.shape[1] / 2) and
                   abs(d.y + d.h / 2 - gy) < max(12, h * img.shape[0] / 2) for d in dets):
                found += 1
    print("found %d of %d objects" % (found, total))
    assert found >= total * 0.6
