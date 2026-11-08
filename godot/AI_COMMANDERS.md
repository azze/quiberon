# Milestone 5 audit / port contract

Current coordination is documented in [Army director and mounted reserves](ARMY_DIRECTOR.md), including a matched comparison against the frozen previous AI.

The subsequent [tactical decision pass](TACTICAL_DECISIONS.md) adds shared mission
assignments, local support-aware engagement decisions, and infantry firing-position
selection. Earlier Python-reference AI descriptions below document the foundation;
those three native extensions intentionally change tactical decisions.

**Current update:** the subsequent [native sandbox stage](SANDBOX.md) ports infantry
bayonet impacts and acquired abilities. Infantry Firebrand is now generated and
active, and defensive AI recognizes Steadfast Defence. Statements below excluding
those features describe the historical Milestone 5 boundary. Campaign remains
unported.


Reference: current Python `ai.py`, `commander_ai.py`, `commanders.py`, and their
hooks in movement, terrain, combat, morale, cavalry. Source checkpoint is
`/tmp/rtt-before-milestone5.tar.gz`; Python gameplay is unchanged.

Python army plans every 50 ticks (5 s), iterating armies/units stably. Strategies:
balanced, all_out_attack, hold_the_line, skirmish. Fourth-or-later infantry can
reserve until 75 s if enemies are >190 m away. Player orders persist; invalid
attack/charge may release autonomy. Charge/pursuit/recoil/reform are not overwritten.
Cavalry score: cohesion+.12*distance+(60 infantry else -40)+50*readiness−90 if
wavering/routing. Initial flank waypoint ±100 m; commitment 18*personality factor.
Artillery searches eight ±60/diagonal40 m offsets when ridge-blocked; clear
positions score forest*3+slope; relocation commitment60 s. Ordinary range .85.
Skirmish desired range .82 rifles/.72 others. Retreat below min(80,range*.45),
or100 versus cavalry, only against stronger opposition; woodland ambush power
changes that comparison. Retreat6 s + up to4 s turning, then10 s re-engagement.

Personalities use a single policy (commitment,pursuit metres,disengage seconds,
overmatch,firing distance): aggressive(.65,320,18,2.4,.78), cautious(1.35,120,6,
1.15,.95), methodical(1.2,180,12,1.65,.85), opportunistic(.5,280,12,1.6,.85),
stalwart(1,140,24,2.7,.85). Methodical low-cohesion prep lasts8 s, retries28 s;
retreat40 m/10 s, cooldown40 s. Opportunistic target lock10 s, improvement15.
Pursuit breakoff avoids the same fugitive30 s. Exact numerical traits/name pools
are exported to shared commander definitions, excluding acquired upgrades.

Specializations: Drillmaster high-cohesion formation−15%/turn loss−10%/recovery
+10%; Firebrand exposed impact shock+12%, up to3 cohesion disorder, pursuit+15%;
Pathfinder forest slowdown−20%/uphill−10%/terrain loss−15%; Sharpshooter stationary
accuracy+12% with clarity, reload+8%; Artillerist scatter−12%, redeploy+10%;
Inspirer strongest visible125 m aura .12/.18 morale per second and rout shock×.9;
Pursuit Specialist power+12%/gap+10%/pursuit congestion loss−10%, prepared frontal
power−10%; Defensive prepared frontal damage/disorder−10%, quiet recovery+10%,
aggressive advance−5%. Methodical turns−8%; Stalwart shock−10% and defensive
shaken morale+.04/s. No acquired upgrade hooks are ported. Infantry Firebrand is excluded from normal
C# generation/setup until bayonet impacts are ported; imported assignments retain
their identity but explicitly display that effect as inactive. Cavalry Firebrand
is fully active and tested, including its post-impact disorder cost.

Preserve legacy fixtures with explicit disabled AI/commander flags. Name generation
uses a separate deterministic stream; normal Python MT19937 identities are not
claimed to match. Supplied commander identities/traits are preserved. Curated
Haudenosaunee names remain whole and rank-free; no invented syllables/surnames.

## Architecture and execution

`TacticalAi` runs entirely in the standalone simulation; `CommanderSystem` reads
immutable definitions/name pools from `simulation_data/commander_definitions.json`.
No commander is a Godot node or archetype subclass. Regiments reference immutable
identities plus separate mutable decision state (locks, retreat timers, pursuit
origin, etc.). Records accept the Python ID/name/rank/background/personality/
specialization fields; optional nation is preserved separately. Supplied IDs are
validated/retained; duplicate assignments are rejected. Acquired upgrades are not
implemented. JSON serialization is independent of the viewer.

The tick applies player commands, prepares spatial queries, evaluates due AI,
then runs existing movement/contact/fire/projectiles/morale. Initial plans happen
for both armies on tick0; later decisions use deterministic ID-based phases over
50 ticks. Target death/escape/new rout can bring the next decision forward.
Charge/pursuit/recoil/reforming phases are protected from replanning. Immediate
movement, formation facing, skirmish execution and cavalry pursuit remain tick
based; playback speed/camera have no authority over them. `AiDecisionTicks` is
configurable. Counters separate evaluated decisions from actually changed orders.
`AiMilliseconds` measures scheduled planner work only, not the whole intent phase.

Armies choose `balanced`, `all_out_attack`, `hold_the_line`, or `skirmish`.
Infantry advances to effective range and forms line; long marches may use column.
Formation selection adds 20 s hysteresis. A reserve can wait until 75 s or a threat
within 190 m. Defensive objectives use clamped initial footprint anchors. Target
choices use authoritative perception, cached LOS and stable IDs. No hidden stat
bonus is granted to an AI army.

Explicit player Hold/Move/Attack/Disengage orders are pinned. Move/Hold remain
owned after arrival until the player releases autonomy; an invalid attack/charge/
pursuit releases back to AI if that army uses AI. Manual formation choices are
pinned until autonomy is explicitly restored. Routing/rallying still overrides
ordinary control. Selecting **Autonomous** releases the selected regiment only;
choosing an army strategy enables its unpinned regiments. Manual army mode stops
planning but leaves issued movement objectives intact. Explicit orders may accept
risks which the autonomous planner would avoid.

Personalities share one implementation and parameter policy. The original
methodical and stalwart secondary mechanical hooks (turn loss/shock/defensive
morale recovery) are retained; they are not extra independent trait systems.
Eight starting specializations multiply the same reload, movement, terrain,
cohesion, aura, impact and pursuit calculations. Existing caps remain: formation
time floor 50% of base, manoeuvre floor .4, quiet recovery cap 1.5×, aimed-fire
combined cap 1.5, strongest aura only (continuous rate cap .45/s), pursuit power
cap1.45× archetype/specialization, shared pursuit casualty budget and one impact
per charge. The Firebrand boost also incurs its actual disorder cost. No campaign
upgrades, levelling or progression are active.

Officer generation uses a separate specified SplitMix64 stream seeded by
`CommanderSeed` (default1729), not the combat seed. Rerolling cannot consume combat
random draws. Generated identity is preserved on reset and when changing the
combat seed; imported commanders validate against category, not faction. European
names use the existing fictional combinations; Haudenosaunee names use the nine
whole user-supplied names, with no fabricated surnames/ranks/syllables. Generation
algorithms/IDs differ from Python's MT19937-based generator; supplied officers
allow exact mechanical reference comparisons.

## Deliberate refinements and limits

The common Python policies/formulas are ported, with narrow tactical safeguards:

- Prepared frontal cavalry targets do not force a charge just because18 s elapsed;
  cavalry can flank/wait. Broken targets can prompt earlier commitment.
- Infantry gains column/line choice with20 s hysteresis and manual formation pins.
  Close exploitation uses existing ordinary melee through a short movement order;
  the deferred Python infantry bayonet-impact system is not silently implemented.
- Light troops may choose a useful nearby forest firing position, with a 30 s
  commitment, then use the Python bounded retreat/re-engagement cycle.
- Autonomous artillery filters obviously low nominal trajectories through dense
  allies, and its relocation candidates avoid friendly footprints too. This is
  not a predictor of scattered/bouncing future hits: friendly fire remains real.
  Player-designated shots remain literal and can hit friendly formations. After
  deployment the battery issues explicit FireAt, so limited turning can aim even
  when a relocation left the target outside its forward hemisphere; autonomous
  fire rechecks own/friendly perception on each firing opportunity.
- Missing targets are cleared. Without detected enemies an attacking regiment
  approaches last contact or the army centre; it does not use hidden enemy poses.
  Defending regiments keep their anchor. This avoids initial hidden-ridge inaction.
- Opportunity targeting keeps its 10 s lock/improvement margin; actual cavalry
  orders follow the selected opportunity. Target-change telemetry counts final
  chosen targets, not intermediate nearest-enemy candidates.

No pathfinder/army-wide synchronized manoeuvre planner was added. Local rectangle
steering may still be cornered; target persistence can retain a costly engagement;
artillery's eight-position search is limited; the nominal safety check cannot
prevent dispersion/ricochet friendly fire. Asymmetric maps, commander assignments
and stable update/RNG order can create deployment advantages. Completion is the
existing morale rule; an observation timeout is reported as inconclusive, never
as a fabricated victory.

## Live setup, controls and scenarios

The Godot mode selector defaults to **Player versus AI** (`ai-player`), opening
paused when selected through the UI. The **AI** button configures Blue/Red army
strategies, rerolls the selected officer or assigns a compatible personality/
specialization before the first tick, and releases the selected Blue regiment to
Autonomous/Hold. Start with Play/Space. After starting, officer edits lock, but
army direction and per-regiment orders remain available. Enemy regiments are
inspectable in AI scenarios; manual commands still control Blue only. Reset
preserves officer assignments and army setup. Replay keeps its existing path.

The inspector puts commander name/personality/specialization and current intention
near the top, with ownership, next decision, last threat ratio/score and actual
conditional effects below. Explanations come from the branch/score used by the
planner; no speculative rejected actions are calculated per rendered frame.
Existing selected-destination/target/F8 indicators are reused. Setup dialogs block
camera hotkeys; camera/input bindings remain unchanged.

| Scenario | Purpose |
|---|---|
| `ai-player` | Manual Blue against autonomous combined-arms Red |
| `ai-combined` | Fully autonomous twelve-regiment combined-arms battle |
| `ai-infantry` | Opposing infantry advance, form and exchange volleys |
| `ai-cavalry-reserve` | Cavalry waits/flanks behind an infantry engagement |
| `ai-exposed-flank` | Mounted exploitation of an exposed defender |
| `ai-forest` | Covered woodland skirmishers and heavy infantry |
| `ai-rifles` | Rifle stand-off versus advancing muskets |
| `ai-artillery` | Ridge-blocked battery relocates, deploys, fires |
| `ai-horse-artillery` | Field/horse battery approach and support |
| `ai-personalities` | Aggressive/cautious cavalry assignments |
| `ai-specializations` | Drillmaster and defensive infantry examples |

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --combat-scenario=ai-player --paused
bash tools/godot.sh -- --combat-scenario=ai-combined --live-speed=4
bash tools/dotnet.sh test godot/Simulation.Tests -c Release
.venv/bin/pytest -q
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release -- --combat-scenario ai-combined --duration 1200 --output benchmark-results/ai-battle.json
.venv/bin/python -m migration_tools.ai_reference
.venv/bin/python -m migration_tools.evaluate_ai --seeds 17 31 73 --swap
.venv/bin/python -m migration_tools.benchmark_ai --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --ai --output-dir benchmark-results/m5-gpu
bash tools/godot.sh --headless --script res://tests/test_ai.gd
```


## Verification results

397 standalone C# tests and 670 Python tests pass. 111 direct current-Python probes
cover factors, policies, preparation, ranges, skirmish/army decisions and target
locks. Native checks:21 AI,40 artillery,36 morale/cavalry,39 combat,39 movement,
58 camera,74 3D viewer,60 replay; the AI suite also runs in a real GPU window.
All twelve side-swapped complete battles finish; the visibility optimization
preserves their outcomes and all repeated benchmark checksums. Full measurements,
controlled personality observations, allocation costs, side-bias caveats and raw
artifact locations are in [MIGRATION.md](../MIGRATION.md) and
[PERFORMANCE.md](../PERFORMANCE.md).
