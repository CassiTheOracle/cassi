#!/usr/bin/env python3
"""Independently verify a V3 toroidal coherence survival receipt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

_BASE_PATH = Path(__file__).with_name("verify_toroidal_coherence_survival_v2.py")
_BASE_SPEC = importlib.util.spec_from_file_location("verify_toroidal_coherence_survival_v2", _BASE_PATH)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise ImportError(f"cannot load {_BASE_PATH}")
base = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(base)

PHI = base.PHI
EXPECTED_CONSTANTS = base.EXPECTED_CONSTANTS
EXPECTED_ARMS = base.EXPECTED_ARMS
ROOT = base.ROOT
DIAGNOSTIC = "sector_normalized_phase_v3"

_original_diagnose = base.diagnose
_original_survival = base.survival
_original_evaluate_gates = base.evaluate_gates


def sector_statistics(field: np.ndarray, grid: dict[str, Any], declared_winding: int) -> dict[str, float]:
    sectors = EXPECTED_CONSTANTS["winding_sectors"]
    flat = field.ravel()
    indices = grid["sector"]
    real = np.bincount(indices, weights=np.real(flat), minlength=sectors)
    imag = np.bincount(indices, weights=np.imag(flat), minlength=sectors)
    amplitude = np.bincount(indices, weights=np.abs(flat), minlength=sectors)
    values = real + 1j * imag
    safe_amplitude = np.maximum(amplitude, np.finfo(np.float64).tiny)
    phasors = values / safe_amplitude
    increments = np.angle(np.roll(phasors, -1) * np.conj(phasors))
    centers = (np.arange(sectors, dtype=np.float64) + 0.5) * (2.0 * math.pi / sectors)
    value_magnitudes = np.abs(values)
    return {
        "winding": float(np.sum(increments) / (2.0 * math.pi)),
        "phase_coherence": float(np.min(np.abs(phasors))),
        "sector_support": float(np.min(amplitude) / max(float(np.mean(amplitude)), 1e-30)),
        "demodulated_coherence": float(abs(np.sum(values * np.exp(-1j * declared_winding * centers))) / max(float(np.sum(amplitude)), 1e-30)),
        "legacy_sector_ratio": float(np.min(value_magnitudes) / max(float(np.mean(value_magnitudes)), 1e-30)),
    }


def diagnose(
    psi_y: np.ndarray,
    psi_i: np.ndarray,
    grid: dict[str, Any],
    g: float,
    time_value: float,
    initial_center: list[float] | None,
) -> dict[str, Any]:
    row = _original_diagnose(psi_y, psi_i, grid, g, time_value, initial_center)
    stats_y = sector_statistics(psi_y, grid, EXPECTED_CONSTANTS["yang_winding"])
    stats_i = sector_statistics(psi_i, grid, EXPECTED_CONSTANTS["yin_winding"])
    row.update(
        winding_y=stats_y["winding"],
        winding_i=stats_i["winding"],
        coherence_y=stats_y["phase_coherence"],
        coherence_i=stats_i["phase_coherence"],
        phase_coherence_y=stats_y["phase_coherence"],
        phase_coherence_i=stats_i["phase_coherence"],
        sector_support_y=stats_y["sector_support"],
        sector_support_i=stats_i["sector_support"],
        demodulated_coherence_y=stats_y["demodulated_coherence"],
        demodulated_coherence_i=stats_i["demodulated_coherence"],
        legacy_sector_ratio_y=stats_y["legacy_sector_ratio"],
        legacy_sector_ratio_i=stats_i["legacy_sector_ratio"],
    )
    return row


def survival(metrics: list[dict[str, Any]]) -> dict[str, bool]:
    gates = _original_survival(metrics)
    gates["S1_winding"] = all(
        abs(row["winding_y"] - 2.0) <= 0.25
        and abs(row["winding_i"] + 3.0) <= 0.25
        and row["phase_coherence_y"] >= 0.50
        and row["phase_coherence_i"] >= 0.50
        and row["demodulated_coherence_y"] >= 0.50
        and row["demodulated_coherence_i"] >= 0.50
        and row["sector_support_y"] >= 0.05
        and row["sector_support_i"] >= 0.05
        for row in metrics
    )
    return gates


def initialization_gates(preflight: dict[str, Any]) -> dict[str, bool]:
    closed = preflight["closed_initial"]
    untwisted = preflight["untwisted_initial"]
    scrambled = preflight["scrambled_initial"]
    return {
        "G1": base.analytic_closure_error() <= 1e-12 and preflight["closure_error"] <= 1e-12,
        "G2": (
            abs(closed["winding_y"] - 2.0) <= 0.05
            and abs(closed["winding_i"] + 3.0) <= 0.05
            and closed["phase_coherence_y"] >= 0.95
            and closed["phase_coherence_i"] >= 0.95
            and closed["demodulated_coherence_y"] >= 0.95
            and closed["demodulated_coherence_i"] >= 0.95
            and closed["sector_support_y"] >= 0.05
            and closed["sector_support_i"] >= 0.05
            and scrambled["demodulated_coherence_y"] <= 0.50
            and scrambled["demodulated_coherence_i"] <= 0.50
        ),
        "G3": closed["helix_order"] >= 0.80 and closed["opposition"] >= 0.80 and untwisted["helix_order"] <= 0.20,
        "G4": (
            abs(closed["component_ratio"] - PHI) / PHI <= 1e-5
            and abs(closed["virial"]) / (2.0 * closed["kinetic"] + abs(closed["potential"])) <= 1e-5
        ),
    }


def evaluate_gates(
    arms: dict[str, dict[str, Any]], preflight: dict[str, Any], finite_fields: bool
) -> tuple[dict[str, Any], str, list[str], str]:
    gates, _, labels, _ = _original_evaluate_gates(arms, preflight, finite_fields)
    gates.update(initialization_gates(preflight))
    primary = survival(arms["A"]["metrics"])
    gates.update(primary)
    perturb = survival(arms["G"]["metrics"])
    perturb_compare, perturb_differences = base.compare_end(arms["A"]["metrics"][-1], arms["G"]["metrics"][-1], 0.15)
    gates["P1"] = {
        "pass": all(perturb.values()) and perturb_compare,
        "survival": perturb,
        "differences": perturb_differences,
    }
    geometry_ok = all(gates[name] for name in ("G1", "G2", "G3", "G4"))
    quality_ok = gates["Q1"] and all(gates[name]["pass"] for name in ("Q2", "Q3", "Q4", "Q5"))
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


setattr(base, "diagnose", diagnose)
setattr(base, "survival", survival)


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
    if results.get("probe") != "toroidal_coherence_survival_v3":
        errors.append("probe identifier mismatch")
    if results.get("diagnostic") != DIAGNOSTIC or results.get("preflight", {}).get("diagnostic") != DIAGNOSTIC:
        errors.append("diagnostic identifier mismatch")
    if results.get("constants") != EXPECTED_CONSTANTS:
        errors.append("frozen constants mismatch")
    has_arms = "arms" in results
    if has_arms and set(results["arms"]) != set(EXPECTED_ARMS):
        errors.append("arm set mismatch")

    expected_source_paths = {
        "field-experience/toroidal-coherence-survival-pre-registration.md",
        "field-experience/toroidal-coherence-survival-v2-pre-registration.md",
        "field-experience/toroidal-coherence-survival-v3-pre-registration.md",
        "field-experience/toroidal_coherence_survival_v2_probe.py",
        "field-experience/toroidal_coherence_survival_v3_probe.py",
        "field-experience/verify_toroidal_coherence_survival_v2.py",
        "field-experience/verify_toroidal_coherence_survival_v3.py",
    }
    source_hashes: dict[str, str] = {}
    if set(results.get("sources", {})) != expected_source_paths:
        errors.append("source manifest mismatch")
    else:
        for relative, expected_hash in results["sources"].items():
            actual_hash = base.sha256_file(ROOT / relative)
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
        actual_hash = base.sha256_file(fields_path)
        field_hashes[arm_id] = actual_hash
        if actual_hash != stored_arm["fields_sha256"]:
            errors.append(f"arm {arm_id}: field hash mismatch")
        with np.load(fields_path) as receipt:
            times = receipt["times"]
            fields_y = receipt["psi_y"]
            fields_i = receipt["psi_i"]
        if fields_y.shape != fields_i.shape or fields_y.shape[0] != len(times):
            errors.append(f"arm {arm_id}: field shape mismatch")
            continue
        expected_reports = round(EXPECTED_CONSTANTS["t_end"] / EXPECTED_CONSTANTS["report_cadence"]) + 1
        if stored_arm["status"] == "complete" and len(times) != expected_reports:
            errors.append(f"arm {arm_id}: report count mismatch")
        grid = base.make_grid(EXPECTED_ARMS[arm_id]["n"])
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
        base.compare_tree(stored_arm["metrics"], metrics, f"arms.{arm_id}.metrics", errors, max_error)
        recomputed_arms[arm_id] = {
            "config": stored_arm["config"],
            "status": stored_arm["status"],
            "stop_reason": stored_arm["stop_reason"],
            "metrics": metrics,
            "fields_file": stored_arm["fields_file"],
            "fields_sha256": stored_arm["fields_sha256"],
        }

    preflight = results["preflight"]
    if abs(preflight["virial_mass"] - (-2.0 * preflight["k1"] / preflight["w1"])) > 1e-10 * abs(preflight["virial_mass"]):
        errors.append("virial calibration algebra mismatch")
    base.compare_tree(preflight["closure_error"], base.analytic_closure_error(), "preflight.closure_error", errors, max_error)
    if recomputed_arms:
        for key, arm_id in (("closed_initial", "A"), ("untwisted_initial", "C"), ("scrambled_initial", "E")):
            base.compare_tree(preflight[key], recomputed_arms[arm_id]["metrics"][0], f"preflight.{key}", errors, max_error)
        gates, verdict, labels, perturbation_verdict = evaluate_gates(recomputed_arms, preflight, finite_fields)
        base.compare_tree(results["gates"], gates, "gates", errors, max_error)
        if results["verdict"] != verdict:
            errors.append(f"verdict mismatch: {results['verdict']} != {verdict}")
        if results["failure_labels"] != labels:
            errors.append("failure-label mismatch")
        if results["perturbation_verdict"] != perturbation_verdict:
            errors.append("perturbation-verdict mismatch")
    else:
        gates = initialization_gates(preflight)
        verdict = "VALID INITIALIZATION" if all(gates.values()) else "INCONCLUSIVE—INVALID INITIALIZATION"
        labels, perturbation_verdict = [], "UNSCORED"
        base.compare_tree(results.get("gates"), gates, "gates", errors, max_error)
        if verdict == "VALID INITIALIZATION":
            errors.append("valid preflight receipt is missing evolved arms")
        if results.get("verdict") != verdict:
            errors.append(f"preflight verdict mismatch: {results.get('verdict')} != {verdict}")

    verification = {
        "verifier": "independent_numpy_v3_field_recomputation",
        "results_sha256": base.sha256_file(results_path),
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
