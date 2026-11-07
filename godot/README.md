# Quiberon 3D battlefield viewer

Godot 4.7.2 offers **Replay Mode** and **Live C# Simulation**, using the same 3D renderer, tactical camera and inspector. Live includes movement/terrain/LOS, infantry fire/melee, **morale, fleeing, rallying, cascades, cavalry charges, recoil and moving pursuit**, without Python. Milestone 4 adds physical round-shot ballistics, battery deployment, friendly fire and all six specialist archetypes. Milestone 5 adds autonomous tactical AI, named commanders, personalities and eight starting specializations. Native custom setup/deployment, infantry bayonet charges, all twelve acquired commander abilities and frozen results are also available. The six-battle Commonwealth campaign is now native C#, with persistent armies, rewards, events, objectives and between-battle saves. The complete Python/Pygame game continues working.

**Current launch:** `bash tools/godot.sh` opens the main menu. Choose **New Campaign** for the prologue, or **Custom Battle**
to edit armies/terrain, deploy both sides, choose commander abilities and start.
Completed live battles open the native results report. [Sandbox controls, recipes,
ability effects and headless commands](SANDBOX.md) describe the complete flow.
Command-line live/replay scenarios continue to bypass the menu.


## The Defence of the Commonwealth campaign

Choose **New Campaign** or **Continue Campaign** in the main menu. The persistent
starting force has two regular infantry, militia, National Cavalry and field
artillery, led by Niesiołowski under Kościuszko. Six stages include a rescue or
interception branch; Cook and Despard introduce allied forces. Use the existing
results screen’s **Continue campaign** button for rewards, events and assignments.

[Campaign rules, all encounters, upgrades, saves, headless commands, measured
results and AI limitations](../docs/COMMONWEALTH_CAMPAIGN.md).

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh
bash tools/dotnet.sh test godot/Simulation.Tests
bash tools/godot.sh --headless --script tests/test_campaign.gd
```

Native save: `user://commonwealth-campaign-v1.json`. Saves occur between battles
and at reward/event screens; completed results apply once. Custom battles and
Python recording replay retain their independent flows. CLI `--campaign-stage=3`
opens an isolated development battle and never overwrites the campaign slot.

## Rivers, crossings and weather

Live battles now support authoritative rivers, timed bridge/ford crossings,
roads/tracks, directional earthworks/barricades and fixed Clear/Rain/Fog weather.
The existing renderer also shows these features in the same battle's 2D view.
[Environment rules, JSON examples, authoring helper, tests, benchmarks and limits](ENVIRONMENT.md).

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --live --combat-scenario=environment-vistula --paused
```

Choose an `Environment A–H` laboratory in the Live scenario selector, or load the
Vistula-style laboratory preset in Custom Battle. The setup weather selector keeps
the authored terrain. Right-click the other bank for automatic crossing routing;
**Route** selects a particular bridge/ford. A pinned infantry Line must receive a
Column order before using a narrow bridge. **F8** shows banks, routes, lane owners
and waiting IDs. Infantry/cavalry/artillery retain their ordinary combat systems;
this milestone adds no crossing-assault planner or campaign missions.

## Commonwealth Stage 1 roster and historical officers

The **15 core campaign units** and **14 recommended historical commanders** are
available for ordinary live/custom battles. This is content preparation, not the
six-mission campaign. [Roster, exact signatures, laboratories and measured results](../docs/COMMONWEALTH_STAGE1.md).

In Custom Battle, use **+ Add units…** and combine faction/category filters to
build coalition armies. Load a `Commonwealth lab …` preset for a ready deployment.
Before starting, select any regiment and open **AI** to assign a compatible unique
historical officer or reroll a generic commander. Army commanders have separate
Blue/Red selectors. Historical signatures are fixed; acquired abilities remain the
existing optional sandbox setup. Saves retain both types of assignment.

```bash
bash tools/godot.sh -- --live --combat-scenario=commonwealth-battle-coalition
bash tools/dotnet.sh test godot/Simulation.Tests
bash tools/godot.sh --headless --script tests/test_commonwealth.gd
.venv/bin/python -m migration_tools.evaluate_commonwealth --suite battles --seeds 17 31 73 --swap
.venv/bin/python -m migration_tools.benchmark_ai --commonwealth --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --commonwealth --frames 600
```

The existing camera, facing ghosts, nominal range rings, pause/speed controls,
same-battle 2D/3D view switch and Python Replay Mode are shared with this content.

## Build and launch live mode

Use **Godot 4.7.2 .NET** and a **.NET 10 SDK**. Tested locally: SDK 10.0.403, runtime 10.0.14 and the official Linux x86_64 Godot .NET build. The ordinary installed `godot` remains usable for replay, but cannot run C#.

From the repository root:

```bash
# First-time Linux x86_64 setup, if needed; installs only into ignored .tools/:
bash tools/bootstrap_dotnet.sh
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh                 # Main menu: Custom Battle, Live scenarios or Replay
bash tools/godot.sh -- --live        # Or enter live mode directly
bash tools/godot.sh --editor        # Open the matching .NET editor
```

The toolchain is already installed and the project built in this workspace. The wrappers set `DOTNET_ROOT`, SDK lookup and local caches. If using an existing installation, set `GODOT_DOTNET` to the .NET Godot executable and use a system .NET 10 SDK. On other platforms, use `dotnet build godot/Quiberon.csproj`, then the matching .NET editor/executable with `--path godot`. The SDK's global configuration accepts .NET 10 feature-band updates. [Official Godot downloads](https://godotengine.org/download/), [Microsoft SDK installation](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-install-script).

The top-left selector returns to **Replay Mode**, reopening the last selected recording. The bundled completed battle is the initial replay. A standard Godot launch still works independently:

```bash
godot --path godot
# Preserved original viewer:
godot --path godot --scene res://scenes/battlefield.tscn
```

Replay needs no .NET SDK or additional assets. **Open recording** selects another `metadata.json`; existing version-1 recordings are supported without conversion. The **2D view** button displays the current live battle or replay without restarting it; **3D view** returns to the same battle. Both views share the clock, selection, orders and controls. [Legacy standalone 2D instructions](README_2D.md) remain available. The mode selector reports a clear requirement message when C# is unavailable.

## Live controls

Live defaults to **Player versus AI** (`ai-player`), opening paused when selected through the mode selector. Use **AI** to configure Blue/Red strategies and the selected commander before Play. `ai-combined` runs both armies autonomously. The top-row selector reads the native scenario registry: eleven AI/commander demonstrations, thirteen artillery/specialist demonstrations, nine morale/cavalry demonstrations, six infantry combat scenarios, and preserved **Movement Sandbox** / **Terrain March**. Only Blue is controllable. AI scenarios use the four native army doctrines and autonomous commanders; older fixtures retain their explicit historical rules.

| Input | Live action |
|---|---|
| Left click | Select friendly formation/flag |
| Right click terrain | Move; hold and drag to set arrival facing before release |
| Right click enemy | Attack that regiment; approach, turn and fire when a lane is available |
| L / J / K | Line / column / loose skirmish; also available as buttons |
| H / V | Hold and fire / advance and engage; also available as buttons |
| B / U | Charge / pursue current enemy (cavalry only; pursuit needs a routing target) |
| X / G | Disengage / reform by holding for ordinary recovery |
| Space | Pause/resume |
| 1 / 2 / 3 / 4 | 1× / 2× / 4× / 10× |
| . | Advance one tick while paused |
| R | Reset the live scenario with fresh state |

C remains camera-follow, so **J** replaces the Python column shortcut. Formation controls respect archetype compatibility and the seven-second transition. Queued orders take effect on the next tick. Strength, morale, cohesion, fatigue, reload and visibility are authoritative. Flags show morale/cohesion/strength plus state warnings; the inspector includes charge state, actual speed, momentum, cooldown, pursuit target, rally progress and recent reasons. **Routing/rallying units reject ordinary orders until they return to duty.** Reform is a hold/recovery command, not instant rallying or a charge reset. Hold can still fight enemies already in contact; Disengage turns and moves away normally.

Infantry Attack seeks a firefight; Cavalry Attack approaches and charges when eligible, then may pursue a broken target. Hold does not initiate a distant pursuit. Explicit Pursue ends when its assigned target dies, escapes or recovers. Battles finish when an army remains below **18% effective starting strength for 12 seconds**; routed survivors are not counted as casualties. Reset restores fresh state. Live has no timeline seeking. All camera controls remain independent and work while paused.

Launch any new demonstration directly:

```bash
bash tools/godot.sh -- --combat-scenario=prepared-charge
# Other IDs: infantry-under-fire, cascading-rout, flank-charge, wavering-charge,
# routing-pursuit, shared-pursuit, safe-rally, difficult-charge
bash tools/godot.sh -- --combat-scenario=routing-pursuit --live-seed=31
```

The six previous IDs (`infantry-duel`, `ridge-defence`, `forest-engagement`, `flank-attack`, `friendly-obstruction`, `combined`) also run with morale/cavalry in normal Live mode. `--combat-scenario=benchmark-dynamics-60` loads an active stress fixture; `--live-warmup-ticks=140 --live-speed=4` pre-rolls exactly 14 simulated seconds before viewing at 4×. Developer pre-roll executes real ticks, not replay seeking. `--legacy-combat` preserves the frozen M2 rules for regression/benchmark comparisons only. Old headless fixture JSON retains its explicit dynamics flags.

Movement developer flags are preserved: `--live-terrain`, or `--live --live-count=60 --march`. All six specialists are functional in normal live combat, including woodland fire/melee, Prussian drill, Grenadier support, Uhlan exploitation, rifle aiming and horse-battery mobility. Batteries fire physical projectiles and remain weak in crew melee. All surviving effective regiment strength counts toward morale victory, as in Python. [MORALE_CAVALRY.md](MORALE_CAVALRY.md) documents current dynamics; [COMBAT.md](COMBAT.md) retains the musket/melee foundation and [LIVE_SIMULATION.md](LIVE_SIMULATION.md) the movement architecture.

## Controls

| Input | Action |
|---|---|
| WASD / arrows | Pan relative to camera heading |
| Q / E | Orbit left/right around the ground focus |
| Shift | Faster pan |
| Middle drag | Grab and drag terrain |
| Alt + middle drag | Orbit and tilt, from 0° (level) to 88° |
| Wheel | Physically move closer to / farther from terrain under the cursor |
| Home | Smooth overview of the whole battlefield |
| F | Focus selected regiment, preserving angle/zoom |
| C | Follow selected regiment; manual pan/orbit cancels |
| T | Toggle near-vertical orthographic tactical view; restore previous view |
| P | Switch orthographic/perspective, preserving focal-plane scale |
| Left click | Select a formation or its flag |
| Escape | Deselect / end following |
| Space / R | Pause or restart replay |
| 1 / 2 / 4 | Replay speed |

The timeline seeks both directions. Replay rate/pause never changes camera speed. UI panels consume selection/scroll; camera shortcuts are disabled during text entry and modal dialogs. The right information panel scrolls on small windows.

The default camera is **perspective**. Wheel input dollies the camera through the scene with a fixed field of view, so approaching formations also brings the camera lower and closer to them. Scrolling from an orthographic/overhead view switches to perspective for this same physical movement. `--perspective` and `--orthographic` explicitly select the initial projection.

**Camera settings** exposes live sensitivities and responsiveness. Defaults and all other limits are exported in [tactical_camera.tres](resources/tactical_camera.tres), implemented by [camera_settings.gd](scripts/three_d/camera_settings.gd). Remap `camera_*` actions in **Project Settings → Input Map**. See [CAMERA.md](CAMERA.md) for detailed behaviour and tuning. Live settings last for the session; edit the resource for persistent defaults.

## World and visuals

One Godot unit is one metre: Python `(x,y)` maps to Godot `(x,elevation,z=y)`. Models face local +X and rotate about Y by **negative** recorded facing. Cannonball height is already absolute elevation and is not added to the terrain again.

Terrain is an indexed, shaded heightfield mesh generated once from the recording's analytic Gaussian/compact hills. The default spacing is 5 m, with a 200,000-vertex target that adapts on large maps. Mesh grounding and mouse rays use identical triangular interpolation, avoiding a separate flat picking plane. Finite-feature supports and static forest candidate cells avoid all-feature scans during map construction. Forests use deterministic, ground-aligned tree batches grouped into 160 m cells. Nearby selected foliage fades; distant foliage is lighter. Flags remain visible above/through trees.

Regiments use MultiMesh batches of low-poly bodies, heads, legs, headwear and muskets; cavalry adds horses/riders and Uhlan lances; artillery has cannons, wheels, crew and horse-battery teams. Default infantry/cavalry visual capacity is **32 figures**, scaled down with actual surviving strength; artillery uses recorded gun count. Stable centre-out slots avoid repacking all survivors after casualties. Line, column and loose footprints come from snapshots; cohesion/routing add bounded visual disorder only.

[unit_visuals.json](resources/unit_visuals.json) maps stable archetype IDs to placeholder uniform/model profiles. Allegiance remains visible in flags/borders so mixed-faction sandbox armies work. Woodland infantry uses a neutral, unexaggerated design. These are stylized placeholders, not detailed historical uniform reconstructions.

[presentation_3d.tres](resources/presentation_3d.tres) controls figure count, terrain resolution/budget, forest density/chunks, foliage fading, distant figure cutoff and shadows. Above the distant cutoff, tactical footprints/flags remain while figures are omitted; selection keeps its figures visible. Meshes/materials are shared, static terrain is cached, and unchanged paused regiment transforms are reused. No decorative figure has a Node, collider, pathfinding, AI, health or morale of its own.

## Structure

- `scenes/battlefield_3d.tscn`: default presentation controller and UI.
- `scripts/three_d/viewer_3d.gd`: recording/playback orchestration; a dedicated 3D SubViewport keeps camera rays separate from HUD coordinates.
- `tactical_camera.gd` / `camera_settings.gd` / `camera_bindings.gd`: reusable camera, resource tuning and InputMap defaults.
- `world_3d.gd` / `terrain_surface.gd` / `terrain_mesh.gd`: coordinate contract and shared surface/mesh.
- `mesh_kit.gd` / `regiment_view_3d.gd` / `forest_view.gd`: procedural assets and batches.
- `effects_3d.gd` / `unit_markers.gd`: recorded shots/smoke/impacts/rout/rally effects and readable tactical markers.
- `replay_hud.gd`: replay controls and the existing inspection pattern adapted to 3D.
- Existing `recording_source.gd`, `battle_frame.gd`, `playback.gd`: reused file adapter, presentation DTOs and replay clock. `battlefield_2d.gd` reuses the 2D terrain/unit renderers inside the current viewport, sharing live/replay frames and controls. The original standalone replay scene remains runnable.
- `Simulation/`: standalone double-precision .NET library, independent of Godot.
- `Simulation.Tests/`, `Simulation.Runner/`: xUnit tests and headless executable, hidden from Godot asset import with `.gdignore`.
- `scripts/simulation_adapter/`: C# bridge and live source supplying the same `BattleFrame` pairs without JSON.
- `Quiberon.csproj` / `Quiberon.sln`: small Godot adapter project and solution; ordinary headless projects remain separately buildable.

## C# tests, fixtures and headless execution

```bash
bash tools/dotnet.sh test godot/Simulation.Tests/Simulation.Tests.csproj -c Release
bash tools/dotnet.sh build godot/Simulation.Runner/Simulation.Runner.csproj -c Release
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --scenario straight --seed 17 --output benchmark-results/straight-csharp.json
.venv/bin/python -m migration_tools.movement_reference --compare benchmark-results/straight-csharp.json
bash tools/godot.sh --headless --script tests/test_live.gd
bash tools/godot.sh --headless --script tests/test_combat.gd
bash tools/godot.sh --headless --script tests/test_dynamics.gd
.venv/bin/pytest -q

# Regenerate Python movement fixtures, only when intentionally updating the oracle:
.venv/bin/python -m migration_tools.movement_reference --generate
# Equivalent movement-only workloads, three sequential repeats:
.venv/bin/python -m migration_tools.benchmark_movement --repeats 3
# All four live GPU counts, run sequentially:
.venv/bin/python -m migration_tools.benchmark_live --frames 600
# Equivalent M2 ordinary-infantry phases; three sequential repeats, JSON + CSV:
.venv/bin/python -m migration_tools.benchmark_combat --repeats 3
# Matched M3 morale/routing/charge/pursuit workloads:
.venv/bin/python -m migration_tools.benchmark_dynamics --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --dynamics --frames 600
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --combat-scenario routing-pursuit --duration 60 --output benchmark-results/pursuit.json
# Separate allocation diagnostic pass; do not use its timings as benchmark data:
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --combat-scenario benchmark-dynamics-60 --benchmark --allocation-profile --output benchmark-results/dynamics-allocations.json
# GPU live combat timing (independent of the console benchmark):
.venv/bin/python -m migration_tools.benchmark_live --combat --frames 600
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --combat-scenario infantry-duel --duration 1200 --output benchmark-results/duel.json
# Regenerate the isolated Python combat oracle only when intentionally updating it:
.venv/bin/python -m migration_tools.combat_reference --generate
.venv/bin/python -m migration_tools.dynamics_reference --generate
# Live GPU timing, independent of the headless movement benchmark:
bash tools/godot.sh -- --live --live-count=60 --march --camera-span=800 --benchmark-frames=600 --benchmark-output="$PWD/benchmark-results/live-60.json"
```

The runner accepts fixture paths or names, `--duration SECONDS`, `--seed N`, `--benchmark` and `--warmup`. Keep the fixture's default duration when comparing every reference sample. It exports JSON only for offline inspection, never as a per-frame live bridge. [Fixture format](../migration_tools/movement_fixtures/README.md) and [measured results/migration status](../MIGRATION.md) explain scope and numerical tolerances. The standard .NET test runner uses local loopback sockets; restricted sandboxes must permit them. A full solution build can use `bash tools/dotnet.sh build godot/Quiberon.sln -m:1`.

## Recording, tests and benchmarks

```bash
.venv/bin/python -m migration_tools.record_battle --seed 7 --duration 650 --output recordings/new-battle
godot --path godot -- --recording="$PWD/recordings/new-battle/metadata.json"
.venv/bin/pytest -q
godot --headless --path godot --script tests/test_camera_3d.gd
godot --headless --path godot --script tests/test_viewer_3d.gd
godot --headless --path godot --script tests/test_playback.gd

.venv/bin/python -m migration_tools.benchmark_viewer --mode prepare
.venv/bin/python -m migration_tools.benchmark_viewer --mode graphics --viewer 3d --frames 600
.venv/bin/python -m migration_tools.benchmark_viewer --mode graphics --viewer 2d --frames 600
```

The tool reuses prepared recordings; choose a fresh `--output-dir` for new inputs. Reports distinguish GPU rendering from headless validation and Python simulation. See [VIEWER_3D.md](VIEWER_3D.md) for measured results, validation and limitations. Native tests skip through pytest if Godot is absent.

Repeatable visual inspection:

```bash
godot --path godot -- --paused --seek=60 --focus-id=4 --camera-span=32 --camera-pitch=35 --screenshot=/tmp/cavalry.png
godot --path godot -- --perspective --benchmark-frames=600 --benchmark-output=/tmp/3d.json
```

A sample interval of 0.5 s keeps the bundled replay compact; use the exporter's default 0.1 s interval when examining short projectile flights/bounces. Effects are rebuilt from the current event window on every seek/reset. Campaign remains in Python; acquired abilities can now be selected and saved in native sandbox recipes. Windows and packaged executable exports remain untested. Include JSON/JSONL/profile files as non-resource files when packaging. Shader warm-up and large map construction can pause the viewer briefly at load.


## Milestone 4 combined arms

The developer selector includes `open-shot`, `ricochet`, `artillery-hills`,
`enfilade`, `friendly-fire`, `battery-under-attack`, `prussian-drill`,
`woodland-specialists`, `grenadier-support`, `uhlan-charge`, `rifle-engagement`,
`horse-redeployment` and `combined-arms`. All use fixed seeds. Normal live combat
also enables new mechanics in earlier templates; old headless reference fixtures
preserve their original explicit feature flags.

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --combat-scenario=combined-arms --live-seed=17
bash tools/godot.sh -- --combat-scenario=friendly-fire
bash tools/godot.sh --headless --script res://tests/test_artillery.gd
.venv/bin/python -m migration_tools.artillery_reference
.venv/bin/python -m migration_tools.benchmark_artillery --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --artillery --output-dir benchmark-results/m4-gpu
```

**Y / I** hold/resume fire without forgetting the target; **O** selects manual
skirmish stance/loose formation; **X** disengages. Right-click enemy orders Attack,
including automatic battery reload/fire and cavalry charge/pursuit. Ground moves
limber artillery and require setup on arrival. **F8** toggles shot tangents,
range/arcs/targets/aura rings and projectile energy/bounce text. Camera bindings
are unchanged. Skirmish stance does not run the deferred autonomous standoff AI.

The battery inspector exposes crew-supported operational guns, limber/setup/reload
and hold-fire state. Rifle aimed bonus and Prussian drill are situational factors;
trait descriptions are in the same panel. All nine archetypes reuse existing
faction visual definitions and instancing; replay remains unchanged.
See [full artillery/specialist rules and limitations](ARTILLERY_SPECIALISTS.md),
[MIGRATION.md](../MIGRATION.md) and [performance measurements](../PERFORMANCE.md).


## Milestone 5 autonomous battles and officers

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --combat-scenario=ai-player --paused
bash tools/godot.sh -- --combat-scenario=ai-combined --live-speed=4
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release -- --combat-scenario ai-combined --duration 1200 --output benchmark-results/ai-battle.json
bash tools/godot.sh --headless --script res://tests/test_ai.gd
.venv/bin/python -m migration_tools.ai_reference
.venv/bin/python -m migration_tools.evaluate_ai --seeds 17 31 73 --swap
.venv/bin/python -m migration_tools.benchmark_ai --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --ai --output-dir benchmark-results/m5-gpu
```

The **AI** dialog selects manual/balanced/all_out_attack/hold_the_line/skirmish
for each army; defensive anchors are original deployment positions. Before the
first tick, select a regiment and reroll its officer or choose compatible traits.
After starting, those edits lock. Army objectives and selected-Blue autonomy remain
adjustable. Explicit unit Hold/Move/Attack/Disengage and manual formation choices
stay pinned; release **Autonomous** to resume planning. Hold-fire control remains
independent. Mandatory routing/rallying overrides ordinary orders. Reset preserves
commander and army setup. Commanders use a separate seed, so changing combat seed
does not silently reroll them. Enemy regiments are inspectable in AI scenarios;
manual battlefield orders still control Blue only.

The selected-unit inspector shows actual decisions/reasons, order owner, next
scheduled decision, threat/target assessment and conditional trait effects.
Current targets/destinations and F8 debug remain available; camera controls are
unchanged. All camera motion works while paused and at every simulation speed.

Additional scenario IDs: `ai-infantry`, `ai-cavalry-reserve`, `ai-exposed-flank`,
`ai-forest`, `ai-rifles`, `ai-artillery`, `ai-horse-artillery`, `ai-personalities`,
`ai-specializations`. [AI_COMMANDERS.md](AI_COMMANDERS.md) documents actual policies,
modifier caps, generation, source differences and limitations; [MIGRATION.md](../MIGRATION.md)
and [PERFORMANCE.md](../PERFORMANCE.md) contain measured results. JSON scenarios
can set `aiEnabled`, `commandersEnabled`, `commanderSeed`, `aiDecisionTicks`,
`aiArmies`, `aiStrategies`, and per-unit `commander`/`autonomy`. The runner reports
`timedOut` separately from victory and includes participation telemetry.
