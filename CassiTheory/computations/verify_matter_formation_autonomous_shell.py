#!/usr/bin/env python3
"""Independent DOP853 verification for autonomous incoming-shell formation."""
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
SELF = Path(__file__).resolve()
PRIMARY = ROOT / "computations" / "matter_formation_autonomous_shell.py"
ACTION_PREREG = ROOT / "computations" / "matter-formation-autonomous-shell-g3-prereg.md"
PREREG = ROOT / "computations" / "matter-formation-autonomous-shell-g3-stability-prereg.md"
SCHEMA = "cassi.matter-formation.autonomous-shell-verification.v6"
PRIMARY_SCHEMA = "cassi.matter-formation.autonomous-shell.v6"
V = 1.0
LAMBDA = 0.25
G = 3.0
RADIUS = 16.0
AMPLITUDE = 0.75
SHELL_CENTER = 4.0
WIDTH = 2.0
FINAL_TIME = 12.0
SAMPLE_DT = 0.1
LATE_START = 8.0
CORE_RADIUS = 4.0
CORE_SMOOTH = 0.5
BOUND_ENERGY_MAX = 1.5
PAIR_EPS = 1.0e-12
RAW_TOL = 5.0e-4
PROJECTOR_TOL = 1.0e-3
SUMMARY_TOL = 2.0e-3
GRIDS = {"G0": (48, RADIUS / 48.0, 0.004), "G1": (72, RADIUS / 72.0, 0.002), "G2": (96, RADIUS / 96.0, 0.001)}


class VerificationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def raw_sha(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


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


def as_json(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [as_json(v) for v in value.tolist()]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): as_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_json(v) for v in value]
    return value


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise VerificationError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(as_json(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_npz_exclusive(path: Path, arrays: dict[str, np.ndarray]) -> str:
    if path.exists():
        raise VerificationError(f"refusing to overwrite {path}")
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return raw_sha(path)


def grid_arrays(n: int, dr: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    face = np.arange(n + 1, dtype=np.float64) * dr
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volume = (4.0 * math.pi / 3.0) * (face[1:] ** 3 - face[:-1] ** 3)
    area = 4.0 * math.pi * face * face
    return radius, face, volume, area


def derivative(values: np.ndarray, dr: float) -> np.ndarray:
    result = np.empty_like(values)
    result[0] = values[1] / (2.0 * dr)
    result[1:-1] = (values[2:] - values[:-2]) / (2.0 * dr)
    result[-1] = -values[-2] / (2.0 * dr)
    return result


def laplacian(sigma: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray) -> np.ndarray:
    flux = np.zeros(sigma.size + 1, dtype=np.float64)
    flux[1:-1] = area[1:-1] * (sigma[1:] - sigma[:-1]) / dr
    flux[-1] = area[-1] * (V - sigma[-1]) / (0.5 * dr)
    return (flux[1:] - flux[:-1]) / volume


def potential(sigma: np.ndarray) -> np.ndarray:
    return 0.25 * LAMBDA * (sigma * sigma - V * V) ** 2


def hamiltonian(sigma: np.ndarray, dr: float) -> np.ndarray:
    n = sigma.size
    h = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    idx = np.arange(n)
    h[idx, idx] = G * sigma
    h[n + idx, n + idx] = -G * sigma
    d = 1.0 / (2.0 * dr)
    for i in range(n - 1):
        h[i, n + i + 1] += -d
        h[i + 1, n + i] += d
        h[n + i, i + 1] += d
        h[n + i + 1, i] += -d
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    radial_connection = 1.0 / np.sqrt(radius * radius + CORE_SMOOTH * CORE_SMOOTH)
    h[idx, n + idx] -= radial_connection
    h[n + idx, idx] -= radial_connection
    if float(np.max(np.abs(h - h.conj().T))) > 1.0e-13:
        raise VerificationError("independent Hamiltonian is not Hermitian")
    return h


def initial_scalar(radius: np.ndarray, homogeneous: bool) -> tuple[np.ndarray, np.ndarray]:
    if homogeneous:
        return np.ones_like(radius), np.zeros_like(radius)
    x = radius - SHELL_CENTER
    gaussian = np.exp(-0.5 * (x / WIDTH) ** 2)
    return V - AMPLITUDE * gaussian, AMPLITUDE * x / (WIDTH * WIDTH) * gaussian


def initial_state(n: int, dr: float, homogeneous: bool, zero_covariance: bool) -> dict[str, Any]:
    radius, _, volume, area = grid_arrays(n, dr)
    sigma0, pi0 = initial_scalar(radius, homogeneous)
    h0 = hamiltonian(sigma0, dr)
    values, vectors = np.linalg.eigh(h0)
    negative = values < -1.0e-10
    positive = values > 1.0e-10
    if int(np.count_nonzero(negative)) != n or int(np.count_nonzero(positive)) != n:
        raise VerificationError("independent initial spectrum split failed")
    modes0 = vectors[:, negative] / math.sqrt(dr)
    modes = np.zeros_like(modes0) if zero_covariance else modes0.copy()
    metric = float(np.max(np.abs(dr * (modes0.conj().T @ modes0) - np.eye(n))))
    if metric > 2.0e-12:
        raise VerificationError(f"independent initial metric error {metric}")
    source0 = dr * np.sum(np.abs(modes0[:n]) ** 2 - np.abs(modes0[n:]) ** 2, axis=1) / volume
    return {"radius": radius, "volume": volume, "area": area, "sigma0": sigma0, "pi0": pi0, "h0": h0, "modes0": modes0, "modes": modes, "source0": source0, "dr": dr, "metric": metric}


def source(modes: np.ndarray, modes0: np.ndarray, dr: float, volume: np.ndarray) -> np.ndarray:
    n = volume.size
    now = np.sum(np.abs(modes[:n]) ** 2 - np.abs(modes[n:]) ** 2, axis=1)
    base = np.sum(np.abs(modes0[:n]) ** 2 - np.abs(modes0[n:]) ** 2, axis=1)
    return dr * (now - base) / volume


def apply_hamiltonian(modes: np.ndarray, sigma: np.ndarray, dr: float) -> np.ndarray:
    n = sigma.size
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    radial_connection = 1.0 / np.sqrt(radius * radius + CORE_SMOOTH * CORE_SMOOTH)
    upper = modes[:n]
    lower = modes[n:]
    upper_out = G * sigma[:, None] * upper - derivative(lower, dr) - radial_connection[:, None] * lower
    lower_out = derivative(upper, dr) - radial_connection[:, None] * upper - G * sigma[:, None] * lower
    return np.concatenate((upper_out, lower_out), axis=0)


def rhs_real(_time: float, state_vector: np.ndarray, state: dict[str, Any], source_enabled: bool) -> np.ndarray:
    n = state["radius"].size
    matrix_size = 2 * n * n
    sigma = state_vector[:n]
    pi = state_vector[n : 2 * n]
    start = 2 * n
    modes = state_vector[start : start + matrix_size].reshape(2 * n, n) + 1j * state_vector[start + matrix_size : start + 2 * matrix_size].reshape(2 * n, n)
    source_now = source(modes, state["modes0"], state["dr"], state["volume"]) if source_enabled else 0.0
    acceleration = laplacian(sigma, state["dr"], state["volume"], state["area"]) - LAMBDA * (sigma * sigma - V * V) * sigma - G * source_now
    mode_dot = -1j * apply_hamiltonian(modes, sigma, state["dr"])
    return np.concatenate((pi, acceleration, mode_dot.real.ravel(), mode_dot.imag.ravel()))


def pack(sigma: np.ndarray, pi: np.ndarray, modes: np.ndarray) -> np.ndarray:
    return np.concatenate((sigma, pi, modes.real.ravel(), modes.imag.ravel()))


def unpack(vector: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix_size = 2 * n * n
    start = 2 * n
    sigma = vector[:n]
    pi = vector[n : 2 * n]
    modes = vector[start : start + matrix_size].reshape(2 * n, n) + 1j * vector[start + matrix_size : start + 2 * matrix_size].reshape(2 * n, n)
    return sigma, pi, modes


def scalar_energy(sigma: np.ndarray, pi: np.ndarray, state: dict[str, Any]) -> float:
    dr = state["dr"]
    kinetic = 0.5 * float(np.sum(state["volume"] * pi * pi))
    potential_energy = float(np.sum(state["volume"] * potential(sigma)))
    internal = 0.5 * float(np.sum(state["area"][1:-1] * (sigma[1:] - sigma[:-1]) ** 2 / dr))
    outer = 0.5 * float(state["area"][-1] * (sigma[-1] - V) ** 2 / (0.5 * dr))
    return kinetic + potential_energy + internal + outer


def energy(sigma: np.ndarray, pi: np.ndarray, modes: np.ndarray, state: dict[str, Any]) -> tuple[float, float, float, float]:
    dynamic = float(np.real(np.trace(modes.conj().T @ hamiltonian(sigma, state["dr"]) @ modes)) * state["dr"])
    initial = float(np.real(np.trace(state["modes0"].conj().T @ state["h0"] @ state["modes0"])) * state["dr"])
    counterterm = float(G * np.sum(state["volume"] * state["source0"] * (sigma - state["sigma0"])))
    fermion = dynamic - initial - counterterm
    scalar = scalar_energy(sigma, pi, state)
    norm = float(np.real(np.trace(modes.conj().T @ modes)) * state["dr"])
    return scalar + fermion, scalar, fermion, norm


def metrics(sigma: np.ndarray, pi: np.ndarray, modes: np.ndarray, state: dict[str, Any]) -> dict[str, float]:
    n = state["radius"].size
    dr = state["dr"]
    values, vectors = np.linalg.eigh(hamiltonian(sigma, dr))
    positive = values > 1.0e-10
    negative = values < -1.0e-10
    p = vectors[:, positive] / math.sqrt(dr)
    q = vectors[:, negative] / math.sqrt(dr)
    coeff = dr * (p.conj().T @ modes)
    particles = p @ coeff
    density = np.sum(np.abs(particles[:n]) ** 2 + np.abs(particles[n:]) ** 2, axis=1)
    pair = float(np.sum(np.abs(coeff) ** 2))
    holes = dr * (q.conj().T @ modes)
    hole = float(n - np.sum(np.abs(holes) ** 2))
    bound_mask = (values > 1.0e-10) & (values <= BOUND_ENERGY_MAX)
    bound_count = int(np.count_nonzero(bound_mask))
    if bound_count:
        bound = vectors[:, bound_mask] / math.sqrt(dr)
        bound_hole = q[:, -bound_count:]
        bound_coeff = dr * (bound.conj().T @ modes)
        hole_coeff = dr * (bound_hole.conj().T @ modes)
        bound_density = np.sum(np.abs(bound[:n]) ** 2 + np.abs(bound[n:]) ** 2, axis=1)
        bound_occupation = float(np.sum(np.abs(bound_coeff) ** 2))
        bound_hole_occupation = float(bound_count - np.sum(np.abs(hole_coeff) ** 2))
    else:
        bound_density = np.zeros(n, dtype=np.float64)
        bound_occupation = 0.0
        bound_hole_occupation = 0.0
    core = state["radius"] < CORE_RADIUS
    pair_core = float(np.sum(density[core]) * dr / pair) if pair > PAIR_EPS else 0.0
    pair_rms = math.sqrt(float(np.sum(state["radius"] ** 2 * density) * dr / pair)) if pair > PAIR_EPS else 0.0
    bound_norm = float(np.sum(bound_density) * dr)
    bound_core = float(np.sum(bound_density[core]) * dr / bound_norm) if bound_norm > PAIR_EPS else 0.0
    bound_rms = math.sqrt(float(np.sum(state["radius"] ** 2 * bound_density) * dr / bound_norm)) if bound_norm > PAIR_EPS else 0.0
    total, scalar, fermion, mode_norm = energy(sigma, pi, modes, state)
    scalar_density = 0.5 * pi * pi + potential(sigma)
    gradient = np.zeros_like(sigma)
    gradient[:-1] = 0.5 * (sigma[1:] - sigma[:-1]) ** 2 / dr**2
    gradient[-1] = 0.5 * (sigma[-1] - V) ** 2 / (0.5 * dr) ** 2
    scalar_density += gradient
    outer = state["radius"] > 12.0
    outer_fraction = float(np.sum(state["volume"][outer] * scalar_density[outer]) / max(scalar, 1.0e-30))
    return {
        "total_energy": total, "scalar_energy": scalar, "fermion_energy": fermion, "mode_norm": mode_norm,
        "pair_number": pair, "hole_number": hole, "pair_hole_gap": abs(pair - hole),
        "bound_occupation": bound_occupation, "bound_hole_occupation": bound_hole_occupation,
        "bound_hole_gap": abs(bound_occupation - bound_hole_occupation), "pair_core_probability": pair_core,
        "pair_rms": pair_rms, "bound_core_probability": bound_core, "bound_rms": bound_rms,
        "bound_energy": float(np.mean(values[bound_mask])) if bound_count else 0.0,
        "negative_bound_energy": float(np.mean(values[negative][-bound_count:])) if bound_count else 0.0,
        "center_deficit": float(1.0 - sigma[0]), "outer_scalar_energy_fraction": outer_fraction,
    }


def expected_arms() -> list[str]:
    return [f"shell_{grid}" for grid in GRIDS] + ["static_vacuum", "source_off", "zero_covariance"]


def arm_spec(arm: str) -> tuple[str, bool, bool, bool]:
    if arm == "static_vacuum":
        return "G1", True, False, False
    if arm == "source_off":
        return "G1", False, False, False
    if arm == "zero_covariance":
        return "G1", False, False, True
    if arm.startswith("shell_") and arm[-2:] in GRIDS:
        return arm[-2:], False, True, False
    raise VerificationError(f"unexpected arm {arm}")


def read_primary_archive(input_dir: Path, arm: str, n: int) -> dict[str, np.ndarray]:
    path = input_dir / f"{arm}.npz"
    if not path.is_file():
        raise VerificationError(f"missing primary archive {path}")
    with np.load(path, allow_pickle=False) as archive:
        expected = {"time", "sigma", "pi", "u_re", "u_im"}
        if set(archive.files) != expected:
            raise VerificationError(f"unexpected primary keys for {arm}: {archive.files}")
        arrays = {key: np.asarray(archive[key]) for key in archive.files}
    count = int(round(FINAL_TIME / SAMPLE_DT)) + 1
    expected_shapes = {"time": (count,), "sigma": (count, n), "pi": (count, n), "u_re": (count, 2 * n, n), "u_im": (count, 2 * n, n)}
    for key, shape in expected_shapes.items():
        if arrays[key].shape != shape or arrays[key].dtype != np.float64 or not np.isfinite(arrays[key]).all():
            raise VerificationError(f"invalid primary archive {arm}.{key}: {arrays[key].shape}")
    expected_time = np.arange(count, dtype=np.float64) * SAMPLE_DT
    if not np.allclose(arrays["time"], expected_time, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"invalid primary times for {arm}")
    return arrays


def independent_evolve(output: Path, arm: str, grid: str, homogeneous: bool, source_enabled: bool, zero_covariance: bool) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    n, dr, dt = GRIDS[grid]
    state = initial_state(n, dr, homogeneous, zero_covariance)
    times = np.arange(int(round(FINAL_TIME / SAMPLE_DT)) + 1, dtype=np.float64) * SAMPLE_DT
    solution = solve_ivp(lambda t, y: rhs_real(t, y, state, source_enabled), (0.0, FINAL_TIME), pack(state["sigma0"], state["pi0"], state["modes"]), method="DOP853", t_eval=times, rtol=2.0e-8, atol=2.0e-10, max_step=0.02)
    if not solution.success:
        raise VerificationError(f"DOP853 failed for {arm}: {solution.message}")
    if solution.t.shape != times.shape or abs(float(solution.t[-1]) - FINAL_TIME) > 1.0e-10 or not np.isfinite(solution.y).all():
        raise VerificationError(f"invalid DOP853 endpoint or state for {arm}")
    sigma_archive = np.asarray(solution.y[:n].T, dtype=np.float64)
    pi_archive = np.asarray(solution.y[n : 2 * n].T, dtype=np.float64)
    matrix_size = 2 * n * n
    start = 2 * n
    real = solution.y[start : start + matrix_size].T.reshape(-1, 2 * n, n)
    imag = solution.y[start + matrix_size : start + 2 * matrix_size].T.reshape(-1, 2 * n, n)
    modes_archive = real + 1j * imag
    raw = {"time": times, "sigma": sigma_archive, "pi": pi_archive, "u_re": np.asarray(modes_archive.real, dtype=np.float64), "u_im": np.asarray(modes_archive.imag, dtype=np.float64)}
    archive_hash = write_npz_exclusive(output / f"independent_{arm}.npz", raw)
    diagnostics = [metrics(sigma_archive[i], pi_archive[i], modes_archive[i], state) for i in range(times.size)]
    values = {key: np.asarray([row[key] for row in diagnostics], dtype=np.float64) for key in diagnostics[0]}
    late = times >= LATE_START - 1.0e-12
    initial_energy = float(values["total_energy"][0])
    error = np.abs(values["total_energy"] - initial_energy)
    row: dict[str, Any] = {
        "arm": arm, "grid": grid, "N": n, "dr": dr, "dt": dt, "steps": int(round(FINAL_TIME / dt)), "duration": FINAL_TIME,
        "initial_energy": initial_energy, "final_energy": float(values["total_energy"][-1]), "max_energy_error": float(np.max(error)),
        "relative_energy_error": float(np.max(error) / max(1.0, abs(initial_energy))),
        "late_means": {key: float(np.mean(value[late])) for key, value in values.items()}, "late_std": {key: float(np.std(value[late])) for key, value in values.items()},
        "candidate": arm.startswith("shell_"), "homogeneous": homogeneous, "source_enabled": source_enabled, "zero_covariance": zero_covariance,
        "initial_covariance_metric_error": state["metric"], "archive": f"independent_{arm}.npz", "archive_sha256": archive_hash,
    }
    row["captured"] = candidate_predicate(row) if row["candidate"] else False
    return row, raw


def candidate_predicate(row: dict[str, Any]) -> bool:
    late, spread = row["late_means"], row["late_std"]
    return bool(late["pair_number"] > 0.05 and late["bound_occupation"] > 0.10 and late["pair_hole_gap"] < 0.05 and late["bound_hole_gap"] < 0.05 and late["pair_core_probability"] > 0.50 and late["bound_core_probability"] > 0.50 and late["pair_rms"] < 5.0 and late["bound_rms"] < 5.0 and spread["pair_number"] <= 0.25 and spread["bound_occupation"] <= 0.25 and spread["pair_rms"] <= 0.75 and spread["bound_rms"] <= 0.75 and row["relative_energy_error"] <= 5.0e-3 and late["center_deficit"] >= 0.05)


def compare_arrays(primary: dict[str, np.ndarray], independent: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for key in ("time", "sigma", "pi"):
        if primary[key].shape != independent[key].shape:
            checks.append({"array": key, "maximum_absolute_error": math.inf, "threshold": 0.0, "pass": False, "reason": "shape"})
            continue
        error = float(np.max(np.abs(primary[key] - independent[key])))
        threshold = 1.0e-12 if key == "time" else RAW_TOL
        checks.append({"array": key, "maximum_absolute_error": error, "threshold": threshold, "pass": error <= threshold})
    primary_modes = primary["u_re"] + 1j * primary["u_im"]
    independent_modes = independent["u_re"] + 1j * independent["u_im"]
    if primary_modes.shape != independent_modes.shape:
        checks.append({"array": "occupied_mode_archive", "maximum_absolute_error": math.inf, "threshold": 0.0, "pass": False, "reason": "shape"})
    else:
        primary_projector = primary_modes @ np.conjugate(np.swapaxes(primary_modes, -1, -2))
        independent_projector = independent_modes @ np.conjugate(np.swapaxes(independent_modes, -1, -2))
        error = float(np.max(np.abs(primary_projector - independent_projector)))
        checks.append({"array": "occupied_covariance_projector", "maximum_absolute_error": error, "threshold": PROJECTOR_TOL, "pass": error <= PROJECTOR_TOL})
    return checks


def compare_summary(primary: dict[str, Any], independent: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for key in ("initial_energy", "final_energy", "max_energy_error", "relative_energy_error"):
        error = abs(float(primary[key]) - float(independent[key]))
        checks.append({"field": key, "error": error, "threshold": SUMMARY_TOL, "pass": error <= SUMMARY_TOL})
    for group in ("late_means", "late_std"):
        for key in primary[group]:
            error = abs(float(primary[group][key]) - float(independent[group][key]))
            checks.append({"field": f"{group}.{key}", "error": error, "threshold": SUMMARY_TOL, "pass": error <= SUMMARY_TOL})
    return checks


def resolution_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_grid = {row["grid"]: row for row in rows if row["candidate"]}
    result: list[dict[str, Any]] = []
    for left_grid, right_grid in (("G0", "G1"), ("G1", "G2")):
        for key, threshold in (("pair_number", 0.25), ("bound_occupation", 0.25), ("pair_core_probability", 0.15), ("bound_core_probability", 0.15), ("pair_rms", 0.50), ("bound_rms", 0.50)):
            difference = abs(by_grid[left_grid]["late_means"][key] - by_grid[right_grid]["late_means"][key])
            result.append({"left": left_grid, "right": right_grid, "observable": key, "difference": difference, "threshold": threshold, "pass": difference < threshold})
    return result


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PRIMARY, ACTION_PREREG, PREREG):
        target = source_dir / relative(path).replace("/", "__")
        shutil.copyfile(path, target)
        result[relative(path)] = raw_sha(target)
    return result


def failure_receipt(path: Path, message: str) -> dict[str, Any]:
    receipt = {"schema": SCHEMA, "numerical_pass": False, "verdict": "INCONCLUSIVE", "complete_physical_matter_formation": False, "failures": [message], "independent_checks": [], "state_comparisons": []}
    write_json_exclusive(path, receipt)
    return receipt


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise VerificationError(f"refusing existing verification receipt: {output_path}")
    primary_path = input_dir / "result.json"
    if not primary_path.is_file():
        return failure_receipt(output_path, "missing primary result.json")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    expected_identity = {"path": relative(PRIMARY), "sha256": canonical_sha(PRIMARY)}
    expected_action = {"path": relative(ACTION_PREREG), "sha256": canonical_sha(ACTION_PREREG)}
    expected_prereg = {"path": relative(PREREG), "sha256": canonical_sha(PREREG)}
    identity_pass = bool(primary.get("schema") == PRIMARY_SCHEMA and primary.get("identities", {}).get("primary") == expected_identity and primary.get("identities", {}).get("action_prereg") == expected_action and primary.get("identities", {}).get("prereg") == expected_prereg)
    if not identity_pass:
        return failure_receipt(output_path, "primary schema or source identity mismatch")
    output_dir = output_path.parent
    output_dir.mkdir(parents=False, exist_ok=True)
    archived = snapshot_sources(output_dir)
    expected = expected_arms()
    primary_rows = {row.get("arm"): row for row in primary.get("rows", [])}
    if set(primary_rows) != set(expected):
        return failure_receipt(output_path, "primary arm set mismatch")
    independent_rows: list[dict[str, Any]] = []
    independent_checks: list[dict[str, Any]] = []
    state_comparisons: list[dict[str, Any]] = []
    state_pass = True
    summary_pass = True
    for arm in expected:
        grid, homogeneous, source_enabled, zero_covariance = arm_spec(arm)
        n = GRIDS[grid][0]
        primary_arrays = read_primary_archive(input_dir, arm, n)
        row, independent_arrays = independent_evolve(output_dir, arm, grid, homogeneous, source_enabled, zero_covariance)
        primary_state = {key: primary_arrays[key] for key in ("time", "sigma", "pi", "u_re", "u_im")}
        state = compare_arrays(primary_state, independent_arrays)
        summary = compare_summary(primary_rows[arm], row)
        state_ok = all(item["pass"] for item in state)
        summary_ok = all(item["pass"] for item in summary)
        state_pass = state_pass and state_ok
        summary_pass = summary_pass and summary_ok
        state_comparisons.extend({"arm": arm, **item} for item in state)
        independent_checks.append({"arm": arm, "state": state, "summary": summary, "pass": state_ok and summary_ok})
        independent_rows.append(row)
    candidates = [row for row in independent_rows if row["candidate"]]
    controls = [row for row in independent_rows if not row["candidate"]]
    static = next(row for row in controls if row["arm"] == "static_vacuum")
    zero = next(row for row in controls if row["arm"] == "zero_covariance")
    controls_pass = bool(static["late_means"]["pair_number"] < 1.0e-10 and static["late_means"]["center_deficit"] < 1.0e-10 and zero["late_means"]["mode_norm"] < 1.0e-8 and zero["late_means"]["pair_number"] < 1.0e-8)
    resolution = resolution_rows(independent_rows)
    resolution_pass = all(item["pass"] for item in resolution)
    finite_pass = all(finite_json(row) for row in independent_rows)
    candidate_pass = all(row["captured"] for row in candidates)
    numerical_pass = bool(identity_pass and finite_pass and state_pass and summary_pass and controls_pass and resolution_pass)
    verdict = "CAPTURED—conditional autonomous radial formation" if numerical_pass and candidate_pass else "DOES NOT EMERGE—conditional autonomous radial formation" if numerical_pass else "INCONCLUSIVE"
    receipt = {
        "schema": SCHEMA, "numerical_pass": numerical_pass, "verdict": verdict, "complete_physical_matter_formation": False,
        "autonomous_regulated_radial_mechanism": bool(numerical_pass and candidate_pass),
        "identities": {"primary": expected_identity, "verifier": {"path": relative(SELF), "sha256": canonical_sha(SELF)}, "action_prereg": expected_action, "prereg": expected_prereg, "archived_source_sha256": archived},
        "rows": independent_rows, "independent_checks": independent_checks, "state_comparisons": state_comparisons, "resolution": resolution,
        "checks": {"identity": identity_pass, "finite_payload": finite_pass, "state_reconstruction": state_pass, "summary_reconstruction": summary_pass, "controls": controls_pass, "resolution": resolution_pass, "candidate": candidate_pass},
        "scope": "finite-box spherical kappa=-1 covariance with self-consistent scalar backreaction from a prescribed finite-energy initial shell; no continuum or all-sector claim",
        "failures": [name for name, passed in (("identity", identity_pass), ("finite_payload", finite_pass), ("state_reconstruction", state_pass), ("summary_reconstruction", summary_pass), ("controls", controls_pass), ("resolution", resolution_pass)) if not passed],
    }
    write_json_exclusive(output_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = run(args.input_dir.resolve(), args.output.resolve())
    except (VerificationError, OSError, ValueError, RuntimeError) as exc:
        print(f"autonomous-shell verifier failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
