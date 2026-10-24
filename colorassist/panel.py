"""Control panel: sidebar navigation, a Home page with the essentials, a page per feature, and Help."""
import copy
import os
import shutil

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QPixmap
from PyQt6.QtWidgets import (QApplication, QColorDialog, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                             QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                             QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from . import APP_NAME, __version__, dataset, detector, engine, winplat
from .config import CHOICES, Entity, Profile, Target
from .help_text import HELP, NAV_TIPS, TIPS
from .ui import ColourButton, SliderField, ToggleSwitch, card, clear_layout, label, swatch

PAGES = ["Home", "Watch", "Targets", "Entities", "Outline", "Tracking", "Hotkeys", "Settings", "Help"]
HELP_IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "help")


def tip(key):
    return TIPS[key][1]


class Panel(QMainWindow):
    startStop = pyqtSignal()
    settingsChanged = pyqtSignal()
    displayModeChanged = pyqtSignal()
    profileChanged = pyqtSignal()
    watchChanged = pyqtSignal()
    previewChanged = pyqtSignal(object)
    pickColourRequested = pyqtSignal()
    pickRegionRequested = pyqtSignal()
    hotkeysApply = pyqtSignal()
    updateRequested = pyqtSignal()
    updateCheckRequested = pyqtSignal()
    labelerRequested = pyqtSignal()
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
        self._help_sections = {}
        self.anchors = {}              # widgets the help pictures point at, per page
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
        for name in PAGES:
            self.nav.addItem(name)
            self.nav.item(self.nav.count() - 1).setToolTip(NAV_TIPS.get(name, ""))
        sl.addWidget(self.nav, 1)
        self.side_state = label("○ Stopped", "muted")
        self.side_state.setContentsMargins(22, 8, 12, 4)
        self.side_saved = label("", "muted")
        self.side_saved.setContentsMargins(22, 0, 12, 14)
        sl.addWidget(self.side_state)
        sl.addWidget(self.side_saved)
        root.addWidget(side)

        self.stack = QStackedWidget()
        self._model_names = {}         # model path -> class names (read once)
        for build in (self._page_home, self._page_watch, self._page_targets, self._page_entities,
                      self._page_outline,
                      self._page_tracking, self._page_hotkeys, self._page_settings, self._page_help):
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

    def _page(self, title, subtitle, help_key=None):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(32, 26, 32, 26)
        v.setSpacing(18)
        head = QHBoxLayout()
        head.addWidget(label(title, "h1"), 1)
        if help_key:
            b = QPushButton("?  Help")
            b.setToolTip(tip("help_button"))
            b.clicked.connect(lambda: self.show_help(help_key))
            head.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(head)
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

    @staticmethod
    def _row(form, key, field):
        """Add a form row whose label and field both show the tooltip for `key`."""
        text, tiptext = TIPS[key]
        lab = QLabel(text)
        lab.setToolTip(tiptext)
        if isinstance(field, QWidget):
            field.setToolTip(tiptext)
            form.addRow(lab, field)
        else:                                   # a layout
            for i in range(field.count()):
                wdg = field.itemAt(i).widget()
                if wdg is not None and not wdg.toolTip():
                    wdg.setToolTip(tiptext)
            form.addRow(lab, field)
        return lab

    @staticmethod
    def _button(text, key, slot, name=None):
        b = QPushButton(text)
        b.setToolTip(tip(key))
        b.clicked.connect(slot)
        if name:
            b.setObjectName(name)
        return b

    def go(self, page_name):
        self.nav.setCurrentRow(PAGES.index(page_name))

    def _page_changed(self, row):
        self.stack.setCurrentIndex(row)
        self._emit_preview()

    def show_help(self, key):
        self.go("Help")
        section = self._help_sections.get(key)
        scroll = self.stack.widget(PAGES.index("Help"))
        if section is not None:
            QTimer.singleShot(30, lambda: scroll.verticalScrollBar().setValue(max(0, section.y() - 12)))

    # ---------- bound widgets ----------
    def _set(self, getter, attr, value, after=None):
        obj = getter()
        if obj is None:
            return
        setattr(obj, attr, value)
        if after:
            after()
        self.settingsChanged.emit()

    def _bind(self, kind, getter, attr, refreshers, key, lo=0, hi=100, step=1, decimals=0, suffix="",
              choices_key=None, after=None):
        text, tiptext = TIPS[key]
        if kind == "switch":
            w = ToggleSwitch(text)
            w.toggled.connect(lambda v: self._set(getter, attr, bool(v), after))
            load = lambda o: w.setChecked(bool(getattr(o, attr)))
        elif kind == "slider":
            w = SliderField(lo, hi, step, decimals, suffix)
            cast = float if decimals else int
            w.valueChanged.connect(lambda v: self._set(getter, attr, cast(round(v, decimals)), after))
            load = lambda o: w.setValue(getattr(o, attr))
            w.slider.setToolTip(tiptext)
            w.spin.setToolTip(tiptext)
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
        w.setToolTip(tiptext)

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
        return w

    # ---------- pages ----------
    def _page_home(self):
        R = self._refreshers
        w, v = self._page("Home", "Outlines things of chosen colours on your screen so they are easier to see. "
                                  "MineColorTrack only draws; it never controls the game.", "start")
        c, cl = card()
        self.update_card = c
        self.update_text = label("", "h2")
        cl.addWidget(self.update_text)
        urow = QHBoxLayout()
        urow.addWidget(self._button("Update now", "update_now", self.updateRequested.emit, "primary"))
        urow.addWidget(self._button("What's new", "update_notes", self._open_update_notes))
        urow.addWidget(self._button("Skip this version", "update_skip", self._skip_update))
        urow.addStretch(1)
        cl.addLayout(urow)
        c.hide()
        v.addWidget(c)
        self._update_info = None
        c, cl = card()
        row = QHBoxLayout()
        row.setSpacing(22)
        self.start_btn = QPushButton()
        self.start_btn.setMinimumWidth(190)
        self.start_btn.setToolTip(tip("start"))
        self.start_btn.clicked.connect(self.startStop.emit)
        row.addWidget(self.start_btn, 0, Qt.AlignmentFlag.AlignTop)
        st = QVBoxLayout()
        self.status_title = label("Stopped", "h2")
        self.status = label("Press Start, then click back into your game.", "muted")
        st.addWidget(self.status_title)
        st.addWidget(self.status)
        row.addLayout(st, 1)
        cl.addLayout(row)
        prow = QHBoxLayout()
        plab = label(TIPS["profile"][0], wrap=False)
        plab.setToolTip(tip("profile"))
        prow.addWidget(plab)
        self.profile_box = QComboBox()
        self.profile_box.setToolTip(tip("profile"))
        self.profile_box.currentTextChanged.connect(self._profile_selected)
        prow.addWidget(self.profile_box, 1)
        more = QToolButton()
        more.setText("Manage profiles")
        more.setToolTip(tip("manage_profiles"))
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        for text, fn in (("New empty profile...", self._new_profile), ("Duplicate...", self._dup_profile),
                         ("Rename...", self._rename_profile), (None, None), ("Delete", self._delete_profile)):
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

        c, cl = card("Outline")
        r = QHBoxLayout()
        r.setSpacing(14)
        self.home_outline = self._bind("switch", lambda: self.cfg.profile.outline, "enabled", R, "outline_switch")
        self.home_outline.setMinimumWidth(230)
        r.addWidget(self.home_outline)
        r.addWidget(label("Boxes and arrows around everything that matches your targets.", "muted"), 1)
        r.addWidget(self._button("Options", "outline_options", lambda: self.go("Outline")))
        cl.addLayout(r)
        v.addWidget(c)

        c, cl = card("AI entity detection")
        r = QHBoxLayout()
        r.setSpacing(14)
        self.home_ai = self._bind("switch", lambda: self.cfg.profile.detection, "enabled", R, "detection.enabled",
                                  after=self._ai_edited)
        self.home_ai.setMinimumWidth(230)
        r.addWidget(self.home_ai)
        self.home_ai_text = label("", "muted")
        r.addWidget(self.home_ai_text, 1)
        r.addWidget(self._button("Options", "outline_options", lambda: self.go("Entities")))
        cl.addLayout(r)
        v.addWidget(c)

        c, cl = card("Targets in this profile")
        self.home_targets_card = c
        self.home_targets = QVBoxLayout()
        self.home_targets.setSpacing(8)
        cl.addLayout(self.home_targets)
        cl.addWidget(self._button("Edit targets and pick colours", "edit_targets", lambda: self.go("Targets")),
                     0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(c)

        c, cl = card("Watching")
        self.home_watch_card = c
        wr = QHBoxLayout()
        self.watch_summary = label("", wrap=True)
        wr.addWidget(self.watch_summary, 1)
        wr.addWidget(self._button("Change", "change_watch", lambda: self.go("Watch")))
        cl.addLayout(wr)
        f = self._form(cl)
        disp = lambda: self.cfg.display
        self._row(f, "display.mode", self._bind("choice", disp, "mode", R, "display.mode",
                                                choices_key=("DisplayCfg", "mode"), after=self.displayModeChanged.emit))
        f.addRow("", self._bind("switch", disp, "crosshair", R, "display.crosshair"))
        self._row(f, "display.crosshair_color", self._bind("colour", disp, "crosshair_color", R,
                                                           "display.crosshair_color"))
        v.addWidget(c)
        v.addStretch(1)
        self.anchors["home"] = [self.start_btn, self.profile_box, self.home_outline, self.home_targets_card,
                                self.home_watch_card]
        return w

    def _page_watch(self):
        cap = lambda: self.cfg.capture
        R = self._refreshers
        w, v = self._page("Watch", "Choose what MineColorTrack scans for your target colours.", "watch")
        c, cl = card("What to watch")
        f = self._form(cl)
        self.source_box = self._bind("choice", cap, "source", R, "capture.source",
                                     choices_key=("CaptureCfg", "source"), after=self._watch_edited)
        self._row(f, "capture.source", self.source_box)

        wrow = QHBoxLayout()
        self.window_box = QComboBox()
        self.window_box.setMinimumContentsLength(30)
        self.window_box.activated.connect(self._window_chosen)
        wrow.addWidget(self.window_box, 1)
        wrow.addWidget(self._button("Refresh", "refresh", self.refresh_sources))
        self._row(f, "window_list", wrow)
        self.title_edit = self._bind("text", cap, "window_title", R, "capture.window_title", after=self._watch_edited)
        self._row(f, "capture.window_title", self.title_edit)
        self.exe_edit = self._bind("text", cap, "window_exe", R, "capture.window_exe", after=self._watch_edited)
        self._row(f, "capture.window_exe", self.exe_edit)

        self.monitor_box = QComboBox()
        self.monitor_box.currentIndexChanged.connect(self._monitor_chosen)
        self._row(f, "capture.monitor", self.monitor_box)
        rrow = QHBoxLayout()
        self.region_label = label("", wrap=False)
        rrow.addWidget(self.region_label, 1)
        self.region_btn = self._button("Select region on screen...", "select_region", self.pickRegionRequested.emit)
        rrow.addWidget(self.region_btn)
        self._row(f, "region", rrow)
        v.addWidget(c)
        self.refresh_sources()

        c, cl = card("Performance")
        self.perf_card = c
        f = self._form(cl)
        self.fps_slider = self._bind("slider", cap, "fps", R, "capture.fps", lo=5, hi=120)
        self._row(f, "capture.fps", self.fps_slider)
        self._row(f, "capture.scale", self._bind("slider", cap, "scale", R, "capture.scale", lo=20, hi=100,
                                                 step=5, suffix=" %"))
        self._row(f, "capture.method", self._bind("choice", cap, "method", R, "capture.method",
                                                  choices_key=("CaptureCfg", "method")))
        v.addWidget(c)
        v.addStretch(1)
        self.anchors["watch"] = [self.source_box, self.window_box, self.monitor_box, self.region_btn, self.perf_card]
        return w

    def refresh_sources(self):
        """Re-read open windows and monitors into the Watch page lists."""
        cap = self.cfg.capture
        self.window_box.blockSignals(True)
        self.window_box.clear()
        wins = winplat.list_windows()
        current = -1
        for wdw in wins:
            text = wdw["title"] + ("  (%s)" % wdw["exe"] if wdw["exe"] else "") + \
                ("  [minimised]" if wdw["minimised"] else "")
            self.window_box.addItem(text, (wdw["title"], wdw["exe"]))
            if current < 0 and (cap.window_title or cap.window_exe):
                same_exe = not cap.window_exe or wdw["exe"].lower() == cap.window_exe.lower()
                if same_exe and cap.window_title.lower() in wdw["title"].lower():
                    current = self.window_box.count() - 1
        if current < 0 and (cap.window_title or cap.window_exe):
            self.window_box.insertItem(0, "%s  (not open right now)" % (cap.window_title or cap.window_exe),
                                       (cap.window_title, cap.window_exe))
            current = 0
        if not wins and not winplat.IS_WIN:
            self.window_box.addItem("The window list is available on Windows", None)
        elif not wins:
            self.window_box.addItem("No open windows found. Open your game and press Refresh.", None)
        if current < 0:
            self.window_box.insertItem(0, "Choose a window...", None)
            current = 0
        self.window_box.setCurrentIndex(current)
        self.window_box.blockSignals(False)

        self.monitor_box.blockSignals(True)
        self.monitor_box.clear()
        try:
            names = engine.monitor_names()
        except Exception:
            names = ["1"]
        for n in names:
            self.monitor_box.addItem("Monitor " + n)
        self.monitor_box.setCurrentIndex(max(0, min(len(names) - 1, cap.monitor - 1)))
        self.monitor_box.blockSignals(False)
        self._update_watch_rows()

    def _window_chosen(self, index):
        data = self.window_box.itemData(index)
        if not data:
            return
        cap = self.cfg.capture
        cap.window_title, cap.window_exe = data
        cap.source = "window"
        self._watch_edited()
        for r in self._refreshers:
            r()
        self.settingsChanged.emit()

    def _monitor_chosen(self, index):
        self.cfg.capture.monitor = index + 1
        if self.cfg.capture.source != "region":
            self.cfg.capture.source = "monitor"
        self._watch_edited()
        for r in self._refreshers:
            r()
        self.settingsChanged.emit()

    def _watch_edited(self):
        self._update_watch_rows()
        self.watchChanged.emit()

    def _update_watch_rows(self):
        src = self.cfg.capture.source
        for wdg in (self.title_edit, self.exe_edit):
            wdg.setEnabled(src == "window")
        self.region_btn.setEnabled(src == "region")
        self.show_region()
        self.watch_summary.setText(self.watch_text())

    def watch_text(self):
        cap = self.cfg.capture
        if cap.source == "window":
            name = cap.window_title or cap.window_exe
            return "Window: “%s”" % name if name else "Window: none chosen yet"
        if cap.source == "monitor":
            return "Monitor %s" % self.monitor_box.itemText(max(0, cap.monitor - 1)).replace("Monitor ", "")
        x, y, w, h = cap.region
        return "Part of the screen: %d × %d at (%d, %d)" % (w, h, x, y)

    def _page_targets(self):
        w, v = self._page("Targets", "Each target is a colour to look for. Click “Pick colour from the game” "
                                     "and click on the mob, then fine-tune with the live preview.", "targets")
        row = QHBoxLayout()
        row.setSpacing(18)
        c, cl = card("List")
        self.target_list = QListWidget()
        self.target_list.setObjectName("targets")
        self.target_list.setToolTip(tip("target_list"))
        self.target_list.currentRowChanged.connect(self._target_selected)
        cl.addWidget(self.target_list, 1)
        bl = QHBoxLayout()
        for text, key, fn in (("Add", "target_add", self._add_target), ("Copy", "target_copy", self._dup_target),
                              ("Remove", "target_remove", self._remove_target)):
            bl.addWidget(self._button(text, key, fn))
        cl.addLayout(bl)
        cl.addWidget(self._button("Add Minecraft armour targets", "target_add_armour", self._add_armour))
        c.setMinimumWidth(330)
        row.addWidget(c, 1)

        T = self._target_refreshers
        tg = self._current_target
        c, cl = card("Selected target")
        self.pick_btn = self._button("Pick colour from the game...", "pick", self.pickColourRequested.emit, "primary")
        self._target_widgets.append(self.pick_btn)
        cl.addWidget(self.pick_btn)
        f = self._form(cl)
        f.addRow("", self._bind("switch", tg, "enabled", T, "target.enabled", after=self._targets_edited))
        self._row(f, "target.name", self._bind("text", tg, "name", T, "target.name", after=self._targets_edited))
        self.colour_btn = self._bind("colour", tg, "color", T, "target.color", after=self._targets_edited)
        self._row(f, "target.color", self.colour_btn)
        ranges = []
        for attr, lo, hi, suffix in (("hue_tol", 1, 90, " °"), ("sat_min", 0, 100, " %"),
                                     ("sat_max", 0, 100, " %"), ("val_min", 0, 100, " %"),
                                     ("val_max", 0, 100, " %")):
            wdg = self._bind("slider", tg, attr, T, "target." + attr, lo=lo, hi=hi, suffix=suffix)
            self._row(f, "target." + attr, wdg)
            ranges.append(wdg)
        self.size_box = self._bind("int", tg, "min_area", T, "target.min_area", lo=1, hi=200000, suffix=" px")
        self._row(f, "target.min_area", self.size_box)
        self._row(f, "target.max_area", self._bind("int", tg, "max_area", T, "target.max_area", lo=0, hi=2000000,
                                                   suffix=" px"))
        self._row(f, "target.outline_color", self._bind("colour", tg, "outline_color", T, "target.outline_color",
                                                        after=self._targets_edited))
        row.addWidget(c, 2)
        v.addLayout(row)

        c, cl = card("Live preview", "White = what will be outlined for the selected target. "
                                     "Shown while this page is open and MineColorTrack is running.")
        self.preview_label = label("Press Start on the Home page to see the live preview.", "preview")
        self.preview_label.setToolTip(tip("preview"))
        self.preview_label.setMinimumHeight(220)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.preview_label)
        v.addWidget(c)
        v.addStretch(1)
        self.anchors["targets"] = [self.target_list, self.pick_btn, self.colour_btn, ranges[0], self.size_box,
                                   self.preview_label]
        return w

    def _page_entities(self):
        d = lambda: self.cfg.profile.detection
        R = self._refreshers
        w, v = self._page("Entities", "Find things by their shape, such as pigs, villagers or players, with an AI "
                                      "model you train on your own labelled screenshots.", "entities")
        c, cl = card("AI model")
        f = self._form(cl)
        self.ai_switch = self._bind("switch", d, "enabled", R, "detection.enabled", after=self._ai_edited)
        f.addRow("", self.ai_switch)
        mrow = QHBoxLayout()
        self.model_label = label("", wrap=True)
        mrow.addWidget(self.model_label, 1)
        self.load_model_btn = self._button("Load model...", "load_model", self.load_model, "primary")
        mrow.addWidget(self.load_model_btn)
        mrow.addWidget(self._button("Clear", "clear_model", self.clear_model))
        self._row(f, "model_file", mrow)
        self.model_info = label("", "muted")
        f.addRow("", self.model_info)
        self.confidence_slider = self._bind("slider", d, "confidence", R, "detection.confidence", lo=5, hi=95,
                                            suffix=" %")
        self._row(f, "detection.confidence", self.confidence_slider)
        f.addRow("", self._bind("switch", lambda: self.cfg.ai, "prefer_gpu", R, "ai.prefer_gpu"))
        v.addWidget(c)

        c, cl = card("Entities in this model")
        self.entity_card = c
        self.entity_rows = QVBoxLayout()
        self.entity_rows.setSpacing(8)
        cl.addLayout(self.entity_rows)
        v.addWidget(c)

        c, cl = card("Make your own model", "1. Collect and label screenshots.  2. Export for training.  "
                                            "3. Train in Google Colab (free).  4. Load the model above.")
        brow = QHBoxLayout()
        brow.addWidget(self._button("Open labelling tool", "open_labeler", self.labelerRequested.emit, "primary"))
        brow.addWidget(self._button("Open Google Colab", "open_colab", lambda: QDesktopServices.openUrl(
            QUrl("https://colab.research.google.com/"))))
        brow.addWidget(self._button("Save training notebook...", "save_notebook", self.save_notebook))
        brow.addStretch(1)
        cl.addLayout(brow)
        drow = QHBoxLayout()
        self.dataset_label = label("", wrap=True)
        drow.addWidget(self.dataset_label, 1)
        drow.addWidget(self._button("Change...", "change_dataset", self.change_dataset))
        f = self._form(cl)
        self._row(f, "dataset_dir", drow)
        v.addWidget(c)
        v.addStretch(1)
        self.anchors["entities"] = [self.ai_switch, self.load_model_btn, self.confidence_slider, self.entity_card, c]
        return w

    # ---------- AI model ----------
    def dataset_root(self):
        return self.cfg.ai.dataset_dir or dataset.default_root()

    def model_names(self, path):
        """Class names of a model file (cached); raises detector.ModelError."""
        if path not in self._model_names:
            self._model_names[path] = detector.Detector(path, prefer_gpu=False).names
        return self._model_names[path]

    def load_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load AI model", os.path.dirname(self.cfg.profile.detection.model_path
                                                                                  or self.dataset_root()),
                                              "ONNX models (*.onnx)")
        if not path:
            return
        try:
            names = self.model_names(path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, "This model cannot be used:\n%s" % exc)
            return
        det = self.cfg.profile.detection
        old = {e.name: e for e in det.entities}
        det.entities = [old.get(n) or Entity(name=n, outline_color=engine.PALETTE[i % len(engine.PALETTE)])
                        for i, n in enumerate(names)]
        det.model_path = path
        det.enabled = True
        self.refresh_all()
        self.settingsChanged.emit()

    def clear_model(self):
        det = self.cfg.profile.detection
        det.model_path = ""
        det.enabled = False
        det.entities = []
        self.refresh_all()
        self.settingsChanged.emit()

    def save_notebook(self):
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "train_minecolortrack.ipynb")
        path, _ = QFileDialog.getSaveFileName(self, "Save training notebook",
                                              os.path.join(os.path.dirname(self.dataset_root()),
                                                           "train_minecolortrack.ipynb"), "Notebooks (*.ipynb)")
        if path:
            try:
                shutil.copyfile(src, path)
            except OSError as exc:
                QMessageBox.warning(self, APP_NAME, "Could not save: %s" % exc)

    def change_dataset(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a dataset folder", self.dataset_root())
        if path:
            self.cfg.ai.dataset_dir = path
            self._refresh_ai()
            self.settingsChanged.emit()

    def set_dataset_dir(self, path):
        self.cfg.ai.dataset_dir = path
        self._refresh_ai()
        self.settingsChanged.emit()

    def _ai_edited(self):
        self._refresh_ai()

    def _refresh_ai(self, device=None, error=None):
        det = self.cfg.profile.detection
        self.dataset_label.setText(self.dataset_root())
        names, problem = [], None
        if det.model_path:
            try:
                names = self.model_names(det.model_path)
            except Exception as exc:
                problem = str(exc)
        self.model_label.setText(os.path.basename(det.model_path) if det.model_path else "No model loaded")
        self.model_label.setToolTip(det.model_path or tip("model_file"))
        if not detector.available():
            info = "The AI runtime is missing from this installation."
        elif problem or error:
            info = "Problem: %s" % (problem or error)
        elif det.model_path:
            info = "%d entit%s: %s%s" % (len(names), "y" if len(names) == 1 else "ies", ", ".join(names),
                                         (" \u00b7 running on the %s" % device) if device else "")
        else:
            info = "Load a model you trained, or make one with the labelling tool."
        self.model_info.setText(info)
        on = [e.name for e in det.entities if e.enabled]
        if not det.model_path:
            self.home_ai_text.setText("No model loaded. Options shows how to make one.")
        else:
            self.home_ai_text.setText("%s \u00b7 %d of %d entities on" % (os.path.basename(det.model_path), len(on),
                                                                         len(det.entities)))
        self._rebuild_entity_rows()

    def _rebuild_entity_rows(self):
        lay = self.entity_rows
        clear_layout(lay)
        det = self.cfg.profile.detection
        if not det.entities:
            lay.addWidget(label("Entities appear here when a model is loaded.", "muted"))
            return
        for e in det.entities:
            r = QHBoxLayout()
            sw = ToggleSwitch(e.name)
            sw.setToolTip(tip("entity_switch"))
            sw.setChecked(e.enabled)
            sw.toggled.connect(lambda val, ent=e: self._entity_toggled(ent, val))
            r.addWidget(sw, 1)
            cb = ColourButton()
            cb.setToolTip(tip("entity_colour"))
            cb.setMaximumWidth(160)
            cb.set_colour(e.outline_color)
            cb.clicked.connect(lambda _=False, ent=e, btn=cb: self._entity_colour(ent, btn))
            r.addWidget(cb)
            lay.addLayout(r)

    def _entity_toggled(self, ent, value):
        ent.enabled = bool(value)
        self._refresh_ai()
        self.settingsChanged.emit()

    def _entity_colour(self, ent, btn):
        c = QColorDialog.getColor(QColor(ent.outline_color), self, "Outline colour for %s" % ent.name)
        if c.isValid():
            ent.outline_color = c.name().upper()
            btn.set_colour(ent.outline_color)
            self.settingsChanged.emit()

    def _page_outline(self):
        o = lambda: self.cfg.profile.outline
        R = self._refreshers
        w, v = self._page("Outline", "How the outlines around targets look.", "outline")
        c, cl = card()
        f = self._form(cl)
        f.addRow("", self._bind("switch", o, "enabled", R, "outline.enabled"))
        self._row(f, "outline.style", self._bind("choice", o, "style", R, "outline.style",
                                                 choices_key=("OutlineCfg", "style")))
        self._row(f, "outline.thickness", self._bind("slider", o, "thickness", R, "outline.thickness", lo=1, hi=24,
                                                     suffix=" px"))
        self._row(f, "outline.padding", self._bind("slider", o, "padding", R, "outline.padding", lo=0, hi=60,
                                                   suffix=" px"))
        self._row(f, "outline.marker", self._bind("choice", o, "marker", R, "outline.marker",
                                                  choices_key=("OutlineCfg", "marker")))
        f.addRow("", self._bind("switch", o, "black_border", R, "outline.black_border"))
        f.addRow("", self._bind("switch", o, "use_target_color", R, "outline.use_target_color"))
        self._row(f, "outline.color", self._bind("colour", o, "color", R, "outline.color"))
        f.addRow("", self._bind("switch", o, "labels", R, "outline.labels"))
        f.addRow("", self._bind("switch", o, "blink", R, "outline.blink"))
        f.addRow("", self._bind("switch", o, "show_held", R, "outline.show_held"))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_tracking(self):
        t = lambda: self.cfg.profile.tracking
        R = self._refreshers
        w, v = self._page("Tracking", "How detections become steady outlines.", "profiles")
        c, cl = card()
        f = self._form(cl)
        self._row(f, "tracking.smoothing", self._bind("slider", t, "smoothing", R, "tracking.smoothing", lo=0, hi=95,
                                                      suffix=" %"))
        self._row(f, "tracking.hold_frames", self._bind("slider", t, "hold_frames", R, "tracking.hold_frames",
                                                        lo=0, hi=90, suffix=" fr"))
        self._row(f, "tracking.merge_distance", self._bind("slider", t, "merge_distance", R,
                                                           "tracking.merge_distance", lo=0, hi=80, suffix=" px"))
        self._row(f, "tracking.noise_filter", self._bind("slider", t, "noise_filter", R, "tracking.noise_filter",
                                                         lo=0, hi=6))
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_hotkeys(self):
        k = lambda: self.cfg.hotkeys
        R = self._refreshers
        w, v = self._page("Hotkeys", "Work anywhere, also while the game window is active. "
                                     "Examples: Ctrl+Alt+O, Shift+F7, Ctrl+Num5. Leave empty to disable.", "profiles")
        c, cl = card()
        f = self._form(cl)
        for attr in ("toggle_overlay", "next_profile", "toggle_outline", "save_screenshot"):
            self._row(f, "hotkeys." + attr, self._bind("text", k, attr, R, "hotkeys." + attr))
        f.addRow("", self._button("Apply hotkeys", "hotkeys_apply", self.hotkeysApply.emit, "primary"))
        self.hotkey_status = label("", "muted")
        f.addRow(self.hotkey_status)
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_settings(self):
        d = lambda: self.cfg.display
        R = self._refreshers
        w, v = self._page("Settings", None, "profiles")
        c, cl = card("Appearance")
        f = self._form(cl)
        self._row(f, "display.theme", self._bind("choice", d, "theme", R, "display.theme",
                                                 choices_key=("DisplayCfg", "theme"), after=self.themeChanged.emit))
        self._row(f, "display.ui_font_pt", self._bind("slider", d, "ui_font_pt", R, "display.ui_font_pt", lo=9, hi=24,
                                                      suffix=" pt", after=self.themeChanged.emit))
        v.addWidget(c)
        c, cl = card("Behaviour")
        f = self._form(cl)
        f.addRow("", self._bind("switch", d, "start_on_launch", R, "display.start_on_launch"))
        f.addRow("", self._bind("switch", d, "close_to_tray", R, "display.close_to_tray"))
        f.addRow("", self._bind("switch", d, "mirror_on_top", R, "display.mirror_on_top",
                                after=self.displayModeChanged.emit))
        v.addWidget(c)
        c, cl = card("Updates")
        f = self._form(cl)
        f.addRow("", self._bind("switch", lambda: self.cfg.updates, "check_on_start", R, "updates.check_on_start"))
        ur = QHBoxLayout()
        ur.addWidget(self._button("Check for updates now", "check_updates", self.updateCheckRequested.emit))
        self.update_status = label("", "muted")
        ur.addWidget(self.update_status, 1)
        f.addRow("", ur)
        v.addWidget(c)

        c, cl = card("Command line (for scripts and AI agents)",
                     "The mct tool controls everything on these pages: settings, profiles, targets, the AI model, "
                     "what to watch, start and stop. Changes apply live while MineColorTrack is open.")
        self.cli_path = label(self.cli_location(), "muted")
        cl.addWidget(self.cli_path)
        crow = QHBoxLayout()
        crow.addWidget(self._button("Copy instructions for an AI agent", "copy_agent_prompt", self.copy_agent_prompt,
                                    "primary"))
        crow.addStretch(1)
        cl.addLayout(crow)
        v.addWidget(c)

        c, cl = card("About")
        cl.addWidget(label("%s %s" % (APP_NAME, __version__), "h2"))
        cl.addWidget(label("Settings are saved automatically to:\n%s" % self.config_path, "muted"))
        cl.addWidget(self._button("Open settings folder", "open_folder", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(self.config_path) or "."))), 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(c)
        v.addStretch(1)
        return w

    def _page_help(self):
        w, v = self._page("Help", "How every part of MineColorTrack works. Hover over any setting for a short "
                                  "explanation too. Numbers in the pictures match the numbered lists.")
        for key, title, image, html in HELP:
            c, cl = card(title)
            path = os.path.join(HELP_IMAGES, image) if image else None
            if path and os.path.exists(path):
                pm = QPixmap(path)
                if pm.width() > 820:
                    pm = pm.scaledToWidth(820, Qt.TransformationMode.SmoothTransformation)
                pic = QLabel()
                pic.setPixmap(pm)
                pic.setAlignment(Qt.AlignmentFlag.AlignLeft)
                cl.addWidget(pic)
            text = QLabel(html.strip())
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setWordWrap(True)
            cl.addWidget(text)
            v.addWidget(c)
            self._help_sections[key] = c
        v.addStretch(1)
        return w

    # ---------- updates ----------
    def show_update(self, info, manual=False):
        """info from updater.check(); manual = the person pressed Check now."""
        self._update_info = info
        newer = info.get("newer")
        skipped = info.get("latest") == self.cfg.updates.skip_version
        if newer:
            self.update_status.setText("Version %s is available (you have %s)." % (info["latest"], info["current"]))
        else:
            self.update_status.setText("You have the newest version (%s)." % info["current"])
        if newer and (manual or not skipped):
            self.update_text.setText("MineColorTrack %s is available (you have %s)." % (info["latest"],
                                                                                         info["current"]))
            self.update_card.show()
        else:
            self.update_card.hide()

    def show_update_problem(self, text):
        self.update_status.setText(text)

    def _open_update_notes(self):
        if self._update_info and self._update_info.get("url"):
            QDesktopServices.openUrl(QUrl(self._update_info["url"]))

    def _skip_update(self):
        if self._update_info:
            self.cfg.updates.skip_version = self._update_info.get("latest", "")
            self.update_card.hide()
            self.settingsChanged.emit()

    # ---------- command line ----------
    @staticmethod
    def cli_location():
        import sys
        if getattr(sys, "frozen", False):
            return "Program: %s   (type mct in a terminal if it was added to PATH)" % os.path.join(
                os.path.dirname(sys.executable), "mct.exe")
        return "From source: python mct.py ...  (run in the MineColorTrack folder)"

    def copy_agent_prompt(self):
        import sys
        exe = os.path.join(os.path.dirname(sys.executable), "mct.exe") if getattr(sys, "frozen", False) \
            else "python mct.py"
        text = ("You can control the MineColorTrack app on this PC with its command-line tool: %s "
                "(or just `mct` if it is on PATH). Start by running `mct guide` and `mct schema`. Every command "
                "prints JSON; errors are JSON on stderr with exit code 1. Changes apply live while the app is open. "
                "Use `mct status` to see what it is doing, `mct get`/`mct set KEY VALUE` for settings, "
                "`mct target ...` for colour targets, `mct model`/`mct entity` for the AI model, `mct watch ...` "
                "for what to watch, and `mct detect IMAGE --out marked.png` to test settings on a screenshot. "
                "Do not delete profiles or reset settings unless I ask." % exe)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, APP_NAME, "Copied. Paste it into your AI agent's chat.")

    # ---------- refresh ----------
    def refresh_all(self):
        for r in self._refreshers:
            r()
        self._reload_targets()
        self._update_watch_rows()
        self._refresh_ai()

    def restyle(self):
        """Theme changed: re-colour widgets that carry inline styles."""
        for w, getter, attr in self._colour_buttons:
            o = getter()
            if o is not None:
                w.set_colour(getattr(o, attr))
        self._set_start_button()
        self._rebuild_home_targets()

    # ---------- home target switches ----------
    def _rebuild_home_targets(self):
        lay = self.home_targets
        clear_layout(lay)
        targets = self.cfg.profile.targets
        if not targets:
            lay.addWidget(label("No targets yet. Add one and pick its colour from the game.", "muted"))
            return
        for i, t in enumerate(targets):
            r = QHBoxLayout()
            r.setSpacing(12)
            sw_col = swatch(t.color, 22)
            sw_col.setToolTip("Colour searched for: %s" % t.color)
            r.addWidget(sw_col)
            sw = ToggleSwitch(t.name)
            sw.setToolTip(tip("home_target"))
            sw.setChecked(t.enabled)
            sw.toggled.connect(lambda val, idx=i: self._toggle_target(idx, val))
            r.addWidget(sw, 1)
            r.addWidget(label("outline", "muted", wrap=False))
            out_col = swatch(t.outline_color, 22)
            out_col.setToolTip("Outline colour: %s" % t.outline_color)
            r.addWidget(out_col)
            lay.addLayout(r)

    def _toggle_target(self, idx, value):
        targets = self.cfg.profile.targets
        if 0 <= idx < len(targets):
            targets[idx].enabled = bool(value)
            self._refresh_target_names()
            for r in self._target_refreshers:
                r()
            self.settingsChanged.emit()

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
            self.cfg.profiles = {(name if k == old else k): val for k, val in self.cfg.profiles.items()}
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

    def _new_profile(self):
        name = self._ask_name("New profile", "Profile %d" % (len(self.cfg.profiles) + 1))
        if name:
            self.cfg.profiles[name] = Profile()
            self.cfg.active_profile = name
            self._reload_profiles()
            self.profileChanged.emit()
            self.settingsChanged.emit()

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

    def _add_target(self, pick=True):
        """New targets start switched off until their colour is picked, so nothing is outlined by accident."""
        self.cfg.profile.targets.append(Target(name="Target %d" % (len(self.cfg.profile.targets) + 1),
                                               enabled=False))
        self._reload_targets(select=len(self.cfg.profile.targets) - 1)
        self.settingsChanged.emit()
        if pick:
            self.status.setText("New target added. Click on the thing to outline; it switches on once its "
                                "colour is picked.")
            self.pickColourRequested.emit()

    def _add_armour(self):
        from .config import add_armour_targets
        added = add_armour_targets(self.cfg.profile)
        self._reload_targets(select=len(self.cfg.profile.targets) - 1)
        self.settingsChanged.emit()
        if not added:
            QMessageBox.information(self, APP_NAME, "This profile already has all the armour targets.")
            return
        off = [x.name for x in added if not x.enabled]
        QMessageBox.information(
            self, APP_NAME,
            "Added %d armour targets to \u201c%s\u201d.\n\n"
            "The colours are approximate. If armour is missed or the wrong things are outlined, select the target, "
            "press \u201cPick colour from the game\u201d and click on the armour, then check the live preview.%s"
            % (len(added), self.cfg.active_profile,
               ("\n\nSwitched off because grey also matches stone and similar blocks: %s. Switch them on to try them."
                % ", ".join(off)) if off else ""))

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
            self._add_target(pick=False)
            t = self._current_target()
        t.color, t.hue_tol, t.sat_min, t.val_min = values
        t.sat_max = t.val_max = 100
        t.enabled = True
        self._refresh_target_names()
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
            self.status.setText("Press Start, then click back into your game.")
        self._emit_preview()

    def set_status(self, text):
        self.status.setText(text)

    def set_saved(self, text):
        self.side_saved.setText(text)

    def show_result(self, res):
        det = self.cfg.profile.detection
        ai_on = det.enabled and det.model_path and any(e.enabled for e in det.entities)
        if not any(t.enabled for t in self.cfg.profile.targets) and not ai_on:
            self.status_title.setText("Running · no targets yet")
            self.status.setText("This profile has no switched-on targets. Go to Targets, press Add and click on "
                                "the thing you want outlined.")
        else:
            self.status_title.setText("Running · %d target%s in view" % (res.count, "" if res.count == 1 else "s"))
            self.status.setText("%.0f fps · %s · profile “%s”%s"
                                % (res.fps, self.watch_text(), self.cfg.active_profile,
                                   (" · " + res.capture) if res.capture else ""))
        if (res.ai_device, res.ai_error) != getattr(self, "_ai_state", (None, None)):
            self._ai_state = (res.ai_device, res.ai_error)
            self._refresh_ai(res.ai_device, res.ai_error)
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
