"""Source-independent NumPy verifier for the frozen L47 board."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BOARD_SCHEMA = "cassi.l47.absorbing-harmonic-age-shift-board.v1"
TRACE_SCHEMA = "cassi.l47.absorbing-harmonic-age-shift-traces.v1"
VERIFICATION_SCHEMA = "cassi.l47.absorbing-harmonic-age-shift-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-absorbing-harmonic-age-write.v2"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
PREREGISTRATION = ROOT / "designs" / "L47-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag/l47-absorbing-harmonic-age-shift/l47-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts/l47-absorbing-harmonic-age-shift"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L47-ABSORBING-HARMONIC-AGE-SHIFT-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l47-verification.json"
CHANNELS, MODE_COUNT, WIDTH, ALPHABET, BATCH = 7, 2048, 1024, 260, 8
FLOOR = 1.0e-8
ATOL_NATIVE = RTOL_NATIVE = 3.0e-6
ATOL_SCORE, RTOL_SCORE = 3.0e-5, 2.0e-4
ATOL_DRIFT = 2.0e-6
AGE_HARMONICS = np.asarray((1, 2, 3, 4, 5, 6, 0), dtype=np.int64)
SYMBOL_BASE = np.asarray((0, 37, 74, 111, 148, 185, 222, 259), dtype=np.int64)
SYMBOLS = (SYMBOL_BASE + 181) % ALPHABET

EXPECTED_SOURCE_PATHS = {
    "designs/L47-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md",
    "cassi_qi_profile.py",
    "cassi_qi_field.py",
    "cassi_prismatic_field.py",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_harmonic_age_field.py",
    "cassi_absorbing_harmonic_age_field.py",
    "verification/run_l47_absorbing_harmonic_age_shift.py",
    "verification/verify_l47_absorbing_harmonic_age_shift.py",
}


class L47VerificationError(RuntimeError):
    pass


def need(ok: bool, message: str) -> None:
    if not ok:
        raise L47VerificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _finite_json(value: Any, label: str = "JSON") -> None:
    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        need(math.isfinite(value), f"{label} is nonfinite")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _finite_json(item, f"{label}[{i}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            need(isinstance(key, str), f"{label} has non-string key")
            _finite_json(item, f"{label}.{key}")
    else:
        raise L47VerificationError(f"{label} has unsupported JSON value")


def load_json(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    need(isinstance(value, Mapping), "JSON must be an object")
    _finite_json(value)
    need(raw == canonical_bytes(value), "JSON is not canonical")
    return value


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _field_dimensions(field: np.ndarray) -> tuple[int, int]:
    need(field.ndim == 3 and field.shape[0] == CHANNELS and field.shape[1] % 9 == 0,
         "native field layout mismatch")
    modes = field.shape[1] // 9
    need(modes == MODE_COUNT and field.shape[2] == BATCH, "field dimensions mismatch")
    return modes, modes // 2


def native_coordinates(field: np.ndarray) -> tuple[np.ndarray, ...]:
    modes, width = _field_dimensions(field)
    packed = field.reshape(CHANNELS, 9, modes, BATCH)
    return tuple(packed[:, i, :width] + 1j * packed[:, i + 1, :width] for i in (0, 2, 4, 6))


def pack_field(field: np.ndarray, coords: tuple[np.ndarray, ...]) -> np.ndarray:
    modes, width = _field_dimensions(field)
    out = np.array(field, copy=True)
    packed = out.reshape(CHANNELS, 9, modes, BATCH)
    for i, value in zip((0, 2, 4, 6), coords):
        packed[:, i, :width] = np.real(value)
        packed[:, i + 1, :width] = np.imag(value)
        packed[:, i:i + 2, width:] = 0.0
    packed[:, 8, width:] = 0.0
    return out


def phase_vector() -> np.ndarray:
    return np.exp(2j * np.pi * np.arange(CHANNELS, dtype=np.float64) / CHANNELS)


def dft(values: np.ndarray) -> np.ndarray:
    phase = phase_vector()
    return np.einsum("kj,jwb->kwb", phase.conj()[None, :] ** np.arange(CHANNELS)[:, None], values,
                     optimize=True) / math.sqrt(CHANNELS)


def inverse_dft(values: np.ndarray) -> np.ndarray:
    phase = phase_vector()
    return np.einsum("jk,kwb->jwb", phase[None, :] ** np.arange(CHANNELS)[:, None], values,
                     optimize=True) / math.sqrt(CHANNELS)


def absorbing_projection(differential: np.ndarray) -> np.ndarray:
    phase = phase_vector()[:, None, None]
    return phase * (differential - differential.mean(axis=0, keepdims=True))


def dynamic_energy(field: np.ndarray) -> np.ndarray:
    modes, width = _field_dimensions(field)
    packed = field.reshape(CHANNELS, 9, modes, BATCH)
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    return (
        (packed[:, :8, :width].astype(np.float64) ** 2)
        .sum(axis=1).mean(axis=1)
        / (1.0 + phi * phi)
    )


def codebook_complex(codebook: np.ndarray) -> np.ndarray:
    need(codebook.shape == (ALPHABET, WIDTH, 2), "codebook shape mismatch")
    return codebook[..., 0] + 1j * codebook[..., 1]


def givens_write(field: np.ndarray, codebook: np.ndarray, symbols: np.ndarray, *, cyclic: bool = False) -> np.ndarray:
    common, differential, common_v, differential_v = native_coordinates(field)
    if cyclic:
        differential = phase_vector()[:, None, None] * differential
        differential_v = phase_vector()[:, None, None] * differential_v
    code = codebook_complex(codebook)[symbols]
    direction = (
        phase_vector()[:, None, None]
        * code.transpose(1, 0)[None, :, :]
        / math.sqrt(CHANNELS)
    )
    white = np.full(CHANNELS, 1.0 / math.sqrt(CHANNELS))
    carrier = np.sum(white[:, None, None] * common, axis=0)
    chromatic = np.sum(np.conjugate(direction) * differential, axis=0)
    carrier_v = np.sum(white[:, None, None] * common_v, axis=0)
    chromatic_v = np.sum(np.conjugate(direction) * differential_v, axis=0)
    cosine, sine = 0.0, 1.0  # frozen trust-one Givens angle
    new_chromatic, new_carrier = cosine * chromatic + sine * carrier, cosine * carrier - sine * chromatic
    new_chromatic_v, new_carrier_v = cosine * chromatic_v + sine * carrier_v, cosine * carrier_v - sine * chromatic_v
    common = common + white[:, None, None] * (new_carrier - carrier)[None]
    differential = differential + direction * (new_chromatic - chromatic)[None]
    common_v = common_v + white[:, None, None] * (new_carrier_v - carrier_v)[None]
    differential_v = differential_v + direction * (new_chromatic_v - chromatic_v)[None]
    result = pack_field(field, (common, differential, common_v, differential_v))
    packed = result.reshape(CHANNELS, 9, MODE_COUNT, BATCH)
    active = packed[:, :8, :WIDTH]
    clamped = np.clip(active, -8.0, 8.0)
    packed[:, :8, :WIDTH] = clamped
    energy = (
        (clamped.astype(np.float64) ** 2)
        .sum(axis=1)
        .mean(axis=1)
        / (1.0 + ((1 + math.sqrt(5.0)) / 2.0) ** 2)
    )
    factors = np.where(
        energy > 4.0,
        np.sqrt(4.0 / np.maximum(energy, 1e-30)),
        1.0,
    )
    packed[:, :8, :WIDTH] *= factors[:, None, None, :]
    packed[:, 8, :WIDTH] = np.clip(packed[:, 8, :WIDTH], 0.0, 4096.0)
    packed[:, :, WIDTH:] = 0.0
    return result


def reconstruct_readout(field: np.ndarray, codebook: np.ndarray) -> dict[str, np.ndarray]:
    _, differential, _, differential_v = native_coordinates(field)
    code = codebook_complex(codebook)
    phase = phase_vector()
    coefficients = np.einsum("sw,jwb->jbs", code.conj(), differential, optimize=True) / WIDTH
    aligned = phase.conj()[:, None, None] * coefficients
    white_scores = np.abs(aligned.sum(axis=0) / math.sqrt(CHANNELS)) ** 2
    rms = np.sqrt(np.mean(np.abs(differential) ** 2, axis=1))
    available = (np.mean(np.abs(differential) ** 2, axis=(0, 1)) >= FLOOR) & ((rms >= FLOOR).sum(axis=0) >= 2)
    physical_d, physical_v = dft(differential), dft(differential_v)
    age_d = physical_d[AGE_HARMONICS]
    age_coeff = np.einsum("sw,kwb->bks", code.conj(), age_d, optimize=True) / WIDTH
    age_scores = np.abs(age_coeff) ** 2
    age_symbols = np.argmax(age_scores, axis=2).astype(np.int64)
    age_max = age_scores.max(axis=2)
    age_available = available[:, None] & (age_max >= FLOOR)
    scores = (age_scores / np.maximum(age_max, FLOOR)[:, :, None]).max(axis=1)
    candidates = np.arange(ALPHABET)[None, :]
    for age in range(CHANNELS - 1, -1, -1):
        slot = age_available[:, age, None] & (candidates == age_symbols[:, age, None])
        scores = np.where(slot, 8.0 - age, scores)
    scores = np.where(available[:, None], scores, white_scores)
    return {"scores": scores.astype(np.float32), "symbols": age_symbols[:, 0],
            "symbol_available": age_available[:, 0], "available": available,
            "physical_d": physical_d, "physical_vd": physical_v, "age_scores": age_scores.astype(np.float32),
            "age_symbols": age_symbols, "age_available": age_available}


def _artifact(board_path: Path, value: Any, expected_name: str, label: str) -> Path:
    item = mapping(value, label)
    need(item.get("path") == expected_name, f"{label} sibling name mismatch")
    path = board_path.parent / expected_name
    need(path.is_file(), f"{label} artifact missing")
    need(item.get("sha256") == sha256_file(path), f"{label} hash mismatch")
    return path


def _check_sources(board: Mapping[str, Any]) -> None:
    source = mapping(board.get("source_sha256"), "source_sha256")
    need(set(source) == EXPECTED_SOURCE_PATHS, "source hash path set mismatch")
    for relative in EXPECTED_SOURCE_PATHS:
        path = ROOT / relative
        need(path.is_file(), f"source path missing: {relative}")
        need(source.get(relative) == sha256_file(path), f"source hash mismatch: {relative}")
    pre = PREREGISTRATION.relative_to(ROOT).as_posix()
    need(board.get("preregistration_sha256") == source.get(pre), "preregistration hash mismatch")


def _check_arrays(arrays: Mapping[str, np.ndarray]) -> None:
    required = {
        "schema_id", "codebook", "channel_phase", "age_harmonics",
        "age_symbols", "deposit_symbols", "analytic_amplitudes",
        "pre_field_sha256", "operator_pre_field", "operator_identity_field",
        "operator_post_field", "operator_pre_harmonic_d", "operator_pre_harmonic_vd",
        "operator_post_harmonic_d", "operator_post_harmonic_vd",
    }
    need(required <= set(arrays), "trace array set is incomplete")
    need(arrays["schema_id"].shape == () and arrays["schema_id"].dtype.kind == "U"
         and arrays["schema_id"].item() == TRACE_SCHEMA, "trace schema array mismatch")
    need(arrays["codebook"].shape == (ALPHABET, WIDTH, 2)
         and arrays["codebook"].dtype == np.float32, "codebook shape/dtype mismatch")
    need(arrays["channel_phase"].shape == (CHANNELS, 2)
         and arrays["channel_phase"].dtype == np.float32, "phase shape/dtype mismatch")
    need(arrays["age_harmonics"].shape == (CHANNELS,) and arrays["age_harmonics"].dtype == np.int64
         and np.array_equal(arrays["age_harmonics"], AGE_HARMONICS), "age harmonics mismatch")
    for name, value in arrays.items():
        if value.dtype.kind in "fc":
            need(bool(np.isfinite(value).all()), f"{name} contains nonfinite values")
        if "field" in name and value.dtype.kind == "f":
            need(value.dtype == np.float32 and value.shape[-3:] == (CHANNELS, 9 * MODE_COUNT, BATCH),
                 f"{name} field shape/dtype mismatch")
        if name.endswith("_symbols") or name.endswith("_clamp_count"):
            need(value.dtype == np.int64, f"{name} dtype mismatch")
        if name.endswith("_available"):
            need(value.dtype == np.bool_, f"{name} dtype mismatch")
        if name.endswith("_harmonic_d") or name.endswith("_harmonic_vd") or name.endswith("_coefficients"):
            need(value.dtype == np.complex64, f"{name} dtype mismatch")
    for name, value in arrays.items():
        if name.endswith(("_c", "_d", "_vc", "_vd", "_epsilon")):
            need(value.shape[-3:] == (CHANNELS, WIDTH, BATCH), f"{name} shape mismatch")
        if name.endswith("_inactive_tail"):
            need(value.shape[-4:] == (CHANNELS, 9, WIDTH, BATCH), f"{name} shape mismatch")
        if name.endswith("_age_scores"):
            need(value.shape[-3:] == (BATCH, CHANNELS, ALPHABET), f"{name} shape mismatch")
        if name.endswith(("_age_symbols", "_age_available")):
            need(value.shape[-2:] == (BATCH, CHANNELS), f"{name} shape mismatch")
        if name.endswith("_readout_scores"):
            need(value.shape[-2:] == (BATCH, ALPHABET), f"{name} shape mismatch")
        if name.endswith(("_readout_symbols", "_readout_available")):
            need(value.shape[-1:] == (BATCH,), f"{name} shape mismatch")
        if name.endswith(("_harmonic_d", "_harmonic_vd")):
            need(value.shape[-3:] == (CHANNELS, WIDTH, BATCH), f"{name} shape mismatch")
        if name.endswith("_coefficients"):
            need(value.shape[-3:] == (BATCH, CHANNELS, ALPHABET), f"{name} shape mismatch")
        if name.endswith("_dynamic_energy"):
            need(value.shape[-2:] == (CHANNELS, BATCH), f"{name} shape mismatch")
        if name.endswith("_drift"):
            need(value.shape[-1:] == (BATCH,), f"{name} shape mismatch")


def _close(a: np.ndarray, b: np.ndarray, label: str, *, score: bool = False) -> None:
    need(np.allclose(a, b, atol=ATOL_SCORE if score else ATOL_NATIVE, rtol=RTOL_SCORE if score else RTOL_NATIVE),
         f"{label} mismatch")


def _zero_clamps(arrays: Mapping[str, np.ndarray]) -> None:
    for name, value in arrays.items():
        if "clamp_count" in name:
            need(bool(np.all(value == 0)), f"{name} contains clamps")


def _bounds(fields: list[np.ndarray]) -> float:
    maximum = 0.0
    for field in fields:
        packed = np.asarray(field).reshape(-1, CHANNELS, 9, MODE_COUNT, BATCH)
        need(bool(np.all(packed[:, :, :, WIDTH:] == 0)),
             "inactive packed coordinates are nonzero")
        active, epsilon = packed[:, :, :8, :WIDTH], packed[:, :, 8, :WIDTH]
        need(bool(np.all((epsilon >= 0) & (epsilon <= 4096))),
             "epsilon bound exceeded")
        item = float(np.abs(active).max())
        maximum = max(maximum, item)
        need(item <= 8.0 + ATOL_NATIVE, "active amplitude bound exceeded")
        fields4 = packed.reshape(-1, CHANNELS, 9 * MODE_COUNT, BATCH)
        energies = np.stack([dynamic_energy(item_field) for item_field in fields4])
        need(float(energies.max()) <= 4.0 + ATOL_NATIVE,
             "dynamic energy bound exceeded")
    return maximum


def absorbing_projection_field(field: np.ndarray) -> np.ndarray:
    common, differential, common_v, differential_v = native_coordinates(field)
    return pack_field(field, (common, absorbing_projection(differential), common_v,
                              absorbing_projection(differential_v)))


def _compare_capture(
    arrays: Mapping[str, np.ndarray],
    prefix: str,
    field: np.ndarray,
    codebook: np.ndarray,
    failures: list[str],
) -> bool:
    ok = True
    expected = reconstruct_readout(field, codebook)
    numeric = {
        "harmonic_d": ("physical_d", False),
        "harmonic_vd": ("physical_vd", False),
        "age_scores": ("age_scores", True),
        "readout_scores": ("scores", True),
    }
    availability = {
        "age_available": "age_available",
        "readout_available": "available",
    }
    symbols = {
        "age_symbols": ("age_symbols", "age_available"),
        "readout_symbols": ("symbols", "symbol_available"),
    }
    for suffix, (expected_name, score) in numeric.items():
        name = f"{prefix}_{suffix}"
        if name not in arrays:
            continue
        try:
            _close(
                arrays[name],
                expected[expected_name],
                name,
                score=score,
            )
        except L47VerificationError as exc:
            failures.append(str(exc))
            ok = False
    for suffix, expected_name in availability.items():
        name = f"{prefix}_{suffix}"
        if name not in arrays:
            continue
        try:
            need(
                np.array_equal(arrays[name], expected[expected_name]),
                f"{name} mismatch",
            )
        except L47VerificationError as exc:
            failures.append(str(exc))
            ok = False
    for suffix, (expected_name, available_name) in symbols.items():
        name = f"{prefix}_{suffix}"
        if name not in arrays:
            continue
        expected_available = expected[available_name]
        recorded_available = (
            arrays[f"{prefix}_age_available"]
            if suffix == "age_symbols"
            else arrays[f"{prefix}_age_available"][:, 0]
        )
        mask = expected_available & recorded_available
        try:
            need(
                np.array_equal(
                    arrays[name][mask], expected[expected_name][mask]
                ),
                f"{name} available-winner mismatch",
            )
        except L47VerificationError as exc:
            failures.append(str(exc))
            ok = False
    return ok


def _capture_field(base: np.ndarray, arrays: Mapping[str, np.ndarray],
                   prefix: str, index: int) -> np.ndarray:
    return pack_field(
        base,
        tuple(arrays[f"{prefix}_{component}"][index]
              for component in ("c", "d", "vc", "vd")),
    )


def verify_board(board_path: Path, *, allow_smoke_device: bool = False) -> tuple[str, dict[str, Any]]:
    board = load_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA and board.get("status") == "COMPLETE",
         "board identity/status mismatch")
    for key, expected in (("layout_profile_id", LAYOUT_PROFILE),
                          ("operator_profile_id", OPERATOR_PROFILE),
                          ("projection_profile_id", PROJECTION_PROFILE),
                          ("trace_schema_id", TRACE_SCHEMA)):
        need(board.get(key) == expected, f"{key} mismatch")
    _check_sources(board)
    constants = mapping(board.get("constants"), "constants")
    expected_constants = {
        "mode_count": MODE_COUNT, "active_modes": WIDTH, "channels": CHANNELS,
        "batch_size": BATCH, "alphabet_size": ALPHABET, "evolution_steps": 8,
        "readout_energy_floor": FLOOR, "max_mode_amplitude": 8.0,
        "max_epsilon": 4096.0, "write_count": 128, "save_write_index": 63,
        "age_harmonics": list(AGE_HARMONICS), "deposit_offset": 181,
        "age_offsets": {"0": 0, "1": 53, "2": 97, "3": 149, "6": 223},
        "age_amplitudes": {"0": 0.08, "1": 0.07, "2": 0.06, "3": 0.05, "6": 0.09},
    }
    for key, expected in expected_constants.items():
        need(constants.get(key) == expected, f"constant {key} mismatch")
    device = mapping(board.get("device"), "device")
    need(device.get("dtype") == "float32", "canonical dtype mismatch")
    if not allow_smoke_device:
        need(device.get("requested") == "cuda" and device.get("type") == "cuda"
             and device.get("name") == "AMD Radeon RX 7900 XTX", "canonical device mismatch")
        need(board.get("execution") == {"canonical": True, "smoke": False, "cpu_smoke": False},
             "canonical execution mismatch")
    trace_path = _artifact(board_path, board.get("trace"), "l47-traces.npz", "trace")
    with np.load(trace_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    _check_arrays(arrays)
    need(
        mapping(board.get("trace"), "trace").get("array_count")
        == len(arrays),
        "trace array count mismatch",
    )
    failures: list[str] = []
    codebook = arrays["codebook"]
    pre = arrays["operator_pre_field"]
    identity = arrays["operator_identity_field"]
    absorbing = arrays["operator_post_field"]
    operator_ok = True
    try:
        need(np.array_equal(identity, pre), "identity branch is not byte-identical")
        expected_absorbing = absorbing_projection_field(pre)
        _close(absorbing, expected_absorbing, "absorbing projection")
        need(np.array_equal(absorbing.reshape(CHANNELS, 9, MODE_COUNT, BATCH)[:, 8],
                            pre.reshape(CHANNELS, 9, MODE_COUNT, BATCH)[:, 8]),
             "operator changed epsilon")
        for prefix, field in (("operator_pre", pre), ("operator_post", absorbing)):
            common_f, differential_f, common_v_f, differential_v_f = native_coordinates(field)
            for suffix, expected in (("c", common_f), ("d", differential_f),
                                     ("vc", common_v_f), ("vd", differential_v_f)):
                _close(arrays[f"{prefix}_{suffix}"], expected, f"{prefix} {suffix}")
            _close(arrays[f"{prefix}_harmonic_d"], dft(differential_f), f"{prefix} DFT")
            _close(arrays[f"{prefix}_harmonic_vd"], dft(differential_v_f), f"{prefix} VD DFT")
            _close(arrays[f"{prefix}_coefficients"],
                   np.einsum("sw,kwb->bks", codebook_complex(codebook).conj(),
                             dft(differential_f)[AGE_HARMONICS], optimize=True) / WIDTH,
                   f"{prefix} coefficients")
            _close(arrays[f"{prefix}_dynamic_energy"], dynamic_energy(field),
                   f"{prefix} dynamic energy")
            if not _compare_capture(arrays, prefix, field, codebook, failures):
                operator_ok = False
        common_pre, _, common_v_pre, _ = native_coordinates(pre)
        common_post, _, common_v_post, _ = native_coordinates(absorbing)
        need(np.array_equal(common_pre, common_post) and np.array_equal(common_v_pre, common_v_post),
             "projection changed common coordinates")
        zero = dft(native_coordinates(pre)[1])[0]
        zero_v = dft(native_coordinates(pre)[3])[0]
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        expected_loss = (np.abs(zero) ** 2 + np.abs(zero_v) ** 2).mean(axis=0) / (
            CHANNELS * (1.0 + phi * phi)
        )
        pre_hash = hashlib.sha256(np.ascontiguousarray(pre).tobytes()).hexdigest()
        need(arrays["pre_field_sha256"].shape == () and arrays["pre_field_sha256"].item() == pre_hash,
             "pre-state hash receipt mismatch")
        need(arrays.get("operator_identity_field_sha256", np.asarray(pre_hash)).item()
             == hashlib.sha256(np.ascontiguousarray(identity).tobytes()).hexdigest(),
             "identity field hash receipt mismatch")
        need(arrays.get("operator_absorbing_field_sha256", np.asarray(pre_hash)).item()
             == hashlib.sha256(np.ascontiguousarray(absorbing).tobytes()).hexdigest(),
             "absorbing field hash receipt mismatch")
        _close(arrays["operator_predicted_removed_energy"], expected_loss,
               "predicted removed energy")
        _close(arrays["operator_removed_energy"],
               dynamic_energy(pre).mean(axis=0) - dynamic_energy(absorbing).mean(axis=0),
               "observed removed energy")
        cleared_energy = (
            np.abs(arrays["operator_post_harmonic_d"][1]) ** 2
            + np.abs(arrays["operator_post_harmonic_vd"][1]) ** 2
        ).mean(axis=0) / (CHANNELS * (1.0 + phi * phi))
        need(bool(np.all(cleared_energy < FLOOR)), "cleared age-zero harmonic exceeds energy floor")
        need(not bool(np.any(arrays["operator_post_age_available"][:, 0])),
             "cleared age-zero harmonic is available")
        _close(arrays["operator_post_harmonic_d"][0],
               arrays["operator_pre_harmonic_d"][6], "advanced harmonic-zero D")
        _close(arrays["operator_post_harmonic_vd"][0],
               arrays["operator_pre_harmonic_vd"][6], "advanced harmonic-zero VD")
        need(bool(np.all(dynamic_energy(absorbing) <= dynamic_energy(pre) + ATOL_NATIVE)),
             "projection increased energy")
    except L47VerificationError as exc:
        operator_ok = False; failures.append(str(exc))
    deposit_ok = True
    readout_ok = True
    deposit = arrays["deposit_symbols"]
    try:
        for name, cyclic in (("cyclic_write", True), ("absorbing_write", False)):
            before = arrays[f"{name}_pre_field"]
            shifted = arrays[f"{name}_post_shift_field"]
            common0, differential0, common_v0, differential_v0 = native_coordinates(before)
            expected_shift = pack_field(
                before,
                (common0, phase_vector()[:, None, None] * differential0 if cyclic else
                 absorbing_projection(differential0), common_v0,
                 phase_vector()[:, None, None] * differential_v0 if cyclic else
                 absorbing_projection(differential_v0)),
            )
            _close(shifted, expected_shift, f"{name} shift")
            _close(arrays[f"{name}_post_field"], givens_write(shifted, codebook, deposit),
                   f"{name} write")
            energy_before = dynamic_energy(shifted).mean(axis=0)
            energy_after = dynamic_energy(arrays[f"{name}_post_field"]).mean(axis=0)
            expected_drift = np.where(
                (energy_before == 0.0) & (energy_after == 0.0), 0.0,
                (energy_after - energy_before) /
                np.maximum(np.abs(energy_before), np.finfo(np.float64).eps),
            ).astype(np.float32)
            if name == "absorbing_write":
                age_symbols = arrays[f"{name}_post_age_symbols"]
                age_available = arrays[f"{name}_post_age_available"]
                need(
                    bool(
                        np.all(
                            age_symbols[:, 0][age_available[:, 0]]
                            == deposit[age_available[:, 0]]
                        )
                    ),
                    "deposit does not occupy age zero",
                )
                need(
                    bool(
                        np.all(
                            age_symbols[:, 1][age_available[:, 1]]
                            == arrays["age_symbols"][0][
                                age_available[:, 1]
                            ]
                        )
                    ),
                    "current symbol did not advance to age one",
                )
                need(not np.any(age_available & (age_symbols == arrays["age_symbols"][4][:, None])),
                     "evicted age-six contribution remains")
            _close(arrays[f"{name}_drift"], expected_drift, f"{name} drift")
            need(bool(np.all(np.abs(arrays[f"{name}_drift"]) <= ATOL_DRIFT)),
                 f"{name} energy drift")
            if not _compare_capture(arrays, f"{name}_post",
                                    arrays[f"{name}_post_field"], codebook, failures):
                readout_ok = False
    except (KeyError, L47VerificationError) as exc:
        deposit_ok = False; failures.append(str(exc))
    if not deposit_ok:
        readout_ok = False
    stress_ok = True
    try:
        stress_symbols = arrays["stress_symbols"]
        stress_initial = arrays["stress_initial_field"]
        for branch, cyclic in (("cyclic", True), ("absorbing", False)):
            for index in range(stress_symbols.shape[0]):
                heartbeat = _capture_field(stress_initial, arrays,
                                           f"stress_{branch}_post_heartbeat", index)
                shifted = arrays[f"stress_{branch}_post_shift_field"][index]
                expected_shift = absorbing_projection_field(heartbeat)
                if cyclic:
                    c, d, vc, vd = native_coordinates(heartbeat)
                    expected_shift = pack_field(
                        heartbeat, (c, phase_vector()[:, None, None] * d, vc,
                                    phase_vector()[:, None, None] * vd))
                _close(shifted, expected_shift, f"stress {branch} shift {index}")
                written = arrays[f"stress_{branch}_post_write_field"][index]
                expected_write = givens_write(shifted, codebook, stress_symbols[index])
                _close(written, expected_write, f"stress {branch} write {index}")
                _close(arrays[f"stress_{branch}_post_write_dynamic_energy"][index],
                       dynamic_energy(written), f"stress {branch} energy {index}")
                before_energy = dynamic_energy(shifted).mean(axis=0)
                after_energy = dynamic_energy(written).mean(axis=0)
                expected_drift = np.where(
                    (before_energy == 0.0) & (after_energy == 0.0), 0.0,
                    (after_energy - before_energy) /
                    np.maximum(np.abs(before_energy), np.finfo(np.float64).eps),
                ).astype(np.float32)
                _close(arrays[f"stress_{branch}_drift"][index],
                       expected_drift, f"stress {branch} drift {index}")
                expected_max = np.asarray(np.abs(written.reshape(
                    CHANNELS, 9, MODE_COUNT, BATCH)[:, :8, :WIDTH]).max(), dtype=np.float32)
                _close(arrays[f"stress_{branch}_post_write_maximum_amplitude"][index],
                       expected_max, f"stress {branch} amplitude {index}")
                single = {key: value[index] for key, value in arrays.items()
                          if key.startswith(f"stress_{branch}_post_write_")}
                if not _compare_capture(single, f"stress_{branch}_post_write",
                                        written, codebook, failures):
                    readout_ok = False
            need(bool(np.all(np.abs(arrays[f"stress_{branch}_drift"]) <= ATOL_DRIFT)),
                 f"stress {branch} energy drift")
        expected_available = np.zeros_like(arrays["stress_absorbing_post_write_age_available"])
        expected_age_symbols = np.zeros_like(arrays["stress_absorbing_post_write_age_symbols"])
        for index in range(stress_symbols.shape[0]):
            count = min(index + 1, CHANNELS)
            expected_age_symbols[index, :, :count] = (
                stress_symbols[index - np.arange(count)].T
            )
            expected_available[index, :, :count] = True
        available = arrays["stress_absorbing_post_write_age_available"]
        need(np.array_equal(available, expected_available), "retirement availability mismatch")
        need(
            bool(
                np.all(
                    arrays[
                        "stress_absorbing_post_write_age_symbols"
                    ][available]
                    == expected_age_symbols[available]
                )
            ),
            "retirement age winners mismatch",
        )
        need(np.array_equal(arrays["stress_absorbing_resume_sha256"],
                            arrays["stress_absorbing_state_sha256"][64:]),
             "save/reload continuation mismatch")
        checkpoint_hash = arrays[
            "stress_absorbing_checkpoint_sha256"
        ]
        checkpoint_payload = arrays[
            "stress_absorbing_checkpoint_payload"
        ]
        need(
            checkpoint_hash.shape == ()
            and isinstance(checkpoint_hash.item(), str)
            and checkpoint_hash.item()
            == hashlib.sha256(
                checkpoint_payload.tobytes(order="C")
            ).hexdigest(),
            "checkpoint hash receipt mismatch",
        )
    except (KeyError, IndexError, L47VerificationError) as exc:
        stress_ok = False; failures.append(str(exc))
    try:
        _zero_clamps(arrays)
        field_values = [value for name, value in arrays.items()
                        if "field" in name and value.dtype == np.float32]
        _bounds(field_values)
    except L47VerificationError as exc:
        failures.append(str(exc)); operator_ok = False
    classification = ("OPERATOR_FAILURE" if not operator_ok else
                      "DEPOSIT_COUPLING_FAILURE" if not deposit_ok else
                      "READOUT_FAILURE" if not readout_ok else
                      "RETIREMENT_STRESS_FAILURE" if not stress_ok else "SUPPORTED")
    functional = operator_ok and deposit_ok and readout_ok and stress_ok
    verdict = "ADOPT" if functional else "REJECT"
    if not operator_ok:
        verdict = "FAIL"
    payload = {
        "schema_id": VERIFICATION_SCHEMA, "verdict": verdict,
        "causal_classification": classification,
        "mechanical_gates": {"integrity": True, "schema_shape_dtype_finiteness": True,
                             "native_reconstruction": operator_ok,
                             "bounds_energy_clamps": operator_ok},
        "functional_gates": {"operator": operator_ok, "deposit_coupling": deposit_ok,
                             "readout": readout_ok, "retirement_stress": stress_ok,
                             "persistence": stress_ok},
        "failures": failures, "trace_path": str(trace_path),
        "trace_sha256": sha256_file(trace_path),
    }
    return verdict, payload


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    return "\n".join(("# L47 Absorbing Harmonic Age Shift — Verification", "", f"Verdict: **{verdict}**", "",
                       f"Causal classification: `{payload.get('causal_classification')}`", "",
                       "```json", json.dumps(payload, sort_keys=True, indent=2), "```", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--allow-smoke-device", action="store_true")
    args = parser.parse_args()
    try:
        if not args.board.is_file():
            verdict, payload = "INCOMPLETE", {"schema_id": VERIFICATION_SCHEMA, "verdict": "INCOMPLETE", "mechanical_gates": {}, "functional_gates": {}, "failures": ["board artifact is unavailable"]}
        else:
            verdict, payload = verify_board(args.board.resolve(), allow_smoke_device=args.allow_smoke_device)
    except (Exception,) as exc:
        verdict, payload = "FAIL", {"schema_id": VERIFICATION_SCHEMA, "verdict": "FAIL", "mechanical_gates": {}, "functional_gates": {}, "failures": [str(exc)]}
    atomic_write(args.json.resolve(), canonical_bytes(payload))
    atomic_write(args.report.resolve(), report_text(verdict, payload).encode())
    print(report_text(verdict, payload))
    return 1 if verdict in {"FAIL", "INCOMPLETE"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
