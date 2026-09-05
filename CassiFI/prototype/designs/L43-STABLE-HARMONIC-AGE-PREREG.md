# L43 Stable Harmonic Age — Preregistration

## Status: frozen before implementation or runs

L42 established a useful raw capacity result but did not produce a valid canonical functional verdict. Its completed GPU board reported exact four-deposit ordering, while its independent verifier stopped on a full-score representation mismatch: small cross-device differences in low-energy harmonic coefficients were magnified when every harmonic was normalized, including harmonics below the availability threshold. The same raw board separately reported clamps in the inherited stress arm. L42 source and evidence remain immutable.

L43 changes one mechanism only: the harmonic readout uses a dtype-derived numerical availability floor and excludes unavailable harmonics from normalized remainder aggregation. The L42 state, unitary lift, deposits, dynamics, solver, channel harmonics, codebook, projection, schedules, and constants remain unchanged. This experiment asks whether precision-grounded availability masking yields independently reconstructible scores without weakening any inherited physical gate.

## Frozen identities

- Layout profile: `cassi.qi-cyclic-chromatic-coordinate-native.v1`
- Operator profile: `cassi.qi-stable-harmonic-age-ladder.v1`
- Projection profile: `cassi.qi-cyclic-chromatic-projection.v1`
- Channels: seven
- Active width: 1024 complex modes per channel
- Alphabet: 260 symbols
- State shape: `[7, 9 * 2048, B]`
- Age harmonics, newest to oldest: `(1, 2, 3, 4, 5, 6, 0)`
- New module: `cassi_stable_harmonic_field.py`
- New focused controls: `tests/test_cassi_stable_harmonic_field.py`
- New runner: `verification/run_l43_stable_harmonic_field.py`
- New verifier: `verification/verify_l43_stable_harmonic_field.py`

## Frozen readout refinement

Let $s_{b,a,k}$ be the unchanged L42 squared codebook coefficient for batch row $b$, age slot $a$, and symbol $k$. Let

$$
m_{b,a}=\max_k s_{b,a,k},\qquad M_b=\max_a m_{b,a}.
$$

For the real state dtype with machine epsilon $\epsilon_{\mathrm{dtype}}$, define the row-local numerical floor

$$
f_b=\max\left(10^{-8},\;128\,\epsilon_{\mathrm{dtype}}\,M_b\right).
$$

Age slot $a$ is available exactly when the inherited current readout is available and $m_{b,a}\ge f_b$. The normalized remainder is

$$
r_{b,k}=\max_{a\;\mathrm{available}}\frac{s_{b,a,k}}{\max(m_{b,a},f_b)},
$$

with an exact zero contribution from every unavailable age. If no inherited readout is available, the ordinary 260-score row remains the inherited exact-zero row.

The categorical ordinal slots are unchanged and overwrite the normalized remainder from oldest to newest:

- age 0: score 8,
- age 1: score 7,
- age 2: score 6,
- age 3: score 5,
- age 4: score 4,
- age 5: score 3,
- age 6: score 2.

Newer duplicates therefore win. The emitted symbol remains the available age-0 winner. Allowed-symbol restrictions govern every age winner exactly as in L42.

The multiplier 128 is frozen as a conservative roundoff envelope, not fitted to a task score. It scales with dtype and row energy, leaves finite strong harmonics untouched, and makes unavailable numerical residue contribute exactly zero.

## Explicit non-changes

L43 does not change:

- L42 harmonic lifting of `D` and `VD`,
- the L31 Givens deposit,
- heartbeat behavior,
- the cyclic Hamiltonian or exact solver,
- field bounds or clamp thresholds,
- energy budgets,
- evolution steps,
- source trust,
- the shared codebook,
- canonical target or distractor schedules,
- projection geometry,
- the production L39 profile,
- any L42 source, receipt, raw trace, report, or verdict status.

There is no history table, counter, clock, shift register, learned embedding, optimizer, or auxiliary memory state.

## Focused controls before evidence

The focused CPU controls must establish:

1. L43 modulation and no-symbol evolution are bit-identical to L42.
2. Blank state remains exact zero and exposes no auxiliary state.
3. Strong synthetic harmonics remain available in float32 and float64.
4. Synthetic harmonics below the dtype-derived floor are unavailable and contribute exact-zero remainder scores.
5. Every public readout field matches a direct standalone reconstruction of the frozen equations.
6. One through four mode-2048 deposits emit the newest symbol and expose exact reverse age order.
7. Allowed-symbol restrictions govern every available age winner.
8. The L43 configuration fingerprint is distinct while layout and projection identities remain unchanged.

A failed functional control is retained as a strict expected failure only after confirming source conformance. Evidence plumbing may be repaired before the canonical run; mechanism constants and equations may not.

## Canonical board

Use the unchanged L30/L31 inherited schedules on one float32 `cuda`/ROCm run with:

- batch size 8,
- mode count 2048,
- 8 evolution steps per tick,
- target symbols `(11, 43, 79, 127, 163, 197, 229, 251)`,
- distractors `(29, 61, 97, 139, 181, 211, 241, 7)`,
- the inherited blank, first-heartbeat, projection, task, pre-distractor, and 128-deposit stress arms.

The four-deposit arm remains frozen row-wise as

$$
(T_i,D_i,T_{i+1},D_{i+1}),
$$

with cyclic indexing, one ordinary 8-step tick per deposit, followed by eight ordinary no-symbol ticks.

Raw outputs:

- `_diag/l43-stable-harmonic-field/l43-board.json`
- `_diag/l43-stable-harmonic-field/l43-traces.npz`
- `_diag/l43-stable-harmonic-field/l43-projection.png`

Frozen verification outputs:

- `artifacts/l43-stable-harmonic-field/L43-STABLE-HARMONIC-FIELD-REPORT.md`
- `artifacts/l43-stable-harmonic-field/l43-verification.json`

The runner must hash-bind this preregistration, L30/L31/L42 dependencies, the new L43 module, runner, and verifier. The verifier must independently reconstruct the codebook, channel DFT, dtype floor, age availability, masked normalization, ordinal aggregation, ranks, energies, drifts, clamps, inactive modes, artifact hashes, and source hashes without importing the L43 module.

## Frozen gates

The first nine functional conditions are inherited unchanged:

1. exact pre-target accuracy is 1.0,
2. tick-0 target accuracy is at least 0.875,
3. pre-distractor target MRR is at least 0.75,
4. tick-8 distractor accuracy is at least 0.75,
5. long-horizon distractor MRR is at least 0.25,
6. long-horizon original-target MRR is at least 0.05,
7. tick-0 white coherence is at least 0.90,
8. blank maximum differential magnitude is at most $10^{-6}$,
9. the stress path is clamp-free and total mean dynamic energy never exceeds 1.05.

The four L43 conditions are:

10. immediate emitted-symbol accuracy is 32/32,
11. after deposit four, every row's top four symbols exactly equal its deposited sequence in reverse order,
12. after eight no-symbol ticks, every row's top four symbols still exactly equal that reverse sequence,
13. exactly the four occupied age slots are available after deposit four and after the blank horizon, all unavailable ages contribute exact-zero normalized remainder, every full aggregate score independently reconstructs within absolute tolerance $3\times10^{-5}$ and relative tolerance $2\times10^{-4}$, all values are finite, and the four-deposit arm is clamp-free.

Mechanical integrity also requires exact schema/source/artifact hashes, unchanged inactive modes, independent codebook agreement, first-heartbeat carrier-only behavior, maximum absolute input-energy drift at most $5\times10^{-5}$, total mean dynamic energy at most 1.05, and no verifier use of L43 controller/readout code.

## Decision and stopping rule

- `ADOPT` only if every mechanical check and all 13 functional conditions pass.
- `REJECT` if evidence mechanics pass but one or more functional conditions fail.
- `FAIL` for an integrity, schema, source-binding, nonfinite, reconstruction, or other mechanical failure.
- `INCOMPLETE` if the canonical board does not complete.

Run focused controls, one disposable CPU evidence smoke, then exactly one canonical GPU board and one independent verification. Delete smoke artifacts before the canonical run. Freeze the first complete canonical evidence and verdict; do not tune or rerun this profile. A stress failure remains a failure—this readout-only experiment does not alter the L42 operator to evade it.
