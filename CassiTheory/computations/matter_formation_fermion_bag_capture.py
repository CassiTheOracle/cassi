#!/usr/bin/env python3
"""Primary three-dimensional radial fermion-bag capture calculation.

Run from the repository root:
    python computations/matter_formation_fermion_bag_capture.py --output-dir runs/20260912_matter_formation_fermion_bag_capture
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
PREREG = COMPUTATIONS / "matter-formation-fermion-bag-capture-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-bag-capture.v1"

V = 1.0
LAMBDA = 0.25
G_YUKAWA = 6.0
KAPPA = -1.0
RADIUS = 16.0
FINAL_TIME = 24.0
SAMPLE_DT = 0.1
CORE_RADIUS = 4.0
VACUUM_MASS = G_YUKAWA * V
GRIDS = {
    "G0": (160, 0.1, 0.02),
    "G1": (240, 1.0 / 15.0, 0.01),
    "G2": (320, 0.05, 0.005),
}
LATE_START = 16.0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def source_identity(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": sha256_bytes(canonical_bytes(data)),
    }


def raw_sha(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def finite_json(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, np.integer, str, bool)) or value is None:
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite_json(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_json(v) for v in value)
    return False


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if not finite_json(value):
        raise ValueError(f"non-finite JSON payload: {path}")
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"))


def grid_arrays(n: int, dr: float) -> tuple[np.ndarray, ...]:
    face = np.arange(n + 1, dtype=np.float64) * dr
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volume = (4.0 * math.pi / 3.0) * (face[1:] ** 3 - face[:-1] ** 3)
    area = 4.0 * math.pi * face * face
    return r, face, volume, area


def derivative(values: np.ndarray, dr: float) -> np.ndarray:
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


def scalar_acceleration(
    sigma: np.ndarray,
    psi: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    coupling: float,
) -> np.ndarray:
    density = (np.abs(psi[: sigma.size]) ** 2 - np.abs(psi[sigma.size :]) ** 2) / (4.0 * math.pi * (np.arange(sigma.size, dtype=np.float64) + 0.5) ** 2 * dr * dr)
    return scalar_laplacian(sigma, dr, volume, area) - LAMBDA * (sigma * sigma - V * V) * sigma - coupling * density


def apply_hamiltonian(psi: np.ndarray, sigma: np.ndarray, dr: float, coupling: float) -> np.ndarray:
    n = sigma.size
    upper = psi[:n]
    lower = psi[n:]
    d_upper = derivative(upper, dr)
    d_lower = derivative(lower, dr)
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    result_upper = coupling * sigma * upper - d_lower + KAPPA * lower / r
    result_lower = d_upper + KAPPA * upper / r - coupling * sigma * lower
    return np.concatenate((result_upper, result_lower))


def dense_hamiltonian(sigma: np.ndarray, dr: float, coupling: float) -> np.ndarray:
    n = sigma.size
    matrix = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    matrix[np.arange(n), np.arange(n)] = coupling * sigma
    matrix[n + np.arange(n), n + np.arange(n)] = -coupling * sigma
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    for i in range(n - 1):
        d_up = 1.0 / (2.0 * dr)
        matrix[i, n + i + 1] += -d_up
        matrix[i + 1, n + i] += d_up
        matrix[n + i, i + 1] += d_up
        matrix[n + i + 1, i] += -d_up
    matrix[np.arange(n), n + np.arange(n)] += KAPPA / r
    matrix[n + np.arange(n), np.arange(n)] += KAPPA / r

    return matrix
def operator_self_check() -> None:
    n = 24
    dr = 0.1
    sigma = 1.0 + 0.2 * np.sin(np.arange(n, dtype=np.float64) / 3.0)
    hamiltonian = dense_hamiltonian(sigma, dr, G_YUKAWA)
    rng = np.random.default_rng(20260912)
    vector = rng.normal(size=2 * n) + 1j * rng.normal(size=2 * n)
    hermiticity_error = float(np.max(np.abs(hamiltonian - hamiltonian.conj().T)))
    equivalence_error = float(np.max(np.abs(hamiltonian @ vector - apply_hamiltonian(vector, sigma, dr, G_YUKAWA))))
    assert hermiticity_error <= 1.0e-12, hermiticity_error
    assert equivalence_error <= 1.0e-12, equivalence_error



def initial_spinor(n: int, dr: float, coupling: float, zero: bool = False) -> np.ndarray:
    if zero:
        return np.zeros(2 * n, dtype=np.complex128)
    sigma = np.ones(n, dtype=np.float64) * V
    hamiltonian = dense_hamiltonian(sigma, dr, coupling)
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    positive = eigenvectors[:, eigenvalues > 0.0]
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    trial = np.zeros(2 * n, dtype=np.complex128)
    trial[:n] = r * np.exp(-0.5 * ((r - 1.2) / 0.6) ** 2)
    projected = positive @ (positive.conj().T @ trial)
    norm = math.sqrt(float(np.sum(np.abs(projected) ** 2) * dr))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("positive-energy packet projection failed")
    return projected / norm


def rhs(
    sigma: np.ndarray,
    pi: np.ndarray,
    psi: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    coupling: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        pi,
        scalar_acceleration(sigma, psi, dr, volume, area, coupling),
        -1j * apply_hamiltonian(psi, sigma, dr, coupling),
    )


def rk4_step(
    sigma: np.ndarray,
    pi: np.ndarray,
    psi: np.ndarray,
    dt: float,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    coupling: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    k1 = rhs(sigma, pi, psi, dr, volume, area, coupling)
    k2 = rhs(sigma + 0.5 * dt * k1[0], pi + 0.5 * dt * k1[1], psi + 0.5 * dt * k1[2], dr, volume, area, coupling)
    k3 = rhs(sigma + 0.5 * dt * k2[0], pi + 0.5 * dt * k2[1], psi + 0.5 * dt * k2[2], dr, volume, area, coupling)
    k4 = rhs(sigma + dt * k3[0], pi + dt * k3[1], psi + dt * k3[2], dr, volume, area, coupling)
    return (
        sigma + dt * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]) / 6.0,
        pi + dt * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]) / 6.0,
        psi + dt * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2]) / 6.0,
    )


def energy(
    sigma: np.ndarray,
    pi: np.ndarray,
    psi: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    coupling: float,
) -> tuple[float, float, float, float]:
    scalar_kinetic = 0.5 * float(np.sum(volume * pi * pi))
    scalar_pot = float(np.sum(volume * scalar_potential(sigma)))
    internal = 0.5 * float(np.sum(area[1:-1] * (sigma[1:] - sigma[:-1]) ** 2 / dr))
    outer = 0.5 * float(area[-1] * (sigma[-1] - V) ** 2 / (0.5 * dr))
    scalar_total = scalar_kinetic + scalar_pot + internal + outer
    fermion = float(np.real(np.vdot(psi, apply_hamiltonian(psi, sigma, dr, coupling)) * dr))
    return scalar_total + fermion, scalar_total, fermion, float(np.sum(np.abs(psi) ** 2) * dr)


def observables(
    sigma: np.ndarray,
    pi: np.ndarray,
    psi: np.ndarray,
    r: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    coupling: float,
) -> dict[str, float]:
    n = r.size
    probability = np.abs(psi[:n]) ** 2 + np.abs(psi[n:]) ** 2
    probability_sum = float(np.sum(probability) * dr)
    core = r < CORE_RADIUS
    core_probability = float(np.sum(probability[core]) * dr)
    radius = math.sqrt(float(np.sum(r * r * probability) * dr) / max(probability_sum, 1.0e-30))
    total, scalar_total, fermion, norm = energy(sigma, pi, psi, dr, volume, area, coupling)
    scalar_density = 0.5 * pi * pi + scalar_potential(sigma)
    grad_density = np.zeros_like(sigma)
    grad_density[:-1] = 0.5 * (sigma[1:] - sigma[:-1]) ** 2 / dr**2
    grad_density[-1] = 0.5 * (sigma[-1] - V) ** 2 / (0.5 * dr) ** 2
    scalar_density += grad_density
    outer = r > 12.0
    outer_energy = float(np.sum(volume[outer] * scalar_density[outer]))
    center_deficit = float(1.0 - sigma[0])
    return {
        "total_energy": total,
        "scalar_energy": scalar_total,
        "fermion_energy": fermion,
        "fermion_norm": norm,
        "core_probability": core_probability,
        "fermion_rms": radius,
        "center_deficit": center_deficit,
        "outer_scalar_energy_fraction": outer_energy / max(abs(total), 1.0),
    }


def evolve(
    n: int,
    dr: float,
    dt: float,
    coupling: float,
    psi0: np.ndarray,
    output: Path,
    arm: str,
) -> dict[str, Any]:
    r, _, volume, area = grid_arrays(n, dr)
    sigma = np.full(n, V, dtype=np.float64)
    pi = np.zeros(n, dtype=np.float64)
    psi = psi0.copy()
    steps = int(round(FINAL_TIME / dt))
    stride = int(round(SAMPLE_DT / dt))
    sample_count = steps // stride + 1
    time = np.arange(sample_count, dtype=np.float64) * SAMPLE_DT
    sigma_out = np.empty((sample_count, n), dtype=np.float64)
    pi_out = np.empty((sample_count, n), dtype=np.float64)
    psi_re = np.empty((sample_count, 2 * n), dtype=np.float64)
    psi_im = np.empty((sample_count, 2 * n), dtype=np.float64)
    metrics: list[dict[str, float]] = []
    sample = 0
    sigma_out[0] = sigma
    pi_out[0] = pi
    psi_re[0] = psi.real
    psi_im[0] = psi.imag
    initial = observables(sigma, pi, psi, r, dr, volume, area, coupling)
    metrics.append(initial)
    for step in range(1, steps + 1):
        sigma, pi, psi = rk4_step(sigma, pi, psi, dt, dr, volume, area, coupling)
        if not (np.all(np.isfinite(sigma)) and np.all(np.isfinite(pi)) and np.all(np.isfinite(psi))):
            raise FloatingPointError(f"nonfinite state at {arm} step {step}")
        if step % stride == 0:
            sample += 1
            sigma_out[sample] = sigma
            pi_out[sample] = pi
            psi_re[sample] = psi.real
            psi_im[sample] = psi.imag
            metrics.append(observables(sigma, pi, psi, r, dr, volume, area, coupling))
    archive = output / f"{arm}.npz"
    with archive.open("xb") as stream:
        np.savez_compressed(stream, time=time, sigma=sigma_out, pi=pi_out, psi_re=psi_re, psi_im=psi_im)
    metric_array = {key: np.asarray([row[key] for row in metrics], dtype=np.float64) for key in metrics[0]}
    late = time >= LATE_START - 1.0e-12
    late_means = {key: float(np.mean(values[late])) for key, values in metric_array.items()}
    late_std = {key: float(np.std(values[late])) for key, values in metric_array.items()}
    initial_total = float(metric_array["total_energy"][0])
    max_energy_error = float(np.max(np.abs(metric_array["total_energy"] - initial_total)))
    row = {
        "arm": arm,
        "N": int(n),
        "dr": float(dr),
        "dt": float(dt),
        "coupling": float(coupling),
        "steps": steps,
        "duration": FINAL_TIME,
        "initial_energy": initial_total,
        "final_energy": float(metric_array["total_energy"][-1]),
        "max_energy_error": max_energy_error,
        "relative_energy_error": max_energy_error / max(1.0, abs(initial_total)),
        "final_norm": float(metric_array["fermion_norm"][-1]),
        "late_means": late_means,
        "late_std": late_std,
        "raw_archive": archive.name,
        "raw_archive_sha256": raw_sha(archive),
    }
    return row


def capture_predicate(row: dict[str, Any]) -> bool:
    means = row["late_means"]
    std = row["late_std"]
    return bool(
        means["core_probability"] >= 0.50
        and means["fermion_energy"] <= 0.95 * VACUUM_MASS
        and means["fermion_rms"] <= 5.0
        and std["core_probability"] <= 0.10
        and std["fermion_rms"] <= 0.75
        and means["center_deficit"] >= 0.05
        and row["relative_energy_error"] <= 2.0e-3
        and means["outer_scalar_energy_fraction"] <= 0.10
    )


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG):
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        target = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, target)
        result[relative] = raw_sha(target)
    return result


def run(output: Path) -> dict[str, Any]:
    operator_self_check()
    if output.exists():
        raise FileExistsError(f"refusing existing output directory: {output}")
    output.mkdir(parents=False, exist_ok=False)
    source_hashes = snapshot_sources(output)
    source_identities = {"primary": source_identity(SELF), "prereg": source_identity(PREREG)}
    rows: list[dict[str, Any]] = []
    g1_packet = initial_spinor(GRIDS["G1"][0], GRIDS["G1"][1], G_YUKAWA)
    for grid_name, (n, dr, dt) in GRIDS.items():
        row = evolve(n, dr, dt, G_YUKAWA, initial_spinor(n, dr, G_YUKAWA), output, f"{grid_name}_capture")
        row["grid"] = grid_name
        row["candidate"] = True
        row["captured"] = capture_predicate(row)
        rows.append(row)
    n, dr, dt = GRIDS["G1"]
    control_g = evolve(n, dr, dt, 0.0, g1_packet, output, "G1_g_zero")
    control_g.update({"grid": "G1", "candidate": False, "captured": False})
    rows.append(control_g)
    control_zero = evolve(n, dr, dt, G_YUKAWA, initial_spinor(n, dr, G_YUKAWA, zero=True), output, "G1_packet_zero")
    control_zero.update({"grid": "G1", "candidate": False, "captured": False})
    rows.append(control_zero)
    candidate_rows = [row for row in rows if row["candidate"]]
    controls = [row for row in rows if not row["candidate"]]
    adjacent = []
    ordered = [row for row in candidate_rows]
    for left, right in zip(ordered, ordered[1:]):
        for key in ("core_probability", "fermion_rms", "fermion_energy", "center_deficit"):
            difference = abs(left["late_means"][key] - right["late_means"][key])
            adjacent.append({"left": left["grid"], "right": right["grid"], "observable": key, "difference": difference, "pass": difference <= 0.10})
    finite_pass = all(
        math.isfinite(float(row["relative_energy_error"]))
        and math.isfinite(float(row["final_norm"]))
        and all(math.isfinite(float(value)) for value in row["late_means"].values())
        for row in rows
    )
    controls_pass = bool(
        controls[0]["late_means"]["center_deficit"] < 1.0e-10
        and controls[0]["late_means"]["fermion_norm"] > 0.0
        and controls[1]["late_means"]["center_deficit"] < 1.0e-10
        and controls[1]["late_means"]["fermion_norm"] < 1.0e-10
    )
    candidate_pass = bool(all(row["captured"] for row in candidate_rows))
    resolution_pass = bool(all(item["pass"] for item in adjacent))
    numerical_pass = bool(finite_pass and controls_pass and resolution_pass)
    scientific_verdict = "CAPTURED—conditional radial fermion-bag formation" if numerical_pass and candidate_pass else ("DOES NOT EMERGE—conditional radial fermion-bag formation" if numerical_pass else "INCONCLUSIVE")
    checks = [
        {"name": "source_identity", "pass": True, "sources": source_identities},
        {"name": "finite_payload", "pass": finite_pass},
        {"name": "controls", "pass": controls_pass},
        {"name": "resolution", "pass": resolution_pass, "comparisons": adjacent},
        {"name": "candidate_rows", "pass": candidate_pass, "captured": [row["grid"] for row in candidate_rows if row["captured"]]},
    ]
    receipt = {
        "schema": SCHEMA,
        "numerical_pass": numerical_pass,
        "verdict": scientific_verdict,
        "complete_physical_matter_formation": False,
        "three_dimensional_radial_mechanism_witness": bool(numerical_pass and candidate_pass),
        "identities": {"sources": source_identities, "archived_source_sha256": source_hashes, "constants": {"v": V, "lambda": LAMBDA, "g": G_YUKAWA, "kappa": KAPPA, "R": RADIUS, "T": FINAL_TIME, "core_radius": CORE_RADIUS, "grids": GRIDS}},
        "rows": rows,
        "checks": checks,
        "failures": [check["name"] for check in checks if not check["pass"]],
        "scope": "3D spherical kappa=-1 radial channel, supplied one-fermion degree-zero packet; no vacuum creation or all-sector claim",
    }
    write_json_exclusive(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = run(args.output_dir.resolve())
    except (FileExistsError, OSError, ValueError, FloatingPointError) as exc:
        print(f"fermion-bag primary failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output_dir.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
