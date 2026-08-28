# CassiQwen L28—field world-model identification

## Status: FROZEN BEFORE TRAINING—2026-08-22

## Purpose

L28 tests a narrow question: can a trainable input/readout around the fixed,
native-parity Cassi modal recurrence predict the next state of a deterministic,
partially observed field-consistent world on whole-seed held-out episodes?

This is an offline CPU experiment. It does not test language quality, semantic
understanding, Qwen intervention, a live Godot engine, 7599/7273 transport,
external action, authority, or an adopted general-model claim. It is a
learnability and falsification gate for the first trainable field-world-model
surface.

## Frozen operator and identity

- Differentiable recurrence: `CassiQwen/cassi_modal_torch.py`.
- Mode layout: `cassi.modal.native-linear-x-fast.v1`.
- Operator profile: `cassi.modal.recurrence.v1`.
- Field controls: retained weight `0.9`, `phi=1.618033988749895`,
  `dt=0.005`, `omega2=20.0`, coupling `1.0`, four steps per layer.
- Execution: CPU float32, one PyTorch thread, deterministic seed `20260823`.
- The recurrence has one layer and eight modes. Its inputs use the same
  `[2*M, L, T]`, `[8*M, S]`, `[M]`, and interleaved `[T]` sequence contract as
  the native operation.

The old L18 canonical Fourier codec uses a different mode ordering. It is not
an input, target, baseline, checkpoint source, or comparator in L28.

## World generator

The deterministic generator is defined only by
`CassiQwen/field_world_model.py` and is frozen as follows:

1. Each episode has 24 ordered action/observation events with six finite
   float32 values.
2. A fixed seed-derived world projector maps each event to the modal deposit
   vector. One native-parity modal recurrence update produces the world state
   after that event.
3. A fixed seed-derived readout maps the post-event field correction to a
   three-dimensional bounded next-state target.
4. The learner observes each event before predicting that post-event target.
   It never receives a later event, target, field state, projector, or readout.
5. Episode seeds are indivisible: training `0..47`, validation `48..63`, and
   test `64..79`, all under generator seed `20260822`.

This is a field-consistent system-identification board. A positive result
would establish only that the declared field inductive bias helps identify
this held-out family under the declared controls.

## Frozen learners and budget

All learners train from zero initialization with full-batch AdamW for 400
updates, learning rate `0.03`, weight decay `0.0001`, and no early stopping,
checkpoint selection, shuffled minibatches, or hyperparameter search.

| Arm | Input | Trainable mechanism | Role |
|---|---|---|---|
| `field` | ordered six-value events | trainable event-to-modal projector plus field readout around the fixed recurrence | primary arm |
| `stateless` | current six-value event only | parameter-matched feed-forward MLP | current-observation control |
| `gru` | the same ordered event history | parameter-matched GRU plus readout | generic recurrent control |
| `field-reset` | the same events | frozen trained field model with state reset before every event | state-ablation control |
| `field-shuffled` | the same events | frozen trained field model with sequence-state permutation | temporal-lineage control |

The verifier rejects an arm if its trainable parameter count falls outside
half to twice the primary arm's count. All prediction metrics are mean squared
error over all test episodes, time steps, and three target coordinates.

## Measurements

The runner records:

- source/configuration and code digests;
- generator, train, validation, test, and optimization seeds;
- complete train/validation/test episode identifiers;
- final train, validation, and held-out test MSE for every trainable arm;
- reset and shuffled-state held-out MSE for the field arm;
- parameter counts;
- maximum absolute state value and maximum `EY² + EI²` over all primary-arm
  training and test trajectories;
- finiteness, test-source overlap, and deterministic duplicate-training
  state-digest checks;
- candidate checkpoint and manifest hashes.

## Decision tree

Apply the following in order.

1. **FAIL** if a profile/mode/configuration identity differs, an episode split
   overlaps, a metric is non-finite, a state exceeds absolute value `100`, a
   state power is non-finite, parameter budgets fail, or the duplicate run has
   a different tensor-state digest.
2. **FAIL** if the checkpoint cannot be loaded with its declared profile,
   configuration, and content digest.
3. **SUPPORTS** if all mechanical checks pass and, on held-out episodes:

   \[
   \operatorname{MSE}_{field} \le 0.85\operatorname{MSE}_{stateless},
   \qquad
   \operatorname{MSE}_{field} \le 1.05\operatorname{MSE}_{gru},
   \]

   and both state ablations are at least ten percent worse:

   \[
   \operatorname{MSE}_{reset} \ge 1.10\operatorname{MSE}_{field},
   \qquad
   \operatorname{MSE}_{shuffled} \ge 1.10\operatorname{MSE}_{field}.
   \]

4. **CONTRADICTS** if all mechanical checks pass and the field arm is worse
   than both trainable baselines by more than ten percent.
5. **NULL** for any other mechanically valid result.

A `SUPPORTS` verdict is not an adoption decision. It opens only a separately
preregistered transfer board with non-field-generated environments and a
trace-to-frozen-Qwen adapter experiment.

## Stop rule and artifacts

Run one deterministic board only. Do not alter the world generator, split,
field controls, widths, optimizer, epoch count, thresholds, or decision tree
in response to intermediate metrics. Preserve the raw result and candidate
checkpoint for every terminal verdict.

- Runner: `CassiQwen/run_l28_field_world_model.py`
- Independent verifier: `CassiQwen/verify_l28_field_world_model.py`
- Raw board: `CassiQwen/_diag/l28-field-world-model/l28-board.json`
- Candidate checkpoint: `CassiQwen/_diag/l28-field-world-model/l28-field.pt`
- Report: `CassiQwen/L28-FIELD-WORLD-MODEL-REPORT.md`
