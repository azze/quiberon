The 3D viewer uses procedural low-poly meshes from scripts/three_d/mesh_kit.gd,
shared materials, batched trees and per-regiment MultiMeshes. Uniform/model
profiles use stable archetype IDs in resources/unit_visuals.json. There are no
downloaded models, textures, portraits, addons or third-party asset licences.

The original 2D scene still uses draw primitives and the built-in fallback font.
Later soldier assets can replace these mesh profiles without changing recordings,
selection IDs, playback or authoritative simulation entities. Decorative figures
must not gain AI, physics bodies or independent authoritative state.
