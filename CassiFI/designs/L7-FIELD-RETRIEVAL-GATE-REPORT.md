# CassiQwen L7 — Field Candidate-Order Retrieval Gate Report

## Status: NULL—2026-08-18

## Protocol

This report executes the frozen `L7-FIELD-RETRIEVAL-GATE-PREREG.md` against the local Qwen service. The only changed variable between arms was candidate order: original caller order for baseline and the L6 permutation from the frozen L5d projection for field.

Raw receipt: `field-retrieval-gate.json`.

## Result

| Arm | Exact score | Items |
|---|---:|---:|
| Baseline caller order | 5 | 6 |
| L6 field candidate order | 5 | 6 |

**Terminal verdict: NULL.** The pre-registered decision tree assigns `NULL` when the field arm equals the baseline arm. This mapping did not improve exact evidence selection on the six-item board.

## Per-item receipt

| Item | Baseline | Field | Outcome |
|---|---|---|---|
| `alpha` | `E-ALPHA-2` | `E-ALPHA-2` | both pass |
| `beta` | `E-BETA-3` | `E-BETA-3` | both pass |
| `gamma` | `E-GAMMA-1` | `E-GAMMA-1` | both pass |
| `delta` | `E-DELTA-1` | `E-DELTA-1` | both fail |
| `epsilon` | `E-EPSILON-3` | `E-EPSILON-3` | both pass |
| `zeta` | `E-ZETA-1` | `E-ZETA-1` | both pass |

The `delta` failure was shared. Its candidate text named two throughput values from different measurements, and the model selected the prompt-throughput figure rather than the pre-registered generation-throughput figure. Since that ambiguity was present identically in both arms, it does not favor either arm and must remain in this closed record.

## Interpretation

- **T1 measured:** 12 exact model responses, 5/6 for each arm, and `NULL` under the frozen rule.
- **T2 inferred:** the tested geometry-hash field permutation does not supply measurable benefit for this simple evidence-selection board.
- **T3 speculative:** that another independently derived field-to-retrieval mechanism may help under a different, separately registered task. This result does not support it.

## Consequence

The L6 mapper is **not adopted as a Qwen retrieval intervention**. It remains a tested offline utility, disabled and disconnected from the local-model path. The L2 no-field baseline remains the operational default.

## Next gate

A successor must not retry this mapper or tune this board. The next viable research line is to ask a distinct question: whether a field-derived signal can regulate a bounded operational property that is observable independently of answer correctness, such as when to request deliberate thinking versus fast completion. That line requires a new theoretical mapping and a new pre-registration.
