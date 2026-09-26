# CassiQwen L5c — Native Seeded Bridge Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Provenance

`L5-SEEDED-PROJECTION-SCENE-REPORT.md` and `L5B-SEEDED-PROJECTION-SIDECAR-PREREG.md` closed at `FAIL` before a field observation. Their isolated standalone `SceneTree` packaging did not reproduce the engine’s normal `Node._ready()` lifecycle.

This successor changes one factor only: it uses a normal CassiCosmos `Node` scene with a normal `Node` parent script, matching the already-passing `mind_engine_cache.tscn` lifecycle. The field seed, grid, single step, loopback binding, bridge surface, one-observation limit, and acceptance criteria are unchanged.

## Scope

Add a new, isolated native scene and script in `CassiCosmos/scenes/` and `CassiCosmos/scripts/`:

- `scenes/cassi_qwen_seeded_mind.tscn`
- `scripts/cassi_qwen_seeded_mind.gd`

The script instantiates `res://scripts/cassi_mind_engine.gd` as a child, sets its exported properties before `add_child`, performs its internal seed before enabling the TCP listener, and then allows the L3 adapter’s read-only bridge traffic.

No existing scene, engine source, shader, project file, Qwen artifact, or Qwen server configuration is modified. The scene is launched windowed only.

## Fixed state construction

| Parameter | Value |
|---|---:|
| Grid size | 32 |
| `auto_step` | false |
| Engine bridge before seed | disabled |
| Deposit | $(0.25,-0.4,0.6; 1.4562,0.9,1.0)$ |
| Scatter flush | one internal `_flush_pending()` call |
| PDE evolution | one internal `step_n(1)` call |
| Engine bridge after seed | loopback port 7599 |
| External projection | one `project(k=8)` via the L3 adapter |

No TCP mutation command is used to construct this state.

## Acceptance criteria

The sole L3 observation must satisfy all of:

1. `available: true`.
2. `state.step === 1` and $|state.t-0.005| \le 10^{-9}$.
3. Exactly eight projection cells, all finite, with non-negative $q$.
4. First returned $q > 0$.
5. Returned $q$ values are non-increasing.
6. First cell grid coordinates are each within one cell of $(20,10,26)$.

## Decision and stopping tree

1. Native scene parse, engine ready, seed, PDE step, or listener failure: `FAIL`.
2. The one adapter observation unavailable/malformed: `FAIL`.
3. Any acceptance criterion fails: `FAIL`.
4. All criteria pass: `PASS`.

Exactly one windowed scene launch, one L3 observation, and one managed stop. No alternate seed, additional step, retry, Qwen completion, or code/configuration adjustment during the run.
