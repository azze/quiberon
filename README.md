# Quiberon: Battlefield Prototype

The native [army director and mounted reserves](godot/ARMY_DIRECTOR.md) coordinate regimental roles, prepare firing formations, and keep cavalry with the infantry until useful opportunities appear. The guide includes comparison results and a live test scenario.

Native tactical AI now supports shared mission assignments, local support assessment,
and stable infantry firing-position selection. See [tactical decisions and test scenarios](godot/TACTICAL_DECISIONS.md).

A playable Python real-time tactics experiment, set after an imagined French victory at Quiberon Bay in 1759. Blue and red are sandbox allegiances: mixed historical and alternate-history regiments can fight on either side. A five-battle campaign adds persistent armies and commander upgrades alongside the independent sandbox.


The Godot/C# version now also supports complete autonomous/custom battles, manual
3D deployment, named commanders with twelve configurable acquired abilities,
infantry bayonet charges and detailed battle results. Launch it with
`bash tools/dotnet.sh build godot/Quiberon.sln -m:1` then `bash tools/godot.sh`.
See [the native sandbox guide](godot/SANDBOX.md). Campaign progression remains in
Python.

## Install and launch

Python **3.11+**, Linux or Windows. Pygame Community Edition supplies the `pygame` import; do not install both Pygame distributions in the same environment.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python main.py  # opens Custom Battle / New Campaign / Continue menu
```

On Windows, activate with `.venv\Scripts\activate` (cmd) or `.venv\Scripts\Activate.ps1` (PowerShell). The remaining commands are the same.

```bash
python main.py --scenario movement
python main.py --scenario standard --seed 7
python main.py --spectator --seed 7
pytest -q
python -m analysis.batch_simulation --runs 10 --seed 1 --duration 900 --output results.json
python -m analysis.batch_simulation --runs 3 --output results.csv
```

Installed entry points are `quiberon` and `quiberon-batch`. Batch runs never import or initialize Pygame. CSV output has a companion `.summary.json`. A duration limit records `timeout`, never an invented winner. `--spectator` gives both armies the same strategic AI; without `--config`, batches retain the legacy standard scenario. The menu uses the new deployment generator, so save a recipe and use `--config` to reproduce a GUI battle.

For machines without a display, graphical startup can be checked with:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python main.py --frames 30
```

## Custom battle setup and deployment

Launch `python main.py` and choose **Custom Battle** to open setup. Use Previous/Next preset to choose a conventional or specialist matchup, then edit it:

1. Click **+ Add** in an army panel, filter by regiment type, select a unit, choose its amount, and confirm **Add regiments**. Cancelling leaves the composition unchanged. Army panels show only types currently included; zero counts disappear. Click an existing unit name or **…** to inspect/edit existing counts. Filter infantry/cavalry/artillery, inspect strength, range, reload, speed, turn rate, morale, discipline, accuracy/melee multipliers, formations and traits, then use the amount controls in Add mode, or edit existing counts in inspection mode. The compact army lists also show basic stats; Up/Down and the mouse wheel scroll them. Uncheck **Symmetric armies** to edit red independently. Defaults remain 4 generic infantry, 1 cavalry and 1 battery per side. Each archetype allows 0–12, each army needs at least one regiment, and the default combined cap is 48. Factions can be mixed freely.
2. Choose Small (600 × 400 m), Medium (1,000 × 600 m), Large (1,600 × 1,000 m), **Huge (2,400 × 1,500 m)**, **Epic (3,200 × 2,000 m)** or **Vast (4,800 × 3,000 m)**. Unit footprints, speeds and ranges retain their world-space values; the camera initially fits the field. Larger maps therefore have longer approach phases. Cosmetic terrain painting uses a bounded-resolution cache on large maps; authoritative terrain queries are unchanged.
3. Enter an integer seed, or leave blank to generate one. Click fields to type; Tab switches fields, Ctrl+A selects their text, and Backspace edits. **New seed** fills a fresh value. **AI controls both armies** enables hands-off experiments.
4. Click **Deploy armies**. Simulation time stays at zero. Infantry packs into the centre, cavalry on flanks and batteries behind infantry. Overcrowded armies produce an error instead of overlapping spawns; Small has only 12 automatic deployment slots per army.
5. Left-click a blue regiment, then **hold right mouse at its new position and drag toward its intended facing**. Release to place it. The ghost footprint and arrow show the exact proposed position and heading. Right-click without dragging keeps its current facing; right-drag from its centre rotates it in place. Left-drag placement and Q/E rotation by 15° also remain available. L/C/K selects supported line/column/skirmish formations immediately; H/A/T/R/S sets hold/advance/attack-nearest/reserve/skirmish. Backspace resets the selected regiment; **Reset all** restores automatic deployments. Red deployment is automatic in the GUI.
6. Green ghost outlines indicate valid placement; red indicates invalid. Invalid edits retain the last valid position. The entire footprint must stay inside its own zone, with no starting overlaps. If a reset position is occupied, move the obstructing regiment or use Reset all. For a valid imported layout denser than the automatic grid, reset restores that imported layout.
7. Click **Start battle** or press Enter. Normal combat controls then apply. Escape cancels an active placement gesture; otherwise it returns to setup.

**F5 Restart**, **F6 New seed**, and **F7 Edit setup** (also clickable during or after combat) restore the initial recipe, preserve deployment with a new seed, or return to setup with the recipe loaded. Restart clears all simulation state and queued commands. It does not replay commands issued during the previous battle; reproducibility requires the same subsequent commands at the same ticks. Editing counts or field size discards manual placement and regenerates it on the next deployment. Seed changes retain placements.

**Save JSON / Load JSON** use the editable path in setup (default `battle_config.json`). Deployment Save/Load use that same path and include manual positions, facings, formations, initial orders and the actual seed. Saving a seedless recipe resolves its seed. Loading does not start combat. Files contain starting configuration, not mid-battle state. Existing files at that path are overwritten only when Save is clicked.

```bash
python main.py --preset "Cavalry Assault" --seed 42
python main.py --config battle_config.json
python main.py --config battle_config.json --quick  # exact saved deployment, skip menus
python main.py --preset "Artillery Duel" --quick --seed 42
python -m analysis.batch_simulation --config battle_config.json --runs 5 --duration 1200 --output results.json
```

Batch `--config` uses the saved seed for its first run and increments it for later runs; `--seed` overrides the starting seed. Legacy direct launches (`--scenario standard` and `--scenario movement`) still work and support F5/F6/F7. Editing a legacy scenario opens the balanced setup preset, since the one-army movement demo is not a valid two-army battle recipe.

## Distinctive regiments

All nine archetypes are available in the setup roster. Specialists have distinct letter symbols and accents; loose formations use cosmetic dotted subgroups inside their single simulated footprint. The selected panel describes the trait, and the event log signals its use. Generic I/C/A remain available.

| Symbol / stable ID | Role and trait | Counter or weakness |
| --- | --- | --- |
| P / `prussian_line` | **Prussian Line Infantry**: high-cohesion drill accelerates reloads and formation changes, and reduces manoeuvre disruption | Forests, broken cohesion, flanks and isolation |
| W / `haudenosaunee_skirmishers` | **Haudenosaunee Woodland Skirmishers**: forest fire and ambush melee, mobility/concealment, loose formation and bounded disengagement | Small volleys and weak melee in the open; exposed cavalry |
| G / `royal_grenadiers` | **French Royal Grenadiers**: morale resistance, stronger melee, capped Royal Prestige support within 125 m while steady | Only 180 troops, slow movement, attritional artillery fire |
| U / `commonwealth_uhlans` | **Polish-Lithuanian Uhlans**: fast flank/pursuit cavalry; stronger charges against wavering, routing or disordered targets | Only 80 riders, weak sustained melee, prepared fronts, difficult terrain |
| R / `revolutionary_rifles` | **British Revolutionary Riflemen**: 235 m range; stationary, cohesive, unobscured Aimed Fire | 22 s reload, low shot volume, close massed fire and cavalry |
| H / `french_horse_artillery` | **French Horse Artillery**: rapid support, 1 s limber / 3 s setup | 360 m range, 65% initial shot energy, exposed while moving |

**K** requests loose skirmish formation for Woodland Skirmishers and Riflemen. It is 78 × 28 m, more manoeuvrable, with reduced shot volume and incoming fire vulnerability but poor melee power. Woodland Skirmishers support column/skirmish; Riflemen also support line. Unsupported live formation requests are ignored; deployment edits explain the rejection. The dots are visual markers, not individual soldier AI.

**S** enables skirmish behaviour. Close, stronger visible threats trigger a six-second withdrawal budget plus up to four seconds for turning, followed by ten seconds of committed re-engagement before another withdrawal. Units fire when their facing, range and sight line permit it. Move, Hold and explicit Attack do not invoke automatic skirmish retreat. AI-controlled light infantry normally receives skirmish orders. There is no global escape planner: cavalry, corners and congestion can still catch them. An advance order still follows ordinary advance rules rather than automatically becoming skirmish.

Batteries initially start deployed. Subsequent movement requires limbering, and stopping requires setup before firing: standard artillery takes 3 s / 8 s, horse artillery 1 s / 3 s. Target diagnostics explain this delay. Cannonball trajectories, terrain collision and friendly fire remain physical; lighter horse-artillery shots start with lower energy. Restart resets all timers, trait signals and metrics.

Seven editable specialist presets join the original five: **Prussian Drill**, **Woodland Encounter**, **Open Ground**, **The Royal Guard**, **Cavalry Breakthrough**, **Rifles and Muskets**, **Mobile Artillery**.

```bash
python main.py --preset "Woodland Encounter" --seed 17
python main.py --preset "Mobile Artillery" --quick --spectator --seed 17
pytest tests/test_archetypes.py tests/test_archetype_viewer.py -q
python -m analysis.batch_simulation --preset "Prussian Drill" --spectator --runs 3 --duration 600 --output results-prussian.csv
python -m analysis.matchups --runs 2 --duration 600 --output results-matchups.json
python -m analysis.matchups --preset "Woodland Encounter" --preset "Open Ground" --runs 3 --seed 10 --duration 600 --output results-woods.json
```

The matchup tool runs every selected preset from both sides for each seed, mirroring regiments and initial orders while keeping the same terrain within each pair. It reports timeouts honestly. JSON and the ordinary batch CSV now include per-side/archetype casualty, volley, range, shock, charge, rout-attribution, activity, terrain, cohesion and trait-signal metrics. See [analysis/balance_notes.md](analysis/balance_notes.md) for measured early results and caveats; these units are not yet balanced.

Python recipes can use `ArmyConfig(0, 0, 0, specialists=(("prussian_line", 3), ("royal_grenadiers", 1)))` or `army.with_count("revolutionary_rifles", 2)`. `Regiment(..., archetype_id="prussian_line")` also works headlessly. Traits and baseline stats live in [simulation/archetypes.py](simulation/archetypes.py); no new dependencies, campaign progression, recruitment budget or national restrictions are introduced.

## Hills, forests and terrain presets

Choose one of the six terrain buttons in setup before deploying:

| Preset | Battlefield |
| --- | --- |
| Open Field | Original flat map, no vegetation; default for old saves and legacy scenarios |
| Central Hill | A fixed broad 25 m hill in the centre |
| Rolling Hills | Seeded smooth hills and a shallow valley |
| Wooded Battlefield | Seeded light and dense elliptical forest regions on flat ground |
| Mixed Terrain | Rolling elevation plus scattered forests |
| Ridge Defence | A fixed 32 m ridge toward red's side |

Terrain features retain fixed metre-sized radii and heights; larger fields gain more features. Mixed Terrain has 2 hills / 2 forests on Small, 5 / 4 on Medium, 12 / 12 on Large, and 125 / 100 on Vast. Rolling hill radii stay 70–130 × 72–132 m at every size; forest sizes use the same fixed catalogue. Central hills and defending-side ridge segments repeat on larger maps. Unit sizes and weapon ranges remain unchanged. All terrain remains traversable, with terrain-aware automatic deployment.

```bash
python main.py --terrain "Mixed Terrain" --terrain-seed 17 --seed 42
python main.py --terrain "Ridge Defence" --quick --seed 42
python main.py --config battle_config.json --quick
pytest tests/test_terrain.py -q
```

**Regenerate map** creates a new terrain seed and regenerates automatic deployment. Central Hill and Ridge Defence have fixed geometry; regeneration changes their seed metadata but not their shape. Other presets use procedural variation. The first generated map uses the combat seed unless a terrain seed is supplied. Thereafter Save/Load, F5 restart and F6 rematch preserve its explicit feature geometry: F6 changes only combat randomness. Editing the combat seed in a loaded setup also preserves the map. Changing terrain preset, field size, or explicitly using CLI `--terrain`/`--terrain-seed` rebuilds terrain and automatic placement. Older version-1 JSON files without terrain load as Open Field.

**F2** toggles cached elevation contours in deployment and combat. **F3** adds cursor elevation, slope and forest density; selected terrain speed/cohesion loss; and LOS lines (green clear, amber partly obscured, red hidden). Purple waypoints show a local terrain detour; cyan waypoints remain friendly-unit avoidance. Hills use continuous shading and 5 m contours; dark areas and cosmetic trees distinguish forests. Units are always drawn above terrain. This is not graphical fog of war: all unit symbols remain visible to the player, while combat and AI perception respect terrain.

Terrain effects:

- Uphill travel slows all troops, especially guns. Gentle downhill travel gains at most 12%; steep descents slow troops and disrupt cohesion. Terrain speed is bounded to at least 20% before other movement penalties.
- At full-density forest cover, line infantry loses up to 35% speed, cavalry 65%, guns 75%. Infantry column reduces forest speed/cohesion penalties to 55% of the line penalty. Footprint sampling makes entry/exit gradual.
- Disruption depends on actual distance travelled and slope/vegetation. Stationary troops do not lose cohesion from terrain and recover through the existing rules. Terrain causes no direct morale shock.
- Ridges block direct musket fire. Vegetation accumulates along the actual sight line: edge troops are easier to see than deeply concealed troops; nearby forest opponents can still engage. Partial concealment reduces accuracy. Wide formations also fire less effectively in woods.
- Uphill melee is disadvantaged geometrically. Forests and steep slopes sharply reduce cavalry charge impact; gentle downhill charges can benefit modestly. There is no generic elevation bonus to musket damage.
- Artillery still ignores direct LOS for launching: actual cannonballs can clear or strike a ridge. Their heights are absolute world elevations, slopes affect bounces, and trees abstractly drain projectile energy below the canopy. Batteries in woods also suffer increased scatter. Friendly fire remains possible.
- AI targets must be spotted through terrain. Artillery can use allied spotting, and a live player-directed battery can bombard a hidden target. Infantry advances toward its last known target position rather than tracking unseen movement. There is no full scouting/search system.

Cavalry and guns can take one reasonably short, cheaper terrain detour; otherwise they march directly, keeping soft friendly collisions as a fallback. Guns may try a nearby clear firing position when a ridge blocks their own view. These are local heuristics: they cannot solve every forest maze, find a distant ridge crest, or predict a safe ballistic corridor. Some terrain/composition combinations can stall or run much longer than the intended battle duration. Use manual orders and deployment to explore these situations.

`simulation/terrain.py` owns the analytic surface, region queries, visibility and **TerrainRules** tuning defaults; `Rules.terrain` can override them headlessly. Saved recipes add `terrain_preset`, `terrain_seed`, and a `terrain` object with dimensions, metadata and explicit `hills` / `forests` arrays. A hill has `x`, `y`, `radius_x`, `radius_y`, `height`; a forest replaces `height` with `density` (0–1). Negative hill heights produce valleys. Feature centres must be inside the field, radii at least 1 m, heights within ±200 m, with at most 256 features of each kind. New hills may include `compact: true`; old hills without that flag remain Gaussian. Use Save to generate valid example files rather than hand-writing geometry.

```python
from scenarios.battle_config import BattleConfig
config = BattleConfig(seed=42, terrain_preset="Mixed Terrain", terrain_seed=17).prepared()
config.save("mixed_battle.json")
assert config.create_battle().terrain == config.new_seed().create_battle().terrain
```

```bash
python -m analysis.batch_simulation --config mixed_battle.json --runs 5 --duration 1200 --output results.json
```

Terrain ray sampling adds CPU cost. Sight results and terrain render geometry are cached; movement uses five footprint samples; cannonballs substep only on nonempty terrain maps. A 12-regiment Mixed Terrain smoke run simulated 120 seconds in about 16 seconds headlessly in this environment, with combat, routing and friendly fire observed. This is a small functional check, not a balance benchmark; larger armies and very narrow custom features cost more. Desktop and Windows playtesting remain outstanding.

## Headless recipes and JSON format

`scenarios/battle_config.py` is independent of Pygame. Frozen `BattleConfig`, `ArmyConfig` and `Placement` values are separate from live regiments:

```python
from scenarios.battle_config import ArmyConfig, BattleConfig

config = BattleConfig(
    width=1600, height=1000, seed=42, symmetric=False,
    blue=ArmyConfig(infantry=4, cavalry=0, artillery=2),
    red=ArmyConfig(infantry=2, cavalry=4, artillery=0),
).prepared()  # resolves seed and generates/validates placement once
config.save("battle_config.json")
battle = config.create_battle()  # always constructs fresh mutable regiments
battle.step()
restart = config.create_battle()
rematch = config.new_seed().create_battle()
```

The built-in [presets](scenarios/presets/) are examples of format version 1. A minimal recipe is:

```json
{
  "version": 1,
  "name": "Three infantry against cavalry",
  "width": 1000,
  "height": 600,
  "blue": {"infantry": 3, "cavalry": 0, "artillery": 0},
  "red": {"infantry": 0, "cavalry": 3, "artillery": 0},
  "symmetric": false,
  "seed": 42,
  "placements": []
}
```

An empty `placements` list requests automatic generation. Each explicit placement contains `id`, `army` (0/1), `kind` (`infantry`/`cavalry`/`artillery`), `position: [x,y]`, `facing` in radians, `formation` (`line`/`column`/`skirmish`, subject to archetype support), optional `archetype_id` (a stable roster ID), and `order: {kind, destination, target_id, facing}`. Missing archetype IDs retain the generic unit for `kind`. Army objects retain generic `infantry`, `cavalry`, `artillery` counts and optionally add `specialists: {"prussian_line": 2, "royal_grenadiers": 1}`; specialist counts are additional regiments, not category totals. Loaded archetype/category/formation/count mismatches are rejected. The optional order `facing` is a finite arrival angle for move/advance, defaulting to null in older files. Zero points right/east; positive angles turn toward increasing world y (down on screen). Null destinations/targets are permitted for autonomous orders. Move/defend need a destination; explicit targets must identify an enemy. All positions/orders are validated against the field; IDs are unique and counts must match the recipe. The data layer supports both armies' custom placements via `DeploymentSession.edit()` or immutable replacements.

Optional `ai_armies` defaults to `[1]`; use `[]` to preserve standing orders for both armies headlessly or `[0,1]` for spectator AI. AI-controlled armies may replace initial orders on tick zero and every five seconds. Optional `max_per_type` and `max_total` default to 12 and 48; JSON/API can raise them to 64 and 256. The chosen field must still fit all units. Accepted field dimensions are 300–5,000 × 240–3,000 m; seeds are signed 64-bit integers or null. Unknown versions, malformed files, nonfinite coordinates, invalid counts, overlapping placement and out-of-zone footprints are rejected. Configuration files are limited to 1 MB.

Recipes contain only existing unit baselines and default simulation rules, not custom weapon tuning or campaign data. Battle balance is not guaranteed for arbitrary compositions; artillery-only armies advance into range rather than waiting forever, but batteries otherwise retain the simple AI. Large armies cost more CPU because collision/combat checks remain roughly quadratic; high speed multipliers may run slower than requested. No global deployment optimization, red manual GUI editing, drag-and-drop target selection, or live-battle saves are included.

## Controls

| Input | Action |
| --- | --- |
| Left click | Select a blue regiment; click empty ground to deselect |
| Right click ground | Move; troops still automatically fire at valid targets |
| Hold right mouse on ground, drag, release | Move to the press location, then face toward the drag direction; ghost previews final footprint |
| Shift + right click ground | Advance and engage, stopping at musket range |
| Right click enemy | Attack that regiment; cavalry attempts contact |
| L / C / K | Supported infantry line / column / loose skirmish formation; normally seven simulated seconds |
| S | Skirmish-and-withdraw standing order for infantry; normal move/hold/attack orders override it |
| Ctrl + right-click enemy / B | Charge clicked enemy / current target; infantry rushes with bayonets, cavalry uses its charge |
| H / R / W | Hold / reserve / withdraw |
| Space | Pause; orders issued while paused apply on the next tick |
| 1 / 2 / 3 / 4 | 1× / 2× / 4× / 10× simulation speed |
| Arrow keys / wheel | Pan / zoom around cursor |
| F2 / F3 | Toggle elevation contours / debug terrain, LOS, targets, movement and AI |
| F5 / F6 / F7 | Restart / rematch with new seed / edit setup |
| Tab after battle | Show/hide the battle statistics report |
| Escape | Cancel active mouse gesture, otherwise deselect, then exit |

Move orders are issued on right-button release. Drags shorter than 8 screen pixels count as ordinary clicks. The green ghost shows the pending destination and forward arrow; after committing a facing, the selected unit's gold ghost retains that requested pose. Units move normally, then turn in place at their formation's normal turning rate within the existing 1 m arrival tolerance. They retain that heading until another order, routing, or army AI replanning interrupts it. Shift-drag also sets arrival facing, but advance orders may stop to engage before reaching the destination. Right-clicking an enemy still issues an immediate attack order. Escape or losing window focus cancels a pending gesture; releasing over the HUD cancels it. Move destinations near map edges are inset enough to keep the formation inside the field while turning. Deployment uses exact footprint/zone checks instead and rejects invalid position/facing pairs together.

The standard battle starts with advance orders for friendly infantry and an attack order for cavalry, so it can be watched without input. Enemy AI periodically updates its own orders. In spectator mode it also updates blue orders every five seconds.

Units use actual oriented rectangle footprints. I/C/A identify infantry/cavalry/artillery. Blue and red indicate army. White, yellow and turquoise bars show strength, morale and cohesion respectively. A pale line indicates facing. Gold outlines and destination markers show selection. A frontage-wide smoke plume and brief muzzle flashes mark firing; amber rings mark impacts. Orange formation outlines indicate friendly congestion. In debug mode, cyan lines/circles show active detours; select a regiment to see its overlap percentage, congestion speed multiplier and current speed. Cannonballs show a ground shadow and elevated bright point.

## Army AI strategies and close combat

Click each army's **AI: … >** button in setup to cycle **Balanced**, **All out attack**, **Hold the line**, and **Skirmish**. The choice applies only to AI-controlled armies; red is controlled by default, and the spectator checkbox enables blue. Strategies are independent of composition symmetry and survive save/load/restart. JSON stores `ai_strategies: ["balanced", "all_out_attack"]` in blue/red order; older files default to Balanced.

- **All out attack:** commit every infantry regiment without the usual reserve or automatic light-infantry withdrawal; cavalry attacks directly. Infantry still uses its ranged weapon when appropriate.
- **Hold the line:** infantry and light troops defend their deployment positions; cavalry counterattacks close threats and returns if pulled away.
- **Skirmish:** ranged infantry uses the existing bounded harassment/withdrawal behaviour rather than a static firing line. Cavalry supports with committed attacks.
- **Balanced:** conventional centre/reserve, specialist light-infantry behaviour, and a short cavalry flank approach.

All batteries now attempt to reach firing distance, even with infantry support. Deployment/limber timers and terrain searches remain active. Cavalry keeps a target and fixed approach waypoint, committing within 18 seconds (or sooner when close), rather than chasing a moving flank waypoint indefinitely. Explicit player attack orders retain their existing AI protection.

Melee uses a small 0.75 m formation-contact tolerance so collision separation does not interrupt fighting. Organized engagements stop at the formation edge and fight on the existing two-second cadence; cavalry pursuit follows the fleeing edge instead. Ranged fire is suspended throughout melee, including ticks between damage resolutions. Artillery crews use seeded fractional casualty resolution and reduced morale shock: their weak melee coefficient can no longer be cancelled by a mandatory one-kill-per-round minimum. Routing and withdrawal still permit escape; cavalry remains vulnerable to prepared infantry, disorder and supporting fire.

Routing troops inflict only 10% normal melee power **and morale shock**, with seeded fractional casualties instead of a guaranteed kill each exchange. Shaken/wavering troops use 70%/40%; rallying troops recover from 25% toward 60% as morale and cohesion recover. Broken troops cannot deliver cavalry charges or count as prepared infantry. Tune the melee state factors in `simulation/config.py`; `pytest -q tests/test_routing_melee.py tests/test_cavalry.py` exercises these restrictions and pursuit.

## Cavalry charge and pursuit

Use ordinary **Attack** orders: cavalry approaches normally, then automatically starts a charge within 100 m when aligned, sufficiently cohesive, with at least 12 m of clear run and suitable terrain. Charge speed accelerates at 2 m/s² toward 12 m/s (12.6 for Uhlans), before ordinary terrain/fatigue/morale effects. Turning is half normal rate. A close start, sharp turn, low cohesion, dense forest or steep ground produces weak momentum or prevents charging.

The first enemy contact consumes one charge and resolves casualties, cohesion disruption and morale shock. Momentum comes from actual speed, run distance, alignment, cohesion and terrain. Steady, stationary, cohesive infantry facing the charge resists strongly; flanks, wavering or broken formations are vulnerable. Failed prepared-front impacts can cause **recoil → reforming**. The original Attack order remains intact, and normal movement/turning governs retreat; enemy encirclement can prevent escape. A fresh full impact requires actual disengagement, clear space, reforming and the 20-second cooldown. Repeating an order or flickering contact cannot reset this lock.

Against routing targets, cavalry uses **pursuit**, with controlled two-second damage intervals and very limited scattered resistance. It follows the moving formation edge without the old stationary-melee stop/start loop. Several pursuers share diminishing returns and a per-target casualty cap, while retaining direction-sensitive friendly congestion. Pursuit ends when the target is lost/destroyed/withdrawn, establishes resistance, the cavalry becomes too tired/disorganized, or the player changes its order. Remaining in organized melee is risky: cavalry's sustained-melee factor is 0.8 and Uhlans retain their lower base melee coefficient.

**CH**, **P**, **RC** and **RF** labels indicate charging, pursuit, recoil and reforming. Charging units show an arrow; impacts show a golden expanding ring. Select cavalry for phase/speed/momentum; **F3** adds target, initiation range, run distance, readiness lock and last impact. Event logs report starts, impacts, aborts, recoils and pursuit. Batch/unit reports add initiations, impacts, impact casualties/momentum/shock, failures/aborts, pursuit seconds, pursuit casualties and pursuit losses. `charges` now counts impacts, rather than cooldown-triggered melee bonuses.

```bash
python main.py --scenario charge --seed 17          # prepared frontal defence
python main.py --scenario flank-charge --seed 17
python main.py --scenario cavalry-pursuit --seed 17
python -m analysis.cavalry_balance --runs 5 --output benchmark-results/cavalry-balance.json
pytest -q tests/test_cavalry.py tests/test_routing_melee.py
```

Balance runs use five seeds and side-swapped deployments by default; `--one-sided`, `--duration`, `--seed` and `--matchups` are available. Forest geometry is mirrored with the units. Existing setup presets and saved recipes need no changes. Tune `charge_*`, `pursuit_*` and `cavalry_melee_factor` in `simulation/config.py`, or archetype charge-speed/pursuit coefficients in `simulation/archetypes.py`. [DESIGN.md](DESIGN.md) explains the formulas and limitations; [PERFORMANCE.md](PERFORMANCE.md) records measured overhead.

## Infantry charges, woodland specialists and high ground

**Ctrl-right-click an enemy**, or press **B** for the selected unit's current target. Infantry closes for melee, withholds musket fire and accelerates into a **20% speed boost** inside 55 m when sufficiently cohesive. Contact produces one modest bayonet impact, then ordinary melee. Formation, fatigue, congestion, terrain and actual run distance still matter. Repeated orders cannot renew the impact without disengagement and recovery. Move/Hold/Attack interrupts the rush. Deployment also accepts B as a starting charge order; artillery cannot charge. CH arrows and the selected panel show the rush and momentum.

Woodland skirmishers now have improved observation and firing lanes **under forest cover**, alongside their existing mobility and concealment. Ridges remain opaque. Their current forest accuracy and ambush-melee bonuses make them woodland specialists; open-ground firepower stays unchanged. See the woodland balance section below for matched tests and tuning. Loose troops actively skirmishing at a safe distance in cover suffer less headcount-based outnumbering pressure, so one larger regiment no longer automatically panics a concealed detachment. Casualties, volleys and close combat retain their morale effects. Withdrawals include a bounded allowance for turning before the retreat budget.

High ground already helps through sight lines over lower terrain/friendly screens, slower and less cohesive uphill attackers, an uphill melee penalty, and elevated artillery trajectories that can clear some ridges. Weapon ranges stay fixed. F3 shows elevation/slope and LOS; F2 toggles contours.

```bash
python main.py --scenario bayonets --seed 17
python main.py --scenario woodland --seed 17
pytest -q tests/test_terrain_units_update.py
```

Tune `infantry_charge_*` and `skirmish_*` in `simulation/config.py`, and `forest_vision` / `forest_aim` in `simulation/archetypes.py`. New generated hills have smooth finite support for efficient spatial queries; old saved Gaussian hills keep their shape. Saved explicit maps retain their geometry: choose **Regenerate map** or change dimensions to use the new distribution. Dense Vast maps still have significant simulation costs; see [PERFORMANCE.md](PERFORMANCE.md).

## Range previews and battle statistics

Selecting a regiment shows its **gold maximum-range circle and forward firing arc** without enabling debug mode. Hover any active friendly/enemy regiment to preview its range in blue/red and see the distance in metres. Cavalry is labelled **melee only**. Hover tests use the same interpolated footprints as the drawn units. Range previews also work in deployment and while paused. These show geometric weapon reach, not guaranteed visibility or hits: terrain, screening formations, reload, setup and firing arcs still constrain attacks.

A **battle report opens automatically at battle end**. Army cards show starting strength, survivors, casualties, effective strength, destroyed units, rout transitions, rallies, withdrawals, volleys and charges. The table shows starting/remaining strength, casualties, losses caused, volleys, charges and final status for each regiment. Switch to **Archetypes** to aggregate units, filter by army, click numeric headings to sort descending, and use Previous/Next, the wheel or Page Up/Down for additional rows.

**Tab**, Escape or the Battlefield button hides the report for inspection; Tab or **Battle statistics** reopens it. In custom battles, F5/F6/F7 and the report buttons restart, rematch or edit setup; campaign reports instead provide Continue. Combat remains finished and orders cannot change the result. Restart clears the report. Stats are currently an in-app view; the existing headless batch tool remains the route for JSON/CSV output.

Casualties exclude troops merely routing or withdrawn; survivors include both. Initial per-regiment strength is captured when the battle is constructed, so pre-existing wounds are not counted as new losses. Rout/rally counters persist beyond the short event log and count transitions, including repeated breaks. “Caused” includes friendly fire and is not a count of enemy kills. The report builder is available headlessly as `analysis.battle_report.battle_report(battle)`.

## Selected-unit target indicators

Select a regiment to see its current enemy target without enabling F3. A **red reticle and outline**, connected to the selected unit by a dashed red line, mark its current aiming/pursuit target. The small upper-left panel names that enemy and explains whether the unit is reloading, out of range, outside its firing arc, or blocked by line of sight. A target marker does not by itself mean a shot is being fired.

If an explicit attack order names a different enemy, a **cyan diamond** marks that requested target. An explicit Attack order stays focused on its living target while approaching, turning or reloading; it does not opportunistically fire at another enemy. Automatic fallback resumes when that target is destroyed or withdrawn. Hold/advance orders retain automatic target selection. Cavalry markers indicate pursuit; contact combat can involve multiple enemies. Dead/withdrawn enemies and routing/rallying selected units have no current target marker. Paused orders take effect on the next simulation tick, so markers update after resuming. Cannonballs can still miss or hit intervening units; the marker identifies the intended target, not the eventual projectile victim.

A target inside weapon range can still be outside the firing arc, reloading, or changing formation. Infantry also needs line of sight. Explicit infantry attacks turn toward an in-range target and walk through friendly screens to open a firing lane, using the normal congestion penalties. The HUD names the blocking regiment. Enemy screens block infantry fire and movement; attack the screen or manoeuvre to expose the target behind it. This is local forward repositioning, not a full flanking/pathfinding system.

Friendly infantry screens restrict musket fire. Three samples across the firing frontage allow partial fire past a narrow screen; dense lines directly ahead block it, while loose skirmish screens attenuate it. Directly overlapping formations share outgoing frontage: three coincident dense lines each get roughly one third of a normal volley and its suppression effect. Targets in an overlapping group remain vulnerable, avoiding the old mutual immunity problem. High ground can clear a lower friendly screen when the sampled sight line passes above it. Terrain visibility, arc, range and reload rules still apply. Cannonballs retain their physical collisions and friendly fire.

Artillery does **not** require a clear direct firing lane and does not move forward merely to clear a friendly screen. It can fire over or toward intervening friendly/enemy formations, subject to range, facing, reload and formation-state limits. Cannonball height, swept collisions and bouncing determine what actually gets hit; firing over friends is not guaranteed safe. Infantry still requires a clear firing lane.

Player-issued attacks on a specific enemy are protected from army AI replanning until the target is gone or the player gives another order. This also applies when **AI controls both armies** is enabled. Initial recipe orders still follow the recipe's AI settings; only live player-issued targeted attacks receive this protection. Routing/rallying can still interrupt execution, and reload/formation timers are never bypassed by clicking a new target.

## Performance and smooth playback

The viewer interpolates regiment positions/facings and cannonball flight between fixed 0.1 s simulation ticks. The simulation continues to use exact current poses for movement, hits and targeting; clicking uses the displayed positions. Pausing shows the exact authoritative tick, and restart/deployment reset interpolation. Newly spawned or bouncing balls snap to their current pose rather than blending from an unrelated or pre-impact trajectory.

Rendering allows approximately **8 ms of simulation work per frame**, with a hard cap of four ticks. An indivisible tick can exceed the time budget. When overloaded, per-frame work stays bounded and all accumulated simulation time is retained. The HUD reports pending simulation seconds; reducing requested speed allows the backlog to drain rather than silently deleting it. It never skips tick IDs, enlarges the fixed timestep, or skips simulation events. The HUD shows requested and rolling achieved speed; **[limited; …s pending]** indicates that requested work is falling behind the frame budget. Matching seeds and commands at matching simulation ticks remain reproducible. Headless batches are not frame-budgeted.

Geometry uses bounded caches, a conservative spatial grid during fixed-geometry phases, and distance rejection before exact collision tests. Fire selection checks range and arc before expensive perception. Forest bounds and scalar terrain ray sampling reduce repeated work while preserving the same numerical results. Terrain view images (including contours) are reused until the camera, map, size or contour setting changes. Smoke buffers are reused and unused smoke layers are skipped.

The latest scaling pass preserves exact battle outcomes while reducing the measured 60-regiment Mixed Terrain tick from **156.87 to 41.60 ms**, and the 24-regiment tick from **15.19 to 8.48 ms**. These use a staged active-combat workload and are distinct from older timing samples below. Normal-speed 24/30-unit dummy-display tests run around 60 FPS on this machine; 60-unit mixed-terrain battles still have long frames and limited fast-forward. See [PERFORMANCE.md](PERFORMANCE.md) for complete methodology, before/after tables, environment, memory tradeoffs and remaining bottlenecks.

```bash
python -m analysis.scaling --frames 60 --output benchmark-results/before.json
python -m analysis.scaling --counts 24 --terrains "Mixed Terrain" --profile-dir benchmark-results/profiles --output benchmark-results/profile.json
python -m analysis.scaling --frames 60 --output benchmark-results/after.json --compare benchmark-results/before.json
python -m analysis.scaling --counts 24 --terrains "Mixed Terrain" --frames 120 --paced --speed 4 --output benchmark-results/viewer.json
```

The new tool writes JSON and companion CSV, measures headless/update/draw costs separately, and replays profiles outside the timing pass. Unpaced FPS is a throughput measurement; use `--paced` for actual-clock 60-FPS-capped playback checks. No AI frequency reduction, terrain approximation or combat balance change is used.

Legacy single-battle timings (including saved configurations) remain available with:

```bash
python -m analysis.performance --render-frames 300 --output results-performance.json
python -m analysis.performance --terrain "Mixed Terrain" --profile
python -m analysis.performance --config battle_config.json --warmup 500 --ticks 200
```

By default the tool compares 12-regiment Open Field and Mixed Terrain battles with seed 17, warms 800 ticks, and times the next 200. Optional rendering timings use the initial deployment at 1280 × 800 with SDL's dummy driver; cProfile samples subsequent simulation ticks. JSON includes mean/p95 tick timings and an exact-state checksum for same-runtime comparisons. Desktop drivers, battle phase, army size and machine load affect results; timings are not test assertions.

Measured in this environment, the optimization pass reduced Open Field from **2.5 to about 0.75 ms/tick**, Mixed Terrain from **12.6 to 7.0–7.4 ms/tick**, and warmed initial Mixed Terrain drawing from **2.8 to about 1.0 ms/frame**. At that revision both scenarios matched saved pre-optimization states after 1,000 ticks, including RNG, casualties, orders, events and projectiles. Subsequent combat fixes, including firing from overlapping formations, intentionally change battle outcomes. A three-second dummy-display Mixed Terrain run at requested 10× held about 62 FPS and achieved roughly 9× overall speed. These are representative local checks, not guarantees for every battle. Initial terrain painting, panning and individually expensive ticks can still hitch, especially with larger armies or narrow custom terrain.

## Movement demonstration

Run `python main.py --scenario movement`. It starts orders automatically; existing controls can override them. At 4× or 10× speed, the crossings become visible quickly:

- Top left: two lines marching through one another.
- Middle left: two columns passing in opposite directions.
- Top right: a short detour around a stationary line.
- Bottom right: three regiments crossing several screens, with adjacent screens ruling out a short detour.

Press **F3** and select a moving regiment to inspect congestion severity, speed multiplier, cohesion and its avoidance waypoint. All troops are friendly; combat and victory are disabled. Quiet units recover cohesion using the same rule as the battle simulation; recovery pauses during active crossings. Re-launch the scenario to reset it.

Additional traffic demonstrations use the ordinary battle controls:

```bash
python main.py --scenario crowded-line --seed 17
python main.py --scenario pursuit --seed 7
python main.py --scenario reinforcement
```

**Crowded line** starts three friendly lines on the same frontage: volleys share frontage immediately, then the lines gradually settle apart. **Pursuit** starts two Uhlan regiments chasing slower routing cavalry; stable approach offsets and compatible velocities keep their congestion small. **Reinforcement** sends a reserve through a narrow occupied frontage. F5 restarts each demonstration. These deliberately invalid overlapping starts are scripted scenarios, separate from the setup screen's validated deployment recipes.

Friendly overlap now uses actual movement directions and relative speed. Parallel infantry pays less than crossing infantry; similarly paced cavalry pursuing together pays very little. Opposing movement and passage through stationary troops retain substantial costs. After two seconds of substantial overlap at a stopping position, the lower-priority regiment searches for a nearby clear footprint and moves there normally. Explicit player Hold has priority, followed by other Hold/Reserve positions and existing occupants. Requested destinations remain intact; a small purple marker shows the accepted alternative. F3 adds the preferred position in gold, settling status, overlap duration and the last volley's usable frontage. Active attacks, skirmishing, withdrawal, routing and melee are excluded from settling. If no space exists, overlap remains passable and planning retries after a cooldown.

Tune `congestion_*`, `settling_*`, `pursuit_lane_spacing` and `friendly_*` in `simulation/config.py`; formation congestion profiles remain in `simulation/formations.py`. See [DESIGN.md](DESIGN.md) for the formula and stopping rules, and [PERFORMANCE.md](PERFORMANCE.md) for measured traffic-change overhead.

## Code map

- `simulation/battle.py`: authoritative fixed tick, command queue, events, effects and victory checks.
- `regiment.py`, `formations.py`, `orders.py`, `config.py`: state, immutable characteristics, commands and primary tuning values.
- `movement.py`, `geometry.py`: constrained movement, local detours, terrain/congestion effects, rectangle separation and swept segment collisions.
- `positioning.py`: bounded stationary-overlap settling, preferred versus accepted stopping points, deterministic pursuit lanes.
- `simulation/terrain.py`: analytic heights, forests, visibility, terrain presets and tuning profiles.
- `viewer/terrain.py`: cached shading, contour geometry and cosmetic trees.
- `combat.py`, `morale.py`, `projectiles.py`: statistical volleys, timed contact combat, morale state transitions and ballistic cannonballs.
- `simulation/ai.py`: standing order execution and infrequent opposing army decisions.
- `viewer/`: read-only rendering, camera, input translation and HUD. Rendering never advances RNG.
- `scenarios/`: immutable battle recipes, automatic deployment, JSON presets, the legacy standard battle and congestion demonstration.
- `viewer/setup.py`, `viewer/application.py`: setup/deployment editing, frame-budgeted updates and fresh-instance battle lifecycle.
- `viewer/interpolation.py`: read-only previous poses for smooth movement and projectile drawing.
- `analysis/performance.py`: repeatable simulation/render benchmarks and state checksums.
- `analysis/`: repeated headless battles, metrics, CSV/JSON and aggregates.
- `tests/`: movement, geometry, simulation replay, combat, morale, artillery, victory and dummy-display input/rendering checks.

Simulation positions are metres and angles radians. At each 0.1 s tick, army AI plans, queued player commands apply, intended destinations and pre-move congestion are sampled, units turn/move, post-move congestion costs cohesion, contact and ranged combat resolve, projectiles advance, morale updates, enemy rectangles separate, and victory is checked. Regiments are processed by ID. Each battle owns its seeded RNG. The same seed, scenario, rules and tick-stamped commands reproduce results on the same Python/runtime; cross-version bitwise replay is not promised. `command_history` records accepted commands for inspection; file-based replay is deferred.

## Current scope

Movement, formations, infantry volleys, basic cavalry charges, physical artillery, friendly fire, routing/rallying, autonomous orders, opponent AI, victory feedback, graphical controls and batch analysis work. Tests include a standard battle that completes without player input. This is a prototype, not a balanced game: some seeds can stall or exceed ten minutes. Friendly formations are passable: overlap slows movement and disrupts cohesion, with bounded penalties even in crowds. One bounded detour can avoid a stationary ally; moving allies are crossed rather than engaging in mutual avoidance. Enemies remain physical obstacles. There is no global pathfinding or guaranteed escape from an enemy encirclement.

The GUI was tested using SDL's dummy driver and a rendered screenshot; desktop interaction and Windows installation still need human testing. See [DESIGN.md](DESIGN.md) for rules, balance limits and next steps.

## Named regiment commanders

Every newly created battle regiment receives an independent, named officer with **one personality and one compatible tactical specialization**. Officers are separate from archetypes and may lead any faction's troops. European name pools use fictional combinations; Haudenosaunee officers use the nine supplied names listed below, preserving their spelling and accents. Existing saved assignments retain their identities.

In **deployment**, select a regiment and click **Officers (O)**. The modal's Previous/Next controls inspect either army. Click a personality or compatible specialization for controlled experiments; disabled specializations do not apply to that category. Reroll one officer or the displayed army, cycle background and reroll, or restore the scenario's officer assignments. **Apply/Enter** commits the whole edit; **Cancel/Esc** discards it. Reset positions retains officer edits. Officers cannot be edited during combat.

The selected regiment's upper-right panel shows its officer, personality, specialization, situational benefits and limitation. Major commander decisions, shock attacks, morale support and defensive interventions appear in the existing rate-limited event log. Battle report data also include each commander's full definition.

| Personality | Autonomous tendency | Trade-off |
| --- | --- | --- |
| Aggressive | Earlier cavalry commitment; bayonet attacks on nearby disrupted enemies; commits reserves early | Longer pursuit and greater tolerance for losing engagements |
| Cautious | Greater firing distance; short pursuit; earlier local disengagement when outmatched | Slower cavalry commitment; missed opportunities |
| Methodical | Reduced turning/congestion disruption; briefly reforms below 55 cohesion | Slower commitment; preparation delays |
| Opportunistic | Prefers disrupted/exposed targets with a ten-second target commitment | May divert from the previous autonomous objective |
| Stalwart | Reduced morale shocks; steadies shaken defenders; holds firing positions | Reluctant to disengage from bad fights |

**Explicit player Hold, Move, Attack, Charge and Withdraw orders take priority over personality decisions**, including when AI controls that army. Routing, physical contact and existing charge recovery still apply. Personality mainly changes autonomous orders; it does not provide insubordination.

| Specialization | Actual situational effect | Limitation / compatibility |
| --- | --- | --- |
| Drillmaster | Up to 15% faster formation changes, 10% less manoeuvre disruption and 10% better quiet cohesion recovery | Scales from zero at 40 cohesion to full at 90; infantry/cavalry |
| Firebrand | 12% stronger morale shock on sufficiently forceful exposed charges | Up to 3 extra cohesion lost after impact; autonomous cavalry pursuit radius +15%; infantry/cavalry |
| Pathfinder | Reduces forest slowdown by 20%, uphill sensitivity by 10% and terrain disruption by 15% | Little benefit on level open ground; all categories |
| Sharpshooter | Up to 12% better stationary, cohesive accuracy with clear sights | Reload +8% at all times; no aim bonus while moving, in melee or below 50 cohesion; infantry |
| Artillerist | Deployed battery aim scatter reduced 12% | Limber/setup time +10%; actual projectile physics unchanged; artillery |
| Inspirer | Nearby visible allies gain 0.12 morale/s, or 0.18 when rallying, and reduced nearby rout shock | Source must remain steady above 60 morale; no self-aura or stacking with stronger Royal Prestige; all categories |
| Pursuit Specialist | Pursuit power +12%, contact allowance +10%, pursuit congestion disruption −10% | Frontal fighting against steady targets −10%; cavalry |
| Defensive Tactician | Quiet defensive cohesion recovery +10%; prepared frontal charge resistance and cohesion retention improve 10% | Requires stationary, steady holding with cohesion ≥60 for resistance; aggressive advance speed −5%; infantry |

Numerical tuning and applicability live in `simulation/commanders.py` (`TUNING`, `POLICIES`, trait definitions). Trait effects modify the existing simulation rules; there are no commander bodies, extra soldier entities, active-ability UI, experience or casualties for officers.

Prepared JSON recipes store each placement's commander ID, name, rank, background, personality, specialization and biography, plus a separate `commander_seed` and reroll counter. Older version-1 recipes without those fields generate compatible defaults on preparation. **F5** retains assignments; **F6** changes combat randomness while retaining officers, terrain and deployment. To reproduce a run, retain the saved recipe and issue identical commands on identical simulation ticks. A combat seed alone does not identify manually edited commander assignments.

Five editable presets demonstrate the system: **Disciplined versus Reckless**, **Cavalry Personalities**, **Defensive Stand**, **Pathfinders in Woodland**, and **Morale Support**. They run through normal setup and headless tools:

```bash
python main.py --preset "Disciplined versus Reckless"
python main.py --preset "Defensive Stand" --quick
python -m analysis.batch_simulation --preset "Morale Support" --runs 3 --duration 300 --output morale.json
python -m analysis.commander_comparisons --runs 2 --seed 17 --duration 180 --output benchmark-results/commander-comparisons.json
pytest -q tests/test_commanders.py tests/test_commander_ui.py
```

The commander comparison tool fixes officer/map generation at seed 17, varies combat seeds, and mirrors each matchup to reduce positional bias. JSON includes per-regiment movement, firing, charge/pursuit, casualties, morale, cohesion, officer assignments and the bounded recent event log. These are initial experiments, not evidence of finished balance; see `PERFORMANCE.md` and `DESIGN.md` for limits.

## Threat-aware routing and artillery batteries

Broken regiments choose a local escape direction away from nearby, perceived enemies (with extra weight for cavalry), rather than blindly marching toward their original army edge. They consider several escape headings, avoid paths through known enemy formations, and retain their escape direction after clearing danger. Flight is reconsidered once per simulated second, preserving deterministic movement. A routed formation reaching a map edge can withdraw there. Units still turn, traverse terrain, suffer congestion, and rally through the existing systems. Explicit **Withdraw** remains an order to leave via the army's home edge; panic routing overrides it when necessary.

**Field artillery has six guns; French Horse Artillery has four.** A salvo fires one independently aimed cannonball per available gun, all on the battery's existing reload cycle. The available count is the original capacity multiplied by remaining crew fraction, rounded up and capped at capacity: a half-strength field battery fires three balls, and a half-strength horse battery two. The last surviving crew can operate one gun; destroyed or withdrawn batteries have none. Routing/rallying batteries cannot fire.

Each gun now has independent aim error of **up to ±45 m per axis** instead of ±18 m, with existing forest and Artillerist modifiers. Point-blank scatter is capped at half the target distance so shots cannot point backwards. Gun positions span the formation frontage. Every ball retains physical flight, terrain impacts, bouncing, penetration and friendly fire. More guns therefore mean a broader, less predictable salvo. The selected-unit HUD shows available/maximum guns; setup shows full battery capacity, and headless regiment statistics include `artillery_shots`.

Gun crews are weaker after contact: artillery melee damage and shock use a **0.10 multiplier** (previously 0.25), and incoming ordinary melee damage is multiplied by **1.25**. Cannonball damage and charge-impact formulas are unchanged. Flanking or reaching an unloaded battery remains preferable to charging directly into a loaded salvo.

Tune capacities with `UnitArchetype.guns` in `simulation/archetypes.py`. Flight sensing/cadence, shot scatter and crew melee modifiers are in `simulation/config.py`. Focused checks:

```bash
pytest -q tests/test_routing_and_batteries.py tests/test_artillery_targeting.py tests/test_contact_strategies.py
```

## Volley, woodland melee and trajectory tuning

All infantry—including Riflemen, Grenadiers, Prussian infantry and Woodland Skirmishers—now deal **10% more expected volley casualties**. This boosts the resolved casualties rather than range, reload speed or shot accuracy. Fractional casualties use seeded rounding, so even low-damage volleys receive the benefit. Casualty-related morale/cohesion losses follow normally; the fixed volley suppression shock is unchanged.

Woodland Skirmishers additionally deal **20% more melee casualties and 20% more direct melee morale shock**, including bayonet impacts. This applies in all terrain, while their existing forest advantages, loose-formation penalties and vulnerability to cavalry remain.

Every artillery shot now receives an independent **±3 m/s vertical launch-speed error**, alongside horizontal scatter. Some rounds strike/bounce early; others travel higher and overshoot. Actual terrain and friendly-fire collision remain authoritative. A deployed Artillerist reduces both horizontal and vertical scatter. Tune these with `Rules.infantry_volley_damage` and `Rules.artillery_vertical_scatter` in `simulation/config.py`; woodland melee multipliers are on its archetype in `simulation/archetypes.py`.

New Haudenosaunee commanders draw from these supplied whole names:

Tyorhansera · Akiatonharónkwen · Tekarihoga · Thayendanegea · Sagoyewatha · Skenandoah · Tewahongalahkon · Tyonajanegen · Atayataghlonghta

Generation uses every unused name before repeating within an army. If all nine are already assigned, numbered variants maintain distinct display names. Existing saved commander names are preserved; use **Officers → Reroll selected/this army** during deployment to replace older placeholders.

## Routing disorder and woodland combat

**Routing loses 1 cohesion point per simulated second**, in addition to combat, terrain and crossing disruption. Routing units cannot passively recover cohesion, even when stopped; recovery resumes while rallying. The rate is configurable as `Rules.routing_cohesion_loss`.

**A treeline now provides a real firefight advantage.** Previously vegetation reduced accuracy in both directions, but the regiment inside also suffered a separate firing penalty, often making its position worse. Incoming infantry fire now receives an additional cover reduction based on the target's actual forest-covered footprint and vegetation along the firing lane. A short outward lane at the treeline incurs much less firing disruption than shooting through deep woodland. Completely hidden targets still cannot be fired on.

At maximum cover the additional incoming accuracy reduction is 60%; partial cover and thin vegetation give less. This affects musket/rifle casualties, while artillery retains its physical ball/forest-energy rules. Cover is not a guaranteed win against superior numbers, range, flank attacks or artillery.

**Woodland Skirmishers are now substantially stronger in woods**, including light forest:

- Up to **3.2× woodland accuracy**, **4.5× woodland melee power**, and **2× woodland melee morale shock**. Their existing +20% base melee casualty/shock bonus remains.
- These training bonuses ramp with the fraction of their footprint in forest, reaching full effect at 40% forest cover. Physical protection, visibility and movement still use actual density.
- Dense formations struggle in forest melee: at full density, line loses 45% effectiveness, column 27%, and loose skirmish formation 11.25%.
- Woodland specialists resist headcount-based outnumbering pressure when covered, and accept favourable ambush fights instead of automatically retreating from a larger line regiment. Casualties, fire, flank/charge shocks and nearby cavalry still matter. Depleted or exposed skirmishers still withdraw.
- Open-ground weaknesses remain: the bonuses disappear outside forest, with 140 troops, low volley volume and weak conventional melee.

Controlled tests use fresh regiments, no commanders, seeds 17–26, mirrored sides and a 450-second limit. Woodland Skirmishers beat a 240-strong standard infantry regiment **20/20** in dense-forest ranged and melee engagements, and **19/20 ranged / 20/20 melee** in light forest (density 0.45). Autonomous skirmishing achieved the same woodland win counts. They lost **20/20** ranged and melee controls on open ground. An ordinary infantry regiment defending the treeline beat an identical open-ground opponent **20/20 in dense cover and 18/20 in light cover**. These demonstrate the intended matchup, not guaranteed outcomes with different conditions.

```bash
python -m analysis.woodland_balance --runs 10 --output benchmark-results/woodland-balance.json
python -m analysis.woodland_balance --density .45 --runs 10 --output benchmark-results/woodland-light.json
pytest -q tests/test_woodland_combat.py
```

Combat settings live in `TerrainRules` in `simulation/terrain.py`; skirmisher multipliers live in `simulation/archetypes.py`. Forests still conceal units, slow movement and disrupt marching formations; stationary troops do not lose cohesion simply for occupying woods.

## Idle player deployment and command buttons

New **player-controlled blue armies start on Hold**: infantry, cavalry, skirmishers and guns wait for your commands rather than advancing/charging automatically. Holding regiments still turn toward forward threats and fire autonomously. AI-controlled armies retain their initial plans; **AI controls both armies** still supports watching a battle. Switching blue from AI to player control clears its initial orders to Hold without changing deployment or commanders. Explicit starting orders in a saved recipe or deliberately chosen during deployment are retained; use **Reset positions** during deployment to restore the new default starting orders. The normal `--scenario standard` also starts blue on Hold; scripted movement/charge/traffic demonstrations retain their demonstration orders.

Select a friendly regiment during combat. The bottom panel now has clickable controls:

- **Formation:** Line, Column, Loose. Unsupported formations are greyed out; the chosen formation remains highlighted during its transition.
- **Immediate orders:** Hold, Skirmish, Reserve, Withdraw.
- **Attack / Charge:** click the button, then left-click an enemy. Clicking friendly troops or empty ground does not accidentally choose another order.
- **Move / Advance:** click the button, then left-click a destination and optionally drag to choose arrival facing. Release to issue the command; the existing ghost previews the result.
- **Defend:** click the button, then left-click the centre of the area to defend.

**Esc** cancels a pending command or placement before deselecting. Unsupported actions, routing/rallying/destroyed units and finished battles disable their buttons. Artillery cannot Charge or Skirmish. Buttons use the same simulation command queue as keyboard and right-click input; they work while paused and execute when simulation resumes.

Existing shortcuts remain: **L/C/K** formations, **H** Hold, **S** Skirmish, **R** Reserve, **W** Withdraw, and **B** charge the current target (or choose one if none exists). **M/A/T/D** arm Move/Advance/Attack/Defend targeting. Ordinary right-click move/attack, Ctrl-right-click charge, Shift-right-click advance, facing ghosts, pause, speed, camera and debug controls continue to work. The event panel shows the four most recent events beside the selected-unit information.

## Five-battle campaign

`python main.py` now opens the mode menu. Choose **New Campaign** (optionally edit its seed) or **Continue Campaign**. **Custom Battle** keeps the independent sandbox, presets, saved battle recipes and restart/rematch controls.

A new run starts with two line infantry regiments, Woodland Skirmishers, cavalry and artillery. Select roster entries to inspect their named commanders, starting traits and acquired abilities. **Deploy for next battle** opens the existing deployment view. Place/facing/formation/standing-order controls work as before; composition changes and officer rerolls are disabled. Player units start holding unless you give deployment or combat orders. Back to army retains the deployment.

After combat, the **existing battle report** opens. **Continue campaign** (or Enter) applies the result and opens rewards after victories 1–4. Pick one reward card and **Confirm reward**. For training, select an officer and one of their compatible offered abilities before confirming. The fifth victory completes the run; defeat or a draw ends it. Destroyed regiments leave the roster and their commanders retire from that run. Routed or withdrawn survivors retain their remaining troops.

- Surviving regiments automatically recover **30% of missing strength** after victory, rounded up.
- Replenishment rewards restore **65% of the remaining missing strength** across the surviving army.
- Recruitment supplies a full-strength regiment and new named commander. Specialist recruits can appear; the army cap is **10**.
- Training grants one permanent commander ability, with **three acquired abilities per commander**, one rank each. Starting personality/specialization remain intact. The reward list is fixed when generated, and claiming it advances the campaign exactly once.
- Normally there is one recruitment, training and replenishment option. Unavailable categories are replaced by valid alternative recruits/training offers or full replenishment of one depleted regiment. A fully prepared, capped army gets a Continue fallback.

Campaigns autosave at creation, before combat, after applying results and after reward confirmation. **Save campaign** is also available between battles. Default file: `saves/campaign.json`; **New Campaign replaces it**, as labelled in the menu. Use `--campaign-save /path/to/run.json` for another slot. Continue restores the exact encounter, deployment, commanders and pending reward offers. Closing during combat resumes its **pre-battle checkpoint**; mid-combat saving is unavailable. Restart/rematch/custom editing controls are disabled during campaign battles. Sandbox F5/F6/F7 are unchanged.

There are five encounter themes: Border Engagement, Mobile Opposition, Difficult Ground, Veteran Army and Decisive Engagement. Enemies progress through cavalry, forest specialists, disciplined infantry, guards, rifles and mobile guns. Maps and combat use independent fixed seeds. Recruitment, commander generation and rewards use separate deterministic streams. Final encounters add one infantry regiment when the player has at least eight regiments; recruitment otherwise produces a real numerical advantage.

All twelve commander upgrades are available. The roster/reward descriptions explain their conditions:

| Upgrade | Tactical use |
|---|---|
| Rolling Volley | High-cohesion lines reload faster near steady infantry support. |
| Swift Reform | Quicker formation changes, less manoeuvre disorder, faster quiet recovery. |
| Rallying Presence | Strongest-only morale/rally support aura. |
| Controlled Charge | Better mounted charge alignment/turning, less failed-impact disorder and faster recovery. |
| Relentless Pursuit | Better pursuit, with one cohesion recovery per enemy routed by the regiment. |
| Shock Commander | Greater charge morale shock against exposed enemies. |
| Woodland Ambush | Concealed opening volleys disrupt morale/cohesion; requires genuine disengagement to reset. |
| Harassing Fire | Successful light-infantry volleys disrupt additional cohesion. |
| Steadfast Defence | A steady defensive line resists charges and morale shocks. |
| Mobile Battery | Shorter limber/deployment delays. |
| Calculated Fire | Prepared stationary artillery has less horizontal and vertical aim scatter. |
| Inspired Attack | Hits on wavering/routing enemies encourage allies, with a shared army cooldown. |

Examples: Prussian infantry + Drillmaster + Rolling Volley/Swift Reform; Uhlans + Shock Commander/Relentless Pursuit; Woodland Skirmishers + Pathfinder + Woodland Ambush/Harassing Fire; Grenadiers + Rallying Presence/Steadfast Defence. These combine normal rules, rather than scripted full-build bonuses.

Campaign implementation: `campaign/state.py` owns immutable persistent records and transactions; `simulation/upgrades.py` owns eligibility, descriptions and numerical tuning; `viewer/campaign.py` wraps the existing deployment/battle/report flow. Version-1 JSON campaign saves contain the army, retired commanders, encounter recipe/terrain, progression, rules and fixed pending offers. Custom-battle JSON remains a separate format; older custom recipes default to full starting strength and no acquired abilities.

```bash
pytest -q
pytest -q tests/test_campaign.py tests/test_commander_upgrades.py tests/test_campaign_ui.py
python -m analysis.campaign_run --seed 17 --runs 3 --policy recruit --output benchmark-results/campaign.json
python -m analysis.campaign_run --seed 17 --battles 2 --duration 900 --policy upgrade
```

The headless campaign runner gives blue the existing army AI for balance measurements. It uses actual battles, records timeouts honestly, chooses compatible rewards deterministically, and writes the existing battle reports to JSON. The automated five-stage integration test uses controlled results to exercise all transitions independently of uncertain combat outcomes. This is an initial difficulty curve: enemy counts, map sizes, reward rates, upgrade tuning and the 30–60 minute target need broader player testing. There is no commander transfer UI, campaign mid-battle save, metaprogression, or manual enemy deployment.


## Godot migration viewer

A separate Godot 4 project now plays recordings from the existing Python simulation in **3D**. Launch `godot --path godot` to open its completed mixed-terrain example, with real terrain geometry, batched trees, low-poly infantry/cavalry/cannons and recorded cannonball trajectories. The tactical camera supports WASD pan, Q/E yaw, middle-drag terrain grab, Alt-middle orbit/tilt, cursor-centred wheel zoom, Home overview, F focus, C follow, T overhead and P projection switching. Camera motion stays independent of replay pause/speed. Selection, inspection and timeline seeking remain available. The Python game and campaign continue through `python main.py`.

```bash
python -m migration_tools.record_battle --seed 7 --duration 650 --output recordings/battle
godot --path godot -- --recording="$PWD/recordings/battle/metadata.json"
python -m pytest -q tests/test_recording.py
godot --headless --path godot --script tests/test_playback.gd
godot --headless --path godot --script tests/test_camera_3d.gd
godot --headless --path godot --script tests/test_viewer_3d.gd
# Preserved original 2D scene:
godot --path godot --scene res://scenes/battlefield.tscn
```

The Godot mode selector offers **Live (C#)**, driven by the standalone .NET engine. Milestone 3 adds morale states, fleeing, rallying, cascading routs, accelerating cavalry charges, recoil and moving pursuit to the movement/terrain/LOS/infantry-combat port. Nine new demonstrations join the six prior combat scenarios and original movement sandboxes. Use **B/U/X/G** for charge/pursue/disengage/reform; routing/rallying troops regain control only after recovery. Milestone 4 adds physical artillery, friendly fire and all six specialist archetypes; **Y/I/O** control hold/resume fire and manual skirmish stance. Use `bash tools/godot.sh -- --combat-scenario=combined-arms`. Milestone 5 adds autonomous tactical AI, named commanders and eight starting specializations. Launch `bash tools/godot.sh -- --combat-scenario=ai-player --paused` or `--combat-scenario=ai-combined` to watch AI versus AI. The **AI** dialog controls army objectives and before-battle officers. Acquired upgrades and campaign remain in Python. See [AI and commanders](godot/AI_COMMANDERS.md). See [artillery and specialist rules](godot/ARTILLERY_SPECIALISTS.md). Live requires the matching .NET Godot build and a .NET 10 SDK; replay continues in standard Godot. See [morale/cavalry rules and validation](godot/MORALE_CAVALRY.md) and [launch commands](godot/README.md).

```bash
bash tools/bootstrap_dotnet.sh       # First-time Linux x86_64 setup into .tools/
bash tools/dotnet.sh build godot/Quiberon.csproj
bash tools/godot.sh -- --live
bash tools/dotnet.sh test godot/Simulation.Tests/Simulation.Tests.csproj -c Release
```

Select Blue, right-click to move, use L/J/K for formations, H to hold, Space to pause, 1/2/3/4 for 1×/2×/4×/10×, . for a paused tick and R to reset. C stays camera-follow. Buttons expose the same commands. Choose Replay Mode to return to recorded battles. See [Godot setup and scene structure](godot/README.md), [live architecture and limits](godot/LIVE_SIMULATION.md), [camera tuning](godot/CAMERA.md), [3D validation and performance](godot/VIEWER_3D.md), the [architecture audit and migration results](MIGRATION.md), and the [recording format](migration_tools/FORMAT.md). No external visual assets or new Python dependencies were added.
