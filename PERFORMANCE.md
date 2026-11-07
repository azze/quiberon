# Battlefield performance

## Reproduce

Use the same Python build, machine, seed, terrain, warm-up and measured window. Run performance measurements without competing CPU-heavy jobs. Runtime measurements must have the profiler disabled.

```bash
python -m analysis.scaling --counts 24 --terrains "Mixed Terrain" --output benchmark-results/single.json
python -m analysis.scaling --frames 60 --output benchmark-results/before.json
python -m analysis.scaling --frames 60 --output benchmark-results/after.json --compare benchmark-results/before.json
python -m analysis.scaling --counts 24 --terrains "Mixed Terrain" --repeats 1 --profile-dir benchmark-results/profiles --output benchmark-results/profile.json
python -m pstats benchmark-results/profiles/24-Mixed_Terrain.prof
python -m analysis.scaling --counts 24 --terrains "Mixed Terrain" --frames 120 --paced --speed 1 --output benchmark-results/paced.json
python -m analysis.performance --config battle_config.json --warmup 300 --ticks 100 --profile
```

The default suite has 6, 12, 18, 24, 36 and 60 total regiments on a 1,000 × 600 m Open Field and Mixed Terrain battlefield. The two armies cycle through generic and specialist infantry/cavalry/artillery, use the existing balanced AI, and occupy the existing deployment grid. Caps are raised only to accommodate 60 regiments, without changing unit stats or battle rules. Seed is 17. Each repeat constructs a fresh battle, translates both deployments 130 m forward (without overlaps or stat changes), warms 100 fixed ticks (10 simulated seconds), then measures 100 ticks (10 simulated seconds). Repeat count defaults to two. Activity counters distinguish active combat from an inactive timing loop. A battle ending within the measured window is an error, not a cheap no-op sample.

JSON retains distributions, repeat timings, activity, state checksums and environment metadata. A companion CSV contains core timing columns. With `--profile-dir`, a separate replay writes cProfile dumps, cumulative/self-time summaries and query call counts. Profiled timings never enter the runtime samples. RSS is a process-wide high-water mark, including earlier cases and graphical allocations, not isolated per-battle memory consumption. Benchmark output belongs under `benchmark-results/` or a temporary directory, separate from source.

The optional graphics pass uses the actual Application update/draw loop, 1280 × 800 SDL dummy display, warmed terrain and a selected unit, once normally and once with F3 debugging. This matrix is unthrottled with supplied 1/60-second frame inputs: its FPS and simulated-seconds/wall-second ratio describe throughput, not desktop presentation or achieved speed at a real frame cap. Separate paced checks use actual clock intervals and a 60 FPS cap; SDL dummy results do not establish desktop-driver/vsync performance. Simulation and drawing timings are reported separately. First-frame terrain painting is kept separate from warmed draw timings.

Exact-state checksums cover regiments (including orders, trait timers and analysis), RNG, events, projectiles, terrain and rules. Additional regression snapshots cover effects, melee cooldowns, pending/history commands and defeat timers. No terrain precision or AI refresh-frequency approximation is required for a pure implementation optimization.


## Environment and baseline

Measured locally on Linux x86-64, AMD Ryzen 5 7600X3D (6 cores / 12 logical CPUs), Python 3.14.8, pygame-ce 2.5.8 / SDL 2.32.10. The simulation remains single-threaded. These measurements are environment/workload-specific, with no machine-speed assertions in tests. GUI checks use SDL's dummy driver, not a physical desktop/vsync driver.

Before changing the engine, all 291 existing tests passed. An initial 24-regiment mixed-terrain profile (50 ticks, ordinary deployment) spent about 87% of cumulative tick time in perception/visibility. In the matched staged 60-regiment profile (20 ticks), raw sight rays accounted for most of the cost: 147,867 visibility requests produced 40,925 ray casts, 1.30 million height queries and 1.16 million forest-density queries. Artillery spotting amplified repeated requests; clearing the entire 4,096-entry sight cache caused avoidable churn. Every movement intent also eagerly evaluated visibility to all enemies even though only the nearest visible enemy was used.

The 60-regiment open-field profile ranked firing target/obstruction tests first (roughly one third of cumulative tick time), followed by morale, congestion and separation. Debug rendering showed 331,300 temporary vector constructions and 12,800 font renders over 100 frames. It was smaller than the simulation bottleneck. Projectiles were only about 0.2% of the pre-change mixed-terrain profile and 0.9% afterward, so their physics, substeps and traversal were left unchanged.

An earlier, ordinary-deployment window warmed 600 ticks and timed 100, with two repeats: mixed-terrain means at 12/18/24/36 regiments were 5.94/12.80/22.82/49.20 ms. The final 60-regiment case failed to finish its repeated warm-up/render passes within a five-minute case budget and was interrupted. Those results are separate from the staged benchmark below; the shorter staged protocol makes full-suite iteration practical and exercises firing/projectiles immediately. Do not compare the two windows as an optimization result.

## Matched before/after measurements

Every table uses seed 17, the same staged roster/geometry, 100 warm-up ticks, 100 measured ticks and two repeats. Tick timings exclude profiler, warm-up, fingerprints and rendering. All 12 end-state checksums match exactly. Activity counters at the end include volleys, casualties, charges, routs/rallies and friendly fire; active projectiles are sampled during the measured window. The smaller rosters cannot contain all nine archetypes, and terrain occlusion/composition differ as counts increase, so these are workload scaling observations rather than a fitted asymptotic complexity proof.

### Open Field (milliseconds per tick)

| Total units | Mean before | Mean after | p95 before | p95 after | Speedup |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 0.26 | 0.24 | 0.30 | 0.26 | 1.08× |
| 12 | 0.78 | 0.61 | 0.86 | 0.66 | 1.27× |
| 18 | 1.75 | 1.27 | 1.89 | 1.35 | 1.38× |
| 24 | 3.39 | 2.25 | 3.58 | 2.35 | 1.51× |
| 36 | 8.23 | 5.27 | 9.11 | 5.79 | 1.56× |
| 60 | 16.66 | 10.35 | 21.88 | 12.67 | 1.61× |

### Mixed Terrain (milliseconds per tick)

| Total units | Mean before | Mean after | p95 before | p95 after | Speedup |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 1.56 | 0.59 | 1.96 | 0.82 | 2.64× |
| 12 | 1.89 | 1.06 | 2.45 | 1.39 | 1.79× |
| 18 | 9.28 | 5.47 | 11.57 | 6.50 | 1.70× |
| 24 | 15.19 | 8.48 | 21.28 | 9.28 | 1.79× |
| 36 | 42.90 | 18.22 | 64.69 | 21.78 | 2.35× |
| 60 | 156.87 | 41.60 | 190.78 | 48.67 | 3.77× |

Ten simulated seconds at 60 regiments in Mixed Terrain took **15.69 wall seconds before**, **4.16 wall seconds after** (6.37 → 24.04 ticks per wall second). That is useful headless capacity for normal speed, but does not imply 60 FPS or fast-forward capacity. In this workload, 24→60 regiments increased mixed-terrain cost 10.3× before and 4.9× afterward. Open-field 12→24 cost increased 4.3× before and 3.7× afterward. Scaling remains nonlinear; visibility through obstructed terrain and allied spotting are still costly.

### Warmed rendering

Real Application update/draw, 60 unthrottled frames, active warmed battlefield, 1280 × 800; simulation update time is separate. Times below are drawing only.

| Units / Mixed Terrain view | Mean before ms | Mean after ms | p95 before ms | p95 after ms |
| --- | ---: | ---: | ---: | ---: |
| 24 / normal | 2.10 | 1.84 | 2.26 | 1.99 |
| 24 / debug | 2.88 | 2.25 | 3.17 | 2.53 |
| 60 / normal | 2.99 | 2.77 | 3.50 | 2.73 |
| 60 / debug | 5.14 | 3.93 | 8.19 | 6.47 |

First mixed-terrain terrain painting is still about 0.2 s and is excluded from warmed draw statistics. Panning/zooming invalidates the viewport image as before. Process high-water RSS across the whole suite was about **74 → 100 MiB**; this includes native Pygame allocations and prior cases, and is not an isolated per-battle memory comparison. The higher exact-cache limits trade bounded memory for fewer repeated calculations.

### Paced viewer checks

60 actual-clock frames per case, 60 FPS cap, same warm-up/staged state; ratios include endpoint fractional-tick effects. Before used the old discarded-debt policy; after retains and reports the backlog. FPS is measured dummy-display loop FPS, not a guarantee for a desktop renderer. Debug results and distributions are in generated JSON; normal-view summaries follow.

| Units | Requested speed | FPS before | FPS after | Achieved speed before | Achieved speed after | Pending sim seconds after |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 24 | 1× | 60.6 | 61.8 | 0.91× | 0.93× | 0.07 |
| 24 | 2× | 60.3 | 62.0 | 1.91× | 1.96× | 0.03 |
| 24 | 4× | 56.9 | 61.6 | 3.89× | 3.90× | 0.06 |
| 24 | 10× | 55.1 | 59.8 | 5.51× | 7.87× | 2.03 |
| 60 | 1× | 6.6 | 43.1 | 0.59× | 0.93× | 0.09 |
| 60 | 2× | 6.5 | 29.3 | 0.62× | 1.96× | 0.01 |
| 60 | 4× | 6.3 | 23.2 | 0.62× | 2.28× | 4.27 |
| 60 | 10× | 6.2 | 23.3 | 0.62× | 2.33× | 19.36 |

A separate 30-regiment mixed-terrain probe measured 12.11 ms mean / 15.16 ms p95 ticks, with normal/debug paced loops around 60.5/60.2 FPS at 1×. It has no matching pre-change 30-unit measurement and is not included in speedup comparisons. Thus **20–30 units at normal speed is practical on this hardware in these tests**. The 36-unit case needs longer frames; 60 mixed-terrain units can keep roughly normal simulated speed but still show visible frame spikes and limited fast-forward. Larger maps, different terrain seeds, later battle phases and desktop drivers need further sampling.

## Implemented algorithms and invalidation

- **Lazy exact nearest-visible search:** stable-sort enemy candidates by the original centre distance and stop at the first visible one. A live designated enemy avoids the unused nearest-enemy search entirely. Equal-distance ties preserve input order. There is no visibility radius cutoff, delayed target acquisition or changed tactical choice.
- **Exact LOS LRU:** 32,768 directed position-pair results per Battle, replacing whole-cache clears at 4,096 entries. Coordinates are not rounded and rays are not reversed. Terrain/rules object replacement invalidates the cache. Woodland concealment is applied from current target data after the raw result, and artillery allied spotting remains sensitive to current friendly effectiveness. No cached RNG or perception scheduling is introduced.
- **Conservative spatial hash:** 100 m cells containing bounding-circle AABBs, epsilon-expanded at boundaries. Candidate pairs and segment queries return original list-index order. Used for congestion, fixed-geometry melee contact, overlap-group construction and ranged obstruction candidates. A 1.5 m bound conservatively covers the existing 0.75 m contact tolerance. Moving enemy separation deliberately retains its original ordered traversal; projectile physics is untouched. Small lists keep a linear pair scan to avoid index overhead.
- **Exact terrain samples:** at most 2,048 footprint samples per terrain instance, keyed by exact position/facing/width/depth. Cached forest density/gradients are reused for stationary and straight-moving repeated queries; heading, unit traits and rules are applied freshly. Private cache fields do not participate in equality, hashes, checksums or configuration serialization. Height math retains the original expression order and Python float-sum behaviour; scalar forest evaluation removes redundant calls/temporary generators without altering feature results.
- **Rendering:** bounded 512-entry text surface cache; debug arc projection keeps the same arithmetic order while avoiding temporary vectors. Existing static terrain/viewport and smoke caches remain. No simulation logic moves into rendering.

In a matched 60-unit, 20-tick mixed-terrain cProfile replay, total profiled time fell **9.39 → 2.14 s**. Raw visibility casts fell **40,925 → 13,694**, height queries **1,300,251 → 328,479**, forest-density queries **1,162,672 → 289,417**, and slab obstruction checks **24,986 → 7,589**. Strategic and simulation update schedules are unchanged. These call counts are from a 20-tick profile, not the 100-tick unprofiled timing window.

## Timestep and overload policy

Simulation dt stays 0.1 s. Viewer work still has an approximate 8 ms/four-tick per-frame budget, allowing one indivisible tick to overrun. The old policy discarded whole accumulated ticks and capped elapsed contributions at 0.25 s. **The new policy retains all elapsed simulation demand**, shows pending simulation seconds in the HUD, and processes the backlog within subsequent frame budgets. Camera panning alone still caps its visual elapsed contribution. Reducing requested speed no longer silently erases previous debt; pausing freezes it, restarting resets it. Rendering clamps interpolation to current state when behind. Sustained overload is reported as limited achieved speed and growing pending time, not fixed-dt changes.

This is the only intentional timing-behaviour change. Combat balance, AI tactical rules/cadence, movement/collision order, terrain precision, RNG call order and projectile integration are preserved at matching ticks. Orders issued at matching simulation ticks reproduce the same battle. No approximate position buckets, height grids, reduced LOS resolution, throttled AI or live multithreading were added.

## Validation and next priorities

All 300 tests pass after the change (291 existing tests before). Added guards cover conservative spatial queries, reference all-pairs tick equivalence, lazy stable target choice, exact cache invalidation/bounds, original feature-method numerical equality, terrain cache isolation from serialization, CLI JSON/CSV/profile/comparison output and full elapsed-time catch-up. All 12 benchmark state checksums match. Three longer 1,000-tick replays, including targeted commands and a cavalry matchup, match before/after checkpoints for regiment/RNG/event/projectile data plus effects, melee cooldowns, pending/history commands and defeat timers.

Remaining work is mainly obstructed visibility and artillery spotting, then the still-quadratic mutable enemy-separation pass. Exact batching/shared work is preferable before considering an approximate height grid or slower perception cadence. Such approximations would require separate error bounds and gameplay validation. Debug culling/cached paths and projectile spatial filtering are lower priorities in these profiles. Expand testing to longer terrain battles, other seeds, Vast maps, offscreen camera positions, sustained high-speed overload and a real desktop driver before claiming smooth 40–60-unit play generally.

## Friendly traffic and firing-frontage revision (2026-11-01)

The preceding optimization results describe the earlier revision. The following measurements compare that optimized baseline against the new direction-sensitive congestion, stationary settling, pursuit lanes and friendly musket-frontage rules. This is an intentional gameplay change: casualty/RNG progression and battle fingerprints can change. Each new benchmark independently verifies identical fingerprints across its two repetitions; cross-revision fingerprint equality is not claimed.

Same machine/runtime: AMD Ryzen 5 7600X3D, Python 3.14.8, Linux x86_64, seed 17, `forward130-v1`, 100 warm-up ticks followed by 100 measured ticks, two fresh repetitions per case, no profiler or concurrent test suite. Each measured window is ten **simulated** seconds. Values below are **mean / p95 milliseconds per simulation tick**, with mean runtime change in the final column. Raw local reports are `benchmark-results/traffic-before.json` and `traffic-after.json`, with companion CSVs; generated reports stay outside source packages.

| Regiments | Terrain | Before mean / p95 | After mean / p95 | Mean change |
| --- | --- | --- | --- | --- |
| 18 | Open Field | 1.32 / 1.43 | 1.38 / 1.49 | +4.2% |
| 24 | Open Field | 2.33 / 2.51 | 2.48 / 2.68 | +6.4% |
| 36 | Open Field | 5.40 / 5.85 | 5.85 / 6.58 | +8.2% |
| 60 | Open Field | 10.62 / 12.90 | 11.66 / 14.51 | +9.7% |
| 18 | Mixed Terrain | 5.82 / 6.93 | 5.77 / 7.42 | -0.9% |
| 24 | Mixed Terrain | 8.72 / 10.11 | 8.73 / 9.71 | +0.2% |
| 36 | Mixed Terrain | 19.08 / 22.92 | 18.92 / 22.25 | -0.9% |
| 60 | Mixed Terrain | 43.12 / 50.35 | 42.45 / 49.70 | -1.5% |

Small mixed-terrain differences are measurement variation plus changed battle activity, not a new optimization claim. Open-field overhead is measurable, up to about 1.0 ms/tick at 60 units, while the prior multi-fold improvement is retained. Twenty-four units remain comfortable in this headless sample; 60 mixed-terrain units remain expensive for render-frame pacing and fast-forward even though their mean tick fits the 100 ms normal-speed interval. These short active windows do not establish worst-case performance in long battles.

A separate 120-frame paced SDL dummy-display check at normal speed measured 24 mixed-terrain units at 62.1 FPS normally / 62.0 with debug, with drawing at 2.01 / 2.53 ms per frame and achieved speed about 0.98×. At 60 units it measured 44.7 / 43.5 FPS, drawing at 3.01 / 4.72 ms and achieved speed about 0.97–0.98×. These are **after-only** graphics measurements, not a before/after graphics speedup; live desktop drivers remain untested. The three new demonstrations also passed read-only debug-render smoke checks and screenshot inspection at 1280 × 800.

The pre-move congestion pass returns its existing intersection pairs for settling, avoiding another overlap scan. Velocity costs use worst-pair rather than additive penalties. Separation searches run only after persistent overlap, have at most 24 candidates, and reuse spatial candidates with cooldowns and endpoint reservations. Actual volley attenuation uses the fixed-phase firing index; it is not calculated for every AI target candidate. LOS caches, terrain precision, enemy contact traversal, fixed timestep, AI cadence and projectile physics are unchanged.

Reproduce the timing matrix with:

```bash
python -m analysis.scaling --counts 18 24 36 60 --frames 0 --output benchmark-results/traffic-current.json
python -m analysis.scaling --counts 18 24 36 60 --frames 0 --output benchmark-results/traffic-next.json --compare benchmark-results/traffic-current.json
python -m analysis.scaling --counts 24 60 --terrains "Mixed Terrain" --frames 120 --paced --repeats 1 --output benchmark-results/traffic-graphics.json
pytest -q tests/test_formation_traffic.py
```

Traffic regression coverage includes velocity versus facing, overtaking, opposite-direction crossings, explicit common destinations, three stationary lines, no-space retries, dense/loose/flank/high-ground firing lanes, exclusion of active attacks and withdrawal, deterministic replays and a 36-regiment crowded firefight. The crowded firefight starts with 18 coincident same-army pairs: after 60 simulated seconds it has zero substantial friendly overlaps, 126 volleys and 502 casualties. Two Uhlans pursue slower routing cavalry in seeds 1, 7 and 31, making contact at 48.3 simulated seconds around x=541 m; their minimum aligned overlap multiplier after startup is 0.9901 and cohesion at contact is 91.5–95.8. This does not guarantee catching equal-speed enemies, escaping enemy encirclement, or optimal packing in a full battlefield.

Final regression run: **315 passed in 41.51 seconds**, including the existing movement, specialist, morale, terrain, artillery, configuration and rendering tests. Desktop interaction and Windows remain untested. New traffic rules intentionally supersede the old tests requiring exact shared stopping points or unrestricted volleys through connected source overlaps; original requested Order destinations and target vulnerability remain covered.

## Cavalry charge/pursuit revision (2026-11-01)

This revision starts from the optimized traffic system plus the broken-unit melee correction. It introduces conditional accelerated impact, recoil/reforming, morale-dependent melee and distinct aggregate pursuit. Old outcomes/RNG progression intentionally change; checksums are expected to differ across revisions. Each timed case still verifies identical fingerprints across its two current-version repeats, and tick-grouping regressions cover new cavalry fields and engagements.

Same Ryzen 5 7600X3D, Python 3.14.8 and Linux environment; `forward130-v1`, seed 17, 100 warm-up plus 100 measured fixed ticks, two repeats, profiler disabled, no concurrent CPU-heavy work. Ten simulated seconds are measured per repeat. Values are **mean / p95 milliseconds per tick**. Raw files are `benchmark-results/cavalry-before.json`, `cavalry-after.json` and their CSV companions.

| Regiments | Terrain | Before mean / p95 | After mean / p95 | Mean change |
| --- | --- | --- | --- | --- |
| 18 | Open Field | 1.40 / 1.55 | 1.47 / 1.67 | +4.9% |
| 24 | Open Field | 2.57 / 2.82 | 2.58 / 2.87 | +0.4% |
| 36 | Open Field | 5.99 / 6.68 | 6.04 / 6.98 | +0.8% |
| 60 | Open Field | 11.73 / 14.73 | 11.68 / 14.59 | -0.4% |
| 18 | Mixed Terrain | 5.88 / 7.19 | 5.06 / 6.75 | -13.9% |
| 24 | Mixed Terrain | 9.09 / 10.21 | 8.58 / 9.86 | -5.6% |
| 36 | Mixed Terrain | 19.38 / 23.05 | 18.97 / 22.66 | -2.1% |
| 60 | Mixed Terrain | 43.75 / 52.00 | 42.57 / 49.24 | -2.7% |

The prior performance gain is preserved in this window. Small timing differences include run variation and changed combat activity, especially at 18 mixed-terrain units; this is **not** a new speedup claim. The short staged window mainly exercises approach/movement, musket fire and batteries, not a whole battle's cavalry phases. Sixty mixed-terrain units still have substantial frame spikes and limited fast-forward capacity.

A separate **after-only** Open Field window, 20–50 simulated seconds (200 warm-up / 300 timed ticks, two repeats), exercises actual impacts and routs: 36 units measured 6.12 / 6.91 ms mean/p95 with eight impacts and eight routs by the endpoint; 60 units measured 19.39 / 21.97 ms with 14 impacts, nine routs and up to 14 active projectiles. All units remained active in the sampled averages. This later, more active workload has no matching old-revision baseline and is not a speedup comparison. Results are in `benchmark-results/cavalry-late.json`.

After-only paced SDL dummy-display checks (120 frames at 1×, Mixed Terrain) measured 24 units at 62.2 FPS normally / 62.1 debug, with drawing at 2.01 / 2.64 ms; 60 units measured 43.7 / 42.9 FPS and 3.08 / 4.93 ms drawing. Achieved simulation speed was about 0.97–0.98×. See `benchmark-results/cavalry-graphics.json`. These short dummy-display checks do not establish live desktop/vsync performance.

The state update uses each cavalry unit's existing selected target and stored terrain samples. Impact calculation runs only at physical contact. Close pursuit groups only current pursuers by target and resolves one interval budget; it does not coordinate every regiment with every other regiment or recast terrain LOS. Existing spatial queries, exact LOS/terrain caches, collision traversal, AI scheduling and dt remain. No live parallelism, precision reduction or approximate LOS cache was added. Charge/morale/pursuit mechanics intentionally alter gameplay, in contrast with the behaviour-preserving optimizations documented earlier.

The full suite passes **353 tests**, including the prior 327 plus charge acceleration/turning, momentum and impact locks, interrupts, recoil/recovery, state effectiveness, shared pursuit intervals, lost-contact/exhaustion termination, specialist traits, mirrored forests and fixed-seed replays. The balance harness runs 80 final seeded/side-swapped encounters and records casualties, duration, impacts and pursuit counters in `benchmark-results/cavalry-balance-after.json`; methodology, the discarded baseline mirrored-forest samples and role results are in `analysis/cavalry_notes.md`. New charge/pursuit/recoil scenes also passed read-only dummy-display rendering with screenshot inspection. Desktop drivers and Windows remain untested.

```bash
python -m analysis.scaling --counts 18 24 36 60 --output benchmark-results/cavalry-current.json
python -m analysis.scaling --counts 18 24 36 60 --output benchmark-results/cavalry-next.json --compare benchmark-results/cavalry-current.json
python -m analysis.cavalry_balance --runs 5 --output benchmark-results/cavalry-balance.json
pytest -q tests/test_cavalry.py tests/test_routing_melee.py
```

## Fixed-scale maps and woodland/infantry update

New maps keep feature radii in metres and add features with field area. Mixed Terrain now grows from 2 hills/2 forests (600 × 400 m) to 125/100 (4,800 × 3,000 m). This increases terrain work. Profiling the first 24-infantry Vast tick found sight queries dominated, particularly analytic height evaluation on long hidden rays.

The implementation uses exact static 200 m feature candidates for larger feature collections. Newly generated hills use smooth finite-support polynomial profiles; legacy Gaussian/custom features remain global candidates, retaining their original surfaces. Forest queries are exact. Opaque sight rays terminate as soon as the observer's effective vegetation depth blocks sight; their cache key includes exact endpoints and observer/target opacity. Visible sample results remain exact. There is no height grid, truncated Gaussian tail, RNG scheduling, fixed-timestep change or reduced AI cadence.

A matched 24-regiment Medium Mixed Terrain benchmark (seed 17, forward130-v1, 100 warm-up/100 measured ticks, two repeats, no competing heavy work) measured **8.54 → 8.50 ms mean tick time**. Raw files: `benchmark-results/terrain-update-before.json` and `terrain-update-after.json`, plus CSV. Generated terrain and woodland behaviour intentionally change, so this is a representative performance check rather than exact old-outcome equivalence.

A separate after-only Vast check used 12 standard infantry per side, seed 17, both armies controlled by AI, and the first five ticks including the initial army plan. Mixed Terrain averaged **91.9 ms/tick** (first 106.0 ms, subsequent about 88–89 ms); Wooded Battlefield averaged **23.3 ms** (first 43.1 ms, subsequent about 18.3 ms). These short, different workloads have no matching old-map baseline and are not speedup claims. Dense Vast fields remain costly, with visible tick spikes and limited fast-forward; cached drawing cannot fix this simulation bottleneck. Further work should target long-distance hidden-enemy acquisition on large fields without degrading local firing visibility.

At 1280 × 800 with SDL dummy, a default 12-regiment Vast Mixed Terrain frame took **977 ms initially** to paint terrain and **1.17 ms warmed**. Screenshots and read-only fingerprints verified that drawing Vast terrain and active bayonet charges does not mutate authoritative state. Desktop drivers and Windows remain untested.

All **376 tests pass**, including fixed-scale count/size checks, all Vast preset deployments, exact spatial-query equivalence, smooth compact gradients, legacy hill loading, observer-aware opaque-ray exit, high-ground melee, woodland firing and morale context, infantry rushes/impact limits, controls, saved charge orders and fixed-seed frame-group replays. Existing cavalry, artillery, movement and setup regressions pass. Detailed local checks are in `benchmark-results/terrain-units-checks.json` and `terrain-large-final.json`.

## Named commander revision (2026-11-01)

Measured on the same host/Python 3.14.8 environment as the preceding sections. The baseline was recorded **before commander integration**, not taken from older optimization reports. Both runs use `forward130-v1`, seed 17, the same mixed archetype roster, Medium field, 100 warm-up ticks, 100 measured ticks (10 simulated seconds), two repeats, no profiler and no competing simulation/test process. Timing starts after commander/map generation. Raw JSON/CSV: `benchmark-results/commanders-before.*` and `commanders-after.*`.

| Total regiments | Terrain | Before mean ms/tick | After mean | Before p95 | After p95 | Mean change |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 18 | Open | 1.463 | 1.625 | 1.546 | 1.747 | +11.1% |
| 24 | Open | 2.586 | 2.867 | 2.797 | 3.497 | +10.9% |
| 36 | Open | 6.019 | 6.439 | 6.862 | 7.248 | +7.0% |
| 60 | Open | 11.905 | 12.291 | 14.879 | 15.467 | +3.2% |
| 18 | Mixed | 4.144 | 5.226 | 5.233 | 5.624 | +26.1% |
| 24 | Mixed | 8.520 | 8.827 | 9.562 | 9.997 | +3.6% |
| 36 | Mixed | 18.790 | 19.848 | 21.775 | 23.150 | +5.6% |
| 60 | Mixed | 53.611 | 52.062 | 59.968 | 65.023 | -2.9% |

This is a new gameplay feature, so old/new state hashes intentionally differ: officers alter movement, decisions, morale and firing. It is **not** an exact behaviour-preserving optimization comparison. Every after-run repeat separately checks identical replay fingerprints. The small apparent improvement at 60 Mixed is not a speedup claim; changed battle activity and measurement noise affect timings.

The 18 Mixed outlier was repeated three times before the final unused-aura query guard: means 5.139/5.023/5.096 ms. Its profile (`benchmark-results/commander-profiles/18-Mixed_Terrain.txt`) attributed about 0.832 s of 1.323 s profiled self-runtime to the cumulative visibility path; commander helper self time was 0.0093 s (<1%). Its measured-window activity changed from 28 volleys/2 charges/108 casualties to 26/1/96. This suggests altered positions and visibility workloads account for much of the extra work, rather than expensive trait arithmetic alone; the old run was not profiled here, so this attribution is not a fully isolated proof. Aura support adds some sight work. An exact optimization skips aura visibility for already-full-morale receivers, while still checking support for later rout shocks. No AI frequency, timestep, range, terrain precision or spatial-query ordering was changed for speed.

The added work is mostly constant-time hooks in existing calculations. Personality planning reuses detected enemies at the existing five-second schedule; pursuit breakoff examines only its current target. Morale uses one prefiltered, stable source list and takes the strongest visible aura rather than scanning all friend pairs for every trait. Existing spatial hashes and terrain/visibility/formation caches remain intact. There is no per-frame commander simulation or global commander target search.

An after-only **24-regiment Mixed**, 1280×800 SDL dummy paced check (120 frames per mode) measured warmed drawing **2.15 ms mean / 2.45 ms p95** normally and **2.69 / 3.11 ms** with debug. Both ran about 62 loop FPS and 0.98× achieved simulation speed at requested 1×, with no budget-limited frames. First terrain painting took about 240 ms. These are short software-driver checks, not a desktop GPU or Windows guarantee; raw data are in `commanders-graphics.json`. Normal-speed 24-regiment battles remain comfortably within the 100 ms simulation budget here. Sixty-regiment mixed battles remain feasible headlessly at normal speed (~52 ms/tick) but have long indivisible ticks and limited fast-forward; large-map sight acquisition remains a higher-value optimization target than commander arithmetic.

Reproduce these checks with:

```bash
python -m analysis.scaling --counts 18 24 36 60 --output benchmark-results/commanders-next.json --compare benchmark-results/commanders-after.json
python -m analysis.scaling --counts 18 --terrains "Mixed Terrain" --repeats 3 --profile-dir benchmark-results/commander-profiles --output benchmark-results/commander-profile-check.json
python -m analysis.scaling --counts 24 --terrains "Mixed Terrain" --repeats 1 --frames 120 --paced --output benchmark-results/commander-graphics-next.json
python -m analysis.commander_comparisons --runs 2 --seed 17 --duration 180 --output benchmark-results/commander-comparisons.json
```

### Initial commander experiments

Twenty mirrored runs used combat seeds 17–18, fixed officer/map seed 17 and up to 180 simulated seconds. Eighteen hit the time limit; only two Cavalry Personalities runs ended in victory. These small samples exercise decisions and integrations, and do not establish overall win-rate balance.

| Comparison (original blue / original red, normalized after side swaps) | Observation across four runs |
| --- | --- |
| Methodical / Aggressive, identical infantry and neutral open-ground specialty | Methodical averaged 98.46 final cohesion versus 97.21; aggregate movement 244.6 versus 280.3 regiment-seconds; losses 220.5 versus 211.5. No charges or routs in this short firing-line sample. |
| Cavalry personalities | All officers completed one charge on average. Per-regiment losses averaged 37.75 Aggressive / 33.12 Cautious / 38.75 Opportunistic. Twelve routs and four rallies occurred across the four battles; placement strongly affects individual results. Controlled tests, rather than these confounded casualties, establish commitment/pursuit differences. |
| Stalwart defensive officers, four infantry against six Aggressive | Defenders lost 278.5 on average and inflicted 231.75; cohesion 97.53 versus 95.67. They remained viable at the limit, with defensive stabilization events; this does not prove they could win. |
| Pathfinder infantry / control infantry in woods | Average losses 120.25 versus 121.0; near-equal final cohesion. Route avoidance and recovery obscure the benefit in this preset. Direct terrain-cost tests establish faster wooded movement/lower disruption; the preset does not yet show a decisive combat advantage. |
| One Inspirer supporting otherwise identical infantry | Supported side lost 166 versus 201.5 on average; support activated. No routs occurred, so this sample cannot establish cascade resistance (covered by controlled aura/rout tests). |

The complete JSON includes identities, per-regiment actions and recent events. Results are deliberately reported as observations, with no balance/stat inflation to force a desired winner. Next balance work should use longer, role-specific engagements, fixed approach lanes for Pathfinder comparisons, threatened/routing support tests and more seeds. No campaign, commander levelling or unrelated AI redesign was added.

Final validation: **436 tests passed** (46.87 s), including generation, immutable identity/compatibility, old/new JSON, all eight specialties, aura caps, AI decisions/cooldowns, explicit-order priority, deterministic state/event/RNG replays, deployment transactions, legacy/configured rematches and read-only drawing at 960×640 and 1280×800. The normal preset CLI launched with SDL dummy, and the existing headless batch tool ran a commander preset successfully. Desktop hardware rendering and Windows were not exercised.

## Threat-aware flight and battery salvos (2026-11-03)

Field/horse batteries now launch six/four independent balls at full crew strength, scaling down with casualties. Flight replans only routing units once per simulated second; perception is range-filtered before evaluating escape headings. No new dependencies, timestep changes or live parallel simulation were introduced.

An after-only `forward130-v1` smoke benchmark used seed 17, 100 warm-up ticks, 100 measured ticks, one repeat per configuration. Results are in `benchmark-results/battery-salvos.json` and CSV:

| Regiments | Terrain | Mean tick ms | p95 ms | Peak active balls |
| ---: | --- | ---: | ---: | ---: |
| 24 | Open Field | 2.93 | 3.72 | 28 |
| 60 | Open Field | 12.55 | 18.61 | 51 |
| 24 | Mixed Terrain | 10.23 | 14.79 | 28 |
| 60 | Mixed Terrain | 54.44 | 67.20 | 42 |

These are short current-build budget checks, not isolated before/after optimization claims: battery volume, casualties, morale and routing deliberately change the workload. The measured window includes one rout at 24 Mixed, so the dedicated routing tests are the stronger flight correctness checks. A 1280×800 SDL dummy smoke check rendered a six-ball salvo, displayed the gun count and verified an unchanged authoritative-state fingerprint. Desktop driver performance was not tested for this update.

## Woodland combat and routing disorder

The woodland update reuses cached footprint samples and existing visibility results. It adds no new LOS rays, global scans, pathfinder or rendering-side simulation. Forest melee context is computed only at contact resolution/charge impact; commander estimates retain the existing planning cadence. Routing cohesion uses the existing shared recovery hook.

An after-only Mixed Terrain `forward130-v1` check (seed 17, 100 warm-up ticks, 100 measured ticks, one repeat, no concurrent simulation/test process) measured **24 regiments: 9.70 ms mean / 14.85 ms p95**, and **60 regiments: 52.18 / 64.41 ms**. Raw data: `benchmark-results/woodland-performance.json` and CSV. These remain within the 100 ms tick budget in this short window; this is not an isolated speedup comparison because terrain combat and AI behaviour intentionally changed. Large-map and fast-forward limits remain as previously documented.

All **500 tests pass**, including routing cohesion bounds and grouped-frame determinism, directional treeline protection, off-ray/thin cover, opaque targets, terrain-dependent melee/formation factors, favourable ambush commitments versus depleted/exposed withdrawal, cautious commander terrain estimates and complete woodland replay fingerprints. A 1280×800 SDL dummy graphical combat/debug smoke test retained an unchanged authoritative fingerprint.

Calibration uses `analysis.woodland_balance`, fresh units without commanders, seed ranges 17–21 before and 17–26 after, mirrored sides, and a 450 simulated-second limit. Dense (1.0) woodland specialist ranged/melee/autonomous matches all won 20/20; light (.45) ranged/autonomous won 19/20 and melee 20/20. Open controls lost 20/20 in each mode. Ordinary matched treeline infantry won 20/20 dense and 18/20 light. The baseline had zero wins in ten matched treeline, wooded-ranged and wooded-melee cases. These are representative tactical matchups rather than universal guarantees. Compare altered setups or add seeds with:

```bash
python -m analysis.woodland_balance --runs 10 --output benchmark-results/woodland-after.json
python -m analysis.woodland_balance --density .45 --runs 10 --output benchmark-results/woodland-light-after.json
python -m analysis.scaling --counts 24 60 --terrains "Mixed Terrain" --repeats 1 --output benchmark-results/woodland-performance.json
```

## Campaign and acquired commander upgrades (2026-11-03)

The campaign is a menu/state layer around the existing simulation. Initialization/rewards/saves are outside timed battle ticks. Upgrade hooks modify existing formation, recovery, morale, fire, artillery and charge calculations; there is no additional global decision loop or new simulation frequency. Event-limited support checks reuse the firing index and visibility cache. Unit preparation timers update only when a commander actually has acquired upgrades.

The same host/environment described above was used: Python 3.14.8, Ryzen 5 7600X3D, Linux; `forward130-v1`, Mixed Terrain, seed 17, 100 warm-up ticks then 100 measured ticks (10 simulated seconds), **one repeat**, profiler off and no concurrent simulations/tests. Raw JSON/CSV: `benchmark-results/campaign-before.*`, `campaign-after.*`. Single-repeat differences are timing noise, not claimed speedups.

| Total regiments | Before mean / p95 ms | After mean / p95 ms |
|---|---:|---:|
| 18 | 5.00 / 8.38 | 4.79 / 8.33 |
| 24 | 10.07 / 15.15 | 9.95 / 15.01 |
| 36 | 20.92 / 29.71 | 20.21 / 29.30 |
| 60 | 55.62 / 69.43 | 54.13 / 67.26 |

All four generic-battle state checksums match the baseline, including regiment state, combat RNG and event logs. The fingerprint canonicalizer omits only the newly introduced **neutral defaults** (empty commander upgrades/activation state and a zero preparation timer), making comparisons with pre-campaign snapshots meaningful. Active upgrade state and shared inspiration cooldowns remain part of the fingerprint. No AI cadence, timestep, targeting, terrain sampling or unit balance was changed for performance.

A separate after-only workload gives **every** regiment three compatible acquired upgrades, including many morale sources: 24 regiments **10.91 / 15.88 ms**, 60 regiments **56.39 / 68.72 ms**, two repeats of the same warm-up/window. Raw data: `benchmark-results/campaign-upgraded.json`. This changes combat behaviour, so it is not an isolated measurement of function-call overhead. The 24-regiment SDL dummy viewer measured mean draw **2.23 ms** normally and **2.58 ms** with debug (p95 **2.45 / 2.84 ms**), after terrain-cache warm-up; its first frame was about **257 ms**. These are software/dummy rendering measurements, not desktop/vsync FPS. Normal-speed 20–30-regiment battle ticks remain comfortably below the 100 ms fixed-step budget on this machine; 60-regiment ticks still cause visible frame hitches and limit accelerated playback.

```bash
python -m analysis.scaling --counts 18 24 36 60 --terrains 'Mixed Terrain' --repeats 1 --output benchmark-results/campaign-after.json --compare benchmark-results/campaign-before.json
python -m analysis.campaign_run --seed 17 --runs 3 --battles 2 --policy upgrade --output benchmark-results/campaign-balance.json
pytest -q tests/test_campaign.py tests/test_campaign_ui.py tests/test_commander_upgrades.py
```

Campaign balance samples are separate from these short timing windows. Final-template AI-controlled upgrade runs at seeds 17–19 all won battle 1 (174.9–235.2 simulated seconds) and lost battle 2 (234.2–464.5 s). A final recruitment-policy seed-17 run also won the opener (213.4 s) then lost battle 2 (347.8 s). No sample timed out. These are ordinary AI decisions/rewards, not optimal player tactics or a completed natural campaign; they show that the difficulty curve and reward value need further tuning. Reports retain casualties, regimental activity and existing battle statistics in `campaign-ai-upgrade-adjusted.json` and `campaign-ai-final.json`. The five-victory integration test uses explicitly controlled results to verify progression, persistence, recruitment, training, replenishment and terminal victory independently of balance.

Graphical tests cover the menu, frozen deployment, original results report and Continue action, reward selection, save failure/retry, defeat/victory, return to sandbox and multiple resolutions. No manual physical-display or Windows campaign playthrough has been performed. Further work should prioritize human campaign playtests and late-encounter/reward balance, followed by the already documented large-map visibility/tick-spike bottlenecks.

## Godot recording viewer (2026-11-04)

The migration prototype measures **recorded playback**, independently of Python battle rules. On the same Ryzen 5 7600X3D host with GTX 1080/OpenGL Compatibility, Godot 4.7.2 rendered 12/24/36/60-regiment Mixed Terrain recordings at mean **2.33/3.53/4.84/7.80 ms** and p95 **2.75/4.18/5.74/9.29 ms** per wall-clock frame. Each actual X11/GPU run used 1280×800, 60 warm-up frames, 600 measured frames, vsync off, seed 17 and active 10 Hz recordings. A single cached terrain build cost about 0.6 s at load; pan/zoom does not rebuild it. Four decoded snapshots were retained.

The accompanying **unrecorded** Python replays measured mean **1.55/10.56/21.43/59.29 ms** per simulation tick, using 100 warm-up and 200 measured ticks. This separate cost remains: migrating presentation alone does not accelerate the authoritative simulation. This task changes no unit balance, timestep, physics or AI scheduling. Tests verify recording does not consume RNG or alter battle fingerprints. Methodology, limitations, hardware, raw-result locations and commands are in [MIGRATION.md](MIGRATION.md); the reproducible tool is `python -m migration_tools.benchmark_viewer`.

### 3D presentation

The default viewer now uses genuine heightfield geometry, chunked tree MultiMeshes and per-regiment low-poly figure batches. On the same host/recordings, separate GPU runs at 1280×800 with 2× MSAA and directional shadows measured:

| Regiments | Mean frame ms | p95 frame ms | Presentation CPU mean ms |
|---:|---:|---:|---:|
| 12 | 2.37 | 2.92 | 1.55 |
| 24 | 4.10 | 4.85 | 3.03 |
| 36 | 5.36 | 6.26 | 4.11 |
| 60 | 9.30 | 11.59 | 7.53 |

Each run warms 60 frames and measures 600 wall-clock intervals, vsync off, orthographic overview, 1× playback from 15 seconds; no competing tests/simulations. The battlefield SubViewport is 962×578. There are 24,321 terrain vertices, 385 trees and up to 32 proxies per infantry/cavalry regiment; casualties reduce displayed counts. Terrain is built once, decoded snapshots remain bounded to four. Startup costs 137–151 ms. These are recorded presentation measurements, not live battle tick timings or worst-case close-up GPU limits.

A 4,800×3,000 m headless load test with 125 hills and 100 forests initially took 11,125 ms. Exact feature-support clipping and static forest candidate cells reduced this to 1,068 ms, retaining 199,092 vertices and 9,518 trees; terrain mesh work fell from 5,016 to 807 ms. No authoritative terrain functions were changed. Headless frame intervals are not GPU FPS. Dynamic figure transforms/markers remain the primary scaling cost in the medium-map samples.

Raw current files use `benchmark-results/godot/*-units/graphics-3d.json`; previous 2D results remain separate. The tool supports `--viewer 3d` (default) or `--viewer 2d`. Full methods, 568-test regression results, 48 camera / 73 viewer / 60 preserved playback checks, large-map limitations and reproduction commands: [godot/VIEWER_3D.md](godot/VIEWER_3D.md). No Python simulation, balance, fixed timestep or RNG changes were needed for 3D presentation.

## Native C# Milestone 5: tactical AI and commanders

### Performance

Linux/Ryzen 5 7600X3D, .NET SDK 10.0.403/runtime 10.0.14; C# **Release**, no profiler.
Same autonomous combined-arms JSON/seed 17/commander seed 1729; 100 warm-up and 600
measured fixed ticks (**60 simulated seconds**), three sequential repeats. Results
are averages of per-run statistics. Planning counters/time include all 700 ticks,
including warm-up/JIT, and measure scheduled planner work only, not all tick-level
execution. Timing samples have no competing tests, renderers or other benchmarks.

| Regiments | Mean/median/p95 tick ms | Ticks/wall s | Wall s for 60 simulated s | Planning ms/tick* | Decisions/target evaluations | Managed bytes/tick |
|---|---:|---:|---:|---:|---:|---:|
| 12 | 0.406/0.365/0.641 | 2,464 | 0.244 | 0.030 | 173/297 | 115,599 |
| 24 | 0.829/0.743/1.148 | 1,206 | 0.498 | 0.047 | 355/731 | 244,087 |
| 36 | 1.310/1.265/1.761 | 763 | 0.786 | 0.077 | 533/1,202 | 365,254 |
| 60 | 2.301/2.332/3.151 | 434 | 1.381 | 0.152 | 890/2,603 | 630,767 |

*Planning average covers all 700 ticks, unlike the 600-tick runtime window. At 60,
186,216 visibility requests produce 41,549 actual rays;
the workload fires 136 rounds/180 volleys, starts 10 charges
and produces 9 routs. This is an autonomous workload, not an apples-to-apples
comparison with static M4 armies or the complete Python application.

Profiling identified unnecessary far-enemy perception in scheduled plans. Nearest
roles now stop at the first visible candidate; persistent targets are checked in
priority order; scored searches use conservative distance-score lower bounds.
No approximate visibility, delayed damage or changed decision cadence is involved.
The 60-unit target evaluations fall **24,898→2,603**;
planning average **1.283→0.152 ms/tick**, mean tick
**2.500→2.301 ms**, p95 **4.979→3.151 ms**.
All four stress sizes/three repeats retain the exact pre-optimization state checksum;
all twelve complete battles retain result, time, strength and random-draw counts.
Raw before/after: `m5-unpruned-headless.json`, `m5-headless.json/.csv`,
`m5-battles-before-pruning.json` and `m5-battles.json` under `benchmark-results/`.

A separate allocation diagnostic pass (excluded from timing) reports approximately
191 KB/tick intent/planning, 87 KB/tick movement, 222 KB/tick contact/fire/events, 163 KB/tick morale. These cover all 700 ticks and omit small outside-phase costs;
state checksum/RNG matches the uninstrumented run. Spatial-query collections,
ordered candidate temporaries and event/frame objects remain allocation candidates.
Raw diagnostic: `benchmark-results/m5-allocations.json`.

The same frozen M4 60-regiment combined-arms workload was rebuilt from the source
checkpoint and measured in three interleaved before/after repeats. Mean
**1.642→1.568 ms**, p95 **2.319→2.253 ms**;
managed bytes/tick **532,494→529,316**.
Final states/draws match. The small timing difference does not establish a general
engine speedup; existing gains are retained. Raw: `m5-legacy-guard.json`.

Actual GPU: GTX 1080/NVIDIA 580.196.07, Godot 4.7.2.NET, **Debug** game assembly,
1280×800, 962×544 battlefield, perspective span 800 m, shadows/2×MSAA,
32 maximum figures/regiment. Autonomous fixtures pre-roll 140 ticks, then run 4×;
60 warm-up/600 uncapped measured frames. These combine simulation/bridge/presentation
work and are not isolated GPU timings. End simulated times differ per sample;
distant/offscreen figures may be culled. Terrain builds once (45k–192k vertices).

| Regiments | Mean/median/p95 frame ms | Average FPS | Combined CPU mean ms | End simulated time |
|---|---:|---:|---:|---:|
| 12 | 3.18/2.75/5.69 | 315 | 2.34 | 22.4 s |
| 24 | 5.37/4.24/9.81 | 186 | 4.45 | 28.3 s |
| 36 | 8.53/6.33/14.90 | 117 | 7.38 | 36.9 s |
| 60 | 16.58/16.63/25.89 | 60 | 15.28 | 59.8 s |

At normal 1×, the 60-regiment sample averages **82 FPS**, mean/p95
**12.15/23.03 ms**. The 4× case averages about 60 FPS,
but its 25.89 ms p95 is not a locked 60-FPS guarantee. Every sample ends with
accumulator remainder<.1 s; peak debt was not recorded. Snapshot conversion,
terrain-following figures and event presentation still contribute frame spikes.
One GPU sample per configuration, not a worst-case/close-up/dense-forest guarantee.
Raw: `benchmark-results/m5-gpu/`.

## Native C# Milestone 4: artillery and specialists

### Measured performance (Milestone 4)

Ryzen 5 7600X3D/Linux, Python 3.14.8, .NET SDK 10.0.403/runtime 10.0.14.
C# **Release**, profiling disabled; same scenario JSON/seed 17, actual supported
Python battle loop, neutral commanders/no army planner, 100 warm-up plus 600
measured ticks (**60 simulated seconds**), three sequential repeats. Statistics
are means of per-run statistics, not pooled percentiles. The Python loop retains
its existing analysis bookkeeping and global projectile candidate scan; the C#
port uses the existing spatial broad phase. This is a supported combined-arms
slice comparison, not a claim about the entire future engine or full Python AI.

| Workload | Regiments | Python mean/p95 ms | C# mean/p95 ms | C# ticks/wall s | Wall s for 60 simulated s | Managed bytes/tick | Peak balls | Collision candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| artillery | 12 | 1.811/3.557 | 0.307/0.392 | 3,255 | 0.184 | 95,648 | 24 | 5,942 |
| artillery | 24 | 5.820/12.453 | 0.660/0.881 | 1,514 | 0.397 | 212,108 | 54 | 27,550 |
| artillery | 36 | 12.061/28.073 | 1.164/1.573 | 861 | 0.699 | 335,093 | 79 | 42,030 |
| artillery | 60 | 30.239/71.597 | 1.658/2.871 | 604 | 0.995 | 555,970 | 142 | 92,718 |
| combined | 12 | 1.263/1.962 | 0.310/0.489 | 3,217 | 0.187 | 96,907 | 8 | 4,732 |
| combined | 24 | 3.671/6.269 | 0.700/0.914 | 1,427 | 0.420 | 218,235 | 16 | 16,072 |
| combined | 36 | 6.507/12.100 | 1.041/1.291 | 960 | 0.625 | 292,386 | 24 | 23,642 |
| combined | 60 | 15.688/30.402 | 1.614/2.426 | 620 | 0.969 | 532,056 | 40 | 44,707 |

All eight workloads match Python's final regiment positions/strength/morale/
cohesion/state/escape status and RNG draws in all three repeats; maximum final
numeric difference is **0 on this host**. This does not imply cross-platform
bitwise equivalence for arbitrary trajectories. Activity/collision/peak counts
include warm-up; timed statistics exclude it. The 60 artillery-heavy case fires
564 balls, records 252 regiment hits/2,775 bounces/28 friendly-fire incidents and
11 routs. Combined 60 fires 200 balls, with 107 hits/11 friendly hits/10 routs.
Five times as many regiments costs about 5.4× headless tick time in these layouts.
Global targeting and repeated spatial/terrain query allocations remain worthwhile
optimization candidates; roughly 0.53–0.56 MB managed allocation per60-unit tick
is measurable. No precision/timestep reduction or delayed collision was used.
Raw JSON/CSV and all repeats: `benchmark-results/m4-headless.*`.

The same frozen M3 60-regiment workload was rebuilt from the pre-edit source
checkpoint and compared in three interleaved repeats: mean **1.636→1.738 ms**,
p95 **1.966→2.055 ms**, managed bytes/tick
**417,621→442,825**. The mean difference is
**+6.2%**; final states/draws remain identical. The new opacity-aware
visibility cache and integration add some overhead; this is a measured regression,
not a claim that new mechanics are free. Raw guard: `benchmark-results/m4-legacy-guard.json`.

Actual GPU: GTX 1080/NVIDIA 580.196.07, Godot 4.7.2.NET, **Debug** game assembly,
1280×800, battlefield962×544, perspective span 800 m, shadows/2×MSAA,
32 maximum figures per regiment. Combined-arms fixtures pre-roll 140 real ticks,
then run **4×**, with 60 warm-up/600 measured uncapped frames. These are combined
simulation/presentation wall frames, not GPU-only timestamps. End battle times
vary with frame throughput; distant/offscreen objects may be culled. Different
map heights contain 45k–192k cached terrain vertices and 33 trees.

| Regiments | Mean/median/p95 frame ms | Average FPS | Live CPU mean ms* | Active/peak balls at end |
|---|---:|---:|---:|---:|
| 12 | 2.85/2.44/4.80 | 350 | 1.97 | 8/8 |
| 24 | 5.40/4.08/10.10 | 185 | 4.35 | 0/16 |
| 36 | 8.06/5.60/15.02 | 124 | 6.79 | 24/24 |
| 60 | 15.91/15.65/25.49 | 63 | 14.41 | 40/40 |

*Includes due simulation ticks, typed frame conversion, interpolation/camera,
terrain-following decorative figures, events/effects and markers. At normal **1×**,
the 60-unit sample averages **106 FPS**, mean/p95
**9.45/17.43 ms**, with40 active balls at the end.
Each sample ends with accumulator remainder<.1 s; peak debt was not recorded.
The 4× 60-unit p95 exceeds 16.7 ms, so this is not a locked 60-FPS promise.
One GPU sample per configuration; large dense forests/close-ups/packaged exports
need further profiling. Terrain is constructed once on load, not per frame.
Raw reports: `benchmark-results/m4-gpu/`.

## Native C# Milestone 3: morale and cavalry

Matched supported-slice workloads now include actual morale recovery/cascades,
escape/rallying, accelerating cavalry charges/impacts and moving pursuit. Python
uses its actual `Battle.step()` (with existing analysis bookkeeping), neutral
commanders, no army AI and no projectiles. C# runs the ported slice. Both use the
specified portable stream and identical JSON/seed 17, with matching final states,
RNG draw counts and activity counters at every count. This is not a comparison
against the entire game/future C# engine.

Ryzen 5 7600X3D/Linux, Python 3.14.8, .NET 10.0.14; C# Release, profiler off. 100 warm-up
+600 measured 0.1 s ticks (**60 simulated seconds**), three sequential repeats,
no competing tests/renderers. Entries average each run's metrics, including p95.

| Regiments | Python mean / p95 tick ms | C# mean / median / p95 tick ms | C# ticks/wall second | C# wall seconds for 60 simulated seconds | Managed bytes/tick |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12 | .856 / 1.110 | .188 / .154 / .261 | 5,320 | .113 | 45,822 |
| 24 | 2.151 / 2.760 | .481 / .449 / .641 | 2,079 | .289 | 155,029 |
| 36 | 3.926 / 4.790 | .815 / .786 / .981 | 1,226 | .490 | 243,671 |
| 60 | 8.272 / 9.987 | 1.481 / 1.410 / 1.770 | 676 | .889 | 417,617 |

At 60, the full 700 ticks include 13 routs, 11 rallies, 15 charge starts, 14 impacts,
1,309 pursuit casualties and 9 pursuit resistance losses. 77,852 visibility requests
become 22,914 rays/799,330 samples. Counters include warm-up; timings exclude it.
Five times the regiments costs about 7.9 times the tick time: target ordering and
moving LOS still have nonlinear costs, despite the small absolute times.

The pre-M3 checkpoint and current core were also rebuilt and interleaved over
three runs of **the same M2 frozen-morale workload**. Mean/p95 before→after(ms):

| Regiments | Before | After | Mean change |
| --- | ---: | ---: | ---: |
| 12 | .191 / .317 | .202 / .323 | +6.0% |
| 24 | .408 / .677 | .412 / .678 | +1.0% |
| 36 | .626 / 1.061 | .636 / 1.063 | +1.6% |
| 60 | 1.134 / 2.021 | 1.099 / 2.258 | −3.1% |

Managed allocation is essentially unchanged. Different M2/M3 scenario timings
must not be subtracted and labelled an improvement. The new core remains within
the fixed 100 ms tick budget; final rendering performance is measured separately.

A separate `--allocation-profile` pass attributes 34.5% of phase allocations to
intents/routing/targeting, 28.5% to contact/fire/pursuit/events, 18.8% to movement and
collision, 18.2% to morale queries/recovery/cleanup. Whole-run approximate amounts
are 148/122/80/78 KB per tick, including warm-up and omitting small outside-phase
costs. The profile is optional, does not consume RNG, and has an outcome-preservation
test. Its timings are excluded from the runtime table. Reusing ordered-target,
spatial-query and event temporaries is a future measured optimization opportunity.

Actual GPU samples: GTX 1080 driver 580.196.07, Godot 4.7.2 .NET/Debug assembly,
1280×800 window, 962×544 battlefield, perspective span 800 m, shadows, 2× MSAA and
32 maximum decorative figures/regiment. Pre-roll 140 actual ticks, run at 4×,
warm 60 frames, measure 600 uncapped wall-clock frames, no competing benchmarks:

| Regiments | Mean / median / p95 frame ms | Mean FPS | Viewer update CPU mean ms* |
| --- | ---: | ---: | ---: |
| 12 | 2.29 / 2.10 / 3.55 | 437 | 1.55 |
| 24 | 4.20 / 3.55 / 6.46 | 238 | 3.29 |
| 36 | 6.17 / 4.92 / 9.21 | 162 | 5.11 |
| 60 | 11.09 / 7.83 / 15.14 | 90 | 9.76 |

*Includes due live ticks, interpolation/camera/figures/effects/markers, not isolated
GPU time. Each sample ends at a different simulated time(20.1/25.2/30.4/43.6 s).
The 60 sample includes 12 new routs, 8 impacts, 7 rallies and 1,120 pursuit casualties;
it has 1,659 remaining visible figure proxies. Terrain builds once, with 31 trees
and 67,781–91,357 vertices. Source/terrain load costs 415–526 ms, excluding pre-roll.
Final accumulator remainder is below 0.1 s in every sample; peak debt was not recorded.
These are one-sample observations, not worst-case close-up/dense-forest guarantees.

```bash
bash tools/dotnet.sh build godot/Simulation.Runner -c Release
.venv/bin/python -m migration_tools.benchmark_dynamics --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --dynamics --frames 600
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --combat-scenario benchmark-dynamics-60 --benchmark
# Allocation diagnosis only; do not mix its timings with the normal benchmark:
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --combat-scenario benchmark-dynamics-60 --benchmark --allocation-profile
```

JSON/CSV: `benchmark-results/csharp-dynamics.*`; pre-port baseline:
`m3-combat-before.*`; paired guard:`m3-legacy-guard.json`; allocation diagnosis:
`m3-allocations.json`; GPU reports/logs:`m3-gpu/`. Full formulas, numerical
comparisons, tests and remaining porting work: [MORALE_CAVALRY.md](godot/MORALE_CAVALRY.md)
and [MIGRATION.md](MIGRATION.md).

## Native C# Milestone 2: infantry combat (historical)

Current Release headless results, same Ryzen 5 7600X3D host, Python 3.14.8 / .NET 10.0.14. Shared mixed-terrain inputs/seed 17, **100 warm-up + 600 measured 0.1 s ticks**, three sequential repeats without profiler/competing tests. Infantry marches under fire; other pairs fight sustained melee. Both languages exclude morale/routing, charges, artillery, commander effects, tactical army AI, rendering and snapshot serialization. This comparison is scoped to these matching phases; it is not a complete-engine speedup claim. Final strengths and RNG draw counts match at every size.

| Regiments | Python mean / p95 ms | C# mean / median / p95 ms | C# wall seconds for 60 simulated seconds | C# managed bytes/tick |
|---|---:|---:|---:|---:|
| 12 | .736 / 1.211 | .192 / .157 / .316 | .115 | 66,346 |
| 24 | 1.760 / 2.662 | .421 / .335 / .701 | .253 | 120,848 |
| 36 | 3.000 / 4.443 | .653 / .527 / 1.112 | .392 | 187,004 |
| 60 | 6.420 / 9.172 | 1.107 / .800 / 2.185 | .665 | 314,630 |

Throughput: approximately 5,200 / 2,370 / 1,532 / 903 ticks per wall second. Full-run metrics include the warm-up: the 60-regiment workload produces 178 volleys / 525 melee pulses / 3,416 casualties. Exact caching converts 105,680 LOS requests into 10,085 actual rays / 260,141 samples. No approximate terrain or slower decision schedule was introduced. Allocation includes managed core/query collections only, not native renderer memory.

Movement preservation was measured against a rebuilt pre-M2 checkpoint, interleaving three before/after Release runs with identical original movement inputs. Mean tick before→after: 12 **.0829→.0826 ms**, 24 **.1832→.1817**, 36 **.2639→.2642**, 60 **.5055→.5182** (−.8% to +2.5%); managed bytes/tick are unchanged. The initial one-repeat baseline and the stronger paired guard are retained separately.

GPU live combat uses the GTX 1080, Godot 4.7.2 .NET / Debug assembly, 1280×800 / 962×578 battlefield, perspective span 800 m, 2× MSAA, shadows, 32 maximum figures per infantry, 62 trees. Each case warms 60 frames then measures 600 uncapped frames at 1×, with no competing tests/benchmarks:

| Regiments | Mean / median / p95 frame ms | Mean FPS | Viewer update CPU mean ms* |
|---|---:|---:|---:|
| 12 | 2.78 / 2.68 / 3.38 | 360 | 1.96 |
| 24 | 4.44 / 4.27 / 5.45 | 225 | 3.46 |
| 36 | 6.08 / 5.83 / 9.18 | 164 | 4.93 |
| 60 | 9.30 / 8.51 / 14.30 | 107 | 7.87 |

*Includes live ticks on frames when due, plus camera/interpolation/decorative formation/effect updates; this is not isolated GPU time. These short initial samples have active firing/movement/melee but are not long-duration or worst-case camera guarantees. Terrain is built once; startup costs 357–404 ms. No simulation debt exceeds the ordinary sub-tick remainder.

Commands from repository root:

```bash
bash tools/dotnet.sh build godot/Simulation.Runner -c Release
.venv/bin/python -m migration_tools.benchmark_combat --repeats 3
.venv/bin/python -m migration_tools.benchmark_live --combat --frames 600
# Single headless sample:
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release --no-build -- --combat-scenario benchmark-60 --benchmark
```

JSON/CSV: `benchmark-results/csharp-combat.*`; movement guard: `m2-movement-guard.json`; GPU reports: `m2-gpu/combat-live-*.json`. Remaining costs include target sorting/spatial query collections, exact LOS during motion, and presentation-side per-figure terrain placement. Preserve the current behaviour and measure before reusing allocations/changing cadence. Full rules, reference tests and temporary morale/cavalry limitations: [COMBAT.md](godot/COMBAT.md). Detailed hardware/methodology and validation: [MIGRATION.md](MIGRATION.md).

## Native C# movement milestone (historical baseline)

The C# engine ports the current movement/geometry/congestion/settling/terrain phases. Combat, AI, morale/routing and commander abilities remain excluded. The comparison uses **equivalent movement-only inputs in both languages**, not the old complete Python battle benchmark. Python's isolated phase runner is checked against the original sandbox; eleven cross-language fixtures pass at 1e-5 tolerance, with observed differences about 1.4e-16 or less. C# runs are reproducible.

Same Ryzen 5 7600X3D/Linux host; Python 3.14.8, .NET SDK 10.0.403 / runtime 10.0.14; C# **Release**. Seed 17, 100 warm-up ticks and 600 measured ticks (60 simulated seconds), crowded mixed unit categories with a scheduled reversal. Three sequential repeats, profiler off, no competing renderers/tests. Entries are averages of repeat-level metrics:

| Regiments | Python mean / p95 tick ms | C# mean / p95 tick ms | C# managed bytes/tick |
|---:|---:|---:|---:|
| 12 | 0.759 / 1.077 | 0.082 / 0.099 | 15,613 |
| 24 | 1.600 / 2.219 | 0.184 / 0.229 | 28,873 |
| 36 | 2.421 / 3.409 | 0.263 / 0.338 | 44,035 |
| 60 | 4.267 / 5.942 | 0.492 / 0.605 | 77,481 |

C# simulated the measured 60 seconds in approximately 0.050 / 0.110 / 0.158 / 0.296 wall seconds. This is an 8.7–9.2× improvement for this movement workload, not for an unimplemented full C# combat engine. Allocation counters measure the managed thread only; renderer/native allocations are separate. Spatial/query collections remain candidates for future measured reuse.

Actual Godot .NET live GPU samples, Open Field, default **Debug** assembly, 1280×800, perspective span 800 m, 2× MSAA, shadows, 32 representative figures and 60 warm-up + 600 measured frames:

| Regiments | Mean / p95 wall frame ms | Combined update CPU mean ms |
|---:|---:|---:|
| 12 | 2.02 / 2.46 | 1.36 |
| 24 | 3.34 / 3.89 | 2.54 |
| 36 | 4.80 / 5.82 | 3.82 |
| 60 | 7.63 / 10.27 | 6.35 |

These are one sample per count, with live fixed ticks/interpolation and no dropped backlog. All fit a 60 Hz budget here. They are not comparable to prior Mixed Terrain recorded battles: live has no combat/projectiles, different terrain and a taller map at 60. The driver measures monotonic wall time, avoiding Godot's potentially capped process delta, and retains debt beyond its 16-tick processing budget. The renderer keeps existing visual objects; snapshots are mapped in memory once per tick, without JSON.

Raw results: `benchmark-results/csharp-movement.*` and `benchmark-results/live-{12,24,36,60}.*`. Reproduce with `python -m migration_tools.benchmark_movement --repeats 3` and `python -m migration_tools.benchmark_live --frames 600`. SDK/build/fixture/test instructions and detailed limits are in [MIGRATION.md](MIGRATION.md), [godot/README.md](godot/README.md), and [godot/LIVE_SIMULATION.md](godot/LIVE_SIMULATION.md).
