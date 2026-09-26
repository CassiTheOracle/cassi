# Harmonic Reconstruction Audit — Noncanonical Protocol

## Status: frozen before the formal audit run

This is a read-only diagnostic of the immutable L42 and L43 GPU traces. It cannot change either frozen receipt, issue a functional verdict, justify adoption, widen a tolerance, or authorize a rerun.

## Inputs

- `_diag/l42-harmonic-age-ladder/l42-board.json`
- `_diag/l42-harmonic-age-ladder/l42-traces.npz`
- `artifacts/l42-harmonic-age-ladder/l42-verification.json`
- `_diag/l43-stable-harmonic-field/l43-board.json`
- `_diag/l43-stable-harmonic-field/l43-traces.npz`
- `artifacts/l43-stable-harmonic-field/l43-verification.json`

The audit records SHA-256 hashes for every input and refuses missing or incomplete raw boards.

## Independent comparisons

For four-deposit position 1, reconstruct age scores on CPU from the raw differential coordinates and codebook using the frozen DFT and codebook equations, without importing either field controller.

For L42, report:

1. raw GPU age-score versus independent CPU age-score maximum absolute and relative errors,
2. raw GPU aggregate scores versus aggregation from the raw GPU age scores,
3. raw GPU aggregate scores versus aggregation from independently reconstructed age scores,
4. the location and magnitude of the worst aggregate mismatch,
5. whether the raw-score aggregation validates the formula and axis handling,
6. whether the independent age-score error is inside the frozen age-score tolerance while normalized aggregation exceeds the frozen aggregate tolerance.

Classify the L42 representation failure as `FORMULA_OR_SHAPE_ERROR`, `DEVICE_ROUNDING_AMPLIFIED_BY_NORMALIZATION`, or `UNRESOLVED` from those comparisons only.

For L43, report:

1. the same raw versus independent age-score errors,
2. raw GPU aggregate scores versus stable masked aggregation from raw and independently reconstructed age scores,
3. every raw/independent age-winner disagreement split by available and unavailable slots,
4. maximum mismatched top score, minimum corresponding numerical floor, maximum top-to-floor ratio, and argmax margins,
5. whether all available winners agree.

Classify the L43 delegated verifier limitation as `OVERSTRICT_UNAVAILABLE_ARGMAX`, `SEMANTIC_AVAILABLE_WINNER_MISMATCH`, `FORMULA_OR_SHAPE_ERROR`, or `UNRESOLVED`. `OVERSTRICT_UNAVAILABLE_ARGMAX` requires all winner disagreements to be unavailable, every available winner to agree, stable full-score reconstruction to remain within the frozen aggregate tolerance, and each mismatched top score to remain below its recorded availability floor.

## Frozen tolerances

- age-score absolute tolerance: $3\times10^{-5}$,
- age-score relative tolerance: $2\times10^{-4}$,
- aggregate-score absolute tolerance: $3\times10^{-5}$,
- aggregate-score relative tolerance: $2\times10^{-4}$.

Relative errors use $\max(|x|,|y|,10^{-12})$ as denominator and are reported diagnostically; pass/fail comparisons use `allclose` with both frozen tolerances.

## Output and stopping rule

The only formal output is:

- `artifacts/harmonic-reconstruction-audit/harmonic-reconstruction-audit.json`

Run exactly once after the script passes a syntax diagnostic. Preserve the JSON as a noncanonical audit. Do not alter or regenerate L42/L43 boards, traces, reports, verification receipts, source profiles, or verdict status.
