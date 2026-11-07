# Commonwealth campaign audit

Reference: user-supplied Prologue Campaign Design Reference v0.1 (full conversation),
and docs/COMMONWEALTH_STAGE1_REFERENCE.md. Six stages, stage four rescue/intercept
branch, coalition identities and curated historical cast are retained.

Python campaign/state.py already separates immutable army records, seeded rewards,
atomic saves and battle-result transfer, but has five generic encounters rather
than the authored Commonwealth story. Native UpgradeSystem already implements all
twelve requested effects and compatibility. HistoricalCommanders supplies the cast.
BattleReport and battle_results.gd already freeze/display results and will be reused.

Native Units is a fixed read-only collection with cached ID/initial-strength maps.
Scripted reinforcements will be predeclared inactive reserves, activated only at
valid entry positions; ordinary custom battles have no mission layer. Convoy wagons
use an unarmed, non-fighting transport instance of the existing artillery profile,
with a presentation flag, not a new recruitable archetype. Objective and directive
updates run at fixed ticks and own mission completion only when explicitly configured.
Campaign roster/commander/reward/event data never references live Regiment objects.

Baseline: 551 native tests, 674 Python tests, 537 Godot checks. Environmental
benchmarks in benchmark-results/environment-after.json retain the pre-campaign
reference. No combat formula or general tactical AI rewrite is planned.
