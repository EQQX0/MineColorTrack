# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""The `mct` command-line tool: file mode, validation, and live control of a running app."""
import io
import json
import os
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path[:0] = [os.path.join(os.path.dirname(__file__), ".."), os.path.dirname(__file__)]

from colorassist import cli, config, ipc  # noqa: E402
from scene import make_scene  # noqa: E402


def run(cfg_path, *args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(["--config", cfg_path, "--offline", *args])
    text = out.getvalue() or err.getvalue()
    try:
        return code, json.loads(text)
    except ValueError:
        return code, text


@pytest.fixture
def cfg_path(tmp_path):
    return str(tmp_path / "config.json")


def test_get_set_and_validation(cfg_path):
    code, res = run(cfg_path, "set", "capture.fps", "120")
    assert code == 0 and res["value"] == 120 and res["applied_live"] is False
    assert run(cfg_path, "get", "capture.fps")[1]["value"] == 120
    assert config.load(cfg_path).capture.fps == 120
    code, res = run(cfg_path, "set", "capture.fps", "500")
    assert code == 1 and "between 5 and 120" in res["error"]
    code, res = run(cfg_path, "set", "display.theme", "purple")
    assert code == 1 and "one of" in res["error"]
    code, res = run(cfg_path, "set", "outline.color", "00ff00")
    assert code == 0 and res["value"] == "#00FF00"
    assert run(cfg_path, "set", "outline.blink", "yes")[1]["value"] is True
    assert run(cfg_path, "set", "nope.x", "1")[0] == 1


def test_schema_lists_every_setting_with_help():
    sch = cli.schema()
    keys = {s["key"]: s for s in sch["settings"]}
    assert keys["capture.fps"]["max"] == 120 and keys["capture.method"]["choices"] == ["auto", "fast", "compatible"]
    assert keys["outline.thickness"]["scope"] == "profile" and keys["target.hue_tol"]["scope"] == "target"
    missing = [k for k, s in keys.items() if not s.get("help") and not k.startswith(("entity.", "target.name",
                                                                                     "capture.region", "capture.source"))]
    assert len(missing) < 12, missing


def test_profiles_targets_and_detect(cfg_path, tmp_path):
    assert run(cfg_path, "profile", "new", "Night")[1]["active"] == "Night"
    assert run(cfg_path, "profile", "copy", "Night", "Night 2")[0] == 0
    assert run(cfg_path, "profile", "rename", "Night 2", "Caves")[0] == 0
    assert set(run(cfg_path, "profile", "list")[1]["profiles"][i]["name"] for i in range(3)) == \
        {"My profile", "Night", "Caves"}
    assert run(cfg_path, "profile", "delete", "Caves")[0] == 0

    img_path = str(tmp_path / "scene.png")
    import cv2
    cv2.imwrite(img_path, make_scene())
    code, res = run(cfg_path, "target", "pick", "Creeper", img_path, "384", "140")
    assert code == 0 and res["targets"][0]["name"] == "Creeper" and res["targets"][0]["enabled"]
    code, res = run(cfg_path, "detect", img_path, "--out", str(tmp_path / "marked.png"))
    assert code == 0 and res["found"] == 2 and os.path.exists(res["marked_image"])
    assert run(cfg_path, "target", "set", "Creeper", "min_area", "500")[0] == 0
    assert run(cfg_path, "detect", img_path)[1]["found"] == 1               # the small far creeper is filtered
    assert run(cfg_path, "target", "add", "Pig", "--color", "#F0A0A0", "--outline", "#00FFFF")[0] == 0
    assert run(cfg_path, "target", "set", "Pig", "hue_tol", "999")[0] == 1
    assert run(cfg_path, "target", "remove", "Pig")[0] == 0
    assert [t["name"] for t in run(cfg_path, "target", "list")[1]["targets"]] == ["Creeper"]


def test_watch_model_and_dataset(cfg_path, tmp_path):
    assert run(cfg_path, "watch", "monitor", "2")[1]["watching"] == {"source": "monitor", "monitor": 2}
    assert run(cfg_path, "watch", "region", "10", "20", "640", "360")[1]["watching"]["region"] == [10, 20, 640, 360]
    assert run(cfg_path, "watch", "window", "--title", "Minecraft", "--exe", "Minecraft.Windows.exe")[0] == 0
    assert config.load(cfg_path).capture.window_exe == "Minecraft.Windows.exe"

    pytest.importorskip("onnx")
    import fake_model
    model = fake_model.build(str(tmp_path / "m.onnx"))
    code, res = run(cfg_path, "model", "load", model)
    assert code == 0 and [e["name"] for e in res["entities"]] == ["pig", "villager"] and res["enabled"]
    assert run(cfg_path, "entity", "set", "villager", "enabled", "false")[1]["entity"]["enabled"] is False
    assert run(cfg_path, "model", "load", str(tmp_path / "missing.onnx"))[0] == 1

    run(cfg_path, "set", "ai.dataset_dir", str(tmp_path / "ds"))
    assert run(cfg_path, "dataset", "add-class", "player")[1]["classes"] == ["player"]
    info = run(cfg_path, "dataset", "info")[1]
    assert info["images"] == 0 and info["classes"] == ["player"]


def test_app_commands_need_running_app(cfg_path):
    code, res = run(cfg_path, "stop")
    assert code == 1 and "not running" in res["error"]


def test_live_control_of_running_app(tmp_path):
    from PyQt6.QtWidgets import QApplication
    from colorassist.app import Controller
    app = QApplication.instance() or QApplication([])
    path = str(tmp_path / "live" / "config.json")
    cfg = config.default_config()
    ctl = Controller(app, cfg, path, interactive=False)
    ctl.ipc = ipc.Server(path, ctl._command_from_cli)
    ctl.ipc.start()
    results = {}

    def client():
        def call(*args):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(out):
                code = cli.main(["--config", path, *args])
            return code, json.loads(out.getvalue())
        results["status"] = call("status")
        results["set"] = call("set", "outline.thickness", "9")
        results["target"] = call("target", "add", "Pig", "--color", "#F0A0A0")
        results["toggle"] = call("toggle-outline")
    t = threading.Thread(target=client)
    t.start()
    while t.is_alive():
        app.processEvents()
        t.join(0.01)
    ctl.ipc.stop()
    assert results["status"][1]["running"] is True and results["status"][1]["active_profile"] == "My profile"
    assert results["set"][1]["applied_live"] is True
    assert cfg.profile.outline.thickness == 9                                  # changed in the running app
    assert [x.name for x in cfg.profile.targets] == ["Pig"]
    assert results["toggle"][1]["outline_enabled"] is False and cfg.profile.outline.enabled is False
    assert config.load(path).profile.outline.thickness == 9                   # and saved
    ctl.panel.close()


def test_ai_device_setting(cfg_path):
    keys = {s["key"]: s for s in cli.schema()["settings"]}
    assert keys["ai.device"]["choices"] == ["auto", "tensorrt", "cuda", "directml", "cpu"]
    assert keys["ai.device"]["default"] == "auto" and keys["ai.tensorrt_fp16"]["default"] is True
    assert keys["ai.device"]["help"] and keys["ai.tensorrt_fp16"]["help"]
    assert "ai.prefer_gpu" not in keys
    assert run(cfg_path, "get", "ai.device")[1]["value"] == "auto"
    code, res = run(cfg_path, "set", "ai.device", "tensorrt")
    assert code == 0 and res["value"] == "tensorrt" and config.load(cfg_path).ai.device == "tensorrt"
    code, res = run(cfg_path, "set", "ai.device", "gpu")
    assert code == 1 and "auto, tensorrt, cuda, directml, cpu" in res["error"]
    assert run(cfg_path, "set", "ai.tensorrt_fp16", "off")[1]["value"] is False


def test_old_graphics_card_switch_becomes_ai_device():
    assert config.from_dict({"version": 2, "ai": {"prefer_gpu": False}}).ai.device == "cpu"
    assert config.from_dict({"version": 2, "ai": {"prefer_gpu": True}}).ai.device == "auto"
    assert config.from_dict({"version": 2, "ai": {"prefer_gpu": False, "device": "cuda"}}).ai.device == "cuda"
    assert config.from_dict({"version": 2, "ai": {"device": "quantum"}}).ai.device == "auto"
