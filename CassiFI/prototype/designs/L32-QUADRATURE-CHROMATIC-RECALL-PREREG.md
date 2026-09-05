# L32 Quadrature Chromatic Recall — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L32 is frozen after the complete canonical L31 `REJECT` and before any L32 module, test, runner, verifier, smoke, or canonical execution. L30 and L31 source files and artifacts remain immutable. L32 is a separately named side-by-side readout profile.

## Measured motivation and question

L31 passed every frozen mechanical condition and every functional condition except original-target long-horizon MRR:

- measured L31 value: `0.02615025059625695`;
- required value: `0.05`.

L31 reads symbol evidence from differential position `D` while its oscillator evolves both `D` and differential velocity `VD`. Its recorded distractor ranks were strong at ticks 16 and 64 but weak at tick 32. L32 tests one hypothesis only: earlier symbol evidence remains accessible when the fixed readout measures both normalized phase-space quadratures instead of position alone.

Question: with L31 state, heartbeat, deposit, cyclic coupling, evolution, energy accounting, projection, constants, schedules, and gates unchanged, does a fixed quadrature-aware readout satisfy every inherited condition?

## Identities and files

Unchanged identities:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New identities:

- operator/readout: `cassi.qi-quadrature-chromatic-recall.v1`;
- trace schema: `cassi.l32.quadrature-chromatic-traces.v1`;
- board schema: `cassi.l32.quadrature-chromatic-board.v1`;
- verifier schema: `cassi.l32.quadrature-chromatic-verification.v1`.

New files:

- `cassi_quadrature_chromatic_field.py`;
- `tests/test_cassi_quadrature_chromatic_field.py`;
- `verification/run_l32_quadrature_chromatic_field.py`;
- `verification/verify_l32_quadrature_chromatic_field.py`.

L32 may import frozen L30/L31 modules and evidence helpers. Its board binds SHA-256 values for every directly executed source named by its runner and verifier. It must not modify or overwrite any L30/L31 source or artifact.

## Sole changed mechanism: phase-space readout

The sole adaptive state remains the L31 `QiFieldState.field` tensor with shape `[7, 9*M, B]` and native active planes:

`C_re, C_im, D_re, D_im, VC_re, VC_im, VD_re, VD_im, epsilon2_ema`.

No update equation, deposit equation, state plane, bound, energy equation, oscillator coefficient, coupling coefficient, codebook, or projection equation changes.

For the first cyclic color harmonic, define the fixed per-mode effective angular frequency

\[
\Omega_m = \sqrt{\omega_m^2 + 4\kappa_m\sin^2(\pi/7)}.
\]

For candidate symbol `a`, channel `s`, and batch item `b`, independently compute the two matched coefficients

\[
A^{D}_{sab}=\frac{1}{W}\sum_m u_{am}^{*}D_{smb},
\qquad
A^{V}_{sab}=\frac{1}{W}\sum_m u_{am}^{*}\frac{VD_{smb}}{\Omega_m}.
\]

Apply the unchanged fixed channel-phase compensation `h_s*` to each coefficient and form global coefficients by summing channels with the unchanged `1/sqrt(7)` normalization. The only new symbol score is the noncoherent quadrature sum

\[
S_{ab}=|A^{D}_{ab}|^2+|A^{V}_{ab}|^2.
\]

Per-channel scores use the same sum before channel aggregation. Phase-space RMS, availability, active-channel count, and winning white coherence use `|D|^2 + |VD/Omega|^2`. No learned or fitted weight, temporal band, time counter, history buffer, adaptive threshold, protected lane, altered projection, or exact integrator is allowed in L32.

The trace adds raw `task_read_normalized_vd` and `pre_read_normalized_vd` arrays so the verifier can independently reconstruct all L32 readout quantities. These arrays are evidence only and are not persistent adaptive state.

## Frozen board and gates

Canonical hardware, dtype, dimensions, symbols, distractors, read ticks, tick count, evolution steps, blank/stress schedules, projection side, provenance rules, and tolerances are inherited verbatim from L31:

- CUDA/ROCm float32 on the RX 7900 XTX selected with `CUDA_VISIBLE_DEVICES=1`;
- 7 channels, 2048 modes, 1024 active modes, alphabet 260, batch 8;
- targets `(0, 37, 74, 111, 148, 185, 222, 259)`;
- distractors `(target + 97) % 260`;
- reads `(0, 1, 2, 4, 8, 16, 32, 64)`;
- 8 evolution steps per tick;
- 128-tick blank and cyclic-input stress paths.

All inherited mechanical `FAIL` gates remain unchanged, including exact independent recomputation, source hashes, inactive zeros, finite values, no clamps/rescales, energy bounds, input-energy drift, readout/projection immutability, deterministic bounded projection, and projection counterfactual separation.

With mechanics green, return `ADOPT` only when every inherited functional condition holds:

1. exact pre-evolution target accuracy `1.0`;
2. tick-0 target accuracy `>= 0.875`;
3. mean target MRR at ticks 1, 2, and 4 `>= 0.75`;
4. tick-8 distractor accuracy `>= 0.75`;
5. mean distractor MRR at ticks 16, 32, and 64 `>= 0.25`;
6. mean original-target MRR at ticks 16, 32, and 64 `>= 0.05`;
7. tick-0 winning white coherence `>= 0.90`;
8. blank path `max abs(D) <= 1e-6`;
9. stress path finite, clamp-free, and within the energy gate.

Return `REJECT` when mechanics pass and any functional condition fails. Return `FAIL` on evidence or mechanical failure and `INCOMPLETE` only when canonical hardware is unavailable or interrupted before a complete board exists.

## Artifacts

Raw:

- `_diag/l32-quadrature-chromatic-field/l32-board.json`;
- `_diag/l32-quadrature-chromatic-field/l32-traces.npz`;
- `_diag/l32-quadrature-chromatic-field/l32-projection.png`.

Verification:

- `artifacts/l32-quadrature-chromatic-field/L32-QUADRATURE-CHROMATIC-RECALL-REPORT.md`;
- `artifacts/l32-quadrature-chromatic-field/l32-verification.json`.

Writes are finite canonical JSON or `allow_pickle=False` NPZ, use temporary siblings plus atomic replacement, and reference raw siblings by basename only.

## Stopping rule

Small CPU implementation checks may repeat only until the frozen equations and evidence plumbing conform; they are not evidence and may not tune any coefficient, gate, schedule, or mechanism. Then run one canonical RX 7900 XTX float32 board and one independent verifier. An infrastructure abort may retry only after repair with byte-identical bound sources. Preserve the first complete canonical `ADOPT`, `REJECT`, or `FAIL`; any L32 operator change after that requires a new profile and preregistration.

After preserving the complete L32 result, this stopping rule permits the separately preregistered L33 protected-memory experiment requested by the owner. L33 must start from frozen L31 rather than alter or tune L32, and its mechanism must remain independent of the L32 result.
