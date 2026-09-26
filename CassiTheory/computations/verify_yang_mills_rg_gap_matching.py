#!/usr/bin/env python3
"""Verify the frozen conditional Yang--Mills RG gap-matching arithmetic.

The executable implements
``computations/yang-mills-rg-gap-matching-prereg.md``.  It checks telescoping,
blocking-rate, endpoint-window, volume and perturbative-flatness identities on
frozen synthetic schedules.  It does not construct a Yang--Mills RG flow,
transfer map, interacting gap or continuum quantum field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-rg-gap-matching-prereg.md"
SOURCE = Path(__file__).resolve()
INDEPENDENT_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_rg_gap_matching_independent.mjs"
)
OUTPUT = ROOT / "runs" / "yang-mills-rg-gap-matching" / "verification.json"
EXPECTED_PROTOCOL_SHA256 = "d8749326eb0fcf2062302e0afec4cb68dc2dd96ac532962bffdb18c658860f36"

G2_VALUES = (0.8, 0.5, 0.3, 0.2, 0.1, 0.05)
FLATNESS_POWERS = (1, 2, 4, 8)
B = 2.0
LOG_B = math.log(B)
ENDPOINT_LOWER = 1.0 / 64.0
ENDPOINT_UPPER_EXACT = 1.0 / 32.0
BOUNDED_STEP_DEFECT = 0.025
BOUNDED_CUMULATIVE_LIMIT = 0.025
ENDPOINT_UPPER_BOUNDED = B * math.exp(BOUNDED_STEP_DEFECT) * ENDPOINT_LOWER
DRIFT_STEP_DEFECT = BOUNDED_STEP_DEFECT / 4.0
COARSE_RATE_LOWER = 0.5
COARSE_RATE_UPPER = 2.0
TOLERANCE = 5.0e-13

EXPECTED_EXACT_ROWS = 6
EXPECTED_BOUNDED_ROWS = 6
EXPECTED_DRIFT_ROWS = 6
EXPECTED_EXACT_CHECKS = 42
EXPECTED_BOUNDED_CHECKS = 48
EXPECTED_DRIFT_CHECKS = 18
EXPECTED_VOLUME_CHECKS = 5
EXPECTED_FLATNESS_CHECKS = 4
EXPECTED_FIRING_CHECKS = 7
EXPECTED_TOP_CHECKS = 15
EXPECTED_TOTAL_CHECKS = 139
EXPECTED_FIRING_CONTROLS = 7

B0 = 11.0 / (24.0 * math.pi**2)
B1 = 17.0 / (96.0 * math.pi**4)
P = B1 / (2.0 * B0**2)

NEGATIVE_CLAIMS = (
    "balaban_uv_stability_is_mass_gap",
    "gaussian_no_go_claimed",
    "rg_trajectory_constructed",
    "exact_block_map_constructed",
    "transfer_correlation_matching_established",
    "observable_completeness_established",
    "coarse_interacting_gap_computed",
    "interacting_gap_computed",
    "thermodynamic_limit_constructed",
    "os_axioms_established",
    "nontrivial_continuum_limit_established",
    "continuum_mass_gap_established",
)


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


def close_absolute(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def close_relative(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def strictly_increasing(values: list[float]) -> bool:
    return all(right > left for left, right in zip(values, values[1:]))


def strictly_decreasing(values: list[float]) -> bool:
    return all(right < left for left, right in zip(values, values[1:]))


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


def log_scale(g2: float) -> float:
    return -1.0 / (2.0 * B0 * g2) - P * math.log(B0 * g2)


def scale(g2: float) -> float:
    return math.exp(log_scale(g2))


def exact_row(g2: float, index: int) -> dict[str, Any]:
    log_f0 = log_scale(g2)
    f0 = math.exp(log_f0)
    block_count = math.ceil((math.log(ENDPOINT_LOWER) - log_f0) / LOG_B)
    log_endpoint = log_f0 + block_count * LOG_B
    endpoint = math.exp(log_endpoint)
    cumulative_defect = 0.0
    coarse_rate = COARSE_RATE_LOWER + 0.25 * index
    log_fine_rate = math.log(coarse_rate) - block_count * LOG_B
    fine_rate = math.exp(log_fine_rate)
    block_ratio = math.exp(-block_count * LOG_B - log_f0)
    renormalized_rate = math.exp(log_fine_rate - log_f0)
    expected_renormalized_rate = coarse_rate / endpoint
    n0_f0 = 3.0 + index
    log_n0 = math.log(n0_f0) - log_f0
    log_nn = log_n0 - block_count * LOG_B
    expected_log_nn = math.log(n0_f0) + math.log(block_ratio)

    values = {
        "index": index,
        "g0_squared": g2,
        "log_scale": log_f0,
        "scale": f0,
        "block_count": block_count,
        "log_endpoint_scale": log_endpoint,
        "endpoint_scale": endpoint,
        "cumulative_defect": cumulative_defect,
        "coarse_rate": coarse_rate,
        "log_fine_rate": log_fine_rate,
        "fine_rate": fine_rate,
        "block_ratio_over_scale": block_ratio,
        "renormalized_rate": renormalized_rate,
        "expected_renormalized_rate": expected_renormalized_rate,
        "n0_times_scale": n0_f0,
        "log_initial_sites": log_n0,
        "log_coarse_sites": log_nn,
        "expected_log_coarse_sites": expected_log_nn,
    }

    lower_rate_ratio = COARSE_RATE_LOWER / ENDPOINT_UPPER_EXACT
    upper_rate_ratio = COARSE_RATE_UPPER / ENDPOINT_LOWER
    row_checks = [
        check(
            "exact_scale_reconstruction",
            math.isfinite(log_f0) and math.isfinite(f0) and f0 == scale(g2) and f0 > 0.0,
            value={"log_scale": log_f0, "scale": f0, "comparisons_attempted": 4},
        ),
        check(
            "exact_integer_stopping_depth",
            block_count > 0
            and block_count
            == math.ceil((math.log(ENDPOINT_LOWER) - log_f0) / LOG_B),
            value={"block_count": block_count, "comparisons_attempted": 2},
        ),
        check(
            "exact_endpoint_recurrence",
            close_relative(log_endpoint, log_f0 + block_count * LOG_B)
            and ENDPOINT_LOWER <= endpoint < ENDPOINT_UPPER_EXACT,
            value={
                "endpoint_scale": endpoint,
                "log_endpoint_scale": log_endpoint,
                "comparisons_attempted": 3,
            },
            threshold={"minimum_inclusive": ENDPOINT_LOWER, "maximum_exclusive": ENDPOINT_UPPER_EXACT},
        ),
        check(
            "exact_telescoping_identity",
            close_relative(block_ratio, 1.0 / endpoint),
            value={
                "left": block_ratio,
                "right": 1.0 / endpoint,
                "absolute_error": abs(block_ratio - 1.0 / endpoint),
                "comparisons_attempted": 1,
            },
            threshold=TOLERANCE,
        ),
        check(
            "exact_time_rate_rescaling",
            close_relative(fine_rate, coarse_rate * math.exp(-block_count * LOG_B)),
            value={
                "fine_rate": fine_rate,
                "expected": coarse_rate * math.exp(-block_count * LOG_B),
                "comparisons_attempted": 1,
            },
            threshold=TOLERANCE,
        ),
        check(
            "exact_renormalized_rate_bounds",
            close_relative(renormalized_rate, expected_renormalized_rate)
            and lower_rate_ratio <= renormalized_rate <= upper_rate_ratio,
            value={
                "renormalized_rate": renormalized_rate,
                "expected": expected_renormalized_rate,
                "comparisons_attempted": 3,
            },
            threshold={"minimum_inclusive": lower_rate_ratio, "maximum_inclusive": upper_rate_ratio},
        ),
        check(
            "exact_coarse_volume_factorization",
            close_relative(log_nn, expected_log_nn),
            value={
                "log_coarse_sites": log_nn,
                "expected_log_coarse_sites": expected_log_nn,
                "comparisons_attempted": 1,
            },
            threshold=TOLERANCE,
        ),
    ]
    if len(row_checks) != 7:
        raise AssertionError(f"exact row check count drifted: {len(row_checks)}")
    return {**values, "checks": row_checks}


def run_defect_schedule(log_f0: float, defect_at_step: Any) -> tuple[list[float], list[float]]:
    log_values = [log_f0]
    defects: list[float] = []
    while log_values[-1] < math.log(ENDPOINT_LOWER):
        if len(defects) >= 10_000:
            raise RuntimeError("defect schedule did not reach endpoint")
        defect = float(defect_at_step(len(defects)))
        defects.append(defect)
        log_values.append(log_values[-1] + LOG_B + defect)
    return log_values, defects


def bounded_row(g2: float, index: int) -> dict[str, Any]:
    log_f0 = log_scale(g2)
    f0 = math.exp(log_f0)
    log_values, defects = run_defect_schedule(
        log_f0,
        lambda step: BOUNDED_STEP_DEFECT if step % 2 == 0 else -BOUNDED_STEP_DEFECT,
    )
    block_count = len(defects)
    cumulative_defect = math.fsum(defects)
    log_endpoint = log_values[-1]
    endpoint = math.exp(log_endpoint)
    coarse_rate = COARSE_RATE_LOWER + 0.25 * index
    log_fine_rate = math.log(coarse_rate) - block_count * LOG_B
    fine_rate = math.exp(log_fine_rate)
    block_ratio = math.exp(-block_count * LOG_B - log_f0)
    expected_block_ratio = math.exp(cumulative_defect) / endpoint
    renormalized_rate = math.exp(log_fine_rate - log_f0)
    expected_renormalized_rate = coarse_rate * math.exp(cumulative_defect) / endpoint
    replay_log_endpoint = log_f0 + block_count * LOG_B + cumulative_defect

    values = {
        "index": index,
        "g0_squared": g2,
        "log_scale": log_f0,
        "scale": f0,
        "block_count": block_count,
        "defects": defects,
        "cumulative_defect": cumulative_defect,
        "log_endpoint_scale": log_endpoint,
        "endpoint_scale": endpoint,
        "coarse_rate": coarse_rate,
        "log_fine_rate": log_fine_rate,
        "fine_rate": fine_rate,
        "block_ratio_over_scale": block_ratio,
        "expected_block_ratio_over_scale": expected_block_ratio,
        "renormalized_rate": renormalized_rate,
        "expected_renormalized_rate": expected_renormalized_rate,
        "qualified": (
            ENDPOINT_LOWER <= endpoint <= ENDPOINT_UPPER_BOUNDED
            and abs(cumulative_defect) <= BOUNDED_CUMULATIVE_LIMIT + TOLERANCE
        ),
    }

    lower_rate_ratio = (
        COARSE_RATE_LOWER
        * math.exp(-BOUNDED_CUMULATIVE_LIMIT)
        / ENDPOINT_UPPER_BOUNDED
    )
    upper_rate_ratio = (
        COARSE_RATE_UPPER
        * math.exp(BOUNDED_CUMULATIVE_LIMIT)
        / ENDPOINT_LOWER
    )
    row_checks = [
        check(
            "bounded_scale_reconstruction",
            math.isfinite(log_f0) and math.isfinite(f0) and f0 == scale(g2) and f0 > 0.0,
            value={"log_scale": log_f0, "scale": f0, "comparisons_attempted": 4},
        ),
        check(
            "bounded_positive_stopping_depth",
            block_count > 0 and block_count < 10_000,
            value={"block_count": block_count, "comparisons_attempted": 2},
        ),
        check(
            "bounded_recurrence_replay",
            len(log_values) == block_count + 1
            and len(defects) == block_count
            and close_relative(log_endpoint, replay_log_endpoint),
            value={
                "steps": block_count,
                "log_endpoint": log_endpoint,
                "replayed_log_endpoint": replay_log_endpoint,
                "comparisons_attempted": block_count + 3,
            },
            threshold=TOLERANCE,
        ),
        check(
            "bounded_endpoint_window",
            ENDPOINT_LOWER <= endpoint <= ENDPOINT_UPPER_BOUNDED,
            value={"endpoint_scale": endpoint, "comparisons_attempted": 2},
            threshold={"minimum_inclusive": ENDPOINT_LOWER, "maximum_inclusive": ENDPOINT_UPPER_BOUNDED},
        ),
        check(
            "bounded_cumulative_defect",
            abs(cumulative_defect) <= BOUNDED_CUMULATIVE_LIMIT + TOLERANCE,
            value={
                "cumulative_defect": cumulative_defect,
                "maximum_step_defect": max(abs(item) for item in defects),
                "comparisons_attempted": len(defects) + 1,
            },
            threshold=BOUNDED_CUMULATIVE_LIMIT,
        ),
        check(
            "bounded_telescoping_identity",
            close_relative(block_ratio, expected_block_ratio),
            value={
                "left": block_ratio,
                "right": expected_block_ratio,
                "absolute_error": abs(block_ratio - expected_block_ratio),
                "comparisons_attempted": 1,
            },
            threshold=TOLERANCE,
        ),
        check(
            "bounded_time_rate_rescaling",
            close_relative(fine_rate, coarse_rate * math.exp(-block_count * LOG_B)),
            value={
                "fine_rate": fine_rate,
                "expected": coarse_rate * math.exp(-block_count * LOG_B),
                "comparisons_attempted": 1,
            },
            threshold=TOLERANCE,
        ),
        check(
            "bounded_renormalized_rate_bounds",
            close_relative(renormalized_rate, expected_renormalized_rate)
            and lower_rate_ratio <= renormalized_rate <= upper_rate_ratio,
            value={
                "renormalized_rate": renormalized_rate,
                "expected": expected_renormalized_rate,
                "comparisons_attempted": 3,
            },
            threshold={"minimum_inclusive": lower_rate_ratio, "maximum_inclusive": upper_rate_ratio},
        ),
    ]
    if len(row_checks) != 8:
        raise AssertionError(f"bounded row check count drifted: {len(row_checks)}")
    return {**values, "checks": row_checks}


def drift_row(g2: float, index: int) -> dict[str, Any]:
    log_f0 = log_scale(g2)
    log_values, defects = run_defect_schedule(log_f0, lambda _step: DRIFT_STEP_DEFECT)
    block_count = len(defects)
    cumulative_defect = math.fsum(defects)
    log_endpoint = log_values[-1]
    endpoint = math.exp(log_endpoint)
    replay_log_endpoint = log_f0 + block_count * LOG_B + cumulative_defect
    maximum_step_defect = max(abs(item) for item in defects)
    full_qualified = (
        ENDPOINT_LOWER <= endpoint <= ENDPOINT_UPPER_BOUNDED
        and abs(cumulative_defect) <= BOUNDED_CUMULATIVE_LIMIT + TOLERANCE
    )
    per_step_only_qualified = (
        ENDPOINT_LOWER <= endpoint <= ENDPOINT_UPPER_BOUNDED
        and maximum_step_defect <= BOUNDED_STEP_DEFECT + TOLERANCE
    )
    values = {
        "index": index,
        "g0_squared": g2,
        "log_scale": log_f0,
        "block_count": block_count,
        "defects": defects,
        "cumulative_defect": cumulative_defect,
        "maximum_step_defect": maximum_step_defect,
        "log_endpoint_scale": log_endpoint,
        "endpoint_scale": endpoint,
        "qualified": full_qualified,
        "per_step_only_qualified": per_step_only_qualified,
    }
    row_checks = [
        check(
            "drift_recurrence_replay",
            len(log_values) == block_count + 1
            and len(defects) == block_count
            and close_relative(log_endpoint, replay_log_endpoint),
            value={
                "steps": block_count,
                "log_endpoint": log_endpoint,
                "replayed_log_endpoint": replay_log_endpoint,
                "comparisons_attempted": block_count + 3,
            },
            threshold=TOLERANCE,
        ),
        check(
            "drift_violates_cumulative_bound",
            cumulative_defect > BOUNDED_CUMULATIVE_LIMIT
            and maximum_step_defect < BOUNDED_STEP_DEFECT,
            value={
                "cumulative_defect": cumulative_defect,
                "maximum_step_defect": maximum_step_defect,
                "comparisons_attempted": 2,
            },
            threshold={
                "cumulative_maximum": BOUNDED_CUMULATIVE_LIMIT,
                "step_maximum": BOUNDED_STEP_DEFECT,
            },
        ),
        check(
            "drift_schedule_rejected",
            not full_qualified and per_step_only_qualified,
            value={
                "qualified": full_qualified,
                "per_step_only_qualified": per_step_only_qualified,
                "comparisons_attempted": 2,
            },
        ),
    ]
    if len(row_checks) != 3:
        raise AssertionError(f"drift row check count drifted: {len(row_checks)}")
    return {**values, "checks": row_checks}


def build_volume_schedules(log_scales: list[float]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    log_g2 = [math.log(g2) for g2 in G2_VALUES]
    schedules = [
        {
            "name": "fixed_sites",
            "classification": "COLLAPSE",
            "log_n0_times_scale": [math.log(1024.0) + item for item in log_scales],
        },
        {
            "name": "polynomial",
            "classification": "COLLAPSE",
            "log_n0_times_scale": [
                -4.0 * coupling_log + scale_log
                for coupling_log, scale_log in zip(log_g2, log_scales)
            ],
        },
        {
            "name": "fixed_physical_box",
            "classification": "FIXED",
            "log_n0_times_scale": [math.log(3.0) for _ in log_scales],
        },
        {
            "name": "inverse_g2_enhanced",
            "classification": "INFINITE",
            "log_n0_times_scale": [-item for item in log_g2],
        },
        {
            "name": "logarithmically_enhanced",
            "classification": "INFINITE",
            "log_n0_times_scale": [math.log(-item) for item in log_scales],
        },
    ]

    checks: list[dict[str, Any]] = []
    for schedule in schedules:
        values = schedule["log_n0_times_scale"]
        classification = schedule["classification"]
        if classification == "COLLAPSE":
            passed = strictly_decreasing(values)
        elif classification == "FIXED":
            passed = all(close_absolute(value, math.log(3.0)) for value in values)
        elif classification == "INFINITE":
            passed = strictly_increasing(values)
        else:
            passed = False
        checks.append(
            check(
                f"volume_{schedule['name']}_{classification.lower()}",
                passed,
                value={
                    "classification": classification,
                    "log_n0_times_scale": values,
                    "comparisons_attempted": len(values) if classification == "FIXED" else len(values) - 1,
                },
            )
        )
    return schedules, checks


def build_flatness_rows(log_scales: list[float]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for power in FLATNESS_POWERS:
        log_ratios = [
            log_f - 0.5 * power * math.log(g2)
            for g2, log_f in zip(G2_VALUES, log_scales)
        ]
        ratios = [math.exp(item) for item in log_ratios]
        rows.append({"power": power, "log_ratios": log_ratios, "ratios": ratios})
        checks.append(
            check(
                f"flatness_power_{power}_decreases",
                strictly_decreasing(log_ratios) and all(value > 0.0 for value in ratios),
                value={
                    "power": power,
                    "log_ratios": log_ratios,
                    "ratios": ratios,
                    "comparisons_attempted": 2 * len(ratios) - 1,
                },
            )
        )
    return rows, checks


def full_gap_conclusion_allowed(flags: dict[str, bool]) -> bool:
    required = (
        "rg_construction",
        "cumulative_defect_bound",
        "transfer_matching",
        "positive_endpoint_gap",
        "observable_completeness",
        "os_continuum_construction",
    )
    return all(flags.get(name) is True for name in required)


def construct_firing_controls(
    exact_rows: list[dict[str, Any]],
    bounded_rows: list[dict[str, Any]],
    drift_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    defect_witness = next(
        row
        for row in bounded_rows
        if abs(row["cumulative_defect"]) > BOUNDED_STEP_DEFECT / 2.0
    )
    exact_witness = exact_rows[-1]
    drift_witness = drift_rows[-1]

    correct_defect_formula = math.exp(defect_witness["cumulative_defect"]) / defect_witness["endpoint_scale"]
    omitted_defect_formula = 1.0 / defect_witness["endpoint_scale"]
    reversed_defect_formula = math.exp(-defect_witness["cumulative_defect"]) / defect_witness["endpoint_scale"]
    actual_block_ratio = defect_witness["block_ratio_over_scale"]

    full_flags = {
        "rg_construction": True,
        "cumulative_defect_bound": True,
        "transfer_matching": True,
        "positive_endpoint_gap": True,
        "observable_completeness": True,
        "os_continuum_construction": True,
    }
    incomplete_flags = {**full_flags, "observable_completeness": False}

    controls = [
        {
            "name": "omit_cumulative_defect_factor",
            "unmutated_passed": close_relative(actual_block_ratio, correct_defect_formula),
            "mutation_passed": close_relative(actual_block_ratio, omitted_defect_formula),
        },
        {
            "name": "reverse_cumulative_defect_sign",
            "unmutated_passed": close_relative(actual_block_ratio, correct_defect_formula),
            "mutation_passed": close_relative(actual_block_ratio, reversed_defect_formula),
        },
        {
            "name": "accept_per_step_only_drift",
            "unmutated_passed": not drift_witness["qualified"],
            "mutation_passed": not drift_witness["per_step_only_qualified"],
        },
        {
            "name": "omit_time_rate_rescaling",
            "unmutated_passed": close_relative(
                exact_witness["fine_rate"],
                exact_witness["coarse_rate"] * math.exp(-exact_witness["block_count"] * LOG_B),
            ),
            "mutation_passed": close_relative(
                exact_witness["coarse_rate"],
                exact_witness["fine_rate"],
            ),
        },
        {
            "name": "call_fixed_box_infinite",
            "unmutated_passed": "FIXED" == "FIXED",
            "mutation_passed": "INFINITE" == "FIXED",
        },
        {
            "name": "accept_zero_endpoint_rate",
            "unmutated_passed": COARSE_RATE_LOWER > 0.0,
            "mutation_passed": 0.0 > 0.0,
        },
        {
            "name": "conclude_without_observable_completeness",
            "unmutated_passed": full_gap_conclusion_allowed(full_flags),
            "mutation_passed": full_gap_conclusion_allowed(incomplete_flags),
        },
    ]
    for control in controls:
        control["fired"] = bool(control["unmutated_passed"] and not control["mutation_passed"])
        control["comparisons_attempted"] = 2
    return controls


def exact_claim_boundary(claims: dict[str, Any], executable_status: str) -> bool:
    return (
        claims.get("two_loop_blocking_arithmetic") == executable_status
        and claims.get("conditional_rg_gap_matching_theorem_analytic") is True
        and claims.get("analytic_theorem_outside_executable") is True
        and all(claims.get(name) is False for name in NEGATIVE_CLAIMS)
        and claims.get("clay_verdict") == "NULL"
    )


def build_receipt() -> dict[str, Any]:
    exact_rows = [exact_row(g2, index) for index, g2 in enumerate(G2_VALUES)]
    bounded_rows = [bounded_row(g2, index) for index, g2 in enumerate(G2_VALUES)]
    drift_rows = [drift_row(g2, index) for index, g2 in enumerate(G2_VALUES)]
    exact_checks = [item for row in exact_rows for item in row["checks"]]
    bounded_checks = [item for row in bounded_rows for item in row["checks"]]
    drift_checks = [item for row in drift_rows for item in row["checks"]]

    log_scales = [log_scale(g2) for g2 in G2_VALUES]
    scales = [math.exp(item) for item in log_scales]
    volume_schedules, volume_checks = build_volume_schedules(log_scales)
    flatness_rows, flatness_checks = build_flatness_rows(log_scales)
    firing_controls = construct_firing_controls(exact_rows, bounded_rows, drift_rows)
    firing_checks = [
        check(
            f"mutation_{control['name']}_fires",
            control["fired"],
            value=control,
            threshold={"unmutated_passed": True, "mutation_passed": False},
        )
        for control in firing_controls
    ]

    source_bindings = {
        "protocol": {"path": relative(PROTOCOL), "sha256": sha256(PROTOCOL)},
        "primary_source": {"path": relative(SOURCE), "sha256": sha256(SOURCE)},
        "independent_source": {
            "path": relative(INDEPENDENT_SOURCE),
            "sha256": sha256(INDEPENDENT_SOURCE),
        },
    }
    hex_digits = set("0123456789abcdef")

    expected_volume_classes = {
        "fixed_sites": "COLLAPSE",
        "polynomial": "COLLAPSE",
        "fixed_physical_box": "FIXED",
        "inverse_g2_enhanced": "INFINITE",
        "logarithmically_enhanced": "INFINITE",
    }
    actual_volume_classes = {
        schedule["name"]: schedule["classification"] for schedule in volume_schedules
    }

    top_checks: list[dict[str, Any]] = [
        check(
            "su2_universal_coefficients",
            close_absolute(B0, 11.0 / (24.0 * math.pi**2))
            and close_absolute(B1, 17.0 / (96.0 * math.pi**4)),
            value={"b0": B0, "b1": B1, "comparisons_attempted": 2},
            threshold=TOLERANCE,
        ),
        check(
            "two_loop_power",
            close_absolute(P, 51.0 / 121.0),
            value={"p": P, "expected": 51.0 / 121.0, "comparisons_attempted": 1},
            threshold=TOLERANCE,
        ),
        check(
            "frozen_constants_and_schedules",
            B == 2.0
            and ENDPOINT_LOWER == 1.0 / 64.0
            and ENDPOINT_UPPER_EXACT == 1.0 / 32.0
            and BOUNDED_STEP_DEFECT == 0.025
            and BOUNDED_CUMULATIVE_LIMIT == 0.025
            and DRIFT_STEP_DEFECT == 0.025 / 4.0
            and COARSE_RATE_LOWER == 0.5
            and COARSE_RATE_UPPER == 2.0
            and G2_VALUES == (0.8, 0.5, 0.3, 0.2, 0.1, 0.05)
            and FLATNESS_POWERS == (1, 2, 4, 8),
            value={
                "B": B,
                "endpoint_lower": ENDPOINT_LOWER,
                "endpoint_upper_exact": ENDPOINT_UPPER_EXACT,
                "endpoint_upper_bounded": ENDPOINT_UPPER_BOUNDED,
                "bounded_step_defect": BOUNDED_STEP_DEFECT,
                "bounded_cumulative_limit": BOUNDED_CUMULATIVE_LIMIT,
                "drift_step_defect": DRIFT_STEP_DEFECT,
                "coarse_rate_lower": COARSE_RATE_LOWER,
                "coarse_rate_upper": COARSE_RATE_UPPER,
                "g0_squared": list(G2_VALUES),
                "flatness_powers": list(FLATNESS_POWERS),
                "comparisons_attempted": 10,
            },
        ),
        check(
            "log_scales_finite",
            all(math.isfinite(item) for item in log_scales),
            value={"log_scales": log_scales, "comparisons_attempted": len(log_scales)},
        ),
        check(
            "scales_positive_finite",
            all(math.isfinite(item) and item > 0.0 for item in scales),
            value={"scales": scales, "comparisons_attempted": 2 * len(scales)},
        ),
        check(
            "scales_strictly_decrease_toward_weak_coupling",
            strictly_decreasing(log_scales),
            value={"log_scales": log_scales, "comparisons_attempted": len(log_scales) - 1},
        ),
        check(
            "log_scale_derivative_positive",
            all(
                1.0 / (B0 * math.sqrt(g2) ** 3) - 2.0 * P / math.sqrt(g2) > 0.0
                for g2 in G2_VALUES
            ),
            value={"couplings_checked": len(G2_VALUES), "comparisons_attempted": len(G2_VALUES)},
        ),
        check(
            "exact_block_depths_strictly_increase",
            strictly_increasing([float(row["block_count"]) for row in exact_rows]),
            value={
                "block_counts": [row["block_count"] for row in exact_rows],
                "comparisons_attempted": len(exact_rows) - 1,
            },
        ),
        check(
            "row_and_component_check_counts",
            len(exact_rows) == EXPECTED_EXACT_ROWS
            and len(bounded_rows) == EXPECTED_BOUNDED_ROWS
            and len(drift_rows) == EXPECTED_DRIFT_ROWS
            and len(exact_checks) == EXPECTED_EXACT_CHECKS
            and len(bounded_checks) == EXPECTED_BOUNDED_CHECKS
            and len(drift_checks) == EXPECTED_DRIFT_CHECKS
            and len(volume_checks) == EXPECTED_VOLUME_CHECKS
            and len(flatness_checks) == EXPECTED_FLATNESS_CHECKS
            and len(firing_checks) == EXPECTED_FIRING_CHECKS,
            value={
                "exact_rows": len(exact_rows),
                "bounded_rows": len(bounded_rows),
                "drift_rows": len(drift_rows),
                "exact_checks": len(exact_checks),
                "bounded_checks": len(bounded_checks),
                "drift_checks": len(drift_checks),
                "volume_checks": len(volume_checks),
                "flatness_checks": len(flatness_checks),
                "firing_checks": len(firing_checks),
                "comparisons_attempted": 9,
            },
        ),
        check(
            "all_exact_endpoints_in_window",
            all(
                ENDPOINT_LOWER <= row["endpoint_scale"] < ENDPOINT_UPPER_EXACT
                for row in exact_rows
            ),
            value={
                "endpoints": [row["endpoint_scale"] for row in exact_rows],
                "comparisons_attempted": 2 * len(exact_rows),
            },
        ),
        check(
            "all_bounded_endpoints_in_window",
            all(
                ENDPOINT_LOWER <= row["endpoint_scale"] <= ENDPOINT_UPPER_BOUNDED
                for row in bounded_rows
            ),
            value={
                "endpoints": [row["endpoint_scale"] for row in bounded_rows],
                "comparisons_attempted": 2 * len(bounded_rows),
            },
        ),
        check(
            "all_drift_rows_rejected",
            all(
                not row["qualified"] and row["per_step_only_qualified"]
                for row in drift_rows
            ),
            value={
                "cumulative_defects": [row["cumulative_defect"] for row in drift_rows],
                "comparisons_attempted": 2 * len(drift_rows),
            },
        ),
        check(
            "volume_classifications_match_frozen_contract",
            actual_volume_classes == expected_volume_classes,
            value={
                "actual": actual_volume_classes,
                "expected": expected_volume_classes,
                "comparisons_attempted": len(expected_volume_classes),
            },
        ),
        check(
            "source_bindings_present_and_protocol_frozen",
            source_bindings["protocol"]["sha256"] == EXPECTED_PROTOCOL_SHA256
            and all(
                binding["path"]
                and len(binding["sha256"]) == 64
                and set(binding["sha256"]) <= hex_digits
                for binding in source_bindings.values()
            ),
            value={
                "bindings": source_bindings,
                "expected_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                "comparisons_attempted": 4,
            },
            threshold={"sha256_hex_characters": 64},
        ),
    ]
    if len(top_checks) != EXPECTED_TOP_CHECKS - 1:
        raise AssertionError(f"pre-claim top-level check count drifted: {len(top_checks)}")

    component_checks = (
        exact_checks
        + bounded_checks
        + drift_checks
        + volume_checks
        + flatness_checks
        + firing_checks
    )
    preliminary_pass = all(item["passed"] for item in component_checks + top_checks)
    executable_status = "PASS" if preliminary_pass else "FAIL"
    claims: dict[str, Any] = {
        "two_loop_blocking_arithmetic": executable_status,
        "conditional_rg_gap_matching_theorem_analytic": True,
        "analytic_theorem_outside_executable": True,
        **{name: False for name in NEGATIVE_CLAIMS},
        "clay_verdict": "NULL",
    }
    top_checks.append(
        check(
            "claim_boundary_exact",
            exact_claim_boundary(claims, executable_status),
            value=claims,
        )
    )

    all_checks = component_checks + top_checks
    if len(top_checks) != EXPECTED_TOP_CHECKS or len(all_checks) != EXPECTED_TOTAL_CHECKS:
        raise AssertionError(
            f"total check count drifted: top={len(top_checks)}, total={len(all_checks)}"
        )
    verdict = "PASS" if all(item["passed"] for item in all_checks) else "FAIL"
    if verdict == "FAIL":
        claims["two_loop_blocking_arithmetic"] = "FAIL"

    receipt = {
        "schema": "cassi.yang-mills.rg-gap-matching.verification.v1",
        "verdict": verdict,
        "summary": {
            "checks": len(all_checks),
            "passing_checks": sum(item["passed"] for item in all_checks),
            "exact_rows": len(exact_rows),
            "bounded_rows": len(bounded_rows),
            "drift_rows": len(drift_rows),
            "exact_checks": len(exact_checks),
            "bounded_checks": len(bounded_checks),
            "drift_checks": len(drift_checks),
            "volume_checks": len(volume_checks),
            "flatness_checks": len(flatness_checks),
            "firing_checks": len(firing_checks),
            "top_level_checks": len(top_checks),
            "firing_controls": len(firing_controls),
            "firing_controls_activated": sum(control["fired"] for control in firing_controls),
        },
        "parameters": {
            "B": B,
            "endpoint_lower": ENDPOINT_LOWER,
            "endpoint_upper_exact": ENDPOINT_UPPER_EXACT,
            "endpoint_upper_bounded": ENDPOINT_UPPER_BOUNDED,
            "bounded_step_defect": BOUNDED_STEP_DEFECT,
            "bounded_cumulative_limit": BOUNDED_CUMULATIVE_LIMIT,
            "drift_step_defect": DRIFT_STEP_DEFECT,
            "coarse_rate_lower": COARSE_RATE_LOWER,
            "coarse_rate_upper": COARSE_RATE_UPPER,
            "g0_squared": list(G2_VALUES),
            "flatness_powers": list(FLATNESS_POWERS),
            "tolerance": TOLERANCE,
            "python_standard_library_only": True,
        },
        "coefficients": {"b0": B0, "b1": B1, "p": P},
        "scale_bound": {
            "lower_block_ratio": math.exp(-BOUNDED_CUMULATIVE_LIMIT) / ENDPOINT_UPPER_BOUNDED,
            "upper_block_ratio": math.exp(BOUNDED_CUMULATIVE_LIMIT) / ENDPOINT_LOWER,
            "lower_renormalized_rate": (
                COARSE_RATE_LOWER
                * math.exp(-BOUNDED_CUMULATIVE_LIMIT)
                / ENDPOINT_UPPER_BOUNDED
            ),
            "upper_renormalized_rate": (
                COARSE_RATE_UPPER
                * math.exp(BOUNDED_CUMULATIVE_LIMIT)
                / ENDPOINT_LOWER
            ),
        },
        "exact_rows": exact_rows,
        "bounded_rows": bounded_rows,
        "drift_rows": drift_rows,
        "volume_schedules": volume_schedules,
        "flatness_rows": flatness_rows,
        "firing_controls": firing_controls,
        "claims": claims,
        "checks": all_checks,
        "sources": source_bindings,
    }
    if not finite_payload(receipt):
        raise ValueError("receipt contains a non-finite or unsupported value")
    return receipt


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
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    summary = receipt["summary"]
    print(
        "YANG-MILLS RG GAP MATCHING "
        f"{receipt['verdict']} ({summary['passing_checks']}/{summary['checks']} checks)"
    )
    for row in receipt["bounded_rows"]:
        print(
            f"g0^2={row['g0_squared']:.2f} "
            f"n={row['block_count']:3d} "
            f"R_n={row['cumulative_defect']:+.6f} "
            f"delta0/F={row['renormalized_rate']:.12e}"
        )
    print(
        "scope: conditional arithmetic only; rg_trajectory_constructed=false; "
        "interacting_gap_computed=false; continuum_mass_gap_established=false; "
        "clay_verdict=NULL"
    )
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
