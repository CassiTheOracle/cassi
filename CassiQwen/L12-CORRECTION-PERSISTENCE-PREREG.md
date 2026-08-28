# CassiQwen L12 — Correction Persistence Board Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Question

Does a bounded persistent support/counterpressure state retain a later correction more reliably than simple latest-event and recency-weighted memory baselines after distractor turns?

This is an offline policy receipt. It does not call Qwen, the field engine, MnemicField storage, tools, or the network. It does not treat field magnitude as truth; source provenance and event order are explicit inputs.

## Fixed board

The board contains 18 six-event scenarios over a two-claim topic. Every scenario begins with claim `old`, receives a correction to `new`, then receives four distractor events. The final query asks for the current claim ID.

Each event is one of:

```text
assert(claim, strength, sourceQuality)
correct(old, new, strength, sourceQuality)
distractor(topic, strength)
```

The frozen runner defines six variants for each of three families:

1. **clean correction:** old is asserted once, new is corrected once, distractors follow;
2. **repeated stale mention:** old receives two additional low-quality mentions after correction;
3. **mixed provenance:** old has repeated weak provenance while new has one newer strong correction.

The ground-truth final answer is always `new`; the board tests resistance to stale repetition, not discovery of truth from text.

## Controllers

### Latest-event baseline

Return the claim named by the most recent `correct` event; retain no state beyond the event log.

### Recency-score baseline

For each claim, sum `strength × sourceQuality × 0.85^(events_since_event)`. Choose the larger score, ties choose newer event.

### Persistent correction state

Maintain per-claim Yang support $Y_i$ and Yin counterpressure $I_i$:

- `assert(i,s,q)`: $Y_i\leftarrow\operatorname{clip}(Y_i+0.30sq)$;
- `correct(old,new,s,q)`: $Y_{new}\leftarrow\operatorname{clip}(Y_{new}+0.45sq)$ and $I_{old}\leftarrow\operatorname{clip}(I_{old}+0.55sq)$;
- `distractor`: no claim deposit;
- after every event: $Y_i\leftarrow0.97Y_i$, $I_i\leftarrow0.97I_i$.

The final claim score is $P_i=Y_i-I_i$. Choose maximum $P_i$, ties choose newer event. State is bounded to $[0,1]$.

## Metrics and decision tree

Record exact final claim ID, per-scenario outcome, state finiteness/boundedness, and state after each event.

1. Any non-finite/out-of-range state: `INVALID`.
2. If latest-event baseline is not 18/18, `INVALID`; the board’s correction semantics are broken.
3. If persistent state score is greater than recency-score baseline: `PERSISTENCE-SUPPORTS`.
4. If equal: `NULL`.
5. If lower: `PERSISTENCE-REGRESSION`.

A support result is only evidence on this fixed synthetic correction board. It does not establish factual memory, source reliability, or general cognition.

## Stopping rule

One deterministic run over all 18 scenarios. No parameter sweep, event edits, or retry.
