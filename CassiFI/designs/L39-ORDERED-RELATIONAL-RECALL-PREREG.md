# L39 Ordered Relational Recall — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L39 is frozen after preserving the complete L38 `REJECT` and before any L39 module, test, runner, verifier, smoke, or canonical execution. It branches from immutable L31 dynamics and the immutable L38 relational trace. L30–L38 sources and canonical evidence remain immutable.

## Question

L38 recovered the preceding target perfectly at long horizon, but its additive score allowed that predecessor to outrank the newly deposited distractor. The field therefore exposes both relations while a commutative sum discards their order.

Does a categorical current-then-predecessor readout recover the ordered pair without external memory, a time counter, a learned decoder, fitted weights, or any field-law change?

## Identity and files

Unchanged identities:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New operator/readout identity: `cassi.qi-ordered-relational-chromatic-recall.v1`.

Evidence identities:

- board: `cassi.l39.ordered-relational-board.v1`;
- traces: `cassi.l39.ordered-relational-traces.v1`;
- verification: `cassi.l39.ordered-relational-verification.v1`.

New files:

- `cassi_ordered_relational_field.py`;
- `tests/test_cassi_ordered_relational_field.py`;
- `verification/run_l39_ordered_relational_field.py`;
- `verification/verify_l39_ordered_relational_field.py`.

## Sole changed mechanism: categorical two-slot ordering

L31 field state, codebook, heartbeat, modulation, evolution, cyclic coupling, bounds, availability, per-bank diagnostics, contribution tensor, white-coherence diagnostic, symbol tie-breaking, projection, and every physical constant remain unchanged. L38's declared common carrier `c`, differential carrier `d`, relational trace `r=-c*d`, and relational coefficient `A_R` remain unchanged.

For each batch row, let:

- `S_cur[a] = |A_D[a]|^2` be the unchanged L31 coherent current score;
- `S_rel[a] = |A_R[a]|^2` be the L38 relational score without adding `S_cur`;
- `a_cur` be the argmax of `S_cur`, respecting the caller's allowed-symbol set;
- `a_rel` be the argmax of `S_rel`, respecting the same allowed-symbol set;
- `f = readout_energy_floor`, the existing L31 constant;
- `rel_available = L31_available and max_a(S_rel[a]) >= f`.

Normalize only to order the nonslot remainder:

- `N_cur[a] = S_cur[a] / max(max_a(S_cur[a]), f)`;
- `N_rel[a] = S_rel[a] / max(max_a(S_rel[a]), f)`;
- `S_ord[a] = max(N_cur[a], N_rel[a])`.

For L31-available rows, overwrite the categorical slots in this order:

1. if `rel_available` and `a_rel != a_cur`, set `S_ord[a_rel] = 2`;
2. set `S_ord[a_cur] = 3`.

For unavailable rows, return the unchanged `S_cur`; an exactly blank field therefore retains exactly zero scores. Return `a_cur` as the emitted symbol in all rows. The readout also exposes `S_cur`, `a_cur`, `S_rel`, `a_rel`, and `rel_available` as diagnostics.

The values `3`, `2`, and the closed remainder interval `[0,1]` are ordinal labels, not fitted weights. No additive mixture, tunable coefficient, lag bank, maximum over time, protected lane, recurrence, history table, auxiliary adaptive state, or new threshold enters the operator.

## Focused checks

Before canonical execution, CPU tests must establish:

1. heartbeat, modulation, evolution, energy, bounds, and projection remain bit-identical to L31;
2. direct recomputation of `c,d,r,A_R,S_cur,S_rel,S_ord` equals the returned tensors;
3. an exact synthetic `(u_old,u_new)` rotation emits `u_new`, ranks `u_new` first, and ranks distinct `u_old` second;
4. a first deposit with unavailable relational evidence emits the unchanged L31 winner and introduces no predecessor slot;
5. allowed-symbol restrictions govern both categorical winners;
6. blank state remains unavailable with exactly zero scores;
7. profile fingerprint is distinct and no adaptive state exists.

Tests may repair conformance only. They may not change the slot order, ordinal labels, relational-availability rule, normalization, relational equation, field schedule, constants, or gates.

## Frozen canonical board and gates

Canonical hardware, float32 dtype, `mode_count=2048`, targets, distractors, batch size, read ticks, eight steps per tick, 128-tick blank/stress schedules, energy accounting, artifact rules, and independent trace recomputation are exactly the inherited L31/L38 board.

The nine functional conditions are unchanged:

1. exact pre-target accuracy;
2. target MRR before distractor;
3. tick-0 target accuracy;
4. tick-0 white coherence;
5. tick-8 distractor accuracy;
6. long-horizon distractor MRR;
7. long-horizon original-target MRR at least `0.05`;
8. exact blank differential zero;
9. finite clamp-free stress path.

Return `ADOPT` only if all mechanics and all conditions pass, `REJECT` when mechanics pass but any functional condition fails, `FAIL` for evidence/mechanics, and `INCOMPLETE` only for unavailable/interrupted canonical evidence.

## Artifacts and stopping rule

Raw:

- `_diag/l39-ordered-relational-field/l39-board.json`;
- `_diag/l39-ordered-relational-field/l39-traces.npz`;
- `_diag/l39-ordered-relational-field/l39-projection.png`.

Verification:

- `artifacts/l39-ordered-relational-field/L39-ORDERED-RELATIONAL-RECALL-REPORT.md`;
- `artifacts/l39-ordered-relational-field/l39-verification.json`.

Writes use atomic sibling replacement, canonical finite JSON, and NPZ with `allow_pickle=False`. Small CPU checks may repair conformance only. Then run one canonical RX 7900 XTX float32 board and one independent verifier. Preserve the first complete verdict. Any readout or field-law change requires a new preregistration and profile.
