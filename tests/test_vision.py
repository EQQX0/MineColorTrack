import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from colorassist import config, vision  # noqa: E402
from scene import CREEPERS, make_scene  # noqa: E402


def creeper_target():
    return config.default_profiles()["Minecraft: creepers"].targets[0]


def test_detects_both_creepers_and_nothing_else():
    frame = make_scene()
    blobs, _, _ = vision.detect(frame, [creeper_target()], config.TrackingCfg(), 1.0)
    assert len(blobs) == 2
    for (x, y, w, h) in CREEPERS:
        assert any(abs(b.x - x) <= 3 and abs(b.y - y) <= 3 and abs(b.w - w) <= 4 and abs(b.h - h) <= 4
                   for b in blobs), (x, y, blobs)


def test_detects_at_half_resolution():
    blobs, small, mask = vision.detect(make_scene(), [creeper_target()], config.TrackingCfg(), 0.5)
    assert len(blobs) == 2
    assert small.shape[:2] == (180, 320) and mask.shape == (180, 320)


def test_disabled_target_and_min_area():
    t = creeper_target()
    t.enabled = False
    assert vision.detect(make_scene(), [t], config.TrackingCfg(), 1.0)[0] == []
    t.enabled, t.min_area = True, 500          # far creeper is ~240 px, near one ~1000 px
    blobs = vision.detect(make_scene(), [t], config.TrackingCfg(), 1.0)[0]
    assert len(blobs) == 1 and blobs[0].x > 300


def test_hue_wraparound_red():
    img = np.zeros((50, 50, 3), np.uint8)
    img[10:20, 10:20] = (0, 0, 230)            # pure red, hue 0
    img[30:40, 30:40] = (40, 0, 230)           # red slightly toward magenta, hue ~175
    t = config.Target(color="#E01010", hue_tol=20, sat_min=50, val_min=40, min_area=10)
    blobs = vision.detect(img, [t], config.TrackingCfg(merge_distance=2), 1.0)[0]
    assert len(blobs) == 2


def test_tracker_smooths_and_holds():
    tr = vision.Tracker()
    b = vision.Blob(0, 100, 100, 20, 40, 800)
    tr.update([b], smoothing=50, hold_frames=2)
    moved = vision.Blob(0, 110, 100, 20, 40, 800)
    t = tr.update([moved], smoothing=50, hold_frames=2)[0]
    assert 100 < t.box[0] < 110                 # smoothed between old and new
    assert len(tr.update([], 50, 2)) == 1       # held 1
    assert len(tr.update([], 50, 2)) == 1       # held 2
    assert len(tr.update([], 50, 2)) == 0       # dropped


def test_effects_shapes():
    frame = make_scene()
    t = creeper_target()
    blobs, small, mask = vision.detect(frame, [t], config.TrackingCfg(), 0.5)
    for fill in ("solid", "original"):
        out = vision.high_contrast(small, mask, config.ContrastCfg(fill=fill), 0.5)
        assert out.shape == small.shape
    hc = vision.high_contrast(small, mask, config.ContrastCfg(edges=False, grow=0), 0.5)
    assert (hc[mask > 0] == vision.hex_to_bgr("#FFEB00")).all()
    lens = vision.magnify(frame, 5, 5, 3.0, 240, 50, True)   # near the corner: padded, no crash
    assert lens.shape == (240, 240, 3)


def test_pick_focus_choices():
    tr = vision.Tracker()
    tracks = tr.update([vision.Blob(0, 150, 166, 12, 24, 200), vision.Blob(0, 372, 132, 24, 48, 900)], 0, 0)
    assert vision.pick_focus(tracks, 640, 360, "smallest")[0] == 156
    assert vision.pick_focus(tracks, 640, 360, "largest")[0] == 384
    assert vision.pick_focus(tracks, 640, 360, "nearest-centre")[0] == 384
    assert vision.pick_focus([], 640, 360, "centre") == (320, 180)
    assert vision.pick_focus([], 640, 360, "smallest") is None


def test_patch_stats_suggests_working_tolerances():
    frame = make_scene()
    for x, y in ((384, 140), (378, 160), (153, 180)):     # incl. a click right next to the dark face
        hexcol, hue_tol, sat_min, val_min = vision.patch_stats(frame, x, y)
        t = config.Target(color=hexcol, hue_tol=hue_tol, sat_min=sat_min, val_min=val_min, min_area=40)
        blobs = vision.detect(frame, [t], config.TrackingCfg(), 1.0)[0]
        assert len(blobs) == 2, (x, y, hexcol, hue_tol, sat_min, val_min, blobs)


def test_config_roundtrip_and_bad_values(tmp_path):
    cfg = config.default_config()
    cfg.profile.outline.style = "corners"
    cfg.capture.region = [1, 2, 300, 400]
    p = tmp_path / "c.json"
    config.save(cfg, str(p))
    back = config.load(str(p))
    assert back.profile.outline.style == "corners"
    assert back.capture.region == [1, 2, 300, 400]
    assert len(back.profile.targets) == len(cfg.profile.targets)
    data = json.loads(p.read_text())
    data["capture"]["fps"] = "abc"
    data["display"]["mode"] = "nonsense"
    data["profiles"][cfg.active_profile]["magnifier"]["zoom"] = 4
    p.write_text(json.dumps(data))
    back = config.load(str(p))
    assert back.capture.fps == 30 and back.display.mode == "overlay"
    assert back.profile.magnifier.zoom == 4.0
    p.write_text("{not json")
    assert config.load(str(p)).profiles


def test_hotkey_parsing():
    from colorassist import winplat
    assert winplat.parse_hotkey("Ctrl+Alt+M") == (winplat.MOD_CONTROL | winplat.MOD_ALT, ord("M"))
    assert winplat.parse_hotkey("Shift+F7") == (winplat.MOD_SHIFT, 0x76)
    assert winplat.parse_hotkey("Ctrl+Num5") == (winplat.MOD_CONTROL, 0x65)
    assert winplat.parse_hotkey("Ctrl+") is None
    assert winplat.parse_hotkey("Ctrl+Banana") is None
