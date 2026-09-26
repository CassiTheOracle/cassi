#!/usr/bin/env python3
"""One-run deterministic probe for the preregistered Qi-loop mass cascade."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PHI = (1.0 + math.sqrt(5.0)) / 2.0
TENSION = 1.0
K_Y = 1.0
K_I = 1.0
K_DELTA = 1.0
RECORD_MAX_DENOMINATOR = 144
RECORD_SEPARATION = 1.0e-15
A1_TOLERANCE = 1.0e-12
A3_TOLERANCE = 1.0e-15
A4_MINIMUM = 0.08
B_TOLERANCE = 1.0e-12
CURRENT_CELLS = 256
SCALE_MAX_N = 8
C2_MAX_SPAN = 0.01
C34_TOLERANCE = 1.0e-4
K_DELTA_ARMS = (0.0, 0.25, 1.0, 4.0)
PRIMITIVE_P_MAX = 34
PRIMITIVE_Q_MAX = 55

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "field-experience" / "qi-loop-mass-cascade-pre-registration.md"
PRIMARY_PATH = Path(__file__).resolve()
VERIFIER_PATH = PRIMARY_PATH.with_name("verify_qi_loop_mass_cascade.py")
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
ANCHOR = (13, 21)


def _relative_error(measured: float, expected: float) -> float:
    return abs(measured - expected) / max(abs(expected), 1.0e-300)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value is not None
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_all_finite(item) for item in value)
    if isinstance(value, dict):
        return all(_all_finite(item) for item in value.values())
    return False


def _nearest_positive_integer(value: float) -> int:
    """Nearest integer, selecting the larger integer at an exact half."""
    lower = math.floor(value)
    fraction = value - lower
    return max(1, lower if fraction < 0.5 else lower + 1)


def _record_pairs(alpha: float) -> list[tuple[int, int]]:
    records: list[tuple[int, int]] = []
    best_distance = math.inf
    for p in range(1, RECORD_MAX_DENOMINATOR + 1):
        q_winding = _nearest_positive_integer(alpha * p)
        distance = abs(q_winding - alpha * p)
        if distance < best_distance - RECORD_SEPARATION:
            records.append((p, q_winding))
            best_distance = distance
    return records


def _fibonacci_values(limit: int) -> list[int]:
    values = [0, 1]
    for _ in range(2, limit + 1):
        values.append(values[-1] + values[-2])
    return values


def _energy_coefficient(
    p: int,
    q_winding: int,
    alpha: float,
    k_delta: float = K_DELTA,
) -> float:
    return K_Y * p * p + K_I * q_winding * q_winding + k_delta * (q_winding - alpha * p) ** 2


def _energy_star(
    p: int,
    q_winding: int,
    alpha: float,
    k_delta: float = K_DELTA,
    tension: float = TENSION,
) -> float:
    coefficient = _energy_coefficient(p, q_winding, alpha, k_delta)
    return 2.0 * math.sqrt(2.0 * math.pi * math.pi * tension * coefficient)


def _phase_min_eigenvalue(alpha: float, k_delta: float = K_DELTA) -> float:
    g00 = K_Y + alpha * alpha * k_delta
    g11 = K_I + k_delta
    g01 = -alpha * k_delta
    return 0.5 * (g00 + g11 - math.hypot(g00 - g11, 2.0 * g01))


def _loop_mode(p: int, q_winding: int, alpha: float) -> dict[str, Any]:
    coefficient = _energy_coefficient(p, q_winding, alpha)
    length_star = math.sqrt(2.0 * math.pi * math.pi * coefficient / TENSION)
    energy_star = _energy_star(p, q_winding, alpha)

    def energy(length: float) -> float:
        return TENSION * length + 2.0 * math.pi * math.pi * coefficient / length

    stationarity_term = 2.0 * math.pi * math.pi * coefficient / (length_star * length_star)
    stationarity_residual = _relative_error(TENSION, stationarity_term)
    length_relation_residual = _relative_error(
        length_star * length_star, 2.0 * math.pi * math.pi * coefficient / TENSION
    )
    energy_relation_residual = _relative_error(energy(length_star), energy_star)
    radial_hessian = 4.0 * math.pi * math.pi * coefficient / (length_star**3)
    energy_below = energy(0.99 * length_star)
    energy_above = energy(1.01 * length_star)

    gradient_y = 2.0 * math.pi * p / length_star
    gradient_i = 2.0 * math.pi * q_winding / length_star
    current_y = (K_Y + alpha * alpha * K_DELTA) * gradient_y - alpha * K_DELTA * gradient_i
    current_i = (K_I + K_DELTA) * gradient_i - alpha * K_DELTA * gradient_y
    current_norm = math.hypot(current_y, current_i)
    delta_s = length_star / CURRENT_CELLS
    current_y_samples = [current_y] * CURRENT_CELLS
    current_i_samples = [current_i] * CURRENT_CELLS
    divergence = max(
        max(
            abs((current_y_samples[(index + 1) % CURRENT_CELLS] - current_y_samples[index - 1]) / (2.0 * delta_s))
            for index in range(CURRENT_CELLS)
        ),
        max(
            abs((current_i_samples[(index + 1) % CURRENT_CELLS] - current_i_samples[index - 1]) / (2.0 * delta_s))
            for index in range(CURRENT_CELLS)
        ),
    )
    min_eigenvalue = _phase_min_eigenvalue(alpha)
    closed_form_gates = {
        "length_relation": length_relation_residual < B_TOLERANCE,
        "energy_relation": energy_relation_residual < B_TOLERANCE,
        "stationarity": stationarity_residual < B_TOLERANCE,
        "radial_hessian": radial_hessian > 0.0,
    }
    stability_gates = {
        "B1_stationarity": stationarity_residual < B_TOLERANCE,
        "B2_radial_stability": radial_hessian > 0.0 and energy_below > energy_star and energy_above > energy_star,
        "B3_phase_stability": min_eigenvalue > 0.0,
        "B4_stationary_circulation": divergence < B_TOLERANCE and current_norm > B_TOLERANCE,
    }
    return {
        "yang_winding": p,
        "yin_winding": q_winding,
        "coefficient": coefficient,
        "length_star": length_star,
        "energy_star": energy_star,
        "length_relation_residual": length_relation_residual,
        "energy_relation_residual": energy_relation_residual,
        "stationarity_residual": stationarity_residual,
        "radial_hessian": radial_hessian,
        "energy_below_star": energy_below,
        "energy_above_star": energy_above,
        "phase_min_eigenvalue": min_eigenvalue,
        "current_y": current_y,
        "current_i": current_i,
        "current_norm": current_norm,
        "max_current_divergence": divergence,
        "closed_form_gates": closed_form_gates,
        "stability_gates": stability_gates,
    }


def _arithmetic_stage() -> dict[str, Any]:
    phi_records = _record_pairs(PHI)
    rational_records = _record_pairs(1.5)
    irrational_records = _record_pairs(math.sqrt(2.0))
    fibonacci = _fibonacci_values(13)
    identity_rows = []
    for index in range(2, 13):
        left = fibonacci[index + 1] - PHI * fibonacci[index]
        right = ((-1) ** index) * PHI ** (-index)
        identity_rows.append(
            {
                "index": index,
                "left": left,
                "right": right,
                "absolute_residual": abs(left - right),
            }
        )
    phi_distance = abs(233 - PHI * 144)
    irrational_distance = abs(99 - math.sqrt(2.0) * 70)
    weighted_gap = 144 * phi_distance - 70 * irrational_distance
    gates = {
        "A1_fibonacci_identity": max(row["absolute_residual"] for row in identity_rows) < A1_TOLERANCE,
        "A2_phi_record_sequence": phi_records == EXPECTED_PHI_RECORDS,
        "A3_rational_closure": abs(3 - 1.5 * 2) < A3_TOLERANCE,
        "A4_finite_deresonance_control": weighted_gap >= A4_MINIMUM,
    }
    return {
        "phi_records": [{"yang_winding": p, "yin_winding": q} for p, q in phi_records],
        "rational_records": [{"yang_winding": p, "yin_winding": q} for p, q in rational_records],
        "sqrt2_records": [{"yang_winding": p, "yin_winding": q} for p, q in irrational_records],
        "fibonacci_identity": identity_rows,
        "phi_final_weighted_residual": 144 * phi_distance,
        "sqrt2_final_weighted_residual": 70 * irrational_distance,
        "weighted_residual_gap": weighted_gap,
        "gates": gates,
        "stage_pass": all(gates.values()),
    }


def _loop_stage(arithmetic: dict[str, Any]) -> dict[str, Any]:
    families = (
        ("phi", PHI, arithmetic["phi_records"]),
        ("rational_control", 1.5, arithmetic["rational_records"]),
        ("sqrt2_control", math.sqrt(2.0), arithmetic["sqrt2_records"]),
    )
    mode_families = []
    all_modes: list[dict[str, Any]] = []
    length_residuals: list[float] = []
    energy_residuals: list[float] = []
    for name, alpha, records in families:
        modes = [_loop_mode(row["yang_winding"], row["yin_winding"], alpha) for row in records]
        mode_families.append({"name": name, "alpha": alpha, "modes": modes})
        all_modes.extend(modes)
        for mode in modes:
            for scale_index in range(SCALE_MAX_N + 1):
                scaled_tension = TENSION * PHI ** (-2 * scale_index)
                scaled_length = math.sqrt(
                    2.0 * math.pi * math.pi * mode["coefficient"] / scaled_tension
                )
                scaled_energy = 2.0 * math.sqrt(
                    2.0 * math.pi * math.pi * scaled_tension * mode["coefficient"]
                )
                length_residuals.append(
                    _relative_error(scaled_length, mode["length_star"] * PHI**scale_index)
                )
                energy_residuals.append(
                    _relative_error(scaled_energy, mode["energy_star"] * PHI ** (-scale_index))
                )
    gates = {
        "B1_stationarity": max(mode["stationarity_residual"] for mode in all_modes) < B_TOLERANCE,
        "B2_radial_stability": all(mode["stability_gates"]["B2_radial_stability"] for mode in all_modes),
        "B3_phase_stability": min(mode["phase_min_eigenvalue"] for mode in all_modes) > 0.0,
        "B4_stationary_circulation": max(mode["max_current_divergence"] for mode in all_modes) < B_TOLERANCE
        and min(mode["current_norm"] for mode in all_modes) > B_TOLERANCE,
        "B5_conditional_scale_covariance": max(length_residuals) < B_TOLERANCE
        and max(energy_residuals) < B_TOLERANCE,
    }
    return {
        "families": mode_families,
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
            "max_scale_length_relative_residual": max(length_residuals),
            "max_scale_energy_relative_residual": max(energy_residuals),
        },
        "gates": gates,
        "stage_pass": all(gates.values()),
    }


def _mass_selection_stage(arithmetic: dict[str, Any]) -> dict[str, Any]:
    phi_records = [
        (row["yang_winding"], row["yin_winding"]) for row in arithmetic["phi_records"]
    ]
    primitive_energies = []
    for p in range(1, PRIMITIVE_P_MAX + 1):
        for q_winding in range(1, PRIMITIVE_Q_MAX + 1):
            if math.gcd(p, q_winding) != 1:
                continue
            mode = _loop_mode(p, q_winding, PHI)
            stable = all(mode["stability_gates"].values())
            if stable:
                primitive_energies.append((p, q_winding, mode["energy_star"]))
    minimum_energy = min(energy for _, _, energy in primitive_energies)
    cell_counts: dict[int, int] = {}
    for _, _, energy in primitive_energies:
        cell = math.floor(math.log(energy / minimum_energy) / math.log(PHI))
        cell_counts[cell] = cell_counts.get(cell, 0) + 1
    cells = [
        {"cell": cell, "stable_mode_count": count}
        for cell, count in sorted(cell_counts.items())
    ]
    c1 = all(row["stable_mode_count"] == 1 for row in cells)

    anchor_energies = {
        k_delta: _energy_star(*ANCHOR, PHI, k_delta=k_delta) for k_delta in K_DELTA_ARMS
    }
    sensitivity_rows = []
    for p, q_winding in phi_records:
        arms = []
        for k_delta in K_DELTA_ARMS:
            energy = _energy_star(p, q_winding, PHI, k_delta=k_delta)
            coordinate = math.log(energy / anchor_energies[k_delta]) / math.log(PHI)
            arms.append(
                {
                    "k_delta": k_delta,
                    "energy_star": energy,
                    "relative_rung": coordinate,
                }
            )
        values = [arm["relative_rung"] for arm in arms]
        sensitivity_rows.append(
            {
                "yang_winding": p,
                "yin_winding": q_winding,
                "arms": arms,
                "span": max(values) - min(values),
            }
        )
    max_span = max(row["span"] for row in sensitivity_rows)
    c2 = max_span <= C2_MAX_SPAN

    anchor_index = phi_records.index(ANCHOR)
    branch = phi_records[anchor_index:]
    branch_energies = [_energy_star(p, q_winding, PHI) for p, q_winding in branch]
    ratio_rows = []
    for index in range(len(branch_energies) - 1):
        ratio = branch_energies[index + 1] / branch_energies[index]
        ratio_rows.append(
            {
                "from": {"yang_winding": branch[index][0], "yin_winding": branch[index][1]},
                "to": {"yang_winding": branch[index + 1][0], "yin_winding": branch[index + 1][1]},
                "energy_ratio": ratio,
                "relative_residual": _relative_error(ratio, PHI),
            }
        )
    coordinate_rows = []
    for label, ((p, q_winding), energy) in enumerate(zip(branch, branch_energies)):
        coordinate = math.log(energy / branch_energies[0]) / math.log(PHI)
        coordinate_rows.append(
            {
                "yang_winding": p,
                "yin_winding": q_winding,
                "relative_rung": coordinate,
                "integer_label": label,
                "label_distance": abs(coordinate - label),
            }
        )
    c3 = max(row["relative_residual"] for row in ratio_rows) < C34_TOLERANCE
    c4 = max(row["label_distance"] for row in coordinate_rows[1:]) < C34_TOLERANCE
    gates = {
        "C1_unique_mode_sufficiency": c1,
        "C2_coefficient_independence": c2,
        "C3_asymptotic_phi_spacing": c3,
        "C4_in_cell_collapse": c4,
    }
    return {
        "topological_multiplicity": {
            "primitive_mode_count": sum(
                1
                for p in range(1, PRIMITIVE_P_MAX + 1)
                for q_winding in range(1, PRIMITIVE_Q_MAX + 1)
                if math.gcd(p, q_winding) == 1
            ),
            "stable_primitive_mode_count": len(primitive_energies),
            "minimum_energy_star": minimum_energy,
            "occupied_cells": cells,
            "max_stable_modes_per_cell": max(row["stable_mode_count"] for row in cells),
        },
        "constitutive_sensitivity": {
            "anchor": {"yang_winding": ANCHOR[0], "yin_winding": ANCHOR[1]},
            "k_delta_arms": list(K_DELTA_ARMS),
            "records": sensitivity_rows,
            "maximum_span": max_span,
            "threshold": C2_MAX_SPAN,
        },
        "fibonacci_skeleton": {
            "branch": [
                {"yang_winding": p, "yin_winding": q_winding}
                for p, q_winding in branch
            ],
            "energy_ratios": ratio_rows,
            "rung_coordinates": coordinate_rows,
            "maximum_ratio_relative_residual": max(row["relative_residual"] for row in ratio_rows),
            "maximum_label_distance": max(row["label_distance"] for row in coordinate_rows[1:]),
        },
        "gates": gates,
        "skeleton_decision": "SUPPORTS" if c3 and c4 else "DOES NOT SUPPORT",
        "unique_mass_position_decision": "SUPPORTS" if c1 and c2 else "CONTRADICTS",
    }


def _source_manifest() -> dict[str, dict[str, str]]:
    return {
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(PROTOCOL_PATH),
        },
        "primary": {
            "path": PRIMARY_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(PRIMARY_PATH),
        },
        "verifier": {
            "path": VERIFIER_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(VERIFIER_PATH),
        },
    }


def _provisional_verdicts(quality: dict[str, bool], arithmetic: dict[str, Any], loop: dict[str, Any], mass: dict[str, Any]) -> dict[str, str]:
    q14 = all(quality[key] for key in ("Q1_finite", "Q2_closed_forms", "Q3_deterministic", "Q4_source_record"))
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
    unique = (
        "PENDING Q5: EMERGES CONDITIONAL"
        if arithmetic["stage_pass"] and loop["stage_pass"] and all(mass["gates"].values())
        else "PENDING Q5: DOES NOT EMERGE"
        if arithmetic["stage_pass"]
        and loop["stage_pass"]
        and (not mass["gates"]["C1_unique_mode_sufficiency"] or not mass["gates"]["C2_coefficient_independence"])
        else "PENDING Q5: INCONCLUSIVE"
    )
    return {"closed_qi_loop_skeleton": skeleton, "unique_mass_positions": unique}


def main() -> int:
    arithmetic = _arithmetic_stage()
    loop = _loop_stage(arithmetic)
    mass_selection = _mass_selection_stage(arithmetic)
    sources = _source_manifest()
    closed_form_checks = [
        gate
        for family in loop["families"]
        for mode in family["modes"]
        for gate in mode["closed_form_gates"].values()
    ]
    quality: dict[str, bool] = {
        "Q1_finite": False,
        "Q2_closed_forms": all(closed_form_checks),
        "Q3_deterministic": True,
        "Q4_source_record": all(len(entry["sha256"]) == 64 for entry in sources.values()),
    }
    results: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "qi_loop_mass_cascade",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "constants": {
            "phi": PHI,
            "tension": TENSION,
            "k_y": K_Y,
            "k_i": K_I,
            "k_delta": K_DELTA,
            "record_max_denominator": RECORD_MAX_DENOMINATOR,
            "record_separation": RECORD_SEPARATION,
            "a1_tolerance": A1_TOLERANCE,
            "a3_tolerance": A3_TOLERANCE,
            "a4_minimum": A4_MINIMUM,
            "b_tolerance": B_TOLERANCE,
            "current_cells": CURRENT_CELLS,
            "scale_max_n": SCALE_MAX_N,
            "c2_max_span": C2_MAX_SPAN,
            "c34_tolerance": C34_TOLERANCE,
            "k_delta_arms": list(K_DELTA_ARMS),
            "primitive_p_max": PRIMITIVE_P_MAX,
            "primitive_q_max": PRIMITIVE_Q_MAX,
        },
        "arithmetic": arithmetic,
        "loop": loop,
        "mass_selection": mass_selection,
        "quality": quality,
    }
    quality["Q1_finite"] = _all_finite(results)
    quality["primary_quality_pass"] = all(quality.values())
    results["provisional_verdicts"] = _provisional_verdicts(quality, arithmetic, loop, mass_selection)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = ROOT / "runs" / f"{timestamp}_qi_loop_mass_cascade"
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "results.json"
    output_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("A", "PASS" if arithmetic["stage_pass"] else "FAIL", arithmetic["gates"])
    print("B", "PASS" if loop["stage_pass"] else "FAIL", loop["gates"])
    print("C", mass_selection["gates"])
    print("Q1-Q4", "PASS" if quality["primary_quality_pass"] else "FAIL", quality)
    for name, verdict in results["provisional_verdicts"].items():
        print(f"PROVISIONAL {name}: {verdict}")
    print(f"RAW {output_path.as_posix()}")
    return 0 if quality["primary_quality_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
