# Milestone 2 combat port

**Current melee retention:** new engagements still require the original .75 m
footprint contact. Established melee persists within a 4 m oriented-footprint
margin (`Rules.MeleeDisengageDistance`), preventing flicker as units move or flee.
Pulses keep their existing timers; entering the retention area does not create a
new engagement, impact or free hit. Escaping beyond it, destruction, withdrawal,
or a transition into moving cavalry pursuit clears the engagement. Routing and
explicit movement/disengagement continue normally. Legacy Python numerical traces
explicitly select .75 m release distance to preserve their original contract.


**Current status:** [Milestone 3](MORALE_CAVALRY.md) adds morale/routing/rallying and cavalry charge/pursuit to normal Live mode. This page retains the musket/ordinary-melee audit and the **frozen-morale M2 reference contract**; its temporary annihilation rule is now only used by legacy fixtures. Current launch controls and scope are in [README.md](README.md).

## Audit and port decisions

The current reference is `simulation/terrain.py`, `combat.py`, `ai.py:destination/turn_toward`, and the phase order in `battle.py`. Milestone 1 already ports analytic hills/forests, five-point footprint terrain movement/cohesion, spatial candidates, soft congestion and stable settling. These are extended, not replaced. Python combat code remains unchanged.

The implementation preserves these ordinary-infantry rules:

- LOS samples every `min(4 m, minimum feature radius / 4)` along the centre ray. Sight height is ground +1.7 m at each end. Intervening ground above the interpolated sight line blocks fire. Forest density accumulates below the 12 m canopy: 75 vegetation-metres is opaque, transmission is `exp(-vegetation/60)`. Queries are deterministic and cached by exact endpoints.
- Range is 155 m; half firing arc is 0.65 radians; reload is `max(.5,12*(1+fatigue*.003))` simulated seconds. Line/column/loose firing coefficients are 1/.32/.52. Ordinary shots are `max(1,int(strength*.42*formation*lane_factor))`.
- Base hit probability is `.14*(1-.65*distance/range)*(.3+cohesion/140)`, multiplied by cover and firing conditions, then clamped to [0,.95]. Moving fire is ×.45 and dispersed targets ×.65. Casualties use independent Bernoulli draws and the current ×1.10 volley multiplier with seeded fractional rounding.
- Forest protection is directional, using actual footprint cover and sight-line vegetation. Outgoing woodland fire is impaired by `.45*cover*min(1,vegetation/40)`, incoming protection by `.60*target_cover*min(1,vegetation/4)`. Ordinary infantry has no specialist woodland bonuses.
- Friendly fire uses three frontage rays at −.35/0/+.35 widths, with elevation clearance .5 m. Coincident formations share frontage instead of becoming mutually opaque; loose screens have .35 density. Overlapping target groups remain hittable. This reuses the existing OBB/spatial geometry.
- Contact uses oriented rectangles with .75 m tolerance. Melee pulses every 2 s, in stable pair/attacker order. Flank factors are 1 below π/3, 1.6 below 2.3 radians, otherwise 2.2. Power is `strength*.013*(.3+cohesion/100)*flank*terrain`, with the existing forest/formation and uphill penalties. A uniform [.65,1.35] draw resolves losses, with the ordinary steady infantry minimum of one.
- Damage reduces cohesion by `losses/max_strength*130 + shock*.35`. Volley shock is `.9*lane_factor`; melee shock follows flank/terrain. Morale changes, morale-state penalties, charges, commanders and specialist abilities remain excluded; no provisional routing is introduced.

Simple standing orders use the existing rate-limited threat facing and attack/advance stopping rules. Explicit targets remain binding while valid. Melee does not prevent an explicit movement order from disengaging. Temporary completion counts surviving combat-enabled infantry armies; movement-only cavalry/artillery do not keep a finished engagement running.

The RNG boundary is explicit: live C# uses a specified **SplitMix64-v1** stream, not `System.Random` or assumed Python seeding compatibility. The signed seed is converted to uint64; each draw adds `0x9E3779B97F4A7C15`, applies SplitMix64's xor/multiply mixing, and divides the top 53 bits by 2⁵³. Uniform draws use `a+(b-a)*draw`. Stable ID/pair/shot order and fractional rounding are part of the contract. A finite controlled tape and an isolated Python implementation validate exact draws/casualty ordering without changing Python's actual game RNG. The first 100 golden doubles are checked exactly.

Before editing, 578 pytest and 38 xUnit tests passed and the movement benchmark was saved. `/tmp/rtt-before-milestone2.tar.gz` holds a source checkpoint; `.git` is a read-only empty stub. Implementation followed terrain/visibility → combat/standing orders → fixed tick/events → reference comparisons → existing live renderer. No Python game algorithms or camera controller were edited.

## Architecture and terrain

- `Simulation/Terrain/TerrainMap.cs`: the existing analytic elevation/gradient/forest/movement model plus direct visibility sampling. Compact/Gaussian hills and smooth elliptical forests are immutable battlefield definitions. Footprint terrain uses centre + four corners, column/loose forest multipliers and the existing category profiles. Cohesion loss scales with actual distance travelled; stationary woodland troops recover rather than continually deteriorating.
- `Terrain/Visibility.cs`: exact `(from,to)` cache, shared by intent, acquisition and firing. The 32,768-entry cap clears without changing results. No quantized positions, delayed firing visibility, render raycasts or geometry generation enters authority.
- `Combat/CombatSystem.cs`: reusable arc, obstruction, volley and melee calculations; standing orders; damage/cohesion; bounded pair cooldowns and cleanup. Spatial broad phases and cached formation geometry are reused. The friendly-overlap group is rebuilt only when queried after a phase/pose change.
- `Combat/CombatEvent.cs`: stable sequence/tick/time events and temporary result. Events retain at most 4,096 entries; Godot receives the recent window only on tick changes. Damage and effects never consume separate RNG streams.
- `Core/BattleSimulation.cs`: commands/intents → congestion/settling/avoidance → movement/reload → congestion loss → melee → firing → cleanup/recovery → enemy SAT correction → completion. A pulse damages the later ID before calculating its retaliation, matching Python's sequential rules. Current movement tests still run with `CombatEnabled=false`.
- `simulation_data/movement_archetypes.json`: the existing shared static data now includes a weapon profile for standard infantry. Other current movement archetypes have no outgoing combat. `simulation_data/combat_scenarios/*.json` is shared input for live mode, console, tests and Python tools, embedded in the simulation DLL.

Godot's bridge exports the **same** analytic hill/forest definitions to `BattleFrame.TerrainData`; the existing cached terrain mesh is a presentation approximation of those definitions. Gameplay does not sample a different decorative mesh. High ground changes LOS, slope movement and uphill melee resistance; no new universal high-ground accuracy bonus is added.

## Orders and presentation

Hold fires at the nearest valid enemy and gradually faces threats in its front hemisphere. Attack binds its selected enemy, approaches to musket range and turns; Advance approaches to 85% range. These are standing-order rules, not tactical army AI. Orders do not grant instant rotation. Move retains its destination, permits firing under the existing ×.45 accuracy penalty, and can disengage from melee. Reload continues in simulated time during movement/melee/reforming, while firing is disabled during a formation transition or melee contact.

In Godot, choose **Live (C#)** then the scenario selector. Right-click an enemy to attack, ground to move, **H** to hold/fire, **V** to advance. **L/J/K** change supported formations, **.** steps paused authority. Space/speeds/reset and all camera controls are preserved. See [README.md](README.md) for launch commands. The selected-unit inspector shows target, weapon range, reload, visibility, last volley frontage/accuracy, terrain and cohesion. Morale is labelled inactive; live flag bars show strength instead. Damage reduces stable decorative-figure slots without replacing regiment nodes. Authoritative volley/contact/destruction events drive smoke, rings and MELEE labels. Replay seeking and live reset rebuild effects from the appropriate event window.

The six scenarios cover opposing firing lines, uphill attackers/ridge defenders, forest concealment, immediate flank contact, front/rear/clear-flank firing lanes, and twelve combined-arms movement actors with infantry combat. Terrain scenarios use scheduled Red attack orders. The combined scenario's cavalry/artillery are movable/damageable obstacles with outgoing combat explicitly disabled.

## Reference validation

`migration_tools/combat_reference.py` calls current Python terrain, movement, standing-order and combat functions with neutral commanders and frozen morale states. It excludes routing, charges, artillery and army-level AI in **both** implementations. Python game sources and its normal `random.Random` stream are untouched.

Twenty-six probes compare elevation, forests, slopes, LOS/transmission, firing arc/frontage/accuracy, controlled casualties/reload, friendly screens, overlapping lines/targets and front/flank/rear/forest/uphill melee. Six traces cover five live scenarios (30 s; ridge/forest 90 s) and a 70 s mixed-terrain **moving-under-fire + melee** workload. Sampled positions, facing, strength, cohesion, reload, combat states and RNG draw counts are compared at 1e-5 tolerance, with exact repeated C# output. The eleven original movement fixtures are retained. Tests also cover actual timed disengagement, enemy destruction/target cleanup, completion, clock scheduling, invariants at all four benchmark sizes and effect/reset/replay integration.

## Deliberate limits and differences

- Morale remains fixed; no state transitions, routing, rallying, morale penalties, support auras or commander/specialist effects are applied. Cohesion damage/recovery is functional. Standard infantry uses steady melee effectiveness. No temporary morale threshold is invented.
- Only weapon-enabled ordinary infantry deals damage. Cavalry, artillery and the movement skirmisher have no provisional attack model. Infantry can damage them, but these unsupported units do not prolong temporary infantry-annihilation victory. This is a test rule, separate from campaign/proper morale-driven victory.
- Infantry Charge is not ported. Attack seeks a firefight; moving to ground beyond an enemy can initiate normal melee. Artillery projectiles remain replay-only. No enemy army planner or flanking AI is present.
- Explicit hidden targets remain bound; a regiment approaches its last-seen/ordered position. This is a small adaptation around Python perception/shared-army knowledge dependencies, not a full fog-of-war model. Invalid/dead targets are removed.
- Destruction immediately removes contact/collision participation and clears references. Python may retain an inactive formation until a later phase. Melee cooldowns survive a brief contact gap until their deadline, preventing boundary flicker from granting extra pulses.
- Exact RNG parity is claimed only for the **controlled oracle**, not a normal Python battle using MT19937. Neutral frozen-morale engagements are not complete Python battle replays. Different CPUs/math libraries still require tolerance-aware validation.
- Without morale, last survivors can fight for a long time. The seed-17 duel reaches annihilation at 919.7 simulated seconds. There is no campaign or after-action screen in native live mode; completion displays the winning army and Reset remains available.

Validation: **102 xUnit**, **614 pytest**, **39 native combat**, **39 preserved live movement**, **58 camera**, **74 3D viewer** and **60 playback** checks pass. The combat suite runs headlessly and in an actual GPU window, including completion, final-frame display, follow cleanup, reset and small-window controls. All six sampled combat traces have zero observed numeric difference on this host. Headless/GPU timings are in [MIGRATION.md](../MIGRATION.md) and [PERFORMANCE.md](../PERFORMANCE.md). Commands for regenerating fixtures, console exports, tests and JSON/CSV performance runs are in [README.md](README.md). Generated reports stay under ignored `benchmark-results/`; no profiler dumps are source assets.
