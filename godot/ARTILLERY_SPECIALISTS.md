# Milestone 4 audit and implementation contract

Source of truth: `simulation/projectiles.py`, `archetypes.py`, `combat.py`,
`morale.py`, `movement.py`, `terrain.py`, `cavalry.py`, `regiment.py`.
Python simulation code remains unchanged. Source checkpoint is
`/tmp/rtt-before-milestone4.tar.gz`; this checkout has no writable Git history.

## Audited rules

Round shot only: no ammunition inventories, canister, or calibre system exists.
100 m/s muzzle velocity; elevation solves gravity flight to scattered ground aim.
45 m horizontal scatter per axis, limited to half target distance, doubled by
full forest cover. Independent ±3 m/s vertical error. Muzzle elevation +1.2 m;
flat fields clamp pre-error vertical speed nonnegative. Salvos use evenly spaced
origins over 80% battery width. Operational guns are crew-strength dependent.

Flight uses absolute elevation, gravity 9.81, 14 s lifetime, 50 m field margin.
Nonempty terrain uses ≤2 m spatial and ≤.025 s temporal substeps, adapted to
feature radius/4. Surface contact is clipped by 16 binary iterations. Footprint
hits are swept and ordered by entry then ID; shots above ground+3 m miss troops.
Each regiment can be hit once per projectile lifetime (the Python hit-ID rule).
Damage is integer uniform(5,13) × energy, ×.75 against skirmish formation; shock
5×energy. Energy retains .75 after each regiment, including friendly hits.
Forest drag below 12 m canopy is exp(-density×distance×.008). Ground response
uses analytic normal, .78 horizontal damping / 1.26 reflected normal component,
energy×.72; terminate at 5 bounces or energy≤.15. No arbitrary enfilade multiplier:
formation orientation determines swept intersection, not per-rank damage.

Field battery: 48 crew, six guns, range440, reload19, speed1.8, limber3/setup8 s.
Horse battery: 40 crew, four guns, range360, reload17, speed 3.8, limber1/setup3 s,
shot power .65. Initially stationary batteries are already deployed in Python.
Travelling batteries reset setup, never fire limbered, and retain reload progress.
Explicit artillery targets ignore terrain LOS but obey range/arc; automatic fire
requires own/friendly perception. Once launched, friendly formations are physical
obstacles regardless of targeting. Crew melee remains ×.10.

Prussian Drill: factor clamp((cohesion−40)/50); reload×(1−.25factor), formation
change×(1−.4factor), turning cohesion loss×(1−.5factor), accuracy×(.85+.30factor).
Woodland skirmishers: native stats/forest movement, concealment1.55, forest sight
opacity×(.7 at full cover), forest aim .5, outgoing forest penalty .25;
woodland skill=clamp(cover/.4), forest accuracy up to3.2×, melee power4.5×,
base melee damage/shock1.2×, forest shock2×. Open-field melee power .55.
Grenadiers: morale 96, discipline 1.2, melee 1.5, recovery1.25, shock resistance.78;
steady visible friends within 125 m gain .22 morale/s or .35 rallying, strongest
source only, no stacking; nearby rout shock resistance×.85.
Uhlans: 80 strength, speed 9, charge speed1.05, pursuit1.25, melee.7; impact×1.65
only against broken/disordered unprepared defenders with attacker speed>3.
Rifles: range 235, reload 22, accuracy 1.65; stationary non-melee aimed bonus up to
1.35, scaled by cohesion and visibility. No aiming wind-up exists in Python.

Full tactical skirmisher AI, commander modifiers/upgrades and campaign remain
out of scope. Manual skirmish/disengage must not imply the deferred autonomous AI.
Existing M1–M3 fixtures retain disabled new-system flags for reference stability.

## Implementation and manual use

`Simulation/Artillery/ArtillerySystem.cs` owns stable-ID projectile state and
snapshots. `CombatSystem` owns battery targeting/reload and shared casualty damage;
`MovementSystem` retains the already-ported limber/setup timers. Battery display
state is derived from those timers, not a competing state machine. Full firing
starts from an initially deployed battery, matching Python. Explicit Attack may
fire without LOS; automatic fire requires perception. Hold Fire pauses firing,
retaining target and reload; Resume Fire restores ordinary execution. Shots remain
lethal to friendly troops even if a subsequent cease-fire order is issued.

`SpecialistSystem` centralizes drill, reload, formation timing, aiming, exploit,
and non-stacking aura helpers. The shared archetype JSON contains all nine
archetypes (three generic plus six requested specialists), with stable Python IDs.
Each effect uses the shared terrain, combat, morale or cavalry calculation.
No specialist subclasses, paired-build bonuses, commander effects or new RNG exist.
Aura sources are visible/effective/steady and never support themselves. Support
uses spatial queries, and visibility cache keys now include vegetation opacity.
Specialist activation events are emitted once per effect/source per battle.

`ArtilleryEnabled` and `SpecialistsEnabled` are explicit scenario flags. Existing
M1–M3 headless fixtures keep their historical scope; normal Godot live combat
activates all implemented systems. Movement-only sandboxes remain combat-free.
Recorded Python files and recording format are unchanged. Native projectile
snapshots feed the existing BattleFrame shot DTOs and batched renderer directly;
there is no per-frame JSON or Godot projectile physics. Discontinuous bounces use
the existing interpolation boundary, avoiding a straight interpolation through soil.

Controls: right-click enemy Attack; right-click ground Move. **Y** Hold Fire,
**I** Resume Fire, **O** manual Skirmish stance/loose formation; **X** Disengage.
Skirmish stance permits fire and uses the loose formation, but does not implement
Python's autonomous standoff/withdrawal planner. Players manually move/disengage.
Existing B/U charges/pursuit, H/V hold/advance, L/J/K formations and all camera
controls remain. **F8** toggles trajectory-tangent/range/arc/target/aura debugging;
no debug mesh/height sampling runs when hidden. Tangents are not predictions of
future bounces. Battery energy/bounces remain available in typed projectile frames
and events. The inspector shows actual gun count, reload cycle, deployment timers,
fire hold, and situational drill/aimed factors.

## Demonstrations

All support fixed seeds and headless execution through `Simulation.Runner`:

| ID | Purpose |
|---|---|
| `open-shot` | Six-gun salvo across open ground |
| `ricochet` | Ground bounce and continued travel |
| `artillery-hills` | Analytic hill blocks physical trajectories |
| `enfilade` | Front versus rotated formation geometry |
| `friendly-fire` | Friendly line between muzzle and target |
| `battery-under-attack` | Uhlans reach vulnerable battery crew |
| `prussian-drill` | Generic and disciplined firing lines |
| `woodland-specialists` | Woodland skirmisher versus ordinary infantry |
| `grenadier-support` | Local steady morale anchor |
| `uhlan-charge` | Exploiting a disordered infantry target |
| `rifle-engagement` | 235 m rifle versus 155 m musket |
| `horse-redeployment` | Two batteries move, set up, then resume target fire |
| `combined-arms` | All six specialists in a terrain-aware engagement |

Example:

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --combat-scenario=combined-arms --live-seed=17
bash tools/dotnet.sh test godot/Simulation.Tests -c Release
.venv/bin/pytest -q
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release -- --combat-scenario friendly-fire --duration 70 --output benchmark-results/friendly-fire.json
.venv/bin/python -m migration_tools.artillery_reference
.venv/bin/python -m migration_tools.benchmark_artillery --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --artillery --output-dir benchmark-results/m4-gpu
bash tools/godot.sh --headless --script res://tests/test_artillery.gd
```

## Reference fidelity and limits

Five complete 20 s traces run **actual Python Battle.step**, neutral commanders,
no army AI, and the shared SplitMix64 test stream. They compare sampled positions,
facing, strength, morale, cohesion, reload and complete active projectile physics,
plus RNG consumption. Five additional direct Python physics traces exercise flat
flight, hill impact, forest drag, overflight misses and repeated ricochets. Nine
specialist probes compare current Python trait, visibility and terrain calculations.
Python tests regenerate these observations to guard against stale oracle data.
Ordinary Python still uses MT19937; equal game seeds alone do not guarantee parity.

Current Python has no per-rank penetration/enfilade damage, hit re-entry damage,
calibre/ammunition system or timed rifle aiming. The port deliberately does not
invent them: one projectile hits each regiment at most once for its whole lifetime;
orientation changes whether a path intersects, not an unconditional damage bonus.
The flat-field one-piece update and nonempty-terrain adaptive substeps are preserved.
A shallow surface hit loses the remainder of that substep, as in Python. This is
an arcade deterministic ballistic model, not continuous rigid-body physics.

Artillery ballistics and specialist abilities do not require full tactical AI.
Skirmisher autonomous retreat, battery autonomous position selection, commanders,
upgrades and campaigns remain deferred. No new assets, independent soldiers,
regiment types, terrain types, after-battle screen or camera algorithms were added.


One numerical migration fix is deliberately local to ballistics: a compensated,
scaled Euclidean norm reproduces Python `math.hypot` at integer substep boundaries.
A 1-ulp speed difference around 100 m/s otherwise changes ceil(speed×dt/2) from
5 to 6, and clipped ricochet position by centimetres. A 1,000-direction golden
fixture plus eight 700-tick stress comparisons guard this rule. General regiment
vector arithmetic and previous movement/cavalry fixtures remain unchanged.


## Validation results

261 xUnit and 668 pytest tests pass. Native checks pass: 40 artillery/specialist,
36 morale/cavalry,39 combat,39 movement,58 camera,74 3D viewer,60 replay. The
artillery suite also passes in a real GPU window. Godot/.NET builds and editor
load are clean. Eight matched stress workloads agree with Python final states
and draws across all repeats. Full headless/GPU measurements, allocation costs
and the measured +6.2% frozen-M3 guard are in [MIGRATION.md](../MIGRATION.md)
and [PERFORMANCE.md](../PERFORMANCE.md).
