"""Independent raw-artifact verifier for the frozen CassiQwen L19 control surface.

It reads the manifest, six L18-format receipts, and their JSONL logs.  It never
loads a model, opens Godot, or imports the experiment implementation.
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
DEFAULT_DIRECTORY = HERE / "_diag" / "l19-output-control-surface"
PROTOCOL = "CassiQwen L18 field-output loop"
L19_PROTOCOL = "CassiQwen L19 output control surface"
VERSION = 1
MODEL_SHA = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
MODEL_NAME = "Qwen3.8-27B-Q4_K_M.gguf"
N = 32
CELLS = N**3
D = 5120
LAYERS = 64
HEAD_INDEX = 64
STEPS_PER_LAYER = 4
STEPS_PER_TOKEN = LAYERS * STEPS_PER_LAYER
DT = 0.005
PHI = 1.618033988749895
TOP_K = 16
FIELD_BOUND = 10.0
DTYPE = "float32-le"
LAYOUT = "x + N*(y + N*z)"


class VerifyError(RuntimeError):
    def __init__(self, gate: str, message: str) -> None:
        super().__init__(message)
        self.gate = gate
        self.message = message


def need(condition: bool, gate: str, message: str) -> None:
    if not condition:
        raise VerifyError(gate, message)


def obj(value: Any, gate: str, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), gate, f"{label} must be an object")
    return value


def arr(value: Any, gate: str, label: str) -> list[Any]:
    need(isinstance(value, list), gate, f"{label} must be an array")
    return value


def integer(value: Any, gate: str, label: str) -> int:
    need(isinstance(value, int) and not isinstance(value, bool), gate, f"{label} must be an integer")
    return int(value)


def number(value: Any, gate: str, label: str) -> float:
    need(isinstance(value, (int, float)) and not isinstance(value, bool), gate, f"{label} must be numeric")
    result = float(value)
    need(math.isfinite(result), gate, f"{label} must be finite")
    return result


def text(value: Any, gate: str, label: str) -> str:
    need(isinstance(value, str), gate, f"{label} must be text")
    return value


def sha(value: Any, gate: str, label: str) -> str:
    result = text(value, gate, label).lower()
    need(len(result) == 64 and all(char in "0123456789abcdef" for char in result), gate, f"{label} is not SHA-256")
    return result


def close(actual: float, expected: float, relative: float = 2e-5, absolute: float = 2e-6) -> bool:
    return math.isclose(actual, expected, rel_tol=relative, abs_tol=absolute)


def load_json(raw: bytes, gate: str, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise VerifyError(gate, f"{label} is not finite UTF-8 JSON: {error}") from error


def raw_b64(value: Any, gate: str, label: str) -> bytes:
    encoded = text(value, gate, f"{label} base64")
    need(len(encoded) % 4 == 0, gate, f"{label} base64 is not padded")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise VerifyError(gate, f"{label} base64 is invalid: {error}") from error
    need(base64.b64encode(raw).decode("ascii") == encoded, gate, f"{label} base64 is noncanonical")
    return raw


def f32_bytes(values: np.ndarray) -> bytes:
    result = np.ascontiguousarray(np.asarray(values, dtype="<f4"))
    need(bool(np.isfinite(result).all()), "raw", "array has non-finite values")
    return result.tobytes(order="C")


def decode_array(value: Any, gate: str, label: str, expected_shape: tuple[int, ...] | None = None) -> np.ndarray:
    meta = obj(value, gate, label)
    encoded = meta.get("raw_f32_b64", meta.get("b64"))
    need(encoded is not None, gate, f"{label} lacks raw float32 payload")
    raw = raw_b64(encoded, gate, label)
    declared_shape = arr(meta.get("shape"), gate, f"{label}.shape")
    shape = tuple(integer(axis, gate, f"{label}.shape") for axis in declared_shape)
    if expected_shape is not None:
        need(shape == expected_shape, gate, f"{label} shape mismatch")
    need(len(raw) == math.prod(shape) * 4, gate, f"{label} byte length mismatch")
    need(meta.get("dtype") in ("float32", DTYPE), gate, f"{label} dtype mismatch")
    if "layout" in meta:
        need(meta["layout"] in ("C", LAYOUT), gate, f"{label} layout mismatch")
    if "bytes" in meta:
        need(integer(meta["bytes"], gate, f"{label}.bytes") == len(raw), gate, f"{label} byte count mismatch")
    need(hashlib.sha256(raw).hexdigest() == sha(meta.get("sha256"), gate, f"{label}.sha256"), gate, f"{label} SHA-256 mismatch")
    values = np.frombuffer(raw, dtype="<f4").copy().reshape(shape)
    need(bool(np.isfinite(values).all()), gate, f"{label} contains non-finite values")
    if "l2_norm" in meta:
        need(close(number(meta["l2_norm"], gate, f"{label}.l2_norm"), float(np.linalg.norm(values.astype(np.float64).reshape(-1)))), gate, f"{label} L2 mismatch")
    if "max_abs" in meta:
        need(close(number(meta["max_abs"], gate, f"{label}.max_abs"), float(np.max(np.abs(values))) if values.size else 0.0), gate, f"{label} max mismatch")
    return np.ascontiguousarray(values)


def selected_modes() -> tuple[tuple[int, int, int], ...]:
    def flat(x: int, y: int, z: int) -> int:
        return x + N * (y + N * z)

    def wrap(index: int) -> int:
        return index - N if index > N // 2 else index

    candidates: list[tuple[int, int, int, int, int, int, int, int]] = []
    for z in range(N):
        for y in range(N):
            for x in range(N):
                index = flat(x, y, z)
                negative = flat(0 if x == 0 else N - x, 0 if y == 0 else N - y, 0 if z == 0 else N - z)
                if index != negative:
                    kx, ky, kz = wrap(x), wrap(y), wrap(z)
                    candidates.append((kx * kx + ky * ky + kz * kz, kz, ky, kx, index, negative, x, y, z))
    candidates.sort(key=lambda row: row[:5])
    seen = np.zeros(CELLS, dtype=np.uint8)
    modes: list[tuple[int, int, int]] = []
    for _, _, _, _, index, negative, x, y, z in candidates:
        if not seen[index]:
            seen[index] = seen[negative] = 1
            modes.append((x, y, z))
    need(len(modes) >= D // 2, "codec", "canonical mode set is too short")
    return tuple(modes[: D // 2])


MODES = selected_modes()


def encode_direction(vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector.astype(np.float64)))
    need(vector.shape == (D,) and math.isfinite(norm) and norm > 0.0, "codec", "source vector is malformed")
    spectrum = np.zeros((N, N, N), dtype=np.complex128)
    normalized = vector.astype(np.float64) / norm
    scale = math.sqrt(CELLS / 2.0)
    for pair, (x, y, z) in enumerate(MODES):
        a, b = normalized[2 * pair], normalized[2 * pair + 1]
        spectrum[z, y, x] = scale * (a - 1j * b)
        nx, ny, nz = (0 if x == 0 else N - x, 0 if y == 0 else N - y, 0 if z == 0 else N - z)
        spectrum[nz, ny, nx] = scale * (a + 1j * b)
    signal = np.fft.ifftn(spectrum).real.reshape(-1).astype(np.float32)
    ey = np.where(signal > 0.0, signal, 0.0).astype(np.float32)
    ei = np.where(signal < 0.0, -signal.astype(np.float64) / PHI, 0.0).astype(np.float32)
    return np.ascontiguousarray(ey), np.ascontiguousarray(ei)


def decode_field(ey: np.ndarray, ei: np.ndarray) -> np.ndarray:
    spectrum = np.fft.fftn((ey.astype(np.float64) - PHI * ei.astype(np.float64)).reshape((N, N, N)))
    result = np.empty(D, dtype=np.float64)
    scale = math.sqrt(CELLS / 2.0)
    for pair, (x, y, z) in enumerate(MODES):
        coefficient = spectrum[z, y, x]
        result[2 * pair] = coefficient.real / scale
        result[2 * pair + 1] = -coefficient.imag / scale
    return np.ascontiguousarray(result.astype(np.float32))


def field_payload(value: Any, gate: str, label: str, raw_required: bool) -> tuple[np.ndarray | None, np.ndarray | None]:
    field = obj(value, gate, label)
    need(field.get("grid_n") == N and field.get("dtype") == DTYPE and field.get("shape") == [CELLS] and field.get("layout") == LAYOUT, gate, f"{label} schema mismatch")
    if "volume_shape" in field:
        need(field["volume_shape"] == [N, N, N], gate, f"{label} volume shape mismatch")
    ey_b64, ei_b64 = field.get("ey_b64"), field.get("ei_b64")
    if ey_b64 is None or ei_b64 is None:
        need(not raw_required, gate, f"{label} lacks raw channels")
        for key in ("ey_sha256", "ei_sha256", "sha256"):
            if key in field:
                sha(field[key], gate, f"{label}.{key}")
        return None, None
    ey_raw, ei_raw = raw_b64(ey_b64, gate, f"{label}.EY"), raw_b64(ei_b64, gate, f"{label}.EI")
    ey = np.frombuffer(ey_raw, dtype="<f4").copy()
    ei = np.frombuffer(ei_raw, dtype="<f4").copy()
    need(ey.shape == ei.shape == (CELLS,) and bool(np.isfinite(ey).all()) and bool(np.isfinite(ei).all()), gate, f"{label} channel shape/finiteness mismatch")
    ey_hash, ei_hash = hashlib.sha256(f32_bytes(ey)).hexdigest(), hashlib.sha256(f32_bytes(ei)).hexdigest()
    need(sha(field.get("ey_sha256"), gate, f"{label}.ey_sha256") == ey_hash, gate, f"{label} EY hash mismatch")
    need(sha(field.get("ei_sha256"), gate, f"{label}.ei_sha256") == ei_hash, gate, f"{label} EI hash mismatch")
    need(sha(field.get("sha256"), gate, f"{label}.sha256") == hashlib.sha256(f32_bytes(ey) + f32_bytes(ei)).hexdigest(), gate, f"{label} combined hash mismatch")
    need(integer(field.get("bytes"), gate, f"{label}.bytes") == 8 * CELLS, gate, f"{label} byte count mismatch")
    return np.ascontiguousarray(ey), np.ascontiguousarray(ei)


def rank_rows(logits: np.ndarray, rows: Any, gate: str, label: str) -> list[int]:
    rows = arr(rows, gate, label)
    need(len(rows) == TOP_K, gate, f"{label} length mismatch")
    ids = np.arange(logits.size, dtype=np.int64)
    order = np.lexsort((ids, -logits.astype(np.float64)))[:TOP_K]
    for rank, token_id in enumerate(order, start=1):
        row = obj(rows[rank - 1], gate, f"{label}[{rank - 1}]")
        if "rank" in row:
            need(integer(row.get("rank"), gate, f"{label}.rank") == rank, gate, f"{label} rank mismatch")
        need(integer(row.get("token_id"), gate, f"{label}.token_id") == int(token_id), gate, f"{label} token mismatch")
        need(close(number(row.get("logit"), gate, f"{label}.logit"), float(logits[token_id]), 0.0, 0.0), gate, f"{label} logit mismatch")
    return [int(token_id) for token_id in order]


def capture_record(value: Any, gate: str, label: str, source_index: int) -> tuple[list[np.ndarray], np.ndarray, np.ndarray, list[int]]:
    record = obj(value, gate, label)
    expected_mode = "initial_tokens" if source_index == -1 else "token"
    need(
        record.get("mode") == expected_mode
        and integer(record.get("source_token_index"), gate, f"{label}.source_token") == source_index,
        gate,
        f"{label} identity mismatch",
    )
    token_ids = [integer(token, gate, f"{label}.token_id") for token in arr(record.get("token_ids"), gate, f"{label}.token_ids")]
    positions = [integer(position, gate, f"{label}.position") for position in arr(record.get("token_positions"), gate, f"{label}.positions")]
    pieces = arr(record.get("token_pieces"), gate, f"{label}.pieces")
    need(len(token_ids) == len(positions) == len(pieces) > 0 and all(isinstance(piece, str) for piece in pieces), gate, f"{label} token arrays mismatch")
    trunk = arr(record.get("trunk"), gate, f"{label}.trunk")
    need(len(trunk) == LAYERS, gate, f"{label} trunk layer count mismatch")
    final_position = positions[-1]
    vectors: list[np.ndarray] = []
    for layer, value in enumerate(trunk):
        item = obj(value, gate, f"{label}.trunk[{layer}]")
        need(item.get("role") == "field_trunk" and integer(item.get("layer_index"), gate, "layer") == layer, gate, f"{label} trunk layer identity mismatch")
        need(integer(item.get("token_index"), gate, "token") == source_index and integer(item.get("token_position"), gate, "position") == final_position, gate, f"{label} trunk token/position mismatch")
        vector = decode_array(item, gate, f"{label}.trunk[{layer}]", (D,))
        need(float(np.linalg.norm(vector.astype(np.float64))) > 0.0, gate, f"{label} zero trunk vector")
        vectors.append(vector)
    head_item = obj(record.get("head_output_reference"), gate, f"{label}.head")
    need(head_item.get("role") == "head_output_reference" and integer(head_item.get("layer_index"), gate, "head layer") == HEAD_INDEX, gate, f"{label} head identity mismatch")
    need(integer(head_item.get("token_index"), gate, "head token") == source_index and integer(head_item.get("token_position"), gate, "head position") == final_position, gate, f"{label} head token/position mismatch")
    head = decode_array(head_item, gate, f"{label}.head", (D,))
    ordinary = decode_array(record.get("ordinary_logits"), gate, f"{label}.ordinary_logits")
    need(ordinary.ndim == 1 and ordinary.size >= TOP_K, gate, f"{label} ordinary logit shape mismatch")
    rank_rows(ordinary, record.get("ordinary_top_k"), gate, f"{label}.ordinary_top_k")
    return vectors, head, ordinary, positions


def field_metrics(readout: Mapping[str, Any], ey: np.ndarray, ei: np.ndarray, gate: str, label: str) -> None:
    state, metrics = obj(readout.get("state"), gate, f"{label}.state"), obj(readout.get("metrics"), gate, f"{label}.metrics")
    need(state.get("finite") is True and metrics.get("finite") is True, gate, f"{label} finite flags are false")
    ey64, ei64 = ey.astype(np.float64), ei.astype(np.float64)
    epsilon = ey64 - PHI * ei64
    expected = {
        "ey_l2": float(np.linalg.norm(ey64)),
        "ei_l2": float(np.linalg.norm(ei64)),
        "epsilon_l2": float(np.linalg.norm(epsilon)),
        "max_abs": float(np.max(np.maximum(np.abs(ey64), np.abs(ei64)))),
    }
    need(expected["max_abs"] <= FIELD_BOUND, gate, f"{label} field exceeds bound")
    for key, value in expected.items():
        need(close(number(metrics.get(key), gate, f"{label}.{key}"), value, 4e-5, 3e-6), gate, f"{label}.{key} mismatch")


def cosine(first: np.ndarray, second: np.ndarray) -> float:
    first64, second64 = first.astype(np.float64), second.astype(np.float64)
    denominator = float(np.linalg.norm(first64)) * float(np.linalg.norm(second64))
    return 0.0 if denominator == 0.0 else float(np.dot(first64, second64) / denominator)


def check_memory(event: Mapping[str, Any], query: np.ndarray, previous: list[dict[str, Any]], gate: str) -> None:
    actual = arr(event.get("memory"), gate, "event memory")
    plan = obj(event.get("plan"), gate, "plan")
    need(actual == plan.get("retrieved_memory") == plan.get("memory"), gate, "memory aliases mismatch")
    ranked: list[tuple[tuple[float, int, int, str, int], dict[str, Any]]] = []
    for insertion, item in enumerate(previous):
        row = {
            "record_id": item["record_id"],
            "token_index": item["token_index"],
            "token_id": item["token_id"],
            "piece": item["piece"],
            "source": item["source"],
            "score": cosine(query, item["vector"]),
        }
        ranked.append(((-row["score"], 0, row["token_index"], row["record_id"], insertion), row))
    expected = [row for _, row in sorted(ranked)[:4]]
    need(len(actual) == len(expected), gate, "memory retrieval length mismatch")
    for index, (value, wanted) in enumerate(zip(actual, expected), start=1):
        got = obj(value, gate, f"memory row {index}")
        for key in ("record_id", "token_index", "token_id", "piece", "source"):
            need(got.get(key) == wanted[key], gate, f"memory {key} mismatch at rank {index}")
        need(close(number(got.get("score"), gate, f"memory score {index}"), wanted["score"]), gate, f"memory score mismatch at rank {index}")


def check_updates(event: Mapping[str, Any], vectors: list[np.ndarray], event_index: int, gate: str) -> None:
    rows = arr(event.get("field_layer_updates"), gate, "field updates")
    need(len(rows) == LAYERS, gate, "field update count is not 64")
    for layer, value in enumerate(rows):
        row = obj(value, gate, f"field update {layer}")
        need(row.get("finite") is True and integer(row.get("layer_index"), gate, "layer") == layer, gate, f"field update {layer} identity mismatch")
        need(sha(row.get("source_vector_sha256"), gate, "source vector SHA") == hashlib.sha256(f32_bytes(vectors[layer])).hexdigest(), gate, f"field update {layer} source SHA mismatch")
        encoded_ey, encoded_ei = encode_direction(vectors[layer])
        field_input = obj(row.get("field_input"), gate, f"field update {layer} input")
        need(field_input.get("grid_n") == N and field_input.get("shape") == [CELLS] and field_input.get("dtype") == DTYPE and field_input.get("layout") == LAYOUT, gate, f"field update {layer} input schema mismatch")
        need(sha(field_input.get("ey_sha256"), gate, "input EY SHA") == hashlib.sha256(f32_bytes(encoded_ey)).hexdigest(), gate, f"field update {layer} EY encoding mismatch")
        need(sha(field_input.get("ei_sha256"), gate, "input EI SHA") == hashlib.sha256(f32_bytes(encoded_ei)).hexdigest(), gate, f"field update {layer} EI encoding mismatch")
        state = obj(row.get("state"), gate, f"field update {layer} state")
        expected_step = (event_index * LAYERS + layer + 1) * STEPS_PER_LAYER
        need(integer(state.get("step"), gate, "update step") == expected_step and integer(state.get("token_index"), gate, "update token") == event_index and integer(state.get("layer_index"), gate, "update layer") == layer, gate, f"field update {layer} clock mismatch")
        need(close(number(state.get("t"), gate, "update time"), expected_step * DT, 0.0, 2e-6), gate, f"field update {layer} time mismatch")
        field_payload(row.get("field_output"), gate, f"field update {layer} output", raw_required=False)


def validate_event(event: Mapping[str, Any], arm: Mapping[str, Any], event_index: int) -> dict[str, Any]:
    gate = f"{arm['name']} event {event_index}"
    need(event.get("protocol") == PROTOCOL and integer(event.get("version"), gate, "version") == VERSION and event.get("run_id") == arm["run_id"] and event.get("event_kind") == "output" and integer(event.get("token_index"), gate, "token index") == event_index and event.get("finite") is True, gate, "event identity/finiteness mismatch")
    vectors, head, ordinary, positions = capture_record(event.get("field_source"), gate, "source", event_index - 1)
    check_updates(event, vectors, event_index, gate)
    readout = obj(event.get("field_readout"), gate, "field readout")
    state = obj(readout.get("state"), gate, "field state")
    expected_step = (event_index + 1) * STEPS_PER_TOKEN
    need(integer(state.get("step"), gate, "readout step") == expected_step and integer(state.get("token_index"), gate, "readout token") == event_index and integer(state.get("layer_index"), gate, "readout layer") == LAYERS - 1, gate, "readout clock mismatch")
    need(close(number(state.get("t"), gate, "readout time"), expected_step * DT, 0.0, 2e-6), gate, "readout time mismatch")
    ey, ei = field_payload(readout.get("field"), gate, "readout field", raw_required=True)
    if ey is None or ei is None:
        raise VerifyError(gate, "readout field lacks raw channels")
    ey_array = decode_array(readout.get("ey"), gate, "readout EY", (CELLS,))
    ei_array = decode_array(readout.get("ei"), gate, "readout EI", (CELLS,))
    need(f32_bytes(ey) == f32_bytes(ey_array) and f32_bytes(ei) == f32_bytes(ei_array), gate, "field/readout channel linkage mismatch")
    field_metrics(readout, ey, ei, gate, "readout")
    last_output = obj(arr(event.get("field_layer_updates"), gate, "updates")[-1], gate, "last update output")
    last_field = obj(last_output.get("field_output"), gate, "last field")
    for key in ("ey_sha256", "ei_sha256", "sha256"):
        need(sha(last_field.get(key), gate, f"last field {key}") == sha(obj(readout.get("field"), gate, "field").get(key), gate, f"readout {key}"), gate, f"last-update/readout {key} mismatch")
    decoded_raw = decode_field(ey, ei)
    decoded_raw_norm = float(np.linalg.norm(decoded_raw.astype(np.float64)))
    need(math.isfinite(decoded_raw_norm) and decoded_raw_norm > 0.0, gate, "decoded field has invalid norm")
    decoded = np.ascontiguousarray(decoded_raw / np.float32(decoded_raw_norm))

    output = obj(event.get("output"), gate, "output")
    expected_coupling = number(arm.get("coupling"), gate, "arm coupling")
    need(output.get("mode") == "residual" and output.get("mode_detail") == "field_augmented_output_features" and close(number(output.get("coupling"), gate, "output coupling"), expected_coupling, 0.0, 0.0), gate, "output seam/coupling mismatch")
    direction = decode_array(output.get("field_direction"), gate, "field direction", (D,))
    features = decode_array(output.get("field_output_features"), gate, "field output features", (D,))
    augmented = decode_array(output.get("field_augmented_output_features"), gate, "field augmented features", (D,))
    if f32_bytes(direction) != f32_bytes(decoded):
        raise VerifyError(
            gate,
            f"field decode mismatch (max abs delta {float(np.max(np.abs(direction.astype(np.float64) - decoded.astype(np.float64))))})",
        )
    need(f32_bytes(augmented) == f32_bytes(np.ascontiguousarray(head + np.float32(expected_coupling) * features)), gate, "output feature combination mismatch")
    need(close(number(output.get("head_output_reference_norm"), gate, "head norm"), float(np.linalg.norm(head.astype(np.float64))), 0.0, 0.0), gate, "head norm mismatch")
    field_logits = decode_array(output.get("field_only_logits"), gate, "field-only logits")
    residual_logits = decode_array(output.get("field_augmented_logits"), gate, "residual logits")
    selected_logits = decode_array(output.get("selected_logits"), gate, "selected logits")
    need(field_logits.shape == residual_logits.shape == selected_logits.shape and field_logits.ndim == 1 and field_logits.size >= TOP_K, gate, "output logit shapes mismatch")
    need(f32_bytes(selected_logits) == f32_bytes(residual_logits), gate, "residual selection mismatch")
    rank_rows(field_logits, output.get("field_only_top_k"), gate, "field-only top-k")
    selected_ids = rank_rows(residual_logits, output.get("field_augmented_top_k"), gate, "residual top-k")
    need(rank_rows(selected_logits, output.get("selected_top_k"), gate, "selected top-k") == selected_ids, gate, "selected top-k mismatch")
    selected_token = integer(event.get("selected_token_id"), gate, "selected token")
    need(selected_token == selected_ids[0], gate, "selected token is not residual argmax")
    candidates = arr(event.get("candidates"), gate, "candidates")
    plan = obj(event.get("plan"), gate, "plan")
    need(len(candidates) == TOP_K and plan.get("ranked_candidates") == candidates and plan.get("candidates") == candidates, gate, "candidate aliases/count mismatch")
    for rank, candidate in enumerate(candidates, start=1):
        row = obj(candidate, gate, f"candidate {rank}")
        token_id = selected_ids[rank - 1]
        need(integer(row.get("rank"), gate, "candidate rank") == rank and integer(row.get("token_id"), gate, "candidate token") == token_id, gate, f"candidate {rank} ranking mismatch")
        for key, expected in (("score", residual_logits[token_id]), ("ordinary_score", ordinary[token_id]), ("field_score", residual_logits[token_id])):
            need(close(number(row.get(key), gate, f"candidate {key}"), float(expected), 0.0, 0.0), gate, f"candidate {rank} {key} mismatch")
    need(plan.get("external_actions") == [] and plan.get("actions") == [] and plan.get("field_enabled") is True and plan.get("finite") is True and integer(plan.get("token_index"), gate, "plan token") == event_index and integer(plan.get("selected_token_id"), gate, "plan selected token") == selected_token, gate, "planner no-action contract mismatch")
    committed = obj(event.get("committed_decode"), gate, "committed decode")
    committed_positions = [integer(position, gate, "committed position") for position in arr(committed.get("token_positions"), gate, "committed positions")]
    need(len(committed_positions) == 1 and committed_positions[0] == positions[-1] + 1, gate, "committed position mismatch")
    return {
        "selected_token_id": selected_token,
        "selected_piece": text(event.get("selected_piece"), gate, "selected piece"),
        "field_sha256": sha(obj(readout.get("field"), gate, "field").get("sha256"), gate, "field SHA"),
        "selected_top_k": selected_ids,
        "top_one_margin": float(residual_logits[selected_ids[0]] - residual_logits[selected_ids[1]]),
        "direction": direction,
    }


def event_log_path(receipt: Mapping[str, Any], receipt_path: Path, gate: str) -> Path:
    meta = obj(receipt.get("event_log"), gate, "event log")
    candidate = Path(text(meta.get("path"), gate, "event log path"))
    result = candidate if candidate.is_absolute() else receipt_path.parent / candidate
    raw = result.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == sha(meta.get("sha256"), gate, "event log SHA"), gate, "event log SHA mismatch")
    return result

def event_link(meta: Any, raw: bytes, event_index: int, event_path: Path, gate: str, label: str) -> None:
    receipt = obj(meta, gate, label)
    need(
        integer(receipt.get("event_index"), gate, f"{label}.index") == event_index
        and integer(receipt.get("bytes"), gate, f"{label}.bytes") == len(raw)
        and sha(receipt.get("sha256"), gate, f"{label}.sha256") == hashlib.sha256(raw).hexdigest()
        and text(receipt.get("path"), gate, f"{label}.path") == str(event_path),
        gate,
        f"{label} linkage mismatch",
    )


def validate_arm(directory: Path, arm: Mapping[str, Any]) -> dict[str, Any]:
    gate = str(arm["name"])
    receipt_path = directory / f"{arm['run_id']}.receipt.json"
    receipt_raw = receipt_path.read_bytes()
    receipt = obj(load_json(receipt_raw, gate, "receipt"), gate, "receipt")
    need(receipt.get("protocol") == PROTOCOL and integer(receipt.get("version"), gate, "receipt version") == VERSION and receipt.get("run_id") == arm["run_id"] and receipt.get("verdict") == "PASS" and receipt.get("finite") is True, gate, "receipt identity/verdict mismatch")
    config = obj(receipt.get("config"), gate, "config")
    need(integer(config.get("max_tokens"), gate, "max tokens") == integer(arm.get("max_tokens"), gate, "manifest max tokens") and close(number(config.get("coupling"), gate, "config coupling"), number(arm.get("coupling"), gate, "manifest coupling"), 0.0, 0.0) and config.get("output_mode") == "residual", gate, "frozen arm configuration mismatch")
    field = obj(config.get("field"), gate, "field config")
    need(field.get("grid_n") == N and field.get("dimension") == D and field.get("dtype") == DTYPE and field.get("layout") == LAYOUT and integer(field.get("steps_per_layer"), gate, "steps per layer") == STEPS_PER_LAYER, gate, "field config mismatch")
    lab = obj(config.get("lab"), gate, "lab config")
    need(lab.get("host") == "127.0.0.1" and integer(lab.get("port"), gate, "lab port") == 7601, gate, "lab boundary mismatch")
    need(Path(text(config.get("model"), gate, "model path")).name == MODEL_NAME and sha(config.get("model_sha256"), gate, "model SHA") == MODEL_SHA, gate, "model identity mismatch")
    event_path = event_log_path(receipt, receipt_path, gate)
    lines = event_path.read_bytes().splitlines(keepends=True)
    expected_count = integer(arm.get("max_tokens"), gate, "max tokens") + 1
    need(len(lines) == expected_count and all(line.endswith(b"\n") for line in lines), gate, "event log count or termination mismatch")
    event_receipts = arr(receipt.get("events"), gate, "receipt events")
    need(len(event_receipts) == expected_count - 1, gate, "receipt event count mismatch")
    for index, line in enumerate(lines[:-1]):
        event_link(event_receipts[index], line, index, event_path, gate, f"receipt event {index}")
    event_link(receipt.get("terminal_event"), lines[-1], expected_count - 1, event_path, gate, "terminal event")
    output_events = [obj(load_json(line[:-1], gate, f"event {index}"), gate, f"event {index}") for index, line in enumerate(lines[:-1])]
    selected: list[int] = []
    fields: list[str] = []
    summaries: list[dict[str, Any]] = []
    memory_records: list[dict[str, Any]] = []
    for index, event in enumerate(output_events):
        summary = validate_event(event, arm, index)
        event_gate = f"{arm['name']} event {index}"
        check_memory(event, summary["direction"], memory_records, event_gate)
        memory_records.append(
            {
                "record_id": f"token-{index}-{index}",
                "token_index": index,
                "token_id": summary["selected_token_id"],
                "piece": summary["selected_piece"],
                "source": "token",
                "vector": summary.pop("direction"),
            }
        )
        summary.pop("selected_piece")
        selected.append(summary["selected_token_id"])
        fields.append(summary["field_sha256"])
        summaries.append(summary)
    terminal = obj(load_json(lines[-1][:-1], gate, "terminal event"), gate, "terminal event")
    terminal_index = integer(arm.get("max_tokens"), gate, "terminal index")
    need(terminal.get("protocol") == PROTOCOL and terminal.get("event_kind") == "terminal_field_update" and integer(terminal.get("token_index"), gate, "terminal token index") == terminal_index and terminal.get("finite") is True, gate, "terminal identity mismatch")
    terminal_vectors, _terminal_head, _terminal_ordinary, _terminal_positions = capture_record(terminal.get("field_source"), gate, "terminal source", terminal_index - 1)
    check_updates(terminal, terminal_vectors, terminal_index, gate)
    terminal_readout = obj(terminal.get("field_readout"), gate, "terminal readout")
    terminal_state = obj(terminal_readout.get("state"), gate, "terminal state")
    expected_terminal_step = (terminal_index + 1) * STEPS_PER_TOKEN
    need(integer(terminal_state.get("step"), gate, "terminal step") == expected_terminal_step and close(number(terminal_state.get("t"), gate, "terminal time"), expected_terminal_step * DT, 0.0, 2e-6), gate, "terminal clock mismatch")
    terminal_ey, terminal_ei = field_payload(terminal_readout.get("field"), gate, "terminal field", raw_required=True)
    if terminal_ey is None or terminal_ei is None:
        raise VerifyError(gate, "terminal field lacks raw channels")
    field_metrics(terminal_readout, terminal_ey, terminal_ei, gate, "terminal")
    terminal_raw_direction = decode_field(terminal_ey, terminal_ei)
    terminal_norm = float(np.linalg.norm(terminal_raw_direction.astype(np.float64)))
    need(math.isfinite(terminal_norm) and terminal_norm > 0.0, gate, "terminal decoded field has invalid norm")
    terminal_direction = decode_array(terminal.get("decoded_field_direction"), gate, "terminal decoded direction", (D,))
    need(f32_bytes(terminal_direction) == f32_bytes(np.ascontiguousarray(terminal_raw_direction / np.float32(terminal_norm))), gate, "terminal decoded direction mismatch")
    final_field = obj(receipt.get("final_field"), gate, "final field")
    final_ey, final_ei = field_payload(final_field.get("field"), gate, "final field payload", raw_required=True)
    if final_ey is None or final_ei is None:
        raise VerifyError(gate, "final field lacks raw channels")
    field_metrics(final_field, final_ey, final_ei, gate, "final field")
    need(
        f32_bytes(final_ey) == f32_bytes(terminal_ey)
        and f32_bytes(final_ei) == f32_bytes(terminal_ei),
        gate,
        "terminal/final field linkage mismatch",
    )
    generated = obj(receipt.get("generated"), gate, "generated")
    receipt_ids = [integer(token, gate, "generated token") for token in arr(generated.get("token_ids"), gate, "generated IDs")]
    need(receipt_ids == selected and integer(generated.get("count"), gate, "generated count") == len(selected), gate, "receipt/generated linkage mismatch")
    return {"name": arm["name"], "receipt_path": str(receipt_path), "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(), "event_log_path": str(event_path), "event_log_sha256": hashlib.sha256(event_path.read_bytes()).hexdigest(), "selected_token_ids": selected, "field_sha256": fields, "control": summaries[1]}


def validate(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "l19-manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = obj(load_json(manifest_raw, "manifest", "manifest"), "manifest", "manifest")
    need(manifest.get("protocol") == L19_PROTOCOL and integer(manifest.get("version"), "manifest", "version") == VERSION and manifest.get("status") == "FROZEN BEFORE MODEL RUNS", "manifest", "manifest identity mismatch")
    source = obj(manifest.get("source"), "manifest", "source")
    for key in ("receipt_sha256", "event_log_sha256"):
        sha(source.get(key), "manifest", key)
    derivation = obj(manifest.get("derivation"), "manifest", "derivation")
    control_index = integer(derivation.get("control_event_index"), "manifest", "control index")
    need(control_index == 1, "manifest", "L19 control event must be index 1")
    control = obj(derivation.get("control_event"), "manifest", "control event")
    control_field_sha = sha(control.get("field_sha256"), "manifest", "control field SHA")
    arms = arr(manifest.get("arms"), "manifest", "arms")
    expected_names = ["threshold-zero", "threshold-reference", "threshold-pre", "threshold-post", "trajectory-zero", "trajectory-post"]
    need([arm.get("name") if isinstance(arm, Mapping) else None for arm in arms] == expected_names, "manifest", "arm order mismatch")
    results = {str(arm["name"]): validate_arm(directory, obj(arm, "manifest", "arm")) for arm in arms}
    for result in results.values():
        need(result["field_sha256"][0] == results["threshold-zero"]["field_sha256"][0], "prefix", "first-event fields differ across fresh arms")
        need(result["field_sha256"][control_index] == control_field_sha, "prefix", "control input field does not match frozen field")
    predictions = {str(arm["name"]): obj(arm, "manifest", "arm")["control_event_prediction"] for arm in arms}
    for name, result in results.items():
        prediction = obj(predictions[name], "prediction", name)
        wanted = integer(prediction.get("first_token_id"), "prediction", f"{name} token")
        need(result["selected_token_ids"][control_index] == wanted, "prediction", f"{name} control token differs from frozen direct-head prediction")
    zero_token = results["threshold-zero"]["selected_token_ids"][control_index]
    pre_token = results["threshold-pre"]["selected_token_ids"][control_index]
    post_token = results["threshold-post"]["selected_token_ids"][control_index]
    expected_post = integer(obj(predictions["threshold-post"], "prediction", "post").get("first_token_id"), "prediction", "post token")
    need(zero_token == pre_token and post_token == expected_post and post_token != zero_token, "verdict", "threshold ordering does not show the frozen control transition")
    zero_trajectory = results["trajectory-zero"]
    post_trajectory = results["trajectory-post"]
    divergence = next((index for index, pair in enumerate(zip(zero_trajectory["selected_token_ids"], post_trajectory["selected_token_ids"])) if pair[0] != pair[1]), None)
    need(divergence == control_index, "verdict", "trajectory first divergence is not the frozen control event")
    need(zero_trajectory["field_sha256"][control_index + 1] != post_trajectory["field_sha256"][control_index + 1], "verdict", "post-divergence fields remain identical")
    return {
        "protocol": L19_PROTOCOL,
        "version": VERSION,
        "verdict": "EMERGES",
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "control_event_index": control_index,
        "threshold_tokens": {"zero": zero_token, "pre": pre_token, "post": post_token},
        "trajectory": {
            "zero": zero_trajectory["selected_token_ids"],
            "post": post_trajectory["selected_token_ids"],
            "first_divergent_index": divergence,
            "post_divergence_field_sha256": {"zero": zero_trajectory["field_sha256"][control_index + 1], "post": post_trajectory["field_sha256"][control_index + 1]},
        },
        "arms": list(results.values()),
    }


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--receipt", type=Path, default=None, help="Where to write the independent L19 verification receipt.")
    args = parser.parse_args(argv)
    try:
        result = validate(args.directory.resolve())
        receipt_path = (args.receipt or args.directory / "l19-verification.json").resolve()
        write_json_atomic(receipt_path, result)
    except (OSError, VerifyError) as error:
        print(f"L19 verification failed: {error}")
        return 1
    print(json.dumps({"l19": result["verdict"], "control_event_index": result["control_event_index"], "threshold_tokens": result["threshold_tokens"], "trajectory": result["trajectory"], "receipt": str(receipt_path)}, ensure_ascii=False))
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
