"""Settings, built-in presets and JSON load/save."""
import copy
import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass


@dataclass
class Target:
    name: str = "Target"
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
class ContrastCfg:
    enabled: bool = False
    dim: int = 65               # percent darkening of everything that is not a target
    greyscale: bool = True
    fill: str = "solid"
    fill_color: str = "#FFEB00"
    grow: int = 3               # px to thicken targets by
    edges: bool = True


@dataclass
class MagnifierCfg:
    enabled: bool = False
    zoom: float = 3.0
    size: int = 260
    shape: str = "circle"
    position: str = "top-right"
    source: str = "smallest"
    contrast: int = 50
    pixelated: bool = True
    border_color: str = "#FFEB00"
    link_line: bool = True


@dataclass
class TrackingCfg:
    smoothing: int = 50         # percent, higher = steadier but laggier boxes
    hold_frames: int = 6        # keep a box this many frames after it is lost
    merge_distance: int = 8     # px; pieces closer than this become one target
    noise_filter: int = 1       # 0 = off, higher removes more specks


@dataclass
class Profile:
    targets: list = field(default_factory=list)
    outline: OutlineCfg = field(default_factory=OutlineCfg)
    contrast: ContrastCfg = field(default_factory=ContrastCfg)
    magnifier: MagnifierCfg = field(default_factory=MagnifierCfg)
    tracking: TrackingCfg = field(default_factory=TrackingCfg)


@dataclass
class CaptureCfg:
    source: str = "window"
    window_title: str = "PS Remote Play"
    monitor: int = 1
    region: list = field(default_factory=lambda: [100, 100, 1280, 720])
    fps: int = 30
    scale: int = 50             # processing resolution, percent


@dataclass
class DisplayCfg:
    mode: str = "overlay"
    crosshair: bool = False
    crosshair_color: str = "#00FFFF"
    mirror_on_top: bool = False
    ui_font_pt: int = 12
    theme: str = "dark"
    start_on_launch: bool = False
    close_to_tray: bool = False


@dataclass
class HotkeysCfg:
    toggle_overlay: str = "Ctrl+Alt+A"
    next_profile: str = "Ctrl+Alt+P"
    toggle_outline: str = "Ctrl+Alt+O"
    toggle_contrast: str = "Ctrl+Alt+C"
    toggle_magnifier: str = "Ctrl+Alt+M"


@dataclass
class AppConfig:
    capture: CaptureCfg = field(default_factory=CaptureCfg)
    display: DisplayCfg = field(default_factory=DisplayCfg)
    hotkeys: HotkeysCfg = field(default_factory=HotkeysCfg)
    active_profile: str = ""
    profiles: dict = field(default_factory=dict)

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
    ("ContrastCfg", "fill"): [("solid", "Solid colour"), ("original", "Original colours, boosted")],
    ("MagnifierCfg", "shape"): [("circle", "Circle"), ("square", "Square")],
    ("MagnifierCfg", "position"): [("top-right", "Top right"), ("top-left", "Top left"),
                                   ("bottom-right", "Bottom right"), ("bottom-left", "Bottom left"),
                                   ("follow", "Next to the target")],
    ("MagnifierCfg", "source"): [("smallest", "Smallest (usually farthest) target"),
                                 ("largest", "Largest (usually nearest) target"),
                                 ("nearest-centre", "Target nearest the screen centre"),
                                 ("centre", "Screen centre (always on)")],
    ("CaptureCfg", "source"): [("window", "PS Remote Play window (follows it)"),
                               ("monitor", "Whole monitor"), ("region", "Custom region")],
    ("DisplayCfg", "mode"): [("overlay", "Overlay on top of the game"),
                             ("mirror", "Separate mirror window")],
    ("DisplayCfg", "theme"): [("dark", "Dark"), ("light", "Light"),
                              ("contrast", "High contrast (black and yellow)")],
}


def _preset_target(name, color, outline, hue_tol=12, sat_min=40, val_min=45, min_area=40):
    return Target(name=name, color=color, outline_color=outline, hue_tol=hue_tol,
                  sat_min=sat_min, val_min=val_min, min_area=min_area)


def default_profiles():
    """Starting points. Real colours vary with lighting and texture packs, so re-pick them in game."""
    creeper = Profile(targets=[_preset_target("Creeper", "#50C84B", "#FF00FF", hue_tol=10, sat_min=45, val_min=55)])
    zombie = Profile(targets=[_preset_target("Zombie shirt", "#00A8A8", "#FF6A00", hue_tol=10, sat_min=55, val_min=35)])
    eyes = Profile(targets=[
        _preset_target("Spider eyes", "#E01010", "#00FFFF", hue_tol=10, sat_min=60, val_min=45, min_area=6),
        _preset_target("Enderman eyes", "#D06BF5", "#00FF66", hue_tol=12, sat_min=35, val_min=60, min_area=6),
    ])
    hostiles = Profile(targets=[
        _preset_target("Creeper", "#50C84B", "#FF00FF", hue_tol=10, sat_min=45, val_min=55),
        _preset_target("Zombie shirt", "#00A8A8", "#FF6A00", hue_tol=10, sat_min=55, val_min=35),
        _preset_target("Spider eyes", "#E01010", "#00FFFF", hue_tol=10, sat_min=60, val_min=45, min_area=6),
    ])
    low_vision = copy.deepcopy(hostiles)
    low_vision.contrast.enabled = True
    low_vision.magnifier.enabled = True
    low_vision.outline.thickness = 6
    return {
        "Minecraft: creepers": creeper,
        "Minecraft: zombies": zombie,
        "Minecraft: night eyes (spider, enderman)": eyes,
        "Minecraft: common hostiles": hostiles,
        "Minecraft: strong low-vision": low_vision,
    }


def default_config():
    cfg = AppConfig(profiles=default_profiles())
    cfg.active_profile = next(iter(cfg.profiles))
    return cfg


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


def load(path):
    if not os.path.exists(path):
        return default_config()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return default_config()
    cfg = _fill(AppConfig(), data)
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
