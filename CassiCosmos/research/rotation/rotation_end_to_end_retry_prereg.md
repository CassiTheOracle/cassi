# Live merge-to-orientation — pre-statistic parse-repair retry

Status: PRE-REGISTERED before the repaired launch — 2026-09-02

The first launch registered by `rotation_end_to_end_prereg.md` did not load the acquisition script and acquired no GPU state. Godot rejected an inferred local variable whose receiver is intentionally untyped (`Cannot infer the type of "particle_state"`, `verify_rotation_end_to_end.gd:116`). No raw receipt or G97–G100 statistic was produced.

This retry changes only explicit local `Dictionary` annotations needed by the GDScript parser and the receipt's preregistration path. The fixture, planted particle/field state, 16-step post-merge cadence, production APIs, complete configuration, raw arrays and hashes, G97–G100 thresholds, decision tree, and interpretation remain exactly those frozen in `rotation_end_to_end_prereg.md`.

Before launch, the repaired scene must be opened once in a headless editor parse pass without executing it. The windowed scene then runs once and the independent verifier runs once. Raw output remains `_diag/rotation_end_to_end_gpu.json`; the verifier receipt remains `_diag/rotation_end_to_end_verify.json` and binds both preregistrations. Any further implementation failure stops the campaign as `INCONCLUSIVE—IMPLEMENTATION`.
