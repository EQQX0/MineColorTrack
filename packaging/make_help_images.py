# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Renders the pictures for the in-app Help page into colorassist/assets/help/.

Run from the repository root after UI changes:  python packaging/make_help_images.py
Needs the test requirements (pillow) because it reuses the synthetic game scene from tests/scene.py.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests")]

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from colorassist import config, engine, ui, vision  # noqa: E402
from colorassist.panel import Panel  # noqa: E402
from colorassist.view import AssistView  # noqa: E402
from scene import CREEPERS, make_scene  # noqa: E402
import fake_model  # noqa: E402  (tests/fake_model.py, needs the onnx package)
import tempfile  # noqa: E402

OUT = os.path.join(ROOT, "colorassist", "assets", "help")
YELLOW = QColor("#FFE600")


def settle(app, n=5):
    for _ in range(n):
        app.processEvents()


def annotate(pixmap, panel, widgets):
    """Yellow frame and numbered badge on each widget, in order."""
    img = pixmap.toImage()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = QFont()
    f.setPointSize(13)
    f.setBold(True)
    p.setFont(f)
    for i, w in enumerate(widgets, start=1):
        tl = w.mapTo(panel, QPoint(0, 0))
        r = QRectF(tl.x() - 4, tl.y() - 4, w.width() + 8, w.height() + 8)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0), 6))
        p.drawRoundedRect(r, 10, 10)
        p.setPen(QPen(YELLOW, 3))
        p.drawRoundedRect(r, 10, 10)
        c = QPointF(r.left() + 2, r.top() + 2)
        p.setPen(QPen(QColor(0, 0, 0), 3))
        p.setBrush(YELLOW)
        p.drawEllipse(c, 15, 15)
        p.setPen(QColor(0, 0, 0))
        p.drawText(QRectF(c.x() - 15, c.y() - 15, 30, 30), Qt.AlignmentFlag.AlignCenter, str(i))
    p.end()
    return img


def to_qimage(bgr):
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    return QImage(rgb.data, rgb.shape[1], rgb.shape[0], 3 * rgb.shape[1], QImage.Format.Format_RGB888).copy()


def render_view(cfg, frame, mirror, size):
    eng = engine.Engine(cfg)
    eng.want_frame = True
    res = None
    for _ in range(3):                       # let tracking settle
        res = eng.process(frame, (0, 0, frame.shape[1], frame.shape[0]))
    view = AssistView(cfg, mirror=True)      # mirror mode draws the picture under the outlines
    view.resize(*size)
    view.set_result(res)
    return view.grab().toImage()


def caption(p, x, y, text, size=13, colour="#FFFFFF"):
    f = QFont()
    f.setPointSize(size)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(colour))
    p.drawText(QPointF(x, y), text)


def sheet(width, height):
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor("#14161B"))
    return img


def example_config(full=True):
    """A profile like one a person would build, for the pictures only (the app itself starts empty)."""
    cfg = config.default_config()
    targets = cfg.profile.targets
    targets.append(config.Target(name="Creeper", color="#50C84B", outline_color="#FF00FF", hue_tol=10,
                                 sat_min=45, val_min=55))
    if full:
        targets.append(config.Target(name="Zombie shirt", color="#00A8A8", outline_color="#FF6A00", hue_tol=10,
                                     sat_min=55, val_min=35))
        targets.append(config.Target(name="Spider eyes", color="#E01010", outline_color="#00FFFF", hue_tol=10,
                                     sat_min=60, val_min=45, min_area=6))
    return cfg


def main():
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    ui.apply_theme(app, "dark", 12)
    scene = cv2.resize(make_scene(), (960, 540), interpolation=cv2.INTER_NEAREST)
    cfg = example_config()
    cfg.capture.source = "window"
    cfg.capture.window_title, cfg.capture.window_exe = "Minecraft", "Minecraft.Windows.exe"

    panel = Panel(cfg, r"C:\Users\you\AppData\Roaming\MineColorTrack\config.json")
    panel.resize(1100, 760)
    panel.show()
    settle(app)

    # 1. Home, running
    panel.set_running(True)
    eng = engine.Engine(cfg)
    res = eng.process(scene, (0, 0, 960, 540))
    res.fps = 30
    panel.show_result(res)
    panel.go("Home")
    settle(app)
    annotate(panel.grab(), panel, panel.anchors["home"]).save(os.path.join(OUT, "help_home.png"))

    # 2. Watch, with example windows in the list
    panel.go("Watch")
    wb = panel.window_box
    wb.blockSignals(True)
    panel.monitor_box.blockSignals(True)
    wb.clear()
    for text, data in (("Minecraft  (Minecraft.Windows.exe)", ("Minecraft", "Minecraft.Windows.exe")),
                       ("PS Remote Play  (RemotePlay.exe)", ("PS Remote Play", "RemotePlay.exe")),
                       ("Xbox  (XboxPcApp.exe)", ("Xbox", "XboxPcApp.exe")),
                       ("OBS 30  (obs64.exe)", ("OBS 30", "obs64.exe"))):
        wb.addItem(text, data)
    wb.setCurrentIndex(0)
    panel.monitor_box.clear()
    panel.monitor_box.addItems(["Monitor 1: 2560x1440 at (0, 0)", "Monitor 2: 1920x1080 at (2560, 0)"])
    panel.refresh_all()
    settle(app)
    annotate(panel.grab(), panel, panel.anchors["watch"]).save(os.path.join(OUT, "help_watch.png"))

    # 3. Targets with a live preview
    panel.go("Targets")
    panel.target_list.setCurrentRow(0)
    hsv = cv2.cvtColor(scene, cv2.COLOR_BGR2HSV)
    mask = vision.target_mask(hsv, cfg.profile.targets[0])
    pm = QPixmap.fromImage(to_qimage(cv2.cvtColor(cv2.resize(mask, (384, 216)), cv2.COLOR_GRAY2BGR)))
    panel.preview_label.setPixmap(pm)
    settle(app)
    scroll = panel.stack.currentWidget()
    scroll.verticalScrollBar().setValue(0)
    panel.resize(1100, 1180)
    settle(app)
    annotate(panel.grab(), panel, panel.anchors["targets"]).save(os.path.join(OUT, "help_targets.png"))
    panel.resize(1100, 760)

    # 4. Tuning: picture plus three masks
    t = cfg.profile.targets[0]
    variants = [("Too loose: grass and leaves match", config.Target(color=t.color, hue_tol=40, sat_min=15, val_min=20)),
                ("Good: only creepers", t),
                ("Too tight: creepers break up", config.Target(color=t.color, hue_tol=6, sat_min=52, val_min=70))]
    tw, th = 400, 225
    img = sheet(2 * tw + 60, 2 * th + 110)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cells = [("The game picture", to_qimage(cv2.resize(scene, (tw, th))))]
    for text, tg in variants:
        m = vision.target_mask(hsv, tg)
        cells.append((text, to_qimage(cv2.cvtColor(cv2.resize(m, (tw, th), interpolation=cv2.INTER_AREA),
                                                   cv2.COLOR_GRAY2BGR))))
    for i, (text, q) in enumerate(cells):
        x, y = 20 + (i % 2) * (tw + 20), 40 + (i // 2) * (th + 50)
        caption(p, x, y - 10, text, 12, "#4ADE80" if text.startswith("Good") else "#FFFFFF")
        p.drawImage(QRectF(x, y, tw, th), q)
    p.end()
    img.save(os.path.join(OUT, "help_tuning.png"))

    # 5. Outline styles
    crop = scene[150:420, 260:760]
    tiles = []
    for style, marker, labels, held in (("box", "arrow", False, False), ("corners", "dot", False, False),
                                        ("ellipse", "none", True, False)):
        c2 = example_config(full=False)
        o = c2.profile.outline
        o.style, o.marker, o.labels = style, marker, labels
        o.thickness = 5
        tiles.append(("Style: %s%s" % ({"box": "box", "corners": "corner brackets", "ellipse": "ellipse"}[style],
                                        {"arrow": ", arrow", "dot": ", dot", "none": ", names on"}[marker]),
                      render_view(c2, crop, True, (500, 270))))
    img = sheet(3 * 340 + 40, 250)
    p = QPainter(img)
    for i, (text, q) in enumerate(tiles):
        x = 10 + i * 350
        caption(p, x, 26, text, 12)
        p.drawImage(QRectF(x, 40, 340, 184), q)
    p.end()
    img.save(os.path.join(OUT, "help_outline.png"))

    # 6. Overlay vs mirror
    c3 = example_config(full=False)
    c3.display.crosshair = True
    over = render_view(c3, scene, False, (480, 270))
    mirror = render_view(c3, scene, True, (480, 300))
    img = sheet(1040, 380)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    caption(p, 20, 30, "Overlay: drawn on top of the game window", 12)
    p.drawImage(QRectF(20, 45, 480, 270), over)
    caption(p, 540, 30, "Mirror window: a separate copy, e.g. on monitor 2", 12)
    p.setPen(QPen(QColor("#363B47"), 2))
    p.setBrush(QColor("#272B34"))
    p.drawRoundedRect(QRectF(540, 45, 480, 330), 8, 8)
    caption(p, 552, 66, "MineColorTrack - mirror", 10, "#A1A7B3")
    p.drawImage(QRectF(540, 75, 480, 300), mirror)
    p.end()
    img.save(os.path.join(OUT, "help_display.png"))

    # 7. Entities page with a (stand-in) model that knows pig, villager and player
    tmp = tempfile.mkdtemp()
    model = fake_model.build(os.path.join(tmp, "my_minecraft_model.onnx"),
                             names="{0: 'pig', 1: 'villager', 2: 'player'}")
    det = cfg.profile.detection
    det.model_path, det.enabled = model, True
    det.entities = [config.Entity("pig", True, "#FFE600"), config.Entity("villager", True, "#00E5FF"),
                    config.Entity("player", True, "#FF3DFF")]
    cfg.ai.dataset_dir = r"C:\Users\you\Documents\MineColorTrack dataset"
    panel.refresh_all()
    panel._refresh_ai("GPU")
    panel.go("Entities")
    panel.resize(1100, 1000)
    settle(app)
    annotate(panel.grab(), panel, panel.anchors["entities"]).save(os.path.join(OUT, "help_entities.png"))
    panel.resize(1100, 760)

    # 8. Labelling tool with a few labelled screenshots
    from colorassist.labeler import Labeler
    root = os.path.join(tmp, "dataset")
    lab = Labeler(root, lambda: (None, None))
    for n in ("creeper", "pig", "player"):
        lab.ds.add_class(n)
    H, W = scene.shape[:2]
    sx, sy = W / 640.0, H / 360.0
    for i in range(6):
        stem = lab.ds.add_image(scene)
        if i == 4:
            lab.ds.save_boxes(stem, [])
        elif i < 4:
            boxes = [(0, (x + w / 2) * sx / W, (y + h / 2) * sy / H, w * sx / W, h * sy / H) for x, y, w, h in CREEPERS]
            boxes.append((1, (470 + 21) * sx / W, (182 + 9) * sy / H, 46 * sx / W, 20 * sy / H))
            lab.ds.save_boxes(stem, boxes)
    lab.resize(1450, 860)
    lab.show()
    lab.reload()
    lab.image_list.setCurrentRow(0)
    lab.class_list.setCurrentRow(0)
    lab.canvas.selected = 0
    settle(app, 8)
    annotate(lab.grab(), lab, lab.anchors).save(os.path.join(OUT, "help_labeling.png"))
    lab.close()

    panel.close()
    print("help images written to", OUT)


if __name__ == "__main__":
    main()
