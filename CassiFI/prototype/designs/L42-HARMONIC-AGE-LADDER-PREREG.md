# L42 Harmonic Age Ladder — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L42 is frozen after preserving the L41 solver-audit `PASS` and before any L42 module, test, runner, verifier, smoke, or canonical execution. L41 established that malformed numerical evolution does not explain the multi-deposit capacity limit. L42 therefore leaves every solver equation and L30–L41 source/artifact immutable and tests one field-local modulation/readout mechanism.

## Question

Can the seven physical chromatic channels act as a unitary age axis, routing each deposit into a distinct cyclic harmonic so the same field exposes more than two ordered symbols without a time counter, external history, learned decoder, protected lane, or auxiliary adaptive state?

## Identities and files

Unchanged layout and projection:

- `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- `cassi.qi-cyclic-chromatic-projection.v1`.

New operator/readout identity: `cassi.qi-harmonic-age-ladder.v1`.

Evidence identities:

- board: `cassi.l42.harmonic-age-ladder-board.v1`;
- traces: `cassi.l42.harmonic-age-ladder-traces.v1`;
- verification: `cassi.l42.harmonic-age-ladder-verification.v1`.

New files:

- `cassi_harmonic_age_field.py`;
- `tests/test_cassi_harmonic_age_field.py`;
- `verification/run_l42_harmonic_age_field.py`;
- `verification/verify_l42_harmonic_age_field.py`.

## Sole changed mechanism: unitary harmonic age routing

The adaptive state remains the L31 tensor `[7,9M,B]`. Heartbeat, codebook, Givens symbol deposit, cyclic evolution, damping, nonlinearity, epsilon update, bounds, energy accounting, projection, and physical constants are unchanged.

Let

\[
p_j=\exp(2\pi i j/7),\qquad j=0,\ldots,6.
\]

Immediately before every actual symbol modulation, multiply only the chromatic position and velocity by this fixed unitary channel phase:

\[
D_j\leftarrow p_jD_j,\qquad VD_j\leftarrow p_jVD_j.
\]

`C` and `VC` are unchanged. Multiplication by `p` shifts every seven-point channel-DFT harmonic `h` to `(h+1) mod 7`, preserves pointwise magnitude and the declared dynamic-energy norm, and becomes the identity after seven applications. The unchanged L31 deposit then writes the new symbol into harmonic `h=1`. Consequently age `a` is read from

\[
h_a=(a+1)\bmod 7,\qquad a=0,\ldots,6,
\]

where age zero is the newest symbol. No shift occurs when no symbol is modulated. The shift count exists only in the field's harmonic occupancy; no Python counter or retained history is permitted.

For each age harmonic, collapse

\[
D^{(a)}=\frac1{\sqrt7}\sum_{j=0}^{6}p_j^{-h_a}D_j
\]

and compute the unchanged codebook coefficient and score

\[
A_a(s)=\frac1M\sum_m\overline{u_s(m)}D^{(a)}_m,
\qquad S_a(s)=|A_a(s)|^2.
\]

Age `a` is available only when the unchanged L31 readout is available and `max_s S_a(s) >= readout_energy_floor`. Its winner respects the caller's allowed-symbol set.

For the ordinary 260-way score surface, normalize every age score by `max(max_s S_a(s), readout_energy_floor)` and take the maximum normalized remainder in `[0,1]`. Apply fixed categorical slots from oldest to newest so newer duplicates win:

- age 6 through age 0 receive ordinal scores `2,3,4,5,6,7,8` respectively when available;
- the emitted symbol is the age-0 winner;
- unavailable rows retain the unchanged L31 score, preserving exact blank zero.

The readout additionally exposes `age_scores[B,7,A]`, `age_symbols[B,7]`, `age_available[B,7]`, and the fixed harmonic indices `(1,2,3,4,5,6,0)`. The ordinal values are labels, not fitted weights.

## Focused controls

Before canonical execution, CPU tests must establish:

1. one harmonic lift equals direct multiplication by `p`, preserves shape and finite values, and changes no nonchromatic plane;
2. seven lifts return `D,VD` to their initial value within `2e-12` in float64 and preserve dynamic energy within `2e-12`;
3. a synthetic pure harmonic moves from `h` to `(h+1) mod 7`, with off-slot DFT leakage below `2e-12`;
4. no-symbol evolution remains bit-identical to L31 and does not perform a lift;
5. direct recomputation of all seven collapses, coefficients, availability flags, winners, and ordinal aggregate equals the returned readout;
6. one through four distinct deposits occupy the expected age slots and emit the newest symbol;
7. allowed-symbol restrictions govern every age winner;
8. blank state remains unavailable with exactly zero scores and no adaptive counter/history exists.

Tests may repair conformance only. They may not change shift phase, age-to-harmonic mapping, availability threshold, ordinal labels, field constants, schedule, or gates.

## Frozen canonical board

The inherited canonical L31/L39 board remains fixed: RX 7900 XTX, float32, `mode_count=2048`, batch size eight, frozen targets/distractors, eight evolution steps per tick, pre-target/target/distractor read schedule, 128-tick blank and stress arms, projection, atomic evidence, and the same nine functional conditions. L42 must retain exact current top-1 behavior while ranking the preceding target above the `0.05` long-horizon MRR floor.

A new four-deposit arm uses, for row `i=0..7`, the frozen sequence

\[
(target_i,\ distractor_i,\ target_{(i+1)\bmod8},\ distractor_{(i+1)\bmod8}).
\]

Each deposit is one ordinary eight-step tick. The arm records all seven age scores/symbols/availability flags after every deposit, then records them again after eight additional no-symbol ticks. Frozen functional conditions are:

10. immediate emitted-symbol accuracy across all 32 deposits equals `1.0`;
11. after the fourth deposit, reverse-sequence top-four accuracy equals `1.0`;
12. after eight no-symbol ticks, reverse-sequence top-four accuracy remains `1.0`;
13. all four occupied age slots are available, unused age slots remain below the availability floor, values are finite, and the arm is clamp-free.

Return `ADOPT` only when evidence mechanics and all thirteen conditions pass. Return `REJECT` when mechanics pass but any functional condition fails, `FAIL` for integrity/mechanical failure, and `INCOMPLETE` only for interrupted or unavailable canonical evidence.

## Independent evidence and stopping rule

The verifier independently reconstructs the unitary phase, harmonic DFT collapses, codebook scores, availability, ordinal aggregation, four-deposit histories, ranks, and inherited gates from raw state/readout traces. It validates source hashes, schemas, array shapes, finite values, device, dtype, energy, drift, clamps, and artifact hashes without importing L42 math.

Raw:

- `_diag/l42-harmonic-age-ladder/l42-board.json`;
- `_diag/l42-harmonic-age-ladder/l42-traces.npz`;
- `_diag/l42-harmonic-age-ladder/l42-projection.png`.

Verification:

- `artifacts/l42-harmonic-age-ladder/L42-HARMONIC-AGE-LADDER-REPORT.md`;
- `artifacts/l42-harmonic-age-ladder/l42-verification.json`.

Run focused CPU controls, one small CPU evidence smoke, one canonical GPU board, and one independent verifier. Preserve the first complete verdict. Any change to the lift, write/read dual, dynamics, or thresholds requires a new profile and preregistration.
