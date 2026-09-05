# CassiQwen L10b — Relational Action Arbitration Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Provenance

L10 closed `NULL`: all controllers scored 21/21 because the correct candidate’s individual scalar features were dominant. L10b changes the board structure, not the L10 parameters. It tests relation-dependent cases where the correct action cannot be selected from a candidate’s own scalar score alone.

## Scope

This is an offline deterministic controller comparison. It does not call Qwen, tools, networks, Godot, or the live two-fluid engine. The field arm is a declared **graph-coupled surrogate**, not a claim about the GPU PDE. A passing surrogate result may justify a later GPU-PDE parity gate; it cannot establish a Cassi field advantage.

## Candidate roles and relation types

Each item has `answer`, `retrieve`, `clarify`, `think`, `tool`, `abstain`, and `stop` candidates, using the L9 feature encoding. It also has directed typed relations:

```text
resolves(source, target)
blocks(source, target)
supports(source, target)
```

The source candidate’s outgoing relation modifies the target only during evolution; no relation enters the scalar baseline.

## Fixed board families

The board has 24 cases, six each:

1. **Conflict resolution:** a tempting answer has the largest scalar score; retrieve resolves its contradiction and is the expected action.
2. **Ambiguity resolution:** a tempting answer has the largest scalar score; clarify resolves a missing user preference and is the expected action.
3. **Internal computation:** a tempting answer has the largest scalar score; think resolves an internal constraint conflict and is the expected action.
4. **Completion restraint:** stop has the largest scalar score; an abstain candidate blocks stop because a safety/provenance constraint remains unresolved, and abstain is expected.

The feature values and relation list are fixed in the runner. Every family includes six perturbation variants. No candidate text, label token, or Qwen-derived signal is supplied.

## Fixed controllers

### Scalar baseline

Select largest L9 score $S_i=c_{Y,i}-c_{I,i}$, canonical role tie-break. It ignores relations.

### Relation-blind recurrent baseline

Run five self-decay steps with no edges. It is expected to match scalar selection; this detects accidental edge use.

### Relation-coupled surrogate

Initialize $Y_i^0=c_{Y,i}$ and $I_i^0=c_{I,i}$. For five synchronous steps:

\[
Y_i^{t+1}=\operatorname{clip}\left(0.92Y_i^t+0.35\sum_{j\to i,\,supports}Y_j^t+0.45\sum_{j\to i,\,resolves}Y_j^t-0.45\sum_{j\to i,\,blocks}Y_j^t\right),
\]

\[
I_i^{t+1}=\operatorname{clip}\left(0.92I_i^t-0.35\sum_{j\to i,\,supports}I_j^t-0.45\sum_{j\to i,\,resolves}I_j^t+0.45\sum_{j\to i,\,blocks}I_j^t\right).
\]

All states clip to $[0,1]$. The controller selects maximum $F_i=Y_i^5-I_i^5$.

## Decision tree

Let $A_S$, $A_R$, and $A_C$ be scalar, relation-blind, and coupled exact accuracies over 24 cases.

1. If any state is non-finite/out of range, `INVALID`.
2. If $A_S\ne A_R$, `INVALID`; relation-blind control leaked relationship information.
3. If $A_C>A_S$, `SURROGATE-SUPPORTS`.
4. If $A_C=A_S$, `NULL`.
5. If $A_C<A_S$, `CONTRADICTS`.

A `SURROGATE-SUPPORTS` result does not adopt a field controller. It opens only a GPU-PDE parity test with the same deposits and relations.
