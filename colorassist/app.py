# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wires the control panel, capture engine and assist window together."""
import argparse
from dataclasses import asdict
import threading
import json
import logging
import os
import sys
import tempfile
import time
import traceback

import numpy as np
from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QProgressDialog, QSystemTrayIcon

from . import APP_NAME, __version__, capture, config, dataset, detector, engine, ipc, ui, updater, vision, winplat
from .panel import PAGES, Panel
from .pickers import ColourPicker, RegionPicker
from .view import AssistView

HOTKEY_ACTIONS = ["toggle_overlay", "next_profile", "toggle_outline", "save_screenshot"]
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


class _Bridge(QObject):
    """Hands command-line requests from the connection thread to the GUI thread."""
    call = pyqtSignal(object)


class _UpdateBridge(QObject):
    """Results of the background update check and download, delivered on the GUI thread."""
    checked = pyqtSignal(object, bool)
    failed = pyqtSignal(str, bool)
    progress = pyqtSignal(int, int)
    downloaded = pyqtSignal(str)
    download_failed = pyqtSignal(str)


class Controller:
    def __init__(self, app, cfg, path, interactive=True, start_now=False):
        self.app, self.cfg, self.path = app, cfg, path
        self.interactive = interactive
        self.engine = engine.Engine(cfg, config.trt_cache_dir(path))
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
        p.labelerRequested.connect(self.open_labeler)
        p.updateRequested.connect(self.update_now)
        p.updateCheckRequested.connect(lambda: self.check_updates(manual=True))
        self._upd = _UpdateBridge()
        self._upd.checked.connect(self._update_checked)
        self._upd.failed.connect(self._update_failed)
        self._upd.progress.connect(self._update_progress)
        self._upd.downloaded.connect(self._update_downloaded)
        self._upd.download_failed.connect(self._update_download_failed)
        self._progress = None
        self.labeler = None
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
        self.last_status = {}
        self._bridge = _Bridge()
        self._bridge.call.connect(self._run_command)
        self.ipc = None
        if interactive:
            self.ipc = ipc.Server(path, self._command_from_cli)
            try:
                self.ipc.start()
            except OSError:
                self.ipc = None          # another copy owns the connection; the CLI talks to that one
        if interactive and cfg.updates.check_on_start:
            QTimer.singleShot(4000, self.check_updates)
        if (cfg.display.start_on_launch or start_now) and interactive:
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
        if not any(t.enabled for t in self.cfg.profile.targets):
            self.panel.set_status("Running, but this profile has no targets yet. Go to Targets and press Add.")
        else:
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
        try:
            patch = engine.grab_rect(rect, self.cfg.capture.method)
        except Exception:
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
        timings = dict(res.timings)
        timings["draw"] = round(timings.get("draw", 0.0) + self.view.paint_ms, 2)
        self.panel.show_timings(timings)
        self.last_status = {"fps": round(res.fps, 1), "targets_in_view": res.count, "capture": res.capture,
                            "ai_device": res.ai_label or res.ai_device, "ai_problem": res.ai_error,
                            "ai_status": res.ai_status, "ai_notice": res.ai_notice, "timings_ms": timings,
                            "area": list(res.rect)}

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

    # ---------- labelling ----------
    def grab_for_labelling(self):
        """(frame, message): the latest watched picture, or a fresh grab if not running."""
        if self.engine.running and self.engine.last_frame is not None:
            return self.engine.last_frame.copy(), None
        frame, _, msg = engine.grab_once(self.cfg)
        return frame, msg

    def save_screenshot(self):
        frame, msg = self.grab_for_labelling()
        if frame is None:
            if self.tray:
                self.tray.showMessage(APP_NAME, msg or "Nothing to capture.", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return {"saved": False, "problem": msg or "Nothing to capture."}
        try:
            ds = dataset.Dataset(self.panel.dataset_root())
            stem = ds.add_image(frame)
        except OSError as exc:
            if self.tray:
                self.tray.showMessage(APP_NAME, "Could not save: %s" % exc, QSystemTrayIcon.MessageIcon.Warning, 3000)
            return {"saved": False, "problem": str(exc)}
        if self.labeler is not None and self.labeler.isVisible():
            self.labeler.add_captured(stem)
        if self.tray:
            self.tray.showMessage(APP_NAME, "Screenshot saved for labelling (%d in total)." % len(ds.images()),
                                  QSystemTrayIcon.MessageIcon.NoIcon, 1500)
        return {"saved": True, "file": ds.image_path(stem), "total": len(ds.images())}

    def open_labeler(self):
        from .labeler import Labeler
        root = self.panel.dataset_root()
        if self.labeler is None or self.labeler.ds.root != root:
            if self.labeler is not None:
                self.labeler.close()
            self.labeler = Labeler(root, self.grab_for_labelling)
            self.labeler.setWindowIcon(app_icon())
            self.labeler.datasetChanged.connect(self.panel.set_dataset_dir)
        self.labeler.show()
        self.labeler.raise_()
        self.labeler.activateWindow()

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
        if action == "save_screenshot":
            self.save_screenshot()
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

    # ---------- updates ----------
    def check_updates(self, manual=False):
        if manual:
            self.panel.show_update_problem("Checking...")

        def work():
            try:
                self._upd.checked.emit(updater.check(), manual)
            except Exception as exc:
                self._upd.failed.emit(str(exc), manual)
        threading.Thread(target=work, name="MineColorTrackUpdateCheck", daemon=True).start()

    def _update_checked(self, info, manual):
        self.panel.show_update(info, manual)
        if manual and not info.get("newer"):
            self.panel.set_status("You have the newest version (%s)." % info["current"])
        elif manual:
            self.panel.go("Home")

    def _update_failed(self, text, manual):
        self.panel.show_update_problem(text)
        if manual:
            QMessageBox.information(self.panel, APP_NAME, "Could not check for updates.\n\n%s" % text)

    def update_now(self):
        info = getattr(self.panel, "_update_info", None)
        if not info or not info.get("newer"):
            self.check_updates(manual=True)
            return
        if not winplat.IS_WIN:
            QMessageBox.information(self.panel, APP_NAME, "Updating is only possible on Windows.")
            return
        if not info.get("installer"):
            QMessageBox.information(self.panel, APP_NAME, "This release has no installer yet. Opening its page.")
            self.panel._open_update_notes()
            return
        self._progress = QProgressDialog("Downloading MineColorTrack %s..." % info["latest"], "Cancel", 0, 100,
                                         self.panel)
        self._progress.setWindowTitle(APP_NAME)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(0)
        self._cancel_download = False
        self._progress.canceled.connect(lambda: setattr(self, "_cancel_download", True))

        def work():
            def progress(done, total):
                if self._cancel_download:
                    raise updater.UpdateError("Cancelled.")
                self._upd.progress.emit(done, total)
            try:
                self._upd.downloaded.emit(updater.download(info["installer"], progress))
            except Exception as exc:
                self._upd.download_failed.emit(str(exc))
        threading.Thread(target=work, name="MineColorTrackUpdateDownload", daemon=True).start()

    def _update_progress(self, done, total):
        if self._progress and total:
            self._progress.setValue(int(done * 100 / total))

    def _update_download_failed(self, text):
        if self._progress:
            self._progress.close()
        if text != "Cancelled.":
            QMessageBox.warning(self.panel, APP_NAME, "The update could not be downloaded.\n\n%s" % text)

    def _update_downloaded(self, path):
        if self._progress:
            self._progress.close()
        if QMessageBox.question(self.panel, APP_NAME, "The update is ready. MineColorTrack will close, update and "
                                "open again. Your settings are kept.\n\nInstall now?") \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            winplat.release_running_mutex()
            updater.run_installer(path)
        except Exception as exc:
            QMessageBox.warning(self.panel, APP_NAME, "Could not start the installer: %s" % exc)
            return
        self.quit()

    # ---------- command-line control (mct) ----------
    def _command_from_cli(self, cmd, args):
        """Runs on the connection thread: pass the request to the GUI thread and wait for the answer."""
        job = {"cmd": cmd, "args": args, "done": threading.Event()}
        self._bridge.call.emit(job)
        if not job["done"].wait(20):
            raise TimeoutError("MineColorTrack is busy.")
        if "error" in job:
            raise RuntimeError(job["error"])
        return job["result"]

    def _run_command(self, job):
        try:
            job["result"] = self.handle_command(job["cmd"], job["args"])
        except Exception as exc:
            job["error"] = str(exc)
        finally:
            job["done"].set()

    def handle_command(self, cmd, args):
        if cmd == "ping":
            return {"version": __version__, "pid": os.getpid()}
        if cmd == "get_config":
            return asdict(self.cfg)
        if cmd == "set_config":
            return self.apply_settings(args)
        if cmd != "action":
            raise ValueError("Unknown command %r" % cmd)
        name = args.get("name")
        if name == "status":
            info = {"watching_active": self.engine.running, "active_profile": self.cfg.active_profile,
                    "watching": self.panel.watch_text(), "outline_enabled": self.cfg.profile.outline.enabled,
                    "display": self.cfg.display.mode}
            if self.engine.running:
                info.update(self.last_status)
            return info
        if name == "start":
            self.start()
        elif name == "stop":
            self.stop()
        elif name == "toggle_outline":
            prof = self.cfg.profile
            prof.outline.enabled = not prof.outline.enabled
            self.panel.refresh_all()
            self._save_timer.start()
            return {"outline_enabled": prof.outline.enabled}
        elif name == "screenshot":
            return self.save_screenshot()
        elif name == "show":
            self.show_panel()
        elif name == "quit":
            QTimer.singleShot(150, self.quit)
            return {"quitting": True}
        else:
            raise ValueError("Unknown action %r" % name)
        return {"ok": True, "watching_active": self.engine.running}

    def apply_settings(self, data):
        """Replace all settings with ones sent by `mct`, and update everything that depends on them."""
        new = config.from_dict(data)
        before = (self.cfg.display.mode, self.cfg.display.mirror_on_top, self.cfg.display.theme,
                  self.cfg.display.ui_font_pt, asdict(self.cfg.hotkeys), self.cfg.active_profile,
                  asdict(self.cfg.capture))
        config.replace_in_place(self.cfg, new)
        d = self.cfg.display
        self.panel._reload_profiles()
        if (d.theme, d.ui_font_pt) != before[2:4]:
            self.apply_theme()
        if asdict(self.cfg.hotkeys) != before[4]:
            self.register_hotkeys()
        if (d.mode, d.mirror_on_top) != before[0:2]:
            self.rebuild_view()
        if self.cfg.active_profile != before[5] or asdict(self.cfg.capture) != before[6]:
            self.engine.reset_tracking()
        self.save()
        return {"ok": True}

    def quit(self):
        if self.ipc:
            self.ipc.stop()
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
    try:                    # warnings such as an AI device that could not start go to the same file
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8", delay=True)
        handler.setFormatter(logging.Formatter("%(asctime)s " + __version__ + " %(levelname)s %(name)s: %(message)s",
                                               "%Y-%m-%d %H:%M:%S"))
        log = logging.getLogger("minecolortrack")
        log.addHandler(handler)
        log.setLevel(logging.WARNING)
    except OSError:
        pass

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


def run_selftest(out_path, model_path=None):
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

    cfg.profile.targets.append(config.Target(name="Self-test", color="#50C84B"))

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
        out = {"exclude_api_accepted": protected}
        for method in ("compatible", "fast"):
            cfg.capture.method = method
            out["hidden_from_" + method] = ctl._overlay_hidden_from_capture() if protected else None
        cfg.capture.method = "auto"
        ctl.view.close()
        ctl.view = None
        return out

    def capture_check():
        rect = engine.grab_monitor_rect(1)
        rect = (rect[0], rect[1], min(1920, rect[2]), min(1080, rect[3]))
        out = {"area": list(rect), "fast_library": capture.fast_available()}
        for method in ("compatible", "auto"):
            cap = capture.get(method)
            ms = capture.benchmark(cap, rect, 20)
            out[method] = {"used": cap.name, "ms_per_frame": round(ms, 2), "max_fps": round(1000 / max(ms, 1e-3)),
                           "problem": cap.problem}
        return out
    check("capture_speed", capture_check, False)

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
    check("update_check", lambda: {k: v for k, v in updater.check().items() if k != "notes"}, False)

    def ai_check():
        info = {"runtime": detector.available()}
        if detector.ort is not None:
            info["providers"] = detector.ort.get_available_providers()
        if model_path:
            frame = np.full((480, 640, 3), 120, np.uint8)
            for device in ("auto", "cpu"):
                det = detector.Detector(model_path, device=device)
                found = det.detect(frame, conf=0.3)
                info[device] = {"device": det.device_label, "classes": det.names, "detections": len(found),
                                "skipped": [k for k, _ in det.fallbacks], "notice": det.notice}
        return info
    check("ai_model", ai_check, bool(model_path))

    def labeler_check():
        from .labeler import Labeler
        root = os.path.join(tempfile.mkdtemp(), "dataset")
        lab = Labeler(root, lambda: (np.full((360, 640, 3), 90, np.uint8), None))
        lab.ds.add_class("player")
        lab.capture()
        lab.ds.save_boxes(lab.current, [(0, 0.5, 0.5, 0.2, 0.4)])
        lab.capture()
        lab.mark_background()
        zpath = os.path.join(os.path.dirname(root), "export.zip")
        info = lab.ds.export_zip(zpath)
        lab.close()
        return info
    check("labelling_tool", labeler_check, True)
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
    ap.add_argument("--selftest-model", metavar="MODEL.onnx", help="also load and run this AI model in the self-test")
    ap.add_argument("--start", action="store_true", help="start watching right away")
    args = ap.parse_args(argv)
    winplat.set_app_id("EQQX0.%s" % APP_NAME)
    if args.selftest:
        return run_selftest(args.selftest, args.selftest_model)
    if ipc.is_running(args.config):                 # already open: bring it forward instead of a second copy
        try:
            ipc.request(args.config, "action", {"name": "show"})
            if args.start:
                ipc.request(args.config, "action", {"name": "start"})
        except Exception:
            pass
        return 0
    winplat.hold_running_mutex()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    _install_error_log(args.config)
    cfg = config.default_config() if args.reset else config.load(args.config)
    ctl = Controller(app, cfg, args.config, start_now=args.start)
    app._controller = ctl  # keep alive
    return app.exec()
