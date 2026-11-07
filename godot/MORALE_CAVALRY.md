# Milestone 3 audit and port contract

Milestone 4 has since activated artillery and specialist hooks; see
[ARTILLERY_SPECIALISTS.md](ARTILLERY_SPECIALISTS.md). The scope/baseline statements
below record the M3 port; its formulas and legacy fixtures remain supported.

Reference: current `simulation/morale.py`, `routing.py`, `cavalry.py`,
`combat.py`, `movement.py`, `positioning.py`, `ai.py:destination/turn_toward`
and the actual phase order/victory test in `battle.py`. Python is unchanged.
Baseline: 102 xUnit tests pass; matching M2 performance is retained under
`benchmark-results/m3-combat-before.*`. Source checkpoint:
`/tmp/rtt-before-milestone3.tar.gz` (the checkout's `.git` is a read-only stub).

## Actual rules and dependencies

- Casualty morale loss is `(losses / maximum * 95 + shock * max(.65, resistance)) / discipline`.
  Cohesion still loses `losses/maximum*130 + shock*.35`. Attacker morale gains
  `.025*losses`. There is no additional invented casualty-rate accumulator.
- Routing threshold ≤23; wavering <40; steady→shaken <60; recovery to steady >66,
  wavering→shaken >46. Melee factors: 1/.70/.40/.10 for steady/shaken/wavering/
  routing; rallying interpolates .25→.60 using morale/cohesion recovery. Both power
  and melee shock use the state factor. Ineffective troops use fractional damage
  rather than the ordinary minimum-one casualty floor.
- Shaken/wavering musket accuracy is ×.80/×.55, in addition to existing cohesion
  and moving-fire factors. Shaky movement is ×.65; routing/rallying cannot fire.
  The full Python volley tail and long trace comparisons establish these factors.
- Threats within 160 m prevent ordinary morale recovery. If effective hostile
  strength exceeds local friendly support ×1.6, pressure costs .35 morale/s.
  Otherwise safe recovery is `(.35+.08*nearby effective friends)*discipline*recovery`
  per second; safe fatigue recovery is .1/s. Friends use 130 m radius.
- Routing loses 1 cohesion/s. After 22 s without perceived enemies and with
  >15% original strength, enter Rallying with morale ≥28. Safe rally recovery:
  .9 morale/s (cap60), 1.2 cohesion/s plus ordinary idle recovery. Duty resumes
  Shaken at morale≥48/cohesion≥45; approaching enemies interrupt rallying.
- Newly routed formations emit one shock at 145 m, linearly attenuated from15
  and divided by discipline. Opposing witnesses gain3 morale. Propagation is
  processed after state updates; cascades happen next tick, never recursively.
- Fleeing plans every1 s against effective threats within240 m, always considering
  contact within60 m. Eight deterministic escape rays score inverse-distance
  threat, crossings, heading persistence and home direction. Actual footprint
  edge within2 m of an outward exit marks Withdrawn, retaining surviving strength.
- Charge states: Approach, Charging, Melee, Pursuit, Recoil, Reforming. Eligibility
  requires range≤100 m, footprint gap≥12 m, alignment<.55 rad, cohesion≥50,
  fatigue<75, cover≤.45/slope≤.25, no detour and a ready/cooldown-cleared charge.
  Max speed12 m/s; acceleration2 m/s²; turning×.5; charge timeout16 s.
- Momentum = bounded speed above3 m/s × run-distance/12 × cohesion × velocity
  alignment × `(1-.8*cover)/(1+5*slope)`. A short start cannot grant full impact.
- Readiness belongs to stationary, steady, dense, front-facing infantry. Impact
  power = strength×.20×momentum×flank×(1−.85×readiness), uniform [.8,1.2];
  flank factors1/1.5/1.9; column target×.85. Shock24 and extra cohesion18 use
  momentum/resistance. Prepared resistance can trigger a40 m recoil, then reform.
- One sequence consumes one impact; no outgoing ordinary melee on that impact
  tick, though defenders can resist. Rearming requires gap≥30 m, timed clearance,
  4 s reform and20 s cooldown. Repeated orders never clear this lock.
- Pursuit requires routing target, valid attack-like order, cohesion≥25/fatigue<85.
  Gap≤6 m enters moving pursuit, matching the fleeing edge. Damage every2 s is
  a shared weighted budget divided by sqrt(pursuers), capped at12% target maximum.
  Resistance is one weak fractional budget, not a minimum casualty per pursuer.
  Shared aligned cavalry uses .02 crossing cost; lateral lanes are deterministic.
- Victory: effective surviving strength <18% of the army's **initial current**
  strength continuously for12 s; recovering fighting strength resets the timer.

Commander modifiers, auras, specialist passive abilities, infantry bayonet charge,
full army AI and artillery projectiles remain unported. Their hooks are neutral.
The standard cavalry's actual stats are sufficient for this milestone. Existing
movement archetypes retain their basic statistics; no new archetype is introduced.

## Implemented architecture

`Regiment` owns distinct `MoraleState` and `CavalryState` plus safe-time, escape,
charge sequence/lock/cooldown, momentum and pursuit data. The new `MoraleSystem`,
`RoutingSystem` and `CavalrySystem` extend the shared damage/movement/contact path.
There is no second engine or individual soldier simulation. `Rules.MoraleEnabled`
and `CavalryEnabled` preserve old M1/M2 fixtures; normal live combat enables both.

Phase order matches Python: commands → ordinary/routing intent → cavalry intent
and stable pursuit lanes → congestion/settling/avoidance → movement, acceleration
and momentum → congestion loss → contact/one-time impact/melee → aggregate pursuit
→ fire → morale/recovery/deferred rout shocks → enemy correction → victory.
The same ordinary melee system handles cavalry at ×.80 power. Artillery crew uses
the existing ×.10 weak melee factor without firing cannons. Current movement
specialists retain base melee stats; their ranged/passive abilities are deferred.

Morale radius queries use the phase's spatial index and exact LOS cache, with
range filtering first. Removing casualties invalidates spatial ordinals, so that
index is refreshed before morale only when removals occur. Route effects are
event-driven; cascades never recursively update states in the same tick. Charge
state work is O(1) against the existing target; pursuit groups are ordered by
stable IDs. No random scheduling, delayed LOS or changed timestep was introduced.

Snapshots append a small immutable `RegimentDynamics` record; native Godot
collections are copied on tick changes into the existing `BattleFrame` DTOs.
Neither renderer nor camera mutates authority. Morale warnings, routing disorder,
charge/pursuit labels, event rings and the selected-unit panel reuse existing
visuals. The native scenario registry populates the selector. The two order rows
fit 800×600; replay/movement modes restore their original layout and camera area.

## Scenarios and controls

Select **Live (C#)**, then a scenario; or launch one directly:

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --combat-scenario=routing-pursuit --live-seed=17
```

| Scenario ID | Purpose / fixed-seed observations |
|---|---|
| `infantry-under-fire` | Two firing lines per side; portable seed17 reaches morale victory at302.5 simulated seconds, with two new routs and living survivors. |
| `cascading-rout` | Three adjacent units break over successive ticks, with distinct finite shocks; all three can later rally while a reserve holds. |
| `prepared-charge` | Frontal defenders repel the charge; cavalry recoils/reforms and is vulnerable in the continuing engagement. |
| `flank-charge` | One impact disrupts the flank; pursuit causes149 additional casualties for1 cavalry pursuit loss in the60 s reference window. |
| `wavering-charge` | Disorganized infantry collapses;161 pursuit casualties for1 pursuit loss. |
| `routing-pursuit` | Fresh cavalry catches fleeing foot;143 pursuit casualties for2 pursuit losses. |
| `shared-pursuit` | Both cavalry regiments advance through overlap; two impacts and a bounded shared budget cause128 pursuit casualties for1 pursuit loss. |
| `safe-rally` | Routed troops stop after safety, gradually recover, and regain control Shaken rather than fully steady. |
| `difficult-charge` | Dense woodland/hills prevent a full-speed charge; no charge starts in the60 s reference window. |

These observations use the **shared portable test stream**, neutral commanders
and generic cavalry, not the normal Python game's MT19937 sequence. They establish
tactical relationships, not broad win-rate balance. Distant reserves prevent
isolated charge/pursuit/rally demonstrations ending prematurely through army
collapse. The six earlier combat templates also enable M3 in normal live mode.

Right-click an enemy to Attack (cavalry approaches and charges when eligible), or
ground to Move. **B** charges the current enemy, **U** pursues its routing target,
**X** disengages, **G** reforms by holding for ordinary recovery. **H/V** remain
Hold/Advance; **L/J/K** formations, Space/pause, ./step, R/reset and speed keys are
preserved. Reform never instantly resets morale, cohesion or the impact lock.
Routing/rallying units reject commands until returned to duty. Hold may still
fight in existing contact; use Disengage to turn and leave. Camera controls remain
unchanged, including physical dolly zoom and paused follow/navigation.

## Reference testing and determinism

`migration_tools/dynamics_reference.py` invokes actual Python `Battle.step()` with
no army planner, commanders or projectiles and the specified SplitMix64-v1 stream.
Thirty-eight controlled probes cover casualty morale/cohesion, thresholds and
hysteresis, recovery, escape directions, front/flank/rear impacts, charge momentum,
morale-state fire penalties and fractional broken melee. Ten full sampled traces
cover all nine demonstrations plus victory grace. The infantry
trace runs to an actual morale victory; the remainder run60–70 simulated seconds.

C# compares strength, morale, cohesion, fatigue, positions, facing, movement speed,
state, safe time, reload, charge state/distance/momentum/cooldown/sequence/readiness,
impact results, RNG consumption, rout/rally/cascade/charge/pursuit counts and result
at1e-5 tolerance. Repeated native snapshots/events are exactly reproducible on this
host. Python tests ensure the stored oracle still matches current game functions.
The original eleven movement and six M2 frozen-morale traces remain unchanged.

The four stress fixtures also compare final position/strength/morale/cohesion/state,
withdrawal, random draws and key activity counters after700 ticks in both languages.
They actually contain fire, new routs, charges, impacts and pursuit. Profiling is
optional and has a test proving it does not change state or RNG consumption.

## Intentional adaptations and limits

- Python retains some inactive last-speed/target data. Native snapshots explicitly
  clear dead/escaped motion and obsolete current references. The Python oracle
  normalizes **inactive speed only** to zero; living motion/formulas are compared.
  The original one-tick enemy-correction participant list is retained for parity.
- `Pursue`, `Disengage` and `Reform` are convenient explicit command aliases around
  the existing attack/move/hold mechanics. Explicit Pursue stops when its assigned
  target dies, escapes or recovers; it cannot silently retarget another fugitive.
  Attack/Charge retain Python's ordinary nearest-enemy fallback after invalidation.
- Actual footprint contact identifies a fugitive for pursuit even if a narrow ridge
  hid its centre before movement. This small safety fix prevents a null pursuit
  target at physical contact. Non-contact hidden targets use last-seen approach
  and cannot maintain a blind charge.
- Commander/aura/upgrade modifiers and specialist abilities remain neutral. No
  autonomous army plan, personality pursuit radius or automatic tactical flank
  planning is added. Explicitly ordered cavalry can remain in costly melee until
  commanded out, routed, or repulsed according to the ported rules.
- Routing is local steering with finite turns and rectangle footprints, not global
  pathfinding. A regiment can be cornered or caught before it turns away. Pursuit
  still respects real terrain, congestion, cohesion and fatigue limits.
- Artillery projectiles, infantry bayonet charge, full specialist weapons, campaign
  and commander effects remain unported. Battery crews still count as effective
  strength for victory, matching Python; artillery-only native combat is not a
  completed mode. Windows/packaged exports remain untested.
- No new after-battle screen or campaign flow was introduced. Results use the
  existing native HUD, with Reset. Escaped strength is retained, not recorded as
  killed. Original Python and its replay format/RNG are unchanged.

Tuning lives in `Simulation/Core/Rules.cs`, static archetype values in
`simulation_data/movement_archetypes.json`, and exact terrain profiles in
`Terrain/TerrainMap.cs`. Numeric bounds/stacking follow the Python rules. Current
test counts, measured timings, allocation diagnosis and reproduction commands are
in [MIGRATION.md](../MIGRATION.md), [PERFORMANCE.md](../PERFORMANCE.md) and
[README.md](README.md). Next priority: native artillery trajectories, terrain
impacts/bounces/penetration and friendly fire, before tactical army AI.
