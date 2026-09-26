# CassiQwen L7 — Field Candidate-Order Retrieval Gate Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Question

Does the L6 field-derived candidate permutation improve a fixed, closed-book evidence-selection task over the original candidate order when every Qwen request and candidate text is otherwise identical?

## Scope

This is the first Qwen comparison gate. The only varied component is candidate ordering:

- **Baseline arm:** caller order.
- **Field arm:** `rankCandidatesByField(..., { enabled: true })` using the fixed L5d projection.

Both arms use the same artifact, llama.cpp server, model id, prompt template, candidate texts, query, `temperature: 0`, `stream: false`, thinking disabled, `max_tokens: 32`, and one serial request per item. No tool, memory store, field engine, prompt supplement, logit/KV/weight change, sampling change, retry, or parameter sweep is allowed.

## Fixed board

Each item contains three immutable evidence candidates. The correct evidence ID is the only accepted output.

| Item | Query | Correct ID |
|---|---|---|
| `alpha` | `Which evidence ID states that the CassiQwen field bridge is read-only?` | `E-ALPHA-2` |
| `beta` | `Which evidence ID states that Qwen thinking must be explicitly disabled for short deterministic completions?` | `E-BETA-3` |
| `gamma` | `Which evidence ID states the calibrated projection coordinate map uses N - 1?` | `E-GAMMA-1` |
| `delta` | `Which evidence ID reports the fixed Qwen generation baseline in tokens per second?` | `E-DELTA-2` |
| `epsilon` | `Which evidence ID says the L6 mapper does not interpret q as factual truth?` | `E-EPSILON-3` |
| `zeta` | `Which evidence ID says the model server is loopback-only?` | `E-ZETA-1` |

Each candidate set contains one exact supporting statement and two semantically adjacent distractors. Candidate IDs are stable, texts are held fixed, and the candidate caller order is intentionally fixed but unreported to the model beyond its normal numbered presentation.

## Request template

```text
Use only the evidence below. Answer with exactly one evidence ID and no other text.

Question: <fixed query>

Evidence:
[<ID>] <text>
...
```

Response scoring trims whitespace and accepts only a string exactly equal to the pre-registered correct ID. Any extra text, wrong ID, missing content, reasoning content, transport error, or unavailable field projection is a failed item for that arm.

## Field input

The field arm uses the frozen L5d eight-cell projection recorded in `L5D-CALIBRATED-SEEDED-BRIDGE-REPORT.md`. It does not start or query the live field engine during this test. This isolates the already-measured mapping from sidecar latency and runtime state.

## Metric and decision tree

Let $B$ be baseline exact-score count and $F$ field-arm exact-score count over six items.

1. If either arm has a transport/configuration failure, verdict is `INVALID`.
2. If $F > B$, verdict is `SUPPORTS` for this fixed mapper on this fixed board.
3. If $F = B$, verdict is `NULL`; no claim of improvement.
4. If $F < B$, verdict is `CONTRADICTS`; reject this mapper for this board.

There is no threshold tuning, tie-breaking in favor of the field arm, repeat run, alternate board, or revised candidate text under this protocol.

## Stopping rule

Exactly 12 total requests: six baseline and six field-arm requests, serialized by item with baseline first then field. The line closes under the decision tree.

## Interpretation tiers

- **T1 measured:** exact raw responses and arm score counts on this board.
- **T2 inferred:** whether the fixed L6 candidate ordering changed exact evidence selection on this controlled task.
- **T3 speculative:** general retrieval, long-context reasoning, memory, or agent benefits. None follows from one six-item board.
