"""Independently replay and verify a trajectory-owned corpus field."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from typing import Any, Final, Mapping, Sequence

import torch

from cassi_field_language import (
    CassiFieldTextCodec,
    CassiQiTextEngine,
    CassiQiTrajectoryLaw,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR, ROOT
from training.train_cassi_field_language import _manifest_sources


VERIFICATION_SCHEMA: Final[str] = "cassi.qi-trajectory-language-verification.v1"
TRAINING_SCHEMA: Final[str] = "cassi.qi-trajectory-training-receipt.v1"
_ROOT: Final[Path] = ROOT


class TrajectoryVerificationError(RuntimeError):
    """Raised when independent trajectory reconstruction diverges."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(
        dict(value),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _load_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrajectoryVerificationError(f"could not read training receipt: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != TRAINING_SCHEMA:
        raise TrajectoryVerificationError("training receipt schema mismatch")
    claimed = value.get("receipt_sha256")
    unsealed = dict(value)
    unsealed.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or claimed != _canonical_sha256(unsealed):
        raise TrajectoryVerificationError("training receipt canonical hash mismatch")
    return value


def _read_episode(
    descriptor: Mapping[str, Any],
    source_paths: Mapping[str, Path],
    codec: CassiFieldTextCodec,
) -> tuple[tuple[int, ...], bytes, bytes]:
    required = {
        "continuation_bytes",
        "events",
        "length",
        "offset",
        "payload_sha256",
        "prompt_bytes",
        "source_id",
    }
    if not isinstance(descriptor, Mapping) or set(descriptor) != required:
        raise TrajectoryVerificationError("episode descriptor is malformed")
    source_id = descriptor["source_id"]
    if not isinstance(source_id, str) or source_id not in source_paths:
        raise TrajectoryVerificationError("episode source identity is unknown")
    integers = ("continuation_bytes", "events", "length", "offset", "prompt_bytes")
    if any(
        isinstance(descriptor[key], bool)
        or not isinstance(descriptor[key], int)
        or int(descriptor[key]) < 0
        for key in integers
    ):
        raise TrajectoryVerificationError("episode descriptor integer is malformed")
    with source_paths[source_id].open("rb") as handle:
        handle.seek(int(descriptor["offset"]))
        payload = handle.read(int(descriptor["length"]))
    if hashlib.sha256(payload).hexdigest() != descriptor["payload_sha256"]:
        raise TrajectoryVerificationError("episode payload changed after training")
    prompt_bytes = int(descriptor["prompt_bytes"])
    continuation_bytes = int(descriptor["continuation_bytes"])
    if prompt_bytes + continuation_bytes != len(payload):
        raise TrajectoryVerificationError("episode split does not cover its payload")
    prompt = payload[:prompt_bytes]
    continuation = payload[prompt_bytes:]
    events = codec.encode_training_exchange(prompt, continuation)
    if len(events) != descriptor["events"]:
        raise TrajectoryVerificationError("episode event count changed")
    return events, prompt, continuation


def _metrics(
    law: CassiQiTrajectoryLaw,
    state,
    sequences: Sequence[tuple[int, ...]],
) -> dict[str, object]:
    correct = 0
    total = 0
    for sequence in sequences:
        value, count = law.sequence_accuracy(state, sequence)
        correct += value
        total += count
    return {
        "accuracy": 0.0 if total == 0 else correct / total,
        "correct": correct,
        "total": total,
    }


def verify(
    *,
    config_path: Path,
    artifact_dir: Path,
    output_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    artifact_dir = Path(artifact_dir).resolve()
    training_path = artifact_dir / "training-receipt.json"
    checkpoint_path = artifact_dir / "field-state.pt"
    training = _load_receipt(training_path)
    config_path = Path(config_path).resolve()
    if _sha256_file(config_path) != training["config"]["sha256"]:
        raise TrajectoryVerificationError("field configuration changed after training")
    if _sha256_file(checkpoint_path) != training["checkpoint"]["sha256"]:
        raise TrajectoryVerificationError("trajectory checkpoint bytes changed")
    config = QiFieldConfig.from_dict(json.loads(config_path.read_text(encoding="utf-8")))
    controller = QiFieldController(config)
    law = CassiQiTrajectoryLaw(controller)
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=checkpoint_path,
        max_output_symbols=int(training["experience"]["max_episode_bytes"]),
    )
    if engine.corpus_identity != training["corpus"]["identity"]:
        raise TrajectoryVerificationError("checkpoint corpus identity mismatch")

    source_paths: dict[str, Path] = {}
    bound_sources = None
    if manifest_path is not None:
        sources, _ = _manifest_sources(manifest_path)
        bound_sources = {source.source_id: source for source in sources}
    for source in training["corpus"]["sources"]:
        if not isinstance(source, Mapping):
            raise TrajectoryVerificationError("training source record is malformed")
        source_id = source.get("id")
        source_path = artifact_dir / str(source.get("path"))
        if not isinstance(source_id, str) or source_id in source_paths:
            raise TrajectoryVerificationError("training source id is malformed or duplicated")
        if bound_sources is not None:
            bound = bound_sources.get(source_id)
            if (
                bound is None
                or bound.sha256 != source.get("sha256")
                or bound.corpus_bytes != source.get("bytes")
            ):
                raise TrajectoryVerificationError(
                    f"manifest does not bind the recorded source: {source_id}"
                )
            source_path = bound.path
        if not source_path.is_file() or source_path.stat().st_size != source.get("bytes"):
            raise TrajectoryVerificationError(f"training source size changed: {source_id}")
        if bound_sources is None and _sha256_file(source_path) != source.get("sha256"):
            raise TrajectoryVerificationError(f"training source hash changed: {source_id}")
        source_paths[source_id] = source_path
    if bound_sources is not None and set(bound_sources) != set(source_paths):
        raise TrajectoryVerificationError("manifest source identities differ from training")

    codec = law.codec
    training_sequences: list[tuple[int, ...]] = []
    training_prompts: list[tuple[bytes, bytes, str]] = []
    for descriptor in training["experience"]["training_episodes"]:
        events, prompt, continuation = _read_episode(descriptor, source_paths, codec)
        training_sequences.append(events)
        training_prompts.append((prompt, continuation, str(descriptor["source_id"])))
    heldout_sequences: list[tuple[int, ...]] = []
    heldout_prompts: list[tuple[bytes, bytes, str]] = []
    for descriptor in training["experience"]["heldout_episodes"]:
        events, prompt, continuation = _read_episode(descriptor, source_paths, codec)
        heldout_sequences.append(events)
        heldout_prompts.append((prompt, continuation, str(descriptor["source_id"])))

    reconstructed = law.initial_state()
    for sequence in training_sequences:
        reconstructed = law.learn_sequence(reconstructed, sequence)
    reconstructed = law.reset_context(reconstructed)
    reconstructed_memory = law.memory_sha256(reconstructed)
    if reconstructed_memory != engine.corpus_memory_sha256:
        raise TrajectoryVerificationError("independent trajectory memory reconstruction diverged")

    training_metrics = _metrics(law, reconstructed, training_sequences)
    heldout_metrics = _metrics(law, reconstructed, heldout_sequences)
    for label, observed, recorded in (
        ("training", training_metrics, training["training"]),
        ("heldout", heldout_metrics, training["heldout"]),
    ):
        for key in ("accuracy", "correct", "total"):
            if observed[key] != recorded[key]:
                raise TrajectoryVerificationError(f"{label} metric changed for {key}")

    generation: list[dict[str, object]] = []
    for prompt, expected, source_id in training_prompts[:4]:
        result = engine.generate(
            engine.initial_state(),
            ({"role": "user", "content": prompt.decode("utf-8", errors="strict")},),
        )
        if not result.all_outputs_field_owned:
            raise TrajectoryVerificationError("generation committed an unowned event")
        if result.corpus_memory_sha256 != engine.corpus_memory_sha256:
            raise TrajectoryVerificationError("generation changed trajectory memory")
        generation.append(
            {
                "actual": result.text,
                "expected": expected.decode("utf-8", errors="strict"),
                "prompt": prompt.decode("utf-8", errors="strict"),
                "source_id": source_id,
                "stop_reason": result.stop_reason,
            }
        )
    if generation != training["generation"]["training_examples"]:
        raise TrajectoryVerificationError("recorded training generations do not replay")

    receipt: dict[str, object] = {
        "checkpoint": {
            "finite": bool(torch.isfinite(reconstructed.field).all().item()),
            "memory_sha256": reconstructed_memory,
            "one_adaptive_tensor": tuple(reconstructed.__dataclass_fields__) == ("field",),
            "shape": list(reconstructed.field.shape),
        },
        "generation": generation,
        "heldout": heldout_metrics,
        "reconstruction": {
            "episode_count": len(training_sequences),
            "event_count": sum(len(value) for value in training_sequences),
            "memory_bit_exact": True,
        },
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "timing_seconds": time.perf_counter() - started,
        "training": training_metrics,
        "training_receipt_sha256": _sha256_file(training_path),
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _atomic_write(Path(output_path), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_DIR / "cassi-qi-corpus-language.json",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ARTIFACT_DIR / "cassi-qi-corpus-language",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--manifest", type=Path,
        help="Hash-bound source relocation for an unchanged historical receipt.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output or args.artifact_dir / "verification-receipt.json"
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
    try:
        receipt = verify(
            config_path=args.config,
            artifact_dir=args.artifact_dir,
            output_path=output,
            manifest_path=args.manifest,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise SystemExit(f"trajectory verification failed: {error}") from error
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
