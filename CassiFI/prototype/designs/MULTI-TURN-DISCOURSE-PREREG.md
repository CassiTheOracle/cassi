# CassiFI 100-turn interleaved discourse preregistration

## Status: FROZEN BEFORE RUN — 2026-08-29

## Purpose and scope

This board verifies the already-trained grounded action, spatial, reference, and
temporal ports together in one persistent `CassiFieldAgent` session. It is a
mechanical discourse-persistence experiment, not a language-quality, safety, or
model-comparison claim. The verifier is
`verification/verify_cassi_multiturn_discourse.py`; it is the only runner for
this board.

The adaptive state is exactly the live `QiFieldState.field` tensor. There is no
host lexicon, side memory, conventional model, fallback, retraining, or new
dependency in the protocol. The canonical temporal checkpoint is read-only;
per-session state and the two board receipts are written below the ignored
`_diag/cassi-qi-multiturn-discourse/` directory.

## Frozen environment

- Workspace root: the directory containing `cassi_field_agent.py`.
- Configuration: `configs/cassi-qi-corpus-language.json`.
- Canonical checkpoint: `artifacts/cassi-qi-temporal-language/field-state.pt`.
- Agent entry point: `CassiFieldAgent.open`.
- Device: CPU.
- World: `DeterministicQiWorld(seed=159, session_id="multiturn.159")`.
- Session: exactly one session, ID `multiturn.159`; all close/reopen operations
  reopen that same ID and the same per-run state directory.
- Turn unit: one successful public request/response from `bind_reference`,
  `predict_action`, `step`, `query`, `query_reference`,
  `explain_last_transition`, or `order_last_transition`. `close` and `open`
  are lifecycle boundaries, not dialogue turns.
- Action execution always passes `consolidate=False` (all executions occur
  after the three explicit bindings).
- Field bound: after every turn, the field is finite and
  `max(abs(field)) <= physics.max_mode_amplitude` (`8.0` in the frozen
  configuration); the live controller validation must pass.
- No retry, changed prompt, changed seed, changed threshold, or changed
  checkpoint is permitted after the first turn.

## Primary statistic and gates

The primary statistic is the **100-turn contract completion rate**

\[
C = \frac{\text{turns whose committed answer/action, invariants, and receipt
checks pass}}{100}.
\]

The board is `PASS` only when `C = 1.0` and every mechanical gate below passes.
There is no partial-credit or best-effort verdict: any exception, missing turn,
wrong committed answer/action/change, active-reference mismatch, world mutation
on a prediction/query, post-binding memory change during inference,
non-finite/out-of-bound field, checkpoint write/change, failed exact reopen, or
receipt/transcript write failure is `FAIL`.

The verifier derives expectations from the registered constants and the live
world rather than reproducing adaptive selection:

- action labels come from `GROUND_ACTIONS` and
  `GROUND_HELDOUT_UTTERANCES`; executed changes come from the before/after live
  proprioceptive observations through `change_from_coordinates`;
- spatial answers come from the live colored-object observation through
  `spatial_relation_from_observation` for the requested family and references;
- binding answers come from `GROUND_REFERENCE_HELDOUT_BINDINGS`;
- temporal change/cause/order answers come from the committed transition and
  registered `GROUND_CAUSES`, `GROUND_TIME_HELDOUT_QUESTIONS`, and presentation
  direction.

## Required content and controls

1. **Bindings (three, unseen names):** `Mira → reference.red`,
   `Sable → reference.blue`, and `Orin → reference.green`, using the exact
   registered statements. Each binding must change field memory and leave the
   world/tick unchanged. The memory fingerprint immediately after `Orin` is
   frozen as `post_binding_memory_sha256`.
2. **Actions:** exactly one prediction and one execution for each of the five
   registered actions: gaze-left, gaze-right, gaze-up, gaze-down, and hold.
   Each prediction must leave world and trained memory unchanged. Each
   execution must commit the expected action, have status `applied` (or
   `hold` for hold), use `consolidate=False`, and its observed change must equal
   the preceding prediction for that action.
3. **Spatial families:** generic `query` calls cover horizontal, vertical, and
   distance. They use the live seed-159 object layout and must leave world and
   trained memory unchanged.
4. **Named/pronoun references and active-register controls:**
   - At turns 4–11, `Sable` is named, then a generic red/blue spatial query is
     deliberately inserted, followed by temporal calls, then `it`; the generic
     query intentionally makes red the active subject, so `it` must resolve to
     `reference.red`, not Sable/blue.
   - At turns 26–32, `Orin` is named, then prediction, execution, explanation,
     and ordering calls occur with no generic query; all must preserve the
     active register and `it` must resolve to `reference.green`.
   - Turns 76–80 and 91–93 repeat the temporal-only retention control for Orin.
   - Every named/pronoun relation is checked against the live object
     observation with its resolved subject/comparison references.
5. **Temporal explanation:** every explanation must identify the committed last
   action, observed change, and corresponding registered cause; memory and
   world remain unchanged.
6. **Ordering:** all four combinations are present: forward-before, reverse-
   after, reverse-before, and forward-after. The target and first/second
   position are checked from the registered question and presentation.
7. **Persistence:** after turns 25, 50, 75, and 100, the verifier records the
   exact field tensor, world snapshot, trained-memory fingerprint, and counters,
   closes the agent, reopens the same session, and requires exact equality.
   Turn 100's reopen is the final persisted-reopen gate.
8. **Artifacts:** the verifier prints every meaningful prompt/response and the
   final summary, writes a human-readable transcript to
   `_diag/cassi-qi-multiturn-discourse/transcript.txt`, and writes a sealed
   canonical JSON receipt to
   `_diag/cassi-qi-multiturn-discourse/receipt.json`.

## Exact 100-turn schedule

The symbols below are only compact names for exact public calls. Every question
text is the registered constant named in the symbol definition; `H`, `V`, and
`D` mean `horizontal`, `vertical`, and `distance`.

- `B_M`, `B_S`, `B_O`:
  `bind_reference("Mira", "let Mira refer to red")`,
  `bind_reference("Sable", "let Sable refer to blue")`, and
  `bind_reference("Orin", "let Orin refer to green")` respectively.
- `P_L`, `P_R`, `P_U`, `P_DN`, `P_H`: `predict_action` with the registered
  held-out utterance for gaze-left, gaze-right, gaze-up, gaze-down, and hold,
  plus `GROUND_PREDICTION_HELDOUT_QUESTION`.
- `E_L`, `E_R`, `E_U`, `E_DN`, `E_H`: `step` with that same held-out utterance
  and `consolidate=False`.
- `Q_H`, `Q_V`, `Q_D`: `query(GROUND_SPATIAL_HELDOUT_QUESTIONS[family])`.
- `R(name, comparison, family)`: `query_reference(name, comparison,
  GROUND_REFERENCE_HELDOUT_QUESTIONS[family])`.
- `X`: `explain_last_transition()` (its two registered temporal questions are
  fixed by the public method).
- `O(target, presentation)`: `order_last_transition(
  GROUND_TIME_HELDOUT_QUESTIONS[target], presentation=presentation)`.

For `R(..., "it", ...)`, the expected subject is stated explicitly in the
rightmost column. For all other relation calls, the expected relation is the
live-world-derived relation for the named references, not a duplicated static
layout table.

| Turn | Call | Required expectation/control |
|---:|---|---|
| 1 | B_M | `reference.red`; binding changes memory |
| 2 | B_S | `reference.blue`; binding changes memory |
| 3 | B_O | `reference.green`; freeze post-binding memory |
| 4 | R(Sable, red, H) | named subject `reference.blue` |
| 5 | Q_H | generic red/blue query; active subject becomes red |
| 6 | P_L | action gaze-left; world unchanged |
| 7 | E_L | action gaze-left; observed change matches P_L |
| 8 | X | explain committed gaze-left transition |
| 9 | O(time.before, forward) | `position.first` |
| 10 | O(time.after, reverse) | `position.first` |
| 11 | R(it, blue, H) | **clobber control:** `reference.red` |
| 12 | Q_V | generic vertical family |
| 13 | P_R | action gaze-right; world unchanged |
| 14 | X | explain current last transition |
| 15 | E_R | action gaze-right; observed change matches P_R |
| 16 | O(time.before, reverse) | `position.second` |
| 17 | R(Mira, blue, D) | named subject `reference.red` |
| 18 | Q_D | generic distance family |
| 19 | P_U | action gaze-up; world unchanged |
| 20 | E_U | action gaze-up; observed change matches P_U |
| 21 | X | explain committed gaze-up transition |
| 22 | O(time.after, forward) | `position.second` |
| 23 | R(Mira, blue, V) | named subject `reference.red` |
| 24 | Q_H | generic horizontal family |
| 25 | Q_D | generic distance family; **close/reopen boundary** |
| 26 | R(Orin, blue, H) | named subject `reference.green` |
| 27 | P_DN | action gaze-down; world unchanged |
| 28 | E_DN | action gaze-down; observed change matches P_DN |
| 29 | X | explain committed gaze-down transition |
| 30 | O(time.before, forward) | `position.first` |
| 31 | O(time.after, reverse) | `position.first` |
| 32 | R(it, blue, H) | **temporal-only retention:** `reference.green` |
| 33 | Q_V | generic vertical family |
| 34 | P_H | action hold; world unchanged |
| 35 | E_H | action hold; observed change matches P_H |
| 36 | X | explain committed hold transition |
| 37 | O(time.after, forward) | `position.second` |
| 38 | R(Sable, red, V) | named subject `reference.blue` |
| 39 | Q_D | generic distance family |
| 40 | X | explain current last transition |
| 41 | O(time.before, reverse) | `position.second` |
| 42 | R(Mira, blue, H) | named subject `reference.red` |
| 43 | Q_H | generic horizontal family |
| 44 | O(time.after, forward) | `position.second` |
| 45 | R(Orin, blue, D) | named subject `reference.green` |
| 46 | Q_V | generic vertical family |
| 47 | X | explain current last transition |
| 48 | O(time.after, reverse) | `position.first` |
| 49 | Q_D | generic distance family |
| 50 | R(Sable, red, D) | named subject `reference.blue`; **close/reopen boundary** |
| 51 | R(Sable, red, D) | named subject `reference.blue` |
| 52 | Q_H | generic horizontal family |
| 53 | X | explain current last transition |
| 54 | O(time.before, forward) | `position.first` |
| 55 | Q_V | generic vertical family |
| 56 | R(Mira, blue, D) | named subject `reference.red` |
| 57 | O(time.before, reverse) | `position.second` |
| 58 | Q_D | generic distance family |
| 59 | X | explain current last transition |
| 60 | O(time.after, forward) | `position.second` |
| 61 | R(Orin, blue, V) | named subject `reference.green` |
| 62 | Q_H | generic red/blue query; active subject becomes red |
| 63 | O(time.after, reverse) | temporal call leaves active red |
| 64 | X | explain current last transition |
| 65 | R(it, blue, D) | clobbered active subject `reference.red` |
| 66 | Q_V | generic vertical family |
| 67 | O(time.before, forward) | `position.first` |
| 68 | R(Sable, red, H) | named subject `reference.blue` |
| 69 | X | explain current last transition |
| 70 | O(time.after, reverse) | `position.first` |
| 71 | Q_D | generic distance family |
| 72 | R(Mira, blue, V) | named subject `reference.red` |
| 73 | X | explain current last transition |
| 74 | O(time.before, forward) | `position.first` |
| 75 | O(time.after, reverse) | `position.first`; **close/reopen boundary** |
| 76 | R(Orin, blue, D) | named subject `reference.green` |
| 77 | X | temporal-only active retention |
| 78 | O(time.after, forward) | temporal-only active retention |
| 79 | O(time.before, reverse) | temporal-only active retention |
| 80 | R(it, blue, D) | **temporal-only retention:** `reference.green` |
| 81 | Q_H | generic horizontal family; active becomes red |
| 82 | X | temporal call leaves active red |
| 83 | R(Sable, red, V) | named subject `reference.blue` |
| 84 | O(time.before, forward) | `position.first` |
| 85 | Q_D | generic distance family |
| 86 | O(time.after, reverse) | `position.first` |
| 87 | R(Mira, blue, H) | named subject `reference.red` |
| 88 | X | explain current last transition |
| 89 | Q_V | generic vertical family |
| 90 | O(time.after, forward) | `position.second` |
| 91 | R(Orin, blue, H) | named subject `reference.green` |
| 92 | O(time.before, reverse) | temporal-only active retention |
| 93 | R(it, blue, H) | **temporal-only retention:** `reference.green` |
| 94 | Q_D | generic distance family |
| 95 | X | explain current last transition |
| 96 | R(Sable, red, D) | named subject `reference.blue` |
| 97 | O(time.before, forward) | `position.first` |
| 98 | Q_H | generic horizontal family |
| 99 | O(time.after, reverse) | `position.first` |
| 100 | X | explain current last transition; **final persisted reopen** |

Counter expectations at the declared boundaries are `(step_count,
query_count,binding_count) = (3,19,3)` after turn 25, `(5,42,3)` after turn
50, `(5,67,3)` after turn 75, and `(5,92,3)` after turn 100. The complete
schedule contains exactly five `P_*`, five `E_*`, three `B_*`, and 87 other
inference calls, for exactly 100 public request/response turns.

## Decision tree

1. `FAIL` immediately on a missing/malformed preregistration, wrong canonical
   checkpoint/configuration, wrong seed/session, schedule length mismatch,
   public-method exception, non-finite or out-of-bound field, counter mismatch,
   or any receipt/transcript write failure.
2. `FAIL` if any binding does not resolve to its registered reference, any
   prediction/execution/action change is wrong, any spatial/reference family or
   relation is wrong for the live observation, any pronoun resolves to the
   wrong active register, any explanation has the wrong action/change/cause, or
   any ordering target/position is wrong.
3. `FAIL` if a prediction/query/temporal explanation/order changes the world,
   if any inference changes the post-binding trained-memory fingerprint, if an
   execution is not `consolidate=False`, or if the canonical checkpoint digest
   changes.
4. `FAIL` if any declared close/reopen (including the final reopen) is not
   exact for field tensor values, field hash, world snapshot, memory
   fingerprint, or all three counters.
5. Otherwise report `PASS` with `C=1.0`, the complete transcript, all per-turn
   responses/checks, boundary records, and the sealed canonical JSON receipt.

## Stopping rule

Run this exact schedule once, in order, on the one fresh seed-159 session. Abort
on the first failed mechanical check, write the failing transcript/receipt, and
exit nonzero. On a successful run, perform the turn-100 persisted reopen, close
the agent, write both artifacts, print the final `PASS` summary, and stop. Do
not train, mutate, replace, or rewrite the canonical temporal checkpoint.

## V2 AMENDMENT FROZEN BEFORE RUN — 2026-08-29

The first board run is retained at
`_diag/cassi-qi-multiturn-discourse/receipt.json` with status `FAIL` after
36 completed turns. Turn 37 asked the order-position port to distinguish the
before and after states of `action.hold`. Both coordinates are identical, so
the two presented states are physically indistinguishable and the live port
correctly failed closed instead of inventing a first/second winner. This was a
probe-design error, not a changed field decision.

V2 keeps the same checkpoint, configuration, seed, field/runtime code,
thresholds, primary statistic, invariants, decision tree, and 100-turn count.
It changes only:

- run root to `_diag/cassi-qi-multiturn-discourse-v2/`;
- session ID to `multiturn.159.v2`;
- turn 37 from `O(time.after, forward)` to `P_R`;
- turn 38 from `R(Sable, red, V)` to `E_R`.

Turn 36 still tests the hold transition's causal explanation. Turns 37–38 then
predict and commit a non-degenerate rightward transition before every remaining
ordering query. All other 98 turns remain exactly as frozen in the table above.
The V2 schedule therefore contains three bindings, six predictions, six
executions (right occurs twice), and 85 other inference calls. Boundary
counter expectations are `(3,19,3)` after turn 25, `(6,41,3)` after turn 50,
`(6,66,3)` after turn 75, and `(6,91,3)` after turn 100.

Run V2 exactly once from a fresh V2 session root. Abort on its first failed
check, retain its receipt, and do not alter the protocol during that run.
