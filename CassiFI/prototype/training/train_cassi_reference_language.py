"""Train and verify temporary references in the grounded Qi field."""
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
    GROUND_REFERENCE_HELDOUT_BINDINGS,
    GROUND_REFERENCE_HELDOUT_QUESTIONS,
    GROUND_REFERENCE_ROLES,
    GROUND_REFERENCE_TRAINING_QUESTIONS,
    GROUND_REFERENCE_TRAINING_STATEMENTS,
    GROUND_REFERENCES,
    GROUND_SPATIAL_HELDOUT_QUESTIONS,
    consolidate_spatial_episode,
    observe_colored_objects,
    observe_proprioception,
    select_grounded_action,
    select_grounded_reference,
    select_spatial_relation,
    sense_binding_statement,
    sense_grounded_symbols,
    sense_reference_cue,
    sense_spatial_query,
    spatial_relation_from_observation,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_qi_world import DeterministicQiWorld

REFERENCE_TRAINING_SCHEMA = "cassi.qi-reference-language-training.v1"
REFERENCE_RELATION_TRAINING_SEEDS = (1, 3, 4, 8, 15, 23, 33, 99)
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
REFERENCE_RELATION_HELDOUT_SEEDS = (101, 159)
DEFAULT_CONFIG = CONFIG_DIR / "cassi-qi-corpus-language.json"
DEFAULT_BASE_CHECKPOINT = ARTIFACT_DIR / "cassi-qi-spatial-language" / "field-state.pt"
DEFAULT_OUTPUT_DIR = ARTIFACT_DIR / "cassi-qi-reference-language"

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


def train_reference_language(
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

    for reference_id, statements in GROUND_REFERENCE_TRAINING_STATEMENTS.items():
        for statement in statements:
            episode = codec.binding_episode_symbols(statement, reference_id)
            state = law.learn_sequence(state, episode, strength=1.0)
            training_event_count += len(episode)
            training_rows.append(
                {
                    "episode_type": "binding",
                    "reference_id": reference_id,
                    "statement": statement,
                }
            )

    for reference_id in GROUND_REFERENCES:
        color = reference_id.removeprefix("reference.")
        for role in GROUND_REFERENCE_ROLES:
            episode = codec.reference_episode_symbols(color, role, reference_id)
            state = law.learn_sequence(state, episode, strength=1.0)
            training_event_count += len(episode)
            training_rows.append(
                {
                    "episode_type": "literal-reference",
                    "reference_id": reference_id,
                    "role": role,
                    "surface": color,
                }
            )

    for layout_index, seed in enumerate(REFERENCE_RELATION_TRAINING_SEEDS):
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"reference.relation.train.{seed}",
        )
        observation = observe_colored_objects(world)
        for family, questions in GROUND_REFERENCE_TRAINING_QUESTIONS.items():
            question = questions[layout_index % len(questions)]
            relation_id = spatial_relation_from_observation(observation, family)
            episode = codec.spatial_episode_symbols(
                observation,
                question,
                relation_id,
            )
            state = consolidate_spatial_episode(
                law,
                codec,
                state,
                object_observation=observation,
                question=question,
                relation_id=relation_id,
            )
            training_event_count += len(episode)
            training_rows.append(
                {
                    "episode_type": "reference-relation-family",
                    "family": family,
                    "question": question,
                    "relation_id": relation_id,
                    "seed": seed,
                }
            )

    state = law.reset_context(state)
    trained_memory_sha256 = law.memory_sha256(state)

    binding_rows: list[dict[str, Any]] = []
    binding_correct = 0
    for name, statement, expected_reference in GROUND_REFERENCE_HELDOUT_BINDINGS:
        cue = sense_binding_statement(law, law.reset_context(state), codec, statement)
        decision = select_grounded_reference(controller, law, codec, cue)
        correct = decision.reference_id == expected_reference
        binding_correct += int(correct)
        binding_rows.append(
            {
                "candidate_work": dict(decision.candidate_work),
                "correct": correct,
                "expected_reference": expected_reference,
                "margin": decision.margin,
                "name": name,
                "predicted_reference": decision.reference_id,
                "statement": statement,
            }
        )

    literal_rows: list[dict[str, Any]] = []
    literal_correct = 0
    for reference_id in GROUND_REFERENCES:
        color = reference_id.removeprefix("reference.")
        for role in GROUND_REFERENCE_ROLES:
            cue = sense_reference_cue(
                law,
                law.reset_context(state),
                codec,
                color,
                role,
            )
            decision = select_grounded_reference(controller, law, codec, cue)
            correct = decision.reference_id == reference_id
            literal_correct += int(correct)
            literal_rows.append(
                {
                    "actual_reference": decision.reference_id,
                    "correct": correct,
                    "expected_reference": reference_id,
                    "margin": decision.margin,
                    "role": role,
                    "surface": color,
                }
            )

    unknown_resolved = False
    unknown_prediction: str | None = None
    try:
        unknown_cue = sense_reference_cue(
            law,
            law.reset_context(state),
            codec,
            "Quill",
            "subject",
        )
        unknown = select_grounded_reference(controller, law, codec, unknown_cue)
        unknown_resolved = True
        unknown_prediction = unknown.reference_id
    except CassiGroundedLanguageError:
        pass

    relation_rows: list[dict[str, Any]] = []
    relation_correct = 0
    for seed in REFERENCE_RELATION_HELDOUT_SEEDS:
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"reference.relation.heldout.{seed}",
        )
        observation = observe_colored_objects(world)
        for family, question in GROUND_REFERENCE_HELDOUT_QUESTIONS.items():
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
            relation_correct += int(correct)
            relation_rows.append(
                {
                    "actual_relation": decision.relation_id,
                    "correct": correct,
                    "expected_relation": expected_relation,
                    "family": family,
                    "margin": decision.margin,
                    "question": question,
                    "seed": seed,
                }
            )

    action_rows: list[dict[str, Any]] = []
    action_correct = 0
    for index, expected_action in enumerate(GROUND_ACTIONS):
        world = DeterministicQiWorld(
            seed=301 + index,
            session_id=f"reference.action-retention.{index}",
        )
        cue = sense_grounded_symbols(
            law,
            law.reset_context(state),
            codec.instruction_symbols(
                observe_proprioception(world),
                GROUND_HELDOUT_UTTERANCES[expected_action],
            ),
        )
        decision = select_grounded_action(controller, law, codec, cue)
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

    spatial_rows: list[dict[str, Any]] = []
    spatial_correct = 0
    for seed in REFERENCE_RELATION_HELDOUT_SEEDS:
        world = DeterministicQiWorld(
            seed=seed,
            session_id=f"reference.spatial-retention.{seed}",
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
                    "margin": decision.margin,
                    "seed": seed,
                }
            )

    if binding_correct != len(GROUND_REFERENCE_HELDOUT_BINDINGS):
        raise RuntimeError(f"held-out reference binding failed: {binding_rows}")
    literal_total = len(GROUND_REFERENCES) * len(GROUND_REFERENCE_ROLES)
    if literal_correct != literal_total:
        raise RuntimeError(f"literal reference resolution failed: {literal_rows}")
    if unknown_resolved:
        raise RuntimeError(
            f"unknown reference resolved as {unknown_prediction!r} before binding"
        )
    relation_total = len(REFERENCE_RELATION_HELDOUT_SEEDS) * len(
        GROUND_REFERENCE_HELDOUT_QUESTIONS
    )
    if relation_correct != relation_total:
        raise RuntimeError(f"reference relation-family transfer failed: {relation_rows}")
    if action_correct != len(GROUND_ACTIONS):
        raise RuntimeError(f"reference training displaced actions: {action_rows}")
    if spatial_correct != 2 * len(GROUND_SPATIAL_HELDOUT_QUESTIONS):
        raise RuntimeError(f"reference training displaced spatial answers: {spatial_rows}")

    base_episode_count, base_event_count = _base_counts(base_checkpoint_path)
    curriculum_identity = _canonical_sha256(
        {
            "base_corpus_identity": engine.corpus_identity,
            "boundary_fingerprint": codec.fingerprint,
            "heldout_bindings": list(GROUND_REFERENCE_HELDOUT_BINDINGS),
            "heldout_questions": dict(GROUND_REFERENCE_HELDOUT_QUESTIONS),
            "reference_roles": list(GROUND_REFERENCE_ROLES),
            "references": list(GROUND_REFERENCES),
            "relation_training_seeds": list(REFERENCE_RELATION_TRAINING_SEEDS),
            "schema": REFERENCE_TRAINING_SCHEMA,
            "training_questions": {
                family: list(questions)
                for family, questions in GROUND_REFERENCE_TRAINING_QUESTIONS.items()
            },
            "training_statements": {
                reference: list(statements)
                for reference, statements in GROUND_REFERENCE_TRAINING_STATEMENTS.items()
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
        "binding": {
            "accuracy": binding_correct / len(GROUND_REFERENCE_HELDOUT_BINDINGS),
            "correct": binding_correct,
            "episodes": binding_rows,
            "total": len(GROUND_REFERENCE_HELDOUT_BINDINGS),
            "unknown_name_failed_closed": not unknown_resolved,
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
        "literal_reference": {
            "accuracy": literal_correct / literal_total,
            "correct": literal_correct,
            "episodes": literal_rows,
            "total": literal_total,
        },
        "relation_family": {
            "accuracy": relation_correct / relation_total,
            "correct": relation_correct,
            "episodes": relation_rows,
            "total": relation_total,
        },
        "schema": REFERENCE_TRAINING_SCHEMA,
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
    receipt = train_reference_language(
        config_path=arguments.config,
        base_checkpoint_path=arguments.base_checkpoint,
        output_dir=arguments.output_dir,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
