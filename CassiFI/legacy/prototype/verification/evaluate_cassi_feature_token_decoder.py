"""Evaluate a compact feature-token decoder on held-out causal priors.

Only posterior-free predictions are scored: each candidate readout is produced
from the prior prediction made before the current observation is consumed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from typing import Any, Mapping, Sequence

import numpy as np
import torch

try:
    from .cassi_feature_token_decoder import (
        CassiFeatureTokenDecoder,
        CassiFeatureTokenDecoderConfig,
        CassiFeatureTokenDecoderError,
        load_feature_token_decoder_checkpoint,
    )
    from .cassi_feature_token_pipeline import (
        CandidateAssets,
        FeatureTokenPipelineError,
        Normalization,
        causal_prior_features,
        episode_records,
        load_candidate_assets,
        load_text_metadata,
        sha256_array,
        sha256_file,
        supervision_rows,
        target_ids,
    )
    from .cassi_world_model import CassiWorldModelError, load_world_model_checkpoint
    from .train_cassi_world_model import load_trajectory_npz
except ImportError:  # direct script execution
    from cassi_feature_token_decoder import (  # type: ignore[no-redef]
        CassiFeatureTokenDecoder,
        CassiFeatureTokenDecoderConfig,
        CassiFeatureTokenDecoderError,
        load_feature_token_decoder_checkpoint,
    )
    from cassi_feature_token_pipeline import (  # type: ignore[no-redef]
        CandidateAssets,
        FeatureTokenPipelineError,
        Normalization,
        causal_prior_features,
        episode_records,
        load_candidate_assets,
        load_text_metadata,
        sha256_array,
        sha256_file,
        supervision_rows,
        target_ids,
    )
    from cassi_world_model import CassiWorldModelError, load_world_model_checkpoint  # type: ignore[no-redef]
    from train_cassi_world_model import load_trajectory_npz  # type: ignore[no-redef]


EVALUATION_RECEIPT_SCHEMA = "cassi.feature-token-decoder.evaluation-receipt.v1"


def _fail(message: str) -> None:
    raise CassiFeatureTokenDecoderError(message)


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(f"{name} must be a positive integer")
    return int(value)


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{name} must be a non-negative integer")
    return int(value)


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        _fail(f"{label} must be finite")
    return result


def _parse_model_config(value: Mapping[str, Any]) -> CassiFeatureTokenDecoderConfig:
    if not isinstance(value, Mapping):
        _fail("model config must be a JSON object")
    payload: Any = value.get("decoder_config", value)
    if not isinstance(payload, Mapping):
        _fail("model config decoder_config must be an object")
    try:
        return CassiFeatureTokenDecoderConfig.from_dict(payload)
    except (TypeError, ValueError) as exc:
        _fail(f"invalid decoder model config: {exc}")
    raise AssertionError("unreachable")


def _load_json(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        _fail(f"model config does not exist: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid JSON constant {token}")),
        )
    except Exception as exc:
        _fail(f"model config is not valid JSON: {exc}")
    if not isinstance(value, Mapping):
        _fail("model config must contain a JSON object")
    return value


def _json_finite(value: Any, label: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(f"{label} contains a non-finite value")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _json_finite(item, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _json_finite(item, f"{label}[{index}]")
        return
    _fail(f"{label} contains unsupported value {type(value).__name__}")


def _asset_fingerprints(
    *,
    world_checkpoint: Path,
    data: Path,
    normalization: Path,
    metadata: Path,
    candidate_npz: Path,
    candidate_json: Path,
    assets: CandidateAssets,
) -> dict[str, Any]:
    return {
        "world_checkpoint_sha256": sha256_file(world_checkpoint),
        "data_sha256": sha256_file(data),
        "normalization_sha256": sha256_file(normalization),
        "metadata_sha256": sha256_file(metadata),
        "candidate_npz_sha256": sha256_file(candidate_npz),
        "candidate_json_sha256": sha256_file(candidate_json),
        "candidate_token_ids_sha256": sha256_array(assets.token_ids),
        "candidate_rows_sha256": sha256_array(assets.rows),
    }


def _load_context(
    *,
    world_checkpoint: Path,
    data: Path,
    normalization: Path,
    metadata: Path,
    candidate_npz: Path,
    candidate_json: Path,
    device: torch.device,
) -> tuple[Any, Any, Normalization, Mapping[str, Any], CandidateAssets, dict[str, Any]]:
    world_receipt = load_world_model_checkpoint(world_checkpoint, device=device)
    world = world_receipt.model.to(device=device)
    world.eval()
    for parameter in world.parameters():
        parameter.requires_grad_(False)
    config = world.config
    trajectory = load_trajectory_npz(data, config.observation_dim, config.action_dim, config.reward_dim)
    normalizer = Normalization.load(normalization)
    if normalizer.observation_mean.size != config.observation_dim:
        _fail("normalization observation dimension does not match the world model")
    if normalizer.action_mean.size != config.action_dim:
        _fail("normalization action dimension does not match the world model")
    metadata_value = load_text_metadata(metadata)
    assets = load_candidate_assets(candidate_npz, candidate_json)
    if assets.rows.shape[1] != config.observation_dim:
        _fail("candidate rows feature dimension does not match the world model observation dimension")
    if assets.token_ids.size < 10:
        _fail("evaluation requires at least 10 candidate rows for top-10 metrics")
    fingerprints = _asset_fingerprints(
        world_checkpoint=world_checkpoint,
        data=data,
        normalization=normalization,
        metadata=metadata,
        candidate_npz=candidate_npz,
        candidate_json=candidate_json,
        assets=assets,
    )
    return world, trajectory, normalizer, metadata_value, assets, fingerprints


def _checkpoint_compatible(
    checkpoint_metadata: Mapping[str, Any],
    *,
    fingerprints: Mapping[str, Any],
    world: Any,
    assets: CandidateAssets,
    data_sha256: str,
) -> None:
    if checkpoint_metadata.get("world_config_fingerprint") != world.config_fingerprint:
        _fail("decoder checkpoint world-model configuration is incompatible")
    expected = {
        "world_checkpoint_sha256": fingerprints["world_checkpoint_sha256"],
        "normalization_sha256": fingerprints["normalization_sha256"],
        "metadata_sha256": fingerprints["metadata_sha256"],
        "candidate_npz_sha256": fingerprints["candidate_npz_sha256"],
        "candidate_json_sha256": fingerprints["candidate_json_sha256"],
        "candidate_token_ids_sha256": fingerprints["candidate_token_ids_sha256"],
        "candidate_rows_sha256": fingerprints["candidate_rows_sha256"],
    }
    stored = checkpoint_metadata.get("fingerprints")
    if not isinstance(stored, Mapping):
        _fail("decoder checkpoint lacks compatibility fingerprints")
    for key, value in expected.items():
        if stored.get(key) != value:
            _fail(f"decoder checkpoint {key} does not match supplied assets")
    candidate_count = checkpoint_metadata.get("candidate_count")
    if candidate_count != int(assets.token_ids.size):
        _fail("decoder checkpoint candidate count does not match supplied assets")
    # A training checkpoint records the training archive digest.  Evaluation is
    # allowed to use a different held-out archive, but the field must exist and
    # be a valid digest so stale hand-written metadata cannot pass silently.
    stored_data = stored.get("data_sha256")
    if (
        not isinstance(stored_data, str)
        or len(stored_data) != 64
        or any(character not in "0123456789abcdef" for character in stored_data)
    ):
        _fail("decoder checkpoint has an invalid training data fingerprint")
    if (
        not isinstance(data_sha256, str)
        or len(data_sha256) != 64
        or any(character not in "0123456789abcdef" for character in data_sha256)
    ):
        _fail("evaluation data fingerprint is invalid")


def _metric_value(value: float | None) -> float | None:
    if value is None:
        return None
    return _finite(value, "metric")


def _summarize(
    scores: np.ndarray,
    labels: np.ndarray,
    token_ids: np.ndarray,
    *,
    target_count: int | None = None,
) -> dict[str, Any]:
    if scores.ndim != 2 or labels.ndim != 1 or scores.shape[0] != labels.shape[0]:
        _fail("metric scores and labels have incompatible shapes")
    if scores.shape[1] < 10:
        _fail("metric scores require at least 10 candidates")
    if not np.isfinite(scores).all():
        _fail("metric scores contain non-finite values")
    if labels.size and (np.any(labels < 0) or np.any(labels >= scores.shape[1])):
        _fail("metric labels are outside the candidate range")
    covered = int(labels.size)
    denominator = covered if target_count is None else int(target_count)
    if denominator < 0 or covered > denominator:
        _fail("metric target counts are inconsistent")
    result: dict[str, Any] = {
        "target_count": denominator,
        "covered_count": covered,
        "candidate_coverage": _metric_value(covered / denominator if denominator else None),
    }
    if covered == 0:
        result.update({"top1": None, "top5": None, "top10": None, "top1_accuracy": None, "top5_accuracy": None, "top10_accuracy": None, "mrr": None, "nll": None})
        return result
    reciprocal = 0.0
    nll = 0.0
    hits = {1: 0, 5: 0, 10: 0}
    ids = token_ids.astype(np.int64, copy=False)
    for row_index, label in enumerate(labels.tolist()):
        ranking = sorted(range(scores.shape[1]), key=lambda index: (-float(scores[row_index, index]), int(ids[index])))
        rank = ranking.index(int(label)) + 1
        reciprocal += 1.0 / rank
        for cutoff in hits:
            if rank <= cutoff:
                hits[cutoff] += 1
        row = scores[row_index]
        maximum = float(np.max(row))
        logsum = maximum + math.log(float(np.exp(row - maximum).sum()))
        nll += logsum - float(row[int(label)])
    metrics = {
        "top1": _metric_value(hits[1] / covered),
        "top5": _metric_value(hits[5] / covered),
        "top10": _metric_value(hits[10] / covered),
        "top1_accuracy": _metric_value(hits[1] / covered),
        "top5_accuracy": _metric_value(hits[5] / covered),
        "top10_accuracy": _metric_value(hits[10] / covered),
        "mrr": _metric_value(reciprocal / covered),
        "nll": _metric_value(nll / covered),
    }
    result.update(metrics)
    return result


def _representative(
    scores: np.ndarray,
    labels: np.ndarray,
    episode_indices: np.ndarray,
    time_indices: np.ndarray,
    target_ids_array: np.ndarray,
    assets: CandidateAssets,
) -> dict[str, Any] | None:
    if scores.shape[0] == 0:
        return None
    index = 0
    ranking = sorted(range(scores.shape[1]), key=lambda item: (-float(scores[index, item]), int(assets.token_ids[item])))
    label = int(labels[index])
    predictions = []
    for candidate_index in ranking[:10]:
        predictions.append(
            {
                "token_id": int(assets.token_ids[candidate_index]),
                "piece": assets.pieces[candidate_index],
                "logit": _finite(float(scores[index, candidate_index]), "representative logit"),
            }
        )
    target_token_id = int(target_ids_array[int(episode_indices[index]), int(time_indices[index])])
    return {
        "episode_index": int(episode_indices[index]),
        "time_index": int(time_indices[index]),
        "target": {"token_id": target_token_id, "piece": assets.pieces[label]},
        "predictions": predictions,
    }


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    temporary: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise CassiFeatureTokenDecoderError(f"could not atomically write evaluation receipt: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def evaluate(
    world_checkpoint: Path | str,
    data: Path | str,
    normalization: Path | str,
    metadata: Path | str,
    candidate_npz: Path | str,
    candidate_json: Path | str,
    output: Path | str,
    *,
    decoder_checkpoint: Path | str | None = None,
    model_config: CassiFeatureTokenDecoderConfig | Mapping[str, Any] | None = None,
    device: torch.device | str = "cpu",
    max_episodes: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Evaluate validation-only candidate metrics and atomically write JSON."""
    seed = _nonnegative_int("seed", seed)
    if max_episodes is not None:
        max_episodes = _positive_int("max_episodes", max_episodes)
    try:
        target_device = torch.device(device)
    except Exception as exc:
        _fail(f"invalid device: {exc}")
    world_path = Path(world_checkpoint)
    data_path = Path(data)
    normalization_path = Path(normalization)
    metadata_path = Path(metadata)
    candidate_npz_path = Path(candidate_npz)
    candidate_json_path = Path(candidate_json)
    output_path = Path(output)
    world, trajectory, normalizer, metadata_value, assets, fingerprints = _load_context(
        world_checkpoint=world_path,
        data=data_path,
        normalization=normalization_path,
        metadata=metadata_path,
        candidate_npz=candidate_npz_path,
        candidate_json=candidate_json_path,
        device=target_device,
    )
    all_records = episode_records(metadata_value, "validation", trajectory.batch_size, trajectory.horizon)
    selected_count = trajectory.batch_size if max_episodes is None else min(max_episodes, trajectory.batch_size)
    if selected_count < 1:
        _fail("validation archive contains no selected episodes")
    if selected_count != trajectory.batch_size:
        trajectory = trajectory.index_select(torch.arange(selected_count, dtype=torch.int64))
        records = all_records[:selected_count]
    else:
        records = all_records
    valid_numpy = trajectory.valid.detach().cpu().numpy().astype(np.bool_, copy=False)
    targets = target_ids(records, valid_numpy)
    prior = causal_prior_features(world, trajectory, device=target_device)
    covered_target_mask = (targets >= 0) & np.isin(targets, assets.token_ids)
    masked_targets = np.where(covered_target_mask, targets, -1).astype(np.int64, copy=False)
    features_raw, labels_numpy, episode_indices, time_indices = supervision_rows(
        prior,
        masked_targets,
        valid_numpy,
        normalizer,
        assets.token_ids,
    )
    target_count = int(np.count_nonzero(targets >= 0))
    covered_count = int(np.count_nonzero(covered_target_mask))
    if covered_count != int(labels_numpy.size):
        _fail("candidate coverage and supervision rows disagree")
    config: CassiFeatureTokenDecoderConfig
    decoder_sha256: str | None = None
    if decoder_checkpoint is not None:
        decoder_path = Path(decoder_checkpoint)
        checkpoint = load_feature_token_decoder_checkpoint(decoder_path, device=target_device)
        config = checkpoint.config
        _checkpoint_compatible(
            checkpoint.metadata,
            fingerprints=fingerprints,
            world=world,
            assets=assets,
            data_sha256=fingerprints["data_sha256"],
        )
        decoder = checkpoint.model
        decoder_sha256 = checkpoint.sha256
    else:
        if model_config is None:
            _fail("decoder-checkpoint is required unless model-config is supplied")
        config = model_config if isinstance(model_config, CassiFeatureTokenDecoderConfig) else _parse_model_config(model_config)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        decoder = CassiFeatureTokenDecoder(config).to(device=target_device)
    if config.feature_dim != int(assets.rows.shape[1]) or config.feature_dim != int(features_raw.shape[1]):
        _fail("decoder feature dimension does not match candidate rows and prior features")
    candidate_rows = torch.from_numpy(np.ascontiguousarray(assets.rows, dtype=np.float32)).to(device=target_device)
    decoder = decoder.to(device=target_device)
    decoder.eval()
    scores_chunks: list[np.ndarray] = []
    feature_tensor = torch.from_numpy(features_raw).to(device=target_device)
    with torch.no_grad():
        for offset in range(0, feature_tensor.shape[0], 1024):
            logits = decoder.logits(feature_tensor[offset : offset + 1024], candidate_rows)
            chunk = logits.detach().cpu().numpy().astype(np.float64, copy=False)
            if not np.isfinite(chunk).all():
                _fail("decoder evaluation logits are non-finite")
            scores_chunks.append(chunk)
    scores = np.concatenate(scores_chunks, axis=0) if scores_chunks else np.empty((0, assets.token_ids.size), dtype=np.float64)
    labels = labels_numpy.astype(np.int64, copy=False)
    global_metrics = _summarize(scores, labels, assets.token_ids, target_count=target_count)
    horizon_buckets: dict[str, Any] = {}
    for horizon_index in range(trajectory.horizon):
        selected = time_indices == horizon_index
        bucket_target_count = int(np.count_nonzero((targets[:, horizon_index] >= 0)))
        horizon_buckets[str(horizon_index)] = _summarize(
            scores[selected],
            labels[selected],
            assets.token_ids,
            target_count=bucket_target_count,
        )
    shuffled_metrics: dict[str, Any]
    if labels.size:
        permutation = np.random.default_rng(seed).permutation(labels.size)
        shuffled_metrics = _summarize(scores, labels[permutation], assets.token_ids, target_count=target_count)
    else:
        shuffled_metrics = _summarize(scores, labels, assets.token_ids, target_count=target_count)
    receipt: dict[str, Any] = {
        "schema": EVALUATION_RECEIPT_SCHEMA,
        "status": "ok",
        "world_checkpoint": str(world_path),
        "decoder_checkpoint": str(decoder_checkpoint) if decoder_checkpoint is not None else None,
        "data": str(data_path),
        "normalization": str(normalization_path),
        "metadata": str(metadata_path),
        "candidate_npz": str(candidate_npz_path),
        "candidate_json": str(candidate_json_path),
        "decoder_checkpoint_sha256": decoder_sha256,
        "world_config_fingerprint": world.config_fingerprint,
        "decoder_config": config.to_dict(),
        "decoder_config_fingerprint": config.fingerprint,
        "fingerprints": fingerprints,
        "evaluation": {
            "split": "validation",
            "episodes": int(selected_count),
            "horizon": int(trajectory.horizon),
            "seed": int(seed),
            "device": str(target_device),
        },
        "candidate_count": int(assets.token_ids.size),
        "metrics": global_metrics,
        "exact_horizon_buckets": horizon_buckets,
        "shuffled_target_control": shuffled_metrics,
        "representative": _representative(scores, labels, episode_indices, time_indices, targets, assets),
    }
    _json_finite(receipt, "evaluation receipt")
    _atomic_json(output_path, receipt)
    receipt["output"] = str(output_path)
    receipt["output_sha256"] = sha256_file(output_path)
    return receipt


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-checkpoint", type=Path, required=True, help="frozen world-model checkpoint")
    parser.add_argument("--decoder-checkpoint", type=Path, default=None, help="trained decoder checkpoint")
    parser.add_argument("--model-config", type=Path, default=None, help="decoder config JSON for an untrained control")
    parser.add_argument("--data", type=Path, required=True, help="strict validation trajectory .npz")
    parser.add_argument("--normalization", type=Path, required=True, help="strict normalization.npz")
    parser.add_argument("--metadata", type=Path, required=True, help="strict text-world metadata JSON")
    parser.add_argument("--candidate-npz", type=Path, required=True, help="frozen candidate rows .npz")
    parser.add_argument("--candidate-json", type=Path, required=True, help="candidate manifest JSON")
    parser.add_argument("--output", type=Path, required=True, help="evaluation receipt JSON")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config_value = _load_json(args.model_config) if args.model_config is not None else None
        receipt = evaluate(
            args.world_checkpoint,
            args.data,
            args.normalization,
            args.metadata,
            args.candidate_npz,
            args.candidate_json,
            args.output,
            decoder_checkpoint=args.decoder_checkpoint,
            model_config=config_value,
            device=args.device,
            max_episodes=args.max_episodes,
            seed=args.seed,
        )
    except (CassiFeatureTokenDecoderError, FeatureTokenPipelineError, CassiWorldModelError, OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


__all__ = ["evaluate", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
