#!/usr/bin/env python3
"""Primary finite-mode fermion production and semiclassical backreaction calculation.

Canonical execution (after inspecting both source programs):
    python computations/matter_formation_fermion_production.py --output-dir <directory>

The implementation is deliberately standalone.  It uses four-component Dirac
covariances, exact constant-Hamiltonian propagation, and the exact integrated
fermion force in the registered symmetric A/B/A composition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "computations" / "matter-formation-fermion-production-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_fermion_production.py"
SCHEMA = "cassi.matter-formation.fermion-production.v1"

V = 4.0 * math.pi
OMEGA = 3.0
OMEGA2 = OMEGA * OMEGA
M0 = 1.0
MOMENTA = np.asarray((0.0, 0.5, 1.0, 2.0), dtype=np.float64)
EXCURSION_MASSES = np.asarray((0.5, 2.0), dtype=np.float64)
PULSE_DURATIONS = np.asarray((0.25, 1.0, 3.0), dtype=np.float64)
FINAL_TIME = 12.0

# Exact registered order.  The tuple fields are case, dt, steps, y, initial Pi,
# and whether the fermionic force is included in the B subflow.
TRAJECTORIES = (
    ("closed_coarse", 0.02, 600, 0.25, 3.0 * V, True),
    ("closed_medium", 0.01, 1200, 0.25, 3.0 * V, True),
    ("closed_fine", 0.005, 2400, 0.25, 3.0 * V, True),
    ("feedback_off", 0.005, 2400, 0.25, 3.0 * V, False),
    ("coupling_zero", 0.005, 2400, 0.0, 3.0 * V, True),
    ("pump_zero", 0.005, 2400, 0.25, 0.0, True),
)
TRAJECTORY_CASES = tuple(item[0] for item in TRAJECTORIES)

# Dirac representation, with the up-spin indices (0, 2) and down-spin indices
# (1, 3), as registered in the protocol.
_SIGMA_Z = np.asarray(((1.0, 0.0), (0.0, -1.0)), dtype=np.complex128)
_BETA = np.diag((1.0, 1.0, -1.0, -1.0)).astype(np.complex128)
_ALPHA_Z = np.zeros((4, 4), dtype=np.complex128)
_ALPHA_Z[np.ix_((0, 1), (2, 3))] = _SIGMA_Z
_ALPHA_Z[np.ix_((2, 3), (0, 1))] = _SIGMA_Z
_ID4 = np.eye(4, dtype=np.complex128)


def canonical_sha256(path: Path) -> str:
    """Hash UTF-8 source/specification bytes after CRLF-to-LF normalization."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(path: Path) -> str:
    """Hash generated artifact bytes without text normalization."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    """Return a root-relative, POSIX-form path for a receipt identity."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(__import__("os").path.relpath(path.resolve(), ROOT)).as_posix()


def _identity(path: Path, label: str, failures: list[str]) -> dict[str, str]:
    identity = {"path": relative_path(path), "sha256": ""}
    try:
        identity["sha256"] = canonical_sha256(path)
    except Exception as exc:
        failures.append(f"missing {label} identity: {type(exc).__name__}: {exc}")
    return identity


def _finite_scalar(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite scalar {label}")
    return result


def _as_json(value: Any) -> Any:
    """Convert NumPy values while rejecting non-finite JSON numbers."""
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    if isinstance(value, np.ndarray):
        return [_as_json(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_as_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON value")
    return value


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to replace receipt: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(_as_json(payload), stream, indent=2, sort_keys=False, allow_nan=False)
        stream.write("\n")


def write_npz_exclusive(path: Path, arrays: dict[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to replace trajectory artifact: {path}")
    with path.open("xb") as stream:
        np.savez(stream, **arrays)
    return raw_sha256(path)


def _sinc(x: float) -> float:
    if abs(x) < 1.0e-5:
        x2 = x * x
        return 1.0 - x2 / 6.0 + x2 * x2 / 120.0 - x2 * x2 * x2 / 5040.0
    return math.sin(x) / x


def _one_minus_cos_over_x(x: float) -> float:
    if abs(x) < 1.0e-4:
        x2 = x * x
        return x * (0.5 - x2 / 24.0 + x2 * x2 / 720.0 - x2 * x2 * x2 / 40320.0)
    return (1.0 - math.cos(x)) / x


def hamiltonian(p: float, mass: float) -> np.ndarray:
    return p * _ALPHA_Z + mass * _BETA


def projectors(H: np.ndarray, energy: float) -> tuple[np.ndarray, np.ndarray]:
    K = H / energy
    return 0.5 * (_ID4 + K), 0.5 * (_ID4 - K)


def mode_energy(p: float, mass: float) -> float:
    return math.sqrt(p * p + mass * mass)


def initial_covariances() -> np.ndarray:
    result = np.empty((4, 4, 4), dtype=np.complex128)
    for j, p in enumerate(MOMENTA):
        H = hamiltonian(float(p), M0)
        E = mode_energy(float(p), M0)
        result[j] = projectors(H, E)[1]
    return result


COVARIANCE_INITIAL = initial_covariances()


def propagate_covariance(C: np.ndarray, H: np.ndarray, duration: float) -> np.ndarray:
    """Exact exp(-i H t) C exp(+i H t) using H^2 = E^2 I."""
    E = math.sqrt(float(np.real(np.trace(H @ H))) / 4.0)
    x = E * duration
    U = math.cos(x) * _ID4 - 1j * (duration * _sinc(x)) * H
    return U @ C @ U.conj().T


def integrated_covariance(C: np.ndarray, H: np.ndarray, duration: float) -> np.ndarray:
    """Exact integral of the covariance over a constant-H B subflow."""
    E = math.sqrt(float(np.real(np.trace(H @ H))) / 4.0)
    x = 2.0 * E * duration
    K = H / E if E != 0.0 else np.zeros_like(H)
    a = 0.5 * duration + 0.5 * duration * _sinc(x)
    b = 0.5 * duration - 0.5 * duration * _sinc(x)
    c = 0.5 * duration * _one_minus_cos_over_x(x)
    return a * C + b * (K @ C @ K) - 1j * c * (K @ C - C @ K)


def _occupation(C: np.ndarray, H: np.ndarray, E: float) -> tuple[float, float]:
    P_plus, P_minus = projectors(H, E)
    n_plus = 0.5 * float(np.real(np.trace(P_plus @ C)))
    n_minus = 0.5 * float(np.real(np.trace(P_minus @ (_ID4 - C))))
    return n_plus, n_minus


def _residuals(C: np.ndarray, H: np.ndarray, E: float) -> tuple[float, float, float, float, float, float, float, float]:
    n_plus, n_minus = _occupation(C, H, E)
    projector = float(np.linalg.norm(C @ C - C, ord="fro") / math.sqrt(2.0))
    hermiticity = float(np.linalg.norm(C - C.conj().T, ord="fro") / math.sqrt(2.0))
    trace = abs(float(np.real(np.trace(C))) / 2.0 - 1.0)
    charge = abs(n_plus - n_minus)
    eigs = np.linalg.eigvalsh((C + C.conj().T) * 0.5)
    return n_plus, n_minus, projector, hermiticity, trace, charge, float(np.min(eigs)), float(np.max(eigs))


def pulse_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # The frozen order is all eight quenches first.
    for j, p in enumerate(MOMENTA):
        p_float = float(p)
        E0 = mode_energy(p_float, M0)
        H0 = hamiltonian(p_float, M0)
        C0 = COVARIANCE_INITIAL[j]
        for m1 in EXCURSION_MASSES:
            m_float = float(m1)
            E1 = mode_energy(p_float, m_float)
            H1 = hamiltonian(p_float, m_float)
            n_quench = 0.5 * (1.0 - (p_float * p_float + M0 * m_float) / (E0 * E1))
            quench_np, quench_nm = _occupation(C0, H1, E1)
            quench_work = 0.5 * float(np.real(np.trace((H1 - H0) @ C0)))
            quench_vac = E0 - E1
            quench_exc = 2.0 * E1 * quench_np
            q_res = _residuals(C0, H1, E1)
            rows.append(
                {
                    "kind": "quench", "p": p_float, "mu_initial": M0,
                    "mu_excursion": m_float, "duration": 0.0,
                    "occupation": quench_np, "hole_occupation": quench_nm,
                    "analytic_occupation": n_quench, "work": quench_work,
                    "vacuum_energy_change": quench_vac,
                    "excitation_energy": quench_exc,
                    "work_balance_residual": abs(quench_work - quench_vac - quench_exc),
                    "charge_residual": q_res[5], "projector_residual": q_res[2],
                    "hermiticity_residual": q_res[3], "trace_residual": q_res[4],
                }
            )
    # Then the 24 pulses, with duration as the innermost registered loop.
    for j, p in enumerate(MOMENTA):
        p_float = float(p)
        E0 = mode_energy(p_float, M0)
        H0 = hamiltonian(p_float, M0)
        C0 = COVARIANCE_INITIAL[j]
        for m1 in EXCURSION_MASSES:
            m_float = float(m1)
            E1 = mode_energy(p_float, m_float)
            H1 = hamiltonian(p_float, m_float)
            for duration in PULSE_DURATIONS:
                T = float(duration)
                C_T = propagate_covariance(C0, H1, T)
                pulse_np, pulse_nm = _occupation(C_T, H0, E0)
                analytic = (p_float * p_float * (m_float - M0) ** 2 / (E0 * E0 * E1 * E1)) * math.sin(E1 * T) ** 2
                pulse_work = 0.5 * float(np.real(np.trace((H1 - H0) @ C0 + (H0 - H1) @ C_T)))
                pulse_exc = 2.0 * E0 * pulse_np
                p_res = _residuals(C_T, H0, E0)
                rows.append(
                    {
                        "kind": "pulse", "p": p_float, "mu_initial": M0,
                        "mu_excursion": m_float, "duration": T,
                        "occupation": pulse_np, "hole_occupation": pulse_nm,
                        "analytic_occupation": analytic, "work": pulse_work,
                        "vacuum_energy_change": 0.0,
                        "excitation_energy": pulse_exc,
                        "work_balance_residual": abs(pulse_work - pulse_exc),
                        "charge_residual": p_res[5], "projector_residual": p_res[2],
                        "hermiticity_residual": p_res[3], "trace_residual": p_res[4],
                    }
                )
    if len(rows) != 32:
        raise AssertionError(f"pulse schedule produced {len(rows)} rows")
    return rows


def _validate_constants() -> None:
    if MOMENTA.shape != (4,) or not np.array_equal(MOMENTA, np.asarray((0.0, 0.5, 1.0, 2.0))):
        raise ValueError("registered momentum schedule mismatch")
    if EXCURSION_MASSES.shape != (2,) or not np.array_equal(EXCURSION_MASSES, np.asarray((0.5, 2.0))):
        raise ValueError("registered excursion schedule mismatch")
    if PULSE_DURATIONS.shape != (3,) or not np.array_equal(PULSE_DURATIONS, np.asarray((0.25, 1.0, 3.0))):
        raise ValueError("registered pulse schedule mismatch")
    if COVARIANCE_INITIAL.shape != (4, 4, 4) or not np.isfinite(COVARIANCE_INITIAL).all():
        raise ValueError("initial covariance shape/finite check failed")
    if not np.isfinite(_BETA).all() or not np.isfinite(_ALPHA_Z).all():
        raise ValueError("Dirac matrices are not finite")


def _validate_trajectory_arrays(arrays: dict[str, np.ndarray], steps: int) -> None:
    expected = {"time": (steps + 1,), "f": (steps + 1,), "pi": (steps + 1,),
                "covariance_re": (steps + 1, 4, 4, 4), "covariance_im": (steps + 1, 4, 4, 4)}
    if set(arrays) != set(expected):
        raise ValueError("trajectory array key mismatch")
    for key, shape in expected.items():
        array = arrays[key]
        if array.shape != shape or array.dtype != np.float64 or not np.isfinite(array).all():
            raise ValueError(f"invalid trajectory array {key}")


def _validate_pulse_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 32:
        raise ValueError("pulse row count mismatch")
    expected_keys = ("kind", "p", "mu_initial", "mu_excursion", "duration", "occupation", "hole_occupation", "analytic_occupation", "work", "vacuum_energy_change", "excitation_energy", "work_balance_residual", "charge_residual", "projector_residual", "hermiticity_residual", "trace_residual")
    if any(tuple(row) != expected_keys for row in rows):
        raise ValueError("pulse row key order mismatch")
    for row in rows:
        if row["kind"] not in ("quench", "pulse") or not all(math.isfinite(float(row[key])) for key in expected_keys[1:]):
            raise ValueError("invalid pulse row value")


def diagnose_trajectory(case: str, dt: float, steps: int, y: float, initial_pi: float, arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    cov_re = arrays["covariance_re"]
    cov_im = arrays["covariance_im"]
    particle = np.empty((steps + 1, 4), dtype=np.float64)
    hole = np.empty((steps + 1, 4), dtype=np.float64)
    projector_max = hermiticity_max = trace_max = charge_max = 0.0
    occupation_min = math.inf
    occupation_max = -math.inf
    zero_momentum_max = 0.0
    eigen_min = math.inf
    eigen_max = -math.inf
    mass_min = math.inf
    mass_max = -math.inf
    total_energy = np.empty(steps + 1, dtype=np.float64)
    scalar_energy = np.empty(steps + 1, dtype=np.float64)
    vacuum_energy = np.empty(steps + 1, dtype=np.float64)
    excitation_energy = np.empty(steps + 1, dtype=np.float64)
    partition_max = 0.0
    for step in range(steps + 1):
        f = float(arrays["f"][step])
        pi = float(arrays["pi"][step])
        scalar = pi * pi / (2.0 * V) + V * OMEGA2 * f * f / 2.0
        vac = 0.0
        exc = 0.0
        direct_quantum = 0.0
        for j, p in enumerate(MOMENTA):
            mass = M0 + y * f
            E = mode_energy(float(p), mass)
            H = hamiltonian(float(p), mass)
            C = cov_re[step, j] + 1j * cov_im[step, j]
            n_plus, n_minus, proj, herm, tr, charge, eig_lo, eig_hi = _residuals(C, H, E)
            particle[step, j] = n_plus
            hole[step, j] = n_minus
            occupation_min = min(occupation_min, n_plus, n_minus)
            occupation_max = max(occupation_max, n_plus, n_minus)
            if j == 0:
                zero_momentum_max = max(zero_momentum_max, abs(n_plus), abs(n_minus))
            projector_max = max(projector_max, proj)
            hermiticity_max = max(hermiticity_max, herm)
            trace_max = max(trace_max, tr)
            charge_max = max(charge_max, charge)
            eigen_min = min(eigen_min, eig_lo)
            eigen_max = max(eigen_max, eig_hi)
            mass_min = min(mass_min, mass)
            mass_max = max(mass_max, mass)
            vac += -2.0 * E - float(np.real(np.trace(H @ COVARIANCE_INITIAL[j])))
            exc += 4.0 * E * n_plus
            direct_quantum += float(np.real(np.trace(H @ (C - COVARIANCE_INITIAL[j]))))
        direct = scalar + direct_quantum
        partition = scalar + vac + exc
        total_energy[step] = direct
        scalar_energy[step] = scalar
        vacuum_energy[step] = vac
        excitation_energy[step] = exc
        partition_max = max(partition_max, abs(direct - partition))
    initial_total = float(total_energy[0])
    errors = np.abs(total_energy - initial_total)
    relative_error = float(np.max(errors) / max(1.0, abs(initial_total)))
    summary = {
        "case": case, "steps": int(steps), "dt": float(dt), "duration": float(dt * steps),
        "g": float(y), "initial_pi": float(initial_pi), "final_f": float(arrays["f"][-1]),
        "final_pi": float(arrays["pi"][-1]), "final_particle": particle[-1].tolist(),
        "final_hole": hole[-1].tolist(), "peak_particle": np.max(particle, axis=0).tolist(),
        "max_projector_residual": projector_max, "max_hermiticity_residual": hermiticity_max,
        "max_trace_residual": trace_max, "max_charge_residual": charge_max,
        "min_covariance_eigenvalue": eigen_min, "max_covariance_eigenvalue": eigen_max,
        "min_mass": mass_min, "max_mass": mass_max, "initial_total_energy": initial_total,
        "final_total_energy": float(total_energy[-1]), "max_total_energy_error": float(np.max(errors)),
        "relative_energy_error": relative_error, "final_scalar_energy": float(scalar_energy[-1]),
        "final_vacuum_energy": float(vacuum_energy[-1]), "final_excitation_energy": float(excitation_energy[-1]),
        "energy_partition_residual": partition_max,
        "_min_occupation": occupation_min, "_max_occupation": occupation_max,
        "_zero_momentum_max": zero_momentum_max,
    }
    return summary


def integrate_trajectory(case: str, dt: float, steps: int, y: float, initial_pi: float, feedback: bool) -> dict[str, np.ndarray]:
    _finite_scalar(dt, f"{case}.dt")
    if steps <= 0 or not math.isclose(dt * steps, FINAL_TIME, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(f"invalid fixed schedule for {case}")
    time = np.arange(steps + 1, dtype=np.float64) * dt
    f_values = np.empty(steps + 1, dtype=np.float64)
    pi_values = np.empty(steps + 1, dtype=np.float64)
    covariances = np.empty((steps + 1, 4, 4, 4), dtype=np.complex128)
    f = 0.0
    pi = float(initial_pi)
    C = COVARIANCE_INITIAL.copy()
    f_values[0], pi_values[0], covariances[0] = f, pi, C
    for step in range(steps):
        f += 0.5 * dt * pi / V
        force_integral = 0.0
        evolved = np.empty_like(C)
        mass = M0 + y * f
        for j, p in enumerate(MOMENTA):
            H = hamiltonian(float(p), mass)
            integrated = integrated_covariance(C[j], H, dt)
            force_integral += float(np.real(np.trace(_BETA @ (integrated - dt * COVARIANCE_INITIAL[j]))))
            evolved[j] = propagate_covariance(C[j], H, dt)
        pi -= dt * V * OMEGA2 * f
        if feedback:
            pi -= y * force_integral
        C = evolved
        f += 0.5 * dt * pi / V
        f_values[step + 1], pi_values[step + 1], covariances[step + 1] = f, pi, C
    arrays = {
        "time": time, "f": f_values, "pi": pi_values,
        "covariance_re": np.asarray(covariances.real, dtype=np.float64),
        "covariance_im": np.asarray(covariances.imag, dtype=np.float64),
    }
    _validate_trajectory_arrays(arrays, steps)
    return arrays


def _base_receipt(identities: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "identities": identities, "artifacts": {}, "pulse_rows": [],
        "trajectory_summaries": [], "convergence": {}, "verdicts": {},
        "numerical_pass": False, "failures": [],
    }


def _qualify(pulse: list[dict[str, Any]], summaries: list[dict[str, Any]], convergence: dict[str, float]) -> tuple[bool, dict[str, str], list[str]]:
    failures: list[str] = []
    analytic_ok = True
    for row in pulse:
        discrepancy = max(abs(float(row["occupation"]) - float(row["analytic_occupation"])), float(row["work_balance_residual"]))
        if discrepancy > 2.0e-11:
            analytic_ok = False
        if row["p"] == 0.0:
            if max(abs(float(row[key])) for key in ("analytic_occupation", "occupation", "hole_occupation")) > 2.0e-11:
                analytic_ok = False
        elif float(row["analytic_occupation"]) <= 1.0e-8:
            analytic_ok = False
    if not analytic_ok:
        failures.append("analytic occupation/work qualification failed")
    pauli_ok = all(
        -5.0e-10 <= row["occupation"] <= 1.0 + 5.0e-10
        and -5.0e-10 <= row["hole_occupation"] <= 1.0 + 5.0e-10
        for row in pulse
    )
    pulse_invariants_ok = all(
        row["projector_residual"] <= 5.0e-10
        and row["hermiticity_residual"] <= 5.0e-10
        and row["trace_residual"] <= 5.0e-10
        and row["charge_residual"] <= 5.0e-10
        for row in pulse
    )
    charge_ok = all(row["charge_residual"] <= 5.0e-10 for row in pulse)
    if not pauli_ok:
        failures.append("pulse Pauli bound failed")
    if not pulse_invariants_ok:
        failures.append("pulse invariant residual qualification failed")
    if not charge_ok:
        failures.append("pulse charge qualification failed")
    trajectory_ok = True
    for summary in summaries:
        if summary["_min_occupation"] < -5.0e-10 or summary["_max_occupation"] > 1.0 + 5.0e-10:
            trajectory_ok = False
        if summary["max_projector_residual"] > 5.0e-10 or summary["max_hermiticity_residual"] > 5.0e-10 or summary["max_trace_residual"] > 5.0e-10 or summary["max_charge_residual"] > 5.0e-10:
            trajectory_ok = False
        if summary["min_covariance_eigenvalue"] < -5.0e-10 or summary["max_covariance_eigenvalue"] > 1.0 + 5.0e-10:
            trajectory_ok = False
        if summary["energy_partition_residual"] > 5.0e-10 or summary["min_mass"] <= 0.0:
            trajectory_ok = False
    if not trajectory_ok:
        failures.append("trajectory invariant/partition qualification failed")
    by_case = {summary["case"]: summary for summary in summaries}
    for case in ("closed_fine", "coupling_zero", "pump_zero"):
        if by_case[case]["relative_energy_error"] > 2.0e-4:
            failures.append(f"energy conservation failed: {case}")
    if any(max(abs(by_case[case]["_min_occupation"]), abs(by_case[case]["_max_occupation"])) > 5.0e-10 for case in ("coupling_zero", "pump_zero")):
        failures.append("zero controls produced resolved occupation")
    if any(summary["_zero_momentum_max"] > 5.0e-10 for summary in summaries):
        failures.append("zero-momentum trajectory occupation exceeded bound")
    if convergence["medium_fine_difference"] <= 1.0e-10:
        failures.append("medium-fine difference is not resolved")
    if not 3.0 <= convergence["ratio"] <= 5.0:
        failures.append("convergence ratio outside registered interval")
    numerical_pass = not failures
    verdicts = {
        "fermion_correspondence": "SUPPORTS—finite-mode fermion pair correspondence" if analytic_ok and pauli_ok and charge_ok and pulse_invariants_ok else "INCONCLUSIVE",
        "closed_backreaction": ("SUPPORTS—energy-accounted semiclassical fermion production in the specified finite-mode model" if numerical_pass and convergence["production_peak"] > 1.0e-6 and convergence["feedback_effect"] > 1.0e-6 else "DOES NOT EMERGE—production and feedback at the registered thresholds" if numerical_pass else "INCONCLUSIVE"),
    }
    return numerical_pass, verdicts, failures


def run(output_dir: Path, prereg_path: Path = PREREG_PATH) -> dict[str, Any]:
    failures: list[str] = []
    identities = {
        "primary": _identity(Path(__file__), "primary", failures),
        "verifier": _identity(VERIFIER_PATH, "verifier", failures),
        "prereg": _identity(prereg_path, "preregistration", failures),
    }
    receipt = _base_receipt(identities)
    if failures:
        receipt["failures"] = failures
        write_json_exclusive(output_dir / "results.json", receipt)
        return receipt
    _validate_constants()
    rows = pulse_rows()
    _validate_pulse_rows(rows)
    receipt["pulse_rows"] = rows
    summaries: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, str]] = {}
    for case, dt, steps, y, initial_pi, feedback in TRAJECTORIES:
        arrays = integrate_trajectory(case, dt, steps, y, initial_pi, feedback)
        summary = diagnose_trajectory(case, dt, steps, y, initial_pi, arrays)
        artifact_path = output_dir / f"{case}.npz"
        artifact_hash = write_npz_exclusive(artifact_path, arrays)
        artifacts[case] = {"path": artifact_path.name, "sha256": artifact_hash}
        summaries.append(summary)
    if tuple(summary["case"] for summary in summaries) != TRAJECTORY_CASES:
        raise AssertionError("trajectory order mismatch")
    receipt["artifacts"] = artifacts
    receipt["trajectory_summaries"] = summaries
    by_case = {summary["case"]: summary for summary in summaries}
    # Reconstruct convergence directly from the retained NPZ arrays, avoiding any
    # scalar summary as a substitute for the declared all-time comparison.
    loaded: dict[str, dict[str, np.ndarray]] = {}
    for case in TRAJECTORY_CASES:
        with np.load(output_dir / f"{case}.npz", allow_pickle=False) as archive:
            loaded[case] = {key: np.asarray(archive[key], dtype=np.float64) for key in archive.files}
    def u(case: str) -> np.ndarray:
        data = loaded[case]
        n = np.empty((data["time"].size, 6), dtype=np.float64)
        for k in range(data["time"].size):
            f = float(data["f"][k]); pi = float(data["pi"][k])
            n[k, :2] = (f, pi / (3.0 * V))
            for j, p in enumerate(MOMENTA):
                mass = M0 + by_case[case]["g"] * f
                H = hamiltonian(float(p), mass)
                E = mode_energy(float(p), mass)
                C = data["covariance_re"][k, j] + 1j * data["covariance_im"][k, j]
                n[k, 2 + j] = _occupation(C, H, E)[0]
        return n
    uc, um, uf = u("closed_coarse"), u("closed_medium"), u("closed_fine")
    d_cm = float(np.max(np.abs(uc - um[::2])))
    d_mf = float(np.max(np.abs(um - uf[::2])))
    feedback_diff = float(np.max(np.abs(uf[:, :2] - u("feedback_off")[:, :2])))
    production_peak = float(np.max(uf[:, 3:6]))
    convergence = {
        "coarse_medium_difference": d_cm, "medium_fine_difference": d_mf,
        "ratio": d_cm / d_mf if d_mf != 0.0 else 0.0,
        "feedback_effect": feedback_diff, "production_peak": production_peak,
    }
    # Convergence is computed from the retained raw arrays, independently from
    # scalar summary fields.
    receipt["convergence"] = convergence
    numerical_pass, verdicts, qualification_failures = _qualify(rows, summaries, convergence)
    for summary in summaries:
        summary.pop("_min_occupation", None)
        summary.pop("_max_occupation", None)
        summary.pop("_zero_momentum_max", None)
    receipt["verdicts"] = verdicts
    receipt["numerical_pass"] = numerical_pass
    receipt["failures"] = qualification_failures
    write_json_exclusive(output_dir / "results.json", receipt)
    print(f"numerical_pass={numerical_pass}")
    print(f"production_peak={production_peak:.17g} feedback_effect={feedback_diff:.17g} convergence_ratio={convergence['ratio']:.17g}")
    print(f"fermion_correspondence={verdicts['fermion_correspondence']}")
    print(f"closed_backreaction={verdicts['closed_backreaction']}")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, default=PREREG_PATH)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()
    targets = [output_dir / "results.json", *(output_dir / f"{case}.npz" for case in TRAJECTORY_CASES)]
    if any(path.exists() for path in targets):
        print("refusing to replace an existing result or trajectory target", file=sys.stderr)
        return 1
    try:
        result = run(output_dir, args.prereg.resolve())
    except Exception as exc:
        failure = _base_receipt({
            "primary": {"path": relative_path(Path(__file__)), "sha256": canonical_sha256(Path(__file__))},
            "verifier": {"path": relative_path(VERIFIER_PATH), "sha256": canonical_sha256(VERIFIER_PATH) if VERIFIER_PATH.is_file() else ""},
            "prereg": {"path": relative_path(args.prereg), "sha256": canonical_sha256(args.prereg) if args.prereg.is_file() else ""},
        })
        failure["failures"] = [f"{type(exc).__name__}: {exc}"]
        try:
            write_json_exclusive(output_dir / "results.json", failure)
        except Exception as write_exc:
            print(f"{type(exc).__name__}: {exc}; could not write failure receipt: {write_exc}", file=sys.stderr)
            return 1
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not result["numerical_pass"]:
        print("; ".join(result["failures"]) or "numerical qualification failed", file=sys.stderr)
    return 0 if result["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
