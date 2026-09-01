# L37 Incoherent Chromatic Recall — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L37 is frozen after preserving the L36 phase-portrait `ADOPT` and before any L37 module, test, runner, verifier, smoke, or canonical execution. It branches directly from immutable L31 and changes one readout equation. L30–L36 sources and canonical evidence remain immutable.

## Measured motivation and question

L35 found depth-2 oldest-symbol mean reciprocal rank near `0.0083` and same-tail score distance below `2.2e-8` for all frozen recall profiles. L36 independently showed after-tail phase-portrait distance `0.3023385225292744` for the same histories. This establishes a readout-visible/field-visible gap but does not establish where usable symbol evidence resides.

L37 tests one hypothesis: retained codebook magnitude persists across chromatic channels while channel-to-channel phase evolution cancels the coherent global sum used by L31. Does replacing only that coherent sum with a phase-insensitive channel-energy mean satisfy every inherited gate?

## Identity and files

Unchanged identities:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New operator/readout identity: `cassi.qi-incoherent-chromatic-recall.v1`.

Evidence identities:

- board: `cassi.l37.incoherent-chromatic-board.v1`;
- traces: `cassi.l37.incoherent-chromatic-traces.v1`;
- verification: `cassi.l37.incoherent-chromatic-verification.v1`.

New files:

- `cassi_incoherent_chromatic_field.py`;
- `tests/test_cassi_incoherent_chromatic_field.py`;
- `verification/run_l37_incoherent_chromatic_field.py`;
- `verification/verify_l37_incoherent_chromatic_field.py`.

## Sole changed mechanism: phase-insensitive channel score

L31 field state, codebook, heartbeat, modulation, evolution, cyclic coupling, bounds, availability, bank diagnostics, contribution tensors, white-coherence diagnostic, symbol tie-breaking, and projection remain unchanged.

For codebook row `u_a` and differential coordinate `D_s`, compute the unchanged per-channel coefficient

`A_sab = (1/W) * sum_m conjugate(u_am) * D_smb`.

L31 coherently aligns and sums these coefficients before taking magnitude. L37 instead defines the sole changed score

`S_ba = (1/7) * sum_s |A_sab|^2`.

The factor `1/7` fixes scale but does not change ranks. Allowed-symbol selection applies to this score with the unchanged lowest-index tie rule. No channel phase, velocity coordinate, common coordinate, protected lane, time average, maximum-over-time, learned weight, fitted coefficient, or auxiliary state enters the score.

## Focused checks

Before canonical execution, CPU tests must establish:

1. heartbeat, modulation, evolution, energy, bounds, and projection remain bit-identical to L31;
2. direct score recomputation equals the returned score tensor;
3. a synthetic equal-magnitude channel-dephased symbol cancels in L31 coherent scoring but remains rank one under L37;
4. blank state remains unavailable with exactly zero scores;
5. profile fingerprint is distinct and no adaptive state is introduced.

Tests may repair conformance only. They may not change the equation, normalization, field schedule, constants, or gates.

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

- `_diag/l37-incoherent-chromatic-field/l37-board.json`;
- `_diag/l37-incoherent-chromatic-field/l37-traces.npz`;
- `_diag/l37-incoherent-chromatic-field/l37-projection.png`.

Verification:

- `artifacts/l37-incoherent-chromatic-field/L37-INCOHERENT-CHROMATIC-RECALL-REPORT.md`;
- `artifacts/l37-incoherent-chromatic-field/l37-verification.json`.

Writes use atomic sibling replacement, canonical finite JSON, and NPZ with `allow_pickle=False`. Small CPU checks may repair conformance only. Then run one canonical RX 7900 XTX float32 board and one independent verifier. Preserve the first complete verdict. Any readout or field-law change requires a new preregistration and profile.
