# Morphology Residual Authority

## Result

The morphology language has independent geometric degrees of freedom, but those degrees do not provide stable additional acceleration authority after the V2 dynamic base coordinates are removed.

The reader fits the ten V2 dynamic base atoms across all six frames on each arm's early 60% segment, then measures each morphology atom and the full morphology block on the later 40%. It uses only the sixteen disclosed development arms. This is a diagnostic reading, not a holdout verdict.

## Channel capacity

After residualizing all six morphology atoms against the base language, their 108 frame-resolved columns have full rank:

\[
\operatorname{rank}(M_\perp)=108,
\qquad
\sigma_{\min}=12.167015740378584,
\qquad
\sigma_{\max}=355.53054111806756.
\]

The duplicate-identity control retained rank 108 exactly, while the added compactness residual control reduced validation RMSE by `44.969475992087427%` on average. The reader can therefore see a morphology-dependent acceleration contribution when one is present, and the morphology coordinates are not a rank-one scale ladder or a collapsed duplicate encoding.

## Actual conditional reading

Adding all six morphology blocks worsened mean held-out development RMSE by `37.81547590264799%`. The individual mean fractional RMSE changes were:

| Coordinate | Mean fractional RMSE reduction |
|---|---:|
| Shell tangentiality | `+0.00731708370291833` |
| Radial counterflow | `+0.005329839094461636` |
| Radial spread | `-0.01045551311199315` |
| Compactness | `-0.01307182784876236` |
| Anisotropy | `-0.025810350997004773` |
| Planarity | `-0.14984097497158474` |

The two small positive readings are below the scale of stable authority across the disclosed regimes; the combined block overfits sharply, driven most visibly by the concentrated `GC2` development arm. The current-snapshot morphology representation is therefore geometrically expressive but does not carry a transferable conditional acceleration signal in this data.

## Artifact

The structured reading is `CassiFI/_diag/morphology-residual-authority-v1.json`. It records all sixteen per-arm chronological comparisons, the singular spectrum, all pair separations, the duplicate-identity control, and the injected compactness firing control.
