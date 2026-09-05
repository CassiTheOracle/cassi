# CassiQwen L3 — Field Shadow Bridge Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Scope

This protocol adds a local, default-off adapter that can observe the existing Cassi mind-engine TCP bridge at `127.0.0.1:7599`. It does not modify Qwen requests, model weights, prompts, logits, sampling, KV cache, llama.cpp configuration, MnemicField, or the two-fluid solver.

The field engine is an external optional sidecar. A missing, malformed, timed-out, or non-finite field response must be represented as an unavailable observation. It must never prevent the original local-model path from proceeding.

## Question

Can CassiQwen acquire a bounded, deterministic projection observation from the live two-fluid field without changing the language-model completion path?

## Fixed bridge contract

The adapter communicates using newline-delimited JSON over one TCP connection per operation:

```text
{"cmd":"ping"}
{"cmd":"state"}
{"cmd":"project","k":8}
```

For a valid `project` response, the adapter accepts at most eight cells. Each accepted cell must contain finite numeric `x`, `y`, `z`, `ey`, `ei`, and non-negative finite `q`. It preserves server order, which the mind engine defines as descending `q` with stable flat-index tie-breaking.

The adapter does not send `clear`, `deposit`, `step`, `readout`, or `snapshot`. It performs no write operation.

## Fixed adapter behavior

- Default configuration: disabled; no network connection is attempted.
- Enabled configuration: query `ping`, then `state`, then `project k=8` serially.
- Per-command timeout: 2,000 ms.
- Any unavailable/malformed/timeout/non-finite response produces `available: false` and a descriptive `reason`.
- A successful observation includes only the bridge step, time, state scalars, and the bounded eight-cell projection.
- The adapter does not interpret $q$, $E_Y$, $E_I$, or $ε^2$ as truth, confidence, factuality, safety, or a direct language-model control signal.

## L3 verification board

### Unit-level checks

1. Disabled configuration does not open a socket.
2. A valid scripted bridge response yields a bounded successful observation.
3. Projection cells preserve their given ordering and values.
4. A connection refusal produces `available: false`, not a thrown completion-path exception.
5. A malformed JSON line produces `available: false`.
6. A finite-state response paired with a non-finite projection coordinate or `q` produces `available: false`.
7. The adapter sends only the three allowed read commands in their stated order.
8. Timeout produces `available: false`.

### Live smoke observation

If the existing windowed mind-engine sidecar is available on port 7599, execute exactly one enabled observation with `k=8` and record:

- connectivity outcome;
- returned `step` and `t`;
- cell count;
- whether all accepted values are finite;
- first cell `q` and last cell `q`.

This smoke does not start, clear, deposit into, step, or otherwise change the field. If the sidecar is unavailable, the live portion is `UNAVAILABLE`, not a reason to alter the adapter or retry.

## Decision tree

1. If all unit-level checks pass and the live observation succeeds with 1–8 finite cells, verdict is `PASS`.
2. If all unit-level checks pass but no sidecar is listening, verdict is `PASS — LIVE UNAVAILABLE`; the bridge remains default-off and no completion behavior changes.
3. If any unit-level check fails, verdict is `FAIL`; the adapter is not adopted.
4. If a live observation returns malformed or non-finite data, verdict is `FAIL`; no recovery/tuning run occurs under this protocol.

## Stopping rule

One unit-test run and at most one live read-only observation. No network, PDE, model, or prompt parameter changes are allowed under this protocol.

## Interpretation tiers

- **T1 measured:** adapter behavior, request order, fallback result, and any one live projection response.
- **T2 inferred:** the adapter is technically capable of supplying a future shadow-only signal.
- **T3 speculative:** that the projection can improve retrieval, reasoning, response quality, or agent behavior. This protocol cannot establish it.

## Terminal contract

This protocol concludes at `PASS`, `PASS — LIVE UNAVAILABLE`, or `FAIL`. The next line, if opened, must freeze a separate field-vs-baseline evaluation where only one intervention varies.
