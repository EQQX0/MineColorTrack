# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""The live detections file."""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path[:0] = [os.path.join(os.path.dirname(__file__), ".."), os.path.dirname(__file__)]

from colorassist import config, engine  # noqa: E402
from scene import make_scene  # noqa: E402


def test_engine_writes_latest_and_history(tmp_path):
    cfg = config.AppConfig()
    cfg.profile.targets = [config.Target(name="Creeper", color="#50C84B", hue_tol=10, sat_min=45, val_min=55)]
    cfg.export.enabled = True
    cfg.export.path = str(tmp_path / "out" / "detections.json")
    cfg.export.history = True
    eng = engine.Engine(cfg, str(tmp_path / "trt"))
    frame = make_scene()
    h, w = frame.shape[:2]
    for _ in range(3):
        res = eng.process(frame, (100, 50, w, h))
        eng._export(res)
    eng._close_export()                                   # waits until everything is written

    rec = json.loads(open(cfg.export.path, encoding="utf-8").read())
    assert rec["frame"] == 3 and rec["frame_size"] == [w, h] and rec["capture_rect"] == [100, 50, w, h]
    assert rec["detections"], "the scene has creepers"
    d = rec["detections"][0]
    assert d["name"] == "Creeper" and d["kind"] == "colour"
    assert abs(d["screen_x"] - (100 + d["x"])) < 0.2 and abs(d["screen_y"] - (50 + d["y"])) < 0.2
    lines = open(str(tmp_path / "out" / "detections.jsonl"), encoding="utf-8").read().splitlines()
    assert [json.loads(l)["frame"] for l in lines] == [1, 2, 3]


def test_export_off_writes_nothing(tmp_path):
    cfg = config.AppConfig()
    eng = engine.Engine(cfg, str(tmp_path / "trt"))
    eng._export(eng.process(make_scene(), (0, 0, 640, 360)))
    assert eng._writer is None and not list(tmp_path.glob("*.json"))
