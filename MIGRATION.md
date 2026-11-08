# Controlled migration to Godot

The complete Python game remains operational and authoritative for recorded battles.
Godot now runs native C# combined arms, autonomous tactical AI and named commanders
with personalities/starting specializations, acquired commander abilities, infantry
bayonet charges, custom setup/deployment and native battle reports. The six-battle Commonwealth campaign now runs natively in C#. Existing Python presentation/results/campaign UI, tactical camera and
recording replay are preserved. Earlier milestone sections below are historical records.

## Army director and cavalry accompaniment

The native AI now adds a five-second army plan, persistent regimental roles,
reactive infantry reserves, cavalry accompaniment/recovery stations and early
firing-formation preparation. Player authority and authored approaches remain
binding. Combat calculations and unit statistics are unchanged. The exact previous
AI was frozen before implementation for mixed-controller testing. See
[architecture, measurements and limitations](godot/ARMY_DIRECTOR.md). This supersedes
the earlier pass's fixed reserve timer and enemy-relative mounted approach.

## Tactical decision improvements

Native AI now retains shared attack/defend/support/reserve assignments, derives
purpose from campaign objectives, assesses nearby visible supporting forces, and
selects infantry firing positions using existing terrain and firing-lane geometry.
Player authority, authored approaches and mandatory morale behaviour retain priority.
Three new live/headless laboratories demonstrate the changes. Combat calculations
and Python gameplay code remain unchanged. See [rules, configuration, validation and
performance](godot/TACTICAL_DECISIONS.md).

The subsequent [matched AI evaluation](docs/AI_TACTICAL_EVALUATION.md) found no
overall win-rate advantage (56 new wins, 55 old, 9 unresolved in 120 games). Lane
clearing improves markedly, but line/woodland regressions implicate firing-position
and formation-timing interactions. These findings are documented; no evaluation-time
gameplay tuning has been applied.

## The Defence of the Commonwealth — Part 2

Native campaign progression now connects six stages (seven authored encounter
variants in one data document) to the existing live viewer and results screen.
Persistent regiment/commander records, three stored reward offers, all twelve
existing acquired abilities, alliance/political events, a rescue/interception
branch, replenishment, three endings and atomic version-1 between-battle saves
are implemented in the standalone assembly. Main-menu New/Continue Campaign,
roster/assignment/briefing/choice screens and campaign deployment reuse the current
battle presentation. The after-battle report is extended rather than replaced.

An optional MissionSystem supplies defeat/capture/hold/delay/rescue/convoy goals,
mission-owned outcomes, scripted approaches and safe timed/conditional reserve
activation. Existing custom/replay scenarios do not acquire this layer. Transport
wagons are unarmed instances of the existing mobility/formation model with simple
batched meshes. Enemy crossings and optional friendly guard slots are authored
scenario guidance; no general tactical-AI or crossing-planner rewrite occurred.

[Architecture, exact rules, authoring, save boundaries, tests, actual six-stage
runs, performance and limitations](docs/COMMONWEALTH_CAMPAIGN.md) document the
first playable campaign. The initial [audit](godot/CAMPAIGN_AUDIT.md) records reuse
of Python persistence ideas and existing native commander abilities. Earlier
Stage 1/milestone scope statements below remain historical implementation records.

## Campaign battlefield environment

Native scenario data now optionally contains versioned `terrain.environment`:
polyline rivers, oriented bridge/ford surfaces, road/track strips, directional
pre-placed earthworks/barricades, and fixed Clear/Rain/Fog definitions. The C# core
owns passability, full-footprint swept guards, crossing routes/traffic, movement,
cover, charge restrictions and weather/visibility. Godot receives canonical water
polygons and terrain samples, retains static meshes, and uses authoritative enemy
observation for fog in both views. Python simulation code is unchanged.

A distance-only crossing graph, timed columns/compact transit, deterministic
friendly passage queues and bank escape fallback provide basic navigation. They
do not plan attacks, bridgeheads or fortification occupation. Manual crossing
preferences are supported. Physical projectiles can clear rivers, terminate on
water and still strike troops behind defensive works; the works have no projectile
colliders. No construction/destruction, dynamic weather or campaign objectives
have been introduced.

Eight environmental laboratories, a custom Vistula-style deployment preset,
JSON-authoring helpers and twenty 12/24/36/60-regiment workloads are included.
Missing environmental data defaults to legacy Clear paths; existing formula/RNG
reference tests and matched pre-change final state comparisons are preserved.
There are 551 native tests, 674 unchanged Python tests, and 537 Godot assertions
across 14 scripts, including 28 new environmental integration checks.

[Full representation, numerical parameters, authoring/launch commands, measured
performance, compatibility and remaining risks](godot/ENVIRONMENT.md) are recorded
with the [architecture audit](godot/ENVIRONMENT_AUDIT.md). Future campaign work can
use this terrain without assuming a sophisticated crossing planner already exists.

## The Defence of the Commonwealth — Stage 1

The supplied Design Reference v0.1 has been read and its Sections 5/8 implemented
as a native content pass: **15 core units** (four preserved specialist IDs and
11 new profiles), **14 historical definitions**, separate Kościuszko/Suvorov army
assignments, faction-independent coalitions, conditional starting signatures,
melee-only assault infantry and physical canister. The original nine profiles keep
their numeric balance; generic and French units remain in the sandbox.

The existing custom unit picker now combines faction and category filters. The AI
setup dialog assigns compatible unique historical officers and army leaders before
tick 1; ordinary version-1 recipes preserve the new optional identity fields. There
are 54 controlled live/headless laboratories and four custom deployment presets.
The standalone engine remains independent of Godot. Army command uses bounded
fixed headquarters and spatial queries; mixed-faction coordination uses strongest
sources, not stacking global auras. Explicit player orders remain authoritative.

[Complete roster, commander effects, compatibility, evaluation results and limits](docs/COMMONWEALTH_STAGE1.md)
include the Stage 2 dependencies. **Campaign missions, progression, recruitment,
fortification construction and the other 16 proposed units are not implemented.**
The earlier architecture [audit](godot/COMMONWEALTH_STAGE1_AUDIT.md) retains its
pre-change performance baseline. Python gameplay is unchanged; reference tests now
explicitly distinguish its nine profiles from additional native-only content.

## Melee stability and shared battlefield views

Existing native melee engagements now use a 4 m footprint disengagement margin,
while initial contact still uses .75 m. The stable engagement set and per-pair
pulse timers are retained through small gaps. Broad-phase padding includes this
margin; no new all-to-all search was added. Charge impacts remain contact-only;
fleeing units and explicit disengagement are not halted, and cavalry can transition
out of retained melee into moving pursuit. `MeleeDisengageDistance` is configurable
in standalone rules/scenarios. The unchanged Python trace oracles select .75 m
explicitly; seven new native tests cover the intended behavioral difference.

The 2D HUD button no longer changes to a default-recording scene. Instead,
`scripts/battlefield_2d.gd` reuses the original 2D terrain and regiment renderer in
the existing SubViewport. The parent controller keeps the sole live/replay clock,
backend, immutable frames, selected regiment and command interface. Switching back
to 3D retains all battle state and each view's camera. 2D supports selection,
manual oriented movement, formations, deployment, playback/seeking, focus/follow
and camera controls. Static 2D terrain is built lazily and cached. 3D rendering is
disabled while in 2D; simulation advancement remains exclusively in the controller.

**482 xUnit tests and 672 pytest tests pass.** Existing Godot regression scripts
pass, plus 22 new shared-view assertions (also checked in an actual GTX 1080
window). No Python gameplay or recording format changed.

## Tactical controls and roster picker

Custom setup now lists only chosen archetypes. **+ Add units…** opens a filtered,
searchable catalogue with statistics, abilities, amount selection and limit checks,
matching the old Python workflow. Right-button press/drag/release fixes a destination
and previews/assigns arrival facing in live movement and deployment. Ghost figures,
terrain-following footprint and heading arrow are read-only; invalid deployments
are red, and cancellation does not issue orders. The adapter passes optional facing
to the existing C# Order/arrival-turn rules, without changing movement algorithms.
A cached selected-weapon ring/forward arc is visible in live/replay (metadata supplies
legacy ranges). It indicates nominal geometry rather than authoritative visibility.
The camera's lower pitch limit is now zero, with a near-horizon lifted look point
so clearance and a genuinely level view coexist. Existing dolly/overhead/follow
controls and UI ownership remain intact. See [SANDBOX.md](godot/SANDBOX.md).

## Native sandbox completion — campaign excluded

[The sandbox implementation and controls](godot/SANDBOX.md) document this stage.
Standalone `Setup/BattleConfiguration.cs` reads/writes Python version-1 battle
recipes, validates roster/placement/commander compatibility, packs automatic
formations, and applies deployment edits transactionally. All twelve Python custom
presets are embedded. `Setup/PythonTerrainRandom.cs` reproduces CPython integer-seed
MT19937 only for map generation; core combat/commander streams are unchanged.

`Combat/InfantryChargeSystem.cs` ports the original bayonet rush, actual acceleration
and momentum, one impact, terrain/facing/morale effects, and clear/reform/cooldown
locks. Ordinary melee handles the aftermath. Infantry Firebrand is now active and
eligible. `Commanders/UpgradeSystem.cs` integrates all twelve acquired abilities
into the existing movement, fire, morale, charge, pursuit and deployment rules.
They are selected in sandbox setup, owned/serialized by the immutable commander,
limited to three compatible unique abilities, and keep transient timers in the
battle regiment. No campaign/reward transaction was added.

Godot now starts at `scenes/main_menu.tscn`. The existing 3D viewer/HUD gains the
recipe editor, terrain-aligned deployment boundaries, placement/facing/formation
controls, commander ability checkboxes, and frozen results. The report exposes army,
regiment and archetype statistics, filters/sorting/pagination, JSON export, restart,
new seed and return to setup/menu. `Analysis/BattleReport.cs` works headlessly too;
runner options `--battle-config` and `--report` expose both paths without Godot.

Direct references cover 45 current-Python upgrade/impact calculations and 30 terrain
preset/seed combinations, including negative and extreme signed 64-bit seeds. All
legacy custom presets prepare natively, and an actual native-saved recipe with
abilities was loaded by the unchanged Python `BattleConfig` validator. Full
cross-language battle identity is still not claimed. Optional native placement
nation/autonomy fields survive native recipes but are ignored on Python import.

A seed-17 upgraded combined-arms scenario finished at **319.5 simulated seconds**:
205 ranged salvos, 111 physical artillery rounds, four impacts, nine routs, five
rallies and 851 casualties, including two friendly-fire incidents. This is a
functional integration observation, not a controlled claim about upgrade win rates.

Release headless AI workloads, two runs each, 100 warm-up + 600 measured ticks:

| Regiments | Mean tick ms | p95 tick ms |
|---:|---:|---:|
| 12 | .409 | .620 |
| 24 | .835 | 1.178 |
| 36 | 1.351 | 1.906 |
| 60 | 2.388 | 3.330 |

Checksums match between repeats. Additional ability-equipped workloads measured
.409/.730/1.049/1.951 ms mean and .641/1.177/1.564/2.596 ms p95 for 12/24/36/60.
Those have different officers/outcomes and are not a speedup comparison. Raw data:
`benchmark-results/sandbox-headless.json`, `sandbox-upgrades/`, and
`sandbox-upgraded-report.json`. Current costs are close to the historical M5
baseline; no general Python/C# speed claim is made.

Final validation: **475 standalone xUnit tests** and **672 pytest tests** pass.
Godot checks pass for main menu (6), custom sandbox (41), AI/commanders (21),
artillery/specialists (40), morale/cavalry (36), combat (39), live movement (39),
3D viewer (74), camera (58), and replay (60). The .NET solution builds with zero
warnings/errors; the headless .NET editor imports and exits cleanly. Setup,
deployment and results were also exercised in actual GTX 1080 windows, with
screenshots at 1280×800 and 800×600 inspected for layout.

GPU samples at 4× speed: the 12-regiment upgraded scenario averaged **2.57 ms/frame**
(p95 4.66 ms). A 60-regiment battle at an 800 m camera span, 32 visual slots per
regiment and shadows enabled averaged **15.94 ms/frame (~63 FPS)**, p95 26.77 ms,
with 1,431 figures by the measured end. Overview LOD separately measured 11.74 ms
mean, p95 20.92 ms. These are whole presentation frames including due simulation
ticks, not isolated GPU timestamps or worst-case guarantees. Both 400-frame
samples retained less than one authoritative tick of accumulator time. Raw data:
`benchmark-results/sandbox-gpu*.json`.

Remaining scope: campaign/recruitment/rewards/replenishment and campaign save
migration. No campaign code or Python gameplay was changed. Detailed usage,
parameters, compatibility caveats and validation commands are in SANDBOX.md.

## Milestone 5 — autonomous armies and named commanders

The standalone C# engine now runs player-versus-AI and fully autonomous combined
arms, with five commander personalities and eight starting specializations. The
source audit, formulas, authority rules, controls and differences are in
[AI_COMMANDERS.md](godot/AI_COMMANDERS.md). Python gameplay is unchanged, and all
previous replay/movement/terrain/combat/morale/cavalry/artillery fixtures remain.

`AI/TacticalAi.cs` owns four army objectives, deterministic scheduled regiment
plans, target persistence, preparation/disengagement, cavalry flanking/charge
choices, bounded pursuit, skirmish harassment/withdrawal/cover selection, and local
battery relocation. Initial plans are simultaneous; subsequent work is staggered
by stable IDs across a configurable 50-tick window. Movement/fire/contact/pursuit
remain fixed-tick routines. Target death/escape/new rout can prompt immediate
reevaluation. Protected charge/recoil/pursuit states are not continually replaced.
Manual orders and formations stay pinned; release Autonomy explicitly to let AI
resume. Invalid explicit attack/charge/pursuit orders release when appropriate.

`Commanders/CommanderSystem.cs` loads curated names, policies, eligibility and
numeric tuning from shared JSON. Immutable commander identity is independent of
archetype and mutable decision timers. Supplied officers/IDs validate and persist;
a separate commander seed defaults 1729, independent of combat randomness. Reset
retains setup/rerolls. No acquired upgrades/experience/campaign features are active. Infantry Firebrand is
excluded from ordinary generation/setup until its bayonet-impact dependency is
ported; imported officers retain it with an explicit inactive-effect warning.
Names preserve the original fictional European pools and whole user-provided
Haudenosaunee names, with optional nation metadata and no invented syllables/ranks.
Cross-faction assignment is allowed; category compatibility is enforced.

The five personalities use common policy functions: Aggressive commits/advances
more readily and pursues farther; Cautious disengages earlier; Methodical briefly
reforms at low cohesion; Opportunistic locks onto significantly better vulnerable
or exposed targets; Stalwart holds defensive positions longer. The original small
methodical-turn/stalwart-shock hooks also remain. Drillmaster, Firebrand,
Pathfinder, Sharpshooter, Artillerist, Inspirer, Pursuit Specialist and Defensive
Tactician modify existing movement/reload/terrain/morale/impact/pursuit calculations,
including their limitations. Existing archetype caps and strongest-aura-only rules
prevent duplicate/unbounded stacking.

Godot Live defaults to **Player versus AI**; choosing it through the mode selector
opens paused for setup. The **AI** button selects army objectives, edits/rerolls
the selected commander before tick1, and releases a selected Blue regiment to
Autonomous/Hold. Enemy regiments are inspectable, while manual commands remain
Blue-only. `ai-combined` is AI-versus-AI. The inspector shows the named officer,
personality, specialization, actual last decision, ownership, countdown, measured
threat ratio/target score and conditional effects. Existing renderer, camera,
selection, interpolation, effects and replay path are reused.

### Fidelity and intentional refinements

The current Python `ai.py`, `commander_ai.py` and `commanders.py` supplied the
actual policies, traits, name pools, reserve rules, flank approach, local battery
search, bounded retreat/re-engagement and player authority. Exact order-by-order
full-battle identity is not claimed: C# scheduling is staggered, name generation
uses a separate specified stream, and limited tactical safeguards are added.
Prepared frontal targets no longer force an autonomous cavalry charge solely
because commitment time expired. Formation choice has20 s hysteresis/manual pins;
light troops may commit to nearby cover. Artillery filters nominal low shots
through allies and avoids friendly candidate footprints; physical friendly fire
is still authoritative. Without detected enemies, attackers search last contact
or the army centre rather than using hidden enemy poses. Close infantry assaults
use ordinary melee, not the still-deferred Python bayonet-impact mechanic.

### Validation and behavioural observations

**397 xUnit tests pass**, including all retained gameplay references and 111
current-Python controlled probes: commander factors/policies/preparation, effective
engagement ranges, skirmish decisions, four army doctrines and multi-target
opportunity selection/locks. Numeric tolerance is 1e-5. Pure mechanical comparisons
supply officers explicitly; generator streams are deliberately independent, and
full cross-language AI replay identity is not claimed. Native decision tests cover
player priority/manual formation pins, target persistence/cleanup, prepared-front
avoidance, personality-dependent cavalry patience, bounded pursuit/skirmishing,
artillery relocation→deployment→actual firing, risk filtering and all starting
specializations. Generated IDs/names are compatible, stable and unique; generation
remains bounded even with a repeating test stream. Repeated native snapshots,
events and RNG outcomes are exact on this host.

**670 Python tests pass** (76.58 s); current oracle/schema checks also pass after
fixture regeneration. Native checks pass: **21 AI/commander**,40 artillery,
36 morale/cavalry,39 combat,39 movement,58 camera,74 3D viewer,60 replay. AI checks
also pass in an actual GPU window, covering setup/reroll/assignment, reset identity,
combat-RNG isolation, locked in-battle editing, player Hold, autonomy release,
physical artillery and replay switching. .NET/Godot builds have zero warnings/errors;
the headless editor loads/exits cleanly. No camera algorithms or Python gameplay
were changed. A small recursive vector diagnostic formatter was fixed without
changing vector arithmetic.

Twelve complete battles use combat seeds 17/31/73 with fixed commander seed 1729,
both original and mirrored/swapped deployments. **All finish by morale victory;
zero timeouts and zero regiments with neither shots nor inflicted casualties.**
Terrain stays fixed during swaps, intentionally exposing map-side advantages.

| Scenario | Seed | Normal winner/time | Swapped winner/time | Normal/swapped rounds | Normal/swapped charges |
|---|---:|---|---|---:|---:|
| ai-infantry | 17 | army_1 / 421.9 s | army_0 / 421.9 s | 0/0 | 0/0 |
| ai-infantry | 31 | army_1 / 474.2 s | army_0 / 474.2 s | 0/0 | 0/0 |
| ai-infantry | 73 | army_0 / 385.0 s | army_1 / 385.0 s | 0/0 | 0/0 |
| ai-combined | 17 | army_0 / 686.0 s | army_0 / 522.6 s | 132/192 | 7/3 |
| ai-combined | 31 | army_0 / 622.3 s | army_0 / 525.4 s | 209/199 | 3/2 |
| ai-combined | 73 | army_1 / 622.8 s | army_0 / 439.8 s | 199/178 | 3/3 |

Times are **simulated seconds**, not benchmark wall time. Small samples and fixed
commander assignments do not establish balanced win rates; infantry outcomes mostly
follow the roster after swapping, while the asymmetric combined-arms map shows
side/deployment effects. Raw results include participation, moving/firing-pulse
seconds, volleys, charge successes, routs/rallies, target/formation changes, final
strength and draw counts: `benchmark-results/m5-battles.json`.

A controlled 120 s observation gives all officers Pathfinder, changes only Blue
personality, and fixes Red Methodical. This is a bounded behavioural observation,
**not a completed-battle/victory trial** (`timedOut` remains true if inconclusive):

| Blue personality | Blue moving regiment-seconds | Blue firing-pulse seconds | Total target changes | Total charges |
|---|---:|---:|---:|---:|
| aggressive | 239.0 | 3.6 | 27 | 2 |
| cautious | 150.8 | 4.1 | 27 | 2 |
| methodical | 195.2 | 4.0 | 31 | 2 |
| opportunistic | 277.8 | 3.8 | 34 | 2 |
| stalwart | 168.7 | 4.1 | 27 | 2 |

Controlled decisions also demonstrate Cautious retreat at overmatch 1.15 versus
Aggressive 2.4, bounded Methodical reform below 55 cohesion, Opportunistic weak-target
preference with a 10 s lock, Stalwart longer disengagement tolerance, and earlier
Aggressive than Cautious cavalry commitment. These are behavioural differences,
not scenario-specific hardcoded bonuses. Raw observations: `m5-personalities.json`.


### Performance

Linux/Ryzen 5 7600X3D, .NET SDK 10.0.403/runtime 10.0.14; C# **Release**, no profiler.
Same autonomous combined-arms JSON/seed 17/commander seed 1729; 100 warm-up and 600
measured fixed ticks (**60 simulated seconds**), three sequential repeats. Results
are averages of per-run statistics. Planning counters/time include all 700 ticks,
including warm-up/JIT, and measure scheduled planner work only, not all tick-level
execution. Timing samples have no competing tests, renderers or other benchmarks.

| Regiments | Mean/median/p95 tick ms | Ticks/wall s | Wall s for 60 simulated s | Planning ms/tick* | Decisions/target evaluations | Managed bytes/tick |
|---|---:|---:|---:|---:|---:|---:|
| 12 | 0.406/0.365/0.641 | 2,464 | 0.244 | 0.030 | 173/297 | 115,599 |
| 24 | 0.829/0.743/1.148 | 1,206 | 0.498 | 0.047 | 355/731 | 244,087 |
| 36 | 1.310/1.265/1.761 | 763 | 0.786 | 0.077 | 533/1,202 | 365,254 |
| 60 | 2.301/2.332/3.151 | 434 | 1.381 | 0.152 | 890/2,603 | 630,767 |

*Planning average covers all 700 ticks, unlike the 600-tick runtime window. At 60,
186,216 visibility requests produce 41,549 actual rays;
the workload fires 136 rounds/180 volleys, starts 10 charges
and produces 9 routs. This is an autonomous workload, not an apples-to-apples
comparison with static M4 armies or the complete Python application.

Profiling identified unnecessary far-enemy perception in scheduled plans. Nearest
roles now stop at the first visible candidate; persistent targets are checked in
priority order; scored searches use conservative distance-score lower bounds.
No approximate visibility, delayed damage or changed decision cadence is involved.
The 60-unit target evaluations fall **24,898→2,603**;
planning average **1.283→0.152 ms/tick**, mean tick
**2.500→2.301 ms**, p95 **4.979→3.151 ms**.
All four stress sizes/three repeats retain the exact pre-optimization state checksum;
all twelve complete battles retain result, time, strength and random-draw counts.
Raw before/after: `m5-unpruned-headless.json`, `m5-headless.json/.csv`,
`m5-battles-before-pruning.json` and `m5-battles.json` under `benchmark-results/`.

A separate allocation diagnostic pass (excluded from timing) reports approximately
191 KB/tick intent/planning, 87 KB/tick movement, 222 KB/tick contact/fire/events, 163 KB/tick morale. These cover all 700 ticks and omit small outside-phase costs;
state checksum/RNG matches the uninstrumented run. Spatial-query collections,
ordered candidate temporaries and event/frame objects remain allocation candidates.
Raw diagnostic: `benchmark-results/m5-allocations.json`.

The same frozen M4 60-regiment combined-arms workload was rebuilt from the source
checkpoint and measured in three interleaved before/after repeats. Mean
**1.642→1.568 ms**, p95 **2.319→2.253 ms**;
managed bytes/tick **532,494→529,316**.
Final states/draws match. The small timing difference does not establish a general
engine speedup; existing gains are retained. Raw: `m5-legacy-guard.json`.

Actual GPU: GTX 1080/NVIDIA 580.196.07, Godot 4.7.2.NET, **Debug** game assembly,
1280×800, 962×544 battlefield, perspective span 800 m, shadows/2×MSAA,
32 maximum figures/regiment. Autonomous fixtures pre-roll 140 ticks, then run 4×;
60 warm-up/600 uncapped measured frames. These combine simulation/bridge/presentation
work and are not isolated GPU timings. End simulated times differ per sample;
distant/offscreen figures may be culled. Terrain builds once (45k–192k vertices).

| Regiments | Mean/median/p95 frame ms | Average FPS | Combined CPU mean ms | End simulated time |
|---|---:|---:|---:|---:|
| 12 | 3.18/2.75/5.69 | 315 | 2.34 | 22.4 s |
| 24 | 5.37/4.24/9.81 | 186 | 4.45 | 28.3 s |
| 36 | 8.53/6.33/14.90 | 117 | 7.38 | 36.9 s |
| 60 | 16.58/16.63/25.89 | 60 | 15.28 | 59.8 s |

At normal 1×, the 60-regiment sample averages **82 FPS**, mean/p95
**12.15/23.03 ms**. The 4× case averages about 60 FPS,
but its 25.89 ms p95 is not a locked 60-FPS guarantee. Every sample ends with
accumulator remainder<.1 s; peak debt was not recorded. Snapshot conversion,
terrain-following figures and event presentation still contribute frame spikes.
One GPU sample per configuration, not a worst-case/close-up/dense-forest guarantee.
Raw: `benchmark-results/m5-gpu/`.


### Remaining limits / next milestone

The planner remains local and imperfect. Eight-position artillery searches can
fail around broad terrain barriers; nominal shot safety cannot predict scatter
or bounces; target persistence can retain a costly engagement; rectangle steering
has no global pathfinding. Army objectives are four modest doctrines, not a
synchronized strategic planner. Asymmetric terrain, fixed commander assignments
and stable update/RNG order can produce side advantages. Continue side-swapped
experiments before drawing broad balance conclusions. Windows/packaged exports
remain untested. No new campaign/results screen was built.

Next: use the new telemetry to refine these tactical weaknesses, then port
**acquired commander upgrades and persistent campaign armies** from Python. The
baseline identities/modifier seams support that work without implementing it now.

## Milestone 4 — physical artillery and six specialist archetypes

The audit/port contract is [ARTILLERY_SPECIALISTS.md](godot/ARTILLERY_SPECIALISTS.md).
Python gameplay and replay files are unchanged. The pure C# core adds
`ArtillerySystem` and projectile/snapshot records, and a small `SpecialistSystem`;
no Godot dependencies, per-soldier physics or parallel combat engine were added.
The existing shared archetype JSON now contains all nine Python IDs, with six
specialists alongside generic infantry/cavalry/artillery. Explicit scenario flags
preserve old movement/M2/M3 reference workloads. Normal live combat enables all.

### Artillery and numerical fidelity

Operational guns = ceil(guns×current crew/original crew), capped at six field/four
horse guns. The existing movement timers control 3/8 s field and 1/3 s horse
limber/setup; initially stationary batteries start deployed, as in Python. Reload
is 19/17 s with fatigue. Moving/limbered/deploying batteries cannot fire. Assigned
shots ignore terrain LOS but still obey range/arc; automatic acquisition needs
own/friendly perception. Hold-fire retains the target and reload progress.

Physical round shot uses 100 m/s muzzle speed, gravity 9.81, muzzle+1.2 m,
independent ±45 m horizontal scatter (bounded near muzzle, increased in cover)
and ±3 m/s elevation error. No canister/ammunition inventories/calibres exist in
Python and none are invented. Nonempty terrain uses ≤2 m/≤.025 s adaptive
substeps and 16-iteration surface clipping; swept OBB intersections reject shots
above troops+3 m. Impacts are ordered by entry then ID, including friendlies.
Damage/shock and penetrating energy retention use the same shared morale system.
Ground normals reflect/damp velocity; energy retains .72 on bounce and .75 per
regiment; forest drag, five-bounce/energy/lifetime/field-margin limits are preserved.
The source's one-hit-per-regiment-per-projectile lifetime bookkeeping is retained.
No unconditional enfilade/rank bonus was added: orientation determines actual
path intersection. Projectiles clear on battle completion/reset.

A 1-ulp norm discrepancy initially changed an integer substep boundary during a
60-regiment ricochet. A **ballistics-only compensated norm** now matches Python's
`math.hypot`; 1,000 exact norm/substep golden cases and all stress results cover
this. General movement vector arithmetic remains unchanged. This preserves the
source's clipped-step behaviour rather than introducing arbitrary rounding or a
new trajectory model.

### Specialist mechanics

- Prussian: cohesion-scaled reload (up to25% faster), formation changes (40%),
  turning disruption (50%), and coordinated accuracy; weaker bonuses in disorder.
- Haudenosaunee: existing loose formation/forest mobility/concealment, woodland
  firing/aim modifiers and cover-scaled ambush melee; weak open melee remains.
- Royal Grenadiers: morale 96/discipline 1.2/melee 1.5; visible steady support within
  125 m adds .22 morale/s (.35 rallying), strongest source only; rout shock×.85.
- Uhlans: speed 9, charge speed×1.05, pursuit×1.25, sustained melee×.7; impact×1.65
  only against unprepared broken/disordered targets while moving above 3 m/s.
- British Rifles: range 235/accuracy 1.65/reload 22; up to35% aimed bonus only while
  stationary, sufficiently cohesive and with a clear enough firing lane.
- Horse Artillery: speed 3.8, 1/3 s limber/setup, four lighter-energy guns using
  exactly the same projectile engine as field artillery.

The existing battlefield renderer receives typed projectile snapshots and emits
pooled/batched cannonball/smoke/impact feedback from authoritative events. Existing
specialist visual profiles supply uniforms, lances, headwear and mobile batteries.
The inspector shows actual guns, reload/setup, hold-fire, traits, drill/aim factors.
**Y/I** hold/resume fire, **O** manual loose skirmish stance, **F8** optional
trajectory-tangent/range/arc/aura/energy debug; all previous orders/camera controls
are preserved. Skirmish stance intentionally leaves autonomous standoff/retreat
planning to the AI milestone; manual Move/Attack/Disengage work now.

### Validation

**261 xUnit tests pass**, including all retained regressions, direct mechanics,
five complete 20-second current-Python battle traces, five swept/ballistic/terrain
physics traces, nine specialist probes, 1,000 exact norm/substep cases and eight
700-tick stress reference cases. The whole-battle traces check positions/facing,
strength/morale/cohesion/reload, active projectile physics and draw consumption;
normal tolerance is 1e-5. The oracle calls actual Python functions with neutral
commanders, no army planner, and a shared specified SplitMix64 test stream.
Python's normal MT19937 gameplay RNG is unchanged, so ordinary equal game seeds
alone do not imply replay equivalence across languages.

**668 Python tests pass** in 69.66 s. Native checks pass: **40 artillery/specialist**,
36 morale/cavalry,39 infantry combat,39 movement,58 camera,74 3D viewer,60 replay.
The new checks pass headlessly and in an actual GPU window, including physical
fire, projectile identities, hit/bounce events, cease/resume, specialists, reset
and the 800×600 control strip. Godot .NET build has zero warnings/errors and the
headless editor loads/exits cleanly. `/tmp/rtt-m4-combined.png` captures the live
combined-arms scene. No Pygame results/campaign UI was changed.

### Measured performance (Milestone 4)

Ryzen 5 7600X3D/Linux, Python 3.14.8, .NET SDK 10.0.403/runtime 10.0.14.
C# **Release**, profiling disabled; same scenario JSON/seed 17, actual supported
Python battle loop, neutral commanders/no army planner, 100 warm-up plus 600
measured ticks (**60 simulated seconds**), three sequential repeats. Statistics
are means of per-run statistics, not pooled percentiles. The Python loop retains
its existing analysis bookkeeping and global projectile candidate scan; the C#
port uses the existing spatial broad phase. This is a supported combined-arms
slice comparison, not a claim about the entire future engine or full Python AI.

| Workload | Regiments | Python mean/p95 ms | C# mean/p95 ms | C# ticks/wall s | Wall s for 60 simulated s | Managed bytes/tick | Peak balls | Collision candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| artillery | 12 | 1.811/3.557 | 0.307/0.392 | 3,255 | 0.184 | 95,648 | 24 | 5,942 |
| artillery | 24 | 5.820/12.453 | 0.660/0.881 | 1,514 | 0.397 | 212,108 | 54 | 27,550 |
| artillery | 36 | 12.061/28.073 | 1.164/1.573 | 861 | 0.699 | 335,093 | 79 | 42,030 |
| artillery | 60 | 30.239/71.597 | 1.658/2.871 | 604 | 0.995 | 555,970 | 142 | 92,718 |
| combined | 12 | 1.263/1.962 | 0.310/0.489 | 3,217 | 0.187 | 96,907 | 8 | 4,732 |
| combined | 24 | 3.671/6.269 | 0.700/0.914 | 1,427 | 0.420 | 218,235 | 16 | 16,072 |
| combined | 36 | 6.507/12.100 | 1.041/1.291 | 960 | 0.625 | 292,386 | 24 | 23,642 |
| combined | 60 | 15.688/30.402 | 1.614/2.426 | 620 | 0.969 | 532,056 | 40 | 44,707 |

All eight workloads match Python's final regiment positions/strength/morale/
cohesion/state/escape status and RNG draws in all three repeats; maximum final
numeric difference is **0 on this host**. This does not imply cross-platform
bitwise equivalence for arbitrary trajectories. Activity/collision/peak counts
include warm-up; timed statistics exclude it. The 60 artillery-heavy case fires
564 balls, records 252 regiment hits/2,775 bounces/28 friendly-fire incidents and
11 routs. Combined 60 fires 200 balls, with 107 hits/11 friendly hits/10 routs.
Five times as many regiments costs about 5.4× headless tick time in these layouts.
Global targeting and repeated spatial/terrain query allocations remain worthwhile
optimization candidates; roughly 0.53–0.56 MB managed allocation per60-unit tick
is measurable. No precision/timestep reduction or delayed collision was used.
Raw JSON/CSV and all repeats: `benchmark-results/m4-headless.*`.

The same frozen M3 60-regiment workload was rebuilt from the pre-edit source
checkpoint and compared in three interleaved repeats: mean **1.636→1.738 ms**,
p95 **1.966→2.055 ms**, managed bytes/tick
**417,621→442,825**. The mean difference is
**+6.2%**; final states/draws remain identical. The new opacity-aware
visibility cache and integration add some overhead; this is a measured regression,
not a claim that new mechanics are free. Raw guard: `benchmark-results/m4-legacy-guard.json`.

Actual GPU: GTX 1080/NVIDIA 580.196.07, Godot 4.7.2.NET, **Debug** game assembly,
1280×800, battlefield962×544, perspective span 800 m, shadows/2×MSAA,
32 maximum figures per regiment. Combined-arms fixtures pre-roll 140 real ticks,
then run **4×**, with 60 warm-up/600 measured uncapped frames. These are combined
simulation/presentation wall frames, not GPU-only timestamps. End battle times
vary with frame throughput; distant/offscreen objects may be culled. Different
map heights contain 45k–192k cached terrain vertices and 33 trees.

| Regiments | Mean/median/p95 frame ms | Average FPS | Live CPU mean ms* | Active/peak balls at end |
|---|---:|---:|---:|---:|
| 12 | 2.85/2.44/4.80 | 350 | 1.97 | 8/8 |
| 24 | 5.40/4.08/10.10 | 185 | 4.35 | 0/16 |
| 36 | 8.06/5.60/15.02 | 124 | 6.79 | 24/24 |
| 60 | 15.91/15.65/25.49 | 63 | 14.41 | 40/40 |

*Includes due simulation ticks, typed frame conversion, interpolation/camera,
terrain-following decorative figures, events/effects and markers. At normal **1×**,
the 60-unit sample averages **106 FPS**, mean/p95
**9.45/17.43 ms**, with40 active balls at the end.
Each sample ends with accumulator remainder<.1 s; peak debt was not recorded.
The 4× 60-unit p95 exceeds 16.7 ms, so this is not a locked 60-FPS promise.
One GPU sample per configuration; large dense forests/close-ups/packaged exports
need further profiling. Terrain is constructed once on load, not per frame.
Raw reports: `benchmark-results/m4-gpu/`.


### Limitations and next milestone

This is the Python arcade round-shot model, not a new rigid-body solver. Flat
fields keep their original one-piece update; nonempty terrain substeps adapt to
feature size. Terrain-contact clipping discards the remaining part of that tiny
substep, as the reference does. Lifetime hit IDs disallow re-entry damage. No
canister, per-rank damage, calibre logistics or new aiming wind-up is claimed.
Local rectangle steering can still be cornered, and deliberate frontal cavalry
attacks remain costly. Windows/packaged exports remain untested.

No full tactical/army AI, commander effects/upgrades or campaign has been ported.
The next milestone should restore **tactical AI**, especially skirmisher standoff,
artillery positioning/target safety and combined-arms decisions, using the same
headless fixtures. Commander mechanics and campaign can follow after that.


## Milestone 3 — morale, routing, rallying and cavalry

The pre-port audit/formulas and dependencies are in [MORALE_CAVALRY.md](godot/MORALE_CAVALRY.md). The checkpoint is `/tmp/rtt-before-milestone3.tar.gz`; baseline 102 xUnit tests passed, with matching M2 timings saved as `benchmark-results/m3-combat-before.*`. Python game code, the recording format and the tactical camera controller were not changed.

**Implemented:** independent morale and cohesion; steady/shaken/wavering/routing/rallying states with hysteresis; casualty/melee/impact morale loss and bounded recovery; event-driven visible rout shocks; deterministic threat-aware escape/edge withdrawal with living survivors; gradual safe rallying and restored authority; cavalry approach/acceleration/momentum, one-time impact, prepared-front resistance, flank advantage, recoil/reform, shared sustained melee and moving pursuit; 18% fighting-strength defeat with a 12 s grace/reset timer. Existing soft collisions, pursuit-compatible congestion, stable lanes, geometry caches and exact terrain/LOS remain authoritative.

Three small pure-.NET systems (`MoraleSystem`, `RoutingSystem`, `CavalrySystem`) extend the existing core. State is in Regiment; immutable `RegimentDynamics` snapshots cross the existing typed in-memory Godot bridge. The native HUD, formations, effects, camera and selection are reused. Live enables M3; legacy fixture flags preserve all M1/M2 reference workloads. Spatial indexes used by targeting are refreshed after casualties before morale queries, avoiding stale ordinal accesses found by the dense-combat regression tests. No new dependencies or regiment archetypes were added.

**Controls:** right-click enemy/ground for Attack/Move; B charge, U pursue current routing enemy, X disengage, G reform by holding. H/V and formation/pause/speed/reset/camera controls remain. Routing and rallying reject ordinary commands. Normal Live mode defaults to Infantry Under Fire, with nine new demonstrations and all six prior combat templates; the selector reads native definitions. [Launch/test commands](godot/README.md) and [scenario roles](godot/MORALE_CAVALRY.md) describe every ID. Morale warnings, rout disorder, charge/pursuit labels, momentum/speed/cooldown/rally inspection and authoritative event feedback are visible. Both order rows fit 800×600.

### Reference results and regressions

The oracle now invokes **actual Python `Battle.step()`** with neutral commanders, no army AI/projectiles and the same specified SplitMix64 stream. Thirty-eight controlled probes cover damage, thresholds/recovery, escape, fire penalties, charge momentum/impact and broken melee. Ten full sampled traces cover all nine demonstrations and victory grace. Cross-language tests compare state, position/facing, strength/morale/cohesion/fatigue, speed, reload, escape/rally timers, charge lifecycle, counters, RNG consumption and result at 1e-5 tolerance. Maximum observed error across these traces is **3.57×10⁻¹³**, with identical draws/outcomes. Four 700-tick benchmark workloads also match final living/escaped states and key counters at 12/24/36/60 regiments. Repeated C# outputs are exact on this host. Original Python game RNG remains MT19937; equal numeric game seeds are not otherwise a cross-language equivalence claim.

Full Python regression: **665 tests pass** in 68.95 s. **198 xUnit tests pass**, including all 102 retained regressions plus new dynamics/direct/reference/stress checks. Native checks pass: **36 dynamics**, **39 M2 combat**, **39 movement**, **58 camera**, **74 3D viewer**, **60 replay**. Dynamics checks execute in a real GTX 1080 window and headlessly, including commands, cascades, recovery/control restoration, charge failure, moving/shared pursuit, victory/reset and small-window layout. A dedicated three-seed regression also confirms fresh generic cavalry overrun full-strength routing infantry while retaining ≥75% strength. GPU screenshots are `/tmp/rtt-m3-{routing,charge,pursuit,small}.png`. No new after-battle or campaign interface was built.

Portable seed 17 observations: the infantry battle ends via morale collapse at **302.5 simulated seconds**; three nearby formations cascade then can rally in the reserve scenario; prepared front repels cavalry; flank/wavering/routing demonstrations produce 149/161/143 pursuit casualties for 1/1/2 cavalry pursuit losses over 60 s. Shared pursuit advances both riders and inflicts 128 pursuit casualties for 1 return loss. These are controlled demonstrations, not multi-seed win-rate balancing.

### Headless performance

Ryzen 5 7600X3D/Linux, Python 3.14.8, SDK 10.0.403/runtime 10.0.14; C# **Release**, profiling disabled. Same JSON/seed 17; 100 warm-up + 600 measured ticks (**60 simulated seconds**); three sequential repeats, with no competing tests/renderers. Modules contain active fire, new routs, charges, impacts, pursuit and rallying. Python uses the supported actual battle loop (including its existing analysis bookkeeping), with no commanders, army planner or projectiles. This is a matched supported-slice comparison, not a claim about the complete game/future engine.

| Regiments | Python mean / p95 tick ms | C# mean / median / p95 tick ms | C# ticks/wall second | Wall seconds for 60 simulated seconds | Managed bytes/tick |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12 | .856 / 1.110 | .188 / .154 / .261 | 5,320 | .113 | 45,822 |
| 24 | 2.151 / 2.760 | .481 / .449 / .641 | 2,079 | .289 | 155,029 |
| 36 | 3.926 / 4.790 | .815 / .786 / .981 | 1,226 | .490 | 243,671 |
| 60 | 8.272 / 9.987 | 1.481 / 1.410 / 1.770 | 676 | .889 | 417,617 |

The scoped ratio is 4.5–5.6×. Increasing count 5× costs about 7.9× in C#; globally ordered target acquisition and moving LOS still matter. At 60, full-run activity is 13 routs, 11 rallies, 15 charge starts, 14 impacts and 1,309 pursuit casualties for 9 pursuit resistance losses; 77,852 visibility requests become 22,914 actual rays/799,330 samples. Counters include warm-up, unlike the runtime table. Raw JSON/CSV: `benchmark-results/csharp-dynamics.*`.

A separate allocation diagnostic pass (excluded from runtime measurements) attributes 34.5% of the four measured phase totals to intents/routing/targeting, 28.5% to contact/fire/pursuit/events, 18.8% to movement/collision and 18.2% to morale queries/recovery/cleanup. Whole-run per-tick amounts are approximately 148/122/80/78 KB respectively; these include warm-up and omit small outside-phase costs. Spatial/query collections, ordered-target temporaries and event strings are concrete future allocation-reuse candidates. The diagnostic has a state/RNG preservation test. Raw report: `benchmark-results/m3-allocations.json`.

The checkpoint/current **same M2 workload** was rebuilt in Release and measured in three interleaved sequential repeats, all dynamics flags off:

| Regiments | Before mean / p95 ms | After mean / p95 ms | Mean change |
| --- | ---: | ---: | ---: |
| 12 | .191 / .317 | .202 / .323 | +6.0% |
| 24 | .408 / .677 | .412 / .678 | +1.0% |
| 36 | .626 / 1.061 | .636 / 1.063 | +1.6% |
| 60 | 1.134 / 2.021 | 1.099 / 2.258 | −3.1% |

Allocations are essentially unchanged (about 66/121/187/315 KB per tick). These small timing differences do not establish a movement/combat algorithm change. This guard is separate from the new dynamics workload; the two tables must not be subtracted as a performance improvement. Raw guard: `benchmark-results/m3-legacy-guard.json`.

### Godot performance

Actual X11/GTX 1080 driver 580.196.07, Godot 4.7.2 .NET / **Debug** game assembly. Window 1280×800, battlefield 962×544 (second order row visible), perspective span 800 m, shadows, 2× MSAA and 32 maximum figures/regiment. The same dynamics fixtures pre-roll **140 actual ticks**, then run at **4×**; warm 60 frames, measure 600 uncapped wall frames. No competing tests/benchmarks. Each sample therefore covers a different elapsed battle interval; these are active rendering samples, not equal-duration battle comparisons or GPU-only timestamps.

| Regiments | Mean / median / p95 frame ms | FPS (1000/mean) | Viewer CPU mean ms* | End simulated time |
| --- | ---: | ---: | ---: | ---: |
| 12 | 2.29 / 2.10 / 3.55 | 437 | 1.55 | 20.1 s |
| 24 | 4.20 / 3.55 / 6.46 | 238 | 3.29 | 25.2 s |
| 36 | 6.17 / 4.92 / 9.21 | 162 | 5.11 | 30.4 s |
| 60 | 11.09 / 7.83 / 15.14 | 90 | 9.76 | 43.6 s |

*Includes due live ticks, camera/interpolation, terrain-following figures, effects and markers; this combined CPU number is not isolated GPU time. Terrain builds once (67,781–91,357 vertices; 31 trees); source/terrain loading 415–526 ms excludes the explicit pre-roll. Final accumulator remainder is below 0.1 s in every sample; peak debt was not recorded. The 60 case shows 12 new routs, 8 impacts, 7 rallies and 1,120 pursuit casualties by the measured end; active effects do not require per-soldier logic. One sample per count, not worst-case close-up/dense-forest guarantees. Raw reports/logs: `benchmark-results/m3-gpu/`.

### Deliberate limits and next milestone

No tactical army AI, commander/aura/upgrade effects, specialist passives, infantry bayonet charge, campaign or recruitment is ported. Batteries move/flee/defend weakly in crew melee; their ballistics remain disabled. Base static statistics apply, but no new archetype was created. Pursue/Disengage/Reform are explicit aliases using existing attack/move/hold rules; Pursue cannot silently select another fugitive. A small contact safety fix initializes pursuit's target at physical contact even when a narrow ridge hid the centre before movement. Inactive speed/current references are cleared; the Python oracle normalizes inactive speed only. Detailed temporary differences are in [MORALE_CAVALRY.md](godot/MORALE_CAVALRY.md).

Next: **artillery ballistics** with terrain impacts/bounces/penetration/friendly fire and matching fixtures; then tactical army AI and specialist/commander effects. Reuse the current renderer and fixed-tick tests. Local escape steering/rectangle footprints can still be cornered, deliberate frontal cavalry attacks remain costly, and Windows/packaged exports need validation. No new campaign/result-screen architecture is necessary for this port.

## Milestone 2 — terrain, visibility and infantry combat

The audit in [COMBAT.md](godot/COMBAT.md) records current Python formulas and dependencies before the port. Baseline: 578 pytest / 38 xUnit tests and saved movement timings. A pre-edit source checkpoint is `/tmp/rtt-before-milestone2.tar.gz`; this checkout has an empty read-only `.git` stub. No Python simulation/combat, Pygame UI or tactical camera algorithms were changed.

**Implemented:** authoritative analytic hills/forests and their movement/cohesion effects; elevation/vegetation LOS; exact-endpoint visibility cache; firing arcs, friendly screening/frontage sharing, 155 m muskets, fatigue-adjusted reload, range/cohesion/formation/moving/cover accuracy, seeded casualties and cohesion damage; oriented melee contact, 2 s sustained damage, flank/rear/forest/uphill modifiers, disengagement and dead-target cleanup. A bounded sequence/timestamped event stream drives Godot smoke/contact/destruction effects. Current/previous in-memory snapshots carry combat state without a JSON bridge. Live completion freezes the final frame and rejects further orders; Reset restores fresh state.

The existing live scene now defaults to **Infantry Duel**. Its selector offers Ridge Defence, Forest Engagement, Flank Attack, Friendly Firing Obstruction, Combined Movement and Combat, plus both preserved movement sandboxes. Right-click enemy **Attack**, ground **Move**, **H** Hold/fire and **V** Advance/engage; camera/playback/formation controls are preserved. The inspector shows strength, range, reload, target, sight/terrain and last volley. Morale is explicitly inactive, and unsupported cavalry/artillery combat is labelled disabled. See [launch/test/benchmark commands](godot/README.md).

**Reference scope:** 26 current-Python calculation probes; six complete sampled traces, including 90 s ridge/forest engagements and a 70 s moving-under-fire/melee workload; 100 exact golden portable RNG doubles; eleven retained movement fixtures. Controlled casualties, shots, probabilities, reload, cohesion, positions, facing, visibility and draw order are checked at 1e-5 tolerance. Live C# uses specified SplitMix64-v1; an isolated Python oracle uses that stream, while the actual Python game retains MT19937. There is no claim that ordinary Python/C# games with equal numeric seeds match.

All six sampled combat traces have **zero observed numeric difference** on this machine, including positions and draw counts (1,154 / 1,917 / 3,163 / 30 / 858 / 3,555 respectively). Tolerance-aware tests remain necessary across platforms. Final strengths/draw counts also match the full 700-tick workload at 12/24/36/60 regiments. **102 xUnit tests** and **614 pytest tests pass** (full pytest run 63.79 s), covering retained regressions and the new oracle/native checks. The standalone solution builds with zero warnings/errors. Native preserved checks pass: **58 camera**, **74 3D viewer**, **60 replay**, **39 live movement** and **39 combat** assertions. Combat checks run headlessly and in an actual GPU window, including a complete live duel, final-frame casualty display, dead-follow cleanup and restart after completion. The updated .NET editor also loads/exits cleanly using the delayed `--headless --editor --quit-after 180` check; the older immediate editor-shutdown issue described below remains a toolchain limitation.

The new `CombatSystem`, `VisibilityService`, weapon profile, events/result and portable RNG all remain standalone .NET code. Shared scenario JSON is embedded in the core and also consumed by the Python oracle. Terrain presentation receives those same hill/forest definitions; its cached mesh approximates analytic heights, while gameplay queries remain exact. No Godot combat raycasts, individual soldier logic, new dependencies or balancing changes were introduced.

### Headless combat measurements

Linux, Ryzen 5 7600X3D; Python 3.14.8; SDK 10.0.403 / runtime 10.0.14; C# **Release**, no profiler. Same JSON/seed 17, 100 warm-up + 600 measured ticks (**60 simulated seconds**), three sequential repeats. Workloads include mixed terrain, marching under fire, fresh LOS queries, stationary volleys and sustained melee. Both exclude morale/routing, charges, artillery, commander effects, army AI, rendering and snapshot serialization. Final strengths and random-draw counts match at every count. Metrics are averaged per-run statistics, not pooled percentiles.

| Regiments | Python mean / p95 tick ms | C# mean / median / p95 tick ms | C# ticks/wall second | Wall seconds for 60 simulated seconds | Managed bytes/tick |
|---|---:|---:|---:|---:|---:|
| 12 | .736 / 1.211 | .192 / .157 / .316 | 5,200 | .115 | 66,346 |
| 24 | 1.760 / 2.662 | .421 / .335 / .701 | 2,370 | .253 | 120,848 |
| 36 | 3.000 / 4.443 | .653 / .527 / 1.112 | 1,532 | .392 | 187,004 |
| 60 | 6.420 / 9.172 | 1.107 / .800 / 2.185 | 903 | .665 | 314,630 |

This is a **3.8–5.8× scoped comparison**, not a speedup over the complete Python game. Twelve→sixty regiments costs about 5.8× in C#. At 60, the full 700 ticks produce 178 volleys, 525 melee pulses, 3,416 casualties; 105,680 visibility requests become 10,085 sampled rays (260,141 samples). Metrics include warm-up; the runtime table excludes it. All counts remain comfortably below the 100 ms tick budget, including 10× at the measured headless rates. That is not a guarantee for future full AI/projectiles/morale or larger/densely wooded maps.

The initial baseline is retained as `benchmark-results/m2-movement-before.*`. A stronger paired guard rebuilds the checkpoint and current core in Release, interleaving three sequential repeats with identical original movement inputs:

| Regiments | Before mean / p95 ms | After mean / p95 ms | Mean change |
|---|---:|---:|---:|
| 12 | .0829 / .0997 | .0826 / .1033 | −.3% |
| 24 | .1832 / .2306 | .1817 / .2265 | −.8% |
| 36 | .2639 / .3482 | .2642 / .3356 | +.1% |
| 60 | .5055 / .5972 | .5182 / .6090 | +2.5% |

Movement allocations are unchanged. Small timing differences are not evidence of a movement algorithm change. Raw JSON/CSV: `benchmark-results/csharp-combat.*`; paired guard: `m2-movement-guard.json`. Outputs stay ignored, separate from game source.

### Godot live-combat rendering

Actual X11/GTX 1080 (driver 580.196.07), Godot 4.7.2 .NET, **Debug** game assembly; 1280×800 window / 962×578 battlefield, perspective span 800 m, 2× MSAA, directional shadows, 32 maximum representative figures per infantry. Same combat fixtures now march under fire while other pairs fight in melee. Each independent run warms 60 frames and measures 600 uncapped wall-clock frames at 1×. No competing tests/benchmarks ran. These are separate rendering observations, not Release headless timings; each sample covers only the initial few simulated seconds.

| Regiments | Mean / median / p95 frame ms | Mean displayed FPS (1000/mean) | Presentation CPU mean ms* | Visible figures |
|---|---:|---:|---:|---:|
| 12 | 2.78 / 2.68 / 3.38 | 360 | 1.96 | 382 |
| 24 | 4.44 / 4.27 / 5.45 | 225 | 3.46 | 763 |
| 36 | 6.08 / 5.83 / 9.18 | 164 | 4.93 | 1,142 |
| 60 | 9.30 / 8.51 / 14.30 | 107 | 7.87 | 1,878 |

*This CPU field measures the viewer update, including live ticks when due, camera, interpolation, figure/terrain transforms and effects; it is not a GPU-only timestamp. Overall frame time includes rendering/present. Terrain builds once (54,891–64,521 vertices; 62 trees); startup is 357–404 ms. Accumulator remainder stays below one 0.1 s tick, with no excess debt. The final 60-regiment sample records 28 volleys, 60 melee pulses and 2,685 actual visibility rays, so this is an active combat source. Results are one sample per count, not worst-case guarantees for very close views, more trees, long battles or slower GPUs. Raw reports/logs: `benchmark-results/m2-gpu/`. GPU screenshots inspect the reused combat panel and all controls at 1280×800 and 800×600.

### Limits and next stage

Morale values/states remain frozen, while cohesion is functional. No provisional rout threshold is introduced. Only ordinary musket infantry deals damage; other movement archetypes are movable/damageable but cannot keep an infantry-annihilation test battle running. Attack seeks a firefight; normal movement can force contact/disengage. Full infantry/cavalry charges, pursuit, artillery, tactical planning, specialist/commander abilities and campaign remain unported. Exact details, cache lifetimes and temporary perception/destruction differences are documented in [COMBAT.md](godot/COMBAT.md).

A seed-17 native duel reaches army_0 victory at **919.7 simulated seconds**, with 300 volleys and 830 casualties. Last survivors can prolong annihilation battles without morale. Completion uses the existing HUD, with Reset; no campaign/results replacement was built. Future priorities: morale/routing/rallying and proper victory first, then cavalry charge/pursuit, artillery physics, tactical AI and specialist/commander effects. Retain all reference fixtures and replay paths throughout. Allocation reuse in spatial/targeting collections and presentation-side figure/terrain updates are measured optimization candidates; no decision cadence or terrain precision was reduced.

## Movement-port milestone: audit and implementation plan

The authoritative movement reference is the **current** `simulation/movement.py` and `positioning.py`, not an earlier specification. The tick is 0.1 s. Commands precede intent calculation; congestion samples the shared previous velocities before movement, settling chooses stable alternatives, one-shot avoidance chooses destinations, movement/turning runs, congestion applies disruption once, idle recovery runs, and bounded enemy SAT correction follows. Infantry formation transitions last 7 s and cost 6 cohesion; cavalry/artillery footprints remain 40×18 / 28×18 m. Artillery has 3 s limber and 8 s setup timers. Arrival is within 1 m and an optional final facing remains turn-rate limited. Hold/Move orders are retained after arrival.

Friendly movement is deliberately soft: exact OBB intersection area, worst-pair rather than additive penalties, measured-velocity alignment, low same-direction cavalry impedance, no continuous stationary cohesion loss, and a 2 s stationary-overlap delay before deterministic bounded settling. Spatial pairs preserve original regiment-list order. Settling keeps preferred destinations intact and reserves alternate goals. Avoidance tries one bounded detour per goal and falls back to passage. Analytic terrain movement samples the centre/corners; slopes, forests, formation and static archetype multipliers are separable from LOS/combat.

The Godot renderer already consumes `BattleFrame` DTOs plus an adjacent frame pair/alpha; it need not read JSON. `TacticalCameraRig` and the HUD are separate from recording I/O. The existing replay source/clock can coexist with a live adapter implementing those same presentation fields. C# will pass typed in-memory snapshots at fixed ticks, with presentation-only conversions to `BattleFrame`; no per-frame JSON loop is needed.

Implementation order: (1) standalone double-precision C# state/geometry/formation/order/clock library and headless runner; (2) direct movement/congestion/avoidance/settling/terrain port with commander effects neutral; (3) common movement fixtures invoking the unchanged Python movement functions for sampled reference states; (4) thin Godot .NET bridge and live/replay selection reusing the 3D scene, camera and inspector; (5) deterministic regression comparisons and matched movement-only benchmarks. Enemy contact is an obstacle/contact condition, without melee or AI. Combat, routing, charges, LOS, commander effects and campaign remain Python-only.

The installed Godot 4.7.2 is the standard edition and no .NET SDK was initially present. Matching Godot .NET and SDK 10.0.403 were installed **locally under ignored `.tools/`**, without system changes, and used for actual builds and GPU live execution. `.git` is a read-only empty stub, so `/tmp/rtt-before-csharp.tar.gz` preserves the pre-port Godot project/tools/docs instead of a branch. Final build/test commands and measured results are recorded below.

## Architecture audit

| Responsibility | Current implementation | Migration observations |
|---|---|---|
| Battle state / fixed update | `simulation/battle.py`, `config.py` | `Battle.step()` owns the exact 0.1 s phase order, seeded RNG, queued commands, victory, events and effects. Pure Python. |
| Regiment state / formations | `regiment.py`, `unit_stats.py`, `archetypes.py`, `formations.py` | Immutable characteristics plus mutable state; many timers and commander/charge/settling fields. Preserve separation but do not confuse a presentation snapshot with a full simulation checkpoint. |
| Geometry / collisions / movement | `geometry.py`, `movement.py`, `positioning.py`, `spatial.py`, `routing.py` | Metres and clockwise radians on downward Y. Exact oriented rectangles, SAT/slab tests, soft friendly congestion, deterministic nearby queries and gradual settling. |
| Combat | `combat.py`, `cavalry.py`, `infantry_charge.py` | Statistical volleys, frontage/LOS/friendly obstruction, melee intervals, one-time impacts, momentum and bounded aggregate pursuit. Preserve update/iteration/RNG ordering. |
| Morale / cohesion | `morale.py` | State hysteresis, finite rout propagation, shared cohesion recovery and capped support. No drawing dependency. |
| Terrain / visibility | `terrain.py` | Analytic Gaussian and compact hills; smooth elliptical forests. Exact analytic queries, bounded caches and feature grids. Rendering has its own approximation/cache. |
| Artillery | `projectiles.py` | Mutable balls, absolute elevation, deterministic substeps, terrain clipping/bounces, penetration and friendly fire. No stable public projectile ID yet. |
| AI / commanders / upgrades | `ai.py`, `commander_ai.py`, `commanders.py`, `upgrades.py` | Local rule-based decisions; explicit player authority; immutable commander identity/traits/acquired abilities. Some decisions and modifier hooks cross module boundaries. |
| Presentation | `viewer/renderer.py`, `terrain.py`, `interpolation.py`, `camera.py`, `hud.py`, `results.py` | Pygame-only; poses/text/terrain surfaces are viewer-owned. Existing battle report is independent and will stay in Python during this phase. |
| Input / loop / UI | `main.py`, `viewer/application.py`, `controls.py`, `command_bar.py`, `setup.py`, `campaign.py` | Accumulator with retained backlog, budgeted fixed ticks, camera-only frames. Input queues simulation Commands. Setup may replace recipes; preview battles do not advance. |
| Configurations / shared definitions | `scenarios/battle_config.py`, presets JSON, Python archetype/commander/upgrade registries | Versioned recipes, explicit terrain/seed/deployments and fresh battle creation. Definitions partly Python code, not a language-neutral shared data package yet. |
| Campaign | `campaign/state.py` | Implemented five-battle loop, immutable persistent roster, retired commanders, deterministic offers, one-time claims and atomic between-battle saves. Separates battle records from transient state. |
| Tests / analysis | `tests/`, `analysis/` | 559 pre-migration pytest tests; exact fingerprints, unit/trait/state-machine tests, scripted demos, seeded/mirrored balance and separate timing/render harnesses. |

### Coupling and risks

An import search found no Pygame/viewer imports, screen coordinates or wall-clock timing in `simulation/`, `scenarios/` or `campaign/`. Simulation ticks do not use rendering delta. Renderers read authoritative state and keep interpolation/selection/camera/cache state locally. Terrain rendering/debug queries can populate memoization caches, but do not alter tactical results or consume RNG. Headless construction/import tests can check this boundary.

The main migration challenges are behavioural, rather than Pygame dependencies:

- `Battle.step()` has an important sequential phase order and ordered command/pair/shot resolution. Changing this changes outcomes.
- A large mutable Regiment currently mixes authoritative properties with per-system timers and derived/debug fields. A C# port needs an explicit inventory, not only the exported visual fields.
- Static registries and tuning are global dictionaries/frozen dataclasses. They are treated as read-only by convention; extracting data must preserve defaults, IDs, units, eligibility and bounded stacking. Modifier functions are executable rules, not JSON.
- Geometry has bounded module-level LRU caches; terrain has mutable derived caches inside frozen data. These are not saved state. Existing optimization correctness depends on exact keys, stable candidate ordering and phase-specific spatial indexes.
- Projectiles lack a public identity, and the existing event deque retains only 250 entries. A periodic poll alone loses events and very short-lived shots. The opt-in recording observer therefore copies events/effects at emission and assigns **recorder-owned** monotonic projectile IDs, including shots removed in their first tick. It never consumes RNG or changes physics.
- Some terrain/trait enum values currently use display labels. Introduce stable IDs and migrations before treating these exported definitions as an editable shared-data source.
- Effect/event times use the start of the current tick, while snapshots after `step()` describe its end. Recordings document this convention; they cannot reconstruct internal physics substeps.
- The current simulation stores no portable RNG checkpoint or full replay command stream in visual recordings. Do not treat them as save games.

### Performance considerations

Preserve exact geometry/visibility caches, spatial broad phases, early rejection and AI cadence. Current benchmark tooling separates fixed-tick cost from Pygame drawing. Do not replace analytic terrain, physics substeps or fixed ticks just to speed up presentation. The Godot viewer reads only two neighbouring frames plus a four-frame cache, indexes file byte offsets for seeking, parses on snapshot changes rather than every render frame, and caches static terrain drawing. Large files are exported incrementally. Loader indexing/events still require memory proportional to frames/events, not regiments × frames.

## Environment and dependency setup

Initial replay-stage inspection, 2026-11-04: `/usr/bin/godot` reports **4.7.2.stable.arch_linux.ed1daf0bf**, the standard editor. No .NET SDK or .NET-enabled Godot was initially installed. Replay uses GDScript and requires no SDK, assets or third-party Godot addons. The later movement milestone installs and validates the local .NET tools described below.

For the future C# stage install the **Godot 4.7.2 .NET edition** (Linux x86_64 archive `Godot_v4.7.2-stable_mono_linux_x86_64.zip`, or corresponding Windows build), and a **64-bit .NET SDK**, not just a runtime. The official prerequisites state .NET 8 or later for desktop; use a supported current SDK (e.g. .NET 10), verify `dotnet --info`, and let that .NET editor generate its version-matched Godot SDK project. Use matching .NET export templates when exporting. Sources: [official Godot downloads](https://godotengine.org/download/linux/), [C# prerequisites](https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/c_sharp_basics.html). No machine-wide installs are performed by this migration.

## Proposed C# migration order

1. Pure .NET library for world vectors, angles, oriented geometry, IDs, rules and battle state; no `Node`, physics engine or Godot vector dependency in authoritative code.
2. Regiment/static archetype and commander records, formations, explicit commands; extract and validate language-neutral definitions with stable IDs.
3. Fixed-step movement and turning, then friendly congestion/settling and deterministic spatial candidates.
4. Terrain analytic queries/visibility and exact cache invalidation.
5. Volleys/friendly obstruction/melee, morale/cohesion/rout/rally, then mounted/infantry charges and pursuit locks.
6. Artillery trajectories/substeps/penetration/bounces and stable simulation-owned projectile identities.
7. Local/army AI with identical scheduling and player-command priority.
8. Specialist traits, commander personalities/specializations and acquired upgrades.
9. Battle recipes/deployment and campaign transactions/save compatibility; later replace Python authority only after parity and performance validation.

Keep the viewer consuming `BattleFrame` data throughout. A C# adapter can supply adjacent snapshots without knowing JSON; keep the authoritative library runnable by a headless test executable.

### Using Python as a reference

Port geometry/bounds/modifier/state-transition tests first, with explicit tolerances. Translate fixtures and command sequences rather than pytest/Pygame plumbing. Record controlled scenarios for crossing, stacking, pursuit, LOS ridges, artillery, morale cascades and upgrades. Compare state at matching ticks plus assertions about invariants and event order. Visual recordings are useful oracles for *observable* state, not complete internal-state equivalence.

Python `random.Random` uses MT19937 with Python-specific seeding, distributions and draw consumption; .NET `Random` with the same integer seed is not equivalent. Decide on a specified cross-language PRNG/seeding/distribution contract before demanding exact parity, or record an RNG draw tape for comparison experiments. Changing RNG changes the baseline and needs separate approval/testing. Python doubles vs Godot's usual float32 Vector2 vs C# double, trigonometric implementations, Python 3.12+ float summation, modulo/rounding rules and unordered hash iteration can also differ. Keep stable ID/list ordering and use double-precision C# simulation math. Exact Python fingerprints are useful on the same runtime; a normalized/tolerance-aware shared oracle is needed across languages.

## Original 2D prototype and validation

The original scene remains `godot/scenes/battlefield.tscn`; launch with `godot --path godot --scene res://scenes/battlefield.tscn`. The completed mixed-arms recording loads by default. The project now opens the 3D viewer described below. These measurements and test counts describe the initial 2D stage. See [viewer controls/setup](godot/README.md) and the [version-1 recording specification](migration_tools/FORMAT.md).

The source boundary is deliberately small:

```text
Python Battle + opt-in read-only recorder
             ↓
metadata.json + frames/index/events.jsonl
             ↓
RecordingSource (validation + indexed four-frame cache)
             ↓
BattleFrame / UnitState / ShotState / BattleEvent / TerrainData
             ↓
BattlePlayback (time + adjacent frames) → RegimentView + BattlefieldTerrain
```

The recording adapter owns JSON parsing; the renderer owns no file access or battle rules. A future C# adapter can construct the same presentation objects/adjacent-frame pair, bypassing recording playback when running live. The model uses Godot Vector2 only in **presentation**; the future authoritative library should use its own double-precision math. Terrain display reproduces both current analytic hill formulas and forest taper/max-density behaviour, with a cached visual raster and decorative trees. Fonts use a fixed raster size plus draw transforms, avoiding unbounded glyph sizes when zooming out. One visual node draws regiment batches, rather than creating physics/AI objects for soldiers.

Python changes are restricted to an optional observer on Battle, event/effect forwarding, an out-of-band firing-unit ID for smoke, and projectile-launch notification. No movement, combat, morale, AI, terrain, campaign or balance rules were ported or redesigned. Observers are absent in normal play, with checks only at emission sites. The exporter writes initial, sampled and final states incrementally and never uses the battle RNG. Regression tests compare recorded/unrecorded battle fingerprints and RNG states, byte-identical repeated exports, actual completion, stable identities/byte offsets, and event capture beyond the original deque limit.

Final validation: **566 pytest tests pass**, versus 559 before migration. This includes an optional installed-Godot bridge; without Godot that one test skips. The native headless script performs **60 playback checks**, traverses all 1,163 sample frames, validates terrain/interpolation/seek endpoints/selection/inspection/cache bounds, and handles missing/malformed input, disappearing units and ball transitions. Godot's editor imported/compiled the project cleanly; both headless and actual OpenGL/X11 playback ran. Screenshots were inspected at 1280×800 and 800×600. The existing Pygame main menu and direct-battle launch also pass smoke tests. .NET SDK/compiler execution was **not** tested because those tools are absent.

### Measured performance

Host: AMD Ryzen 5 7600X3D, NVIDIA GTX 1080 (driver 580.196.07), Linux, Python 3.14.8, Godot 4.7.2 standard, OpenGL Compatibility/X11. Each viewer sample uses a **separate actual GPU run**, 1280×800, vsync disabled, 60 warm-up frames and 600 measured frames. Frame times are wall-clock intervals measured with `Time.get_ticks_usec`, not smoothed engine delta or simulation seconds. All cases use seed 17, a 1,000×600 m Mixed Terrain field, 10 Hz snapshots from an active combined-arms recording and playback beginning at 15 simulated seconds. No competing simulations/tests ran during these measurements. A single run per count is a performance sample, not a universal hardware guarantee.

| Regiments | GPU viewer mean / p95 frame, ms | Regiment draw-command CPU mean, ms | Separate Python mean / p95 tick, ms |
|---:|---:|---:|---:|
| 12 | 2.33 / 2.75 | 0.51 | 1.55 / 2.98 |
| 24 | 3.53 / 4.18 | 1.01 | 10.56 / 14.72 |
| 36 | 4.84 / 5.74 | 1.56 | 21.43 / 30.77 |
| 60 | 7.80 / 9.29 | 2.77 | 59.29 / 67.90 |

Python timings use an independent **unrecorded** replay: 100 warm-up ticks followed by 200 measured ticks (20 simulated seconds). Recording/export time is stored separately and includes serialization/I/O. These are different time units/workloads from viewer frames; the GPU results do **not** imply that a live 60-regiment simulation would run at the playback FPS. Long authoritative ticks can still hitch a future integrated viewer and must be measured during C# integration. This task did not optimize or replace the Python algorithms.

Opening a recording took 598–622 ms, of which 592–605 ms was the **one-time** terrain-cache build. Camera pan/zoom did not rebuild terrain. All samples retained at most four decoded snapshots; the viewer parsed neighbouring frames at recorded-time boundaries rather than all frames each render. Larger maps with many more terrain features can take longer to bake and have not been benchmarked here. Raster, projectile interpolation and Godot Vector2 are display approximations; Python outcomes remain unchanged.

Raw results live under `benchmark-results/godot/{12,24,36,60}-units/`: `python-timing.json`, `graphics.json`, `headless.json` and their logs. The bundled complete example is about 8 MB at 2 Hz, with full-rate visual/log events. Other generated recordings and caches are ignored by source control; the bundled example is intentionally retained. Reproduce with:

```bash
python -m migration_tools.benchmark_viewer --mode prepare
python -m migration_tools.benchmark_viewer --mode graphics --frames 600
python -m migration_tools.benchmark_viewer --mode headless --frames 600
godot --headless --path godot --script tests/test_playback.gd
pytest -q
```

Use a fresh `--output-dir` to regenerate recording/timing inputs; otherwise the utility intentionally reuses existing files. Headless/dummy frame timings validate loading/update work but are **not** GPU rendering measurements. No Windows run or packaged executable export has been validated.

### Next stage

Start a standalone C# geometry/state library and headless tests, using Python geometry/formation/terrain fixtures as reference. Decide on portable RNG/seeding, numerical tolerance, event ordering and data ID/version conventions before porting stochastic combat. Then port movement/congestion and drive these same Godot visuals from C# frame pairs. Keep Python reference recordings and tests until parity, realistic live frame budgets and deterministic replay are demonstrated. Shared archetype/commander/upgrade data extraction should accompany state-model parity rather than creating a second independently maintained roster now.

## 3D presentation stage

The default scene is now `godot/scenes/battlefield_3d.tscn`. The original 2D scene/scripts remain runnable, with a button from the 3D HUD. The repository's `.git` is not a usable worktree, so a pre-change checkpoint was saved as `/tmp/rtt-godot-2d-before-3d.tar.gz` rather than creating a branch. The Python simulator, balance, fixed timestep, recording exporter and campaign were not changed by this stage.

The presentation boundary is still `RecordingSource → BattleFrame → BattlePlayback`. Optional archetype gun-count/faction metadata is read with defaults; version-1 recordings need no conversion. A small `scripts/three_d/` layer consumes those same DTOs:

```text
BattlePlayback frame pair + recorded events
    ├── RegimentView3D → per-regiment MultiMesh figures/footprints
    ├── Effects3D → cannonballs, smoke, charge/impact/rout/rally cues
    └── tactical markers + replay/inspection HUD
TerrainData → TerrainSurface3D → indexed terrain mesh + tree chunks
                         └── grounding and camera ray intersection
Real frame delta + InputMap → TacticalCameraRig → Camera3D
```

One metre maps to one world unit: Python X/Y becomes Godot X/Z, elevation becomes Y. Assets face +X and rotate by negative recorded facing about Y. Projectile heights are already absolute elevations. All conversions live in `world_3d.gd`; presentation never invents ballistic motion or resolves combat.

Terrain samples the recording's actual compact/Gaussian hills into a configurable grid, default 5 m and approximately 200,000 vertices maximum. Both the indexed triangles and grounding/ray queries use the same diagonal and interpolation. Static feature-support bounds and forest candidate cells reduce load cost without replacing analytic definitions. Trees are deterministic low-poly trunk/canopy MultiMeshes in spatial chunks. No collision bodies or navigation mesh are added. Shadows, slope/elevation colours and selected-foliage fading improve readability. Vertex palettes are explicitly converted to linear colour for Compatibility rendering.

Regiments contain batched placeholder soldiers, horses/riders/lances or guns/crew. Stable formation slots scale down with casualties and respond visually to cohesion/routing. Visual profiles use stable archetype IDs. There are no per-soldier nodes, simulation state, physics or AI. A distant cutoff retains tactical flags/footprints, and selected figures remain visible. Seeking reconstructs effects from the recorded event window, preventing stale projectiles/particles.

The camera is a separate rig/resource, independent of replay time and JSON. It supports heading-relative pan, terrain grab, orbit/tilt, smooth terrain-anchored cursor zoom, bounded focus, selected-regiment follow, overhead restore and matched orthographic/perspective scale. InputMap actions are remappable; the dedicated battlefield SubViewport isolates world input from UI. See [camera contract and configuration](godot/CAMERA.md).

Validation, current measured GPU results, reproduction commands and simplifications are maintained in [VIEWER_3D.md](godot/VIEWER_3D.md). This stage uses the installed standard Godot 4.7.2; .NET compilation remains untested and unnecessary for viewing. The next authoritative migration step remains the independent C# geometry/state library above, with an adapter into the existing `BattleFrame` presentation boundary.

## Implemented C# movement engine

This milestone completes the foundation proposed above. `godot/Quiberon.sln` contains four projects:

| Project | Responsibility |
|---|---|
| `Simulation/Simulation.csproj` | Ordinary .NET library: double XY geometry, cached OBBs, archetypes/regiments, orders, formations, movement/turning, congestion, stable settling, spatial candidates, analytic terrain movement and the fixed clock. No Godot references. |
| `Simulation.Runner/Simulation.Runner.csproj` | Headless fixture runner, duration/seed overrides, sampled JSON output, tick timings and managed allocation measurement. Does not initialize Godot. |
| `Simulation.Tests/Simulation.Tests.csproj` | xUnit mechanics/invariant tests and eleven Python-reference/determinism cases. |
| `Quiberon.csproj` | Thin Godot-only C# bridge; compiles just `scripts/simulation_adapter/**/*.cs` and references the simulation library. |

The pure .NET folders use `.gdignore`, preventing engine asset import from traversing their source/build products. Shared static data is `simulation_data/movement_archetypes.json`, extracted from current Python values and embedded in the library. Immutable/read-only definitions are separate from mutable regiment state. Snapshot records copy positions, orders and all relevant movement values into read-only collections.

`LiveSimulationBridge.cs` supplies native in-memory Godot collections at tick changes. `live_source.gd` adapts them into the **same BattleFrame pair/alpha contract** used by recordings. There is no per-frame JSON serialization/parsing, Python process or Godot navigation agent. Existing terrain meshes, regiment MultiMeshes, camera, markers and inspector are reused. Mode selection, right-click terrain picking, compatible formation/hold buttons, pause/speed/step/reset and debug timing were added to that scene/HUD. Live mode starts with Hold orders, six controllable Blue and two stationary Red regiments. Returning to replay reopens the previously selected recording; the original 2D scene remains available.

The current authoritative phase order is retained. Direction-sensitive congestion uses previous measured velocities, exact clipped footprint areas, worst-pair bounds and non-additive disruption. A second sample applies cohesion loss once. Stable settling preserves preferred orders, reserves alternative destinations, honors Hold/rest/ID priority, and uses the original bounded candidate/retry/timeout logic. Avoidance and terrain detours remain bounded and retain pass-through fallback. Spatial queries preserve candidate ordering; mutable enemy correction keeps the original traversal rather than querying a stale index. The fixed 0.1 s accumulator has a 16-tick-per-frame budget, retains overload debt and interpolates the last two completed states. Camera delta is independent.

### Scope and deliberate differences

- Four archetypes are supported: standard infantry/cavalry/artillery and woodland skirmishers. Existing line/column/loose footprints, speed/turn modifiers, seven-second formation changes, movement fatigue/cohesion, final facing, field bounds and artillery 3 s limber / 8 s setup are ported.
- Terrain movement is implemented, including analytic hills/forests, static footprint samples, gradient/formation/category costs and one-shot terrain steering. `--live-terrain` demonstrates actual terrain-aware movement. No LOS or terrain combat is claimed.
- Commander identity is plain data; default names are placeholders. All commander/upgrade/active specialist effects, combat, charge/pursuit logic, morale/routing and tactical AI are excluded. The shared-pursuit discount and pursuit lane coordination await that later subsystem; ordinary compatible cavalry already uses the original low same-direction cost.
- Enemy contact is the original bounded three-pass SAT correction without melee. It can nudge opposing formations; no damage occurs. Friendly contact remains soft. Firing priorities/obstruction are deferred with combat.
- Live UI exposes Move/Hold and compatible formations. The core retains arrival-facing data; the current right-click UI issues position-only movement. C stays camera-follow, so J is column. Live mode has no seek or mid-battle save.
- Movement consumes no randomness. Seed is retained, but .NET/Python RNG equivalence is not assumed. Both use double authoritative coordinates; Godot receives floats only for presentation. The C# footprint cache clears at its cap instead of Python's LRU eviction; this affects cache performance only.

### Reference validation

Eleven common version-1 fixture inputs and retained Python sampled oracles live under `migration_tools/movement_fixtures/`. They cover straight movement, turning, formation changes, friendly crossing, cavalry overtaking, stationary separation, destination conflict, dense congestion, bounds, artillery timers and woodland traversal. Comparisons include positions/facing, formations, cohesion/fatigue, movement states, complete orders, stopping alternatives, congestion and terrain factors. Discrete values must match; the absolute floating tolerance is **1e-5**.

All eleven pass. The largest numeric error observed in the direct CLI comparison was approximately **1.4×10⁻¹⁶**, including difficult contact/settling cases. Repeated C# runs also produce exactly identical serialized snapshots. The Python phase harness invokes current authoritative functions and is separately checked against the original sandbox `Battle.step()` in eight controlled cases; this guards against validating a C# port against a newly simplified Python algorithm.

Regression results: **38 standalone xUnit tests pass**, **578 pytest tests pass** (568 before this milestone), and native Godot checks cover **58 camera, 74 3D viewer, 60 preserved playback and 39 live integration assertions**. Live integration uses actual viewport mouse events for selection/orders and checks paused command execution, timed reforming, interpolation, visual-node reuse, 10× ticks, focus/follow/dolly, UI blocking, reset, terrain, stalled-frame wall-clock accounting and returning to replay. The live driver uses monotonic time rather than Godot's potentially capped process delta, retaining the full overload debt. The actual .NET editor and GPU game were launched. Normal editor launch/exit is clean; the immediate headless `--editor --import --quit` path hit a native `editor_node.cpp:6618` shutdown abort in this build. It is not used for live execution or headless simulation/tests. Windows and packaged exports remain untested.

### Matched movement-only performance

Same Linux/Ryzen 5 7600X3D host, Python 3.14.8, .NET SDK 10.0.403 / runtime 10.0.14. C# runner built **Release**, profiler disabled. Each language runs the same seeded, crowded combined-arms fixture: 100 warm-up ticks then 600 measured ticks (**60 simulated seconds**), including a scheduled reversal. Both exclude AI, combat, drawing and snapshot serialization. Python invokes existing movement functions; C# uses their port. Three sequential repeats were averaged; p95 values below are averages of each run's p95, not pooled distributions. No competing simulations/renderers/tests ran.

| Regiments | Python mean / p95 tick ms | C# mean / p95 tick ms | C# wall seconds for 60 simulated seconds | C# managed bytes/tick |
|---:|---:|---:|---:|---:|
| 12 | 0.759 / 1.077 | 0.082 / 0.099 | 0.050 | 15,613 |
| 24 | 1.600 / 2.219 | 0.184 / 0.229 | 0.110 | 28,873 |
| 36 | 2.421 / 3.409 | 0.263 / 0.338 | 0.158 | 44,035 |
| 60 | 4.267 / 5.942 | 0.492 / 0.605 | 0.296 | 77,481 |

Observed throughput is about 12,082 / 5,436 / 3,794 / 2,032 C# ticks per real second. This is **8.7–9.2× for this movement workload**, not an estimate for the full future C# battle engine. The 60-regiment case is easily inside the 100 ms authoritative tick budget. Short-lived spatial/query collections account for remaining managed allocation; reusing them is a possible later measured optimization, not a reason to alter behaviour now. Raw repeat-level metrics and CSV: `benchmark-results/csharp-movement.*`.

### Live Godot rendering

Separate actual X11/GPU runs used the GTX 1080 (driver 580.196.07), Godot 4.7.2 .NET, the default **Debug** game assembly, 1280×800 window / 962×578 battlefield viewport, 2× MSAA, directional shadows and 32 representative figures per infantry/cavalry. The live Open Field stress scenario has two stationary enemies and automatically marching friendlies, at 1×. Each case warms 60 frames then measures 600 uncapped wall-clock frame intervals. Perspective camera span is fixed at 800 m. No competing tests/simulations ran. This is one sample per count; these workloads are not mixed-terrain combat recordings.

| Regiments | Mean / median / p95 frame ms | Total update CPU mean ms | One-time load ms | Figure proxies |
|---:|---:|---:|---:|---:|
| 12 | 2.02 / 1.96 / 2.46 | 1.36 | 186 | 332 |
| 24 | 3.34 / 3.23 / 3.89 | 2.54 | 192 | 638 |
| 36 | 4.80 / 4.64 / 5.82 | 3.82 | 187 | 970 |
| 60 | 7.63 / 7.34 / 10.27 | 6.35 | 232 | 1,608 |

The update CPU column includes live driver/presentation work; it is not an isolated simulation tick measurement. Gun proxies contain decorative crew. Terrain is generated once (24,321 vertices normally; 34,371 on the taller 60-regiment map), with no trees in these open scenarios. Existing visual roots and meshes are reused; native tests verify smooth interpolation and identity preservation. No overload debt above the normal fractional tick remained in these samples. All four cases fit a 60 Hz frame budget on this machine. Other resolutions, hardware and future combat workloads need separate measurements.

Raw results/logs: `benchmark-results/live-{12,24,36,60}.*`. Reproduce with `.venv/bin/python -m migration_tools.benchmark_live --frames 600`. Its `--headless` option validates state flow only and must not be reported as GPU FPS. The standard .NET editor also starts and closes cleanly on the GPU; delayed headless editor validation (`bash tools/godot.sh --headless --editor --quit-after 180`) runs cleanly, avoiding the immediate import/quit shutdown issue noted above.

### Commands and next milestone

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --live
bash tools/dotnet.sh test godot/Simulation.Tests/Simulation.Tests.csproj -c Release
bash tools/dotnet.sh build godot/Simulation.Runner/Simulation.Runner.csproj -c Release
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --scenario turning --output benchmark-results/turning.json
.venv/bin/python -m migration_tools.movement_reference --compare benchmark-results/turning.json
.venv/bin/python -m migration_tools.benchmark_movement --repeats 3
bash tools/godot.sh --headless --script tests/test_live.gd
```

The SDK and matching Godot .NET edition are local under ignored `.tools/`. `tools/bootstrap_dotnet.sh` reproduces that Linux x86_64 setup without system installation. `tools/dotnet.sh` and `tools/godot.sh` configure SDK/cache paths; the normal `godot` executable still runs replay. See [Godot README](godot/README.md), [live architecture/tuning](godot/LIVE_SIMULATION.md) and [fixture format](migration_tools/movement_fixtures/README.md).

Next port LOS/visibility and simple infantry fire with controlled reference fixtures, after specifying a portable RNG and event-order contract. Then morale/routing, cavalry impact/pursuit and artillery can follow in separate milestones. Do not replace Python combat authority until those behaviours and realistic combined-system frame budgets are validated. Movement-only results do not validate unported commander, combat or campaign behaviour.
