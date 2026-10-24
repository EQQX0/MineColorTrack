"""Control panel: every option, profiles, colour/region picking, hotkeys."""
import copy

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
                             QMessageBox, QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout,
                             QWidget)

from .config import CHOICES, Target, default_profiles
from . import engine


class Panel(QMainWindow):
    startStop = pyqtSignal()
    settingsChanged = pyqtSignal()
    displayModeChanged = pyqtSignal()
    profileChanged = pyqtSignal()
    previewChanged = pyqtSignal(object)
    pickColourRequested = pyqtSignal()
    pickRegionRequested = pyqtSignal()
    hotkeysApply = pyqtSignal()
    saveRequested = pyqtSignal()
    fontChanged = pyqtSignal()
    quitRequested = pyqtSignal()

    def __init__(self, cfg, config_path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self._refreshers = []          # re-read widgets from config (profile switch)
        self._target_refreshers = []   # re-read target editor (target selection)
        self._target_widgets = []
        self.setWindowTitle("ColorAssist - control panel")

        root = QWidget()
        lay = QVBoxLayout(root)
        top = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setMinimumWidth(140)
        self.start_btn.clicked.connect(self.startStop.emit)
        top.addWidget(self.start_btn)
        self.status = QLabel("Stopped.")
        self.status.setWordWrap(True)
        top.addWidget(self.status, 1)
        lay.addLayout(top)

        prow = QHBoxLayout()
        prow.addWidget(QLabel("Profile:"))
        self.profile_box = QComboBox()
        self.profile_box.currentTextChanged.connect(self._profile_selected)
        prow.addWidget(self.profile_box, 1)
        for text, fn in (("Duplicate", self._dup_profile), ("Rename", self._rename_profile),
                         ("Delete", self._delete_profile), ("Restore presets", self._restore_presets),
                         ("Save settings", self.saveRequested.emit)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            prow.addWidget(b)
        lay.addLayout(prow)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scroll(self._tab_capture()), "Capture && display")
        self.tabs.addTab(self._scroll(self._tab_targets()), "Targets")
        self.tabs.addTab(self._scroll(self._tab_outline()), "Outline")
        self.tabs.addTab(self._scroll(self._tab_contrast()), "High contrast")
        self.tabs.addTab(self._scroll(self._tab_magnifier()), "Magnifier")
        self.tabs.addTab(self._scroll(self._tab_tracking()), "Tracking")
        self.tabs.addTab(self._scroll(self._tab_hotkeys()), "Hotkeys")
        self.tabs.currentChanged.connect(lambda _: self._emit_preview())
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.resize(820, 700)
        self._reload_profiles()

    # ---------- generic bound widgets ----------
    @staticmethod
    def _scroll(w):
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setWidget(w)
        return s

    def _set(self, getter, attr, value, after=None):
        obj = getter()
        if obj is None:
            return
        setattr(obj, attr, value)
        if after:
            after()
        self.settingsChanged.emit()

    def _bind(self, kind, getter, attr, refreshers, text="", lo=0, hi=100, step=1, suffix="",
              choices_key=None, after=None, tip=""):
        if kind == "check":
            w = QCheckBox(text)
            w.toggled.connect(lambda v: self._set(getter, attr, bool(v), after))
            load = lambda o: w.setChecked(bool(getattr(o, attr)))
        elif kind == "int":
            w = QSpinBox()
            w.setRange(lo, hi)
            w.setSingleStep(step)
            w.setSuffix(suffix)
            w.valueChanged.connect(lambda v: self._set(getter, attr, int(v), after))
            load = lambda o: w.setValue(int(getattr(o, attr)))
        elif kind == "float":
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setSingleStep(step)
            w.setDecimals(1)
            w.setSuffix(suffix)
            w.valueChanged.connect(lambda v: self._set(getter, attr, float(v), after))
            load = lambda o: w.setValue(float(getattr(o, attr)))
        elif kind == "choice":
            w = QComboBox()
            opts = CHOICES[choices_key]
            for value, label in opts:
                w.addItem(label, value)
            w.currentIndexChanged.connect(lambda i: self._set(getter, attr, w.itemData(i), after))
            load = lambda o: w.setCurrentIndex(max(0, w.findData(getattr(o, attr))))
        elif kind == "text":
            w = QLineEdit()
            w.editingFinished.connect(lambda: self._set(getter, attr, w.text().strip(), after))
            load = lambda o: w.setText(str(getattr(o, attr)))
        elif kind == "colour":
            w = QPushButton()
            w.setMinimumWidth(130)

            def choose():
                o = getter()
                if o is None:
                    return
                c = QColorDialog.getColor(QColor(getattr(o, attr)), self, "Choose colour")
                if c.isValid():
                    self._set(getter, attr, c.name().upper(), after)
                    paint(c.name().upper())
            w.clicked.connect(choose)

            def paint(hexcol):
                c = QColor(hexcol)
                fg = "#000000" if c.lightness() > 128 else "#FFFFFF"
                w.setText(hexcol)
                w.setStyleSheet("background:%s; color:%s; font-weight:bold; padding:4px;" % (hexcol, fg))
            load = lambda o: paint(getattr(o, attr))
        else:
            raise ValueError(kind)

        def refresh():
            o = getter()
            w.setEnabled(o is not None)
            if o is None:
                return
            w.blockSignals(True)
            load(o)
            w.blockSignals(False)
        refreshers.append(refresh)
        refresh()
        if tip:
            w.setToolTip(tip)
        return w

    def _form(self, title=None):
        box = QGroupBox(title) if title else QWidget()
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return box, form

    # ---------- tabs ----------
    def _tab_capture(self):
        cap = lambda: self.cfg.capture
        disp = lambda: self.cfg.display
        R = self._refreshers
        page = QWidget()
        v = QVBoxLayout(page)

        box, f = self._form("What to watch")
        f.addRow("Source:", self._bind("choice", cap, "source", R, choices_key=("CaptureCfg", "source")))
        f.addRow("Window title contains:", self._bind(
            "text", cap, "window_title", R, tip="Used when Source is the PS Remote Play window."))
        self.monitor_box = QComboBox()
        try:
            names = engine.monitor_names()
        except Exception:
            names = ["1"]
        self.monitor_box.addItems(names)
        self.monitor_box.setCurrentIndex(max(0, min(len(names) - 1, self.cfg.capture.monitor - 1)))
        self.monitor_box.currentIndexChanged.connect(lambda i: self._set(cap, "monitor", i + 1))
        f.addRow("Monitor:", self.monitor_box)
        rrow = QHBoxLayout()
        self.region_label = QLabel()
        rrow.addWidget(self.region_label, 1)
        rb = QPushButton("Select region on screen...")
        rb.clicked.connect(self.pickRegionRequested.emit)
        rrow.addWidget(rb)
        f.addRow("Custom region:", rrow)
        self.show_region()
        f.addRow("Frames per second:", self._bind("int", cap, "fps", R, lo=5, hi=60))
        f.addRow("Processing resolution:", self._bind(
            "int", cap, "scale", R, lo=20, hi=100, step=5, suffix=" %",
            tip="Lower is faster. 100% finds the smallest/farthest targets best."))
        v.addWidget(box)

        box, f = self._form("How to show it")
        f.addRow("Display:", self._bind("choice", disp, "mode", R, choices_key=("DisplayCfg", "mode"),
                                        after=self.displayModeChanged.emit))
        f.addRow("", self._bind("check", disp, "mirror_on_top", R, text="Keep mirror window on top",
                                after=self.displayModeChanged.emit))
        f.addRow("", self._bind("check", disp, "crosshair", R, text="Draw a high-visibility crosshair at the centre"))
        f.addRow("Crosshair colour:", self._bind("colour", disp, "crosshair_color", R))
        v.addWidget(box)

        box, f = self._form("This window")
        f.addRow("Text size:", self._bind("int", disp, "ui_font_pt", R, lo=9, hi=28, suffix=" pt",
                                          after=self.fontChanged.emit))
        f.addRow("", self._bind("check", disp, "start_on_launch", R, text="Start assisting when the program opens"))
        v.addWidget(box)
        v.addStretch(1)
        return page

    def _tab_targets(self):
        page = QWidget()
        h = QHBoxLayout(page)
        left = QVBoxLayout()
        self.target_list = QListWidget()
        self.target_list.currentRowChanged.connect(self._target_selected)
        left.addWidget(self.target_list, 1)
        for text, fn in (("Add", self._add_target), ("Duplicate", self._dup_target), ("Remove", self._remove_target)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            left.addWidget(b)
        h.addLayout(left, 1)

        T = self._target_refreshers
        tg = self._current_target
        right = QVBoxLayout()
        box, f = self._form("Selected target")
        f.addRow("", self._bind("check", tg, "enabled", T, text="Enabled", after=self._refresh_target_names))
        f.addRow("Name:", self._bind("text", tg, "name", T, after=self._refresh_target_names))
        pick = QPushButton("Pick colour from the game...")
        pick.setMinimumHeight(36)
        pick.clicked.connect(self.pickColourRequested.emit)
        self._target_widgets.append(pick)
        f.addRow("", pick)
        f.addRow("Colour:", self._bind("colour", tg, "color", T))
        f.addRow("Hue tolerance:", self._bind("int", tg, "hue_tol", T, lo=1, hi=180, suffix=" °",
                                              tip="How far the shade may drift. Small = only this exact hue."))
        f.addRow("Saturation min:", self._bind("int", tg, "sat_min", T, suffix=" %",
                                               tip="Raise to ignore greyish/washed-out pixels."))
        f.addRow("Saturation max:", self._bind("int", tg, "sat_max", T, suffix=" %"))
        f.addRow("Brightness min:", self._bind("int", tg, "val_min", T, suffix=" %",
                                               tip="Raise to ignore shadows and dark blocks."))
        f.addRow("Brightness max:", self._bind("int", tg, "val_max", T, suffix=" %"))
        f.addRow("Minimum size:", self._bind("int", tg, "min_area", T, lo=1, hi=200000, suffix=" px",
                                             tip="Matches smaller than this are ignored (removes grass/leaf specks)."))
        f.addRow("Maximum size:", self._bind("int", tg, "max_area", T, lo=0, hi=2000000, suffix=" px",
                                             tip="0 = no limit. Use it to ignore big areas like whole fields."))
        f.addRow("Outline colour:", self._bind("colour", tg, "outline_color", T))
        right.addWidget(box)

        pbox = QGroupBox("Live mask preview (white = matched; needs Start)")
        pl = QVBoxLayout(pbox)
        self.preview_check = QCheckBox("Show preview while this tab is open")
        self.preview_check.toggled.connect(lambda _: self._emit_preview())
        pl.addWidget(self.preview_check)
        self.preview_label = QLabel("Preview off.")
        self.preview_label.setMinimumHeight(190)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#202020; color:#CCCCCC;")
        pl.addWidget(self.preview_label)
        right.addWidget(pbox)
        right.addStretch(1)
        h.addLayout(right, 2)
        return page

    def _tab_outline(self):
        o = lambda: self.cfg.profile.outline
        R = self._refreshers
        box, f = self._form()
        f.addRow("", self._bind("check", o, "enabled", R, text="Draw outlines around targets"))
        f.addRow("Style:", self._bind("choice", o, "style", R, choices_key=("OutlineCfg", "style")))
        f.addRow("Line thickness:", self._bind("int", o, "thickness", R, lo=1, hi=24, suffix=" px"))
        f.addRow("Space around target:", self._bind("int", o, "padding", R, lo=0, hi=60, suffix=" px"))
        f.addRow("", self._bind("check", o, "black_border", R, text="Black border behind the line (visible on any background)"))
        f.addRow("", self._bind("check", o, "use_target_color", R, text="Use each target's own outline colour"))
        f.addRow("Colour otherwise:", self._bind("colour", o, "color", R))
        f.addRow("Marker:", self._bind("choice", o, "marker", R, choices_key=("OutlineCfg", "marker")))
        f.addRow("", self._bind("check", o, "labels", R, text="Show target names"))
        f.addRow("", self._bind("check", o, "blink", R, text="Blink outlines"))
        f.addRow("", self._bind("check", o, "show_held", R,
                                text="Keep a dashed outline briefly when a target is lost"))
        return box

    def _tab_contrast(self):
        c = lambda: self.cfg.profile.contrast
        R = self._refreshers
        box, f = self._form()
        f.addRow("", self._bind("check", c, "enabled", R, text="High-contrast view"))
        f.addRow("Dim the rest by:", self._bind("int", c, "dim", R, suffix=" %"))
        f.addRow("", self._bind("check", c, "greyscale", R, text="Turn the rest grey"))
        f.addRow("Targets drawn as:", self._bind("choice", c, "fill", R, choices_key=("ContrastCfg", "fill")))
        f.addRow("Solid colour:", self._bind("colour", c, "fill_color", R))
        f.addRow("Thicken targets by:", self._bind("int", c, "grow", R, lo=0, hi=30, suffix=" px"))
        f.addRow("", self._bind("check", c, "edges", R, text="White edge around targets"))
        note = QLabel("This view covers the game picture with a processed copy, so it is a few frames "
                      "behind the live stream.")
        note.setWordWrap(True)
        f.addRow(note)
        return box

    def _tab_magnifier(self):
        m = lambda: self.cfg.profile.magnifier
        R = self._refreshers
        box, f = self._form()
        f.addRow("", self._bind("check", m, "enabled", R, text="Magnifier lens"))
        f.addRow("Zoom:", self._bind("float", m, "zoom", R, lo=1.5, hi=10.0, step=0.5, suffix=" x"))
        f.addRow("Lens size:", self._bind("int", m, "size", R, lo=100, hi=900, step=10, suffix=" px"))
        f.addRow("Shape:", self._bind("choice", m, "shape", R, choices_key=("MagnifierCfg", "shape")))
        f.addRow("Position:", self._bind("choice", m, "position", R, choices_key=("MagnifierCfg", "position")))
        f.addRow("Look at:", self._bind("choice", m, "source", R, choices_key=("MagnifierCfg", "source")))
        f.addRow("Extra contrast:", self._bind("int", m, "contrast", R, lo=0, hi=200, suffix=" %"))
        f.addRow("", self._bind("check", m, "pixelated", R, text="Sharp pixels (best for Minecraft)"))
        f.addRow("Border colour:", self._bind("colour", m, "border_color", R))
        f.addRow("", self._bind("check", m, "link_line", R, text="Circle the source area and draw a line to the lens"))
        return box

    def _tab_tracking(self):
        t = lambda: self.cfg.profile.tracking
        R = self._refreshers
        box, f = self._form()
        f.addRow("Smoothing:", self._bind("int", t, "smoothing", R, lo=0, hi=95, suffix=" %",
                                          tip="Higher = steadier outlines, but they trail moving mobs more."))
        f.addRow("Hold lost targets for:", self._bind("int", t, "hold_frames", R, lo=0, hi=90, suffix=" frames"))
        f.addRow("Join pieces closer than:", self._bind("int", t, "merge_distance", R, lo=0, hi=80, suffix=" px",
                                                        tip="Joins a creeper's body and legs into one box."))
        f.addRow("Speck filter:", self._bind("int", t, "noise_filter", R, lo=0, hi=6,
                                             tip="0 = off. Higher removes more single-pixel noise."))
        return box

    def _tab_hotkeys(self):
        k = lambda: self.cfg.hotkeys
        R = self._refreshers
        box, f = self._form()
        f.addRow("Start / stop:", self._bind("text", k, "toggle_overlay", R))
        f.addRow("Next profile:", self._bind("text", k, "next_profile", R))
        f.addRow("Outline on/off:", self._bind("text", k, "toggle_outline", R))
        f.addRow("High contrast on/off:", self._bind("text", k, "toggle_contrast", R))
        f.addRow("Magnifier on/off:", self._bind("text", k, "toggle_magnifier", R))
        b = QPushButton("Apply hotkeys")
        b.clicked.connect(self.hotkeysApply.emit)
        f.addRow("", b)
        self.hotkey_status = QLabel()
        self.hotkey_status.setWordWrap(True)
        f.addRow(self.hotkey_status)
        note = QLabel("Format: Ctrl+Alt+M, Shift+F7, Ctrl+Num5 ... They work while the game has focus. "
                      "Leave a box empty to disable that hotkey.")
        note.setWordWrap(True)
        f.addRow(note)
        return box

    # ---------- profiles ----------
    def _reload_profiles(self):
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        self.profile_box.addItems(list(self.cfg.profiles))
        self.cfg.profile  # normalise
        self.profile_box.setCurrentText(self.cfg.active_profile)
        self.profile_box.blockSignals(False)
        self._refresh_all()

    def _refresh_all(self):
        for r in self._refreshers:
            r()
        self._reload_targets()

    def _profile_selected(self, name):
        if name and name in self.cfg.profiles:
            self.cfg.active_profile = name
            self._refresh_all()
            self.profileChanged.emit()

    def select_profile(self, name):
        self.profile_box.setCurrentText(name)

    def _ask_name(self, title, default):
        name, ok = QInputDialog.getText(self, title, "Profile name:", text=default)
        name = name.strip()
        if not ok or not name:
            return None
        if name in self.cfg.profiles:
            QMessageBox.warning(self, "ColorAssist", "A profile with that name already exists.")
            return None
        return name

    def _dup_profile(self):
        name = self._ask_name("Duplicate profile", self.cfg.active_profile + " (copy)")
        if name:
            self.cfg.profiles[name] = copy.deepcopy(self.cfg.profile)
            self.cfg.active_profile = name
            self._reload_profiles()
            self.profileChanged.emit()

    def _rename_profile(self):
        old = self.cfg.active_profile
        name = self._ask_name("Rename profile", old)
        if name:
            self.cfg.profiles = {(name if k == old else k): v for k, v in self.cfg.profiles.items()}
            self.cfg.active_profile = name
            self._reload_profiles()

    def _delete_profile(self):
        if len(self.cfg.profiles) <= 1:
            QMessageBox.information(self, "ColorAssist", "Keep at least one profile.")
            return
        old = self.cfg.active_profile
        if QMessageBox.question(self, "ColorAssist", "Delete profile '%s'?" % old) != QMessageBox.StandardButton.Yes:
            return
        del self.cfg.profiles[old]
        self.cfg.active_profile = next(iter(self.cfg.profiles))
        self._reload_profiles()
        self.profileChanged.emit()

    def _restore_presets(self):
        added = [k for k in default_profiles() if k not in self.cfg.profiles]
        for k, v in default_profiles().items():
            self.cfg.profiles.setdefault(k, v)
        self._reload_profiles()
        self.set_status("Restored presets: %s" % (", ".join(added) if added else "none were missing"))

    # ---------- targets ----------
    def _current_target(self):
        row = self.target_list.currentRow() if hasattr(self, "target_list") else -1
        targets = self.cfg.profile.targets
        return targets[row] if 0 <= row < len(targets) else None

    def _reload_targets(self, select=None):
        row = self.target_list.currentRow() if select is None else select
        self.target_list.blockSignals(True)
        self.target_list.clear()
        for t in self.cfg.profile.targets:
            self.target_list.addItem(("" if t.enabled else "(off) ") + t.name)
        self.target_list.blockSignals(False)
        n = len(self.cfg.profile.targets)
        self.target_list.setCurrentRow(min(max(row, 0), n - 1) if n else -1)
        self._target_selected()

    def _refresh_target_names(self):
        for i, t in enumerate(self.cfg.profile.targets):
            item = self.target_list.item(i)
            if item:
                item.setText(("" if t.enabled else "(off) ") + t.name)

    def _target_selected(self, *_):
        for r in self._target_refreshers:
            r()
        has = self._current_target() is not None
        for w in self._target_widgets:
            w.setEnabled(has)
        self._emit_preview()

    def _add_target(self):
        self.cfg.profile.targets.append(Target(name="Target %d" % (len(self.cfg.profile.targets) + 1)))
        self._reload_targets(select=len(self.cfg.profile.targets) - 1)
        self.settingsChanged.emit()

    def _dup_target(self):
        t = self._current_target()
        if t:
            c = copy.deepcopy(t)
            c.name += " (copy)"
            self.cfg.profile.targets.append(c)
            self._reload_targets(select=len(self.cfg.profile.targets) - 1)
            self.settingsChanged.emit()

    def _remove_target(self):
        row = self.target_list.currentRow()
        if 0 <= row < len(self.cfg.profile.targets):
            del self.cfg.profile.targets[row]
            self._reload_targets(select=row - 1)
            self.settingsChanged.emit()

    def apply_picked_colour(self, values):
        t = self._current_target()
        if t is None:
            self._add_target()
            t = self._current_target()
        t.color, t.hue_tol, t.sat_min, t.val_min = values
        t.sat_max = t.val_max = 100
        self._target_selected()
        self.settingsChanged.emit()
        self.set_status("Picked %s for '%s' (hue +/-%d°, saturation >= %d%%, brightness >= %d%%). "
                        "Check the mask preview and adjust." % (t.color, t.name, t.hue_tol, t.sat_min, t.val_min))

    def _emit_preview(self):
        on = (hasattr(self, "preview_check") and self.preview_check.isChecked()
              and self.tabs.currentIndex() == 1)
        row = self.target_list.currentRow() if on else -1
        self.previewChanged.emit(row if row >= 0 else None)
        if not on and hasattr(self, "preview_label"):
            self.preview_label.clear()
            self.preview_label.setText("Preview off.")

    # ---------- status ----------
    def show_region(self):
        x, y, w, h = self.cfg.capture.region
        self.region_label.setText("%d x %d at (%d, %d)" % (w, h, x, y))

    def set_running(self, running):
        self.start_btn.setText("Stop" if running else "Start")

    def set_status(self, text):
        self.status.setText(text)

    def show_result(self, res):
        x, y, w, h = res.rect
        self.status.setText("Running: %.0f fps, %d target%s found. Watching %dx%d at (%d, %d). Profile: %s"
                            % (res.fps, res.count, "" if res.count == 1 else "s", w, h, x, y,
                               self.cfg.active_profile))
        if res.preview_img is not None:
            self.preview_label.setPixmap(QPixmap.fromImage(res.preview_img))

    def closeEvent(self, e):
        self.quitRequested.emit()
        e.accept()
