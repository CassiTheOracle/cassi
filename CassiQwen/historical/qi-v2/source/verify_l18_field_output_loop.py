"""Read-only NumPy verifier for the frozen L18 field-output-loop receipt."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

PROTOCOL = "CassiQwen L18 field-output loop"
TRAJECTORY_PROTOCOL = "CassiQwen L18 generated-token field-output trajectory"
VERSION = 1
N = 32
CELLS = N**3
D = 5120
PAIRS = D // 2
LAYOUT = "x + N*(y + N*z)"
DTYPE = "float32-le"
PHI = 1.618033988749895
DT = 0.005
LAYERS = 64
HEAD_INDEX = 64
STEPS_PER_LAYER = 4
STEPS_PER_TOKEN = LAYERS * STEPS_PER_LAYER
TOP_K = 16
COUPLING = 0.15
RETAINED = 0.9
FIELD_BOUND = 10.0
MODEL_NAME = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL_SHA = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
PROMPT = "CassiQwen field output lab. Continue this thought in a short, imaginative sentence: The field remembers"


class VerifyError(RuntimeError):
    def __init__(self, gate: str, message: str) -> None:
        super().__init__(message)
        self.gate, self.message = gate, message


def fail(gate: str, message: str) -> None:
    raise VerifyError(gate, message)


def need(condition: bool, gate: str, message: str) -> None:
    if not condition:
        fail(gate, message)


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
    need(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)), gate, f"{label} must be finite")
    return float(value)


def text(value: Any, gate: str, label: str) -> str:
    need(isinstance(value, str), gate, f"{label} must be text")
    return value


def sha(value: Any, gate: str, label: str) -> str:
    value = text(value, gate, label).lower()
    need(len(value) == 64 and all(c in "0123456789abcdef" for c in value), gate, f"{label} is not SHA-256")
    return value


def close(actual: float, expected: float, rel: float = 2e-5, absolute: float = 2e-6) -> bool:
    return math.isclose(actual, expected, rel_tol=rel, abs_tol=absolute)


def load_json(raw: bytes, gate: str, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-finite {token}")))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        fail(gate, f"{label} is invalid UTF-8 JSON: {error}")


def raw_b64(value: Any, gate: str, label: str) -> bytes:
    value = text(value, gate, f"{label} base64")
    need(len(value) % 4 == 0, gate, f"{label} base64 is not padded")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        fail(gate, f"{label} base64 is invalid: {error}")
    need(base64.b64encode(raw).decode("ascii") == value, gate, f"{label} base64 is not canonical")
    return raw


def f32_bytes(values: np.ndarray) -> bytes:
    values = np.asarray(values, dtype=np.float32)
    need(values.flags.c_contiguous and bool(np.isfinite(values).all()), "raw-f32", "array is non-finite or non-contiguous")
    return values.astype("<f4", copy=False).tobytes(order="C")


def decode_array(value: Any, gate: str, label: str, shape: tuple[int, ...] | None = None) -> np.ndarray:
    meta = obj(value, gate, label)
    encoded = meta.get("raw_f32_b64", meta.get("b64"))
    need(encoded is not None, gate, f"{label} has no raw f32 payload")
    raw = raw_b64(encoded, gate, label)
    declared_shape = meta.get("shape")
    if shape is None:
        need(isinstance(declared_shape, list), gate, f"{label} shape is missing")
        shape = tuple(integer(x, gate, f"{label} shape component") for x in declared_shape)
    else:
        need(declared_shape == list(shape), gate, f"{label} shape mismatch")
    need(len(raw) == math.prod(shape) * 4, gate, f"{label} byte length mismatch")
    need(meta.get("dtype") in ("float32", DTYPE), gate, f"{label} dtype mismatch")
    if "layout" in meta:
        need(meta["layout"] in ("C", LAYOUT), gate, f"{label} layout mismatch")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if "sha256" in meta:
        need(sha(meta["sha256"], gate, f"{label} sha256") == actual_sha, gate, f"{label} raw SHA mismatch")
    if "bytes" in meta:
        need(integer(meta["bytes"], gate, f"{label} bytes") == len(raw), gate, f"{label} byte count mismatch")
    values = np.frombuffer(raw, dtype="<f4").copy().reshape(shape)
    need(bool(np.isfinite(values).all()), gate, f"{label} contains non-finite values")
    if "l2_norm" in meta:
        need(close(number(meta["l2_norm"], gate, f"{label} l2_norm"), float(np.linalg.norm(values.astype(np.float64).reshape(-1)))), gate, f"{label} norm mismatch")
    if "max_abs" in meta:
        need(close(number(meta["max_abs"], gate, f"{label} max_abs"), float(np.max(np.abs(values))) if values.size else 0.0), gate, f"{label} max mismatch")
    return np.ascontiguousarray(values)


def same_bytes(actual: np.ndarray, expected: np.ndarray, gate: str, label: str) -> None:
    need(f32_bytes(actual) == f32_bytes(expected), gate, f"{label} raw f32 mismatch")


def modes() -> tuple[tuple[int, int, int], ...]:
    def flat(x: int, y: int, z: int) -> int:
        return x + N * (y + N * z)
    def wrap(i: int) -> int:
        return i - N if i > N // 2 else i
    candidates = []
    for z in range(N):
        for y in range(N):
            for x in range(N):
                index = flat(x, y, z)
                negative = flat(0 if x == 0 else N - x, 0 if y == 0 else N - y, 0 if z == 0 else N - z)
                if index == negative:
                    continue
                kx, ky, kz = wrap(x), wrap(y), wrap(z)
                candidates.append((kx * kx + ky * ky + kz * kz, kz, ky, kx, index, negative, x, y, z))
    candidates.sort(key=lambda row: row[:5])
    seen = np.zeros(CELLS, dtype=np.uint8)
    selected = []
    for _, _, _, _, index, negative, x, y, z in candidates:
        if seen[index]:
            continue
        seen[index] = seen[negative] = 1
        selected.append((x, y, z))
    need(len(selected) >= PAIRS, "codec", "canonical Fourier pair count is too small")
    return tuple(selected[:PAIRS])


MODES = modes()


def decode_field(ey: np.ndarray, ei: np.ndarray) -> np.ndarray:
    spectrum = np.fft.fftn((ey.astype(np.float64) - PHI * ei.astype(np.float64)).reshape((N, N, N)))
    result = np.empty(D, dtype=np.float64)
    scale = math.sqrt(CELLS / 2.0)
    for pair, (x, y, z) in enumerate(MODES):
        coefficient = spectrum[z, y, x]
        result[2 * pair] = coefficient.real / scale
        result[2 * pair + 1] = -coefficient.imag / scale
    need(bool(np.isfinite(result).all()), "field-decode", "decoded field direction is non-finite")
    return np.ascontiguousarray(result.astype(np.float32))


def encode_direction(vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector.astype(np.float64)))
    need(vector.shape == (D,) and math.isfinite(norm) and norm > 0.0, "field-input", "trunk vector shape/norm invalid")
    spectrum = np.zeros((N, N, N), dtype=np.complex128)
    normalized = vector.astype(np.float64) / norm
    scale = math.sqrt(CELLS / 2.0)
    for pair, (x, y, z) in enumerate(MODES):
        a, b = normalized[2 * pair], normalized[2 * pair + 1]
        spectrum[z, y, x] = scale * (a - 1j * b)
        nx, ny, nz = (0 if x == 0 else N - x, 0 if y == 0 else N - y, 0 if z == 0 else N - z)
        spectrum[nz, ny, nx] = scale * (a + 1j * b)
    signal = np.fft.ifftn(spectrum).real.reshape(-1).astype(np.float32)
    return np.ascontiguousarray(np.where(signal > 0, signal, 0).astype(np.float32)), np.ascontiguousarray(np.where(signal < 0, -signal.astype(np.float64) / PHI, 0).astype(np.float32))


def field_payload(value: Any, gate: str, label: str, raw_required: bool) -> tuple[np.ndarray | None, np.ndarray | None]:
    field = obj(value, gate, label)
    need(field.get("grid_n") == N and field.get("dtype") == DTYPE and field.get("shape") == [CELLS] and field.get("layout") == LAYOUT, gate, f"{label} schema mismatch")
    if "volume_shape" in field:
        need(field["volume_shape"] == [N, N, N], gate, f"{label} volume shape mismatch")
    ey_desc, ei_desc = field.get("ey", {}), field.get("ei", {})
    ey_b64, ei_b64 = field.get("ey_b64", ey_desc.get("b64", ey_desc.get("raw_f32_b64"))), field.get("ei_b64", ei_desc.get("b64", ei_desc.get("raw_f32_b64")))
    if ey_b64 is None or ei_b64 is None:
        need(not raw_required, gate, f"{label} lacks raw channels")
        for key in ("ey_sha256", "ei_sha256", "sha256"):
            if key in field:
                sha(field[key], gate, f"{label}.{key}")
        return None, None
    ey = decode_array({"dtype": DTYPE, "shape": [CELLS], "layout": LAYOUT, "bytes": len(raw_b64(ey_b64, gate, f"{label}.EY")), "sha256": hashlib.sha256(raw_b64(ey_b64, gate, f"{label}.EY")).hexdigest(), "raw_f32_b64": ey_b64}, gate, f"{label}.EY", (CELLS,))
    ei = decode_array({"dtype": DTYPE, "shape": [CELLS], "layout": LAYOUT, "bytes": len(raw_b64(ei_b64, gate, f"{label}.EI")), "sha256": hashlib.sha256(raw_b64(ei_b64, gate, f"{label}.EI")).hexdigest(), "raw_f32_b64": ei_b64}, gate, f"{label}.EI", (CELLS,))
    for descriptor, channel, values in ((ey_desc, "EY", ey), (ei_desc, "EI", ei)):
        if isinstance(descriptor, Mapping) and "sha256" in descriptor:
            need(sha(descriptor["sha256"], gate, f"{label}.{channel} hash") == hashlib.sha256(f32_bytes(values)).hexdigest(), gate, f"{label}.{channel} hash mismatch")
    if "ey_sha256" in field:
        need(sha(field["ey_sha256"], gate, f"{label}.ey_sha256") == hashlib.sha256(f32_bytes(ey)).hexdigest(), gate, f"{label} EY hash mismatch")
    if "ei_sha256" in field:
        need(sha(field["ei_sha256"], gate, f"{label}.ei_sha256") == hashlib.sha256(f32_bytes(ei)).hexdigest(), gate, f"{label} EI hash mismatch")
    combined = hashlib.sha256(f32_bytes(ey) + f32_bytes(ei)).hexdigest()
    if "sha256" in field:
        need(sha(field["sha256"], gate, f"{label}.sha256") == combined, gate, f"{label} combined hash mismatch")
    if "bytes" in field:
        need(integer(field["bytes"], gate, f"{label}.bytes") == 8 * CELLS, gate, f"{label} byte count mismatch")
    return ey, ei


def field_metrics(readout: Mapping[str, Any], ey: np.ndarray, ei: np.ndarray, gate: str, label: str) -> None:
    state, metrics = obj(readout.get("state"), gate, f"{label}.state"), obj(readout.get("metrics"), gate, f"{label}.metrics")
    need(state.get("finite") is True and metrics.get("finite") is True, gate, f"{label} finite flag false")
    ey64, ei64 = ey.astype(np.float64), ei.astype(np.float64)
    epsilon = ey64 - PHI * ei64
    expected = {"ey_l2": float(np.linalg.norm(ey64)), "ei_l2": float(np.linalg.norm(ei64)), "epsilon_l2": float(np.linalg.norm(epsilon)), "max_abs": float(np.max(np.maximum(np.abs(ey64), np.abs(ei64))))}
    need(expected["max_abs"] <= FIELD_BOUND, gate, f"{label} exceeds bounded field magnitude")
    for key, value in expected.items():
        need(key in metrics and close(number(metrics[key], gate, f"{label}.{key}"), value, 4e-5, 3e-6), gate, f"{label}.{key} mismatch")
    max_eps2 = number(state.get("max_eps2"), gate, f"{label}.max_eps2")
    need(0 <= max_eps2 <= (1 + PHI) ** 2 * FIELD_BOUND**2, gate, f"{label} state is unbounded")
    for key in ("t", "mean_ey", "mean_ei"):
        number(state.get(key), gate, f"{label}.{key}")


def capture(value: Any, gate: str, label: str, layer: int | None = None, token: int | None = None, position: int | None = None) -> np.ndarray:
    item = obj(value, gate, label)
    actual_layer = integer(item.get("layer_index"), gate, f"{label}.layer_index")
    if layer is not None:
        need(actual_layer == layer, gate, f"{label} layer order mismatch")
    need(item.get("role") == ("field_trunk" if actual_layer < LAYERS else "head_output_reference") and 0 <= actual_layer <= HEAD_INDEX, gate, f"{label} role/index mismatch")
    if token is not None:
        need(integer(item.get("token_index"), gate, f"{label}.token_index") == token, gate, f"{label} token mismatch")
    if position is not None:
        need(integer(item.get("token_position"), gate, f"{label}.token_position") == position, gate, f"{label} position mismatch")
    vector = decode_array(item, gate, label, (D,))
    need(float(np.linalg.norm(vector.astype(np.float64))) > 0, gate, f"{label} zero norm")
    return vector


def top_k(rows: Any, logits: np.ndarray, gate: str, label: str) -> None:
    rows = arr(rows, gate, label)
    need(len(rows) == TOP_K, gate, f"{label} length is not {TOP_K}")
    ids = np.arange(logits.size, dtype=np.int64)
    order = np.lexsort((ids, -logits.astype(np.float64)))[:TOP_K]
    for rank, index in enumerate(order, 1):
        row = obj(rows[rank - 1], gate, f"{label}[{rank - 1}]")
        need(integer(row.get("token_id"), gate, "top-k token") == int(index) and close(number(row.get("logit"), gate, "top-k logit"), float(logits[index]), 0, 0), gate, f"{label} ranking mismatch at {rank}")
        if "rank" in row:
            need(integer(row["rank"], gate, "top-k rank") == rank, gate, f"{label} rank metadata mismatch")
        if "piece" in row:
            text(row["piece"], gate, "top-k piece")
        if "is_eog" in row:
            need(isinstance(row["is_eog"], bool), gate, "top-k is_eog is not boolean")


def record(value: Any, gate: str, label: str, token: int, mode: str, decode_index: int, positions: list[int] | None = None) -> dict[str, Any]:
    item = obj(value, gate, label)
    need(
        integer(item.get("source_token_index"), gate, "capture source token") == token
        and item.get("mode") == mode
        and integer(item.get("decode_index"), gate, "capture decode index") == decode_index,
        gate,
        f"{label} identity mismatch",
    )
    ids, pos, pieces = arr(item.get("token_ids"), gate, "capture IDs"), arr(item.get("token_positions"), gate, "capture positions"), arr(item.get("token_pieces"), gate, "capture pieces")
    need(len(ids) == len(pos) == len(pieces) > 0, gate, f"{label} token arrays mismatch")
    for x in ids:
        integer(x, gate, "capture token ID")
    for x in pos:
        integer(x, gate, "capture position")
    for x in pieces:
        text(x, gate, "capture piece")
    if positions is not None:
        need(pos == positions, gate, f"{label} positions mismatch")
    trunk = arr(item.get("trunk"), gate, f"{label}.trunk")
    need(len(trunk) == LAYERS and item.get("trunk_layer_indices", list(range(LAYERS))) == list(range(LAYERS)), gate, f"{label} trunk sequence mismatch")
    final_position = pos[-1]
    vectors = [capture(x, gate, f"{label}.trunk[{i}]", i, token, final_position) for i, x in enumerate(trunk)]
    need(item.get("head_output_reference_index", HEAD_INDEX) == HEAD_INDEX, gate, f"{label} head index mismatch")
    head = capture(item.get("head_output_reference"), gate, f"{label}.head", HEAD_INDEX, token, final_position)
    logits = decode_array(item.get("ordinary_logits"), gate, f"{label}.ordinary_logits")
    need(logits.ndim == 1 and logits.size >= TOP_K, gate, f"{label} logits shape mismatch")
    top_k(item.get("ordinary_top_k"), logits, gate, f"{label}.ordinary_top_k")
    return {"item": item, "ids": ids, "positions": pos, "pieces": pieces, "trunk": trunk, "vectors": vectors, "head": head, "logits": logits}


def clock(value: Any, gate: str, label: str, step: int, token: int, layer: int) -> None:
    state = obj(value, gate, label)
    need(integer(state.get("step"), gate, "state step") == step and close(number(state.get("t"), gate, "state t"), step * DT, 0, 2e-6) and integer(state.get("token_index"), gate, "state token") == token and integer(state.get("layer_index"), gate, "state layer") == layer, gate, f"{label} clock mismatch")


def updates(event: Mapping[str, Any], source: dict[str, Any], gate: str, token: int) -> None:
    rows = arr(event.get("field_layer_updates"), gate, "field layer updates")
    need(len(rows) == LAYERS, gate, "field update count is not 64")
    for layer, value in enumerate(rows):
        row = obj(value, gate, f"field layer {layer}")
        need(integer(row.get("layer_index"), gate, "layer index") == layer and row.get("finite") is True, gate, f"field layer {layer} sequencing/finiteness mismatch")
        need(sha(row.get("source_vector_sha256"), gate, "source vector hash") == sha(source["trunk"][layer].get("sha256"), gate, "trunk hash"), gate, f"field layer {layer} source hash mismatch")
        ey, ei = encode_direction(source["vectors"][layer])
        field_input = obj(row.get("field_input"), gate, "field input")
        need(field_input.get("grid_n") == N and field_input.get("dtype") == DTYPE and field_input.get("shape") == [CELLS] and field_input.get("layout") == LAYOUT, gate, f"field layer {layer} input schema mismatch")
        need(sha(field_input.get("ey_sha256"), gate, "input EY hash") == hashlib.sha256(f32_bytes(ey)).hexdigest() and sha(field_input.get("ei_sha256"), gate, "input EI hash") == hashlib.sha256(f32_bytes(ei)).hexdigest() and sha(field_input.get("combined_sha256"), gate, "input combined hash") == hashlib.sha256(f32_bytes(ey) + f32_bytes(ei)).hexdigest(), gate, f"field layer {layer} input encoding mismatch")
        clock(row.get("state"), gate, f"field layer {layer}.state", (token * LAYERS + layer + 1) * STEPS_PER_LAYER, token, layer)
        field_payload(row.get("field_output"), gate, f"field layer {layer}.field_output", False)
        metrics = obj(row.get("metrics"), gate, "field layer metrics")
        need(metrics.get("finite") is True, gate, f"field layer {layer} metrics finite flag false")
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                need(math.isfinite(float(value)), gate, f"field layer {layer} metric {key} non-finite")
def link_last_field_output(event: Mapping[str, Any], readout_field: Mapping[str, Any], gate: str, label: str) -> None:
    rows = arr(event.get("field_layer_updates"), gate, f"{label} updates")
    last_field = obj(obj(rows[-1], gate, f"{label} last update").get("field_output"), gate, f"{label} last field output")
    for key in ("ey_sha256", "ei_sha256", "sha256"):
        if key in last_field and key in readout_field:
            need(sha(last_field[key], gate, f"{label} last {key}") == sha(readout_field[key], gate, f"{label} readout {key}"), gate, f"{label} last update/readout {key} linkage mismatch")



def output_check(event: Mapping[str, Any], source: dict[str, Any], decoded: np.ndarray, gate: str) -> tuple[Mapping[str, Any], np.ndarray]:
    output = obj(event.get("output"), gate, "output")
    need(output.get("mode") == "residual" and output.get("mode_detail") == "field_augmented_output_features", gate, "output mode mismatch")
    need(close(number(output.get("coupling"), gate, "coupling"), COUPLING, 0, 0), gate, "coupling mismatch")
    need(close(number(output.get("head_output_reference_norm"), gate, "reference norm"), float(np.linalg.norm(source["head"].astype(np.float64))), 0, 0), gate, "reference norm mismatch")
    direction = decode_array(output.get("field_direction"), gate, "field direction", (D,))
    features = decode_array(output.get("field_output_features"), gate, "field output features", (D,))
    augmented = decode_array(output.get("field_augmented_output_features"), gate, "augmented output features", (D,))
    same_bytes(direction, decoded, gate, "decoded direction")
    same_bytes(augmented, np.ascontiguousarray(source["head"] + np.float32(COUPLING) * features), gate, "augmented output features")
    field_logits = decode_array(output.get("field_only_logits"), gate, "field-only logits")
    augmented_logits = decode_array(output.get("field_augmented_logits"), gate, "field-augmented logits")
    selected_logits = decode_array(output.get("selected_logits"), gate, "selected logits")
    need(field_logits.ndim == augmented_logits.ndim == selected_logits.ndim == 1 and field_logits.size >= TOP_K and field_logits.size == augmented_logits.size == selected_logits.size, gate, "output logits shape mismatch")
    same_bytes(selected_logits, augmented_logits, gate, "selected residual logits")
    top_k(output.get("field_only_top_k"), field_logits, gate, "field-only top-k")
    top_k(output.get("field_augmented_top_k"), augmented_logits, gate, "field-augmented top-k")
    top_k(output.get("selected_top_k"), selected_logits, gate, "selected top-k")
    need("virtual_decode" not in output, gate, "unexpected virtual decode")
    return output, augmented_logits


def candidate_rows(ordinary: np.ndarray, field: np.ndarray) -> list[dict[str, Any]]:
    ids = np.arange(ordinary.size, dtype=np.int64)
    order = np.lexsort((ids, -field.astype(np.float64)))[:TOP_K]
    return [{"rank": rank, "token_id": int(i), "score": float(field[i]), "ordinary_score": float(ordinary[i]), "field_score": float(field[i])} for rank, i in enumerate(order, 1)]


def plan_check(event: Mapping[str, Any], ordinary: np.ndarray, field: np.ndarray, token: int, gate: str) -> Mapping[str, Any]:
    plan = obj(event.get("plan"), gate, "plan")
    need(integer(plan.get("token_index"), gate, "plan token") == token and plan.get("field_enabled") is True and plan.get("external_actions") == [] and plan.get("actions") == [], gate, "planner token/field/action contract mismatch")
    integer(plan.get("position"), gate, "plan position")
    expected = candidate_rows(ordinary, field)
    actual = arr(plan.get("ranked_candidates"), gate, "ranked candidates")
    need(len(actual) == TOP_K, gate, "planner candidate count mismatch")
    for rank, wanted in enumerate(expected):
        got = obj(actual[rank], gate, "planner candidate")
        for key in ("rank", "token_id"):
            need(integer(got.get(key), gate, key) == wanted[key], gate, f"planner {key} mismatch at rank {rank + 1}")
        for key in ("score", "ordinary_score", "field_score"):
            need(close(number(got.get(key), gate, key), wanted[key], 0, 0), gate, f"planner {key} mismatch at rank {rank + 1}")
    need(plan.get("candidates") == actual and plan.get("retrieved_memory") == plan.get("memory") and plan.get("finite") is True, gate, "planner aliases/finiteness mismatch")
    return plan


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(np.float64), b.astype(np.float64)
    denominator = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    return 0.0 if denominator == 0 else float(np.dot(a, b) / denominator)


def check_memory(event: Mapping[str, Any], plan: Mapping[str, Any], query: np.ndarray, previous: list[dict[str, Any]], gate: str) -> None:
    actual, planned = arr(event.get("memory"), gate, "event memory"), arr(plan.get("retrieved_memory"), gate, "plan memory")
    need(actual == planned, gate, "event/plan memory aliases differ")
    ranked = []
    for insertion, item in enumerate(previous):
        row = {key: item[key] for key in ("record_id", "token_index", "token_id", "piece", "source")}
        row["score"] = cosine(query, item["vector"])
        ranked.append(((-row["score"], 0, item["token_index"], item["record_id"], insertion), row))
    expected = [row for _, row in sorted(ranked)[:4]]
    need(len(actual) == len(expected), gate, "memory retrieval length mismatch")
    for index, (got_value, wanted) in enumerate(zip(actual, expected)):
        got = obj(got_value, gate, "memory row")
        for key in ("record_id", "token_index", "token_id", "piece", "source"):
            need(got.get(key) == wanted[key], gate, f"memory {key} mismatch at rank {index + 1}")
        need(close(number(got.get("score"), gate, "memory score"), wanted["score"]), gate, f"memory cosine mismatch at rank {index + 1}")


def event_link(meta: Any, raw: bytes, index: int, path: str, gate: str, label: str) -> None:
    meta = obj(meta, gate, label)
    need(integer(meta.get("event_index"), gate, "event index") == index and integer(meta.get("bytes"), gate, "event bytes") == len(raw) and sha(meta.get("sha256"), gate, "event hash") == hashlib.sha256(raw).hexdigest() and str(meta.get("path")) == path, gate, f"{label} linkage mismatch")


def header(receipt: Mapping[str, Any], receipt_path: Path) -> Path:
    need(receipt.get("protocol") == PROTOCOL and integer(receipt.get("version"), "header", "version") == VERSION and receipt.get("verdict") == "PASS" and receipt.get("finite") is True, "header", "protocol/version/verdict mismatch")
    config = obj(receipt.get("config"), "header", "config")
    need(config.get("prompt") == PROMPT and integer(config.get("max_tokens"), "header", "max_tokens") == 4 and config.get("output_mode") == "residual" and close(number(config.get("coupling"), "header", "coupling"), COUPLING, 0, 0), "header", "frozen configuration mismatch")
    field = obj(config.get("field"), "header", "field config")
    need(field.get("grid_n") == N and field.get("dimension") == D and field.get("dtype") == DTYPE and field.get("layout") == LAYOUT and close(number(field.get("retained_weight"), "header", "retained weight"), RETAINED, 0, 0) and integer(field.get("steps_per_layer"), "header", "steps") == STEPS_PER_LAYER, "header", "field config mismatch")
    lab = obj(config.get("lab"), "header", "lab config")
    need(lab.get("host") == "127.0.0.1" and integer(lab.get("port"), "header", "lab port") == 7601, "header", "lab config mismatch")
    model = text(config.get("model"), "header", "model path")
    need(Path(model).name == MODEL_NAME and sha(config.get("model_sha256"), "header", "model SHA") == MODEL_SHA, "header", "model identity mismatch")
    hello = obj(receipt.get("lab_hello"), "header", "lab hello")
    need(hello.get("protocol") == PROTOCOL and integer(hello.get("version"), "header", "hello version") == VERSION and hello.get("ok") is True and hello.get("finite") is True, "header", "lab hello mismatch")
    server, engine = obj(hello.get("server"), "header", "server"), obj(hello.get("engine"), "header", "engine")
    need(server.get("host") == "127.0.0.1" and integer(server.get("port"), "header", "server port") == 7601 and server.get("lab_only") is True and engine.get("grid_n") == N and close(number(engine.get("dt"), "header", "dt"), DT, 0, 0) and engine.get("auto_step") is False and engine.get("serve_bridge") is False, "header", "lab identity mismatch")
    hf = obj(hello.get("field"), "header", "hello field")
    need(hf.get("grid_n") == N and hf.get("cells") == CELLS and hf.get("dtype") == DTYPE and hf.get("layout") == LAYOUT and hf.get("channels") == 2 and hf.get("channel_names") == ["EY", "EI"], "header", "hello field mismatch")
    head = obj(receipt.get("head"), "header", "head")
    need(head.get("architecture") == "qwen35", "header", "head architecture mismatch")
    metadata = obj(head.get("metadata"), "header", "head metadata")
    need(str(metadata.get("general.architecture", "")).lower().replace(".", "") == "qwen35", "header", "GGUF architecture mismatch")
    parity = obj(head.get("head_parity"), "header", "head parity")
    for key in ("head_output_sha256", "ordinary_logits_sha256", "reconstructed_logits_sha256"):
        sha(parity.get(key), "header", key)
    delta = number(parity.get("max_abs_logit_delta"), "header", "parity delta")
    need(
        parity.get("finite") is True
        and parity.get("argmax_match") is True
        and 0.0 <= delta <= 0.25,
        "header",
        "direct output-head parity metadata is outside the frozen Q6_K tolerance",
    )
    ids = obj(parity.get("top16_ids"), "header", "parity IDs")
    ordinary_ids = arr(ids.get("ordinary"), "header", "parity ordinary IDs")
    reconstructed_ids = arr(ids.get("reconstructed"), "header", "parity reconstructed IDs")
    need(
        len(ordinary_ids) == TOP_K
        and len(reconstructed_ids) == TOP_K
        and ordinary_ids[0] == reconstructed_ids[0],
        "header",
        "parity top-k argmax mismatch",
    )
    event_text = text(obj(receipt.get("event_log"), "header", "event log").get("path"), "header", "event path")
    event_path = Path(event_text)
    return event_path if event_path.is_absolute() else receipt_path.parent / event_path


def verify(receipt_path: Path) -> list[str]:
    receipt = obj(load_json(receipt_path.read_bytes(), "receipt", "receipt"), "receipt", "receipt")
    event_path = header(receipt, receipt_path)
    event_meta = obj(receipt.get("event_log"), "event log", "event log")
    event_raw = event_path.read_bytes()
    need(sha(event_meta.get("sha256"), "event log", "event log SHA") == hashlib.sha256(event_raw).hexdigest() and event_raw, "event log", "linked event log missing/hash mismatch")
    lines = event_raw.splitlines(keepends=True)
    need(all(line.endswith(b"\n") for line in lines), "event log", "event log line missing LF")
    metadata, terminal_meta = arr(receipt.get("events"), "event log", "receipt events"), obj(receipt.get("terminal_event"), "event log", "terminal metadata")
    need(len(lines) == len(metadata) + 1, "event log", "event count mismatch")
    events = []
    for index, (raw, meta) in enumerate(zip(lines[:-1], metadata)):
        event_link(meta, raw, index, str(event_path), "event log", f"event {index}")
        event = obj(load_json(raw[:-1], "event log", f"event {index}"), "event log", f"event {index}")
        need(event.get("protocol") == PROTOCOL and integer(event.get("version"), "event log", "event version") == VERSION and event.get("run_id") == receipt.get("run_id") and event.get("event_kind") == "output" and integer(event.get("token_index"), "event log", "event token") == index, "event log", f"event {index} identity mismatch")
        events.append(event)
    terminal_raw = lines[-1]
    event_link(terminal_meta, terminal_raw, len(events), str(event_path), "event log", "terminal")
    terminal = obj(load_json(terminal_raw[:-1], "terminal", "terminal"), "terminal", "terminal")
    need(terminal.get("protocol") == PROTOCOL and integer(terminal.get("version"), "terminal", "version") == VERSION and terminal.get("run_id") == receipt.get("run_id") and terminal.get("event_kind") == "terminal_field_update", "terminal", "terminal identity mismatch")
    generated = obj(receipt.get("generated"), "sequence", "generated")
    generated_ids, generated_pieces = arr(generated.get("token_ids"), "sequence", "generated IDs"), arr(generated.get("pieces"), "sequence", "generated pieces")
    need(len(generated_ids) == len(generated_pieces) == len(events) > 0 and integer(generated.get("count"), "sequence", "generated count") == len(events) and generated.get("text") == "".join(text(x, "sequence", "piece") for x in generated_pieces), "sequence", "generated sequence mismatch")
    prompt = obj(receipt.get("prompt"), "sequence", "prompt")
    prompt_ids = arr(prompt.get("token_ids"), "sequence", "prompt IDs")
    need(integer(prompt.get("token_count"), "sequence", "prompt count") == len(prompt_ids) > 0, "sequence", "prompt count mismatch")
    previous = []
    for index, event in enumerate(events):
        source = record(event.get("field_source"), "events", f"event {index} source", -1 if index == 0 else index - 1, "initial_tokens" if index == 0 else "token", index, list(range(len(prompt_ids))) if index == 0 else None)
        if index == 0:
            parity = obj(obj(receipt.get("head"), "header", "head").get("head_parity"), "header", "head parity")
            need(sha(parity.get("head_output_sha256"), "header", "head parity output hash") == sha(source["item"]["head_output_reference"].get("sha256"), "header", "source output hash"), "header", "head parity/output-reference hash linkage mismatch")
            need(sha(parity.get("ordinary_logits_sha256"), "header", "head parity ordinary hash") == sha(source["item"]["ordinary_logits"].get("sha256"), "header", "source ordinary hash"), "header", "head parity/ordinary-logits hash linkage mismatch")
        if index == 0:
            need(source["ids"] == prompt_ids, "sequence", "initial source/prompt mismatch")
        else:
            prior = obj(events[index - 1].get("committed_decode"), "sequence", "prior commit")
            need(source["ids"] == arr(prior.get("token_ids"), "sequence", "prior IDs") and source["positions"] == arr(prior.get("token_positions"), "sequence", "prior positions"), "sequence", f"event {index} source continuity mismatch")
        readout = obj(event.get("field_readout"), "field", f"event {index} readout")
        clock(readout.get("state"), "field", f"event {index} clock", (index + 1) * STEPS_PER_TOKEN, index, LAYERS - 1)
        ey, ei = field_payload(readout.get("field"), "field", f"event {index} field", True)
        assert ey is not None and ei is not None
        same_bytes(decode_array(readout.get("ey"), "field", f"event {index} EY", (CELLS,)), ey, "field", "EY")
        same_bytes(decode_array(readout.get("ei"), "field", f"event {index} EI", (CELLS,)), ei, "field", "EI")
        field_metrics(readout, ey, ei, "field", f"event {index}")
        decoded_raw = decode_field(ey, ei)
        decoded = np.ascontiguousarray(decoded_raw / np.float32(np.linalg.norm(decoded_raw.astype(np.float64))))
        updates(event, source, "field", index)
        link_last_field_output(event, obj(readout.get("field"), "field", f"event {index} field"), "field", f"event {index}")
        output, augmented = output_check(event, source, decoded, "output")
        plan = plan_check(event, source["logits"], augmented, index, "planner")
        need(integer(plan.get("position"), "sequence", "plan position") == source["positions"][-1] + 1, "sequence", f"event {index} output position is not source-final plus one")
        selected_id, selected_piece = integer(event.get("selected_token_id"), "sequence", "selected ID"), text(event.get("selected_piece"), "sequence", "selected piece")
        need(selected_id == generated_ids[index] and selected_piece == generated_pieces[index] and plan.get("selected_token_id") == selected_id and plan.get("selected_piece") == selected_piece, "sequence", f"event {index} selected token mismatch")
        selected_top = arr(output.get("selected_top_k"), "candidates", "selected top-k")
        need(integer(obj(selected_top[0], "candidates", "top row").get("token_id"), "candidates", "top token") == selected_id, "candidates", f"event {index} selected token is not top candidate")
        need(event.get("candidates") == plan.get("ranked_candidates"), "candidates", f"event {index} candidate alias mismatch")
        check_memory(event, plan, decoded, previous, "memory")
        previous.append({"record_id": f"token-{index}-{index}", "token_index": index, "token_id": selected_id, "piece": selected_piece, "source": "token", "vector": decoded})
        committed = record(event.get("committed_decode"), "sequence", f"event {index} commit", index, "token", index + 1)
        need(committed["ids"] == [selected_id] and committed["pieces"] == [selected_piece] and committed["positions"] == [integer(plan.get("position"), "sequence", "commit position")], "sequence", f"event {index} commit mismatch")
        need(event.get("finite") is True, "events", f"event {index} finite flag false")
    count = len(events)
    need(integer(terminal.get("token_index"), "terminal", "terminal token") == count, "terminal", "terminal token mismatch")
    terminal_source = record(terminal.get("field_source"), "terminal", "terminal source", count - 1, "token", count)
    need(terminal_source["ids"] == [generated_ids[-1]], "terminal", "terminal source mismatch")
    terminal_readout = obj(terminal.get("field_readout"), "terminal", "terminal readout")
    clock(terminal_readout.get("state"), "terminal", "terminal clock", (count + 1) * STEPS_PER_TOKEN, count, LAYERS - 1)
    tey, tei = field_payload(terminal_readout.get("field"), "terminal", "terminal field", True)
    assert tey is not None and tei is not None
    field_metrics(terminal_readout, tey, tei, "terminal", "terminal field")
    terminal_decoded_raw = decode_field(tey, tei)
    terminal_decoded = np.ascontiguousarray(terminal_decoded_raw / np.float32(np.linalg.norm(terminal_decoded_raw.astype(np.float64))))
    updates(terminal, terminal_source, "terminal", count)
    link_last_field_output(terminal, obj(terminal_readout.get("field"), "terminal", "terminal field"), "terminal", "terminal")
    same_bytes(decode_array(terminal.get("decoded_field_direction"), "terminal", "terminal direction", (D,)), terminal_decoded, "terminal", "direction")
    final_field = obj(receipt.get("final_field"), "final", "final field")
    need(obj(final_field.get("state"), "final", "final state") == obj(terminal_readout.get("state"), "final", "terminal state"), "final", "final state differs from terminal")
    fey, fei = field_payload(final_field.get("field"), "final", "final field", True)
    assert fey is not None and fei is not None
    same_bytes(fey, tey, "final", "final EY")
    same_bytes(fei, tei, "final", "final EI")
    field_metrics(final_field, fey, fei, "final", "final field")
    need(terminal.get("finite") is True and receipt.get("finite") is True, "final", "terminal or receipt finite flag false")
    memory = arr(receipt.get("memory"), "memory", "receipt memory")
    need(len(memory) == count + 1, "memory", "receipt memory count mismatch")
    for index, value in enumerate(memory[:-1]):
        item = obj(value, "memory", "receipt memory row")
        need(all(item.get(key) == previous[index][key] for key in ("record_id", "token_index", "token_id", "piece", "source")), "memory", f"receipt memory {index} mismatch")
    terminal_memory = obj(memory[-1], "memory", "terminal memory")
    need(terminal_memory.get("record_id") == f"token-{count}-{count}" and terminal_memory.get("token_index") == count and terminal_memory.get("token_id") == generated_ids[-1] and terminal_memory.get("piece") == generated_pieces[-1] and terminal_memory.get("source") == "terminal_committed_token", "memory", "terminal memory mismatch")
    return ["protocol/version/config/model identity", "UTF-8 receipt and linked event-log SHA", "raw f32 hashes/shapes/finiteness/norms", "64 trunk captures and ordered field updates", "field clock, 256 steps/token, bounded state", "public output seam and head parity metadata", "logits/top-k/candidate ranks", "token and commit position continuity", "cosine memory retrieval and planner no-action", "terminal update and final receipt consistency"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=Path(__file__).resolve().parent / "_diag" / "l18-field-output-loop" / "l18-first.receipt.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        gates = verify(build_parser().parse_args(argv).receipt)
    except (OSError, VerifyError) as error:
        if isinstance(error, VerifyError):
            print(f"FAIL {error.gate}: {error.message}", file=sys.stderr)
        else:
            print(f"FAIL io: {error}", file=sys.stderr)
        return 1
    for gate in gates:
        print(f"PASS {gate}")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
