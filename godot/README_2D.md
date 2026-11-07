# Original 2D recorded battlefield viewer

**In-game view switching:** use **2D view** in the main battlefield HUD to see the
current native battle, deployment or replay. Use **3D view** to return. This keeps
the same simulation/replay clock, current time, selection, speed, pause state and
orders; no demo is loaded. Live movement, facing gestures and formation controls
remain available. The instructions below describe the preserved legacy standalone
recording scene, rather than the current in-game view switch.


This document describes the preserved `scenes/battlefield.tscn`. The project's default scene is now 3D; see [README.md](README.md). In the editor, open the 2D scene and press F6 to run it; F5 runs the default 3D scene.

This is a Godot 4 presentation prototype alongside the working Python game.
It plays actual Python outcomes and does not execute battle rules.

## Run

Install [Godot 4.7.2 standard or .NET](https://godotengine.org/download/), extract it, and put its executable on PATH as `godot` (or use its full path). No addons, textures or C# compiler are needed for this GDScript viewer. The installed standard Linux 4.7.2 build was tested. .NET support is a future stage; see [the audit and SDK requirements](../MIGRATION.md).

From the repository root:

```bash
godot --path godot --scene res://scenes/battlefield.tscn
# Or open the 2D battlefield scene in the editor, then press F6.
godot --editor --path godot
```

The completed 12-regiment example in `recordings/combined-arms/` loads by default. It includes mixed terrain, specialist infantry, cavalry, artillery, volleys, cannonball impacts, charges, routs, rallies and an actual battle result. **Open recording** selects another recording's `metadata.json` from the filesystem.

- Space or Play/Pause; speed dropdown: 0.25×, 0.5×, 1×, 2×, 4×. Number keys 1/2/4 also set speed.
- Home or Restart starts from the first frame. Drag/click the timeline to seek, including backwards. Playback pauses at the final frame.
- Wheel zooms around the cursor; middle-drag, WASD or arrows pan; F fits the battlefield. Coordinates remain metres at every map size.
- Click any regiment to inspect its name/category/archetype, commander, army, strength, morale, cohesion, formation, state, order, actual target, charge/pursuit state, momentum and speed. Escape or clicking empty ground deselects. The information panel scrolls on small windows.
- Army-coloured footprints use recorded dimensions; arrows show facing. Cavalry has chevrons, artillery gun markers, loose infantry dispersed dots, and specialist letter labels. Gold outlines select; a gold connector/ring shows the actual target. Cosmetic soldiers are not entities.

## Record a Python battle

Use the existing Python environment (`python -m venv .venv`, activate it, `pip install -e '.[dev]'` if not already installed). Recording is headless and does not initialize Pygame.

```bash
.venv/bin/python -m migration_tools.record_battle --seed 7 --duration 650 --output recordings/my-battle
godot --path godot --scene res://scenes/battlefield.tscn -- --recording="$PWD/recordings/my-battle/metadata.json"

# Short, deliberately duration-limited large-battle recording:
.venv/bin/python -m migration_tools.record_battle --count 60 --duration 30 --output recordings/large

# Existing custom battle recipe or preset; both armies use existing AI:
.venv/bin/python -m migration_tools.record_battle --config battle_config.json --seed 42 --output recordings/custom
.venv/bin/python -m migration_tools.record_battle --preset 'Cavalry Assault' --output recordings/assault
```

Default snapshots are every 0.1 s. `--interval-ticks 5` samples every 0.5 s while events remain at full emission frequency; this is used by the bundled compact example. Existing directories are not overwritten: use a new path. Demos translate deployments 130 m forward to exercise battle activity; saved recipes retain their own positions unless `--advance` is supplied. A duration limit remains `limit`, never an invented winner. The original `python main.py` still opens the campaign/custom-battle menu.

The format is [documented here](../migration_tools/FORMAT.md): versioned JSON metadata plus incremental snapshot/event/index JSON Lines. One canvas unit equals one metre; +Y is down, radians clockwise from +X, formation depth is along facing and frontage perpendicular. Cannonballs show a ground shadow and an up-screen offset for height above the actual terrain surface.

## Validation and measurements

```bash
.venv/bin/pytest -q
.venv/bin/pytest -q tests/test_recording.py
godot --headless --path godot --script tests/test_playback.gd
godot --headless --editor --path godot --import --quit

.venv/bin/python -m migration_tools.benchmark_viewer --mode prepare
.venv/bin/python -m migration_tools.benchmark_viewer --mode graphics --viewer 2d --frames 600
.venv/bin/python -m migration_tools.benchmark_viewer --mode headless --viewer 2d --frames 600
```

The optional pytest bridge skips when Godot is absent. The native Godot tests validate the complete example, malformed/missing files, indexed seeking, shortest-angle interpolation, terrain maths, discrete states/endpoints, missing regiments, ball births/removals, selection, inspection and bounded caches. On restricted machines use writable `XDG_DATA_HOME`, `XDG_CONFIG_HOME`, and `XDG_CACHE_HOME`; graphical tests also require permission to connect to the desktop display.

The benchmark tool prepares 12/24/36/60-regiment Mixed Terrain recordings, measures Python ticks without recording, then runs the viewer independently. It reuses existing recording directories; choose a fresh `--output-dir` for a new baseline. Godot warms up 60 frames then reports 600 **wall-clock** frame intervals, unit draw-command CPU time, startup terrain-cache cost, decoded-frame count and cache size. GPU/X11 results and dummy/headless results must not be mixed. See [MIGRATION.md](../MIGRATION.md) for measured results and limitations.

Optional automated inspection:

```bash
godot --path godot --scene res://scenes/battlefield.tscn -- --seek=60 --paused --screenshot=/tmp/battle.png
godot --path godot --scene res://scenes/battlefield.tscn -- --benchmark-frames=600 --benchmark-output=/tmp/viewer.json
```

## Boundaries and limitations

`recording_source.gd` parses/validates files into `BattleFrame` presentation DTOs. `playback.gd` controls time and adjacent frames. `regiment_view.gd` consumes only those DTOs; `terrain_view.gd` caches analytic terrain visuals. The next C# stage should supply frames through an adapter without introducing JSON dependencies in rendering or Godot nodes in authoritative rules.

Only four decoded frames are cached; events and the byte-offset/time index remain in memory. Terrain is baked once into a bounded visual texture and retained draw commands. Its analytic shapes match Python, with display-only raster/single-precision approximation. First load takes about 0.6 s on the tested map. Large maps with many features can take longer to bake. Moving/zooming the camera does not regenerate it.

There is no live Python bridge, C# simulation, command input into recordings, full fog of war, campaign UI, animation rig or individual-soldier AI. Coarse recordings can alias short projectile flights and bounce/contact motion; use the default 10 Hz for detailed investigations. Missing middle-frame data stops playback safely when reached. Only successfully closed exports are accepted. Godot export presets are not included; when packaging an executable, include JSON/JSONL files as non-resource export files. Windows and .NET compilation remain untested.
