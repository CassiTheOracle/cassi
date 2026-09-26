"""Train and verify field-owned whole-utterance semantic frames."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

import torch

from cassi_discourse_language import (
    DISCOURSE_ABSTAIN_CLARIFICATIONS,
    DISCOURSE_ROUTES,
    DISCOURSE_FRAME_MINIMUM_HISTORY,
    DISCOURSE_ROUTE_TRAINING_PROMPTS,
    DISCOURSE_ROUTE_VALIDATION_PROMPTS,
    CassiDiscourseEventCodec,
    select_discourse_frame,
    semantic_frame_target,
)
from cassi_field_language import CassiQiTextEngine, save_trajectory_checkpoint
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_qi_field import QiFieldConfig, QiFieldController

DISCOURSE_TRAINING_SCHEMA = "cassi.qi-discourse-language-training.v2"
DEFAULT_CONFIG = CONFIG_DIR / "cassi-qi-corpus-language.json"
DEFAULT_BASE_CHECKPOINT = ARTIFACT_DIR / "cassi-qi-temporal-language" / "field-state.pt"
DEFAULT_OUTPUT_DIR = ARTIFACT_DIR / "cassi-qi-discourse-language"


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _base_counts(path: Path) -> tuple[int, int]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise RuntimeError("trajectory checkpoint payload is not an object")
    return int(payload["training_episode_count"]), int(payload["training_event_count"])


def _validate_frame_set(
    controller: QiFieldController,
    law: Any,
    codec: CassiDiscourseEventCodec,
    state: Any,
    trained_memory_sha256: str,
    prompts: Mapping[str, tuple[str, ...]],
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    correct = 0
    for expected_route in DISCOURSE_ROUTES:
        for prompt in prompts[expected_route]:
            expected = semantic_frame_target(
                prompt,
                expected_route,
                clarification=DISCOURSE_ABSTAIN_CLARIFICATIONS.get(prompt),
            )
            decision = select_discourse_frame(
                controller,
                law,
                codec,
                state,
                prompt,
            )
            row_correct = decision.target == expected
            correct += int(row_correct)
            rows.append(
                {
                    "correct": row_correct,
                    "expected_frame": expected.receipt_dict(),
                    "memory_unchanged": decision.trained_memory_sha256
                    == trained_memory_sha256,
                    "prompt": prompt,
                    "frame": decision.receipt_dict(),
                    "selected_frame": decision.target.receipt_dict(),
                }
            )
    return rows, correct


def _validate_prompt_banks() -> None:
    if tuple(DISCOURSE_ROUTE_TRAINING_PROMPTS) != DISCOURSE_ROUTES:
        raise RuntimeError("route training prompt bank does not cover canonical routes")
    if tuple(DISCOURSE_ROUTE_VALIDATION_PROMPTS) != DISCOURSE_ROUTES:
        raise RuntimeError("route validation prompt bank does not cover canonical routes")
    training_prompts = [
        prompt
        for prompts in DISCOURSE_ROUTE_TRAINING_PROMPTS.values()
        for prompt in prompts
    ]
    validation_prompts = [
        prompt
        for prompts in DISCOURSE_ROUTE_VALIDATION_PROMPTS.values()
        for prompt in prompts
    ]
    if not training_prompts or not validation_prompts:
        raise RuntimeError("route prompt banks must not be empty")
    if len(training_prompts) != len(set(training_prompts)):
        raise RuntimeError("route training prompts are not unique")
    if len(validation_prompts) != len(set(validation_prompts)):
        raise RuntimeError("route validation prompts are not unique")
    if set(training_prompts) & set(validation_prompts):
        raise RuntimeError("route training and validation prompts overlap")


def train_discourse_language(
    *,
    config_path: Path = DEFAULT_CONFIG,
    base_checkpoint_path: Path = DEFAULT_BASE_CHECKPOINT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Derive a semantic-frame checkpoint and require exact heldout frames."""
    started = time.perf_counter()
    config_path = Path(config_path).resolve()
    base_checkpoint_path = Path(base_checkpoint_path).resolve()
    output_dir = Path(output_dir).resolve()
    checkpoint_path = output_dir / "field-state.pt"
    if checkpoint_path == base_checkpoint_path:
        raise ValueError("derived checkpoint must not overwrite the base checkpoint")
    _validate_prompt_banks()

    base_checkpoint_sha256 = _file_sha256(base_checkpoint_path)
    config = QiFieldConfig.from_dict(json.loads(config_path.read_text(encoding="utf-8")))
    controller = QiFieldController(config)
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=base_checkpoint_path,
        max_output_symbols=96,
    )
    law = engine.law
    codec = CassiDiscourseEventCodec(engine.codec)
    state = engine.initial_state(device="cpu")
    base_memory_sha256 = law.memory_sha256(state)
    base_episode_count, base_event_count = _base_counts(base_checkpoint_path)

    training_rows: list[dict[str, Any]] = []
    training_episode_count = 0
    training_event_count = 0
    for route_id in DISCOURSE_ROUTES:
        for prompt in DISCOURSE_ROUTE_TRAINING_PROMPTS[route_id]:
            target = semantic_frame_target(
                prompt,
                route_id,
                clarification=DISCOURSE_ABSTAIN_CLARIFICATIONS.get(prompt),
            )
            episodes = codec.frame_episode_sequences(prompt, target)
            for episode in episodes:
                state = law.learn_sequence(
                    state,
                    episode,
                    strength=1.0,
                    minimum_history=DISCOURSE_FRAME_MINIMUM_HISTORY,
                )
                training_episode_count += 1
                training_event_count += len(episode)
            training_rows.append(
                {
                    "event_count": sum(map(len, episodes)),
                    "prompt": prompt,
                    "route_id": route_id,
                    "sequence_count": len(episodes),
                    "target": target.receipt_dict(),
                }
            )

    state = law.reset_context(state)
    trained_memory_sha256 = law.memory_sha256(state)
    validation_rows, validation_correct = _validate_frame_set(
        controller,
        law,
        codec,
        state,
        trained_memory_sha256,
        DISCOURSE_ROUTE_VALIDATION_PROMPTS,
    )
    validation_total = len(validation_rows)
    if validation_correct != validation_total:
        failures = [
            row
            for row in validation_rows
            if not row["correct"]
        ]
        raise RuntimeError(
            "discourse frame validation failed:\n"
            + json.dumps(failures, indent=2, sort_keys=True)
        )
    if not all(row["memory_unchanged"] for row in validation_rows):
        raise RuntimeError("frame validation changed field-only trajectory memory")

    curriculum_identity = _canonical_sha256(
        {
            "base_corpus_identity": engine.corpus_identity,
            "base_checkpoint_sha256": base_checkpoint_sha256,
            "codebook_fingerprint": controller.codebook_fingerprint,
            "config_fingerprint": controller.config_fingerprint,
            "semantic_frame_codec_fingerprint": codec.fingerprint,
            "semantic_frame_minimum_history": DISCOURSE_FRAME_MINIMUM_HISTORY,
            "semantic_frame_training_prompts": {
                route_id: list(DISCOURSE_ROUTE_TRAINING_PROMPTS[route_id])
                for route_id in DISCOURSE_ROUTES
            },
            "schema": DISCOURSE_TRAINING_SCHEMA,
            "trajectory_fingerprint": law.fingerprint,
        }
    )
    checkpoint_sha256 = save_trajectory_checkpoint(
        checkpoint_path,
        law=law,
        state=state,
        corpus_identity=curriculum_identity,
        training_episode_count=base_episode_count + training_episode_count,
        training_event_count=base_event_count + training_event_count,
    )

    reloaded_engine = CassiQiTextEngine(
        controller,
        checkpoint_path=checkpoint_path,
        max_output_symbols=96,
    )
    reloaded_state = reloaded_engine.initial_state(device="cpu")
    reloaded_memory_sha256 = reloaded_engine.law.memory_sha256(reloaded_state)
    if reloaded_engine.corpus_identity != curriculum_identity:
        raise RuntimeError("serialized discourse curriculum identity did not round-trip")
    if reloaded_memory_sha256 != trained_memory_sha256:
        raise RuntimeError("serialized discourse memory did not round-trip")
    reloaded_rows, reloaded_correct = _validate_frame_set(
        controller,
        reloaded_engine.law,
        CassiDiscourseEventCodec(reloaded_engine.codec),
        reloaded_state,
        reloaded_memory_sha256,
        DISCOURSE_ROUTE_VALIDATION_PROMPTS,
    )
    if reloaded_correct != validation_total:
        failures = [row for row in reloaded_rows if not row["correct"]]
        raise RuntimeError(f"reloaded discourse frame validation failed: {failures}")
    if [row["selected_frame"] for row in reloaded_rows] != [
        row["selected_frame"] for row in validation_rows
    ]:
        raise RuntimeError("serialized discourse frame decisions were not deterministic")
    if _file_sha256(base_checkpoint_path) != base_checkpoint_sha256:
        raise RuntimeError("base temporal checkpoint changed during discourse training")

    output_checkpoint_sha256 = _file_sha256(checkpoint_path)
    if output_checkpoint_sha256 != checkpoint_sha256:
        raise RuntimeError("saved discourse checkpoint hash was not stable")
    receipt: dict[str, Any] = {
        "base": {
            "checkpoint_path": str(base_checkpoint_path),
            "checkpoint_sha256": base_checkpoint_sha256,
            "event_count": base_event_count,
            "memory_sha256": base_memory_sha256,
            "episode_count": base_episode_count,
            "sha256": base_checkpoint_sha256,
        },
        "checkpoint": {
            "memory_event_capacity": config.scale_count * law.width,
            "memory_event_count": law.memory_event_count(state),
            "memory_sha256": trained_memory_sha256,
            "path": str(checkpoint_path),
            "sha256": output_checkpoint_sha256,
            "shape": list(state.field.shape),
            "tensor_count": 1,
        },
        "boundary_fingerprint": codec.fingerprint,
        "codebook_fingerprint": controller.codebook_fingerprint,
        "config_fingerprint": controller.config_fingerprint,
        "curriculum_identity": curriculum_identity,
        "field_only": {
            "base_memory_event_count": law.memory_event_count(engine.initial_state(device="cpu")),
            "trained_memory_event_count": law.memory_event_count(state),
            "training_event_count": training_event_count,
        },
        "fingerprints": {
            "codebook": controller.codebook_fingerprint,
            "config": controller.config_fingerprint,
            "semantic_frame_codec": codec.fingerprint,
            "trajectory": law.fingerprint,
            "semantic_frame_minimum_history": DISCOURSE_FRAME_MINIMUM_HISTORY,
        },
        "trajectory_fingerprint": law.fingerprint,
        "validation": {
            "accuracy": validation_correct / validation_total,
            "correct": validation_correct,
            "episodes": validation_rows,
            "reloaded_accuracy": reloaded_correct / validation_total,
            "reloaded_episodes": reloaded_rows,
            "total": validation_total,
        },
        "schema": DISCOURSE_TRAINING_SCHEMA,
        "status": "PASS",
        "timing_seconds": time.perf_counter() - started,
        "training": {
            "episode_count": training_episode_count,
            "event_count": training_event_count,
            "prompt_count": len(training_rows),
            "episodes": training_rows,
        },
    }
    _atomic_json(output_dir / "training-receipt.json", receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--base-checkpoint", type=Path, default=DEFAULT_BASE_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    receipt = train_discourse_language(
        config_path=arguments.config,
        base_checkpoint_path=arguments.base_checkpoint,
        output_dir=arguments.output_dir,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
