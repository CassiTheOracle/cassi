# L31 Cyclic Chromatic Field — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L31 is frozen after the canonical L30 `REJECT` and before any L31 module, test, runner, verifier, smoke, or canonical execution. L30 remains immutable. L31 is a separately named side-by-side operator and checkpoint-incompatible layout.

## Motivation and question

Canonical L30 passed immediate refraction, energy accounting, stability, recency, coherence, projection, and stress conditions, but returned `REJECT` because:

- 128-tick blank differential leakage was `2.9802322387695312e-06` against `1e-6`;
- original-target long-horizon MRR was `0.02611927139444087` against `0.05`.

L31 tests one combined engineering hypothesis without attributing separate causal effects:

1. Store the already-used common/differential coordinates directly so a mathematically zero differential field remains exactly zero in float32 instead of repeatedly cancelling reconstructed Yang/Yin values.
2. Couple the seven colors as a reciprocal cycle. The fixed chromatic phase vector `exp(2*pi*i*s/7)` is then an eigenvector of the coupling Laplacian, so circulation does not shear the phase relationship required by coherent readout.

Question: with all other L30 equations, constants, schedules, and gates held fixed, does native common/differential storage plus cyclic color coupling satisfy every frozen mechanical and functional condition?

## Separate identities and files

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- operator: `cassi.qi-cyclic-chromatic-heartbeat.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`;
- trace schema: `cassi.l31.cyclic-chromatic-traces.v1`;
- board schema: `cassi.l31.cyclic-chromatic-board.v1`;
- verifier schema: `cassi.l31.cyclic-chromatic-verification.v1`.

New files:

- `cassi_cyclic_chromatic_field.py`;
- `tests/test_cassi_cyclic_chromatic_field.py`;
- `verification/run_l31_cyclic_chromatic_field.py`;
- `verification/verify_l31_cyclic_chromatic_field.py`.

L31 may import the frozen L30 operator, runner, and verifier as implementation/evidence helpers. The L31 board must bind SHA-256 values for every executed source: both L30 helpers, the L30 base module, the L31 module/runner/verifier, and this preregistration. It must not change L30 source or artifacts.

## Sole adaptive state and native coordinates

The sole adaptive state remains one `QiFieldState.field` tensor with shape `[7, 9*M, B]`. Only modes `[0, M/2)` are active. L31 stores these planes directly:

`C_re, C_im, D_re, D_im, VC_re, VC_im, VD_re, VD_im, epsilon2_ema`.

No extra tensor, learned codec, cache, model, policy, optimizer, or adaptive projection is allowed. State validation, inactive-mode zeroing, and the immutable L30 codebook contract remain unchanged.

Per-channel dynamic energy is

\[
E_s=\frac{1}{1+\phi^2}\operatorname{mean}_m
\left(|C_s|^2+|D_s|^2+|V_{C,s}|^2+|V_{D,s}|^2\right),
\]

and total energy is `mean_s(E_s)`. Component bounds apply directly to stored coordinates; aggregate safety scaling uses `E_s`.

Heartbeat, chromatic unitary modulation, codebook, shared mode timescales, oscillator coefficients, epsilon update, coherent readout, energy budget, projection equations/RGB values, and tick order are exactly those frozen in `designs/L30-WHITE-CHROMATIC-FIELD-PREREG.md`.

## Cyclic coupling

Replace only the no-flux path coupling with the seven-edge periodic Laplacian:

\[
F_s=\kappa_m\left(Z_{s-1}+Z_{s+1}-2Z_s\right),
\]

with channel indices modulo 7. Apply the same force independently to `C` and `D`. The per-mode weight remains

\[
\kappa_m=0.05/\tau_m^2.
\]

The force sums to zero, the white vector has zero force, and the fixed first chromatic Fourier mode is an eigenvector. No direction-specific or candidate-specific coupling is permitted.

## Frozen board and gates

Canonical hardware, dtype, dimensions, symbols, distractors, read ticks, tick count, evolution steps, blank/stress schedules, projection side, raw arrays, provenance rules, tolerances, and stopping rule are inherited verbatim from L30:

- CUDA/ROCm float32 on the RX 7900 XTX selected with `CUDA_VISIBLE_DEVICES=1`;
- 7 channels, 2048 modes, 1024 active modes, alphabet 260, batch 8;
- targets `(0, 37, 74, 111, 148, 185, 222, 259)`;
- distractors `(target + 97) % 260`;
- reads `(0, 1, 2, 4, 8, 16, 32, 64)`;
- 8 evolution steps per tick;
- 128-tick blank and cyclic-input stress paths.

Mechanical `FAIL` gates are inherited exactly, including:

- first heartbeat carrier and total energy targets;
- equal channel energies;
- first heartbeat and blank `max abs(D) <= 1e-6`;
- input energy drift `<= 5e-5`;
- no nonfinite values, inactive changes, component clamps, or aggregate safety rescales;
- maximum total mean energy `<= 1.05`;
- readout/projection immutability;
- deterministic bounded projection, RGB standard deviation `>= 1e-4`, and counterfactual image RMS difference `> 1e-4`;
- complete independent recomputation and provenance.

With mechanics green, return `ADOPT` only when all inherited functional conditions hold:

1. exact pre-evolution target accuracy `1.0`;
2. tick-0 target accuracy `>= 0.875`;
3. mean target MRR at ticks 1, 2, and 4 `>= 0.75`;
4. tick-8 distractor accuracy `>= 0.75`;
5. mean distractor MRR at ticks 16, 32, and 64 `>= 0.25`;
6. mean original-target MRR at ticks 16, 32, and 64 `>= 0.05`;
7. tick-0 winning white coherence `>= 0.90`;
8. blank path `max abs(D) <= 1e-6`;
9. stress path finite, clamp-free, and within the energy gate.

Return `REJECT` when mechanics pass and any functional condition fails. Return `FAIL` on mechanical/evidence failure and `INCOMPLETE` only for unavailable/interrupted canonical hardware before a complete board exists.

## Artifacts

Raw:

- `_diag/l31-cyclic-chromatic-field/l31-board.json`;
- `_diag/l31-cyclic-chromatic-field/l31-traces.npz`;
- `_diag/l31-cyclic-chromatic-field/l31-projection.png`.

Verification:

- `artifacts/l31-cyclic-chromatic-field/L31-CYCLIC-CHROMATIC-FIELD-REPORT.md`;
- `artifacts/l31-cyclic-chromatic-field/l31-verification.json`.

Writes are finite canonical JSON or `allow_pickle=False` NPZ, use temporary siblings plus atomic replacement, and reference raw siblings by basename only.

## Stopping rule

Small CPU float64 implementation checks may repeat until L31 conforms to the frozen equations; they are not evidence and cannot tune constants, schedules, gates, or topology. After focused checks pass, run one canonical RX 7900 XTX float32 board and one independent verifier. An infrastructure abort may retry only after repair with byte-identical bound sources. Preserve the first complete canonical `ADOPT`, `REJECT`, or `FAIL`. Any operator change after it requires L32 and a new preregistration.
