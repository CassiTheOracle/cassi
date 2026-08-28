# Current global-RenderingDevice visibility and volumetric persistence — preregistration

Date: 2026-08-17  
Status: **FROZEN BEFORE FURTHER PERFORMANCE RUNS**  
Scope: current producer/consumer path only; no production-code change and no edit to `scenes/main.tscn`.

## 1. Purpose and evidence rule

This document freezes the acceptance gates for the visibility/persistence program. It is a measurement contract, not a report of results. A run may be cited only when its artifact records the current producer identity, current global `RenderingDevice` path, configuration, seed, commit/worktree description, and host timing/readback accounting.

The following are **not current timing evidence**: stale local-RenderingDevice runs, snapshot logs, logs whose producer RID/path is not recorded, or runs that predate the current shader/buffer/dispatch wiring. They may motivate a probe, but they cannot establish a performance verdict. Headless runs cannot establish RD behavior on this rig. Scene GPU runs are windowed.

Frozen verdict vocabulary:

- `PASS`: every applicable gate passes with no missing evidence.
- `FAIL`: an applicable gate has a measured threshold violation.
- `NULL`: the requested signal is absent under a valid, bounded scenario.
- `INVALID`: a prerequisite, identity, finiteness, or accounting gate is missing/ambiguous; no performance conclusion is allowed.
- `ADOPT`: all mandatory gates pass and the path is eligible for the next implementation stage.
- `REJECT`: a mandatory gate fails or a known artifact path is being used as current evidence.
- `HOLD`: measurements are valid but the decision is intentionally deferred by a frozen stopping rule.

All claims are tiered: `T1 measured`, `T2 inferred from T1`, or `T3 speculative`. A missing measurement remains missing; it is never inferred from a screenshot or a stale log.

## 2. Frozen scenarios

Each scenario runs from a fresh process, fixed seed, and recorded configuration. The same scenario is repeated only as a pre-registered new record, never as an unannounced retry.

| ID | Scenario | Required arms |
|---|---|---|
| S1 | Decoupled visibility/persistence | decoupled on; finite state; positive-mass state; render buffer; AABB/frustum state |
| S2 | Current global-RD marker | one current global RD; sentinel write/readback; producer RID/path identity at creation and dispatch |
| S3 | Boxless coordinate/hash parity | render-local = world − window center; site tile = render-local + extents; same full-axis tile geometry in hash build/query |
| S4 | Open render topology | open-boundary topology generation; generation changes only after coherent site/JFA/topology rebuild; no stale history acceptance |
| S5 | Optical path | overflow counters, transmittance/accumulation bounds, and finite output under the frozen scene |
| S6 | Image precision | RGBA16F image error versus an RGBA32F reference on the same current producer and dispatch |
| S7 | Dirty-state identity | default-off path byte identity, including push constants, dispatch count/order, and output buffers |
| S8 | Dynamic resolution | quality statistic and work/frame budget across frozen resolutions; no post-hoc scale selection |
| S9 | Temporal history | rejection on topology-generation, transform, camera-cut, and invalid-depth changes; accepted-history error bound |
| S10 | Adaptive scheduling | quality floor, cadence, bounded backlog, and host-observed frame/dispatch cost |

No scenario may silently substitute a local RD, a CPU snapshot, or a different producer.

## 3. Mandatory diagnostic record

Every current probe record must emit machine-readable fields (JSON or equivalent) for:

1. **Producer identity:** scene/path, shader resource paths and hashes when available, current global RD marker, RID validity plus creation/dispatch identity, producer generation, and whether the path is inline or decoupled.
2. **Raw/render positions:** sampled raw particle/site positions, window center, extents, canonical render-local positions, and the transform used by the consumer.
3. **Mass and finiteness:** finite count, positive-mass count, non-finite count, minimum/maximum positive mass, and explicit distinction between zero/dead mass and non-finite state.
4. **Envelope/AABB/frustum:** envelope inclusion count, MultiMesh/render AABB center and half-extents, particle-size margin, camera position/projection, frustum inclusion count, and the applied window transform.
5. **Render buffer:** MultiMesh RID, instance count, buffer byte size, producer write counter, consumer/read counter where available, and sampled buffer values. A screenshot alone is insufficient.
6. **Dispatch/readback accounting:** current global-RD dispatch count/list labels, submit/readback count, bytes read back, bytes uploaded, host wall time, GPU timestamp if available, and whether each readback was blocking.
7. **Topology/history:** topology generation, graph source, open/periodic mode, transform generation, history accepted/rejected counts and reasons.

The record must distinguish `unknown` from zero. A zero count is a measurement; an omitted field is `INVALID` for any gate that needs it.

## 4. Gates and thresholds

Thresholds are frozen before any new performance run.

### G1 — decoupled finite/mass/render/AABB persistence

At every sampled checkpoint after bootstrap and during the fixed observation window: all sampled raw positions, render-local positions, masses, extents, AABB values, and render-buffer values are finite. Positive-mass count is non-zero and does not drop by more than 1% between adjacent checkpoints unless the scenario explicitly records a merge/accretion event. Render-buffer count equals the configured live instance count, and the AABB contains every expected render-local position plus the frozen particle margin. A missing `_ml_ready`/engine readiness marker is `INVALID`, not a pass.

### G2 — current one-RD marker

The sentinel dispatch writes the expected marker and the settled readback returns it exactly. Producer and dispatch identities must match; current global-RD path must be explicit. Any local-RD-only or snapshot-only result is `INVALID` for current timing and `REJECT` as evidence substitution.

### G3 — boxless coordinate/hash parity

For every sampled site/particle, the recorded transform satisfies `tile = render_local + extents` and `render_local = world − window_center` within `1e-6` absolute error per component. Hash build and query use identical full per-axis tile extents and cell mapping. Any axis mismatch, stale center, or mixed-space distance is `FAIL`.

### G4 — open topology generation integrity

Each topology generation is monotonic and changes only after a coherent rebuild. Open mode contains no unmarked periodic seam edge. Every accepted history sample carries the generation/transform it used. A generation or transform change with accepted old history is `FAIL`; missing generation metadata is `INVALID`.

### G5 — optical overflow/transmittance

All optical accumulators and transmittance values are finite. Transmittance remains in `[0,1]` within `1e-6`; overflow count is zero; NaN/Inf count is zero. Any overflow or non-finite sample is `FAIL`, not clamped into a pass.

### G6 — RGBA16F image error

Against the same current producer and scene, compute per-pixel absolute and relative error against RGBA32F. Mandatory bound: finite-pixel max absolute error `<= 2e-3` for normalized channels and p99 absolute error `<= 5e-4`; alpha/transmittance uses the G5 bound. Missing matched reference or mismatched producer identity is `INVALID`.

### G7 — dirty-state bit identity

Default-off output buffers and serialized dispatch/push-constant records are byte-identical between control and the unchanged current path over the frozen short run. Any byte difference is `FAIL`; an unrecorded dirty state is `INVALID`. This is an identity gate, not a perceptual screenshot comparison.

### G8 — dynamic-resolution quality

For each frozen resolution arm, report finite output, p99 image error versus the reference, topology/temporal validity, and host frame time. Quality must satisfy G5/G6 and p99 error must not exceed the frozen reference bound. Resolution is not selected post hoc: all listed arms are reported.

### G9 — temporal history rejection

Injected topology-generation, transform, camera-cut, and invalid-depth changes must reject history on the first affected frame; unchanged stable frames may accept history. No rejected-history frame may contribute prior color. Accepted-history output remains within G6 error bounds. Missing rejection reason is `INVALID`.

### G10 — adaptive scheduling quality/performance

Every scheduled pass reports cadence, skipped count, backlog, host frame time, dispatch count, and readback bytes. Quality gates remain G5/G6/G9. No unbounded backlog, TDR, or omitted accounting is acceptable. Host timing is reported as wall-clock timing with configuration and readback bytes; stale logs do not satisfy this gate.

## 5. Decision tree and stopping rules

1. If producer identity, current global-RD marker, readiness, finiteness, or accounting is missing: `INVALID`; stop the run and repair only the measurement path.
2. If G1–G4 fail: `REJECT` the visibility/coordinate path; stop performance work until the persistence or coordinate contract is restored.
3. If G5 fails: `REJECT` optical output; no clamp or threshold change is permitted within this preregistration.
4. If G6 fails while G1–G5 pass: `FAIL` precision arm; do not tune the image-error threshold. A new preregistration may change exactly one declared representation variable.
5. If G7 fails: `REJECT` the default-off change and stop all downstream comparisons.
6. If G8–G10 fail with earlier correctness gates passing: `HOLD` correctness adoption and report the measured quality/performance failure; no post-hoc resolution, cadence, or history tuning.
7. If all applicable gates pass with complete records: `ADOPT` the current measurement path for the next implementation slice.
8. Stop after the first terminal verdict for each scenario. A new seed, resolution, cadence, producer, RD type, or threshold is a new preregistration, not a continuation.

The report must include the complete gate table, raw artifact path, exact configuration, and the reason for every `INVALID`, `FAIL`, `NULL`, `HOLD`, `REJECT`, or `ADOPT`. No performance claim may be made from a partial run.

## 6. Present-state report template

**Run ID:** `<date/time and unique id>`  
**Producer:** `<current scene/path, shader/resource identity>`  
**RD:** `<global RenderingDevice marker and RID identity>`  
**Config/seed:** `<complete values>`  
**Host timing:** `<wall time, GPU time if available, dispatches, readbacks, bytes>`  
**Gate table:** `G1 … G10` with `PASS/FAIL/NULL/INVALID/HOLD` and measured values.  
**Verdict:** one frozen vocabulary term, plus tier (`T1/T2/T3`).  
**Non-claims:** list every unmeasured quantity and every stale artifact excluded from timing evidence.
