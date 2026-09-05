# CassiQwen L2 — Local Baseline Performance Report

## Status: PASS—2026-08-18

## Protocol

This report executes the frozen protocol in `L2-BASELINE-PERFORMANCE-PREREG.md` against the artifact and llama.cpp service identified in `MODEL-RECEIPT.md`. No Cassi field, MnemicField state, tool loop, reranker, prompt intervention, logit processor, or KV-cache intervention participated in the run.

Raw machine receipt: `baseline-receipt.json`.

## Terminal verdict

**PASS.** Health and model identity checks passed. All four exact functional checks passed, the service-liveness item completed, and every response carried final string content with no reasoning content while thinking was disabled.

| Gate | Result |
|---|---|
| Health | `PASS`: `{"status":"ok"}` |
| Model identity | `PASS`: returned identifier matched the frozen absolute GGUF path |
| Exact board | `4 / 4` |
| Service board | `5 / 5` |
| Terminal verdict | `PASS` |

## Measured baseline

| Metric | Value |
|---|---:|
| Median client wall time | 489.789 ms |
| Median prompt throughput | 136.950 tokens/s |
| Median generated-token throughput | 36.161 tokens/s |
| First request wall time | 219.189 ms |
| Longest board response wall time | 1,534.561 ms |
| Longest board completion | 47 tokens at 35.115 generated tokens/s |

The first request reused 17 prompt tokens from the resident server cache. The remaining board requests reported zero cached prompt tokens. The run therefore establishes a resident-service baseline with explicit per-request cache information; it does not claim process-cold latency.

## Board receipt

| ID | Request class | Outcome | Final content |
|---|---|---|---|
| `echo_ready` | first-request | `PASS` | `CASSI_LOCAL_READY` |
| `arithmetic` | resident-request | `PASS` | `102` |
| `reverse_word` | resident-request | `PASS` | `issac` |
| `json_shape` | resident-request | `PASS` | `{"cassi":true,"rungs":3}` |
| `short_explanation` | resident-request | `PASS` | One complete sentence defining `127.0.0.1` loopback behavior. |

## Interpretation

- **T1 measured:** the exact request outcomes, content, timing, usage, cache counts, and medians in `baseline-receipt.json`.
- **T2 inferred:** the loopback llama.cpp service is a usable no-field baseline for the first bounded Cassi comparison.
- **T3 speculative:** that a Cassi-derived intervention will improve quality, latency, memory use, or reasoning. This report makes no such claim.

## Next gated step

The next protocol must pre-register an isolated, default-off Cassi shadow arm. The first arm should not modify Qwen weights, logits, or the KV cache. Its comparison must hold the model artifact, server settings, request board, and scoring rules fixed while changing only one declared Cassi-derived retrieval or candidate-ordering signal.
