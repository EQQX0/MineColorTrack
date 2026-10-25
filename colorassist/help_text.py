# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""All user-facing explanations: tooltips for every control, and the Help page sections."""

# key -> (text, tooltip). The text is the row label, or the switch's own text; "" for buttons.
TIPS = {
    # Home
    "start": ("", "Start or stop watching the screen and drawing outlines.\n"
                  "You can also use the Start / stop hotkey while playing."),
    "profile": ("Profile", "A profile is a saved set of targets and outline settings.\n"
                           "Use different profiles for different games, biomes or times of day."),
    "manage_profiles": ("", "Make a new empty profile, or duplicate, rename or delete the current one."),
    "outline_switch": ("Show outlines", "Show or hide the outlines for this profile."),
    "outline_options": ("", "Open the Outline page with all outline settings."),
    "home_target": ("", "Turn this target on or off. Targets that are off are not searched for."),
    "edit_targets": ("", "Open the Targets page to add targets and pick their colours from the game."),
    "change_watch": ("", "Open the Watch page to choose which window, monitor or screen area to watch."),
    "display.mode": ("Show outlines", "Overlay: draws directly on top of the watched window or monitor. "
                                      "Clicks pass straight through it.\n"
                                      "Mirror window: shows a copy of the watched picture with outlines in its own "
                                      "window, for example on a second monitor."),
    "display.crosshair": ("Crosshair at the centre of the picture", "Draw a cross in the middle of the watched picture,\nto help find the screen centre."),
    "display.crosshair_color": ("Crosshair colour", "Colour of the centre cross. A black border is always drawn "
                                                    "around it so it stays visible."),
    # Watch
    "capture.source": ("Watch", "What to scan for your target colours:\n"
                                "- An open window: follows that window when it moves or is resized.\n"
                                "- A whole monitor: everything on one screen.\n"
                                "- Part of the screen: a box you drag yourself."),
    "window_list": ("Window", "All windows that are open right now. Pick the one that shows your game.\n"
                              "Press Refresh after opening a new window."),
    "refresh": ("", "Read the list of open windows and monitors again."),
    "capture.window_title": ("Title contains", "Filled in when you pick a window. The window whose title contains "
                                               "this text is watched.\nShorten it if the title changes while you "
                                               "play, for example remove a version number."),
    "capture.window_exe": ("Program", "Program file of the picked window, for example RemotePlay.exe.\n"
                                      "Used to find the window again even if its title changes. "
                                      "Leave empty to match by title only."),
    "capture.monitor": ("Monitor", "Which screen to watch when Watch is set to a whole monitor.\n"
                                   "Also the screen shown when you drag a region."),
    "region": ("Region", "The screen area watched when Watch is set to part of the screen."),
    "select_region": ("", "Shows a still picture of the chosen monitor.\n"
                          "Drag a box around the game picture and release."),
    "capture.fps": ("Frames per second", "How often the screen is checked, up to 120. Higher follows fast mobs "
                                         "more closely but uses more CPU.\n30 is a good start; above 60 only helps "
                                         "on a 120 Hz screen with a fast PC.\nThe speed actually reached is shown "
                                         "on the Home page while running."),
    "capture.method": ("Capture method", "How the screen is read.\n"
                                         "- Fast: Windows Desktop Duplication, made for high frame rates.\n"
                                         "- Compatible: the classic screen copy; slower on big areas.\n"
                                         "- Automatic: fast when it works on this PC, otherwise compatible.\n"
                                         "The method in use is shown on the Home page while running."),
    "capture.scale": ("Processing resolution", "Size at which each frame is analysed. 100% finds the smallest, "
                                               "farthest targets;\nlower values are faster. Outlines are always "
                                               "drawn at full size."),
    # Targets
    "target_list": ("", "Targets in this profile. Select one to edit it."),
    "target_add": ("", "Add a new target to this profile and pick its colour from the game straight away.\n"
                     "It switches on once its colour is picked."),
    "target_copy": ("", "Make a copy of the selected target, for example to track the same mob at night."),
    "target_remove": ("", "Delete the selected target from this profile."),
    "pick": ("", "Freezes the current picture. Click on the thing you want outlined:\n"
                 "its colour is copied and sensible ranges are suggested."),
    "target.enabled": ("Enabled", "Search for this target. Turn it off to ignore it without deleting it."),
    "target.name": ("Name", "Shown in the lists and, if names are on, above the outline."),
    "target.color": ("Colour", "The colour to look for. Click to choose it by hand;\n"
                               "it is usually easier to use Pick colour from the game."),
    "target.hue_tol": ("Hue tolerance", "How far the shade may differ from the chosen colour, in degrees around "
                                        "the colour wheel.\nLower = only very similar shades. Higher = more matches, "
                                        "including unwanted ones."),
    "target.sat_min": ("Saturation min", "Minimum colour strength.\nRaise it to ignore greyish or washed-out "
                                         "pixels such as fog or stone."),
    "target.sat_max": ("Saturation max", "Maximum colour strength. Rarely needed;\nlower it to ignore very vivid "
                                         "colours."),
    "target.val_min": ("Brightness min", "Minimum brightness.\nRaise it to ignore shadows and dark blocks such "
                                         "as leaves."),
    "target.val_max": ("Brightness max", "Maximum brightness.\nLower it to ignore bright highlights or the sky."),
    "target.min_area": ("Minimum size", "A match must cover at least this many pixels of the watched picture to "
                                        "get an outline.\nRaise it to ignore small specks of grass or leaves."),
    "target.max_area": ("Maximum size", "Matches bigger than this are ignored, for example a whole field of "
                                        "grass.\n0 means no limit."),
    "target.outline_color": ("Outline colour", "Colour of this target's outline and marker\n(when Outline uses "
                                               "each target's own colour)."),
    "preview": ("", "Live black-and-white view of what the selected target matches.\n"
                    "White pixels would get an outline."),
    # Outline
    "outline.enabled": ("Draw outlines", "Draw outlines around matches. Hotkey: Outline on/off."),
    "outline.style": ("Style", "Shape drawn around each target: a full box, only the four corners, or an ellipse."),
    "outline.thickness": ("Line thickness", "Width of the outline in pixels."),
    "outline.padding": ("Space around target", "Gap between the target and its outline,\n"
                                               "so the outline does not cover the target."),
    "outline.marker": ("Marker above target", "An arrow or dot above each outline, easier to spot from a distance."),
    "outline.black_border": ("Black backing line (visible on any background)", "Draws a black line behind the outline so it stays visible on light and dark "
                                 "backgrounds."),
    "outline.use_target_color": ("Use each target's own outline colour", "On: each target uses its own outline colour from the Targets page.\n"
                                     "Off: all outlines use the single colour below."),
    "outline.color": ("Single colour", "Outline colour for all targets when “Use each target's own outline "
                                       "colour” is off."),
    "outline.labels": ("Show target names", "Write the target's name above its outline."),
    "outline.blink": ("Blink", "Make outlines flash about three times a second to draw attention."),
    "outline.show_held": ("Dashed outline for a moment after a target is lost", "If a target disappears for a moment (behind a block, or a dropped frame),\n"
                              "keep a dashed outline where it was for a short time."),
    # Tracking
    "tracking.smoothing": ("Smoothing", "Averages outline positions over time.\nHigher = steadier outlines that "
                                        "trail fast mobs slightly. Lower = more responsive but jittery."),
    "tracking.hold_frames": ("Keep lost targets for", "How many frames the dashed outline stays after a target is "
                                                      "lost.\nAt 30 frames per second, 30 frames is one second."),
    "tracking.merge_distance": ("Join pieces closer than", "Matched areas closer than this many pixels count as one "
                                                           "target,\nso a creeper's head, body and legs get one "
                                                           "outline instead of several."),
    "tracking.noise_filter": ("Speck filter", "Removes tiny isolated matching pixels before looking for targets.\n"
                                              "0 = off. Higher removes more, but can erase very distant targets."),
    # Hotkeys
    "hotkeys.toggle_overlay": ("Start / stop", "Starts or stops watching, like the Start button.\n"
                                               "Works while the game has focus."),
    "hotkeys.next_profile": ("Next profile", "Switches to the next profile in the list."),
    "hotkeys.toggle_outline": ("Outline on/off", "Shows or hides outlines without stopping."),
    "hotkeys_apply": ("", "Activate the hotkeys typed above. The line below lists any that could not be used,\n"
                          "for example because another program already uses them."),
    # Entities (AI)
    "detection.enabled": ("Find entities with an AI model", "Outline entities your own AI model recognises, such "
                                                            "as pigs, villagers or players.\nWorks together with "
                                                            "the colour targets."),
    "load_model": ("", "Choose the .onnx model file you trained with the Google Colab notebook."),
    "clear_model": ("", "Stop using this model in this profile."),
    "model_file": ("Model", "The AI model used by this profile. Make one with the labelling tool and Google Colab."),
    "detection.confidence": ("Confidence", "How sure the model must be before something is outlined.\n"
                                           "Higher = fewer mistakes but more misses. Lower = finds more, including "
                                           "wrong things.\n40 to 60% is a good start."),
    "ai.device": ("AI device", "Where the model runs. Automatic tries the fastest first and moves on when one "
                               "does not work:\nTensorRT (NVIDIA, fastest), CUDA (NVIDIA), DirectML (any DirectX 12 "
                               "graphics card), then the processor.\nTensorRT and CUDA need the NVIDIA build "
                               "and NVIDIA's CUDA libraries (see Help). Choose Processor only if you see errors."),
    "ai.tensorrt_fp16": ("TensorRT half precision (FP16)", "Lets TensorRT use 16-bit numbers: faster on RTX cards, "
                                                           "with the same boxes within a pixel or so.\nOnly used "
                                                           "with TensorRT. Changing it builds the engine again."),
    "timings": ("", "How long each step of one frame takes, in milliseconds, averaged over recent frames:\n"
                    "capture (screen picture), colour (colour targets), preprocess, inference and postprocess (AI "
                    "model, plus tracking),\ndraw (preparing and painting the outlines). `mct status` shows the "
                    "same numbers."),
    "entity_switch": ("", "Outline this entity. Turned-off entities are ignored."),
    "entity_colour": ("", "Outline colour for this entity."),
    "open_labeler": ("", "Open the labelling tool: collect screenshots and draw boxes around entities\nto teach "
                         "your own model."),
    "open_colab": ("", "Open Google Colab in your browser, where the training notebook runs for free."),
    "save_notebook": ("", "Save a copy of the training notebook (.ipynb) to upload to Google Colab."),
    "dataset_dir": ("Dataset folder", "Where your labelled screenshots are stored."),
    "change_dataset": ("", "Use a different folder for labelled screenshots."),
    "hotkeys.save_screenshot": ("Save screenshot for labelling", "Saves what you are watching into your dataset "
                                                                 "while you play,\nso you can label it later in "
                                                                 "the labelling tool."),
    # Labelling tool
    "lab.capture": ("", "Save what you are watching right now as a new screenshot to label.\n"
                        "While playing, use the Save screenshot hotkey instead."),
    "lab.import": ("", "Add pictures to label, or merge an already labelled dataset\n(YOLO format, for example "
                       "a Roboflow \u201cYOLOv8\u201d export)."),
    "lab.export": ("", "Make the zip to upload to the Google Colab training notebook.\nOnly labelled screenshots "
                       "are included."),
    "lab.colab": ("", "Open Google Colab in your browser."),
    "lab.folder": ("", "Open the dataset folder, or switch to a different one."),
    "lab.images": ("", "Your screenshots. \u2713 = labelled, \u25CB = nothing in it (background), "
                       "\u2022 = not labelled yet."),
    "lab.delete_image": ("", "Delete the selected screenshot and its boxes."),
    "lab.canvas": ("", "Drag to draw a box. Click a box to select it; Delete or right-click removes it.\n"
                       "Keys 1 to 9 choose the class or change the selected box."),
    "lab.background": ("", "This screenshot has none of your classes in it. Teaches the model what is NOT a "
                           "target,\nfor example blocks that look like armour. Shortcut: B."),
    "lab.clear": ("", "Remove all boxes from this screenshot and mark it as not labelled."),
    "lab.prev": ("", "Previous screenshot (Left arrow)."),
    "lab.next": ("", "Next screenshot (Right arrow)."),
    "lab.classes": ("", "The kinds of things you label. Click one to use it for new boxes,\n"
                        "or to change the selected box. Keys 1 to 9 do the same."),
    "lab.add_class": ("", "Add a class, for example pig, villager or player."),
    "lab.rename_class": ("", "Rename the selected class."),
    "lab.delete_class": ("", "Delete the selected class and every box of it."),
    "lab.advice": ("", "What your dataset still needs for a reliable model."),
    # Settings
    "display.theme": ("Theme", "Colours of this window. High contrast uses black, white and yellow\n"
                               "for the easiest reading."),
    "display.ui_font_pt": ("Text size", "Size of all text in this window."),
    "display.start_on_launch": ("Start watching when the program opens", "Start watching automatically when MineColorTrack opens."),
    "display.close_to_tray": ("Closing the window keeps it running in the system tray", "When on, closing this window keeps MineColorTrack running as an icon\n"
                                  "next to the clock. Right-click that icon to quit."),
    "display.mirror_on_top": ("Keep the mirror window on top", "Keep the mirror window above all other windows."),
    "copy_agent_prompt": ("", "Copies a short explanation of the mct command-line tool, to paste into an AI "
                              "agent\nso it can change MineColorTrack's settings for you."),
    "updates.check_on_start": ("Check for updates when the program opens", "Looks on GitHub for a newer "
                                                                          "MineColorTrack each time it opens\n"
                                                                          "and shows a message on the Home page."),
    "check_updates": ("", "Look on GitHub for a newer version now."),
    "update_now": ("", "Download the new installer and update. MineColorTrack closes, updates itself and opens "
                       "again;\nyour settings and profiles are kept."),
    "update_notes": ("", "Open the release page with the list of changes."),
    "update_skip": ("", "Do not mention this version again. You can still update from Settings."),
    "show_licence": ("", "Read the GNU General Public License, version 3, that MineColorTrack is released under."),
    "show_notices": ("", "Licences of the software MineColorTrack is built with (Qt, OpenCV, ONNX Runtime and "
                         "others)."),
    "show_source": ("", "Open MineColorTrack's source code on GitHub."),
    "open_folder": ("", "Open the folder that holds your settings file and the error log."),
    "help_button": ("", "Explain this page, with pictures."),
}

NAV_TIPS = {
    "Home": "Start and stop, choose a profile, switch outlines and targets on or off.",
    "Watch": "Choose which window, monitor or screen area to watch.",
    "Targets": "The colours to look for, and the colour picker.",
    "Entities": "Find things by their shape with your own AI model, and the labelling tool to make one.",
    "Outline": "How the outlines look.",
    "Tracking": "How steady the outlines are and how pieces are joined.",
    "Hotkeys": "Keyboard shortcuts that work while you play.",
    "Settings": "Theme, text size and start-up behaviour.",
    "Help": "Explanations of every part of MineColorTrack, with pictures.",
}

# Help page. Each image is in colorassist/assets/help/ (made by packaging/make_help_images.py).
# Numbers in the text match the yellow numbered badges in the pictures.
HELP = [
    ("start", "Getting started", "help_home.png", """
<p>MineColorTrack looks for chosen colours on your screen, for example a creeper's green, and draws a clear
outline around everything that matches. It only draws; it never touches your controller, mouse or keyboard.</p>
<ol>
<li><b>Start / Stop</b>: begins watching. The status next to it shows how many targets are in view.</li>
<li><b>Profile</b>: a saved set of targets and outline settings. You start with one empty profile,
“My profile”; add your own targets to it, or make more profiles under <b>Manage profiles</b>.</li>
<li><b>Outline switch</b>: show or hide outlines. <b>Options</b> opens all outline settings.</li>
<li><b>Targets in this profile</b>: switch each colour on or off. The square on the left is the colour searched
for, the square on the right is its outline colour.</li>
<li><b>Watching</b>: what is being watched right now, and <b>Change</b> to pick another window or monitor.</li>
</ol>
<p>First time: nothing is set up for you. Choose what to watch on the Watch page, press Start, then go to
Targets, press <b>Add</b> and click on the thing you want outlined. Repeat for each kind of thing.
Afterwards click back into your game so it receives your controller again.</p>
"""),
    ("watch", "Choosing what to watch", "help_watch.png", """
<ol>
<li><b>Watch</b>: an open window, a whole monitor, or a part of the screen you drag.</li>
<li><b>Window</b>: every window that is open right now. Pick the one showing your game (for example a remote-play
app, a capture-card viewer or a PC game). <b>Refresh</b> updates the list. The overlay follows the window
when you move or resize it. <b>Title contains</b> and <b>Program</b> are filled in for you; they help find the
window again next time, even if its title changes.</li>
<li><b>Monitor</b>: which screen to watch when Watch is set to a whole monitor.</li>
<li><b>Region</b>: <b>Select region on screen</b> shows a still picture of the monitor; drag a box around the
game picture.</li>
<li><b>Performance</b>: frames per second (up to 120), processing resolution, and the capture method.
Automatic uses Windows' fast Desktop Duplication when it works. Lower the numbers if your PC struggles.</li>
</ol>
<p>Tip: watching only the game window gives fewer false matches than a whole monitor, because the taskbar and
other windows are left out. Games in exclusive full screen may block capture; use windowed or borderless mode.</p>
"""),
    ("targets", "Targets and colours", "help_targets.png", """
<ol>
<li><b>List</b>: the targets of this profile. <b>Add</b> creates a target and opens the colour picker
straight away; Copy and Remove are next to it.</li>
<li><b>Pick colour from the game</b>: freezes the picture; click on the mob. Its colour and suggested ranges
are filled in.</li>
<li><b>Colour</b>: the colour searched for. Click it to choose by hand.</li>
<li><b>Ranges</b>: how close a pixel must be to that colour. See “Tuning a colour” below.</li>
<li><b>Size limits</b>: ignore matches that are too small (specks) or too big (a whole field).</li>
<li><b>Live preview</b>: white shows what will be outlined. It works while assist is running.</li>
</ol>
"""),
    ("tuning", "Tuning a colour", "help_tuning.png", """
<p>Many things in a game share similar colours. In Minecraft, creepers, grass and leaves are all green.
Use the live preview on the Targets page and adjust until only your target is white:</p>
<ul>
<li><b>Too much is white</b> (grass, leaves): lower <b>Hue tolerance</b>, raise <b>Brightness min</b> and
<b>Saturation min</b>, or raise <b>Minimum size</b>.</li>
<li><b>The target is only partly white</b>: do the opposite, a few steps at a time.</li>
<li>Lighting changes colours. Night, caves and rain often need their own copy of a target or profile.</li>
</ul>
"""),
    ("entities", "Finding entities with AI", "help_entities.png", """
<p>Colours cannot tell a creeper from grass of the same green. An AI model can: it learns what a pig, a villager
or a player looks like from screenshots you label yourself. Nothing is built in; you make your own model.</p>
<ol>
<li><b>Collect screenshots</b>: press the <b>Save screenshot for labelling</b> hotkey (Ctrl+Alt+S) while you play,
or <b>Capture screenshot</b> in the labelling tool.</li>
<li><b>Label them</b> in the labelling tool (see below).</li>
<li><b>Export for training</b>: makes a zip and a copy of the training notebook.</li>
<li><b>Train in Google Colab</b> (free): open colab.research.google.com, File &gt; Upload notebook, choose the
notebook, set Runtime &gt; Change runtime type &gt; T4 GPU, then Runtime &gt; Run all and upload the zip when asked.
It takes about 10 to 30 minutes and downloads <i>minecolortrack_model.onnx</i>.</li>
<li><b>Load the model</b> on the Entities page, switch on the entities you want and press Start.</li>
</ol>
<p>On the Entities page (picture): <b>1</b> switches AI detection on or off, <b>2</b> loads your model file,
<b>3</b> is the confidence, <b>4</b> lists the entities your model knows (switch each on or off and choose its outline
colour), <b>5</b> opens the labelling tool, Google Colab and the training notebook.</p>
<p>The <b>Confidence</b> slider decides how sure the model must be. Colour targets and AI entities can be used at the
same time. Training uses Ultralytics YOLO (AGPL-3.0 licence).</p>
<p><b>AI device</b> chooses where the model runs. <b>Automatic</b> tries the fastest first and moves on by itself
when one does not work on this PC: <b>TensorRT</b> (NVIDIA, fastest), <b>CUDA</b> (NVIDIA), <b>DirectML</b> (any
DirectX 12 graphics card: NVIDIA, AMD or Intel) and finally the <b>processor</b>. The line under the model says which
one is used and, if one was skipped, why. Skipped devices are also written to <i>error.log</i> in the settings
folder.</p>
<p>The installer comes with DirectML. TensorRT and CUDA need the NVIDIA build of the AI runtime
(<i>onnxruntime-gpu</i>, see README: NVIDIA acceleration) and NVIDIA's own libraries, which MineColorTrack does not
include: a recent NVIDIA driver, the CUDA runtime, cuDNN 9 and, for TensorRT, TensorRT 10. The message under the
model names any that are missing and the versions needed.</p>
<p>The first start with <b>TensorRT</b> builds an <i>engine</i> for your model and graphics card. This can take a
few minutes; colour targets keep working meanwhile and the Entities page shows “Building engine”. The engine
is saved in the <i>trt_cache</i> folder next to the settings, so later starts take seconds. Changing the model, the
graphics card or <b>TensorRT half precision (FP16)</b> builds a new one. FP16 is faster on RTX cards and finds the
same things; boxes may differ by about a pixel.</p>
"""),
    ("labelling", "Labelling screenshots", "help_labeling.png", """
<ol>
<li><b>Capture / Import</b>: add screenshots, or merge a labelled dataset you downloaded (YOLO format).</li>
<li><b>Screenshots</b>: \u2713 labelled, \u25CB nothing in it, \u2022 not labelled yet.</li>
<li><b>Picture</b>: drag a box tightly around every target. Click a box to select it; Delete or right-click
removes it. Left/Right arrows move between screenshots.</li>
<li><b>Classes</b>: the kinds of things you label. Keys 1 to 9 pick a class or change the selected box.</li>
<li><b>Tips</b>: what your dataset still needs.</li>
<li><b>Export for training</b>: the zip for Google Colab.</li>
</ol>
<p><b>For a reliable model</b>:</p>
<ul>
<li>Label <b>every</b> visible target in a screenshot; an unboxed target teaches the model to ignore it.</li>
<li>Aim for 100 or more boxes per class, from different distances, angles, biomes, times of day and weather.</li>
<li><b>Players</b>: use one class (for example \u201cplayer\u201d) for all of them and include every look: no armour,
leather, chainmail, iron, gold, diamond and netherite armour, different skins, holding items, sneaking, far away
and close up. Then the model learns that an armoured player is a player, not a block.</li>
<li>Save plenty of <b>background</b> screenshots (button \u201cNothing here\u201d or key B) showing blocks, ores,
item frames and builds that look like your targets but are not. This is what stops the model mistaking blocks
for players or mobs. About one in ten screenshots is a good share.</li>
<li>Labelling on your own Remote Play or capture picture works better than clean screenshots, because the model
learns the stream's blur and colours.</li>
</ul>
"""),
    ("outline", "Outline styles", "help_outline.png", """
<p>Style can be a full <b>box</b>, <b>corner brackets</b> or an <b>ellipse</b>. Thickness, the space around the
target, an arrow or dot marker above it, the target's name, and blinking are all on the Outline page.
<b>Black backing line</b> keeps outlines visible on bright and dark backgrounds. When a target is hidden for a
moment, a <b>dashed outline</b> stays where it was last seen.</p>
"""),
    ("display", "Overlay or mirror window", "help_display.png", """
<ul>
<li><b>Overlay</b> draws straight on top of what you watch. Clicks pass through it. Windows hides it from screen
capture so MineColorTrack never detects its own drawings; if that is not possible on your PC, it switches to the
mirror window automatically and tells you.</li>
<li><b>Mirror window</b> shows a copy of the watched picture with outlines in a separate, resizable window,
for example on a second monitor. Keep the game itself visible somewhere (not minimised).</li>
<li><b>Crosshair</b> marks the centre of the watched picture.</li>
</ul>
"""),
    ("profiles", "Profiles, hotkeys and settings", None, """
<ul>
<li><b>Profiles</b> (Home, Manage profiles): make a new empty profile, duplicate one before experimenting,
rename or delete it. The profile in use is remembered.</li>
<li><b>Hotkeys</b> work anywhere, also while the game is active: Start / stop, Next profile, Outline on/off,
Save screenshot for labelling.
Type a combination such as Ctrl+Alt+O and press Apply hotkeys.</li>
<li><b>Tracking</b>: Smoothing makes outlines steadier; Join pieces makes one outline per mob; Speck filter
removes single-pixel noise.</li>
<li><b>Settings</b>: dark, light or high-contrast theme, text size, start automatically, keep running in the
system tray. Everything is saved automatically.</li>
</ul>
"""),
    ("cli", "Command line and AI agents", None, """
<p>The <b>mct</b> tool (installed next to MineColorTrack, and on PATH if you ticked that during setup) controls
everything from a terminal, a script or an AI agent. Every command prints JSON. While MineColorTrack is open,
changes apply live; when it is closed, the settings file is edited.</p>
<ul>
<li><b>mct guide</b> explains all commands; <b>mct schema</b> lists every setting with allowed values.</li>
<li><b>mct status</b>, <b>mct get capture.fps</b>, <b>mct set outline.thickness 8</b></li>
<li><b>mct target pick Creeper shot.png 384 140</b> takes a colour from a screenshot;
<b>mct detect shot.png --out marked.png</b> shows what would be outlined.</li>
<li><b>mct watch window --title Minecraft</b>, <b>mct start</b>, <b>mct stop</b>, <b>mct screenshot</b></li>
</ul>
<p>Settings &gt; <b>Copy instructions for an AI agent</b> copies a ready-made explanation to paste into an agent.</p>
<p><b>Updates</b>: MineColorTrack looks for a newer version on GitHub when it opens (Settings &gt; Updates) and shows
a message on the Home page. <b>Update now</b> downloads the installer, closes MineColorTrack, updates it and opens
it again; your settings and profiles are kept. From a terminal: <b>mct update check</b> or <b>mct update install</b>.</p>
"""),
    ("trouble", "Troubleshooting", None, """
<ul>
<li><b>“Waiting for the window”</b>: the window is closed or minimised. Open it, or pick it again on the
Watch page and press Refresh.</li>
<li><b>Nothing is outlined</b>: check the live preview on the Targets page, and that the target and Outline are
switched on.</li>
<li><b>Outlines are in the wrong place</b>: the watched window moved to another monitor with different scaling.
Stop and Start again.</li>
<li><b>The game ignores the controller</b>: click on the game window so it has focus again.</li>
<li><b>Overlay not visible over the game</b>: the game uses exclusive full screen. Use borderless/windowed mode,
or the mirror window.</li>
<li>If something goes wrong, details are written to <i>error.log</i> next to the settings file (Settings,
Open settings folder).</li>
</ul>
"""),
]
