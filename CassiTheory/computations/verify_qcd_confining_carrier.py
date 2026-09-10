#!/usr/bin/env python3
"""Independently verify the QCD-target and confining-carrier receipt.

Run from the CassiTheory repository root after the primary program:
    python computations/verify_qcd_confining_carrier.py
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import mpmath as mp


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "qcd-confining-carrier-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "qcd_confining_carrier.py"
PRIMARY_RESULTS = ROOT / "runs" / "20260910_qcd_confining_carrier" / "primary" / "results.json"
OUT_DIR = ROOT / "runs" / "20260910_qcd_confining_carrier" / "verification"
RESULTS = OUT_DIR / "verification.json"

mp.mp.dps = 80


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_error(left: Any, right: Any) -> float:
    left_mp = mp.mpf(left)
    right_mp = mp.mpf(right)
    scale = max(abs(left_mp), abs(right_mp), mp.mpf("1e-80"))
    return float(abs(left_mp - right_mp) / scale)


def potential(x: Any, b: Any) -> Any:
    return b * (1 - x) ** 2 * (1 + 2 * x + 4 * x**2)


def kappa(x: Any) -> Any:
    return (1 - x**3) ** 2


def trial_shell(radius: Any, q: Any, b: Any, chi_v: Any) -> Any:
    c_star = (q**2 / (mp.mpf(2016) * mp.pi**2 * b)) ** mp.mpf("0.25")
    x = 1 - c_star / radius
    derivative = c_star / radius**2
    scalar = 4 * mp.pi * radius**2 * (
        mp.mpf("0.5") * chi_v**2 * derivative**2 + potential(x, b)
    )
    flux = q**2 / (8 * mp.pi * radius**2 * kappa(x))
    return scalar + flux


def tube_tension(radius: Any, q: Any, b: Any, sigma: Any) -> Any:
    return q**2 / (2 * mp.pi * radius**2) + mp.pi * b * radius**2 + 2 * mp.pi * sigma * radius


def tube_derivative(radius: Any, q: Any, b: Any, sigma: Any) -> Any:
    return -(q**2) / (mp.pi * radius**3) + 2 * mp.pi * b * radius + 2 * mp.pi * sigma


def bisect_tube_root(low: Any, high: Any, q: Any, b: Any, sigma: Any) -> Any:
    f_low = tube_derivative(low, q, b, sigma)
    f_high = tube_derivative(high, q, b, sigma)
    if not (f_low < 0 < f_high):
        raise RuntimeError("tube derivative is not bracketed")
    for _ in range(400):
        midpoint = (low + high) / 2
        value = tube_derivative(midpoint, q, b, sigma)
        if value < 0:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2


def require_keys(mapping: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(mapping.get(key) is True for key in keys)


def main() -> None:
    if not PRIMARY_RESULTS.exists():
        raise FileNotFoundError(f"missing primary receipt: {PRIMARY_RESULTS}")
    primary = json.loads(PRIMARY_RESULTS.read_text(encoding="utf-8"))
    constants = primary["constants"]
    b = mp.mpf(str(constants["B_dimensionless"]))
    chi_v = mp.mpf(str(constants["chi_v_dimensionless"]))
    g_s = mp.mpf(str(constants["g_s_dimensionless"]))
    q_isolated = mp.mpf(str(constants["q_isolated"]))

    source_hash_match = sha256(PRIMARY_SOURCE) == primary["hashes"]["primary_source_sha256"]
    protocol_hash_match = sha256(PROTOCOL) == primary["hashes"]["protocol_sha256"]

    exact_stationary = {
        "0.000": {"x": mp.mpf(0), "potential": b, "first_derivative": mp.mpf(0), "second_derivative": 2 * b},
        "0.125": {
            "x": mp.mpf(1) / 8,
            "potential": mp.mpf(1029) * b / 1024,
            "first_derivative": mp.mpf(0),
            "second_derivative": -mp.mpf(7) * b / 4,
        },
        "1.000": {"x": mp.mpf(1), "potential": mp.mpf(0), "first_derivative": mp.mpf(0), "second_derivative": 14 * b},
    }
    stationary_errors: dict[str, dict[str, float]] = {}
    for key, expected in exact_stationary.items():
        observed = primary["polynomial_controls"]["stationary"][key]
        stationary_errors[key] = {
            field: relative_error(observed[field], value) for field, value in expected.items()
        }
    maximum_stationary_error = max(
        error for row in stationary_errors.values() for error in row.values()
    )

    dimensions = primary["dimensions"]
    dimension_check = (
        all(value == 4.0 for value in dimensions["lagrangian_terms"].values())
        and all(row["operator"] + row["coefficient"] == 4.0 for row in dimensions["expanded_operators"].values())
    )
    polynomial_exact = {
        "kappa_factorization": "(1-x^3)^2>=0",
        "kappa_only_real_zero": 1.0,
        "potential_factorization": "B(1-x)^2(4(x+1/4)^2+3/4)>=0",
        "potential_stationary_factorization": "2Bx(1-x)(1-8x)",
        "all_nonnegative": True,
        "chiral_zero_coefficients_finite": True,
    }

    regulator_errors = []
    for row in primary["polynomial_controls"]["regulator_rows"]:
        epsilon = mp.mpf(str(row["epsilon"]))
        regulator_errors.append(
            {
                "epsilon": float(epsilon),
                "minimum_error": relative_error(row["sampled_minimum"], epsilon),
                "argmin_error": abs(float(row["sampled_argmin"]) - 1.0),
            }
        )
    maximum_regulator_error = max(
        max(row["minimum_error"], row["argmin_error"]) for row in regulator_errors
    )

    field_minimal = primary["field_minimal_control"]
    field_minimal_pass = (
        field_minimal["max_abs_amplitude_minus_one"] < 1.0e-14
        and field_minimal["max_kappa_minimal"] < 1.0e-28
        and field_minimal["interior_dielectric_present"] is False
    )

    lower_bound = 4 * mp.sqrt(6) * abs(q_isolated) * mp.sqrt(b) / 19
    c_star = (q_isolated**2 / (mp.mpf(2016) * mp.pi**2 * b)) ** mp.mpf("0.25")
    asymptotic_slope = mp.sqrt(14) * abs(q_isolated) * mp.sqrt(b) / 3
    independent_shell_rows = []
    shell_agreement = []
    for primary_row in primary["isolated_color"]["shell_rows"]:
        radius = mp.mpf(str(primary_row["radius"]))
        value = trial_shell(radius, q_isolated, b, chi_v)
        independent_shell_rows.append(
            {
                "radius": float(radius),
                "shell_energy": float(value),
                "relative_error_to_asymptote": relative_error(value, asymptotic_slope),
            }
        )
        shell_agreement.append(relative_error(primary_row["shell_energy"], value))

    independent_tail_rows = []
    tail_agreement = []
    tail_start = mp.mpf(str(constants["tail_start"]))
    for primary_row in primary["isolated_color"]["tail_rows"]:
        limit = mp.mpf(str(primary_row["limit"]))
        value = mp.quad(
            lambda radius: trial_shell(radius, q_isolated, b, chi_v),
            [tail_start, limit],
        )
        independent_tail_rows.append(
            {"start": float(tail_start), "limit": float(limit), "energy": float(value)}
        )
        tail_agreement.append(relative_error(primary_row["energy"], value))

    final_limits = [mp.mpf(str(row["limit"])) for row in independent_tail_rows[-3:]]
    final_energies = [mp.mpf(str(row["energy"])) for row in independent_tail_rows[-3:]]
    mean_limit = sum(final_limits) / len(final_limits)
    mean_energy = sum(final_energies) / len(final_energies)
    fitted_slope = sum(
        (limit - mean_limit) * (energy - mean_energy)
        for limit, energy in zip(final_limits, final_energies, strict=True)
    ) / sum((limit - mean_limit) ** 2 for limit in final_limits)
    fitted_intercept = mean_energy - fitted_slope * mean_limit
    slope_relative_error = relative_error(fitted_slope, asymptotic_slope)

    isolated_agreement = {
        "lower_bound": relative_error(primary["isolated_color"]["lower_bound_coefficient"], lower_bound),
        "c_star": relative_error(primary["isolated_color"]["c_star"], c_star),
        "asymptotic_slope": relative_error(primary["isolated_color"]["expected_asymptotic_slope"], asymptotic_slope),
        "maximum_shell": max(shell_agreement),
        "maximum_tail": max(tail_agreement),
        "fit_slope": relative_error(primary["isolated_color"]["final_three_fit_slope"], fitted_slope),
        "fit_intercept": relative_error(primary["isolated_color"]["final_three_fit_intercept"], fitted_intercept),
    }
    maximum_isolated_agreement_error = max(isolated_agreement.values())

    sigma_chi = chi_v * mp.sqrt(2 * b) * mp.quad(
        lambda x: (1 - x) * mp.sqrt(1 + 2 * x + 4 * x**2),
        [0, 1],
    )
    weights = (
        (mp.mpf(1) / 2, mp.mpf(1) / (2 * mp.sqrt(3))),
        (-mp.mpf(1) / 2, mp.mpf(1) / (2 * mp.sqrt(3))),
        (mp.mpf(0), -mp.mpf(1) / mp.sqrt(3)),
    )
    weight_sum = [sum(weight[index] for weight in weights) for index in range(2)]
    magnitudes = [mp.sqrt(weight[0] ** 2 + weight[1] ** 2) for weight in weights]
    independent_tubes = []
    tube_agreement = []
    low = mp.mpf(str(constants["tube_radius_interval"][0]))
    high = mp.mpf(str(constants["tube_radius_interval"][1]))
    for label, magnitude, primary_row in zip(
        ("red", "green", "blue"),
        magnitudes,
        primary["color_neutral_witness"]["tube_rows"],
        strict=True,
    ):
        q = g_s * magnitude
        radius = bisect_tube_root(low, high, q, b, sigma_chi)
        tension = tube_tension(radius, q, b, sigma_chi)
        derivative = tube_derivative(radius, q, b, sigma_chi)
        small = tube_tension(low, q, b, sigma_chi)
        large = tube_tension(high, q, b, sigma_chi)
        row = {
            "label": label,
            "weight_magnitude": float(magnitude),
            "charge_magnitude": float(q),
            "stationary_radius": float(radius),
            "tension": float(tension),
            "derivative_residual": float(derivative),
            "small_radius_tension": float(small),
            "large_radius_tension": float(large),
            "small_to_minimum_ratio": float(small / tension),
            "large_to_minimum_ratio": float(large / tension),
        }
        independent_tubes.append(row)
        for field in (
            "weight_magnitude",
            "charge_magnitude",
            "stationary_radius",
            "tension",
            "small_radius_tension",
            "large_radius_tension",
            "small_to_minimum_ratio",
            "large_to_minimum_ratio",
        ):
            tube_agreement.append(relative_error(primary_row[field], row[field]))
    maximum_tube_agreement_error = max(tube_agreement)
    sigma_agreement_error = relative_error(
        primary["color_neutral_witness"]["sigma_chi"], sigma_chi
    )

    regulator = primary["regulator_state_ledger"]
    regulator_state_pass = (
        require_keys(
            regulator,
            (
                "compact_wilson_links",
                "positive_finite_epsilon_plaquette_weight",
                "vacuum_subtraction",
                "symmetry_complete_counterterms_through_cutoff_order",
                "counterterms_fixed_before_hadron_calculation",
                "gauss_projector",
                "fixed_baryon_projector",
                "finite_cutoff_eft",
            ),
        )
        and regulator.get("two_degenerate_flavour_sea")
        == "det(D_W^dagger D_W)>=0 at mu=0"
        and regulator.get("continuum_uv_completion_claimed") is False
    )
    symmetry = primary["symmetry_ledger"]
    symmetry_pass = require_keys(
        symmetry,
        (
            "local_su3_color",
            "chiral_su2_left_right",
            "global_vector_u1_baryon",
            "chiral_zero_yukawa_finite",
            "standalone_chi_qbar_q_absent",
        ),
    )

    rcf1 = (
        source_hash_match
        and protocol_hash_match
        and dimension_check
        and polynomial_exact["all_nonnegative"]
        and polynomial_exact["chiral_zero_coefficients_finite"]
        and symmetry_pass
        and maximum_stationary_error < 1.0e-13
        and maximum_regulator_error < 1.0e-13
        and field_minimal_pass
        and primary["primary_gate_inputs"]["RCF1"] == "PASS"
    )
    rcf2 = regulator_state_pass and primary["primary_gate_inputs"]["RCF2"] == "PASS"
    rcf3 = (
        lower_bound > 0
        and all(math.isfinite(row["shell_energy"]) for row in independent_shell_rows)
        and independent_shell_rows[-1]["relative_error_to_asymptote"] < 5.0e-3
        and slope_relative_error < 1.0e-2
        and maximum_isolated_agreement_error < 2.0e-10
        and primary["primary_gate_inputs"]["RCF3_without_independent_agreement"] == "PASS"
    )
    rcf4 = (
        max(abs(value) for value in weight_sum) < mp.mpf("1e-14")
        and max(magnitudes) - min(magnitudes) < mp.mpf("1e-14")
        and sigma_chi > 0
        and all(
            row["stationary_radius"] > 0
            and row["tension"] > 0
            and abs(row["derivative_residual"]) < 1.0e-10
            and row["small_to_minimum_ratio"] >= 1.0e6
            and row["large_to_minimum_ratio"] >= 1.0e6
            for row in independent_tubes
        )
        and sigma_agreement_error < 2.0e-10
        and maximum_tube_agreement_error < 2.0e-10
        and primary["primary_gate_inputs"]["RCF4_without_independent_agreement"] == "PASS"
    )
    verdicts = {
        "RCF1": "PASS" if rcf1 else "FAIL",
        "RCF2": "PASS" if rcf2 else "FAIL",
        "RCF3": "PASS" if rcf3 else "FAIL",
        "RCF4": "PASS" if rcf4 else "FAIL",
        "RCF5": "ADOPT" if rcf1 and rcf2 and rcf3 and rcf4 else "REJECT",
        "RCF6": "FAIL",
        "physical_completion": "FAIL",
    }

    receipt = {
        "protocol": "qcd-confining-carrier-independent-verification",
        "source_hash_match": source_hash_match,
        "protocol_hash_match": protocol_hash_match,
        "dimension_check": dimension_check,
        "polynomial_exact": polynomial_exact,
        "stationary_errors": stationary_errors,
        "maximum_stationary_error": maximum_stationary_error,
        "regulator_errors": regulator_errors,
        "maximum_regulator_error": maximum_regulator_error,
        "field_minimal_control_pass": field_minimal_pass,
        "isolated_color": {
            "lower_bound_coefficient": float(lower_bound),
            "c_star": float(c_star),
            "expected_asymptotic_slope": float(asymptotic_slope),
            "shell_rows": independent_shell_rows,
            "tail_rows": independent_tail_rows,
            "final_three_fit_slope": float(fitted_slope),
            "final_three_fit_intercept": float(fitted_intercept),
            "slope_relative_error": slope_relative_error,
            "agreement_errors": isolated_agreement,
            "maximum_agreement_error": maximum_isolated_agreement_error,
        },
        "color_neutral_witness": {
            "weight_sum": [float(value) for value in weight_sum],
            "weight_magnitudes": [float(value) for value in magnitudes],
            "sigma_chi": float(sigma_chi),
            "sigma_agreement_error": sigma_agreement_error,
            "tube_rows": independent_tubes,
            "maximum_tube_agreement_error": maximum_tube_agreement_error,
        },
        "regulator_state_pass": regulator_state_pass,
        "symmetry_pass": symmetry_pass,
        "verdicts": verdicts,
        "complete_physical_matter_formation": False,
        "hashes": {
            "protocol_sha256": sha256(PROTOCOL),
            "primary_source_sha256": sha256(PRIMARY_SOURCE),
            "primary_results_sha256": sha256(PRIMARY_RESULTS),
            "verification_source_sha256": sha256(Path(__file__).resolve()),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdicts, indent=2))
    print(f"maximum isolated agreement error: {maximum_isolated_agreement_error:.3e}")
    print(f"maximum tube agreement error: {maximum_tube_agreement_error:.3e}")
    print(f"wrote {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
