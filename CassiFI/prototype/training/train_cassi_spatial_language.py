"""Train and verify state-dependent spatial relations in the grounded Qi field."""
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

from cassi_field_language import CassiQiTextEngine, save_trajectory_checkpoint
from cassi_grounded_language import (
    CassiGroundedEventCodec,
    CassiGroundedLanguageError,
    GROUND_ACTIONS,
    GROUND_HELDOUT_UTTERANCES,
    GROUND_RELATIONS,
    GROUND_SPATIAL_GRID_SIZE,
    GROUND_SPATIAL_HELDOUT_QUESTIONS,
    GROUND_SPATIAL_TRAINING_QUESTIONS,
    commit_spatial_relation,
    consolidate_spatial_episode,
    decode_colored_objects,
    observe_colored_objects,
    observe_proprioception,
    select_grounded_action,
    select_spatial_relation,
    sense_grounded_symbols,
    sense_spatial_query,
    spatial_relation_from_observation,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_qi_world import DeterministicQiWorld

SPATIAL_TRAINING_SCHEMA = "cassi.qi-spatial-language-training.v1"
SPATIAL_TRAINING_SEEDS = (1, 3, 4, 8, 15, 23, 33, 99)
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR

SPATIAL_HELDOUT_SEEDS = (101, 159)
DEFAULT_CONFIG = CONFIG_DIR / "cassi-qi-corpus-language.json"
DEFAULT_BASE_CHECKPOINT = ARTIFACT_DIR / "cassi-qi-grounded-language" / "field-state.pt"
DEFAULT_OUTPUT_DIR = ARTIFACT_DIR / "cassi-qi-spatial-language"

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


def _object_rows(observation: bytes) -> list[dict[str, int | str]]:
    return [
        {"color": color, "x_bin": x_bin, "y_bin": y_bin}
        for color, x_bin, y_bin in decode_colored_objects(observation)
    ]


def train_spatial_language(
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

    for layout_index, seed in enumerate(SPATIAL_TRAINING_SEEDS):
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"spatial.train.{seed}",
        )
        object_observation = observe_colored_objects(world)
        for family, questions in GROUND_SPATIAL_TRAINING_QUESTIONS.items():
            question = questions[layout_index % len(questions)]
            desired_relation = spatial_relation_from_observation(
                object_observation,
                family,
            )
            cue_state = sense_spatial_query(
                law,
                state,
                codec,
                object_observation,
                question,
            )
            try:
                prediction = select_spatial_relation(
                    controller,
                    law,
                    codec,
                    cue_state,
                )
                predicted_relation: str | None = prediction.relation_id
                candidate_work = dict(prediction.candidate_work)
            except CassiGroundedLanguageError:
                predicted_relation = None
                candidate_work = {}
            episode = codec.spatial_episode_symbols(
                object_observation,
                question,
                desired_relation,
            )
            state = consolidate_spatial_episode(
                law,
                codec,
                state,
                object_observation=object_observation,
                question=question,
                relation_id=desired_relation,
            )
            training_event_count += len(episode)
            training_rows.append(
                {
                    "candidate_work_before_training": candidate_work,
                    "desired_relation": desired_relation,
                    "family": family,
                    "field_prediction_before_training": predicted_relation,
                    "objects": _object_rows(object_observation),
                    "question": question,
                    "seed": seed,
                }
            )

    state = law.reset_context(state)
    trained_memory_sha256 = law.memory_sha256(state)
    heldout_rows: list[dict[str, Any]] = []
    heldout_correct = 0
    for seed in SPATIAL_HELDOUT_SEEDS:
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"spatial.heldout.{seed}",
        )
        object_observation = observe_colored_objects(world)
        for family, question in GROUND_SPATIAL_HELDOUT_QUESTIONS.items():
            expected_relation = spatial_relation_from_observation(
                object_observation,
                family,
            )
            cue_state = sense_spatial_query(
                law,
                law.reset_context(state),
                codec,
                object_observation,
                question,
            )
            decision = select_spatial_relation(
                controller,
                law,
                codec,
                cue_state,
            )
            committed = commit_spatial_relation(law, codec, cue_state, decision)
            correct = decision.relation_id == expected_relation
            heldout_correct += int(correct)
            heldout_rows.append(
                {
                    "answer": decision.answer,
                    "candidate_work": dict(decision.candidate_work),
                    "correct": correct,
                    "expected_relation": expected_relation,
                    "family": family,
                    "margin": decision.margin,
                    "memory_unchanged": law.memory_sha256(committed)
                    == trained_memory_sha256,
                    "objects": _object_rows(object_observation),
                    "question": question,
                    "relation_id": decision.relation_id,
                    "seed": seed,
                }
            )

    heldout_by_key = {
        (int(row["seed"]), str(row["family"])): row for row in heldout_rows
    }
    reversal_rows: list[dict[str, Any]] = []
    for family, question in GROUND_SPATIAL_HELDOUT_QUESTIONS.items():
        first = heldout_by_key[(SPATIAL_HELDOUT_SEEDS[0], family)]
        second = heldout_by_key[(SPATIAL_HELDOUT_SEEDS[1], family)]
        reversal_rows.append(
            {
                "answers_reverse": first["relation_id"] != second["relation_id"],
                "family": family,
                "first_relation": first["relation_id"],
                "first_seed": SPATIAL_HELDOUT_SEEDS[0],
                "question": question,
                "second_relation": second["relation_id"],
                "second_seed": SPATIAL_HELDOUT_SEEDS[1],
            }
        )

    substituted_rows: list[dict[str, Any]] = []
    substituted_followed = 0
    substituted_original_correct = 0
    for seed in SPATIAL_HELDOUT_SEEDS:
        other_seed = next(item for item in SPATIAL_HELDOUT_SEEDS if item != seed)
        other_world = DeterministicQiWorld(
            seed=other_seed,
            session_id=f"spatial.substituted.{seed}.{other_seed}",
        )
        substituted_observation = observe_colored_objects(other_world)
        for family, question in GROUND_SPATIAL_HELDOUT_QUESTIONS.items():
            original_relation = str(heldout_by_key[(seed, family)]["expected_relation"])
            substituted_relation = spatial_relation_from_observation(
                substituted_observation,
                family,
            )
            cue_state = sense_spatial_query(
                law,
                law.reset_context(state),
                codec,
                substituted_observation,
                question,
            )
            decision = select_spatial_relation(controller, law, codec, cue_state)
            followed = decision.relation_id == substituted_relation
            original_correct = decision.relation_id == original_relation
            substituted_followed += int(followed)
            substituted_original_correct += int(original_correct)
            substituted_rows.append(
                {
                    "family": family,
                    "follows_substituted_layout": followed,
                    "original_relation": original_relation,
                    "original_seed": seed,
                    "predicted_relation": decision.relation_id,
                    "question": question,
                    "substituted_relation": substituted_relation,
                    "substituted_seed": other_seed,
                }
            )

    action_rows: list[dict[str, Any]] = []
    action_correct = 0
    for index, expected_action in enumerate(GROUND_ACTIONS):
        world = DeterministicQiWorld(
            seed=201 + index,
            session_id=f"spatial.action-retention.{index}",
        )
        cue_state = sense_grounded_symbols(
            law,
            law.reset_context(state),
            codec.instruction_symbols(
                observe_proprioception(world),
                GROUND_HELDOUT_UTTERANCES[expected_action],
            ),
        )
        decision = select_grounded_action(controller, law, codec, cue_state)
        correct = decision.action_id == expected_action
        action_correct += int(correct)
        action_rows.append(
            {
                "actual_action": decision.action_id,
                "correct": correct,
                "expected_action": expected_action,
                "margin": decision.margin,
            }
        )

    heldout_total = len(SPATIAL_HELDOUT_SEEDS) * len(
        GROUND_SPATIAL_HELDOUT_QUESTIONS
    )
    if heldout_correct != heldout_total:
        raise RuntimeError(
            "spatial held-out transfer failed: "
            f"{[(row['seed'], row['family'], row['expected_relation'], row['relation_id'], row['candidate_work']) for row in heldout_rows if not row['correct']]}"
        )
    if not all(row["answers_reverse"] for row in reversal_rows):
        raise RuntimeError(f"spatial answers did not reverse: {reversal_rows}")
    if substituted_followed != heldout_total or substituted_original_correct != 0:
        raise RuntimeError(
            "spatial answer did not follow the substituted world frame: "
            f"{substituted_rows}"
        )
    if not all(row["memory_unchanged"] for row in heldout_rows):
        raise RuntimeError("spatial inference changed trained trajectory memory")
    minimum_margin = min(float(row["margin"]) for row in heldout_rows)
    if minimum_margin <= 1.0e-4:
        raise RuntimeError(f"spatial answer margin is unresolved: {minimum_margin}")
    if action_correct != len(GROUND_ACTIONS):
        raise RuntimeError(f"spatial training displaced grounded actions: {action_rows}")

    base_episode_count, base_event_count = _base_counts(base_checkpoint_path)
    curriculum_identity = _canonical_sha256(
        {
            "base_corpus_identity": engine.corpus_identity,
            "boundary_fingerprint": codec.fingerprint,
            "grid_size": GROUND_SPATIAL_GRID_SIZE,
            "heldout_questions": dict(GROUND_SPATIAL_HELDOUT_QUESTIONS),
            "heldout_seeds": list(SPATIAL_HELDOUT_SEEDS),
            "relations": list(GROUND_RELATIONS),
            "schema": SPATIAL_TRAINING_SCHEMA,
            "training_questions": {
                family: list(questions)
                for family, questions in GROUND_SPATIAL_TRAINING_QUESTIONS.items()
            },
            "training_seeds": list(SPATIAL_TRAINING_SEEDS),
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
        "action_retention": {
            "accuracy": action_correct / len(GROUND_ACTIONS),
            "correct": action_correct,
            "episodes": action_rows,
            "total": len(GROUND_ACTIONS),
        },
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
        "curriculum_identity": curriculum_identity,
        "heldout": {
            "accuracy": heldout_correct / heldout_total,
            "correct": heldout_correct,
            "episodes": heldout_rows,
            "minimum_margin": minimum_margin,
            "reversals": reversal_rows,
            "substituted_layout_accuracy": substituted_followed / heldout_total,
            "substituted_layout_episodes": substituted_rows,
            "substituted_original_label_accuracy": substituted_original_correct
            / heldout_total,
            "total": heldout_total,
        },
        "schema": SPATIAL_TRAINING_SCHEMA,
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
    receipt = train_spatial_language(
        config_path=arguments.config,
        base_checkpoint_path=arguments.base_checkpoint,
        output_dir=arguments.output_dir,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
