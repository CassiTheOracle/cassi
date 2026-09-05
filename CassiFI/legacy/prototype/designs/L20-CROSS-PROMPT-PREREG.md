# CassiQwen L20 cross-prompt field-output test

## Status: FROZEN BEFORE MODEL RUNS — 2026-08-22

## Purpose

Test whether the L19 field-to-output control remains mechanically active across several distinct prompt shapes, rather than only the original L18 prompt. L20 compares the current isolated experimental `residual` output seam with the same runner's `baseline` mode. The baseline still evolves the field for transport parity, but selects tokens from ordinary native Qwen logits and disables field candidate steering.

This is a mechanism/general-use readiness test for the experimental llama.cpp provider path. It is not a language-quality, semantic, safety, or production-benefit test.

## Frozen environment

- Model: `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256 `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169`.
- Runtime: the pinned local llama.cpp b10472 Vulkan DLL chain on the RX 7900 XTX.
- Each arm uses a fresh Qwen context and a fresh windowed `CassiQwenL18FieldLab` scene on loopback `127.0.0.1:7601`.
- The production `llama-server.exe`, CassiCosmos 7599 bridge, and 7273 HTTP path remain stopped and unchanged.
- Field grid, dimension, codec, retained weight, four steps per captured layer, context/batch sizes, tokenizer flags, and head parity are those recorded in L18.
- Each arm runs exactly four generated tokens unless an EOG token ends the run.
- Coupling is fixed at `0.15` for both modes.

## Prompt board

Prompt bytes are ASCII and are passed exactly as written, including the final punctuation:

| ID | Shape | Prompt |
|---|---|---|
| `rain` | short creative completion | `Write one short sentence about a rainy morning.` |
| `python` | code completion | `Complete this Python expression in one line: total = 2 +` |
| `primes` | factual continuation | `The first three prime numbers are` |
| `door` | narrative continuation | `A patient explorer opens a door and sees` |

The board order is frozen as `rain`, `python`, `primes`, `door`. For each prompt, run `baseline` first and `residual` second.

## Arm matrix

| Arm | Prompt ID | Output mode | Coupling | Max tokens |
|---|---|---|---:|---:|
| `rain-baseline` | `rain` | `baseline` | `0.15` | 4 |
| `rain-residual` | `rain` | `residual` | `0.15` | 4 |
| `python-baseline` | `python` | `baseline` | `0.15` | 4 |
| `python-residual` | `python` | `residual` | `0.15` | 4 |
| `primes-baseline` | `primes` | `baseline` | `0.15` | 4 |
| `primes-residual` | `primes` | `residual` | `0.15` | 4 |
| `door-baseline` | `door` | `baseline` | `0.15` | 4 |
| `door-residual` | `door` | `residual` | `0.15` | 4 |

## Measurements

For every receipt and event log:

1. verify model, runtime, prompt, mode, coupling, field schema, 64 layer captures, 64 field updates per event, 256-step clocks, finiteness, raw hashes, output-head parity, token positions, terminal update, and receipt/event linkage;
2. compare each baseline/residual pair's prompt token IDs and initial source field hash;
3. record the first token-index divergence, selected token IDs/pieces, field hashes, residual-vs-baseline field relative-L2 separation after divergence, and selected-logit top-one margins;
4. record whether the residual arm's first divergence is attributable to the field-augmented selection rather than an input or runtime mismatch.

The primary statistic is the number of the four prompt pairs whose generated token sequences first diverge at an index in `[0, 3]`. A pair that remains identical through four tokens counts as no divergence, even if raw logits differ.

## Frozen decision tree

- `FAIL`: any arm is not a passing L18 receipt, has wrong model/config/prompt/mode, malformed raw artifacts, non-finite values, missing layer/update records, wrong clocks, broken event linkage, or a baseline/residual prompt-token mismatch.
- `INCONCLUSIVE`: all mechanical checks pass but fewer than two prompt pairs have comparable field trajectories through their common prefix, preventing a clean paired interpretation.
- `EMERGES`: all mechanical checks pass and at least two of four prompt pairs diverge in committed token IDs within the four-token horizon, with a distinct field state after the first divergence in each diverging pair.
- `DOES NOT EMERGE`: all mechanical checks pass, paired inputs are comparable, and zero or one of four pairs diverges.

This verdict establishes cross-prompt experimental control only. It does not establish that residual mode is better than baseline, nor that it should modify ordinary user-visible output without the user choosing the experimental path.

## Stop rule

Run exactly these eight arms once, serially. Preserve every raw receipt and event log, including a failure. Do not change prompts, coupling, recurrence, horizon, ordering, or decision thresholds after the first arm. A later prompt board requires a new preregistration.
