# Rotation/stress raw-replay verification preregistration

**Frozen: 2026-09-02, before the first v2 artifact run.**

## Purpose

This addendum closes one evidence gap in G75–G82. The v1 checker reapplied frozen thresholds to producer-reported metrics; it did not recompute those metrics from the states that produced them. The v2 producers therefore emit exact array receipts, and `research/rotation/rotation_verify.py` independently reconstructs every gate statistic from those receipts.

This is an implementation audit, not a new physics probe. The equations, deterministic inputs, step counts, coefficients, G75–G82 thresholds, and decision tree in `research/rotation/rotation_prereg.md` remain frozen and unchanged.

## Artifact contract

The reference artifact schema becomes `cassi.rotation.reference.v2`. The GPU artifact schema becomes `cassi.rotation.gpu.v2`.

Every numerical array receipt has exactly this envelope:

```json
{"dtype": "<f8", "shape": [4, 3], "base64": "..."}
```

- `dtype` is a NumPy dtype string. Reference arrays are little-endian float64 (`<f8`); GPU arrays are little-endian float32 (`<f4`).
- `shape` is the full logical shape.
- `base64` encodes the exact contiguous C-order bytes.
- The replay verifier rejects invalid base64, unsupported dtypes, negative dimensions, and byte lengths inconsistent with `dtype × shape`.

Both artifacts retain their producer-reported `gates` and add a top-level `receipts` object.

### Reference receipts

- `G75`: particle positions, masses, pre-step velocities, accelerations, post-step positions and velocities, mirror matrix, mirrored post-step positions and velocities, aligned-control post-step positions and velocities, and aligned-control masses.
- `G76`: positions, masses, and the before/after particle velocities, field momentum, intrinsic spin, and heat arrays.
- `G77`: attenuated, unit-conductance, zero, and equal-rung scale accelerations plus the final 64-step displacement, momentum, spin, heat, and particle-velocity arrays.

### GPU receipts

- `G78`: baseline and explicit-off bytes for `pos`, `pvel`, `acc`, `ey`, `ei`, and `q`; plus direct runtime observations for workbench readiness and disabled rotation resources/readback.
- `enabled`: complete rotation readbacks before exchange, after one isolated step, and after 64 isolated steps. Each readback contains displacement, momentum, next momentum, spin/heat, orientation, telemetry, particle position, particle velocity, and merge spin.
- `G81`: complete non-particle rotation readbacks for attenuated, unit-conductance, zero, and equal-rung cases.

Reference vector-field receipts use shape `[rungs, grid_n, grid_n, grid_n, 3]`, with scalar heat shaped `[rungs, grid_n, grid_n, grid_n]`. GPU rotation fields use `[rungs, grid_n, grid_n, grid_n, 4]`; GPU particle and orientation receipts use `[particle_count, 4]`; telemetry uses `[16]`. G78 particle buffers use `[particle_count, 4]`, while its scalar `ey`, `ei`, and `q` grids use `[workbench_grid_n, workbench_grid_n, workbench_grid_n]`.

**Post-freeze metadata clarification—2026-09-02:** the initial generic field-shape sentence described the padded GPU rotation layout but did not separately spell out the reference three-vector/scalar layouts or the effective 64³ G78 workbench grid. This clarification changes only shape metadata validation; it changes no state bytes, equations, inputs, metrics, thresholds, or consistency tolerances.

## Independent recomputation

The verifier must not use producer-reported numerical gate metrics to decide G75–G82. It recomputes:

- G75 torque, angular-momentum change, mirrored pseudovector transform, and aligned null directly from particle receipts.
- G76 and G79/G80/G82 total linear and angular ledgers from particle momentum, cell-centered field momentum, and intrinsic spin.
- G76 heat increments from its separate scalar heat receipts and G79 heat increments from the fourth component of the GPU spin/heat receipt.
- G77/G81 attenuation ratios, summed scale momentum, null maxima, and finiteness directly from field arrays.
- G82 quaternion motion, normalization, zero-spin identity, final finiteness, and 64-step ledger drift directly from the three enabled-state receipts.
- G78 byte identity directly from decoded bytes. Readiness and disabled-resource facts are runtime observations and therefore remain exact observed booleans rather than numerical replays.

The original frozen G75–G82 thresholds alone determine the scientific gate results.

## Producer-consistency audit

Producer-reported gate metrics remain in each artifact for human-readable GPU logs and diagnostics. The verifier also checks that each reported decision metric agrees with its raw recomputation:

- reference scalar metrics: `rel_tol = 1e-12`, `abs_tol = 1e-12`;
- GPU scalar metrics: `rel_tol = 1e-5`, `abs_tol = 1e-6`;
- booleans: exact identity.

These tolerances audit serialization and independent accumulation order; they do not replace or relax any G75–G82 threshold. A raw gate may satisfy its physics threshold but still fail the v2 verification result if its producer report is inconsistent.

## Stopping rule and verdict

Run the reference producer, the reference-only replay, the existing windowed GPU scene, and then the combined replay exactly once after implementation. Missing/malformed receipts, non-finite recomputed metrics, producer/replay disagreement, or reference/GPU gate disagreement yields `INCONCLUSIVE—IMPLEMENTATION` under the original decision tree.

After the first run, do not change coefficients, deterministic inputs, step counts, receipt precision, consistency tolerances, or G75–G82 thresholds in response to the outcome. A code defect in receipt emission or replay arithmetic may be corrected only with the defect and correction reported explicitly; the frozen experiment values remain unchanged.

## Execution record—2026-09-02

The reference producer and reference-only replay passed G75–G77 from v2 raw receipts.

The first combined replay classified G80 as `INCONCLUSIVE—IMPLEMENTATION`: the raw-derived G80 threshold result was `PASS`, but producer consistency failed. The initial verifier used vectorized float64 ledger reductions and obtained angular error `2.7479616372338715e-08` and spin-error separation `55718.851034966465`; Godot's sequential float32 `Vector3` ledger reported `1.5565318e-07` and `9836.788`. The cancellation-sensitive ratio remained above the frozen `10.0` threshold under both calculations.

The replay arithmetic was corrected to independently reconstruct Godot's sequential float32 vector accumulation and norm semantics from the same raw bytes. No producer state, equation, input, coefficient, step count, receipt precision, consistency tolerance, or G75–G82 threshold changed. The corrected combined replay passed G75–G82 with every `threshold_pass` and `producer_consistent` flag true.

The final metadata audit made the effective G78 workbench grid and logical array shapes explicit, regenerated the v2 GPU artifact through the real windowed scene, and repeated the combined replay successfully. A negative control then changed only the reported G80 separation to `1.0` while preserving all raw receipts: the verifier retained raw `threshold_pass: True`, set `producer_consistent: False`, returned `G80: FAIL` and `RESULT: FAIL`, exited `1`, and removed the temporary artifact.
