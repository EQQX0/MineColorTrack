# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""The window that draws the assist: a click-through overlay or a separate mirror window."""
import time

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from . import winplat


class AssistView(QWidget):
    def __init__(self, cfg, mirror):
        super().__init__()
        self.cfg = cfg
        self.mirror = mirror
        self.res = None
        self.message = ""
        self.test_colour = None   # solid fill used by the capture self-test
        self.paint_ms = 0.0       # average time to draw one frame
        if mirror:
            self.setWindowTitle("MineColorTrack - mirror")
            flags = Qt.WindowType.Window
            if cfg.display.mirror_on_top:
                flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.resize(960, 540)
        else:
            self.setWindowTitle("MineColorTrack overlay")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                                | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput
                                | Qt.WindowType.NoDropShadowWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def protect_from_capture(self):
        """True if Windows will leave this window out of screenshots (overlay mode needs it)."""
        return winplat.exclude_from_capture(int(self.winId()))

    def set_result(self, res):
        self.res = res
        self.update()

    def _view_rect(self, fw, fh):
        if not self.mirror:
            return QRectF(0, 0, self.width(), self.height())
        k = min(self.width() / fw, self.height() / fh)
        w, h = fw * k, fh * k
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, _):
        t = time.perf_counter()
        p = QPainter(self)
        self._paint(p)
        p.end()
        ms = (time.perf_counter() - t) * 1000.0
        self.paint_ms = 0.9 * self.paint_ms + 0.1 * ms if self.paint_ms else ms

    def _paint(self, p):
        if self.test_colour is not None:
            p.fillRect(self.rect(), self.test_colour)
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.mirror:
            p.fillRect(self.rect(), QColor(0, 0, 0))
        res = self.res
        if res is None:
            if self.mirror:
                self._text(p, QPointF(20, 40), self.message or "Press Start in the control panel.", QColor("#FFFFFF"))
            return
        fw, fh = res.frame_size
        vr = self._view_rect(fw, fh)
        sx, sy = vr.width() / fw, vr.height() / fh
        prof = self.cfg.profile

        if self.mirror and res.frame_img is not None:
            p.drawImage(vr, res.frame_img)

        if prof.outline.enabled:
            self._outlines(p, res, vr, sx, sy, prof.outline)
        if self.cfg.display.crosshair:
            c = vr.center()
            col = QColor(self.cfg.display.crosshair_color)
            for w, colr in ((6, QColor(0, 0, 0)), (2, col)):
                p.setPen(QPen(colr, w))
                p.drawLine(QPointF(c.x() - 14, c.y()), QPointF(c.x() + 14, c.y()))
                p.drawLine(QPointF(c.x(), c.y() - 14), QPointF(c.x(), c.y() + 14))
        if self.mirror and self.message:
            self._text(p, QPointF(20, 40), self.message, QColor("#FFFFFF"))

    def _text(self, p, pos, text, colour, size=14):
        path = QPainterPath()
        f = QFont()
        f.setPointSize(size)
        f.setBold(True)
        path.addText(pos, f, text)
        p.setPen(QPen(QColor(0, 0, 0), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.fillPath(path, colour)

    def _outlines(self, p, res, vr, sx, sy, cfg):
        if cfg.blink and int(time.monotonic() * 3) % 2:
            return
        th, pad = max(1, cfg.thickness), cfg.padding
        for (x, y, w, h, held, name, hexcol) in res.tracks:
            if held and not cfg.show_held:
                continue
            r = QRectF(vr.x() + x * sx - pad, vr.y() + y * sy - pad, w * sx + 2 * pad, h * sy + 2 * pad)
            col = QColor(hexcol if cfg.use_target_color else cfg.color)
            if held:
                col.setAlpha(150)
            layers = ([(th + 4, QColor(0, 0, 0, 200 if not held else 110))] if cfg.black_border else []) + [(th, col)]
            for width, c in layers:
                pen = QPen(c, width)
                pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                if held:
                    pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                if cfg.style == "ellipse":
                    p.drawEllipse(r)
                elif cfg.style == "corners":
                    k = max(8.0, min(r.width(), r.height()) * 0.3)
                    for cx, cy, dx, dy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                                           (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
                        p.drawLine(QPointF(cx, cy), QPointF(cx + dx * k, cy))
                        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * k))
                else:
                    p.drawRect(r)
            top = r.top() - 6
            if cfg.marker != "none":
                s = 8 + th * 2
                p.setPen(QPen(QColor(0, 0, 0), 2))
                p.setBrush(col)
                if cfg.marker == "arrow":
                    cx = r.center().x()
                    p.drawPolygon(QPolygonF([QPointF(cx, top), QPointF(cx - s, top - s * 1.4),
                                             QPointF(cx + s, top - s * 1.4)]))
                    top -= s * 1.4 + 4
                else:
                    p.drawEllipse(QPointF(r.center().x(), top - s / 2), s / 2, s / 2)
                    top -= s + 4
            if cfg.labels:
                self._text(p, QPointF(r.left(), top - 2), name, col, 12)
