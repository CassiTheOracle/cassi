"""Train and verify temporal prediction and causal querying in the Qi field."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from typing import Any

import torch

from cassi_field_language import (
    CassiQiTextEngine,
    qi_state_sha256,
    save_trajectory_checkpoint,
)
from cassi_grounded_language import (
    CassiGroundedEventCodec,
    GROUND_ACTIONS,
    GROUND_CHANGES,
    GROUND_HELDOUT_UTTERANCES,
    GROUND_PREDICTION_HELDOUT_QUESTION,
    GROUND_PREDICTION_TRAINING_QUESTIONS,
    GROUND_REFERENCE_HELDOUT_BINDINGS,
    GROUND_SPATIAL_HELDOUT_QUESTIONS,
    GROUND_TIME_HELDOUT_QUESTIONS,
    GROUND_TIME_TRAINING_QUESTIONS,
    GROUND_TRAINING_UTTERANCES,
    commit_grounded_action,
    make_grounded_action_command,
    observe_colored_objects,
    observe_proprioception,
    select_grounded_action,
    select_grounded_reference,
    select_spatial_relation,
    sense_binding_statement,
    sense_grounded_symbols,
    sense_spatial_query,
    spatial_relation_from_observation,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_qi_world import DeterministicQiWorld
from cassi_temporal_language import (
    change_from_observations,
    decode_proprioception,
    commit_temporal_decision,
    render_causal_explanation,
    select_cause,
    select_observed_change,
    select_order_position,
    select_predicted_change,
    select_time_target,
    sense_order_question,
    sense_prediction_prompt,
    sense_temporal_prompt,
    write_transition_register,
)

TEMPORAL_TRAINING_SCHEMA = "cassi.qi-temporal-language-training.v1"
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
TEMPORAL_COUNTERFACTUAL_SEED = 777
DEFAULT_CONFIG = CONFIG_DIR / "cassi-qi-corpus-language.json"
DEFAULT_BASE_CHECKPOINT = ARTIFACT_DIR / "cassi-qi-reference-language" / "field-state.pt"
DEFAULT_OUTPUT_DIR = ARTIFACT_DIR / "cassi-qi-temporal-language"

def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _base_counts(path: Path) -> tuple[int, int]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    return int(payload["training_episode_count"]), int(payload["training_event_count"])


def _execute(
    world: DeterministicQiWorld,
    action_id: str,
    field_state_sha256: str,
) -> tuple[bytes, bytes, str]:
    before = observe_proprioception(world)
    command = make_grounded_action_command(
        world,
        action_id,
        field_state_sha256=field_state_sha256,
    )
    acknowledgment = world.step(command)
    after = observe_proprioception(world)
    return before, after, acknowledgment.status


def _predict(
    controller: QiFieldController,
    engine: CassiQiTextEngine,
    codec: CassiGroundedEventCodec,
    state,
    observation: bytes,
    instruction: str,
):
    law = engine.law
    action_cue = sense_grounded_symbols(
        law,
        state,
        codec.instruction_symbols(observation, instruction),
    )
    action_decision = select_grounded_action(controller, law, codec, action_cue)
    action_committed = commit_grounded_action(
        law,
        codec,
        action_cue,
        action_decision,
    )
    prediction_cue = sense_prediction_prompt(
        law,
        action_committed,
        codec,
        GROUND_PREDICTION_HELDOUT_QUESTION,
        action_decision.action_id,
    )
    prediction = select_predicted_change(
        controller,
        law,
        codec,
        prediction_cue,
    )
    committed = commit_temporal_decision(law, codec, prediction_cue, prediction)
    return action_decision, prediction, committed


def train_temporal_language(
    *,
    config_path: Path = DEFAULT_CONFIG,
    base_checkpoint_path: Path = DEFAULT_BASE_CHECKPOINT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started = time.perf_counter()
    config = QiFieldConfig.from_dict(json.loads(config_path.read_text("utf-8")))
    controller = QiFieldController(config)
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=base_checkpoint_path,
        max_output_symbols=96,
    )
    law = engine.law
    codec = CassiGroundedEventCodec(engine.codec)
    state = engine.initial_state(device="cpu")
    base_memory_sha256 = law.memory_sha256(state)
    training_rows: list[dict[str, Any]] = []
    training_event_count = 0

    episode_index = 0
    for action_id in GROUND_ACTIONS:
        for utterance_index, utterance in enumerate(
            GROUND_TRAINING_UTTERANCES[action_id]
        ):
            seed = 501 + episode_index
            world = DeterministicQiWorld(
                seed=seed,
                session_id=f"temporal.prediction.train.{seed}",
            )
            before, after, _ = _execute(
                world,
                action_id,
                qi_state_sha256(controller, state),
            )
            change_id = change_from_observations(before, after)
            question = GROUND_PREDICTION_TRAINING_QUESTIONS[
                utterance_index % len(GROUND_PREDICTION_TRAINING_QUESTIONS)
            ]
            episode = codec.prediction_episode_symbols(
                before,
                utterance,
                action_id,
                question,
                change_id,
            )
            state = law.learn_sequence(state, episode, strength=1.0)
            training_event_count += len(episode)
            training_rows.append(
                {
                    "action_id": action_id,
                    "change_id": change_id,
                    "episode_type": "prediction",
                    "question": question,
                    "seed": seed,
                    "utterance": utterance,
                }
            )
            episode_index += 1
    order_world = DeterministicQiWorld(
        seed=650,
        session_id="temporal.order.train",
    )
    order_before, order_after, _ = _execute(
        order_world,
        "action.gaze-right",
        qi_state_sha256(controller, state),
    )
    before_coordinates = decode_proprioception(order_before)
    after_coordinates = decode_proprioception(order_after)
    for target_id, questions in GROUND_TIME_TRAINING_QUESTIONS.items():
        for question_index, question in enumerate(questions):
            first_state, second_state = (
                (before_coordinates, after_coordinates)
                if question_index == 0
                else (after_coordinates, before_coordinates)
            )
            episode = codec.time_target_episode_symbols(
                first_state,
                second_state,
                question,
                target_id,
            )
            state = law.learn_sequence(state, episode, strength=1.0)
            training_event_count += len(episode)
            training_rows.append(
                {
                    "episode_type": "time-target",
                    "presentation": "forward" if question_index == 0 else "reverse",
                    "question": question,
                    "target_id": target_id,
                }
            )

    state = law.reset_context(state)
    trained_memory_sha256 = law.memory_sha256(state)

    prediction_rows: list[dict[str, Any]] = []
    prediction_correct = 0
    shuffled_correct = 0
    for index, expected_action in enumerate(GROUND_ACTIONS):
        seed = 701 + index
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"temporal.prediction.heldout.{seed}",
        )
        observation = observe_proprioception(world)
        tick_before_prediction = world.logical_tick
        action_decision, prediction, committed = _predict(
            controller,
            engine,
            codec,
            law.reset_context(state),
            observation,
            GROUND_HELDOUT_UTTERANCES[expected_action],
        )
        tick_after_prediction = world.logical_tick
        before, after, _ = _execute(
            world,
            action_decision.action_id,
            qi_state_sha256(controller, committed),
        )
        expected_change = change_from_observations(before, after)
        correct = (
            action_decision.action_id == expected_action
            and prediction.answer_id == expected_change
        )
        prediction_correct += int(correct)
        shuffled_change = GROUND_CHANGES[
            (GROUND_CHANGES.index(expected_change) + 1) % len(GROUND_CHANGES)
        ]
        shuffled_correct += int(prediction.answer_id == shuffled_change)
        prediction_rows.append(
            {
                "action_id": action_decision.action_id,
                "action_margin": action_decision.margin,
                "correct": correct,
                "expected_action": expected_action,
                "expected_change": expected_change,
                "instruction": GROUND_HELDOUT_UTTERANCES[expected_action],
                "memory_unchanged": law.memory_sha256(committed)
                == trained_memory_sha256,
                "predicted_change": prediction.answer_id,
                "prediction_margin": prediction.margin,
                "seed": seed,
                "world_unchanged_before_execution": tick_before_prediction
                == tick_after_prediction,
            }
        )

    counterfactual_world = DeterministicQiWorld(
        seed=TEMPORAL_COUNTERFACTUAL_SEED,
        session_id="temporal.counterfactual",
    )
    counterfactual_snapshot = counterfactual_world.snapshot()
    counterfactual_observation = observe_proprioception(counterfactual_world)
    counterfactual_rows: list[dict[str, Any]] = []
    counterfactual_correct = 0
    for expected_action in GROUND_ACTIONS:
        action_decision, prediction, committed = _predict(
            controller,
            engine,
            codec,
            law.reset_context(state),
            counterfactual_observation,
            GROUND_HELDOUT_UTTERANCES[expected_action],
        )
        branch_world = DeterministicQiWorld(
            seed=TEMPORAL_COUNTERFACTUAL_SEED,
            session_id="temporal.counterfactual",
        )
        branch_world.restore(counterfactual_snapshot)
        before, after, _ = _execute(
            branch_world,
            action_decision.action_id,
            qi_state_sha256(controller, committed),
        )
        expected_change = change_from_observations(before, after)
        correct = (
            action_decision.action_id == expected_action
            and prediction.answer_id == expected_change
        )
        counterfactual_correct += int(correct)
        counterfactual_rows.append(
            {
                "action_id": action_decision.action_id,
                "correct": correct,
                "expected_change": expected_change,
                "predicted_change": prediction.answer_id,
                "predecessor_world_sha256": str(
                    counterfactual_snapshot["snapshot_sha256"]
                ),
            }
        )

    explanation_rows: list[dict[str, Any]] = []
    explanation_correct = 0
    for index, action_id in enumerate(GROUND_ACTIONS):
        world = DeterministicQiWorld(
            seed=801 + index,
            session_id=f"temporal.explanation.{index}",
        )
        before, after, _ = _execute(
            world,
            action_id,
            qi_state_sha256(controller, state),
        )
        transition_state = write_transition_register(
            law,
            state,
            before_observation=before,
            after_observation=after,
            action_id=action_id,
        )
        change_cue = sense_temporal_prompt(
            law,
            transition_state,
            codec,
            "observed-change",
            "what changed in the measured transition",
        )
        change_decision = select_observed_change(
            controller,
            law,
            codec,
            change_cue,
        )
        change_committed = commit_temporal_decision(
            law,
            codec,
            change_cue,
            change_decision,
        )
        cause_cue = sense_temporal_prompt(
            law,
            change_committed,
            codec,
            "cause",
            "identify the committed cause",
        )
        cause_decision = select_cause(controller, law, codec, cause_cue)
        expected_change = change_from_observations(before, after)
        expected_cause = action_id.replace("action.", "cause.")
        correct = (
            change_decision.answer_id == expected_change
            and cause_decision.answer_id == expected_cause
        )
        explanation_correct += int(correct)
        explanation_rows.append(
            {
                "action_id": action_id,
                "cause_id": cause_decision.answer_id,
                "change_id": change_decision.answer_id,
                "correct": correct,
                "explanation": render_causal_explanation(
                    change_decision,
                    cause_decision,
                ),
            }
        )

    order_rows: list[dict[str, Any]] = []
    order_correct = 0
    order_base = write_transition_register(
        law,
        state,
        before_observation=order_before,
        after_observation=order_after,
        action_id="action.gaze-right",
    )
    for target_id, question in GROUND_TIME_HELDOUT_QUESTIONS.items():
        for presentation in ("forward", "reverse"):
            first_state, second_state = (
                (before_coordinates, after_coordinates)
                if presentation == "forward"
                else (after_coordinates, before_coordinates)
            )
            cue = sense_order_question(
                law,
                order_base,
                codec,
                first_state,
                second_state,
                question,
            )
            target_decision = select_time_target(controller, law, codec, cue)
            target_committed = commit_temporal_decision(
                law,
                codec,
                cue,
                target_decision,
            )
            position_decision = select_order_position(
                controller,
                law,
                codec,
                target_committed,
                target_decision.answer_id,
            )
            expected_position = (
                "position.first"
                if (target_id == "time.before") == (presentation == "forward")
                else "position.second"
            )
            correct = (
                target_decision.answer_id == target_id
                and position_decision.answer_id == expected_position
            )
            order_correct += int(correct)
            order_rows.append(
                {
                    "correct": correct,
                    "expected_position": expected_position,
                    "expected_target": target_id,
                    "position": position_decision.answer_id,
                    "position_margin": position_decision.margin,
                    "presentation": presentation,
                    "question": question,
                    "target": target_decision.answer_id,
                    "target_margin": target_decision.margin,
                }
            )

    reference_rows: list[dict[str, Any]] = []
    reference_correct = 0
    for name, statement, expected_reference in GROUND_REFERENCE_HELDOUT_BINDINGS:
        cue = sense_binding_statement(law, law.reset_context(state), codec, statement)
        decision = select_grounded_reference(controller, law, codec, cue)
        correct = decision.reference_id == expected_reference
        reference_correct += int(correct)
        reference_rows.append(
            {
                "actual_reference": decision.reference_id,
                "correct": correct,
                "expected_reference": expected_reference,
                "name": name,
            }
        )

    spatial_rows: list[dict[str, Any]] = []
    spatial_correct = 0
    for seed in (101, 159):
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"temporal.spatial-retention.{seed}",
        )
        observation = observe_colored_objects(world)
        for family, question in GROUND_SPATIAL_HELDOUT_QUESTIONS.items():
            expected_relation = spatial_relation_from_observation(observation, family)
            cue = sense_spatial_query(
                law,
                law.reset_context(state),
                codec,
                observation,
                question,
            )
            decision = select_spatial_relation(controller, law, codec, cue)
            correct = decision.relation_id == expected_relation
            spatial_correct += int(correct)
            spatial_rows.append(
                {
                    "actual_relation": decision.relation_id,
                    "correct": correct,
                    "expected_relation": expected_relation,
                    "family": family,
                    "seed": seed,
                }
            )

    if prediction_correct != len(GROUND_ACTIONS):
        raise RuntimeError(f"held-out temporal prediction failed: {prediction_rows}")
    if shuffled_correct != 0:
        raise RuntimeError(f"shuffled temporal control scored {shuffled_correct}/5")
    if not all(row["world_unchanged_before_execution"] for row in prediction_rows):
        raise RuntimeError("temporal prediction advanced the world before execution")
    if not all(row["memory_unchanged"] for row in prediction_rows):
        raise RuntimeError("temporal prediction changed trained memory")
    if counterfactual_correct != len(GROUND_ACTIONS):
        raise RuntimeError(f"counterfactual prediction failed: {counterfactual_rows}")
    if len({row["predecessor_world_sha256"] for row in counterfactual_rows}) != 1:
        raise RuntimeError("counterfactual branches did not share one predecessor")
    if explanation_correct != len(GROUND_ACTIONS):
        raise RuntimeError(f"temporal explanation failed: {explanation_rows}")
    if order_correct != 2 * len(GROUND_TIME_HELDOUT_QUESTIONS):
        raise RuntimeError(f"temporal ordering failed: {order_rows}")
    if reference_correct != len(GROUND_REFERENCE_HELDOUT_BINDINGS):
        raise RuntimeError(f"temporal training displaced references: {reference_rows}")
    if spatial_correct != len(spatial_rows):
        raise RuntimeError(f"temporal training displaced spatial answers: {spatial_rows}")

    base_episode_count, base_event_count = _base_counts(base_checkpoint_path)
    curriculum_identity = _canonical_sha256(
        {
            "base_corpus_identity": engine.corpus_identity,
            "boundary_fingerprint": codec.fingerprint,
            "counterfactual_seed": TEMPORAL_COUNTERFACTUAL_SEED,
            "heldout_prediction_question": GROUND_PREDICTION_HELDOUT_QUESTION,
            "heldout_time_questions": dict(GROUND_TIME_HELDOUT_QUESTIONS),
            "prediction_questions": list(GROUND_PREDICTION_TRAINING_QUESTIONS),
            "prediction_cue_order": "question-then-selected-action-frame",
            "schema": TEMPORAL_TRAINING_SCHEMA,
            "time_questions": {
                target: list(questions)
                for target, questions in GROUND_TIME_TRAINING_QUESTIONS.items()
            },
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "field-state.pt"
    checkpoint_sha256 = save_trajectory_checkpoint(
        checkpoint_path,
        law=law,
        state=state,
        corpus_identity=curriculum_identity,
        training_episode_count=base_episode_count + len(training_rows),
        training_event_count=base_event_count + training_event_count,
    )
    reloaded_engine = CassiQiTextEngine(
        controller,
        checkpoint_path=checkpoint_path,
        max_output_symbols=96,
    )
    reloaded_state = reloaded_engine.initial_state(device="cpu")
    reloaded_memory_sha256 = reloaded_engine.law.memory_sha256(reloaded_state)
    roundtrip_world = DeterministicQiWorld(
        seed=901,
        session_id="temporal.checkpoint.roundtrip",
    )
    roundtrip_action, roundtrip_prediction, roundtrip_committed = _predict(
        controller,
        reloaded_engine,
        codec,
        reloaded_engine.law.reset_context(reloaded_state),
        observe_proprioception(roundtrip_world),
        GROUND_HELDOUT_UTTERANCES["action.gaze-left"],
    )
    if reloaded_memory_sha256 != trained_memory_sha256:
        raise RuntimeError("serialized temporal memory did not round-trip")
    if (
        roundtrip_action.action_id != "action.gaze-left"
        or roundtrip_prediction.answer_id != "change.x-decrease"
        or reloaded_engine.law.memory_sha256(roundtrip_committed)
        != trained_memory_sha256
    ):
        raise RuntimeError("serialized temporal checkpoint consumer failed")
    receipt: dict[str, Any] = {
        "base": {
            "checkpoint_path": str(base_checkpoint_path.resolve()),
            "memory_sha256": base_memory_sha256,
        },
        "boundary_fingerprint": codec.fingerprint,
        "checkpoint": {
            "memory_event_capacity": config.scale_count * law.width,
            "memory_event_count": law.memory_event_count(state),
            "memory_sha256": trained_memory_sha256,
            "path": str(checkpoint_path.resolve()),
            "sha256": checkpoint_sha256,
            "shape": list(state.field.shape),
            "tensor_count": 1,
        },
        "counterfactual": {
            "accuracy": counterfactual_correct / len(GROUND_ACTIONS),
            "correct": counterfactual_correct,
            "episodes": counterfactual_rows,
            "total": len(GROUND_ACTIONS),
        },
        "curriculum_identity": curriculum_identity,
        "explanation": {
            "accuracy": explanation_correct / len(GROUND_ACTIONS),
            "correct": explanation_correct,
            "episodes": explanation_rows,
            "total": len(GROUND_ACTIONS),
        },
        "ordering": {
            "accuracy": order_correct / len(order_rows),
            "correct": order_correct,
            "episodes": order_rows,
            "total": len(order_rows),
        },
        "prediction": {
            "accuracy": prediction_correct / len(GROUND_ACTIONS),
            "correct": prediction_correct,
            "episodes": prediction_rows,
            "shuffled_accuracy": shuffled_correct / len(GROUND_ACTIONS),
            "shuffled_correct": shuffled_correct,
            "total": len(GROUND_ACTIONS),
        },
        "reference_retention": {
            "accuracy": reference_correct / len(reference_rows),
            "correct": reference_correct,
            "episodes": reference_rows,
            "total": len(reference_rows),
        },
        "roundtrip": {
            "action_id": roundtrip_action.action_id,
            "memory_unchanged": reloaded_engine.law.memory_sha256(
                roundtrip_committed
            )
            == trained_memory_sha256,
            "memory_verified": reloaded_memory_sha256 == trained_memory_sha256,
            "predicted_change": roundtrip_prediction.answer_id,
        },
        "schema": TEMPORAL_TRAINING_SCHEMA,
        "spatial_retention": {
            "accuracy": spatial_correct / len(spatial_rows),
            "correct": spatial_correct,
            "episodes": spatial_rows,
            "total": len(spatial_rows),
        },
        "status": "PASS",
        "timing_seconds": time.perf_counter() - started,
        "training": {
            "episode_count": len(training_rows),
            "episodes": training_rows,
            "event_count": training_event_count,
        },
    }
    _atomic_json(output_dir / "training-receipt.json", receipt)
    return receipt




def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--base-checkpoint",
        type=Path,
        default=DEFAULT_BASE_CHECKPOINT,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    receipt = train_temporal_language(
        config_path=arguments.config,
        base_checkpoint_path=arguments.base_checkpoint,
        output_dir=arguments.output_dir,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
