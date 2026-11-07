# Morale/cavalry oracle

`calculations.json` contains 38 controlled current-Python probes.
`traces.json` contains ten sampled actual Python `Battle.step()` runs: nine live
demonstrations and a victory-grace case. The normal Python game is unchanged;
only this isolated harness substitutes the specified SplitMix64 stream or a
finite tape. Commanders/army AI/projectiles are absent, matching the native scope.

Inputs extend the existing version-1 scenario schema with `moraleEnabled`,
`cavalryEnabled`, and optional unit `morale`, `state` and `safeTime`. Legacy
fixtures default to frozen morale; normal Godot live combat enables M3. The shared
live/benchmark JSON lives in `simulation_data/combat_scenarios/` and is embedded
in the C# assembly. The renderer never regenerates encounters or rules.

Comparisons include morale/cohesion/strength, position/facing/fatigue/speed, states,
recovery timers, reload, charge lifecycle/momentum/readiness, impact/pursuit/rout
counters, random draw consumption and battle result. Inactive speed is normalized
to zero: Python retains its old value, while native snapshots explicitly clear
dead/escaped movement. No living motion is normalized. Exact tested differences
and the small physical-contact pursuit fix are documented in
[MORALE_CAVALRY.md](../../godot/MORALE_CAVALRY.md).

```bash
# Deliberately regenerate expectations from current Python:
.venv/bin/python -m migration_tools.dynamics_reference --generate
.venv/bin/pytest tests/test_dynamics_reference.py -q
bash tools/dotnet.sh test godot/Simulation.Tests
# Matched active dynamics workloads, separate from rendering:
bash tools/dotnet.sh build godot/Simulation.Runner -c Release
.venv/bin/python -m migration_tools.benchmark_dynamics --repeats 3
```

Current maximum sampled numeric difference is 3.57e-13; tests allow 1e-5 for
platform math differences and require exact repeated C# output. Equal ordinary
Python/C# numeric seeds do not imply matching MT19937/SplitMix64 streams. Generated
runtime reports remain under ignored `benchmark-results/`, not in this oracle.
