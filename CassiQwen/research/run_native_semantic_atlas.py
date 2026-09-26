#!/usr/bin/env python3
"""Capture and measure a held-out four-axis native semantic atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
_CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))


from cassi_llama_capture import NativeLlamaSession
from cassi_model_instrument import sha256_path


HERE = Path(__file__).resolve().parent
_CASSIQWEN_ROOT = HERE.parent
DEFAULT_MODEL = _CASSIQWEN_ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
DEFAULT_RUNTIME = _CASSIQWEN_ROOT / "native/llama.cpp/b8/bin/Release"
DEFAULT_EXECUTABLE = DEFAULT_RUNTIME / "cassi-qwen.exe"
CONTEXT_TOKENS = 256
GPU_LAYERS = 99
QUANTIZATION = "Q4_0"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _descriptor(path: Path, values: np.ndarray, root: Path) -> dict[str, Any]:
    return {
        "path": _relative(path, root),
        "sha256": sha256_path(path),
        "bytes": int(path.stat().st_size),
        "elements": int(values.size),
        "shape": list(values.shape),
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("semantic atlas manifest could not be loaded") from exc
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
        if not isinstance(axis.get("pole_a"), str) or not isinstance(axis.get("pole_b"), str):
            raise RuntimeError("semantic atlas axis poles are invalid")
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
            for prompt_key in ("a_prompt", "b_prompt"):
                if not isinstance(pair.get(prompt_key), str) or not pair[prompt_key]:
                    raise RuntimeError(f"semantic atlas pair {pair_id} prompt is invalid")
        if not str(pairs[-1]["pair_id"]).endswith("-holdout"):
            raise RuntimeError(f"semantic atlas axis {axis_id} must end with a holdout pair")
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


def _capture_one(
    native: NativeLlamaSession,
    *,
    capture_id: str,
    prompt: str,
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    capture = native.capture(
        prompt=prompt,
        sequence_id=capture_id,
        output_dir=output_dir,
    )
    values = np.asarray(capture.trace.values, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise RuntimeError(f"capture {capture_id} residual is empty or non-finite")
    residual_path = output_dir / "atlas-residual.f32"
    values.tofile(residual_path)
    return {
        "capture_id": capture_id,
        "prompt": prompt,
        "prompt_sha256": _sha_bytes(prompt.encode("utf-8")),
        "trace_sha256": capture.trace.trace_sha256,
        "model_fingerprint": capture.trace.model.fingerprint,
        "layer": int(capture.trace.layer),
        "values": _descriptor(residual_path, values, root),
        "norm": float(np.linalg.norm(values)),
        "capture_receipt": _relative(output_dir / "capture-receipt.json", root),
        "capture_verdict": capture.receipt["verdict"],
        "capture_parity": capture.receipt["parity"],
    }


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


def _write_matrix(path: Path, matrix: np.ndarray, root: Path) -> dict[str, Any]:
    values = np.asarray(matrix, dtype=np.float32)
    values.tofile(path)
    descriptor = _descriptor(path, values, root)
    descriptor["dtype"] = "<f4"
    return descriptor

def _run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if root.exists():
        raise RuntimeError(f"atlas output already exists: {root}")
    root.mkdir(parents=True)
    manifest_path = Path(args.manifest).resolve()
    manifest = _load_manifest(manifest_path)
    model_path = Path(args.model).resolve()
    runtime_dir = Path(args.runtime).resolve()
    executable = Path(args.executable).resolve()
    for path in (model_path, runtime_dir, executable):
        if not path.exists():
            raise FileNotFoundError(path)
    model_contract = manifest.get("model_contract")
    if isinstance(model_contract, Mapping):
        if model_path.name != model_contract["model_filename"]:
            raise RuntimeError("semantic atlas model filename contract mismatch")
        if sha256_path(model_path) != model_contract["model_sha256"]:
            raise RuntimeError("semantic atlas model digest contract mismatch")
        if str(args.quantization) != model_contract["quantization"]:
            raise RuntimeError("semantic atlas quantization contract mismatch")
        if int(args.gpu_layers) != int(model_contract["gpu_layers"]):
            raise RuntimeError("semantic atlas backend layer contract mismatch")


    capture_rows: list[dict[str, Any]] = []
    capture_values: dict[str, np.ndarray] = {}
    with NativeLlamaSession(
        runtime_dir,
        model_path,
        gpu_layers=int(args.gpu_layers),
        context_tokens=int(args.context_tokens),
        quantization=str(args.quantization),
    ) as native:
        for axis in manifest["axes"]:
            axis_id = str(axis["axis_id"])
            for pair in axis["pairs"]:
                pair_id = str(pair["pair_id"])
                for side in ("a", "b"):
                    capture_id = f"{axis_id}__{pair_id}__{side}"
                    prompt = str(pair[f"{side}_prompt"])
                    row = _capture_one(
                        native,
                        capture_id=capture_id,
                        prompt=prompt,
                        output_dir=root / "captures" / capture_id,
                        root=root,
                    )
                    capture_rows.append(row)
                    capture_values[capture_id] = np.fromfile(
                        root / row["values"]["path"],
                        dtype="<f4",
                    )
        for control in manifest.get("negative_controls", []):
            control_id = str(control["control_id"])
            prompt = str(control["prompt"])
            for side in ("a", "b"):
                capture_id = f"control__{control_id}__{side}"
                row = _capture_one(
                    native,
                    capture_id=capture_id,
                    prompt=prompt,
                    output_dir=root / "captures" / capture_id,
                    root=root,
                )
                capture_rows.append(row)
                capture_values[capture_id] = np.fromfile(
                    root / row["values"]["path"],
                    dtype="<f4",
                )


    if not capture_rows:
        raise RuntimeError("semantic atlas captured no residuals")
    dimensions = {values.size for values in capture_values.values()}
    if len(dimensions) != 1:
        raise RuntimeError("semantic atlas residual dimensions disagree")
    dimension = dimensions.pop()
    relative_tolerance = float(manifest["analysis_contract"]["rank_relative_tolerance"])
    axis_results: list[dict[str, Any]] = []
    train_differences: list[np.ndarray] = []
    negative_control_results: list[dict[str, Any]] = []
    for control in manifest.get("negative_controls", []):
        control_id = str(control["control_id"])
        left = capture_values[f"control__{control_id}__a"]
        right = capture_values[f"control__{control_id}__b"]
        difference_norm = float(np.linalg.norm(left - right))
        negative_control_results.append(
            {
                "control_id": control_id,
                "prompt_sha256": _sha_bytes(str(control["prompt"]).encode("utf-8")),
                "a_capture_id": f"control__{control_id}__a",
                "b_capture_id": f"control__{control_id}__b",
                "difference_norm": difference_norm,
                "passed": bool(np.array_equal(left, right)),
            }
        )

    holdout_differences: list[np.ndarray] = []
    axis_directions: list[np.ndarray] = []
    identity_rows: list[np.ndarray] = []
    for axis in manifest["axes"]:
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
            raise RuntimeError(f"semantic atlas axis {axis_id} has a zero training difference")
        direction = np.mean(
            [diff / norm for diff, norm in zip(train_diffs, train_norms)],
            axis=0,
        )
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm <= 0.0:
            raise RuntimeError(f"semantic atlas axis {axis_id} has no direction")
        direction = direction / direction_norm
        axis_directions.append(direction)
        heldout_diff = (
            capture_values[f"{axis_id}__{holdout_pair['pair_id']}__a"]
            - capture_values[f"{axis_id}__{holdout_pair['pair_id']}__b"]
        )
        holdout_norm = float(np.linalg.norm(heldout_diff))
        score = float(np.dot(heldout_diff, direction))
        predicted = "pole_a" if score > 0.0 else "pole_b"
        axis_results.append(
            {
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
                "predicted_pole": predicted,
                "expected_pole": "pole_a",
                "passed": predicted == "pole_a",
            }
        )
        train_differences.extend(train_diffs)
        holdout_differences.append(heldout_diff)
        identity_rows.extend(
            [
                capture_values[f"{axis_id}__{holdout_pair['pair_id']}__a"],
                capture_values[f"{axis_id}__{holdout_pair['pair_id']}__b"],
            ]
        )

    distinct = np.stack(identity_rows, axis=0)
    shared = np.repeat(distinct[:1], distinct.shape[0], axis=0)
    scalar_factors = np.linspace(0.5, 2.0, distinct.shape[0], dtype=np.float32)
    scalar = distinct[:1] * scalar_factors[:, None]
    duplicate = np.vstack([distinct[:-1], distinct[:1]])
    rank_controls = {
        "distinct_identity": _spectrum(distinct, relative_tolerance),
        "shared_identity": _spectrum(shared, relative_tolerance),
        "scalar_identity": _spectrum(scalar, relative_tolerance),
        "duplicate_identity": _spectrum(duplicate, relative_tolerance),
    }
    rank_controls["distinct_identity"]["passed"] = (
        rank_controls["distinct_identity"]["rank"]
        == int(manifest["analysis_contract"]["required_distinct_rank"])
    )
    rank_controls["shared_identity"]["passed"] = rank_controls["shared_identity"]["rank"] == 1
    rank_controls["scalar_identity"]["passed"] = rank_controls["scalar_identity"]["rank"] == 1
    rank_controls["duplicate_identity"]["duplicate_pair_separation"] = float(
        np.linalg.norm(duplicate[0] - duplicate[-1])
    )
    rank_controls["duplicate_identity"]["passed"] = (
        rank_controls["duplicate_identity"]["rank"]
        == int(manifest["analysis_contract"]["required_duplicate_rank"])
        and rank_controls["duplicate_identity"]["duplicate_pair_separation"] == 0.0
    )

    artifacts = {
        "train_differences": _write_matrix(
            root / "atlas-train-differences.f32",
            np.stack(train_differences),
            root,
        ),
        "holdout_differences": _write_matrix(
            root / "atlas-holdout-differences.f32",
            np.stack(holdout_differences),
            root,
        ),
        "holdout_identity_rows": _write_matrix(
            root / "atlas-holdout-identity-rows.f32",
            distinct,
            root,
        ),
        "axis_directions": _write_matrix(
            root / "atlas-axis-directions.f32",
            np.stack(axis_directions),
            root,
        ),
    }
    model = capture_rows[0]["model_fingerprint"]
    runtime = None
    first_capture_receipt = root / capture_rows[0]["capture_receipt"]
    if first_capture_receipt.is_file():
        runtime = json.loads(first_capture_receipt.read_text(encoding="utf-8")).get("runtime")
    receipt = {
        "schema": "cassi.native-semantic-atlas-receipt.v1",
        "verdict": "PASS"
        if all(row["passed"] for row in axis_results)
        and all(row["passed"] for row in rank_controls.values())
        and all(row["passed"] for row in negative_control_results)
        else "FAIL",
        "manifest": {
            "path": manifest_path.name,
            "sha256": _sha_bytes(_canonical(manifest)),
            "schema": manifest["schema"],
            "semantic_source": manifest["semantic_source"],
        },
        "model_fingerprint": model,
        "model_sha256": sha256_path(model_path),
        "runtime": runtime,
        "capture_contract": manifest["capture_contract"],
        "capture_count": len(capture_rows),
        "residual_dimension": dimension,
        "negative_controls": negative_control_results,
        "captures": capture_rows,
        "axes": axis_results,
        "rank_controls": rank_controls,
        "artifacts": artifacts,
        "analysis": {
            "rank_relative_tolerance": relative_tolerance,
            "identity_row_count": int(distinct.shape[0]),
            "train_difference_count": int(len(train_differences)),
            "holdout_difference_count": int(len(holdout_differences)),
        },
    }
    receipt["content_sha256"] = _sha_bytes(
        _canonical({key: value for key, value in receipt.items() if key != "content_sha256"})
    )
    _write_json(root / "semantic-atlas-receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "semantic-atlas-manifest.json")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--gpu-layers", type=int, default=GPU_LAYERS)
    parser.add_argument("--context-tokens", type=int, default=CONTEXT_TOKENS)
    parser.add_argument("--quantization", default=QUANTIZATION)
    args = parser.parse_args()
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
