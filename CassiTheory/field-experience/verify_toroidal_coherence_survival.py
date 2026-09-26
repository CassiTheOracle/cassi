#!/usr/bin/env python3
"""Independently verify a toroidal coherence survival receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
EXPECTED_CONSTANTS: dict[str, Any] = {
    "box_size": 16.0,
    "reference_n": 48,
    "low_n": 32,
    "high_n": 64,
    "dt": 0.005,
    "dt_half": 0.0025,
    "t_end": 4.0,
    "report_cadence": 0.25,
    "major_radius": 4.0,
    "strand_offset": 1.0,
    "sigma": 0.75,
    "spatial_winding": 1,
    "yang_winding": 2,
    "yin_winding": -3,
    "component_ratio": PHI,
    "random_seed": 20260831,
    "winding_sectors": 64,
}
EXPECTED_ARMS = {
    "A": {"id": "A", "name": "closed_primary", "seed": "closed", "n": 48, "dt": 0.005, "g": 1.0},
    "B": {"id": "B", "name": "closed_free", "seed": "closed", "n": 48, "dt": 0.005, "g": 0.0},
    "C": {"id": "C", "name": "untwisted", "seed": "untwisted", "n": 48, "dt": 0.005, "g": 1.0},
    "D": {"id": "D", "name": "open", "seed": "open", "n": 48, "dt": 0.005, "g": 1.0},
    "E": {"id": "E", "name": "scrambled", "seed": "scrambled", "n": 48, "dt": 0.005, "g": 1.0},
    "F": {"id": "F", "name": "sphere", "seed": "sphere", "n": 48, "dt": 0.005, "g": 1.0},
    "G": {"id": "G", "name": "perturbed", "seed": "perturbed", "n": 48, "dt": 0.005, "g": 1.0},
    "H": {"id": "H", "name": "closed_n32", "seed": "closed", "n": 32, "dt": 0.005, "g": 1.0},
    "I": {"id": "I", "name": "closed_n64", "seed": "closed", "n": 64, "dt": 0.005, "g": 1.0},
    "J": {"id": "J", "name": "closed_dt_half", "seed": "closed", "n": 48, "dt": 0.0025, "g": 1.0},
}
ROOT = Path(__file__).resolve().parents[1]
RTOL = 1.0e-3
ATOL = 1.0e-4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_grid(n: int) -> dict[str, Any]:
    box = EXPECTED_CONSTANTS["box_size"]
    dx = box / n
    axis = (np.arange(n, dtype=np.float64) - n / 2) * dx
    x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
    r_perp = np.sqrt(x * x + y * y)
    chi = np.arctan2(y, x)
    k_axis = 2.0 * math.pi * np.fft.fftfreq(n, d=dx)
    kx, ky, kz = np.meshgrid(k_axis, k_axis, k_axis, indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    sector = np.floor((chi + math.pi) * EXPECTED_CONSTANTS["winding_sectors"] / (2.0 * math.pi)).astype(np.int64)
    np.clip(sector, 0, EXPECTED_CONSTANTS["winding_sectors"] - 1, out=sector)
    return {
        "n": n,
        "dx": dx,
        "dv": dx**3,
        "x": x,
        "y": y,
        "z": z,
        "r_perp": r_perp,
        "chi": chi,
        "k2": k2,
        "sector": sector.ravel(),
    }


def solve_phi(psi_y: np.ndarray, psi_i: np.ndarray, grid: dict[str, Any]) -> np.ndarray:
    density = np.abs(psi_y) ** 2 + np.abs(psi_i) ** 2
    source_hat = np.fft.fftn(density - np.mean(density))
    phi_hat = np.zeros_like(source_hat)
    mask = grid["k2"] > 0
    phi_hat[mask] = -source_hat[mask] / grid["k2"][mask]
    return np.fft.ifftn(phi_hat).real


def energy_terms(
    psi_y: np.ndarray,
    psi_i: np.ndarray,
    grid: dict[str, Any],
    g: float,
    phi_field: np.ndarray | None,
) -> tuple[float, float, float]:
    kinetic = 0.0
    for field in (psi_y, psi_i):
        laplacian = np.fft.ifftn(-grid["k2"] * np.fft.fftn(field))
        kinetic += -0.5 * float(np.sum(np.real(np.conj(field) * laplacian)) * grid["dv"])
    if g == 0.0:
        potential = 0.0
    else:
        if phi_field is None:
            phi_field = solve_phi(psi_y, psi_i, grid)
        density = np.abs(psi_y) ** 2 + np.abs(psi_i) ** 2
        potential = 0.5 * g * float(np.sum(density * phi_field) * grid["dv"])
    return kinetic, potential, kinetic + potential


def periodic_center(density: np.ndarray, grid: dict[str, Any]) -> list[float]:
    mass = np.sum(density)
    result: list[float] = []
    for coordinate in (grid["x"], grid["y"], grid["z"]):
        moment = np.sum(density * np.exp(2j * math.pi * coordinate / EXPECTED_CONSTANTS["box_size"])) / mass
        result.append(float(np.angle(moment) * EXPECTED_CONSTANTS["box_size"] / (2.0 * math.pi)))
    return result


def center_displacement(center: list[float], initial: list[float]) -> float:
    box = EXPECTED_CONSTANTS["box_size"]
    delta = [((a - b + box / 2.0) % box) - box / 2.0 for a, b in zip(center, initial)]
    return math.sqrt(sum(value * value for value in delta))


def winding(field: np.ndarray, grid: dict[str, Any]) -> tuple[float, float]:
    sectors = EXPECTED_CONSTANTS["winding_sectors"]
    flat = field.ravel()
    real = np.bincount(grid["sector"], weights=np.real(flat), minlength=sectors)
    imag = np.bincount(grid["sector"], weights=np.imag(flat), minlength=sectors)
    values = real + 1j * imag
    turns = float(np.sum(np.angle(np.roll(values, -1) * np.conj(values))) / (2.0 * math.pi))
    coherence = float(np.min(np.abs(values)) / max(float(np.mean(np.abs(values))), 1e-30))
    return turns, coherence


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
    mass_y = float(np.sum(rho_y) * grid["dv"])
    mass_i = float(np.sum(rho_i) * grid["dv"])
    mass = mass_y + mass_i
    phi_field = solve_phi(psi_y, psi_i, grid) if g != 0.0 else None
    kinetic, potential, energy = energy_terms(psi_y, psi_i, grid, g, phi_field)
    r_fit = float(np.sum(grid["r_perp"] * density) * grid["dv"] / mass)
    d_tor = np.sqrt((grid["r_perp"] - r_fit) ** 2 + grid["z"] ** 2)
    core_fraction = float(np.sum(density[d_tor <= 2.5 * EXPECTED_CONSTANTS["sigma"]]) * grid["dv"] / mass)
    theta = np.arctan2(grid["z"], grid["r_perp"] - r_fit)
    carrier = np.exp(1j * (theta - EXPECTED_CONSTANTS["spatial_winding"] * grid["chi"]))
    h_y = np.sum(rho_y * carrier) * grid["dv"] / mass_y
    h_i = np.sum(rho_i * carrier) * grid["dv"] / mass_i
    abs_y = float(abs(h_y))
    abs_i = float(abs(h_i))
    opposition: float | None = None
    if abs_y >= 1e-8 and abs_i >= 1e-8:
        opposition = float(-np.real(h_y * np.conj(h_i)) / (abs_y * abs_i))
    winding_y, coherence_y = winding(psi_y, grid)
    winding_i, coherence_i = winding(psi_i, grid)
    center = periodic_center(density, grid)
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
        "winding_y": winding_y,
        "winding_i": winding_i,
        "coherence_y": coherence_y,
        "coherence_i": coherence_i,
        "helix_y": abs_y,
        "helix_i": abs_i,
        "helix_order": 0.5 * (abs_y + abs_i),
        "opposition": opposition,
        "center": center,
        "center_displacement": 0.0 if initial_center is None else center_displacement(center, initial_center),
        "max_density": float(np.max(density)),
    }


def analytic_closure_error() -> float:
    def point(angle: float, sign: float) -> np.ndarray:
        center = np.array(
            [EXPECTED_CONSTANTS["major_radius"] * math.cos(angle), EXPECTED_CONSTANTS["major_radius"] * math.sin(angle), 0.0]
        )
        radial = np.array([math.cos(angle), math.sin(angle), 0.0])
        vertical = np.array([0.0, 0.0, 1.0])
        offset = sign * EXPECTED_CONSTANTS["strand_offset"] * (
            radial * math.cos(EXPECTED_CONSTANTS["spatial_winding"] * angle)
            + vertical * math.sin(EXPECTED_CONSTANTS["spatial_winding"] * angle)
        )
        return center + offset

    return max(float(np.linalg.norm(point(0.0, sign) - point(2.0 * math.pi, sign))) for sign in (1.0, -1.0))


def relative_difference(a: float, b: float, floor: float = 1e-8) -> float:
    return abs(a - b) / max(abs(a), abs(b), floor)


def survival(metrics: list[dict[str, Any]]) -> dict[str, bool]:
    initial = metrics[0]
    final = metrics[-1]
    s1 = all(
        abs(row["winding_y"] - 2.0) <= 0.25
        and abs(row["winding_i"] + 3.0) <= 0.25
        and row["coherence_y"] >= 0.05
        and row["coherence_i"] >= 0.05
        for row in metrics
    )
    s2 = (
        final["core_fraction"] / initial["core_fraction"] >= 0.75
        and 0.80 <= final["r_fit"] / initial["r_fit"] <= 1.20
        and all(
            0.75 <= row["r_fit"] / initial["r_fit"] <= 1.25
            for row in metrics
            if row["time"] >= 1.0 - 1e-9
        )
        and final["center_displacement"] <= 0.25 * EXPECTED_CONSTANTS["major_radius"]
    )
    s3 = final["helix_order"] / initial["helix_order"] >= 0.70 and final["opposition"] >= 0.70
    return {"S1_winding": s1, "S2_localization": s2, "S3_helix": s3}


def compare_end(first: dict[str, Any], second: dict[str, Any], limit: float) -> tuple[bool, dict[str, float]]:
    differences = {
        key: relative_difference(first[key], second[key])
        for key in ("r_fit", "core_fraction", "helix_order", "opposition")
    }
    return all(value <= limit for value in differences.values()), differences


def evaluate_gates(
    arms: dict[str, dict[str, Any]],
    preflight: dict[str, Any],
    finite_fields: bool,
) -> tuple[dict[str, Any], str, list[str], str]:
    gates: dict[str, Any] = {}
    gates["G1"] = analytic_closure_error() <= 1e-12 and preflight["closure_error"] <= 1e-12
    initial_a = arms["A"]["metrics"][0]
    initial_c = arms["C"]["metrics"][0]
    gates["G2"] = (
        abs(initial_a["winding_y"] - 2.0) <= 0.05
        and abs(initial_a["winding_i"] + 3.0) <= 0.05
        and initial_a["coherence_y"] >= 0.20
        and initial_a["coherence_i"] >= 0.20
    )
    gates["G3"] = initial_a["helix_order"] >= 0.80 and initial_a["opposition"] >= 0.80 and initial_c["helix_order"] <= 0.20
    gates["G4"] = (
        abs(initial_a["component_ratio"] - PHI) / PHI <= 1e-5
        and abs(initial_a["virial"]) / (2.0 * initial_a["kinetic"] + abs(initial_a["potential"])) <= 1e-5
    )
    geometry_ok = all(gates[name] for name in ("G1", "G2", "G3", "G4"))

    gates["Q1"] = finite_fields and all(arm["status"] == "complete" for arm in arms.values())
    q2_details: dict[str, float] = {}
    q3_details: dict[str, float] = {}
    for arm_id, arm in arms.items():
        metrics = arm["metrics"]
        mass0 = metrics[0]["mass"]
        energy0 = metrics[0]["energy"]
        denominator = max(abs(energy0), metrics[0]["kinetic"], 1e-12)
        q2_details[arm_id] = max(abs(row["mass"] - mass0) / mass0 for row in metrics)
        q3_details[arm_id] = max(abs(row["energy"] - energy0) / denominator for row in metrics)
    gates["Q2"] = {"pass": all(value <= 2e-4 for value in q2_details.values()), "max_relative_mass_drift": q2_details}
    gates["Q3"] = {"pass": all(value <= 5e-3 for value in q3_details.values()), "max_relative_energy_drift": q3_details}

    q4_pass, q4_diff = compare_end(arms["A"]["metrics"][-1], arms["J"]["metrics"][-1], 0.05)
    q4_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["J"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["J"]["metrics"][-1]["winding_i"]),
    )
    gates["Q4"] = {"pass": q4_pass and q4_winding <= 0.10, "differences": q4_diff, "winding_difference": q4_winding}

    q5_pass, q5_diff = compare_end(arms["A"]["metrics"][-1], arms["I"]["metrics"][-1], 0.10)
    q5_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["I"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["I"]["metrics"][-1]["winding_i"]),
    )
    direction_agreement = survival(arms["A"]["metrics"]) == survival(arms["I"]["metrics"])
    gates["Q5"] = {
        "pass": q5_pass and q5_winding <= 0.10 and direction_agreement,
        "differences": q5_diff,
        "winding_difference": q5_winding,
        "direction_agreement": direction_agreement,
    }

    primary_survival = survival(arms["A"]["metrics"])
    gates.update(primary_survival)
    perturb_survival = survival(arms["G"]["metrics"])
    p_compare, p_diff = compare_end(arms["A"]["metrics"][-1], arms["G"]["metrics"][-1], 0.15)
    gates["P1"] = {"pass": all(perturb_survival.values()) and p_compare, "survival": perturb_survival, "differences": p_diff}

    quality_ok = (
        gates["Q1"]
        and gates["Q2"]["pass"]
        and gates["Q3"]["pass"]
        and gates["Q4"]["pass"]
        and gates["Q5"]["pass"]
    )
    labels: list[str] = []
    if not primary_survival["S1_winding"]:
        labels.append("UNWINDS")
    initial, final = arms["A"]["metrics"][0], arms["A"]["metrics"][-1]
    if final["core_fraction"] / initial["core_fraction"] < 0.75:
        labels.append("DELOCALIZES")
    radius_ratio = final["r_fit"] / initial["r_fit"]
    if radius_ratio < 0.80:
        labels.append("RADIUS COLLAPSES")
    elif radius_ratio > 1.20:
        labels.append("RADIUS EXPANDS")
    if not primary_survival["S3_helix"]:
        labels.append("HELIX DISSOLVES")
    if final["center_displacement"] > 0.25 * EXPECTED_CONSTANTS["major_radius"]:
        labels.append("DRIFTS")

    if not geometry_ok:
        verdict = "INCONCLUSIVE—INVALID INITIALIZATION"
        perturbation_verdict = "UNSCORED"
    elif not quality_ok:
        verdict = "INCONCLUSIVE—NUMERICAL QUALITY"
        perturbation_verdict = "UNSCORED"
    elif all(primary_survival.values()):
        verdict = "EMERGES CONDITIONALLY"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    else:
        verdict = "DOES NOT EMERGE"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    return gates, verdict, labels, perturbation_verdict


def compare_tree(stored: Any, recomputed: Any, path: str, errors: list[str], max_error: list[float]) -> None:
    if isinstance(stored, dict) and isinstance(recomputed, dict):
        if set(stored) != set(recomputed):
            errors.append(f"{path}: key mismatch")
            return
        for key in stored:
            compare_tree(stored[key], recomputed[key], f"{path}.{key}", errors, max_error)
        return
    if isinstance(stored, list) and isinstance(recomputed, list):
        if len(stored) != len(recomputed):
            errors.append(f"{path}: length mismatch")
            return
        for index, (left, right) in enumerate(zip(stored, recomputed)):
            compare_tree(left, right, f"{path}[{index}]", errors, max_error)
        return
    if stored is None or recomputed is None or isinstance(stored, (bool, str)) or isinstance(recomputed, (bool, str)):
        if stored != recomputed:
            errors.append(f"{path}: {stored!r} != {recomputed!r}")
        return
    if isinstance(stored, (int, float)) and isinstance(recomputed, (int, float)):
        if not math.isfinite(float(stored)) or not math.isfinite(float(recomputed)):
            errors.append(f"{path}: nonfinite numeric value")
            return
        scale = max(abs(float(stored)), abs(float(recomputed)), 1.0)
        normalized = abs(float(stored) - float(recomputed)) / scale
        max_error[0] = max(max_error[0], normalized)
        if abs(float(stored) - float(recomputed)) > ATOL + RTOL * max(abs(float(stored)), abs(float(recomputed))):
            errors.append(f"{path}: {stored} != {recomputed}")
        return
    if stored != recomputed:
        errors.append(f"{path}: {stored!r} != {recomputed!r}")


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
    if results.get("probe") != "toroidal_coherence_survival":
        errors.append("probe identifier mismatch")
    if results.get("constants") != EXPECTED_CONSTANTS:
        errors.append("frozen constants mismatch")
    if set(results.get("arms", {})) != set(EXPECTED_ARMS):
        errors.append("arm set mismatch")

    source_hashes: dict[str, str] = {}
    expected_source_paths = {
        "field-experience/toroidal_coherence_survival_probe.py",
        "field-experience/toroidal-coherence-survival-pre-registration.md",
        "field-experience/verify_toroidal_coherence_survival.py",
    }
    if set(results.get("sources", {})) != expected_source_paths:
        errors.append("source manifest mismatch")
    else:
        for relative, expected_hash in results["sources"].items():
            actual_hash = sha256_file(ROOT / relative)
            source_hashes[relative] = actual_hash
            if actual_hash != expected_hash:
                errors.append(f"source hash mismatch: {relative}")

    recomputed_arms: dict[str, dict[str, Any]] = {}
    field_hashes: dict[str, str] = {}
    finite_fields = True
    for arm_id in sorted(EXPECTED_ARMS):
        stored_arm = results["arms"].get(arm_id)
        if stored_arm is None:
            continue
        if stored_arm.get("config") != EXPECTED_ARMS[arm_id]:
            errors.append(f"arm {arm_id}: configuration mismatch")
        fields_path = run_dir / stored_arm["fields_file"]
        actual_hash = sha256_file(fields_path)
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
        grid = make_grid(EXPECTED_ARMS[arm_id]["n"])
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
        compare_tree(stored_arm["metrics"], metrics, f"arms.{arm_id}.metrics", errors, max_error)
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
    if recomputed_arms:
        compare_tree(preflight["closed_initial"], recomputed_arms["A"]["metrics"][0], "preflight.closed_initial", errors, max_error)
        compare_tree(preflight["untwisted_initial"], recomputed_arms["C"]["metrics"][0], "preflight.untwisted_initial", errors, max_error)
        gates, verdict, labels, perturbation_verdict = evaluate_gates(recomputed_arms, preflight, finite_fields)
        compare_tree(results["gates"], gates, "gates", errors, max_error)
        if results["verdict"] != verdict:
            errors.append(f"verdict mismatch: {results['verdict']} != {verdict}")
        if results["failure_labels"] != labels:
            errors.append("failure-label mismatch")
        if results["perturbation_verdict"] != perturbation_verdict:
            errors.append("perturbation-verdict mismatch")
    else:
        gates, verdict, labels, perturbation_verdict = {}, "UNVERIFIED", [], "UNSCORED"

    verification = {
        "verifier": "independent_numpy_field_recomputation",
        "results_sha256": sha256_file(results_path),
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
