"""Wires the control panel, capture engine and assist window together."""
import argparse
import sys
import time

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import config, engine, winplat
from .panel import Panel
from .pickers import ColourPicker, RegionPicker
from .view import AssistView

HOTKEY_ACTIONS = ["toggle_overlay", "next_profile", "toggle_outline", "toggle_contrast", "toggle_magnifier"]


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
    def __init__(self, app, cfg, path):
        self.app, self.cfg, self.path = app, cfg, path
        self.engine = engine.Engine(cfg)
        self.panel = Panel(cfg, path)
        self.view = None
        self._placed_rect = None
        self._placed_at = 0.0
        self._hotkey_ids = []
        self._region_picker = None

        self.apply_font()
        p = self.panel
        p.startStop.connect(self.toggle)
        p.displayModeChanged.connect(self.rebuild_view)
        p.profileChanged.connect(self.engine.reset_tracking)
        p.previewChanged.connect(lambda i: setattr(self.engine, "preview_target", i))
        p.pickColourRequested.connect(self.pick_colour)
        p.pickRegionRequested.connect(self.pick_region)
        p.hotkeysApply.connect(self.register_hotkeys)
        p.saveRequested.connect(self.save)
        p.fontChanged.connect(self.apply_font)
        p.quitRequested.connect(self.quit)
        self.engine.result.connect(self.on_result)
        self.engine.status.connect(self.on_status)

        self._filter = _HotkeyFilter(self.on_hotkey)
        app.installNativeEventFilter(self._filter)
        p.show()
        self.register_hotkeys()
        if cfg.display.start_on_launch:
            QTimer.singleShot(300, self.start)

    # ---------- run state ----------
    def start(self):
        if self.engine.running:
            return
        self._make_view()
        self.engine.start()
        self.panel.set_running(True)
        self.panel.set_status("Starting...")

    def stop(self):
        self.engine.stop()
        if self.view:
            self.view.close()
            self.view = None
        self.panel.set_running(False)
        self.panel.set_status("Stopped.")

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
                QMessageBox.warning(
                    self.panel, "ColorAssist",
                    "Windows could not hide the overlay from screen capture (needs Windows 10 version 2004 "
                    "or newer). Without that the program would detect its own drawings, so it has switched "
                    "to the separate mirror window.")
                self.cfg.display.mode = "mirror"
                self.panel._refresh_all()
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
            QMessageBox.information(self.panel, "ColorAssist", msg or "Nothing to capture.")
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
                self.panel._refresh_all()
                self.panel.show_region()
                self.engine.reset_tracking()
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
        elif action == "next_profile":
            names = list(self.cfg.profiles)
            nxt = names[(names.index(self.cfg.active_profile) + 1) % len(names)]
            self.panel.select_profile(nxt)
        elif action == "toggle_outline":
            prof.outline.enabled = not prof.outline.enabled
        elif action == "toggle_contrast":
            prof.contrast.enabled = not prof.contrast.enabled
        elif action == "toggle_magnifier":
            prof.magnifier.enabled = not prof.magnifier.enabled
        self.panel._refresh_all()

    # ---------- misc ----------
    def apply_font(self):
        f = QFont(self.app.font())
        f.setPointSize(int(self.cfg.display.ui_font_pt))
        self.app.setFont(f)

    def save(self):
        try:
            config.save(self.cfg, self.path)
            self.panel.set_status("Settings saved to %s" % self.path)
        except OSError as exc:
            QMessageBox.warning(self.panel, "ColorAssist", "Could not save settings: %s" % exc)

    def quit(self):
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
        self.app.quit()


def main(argv=None):
    ap = argparse.ArgumentParser(description="ColorAssist: low-vision colour highlighting overlay.")
    ap.add_argument("--config", default=config.default_path(), help="settings file (JSON)")
    ap.add_argument("--reset", action="store_true", help="ignore the saved settings and start from defaults")
    args = ap.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ColorAssist")
    app.setQuitOnLastWindowClosed(False)
    cfg = config.default_config() if args.reset else config.load(args.config)
    ctl = Controller(app, cfg, args.config)
    app._controller = ctl  # keep alive
    return app.exec()
