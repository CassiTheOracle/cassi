# L35 Held-Out Chromatic Capacity — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L35 is frozen after preserving the complete L34 `REJECT` and before any L35 runner, verifier, smoke, or canonical execution. It is an evidence-only probe over the immutable L31 cyclic, L32 quadrature-readout, and L34 exact-dynamics profiles. It does not change, select, combine, or tune a field mechanism.

## Question

What history-conditioned sequence capacity is observably present at the existing field readout when the frozen profiles receive symbols excluded from the L30–L34 canonical target/distractor board?

L35 measures simultaneous old/new symbol readability and whether two histories with the same final symbol remain distinguishable at the output. Field-state difference without readout-visible consequence is not counted as usable sequence capacity.

## Bound profiles and identities

The three arms are fixed and ordered:

1. `l31-cyclic` — `CyclicChromaticFieldController`;
2. `l32-quadrature` — `QuadratureChromaticFieldController`;
3. `l34-exact` — `ExactCyclicFieldController`.

Each uses `mode_count=2048`, float32, batch size 16, the shared 260-symbol codebook, seven channels, trust 1.0, and eight evolution steps per ordinary `tick`. Each depth starts from a new zero state. No checkpoint, learned table, replay, external memory, parameter fitting, profile ranking, or cross-arm state transfer is allowed.

Evidence identities:

- board: `cassi.l35.heldout-chromatic-capacity-board.v1`;
- traces: `cassi.l35.heldout-chromatic-capacity-traces.v1`;
- verification: `cassi.l35.heldout-chromatic-capacity-verification.v1`.

## Frozen held-out histories

Depths are `(1, 2, 4, 8, 16)`. Every depth has 16 histories arranged as eight adjacent pairs. The two histories in each pair have different prefixes and the same final symbol.

The eligible pool is `0..259` excluding the sixteen L30 target/distractor symbols:

`0, 22, 37, 59, 74, 96, 97, 111, 134, 148, 171, 185, 208, 222, 245, 259`.

Symbols are generated only from the eligible pool by SHA-256 domain `cassi-l35-heldout-sequence-capacity.v1`. Prefix draws hash `(depth, history, position, attempt)`; the shared final draw hashes `(depth, pair, final, attempt)`. The first pool index not already used inside that history is accepted. The verifier independently regenerates the complete integer tensor and rejects any mismatch, repeat inside a history, exposed-board symbol, unequal paired tail, or equal paired prefix.

For each history, one ordinary field tick admits each symbol in order. The full 260-way score vector is retained after every tick. The final state is not persisted as runtime memory; bounded traces are evidence only.

## Frozen measurements

For every profile and depth, independently recompute:

1. immediate top-1 accuracy over all admitted positions;
2. final reciprocal rank for every sequence member, reported by age where age zero is the newest symbol;
3. newest-symbol final top-1 accuracy;
4. paired same-tail output distance
   `||s_even-s_odd||_2 / max(||s_even||_2+||s_odd||_2, 1e-12)`;
5. maximum mean dynamic energy, maximum absolute input-energy drift, clamp count, availability, and finite-value status.

A depth is **retained** for a profile only when immediate and newest final accuracy are both 1.0 and mean final reciprocal rank at every represented age is at least `0.05`. A depth is **history-observable** only when it is retained and median paired same-tail output distance is at least `0.01`. Capacity is the largest qualifying depth, or zero if none qualifies.

## Frozen outcome tree

Mechanical evidence requires the canonical RX 7900 XTX float32 device, exact schemas/hashes/shapes/history tensor, finite scores and energies, zero clamps, maximum mean dynamic energy at most `1.05`, and maximum absolute input-energy drift at most `2e-5`.

After mechanics pass:

- `SUPPORTS` if any profile has history-observable capacity at least 2;
- `CONTRADICTS` if every profile has history-observable capacity below 2, retained capacity at most 1, depth-2 oldest-symbol mean reciprocal rank below `0.05`, and depth-2 median paired distance below `0.01`;
- `INCONCLUSIVE` otherwise.

Return `FAIL` only for evidence-integrity or mechanical failure and `INCOMPLETE` only when the canonical board is unavailable or interrupted. A negative outcome is preserved; thresholds, histories, and profiles are never adjusted after observation.

## Artifacts and stopping rule

Raw:

- `_diag/l35-heldout-chromatic-capacity/l35-board.json`;
- `_diag/l35-heldout-chromatic-capacity/l35-traces.npz`.

Verification:

- `artifacts/l35-heldout-chromatic-capacity/L35-HELDOUT-CHROMATIC-CAPACITY-REPORT.md`;
- `artifacts/l35-heldout-chromatic-capacity/l35-verification.json`.

Writes use atomic sibling replacement, canonical finite JSON, and NPZ with `allow_pickle=False`. Small CPU runs may repair evidence plumbing only. Then run one canonical GPU board and one independent verifier. Preserve the first complete outcome. Any changed field mechanism or sequence protocol requires a new preregistration and profile.
