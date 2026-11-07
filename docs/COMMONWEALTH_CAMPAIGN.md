# The Defence of the Commonwealth — playable campaign

Spring–Summer 1796. The Commonwealth resists Prussia and Russia, with Revolutionary
British, Irish and Haudenosaunee allies. This implements Part 2 of the supplied
Prologue Design Reference v0.1, using the existing fifteen core units, fourteen
historical definitions, native battle engine and twelve commander upgrades.

## Playing

From the repository root, using the installed **Godot 4.7.2 .NET / .NET 10**:

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh
```

Choose **New Campaign**. The overview shows its seed, briefing, force, commander
assignments, reserve officers and acquired abilities. A seed field can start a new
reproducible run. **Continue Campaign** loads the single versioned native save.
Custom Battle, Live laboratories and Python Replay remain separate menu options.

Read the briefing, assign officers, then deploy. Blue outlines show the actual
campaign deployment area, including the eastern bank at the Vistula. Only the
player's active regiments can be repositioned; ghost validation checks the whole
footprint, other units and water. Existing facing, formations, pause, speed,
selection, tactical camera and same-battle 2D/3D controls are retained. Deployment
Reset restores authored positions. Enemy command/setup edits and rematches are
locked during campaign missions. Normal player move/attack/hold/autonomy orders work.

Mission text shows progress, deadlines and waiting reinforcements; ground circles
mark objective/safety/exit areas in both views. Arrival events appear in the
existing notification line. After completion, the **existing battle-results dialog**
opens with **Continue campaign**. Results are committed and saved before leaving
this screen. Select one reward, resolve the event(s), assign new/reserve officers
and proceed. There is no ordinary reward after the final battle.

The optional both-armies-AI checkbox is a development/spectator mode. It includes
limited authored friendly guard assignments for defensive missions. It does not
turn an aggressive autonomous army into a general objective planner.

## Six stages / seven encounter definitions

| Stage | Encounter | Actual primary victory / failure |
| --- | --- | --- |
| 1 | The Frontier | Rout-based defeat of Bülow's reduced advance detachment; defeat if player fighting strength collapses |
| 2 | The Forest Road | Deny the western road exit for 360 simulated seconds, or break the enemy; lose after 10 uncontested seconds of enemy control |
| 3 | Defence of the Vistula | Deny an eastern bridgehead for 480 seconds, or break the enemy; bridge and ford are physical, Despard enters after 60 seconds, enemy second wave is scripted |
| 4A | A Dangerous Choice — Rescue | Bring at least 50% of the allied detachment's original strength into the western safety area without enemy control; fail if too few survive or time expires |
| 4B | A Dangerous Choice — Interception | Destroy/disperse both moving supply trains before either enters its eastern escape region; no requirement to annihilate escorts |
| 5 | The Two Eagles | Hold the western road junction against a mixed Prussian–Russian offensive for 540 seconds, or break it; rain, cavalry/artillery and a second wave |
| 6 | The Road to Warsaw | Protect the Warsaw road for 600 seconds, or break Suvorov's attack; prepared works and a combined-arms second wave |

Stage four is a choice, not an extra seventh battle. Rescue adds a temporary allied
support regiment in stage five; interception removes one Russian grenadier regiment.
Enemy wave timings vary deterministically by ±10 seconds. Enemy forces do not
scale in response to player recruitment/upgrades. Only the first two detachments'
starting strengths were reduced for the introductory encounters; unit balance
profiles/combat formulas were not rebalanced.

Cook can join around the forest encounter. Despard and a chosen line/rifle detachment
arrive with the expedition before the Vistula encounter; that detachment is
predeclared as a timed reserve for the battle. Historical individuals are unique.
Kościuszko remains a separate army-level commander; Suvorov commands the final
opponent at army level. Bülow, Blücher, Bagration and Platov use their existing
personalities/signatures in appropriate enemy regiment slots.

## Persistent state and rewards

`Simulation/Campaign/CampaignState.cs`, `CampaignSession.cs` and the embedded
`simulation_data/campaign/commonwealth.json` own progression without Godot.
Persistent regiments retain ID, name, archetype, faction, strength/maximum,
commander assignment, battles fought and damage inflicted. Commanders have a
separate pool: identity/personality/signature and upgrades survive reassignment or
regiment destruction. Assigning an already assigned officer swaps compatible
assignments; a displaced officer otherwise stays in reserve.

Each battle creates **fresh** Regiment objects from records. Morale/cohesion,
projectiles, orders, charge/melee/routing state, AI references and timers reset.
Surviving strength is copied back after a matching finished battle. Destroyed
regiments leave the roster; routed/escaped survivors are not counted as killed.
No commander death, injuries or experience system is implemented.

Defaults (editable in campaign JSON rules):

- Capacity **10**; bounded configuration supports 5–20 regiments.
- Victory replaces **20% of missing strength**, rounded upwards, for survivors.
- A replenishment reward restores **60% of missing strength**.
- At most **three** acquired upgrades per commander (configurable 1–3).
- Final victory is **Decisive** at ≥55% of the entering roster's maximum strength;
  otherwise **Negotiated**. Destroyed formations count against that denominator.
  A principal mission defeat ends the run as **Defeat**. No hidden ending dice roll.

Three stored offers are generated after ordinary victories: eligible coalition
regiments, historical commanders, upgrades or replacements. A training offer fixes
its recipient and up to three compatible upgrades; the recipient is displayed, and
one ability is chosen. Reopening/loading never rerolls offers. At capacity,
recruitment offers are excluded; full-strength armies do not get empty replacement
offers. Enemy-only units are not in ordinary recruitment. Allied unit pools unlock
through events. Existing sandbox recruitment remains unrestricted.

The twelve **existing mechanical upgrades** are reused:
Rolling Volley, Swift Reform, Rallying Presence, Controlled Charge, Relentless
Pursuit, Shock Commander, Woodland Ambush, Harassing Fire, Steadfast Defence,
Mobile Battery, Calculated Fire and Inspired Attack. Descriptions and compatibility
come from `simulation_data/commander_upgrades.json`; no duplicate combat framework
or regiment-owned upgrade system was added. Starting specializations remain separate.

Historical recruitment includes Dąbrowski, Madaliński, Jasiński, Łaźniński and,
after the relevant alliance unlock, FitzGerald and Cook. Despard/Cook may join via
their events. Names and alternative names are reserved against procedural campaign
officers; no invented Indigenous name generator was introduced.

## Events

The JSON contains a small fixed event schema: title/text, choices, flags, optional
unit and historical officer. Events resolve once, with explicit consequences:

- Haudenosaunee assistance: Cook plus a War Party, or a liaison officer in reserve;
  both unlock War Party recruitment.
- British arrival: Despard with line infantry or rifle specialists; unlock British
  recruitment and FitzGerald availability.
- Dangerous Choice: select rescue or interception and retain its result flag.
- Political tensions: regular infantry or republican Scythemen support.
- Prussian–Russian disagreement: delay the stage-five second wave by 45 seconds,
  or restore 35% of missing strength.
- Commonwealth volunteers: militia or Scythemen before the final battle.

At capacity, a unit-only event supplies replacements; an event recruiting a named
officer retains that officer in reserve even when its regiment does not fit. Text
explains the capacity fallback. No economy, diplomacy simulation or metaprogression.

## Objectives, scripted orders and reinforcements

The optional `ScenarioDefinition.Mission` adds `MissionSystem` to the existing
fixed-step engine. Scenarios without it keep the ordinary victory path. Mission
results own completion, preventing annihilation checks from overriding objectives.

Reusable types: **defeat, capture, hold, delay, rescue, convoy**. Definitions have
stable ID, description, side, centre/radius, duration, optional unit IDs, required
fraction, dependencies and optional/required status. Progress uses simulation time.
Capture needs uninterrupted uncontested control; Hold needs continuous presence
and resets on contest/absence. Delay fails after ten uncontested enemy seconds or
succeeds at its deadline. Routing and transport actors cannot control regions;
a token below max(5 soldiers, 5% original maximum) cannot contest. Rescue also
requires an uncontested safety area. Required failure/player collapse wins a
simultaneous tie. The mission's explicit timeout is a failure, never a fake victory.
An evaluator stopping earlier reports **inconclusive-timeout**.

Directives specify regiment ID, approach waypoints, optional crossing/formation,
arrival time or successful-objective trigger, and an after-route attack/hold action.
They use ordinary movement, real timed formation changes and crossing queues.
Player orders override friendly directives; routing overrides movement. Enemy
crossing assignments are authored. Friendly defensive slots are used only by the
optional autonomous-player mode. These are deliberately narrow scenario workarounds.

Reinforcements are **predeclared inactive reserve regiments**, not appended to a
mutable simulation collection. On trigger they activate only when their authored
entry footprint is water-safe and clear of other active formations. Blocked entries
wait and remain listed in the objective panel. The arrival emits one timestamped
event. Results distinguish `not-arrived` from escaped/destroyed; the report's planned
initial strength includes declared reserves. Permanent allied units are persistent
roster records; temporary rescue/support units have separate IDs and do not leak
into the roster.

Supply trains are a deliberately small **unarmed transport proxy** using an
instance of the existing artillery footprint/mobility model with weapon, guns and
melee disabled. They have crew/durability strength, a fixed route, normal combat
vulnerability and a simple batched wagon mesh. Rout/dispersal counts as disabling a
train. There is no cargo, supply economy, vehicle physics or new recruitable unit.

## Save/load and determinism

Single native slot: `user://commonwealth-campaign-v1.json` (Godot's QuiberonViewer
user directory). It is separate from Python campaign files. Writes use a temporary
file and atomic replacement. Version **1** and campaign ID are required; foreign or
unsupported saves are rejected. This is an initial native schema, not an importer
for the Python prototype.

Saved state includes seed, phase/stage/branch, rules, roster, all commanders and
assignments/upgrades, history, flags, pending event, exact pending offers and the
prepared encounter. Valid phases: overview, battle, rewards, event, ended. Files
are saved between battles and during choice screens; no mid-battle save is offered.
A pre-battle checkpoint survives abandoning a battle. A completed result is applied
once and autosaved before leaving the existing results screen. Repeated callbacks
cannot give another reward or advance a second time. If a save fails after result
application, retrying persistence does not reapply the result.

SHA-256-derived, explicit little-endian seeds separate combat, commander generation,
recruit officers, offers/upgrade selection and arrival variation. Preparation and
viewing choices do not consume the combat RNG. Same campaign seed and choices
reproduce the next encounter and offers. Campaign records never hold live Node or
Regiment references.

## Authoring / headless commands

Edit `simulation_data/campaign/commonwealth.json`, then rebuild. Starting units,
starting officer assignments, rules, briefings, deployments, enemies, environment,
mission objectives/directives, defensive slots and events are data. Existing
native terrain/environment JSON is reused. Branch consequences are a small set of
explicit native flag handlers, not a narrative programming language.

```bash
.venv/bin/python -m migration_tools.author_commonwealth_campaign
bash tools/dotnet.sh test godot/Simulation.Tests
.venv/bin/python -m pytest -q
bash tools/godot.sh --headless --script tests/test_campaign.gd

bash tools/dotnet.sh build godot/Simulation.Runner -c Release
# Natural starting roster, ordinary deterministic rewards, all AI:
bash tools/dotnet.sh godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll --campaign-run --seed 17 --branch rescue --output /tmp/campaign-run.json
# Full progression/save-load fixture: controlled wins, explicitly NOT AI victories:
bash tools/dotnet.sh godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll --campaign-fixture --branch intercept --output /tmp/campaign-fixture.json
# Isolated encounter, no invented outcome if the requested limit is insufficient:
bash tools/dotnet.sh godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll --campaign-stage 3 --seed 31 --duration 120 --output /tmp/vistula-profile.json
# Provisional 10-regiment composition laboratories (not naturally earned rosters):
bash tools/dotnet.sh godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll --campaign-run --build mobile --seed 31
# Isolated GPU laboratory; never overwrites campaign saves:
bash tools/godot.sh -- --campaign-stage=3 --live-warmup-ticks=1800 --live-speed=4 --benchmark-frames=600 --benchmark-output=/tmp/campaign-render.json
```

## Known limitations and the next AI pass

The campaign is playable end-to-end, but this is **first-playable balance**:

- The 45–90 minute human-run target has not been certified by a human playtest.
  Automated successful runs take roughly 30–40 simulated minutes plus deployment,
  inspection and decisions. Speed controls remain available.
- Interception is short and especially easy for a developed artillery/rifle army;
  convoy durability/route exposure need further tuning. Rescue takes substantially
  longer. Both give a meaningful but simple stage-five advantage.
- Authored guard slots prevent spectator armies abandoning defensive goals; enemy
  waypoint columns can be predictable. There is no general objective-taking,
  coordinated crossing, bridgehead, reserve or defensive-occupation planner.
- Artillery mobility uses current limber/compact-column rules; congestion or enemy
  occupation can delay crossings. Blocked reinforcements wait rather than spawn on
  top of troops. Wider/safely authored approaches remain necessary.
- Escort AI is ordinary local combat AI around a scripted transport route, not a
  coordinated convoy-escort operation. Skirmisher/cavalry pursuit can still divert
  regiments from useful positions; explicit player intervention remains valuable.
- Capture is a goal-completion model, not a permanent contested-frontline network.
  Optional/dependent objectives are supported, but the initial missions mostly use
  defeat, delay, rescue and interception rather than elaborate multi-objective chains.
- Save/load is between battles, with one slot and no campaign save migration from
  Python. No commander injury/death, economy, relationships or metaprogression.
- Temporary support troops do not become permanent recruits unless explicitly
  represented by a persistent event/roster addition.

Next development should use these exact scenarios to improve river approach/
crossing coordination, defence commitment, escort behaviour, objective-taking,
pursuit limits and reserves. Keep regression seeds and report stuck outcomes rather
than disguising them as wins.

## Recorded validation — 6 November 2026

- **581 native tests passed** (551 pre-campaign baseline plus 30 new campaign cases),
  including both six-stage controlled progressions with save/load, strength and
  commander persistence, events/rewards, destroyed/escaped handling, all endings,
  upgrade compatibility/limits, region contesting, rescue/convoy rules, safe arrivals,
  historical name/alternative-name uniqueness and direct player-order precedence.
- **674 Python tests passed**. Python combat/campaign implementation was not changed.
- **568 Godot assertions across 15 scripts passed**, including 29 campaign checks
  and main-menu campaign entry. Existing custom setup, replay, formations, camera,
  facing, environmental features and shared 2D/3D view checks remain in the suite.
- The 29 campaign checks also passed in the real GPU renderer. They exercise the
  overview, actual opening battle, locked campaign deployment, reused results,
  once-only commit/save/reload, rewards/event transition, physical wagon meshes
  and the prohibition on moving rescue targets into safety during deployment.
- Both controlled fixtures reached six stages and the ending with serialization
  boundaries. They are explicitly marked `fixture: true`; they are **not** counted
  as autonomous battlefield wins.

### Actual complete campaigns

These use the **natural five-regiment start**, deterministic ordinary rewards,
alliance/events and subsequent recruitment. Both armies are autonomous; friendly
AI uses the documented authored guard slots. No scripted victory is injected.

| Seed | Stage-four branch | Battles completed | Ending | Simulated minutes |
| --- | --- | ---: | --- | ---: |
| 17 | rescue | 6 | decisive | 38.6 |
| 17 | intercept | 6 | decisive | 29.4 |
| 31 | rescue | 6 | decisive | 36.6 |
| 31 | intercept | 6 | decisive | 32.5 |
| 73 | rescue | 6 | decisive | 31.7 |
| 73 | intercept | 6 | decisive | 27.5 |

All six natural-start runs concluded validly; no evaluator timeouts were hidden.
This supports end-to-end playability, **not** a claim that difficulty or human
playtime is final. First-playable tuning is forgiving, and interception is notably
shorter than rescue. Controlled tests separately verify negotiated victory/defeat.

Additional provisional **10-regiment starting build laboratories** (People's Army,
Mobile Army and Firepower Army, seeds 17/31) also completed six stages. Those
rosters were prefilled for composition testing and are not presented as naturally
earned campaign starts. Twenty-one isolated encounter tests (seven scenario
variants × three seeds) start with the small base roster; wins and losses are
recorded honestly. Those late-stage five-regiment tests are not a balance claim
about a naturally developed late-game army.

Raw reports: `benchmark-results/campaign/default-{rescue,intercept}-{17,31,73}.json`,
`fixture-*.json`, `run-{people,mobile,firepower}-*.json`, and
`stage-{1..6}-*-seed*.json`. Repeat them with
`migration_tools.evaluate_campaign --suite runs|fixtures|builds|encounters`.

### Performance

Ryzen 5 7600X3D, .NET 10 Release. Isolated full encounter measurements below are
medians of seeds 17/31/73 with the base roster and authored AI/objectives enabled.
They include cold/JIT startup ticks rather than claiming a separate AI or objective
microbenchmark. Allocations include the entire simulation and measurement lists.

| Encounter | Mean tick ms | p95 tick ms | Ticks/s | Allocated KiB/tick |
| --- | ---: | ---: | ---: | ---: |
| 3 | 0.375 | 0.586 | 2663 | 153 |
| 5 | 0.500 | 0.904 | 1997 | 122 |
| 6 | 0.477 | 0.872 | 2091 | 132 |

Matched legacy Clear workloads (three runs, 100 warmup / 600 measured ticks) still
match all four pre-campaign final regiment states and combat RNG draw counts.
Observed local timings, rather than a general speed claim:

| Regiments | Before mean ms | After mean ms | Difference |
| --- | ---: | ---: | ---: |
| 12 | 0.226 | 0.231 | +2.3% |
| 24 | 0.500 | 0.517 | +3.3% |
| 36 | 0.772 | 0.805 | +4.2% |
| 60 | 1.255 | 1.233 | -1.7% |

The small 12–36-regiment increases are reported, not concealed; JIT/scheduling
noise and different run dates limit precision. No large baseline regression was
observed. Campaign roster/reward/save operations run outside ordinary battle ticks.

Actual Godot GPU measurements: GTX 1080 / NVIDIA 580.196.07, X11, Godot 4.7.2 .NET,
OpenGL compatibility, shadows, 32 decorative figures, 800 m view, 4× speed,
600 measured frames after 180 simulated seconds. These use isolated 10-regiment
player development rosters, not the small headless roster above.

| Encounter | Mean frame ms | p95 frame ms | FPS |
| --- | ---: | ---: | ---: |
| 3 | 3.58 | 6.75 | 279 |
| 5 | 3.57 | 6.48 | 280 |
| 6 | 3.89 | 7.50 | 257 |

Frame and simulation debt/counters are retained in `render-stage-*.json`; these
local short-window FPS measurements do not guarantee later intense-battle frame
rates. Terrain meshes are retained, and no authoritative ticks are discarded.
