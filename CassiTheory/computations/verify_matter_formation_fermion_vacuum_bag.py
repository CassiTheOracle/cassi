#!/usr/bin/env python3
"""Independent DOP853 verification for regulated spatial vacuum-to-bag formation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp


ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PRIMARY = COMPUTATIONS / "matter_formation_fermion_vacuum_bag.py"
PREREG = COMPUTATIONS / "matter-formation-fermion-vacuum-bag-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-vacuum-bag-verification.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.fermion-vacuum-bag.v1"

V = 1.0
LAMBDA = 0.25
G_YUKAWA = 6.0
KAPPA = -1.0
RADIUS = 16.0
WIDTH = 2.5
FINAL_TIME = 12.0
SAMPLE_DT = 0.1
LATE_START = 8.0
CORE_RADIUS = 4.0
AMPLITUDES = (1.5, 2.0)
GRIDS = {
    "G0": (48, RADIUS / 48.0, 0.004),
    "G1": (72, RADIUS / 72.0, 0.002),
    "G2": (96, RADIUS / 96.0, 0.001),
}
RAW_TOL = 5.0e-4
SUMMARY_TOL = 2.0e-3


class VacuumBasis:
    def __init__(self, values: np.ndarray, negative: np.ndarray, positive: np.ndarray) -> None:
        self.values = values
        self.negative = negative
        self.positive = positive


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def raw_sha(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def finite_json(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, np.integer, str, bool)) or value is None:
        return True
    if isinstance(value, dict):
        return all(isinstance(key, str) and finite_json(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_json(item) for item in value)
    return False


def as_json(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, np.ndarray):
        return [as_json(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): as_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [as_json(item) for item in value]
    return value


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace receipt: {path}")
    if not finite_json(payload):
        raise ValueError(f"non-finite JSON payload: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(as_json(payload), stream, indent=2, allow_nan=False)
        stream.write("\n")


def grid_arrays(n: int, dr: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    face = np.arange(n + 1, dtype=np.float64) * dr
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volume = (4.0 * math.pi / 3.0) * (face[1:] ** 3 - face[:-1] ** 3)
    area = 4.0 * math.pi * face * face
    return radius, face, volume, area


def derivative_matrix(values: np.ndarray, dr: float) -> np.ndarray:
    result = np.empty_like(values)
    result[0] = values[1] / (2.0 * dr)
    result[1:-1] = (values[2:] - values[:-2]) / (2.0 * dr)
    result[-1] = -values[-2] / (2.0 * dr)
    return result


def scalar_laplacian(sigma: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray) -> np.ndarray:
    flux = np.zeros(sigma.size + 1, dtype=np.float64)
    flux[1:-1] = area[1:-1] * (sigma[1:] - sigma[:-1]) / dr
    flux[-1] = area[-1] * (V - sigma[-1]) / (0.5 * dr)
    return (flux[1:] - flux[:-1]) / volume


def scalar_potential(sigma: np.ndarray) -> np.ndarray:
    return 0.25 * LAMBDA * (sigma * sigma - V * V) ** 2


def dense_hamiltonian(sigma: np.ndarray, dr: float, coupling: float) -> np.ndarray:
    n = sigma.size
    matrix = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    index = np.arange(n)
    matrix[index, index] = coupling * sigma
    matrix[n + index, n + index] = -coupling * sigma
    derivative = 1.0 / (2.0 * dr)
    for i in range(n - 1):
        matrix[i, n + i + 1] += -derivative
        matrix[i + 1, n + i] += derivative
        matrix[n + i, i + 1] += derivative
        matrix[n + i + 1, i] += -derivative
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    matrix[index, n + index] += KAPPA / radius
    matrix[n + index, index] += KAPPA / radius
    return matrix


def apply_hamiltonian(modes: np.ndarray, sigma: np.ndarray, dr: float, coupling: float) -> np.ndarray:
    n = sigma.size
    upper = modes[:n]
    lower = modes[n:]
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    result_upper = coupling * sigma[:, None] * upper - derivative_matrix(lower, dr) + KAPPA * lower / radius[:, None]
    result_lower = derivative_matrix(upper, dr) + KAPPA * upper / radius[:, None] - coupling * sigma[:, None] * lower
    return np.concatenate((result_upper, result_lower), axis=0)


def vacuum_basis(n: int, dr: float, coupling: float) -> tuple[VacuumBasis, np.ndarray, np.ndarray, np.ndarray]:
    sigma = np.ones(n, dtype=np.float64) * V
    hamiltonian = dense_hamiltonian(sigma, dr, coupling)
    values, vectors = np.linalg.eigh(hamiltonian)
    negative = values < -1.0e-10
    positive = values > 1.0e-10
    if int(np.count_nonzero(negative)) != n or int(np.count_nonzero(positive)) != n:
        raise ValueError(f"vacuum spectrum is not split into {n}+{n} states")
    scale = 1.0 / math.sqrt(dr)
    negative_vectors = vectors[:, negative] * scale
    positive_vectors = vectors[:, positive] * scale
    if max(
        float(np.max(np.abs(dr * (negative_vectors.conj().T @ negative_vectors) - np.eye(n)))),
        float(np.max(np.abs(dr * (positive_vectors.conj().T @ positive_vectors) - np.eye(n)))),
    ) > 1.0e-12:
        raise ValueError("radial vacuum basis is not dr-orthonormal")
    basis = VacuumBasis(values, negative_vectors, positive_vectors)
    b0 = np.sum(np.abs(negative_vectors[:n]) ** 2 - np.abs(negative_vectors[n:]) ** 2, axis=1)
    face = np.arange(n + 1, dtype=np.float64) * dr
    volume = (4.0 * math.pi / 3.0) * (face[1:] ** 3 - face[:-1] ** 3)
    source0 = dr * b0 / volume
    return basis, hamiltonian, b0, source0


def normal_ordered_source(
    modes: np.ndarray, b0: np.ndarray, dr: float, volume: np.ndarray
) -> np.ndarray:
    n = b0.size
    b = np.sum(np.abs(modes[:n]) ** 2 - np.abs(modes[n:]) ** 2, axis=1)
    return dr * (b - b0) / volume


def scalar_acceleration(
    sigma: np.ndarray,
    modes: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    radius: np.ndarray,
    b0: np.ndarray,
    coupling: float,
    source_enabled: bool,
) -> np.ndarray:
    source = normal_ordered_source(modes, b0, dr, volume) if source_enabled else 0.0
    return scalar_laplacian(sigma, dr, volume, area) - LAMBDA * (sigma * sigma - V * V) * sigma - coupling * source


def pack(sigma: np.ndarray, pi: np.ndarray, modes: np.ndarray) -> np.ndarray:
    return np.concatenate((sigma, pi, modes.real.ravel(), modes.imag.ravel()))


def unpack(state: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix_size = 2 * n * n
    sigma = state[:n]
    pi = state[n : 2 * n]
    start = 2 * n
    real = state[start : start + matrix_size].reshape(2 * n, n)
    imag = state[start + matrix_size : start + 2 * matrix_size].reshape(2 * n, n)
    return sigma, pi, real + 1j * imag


def independent_rhs(
    state: np.ndarray,
    n: int,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    radius: np.ndarray,
    b0: np.ndarray,
    coupling: float,
    source_enabled: bool,
) -> np.ndarray:
    sigma, pi, modes = unpack(state, n)
    acceleration = scalar_acceleration(sigma, modes, dr, volume, area, radius, b0, coupling, source_enabled)
    mode_dot = -1j * apply_hamiltonian(modes, sigma, dr, coupling)
    return pack(pi, acceleration, mode_dot)


def scalar_energy(sigma: np.ndarray, pi: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray) -> float:
    kinetic = 0.5 * float(np.sum(volume * pi * pi))
    potential = float(np.sum(volume * scalar_potential(sigma)))
    internal = 0.5 * float(np.sum(area[1:-1] * (sigma[1:] - sigma[:-1]) ** 2 / dr))
    outer = 0.5 * float(area[-1] * (sigma[-1] - V) ** 2 / (0.5 * dr))
    return kinetic + potential + internal + outer


def energy(
    sigma: np.ndarray,
    pi: np.ndarray,
    modes: np.ndarray,
    modes0: np.ndarray,
    h0: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    source0: np.ndarray,
    coupling: float,
) -> tuple[float, float, float, float]:
    scalar = scalar_energy(sigma, pi, dr, volume, area)
    h = dense_hamiltonian(sigma, dr, coupling)
    dynamic = float(np.real(np.trace(modes.conj().T @ h @ modes)) * dr)
    initial = float(np.real(np.trace(modes0.conj().T @ h0 @ modes0)) * dr)
    counterterm = float(coupling * np.sum(volume * source0 * (sigma - V)))
    fermion = dynamic - initial - counterterm
    mode_norm = float(np.real(np.trace(modes.conj().T @ modes)) * dr)
    return scalar + fermion, scalar, fermion, mode_norm


def observables(
    sigma: np.ndarray,
    pi: np.ndarray,
    modes: np.ndarray,
    modes0: np.ndarray,
    basis: VacuumBasis,
    h0: np.ndarray,
    radius: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    source0: np.ndarray,
    coupling: float,
) -> dict[str, float]:
    coefficients = dr * (basis.positive.conj().T @ modes)
    particles = basis.positive @ coefficients
    particle_density = np.sum(np.abs(particles[: radius.size]) ** 2 + np.abs(particles[radius.size :]) ** 2, axis=1)
    pair_number = float(np.sum(np.abs(coefficients) ** 2))
    holes = dr * (basis.negative.conj().T @ modes)
    hole_number = float(radius.size - np.sum(np.abs(holes) ** 2))
    core = radius < CORE_RADIUS
    if pair_number > 1.0e-30:
        core_probability = float(np.sum(particle_density[core]) * dr / pair_number)
        rms = math.sqrt(float(np.sum(radius * radius * particle_density) * dr / pair_number))
    else:
        core_probability = 0.0
        rms = 0.0
    total, scalar, fermion, mode_norm = energy(
        sigma, pi, modes, modes0, h0, dr, volume, area, source0, coupling
    )
    scalar_density = 0.5 * pi * pi + scalar_potential(sigma)
    gradient = np.zeros_like(sigma)
    gradient[:-1] = 0.5 * (sigma[1:] - sigma[:-1]) ** 2 / dr**2
    gradient[-1] = 0.5 * (sigma[-1] - V) ** 2 / (0.5 * dr) ** 2
    scalar_density += gradient
    outer = radius > 12.0
    outer_fraction = float(np.sum(volume[outer] * scalar_density[outer]) / max(scalar, 1.0e-30))
    return {
        "total_energy": total,
        "scalar_energy": scalar,
        "fermion_energy": fermion,
        "mode_norm": mode_norm,
        "pair_number": pair_number,
        "hole_number": hole_number,
        "pair_hole_gap": abs(pair_number - hole_number),
        "pair_core_probability": core_probability,
        "pair_rms": rms,
        "center_deficit": float(1.0 - sigma[0]),
        "outer_scalar_energy_fraction": outer_fraction,
    }


def expected_arms() -> list[str]:
    arms = [f"pulse_A{int(round(amplitude * 10)):02d}_{grid}" for amplitude in AMPLITUDES for grid in GRIDS]
    return arms + ["static_vacuum", "source_off", "zero_covariance"]


def arm_spec(arm: str) -> tuple[str, float, bool, bool]:
    if arm == "static_vacuum":
        return "G1", 0.0, True, False
    if arm == "source_off":
        return "G1", 1.5, False, False
    if arm == "zero_covariance":
        return "G1", 1.5, False, True
    for amplitude in AMPLITUDES:
        prefix = f"pulse_A{int(round(amplitude * 10)):02d}_"
        if arm.startswith(prefix):
            grid = arm[len(prefix) :]
            if grid in GRIDS:
                return grid, amplitude, True, False
    raise ValueError(f"unexpected arm {arm}")


def read_primary_archive(input_dir: Path, arm: str, n: int) -> dict[str, np.ndarray]:
    path = input_dir / f"{arm}.npz"
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as archive:
        expected = {"time", "sigma", "pi", "u_re", "u_im"}
        if set(archive.files) != expected:
            raise ValueError(f"unexpected archive keys for {arm}: {archive.files}")
        arrays = {key: np.asarray(archive[key]) for key in archive.files}
    expected_shapes = {
        "time": (int(round(FINAL_TIME / SAMPLE_DT)) + 1,),
        "sigma": (int(round(FINAL_TIME / SAMPLE_DT)) + 1, n),
        "pi": (int(round(FINAL_TIME / SAMPLE_DT)) + 1, n),
        "u_re": (int(round(FINAL_TIME / SAMPLE_DT)) + 1, 2 * n, n),
        "u_im": (int(round(FINAL_TIME / SAMPLE_DT)) + 1, 2 * n, n),
    }
    for key, shape in expected_shapes.items():
        if arrays[key].shape != shape or arrays[key].dtype != np.float64 or not np.isfinite(arrays[key]).all():
            raise ValueError(f"invalid primary archive {arm}.{key}: {arrays[key].shape}")
    expected_time = np.arange(expected_shapes["time"][0], dtype=np.float64) * SAMPLE_DT
    if not np.allclose(arrays["time"], expected_time, rtol=0.0, atol=1.0e-12):
        raise ValueError(f"unexpected primary archive times for {arm}")
    return arrays


def independent_evolve(
    output: Path,
    arm: str,
    n: int,
    dr: float,
    amplitude: float,
    source_enabled: bool,
    zero_covariance: bool,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    radius, _, volume, area = grid_arrays(n, dr)
    basis, h0, b0, source0 = vacuum_basis(n, dr, G_YUKAWA)
    modes0 = basis.negative.copy()
    modes = np.zeros_like(modes0) if zero_covariance else modes0.copy()
    sigma = V - amplitude * np.exp(-0.5 * (radius / WIDTH) ** 2)
    pi = np.zeros(n, dtype=np.float64)
    time = np.arange(int(round(FINAL_TIME / SAMPLE_DT)) + 1, dtype=np.float64) * SAMPLE_DT
    solution = solve_ivp(
        lambda _t, state: independent_rhs(state, n, dr, volume, area, radius, b0, G_YUKAWA, source_enabled),
        (0.0, FINAL_TIME),
        pack(sigma, pi, modes),
        method="DOP853",
        t_eval=time,
        rtol=2.0e-8,
        atol=2.0e-10,
        max_step=0.02,
    )
    if not solution.success:
        raise RuntimeError(f"DOP853 failed for {arm}: {solution.message}")
    sigma_archive = np.asarray(solution.y[:n].T, dtype=np.float64)
    pi_archive = np.asarray(solution.y[n : 2 * n].T, dtype=np.float64)
    matrix_size = 2 * n * n
    start = 2 * n
    real = solution.y[start : start + matrix_size].T.reshape(-1, 2 * n, n)
    imag = solution.y[start + matrix_size : start + 2 * matrix_size].T.reshape(-1, 2 * n, n)
    modes_archive = real + 1j * imag
    raw = {
        "time": time,
        "sigma": sigma_archive,
        "pi": pi_archive,
        "u_re": np.asarray(modes_archive.real, dtype=np.float64),
        "u_im": np.asarray(modes_archive.imag, dtype=np.float64),
    }
    archive_path = output / f"independent_{arm}.npz"
    with archive_path.open("xb") as stream:
        np.savez_compressed(stream, **raw)
    diagnostics = [
        observables(sigma_archive[index], pi_archive[index], modes_archive[index], modes0, basis, h0, radius, dr, volume, area, source0, G_YUKAWA)
        for index in range(time.size)
    ]
    late = time >= LATE_START - 1.0e-12
    values = {key: np.asarray([row[key] for row in diagnostics], dtype=np.float64) for key in diagnostics[0]}
    initial_energy = float(values["total_energy"][0])
    energy_error = np.abs(values["total_energy"] - initial_energy)
    row = {
        "arm": arm,
        "N": n,
        "dr": dr,
        "dt": float(GRIDS[arm_spec(arm)[0]][2]),
        "amplitude": amplitude,
        "steps": int(round(FINAL_TIME / GRIDS[arm_spec(arm)[0]][2])),
        "duration": FINAL_TIME,
        "initial_energy": initial_energy,
        "final_energy": float(values["total_energy"][-1]),
        "max_energy_error": float(np.max(energy_error)),
        "relative_energy_error": float(np.max(energy_error) / max(1.0, abs(initial_energy))),
        "late_means": {key: float(np.mean(value[late])) for key, value in values.items()},
        "late_std": {key: float(np.std(value[late])) for key, value in values.items()},
        "grid": arm_spec(arm)[0],
        "candidate": arm.startswith("pulse_"),
        "source_enabled": source_enabled,
        "zero_covariance": zero_covariance,
    }
    row["captured"] = capture_predicate(row) if row["candidate"] else False
    return row, raw


def compare_arrays(primary: dict[str, np.ndarray], independent: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for key in ("time", "sigma", "pi", "u_re", "u_im"):
        if primary[key].shape != independent[key].shape:
            comparisons.append({"array": key, "pass": False, "maximum_absolute_error": math.inf, "threshold": 0.0, "reason": "shape"})
            continue
        error = float(np.max(np.abs(primary[key] - independent[key])))
        threshold = 1.0e-12 if key == "time" else RAW_TOL
        comparisons.append({"array": key, "pass": bool(error <= threshold), "maximum_absolute_error": error, "threshold": threshold})
    return comparisons


def capture_predicate(row: dict[str, Any]) -> bool:
    late = row["late_means"]
    spread = row["late_std"]
    return bool(
        late["pair_number"] >= 0.02
        and late["pair_core_probability"] >= 0.50
        and late["pair_rms"] <= 5.0
        and spread["pair_number"] <= 0.10
        and spread["pair_rms"] <= 0.75
        and late["center_deficit"] >= 0.05
        and late["outer_scalar_energy_fraction"] < 0.20
        and row["relative_energy_error"] <= 5.0e-3
        and late["pair_hole_gap"] <= 0.10
    )


def summary_comparisons(primary: dict[str, Any], independent: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for key in ("relative_energy_error", "initial_energy", "final_energy", "max_energy_error"):
        error = abs(float(primary[key]) - float(independent[key]))
        checks.append({"field": key, "error": error, "pass": error <= SUMMARY_TOL})
    for group in ("late_means", "late_std"):
        for key in primary[group]:
            error = abs(float(primary[group][key]) - float(independent[group][key]))
            checks.append({"field": f"{group}.{key}", "error": error, "pass": error <= SUMMARY_TOL})
    return checks


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PRIMARY, PREREG):
        relative = relative_path(path)
        target = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, target)
        result[relative] = raw_sha(target)
    return result


def failure_receipt(output: Path, message: str) -> dict[str, Any]:
    receipt = {
        "schema": SCHEMA,
        "numerical_pass": False,
        "verdict": "INCONCLUSIVE",
        "complete_physical_matter_formation": False,
        "failures": [message],
        "rows": [],
        "independent_checks": [],
    }
    write_json_exclusive(output, receipt)
    return receipt


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing existing verification receipt: {output_path}")
    output_path.parent.mkdir(parents=False, exist_ok=True)
    primary_receipt_path = input_dir / "result.json"
    if not primary_receipt_path.is_file():
        return failure_receipt(output_path, "missing primary result.json")
    primary_receipt = json.loads(primary_receipt_path.read_text(encoding="utf-8"))
    expected_sources = {
        "primary": {"path": relative_path(PRIMARY), "sha256": canonical_sha(PRIMARY)},
        "prereg": {"path": relative_path(PREREG), "sha256": canonical_sha(PREREG)},
    }
    source_pass = bool(primary_receipt.get("schema") == PRIMARY_SCHEMA and primary_receipt.get("identities", {}).get("sources") == expected_sources)
    if not source_pass:
        return failure_receipt(output_path, "primary source identity or schema mismatch")
    output_dir = output_path.parent
    archived_sources = snapshot_sources(output_dir)
    rows: list[dict[str, Any]] = []
    independent_checks: list[dict[str, Any]] = []
    raw_comparisons: list[dict[str, Any]] = []
    summary_pass = True
    raw_pass = True
    primary_rows = {row.get("arm"): row for row in primary_receipt.get("rows", [])}
    if set(primary_rows) != set(expected_arms()):
        return failure_receipt(output_path, "primary row arm set mismatch")
    for arm in expected_arms():
        grid, amplitude, source_enabled, zero_covariance = arm_spec(arm)
        n, dr, _dt = GRIDS[grid]
        primary_arrays = read_primary_archive(input_dir, arm, n)
        independent_row, independent_arrays = independent_evolve(output_dir, arm, n, dr, amplitude, source_enabled, zero_covariance)
        primary_raw = {
            "time": primary_arrays["time"],
            "sigma": primary_arrays["sigma"],
            "pi": primary_arrays["pi"],
            "u_re": primary_arrays["u_re"],
            "u_im": primary_arrays["u_im"],
        }
        comparison = compare_arrays(primary_raw, independent_arrays)
        raw_comparisons.extend({"arm": arm, **item} for item in comparison)
        raw_ok = all(item["pass"] for item in comparison)
        primary_summary = primary_rows[arm]
        summary = summary_comparisons(primary_summary, independent_row)
        summary_ok = all(item["pass"] for item in summary)
        raw_pass = raw_pass and raw_ok
        summary_pass = summary_pass and summary_ok
        independent_checks.append({"arm": arm, "raw": comparison, "summary": summary, "pass": raw_ok and summary_ok})
        rows.append(independent_row)
    candidate_rows = [row for row in rows if row["candidate"]]
    controls = [row for row in rows if not row["candidate"]]
    resolution: list[dict[str, Any]] = []
    by_key = {(row["amplitude"], row["grid"]): row for row in candidate_rows}
    for amplitude in AMPLITUDES:
        for left_grid, right_grid in (("G0", "G1"), ("G1", "G2")):
            left = by_key[(amplitude, left_grid)]
            right = by_key[(amplitude, right_grid)]
            for key in ("pair_number", "pair_core_probability", "pair_rms", "center_deficit"):
                difference = abs(left["late_means"][key] - right["late_means"][key])
                resolution.append({"amplitude": amplitude, "left": left_grid, "right": right_grid, "observable": key, "difference": difference, "pass": difference <= 0.15})
    static = next(row for row in controls if row["arm"] == "static_vacuum")
    zero = next(row for row in controls if row["arm"] == "zero_covariance")
    controls_pass = bool(
        static["late_means"]["center_deficit"] <= 1.0e-10
        and static["late_means"]["pair_number"] <= 1.0e-8
        and zero["late_means"]["mode_norm"] <= 1.0e-8
        and zero["late_means"]["pair_number"] <= 1.0e-8
    )
    resolution_pass = bool(all(item["pass"] for item in resolution))
    candidate_pass = bool(any(row["captured"] for row in candidate_rows))
    finite_pass = bool(all(finite_json(row) for row in rows))
    numerical_pass = bool(source_pass and finite_pass and raw_pass and summary_pass and controls_pass and resolution_pass)
    verdict = (
        "CAPTURED—conditional regulated radial vacuum-to-bag formation"
        if numerical_pass and candidate_pass
        else "DOES NOT EMERGE—conditional regulated radial vacuum-to-bag formation"
        if numerical_pass
        else "INCONCLUSIVE"
    )
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "regulated_radial_vacuum_mechanism": bool(numerical_pass and candidate_pass),
        "identities": {
            "primary": expected_sources["primary"],
            "verifier": {"path": relative_path(SELF), "sha256": canonical_sha(SELF)},
            "prereg": expected_sources["prereg"],
            "archived_source_sha256": archived_sources,
        },
        "rows": rows,
        "raw_comparisons": raw_comparisons,
        "independent_checks": independent_checks,
        "resolution": resolution,
        "controls_pass": controls_pass,
        "scope": "finite-box 3D spherical kappa=-1 vacuum covariance with normal-ordered force; no continuum renormalization or all-sector claim",
        "failures": [name for name, passed in (("source", source_pass), ("finite", finite_pass), ("raw", raw_pass), ("summary", summary_pass), ("controls", controls_pass), ("resolution", resolution_pass)) if not passed],
    }
    write_json_exclusive(output_path, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = run(args.input_dir.resolve(), args.output.resolve())
    except (FileExistsError, OSError, ValueError, RuntimeError) as exc:
        print(f"vacuum-bag verifier failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
