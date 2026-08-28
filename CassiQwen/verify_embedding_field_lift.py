"""Independent NumPy gate for the CassiQwen L15 embedding-field receipt."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
SEED_PATH = HERE.parent / "CassiCosmos" / "_diag" / "cassi_qwen_embedding_field_seed.json"
GPU_PATH = HERE.parent / "CassiCosmos" / "_diag" / "cassi_qwen_embedding_field_gpu.json"
RECEIPT_PATH = HERE / "embedding-field-lift.json"

PROTOCOL = "CassiQwen L15 embedding-to-field lift"
VERSION = 1
N = 32
VOLUME = N**3
DIMENSION = 1536
MODE_COUNT = DIMENSION // 2
PHI = 1.618033988749895
AMPLITUDE = 1.0
DT = 0.005
LAYOUT = "x + N*(y + N*z)"
DTYPE = "float32-le"
HORIZONS = [0, 1, 4, 16, 64, 256, 1024, 2048]
CANONICAL_IDS = ["anchor", "near", "orthogonal", "opposite"]
NONZERO_IDS = CANONICAL_IDS + ["anchor_shuffled", "near_shuffled"]
CASE_IDS = NONZERO_IDS + ["zero"]
CASE_BASIS = {
    "anchor": "canonical",
    "near": "canonical",
    "orthogonal": "canonical",
    "opposite": "canonical",
    "anchor_shuffled": "shuffled",
    "near_shuffled": "shuffled",
    "zero": "zero",
}
SHUFFLE_SEED = 0x51F71E1D


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    parsed = json.loads(raw)
    require(isinstance(parsed, dict), f"{path.name}: root must be an object")
    return raw, parsed


def decode_f32(text: str, count: int) -> np.ndarray:
    raw = base64.b64decode(text, validate=True)
    require(len(raw) == count * 4, f"float32 payload has {len(raw)} bytes, expected {count * 4}")
    values = np.frombuffer(raw, dtype="<f4").copy()
    require(values.size == count and np.isfinite(values).all(), "float32 payload is wrong-sized or non-finite")
    return values


def flat_index(x: int, y: int, z: int) -> int:
    return x + N * (y + N * z)


def wrapped(index: int) -> int:
    return index if index <= N // 2 else index - N


def mode_record(x: int, y: int, z: int) -> tuple[int, int, int, int, int, int, int, int]:
    nx, ny, nz = (-x) % N, (-y) % N, (-z) % N
    kx, ky, kz = wrapped(x), wrapped(y), wrapped(z)
    return (kx * kx + ky * ky + kz * kz, kz, ky, kx, flat_index(x, y, z), flat_index(nx, ny, nz), x, y, z)


def canonical_modes() -> list[tuple[int, int, int]]:
    candidates = []
    for z in range(N):
        for y in range(N):
            for x in range(N):
                record = mode_record(x, y, z)
                if record[4] != record[5]:
                    candidates.append(record)
    candidates.sort(key=lambda item: item[:5])
    seen: set[int] = set()
    modes: list[tuple[int, int, int]] = []
    for record in candidates:
        positive, negative = record[4], record[5]
        if positive in seen:
            continue
        seen.add(positive)
        seen.add(negative)
        modes.append((record[6], record[7], record[8]))
    return modes[:MODE_COUNT]


def xorshift32(state: int) -> int:
    state &= 0xFFFFFFFF
    state ^= (state << 13) & 0xFFFFFFFF
    state &= 0xFFFFFFFF
    state ^= state >> 17
    state &= 0xFFFFFFFF
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def shuffled_modes(source: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    result = list(source)
    state = SHUFFLE_SEED
    for index in range(len(result) - 1, 0, -1):
        state = xorshift32(state)
        swap_index = state % (index + 1)
        result[index], result[swap_index] = result[swap_index], result[index]
    return result


def normalize(vector: np.ndarray) -> np.ndarray:
    result = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(result)
    require(np.isfinite(norm) and norm > 0.0, "embedding norm must be finite and nonzero")
    return result / norm


def decode_embedding(ey: np.ndarray, ei: np.ndarray, modes: list[tuple[int, int, int]]) -> tuple[np.ndarray, float, float]:
    epsilon = ey.astype(np.float64) - PHI * ei.astype(np.float64)
    volume = epsilon.reshape((N, N, N), order="F")
    spectrum = np.fft.fftn(volume)
    scale = AMPLITUDE * math.sqrt(VOLUME / 2.0)
    decoded = np.empty(DIMENSION, dtype=np.float64)
    selected = np.zeros((N, N, N), dtype=bool)
    for pair, (x, y, z) in enumerate(modes):
        value = spectrum[x, y, z]
        decoded[2 * pair] = value.real / scale
        decoded[2 * pair + 1] = -value.imag / scale
        selected[x, y, z] = True
        selected[(-x) % N, (-y) % N, (-z) % N] = True
    energy = np.abs(spectrum) ** 2
    total = float(energy.sum())
    residual = 0.0 if total == 0.0 else float(energy[~selected].sum() / total)
    return decoded, float(np.linalg.norm(epsilon)), residual


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    left64 = np.asarray(left, dtype=np.float64)
    right64 = np.asarray(right, dtype=np.float64)
    denominator = float(np.linalg.norm(left64) * np.linalg.norm(right64))
    return 0.0 if denominator == 0.0 else float(np.dot(left64, right64) / denominator)


def relative_l2(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = float(np.linalg.norm(expected))
    numerator = float(np.linalg.norm(actual - expected))
    return 0.0 if denominator == 0.0 and numerator == 0.0 else numerator / denominator


def validate_common(document: dict[str, Any], label: str) -> None:
    require(document.get("protocol") == PROTOCOL, f"{label}: protocol mismatch")
    require(document.get("version") == VERSION, f"{label}: version mismatch")
    require(document.get("grid_n") == N, f"{label}: grid mismatch")
    require(document.get("dimension") == DIMENSION, f"{label}: dimension mismatch")
    require(math.isclose(float(document.get("phi")), PHI, rel_tol=0.0, abs_tol=1e-13), f"{label}: phi mismatch")
    require(math.isclose(float(document.get("dt")), DT, rel_tol=0.0, abs_tol=1e-13), f"{label}: dt mismatch")
    require(document.get("layout") == LAYOUT, f"{label}: layout mismatch")
    require(document.get("dtype") == DTYPE, f"{label}: dtype mismatch")
    require(document.get("horizons") == HORIZONS, f"{label}: horizons mismatch")
    cases = document.get("cases")
    require(isinstance(cases, list) and len(cases) == len(CASE_IDS), f"{label}: case count mismatch")


def cases_by_id(document: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for case in document["cases"]:
        require(isinstance(case, dict), f"{label}: malformed case")
        case_id = case.get("id")
        require(case_id in CASE_IDS and case_id not in result, f"{label}: invalid/duplicate case {case_id}")
        require(case.get("basis") == CASE_BASIS[case_id], f"{label}: basis mismatch for {case_id}")
        result[case_id] = case
    require(set(result) == set(CASE_IDS), f"{label}: missing case")
    return result


def main() -> None:
    seed_raw, seed = load_json(SEED_PATH)
    gpu_raw, gpu = load_json(GPU_PATH)
    _, receipt = load_json(RECEIPT_PATH)
    validate_common(seed, "seed")
    validate_common(gpu, "GPU")
    require(seed.get("amplitude") == AMPLITUDE, "seed: amplitude mismatch")

    canonical = canonical_modes()
    shuffled = shuffled_modes(canonical)
    require(seed["basis"]["canonical"]["modes"] == [list(mode) for mode in canonical], "canonical mode manifest mismatch")
    require(seed["basis"]["shuffled"]["modes"] == [list(mode) for mode in shuffled], "shuffled mode manifest mismatch")

    seed_cases = cases_by_id(seed, "seed")
    gpu_cases = cases_by_id(gpu, "GPU")
    embeddings: dict[str, np.ndarray] = {}
    prepared: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for case_id in CASE_IDS:
        case = seed_cases[case_id]
        signal = decode_f32(case["signal_b64"], VOLUME)
        ey = decode_f32(case["ey_b64"], VOLUME)
        ei = decode_f32(case["ei_b64"], VOLUME)
        prepared[case_id] = (ey, ei)
        if case_id == "zero":
            require(case.get("embedding_b64") is None, "zero case has an embedding")
            require(not signal.tobytes().strip(b"\x00") and not ey.tobytes().strip(b"\x00") and not ei.tobytes().strip(b"\x00"), "zero seed is not byte-zero")
        else:
            embeddings[case_id] = normalize(decode_f32(case["embedding_b64"], DIMENSION))
            joined = ey.astype(np.float64) - PHI * ei.astype(np.float64)
            require(relative_l2(joined, signal.astype(np.float64)) <= 2e-6, f"{case_id}: split does not reconstruct signal")
            modes = canonical if case["basis"] == "canonical" else shuffled
            decoded, _, _ = decode_embedding(ey, ei, modes)
            require(cosine(decoded, embeddings[case_id]) >= 0.999999, f"{case_id}: CPU cosine gate failed")
            require(relative_l2(decoded, embeddings[case_id]) <= 2e-6, f"{case_id}: CPU relative-L2 gate failed")

    decoded_by_horizon: dict[int, dict[str, np.ndarray]] = {horizon: {} for horizon in HORIZONS}
    global_max_abs = 0.0
    zero_ok = True
    for case_id in CASE_IDS:
        case = gpu_cases[case_id]
        checkpoints = case.get("checkpoints")
        require(isinstance(checkpoints, list) and len(checkpoints) == len(HORIZONS), f"{case_id}: checkpoint count mismatch")
        modes = canonical if case["basis"] in {"canonical", "zero"} else shuffled
        for expected_step, checkpoint in zip(HORIZONS, checkpoints, strict=True):
            require(checkpoint.get("step") == expected_step, f"{case_id}/{expected_step}: step mismatch")
            require(abs(float(checkpoint.get("t")) - expected_step * DT) <= 1e-6, f"{case_id}/{expected_step}: time mismatch")
            require(checkpoint.get("finite") is True, f"{case_id}/{expected_step}: non-finite flag")
            ey = decode_f32(checkpoint["ey_b64"], VOLUME)
            ei = decode_f32(checkpoint["ei_b64"], VOLUME)
            max_abs = float(max(np.max(np.abs(ey)), np.max(np.abs(ei))))
            global_max_abs = max(global_max_abs, max_abs)
            require(max_abs <= 10.0, f"{case_id}/{expected_step}: field bound exceeded")
            require(abs(max_abs - float(checkpoint["max_abs"])) <= 2e-6 * max(1.0, max_abs), f"{case_id}/{expected_step}: max_abs summary mismatch")
            decoded, epsilon_l2, _ = decode_embedding(ey, ei, modes)
            require(abs(epsilon_l2 - float(checkpoint["epsilon_l2"])) <= 2e-6 * max(1.0, epsilon_l2), f"{case_id}/{expected_step}: epsilon norm mismatch")
            if case_id == "zero":
                zero_ok = zero_ok and not ey.tobytes().strip(b"\x00") and not ei.tobytes().strip(b"\x00")
            else:
                decoded_by_horizon[expected_step][case_id] = decoded
                if expected_step == 0:
                    seed_ey, seed_ei = prepared[case_id]
                    require(ey.tobytes() == seed_ey.tobytes() and ei.tobytes() == seed_ei.tobytes(), f"{case_id}: GPU seed is not byte-identical")
                    require(cosine(decoded, embeddings[case_id]) >= 0.999999, f"{case_id}: GPU t0 cosine gate failed")
                    require(relative_l2(decoded, embeddings[case_id]) <= 2e-6, f"{case_id}: GPU t0 relative-L2 gate failed")
    require(zero_ok, "zero GPU control is not byte-zero")
    require(gpu.get("finite") is True and gpu.get("verdict") == "PASS", "GPU receipt is not PASS")

    geometry = "SUPPORTS"
    rows = []
    for horizon in HORIZONS:
        vectors = decoded_by_horizon[horizon]
        norms = {case_id: float(np.linalg.norm(vectors[case_id])) for case_id in CANONICAL_IDS}
        near = cosine(vectors["anchor"], vectors["near"])
        orthogonal = cosine(vectors["anchor"], vectors["orthogonal"])
        opposite = cosine(vectors["anchor"], vectors["opposite"])
        ordered = near > orthogonal > opposite
        if any(value <= 1e-6 for value in norms.values()):
            geometry = "INCONCLUSIVE"
        elif not ordered and geometry != "INCONCLUSIVE":
            geometry = "CONTRADICTS"
        rows.append((horizon, near, orthogonal, opposite, ordered))

    require(receipt.get("verdict") == "PASS", "reduced receipt is not PASS")
    require(receipt.get("geometry", {}).get("verdict") == geometry, "reduced geometry verdict mismatch")
    require(receipt["artifacts"]["seed"]["sha256"] == hashlib.sha256(seed_raw).hexdigest(), "seed hash mismatch")
    require(receipt["artifacts"]["gpu"]["sha256"] == hashlib.sha256(gpu_raw).hexdigest(), "GPU hash mismatch")
    require(receipt.get("cpu_codec_contract", {}).get("pass") is True, "reduced C1 is not PASS")
    require(receipt.get("gpu_seed_contract", {}).get("pass") is True, "reduced C2 is not PASS")
    require(receipt.get("extended_horizon_contract", {}).get("pass") is True, "reduced C3 is not PASS")

    print(json.dumps({
        "verdict": receipt["verdict"],
        "geometry": geometry,
        "max_abs": global_max_abs,
        "terminal": {
            "horizon": rows[-1][0],
            "near": rows[-1][1],
            "orthogonal": rows[-1][2],
            "opposite": rows[-1][3],
            "ordered": rows[-1][4],
        },
        "seed_sha256": hashlib.sha256(seed_raw).hexdigest(),
        "gpu_sha256": hashlib.sha256(gpu_raw).hexdigest(),
    }, indent=2))
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
