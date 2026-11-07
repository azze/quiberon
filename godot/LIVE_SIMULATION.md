# Native C# live simulation

Live now includes [Milestone 4 artillery and specialists](ARTILLERY_SPECIALISTS.md), plus infantry combat and the [Milestone 3 morale/cavalry systems](MORALE_CAVALRY.md); the default is Player versus AI, with [native AI and named officers](AI_COMMANDERS.md). The original movement-only scenario remains in the selector as Movement Sandbox: six controllable Blue regiments (four infantry, cavalry, artillery) and two Red obstacles. The movement foundation below applies to both. [README.md](README.md) contains setup, controls and test commands.

## Simulation/presentation boundary

```text
Pure .NET Simulation library → immutable BattleSnapshot records
              ↓
LiveSimulationBridge.cs → native Godot in-memory collections, only on tick changes
              ↓
live_source.gd → BattleFrame / UnitState pairs + alpha
              ↓
Existing regiment/terrain/marker renderer + camera + inspector
              ↑
RecordingSource → BattlePlayback (unchanged replay path)
```

The standalone library references only .NET. No Node, Godot vector, scene tree, physics server or Godot navigation agent enters authoritative code. `Vec2` uses doubles and Python's X-right/Y-down clockwise convention. Godot receives float vectors at the presentation boundary; the existing `world_3d.gd` converts XY to XZ and negative Y-axis yaw. The bridge copies state; renderer interpolation cannot modify regiments. No JSON is generated or parsed per live frame. Offline fixture/runner JSON is a separate tool.

`SimulationClock` accumulates real seconds × speed, executing exact **0.1 s** ticks. The live driver measures monotonic `Time.get_ticks_usec()` intervals, avoiding Godot's capped/scaled/smoothed process delta under load. It retains excess time after its default **16-tick-per-frame** budget. It never discards ticks or uses a variable simulation step. Debt above one tick appears in the status line. Command queues apply at the next tick; pause does not accumulate additional time. Single stepping displays the completed tick. Normal rendering interpolates the latest two completed states, introducing up to one tick of visual latency. Camera motion always uses real frame delta.

## Ported mechanics

- Commands precede shared intents, previous-velocity congestion, stable settling, bounded avoidance, terrain steering, movement, post-move congestion loss, idle recovery and enemy SAT correction. Regiment iteration is sorted by ID, matching Python `Battle` construction.
- Line/column/skirmish dimensions and speed/turn coefficients match Python. Cavalry and artillery keep their original 40×18 / 28×18 m footprints. Line's 0.75 speed coefficient also applies to them, as in Python.
- Arrival is within 1 m, with optional rate-limited final facing in the core/fixtures. The current mouse interface issues position-only orders. Completed Move orders retain their preferred destination rather than converting to Hold.
- Formation changes take 7 s and cost 6 cohesion; movement pauses during the transition. Cavalry/artillery currently support their existing line formation only. The skirmisher supports column/loose.
- Batteries preserve 3 s limber and 8 s setup delays. No guns fire in live mode.
- Friendly OBB overlap remains passable. Congestion uses exact clipped area, the worst pair rather than stacking sums, measured velocity directions and relative speed. Stationary overlap alone does not continuously damage cohesion.
- Substantial persistent overlap triggers gradual settling after a delay. Explicit Hold priority, rest time and stable ID ties decide who stays. At most 24 nearby endpoint/route candidates are tried. Preferred orders remain intact; alternative goals stay reserved with retry/timeout hysteresis. No teleporting or global packing solver is introduced.
- Avoidance tries one conservative bounded detour per destination; moving allies are crossed. Timeout/congestion cancels the detour and preserves soft passage.
- Spatial queries use conservative 100 m cells and original deterministic candidate order; oriented footprints cache pose-derived geometry. Small battles retain direct pair iteration. Mutable enemy correction preserves its original three-pass pair traversal.
- Analytic compact/Gaussian elevation, gradients, smooth forests, five-point footprint movement sampling, slope/formation/category costs and bounded cavalry/artillery terrain detours are ported. Static forest coefficients for the selected archetypes remain data, not combat abilities. `--live-terrain` uses these actual rules, not visual-only hills.

## Tuning

Movement rules live in `Simulation/Core/Rules.cs`; formation profiles in `Units/Formation.cs`; static archetype data in `../simulation_data/movement_archetypes.json` (embedded in the core DLL). Terrain profiles/constants live in `Terrain/TerrainMap.cs`. The shared JSON contains standard infantry/cavalry/artillery and woodland skirmishers, exported from current Python definitions; tests check that it has not drifted.

| Parameter | Initial value |
|---|---:|
| Tick / formation duration | 0.1 s / 7 s |
| Minimum congestion speed | 0.5× |
| Same-direction / cavalry same-direction cost | 0.20 / 0.06 of crossing cost |
| Overtaking coefficient / stationary disruption fraction | 0.35 / 0.35 |
| Persistent overlap threshold / delay | 25% of both footprints / 2 s |
| Settling radius / gap / retry / timeout | 110 m / 4 m / 5 s / 60 s |
| Maximum avoidance extra distance / ratio | 100 m / 1.5× |
| Rest / moving cohesion recovery | 0.65 / 0.10 points per second |
| Terrain speed bounds | 0.20–1.12× |

Numerical data follows Python. Commander modifiers, Prussian Drill and acquired abilities are neutral/out of scope. Commander identity/name fields are plain data; default names are placeholders. Movement-only scenarios keep morale/strength constant. Normal combat enables morale, routing/rallying, fatigue recovery and cavalry: shaken/wavering movement is ×.65, charging uses bounded acceleration/turning, routed units lose cohesion and flee local threats. Those extensions use the same movement function and optional motion parameters, not a second mover.

## Validation and limitations

Eleven shared inputs test straight motion, turning, formation changes, opposing friendly crossing, cavalry overtaking, stationary separation, destination conflict, dense movement, bounds, artillery relocation and woodland traversal. C# xUnit tests compare sampled position, facing, formation, cohesion, movement state, orders, alternate destinations, fatigue and movement modifiers against Python, at **1e-5 absolute tolerance**. Repeated C# runs compare exact serialized snapshots. The Python harness calls the current movement functions and is independently checked against the original sandbox `Battle.step()` for eight cases. See [fixture documentation](../migration_tools/movement_fixtures/README.md).

Movement reference scenarios consume no simulation RNG. M2 combat uses the specified SplitMix64-v1 stream, with a finite draw tape and Python counterpart for reference tests; Python's actual game still uses its original RNG. Math library/tie differences on other platforms still need comparison tests. Terrain sampling caches have bounded size; C# clears a full footprint cache rather than reproducing Python's LRU eviction, affecting only cache performance.

The original bounded SAT correction prevents enemies marching through each other. Combat resolves infantry/cavalry contact first; pursuit instead matches the fleeing edge and uses a separate shared casualty interval. Shared compatible cavalry uses the original .02 pursuit congestion fraction and stable lateral lanes. Routing/rallying units cannot settle into stationary positions. M3 retains the Python correction participant list through the tick; spatial ordinals are rebuilt if casualties remove members before morale queries.

There is no tactical army planner, artillery physics, infantry bayonet charge, specialist/commander abilities, campaign or save-game migration. Live input is the shared small scenario schema, now with optional morale/state/dynamics flags. Old M1/M2 fixture flags preserve historical reference tests; normal Live combat enables M3. Reset/mode switching discards transient state, while escaped survivors retain strength in the final snapshot.

Runtime costs remain in spatial-index reconstruction and short-lived query collections; this milestone preserves the algorithm rather than prematurely replacing it. Managed allocation/tick is measured separately from renderer/native allocations. GPU frame results are live Open Field samples, not comparable to mixed-terrain combat replays. Current results and next migration priorities are in [MIGRATION.md](../MIGRATION.md).
