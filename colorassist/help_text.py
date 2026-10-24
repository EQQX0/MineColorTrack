"""All user-facing explanations: tooltips for every control, and the Help page sections."""

# key -> (text, tooltip). The text is the row label, or the switch's own text; "" for buttons.
TIPS = {
    # Home
    "start": ("", "Start or stop watching the screen and drawing outlines.\n"
                  "You can also use the Start / stop hotkey while playing."),
    "profile": ("Profile", "A profile is a saved set of targets and outline settings.\n"
                           "Use different profiles for different games, biomes or times of day."),
    "manage_profiles": ("", "Duplicate, rename or delete the current profile,\nor bring back the built-in presets."),
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
    "capture.fps": ("Frames per second", "How often the screen is checked. Higher follows fast mobs more closely "
                                         "but uses more CPU.\n30 is a good start."),
    "capture.scale": ("Processing resolution", "Size at which each frame is analysed. 100% finds the smallest, "
                                               "farthest targets;\nlower values are faster. Outlines are always "
                                               "drawn at full size."),
    # Targets
    "target_list": ("", "Targets in this profile. Select one to edit it."),
    "target_add": ("", "Add a new target to this profile."),
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
    # Settings
    "display.theme": ("Theme", "Colours of this window. High contrast uses black, white and yellow\n"
                               "for the easiest reading."),
    "display.ui_font_pt": ("Text size", "Size of all text in this window."),
    "display.start_on_launch": ("Start watching when the program opens", "Start watching automatically when MineColorTrack opens."),
    "display.close_to_tray": ("Closing the window keeps it running in the system tray", "When on, closing this window keeps MineColorTrack running as an icon\n"
                                  "next to the clock. Right-click that icon to quit."),
    "display.mirror_on_top": ("Keep the mirror window on top", "Keep the mirror window above all other windows."),
    "open_folder": ("", "Open the folder that holds your settings file and the error log."),
    "help_button": ("", "Explain this page, with pictures."),
}

NAV_TIPS = {
    "Home": "Start and stop, choose a profile, switch outlines and targets on or off.",
    "Watch": "Choose which window, monitor or screen area to watch.",
    "Targets": "The colours to look for, and the colour picker.",
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
<li><b>Profile</b>: a saved set of targets and outline settings. Five Minecraft presets are included.</li>
<li><b>Outline switch</b>: show or hide outlines. <b>Options</b> opens all outline settings.</li>
<li><b>Targets in this profile</b>: switch each colour on or off. The square on the left is the colour searched
for, the square on the right is its outline colour.</li>
<li><b>Watching</b>: what is being watched right now, and <b>Change</b> to pick another window or monitor.</li>
</ol>
<p>First time: choose what to watch, press Start, then go to Targets and pick your colours from the game.
Afterwards click back into your game so it receives your controller again.</p>
"""),
    ("watch", "Choosing what to watch", "help_watch.png", """
<ol>
<li><b>Watch</b>: an open window, a whole monitor, or a part of the screen you drag.</li>
<li><b>Window</b>: every window that is open right now. Pick the one showing your game (for example PS Remote Play,
the Xbox app, a capture-card viewer or a PC game). <b>Refresh</b> updates the list. The overlay follows the window
when you move or resize it. <b>Title contains</b> and <b>Program</b> are filled in for you; they help find the
window again next time, even if its title changes.</li>
<li><b>Monitor</b>: which screen to watch when Watch is set to a whole monitor.</li>
<li><b>Region</b>: <b>Select region on screen</b> shows a still picture of the monitor; drag a box around the
game picture.</li>
<li><b>Performance</b>: frames per second and processing resolution. Lower them if your PC struggles.</li>
</ol>
<p>Tip: watching only the game window gives fewer false matches than a whole monitor, because the taskbar and
other windows are left out. Games in exclusive full screen may block capture; use windowed or borderless mode.</p>
"""),
    ("targets", "Targets and colours", "help_targets.png", """
<ol>
<li><b>List</b>: the targets of this profile. Add, Copy and Remove are below it.</li>
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
<li><b>Profiles</b> (Home, Manage profiles): duplicate one before experimenting, rename it, delete it, or restore
the built-in presets. The profile in use is remembered.</li>
<li><b>Hotkeys</b> work anywhere, also while the game is active: Start / stop, Next profile, Outline on/off.
Type a combination such as Ctrl+Alt+O and press Apply hotkeys.</li>
<li><b>Tracking</b>: Smoothing makes outlines steadier; Join pieces makes one outline per mob; Speck filter
removes single-pixel noise.</li>
<li><b>Settings</b>: dark, light or high-contrast theme, text size, start automatically, keep running in the
system tray. Everything is saved automatically.</li>
</ul>
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
