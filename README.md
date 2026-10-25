# MineColorTrack

A low-vision helper for Windows, built with Minecraft in mind. It watches any open window (a remote-play
app, a capture-card viewer, a PC game) or any monitor, finds things of a chosen colour (for example
creepers) and draws clear outlines around them.

It only draws on screen. It never sends controller, mouse or keyboard input to the game.

![Control panel](docs/ui_home.png)

## How it works

1. **Capture**: grabs frames of a window, monitor or screen area.
2. **Colour targets**: you pick a colour and it finds things of that colour, filtered by size.
3. **AI entities** (optional): your own trained model finds things colour can't tell apart, like creepers vs grass.
4. **Tracking**: smooths the outlines and keeps a lost target marked for a moment.
5. **Display**: draws outlines in an overlay on the game, or in a separate mirror window.
6. **Live export**: writes each frame's detections to `detections.json` so other programs can read them
   (turn it on with `mct set export.enabled on`).

## Download and install

1. Open the **Releases** page of this repository (right-hand side on GitHub, or `/releases`).
2. Under **Assets** of the newest release, download `MineColorTrack-Setup-<version>.exe`.
3. Run it. It installs for your Windows user only (no administrator password), adds a
   **desktop shortcut** and a **MineColorTrack** folder in the Start menu.

To uninstall, use **Start menu > MineColorTrack > Uninstall MineColorTrack**, or Windows Settings > Apps >
Installed apps. At the end it asks whether to also delete your settings and profiles; choose No to keep them
for a later reinstall.

**Updating**: from 1.6.0 on, MineColorTrack checks GitHub for a newer version when it opens and shows
**Update now** on the Home page (or Settings > Updates > Check for updates now; `mct update install` from a
terminal). It downloads the installer, closes, updates and reopens itself; settings are kept. Running a newer
installer by hand also updates in place. The check needs this repository to be public.

Windows SmartScreen may say "Windows protected your PC" because the installer is not code-signed.
Click **More info**, then **Run anyway**.

Requirements: 64-bit Windows 10 version 2004 or newer, or Windows 11. Nothing else to install.

## Quick start for Minecraft

1. Start your game. Keep its window visible (not minimised).
2. Open MineColorTrack from the desktop shortcut. Nothing is set up for you: you start with one empty
   profile, "My profile". On **Watch**, pick the game's window from the list (or a monitor), then press
   **Start** on **Home**.
3. Go to **Targets**, press **Add** and click on the thing you want outlined (for example a creeper).
   The new target switches on once its colour is picked. The live preview shows in white what will be outlined.
   Repeat for each kind of thing.
4. If grass or leaves light up too, raise **Brightness min** and **Saturation min** a little,
   lower **Hue tolerance**, or raise **Minimum size**. If the creeper is only partly white, do the opposite.
5. Click back into your game so it gets your controller input again.

Hover over any setting for an explanation, or open the **Help** page (also the "? Help" button on each page)
for illustrated instructions.

Settings save automatically. Creepers, grass and leaves are similar greens in Minecraft, so step 4
matters. Night, caves and rain change colours, so a separate profile for each (Home > Manage profiles >
Duplicate) works better than one compromise.

![Overlay with outlines](docs/overlay_outline.png)

## Finding entities with AI (pigs, villagers, players...)

Colours cannot tell a creeper from grass. An AI model can, and you make your own:

1. **Collect screenshots** while you play with the hotkey **Ctrl+Alt+S** (or **Capture screenshot** in the
   labelling tool: Entities > Open labelling tool).
2. **Label them**: add classes such as `pig`, `villager`, `player`, and drag a box around every one you see.
   Mark screenshots with none of them as **Nothing here** (background): this is what stops blocks being
   mistaken for players or mobs. For players, use one class and include every look: no armour, each armour type
   (leather, chainmail, iron, gold, diamond, netherite), different skins, near and far.
3. **Export for training**: a zip plus the training notebook.
4. **Train in Google Colab** (free GPU): open colab.research.google.com, File > Upload notebook
   (`train_minecolortrack.ipynb`), Runtime > Change runtime type > T4 GPU, Runtime > Run all, upload the zip.
   About 10 to 30 minutes later the browser downloads `minecolortrack_model.onnx`.
5. **Entities > Load model**, switch on the entities you want, press Start.

Labelled datasets from elsewhere (YOLO format, for example a Roboflow "YOLOv8" export) can be merged with
Import in the labelling tool. Nothing AI-related is built in: no model ships with MineColorTrack.

The app runs models with ONNX Runtime. The installer uses DirectML, so most graphics cards work (NVIDIA, AMD,
Intel); NVIDIA cards can be faster with TensorRT, see [NVIDIA acceleration](#nvidia-acceleration-tensorrt-and-cuda).
The Colab notebook trains with
[Ultralytics YOLO](https://docs.ultralytics.com), which is AGPL-3.0; Ultralytics considers models trained with
it to fall under that licence too. That is fine for personal use; check the licence before sharing models.

## NVIDIA acceleration (TensorRT and CUDA)

**Entities > AI device** chooses where the model runs. **Automatic** (the default) tries the fastest first and moves
on by itself when one does not start: **TensorRT** (NVIDIA, fastest), **CUDA** (NVIDIA), **DirectML** (any DirectX 12
graphics card), then the **processor**. A device that is skipped is written to `error.log` and explained under the
model on the Entities page, including which NVIDIA libraries are missing and which versions are needed.

TensorRT and CUDA need the NVIDIA build of ONNX Runtime (`onnxruntime-gpu`). It cannot be installed next to the
DirectML build (both provide the `onnxruntime` module), so the installer keeps DirectML and the NVIDIA build runs
from source in its own environment:

```
py -3 -m venv .venv-nvidia
.venv-nvidia\Scripts\activate
pip install -r requirements-nvidia.txt
python run.py
```

MineColorTrack does not include NVIDIA's libraries; install them yourself. For the current `onnxruntime-gpu`
(1.27 or newer, built with CUDA 13.0; versions 1.21 to 1.26 are built with CUDA 12.8):

1. An NVIDIA graphics card and a recent driver: the 580 series or newer for CUDA 13 (570.65 or newer for CUDA 12.8).
2. The CUDA runtime and cuDNN 9: either `pip install onnxruntime-gpu[cuda,cudnn]` (puts them in the environment), or
   NVIDIA's CUDA Toolkit and cuDNN installers with their `bin` folders on `PATH`.
3. For TensorRT only: TensorRT 10 for the same CUDA major version, either `pip install "tensorrt-cu13>=10,<11"`
   (use `tensorrt-cu12` for CUDA 12; the pin matters, because pip's newest is TensorRT 11, which ONNX Runtime does not
   load yet) or NVIDIA's installer with its `lib` folder on `PATH`. MineColorTrack finds the pip copy by itself.

Without them, TensorRT and CUDA are skipped with a message. In the NVIDIA build DirectML is not available, so the
next step is the processor; in the installer's DirectML build, choosing TensorRT or CUDA falls back to DirectML.

The first time TensorRT runs a model it builds an *engine* for that model and graphics card, which can take a few
minutes; colour targets keep working and the app shows "Building engine". Engines are saved in
`%APPDATA%\MineColorTrack\trt_cache`, so later starts take seconds. Changing the model, the card or **TensorRT half
precision (FP16)** (on by default) builds a new one; deleting the folder forces a rebuild. FP16 is faster on RTX
cards; boxes stay within about a pixel of full precision.

To see the effect: the Home page shows the milliseconds per frame for capture, colour, preprocess, inference,
postprocess and draw; `mct status` reports the same as `timings_ms`, plus the AI device in use. `mct model benchmark
shot.png` times every installed device on a screenshot (TensorRT in FP16 and FP32) and compares each one's boxes with
the processor's FP32 result.

Version requirements come from the ONNX Runtime documentation for the
[CUDA](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements) and
[TensorRT](https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html#requirements) execution
providers and NVIDIA's [CUDA release notes](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/).

## Command line and AI agents (`mct`)

`mct.exe` is installed next to MineColorTrack (and added to PATH if you keep that option ticked in Setup).
It controls everything in the control panel; every command prints JSON, and changes apply live while the
app is open (otherwise the settings file is edited). Settings > **Copy instructions for an AI agent** copies a
ready-made explanation to paste into an agent.

```
mct guide                                 # all commands, with examples
mct schema                                # every setting: type, allowed values, limits, explanation
mct status                                # running? fps, targets in view, capture, AI device, ms per stage
mct get capture.fps
mct set capture.fps 120
mct set outline.thickness 8 --profile "Night"
mct windows                               # open windows
mct watch window --title "PS Remote Play" --exe RemotePlay.exe
mct profile new Night
mct target pick Creeper shot.png 384 140  # colour from a screenshot pixel, with suggested ranges
mct target set Creeper min_area 200
mct detect shot.png --out marked.png      # what the current profile would outline
mct model load C:\models\minecolortrack_model.onnx
mct set ai.device tensorrt                # auto | tensorrt | cuda | directml | cpu
mct model benchmark shot.png              # ms per stage on each AI device; boxes compared with the processor
mct entity set player outline_color "#FF00FF"
mct start | stop | toggle-outline | screenshot | show | quit
mct dataset info | import roboflow.zip | export training.zip
```

Errors are JSON on stderr with exit code 1. The connection to the running app is local and protected by a
random key stored next to the settings file, so only your Windows user can use it.

## What you can set

| Page | Options |
|---|---|
| Home | Start/stop, profile, outline switch, a switch per target, what is being watched, overlay or mirror window |
| Watch | Any open window (picked from a list, followed when it moves; matched by title and program), any monitor, or a dragged screen area; frames per second; processing resolution; optional circle or square zone in the middle (only look there) with its own colour and see-through line and inside |
| Targets | Any number of colours per profile with name, hue tolerance, saturation and brightness range, size limits and outline colour; on-screen colour picker that suggests tolerances; live preview |
| Entities | AI detection on/off, load your .onnx model, confidence, AI device (automatic, TensorRT, CUDA, DirectML or processor) and TensorRT FP16, a switch and outline colour per entity, labelling tool, Google Colab, training notebook, dataset folder |
| Outline | Box, corner brackets or ellipse; thickness; spacing; black backing line; per-target or single colour; arrow or dot marker; names; blinking; dashed "last seen" outline |
| Tracking | Smoothing, how long a lost target stays marked, joining pieces into one target, speck filter |
| Hotkeys | Global hotkeys that work while the game has focus (defaults: Ctrl+Alt+A start/stop, Ctrl+Alt+P next profile, Ctrl+Alt+O outline on/off, Ctrl+Alt+S save screenshot for labelling) |
| Settings | Dark, light or high-contrast (black and yellow) theme; text size; start on launch; keep running in the system tray |
| Help | Illustrated explanations of every page, tuning colours, overlay vs. mirror, troubleshooting |

There are no built-in presets: every target and profile is your own. Use Home > Manage profiles to make new
empty profiles or duplicates. Updating from 1.0 or 1.1 removes the presets those versions created (unless you
changed them) and the old PS Remote Play window default; everything you made yourself is kept.
Settings file: `%APPDATA%\MineColorTrack\config.json`. Crash details and skipped AI devices, if any: `error.log` in
the same folder. TensorRT engines: `trt_cache` in the same folder.

## Overlay vs. mirror window

- **Overlay** sits exactly on top of what you watch, follows a watched window and is click-through.
  Windows has to hide it from screen capture so the program never detects its own drawings
  (Windows 10 version 2004 or newer). MineColorTrack tests this when it starts and switches to the
  mirror window if it fails.
- **Mirror** shows the processed picture in its own window, for example on a second monitor.
  Keep the game itself visible somewhere (it can be small, but not minimised or covered).

## Limits

- Colour matching only. It cannot tell a creeper from green blocks of the same shade; tuning and
  size limits are how you separate them.
- Stream compression and motion blur make outlines shimmer a little. Raise **Smoothing** if it bothers you.
- Games in exclusive full screen may block capture and overlays. Use windowed or borderless mode,
  or the mirror window.

## For developers

Run from source (Python 3.10+):

```
py -3 -m pip install -r requirements.txt
py -3 run.py
py -3 -m pip install pytest pillow && py -3 -m pytest tests
```

For TensorRT/CUDA, use `requirements-nvidia.txt` instead, in a separate virtual environment (see NVIDIA
acceleration). The provider tests mock `onnxruntime.get_available_providers()`, so no graphics card is needed.

Releases are built by `.github/workflows/release.yml` on a Windows runner when a `v*` tag is pushed:
unit tests, PyInstaller (`packaging/MineColorTrack.spec`), a `--selftest` of the built app, the Inno Setup
installer (`packaging/MineColorTrack.iss`), a silent test install that checks the desktop shortcut,
and finally the GitHub release.

The AI pipeline is tested end to end with `MCT_E2E=1 python -m pytest tests/test_training_e2e.py -s` (needs
`ultralytics`): it labels synthetic screenshots, exports the zip, runs the notebook's own code, and checks the
exported model with the app's detector. `packaging/make_notebook.py` writes the notebook.

From source, the command-line tool is `python mct.py ...`.

Code map: `colorassist/vision.py` colour detection and tracking (numpy/OpenCV, no GUI), `detector.py` AI model
runtime, `dataset.py` labelled screenshots, import and export, `labeler.py` labelling tool, `engine.py` capture
thread, `view.py` overlay/mirror drawing, `panel.py` and `ui.py` control panel and themes,
`winplat.py` Windows API calls (window list, capture exclusion, hotkeys), `capture.py` screen capture, `cli.py` and `ipc.py` the `mct` tool and its connection to the app, `help_text.py` all tooltips and
Help page text, `app.py` wiring, tray, self-test. Help pictures are rendered by
`packaging/make_help_images.py`.

## Licence

Copyright (C) 2026 EQQX0.

MineColorTrack is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
option) any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE).

It is built with PyQt6 (GPL-3.0), Qt, OpenCV, NumPy, ONNX Runtime, dxcam, mss and others; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
