"""Independent NumPy verifier for the CassiQwen L16 hidden-state observatory."""

from __future__ import annotations

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

DIAG = WORKSPACE_ROOT / "CassiCosmos" / "_diag"
CAPTURE_PATH = ARTIFACT_DIR / "native" / "hidden-state-capture.json"
SEED_PATH = DIAG / "cassi_qwen_hidden_state_field_seed.json"
GPU_PATH = DIAG / "cassi_qwen_hidden_state_field_gpu.json"
RECEIPT_PATH = ARTIFACT_DIR / "native" / "hidden-state-field-observatory.json"

PROTOCOL = "CassiQwen L16 hidden-state field observatory"
VERSION = 1
N = 32
VOLUME = N**3
DIMENSION = 5120
MODE_COUNT = DIMENSION // 2
PHI = 1.618033988749895
DT = 0.005
HORIZONS = [0, 1, 4, 16, 64, 256, 1024, 2048]
LAYOUT = "x + N*(y + N*z)"
DTYPE = "float32-le"
CASE_IDS = ["hidden_canonical", "hidden_shuffled", "zero"]
CASE_BASIS = {"hidden_canonical": "canonical", "hidden_shuffled": "shuffled", "zero": "zero"}
SHUFFLE_SEED = 0x51F71E1D
TOP_K = 16


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    parsed = json.loads(raw)
    require(isinstance(parsed, dict), f"{path.name}: root is not an object")
    return raw, parsed


def b64_f32(text: str, count: int, label: str) -> np.ndarray:
    raw = base64.b64decode(text, validate=True)
    require(len(raw) == count * 4, f"{label}: byte length mismatch")
    result = np.frombuffer(raw, dtype="<f4").copy()
    require(result.size == count and np.isfinite(result).all(), f"{label}: wrong shape or non-finite values")
    return result


def sha256_b64(text: str, expected: str, label: str) -> bytes:
    raw = base64.b64decode(text, validate=True)
    require(base64.b64encode(raw).decode("ascii") == text, f"{label}: non-canonical base64")
    require(hashlib.sha256(raw).hexdigest() == expected, f"{label}: SHA-256 mismatch")
    return raw


def flat_index(x: int, y: int, z: int) -> int:
    return x + N * (y + N * z)


def wrapped(index: int) -> int:
    return index if index <= N // 2 else index - N


def canonical_modes() -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int, int, int, int, int, int]] = []
    for z in range(N):
        for y in range(N):
            for x in range(N):
                nx, ny, nz = (-x) % N, (-y) % N, (-z) % N
                index, negative = flat_index(x, y, z), flat_index(nx, ny, nz)
                if index == negative:
                    continue
                kx, ky, kz = wrapped(x), wrapped(y), wrapped(z)
                candidates.append((kx * kx + ky * ky + kz * kz, kz, ky, kx, index, negative, x, y * N + z * N * N))
    candidates.sort(key=lambda row: row[:5])
    seen: set[int] = set()
    selected: list[tuple[int, int, int]] = []
    for _, _, _, _, index, negative, x, yz in candidates:
        if index in seen:
            continue
        seen.add(index)
        seen.add(negative)
        y = (yz // N) % N
        z = yz // (N * N)
        selected.append((x, y, z))
    require(len(selected) >= MODE_COUNT, "Fourier mode capacity is insufficient")
    return selected[:MODE_COUNT]


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


def normalize(values: np.ndarray) -> tuple[np.ndarray, float]:
    source = np.asarray(values, dtype=np.float64)
    norm = float(np.linalg.norm(source))
    require(math.isfinite(norm) and norm > 0, "hidden norm is invalid")
    return source / norm, norm


def decode(ey: np.ndarray, ei: np.ndarray, modes: list[tuple[int, int, int]]) -> tuple[np.ndarray, dict[str, float]]:
    epsilon = ey.astype(np.float64) - PHI * ei.astype(np.float64)
    volume = epsilon.reshape((N, N, N), order="F")
    spectrum = np.fft.fftn(volume)
    scale = math.sqrt(VOLUME / 2.0)
    direction = np.empty(DIMENSION, dtype=np.float64)
    selected = np.zeros((N, N, N), dtype=bool)
    for pair, (x, y, z) in enumerate(modes):
        value = spectrum[x, y, z]
        direction[2 * pair] = value.real / scale
        direction[2 * pair + 1] = -value.imag / scale
        selected[x, y, z] = True
        selected[(-x) % N, (-y) % N, (-z) % N] = True
    energy = np.abs(spectrum) ** 2
    total = float(energy.sum())
    residual = 0.0 if total == 0.0 else float(energy[~selected].sum() / total)
    return direction, {
        "epsilon_l2": float(np.linalg.norm(epsilon)),
        "subspace_residual_energy": residual,
        "max_abs": float(max(np.max(np.abs(ey)), np.max(np.abs(ei)))),
        "ey_l2": float(np.linalg.norm(ey.astype(np.float64))),
        "ei_l2": float(np.linalg.norm(ei.astype(np.float64))),
    }


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return 0.0 if denom == 0 else float(np.dot(left, right) / denom)


def relative_l2(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(right))
    diff = float(np.linalg.norm(left - right))
    return 0.0 if denom == 0 and diff == 0 else diff / denom


def close(actual: float, expected: float, tolerance: float = 2e-6) -> bool:
    return math.isfinite(actual) and abs(actual - expected) <= tolerance * max(1.0, abs(actual), abs(expected))


def expected_top(logits: np.ndarray) -> list[int]:
    token_ids = np.arange(logits.size)
    order = np.lexsort((token_ids, -logits.astype(np.float64)))[:TOP_K]
    return [int(value) for value in order]


def validate_capture(capture: dict[str, Any]) -> tuple[np.ndarray, float]:
    require(capture.get("protocol") == PROTOCOL and capture.get("version") == VERSION, "capture protocol/version mismatch")
    require(capture.get("verdict") == "PASS", "capture verdict is not PASS")
    model, runtime, hook, prompt = capture["model"], capture["runtime"], capture["hook"], capture["prompt"]
    require(model["hidden_dimension"] == DIMENSION and model["sha256"] == "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169", "capture model mismatch")
    require(runtime["llama_version"] == "0.1.1-dev" and runtime["requested_gpu_layers"] == 99, "capture runtime mismatch")
    require(runtime["context_size"] == 512 and runtime["batch_size"] == 512, "capture context mismatch")
    require(hook["kind"] == "layer_input_residual" and hook["layer_rule"] == "floor(n_layer / 2)", "capture hook mismatch")
    require(hook["layer_index"] == model["layer_count"] // 2 and hook["token_row"] == prompt["final_token_index"], "capture hook location mismatch")
    require(hook["setter_export"].find("llama_set_embeddings_layer_inp") >= 0 and hook["getter_export"].find("llama_get_embeddings_layer_inp") >= 0, "capture WIP export mismatch")
    require(prompt["tokenization"] == {"add_special": True, "parse_special": True}, "capture tokenization mismatch")
    require(prompt["final_token_index"] == prompt["token_count"] - 1 and prompt["final_token_id"] == prompt["token_ids"][-1], "capture final token mismatch")

    hidden_raw = sha256_b64(capture["hidden_state_b64"], capture["hidden_state_sha256"], "hidden")
    require(len(hidden_raw) == DIMENSION * 4, "hidden raw size mismatch")
    hidden = b64_f32(capture["hidden_state_b64"], DIMENSION, "hidden")
    direction, norm = normalize(hidden)
    require(close(norm, float(capture["hidden_l2_norm"]), 1e-12), "hidden norm mismatch")

    logit_arrays = []
    top_ids = []
    for name in ("capture_off", "capture_on"):
        arm = capture[name]
        raw = sha256_b64(arm["logits_b64"], arm["logits_sha256"], name)
        require(len(raw) == model["vocabulary_size"] * 4, f"{name} logit size mismatch")
        logits = b64_f32(arm["logits_b64"], model["vocabulary_size"], name)
        ids = expected_top(logits)
        require(arm["argmax_token_id"] == ids[0], f"{name} argmax mismatch")
        require([row["token_id"] for row in arm["top16"]] == ids, f"{name} top16 token mismatch")
        logit_arrays.append(logits)
        top_ids.append(ids)
    delta = float(np.max(np.abs(logit_arrays[0].astype(np.float64) - logit_arrays[1].astype(np.float64))))
    parity = capture["parity"]
    require(close(delta, float(parity["max_abs_logit_difference"]), 1e-12), "capture delta mismatch")
    require(logit_arrays[0].argmax() == logit_arrays[1].argmax() and top_ids[0] == top_ids[1] and delta <= 1e-6, "H1 parity failed")
    require(parity["pass"] is True, "capture parity metadata failed")
    return hidden.astype(np.float64), norm


def validate_common(document: dict[str, Any], label: str, amplitude: bool) -> None:
    require(document.get("protocol") == PROTOCOL and document.get("version") == VERSION, f"{label} protocol/version mismatch")
    require(document.get("grid_n") == N and document.get("dimension") == DIMENSION, f"{label} shape mismatch")
    require(close(float(document.get("phi")), PHI, 1e-13) and close(float(document.get("dt")), DT, 1e-13), f"{label} phi/dt mismatch")
    require(document.get("layout") == LAYOUT and document.get("dtype") == DTYPE and document.get("horizons") == HORIZONS, f"{label} layout/horizons mismatch")
    if amplitude:
        require(close(float(document.get("amplitude")), 1.0, 1e-13), f"{label} amplitude mismatch")


def case_map(document: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    cases = document.get("cases")
    require(isinstance(cases, list) and len(cases) == len(CASE_IDS), f"{label} case count mismatch")
    result = {case["id"]: case for case in cases}
    require(set(result) == set(CASE_IDS), f"{label} case ids mismatch")
    for case_id, case in result.items():
        require(case["basis"] == CASE_BASIS[case_id], f"{label} basis mismatch for {case_id}")
    return result


def main() -> None:
    capture_raw, capture = load_json(CAPTURE_PATH)
    seed_raw, seed = load_json(SEED_PATH)
    gpu_raw, gpu = load_json(GPU_PATH)
    _, receipt = load_json(RECEIPT_PATH)
    hidden, norm = validate_capture(capture)
    direction, _ = normalize(hidden)
    canonical = canonical_modes()
    shuffled = shuffled_modes(canonical)
    validate_common(seed, "seed", True)
    require(seed["capture_sha256"] == hashlib.sha256(capture_raw).hexdigest(), "seed capture hash mismatch")
    require(seed["hidden_state_sha256"] == capture["hidden_state_sha256"] and close(float(seed["hidden_l2_norm"]), norm, 1e-12), "seed hidden metadata mismatch")
    require(seed["basis"]["canonical"]["modes"] == [list(mode) for mode in canonical], "seed canonical modes mismatch")
    require(seed["basis"]["shuffled"]["modes"] == [list(mode) for mode in shuffled], "seed shuffled modes mismatch")
    seed_cases = case_map(seed, "seed")
    prepared: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for case_id, case in seed_cases.items():
        signal = b64_f32(case["signal_b64"], VOLUME, f"seed {case_id} signal")
        ey = b64_f32(case["ey_b64"], VOLUME, f"seed {case_id} EY")
        ei = b64_f32(case["ei_b64"], VOLUME, f"seed {case_id} EI")
        prepared[case_id] = (ey, ei)
        if case_id == "zero":
            require(not signal.tobytes().strip(b"\0") and not ey.tobytes().strip(b"\0") and not ei.tobytes().strip(b"\0"), "seed zero not byte-zero")
            continue
        modes = canonical if case["basis"] == "canonical" else shuffled
        decoded, _ = decode(ey, ei, modes)
        restored = decoded * norm
        require(cosine(restored, hidden) >= 0.999999 and relative_l2(restored, hidden) <= 2e-6, f"seed {case_id} C1 failed")
        require(np.linalg.norm((ey.astype(np.float64) - PHI * ei.astype(np.float64)) - signal.astype(np.float64)) <= 2e-6, f"seed {case_id} split mismatch")

    validate_common(gpu, "GPU", False)
    require(gpu.get("finite") is True and gpu.get("verdict") == "PASS", "GPU receipt is not PASS")
    gpu_cases = case_map(gpu, "GPU")
    maximum = 0.0
    zero_ok = True
    terminal: dict[str, dict[str, float]] = {}
    for case_id, case in gpu_cases.items():
        checkpoints = case.get("checkpoints")
        require(isinstance(checkpoints, list) and len(checkpoints) == len(HORIZONS), f"GPU {case_id} checkpoint count mismatch")
        modes = canonical if case["basis"] in {"canonical", "zero"} else shuffled
        for step, checkpoint in zip(HORIZONS, checkpoints, strict=True):
            require(checkpoint["step"] == step and abs(float(checkpoint["t"]) - step * DT) <= 1e-6 and checkpoint["finite"] is True, f"GPU {case_id}/{step} timing/finite mismatch")
            ey = b64_f32(checkpoint["ey_b64"], VOLUME, f"GPU {case_id}/{step} EY")
            ei = b64_f32(checkpoint["ei_b64"], VOLUME, f"GPU {case_id}/{step} EI")
            decoded, metrics = decode(ey, ei, modes)
            maximum = max(maximum, metrics["max_abs"])
            require(metrics["max_abs"] <= 10.0, f"GPU {case_id}/{step} bound failed")
            for key in ("max_abs", "ey_l2", "ei_l2", "epsilon_l2"):
                require(close(metrics[key], float(checkpoint[key])), f"GPU {case_id}/{step} {key} mismatch")
            if case_id == "zero":
                zero_ok = zero_ok and not ey.tobytes().strip(b"\0") and not ei.tobytes().strip(b"\0")
            else:
                restored = decoded * norm
                if step == 0:
                    prep_ey, prep_ei = prepared[case_id]
                    require(ey.tobytes() == prep_ey.tobytes() and ei.tobytes() == prep_ei.tobytes(), f"GPU {case_id} seed bytes mismatch")
                    require(cosine(restored, hidden) >= 0.999999 and relative_l2(restored, hidden) <= 2e-6, f"GPU {case_id} H2 failed")
                if step == HORIZONS[-1]:
                    terminal[case_id] = {"direction_cosine": cosine(decoded, direction), "restored_cosine": cosine(restored, hidden), "restored_relative_l2_error": relative_l2(restored, hidden)}
    require(zero_ok, "GPU zero control is not byte-zero")
    require(receipt.get("verdict") == "PASS", "reduced receipt is not PASS")
    require(receipt["artifacts"]["capture"]["sha256"] == hashlib.sha256(capture_raw).hexdigest(), "capture hash mismatch")
    require(receipt["artifacts"]["seed"]["sha256"] == hashlib.sha256(seed_raw).hexdigest(), "seed hash mismatch")
    require(receipt["artifacts"]["gpu"]["sha256"] == hashlib.sha256(gpu_raw).hexdigest(), "GPU hash mismatch")
    require(receipt["gates"] == {"H1": True, "H2": True, "H3": True}, "reduced gate mismatch")
    print(json.dumps({"verdict": "PASS", "max_abs": maximum, "terminal": terminal, "capture_sha256": hashlib.sha256(capture_raw).hexdigest(), "gpu_sha256": hashlib.sha256(gpu_raw).hexdigest()}, indent=2))
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
