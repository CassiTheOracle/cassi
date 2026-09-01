# Grounded Language Understanding Plan

**Status:** Action, spatial, reference, and temporal milestones measured — 2026-08-29

## Goal

Cassi's trajectory language field retains complete byte/control episodes,
recovers exact learned continuations, grounds actions and relations in a live
world, resolves references, and predicts or explains measured transitions. The
next capability is multi-turn discourse: goals and referents must continue to
control behavior across several committed turns.

The first operational definition of language understanding is:

> An unseen utterance composition causes the field to select the correct world
> action, predict or absorb its delayed consequence, preserve that experience in
> the same field, and later report behavior from the resulting state.

Meaning is measured by action and consequence. It is not represented by a host
lexicon, parser, embedding table, vector database, reward model, or language-model
sidecar.

## Current Baseline

The adopted language runtime is `cassi_field_language.py`:

- the sole adaptive persistent object is `QiFieldState.field`;
- the common-mode half stores phase-coded corpus trajectories;
- the differential half carries live 16/32/64/128-event histories;
- the fixed boundary uses raw UTF-8 bytes and role/control events;
- the active port commits bytes through outgoing work and a negative reaction;
- terminal and provider sessions persist the same field state.

The adopted world loop is split between `cassi_field_agent.py` and
`cassi_qi_world.py`. `DeterministicQiWorld` already supplies optical, audio,
proprioceptive, action, acknowledgment, and successor-observation boundaries.
The field agent already owns its selected actions and atomically persists world
and field state.

The grounded boundary replaces digest compression with exact ordered typed
frames. Proprioceptive bytes, utterances, action frames, acknowledgments, and
successor observations therefore retain their causal order inside the field.

## First Milestone: Five Grounded Actions

The first implementation grounds language in the five actions already exposed by
`DeterministicQiWorld`:

- `action.gaze-left`;
- `action.gaze-right`;
- `action.gaze-up`;
- `action.gaze-down`;
- `action.hold`.

The milestone is intentionally narrow. It establishes the complete causal loop
before adding objects, pronouns, spatial relations, planning, or unrestricted
natural-language training.

## One-Field Architecture

The text engine and field agent use one controller, one trajectory law, one
`QiFieldState`, one checkpoint lineage, and one session lock.

```text
committed world observation
  → typed fixed boundary frame
  → user utterance bytes
  → live multiscale Qi trajectory
  → exhaustive five-action port work
  → field-owned action commitment
  → deterministic world transition
  → acknowledgment
  → successor observation
  → delayed residual-gated consolidation
  → atomic field + world checkpoint
```

No action consequence is available before commitment. A selected action becomes
causal only when the world applies it. The acknowledgment and successor
observation enter later as ordinary inbound events.

## Typed Grounded Boundary

`CassiGroundedEventCodec` uses the existing 256 byte events and four role/control
events. It adds no adaptive vocabulary and does not change the text codec.

A grounded frame contains:

1. a fixed frame prefix and version;
2. a fixed frame-kind byte;
3. an encoded payload length, or a fixed payload length declared by the frame kind;
4. the payload bytes;
5. an existing boundary control.

The first milestone needs these frame kinds:

- predecessor proprioceptive observation;
- committed action;
- world acknowledgment;
- successor proprioceptive observation.

Proprioceptive payloads remain the world's exact ordered `f32le` bytes. Action
payloads are fixed action descriptors. Acknowledgments use their declared world
status. No semantic feature extraction occurs at the boundary.

## Action Port

Every registered action is evaluated from the same predecessor field. The field
simulates the fixed action-frame event sequence without mutating memory, sums its
outgoing work, and selects the unique positive-margin winner. All five actions
are evaluated; there is no top-k shortlist, stochastic sampling, or host policy.

The selected action frame is then committed through the same negative outbound
reaction used by text emission. The world receives only this committed action.

## Delayed Residual-Gated Consolidation

Training experiences are deposited only after the world returns an acknowledgment
and successor observation. Before the outcome is admitted, the runner records the
field's action work for every candidate. The desired-action deficit is the causal
residual:

```text
residual = max(0, best competing work + required margin - desired work)
```

After the outcome exists, two ordered trajectories are written into available
common-mode field coordinates. A full-strength causal prefix reinforces
`observation → utterance → action`; the complete episode adds acknowledgment and
successor observation with bounded amplitude determined by the residual.
Already-correct predictions receive a smaller stabilizing episode deposit;
unresolved or incorrect predictions receive the larger correction.

This is a fixed local field law, not an optimizer. No residual, score table,
example index, replay buffer, or action model is persisted outside
`QiFieldState.field`.

## Curriculum

Training uses two compositional surface forms per action:

| Action | Training utterances |
|---|---|
| left | `look left`; `turn left` |
| right | `look right`; `turn right` |
| up | `look up`; `turn up` |
| down | `look down`; `turn down` |
| hold | `hold still`; `stay still` |

Held-out utterances are complete unseen compositions:

| Action | Held-out utterance |
|---|---|
| left | `turn your gaze left` |
| right | `turn your gaze right` |
| up | `raise your gaze up` |
| down | `lower your gaze down` |
| hold | `remain still` |

Each episode runs in a deterministic world with a declared seed. Training and
held-out episodes use disjoint seeds. Splits occur at whole episodes; no held-out
outcome is deposited into the trained field.

## Required Behavior

The milestone is complete when the actual runtime demonstrates:

1. all five held-out utterances select their intended actions;
2. action choice occurs before acknowledgment and successor observation;
3. the selected action changes the real deterministic world as declared;
4. the field state changes after instruction, action reaction, and consequence;
5. trained trajectory memory is unchanged during inference-only runs;
6. exact field and world state survive save, close, reopen, and the next turn;
7. deterministic replay from the same checkpoint, seed, and utterance is exact;
8. shuffled utterance/action grounding does not preserve the held-out result;
9. a live field-only intervention can alter a committed action without changing
   trained memory;
10. no Qwen, GGUF, tokenizer, neural layer, learned embedding, count table,
    optimizer, probabilistic sampler, or external policy is loaded.

The receipt reports per-utterance action work, winner, runner-up, margin,
predecessor and successor state identities, acknowledgment status, world effect,
and delayed consolidation residual.

## Implementation Map

- `cassi_field_language.py`
  - bounded trajectory strength;
  - ordered contiguous-suffix matching;
  - non-mutating candidate-sequence work.
- `cassi_grounded_language.py`
  - typed grounded and temporal boundary codec;
  - exhaustive action, relation, and reference selection;
  - delayed residual-gated causal consolidation.
- `cassi_temporal_language.py`
  - action-effect prediction, transition registers, causal ports, and ordering.
- `cassi_field_agent.py`
  - one-field language/world session;
  - committed actions, predictions, explanations, ordering, and atomic save.
- `train_cassi_grounded_language.py`
  - deterministic five-action curriculum;
  - derived grounded checkpoint and receipt;
  - held-out action evaluation.
- `train_cassi_temporal_language.py`
  - prediction, counterfactual, causal, ordering, retention, and reload gates.
- `run_cassi_field_agent.py`
  - persistent action, prediction, explanation, and ordering smoke path.
- `test_cassi_field_agent.py`
  - held-out transfer, causal controls, memory preservation, rollback, process
    reload, and persistence behavior.

Each derived checkpoint and receipt remains in its named
`_diag/cassi-qi-{grounded,spatial,reference,temporal}-language/` directory.

## Measured First-Milestone Result

The canonical derived checkpoint contains one field tensor with shape
`[4,55296,1]`. Ten causal training episodes add 930 field events to the corpus
memory; 4,290 of 12,288 common-mode event positions are occupied.

All five held-out compositions select the intended world action:

| Held-out utterance | Committed action | Margin |
|---|---|---:|
| `turn your gaze left` | `action.gaze-left` | `7.985973` |
| `turn your gaze right` | `action.gaze-right` | `10.041994` |
| `raise your gaze up` | `action.gaze-up` | `5.956003` |
| `lower your gaze down` | `action.gaze-down` | `10.029530` |
| `remain still` | `action.hold` | `12.024390` |

Held-out action accuracy is `1.0`, successor-observation prediction accuracy is
`1.0`, and cyclically shuffled utterance/action accuracy is `0.0`. Every
inference-only arm leaves trained common-mode memory unchanged. A five-turn
persistent smoke commits left, right, up, down, and hold in order; a separately
consolidating session survives close and reopen at the exact next field and
world state. Rotating only the live differential trajectory can change the
committed action while leaving trained memory unchanged.

## Second Milestone: State-Dependent Spatial Relations

This implementation adds three persistent colored objects to the reference
world boundary. The colors `red`, `blue`, and `green` are fixed sensor
identities attached to the world's first three stable object slots. Object
positions already belong to the world snapshot and therefore survive the same
save, close, and reopen path as action state.

The field receives one fixed object frame:

```text
grid size, object count,
red x-bin, red y-bin,
blue x-bin, blue y-bin,
green x-bin, green y-bin
```

Each coordinate is the direct uniform quantization of the world coordinate onto
a $5 \times 5$ sensor grid. The frame contains no relation label, distance
class, sorted order, answer hint, object embedding, or learned feature.

Three questions are grounded for the red/blue pair:

| Question family | Exhaustive field-owned answers |
|---|---|
| horizontal | `relation.left`, `relation.right` |
| vertical | `relation.above`, `relation.below` |
| distance | `relation.near`, `relation.far` |

All six fixed answer frames are evaluated from the same predecessor field.
Question trajectories first resolve the horizontal, vertical, or distance
family. The raw object coordinates occupy bounded live differential field
modes; a fixed non-adaptive resonance probe then resolves the two answers
inside the field-selected family. The winner is committed through the outbound
reaction, and a fixed boundary transducer exposes its relation word.

Training uses the eight disjoint world layouts with seeds
`1, 3, 4, 8, 15, 23, 33, 99`. Together they balance both answers in every
question family. Seeds `101` and `159` are held out. The same three unseen
paraphrases are asked in both held-out worlds, whose horizontal, vertical, and
distance answers are exact opposites.

The spatial milestone passes only when:

1. all six held-out layout/question episodes select the visible relation;
2. every answer reverses when the same question is asked in the opposite
   held-out layout;
3. substituting the opposite world's object frame makes the field follow that
   frame rather than the original label;
4. inference leaves trained common-mode memory unchanged;
5. object layout, live field state, and the next answer survive close and
   reopen exactly;
6. changing only live differential field coordinates can change an answer
   without changing trained memory;
7. all six answers remain exhaustive field-port decisions with no host relation
   policy.

### Measured spatial result

The derived spatial checkpoint adds 24 balanced relation episodes and 1,336
typed events to the five-action field. It contains 5,626 occupied trajectory
positions out of 12,288 and still contains exactly one adaptive tensor with
shape `[4,55296,1]`.

| Held-out world | Horizontal | Vertical | Distance |
|---|---|---|---|
| seed `101` | `left` (`10.000000`) | `above` (`5.000000`) | `far` (`10.000000`) |
| seed `159` | `right` (`5.000000`) | `below` (`5.000000`) | `near` (`5.000000`) |

All six unseen layout/paraphrase episodes pass. The answers reverse in every
question family between the two worlds. Replacing an episode's object frame
with the opposite world's frame makes the field follow the substituted frame
in `6/6` cases and score `0/6` against the original world's label. The prior
five-action board remains `5/5`; inference keeps common-mode memory unchanged;
spatial field/world state and the next answer survive close and reopen; and a
live differential phase intervention can change the answer without changing
trained memory.

## Third Milestone: Reference and Identity

This implementation binds temporary surface names to the three persistent
object identities inside the same field. The runtime does not retain a Python
name dictionary, entity table, alias cache, or name in session metadata.

A binding turn has two fixed boundary parts:

1. a natural binding statement such as `let Mira refer to red`;
2. an exhaustive field port over `reference.red`, `reference.blue`, and
   `reference.green`.

After the field commits the referenced color, explicit consolidation stores the
statement and compact subject/object name cues as trajectories in common-mode
field coordinates. The selected referent also occupies a three-value one-hot
register in bounded live differential coordinates.

A named spatial query has three typed inputs: subject surface text, comparison
surface text, and a relation-family question. The boundary supplies the
grammatical subject/comparison roles but never maps either surface to a world
object. Two exhaustive reference ports resolve those identities from the field.
The existing spatial port then compares the coordinates of the two
field-selected objects.

The literal pronoun `it` is a fixed boundary control. It reads the active
referent register rather than a host variable. Resolving a new subject rewrites
that register, so the same pronoun can change referent across turns while the
mapping remains entirely inside `QiFieldState.field`.

Training uses only the temporary names `Alder`, `Birch`, `Cedar`, `Dahlia`,
`Elm`, and `Fir`. `Mira`, `Orin`, and `Sable` are held out from the checkpoint.
Generic horizontal, vertical, and distance questions are trained separately
from reference identity.

The reference milestone passes only when:

1. all three held-out binding statements select their declared object;
2. a bound unseen name resolves as subject and comparison object;
3. `it` resolves to the most recently selected subject;
4. switching the active subject changes a pronoun answer when the world
   geometry requires it;
5. unknown names fail before binding rather than inheriting an arbitrary color;
6. binding is the only reference operation that changes common-mode memory;
7. unseen bindings, active pronouns, object layout, and the next answer survive
   close and reopen;
8. serialized session metadata contains counters and world state but no names
   or referent map;
9. the existing five-action and six spatial-relation boards remain unchanged.

### Measured reference result

The reference checkpoint adds 36 episodes and 1,768 typed events to the
spatial field. It contains 7,394 occupied trajectory positions out of 12,288
and still contains exactly one adaptive tensor with shape `[4,55296,1]`.

| Held-out binding | Field-selected identity | Margin |
|---|---|---:|
| `let Mira refer to red` | `reference.red` | `13.997237` |
| `let Sable refer to blue` | `reference.blue` | `15.993719` |
| `let Orin refer to green` | `reference.green` | `17.942223` |

All three names are absent from training memory before their binding turns.
Literal color resolution is `6/6` across subject and comparison roles, generic
relation-family transfer is `6/6`, unknown `Quill` fails closed before binding,
the action board remains `5/5`, and the spatial board remains `6/6`.

In held-out world seed `159`, `Mira` resolves to red and is `near` blue. The
following `it` also resolves to red and answers `near`. `Orin` resolves to green
and is `far` from blue; the next `it` resolves to green and answers `far`.
Changing only the active one-hot referent therefore changes the committed
pronoun answer while common-mode memory remains unchanged.

Two bindings, both names, the active `Orin` referent, the world layout, and the
next `far` answers survive process close and reopen. Session metadata contains
only the boundary identity, three counters, and the world snapshot; it contains
neither name nor referent mapping.

## Fourth Milestone: Temporal and Causal Language

The implementation makes committed world transitions queryable and makes
action effects predictable before execution. The field exposes 12,288
trajectory positions; the temporal decisions pass causal controls rather than
being inferred from that capacity.

Four fixed output boards are added:

| Board | Exhaustive outputs |
|---|---|
| change | `x-decrease`, `x-increase`, `y-increase`, `y-decrease`, `none` |
| cause | the five registered gaze/hold actions |
| time target | `before`, `after` |
| presented position | `first`, `second` |

An action-effect prediction starts from the current proprioceptive observation
and a natural action instruction. The existing action port selects the proposed
action without executing it. A learned temporal trajectory then commits one
change output. The world remains unchanged.

Every executed action writes its exact predecessor and successor coordinates,
the committed action one-hot value, and a validity marker into bounded live
differential field modes. Those modes survive sensing, reactions, save, close,
and reopen. They are overwritten by the next committed world transition.

An explanation uses two independent field ports over that register: one selects
the observed change and one selects the committed cause. A fixed boundary
transducer joins those field decisions into text such as
`gaze-left caused x to decrease`.

A before/after query presents the two measured states in either order. The
question trajectory selects `before` or `after`; a phase-conjugate register
probe selects `first` or `second`. The answer therefore depends on both the
language and the stored transition rather than the presentation order.

The temporal curriculum trains two action phrases per registered action and
separate before/after question trajectories. Held-out action paraphrases,
questions, world seeds, and presentation orders remain outside the checkpoint.

The temporal milestone passes only when:

1. all five held-out action instructions predict the measured successor change
   before world execution;
2. cyclically shuffled change labels score `0/5`;
3. five counterfactual actions branch from one identical predecessor and all
   five field predictions match separately executed cloned worlds;
4. every executed action yields the correct observed-change and cause outputs;
5. `before` and `after` select the correct presented state in both forward and
   reversed presentation order;
6. prediction, explanation, and ordering leave common-mode memory unchanged;
7. the last transition, its explanation, and its temporal order survive close
   and reopen;
8. changing only the live transition register can change the cause/change/order
   decisions without changing trained memory;
9. the action, spatial, and reference boards remain unchanged.

### Measured temporal result

The temporal checkpoint adds 14 episodes and 1,146 typed events to the
reference field. It contains 8,540 occupied trajectory positions out of 12,288
and still contains exactly one adaptive tensor with shape `[4,55296,1]`.

| Held-out instruction | Predicted action effect | Margin |
|---|---|---:|
| `turn your gaze left` | `x-decrease` | `37.977561` |
| `turn your gaze right` | `x-increase` | `37.946908` |
| `raise your gaze up` | `y-increase` | `21.309815` |
| `lower your gaze down` | `y-decrease` | `37.938599` |
| `remain still` | `none` | `37.977328` |

All five predictions are committed before world execution and leave both the
world and trained memory unchanged. The cyclically shuffled control scores
`0/5`. Five branches from one identical predecessor predict the five separately
executed successor changes correctly.

Executed transitions produce `5/5` observed-change decisions and `5/5` cause
decisions, including the rendered answer
`gaze-right caused x to increase`. `before` and `after` select the correct
state in all four forward/reverse presentation cases; target margins exceed
`12.0`, and the measured position margin is `0.08`.

The action, spatial, and reference retention boards remain `5/5`, `6/6`, and
`3/3`. Prediction, explanation, and ordering preserve common-mode memory. A
serialized checkpoint reload repeats the action-effect prediction; a separate
agent process reloads the last transition and reproduces its explanation and
order. Changing only live differential phase can change the predicted effect,
and changing only the transition register changes the observed change, cause,
and before/after position without changing trained memory.

## Next Language-Understanding Rungs

The next rungs are conditional on the temporal milestone continuing to hold
through the actual persistent world loop.

1. **Multi-turn discourse:** goals and references retained in field state across
   committed turns.
2. **Natural-corpus attachment:** use grounded slow-scale state to condition the
   current fast trajectory generator; prose supplies linguistic realization but
   does not define meaning by itself.

The implementation now stops at the temporal milestone. Later rungs remain
separate measured changes rather than speculative runtime scaffolding.
