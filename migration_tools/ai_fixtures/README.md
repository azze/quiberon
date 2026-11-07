# Current-Python commander and AI decision probes

Regenerate with `.venv/bin/python -m migration_tools.ai_reference`.
Definitions and naming pools come from current `simulation/commanders.py`;
probes invoke actual `commander_ai`, `ai.destination`, `ai.skirmish_destination`
and `ai.army_plan` functions. Explicit officers isolate rule comparisons from
the different name-generator streams. The C# suite checks 111 probes at 1e-5
numerical tolerance; the Python suite regenerates and verifies them.

These are controlled decisions and mechanics, not a claim of full cross-language
AI replay identity. Native scheduling, prepared-front safeguards, cover selection,
formation initiative and artillery safety/aiming refinements are documented in
`godot/AI_COMMANDERS.md`. Earlier movement/combat/dynamics/artillery fixtures stay
independent and continue testing their original scope.
