# The Defence of the Commonwealth — Stage 1 content audit

Status: the user supplied Design Reference v0.1 in full after the initial audit.
Sections 5 and 8 were read and checked before implementing content. The scoped
[reference extract](../docs/COMMONWEALTH_STAGE1_REFERENCE.md) and final
[implementation report](../docs/COMMONWEALTH_STAGE1.md) describe the source and
result. The pre-change findings and baseline below are retained for review.

## Existing implementation

- `simulation_data/movement_archetypes.json` is the embedded source of nine native
  archetypes. `Simulation/Units/RegimentArchetype.cs` separates immutable stats from
  `Regiment` battlefield state. Weapon profiles cover muskets, rifles and round shot.
- `Simulation/AI/TacticalAi.cs` provides scheduled common decisions, reserve/flank
  preparation, skirmishing, artillery repositioning and player-order priority.
  Some role decisions currently check specific archetype IDs. New content should
  introduce reusable role metadata while preserving those legacy identities.
- `Combat/CombatSystem.cs`, `InfantryChargeSystem.cs`, `CavalrySystem.cs`,
  `MoraleSystem.cs`, and `Artillery/ArtillerySystem.cs` already own damage, shock,
  impact locks, moving pursuit, bounded support, physical trajectories and hits.
  New units should use those calculations rather than parallel combat systems.
- `Commanders/CommanderSystem.cs` reads generic names, five personality policies
  and eight specializations from `commander_definitions.json`. Historical
  definitions, alternative-name collections, availability tags and army command
  assignments do not yet exist. Acquired upgrades are a separate system and are
  not progression work for this stage.
- Battlefield allegiance is already `Regiment.Army`; archetype faction is separate.
  Mixed factions can cooperate without changing the definition of an enemy.
- `Setup/BattleConfiguration.cs` preserves version-1 custom recipes and explicit
  terrain/placement/officer state. It validates unique commander IDs and category
  compatibility. Historical definition uniqueness must also cover army assignments.
- Godot's `unit_picker.gd`, `battle_setup.gd`, `replay_hud.gd` and
  `LiveSimulationBridge.cs` are the extension points for faction filters, historical
  selection and inspection. Existing count limits and deployment validation remain.
- `resources/unit_visuals.json` and `three_d/mesh_kit.gd` provide shared low-poly
  silhouettes. New profiles should retain army readability and batching.
- The live/replay controller shares its current battle between 2D and 3D. Do not
  replace this with campaign-specific presentation or replay loading.

## Core-roster implementation mapping

These were the baseline choices checked against the supplied design document.
Generic archetypes and both French specialists must remain available independently.

| Campaign unit | Existing baseline | Required work |
|---|---|---|
| Commonwealth Regular Infantry | `infantry` | New faction-specific regular profile; preserve generic infantry. |
| Citizen Militia | `infantry` | New profile with conditional defensive purpose and weaker manoeuvring. |
| Scythemen | Infantry movement, bayonet charge and shared melee | New melee-only profile, role-aware approach AI, and scythe silhouette; no fake musket. |
| National Cavalry | `cavalry` | New balanced Commonwealth cavalry profile. |
| Advance Guard Lancers | `commonwealth_uhlans` | Check intended role against document; reuse/alias the existing identity where suitable. |
| Commonwealth Field Artillery | `artillery` | Faction-specific battery; retain physical round shot and assess physical canister. |
| Revolutionary Line Infantry | `infantry` | New British rate-of-fire/manoeuvre trade-off without replacing generic regulars. |
| Experimental Rifle Corps | `revolutionary_rifles` | Strong reuse candidate; preserve ID, range/aim/reload trade-off and AI. |
| Haudenosaunee War Party | `haudenosaunee_skirmishers` | Check detachment strength and open-ground utility; retain existing woodland mechanics. |
| Prussian Musketeers | `prussian_line` | Strong reuse candidate; preserve existing drill and cohesion balance. |
| Prussian Grenadiers | Infantry assault systems | New offensive elite profile; do not repurpose French Royal Grenadiers. |
| Prussian Cuirassiers | Cavalry charge/melee systems | New heavy profile with turn/terrain/pursuit limitations. |
| Russian Musketeers | `infantry` | New resilience versus tactical-responsiveness trade-off. |
| Russian Grenadiers | Infantry assault systems | New shock/resilience profile distinct from Prussian grenadiers. |
| Russian Cossacks | Cavalry flanking/pursuit systems | New light profile and reusable risk-sensitive harassment decisions. |

Four existing IDs potentially cover four core units; the remaining eleven core
profiles would bring the sandbox to twenty archetypes, including the five retained
non-core/generic profiles. This is not an expansion to the document's full 31 units.

## Commander implementation mapping checked against the design reference

| Historical figure | Scope to represent | Existing integration points |
|---|---|---|
| Tadeusz Kościuszko | Army commander | Bounded citizen-formation defensive support; no forced regimental slot. |
| Franciszek Ksawery Niesiołowski | Regimental | Cohesion-dependent organized volleys through existing reload/accuracy. |
| Jan Henryk Dąbrowski | Regimental | Manoeuvre disruption, formation time and quiet recovery hooks. |
| Antoni Madaliński | Regimental cavalry | Moving pursuit, shared casualty budgets and prepared-front limitations. |
| Jakub Jasiński | Regimental | Conditional outnumbered militia support; alternate-history survival note. |
| Franciszek Ksawery Łaźniński | Regimental cavalry | Recovery/fatigue/reform hooks; retain impact and cooldown locks. |
| Edward Marcus Despard | Expeditionary/regimental | Prepared defence and battery deployment; construction remains future-only. |
| Lord Edward FitzGerald | Regimental/coalition | Conditional nearby mixed-faction cooperation using spatial queries. |
| Joseph Louis Cook | Expeditionary/regimental | Structured Akiatonharónkwen alternative name and mixed-army cooperation. |
| Friedrich Wilhelm von Bülow | Regimental | Infantry formation/manoeuvre support; no new Fusilier unit. |
| Gebhard Leberecht von Blücher | Regimental cavalry | Existing aggressive personality policy plus conditional offensive trade-offs. |
| Pyotr Bagration | Regimental | Mobile infantry assault intent and manoeuvre hooks. |
| Matvei Platov | Regimental cavalry | Light-cavalry threat evaluation, mobility and pursuit. |
| Alexander Suvorov | Army commander | Scoped offensive direction/coordination, not large universal stat inflation. |

Final personalities, numeric effects, eligibility and metadata are recorded in
`simulation_data/commonwealth_commanders.json` and the implementation report. Historical
officers must not enter the procedural fictional-officer pool. Stable definition
identity must prevent duplicate historical assignments across both armies and
both commander scopes.

## Important mechanical gaps and compatibility risks

1. **Melee-only infantry:** `CombatCapable` currently depends on a weapon profile.
   `Combat.Intent` returns early for non-ranged infantry, and attack paths later
   dereference `Weapon!`. Scythemen require an explicit ranged-versus-melee role
   distinction and a shared close-assault branch, not a zero-range musket.
2. **Role-based AI:** rifle/skirmisher checks use existing IDs, and cavalry currently
   shares one risk/charge plan. Extend small common role parameters, preserving
   existing thresholds and explicit player orders.
3. **Canister:** the native model currently fires solid round shot only. Any canister
   extension must use actual swept projectiles, friendly collision and existing
   damage/morale rules; exact scope and parameters need to be decided after reading
   the design document.
4. **Historical identity:** current commanders have IDs and one `Nation` field but
   no definition registry, historical role or structured alternative names. Save
   compatibility should preserve absent optional fields in existing recipes.
5. **Army command:** current army objects describe doctrines, not historical leaders.
   Add only a small serializable assignment/effect scope; no generals as dummy
   regiments, command hierarchy, campaign recruitment or progression.
6. **Support stacking/performance:** reuse spatial queries and strongest-source
   caps. Do not add a fresh full-army scan per commander per tick.
7. **Replay and existing sandbox:** preserve all nine existing archetype IDs, curated
   procedural names, old recordings, generic traits, French specialists, camera
   controls, facing gestures, and the same-battle 2D/3D switch.

## Pre-change validation

`bash tools/dotnet.sh test godot/Simulation.Tests --no-restore -v quiet`:
482 passed, zero failed, zero skipped. No gameplay changes were made.

## Pre-change performance baseline

Command: `.venv/bin/python -m migration_tools.benchmark_ai --repeats 1
--output benchmark-results/commonwealth-stage1-baseline.json`.
Each case used 100 warm-up ticks followed by 600 measured ticks (60 simulated
seconds). These are single-run development baselines, not evidence about new
campaign content or Godot rendering performance.

| Regiments | Mean tick (ms) | 95th percentile (ms) | Ticks / wall second |
|---|---:|---:|---:|
| 12 | 0.492 | 0.890 | 2,029 |
| 24 | 0.863 | 1.256 | 1,158 |
| 36 | 1.385 | 2.078 | 722 |
| 60 | 2.581 | 3.550 | 387 |

## Audit resolution

The document prerequisite is satisfied. Stage 1 now adds eleven profiles, reuses
four stable specialist IDs, adds fourteen authored historical definitions and two
army-command roles, and extends existing combat/custom setup. See the implementation
report for validation, comparisons, limits and Stage 2 dependencies. The initial
mechanical gaps above describe the code before this content pass.
