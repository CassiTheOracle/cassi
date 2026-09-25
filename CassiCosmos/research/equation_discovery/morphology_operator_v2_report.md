# Morphology-Aware Field Operator Campaign V2

## Status: UNSUPPORTED_REGIME_MODEL — 2026-09-20

## Result

The morphology-aware successor language executed end to end on four fresh worlds and was independently reconstructed. The field selected

\[
\frac{\mathbf a}{A_0}
=
0.0639720498873\,
\widehat{-\nabla\log\rho}\;
\operatorname{signed\_square}(v_r).
\]

The selected expression uses a density-gradient frame and squared radial speed. It selected none of the six added morphology coordinates.

Its held-out mean NRMSE was `0.9998473144205835`, above the campaign's `0.85` regime-support threshold. The classification is therefore `UNSUPPORTED_REGIME_MODEL`.

## Fresh-world reading

| Fresh world | Selected NRMSE |
|---|---:|
| `MH3` narrow spiral | `1.0013722941029648` |
| `MH6` nested shells | `0.9999660928046744` |
| `MHC3` concentrated spiral | `0.9980420337026054` |
| `MHL3` live-field spiral | `1.0000088370720892` |

The morphology coordinates successfully described the distinct geometric regimes, but within the V2 development evidence the field preferred a pre-existing radial-flow expression. The new geometry was therefore available and selected against, rather than absent from the language.

The selected expression was structurally distinct from the recorded human comparators. Its prediction cosine to harmonic, inverse-square, and prior-radial comparators was `-0.002046597503146575`, `0.000073660286328`, and `-0.00371370339183229` respectively. It also improved on those comparators numerically, but that comparison does not establish a useful collective law because its absolute error remains essentially a unit normalized residual on every fresh world.

## Integrity

The receipt is `CassiFI/_diag/morphology-operator-v2/receipt.json` with result digest `701bfc5420cd0d471c708d26e430dbce5e66a673cb18323f956522ee05f55d40`.

Independent reconstruction returned `PASS`: 108 source hashes, all 37 atoms, all six vector frames, fourteen field-selection records, nine mutation controls, and zero model calls were verified. The source implementation digest is `bf0a1439142699f6ebcc797d3171c2fba27989e11015970068165c5f920fcf9b`.

V1 ended before hidden-target reading when its field session exceeded the safe cumulative selection schedule and faulted. V2 used a new field instance and a 16-candidate local selection surface; it completed without that failure.
