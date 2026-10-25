# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds the real control panel off-screen and checks every control explains itself."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox,  # noqa: E402
                             QLineEdit, QListWidget)

from colorassist import config, ui  # noqa: E402
from colorassist.help_text import HELP, TIPS  # noqa: E402
from colorassist.panel import PAGES, Panel  # noqa: E402


@pytest.fixture(scope="module")
def panel(tmp_path_factory):
    app = QApplication.instance() or QApplication([])
    ui.apply_theme(app, "dark", 12)
    p = Panel(config.default_config(), str(tmp_path_factory.mktemp("cfg") / "c.json"))
    yield p
    p.close()


def test_every_control_has_a_tooltip(panel):
    kinds = (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QListWidget)
    missing = []
    for w in panel.findChildren(QAbstractButton) + panel.findChildren(QAbstractSlider) + \
            panel.findChildren(QAbstractSpinBox) + panel.findChildren(QComboBox) + \
            panel.findChildren(QLineEdit) + panel.findChildren(QListWidget):
        if not isinstance(w, kinds) or w.objectName() in ("nav", "qt_spinbox_lineedit"):
            continue
        if type(w).__name__ in ("QScrollBar",) or w.parent() is None:
            continue
        if isinstance(w, QLineEdit) and isinstance(w.parent(), (QAbstractSpinBox, QComboBox)):
            continue
        if not w.toolTip().strip():
            missing.append("%s %r" % (type(w).__name__, getattr(w, "text", lambda: "")()))
    assert not missing, missing


def test_no_removed_features_and_pages(panel):
    assert "High contrast" not in PAGES and "Magnifier" not in PAGES
    assert not hasattr(config.Profile(), "contrast") and not hasattr(config.Profile(), "magnifier")
    assert panel.stack.count() == len(PAGES)


def test_help_sections_and_images(panel):
    here = os.path.join(os.path.dirname(__file__), "..", "colorassist", "assets", "help")
    for key, title, image, html in HELP:
        assert key in panel._help_sections
        if image:
            assert os.path.exists(os.path.join(here, image)), image
    panel.show_help("watch")
    assert panel.stack.currentIndex() == PAGES.index("Help")


def test_watch_choice_is_generic(panel):
    labels = [lab for _, lab in config.CHOICES[("CaptureCfg", "source")]]
    assert not any("Remote Play" in lab for lab in labels)
    assert config.CaptureCfg().window_title == "" and config.CaptureCfg().source == "monitor"
    panel._window_chosen  # exists
    panel.cfg.capture.source = "region"
    panel._update_watch_rows()
    assert panel.region_btn.isEnabled() and not panel.title_edit.isEnabled()


def test_tip_texts_present():
    for key, (text, tiptext) in TIPS.items():
        assert tiptext.strip(), key


def test_add_target_starts_off_and_asks_for_colour(panel):
    asked = []
    panel.pickColourRequested.connect(lambda: asked.append(True))
    n = len(panel.cfg.profile.targets)
    panel._add_target()
    t = panel.cfg.profile.targets[-1]
    assert len(panel.cfg.profile.targets) == n + 1 and not t.enabled and asked
    panel.apply_picked_colour(("#123456", 12, 30, 30))
    assert t.enabled and t.color == "#123456"


def test_fps_goes_to_120(panel):
    assert panel.fps_slider.slider.maximum() == 120
    panel.fps_slider.setValue(120)
    panel.fps_slider._from_spin(120)
    assert panel.cfg.capture.fps == 120


def test_licence_shown_and_files_present(panel):
    import hashlib
    root = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(root, "LICENSE"), "rb") as fh:
        text = fh.read().replace(b"\r\n", b"\n")          # Windows checkouts use CRLF line endings
        assert hashlib.sha256(text).hexdigest() == \
            "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"   # official GPL-3.0 text
    assert os.path.exists(os.path.join(root, "THIRD_PARTY_NOTICES.md"))
    assert "GPL v3" in panel.licence_label.text() and "EQQX0" in panel.licence_label.text()


def test_ai_device_choice_on_entities_page(panel):
    combo = panel.device_combo
    assert [combo.itemData(i) for i in range(combo.count())] == ["auto", "tensorrt", "cuda", "directml", "cpu"]
    assert combo.toolTip() and panel.fp16_switch.toolTip()
    combo.setCurrentIndex(combo.findData("cuda"))
    assert panel.cfg.ai.device == "cuda"
    panel.fp16_switch.setChecked(False)
    assert panel.cfg.ai.tensorrt_fp16 is False
    combo.setCurrentIndex(combo.findData("auto"))
    panel.fp16_switch.setChecked(True)
