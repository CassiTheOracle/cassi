# CassiQwen L13 — Q4-to-Q6 Escalation Receipt Pre-registration

## Status: FROZEN—AWAITING Q6 ARTIFACT—2026-08-18

## Prerequisite

The workspace currently contains the hash-pinned `Qwen3.8-27B-Q4_K_M.gguf` only. No Q6/Q8 GGUF is present in `CassiQwen/`. This protocol defines the receipt and evaluator but cannot run until an exact same-model higher-precision artifact is supplied or explicitly acquired.

The Q6 artifact must document its own path, SHA-256, quantization type, model architecture, and source. It must be the same Qwen family/configuration, not a different model used as a proxy.

## Question

Can a bounded escalation policy preserve or improve task quality by using Q4 fast completion normally and escalating only failed/uncertain cases to the same-model Q6 service?

## Fixed policy arms

- `q4_only`: run every item on Q4 with fast mode.
- `q4_q6_escalate`: run Q4 fast first; run Q6 fast only when Q4’s exact final answer fails the frozen validator. A Q6 request is never issued after a Q4 pass.
- `q6_reference`: run every item on Q6 fast for reference measurement.

No thinking-mode change, prompt change, temperature change, field signal, or candidate reorder is permitted.

## Fixed board

Six deterministic tasks with exact validators:

1. arithmetic: `17 * 6 = 102`;
2. modular arithmetic: `7^4 mod 10 = 1`;
3. sequence: `2, 6, 12, 20, 30, ? = 42`;
4. logic: youngest of Nora > Ivo > Pia is `Pia`;
5. exact JSON: `{"cassi":true,"rungs":3}`;
6. short loopback definition: non-empty final content containing `127.0.0.1`.

Each model receives identical user prompts, `temperature: 0`, `stream: false`, thinking disabled, and `max_tokens: 64`. Requests are serialized. No retry is allowed.

## Metrics

Record exact task score, Q4 requests, Q6 escalations, Q6 reference requests, prompt/completion tokens, generated-token throughput, latency, and transport/model identity failures.

Define escalation utility:

\[
U=A-\lambda_T T-\lambda_L L-\lambda_Q Q,
\]

where $A$ is exact score, $T$ completion tokens, $L$ wall latency, and $Q$ number of Q6 requests. Coefficients are fixed in the runner to $\lambda_T=0.001$, $\lambda_L=0.0001$, and $\lambda_Q=0.02$; they are not tuned after the run.

## Decision tree

1. If the Q6 artifact, server, identity, or any required request is unavailable: `BLOCKED-PREREQUISITE`, not a model verdict.
2. If either model identity or architecture differs: `INVALID`.
3. If escalation exact score exceeds Q4-only and escalation utility is no lower than Q4-only: `ESCALATION-SUPPORTS`.
4. If scores tie and escalation utility is lower: `Q4-PARETO`.
5. If Q6 reference is not better than Q4 on this board: `Q6-NO-MEASURED-GAIN`.
6. Any other complete result: `INCONCLUSIVE`.

## Stopping rule

One serial run of the six-item board for each available arm, no retries or post-hoc policy changes. A missing Q6 artifact closes the current attempt as `BLOCKED-PREREQUISITE`.
