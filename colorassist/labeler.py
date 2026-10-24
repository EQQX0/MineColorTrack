"""Labelling tool: collect screenshots, draw boxes around entities, and export a zip for training in Colab."""
import os
import shutil
import time

from PyQt6.QtCore import QRectF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QKeySequence, QPainter, QPen, QShortcut
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog, QListWidget,
                             QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QToolButton,
                             QVBoxLayout, QWidget)

from . import APP_NAME
from .dataset import Dataset, read_image
from .engine import PALETTE, to_qimage
from .help_text import TIPS
from .ui import card, label

COLAB_URL = "https://colab.research.google.com/"
NOTEBOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "train_minecolortrack.ipynb")


def tip(key):
    return TIPS[key][1]


def class_colour(i):
    return QColor(PALETTE[i % len(PALETTE)])


class Canvas(QWidget):
    """Shows one screenshot. Drag to draw a box, click a box to select it, right-click a box to delete it."""
    changed = pyqtSignal()
    needClass = pyqtSignal()

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.img = None
        self.size_px = (1, 1)
        self.boxes = []             # [(class, cx, cy, w, h)] normalised
        self.selected = -1
        self.drag_from = self.drag_to = None
        self.setMinimumSize(480, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip(tip("lab.canvas"))

    def set_image(self, frame_bgr, boxes):
        self.img = to_qimage(frame_bgr) if frame_bgr is not None else None
        self.size_px = (frame_bgr.shape[1], frame_bgr.shape[0]) if frame_bgr is not None else (1, 1)
        self.boxes = list(boxes or [])
        self.selected = -1
        self.update()

    def _view(self):
        w, h = self.size_px
        k = min(self.width() / w, self.height() / h)
        return QRectF((self.width() - w * k) / 2, (self.height() - h * k) / 2, w * k, h * k)

    def _to_norm(self, p):
        v = self._view()
        return (min(1.0, max(0.0, (p.x() - v.x()) / v.width())), min(1.0, max(0.0, (p.y() - v.y()) / v.height())))

    def _box_rect(self, b):
        v = self._view()
        _, cx, cy, w, h = b
        return QRectF(v.x() + (cx - w / 2) * v.width(), v.y() + (cy - h / 2) * v.height(), w * v.width(), h * v.height())

    def _hit(self, pos):
        best, area = -1, None
        for i, b in enumerate(self.boxes):
            r = self._box_rect(b)
            if r.contains(pos) and (area is None or r.width() * r.height() < area):
                best, area = i, r.width() * r.height()
        return best

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0B0C0F"))
        if self.img is None:
            p.setPen(QColor("#A1A7B3"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No screenshot selected.\nPress “Capture screenshot” or import pictures.")
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(self._view(), self.img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        names = self.owner.ds.classes
        for i, b in enumerate(self.boxes):
            r = self._box_rect(b)
            col = class_colour(b[0])
            sel = i == self.selected
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(0, 0, 0), 5 if sel else 4))
            p.drawRect(r)
            p.setPen(QPen(col, 3 if sel else 2))
            p.drawRect(r)
            name = names[b[0]] if 0 <= b[0] < len(names) else "?"
            tw = p.fontMetrics().horizontalAdvance(name) + 10
            tag = QRectF(r.left(), r.top() - 20, tw, 20)
            p.fillRect(tag, col)
            p.setPen(QColor("#000000"))
            p.drawText(tag, Qt.AlignmentFlag.AlignCenter, name)
        if self.drag_from and self.drag_to:
            p.setPen(QPen(class_colour(self.owner.current_class()), 2, Qt.PenStyle.DashLine))
            p.drawRect(QRectF(self.drag_from, self.drag_to).normalized())

    def mousePressEvent(self, e):
        if self.img is None:
            return
        hit = self._hit(e.position())
        if e.button() == Qt.MouseButton.RightButton:
            if hit >= 0:
                del self.boxes[hit]
                self.selected = -1
                self.changed.emit()
                self.update()
            return
        if hit >= 0:
            self.selected = hit
            self.update()
            return
        if self.owner.current_class() < 0:
            self.needClass.emit()
            return
        self.selected = -1
        self.drag_from = self.drag_to = e.position()

    def mouseMoveEvent(self, e):
        if self.drag_from is not None:
            self.drag_to = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.drag_from is None:
            return
        a, b = self._to_norm(self.drag_from), self._to_norm(e.position())
        self.drag_from = self.drag_to = None
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        if (x1 - x0) * self.size_px[0] >= 4 and (y1 - y0) * self.size_px[1] >= 4:
            self.boxes.append((self.owner.current_class(), (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0))
            self.selected = len(self.boxes) - 1
            self.changed.emit()
        self.update()

    def delete_selected(self):
        if 0 <= self.selected < len(self.boxes):
            del self.boxes[self.selected]
            self.selected = -1
            self.changed.emit()
            self.update()

    def set_selected_class(self, c):
        if 0 <= self.selected < len(self.boxes):
            _, cx, cy, w, h = self.boxes[self.selected]
            self.boxes[self.selected] = (c, cx, cy, w, h)
            self.changed.emit()
            self.update()
            return True
        return False


class Labeler(QMainWindow):
    datasetChanged = pyqtSignal(str)     # new dataset folder chosen

    def __init__(self, root, grab_frame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("%s - labelling tool" % APP_NAME)
        self.grab_frame = grab_frame
        self.ds = Dataset(root)
        self.current = None
        central = QWidget()
        central.setObjectName("central")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 12)

        bar = QHBoxLayout()
        self.capture_btn = self._button("Capture screenshot", "lab.capture", self.capture, "primary")
        bar.addWidget(self.capture_btn)
        imp = QToolButton()
        imp.setText("Import...")
        imp.setToolTip(tip("lab.import"))
        imp.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(imp)
        menu.addAction("Pictures (to label here)...", self.import_pictures)
        menu.addAction("Labelled dataset, zip (YOLO format)...", self.import_zip)
        menu.addAction("Labelled dataset, folder (YOLO format)...", self.import_folder)
        imp.setMenu(menu)
        self.import_btn = imp
        bar.addWidget(imp)
        bar.addStretch(1)
        self.export_btn = self._button("Export for training...", "lab.export", self.export, "primary")
        bar.addWidget(self.export_btn)
        bar.addWidget(self._button("Open Google Colab", "lab.colab",
                                   lambda: QDesktopServices.openUrl(QUrl(COLAB_URL))))
        bar.addWidget(self._button("Dataset folder...", "lab.folder", self.folder_menu))
        outer.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        # left: pictures
        left, ll = card("Screenshots")
        self.image_list = QListWidget()
        self.image_list.setObjectName("targets")
        self.image_list.setToolTip(tip("lab.images"))
        self.image_list.currentRowChanged.connect(self._image_selected)
        ll.addWidget(self.image_list, 1)
        self.delete_img_btn = self._button("Delete screenshot", "lab.delete_image", self.delete_image)
        ll.addWidget(self.delete_img_btn)
        split.addWidget(left)
        # centre: canvas
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        self.canvas = Canvas(self)
        self.canvas.changed.connect(self._boxes_changed)
        self.canvas.needClass.connect(self.add_class)
        ml.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.bg_btn = self._button("Nothing here (background)", "lab.background", self.mark_background)
        row.addWidget(self.bg_btn)
        self.clear_btn = self._button("Remove all boxes", "lab.clear", self.clear_boxes)
        row.addWidget(self.clear_btn)
        row.addStretch(1)
        self.prev_btn = self._button("◀ Previous", "lab.prev", lambda: self.step(-1))
        self.next_btn = self._button("Next ▶", "lab.next", lambda: self.step(1))
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)
        ml.addLayout(row)
        ml.addWidget(label("Drag on the picture to draw a box around each thing. Click a box to select it, "
                           "Delete or right-click removes it, keys 1 to 9 pick the class (or change the selected "
                           "box), Left/Right arrows change picture, B marks “nothing here”.", "muted"))
        split.addWidget(mid)
        # right: classes and advice
        right, rl = card("Classes")
        self.class_list = QListWidget()
        self.class_list.setObjectName("targets")
        self.class_list.setToolTip(tip("lab.classes"))
        self.class_list.itemClicked.connect(self._class_clicked)
        rl.addWidget(self.class_list, 1)
        cb = QHBoxLayout()
        self.add_class_btn = self._button("Add", "lab.add_class", self.add_class)
        self.rename_class_btn = self._button("Rename", "lab.rename_class", self.rename_class)
        self.delete_class_btn = self._button("Delete", "lab.delete_class", self.delete_class)
        for b in (self.add_class_btn, self.rename_class_btn, self.delete_class_btn):
            cb.addWidget(b)
        rl.addLayout(cb)
        self.stats_label = label("", "muted")
        rl.addWidget(self.stats_label)
        self.advice_label = label("")
        self.advice_label.setToolTip(tip("lab.advice"))
        rl.addWidget(self.advice_label)
        right.setMinimumWidth(320)
        split.addWidget(right)
        split.setSizes([220, 880, 350])
        outer.addWidget(split, 1)
        self.setCentralWidget(central)
        self.resize(1450, 860)
        self.anchors = [self.capture_btn, self.image_list, self.canvas, self.class_list, self.advice_label,
                        self.export_btn]

        for key, fn in ((Qt.Key.Key_Delete, self.canvas.delete_selected),
                        (Qt.Key.Key_Backspace, self.canvas.delete_selected),
                        (Qt.Key.Key_Left, lambda: self.step(-1)), (Qt.Key.Key_Right, lambda: self.step(1)),
                        (Qt.Key.Key_B, self.mark_background)):
            QShortcut(QKeySequence(key), self, activated=fn)
        for n in range(1, 10):
            QShortcut(QKeySequence(str(n)), self, activated=lambda n=n: self.choose_class(n - 1))
        self.reload()

    # ---------- helpers ----------
    @staticmethod
    def _button(text, key, slot, name=None):
        b = QPushButton(text)
        b.setToolTip(tip(key))
        b.clicked.connect(slot)
        if name:
            b.setObjectName(name)
        return b

    def current_class(self):
        row = self.class_list.currentRow()
        return row if 0 <= row < len(self.ds.classes) else (-1 if not self.ds.classes else 0)

    def _item_text(self, stem, number):
        boxes = self.ds.load_boxes(stem)
        if boxes is None:
            return "%d.  • not labelled" % number
        if not boxes:
            return "%d.  ○ nothing here" % number
        return "%d.  ✓ %d box%s" % (number, len(boxes), "" if len(boxes) == 1 else "es")

    def reload(self, select=None):
        stems = self.ds.images()
        keep = select or self.current
        self.image_list.blockSignals(True)
        self.image_list.clear()
        for i, s in enumerate(stems):
            item = QListWidgetItem(self._item_text(s, i + 1))
            item.setData(Qt.ItemDataRole.UserRole, s)
            item.setToolTip(s)
            self.image_list.addItem(item)
        self.image_list.blockSignals(False)
        row = stems.index(keep) if keep in stems else (len(stems) - 1 if stems else -1)
        self.image_list.setCurrentRow(row)
        self._image_selected(row)
        self.reload_classes()

    def reload_classes(self):
        st = self.ds.stats()
        row = self.class_list.currentRow()
        self.class_list.clear()
        for i, name in enumerate(self.ds.classes):
            item = QListWidgetItem("%d  %s  · %d" % (i + 1, name, st["boxes"][i]))
            item.setToolTip("%s: %d boxes in %d screenshots. Key %d selects it." % (
                name, st["boxes"][i], st["images_with"][i], i + 1))
            item.setForeground(class_colour(i))
            self.class_list.addItem(item)
        if self.ds.classes:
            self.class_list.setCurrentRow(min(max(row, 0), len(self.ds.classes) - 1))
        self.stats_label.setText("%d screenshots: %d labelled, %d with nothing in them."
                                 % (st["images"], st["labelled"], st["backgrounds"]))
        self.stats_label.setToolTip("Dataset folder: %s" % self.ds.root)
        tips = self.ds.advice(st)
        self.advice_label.setText("<b>Tips</b><ul>%s</ul>" % "".join("<li>%s</li>" % t for t in tips)
                                  if tips else "<b>Looks ready to export and train.</b>")
        has_class = bool(self.ds.classes)
        self.rename_class_btn.setEnabled(has_class)
        self.delete_class_btn.setEnabled(has_class)

    def _image_selected(self, row):
        item = self.image_list.item(row) if row >= 0 else None
        if item is None:
            self.current = None
            self.canvas.set_image(None, [])
            return
        self.current = item.data(Qt.ItemDataRole.UserRole)
        path = self.ds.image_path(self.current)
        img = read_image(path) if path else None
        self.canvas.set_image(img, self.ds.load_boxes(self.current) or [])
        self.canvas.setFocus()

    def _refresh_item(self):
        item = self.image_list.currentItem()
        if item and self.current:
            item.setText(self._item_text(self.current, self.image_list.currentRow() + 1))
        self.reload_classes()

    def _boxes_changed(self):
        if self.current:
            self.ds.save_boxes(self.current, self.canvas.boxes)
            self._refresh_item()

    # ---------- actions ----------
    def step(self, d):
        n = self.image_list.count()
        if n:
            self.image_list.setCurrentRow(max(0, min(n - 1, self.image_list.currentRow() + d)))

    def capture(self):
        frame, msg = self.grab_frame()
        if frame is None:
            QMessageBox.information(self, APP_NAME, msg or "Nothing to capture. Choose what to watch on the Watch page.")
            return
        stem = self.ds.add_image(frame)
        self.reload(select=stem)

    def add_captured(self, stem):
        """A screenshot was saved by the hotkey while this window is open."""
        self.reload(select=stem)

    def mark_background(self):
        if self.current:
            self.canvas.boxes = []
            self.canvas.selected = -1
            self.canvas.update()
            self.ds.save_boxes(self.current, [])
            self._refresh_item()
            self.step(1)

    def clear_boxes(self):
        if self.current:
            self.ds.unlabel(self.current)
            self.canvas.set_image(read_image(self.ds.image_path(self.current)), [])
            self._refresh_item()

    def delete_image(self):
        if self.current and QMessageBox.question(
                self, APP_NAME, "Delete this screenshot and its boxes?") == QMessageBox.StandardButton.Yes:
            row = self.image_list.currentRow()
            self.ds.delete_image(self.current)
            self.current = None
            stems = self.ds.images()
            self.reload(select=stems[min(row, len(stems) - 1)] if stems else None)

    def choose_class(self, i):
        if 0 <= i < len(self.ds.classes):
            self.class_list.setCurrentRow(i)
            self.canvas.set_selected_class(i)

    def _class_clicked(self, item):
        self.canvas.set_selected_class(self.class_list.row(item))

    def add_class(self):
        name, ok = QInputDialog.getText(self, "New class", "What is it called? (for example pig, villager, player)")
        if ok and name.strip():
            try:
                i = self.ds.add_class(name)
            except ValueError as exc:
                QMessageBox.warning(self, APP_NAME, str(exc))
                return
            self.reload_classes()
            self.class_list.setCurrentRow(i)

    def rename_class(self):
        i = self.class_list.currentRow()
        if 0 <= i < len(self.ds.classes):
            name, ok = QInputDialog.getText(self, "Rename class", "New name:", text=self.ds.classes[i])
            if ok:
                try:
                    self.ds.rename_class(i, name)
                except ValueError as exc:
                    QMessageBox.warning(self, APP_NAME, str(exc))
                self.reload_classes()
                self.canvas.update()

    def delete_class(self):
        i = self.class_list.currentRow()
        if 0 <= i < len(self.ds.classes) and QMessageBox.question(
                self, APP_NAME, "Delete the class “%s” and all its boxes?" % self.ds.classes[i]) \
                == QMessageBox.StandardButton.Yes:
            self.ds.delete_class(i)
            self.reload()

    def _busy(self, fn, *args):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return fn(*args)
        finally:
            QApplication.restoreOverrideCursor()

    def import_pictures(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Import pictures", "", "Pictures (*.png *.jpg *.jpeg *.bmp *.webp)")
        last = None
        for f in files:
            try:
                last = self.ds.add_image_file(f)
            except ValueError as exc:
                QMessageBox.warning(self, APP_NAME, str(exc))
        if last:
            self.reload(select=last)

    def _import(self, source):
        try:
            added, new = self._busy(self.ds.import_yolo, source)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, "Could not import: %s" % exc)
            return
        self.reload()
        QMessageBox.information(self, APP_NAME, "Imported %d labelled pictures.%s" % (
            added, ("\nNew classes: %s" % ", ".join(new)) if new else ""))

    def import_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import labelled dataset", "", "Zip files (*.zip)")
        if path:
            self._import(path)

    def import_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Import labelled dataset folder")
        if path:
            self._import(path)

    def export(self):
        default = os.path.join(os.path.dirname(self.ds.root.rstrip("\\/")) or os.path.expanduser("~"),
                               "MineColorTrack-training-%s.zip" % time.strftime("%Y%m%d-%H%M"))
        path, _ = QFileDialog.getSaveFileName(self, "Export for training", default, "Zip files (*.zip)")
        if not path:
            return
        try:
            info = self._busy(self.ds.export_zip, path, 0.15, 1, NOTEBOOK)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, "Could not export: %s" % exc)
            return
        nb_copy = os.path.join(os.path.dirname(path), os.path.basename(NOTEBOOK))
        try:
            shutil.copyfile(NOTEBOOK, nb_copy)
        except OSError:
            nb_copy = NOTEBOOK
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText("Exported %d pictures for training and %d for checking (classes: %s).\n\n"
                    "Next:\n1. Open Google Colab and choose File > Upload notebook: %s\n"
                    "2. Runtime > Change runtime type > T4 GPU.\n3. Runtime > Run all, and upload:\n   %s\n"
                    "4. Load the downloaded minecolortrack_model.onnx on the Entities page."
                    % (info["train"], info["val"], ", ".join(info["classes"]), nb_copy, path))
        open_colab = box.addButton("Open Google Colab", QMessageBox.ButtonRole.AcceptRole)
        open_folder = box.addButton("Show the files", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_colab:
            QDesktopServices.openUrl(QUrl(COLAB_URL))
        elif box.clickedButton() is open_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def folder_menu(self):
        menu = QMenu(self)
        menu.addAction("Open the dataset folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.ds.root)))
        menu.addAction("Use a different folder...", self.change_folder)
        menu.exec(self.cursor().pos())

    def change_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a dataset folder", self.ds.root)
        if path:
            self.ds = Dataset(path)
            self.current = None
            self.reload()
            self.datasetChanged.emit(path)
