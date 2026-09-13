#!/usr/bin/env python3
"""Independent verifier for the two-channel autonomous shell receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PRIMARY = ROOT / "computations" / "matter_formation_autonomous_shell_g3_two_channel.py"
PROTOCOL = ROOT / "computations" / "matter-formation-autonomous-shell-g3-two-channel-fourth-order-prereg.md"
SCHEMA = "cassi.matter-formation.autonomous-shell-g3-two-channel-fourth-order.v1"
LAMBDA = 0.25
G = 3.0
V = 1.0
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
CHANNELS = (-1, 1)
DEGENERACY = {-1: 2.0, 1: 2.0}
GRIDS = {"G0": (48, RADIUS / 48.0, 0.004), "G1": (72, RADIUS / 72.0, 0.002), "G2": (96, RADIUS / 96.0, 0.001)}


class VerificationError(RuntimeError):
    pass


def digest(path: Path, canonical: bool = False) -> str:
    data = path.read_bytes()
    if canonical:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, np.integer, str, bool)) or value is None:
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite(v) for v in value)
    return False


def grid(n: int, dr: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    faces = np.arange(n + 1, dtype=float) * dr
    radius = (np.arange(n, dtype=float) + 0.5) * dr
    volume = 4.0 * math.pi / 3.0 * (faces[1:] ** 3 - faces[:-1] ** 3)
    area = 4.0 * math.pi * faces * faces
    return radius, volume, area


def d1(field: np.ndarray, dr: float) -> np.ndarray:
    out = np.zeros_like(field)
    nearest = 2.0 / (3.0 * dr)
    next_nearest = -1.0 / (12.0 * dr)
    out[1:] += nearest * field[:-1]
    out[:-1] -= nearest * field[1:]
    out[2:] += next_nearest * field[:-2]
    out[:-2] -= next_nearest * field[2:]
    return out


def lap(field: np.ndarray, dr: float, volume: np.ndarray, area: np.ndarray) -> np.ndarray:
    flux = np.zeros(field.size + 1, dtype=float)
    flux[1:-1] = area[1:-1] * (field[1:] - field[:-1]) / dr
    flux[-1] = area[-1] * (1.0 - field[-1]) / (0.5 * dr)
    return (flux[1:] - flux[:-1]) / volume


def sigma_initial(radius: np.ndarray, homogeneous: bool) -> tuple[np.ndarray, np.ndarray]:
    if homogeneous:
        return np.ones_like(radius), np.zeros_like(radius)
    x = radius - SHELL_CENTER
    pulse = np.exp(-0.5 * (x / WIDTH) ** 2)
    return 1.0 - AMPLITUDE * pulse, AMPLITUDE * x / (WIDTH * WIDTH) * pulse


def operator(sigma: np.ndarray, dr: float, kappa: int) -> np.ndarray:
    n = sigma.size
    matrix = np.zeros((2 * n, 2 * n), dtype=complex)
    indices = np.arange(n)
    matrix[indices, indices] = G * sigma
    matrix[n + indices, n + indices] = -G * sigma
    derivative_matrix = np.zeros((n, n), dtype=float)
    nearest = 2.0 / (3.0 * dr)
    next_nearest = -1.0 / (12.0 * dr)
    for i in range(n - 1):
        derivative_matrix[i + 1, i] += nearest
        derivative_matrix[i, i + 1] -= nearest
    for i in range(n - 2):
        derivative_matrix[i + 2, i] += next_nearest
        derivative_matrix[i, i + 2] -= next_nearest
    r = (np.arange(n, dtype=float) + 0.5) * dr
    c = kappa / np.sqrt(r * r + CORE_SMOOTH * CORE_SMOOTH)
    matrix[:n, n:] = -derivative_matrix
    matrix[n:, :n] = derivative_matrix
    matrix[indices, n + indices] += c
    matrix[n + indices, indices] += c
    return matrix


def setup(n: int, dr: float, homogeneous: bool, zero_covariance: bool) -> dict[str, Any]:
    radius, volume, area = grid(n, dr)
    sigma0, pi0 = sigma_initial(radius, homogeneous)
    channels: dict[int, dict[str, Any]] = {}
    source0 = np.zeros(n, dtype=float)
    for kappa in CHANNELS:
        values, vectors = np.linalg.eigh(operator(sigma0, dr, kappa))
        negative = values < -1.0e-10
        positive = values > 1.0e-10
        if int(negative.sum()) != n or int(positive.sum()) != n:
            raise VerificationError(f"spectrum split failed at kappa={kappa}")
        vacuum = vectors[:, negative] / math.sqrt(dr)
        modes = np.zeros_like(vacuum) if zero_covariance else vacuum.copy()
        source0 += DEGENERACY[kappa] * dr * (np.sum(np.abs(vacuum[:n]) ** 2, axis=1) - np.sum(np.abs(vacuum[n:]) ** 2, axis=1)) / volume
        channels[kappa] = {"vacuum": vacuum, "modes": modes}
    return {"radius": radius, "volume": volume, "area": area, "sigma0": sigma0, "pi0": pi0, "source0": source0, "channels": channels, "dr": dr}


def channel_action(modes: np.ndarray, sigma: np.ndarray, dr: float, kappa: int) -> np.ndarray:
    n = sigma.size
    r = (np.arange(n, dtype=float) + 0.5) * dr
    c = kappa / np.sqrt(r * r + CORE_SMOOTH * CORE_SMOOTH)
    upper, lower = modes[:n], modes[n:]
    return np.vstack((G * sigma[:, None] * upper - d1(lower, dr) + c[:, None] * lower, d1(upper, dr) + c[:, None] * upper - G * sigma[:, None] * lower))


def decode(y: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    index = 0
    sigma = y[index:index + n]; index += n
    pi = y[index:index + n]; index += n
    modes: dict[int, np.ndarray] = {}
    size = 2 * n * n
    for kappa in CHANNELS:
        real = y[index:index + size].reshape(2 * n, n); index += size
        imag = y[index:index + size].reshape(2 * n, n); index += size
        modes[kappa] = real + 1j * imag
    if index != y.size:
        raise VerificationError("state decode length mismatch")
    return sigma, pi, modes


def encode(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray]) -> np.ndarray:
    parts: list[np.ndarray] = [sigma.real, pi.real]
    for kappa in CHANNELS:
        parts.extend((modes[kappa].real.ravel(), modes[kappa].imag.ravel()))
    return np.concatenate(parts)


def flow(t: float, y: np.ndarray, state: dict[str, Any], source_enabled: bool) -> np.ndarray:
    del t
    n = state["radius"].size
    sigma, pi, modes = decode(y, n)
    source = np.zeros(n, dtype=float)
    if source_enabled:
        for kappa in CHANNELS:
            current = np.sum(np.abs(modes[kappa][:n]) ** 2 - np.abs(modes[kappa][n:]) ** 2, axis=1)
            vacuum = state["channels"][kappa]["vacuum"]
            reference = np.sum(np.abs(vacuum[:n]) ** 2 - np.abs(vacuum[n:]) ** 2, axis=1)
            source += DEGENERACY[kappa] * state["dr"] * (current - reference) / state["volume"]
    acceleration = lap(sigma, state["dr"], state["volume"], state["area"]) - LAMBDA * (sigma * sigma - 1.0) * sigma - G * source
    output: list[np.ndarray] = [pi, acceleration]
    for kappa in CHANNELS:
        derivative = -1j * channel_action(modes[kappa], sigma, state["dr"], kappa)
        output.extend((derivative.real.ravel(), derivative.imag.ravel()))
    return np.concatenate(output)


def scalar_potential(sigma: np.ndarray) -> np.ndarray:
    return 0.25 * LAMBDA * (sigma * sigma - 1.0) ** 2


def measure(sigma: np.ndarray, pi: np.ndarray, modes: dict[int, np.ndarray], state: dict[str, Any]) -> dict[str, float]:
    n = sigma.size
    dr = state["dr"]
    pair = hole = bound = bound_hole = 0.0
    pair_density = np.zeros(n, dtype=float)
    bound_density = np.zeros(n, dtype=float)
    bound_energy = count = 0.0
    for kappa in CHANNELS:
        factor = DEGENERACY[kappa]
        values, vectors = np.linalg.eigh(operator(sigma, dr, kappa))
        pos = values > 1.0e-10
        neg = values < -1.0e-10
        positive = vectors[:, pos] / math.sqrt(dr)
        negative = vectors[:, neg] / math.sqrt(dr)
        occupation = dr * positive.conj().T @ modes[kappa]
        particle_modes = positive @ occupation
        pair_density += factor * np.sum(np.abs(particle_modes[:n]) ** 2 + np.abs(particle_modes[n:]) ** 2, axis=1)
        pair += factor * float(np.sum(np.abs(occupation) ** 2))
        vacuum_overlap = dr * negative.conj().T @ modes[kappa]
        hole += factor * float(n - np.sum(np.abs(vacuum_overlap) ** 2))
        bounded = (values > 1.0e-10) & (values <= BOUND_ENERGY_MAX)
        count_here = int(bounded.sum())
        if count_here:
            bound_vectors = vectors[:, bounded] / math.sqrt(dr)
            bound_occ = dr * bound_vectors.conj().T @ modes[kappa]
            bound_negative = negative[:, -count_here:]
            bound_holes = dr * bound_negative.conj().T @ modes[kappa]
            bound_density += factor * np.sum(np.abs(bound_vectors[:n]) ** 2 + np.abs(bound_vectors[n:]) ** 2, axis=1)
            bound += factor * float(np.sum(np.abs(bound_occ) ** 2))
            bound_hole += factor * float(count_here - np.sum(np.abs(bound_holes) ** 2))
            bound_energy += factor * float(np.sum(values[bounded]))
            count += factor * count_here
    core = state["radius"] < CORE_RADIUS
    pair_core = float(dr * pair_density[core].sum() / pair) if pair > PAIR_EPS else 0.0
    pair_rms = math.sqrt(float(dr * np.sum(state["radius"] ** 2 * pair_density) / pair)) if pair > PAIR_EPS else 0.0
    bound_norm = float(dr * bound_density.sum())
    bound_core = float(dr * bound_density[core].sum() / bound_norm) if bound_norm > PAIR_EPS else 0.0
    bound_rms = math.sqrt(float(dr * np.sum(state["radius"] ** 2 * bound_density) / bound_norm)) if bound_norm > PAIR_EPS else 0.0
    return {
        "pair_number": pair, "hole_number": hole, "pair_hole_gap": abs(pair - hole),
        "bound_occupation": bound, "bound_hole_occupation": bound_hole, "bound_hole_gap": abs(bound - bound_hole),
        "pair_core_probability": pair_core, "pair_rms": pair_rms, "bound_core_probability": bound_core, "bound_rms": bound_rms,
        "bound_energy": bound_energy / count if count else 0.0, "negative_bound_energy": -bound_energy / count if count else 0.0,
        "center_deficit": float(1.0 - sigma[0]),
        "mode_norm": sum(DEGENERACY[kappa] * float(np.real(np.trace(modes[kappa].conj().T @ modes[kappa])) * dr) for kappa in CHANNELS),
    }


def initial_vector(state: dict[str, Any]) -> np.ndarray:
    return encode(state["sigma0"], state["pi0"], {kappa: state["channels"][kappa]["modes"].copy() for kappa in CHANNELS})


def integrate(arm: str, grid_name: str, homogeneous: bool, source_enabled: bool, zero_covariance: bool) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    n, dr, dt = GRIDS[grid_name]
    state = setup(n, dr, homogeneous, zero_covariance)
    times = np.arange(0.0, FINAL_TIME + 0.5 * SAMPLE_DT, SAMPLE_DT, dtype=float)
    solution = solve_ivp(lambda t, y: flow(t, y, state, source_enabled), (0.0, FINAL_TIME), initial_vector(state), method="DOP853", t_eval=times, rtol=2.0e-8, atol=2.0e-10, max_step=0.02)
    if not solution.success:
        raise VerificationError(f"{arm} DOP853 failed: {solution.message}")
    if solution.y.shape[1] != times.size:
        raise VerificationError(f"{arm} sample count mismatch")
    return times, state, {"y": solution.y, "n": n, "dr": dr, "dt": dt}


def extract(solution: dict[str, Any], state: dict[str, Any], index: int) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    return decode(solution["y"][:, index], solution["n"])


def arrays_from_solution(solution: dict[str, Any], state: dict[str, Any]) -> dict[str, np.ndarray]:
    sigma_rows: list[np.ndarray] = []
    pi_rows: list[np.ndarray] = []
    re_rows: list[np.ndarray] = []
    im_rows: list[np.ndarray] = []
    for index in range(solution["y"].shape[1]):
        sigma, pi, modes = extract(solution, state, index)
        sigma_rows.append(sigma)
        pi_rows.append(pi)
        re_rows.append(np.asarray([modes[kappa].real for kappa in CHANNELS]))
        im_rows.append(np.asarray([modes[kappa].imag for kappa in CHANNELS]))
    return {"sigma": np.asarray(sigma_rows), "pi": np.asarray(pi_rows), "u_re": np.asarray(re_rows), "u_im": np.asarray(im_rows)}


def compare_projectors(primary_re: np.ndarray, primary_im: np.ndarray, independent_re: np.ndarray, independent_im: np.ndarray, dr: float) -> float:
    error = 0.0
    for time_index in range(primary_re.shape[0]):
        for channel_index in range(primary_re.shape[1]):
            left = primary_re[time_index, channel_index] + 1j * primary_im[time_index, channel_index]
            right = independent_re[time_index, channel_index] + 1j * independent_im[time_index, channel_index]
            left_projector = dr * left @ left.conj().T
            right_projector = dr * right @ right.conj().T
            error = max(error, float(np.max(np.abs(left_projector - right_projector))))
    return error


def late_summary(arrays: dict[str, np.ndarray], state: dict[str, Any], times: np.ndarray) -> dict[str, dict[str, float]]:
    rows = []
    for index in range(times.size):
        modes = {kappa: arrays["u_re"][index, channel] + 1j * arrays["u_im"][index, channel] for channel, kappa in enumerate(CHANNELS)}
        rows.append(measure(arrays["sigma"][index], arrays["pi"][index], modes, state))
    late = times >= LATE_START - 1.0e-12
    keys = rows[0].keys()
    return {"mean": {key: float(np.mean([row[key] for index, row in enumerate(rows) if late[index]])) for key in keys}, "std": {key: float(np.std([row[key] for index, row in enumerate(rows) if late[index]])) for key in keys}}


def candidate(summary: dict[str, dict[str, float]]) -> bool:
    late, spread = summary["mean"], summary["std"]
    return bool(
        late["pair_number"] > 0.05 and late["bound_occupation"] > 0.10 and late["pair_hole_gap"] < 0.05 and late["bound_hole_gap"] < 0.05
        and late["pair_core_probability"] > 0.50 and late["bound_core_probability"] > 0.50
        and late["pair_rms"] < 5.0 and late["bound_rms"] < 5.0
        and spread["pair_number"] <= 0.25 and spread["bound_occupation"] <= 0.25 and spread["pair_rms"] <= 0.75 and spread["bound_rms"] <= 0.75
        and late["center_deficit"] >= 0.05
    )


def control_passes(summaries: dict[str, dict[str, dict[str, float]]]) -> bool:
    static = summaries["static_vacuum"]["mean"]
    zero = summaries["zero_covariance"]["mean"]
    return bool(static["pair_number"] < 1.0e-10 and static["center_deficit"] < 1.0e-10 and zero["mode_norm"] < 1.0e-8 and zero["pair_number"] < 1.0e-8)


def resolution(rows: dict[str, dict[str, dict[str, float]]]) -> list[dict[str, Any]]:
    checks = []
    for left, right in (("G0", "G1"), ("G1", "G2")):
        for key, threshold in (("pair_number", 0.25), ("bound_occupation", 0.25), ("pair_core_probability", 0.15), ("bound_core_probability", 0.15), ("pair_rms", 0.50), ("bound_rms", 0.50)):
            difference = abs(rows[f"shell_{left}"]["mean"][key] - rows[f"shell_{right}"]["mean"][key])
            checks.append({"left": left, "right": right, "observable": key, "difference": difference, "threshold": threshold, "pass": difference < threshold})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-run", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    primary_run = args.primary_run.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        print(f"refusing existing verifier output: {output}")
        return 1
    output.mkdir(parents=False, exist_ok=False)
    primary_receipt = json.loads((primary_run / "result.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    identity_pass = bool(
        primary_receipt.get("schema") == SCHEMA
        and primary_receipt.get("identities", {}).get("primary", {}).get("sha256") == digest(PRIMARY, canonical=True)
        and primary_receipt.get("identities", {}).get("protocol", {}).get("sha256") == digest(PROTOCOL, canonical=True)
    )
    if not identity_pass:
        failures.append("identity")
    arm_specs = {"shell_G0": ("G0", False, True, False), "shell_G1": ("G1", False, True, False), "shell_G2": ("G2", False, True, False), "static_vacuum": ("G1", True, False, False), "source_off": ("G1", False, False, False), "zero_covariance": ("G1", False, False, True)}
    independent_summaries: dict[str, dict[str, dict[str, float]]] = {}
    state_checks: list[dict[str, Any]] = []
    archive_checks: list[dict[str, Any]] = []
    summary_checks: list[dict[str, Any]] = []
    all_finite = True
    for arm, spec in arm_specs.items():
        grid_name, homogeneous, source_enabled, zero_covariance = spec
        try:
            times, state, solution = integrate(arm, grid_name, homogeneous, source_enabled, zero_covariance)
            independent = arrays_from_solution(solution, state)
            archive = np.load(primary_run / f"{arm}.npz")
            primary_arrays = {name: archive[name] for name in ("time", "sigma", "pi", "u_re", "u_im")}
            finite_arrays = all(np.isfinite(value).all() for value in primary_arrays.values()) and all(np.isfinite(value).all() for value in independent.values())
            all_finite = all_finite and finite_arrays
            array_error = {name: float(np.max(np.abs(primary_arrays[name] - (times if name == "time" else independent[name])))) for name in ("sigma", "pi", "u_re", "u_im")}
            projector_error = compare_projectors(primary_arrays["u_re"], primary_arrays["u_im"], independent["u_re"], independent["u_im"], state["dr"])
            state_pass = bool(finite_arrays and array_error["sigma"] < 2.0e-5 and array_error["pi"] < 5.0e-5 and projector_error < 3.0e-5)
            state_checks.append({"arm": arm, "array_error": array_error, "projector_max_absolute_error": projector_error, "pass": state_pass})
            archive_pass = bool(primary_arrays["time"].shape == times.shape and np.max(np.abs(primary_arrays["time"] - times)) < 1.0e-12 and primary_arrays["sigma"].shape == independent["sigma"].shape and primary_arrays["u_re"].shape == independent["u_re"].shape)
            archive_checks.append({"arm": arm, "pass": archive_pass, "sample_count": int(times.size)})
            independent_summaries[arm] = late_summary(independent, state, times)
            primary_row = next(row for row in primary_receipt["rows"] if row["arm"] == arm)
            summary_error = max(abs(independent_summaries[arm]["mean"][key] - primary_row["late_means"][key]) for key in independent_summaries[arm]["mean"] if key in primary_row["late_means"])
            summary_checks.append({"arm": arm, "maximum_absolute_error": float(summary_error), "threshold": 2.0e-4, "pass": summary_error < 2.0e-4})
        except (OSError, ValueError, VerificationError, FloatingPointError) as exc:
            state_checks.append({"arm": arm, "pass": False, "error": str(exc)})
            archive_checks.append({"arm": arm, "pass": False, "error": str(exc)})
            summary_checks.append({"arm": arm, "pass": False, "error": str(exc)})
            failures.append(f"arm:{arm}")
    state_pass = bool(state_checks and all(item["pass"] for item in state_checks))
    archive_pass = bool(archive_checks and all(item["pass"] for item in archive_checks))
    summary_pass = bool(summary_checks and all(item["pass"] for item in summary_checks))
    controls_pass = control_passes(independent_summaries) if len(independent_summaries) == len(arm_specs) else False
    candidate_pass = all(candidate(independent_summaries[f"shell_{grid}"]) for grid in GRIDS) if len(independent_summaries) == len(arm_specs) else False
    resolution_checks = resolution({key: independent_summaries[key] for key in ("shell_G0", "shell_G1", "shell_G2")}) if len(independent_summaries) == len(arm_specs) else []
    resolution_pass = bool(resolution_checks) and all(item["pass"] for item in resolution_checks)
    finite_pass = bool(all_finite and finite(primary_receipt))
    checks = {"identity": identity_pass, "finite_payload": finite_pass, "state_reconstruction": bool(state_pass and archive_pass), "summary_reconstruction": summary_pass, "controls": controls_pass, "resolution": resolution_pass, "candidate": candidate_pass}
    numerical_pass = bool(identity_pass and finite_pass and state_pass and archive_pass and summary_pass and controls_pass)
    verdict = "CAPTURED—conditional autonomous two-channel spherical formation" if numerical_pass and resolution_pass and candidate_pass else "DOES NOT EMERGE—conditional autonomous two-channel spherical formation" if numerical_pass and resolution_pass else "INCONCLUSIVE"
    failures.extend(name for name, passed in checks.items() if not passed and name not in failures)
    receipt = {
        "schema": SCHEMA, "primary_run": str(primary_run), "primary_result_sha256": digest(primary_run / "result.json"),
        "identities": {"verifier": {"path": rel(SELF), "sha256": digest(SELF, canonical=True)}, "primary": {"path": rel(PRIMARY), "sha256": digest(PRIMARY, canonical=True)}, "protocol": {"path": rel(PROTOCOL), "sha256": digest(PROTOCOL, canonical=True)}},
        "checks": checks, "state_comparisons": state_checks, "archive_checks": archive_checks, "summary_comparisons": summary_checks, "resolution": resolution_checks,
        "independent_summaries": independent_summaries, "numerical_pass": numerical_pass, "verdict": verdict, "complete_physical_matter_formation": False,
        "scope": "finite-box spherical kappa=-1,+1 covariance with degeneracy-weighted self-consistent scalar backreaction from a prescribed finite-energy initial shell; no continuum or all-sector claim",
        "failures": failures,
    }
    (output / "verification.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output), "verdict": verdict, "numerical_pass": numerical_pass, "checks": checks}), flush=True)
    return 0 if numerical_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
