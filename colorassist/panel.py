"""Control panel: sidebar navigation, a Home page with the essentials, and a page per feature."""
import copy
import os

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QPixmap
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLineEdit,
                             QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                             QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from . import APP_NAME, __version__, engine
from .config import CHOICES, Target, default_profiles
from .ui import ColourButton, SliderField, ToggleSwitch, card, label, swatch

PAGES = ["Home", "Targets", "Outline", "High contrast", "Magnifier", "Capture", "Tracking", "Hotkeys", "Settings"]


class Panel(QMainWindow):
    startStop = pyqtSignal()
    settingsChanged = pyqtSignal()
    displayModeChanged = pyqtSignal()
    profileChanged = pyqtSignal()
    previewChanged = pyqtSignal(object)
    pickColourRequested = pyqtSignal()
    pickRegionRequested = pyqtSignal()
    hotkeysApply = pyqtSignal()
    themeChanged = pyqtSignal()
    quitRequested = pyqtSignal()
    closeToTray = pyqtSignal()

    def __init__(self, cfg, config_path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.running = False
        self._refreshers = []          # re-read widgets from config (profile switch, hotkey toggles)
        self._target_refreshers = []   # re-read the target editor (target selection)
        self._target_widgets = []
        self._colour_buttons = []
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 620)

        central = QWidget()
        central.setObjectName("central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QWidget()
        side.setObjectName("side")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 12, 0, 0)
        sl.setSpacing(0)
        brand = label(APP_NAME, "brand", wrap=False)
        brand.setContentsMargins(14, 8, 8, 0)
        sl.addWidget(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.addItems(PAGES)
        sl.addWidget(self.nav, 1)
        self.side_state = label("○ Stopped", "muted")
        self.side_state.setContentsMargins(22, 8, 12, 4)
        self.side_saved = label("", "muted")
        self.side_saved.setContentsMargins(22, 0, 12, 14)
        sl.addWidget(self.side_state)
        sl.addWidget(self.side_saved)
        root.addWidget(side)

        self.stack = QStackedWidget()
        for build in (self._page_home, self._page_targets, self._page_outline, self._page_contrast,
                      self._page_magnifier, self._page_capture, self._page_tracking, self._page_hotkeys,
                      self._page_settings):
            self.stack.addWidget(self._scroll(build()))
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self._page_changed)
        self.nav.setCurrentRow(0)
        self.resize(1100, 760)
        self._reload_profiles()

    # ---------- layout helpers ----------
    @staticmethod
    def _scroll(content):
        content.setObjectName("page")
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        s.setWidget(content)
        return s

    @staticmethod
    def _page(title, subtitle):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(32, 26, 32, 26)
        v.setSpacing(18)
        v.addWidget(label(title, "h1"))
        if subtitle:
            v.addWidget(label(subtitle, "muted"))
        return w, v

    @staticmethod
    def _form(lay):
        f = QFormLayout()
        f.setHorizontalSpacing(18)
        f.setVerticalSpacing(12)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        lay.addLayout(f)
        return f

    def go(self, page_name):
        self.nav.setCurrentRow(PAGES.index(page_name))

    def _page_changed(self, row):
        self.stack.setCurrentIndex(row)
        self._emit_preview()

    # ---------- bound widgets ----------
    def _set(self, getter, attr, value, after=None):
        obj = getter()
        if obj is None:
            return
        setattr(obj, attr, value)
        if after:
            after()
        self.settingsChanged.emit()

    def _bind(self, kind, getter, attr, refreshers, text="", lo=0, hi=100, step=1, decimals=0, suffix="",
              choices_key=None, after=None, tip=""):
        if kind == "switch":
            w = ToggleSwitch(text)
            w.toggled.connect(lambda v: self._set(getter, attr, bool(v), after))
            load = lambda o: w.setChecked(bool(getattr(o, attr)))
        elif kind == "slider":
            w = SliderField(lo, hi, step, decimals, suffix)
            cast = float if decimals else int
            w.valueChanged.connect(lambda v: self._set(getter, attr, cast(round(v, decimals)), after))
            load = lambda o: w.setValue(getattr(o, attr))
        elif kind == "int":
            w = QSpinBox()
            w.setRange(lo, hi)
            w.setSingleStep(step)
            w.setSuffix(suffix)
            w.setMaximumWidth(220)
            w.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            w.valueChanged.connect(lambda v: self._set(getter, attr, int(v), after))
            load = lambda o: w.setValue(int(getattr(o, attr)))
        elif kind == "choice":
            w = QComboBox()
            for value, lab in CHOICES[choices_key]:
                w.addItem(lab, value)
            w.currentIndexChanged.connect(lambda i: self._set(getter, attr, w.itemData(i), after))
            load = lambda o: w.setCurrentIndex(max(0, w.findData(getattr(o, attr))))
        elif kind == "text":
            w = QLineEdit()
            w.editingFinished.connect(lambda: self._set(getter, attr, w.text().strip(), after))
            load = lambda o: w.setText(str(getattr(o, attr)))
        elif kind == "colour":
            w = ColourButton()
            w.setMinimumWidth(150)
            w.setMaximumWidth(260)
            self._colour_buttons.append((w, getter, attr))

            def choose():
                o = getter()
                if o is None:
                    return
                c = QColorDialog.getColor(QColor(getattr(o, attr)), self, "Choose colour")
                if c.isValid():
                    self._set(getter, attr, c.name().upper(), after)
                    w.set_colour(c.name().upper())
            w.clicked.connect(choose)
            load = lambda o: w.set_colour(getattr(o, attr))
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

    # ---------- pages ----------
    def _page_home(self):
        w, v = self._page("Home", "Make mobs easier to see on the PS Remote Play picture. "
                                  "MineColorTrack only draws on screen; it never controls the game.")
        c, cl = card()
        row = QHBoxLayout()
        row.setSpacing(22)
        self.start_btn = QPushButton()
        self.start_btn.setMinimumWidth(190)
        self.start_btn.clicked.connect(self.startStop.emit)
        row.addWidget(self.start_btn, 0, Qt.AlignmentFlag.AlignTop)
        st = QVBoxLayout()
        self.status_title = label("Stopped", "h2")
        self.status = label("Press Start, then switch back to the Remote Play window.", "muted")
        st.addWidget(self.status_title)
        st.addWidget(self.status)
        row.addLayout(st, 1)
        cl.addLayout(row)
        prow = QHBoxLayout()
        prow.addWidget(label("Profile", wrap=False))
        self.profile_box = QComboBox()
        self.profile_box.currentTextChanged.connect(self._profile_selected)
        prow.addWidget(self.profile_box, 1)
        more = QToolButton()
        more.setText("Manage profiles")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        for text, fn in (("Duplicate...", self._dup_profile), ("Rename...", self._rename_profile),
                         ("Delete", self._delete_profile), (None, None),
                         ("Restore built-in presets", self._restore_presets)):
            if text is None:
                menu.addSeparator()
                continue
            act = QAction(text, menu)
            act.triggered.connect(fn)
            menu.addAction(act)
        more.setMenu(menu)
        prow.addWidget(more)
        cl.addLayout(prow)
        v.addWidget(c)
        self._set_start_button()

        R = self._refreshers
        c, cl = card("Assist modes", "Mix and match. Each can also be switched with a hotkey while you play.")
        for getter, title, desc, page in (
                (lambda: self.cfg.profile.outline, "Outline", "Boxes and arrows around every match.", "Outline"),
                (lambda: self.cfg.profile.contrast, "High contrast",
                 "Dims and greys everything except the targets, which are painted bright.", "High contrast"),
                (lambda: self.cfg.profile.magnifier, "Magnifier",
                 "A zoomed lens on the farthest target or the screen centre.", "Magnifier")):
            r = QHBoxLayout()
            r.setSpacing(14)
            sw = self._bind("switch", getter, "enabled", R, text=title)
            sw.setMinimumWidth(230)
            r.addWidget(sw)
            r.addWidget(label(desc, "muted"), 1)
            b = QPushButton("Options")
            b.clicked.connect(lambda _=False, pg=page: self.go(pg))
            r.addWidget(b)
            cl.addLayout(r)
        v.addWidget(c)

        c, cl = card("Targets in this profile")
        self.home_targets = QVBoxLayout()
        self.home_targets.setSpacing(8)
        cl.addLayout(self.home_targets)
        b = QPushButton("Edit targets and pick colours")
        b.clicked.connect(lambda: self.go("Targets"))
        cl.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(c)

        c, cl = card("Display")
        f = self._form(cl)
        disp = lambda: self.cfg.display
        f.addRow("Show assist as", self._bind("choice", disp, "mode", R, choices_key=("DisplayCfg", "mode"),
                                              after=self.displayModeChanged.emit))
        f.addRow("", self._bind("switch", disp, "crosshair", R, text="Crosshair at the screen centre"))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _rebuild_home_targets(self):
        lay = self.home_targets
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                inner = item.layout()
                while inner.count():
                    it = inner.takeAt(0)
                    if it.widget():
                        it.widget().deleteLater()
        targets = self.cfg.profile.targets
        if not targets:
            lay.addWidget(label("No targets yet. Add one and pick its colour from the game.", "muted"))
            return
        for i, t in enumerate(targets):
            r = QHBoxLayout()
            r.setSpacing(12)
            r.addWidget(swatch(t.color, 22))
            sw = ToggleSwitch(t.name)
            sw.setChecked(t.enabled)
            sw.toggled.connect(lambda v, idx=i: self._toggle_target(idx, v))
            r.addWidget(sw, 1)
            r.addWidget(label("outline", "muted", wrap=False))
            r.addWidget(swatch(t.outline_color, 22))
            lay.addLayout(r)

    def _toggle_target(self, idx, value):
        targets = self.cfg.profile.targets
        if 0 <= idx < len(targets):
            targets[idx].enabled = bool(value)
            self._refresh_target_names()
            for r in self._target_refreshers:
                r()
            self.settingsChanged.emit()

    def _page_targets(self):
        w, v = self._page("Targets", "Each target is a colour to look for. Click “Pick colour from the game” "
                                     "and click on the mob, then fine-tune with the live preview.")
        row = QHBoxLayout()
        row.setSpacing(18)
        c, cl = card("List")
        self.target_list = QListWidget()
        self.target_list.setObjectName("targets")
        self.target_list.currentRowChanged.connect(self._target_selected)
        cl.addWidget(self.target_list, 1)
        bl = QHBoxLayout()
        for text, fn in (("Add", self._add_target), ("Copy", self._dup_target), ("Remove", self._remove_target)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bl.addWidget(b)
        cl.addLayout(bl)
        c.setMinimumWidth(270)
        row.addWidget(c, 1)

        T = self._target_refreshers
        tg = self._current_target
        c, cl = card("Selected target")
        pick = QPushButton("Pick colour from the game...")
        pick.setObjectName("primary")
        pick.clicked.connect(self.pickColourRequested.emit)
        self._target_widgets.append(pick)
        cl.addWidget(pick)
        f = self._form(cl)
        f.addRow("", self._bind("switch", tg, "enabled", T, text="Enabled", after=self._targets_edited))
        f.addRow("Name", self._bind("text", tg, "name", T, after=self._targets_edited))
        f.addRow("Colour", self._bind("colour", tg, "color", T, after=self._targets_edited))
        f.addRow("Hue tolerance", self._bind("slider", tg, "hue_tol", T, lo=1, hi=90, suffix=" °",
                                             tip="How far the shade may drift. Lower = only this exact shade."))
        f.addRow("Saturation min", self._bind("slider", tg, "sat_min", T, suffix=" %",
                                              tip="Raise to ignore greyish, washed-out pixels."))
        f.addRow("Saturation max", self._bind("slider", tg, "sat_max", T, suffix=" %"))
        f.addRow("Brightness min", self._bind("slider", tg, "val_min", T, suffix=" %",
                                              tip="Raise to ignore shadows and dark blocks such as leaves."))
        f.addRow("Brightness max", self._bind("slider", tg, "val_max", T, suffix=" %"))
        f.addRow("Minimum size", self._bind("int", tg, "min_area", T, lo=1, hi=200000, suffix=" px",
                                            tip="Smaller matches are ignored (removes specks of grass or leaves)."))
        f.addRow("Maximum size", self._bind("int", tg, "max_area", T, lo=0, hi=2000000, suffix=" px",
                                            tip="0 = no limit. Use it to ignore huge areas like a whole field."))
        f.addRow("Outline colour", self._bind("colour", tg, "outline_color", T, after=self._targets_edited))
        row.addWidget(c, 2)
        v.addLayout(row)

        c, cl = card("Live preview", "White = what will be highlighted for the selected target. "
                                     "Shown while this page is open and assist is running.")
        self.preview_label = label("Press Start on the Home page to see the live preview.", "preview")
        self.preview_label.setMinimumHeight(220)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.preview_label)
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_outline(self):
        o = lambda: self.cfg.profile.outline
        R = self._refreshers
        w, v = self._page("Outline", "Shapes drawn around each target.")
        c, cl = card()
        f = self._form(cl)
        f.addRow("", self._bind("switch", o, "enabled", R, text="Draw outlines"))
        f.addRow("Style", self._bind("choice", o, "style", R, choices_key=("OutlineCfg", "style")))
        f.addRow("Line thickness", self._bind("slider", o, "thickness", R, lo=1, hi=24, suffix=" px"))
        f.addRow("Space around target", self._bind("slider", o, "padding", R, lo=0, hi=60, suffix=" px"))
        f.addRow("Marker above target", self._bind("choice", o, "marker", R, choices_key=("OutlineCfg", "marker")))
        f.addRow("", self._bind("switch", o, "black_border", R, text="Black backing line (visible on any background)"))
        f.addRow("", self._bind("switch", o, "use_target_color", R, text="Use each target's own outline colour"))
        f.addRow("Single colour", self._bind("colour", o, "color", R))
        f.addRow("", self._bind("switch", o, "labels", R, text="Show target names"))
        f.addRow("", self._bind("switch", o, "blink", R, text="Blink"))
        f.addRow("", self._bind("switch", o, "show_held", R, text="Dashed outline for a moment after a target is lost"))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_contrast(self):
        k = lambda: self.cfg.profile.contrast
        R = self._refreshers
        w, v = self._page("High contrast", "Replaces the picture with a simplified copy where only targets stand "
                                           "out. It runs a few frames behind the live stream.")
        c, cl = card()
        f = self._form(cl)
        f.addRow("", self._bind("switch", k, "enabled", R, text="High-contrast view"))
        f.addRow("Dim everything else", self._bind("slider", k, "dim", R, suffix=" %"))
        f.addRow("", self._bind("switch", k, "greyscale", R, text="Turn everything else grey"))
        f.addRow("Draw targets as", self._bind("choice", k, "fill", R, choices_key=("ContrastCfg", "fill")))
        f.addRow("Solid colour", self._bind("colour", k, "fill_color", R))
        f.addRow("Thicken targets", self._bind("slider", k, "grow", R, lo=0, hi=30, suffix=" px"))
        f.addRow("", self._bind("switch", k, "edges", R, text="White edge around targets"))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_magnifier(self):
        m = lambda: self.cfg.profile.magnifier
        R = self._refreshers
        w, v = self._page("Magnifier", "A zoomed, contrast-boosted lens.")
        c, cl = card()
        f = self._form(cl)
        f.addRow("", self._bind("switch", m, "enabled", R, text="Magnifier lens"))
        f.addRow("Look at", self._bind("choice", m, "source", R, choices_key=("MagnifierCfg", "source")))
        f.addRow("Zoom", self._bind("slider", m, "zoom", R, lo=1.5, hi=10.0, step=0.5, decimals=1, suffix=" x"))
        f.addRow("Lens size", self._bind("slider", m, "size", R, lo=100, hi=900, step=10, suffix=" px"))
        f.addRow("Position", self._bind("choice", m, "position", R, choices_key=("MagnifierCfg", "position")))
        f.addRow("Shape", self._bind("choice", m, "shape", R, choices_key=("MagnifierCfg", "shape")))
        f.addRow("Extra contrast", self._bind("slider", m, "contrast", R, lo=0, hi=200, step=5, suffix=" %"))
        f.addRow("", self._bind("switch", m, "pixelated", R, text="Sharp pixels (best for Minecraft)"))
        f.addRow("Border colour", self._bind("colour", m, "border_color", R))
        f.addRow("", self._bind("switch", m, "link_line", R, text="Circle the source area and link it to the lens"))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_capture(self):
        cap = lambda: self.cfg.capture
        R = self._refreshers
        w, v = self._page("Capture", "Which part of the screen to watch.")
        c, cl = card("Source")
        f = self._form(cl)
        f.addRow("Watch", self._bind("choice", cap, "source", R, choices_key=("CaptureCfg", "source")))
        f.addRow("Window title contains", self._bind(
            "text", cap, "window_title", R, tip="Used when watching the PS Remote Play window."))
        self.monitor_box = QComboBox()
        try:
            names = engine.monitor_names()
        except Exception:
            names = ["1"]
        self.monitor_box.addItems(names)
        self.monitor_box.setCurrentIndex(max(0, min(len(names) - 1, self.cfg.capture.monitor - 1)))
        self.monitor_box.currentIndexChanged.connect(lambda i: self._set(cap, "monitor", i + 1))
        f.addRow("Monitor", self.monitor_box)
        rrow = QHBoxLayout()
        self.region_label = label("", wrap=False)
        rrow.addWidget(self.region_label, 1)
        rb = QPushButton("Select region on screen...")
        rb.clicked.connect(self.pickRegionRequested.emit)
        rrow.addWidget(rb)
        f.addRow("Custom region", rrow)
        self.show_region()
        v.addWidget(c)
        c, cl = card("Performance")
        f = self._form(cl)
        f.addRow("Frames per second", self._bind("slider", cap, "fps", R, lo=5, hi=60))
        f.addRow("Processing resolution", self._bind(
            "slider", cap, "scale", R, lo=20, hi=100, step=5, suffix=" %",
            tip="Lower is faster. 100% finds the smallest, farthest targets best."))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_tracking(self):
        t = lambda: self.cfg.profile.tracking
        R = self._refreshers
        w, v = self._page("Tracking", "How detections become steady outlines.")
        c, cl = card()
        f = self._form(cl)
        f.addRow("Smoothing", self._bind("slider", t, "smoothing", R, lo=0, hi=95, suffix=" %",
                                         tip="Higher = steadier outlines that trail fast mobs a little more."))
        f.addRow("Keep lost targets for", self._bind("slider", t, "hold_frames", R, lo=0, hi=90, suffix=" fr"))
        f.addRow("Join pieces closer than", self._bind("slider", t, "merge_distance", R, lo=0, hi=80, suffix=" px",
                                                       tip="Joins a creeper's head, body and legs into one box."))
        f.addRow("Speck filter", self._bind("slider", t, "noise_filter", R, lo=0, hi=6,
                                            tip="0 = off. Higher removes more single-pixel noise."))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_hotkeys(self):
        k = lambda: self.cfg.hotkeys
        R = self._refreshers
        w, v = self._page("Hotkeys", "Work anywhere, also while the game window is active. "
                                     "Examples: Ctrl+Alt+M, Shift+F7, Ctrl+Num5. Leave empty to disable.")
        c, cl = card()
        f = self._form(cl)
        f.addRow("Start / stop", self._bind("text", k, "toggle_overlay", R))
        f.addRow("Next profile", self._bind("text", k, "next_profile", R))
        f.addRow("Outline on/off", self._bind("text", k, "toggle_outline", R))
        f.addRow("High contrast on/off", self._bind("text", k, "toggle_contrast", R))
        f.addRow("Magnifier on/off", self._bind("text", k, "toggle_magnifier", R))
        b = QPushButton("Apply hotkeys")
        b.setObjectName("primary")
        b.clicked.connect(self.hotkeysApply.emit)
        f.addRow("", b)
        self.hotkey_status = label("", "muted")
        f.addRow(self.hotkey_status)
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_settings(self):
        d = lambda: self.cfg.display
        R = self._refreshers
        w, v = self._page("Settings", None)
        c, cl = card("Appearance")
        f = self._form(cl)
        f.addRow("Theme", self._bind("choice", d, "theme", R, choices_key=("DisplayCfg", "theme"),
                                     after=self.themeChanged.emit))
        f.addRow("Text size", self._bind("slider", d, "ui_font_pt", R, lo=9, hi=24, suffix=" pt",
                                         after=self.themeChanged.emit))
        v.addWidget(c)
        c, cl = card("Behaviour")
        f = self._form(cl)
        f.addRow("", self._bind("switch", d, "start_on_launch", R, text="Start assisting when the program opens"))
        f.addRow("", self._bind("switch", d, "close_to_tray", R,
                                text="Closing the window keeps it running in the system tray"))
        f.addRow("", self._bind("switch", d, "mirror_on_top", R, text="Keep the mirror window on top",
                                after=self.displayModeChanged.emit))
        v.addWidget(c)
        c, cl = card("About")
        cl.addWidget(label("%s %s" % (APP_NAME, __version__), "h2"))
        cl.addWidget(label("Settings are saved automatically to:\n%s" % self.config_path, "muted"))
        b = QPushButton("Open settings folder")
        b.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(self.config_path) or ".")))
        cl.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(c)
        v.addStretch(1)
        return w

    # ---------- refresh ----------
    def refresh_all(self):
        for r in self._refreshers:
            r()
        self._reload_targets()

    def restyle(self):
        """Theme changed: re-colour widgets that carry inline styles."""
        for w, getter, attr in self._colour_buttons:
            o = getter()
            if o is not None:
                w.set_colour(getattr(o, attr))
        self._set_start_button()
        self._rebuild_home_targets()

    # ---------- profiles ----------
    def _reload_profiles(self):
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        self.profile_box.addItems(list(self.cfg.profiles))
        self.cfg.profile  # normalise
        self.profile_box.setCurrentText(self.cfg.active_profile)
        self.profile_box.blockSignals(False)
        self.refresh_all()

    def _profile_selected(self, name):
        if name and name in self.cfg.profiles:
            self.cfg.active_profile = name
            self.refresh_all()
            self.profileChanged.emit()
            self.settingsChanged.emit()

    def select_profile(self, name):
        self.profile_box.setCurrentText(name)

    def _ask_name(self, title, default):
        name, ok = QInputDialog.getText(self, title, "Profile name:", text=default)
        name = name.strip()
        if not ok or not name:
            return None
        if name in self.cfg.profiles:
            QMessageBox.warning(self, APP_NAME, "A profile with that name already exists.")
            return None
        return name

    def _dup_profile(self):
        name = self._ask_name("Duplicate profile", self.cfg.active_profile + " (copy)")
        if name:
            self.cfg.profiles[name] = copy.deepcopy(self.cfg.profile)
            self.cfg.active_profile = name
            self._reload_profiles()
            self.profileChanged.emit()
            self.settingsChanged.emit()

    def _rename_profile(self):
        old = self.cfg.active_profile
        name = self._ask_name("Rename profile", old)
        if name:
            self.cfg.profiles = {(name if k == old else k): v for k, v in self.cfg.profiles.items()}
            self.cfg.active_profile = name
            self._reload_profiles()
            self.settingsChanged.emit()

    def _delete_profile(self):
        if len(self.cfg.profiles) <= 1:
            QMessageBox.information(self, APP_NAME, "Keep at least one profile.")
            return
        old = self.cfg.active_profile
        if QMessageBox.question(self, APP_NAME, "Delete profile '%s'?" % old) != QMessageBox.StandardButton.Yes:
            return
        del self.cfg.profiles[old]
        self.cfg.active_profile = next(iter(self.cfg.profiles))
        self._reload_profiles()
        self.profileChanged.emit()
        self.settingsChanged.emit()

    def _restore_presets(self):
        added = [k for k in default_profiles() if k not in self.cfg.profiles]
        for k, val in default_profiles().items():
            self.cfg.profiles.setdefault(k, val)
        self._reload_profiles()
        self.settingsChanged.emit()
        QMessageBox.information(self, APP_NAME,
                                "Restored: %s" % (", ".join(added) if added else "nothing was missing"))

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
            self.target_list.addItem(self._target_text(t))
        self.target_list.blockSignals(False)
        n = len(self.cfg.profile.targets)
        self.target_list.setCurrentRow(min(max(row, 0), n - 1) if n else -1)
        self._target_selected()
        self._rebuild_home_targets()

    @staticmethod
    def _target_text(t):
        return t.name + ("" if t.enabled else "  (off)")

    def _refresh_target_names(self):
        for i, t in enumerate(self.cfg.profile.targets):
            item = self.target_list.item(i)
            if item:
                item.setText(self._target_text(t))

    def _targets_edited(self):
        self._refresh_target_names()
        self._rebuild_home_targets()

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
        self._rebuild_home_targets()
        self.settingsChanged.emit()
        self.status.setText("Picked %s for '%s'. Check the live preview on the Targets page and adjust."
                            % (t.color, t.name))

    def _emit_preview(self):
        if not hasattr(self, "preview_label"):
            return
        on = self.nav.currentRow() == PAGES.index("Targets") and self.running
        row = self.target_list.currentRow() if on else -1
        self.previewChanged.emit(row if row >= 0 else None)
        if not on or row < 0:
            self.preview_label.clear()
            self.preview_label.setText("Press Start on the Home page to see the live preview."
                                       if not self.running else "Select a target to preview it.")

    # ---------- status ----------
    def _set_start_button(self):
        b = self.start_btn
        b.setText("■  Stop" if self.running else "▶  Start")
        b.setObjectName("danger" if self.running else "primary")
        b.setStyleSheet("QPushButton { font-size: %dpt; padding: 14px 30px; border-radius: 14px; }"
                        % (self.cfg.display.ui_font_pt + 3))
        b.style().unpolish(b)
        b.style().polish(b)

    def show_region(self):
        x, y, w, h = self.cfg.capture.region
        self.region_label.setText("%d × %d at (%d, %d)" % (w, h, x, y))

    def set_running(self, running):
        self.running = running
        self._set_start_button()
        self.side_state.setText("● Running" if running else "○ Stopped")
        self.status_title.setText("Running" if running else "Stopped")
        if not running:
            self.status.setText("Press Start, then switch back to the Remote Play window.")
        self._emit_preview()

    def set_status(self, text):
        self.status.setText(text)

    def set_saved(self, text):
        self.side_saved.setText(text)

    def show_result(self, res):
        x, y, w, h = res.rect
        self.status_title.setText("Running · %d target%s in view" % (res.count, "" if res.count == 1 else "s"))
        self.status.setText("%.0f fps · watching %d×%d at (%d, %d) · profile “%s”"
                            % (res.fps, w, h, x, y, self.cfg.active_profile))
        if res.preview_img is not None:
            pm = QPixmap.fromImage(res.preview_img)
            lw = max(100, self.preview_label.width() - 16)
            if pm.width() < lw:
                pm = pm.scaledToWidth(min(lw, pm.width() * 3), Qt.TransformationMode.FastTransformation)
            self.preview_label.setPixmap(pm)

    def closeEvent(self, e):
        if self.cfg.display.close_to_tray:
            e.ignore()
            self.hide()
            self.closeToTray.emit()
            return
        self.quitRequested.emit()
        e.accept()
