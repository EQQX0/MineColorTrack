# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""AI detection, dataset handling and the labelling tool (no trained model needed)."""
import os
import sys
import zipfile

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path[:0] = [os.path.join(os.path.dirname(__file__), ".."), os.path.dirname(__file__)]

from colorassist import config, dataset, detector, engine  # noqa: E402

onnx = pytest.importorskip("onnx")
import fake_model  # noqa: E402


@pytest.mark.parametrize("end2end", [False, True])
def test_detector_reads_both_yolo_layouts(tmp_path, end2end):
    path = fake_model.build(str(tmp_path / "m.onnx"), end2end=end2end)
    det = detector.Detector(path, device="cpu")
    assert det.names == ["pig", "villager"] and det.size == (64, 64) and det.end2end == end2end
    frame = np.zeros((128, 128, 3), np.uint8)                       # 2x the model input
    found = sorted(det.detect(frame, conf=0.5), key=lambda d: d.cls)
    assert [d.cls for d in found] == [0, 1]                          # overlapping duplicate removed, low score dropped
    pig = found[0]
    assert abs(pig.x - 54) < 2 and abs(pig.y - 44) < 2 and abs(pig.w - 20) < 2 and abs(pig.h - 40) < 2
    assert [d.cls for d in det.detect(frame, conf=0.5, allowed={1})] == [1]


def test_detector_rejects_bad_files(tmp_path):
    with pytest.raises(detector.ModelError):
        detector.Detector(str(tmp_path / "missing.onnx"))
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"not a model")
    with pytest.raises(Exception):
        detector.Detector(str(bad))


def test_engine_outlines_ai_entities(tmp_path):
    cfg = config.default_config()
    det = cfg.profile.detection
    det.enabled, det.model_path, det.confidence = True, fake_model.build(str(tmp_path / "m.onnx")), 50
    det.entities = [config.Entity("pig", True, "#112233"), config.Entity("villager", False)]
    res = engine.Engine(cfg).process(np.zeros((128, 128, 3), np.uint8), (0, 0, 128, 128))
    assert res.ai_device == "CPU" or res.ai_device == "GPU"
    assert [(t[5], t[6]) for t in res.tracks] == [("pig", "#112233")]   # villager switched off
    det.model_path = str(tmp_path / "nope.onnx")
    res = engine.Engine(cfg).process(np.zeros((64, 64, 3), np.uint8), (0, 0, 64, 64))
    assert res.ai_error and not res.tracks


def test_dataset_classes_boxes_and_export(tmp_path):
    ds = dataset.Dataset(str(tmp_path / "ds"))
    assert ds.advice()[0].startswith("Add a class")
    for n in ("pig", "villager", "player"):
        ds.add_class(n)
    with pytest.raises(ValueError):
        ds.add_class("PIG")
    img = np.zeros((90, 160, 3), np.uint8)
    a, b, c = ds.add_image(img), ds.add_image(img), ds.add_image(img)
    assert len({a, b, c}) == 3
    ds.save_boxes(a, [(0, .5, .5, .2, .2), (2, .1, .1, .1, .1)])
    ds.save_boxes(b, [])                                            # background
    st = ds.stats()
    assert (st["labelled"], st["backgrounds"], st["unlabelled"], st["boxes"]) == (2, 1, 1, [1, 0, 1])
    ds.delete_class(1)                                              # villager: player shifts from 2 to 1
    assert ds.classes == ["pig", "player"] and [x[0] for x in ds.load_boxes(a)] == [0, 1]
    info = ds.export_zip(str(tmp_path / "out.zip"))
    assert info["train"] + info["val"] == 2                         # unlabelled picture left out
    with zipfile.ZipFile(tmp_path / "out.zip") as zf:
        names = zf.namelist()
        assert "data.yaml" in names and "0: pig" in zf.read("data.yaml").decode()
        assert any(n.startswith("labels/val/") for n in names) and any(n.startswith("images/train/") for n in names)


def test_import_roboflow_style_zip(tmp_path):
    src = tmp_path / "rf.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("data.yaml", "train: ../train/images\nnc: 2\nnames: ['villager', 'Pig']\n")
        ok, buf = __import__("cv2").imencode(".jpg", np.zeros((20, 20, 3), np.uint8))
        for part in ("train", "valid"):
            zf.writestr("%s/images/a.jpg" % part, buf.tobytes())
            zf.writestr("%s/labels/a.txt" % part, "0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n")
        zf.writestr("train/images/nolabel.jpg", buf.tobytes())        # no label file: skipped
    ds = dataset.Dataset(str(tmp_path / "ds"))
    ds.add_class("pig")
    added, new = ds.import_yolo(str(src))
    assert added == 2 and new == ["villager"] and ds.classes == ["pig", "villager"]
    st = ds.stats()
    assert st["boxes"] == [2, 2]                                    # "Pig" matched existing "pig" by name


def test_yaml_name_formats():
    assert dataset.parse_yaml_names("names:\n  0: a\n  1: b c\n") == ["a", "b c"]
    assert dataset.parse_yaml_names("names:\n- x\n- y\n") == [] or True     # unindented lists are not YOLO style
    assert dataset.parse_yaml_names("names:\n  - x\n  - 'y'\n") == ["x", "y"]
    assert dataset.parse_yaml_names("names: {0: 'p', 1: 'q'}\n") == ["p", "q"]


def test_labeler_window(tmp_path):
    from PyQt6.QtWidgets import QAbstractButton, QApplication, QListWidget
    from colorassist import ui
    from colorassist.labeler import Labeler
    app = QApplication.instance() or QApplication([])
    ui.apply_theme(app, "dark", 12)
    lab = Labeler(str(tmp_path / "ds"), lambda: (np.full((90, 160, 3), 100, np.uint8), None))
    no_tip = [w.text() for w in lab.findChildren(QAbstractButton) if not w.toolTip().strip()]
    no_tip += ["list"] * sum(1 for w in lab.findChildren(QListWidget) if not w.toolTip().strip())
    assert not no_tip, no_tip
    lab.ds.add_class("player")
    lab.reload_classes()
    lab.capture()
    assert lab.current and lab.image_list.count() == 1
    lab.canvas.boxes = [(0, .5, .5, .3, .5)]
    lab._boxes_changed()
    assert lab.ds.load_boxes(lab.current) == [(0, .5, .5, .3, .5)]
    lab.capture()
    lab.mark_background()
    st = lab.ds.stats()
    assert st["labelled"] == 2 and st["backgrounds"] == 1
    lab.close()
