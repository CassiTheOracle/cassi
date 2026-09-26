#!/usr/bin/env python3
"""Primary receipt producer for the conditional hyperbolic-parent calculation.

Run from the repository root with::

    python computations/matter_formation_hyperbolic_parent.py

The calculation is deliberately conditional.  It integrates the prescribed
quadratic Gaussian modes and records the correspondence checks; it does not
select a physical parent coefficient or claim nonlinear matter formation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
import scipy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_hyperbolic_parent"
PREREG_PATH = ROOT / "computations" / "matter-formation-hyperbolic-parent-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_hyperbolic_parent.py"
INPUT_RESULTS_PATH = ROOT / "runs" / "20260906_matter_formation_radial" / "results.json"
INPUT_RESULTS_SHA256 = "3ac6ec265c11d8eed2040c372d8862084be084ad0a640bbe0d8655e06e19a313"

SCHEMA = "cassi.matter-formation.hyperbolic-parent.v1"
COEFFICIENTS = {"k_Cx": 1.0, "u_C": 1.0, "u_rho": 4.0, "e_C": 0.75, "h_C": 2.9598260763447164}
A_VALUES = (1.0 / 16.0, 1.0 / 32.0, 1.0 / 64.0)
A_DENOMINATORS = (16, 32, 64)
K_VALUES = (0, 1, 2)
T_VALUES = (0.05, 0.25, 1.0)
AMPLITUDE = 1.0
RTOL = 1.0e-11
ATOL = 1.0e-13
OCCUPATION_ABS_TOL = 1.0e-10
OCCUPATION_REL_TOL = 1.0e-7
WRONSKIAN_TOL = 1.0e-8
ENERGY_WORK_TOL = 1.0e-8
CONTROL_TOL = 1.0e-12
TIME_WINDOW_TOL = 1.0e-9
ADIABATIC_MARGIN = 1.0e-9
FAST_WITNESS_MINIMUM = 1.0e-4

# The two qualified radial endpoints are immutable inputs, not recomputed fields.
STATIONARY_INPUTS = {
    "q16_R12_n768_refine": {
        "artifact": "runs/20260906_matter_formation_radial/q16_R12_n768_refine.npz",
        "artifact_sha256": "335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be",
        "Q_C": 16.0,
    },
    "q256_R12_n768_refine": {
        "artifact": "runs/20260906_matter_formation_radial/q256_R12_n768_refine.npz",
        "artifact_sha256": "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a",
        "Q_C": 256.0,
    },
}


class ContractError(RuntimeError):
    """An input, schedule, identity, or numerical contract violation."""


def canonical_sha256(path: Path) -> str:
    """Hash source/specification bytes after the declared CRLF-to-LF normalization."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(path: Path) -> str:
    """Hash artifact/JSON bytes without text normalization."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT).replace("\\", "/")


def finite_scalar(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{label} is not finite")
    return result


def expected_id(a_index: int, k: int, T: float, half_span: int, amplitude: float) -> str:
    milliseconds = int(round(1000.0 * T))
    amplitude_text = str(int(amplitude)) if float(amplitude).is_integer() else str(amplitude)
    return f"a{A_DENOMINATORS[a_index]}_k{k}_T{milliseconds}_L{half_span}_A{amplitude_text}"


def expected_schedule() -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    for index, a in enumerate(A_VALUES):
        for k in K_VALUES:
            for T in T_VALUES:
                schedule.append({
                    "id": expected_id(index, k, T, 16, AMPLITUDE),
                    "a": a, "k": k, "T": T, "amplitude": AMPLITUDE, "half_span": 16,
                })
    for index, a in enumerate(A_VALUES):
        schedule.append({
            "id": expected_id(index, 0, 0.25, 16, 0.0),
            "a": a, "k": 0, "T": 0.25, "amplitude": 0.0, "half_span": 16,
        })
    schedule.append({
        "id": expected_id(0, 0, 0.05, 24, AMPLITUDE),
        "a": A_VALUES[0], "k": 0, "T": 0.05, "amplitude": AMPLITUDE, "half_span": 24,
    })
    if len(schedule) != 31 or len({row["id"] for row in schedule}) != 31:
        raise ContractError("frozen schedule does not contain exactly 31 unique rows")
    return schedule


def load_stationary_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    if not INPUT_RESULTS_PATH.is_file():
        raise FileNotFoundError(INPUT_RESULTS_PATH)
    actual_results_hash = raw_sha256(INPUT_RESULTS_PATH)
    if actual_results_hash != INPUT_RESULTS_SHA256:
        raise ContractError(
            f"radial results byte hash mismatch: {actual_results_hash}"
        )
    with INPUT_RESULTS_PATH.open("r", encoding="utf-8", newline="") as handle:
        receipt = json.load(handle)
    if receipt.get("schema") != "matter-formation-radial-v1":
        raise ContractError("radial results schema mismatch")
    coefficients = receipt.get("coefficients")
    if not isinstance(coefficients, dict):
        raise ContractError("radial results have no coefficient object")
    for key, expected in COEFFICIENTS.items():
        if key not in coefficients or not math.isclose(
            finite_scalar(coefficients[key], f"radial coefficient {key}"), expected,
            rel_tol=0.0, abs_tol=2.0e-15,
        ):
            raise ContractError(f"radial coefficient mismatch for {key}")
    arms = receipt.get("arms")
    if not isinstance(arms, list):
        raise ContractError("radial results have no arms list")
    by_id = {arm.get("id"): arm for arm in arms if isinstance(arm, dict)}
    embeddings: dict[str, Any] = {}
    for source_id, expected in STATIONARY_INPUTS.items():
        arm = by_id.get(source_id)
        if arm is None:
            raise ContractError(f"missing qualified radial endpoint {source_id}")
        if arm.get("status") != "complete" or arm.get("artifact") != expected["artifact"]:
            raise ContractError(f"radial endpoint identity/status mismatch: {source_id}")
        if arm.get("artifact_sha256") != expected["artifact_sha256"]:
            raise ContractError(f"radial endpoint receipt hash mismatch: {source_id}")
        diagnostics = arm.get("diagnostics")
        if not isinstance(diagnostics, dict) or diagnostics.get("qualified") is not True or diagnostics.get("bound") is not True:
            raise ContractError(f"radial endpoint is not qualified and bound: {source_id}")
        Q_C = finite_scalar(arm.get("q"), f"{source_id}.q")
        if Q_C != expected["Q_C"]:
            raise ContractError(f"radial endpoint charge mismatch: {source_id}")
        omega_C = finite_scalar(diagnostics.get("omega"), f"{source_id}.omega")
        artifact = ROOT / expected["artifact"]
        if not artifact.is_file() or raw_sha256(artifact) != expected["artifact_sha256"]:
            raise ContractError(f"radial endpoint NPZ identity mismatch: {source_id}")
        with np.load(artifact, allow_pickle=False) as archive:
            required = {"r", "volumes", "f", "c", "R", "q"}
            if not required.issubset(set(archive.files)):
                raise ContractError(f"radial endpoint NPZ schema mismatch: {source_id}")
            for key in ("r", "volumes", "f", "c"):
                values = np.asarray(archive[key])
                if values.ndim != 1 or not np.all(np.isfinite(values)):
                    raise ContractError(f"radial endpoint NPZ field invalid: {source_id}.{key}")
        embeddings[source_id] = {
            "source_id": source_id,
            "artifact": expected["artifact"],
            "artifact_sha256": expected["artifact_sha256"],
            "Q_C": Q_C,
            "omega_C": omega_C,
        }
    return receipt, embeddings


def asymptotic_omega2(a: float, k: int, amplitude: float, final: bool) -> float:
    U = COEFFICIENTS["e_C"] - (COEFFICIENTS["h_C"] * amplitude if final else 0.0)
    value = COEFFICIENTS["k_Cx"] * k * k / (2.0 * a) + 1.0 / (4.0 * a * a) + U / a
    return finite_scalar(value, "asymptotic omega squared")


def omega2_at(t: float, a: float, k: int, T: float, amplitude: float) -> float:
    # sech^2(t/T) is safe over the frozen finite windows (|t/T| <= 24).
    tanh = math.tanh(t / T) if amplitude else 0.0
    U = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * amplitude * 0.5 * (1.0 + tanh)
    value = COEFFICIENTS["k_Cx"] * k * k / (2.0 * a) + 1.0 / (4.0 * a * a) + U / a
    return finite_scalar(value, "sampled omega squared")


def domega2_dt(t: float, a: float, T: float, amplitude: float) -> float:
    if amplitude == 0.0:
        return 0.0
    x = t / T
    sech2 = 1.0 / math.cosh(x) ** 2
    return finite_scalar(-COEFFICIENTS["h_C"] * amplitude * sech2 / (2.0 * a * T), "omega squared derivative")


def solve_mode(row: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    a = finite_scalar(row["a"], "a")
    k = int(row["k"])
    T = finite_scalar(row["T"], "T")
    amplitude = finite_scalar(row["amplitude"], "amplitude")
    half_span = int(row["half_span"])
    if a <= 0.0 or T <= 0.0 or k not in K_VALUES or amplitude not in (0.0, 1.0) or half_span not in (16, 24):
        raise ContractError(f"invalid schedule row {row.get('id')}")
    t_i, t_f = -half_span * T, half_span * T
    omega_in2 = asymptotic_omega2(a, k, amplitude, False)
    omega_out2 = asymptotic_omega2(a, k, amplitude, True)
    if omega_in2 <= 0.0 or omega_out2 <= 0.0:
        raise ContractError(f"nonpositive asymptotic frequency squared for {row['id']}")
    omega_in, omega_out = math.sqrt(omega_in2), math.sqrt(omega_out2)
    max_step = min(T / 16.0, 1.0 / (16.0 * omega_in), 1.0 / (16.0 * omega_out))
    n_samples = 2 * half_span * 256 + 1
    t_eval = np.linspace(t_i, t_f, n_samples, dtype=np.float64)
    if not np.all(np.isfinite(t_eval)) or t_eval.size != n_samples:
        raise ContractError(f"invalid uniform sampling grid for {row['id']}")
    u0 = np.exp(-1j * omega_in * t_i) / math.sqrt(2.0 * omega_in)
    v0 = -1j * omega_in * u0
    initial = np.array([u0.real, u0.imag, v0.real, v0.imag, 0.0], dtype=np.float64)

    def rhs(t: float, state: np.ndarray) -> np.ndarray:
        omega_sq = omega2_at(t, a, k, T, amplitude)
        u = complex(state[0], state[1])
        v = complex(state[2], state[3])
        du = v
        dv = -omega_sq * u
        dwork = domega2_dt(t, a, T, amplitude) * (u.real * u.real + u.imag * u.imag)
        return np.array([du.real, du.imag, dv.real, dv.imag, dwork], dtype=np.float64)

    solution = solve_ivp(
        rhs, (t_i, t_f), initial, method="DOP853", t_eval=t_eval,
        rtol=RTOL, atol=ATOL, max_step=max_step,
    )
    if not solution.success or solution.y.shape != (5, n_samples):
        raise ContractError(f"DOP853 failed for {row['id']}: {solution.message}")
    state = np.asarray(solution.y, dtype=np.float64)
    if not np.all(np.isfinite(state)):
        raise ContractError(f"non-finite DOP853 state for {row['id']}")
    t = np.asarray(solution.t, dtype=np.float64)
    u = state[0] + 1j * state[1]
    v = state[2] + 1j * state[3]
    work = state[4]
    omega2 = np.asarray([omega2_at(float(value), a, k, T, amplitude) for value in t], dtype=np.float64)
    if not (np.all(np.isfinite(u)) and np.all(np.isfinite(v)) and np.all(np.isfinite(work)) and np.all(np.isfinite(omega2))):
        raise ContractError(f"non-finite output array for {row['id']}")
    if np.any(omega2 <= 0.0) or np.any(np.diff(t) <= 0.0):
        raise ContractError(f"positivity or monotonicity failure for {row['id']}")
    expected_spacing = T / 256.0
    if not np.allclose(np.diff(t), expected_spacing, rtol=0.0, atol=2.0e-14):
        raise ContractError(f"uniform sampling spacing failure for {row['id']}")

    u_f, v_f = complex(u[-1]), complex(v[-1])
    alpha = np.exp(1j * omega_out * t_f) * (
        math.sqrt(omega_out / 2.0) * u_f + 1j * v_f / math.sqrt(2.0 * omega_out)
    )
    beta = np.exp(-1j * omega_out * t_f) * (
        math.sqrt(omega_out / 2.0) * u_f - 1j * v_f / math.sqrt(2.0 * omega_out)
    )
    occupation = finite_scalar(abs(beta) ** 2, "numerical occupation")
    numerator = math.sinh(math.pi * T * (omega_out - omega_in) / 2.0) ** 2
    denominator = math.sinh(math.pi * T * omega_in) * math.sinh(math.pi * T * omega_out)
    occupation_exact = finite_scalar(numerator / denominator, "analytic occupation")
    wronskian = 1j * (np.conjugate(u) * v - np.conjugate(v) * u)
    wronskian_defect = finite_scalar(np.max(np.abs(wronskian - 1.0)), "Wronskian defect")
    bogoliubov_defect = finite_scalar(abs(abs(alpha) ** 2 - abs(beta) ** 2 - 1.0), "Bogoliubov defect")
    energy_initial = finite_scalar(abs(v[0]) ** 2 + omega2[0] * abs(u[0]) ** 2, "initial energy")
    energy_final = finite_scalar(abs(v_f) ** 2 + omega2[-1] * abs(u_f) ** 2, "final energy")
    work_final = finite_scalar(work[-1], "accumulated work")
    energy_work_defect = finite_scalar(abs((energy_final - energy_initial) - work_final), "energy-work defect")
    measurements = {
        "omega_in": omega_in,
        "omega_out": omega_out,
        "alpha_re": finite_scalar(alpha.real, "alpha real"),
        "alpha_im": finite_scalar(alpha.imag, "alpha imaginary"),
        "beta_re": finite_scalar(beta.real, "beta real"),
        "beta_im": finite_scalar(beta.imag, "beta imaginary"),
        "occupation": occupation,
        "occupation_exact": occupation_exact,
        "wronskian_defect": wronskian_defect,
        "bogoliubov_defect": bogoliubov_defect,
        "energy_initial": energy_initial,
        "energy_final": energy_final,
        "work_final": work_final,
        "energy_work_defect": energy_work_defect,
        "omega2_min": finite_scalar(np.min(omega2), "minimum omega squared"),
    }
    artifact_path = output_dir / f"{row['id']}.npz"
    if artifact_path.exists():
        raise FileExistsError(f"refusing to replace trajectory artifact: {artifact_path}")
    with artifact_path.open("xb") as handle:
        np.savez(handle, t=t, u=np.asarray(u, dtype=np.complex128), v=np.asarray(v, dtype=np.complex128),
                 work=np.asarray(work, dtype=np.float64), omega2=np.asarray(omega2, dtype=np.float64))
    artifact_hash = raw_sha256(artifact_path)
    return {
        **row,
        "artifact": relative_path(artifact_path),
        "artifact_sha256": artifact_hash,
        "measurements": measurements,
    }


def dispersion_rows() -> tuple[list[dict[str, float]], list[str]]:
    rows: list[dict[str, float]] = []
    failures: list[str] = []
    for a in A_VALUES:
        for epsilon in (-0.5, 0.0, 0.75, 2.0):
            discriminant = 1.0 + 4.0 * a * epsilon
            if discriminant <= 0.0:
                raise ContractError("dispersion discriminant is not positive")
            root = math.sqrt(discriminant)
            low = 2.0 * epsilon / (1.0 + root)
            high = (-1.0 - root) / (2.0 * a)
            norm_low, norm_high = 1.0 + 2.0 * a * low, 1.0 + 2.0 * a * high
            residual_low, residual_high = a * low * low + low - epsilon, a * high * high + high - epsilon
            row = {"a": a, "epsilon": epsilon, "omega_low": low, "omega_high": high,
                   "norm_low": norm_low, "norm_high": norm_high,
                   "residual_low": residual_low, "residual_high": residual_high}
            rows.append(row)
            scale = lambda x, y: max(1.0, abs(x), abs(y))
            if abs(residual_low) > 1.0e-12 * scale(low, epsilon) or abs(residual_high) > 1.0e-12 * scale(high, epsilon):
                failures.append(f"dispersion residual a={a} epsilon={epsilon}")
            if not (norm_low > 0.0 and norm_high < 0.0):
                failures.append(f"dispersion norm signs a={a} epsilon={epsilon}")
            if abs(norm_low + norm_high) > 1.0e-12 * scale(norm_low, norm_high):
                failures.append(f"dispersion opposite norms a={a} epsilon={epsilon}")
    return rows, failures


def algebra_spot_checks() -> list[str]:
    failures: list[str] = []
    a, U = 0.03125, -1.7
    phi, phidot, phiddot = 0.8 - 0.3j, -0.2 + 0.4j, 0.7 + 0.1j
    chi_factor = a ** -0.5
    chi = chi_factor * phi
    chidot = chi_factor * (phidot + 1j * phi / (2.0 * a))
    chiddot = chi_factor * (phiddot + 1j * phidot / a - phi / (4.0 * a * a))
    parent = a * chiddot - 1j * chidot + U * chi
    canonical = chi_factor * (a * phiddot + (U + 1.0 / (4.0 * a)) * phi)
    if abs(parent - canonical) > 1.0e-12 * max(1.0, abs(parent), abs(canonical)):
        failures.append("phase rotation identity")

    z, zdot = 0.6 - 0.2j, -0.15 + 0.35j
    p_z = a * np.conjugate(zdot) + 0.5j * np.conjugate(z)
    p_zstar = a * zdot - 0.5j * z
    noether = -(p_z * (1j * z) + p_zstar * (-1j * np.conjugate(z)))
    declared = abs(z) ** 2 - 2.0 * a * np.imag(np.conjugate(z) * zdot)
    if abs(noether.real - declared) > 1.0e-12 * max(1.0, abs(declared)) or abs(noether.imag) > 1.0e-12:
        failures.append("Noether charge sign")

    omega_C, Q_C = 0.287921767986127, 16.0
    omega_parent = 2.0 * omega_C / (1.0 + math.sqrt(1.0 + 4.0 * a * omega_C))
    residual = a * omega_parent * omega_parent + omega_parent - omega_C
    if abs(residual) > 1.0e-12 * max(1.0, abs(omega_C)):
        failures.append("stationary embedding identity")
    charge = (1.0 + 2.0 * a * omega_parent) * Q_C
    direct_charge = Q_C - 2.0 * a * np.imag(np.conjugate(1.0 + 0j) * (-1j * omega_parent)) * Q_C
    if abs(charge - direct_charge) > 1.0e-12 * max(1.0, abs(charge), abs(direct_charge)):
        failures.append("stationary charge embedding")
    return failures


def make_embeddings(source_embeddings: dict[str, Any]) -> list[dict[str, Any]]:
    embeddings: list[dict[str, Any]] = []
    for source_id in ("q16_R12_n768_refine", "q256_R12_n768_refine"):
        source = source_embeddings[source_id]
        for a in A_VALUES:
            omega_C = source["omega_C"]
            omega_parent = 2.0 * omega_C / (1.0 + math.sqrt(1.0 + 4.0 * a * omega_C))
            embeddings.append({
                "source_id": source_id,
                "artifact": source["artifact"],
                "artifact_sha256": source["artifact_sha256"],
                "a": a,
                "Q_C": source["Q_C"],
                "omega_C": omega_C,
                "omega_parent": omega_parent,
                "signed_charge": (1.0 + 2.0 * a * omega_parent) * source["Q_C"],
            })
    return embeddings


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace receipt: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def failure_receipt(output_dir: Path, error: BaseException) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "failed.json"
        if path.exists():
            return
        payload = {
            "schema": SCHEMA,
            "verdict": "FAIL",
            "pass": False,
            "failures": [f"{type(error).__name__}: {error}"],
            "prereg_sha256": canonical_sha256(PREREG_PATH) if PREREG_PATH.is_file() else None,
            "source_sha256": canonical_sha256(Path(__file__)),
            "verifier_sha256": canonical_sha256(VERIFIER_PATH) if VERIFIER_PATH.is_file() else None,
            "input_sha256": raw_sha256(INPUT_RESULTS_PATH) if INPUT_RESULTS_PATH.is_file() else None,
        }
        write_json_exclusive(path, payload)
    except Exception:
        # The original exception remains the actionable failure if the destination itself is unusable.
        pass


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing nonempty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    prereg_hash = canonical_sha256(PREREG_PATH)
    source_hash = canonical_sha256(Path(__file__))
    if not VERIFIER_PATH.is_file():
        raise FileNotFoundError(VERIFIER_PATH)
    verifier_hash = canonical_sha256(VERIFIER_PATH)
    input_receipt, source_embeddings = load_stationary_inputs()
    rows_schedule = expected_schedule()
    dispersion, failures = dispersion_rows()
    failures.extend(algebra_spot_checks())
    rows: list[dict[str, Any]] = []
    for row in rows_schedule:
        rows.append(solve_mode(row, output_dir))
    if len(rows) != 31 or {row["id"] for row in rows} != {row["id"] for row in rows_schedule}:
        raise ContractError("completed trajectory set does not equal the frozen 31-row schedule")

    for row in rows:
        m = row["measurements"]
        if abs(m["occupation"] - m["occupation_exact"]) > OCCUPATION_ABS_TOL + OCCUPATION_REL_TOL * m["occupation_exact"]:
            failures.append(f"occupation agreement {row['id']}")
        if m["wronskian_defect"] > WRONSKIAN_TOL:
            failures.append(f"Wronskian defect {row['id']}")
        if m["bogoliubov_defect"] > WRONSKIAN_TOL:
            failures.append(f"Bogoliubov identity defect {row['id']}")
        scale = max(1.0, abs(m["energy_initial"]), abs(m["energy_final"]), abs(m["work_final"]))
        if m["energy_work_defect"] > ENERGY_WORK_TOL * scale:
            failures.append(f"energy-work defect {row['id']}")
        if row["amplitude"] == 0.0 and m["occupation"] > CONTROL_TOL:
            failures.append(f"constant-background occupation {row['id']}")
    by_key = {(row["a"], row["k"], row["T"], row["half_span"]): row for row in rows}
    fast = by_key[(A_VALUES[0], 0, 0.05, 16)]["measurements"]["occupation"]
    window = by_key[(A_VALUES[0], 0, 0.05, 24)]["measurements"]["occupation"]
    time_window_difference = abs(window - fast)
    if time_window_difference > TIME_WINDOW_TOL:
        failures.append("time-window occupation agreement")
    if fast <= FAST_WITNESS_MINIMUM:
        failures.append("fast witness occupation threshold")
    adiabatic_differences = []
    for a in A_VALUES:
        for k in K_VALUES:
            fast_value = by_key[(a, k, 0.05, 16)]["measurements"]["occupation"]
            slow_value = by_key[(a, k, 1.0, 16)]["measurements"]["occupation"]
            difference = fast_value - slow_value
            adiabatic_differences.append({"a": a, "k": k, "fast_minus_slow": difference})
            if difference <= ADIABATIC_MARGIN:
                failures.append(f"adiabatic ordering a={a} k={k}")

    comparisons = {
        "time_window_occupation_difference": time_window_difference,
        "fast_witness_occupation": fast,
        "adiabatic_differences": adiabatic_differences,
    }
    passed = not failures
    result = {
        "schema": SCHEMA,
        "prereg_sha256": prereg_hash,
        "source_sha256": source_hash,
        "verifier_sha256": verifier_hash,
        "input_sha256": raw_sha256(INPUT_RESULTS_PATH),
        "settings": {
            "a_values": list(A_VALUES), "k_values": list(K_VALUES), "T_values": list(T_VALUES),
            "amplitude": AMPLITUDE, "half_span": 16, "window_half_span": 24,
            "sample_spacing_factor": 256, "rtol": RTOL, "atol": ATOL,
            "method": "DOP853", "state": ["u_re", "u_im", "v_re", "v_im", "work"],
            "max_step": "min(T/16,1/(16*omega_in),1/(16*omega_out))",
            "phase_rotation": "chi=a^(-1/2) exp(i t/(2a)) phi",
            "benchmark_action_normalization": "S/hbar = integral L_a; physical N_Q=rho0 ell_Q^3 unselected",
            "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "input_results": relative_path(INPUT_RESULTS_PATH),
        },
        "coefficients": dict(COEFFICIENTS),
        "dispersion": dispersion,
        "stationary_embeddings": make_embeddings(source_embeddings),
        "rows": rows,
        "comparisons": comparisons,
        "failures": failures,
        "verdict": "PASS" if passed else "FAIL",
        "pass": passed,
        "scope": "Conditional Gaussian carrier-parent correspondence only; no physical parent selection or matter-formation adoption.",
    }
    write_json_exclusive(output_dir / "results.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()
    try:
        result = run(output_dir)
    except KeyboardInterrupt:
        return 130
    except BaseException as error:
        failure_receipt(output_dir, error)
        print(json.dumps({"schema": SCHEMA, "verdict": "FAIL", "error": f"{type(error).__name__}: {error}"}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"schema": result["schema"], "output_dir": relative_path(output_dir), "verdict": result["verdict"], "pass": result["pass"]}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
