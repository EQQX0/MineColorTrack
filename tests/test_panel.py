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
