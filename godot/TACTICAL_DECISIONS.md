# Tactical decisions: shared purposes, support, and firing positions

This describes the first tactical pass. The subsequent [army director and formation fix](ARMY_DIRECTOR.md) supersede its reserve and cavalry-approach rules and include a new strength evaluation.

The standalone AI now adds three layers to the existing decision schedule. These
are decisions, not changes to weapon damage, morale formulas, or movement speed.

## Shared assignments

A regiment retains an assignment while choosing immediate targets and orders.
Assignments support `attack`, `defend`, `support`, and `reserve`. Several regiments
can share an assignment. Initial deployment offsets provide distinct destination
slots within 65% of the assignment radius.

Campaign capture, hold, and delay objectives supply assignments automatically.
Rescue and interception objectives follow the relevant detachment/convoy centroid;
enemy actors must be perceived before their positions can inform that purpose.
Completed objectives release their assignments. Explicit groups take precedence
over army-wide assignments, with stable distance/ID tie-breaking.

Defenders return when outside radius + half their weapon range, unless an immediate
threat is within 80 m. Local fighting and bounded pursuit can interrupt the purpose
without deleting it. Existing authored routes run first; their final `hold` remains
binding. Player orders and mandatory routing remain authoritative.

Optional `mission.assignments` JSON uses the existing scenario format:

```json
{
  "id": "bridge-defence",
  "army": 0,
  "kind": "defend",
  "position": {"x": 850, "y": 450},
  "radius": 110,
  "units": [0, 1],
  "objectiveId": "eastern-bank"
}
```

`units` and `objectiveId` are optional. C# callers can use `battle.Ai.Assign(...)`
and `RemoveAssignment(id)`. Existing saves/scenarios need no migration. Generic
custom battles retain their chosen army strategy unless assignments are supplied.
There is no new mouse command scheme or crossing planner.

## Local support

Spatial queries assess supporting units within 180 m of each participant. Exclude
routed, rallying, destroyed, withdrawn and noncombatant supporters. Enemy supporters
must be perceived by the observing regiment, including fog/forest restrictions.

Estimated power uses strength, melee capability, cohesion, morale state, facing,
formation-transition readiness, woodland effects, and artillery deployment. Support
has a 0.65 weight falling linearly to zero at 180 m. It affects disengagement,
ordinary infantry target preference, assault willingness, and autonomous cavalry
commitment. Routing targets remain legitimate pursuit opportunities.

Infantry compares up to three detected candidates, penalizing an unfavorable local
power ratio and distance from its objective. Changing a viable target requires a
15-point improvement after a 10-second commitment. Existing opportunistic commander
logic retains its own scoring and persistence.

This is an estimate, not a battle prediction: it does not compute the time for
supporters to cross a river or simulate their future volleys.

## Infantry firing positions

Within 1.8 weapon ranges, compare the current location and eight nearby candidates
(35/65 m lateral moves, 35 m range adjustments and diagonals). Score actual terrain
visibility/transmission, existing friendly-fire obstruction geometry, preferred
range, woodland cover, modest elevation, nearby support/threats, and movement/turning
cost. Leaving a clear firing lane additionally costs estimated firing time.

Candidate destinations must fit the intended firing formation, avoid known occupied
footprints, and pass a swept-water check. Local positioning cannot cross a river;
longer approaches continue through existing crossing navigation. Riflemen retain
longer preferred range and skirmish withdrawal behaviour. Melee-only infantry is
excluded.

Require a score improvement greater than 14. Search at most every 8 simulation
seconds. A selected move commits for up to 18 seconds, with a 24-second search
cooldown. Invalid destinations and immediate close combat can interrupt it. Useful
positions hold and fire instead of continually advancing. Formation changes retain
the existing transition time and 20-second AI cooldown.

The selected-regiment inspector exposes the assignment, friendly/enemy support,
and last positioning reason. Headless snapshots expose the same information;
`AiPositionEvaluations` counts scored positions.

## Laboratories and validation

Select these in Godot Live Mode's existing scenario menu:

- **AI: Shared road objective** (`ai-shared-objective`).
- **AI: Supported line and isolated flank** (`ai-local-support`).
- **AI: Clear a blocked firing lane** (`ai-firing-positions`).

Headless example:

```bash
bash tools/dotnet.sh run --project godot/Simulation.Runner -- \
  --combat-scenario ai-firing-positions --duration 600
bash tools/dotnet.sh test godot/Simulation.Tests
```

`TacticalContextTests` covers assignments, player authority, objective completion,
authored routes, support and fog, disengagement, target persistence, clear-lane
movement, stable firing, rifles, river safety, deterministic battles and all three
laboratories. Existing Python-reference calculation tests continue to run; AI
trajectories intentionally differ from the older Python heuristics.

## Validation results (2026-11-07)

- .NET: **603 passed**, including 22 new tactical tests; baseline was 581.
- Godot: **569 checks passed across 15 scripts**, including camera, replay, campaign,
  environment, controls, live adapter and new inspector defaults.
- Two natural-start AI campaigns completed all six stages with decisive endings:
  - Seed 17, rescue: stages 1–6 took 283.7, 293.1, 480.0, 240.3, 410.8, 358.5 simulation seconds.
  - Seed 31, intercept: stages 1–6 took 499.9, 308.9, 480.0, 157.8, 421.0, 445.3 simulation seconds.

These are regression observations, not evidence of stronger human opposition or
final campaign balance. Two seeds do not establish win rates. Python source was
unchanged; native regression tests include the existing Python-reference fixtures.

Release headless benchmarks compare the pre-change Git snapshot (`9a23276`) with
the new code, alternating before/after runs, three repeats per workload; values are
medians. Each existing `benchmark-ai-N` workload measures 600 ticks after warm-up.
Repeated final checksums matched within each implementation. Different tactical
trajectories mean these timings include changed movement/combat work as well as AI.

| Regiments | Before mean ms | After mean ms | After p95 ms | After ticks/s | After allocated KB/tick |
|---|---:|---:|---:|---:|---:|
| 12 | 0.437 | 0.575 | 0.812 | 1736 | 149.3 |
| 24 | 0.882 | 1.044 | 1.416 | 957 | 293.3 |
| 36 | 1.415 | 1.616 | 2.164 | 618 | 420.5 |
| 60 | 2.574 | 2.635 | 3.745 | 379 | 740.6 |

There is measurable overhead: mean ticks increase approximately 32%, 18%, 14%,
and 2% respectively. Allocations rise about 25%, 18%, 11%, and 9%. AI decision time
roughly doubles, while total throughput remains far above the fixed 10 Hz battle
tick rate. The bounded search deliberately runs on AI decisions, not rendered frames.
Further allocation tuning is worthwhile if larger battles or higher speed settings
expose a measured bottleneck. No new GPU frame-rate claim is made; presentation
changes in this pass are inspector text and existing-scenario menu entries.

Raw local reports are under `benchmark-results/tactical-decisions/` (the existing
`.gitignore` excludes generated benchmark artifacts). Reproduce current timings:

```bash
bash tools/dotnet.sh build godot/Simulation.Runner -c Release
.venv/bin/python -m migration_tools.benchmark_ai --repeats 3
```

Limitations: support is a local estimate rather than coordinated attack planning;
assignments use static deployment spacing rather than a frontage allocator; local
position search is bounded and cannot discover distant superior firing positions.
Authored approach/hold directives continue to override autonomous purpose. There is
no new crossing-operation planner, dynamic reserve dispatcher, or broad-order mouse
interface in this pass.

## Subsequent strength evaluation

The matched old/new tournament found **56 new wins, 55 old wins and 9 unresolved**
over 120 side-swapped games. Functional regression tests passing did not establish
a stronger opponent. There are severe line/woodland regressions associated with
firing-position decisions suppressing timely firing-formation preparation. See the
[full measured evaluation and ablations](../docs/AI_TACTICAL_EVALUATION.md) before
treating these tactical extensions as an improvement in overall AI strength.
