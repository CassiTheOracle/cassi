"""Build bounded frozen Qwen candidate-token assets for the feature decoder.

The module is import-safe: Qwen/llama.cpp loading occurs only when ``main``
runs and the explicit build function reaches ``extract_candidate_rows``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .cassi_feature_token_pipeline import (
        DEFAULT_VOCABULARY_SIZE,
        EXPECTED_FEATURE_DIMENSION,
        FEATURE_TOKEN_ASSET_SCHEMA,
        FeatureTokenPipelineError,
        candidate_lexicon,
        episode_records,
        extract_candidate_rows,
        load_text_metadata,
        save_candidate_assets,
        sha256_array,
        sha256_file,
    )
except ImportError:  # direct ``python CassiQwen/...py`` execution
    from cassi_feature_token_pipeline import (  # type: ignore
        DEFAULT_VOCABULARY_SIZE,
        EXPECTED_FEATURE_DIMENSION,
        FEATURE_TOKEN_ASSET_SCHEMA,
        FeatureTokenPipelineError,
        candidate_lexicon,
        episode_records,
        extract_candidate_rows,
        load_text_metadata,
        save_candidate_assets,
        sha256_array,
        sha256_file,
    )


def _fail(message: str) -> None:
    raise FeatureTokenPipelineError(message)


def _positive(value: int, label: str) -> int:
    if isinstance(value, bool) or value < 1:
        _fail(f"{label} must be a positive integer")
    return int(value)


def _records_for_split(metadata: Mapping[str, Any], split: str) -> list[Mapping[str, Any]]:
    splits = metadata.get("splits")
    if not isinstance(splits, Mapping):
        _fail("text metadata must contain a splits object")
    split_info = splits.get(split)
    if not isinstance(split_info, Mapping):
        _fail(f"metadata has no configuration for split {split!r}")
    episodes = split_info.get("episodes")
    horizon = split_info.get("horizon")
    if isinstance(episodes, bool) or not isinstance(episodes, int):
        _fail(f"metadata split {split!r} has an invalid episode count")
    if isinstance(horizon, bool) or not isinstance(horizon, int):
        _fail(f"metadata split {split!r} has an invalid horizon")
    return episode_records(metadata, split, _positive(episodes, f"{split} episodes"), _positive(horizon, f"{split} horizon"))


def build_candidate_assets(
    *,
    metadata_path: str | Path,
    split: str,
    model_path: str | Path,
    dll_path: str | Path | None,
    candidate_npz: str | Path,
    candidate_json: str | Path,
    vocabulary_size: int = DEFAULT_VOCABULARY_SIZE,
    expected_feature_dim: int = EXPECTED_FEATURE_DIMENSION,
) -> dict[str, Any]:
    """Build and atomically persist one exact metadata-split candidate lexicon."""
    vocabulary_size = _positive(vocabulary_size, "vocabulary_size")
    expected_feature_dim = _positive(expected_feature_dim, "expected_feature_dim")
    if expected_feature_dim != EXPECTED_FEATURE_DIMENSION:
        _fail(
            f"frozen Qwen output dimension is {EXPECTED_FEATURE_DIMENSION}; "
            f"expected_feature_dim {expected_feature_dim} is incompatible"
        )
    metadata_file = Path(metadata_path)
    model_file = Path(model_path)
    if not metadata_file.is_file():
        _fail(f"metadata file does not exist: {metadata_file}")
    if not model_file.is_file():
        _fail(f"model file does not exist: {model_file}")
    dll_file: Path | None = None
    if dll_path is not None:
        dll_file = Path(dll_path)
        if not dll_file.is_file():
            _fail(f"DLL file does not exist: {dll_file}")

    metadata = load_text_metadata(metadata_file)
    records = _records_for_split(metadata, split)
    if not records:
        _fail(f"metadata split {split!r} contains no records")
    token_ids, pieces = candidate_lexicon(records, vocabulary_size=vocabulary_size)
    if token_ids.size == 0:
        _fail("candidate lexicon contains no token IDs")

    # The sole model-facing operation is deliberately after all metadata checks.
    rows = extract_candidate_rows(model_file, dll_file, token_ids)
    if rows.ndim != 2 or rows.shape != (token_ids.size, expected_feature_dim):
        _fail(f"extracted candidate rows have incompatible shape {rows.shape}")

    valid_steps = 0
    target_steps = 0
    candidate_mentions = 0
    for row in records:
        targets = row.get("target_next_token_ids")
        teachers = row.get("teacher_top_candidates")
        if not isinstance(targets, Sequence) or isinstance(targets, (str, bytes, bytearray)):
            _fail("record target_next_token_ids must be a sequence")
        if not isinstance(teachers, Sequence) or isinstance(teachers, (str, bytes, bytearray)):
            _fail("record teacher_top_candidates must be a sequence")
        valid_steps += sum(value is not None for value in targets)
        target_steps += sum(value is not None for value in targets)
        candidate_mentions += sum(len(item) for item in teachers if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)))
    metadata_sha = sha256_file(metadata_file)
    model_sha = sha256_file(model_file)
    asset_metadata = {
        "schema": FEATURE_TOKEN_ASSET_SCHEMA,
        "source_metadata_sha256": metadata_sha,
        "model_sha256": model_sha,
        "split": split,
        "feature_dim": expected_feature_dim,
        "vocabulary_size": vocabulary_size,
        "candidate_count": int(token_ids.size),
        "coverage": {
            "episodes": len(records),
            "target_steps": target_steps,
            "valid_target_steps": valid_steps,
            "teacher_candidate_mentions": candidate_mentions,
        },
        "token_ids_sha256": sha256_array(token_ids),
        "rows_sha256": sha256_array(rows),
    }
    save_candidate_assets(candidate_npz, candidate_json, token_ids, rows, pieces, asset_metadata)
    return {
        "schema": FEATURE_TOKEN_ASSET_SCHEMA,
        "split": split,
        "candidate_count": int(token_ids.size),
        "feature_dim": expected_feature_dim,
        "vocabulary_size": vocabulary_size,
        "coverage": asset_metadata["coverage"],
        "candidate_npz": str(candidate_npz),
        "candidate_json": str(candidate_json),
        "source_metadata_sha256": metadata_sha,
        "model_sha256": model_sha,
        "rows_sha256": asset_metadata["rows_sha256"],
        "token_ids_sha256": asset_metadata["token_ids_sha256"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build sorted, train-split (or explicitly selected split) frozen Qwen candidate rows and manifest assets."
    )
    parser.add_argument("--metadata", required=True, metavar="PATH", help="text-world metadata.json")
    parser.add_argument("--split", default="train", choices=("train", "validation", "tiny"), help="metadata split (default: train; validation must be explicit)")
    parser.add_argument("--model-path", required=True, metavar="PATH", help="frozen Qwen GGUF model path")
    parser.add_argument("--dll-path", metavar="PATH", help="optional llama.cpp DLL path")
    parser.add_argument("--candidate-npz", required=True, metavar="PATH", help="output candidate row archive")
    parser.add_argument("--candidate-json", required=True, metavar="PATH", help="output candidate manifest")
    parser.add_argument("--vocabulary-size", type=int, default=DEFAULT_VOCABULARY_SIZE, help=f"token vocabulary size (default: {DEFAULT_VOCABULARY_SIZE})")
    parser.add_argument("--expected-feature-dim", type=int, default=EXPECTED_FEATURE_DIMENSION, help=f"expected frozen output width (default: {EXPECTED_FEATURE_DIMENSION})")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        summary = build_candidate_assets(
            metadata_path=args.metadata,
            split=args.split,
            model_path=args.model_path,
            dll_path=args.dll_path,
            candidate_npz=args.candidate_npz,
            candidate_json=args.candidate_json,
            vocabulary_size=args.vocabulary_size,
            expected_feature_dim=args.expected_feature_dim,
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (FeatureTokenPipelineError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
