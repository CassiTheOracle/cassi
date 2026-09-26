#!/usr/bin/env python3
"""Independent verifier for the preregistered Qi-loop mass-cascade receipt."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PHI = (1.0 + math.sqrt(5.0)) / 2.0
TENSION = 1.0
K_Y = 1.0
K_I = 1.0
K_DELTA = 1.0
RECORD_LIMIT = 144
RECORD_MARGIN = 1.0e-15
A1_LIMIT = 1.0e-12
A3_LIMIT = 1.0e-15
A4_FLOOR = 0.08
B_LIMIT = 1.0e-12
RING_POINTS = 256
SCALE_LAST_N = 8
C2_LIMIT = 0.01
C34_LIMIT = 1.0e-4
COUPLING_ARMS = (0.0, 0.25, 1.0, 4.0)
PRIMITIVE_P_LIMIT = 34
PRIMITIVE_Q_LIMIT = 55
ANCHOR = (13, 21)
EXPECTED_PHI_RECORDS = [
    (1, 2),
    (2, 3),
    (3, 5),
    (5, 8),
    (8, 13),
    (13, 21),
    (21, 34),
    (34, 55),
    (55, 89),
    (89, 144),
    (144, 233),
]

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "field-experience" / "qi-loop-mass-cascade-pre-registration.md"
PRIMARY_PATH = Path(__file__).with_name("qi_loop_mass_cascade_probe.py")
VERIFIER_PATH = Path(__file__).resolve()


def _relative_error(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), 1.0e-300)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or isinstance(value, str):
        return True
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(_finite_tree(item) for item in value.values())
    return False


def _round_nearest_high(value: float) -> int:
    integer = math.floor(value)
    return max(1, integer if value - integer < 0.5 else integer + 1)


def _convergents(alpha: float) -> list[tuple[int, int]]:
    record: list[tuple[int, int]] = []
    previous = math.inf
    for denominator in range(1, RECORD_LIMIT + 1):
        numerator = _round_nearest_high(alpha * denominator)
        residual = abs(numerator - alpha * denominator)
        if residual < previous - RECORD_MARGIN:
            record.append((denominator, numerator))
            previous = residual
    return record


def _fibonacci(limit: int) -> list[int]:
    output = [0, 1]
    while len(output) <= limit:
        output.append(output[-1] + output[-2])
    return output


def _a_value(p: int, q_winding: int, alpha: float, k_delta: float = K_DELTA) -> float:
    mismatch = q_winding - alpha * p
    return K_Y * p**2 + K_I * q_winding**2 + k_delta * mismatch**2


def _h_star(p: int, q_winding: int, alpha: float, k_delta: float = K_DELTA, tension: float = TENSION) -> float:
    return 2.0 * math.sqrt(2.0 * math.pi**2 * tension * _a_value(p, q_winding, alpha, k_delta))


def _smallest_phase_eigenvalue(alpha: float) -> float:
    diagonal_y = K_Y + alpha**2 * K_DELTA
    diagonal_i = K_I + K_DELTA
    off_diagonal = -alpha * K_DELTA
    return (diagonal_y + diagonal_i - math.sqrt((diagonal_y - diagonal_i) ** 2 + 4.0 * off_diagonal**2)) / 2.0


def _evaluate_mode(p: int, q_winding: int, alpha: float) -> dict[str, Any]:
    a_value = _a_value(p, q_winding, alpha)
    length = math.sqrt(2.0 * math.pi**2 * a_value / TENSION)
    h_star = _h_star(p, q_winding, alpha)
    energy_at_length = TENSION * length + 2.0 * math.pi**2 * a_value / length
    stationarity_side = 2.0 * math.pi**2 * a_value / length**2
    stationarity_residual = _relative_error(TENSION, stationarity_side)
    length_relation_residual = _relative_error(length**2, 2.0 * math.pi**2 * a_value / TENSION)
    energy_relation_residual = _relative_error(energy_at_length, h_star)
    hessian = 4.0 * math.pi**2 * a_value / length**3
    energy_below = TENSION * (0.99 * length) + 2.0 * math.pi**2 * a_value / (0.99 * length)
    energy_above = TENSION * (1.01 * length) + 2.0 * math.pi**2 * a_value / (1.01 * length)
    gradient_y = 2.0 * math.pi * p / length
    gradient_i = 2.0 * math.pi * q_winding / length
    current_y = (K_Y + alpha**2 * K_DELTA) * gradient_y - alpha * K_DELTA * gradient_i
    current_i = (K_I + K_DELTA) * gradient_i - alpha * K_DELTA * gradient_y
    current_norm = math.hypot(current_y, current_i)
    delta_s = length / RING_POINTS
    current_y_values = [current_y] * RING_POINTS
    current_i_values = [current_i] * RING_POINTS
    divergence_y = max(
        abs((current_y_values[(index + 1) % RING_POINTS] - current_y_values[index - 1]) / (2.0 * delta_s))
        for index in range(RING_POINTS)
    )
    divergence_i = max(
        abs((current_i_values[(index + 1) % RING_POINTS] - current_i_values[index - 1]) / (2.0 * delta_s))
        for index in range(RING_POINTS)
    )
    divergence = max(divergence_y, divergence_i)
    minimum_eigenvalue = _smallest_phase_eigenvalue(alpha)
    closed_form_gates = {
        "length_relation": length_relation_residual < B_LIMIT,
        "energy_relation": energy_relation_residual < B_LIMIT,
        "stationarity": stationarity_residual < B_LIMIT,
        "radial_hessian": hessian > 0.0,
    }
    stability_gates = {
        "B1_stationarity": stationarity_residual < B_LIMIT,
        "B2_radial_stability": hessian > 0.0 and energy_below > h_star and energy_above > h_star,
        "B3_phase_stability": minimum_eigenvalue > 0.0,
        "B4_stationary_circulation": divergence < B_LIMIT and current_norm > B_LIMIT,
    }
    return {
        "yang_winding": p,
        "yin_winding": q_winding,
        "coefficient": a_value,
        "length_star": length,
        "energy_star": h_star,
        "length_relation_residual": length_relation_residual,
        "energy_relation_residual": energy_relation_residual,
        "stationarity_residual": stationarity_residual,
        "radial_hessian": hessian,
        "energy_below_star": energy_below,
        "energy_above_star": energy_above,
        "phase_min_eigenvalue": minimum_eigenvalue,
        "current_y": current_y,
        "current_i": current_i,
        "current_norm": current_norm,
        "max_current_divergence": divergence,
        "closed_form_gates": closed_form_gates,
        "stability_gates": stability_gates,
    }


def _recompute_arithmetic() -> dict[str, Any]:
    phi_records = _convergents(PHI)
    rational_records = _convergents(1.5)
    sqrt2_records = _convergents(math.sqrt(2.0))
    fibonacci = _fibonacci(13)
    identities = []
    for n in range(2, 13):
        left = fibonacci[n + 1] - PHI * fibonacci[n]
        right = (-1) ** n * PHI ** (-n)
        identities.append(
            {"index": n, "left": left, "right": right, "absolute_residual": abs(left - right)}
        )
    phi_weighted = 144 * abs(233 - PHI * 144)
    sqrt2_weighted = 70 * abs(99 - math.sqrt(2.0) * 70)
    gap = phi_weighted - sqrt2_weighted
    gates = {
        "A1_fibonacci_identity": max(row["absolute_residual"] for row in identities) < A1_LIMIT,
        "A2_phi_record_sequence": phi_records == EXPECTED_PHI_RECORDS,
        "A3_rational_closure": abs(3 - 1.5 * 2) < A3_LIMIT,
        "A4_finite_deresonance_control": gap >= A4_FLOOR,
    }
    return {
        "phi_records": [{"yang_winding": p, "yin_winding": q} for p, q in phi_records],
        "rational_records": [{"yang_winding": p, "yin_winding": q} for p, q in rational_records],
        "sqrt2_records": [{"yang_winding": p, "yin_winding": q} for p, q in sqrt2_records],
        "fibonacci_identity": identities,
        "phi_final_weighted_residual": phi_weighted,
        "sqrt2_final_weighted_residual": sqrt2_weighted,
        "weighted_residual_gap": gap,
        "gates": gates,
        "stage_pass": all(gates.values()),
    }


def _recompute_loop(arithmetic: dict[str, Any]) -> dict[str, Any]:
    inputs = (
        ("phi", PHI, arithmetic["phi_records"]),
        ("rational_control", 1.5, arithmetic["rational_records"]),
        ("sqrt2_control", math.sqrt(2.0), arithmetic["sqrt2_records"]),
    )
    all_modes: list[dict[str, Any]] = []
    family_rows = []
    length_errors: list[float] = []
    energy_errors: list[float] = []
    for name, alpha, records in inputs:
        modes = [_evaluate_mode(row["yang_winding"], row["yin_winding"], alpha) for row in records]
        family_rows.append({"name": name, "alpha": alpha, "modes": modes})
        all_modes.extend(modes)
        for mode in modes:
            for scale in range(SCALE_LAST_N + 1):
                scaled_tension = TENSION * PHI ** (-2 * scale)
                scaled_length = math.sqrt(2.0 * math.pi**2 * mode["coefficient"] / scaled_tension)
                scaled_energy = 2.0 * math.sqrt(2.0 * math.pi**2 * scaled_tension * mode["coefficient"])
                length_errors.append(_relative_error(scaled_length, mode["length_star"] * PHI**scale))
                energy_errors.append(_relative_error(scaled_energy, mode["energy_star"] * PHI ** (-scale)))
    gates = {
        "B1_stationarity": max(mode["stationarity_residual"] for mode in all_modes) < B_LIMIT,
        "B2_radial_stability": all(mode["stability_gates"]["B2_radial_stability"] for mode in all_modes),
        "B3_phase_stability": min(mode["phase_min_eigenvalue"] for mode in all_modes) > 0.0,
        "B4_stationary_circulation": max(mode["max_current_divergence"] for mode in all_modes) < B_LIMIT
        and min(mode["current_norm"] for mode in all_modes) > B_LIMIT,
        "B5_conditional_scale_covariance": max(length_errors) < B_LIMIT and max(energy_errors) < B_LIMIT,
    }
    return {
        "families": family_rows,
        "summary": {
            "mode_count": len(all_modes),
            "max_stationarity_residual": max(mode["stationarity_residual"] for mode in all_modes),
            "min_radial_hessian": min(mode["radial_hessian"] for mode in all_modes),
            "min_energy_excess_at_one_percent": min(
                min(mode["energy_below_star"], mode["energy_above_star"]) - mode["energy_star"]
                for mode in all_modes
            ),
            "min_phase_eigenvalue": min(mode["phase_min_eigenvalue"] for mode in all_modes),
            "max_current_divergence": max(mode["max_current_divergence"] for mode in all_modes),
            "min_current_norm": min(mode["current_norm"] for mode in all_modes),
            "max_scale_length_relative_residual": max(length_errors),
            "max_scale_energy_relative_residual": max(energy_errors),
        },
        "gates": gates,
        "stage_pass": all(gates.values()),
    }


def _recompute_mass_selection(arithmetic: dict[str, Any]) -> dict[str, Any]:
    phi_records = [(row["yang_winding"], row["yin_winding"]) for row in arithmetic["phi_records"]]
    stable_energies: list[tuple[int, int, float]] = []
    primitive_count = 0
    for p in range(1, PRIMITIVE_P_LIMIT + 1):
        for q_winding in range(1, PRIMITIVE_Q_LIMIT + 1):
            if math.gcd(p, q_winding) != 1:
                continue
            primitive_count += 1
            mode = _evaluate_mode(p, q_winding, PHI)
            if all(mode["stability_gates"].values()):
                stable_energies.append((p, q_winding, mode["energy_star"]))
    h_minimum = min(energy for _, _, energy in stable_energies)
    counts: dict[int, int] = {}
    for _, _, energy in stable_energies:
        cell = math.floor(math.log(energy / h_minimum) / math.log(PHI))
        counts[cell] = counts.get(cell, 0) + 1
    occupied_cells = [{"cell": cell, "stable_mode_count": count} for cell, count in sorted(counts.items())]
    c1 = all(cell["stable_mode_count"] == 1 for cell in occupied_cells)

    anchor_values = {coupling: _h_star(*ANCHOR, PHI, k_delta=coupling) for coupling in COUPLING_ARMS}
    sensitivity = []
    for p, q_winding in phi_records:
        arms = []
        for coupling in COUPLING_ARMS:
            energy = _h_star(p, q_winding, PHI, k_delta=coupling)
            arms.append(
                {
                    "k_delta": coupling,
                    "energy_star": energy,
                    "relative_rung": math.log(energy / anchor_values[coupling]) / math.log(PHI),
                }
            )
        rung_values = [arm["relative_rung"] for arm in arms]
        sensitivity.append(
            {
                "yang_winding": p,
                "yin_winding": q_winding,
                "arms": arms,
                "span": max(rung_values) - min(rung_values),
            }
        )
    maximum_span = max(row["span"] for row in sensitivity)
    c2 = maximum_span <= C2_LIMIT

    branch = phi_records[phi_records.index(ANCHOR) :]
    branch_energies = [_h_star(p, q_winding, PHI) for p, q_winding in branch]
    ratios = []
    for index, (left, right) in enumerate(zip(branch_energies, branch_energies[1:])):
        ratio = right / left
        ratios.append(
            {
                "from": {"yang_winding": branch[index][0], "yin_winding": branch[index][1]},
                "to": {"yang_winding": branch[index + 1][0], "yin_winding": branch[index + 1][1]},
                "energy_ratio": ratio,
                "relative_residual": _relative_error(ratio, PHI),
            }
        )
    coordinates = []
    for label, ((p, q_winding), energy) in enumerate(zip(branch, branch_energies)):
        relative_rung = math.log(energy / branch_energies[0]) / math.log(PHI)
        coordinates.append(
            {
                "yang_winding": p,
                "yin_winding": q_winding,
                "relative_rung": relative_rung,
                "integer_label": label,
                "label_distance": abs(relative_rung - label),
            }
        )
    c3 = max(row["relative_residual"] for row in ratios) < C34_LIMIT
    c4 = max(row["label_distance"] for row in coordinates[1:]) < C34_LIMIT
    gates = {
        "C1_unique_mode_sufficiency": c1,
        "C2_coefficient_independence": c2,
        "C3_asymptotic_phi_spacing": c3,
        "C4_in_cell_collapse": c4,
    }
    return {
        "topological_multiplicity": {
            "primitive_mode_count": primitive_count,
            "stable_primitive_mode_count": len(stable_energies),
            "minimum_energy_star": h_minimum,
            "occupied_cells": occupied_cells,
            "max_stable_modes_per_cell": max(cell["stable_mode_count"] for cell in occupied_cells),
        },
        "constitutive_sensitivity": {
            "anchor": {"yang_winding": ANCHOR[0], "yin_winding": ANCHOR[1]},
            "k_delta_arms": list(COUPLING_ARMS),
            "records": sensitivity,
            "maximum_span": maximum_span,
            "threshold": C2_LIMIT,
        },
        "fibonacci_skeleton": {
            "branch": [{"yang_winding": p, "yin_winding": q_winding} for p, q_winding in branch],
            "energy_ratios": ratios,
            "rung_coordinates": coordinates,
            "maximum_ratio_relative_residual": max(row["relative_residual"] for row in ratios),
            "maximum_label_distance": max(row["label_distance"] for row in coordinates[1:]),
        },
        "gates": gates,
        "skeleton_decision": "SUPPORTS" if c3 and c4 else "DOES NOT SUPPORT",
        "unique_mass_position_decision": "SUPPORTS" if c1 and c2 else "CONTRADICTS",
    }


def _manifest() -> dict[str, dict[str, str]]:
    return {
        "protocol": {"path": PROTOCOL_PATH.relative_to(ROOT).as_posix(), "sha256": _digest(PROTOCOL_PATH)},
        "primary": {"path": PRIMARY_PATH.relative_to(ROOT).as_posix(), "sha256": _digest(PRIMARY_PATH)},
        "verifier": {"path": VERIFIER_PATH.relative_to(ROOT).as_posix(), "sha256": _digest(VERIFIER_PATH)},
    }


def _provisional(quality: dict[str, bool], arithmetic: dict[str, Any], loop: dict[str, Any], mass: dict[str, Any]) -> dict[str, str]:
    q14 = all(quality[name] for name in ("Q1_finite", "Q2_closed_forms", "Q3_deterministic", "Q4_source_record"))
    if not q14:
        return {
            "closed_qi_loop_skeleton": "INCONCLUSIVE: primary quality gate failure",
            "unique_mass_positions": "INCONCLUSIVE: primary quality gate failure",
        }
    skeleton = (
        "PENDING Q5: EMERGES CONDITIONAL"
        if arithmetic["stage_pass"] and loop["stage_pass"] and mass["gates"]["C3_asymptotic_phi_spacing"] and mass["gates"]["C4_in_cell_collapse"]
        else "PENDING Q5: DOES NOT EMERGE"
    )
    if arithmetic["stage_pass"] and loop["stage_pass"] and all(mass["gates"].values()):
        unique = "PENDING Q5: EMERGES CONDITIONAL"
    elif arithmetic["stage_pass"] and loop["stage_pass"] and (
        not mass["gates"]["C1_unique_mode_sufficiency"]
        or not mass["gates"]["C2_coefficient_independence"]
    ):
        unique = "PENDING Q5: DOES NOT EMERGE"
    else:
        unique = "PENDING Q5: INCONCLUSIVE"
    return {"closed_qi_loop_skeleton": skeleton, "unique_mass_positions": unique}


def _compare(actual: Any, expected: Any, path: str, differences: list[dict[str, str]], counts: dict[str, int]) -> None:
    if isinstance(expected, bool):
        counts["boolean_values_checked"] += 1
        if not isinstance(actual, bool) or actual != expected:
            differences.append({"path": path, "expected": repr(expected), "actual": repr(actual)})
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        counts["finite_scalars_checked"] += 1
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            differences.append({"path": path, "expected": repr(expected), "actual": repr(actual)})
        elif not math.isfinite(float(actual)) or abs(float(actual) - float(expected)) > 1.0e-12 * max(1.0, abs(float(expected))):
            differences.append({"path": path, "expected": repr(expected), "actual": repr(actual)})
        return
    if isinstance(expected, str):
        if actual != expected:
            differences.append({"path": path, "expected": repr(expected), "actual": repr(actual)})
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            differences.append({"path": path, "expected": f"list[{len(expected)}]", "actual": repr(actual)})
            return
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            _compare(actual_item, expected_item, f"{path}[{index}]", differences, counts)
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            differences.append({"path": path, "expected": repr(sorted(expected)), "actual": repr(sorted(actual) if isinstance(actual, dict) else actual)})
            return
        for key in sorted(expected):
            _compare(actual[key], expected[key], f"{path}.{key}", differences, counts)
        return
    differences.append({"path": path, "expected": repr(expected), "actual": repr(actual)})


def _combined_verdicts(quality: dict[str, bool], arithmetic: dict[str, Any], loop: dict[str, Any], mass: dict[str, Any]) -> dict[str, str]:
    if not all(quality.values()):
        return {
            "closed_qi_loop_skeleton": "INCONCLUSIVE",
            "unique_mass_positions": "INCONCLUSIVE",
        }
    if arithmetic["stage_pass"] and loop["stage_pass"] and mass["gates"]["C3_asymptotic_phi_spacing"] and mass["gates"]["C4_in_cell_collapse"]:
        skeleton = "EMERGES CONDITIONAL"
    else:
        skeleton = "DOES NOT EMERGE"
    if arithmetic["stage_pass"] and loop["stage_pass"] and all(mass["gates"].values()):
        unique = "EMERGES CONDITIONAL"
    elif arithmetic["stage_pass"] and loop["stage_pass"] and (
        not mass["gates"]["C1_unique_mode_sufficiency"]
        or not mass["gates"]["C2_coefficient_independence"]
    ):
        unique = "DOES NOT EMERGE"
    else:
        unique = "INCONCLUSIVE"
    return {"closed_qi_loop_skeleton": skeleton, "unique_mass_positions": unique}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} RUNS_DIR/results.json", file=sys.stderr)
        return 2
    receipt_path = Path(argv[1]).resolve()
    actual = json.loads(receipt_path.read_text(encoding="utf-8"))
    arithmetic = _recompute_arithmetic()
    loop = _recompute_loop(arithmetic)
    mass = _recompute_mass_selection(arithmetic)
    sources = _manifest()
    closed_forms = [
        gate
        for family in loop["families"]
        for mode in family["modes"]
        for gate in mode["closed_form_gates"].values()
    ]
    expected_quality = {
        "Q1_finite": _finite_tree(actual),
        "Q2_closed_forms": all(closed_forms),
        "Q3_deterministic": True,
        "Q4_source_record": all(len(row["sha256"]) == 64 for row in sources.values()),
    }
    expected_quality["primary_quality_pass"] = all(expected_quality.values())
    expected = {
        "schema_version": 1,
        "experiment": "qi_loop_mass_cascade",
        "sources": sources,
        "constants": {
            "phi": PHI,
            "tension": TENSION,
            "k_y": K_Y,
            "k_i": K_I,
            "k_delta": K_DELTA,
            "record_max_denominator": RECORD_LIMIT,
            "record_separation": RECORD_MARGIN,
            "a1_tolerance": A1_LIMIT,
            "a3_tolerance": A3_LIMIT,
            "a4_minimum": A4_FLOOR,
            "b_tolerance": B_LIMIT,
            "current_cells": RING_POINTS,
            "scale_max_n": SCALE_LAST_N,
            "c2_max_span": C2_LIMIT,
            "c34_tolerance": C34_LIMIT,
            "k_delta_arms": list(COUPLING_ARMS),
            "primitive_p_max": PRIMITIVE_P_LIMIT,
            "primitive_q_max": PRIMITIVE_Q_LIMIT,
        },
        "arithmetic": arithmetic,
        "loop": loop,
        "mass_selection": mass,
        "quality": expected_quality,
        "provisional_verdicts": _provisional(expected_quality, arithmetic, loop, mass),
    }
    actual_without_timestamp = {key: value for key, value in actual.items() if key != "timestamp_utc"}
    differences: list[dict[str, str]] = []
    counts = {"boolean_values_checked": 0, "finite_scalars_checked": 0}
    _compare(actual_without_timestamp, expected, "receipt", differences, counts)
    source_hash_gate = actual.get("sources") == sources
    gate_q5 = source_hash_gate and not differences
    quality = {
        "Q1_finite": bool(actual.get("quality", {}).get("Q1_finite", False)),
        "Q2_closed_forms": bool(actual.get("quality", {}).get("Q2_closed_forms", False)),
        "Q3_deterministic": bool(actual.get("quality", {}).get("Q3_deterministic", False)),
        "Q4_source_record": bool(actual.get("quality", {}).get("Q4_source_record", False)),
        "Q5_independent_recomputation": gate_q5,
    }
    quality["combined_quality_pass"] = all(quality.values())
    verification = {
        "schema_version": 1,
        "experiment": "qi_loop_mass_cascade",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "results_path": receipt_path.as_posix(),
        "source_hash_gate": source_hash_gate,
        "recomputed_gates": {
            "arithmetic": arithmetic["gates"],
            "loop": loop["gates"],
            "mass_selection": mass["gates"],
        },
        "comparison": {**counts, "difference_count": len(differences), "differences": differences},
        "gate_Q5_independent_recomputation": gate_q5,
        "quality": quality,
        "combined_verdicts": _combined_verdicts(quality, arithmetic, loop, mass),
    }
    output_path = receipt_path.with_name("verification.json")
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(verification, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("Q5", "PASS" if gate_q5 else "FAIL", f"differences={len(differences)}")
    print("COMBINED", verification["combined_verdicts"])
    print(f"RAW {output_path.as_posix()}")
    return 0 if quality["combined_quality_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
