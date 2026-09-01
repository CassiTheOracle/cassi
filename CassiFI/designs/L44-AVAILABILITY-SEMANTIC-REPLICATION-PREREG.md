# L44 Availability-Semantic Harmonic Replication — Preregistration

## Status: frozen before implementation or runs

The noncanonical audit at `artifacts/harmonic-reconstruction-audit/harmonic-reconstruction-audit.json` established two distinct facts without changing a frozen verdict:

- L43 stable aggregate scores independently reconstruct within the existing tolerance, with maximum absolute error $1.0943040251731873\times10^{-8}$.
- All 16 raw/independent age-winner disagreements occur in unavailable harmonics. Every available winner agrees; the largest mismatched score is only $1.4657511870908024\times10^{-9}$ of its numerical availability floor.

L43 nevertheless has no canonical functional verdict because its delegated verifier compared `age_symbols` across every harmonic, including unavailable slots whose argmax has no semantic meaning.

L44 is a fresh canonical replication of the unchanged L43 field under one preregistered evidence-rule correction: age-winner equality is checked only after availability reconstructs exactly, and only on available age slots. Unavailable winner indices are ignored. Full age scores, availability, aggregate scores, emitted symbols, ranks, state, energy, drift, clamps, source hashes, and artifact hashes remain independently checked at their frozen tolerances.

## Frozen identities

- Layout profile: `cassi.qi-cyclic-chromatic-coordinate-native.v1`
- Operator profile: `cassi.qi-stable-harmonic-age-ladder.v1`
- Projection profile: `cassi.qi-cyclic-chromatic-projection.v1`
- Evidence schema: `cassi.l44.availability-semantic-replication.v1`
- Field module: unchanged `cassi_stable_harmonic_field.py`
- Runner: `verification/run_l44_semantic_harmonic_replication.py`
- Independent verifier: `verification/verify_l44_semantic_harmonic_replication.py`
- Focused contracts: `tests/test_l44_semantic_harmonic_verifier.py`

No field equation, profile constant, state, solver, lift, deposit, readout score, numerical floor, schedule, projection, or clamp threshold changes in L44.

## Frozen semantic comparison rule

For each independently reconstructed readout:

1. Raw age-score arrays must match within absolute tolerance $3\times10^{-5}$ and relative tolerance $2\times10^{-4}$.
2. Raw age availability must equal independently reconstructed availability exactly.
3. Raw age winners must equal independently reconstructed winners at every slot where availability is true.
4. Raw winner indices at unavailable slots are neither compared nor counted because no semantic symbol exists there.
5. Full aggregate scores must match within the same frozen tolerances.
6. Emitted symbols and ordinary availability must match exactly.

An available winner disagreement, availability disagreement, full-score mismatch, or emitted-symbol disagreement is a mechanical `FAIL`. An unavailable winner disagreement is reported diagnostically and has no verdict effect.

## Canonical board

Run the unchanged L43 stable harmonic controller once on float32 `cuda`/ROCm with:

- batch size 8,
- mode count 2048,
- 8 evolution steps per tick,
- inherited L30/L31 blank, first-heartbeat, projection, target/distractor, pre-distractor, long-horizon, and 128-deposit stress schedules,
- the four-deposit rows $(T_i,D_i,T_{i+1},D_{i+1})$ followed by eight no-symbol ticks.

Raw outputs:

- `_diag/l44-semantic-harmonic-replication/l44-board.json`
- `_diag/l44-semantic-harmonic-replication/l44-traces.npz`
- `_diag/l44-semantic-harmonic-replication/l44-projection.png`

Verification outputs:

- `artifacts/l44-semantic-harmonic-replication/L44-SEMANTIC-HARMONIC-REPORT.md`
- `artifacts/l44-semantic-harmonic-replication/l44-verification.json`

The board must hash-bind this preregistration, the formal audit receipt, every reused L30/L31/L42/L43 source dependency, and the new runner/verifier.

## Focused controls

Before evidence, focused contracts must establish:

1. equal available winners pass,
2. an unavailable winner disagreement passes and is counted diagnostically,
3. an available winner disagreement fails,
4. an availability mismatch fails,
5. a full aggregate-score mismatch fails,
6. exact availability-qualified comparison leaves all input arrays unchanged.

## Functional gates

The 13 functional gates remain unchanged from L43:

1. exact pre-target accuracy is 1.0,
2. tick-0 target accuracy is at least 0.875,
3. pre-distractor target MRR is at least 0.75,
4. tick-8 distractor accuracy is at least 0.75,
5. long-horizon distractor MRR is at least 0.25,
6. long-horizon original-target MRR is at least 0.05,
7. tick-0 white coherence is at least 0.90,
8. blank maximum differential magnitude is at most $10^{-6}$,
9. the stress path is clamp-free and total mean dynamic energy never exceeds 1.05,
10. immediate emitted-symbol accuracy is 32/32,
11. top four after deposit four exactly equal reverse deposit order,
12. top four after eight no-symbol ticks still exactly equal reverse order,
13. exactly four age slots are available at both reads, unavailable harmonics contribute exact-zero normalized remainder, every full score reconstructs at frozen tolerance, all values are finite, and the four-deposit arm is clamp-free.

Mechanical integrity additionally requires source/schema/artifact hashes, unchanged inactive modes, exact codebook reconstruction, first-heartbeat carrier-only behavior, maximum input-energy drift at most $5\times10^{-5}$, total mean dynamic energy at most 1.05, and semantic comparison implemented without importing the stable field controller.

## Decision and stopping rule

- `ADOPT` only if every mechanical check and all 13 functional gates pass.
- `REJECT` if mechanics pass but at least one functional gate fails.
- `FAIL` for integrity, reconstruction, schema, source-binding, nonfinite, clamp/safety-rescale, or other mechanical failure.
- `INCOMPLETE` if the canonical board does not complete.

Run focused contracts, one disposable CPU smoke, then exactly one canonical GPU board and independent verification. Delete smoke artifacts before canonical execution. Preserve the first complete L44 board and receipt without tuning or rerunning. L42 and L43 artifacts remain immutable.
