#!/usr/bin/env python3
"""Primary source-bound two-channel autonomous shell calculation."""
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
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "matter-formation-autonomous-shell-g3-two-channel-fourth-order-prereg.md"
SCHEMA = "cassi.matter-formation.autonomous-shell-g3-two-channel-fourth-order.v1"
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
RK4_SUBSTEPS = 8
PAIR_EPS = 1.0e-12
CHANNELS = (-1, 1)
DEGENERACY = {-1: 2.0, 1: 2.0}
GRIDS = {"G0": (48, RADIUS / 48.0, 0.004), "G1": (72, RADIUS / 72.0, 0.002), "G2": (96, RADIUS / 96.0, 0.001)}


class FormationError(RuntimeError):
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
        return all(isinstance(key, str) and finite_json(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_json(item) for item in value)
    return False


def as_json(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [as_json(item) for item in value.tolist()]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): as_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_json(item) for item in value]
    return value


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FormationError(f"refusing to overwrite {path}")
    if not finite_json(payload):
        raise FormationError(f"nonfinite receipt payload: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(as_json(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_npz_exclusive(path: Path, arrays: dict[str, np.ndarray]) -> str:
    if path.exists():
        raise FormationError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
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
    result = np.zeros_like(values)
    nearest = 2.0 / (3.0 * dr)
    next_nearest = -1.0 / (12.0 * dr)
    result[1:] += nearest * values[:-1]
    result[:-1] -= nearest * values[1:]
    result[2:] += next_nearest * values[:-2]
    result[:-2] -= next_nearest * values[2:]
    return result


def laplacian(sigma: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray) -> np.ndarray:
    flux = np.zeros(sigma.size + 1, dtype=np.float64)
    flux[1:-1] = area[1:-1] * (sigma[1:] - sigma[:-1]) / dr
    flux[-1] = area[-1] * (V - sigma[-1]) / (0.5 * dr)
    return (flux[1:] - flux[:-1]) / volume


def scalar_potential(sigma: np.ndarray) -> np.ndarray:
    return 0.25 * LAMBDA * (sigma * sigma - V * V) ** 2


def hamiltonian(sigma: np.ndarray, dr: float, kappa: int) -> np.ndarray:
    n = sigma.size
    h = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    idx = np.arange(n)
    h[idx, idx] = G * sigma
    h[n + idx, n + idx] = -G * sigma
    derivative_matrix = np.zeros((n, n), dtype=np.float64)
    nearest = 2.0 / (3.0 * dr)
    next_nearest = -1.0 / (12.0 * dr)
    for i in range(n - 1):
        derivative_matrix[i + 1, i] += nearest
        derivative_matrix[i, i + 1] -= nearest
    for i in range(n - 2):
        derivative_matrix[i + 2, i] += next_nearest
        derivative_matrix[i, i + 2] -= next_nearest
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    connection = kappa / np.sqrt(radius * radius + CORE_SMOOTH * CORE_SMOOTH)
    h[:n, n:] = -derivative_matrix
    h[n:, :n] = derivative_matrix
    h[idx, n + idx] += connection
    h[n + idx, idx] += connection
    if float(np.max(np.abs(h - h.conj().T))) > 1.0e-13:
        raise FormationError(f"non-Hermitian Hamiltonian for kappa={kappa}")
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
    channels: dict[int, dict[str, Any]] = {}
    source0 = np.zeros(n, dtype=np.float64)
    metric = 0.0
    for kappa in CHANNELS:
        h0 = hamiltonian(sigma0, dr, kappa)
        values, vectors = np.linalg.eigh(h0)
        negative = values < -1.0e-10
        positive = values > 1.0e-10
        if int(np.count_nonzero(negative)) != n or int(np.count_nonzero(positive)) != n:
            raise FormationError(f"initial spectrum split failed for kappa={kappa}")
        modes0 = vectors[:, negative] / math.sqrt(dr)
        modes = np.zeros_like(modes0) if zero_covariance else modes0.copy()
        metric = max(metric, float(np.max(np.abs(dr * (modes0.conj().T @ modes0) - np.eye(n)))))
        channel_source = dr * np.sum(np.abs(modes0[:n]) ** 2 - np.abs(modes0[n:]) ** 2, axis=1) / volume
        source0 += DEGENERACY[kappa] * channel_source
        channels[kappa] = {"h0": h0, "modes0": modes0, "modes": modes}
    if metric > 2.0e-12:
        raise FormationError(f"initial covariance metric error {metric}")
    return {"radius": radius, "volume": volume, "area": area, "sigma0": sigma0, "pi0": pi0, "source0": source0, "channels": channels, "dr": dr, "metric": metric}


def normal_ordered_source(modes: dict[int, np.ndarray], state: dict[str, Any], source_enabled: bool) -> np.ndarray:
    if not source_enabled:
        return 0.0
    source = np.zeros_like(state["radius"])
    volume = state["volume"]
    dr = state["dr"]
    for kappa in CHANNELS:
        now = np.sum(np.abs(modes[kappa][: volume.size]) ** 2 - np.abs(modes[kappa][volume.size :]) ** 2, axis=1)
        base_modes = state["channels"][kappa]["modes0"]
        base = np.sum(np.abs(base_modes[: volume.size]) ** 2 - np.abs(base_modes[volume.size :]) ** 2, axis=1)
        source += DEGENERACY[kappa] * dr * (now - base) / volume
    return source


def apply_hamiltonian(modes: np.ndarray, sigma: np.ndarray, dr: float, kappa: int) -> np.ndarray:
    n = sigma.size
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    connection = kappa / np.sqrt(radius * radius + CORE_SMOOTH * CORE_SMOOTH)
    upper = modes[:n]
    lower = modes[n:]
    upper_out = G * sigma[:, None] * upper - derivative(lower, dr) + connection[:, None] * lower
    lower_out = derivative(upper, dr) + connection[:, None] * upper - G * sigma[:, None] * lower
    return np.concatenate((upper_out, lower_out), axis=0)


def rhs(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray], state: dict[str, Any], source_enabled: bool) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    source = normal_ordered_source(modes, state, source_enabled)
    acceleration = laplacian(sigma, state["dr"], state["volume"], state["area"]) - LAMBDA * (sigma * sigma - V * V) * sigma - G * source
    mode_dot = {kappa: -1j * apply_hamiltonian(modes[kappa], sigma, state["dr"], kappa) for kappa in CHANNELS}
    return pi, acceleration, mode_dot


def add_state(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray], factor: float, stage: tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    return sigma + factor * stage[0], pi + factor * stage[1], {kappa: modes[kappa] + factor * stage[2][kappa] for kappa in CHANNELS}


def rk4_step(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray], dt: float, state: dict[str, Any], source_enabled: bool) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    k1 = rhs(sigma, pi, modes, state, source_enabled)
    s2, p2, u2 = add_state(sigma, pi, modes, 0.5 * dt, k1)
    k2 = rhs(s2, p2, u2, state, source_enabled)
    s3, p3, u3 = add_state(sigma, pi, modes, 0.5 * dt, k2)
    k3 = rhs(s3, p3, u3, state, source_enabled)
    s4, p4, u4 = add_state(sigma, pi, modes, dt, k3)
    k4 = rhs(s4, p4, u4, state, source_enabled)
    return (
        sigma + dt * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]) / 6.0,
        pi + dt * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]) / 6.0,
        {kappa: modes[kappa] + dt * (k1[2][kappa] + 2.0 * k2[2][kappa] + 2.0 * k3[2][kappa] + k4[2][kappa]) / 6.0 for kappa in CHANNELS},
    )


def scalar_energy(sigma: np.ndarray, pi: np.ndarray, state: dict[str, Any]) -> float:
    dr = state["dr"]
    kinetic = 0.5 * float(np.sum(state["volume"] * pi * pi))
    potential = float(np.sum(state["volume"] * scalar_potential(sigma)))
    internal = 0.5 * float(np.sum(state["area"][1:-1] * (sigma[1:] - sigma[:-1]) ** 2 / dr))
    outer = 0.5 * float(state["area"][-1] * (sigma[-1] - V) ** 2 / (0.5 * dr))
    return kinetic + potential + internal + outer


def total_energy(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray], state: dict[str, Any]) -> tuple[float, float, float, float]:
    dynamic = 0.0
    initial = 0.0
    for kappa in CHANNELS:
        factor = DEGENERACY[kappa]
        dynamic += factor * float(np.real(np.trace(modes[kappa].conj().T @ hamiltonian(sigma, state["dr"], kappa) @ modes[kappa])) * state["dr"])
        initial += factor * float(np.real(np.trace(state["channels"][kappa]["modes0"].conj().T @ state["channels"][kappa]["h0"] @ state["channels"][kappa]["modes0"])) * state["dr"])
    counterterm = float(G * np.sum(state["volume"] * state["source0"] * (sigma - state["sigma0"])) )
    fermion = dynamic - initial - counterterm
    scalar = scalar_energy(sigma, pi, state)
    norm = sum(DEGENERACY[kappa] * float(np.real(np.trace(modes[kappa].conj().T @ modes[kappa])) * state["dr"]) for kappa in CHANNELS)
    return scalar + fermion, scalar, fermion, norm


def metrics(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray], state: dict[str, Any]) -> dict[str, float]:
    n = state["radius"].size
    dr = state["dr"]
    pair = 0.0
    hole = 0.0
    pair_density = np.zeros(n, dtype=np.float64)
    bound_density = np.zeros(n, dtype=np.float64)
    bound_occupation = 0.0
    bound_hole_occupation = 0.0
    bound_energy_sum = 0.0
    bound_count_total = 0.0
    for kappa in CHANNELS:
        factor = DEGENERACY[kappa]
        values, vectors = np.linalg.eigh(hamiltonian(sigma, dr, kappa))
        positive = values > 1.0e-10
        negative = values < -1.0e-10
        p = vectors[:, positive] / math.sqrt(dr)
        q = vectors[:, negative] / math.sqrt(dr)
        coeff = dr * (p.conj().T @ modes[kappa])
        particles = p @ coeff
        pair_density += factor * np.sum(np.abs(particles[:n]) ** 2 + np.abs(particles[n:]) ** 2, axis=1)
        pair += factor * float(np.sum(np.abs(coeff) ** 2))
        holes = dr * (q.conj().T @ modes[kappa])
        hole += factor * float(n - np.sum(np.abs(holes) ** 2))
        bound_mask = (values > 1.0e-10) & (values <= BOUND_ENERGY_MAX)
        bound_count = int(np.count_nonzero(bound_mask))
        if bound_count:
            bound = vectors[:, bound_mask] / math.sqrt(dr)
            bound_hole = q[:, -bound_count:]
            bound_coeff = dr * (bound.conj().T @ modes[kappa])
            hole_coeff = dr * (bound_hole.conj().T @ modes[kappa])
            bound_density += factor * np.sum(np.abs(bound[:n]) ** 2 + np.abs(bound[n:]) ** 2, axis=1)
            bound_occupation += factor * float(np.sum(np.abs(bound_coeff) ** 2))
            bound_hole_occupation += factor * float(bound_count - np.sum(np.abs(hole_coeff) ** 2))
            bound_energy_sum += factor * float(np.sum(values[bound_mask]))
            bound_count_total += factor * bound_count
    core = state["radius"] < CORE_RADIUS
    pair_core = float(np.sum(pair_density[core]) * dr / pair) if pair > PAIR_EPS else 0.0
    pair_rms = math.sqrt(float(np.sum(state["radius"] ** 2 * pair_density) * dr / pair)) if pair > PAIR_EPS else 0.0
    bound_norm = float(np.sum(bound_density) * dr)
    bound_core = float(np.sum(bound_density[core]) * dr / bound_norm) if bound_norm > PAIR_EPS else 0.0
    bound_rms = math.sqrt(float(np.sum(state["radius"] ** 2 * bound_density) * dr / bound_norm)) if bound_norm > PAIR_EPS else 0.0
    total, scalar, fermion, mode_norm = total_energy(sigma, pi, modes, state)
    scalar_density = 0.5 * pi * pi + scalar_potential(sigma)
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
        "bound_hole_gap": abs(bound_occupation - bound_hole_occupation),
        "pair_core_probability": pair_core, "pair_rms": pair_rms,
        "bound_core_probability": bound_core, "bound_rms": bound_rms,
        "bound_energy": bound_energy_sum / bound_count_total if bound_count_total else 0.0,
        "negative_bound_energy": -bound_energy_sum / bound_count_total if bound_count_total else 0.0,
        "center_deficit": float(1.0 - sigma[0]), "outer_scalar_energy_fraction": outer_fraction,
    }


def archive_arrays(output: Path, arm: str, times: list[float], sigmas: list[np.ndarray], pis: list[np.ndarray], modes: list[dict[int, np.ndarray]]) -> str:
    arrays = {
        "time": np.asarray(times, dtype=np.float64),
        "sigma": np.asarray(sigmas, dtype=np.float64),
        "pi": np.asarray(pis, dtype=np.float64),
        "u_re": np.asarray([[item[kappa].real for kappa in CHANNELS] for item in modes], dtype=np.float64),
        "u_im": np.asarray([[item[kappa].imag for kappa in CHANNELS] for item in modes], dtype=np.float64),
    }
    if any(not np.isfinite(value).all() for value in arrays.values()):
        raise FormationError(f"nonfinite archive for {arm}")
    return write_npz_exclusive(output / f"{arm}.npz", arrays)


def candidate_predicate(row: dict[str, Any]) -> bool:
    late, spread = row["late_means"], row["late_std"]
    return bool(
        late["pair_number"] > 0.05 and late["bound_occupation"] > 0.10 and late["pair_hole_gap"] < 0.05 and late["bound_hole_gap"] < 0.05
        and late["pair_core_probability"] > 0.50 and late["bound_core_probability"] > 0.50
        and late["pair_rms"] < 5.0 and late["bound_rms"] < 5.0
        and spread["pair_number"] <= 0.25 and spread["bound_occupation"] <= 0.25 and spread["pair_rms"] <= 0.75 and spread["bound_rms"] <= 0.75
        and row["relative_energy_error"] <= 5.0e-3 and late["center_deficit"] >= 0.05
    )


def arm_spec(arm: str) -> tuple[str, bool, bool, bool]:
    if arm == "static_vacuum":
        return "G1", True, False, False
    if arm == "source_off":
        return "G1", False, False, False
    if arm == "zero_covariance":
        return "G1", False, False, True
    if arm.startswith("shell_") and arm[-2:] in GRIDS:
        return arm[-2:], False, True, False
    raise FormationError(f"unexpected arm {arm}")


def expected_arms() -> list[str]:
    return [f"shell_{grid}" for grid in GRIDS] + ["static_vacuum", "source_off", "zero_covariance"]


def evolve_arm(output: Path, arm: str, grid: str, homogeneous: bool, source_enabled: bool, zero_covariance: bool) -> tuple[dict[str, Any], dict[str, str]]:
    n, dr, dt = GRIDS[grid]
    state = initial_state(n, dr, homogeneous, zero_covariance)
    sigma = state["sigma0"].copy()
    pi = state["pi0"].copy()
    modes = {kappa: state["channels"][kappa]["modes"].copy() for kappa in CHANNELS}
    steps = int(round(FINAL_TIME / dt))
    sample_steps = int(round(SAMPLE_DT / dt))
    if steps * dt != FINAL_TIME or sample_steps * dt != SAMPLE_DT:
        raise FormationError(f"invalid schedule for {arm}")
    times: list[float] = [0.0]
    sigmas: list[np.ndarray] = [sigma.copy()]
    pis: list[np.ndarray] = [pi.copy()]
    archives: list[dict[int, np.ndarray]] = [{kappa: modes[kappa].copy() for kappa in CHANNELS}]
    diagnostics: list[dict[str, float]] = [metrics(sigma, pi, modes, state)]
    for step in range(1, steps + 1):
        for _ in range(RK4_SUBSTEPS):
            sigma, pi, modes = rk4_step(sigma, pi, modes, dt / RK4_SUBSTEPS, state, source_enabled)
        if step % sample_steps == 0 or step == steps:
            times.append(step * dt)
            sigmas.append(sigma.copy())
            pis.append(pi.copy())
            archives.append({kappa: modes[kappa].copy() for kappa in CHANNELS})
            diagnostics.append(metrics(sigma, pi, modes, state))
    expected_count = int(round(FINAL_TIME / SAMPLE_DT)) + 1
    if len(times) != expected_count:
        raise FormationError(f"archive count mismatch for {arm}")
    archive_hash = archive_arrays(output, arm, times, sigmas, pis, archives)
    values = {key: np.asarray([row[key] for row in diagnostics], dtype=np.float64) for key in diagnostics[0]}
    late = np.asarray(times) >= LATE_START - 1.0e-12
    initial_energy = float(values["total_energy"][0])
    energy_error = np.abs(values["total_energy"] - initial_energy)
    row: dict[str, Any] = {
        "arm": arm, "grid": grid, "N": n, "dr": dr, "dt": dt, "steps": steps, "duration": FINAL_TIME,
        "initial_energy": initial_energy, "final_energy": float(values["total_energy"][-1]),
        "max_energy_error": float(np.max(energy_error)), "relative_energy_error": float(np.max(energy_error) / max(1.0, abs(initial_energy))),
        "late_means": {key: float(np.mean(value[late])) for key, value in values.items()},
        "late_std": {key: float(np.std(value[late])) for key, value in values.items()},
        "candidate": arm.startswith("shell_"), "homogeneous": homogeneous, "source_enabled": source_enabled, "zero_covariance": zero_covariance,
        "initial_covariance_metric_error": state["metric"], "archive": f"{arm}.npz", "archive_sha256": archive_hash,
    }
    row["captured"] = candidate_predicate(row) if row["candidate"] else False
    return row, {"path": f"{arm}.npz", "sha256": archive_hash}


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    target = source_dir / relative(SELF).replace("/", "__")
    shutil.copyfile(SELF, target)
    protocol_target = source_dir / relative(PROTOCOL).replace("/", "__")
    shutil.copyfile(PROTOCOL, protocol_target)
    return {relative(SELF): raw_sha(target), relative(PROTOCOL): raw_sha(protocol_target)}


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FormationError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=False, exist_ok=False)
    archived = snapshot_sources(output_dir)
    rows: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, str]] = {}
    for grid in GRIDS:
        row, artifact = evolve_arm(output_dir, f"shell_{grid}", grid, False, True, False)
        rows.append(row)
        artifacts[row["arm"]] = artifact
    for arm, grid, homogeneous, source_enabled, zero_covariance in (("static_vacuum", "G1", True, False, False), ("source_off", "G1", False, False, False), ("zero_covariance", "G1", False, False, True)):
        row, artifact = evolve_arm(output_dir, arm, grid, homogeneous, source_enabled, zero_covariance)
        rows.append(row)
        artifacts[arm] = artifact
    candidates = [row for row in rows if row["candidate"]]
    controls = [row for row in rows if not row["candidate"]]
    by_grid = {row["grid"]: row for row in candidates}
    resolution = []
    for left_grid, right_grid in (("G0", "G1"), ("G1", "G2")):
        for key, threshold in (("pair_number", 0.25), ("bound_occupation", 0.25), ("pair_core_probability", 0.15), ("bound_core_probability", 0.15), ("pair_rms", 0.50), ("bound_rms", 0.50)):
            difference = abs(by_grid[left_grid]["late_means"][key] - by_grid[right_grid]["late_means"][key])
            resolution.append({"left": left_grid, "right": right_grid, "observable": key, "difference": difference, "threshold": threshold, "pass": difference < threshold})
    static = next(row for row in controls if row["arm"] == "static_vacuum")
    zero = next(row for row in controls if row["arm"] == "zero_covariance")
    controls_pass = bool(static["late_means"]["pair_number"] < 1.0e-10 and static["late_means"]["center_deficit"] < 1.0e-10 and zero["late_means"]["mode_norm"] < 1.0e-8 and zero["late_means"]["pair_number"] < 1.0e-8)
    finite_pass = all(finite_json(row) for row in rows)
    resolution_pass = all(item["pass"] for item in resolution)
    candidate_pass = all(row["captured"] for row in candidates)
    numerical_pass = bool(finite_pass and controls_pass and resolution_pass)
    verdict = "CAPTURED—conditional autonomous two-channel spherical formation" if numerical_pass and candidate_pass else "DOES NOT EMERGE—conditional autonomous two-channel spherical formation" if numerical_pass else "INCONCLUSIVE"
    receipt = {
        "schema": SCHEMA,
        "identities": {"primary": {"path": relative(SELF), "sha256": canonical_sha(SELF)}, "protocol": {"path": relative(PROTOCOL), "sha256": canonical_sha(PROTOCOL)}, "archived_source_sha256": archived},
        "channels": [{"kappa": kappa, "degeneracy": DEGENERACY[kappa]} for kappa in CHANNELS],
        "artifacts": artifacts, "rows": rows, "resolution": resolution,
        "checks": {"finite_payload": finite_pass, "controls": controls_pass, "resolution": resolution_pass, "candidate": candidate_pass},
        "numerical_pass": numerical_pass, "verdict": verdict, "complete_physical_matter_formation": False,
        "autonomous_two_channel_mechanism": bool(numerical_pass and candidate_pass),
        "scope": "finite-box spherical kappa=-1,+1 covariance with degeneracy-weighted self-consistent scalar backreaction from a prescribed finite-energy initial shell; no continuum or all-sector claim",
        "failures": [name for name, passed in (("finite_payload", finite_pass), ("controls", controls_pass), ("resolution", resolution_pass)) if not passed],
    }
    write_json_exclusive(output_dir / "result.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = run(args.output_dir.resolve())
    except (FormationError, OSError, ValueError, FloatingPointError) as exc:
        print(f"two-channel primary failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output_dir.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
