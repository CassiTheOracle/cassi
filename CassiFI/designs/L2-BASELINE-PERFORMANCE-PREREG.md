# CassiQwen L2 — Local Baseline Performance Receipt

## Status: FROZEN BEFORE RUN—2026-08-18

## Scope

This receipt measures the already-running local Qwen server as a frozen language-model baseline. It does not attach, invoke, or score any Cassi field, MnemicField state, tool loop, reranker, modified prompt prefix, logit processor, or KV-cache intervention.

The target artifact and service are fixed by `MODEL-RECEIPT.md`:

- GGUF: `Qwen3.8-27B-Q4_K_M.gguf`
- SHA-256: `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169`
- Runtime: llama.cpp build 10472, Windows Vulkan package
- Endpoint: `http://127.0.0.1:8080/v1/chat/completions`
- Model request id: absolute GGUF path returned by `/v1/models`
- Context: 32,768 tokens; one slot; loopback-only binding

## Question

Can the fixed local service deliver a reproducible, measurable no-field baseline suitable for later Cassi-vs-baseline comparisons?

## Fixed request policy

Every request uses:

```json
{
  "temperature": 0,
  "stream": false,
  "chat_template_kwargs": { "enable_thinking": false }
}
```

No system prompt is supplied. The model receives exactly one user prompt. The evaluation runner issues requests serially. It records the raw response object, elapsed monotonic wall time, HTTP status, `usage`, and the exact assistant `content`.

## Fixed board

| ID | User prompt | `max_tokens` | Pass rule |
|---|---|---:|---|
| `echo_ready` | `Reply with exactly: CASSI_LOCAL_READY` | 16 | Trimmed content equals `CASSI_LOCAL_READY`. |
| `arithmetic` | `What is 17 multiplied by 6? Reply with only the integer.` | 16 | Trimmed content equals `102`. |
| `reverse_word` | `Reverse the letters in cassi. Reply with only the reversed word.` | 16 | Trimmed content equals `issac`. |
| `json_shape` | `Return exactly this JSON object and nothing else: {"cassi":true,"rungs":3}` | 32 | Content parses as JSON and deep-equals `{"cassi":true,"rungs":3}`. |
| `short_explanation` | `In one sentence, define a loopback network address.` | 64 | Non-empty final content, no error, and completion tokens are present. This is a service-liveness observation, not a semantic-quality claim. |

The first four items are exact, pre-specified functional checks. The final item is intentionally scored only as a complete response because its semantic wording is not frozen to a single reference answer.

## Measurements

For each board item, record:

- outcome: `PASS`, `FAIL`, or `ERROR`;
- elapsed client wall time in milliseconds;
- `usage.prompt_tokens`, `usage.completion_tokens`, and `usage.total_tokens` when returned;
- `timings.prompt_n`, `timings.prompt_ms`, `timings.prompt_per_second` when returned;
- `timings.predicted_n`, `timings.predicted_ms`, `timings.predicted_per_second` when returned;
- exact content and any reasoning content separately;
- HTTP or parse error detail, if applicable.

Aggregate only the following pre-stated quantities from successful responses that contain their server timing fields:

- median prompt throughput;
- median generation throughput;
- median client wall time;
- exact-board score: passed exact items / 4;
- service-board score: completed items / 5.

No average is substituted for a missing measurement. No outlier is removed. No task is retried.

## Cache terminology

The server and model are already loaded from L1. This receipt therefore does **not** claim a process-cold latency. The first serial request is labeled `first-request`; the remaining requests are labeled `resident-request`. llama.cpp prefix/KV-cache reuse is recorded only if returned by the server; it is not inferred from wall time.

## Decision tree

1. If `/health` fails before the board, verdict is `INVALID`; no board requests are sent.
2. If the reported `/v1/models` identifier differs from the fixed model path, verdict is `INVALID`; no board requests are sent.
3. If any board request errors, is malformed, omits final string content, or returns reasoning content despite thinking being disabled, verdict is `FAIL`.
4. Otherwise, if any of the four exact items fails its pre-stated rule, verdict is `FAIL`.
5. Otherwise, if the one-sentence liveness item completes, verdict is `PASS` and the observed throughput values become the L2 baseline receipt.
6. Any `INVALID` or `FAIL` result closes this L2 protocol. A changed configuration, task board, metric, or retry requires a new pre-registration.

## Stopping rule

Exactly one health check, one models check, and one serial pass across the five-item board. There are no retries, parameter sweeps, or post-hoc prompt changes.

## Interpretation tiers

- **T1 measured:** endpoint health, responses, timings, usage, exact-board score, and computed medians from this one frozen run.
- **T2 inferred:** suitability of the observed service as the no-field comparison point for the next Cassi experiment.
- **T3 speculative:** any claim that field steering will improve this model. This receipt cannot support it.

## Terminal contract

This protocol terminates as `PASS`, `FAIL`, or `INVALID`. The result will be written into `L2-BASELINE-PERFORMANCE-REPORT.md` with all raw response data needed to reproduce the stated aggregate values.
