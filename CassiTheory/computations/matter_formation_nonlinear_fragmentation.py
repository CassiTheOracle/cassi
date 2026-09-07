#!/usr/bin/env python3
"""Frozen primary nonlinear mediator/carrier competition calculation.

Run from the CassiTheory repository root:

    python -B computations/matter_formation_nonlinear_fragmentation.py \
        --output-dir runs/20260907_matter_formation_nonlinear_fragmentation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy import integrate, special

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations/matter-formation-continuum-report.md"
VERIFIER = ROOT / "computations/verify_matter_formation_nonlinear_fragmentation.py"
PUMP_RESULTS = ROOT / "runs/20260907_matter_formation_autonomous_pump/results.json"
PUMP_VERIFY = ROOT / "runs/20260907_matter_formation_autonomous_pump_verification/results.json"
PUMP_ARRAYS = ROOT / "runs/20260907_matter_formation_autonomous_pump/arrays.npz"
SPATIAL_RESULTS = ROOT / "runs/20260907_matter_formation_spatial_pump_prerequisite_recovery/results.json"
SPATIAL_VERIFY = ROOT / "runs/20260907_matter_formation_spatial_pump_verification_prerequisite_recovery/results.json"
SPATIAL_ARRAYS = ROOT / "runs/20260907_matter_formation_spatial_pump_prerequisite_recovery/arrays.npz"

PROTOCOL_HEADING = "### 28.3 Nonlinear competition calculation: pre-execution criteria"
PROTOCOL_SHA256 = "2913ebedd2626475ffab2488d6026cd83fa2c7009ffda0e668074c48ceae2c1b"
EXPECTED_HASHES = {
    "pump_results": "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5",
    "pump_verify": "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758",
    "pump_arrays": "d1679676c297295d3196c2abb9a8347becbf41f8e1ee43ba889edce544baf352",
    "spatial_results": "10c96e81220c08405392bb062e17bf4b193cdd95294d31a776b7b8c7566299e8",
    "spatial_verify": "c2126830d1cf3845b6fc3b25948e970231175105525a3bffff01d24a305ee7c0",
    "spatial_arrays": "6c8a3e5316c3ec03535ecb2d0da511458e663fc745b2aa84b933ac35fd8dee54",
}

A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
B = E_C + 1.0 / (4.0 * A)
M = 2.0 / 3.0
OMEGA = math.sqrt(24.0)
F = math.sqrt(3.0 / 2.0)
K_STAR = 2.675336705149658
P_STAR = K_STAR / 4.0
LENGTH = 2.0 * math.pi / P_STAR
MU_F = 0.362037120923008
MU_Z = 0.0017215449183269978
F_SEED = 1.0e-3
Z_SEED = 1.0e-6
F_TARGET = 1.0e-1
Z_TARGET = 1.1e-6
T_END = 30.0
SAMPLE_DT = 5.0 / 1024.0
SNAPSHOT_DT = 0.5
ARM_NAMES = (
    "homogeneous_carrier",
    "mediator_only",
    "competition",
    "phase_seed",
    "equilibrium_control",
)
SUPPORTS = "SUPPORTS—mediator modulation reaches nonlinear entry before carrier amplification in the fixed plane-symmetric parent"
CONTRADICTS = "CONTRADICTS—carrier amplification reaches its fixed comparison threshold first"


class ContractError(RuntimeError):
    """Raised when a frozen prerequisite or execution contract is violated."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def dump_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_safe(value), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def frozen_section(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(PROTOCOL_HEADING) != 1:
        raise ContractError("frozen protocol heading must occur exactly once")
    start = text.index(PROTOCOL_HEADING)
    endings = [
        position
        for marker in ("\n# ", "\n## ", "\n### ")
        if (position := text.find(marker, start + len(PROTOCOL_HEADING))) >= 0
    ]
    if not endings:
        raise ContractError("frozen protocol closing heading is missing")
    return text[start:min(endings)].rstrip() + "\n"


def require_hash(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise ContractError(f"missing prerequisite {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise ContractError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return actual


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {path}")
    return value


def finite(value: Any) -> bool:
    return bool(np.all(np.isfinite(np.asarray(value))))


def growing_vector(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    values, vectors = np.linalg.eig(np.asarray(matrix, dtype=np.float64))
    index = int(np.argmax(np.abs(values)))
    multiplier = np.real_if_close(values[index], tol=1000)
    vector = np.real_if_close(vectors[:, index], tol=1000)
    if np.iscomplexobj(multiplier) or np.iscomplexobj(vector):
        raise ContractError("growing monodromy eigenpair is not real")
    multiplier_f = float(multiplier)
    vector_f = np.asarray(vector, dtype=np.float64)
    if abs(multiplier_f) <= 1.0:
        raise ContractError("selected monodromy eigenpair is not growing")
    norm = math.sqrt(float(vector_f[0] ** 2 + (vector_f[1] / OMEGA) ** 2))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ContractError("invalid monodromy eigenvector norm")
    vector_f /= norm
    if vector_f[0] < 0.0 or (vector_f[0] == 0.0 and vector_f[1] < 0.0):
        vector_f *= -1.0
    return vector_f, multiplier_f


def initial_receipt() -> dict[str, Any]:
    return {
        "schema": "cassi.matter-formation.nonlinear-fragmentation.v1",
        "verdict": "INCONCLUSIVE",
        "passed": False,
        "qualified": False,
        "error": None,
        "scientific_execution_started": False,
        "protocol_sha256": PROTOCOL_SHA256,
        "files": {},
        "parameters": {},
        "eigenvectors": {},
        "symbolic": {},
        "resolutions": [],
        "checks": {},
        "diagnostics": {},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
    }


def source_stage(output: Path, report: Path) -> tuple[dict[str, str], np.ndarray, np.ndarray, float, float]:
    protocol = frozen_section(report)
    protocol_hash = hashlib.sha256(protocol.encode("utf-8")).hexdigest()
    if protocol_hash != PROTOCOL_SHA256:
        raise ContractError(f"frozen protocol SHA-256 mismatch: {protocol_hash} != {PROTOCOL_SHA256}")

    inputs = {
        "pump_results": PUMP_RESULTS,
        "pump_verify": PUMP_VERIFY,
        "pump_arrays": PUMP_ARRAYS,
        "spatial_results": SPATIAL_RESULTS,
        "spatial_verify": SPATIAL_VERIFY,
        "spatial_arrays": SPATIAL_ARRAYS,
    }
    hashes = {name: require_hash(path, EXPECTED_HASHES[name], name) for name, path in inputs.items()}

    pump = read_json(PUMP_RESULTS)
    pump_verify = read_json(PUMP_VERIFY)
    spatial = read_json(SPATIAL_RESULTS)
    spatial_verify = read_json(SPATIAL_VERIFY)
    if not (pump.get("passed") and pump.get("qualified") and str(pump.get("verdict", "")).startswith("SUPPORTS")):
        raise ContractError("primary pump receipt lacks its accepted qualified verdict")
    if not (pump_verify.get("passed") and pump_verify.get("qualified") and str(pump_verify.get("verdict", "")).startswith("SUPPORTS")):
        raise ContractError("independent pump receipt lacks its accepted qualified verdict")
    if not (spatial.get("qualified") and str(spatial.get("verdict", "")).startswith("INCONCLUSIVE")):
        raise ContractError("spatial primary receipt lacks its accepted provisional qualification")
    if not (spatial_verify.get("passed") and spatial_verify.get("qualified") and str(spatial_verify.get("verdict", "")).startswith("SUPPORTS")):
        raise ContractError("spatial independent receipt lacks its accepted qualified verdict")

    with np.load(PUMP_ARRAYS, allow_pickle=False) as data:
        required = {"fundamental", "witness_gaps", "witness_k"}
        if not required.issubset(data.files):
            raise ContractError("pump array schema is incomplete")
        gaps = np.asarray(data["witness_gaps"], dtype=np.int64)
        wave_numbers = np.asarray(data["witness_k"], dtype=np.float64)
        indices = np.flatnonzero(gaps == 3)
        if indices.size != 1 or abs(float(wave_numbers[indices[0]]) - K_STAR) > 1.0e-13:
            raise ContractError("unique accepted carrier witness is missing")
        carrier_matrix = np.asarray(data["fundamental"][indices[0], 0, -1], dtype=np.float64)
    with np.load(SPATIAL_ARRAYS, allow_pickle=False) as data:
        required = {"matrices", "p"}
        if not required.issubset(data.files):
            raise ContractError("spatial array schema is incomplete")
        p_values = np.asarray(data["p"], dtype=np.float64)
        indices = np.flatnonzero(np.isclose(p_values, P_STAR, rtol=0.0, atol=1.0e-13))
        if indices.size != 2 or int(indices[0]) != 2:
            raise ContractError("accepted spatial witness row is missing")
        mediator_matrix = np.asarray(data["matrices"][2, -1], dtype=np.float64)

    mediator_vector, mediator_multiplier = growing_vector(mediator_matrix)
    carrier_vector, carrier_multiplier = growing_vector(carrier_matrix)
    if not (finite(mediator_vector) and finite(carrier_vector)):
        raise ContractError("nonfinite growing eigenvector")

    output.mkdir(parents=True, exist_ok=False)
    copies = {
        "source_primary.py": Path(__file__).resolve(),
        "source_verifier.py": VERIFIER,
        "source_record.md": report,
        "parent_pump_results.json": PUMP_RESULTS,
        "parent_pump_verification.json": PUMP_VERIFY,
        "parent_pump_arrays.npz": PUMP_ARRAYS,
        "parent_spatial_results.json": SPATIAL_RESULTS,
        "parent_spatial_verification.json": SPATIAL_VERIFY,
        "parent_spatial_arrays.npz": SPATIAL_ARRAYS,
    }
    files: dict[str, str] = {}
    for name, source in copies.items():
        if not source.is_file():
            raise ContractError(f"missing source copy prerequisite: {source}")
        target = output / name
        shutil.copyfile(source, target)
        files[name] = sha256(target)
    protocol_path = output / "frozen_protocol.txt"
    protocol_path.write_text(protocol, encoding="utf-8", newline="\n")
    files["frozen_protocol.txt"] = sha256(protocol_path)
    for name, value in hashes.items():
        files[f"bound_{name}"] = value
    return files, mediator_vector, carrier_vector, mediator_multiplier, carrier_multiplier


def symbolic_checks() -> dict[str, Any]:
    c, a, kx, ur, h, uc, b = sp.symbols("c a kx ur h uc b", real=True)
    f, ft, fxx, ftt = sp.symbols("f ft fxx ftt", real=True)
    zr, zi = sp.symbols("zr zi", real=True)
    zrt, zit, zrxx, zixx, zrtt, zitt = sp.symbols(
        "zrt zit zrxx zixx zrtt zitt", real=True
    )
    radius = zr**2 + zi**2
    potential = b - h + h * f**2 + uc * radius
    af = (fxx - ur * (f**2 - 1) * f - 2 * h * f * radius) / c
    azr = (kx * zrxx / 2 - potential * zr) / a
    azi = (kx * zixx / 2 - potential * zi) / a
    energy_rate = (
        ft * (c * ftt - fxx + ur * (f**2 - 1) * f + 2 * h * f * radius)
        + 2 * zrt * (a * zrtt - kx * zrxx / 2 + potential * zr)
        + 2 * zit * (a * zitt - kx * zixx / 2 + potential * zi)
    )
    energy_residual = sp.simplify(energy_rate.subs({ftt: af, zrtt: azr, zitt: azi}))
    charge_bulk = sp.simplify(-2 * a * (zr * azi - zi * azr))
    charge_after_parts = sp.simplify(charge_bulk.subs({zr * zixx: -sp.Symbol("cross", real=True), zi * zrxx: -sp.Symbol("cross", real=True)}))
    alpha = sp.symbols("alpha", real=True)
    common_phase = sp.simplify((zr * (alpha * zrt) - (alpha * zr) * zrt))
    phase_seed_initial = sp.Integer(0)
    rows = {
        "energy": {"residual": str(energy_residual), "passed": bool(energy_residual == 0)},
        "charge": {"residual": str(charge_after_parts), "passed": bool(charge_after_parts == 0)},
        "common_phase": {"residual": str(common_phase), "passed": bool(common_phase == 0)},
        "phase_seed_initial": {"residual": str(phase_seed_initial), "passed": True},
    }
    rows["passed"] = bool(all(row["passed"] for row in rows.values() if isinstance(row, dict)))
    return rows


def initial_state(n: int, mediator_vector: np.ndarray, carrier_vector: np.ndarray) -> tuple[np.ndarray, ...]:
    x = LENGTH * np.arange(n, dtype=np.float64) / n
    c1 = np.cos(P_STAR * x)
    c4 = np.cos(4.0 * P_STAR * x)
    c5 = np.cos(5.0 * P_STAR * x)
    f = np.full((len(ARM_NAMES), n), F, dtype=np.float64)
    vf = np.zeros_like(f)
    z = np.zeros((len(ARM_NAMES), n), dtype=np.complex128)
    vz = np.zeros_like(z)

    z[0] = Z_SEED * carrier_vector[0] * c4
    vz[0] = Z_SEED * carrier_vector[1] * c4

    for arm in (1, 2, 3):
        f[arm] += F_SEED * mediator_vector[0] * c1
        vf[arm] += F_SEED * mediator_vector[1] * c1

    z[2] = Z_SEED * carrier_vector[0] * c4
    vz[2] = Z_SEED * carrier_vector[1] * c4
    z[3] = (Z_SEED / math.sqrt(2.0)) * (c4 + 1j * c5)

    f[4] = 1.0 + F_SEED * c1
    return x, f, vf, z, vz


def spectral_operators(n: int) -> tuple[float, np.ndarray]:
    dx = LENGTH / n
    wave = 2.0 * math.pi * np.fft.fftfreq(n, d=dx)
    return dx, wave


def accelerations(f: np.ndarray, z: np.ndarray, wave: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lap_f = np.fft.ifft(-(wave**2)[None, :] * np.fft.fft(f, axis=1), axis=1).real
    lap_z = np.fft.ifft(-(wave**2)[None, :] * np.fft.fft(z, axis=1), axis=1)
    radius = np.abs(z) ** 2
    af = (lap_f - U_RHO * (f**2 - 1.0) * f - 2.0 * H_C * f * radius) / C_PSI
    az = (0.5 * K_CX * lap_z - (B - H_C + H_C * f**2 + U_C * radius) * z) / A
    return af, az


def mode_coefficients(field: np.ndarray) -> np.ndarray:
    n = field.shape[1]
    values = 2.0 * np.fft.fft(field, axis=1) / n
    values[:, 0] *= 0.5
    return values


def energy_charge(
    f: np.ndarray,
    vf: np.ndarray,
    z: np.ndarray,
    vz: np.ndarray,
    dx: float,
    wave: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grad_f = np.fft.ifft((1j * wave)[None, :] * np.fft.fft(f, axis=1), axis=1).real
    grad_z = np.fft.ifft((1j * wave)[None, :] * np.fft.fft(z, axis=1), axis=1)
    radius = np.abs(z) ** 2
    density = (
        0.5 * C_PSI * vf**2
        + 0.5 * grad_f**2
        + A * np.abs(vz) ** 2
        + 0.5 * K_CX * np.abs(grad_z) ** 2
        + 0.25 * U_RHO * (f**2 - 1.0) ** 2
        + (B - H_C + H_C * f**2) * radius
        + 0.5 * U_C * radius**2
    )
    rho_q = -2.0 * A * np.imag(np.conj(z) * vz)
    return dx * np.sum(density, axis=1), dx * np.sum(rho_q, axis=1), dx * np.sum(np.abs(rho_q), axis=1)


def simulate(n: int, dt: float, mediator_vector: np.ndarray, carrier_vector: np.ndarray) -> dict[str, np.ndarray]:
    ratio = T_END / dt
    if abs(ratio - round(ratio)) > 1.0e-12:
        raise ContractError("time step does not divide stopping time")
    n_steps = int(round(ratio))
    sample_stride = int(round(SAMPLE_DT / dt))
    snapshot_stride = int(round(SNAPSHOT_DT / dt))
    if abs(sample_stride * dt - SAMPLE_DT) > 1.0e-15 or abs(snapshot_stride * dt - SNAPSHOT_DT) > 1.0e-15:
        raise ContractError("retention schedule is not integral")

    x, f, vf, z, vz = initial_state(n, mediator_vector, carrier_vector)
    dx, wave = spectral_operators(n)
    n_samples = n_steps // sample_stride + 1
    n_snapshots = n_steps // snapshot_stride + 1
    sample_t = np.empty(n_samples, dtype=np.float64)
    snap_t = np.empty(n_snapshots, dtype=np.float64)
    f_mode1 = np.empty((len(ARM_NAMES), n_samples), dtype=np.complex128)
    vf_mode1 = np.empty_like(f_mode1)
    z_mode4 = np.empty_like(f_mode1)
    vz_mode4 = np.empty_like(f_mode1)
    f_envelope = np.empty((len(ARM_NAMES), n_samples), dtype=np.float64)
    z_envelope = np.empty_like(f_envelope)
    energy = np.empty_like(f_envelope)
    charge = np.empty_like(f_envelope)
    local_charge = np.empty_like(f_envelope)
    f_spectrum = np.empty((len(ARM_NAMES), n_samples, 17), dtype=np.float64)
    z_spectrum = np.empty_like(f_spectrum)
    snap_shape = (len(ARM_NAMES), n_snapshots, n)
    snap_f = np.empty(snap_shape, dtype=np.float64)
    snap_vf = np.empty(snap_shape, dtype=np.float64)
    snap_zr = np.empty(snap_shape, dtype=np.float64)
    snap_zi = np.empty(snap_shape, dtype=np.float64)
    snap_vzr = np.empty(snap_shape, dtype=np.float64)
    snap_vzi = np.empty(snap_shape, dtype=np.float64)

    def retain_sample(index: int, time: float) -> None:
        fc = mode_coefficients(f)
        vfc = mode_coefficients(vf)
        zc = mode_coefficients(z)
        vzc = mode_coefficients(vz)
        sample_t[index] = time
        f_mode1[:, index] = fc[:, 1]
        vf_mode1[:, index] = vfc[:, 1]
        z_mode4[:, index] = zc[:, 4]
        vz_mode4[:, index] = vzc[:, 4]
        f_envelope[:, index] = np.sqrt(np.abs(fc[:, 1]) ** 2 + np.abs(vfc[:, 1] / OMEGA) ** 2)
        z_envelope[:, index] = np.sqrt(np.abs(zc[:, 4]) ** 2 + np.abs(vzc[:, 4] / OMEGA) ** 2)
        energy[:, index], charge[:, index], local_charge[:, index] = energy_charge(f, vf, z, vz, dx, wave)
        f_spectrum[:, index] = np.abs(fc[:, :17])
        z_spectrum[:, index] = np.abs(zc[:, :17])

    def retain_snapshot(index: int, time: float) -> None:
        snap_t[index] = time
        snap_f[:, index] = f
        snap_vf[:, index] = vf
        snap_zr[:, index] = z.real
        snap_zi[:, index] = z.imag
        snap_vzr[:, index] = vz.real
        snap_vzi[:, index] = vz.imag

    retain_sample(0, 0.0)
    retain_snapshot(0, 0.0)
    sample_index = 1
    snapshot_index = 1
    af, az = accelerations(f, z, wave)
    for step in range(1, n_steps + 1):
        vf_half = vf + 0.5 * dt * af
        vz_half = vz + 0.5 * dt * az
        f = f + dt * vf_half
        z = z + dt * vz_half
        af, az = accelerations(f, z, wave)
        vf = vf_half + 0.5 * dt * af
        vz = vz_half + 0.5 * dt * az
        if step % sample_stride == 0:
            retain_sample(sample_index, step * dt)
            sample_index += 1
        if step % snapshot_stride == 0:
            retain_snapshot(snapshot_index, step * dt)
            snapshot_index += 1
    if sample_index != n_samples or snapshot_index != n_snapshots:
        raise ContractError("retention count mismatch")
    return {
        "x": x,
        "t": sample_t,
        "snapshot_t": snap_t,
        "f_mode1": f_mode1,
        "vf_mode1": vf_mode1,
        "z_mode4": z_mode4,
        "vz_mode4": vz_mode4,
        "f_envelope": f_envelope,
        "z_envelope": z_envelope,
        "energy": energy,
        "charge": charge,
        "local_charge_l1": local_charge,
        "f_spectrum": f_spectrum,
        "z_spectrum": z_spectrum,
        "snapshot_f": snap_f,
        "snapshot_vf": snap_vf,
        "snapshot_z_real": snap_zr,
        "snapshot_z_imag": snap_zi,
        "snapshot_vz_real": snap_vzr,
        "snapshot_vz_imag": snap_vzi,
    }


def first_crossing(t: np.ndarray, values: np.ndarray, threshold: float) -> float | None:
    hits = np.flatnonzero(values >= threshold)
    if hits.size == 0:
        return None
    index = int(hits[0])
    if index == 0:
        return float(t[0])
    y0 = float(values[index - 1])
    y1 = float(values[index])
    if y1 == y0:
        return float(t[index])
    fraction = (threshold - y0) / (y1 - y0)
    return float(t[index - 1] + fraction * (t[index] - t[index - 1]))


def interpolate_at(t: np.ndarray, values: np.ndarray, target: float | None) -> float | None:
    if target is None:
        return None
    return float(np.interp(target, t, values))


def fitted_slope(t: np.ndarray, envelope: np.ndarray) -> tuple[float, int]:
    mask = (envelope >= 2.0e-3) & (envelope <= 2.0e-2)
    count = int(np.count_nonzero(mask))
    if count < 10:
        return float("nan"), count
    slope = float(np.polyfit(t[mask], np.log(envelope[mask]), 1)[0])
    return slope, count


def exact_carrier_reference(t: np.ndarray, carrier_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    initial = Z_SEED * carrier_vector

    def rhs(time: float, state: np.ndarray) -> np.ndarray:
        dn = float(special.ellipj(OMEGA * time, M)[2])
        f0 = F * dn
        frequency2 = (
            K_CX * K_STAR**2 / (2.0 * A)
            + 1.0 / (4.0 * A**2)
            + (E_C - H_C + H_C * f0**2) / A
        )
        return np.asarray((state[1], -frequency2 * state[0]), dtype=np.float64)

    solution = integrate.solve_ivp(
        rhs,
        (0.0, T_END),
        initial,
        method="DOP853",
        t_eval=t,
        rtol=2.0e-12,
        atol=2.0e-14,
        max_step=float(2.0 * special.ellipk(M) / OMEGA / 128.0),
    )
    if not solution.success or solution.y.shape[1] != t.size or not finite(solution.y):
        raise ContractError(f"exact carrier reference failed: {solution.message}")
    return solution.y[0], solution.y[1]


def resolution_metrics(data: dict[str, np.ndarray], carrier_vector: np.ndarray) -> dict[str, Any]:
    t = data["t"]
    energy = data["energy"]
    energy_drift = np.max(np.abs(energy - energy[:, :1]), axis=1) / np.maximum(1.0, np.abs(energy[:, 0]))
    ref_y, ref_v = exact_carrier_reference(t, carrier_vector)
    carrier_error = np.max(
        np.sqrt(
            np.abs(data["z_mode4"][0] - ref_y) ** 2
            + np.abs((data["vz_mode4"][0] - ref_v) / OMEGA) ** 2
        )
    ) / Z_SEED
    slopes: dict[str, dict[str, Any]] = {}
    entries: dict[str, float | None] = {}
    for arm in ("mediator_only", "competition", "phase_seed"):
        index = ARM_NAMES.index(arm)
        slope, count = fitted_slope(t, data["f_envelope"][index])
        slopes[arm] = {
            "value": slope,
            "samples": count,
            "relative_error": abs(slope - MU_F) / MU_F if math.isfinite(slope) else None,
        }
        entries[arm] = first_crossing(t, data["f_envelope"][index], F_TARGET)
    competition_index = ARM_NAMES.index("competition")
    carrier_crossing = first_crossing(t, data["z_envelope"][competition_index], Z_TARGET)
    carrier_at_entry = interpolate_at(t, data["z_envelope"][competition_index], entries["competition"])
    phase_index = ARM_NAMES.index("phase_seed")
    charge_scale = 2.0 * A * OMEGA * LENGTH * 1.0e-12
    phase_charge_drift = float(np.max(np.abs(data["charge"][phase_index] - data["charge"][phase_index, 0])) / max(charge_scale, abs(float(data["charge"][phase_index, 0]))))
    phase_local_max = float(np.max(data["local_charge_l1"][phase_index]) / charge_scale)
    equilibrium_max = float(np.max(data["f_envelope"][ARM_NAMES.index("equilibrium_control")]))
    final_spectrum = data["f_spectrum"][competition_index, -1]
    broadband = float(np.sum(final_spectrum[2:] ** 2) / max(np.sum(final_spectrum[1:] ** 2), np.finfo(float).tiny))
    return {
        "energy_drift": energy_drift.tolist(),
        "max_energy_drift": float(np.max(energy_drift)),
        "carrier_reference_error": float(carrier_error),
        "equilibrium_max_envelope": equilibrium_max,
        "slopes": slopes,
        "mediator_entry_times": entries,
        "carrier_comparison_time": carrier_crossing,
        "carrier_at_mediator_entry": carrier_at_entry,
        "phase_global_charge_drift": phase_charge_drift,
        "phase_local_charge_max": phase_local_max,
        "late_broadband_fraction": broadband,
        "initial_energy": energy[:, 0].tolist(),
        "final_energy": energy[:, -1].tolist(),
    }


def relative_time_error(left: float | None, right: float | None) -> float:
    if left is None or right is None:
        return float("inf")
    return abs(left - right) / max(abs(left), abs(right), np.finfo(float).tiny)


def save_arrays(path: Path, arrays: dict[str, np.ndarray]) -> str:
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return sha256(path)


def run(output: Path, report: Path) -> int:
    if output.exists():
        raise ContractError("output directory must be absent before invocation")
    receipt = initial_receipt()
    retained: dict[str, np.ndarray] = {}
    try:
        files, mediator_vector, carrier_vector, mediator_multiplier, carrier_multiplier = source_stage(output, report)
        receipt["files"].update(files)
        receipt["scientific_execution_started"] = True
        receipt["parameters"] = {
            "a": A,
            "cPsi": C_PSI,
            "uRho": U_RHO,
            "uC": U_C,
            "kCx": K_CX,
            "eC": E_C,
            "hC": H_C,
            "B": B,
            "m": M,
            "Omega": OMEGA,
            "F": F,
            "kstar": K_STAR,
            "pstar": P_STAR,
            "L": LENGTH,
            "mu_f": MU_F,
            "mu_z": MU_Z,
            "f_seed": F_SEED,
            "z_seed": Z_SEED,
            "f_target": F_TARGET,
            "z_target": Z_TARGET,
            "t_end": T_END,
            "sample_dt": SAMPLE_DT,
            "snapshot_dt": SNAPSHOT_DT,
            "arms": list(ARM_NAMES),
        }
        receipt["eigenvectors"] = {
            "mediator": mediator_vector.tolist(),
            "mediator_multiplier": mediator_multiplier,
            "carrier": carrier_vector.tolist(),
            "carrier_multiplier": carrier_multiplier,
        }
        symbolic = symbolic_checks()
        receipt["symbolic"] = symbolic

        schedules = (("coarse", 256, 2.0**-11), ("fine", 512, 2.0**-12))
        metrics_by_name: dict[str, dict[str, Any]] = {}
        for name, n, dt in schedules:
            data = simulate(n, dt, mediator_vector, carrier_vector)
            metrics = resolution_metrics(data, carrier_vector)
            metrics_by_name[name] = metrics
            receipt["resolutions"].append({"name": name, "N": n, "dt": dt, "metrics": metrics})
            for key, value in data.items():
                retained[f"{name}_{key}"] = value

        coarse = metrics_by_name["coarse"]
        fine = metrics_by_name["fine"]
        finite_arrays = bool(all(finite(value) for value in retained.values()))
        slope_ok = bool(
            all(
                row["relative_error"] is not None and row["relative_error"] < 0.02
                for metrics in (coarse, fine)
                for row in (metrics["slopes"]["mediator_only"], metrics["slopes"]["competition"])
            )
        )
        event_errors = {
            arm: relative_time_error(
                coarse["mediator_entry_times"][arm], fine["mediator_entry_times"][arm]
            )
            for arm in ("mediator_only", "competition")
        }
        coarse_fine_ok = bool(all(value < 0.01 for value in event_errors.values()))
        fine_internal_error = relative_time_error(
            fine["mediator_entry_times"]["mediator_only"], fine["mediator_entry_times"]["competition"]
        )
        carrier_time = fine["carrier_comparison_time"]
        mediator_time = fine["mediator_entry_times"]["competition"]
        carrier_later = bool(mediator_time is not None and (carrier_time is None or carrier_time > mediator_time))
        carrier_below = bool(
            fine["carrier_at_mediator_entry"] is not None
            and fine["carrier_at_mediator_entry"] < Z_TARGET
        )
        mediator_first = bool(
            fine["mediator_entry_times"]["mediator_only"] is not None
            and mediator_time is not None
            and carrier_later
            and carrier_below
            and fine_internal_error < 0.01
        )
        numerical_qualification = bool(
            finite_arrays
            and symbolic["passed"]
            and fine["max_energy_drift"] < 2.0e-6
            and fine["carrier_reference_error"] < 2.0e-4
            and fine["equilibrium_max_envelope"] < 2.0e-3
            and fine["phase_global_charge_drift"] < 1.0e-9
            and fine["phase_local_charge_max"] >= 0.05
            and slope_ok
            and coarse_fine_ok
        )
        receipt["checks"] = {
            "prerequisites": True,
            "symbolic": bool(symbolic["passed"]),
            "finite_arrays": finite_arrays,
            "fine_energy": bool(fine["max_energy_drift"] < 2.0e-6),
            "carrier_reference": bool(fine["carrier_reference_error"] < 2.0e-4),
            "equilibrium_control": bool(fine["equilibrium_max_envelope"] < 2.0e-3),
            "global_charge": bool(fine["phase_global_charge_drift"] < 1.0e-9),
            "local_charge_transport": bool(fine["phase_local_charge_max"] >= 0.05),
            "linear_slopes": slope_ok,
            "coarse_fine_entry_times": coarse_fine_ok,
            "mediator_only_competition": bool(fine_internal_error < 0.01),
            "mediator_first": mediator_first,
            "all_qualifications": numerical_qualification,
        }
        linear_f_time = math.log(F_TARGET / F_SEED) / MU_F
        linear_z_time = math.log(Z_TARGET / Z_SEED) / MU_Z
        selection_floor = F_TARGET * (Z_SEED / Z_TARGET) ** (MU_F / MU_Z)
        receipt["diagnostics"] = {
            "coarse_fine_entry_relative_errors": event_errors,
            "fine_mediator_only_competition_relative_error": fine_internal_error,
            "linear_mediator_time": linear_f_time,
            "linear_carrier_time": linear_z_time,
            "selection_floor": selection_floor,
            "growth_rate_ratio": MU_F / MU_Z,
            "primary_scientific_condition": "mediator_first" if mediator_first else (
                "carrier_first" if carrier_time is not None and (mediator_time is None or carrier_time < mediator_time) else "unresolved"
            ),
        }
        receipt["qualified"] = numerical_qualification
        if numerical_qualification:
            receipt["verdict"] = "INCONCLUSIVE—awaiting independent nonlinear qualification"
        else:
            receipt["verdict"] = "INCONCLUSIVE"

        receipt["files"]["arrays.npz"] = save_arrays(output / "arrays.npz", retained)
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["verdict"] = "INCONCLUSIVE"
        receipt["passed"] = False
        receipt["qualified"] = False
    if not output.exists():
        output.mkdir(parents=True, exist_ok=False)
    dump_json(output / "results.json", receipt)
    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "qualified": receipt["qualified"],
                "error": receipt["error"],
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0 if receipt["qualified"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=REPORT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        return 1
    try:
        return run(output, args.record.resolve())
    except Exception as exc:
        if output.exists():
            return 1
        output.mkdir(parents=True, exist_ok=False)
        receipt = initial_receipt()
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        dump_json(output / "results.json", receipt)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
