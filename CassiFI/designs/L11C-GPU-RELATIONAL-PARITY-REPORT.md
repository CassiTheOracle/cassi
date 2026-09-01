# CassiQwen L11c — Single-Engine GPU Relational Parity Report

## Status: NULL—2026-08-18

## Protocol

This report executes `L11C-GPU-RELATIONAL-PARITY-PREREG.md` with the unchanged CassiCosmos two-fluid engine. One local engine was reused across the four arms, with its existing `_clear_field()` between arms. The run was windowed on the RX 7900 XTX and produced `CassiCosmos/_diag/cassi_qwen_relational_field.json`.

## Measured result

All arms produced finite values. The aligned and shuffled arms were identical in the candidate-local answer/retrieve difference:

| Arm | Step | Time | Answer local $q$ | Retrieve local $q$ | Difference |
|---|---:|---:|---:|---:|---:|
| `field_off` | 0 | 0 | 0.127704591467226 | 0.0892559635716617 | 0.0384486278955641 |
| `relation_aligned` | 16 | 0.08 | 0.113394127435119 | 0.0796608322972698 | 0.0337332951378489 |
| `relation_shuffled` | 16 | 0.08 | 0.113394127435119 | 0.0796608322972698 | 0.0337332951378489 |
| `channel_swapped` | 16 | 0.08 | 0.113394127435119 | 0.0796608322972698 | 0.0337332951378489 |

The aligned and shuffled local readouts were equal at the recorded precision. Channel-swapping changed global mean-field scalars slightly but did not change the candidate-local readout.

## Terminal verdict

**NULL.** The frozen decision tree closes at the first branch: aligned and shuffled relation relay placement produced the same candidate-local answer/retrieve difference. This probe found no detectable relation-specific local readout effect under its fixed geometry, relay placement, 16-step horizon, and 3×3×3 measurement windows.

## Interpretation

- **T1 measured:** the unchanged GPU engine remained finite through 16 steps; candidate-local values and control comparisons are in the raw JSON receipt.
- **T2 inferred:** this particular spatial relay encoding does not couple into the measured candidate-local readouts strongly enough to distinguish aligned from shuffled relations.
- **T3 speculative:** that the two-fluid engine cannot express useful relational arbitration. This single geometry/horizon probe cannot support that claim.

## Consequence

The L10b surrogate does not transfer to the current GPU field through this relay construction. The relay mapping is not tuned or retried. Future field work would need a new mechanism design—such as candidate-centered interacting pools or a longer-range coupling term—with a fresh pre-registration.
