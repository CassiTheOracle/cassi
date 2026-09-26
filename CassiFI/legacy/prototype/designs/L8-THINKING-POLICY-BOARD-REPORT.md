# CassiQwen L8 — Thinking Policy Capability Board Report

## Status: INVALID—2026-08-18

## Protocol result

`L8-THINKING-POLICY-BOARD-PREREG.md` began its fixed 12-request board but the managed local Qwen service exited during the third item. The recorded run therefore has 4 completed requests and 8 `fetch failed` transport failures.

The completed paired observations were:

| Item | Fast | Deliberate |
|---|---|---|
| `logic_chain` | pass; 3 completion tokens | pass; 34 completion tokens including reasoning content |
| `modular_arithmetic` | pass; 2 completion tokens | pass; 98 completion tokens including reasoning content |

The remaining four item pairs were not served after the process exit.

## Terminal verdict

**INVALID.** The protocol states that any transport/configuration failure makes the board invalid. It cannot be used to claim a speed, cost, or quality comparison.

## Recorded observation

The two completed deliberate calls show that thinking mode returns explicit `reasoning_content` and substantially more completion tokens than fast mode for these simple items. This is an incomplete observation only, not a benchmark conclusion.

## Successor boundary

A successor must restore and health-check the local service first, then use a fresh pre-registration. It must not reuse the incomplete L8 board as a score record or retry it under the same protocol.
