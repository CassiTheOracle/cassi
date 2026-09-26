# CassiQwen L14 — Local Candidate-Pool Coupling Report

## Status: NULL—2026-08-18

## Protocol

This report executes `L14-LOCAL-POOL-COUPLING-PREREG.md` using the unchanged CassiCosmos two-fluid engine. The windowed RX 7900 XTX run wrote `CassiCosmos/_diag/cassi_qwen_local_pool.json`.

## Measured result

All arms remained finite through 16 steps.

| Arm | Answer $q$ | Retrieve $q$ | Difference |
|---|---:|---:|---:|
| `off` | 0.724500739938849 | 0.505777835898931 | 0.218722904039918 |
| `aligned` | 0.639875259263713 | 0.448131056786167 | 0.191744202477546 |
| `shuffled` | 0.639872057090716 | 0.448128092310462 | 0.191743964780253 |
| `swapped` | 0.639875259263713 | 0.448131056786167 | 0.191744202477546 |

Aligned versus shuffled placement produced a small finite difference in the local readout. However, the channel-swapped arm was identical to the aligned arm at the recorded precision. The fixed decision tree therefore closed at `NULL`.

**Terminal verdict: NULL.** The localized relay geometry changed the field state slightly, but this probe found no channel-sensitive candidate-local mechanism.

## Interpretation

- **T1 measured:** finite GPU evolution, local readouts, and controls above.
- **T2 inferred:** spatial proximity can perturb the candidate-local readout at this scale, but the tested Yang/Yin relay semantics did not survive as a distinguishable readout signal.
- **T3 speculative:** that the current two-fluid engine cannot support channel-sensitive candidate arbitration. This probe used one geometry, one width, one step horizon, and a single readout statistic.

## Consequence

The L10b relation-coupled surrogate remains untransferred to the current GPU engine. The L14 geometry is not adopted as a production mechanism. Further GPU work would need a new preregistered channel-coupling construction or an engine term specifically derived and tested under the scratch-layer/no-op contract; no tuning is performed here.
