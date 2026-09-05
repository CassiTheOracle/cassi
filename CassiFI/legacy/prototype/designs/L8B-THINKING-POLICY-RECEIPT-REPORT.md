# CassiQwen L8b — Resilient Thinking Policy Receipt Report

## Status: DELIBERATE-COST-CONFIRMED—2026-08-18

## Protocol

This report executes `L8B-THINKING-POLICY-RECEIPT-PREREG.md` after the local service passed fresh health and model-identity checks. Raw receipt: `thinking-policy-receipt.json`.

## Result

Both fast and deliberate modes produced the exact final answer on both fixed items:

| Item | Fast | Deliberate |
|---|---|---|
| `logic_chain` | `Pia` | `Pia` |
| `modular_arithmetic` | `1` | `1` |

| Measurement | Fast | Deliberate |
|---|---:|---:|
| Exact score | 2 / 2 | 2 / 2 |
| Completion tokens | 5 | 132 |
| Logic-chain wall time | 329.165 ms | 1,180.724 ms |
| Arithmetic wall time | 715.580 ms | 3,624.329 ms |

**Terminal verdict: DELIBERATE-COST-CONFIRMED.** Deliberate mode preserved exact answer quality on this two-item receipt but used 127 additional completion tokens. Its output included explicit reasoning content; fast mode did not.

## Interpretation

- **T1 measured:** two exact answers per arm, completion-token totals, response timing, and reasoning-content presence in `thinking-policy-receipt.json`.
- **T2 inferred:** fast and deliberate completion are distinguishable local operational modes with materially different token and latency costs on these trivial items.
- **T3 speculative:** that a Cassi field signal should decide which mode to use, or that deliberate mode improves harder tasks. This receipt does not show a quality gain.

## Operational decision

The default remains fast completion. Deliberate thinking is an explicitly requested, costlier mode; it is not automatically selected by any field observation.

## Next boundary

CassiQwen’s current work is complete at the safe-integration stage: local model service, baseline, field observation, calibrated projection, default-off pure mapper, rejected retrieval intervention, and measured fast/deliberate capability receipt. A later experiment may open a new field-policy line only with an independently derived mapping and a pre-registered quality/cost gate.
