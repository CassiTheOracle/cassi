# CassiQwen L19 output control surface

## Status: AMENDED AND FROZEN BEFORE MODEL RUNS — 2026-08-22

## Purpose

Measure whether the isolated L18 field-output residual seam produces a reproducible, quantitatively predicted change in Qwen's selected token when only its declared coupling strength changes. L19 measures a control surface of the frozen output head. It does not measure language quality, semantic benefit, truth, or suitability for the operational Qwen path.

## Frozen source and environment

- Source receipt: `CassiFI/_diag/l18-field-output-loop/l18-first.receipt.json` and its linked JSONL event log.
- Model: `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256 `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169`.
- Prompt, runtime dimensions, batch sizes, grid, codec, retained field weight, four PDE steps per layer, and isolated loopback L18 lab remain those recorded by L18.
- `llama-server.exe` stays stopped. Each arm uses a fresh windowed L18 lab scene, reset to byte-zero, with its direct child field engine bridge-disabled.
- The model's weights, ordinary decode path, production HTTP service, and 7599 mind-engine path remain unchanged.

## Coupling derivation

Before any L19 model arm, `analyze_l18_output_control_surface.py` read the frozen L18 receipt and wrote `CassiFI/_diag/l19-output-control-surface/l19-manifest.json`, SHA-256 `82818986c54a512a9c04b640564210f38a03b8128157e5faa926703a31798fe5`.

For each recorded L18 output event, let `F` be its field-only output logits and let `R_0.15` be its field-augmented logits at L18's coupling `0.15`. The script reconstructs the direct output-head baseline:

```text
B = R_0.15 - 0.15 F
```

For the `B` argmax token `i`, it calculates the first positive crossover:

```text
g* = min_j (B_i - B_j) / (F_j - F_i), for F_j > F_i and g* > 0
```

The first L18 output event has no positive crossover: its direct baseline and field-only logits share token `1396` as their argmax. The earliest positive crossover occurs at output event index `1`, after the common first committed token. The frozen control values are:

| Item | Value |
|---|---:|
| Control event index | `1` |
| Control-event field SHA-256 | `0136de07fdcc579ec94107a28f38ed02fefd22d5eb11451419e89d2692c5a525` |
| Baseline control token | `33700` |
| First crossover candidate | `4330` |
| `g*` | `0.2813035510306464` |
| Pre-crossover coupling | `0.26723837347911406` |
| Post-crossover coupling | `0.2953687285821788` |

The manifest freezes these six sequential arms:

| Arm | Coupling | Generated-token limit |
|---|---:|---:|
| `threshold-zero` | `0.0` | 2 |
| `threshold-reference` | `0.15` | 2 |
| `threshold-pre` | `0.26723837347911406` | 2 |
| `threshold-post` | `0.2953687285821788` | 2 |
| `trajectory-zero` | `0.0` | 4 |
| `trajectory-post` | `0.2953687285821788` | 4 |

The manifest records the source hashes, numerical crossover, each arm coupling, and the direct-head predicted control-event ranking. It is immutable evidence for the subsequent six arms. No parameter or prompt adjustment is permitted after it is written.

## Measurements

For every receipt and JSONL event, record:

1. L18 raw float32/hash/finiteness contract and all 64 field updates for each source trajectory;
2. every pre-control source selection and terminal EY/EI hash, which must match across fresh arms so the control-event input field is the same;
3. the control event's selected token, selected-logit top-16, top-one margin, and manifest-predicted direct-head rank at that arm's coupling;
4. for the two four-token arms, the generated token IDs, first divergent index, and first post-divergence field EY/EI hash difference;
5. field-memory retrieval records and the planner's empty external-action list.

## Decision tree

- `FAIL`: any arm cannot complete the mechanical L18 contract, has a malformed receipt/event linkage, non-finite value, wrong model identity, wrong coupling, non-byte-zero initial field, a pre-control source selection different from the frozen prefix, or a pre-control field state that differs across fresh arms.
- `INCONCLUSIVE`: all mechanical checks pass, but the direct-head arithmetic cannot predict the stored control-event ranking within its recorded float32 evidence.
- `EMERGES`: all checks pass; `threshold-zero` and `threshold-pre` retain control token `33700`; `threshold-post` selects the frozen predicted post-crossover token `4330`; and the `trajectory-zero` and `trajectory-post` sequences diverge at control event index `1` with different subsequent field state hashes.
- `DOES NOT EMERGE`: all checks pass but the declared post-crossover arm does not produce the frozen token or trajectory distinction.

The verdict concerns reproducible field-to-output control only. It is not an adoption decision and does not imply a quality or semantic advantage.

## Stop rule

Run exactly the six manifest arms once, serially. Preserve every raw receipt, including a failed arm. Do not rerun, widen the coupling ladder, change the prompt, or change recurrence settings within L19. A later experiment requires a new preregistration.
