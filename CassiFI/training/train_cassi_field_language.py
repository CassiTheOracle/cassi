"""Stream hash-bound text episodes through the trajectory-owned Qi field."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Final, Mapping, Sequence
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

import torch

from cassi_field_language import (
    CassiFieldTextCodec,
    CassiQiTextEngine,
    CassiQiTrajectoryLaw,
    save_trajectory_checkpoint,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState


from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR, ROOT
TRAINING_RECEIPT_SCHEMA: Final[str] = "cassi.qi-trajectory-training-receipt.v1"
CORPUS_MANIFEST_SCHEMA: Final[str] = "cassi.qi-corpus-manifest.v1"
CORPUS_IDENTITY_SCHEMA: Final[str] = "cassi.qi-trajectory-corpus-identity.v1"
_ROOT: Final[Path] = ROOT
DEFAULT_CONFIG: Final[Path] = CONFIG_DIR / "cassi-qi-corpus-language.json"
DEFAULT_MANIFEST: Final[Path] = CONFIG_DIR / "cassi-qi-corpus-first-wave.json"
DEFAULT_OUTPUT_DIR: Final[Path] = ARTIFACT_DIR / "cassi-qi-corpus-language"
DEFAULT_EPISODES_PER_SOURCE: Final[int] = 10
DEFAULT_HELDOUT_EPISODES_PER_SOURCE: Final[int] = 4
DEFAULT_MAX_EPISODE_BYTES: Final[int] = 96


class TrajectoryTrainingError(RuntimeError):
    """Raised when corpus experience cannot be applied exactly."""


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


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
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


@dataclasses.dataclass(frozen=True)
class CorpusSource:
    source_id: str
    path: Path
    sha256: str
    corpus_bytes: int
    train_bytes: int
    holdout_bytes: int

    def identity_dict(self) -> dict[str, object]:
        return {
            "bytes": self.corpus_bytes,
            "holdout_bytes": self.holdout_bytes,
            "id": self.source_id,
            "sha256": self.sha256,
            "train_bytes": self.train_bytes,
        }


@dataclasses.dataclass(frozen=True)
class TrajectoryEpisode:
    source_id: str
    path: Path
    offset: int
    payload: bytes
    prompt: bytes
    continuation: bytes
    events: tuple[int, ...]

    def descriptor(self) -> dict[str, object]:
        return {
            "continuation_bytes": len(self.continuation),
            "events": len(self.events),
            "length": len(self.payload),
            "offset": self.offset,
            "payload_sha256": hashlib.sha256(self.payload).hexdigest(),
            "prompt_bytes": len(self.prompt),
            "source_id": self.source_id,
        }


def _source_split(
    corpus_bytes: int,
    *,
    denominator: int,
    minimum_holdout_bytes: int,
    explicit_holdout_bytes: int | None = None,
) -> tuple[int, int]:
    if isinstance(corpus_bytes, bool) or not isinstance(corpus_bytes, int) or corpus_bytes < 8:
        raise TrajectoryTrainingError("corpus source is too small for trajectory learning")
    if (
        isinstance(denominator, bool)
        or not isinstance(denominator, int)
        or denominator < 2
        or isinstance(minimum_holdout_bytes, bool)
        or not isinstance(minimum_holdout_bytes, int)
        or minimum_holdout_bytes < 0
    ):
        raise TrajectoryTrainingError("corpus split policy is malformed")
    holdout = (
        max(minimum_holdout_bytes, corpus_bytes // denominator)
        if explicit_holdout_bytes is None
        else explicit_holdout_bytes
    )
    if isinstance(holdout, bool) or not isinstance(holdout, int) or not 4 <= holdout < corpus_bytes:
        raise TrajectoryTrainingError("holdout bytes must lie inside the corpus")
    return corpus_bytes - holdout, holdout


def _manifest_sources(path: Path) -> tuple[list[CorpusSource], dict[str, object]]:
    manifest_path = Path(path).resolve()
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrajectoryTrainingError(f"could not read corpus manifest: {error}") from error
    required = {
        "holdout_fraction_denominator",
        "minimum_holdout_bytes",
        "schema",
        "sources",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest.get("schema") != CORPUS_MANIFEST_SCHEMA
        or not isinstance(manifest.get("sources"), list)
        or not manifest["sources"]
    ):
        raise TrajectoryTrainingError("corpus manifest schema is malformed")
    denominator = manifest["holdout_fraction_denominator"]
    minimum = manifest["minimum_holdout_bytes"]
    sources: list[CorpusSource] = []
    ids: set[str] = set()
    paths: set[Path] = set()
    hashes: set[str] = set()
    for entry in manifest["sources"]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"id", "path", "sha256"}
            or not all(isinstance(entry[key], str) and entry[key] for key in entry)
        ):
            raise TrajectoryTrainingError("corpus source declaration is malformed")
        source_path = Path(entry["path"]).resolve()
        source_id = entry["id"]
        expected_hash = entry["sha256"]
        if source_id in ids or source_path in paths or expected_hash in hashes:
            raise TrajectoryTrainingError("corpus source identity is duplicated")
        if not source_path.is_file():
            raise TrajectoryTrainingError(f"corpus source is unavailable: {source_path}")
        observed_hash = _sha256_file(source_path)
        if observed_hash != expected_hash:
            raise TrajectoryTrainingError(f"corpus source hash mismatch: {source_id}")
        corpus_bytes = source_path.stat().st_size
        train_bytes, holdout_bytes = _source_split(
            corpus_bytes,
            denominator=denominator,
            minimum_holdout_bytes=minimum,
        )
        sources.append(
            CorpusSource(
                source_id=source_id,
                path=source_path,
                sha256=observed_hash,
                corpus_bytes=corpus_bytes,
                train_bytes=train_bytes,
                holdout_bytes=holdout_bytes,
            )
        )
        ids.add(source_id)
        paths.add(source_path)
        hashes.add(expected_hash)
    metadata = {
        "path": str(manifest_path),
        "schema": CORPUS_MANIFEST_SCHEMA,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return sources, metadata


def _direct_source(path: Path, *, holdout_bytes: int | None) -> tuple[list[CorpusSource], dict[str, object]]:
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise TrajectoryTrainingError(f"corpus source is unavailable: {source_path}")
    corpus_bytes = source_path.stat().st_size
    train_bytes, selected_holdout = _source_split(
        corpus_bytes,
        denominator=100,
        minimum_holdout_bytes=min(1 << 20, max(4, corpus_bytes // 10)),
        explicit_holdout_bytes=holdout_bytes,
    )
    digest = _sha256_file(source_path)
    return [
        CorpusSource(
            source_id="direct-corpus",
            path=source_path,
            sha256=digest,
            corpus_bytes=corpus_bytes,
            train_bytes=train_bytes,
            holdout_bytes=selected_holdout,
        )
    ], {
        "holdout_bytes": selected_holdout,
        "path": str(source_path),
        "schema": "cassi.qi-trajectory-direct-corpus.v1",
        "sha256": digest,
    }


def _episode_at(
    source: CorpusSource,
    *,
    offset: int,
    region_end: int,
    max_episode_bytes: int,
    codec: CassiFieldTextCodec,
) -> TrajectoryEpisode | None:
    with source.path.open("rb") as handle:
        handle.seek(offset)
        if offset > 0:
            handle.readline(max_episode_bytes + 1)
        start = handle.tell()
        if start >= region_end:
            return None
        payload = handle.readline(max_episode_bytes + 1)[:max_episode_bytes]
    payload = payload.rstrip(b"\r\n")
    if len(payload) < 8:
        return None
    try:
        payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    split = len(payload) // 2
    while split < len(payload) and payload[split] & 0xC0 == 0x80:
        split += 1
    if split < 2 or len(payload) - split < 2:
        return None
    prompt = payload[:split]
    continuation = payload[split:]
    events = codec.encode_training_exchange(prompt, continuation)
    return TrajectoryEpisode(
        source_id=source.source_id,
        path=source.path,
        offset=start,
        payload=payload,
        prompt=prompt,
        continuation=continuation,
        events=events,
    )


def _sample_episodes(
    source: CorpusSource,
    *,
    region_start: int,
    region_bytes: int,
    count: int,
    max_episode_bytes: int,
    codec: CassiFieldTextCodec,
) -> list[TrajectoryEpisode]:
    if isinstance(count, bool) or count < 1:
        raise TrajectoryTrainingError("episode count must be positive")
    region_end = region_start + region_bytes
    episodes: list[TrajectoryEpisode] = []
    seen: set[str] = set()
    attempts = max(count * 8, count)
    for index in range(attempts):
        fraction = (index + 0.5) / attempts
        offset = region_start + min(region_bytes - 1, int(fraction * region_bytes))
        episode = _episode_at(
            source,
            offset=offset,
            region_end=region_end,
            max_episode_bytes=max_episode_bytes,
            codec=codec,
        )
        if episode is None:
            continue
        digest = hashlib.sha256(episode.payload).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        episodes.append(episode)
        if len(episodes) == count:
            break
    if not episodes:
        episode = _episode_at(
            source,
            offset=region_start,
            region_end=region_end,
            max_episode_bytes=max_episode_bytes,
            codec=codec,
        )
        if episode is not None:
            episodes.append(episode)
    if not episodes:
        raise TrajectoryTrainingError(
            f"no valid UTF-8 trajectory episodes found in {source.source_id}"
        )
    return episodes


def _corpus_identity(
    sources: Sequence[CorpusSource],
    *,
    episodes_per_source: int,
    heldout_episodes_per_source: int,
    max_episode_bytes: int,
) -> str:
    return _canonical_sha256(
        {
            "episodes_per_source": episodes_per_source,
            "heldout_episodes_per_source": heldout_episodes_per_source,
            "max_episode_bytes": max_episode_bytes,
            "schema": CORPUS_IDENTITY_SCHEMA,
            "sources": [source.identity_dict() for source in sources],
        }
    )


def _evaluate(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    episodes: Sequence[TrajectoryEpisode],
) -> dict[str, object]:
    correct = 0
    total = 0
    by_source: dict[str, dict[str, int]] = {}
    for episode in episodes:
        episode_correct, episode_total = law.sequence_accuracy(state, episode.events)
        correct += episode_correct
        total += episode_total
        record = by_source.setdefault(episode.source_id, {"correct": 0, "total": 0})
        record["correct"] += episode_correct
        record["total"] += episode_total
    return {
        "accuracy": 0.0 if total == 0 else correct / total,
        "correct": correct,
        "total": total,
        "by_source": {
            source_id: {
                **record,
                "accuracy": 0.0 if record["total"] == 0 else record["correct"] / record["total"],
            }
            for source_id, record in sorted(by_source.items())
        },
    }


def _generation_examples(
    engine: CassiQiTextEngine,
    episodes: Sequence[TrajectoryEpisode],
    *,
    limit: int,
) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    for episode in episodes[:limit]:
        prompt = episode.prompt.decode("utf-8", errors="strict")
        expected = episode.continuation.decode("utf-8", errors="strict")
        result = engine.generate(
            engine.initial_state(),
            ({"role": "user", "content": prompt},),
        )
        examples.append(
            {
                "actual": result.text,
                "expected": expected,
                "prompt": prompt,
                "source_id": episode.source_id,
                "stop_reason": result.stop_reason,
            }
        )
    return examples


def _train_sources(
    sources: Sequence[CorpusSource],
    *,
    manifest_metadata: Mapping[str, object],
    config_path: Path,
    output_dir: Path,
    episodes_per_source: int,
    heldout_episodes_per_source: int,
    max_episode_bytes: int,
) -> dict[str, object]:
    started = time.perf_counter()
    config_path = Path(config_path).resolve()
    config = QiFieldConfig.from_dict(json.loads(config_path.read_text(encoding="utf-8")))
    controller = QiFieldController(config)
    law = CassiQiTrajectoryLaw(controller)
    codec = law.codec
    training_episodes: list[TrajectoryEpisode] = []
    heldout_episodes: list[TrajectoryEpisode] = []
    for source in sources:
        training_episodes.extend(
            _sample_episodes(
                source,
                region_start=0,
                region_bytes=source.train_bytes,
                count=episodes_per_source,
                max_episode_bytes=max_episode_bytes,
                codec=codec,
            )
        )
        heldout_episodes.extend(
            _sample_episodes(
                source,
                region_start=source.train_bytes,
                region_bytes=source.holdout_bytes,
                count=heldout_episodes_per_source,
                max_episode_bytes=max_episode_bytes,
                codec=codec,
            )
        )
    state = law.initial_state()
    for episode in training_episodes:
        state = law.learn_sequence(state, episode.events)
    state = law.reset_context(state)
    corpus_identity = _corpus_identity(
        sources,
        episodes_per_source=episodes_per_source,
        heldout_episodes_per_source=heldout_episodes_per_source,
        max_episode_bytes=max_episode_bytes,
    )
    output_dir = Path(output_dir).resolve()
    checkpoint_path = output_dir / "field-state.pt"
    training_event_count = sum(len(episode.events) for episode in training_episodes)
    checkpoint_sha256 = save_trajectory_checkpoint(
        checkpoint_path,
        law=law,
        state=state,
        corpus_identity=corpus_identity,
        training_episode_count=len(training_episodes),
        training_event_count=training_event_count,
    )
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=checkpoint_path,
        max_output_symbols=max_episode_bytes,
    )
    receipt: dict[str, object] = {
        "checkpoint": {
            "memory_sha256": law.memory_sha256(state),
            "path": str(checkpoint_path),
            "sha256": checkpoint_sha256,
            "shape": list(state.field.shape),
            "tensor_count": 1,
        },
        "config": {
            "path": str(config_path),
            "sha256": _sha256_file(config_path),
        },
        "corpus": {
            "identity": corpus_identity,
            "identity_schema": CORPUS_IDENTITY_SCHEMA,
            "manifest": dict(manifest_metadata),
            "sources": [
                {
                    **source.identity_dict(),
                    "path": str(source.path),
                }
                for source in sources
            ],
        },
        "experience": {
            "heldout_episode_count": len(heldout_episodes),
            "heldout_episodes": [episode.descriptor() for episode in heldout_episodes],
            "max_episode_bytes": max_episode_bytes,
            "training_episode_count": len(training_episodes),
            "training_episodes": [episode.descriptor() for episode in training_episodes],
            "training_event_count": training_event_count,
        },
        "generation": {
            "heldout_examples": _generation_examples(engine, heldout_episodes, limit=2),
            "training_examples": _generation_examples(engine, training_episodes, limit=4),
        },
        "heldout": _evaluate(law, state, heldout_episodes),
        "schema": TRAINING_RECEIPT_SCHEMA,
        "software": {
            "language_source_sha256": _sha256_file(_ROOT / "cassi_field_language.py"),
            "trainer_source_sha256": _sha256_file(_ROOT / "training" / "train_cassi_field_language.py"),
        },
        "timing_seconds": time.perf_counter() - started,
        "training": _evaluate(law, state, training_episodes),
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _atomic_write_json(output_dir / "training-receipt.json", receipt)
    return receipt


def train_manifest(
    manifest_path: Path,
    config_path: Path,
    output_dir: Path,
    *,
    episodes_per_source: int = DEFAULT_EPISODES_PER_SOURCE,
    heldout_episodes_per_source: int = DEFAULT_HELDOUT_EPISODES_PER_SOURCE,
    max_episode_bytes: int = DEFAULT_MAX_EPISODE_BYTES,
) -> dict[str, object]:
    sources, metadata = _manifest_sources(manifest_path)
    return _train_sources(
        sources,
        manifest_metadata=metadata,
        config_path=config_path,
        output_dir=output_dir,
        episodes_per_source=episodes_per_source,
        heldout_episodes_per_source=heldout_episodes_per_source,
        max_episode_bytes=max_episode_bytes,
    )


def train_corpus(
    corpus_path: Path,
    config_path: Path,
    output_dir: Path,
    *,
    holdout_bytes: int | None = None,
    episodes_per_source: int = DEFAULT_EPISODES_PER_SOURCE,
    heldout_episodes_per_source: int = DEFAULT_HELDOUT_EPISODES_PER_SOURCE,
    max_episode_bytes: int = DEFAULT_MAX_EPISODE_BYTES,
) -> dict[str, object]:
    sources, metadata = _direct_source(corpus_path, holdout_bytes=holdout_bytes)
    return _train_sources(
        sources,
        manifest_metadata=metadata,
        config_path=config_path,
        output_dir=output_dir,
        episodes_per_source=episodes_per_source,
        heldout_episodes_per_source=heldout_episodes_per_source,
        max_episode_bytes=max_episode_bytes,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--manifest", type=Path)
    source.add_argument("--corpus", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--holdout-bytes", type=int)
    parser.add_argument("--episodes-per-source", type=int, default=DEFAULT_EPISODES_PER_SOURCE)
    parser.add_argument(
        "--heldout-episodes-per-source",
        type=int,
        default=DEFAULT_HELDOUT_EPISODES_PER_SOURCE,
    )
    parser.add_argument("--max-episode-bytes", type=int, default=DEFAULT_MAX_EPISODE_BYTES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.holdout_bytes is not None and args.corpus is None:
        raise SystemExit("--holdout-bytes requires --corpus")
    if any(
        isinstance(value, bool) or int(value) < 1
        for value in (
            args.episodes_per_source,
            args.heldout_episodes_per_source,
            args.max_episode_bytes,
        )
    ):
        raise SystemExit("episode counts and byte limits must be positive integers")
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
    try:
        if args.corpus is not None:
            receipt = train_corpus(
                args.corpus,
                args.config,
                args.output_dir,
                holdout_bytes=args.holdout_bytes,
                episodes_per_source=args.episodes_per_source,
                heldout_episodes_per_source=args.heldout_episodes_per_source,
                max_episode_bytes=args.max_episode_bytes,
            )
        else:
            receipt = train_manifest(
                DEFAULT_MANIFEST if args.manifest is None else args.manifest,
                args.config,
                args.output_dir,
                episodes_per_source=args.episodes_per_source,
                heldout_episodes_per_source=args.heldout_episodes_per_source,
                max_episode_bytes=args.max_episode_bytes,
            )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise SystemExit(f"trajectory training failed: {error}") from error
    print(
        json.dumps(
            {
                "checkpoint": receipt["checkpoint"],
                "generation": receipt["generation"],
                "heldout": receipt["heldout"],
                "timing_seconds": receipt["timing_seconds"],
                "training": receipt["training"],
            },
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
