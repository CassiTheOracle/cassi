# CassiQwen L27 longer-generation field-output comparison

## Status: FROZEN BEFORE MODEL RUNS — 2026-08-22

## Purpose

Test whether the isolated L18 provider-facing field-output seam produces a longer committed-token trajectory difference than the four-token L20 board. This is a mechanical control experiment only; it does not test language quality, semantic usefulness, safety, or production benefit.

## Frozen environment

- Model: `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256 `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169`.
- Provider: `cassi_persistent_provider.py` on loopback port `8081`, with student mode off and teacher policy `always`.
- Field lab: direct-child `CassiQwenL18FieldLab` on loopback port `7601`.
- Coupling: provider default `0.15`.
- Output modes: one fresh `baseline` session and one fresh `residual` session.
- Prompt bytes, request order, model ID, context/batch sizes, and maximum output length are fixed by the runner.
- Maximum generation: 16 committed tokens per arm unless an EOG token ends the arm.

## Measurements

For each arm, retain the complete provider JSON response and record:

1. prompt-token count, output mode, model identity, head parity, completion length, terminal field step, and field hash;
2. per-token selected IDs/pieces, field steps/hashes, trace IDs, and compact teacher receipts;
3. the first committed-token divergence, total differing positions, common-prefix length, and whether terminal field hashes differ.

The verifier checks the field clock at 256 steps per committed output event plus one terminal event, sequential event indices, finite receipts, and complete trace linkage.

## Frozen decision tree

- `FAIL`: either arm lacks a valid L18/provider receipt, has mismatched prompt/model/configuration, malformed event clocks, missing traces, or non-finite fields.
- `EMERGES`: mechanical checks pass, the baseline/residual committed token sequences diverge within the 16-token horizon, and their terminal field hashes differ.
- `DOES NOT EMERGE`: mechanical checks pass and no committed-token divergence occurs in the horizon.
- `INCONCLUSIVE`: reserved for a mechanically valid board whose terminal field state cannot be compared.

This verdict addresses longer-horizon mechanical control only. It does not authorize quality claims or changes to ordinary 7599/7273 behavior.

## Stop rule

Run exactly the two fresh arms once, baseline first and residual second. Do not alter the prompt, coupling, horizon, provider flags, or decision thresholds after the first arm. Stop the provider and field lab after raw responses and verification are written.
