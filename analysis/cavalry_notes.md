# Cavalry experiments — 2026-11-01

Python 3.14.8 / Linux x86_64. Five seeds (1–5), each normally tested in both side-swapped deployments; 240 simulated seconds maximum. Factory: `scenarios/cavalry_tests.py`; runner: `python -m analysis.cavalry_balance`. No Pygame or profiler. Raw local files: `benchmark-results/cavalry-balance-before.json` and `cavalry-balance-after.json`.

The baseline already includes the previous broken-unit kill-floor/morale-shock correction. This pass adds distinct accelerated impact, close pursuit, morale-state melee penalties and post-impact behaviour. Baseline charge counters mean cooldown-triggered melee bonuses; new charge counters mean actual impacts, so they are not interchangeable.

Non-routing encounters count cavalry success when infantry routes or is destroyed; cavalry loses when all pursuers lose effective capability. Initially routing encounters continue until destruction, reaching the home edge, or timeout. Home-edge escape is an experiment stopping rule, not a change to runtime withdrawal. Distant reserves keep army victory from truncating the isolated interaction. Duration includes approach, and losses count riders/infantry rather than regiment percentages.

The first baseline harness incorrectly left the forest fixed when swapping armies. Its five mirrored forest samples are excluded below; the forest before/after comparison uses the five matching unmirrored samples. All other comparisons use ten samples. The final factory mirrors forests/hills with armies, guarded by a regression test, and all 80 after samples use valid geometry.

| Matchup | Samples | Cavalry successes before → after | Mean seconds before → after | Mean cavalry losses before → after | Mean infantry losses after |
| --- | ---: | ---: | ---: | ---: | ---: |
| standard-routing | 10 | 10 → 10 | 143.8 → 61.0 | 5.4 → 2.4 | 240.0 |
| standard-wavering | 10 | 10 → 10 | 35.9 → 16.8 | 24.2 → 9.2 | 15.2 |
| steady-front | 10 | 0 → 0 | 36.2 → 34.2 | 45.6 → 47.2 | 1.8 |
| steady-flank | 10 | 0 → 10 | 46.1 → 29.4 | 35.2 → 9.2 | 39.8 |
| uhlans-routing | 10 | 10 → 10 | 184.7 → 54.5 | 7.6 → 1.8 | 240.0 |
| forest-front | 5 | 0 → 0 | 76.3 → 76.0 | 46.0 → 45.8 | 10.0 |
| open-front | 10 | 0 → 0 | 36.2 → 34.2 | 45.6 → 47.2 | 1.8 |
| double-pursuit | 10 | 10 → 10 | 114.7 → 38.2 | 8.6 → 0.8 | 240.0 |

After-only detail below uses all ten valid samples per matchup. Impact damage averages actual impacts; duration means elapsed pursuit seconds, while the JSON also reports summed pursuit unit-seconds. Impact success is at least 5% of target type strength or a sufficiently forceful break; it is a proxy rather than proof that the charge caused a rout.

| Matchup | Impacts/battle | Mean impact casualties | Mean pursuit seconds | Pursuit casualties | Cavalry pursuit losses | Failed / aborted charges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| standard-routing | 1.0 | 36.2 | 37.3 | 203.8 | 2.4 | 0.0 / 0.0 |
| standard-wavering | 1.0 | 15.2 | 0.0 | 0.0 | 0.0 | 0.0 / 0.0 |
| steady-front | 1.0 | 0.8 | 0.0 | 0.0 | 0.0 | 1.0 / 0.0 |
| steady-flank | 1.0 | 28.6 | 0.0 | 0.0 | 0.0 | 0.0 / 0.0 |
| uhlans-routing | 1.0 | 48.2 | 34.9 | 191.8 | 1.8 | 0.0 / 0.0 |
| forest-front | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 / 0.0 |
| open-front | 1.0 | 0.8 | 0.0 | 0.0 | 0.0 | 1.0 / 0.0 |
| double-pursuit | 2.0 | 49.0 | 18.5 | 142.0 | 0.8 | 0.0 / 0.0 |

All final encounters resolved within the duration limit; no initially routing matchup failed to make contact. Routing and wavering targets favour cavalry strongly; prepared frontal infantry defeats it; exposed flanks can break under a fast impact. Forests deny the organized charge in this fixture and prolong the approach. Two pursuers shorten the chase without doubling instantaneous damage or multiplying resistance rolls. These are deliberately clear role tests, not evidence of general balance or a required equal win rate.

Standard and Uhlan riders retain their old normal movement speed and strengths. Uhlans have a slightly higher charge cap and 1.25 pursuit coefficient; their existing Exploit the Break trait applies once to impact. Their sustained melee remains weaker. Supporting fire, changing facing, numerical differences, difficult slopes, cavalry fatigue and other specialist combinations need larger seed sets and human playtesting.

Tests cover bounded range/acceleration, finite turning, short versus long run, weak/zero momentum, single impact with contact flicker and order spam, recovery locks, interruptions, frontal versus flank matchups, dense-forest disruption, pursuit movement/termination, shared budgets, morale/rally factors, deterministic tick groupings, and recoil that actually escapes contact. Movement, artillery, terrain, configuration and specialist regressions run in the complete suite.

Interactive: `python main.py --scenario charge`, `--scenario flank-charge`, or `--scenario cavalry-pursuit`. Select cavalry for phase/speed/momentum and use F3 for stored debug state. GUI validation uses SDL dummy rendering and screenshots; desktop interaction and Windows are not verified.

See `PERFORMANCE.md` for the matched 18/24/36/60-regiment timing matrix. No AI refresh cadence, terrain precision, spatial hash or fixed timestep was changed.
