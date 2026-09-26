# CassiQwen L10 — Action Arbitration Gate Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Question

Do two-fluid field dynamics over the L9 semantic candidate deposits improve action selection on a fixed operational board relative to a direct scalar-score baseline and a no-evolution field control?

This gate is offline. It does not call Qwen, tools, the network, or a live Godot engine. It uses a deterministic scalar surrogate for the declared Yang/Yin relationship so the controller comparison is reproducible before GPU integration.

## Board

Each item contains one candidate for each role: `answer`, `retrieve`, `clarify`, `think`, `tool`, `abstain`, and `stop`. Features are normalized and fixed in the implementation. The board contains 21 items: three each for the seven correct action classes.

The feature construction is deliberately operational:

- answer cases: high support/alignment, low missing/conflict/risk;
- retrieve cases: high missing information and high retrieval availability encoded through its support/alignment;
- clarify cases: high ambiguity/missing information and low answer support;
- think cases: high internal support/urgency with moderate conflict but no external missing data;
- tool cases: high tool support/alignment for deterministic computation;
- abstain cases: high contradiction/risk with no sufficiently supported action;
- stop cases: high completion alignment with low remaining pressure.

No candidate text is used. No lexical or Qwen-derived signal is present.

## Fixed controllers

### Scalar baseline

For candidate $i$:

\[
S_i=c_{Y,i}-c_{I,i},
\]

where $c_Y,c_I$ are exactly L9 outputs. Choose maximum $S_i$, breaking ties by canonical role order.

### No-evolution control

Use the same initial candidate states and choose maximum $c_Y-c_I$. This must be byte-equivalent to the scalar baseline.

### Field controller

For five synchronous steps, update each candidate pool:

\[
Y_i^{t+1}=\mathrm{clip}\left(Y_i^t+0.20\sum_{j\ne i}W_{ij}(Y_j^t-I_j^t)-0.08Y_i^t\right),
\]

\[
I_i^{t+1}=\mathrm{clip}\left(I_i^t+0.20\sum_{j\ne i}W_{ij}(I_j^t-Y_j^t)-0.08I_i^t\right),
\]

with $\mathrm{clip}(v)=\min(1,\max(0,v))$.

The symmetric role-coupling matrix $W$ is fixed by action semantics:

- `answer` inhibits `retrieve`, `clarify`, `abstain` at $-0.25$;
- `retrieve` supports `answer` at $+0.30$ and inhibits `stop` at $-0.20$;
- `clarify` inhibits `answer` at $-0.35$ and `stop` at $-0.20$;
- `think` supports `answer` at $+0.15$ and inhibits `stop` at $-0.15$;
- `tool` supports `answer` at $+0.20$ and inhibits `stop` at $-0.20$;
- `abstain` inhibits `answer` at $-0.35$ and `stop` at $-0.25$;
- all unspecified couplings are zero.

Final field score:

\[
F_i=Y_i^5-I_i^5.
\]

Choose maximum $F_i$, canonical role tie-break.

## Scoring and decision tree

Let $A_S$ be scalar exact accuracy, $A_N$ no-evolution exact accuracy, and $A_F$ field exact accuracy over 21 items.

1. If $A_S\ne A_N$, verdict `INVALID`; the no-evolution control is broken.
2. If any controller emits non-finite/out-of-range state, verdict `INVALID`.
3. If $A_F>A_S$, verdict `SUPPORTS`.
4. If $A_F=A_S$, verdict `NULL`.
5. If $A_F<A_S$, verdict `CONTRADICTS`.

There are no parameter sweeps, board changes, threshold changes, or retries. A future MLP/GRU comparison is a separate successor protocol, not a post-hoc addition.
