# Army director, mounted reserves, and firing-formation preparation

This pass adds an army-level purpose above regimental decisions, fixes the
positioning/formation integration fault, and changes cavalry accompaniment.
Combat statistics, projectile physics, morale formulas and movement speeds are
unchanged. This is a modest tactical director, not an operational crossing planner.

## Authority and scheduling

The order of authority remains mandatory morale behaviour, explicit player orders,
authored scenario approaches/holds, then autonomous decisions. Existing strategies
and commander personalities remain available. Giving a cavalry regiment an explicit
attack still overrides autonomous reserve policy.

`ArmyDirector` reviews each active army at most every five simulation seconds.
Plans normally commit for 15 seconds; a threatened sector can interrupt that
commitment. Losing the designated reserve also invalidates the cached plan.
Configuring a different army strategy invalidates the plan immediately.

The director tracks observed contacts, the regular infantry body, a robust front
projection, mission focus, and a potential threatened sector. It uses only existing
perception: nearby spatial candidates and visible current targets. Hidden enemies
cannot contribute positions. Shared observed contacts may direct movement, while
individual shooting continues to require normal visibility.

Plans include Advance, Engage, Defend, Attack objective, Exploit, and Reinforce.
Regiment purposes include battle line, infantry reserve, screen/harassment, fire
support and mounted reserve. They feed the existing assignment system rather than
replacing combat execution. Starting lateral offsets keep individual purposes
spread across the frontage. Once an engagement is local, a generic army focus
leaves its execution to the regiment. Explicit mission assignments retain priority.

A balanced army with at least four formed infantry regiments can retain one infantry
reserve. It commits when a sector is threatened, a nearby enemy breaks, or frontline
losses exceed 15% of a regiment's entering strength. Commitment persists. This
replaces the previous fixed 75-second reserve release. Skirmishers do not define the
main line, and uncommitted reserves do not pull the main front backwards.

## Cavalry accompaniment

With a regular infantry body present, autonomous cavalry uses four intentions:

- **Accompany:** move behind a friendly wing as the infantry advances.
- **Reserve:** wait near that station and assess nearby opportunities.
- **Exploit:** commit to a suitable target and allow the existing charge lifecycle.
- **Recover:** return behind friendly infantry when cohesion/fatigue is unsuitable.

The first station is approximately 75 m behind a wing and 45 m outside it. Additional
horse regiments receive separate wings/lanes, offset by 45 m laterally and 25 m in
depth. A station changes only after its desired location moves more than 25 m;
arrival uses a 20 m tolerance. These values prevent small formation adjustments
from causing continuous contradictory orders.

A detached support assignment stations cavalry about 65 m behind the assigned
formation rather than behind the main army's wing. A distant defensive objective
does not pull cavalry ahead of its accompanying infantry. A specific reserve
assignment can specify its station directly.

Opportunities require suitable cohesion (at least 50), fatigue below the existing
pursuit limit minus 10, acceptable local support, and a genuinely exposed target:
a vulnerable formation, artillery, weaker cavalry, or an unprepared infantry flank.
Prepared infantry fronts are not made attractive just by waiting out a timer.

Maximum opportunity reach beyond the friendly front is 180 m for cautious, 250 m
for aggressive, and 220 m for other personalities, with a 350 m distance cap from
the horse regiment. Local overmatch tolerance uses the existing personality policy,
bounded to 1.1–1.8. A dense-forest midpoint (>0.5 density), steep midpoint (>0.16
gradient), or water-blocked swept approach rejects an opportunity.

A selected target receives a 20-second score preference, rather than being replaced
at every review. Active charges, pursuit, recoil and reformation remain owned by
the existing cavalry state machine. Crossing routes finish before a new reserve
station replaces the approach. Existing pursuit limits still apply; afterwards the
next autonomous decision returns cavalry to support.

Cavalry-only forces retain their earlier local charge policy because there is no
infantry body to accompany. The director does not calculate a coordinated route
around every intervening enemy formation or stage a bridgehead operation.

## Firing formations and strategic travel

The positioning routine now requests a proper firing formation before it can return
a movement order: line or the unit's skirmish formation within 1.35 weapon ranges.
Transitions retain their actual duration, cooldown and player pinning rules.

Long strategic approaches can request column when both the destination and closest
known threat are beyond 1.8 weapon ranges. They prepare firing formations again as
contact approaches. Existing crossing navigation continues to control necessary
crossing formations. This also avoids slow line marches surrendering an objective
before defenders can reach it.

A working battery retains its own position/deployment decisions when it has a
perceived target. A general fire-support purpose cannot continually limber it.

## Inspection and laboratory

The selected-regiment inspector now shows the actual army plan, regiment role and
mounted intention, alongside its existing assignment, target and support estimates.
The same fields and army goal are present in authoritative snapshots. `army_plan`
events describe phase changes; none are emitted each tick merely for maintaining
an unchanged plan.

Choose **AI: Army line and mounted reserves** (`ai-mounted-reserve`) in the existing
Live Mode scenario menu. Both armies have formed infantry, horse and artillery.
Watch the opening march and inspect the cavalry before and after the infantry
engagement. No new camera or mouse command scheme is introduced.

## Comparison against the exact previous AI

The baseline is the first tactical pass, not the original pre-port AI. Its two
source files were frozen before any implementation changes under
`migration_tools/ai_tournament/baselines/tactical-v1/`, with combined SHA-256:

`58dea1ad41ffade13fd895042eb6c04911192fc8f4ea6fe31a9f6a46cc0deaec`.

The evaluator compiles both controllers into an isolated simulation build and
dispatches Plan/Skirmish per army. Both sides share the current combat engine,
identical forces, matched officers and a fixed combat RNG stream. Every seed runs
both controller-side assignments. Different decisions legitimately consume the
stream differently. The playable source tree and user saves are not patched.

Main suite: ten seeds × six matchups × two side assignments = 120 battles, plus
24 same-controller controls. All 12 previous/previous controls exactly match the
actual previous engine's final positions, facing, strengths, morale, cohesion,
routing/withdrawal state, ending time, winner and RNG draw count.

| Matchup | Revised wins | Previous wins | Unresolved |
|---|---:|---:|---:|
| Line infantry | 18 | 1 | 1 |
| Combined arms | 20 | 0 | 0 |
| Blocked firing lanes | 3 | 9 | 8 |
| Wooded flanks | 18 | 2 | 0 |
| Concentrated support | 18 | 2 | 0 |
| Capture centre | 15 | 5 | 0 |
| **Total** | **92** | **19** | **9** |

That is 82.9% of resolved battles, or 76.7% of all games won. Unresolved matches
are never declared victories. The seed-block exploratory 95% score interval is
76.25–84.17% when unresolved games receive half a point only for the interval.

A final additional run on five fresh seeds (4507, 5003, 5501, 6007, 6503), after
freezing the implementation, produced **47 wins, 7 losses and 6 unresolved** over
60 games. Those seeds were not used for implementation adjustments. The layouts
remain the same six authored tests, so this does not establish strength on every
possible battlefield or army composition.

In the main suite, sampled unsupported cavalry time fell from **1,619 to 466
regiment-seconds (71.2%)**. The diagnostic requires two visible effective enemies
within 180 m and no effective formed friendly infantry within 160 m. It is sampled
once per simulation second. Cavalry still sometimes advances ahead during legitimate
exploitation: total ahead-of-front time was 7,387 versus 7,307 regiment-seconds.
Reduced dangerous isolation is not equivalent to never leaving the infantry line.

Mean charge starts per side rose from 0.175 to 1.408, and mean casualties fell from
576.1 to 466.9. These are outcomes of the combined formation and coordination changes,
not a controlled attribution to the director alone. In observed opening infantry
volleys, column openings fell from 353/480 to 70/480; preparation has improved but
is not an absolute ban on firing during every transition or constrained approach.

**Remaining regression:** the revised AI loses more blocked-lane matchups and often
runs past the 900-second evaluation budget. These are recorded as unresolved, not
forced wins. Dense infantry positioning and late-battle pursuit/engagement closure
need further work. Equal weighting of six test layouts is not a universal win-rate
prediction.

Reproduce:

```bash
.venv/bin/python -m migration_tools.compare_tactical_ai --baseline previous \
  --output benchmark-results/army-director-release
.venv/bin/python -m migration_tools.summarize_ai_tournament \
  benchmark-results/army-director-release
.venv/bin/python -m migration_tools.compare_tactical_ai --baseline previous \
  --seeds 4507 5003 5501 6007 6503 --control-seeds 0 \
  --output benchmark-results/army-director-release-additional
```

An explicit `--baseline 9a23276044df6526c7422c6777eef71bc1438732` still selects the
older original AI for historical comparisons. Default `previous` now means the
frozen tactical-v1 snapshot. Generated reports remain covered by the existing
benchmark-results ignore rule.

## Regression and performance validation

- **620 .NET tests passed**, including 17 new formation/director/cavalry checks.
- **570 Godot checks passed across 15 scripts**, covering AI inspection, campaign,
  camera, controls, environment, custom battles, replay and shared 2D/3D state.
- Repeat runs retain deterministic final-state checksums within each implementation.
- Campaign seed 31/interception completes all six battles with a decisive ending.
- Campaign seed 17/rescue wins stages 1–3, then loses the allied detachment in
  stage 4 at 76 simulation seconds. This is a genuine mission defeat, not a
  simulation timeout or forced result. The stronger enemy's opening fire makes this
  authored rescue scenario much less forgiving; escort planning and campaign
  deployment/balance need follow-up. No force-stat or mission-balance compensation
  has been applied. Controlled campaign progression/save/load tests for both
  branches still pass.

Release headless timings below compare the frozen previous engine against the
revised engine, alternating before/after runs, three repeats per count, reporting
medians. Each existing `benchmark-ai-N` workload measures 600 ticks after 100 warm-up
ticks. Tactical trajectories differ, so total timings include altered combat work.

| Regiments | Previous mean ms | Revised mean ms | Revised p95 ms | Revised ticks/s |
|---|---:|---:|---:|---:|
| 12 | 0.596 | 0.553 | 0.871 | 1806 |
| 24 | 1.096 | 1.149 | 1.680 | 870 |
| 36 | 1.618 | 1.910 | 2.819 | 523 |
| 60 | 2.572 | 3.247 | 4.915 | 308 |

Mean tick changes are approximately −7%, +5%, +18%, and +26%. The director increases
AI decision cost; at 60 regiments aggregate AI time over the workload rises from
218 to 513 ms. Total allocations rise from about 741 to 819 KB/tick at 60 regiments.
Throughput remains above 300 ticks/s on this machine versus the fixed 10 Hz realtime
simulation requirement. The overhead is real; caching generated role purposes is a
possible subsequent measured optimization. No new GPU frame-rate claim is made.

Raw validation logs and benchmark reports are in
`benchmark-results/army-director-validation/`; tournament results are in
`army-director-release/` and `army-director-release-additional/`. These generated
artifacts follow the existing ignore rules. All source tooling, frozen comparison
AI, scenario data and this report remain in the project.
