# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private local connection between the `mct` command-line tool and a running MineColorTrack.

Windows uses a named pipe, other systems a Unix socket. Every connection must prove it knows a random key stored
next to the settings file, so only the same Windows user can control the app.
"""
import getpass
import os
import re
import secrets
import sys
import tempfile
import threading
from multiprocessing.connection import Client, Listener


class NotRunning(Exception):
    pass


def address():
    user = re.sub(r"[^A-Za-z0-9_.-]", "_", getpass.getuser() or "user")
    if sys.platform == "win32":
        return r"\\.\pipe\MineColorTrack-" + user
    return os.path.join(tempfile.gettempdir(), "minecolortrack-%s.sock" % user)


def key_path(config_path):
    return os.path.join(os.path.dirname(os.path.abspath(config_path)), "cli.key")


def load_key(config_path, create=False):
    path = key_path(config_path)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            key = fh.read()
        if len(key) >= 16:
            return key
    if not create:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = secrets.token_bytes(32)
    with open(path, "wb") as fh:
        fh.write(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def request(config_path, cmd, args=None, timeout=20.0):
    """Send one command to the running app. Raises NotRunning if there is none."""
    key = load_key(config_path)
    if key is None:
        raise NotRunning("MineColorTrack is not running.")
    addr = address()
    if sys.platform != "win32" and not os.path.exists(addr):
        raise NotRunning("MineColorTrack is not running.")
    try:
        conn = Client(addr, family="AF_PIPE" if sys.platform == "win32" else "AF_UNIX", authkey=key)
    except (OSError, EOFError):
        raise NotRunning("MineColorTrack is not running.")
    try:
        conn.send({"cmd": cmd, "args": args or {}})
        if not conn.poll(timeout):
            raise TimeoutError("MineColorTrack did not answer in time.")
        reply = conn.recv()
    finally:
        conn.close()
    if isinstance(reply, dict) and reply.get("error"):
        raise RuntimeError(reply["error"])
    return reply.get("result") if isinstance(reply, dict) else reply


def is_running(config_path):
    try:
        request(config_path, "ping", timeout=3.0)
        return True
    except Exception:
        return False


class Server:
    """Accepts commands on a background thread; `handler(cmd, args)` must be thread-safe (the app hands the
    call to its GUI thread)."""

    def __init__(self, config_path, handler):
        self.config_path = config_path
        self.handler = handler
        self.key = load_key(config_path, create=True)
        self.addr = address()
        self.listener = None
        self._stop = False
        self._thread = None

    def start(self):
        family = "AF_PIPE" if sys.platform == "win32" else "AF_UNIX"
        if family == "AF_UNIX" and os.path.exists(self.addr):
            os.remove(self.addr)                    # stale socket from a crashed run
        self.listener = Listener(self.addr, family=family, authkey=self.key)
        self._thread = threading.Thread(target=self._loop, name="MineColorTrackCLI", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop:
            try:
                conn = self.listener.accept()
            except Exception:                       # wrong key, or closing
                if self._stop:
                    return
                continue
            try:
                if self._stop:
                    return
                req = conn.recv()
                try:
                    result = self.handler(req.get("cmd"), req.get("args") or {})
                    conn.send({"result": result})
                except Exception as exc:
                    conn.send({"error": str(exc)})
            except Exception:
                pass
            finally:
                conn.close()

    def stop(self):
        if self.listener is None:
            return
        self._stop = True
        try:                                        # wake up accept()
            Client(self.addr, family="AF_PIPE" if sys.platform == "win32" else "AF_UNIX", authkey=self.key).close()
        except Exception:
            pass
        try:
            self.listener.close()
        except Exception:
            pass
        self.listener = None
