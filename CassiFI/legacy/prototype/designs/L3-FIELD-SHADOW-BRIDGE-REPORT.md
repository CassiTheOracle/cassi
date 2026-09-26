# CassiQwen L3 — Field Shadow Bridge Report

## Status: PASS — LIVE UNAVAILABLE—2026-08-18

## Protocol

This report executes `L3-FIELD-SHADOW-BRIDGE-PREREG.md`. The implementation is `cassi-field-shadow.mjs`; its only public operation is the default-off `observeCassiField()` function.

The adapter opens a loopback TCP connection only when enabled. It sends exactly these read-only commands, in order:

```text
{"cmd":"ping"}
{"cmd":"state"}
{"cmd":"project","k":8}
```

It never sends `clear`, `deposit`, `step`, `readout`, or `snapshot`. It never contacts the Qwen server.

## Contract results

| Pre-registered check | Result |
|---|---|
| Disabled configuration avoids network activity | `PASS` |
| Valid scripted bridge response becomes bounded observation | `PASS` |
| Projection ordering is preserved | `PASS` |
| Connection refusal is unavailable, not thrown | `PASS` |
| Malformed JSON is unavailable | `PASS` |
| Non-finite projection data is unavailable | `PASS` |
| Command sequence is limited and ordered | `PASS` |
| Timeout is unavailable | `PASS` |

The Node contract suite completed with 6 tests passing and 0 failures.

## Live read-only smoke

One enabled observation was attempted at the fixed default `127.0.0.1:7599` with the pre-registered two-second command timeout. The connection was refused:

```text
connect ECONNREFUSED 127.0.0.1:7599
```

No field process was started, stopped, cleared, stepped, deposited into, or otherwise modified. This is the pre-registered `LIVE UNAVAILABLE` branch, not a runtime failure of the adapter.

## Terminal verdict

**PASS — LIVE UNAVAILABLE.** The implementation fulfills the default-off, bounded, read-only bridge contract. The currently absent sidecar prevents a live projection receipt, but completion behavior remains unmodified and no retry or configuration change belongs in this closed protocol.

## Interpretation

- **T1 measured:** six contract-test outcomes and the refused live connection above.
- **T2 inferred:** when the independently launched windowed mind-engine sidecar is present, CassiQwen can safely acquire a bounded projection observation without writing to it.
- **T3 speculative:** that such an observation can improve retrieval, reasoning, or response quality. No language-model request was altered and no comparison was run.

## Next gated step

The next protocol should define a single, independently measurable shadow signal from a successful live projection and compare it against the L2 baseline. Until the live sidecar is available and that protocol is frozen, `observeCassiField()` remains an unused observation capability rather than a steering mechanism.
