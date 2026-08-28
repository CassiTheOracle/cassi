# CassiQwen L5b — Seeded Projection Sidecar Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Provenance

This is the sole successor to the terminal `FAIL` recorded in `L5-SEEDED-PROJECTION-SCENE-REPORT.md`. It changes exactly one implementation detail: the startup packaging. The CassiQwen-owned `SceneTree` launcher is run through the CassiCosmos project, so its engine resource resolves canonically as `res://scripts/cassi_mind_engine.gd`.

The fixed field seed, grid, evolution, bridge surface, observation, acceptance criteria, and decision tree are unchanged from L5.

## Scope and fixed launch

Run one windowed process:

```text
<Godot 4.7.1 Mono console executable> --path CassiCosmos --script CassiQwen/seeded_mind_engine.gd
```

The launcher creates the existing engine with `N=32`, `auto_step=false`, and `serve_bridge=false`; it internally deposits $(0.25,-0.4,0.6; 1.4562,0.9,1.0)$, flushes the scatter, runs one step, then starts the existing bridge on loopback port 7599.

No CassiCosmos source, shader, scene, or project file is modified. No Qwen request is sent. The only external bridge observation is the L3 adapter’s `ping`, `state`, `project(k=8)` sequence.

## Acceptance criteria

The sole observation must have:

1. `available: true`;
2. `state.step === 1` and $|t-0.005| \le 10^{-9}$;
3. exactly eight finite cells with non-negative $q$;
4. strictly positive first-cell $q$;
5. non-increasing $q$ order; and
6. first-cell coordinates within one grid cell per axis of $(20,10,26)$.

## Decision tree and stopping rule

- Startup/parse/listener failure: `FAIL`.
- Unavailable or malformed sole observation: `FAIL`.
- Any failed acceptance criterion: `FAIL`.
- All criteria pass: `PASS`.

Exactly one launch, one observation, and one managed stop. No retry or parameter change is permitted.
