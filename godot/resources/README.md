No duplicated authoritative unit resources are introduced in this prototype.
The recording header supplies archetype labels, colours, categories, statistics,
commanders and explicit terrain. RecordingSource translates it into BattleFrame
presentation objects. Future shared JSON definitions should be versioned and
validated against the Python registries before moving their source of truth.
A future plain-.NET simulation should publish the same visual frame contract
through a small adapter; it should not depend on FileAccess or Godot nodes.
