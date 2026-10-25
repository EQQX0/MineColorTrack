# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings, JSON load/save, and migration of older settings files."""
import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass


@dataclass
class Target:
    name: str = "New target"
    enabled: bool = True
    color: str = "#50C84B"      # colour to look for (hex)
    hue_tol: int = 12           # +/- degrees around the colour's hue
    sat_min: int = 40           # percent
    sat_max: int = 100
    val_min: int = 45           # percent (brightness)
    val_max: int = 100
    min_area: int = 40          # matched pixels needed (in stream pixels)
    max_area: int = 0           # 0 = no limit
    outline_color: str = "#FF00FF"


@dataclass
class OutlineCfg:
    enabled: bool = True
    style: str = "box"
    thickness: int = 4
    padding: int = 6
    black_border: bool = True
    use_target_color: bool = True
    color: str = "#FF00FF"
    marker: str = "arrow"
    labels: bool = False
    blink: bool = False
    show_held: bool = True


@dataclass
class TrackingCfg:
    smoothing: int = 50         # percent, higher = steadier but laggier boxes
    hold_frames: int = 6        # keep a box this many frames after it is lost
    merge_distance: int = 8     # px; pieces closer than this become one target
    noise_filter: int = 1       # 0 = off, higher removes more specks


@dataclass
class Entity:
    name: str = ""
    enabled: bool = True
    outline_color: str = "#FFE600"


@dataclass
class DetectionCfg:
    enabled: bool = False
    model_path: str = ""        # .onnx file made with the Colab notebook
    confidence: int = 45        # percent; lower finds more but makes more mistakes
    entities: list = field(default_factory=list)


@dataclass
class Profile:
    targets: list = field(default_factory=list)
    outline: OutlineCfg = field(default_factory=OutlineCfg)
    tracking: TrackingCfg = field(default_factory=TrackingCfg)
    detection: DetectionCfg = field(default_factory=DetectionCfg)


@dataclass
class CaptureCfg:
    source: str = "monitor"
    window_title: str = ""      # text the window title contains
    window_exe: str = ""        # program file name, e.g. "RemotePlay.exe" (survives title changes)
    monitor: int = 1
    region: list = field(default_factory=lambda: [100, 100, 1280, 720])
    fps: int = 30
    scale: int = 50             # processing resolution, percent
    method: str = "auto"        # screen capture: auto | fast | compatible
    focus_shape: str = "off"    # only look in the middle: off | circle | square
    focus_size: int = 50        # its size, percent of the watched picture's shorter side
    focus_show: bool = True     # draw the zone on screen so you can see it
    focus_color: str = "#FF0000"    # colour of the zone's line and inside
    focus_line_alpha: int = 70      # line opacity, percent
    focus_fill_alpha: int = 6       # inside opacity, percent (almost invisible)


@dataclass
class DisplayCfg:
    mode: str = "overlay"
    mirror_on_top: bool = False
    ui_font_pt: int = 12
    theme: str = "dark"
    start_on_launch: bool = False
    close_to_tray: bool = False
    show_advanced: bool = False


@dataclass
class HotkeysCfg:
    toggle_overlay: str = "Ctrl+Alt+A"
    next_profile: str = "Ctrl+Alt+P"
    toggle_outline: str = "Ctrl+Alt+O"
    save_screenshot: str = "Ctrl+Alt+S"


@dataclass
class AICfg:
    dataset_dir: str = ""       # "" = Documents\MineColorTrack dataset
    device: str = "auto"        # where the model runs: auto | tensorrt | cuda | directml | cpu
    tensorrt_fp16: bool = True  # TensorRT may use half precision (faster, same results within rounding)


@dataclass
class ExportCfg:
    enabled: bool = False       # write detections to a file while running
    path: str = ""              # "" = detections.json next to the settings file
    history: bool = False       # also append every frame to a .jsonl file next to it


@dataclass
class UpdateCfg:
    check_on_start: bool = True
    skip_version: str = ""      # "Skip this version" remembers it here


@dataclass
class AppConfig:
    capture: CaptureCfg = field(default_factory=CaptureCfg)
    display: DisplayCfg = field(default_factory=DisplayCfg)
    hotkeys: HotkeysCfg = field(default_factory=HotkeysCfg)
    ai: AICfg = field(default_factory=AICfg)
    export: ExportCfg = field(default_factory=ExportCfg)
    updates: UpdateCfg = field(default_factory=UpdateCfg)
    active_profile: str = ""
    profiles: dict = field(default_factory=dict)
    version: int = 2            # settings-file format; 1 = MineColorTrack 1.0 to 1.1.x

    @property
    def profile(self):
        if self.active_profile not in self.profiles:
            if not self.profiles:
                self.profiles = default_profiles()
            self.active_profile = next(iter(self.profiles))
        return self.profiles[self.active_profile]


# Allowed values for multiple-choice settings: (class name, field) -> [(value, label)]
CHOICES = {
    ("OutlineCfg", "style"): [("box", "Box"), ("corners", "Corner brackets"), ("ellipse", "Ellipse")],
    ("OutlineCfg", "marker"): [("arrow", "Arrow above"), ("dot", "Dot above"), ("none", "None")],
    ("CaptureCfg", "source"): [("window", "An open window (follows it when it moves)"),
                               ("monitor", "A whole monitor"),
                               ("region", "Part of the screen (drag a box)")],
    ("CaptureCfg", "method"): [("auto", "Automatic (fast when it works)"),
                               ("fast", "Fast: Windows Desktop Duplication"),
                               ("compatible", "Compatible: classic screen copy")],
    ("CaptureCfg", "focus_shape"): [("off", "Whole picture"),
                                    ("circle", "Circle in the middle"),
                                    ("square", "Square in the middle")],
    ("DisplayCfg", "mode"): [("overlay", "Overlay on top of the game"),
                             ("mirror", "Separate mirror window")],
    ("DisplayCfg", "theme"): [("dark", "Dark"), ("light", "Light"),
                              ("contrast", "High contrast (black and yellow)")],
    ("AICfg", "device"): [("auto", "Automatic (fastest that works)"),
                          ("tensorrt", "TensorRT (NVIDIA, fastest)"),
                          ("cuda", "CUDA (NVIDIA)"),
                          ("directml", "DirectML (any DirectX 12 graphics card)"),
                          ("cpu", "Processor only")],
}


STARTER_PROFILE = "My profile"


def default_profiles():
    """No built-in content: one empty profile that people fill with their own targets."""
    return {STARTER_PROFILE: Profile()}


def default_config():
    cfg = AppConfig(profiles=default_profiles())
    cfg.active_profile = STARTER_PROFILE
    return cfg


# Allowed numeric ranges, (class name, field) -> (min, max). Shared by the control panel and the `mct` tool.
LIMITS = {
    ("CaptureCfg", "fps"): (5, 120), ("CaptureCfg", "scale"): (20, 100), ("CaptureCfg", "monitor"): (1, 16),
    ("CaptureCfg", "focus_size"): (5, 100),
    ("CaptureCfg", "focus_line_alpha"): (0, 100), ("CaptureCfg", "focus_fill_alpha"): (0, 100),
    ("DisplayCfg", "ui_font_pt"): (9, 24),
    ("OutlineCfg", "thickness"): (1, 24), ("OutlineCfg", "padding"): (0, 60),
    ("TrackingCfg", "smoothing"): (0, 95), ("TrackingCfg", "hold_frames"): (0, 90),
    ("TrackingCfg", "merge_distance"): (0, 80), ("TrackingCfg", "noise_filter"): (0, 6),
    ("DetectionCfg", "confidence"): (5, 95),
    ("Target", "hue_tol"): (1, 90), ("Target", "sat_min"): (0, 100), ("Target", "sat_max"): (0, 100),
    ("Target", "val_min"): (0, 100), ("Target", "val_max"): (0, 100),
    ("Target", "min_area"): (1, 200000), ("Target", "max_area"): (0, 2000000),
}
COLOUR_FIELDS = {"color", "outline_color", "focus_color"}


def convert(obj, attr, text):
    """Turn a text value into the right type for obj.attr, enforcing choices, limits and colour format."""
    import re
    cls = type(obj).__name__
    cur = getattr(obj, attr)
    if (cls, attr) in CHOICES:
        allowed = [c[0] for c in CHOICES[(cls, attr)]]
        if text not in allowed:
            raise ValueError("%s must be one of: %s" % (attr, ", ".join(allowed)))
        return text
    if isinstance(cur, bool):
        low = str(text).strip().lower()
        if low in ("1", "true", "yes", "on"):
            return True
        if low in ("0", "false", "no", "off"):
            return False
        raise ValueError("%s must be true or false" % attr)
    if isinstance(cur, (int, float)):
        try:
            val = type(cur)(float(text)) if isinstance(cur, int) else float(text)
        except ValueError:
            raise ValueError("%s must be a number" % attr)
        lo, hi = LIMITS.get((cls, attr), (None, None))
        if lo is not None and not lo <= val <= hi:
            raise ValueError("%s must be between %s and %s" % (attr, lo, hi))
        return val
    if isinstance(cur, list):
        parts = [int(float(v)) for v in str(text).replace(",", " ").split()]
        if attr == "region" and len(parts) != 4:
            raise ValueError("region needs 4 numbers: x y width height")
        return parts
    text = str(text)
    if attr in COLOUR_FIELDS:
        if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", text.strip()):
            raise ValueError("%s must be a colour like #FF00FF" % attr)
        return "#" + text.strip().lstrip("#").upper()
    return text


def replace_in_place(cfg, new):
    """Copy every setting from `new` into `cfg`, keeping the same object (the running app holds references)."""
    for f in fields(cfg):
        setattr(cfg, f.name, getattr(new, f.name))
    cfg.profile  # normalise active_profile


def _legacy_presets():
    """Profiles that versions 1.0 to 1.1.x created automatically. Only used to clean up old settings files."""
    def t(name, color, outline, hue_tol, sat_min, val_min, min_area=40):
        return Target(name=name, color=color, outline_color=outline, hue_tol=hue_tol, sat_min=sat_min,
                      val_min=val_min, min_area=min_area)
    creeper = lambda: t("Creeper", "#50C84B", "#FF00FF", 10, 45, 55)
    zombie = lambda: t("Zombie shirt", "#00A8A8", "#FF6A00", 10, 55, 35)
    spider = lambda: t("Spider eyes", "#E01010", "#00FFFF", 10, 60, 45, 6)
    hostiles = lambda: Profile(targets=[creeper(), zombie(), spider()])
    strong_10 = hostiles()
    strong_10.outline.thickness = 6
    strong_11 = hostiles()
    strong_11.outline.thickness, strong_11.outline.padding, strong_11.outline.labels = 8, 10, True
    return {
        "Minecraft: creepers": Profile(targets=[creeper()]),
        "Minecraft: zombies": Profile(targets=[zombie()]),
        "Minecraft: night eyes (spider, enderman)": Profile(
            targets=[spider(), t("Enderman eyes", "#D06BF5", "#00FF66", 12, 35, 60, 6)]),
        "Minecraft: common hostiles": hostiles(),
        "Minecraft: strong low-vision": strong_10,
        "Minecraft: extra-bold outlines": strong_11,
    }


def _migrate_v1(cfg):
    """Remove what older versions filled in by themselves; keep everything the person changed or made."""
    legacy = _legacy_presets()
    cfg.profiles = {name: prof for name, prof in cfg.profiles.items()
                    if not (name in legacy and prof == legacy[name])}
    cap = cfg.capture
    if cap.window_title == "PS Remote Play" and not cap.window_exe:   # 1.0's built-in default
        cap.window_title = ""
        if cap.source == "window":
            cap.source = "monitor"


def _fill(obj, data):
    """Copy known keys from a dict onto a dataclass, keeping defaults for anything missing or invalid."""
    if not isinstance(data, dict):
        return obj
    cls = type(obj).__name__
    for f in fields(obj):
        if f.name not in data:
            continue
        cur, val = getattr(obj, f.name), data[f.name]
        try:
            if is_dataclass(cur):
                _fill(cur, val)
            elif f.name == "targets":
                setattr(obj, f.name, [_fill(Target(), t) for t in val if isinstance(t, dict)])
            elif f.name == "entities":
                setattr(obj, f.name, [_fill(Entity(), e) for e in val if isinstance(e, dict)])
            elif f.name == "profiles":
                setattr(obj, f.name, {str(k): _fill(Profile(), v) for k, v in val.items() if isinstance(v, dict)})
            elif (cls, f.name) in CHOICES:
                if val in [c[0] for c in CHOICES[(cls, f.name)]]:
                    setattr(obj, f.name, val)
            elif isinstance(cur, bool):
                setattr(obj, f.name, bool(val))
            elif isinstance(cur, (int, float)):
                setattr(obj, f.name, type(cur)(val))
            elif isinstance(cur, str):
                setattr(obj, f.name, str(val))
            elif isinstance(cur, list):
                if f.name == "region" and len(val) == 4:
                    setattr(obj, f.name, [int(v) for v in val])
        except (TypeError, ValueError):
            pass
    return obj


def default_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MineColorTrack", "config.json")
    return os.path.join(os.path.expanduser("~"), ".config", "minecolortrack", "config.json")


def trt_cache_dir(config_path=None):
    """Folder for TensorRT engines, next to the settings file (%APPDATA%\\MineColorTrack\\trt_cache)."""
    return os.path.join(os.path.dirname(os.path.abspath(config_path or default_path())), "trt_cache")


def load(path):
    if not os.path.exists(path):
        return default_config()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return default_config()
    return from_dict(data)


def from_dict(data):
    """Settings from a dict (a settings file, or the running app's settings sent to the `mct` tool)."""
    cfg = _fill(AppConfig(), data)
    ai = data.get("ai") if isinstance(data, dict) else None
    if isinstance(ai, dict) and "device" not in ai and ai.get("prefer_gpu") is False:
        cfg.ai.device = "cpu"       # 1.6 and older: "Use the graphics card when possible" switched off
    old_version = data.get("version", 1) if isinstance(data, dict) else 1
    if not isinstance(old_version, int) or old_version < 2:
        _migrate_v1(cfg)
    cfg.version = 2
    if not cfg.profiles:
        cfg.profiles = default_profiles()
    cfg.profile  # normalises active_profile
    return cfg


def save(cfg, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(asdict(cfg), fh, indent=2)
    os.replace(tmp, path)
