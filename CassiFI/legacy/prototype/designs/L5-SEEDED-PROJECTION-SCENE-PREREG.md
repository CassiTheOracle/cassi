# CassiQwen L5 — Seeded Projection Scene Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Scope

This protocol adds one new CassiQwen-owned Godot scene/script pair under `CassiQwen/` that instantiates the existing `CassiCosmos/scripts/cassi_mind_engine.gd` engine as a child. It seeds a fixed two-fluid deposit internally before the bridge is opened, then exposes only the existing read-only bridge surface to the L3 adapter.

No existing CassiCosmos source, shader, scene, or verification file is modified. The Qwen server is not contacted. The test must be windowed, not headless.

## Fixed seed and dynamics

Before beginning the TCP listener, the scene configures:

| Parameter | Fixed value |
|---|---:|
| Grid size | 32 |
| `auto_step` | `false` |
| Deposit position | $(x,y,z)=(0.25,-0.4,0.6)$ |
| Yang deposit | $c_Y=1.4562$ |
| Yin deposit | $c_I=0.9$ |
| Scatter width | $σ=1.0$ |
| PDE steps after seed | 1 |
| Projection | top $k=8$ by $q=E_Y^2+E_I^2$ |

The parent scene must construct the engine with `serve_bridge=false`, add it as a child, confirm its local RenderingDevice/pipeline, call `deposit`, flush the pending scatter, call `step_n(1)`, and only then set `serve_bridge=true` and start the existing bridge listener. It must not call the bridge’s mutable command handler for this setup.

## Question

Can the live CassiQwen bridge observe a reproducible, nonzero top-$q$ field projection seeded entirely within an explicit local scene?

## Deterministic acceptance checks

The single live read-only observation must satisfy all of these:

1. `available` is true.
2. `state.step` is exactly 1 and `state.t` is exactly 0.005 within $10^{-9}$.
3. Projection contains exactly eight cells.
4. Every reported scalar is finite and every `q` is non-negative.
5. First cell `q` is strictly positive.
6. `q` is non-increasing across the returned cells.
7. The first cell grid coordinate is within one cell per axis of the known TSC anchor. For N=32, the anchor is $(20,10,26)$.

## Decision tree

1. Scene parse, engine creation, pipeline, or listener failure: `FAIL`.
2. Adapter unavailable/malformed result: `FAIL`.
3. Any acceptance check fails: `FAIL`.
4. Every acceptance check passes: `PASS`.

No alternate seed, extra PDE step, retry, or changed threshold is allowed under this protocol.

## Stopping rule

One windowed scene launch, one live observation, and one managed stop. No Qwen request, no model change, and no externally issued mutable bridge command.

## Interpretation tiers

- **T1 measured:** the seeded state and projected cell values returned over the live bridge.
- **T2 inferred:** a future CassiQwen shadow protocol can consume a nonzero bounded observation with reproducible geometry.
- **T3 speculative:** that any mapping of projection cells to language-model retrieval improves a task.

## Terminal contract

The result is `PASS` or `FAIL`. This protocol does not test a retrieval mapping or steer Qwen.
