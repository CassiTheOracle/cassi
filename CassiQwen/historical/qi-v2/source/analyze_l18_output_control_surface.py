"""Freeze the L19 field-output coupling ladder from the verified L18 receipt.

This script reads recorded raw float32 output-head logits only.  It never opens a
model, contacts Godot, or starts a service.  Its manifest is the fixed input to
the six serial L19 model-and-field arms declared in L19's preregistration.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_RECEIPT = HERE / "_diag" / "l18-field-output-loop" / "l18-first.receipt.json"
DEFAULT_OUTPUT = HERE / "_diag" / "l19-output-control-surface" / "l19-manifest.json"
L18_PROTOCOL = "CassiQwen L18 field-output loop"
L19_PROTOCOL = "CassiQwen L19 output control surface"
VERSION = 1
TOP_K = 16
REFERENCE_COUPLING = 0.15


class SurfaceError(ValueError):
    """Raised when L18's frozen receipt cannot define a safe L19 ladder."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise SurfaceError(message)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    _need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _finite_number(value: Any, label: str) -> float:
    _need(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} must be numeric")
    result = float(value)
    _need(math.isfinite(result), f"{label} must be finite")
    return result


def _sha256(value: Any, label: str) -> str:
    _need(isinstance(value, str) and len(value) == 64, f"{label} must be a SHA-256 string")
    value = value.lower()
    _need(all(char in "0123456789abcdef" for char in value), f"{label} is malformed")
    return value


def _load_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise SurfaceError(f"{label} is not finite UTF-8 JSON: {error}") from error


def _decode_float32(receipt: Any, label: str) -> np.ndarray:
    item = _mapping(receipt, label)
    payload = item.get("raw_f32_b64")
    _need(isinstance(payload, str) and len(payload) % 4 == 0, f"{label} has invalid base64")
    try:
        raw = base64.b64decode(payload.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise SurfaceError(f"{label} base64 is invalid") from error
    _need(base64.b64encode(raw).decode("ascii") == payload, f"{label} base64 is noncanonical")
    _need(len(raw) % 4 == 0, f"{label} payload is not float32 aligned")
    expected_sha = _sha256(item.get("sha256"), f"{label}.sha256")
    _need(hashlib.sha256(raw).hexdigest() == expected_sha, f"{label} SHA-256 mismatch")
    shape = item.get("shape")
    _need(isinstance(shape, list) and all(isinstance(axis, int) and axis >= 0 for axis in shape), f"{label} shape is invalid")
    _need(math.prod(shape) * 4 == len(raw), f"{label} shape does not match payload")
    array = np.frombuffer(raw, dtype="<f4").copy().reshape(tuple(shape))
    _need(bool(np.isfinite(array).all()), f"{label} contains non-finite values")
    return np.ascontiguousarray(array)


def _rank(logits: np.ndarray) -> list[dict[str, float | int]]:
    _need(logits.ndim == 1 and logits.size >= TOP_K and bool(np.isfinite(logits).all()), "logits are malformed")
    ids = np.arange(logits.size, dtype=np.int64)
    order = np.lexsort((ids, -logits.astype(np.float64, copy=False)))[:TOP_K]
    return [
        {"rank": rank, "token_id": int(token_id), "logit": float(logits[token_id])}
        for rank, token_id in enumerate(order, start=1)
    ]


def _prediction(logits: np.ndarray) -> dict[str, Any]:
    ranked = _rank(logits)
    return {
        "first_token_id": ranked[0]["token_id"],
        "top_one_margin": float(ranked[0]["logit"] - ranked[1]["logit"]),
        "top_k": ranked,
    }


def _first_crossover(baseline: np.ndarray, field: np.ndarray) -> tuple[float, int] | None:
    baseline_id = int(np.argmax(baseline))
    delta_logits = baseline[baseline_id] - baseline
    delta_slopes = field - field[baseline_id]
    eligible = (delta_slopes > 0.0) & (delta_logits >= 0.0)
    crossings = np.full(baseline.shape, np.inf, dtype=np.float64)
    crossings[eligible] = delta_logits[eligible] / delta_slopes[eligible]
    crossings[crossings <= 0.0] = np.inf
    candidate_id = int(np.argmin(crossings))
    crossover = float(crossings[candidate_id])
    if not math.isfinite(crossover) or crossover <= 0.0:
        return None
    return crossover, candidate_id


def _event_path(receipt: Mapping[str, Any], receipt_path: Path) -> Path:
    event_log = _mapping(receipt.get("event_log"), "receipt.event_log")
    candidate = event_log.get("path")
    _need(isinstance(candidate, str) and candidate, "receipt event path is missing")
    path = Path(candidate)
    return path if path.is_absolute() else receipt_path.parent / path


def _surface_event(event: Mapping[str, Any], raw: bytes, event_index: int) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    _need(
        event.get("protocol") == L18_PROTOCOL
        and event.get("version") == VERSION
        and event.get("event_kind") == "output"
        and event.get("token_index") == event_index,
        f"output event {event_index} identity mismatch",
    )
    output = _mapping(event.get("output"), f"output event {event_index}.output")
    coupling = _finite_number(output.get("coupling"), f"output event {event_index} reference coupling")
    _need(
        math.isclose(coupling, REFERENCE_COUPLING, rel_tol=0.0, abs_tol=0.0),
        f"output event {event_index} reference coupling is not 0.15",
    )
    _need(
        output.get("mode") == "residual"
        and output.get("mode_detail") == "field_augmented_output_features",
        f"output event {event_index} is not the residual output seam",
    )
    field_logits = _decode_float32(output.get("field_only_logits"), f"output event {event_index} field-only logits")
    residual_logits = _decode_float32(output.get("field_augmented_logits"), f"output event {event_index} field-augmented logits")
    _need(
        field_logits.shape == residual_logits.shape and field_logits.ndim == 1,
        f"output event {event_index} logits shapes differ",
    )
    field64 = field_logits.astype(np.float64)
    baseline = np.ascontiguousarray(residual_logits.astype(np.float64) - coupling * field64)
    crossover = _first_crossover(baseline, field64)
    readout = _mapping(event.get("field_readout"), f"output event {event_index} field readout")
    field = _mapping(readout.get("field"), f"output event {event_index} field")
    result: dict[str, Any] = {
        "event_index": event_index,
        "event_sha256": hashlib.sha256(raw).hexdigest(),
        "field_sha256": _sha256(field.get("sha256"), f"output event {event_index} field SHA"),
        "field_only_logits_sha256": _sha256(
            _mapping(output.get("field_only_logits"), "field-only logits").get("sha256"),
            f"output event {event_index} field-only logit SHA",
        ),
        "residual_logits_sha256": _sha256(
            _mapping(output.get("field_augmented_logits"), "residual logits").get("sha256"),
            f"output event {event_index} residual logit SHA",
        ),
        "baseline_prediction": _prediction(baseline),
        "field_only_prediction": _prediction(field64),
        "first_crossover": None,
    }
    if crossover is not None:
        gamma, candidate_id = crossover
        result["first_crossover"] = {
            "coupling": gamma,
            "candidate_token_id": candidate_id,
            "candidate_prediction_at_crossing": _prediction(baseline + gamma * field64),
        }
    return result, baseline, field64


def build_manifest(receipt_path: Path) -> dict[str, Any]:
    receipt_raw = receipt_path.read_bytes()
    receipt = _mapping(_load_json_bytes(receipt_raw, "receipt"), "receipt")
    _need(
        receipt.get("protocol") == L18_PROTOCOL
        and receipt.get("version") == VERSION
        and receipt.get("verdict") == "PASS",
        "receipt is not a passing L18 record",
    )
    event_path = _event_path(receipt, receipt_path)
    event_raw = event_path.read_bytes()
    event_log = _mapping(receipt.get("event_log"), "receipt.event_log")
    _need(
        hashlib.sha256(event_raw).hexdigest() == _sha256(event_log.get("sha256"), "event-log SHA"),
        "event-log SHA mismatch",
    )
    lines = event_raw.splitlines(keepends=True)
    _need(lines and all(line.endswith(b"\n") for line in lines), "event log is not LF-terminated")
    surfaces: list[tuple[dict[str, Any], np.ndarray, np.ndarray]] = []
    for event_index, line in enumerate(lines):
        event = _mapping(_load_json_bytes(line[:-1], f"event {event_index}"), f"event {event_index}")
        if event.get("event_kind") == "terminal_field_update":
            break
        surfaces.append(_surface_event(event, line, event_index))
    _need(surfaces, "L18 event log has no output events")
    control_index = next(
        (index for index, (surface, _, _) in enumerate(surfaces) if surface["first_crossover"] is not None),
        None,
    )
    _need(control_index is not None, "no positive direct-head crossover occurs in the recorded L18 trajectory")
    control, baseline_logits, field_logits = surfaces[control_index]
    crossover = _mapping(control["first_crossover"], "control crossover")
    gamma = _finite_number(crossover.get("coupling"), "control crossover coupling")
    threshold_tokens = control_index + 1
    trajectory_tokens = max(4, threshold_tokens)
    arm_specs = (
        ("threshold-zero", 0.0, threshold_tokens),
        ("threshold-reference", REFERENCE_COUPLING, threshold_tokens),
        ("threshold-pre", 0.95 * gamma, threshold_tokens),
        ("threshold-post", 1.05 * gamma, threshold_tokens),
        ("trajectory-zero", 0.0, trajectory_tokens),
        ("trajectory-post", 1.05 * gamma, trajectory_tokens),
    )
    arms: list[dict[str, Any]] = []
    for name, arm_gamma, max_tokens in arm_specs:
        arms.append(
            {
                "name": name,
                "run_id": f"l19-{name}",
                "coupling": float(arm_gamma),
                "max_tokens": max_tokens,
                "control_event_prediction": _prediction(baseline_logits + arm_gamma * field_logits),
            }
        )
    prefix = [surface for surface, _, _ in surfaces[:threshold_tokens]]
    return {
        "protocol": L19_PROTOCOL,
        "version": VERSION,
        "status": "FROZEN BEFORE MODEL RUNS",
        "source": {
            "receipt_path": str(receipt_path.resolve()),
            "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
            "event_log_path": str(event_path.resolve()),
            "event_log_sha256": hashlib.sha256(event_raw).hexdigest(),
        },
        "derivation": {
            "reference_coupling": REFERENCE_COUPLING,
            "formula": "B = R_0.15 - 0.15 F",
            "control_event_index": control_index,
            "control_event": control,
            "prefix": prefix,
        },
        "arms": arms,
    }


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = build_manifest(args.receipt.resolve())
        _write_json_atomic(args.output.resolve(), manifest)
    except (OSError, SurfaceError) as error:
        print(f"L19 manifest failed: {error}")
        return 1
    control = manifest["derivation"]["control_event"]
    arms = manifest["arms"]
    print(
        json.dumps(
            {
                "l19": "manifest-frozen",
                "output": str(args.output.resolve()),
                "control_event_index": manifest["derivation"]["control_event_index"],
                "first_crossover": control["first_crossover"]["coupling"],
                "baseline_token": control["baseline_prediction"]["first_token_id"],
                "post_token": next(
                    arm for arm in arms if arm["name"] == "threshold-post"
                )["control_event_prediction"]["first_token_id"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
