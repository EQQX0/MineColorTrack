# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Update check against simulated GitHub answers (no network)."""
import io
import json
import os
import sys
import urllib.error

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from colorassist import __version__, updater  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def fake_github(monkeypatch, tag="v99.0.0", status=200, asset=True, payload=b"x" * 1000):
    def urlopen(req, timeout=None):
        url = req.full_url
        if status != 200:
            raise urllib.error.HTTPError(url, status, "err", {}, None)
        if url.endswith("/releases/latest"):
            body = {"tag_name": tag, "html_url": "https://github.com/x/y/releases/tag/" + tag, "body": "notes",
                    "assets": ([{"name": "MineColorTrack-Setup-%s.exe" % tag.lstrip("v"),
                                 "browser_download_url": "https://example/setup.exe", "size": len(payload)}]
                               if asset else [])}
            return FakeResponse(json.dumps(body).encode())
        return FakeResponse(payload)
    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)


def test_versions():
    assert updater.parse_version("v1.10.2") == (1, 10, 2)
    assert updater.parse_version("2") == (2, 0, 0)
    assert updater.is_newer("1.10.0", "1.9.9") and not updater.is_newer("1.5.0", "1.5.0")
    assert not updater.is_newer("v1.4.9", "1.5.0")


def test_check_finds_newer_release_and_installer(monkeypatch):
    fake_github(monkeypatch)
    info = updater.check()
    assert info["newer"] and info["latest"] == "99.0.0" and info["current"] == __version__
    assert info["installer"]["name"] == "MineColorTrack-Setup-99.0.0.exe"


def test_same_version_is_not_newer(monkeypatch):
    fake_github(monkeypatch, tag="v" + __version__)
    assert updater.check()["newer"] is False


def test_private_repo_gives_clear_message(monkeypatch):
    fake_github(monkeypatch, status=404)
    with pytest.raises(updater.UpdateError, match="public"):
        updater.check()


def test_download_checks_size(monkeypatch, tmp_path):
    fake_github(monkeypatch, payload=b"abc" * 100)
    info = updater.check()
    seen = []
    path = updater.download(info["installer"], progress=lambda d, t: seen.append((d, t)), folder=str(tmp_path))
    assert os.path.getsize(path) == 300 and seen[-1] == (300, 300)
    info["installer"]["size"] = 999
    with pytest.raises(updater.UpdateError, match="incomplete"):
        updater.download(info["installer"], folder=str(tmp_path))


def test_banner_and_skip(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QApplication
    from colorassist import config, ui
    from colorassist.panel import Panel
    app = QApplication.instance() or QApplication([])
    ui.apply_theme(app, "dark", 12)
    p = Panel(config.default_config(), str(tmp_path / "c.json"))
    p.show()
    fake_github(monkeypatch)
    p.show_update(updater.check())
    assert p.update_card.isVisible() and "99.0.0" in p.update_text.text()
    p._skip_update()
    assert p.cfg.updates.skip_version == "99.0.0" and not p.update_card.isVisible()
    p.show_update(updater.check())                       # automatic check: skipped version stays hidden
    assert not p.update_card.isVisible()
    p.show_update(updater.check(), manual=True)          # "Check now" still shows it
    assert p.update_card.isVisible()
    p.close()


def test_cli_update_check(monkeypatch, tmp_path, capsys):
    from colorassist import cli
    fake_github(monkeypatch)
    assert cli.main(["--config", str(tmp_path / "c.json"), "--offline", "update", "check"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["newer"] and "notes" not in out
