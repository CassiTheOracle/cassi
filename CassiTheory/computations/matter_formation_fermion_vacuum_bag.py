#!/usr/bin/env python3
"""Primary regulated spatial vacuum-to-bag formation calculation.

Run from the repository root:
    python computations/matter_formation_fermion_vacuum_bag.py --output-dir runs/<fresh-name>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter-formation-fermion-vacuum-bag-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-vacuum-bag.v1"

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


def write_npz_exclusive(path: Path, arrays: dict[str, np.ndarray]) -> str:
    if path.exists():
        raise FileExistsError(f"refusing to replace archive: {path}")
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return raw_sha(path)


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG):
        relative = relative_path(path)
        target = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, target)
        result[relative] = raw_sha(target)
    return result


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
    d = 1.0 / (2.0 * dr)
    for i in range(n - 1):
        matrix[i, n + i + 1] += -d
        matrix[i + 1, n + i] += d
        matrix[n + i, i + 1] += d
        matrix[n + i + 1, i] += -d
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    matrix[index, n + index] += KAPPA / radius
    matrix[n + index, index] += KAPPA / radius
    return matrix


def matrix_hamiltonian_apply(
    modes: np.ndarray, sigma: np.ndarray, dr: float, coupling: float
) -> np.ndarray:
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
    radial_scale = 1.0 / math.sqrt(dr)
    basis = VacuumBasis(values, vectors[:, negative] * radial_scale, vectors[:, positive] * radial_scale)
    metric_negative = dr * (basis.negative.conj().T @ basis.negative)
    metric_positive = dr * (basis.positive.conj().T @ basis.positive)
    if max(float(np.max(np.abs(metric_negative - np.eye(n)))), float(np.max(np.abs(metric_positive - np.eye(n))))) > 1.0e-12:
        raise ValueError("radial vacuum basis is not dr-orthonormal")
    b0 = np.sum(np.abs(basis.negative[:n]) ** 2 - np.abs(basis.negative[n:]) ** 2, axis=1)
    volume = (4.0 * math.pi / 3.0) * (((np.arange(n, dtype=np.float64) + 1.0) * dr) ** 3 - (np.arange(n, dtype=np.float64) * dr) ** 3)
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



def rhs(
    sigma: np.ndarray,
    pi: np.ndarray,
    modes: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    radius: np.ndarray,
    b0: np.ndarray,
    coupling: float,
    source_enabled: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        pi,
        scalar_acceleration(sigma, modes, dr, volume, area, radius, b0, coupling, source_enabled),
        -1j * matrix_hamiltonian_apply(modes, sigma, dr, coupling),
    )


def rk4_step(
    sigma: np.ndarray,
    pi: np.ndarray,
    modes: np.ndarray,
    dt: float,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    radius: np.ndarray,
    b0: np.ndarray,
    coupling: float,
    source_enabled: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    k1 = rhs(sigma, pi, modes, dr, volume, area, radius, b0, coupling, source_enabled)
    k2 = rhs(sigma + 0.5 * dt * k1[0], pi + 0.5 * dt * k1[1], modes + 0.5 * dt * k1[2], dr, volume, area, radius, b0, coupling, source_enabled)
    k3 = rhs(sigma + 0.5 * dt * k2[0], pi + 0.5 * dt * k2[1], modes + 0.5 * dt * k2[2], dr, volume, area, radius, b0, coupling, source_enabled)
    k4 = rhs(sigma + dt * k3[0], pi + dt * k3[1], modes + dt * k3[2], dr, volume, area, radius, b0, coupling, source_enabled)
    return (
        sigma + dt * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]) / 6.0,
        pi + dt * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]) / 6.0,
        modes + dt * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2]) / 6.0,
    )


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
    return scalar + fermion, scalar, fermion, float(np.real(np.trace(modes.conj().T @ modes)) * dr)


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
    hole_coefficients = dr * (basis.negative.conj().T @ modes)
    hole_number = float(radius.size - np.sum(np.abs(hole_coefficients) ** 2))
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


def initial_state(n: int, dr: float, amplitude: float, zero_covariance: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, VacuumBasis, np.ndarray, np.ndarray]:
    radius, _, volume, area = grid_arrays(n, dr)
    basis, h0, b0, source0 = vacuum_basis(n, dr, G_YUKAWA)
    modes0 = basis.negative.copy()
    modes = np.zeros_like(modes0) if zero_covariance else modes0.copy()
    sigma = V - amplitude * np.exp(-0.5 * (radius / WIDTH) ** 2)
    pi = np.zeros(n, dtype=np.float64)
    return sigma, pi, modes, basis, h0, source0


def arm_name(amplitude: float, grid: str) -> str:
    return f"pulse_A{int(round(amplitude * 10)):02d}_{grid}"


def archive_arrays(
    output: Path,
    arm: str,
    time: list[float],
    sigma: list[np.ndarray],
    pi: list[np.ndarray],
    modes: list[np.ndarray],
) -> str:
    arrays = {
        "time": np.asarray(time, dtype=np.float64),
        "sigma": np.asarray(sigma, dtype=np.float64),
        "pi": np.asarray(pi, dtype=np.float64),
        "u_re": np.asarray([value.real for value in modes], dtype=np.float64),
        "u_im": np.asarray([value.imag for value in modes], dtype=np.float64),
    }
    if any(not np.isfinite(value).all() for value in arrays.values()):
        raise FloatingPointError(f"nonfinite archive for {arm}")
    return write_npz_exclusive(output / f"{arm}.npz", arrays)


def evolve_arm(
    output: Path,
    arm: str,
    n: int,
    dr: float,
    dt: float,
    amplitude: float,
    source_enabled: bool,
    zero_covariance: bool,
) -> tuple[dict[str, Any], dict[str, str]]:
    radius, _, volume, area = grid_arrays(n, dr)
    sigma, pi, modes, basis, h0, source0 = initial_state(n, dr, amplitude, zero_covariance)
    b0 = source0 * volume / dr
    modes0 = basis.negative.copy()
    steps = int(round(FINAL_TIME / dt))
    sample_steps = int(round(SAMPLE_DT / dt))
    if steps <= 0 or sample_steps <= 0 or not math.isclose(steps * dt, FINAL_TIME, abs_tol=1.0e-12) or not math.isclose(sample_steps * dt, SAMPLE_DT, abs_tol=1.0e-12):
        raise ValueError(f"invalid schedule for {arm}")
    times: list[float] = [0.0]
    sigmas: list[np.ndarray] = [sigma.copy()]
    pis: list[np.ndarray] = [pi.copy()]
    mode_archive: list[np.ndarray] = [modes.copy()]
    diagnostics: list[dict[str, float]] = [observables(sigma, pi, modes, modes0, basis, h0, radius, dr, volume, area, source0, G_YUKAWA)]
    for step in range(1, steps + 1):
        sigma, pi, modes = rk4_step(
            sigma, pi, modes, dt, dr, volume, area, radius, b0,
            G_YUKAWA, source_enabled
        )
        if step % sample_steps == 0 or step == steps:
            times.append(step * dt)
            sigmas.append(sigma.copy())
            pis.append(pi.copy())
            mode_archive.append(modes.copy())
            diagnostics.append(observables(sigma, pi, modes, modes0, basis, h0, radius, dr, volume, area, source0, G_YUKAWA))
    if len(times) != int(round(FINAL_TIME / SAMPLE_DT)) + 1:
        raise AssertionError(f"archive count mismatch for {arm}")
    archive_hash = archive_arrays(output, arm, times, sigmas, pis, mode_archive)
    values = {key: np.asarray([row[key] for row in diagnostics], dtype=np.float64) for key in diagnostics[0]}
    late = np.asarray(times, dtype=np.float64) >= LATE_START - 1.0e-12
    initial_energy = float(values["total_energy"][0])
    energy_error = np.abs(values["total_energy"] - initial_energy)
    relative_energy_error = float(np.max(energy_error) / max(1.0, abs(initial_energy)))
    late_means = {key: float(np.mean(value[late])) for key, value in values.items()}
    late_std = {key: float(np.std(value[late])) for key, value in values.items()}
    row = {
        "arm": arm,
        "N": n,
        "dr": dr,
        "dt": dt,
        "amplitude": amplitude,
        "steps": steps,
        "duration": FINAL_TIME,
        "initial_energy": initial_energy,
        "final_energy": float(values["total_energy"][-1]),
        "max_energy_error": float(np.max(energy_error)),
        "relative_energy_error": relative_energy_error,
        "late_means": late_means,
        "late_std": late_std,
        "grid": arm.rsplit("_", 1)[-1],
        "candidate": bool(arm.startswith("pulse_")),
        "source_enabled": source_enabled,
        "zero_covariance": zero_covariance,
    }
    if row["candidate"]:
        row["captured"] = capture_predicate(row)
    else:
        row["captured"] = False
    return row, {"path": f"{arm}.npz", "sha256": archive_hash}


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


def validate_row(row: dict[str, Any]) -> bool:
    values: list[float] = [row["initial_energy"], row["final_energy"], row["max_energy_error"], row["relative_energy_error"]]
    values.extend(row["late_means"].values())
    values.extend(row["late_std"].values())
    return bool(all(math.isfinite(float(value)) for value in values))


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=False, exist_ok=False)
    source_hashes = snapshot_sources(output_dir)
    rows: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, str]] = {}
    for amplitude in AMPLITUDES:
        for grid, (n, dr, dt) in GRIDS.items():
            arm = arm_name(amplitude, grid)
            row, artifact = evolve_arm(output_dir, arm, n, dr, dt, amplitude, True, False)
            rows.append(row)
            artifacts[arm] = artifact
    n, dr, dt = GRIDS["G1"]
    controls = (
        ("static_vacuum", 0.0, True, False),
        ("source_off", 1.5, False, False),
        ("zero_covariance", 1.5, False, True),
    )
    for arm, amplitude, source_enabled, zero_covariance in controls:
        row, artifact = evolve_arm(output_dir, arm, n, dr, dt, amplitude, source_enabled, zero_covariance)
        row.update({"grid": "G1", "candidate": False, "captured": False})
        rows.append(row)
        artifacts[arm] = artifact
    candidate_rows = [row for row in rows if row["candidate"]]
    control_rows = [row for row in rows if not row["candidate"]]
    finite_pass = bool(all(validate_row(row) for row in rows))
    resolution: list[dict[str, Any]] = []
    by_key = {(row["amplitude"], row["grid"]): row for row in candidate_rows}
    for amplitude in AMPLITUDES:
        for left_grid, right_grid in (("G0", "G1"), ("G1", "G2")):
            left = by_key[(amplitude, left_grid)]
            right = by_key[(amplitude, right_grid)]
            for key in ("pair_number", "pair_core_probability", "pair_rms", "center_deficit"):
                difference = abs(left["late_means"][key] - right["late_means"][key])
                resolution.append({"amplitude": amplitude, "left": left_grid, "right": right_grid, "observable": key, "difference": difference, "pass": difference <= 0.15})
    static = next(row for row in control_rows if row["arm"] == "static_vacuum")
    zero = next(row for row in control_rows if row["arm"] == "zero_covariance")
    controls_pass = bool(
        static["late_means"]["center_deficit"] <= 1.0e-10
        and static["late_means"]["pair_number"] <= 1.0e-8
        and zero["late_means"]["mode_norm"] <= 1.0e-8
        and zero["late_means"]["pair_number"] <= 1.0e-8
    )
    resolution_pass = bool(all(item["pass"] for item in resolution))
    candidate_pass = bool(any(row["captured"] for row in candidate_rows))
    numerical_pass = bool(finite_pass and controls_pass and resolution_pass)
    verdict = (
        "CAPTURED—conditional regulated radial vacuum-to-bag formation"
        if numerical_pass and candidate_pass
        else "DOES NOT EMERGE—conditional regulated radial vacuum-to-bag formation"
        if numerical_pass
        else "INCONCLUSIVE"
    )
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "identities": {
            "sources": {
                "primary": {"path": relative_path(SELF), "sha256": canonical_sha(SELF)},
                "prereg": {"path": relative_path(PREREG), "sha256": canonical_sha(PREREG)},
            },
            "archived_source_sha256": source_hashes,
        },
        "artifacts": artifacts,
        "rows": rows,
        "resolution": resolution,
        "checks": {
            "finite_payload": finite_pass,
            "controls": controls_pass,
            "resolution": resolution_pass,
            "candidate": candidate_pass,
        },
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "regulated_radial_vacuum_mechanism": bool(numerical_pass and candidate_pass),
        "scope": "finite-box 3D spherical kappa=-1 vacuum covariance with normal-ordered force; no continuum renormalization or all-sector claim",
        "failures": [name for name, passed in (("finite_payload", finite_pass), ("controls", controls_pass), ("resolution", resolution_pass)) if not passed],
    }
    write_json_exclusive(output_dir / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = run(args.output_dir.resolve())
    except (FileExistsError, OSError, ValueError, FloatingPointError) as exc:
        print(f"vacuum-bag primary failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output_dir.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
