# The Defence of the Commonwealth — Stage 1 implementation

This is an authored **battlefield content pass**, based on the supplied Design
Reference v0.1, especially Sections 5 and 8. [Scoped source extract](COMMONWEALTH_STAGE1_REFERENCE.md).
It adds no campaign missions, recruitment, progression, economy, narrative events
or persistent roster. Existing Python combat and all nine prior native archetype
IDs/stats are retained. New content uses the same movement, weapons, formations,
terrain, morale, charges, projectiles and scheduled AI as the existing sandbox.

## Core roster

Four existing specialist profiles retain their IDs **and numeric balance**. Their
campaign-facing catalogue labels expose their intended roles; their old labels and
IDs remain usable by recordings and saved recipes. Eleven profiles are new, giving
20 sandbox archetypes including the five other generic/French profiles.

| Faction | Campaign unit | Stable archetype ID | Status and actual role |
|---|---|---|---|
| Commonwealth | Regular Infantry | `commonwealth_regulars` | New; 240 soldiers, dependable line fire, modest 1.04 discipline |
| Commonwealth | Citizen Militia | `commonwealth_militia` | New; 300 soldiers, poor drill/reload, conditional defensive shock resistance |
| Commonwealth | Scythemen | `commonwealth_scythemen` | New; 260 melee-only infantry, no firearm; strong close assault, poor discipline |
| Commonwealth | National Cavalry | `commonwealth_national_cavalry` | New; balanced 100-horse charge/melee profile |
| Commonwealth | Advance Guard Lancers | `commonwealth_uhlans` | Reused; 80 fast lancers, existing one-impact exploit and pursuit, weak prolonged melee |
| Commonwealth | Field Artillery | `commonwealth_field_artillery` | New; existing six-gun conventional ballistics plus physical close canister |
| Revolutionary Britain | Line Infantry | `revolutionary_line` | New; 220 soldiers, 10.8 s reload, flexible manoeuvre, ordinary melee |
| Revolutionary Britain | Experimental Rifle Corps | `revolutionary_rifles` | Reused; 140 soldiers, 235 m range, 22 s reload, aimed/skirmish fire |
| Haudenosaunee Confederacy | War Party | `haudenosaunee_skirmishers` | Reused; smaller 140-person expeditionary detachment, mobile open-ground harassment and existing woodland advantages |
| Prussia | Musketeers | `prussian_line` | Reused; existing cohesion-dependent drill, forest disadvantages |
| Prussia | Grenadiers | `prussian_grenadiers` | New; 200 elite assault infantry; no French prestige aura |
| Prussia | Cuirassiers | `prussian_cuirassiers` | New; heavy impact/melee, slow turning, difficult-ground penalties |
| Russia | Musketeers | `russian_musketeers` | New; higher morale/staying power, slower formation response |
| Russia | Grenadiers | `russian_grenadiers` | New; 220 resilient assault infantry, more melee shock and less drill |
| Russia | Cossacks | `russian_cossacks` | New; 80 fast light horse, pursuit/flank opportunities, weak frontal shock/melee |

Profiles live in `simulation_data/movement_archetypes.json`. `CampaignCore`,
`CampaignName`, `Role`, tags, faction, standard strength, allowed formations and
weapon data are ordinary serializable content. They contain no battle numbers,
recruitment costs or diplomacy. Faction describes identity; `Regiment.Army` is the
only coalition/allegiance boundary used by combat. Prussian and Russian units can
cooperate just as Commonwealth, British and Haudenosaunee units can.

The generic infantry/cavalry/artillery and French Royal Grenadiers/Horse Artillery
remain available. No additional proposed unit from the full 31-unit roster was
introduced. The old Python roster remains its original nine types; new native
recipes are not promised to load in Python, while old Python recipes/replays are
still supported in Godot.

## Small shared rule additions

**Melee-only infantry:** a weaponless assault profile can acquire enemies, receive
attack/charge orders and close into the existing infantry-charge/melee rules.
`CombatCapable` continues to mean ranged capability; the presentation receives a
separate attack-capability flag. No zero-range musket or fake volley is used.

**Role-based AI:** rifle/skirmish behaviour now uses profile roles. Assault infantry
recognize close-combat opportunities. Citizen militia prefers a cohesive defensive
firing line. Light cavalry avoids prepared infantry fronts even with an offensive
army objective. Light horse and the historical pursuit specialist can redirect
from an intact front to a nearby visible rout within 220 m, before committing to
a charge. Existing charge/pursuit commitment, target persistence and pinned player
orders still take precedence. No separate per-archetype AI or pathfinder exists.

**Militia defence:** while steady, stationary and cohesive in a holding line,
`DefensiveResolve=.82` feeds the common shock hook. Moving, changing formation or
losing the prepared state removes it. Slow turning, formation change and reload,
low discipline and weaker accuracy keep it distinct from professional infantry.

**Physical canister:** only the new Commonwealth Field Artillery automatically
selects canister when its target centre is within 95 m. Each operational gun emits
eight physical statistical shot groups through the existing swept formation and
terrain collision code. Groups spread by ±0.12 radians horizontally and ±0.6 m/s
vertically. Hits use 1–3 casualty potential times energy/density, 0.6 direct shock
and the existing casualty/morale/cohesion pipeline. A group stops at its first hit
or ground contact and cannot damage beyond its 105 m maximum swept path. It cannot
ricochet or penetrate multiple formations. Friendly fire remains enabled. Outside
95 m the unchanged solid-round-shot model is used. This is a bounded prototype of
canister, not hundreds of independently modelled pellets or a new ammunition UI.

## Historical cast and starting signatures

`simulation_data/commonwealth_commanders.json` contains the 14 authored definitions.
`HistoricalCommanderDefinition` owns stable definition ID, accurate display name,
structured alternative names, faction, personality, signature, role, category
eligibility, preferred battlefield-role tags, availability tags and notes. Preferred-role tags guide future assignment; compatible cross-role sandbox
choices remain allowed. `CommanderIdentity.DefinitionId` links a
battle instance to that definition. Historical officers are never randomly selected
from the procedural pool. Definitions and alternative names serialize without a
Godot dependency.

| Historical commander | Personality | Signature — implemented effects before existing global caps |
|---|---|---|
| Tadeusz Kościuszko | Stalwart | **Citizen’s Defence**: army headquarters, 180 m radius; cohesive citizen formations holding position take 15% less shock and receive up to 0.15 morale/s |
| Franciszek Ksawery Niesiołowski | Methodical | **Steady Volley**: up to 18% accuracy for stationary line infantry, scaling with cohesion 60–90 |
| Jan Henryk Dąbrowski | Methodical | **Flexible Manoeuvres**: formation time ×0.85, manoeuvre disorder ×0.78, cohesion recovery ×1.18 |
| Antoni Madaliński | Aggressive | **Relentless Pursuit**: pursuit ×1.22, contact gap ×1.12, pursuit congestion disorder ×0.80; prepared frontal combat ×0.90; recognizes local rout opportunities |
| Jakub Jasiński | Aggressive | **Revolutionary Fervour**: locally outnumbered citizen troops within 130 m take 18% less direct shock, 12% less casualty morale loss and gain 10% melee power; remains useful while shaken/wavering |
| Franciszek Ksawery Łaźniński | Cautious | **Cavalry Reserve**: resting/reforming cohesion recovery ×1.25, additional 0.25 fatigue/s recovery while resting, cooldown ×0.85, genuine clearance/reform time ×0.80 |
| Edward Marcus Despard | Stalwart | **Improvised Defences**: prepared shock ×0.88 and artillery limber/deployment time ×0.85 |
| Lord Edward FitzGerald | Stalwart | **Brotherhood of Nations**: visible steady allies of different factions within 110 m give both sides of the pair cohesion recovery ×1.12 and up to 0.12 morale/s |
| Joseph Louis Cook (Akiatonharónkwen) | Opportunistic | **Veteran of Two Worlds**: a nearby mixed Haudenosaunee/conventional pair receives cohesion recovery ×1.15, manoeuvre disorder ×0.90 and up to 0.12 morale/s |
| Friedrich Wilhelm von Bülow | Methodical | **Disciplined Skirmishers**: infantry formation time ×0.80, manoeuvre disorder ×0.82, recovery ×1.12; useful without Fusiliers |
| Gebhard Leberecht von Blücher | Aggressive | **Vorwärts!**: common aggressive decisions; unprepared impact shock ×1.15, with additional 0.10 charging fatigue/s and up to 2 impact cohesion loss |
| Pyotr Bagration | Aggressive | **Vanguard Assault**: attack/advance speed ×1.08, manoeuvre disorder ×0.88, moving unprepared charge shock ×1.08 |
| Matvei Platov | Opportunistic | **Cossack Screen**: light-horse speed ×1.06, pursuit ×1.15, pursuit disorder ×0.90, visibility opacity ×0.90; existing opportunity and light-cavalry AI |
| Alexander Suvorov | Aggressive | **Speed and Shock**: default offensive army objective; attacking infantry within 220 m of headquarters gain movement ×1.06, shock ×0.92 and cohesion recovery ×1.08 |

Kościuszko and Suvorov occupy **army command assignments**, not regiment slots.
Headquarters defaults to the army's deployment centroid and can be set explicitly
in scenario data. It remains fixed during the battle; no command hierarchy or
moving general entity is simulated. Choosing Suvorov in the setup offers an
offensive objective; later explicit army objectives and regiment orders remain
binding. An explicitly supplied scenario strategy is respected.

Historical identity is unique across both armies and both command scopes, even
when instance IDs differ. Canonical names/personality/signature cannot be forged
by editing a recipe. Generated officers reserve names/aliases of already assigned
historical people. An existing generic officer using a historical name/alias must
be rerolled before assigning that person. Generic commander generation, curated
Haudenosaunee names and ordinary specializations otherwise remain unchanged.

### Stacking and activation

Signatures feed the existing commander hooks rather than implementing parallel
combat. Formation-time floors, recovery limits, charge-shock limits and the existing
pursuit cap remain authoritative; the table lists raw modifiers, not a promise
that a capped Uhlan/Cossack gets every percentage again. Repeated charge orders
cannot reset impact locks, separation requirements or cooldowns.

Mixed-faction and headquarters effects refresh every five fixed ticks (0.5 s),
using existing spatial queries. Coordination uses the strongest applicable source,
not a sum over nearby officers. The same army/visible/range/state checks apply in
headless execution. Jasiński's local force count excludes routed enemies. These
are bounded conditional effects, not faction-wide or named-build bonuses.

Inspector text reports actual conditional activation. No fortification, engineer,
Fusilier or strategic scouting benefit is labelled active. Despard's construction
and Kościuszko's fortification extensions, and future campaign recruitment/rewards,
remain future-only. Jasiński's alternate-history survival and Cook's curated name
are explicit metadata.

## Custom battle and laboratory use

From the repository root:

```bash
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh
```

1. Choose **Custom Battle**, then **+ Add units…**. Combine faction and unit-category
   filters; inspect strength, speed, range, reload, formations and abilities.
2. Turn off symmetric rosters to create different coalitions. Faction never locks
   a unit to Blue or Red. Set either or both armies to AI for PvAI/AIvAI.
3. Load a `Commonwealth lab …` preset or deploy your own roster. In the existing
   **AI** dialog, select a regiment and assign a compatible historical officer,
   inspect the signature, or reroll a generic officer. Select army commanders
   separately. Already used historical identities are unavailable.
4. Assignments lock after the first tick. Save/reload the ordinary custom recipe
   during deployment. `definition_id`, `nation` and `army_commanders` are optional
   version-1 extensions; absent fields preserve old recipes.
5. Start battle. All existing camera, facing ghosts, nominal range indicators,
   selection, 2D/3D current-battle switching and Python replay controls remain.

Four custom deployment presets are bundled: `commonwealth_lab_border`,
`commonwealth_lab_forest_allies`, `commonwealth_lab_russian`,
`commonwealth_lab_coalition`. These are laboratories, **not** the six campaign
missions. The live scenario selector also offers 54 controlled roster, terrain,
cavalry, historical signature, canister and combined-arms scenarios. All work with
the ordinary standalone runner:

```bash
bash tools/dotnet.sh build godot/Simulation.Runner -c Release
bash tools/dotnet.sh godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll \
  --combat-scenario commonwealth-battle-coalition --seed 17 \
  --output /tmp/commonwealth-battle.json
bash tools/godot.sh -- --live --combat-scenario=commonwealth-battle-coalition
```

New 3D silhouettes reuse the mesh kit and batching: scythes, heavy cuirassier
breastplates, light mounted lances, grenadier headwear and faction colour profiles.
No individual soldier AI/physics or new rendering technology was added.

## Automated evaluation commands

```bash
bash tools/dotnet.sh test godot/Simulation.Tests
.venv/bin/python -m pytest -q
bash tools/godot.sh --headless --script tests/test_commonwealth.gd
.venv/bin/python -m migration_tools.evaluate_commonwealth \
  --suite battles --seeds 17 31 73 --swap
.venv/bin/python -m migration_tools.evaluate_commonwealth \
  --suite roster --seeds 17 31 --output benchmark-results/commonwealth-stage1-roster.json
.venv/bin/python -m migration_tools.evaluate_commonwealth \
  --suite commanders --seeds 17 31 --output benchmark-results/commonwealth-stage1-commanders.json
.venv/bin/python -m migration_tools.benchmark_ai --commonwealth --repeats 3 \
  --output benchmark-results/commonwealth-stage1-headless.json
.venv/bin/python -m migration_tools.benchmark_live --commonwealth --frames 600 \
  --output-dir benchmark-results/commonwealth-stage1-rendering
```

`--headless` on the last command validates presentation work but is **not a GPU FPS
measurement**. Tests can set `XDG_DATA_HOME`/`XDG_CONFIG_HOME` to repository-local
`.tools/godot-user`/`.tools/godot-config` where user directories are restricted.
The .NET test runner requires local loopback access.

The evaluation tools preserve seeds, side-swap deployments/terrain/headquarters,
report participation and expose timeouts honestly. Generic commander controls keep
the authored personality and use the existing Inspirer specialization; they are
not pure isolated signature measurements. Direct unit tests isolate activation,
numerical factors, caps, uniqueness, input priority and repeatability. No final
recruitment costs or economic balance are invented.

## Validation and balance results

- **512 .NET tests passed**, including all existing movement, combat, morale,
  artillery, specialist and Python-oracle regressions. Thirty new cases cover core
  content, historical signatures, uniqueness/aliases, local support, live-capability
  boundaries, physical canister, recipe round trips and determinism.
- **674 Python tests passed** in the complete final suite, including the two new
  laboratory side-swap checks. Shared-profile comparisons still verify
  every original Python archetype; extra native-only profiles are explicitly
  distinguished rather than deleting or weakening the old comparisons.
- Godot .NET project builds without warnings/errors. The **31 new integration
  checks pass headlessly and with real OpenGL rendering**. Existing checks pass:
  tactical controls 42, dynamics 36, shared 2D/3D views 22, custom sandbox 41,
  AI/commanders 21, artillery/specialists 40 and main menu 6. Python regressions
  also exercise camera, replay, live movement, combat and terrain contracts.
- Screenshot inspection checked the faction/category picker, fixed Add-button
  footer, readable historical signatures, separate army leaders and 3D coalition
  formations. Existing camera scripts and authoritative Python gameplay were not
  modified.

### Repeated comparisons

`commonwealth-stage1-final-evaluation.json` records 272 fixed-seed laboratory runs,
including opposite deployments and generic-commander controls. Twenty isolated
runs hit the explicit 600 s limit and remain **inconclusive**, not victories.
Deep woodland and isolated cavalry/defender situations can still produce long
standoffs. Side-swap validation mirrors scheduled orders as well as unit positions,
terrain and headquarters.

Representative observations (seeds 17/31 unless stated):

- Scythemen against prepared musketeers lost, inflicting only 1 casualty before
  collapse; against a wavering/disorganized target they won, inflicting 42–44
  casualties in about 57 s. They fired no volleys in either case.
- War Parties in the open inflicted 19 casualties before losing to the much larger
  regular regiment; in woodland they won the tested duels, inflicting 130–144.
  Open-ground movement, harassment and disengagement still function; this is not
  a claim that a small detachment should win an unsupported line duel.
- Prussian musketeers beat Commonwealth regulars in the controlled line duel
  (about 210–219 s). Russian musketeers' staying power also mattered. British line
  infantry traded smaller size and weaker melee for quicker volleys/manoeuvre;
  it was not universally superior to Commonwealth regulars.
- Prepared infantry repelled the frontal National Cavalry, Cuirassier and Cossack
  probes. Strong initial-impact profiles did not bypass readiness or create
  repeated impacts. Light horse and lancers remain better in their intended
  exploitation roles.
- Niesiołowski's organized line inflicted 80 rather than 53 casualties in the seed-17
  generic-control comparison, although both lost to Prussian drill. Kościuszko's
  supported militia held about 186 s versus 141 s without the army support; it
  incurred more casualties by staying in the fight, and still lost.
- Despard's deployment advantage changed the seed-17 battery probe from a defeat
  to a victory (76 s, 80 inflicted versus 85 s, 55 inflicted). Bülow's manoeuvre
  probe finished around 302 s versus 314 s for its control. Madaliński and Platov
  pursued and destroyed the initial routed target sooner; the fresh prepared
  enemy reserve remained dangerous. Blücher's conditional shock comes with real
  fatigue/disorder costs and does not always improve the final casualty ratio.
- Some support/recovery signatures barely change an individual duel's winner.
  Direct numeric tests establish their conditional effects independently of RNG
  and generic Inspirer support; they are not presented as universal win bonuses.

The final combined-arms report (`commonwealth-stage1-battles.json`) includes seeds
17, 31 and 73 in both orientations: **24/24 concluded**, with volleys, physical
artillery and cavalry activity. The results below are laboratory compositions,
not equal-cost or balanced campaign missions.

| Laboratory | Completed | Duration range (simulated seconds) | Commonwealth-coalition wins |
|---|---:|---:|---:|

| border | 6/6 | 146.0–211.5 | 0/6 |
| coalition | 6/6 | 278.1–392.4 | 0/6 |
| forest-allies | 6/6 | 282.2–314.8 | 0/6 |
| russian | 6/6 | 202.8–458.4 | 2/6 |

The Prussian/mixed opponents dominate these fixed compositions. This is a force
valuation and encounter-authoring concern for Stage 2, not proof of equal-value
faction balance: militia, detachments, heavy cavalry and artillery have no final
cost model. No sweeping buff was applied to make the tables look even. A regiment
listed as never inflicting damage may have been killed during its approach; that
metric is not automatically evidence of idle AI.

### Standalone simulation performance

Release .NET 10, three repeats per size, 100 warm-up ticks + 600 measured ticks
(60 simulated seconds), fixed 0.1 s timestep. These are the flat mixed-roster
`benchmark-commonwealth-*` cases with authored officers and headquarters. They
include infantry, cavalry, physical artillery, morale and scheduled AI.

| Regiments | Mean tick (ms) | 95th percentile (ms) | Ticks / wall second | Allocated bytes / tick | Visibility calculations (whole run) |
|---|---:|---:|---:|---:|---:|
| 12 | 0.270 | 0.288 | 3,697 | 73,545 | 9,454 |
| 24 | 0.532 | 0.582 | 1,877 | 146,167 | 20,487 |
| 36 | 0.845 | 0.896 | 1,183 | 235,944 | 32,607 |
| 60 | 1.687 | 2.205 | 593 | 432,703 | 57,200 |

The exact unchanged legacy `benchmark-ai-*` workload was also measured after the
change (three repeats). Its mean ticks were 0.398 / 0.797 / 1.284 / 2.348 ms for
12 / 24 / 36 / 60, compared with the pre-change single-run 0.492 / 0.863 / 1.385 /
2.581 ms baseline. No slowdown was measured; differing repeat counts and machine
variation do not establish an optimization speedup. The new workload is different
and its faster timings are not a general engine-performance comparison. All three
repeated checksums agreed per workload. Allocations remain a future profiling
opportunity; this pass did not add a new framework or new dependency.

### Rendered viewer performance

Actual Godot 4.7.2 .NET/OpenGL compatibility on **NVIDIA GTX 1080**, 1280×800,
perspective camera, shadows, 32 decorative figures/regiment, 600 measured frames
after 60 warm-up frames, live playback at **4×**. These are full viewer frame times,
including live updates, not pure GPU-kernel or standalone simulation timings.

| Regiments | Mean frame (ms) | 95th percentile (ms) | Approx. average FPS | Visible figures at measurement end |
|---|---:|---:|---:|---:|
| 12 | 7.02 | 6.97 | 142 | 307 |
| 24 | 7.25 | 9.45 | 138 | 618 |
| 36 | 7.92 | 12.19 | 126 | 937 |
| 60 | 13.09 | 21.43 | 76 | 1511 |

Terrain was built once per load, snapshot file cache stayed empty and retained
simulation debt remained below one fixed tick. Shots, impacts, routs and pursuit
occurred in the rendered cases. The 60-unit case has occasional ~21 ms frames;
this is responsive prototype performance, not a guarantee of steady high FPS on
other hardware or dense forests. Detailed results are in
`benchmark-results/commonwealth-stage1-rendering/`. Dedicated headless timings are
in `commonwealth-stage1-headless.json`; the benchmark rows inside the broad
comparison report are smoke measurements during concurrent tests and are not used
as the performance baseline.

## Known limits and Stage 2 dependencies

- The 54 scenarios and four presets are battle laboratories. None is a campaign
  mission, narrative event, unlock, persistent roster, recruitment cost or reward.
- Force valuation, campaign budgets and authored deployments still need design.
  Prussian drill is strong in orderly line duels; small detachments and unsupported
  Scythemen should not be assessed as equal-cost line regiments.
- Fixed headquarters are deliberately simple. There is no moving general,
  command hierarchy, fortification construction or engineer simulation.
- Some isolated forest/cavalry tests can reach their explicit timeout. Existing
  local AI has no full army manoeuvre planner; ranged visibility and prepared
  defenders can cause standoffs. Cavalry may die during an approach without
  landing an impact. These limitations are reported rather than hidden by forced
  victories or faction bonuses.
- Historical signature controls retain the personality and use generic Inspirer;
  winner comparisons do not isolate every modifier. Direct tests provide exact
  conditional assertions. Balance is provisional, with no claim of historic
  numerical accuracy or final economic equivalence.
- Canister uses eight grouped projectiles per gun, automatic range selection and
  existing rendering. It is not a detailed ammunition/supply system.
- New native-only archetypes/signatures are not backported into Python. Old
  Python configurations, recordings, names and simulator behaviour remain intact.
- Future campaign work should consume the stable IDs/tags, define force budgets,
  implement persistence/recruitment and progression separately, and then author
  the six encounters. Engineering, Fusiliers, Scouts and additional historical
  characters remain future content, not falsely active abilities.
