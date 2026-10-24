"""Wires the control panel, capture engine and assist window together."""
import argparse
import json
import os
import sys
import tempfile
import time
import traceback

import numpy as np
from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer
from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import APP_NAME, __version__, config, engine, ui, vision, winplat
from .panel import PAGES, Panel
from .pickers import ColourPicker, RegionPicker
from .view import AssistView

HOTKEY_ACTIONS = ["toggle_overlay", "next_profile", "toggle_outline"]
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def app_icon():
    for name in ("icon.ico", "icon.png"):
        path = os.path.join(ASSETS, name)
        if os.path.exists(path):
            return QIcon(path)
    return QIcon()


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            hid = winplat.hotkey_id_from_msg(message)
            if hid is not None:
                QTimer.singleShot(0, lambda: self.callback(hid))
                return True, 0
        return False, 0


class Controller:
    def __init__(self, app, cfg, path, interactive=True):
        self.app, self.cfg, self.path = app, cfg, path
        self.interactive = interactive
        self.engine = engine.Engine(cfg)
        ui.apply_theme(app, cfg.display.theme, cfg.display.ui_font_pt)
        self.panel = Panel(cfg, path)
        self.panel.setWindowIcon(app_icon())
        self.view = None
        self._placed_rect = None
        self._placed_at = 0.0
        self._hotkey_ids = []
        self._region_picker = None
        self._tray_hint_shown = False

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(700)
        self._save_timer.timeout.connect(self.save)

        p = self.panel
        p.startStop.connect(self.toggle)
        p.settingsChanged.connect(self._save_timer.start)
        p.displayModeChanged.connect(self.rebuild_view)
        p.profileChanged.connect(self.engine.reset_tracking)
        p.watchChanged.connect(self.engine.reset_tracking)
        p.previewChanged.connect(lambda i: setattr(self.engine, "preview_target", i))
        p.pickColourRequested.connect(self.pick_colour)
        p.pickRegionRequested.connect(self.pick_region)
        p.hotkeysApply.connect(self.register_hotkeys)
        p.themeChanged.connect(self.apply_theme)
        p.quitRequested.connect(self.quit)
        p.closeToTray.connect(self._closed_to_tray)
        self.engine.result.connect(self.on_result)
        self.engine.status.connect(self.on_status)

        self._filter = _HotkeyFilter(self.on_hotkey)
        app.installNativeEventFilter(self._filter)
        self.tray = self._make_tray()
        if interactive:
            p.show()
        self.register_hotkeys()
        if cfg.display.start_on_launch and interactive:
            QTimer.singleShot(300, self.start)

    # ---------- tray ----------
    def _make_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(app_icon(), self.app)
        tray.setToolTip(APP_NAME)
        menu = QMenu()
        show = QAction("Show %s" % APP_NAME, menu)
        show.triggered.connect(self.show_panel)
        self._tray_toggle = QAction("Start", menu)
        self._tray_toggle.triggered.connect(self.toggle)
        quit_ = QAction("Quit", menu)
        quit_.triggered.connect(self.quit)
        for a in (show, self._tray_toggle):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(quit_)
        tray.setContextMenu(menu)
        self._tray_menu = menu
        tray.activated.connect(lambda reason: self.show_panel()
                               if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        if self.interactive:
            tray.show()
        return tray

    def show_panel(self):
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _closed_to_tray(self):
        if self.tray and not self._tray_hint_shown:
            self.tray.showMessage(APP_NAME, "Still running here. Right-click the icon to quit.",
                                  QSystemTrayIcon.MessageIcon.Information, 4000)
            self._tray_hint_shown = True

    # ---------- run state ----------
    def start(self):
        if self.engine.running:
            return
        self._make_view()
        self.engine.start()
        self._set_running(True)
        self.panel.set_status("Starting...")

    def stop(self):
        self.engine.stop()
        if self.view:
            self.view.close()
            self.view = None
        self._set_running(False)

    def _set_running(self, running):
        self.panel.set_running(running)
        if self.tray:
            self._tray_toggle.setText("Stop" if running else "Start")
            self.tray.setToolTip("%s (%s)" % (APP_NAME, "running" if running else "stopped"))

    def toggle(self):
        self.stop() if self.engine.running else self.start()

    def rebuild_view(self):
        """Display settings changed: recreate the assist window if we are running."""
        if self.engine.running:
            self._make_view()

    def _make_view(self):
        if self.view:
            self.view.close()
            self.view = None
        self._placed_rect = None
        mirror = self.cfg.display.mode == "mirror"
        self.view = AssistView(self.cfg, mirror)
        self.view.setWindowIcon(app_icon())
        self.engine.want_frame = mirror
        if mirror:
            self.view.show()
            self.view.protect_from_capture()   # harmless if it fails; it only matters if it overlaps the game
            return
        # Overlay: show it tiny first so it has a native window, then hide it from screen capture.
        self.view.resize(1, 1)
        self.view.show()
        if not (self.view.protect_from_capture() and self._overlay_hidden_from_capture()):
            if winplat.IS_WIN:
                if self.interactive:
                    QMessageBox.warning(
                        self.panel, APP_NAME,
                        "Windows could not hide the overlay from screen capture (needs Windows 10 version 2004 "
                        "or newer). Without that the program would detect its own drawings, so it has switched "
                        "to the separate mirror window.")
                self.cfg.display.mode = "mirror"
                self.panel.refresh_all()
                self._make_view()

    def _overlay_hidden_from_capture(self):
        """Self-test: paint a patch on the overlay and confirm screen capture does not see it."""
        v = self.view
        mx, my, _, _ = engine.grab_monitor_rect(1)
        rect = (mx + 40, my + 40, 48, 48)
        v.test_colour = QColor(253, 0, 254)
        winplat.place_window(v, rect)
        v.repaint()
        for _ in range(4):
            self.app.processEvents()
            time.sleep(0.05)
        patch = engine.grab_rect(rect)
        v.test_colour = None
        winplat.place_window(v, (rect[0], rect[1], 1, 1))
        v.update()
        seen = (abs(patch.astype(int) - (254, 0, 253)).max(axis=2) <= 8).mean()
        return seen < 0.2

    # ---------- engine callbacks ----------
    def on_result(self, res):
        if not self.engine.running or self.view is None:
            return
        now = time.monotonic()
        if not self.view.mirror and (res.rect != self._placed_rect or now - self._placed_at > 1.0):
            # re-assert size and always-on-top every second (DPI changes, game window raised)
            winplat.place_window(self.view, res.rect)
            self._placed_rect, self._placed_at = res.rect, now
        self.view.message = ""
        self.view.set_result(res)
        self.panel.show_result(res)

    def on_status(self, text):
        if not self.engine.running and not text.startswith("Capture stopped"):
            return
        self.panel.set_status(text)
        if self.view:
            self.view.message = text
            self.view.set_result(None)
        if text.startswith("Capture stopped"):
            self.stop()
            self.panel.set_status(text)

    # ---------- pickers ----------
    def _frame_for_picking(self):
        if self.engine.running and self.engine.last_frame is not None:
            return self.engine.last_frame.copy()
        frame, _, msg = engine.grab_once(self.cfg)
        if frame is None:
            QMessageBox.information(self.panel, APP_NAME, msg or "Nothing to capture.")
        return frame

    def pick_colour(self):
        frame = self._frame_for_picking()
        if frame is None:
            return
        dlg = ColourPicker(frame, self.panel)
        if dlg.exec() and dlg.result_values:
            self.panel.apply_picked_colour(dlg.result_values)

    def pick_region(self):
        was_running = self.engine.running
        if self.view:
            self.view.hide()
        QApplication.processEvents()
        shot, mon = engine.grab_monitor(self.cfg.capture.monitor)
        picker = RegionPicker(shot, mon)

        def done(rect):
            if rect:
                self.cfg.capture.region = list(rect)
                self.cfg.capture.source = "region"
                self.panel.refresh_all()
                self.panel.show_region()
                self.engine.reset_tracking()
                self._save_timer.start()
            if self.view and was_running:
                self.view.show()
            self._region_picker = None
        picker.picked.connect(done)
        self._region_picker = picker
        picker.open()

    # ---------- hotkeys ----------
    def register_hotkeys(self):
        hwnd = int(self.panel.winId())
        for hid in self._hotkey_ids:
            winplat.unregister_hotkey(hwnd, hid)
        self._hotkey_ids = []
        if not winplat.IS_WIN:
            self.panel.hotkey_status.setText("Global hotkeys are only available on Windows.")
            return
        failed = []
        for i, action in enumerate(HOTKEY_ACTIONS, start=1):
            text = getattr(self.cfg.hotkeys, action).strip()
            if not text:
                continue
            if winplat.register_hotkey(hwnd, i, text):
                self._hotkey_ids.append(i)
            else:
                failed.append(text)
        self.panel.hotkey_status.setText(
            "All hotkeys active." if not failed else
            "Could not register: %s (invalid, or already used by another program)." % ", ".join(failed))

    def on_hotkey(self, hid):
        if not 1 <= hid <= len(HOTKEY_ACTIONS):
            return
        action = HOTKEY_ACTIONS[hid - 1]
        prof = self.cfg.profile
        if action == "toggle_overlay":
            self.toggle()
            return
        if action == "next_profile":
            names = list(self.cfg.profiles)
            nxt = names[(names.index(self.cfg.active_profile) + 1) % len(names)]
            self.panel.select_profile(nxt)
            if self.tray:
                self.tray.showMessage(APP_NAME, "Profile: %s" % nxt, QSystemTrayIcon.MessageIcon.NoIcon, 1500)
            return
        if action == "toggle_outline":
            prof.outline.enabled = not prof.outline.enabled
        self.panel.refresh_all()
        self._save_timer.start()

    # ---------- misc ----------
    def apply_theme(self):
        ui.apply_theme(self.app, self.cfg.display.theme, self.cfg.display.ui_font_pt)
        self.panel.restyle()

    def save(self):
        try:
            config.save(self.cfg, self.path)
            self.panel.set_saved("Settings saved")
        except OSError as exc:
            self.panel.set_saved("Could not save: %s" % exc)

    def quit(self):
        self._save_timer.stop()
        self.engine.stop()
        try:
            config.save(self.cfg, self.path)
        except OSError:
            pass
        hwnd = int(self.panel.winId())
        for hid in self._hotkey_ids:
            winplat.unregister_hotkey(hwnd, hid)
        if self.view:
            self.view.close()
        if self.tray:
            self.tray.hide()
        self.app.quit()


def _install_error_log(cfg_path):
    """Windowed builds have no console: write crashes to a log file and tell the user where it is."""
    log_path = os.path.join(os.path.dirname(cfg_path), "error.log")
    shown = []

    def hook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("%s %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), __version__, text))
        except OSError:
            pass
        if not shown and QApplication.instance():
            shown.append(True)
            QMessageBox.critical(None, APP_NAME, "Something went wrong:\n\n%s\n\nDetails were saved to:\n%s"
                                 % (value, log_path))
    sys.excepthook = hook


def run_selftest(out_path):
    """Non-interactive checks of a built app, used by the release pipeline on a real Windows machine."""
    report = {"app": APP_NAME, "version": __version__, "platform": sys.platform, "checks": {}}
    ok = [True]

    def check(name, fn, required):
        try:
            report["checks"][name] = {"ok": True, "detail": fn()}
        except Exception as exc:
            report["checks"][name] = {"ok": False, "detail": "%s: %s" % (type(exc).__name__, exc)}
            if required:
                ok[0] = False

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    cfg = config.default_config()
    path = os.path.join(tempfile.mkdtemp(), "config.json")
    holder = {}

    def vision_check():
        frame = np.full((240, 320, 3), 90, np.uint8)
        frame[60:140, 100:140] = vision.hex_to_bgr("#50C84B")
        blobs, _, _ = vision.detect(frame, cfg.profile.targets, cfg.profile.tracking, 1.0)
        assert len(blobs) == 1, blobs
        return "1 target found"

    def panel_check():
        holder["ctl"] = Controller(app, cfg, path, interactive=False)
        return "%d pages, %d profiles" % (len(PAGES), len(cfg.profiles))

    def engine_check():
        frame = np.full((360, 640, 3), 90, np.uint8)
        frame[100:200, 300:340] = vision.hex_to_bgr("#50C84B")
        holder["ctl"].engine.want_frame = True
        res = holder["ctl"].engine.process(frame, (0, 0, 640, 360))
        assert res.count == 1 and res.frame_img is not None
        return "processed one frame"

    def overlay_check():
        ctl = holder["ctl"]
        ctl.view = AssistView(cfg, False)
        ctl.view.resize(1, 1)
        ctl.view.show()
        protected = ctl.view.protect_from_capture()
        hidden = ctl._overlay_hidden_from_capture() if protected else None
        ctl.view.close()
        ctl.view = None
        return {"exclude_api_accepted": protected, "hidden_in_capture": hidden}

    check("vision", vision_check, True)
    check("control_panel", panel_check, True)
    check("engine", engine_check, True)
    check("monitors", engine.monitor_names, False)
    check("screen_grab", lambda: list(engine.grab_monitor(1)[0].shape), False)
    check("overlay_capture_exclusion", overlay_check, False)
    check("hotkeys", lambda: holder["ctl"].panel.hotkey_status.text(), False)
    check("window_list", lambda: ["%s | %s" % (w["title"][:40], w["exe"]) for w in winplat.list_windows()][:8], False)
    check("window_search", lambda: str(winplat.find_window("no-such-window-%d" % os.getpid())), False)
    check("config_save", lambda: (config.save(cfg, path), os.path.getsize(path))[1], True)
    report["ok"] = ok[0]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    if "ctl" in holder:
        holder["ctl"].quit()
    return 0 if ok[0] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog=APP_NAME, description="Low-vision colour highlighting overlay.")
    ap.add_argument("--config", default=config.default_path(), help="settings file (JSON)")
    ap.add_argument("--reset", action="store_true", help="ignore the saved settings and start from defaults")
    ap.add_argument("--selftest", metavar="REPORT.json", help="run non-interactive checks and exit")
    args = ap.parse_args(argv)
    winplat.set_app_id("EQQX0.%s" % APP_NAME)
    if args.selftest:
        return run_selftest(args.selftest)
    winplat.hold_running_mutex()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    _install_error_log(args.config)
    cfg = config.default_config() if args.reset else config.load(args.config)
    ctl = Controller(app, cfg, args.config)
    app._controller = ctl  # keep alive
    return app.exec()
