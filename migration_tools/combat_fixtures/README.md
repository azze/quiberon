# Milestone 2 combat oracle

These are reference fixtures, not battle recordings or full Python save games.
They call the current Python rules with neutral commanders, steady/frozen morale,
ordinary musket infantry and a controlled random stream. Python game code and
its normal MT19937 RNG are unchanged.

- `calculations.json`: 26 input/expected pairs for analytic terrain/LOS, arcs,
  frontage, hit probability, friendly screens/stacking, controlled volleys and
  front/flank/rear/woodland/uphill melee. `randomDraws` is a finite test tape.
- `traces.json`: six sampled engagements: five live scenarios and a twelve-unit
  moving-under-fire/melee case. Ridge/forest run 90 simulated seconds, the other
  demonstrations 30, and moving combat 70. Samples include discrete formation,
  position, facing, strength, cohesion, reload, combat state and final draw count.
- `rng.json`: the first 100 SplitMix64-v1 doubles for seed 17. The C# and isolated
  Python implementations must match these exactly; equal ordinary Python/.NET
  seeds do not otherwise imply matching random sequences.

Scenario input uses the Milestone 1 schema with optional `combatEnabled`, unit
`strength`, order `targetId`, and `randomDraws`. World XY is metres, downward Y,
clockwise radians. Ticks are 0.1 s. `simulation_data/combat_scenarios/` contains
the six shared live templates and four 12/24/36/60 stress inputs. The C# core
embeds these definitions; the viewer does not regenerate them on load.

Regenerate only when deliberately updating the oracle:

```bash
.venv/bin/python -m migration_tools.combat_reference --generate
.venv/bin/pytest tests/test_combat_reference.py -q
bash tools/dotnet.sh test godot/Simulation.Tests
```

Python tests verify the checked-in expectations still describe current Python.
C# tests compare formulas/states at 1e-5 absolute tolerance and exact repeated
serialized output; all six current sampled traces have zero observed numeric
difference on the tested host. Portable draw counts and final strengths also
match the full benchmark workloads. These scoped tests intentionally exclude
morale transitions, charges, artillery, tactical army AI and trait effects.

Benchmark and launcher instructions: [Godot README](../../godot/README.md).
Rules, temporary differences and limitations: [COMBAT.md](../../godot/COMBAT.md).
