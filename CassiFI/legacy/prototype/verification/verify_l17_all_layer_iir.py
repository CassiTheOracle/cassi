"""Independent NumPy verifier for the CassiQwen L17 all-layer IIR observatory.

This verifier is deliberately read-only. It loads the four frozen JSON
artifacts, independently checks their hashes and schemas, reconstructs the
N=32 real-periodic Fourier bases, decodes both 64-layer CPU seeds, validates
all GPU raw checkpoints and recurrence metadata, and checks the reduced Node
receipt. It never imports the production codec, loads Qwen, starts Godot, or
uses a network connection.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np


_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from cassi_fi_paths import ARTIFACT_DIR, WORKSPACE_ROOT

DEFAULT_CAPTURE = ARTIFACT_DIR / "native" / "all-layer-hidden-state-capture.json"
DEFAULT_SEED = WORKSPACE_ROOT / "CassiCosmos" / "_diag" / "cassi_qwen_all_layer_iir_seed.json"
DEFAULT_GPU = WORKSPACE_ROOT / "CassiCosmos" / "_diag" / "cassi_qwen_all_layer_iir_gpu.json"
DEFAULT_RECEIPT = ARTIFACT_DIR / "native" / "all-layer-iir-observatory.json"

PROTOCOL = "CassiQwen L17 all-layer IIR field observatory"
VERSION = 1
N = 32
VOLUME = N**3
DIMENSION = 5120
MODE_COUNT = DIMENSION // 2
PHI = 1.618033988749895
AMPLITUDE = 1.0
DT = 0.005
LAYOUT = "x + N*(y + N*z)"
DTYPE = "float32-le"
RETAINED_WEIGHT = 0.9
INPUT_WEIGHT = 1.0 - RETAINED_WEIGHT
STEPS_PER_LAYER = 4
LAYER_COUNT = 64
LAYER_CHECKPOINTS = [0, 1, 2, 3, 7, 15, 31, 47, 63]
CONTINUATION_HORIZONS = [0, 1, 4, 16, 64]
FORWARD_ORDER = list(range(LAYER_COUNT))
REVERSE_ORDER = list(reversed(FORWARD_ORDER))
ARM_IDS = ["forward_canonical", "reverse_canonical", "forward_shuffled", "zero"]
ARM_BASIS = {
    "forward_canonical": "canonical",
    "reverse_canonical": "canonical",
    "forward_shuffled": "shuffled",
    "zero": "zero",
}
SHUFFLE_SEED = 0x51F71E1D
TOP_K = 16
COSINE_MIN = 0.999999
RELATIVE_L2_MAX = 2e-6
LOGIT_DELTA_MAX = 1e-6
MAX_FIELD_ABS = 10.0
FIRST_BLEND_ERROR_MAX = 2e-6
H4_THRESHOLD = 1e-4

MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
MODEL_PATH = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL_ARCHITECTURE = "qwen35"
MODEL_VOCABULARY_SIZE = 248320
RUNTIME_EXPECTED = {
    "llama_version": "0.1.1-dev",
    "package_build": 10472,
    "package_commit": "60eeeb608",
    "requested_gpu_layers": 99,
    "context_size": 512,
    "batch_size": 512,
}
RUNTIME_FILES = {
    "llama_dll": "llama.dll",
    "ggml_dll": "ggml.dll",
    "ggml_base_dll": "ggml-base.dll",
    "openmp_dll": "libomp140.x86_64.dll",
}
RUNTIME_HASHES = {
    "llama_dll_sha256": "d5bb3c11dd5767f4f0041e04a82e1c2fd54c687f1996706bba6e3bfdb7d3c5a6",
    "ggml_dll_sha256": "362831c05b00cc6b7dabf0f4868894564f52740d0c3ae6a1d7f3d13e38046942",
    "ggml_base_dll_sha256": "841889f26faacff284c2c5607f96358d2bbd0605c36fb33709e7e9490d2fec5b",
    "openmp_dll_sha256": "4a20c1e5c115c29771a12324513eb109badac72180f79481527ad79d996ffb33",
}
PROMPT_UTF8 = "Cassi hidden-state observatory: reply with exactly one physical field name."
PROMPT_SHA256 = "d4d47a5b46c1c6ba6706643da2a73b752572bf2d862c55f7171bab255c6628ad"
PROMPT_TOKEN_IDS = [34, 78732, 7920, 20105, 9006, 5101, 25, 9559, 440, 6681, 799, 6745, 2002, 803, 13]
PROMPT_TOKENIZATION = {"add_special": True, "parse_special": True}


class VerificationError(RuntimeError):
    """A descriptive contract failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def as_object(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def as_array(value: Any, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} must be an array")
    return value


def require_bool(value: Any, label: str) -> bool:
    require(type(value) is bool, f"{label} must be boolean")
    return value


def require_int(value: Any, label: str) -> int:
    require(type(value) is int, f"{label} must be an integer")
    return value


def finite_number(value: Any, label: str) -> float:
    require(type(value) in (int, float), f"{label} must be numeric")
    result = float(value)
    require(math.isfinite(result), f"{label} must be finite")
    return result


def close(actual: Any, expected: Any, tolerance: float = 2e-6) -> bool:
    try:
        left = float(actual)
        right = float(expected)
    except (TypeError, ValueError):
        return False
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def close_abs(actual: Any, expected: Any, tolerance: float = 1e-6) -> bool:
    try:
        left = float(actual)
        right = float(expected)
    except (TypeError, ValueError):
        return False
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tolerance


def exact_array(actual: Any, expected: list[Any], label: str) -> None:
    require(isinstance(actual, list), f"{label} must be an array")
    require(len(actual) == len(expected), f"{label} length mismatch")
    for index, expected_value in enumerate(expected):
        value = actual[index]
        if type(value) is not type(expected_value) or value != expected_value:
            raise VerificationError(f"{label}[{index}] mismatch")


def load_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except Exception as error:
        raise VerificationError(f"{path}: invalid UTF-8 JSON: {error}") from error
    require(isinstance(document, dict), f"{path.name}: root is not an object")
    return raw, document


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_base64_raw(value: Any, label: str, expected_bytes: int | None = None) -> bytes:
    require(isinstance(value, str), f"{label} base64 is absent")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as error:
        raise VerificationError(f"{label} base64 is malformed: {error}") from error
    require(base64.b64encode(raw).decode("ascii") == value, f"{label} base64 is not canonical")
    if expected_bytes is not None:
        require(len(raw) == expected_bytes, f"{label} byte length mismatch")
    return raw


def decode_f32(value: Any, count: int, label: str) -> tuple[bytes, np.ndarray]:
    raw = decode_base64_raw(value, label, count * 4)
    result = np.frombuffer(raw, dtype="<f4").copy()
    require(result.size == count, f"{label} shape mismatch")
    require(bool(np.isfinite(result).all()), f"{label} contains non-finite values")
    return raw, result


def validate_base64_hash(value: Any, expected_hash: Any, byte_count: int, label: str) -> bytes:
    raw = decode_base64_raw(value, label, byte_count)
    require(isinstance(expected_hash, str) and len(expected_hash) == 64, f"{label} SHA-256 is malformed")
    require(sha256_bytes(raw) == expected_hash, f"{label} SHA-256 mismatch")
    return raw


def flat_index(x: int, y: int, z: int) -> int:
    return x + N * (y + N * z)


def wrapped(index: int) -> int:
    return index if index <= N // 2 else index - N


def canonical_modes() -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int, int, int, int]] = []
    for z in range(N):
        for y in range(N):
            for x in range(N):
                negative = flat_index((-x) % N, (-y) % N, (-z) % N)
                index = flat_index(x, y, z)
                if index == negative:
                    continue
                kx, ky, kz = wrapped(x), wrapped(y), wrapped(z)
                candidates.append((kx * kx + ky * ky + kz * kz, kz, ky, kx, index, negative))
    candidates.sort(key=lambda row: row[:5])
    seen = np.zeros(VOLUME, dtype=np.bool_)
    result: list[tuple[int, int, int]] = []
    for _, _, _, _, index, negative in candidates:
        if seen[index]:
            continue
        seen[index] = True
        seen[negative] = True
        x = index % N
        y = (index // N) % N
        z = index // (N * N)
        result.append((x, y, z))
    require(len(result) >= MODE_COUNT, "canonical Fourier mode capacity is insufficient")
    return result[:MODE_COUNT]


def xorshift32(value: int) -> int:
    value &= 0xFFFFFFFF
    value ^= (value << 13) & 0xFFFFFFFF
    value &= 0xFFFFFFFF
    value ^= value >> 17
    value &= 0xFFFFFFFF
    value ^= (value << 5) & 0xFFFFFFFF
    return value & 0xFFFFFFFF


def shuffled_modes(canonical: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    result = list(canonical)
    state = SHUFFLE_SEED
    for index in range(len(result) - 1, 0, -1):
        state = xorshift32(state)
        swap = state % (index + 1)
        result[index], result[swap] = result[swap], result[index]
    return result


def mode_manifest(canonical: list[tuple[int, int, int]], shuffled: list[tuple[int, int, int]]) -> dict[str, Any]:
    return {
        "kind": "real-periodic-fourier",
        "flat_layout": LAYOUT,
        "coefficient_pair": "X[k]=sqrt(V/2)*(a-i*b), X[-k]=conjugate(X[k])",
        "mode_order": "k2 then signed (kz,ky,kx)",
        "canonical": {"capacity": MODE_COUNT, "modes": [list(mode) for mode in canonical]},
        "shuffled": {
            "capacity": MODE_COUNT,
            "seed": "0x51f71e1d",
            "modes": [list(mode) for mode in shuffled],
        },
    }


def normalize(values: np.ndarray, label: str) -> tuple[np.ndarray, float]:
    source = np.asarray(values, dtype=np.float64)
    norm = float(np.sqrt(np.sum(source * source, dtype=np.float64)))
    require(math.isfinite(norm) and norm > 0.0, f"{label} norm is invalid")
    return source / norm, norm


def byte_zero(values: np.ndarray) -> bool:
    return not bool(np.any(values.view(np.uint8)))


def relative_l2(actual: np.ndarray, expected: np.ndarray) -> float:
    left = np.asarray(actual, dtype=np.float64)
    right = np.asarray(expected, dtype=np.float64)
    denominator = float(np.sqrt(np.sum(right * right, dtype=np.float64)))
    numerator = float(np.sqrt(np.sum((left - right) * (left - right), dtype=np.float64)))
    if denominator == 0.0:
        return 0.0 if numerator == 0.0 else math.inf
    return numerator / denominator


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    left64 = np.asarray(left, dtype=np.float64)
    right64 = np.asarray(right, dtype=np.float64)
    left_norm = float(np.sqrt(np.sum(left64 * left64, dtype=np.float64)))
    right_norm = float(np.sqrt(np.sum(right64 * right64, dtype=np.float64)))
    denominator = left_norm * right_norm
    return 0.0 if denominator == 0.0 else float(np.sum(left64 * right64, dtype=np.float64) / denominator)


def encode_unit(vector: np.ndarray, modes: list[tuple[int, int, int]]) -> tuple[np.ndarray, np.ndarray]:
    """Independent NumPy equivalent of the production Fourier construction."""
    normalized, _ = normalize(vector, "embedding")
    spectrum = np.zeros((N, N, N), dtype=np.complex128)
    scale = AMPLITUDE * math.sqrt(VOLUME / 2.0)
    for pair, (x, y, z) in enumerate(modes):
        coefficient = scale * complex(float(normalized[2 * pair]), -float(normalized[2 * pair + 1]))
        spectrum[x, y, z] = coefficient
        spectrum[(-x) % N, (-y) % N, (-z) % N] = coefficient.conjugate()
    signal = np.fft.ifftn(spectrum, axes=(0, 1, 2)).real.reshape(VOLUME, order="F").astype("<f4")
    ey = np.zeros(VOLUME, dtype="<f4")
    ei = np.zeros(VOLUME, dtype="<f4")
    positive = signal > 0.0
    negative = signal < 0.0
    ey[positive] = signal[positive]
    ei[negative] = (-signal[negative].astype(np.float64) / PHI).astype("<f4")
    return ey, ei


def decode_unit(ey: np.ndarray, ei: np.ndarray, modes: list[tuple[int, int, int]]) -> tuple[np.ndarray, float]:
    epsilon = ey.astype(np.float64) - PHI * ei.astype(np.float64)
    volume = epsilon.reshape((N, N, N), order="F")
    spectrum = np.fft.fftn(volume, axes=(0, 1, 2))
    scale = AMPLITUDE * math.sqrt(VOLUME / 2.0)
    direction = np.empty(DIMENSION, dtype=np.float64)
    selected = np.zeros((N, N, N), dtype=np.bool_)
    for pair, (x, y, z) in enumerate(modes):
        value = spectrum[x, y, z]
        direction[2 * pair] = float(value.real / scale)
        direction[2 * pair + 1] = float(-value.imag / scale)
        selected[x, y, z] = True
        selected[(-x) % N, (-y) % N, (-z) % N] = True
    energy = spectrum.real * spectrum.real + spectrum.imag * spectrum.imag
    total = float(np.sum(energy, dtype=np.float64))
    residual = 0.0 if total == 0.0 else float(np.sum(energy[~selected], dtype=np.float64) / total)
    require(bool(np.isfinite(direction).all()), "decoded Fourier direction is non-finite")
    require(math.isfinite(residual), "decoded Fourier residual is non-finite")
    return direction, residual


def field_metrics(ey: np.ndarray, ei: np.ndarray, modes: list[tuple[int, int, int]]) -> dict[str, float | bool]:
    require(ey.size == VOLUME and ei.size == VOLUME, "field channel shape mismatch")
    require(bool(np.isfinite(ey).all()) and bool(np.isfinite(ei).all()), "field contains non-finite values")
    ey64 = ey.astype(np.float64)
    ei64 = ei.astype(np.float64)
    epsilon = ey64 - PHI * ei64
    max_abs = float(max(np.max(np.abs(ey64)), np.max(np.abs(ei64))))
    ey_l2 = float(np.sqrt(np.sum(ey64 * ey64, dtype=np.float64)))
    ei_l2 = float(np.sqrt(np.sum(ei64 * ei64, dtype=np.float64)))
    epsilon_l2 = float(np.sqrt(np.sum(epsilon * epsilon, dtype=np.float64)))
    _, residual = decode_unit(ey, ei, modes)
    return {
        "finite": True,
        "max_abs": max_abs,
        "ey_l2": ey_l2,
        "ei_l2": ei_l2,
        "epsilon_l2": epsilon_l2,
        "subspace_residual_energy": residual,
    }


def expected_top16(logits: np.ndarray) -> list[int]:
    token_ids = np.arange(logits.size, dtype=np.int64)
    order = np.lexsort((token_ids, -logits.astype(np.float64)))[:TOP_K]
    return [int(value) for value in order]


def validate_top16(logits: np.ndarray, rows: Any, label: str) -> list[int]:
    rows_list = as_array(rows, f"{label} top16")
    require(len(rows_list) == TOP_K, f"{label} top16 has wrong shape")
    expected_ids = expected_top16(logits)
    for rank, expected_id in enumerate(expected_ids):
        row = as_object(rows_list[rank], f"{label} top16 row {rank}")
        require_int(row.get("token_id"), f"{label} top16 row {rank}.token_id")
        finite_number(row.get("logit"), f"{label} top16 row {rank}.logit")
        require(row["token_id"] == expected_id, f"{label} top16 token rank {rank} mismatch")
        require(close(row["logit"], float(logits[expected_id]), 1e-7), f"{label} top16 logit rank {rank} mismatch")
    return expected_ids


def validate_capture(document: dict[str, Any], raw_bytes: bytes) -> dict[str, Any]:
    require(document.get("protocol") == PROTOCOL, "capture protocol mismatch")
    require(document.get("version") == VERSION, "capture version mismatch")
    require(document.get("verdict") in ("PASS", "FAIL"), "capture verdict is malformed")

    model = as_object(document.get("model"), "capture model")
    expected_model = {
        "path": MODEL_PATH,
        "sha256": MODEL_SHA256,
        "architecture": MODEL_ARCHITECTURE,
        "hidden_dimension": DIMENSION,
        "layer_count": LAYER_COUNT,
        "vocabulary_size": MODEL_VOCABULARY_SIZE,
    }
    for key, expected in expected_model.items():
        require(model.get(key) == expected, f"capture model.{key} mismatch")

    runtime = as_object(document.get("runtime"), "capture runtime")
    for key, expected in RUNTIME_EXPECTED.items():
        require(runtime.get(key) == expected, f"capture runtime.{key} mismatch")
    for key, expected in RUNTIME_FILES.items():
        require(runtime.get(key) == expected, f"capture runtime.{key} mismatch")
    for key, expected in RUNTIME_HASHES.items():
        require(runtime.get(key) == expected, f"capture runtime.{key} mismatch")
    require(runtime.get("backend_loader") == "ggml_backend_load_all_from_path", "capture backend loader mismatch")
    require(runtime.get("backend_path") == "CassiQwen", "capture backend path mismatch")

    hook = as_object(document.get("hook"), "capture hook")
    require(hook.get("kind") == "all_layer_input_residuals", "capture hook kind mismatch")
    require(hook.get("layer_rule") == "0..n_layer-1", "capture hook layer rule mismatch")
    exact_array(hook.get("layer_indices"), FORWARD_ORDER, "capture hook layer indices")
    require_int(hook.get("token_row"), "capture hook token row")
    require("llama_set_embeddings_layer_inp" in str(hook.get("setter_export", "")), "capture setter export mismatch")
    require("llama_get_embeddings_layer_inp" in str(hook.get("getter_export", "")), "capture getter export mismatch")

    prompt = as_object(document.get("prompt"), "capture prompt")
    require(prompt.get("utf8") == PROMPT_UTF8, "capture prompt bytes mismatch")
    require(prompt.get("sha256") == PROMPT_SHA256, "capture prompt SHA-256 mismatch")
    require(prompt.get("tokenization") == PROMPT_TOKENIZATION, "capture prompt tokenization mismatch")
    exact_array(prompt.get("token_ids"), PROMPT_TOKEN_IDS, "capture prompt token IDs")
    require(prompt.get("token_count") == len(PROMPT_TOKEN_IDS), "capture prompt token count mismatch")
    require(prompt.get("final_token_index") == len(PROMPT_TOKEN_IDS) - 1, "capture final token index mismatch")
    require(prompt.get("final_token_id") == PROMPT_TOKEN_IDS[-1], "capture final token ID mismatch")
    require(hook.get("token_row") == prompt["final_token_index"], "capture hook token row mismatch")

    layers = as_array(document.get("layers"), "capture layers")
    require(len(layers) == LAYER_COUNT, "capture layer rows must contain exactly 64 entries")
    parsed_layers: list[dict[str, Any]] = []
    for index, value in enumerate(layers):
        row = as_object(value, f"capture layer {index}")
        require(row.get("layer_index") == index, f"capture layer {index} true index mismatch")
        raw = validate_base64_hash(row.get("hidden_state_b64"), row.get("hidden_state_sha256"), DIMENSION * 4, f"capture layer {index} hidden state")
        hidden = np.frombuffer(raw, dtype="<f4").copy()
        require(bool(np.isfinite(hidden).all()), f"capture layer {index} hidden state contains non-finite values")
        _, norm = normalize(hidden, f"capture layer {index} hidden state")
        require(close(row.get("hidden_l2_norm"), norm, 1e-12), f"capture layer {index} hidden norm mismatch")
        parsed_layers.append({
            "layer_index": index,
            "hidden": hidden.astype(np.float64),
            "hidden_state_sha256": row["hidden_state_sha256"],
            "hidden_l2_norm": norm,
        })

    logits: list[np.ndarray] = []
    top_ids: list[list[int]] = []
    for arm_name in ("capture_off", "capture_on"):
        arm = as_object(document.get(arm_name), f"capture {arm_name}")
        raw = validate_base64_hash(arm.get("logits_b64"), arm.get("logits_sha256"), MODEL_VOCABULARY_SIZE * 4, f"{arm_name} logits")
        values = np.frombuffer(raw, dtype="<f4").copy()
        require(bool(np.isfinite(values).all()), f"{arm_name} logits contain non-finite values")
        ids = validate_top16(values, arm.get("top16"), arm_name)
        require(arm.get("argmax_token_id") == ids[0], f"{arm_name} argmax metadata mismatch")
        logits.append(values)
        top_ids.append(ids)

    max_delta = float(np.max(np.abs(logits[0].astype(np.float64) - logits[1].astype(np.float64))))
    argmax_match = top_ids[0][0] == top_ids[1][0]
    top_match = top_ids[0] == top_ids[1]
    h1_pass = argmax_match and top_match and max_delta <= LOGIT_DELTA_MAX
    parity = as_object(document.get("parity"), "capture parity")
    require(parity.get("argmax_match") is argmax_match, "capture argmax parity metadata mismatch")
    require(parity.get("top16_token_ids_match") is top_match, "capture top16 parity metadata mismatch")
    require(close(parity.get("max_abs_logit_difference"), max_delta, 1e-12), "capture logit delta metadata mismatch")
    require(close(parity.get("max_abs_logit_difference_bound"), LOGIT_DELTA_MAX, 1e-12), "capture logit delta bound mismatch")
    require(parity.get("pass") is h1_pass, "capture parity pass metadata mismatch")
    require(document.get("verdict") == ("PASS" if h1_pass else "FAIL"), "capture verdict/parity mismatch")
    require(h1_pass, "H1 capture parity failed")

    return {
        "hash": sha256_bytes(raw_bytes),
        "layers": parsed_layers,
        "h1": {
            "pass": True,
            "argmax_token_id": top_ids[0][0],
            "max_abs_logit_difference": max_delta,
            "top16_token_ids_match": True,
        },
    }


def validate_field_common(document: dict[str, Any], label: str, require_amplitude: bool) -> None:
    require(document.get("protocol") == PROTOCOL, f"{label} protocol mismatch")
    require(document.get("version") == VERSION, f"{label} version mismatch")
    require(document.get("grid_n") == N, f"{label} grid_n mismatch")
    require(document.get("dimension") == DIMENSION, f"{label} dimension mismatch")
    require(close(document.get("phi"), PHI, 1e-13), f"{label} phi mismatch")
    require(close(document.get("dt"), DT, 1e-13), f"{label} dt mismatch")
    require(document.get("layout") == LAYOUT and document.get("dtype") == DTYPE, f"{label} layout/dtype mismatch")
    if require_amplitude:
        require(close(document.get("amplitude"), AMPLITUDE, 1e-13), f"{label} amplitude mismatch")


def validate_seed_rows(
    rows: Any,
    capture_layers: list[dict[str, Any]],
    modes: list[tuple[int, int, int]],
    basis_label: str,
) -> list[dict[str, Any]]:
    values = as_array(rows, f"seed {basis_label}_layers")
    require(len(values) == LAYER_COUNT, f"seed {basis_label}_layers must contain exactly 64 rows")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        row = as_object(value, f"seed {basis_label}_layers[{index}]")
        source = capture_layers[index]
        require(row.get("layer_index") == index, f"seed {basis_label}_layers[{index}] layer index mismatch")
        require("signal_b64" not in row, f"seed {basis_label}_layers[{index}] must not duplicate signal")
        require(row.get("hidden_state_sha256") == source["hidden_state_sha256"], f"seed {basis_label}_layers[{index}] hidden hash mismatch")
        require(close(row.get("hidden_l2_norm"), source["hidden_l2_norm"], 1e-12), f"seed {basis_label}_layers[{index}] hidden norm mismatch")
        _, ey = decode_f32(row.get("ey_b64"), VOLUME, f"seed {basis_label}_layers[{index}] EY")
        _, ei = decode_f32(row.get("ei_b64"), VOLUME, f"seed {basis_label}_layers[{index}] EI")
        require(not byte_zero(ey) or not byte_zero(ei), f"seed {basis_label}_layers[{index}] is byte-zero")

        expected_ey, expected_ei = encode_unit(source["hidden"], modes)
        # NumPy pocketfft and the runner's radix-2 JavaScript FFT can differ
        # by a final float32 ULP. The independent construction is accepted
        # only within the frozen relative-L2 tolerance and a 2e-6 absolute cap.
        require(relative_l2(ey, expected_ey) <= RELATIVE_L2_MAX, f"seed {basis_label}_layers[{index}] EY codec mismatch")
        require(relative_l2(ei, expected_ei) <= RELATIVE_L2_MAX, f"seed {basis_label}_layers[{index}] EI codec mismatch")
        require(float(np.max(np.abs(ey.astype(np.float64) - expected_ey.astype(np.float64)))) <= RELATIVE_L2_MAX, f"seed {basis_label}_layers[{index}] EY codec absolute mismatch")
        require(float(np.max(np.abs(ei.astype(np.float64) - expected_ei.astype(np.float64)))) <= RELATIVE_L2_MAX, f"seed {basis_label}_layers[{index}] EI codec absolute mismatch")

        direction, residual = decode_unit(ey, ei, modes)
        normalized, norm = normalize(source["hidden"], f"capture layer {index}")
        restored = direction * source["hidden_l2_norm"]
        direction_cosine = cosine(direction, normalized)
        restored_cosine = cosine(restored, source["hidden"])
        restored_error = relative_l2(restored, source["hidden"])
        require(direction_cosine >= COSINE_MIN, f"seed {basis_label}_layers[{index}] direction cosine failed")
        require(restored_cosine >= COSINE_MIN, f"seed {basis_label}_layers[{index}] restored cosine failed")
        require(restored_error <= RELATIVE_L2_MAX, f"seed {basis_label}_layers[{index}] restored relative L2 failed")
        result.append({
            "layer_index": index,
            "hidden_l2_norm": norm,
            "direction_cosine": direction_cosine,
            "restored_cosine": restored_cosine,
            "restored_relative_l2_error": restored_error,
            "decoded_direction_norm": float(np.sqrt(np.sum(direction * direction, dtype=np.float64))),
            "subspace_residual_energy": residual,
            "pass": True,
            "ey": ey,
            "ei": ei,
        })
    return result


def validate_seed(document: dict[str, Any], capture: dict[str, Any], capture_hash: str, canonical: list[tuple[int, int, int]], shuffled: list[tuple[int, int, int]]) -> dict[str, Any]:
    validate_field_common(document, "seed", True)
    require(document.get("retained_weight") == RETAINED_WEIGHT, "seed retained_weight mismatch")
    require(document.get("steps_per_layer") == STEPS_PER_LAYER, "seed steps_per_layer mismatch")
    require(document.get("layer_count") == LAYER_COUNT, "seed layer_count mismatch")
    exact_array(document.get("layer_checkpoints"), LAYER_CHECKPOINTS, "seed layer checkpoints")
    exact_array(document.get("continuation_horizons"), CONTINUATION_HORIZONS, "seed continuation horizons")
    require(document.get("capture_sha256") == capture_hash, "seed capture hash mismatch")
    require(document.get("basis") == mode_manifest(canonical, shuffled), "seed Fourier basis manifest mismatch")
    canonical_rows = validate_seed_rows(document.get("canonical_layers"), capture["layers"], canonical, "canonical")
    shuffled_rows = validate_seed_rows(document.get("shuffled_layers"), capture["layers"], shuffled, "shuffled")
    return {"canonical": canonical_rows, "shuffled": shuffled_rows, "pass": True}


def validate_metric_row(row: dict[str, Any], label: str) -> None:
    require(row.get("finite") is True, f"{label}.finite failed")
    for key in ("max_abs", "ey_l2", "ei_l2", "epsilon_l2"):
        value = finite_number(row.get(key), f"{label}.{key}")
        require(value >= 0.0, f"{label}.{key} is negative")
    require(float(row["max_abs"]) <= MAX_FIELD_ABS, f"{label}.max_abs exceeds field bound")


def compare_reported_metrics(actual: dict[str, float | bool], reported: dict[str, Any], label: str) -> None:
    for key in ("max_abs", "ey_l2", "ei_l2", "epsilon_l2"):
        require(close(reported.get(key), actual[key], 2e-6), f"{label}.{key} disagrees with raw field")


def validate_raw_field_row(
    row: dict[str, Any],
    label: str,
    basis: str,
    expected_summary: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | bool], np.ndarray, float]:
    validate_metric_row(row, label)
    _, ey = decode_f32(row.get("ey_b64"), VOLUME, f"{label} EY")
    _, ei = decode_f32(row.get("ei_b64"), VOLUME, f"{label} EI")
    modes = CANONICAL_MODES if basis in ("canonical", "zero") else SHUFFLED_MODES
    metrics = field_metrics(ey, ei, modes)
    compare_reported_metrics(metrics, row, label)
    if expected_summary is not None:
        require(row.get("step") == expected_summary.get("step"), f"{label} step disagrees with summary")
        require(row.get("finite") is expected_summary.get("finite"), f"{label} finite disagrees with summary")
        require(close_abs(row.get("t"), expected_summary.get("t"), 1e-6), f"{label} time disagrees with summary")
        compare_reported_metrics(metrics, expected_summary, f"{label} summary agreement")
    direction, residual = decode_unit(ey, ei, modes)
    return ey, ei, metrics, direction, residual


def validate_gpu(document: dict[str, Any], capture_hash: str, capture: dict[str, Any]) -> dict[str, Any]:
    validate_field_common(document, "GPU receipt", False)
    require(document.get("retained_weight") == RETAINED_WEIGHT, "GPU retained_weight mismatch")
    require(document.get("steps_per_layer") == STEPS_PER_LAYER, "GPU steps_per_layer mismatch")
    require(document.get("layer_count") == LAYER_COUNT, "GPU layer_count mismatch")
    exact_array(document.get("layer_checkpoints"), LAYER_CHECKPOINTS, "GPU layer checkpoints")
    exact_array(document.get("continuation_horizons"), CONTINUATION_HORIZONS, "GPU continuation horizons")
    require(document.get("capture_sha256") == capture_hash, "GPU capture hash mismatch")
    require(document.get("finite") is True, "GPU receipt finite flag failed")
    require(document.get("verdict") == "PASS", "GPU receipt verdict is not PASS")

    arms = as_array(document.get("arms"), "GPU arms")
    require(len(arms) == len(ARM_IDS), "GPU arm array shape mismatch")
    arm_results: dict[str, Any] = {}
    h3 = True
    first_blend_pass = True
    zero_byte_zero = True
    maximum_field_abs = 0.0

    for arm_index, arm_id in enumerate(ARM_IDS):
        arm = as_object(arms[arm_index], f"GPU arm {arm_id}")
        basis = ARM_BASIS[arm_id]
        expected_order = REVERSE_ORDER if arm_id == "reverse_canonical" else FORWARD_ORDER
        require(arm.get("id") == arm_id, f"GPU arm {arm_id} id/order mismatch")
        require(arm.get("basis") == basis, f"GPU arm {arm_id} basis mismatch")
        exact_array(arm.get("layer_order"), expected_order, f"GPU arm {arm_id} layer order")

        first = as_object(arm.get("first_blend_contract"), f"GPU arm {arm_id} first blend contract")
        require(first.get("pass") is True, f"GPU arm {arm_id} first blend contract failed")
        first_error = finite_number(first.get("max_abs_error"), f"GPU arm {arm_id} first blend error")
        require(first_error >= 0.0, f"GPU arm {arm_id} first blend error is negative")
        arm_first_pass = first_error <= FIRST_BLEND_ERROR_MAX
        first_blend_pass = first_blend_pass and arm_first_pass
        h3 = h3 and arm_first_pass

        summaries = as_array(arm.get("layer_summaries"), f"GPU arm {arm_id} layer summaries")
        require(len(summaries) == LAYER_COUNT, f"GPU arm {arm_id} layer summary count mismatch")
        summary_by_layer: dict[int, dict[str, Any]] = {}
        summary_rows: list[dict[str, Any]] = []
        for update_index, value in enumerate(summaries):
            row = as_object(value, f"GPU arm {arm_id} summary {update_index}")
            layer_index = expected_order[update_index]
            require(row.get("layer_index") == layer_index, f"GPU arm {arm_id} summary {update_index} layer mismatch")
            require(row.get("update_index") == update_index, f"GPU arm {arm_id} summary {update_index} update index mismatch")
            step = (update_index + 1) * STEPS_PER_LAYER
            require(row.get("step") == step, f"GPU arm {arm_id} summary {update_index} step mismatch")
            require(close_abs(row.get("t"), step * DT, 1e-6), f"GPU arm {arm_id} summary {update_index} time mismatch")
            validate_metric_row(row, f"GPU arm {arm_id} summary {update_index}")
            maximum_field_abs = max(maximum_field_abs, float(row["max_abs"]))
            if arm_id == "zero":
                summary_zero = row["max_abs"] == 0 and row["ey_l2"] == 0 and row["ei_l2"] == 0 and row["epsilon_l2"] == 0
                zero_byte_zero = zero_byte_zero and summary_zero
                h3 = h3 and summary_zero
            summary_by_layer[layer_index] = row
            summary_rows.append({key: row[key] for key in ("layer_index", "update_index", "step", "t", "finite", "max_abs", "ey_l2", "ei_l2", "epsilon_l2")})

        layer_rows = as_array(arm.get("layer_checkpoints"), f"GPU arm {arm_id} layer checkpoints")
        require(len(layer_rows) == len(LAYER_CHECKPOINTS), f"GPU arm {arm_id} layer checkpoint count mismatch")
        checkpoint_results: list[dict[str, Any]] = []
        checkpoint_map = {layer: index for index, layer in enumerate(expected_order)}
        for checkpoint_index, layer_index in enumerate(LAYER_CHECKPOINTS):
            row = as_object(layer_rows[checkpoint_index], f"GPU arm {arm_id} layer checkpoint {layer_index}")
            require(row.get("layer_index") == layer_index, f"GPU arm {arm_id} layer checkpoint {layer_index} layer mismatch")
            update_index = checkpoint_map[layer_index]
            require(row.get("update_index") == update_index, f"GPU arm {arm_id} layer checkpoint {layer_index} update index mismatch")
            step = (update_index + 1) * STEPS_PER_LAYER
            require(row.get("step") == step, f"GPU arm {arm_id} layer checkpoint {layer_index} step mismatch")
            require(close_abs(row.get("t"), step * DT, 1e-6), f"GPU arm {arm_id} layer checkpoint {layer_index} time mismatch")
            summary = summary_by_layer[layer_index]
            ey, ei, metrics, direction, residual = validate_raw_field_row(row, f"GPU arm {arm_id} layer checkpoint {layer_index}", basis, summary)
            maximum_field_abs = max(maximum_field_abs, float(metrics["max_abs"]))
            if arm_id == "zero":
                row_zero = byte_zero(ey) and byte_zero(ei)
                zero_byte_zero = zero_byte_zero and row_zero
                h3 = h3 and row_zero
                decoded: dict[str, float] | None = None
            else:
                source = capture["layers"][layer_index]
                normalized, _ = normalize(source["hidden"], f"capture layer {layer_index}")
                restored = direction * source["hidden_l2_norm"]
                decoded = {
                    "direction_norm": float(np.sqrt(np.sum(direction * direction, dtype=np.float64))),
                    "subspace_residual_energy": residual,
                    "direction_cosine": cosine(direction, normalized),
                    "restored_cosine": cosine(restored, source["hidden"]),
                    "restored_relative_l2_error": relative_l2(restored, source["hidden"]),
                }
                require(all(math.isfinite(float(value)) for value in decoded.values()), f"GPU arm {arm_id} layer checkpoint {layer_index} decoded values are non-finite")
            h3 = h3 and row.get("step") == summary.get("step") and row.get("finite") is summary.get("finite")
            checkpoint_results.append({
                "layer_index": row["layer_index"],
                "update_index": row["update_index"],
                "step": row["step"],
                "t": row["t"],
                "finite": row["finite"],
                "max_abs": float(metrics["max_abs"]),
                "ey_l2": float(metrics["ey_l2"]),
                "ei_l2": float(metrics["ei_l2"]),
                "epsilon_l2": float(metrics["epsilon_l2"]),
                "decoded": decoded,
                "contract_pass": True,
            })

        continuation_rows = as_array(arm.get("continuation_checkpoints"), f"GPU arm {arm_id} continuation checkpoints")
        require(len(continuation_rows) == len(CONTINUATION_HORIZONS), f"GPU arm {arm_id} continuation checkpoint count mismatch")
        continuation_results: list[dict[str, Any]] = []
        continuation_directions: dict[int, np.ndarray] = {}
        for horizon_index, horizon in enumerate(CONTINUATION_HORIZONS):
            row = as_object(continuation_rows[horizon_index], f"GPU arm {arm_id} continuation {horizon}")
            require(row.get("horizon") == horizon, f"GPU arm {arm_id} continuation {horizon} horizon mismatch")
            step = LAYER_COUNT * STEPS_PER_LAYER + horizon
            require(row.get("step") == step, f"GPU arm {arm_id} continuation {horizon} step mismatch")
            require(close_abs(row.get("t"), step * DT, 1e-6), f"GPU arm {arm_id} continuation {horizon} time mismatch")
            ey, ei, metrics, direction, residual = validate_raw_field_row(row, f"GPU arm {arm_id} continuation {horizon}", basis)
            maximum_field_abs = max(maximum_field_abs, float(metrics["max_abs"]))
            continuation_directions[horizon] = direction
            if arm_id == "zero":
                row_zero = byte_zero(ey) and byte_zero(ei)
                zero_byte_zero = zero_byte_zero and row_zero
                h3 = h3 and row_zero
                decoded = None
            else:
                decoded = {
                    "direction_norm": float(np.sqrt(np.sum(direction * direction, dtype=np.float64))),
                    "subspace_residual_energy": residual,
                }
                require(all(math.isfinite(float(value)) for value in decoded.values()), f"GPU arm {arm_id} continuation {horizon} decoded values are non-finite")
            continuation_results.append({
                "horizon": row["horizon"],
                "step": row["step"],
                "t": row["t"],
                "finite": row["finite"],
                "max_abs": float(metrics["max_abs"]),
                "ey_l2": float(metrics["ey_l2"]),
                "ei_l2": float(metrics["ei_l2"]),
                "epsilon_l2": float(metrics["epsilon_l2"]),
                "decoded": decoded,
                "contract_pass": True,
            })

        arm_results[arm_id] = {
            "id": arm_id,
            "basis": basis,
            "layer_order": list(expected_order),
            "first_blend_contract": {
                "pass": first["pass"],
                "max_abs_error": first_error,
                "contract_pass": arm_first_pass,
            },
            "layer_summaries": summary_rows,
            "layer_checkpoints": checkpoint_results,
            "continuation_checkpoints": continuation_results,
            "continuation_directions": continuation_directions,
        }

    require(maximum_field_abs <= MAX_FIELD_ABS, "GPU maximum field bound failed")
    require(zero_byte_zero, "GPU zero control is not byte-zero")
    h3 = h3 and maximum_field_abs <= MAX_FIELD_ABS and zero_byte_zero
    require(first_blend_pass, "GPU first-blend contract failed")
    require(h3, "GPU H3 transport contract failed")
    return {
        "pass_h2_first_blend": first_blend_pass,
        "pass_h3_transport": h3,
        "max_abs": maximum_field_abs,
        "bound": MAX_FIELD_ABS,
        "zero_byte_zero": zero_byte_zero,
        "arms": arm_results,
    }


def baseline(capture_layers: list[dict[str, Any]], order: list[int], decoded_terminal: np.ndarray) -> dict[str, Any]:
    state = np.zeros(DIMENSION, dtype=np.float64)
    rows: list[dict[str, Any]] = []
    for update_index, layer_index in enumerate(order):
        direction, _ = normalize(capture_layers[layer_index]["hidden"], f"capture layer {layer_index}")
        state = RETAINED_WEIGHT * state + INPUT_WEIGHT * direction
        rows.append({
            "layer_index": layer_index,
            "update_index": update_index,
            "norm": float(np.sqrt(np.sum(state * state, dtype=np.float64))),
            "direction_cosine_to_input": cosine(state, direction),
        })
    return {
        "layer_rows": rows,
        "terminal_norm": float(np.sqrt(np.sum(state * state, dtype=np.float64))),
        "terminal_decoded_cosine": cosine(state, decoded_terminal),
    }


def compare_float(actual: Any, expected: float, label: str, tolerance: float = 2e-6) -> None:
    require(close(actual, expected, tolerance), f"{label} mismatch")


def compare_cpu_receipt_rows(receipt_rows: Any, expected_rows: list[dict[str, Any]], basis: str) -> None:
    rows = as_array(receipt_rows, f"receipt CPU {basis} rows")
    require(len(rows) == LAYER_COUNT, f"receipt CPU {basis} row count mismatch")
    fields = ("hidden_l2_norm", "direction_cosine", "restored_cosine", "restored_relative_l2_error", "decoded_direction_norm", "subspace_residual_energy")
    for index, expected in enumerate(expected_rows):
        row = as_object(rows[index], f"receipt CPU {basis} row {index}")
        require(row.get("layer_index") == expected["layer_index"], f"receipt CPU {basis} layer index mismatch")
        for field in fields:
            compare_float(row.get(field), float(expected[field]), f"receipt CPU {basis} row {index}.{field}")
        require(row.get("pass") is True, f"receipt CPU {basis} row {index} pass mismatch")


def compare_core_rows(
    actual_rows: Any,
    expected_rows: list[dict[str, Any]],
    label: str,
    includes_layer: bool,
    includes_update: bool,
    require_contract_pass: bool,
) -> None:
    rows = as_array(actual_rows, label)
    require(len(rows) == len(expected_rows), f"{label} count mismatch")
    numeric_fields = ("t", "max_abs", "ey_l2", "ei_l2", "epsilon_l2")
    fields: tuple[str, ...] = ("layer_index",) if includes_layer else ()
    if includes_update:
        fields += ("update_index",)
    for index, expected in enumerate(expected_rows):
        row = as_object(rows[index], f"{label}[{index}]")
        for field in fields:
            require(row.get(field) == expected[field], f"{label}[{index}].{field} mismatch")
        require(row.get("step") == expected["step"], f"{label}[{index}].step mismatch")
        require(row.get("finite") is expected["finite"], f"{label}[{index}].finite mismatch")
        for field in numeric_fields:
            compare_float(row.get(field), float(expected[field]), f"{label}[{index}].{field}")
        if require_contract_pass:
            require(row.get("contract_pass") is True, f"{label}[{index}].contract_pass mismatch")


def compare_decoded(actual: Any, expected: dict[str, float] | None, label: str) -> None:
    if expected is None:
        require(actual is None, f"{label} must be null")
        return
    row = as_object(actual, label)
    for key, value in expected.items():
        compare_float(row.get(key), value, f"{label}.{key}")


def validate_reduced_receipt(
    receipt: dict[str, Any],
    artifact_hashes: dict[str, str],
    capture: dict[str, Any],
    seed_analysis: dict[str, Any],
    gpu_analysis: dict[str, Any],
    baselines: dict[str, Any],
    h4: dict[str, float],
) -> None:
    require(receipt.get("protocol") == PROTOCOL, "reduced receipt protocol mismatch")
    require(receipt.get("version") == VERSION, "reduced receipt version mismatch")
    artifacts = as_object(receipt.get("artifacts"), "reduced receipt artifacts")
    expected_paths = {
        "capture": "CassiFI/artifacts/native/all-layer-hidden-state-capture.json",
        "seed": "CassiCosmos/_diag/cassi_qwen_all_layer_iir_seed.json",
        "gpu": "CassiCosmos/_diag/cassi_qwen_all_layer_iir_gpu.json",
    }
    for key in ("capture", "seed", "gpu"):
        row = as_object(artifacts.get(key), f"reduced receipt artifact {key}")
        require(row.get("path") == expected_paths[key], f"reduced receipt artifact {key} path mismatch")
        require(row.get("sha256") == artifact_hashes[key], f"reduced receipt artifact {key} SHA-256 mismatch")

    config = as_object(receipt.get("config"), "reduced receipt config")
    expected_config: dict[str, Any] = {
        "grid_n": N,
        "dimension": DIMENSION,
        "mode_count": MODE_COUNT,
        "phi": PHI,
        "amplitude": AMPLITUDE,
        "dt": DT,
        "retained_weight": RETAINED_WEIGHT,
        "steps_per_layer": STEPS_PER_LAYER,
        "layer_count": LAYER_COUNT,
        "layer_checkpoints": LAYER_CHECKPOINTS,
        "continuation_horizons": CONTINUATION_HORIZONS,
        "layout": LAYOUT,
        "dtype": DTYPE,
    }
    for key, expected in expected_config.items():
        if isinstance(expected, list):
            exact_array(config.get(key), expected, f"reduced receipt config {key}")
        elif isinstance(expected, float):
            require(close(config.get(key), expected, 1e-13), f"reduced receipt config {key} mismatch")
        else:
            require(config.get(key) == expected, f"reduced receipt config {key} mismatch")

    capture_parity = as_object(receipt.get("capture_parity"), "reduced receipt capture parity")
    for key, expected in capture["h1"].items():
        if isinstance(expected, bool):
            require(capture_parity.get(key) is expected, f"reduced receipt capture parity {key} mismatch")
        elif isinstance(expected, int):
            require(capture_parity.get(key) == expected, f"reduced receipt capture parity {key} mismatch")
        else:
            compare_float(capture_parity.get(key), float(expected), f"reduced receipt capture parity {key}", 1e-12)

    cpu = as_object(receipt.get("cpu_codec_contract"), "reduced receipt CPU contract")
    require(cpu.get("pass") is seed_analysis["pass"], "reduced receipt CPU pass mismatch")
    thresholds = as_object(cpu.get("thresholds"), "reduced receipt CPU thresholds")
    compare_float(thresholds.get("cosine_min"), COSINE_MIN, "reduced receipt cosine threshold", 1e-13)
    compare_float(thresholds.get("relative_l2_max"), RELATIVE_L2_MAX, "reduced receipt relative L2 threshold", 1e-13)
    rows = as_object(cpu.get("rows"), "reduced receipt CPU rows")
    compare_cpu_receipt_rows(rows.get("canonical"), seed_analysis["canonical"], "canonical")
    compare_cpu_receipt_rows(rows.get("shuffled"), seed_analysis["shuffled"], "shuffled")

    gpu = as_object(receipt.get("gpu_contract"), "reduced receipt GPU contract")
    require(gpu.get("first_blend_pass") is gpu_analysis["pass_h2_first_blend"], "reduced receipt first-blend pass mismatch")
    require(gpu.get("h3_transport_pass") is gpu_analysis["pass_h3_transport"], "reduced receipt H3 pass mismatch")
    compare_float(gpu.get("max_abs"), gpu_analysis["max_abs"], "reduced receipt GPU max_abs")
    compare_float(gpu.get("bound"), MAX_FIELD_ABS, "reduced receipt GPU bound", 1e-13)
    require(gpu.get("zero_byte_zero") is gpu_analysis["zero_byte_zero"], "reduced receipt zero control mismatch")
    receipt_arms = as_object(gpu.get("arms"), "reduced receipt GPU arms")
    for arm_id in ARM_IDS:
        expected_arm = gpu_analysis["arms"][arm_id]
        arm = as_object(receipt_arms.get(arm_id), f"reduced receipt GPU arm {arm_id}")
        require(arm.get("id") == arm_id, f"reduced receipt GPU arm {arm_id} id mismatch")
        require(arm.get("basis") == expected_arm["basis"], f"reduced receipt GPU arm {arm_id} basis mismatch")
        exact_array(arm.get("layer_order"), expected_arm["layer_order"], f"reduced receipt GPU arm {arm_id} layer order")
        first = as_object(arm.get("first_blend_contract"), f"reduced receipt GPU arm {arm_id} first blend")
        require(first.get("pass") is True, f"reduced receipt GPU arm {arm_id} first blend pass mismatch")
        require(first.get("contract_pass") is expected_arm["first_blend_contract"]["contract_pass"], f"reduced receipt GPU arm {arm_id} first blend contract mismatch")
        compare_float(first.get("max_abs_error"), expected_arm["first_blend_contract"]["max_abs_error"], f"reduced receipt GPU arm {arm_id} first blend error")
        compare_core_rows(
            arm.get("layer_summaries"),
            expected_arm["layer_summaries"],
            f"reduced receipt GPU arm {arm_id} summaries",
            True,
            True,
            False,
        )
        compare_core_rows(
            arm.get("layer_checkpoints"),
            expected_arm["layer_checkpoints"],
            f"reduced receipt GPU arm {arm_id} layer checkpoints",
            True,
            True,
            True,
        )
        receipt_checkpoints = as_array(arm.get("layer_checkpoints"), f"reduced receipt GPU arm {arm_id} layer checkpoints")
        for index, expected in enumerate(expected_arm["layer_checkpoints"]):
            compare_decoded(as_object(receipt_checkpoints[index], "receipt checkpoint").get("decoded"), expected["decoded"], f"reduced receipt GPU arm {arm_id} checkpoint {index} decoded")
        compare_core_rows(
            arm.get("continuation_checkpoints"),
            expected_arm["continuation_checkpoints"],
            f"reduced receipt GPU arm {arm_id} continuations",
            False,
            False,
            True,
        )
        receipt_continuations = as_array(arm.get("continuation_checkpoints"), f"reduced receipt GPU arm {arm_id} continuations")
        for index, expected in enumerate(expected_arm["continuation_checkpoints"]):
            compare_decoded(as_object(receipt_continuations[index], "receipt continuation").get("decoded"), expected["decoded"], f"reduced receipt GPU arm {arm_id} continuation {index} decoded")

    baseline_receipt = as_object(receipt.get("ordinary_cpu_iir_direction_baseline"), "reduced receipt CPU baseline")
    require(baseline_receipt.get("retained_weight") == RETAINED_WEIGHT, "reduced receipt baseline retained weight mismatch")
    for arm_name in ("forward", "reverse"):
        expected_baseline = baselines[arm_name]
        actual_baseline = as_object(baseline_receipt.get(arm_name), f"reduced receipt baseline {arm_name}")
        rows_actual = as_array(actual_baseline.get("layer_rows"), f"reduced receipt baseline {arm_name} rows")
        require(len(rows_actual) == LAYER_COUNT, f"reduced receipt baseline {arm_name} row count mismatch")
        for index, expected_row in enumerate(expected_baseline["layer_rows"]):
            row = as_object(rows_actual[index], f"reduced receipt baseline {arm_name} row {index}")
            require(row.get("layer_index") == expected_row["layer_index"], f"reduced receipt baseline {arm_name} layer mismatch")
            require(row.get("update_index") == expected_row["update_index"], f"reduced receipt baseline {arm_name} update mismatch")
            compare_float(row.get("norm"), expected_row["norm"], f"reduced receipt baseline {arm_name} norm {index}")
            compare_float(row.get("direction_cosine_to_input"), expected_row["direction_cosine_to_input"], f"reduced receipt baseline {arm_name} cosine {index}")
        compare_float(actual_baseline.get("terminal_norm"), expected_baseline["terminal_norm"], f"reduced receipt baseline {arm_name} terminal norm")
        compare_float(actual_baseline.get("terminal_decoded_cosine"), expected_baseline["terminal_decoded_cosine"], f"reduced receipt baseline {arm_name} decoded cosine")

    h4_receipt = as_object(receipt.get("h4_temporal_order"), "reduced receipt H4")
    compare_float(h4_receipt.get("cosine"), h4["cosine"], "reduced receipt H4 cosine")
    compare_float(h4_receipt.get("forward_reverse_cosine"), h4["cosine"], "reduced receipt H4 forward/reverse cosine")
    compare_float(h4_receipt.get("one_minus_cosine"), h4["cosine_gap"], "reduced receipt H4 cosine gap")
    compare_float(h4_receipt.get("threshold"), H4_THRESHOLD, "reduced receipt H4 threshold", 1e-13)
    require(h4_receipt.get("verdict") == ("SUPPORTS" if h4["cosine_gap"] >= H4_THRESHOLD else "NULL"), "reduced receipt H4 verdict mismatch")

    gates = as_object(receipt.get("gates"), "reduced receipt gates")
    require(gates.get("H1") is True, "reduced receipt H1 gate mismatch")
    require(gates.get("H2") is True, "reduced receipt H2 gate mismatch")
    require(gates.get("H3") is True, "reduced receipt H3 gate mismatch")
    require(gates.get("H4") == h4_receipt["verdict"], "reduced receipt H4 gate mismatch")
    require(receipt.get("verdict") == "PASS", "reduced receipt verdict is not PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--gpu", type=Path, default=DEFAULT_GPU)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


# These are computed once, without loading any artifact or production module.
CANONICAL_MODES = canonical_modes()
SHUFFLED_MODES = shuffled_modes(CANONICAL_MODES)


def main() -> int:
    args = parse_args()
    try:
        capture_raw, capture_document = load_json(args.capture.resolve())
        seed_raw, seed_document = load_json(args.seed.resolve())
        gpu_raw, gpu_document = load_json(args.gpu.resolve())
        _, receipt_document = load_json(args.receipt.resolve())

        capture = validate_capture(capture_document, capture_raw)
        seed_analysis = validate_seed(seed_document, capture, sha256_bytes(capture_raw), CANONICAL_MODES, SHUFFLED_MODES)
        gpu_analysis = validate_gpu(gpu_document, sha256_bytes(capture_raw), capture)

        forward_direction = gpu_analysis["arms"]["forward_canonical"]["continuation_directions"][0]
        reverse_direction = gpu_analysis["arms"]["reverse_canonical"]["continuation_directions"][0]
        h4_cosine = cosine(forward_direction, reverse_direction)
        h4 = {"cosine": h4_cosine, "cosine_gap": 1.0 - h4_cosine}
        baselines = {
            "forward": baseline(capture["layers"], FORWARD_ORDER, forward_direction),
            "reverse": baseline(capture["layers"], REVERSE_ORDER, reverse_direction),
        }
        artifact_hashes = {
            "capture": sha256_bytes(capture_raw),
            "seed": sha256_bytes(seed_raw),
            "gpu": sha256_bytes(gpu_raw),
        }
        validate_reduced_receipt(receipt_document, artifact_hashes, capture, seed_analysis, gpu_analysis, baselines, h4)

        print("[H1] PASS — full capture shape, hashes, norms, logits, top-16, and parity")
        print("[H2] PASS — canonical/shuffled Fourier round trips, first blends, and zero control")
        print("[H3] PASS — all GPU summaries, raw checkpoints, continuations, clocks, metrics, and bounds")
        print(f"[H4] {('SUPPORTS' if h4['cosine_gap'] >= H4_THRESHOLD else 'NULL')} — forward/reverse cosine gap {h4['cosine_gap']:.9g}")
        print("[ARTIFACTS] PASS — SHA-256 linkage and reduced Node receipt consistency")
        print("ALL CHECKS PASSED")
        return 0
    except (VerificationError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"VERIFICATION FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
