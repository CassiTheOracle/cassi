# CassiQwen L8 — Thinking Policy Capability Board Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Question

On a fixed local-Qwen reasoning board, what are the measured exact-score and token-cost differences between fast completions with thinking disabled and deliberate completions with thinking enabled?

This is a capability receipt, not a field-intervention experiment. It establishes whether there is an observable policy tradeoff worth regulating later.

## Fixed arms

Both arms use the same frozen Qwen artifact, llama.cpp server, model ID, one user message, `temperature: 0`, `stream: false`, serial execution, and exact final-answer scoring.

| Arm | `enable_thinking` | `max_tokens` |
|---|---:|---:|
| `fast` | false | 64 |
| `deliberate` | true | 256 |

The deliberate arm records both `reasoning_content` and final `content` separately. A response with no final string content is a failed item regardless of any reasoning text.

## Fixed board

Each prompt requires one exact final answer and explicitly requests only that final answer.

| ID | Prompt | Expected final content |
|---|---|---|
| `logic_chain` | `Nora is older than Ivo. Ivo is older than Pia. Who is youngest? Reply with only the name.` | `Pia` |
| `modular_arithmetic` | `What is the remainder when 7 to the power of 4 is divided by 10? Reply with only the integer.` | `1` |
| `syllogism` | `All maps are tools. Some tools are blue. Does it follow that some maps are blue? Reply with only Yes or No.` | `No` |
| `sequence` | `Complete the sequence: 2, 6, 12, 20, 30, ?. Reply with only the integer.` | `42` |
| `constraint_count` | `A box contains 3 red balls, 4 blue balls, and 5 green balls. How many balls are not blue? Reply with only the integer.` | `8` |
| `conditional_logic` | `If the alarm is armed, the light is on. The light is off. What follows about the alarm? Reply with only: armed, not armed, or unknown.` | `not armed` |

## Metrics

For each item and arm record final exact pass/fail, response content, reasoning content, `usage`, server timings, and client wall time.

Aggregate:

- exact score / 6;
- total completion tokens / 6 requests;
- median generated-token throughput;
- median client wall time;
- deliberate-minus-fast exact score;
- deliberate-minus-fast completion-token cost.

No semantic score or subjective judgment is used.

## Decision tree

1. A transport/configuration failure in either arm: `INVALID`.
2. If deliberate exact score exceeds fast exact score: `DELIBERATE-QUALITY-GAIN`.
3. If scores tie and deliberate total completion-token cost is greater: `FAST-PARETO` for this board.
4. If scores tie and deliberate cost is not greater: `TIE`.
5. If deliberate score is lower: `DELIBERATE-REGRESSION`.

The verdict describes only this board and must not be presented as a general reasoning claim.

## Stopping rule

Exactly 12 requests: for each item, fast arm first and deliberate arm second. No retry, prompt change, token-budget change, or alternative board.

## Future field boundary

A later field-policy gate may use this board only if it can pre-register an independent mapping from bounded field observation to the policy choice. It may not use L8 results to tune such a mapping after the fact.
