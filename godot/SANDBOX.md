# Native custom battles, commander abilities and results

Launch from the repository root:

```bash
bash tools/dotnet.sh build godot/Quiberon.sln -m:1
bash tools/godot.sh
```

The main menu offers **Custom Battle**, **Live scenarios / AI battles**, **Python
Battle Replay**, and Quit. The native sandbox has no campaign, recruitment,
rewards, replenishment, permanent progression, or campaign save migration.
The existing Python game and its campaign remain independent and operational.

## Custom battle flow

1. Choose a preset or use **+ Add units…** for either army. A separate catalogue
   has All/Infantry/Cavalry/Artillery filters, search, unit statistics, abilities,
   and an amount to add. The main screen lists only chosen archetypes with their
   counts. All nine archetypes are available, including the six specialists.
   Symmetric rosters can be disabled; mirrored additions and army limits are respected.
2. Choose battlefield dimensions, terrain preset, battle seed, terrain seed,
   officer seed, army objectives, and regiment limits (default 12 per archetype,
   48 total; configurable up to 64 and 256 respectively).
3. **Deploy armies** opens the existing 3D battlefield at tick zero. Blue and Red
   deployment zones have visible outlines. Click either army, right-click terrain
   to place the selected formation, **hold right mouse and drag** to choose facing,
   or use **Rotate selected 15°**. A translucent formation ghost and arrow show
   the final position/heading before release; invalid placements turn red. Use
   L/J/K or formation buttons to change its initial formation. Invalid
   candidates do not change the recipe. Starting footprints must stay in their
   zones and cannot overlap. Reset positions retains regiment/officer identities.
4. The **AI** dialog edits personalities, starting specializations, and up to
   three compatible acquired abilities per commander. Rerolling generates a fresh
   officer. Assign abilities after rerolling. Army strategies and individual Blue
   autonomy can be adjusted. Officers/abilities lock after the first tick.
5. **Start battle** or Space starts the authoritative simulation. Blue regiments
   begin with Hold orders unless the recipe explicitly supplies another order or
   enables their AI. Camera motion is independent of deployment and simulation.
6. Results open automatically when combat finishes. Tab also opens a frozen
   mid-battle report. Return to battlefield to inspect the final positions;
   Restart repeats the same setup/seed, New seed changes only combat randomness,
   and Edit setup returns to the recipe editor.

**Load file / Save file** use the version-1 Python `BattleConfig` JSON schema,
including actual terrain features, placements, names, strengths, orders,
commander identities, traits and acquired abilities. All twelve existing Python
custom-battle presets are embedded in the standalone assembly; no Python process
is needed. Native saves can also be loaded by Python. Optional per-placement
`commander_nation` and `autonomy` fields are native extensions which Python ignores;
Python resaving will discard those two extensions. Loading is limited to 1 MB.
Unknown archetypes/traits/upgrades, invalid numbers, duplicate identities,
incompatible abilities, excessive counts and invalid deployments are rejected.
Between-battle recipes are saved, not in-progress combat state.

Terrain presets use the original sector formulas and a small CPython-compatible
MT19937 integer-seed stream. Existing terrain seeds reproduce Python hills/forests,
including negative and signed 64-bit extreme seeds. The original combat and
commander streams are unchanged and separate. Explicit terrain is saved as the
canonical feature list. The UI keeps seeds as text to preserve 64-bit precision.

## Infantry bayonet charges

**B / Charge** now supports infantry as well as cavalry. Infantry approaches its
specified enemy, aligns within 0.7 radians, and starts a bayonet rush within 55 m
with at least 4 m of footprint clearance, cohesion 35+, and fatigue below 85.
Speed cap is normal formation speed ×1.20, acceleration 0.8 m/s², and turning ×.85.
The rush aborts after 30 seconds or a 1.4-radian loss of alignment. It cannot fire
volleys while rushing.

Momentum combines actual speed, distance, cohesion and movement alignment. One
impact uses `strength × .035 × momentum × melee × morale effectiveness`, multiplied
by forest/slope conditions, flank/rear factors 1.3/1.6 and a controlled random
factor 0.8–1.2. Base morale shock is `6 × momentum`, with matching situational
factors. Skirmish impact power is ×.65. Afterwards the regiment uses ordinary
melee, without double-counting its first impact as a sustained-melee hit.

Each charge has an explicit sequence/impact lock. A new charge requires 20 seconds
cooldown and 3 seconds clear of melee with at least 18 m of clearance. Reissuing
orders does not reset those locks. Infantry Firebrand is now active and available
in ordinary generation/setup. Autonomous exposed-target infantry assaults use this
same charge system; they do not have a separate damage calculation.

## Commander-owned acquired abilities

The registry and tuning are in `simulation_data/commander_upgrades.json`, derived
from Python `simulation/upgrades.py`. These are separate from personality and the
starting specialization. There are no levels or reward transactions in this port.

| Ability | Eligibility | Actual effect |
|---|---|---|
| Rolling Volley | Infantry supporting line formation | Reload ×.8 while stationary, in line, cohesion ≥70, with a visible steady infantry ally within 90 m. |
| Swift Reform | Infantry/cavalry | Formation time ×.75; turning disruption ×.8; quiet cohesion recovery ×1.35. |
| Rallying Presence | All categories | Strongest visible steady source within 125 m grants .30 morale/s, or .45 while rallying, and reduces nearby-rout shock. |
| Controlled Charge | Cavalry | Charge turning ×1.2, alignment ×1.1, failed-impact disorder ×.7, cooldown ×.8, reform time ×.7. |
| Relentless Pursuit | Cavalry | Pursuit power ×1.2; recover 8 cohesion once per enemy routed by this officer per battle. |
| Shock Commander | Cavalry and Grenadiers | Exposed, unprepared targets receive ×1.35 charge morale shock above .25 momentum. |
| Woodland Ambush | Woodland skirmishers/rifles | Concealed stationary opening forest volley adds 6 morale shock and removes 8 cohesion. Another activation requires ≥30 s without attacking and ≥40 m relocation. |
| Harassing Fire | Woodland skirmishers/rifles | A damaging volley removes 3 additional cohesion; casualty damage is unchanged. |
| Steadfast Defence | Infantry with line formation | Steady stationary defensive line at cohesion ≥60 gains prepared charge/cohesion resistance and ×.8 morale shock; autonomous infantry prefers holding a useful firing position. |
| Mobile Battery | Artillery | Limber and setup times ×.6, using the same deployment and AI routines. |
| Calculated Fire | Artillery | After 6 seconds stationary and deployed, horizontal/vertical scatter ×.65; moving or redeploying resets preparation. |
| Inspired Attack | Infantry/cavalry | Damaging a wavering/routing enemy grants 3 morale to visible non-routing allies within 100 m; shared 20-second army cooldown. |

All twelve are rank one, unique, limited to three per officer, and validated against
archetype category/role/formations. Commander lists are defensively copied; transient
activation state belongs to the battle regiment and resets on restart. Strongest
aura only, with a .45/s cap. Swift Reform can lower formation duration to 40% of
base; manoeuvre floor .4, cohesion recovery cap 1.8, scatter floor .45, combined
charge-shock cap 1.8, and upgraded pursuit cap 1.8 preserve valid stacking. Shared
pursuit casualty budgets and charge-instance locks remain. Bonuses use existing
combat/terrain/morale/movement calculations and spatial queries.

Examples include Prussian infantry + Drillmaster + Rolling Volley/Swift Reform;
Uhlans + Firebrand + Controlled Charge/Relentless Pursuit; woodland skirmishers +
Pathfinder + Woodland Ambush/Harassing Fire; and horse artillery + Artillerist +
Mobile Battery/Calculated Fire. No combination-specific bonus is scripted.

## Results and controls

The native report reproduces the Python report's read-only data model. Army totals
distinguish lost, surviving, effective, destroyed and escaped troops. Per-regiment
and grouped-archetype tables support army filters, sorting and pagination. Select a
regiment row for its commander, abilities, morale, cohesion, charges, routs and
rallies. Export saves the frozen report as JSON. Caused casualties include friendly
fire; escaping does not count survivors as killed. Counters are retained per unit,
so the bounded transient event queue cannot truncate battle totals.

- Tab: report; Tab/Escape closes it.
- F5 or R: same-seed restart. F6: new combat seed. F7: edit setup.
- B: charge selected/current enemy (infantry or cavalry). U remains cavalry pursuit.
- Hold right mouse on ground, drag toward the desired front, release to commit.
  The initial click fixes the destination; an 8-pixel deadzone preserves ordinary
  click-to-move. A plain movement click keeps automatic facing; a plain deployment
  click preserves the existing heading. Releasing outside the battlefield, losing
  focus, resizing or cancelling clears the ghost without issuing an order.
- Deployment: right-click/drag to place and face; L/J/K formations; Space to start.
- A selected ranged regiment shows its nominal weapon radius and highlighted
  forward firing arc in Live and Replay modes. This is a geometric envelope, not
  a guarantee of visibility or a clear friendly firing lane. Melee-only cavalry
  has no weapon-range ring.
- Alt + middle drag tilts down to 0° (parallel to the ground). The eye stays above
  terrain; minimum tilt can be tuned in Camera settings.
- Existing camera, pause/speed, move/attack, fire control and replay controls remain.

## Headless use and validation

```bash
bash tools/dotnet.sh test godot/Simulation.Tests
.venv/bin/pytest -q
bash tools/godot.sh --headless --script tests/test_sandbox.gd
bash tools/godot.sh --headless --script tests/test_menu.gd
bash tools/godot.sh -- --combat-scenario=infantry-bayonet --paused
bash tools/godot.sh -- --combat-scenario=upgraded-combined
bash tools/dotnet.sh run --project godot/Simulation.Runner -c Release -- \
  --battle-config saves/custom-battle.json --duration 1200 \
  --output /tmp/custom-battle.json --report /tmp/custom-report.json
```

`--battle-config` loads a standalone recipe. `--report` exports frozen statistics
alongside the runner's existing snapshots/benchmark output. The runner reports a
timeout as inconclusive; it does not manufacture a winner. Regenerate reference
data intentionally with `.venv/bin/python -m migration_tools.sandbox_reference`.
It reads Python gameplay without modifying it and regenerates the upgrade registry,
45 numerical probes, terrain fixtures, and two demonstration scenarios.

Validation includes native tests for all twelve effects, activation conditions,
stacking, recovery/impact locks, transactional placement, independent restart
state, signed terrain seeds, all legacy presets, and frozen report accounting.
Godot checks cover menu/setup/deployment/picking/start/results/rematch/file roundtrip,
ability assignment, small windows and returning to replay. Existing movement,
combat, dynamics, artillery, AI, camera and replay tests remain.

## Current limits

This is a battle sandbox. Abilities are selected freely before combat and have no
campaign acquisition, cost or persistence between separate recipes. There is no
mid-battle save/resume. The deployment controls edit existing regiment positions,
facing and formation; counts and terrain are edited in setup. Regimental names and
starting strengths are preserved from files but do not yet have separate text
editors. Native-only orders/autonomy metadata are not all expressible in the Python
order enum. Local AI steering retains its existing limitations. Campaign, campaign
save compatibility, Windows and packaged exports remain outside this change.

## Measured validation

The final suite passes **475 xUnit tests** and **672 Python tests**. Native Godot
checks pass: 6 menu, 41 sandbox, 21 AI, 40 artillery, 36 dynamics, 39 combat,
39 movement, 74 viewer, 58 camera and 60 replay assertions. Builds are clean and
the .NET editor imports/exits without errors. GPU setup/deployment/report layout
was inspected at 1280×800 and 800×600.

Two-run release headless means for 12/24/36/60 regiments were
**.409/.835/1.351/2.388 ms per tick**, with p95 **.620/1.178/1.906/3.330 ms**.
Checksums agree between repeats. A 60-regiment GPU sample at 4× speed, 800 m camera
span and 32 figure slots per regiment averaged **15.94 ms/frame (~63 FPS)**,
p95 26.77 ms, with 1,431 visible figures. These whole-frame measurements include
simulation and rendering, and are observations on the development GTX 1080,
not hardware-independent guarantees. The upgraded 12-regiment combined-arms run
finished by morale victory in 319.5 simulated seconds. Detailed measurements and
limitations are in [MIGRATION.md](../MIGRATION.md).


The follow-up tactical-controls validation adds 42 checks covering filtered unit
selection, symmetric additions and limits, press/drag/release arrival facing,
read-only/invalid ghosts, camera rotation, hill picking/grounding, cancellation,
resizing, cached weapon ranges, replay ranges and level-camera terrain clearance.
The original 475 native tests and 672 Python tests still pass.


## Melee retention and 2D/3D views

New melee still needs .75 m footprint contact; once established, it persists
through gaps up to the 4 m oriented-rectangle margin. This avoids repeated
enter/leave events during fleeing or minor separation without creating long-range
melee. Existing two-second damage timers persist, and charge impact still requires
physical contact. Routing/disengagement remain mobile; cavalry can switch to moving
pursuit, and destruction/escape cleans up the engagement. This is a deliberate
native improvement over Python's strict-contact reference; the legacy numerical
reference tests use .75 m explicitly while seven new tests validate the buffer.

**2D view** switches the current battlefield renderer; **3D view** switches back.
The same battle/replay object, seed, clock, frame pair, selection, queued orders,
pause and speed are retained. Live combat, manual movement/facing, formation
controls, deployment, results and replay seeking use the same HUD. 2D camera
controls: WASD pan, middle drag, cursor-centred wheel zoom, Home to fit, F to focus
and C to follow. 3D camera state is retained separately. The terrain raster is
cached between switches, and only the active renderer advances its camera; neither
renderer advances the simulation independently.

Validation: **482 native tests**, **672 pytest tests**, the existing Godot regression
scripts, and **22 new shared-view assertions** pass. The shared-view tests also run
on the actual GPU, covering retained live/replay state, queued commands, 2D picking,
oriented movement, deployment and returning to 3D.
