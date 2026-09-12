#!/usr/bin/env python3
"""Independent DOP853 verification for radial fermion-bag capture."""
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
PRIMARY = COMPUTATIONS / "matter_formation_fermion_bag_capture.py"
PREREG = COMPUTATIONS / "matter-formation-fermion-bag-capture-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-bag-capture-verification.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.fermion-bag-capture.v1"
V = 1.0
LAMBDA = 0.25
G_YUKAWA = 6.0
KAPPA = -1.0
RADIUS = 16.0
FINAL_TIME = 24.0
SAMPLE_DT = 0.1
CORE_RADIUS = 4.0
VACUUM_MASS = G_YUKAWA * V
RAW_TOL = 2.0e-4
SUMMARY_TOL = 5.0e-4
GRIDS = {
    "G0": (160, 0.1, 0.02),
    "G1": (240, 1.0 / 15.0, 0.01),
    "G2": (320, 0.05, 0.005),
}
LATE_START = 16.0
EXPECTED_ARMS = ("G0_capture", "G1_capture", "G2_capture", "G1_g_zero", "G1_packet_zero")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha(path: Path) -> str:
    return sha256_bytes(canonical_bytes(path.read_bytes()))


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


def source_identity(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(), "sha256": canonical_sha(path)}


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


def apply_hamiltonian(psi: np.ndarray, sigma: np.ndarray, dr: float, coupling: float) -> np.ndarray:
    n = sigma.size
    upper = psi[:n]
    lower = psi[n:]
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    return np.concatenate((
        coupling * sigma * upper - derivative(lower, dr) + KAPPA * lower / r,
        derivative(upper, dr) + KAPPA * upper / r - coupling * sigma * lower,
    ))


def dense_hamiltonian(sigma: np.ndarray, dr: float, coupling: float) -> np.ndarray:
    n = sigma.size
    hamiltonian = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    indices = np.arange(n)
    hamiltonian[indices, indices] = coupling * sigma
    hamiltonian[n + indices, n + indices] = -coupling * sigma
    radius = (indices + 0.5) * dr
    step = 1.0 / (2.0 * dr)
    for i in range(n - 1):
        hamiltonian[i, n + i + 1] -= step
        hamiltonian[i + 1, n + i] += step
        hamiltonian[n + i, i + 1] += step
        hamiltonian[n + i + 1, i] -= step
    hamiltonian[indices, n + indices] += KAPPA / radius
    hamiltonian[n + indices, indices] += KAPPA / radius
    return hamiltonian


def initial_spinor(n: int, dr: float, coupling: float, zero: bool = False) -> np.ndarray:
    if zero:
        return np.zeros(2 * n, dtype=np.complex128)
    hamiltonian = dense_hamiltonian(np.ones(n, dtype=np.float64) * V, dr, coupling)
    values, vectors = np.linalg.eigh(hamiltonian)
    positive = vectors[:, values > 0.0]
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    trial = np.zeros(2 * n, dtype=np.complex128)
    trial[:n] = radius * np.exp(-0.5 * ((radius - 1.2) / 0.6) ** 2)
    state = positive @ (positive.conj().T @ trial)
    norm = math.sqrt(float(np.sum(np.abs(state) ** 2) * dr))
    if norm <= 0.0 or not math.isfinite(norm):
        raise ValueError("positive-energy projection failed")
    return state / norm


def unpack(state: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sigma = state[:n].real
    pi = state[n : 2 * n].real
    psi = state[2 * n : 4 * n] + 1j * state[4 * n : 6 * n]
    return sigma, pi, psi


def pack(sigma: np.ndarray, pi: np.ndarray, psi: np.ndarray) -> np.ndarray:
    return np.concatenate((sigma, pi, psi.real, psi.imag)).astype(np.float64)


def rhs(t: float, state: np.ndarray, n: int, dr: float, volume: np.ndarray, area: np.ndarray, coupling: float) -> np.ndarray:
    del t
    sigma, pi, psi = unpack(state, n)
    density = (np.abs(psi[:n]) ** 2 - np.abs(psi[n:]) ** 2) / (4.0 * math.pi * ((np.arange(n, dtype=np.float64) + 0.5) * dr) ** 2)
    scalar_accel = scalar_laplacian(sigma, dr, volume, area) - LAMBDA * (sigma * sigma - V * V) * sigma - coupling * density
    psi_dot = -1j * apply_hamiltonian(psi, sigma, dr, coupling)
    return pack(pi, scalar_accel, psi_dot)


def scalar_potential(sigma: np.ndarray) -> np.ndarray:
    return 0.25 * LAMBDA * (sigma * sigma - V * V) ** 2


def energy(sigma: np.ndarray, pi: np.ndarray, psi: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray, coupling: float) -> tuple[float, float, float, float]:
    scalar_kinetic = 0.5 * float(np.sum(volume * pi * pi))
    scalar_pot = float(np.sum(volume * scalar_potential(sigma)))
    internal = 0.5 * float(np.sum(area[1:-1] * (sigma[1:] - sigma[:-1]) ** 2 / dr))
    outer = 0.5 * float(area[-1] * (sigma[-1] - V) ** 2 / (0.5 * dr))
    scalar_total = scalar_kinetic + scalar_pot + internal + outer
    fermion = float(np.real(np.vdot(psi, apply_hamiltonian(psi, sigma, dr, coupling)) * dr))
    return scalar_total + fermion, scalar_total, fermion, float(np.sum(np.abs(psi) ** 2) * dr)


def observables(sigma: np.ndarray, pi: np.ndarray, psi: np.ndarray, r: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray, coupling: float) -> dict[str, float]:
    n = r.size
    probability = np.abs(psi[:n]) ** 2 + np.abs(psi[n:]) ** 2
    norm = float(np.sum(probability) * dr)
    core = r < CORE_RADIUS
    total, scalar_total, fermion, hnorm = energy(sigma, pi, psi, dr, volume, area, coupling)
    scalar_density = 0.5 * pi * pi + scalar_potential(sigma)
    gradient = np.zeros_like(sigma)
    gradient[:-1] = 0.5 * (sigma[1:] - sigma[:-1]) ** 2 / dr**2
    gradient[-1] = 0.5 * (sigma[-1] - V) ** 2 / (0.5 * dr) ** 2
    outer = r > 12.0
    return {
        "total_energy": total,
        "scalar_energy": scalar_total,
        "fermion_energy": fermion,
        "fermion_norm": hnorm,
        "core_probability": float(np.sum(probability[core]) * dr),
        "fermion_rms": math.sqrt(float(np.sum(r * r * probability) * dr) / max(norm, 1.0e-30)),
        "center_deficit": float(1.0 - sigma[0]),
        "outer_scalar_energy_fraction": float(np.sum(volume[outer] * (scalar_density[outer] + gradient[outer])) / max(abs(total), 1.0)),
    }


def row_from_arrays(time: np.ndarray, sigma: np.ndarray, pi: np.ndarray, psi_re: np.ndarray, psi_im: np.ndarray, n: int, dr: float, coupling: float, volume: np.ndarray, area: np.ndarray, r: np.ndarray, arm: str) -> dict[str, Any]:
    metrics = []
    for index in range(time.size):
        psi = psi_re[index] + 1j * psi_im[index]
        metrics.append(observables(sigma[index], pi[index], psi, r, dr, volume, area, coupling))
    arrays = {key: np.asarray([item[key] for item in metrics], dtype=np.float64) for key in metrics[0]}
    late = time >= LATE_START - 1.0e-12
    late_means = {key: float(np.mean(value[late])) for key, value in arrays.items()}
    late_std = {key: float(np.std(value[late])) for key, value in arrays.items()}
    initial_energy = float(arrays["total_energy"][0])
    max_error = float(np.max(np.abs(arrays["total_energy"] - initial_energy)))
    return {
        "arm": arm,
        "N": int(n),
        "dr": float(dr),
        "dt": float(time[1] - time[0]) if time.size > 1 else None,
        "coupling": float(coupling),
        "steps": int(round(FINAL_TIME / (time[1] - time[0]))) if time.size > 1 else 0,
        "duration": FINAL_TIME,
        "initial_energy": initial_energy,
        "final_energy": float(arrays["total_energy"][-1]),
        "max_energy_error": max_error,
        "relative_energy_error": max_error / max(1.0, abs(initial_energy)),
        "final_norm": float(arrays["fermion_norm"][-1]),
        "late_means": late_means,
        "late_std": late_std,
    }


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


def independent_evolve(n: int, dr: float, dt: float, coupling: float, psi0: np.ndarray, output: Path, arm: str) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    r, _, volume, area = grid_arrays(n, dr)
    sigma0 = np.ones(n, dtype=np.float64) * V
    pi0 = np.zeros(n, dtype=np.float64)
    t_eval = np.arange(int(round(FINAL_TIME / SAMPLE_DT)) + 1, dtype=np.float64) * SAMPLE_DT
    initial = pack(sigma0, pi0, psi0)
    solution = solve_ivp(
        lambda t, y: rhs(t, y, n, dr, volume, area, coupling),
        (0.0, FINAL_TIME),
        initial,
        method="DOP853",
        t_eval=t_eval,
        rtol=2.0e-9,
        atol=2.0e-11,
        max_step=0.05,
    )
    if not solution.success:
        raise RuntimeError(f"DOP853 failed for {arm}: {solution.message}")
    sigma = solution.y[:n].T
    pi = solution.y[n : 2 * n].T
    psi_re = solution.y[2 * n : 4 * n].T
    psi_im = solution.y[4 * n : 6 * n].T
    archive = output / f"independent_{arm}.npz"
    with archive.open("xb") as stream:
        np.savez_compressed(stream, time=t_eval, sigma=sigma, pi=pi, psi_re=psi_re, psi_im=psi_im)
    row = row_from_arrays(t_eval, sigma, pi, psi_re, psi_im, n, dr, coupling, volume, area, r, arm)
    return row, {"time": t_eval, "sigma": sigma, "pi": pi, "psi_re": psi_re, "psi_im": psi_im}


def raw_archive(input_dir: Path, arm: str) -> dict[str, np.ndarray]:
    path = input_dir / f"{arm}.npz"
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as archive:
        expected = {"time", "sigma", "pi", "psi_re", "psi_im"}
        if set(archive.files) != expected:
            raise ValueError(f"unexpected archive keys for {arm}: {archive.files}")
        values = {key: np.asarray(archive[key]) for key in archive.files}
    if any(value.dtype != np.float64 or not np.all(np.isfinite(value)) for value in values.values()):
        raise ValueError(f"nonfinite or non-float64 primary archive: {arm}")
    return values


def compare_arrays(primary: dict[str, np.ndarray], independent: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    result = []
    for key in ("time", "sigma", "pi", "psi_re", "psi_im"):
        if primary[key].shape != independent[key].shape:
            result.append({"array": key, "pass": False, "reason": "shape", "primary": primary[key].shape, "independent": independent[key].shape})
            continue
        error = float(np.max(np.abs(primary[key] - independent[key])))
        result.append({"array": key, "pass": bool(error <= RAW_TOL if key != "time" else error == 0.0), "maximum_absolute_error": error, "threshold": RAW_TOL if key != "time" else 0.0})
    return result


def failure_receipt(output: Path, message: str) -> dict[str, Any]:
    receipt = {"schema": SCHEMA, "numerical_pass": False, "verdict": "INCONCLUSIVE", "complete_physical_matter_formation": False, "failures": [message], "rows": [], "independent_checks": []}
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
    source_expected = {"primary": source_identity(PRIMARY), "prereg": source_identity(PREREG)}
    source_pass = primary_receipt.get("schema") == PRIMARY_SCHEMA and primary_receipt.get("identities", {}).get("sources") == source_expected
    if not source_pass:
        return failure_receipt(output_path, "primary source identity or schema mismatch")
    output_dir = output_path.parent
    source_dir = output_dir / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    archived_sources: dict[str, str] = {}
    for path in (SELF, PREREG):
        target = source_dir / path.resolve().relative_to(ROOT.resolve()).as_posix().replace("/", "__")
        shutil.copyfile(path, target)
        archived_sources[path.resolve().relative_to(ROOT.resolve()).as_posix()] = raw_sha(target)
    rows = []
    comparisons = []
    independent_checks = []
    g1_packet = initial_spinor(GRIDS["G1"][0], GRIDS["G1"][1], G_YUKAWA)
    for arm in EXPECTED_ARMS:
        if arm.endswith("capture"):
            grid = arm[:2]
            coupling = G_YUKAWA
            n, dr, dt = GRIDS[grid]
            psi0 = initial_spinor(n, dr, coupling)
        elif arm == "G1_g_zero":
            grid = "G1"
            coupling = 0.0
            n, dr, dt = GRIDS[grid]
            psi0 = g1_packet
        else:
            grid = "G1"
            coupling = G_YUKAWA
            n, dr, dt = GRIDS[grid]
            psi0 = initial_spinor(n, dr, coupling, zero=True)
        primary_arrays = raw_archive(input_dir, arm)
        independent_row, independent_arrays = independent_evolve(n, dr, dt, coupling, psi0, output_dir, arm)
        comparison = compare_arrays(primary_arrays, independent_arrays)
        comparisons.extend({"arm": arm, **item} for item in comparison)
        r, _, volume, area = grid_arrays(n, dr)
        primary_row = row_from_arrays(primary_arrays["time"], primary_arrays["sigma"], primary_arrays["pi"], primary_arrays["psi_re"], primary_arrays["psi_im"], n, dr, coupling, volume, area, r, arm)
        row_errors = []
        for key in ("relative_energy_error", "final_norm"):
            error = abs(primary_row[key] - independent_row[key])
            row_errors.append({"field": key, "error": error, "pass": error <= SUMMARY_TOL})
        for key in primary_row["late_means"]:
            error = abs(primary_row["late_means"][key] - independent_row["late_means"][key])
            row_errors.append({"field": f"late_means.{key}", "error": error, "pass": error <= SUMMARY_TOL})
        for key in primary_row["late_std"]:
            error = abs(primary_row["late_std"][key] - independent_row["late_std"][key])
            row_errors.append({"field": f"late_std.{key}", "error": error, "pass": error <= SUMMARY_TOL})
        independent_checks.append({"arm": arm, "raw": comparison, "summary": row_errors, "pass": all(item["pass"] for item in comparison + row_errors)})
        independent_row["grid"] = grid
        independent_row["candidate"] = arm.endswith("capture")
        independent_row["captured"] = capture_predicate(independent_row)
        rows.append(independent_row)
    candidate_rows = [row for row in rows if row["candidate"]]
    controls = [row for row in rows if not row["candidate"]]
    resolution = []
    for left, right in zip(candidate_rows, candidate_rows[1:]):
        for key in ("core_probability", "fermion_rms", "fermion_energy", "center_deficit"):
            difference = abs(left["late_means"][key] - right["late_means"][key])
            resolution.append({"left": left["grid"], "right": right["grid"], "observable": key, "difference": difference, "pass": difference <= 0.10})
    control_pass = bool(
        controls[0]["late_means"]["center_deficit"] < 1.0e-10
        and controls[0]["late_means"]["fermion_norm"] > 0.0
        and controls[1]["late_means"]["center_deficit"] < 1.0e-10
        and controls[1]["late_means"]["fermion_norm"] < 1.0e-10
    )
    raw_pass = bool(all(item["pass"] for item in comparisons))
    summary_pass = bool(all(item["pass"] for check in independent_checks for item in check["summary"]))
    resolution_pass = bool(all(item["pass"] for item in resolution))
    candidate_pass = bool(all(row["captured"] for row in candidate_rows))
    numerical_pass = bool(source_pass and raw_pass and summary_pass and control_pass and resolution_pass)
    verdict = "CAPTURED—conditional radial fermion-bag formation" if numerical_pass and candidate_pass else ("DOES NOT EMERGE—conditional radial fermion-bag formation" if numerical_pass else "INCONCLUSIVE")
    receipt = {
        "schema": SCHEMA,
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "three_dimensional_radial_mechanism_witness": bool(numerical_pass and candidate_pass),
        "identities": {"primary": source_expected["primary"], "verifier": source_identity(SELF), "prereg": source_expected["prereg"], "archived_source_sha256": archived_sources},
        "rows": rows,
        "raw_comparisons": comparisons,
        "independent_checks": independent_checks,
        "resolution": resolution,
        "controls_pass": control_pass,
        "scope": "3D spherical kappa=-1 radial channel, supplied one-fermion degree-zero packet; no vacuum creation or all-sector claim",
        "failures": [name for name, passed in (("source", source_pass), ("raw", raw_pass), ("summary", summary_pass), ("controls", control_pass), ("resolution", resolution_pass)) if not passed],
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
        print(f"fermion-bag verifier failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
