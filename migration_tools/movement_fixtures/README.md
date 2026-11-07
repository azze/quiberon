# Movement-only reference schema, version 1

These are small shared experiment inputs, **not** Python battle saves or visual recordings. Both languages use metres, clockwise XY radians, a 0.1 s tick and stable integer IDs. Movement consumes no RNG; seed is retained for future use. The C# core knows four archetype IDs from `simulation_data/movement_archetypes.json`.

```json
{
  "version": 1,
  "name": "example",
  "seed": 17,
  "width": 1000,
  "height": 600,
  "duration": 60,
  "sampleTicks": [0, 1, 100, 600],
  "units": [{"id": 0, "army": 0, "name": "Line 1", "archetype": "infantry", "position": {"x": 200, "y": 300}, "facing": 0, "formation": "line", "cohesion": 100}],
  "commands": [{"tick": 0, "regimentId": 0, "order": {"kind": "move", "destination": {"x": 400, "y": 300}, "facing": 1.57}}, {"tick": 100, "regimentId": 0, "formation": "column"}]
}
```

Commands execute before the numbered tick. Formation commands take time and preserve existing orders. Optional terrain contains `hills` (`x,y,radiusX,radiusY,height,compact`) and `forests` (`x,y,radiusX,radiusY,density`), in the authoritative analytic representation. Optional unit fields include fatigue and a plain commander identity record. All regiments start at full strength; combat is absent.

`references/*.json` stores Python sampled states, with complete order/formation/separation/cohesion/terrain context. Generated references are retained as reviewable oracles. Eleven cases cover requested movement scenarios plus destination conflicts, artillery delays and terrain. `benchmark-*.json` instead describes crowded movement-heavy combined arms at 12/24/36/60 regiments. Both languages run the same movement phases; benchmarks exclude AI target searches, combat, rendering and snapshot serialization. The first 100 ticks warm up; the next 600 measure 60 simulated seconds, with a scheduled reversal at tick 500.

From the repository root:

```bash
.venv/bin/python -m migration_tools.movement_reference --generate
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release -- --scenario turning --output benchmark-results/turning.json
.venv/bin/python -m migration_tools.movement_reference --compare benchmark-results/turning.json
bash tools/dotnet.sh test godot/Simulation.Tests/Simulation.Tests.csproj -c Release
.venv/bin/python -m migration_tools.benchmark_movement --repeats 3
```

Do not regenerate expected output just to hide a mismatch. Investigate numerical or behavioural differences first. Comparisons require equal sampled times, exact discrete states/orders and at most **1e-5 absolute numeric error**. The reference tool calls unchanged Python movement/positioning/terrain functions; pytest verifies its phase runner against the original sandbox battle. C# tests also compare repeated runs exactly. No cross-language stochastic equivalence is promised.
