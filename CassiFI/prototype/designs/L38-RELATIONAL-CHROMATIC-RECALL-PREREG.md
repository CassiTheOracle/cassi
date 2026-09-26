# L38 Relational Chromatic Recall — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L38 is frozen after preserving the complete L37 `REJECT` and before any L38 module, test, runner, verifier, smoke, or canonical execution. It branches directly from immutable L31 and changes one readout equation. L30–L37 sources and canonical evidence remain immutable.

## Question

A full-trust chromatic deposit rotates the white carrier into the new differential direction and rotates the previous differential projection into the common coordinate. For ideal codeword phases `u_old,u_new`, this produces the relational phase `C ~ -conjugate(u_new)*u_old` while `D ~ u_new`, so `-C*D ~ u_old`.

Does exposing this already-present common–differential relation recover the preceding symbol without external memory, a time counter, a learned decoder, or any field-law change?

## Identity and files

Unchanged identities:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New operator/readout identity: `cassi.qi-relational-chromatic-recall.v1`.

Evidence identities:

- board: `cassi.l38.relational-chromatic-board.v1`;
- traces: `cassi.l38.relational-chromatic-traces.v1`;
- verification: `cassi.l38.relational-chromatic-verification.v1`.

New files:

- `cassi_relational_chromatic_field.py`;
- `tests/test_cassi_relational_chromatic_field.py`;
- `verification/run_l38_relational_chromatic_field.py`;
- `verification/verify_l38_relational_chromatic_field.py`.

## Sole changed mechanism: common–differential relational score

L31 field state, codebook, heartbeat, modulation, evolution, cyclic coupling, bounds, availability, per-bank diagnostics, contribution tensor, white-coherence diagnostic, symbol tie-breaking, and projection remain unchanged.

For white vector `w_s=1/sqrt(7)`, first channel harmonic `h_s=exp(2*pi*i*s/7)`, common coordinate `C_smb`, and differential coordinate `D_smb`, collapse

- `c_mb = sum_s w_s*C_smb`;
- `d_mb = (1/sqrt(7))*sum_s conjugate(h_s)*D_smb`.

Define the sole new relational trace

`r_mb = -c_mb*d_mb`.

For codebook row `u_a`, compute

- the unchanged coherent current coefficient `A_Dab` from L31;
- `A_Rab = (1/W)*sum_m conjugate(u_am)*r_mb`;
- score `S_ba = |A_Dab|^2 + |A_Rab|^2`.

No conjugation other than the declared channel/codebook alignment, velocity coordinate, normalization fitted from evidence, lag bank, maximum over time, channel-energy replacement, protected lane, recurrence, history table, or auxiliary adaptive state enters the score.

## Focused checks

Before canonical execution, CPU tests must establish:

1. heartbeat, modulation, evolution, energy, bounds, and projection remain bit-identical to L31;
2. direct recomputation of `c,d,r,A_R,S` equals the returned score tensor;
3. an exact synthetic `(u_old,u_new)` rotation ranks `u_new` and `u_old` in the top two while L31 exposes only `u_new`;
4. a first deposit with zero relational trace preserves exact L31 scores;
5. blank state remains unavailable with exactly zero scores;
6. profile fingerprint is distinct and no adaptive state exists.

Tests may repair conformance only. They may not change the product, sign, score sum, field schedule, constants, or gates.

## Frozen canonical board and gates

Canonical hardware, float32 dtype, `mode_count=2048`, targets, distractors, batch size, read ticks, eight steps per tick, 128-tick blank/stress schedules, energy accounting, artifact rules, and independent trace recomputation are exactly the inherited L31 board.

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

- `_diag/l38-relational-chromatic-field/l38-board.json`;
- `_diag/l38-relational-chromatic-field/l38-traces.npz`;
- `_diag/l38-relational-chromatic-field/l38-projection.png`.

Verification:

- `artifacts/l38-relational-chromatic-field/L38-RELATIONAL-CHROMATIC-RECALL-REPORT.md`;
- `artifacts/l38-relational-chromatic-field/l38-verification.json`.

Writes use atomic sibling replacement, canonical finite JSON, and NPZ with `allow_pickle=False`. Small CPU checks may repair conformance only. Then run one canonical RX 7900 XTX float32 board and one independent verifier. Preserve the first complete verdict. Any readout or field-law change requires a new preregistration and profile.
