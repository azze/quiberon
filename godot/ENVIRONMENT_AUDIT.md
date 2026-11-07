# Environmental terrain extension audit

The existing authoritative terrain is `TerrainMap` (analytic hills and elliptical
forests). `MovementSystem` samples footprints, `VisibilityService` caches endpoint
queries, `CombatSystem` resolves fire/melee and `ArtillerySystem` sweeps projectiles.
The 3D viewer samples a static terrain surface; live data crosses through the C#
bridge into the same presentation DTOs used by replay. Custom recipes retain a
version-1 Python-compatible wrapper. All these paths remain in use.

Extension decisions:

- Optional `terrain.environment`, version 1, contains polylines, crossings, roads,
  directional defences and a constant weather definition. Missing data means no
  added features and Clear; old formula/RNG paths remain unchanged.
- River segments become cached convex capsule polygons in a static spatial grid.
  Full oriented footprints and swept poses must be dry or inside a permitted
  crossing. Movement, turning, formation changes and separation are guarded.
- Bridge/ford rectangles define real surfaces and entry/exit connections. A small
  visibility graph joins dry approaches and usable crossings. It evaluates distance
  and category/width, not enemy strategy. FIFO traffic gives one friendly formation
  priority to clear a crossing; enemy occupancy is resolved by ordinary combat.
- Infantry uses its existing timed column change. Cavalry/artillery use timed
  compact travel footprints without altering legacy archetypes or combat balance.
- Road benefits depend on category, heading and formation. Rain adds bounded
  off-road/reload effects. Fog composes with authoritative LOS and applies equally
  to manual targeting and AI, including the existing artillery exceptions.
- Defences reduce frontal musket exposure and charge shock only for properly
  positioned defenders. They are not projectile colliders or constructed entities.
- Live presentation receives canonical water polygons/crossing geometry and sampled
  elevations from C#, not independently invented rivers. Fog hides unseen enemy
  presentation; camera distance does not decide authoritative visibility.
- No river operation planner, bridge construction, objectives, weather transitions,
  campaign systems, external navigation library or physics engine is introduced.

Temporary pre-change checkpoint was taken at `/tmp/rtt-environment-before.tgz` (the repository's `.git`
stub is not a writable worktree). Baseline: 512 native tests; existing performance
measurements in `benchmark-results/commonwealth-stage1-legacy-after.json` are kept
for comparison. Final rules, tests and timings will be in `ENVIRONMENT.md`.
