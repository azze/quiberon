# Battlefield environment

Environmental terrain is implemented in the standalone C# simulation and the
existing Godot live renderer. These are development battlefields, not campaign
missions. Python combat/replay files and legacy Clear scenarios remain supported.
No crossing-operation AI, construction/destruction, objectives, campaign state or
changing weather has been added.

## Try it

From the repository root (Godot **4.7.2 .NET**, **.NET SDK 10**):

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --live --combat-scenario=environment-vistula --paused
```

The existing Live scenario selector includes eight laboratories:

| ID suffix (prefix `environment-`) | Demonstration |
| --- | --- |
| `river` | Deep water, no crossing |
| `bridge` | Single narrow bridge, mixed categories |
| `ford` | Bridge plus an infantry/cavalry ford |
| `roads` | Line/column/cavalry/artillery road march |
| `defences` | Earthwork and barricade firing positions |
| `rain` | Road march in rain |
| `fog` | Restricted spotting with woodland |
| `vistula` | Broad river, bridge, ford, roads, works and combined arms |

In **Custom Battle**, load **Environment H — Vistula-style crossing laboratory**
from the preset list, edit the armies, choose Clear/Rain/Fog, then deploy normally.
Existing file load/save retains the environmental geometry. Changing the terrain
preset intentionally generates a new battlefield; simply changing weather retains
its features. Custom configurations use the existing version-1 wrapper.

Right-click dry ground on the other bank to route through a suitable crossing.
**Route: Auto / crossing ID** in the top toolbar pins a specific crossing for the
next movement order, including right-drag arrival facing. Select Auto to release
the preference. Infantry explicitly pinned to a wide line waits: issue **Column**
to permit a narrow crossing. Pause, speeds, stepping, range rings, focus/follow,
WASD, panning, rotation, zoom and same-battle **2D / 3D** switching are unchanged.

**F8** extends the existing combat debug display: banks, crossing limits and
entry/exit, active route segments, lane owner and waiting IDs. The selected-unit
inspector shows crossing/formation/waiting/blocked-route status and road surface.
Static meshes are retained; debug route geometry is updated only while enabled.

## Authoring and format

Coordinates are simulation metres. A position is `{ "x": 600, "y": 400 }`;
facing is radians, zero towards +X, positive towards +Y. Formation width is
perpendicular to facing; depth and crossing length follow facing.

Use the small Python **authoring helper** (it does not run Python combat):

```bash
# Native headless scenario, ready to edit/run.
.venv/bin/python -m migration_tools.environment_maps --map vistula --weather rain --output /tmp/river-battle.json
bash tools/dotnet.sh run --project godot/Simulation.Runner -- --scenario /tmp/river-battle.json --duration 120 --output /tmp/river-states.json

# Existing custom-battle recipe, load with Custom Battle > Load.
.venv/bin/python -m migration_tools.environment_maps --map ford --custom --output /tmp/crossing-custom.json
bash tools/dotnet.sh run --project godot/Simulation.Runner -- --battle-config /tmp/crossing-custom.json --duration 60
```

`migration_tools/environment_maps.py` exposes `river`, `crossing`, `road`,
`defence`, `unit` and `environment` helpers. Change a few endpoints and parameters,
then regenerate a file; no terrain-editor scene or hundreds of points are needed.
`--write-bundled` intentionally regenerates the eight scenarios, twenty benchmark
workloads and custom Vistula preset. To add a permanent Godot laboratory, save a
native scenario in `simulation_data/combat_scenarios/` and rebuild. These JSON files
are embedded by the existing standalone project. Files prefixed `benchmark-` are
excluded from the normal scenario selector.

Both formats accept optional **`terrain.environment`**, with its own `version: 1`.
Native `terrain.hills` / `terrain.forests` keep their old camelCase definitions;
the custom wrapper keeps its existing snake_case hill/forest fields. Environment
keys are camelCase in both. Omitted lists mean empty; omitted weather means Clear.

Example environmental definition (merge under `terrain.environment`):

```json
{
  "version": 1,
  "rivers": [{
    "id": "river", "name": "Test river",
    "points": [{"x": 600, "y": -100}, {"x": 600, "y": 1100}],
    "width": 90, "waterHeight": -0.4, "depth": 2
  }],
  "crossings": [
    {"id": "bridge", "riverId": "river", "position": {"x": 600, "y": 400},
     "facing": 0, "length": 140, "width": 26, "kind": "bridge"},
    {"id": "ford", "riverId": "river", "position": {"x": 600, "y": 650},
     "facing": 0, "length": 140, "width": 42, "kind": "ford",
     "fordDepth": "moderate", "speed": 0.45, "cohesionPerMetre": 0.10}
  ],
  "roads": [{
    "id": "main", "name": "Bridge road", "width": 10, "surface": "mainRoad",
    "points": [{"x": 100, "y": 400}, {"x": 600, "y": 400}, {"x": 1100, "y": 400}]
  }],
  "defences": [{
    "id": "work", "position": {"x": 850, "y": 400}, "facing": 3.141592653589793,
    "width": 90, "depth": 3, "kind": "earthwork", "protectionDepth": 36,
    "musketExposure": 0.70, "chargeResistance": 0.65
  }],
  "weather": {"type": "clear", "visibilityLimit": 180}
}
```

IDs must be globally unique within the environmental definition. Crossings must
reference a river, have their centre in it, and both endpoints on dry banks.
`permitted: ["infantry", "cavalry", "artillery"]` overrides category defaults.
A native move order may include `viaCrossing: "ford"`; the custom placement-order
wrapper uses `via_crossing`. Unknown crossing IDs are rejected.

## Rivers, footprints and navigation

A river is a constant-width polyline. Each segment is a cached **convex capsule
polygon**, with eight edges per semicircular end. The exact same polygons are
exported for water rendering (clipped only to battlefield bounds). A static 100 m
spatial index filters overlap tests. Geometry and collection sizes are validated
and bounded; split very long diagonal polylines to avoid large AABB grid budgets.
There is no hydrology, swimming or independent Godot navigation/physics layer.

The whole **oriented formation footprint**, with 0.1 m clearance, must remain dry
or have all water-overlap geometry inside a permitted crossing rectangle. Swept
translation and bounded angular subdivisions check the area traversed, including
turns; movement cannot tunnel over narrow water. Separation and formation changes
are guarded as well. Invalid steps restore the previous safe pose and cancel
stored charge momentum. A bounded, swept clearance step can back a formation away
from a bank to make turning possible. Invalid initial/deployment footprints are
rejected, not teleported onto the far bank.

Crossings expose entry/exit points and a distance-only visibility graph. Dry links
are joined to compatible crossing edges using deterministic Dijkstra selection;
fords have twice the route cost per metre. Graph links are cached. A 46 m dry
approach extension provides turning/formation clearance; static links conservatively
check a 90 m footprint. A preferred crossing constrains its river, without
preventing use of crossings on other rivers. Unreachable routes wait with a useful
status and retry at most every three simulated seconds for unchanged goals.
Routing units use reachable, bounded movement along a bank when no crossing route
exists. Normal threat-based fleeing and escape rules remain in use.

This is **local mechanical navigation**, not a bridge assault planner. It does
not choose a strategically safe crossing, coordinate armies, or solve intricate
concave-bank mazes. Author broad, clear approaches and keep the approach nodes
inside the map. Infantry without an allowed Column cannot use a narrow crossing.
The player can deliberately approach another crossing or pin it in the toolbar.

### Bridges and traffic

A bridge is a traversable oriented rectangle, with surface height defaulting to
water + **0.55 m** (override `surfaceHeight`). Visible deck/rails match its width
and length. Bridge movement factor defaults to **0.85**. All three categories are
permitted by default.

Infantry uses its existing **timed Column** change (base seven seconds, existing
traits apply), never an instantaneous width reduction. A 26 m bridge accommodates
the 22 m infantry column plus clearance. Pinned lines wait for a player formation
order. Cavalry and artillery need **four simulated seconds** to enter compact
travel footprints, **12 × 60 m** and **12 × 42 m** respectively, when their ordinary
width does not fit. They take four seconds to reform once safely clear. Artillery
retains limber/setup/reload state and cannot fire in compact transit.

A FIFO queue, ordered by arrival tick then stable regiment ID, grants one friendly
formation passage at a time. A formation already traversing continues its route to
clear the exit before an ordinary stop; obsolete/dead queue entries are removed.
Opposite friendly traffic is tested. Enemy presence remains an ordinary collision
and melee obstacle, not a friendly pass-through exception. Deliberately holding a
formation on a crossing or fighting over its exit may of course prevent passage.
There is no bridge destruction or construction.

### Fords

Fords use the same actual crossing rectangle. Default **moderate** depth permits
infantry and cavalry; **shallow** additionally permits artillery. Permissions are
configurable. Default speed is **0.45**, with **0.10 cohesion loss per metre** of
movement added while the footprint overlaps water. Stationary units do not receive
movement disorder. Full-footprint width requirements still apply.

While fording, charge distance resets to zero and momentum is capped at **0.15**;
crossing navigation cancels charge/pursuit acceleration in favour of marching.
Cavalry must clear the crossing and prepare a genuine subsequent charge. Fords do
not give musket cover or arbitrary damage immunity.

## Terrain elevation and presentation

The river bed is water height minus depth; ford ground is water height minus
0.15 m by default. Bridge deck elevations override the bed. Native terrain and
ballistics query these same definitions; bank gradients use central 1 m sampling.
The Godot river terrain is sampled from C# at **5 m** spacing, increased only for
the approximately 196k-vertex budget, with the existing triangular interpolation.
Soldier placement and picking override bridge deck height exactly. Bank edges are
therefore visually smoothed at grid resolution; narrow/strongly angled features
can have small visual edge differences. The authoritative polygon always governs
passability. Hills/forests retain their existing formulas and data.

Round shot can fly over water. A low shot striking water loses its remaining
energy and emits `projectile_water`; it does not ricochet off deep water. Gravity,
flight, formation collisions and friendly fire otherwise use the existing system.
Bridges have a ground/deck collision surface. Trees are not placed in river water.

## Roads and tracks

A road is a polyline strip. Benefits use distance to its centreline and alignment
with the segment (absolute heading dot product **> 0.85**). Marching along it:

| Category / formation | Main road | Track |
| --- | --- | --- |
| Infantry Column | ×1.08 | ×1.036 |
| Infantry Line / Skirmish | ×1.00 | ×1.00 |
| Cavalry marching | ×1.05 | ×1.0225 |
| Artillery | ×1.20 | ×1.09 |

Optional `multiplier` is bounded 0.8–1.15; total road benefit is capped at ×1.25,
and total terrain speed at ×1.30. Slope, forest, formation and congestion still
apply. Charging receives no marching road bonus. Road navigation is not a network
planner; units benefit naturally when their path lies along the strip.

## Directional works

Earthworks and barricades share configurable mechanics and have distinct simple
meshes. Their facing points **towards the protected approach**. A defender must be
stationary, combat-effective, cohesion at least **45**, not changing formation,
not in Skirmish, facing within **45°** of the work, fully behind its front edge,
within `protectionDepth`, and fit its frontage. The attacker must be on the front
side within the forward **60° half-cone**. The strongest applicable modifier wins;
works never stack.

Default musket exposure is **×0.70**. Default frontal cavalry impact/casualty/
cohesion/shock factor is **×0.65** and additionally requires Steady morale. A
Shaken organized unit can still use physical musket cover. Rear/flank attacks,
moving/disorganized formations or incompatible positions receive no bonus.

**Works are not projectile colliders.** An earthwork does not magically absorb
cannonballs or grant artillery immunity. Physical barrier collision, fortification
construction/destruction and an AI occupation planner remain future work.

## Constant weather

| Preset | Authoritative effect | Presentation |
| --- | --- | --- |
| Clear | Exact legacy movement/reload/LOS path when no new features exist | Original light/terrain |
| Rain | Off-road infantry ×0.90, cavalry ×0.88, artillery ×0.80; firearm reload ×1.08, artillery reload ×1.03 | Dimmer light and 200 camera-local deterministic shader rain streaks |
| Fog | Default hard visibility limit **180 m**; beyond 55% of limit transmission fades from 1 to 0.35 at limit | Distance atmosphere; unobserved enemies hidden from 3D/2D/picking/markers |

Rain increases existing movement-disorder loss by **×1.12**, plus **0.004 cohesion
per off-road metre**. Main roads remove **80%**, tracks **40%** of the wet movement
penalty/additional flat disorder. Rain uses reload alone for firearm effects: no
additional random misfire, accuracy or gravitational penalties.

Weather parameters are fields of `weather` (`infantryWetSpeed`, `cavalryWetSpeed`,
`artilleryWetSpeed`, `firearmReload`, `artilleryReload`, `wetDisorder`,
`visibilityLimit`), with validated modest bounds. Weather is immutable per battle.
Fog combines with hill/forest LOS and applies to manual/automatic targeting,
including artillery acquisition. Existing artillery spotter/obscured-fire rules
remain subject to the distance limit; **a projectile already in flight can travel
beyond it**. The AI uses existing detected/last-contact behaviour, not a new
intelligence system. The viewer uses Blue's army LOS; this is not persistent
fog-of-war or a recon campaign system. Fog density compensates for tactical camera
height so close friendly units remain readable.

## Validation and measurements

```bash
bash tools/dotnet.sh test godot/Simulation.Tests
.venv/bin/python -m pytest -q
bash tools/godot.sh --headless --script tests/test_environment.gd
# Actual GPU / visual checks (not --headless):
bash tools/godot.sh --rendering-method gl_compatibility --script tests/test_environment.gd -- --test-capture

bash tools/dotnet.sh build godot/Simulation.Runner -c Release
.venv/bin/python -m migration_tools.benchmark_environment --repeat 3
.venv/bin/python -m migration_tools.benchmark_live --environment river --frames 600
```

All headless regression suites, deterministic scenario runs, actual measured
performance, Clear-reference comparison and remaining limits are recorded below.

### Recorded validation (6 November 2026)

- **551 .NET tests passed**, including 39 environmental cases added to the 512-test
  baseline. Existing movement/combat/RNG reference fixtures remain intact.
- **674 Python tests passed**; no Python simulation files were changed.
- **537 Godot checks passed across 14 scripts**, including 28 environment checks.
  These exercise live/native geometry, wet/fog presentation, hidden enemies, custom
  weather/save/load, crossing selector, terrain mesh retention, 2D switching,
  existing camera controls and Python replay seeking. The 28 environment checks
  also passed in the real X11/OpenGL renderer on the GTX 1080, with screenshots.
- All eight lab states/events/random streams reproduced exactly across repeated
  headless runs; invariants check every active footprint against water each step.
  Native and custom files produced by the documented authoring commands ran
  successfully in the standalone runner.
- Geometry/interaction coverage includes swept water exclusion; pinned lines;
  timed infantry/cavalry/artillery passage; opposite friendly traffic and stale
  queue cancellation; selected fords; two-river routing; ford permissions/charge
  momentum; routing along banks; stationary rain recovery; reload ratios; fog AI
  acquisition; actual volley/charge protection and unshielded physical shot;
  water impacts; save compatibility and exact Clear traces.

### Headless performance

Ryzen 5 7600X3D, .NET 10 Release. Each row is the median of three independent
70-simulated-second runs (100 warmup ticks, 600 measured ticks, fixed seed 1796).
These are **movement-heavy matched initial workloads** with the existing combat
systems enabled and explicit march orders. Different obstacles change subsequent
positions/contact, so timings are not a pure isolated geometry microbenchmark or
an AI/combat throughput claim. Initial inputs are shared across variants; AI
planning is not measured in this matrix. Allocation totals include the complete
native tick, not just environmental work.

| Regiments | Map | Mean ms/tick | p95 ms/tick | Ticks/s | KiB allocated/tick | Geometry queries | Route plans |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | baseline | 0.226 | 0.229 | 4421 | 67 | 0 | 0 |
| 12 | river | 0.383 | 0.424 | 2609 | 162 | 170 | 12 |
| 12 | roads | 0.245 | 0.248 | 4066 | 76 | 16742 | 0 |
| 12 | rain | 0.231 | 0.242 | 4312 | 75 | 16742 | 0 |
| 12 | fog | 0.235 | 0.237 | 4243 | 68 | 0 | 0 |
| 24 | baseline | 0.500 | 0.545 | 1997 | 136 | 0 | 0 |
| 24 | river | 0.936 | 1.324 | 1067 | 338 | 1755 | 24 |
| 24 | roads | 0.530 | 0.575 | 1885 | 154 | 33484 | 0 |
| 24 | rain | 0.522 | 0.581 | 1915 | 153 | 33484 | 0 |
| 24 | fog | 0.513 | 0.562 | 1946 | 138 | 0 | 0 |
| 36 | baseline | 0.772 | 0.922 | 1294 | 214 | 0 | 0 |
| 36 | river | 1.107 | 1.840 | 903 | 487 | 1831 | 36 |
| 36 | roads | 0.824 | 0.982 | 1212 | 241 | 50226 | 0 |
| 36 | rain | 0.853 | 0.991 | 1171 | 240 | 50226 | 0 |
| 36 | fog | 0.922 | 1.048 | 1084 | 222 | 0 | 0 |
| 60 | baseline | 1.255 | 2.224 | 797 | 368 | 0 | 0 |
| 60 | river | 1.171 | 3.209 | 853 | 791 | 2135 | 60 |
| 60 | roads | 1.195 | 2.295 | 836 | 406 | 83704 | 0 |
| 60 | rain | 1.218 | 2.138 | 821 | 411 | 83704 | 0 |
| 60 | fog | 1.607 | 2.319 | 622 | 390 | 0 | 0 |

Query counts are diagnostic geometry calls/narrow-phase work, not an isolated
query timer. Static grids reject dry swept bounds before hull/clip allocation.
This measured change reduced the 60-regiment river workload from approximately
1,200 to **791 KiB allocated per tick**; clip/hull buffers near water and the
existing general movement/combat collections remain allocation hotspots. Fog
rejects out-of-range pairs before allocating LOS cache entries or sampling terrain.
No authoritative ticks are dropped.

[Raw final headless reports](../benchmark-results/environment-after.json),
[pre-change same-input baseline](../benchmark-results/environment-before.json).
The latter is one run per count, not an equally repeated benchmark; timing varies
with JIT/scheduling and should not be interpreted as a precise speed regression.
Here are the observed values rather than a claimed speedup:

| Regiments | Before Clear mean ms | After Clear mean ms | Final state / RNG match |
| --- | ---: | ---: | --- |
| 12 | 0.223 | 0.226 | Exact |
| 24 | 0.571 | 0.500 | Exact |
| 36 | 0.765 | 0.772 | Exact |
| 60 | 1.589 | 1.255 | Exact |

All four matched final positions, strength, morale, cohesion, routing/withdrawal
states and random-draw counts exactly. Whole-snapshot hashes differ because the
new optional environment DTO adds serialized fields; they are not used as an
incorrect cross-version determinism comparison. Within-version repeated benchmark
hashes match. New terrain/weather rules have no Python equivalents yet; existing
Python movement/combat fixtures provide legacy regression coverage.

### Actual Godot rendering

X11, NVIDIA GTX 1080 (driver 580.196.07), Godot 4.7.2 .NET, OpenGL compatibility,
shadows, 32 decorative figures per regiment, 800 m camera span, 4× simulation.
Each run measures 600 frames after 300 simulation warmup ticks. Vsync is disabled.
Frame values are complete frame times, not console tick timings. Each terrain
mesh was built **once**; no snapshot backlog/cache accumulated (ordinary fixed-step
fractional debt remains below one tick). Fog renders fewer soldiers, so its FPS
must not be presented as an equal-visible-load optimization over Clear.

| Regiments | Map | Mean frame ms | p95 frame ms | FPS (1000/mean) |
| --- | --- | ---: | ---: | ---: |
| 12 | baseline | 2.41 | 4.22 | 414 |
| 12 | river | 2.60 | 4.57 | 385 |
| 12 | roads | 2.43 | 4.20 | 412 |
| 12 | rain | 2.49 | 4.24 | 401 |
| 12 | fog | 1.71 | 3.53 | 586 |
| 24 | baseline | 4.61 | 7.79 | 217 |
| 24 | river | 5.14 | 8.77 | 195 |
| 24 | roads | 4.63 | 7.78 | 216 |
| 24 | rain | 4.82 | 8.11 | 208 |
| 24 | fog | 2.64 | 5.67 | 378 |
| 36 | baseline | 7.29 | 11.51 | 137 |
| 36 | river | 8.15 | 12.46 | 123 |
| 36 | roads | 7.25 | 11.64 | 138 |
| 36 | rain | 7.45 | 11.84 | 134 |
| 36 | fog | 4.19 | 9.29 | 239 |
| 60 | baseline | 15.21 | 23.10 | 66 |
| 60 | river | 17.03 | 28.71 | 59 |
| 60 | roads | 14.79 | 22.48 | 68 |
| 60 | rain | 15.18 | 22.94 | 66 |
| 60 | fog | 9.07 | 17.49 | 110 |

Full frame/CPU/tick/debt/visibility data is in
`benchmark-results/environment-{baseline,river,roads,rain,fog}-live-{12,24,36,60}.json`.
The initial river/fog measurements are retained as `*-live-before-*.json`; bridge
height queries now use cached deck axes/extents, and far fog checks do not create
LOS-cache entries. These are local development measurements, not a hardware-independent
FPS guarantee. Larger/high-detail battles still have visible frame-time variation;
profile them again with actual campaign deployments and objectives.

### Remaining limitations / next campaign step

- No coordinated crossing assault, safe-crossing score, bridgehead or defensive
  occupation planner. Army-centre/last-contact goals can be unreachable, in which
  case navigation waits rather than marching through water. Give explicit crossing
  movement orders on difficult maps. Empty/no-crossing laboratories can remain
  inconclusive; no artificial victory is declared.
- The dry visibility graph is conservative. Sharp bends, cramped approaches,
  crossing endpoints near map boundaries, or deliberate enemy/held formations on
  the deck can block routes. Broader navigation and tactical AI should be tested
  with the actual six campaign maps, not inferred from these laboratories.
- Bridge lanes serialize friendly traffic mechanically; they are not a capacity
  model or a guarantee of passage through a defended exit. Compact transit has
  timed footprints, not individual-file soldier simulation.
- Rivers use constant-width segments and simple fixed banks. Rendering samples
  bank height at 5 m; there is no erosion, continuous ford hydrodynamics, variable
  soil, seasons or weather transitions. Author forest regions sensibly around
  riverbanks; forest definitions remain the existing analytic regions.
- Defensive cover is geometric/modifier based. No earthwork/barricade projectile
  collision, construction/destruction, engineer behaviour or physical building
  simulation is claimed.
- New environmental rules are native C# features. Python replays are preserved;
  the Python application does not simulate these new JSON environmental fields.
- Allocation remains measurable near banks and in the existing simulation systems.
  The benchmarks report it rather than claiming allocation-free simulation.

Next: author the campaign battlefields and crossing approaches with these data
helpers, then evaluate objective-driven AI on them. Add coordinated crossings and
fortification occupation only when those concrete campaign behaviours require it.
