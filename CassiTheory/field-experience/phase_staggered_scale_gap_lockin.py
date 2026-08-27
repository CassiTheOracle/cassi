#!/usr/bin/env python3
"""Frequency-domain closure for the phase-staggered scale-gap probe."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PHI = (1.0 + math.sqrt(5.0)) / 2.0
R_MAX = 60.0
DR = 0.025
SOURCE_SIGMA = 0.4
PROPAGATING_WINDOW = (10.0, 40.0)
EVANESCENT_WINDOW = (2.0, 10.0)
PARENT_RECEIPT = "20260827T093616Z_phase_staggered_scale_gap/results.json"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _relative_error(measured: float, expected: float) -> float:
    return abs(measured - expected) / max(abs(expected), 1.0e-300)


def _solve_tridiagonal(
    lower: np.ndarray,
    diagonal: np.ndarray,
    upper: np.ndarray,
    rhs: np.ndarray,
) -> np.ndarray:
    n = len(diagonal)
    modified_upper = np.zeros(n, dtype=np.complex128)
    modified_rhs = np.zeros(n, dtype=np.complex128)
    modified_upper[0] = upper[0] / diagonal[0]
    modified_rhs[0] = rhs[0] / diagonal[0]
    for index in range(1, n):
        pivot = diagonal[index] - lower[index] * modified_upper[index - 1]
        if abs(pivot) < 1.0e-14:
            raise RuntimeError(f"near-zero Thomas pivot at index {index}")
        if index < n - 1:
            modified_upper[index] = upper[index] / pivot
        modified_rhs[index] = (
            rhs[index] - lower[index] * modified_rhs[index - 1]
        ) / pivot

    solution = np.zeros(n, dtype=np.complex128)
    solution[-1] = modified_rhs[-1]
    for index in range(n - 2, -1, -1):
        solution[index] = modified_rhs[index] - modified_upper[index] * solution[index + 1]
    return solution


def _linear_residual(
    lower: np.ndarray,
    diagonal: np.ndarray,
    upper: np.ndarray,
    solution: np.ndarray,
    rhs: np.ndarray,
) -> float:
    product = diagonal * solution
    product[1:] += lower[1:] * solution[:-1]
    product[:-1] += upper[:-1] * solution[1:]
    return float(np.max(np.abs(product - rhs)) / max(float(np.max(np.abs(rhs))), 1.0))


def solve_channel(omega: float, mass: float) -> dict[str, Any]:
    n = int(round(R_MAX / DR)) + 1
    r = np.linspace(0.0, R_MAX, n, dtype=np.float64)
    source = r * np.exp(-(r * r) / (2.0 * SOURCE_SIGMA * SOURCE_SIGMA))
    source /= float(np.max(source))

    k2 = omega * omega - mass * mass
    inverse_dr2 = 1.0 / (DR * DR)
    lower = np.zeros(n, dtype=np.complex128)
    diagonal = np.zeros(n, dtype=np.complex128)
    upper = np.zeros(n, dtype=np.complex128)
    rhs = np.zeros(n, dtype=np.complex128)

    diagonal[0] = 1.0
    for index in range(1, n - 1):
        lower[index] = inverse_dr2
        diagonal[index] = -2.0 * inverse_dr2 + k2
        upper[index] = inverse_dr2
        rhs[index] = -source[index]

    lower[-1] = -1.0
    if k2 > 0.0:
        k = math.sqrt(k2)
        diagonal[-1] = 1.0 - 1j * k * DR
        boundary_type = "outgoing"
        expected_rate = k
    else:
        kappa = math.sqrt(-k2)
        diagonal[-1] = 1.0 + kappa * DR
        boundary_type = "decaying"
        expected_rate = kappa

    solution = _solve_tridiagonal(lower, diagonal, upper, rhs)
    residual = _linear_residual(lower, diagonal, upper, solution, rhs)
    return {
        "r": r,
        "solution": solution,
        "k2": k2,
        "boundary_type": boundary_type,
        "expected_rate": expected_rate,
        "linear_residual": residual,
        "finite": bool(np.all(np.isfinite(solution))),
    }


def phase_fit(channel: dict[str, Any]) -> dict[str, float]:
    r = channel["r"]
    solution = channel["solution"]
    mask = (r >= PROPAGATING_WINDOW[0]) & (r <= PROPAGATING_WINDOW[1])
    x = r[mask]
    amplitude = np.abs(solution[mask])
    phase = np.unwrap(np.angle(solution[mask]))
    slope, intercept = np.polyfit(x, phase, 1)
    fitted = slope * x + intercept
    residual = float(np.sum((phase - fitted) ** 2))
    total = float(np.sum((phase - np.mean(phase)) ** 2))
    r2 = 1.0 if total == 0.0 else 1.0 - residual / total
    return {
        "rate": abs(float(slope)),
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": r2,
        "median_amplitude": float(np.median(amplitude)),
    }


def decay_fit(channel: dict[str, Any]) -> dict[str, float]:
    r = channel["r"]
    solution = channel["solution"]
    mask = (r >= EVANESCENT_WINDOW[0]) & (r <= EVANESCENT_WINDOW[1])
    x = r[mask]
    amplitude = np.abs(solution[mask])
    log_amplitude = np.log(np.maximum(amplitude, 1.0e-300))
    slope, intercept = np.polyfit(x, log_amplitude, 1)
    fitted = slope * x + intercept
    residual = float(np.sum((log_amplitude - fitted) ** 2))
    total = float(np.sum((log_amplitude - np.mean(log_amplitude)) ** 2))
    r2 = 1.0 if total == 0.0 else 1.0 - residual / total
    return {
        "rate": abs(float(slope)),
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": r2,
        "median_amplitude": float(np.median(amplitude)),
    }


def _amplitude_at(channel: dict[str, Any], radius: float) -> float:
    r = channel["r"]
    solution = channel["solution"]
    real = np.interp(radius, r, np.real(solution))
    imag = np.interp(radius, r, np.imag(solution))
    return abs(complex(real, imag))


def main() -> int:
    omega_subgap = 0.9 * PHI
    omega_tuned = PHI ** 1.5
    omega_generic = 2.5

    l0_epsilon = solve_channel(omega_subgap, PHI)
    l1_rho = solve_channel(omega_tuned, 0.0)
    l1_epsilon = solve_channel(omega_tuned, PHI)
    l2_rho = solve_channel(omega_generic, 0.0)
    l2_epsilon = solve_channel(omega_generic, PHI)

    l0_fit = decay_fit(l0_epsilon)
    l1_rho_fit = phase_fit(l1_rho)
    l1_epsilon_fit = phase_fit(l1_epsilon)
    l2_rho_fit = phase_fit(l2_rho)
    l2_epsilon_fit = phase_fit(l2_epsilon)

    channels = {
        "L0_epsilon": (l0_epsilon, l0_fit),
        "L1_rho": (l1_rho, l1_rho_fit),
        "L1_epsilon": (l1_epsilon, l1_epsilon_fit),
        "L2_rho": (l2_rho, l2_rho_fit),
        "L2_epsilon": (l2_epsilon, l2_epsilon_fit),
    }

    attenuation = _amplitude_at(l0_epsilon, 30.0) / max(
        _amplitude_at(l0_epsilon, 12.0), 1.0e-300
    )
    tuned_ratio = l1_rho_fit["rate"] / l1_epsilon_fit["rate"]
    generic_ratio = l2_rho_fit["rate"] / l2_epsilon_fit["rate"]

    repo_root = Path(__file__).resolve().parents[1]
    parent_path = repo_root / "runs" / PARENT_RECEIPT
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    parent_arms = parent["stages"]["radial"]["arms"]
    parent_rates = {
        "L1_rho": parent_arms["D1_tuned"]["fit_rho"]["k"],
        "L1_epsilon": parent_arms["D1_tuned"]["fit_epsilon"]["k"],
        "L2_rho": parent_arms["D2_generic"]["fit_rho"]["k"],
        "L2_epsilon": parent_arms["D2_generic"]["fit_epsilon"]["k"],
    }
    lockin_rates = {
        "L1_rho": l1_rho_fit["rate"],
        "L1_epsilon": l1_epsilon_fit["rate"],
        "L2_rho": l2_rho_fit["rate"],
        "L2_epsilon": l2_epsilon_fit["rate"],
    }
    parent_residuals = {
        name: _relative_error(lockin_rates[name], parent_rates[name])
        for name in lockin_rates
    }

    quality = {
        "Q1_finite": all(channel["finite"] for channel, _ in channels.values()),
        "Q2_linear_residual": max(
            channel["linear_residual"] for channel, _ in channels.values()
        ) < 1.0e-10,
        "Q3_fit_quality": all(fit["r2"] >= 0.99 for _, fit in channels.values()),
        "Q4_amplitude": all(
            fit["median_amplitude"] > 1.0e-12 for _, fit in channels.values()
        ),
    }
    physics = {
        "L1_subgap_decay": _relative_error(l0_fit["rate"], l0_epsilon["expected_rate"]) <= 0.02,
        "L2_subgap_attenuation": attenuation <= 1.0e-2,
        "L3_tuned_propagation": _relative_error(tuned_ratio, PHI) <= 0.02,
        "L4_generic_control": abs(generic_ratio - PHI) >= 0.1,
        "L5_parent_agreement": max(parent_residuals.values()) <= 0.02,
    }

    quality_pass = all(quality.values())
    physics_pass = all(physics.values())
    verdict = "PASS" if quality_pass and physics_pass else ("FAIL" if quality_pass else "INCONCLUSIVE")

    channel_results = {
        name: {
            "k2": channel["k2"],
            "boundary_type": channel["boundary_type"],
            "expected_rate": channel["expected_rate"],
            "linear_residual": channel["linear_residual"],
            "fit": fit,
        }
        for name, (channel, fit) in channels.items()
    }
    results = {
        "protocol": "field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "parent_receipt": f"runs/{PARENT_RECEIPT}",
        "channels": channel_results,
        "subgap_attenuation": attenuation,
        "tuned_ratio": tuned_ratio,
        "tuned_phi_relative_residual": _relative_error(tuned_ratio, PHI),
        "generic_ratio": generic_ratio,
        "generic_phi_distance": abs(generic_ratio - PHI),
        "parent_relative_residuals": parent_residuals,
        "quality_gates": quality,
        "physics_gates": physics,
        "verdict": verdict,
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = repo_root / "runs" / f"{timestamp}_phase_staggered_scale_gap_lockin"
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "results.json"
    output_path.write_text(json.dumps(_jsonable(results), indent=2) + "\n", encoding="utf-8")

    print(
        "Q",
        "PASS" if quality_pass else "FAIL",
        f"max_linear_residual={max(channel['linear_residual'] for channel, _ in channels.values()):.3e}",
        f"min_r2={min(fit['r2'] for _, fit in channels.values()):.12f}",
    )
    print(
        "L0",
        "PASS" if physics["L1_subgap_decay"] and physics["L2_subgap_attenuation"] else "FAIL",
        f"kappa_fit={l0_fit['rate']:.12f}",
        f"kappa_expected={l0_epsilon['expected_rate']:.12f}",
        f"attenuation={attenuation:.3e}",
    )
    print(
        "L1/L2",
        "PASS" if physics["L3_tuned_propagation"] and physics["L4_generic_control"] else "FAIL",
        f"tuned_ratio={tuned_ratio:.12f}",
        f"generic_ratio={generic_ratio:.12f}",
        f"parent_max_residual={max(parent_residuals.values()):.3e}",
    )
    print(f"VERDICT {verdict}")
    print(f"RAW {output_path.as_posix()}")
    if verdict == "PASS":
        print("ALL LOCK-IN CLOSURE GATES PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
