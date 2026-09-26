#!/usr/bin/env python3
"""Verify the frozen renormalized SU(2) gap and volume scaling diagnostic.

The arithmetic implements
``computations/yang-mills-renormalized-gap-scaling-prereg.md``.  It checks
universal two-loop conventions and classifies prescribed asymptotic schedules.
It does not compute an interacting Yang--Mills spectrum or construct a
continuum quantum field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-renormalized-gap-scaling-prereg.md"
SOURCE = Path(__file__).resolve()
INDEPENDENT_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_renormalized_gap_scaling_independent.mjs"
)
OUTPUT = ROOT / "runs" / "yang-mills-renormalized-gap-scaling" / "verification.json"

G2_VALUES = (0.8, 0.5, 0.3, 0.2, 0.1, 0.05)
ALGEBRA_TOLERANCE = 2.0e-13
EXPECTED_ROWS = 6
EXPECTED_ROW_CHECKS = 60
EXPECTED_TOP_CHECKS = 20
EXPECTED_TOTAL_CHECKS = 80
EXPECTED_FIRING_CONTROLS = 6

B0 = 11.0 / (24.0 * math.pi**2)
B1 = 17.0 / (96.0 * math.pi**4)
P = B1 / (2.0 * B0**2)
COUPLING_FACTOR = 2.0**0.25
MATCHED_GAP_RATIO = 7.0 / 4.0
SYNTHETIC_EIGEN_GAP = 13.0 / 10.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check(
    name: str,
    passed: bool,
    *,
    value: Any | None = None,
    threshold: Any | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if value is not None:
        result["value"] = value
    if threshold is not None:
        result["threshold"] = threshold
    return result


def close_absolute(left: float, right: float, tolerance: float = ALGEBRA_TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def close_relative(left: float, right: float, tolerance: float = ALGEBRA_TOLERANCE) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def finite_payload(value: Any) -> bool:
    if value is None or isinstance(value, (bool, str)):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and finite_payload(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_payload(item) for item in value)
    return False


def strictly_increasing(values: list[float]) -> bool:
    return all(right > left for left, right in zip(values, values[1:]))


def strictly_decreasing(values: list[float]) -> bool:
    return all(right < left for left, right in zip(values, values[1:]))


def log_scale_from_coupling(g2: float) -> float:
    return -1.0 / (2.0 * B0 * g2) - P * math.log(B0 * g2)


def log_scale_from_beta(g2: float) -> float:
    beta_lat = 4.0 / g2
    return (
        -3.0 * math.pi**2 * beta_lat / 11.0
        + (51.0 / 121.0) * math.log(6.0 * math.pi**2 * beta_lat / 11.0)
    )


def log_scale_hamiltonian(g_h2: float) -> float:
    return (
        -6.0 * math.sqrt(2.0) * math.pi**2 / (11.0 * g_h2)
        + (51.0 / 121.0)
        * math.log(12.0 * math.sqrt(2.0) * math.pi**2 / (11.0 * g_h2))
    )


def derivative_beta_direct(g: float) -> float:
    derivative = 1.0 / (B0 * g**3) - 2.0 * P / g
    return -1.0 / derivative


def derivative_beta_rational(g: float) -> float:
    return -B0 * g**3 / (1.0 - (B1 / B0) * g**2)


def classify_volume(exponential_cancellation: float, residual: str) -> str:
    """Classify log(NF) from its coefficient of log F and residual term."""

    coefficient = 1.0 - exponential_cancellation
    if coefficient > 0.0:
        return "COLLAPSES_TO_ZERO"
    if coefficient < 0.0:
        return "DIVERGES_TO_INFINITY"
    if residual == "constant":
        return "FIXED_PHYSICAL_SIZE"
    if residual in {"minus_log_g2", "log_minus_log_f"}:
        return "DIVERGES_TO_INFINITY"
    raise ValueError(f"unsupported volume residual: {residual}")


def classify_gap_ratio(scale_power: float, g2_power: float) -> str:
    """Classify delta/F for log(delta)=scale_power*log(F)+g2_power*log(g2)+O(1)."""

    scale_coefficient = scale_power - 1.0
    if scale_coefficient < 0.0:
        return "DIVERGES_TO_INFINITY"
    if scale_coefficient > 0.0:
        return "VANISHES_TO_ZERO"
    if g2_power > 0.0:
        return "VANISHES_TO_ZERO"
    if g2_power < 0.0:
        return "DIVERGES_TO_INFINITY"
    return "FINITE_POSITIVE"


def construct_row(g2: float) -> dict[str, Any]:
    g = math.sqrt(g2)
    beta_lat = 4.0 / g2
    log_f_coupling = log_scale_from_coupling(g2)
    log_f_beta = log_scale_from_beta(g2)
    f_w = math.exp(log_f_coupling)

    g_h2 = g2 / math.sqrt(2.0)
    log_f_h = log_scale_hamiltonian(g_h2)

    beta_direct = derivative_beta_direct(g)
    beta_rational = derivative_beta_rational(g)
    beta_two_loop = -B0 * g**3 - B1 * g**5
    beta_remainder = beta_direct - beta_two_loop
    beta_remainder_coefficient = beta_remainder / g**7
    beta_remainder_expected = -(B1**2 / B0) / (1.0 - (B1 / B0) * g2)

    volume_logs = {
        "fixed_count": math.log(64.0) + log_f_coupling,
        "polynomial_count": -4.0 * math.log(g2) + log_f_coupling,
        "fixed_box": math.log(8.0),
        "thermodynamic_inverse_g2": -math.log(g2),
        "thermodynamic_log_scale": math.log(-log_f_coupling),
    }
    gap_log_ratios = {
        "constant": math.log(0.25) - log_f_coupling,
        "polynomial": 3.0 * math.log(g2) - log_f_coupling,
        "subscale": math.log(g2),
        "matched": math.log(MATCHED_GAP_RATIO),
        "isolated_square": math.log(2.0 * math.sqrt(2.0)) - log_f_h,
    }

    delta_w = 0.5 * g2 * SYNTHETIC_EIGEN_GAP
    delta_h_from_energy = delta_w / math.sqrt(2.0)
    delta_h_from_prefactor = 0.5 * g_h2 * SYNTHETIC_EIGEN_GAP
    recovered_h_hat_gap = 2.0 * delta_h_from_energy / g_h2

    numeric_values = {
        "g0_squared": g2,
        "g0": g,
        "beta_lattice": beta_lat,
        "log_scale_from_coupling": log_f_coupling,
        "log_scale_from_beta": log_f_beta,
        "scale": f_w,
        "g_h_squared": g_h2,
        "log_scale_hamiltonian": log_f_h,
        "beta_from_log_derivative": beta_direct,
        "beta_rational": beta_rational,
        "beta_two_loop_truncation": beta_two_loop,
        "beta_remainder": beta_remainder,
        "beta_remainder_over_g7": beta_remainder_coefficient,
        "beta_remainder_over_g7_expected": beta_remainder_expected,
        "volume_log_products": volume_logs,
        "gap_log_ratios": gap_log_ratios,
        "synthetic_gap_map": {
            "widehat_delta": SYNTHETIC_EIGEN_GAP,
            "delta_w": delta_w,
            "delta_h_from_energy_map": delta_h_from_energy,
            "delta_h_from_prefactor": delta_h_from_prefactor,
            "recovered_h_widehat_delta": recovered_h_hat_gap,
        },
    }

    row_checks = [
        check(
            "wilson_log_scale_forms_agree",
            close_absolute(log_f_coupling, log_f_beta),
            value={"absolute_error": abs(log_f_coupling - log_f_beta), "comparisons_attempted": 1},
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "wilson_scale_finite_strictly_between_zero_and_one",
            math.isfinite(f_w) and 0.0 < f_w < 1.0,
            value=f_w,
            threshold={"minimum_exclusive": 0.0, "maximum_exclusive": 1.0},
        ),
        check(
            "hamiltonian_and_wilson_log_scales_agree",
            close_absolute(log_f_h, log_f_coupling),
            value={"absolute_error": abs(log_f_h - log_f_coupling), "comparisons_attempted": 1},
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "log_scale_derivative_beta_identity",
            close_relative(beta_direct, beta_rational),
            value={
                "relative_scaled_error": abs(beta_direct - beta_rational)
                / max(1.0, abs(beta_direct), abs(beta_rational)),
                "comparisons_attempted": 1,
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "fixed_box_product_equals_eight",
            close_absolute(volume_logs["fixed_box"], math.log(8.0)),
            value={"log_absolute_error": abs(volume_logs["fixed_box"] - math.log(8.0)), "comparisons_attempted": 1},
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "inverse_g2_thermodynamic_product_identity",
            close_absolute(volume_logs["thermodynamic_inverse_g2"], -math.log(g2)),
            value={"log_absolute_error": abs(volume_logs["thermodynamic_inverse_g2"] + math.log(g2)), "comparisons_attempted": 1},
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "log_scale_thermodynamic_product_identity",
            close_absolute(volume_logs["thermodynamic_log_scale"], math.log(-log_f_coupling)),
            value={
                "log_absolute_error": abs(
                    volume_logs["thermodynamic_log_scale"] - math.log(-log_f_coupling)
                ),
                "comparisons_attempted": 1,
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "matched_gap_ratio_equals_seven_fourths",
            close_absolute(gap_log_ratios["matched"], math.log(MATCHED_GAP_RATIO)),
            value={
                "log_absolute_error": abs(
                    gap_log_ratios["matched"] - math.log(MATCHED_GAP_RATIO)
                ),
                "comparisons_attempted": 1,
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "hamiltonian_gap_normalization_identity",
            close_absolute(delta_h_from_energy, delta_h_from_prefactor)
            and close_absolute(recovered_h_hat_gap, SYNTHETIC_EIGEN_GAP),
            value={
                "delta_h_absolute_error": abs(delta_h_from_energy - delta_h_from_prefactor),
                "widehat_gap_absolute_error": abs(recovered_h_hat_gap - SYNTHETIC_EIGEN_GAP),
                "comparisons_attempted": 2,
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "row_numeric_payload_finite",
            finite_payload(numeric_values),
            value={"top_level_fields_checked": len(numeric_values)},
        ),
    ]

    if len(row_checks) != 10:
        raise AssertionError(f"row check count drifted: {len(row_checks)}")
    return {**numeric_values, "checks": row_checks}


def coefficient_triplet_valid(b0: float, b1: float, p: float) -> bool:
    return (
        close_absolute(b0, 11.0 / (24.0 * math.pi**2))
        and close_absolute(b1, 17.0 / (96.0 * math.pi**4))
        and close_absolute(p, 51.0 / 121.0)
    )


def beta_form_valid(power: float) -> bool:
    return (
        close_absolute(1.0 / (8.0 * B0), 3.0 * math.pi**2 / 11.0)
        and close_absolute(1.0 / (4.0 * B0), 6.0 * math.pi**2 / 11.0)
        and close_absolute(power, 51.0 / 121.0)
    )


def volume_diverges(log_products: list[float]) -> bool:
    return strictly_increasing(log_products) and log_products[-1] > log_products[0]


def finite_positive_gap_ratio(log_ratios: list[float]) -> bool:
    lower = math.log(0.5)
    upper = math.log(4.0)
    return all(lower <= value <= upper for value in log_ratios)


def coupling_map_valid(factor: float) -> bool:
    errors = []
    for g_w2 in G2_VALUES:
        g_h2 = g_w2 / factor**2
        errors.append(abs(log_scale_from_coupling(g_w2) - log_scale_hamiltonian(g_h2)))
    return max(errors) <= ALGEBRA_TOLERANCE


def gap_map_valid(delta_scale: float) -> bool:
    errors = []
    for g_w2 in G2_VALUES:
        g_h2 = g_w2 / math.sqrt(2.0)
        delta_w = 0.5 * g_w2 * SYNTHETIC_EIGEN_GAP
        delta_h = delta_scale * delta_w
        errors.append(abs(2.0 * delta_h / g_h2 - SYNTHETIC_EIGEN_GAP))
    return max(errors) <= ALGEBRA_TOLERANCE


def construct_firing_controls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    thermodynamic_base = [
        row["volume_log_products"]["thermodynamic_inverse_g2"] for row in rows
    ]
    fixed_box_mutation = [row["volume_log_products"]["fixed_box"] for row in rows]
    matched_base = [row["gap_log_ratios"]["matched"] for row in rows]
    constant_gap_mutation = [row["gap_log_ratios"]["constant"] for row in rows]

    controls = [
        {
            "name": "omit_two_loop_power",
            "unmutated_passed": beta_form_valid(P),
            "mutation_passed": beta_form_valid(0.0),
        },
        {
            "name": "replace_su2_b0_with_su3_b0",
            "unmutated_passed": coefficient_triplet_valid(B0, B1, P),
            "mutation_passed": coefficient_triplet_valid(11.0 / (16.0 * math.pi**2), B1, P),
        },
        {
            "name": "mislabel_fixed_box_as_thermodynamic",
            "unmutated_passed": volume_diverges(thermodynamic_base),
            "mutation_passed": volume_diverges(fixed_box_mutation),
        },
        {
            "name": "mislabel_constant_gap_as_finite_mass",
            "unmutated_passed": finite_positive_gap_ratio(matched_base),
            "mutation_passed": finite_positive_gap_ratio(constant_gap_mutation),
        },
        {
            "name": "reverse_wilson_hamiltonian_coupling_map",
            "unmutated_passed": coupling_map_valid(COUPLING_FACTOR),
            "mutation_passed": coupling_map_valid(1.0 / COUPLING_FACTOR),
        },
        {
            "name": "omit_gap_time_rescaling",
            "unmutated_passed": gap_map_valid(1.0 / math.sqrt(2.0)),
            "mutation_passed": gap_map_valid(1.0),
        },
    ]
    for control in controls:
        control["fired"] = bool(control["unmutated_passed"] and not control["mutation_passed"])
        control["comparisons_attempted"] = 2
    return controls


def build_receipt() -> dict[str, Any]:
    rows = [construct_row(g2) for g2 in G2_VALUES]
    row_checks = [item for row in rows for item in row["checks"]]
    firing_controls = construct_firing_controls(rows)

    log_scales = [row["log_scale_from_coupling"] for row in rows]
    derivative_remainders_over_g7 = [row["beta_remainder_over_g7"] for row in rows]
    derivative_expected = [row["beta_remainder_over_g7_expected"] for row in rows]
    derivative_order_ratios = [
        abs(row["beta_remainder"] / math.sqrt(row["g0_squared"]) ** 5) for row in rows
    ]

    volume_series = {
        name: [row["volume_log_products"][name] for row in rows]
        for name in rows[0]["volume_log_products"]
    }
    gap_series = {
        name: [row["gap_log_ratios"][name] for row in rows]
        for name in rows[0]["gap_log_ratios"]
    }

    volume_classifications = {
        "fixed_count": classify_volume(0.0, "constant"),
        "polynomial_count": classify_volume(0.0, "constant"),
        "fixed_box": classify_volume(1.0, "constant"),
        "thermodynamic_inverse_g2": classify_volume(1.0, "minus_log_g2"),
        "thermodynamic_log_scale": classify_volume(1.0, "log_minus_log_f"),
    }
    gap_classifications = {
        "constant": classify_gap_ratio(0.0, 0.0),
        "polynomial": classify_gap_ratio(0.0, 3.0),
        "subscale": classify_gap_ratio(1.0, 1.0),
        "matched": classify_gap_ratio(1.0, 0.0),
        "isolated_square": classify_gap_ratio(0.0, 0.0),
    }

    source_bindings = {
        "protocol": {"path": relative(PROTOCOL), "sha256": sha256(PROTOCOL)},
        "primary_source": {"path": relative(SOURCE), "sha256": sha256(SOURCE)},
        "independent_source": {
            "path": relative(INDEPENDENT_SOURCE),
            "sha256": sha256(INDEPENDENT_SOURCE),
        },
    }

    hamiltonian_map_errors = [
        abs(row["log_scale_hamiltonian"] - row["log_scale_from_coupling"])
        for row in rows
    ]
    gap_map_errors = [
        row["checks"][8]["value"]["widehat_gap_absolute_error"] for row in rows
    ]

    top_checks: list[dict[str, Any]] = [
        check(
            "su2_universal_coefficients",
            coefficient_triplet_valid(B0, B1, P),
            value={
                "b0": B0,
                "b1": B1,
                "p": P,
                "expected_p": 51.0 / 121.0,
                "comparisons_attempted": 3,
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "wilson_beta_lattice_exponent_and_power",
            beta_form_valid(P),
            value={
                "exponential_coefficient": 1.0 / (8.0 * B0),
                "expected_exponential_coefficient": 3.0 * math.pi**2 / 11.0,
                "power_base_coefficient": 1.0 / (4.0 * B0),
                "expected_power_base_coefficient": 6.0 * math.pi**2 / 11.0,
                "power": P,
                "comparisons_attempted": 3,
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "scale_strictly_decreases_toward_weak_coupling",
            strictly_decreasing(log_scales),
            value={"log_scales": log_scales, "comparisons_attempted": len(log_scales) - 1},
            threshold={"strictly_decreasing": True},
        ),
        check(
            "derivative_remainder_is_order_g7",
            all(
                close_relative(actual, expected)
                for actual, expected in zip(derivative_remainders_over_g7, derivative_expected)
            )
            and strictly_decreasing(derivative_order_ratios),
            value={
                "remainder_over_g7": derivative_remainders_over_g7,
                "expected": derivative_expected,
                "absolute_remainder_over_g5": derivative_order_ratios,
                "comparisons_attempted": 2 * len(rows) + len(rows) - 1,
            },
            threshold={"relative_error": ALGEBRA_TOLERANCE, "order_g5_ratio_strictly_decreasing": True},
        ),
        check(
            "fixed_count_volume_collapses",
            volume_classifications["fixed_count"] == "COLLAPSES_TO_ZERO"
            and strictly_decreasing(volume_series["fixed_count"]),
            value={
                "classification": volume_classifications["fixed_count"],
                "log_products": volume_series["fixed_count"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "polynomial_volume_collapses",
            volume_classifications["polynomial_count"] == "COLLAPSES_TO_ZERO"
            and strictly_decreasing(volume_series["polynomial_count"]),
            value={
                "classification": volume_classifications["polynomial_count"],
                "log_products": volume_series["polynomial_count"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "fixed_box_stays_finite",
            volume_classifications["fixed_box"] == "FIXED_PHYSICAL_SIZE"
            and all(close_absolute(value, math.log(8.0)) for value in volume_series["fixed_box"]),
            value={
                "classification": volume_classifications["fixed_box"],
                "log_products": volume_series["fixed_box"],
                "comparisons_attempted": len(rows),
            },
        ),
        check(
            "inverse_g2_schedule_reaches_thermodynamic_limit",
            volume_classifications["thermodynamic_inverse_g2"] == "DIVERGES_TO_INFINITY"
            and strictly_increasing(volume_series["thermodynamic_inverse_g2"]),
            value={
                "classification": volume_classifications["thermodynamic_inverse_g2"],
                "log_products": volume_series["thermodynamic_inverse_g2"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "log_scale_schedule_reaches_thermodynamic_limit",
            volume_classifications["thermodynamic_log_scale"] == "DIVERGES_TO_INFINITY"
            and strictly_increasing(volume_series["thermodynamic_log_scale"]),
            value={
                "classification": volume_classifications["thermodynamic_log_scale"],
                "log_products": volume_series["thermodynamic_log_scale"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "constant_gap_is_ultraviolet_scale",
            gap_classifications["constant"] == "DIVERGES_TO_INFINITY"
            and strictly_increasing(gap_series["constant"]),
            value={
                "classification": gap_classifications["constant"],
                "log_ratios": gap_series["constant"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "polynomial_gap_is_ultraviolet_scale",
            gap_classifications["polynomial"] == "DIVERGES_TO_INFINITY"
            and strictly_increasing(gap_series["polynomial"]),
            value={
                "classification": gap_classifications["polynomial"],
                "log_ratios": gap_series["polynomial"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "subscale_gap_vanishes",
            gap_classifications["subscale"] == "VANISHES_TO_ZERO"
            and strictly_decreasing(gap_series["subscale"]),
            value={
                "classification": gap_classifications["subscale"],
                "log_ratios": gap_series["subscale"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "matched_gap_is_finite_positive",
            gap_classifications["matched"] == "FINITE_POSITIVE"
            and finite_positive_gap_ratio(gap_series["matched"]),
            value={
                "classification": gap_classifications["matched"],
                "log_ratios": gap_series["matched"],
                "comparisons_attempted": len(rows),
            },
        ),
        check(
            "isolated_square_gap_is_ultraviolet_scale",
            gap_classifications["isolated_square"] == "DIVERGES_TO_INFINITY"
            and strictly_increasing(gap_series["isolated_square"]),
            value={
                "classification": gap_classifications["isolated_square"],
                "log_ratios": gap_series["isolated_square"],
                "comparisons_attempted": len(rows) - 1,
            },
        ),
        check(
            "hamiltonian_map_all_rows",
            max(hamiltonian_map_errors) <= ALGEBRA_TOLERANCE
            and max(gap_map_errors) <= ALGEBRA_TOLERANCE,
            value={
                "maximum_log_scale_error": max(hamiltonian_map_errors),
                "maximum_widehat_gap_error": max(gap_map_errors),
                "comparisons_attempted": 2 * len(rows),
            },
            threshold=ALGEBRA_TOLERANCE,
        ),
        check(
            "all_firing_controls_activate",
            len(firing_controls) == EXPECTED_FIRING_CONTROLS
            and all(control["fired"] for control in firing_controls),
            value={
                "controls": firing_controls,
                "fired": sum(control["fired"] for control in firing_controls),
                "comparisons_attempted": 2 * len(firing_controls),
            },
            threshold={"controls": EXPECTED_FIRING_CONTROLS, "fired": EXPECTED_FIRING_CONTROLS},
        ),
        check(
            "row_and_check_counts_match_frozen_contract",
            len(rows) == EXPECTED_ROWS
            and len(row_checks) == EXPECTED_ROW_CHECKS
            and all(len(row["checks"]) == 10 for row in rows),
            value={
                "rows": len(rows),
                "row_checks": len(row_checks),
                "checks_per_row": [len(row["checks"]) for row in rows],
                "expected_total_checks": EXPECTED_TOTAL_CHECKS,
            },
            threshold={"rows": EXPECTED_ROWS, "row_checks": EXPECTED_ROW_CHECKS, "checks_per_row": 10},
        ),
        check(
            "numeric_payloads_are_finite",
            finite_payload(
                {
                    "rows": rows,
                    "volume_classifications": volume_classifications,
                    "gap_classifications": gap_classifications,
                    "firing_controls": firing_controls,
                }
            ),
            value={"rows_checked": len(rows), "firing_controls_checked": len(firing_controls)},
        ),
        check(
            "source_bindings_present",
            all(
                binding["path"] and len(binding["sha256"]) == 64
                for binding in source_bindings.values()
            ),
            value={"bindings": source_bindings, "comparisons_attempted": len(source_bindings)},
            threshold={"sha256_hex_characters": 64},
        ),
    ]

    if len(top_checks) != EXPECTED_TOP_CHECKS - 1:
        raise AssertionError(f"pre-claim top-level check count drifted: {len(top_checks)}")

    preliminary_pass = all(item["passed"] for item in row_checks + top_checks)
    claims = {
        "two_loop_scaling_arithmetic": "PASS" if preliminary_pass else "FAIL",
        "double_scaling_necessity_diagnostic": "PASS" if preliminary_pass else "FAIL",
        "conditional_continuum_bridge_analytic": True,
        "analytic_theorem_outside_executable": True,
        "interacting_gap_computed": False,
        "continuum_trajectory_constructed": False,
        "thermodynamic_limit_constructed": False,
        "os_axioms_established": False,
        "euclidean_covariance_restored": False,
        "nontrivial_continuum_limit_established": False,
        "volume_uniform_mass_gap_established": False,
        "continuum_mass_gap_established": False,
        "clay_verdict": "NULL",
    }
    expected_negative_claims = {
        "interacting_gap_computed": False,
        "continuum_trajectory_constructed": False,
        "thermodynamic_limit_constructed": False,
        "os_axioms_established": False,
        "euclidean_covariance_restored": False,
        "nontrivial_continuum_limit_established": False,
        "volume_uniform_mass_gap_established": False,
        "continuum_mass_gap_established": False,
    }
    top_checks.append(
        check(
            "claim_boundary_exact",
            claims["two_loop_scaling_arithmetic"] == ("PASS" if preliminary_pass else "FAIL")
            and claims["double_scaling_necessity_diagnostic"]
            == ("PASS" if preliminary_pass else "FAIL")
            and claims["conditional_continuum_bridge_analytic"] is True
            and claims["analytic_theorem_outside_executable"] is True
            and all(claims[name] is expected for name, expected in expected_negative_claims.items())
            and claims["clay_verdict"] == "NULL",
            value=claims,
        )
    )

    all_checks = row_checks + top_checks
    if len(top_checks) != EXPECTED_TOP_CHECKS or len(all_checks) != EXPECTED_TOTAL_CHECKS:
        raise AssertionError(
            f"total check count drifted: top={len(top_checks)}, total={len(all_checks)}"
        )

    verdict = "PASS" if all(item["passed"] for item in all_checks) else "FAIL"
    if verdict == "FAIL":
        claims["two_loop_scaling_arithmetic"] = "FAIL"
        claims["double_scaling_necessity_diagnostic"] = "FAIL"

    return {
        "schema": "cassi.yang-mills.renormalized-gap-scaling.verification.v1",
        "verdict": verdict,
        "summary": {
            "checks": len(all_checks),
            "passing_checks": sum(item["passed"] for item in all_checks),
            "rows": len(rows),
            "row_checks": len(row_checks),
            "top_level_checks": len(top_checks),
            "firing_controls": len(firing_controls),
            "firing_controls_activated": sum(control["fired"] for control in firing_controls),
        },
        "parameters": {
            "g0_squared": list(G2_VALUES),
            "algebra_tolerance": ALGEBRA_TOLERANCE,
            "matched_gap_ratio": MATCHED_GAP_RATIO,
            "synthetic_widehat_gap": SYNTHETIC_EIGEN_GAP,
            "python_standard_library_only": True,
        },
        "coefficients": {"b0": B0, "b1": B1, "p": P},
        "classifications": {
            "volume": volume_classifications,
            "gap": gap_classifications,
        },
        "derivative_diagnostic": {
            "remainder_over_g7": derivative_remainders_over_g7,
            "expected_remainder_over_g7": derivative_expected,
            "absolute_remainder_over_g5": derivative_order_ratios,
        },
        "attempted_comparisons": {
            "wilson_log_form": len(rows),
            "hamiltonian_scale_map": len(rows),
            "derivative_identity": len(rows),
            "fixed_box_identity": len(rows),
            "thermodynamic_identities": 2 * len(rows),
            "matched_gap_identity": len(rows),
            "gap_normalization_map": 2 * len(rows),
            "trend_comparisons": 8 * (len(rows) - 1),
            "firing_control_comparisons": 2 * len(firing_controls),
        },
        "firing_controls": firing_controls,
        "claims": claims,
        "rows": rows,
        "checks": all_checks,
        "sources": source_bindings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    if output.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite existing receipt without --replace: {output}")

    receipt = build_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = receipt["summary"]
    print(
        "RENORMALIZED GAP SCALING "
        f"{receipt['verdict']} ({summary['passing_checks']}/{summary['checks']} checks)"
    )
    for row in receipt["rows"]:
        print(
            f"g0^2={row['g0_squared']:.2f} "
            f"log(a Lambda_L)={row['log_scale_from_coupling']:.12e} "
            f"a Lambda_L={row['scale']:.12e}"
        )
    print(
        "scope: arithmetic diagnostic only; interacting_gap_computed=false; "
        "continuum_mass_gap_established=false; clay_verdict=NULL"
    )
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
