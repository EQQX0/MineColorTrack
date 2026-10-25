# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Full-screen region selector and a click-to-pick colour dialog."""
from PyQt6.QtCore import QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from . import vision, winplat
from .engine import to_qimage


class RegionPicker(QWidget):
    """Shows a frozen screenshot of one monitor; drag a box around the game picture."""
    picked = pyqtSignal(object)   # (x, y, w, h) physical pixels, or None if cancelled

    def __init__(self, shot_bgr, mon_rect):
        super().__init__()
        self.setWindowTitle("MineColorTrack - select region")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.img = to_qimage(shot_bgr)
        self.mon = mon_rect
        self.a = self.b = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def open(self):
        self.show()
        winplat.place_window(self, self.mon)
        self.activateWindow()
        self.setFocus()

    def _to_phys(self, pt):
        mx, my, mw, mh = self.mon
        return (mx + pt.x() * mw / max(1, self.width()), my + pt.y() * mh / max(1, self.height()))

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(QRectF(self.rect()), self.img)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRect(0, 20, self.width(), 40), Qt.AlignmentFlag.AlignHCenter,
                   "Drag around the game picture. Enter or release to confirm, Esc to cancel.")
        if self.a and self.b:
            r = QRectF(self.a, self.b).normalized()
            src = QRectF(r.x() * self.img.width() / self.width(), r.y() * self.img.height() / self.height(),
                         r.width() * self.img.width() / self.width(), r.height() * self.img.height() / self.height())
            p.drawImage(r, self.img, src)
            p.setPen(QPen(QColor("#FFEB00"), 3))
            p.drawRect(r)

    def mousePressEvent(self, e):
        self.a = self.b = e.position()
        self.update()

    def mouseMoveEvent(self, e):
        if self.a is not None:
            self.b = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        self.b = e.position()
        self._finish()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.picked.emit(None)
            self.close()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish()

    def _finish(self):
        if not (self.a and self.b):
            return
        x0, y0 = self._to_phys(self.a)
        x1, y1 = self._to_phys(self.b)
        x, y = int(min(x0, x1)), int(min(y0, y1))
        w, h = int(abs(x1 - x0)), int(abs(y1 - y0))
        if w < 32 or h < 32:
            return
        self.picked.emit((x, y, w, h))
        self.close()


class _FrameCanvas(QWidget):
    hovered = pyqtSignal(int, int)
    clicked = pyqtSignal(int, int)

    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self.img = to_qimage(frame)
        self.mouse = None
        h, w = frame.shape[:2]
        k = min(1.0, 1100 / w, 650 / h)
        self.setFixedSize(int(w * k), int(h * k))
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _frame_xy(self, pos):
        h, w = self.frame.shape[:2]
        return (min(w - 1, max(0, int(pos.x() * w / self.width()))),
                min(h - 1, max(0, int(pos.y() * h / self.height()))))

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(QRectF(self.rect()), self.img)
        if self.mouse is None:
            return
        # loupe: 8x zoom of the pixels under the cursor
        fx, fy = self._frame_xy(self.mouse)
        r, z = 6, 10
        src = QRectF(fx - r, fy - r, 2 * r + 1, 2 * r + 1)
        size = (2 * r + 1) * z
        lx = self.mouse.x() + 20 if self.mouse.x() + 20 + size < self.width() else self.mouse.x() - 20 - size
        ly = min(max(0, self.mouse.y() - size / 2), self.height() - size)
        dst = QRectF(lx, ly, size, size)
        p.drawImage(dst, self.img, src)
        p.setPen(QPen(QColor(0, 0, 0), 3))
        p.drawRect(dst)
        p.setPen(QPen(QColor("#FFFFFF"), 1))
        p.drawRect(QRectF(lx + r * z, ly + r * z, z, z))

    def mouseMoveEvent(self, e):
        self.mouse = e.position()
        self.hovered.emit(*self._frame_xy(self.mouse))
        self.update()

    def mousePressEvent(self, e):
        self.clicked.emit(*self._frame_xy(e.position()))


class ColourPicker(QDialog):
    """Click on the thing you want highlighted. Gives a colour and suggested tolerances."""

    def __init__(self, frame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MineColorTrack - pick a colour")
        self.frame = frame
        self.result_values = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Hover to inspect, click on the mob/thing to track. Pick its most typical colour, "
                             "not a shadow or highlight."))
        canvas = _FrameCanvas(frame)
        lay.addWidget(canvas)
        self.info = QLabel(" ")
        self.info.setMinimumHeight(28)
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        canvas.hovered.connect(self._hover)
        canvas.clicked.connect(self._click)

    def _hover(self, x, y):
        b, g, r = (int(v) for v in self.frame[y, x])
        hexcol = vision.bgr_to_hex((b, g, r))
        self.info.setText("Pixel (%d, %d): %s" % (x, y, hexcol))
        text = "#000000" if (r * 299 + g * 587 + b * 114) / 1000 > 128 else "#FFFFFF"
        self.info.setStyleSheet("background:%s; color:%s; padding:4px; font-weight:bold;" % (hexcol, text))

    def _click(self, x, y):
        self.result_values = vision.patch_stats(self.frame, x, y)
        self.accept()
