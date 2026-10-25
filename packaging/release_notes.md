## Download

Download **MineColorTrack-Setup-<version>.exe** below (under "Assets"), run it, and follow the installer.
It installs for your Windows user only (no administrator password needed), adds a **desktop shortcut**
and a **MineColorTrack** folder in the Start menu.

To uninstall: **Start menu > MineColorTrack > Uninstall MineColorTrack** (or Windows Settings > Apps).
It asks whether to also delete your settings and profiles.

Windows SmartScreen may say "Windows protected your PC" because the installer is not code-signed.
Click **More info**, then **Run anyway**.

Requirements: Windows 10 (version 2004 or newer) or Windows 11, 64-bit. Nothing else to install.

## Getting started

1. Start your game. Keep its window visible.
2. Open MineColorTrack from the desktop shortcut. On **Watch**, pick the game window from the list (or a monitor),
   then press **Start** on **Home**.
3. On **Targets** press **Add** and click on the thing to outline. Fine-tune with the live preview.
4. Click back into your game so it receives your controller again.

Every setting has a tooltip, and the **Help** page explains everything with pictures.

## What's new in 1.6.3

- MineColorTrack is now free software under the **GNU GPL v3 or later** (Copyright (C) 2026 EQQX2).
  The licence and a list of the bundled third-party software are installed with the app and shown under
  Settings > About.

## What's new in 1.6.2

- Removed "Add Minecraft armour targets" (added in 1.6.1). Armour targets you already added stay in your
  profile until you delete them on the Targets page.

## What's new in 1.6.0

- **Update check**: MineColorTrack looks for a newer release when it opens and shows **Update now** on the Home
  page. One click downloads the installer, updates and reopens MineColorTrack; settings are kept.
  Settings > Updates: turn the check off or check now. "Skip this version" hides one release.
- `mct update check` and `mct update install` for scripts and agents.

## What's new in 1.5.0

- **Command line for scripts and AI agents**: `mct.exe` controls everything (settings, profiles, colour targets,
  AI model and entities, what to watch, start/stop, screenshots, the labelling dataset) and prints JSON.
  Changes apply live while MineColorTrack is open. `mct guide` and `mct schema` explain everything.
- Setup can add `mct` to PATH (ticked by default); uninstalling removes it again.
- Settings > **Copy instructions for an AI agent**.
- Opening MineColorTrack while it is already running brings the open window forward instead of a second copy.

## What's new in 1.4.0

- **Faster screen capture**: Windows Desktop Duplication, made for high frame rates (Watch > Performance >
  Capture method). Automatic uses it when it works and falls back to the classic method otherwise.
  The Home page shows which method is in use.

## What's new in 1.3.1

- Frames per second can go up to 120 (Watch > Performance).

## What's new in 1.3.0

- **Find entities with AI**: outline pigs, villagers, players or anything else by shape, with a model you train
  yourself. New **Entities** page: load a model, confidence, a switch and colour per entity.
- **Labelling tool**: capture screenshots (or press Ctrl+Alt+S while playing), draw boxes, mark "nothing here"
  backgrounds, import labelled YOLO datasets, and export a zip for training. Built-in tips say what your dataset
  still needs.
- **Free training in Google Colab** with the included notebook; it gives back a model file to load.
- Runs on most graphics cards (DirectML), or on the processor.

## What's new in 1.2.0

- No built-in defaults: you start with one empty profile and make your own targets.
  Updating removes the old presets (unless you edited them) and the old PS Remote Play window default.
- **Add** on the Targets page opens the colour picker straight away; new targets switch on once picked.
- Manage profiles has **New empty profile**.

## What's new in 1.1.1

- "Uninstall MineColorTrack" shortcut in the Start menu folder.
- The uninstaller asks whether to also delete your settings and profiles.
- Setup and the uninstaller ask you to close MineColorTrack first if it is running.

## What's new in 1.1.0

- Watch any open window (chosen from a list, followed by title and program) or any monitor.
- Tooltips on every setting and a new illustrated Help page.
- Simplified to outlines only: the high-contrast view and the magnifier were removed.

MineColorTrack only draws on screen. It never sends controller, mouse or keyboard input to the game.
