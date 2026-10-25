# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Look and feel: colour themes and the custom widgets used by the control panel."""
import os
import tempfile

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPalette, QPen, QPolygonF
from PyQt6.QtWidgets import (QAbstractButton, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QSlider, QSpinBox, QVBoxLayout, QWidget)

THEMES = {
    # Surfaces are separated by a step in tone, not by outlines; `edge` is only drawn in the high-contrast theme.
    "dark": dict(bg="#0D1014", surface="#161A20", surface2="#212630", input="#0D1014", border="#2E3440",
                 edge="transparent", text="#F1F3F6", muted="#9AA2B1", accent="#3DDC84", accent_text="#04200F",
                 danger="#FF5C5C", danger_text="#1A0505"),
    "light": dict(bg="#EEF0F3", surface="#FFFFFF", surface2="#E3E6EB", input="#F6F7F9", border="#C4CAD3",
                  edge="transparent", text="#101318", muted="#4F5663", accent="#12753A", accent_text="#FFFFFF",
                  danger="#C21F1F", danger_text="#FFFFFF"),
    "contrast": dict(bg="#000000", surface="#000000", surface2="#1A1A1A", input="#000000", border="#FFFFFF",
                     edge="#FFFFFF", text="#FFFFFF", muted="#FFE600", accent="#FFE600", accent_text="#000000",
                     danger="#FF4D4D", danger_text="#000000"),
}

CURRENT = dict(THEMES["dark"])


def palette_for(t):
    pal = QPalette()
    c = lambda k: QColor(t[k])
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        pal.setColor(group, QPalette.ColorRole.Window, c("bg"))
        pal.setColor(group, QPalette.ColorRole.WindowText, c("text"))
        pal.setColor(group, QPalette.ColorRole.Base, c("input"))
        pal.setColor(group, QPalette.ColorRole.AlternateBase, c("surface2"))
        pal.setColor(group, QPalette.ColorRole.Text, c("text"))
        pal.setColor(group, QPalette.ColorRole.Button, c("surface2"))
        pal.setColor(group, QPalette.ColorRole.ButtonText, c("text"))
        pal.setColor(group, QPalette.ColorRole.Highlight, c("accent"))
        pal.setColor(group, QPalette.ColorRole.HighlightedText, c("accent_text"))
        pal.setColor(group, QPalette.ColorRole.ToolTipBase, c("surface"))
        pal.setColor(group, QPalette.ColorRole.ToolTipText, c("text"))
        pal.setColor(group, QPalette.ColorRole.PlaceholderText, c("muted"))
        pal.setColor(group, QPalette.ColorRole.Mid, c("border"))
        pal.setColor(group, QPalette.ColorRole.Light, c("surface2"))
        pal.setColor(group, QPalette.ColorRole.Dark, c("border"))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, c("muted"))
    return pal


def stylesheet(t, pt):
    return """
* {{ font-size: {pt}pt; }}
QMainWindow, QDialog, QWidget#page, QWidget#central {{ background: {bg}; }}
QWidget {{ color: {text}; }}
QScrollArea {{ background: transparent; border: none; }}
QFrame#card {{ background: {surface}; border: 1px solid {edge}; border-radius: 20px; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: {h1}pt; font-weight: 800; }}
QLabel#h2 {{ font-size: {h2}pt; font-weight: 700; }}
QLabel#muted {{ color: {muted}; }}
QLabel#brand {{ font-size: {pt}pt; font-weight: 800; color: {text}; padding: 6px 8px 18px 8px; }}
QLabel#preview {{ background: {input}; border: 1px solid {edge}; border-radius: 14px; color: {muted}; }}
QPushButton, QToolButton {{ background: {surface2}; border: 1px solid {edge}; border-radius: 20px; padding: 8px 20px; min-height: 24px; }}
QPushButton:hover, QToolButton:hover {{ background: {border}; border-color: {edge}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {accent}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton#primary {{ background: {accent}; color: {accent_text}; border: 2px solid {accent}; font-weight: 700; }}
QPushButton#primary:hover {{ background: {accent}; border-color: {text}; }}
QPushButton#danger {{ background: {danger}; color: {danger_text}; border: 2px solid {danger}; font-weight: 700; }}
QPushButton#danger:hover {{ background: {danger}; border-color: {text}; }}
QPushButton#primary:focus, QPushButton#danger:focus {{ border: 2px solid {text}; }}
QPushButton#big {{ font-size: {h2}pt; padding: 16px 38px; border-radius: 30px; min-height: 28px; }}
QToolButton::menu-indicator {{ image: none; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {surface2}; border: 2px solid {edge};
    border-radius: 12px; padding: 7px 12px; selection-background-color: {accent}; selection-color: {accent_text}; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ background: {border}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 2px solid {accent}; }}
QComboBox::drop-down {{ border: none; width: 30px; }}
QComboBox QAbstractItemView {{ background: {surface2}; border: 1px solid {edge}; outline: none;
    selection-background-color: {accent}; selection-color: {accent_text}; padding: 6px; }}
QWidget#side {{ background: {surface}; border-right: 1px solid {edge}; }}
QListWidget#nav {{ background: transparent; border: none; padding: 8px 12px; outline: none; }}
QListWidget#nav::item {{ padding: 12px 16px; border-radius: 18px; margin: 3px 0; color: {muted}; }}
QListWidget#nav::item:hover {{ background: {surface2}; color: {text}; }}
QListWidget#nav::item:selected {{ background: {accent}; color: {accent_text}; font-weight: 700; }}
QListWidget#targets {{ background: {surface2}; border: 1px solid {edge}; border-radius: 14px; padding: 6px; outline: none; }}
QListWidget#targets::item {{ padding: 10px; border-radius: 10px; }}
QListWidget#targets::item:selected {{ background: {accent}; color: {accent_text}; }}
QSlider::groove:horizontal {{ height: 8px; background: {surface2}; border-radius: 4px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 4px; }}
QSlider::handle:horizontal {{ background: {text}; width: 22px; height: 22px; margin: -7px 0; border-radius: 11px; }}
QSlider::handle:horizontal:hover {{ background: {accent}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {surface2}; border-radius: 5px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {border}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QToolTip {{ background: {surface2}; color: {text}; border: 1px solid {edge}; padding: 8px; }}
QMenu {{ background: {surface2}; border: 1px solid {edge}; padding: 8px; }}
QMenu::item {{ padding: 8px 24px; border-radius: 10px; }}
QMenu::item:selected {{ background: {accent}; color: {accent_text}; }}
""".format(pt=pt, h1=pt + 14, h2=pt + 4, **t)


def apply_theme(app, name, pt):
    t = THEMES.get(name, THEMES["dark"])
    CURRENT.clear()
    CURRENT.update(t)
    app.setPalette(palette_for(t))
    app.setStyleSheet(stylesheet(t, pt) + "QComboBox::down-arrow { image: url(%s); width: 12px; height: 8px; }"
                      % _arrow_image(t["text"]))
    for w in app.allWidgets():
        if isinstance(w, ToggleSwitch):
            w.update()


def card(title=None, subtitle=None):
    """A rounded panel. Returns (frame, inner vertical layout)."""
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(20, 16, 20, 18)
    lay.setSpacing(12)
    if title:
        t = QLabel(title)
        t.setObjectName("h2")
        lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    return f, lay


def label(text, name=None, wrap=True):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


class ToggleSwitch(QAbstractButton):
    """An on/off switch with a text label; large and keyboard accessible (Space toggles)."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _track(self):
        h = self.fontMetrics().height() + 8
        return QRectF(2, (self.height() - h) / 2, h * 1.9, h)

    def sizeHint(self):
        h = self.fontMetrics().height() + 12
        w = int(h * 1.9) + 14 + (self.fontMetrics().horizontalAdvance(self.text()) if self.text() else 0)
        return QSize(w + 4, h)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tr = self._track()
        on = self.isChecked()
        enabled = self.isEnabled()
        track = QColor(CURRENT["accent"] if on else CURRENT["border"])
        if not enabled:
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen if on or CURRENT["edge"] == "transparent" else QPen(QColor(CURRENT["border"]), 2))
        p.setBrush(track)
        p.drawRoundedRect(tr.adjusted(1, 1, -1, -1), tr.height() / 2 - 1, tr.height() / 2 - 1)
        if self.hasFocus():
            p.setPen(QPen(QColor(CURRENT["text"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(tr.adjusted(-2, -2, 2, 2), tr.height() / 2 + 2, tr.height() / 2 + 2)
        d = tr.height() - 6
        x = tr.right() - d - 3 if on else tr.left() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(CURRENT["accent_text"] if on else CURRENT["text"]))
        p.drawEllipse(QRectF(x, tr.top() + 3, d, d))
        if self.text():
            p.setPen(QColor(CURRENT["text"] if enabled else CURRENT["muted"]))
            p.drawText(QRectF(tr.right() + 12, 0, self.width() - tr.right() - 12, self.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


class SliderField(QWidget):
    """Slider plus an exact-value box, kept in sync."""
    valueChanged = pyqtSignal(float)

    def __init__(self, lo, hi, step=1, decimals=0, suffix=""):
        super().__init__()
        self.k = 10 ** decimals
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(round(lo * self.k)), int(round(hi * self.k)))
        self.slider.setSingleStep(max(1, int(round(step * self.k))))
        self.slider.setPageStep(max(1, int(round(step * self.k * 5))))
        self.spin = QDoubleSpinBox() if decimals else QSpinBox()
        if decimals:
            self.spin.setDecimals(decimals)
        self.spin.setRange(lo, hi)
        self.spin.setSingleStep(step)
        self.spin.setSuffix(suffix)
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.spin.setFixedWidth(self.fontMetrics().horizontalAdvance("00000" + suffix) + 34)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, v):
        val = v / self.k
        self.spin.blockSignals(True)
        self.spin.setValue(val if self.k > 1 else int(val))
        self.spin.blockSignals(False)
        self.valueChanged.emit(val)

    def _from_spin(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * self.k)))
        self.slider.blockSignals(False)
        self.valueChanged.emit(float(v))

    def setValue(self, v):
        for w in (self.slider, self.spin):
            w.blockSignals(True)
        self.slider.setValue(int(round(v * self.k)))
        self.spin.setValue(v if self.k > 1 else int(v))
        for w in (self.slider, self.spin):
            w.blockSignals(False)


class ColourButton(QPushButton):
    def set_colour(self, hexcol):
        fg = readable_text(hexcol)
        self.setText(hexcol)
        self.setStyleSheet("QPushButton { background: %s; color: %s; font-weight: 700; border: 2px solid %s; "
                           "border-radius: 20px; padding: 8px 20px; min-height: 24px; } QPushButton:focus { border: 3px solid %s; }"
                           % (hexcol, fg, CURRENT["border"], CURRENT["text"]))


def readable_text(hexcol):
    """Black or white, whichever reads better on this background colour."""
    c = QColor(hexcol)
    return "#000000" if (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) > 140 else "#FFFFFF"


def _arrow_image(colour):
    """Small down-arrow PNG in the theme's text colour, for combo boxes (QSS needs an image file)."""
    path = os.path.join(tempfile.gettempdir(), "minecolortrack_arrow_%s.png" % colour.lstrip("#"))
    if not os.path.exists(path):
        img = QImage(24, 16, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colour))
        p.drawPolygon(QPolygonF([QPointF(2, 3), QPointF(22, 3), QPointF(12, 14)]))
        p.end()
        img.save(path)
    return path.replace("\\", "/")


def swatch(hexcol, size=18):
    lb = QLabel()
    lb.setFixedSize(size, size)
    lb.setStyleSheet("background: %s; border: 1px solid %s; border-radius: %dpx;"
                     % (hexcol, CURRENT["edge"], size // 2))
    return lb


def clear_layout(lay):
    """Remove and destroy everything in a layout right away (deleteLater alone leaves widgets visible until later)."""
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())
