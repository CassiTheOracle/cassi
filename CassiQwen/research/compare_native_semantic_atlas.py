#!/usr/bin/env python3
"""Compare one semantic atlas across two native backends."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "semantic-atlas-broad-manifest.json"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"artifact escapes atlas root: {relative}") from exc
    return candidate


def _load_receipt(root: Path) -> dict[str, Any]:
    path = root / "semantic-atlas-receipt.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "cassi.native-semantic-atlas-receipt.v1":
        raise RuntimeError(f"atlas receipt schema mismatch: {path}")
    body = {key: value for key, value in receipt.items() if key != "content_sha256"}
    if receipt.get("content_sha256") != _sha_bytes(_canonical(body)):
        raise RuntimeError(f"atlas receipt content digest mismatch: {path}")
    if receipt.get("verdict") != "PASS":
        raise RuntimeError(f"atlas receipt did not pass: {path}")
    return receipt


def _read_f32(root: Path, descriptor: Mapping[str, Any]) -> np.ndarray:
    path = _safe(root, str(descriptor["path"]))
    raw = path.read_bytes()
    if _sha_bytes(raw) != descriptor.get("sha256"):
        raise RuntimeError(f"artifact digest mismatch: {path}")
    if len(raw) != int(descriptor["bytes"]) or len(raw) % 4:
        raise RuntimeError(f"artifact size mismatch: {path}")
    values = np.frombuffer(raw, dtype="<f4").copy()
    if values.size != int(descriptor["elements"]):
        raise RuntimeError(f"artifact element mismatch: {path}")
    if not np.isfinite(values).all():
        raise RuntimeError(f"artifact contains non-finite values: {path}")
    return values


def _capture_map(root: Path, receipt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    captures = receipt.get("captures")
    if not isinstance(captures, list):
        raise RuntimeError("atlas captures are missing")
    rows: dict[str, Mapping[str, Any]] = {}
    for row in captures:
        if not isinstance(row, Mapping):
            raise RuntimeError("atlas capture row is malformed")
        capture_id = str(row["capture_id"])
        if capture_id in rows:
            raise RuntimeError(f"duplicate atlas capture ID: {capture_id}")
        _read_f32(root, row["values"])
        rows[capture_id] = row
    return rows


def _capture_identity(root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    capture_receipt = json.loads(
        _safe(root, str(row["capture_receipt"])).read_text(encoding="utf-8")
    )
    model = capture_receipt.get("model")
    runtime = capture_receipt.get("runtime")
    if not isinstance(model, Mapping) or not isinstance(runtime, Mapping):
        raise RuntimeError("capture identity is incomplete")
    return {
        "model_id": model.get("model_id"),
        "model_sha256": model.get("model_sha256"),
        "quantization": model.get("quantization"),
        "backend": model.get("backend"),
        "embedding_width": int(model["embedding_width"]),
        "layer_count": int(model["layer_count"]),
        "layer": int(row["layer"]),
        "gpu_layers": int(runtime["gpu_layers"]),
        "runtime_id": model.get("runtime_id"),
        "runtime_sha256": model.get("runtime_sha256"),
    }


def _expected_capture_ids(manifest: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for axis in manifest["axes"]:
        axis_id = str(axis["axis_id"])
        for pair in axis["pairs"]:
            pair_id = str(pair["pair_id"])
            for side in ("a", "b"):
                ids.add(f"{axis_id}__{pair_id}__{side}")
    for control in manifest.get("negative_controls", []):
        control_id = str(control["control_id"])
        ids.add(f"control__{control_id}__a")
        ids.add(f"control__{control_id}__b")
    return ids


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        raise RuntimeError("cannot compare a zero axis direction")
    return float(np.dot(left, right) / (left_norm * right_norm))


def _compare(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise RuntimeError("atlas manifest is malformed")
    left_root = Path(args.left_root).resolve()
    right_root = Path(args.right_root).resolve()
    left = _load_receipt(left_root)
    right = _load_receipt(right_root)
    left_rows = _capture_map(left_root, left)
    right_rows = _capture_map(right_root, right)
    expected_ids = _expected_capture_ids(manifest)
    if set(left_rows) != expected_ids or set(right_rows) != expected_ids:
        raise RuntimeError("cross-runtime capture ID set mismatch")
    if left.get("manifest", {}).get("sha256") != right.get("manifest", {}).get("sha256"):
        raise RuntimeError("cross-runtime manifest digest mismatch")
    if left.get("manifest", {}).get("sha256") != _sha_bytes(_canonical(manifest)):
        raise RuntimeError("cross-runtime manifest does not match supplied manifest")

    left_identity = _capture_identity(left_root, left_rows[sorted(expected_ids)[0]])
    right_identity = _capture_identity(right_root, right_rows[sorted(expected_ids)[0]])
    if left_identity["model_sha256"] != right_identity["model_sha256"]:
        raise RuntimeError("cross-runtime model digest mismatch")
    if left_identity["model_id"] != right_identity["model_id"]:
        raise RuntimeError("cross-runtime model identity mismatch")
    if left_identity["embedding_width"] != right_identity["embedding_width"] or left_identity["layer_count"] != right_identity["layer_count"]:
        raise RuntimeError("cross-runtime model dimensions mismatch")
    if left_identity["backend"] == right_identity["backend"]:
        raise RuntimeError("cross-runtime backends are not distinct")
    if left_identity["runtime_id"] != right_identity["runtime_id"] or left_identity["runtime_sha256"] != right_identity["runtime_sha256"]:
        raise RuntimeError("cross-runtime runtime build mismatch")

    prompt_hash_match = True
    identity_mismatch: list[str] = []
    for capture_id in sorted(expected_ids):
        left_row = left_rows[capture_id]
        right_row = right_rows[capture_id]
        if left_row.get("prompt_sha256") != right_row.get("prompt_sha256"):
            prompt_hash_match = False
            identity_mismatch.append(capture_id)
        if left_row.get("layer") != right_row.get("layer"):
            identity_mismatch.append(f"{capture_id}:layer")

    left_dirs = _read_f32(left_root, left["artifacts"]["axis_directions"]).reshape(
        len(manifest["axes"]), left_identity["embedding_width"]
    )
    right_dirs = _read_f32(right_root, right["artifacts"]["axis_directions"]).reshape(
        len(manifest["axes"]), right_identity["embedding_width"]
    )
    direction_cosines = {
        str(axis["axis_id"]): _cosine(left_dirs[index], right_dirs[index])
        for index, axis in enumerate(manifest["axes"])
    }
    left_axes = {str(row["axis_id"]): row for row in left["axes"]}
    right_axes = {str(row["axis_id"]): row for row in right["axes"]}
    holdout_signs = {
        axis_id: {
            "left_score": float(left_axes[axis_id]["holdout_score"]),
            "right_score": float(right_axes[axis_id]["holdout_score"]),
            "same_sign": math.copysign(1.0, float(left_axes[axis_id]["holdout_score"]))
            == math.copysign(1.0, float(right_axes[axis_id]["holdout_score"])),
        }
        for axis_id in left_axes
    }
    rank_match = {
        name: int(left["rank_controls"][name]["rank"]) == int(right["rank_controls"][name]["rank"])
        for name in ("distinct_identity", "duplicate_identity", "shared_identity", "scalar_identity")
    }
    left_negative = left.get("negative_controls", [])
    right_negative = right.get("negative_controls", [])
    negative_controls_pass = all(
        bool(row.get("passed")) and float(row.get("difference_norm", 1.0)) == 0.0
        for row in [*left_negative, *right_negative]
    )
    checks = {
        "same_manifest": left.get("manifest", {}).get("sha256") == right.get("manifest", {}).get("sha256"),
        "same_model": left_identity["model_sha256"] == right_identity["model_sha256"],
        "distinct_backends": left_identity["backend"] != right_identity["backend"],
        "same_runtime_build": left_identity["runtime_sha256"] == right_identity["runtime_sha256"],
        "same_prompt_hashes": prompt_hash_match,
        "same_capture_layers": not identity_mismatch,
        "all_axes_pass_both": all(bool(row.get("passed")) for row in [*left["axes"], *right["axes"]]),
        "all_holdout_signs_match": all(row["same_sign"] for row in holdout_signs.values()),
        "rank_controls_match": all(rank_match.values()),
        "negative_controls_pass": negative_controls_pass,
    }
    result = {
        "schema": "cassi.native-semantic-atlas-cross-runtime.v1",
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "manifest_sha256": left["manifest"]["sha256"],
        "left": {
            "root": str(left_root),
            "receipt_content_sha256": left["content_sha256"],
            "identity": left_identity,
        },
        "right": {
            "root": str(right_root),
            "receipt_content_sha256": right["content_sha256"],
            "identity": right_identity,
        },
        "checks": checks,
        "identity_mismatches": identity_mismatch,
        "direction_cosines": direction_cosines,
        "holdout_signs": holdout_signs,
        "rank_controls": rank_match,
    }
    if result["verdict"] != "PASS":
        raise RuntimeError(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-root", type=Path, required=True)
    parser.add_argument("--right-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = _compare(args)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
