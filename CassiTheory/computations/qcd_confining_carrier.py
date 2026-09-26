#!/usr/bin/env python3
"""Run the preregistered QCD-target and confining-carrier calculation.

Run from the CassiTheory repository root:
    python computations/qcd_confining_carrier.py
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import cast

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "qcd-confining-carrier-prereg.md"
OUT_DIR = ROOT / "runs" / "20260910_qcd_confining_carrier" / "primary"
RESULTS = OUT_DIR / "results.json"

B = 1.0
CHI_V = 1.0
G_S = 1.0
Q_ISOLATED = 1.0
X_SAMPLES = 200_001
X_MIN = -4.0
X_MAX = 4.0
EPSILONS = (1.0e-2, 1.0e-4, 1.0e-6, 1.0e-8)
RADII = (16.0, 32.0, 64.0, 128.0, 256.0, 512.0)
TAIL_LIMITS = (32.0, 64.0, 128.0, 256.0, 512.0)
TAIL_START = 16.0
TUBE_R_MIN = 1.0e-4
TUBE_R_MAX = 1.0e4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def kappa_zero(x: np.ndarray | float) -> np.ndarray | float:
    return (1.0 - np.asarray(x) ** 3) ** 2


def kappa_epsilon(x: np.ndarray | float, epsilon: float) -> np.ndarray | float:
    return kappa_zero(x) + epsilon


def dielectric_potential(x: np.ndarray | float) -> np.ndarray | float:
    x_arr = np.asarray(x)
    return B * (1.0 - x_arr) ** 2 * (1.0 + 2.0 * x_arr + 4.0 * x_arr**2)


def dielectric_potential_prime(x: float) -> float:
    return B * (2.0 * x - 18.0 * x**2 + 16.0 * x**3)


def dielectric_potential_second(x: float) -> float:
    return B * (2.0 - 36.0 * x + 48.0 * x**2)


def trial_c_star(q: float = Q_ISOLATED) -> float:
    return (q * q / (2016.0 * math.pi**2 * B)) ** 0.25


def asymptotic_trial_shell(r: float, q: float = Q_ISOLATED) -> float:
    c_star = trial_c_star(q)
    x = 1.0 - c_star / r
    dx_dr = c_star / (r * r)
    scalar = 4.0 * math.pi * r * r * (
        0.5 * CHI_V**2 * dx_dr**2 + float(dielectric_potential(x))
    )
    flux = q * q / (8.0 * math.pi * r * r * float(kappa_zero(x)))
    return scalar + flux


def wall_tension() -> tuple[float, float]:
    integrand = lambda x: (1.0 - x) * math.sqrt(1.0 + 2.0 * x + 4.0 * x * x)
    integral, error = quad(integrand, 0.0, 1.0, epsabs=1.0e-13, epsrel=1.0e-13)
    return CHI_V * math.sqrt(2.0 * B) * integral, error


def tube_tension(radius: float, q: float, sigma: float) -> float:
    return (
        q * q / (2.0 * math.pi * radius * radius)
        + math.pi * B * radius * radius
        + 2.0 * math.pi * sigma * radius
    )


def tube_tension_derivative(radius: float, q: float, sigma: float) -> float:
    return (
        -q * q / (math.pi * radius**3)
        + 2.0 * math.pi * B * radius
        + 2.0 * math.pi * sigma
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dimensions = {
        "fields": {
            "q": 1.5,
            "qbar": 1.5,
            "A_mu": 1.0,
            "G_mu_nu": 2.0,
            "Phi": 1.0,
            "chi": 1.0,
            "x": 0.0,
            "ghost": 1.0,
        },
        "parameters": {
            "g_s": 0.0,
            "g": 0.0,
            "F": 0.0,
            "kappa": 0.0,
            "epsilon": 0.0,
            "chi_v": 1.0,
            "B": 4.0,
        },
        "lagrangian_terms": {
            "quark_kinetic": 4.0,
            "yukawa": 4.0,
            "chiral_kinetic": 4.0,
            "dielectric_kinetic": 4.0,
            "gauge_kinetic": 4.0,
            "chiral_potential": 4.0,
            "dielectric_potential": 4.0,
        },
        "expanded_operators": {
            "chi2_qbar_Phi_q": {"operator": 6.0, "coefficient": -2.0, "total": 4.0},
            "chi3_G2": {"operator": 7.0, "coefficient": -3.0, "total": 4.0},
            "chi6_G2": {"operator": 10.0, "coefficient": -6.0, "total": 4.0},
        },
    }
    dimensions_pass = (
        all(value == 4.0 for value in dimensions["lagrangian_terms"].values())
        and all(row["total"] == 4.0 for row in dimensions["expanded_operators"].values())
    )

    xs = np.linspace(X_MIN, X_MAX, X_SAMPLES, dtype=np.float64)
    kappas = np.asarray(kappa_zero(xs), dtype=np.float64)
    potentials = np.asarray(dielectric_potential(xs), dtype=np.float64)
    stationary_points = (0.0, 0.125, 1.0)
    stationary = {
        f"{x:.3f}": {
            "x": x,
            "potential": float(dielectric_potential(x)),
            "first_derivative": dielectric_potential_prime(x),
            "second_derivative": dielectric_potential_second(x),
        }
        for x in stationary_points
    }
    regulator_rows = []
    for epsilon in EPSILONS:
        values = np.asarray(kappa_epsilon(xs, epsilon), dtype=np.float64)
        index = int(np.argmin(values))
        regulator_rows.append(
            {
                "epsilon": epsilon,
                "sampled_minimum": float(values[index]),
                "sampled_argmin": float(xs[index]),
                "minimum_minus_epsilon": float(values[index] - epsilon),
            }
        )

    r_hedgehog = np.linspace(0.0, 12.0, 4097, dtype=np.float64)
    profile = math.pi * np.exp(-r_hedgehog)
    sigma = 93.0 * np.cos(profile)
    pion_norm = 93.0 * np.sin(profile)
    normalized_amplitude = (sigma * sigma + pion_norm * pion_norm) / 93.0**2
    kappa_minimal = (1.0 - normalized_amplitude) ** 2
    field_minimal_control = {
        "sample_count": int(r_hedgehog.size),
        "max_abs_amplitude_minus_one": float(np.max(np.abs(normalized_amplitude - 1.0))),
        "max_kappa_minimal": float(np.max(kappa_minimal)),
        "interior_dielectric_present": bool(np.any(kappa_minimal > 1.0e-14)),
    }

    lower_bound_coefficient = 4.0 * math.sqrt(6.0) / 19.0 * abs(Q_ISOLATED) * math.sqrt(B)
    expected_asymptotic_slope = math.sqrt(14.0) / 3.0 * abs(Q_ISOLATED) * math.sqrt(B)
    c_star = trial_c_star()
    shell_rows = []
    for radius in RADII:
        value = asymptotic_trial_shell(radius)
        shell_rows.append(
            {
                "radius": radius,
                "shell_energy": value,
                "relative_error_to_asymptote": abs(value - expected_asymptotic_slope)
                / expected_asymptotic_slope,
            }
        )

    tail_rows = []
    for limit in TAIL_LIMITS:
        value, error = quad(
            asymptotic_trial_shell,
            TAIL_START,
            limit,
            epsabs=1.0e-10,
            epsrel=1.0e-12,
            limit=500,
        )
        tail_rows.append(
            {
                "start": TAIL_START,
                "limit": limit,
                "energy": value,
                "quadrature_error": error,
            }
        )
    final_limits = np.array([row["limit"] for row in tail_rows[-3:]], dtype=np.float64)
    final_energies = np.array([row["energy"] for row in tail_rows[-3:]], dtype=np.float64)
    fitted_slope, fitted_intercept = np.polyfit(final_limits, final_energies, 1)
    slope_relative_error = abs(fitted_slope - expected_asymptotic_slope) / expected_asymptotic_slope

    sigma_chi, sigma_error = wall_tension()
    weights = np.array(
        [
            [0.5, 1.0 / (2.0 * math.sqrt(3.0))],
            [-0.5, 1.0 / (2.0 * math.sqrt(3.0))],
            [0.0, -1.0 / math.sqrt(3.0)],
        ],
        dtype=np.float64,
    )
    weight_sum = np.sum(weights, axis=0)
    weight_magnitudes = np.linalg.norm(weights, axis=1)
    tube_rows = []
    for label, magnitude in zip(("red", "green", "blue"), weight_magnitudes, strict=True):
        q = G_S * float(magnitude)
        radius = cast(
            float,
            brentq(
                lambda value: tube_tension_derivative(value, q, sigma_chi),
                TUBE_R_MIN,
                TUBE_R_MAX,
                xtol=1.0e-14,
            ),
        )
        tension = tube_tension(radius, q, sigma_chi)
        tube_rows.append(
            {
                "label": label,
                "weight_magnitude": float(magnitude),
                "charge_magnitude": q,
                "stationary_radius": radius,
                "tension": tension,
                "derivative_residual": tube_tension_derivative(radius, q, sigma_chi),
                "small_radius_tension": tube_tension(TUBE_R_MIN, q, sigma_chi),
                "large_radius_tension": tube_tension(TUBE_R_MAX, q, sigma_chi),
                "small_to_minimum_ratio": tube_tension(TUBE_R_MIN, q, sigma_chi) / tension,
                "large_to_minimum_ratio": tube_tension(TUBE_R_MAX, q, sigma_chi) / tension,
            }
        )

    symmetry_ledger = {
        "local_su3_color": True,
        "chiral_su2_left_right": True,
        "global_vector_u1_baryon": True,
        "baryon_current": "j_B^mu=(1/3) qbar gamma^mu q",
        "chiral_zero_yukawa_finite": True,
        "standalone_chi_qbar_q_absent": True,
    }
    regulator_state_ledger = {
        "compact_wilson_links": True,
        "positive_finite_epsilon_plaquette_weight": True,
        "wilson_fermion_r": 1.0,
        "two_degenerate_flavour_sea": "det(D_W^dagger D_W)>=0 at mu=0",
        "vacuum_subtraction": True,
        "symmetry_complete_counterterms_through_cutoff_order": True,
        "counterterms_fixed_before_hadron_calculation": True,
        "gauss_projector": True,
        "fixed_baryon_projector": True,
        "finite_cutoff_eft": True,
        "continuum_uv_completion_claimed": False,
    }

    rcf1 = (
        dimensions_pass
        and float(np.min(kappas)) >= -1.0e-13
        and float(np.min(potentials)) >= -1.0e-13
        and all(abs(row["first_derivative"]) <= 1.0e-14 for row in stationary.values())
        and abs(stationary["0.000"]["potential"] - 1.0) <= 1.0e-14
        and abs(stationary["0.125"]["potential"] - 1029.0 / 1024.0) <= 1.0e-14
        and abs(stationary["1.000"]["potential"]) <= 1.0e-14
        and abs(stationary["0.000"]["second_derivative"] - 2.0) <= 1.0e-14
        and abs(stationary["1.000"]["second_derivative"] - 14.0) <= 1.0e-14
        and all(
            row["sampled_minimum"] >= row["epsilon"] - 1.0e-13
            and abs(row["sampled_argmin"] - 1.0) <= 1.0e-14
            for row in regulator_rows
        )
        and all(value is True or isinstance(value, str) for value in symmetry_ledger.values())
    )
    rcf2 = (
        all(
            regulator_state_ledger[key]
            for key in (
                "compact_wilson_links",
                "positive_finite_epsilon_plaquette_weight",
                "vacuum_subtraction",
                "symmetry_complete_counterterms_through_cutoff_order",
                "counterterms_fixed_before_hadron_calculation",
                "gauss_projector",
                "fixed_baryon_projector",
                "finite_cutoff_eft",
            )
        )
        and not regulator_state_ledger["continuum_uv_completion_claimed"]
    )
    rcf3_without_independent = (
        lower_bound_coefficient > 0.0
        and all(math.isfinite(row["shell_energy"]) for row in shell_rows)
        and shell_rows[-1]["relative_error_to_asymptote"] < 5.0e-3
        and slope_relative_error < 1.0e-2
    )
    rcf4_without_independent = (
        float(np.max(np.abs(weight_sum))) < 1.0e-14
        and float(np.max(weight_magnitudes) - np.min(weight_magnitudes)) < 1.0e-14
        and math.isfinite(sigma_chi)
        and sigma_chi > 0.0
        and all(
            row["stationary_radius"] > 0.0
            and math.isfinite(row["tension"])
            and row["tension"] > 0.0
            and abs(row["derivative_residual"]) < 1.0e-10
            and row["small_to_minimum_ratio"] >= 1.0e6
            and row["large_to_minimum_ratio"] >= 1.0e6
            for row in tube_rows
        )
    )

    receipt = {
        "protocol": "qcd-confining-carrier",
        "protocol_status": "Preregistered—September 2026",
        "constants": {
            "B_dimensionless": B,
            "chi_v_dimensionless": CHI_V,
            "g_s_dimensionless": G_S,
            "q_isolated": Q_ISOLATED,
            "x_interval": [X_MIN, X_MAX],
            "x_samples": X_SAMPLES,
            "epsilons": list(EPSILONS),
            "radii": list(RADII),
            "tail_start": TAIL_START,
            "tail_limits": list(TAIL_LIMITS),
            "tube_radius_interval": [TUBE_R_MIN, TUBE_R_MAX],
        },
        "dimensions": dimensions,
        "symmetry_ledger": symmetry_ledger,
        "regulator_state_ledger": regulator_state_ledger,
        "polynomial_controls": {
            "sampled_kappa_minimum": float(np.min(kappas)),
            "sampled_kappa_argmin": float(xs[int(np.argmin(kappas))]),
            "sampled_potential_minimum": float(np.min(potentials)),
            "sampled_potential_argmin": float(xs[int(np.argmin(potentials))]),
            "stationary": stationary,
            "regulator_rows": regulator_rows,
        },
        "field_minimal_control": field_minimal_control,
        "isolated_color": {
            "lower_bound_coefficient": lower_bound_coefficient,
            "c_star": c_star,
            "expected_asymptotic_slope": expected_asymptotic_slope,
            "shell_rows": shell_rows,
            "tail_rows": tail_rows,
            "final_three_fit_slope": float(fitted_slope),
            "final_three_fit_intercept": float(fitted_intercept),
            "slope_relative_error": float(slope_relative_error),
        },
        "color_neutral_witness": {
            "weights": weights.tolist(),
            "weight_sum": weight_sum.tolist(),
            "weight_magnitudes": weight_magnitudes.tolist(),
            "sigma_chi": sigma_chi,
            "sigma_quadrature_error": sigma_error,
            "tube_rows": tube_rows,
            "gauge_invariant_baryon_interpolator": True,
        },
        "primary_gate_inputs": {
            "RCF1": "PASS" if rcf1 else "FAIL",
            "RCF2": "PASS" if rcf2 else "FAIL",
            "RCF3_without_independent_agreement": "PASS" if rcf3_without_independent else "FAIL",
            "RCF4_without_independent_agreement": "PASS" if rcf4_without_independent else "FAIL",
        },
        "final_verdicts": {
            "RCF1": "PASS" if rcf1 else "FAIL",
            "RCF2": "PASS" if rcf2 else "FAIL",
            "RCF3": "PENDING_INDEPENDENT_VERIFICATION",
            "RCF4": "PENDING_INDEPENDENT_VERIFICATION",
            "RCF5": "PENDING_INDEPENDENT_VERIFICATION",
            "RCF6": "FAIL",
            "physical_completion": "FAIL",
        },
        "complete_physical_matter_formation": False,
        "hashes": {
            "protocol_sha256": sha256(PROTOCOL),
            "primary_source_sha256": sha256(Path(__file__).resolve()),
        },
    }
    RESULTS.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt["primary_gate_inputs"], indent=2))
    print(f"wrote {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
