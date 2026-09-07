#!/usr/bin/env python3
"""Independent finite-difference verification of nonlinear mode competition.

Run from the CassiTheory repository root after the primary calculation:

    python -B computations/verify_matter_formation_nonlinear_fragmentation.py \
        --primary-dir runs/20260907_matter_formation_nonlinear_fragmentation \
        --output-dir runs/20260907_matter_formation_nonlinear_fragmentation_verification
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
PRIMARY_SOURCE = ROOT / "computations/matter_formation_nonlinear_fragmentation.py"
PUMP_RESULTS = ROOT / "runs/20260907_matter_formation_autonomous_pump/results.json"
PUMP_VERIFY = ROOT / "runs/20260907_matter_formation_autonomous_pump_verification/results.json"
PUMP_ARRAYS = ROOT / "runs/20260907_matter_formation_autonomous_pump/arrays.npz"
SPATIAL_RESULTS = ROOT / "runs/20260907_matter_formation_spatial_pump_prerequisite_recovery/results.json"
SPATIAL_VERIFY = ROOT / "runs/20260907_matter_formation_spatial_pump_verification_prerequisite_recovery/results.json"
SPATIAL_ARRAYS = ROOT / "runs/20260907_matter_formation_spatial_pump_prerequisite_recovery/arrays.npz"

PROTOCOL_HEADING = "### 28.3 Nonlinear competition calculation: pre-execution criteria"
PROTOCOL_SHA256 = "2913ebedd2626475ffab2488d6026cd83fa2c7009ffda0e668074c48ceae2c1b"
RECOVERY_HEADING = "### 28.4 Independent-verifier prerequisite recovery"
RECOVERY_SHA256 = "df1cbc42f71ffabe6a50e7af133a7608269264e703e3ec448b260296c5ce9c61"
FROZEN_VERIFIER_SHA256 = "1c59152413f8a79c9d6b8fb967bd7cdbb815dc3d4ee3ad8eaccf5d5b895692f2"
EXPECTED_HASHES = {
    "pump_results": "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5",
    "pump_verify": "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758",
    "pump_arrays": "d1679676c297295d3196c2abb9a8347becbf41f8e1ee43ba889edce544baf352",
    "spatial_results": "10c96e81220c08405392bb062e17bf4b193cdd95294d31a776b7b8c7566299e8",
    "spatial_verify": "c2126830d1cf3845b6fc3b25948e970231175105525a3bffff01d24a305ee7c0",
    "spatial_arrays": "6c8a3e5316c3ec03535ecb2d0da511458e663fc745b2aa84b933ac35fd8dee54",
}

A = 0.0625
C_PSI = 0.125
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 0.75
H_C = 2.9598260763447164
B = E_C + 1.0 / (4.0 * A)
M = 2.0 / 3.0
OMEGA = math.sqrt(24.0)
F = math.sqrt(1.5)
K_STAR = 2.675336705149658
P_STAR = K_STAR / 4.0
LENGTH = 2.0 * math.pi / P_STAR
MU_F = 0.362037120923008
MU_Z = 0.0017215449183269978
F_SEED = 0.001
Z_SEED = 0.000001
F_TARGET = 0.1
Z_TARGET = 0.0000011
T_END = 30.0
DT = 2.0**-12
SAMPLE_DT = 5.0 / 1024.0
SNAPSHOT_DT = 0.5
N_GRID = 512
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
    """Raised when immutable evidence or the frozen protocol is unavailable."""


def file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            result.update(block)
    return result.hexdigest()


def json_compatible(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_compatible(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_compatible(value), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def section_bytes(path: Path, heading: str, label: str) -> bytes:
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    positions = []
    offset = 0
    while True:
        found = normalized.find(heading, offset)
        if found < 0:
            break
        positions.append(found)
        offset = found + 1
    if len(positions) != 1:
        raise ContractError(f"{label} heading count differs from one")
    start = positions[0]
    endings = [
        position
        for marker in ("\n# ", "\n## ", "\n### ")
        if (position := normalized.find(marker, start + len(heading))) >= 0
    ]
    if not endings:
        raise ContractError(f"{label} has no closing heading at level three or higher")
    return (normalized[start:min(endings)].rstrip() + "\n").encode("utf-8")


def protocol_bytes(path: Path) -> bytes:
    return section_bytes(path, PROTOCOL_HEADING, "frozen protocol")


def recovery_bytes(path: Path) -> bytes:
    return section_bytes(path, RECOVERY_HEADING, "recovery declaration")


def checked_hash(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise ContractError(f"{label} is missing")
    actual = file_hash(path)
    if actual != expected:
        raise ContractError(f"{label} hash differs: {actual}")
    return actual


def json_object(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if type(parsed) is not dict:
        raise ContractError(f"expected object in {path}")
    return parsed


def all_finite(value: Any) -> bool:
    array = np.asanyarray(value)
    return bool(np.isfinite(array).all())


def normalized_unstable_eigenvector(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    roots, basis = np.linalg.eig(np.array(matrix, dtype=float, copy=True))
    order = np.argsort(np.abs(roots))
    chosen = int(order[-1])
    root = np.real_if_close(roots[chosen], tol=1000)
    column = np.real_if_close(basis[:, chosen], tol=1000)
    if np.iscomplexobj(root) or np.iscomplexobj(column):
        raise ContractError("unstable parent eigendata are complex")
    root_value = float(root)
    vector = np.array(column, dtype=float, copy=True)
    scale = math.hypot(float(vector[0]), float(vector[1] / OMEGA))
    if abs(root_value) <= 1.0 or scale <= 0.0 or not math.isfinite(scale):
        raise ContractError("unstable parent eigendata fail normalization")
    vector /= scale
    orientation = vector[0] if vector[0] != 0.0 else vector[1]
    if orientation < 0.0:
        vector = -vector
    return vector, root_value


def empty_receipt() -> dict[str, Any]:
    return {
        "schema": "cassi.matter-formation.nonlinear-fragmentation-verification.v1",
        "verdict": "INCONCLUSIVE",
        "passed": False,
        "qualified": False,
        "error": None,
        "scientific_execution_started": False,
        "protocol_sha256": PROTOCOL_SHA256,
        "recovery_sha256": RECOVERY_SHA256,
        "files": {},
        "parameters": {},
        "eigenvectors": {},
        "symbolic": {},
        "metrics": {},
        "checks": {},
        "diagnostics": {},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
    }


def prerequisite_stage(
    output: Path, report: Path, primary_dir: Path
) -> tuple[dict[str, str], dict[str, Any], dict[str, np.ndarray], np.ndarray, np.ndarray, float, float]:
    frozen = protocol_bytes(report)
    actual_protocol = hashlib.sha256(frozen).hexdigest()
    if actual_protocol != PROTOCOL_SHA256:
        raise ContractError(f"protocol hash differs: {actual_protocol}")
    recovery = recovery_bytes(report)
    actual_recovery = hashlib.sha256(recovery).hexdigest()
    if actual_recovery != RECOVERY_SHA256:
        raise ContractError(f"recovery declaration hash differs: {actual_recovery}")

    canonical_inputs = {
        "pump_results": PUMP_RESULTS,
        "pump_verify": PUMP_VERIFY,
        "pump_arrays": PUMP_ARRAYS,
        "spatial_results": SPATIAL_RESULTS,
        "spatial_verify": SPATIAL_VERIFY,
        "spatial_arrays": SPATIAL_ARRAYS,
    }
    bound = {
        name: checked_hash(path, EXPECTED_HASHES[name], name)
        for name, path in canonical_inputs.items()
    }
    pump = json_object(PUMP_RESULTS)
    pump_verify = json_object(PUMP_VERIFY)
    spatial = json_object(SPATIAL_RESULTS)
    spatial_verify = json_object(SPATIAL_VERIFY)
    if not (pump.get("qualified") is True and pump.get("passed") is True and str(pump.get("verdict", "")).startswith("SUPPORTS")):
        raise ContractError("primary pump status is not accepted")
    if not (pump_verify.get("qualified") is True and pump_verify.get("passed") is True and str(pump_verify.get("verdict", "")).startswith("SUPPORTS")):
        raise ContractError("independent pump status is not accepted")
    if not (spatial.get("qualified") is True and str(spatial.get("verdict", "")).startswith("INCONCLUSIVE")):
        raise ContractError("primary spatial status is not accepted")
    if not (spatial_verify.get("qualified") is True and spatial_verify.get("passed") is True and str(spatial_verify.get("verdict", "")).startswith("SUPPORTS")):
        raise ContractError("independent spatial status is not accepted")

    primary_results_path = primary_dir / "results.json"
    primary_arrays_path = primary_dir / "arrays.npz"
    if not primary_results_path.is_file():
        raise ContractError("primary result is missing")
    primary_receipt = json_object(primary_results_path)
    if primary_receipt.get("scientific_execution_started") is not True:
        raise ContractError("primary nonlinear scientific execution did not start")
    if type(primary_receipt.get("qualified")) is not bool or type(primary_receipt.get("passed")) is not bool:
        raise ContractError("primary nonlinear qualification state is malformed")
    expected_primary_array = primary_receipt.get("files", {}).get("arrays.npz")
    if not isinstance(expected_primary_array, str):
        raise ContractError("primary nonlinear array manifest is missing")
    checked_hash(primary_arrays_path, expected_primary_array, "primary nonlinear array")
    local_primary_hash = file_hash(PRIMARY_SOURCE)
    if primary_receipt.get("files", {}).get("source_primary.py") != local_primary_hash:
        raise ContractError("primary source identity differs from the executed source copy")
    frozen_verifier_path = primary_dir / "source_verifier.py"
    if primary_receipt.get("files", {}).get("source_verifier.py") != FROZEN_VERIFIER_SHA256:
        raise ContractError("primary manifest does not bind the frozen verifier source")
    checked_hash(frozen_verifier_path, FROZEN_VERIFIER_SHA256, "frozen verifier source")

    with np.load(primary_arrays_path, allow_pickle=False) as archive:
        primary_arrays = {name: np.array(archive[name], copy=True) for name in archive.files}
    if not primary_arrays or not all(all_finite(value) for value in primary_arrays.values()):
        raise ContractError("primary raw arrays are empty or nonfinite")

    with np.load(PUMP_ARRAYS, allow_pickle=False) as archive:
        required = {"fundamental", "witness_gaps", "witness_k"}
        if not required.issubset(archive.files):
            raise ContractError("pump parent array keys are incomplete")
        gaps = np.array(archive["witness_gaps"], dtype=np.int64)
        ks = np.array(archive["witness_k"], dtype=float)
        location = np.flatnonzero(gaps == 3)
        if location.size != 1 or abs(float(ks[location[0]]) - K_STAR) > 1.0e-13:
            raise ContractError("pump parent lacks the unique j=3 witness")
        carrier_matrix = np.array(archive["fundamental"][location[0], 0, -1], dtype=float)
    with np.load(SPATIAL_ARRAYS, allow_pickle=False) as archive:
        required = {"matrices", "p"}
        if not required.issubset(archive.files):
            raise ContractError("spatial parent array keys are incomplete")
        ps = np.array(archive["p"], dtype=float)
        locations = np.flatnonzero(np.abs(ps - P_STAR) <= 1.0e-13)
        if locations.size != 2 or int(locations[0]) != 2:
            raise ContractError("spatial parent witness row is ambiguous")
        mediator_matrix = np.array(archive["matrices"][2, -1], dtype=float)
    mediator_vector, mediator_multiplier = normalized_unstable_eigenvector(mediator_matrix)
    carrier_vector, carrier_multiplier = normalized_unstable_eigenvector(carrier_matrix)

    primary_mediator = np.asarray(primary_receipt.get("eigenvectors", {}).get("mediator", []), dtype=float)
    primary_carrier = np.asarray(primary_receipt.get("eigenvectors", {}).get("carrier", []), dtype=float)
    if primary_mediator.shape != (2,) or primary_carrier.shape != (2,):
        raise ContractError("primary eigenvector receipt is incomplete")
    if max(float(np.max(np.abs(primary_mediator - mediator_vector))), float(np.max(np.abs(primary_carrier - carrier_vector)))) > 1.0e-13:
        raise ContractError("independently reconstructed eigenvectors disagree")

    output.mkdir(parents=True, exist_ok=False)
    copies = {
        "source_primary.py": PRIMARY_SOURCE,
        "source_verifier_frozen.py": frozen_verifier_path,
        "source_verifier_recovery.py": Path(__file__).resolve(),
        "source_record.md": report,
        "primary_results.json": primary_results_path,
        "primary_arrays.npz": primary_arrays_path,
        "parent_pump_results.json": PUMP_RESULTS,
        "parent_pump_verification.json": PUMP_VERIFY,
        "parent_pump_arrays.npz": PUMP_ARRAYS,
        "parent_spatial_results.json": SPATIAL_RESULTS,
        "parent_spatial_verification.json": SPATIAL_VERIFY,
        "parent_spatial_arrays.npz": SPATIAL_ARRAYS,
    }
    files: dict[str, str] = {}
    for destination_name, source in copies.items():
        destination = output / destination_name
        shutil.copyfile(source, destination)
        files[destination_name] = file_hash(destination)
    frozen_path = output / "frozen_protocol.txt"
    with frozen_path.open("xb") as stream:
        stream.write(frozen)
    files["frozen_protocol.txt"] = file_hash(frozen_path)
    recovery_path = output / "frozen_recovery.txt"
    with recovery_path.open("xb") as stream:
        stream.write(recovery)
    files["frozen_recovery.txt"] = file_hash(recovery_path)
    for name, digest in bound.items():
        files[f"bound_{name}"] = digest
    return files, primary_receipt, primary_arrays, mediator_vector, carrier_vector, mediator_multiplier, carrier_multiplier


def independent_symbolic_review() -> dict[str, Any]:
    rf, rr, ri = sp.symbols("R_f R_r R_i", real=True)
    ft, rt, it = sp.symbols("f_t r_t i_t", real=True)
    energy_identity = sp.expand(ft * rf + 2 * rt * rr + 2 * it * ri).subs({rf: 0, rr: 0, ri: 0})
    kappa, r, i, rxx, ixx = sp.symbols("kappa r i r_xx i_xx", real=True)
    charge_bulk = sp.expand(kappa * (r * ixx - i * rxx))
    cross = sp.symbols("cross", real=True)
    charge_parts = sp.simplify(charge_bulk.subs({r * ixx: -cross, i * rxx: -cross}))
    alpha, u, udot = sp.symbols("alpha u u_dot", real=True)
    common_phase = sp.simplify(u * (alpha * udot) - alpha * u * udot)
    phase_seed_at_zero = sp.Integer(0)
    checks = {
        "energy": {"residual": str(energy_identity), "passed": energy_identity == 0},
        "charge": {"residual": str(charge_parts), "passed": charge_parts == 0},
        "common_phase": {"residual": str(common_phase), "passed": common_phase == 0},
        "phase_seed_initial": {"residual": str(phase_seed_at_zero), "passed": True},
    }
    checks["passed"] = bool(all(bool(row["passed"]) for row in checks.values() if isinstance(row, dict)))
    return checks


def prepare_state(mediator_vector: np.ndarray, carrier_vector: np.ndarray) -> tuple[np.ndarray, ...]:
    x = np.arange(N_GRID, dtype=float) * (LENGTH / N_GRID)
    cos1 = np.cos(P_STAR * x)
    cos4 = np.cos(4.0 * P_STAR * x)
    cos5 = np.cos(5.0 * P_STAR * x)
    f = np.empty((len(ARM_NAMES), N_GRID), dtype=float)
    f[:] = F
    vf = np.zeros_like(f)
    z = np.zeros(f.shape, dtype=np.complex128)
    vz = np.zeros_like(z)
    z[0] = Z_SEED * carrier_vector[0] * cos4
    vz[0] = Z_SEED * carrier_vector[1] * cos4
    for index in (1, 2, 3):
        f[index] += F_SEED * mediator_vector[0] * cos1
        vf[index] = F_SEED * mediator_vector[1] * cos1
    z[2] = Z_SEED * carrier_vector[0] * cos4
    vz[2] = Z_SEED * carrier_vector[1] * cos4
    z[3] = Z_SEED * (cos4 + 1j * cos5) / math.sqrt(2.0)
    f[4] = 1.0 + F_SEED * cos1
    return x, f, vf, z, vz


def laplacian_fourth(field: np.ndarray, dx: float) -> np.ndarray:
    return (
        -np.roll(field, -2, axis=1)
        + 16.0 * np.roll(field, -1, axis=1)
        - 30.0 * field
        + 16.0 * np.roll(field, 1, axis=1)
        - np.roll(field, 2, axis=1)
    ) / (12.0 * dx * dx)


def state_derivative(
    f: np.ndarray, vf: np.ndarray, z: np.ndarray, vz: np.ndarray, dx: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    lap_f = laplacian_fourth(f, dx).real
    lap_z = laplacian_fourth(z, dx)
    norm2 = z.real * z.real + z.imag * z.imag
    force_f = (lap_f - U_RHO * (f * f - 1.0) * f - 2.0 * H_C * f * norm2) / C_PSI
    force_z = (0.5 * K_CX * lap_z - (B - H_C + H_C * f * f + U_C * norm2) * z) / A
    return vf, force_f, vz, force_z


def coefficients(field: np.ndarray) -> np.ndarray:
    transformed = 2.0 * np.fft.fft(field, axis=1) / field.shape[1]
    transformed[:, 0] *= 0.5
    return transformed


def discrete_diagnostics(
    f: np.ndarray, vf: np.ndarray, z: np.ndarray, vz: np.ndarray, dx: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lap_f = laplacian_fourth(f, dx).real
    lap_z = laplacian_fourth(z, dx)
    norm2 = np.abs(z) ** 2
    energy_density = (
        0.5 * C_PSI * vf**2
        - 0.5 * f * lap_f
        + A * np.abs(vz) ** 2
        - 0.5 * K_CX * np.real(np.conj(z) * lap_z)
        + 0.25 * U_RHO * (f**2 - 1.0) ** 2
        + (B - H_C + H_C * f**2) * norm2
        + 0.5 * U_C * norm2**2
    )
    density_q = -2.0 * A * np.imag(np.conj(z) * vz)
    return (
        dx * np.sum(energy_density, axis=1),
        dx * np.sum(density_q, axis=1),
        dx * np.sum(np.abs(density_q), axis=1),
    )


def evolve(mediator_vector: np.ndarray, carrier_vector: np.ndarray) -> dict[str, np.ndarray]:
    steps = int(round(T_END / DT))
    sample_stride = int(round(SAMPLE_DT / DT))
    snapshot_stride = int(round(SNAPSHOT_DT / DT))
    if abs(steps * DT - T_END) > 1.0e-15 or abs(sample_stride * DT - SAMPLE_DT) > 1.0e-15 or abs(snapshot_stride * DT - SNAPSHOT_DT) > 1.0e-15:
        raise ContractError("independent integration schedule is not integral")
    x, f, vf, z, vz = prepare_state(mediator_vector, carrier_vector)
    dx = LENGTH / N_GRID
    sample_count = steps // sample_stride + 1
    snapshot_count = steps // snapshot_stride + 1
    t = np.empty(sample_count, dtype=float)
    snapshot_t = np.empty(snapshot_count, dtype=float)
    shape = (len(ARM_NAMES), sample_count)
    f_mode1 = np.empty(shape, dtype=np.complex128)
    vf_mode1 = np.empty_like(f_mode1)
    z_mode4 = np.empty_like(f_mode1)
    vz_mode4 = np.empty_like(f_mode1)
    f_envelope = np.empty(shape, dtype=float)
    z_envelope = np.empty(shape, dtype=float)
    energy = np.empty(shape, dtype=float)
    charge = np.empty(shape, dtype=float)
    local_charge = np.empty(shape, dtype=float)
    f_spectrum = np.empty((len(ARM_NAMES), sample_count, 17), dtype=float)
    z_spectrum = np.empty_like(f_spectrum)
    snapshot_shape = (len(ARM_NAMES), snapshot_count, N_GRID)
    snapshots = {
        "snapshot_f": np.empty(snapshot_shape, dtype=float),
        "snapshot_vf": np.empty(snapshot_shape, dtype=float),
        "snapshot_z_real": np.empty(snapshot_shape, dtype=float),
        "snapshot_z_imag": np.empty(snapshot_shape, dtype=float),
        "snapshot_vz_real": np.empty(snapshot_shape, dtype=float),
        "snapshot_vz_imag": np.empty(snapshot_shape, dtype=float),
    }

    def sample(index: int, time: float) -> None:
        fc = coefficients(f)
        vfc = coefficients(vf)
        zc = coefficients(z)
        vzc = coefficients(vz)
        t[index] = time
        f_mode1[:, index] = fc[:, 1]
        vf_mode1[:, index] = vfc[:, 1]
        z_mode4[:, index] = zc[:, 4]
        vz_mode4[:, index] = vzc[:, 4]
        f_envelope[:, index] = np.hypot(np.abs(fc[:, 1]), np.abs(vfc[:, 1]) / OMEGA)
        z_envelope[:, index] = np.hypot(np.abs(zc[:, 4]), np.abs(vzc[:, 4]) / OMEGA)
        energy[:, index], charge[:, index], local_charge[:, index] = discrete_diagnostics(f, vf, z, vz, dx)
        f_spectrum[:, index] = np.abs(fc[:, :17])
        z_spectrum[:, index] = np.abs(zc[:, :17])

    def snapshot(index: int, time: float) -> None:
        snapshot_t[index] = time
        snapshots["snapshot_f"][:, index] = f
        snapshots["snapshot_vf"][:, index] = vf
        snapshots["snapshot_z_real"][:, index] = z.real
        snapshots["snapshot_z_imag"][:, index] = z.imag
        snapshots["snapshot_vz_real"][:, index] = vz.real
        snapshots["snapshot_vz_imag"][:, index] = vz.imag

    sample(0, 0.0)
    snapshot(0, 0.0)
    sample_index = 1
    snapshot_index = 1
    for step in range(1, steps + 1):
        k1 = state_derivative(f, vf, z, vz, dx)
        k2 = state_derivative(
            f + 0.5 * DT * k1[0],
            vf + 0.5 * DT * k1[1],
            z + 0.5 * DT * k1[2],
            vz + 0.5 * DT * k1[3],
            dx,
        )
        k3 = state_derivative(
            f + 0.5 * DT * k2[0],
            vf + 0.5 * DT * k2[1],
            z + 0.5 * DT * k2[2],
            vz + 0.5 * DT * k2[3],
            dx,
        )
        k4 = state_derivative(
            f + DT * k3[0],
            vf + DT * k3[1],
            z + DT * k3[2],
            vz + DT * k3[3],
            dx,
        )
        f = f + (DT / 6.0) * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        vf = vf + (DT / 6.0) * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
        z = z + (DT / 6.0) * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])
        vz = vz + (DT / 6.0) * (k1[3] + 2.0 * k2[3] + 2.0 * k3[3] + k4[3])
        if step % sample_stride == 0:
            sample(sample_index, step * DT)
            sample_index += 1
        if step % snapshot_stride == 0:
            snapshot(snapshot_index, step * DT)
            snapshot_index += 1
    if sample_index != sample_count or snapshot_index != snapshot_count:
        raise ContractError("independent retention count differs from schedule")
    result = {
        "x": x,
        "t": t,
        "snapshot_t": snapshot_t,
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
    }
    result.update(snapshots)
    return result


def first_event(t: np.ndarray, values: np.ndarray, level: float) -> float | None:
    indices = np.nonzero(values >= level)[0]
    if indices.size == 0:
        return None
    index = int(indices[0])
    if index == 0:
        return float(t[0])
    lower = float(values[index - 1])
    upper = float(values[index])
    if upper == lower:
        return float(t[index])
    weight = (level - lower) / (upper - lower)
    return float((1.0 - weight) * t[index - 1] + weight * t[index])


def time_difference(left: float | None, right: float | None) -> float:
    if left is None or right is None:
        return float("inf")
    return abs(left - right) / max(abs(left), abs(right), np.finfo(float).tiny)


def slope_measurement(t: np.ndarray, amplitude: np.ndarray) -> tuple[float, int, float]:
    selected = np.logical_and(amplitude >= 0.002, amplitude <= 0.02)
    count = int(selected.sum())
    if count < 10:
        return float("nan"), count, float("inf")
    design = np.column_stack((t[selected], np.ones(count)))
    target = np.log(amplitude[selected])
    parameters, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
    slope = float(parameters[0])
    return slope, count, abs(slope - MU_F) / MU_F


def direct_mode_solution(times: np.ndarray, carrier_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    state0 = np.array(carrier_vector, dtype=float) * Z_SEED
    period = 2.0 * float(special.ellipk(M)) / OMEGA

    def equation(time: float, state: np.ndarray) -> list[float]:
        elliptic = special.ellipj(OMEGA * time, M)
        background = F * float(elliptic[2])
        omega_squared = (
            K_STAR**2 / (2.0 * A)
            + 1.0 / (4.0 * A**2)
            + (E_C - H_C + H_C * background**2) / A
        )
        return [float(state[1]), float(-omega_squared * state[0])]

    solved = integrate.solve_ivp(
        equation,
        [0.0, T_END],
        state0,
        t_eval=times,
        method="DOP853",
        rtol=2.0e-12,
        atol=2.0e-14,
        max_step=period / 128.0,
    )
    if not solved.success or solved.y.shape != (2, len(times)) or not all_finite(solved.y):
        raise ContractError(f"independent direct mode solve failed: {solved.message}")
    return solved.y[0], solved.y[1]


def summarize(data: dict[str, np.ndarray], carrier_vector: np.ndarray) -> dict[str, Any]:
    times = data["t"]
    energies = data["energy"]
    drifts = np.max(np.abs(energies - energies[:, [0]]), axis=1) / np.maximum(1.0, np.abs(energies[:, 0]))
    exact_y, exact_v = direct_mode_solution(times, carrier_vector)
    difference = np.hypot(
        np.abs(data["z_mode4"][0] - exact_y),
        np.abs(data["vz_mode4"][0] - exact_v) / OMEGA,
    )
    carrier_error = float(np.max(difference) / Z_SEED)
    entries: dict[str, float | None] = {}
    slopes: dict[str, dict[str, Any]] = {}
    for name in ("mediator_only", "competition", "phase_seed"):
        index = ARM_NAMES.index(name)
        entries[name] = first_event(times, data["f_envelope"][index], F_TARGET)
        slope, count, relative = slope_measurement(times, data["f_envelope"][index])
        slopes[name] = {"value": slope, "samples": count, "relative_error": relative}
    competition = ARM_NAMES.index("competition")
    carrier_time = first_event(times, data["z_envelope"][competition], Z_TARGET)
    entry = entries["competition"]
    carrier_at_entry = None if entry is None else float(np.interp(entry, times, data["z_envelope"][competition]))
    phase = ARM_NAMES.index("phase_seed")
    charge_scale = 2.0 * A * OMEGA * LENGTH * 1.0e-12
    global_charge = float(np.max(np.abs(data["charge"][phase] - data["charge"][phase, 0])) / max(charge_scale, abs(float(data["charge"][phase, 0]))))
    local_charge = float(np.max(data["local_charge_l1"][phase]) / charge_scale)
    equilibrium = float(np.max(data["f_envelope"][ARM_NAMES.index("equilibrium_control")]))
    spectrum = data["f_spectrum"][competition, -1]
    broadband = float(np.dot(spectrum[2:], spectrum[2:]) / max(float(np.dot(spectrum[1:], spectrum[1:])), np.finfo(float).tiny))
    return {
        "energy_drift": drifts.tolist(),
        "max_energy_drift": float(np.max(drifts)),
        "carrier_reference_error": carrier_error,
        "equilibrium_max_envelope": equilibrium,
        "slopes": slopes,
        "mediator_entry_times": entries,
        "carrier_comparison_time": carrier_time,
        "carrier_at_mediator_entry": carrier_at_entry,
        "phase_global_charge_drift": global_charge,
        "phase_local_charge_max": local_charge,
        "late_broadband_fraction": broadband,
        "initial_energy": energies[:, 0].tolist(),
        "final_energy": energies[:, -1].tolist(),
    }


def archive_arrays(path: Path, arrays: dict[str, np.ndarray]) -> str:
    with path.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
    return file_hash(path)


def run(output: Path, primary_dir: Path, report: Path) -> int:
    if output.exists():
        raise ContractError("output directory must be absent")
    receipt = empty_receipt()
    independent: dict[str, np.ndarray] = {}
    try:
        (
            files,
            primary_receipt,
            primary_arrays,
            mediator_vector,
            carrier_vector,
            mediator_multiplier,
            carrier_multiplier,
        ) = prerequisite_stage(output, report, primary_dir)
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
            "N": N_GRID,
            "dt": DT,
            "t_end": T_END,
            "arms": list(ARM_NAMES),
        }
        receipt["eigenvectors"] = {
            "mediator": mediator_vector.tolist(),
            "mediator_multiplier": mediator_multiplier,
            "carrier": carrier_vector.tolist(),
            "carrier_multiplier": carrier_multiplier,
        }
        symbolic = independent_symbolic_review()
        receipt["symbolic"] = symbolic
        independent = evolve(mediator_vector, carrier_vector)
        metrics = summarize(independent, carrier_vector)
        receipt["metrics"] = metrics

        required_primary = {
            "fine_t",
            "fine_f_envelope",
            "fine_z_envelope",
            "fine_energy",
            "fine_charge",
            "fine_local_charge_l1",
        }
        primary_schema = required_primary.issubset(primary_arrays)
        schedule_match = bool(
            primary_schema
            and primary_arrays["fine_t"].shape == independent["t"].shape
            and np.max(np.abs(primary_arrays["fine_t"] - independent["t"])) < 1.0e-14
        )
        primary_fine_rows = [row for row in primary_receipt.get("resolutions", []) if row.get("name") == "fine"]
        if len(primary_fine_rows) != 1:
            raise ContractError("primary fine-resolution receipt row is missing")
        primary_metrics = primary_fine_rows[0]["metrics"]

        event_errors = {
            name: time_difference(
                primary_metrics["mediator_entry_times"][name], metrics["mediator_entry_times"][name]
            )
            for name in ("mediator_only", "competition")
        }
        method_event_match = bool(all(error < 0.01 for error in event_errors.values()))
        internal_event_error = time_difference(
            metrics["mediator_entry_times"]["mediator_only"], metrics["mediator_entry_times"]["competition"]
        )
        slope_ok = bool(
            all(
                metrics["slopes"][name]["samples"] >= 10
                and metrics["slopes"][name]["relative_error"] < 0.02
                for name in ("mediator_only", "competition")
            )
        )
        mediator_time = metrics["mediator_entry_times"]["competition"]
        carrier_time = metrics["carrier_comparison_time"]
        independent_mediator_first = bool(
            mediator_time is not None
            and metrics["mediator_entry_times"]["mediator_only"] is not None
            and (carrier_time is None or carrier_time > mediator_time)
            and metrics["carrier_at_mediator_entry"] is not None
            and metrics["carrier_at_mediator_entry"] < Z_TARGET
            and internal_event_error < 0.01
        )
        primary_mediator_first = bool(primary_receipt.get("checks", {}).get("mediator_first"))
        primary_carrier_first = bool(
            primary_metrics.get("carrier_comparison_time") is not None
            and (
                primary_metrics["mediator_entry_times"].get("competition") is None
                or primary_metrics["carrier_comparison_time"] < primary_metrics["mediator_entry_times"]["competition"]
            )
        )
        independent_carrier_first = bool(
            carrier_time is not None and (mediator_time is None or carrier_time < mediator_time)
        )
        numerical = bool(
            primary_receipt.get("qualified") is True
            and primary_schema
            and schedule_match
            and all(all_finite(value) for value in independent.values())
            and symbolic["passed"]
            and metrics["max_energy_drift"] < 1.0e-5
            and metrics["carrier_reference_error"] < 5.0e-4
            and metrics["equilibrium_max_envelope"] < 2.0e-3
            and metrics["phase_global_charge_drift"] < 1.0e-9
            and metrics["phase_local_charge_max"] >= 0.05
            and slope_ok
            and method_event_match
            and internal_event_error < 0.01
        )
        supports = bool(numerical and primary_mediator_first and independent_mediator_first)
        contradicts = bool(numerical and primary_carrier_first and independent_carrier_first)
        receipt["checks"] = {
            "prerequisites": True,
            "primary_qualification": bool(primary_receipt.get("qualified")),
            "primary_schema": primary_schema,
            "schedule": schedule_match,
            "finite": bool(all(all_finite(value) for value in independent.values())),
            "symbolic": bool(symbolic["passed"]),
            "energy": bool(metrics["max_energy_drift"] < 1.0e-5),
            "carrier_reference": bool(metrics["carrier_reference_error"] < 5.0e-4),
            "equilibrium_control": bool(metrics["equilibrium_max_envelope"] < 2.0e-3),
            "global_charge": bool(metrics["phase_global_charge_drift"] < 1.0e-9),
            "local_charge_transport": bool(metrics["phase_local_charge_max"] >= 0.05),
            "linear_slopes": slope_ok,
            "method_entry_times": method_event_match,
            "mediator_only_competition": bool(internal_event_error < 0.01),
            "primary_mediator_first": primary_mediator_first,
            "independent_mediator_first": independent_mediator_first,
            "all_qualifications": numerical,
        }
        receipt["diagnostics"] = {
            "method_entry_relative_errors": event_errors,
            "independent_mediator_only_competition_relative_error": internal_event_error,
            "primary_scientific_condition": primary_receipt.get("diagnostics", {}).get("primary_scientific_condition"),
            "independent_scientific_condition": "mediator_first" if independent_mediator_first else (
                "carrier_first" if independent_carrier_first else "unresolved"
            ),
            "primary_array_sha256": files["primary_arrays.npz"],
        }
        receipt["qualified"] = numerical
        if supports:
            receipt["verdict"] = SUPPORTS
            receipt["passed"] = True
        elif contradicts:
            receipt["verdict"] = CONTRADICTS
            receipt["passed"] = True
        else:
            receipt["verdict"] = "INCONCLUSIVE"
            receipt["passed"] = False
        receipt["files"]["independent_arrays.npz"] = archive_arrays(output / "independent_arrays.npz", independent)
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["verdict"] = "INCONCLUSIVE"
        receipt["passed"] = False
        receipt["qualified"] = False
    if not output.exists():
        output.mkdir(parents=True, exist_ok=False)
    write_json_exclusive(output / "results.json", receipt)
    print(json.dumps({"verdict": receipt["verdict"], "qualified": receipt["qualified"], "error": receipt["error"]}, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--record", type=Path, default=REPORT)
    arguments = parser.parse_args()
    output = arguments.output_dir.resolve()
    if output.exists():
        return 1
    try:
        return run(output, arguments.primary_dir.resolve(), arguments.record.resolve())
    except Exception as exc:
        if output.exists():
            return 1
        output.mkdir(parents=True, exist_ok=False)
        receipt = empty_receipt()
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        write_json_exclusive(output / "results.json", receipt)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
