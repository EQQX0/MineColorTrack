# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""The circle or square zone in the middle of the watched picture."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path[:0] = [os.path.join(os.path.dirname(__file__), ".."), os.path.dirname(__file__)]

from colorassist import config, engine, vision  # noqa: E402
from scene import make_scene  # noqa: E402


def found(shape, size, tmp_path):
    cfg = config.AppConfig()
    cfg.profile.targets = [config.Target(name="Creeper", color="#50C84B", hue_tol=10, sat_min=45, val_min=55)]
    cfg.capture.focus_shape, cfg.capture.focus_size = shape, size
    frame = make_scene()
    h, w = frame.shape[:2]
    res = engine.Engine(cfg, str(tmp_path)).process(frame, (0, 0, w, h))
    return [t for t in res.tracks if not t[4]]


def test_geometry():
    assert vision.focus_contains("off", 10, 640, 360, 0, 0)
    assert vision.focus_contains("circle", 50, 640, 360, 320, 180)
    assert not vision.focus_contains("circle", 50, 640, 360, 320 + 100, 180 + 100)   # radius 90, corner of the square
    assert vision.focus_contains("square", 50, 640, 360, 320 + 85, 180 + 85)          # half side 90
    assert not vision.focus_contains("square", 50, 640, 360, 320 + 95, 180)


def test_zone_limits_what_is_found(tmp_path):
    everything = found("off", 50, tmp_path)
    assert len(everything) >= 2                                   # the scene has two creepers
    assert found("square", 100, tmp_path) == everything or len(found("square", 100, tmp_path)) == len(everything)
    assert found("circle", 5, tmp_path) == []                     # a tiny zone in the middle sees nothing
    # a bigger zone never finds fewer than a smaller one
    sizes = [len(found("circle", s, tmp_path)) for s in (5, 25, 50, 75, 100)]
    assert sizes == sorted(sizes)
