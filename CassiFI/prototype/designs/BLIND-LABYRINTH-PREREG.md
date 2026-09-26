# CassiFI Blind Labyrinth 300-turn exam

## Status: FROZEN BEFORE FIRST RUN

This preregistration is frozen before the first run. It defines one deterministic
300-turn exam from the constants below and one seed, not a 300-row prompt table.
A runner may materialize receipts but cannot alter this algorithm, constants,
seed, thresholds, checkpoint, or stopping rule. Every exam prompt, name,
schedule, and answer key is excluded from route/goal training examples. The
generic route checkpoint is built and frozen before the first exam turn; the
main exam itself runs exactly once.

## API and ownership

```python
CassiFieldAgent.turn(text: str, *, consolidate: bool = False) -> CassiFieldAgentTurn
```

The harness invokes only `agent.turn(prompt)`: one positional raw UTF-8 string,
never the optional keyword, a category, operation, slots, parsed name, expected
answer, or oracle hint. It never calls lower-level action/relation/temporal/
reference/parser/router/goal methods. Explicit binding, correction, and goal
text may internally consolidate; the receipt reports that effective decision,
not a caller argument.

The route is selected by a field-owned boundary from `QiFieldState.field`; fixed
slot extraction/rendering may follow that route. Host lexical/category routing,
learned side state, embeddings, neural heads, conventional model, Qwen
fallback, pending-goal object, replay buffer, optimizer, and side memory are
forbidden. The sole adaptive persistent object is exactly
`QiFieldState.field[S,9M,B]`. Every receipt states:

```text
adaptive_persistent_state = "QiFieldState.field[S,9M,B] only"
```

`CassiFieldAgentTurn` exposes `route_id`, `reply`, schema identity,
`abstained`/`reason`, applicable committed `action`, `relation`, `reference`,
`temporal`, and `goal` outputs (others null), state/memory before and after
hashes, world before and after hashes, `field_ownership`, and
`effective_consolidate`.

## Frozen environment

| Item | Frozen value |
|---|---|
| protocol | `cassi.blind-labyrinth.v1` |
| seed | `20260829` |
| world/session | `731` / `blind-labyrinth.20260829` |
| execution | CPU, deterministic, one torch thread |
| config | `configs/cassi-qi-corpus-language.json` |
| canonical base checkpoint | `artifacts/cassi-qi-temporal-language/field-state.pt` |
| frozen exam checkpoint | `artifacts/cassi-qi-discourse-language/field-state.pt` |
| checkpoint builder | `training/train_cassi_discourse_language.py` |
| runner | `verification/run_blind_labyrinth.py` |
| verifier | `verification/verify_blind_labyrinth.py` |
| artifacts | `_diag/blind-labyrinth/{transcript.txt,schedule.json,oracle.json,receipt.json}` |
| report | `designs/BLIND-LABYRINTH-REPORT.md` |

The frozen exam checkpoint is derived once from the canonical base checkpoint
using only the generic route examples in `cassi_discourse_language.py`; its
builder must obtain 100% exact route accuracy on the disjoint development
validation set before saving. Neither the six names nor any prompt bank in this
document may enter the builder, its examples, or its validation. Both
checkpoints and the config are read-only during the exam; their schema/tensor
digests are recorded before turn 1 and must never change. Agent and oracle
independently construct `DeterministicQiWorld(seed=731,
session_id="blind-labyrinth.20260829")`. The runner/verifier paths are reserved
consumers and may be absent at this freeze; a run is blocked until supplied,
never amended afterward.

## Source constants and held-out material

Read-only source constants from `cassi_grounded_language.py` and
`cassi_temporal_language.py` are:

```text
GROUND_ACTIONS = ("action.gaze-left", "action.gaze-right", "action.gaze-up",
                  "action.gaze-down", "action.hold")
GROUND_RELATIONS = ("relation.left", "relation.right", "relation.above",
                    "relation.below", "relation.near", "relation.far")
GROUND_RELATION_FAMILIES = {horizontal:(left,right), vertical:(above,below),
                            distance:(near,far)}
GROUND_CHANGES = ("change.x-decrease", "change.x-increase", "change.y-increase",
                  "change.y-decrease", "change.none")
GROUND_CAUSES = ("cause.gaze-left", "cause.gaze-right", "cause.gaze-up",
                 "cause.gaze-down", "cause.hold")
GROUND_TIME_TARGETS = ("time.before", "time.after")
GROUND_ORDER_POSITIONS = ("position.first", "position.second")
GROUND_OBJECT_COLORS = ("red", "blue", "green")
```

Exactly six unseen names are:

```text
HELDOUT_NAMES = ("Juniper", "Kestrel", "Lumen", "Nix", "Opal", "Quill")
HELDOUT_BINDINGS = {Juniper:red, Kestrel:blue, Lumen:green, Nix:red,
                    Opal:blue, Quill:green}
CORRECTED_BINDINGS = {Juniper:blue, Kestrel:green, Lumen:red, Nix:green,
                      Opal:red, Quill:blue}
```

Exact held-out banks (brackets are fixed substitutions) are:

```text
ACTION_BANK[d] = ("shift your gaze toward the [d]",
  "direct your eyes to the [d] side", "move your looking direction [d]")
ACTION_BANK[hold] = ("keep your gaze exactly where it is", "make no gaze movement",
  "remain at the current gaze position")
ACTION_PREDICTION_BANK[d] = ("without moving, forecast a [d] gaze transition",
  "predict what follows if the gaze is directed [d]",
  "state the [d]-gaze outcome without acting")
ACTION_PREDICTION_BANK[hold] = ("without moving, forecast holding the gaze",
  "predict what follows if the gaze remains still",
  "state the no-movement outcome without acting")
RELATION_BANK[f] = ("determine the [f] relation of red and blue",
  "settle the [f] relation for red and blue", "identify [f] placement of red")
REFERENCE_BANK[f] = ("resolve the [f] relation from {name} to {comparison}",
  "which [f] relation involves {name} and {comparison}",
  "settle [f] placement of {name} against {comparison}")
TEMPORAL_BANK[k] = ("state the change that should follow the action",
  "what transition is expected next", "identify the [k] transition")
BINDING_BANK = ("record {name} as the name for {color}",
  "use {name} to mean {color}", "make {name} refer to {color}")
CORRECTION_BANK = ("correct the reference: {name} means {color}",
  "revise {name} so it denotes {color}",
  "replace the old reference for {name} with {color}")
NEUTRAL_BANK = ("acknowledge the current field without changing the world",
  "inspect the present field without an action", "observe without committing")
GOAL_BANK = ("store this deferred mission: {a}, then {b}, then {c}",
  "remember this three-step order: {a}; {b}; {c}",
  "defer these actions until after restart: {a}, {b}, {c}")
```

No bank item or name is training material.

## Generated schedule

All bytes are UTF-8. The only PRF is:

```python
def prf(tag, *parts):
    p = "BLIND-LABYRINTH/v1|20260829|" + tag + "|" + "|".join(map(str, parts))
    return int.from_bytes(sha256(p.encode("utf-8")).digest()[:8], "big")
```

Start `nonce=0`. Fisher–Yates uses
`j=prf("shuffle",phase,nonce,i)%(i+1)` while descending `i` from final index
to 1. No runtime PRNG, clock, OS entropy, or hash randomization is allowed.
Operation counts are:

| Operation | Count |
|---|---:|
| binding | 6 |
| binding-correction | 6 |
| action-prediction | 24 |
| action-execution | 24 |
| generic-relation | 30 |
| named-relation | 30 |
| pronoun-relation | 18 |
| temporal-prediction | 24 |
| temporal-observed-change | 18 |
| temporal-cause | 18 |
| temporal-order | 18 |
| temporal-interference | 18 |
| delayed-reference | 18 |
| delayed-prediction | 18 |
| ambiguity-abstention | 5 |
| neutral-field-inference | 25 |
| **total** | **300** |

Vectors use that row order and each phase is exactly 50:

```text
1-50:    [6,0,2,2,5,5,3,4,3,3,3,3,3,3,1,4]
51-100:  [0,0,2,2,5,5,3,4,3,3,3,3,3,3,1,10]
101-150: [0,2,6,6,5,5,3,4,3,3,3,3,3,3,1,0]
151-200: [0,2,6,6,5,5,3,4,3,3,3,3,3,3,1,0]
201-250: [0,2,4,4,5,5,3,4,3,3,3,3,3,3,1,4]
251-300: [0,0,4,4,5,5,3,4,3,3,3,3,3,3,0,7]
```

The first six records are pinned bindings in name order. The first two records
of phases 3/4/5 are pinned corrections for names 1–2/3–4/5–6. Shuffle each
remaining phase multiset with Fisher–Yates at `nonce=0`, then apply the frozen
stable obligation layout while preserving shuffled order inside every moved
queue:

1. phase-1 ambiguity case 5 is turn 7;
2. every phase places all action predictions before their FIFO-paired
   executions, its first named relation at phase offset 20, its first execution
   at offset 21, and its six delayed operations at offsets 45–50;
3. phase 4 places its hold ambiguity immediately after that first execution,
   and fixes the paired first prediction/execution action to `action.hold`;
4. if a temporal-interference record lacks a relation/neutral operation since
   the latest execution, move the next such shuffled record immediately before
   it.

For turn `t`, select bank index
`prf("bank",t,operation,0)%len(bank)` and name `prf("name",t,0)%6` subject to
availability. Start family and comparison at their PRF indices, then rotate in
frozen tuple order to the first distinct pair whose independent sensor-grid
oracle has a resolved relation. This mechanical repair may avoid a grid tie but
does not inspect the agent or answer text.
Action predictions use `GROUND_ACTIONS[prf("action",t)%5]` except the frozen
hold control; each FIFO execution copies its source prediction action. Other
action-bearing operations use the turn PRF.

The selected bank item, not the tuple, is rendered. For a temporal prediction,
append `" Candidate action: " + ACTION_BANK[action][i_action] + "."`, where
`i_action=prf("bank",t,"action-execution",0)%len(ACTION_BANK[action])`. For a
delayed prediction, render `TEMPORAL_BANK["prediction"][i]`, pair the closest eligible earlier execution, and append
`" Earlier action: " + ACTION_BANK[action_s][i_s] + "."`, with
`i_s=prf("bank",s,"action-execution",0)%len(ACTION_BANK[action_s])`; never use
the current action. A delayed reference copies the name of its closest eligible
earlier named relation. Every delayed source gap is 15–30 turns inclusive; ties
use source turn then operation ordinal. For order append exactly
`State A=tick=<decimal>;x=<signed 9-place>;y=<signed 9-place>; State B=tick=<decimal>;x=<signed 9-place>;y=<signed 9-place>.`
Every placeholder is replaced with round-half-even decimal formatting; no
label, category, route, answer, or oracle field is added.

## Phase obligations and abstention

Phase 1 introduces all names, covers relation families, starts prediction /
execution pairs, and has one ambiguity. Phase 2 has first delay windows and
interference. Phase 3 corrects Juniper/Kestrel and checks before/after. Phase 4
corrects Lumen/Nix and has a hold plus hold-temporal check. Phase 5 corrects
Opal/Quill and checks pronouns before/after. Phase 6 has no new names/corrections
and completes delay windows. A nonce is invalid unless all hold.

Exactly five ambiguity records use these fixed prompts/reasons. Case 5 is the
first ambiguity after the six bindings (active empty); cases 1–4 fill remaining
slots in PRF order. Case 3 follows a hold:

1. `shift your gaze left or right` → `ambiguous_action`.
2. `settle the relation between red and blue` → `ambiguous_relation_family`.
3. `which state came first after the gaze was held still` →
   `temporal_states_indistinguishable` (hold ordering).
4. `compare the unnamed object with blue` → `missing_referent`.
5. `is it near blue` with empty active → `missing_active_referent`.

Each requires `abstained=true`, no committed output, unchanged world/tick and
trained-memory hash, and no invented answer.

## Oracle, active register, and invariants

The independent oracle constructs its own world and derives actions from its
coordinates, relations from live object coordinates/family, references from
binding/correction and active register, temporal answers from its transition
ledger, order from presented descriptors, and mission completion from its own
ledger. It uses no static answer table, agent reply/private state, or host route,
and sends no expected operation/answer to `turn`.

A named query sets active to its resolved subject; generic relation sets active
red; temporal/prediction/neutral/correction leave it unchanged except correction
updates an active name. Pronouns use active only. After every main turn field is
finite/controller-valid and within `physics.max_mode_amplitude` (`8.0`); hashes
match canonical serialization; inference/query/abstention do not mutate world;
execution changes world exactly as oracle predicts and ticks once; ordinary
inference preserves trained-memory hash; only explicit binding/correction may
mutate reference memory; no execution internally consolidates; and checkpoint,
config, session, route ownership, and artifact hashes remain fixed.

## Persistence, controls, and deferred mission

At turns 50,100,150,200,250,300 record field bytes/hash, field-memory hash,
full world snapshot/hash, tick/counters, checkpoint/config digests, and
active/temporal registers; close and reopen the same session ID/directory and
require exact equality. Lifecycle calls are not main turns; turn 300 reopen is
mandatory before the mission.

At each boundary, disposable copies run controls excluded from the statistic.
**A/A replay** submits the same raw prompt selected by
`prf("replay",boundary)` to two copies and requires byte-identical route,
reply, typed output, abstention, and after hashes. **Targeted active-reference
A/B** selects two bound names by `prf("fork",boundary)`, establishes each
active register only through raw named prompts, then submits the same raw
pronoun relation; each must resolve to its own reference with equal independent
world. Forks never write main state or count as main turns.

After turn-300 reopen, submit one auxiliary raw goal setup, close/reopen, then
submit one auxiliary raw `begin` trigger; neither is a main turn. Choose
`mission[i]=GROUND_ACTIONS[prf("mission",i)%5]`, `i=0,1,2`. Setup may internally
consolidate and must commit exactly three ordered field-owned IDs. The trigger
must select the whole triple from `QiFieldState.field` before any side effect,
execute the three actions transactionally, advance the independent world
exactly three ticks, and report completion. A failed action restores the
pre-trigger field and world; no partial mission or fourth action is permitted.

## Statistic, decision tree, stop rule, and failure taxonomy

\[
C=\frac{\#\{\text{main turns with correct typed output, hashes, invariants, and receipt}\}}{300}.
\]

Binary decision is `FAIL` for any frozen-input/training-overlap difference,
generation/count/nonce/prompt mismatch, missing/extra turn, API/schema/
exception/timeout, host route/fallback/side memory/hidden goal, wrong typed
answer/correction/delay/temporal/goal, wrong/missing abstention, mutation,
consolidation, state bound/hash, persistence/reopen/counter, A/A, A/B,
checkpoint, mission, or artifact gate. Only if every gate passes and all 300
main turns pass is `PASS` with `C=1.0`, complete transcript, schedule/oracle
hashes, boundaries, controls, and mission receipt.

Run once from a fresh session; abort at first mechanical failure, preserve the
partial transcript and sealed failure receipt, and exit nonzero. On success do
reopen, controls, mission setup/restart/trigger, write artifacts, print `PASS`,
and stop. Never train/retrain after turn 1, mutate either frozen checkpoint,
alter schedule, or run a second main session.

Failure classes are `FROZEN_INPUT_FAILURE`, `GENERATION_FAILURE`, `API_FAILURE`,
`ROUTING_OWNERSHIP_FAILURE`, `GROUNDING_FAILURE`, `TEMPORAL_FAILURE`,
`ABSTENTION_FAILURE`, `MEMORY_OWNERSHIP_FAILURE`, `WORLD_INVARIANT_FAILURE`,
`STATE_BOUND_FAILURE`, `PERSISTENCE_FAILURE`, `CONTROL_FAILURE`,
`ARTIFACT_FAILURE`, and `ENVIRONMENT_FAILURE`: respectively frozen source /
seed/checkpoint/exclusion; generated count/payload/dependency; raw API/schema /
runtime; non-field route; wrong grounding; wrong temporal/delay; wrong abstention;
memory ownership; world mutation; invalid state; persistence; replay/fork;
artifact sealing; and uninterpretable environment. A failure is never called
`PASS`, "mostly passed", or success because an answer was close.
