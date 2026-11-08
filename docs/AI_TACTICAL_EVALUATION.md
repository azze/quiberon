# Old versus new tactical AI — 7 November 2026

Historical evaluation of the first tactical pass. The subsequent army director and
formation fix are evaluated in [Army director](../godot/ARMY_DIRECTOR.md).

The new AI does **not yet show an overall win-rate advantage** in this test suite.
It has a strong advantage when friendly firing lanes are blocked, but serious
regressions in conventional line engagements and woodland fighting.

## Main tournament

| Matchup | New wins | Old wins | Unresolved |
|---|---:|---:|---:|
| Equal line infantry | 0 | 16 | 4 |
| Symmetric combined arms | 11 | 9 | 0 |
| Blocked friendly firing lanes | 20 | 0 | 0 |
| Wooded flanks | 4 | 15 | 1 |
| Concentrated local support | 10 | 6 | 4 |
| Capture central road | 11 | 9 | 0 |
| **Total** | **56** | **55** | **9** |

The new AI wins 50.45% of the 111 resolved battles. Across all 120 games its win
fraction is 46.67%; unresolved battles could move that to at most 54.17%. Timeouts
are not counted as victories. The capture scenario has an explicit 900-second
mission deadline; a defender winning that deadline is a real scenario result.

A seed-block bootstrap, keeping both side assignments and all six matchups within
each sampled seed together, gives an approximate 95% score interval of 43.75–57.08%.
For that exploratory interval only, an unresolved game receives half a point. The
interval includes 50%; these results do not establish an overall improvement.

There are useful improvements apart from wins:

- Mean casualties per army/battle: **524.8 new versus 569.6 old** (7.9% fewer).
- Mean lost fraction: **53.6% versus 58.2%** of starting strength.
- In blocked-lane battles specifically, mean casualties: **301.3 versus 586.2**.
- Sampled blocked firing time in that scenario: **3.65 versus 305.6 regiment-seconds**.
- Across the full suite, mean salvos: **123.3 versus 117.1**.

The blocked-time diagnostic samples once per simulation second. It counts effective
infantry with an in-range, visible current target whose firing corridor is blocked;
it is not a measure of all causes of missed fire. Casualties include living routed
and escaped troops correctly as survivors. These averages come from the same games,
not separate force compositions.

## Method and fairness checks

- Baseline: exact `TacticalAi.cs` from Git commit
  `9a23276044df6526c7422c6777eef71bc1438732`.
- New controller: working-tree tactical AI after the three decision improvements.
  Combined source SHA-256:
  `58dea1ad41ffade13fd895042eb6c04911192fc8f4ea6fe31a9f6a46cc0deaec`.
- Both controllers run in the **same current simulation instance**. A temporary
  build dispatches per-army `Plan` and `Skirmish` calls to the archived controller.
  The schedule, movement, combat, visibility, morale, terrain, RNG and unit stats
  are shared. Playable project sources are not patched by the evaluator.
- Seeds: 17, 31, 73, 101, 149, 211, 307, 401, 503, 601.
- Each seed/matchup runs twice: new on army 0, then new on army 1, without changing
  the forces, deployment, officers, strategies, terrain or battle seed.
- Both forces have matched archetypes and officer personalities/specializations.
  Formations and subsequent actions are chosen by their respective AI.
- Five matchups use ordinary army-collapse victory. The sixth is capture versus
  defence, with the controller assignments swapped between roles.
- All use balanced army strategy and a 900-second simulation-time budget.
- An additional 24 controls use old/old and new/new controllers on seeds 17 and 31.
  Old/old: army 0 wins 6, army 1 wins 4, 2 unresolved. New/new: 8, 2, 2 respectively.
  This small control sample is insufficient to rule out deployment or ID-order
  advantages; swapping controller sides in every main pair limits that confound.
- **All 12 old/old controls exactly reproduce the original baseline engine's final
  positions, facing, strength, morale, cohesion, routing/withdrawal states, ending
  time, winner and combat RNG draw count.** This checks the legacy dispatch against
  the real baseline rather than an approximation of it.

Matching seeds do not imply matching random draws across different decisions. The
paired test keeps the starting stream fixed, while allowing different action and
combat histories. It is not a claim of identical RNG call order.

The layouts were chosen to exercise the new features, including a deliberately
obstructed firing-line setup. Equal weighting of six authored layouts is not a
prediction of win rate over every custom battle or campaign composition.

## Diagnostic: firing-position layer

After the main results, a temporary ablation disabled only the new
`TryFiringPosition` layer for the new controller. All its other new decision rules
remained enabled. These are diagnostic results, not a deployed fix.

| Matchup | Full new AI W/L/unresolved | New AI without positioning W/L/unresolved |
|---|---:|---:|
| Line infantry | 0 / 16 / 4 | 7 / 11 / 2 |
| Wooded flanks | 4 / 15 / 1 | 12 / 8 / 0 |

The same ten seeds and both side assignments were used: 40 ablation games. This
implicates the positioning layer and its interactions with other decisions, rather
than proving which individual scoring coefficient is responsible.

A further 40 instrumented repeats of the full new/old matchups reproduced **all
40 original final checksums**. Opening volleys show a concrete formation issue:

| Observed first infantry volleys | New in column | Old in column |
|---|---:|---:|
| Line matchup | 20 of 80 | 0 of 80 |
| Woodland matchup | 50 of 80 | 0 of 80 |

These counts include only regiments that fired. Mean shots in those first volleys
were 74.6 new versus 91.5 old in the line matchup, and 31.3 versus 69.5 in woodland.
Column formations fire only 32% of line volume under the existing combat rules.

Code inspection gives a plausible mechanism: `TryFiringPosition` can return a Move
order before normal line/skirmish formation selection runs. The regiment may then
open fire while still in its marching column. This is a decision-integration fault,
not evidence that the underlying infantry combat balance needs changing.

Range/accuracy alone does not explain the line result: mean volley range was 0.846
of weapon range for new versus 0.837 for old, with mean hit probabilities 0.0504
versus 0.0507. Woodland showed a larger accuracy gap: 0.0367 versus 0.0418. These
are per-battle means, not a controlled estimate of casualties caused by range alone.

**Recommended next step:** ensure firing-position movement cannot suppress timely
firing-formation preparation, retain the demonstrated lane-clearing benefit, then
repeat the unchanged tournament. Further sub-ablations can separate repositioning,
hold/range policy and formation timing. No playable AI or balance was changed during
this evaluation.

## Reproduction and artifacts

```bash
.venv/bin/python -m migration_tools.compare_tactical_ai --baseline 9a23276044df6526c7422c6777eef71bc1438732
.venv/bin/python -m migration_tools.summarize_ai_tournament benchmark-results/ai-tournament

# Diagnostic: disable positioning only in the isolated new-controller test build.
.venv/bin/python -m migration_tools.compare_tactical_ai \
  --baseline 9a23276044df6526c7422c6777eef71bc1438732 \
  --scenarios line-engagement wooded-flanks --control-seeds 0 \
  --ablate-positioning --output benchmark-results/ai-tournament-no-positioning
```

The evaluator creates and removes an isolated C# build in `/tmp`, reading the
baseline controller from Git. It needs the .NET SDK and existing package cache.
An optional `--legacy-runner /path/to/baseline/Simulation.Runner.dll` verifies the
old/old controls against a separately built baseline runner.

Generated raw cases, methods, results, summaries and parity checks are under
`benchmark-results/ai-tournament/`; ablation and instrumented repeats are in sibling
`ai-tournament-no-positioning/` and `ai-tournament-position-diagnostics/` directories.
The repository's existing ignore rules exclude generated benchmark files. This
report and the reusable evaluation tools remain source-controlled project content.

This is an exploratory evaluation, not a complete AI strength certification. It does
not measure human opponents, full mixed-controller campaign runs, river-crossing
operations, all commander combinations, or all army strategies. The conspicuous
line/woodland regressions should be addressed before calling the new AI stronger.
