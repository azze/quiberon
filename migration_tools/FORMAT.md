# Quiberon battle recording, version 1

This is a **presentation recording**, not a resumable simulation save or a deterministic C# command replay. Python remains authoritative. All four files live in one directory, encoded as UTF-8. JSON Lines use LF newlines and compact JSON objects; byte offsets refer to that exact file. No wall-clock timestamps, output paths or RNG draws enter the recording.

## Files

- `metadata.json`: `format: "quiberon-battle-recording"`, integer `version: 1`; scenario identifier, decimal-string `seed` (avoids Godot JSON's 64-bit integer precision trap), `world`, `dt`, `interval_ticks`, `interval_seconds`, initial/final times/ticks, frame/event counts, status and actual result. Includes armies/colours, used archetype definitions, regiment identities/names/categories/max and initial strengths/full commander records, explicit terrain geometry, and the existing final battle report. Terrain includes its original Python seed for reference; Godot renders the explicit features and never regenerates them from a possibly rounded JSON integer.
- `frames.jsonl`: one complete visual state per sampled simulation tick. `tick` and `time` (`tick * dt`) identify each state. `result` is null until the battle actually completes. `units` and `projectiles` contain ordered arrays with stable integer IDs.
- `index.jsonl`: one `{tick, time, offset}` entry per frame; `offset` is its **UTF-8 byte offset**, not a character count. Strictly increasing. Allows seeking without loading/parsing all snapshots.
- `events.jsonl`: records `{seq, tick, time, kind, position, ...}` in emission order. `seq` begins at zero and is unique/contiguous. Events stream immediately, even between sampled frames and beyond the original battle event deque's 250-entry limit.

Metadata status is initially `recording`, then `complete` for an actual battle result, `limit` for a duration-limited clip, or `incomplete` after a recording exception. The viewer rejects unfinished exports. A final forced snapshot is always written on close if the latest tick was not sampled. Metadata is replaced atomically after streams are flushed. Interrupted recording directories are left recognizable and are never silently reused/overwritten; choose a new output directory.

The exporter retains only static metadata, current projectile references/IDs and stream buffers. It does not retain the frame/event history or a growing in-memory index. The viewer retains metadata, index and event records plus at most **four decoded frames**. Invalid middle frames are detected lazily when seeking/playing into them, stop playback, and retain the previous valid view.

## Regiment data

Immutable identity is normalized into `metadata.regiments`, keyed by `id`: `army`, `name`, `archetype`, `category`, `max_strength`, `initial_strength`, `commander` (ID, name/rank/background, personality, specialization and acquired upgrades). Each snapshot joins that identity by `id` instead of repeating long names and definitions thousands of times.

Dynamic unit fields are `position: [x,y]`, `facing`, `width`, `depth`, `formation`, `strength`, `morale`, `cohesion`, `state`, `combat_state`, `active`, `withdrawn`, `speed`, `order`, `target_id`, `charge_state`, `charge_momentum`, `pursuit_id`, `ai_state`. `order` uses the existing recipe shape (`kind`, destination `{x,y}` or null, target ID/facing or null). Null targets are distinct from ID zero. All currently present regiments, including destroyed/withdrawn ones, remain in Python snapshots; the viewer also tolerates a regiment disappearing from later frames.

## Projectiles and effects

Projectile snapshots: stable `id`, `type: "cannonball"`, `owner_id`, horizontal `position`, absolute `height`, actual terrain `ground` elevation beneath the ball, horizontal `velocity`, `vertical_speed`, `age`, `energy`, `bounces`. IDs are monotonic, recorder-owned integers assigned at launch; no object address is serialized. Strong references prevent Python address reuse from joining unrelated shots. A ball destroyed in its first physics tick still has a `projectile_spawn` event containing its initial data, although it may never appear in a sampled frame.

Battle log events keep their existing kinds/messages (casualties, engage, charge_start, charge, pursuit, rout, rally, morale, friendly_fire, withdraw, trait, result). Existing smoke effects become `volley` or `artillery_fire`, with unit ID, muzzle position, facing, frontage and duration. Existing impact/charge_impact effects keep their position/duration. These are copies of actual simulation effects, not invented combat outcomes. An impact event is a visual occurrence, not a full physics contact record; substep times, exact terrain-vs-regiment collision classification and projectile removal reasons are not currently exposed. Spawn events preserve short-lived shot identity but playback does not invent an intermediate trajectory between unobserved states.

## Coordinates, timing and interpolation

- All horizontal positions, formation dimensions and elevations are metres. Time is seconds. The preserved 2D scene uses **one canvas unit per metre**; Camera2D alone controls zoom and translation.
- X points right; Y points down. Facing zero is +X and positive radians rotate clockwise, matching Godot 2D. **Depth** is along facing/local X, **frontage width** along local Y. `WorldCoordinates` centralizes footprint, hit test, shortest-angle and projectile-height rules.
- Projectile height is absolute elevation. The displayed ball is offset up-screen by `max(0, height - ground)` metres from its 2D ground shadow. Units remain top-down footprints; hills do not move unit centres up-screen.
- The 3D scene uses **one world unit per metre**, `(x,y)` → `(x,elevation,z=y)`. Models face local +X; yaw about Godot Y is **negative** recorded facing. Cannonballs use `(x,absolute_height,z=y)` directly, without adding ground twice. `three_d/world_3d.gd` owns these conversions. Unit/tree grounding and camera rays share the same triangular heightfield mesh reconstructed from explicit analytic terrain; this is a configurable visual approximation, not a new simulation surface.
- Snapshots capture authoritative state **after** a fixed tick. Existing logs/effects are stamped at the **start** of the tick that produced them. Thus an event can lead its first resulting snapshot by one `dt`; physics substeps are not timestamped separately.
- The default exporter samples every tick (10 Hz at dt 0.1). `--interval-ticks` changes only recording frequency, never simulation timestep or event capture. Initial and final states are always included.
- Playback interpolates position/facing only between matching identities. State, formation, strength, morale, cohesion, orders and targets step at the current recorded frame; no interpolation invents intermediate morale states or formation widths. Birth/removal happens on its observed sample boundary. Projectile interpolation is suppressed across bounce-count changes. Coarser recordings can alias brief contact/projectile motion; use 10 Hz when investigating those behaviours.
- Seeking finds bracketing indexed times by binary search. Visual effects are reconstructed from the preceding three seconds of events, so backwards seeks do not accumulate particles or replay future messages.

## Included example

`godot/recordings/combined-arms/` is an actual completed, 12-regiment Mixed Terrain battle, seed **7**, simulation dt **0.1 s**, snapshots every **0.5 s** to keep the example about 8 MB. It runs **580.8 simulated seconds**, ends with `army_1`, and contains 1,163 frames, 1,846 log/visual events, 302 infantry volleys, 63 artillery firing cycles, 219 projectile spawns, two charges, ten routs and sixteen rally events. At most seven balls are present in the sampled frames. The demo translates deployments 130 m forward, identically to the existing scaling workload, to begin activity sooner. No unit statistics or simulation rules were changed. The exporter defaults to a different demo seed (17); use `--seed 7 --interval-ticks 5` to reproduce this example.

Entity IDs, ticks, event sequences and byte offsets in version 1 must remain exactly representable by the viewer's JSON numeric representation (non-negative integers below 2^53). Current game IDs/ticks are well within that range. Future larger identifiers should use a versioned decimal-string convention, as the primary battle seed already does. This format does not promise to round-trip every Python/C# internal type or arbitrary user-mutated battlefield object.
