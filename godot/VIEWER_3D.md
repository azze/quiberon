# 3D viewer validation and performance

This report describes the recording-driven 3D presentation milestone. The newer native C# movement sandbox, reference comparisons and live GPU timings are documented in [LIVE_SIMULATION.md](LIVE_SIMULATION.md) and [MIGRATION.md](../MIGRATION.md). Replay and live mode now share this renderer.

The default scene is `scenes/battlefield_3d.tscn`. Launch with `godot --path godot`; the original 2D scene remains `scenes/battlefield.tscn`. See [README.md](README.md) for scene/script structure and recording commands, and [CAMERA.md](CAMERA.md) for controls and resource tuning. Python remains authoritative; no battle rules, RNG calls, balance or fixed simulation ticks changed in this stage.

## Tested environment and method

2026-11-04: Linux, AMD Ryzen 5 7600X3D, NVIDIA GTX 1080 / driver 580.196.07, Godot 4.7.2 standard, OpenGL Compatibility/X11. No .NET SDK is installed or required by this GDScript viewer. The editor imports/compiles the project and actual desktop GPU playback was exercised. Screenshots were inspected at 1280×800 and 800×600, including close infantry/cavalry, forests and oblique hills. Native input-event tests supplement these visual checks; this is not a long human camera playtest or a Windows/package-export validation.

Each performance sample is a **separate actual GPU run**, 1280×800 window, 962×578 battlefield SubViewport, 2× MSAA, directional shadows enabled, default 32 visual infantry/cavalry capacity, orthographic overview. Prepared recordings use seed 17, Mixed Terrain, 1,000×600 m, 10 Hz snapshots, active combined arms, and playback starts at 15 simulated seconds at 1×. Vsync is disabled, 60 frames warm up, then 600 wall-clock frame intervals are measured. No competing simulations/tests ran during measurement. This is one sample per size, not a cross-hardware FPS guarantee or a worst-case forest close-up.

Camera follow-up: the normal launch now defaults to **perspective with physical wheel dollying**, rather than orthographic scaling. The historical measurements below remain orthographic samples; use `--orthographic` when launching a matching scene directly. New default-perspective runs are a different camera workload. Scrolling from an orthographic view switches to perspective without changing the lens field of view.

## Results

| Regiments | Mean / median / p95 frame (ms) | Presentation CPU mean (ms) | Load (ms) | Visible figure proxies at end |
|---:|---:|---:|---:|---:|
| 12 | 2.37 / 2.32 / 2.92 | 1.55 | 137 | 313 |
| 24 | 4.10 / 4.02 / 4.85 | 3.03 | 145 | 572 |
| 36 | 5.36 / 5.24 / 6.26 | 4.11 | 143 | 901 |
| 60 | 9.30 / 9.00 / 11.59 | 7.53 | 151 | 1,500 |

Each map builds **24,321 terrain vertices and 385 trees once**, with a 104–107 ms terrain mesh build. At most four decoded snapshots were cached. Figure counts reflect current strength; artillery counts gun proxies, each of which includes decorative crew. Figures/materials are shared MultiMeshes, not independent soldier nodes. Tree batches are spatially grouped. Native renderer frustum culling and a simple distant figure cutoff are used; this is not a full LOD system.

These recordings play comfortably at 60 Hz on this host, including 60 regiments. Most measured scaling is presentation CPU work updating figure transforms and tactical markers. Playback does **not** include authoritative battle computation: previously measured Python 60-regiment ticks averaged about 59 ms in this workload, documented separately in [MIGRATION.md](../MIGRATION.md). A live C# integration still needs a simulation/frame budget. Higher resolution, dense selected forests, more proxies and other GPUs can cost more.

A separate **headless load test**, 4,800×3,000 m Mixed Terrain with 125 hills, 100 forests and 12 regiments, exposed repeated all-feature scans. Restricting compact hills to exact finite supports and indexing forest candidates reduced loading from **11,125 to 1,068 ms**, retaining **199,092 vertices and 9,518 trees**. Static mesh work fell from 5,016 to 807 ms. This comparison measures initialization with the same map, not GPU FPS; the dummy renderer's frame rate is not a graphics benchmark. Legacy infinite-support Gaussian hills still evaluate across the grid. Very large maps can still pause briefly at load, and the vertex budget coarsens terrain spacing.

Raw current results: `benchmark-results/godot/{12,24,36,60}-units/graphics-3d.json`. The large-map load comparison is under `benchmark-results/godot/large-3d/`. Generated results/recordings stay outside source files. Reproduce:

```bash
.venv/bin/python -m migration_tools.benchmark_viewer --mode prepare
.venv/bin/python -m migration_tools.benchmark_viewer --mode graphics --viewer 3d --frames 600
.venv/bin/python -m migration_tools.benchmark_viewer --mode graphics --viewer 2d --frames 600
```

Prepared recordings are reused; choose a fresh `--output-dir` to generate new inputs. `--mode headless` validates parsing/update work but cannot measure GPU rendering. Native reports label frame intervals and presentation CPU separately from startup and Python simulation time.

## Regression and camera checks

The initial 3D full suite passed **568 pytest tests** (61.40 s). After the physical-dolly camera follow-up, the targeted pytest bridges and exporter tests pass; native checks now cover **58 camera** and **74 3D viewer** assertions, including physical approach/retreat, smooth motion, fixed FOV and dollying from overhead. The initial **60 preserved playback/2D** checks also passed. The two new pytest bridges invoke the installed Godot, fail on script errors as well as exit status, and skip if Godot is absent. Existing exporter tests retain deterministic recording/RNG/outcome comparisons.

Coverage includes coordinate/yaw/absolute-projectile-height conversion, shortest-angle interpolation, terrain/forest agreement with the analytic DTO, clockwise terrain triangle winding, grounding, all visual unit categories, casualty slots, formations, dead/disappearing units, projectile transitions, selection via actual viewport input, inspection, seeking/effect resets, invalid files and cache limits. Camera tests cover heading-relative pan, terrain grab at multiple sensitivities, orbit around focus, ray/zoom anchoring across 30°/55°/87° and both projections, hills/field edges/sky fallback, perspective fit/scale, bounds, pitch, overhead restoration, focus/follow/manual cancellation, zoom during follow, resize, UI blocking, and consistency at 20/144 FPS. Native viewer checks exercise paused navigation and 1×/2×/4× replay.

```bash
.venv/bin/pytest -q
godot --headless --path godot --script tests/test_camera_3d.gd
godot --headless --path godot --script tests/test_viewer_3d.gd
godot --headless --path godot --script tests/test_playback.gd
godot --headless --editor --path godot --import --quit
```

## Simplifications and next steps

- Models are rigid low-poly placeholders. No walking, recoil or individual-soldier simulation; gun/horse crews are decorative. Archetype colours are readable profiles, not historical uniform research.
- A sampled mesh approximates analytic elevation. Mesh, tree/regiment grounding and picking agree with each other, but very narrow terrain can require a finer configured spacing. Projectile positions remain recorded absolute elevations, so sampling error can cause slight visual ground penetration.
- The bundled completed example uses 0.5 s snapshots. Short flights/bounces can alias; export at the default 0.1 s interval for inspection. No interpolation can recover unrecorded physics substeps.
- Foliage fade is a bounded local/zoom approximation, with normal transparent sorting limitations. Flags provide visibility through trees. There is no full occlusion or fog-of-war system.
- Live camera settings last for the session; edit the resource to persist defaults. Extreme manual resource tuning should be validated. At outer camera bounds, cursor anchoring may relax. Projection switching preserves scale at the focus plane, not every depth simultaneously.
- Startup geometry/shader work is synchronous. Dynamic figure transforms and UI marker projection remain the main scaling costs. Profile before adding more complex LOD or multithreaded loading.
- The next presentation step is a human camera playtest, followed by replacement mesh assets/simple animation and targeted profiling of dense forest views. The C# geometry/state/movement library and adapter proposed in this report are now implemented. LOS and basic infantry fire, with portable RNG/event-order rules and Python references, are the next simulation candidates; combat remains unported.
