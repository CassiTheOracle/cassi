# CassiQwen L9 — Semantic Candidate Field Encoder Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Question

Can a pure deterministic encoder preserve action-candidate identity while converting explicit operational evidence features into bounded Yang/Yin deposits and fixed role geometry suitable for the existing two-fluid field engine?

This is an encoder-contract receipt. It does not run a field, Qwen, socket, controller, or action policy.

## Candidate contract

Each candidate must provide:

```ts
{
  id: string,
  kind: "answer" | "retrieve" | "clarify" | "think" | "tool" | "abstain" | "stop",
  support: number,
  goalAlignment: number,
  urgency: number,
  contradiction: number,
  missingInformation: number,
  risk: number,
  cost: number
}
```

Every feature is a finite normalized value in $[0,1]$. Candidate IDs are non-empty and unique. Exactly one candidate per action kind is allowed in this first encoder; duplicate roles fail closed rather than silently colliding in one pool.

## Fixed role geometry

The encoder uses the fixed seven-role coordinate table:

| Kind | Coordinate |
|---|---|
| `answer` | $(+0.72,0,0)$ |
| `clarify` | $(-0.72,0,0)$ |
| `retrieve` | $(0,+0.72,0)$ |
| `think` | $(0,-0.72,0)$ |
| `tool` | $(0,0,+0.72)$ |
| `stop` | $(0,0,-0.72)$ |
| `abstain` | $(0,0,0)$ |

These coordinates encode action role only. They do not encode candidate truth, textual semantics, or an asserted physical correspondence.

## Fixed channel encoding

For each candidate $i$:

\[
c_{Y,i}=\frac{support_i+goalAlignment_i+urgency_i}{3},
\]

\[
c_{I,i}=\frac{contradiction_i+missingInformation_i+risk_i+cost_i}{4}.
\]

Every deposit uses a fixed scatter width $\sigma=1.0$. The output records the source features and its generated deposit, preserving candidate ID and role.

## Default and invalid behavior

- `enabled=false` returns no deposits and `applied=false` without inspecting candidate feature values.
- Invalid input returns `applied=false`, no deposits, and a reason; it does not throw from the ordinary encoding call.
- The encoder never emits a field command.

## Verification board

1. Disabled mode returns no deposits even for malformed input.
2. Valid action candidates produce one bounded finite deposit each and preserve IDs.
3. Role coordinate table is exact.
4. Yang and Yin formulas match exact expected values.
5. Candidate input permutation yields deposits in canonical kind order with the same candidate-to-deposit association.
6. Duplicate roles, duplicate IDs, out-of-range, and non-finite feature values fail closed.
7. The all-zero candidate set produces zero channel amplitudes without changing geometry.

## Decision tree

- Any contract test failure: `FAIL`.
- All contract tests pass: `PASS`.

No field claim or action-policy claim follows from this gate.
