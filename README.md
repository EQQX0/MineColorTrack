# MineColorTrack

A low-vision helper for Windows, built with Minecraft in mind. It watches any open window (PS Remote Play,
the Xbox app, a capture-card viewer, a PC game) or any monitor, finds things of a chosen colour (for example
creepers) and draws clear outlines around them.

It only draws on screen. It never sends controller, mouse or keyboard input to the game.

![Control panel](docs/ui_home.png)

## Download and install

1. Open the **Releases** page of this repository (right-hand side on GitHub, or `/releases`).
2. Under **Assets** of the newest release, download `MineColorTrack-Setup-<version>.exe`.
3. Run it. It installs for your Windows user only (no administrator password), adds a
   **desktop shortcut** and a **MineColorTrack** folder in the Start menu.

To uninstall, use **Start menu > MineColorTrack > Uninstall MineColorTrack**, or Windows Settings > Apps >
Installed apps. At the end it asks whether to also delete your settings and profiles; choose No to keep them
for a later reinstall.

Windows SmartScreen may say "Windows protected your PC" because the installer is not code-signed.
Click **More info**, then **Run anyway**.

Requirements: 64-bit Windows 10 version 2004 or newer, or Windows 11. Nothing else to install.

## Quick start for Minecraft

1. Start your game (for example Minecraft through PS Remote Play). Keep its window visible (not minimised).
2. Open MineColorTrack from the desktop shortcut. On **Watch**, pick the game's window from the list
   (or a monitor), choose a profile such as "Minecraft: creepers" on **Home** and press **Start**.
3. Go to **Targets**, press **Pick colour from the game...** and click on a creeper.
   The live preview shows in white what will be highlighted.
4. If grass or leaves light up too, raise **Brightness min** and **Saturation min** a little,
   lower **Hue tolerance**, or raise **Minimum size**. If the creeper is only partly white, do the opposite.
5. Click back into your game so it gets your controller input again.

Hover over any setting for an explanation, or open the **Help** page (also the "? Help" button on each page)
for illustrated instructions.

Settings save automatically. Creepers, grass and leaves are similar greens in Minecraft, so step 4
matters. Night, caves and rain change colours, so a separate profile for each (Home > Manage profiles >
Duplicate) works better than one compromise.

![Overlay with outlines](docs/overlay_outline.png)

## What you can set

| Page | Options |
|---|---|
| Home | Start/stop, profile, outline switch, a switch per target, what is being watched, overlay or mirror window, crosshair |
| Watch | Any open window (picked from a list, followed when it moves; matched by title and program), any monitor, or a dragged screen area; frames per second; processing resolution |
| Targets | Any number of colours per profile with name, hue tolerance, saturation and brightness range, size limits and outline colour; on-screen colour picker that suggests tolerances; live preview |
| Outline | Box, corner brackets or ellipse; thickness; spacing; black backing line; per-target or single colour; arrow or dot marker; names; blinking; dashed "last seen" outline |
| Tracking | Smoothing, how long a lost target stays marked, joining pieces into one target, speck filter |
| Hotkeys | Global hotkeys that work while the game has focus (defaults: Ctrl+Alt+A start/stop, Ctrl+Alt+P next profile, Ctrl+Alt+O outline on/off) |
| Settings | Dark, light or high-contrast (black and yellow) theme; text size; start on launch; keep running in the system tray |
| Help | Illustrated explanations of every page, tuning colours, overlay vs. mirror, troubleshooting |

Five Minecraft presets are included (creepers, zombies, night eyes, common hostiles, strong low-vision).
Their colours are starting points only; re-pick them in your own game.
Settings file: `%APPDATA%\MineColorTrack\config.json`. Crash details, if any: `error.log` in the same folder.

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

Releases are built by `.github/workflows/release.yml` on a Windows runner when a `v*` tag is pushed:
unit tests, PyInstaller (`packaging/MineColorTrack.spec`), a `--selftest` of the built app, the Inno Setup
installer (`packaging/MineColorTrack.iss`), a silent test install that checks the desktop shortcut,
and finally the GitHub release.

Code map: `colorassist/vision.py` detection and effects (numpy/OpenCV, no GUI), `engine.py` capture
thread, `view.py` overlay/mirror drawing, `panel.py` and `ui.py` control panel and themes,
`winplat.py` Windows API calls (window list, capture exclusion, hotkeys), `help_text.py` all tooltips and
Help page text, `app.py` wiring, tray, self-test. Help pictures are rendered by
`packaging/make_help_images.py`.
