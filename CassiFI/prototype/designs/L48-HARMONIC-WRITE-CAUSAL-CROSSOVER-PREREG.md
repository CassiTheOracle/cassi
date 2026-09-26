# L48 Harmonic Write Causal Crossover — Corrected Frozen Preregistration

## Status: FROZEN CORRECTED — 2026-08-30; no implementation or run

This joint Brain–Mind protocol corrects the blocked L46 contract without editing it. It is grounded in CassiMind contract review `01a05474-1345-7508-b606-309ab0f1d999`. CassiMind accepted the physical harmonic convention, preserved L40 fork, `I/U/W/UW` causal composition, horizons, rolling reversal, persistence boundary, raw shapes, tolerances, and functional scope. It blocked L46 before implementation because L46 misstated the immutable L42 availability floor, made unavailable argmax comparison ambiguous, did not freeze a sufficiently explicit bare-write bypass and focused proof, and did not enumerate the source dependency closure.

No L48 implementation, focused test, smoke, raw evidence, or canonical execution existed when this protocol was frozen.

## Relationship to L46, L47, and L45

- `corrects_before_run`: `designs/L46-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md`, SHA-256 `1177ad06111a7c99037595bf59b48d6b35ed1b4d1b1a0a857fffafce32f045a`;
- `L46_status`: `BLOCKED_BEFORE_IMPLEMENTATION`; its identities remain reserved and it receives no implementation or evidence;
- `preserves`: `designs/L47-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md`, SHA-256 `533e3d1a2017addd9ecf26fbdf6c5ea126394485a54c14bfb486a80c940bdb32`, approved only as a corrected deferred contract;
- `execution_dependency`: L47 ownership, implementation, smoke, and canonical execution remain blocked until L48 has one complete receipt and CassiMind has reviewed its raw arrays;
- `preserves`: `designs/L45-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md`, SHA-256 `32bc4e741e08205d8badc4b9d307b27cd0681274d5a384b2ed63cd2182f46a44`, status `SUPERSEDED_BEFORE_RUN`;
- `scope`: L48 tests the causal value and failure location of the existing cyclic `U_age`. Because `U_age^7=I`, L48 cannot establish bounded retirement and cannot adopt or reject an absorbing boundary.

L45, L46, and L47 are not renamed or amended by L48. After a complete L48 receipt and raw-array review, CassiMind decides whether L47's deferred dependency is satisfied by this corrected replacement protocol or whether the absorbing experiment requires a fresh evidence identity.

## Ownership and integration

This CassiBrain session owns the L48 design, causal runner, focused tests, source-independent verifier, and evidence integration. L48 adds no field module and changes no L39–L47 field source.

CassiMind independently reviews the raw native arrays, causal assumptions, and behavioral interpretation. CassiMind is not the formal verifier and supplies no receipt verdict fields. The formal verifier reconstructs every declared coordinate and readout from raw arrays without importing runner or field-controller mathematics. This CassiBrain session is the sole integration lane.

Implementation, smoke, and canonical execution require an explicit CassiMind approval of this exact preregistration hash.

## Question

At the earliest observed L40 divergence, does one existing L42 cyclic age lift causally separate the contaminated S0 trace from an otherwise unchanged S1 Givens write, or is the subsequent rolling failure already caused by write geometry, evolution, or readout?

The causal factors are:

- `I`: no age lift and no write;
- `U`: one unchanged L42 age lift and no write;
- `W`: no age lift and one inherited bare Givens write of S1;
- `UW`: one unchanged L42 age lift followed by the identical inherited bare Givens write of S1.

## Frozen identities and files

Existing profiles remain unchanged:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- ordered operator/readout: `cassi.qi-ordered-relational-chromatic-recall.v1`;
- harmonic operator/readout: `cassi.qi-harmonic-age-ladder.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New evidence identities are:

- protocol: `cassi.l48.harmonic-write-causal-crossover-protocol.v1`;
- board: `cassi.l48.harmonic-write-causal-crossover-board.v1`;
- traces: `cassi.l48.harmonic-write-causal-crossover-traces.v1`;
- verification: `cassi.l48.harmonic-write-causal-crossover-verification.v1`.

New files are:

- `designs/L48-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md`;
- `tests/test_l48_harmonic_write_causal_crossover.py`;
- `verification/run_l48_harmonic_write_causal_crossover.py`;
- `verification/verify_l48_harmonic_write_causal_crossover.py`.

Raw evidence is:

- `_diag/l48-harmonic-write-causal-crossover/l48-board.json`;
- `_diag/l48-harmonic-write-causal-crossover/l48-traces.npz`.

Verified evidence is:

- `artifacts/l48-harmonic-write-causal-crossover/L48-HARMONIC-WRITE-CAUSAL-CROSSOVER-REPORT.md`;
- `artifacts/l48-harmonic-write-causal-crossover/l48-verification.json`.

## Immutable source dependency closure

The board must contain a `source_sha256` object whose key set is exactly the following paths. The independent verifier must require the same exact key set and recompute every hash before reading functional results.

Frozen controller/runtime closure:

- `cassi_qi_profile.py`: `d6eda20a1cf45032191d8f52ece3c4cffca3dfafa83b0052dd1bd89b8f738238` — profile serialization used by native state persistence;
- `cassi_qi_field.py`: `31ca9a9c878b5397f96cffc6aaa7245b2d0cc70847b8d8c04e5a6881c3393b9b` — state, fixed codebook, validation, and persistence substrate;
- `cassi_prismatic_field.py`: `dc3fc1143c762ee0b9e024f3f8e2a7d8a4353c60c55403b344ff01785ec41b29` — inherited heartbeat and nonlinear solver, including `_evolve_unchecked`;
- `cassi_white_chromatic_field.py`: `3ca4f7d9eb28f0e8450338f88498e03e02551d65d7146ea0607b9490fe283674` — inherited carrier projection, bare Givens `_modulate_unchecked`, current availability, and tick composition;
- `cassi_cyclic_chromatic_field.py`: `643310f91d468771daf1a0a162999b473f9775246798b32b4411b58be47caf6b` — native C/D layout, cyclic energy, and bound;
- `cassi_relational_chromatic_field.py`: `87fefae8a9d73c2ba420a547bc5bf48207567e8f0495237e04736a599304b978` — relational trace and readout;
- `cassi_ordered_relational_field.py`: `c02260a0f0e778ad811a3fdc04b0c6493775d808fcef3458d88391928f978380` — L39 ordered current/predecessor readout;
- `cassi_harmonic_age_field.py`: `b4f053f2d441bf612842a88ed13a02d2554bc31c5711a460a9c72bfef417aa61` — unchanged L42 lift and harmonic readout.

Frozen evidence-helper and ancestry closure:

- `verification/run_l30_white_chromatic_field.py`: `0b38a76aeb476f4d20c3dbd81e39fe1c6abe105f735574cf5c9b6a1bc08976dc` — canonical device, tensor, and atomic-artifact helpers reused by the runner;
- `verification/verify_l30_white_chromatic_field.py`: `48bddc4b97b77a174de3885ec42886b78e623c19f74c0acab32cf6e607b24405` — canonical JSON, hash, and receipt helpers reused by the verifier;
- `verification/run_l40_rolling_ordered_relational_recall.py`: `490322bb0b11bbf3e3c8f95badd254bf6737b4831abc9cea2d3eac7fe58c1e09` — immutable prefix producer ancestry;
- `verification/verify_l40_rolling_ordered_relational_recall.py`: `756e02f5b33ad88b3d8cf11eb7412ae3003f125d1780a288c573e10288b80202` — immutable prefix verifier ancestry.

New protocol source paths, hashed after implementation but before any canonical field operation:

- `designs/L48-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md`;
- `tests/test_l48_harmonic_write_causal_crossover.py`;
- `verification/run_l48_harmonic_write_causal_crossover.py`;
- `verification/verify_l48_harmonic_write_causal_crossover.py`.

The exact set therefore contains sixteen paths. Missing or additional keys fail mechanically. The preregistration hash is frozen before implementation. The three new executable-source hashes are frozen by the first complete canonical board. The board and NPZ cannot include their own hashes without a cycle; the independent receipt records and verifies their SHA-256 values.

`cassi_exact_cyclic_field.py` is deliberately excluded. L39 does not import or inherit it. The tested solver is `PrismaticFieldController._evolve_unchecked` through the ordered-relational inheritance chain above.

## Immutable prefix evidence

L48 hash-binds and never overwrites:

- L40 board SHA-256 `44a0baff773c85405c35e0d92da405e8157e3617b811da75f6d2f00e88811530`;
- L40 traces SHA-256 `21549f5bd65fd6e10247295bf59b48d6b35ed1b4d1b1a0a857fffafce32f045a`;
- L40 verification SHA-256 `b5fd0f085e876eebd589dc7cf8a6353d20b93e1616c014f13d77c11a8aca8ca7`.

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
- immutable `readout_energy_floor=1e-8` for both ordinary current availability and the L42 age-score threshold.

`age_energies`, defined as mean native energy in each physical harmonic, are stored diagnostics and are reconstructed within tolerance. They are never substituted for public L42 availability and have no separate threshold.

Frozen symbols are:

- `S0 = (0,37,74,111,148,185,222,259)`;
- `S1 = (S0+97) mod 260`;
- `S2 = (S0+181) mod 260`;
- `S3 = S1`.

## Prefix reproduction

The L48 runner must reproduce the unchanged L40 prefix exactly:

1. construct a fresh L39 ordered-relational field;
2. run the unchanged initial heartbeat;
3. run one unchanged S0 tick with trust `1` and eight evolution steps;
4. capture `s0-deposit`;
5. run sixteen unchanged blank ticks, each with eight evolution steps;
6. capture `s0-horizon` and its readout.

The reproduced fields must be byte-identical to both preserved L40 fields and match their frozen SHA-256 values. The reproduced `s0-horizon` readout must include the same unexpected relational availability and symbol in all rows. Any prefix mismatch returns `FAIL` and stops before the causal fork.

No new heartbeat is inserted between reproduced `s0-horizon` and the fork. This preserves `s0-horizon` itself as the canonical pre-write checkpoint and isolates the bare Givens write from heartbeat.

## Native operators and exact write bypass

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

`U` is invoked only through `HarmonicAgeFieldController._lift_harmonics_unchecked` or its validating public wrapper. Neither W branch may call `HarmonicAgeFieldController._modulate_unchecked`, because that override applies `U` before delegating.

Both `W` and `UW` must call one shared local `bare_write` helper. Its only write call is the function object that L39 inherits through the cyclic controller and whose implementation is owned by the white-chromatic source:

```python
WhiteChromaticFieldController._modulate_unchecked(
    ordered_controller,
    state,
    symbols,
    1.0,
)
```

`W` calls `bare_write(s0_horizon, S1)` exactly once. `UW` computes `U(s0_horizon)` exactly once, then calls `bare_write(U_state, S1)` exactly once. No heartbeat, harmonic modulation override, extra bound, evolution, or readout occurs inside either composition.

## Required focused bare-write proof

Before any smoke, the focused CPU float64 test must construct a frozen-style state with `mode_count=520`, batch size eight, the canonical S0 vector, one initial heartbeat, one S0 tick with eight evolution steps, and sixteen blank ticks with eight evolution steps each. From byte-identical clones it must prove:

1. the runner's W helper returns field, drift, and clamp receipt bit-identical to the direct qualified `WhiteChromaticFieldController._modulate_unchecked(ordered_controller, state, S1, 1.0)` call;
2. the runner's UW helper returns field, drift, and clamp receipt bit-identical to the same direct qualified bare write applied to `U(state)`;
3. W and UW fields are not byte-identical on this frozen-style state;
4. `HarmonicAgeFieldController._modulate_unchecked` is never invoked by either helper.

The test may instrument the harmonic override to raise if called. A failed proof blocks smoke and canonical execution.

## Immediate 2x2 fork

Create four byte-identical clones of the reproduced `s0-horizon` field. Record the contiguous tensor SHA-256 for every clone and the SHA-256 of one shared contiguous S1 tensor. Apply:

- branch `I`: identity;
- branch `U`: `U` only;
- branch `W`: `bare_write(S1)` only;
- branch `UW`: `U`, then the identical `bare_write(S1)`.

There is no heartbeat, bound outside the unchanged write, evolution, or readout before immediate native coordinates are captured. `I` and `U` have declared zero write drift and zero clamp count. The runner captures native coordinates before any public readout and captures the field again after both unchanged L39 and L42 readouts.

## Blank-horizon forks

From each immediate post-branch field, run 128 consecutive unchanged no-symbol L39 ticks. No additional `U` is applied because no symbol is written. Capture all four branches at:

- immediate (`0` blank ticks);
- `8` blank ticks;
- `16` blank ticks;
- `128` blank ticks.

The `UW` branch must retain native age-zero/age-one coefficients and the availability-qualified public tuple `[S1,S0]` at all four checkpoints. The other branches are causal controls and have no post-hoc semantic target; all of their continuous coordinates, availability, availability-qualified winners, readouts, bounds, and clamp telemetry are still independently reconstructed.

## Rolling and reversal continuation

From a separate clone of immediate `UW`:

1. run sixteen blank ticks and capture `s1-horizon`;
2. apply one `U` and the unchanged `bare_write(S2)`, capture `s2-deposit`;
3. run sixteen blank ticks, capture `s2-horizon`;
4. apply one `U` and the unchanged `bare_write(S3)`, capture `s3-reversal-deposit`;
5. run sixteen blank ticks, capture `s3-reversal-horizon`.

Include immediate `UW` as `s1-deposit`, yielding six sequence checkpoints. Required availability-qualified age tuples in every row are:

- `s1-deposit` and `s1-horizon`: `[S1,S0]`;
- `s2-deposit` and `s2-horizon`: `[S2,S1]`;
- `s3-reversal-deposit` and `s3-reversal-horizon`: `[S1,S2]`.

At the reversal, S0 must not occupy the predecessor slot. This is the direction-sensitive gate distinguishing ordered recent history from unordered recent-set membership.

After `s1-horizon`, serialize only the native field tensor plus frozen profile/config identities, load it into fresh unchanged ordered and harmonic controllers, and continue through S2 and S3 beside the uninterrupted branch. Resumed and uninterrupted fields and readouts must remain byte-identical after every subsequent event.

## Independent native and availability reconstruction

The verifier must implement native unpacking, DFT, codebook projection, ordinary current availability, harmonic availability, harmonic readout, L39 relational readout, and the Givens write directly in NumPy. It may import only canonical JSON/file/hash helpers, never either field controller, the L48 runner, or controller operator/readout formulas.

For each stored field it reconstructs:

- complex `C`, `D`, `VC`, and `VD` with shape `[7,1024,8]`;
- physical-harmonic `D` and `VD` with shape `[7,1024,8]`, indexed `k=0,...,6`;
- age-ordered harmonic tensors using `(1,2,3,4,5,6,0)`;
- complex codebook coefficients with shape `[8,7,260]`;
- age scores, diagnostic energies, symbols, and availability with shapes `[8,7,260]`, `[8,7]`, `[8,7]`, and `[8,7]`;
- the availability-qualified current/predecessor tuple `[8,2]`, using `-1` for an unavailable slot;
- unchanged L39 current, relational, and ordered scores and categorical availability.

The complex codebook coefficient is frozen as

\[
c_{bks}=\frac1{1024}\sum_m \overline{u_{sm}}z^D_{kmb},
\]

with `age_scores=|c|^2`. The exact unchanged ordinary availability is:

\[
\operatorname{ordinary\_available}_b=
\left(\operatorname{mean}_{j,m}|D_{jmb}|^2\ge 10^{-8}\right)
\land
\left(\sum_j [\sqrt{\operatorname{mean}_m|D_{jmb}|^2}\ge10^{-8}]\ge2\right).
\]

For age slot `a`, the exact unchanged L42 rule is:

\[
\operatorname{age\_available}_{ba}=
\operatorname{ordinary\_available}_b
\land
\left(\max_s \operatorname{age\_scores}_{bas}\ge10^{-8}\right).
\]

Diagnostic mean native harmonic energy is not part of either availability expression.

Availability arrays must match reconstruction exactly. Age-symbol equality is required exactly only where both the recorded and independently reconstructed availability bits are true. An unavailable argmax remains a stored diagnostic, is never placed in an availability-qualified tuple, and may differ from NumPy reconstruction without failing a mechanical or semantic gate. Current/predecessor tuples and every availability-qualified winner remain exact.

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
- `branch_age_energies`: `[4,4,8,7]`, float32 diagnostic values;
- `branch_age_symbols`: `[4,4,8,7]`, int64 diagnostic argmax values when unavailable;
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
- `sequence_age_energies`: `[6,8,7]`, float32 diagnostic values;
- `sequence_age_symbols`: `[6,8,7]`, int64 diagnostic argmax values when unavailable;
- `sequence_age_available`: `[6,8,7]`, bool;
- `sequence_current_predecessor`: `[6,8,2]`, int64;
- `sequence_ordered_current_symbols`, `sequence_ordered_relational_symbols`: `[6,8]`, int64;
- `sequence_ordered_current_available`, `sequence_ordered_relational_available`: `[6,8]`, bool;
- `sequence_ordered_scores`: `[6,8,260]`, float32;
- `sequence_clamp_counts`: `[51]`, int64, containing initial UW, forty-eight blanks, S2, and S3 writes;
- `sequence_input_energy_drift`: `[51,8]`, float32;
- `resume_uninterrupted_sha256`, `resume_reloaded_sha256`: `[34]` fixed-length Unicode, one pair after each post-reload event.

Every required array is stored even when a branch has no semantic target. Additional arrays are prohibited because they would create an unfrozen evidence surface. Source hashes live only in the board's exact `source_sha256` object.

## Frozen tolerances

Focused CPU float64 controls use zero relative tolerance and absolute tolerance `2e-12` for native coordinate, DFT, codebook coefficient, energy, and write reconstruction. Exact identity, untouched coordinates, readout immutability, qualified-call proof, and save/reload checks remain bitwise.

Canonical float32 checks use:

- native `C,D,VC,VD`, physical harmonics, codebook coefficients, DFT relocation, and dynamic energy: `atol=3e-6`, `rtol=3e-6`;
- current, relational, ordered, and harmonic scores: `atol=3e-5`, `rtol=2e-4`;
- maximum Givens input-energy drift: `2e-6`;
- maximum active component amplitude: `8`;
- epsilon range: `[0,4096]`;
- inactive coordinates: exact zero;
- clamp count: exact zero;
- availability, availability-qualified symbols and tuples, order, clone hashes, and save/reload hashes: exact.

Unavailable age-symbol argmax diagnostics have no equality tolerance because they are not compared. These values and rules are frozen before implementation and may not be widened after any focused test, smoke, or canonical result.

## Mechanical gates

The independent verifier requires:

1. exact preregistration, exact sixteen-path source key set and hashes, L40 input hashes, board hash, trace hash, and schema identities;
2. exact L48 raw array set, shape, dtype, order, and finiteness;
3. canonical float32 execution on `AMD Radeon RX 7900 XTX` with recorded PyTorch, HIP, and device versions;
4. exact prefix reproduction, including both frozen field hashes and contaminated `s0-horizon` readout;
5. four byte-identical fork fields and one identical S1 symbol tensor;
6. branch `I` byte-identical before and after identity and both readouts;
7. branch `U` changes only `D` and `VD`, relocates every physical harmonic `k` to `(k+1) mod 7`, and conserves their norm within tolerance;
8. focused proof and canonical reconstruction both establish that W is the direct inherited bare write, UW is `bare_write(U(state))`, W differs from UW on the frozen-style state, and neither invokes the harmonic modulation override;
9. runner-stored native harmonics, coefficients, scores, diagnostic energies, availability, availability-qualified symbols and tuples, and both public readouts match independent reconstruction under the frozen comparison rules;
10. neither public readout mutates any field;
11. every active coordinate remains within `8`, every epsilon value within `[0,4096]`, every inactive coordinate exactly zero, and every input-energy drift within `2e-6`;
12. every prefix, branch, horizon, sequence, and resume clamp count is zero;
13. save/reload continuation remains byte-identical to uninterrupted execution after every event;
14. focused verifier mutations reject a changed source key/hash, prefix hash, clone, S1 symbol vector, native harmonic, availability bit, available winner, clamp, inactive tail, or resume hash;
15. a unit-level comparator control accepts a changed runner-stored age symbol only at a slot where recorded and reconstructed availability are both false, while full-file trace hash integrity remains enforced.

Any failed mechanical gate returns `FAIL` and stops functional interpretation.

## Functional and causal gates

Every semantic gate is exact in all eight rows and is evaluated only on available slots.

Immediate `UW` must have:

- S1 available and selected at age zero/physical harmonic one;
- S0 available and selected at age one/physical harmonic two;
- availability-qualified tuple `[S1,S0]`;
- zero clamps.

No age-separation claim is made for `W`. The controls instead establish attribution:

- if `U` fails native relocation, classify `AGE_ROTATION_FAILURE`;
- if `W` fails independent inherited-write reconstruction, classify `WRITE_GEOMETRY_FAILURE`;
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

`SUPPORTS` establishes only that existing `U_age` causally provides four-write ordered separation through the tested horizons. It does not establish bounded retirement and does not authorize L47 execution without the separate Brain–Mind raw-array review.

After CassiMind approves this exact preregistration hash, implement the focused tests, runner, and verifier without changing any frozen field source. Run the focused CPU contracts and verifier-mutation tests, then one disposable CPU smoke. Delete smoke outputs. Run exactly one canonical RX 7900 XTX board and one source-independent verifier. Preserve the first complete board and receipt. Stop after the first complete verdict.

Any change to the prefix, fork checkpoint, symbols, operators, exact bare-write function, branch ordering, arrays, horizons, sequence, persistence boundary, availability rules, comparison masks, gates, tolerances, source dependencies, or stopping rule requires a new preregistration and evidence identity.