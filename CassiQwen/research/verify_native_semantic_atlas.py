#!/usr/bin/env python3
"""Independently verify a four-axis native semantic atlas receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
_CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))


from cassi_llama_capture import load_capture_receipt
from cassi_model_instrument import sha256_path


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "semantic-atlas-manifest.json"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"artifact escapes atlas root: {relative}") from exc
    return candidate


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise RuntimeError("semantic atlas manifest must be an object")
    if manifest.get("schema") != "cassi.native-semantic-atlas.v1":
        raise RuntimeError("semantic atlas manifest schema mismatch")
    capture_contract = manifest.get("capture_contract")
    analysis_contract = manifest.get("analysis_contract")
    if not isinstance(capture_contract, Mapping) or not isinstance(analysis_contract, Mapping):
        raise RuntimeError("semantic atlas contracts are missing")
    training_count = int(capture_contract.get("training_pairs_per_axis", -1))
    holdout_count = int(capture_contract.get("holdout_pairs_per_axis", -1))
    if training_count < 1 or holdout_count != 1:
        raise RuntimeError("semantic atlas pair contract is invalid")
    axes = manifest.get("axes")
    if not isinstance(axes, list) or not axes:
        raise RuntimeError("semantic atlas requires at least one axis")
    seen_axes: set[str] = set()
    for axis in axes:
        if not isinstance(axis, Mapping):
            raise RuntimeError("semantic atlas axis is malformed")
        axis_id = axis.get("axis_id")
        if not isinstance(axis_id, str) or not axis_id or axis_id in seen_axes:
            raise RuntimeError("semantic atlas axis IDs are invalid")
        seen_axes.add(axis_id)
        pairs = axis.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != training_count + holdout_count:
            raise RuntimeError(f"semantic atlas axis {axis_id} pair count mismatch")
        pair_ids: set[str] = set()
        for pair in pairs:
            if not isinstance(pair, Mapping):
                raise RuntimeError(f"semantic atlas axis {axis_id} pair is malformed")
            pair_id = pair.get("pair_id")
            if not isinstance(pair_id, str) or not pair_id or pair_id in pair_ids:
                raise RuntimeError(f"semantic atlas axis {axis_id} pair IDs are invalid")
            pair_ids.add(pair_id)
        if not str(pairs[-1]["pair_id"]).endswith("-holdout"):
            raise RuntimeError(f"semantic atlas axis {axis_id} holdout pair is not last")
    controls = manifest.get("negative_controls", [])
    if not isinstance(controls, list):
        raise RuntimeError("semantic atlas negative controls are malformed")
    seen_controls: set[str] = set()
    for control in controls:
        if not isinstance(control, Mapping):
            raise RuntimeError("semantic atlas negative control is malformed")
        control_id = control.get("control_id")
        prompt = control.get("prompt")
        if not isinstance(control_id, str) or not control_id or control_id in seen_controls:
            raise RuntimeError("semantic atlas negative control IDs are invalid")
        if not isinstance(prompt, str) or not prompt:
            raise RuntimeError(f"semantic atlas negative control {control_id} prompt is invalid")
        seen_controls.add(control_id)
    model_contract = manifest.get("model_contract")
    if model_contract is not None:
        if not isinstance(model_contract, Mapping):
            raise RuntimeError("semantic atlas model contract is malformed")
        for key in ("model_filename", "model_sha256", "quantization", "backend"):
            if not isinstance(model_contract.get(key), str) or not model_contract[key]:
                raise RuntimeError(f"semantic atlas model contract field is invalid: {key}")
        if not isinstance(model_contract.get("gpu_layers"), int) or int(model_contract["gpu_layers"]) < 0:
            raise RuntimeError("semantic atlas model contract gpu_layers is invalid")

    if float(analysis_contract.get("rank_relative_tolerance", 0.0)) <= 0.0:
        raise RuntimeError("semantic atlas rank tolerance is invalid")
    if int(analysis_contract.get("required_distinct_rank", 0)) <= 0:
        raise RuntimeError("semantic atlas distinct-rank requirement is invalid")
    if int(analysis_contract.get("required_duplicate_rank", 0)) <= 0:
        raise RuntimeError("semantic atlas duplicate-rank requirement is invalid")
    return dict(manifest)


def _read_f32(root: Path, descriptor: Mapping[str, Any]) -> np.ndarray:
    path = _safe(root, str(descriptor["path"]))
    raw = path.read_bytes()
    if _sha_bytes(raw) != descriptor.get("sha256"):
        raise RuntimeError(f"artifact digest mismatch: {descriptor['path']}")
    if len(raw) != int(descriptor["bytes"]) or len(raw) % 4 != 0:
        raise RuntimeError(f"artifact size mismatch: {descriptor['path']}")
    values = np.frombuffer(raw, dtype="<f4").copy()
    if int(descriptor["elements"]) != values.size:
        raise RuntimeError(f"artifact element mismatch: {descriptor['path']}")
    if list(descriptor.get("shape", [values.size])) != [values.size] and len(descriptor.get("shape", [])) == 1:
        raise RuntimeError(f"artifact shape mismatch: {descriptor['path']}")
    if not np.isfinite(values).all():
        raise RuntimeError(f"artifact contains non-finite values: {descriptor['path']}")
    return values


def _spectrum(matrix: np.ndarray, relative_tolerance: float) -> dict[str, Any]:
    gram = np.asarray(matrix, dtype=np.float64) @ np.asarray(matrix, dtype=np.float64).T
    eigenvalues = np.linalg.eigvalsh(gram)
    singular_values = np.sqrt(np.clip(eigenvalues, 0.0, None))[::-1]
    tolerance = float(singular_values[0] * relative_tolerance) if singular_values.size else 0.0
    rank = int(np.count_nonzero(singular_values > tolerance))
    return {
        "rows": int(matrix.shape[0]),
        "columns": int(matrix.shape[1]),
        "rank": rank,
        "relative_tolerance": relative_tolerance,
        "absolute_tolerance": tolerance,
        "singular_values": [float(value) for value in singular_values],
        "sigma_min": float(singular_values[-1]) if singular_values.size else 0.0,
    }


def _axis_measurement(
    axis: Mapping[str, Any],
    capture_values: Mapping[str, np.ndarray],
) -> tuple[dict[str, Any], list[np.ndarray], np.ndarray, np.ndarray]:
    axis_id = str(axis["axis_id"])
    pairs = list(axis["pairs"])
    train_pairs = pairs[:-1]
    holdout_pair = pairs[-1]
    train_diffs = [
        capture_values[f"{axis_id}__{pair['pair_id']}__a"]
        - capture_values[f"{axis_id}__{pair['pair_id']}__b"]
        for pair in train_pairs
    ]
    train_norms = [float(np.linalg.norm(diff)) for diff in train_diffs]
    if any(norm <= 0.0 for norm in train_norms):
        raise RuntimeError(f"zero training difference for axis {axis_id}")
    raw_direction = np.mean(
        [diff / norm for diff, norm in zip(train_diffs, train_norms)],
        axis=0,
    )
    direction_norm = float(np.linalg.norm(raw_direction))
    if direction_norm <= 0.0:
        raise RuntimeError(f"zero axis direction for axis {axis_id}")
    direction = raw_direction / direction_norm
    holdout_diff = (
        capture_values[f"{axis_id}__{holdout_pair['pair_id']}__a"]
        - capture_values[f"{axis_id}__{holdout_pair['pair_id']}__b"]
    )
    holdout_norm = float(np.linalg.norm(holdout_diff))
    score = float(np.dot(holdout_diff, direction))
    result = {
        "axis_id": axis_id,
        "pole_a": axis["pole_a"],
        "pole_b": axis["pole_b"],
        "train_pair_ids": [pair["pair_id"] for pair in train_pairs],
        "holdout_pair_id": holdout_pair["pair_id"],
        "training_difference_norms": train_norms,
        "holdout_difference_norm": holdout_norm,
        "axis_direction_norm_before_normalization": direction_norm,
        "holdout_score": score,
        "swapped_holdout_score": -score,
        "predicted_pole": "pole_a" if score > 0.0 else "pole_b",
        "expected_pole": "pole_a",
        "passed": score > 0.0,
    }
    return result, train_diffs, holdout_diff, direction


def _compare_float(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1.0e-5, abs_tol=1.0e-5):
        raise RuntimeError(f"{label} mismatch: {actual} != {expected}")


def _verify(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    receipt_path = root / "semantic-atlas-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "cassi.native-semantic-atlas-receipt.v1":
        raise RuntimeError("semantic atlas receipt schema mismatch")
    receipt_body = {
        key: value
        for key, value in receipt.items()
        if key != "content_sha256"
    }
    if receipt.get("content_sha256") != _sha_bytes(_canonical(receipt_body)):
        raise RuntimeError("semantic atlas receipt content digest mismatch")
    if receipt.get("verdict") != "PASS":
        raise RuntimeError("semantic atlas receipt did not pass")
    manifest_path = Path(args.manifest).resolve()
    manifest = _load_manifest(manifest_path)
    manifest_digest = _sha_bytes(_canonical(manifest))
    receipt_manifest = receipt.get("manifest")
    if (
        not isinstance(receipt_manifest, Mapping)
        or receipt_manifest.get("sha256") != manifest_digest
        or receipt_manifest.get("path") != manifest_path.name
    ):
        raise RuntimeError("semantic atlas manifest binding mismatch")
    if receipt.get("model_sha256") != sha256_path(Path(args.model).resolve()):
        raise RuntimeError("semantic atlas model digest mismatch")

    captures = receipt.get("captures")
    expected_capture_count = (
        len(manifest["axes"])
        * (
            int(manifest["capture_contract"]["training_pairs_per_axis"])
            + int(manifest["capture_contract"]["holdout_pairs_per_axis"])
        )
        * 2
        + len(manifest.get("negative_controls", [])) * 2
    )
    if not isinstance(captures, list) or len(captures) != expected_capture_count:
        raise RuntimeError("semantic atlas capture count mismatch")
    capture_values: dict[str, np.ndarray] = {}
    model_fingerprint: str | None = None
    layer: int | None = None
    model_identity: Mapping[str, Any] | None = None
    runtime_identity: Mapping[str, Any] | None = None
    for row in captures:
        if not isinstance(row, Mapping):
            raise RuntimeError("semantic atlas capture row is malformed")
        capture_id = str(row["capture_id"])
        capture_receipt_path = _safe(root, str(row["capture_receipt"]))
        native_capture = load_capture_receipt(capture_receipt_path)
        if native_capture.trace.trace_sha256 != row["trace_sha256"]:
            raise RuntimeError(f"capture trace digest mismatch: {capture_id}")
        if native_capture.trace.model.fingerprint != row["model_fingerprint"]:
            raise RuntimeError(f"capture model mismatch: {capture_id}")
        if native_capture.trace.prompt_sha256 != row["prompt_sha256"]:
            raise RuntimeError(f"capture prompt digest mismatch: {capture_id}")
        if native_capture.trace.layer != int(row["layer"]):
            raise RuntimeError(f"capture layer mismatch: {capture_id}")
        if native_capture.receipt.get("verdict") != "PASS" or not native_capture.receipt.get("parity", {}).get("pass"):
            raise RuntimeError(f"capture parity failed: {capture_id}")
        values = _read_f32(root, row["values"])
        if not np.array_equal(values, native_capture.trace.values.astype(np.float32, copy=False).reshape(-1)):
            raise RuntimeError(f"capture residual artifact mismatch: {capture_id}")
        if model_identity is None:
            candidate_model = native_capture.receipt.get("model")
            candidate_runtime = native_capture.receipt.get("runtime")
            if not isinstance(candidate_model, Mapping) or not isinstance(candidate_runtime, Mapping):
                raise RuntimeError("semantic atlas capture model identity is incomplete")
            model_identity = candidate_model
            runtime_identity = candidate_runtime
        capture_values[capture_id] = values
        if model_fingerprint is None:
            model_fingerprint = str(row["model_fingerprint"])
            layer = int(row["layer"])
        elif model_fingerprint != row["model_fingerprint"] or layer != int(row["layer"]):
            raise RuntimeError("semantic atlas capture identity is not fixed")
    expected_negative_controls: list[dict[str, Any]] = []
    if model_identity is None or runtime_identity is None:
        raise RuntimeError("semantic atlas capture identity is missing")
    model_contract = manifest.get("model_contract")
    if isinstance(model_contract, Mapping):
        if Path(args.model).name != model_contract["model_filename"]:
            raise RuntimeError("semantic atlas model filename contract mismatch")
        if str(receipt["model_sha256"]) != model_contract["model_sha256"]:
            raise RuntimeError("semantic atlas model digest contract mismatch")
        if model_identity.get("quantization") != model_contract["quantization"]:
            raise RuntimeError("semantic atlas quantization contract mismatch")
        if model_identity.get("backend") != model_contract["backend"]:
            raise RuntimeError("semantic atlas backend contract mismatch")
        if int(runtime_identity.get("gpu_layers", -1)) != int(model_contract["gpu_layers"]):
            raise RuntimeError("semantic atlas gpu layer contract mismatch")

    for control in manifest.get("negative_controls", []):
        control_id = str(control["control_id"])
        left_id = f"control__{control_id}__a"
        right_id = f"control__{control_id}__b"
        left = capture_values[left_id]
        right = capture_values[right_id]
        difference_norm = float(np.linalg.norm(left - right))
        expected_negative_controls.append(
            {
                "control_id": control_id,
                "prompt_sha256": _sha_bytes(str(control["prompt"]).encode("utf-8")),
                "a_capture_id": left_id,
                "b_capture_id": right_id,
                "difference_norm": difference_norm,
                "passed": bool(np.array_equal(left, right)),
            }
        )
    actual_negative_controls = receipt.get("negative_controls", [])
    if not isinstance(actual_negative_controls, list) or len(actual_negative_controls) != len(expected_negative_controls):
        raise RuntimeError("semantic atlas negative-control count mismatch")
    for actual, expected in zip(actual_negative_controls, expected_negative_controls):
        if (
            not isinstance(actual, Mapping)
            or actual.get("control_id") != expected["control_id"]
            or actual.get("prompt_sha256") != expected["prompt_sha256"]
            or actual.get("a_capture_id") != expected["a_capture_id"]
            or actual.get("b_capture_id") != expected["b_capture_id"]
            or actual.get("passed") is not expected["passed"]
        ):
            raise RuntimeError(f"semantic atlas negative-control mismatch: {expected['control_id']}")
        _compare_float(
            float(actual["difference_norm"]),
            expected["difference_norm"],
            f"{expected['control_id']} difference norm",
        )
    if not all(control["passed"] for control in expected_negative_controls):
        raise RuntimeError("semantic atlas negative control fired")


    axis_results: list[dict[str, Any]] = []
    train_differences: list[np.ndarray] = []
    holdout_differences: list[np.ndarray] = []
    identity_rows: list[np.ndarray] = []
    axis_directions: list[np.ndarray] = []
    for axis in manifest["axes"]:
        result, train_diffs, holdout_diff, direction = _axis_measurement(axis, capture_values)
        axis_results.append(result)
        train_differences.extend(train_diffs)
        holdout_differences.append(holdout_diff)
        axis_directions.append(direction)
        holdout_pair = axis["pairs"][-1]
        axis_id = str(axis["axis_id"])
        identity_rows.extend(
            [
                capture_values[f"{axis_id}__{holdout_pair['pair_id']}__a"],
                capture_values[f"{axis_id}__{holdout_pair['pair_id']}__b"],
            ]
        )
    for actual, expected in zip(receipt["axes"], axis_results):
        if actual["axis_id"] != expected["axis_id"] or actual["predicted_pole"] != expected["predicted_pole"] or actual["passed"] is not expected["passed"]:
            raise RuntimeError(f"semantic atlas axis verdict mismatch: {expected['axis_id']}")
        for key in ("holdout_score", "swapped_holdout_score", "holdout_difference_norm"):
            _compare_float(float(actual[key]), float(expected[key]), f"{expected['axis_id']} {key}")

    distinct = np.stack(identity_rows, axis=0)
    shared = np.repeat(distinct[:1], distinct.shape[0], axis=0)
    scalar_factors = np.linspace(0.5, 2.0, distinct.shape[0], dtype=np.float32)
    scalar = distinct[:1] * scalar_factors[:, None]
    duplicate = np.vstack([distinct[:-1], distinct[:1]])
    relative_tolerance = float(manifest["analysis_contract"]["rank_relative_tolerance"])
    expected_controls = {
        "distinct_identity": _spectrum(distinct, relative_tolerance),
        "shared_identity": _spectrum(shared, relative_tolerance),
        "scalar_identity": _spectrum(scalar, relative_tolerance),
        "duplicate_identity": _spectrum(duplicate, relative_tolerance),
    }
    expected_controls["duplicate_identity"]["duplicate_pair_separation"] = float(np.linalg.norm(duplicate[0] - duplicate[-1]))
    for name, expected in expected_controls.items():
        actual = receipt["rank_controls"][name]
        if int(actual["rank"]) != expected["rank"]:
            raise RuntimeError(f"semantic atlas rank mismatch: {name}")
        if actual["passed"] is not True:
            raise RuntimeError(f"semantic atlas rank control failed: {name}")
        for left, right in zip(actual["singular_values"], expected["singular_values"]):
            _compare_float(float(left), float(right), f"{name} singular value")
    if receipt["rank_controls"]["duplicate_identity"]["duplicate_pair_separation"] != 0.0:
        raise RuntimeError("semantic atlas duplicate identity is not exact")

    expected_artifacts = {
        "train_differences": np.stack(train_differences),
        "holdout_differences": np.stack(holdout_differences),
        "holdout_identity_rows": distinct,
        "axis_directions": np.stack(axis_directions),
    }
    for name, expected in expected_artifacts.items():
        actual = _read_f32(root, receipt["artifacts"][name])
        if actual.shape != expected.astype(np.float32).reshape(-1).shape or not np.array_equal(actual, expected.astype(np.float32).reshape(-1)):
            raise RuntimeError(f"semantic atlas derived artifact mismatch: {name}")
    if not all(row["passed"] for row in axis_results):
        raise RuntimeError("semantic atlas holdout classification did not pass")
    return {
        "verdict": "PASS",
        "model_fingerprint": model_fingerprint,
        "layer": layer,
        "capture_count": len(captures),
        "axes": axis_results,
        "rank_controls": {
            name: {"rank": int(value["rank"]), "sigma_min": float(value["sigma_min"])}
            for name, value in expected_controls.items()
        },
        "negative_controls": expected_negative_controls,
        "manifest_sha256": manifest_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model", type=Path, default=_CASSIQWEN_ROOT / "Qwen3.5-0.8B-Q4_0.gguf")
    args = parser.parse_args()
    result = _verify(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
