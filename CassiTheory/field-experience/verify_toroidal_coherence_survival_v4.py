#!/usr/bin/env python3
"""Independently verify a V4 high-precision toroidal survival receipt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

_V3_PATH = Path(__file__).with_name("verify_toroidal_coherence_survival_v3.py")
_V3_SPEC = importlib.util.spec_from_file_location("verify_toroidal_coherence_survival_v3", _V3_PATH)
if _V3_SPEC is None or _V3_SPEC.loader is None:
    raise ImportError(f"cannot load {_V3_PATH}")
v3 = importlib.util.module_from_spec(_V3_SPEC)
_V3_SPEC.loader.exec_module(v3)

ROOT = v3.ROOT
PHI = v3.PHI
DIAGNOSTIC = "sector_normalized_phase_v4_complex128"
EXPECTED_CONSTANTS = {
    **v3.EXPECTED_CONSTANTS,
    "reference_n": 64,
    "dt": 0.0025,
    "state_dtype": "complex128",
}
EXPECTED_ARMS = {
    "A": {"id": "A", "name": "primary_closed", "seed": "closed", "n": 64, "dt": 0.0025, "g": 1.0},
    "B": {"id": "B", "name": "gravity_off", "seed": "closed", "n": 64, "dt": 0.0025, "g": 0.0},
    "C": {"id": "C", "name": "untwisted", "seed": "untwisted", "n": 64, "dt": 0.0025, "g": 1.0},
    "D": {"id": "D", "name": "open_loop", "seed": "open", "n": 64, "dt": 0.0025, "g": 1.0},
    "E": {"id": "E", "name": "scrambled_phase", "seed": "scrambled", "n": 64, "dt": 0.0025, "g": 1.0},
    "F": {"id": "F", "name": "sphere", "seed": "sphere", "n": 64, "dt": 0.0025, "g": 1.0},
    "G": {"id": "G", "name": "perturbed", "seed": "perturbed", "n": 64, "dt": 0.0025, "g": 1.0},
    "H": {"id": "H", "name": "low_resolution", "seed": "closed", "n": 48, "dt": 0.0025, "g": 1.0},
    "I": {"id": "I", "name": "high_resolution", "seed": "closed", "n": 80, "dt": 0.0025, "g": 1.0},
    "J": {"id": "J", "name": "half_dt", "seed": "closed", "n": 64, "dt": 0.00125, "g": 1.0},
}


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
        "sector_support": float(np.min(amplitude) / max(float(np.mean(amplitude)), 1e-300)),
        "demodulated_coherence": float(abs(np.sum(values * np.exp(-1j * declared_winding * centers))) / max(float(np.sum(amplitude)), 1e-300)),
        "legacy_sector_ratio": float(np.min(value_magnitudes) / max(float(np.mean(value_magnitudes)), 1e-300)),
    }


def comparable_metric(row: dict[str, Any], other: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    left, right = dict(row), dict(other)
    left.pop("virial", None)
    right.pop("virial", None)
    if min(float(left.get("helix_order", 0.0)), float(right.get("helix_order", 0.0))) < 1e-4:
        left.pop("opposition", None)
        right.pop("opposition", None)
    return left, right


def compare_metric(
    stored: dict[str, Any], recomputed: dict[str, Any], path: str, errors: list[str], max_error: list[float]
) -> None:
    left, right = comparable_metric(stored, recomputed)
    v3.base.compare_tree(left, right, path, errors, max_error)


setattr(v3, "EXPECTED_CONSTANTS", EXPECTED_CONSTANTS)
setattr(v3, "EXPECTED_ARMS", EXPECTED_ARMS)
setattr(v3, "sector_statistics", sector_statistics)
v3.base.EXPECTED_CONSTANTS = EXPECTED_CONSTANTS
v3.base.EXPECTED_ARMS = EXPECTED_ARMS
v3.base.RTOL = 1e-6
v3.base.ATOL = 1e-8


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
    if results.get("probe") != "toroidal_coherence_survival_v4":
        errors.append("probe identifier mismatch")
    if results.get("diagnostic") != DIAGNOSTIC or results.get("preflight", {}).get("diagnostic") != DIAGNOSTIC:
        errors.append("diagnostic identifier mismatch")
    if results.get("dtype") != "complex128/float64" or results.get("preflight", {}).get("precision") != "float64/complex128":
        errors.append("precision identifier mismatch")
    if results.get("constants") != EXPECTED_CONSTANTS:
        errors.append("frozen constants mismatch")
    if results.get("arms_spec") != list(EXPECTED_ARMS.values()):
        errors.append("arm specification mismatch")
    has_arms = "arms" in results
    if has_arms and set(results["arms"]) != set(EXPECTED_ARMS):
        errors.append("arm set mismatch")

    expected_source_paths = {
        "field-experience/toroidal-coherence-survival-pre-registration.md",
        *(f"field-experience/toroidal-coherence-survival-{version}-pre-registration.md" for version in ("v2", "v3", "v4")),
        *(f"field-experience/toroidal_coherence_survival_{version}_probe.py" for version in ("v2", "v3", "v4")),
        *(f"field-experience/verify_toroidal_coherence_survival_{version}.py" for version in ("v2", "v3", "v4")),
    }
    source_hashes: dict[str, str] = {}
    if set(results.get("sources", {})) != expected_source_paths:
        errors.append("source manifest mismatch")
    else:
        for relative, expected_hash in results["sources"].items():
            actual_hash = v3.base.sha256_file(ROOT / relative)
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
        actual_hash = v3.base.sha256_file(fields_path)
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
        grid = v3.base.make_grid(EXPECTED_ARMS[arm_id]["n"])
        metrics: list[dict[str, Any]] = []
        initial_center: list[float] | None = None
        for index, time_value in enumerate(times):
            psi_y = fields_y[index]
            psi_i = fields_i[index]
            finite_fields = finite_fields and bool(np.isfinite(psi_y).all() and np.isfinite(psi_i).all())
            row = v3.diagnose(psi_y, psi_i, grid, EXPECTED_ARMS[arm_id]["g"], float(time_value), initial_center)
            if initial_center is None:
                initial_center = row["center"]
                row["center_displacement"] = 0.0
            metrics.append(row)
        for index, (stored_row, recomputed_row) in enumerate(zip(stored_arm["metrics"], metrics)):
            compare_metric(stored_row, recomputed_row, f"arms.{arm_id}.metrics[{index}]", errors, max_error)
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
    v3.base.compare_tree(stored_preflight["closure_error"], v3.base.analytic_closure_error(), "preflight.closure_error", errors, max_error)
    if recomputed_arms:
        recomputed_preflight = {
            **stored_preflight,
            "closure_error": v3.base.analytic_closure_error(),
            "closed_initial": recomputed_arms["A"]["metrics"][0],
            "untwisted_initial": recomputed_arms["C"]["metrics"][0],
            "scrambled_initial": recomputed_arms["E"]["metrics"][0],
        }
        for key in ("closed_initial", "untwisted_initial", "scrambled_initial"):
            compare_metric(stored_preflight[key], recomputed_preflight[key], f"preflight.{key}", errors, max_error)
        gates, verdict, labels, perturbation_verdict = v3.evaluate_gates(recomputed_arms, recomputed_preflight, finite_fields)
        v3.base.compare_tree(results["gates"], gates, "gates", errors, max_error)
        if results["verdict"] != verdict:
            errors.append(f"verdict mismatch: {results['verdict']} != {verdict}")
        if results["failure_labels"] != labels:
            errors.append("failure-label mismatch")
        if results["perturbation_verdict"] != perturbation_verdict:
            errors.append("perturbation-verdict mismatch")
    else:
        gates = v3.initialization_gates(stored_preflight)
        verdict = "VALID INITIALIZATION" if all(gates.values()) else "INCONCLUSIVE—INVALID INITIALIZATION"
        labels, perturbation_verdict = [], "UNSCORED"
        v3.base.compare_tree(results.get("gates"), gates, "gates", errors, max_error)
        if verdict == "VALID INITIALIZATION":
            errors.append("valid preflight receipt is missing evolved arms")
        if results.get("verdict") != verdict:
            errors.append(f"preflight verdict mismatch: {results.get('verdict')} != {verdict}")

    verification = {
        "verifier": "independent_numpy_v4_complex128_recomputation",
        "results_sha256": v3.base.sha256_file(results_path),
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
