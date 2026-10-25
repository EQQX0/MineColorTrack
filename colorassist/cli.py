# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""`mct`: command-line control of MineColorTrack for people and AI agents.

Every command prints JSON. If MineColorTrack is running, changes apply to it live; otherwise the settings file
is edited directly. Run `mct --help`, `mct <command> --help`, `mct schema` and `mct guide` for details.
"""
import argparse
import copy
import json
import os
import subprocess
import sys
from dataclasses import asdict, fields, is_dataclass

from . import APP_NAME, COPYRIGHT, LICENSE_NAME, SOURCE_URL, __version__, config, ipc

GLOBAL_SECTIONS = ("capture", "display", "hotkeys", "ai")
PROFILE_SECTIONS = ("outline", "tracking", "detection")

GUIDE = """MineColorTrack command-line guide (for people and AI agents)

MineColorTrack outlines things on screen: colour targets (any thing of a chosen colour) and AI entities
(things your own trained .onnx model recognises). It only draws; it never controls the game.

Basics
  mct status                         is the app running, what it watches, fps, targets in view
  mct schema                         every setting: key, type, allowed values, limits, explanation
  mct get [KEY]                      read all settings, or one (e.g. capture.fps, outline.thickness)
  mct set KEY VALUE                  change a setting (validated). Profile settings (outline.*, tracking.*,
                                     detection.*) apply to the active profile unless --profile NAME is given.
What to watch
  mct windows / mct monitors         list open windows / monitors
  mct watch window --title T [--exe E] | mct watch monitor N | mct watch region X Y W H
Profiles
  mct profile list | use NAME | new NAME | copy FROM NEW | rename OLD NEW | delete NAME
Colour targets (in the active profile, or --profile NAME)
  mct target list
  mct target add NAME --color "#50C84B" [--hue-tol 10 --sat-min 45 --val-min 55 --min-area 40 --outline "#FF00FF"]
  mct target pick NAME IMAGE X Y     add/update NAME with the colour at pixel X,Y of a screenshot (suggests ranges)
  mct target set NAME KEY VALUE      KEY: enabled color hue_tol sat_min sat_max val_min val_max min_area
                                     max_area outline_color name
  mct target remove NAME
AI model and entities
  mct model load FILE.onnx | mct model clear | mct model info
  mct entity list | mct entity set NAME enabled|outline_color VALUE
Testing settings on a picture
  mct detect IMAGE [--out marked.png]  what the current profile would outline in IMAGE (JSON boxes)
Running app
  mct start | stop | toggle-outline | screenshot | show | quit   (start launches the app if needed)
Updates
  mct update check | mct update install   (install closes the app, runs the new installer, reopens it)
Labelling dataset (for training your own AI model)
  mct dataset info | classes | add-class NAME | import ZIP_OR_FOLDER | add-image FILE... | export OUT.zip

Tips for agents
  - Read `mct schema` first; keys and allowed values are listed there.
  - All output is JSON on stdout. Errors are JSON on stderr with exit code 1.
  - To tune a colour target: take a screenshot (`mct screenshot` saves one to the dataset, or use any image),
    `mct target pick`, then run `mct detect` and adjust hue_tol / sat_min / val_min / min_area until only the
    wanted things are found.
"""


class CliError(Exception):
    pass


def out(obj):
    # ASCII-only JSON (non-English text becomes \\uXXXX): safe in every Windows console and easy to parse
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=True, default=str) + "\n")


# ---------------------------------------------------------------- settings access (live app or file)
class Backend:
    def __init__(self, path, offline=False):
        self.path = path
        self.live = not offline and ipc.is_running(path)

    def load(self):
        if self.live:
            return config.from_dict(ipc.request(self.path, "get_config"))
        return config.load(self.path)

    def save(self, cfg):
        if self.live:
            ipc.request(self.path, "set_config", asdict(cfg))
        else:
            config.save(cfg, self.path)

    def action(self, name, **args):
        if not self.live:
            raise CliError("MineColorTrack is not running. Use `mct start` first.")
        return ipc.request(self.path, "action", dict(args, name=name))


def pick_profile(cfg, name):
    if name is None:
        return cfg.profile
    if name not in cfg.profiles:
        raise CliError("No profile called %r. Profiles: %s" % (name, ", ".join(cfg.profiles)))
    return cfg.profiles[name]


def resolve_key(cfg, key, profile_name=None):
    """'capture.fps' -> (object, 'fps'); 'outline.thickness' -> (profile.outline, 'thickness')."""
    parts = key.split(".")
    if len(parts) == 3 and parts[0] == "profile":
        parts = parts[1:]
    if len(parts) != 2:
        raise CliError("Keys look like section.name, for example capture.fps or outline.thickness. See `mct schema`.")
    section, attr = parts
    if section in GLOBAL_SECTIONS:
        obj = getattr(cfg, section)
    elif section in PROFILE_SECTIONS:
        obj = getattr(pick_profile(cfg, profile_name), section)
    else:
        raise CliError("Unknown section %r. Sections: %s" % (section, ", ".join(GLOBAL_SECTIONS + PROFILE_SECTIONS)))
    if attr not in {f.name for f in fields(obj)} or attr == "entities":
        raise CliError("Unknown setting %r in %s. See `mct schema`." % (attr, section))
    return obj, attr


def schema():
    from .help_text import TIPS
    items = []

    def add(prefix, obj, scope):
        cls = type(obj).__name__
        for f in fields(obj):
            if f.name in ("entities",):
                continue
            val = getattr(obj, f.name)
            key = "%s.%s" % (prefix, f.name)
            entry = {"key": key, "scope": scope, "type": type(val).__name__, "default": val}
            if (cls, f.name) in config.CHOICES:
                entry["choices"] = [c[0] for c in config.CHOICES[(cls, f.name)]]
                entry["choice_labels"] = {c[0]: c[1] for c in config.CHOICES[(cls, f.name)]}
            if (cls, f.name) in config.LIMITS:
                entry["min"], entry["max"] = config.LIMITS[(cls, f.name)]
            if f.name in config.COLOUR_FIELDS:
                entry["format"] = "#RRGGBB"
            tip = TIPS.get(key) or TIPS.get(key.replace("detection.", "detection."))
            if tip:
                entry["label"], entry["help"] = tip[0] or None, tip[1]
            items.append(entry)

    for sec in GLOBAL_SECTIONS:
        add(sec, getattr(config.AppConfig(), sec), "global")
    prof = config.Profile()
    for sec in PROFILE_SECTIONS:
        add(sec, getattr(prof, sec), "profile")
    add("target", config.Target(), "target")
    add("entity", config.Entity(), "entity")
    return {"settings": items,
            "notes": ["Set global and profile keys with `mct set KEY VALUE`.",
                      "Target keys are changed with `mct target set NAME KEY VALUE` (without the 'target.' prefix).",
                      "Entity keys are changed with `mct entity set NAME KEY VALUE`."]}


def find_target(prof, name):
    for t in prof.targets:
        if t.name.lower() == name.lower():
            return t
    raise CliError("No target called %r. Targets: %s" % (name, ", ".join(t.name for t in prof.targets) or "none"))


def find_entity(prof, name):
    for e in prof.detection.entities:
        if e.name.lower() == name.lower():
            return e
    raise CliError("No entity called %r. Entities: %s" % (
        name, ", ".join(e.name for e in prof.detection.entities) or "none (load a model first)"))


def set_attr(obj, attr, value):
    valid = {f.name for f in fields(obj)}
    if attr not in valid:
        raise CliError("Unknown key %r. Valid: %s" % (attr, ", ".join(sorted(valid))))
    try:
        setattr(obj, attr, config.convert(obj, attr, value))
    except ValueError as exc:
        raise CliError(str(exc))
    return getattr(obj, attr)


# ---------------------------------------------------------------- commands
def cmd_status(b, a):
    info = {"app": APP_NAME, "version": __version__, "running": b.live, "settings_file": b.path}
    if b.live:
        info.update(ipc.request(b.path, "action", {"name": "status"}))
    else:
        cfg = b.load()
        info.update({"active_profile": cfg.active_profile, "watching": watch_summary(cfg)})
    return info


def watch_summary(cfg):
    cap = cfg.capture
    if cap.source == "window":
        return {"source": "window", "title": cap.window_title, "exe": cap.window_exe}
    if cap.source == "monitor":
        return {"source": "monitor", "monitor": cap.monitor}
    return {"source": "region", "region": cap.region}


def cmd_get(b, a):
    cfg = b.load()
    if not a.key:
        return asdict(cfg)
    obj, attr = resolve_key(cfg, a.key, a.profile)
    val = getattr(obj, attr)
    return {"key": a.key, "value": asdict(val) if is_dataclass(val) else val}


def cmd_set(b, a):
    cfg = b.load()
    obj, attr = resolve_key(cfg, a.key, a.profile)
    try:
        setattr(obj, attr, config.convert(obj, attr, a.value))
    except ValueError as exc:
        raise CliError(str(exc))
    b.save(cfg)
    return {"key": a.key, "value": getattr(obj, attr), "applied_live": b.live}


def cmd_reset(b, a):
    if not a.confirm:
        raise CliError("This replaces ALL settings and profiles with the defaults. Add --confirm to do it.")
    b.save(config.default_config())
    return {"reset": True}


def cmd_profile(b, a):
    cfg = b.load()
    act = a.action
    if act == "list":
        return {"active": cfg.active_profile, "profiles": [
            {"name": n, "targets": len(p.targets), "ai": bool(p.detection.enabled and p.detection.model_path)}
            for n, p in cfg.profiles.items()]}
    if act == "use":
        pick_profile(cfg, a.name)
        cfg.active_profile = a.name
    elif act == "new":
        if a.name in cfg.profiles:
            raise CliError("A profile called %r already exists." % a.name)
        cfg.profiles[a.name] = config.Profile()
        cfg.active_profile = a.name
    elif act == "copy":
        src = pick_profile(cfg, a.name)
        if not a.new or a.new in cfg.profiles:
            raise CliError("Give a new, unused name: mct profile copy FROM NEW")
        cfg.profiles[a.new] = copy.deepcopy(src)
    elif act == "rename":
        pick_profile(cfg, a.name)
        if not a.new or a.new in cfg.profiles:
            raise CliError("Give a new, unused name: mct profile rename OLD NEW")
        cfg.profiles = {(a.new if k == a.name else k): v for k, v in cfg.profiles.items()}
        if cfg.active_profile == a.name:
            cfg.active_profile = a.new
    elif act == "delete":
        pick_profile(cfg, a.name)
        if len(cfg.profiles) == 1:
            raise CliError("Keep at least one profile.")
        del cfg.profiles[a.name]
        cfg.profile  # normalise
    b.save(cfg)
    return {"ok": True, "active": cfg.active_profile, "profiles": list(cfg.profiles)}


TARGET_OPTS = ("color", "hue_tol", "sat_min", "sat_max", "val_min", "val_max", "min_area", "max_area",
               "outline_color", "enabled")


def cmd_target(b, a):
    cfg = b.load()
    prof = pick_profile(cfg, a.profile)
    act = a.action
    if act == "list":
        return {"profile": a.profile or cfg.active_profile, "targets": [asdict(t) for t in prof.targets]}
    if act == "add":
        if any(t.name.lower() == a.name.lower() for t in prof.targets):
            raise CliError("Target %r already exists; use `mct target set`." % a.name)
        t = config.Target(name=a.name)
        for opt in TARGET_OPTS:
            val = getattr(a, opt, None)
            if val is not None:
                set_attr(t, opt, val)
        prof.targets.append(t)
    elif act == "set":
        if a.key is None or a.value is None:
            raise CliError("Usage: mct target set NAME KEY VALUE")
        t = find_target(prof, a.name)
        set_attr(t, a.key, a.value)
    elif act == "remove":
        t = find_target(prof, a.name)
        prof.targets.remove(t)
    elif act == "pick":
        from . import vision
        from .dataset import read_image
        if a.image is None or a.x is None or a.y is None:
            raise CliError("Usage: mct target pick NAME IMAGE X Y")
        img = read_image(a.image)
        if img is None:
            raise CliError("Cannot read image %s" % a.image)
        h, w = img.shape[:2]
        if not (0 <= a.x < w and 0 <= a.y < h):
            raise CliError("Pixel %d,%d is outside the %dx%d image." % (a.x, a.y, w, h))
        colour, hue_tol, sat_min, val_min = vision.patch_stats(img, a.x, a.y)
        try:
            t = find_target(prof, a.name)
        except CliError:
            t = config.Target(name=a.name)
            prof.targets.append(t)
        t.color, t.hue_tol, t.sat_min, t.val_min = colour, hue_tol, sat_min, val_min
        t.sat_max = t.val_max = 100
        t.enabled = True
    b.save(cfg)
    return {"ok": True, "targets": [asdict(t) for t in prof.targets], "applied_live": b.live}


def cmd_model(b, a):
    cfg = b.load()
    prof = pick_profile(cfg, a.profile)
    det = prof.detection
    if a.action == "info":
        info = {"enabled": det.enabled, "model_path": det.model_path, "confidence": det.confidence,
                "entities": [asdict(e) for e in det.entities]}
        if det.model_path:
            try:
                from .detector import Detector
                d = Detector(det.model_path, prefer_gpu=False)
                info["classes"], info["input_size"] = d.names, list(d.size)
            except Exception as exc:
                info["problem"] = str(exc)
        return info
    if a.action == "clear":
        det.model_path, det.enabled, det.entities = "", False, []
    elif a.action == "load":
        from .detector import Detector
        from .engine import PALETTE
        if not a.file:
            raise CliError("Usage: mct model load FILE.onnx")
        path = os.path.abspath(a.file)
        try:
            names = Detector(path, prefer_gpu=False).names
        except Exception as exc:
            raise CliError("This model cannot be used: %s" % exc)
        old = {e.name: e for e in det.entities}
        det.entities = [old.get(n) or config.Entity(name=n, outline_color=PALETTE[i % len(PALETTE)])
                        for i, n in enumerate(names)]
        det.model_path, det.enabled = path, True
    b.save(cfg)
    return {"ok": True, "model_path": det.model_path, "enabled": det.enabled,
            "entities": [asdict(e) for e in det.entities], "applied_live": b.live}


def cmd_entity(b, a):
    cfg = b.load()
    prof = pick_profile(cfg, a.profile)
    if a.action == "list":
        return {"entities": [asdict(e) for e in prof.detection.entities]}
    if a.name is None or a.key is None or a.value is None:
        raise CliError("Usage: mct entity set NAME KEY VALUE   (KEY: enabled or outline_color)")
    e = find_entity(prof, a.name)
    if a.key not in ("enabled", "outline_color"):
        raise CliError("KEY must be enabled or outline_color")
    set_attr(e, a.key, a.value)
    b.save(cfg)
    return {"ok": True, "entity": asdict(e), "applied_live": b.live}


def cmd_windows(b, a):
    from . import winplat
    if not winplat.IS_WIN:
        return {"windows": [], "note": "The window list is only available on Windows."}
    return {"windows": [{"title": w["title"], "exe": w["exe"], "minimised": w["minimised"]}
                        for w in winplat.list_windows()]}


def cmd_monitors(b, a):
    import mss
    factory = getattr(mss, "MSS", None) or mss.mss
    with factory() as sct:
        return {"monitors": [{"number": i, "x": m["left"], "y": m["top"], "width": m["width"], "height": m["height"]}
                             for i, m in enumerate(sct.monitors) if i > 0]}


def cmd_watch(b, a):
    cfg = b.load()
    cap = cfg.capture
    if a.kind == "window":
        if not (a.title or a.exe):
            raise CliError("Give --title and/or --exe (see `mct windows`).")
        cap.source, cap.window_title, cap.window_exe = "window", a.title or "", a.exe or ""
    elif a.kind == "monitor":
        if len(a.numbers) != 1:
            raise CliError("Usage: mct watch monitor N   (see `mct monitors`)")
        set_attr(cap, "monitor", str(a.numbers[0]))
        cap.source = "monitor"
    else:
        if len(a.numbers) != 4 or a.numbers[2] < 16 or a.numbers[3] < 16:
            raise CliError("Usage: mct watch region X Y WIDTH HEIGHT  (width and height at least 16)")
        cap.source, cap.region = "region", list(a.numbers)
    b.save(cfg)
    return {"ok": True, "watching": watch_summary(cfg), "applied_live": b.live}


def cmd_detect(b, a):
    import cv2
    from . import engine, vision
    from .dataset import read_image
    img = read_image(a.image)
    if img is None:
        raise CliError("Cannot read image %s" % a.image)
    cfg = b.load()
    if a.profile:
        cfg.active_profile = a.profile
        pick_profile(cfg, a.profile)
    res = engine.Engine(cfg).process(img, (0, 0, img.shape[1], img.shape[0]))
    boxes = [{"name": t[5], "x": round(t[0]), "y": round(t[1]), "w": round(t[2]), "h": round(t[3]),
              "outline_color": t[6]} for t in res.tracks if not t[4]]
    result = {"image": a.image, "size": [img.shape[1], img.shape[0]], "found": len(boxes), "boxes": boxes}
    if res.ai_error:
        result["ai_problem"] = res.ai_error
    if a.out:
        marked = img.copy()
        for bx in boxes:
            col = vision.hex_to_bgr(bx["outline_color"])
            cv2.rectangle(marked, (bx["x"], bx["y"]), (bx["x"] + bx["w"], bx["y"] + bx["h"]), (0, 0, 0), 5)
            cv2.rectangle(marked, (bx["x"], bx["y"]), (bx["x"] + bx["w"], bx["y"] + bx["h"]), col, 2)
            cv2.putText(marked, bx["name"], (bx["x"], max(12, bx["y"] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
        ok, buf = cv2.imencode(os.path.splitext(a.out)[1] or ".png", marked)
        buf.tofile(a.out)
        result["marked_image"] = os.path.abspath(a.out)
    return result


def app_executable():
    """Path of the windowed app next to this tool (installed), or a source-run command line."""
    if getattr(sys, "frozen", False):
        exe = os.path.join(os.path.dirname(sys.executable), "MineColorTrack.exe")
        if os.path.exists(exe):
            return [exe]
    run = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run.py")
    return [sys.executable, run]


def cmd_app(b, a):
    name = a.command.replace("-", "_")
    if name == "start" and not b.live:
        cmd = app_executable() + ["--start"]
        if b.path != config.default_path():
            cmd += ["--config", b.path]
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(cmd, close_fds=True, creationflags=flags if sys.platform == "win32" else 0)
        import time
        for _ in range(60):
            time.sleep(0.25)
            if ipc.is_running(b.path):
                return {"launched": True, "running": True}
        return {"launched": True, "running": False, "note": "Launched, but it did not answer yet."}
    return b.action(name)


def cmd_update(b, a):
    from . import updater, winplat
    try:
        info = updater.check()
    except updater.UpdateError as exc:
        raise CliError(str(exc))
    if not a.notes:
        info.pop("notes", None)
    if a.action == "check":
        return info
    if not info["newer"]:
        return dict(info, installed=False, note="Already the newest version.")
    if not winplat.IS_WIN:
        raise CliError("Installing updates is only possible on Windows.")
    path = updater.download(info["installer"])
    if b.live:
        ipc.request(b.path, "action", {"name": "quit"})
        import time
        for _ in range(40):
            time.sleep(0.25)
            if not ipc.is_running(b.path):
                break
    updater.run_installer(path)
    return dict(info, installed=True, installer=path, note="The installer is running and reopens MineColorTrack.")


def cmd_dataset(b, a):
    from .dataset import Dataset, default_root
    cfg = b.load()
    ds = Dataset(cfg.ai.dataset_dir or default_root())
    act = a.action
    if act == "info":
        st = ds.stats()
        st["classes"], st["folder"], st["advice"] = ds.classes, ds.root, ds.advice(st)
        return st
    if act == "classes":
        return {"classes": ds.classes}
    if act == "add-class":
        if not a.args:
            raise CliError("Usage: mct dataset add-class NAME")
        try:
            return {"id": ds.add_class(" ".join(a.args)), "classes": ds.classes}
        except ValueError as exc:
            raise CliError(str(exc))
    if act == "import":
        if not a.args:
            raise CliError("Usage: mct dataset import ZIP_OR_FOLDER")
        try:
            added, new = ds.import_yolo(a.args[0])
        except Exception as exc:
            raise CliError("Could not import: %s" % exc)
        return {"added": added, "new_classes": new, "classes": ds.classes}
    if act == "add-image":
        stems = []
        for f in a.args:
            try:
                stems.append(ds.add_image_file(f))
            except ValueError as exc:
                raise CliError(str(exc))
        return {"added": stems}
    if act == "export":
        if not a.args:
            raise CliError("Usage: mct dataset export OUT.zip")
        nb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "train_minecolortrack.ipynb")
        try:
            info = ds.export_zip(os.path.abspath(a.args[0]), notebook=nb)
        except ValueError as exc:
            raise CliError(str(exc))
        info["zip"] = os.path.abspath(a.args[0])
        info["next"] = ("Upload train_minecolortrack.ipynb to https://colab.research.google.com (File > Upload "
                        "notebook), choose a T4 GPU runtime, Run all and upload this zip.")
        return info
    raise CliError("Unknown dataset action")


# ---------------------------------------------------------------- argument parsing
def build_parser():
    ap = argparse.ArgumentParser(prog="mct", description="Control MineColorTrack from the command line. "
                                 "Output is JSON. Changes apply live when the app is running.",
                                 epilog="Run `mct guide` for a walkthrough and `mct schema` for every setting.")
    ap.add_argument("--config", default=config.default_path(), help="settings file (default: %(default)s)")
    ap.add_argument("--offline", action="store_true", help="edit the settings file even if the app is running "
                    "(the app may overwrite it)")
    ap.add_argument("--version", action="version", version="%s %s - %s, %s. No warranty. Source: %s" % (
        APP_NAME, __version__, COPYRIGHT, LICENSE_NAME, SOURCE_URL))
    sub = ap.add_subparsers(dest="command", required=True, metavar="COMMAND")

    sub.add_parser("guide", help="how to use this tool")
    sub.add_parser("status", help="is the app running, what it watches, fps")
    sub.add_parser("schema", help="every setting with type, allowed values and explanation")
    p = sub.add_parser("get", help="read settings")
    p.add_argument("key", nargs="?", help="e.g. capture.fps or outline.thickness; omit for everything")
    p.add_argument("--profile")
    p = sub.add_parser("set", help="change a setting")
    p.add_argument("key")
    p.add_argument("value")
    p.add_argument("--profile")
    p = sub.add_parser("reset", help="restore default settings (deletes profiles)")
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("profile", help="list, use, create, copy, rename or delete profiles")
    p.add_argument("action", choices=["list", "use", "new", "copy", "rename", "delete"])
    p.add_argument("name", nargs="?")
    p.add_argument("new", nargs="?")

    p = sub.add_parser("target", help="colour targets")
    p.add_argument("action", choices=["list", "add", "set", "remove", "pick"])
    p.add_argument("name", nargs="?")
    p.add_argument("rest", nargs="*", help="set: KEY VALUE   pick: IMAGE X Y")
    p.add_argument("--profile")
    for opt in TARGET_OPTS:
        p.add_argument("--" + opt.replace("_", "-"), dest=opt)
    p.add_argument("--outline", dest="outline_color")

    p = sub.add_parser("model", help="AI model: load, clear, info")
    p.add_argument("action", choices=["load", "clear", "info"])
    p.add_argument("file", nargs="?")
    p.add_argument("--profile")
    p = sub.add_parser("entity", help="AI entities: list, set")
    p.add_argument("action", choices=["list", "set"])
    p.add_argument("name", nargs="?")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.add_argument("--profile")

    sub.add_parser("windows", help="list open windows (Windows only)")
    sub.add_parser("monitors", help="list monitors")
    p = sub.add_parser("watch", help="choose what to watch")
    p.add_argument("kind", choices=["window", "monitor", "region"])
    p.add_argument("numbers", nargs="*", type=int, help="monitor: N   region: X Y WIDTH HEIGHT")
    p.add_argument("--title")
    p.add_argument("--exe")

    p = sub.add_parser("detect", help="test the current profile on an image")
    p.add_argument("image")
    p.add_argument("--out", help="also save a copy with the outlines drawn")
    p.add_argument("--profile")

    for name, text in (("start", "start watching (launches the app if needed)"), ("stop", "stop watching"),
                       ("toggle-outline", "outlines on/off"), ("screenshot", "save a screenshot for labelling"),
                       ("show", "bring the control panel to the front"), ("quit", "close the app")):
        sub.add_parser(name, help=text)

    p = sub.add_parser("update", help="check GitHub for a newer version, or download and install it")
    p.add_argument("action", choices=["check", "install"])
    p.add_argument("--notes", action="store_true", help="include the release notes")

    p = sub.add_parser("dataset", help="labelled screenshots for training")
    p.add_argument("action", choices=["info", "classes", "add-class", "import", "add-image", "export"])
    p.add_argument("args", nargs="*")
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    if a.command == "guide":
        sys.stdout.write(GUIDE)
        return 0
    if a.command == "schema":
        out(schema())
        return 0
    if a.command == "target":
        rest = a.rest
        a.key = a.value = a.image = a.x = a.y = None
        if a.action == "set" and len(rest) >= 2:
            a.key, a.value = rest[0], " ".join(rest[1:])
        elif a.action == "pick" and len(rest) == 3:
            try:
                a.image, a.x, a.y = rest[0], int(rest[1]), int(rest[2])
            except ValueError:
                pass
        if a.action != "list" and not a.name:
            ap.error("target %s needs a NAME" % a.action)
    try:
        b = Backend(a.config, offline=a.offline)
        handler = {
            "status": cmd_status, "get": cmd_get, "set": cmd_set, "reset": cmd_reset, "profile": cmd_profile,
            "target": cmd_target, "model": cmd_model, "entity": cmd_entity, "windows": cmd_windows,
            "monitors": cmd_monitors, "watch": cmd_watch, "detect": cmd_detect, "dataset": cmd_dataset,
            "update": cmd_update,
        }.get(a.command, cmd_app)
        if a.command == "profile" and a.action != "list" and not a.name:
            raise CliError("profile %s needs a NAME" % a.action)
        out(handler(b, a))
        return 0
    except (CliError, RuntimeError, TimeoutError, ipc.NotRunning) as exc:
        sys.stderr.write(json.dumps({"error": str(exc)}) + "\n")
        return 1
