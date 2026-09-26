#!/usr/bin/env python3
"""Independently verify a V5 diagnostic-precision toroidal receipt."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

_V4_PATH = Path(__file__).with_name("verify_toroidal_coherence_survival_v4.py")
_V4_SPEC = importlib.util.spec_from_file_location("verify_toroidal_coherence_survival_v4", _V4_PATH)
if _V4_SPEC is None or _V4_SPEC.loader is None:
    raise ImportError(f"cannot load {_V4_PATH}")
v4 = importlib.util.module_from_spec(_V4_SPEC)
_V4_SPEC.loader.exec_module(v4)

ROOT = v4.ROOT
DIAGNOSTIC = "sector_normalized_phase_v5_s4_float64_energy"
EXPECTED_CONSTANTS = dict(v4.EXPECTED_CONSTANTS)
EXPECTED_ARMS = {arm_id: dict(arm) for arm_id, arm in v4.EXPECTED_ARMS.items()}


def energy_terms(
    psi_y: np.ndarray,
    psi_i: np.ndarray,
    grid: dict[str, Any],
    g: float,
    phi_field: np.ndarray | None,
) -> tuple[float, float, float]:
    kinetic = np.float64(0.0)
    for field in (psi_y, psi_i):
        laplacian = np.fft.ifftn(-grid["k2"] * np.fft.fftn(field))
        kinetic = kinetic - np.float64(0.5) * np.sum(np.real(np.conj(field) * laplacian), dtype=np.float64) * grid["dv"]
    if g == 0.0:
        potential = 0.0
    else:
        if phi_field is None:
            phi_field = v4.v3.base.solve_phi(psi_y, psi_i, grid)
        density = np.abs(psi_y) ** 2 + np.abs(psi_i) ** 2
        potential = 0.5 * g * float(np.sum(density * phi_field, dtype=np.float64) * grid["dv"])
    kinetic_value = float(kinetic)
    return kinetic_value, potential, kinetic_value + potential


def diagnose(
    psi_y: np.ndarray,
    psi_i: np.ndarray,
    grid: dict[str, Any],
    g: float,
    time_value: float,
    initial_center: list[float] | None,
) -> dict[str, Any]:
    rho_y = np.abs(psi_y) ** 2
    rho_i = np.abs(psi_i) ** 2
    density = rho_y + rho_i
    mass_y = float(np.sum(rho_y, dtype=np.float64) * grid["dv"])
    mass_i = float(np.sum(rho_i, dtype=np.float64) * grid["dv"])
    mass = mass_y + mass_i
    phi_field = v4.v3.base.solve_phi(psi_y, psi_i, grid) if g != 0.0 else None
    kinetic, potential, energy = energy_terms(psi_y, psi_i, grid, g, phi_field)
    r_fit = float(np.sum(grid["r_perp"] * density, dtype=np.float64) * grid["dv"] / mass)
    d_tor = np.sqrt((grid["r_perp"] - r_fit) ** 2 + grid["z"] ** 2)
    core_fraction = float(np.sum(density[d_tor <= 2.5 * EXPECTED_CONSTANTS["sigma"]], dtype=np.float64) * grid["dv"] / mass)
    theta = np.arctan2(grid["z"], grid["r_perp"] - r_fit)
    carrier = np.exp(1j * (theta - EXPECTED_CONSTANTS["spatial_winding"] * grid["chi"]))
    h_y = np.sum(rho_y * carrier, dtype=np.complex128) * grid["dv"] / mass_y
    h_i = np.sum(rho_i * carrier, dtype=np.complex128) * grid["dv"] / mass_i
    abs_y = float(abs(h_y))
    abs_i = float(abs(h_i))
    opposition: float | None = None
    opposed_helical_moment = 0.0
    if abs_y >= 1e-8 and abs_i >= 1e-8:
        opposition = float(-np.real(h_y * np.conj(h_i)) / (abs_y * abs_i))
        opposed_helical_moment = float(-np.real(h_y * np.conj(h_i)))
    stats_y = v4.sector_statistics(psi_y, grid, EXPECTED_CONSTANTS["yang_winding"])
    stats_i = v4.sector_statistics(psi_i, grid, EXPECTED_CONSTANTS["yin_winding"])
    center = v4.v3.base.periodic_center(density, grid)
    return {
        "time": float(time_value),
        "mass_y": mass_y,
        "mass_i": mass_i,
        "mass": mass,
        "component_ratio": mass_y / mass_i,
        "kinetic": kinetic,
        "potential": potential,
        "energy": energy,
        "virial": 2.0 * kinetic + potential,
        "r_fit": r_fit,
        "core_fraction": core_fraction,
        "winding_y": stats_y["winding"],
        "winding_i": stats_i["winding"],
        "coherence_y": stats_y["phase_coherence"],
        "coherence_i": stats_i["phase_coherence"],
        "phase_coherence_y": stats_y["phase_coherence"],
        "phase_coherence_i": stats_i["phase_coherence"],
        "sector_support_y": stats_y["sector_support"],
        "sector_support_i": stats_i["sector_support"],
        "demodulated_coherence_y": stats_y["demodulated_coherence"],
        "demodulated_coherence_i": stats_i["demodulated_coherence"],
        "legacy_sector_ratio_y": stats_y["legacy_sector_ratio"],
        "legacy_sector_ratio_i": stats_i["legacy_sector_ratio"],
        "helix_y": abs_y,
        "helix_i": abs_i,
        "helix_order": 0.5 * (abs_y + abs_i),
        "opposition": opposition,
        "opposed_helical_moment": opposed_helical_moment,
        "center": center,
        "center_displacement": 0.0 if initial_center is None else v4.v3.base.center_displacement(center, initial_center),
        "max_density": float(np.max(density)),
    }


def compare_converged_end(
    first: dict[str, Any], second: dict[str, Any], limit: float
) -> tuple[bool, dict[str, float]]:
    differences = {
        key: v4.v3.base.relative_difference(first[key], second[key])
        for key in ("r_fit", "core_fraction", "helix_order")
    }
    differences["opposed_helical_moment"] = abs(
        first["opposed_helical_moment"] - second["opposed_helical_moment"]
    )
    return all(value <= limit for value in differences.values()), differences


def evaluate_gates(
    arms: dict[str, dict[str, Any]], preflight: dict[str, Any], finite_fields: bool
) -> tuple[dict[str, Any], str, list[str], str]:
    gates, _, labels, _ = v4.v3.evaluate_gates(arms, preflight, finite_fields)

    q4_pass, q4_differences = compare_converged_end(
        arms["A"]["metrics"][-1], arms["J"]["metrics"][-1], 0.05
    )
    q4_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["J"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["J"]["metrics"][-1]["winding_i"]),
    )
    gates["Q4"] = {
        "pass": q4_pass and q4_winding <= 0.10,
        "differences": q4_differences,
        "winding_difference": q4_winding,
    }

    q5_pass, q5_differences = compare_converged_end(
        arms["A"]["metrics"][-1], arms["I"]["metrics"][-1], 0.10
    )
    q5_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["I"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["I"]["metrics"][-1]["winding_i"]),
    )
    direction_agreement = v4.v3.survival(arms["A"]["metrics"]) == v4.v3.survival(arms["I"]["metrics"])
    gates["Q5"] = {
        "pass": q5_pass and q5_winding <= 0.10 and direction_agreement,
        "differences": q5_differences,
        "winding_difference": q5_winding,
        "direction_agreement": direction_agreement,
    }

    geometry_ok = all(gates[name] for name in ("G1", "G2", "G3", "G4"))
    quality_ok = gates["Q1"] and all(gates[name]["pass"] for name in ("Q2", "Q3", "Q4", "Q5"))
    primary = v4.v3.survival(arms["A"]["metrics"])
    if not geometry_ok:
        verdict, perturbation_verdict = "INCONCLUSIVE—INVALID INITIALIZATION", "UNSCORED"
    elif not quality_ok:
        verdict, perturbation_verdict = "INCONCLUSIVE—NUMERICAL QUALITY", "UNSCORED"
    elif all(primary.values()):
        verdict = "EMERGES CONDITIONALLY"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    else:
        verdict = "DOES NOT EMERGE"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    return gates, verdict, labels, perturbation_verdict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    results_path = args.results.resolve()
    run_dir = results_path.parent
    output_path = run_dir / "verification.json"
    with results_path.open("r", encoding="utf-8") as handle:
        results = json.load(handle)

    errors: list[str] = []
    max_error = [0.0]
    if results.get("probe") != "toroidal_coherence_survival_v5":
        errors.append("probe identifier mismatch")
    if results.get("diagnostic") != DIAGNOSTIC or results.get("preflight", {}).get("diagnostic") != DIAGNOSTIC:
        errors.append("diagnostic identifier mismatch")
    if results.get("dtype") != "complex128/float64" or results.get("preflight", {}).get("precision") != "float64/complex128":
        errors.append("precision identifier mismatch")
    for key, expected in {
        "integrator": "yoshida_triple_jump_s4",
        "energy_dtype": "float64",
        "convergence_metric": "opposed_helical_moment",
    }.items():
        if results.get(key) != expected or results.get("preflight", {}).get(key) != expected:
            errors.append(f"{key} identifier mismatch")
    if results.get("constants") != EXPECTED_CONSTANTS:
        errors.append("frozen constants mismatch")
    if results.get("arms_spec") != list(EXPECTED_ARMS.values()):
        errors.append("arm specification mismatch")
    has_arms = "arms" in results
    if has_arms and set(results["arms"]) != set(EXPECTED_ARMS):
        errors.append("arm set mismatch")

    expected_source_paths = {
        "field-experience/toroidal-coherence-survival-pre-registration.md",
        *(f"field-experience/toroidal-coherence-survival-{version}-pre-registration.md" for version in ("v2", "v3", "v4", "v5")),
        *(f"field-experience/toroidal_coherence_survival_{version}_probe.py" for version in ("v2", "v3", "v4", "v5")),
        *(f"field-experience/verify_toroidal_coherence_survival_{version}.py" for version in ("v2", "v3", "v4", "v5")),
    }
    source_hashes: dict[str, str] = {}
    if set(results.get("sources", {})) != expected_source_paths:
        errors.append("source manifest mismatch")
    else:
        for relative, expected_hash in results["sources"].items():
            actual_hash = v4.v3.base.sha256_file(ROOT / relative)
            source_hashes[relative] = actual_hash
            if actual_hash != expected_hash:
                errors.append(f"source hash mismatch: {relative}")

    recomputed_arms: dict[str, dict[str, Any]] = {}
    field_hashes: dict[str, str] = {}
    finite_fields = True
    for arm_id in sorted(EXPECTED_ARMS):
        stored_arm = results.get("arms", {}).get(arm_id)
        if stored_arm is None:
            continue
        if stored_arm.get("config") != EXPECTED_ARMS[arm_id]:
            errors.append(f"arm {arm_id}: configuration mismatch")
        fields_path = run_dir / stored_arm["fields_file"]
        actual_hash = v4.v3.base.sha256_file(fields_path)
        field_hashes[arm_id] = actual_hash
        if actual_hash != stored_arm["fields_sha256"]:
            errors.append(f"arm {arm_id}: field hash mismatch")
        with np.load(fields_path) as receipt:
            times = receipt["times"]
            fields_y = receipt["psi_y"]
            fields_i = receipt["psi_i"]
        if fields_y.dtype != np.complex128 or fields_i.dtype != np.complex128:
            errors.append(f"arm {arm_id}: field precision mismatch")
        if fields_y.shape != fields_i.shape or fields_y.shape[0] != len(times):
            errors.append(f"arm {arm_id}: field shape mismatch")
            continue
        expected_reports = round(EXPECTED_CONSTANTS["t_end"] / EXPECTED_CONSTANTS["report_cadence"]) + 1
        if stored_arm["status"] == "complete" and len(times) != expected_reports:
            errors.append(f"arm {arm_id}: report count mismatch")
        grid = v4.v3.base.make_grid(EXPECTED_ARMS[arm_id]["n"])
        metrics: list[dict[str, Any]] = []
        initial_center: list[float] | None = None
        for index, time_value in enumerate(times):
            psi_y = fields_y[index]
            psi_i = fields_i[index]
            finite_fields = finite_fields and bool(np.isfinite(psi_y).all() and np.isfinite(psi_i).all())
            row = diagnose(psi_y, psi_i, grid, EXPECTED_ARMS[arm_id]["g"], float(time_value), initial_center)
            if initial_center is None:
                initial_center = row["center"]
                row["center_displacement"] = 0.0
            metrics.append(row)
        for index, (stored_row, recomputed_row) in enumerate(zip(stored_arm["metrics"], metrics)):
            v4.compare_metric(stored_row, recomputed_row, f"arms.{arm_id}.metrics[{index}]", errors, max_error)
        if len(stored_arm["metrics"]) != len(metrics):
            errors.append(f"arm {arm_id}: metric count mismatch")
        recomputed_arms[arm_id] = {
            "config": stored_arm["config"],
            "status": stored_arm["status"],
            "stop_reason": stored_arm["stop_reason"],
            "metrics": metrics,
            "fields_file": stored_arm["fields_file"],
            "fields_sha256": stored_arm["fields_sha256"],
        }

    stored_preflight = results["preflight"]
    if abs(stored_preflight["virial_mass"] - (-2.0 * stored_preflight["k1"] / stored_preflight["w1"])) > 1e-12 * abs(stored_preflight["virial_mass"]):
        errors.append("virial calibration algebra mismatch")
    v4.v3.base.compare_tree(
        stored_preflight["closure_error"],
        v4.v3.base.analytic_closure_error(),
        "preflight.closure_error",
        errors,
        max_error,
    )
    if recomputed_arms:
        recomputed_preflight = {
            **stored_preflight,
            "closure_error": v4.v3.base.analytic_closure_error(),
            "closed_initial": recomputed_arms["A"]["metrics"][0],
            "untwisted_initial": recomputed_arms["C"]["metrics"][0],
            "scrambled_initial": recomputed_arms["E"]["metrics"][0],
        }
        for key in ("closed_initial", "untwisted_initial", "scrambled_initial"):
            v4.compare_metric(stored_preflight[key], recomputed_preflight[key], f"preflight.{key}", errors, max_error)
        gates, verdict, labels, perturbation_verdict = evaluate_gates(recomputed_arms, recomputed_preflight, finite_fields)
        v4.v3.base.compare_tree(results["gates"], gates, "gates", errors, max_error)
        if results["verdict"] != verdict:
            errors.append(f"verdict mismatch: {results['verdict']} != {verdict}")
        if results["failure_labels"] != labels:
            errors.append("failure-label mismatch")
        if results["perturbation_verdict"] != perturbation_verdict:
            errors.append("perturbation-verdict mismatch")
    else:
        gates = v4.v3.initialization_gates(stored_preflight)
        verdict = "VALID INITIALIZATION" if all(gates.values()) else "INCONCLUSIVE—INVALID INITIALIZATION"
        labels, perturbation_verdict = [], "UNSCORED"
        v4.v3.base.compare_tree(results.get("gates"), gates, "gates", errors, max_error)
        if verdict == "VALID INITIALIZATION":
            errors.append("valid preflight receipt is missing evolved arms")
        if results.get("verdict") != verdict:
            errors.append(f"preflight verdict mismatch: {results.get('verdict')} != {verdict}")

    verification = {
        "verifier": "independent_numpy_v5_s4_float64_recomputation",
        "results_sha256": v4.v3.base.sha256_file(results_path),
        "source_hashes": source_hashes,
        "field_hashes": field_hashes,
        "finite_fields": finite_fields,
        "max_normalized_metric_error": max_error[0],
        "recomputed_gates": gates,
        "recomputed_verdict": verdict,
        "recomputed_failure_labels": labels,
        "recomputed_perturbation_verdict": perturbation_verdict,
        "errors": errors,
        "pass": not errors,
    }
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(verification, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(verification, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
