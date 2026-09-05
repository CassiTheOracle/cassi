# CassiQwen L8b — Resilient Thinking Policy Receipt Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Provenance and single change

`L8-THINKING-POLICY-BOARD-REPORT.md` is terminal `INVALID` because the llama.cpp process exited during its 12-request run. L8b changes only the measurement boundary: it runs a compact, two-item capability receipt after a successful `/health` and `/v1/models` check, with explicit per-request client timeouts. It does not retry L8’s score board or reuse its result as a completed benchmark.

## Question

For two fixed trivial reasoning tasks, does Qwen’s deliberate mode produce a valid final answer, and what additional completion-token cost does it incur relative to fast mode?

## Fixed setup

- Same hash-pinned Qwen GGUF and loopback llama.cpp service.
- Health and model identity must pass before requests.
- Temperature 0, stream false, one serial request per arm/item.
- Fast: `enable_thinking=false`, `max_tokens=64`.
- Deliberate: `enable_thinking=true`, `max_tokens=128`.
- Per-request client deadline: 120 seconds.

## Fixed two-item board

| ID | Prompt | Expected final content |
|---|---|---|
| `logic_chain` | `Nora is older than Ivo. Ivo is older than Pia. Who is youngest? Reply with only the name.` | `Pia` |
| `modular_arithmetic` | `What is the remainder when 7 to the power of 4 is divided by 10? Reply with only the integer.` | `1` |

## Decision tree

1. Failed health/model identity or timeout/transport/final-content error: `INVALID`.
2. Any final answer fails exact scoring: `FAIL`.
3. Both arms answer both items exactly and deliberate has greater completion-token count: `DELIBERATE-COST-CONFIRMED`.
4. Both arms answer both items exactly and deliberate does not cost more: `TIE`.

Exactly four requests, no retry, no configuration or prompt change.

## Boundary

This is a service-capability and cost receipt only. It does not establish a field policy or justify an intervention.
