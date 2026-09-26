# L46 Harmonic Write Causal Crossover — Frozen Preregistration

## Status: FROZEN — 2026-08-30

This joint Brain–Mind protocol is grounded in CassiMind message `01a05463-143e-7db5-871f-098ca182a281`. CassiMind selected the preserved L40 `s0-horizon` field immediately before the S1 write as the canonical causal checkpoint, retained `S3=S1` as the downstream direction-sensitive gate, and required an `I/U/W/UW` crossover using the unchanged L39 write and unchanged L42 cyclic age lift.

No L46 implementation, smoke, or canonical execution existed when this protocol was frozen.

## Relationship to L45

- `supersedes`: none;
- `depends_on`: immutable L39/L40 ordered-relational evidence and the unchanged L42 `U_age` source;
- `preserves`: `designs/L45-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md`, SHA-256 `32bc4e741e08205d8badc4b9d307b27cd0681274d5a384b2ed63cd2182f46a44`;
- `execution_dependency`: L45 implementation ownership, execution, or adoption is blocked until L46 has a complete receipt and CassiMind has reviewed the L46 raw arrays;
- `scope`: L46 tests the causal value and failure location of the existing cyclic `U_age`. Because `U_age^7=I`, L46 cannot establish bounded retirement under eight or more writes and cannot adopt or reject the L45 absorbing boundary.

L45 is neither renamed nor amended by L46.

## Ownership and integration

This CassiBrain session owns the L46 design, causal runner, focused verifier tests, source-independent verifier, and final evidence integration. L46 adds no field module and changes no L39–L45 field source.

CassiMind independently reviews the raw native arrays, causal assumptions, and behavioral interpretation. CassiMind is not the formal verifier and supplies no receipt verdict fields. The formal verifier reconstructs every declared coordinate and readout from raw arrays without importing runner or field-controller mathematics. This CassiBrain session is the sole integration lane.

## Question

At the earliest observed L40 divergence, does one existing L42 cyclic age lift causally separate the contaminated S0 trace from an otherwise unchanged S1 Givens write, or is the subsequent rolling failure already caused by write geometry, evolution, or readout?

The causal factors are:

- `I`: no age lift and no write;
- `U`: one unchanged L42 age lift and no write;
- `W`: no age lift and one unchanged L39 Givens write of S1;
- `UW`: one unchanged L42 age lift followed by the identical L39 Givens write of S1.

## Frozen identities and files

Existing profiles remain unchanged:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- ordered operator/readout: `cassi.qi-ordered-relational-chromatic-recall.v1`;
- harmonic operator/readout: `cassi.qi-harmonic-age-ladder.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New evidence identities:

- board: `cassi.l46.harmonic-write-causal-crossover-board.v1`;
- traces: `cassi.l46.harmonic-write-causal-crossover-traces.v1`;
- verification: `cassi.l46.harmonic-write-causal-crossover-verification.v1`.

New files:

- `designs/L46-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md`;
- `tests/test_l46_harmonic_write_causal_crossover.py`;
- `verification/run_l46_harmonic_write_causal_crossover.py`;
- `verification/verify_l46_harmonic_write_causal_crossover.py`.

Raw evidence:

- `_diag/l46-harmonic-write-causal-crossover/l46-board.json`;
- `_diag/l46-harmonic-write-causal-crossover/l46-traces.npz`.

Verified evidence:

- `artifacts/l46-harmonic-write-causal-crossover/L46-HARMONIC-WRITE-CAUSAL-CROSSOVER-REPORT.md`;
- `artifacts/l46-harmonic-write-causal-crossover/l46-verification.json`.

## Immutable prefix evidence

L46 hash-binds and never overwrites:

- L40 board SHA-256 `44a0baff773c85405c35e0d92da405e8157e3617b811da75f6d2f00e88811530`;
- L40 traces SHA-256 `21549f5bd65fd6e10247295bf59b48d6b35ed1b4d1b1a0a857fffafce32f045a`;
- L40 verification SHA-256 `b5fd0f085e876eebd589dc7cf8a6353d20b93e1616c014f13d77c11a8aca8ca7`;
- unchanged `cassi_harmonic_age_field.py` SHA-256 `b4f053f2d441bf612842a88ed13a02d2554bc31c5711a460a9c72bfef417aa61`.

The preserved float32 field hashes, computed from contiguous native tensor bytes, are:

- `s0-deposit`: `e8370b2ebbe4d3afb155cf2a5fd3d866462f8d7b7481806536ef103c30c8a15c`;
- `s0-horizon`: `493a231a6606a7530b959880646b34e9142c9bdf577057e940211b33974ae1f2`.

At preserved `s0-horizon`:

- emitted/current symbols equal `S0` in 8/8 rows;
- current is available in 8/8 rows;
- relational availability is unexpectedly true in 8/8 rows;
- relational symbols also equal `S0` in 8/8 rows, although the preregistered predecessor is unavailable;
- prefix clamp count is zero;
- prefix maximum modulation input-energy drift is exactly zero;
- active amplitude maximum is `1.936202883720398`;
- epsilon lies in `[0.001434104866348207,0.9794970750808716]`;
- inactive packed coordinates are exact zero.

These are frozen contaminated starting conditions, not success gates to be repaired.

## Canonical configuration and schedule

Canonical execution uses:

- AMD Radeon RX 7900 XTX through PyTorch/ROCm;
- float32;
- seven channels;
- `mode_count=2048`, active width 1024;
- alphabet size 260;
- batch size eight;
- trust `1`;
- eight solver evolution steps per blank tick;
- immutable active amplitude bound `8`;
- immutable epsilon bound `[0,4096]`;
- L42 harmonic readout energy floor `2e-6`;
- L39 relational readout floor `1e-8`.

Frozen symbols are

- `S0 = (0,37,74,111,148,185,222,259)`;
- `S1 = (S0+97) mod 260`;
- `S2 = (S0+181) mod 260`;
- `S3 = S1`.

## Prefix reproduction

The L46 runner must reproduce the unchanged L40 prefix exactly:

1. construct a fresh L39 ordered-relational field;
2. run the unchanged initial heartbeat;
3. run one unchanged S0 tick with trust `1` and eight evolution steps;
4. capture `s0-deposit`;
5. run sixteen unchanged blank ticks, each with eight evolution steps;
6. capture `s0-horizon` and its readout.

The reproduced fields must be byte-identical to both preserved L40 fields and match their frozen SHA-256 values. The reproduced `s0-horizon` readout must include the same unexpected relational availability and symbol in all rows. Any prefix mismatch returns `FAIL` and stops before the causal fork.

No new heartbeat is inserted between reproduced `s0-horizon` and the fork. This preserves `s0-horizon` itself as the canonical pre-write checkpoint and isolates the Givens write from heartbeat.

## Native operators

For channel index `j`, let

\[
p_j=\exp(2\pi i j/7).
\]

The unchanged L42 age lift is

\[
U(D)_j=p_jD_j,
\qquad
U(VD)_j=p_jVD_j,
\]

with `C`, `VC`, epsilon, and inactive coordinates exact. In the orthonormal physical channel DFT,

\[
z_k=\frac1{\sqrt7}\sum_{j=0}^{6}p_j^{-k}D_j,
\]

it maps old physical harmonic `k` to `(k+1) mod 7`. Age order is physical harmonics `(1,2,3,4,5,6,0)`.

`W` is the unchanged L39 inherited Givens modulation with S1, trust `1`, and the fixed shared codebook. `W` and `UW` call the same base write implementation exactly once. `UW` applies `U` first and must not call L42 modulation afterward because that would apply a second lift.

## Immediate 2x2 fork

Create four byte-identical clones of the reproduced `s0-horizon` field. Record the contiguous tensor SHA-256 for every clone and the SHA-256 of one shared contiguous S1 tensor. Apply:

- branch `I`: identity;
- branch `U`: `U` only;
- branch `W`: `W(S1)` only;
- branch `UW`: `U`, then the identical `W(S1)`.

There is no heartbeat, bound outside the unchanged write, evolution, or readout before immediate native coordinates are captured. `I` and `U` have declared zero write drift and zero clamp count. The runner captures native coordinates before any public readout and captures the field again after both unchanged L39 and L42 readouts.

## Blank-horizon forks

From each immediate post-branch field, run 128 consecutive unchanged no-symbol L39 ticks. No additional `U` is applied because no symbol is written. Capture all four branches at:

- immediate (`0` blank ticks);
- `8` blank ticks;
- `16` blank ticks;
- `128` blank ticks.

The `UW` branch must retain native age-zero/age-one coefficients and the availability-qualified public tuple `[S1,S0]` at all four checkpoints. The other branches are causal controls and have no post-hoc semantic target; all of their continuous coordinates, readouts, bounds, and clamp telemetry are still independently reconstructed.

## Rolling and reversal continuation

From a separate clone of immediate `UW`:

1. run sixteen blank ticks and capture `s1-horizon`;
2. apply one `U` and the unchanged `W(S2)`, capture `s2-deposit`;
3. run sixteen blank ticks, capture `s2-horizon`;
4. apply one `U` and the unchanged `W(S3)`, capture `s3-reversal-deposit`;
5. run sixteen blank ticks, capture `s3-reversal-horizon`.

Include immediate `UW` as `s1-deposit`, yielding six sequence checkpoints. Required availability-qualified age tuples in every row are:

- `s1-deposit` and `s1-horizon`: `[S1,S0]`;
- `s2-deposit` and `s2-horizon`: `[S2,S1]`;
- `s3-reversal-deposit` and `s3-reversal-horizon`: `[S1,S2]`.

At the reversal, S0 must not occupy the predecessor slot. This is the direction-sensitive gate distinguishing ordered recent history from unordered recent-set membership.

After `s1-horizon`, serialize only the native field tensor plus frozen profile/config identities, load it into fresh unchanged controllers, and continue through S2 and S3 beside the uninterrupted branch. Resumed and uninterrupted fields and readouts must remain byte-identical after every subsequent event.

## Independent native reconstruction

The verifier must implement the native unpacking, DFT, codebook projection, availability, harmonic readout, L39 relational readout, and Givens write directly in NumPy. It may import only canonical JSON/file helpers, never either field controller, the L46 runner, or controller readout/operator formulas.

For each stored field it reconstructs:

- complex `C`, `D`, `VC`, and `VD` with shape `[7,1024,8]`;
- physical-harmonic `D` and `VD` with shape `[7,1024,8]`, indexed `k=0,...,6`;
- age-ordered harmonic tensors using `(1,2,3,4,5,6,0)`;
- complex codebook coefficients with shape `[8,7,260]`;
- age scores, energies, symbols, and availability with shapes `[8,7,260]`, `[8,7]`, `[8,7]`, and `[8,7]`;
- the availability-qualified current/predecessor tuple `[8,2]`, using `-1` for an unavailable slot;
- unchanged L39 current, relational, and ordered scores and categorical availability.

The complex codebook coefficient is frozen as

\[
c_{bks}=\frac1{1024}\sum_m \overline{u_{sm}}z^D_{kmb},
\]

with score `|c|^2`. Harmonic availability is decided from mean native harmonic energy before any argmax. An unavailable argmax is recorded diagnostically and is never a semantic gate.

## Frozen raw array contract

The NPZ array set is exact. Required identity arrays are:

- `schema_id`: scalar Unicode;
- `branch_names`: `[4]` Unicode, exactly `I,U,W,UW`;
- `branch_checkpoint_names`: `[4]` Unicode, exactly `immediate,tick-8,tick-16,tick-128`;
- `sequence_checkpoint_names`: `[6]` Unicode, exactly `s1-deposit,s1-horizon,s2-deposit,s2-horizon,s3-reversal-deposit,s3-reversal-horizon`;
- `stage_symbols`: `[4,8]`, int64;
- `codebook`: `[260,1024,2]`, float32;
- `channel_phase`: `[7,2]`, float32;
- `prefix_field_sha256`, `fork_field_sha256`, `s1_symbol_sha256`: scalar or fixed-length Unicode SHA-256 values.

Required prefix arrays are:

- `prefix_checkpoint_fields` and `prefix_post_readout_fields`: `[2,7,18432,8]`, float32, ordered `s0-deposit,s0-horizon`;
- `prefix_emitted_symbols`, `prefix_current_symbols`, `prefix_relational_symbols`: `[2,8]`, int64;
- `prefix_current_available`, `prefix_relational_available`: `[2,8]`, bool;
- `prefix_current_scores`, `prefix_relational_scores`, `prefix_ordered_scores`: `[2,8,260]`, float32;
- `prefix_clamp_counts`: `[18]`, int64;
- `prefix_input_energy_drift`: `[17,8]`, float32.

Required branch arrays are:

- `branch_pre_fields`: `[4,7,18432,8]`, float32;
- `branch_checkpoint_fields` and `branch_post_readout_fields`: `[4,4,7,18432,8]`, float32;
- `branch_harmonic_d`, `branch_harmonic_vd`: `[4,4,7,1024,8]`, complex64 in physical-harmonic order;
- `branch_codebook_coefficients`: `[4,4,8,7,260]`, complex64 in age order;
- `branch_age_scores`: `[4,4,8,7,260]`, float32;
- `branch_age_energies`: `[4,4,8,7]`, float32;
- `branch_age_symbols`: `[4,4,8,7]`, int64;
- `branch_age_available`: `[4,4,8,7]`, bool;
- `branch_current_predecessor`: `[4,4,8,2]`, int64;
- `branch_ordered_current_symbols`, `branch_ordered_relational_symbols`: `[4,4,8]`, int64;
- `branch_ordered_current_available`, `branch_ordered_relational_available`: `[4,4,8]`, bool;
- `branch_ordered_scores`: `[4,4,8,260]`, float32;
- `branch_clamp_counts`: `[4,129]`, int64, containing the immediate operation and 128 blank ticks;
- `branch_input_energy_drift`: `[4,129,8]`, float32;
- `branch_dynamic_energy`: `[4,4,7,8]`, float32;
- `branch_maximum_absolute_field`: `[4,4]`, float32.

Required sequence arrays are:

- `sequence_fields` and `sequence_post_readout_fields`: `[6,7,18432,8]`, float32;
- `sequence_harmonic_d`, `sequence_harmonic_vd`: `[6,7,1024,8]`, complex64;
- `sequence_codebook_coefficients`: `[6,8,7,260]`, complex64;
- `sequence_age_scores`: `[6,8,7,260]`, float32;
- `sequence_age_energies`: `[6,8,7]`, float32;
- `sequence_age_symbols`: `[6,8,7]`, int64;
- `sequence_age_available`: `[6,8,7]`, bool;
- `sequence_current_predecessor`: `[6,8,2]`, int64;
- `sequence_ordered_current_symbols`, `sequence_ordered_relational_symbols`: `[6,8]`, int64;
- `sequence_ordered_current_available`, `sequence_ordered_relational_available`: `[6,8]`, bool;
- `sequence_ordered_scores`: `[6,8,260]`, float32;
- `sequence_clamp_counts`: `[51]`, int64, containing initial UW, forty-eight blanks, S2, and S3 writes;
- `sequence_input_energy_drift`: `[51,8]`, float32;
- `resume_uninterrupted_sha256`, `resume_reloaded_sha256`: `[34]` fixed-length Unicode, one pair after each post-reload event.

Every required array is stored even when a branch has no semantic target. Additional arrays are prohibited because they would create an unfrozen evidence surface.

## Frozen tolerances

Focused CPU float64 controls use zero relative tolerance and absolute tolerance `2e-12` for native coordinate, DFT, codebook coefficient, energy, and write reconstruction. Exact identity, untouched coordinates, readout immutability, and save/reload checks remain bitwise.

Canonical float32 checks use:

- native `C,D,VC,VD`, physical harmonics, codebook coefficients, DFT relocation, and dynamic energy: `atol=3e-6`, `rtol=3e-6`;
- current, relational, ordered, and harmonic scores: `atol=3e-5`, `rtol=2e-4`;
- maximum Givens input-energy drift: `2e-6`;
- maximum active component amplitude: `8`;
- epsilon range: `[0,4096]`;
- inactive coordinates: exact zero;
- clamp count: exact zero;
- discrete symbols, availability, order, clone hashes, and save/reload hashes: exact.

These values are frozen before implementation and may not be widened after any smoke or canonical result.

## Mechanical gates

The independent verifier requires:

1. exact preregistration, source, L40 input, board, trace, and schema hashes;
2. exact L46 raw array set, shape, dtype, order, and finiteness;
3. canonical float32 execution on `AMD Radeon RX 7900 XTX` with a recorded HIP version;
4. exact prefix reproduction, including both frozen field hashes and contaminated `s0-horizon` readout;
5. four byte-identical fork fields and one identical S1 symbol tensor;
6. branch `I` byte-identical before and after identity and both readouts;
7. branch `U` changes only `D` and `VD`, relocates every physical harmonic `k` to `(k+1) mod 7`, and conserves their norm within tolerance;
8. `W` and `UW` use the same independently reconstructed Givens write exactly once;
9. runner-stored native harmonics, coefficients, scores, energies, availability, tuples, and both public readouts match independent reconstruction;
10. neither public readout mutates any field;
11. every active coordinate remains within `8`, every epsilon value within `[0,4096]`, every inactive coordinate exactly zero, and every input-energy drift within `2e-6`;
12. every prefix, branch, horizon, sequence, and resume clamp count is zero;
13. save/reload continuation remains byte-identical to uninterrupted execution after every event;
14. focused verifier mutations reject a changed prefix hash, clone, S1 symbol vector, native harmonic, availability bit, unavailable argmax interpretation, clamp, inactive tail, or resume hash.

Any failed mechanical gate returns `FAIL` and stops functional interpretation.

## Functional and causal gates

Every semantic gate is exact in all eight rows.

Immediate `UW` must have:

- S1 available and selected at age zero/physical harmonic one;
- S0 available and selected at age one/physical harmonic two;
- availability-qualified tuple `[S1,S0]`;
- zero clamps.

No age-separation claim is made for `W`. The controls instead establish attribution:

- if `U` fails native relocation, classify `AGE_ROTATION_FAILURE`;
- if `W` fails independent unchanged-write reconstruction, classify `WRITE_GEOMETRY_FAILURE`;
- if `U` and `W` pass but `UW` fails their independently composed native expectation, classify `DEPOSIT_INTERACTION_FAILURE`;
- if immediate `UW` native coordinates pass but its public tuple fails, classify `READOUT_FAILURE`.

At 8, 16, and 128 blank ticks:

- if `UW` native S1/S0 age coordinates no longer satisfy the immediate ordering while immediate `UW` passed, classify `EVOLUTION_FAILURE`;
- if native ordering remains correct but the public tuple differs, classify `READOUT_FAILURE`;
- otherwise require `[S1,S0]` exactly.

In the rolling continuation, require `[S2,S1]` and then reversal `[S1,S2]` at both deposit and sixteen-tick horizon checkpoints. A failure after prior gates pass is `ROLLING_SEQUENCE_FAILURE`. A stale S0 predecessor at reversal is an explicit failure.

Causal classification is `SUPPORTED` only if every immediate, horizon, rolling, reversal, bound, clamp, persistence, and readout gate passes.

## Verdict and stopping rule

Return:

- `SUPPORTS` when mechanics pass and causal classification is `SUPPORTED`;
- `CONTRADICTS` when mechanics pass but any functional gate fails, with the earliest frozen causal classification;
- `FAIL` for prefix, integrity, schema, source, device, clone, reconstruction, tolerance, nonfinite, mutation, energy, bound, clamp, or persistence failure;
- `INCOMPLETE` only when canonical evidence is interrupted or unavailable.

`SUPPORTS` establishes only that existing `U_age` causally provides four-write ordered separation through the tested horizons. It does not establish bounded retirement and does not authorize L45 execution without a separate Brain–Mind review.

Run focused CPU contracts and verifier-mutation tests, then one disposable CPU smoke. Delete smoke outputs. Run exactly one canonical RX 7900 XTX board and one source-independent verifier. Preserve the first complete board and receipt. Stop after the first complete verdict. Any change to the prefix, fork checkpoint, symbols, operators, branch ordering, arrays, horizons, sequence, persistence boundary, gates, tolerances, source dependencies, or stopping rule requires a new preregistration and evidence identity.
