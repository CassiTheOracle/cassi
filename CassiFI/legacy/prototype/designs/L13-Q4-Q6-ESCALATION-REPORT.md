# CassiQwen L13 — Q4-to-Q6 Escalation Receipt Report

## Status: BLOCKED-PREREQUISITE—2026-08-18

## Protocol

The frozen receipt is `L13-Q4-Q6-ESCALATION-PREREG.md`; the prerequisite checker is `run-q4-q6-escalation.mjs`; raw status is `q4-q6-escalation.json`.

## Availability

| Artifact | Status |
|---|---|
| `Qwen3.8-27B-Q4_K_M.gguf` | present |
| same-model Q6 GGUF | absent |

The checker found no `Qwen3.8-27B-Q6_K.gguf` in `CassiQwen/` and did not launch a second server, download a model, or run a partial comparison.

## Terminal status

**BLOCKED-PREREQUISITE.** No Q4-versus-Q6 quality, cost, escalation, or utility claim is made.

## Required input to unblock

Provide or explicitly authorize acquisition of an exact same-model Q6/Q8 GGUF, then record its SHA-256, architecture, quantization metadata, and source before starting the two-model receipt. A different model or unverified higher-precision artifact is not an acceptable substitute.
