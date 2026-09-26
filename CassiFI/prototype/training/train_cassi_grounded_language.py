"""Train and verify the five-action grounded language milestone."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
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
    GROUND_CONSOLIDATION_STRENGTH_FLOOR,
    GROUND_HELDOUT_UTTERANCES,
    GROUND_TRAINING_UTTERANCES,
    commit_grounded_action,
    consolidate_grounded_episode,
    make_grounded_action_command,
    observe_proprioception,
    select_grounded_action,
    sense_grounded_symbols,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_qi_world import DeterministicQiWorld
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR

GROUND_TRAINING_SCHEMA = "cassi.qi-grounded-language-training.v1"
DEFAULT_CONFIG = CONFIG_DIR / "cassi-qi-corpus-language.json"
DEFAULT_BASE_CHECKPOINT = ARTIFACT_DIR / "cassi-qi-corpus-language" / "field-state.pt"
DEFAULT_OUTPUT_DIR = ARTIFACT_DIR / "cassi-qi-grounded-language"


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
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _position(raw: bytes) -> tuple[float, float]:
    if len(raw) != 8:
        raise RuntimeError("proprioceptive observation is not two f32le values")
    return tuple(float(value) for value in struct.unpack("<ff", raw))


def _base_counts(path: Path) -> tuple[int, int]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    return int(payload["training_episode_count"]), int(payload["training_event_count"])


def train_grounded_language(
    *,
    config_path: Path = DEFAULT_CONFIG,
    base_checkpoint_path: Path = DEFAULT_BASE_CHECKPOINT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    training_seed_start: int = 1,
    heldout_seed_start: int = 101,
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
    seed = training_seed_start

    for desired_action in GROUND_ACTIONS:
        for utterance in GROUND_TRAINING_UTTERANCES[desired_action]:
            world = DeterministicQiWorld(
                seed=seed,
                session_id=f"grounded.train.{seed}",
            )
            observation_before = observe_proprioception(world)
            cue_state = sense_grounded_symbols(
                law,
                state,
                codec.instruction_symbols(observation_before, utterance),
            )
            prediction = select_grounded_action(controller, law, codec, cue_state)
            command = make_grounded_action_command(
                world,
                desired_action,
                field_state_sha256=prediction.state_sha256,
            )
            acknowledgment = world.step(command)
            observation_after = observe_proprioception(world)
            state, consolidation = consolidate_grounded_episode(
                law,
                codec,
                state,
                predecessor_observation=observation_before,
                utterance=utterance,
                desired_action_id=desired_action,
                acknowledgment_status=acknowledgment.status,
                successor_observation=observation_after,
                prediction=prediction,
            )
            training_event_count += consolidation.event_count
            training_rows.append(
                {
                    "acknowledgment_status": acknowledgment.status,
                    "candidate_work": dict(prediction.candidate_work),
                    "desired_action": desired_action,
                    "field_prediction_before_outcome": prediction.action_id,
                    "observation_after": list(_position(observation_after)),
                    "observation_before": list(_position(observation_before)),
                    "residual": consolidation.residual,
                    "seed": seed,
                    "trajectory_strength": consolidation.trajectory_strength,
                    "utterance": utterance,
                    "world_effect": acknowledgment.world_effect,
                }
            )
            seed += 1

    state = law.reset_context(state)
    trained_memory_sha256 = law.memory_sha256(state)
    heldout_rows: list[dict[str, Any]] = []
    heldout_correct = 0
    successor_correct = 0
    for index, expected_action in enumerate(GROUND_ACTIONS):
        utterance = GROUND_HELDOUT_UTTERANCES[expected_action]
        test_seed = heldout_seed_start + index
        world = DeterministicQiWorld(
            seed=test_seed,
            session_id=f"grounded.heldout.{test_seed}",
        )
        observation_before = observe_proprioception(world)
        cue_state = sense_grounded_symbols(
            law,
            law.reset_context(state),
            codec.instruction_symbols(observation_before, utterance),
        )
        decision = select_grounded_action(controller, law, codec, cue_state)
        committed = commit_grounded_action(law, codec, cue_state, decision)
        successor_sequences: dict[str, tuple[int, ...]] = {}
        successor_event_work: dict[str, tuple[float, ...]] = {}
        for candidate_action in GROUND_ACTIONS:
            counterfactual_world = DeterministicQiWorld(
                seed=test_seed,
                session_id=f"grounded.successor.{test_seed}.{candidate_action}",
            )
            counterfactual_command = make_grounded_action_command(
                counterfactual_world,
                candidate_action,
                field_state_sha256=qi_state_sha256(controller, committed),
            )
            counterfactual_ack = counterfactual_world.step(counterfactual_command)
            counterfactual_observation = observe_proprioception(counterfactual_world)
            sequence = codec.outcome_symbols(
                counterfactual_ack.status,
                counterfactual_observation,
            )
            successor_sequences[candidate_action] = sequence
            successor_event_work[candidate_action] = law.candidate_sequence_work(
                committed,
                sequence,
            )[1]
        sequence_length = len(next(iter(successor_sequences.values())))
        if any(len(sequence) != sequence_length for sequence in successor_sequences.values()):
            raise RuntimeError("grounded successor frames have inconsistent lengths")
        varying_positions = tuple(
            position
            for position in range(sequence_length)
            if len(
                {
                    successor_sequences[action][position]
                    for action in GROUND_ACTIONS
                }
            )
            > 1
        )
        if not varying_positions:
            raise RuntimeError("grounded successor controls contain no distinct events")
        successor_work = {
            action: sum(successor_event_work[action][position] for position in varying_positions)
            for action in GROUND_ACTIONS
        }
        predicted_successor_action = max(
            GROUND_ACTIONS,
            key=lambda action: (successor_work[action], -GROUND_ACTIONS.index(action)),
        )
        successor_correct += int(predicted_successor_action == expected_action)
        command = make_grounded_action_command(
            world,
            decision.action_id,
            field_state_sha256=qi_state_sha256(controller, committed),
        )
        acknowledgment = world.step(command)
        observation_after = observe_proprioception(world)
        correct = decision.action_id == expected_action
        heldout_correct += int(correct)
        heldout_rows.append(
            {
                "acknowledgment_status": acknowledgment.status,
                "actual_action": decision.action_id,
                "candidate_work": dict(decision.candidate_work),
                "correct": correct,
                "expected_action": expected_action,
                "margin": decision.margin,
                "memory_unchanged": law.memory_sha256(committed)
                == trained_memory_sha256,
                "observation_after": list(_position(observation_after)),
                "observation_before": list(_position(observation_before)),
                "seed": test_seed,
                "utterance": utterance,
                "world_effect": acknowledgment.world_effect,
                "successor_prediction": predicted_successor_action,
                "successor_prediction_correct": predicted_successor_action
                == expected_action,
                "successor_work": successor_work,
            }
        )

    shifted_actions = GROUND_ACTIONS[1:] + GROUND_ACTIONS[:1]
    shuffled_correct = sum(
        int(row["actual_action"] == shifted)
        for row, shifted in zip(heldout_rows, shifted_actions, strict=True)
    )
    if heldout_correct != len(GROUND_ACTIONS):
        failures = [row for row in heldout_rows if not row["correct"]]
        raise RuntimeError(f"grounded held-out transfer failed: {failures}")
    minimum_margin = min(float(row["margin"]) for row in heldout_rows)
    if minimum_margin <= 1.0e-4:
        raise RuntimeError(
            f"grounded held-out action margin is numerically unresolved: {minimum_margin}"
        )
    if shuffled_correct >= heldout_correct:
        raise RuntimeError("shuffled grounding preserved held-out behavior")
    if not all(row["memory_unchanged"] for row in heldout_rows):
        raise RuntimeError("held-out inference changed trained trajectory memory")

    if successor_correct != len(GROUND_ACTIONS):
        failures = [
            row for row in heldout_rows if not row["successor_prediction_correct"]
        ]
        raise RuntimeError(f"grounded successor prediction failed: {failures}")
    base_episode_count, base_event_count = _base_counts(base_checkpoint_path)
    curriculum_identity = _canonical_sha256(
        {
            "base_corpus_identity": engine.corpus_identity,
            "boundary_fingerprint": codec.fingerprint,
            "consolidation_strength_floor": GROUND_CONSOLIDATION_STRENGTH_FLOOR,
            "heldout_seed_start": heldout_seed_start,
            "heldout_utterances": dict(GROUND_HELDOUT_UTTERANCES),
            "schema": GROUND_TRAINING_SCHEMA,
            "training_seed_start": training_seed_start,
            "training_utterances": {
                action: list(values)
                for action, values in GROUND_TRAINING_UTTERANCES.items()
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
    receipt: dict[str, Any] = {
        "base": {
            "checkpoint_path": str(base_checkpoint_path.resolve()),
            "memory_sha256": base_memory_sha256,
        },
        "boundary_fingerprint": codec.fingerprint,
        "checkpoint": {
            "memory_event_count": law.memory_event_count(state),
            "memory_event_capacity": config.scale_count * law.width,
            "memory_sha256": trained_memory_sha256,
            "path": str(checkpoint_path.resolve()),
            "sha256": checkpoint_sha256,
            "shape": list(state.field.shape),
            "tensor_count": 1,
        },
        "curriculum_identity": curriculum_identity,
        "heldout": {
            "accuracy": heldout_correct / len(GROUND_ACTIONS),
            "correct": heldout_correct,
            "minimum_margin": minimum_margin,
            "successor_accuracy": successor_correct / len(GROUND_ACTIONS),
            "episodes": heldout_rows,
            "shuffled_accuracy": shuffled_correct / len(GROUND_ACTIONS),
            "total": len(GROUND_ACTIONS),
        },
        "schema": GROUND_TRAINING_SCHEMA,
        "status": "PASS",
        "timing_seconds": time.perf_counter() - started,
        "training": {
            "episode_count": len(training_rows),
            "event_count": training_event_count,
            "episodes": training_rows,
        },
    }
    _atomic_json(output_dir / "training-receipt.json", receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the five-action grounded Qi language field."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--base-checkpoint",
        type=Path,
        default=DEFAULT_BASE_CHECKPOINT,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--training-seed-start", type=int, default=1)
    parser.add_argument("--heldout-seed-start", type=int, default=101)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    receipt = train_grounded_language(
        config_path=arguments.config,
        base_checkpoint_path=arguments.base_checkpoint,
        output_dir=arguments.output_dir,
        training_seed_start=arguments.training_seed_start,
        heldout_seed_start=arguments.heldout_seed_start,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
