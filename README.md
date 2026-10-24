# ColorAssist

A low-vision helper for games streamed with PS Remote Play on Windows (built with Minecraft in mind).
It watches the Remote Play picture, finds things of a chosen colour (for example creepers) and makes
them easier to see. You can use outlines, a high-contrast view, a magnifier lens, or any mix of the three.

It only draws on screen. It never sends controller, mouse or keyboard input to the game.

![Overlay with outlines](docs/overlay_outline.png)
![Mirror window with high contrast and magnifier](docs/mirror_contrast_magnifier.png)

## Install (once)

1. Install Python 3.10 or newer (64-bit) from https://www.python.org/downloads/windows/ .
   During setup, tick "Add python.exe to PATH".
2. Unzip this folder anywhere, for example `Documents\ColorAssist`.
3. Double-click `install.bat`.

## Run

Double-click `start.bat`. If nothing appears, run `start_with_console.bat` to see the error message.

## Quick start for Minecraft

1. Open PS Remote Play and start Minecraft. Keep the Remote Play window visible (not minimised).
2. In ColorAssist pick a profile, for example "Minecraft: creepers", and press **Start**.
3. Go to the **Targets** tab, tick **Show preview**, press **Pick colour from the game...** and
   click on a creeper. White areas in the preview are what will be highlighted.
4. If grass or leaves light up too, raise **Brightness min** and **Saturation min** a little,
   lower **Hue tolerance**, or raise **Minimum size**. If the creeper is only partly white, do the opposite.
5. Press **Save settings**. Settings are also saved when you close the program.
6. Click back on the Remote Play window so it gets your controller input again.

Creepers, grass and leaves are similar greens in Minecraft, so step 4 matters. Night, caves and
rain change colours, so a separate profile for each (use **Duplicate**) works better than one compromise.

## Choices and settings

| Tab | What you can set |
|---|---|
| Capture & display | Follow the PS Remote Play window automatically, a whole monitor, or a dragged region; frames per second; processing resolution; overlay on the game or a separate mirror window; high-visibility crosshair; text size of the panel |
| Targets | Any number of colours per profile, each with its own name, hue tolerance, saturation and brightness range, minimum and maximum size and outline colour; on-screen colour picker that suggests tolerances; live mask preview |
| Outline | Box, corner brackets or ellipse; thickness; spacing; black backing line; per-target or single colour; arrow or dot marker; names; blinking; dashed "last seen" outline |
| High contrast | Dim the rest of the picture (0 to 100 %), turn it grey, paint targets a solid colour or boost their real colours, thicken them, add a white edge |
| Magnifier | Zoom 1.5x to 10x; size; circle or square; corner or next-to-target placement; which target to follow (smallest/farthest, largest/nearest, nearest the centre, or always the centre of the screen); extra contrast; sharp pixels; link line |
| Tracking | Smoothing (steadier vs. more responsive); how long a lost target stays marked; how close pieces must be to count as one target; speck filter |
| Hotkeys | Global hotkeys that work while the game has focus (defaults: Ctrl+Alt+A start/stop, Ctrl+Alt+P next profile, Ctrl+Alt+O outline, Ctrl+Alt+C high contrast, Ctrl+Alt+M magnifier) |

Profiles: five Minecraft presets are included (creepers, zombies, night eyes, common hostiles, strong
low-vision). Their colours are starting points only. Re-pick colours in your own game.
**Restore presets** brings back any you deleted.

Settings file: `%APPDATA%\ColorAssist\config.json`. Start with `start.bat --reset` to ignore it once.

## Overlay vs. mirror window

- **Overlay** sits exactly on top of the Remote Play picture and follows the window. It is click-through.
  Windows has to hide it from screen capture so the program never detects its own drawings. That needs
  Windows 10 version 2004 or newer. ColorAssist tests this when it starts. If it fails, it switches
  to the mirror window and tells you.
- **Mirror** shows the processed picture in its own window. Put it on a second monitor, or full screen,
  and keep Remote Play visible somewhere (it can be small, but not minimised or covered).

High contrast replaces the picture with a processed copy, so it runs a few frames behind the live stream.

## Limits

- Colour matching only. It cannot tell a creeper from green blocks of the same shade. Tuning
  (step 4 above) and the size limits are how you separate them.
- Stream compression and motion blur make outlines shimmer a little. Raise **Smoothing** if it bothers you.
- If Remote Play runs in exclusive full screen, overlays may not show on top. Use windowed or
  maximised Remote Play, or the mirror window.
- Global hotkeys and window following are Windows-only.

## For developers

```
py -3 -m pip install -r requirements.txt pytest pillow
py -3 -m pytest tests
```

`colorassist/vision.py` has the detection and effects (numpy/OpenCV, no GUI). `engine.py` does capture
on a background thread. `view.py` draws. `panel.py` is the control panel. `winplat.py` has the Windows API calls.
