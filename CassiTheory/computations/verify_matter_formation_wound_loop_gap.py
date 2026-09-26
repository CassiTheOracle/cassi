#!/usr/bin/env python3
"""Independently audit the frozen wound-carrier-loop gap receipt.

This program does not import the primary calculator or its tube module. It
reconstructs their declared finite-volume functional from stored arrays.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, Callable

import numpy as np
import scipy
import scipy.linalg as sla
from scipy.interpolate import PchipInterpolator
from scipy.optimize import minimize_scalar


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "runs/20260921_matter_formation_wound_loop_gap_recovery/primary.json"
DEFAULT_OUTPUT = ROOT / "runs/20260921_matter_formation_wound_loop_gap_recovery/independent.json"
PRIMARY_SCHEMA = "cassi.matter-formation.wound-loop-gap.v1"
SCHEMA = "cassi.matter-formation.wound-loop-gap.independent.v1"

DENSITIES = (
    1.75, 1.875, 2.0, 2.25, 2.5, 2.75, 3.0, math.pi, 3.25, 3.5,
    3.75, 4.0, 4.5, 5.0, 6.0, 8.0, 12.0, 24.0, 48.0,
)
REFINEMENT_DENSITIES = (2.0, 4.0, 8.0)
CHARGES = (16.0, 64.0, 128.0, 256.0)
WINDING = 1
SUPPORT_RADIUS = 6.0
MIN_LOOP_RADIUS = 8.0
NORMALIZED_TOL = 5e-9
EIGEN_TOL = 1e-7
PROFILE_RESIDUAL_TOL = 1e-7
GRID_REL_TOL = 5e-4
TAIL_TOL = 1e-4

A_COEF = 1.0 / 16.0
C_PSI = 1.0 / 8.0
K_CX = 1.0
U_C = 1.0
U_RHO = 4.0
B_COEF = 19.0 / 4.0
H_COEF = 2.9598260763447164
GRAD_F = 0.5
GRAD_C = 0.5
TOWNES_MASS = 11.700896
OMEGA_INF = math.sqrt(B_COEF / A_COEF)
WEAK_ATTRACTION = 2.0 * H_COEF * H_COEF / U_RHO - U_C
TOWNES_DENSITY = K_CX * TOWNES_MASS / (2.0 * WEAK_ATTRACTION)

EXPECTED_SOURCES = {
    "protocol": "matter-formation-wound-loop-gap-prereg.md",
    "geometry": "matter_formation_tube_geometry.py",
    "primary": "matter_formation_wound_loop_gap.py",
    "independent": "verify_matter_formation_wound_loop_gap.py",
}


class VerificationError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalized_error(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(1.0, abs(float(left)), abs(float(right)))


def array_error(left: Any, right: Any) -> float:
    lval = np.asarray(left, dtype=np.float64)
    rval = np.asarray(right, dtype=np.float64)
    if lval.shape != rval.shape:
        return float("inf")
    return float(np.max(np.abs(lval - rval) / np.maximum(1.0, np.maximum(np.abs(lval), np.abs(rval)))))


def content_digest(receipt: dict[str, Any]) -> str:
    body = dict(receipt)
    body.pop("content_sha256", None)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha256_bytes(encoded)


def add_check(receipt: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    row = {"name": name, "passed": bool(passed), "detail": detail}
    receipt["checks"].append(row)
    if not passed:
        receipt["failures"].append(name)


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    return False


def profile_grid(row: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    M = int(row["M"])
    rmax = float(row["rmax"])
    dr = rmax / M
    f = np.asarray(row["f"], dtype=np.float64)
    c = np.asarray(row["c"], dtype=np.float64)
    if f.shape != (M,) or c.shape != (M,):
        raise VerificationError(f"profile array shape mismatch at density {row.get('density')}")
    r = (np.arange(M, dtype=np.float64) + 0.5) * dr
    return r, f, c, dr


def reconstruct_profile(row: dict[str, Any]) -> dict[str, float]:
    r, f, c, dr = profile_grid(row)
    M = len(r)
    rf = (np.arange(M, dtype=np.float64) + 1.0) * dr
    rfm = np.concatenate([[0.0], rf[:-1]])
    fe = np.concatenate([f, [1.0]])
    ce = np.concatenate([c, [0.0]])
    potential = (
        (U_RHO / 4.0) * (f * f - 1.0) ** 2
        + (B_COEF - H_COEF + H_COEF * f * f) * c * c
        + (U_C / 2.0) * c ** 4
    )
    energy = 2.0 * math.pi * float(np.sum(r * dr * potential))
    energy += 2.0 * math.pi * GRAD_F * float(np.sum(rf * dr * ((fe[1:] - fe[:-1]) / dr) ** 2))
    energy += 2.0 * math.pi * GRAD_C * float(np.sum(rf * dr * ((ce[1:] - ce[:-1]) / dr) ** 2))
    population = 2.0 * math.pi * float(np.sum(r * dr * c * c))
    width = math.sqrt(float(np.sum(r * dr * c * c * r * r)) / float(np.sum(r * dr * c * c)))
    tail = 2.0 * math.pi * float(np.sum(r[r > SUPPORT_RADIUS] * dr * c[r > SUPPORT_RADIUS] ** 2)) / population

    mu = float(row["multiplier"])
    dVdf = U_RHO * f * (f * f - 1.0) + 2.0 * H_COEF * f * c * c
    dVdc = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) * c + 2.0 * U_C * c ** 3
    flux_f = rf * (fe[1:] - fe[:-1])
    flux_c = rf * (ce[1:] - ce[:-1])
    lap_f = np.concatenate([[0.0], flux_f[:-1]]) - flux_f
    lap_c = np.concatenate([[0.0], flux_c[:-1]]) - flux_c
    res_f = 2.0 * math.pi * (dr * r * dVdf + (2.0 * GRAD_F / dr) * lap_f)
    res_c = (2.0 * math.pi * (dr * r * dVdc + (2.0 * GRAD_C / dr) * lap_c)
             - mu * 4.0 * math.pi * r * dr * c)
    residual = max(float(np.max(np.abs(res_f))), float(np.max(np.abs(res_c))),
                   abs(population - float(row["density"])))
    return {
        "population": population,
        "energy": energy,
        "energy_per_population": energy / population,
        "width_rms": width,
        "f_min": float(np.min(f)),
        "c_core": float(c[0]),
        "tail_fraction_outside_6": tail,
        "residual": residual,
        "dr": dr,
        "rf_last": float(rf[-1]),
        "rfm_last": float(rfm[-1]),
    }


def piecewise_minimum(nodes: np.ndarray, fn: Callable[[float], float]) -> dict[str, Any]:
    candidates: list[tuple[float, float, tuple[float, float]]] = []
    for lo, hi in zip(nodes[:-1], nodes[1:]):
        for point in (float(lo), float(hi)):
            candidates.append((float(fn(point)), point, (float(lo), float(hi))))
        result = minimize_scalar(fn, bounds=(float(lo), float(hi)), method="bounded",
                                 options={"xatol": 1e-11, "maxiter": 200})
        if result.success and math.isfinite(float(result.fun)):
            candidates.append((float(result.fun), float(result.x), (float(lo), float(hi))))
    value, point, bracket = min(candidates, key=lambda item: item[0])
    endpoint = abs(point - float(nodes[0])) < 1e-8 or abs(point - float(nodes[-1])) < 1e-8
    return {"value": value, "density": point, "bracket": list(bracket), "endpoint": endpoint}


def leading_row(charge: float, density: float, energy_per_population: float) -> dict[str, float | bool]:
    auxiliary = charge ** 2 / (4.0 * A_COEF) + 2.0 * math.pi ** 2 * K_CX * density ** 2
    total_population = math.sqrt(auxiliary / energy_per_population)
    length = total_population / density
    mass = 2.0 * math.sqrt(energy_per_population * auxiliary)
    threshold = OMEGA_INF * charge
    return {
        "density": density, "energy_per_population": energy_per_population,
        "auxiliary": auxiliary, "total_population": total_population,
        "length": length, "radius": length / (2.0 * math.pi),
        "mass": mass, "continuum_threshold": threshold,
        "binding_margin": threshold - mass, "bound": mass < threshold,
        "population_curvature": 2.0 * auxiliary / total_population ** 3,
    }


def metric_values(row: dict[str, Any], radius: float) -> tuple[float, float, float]:
    r, _, c, dr = profile_grid(row)
    mask = r <= SUPPORT_RADIUS
    rr = r[mask]
    weights = rr * dr * c[mask] ** 2
    denominator = float(np.sum(weights))
    root = np.sqrt(1.0 - (rr / radius) ** 2)
    eta = float(np.sum(weights / root) / denominator)
    deta = float(np.sum(-weights * rr ** 2 / (radius ** 3 * root ** 3)) / denominator)
    inside = 2.0 * math.pi * denominator
    return eta, deta, inside


def reconstruct_torus(row: dict[str, Any], charge: float, radius: float) -> dict[str, float | bool | str]:
    profile = reconstruct_profile(row)
    density = float(row["density"])
    eta, deta, inside = metric_values(row, radius)
    static = 2.0 * math.pi * radius * profile["energy"]
    twist = math.pi * K_CX * density * eta / radius
    temporal = charge ** 2 / (8.0 * math.pi * A_COEF * radius * density)
    mass = static + twist + temporal
    derivative = (2.0 * math.pi * profile["energy"]
                  + math.pi * K_CX * density * (deta / radius - eta / radius ** 2)
                  - charge ** 2 / (8.0 * math.pi * A_COEF * density * radius ** 2))
    tail = max(0.0, 1.0 - inside / profile["population"])
    return {
        "metric_factor": eta, "metric_factor_derivative": deta,
        "tail_fraction_outside_6": tail, "static_energy": static,
        "twist_energy": twist, "temporal_charge_energy": temporal,
        "mass": mass, "continuum_threshold": OMEGA_INF * charge,
        "binding_margin": OMEGA_INF * charge - mass,
        "bound": mass < OMEGA_INF * charge,
        "radial_derivative": derivative,
        "radial_drive": "toward-smaller-R" if derivative > 0.0 else "toward-larger-R",
    }


def reconstruct_hessian(row: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    r, f, c, dr = profile_grid(row)
    M = len(r)
    rf = (np.arange(M, dtype=np.float64) + 1.0) * dr
    rfm = np.concatenate([[0.0], rf[:-1]])
    mu = float(row["multiplier"])
    d2ff = U_RHO * (3.0 * f * f - 1.0) + 2.0 * H_COEF * c * c
    d2cc = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) + 6.0 * U_C * c * c
    d2fc = 4.0 * H_COEF * f * c
    hessian = np.zeros((2 * M, 2 * M), dtype=np.float64)
    idx = np.arange(M)
    diag_f = 2.0 * math.pi * (dr * r * d2ff + 2.0 * GRAD_F * (rf + rfm) / dr)
    diag_c = (2.0 * math.pi * (dr * r * d2cc + 2.0 * GRAD_C * (rf + rfm) / dr)
              - mu * 4.0 * math.pi * r * dr)
    off_f = 2.0 * math.pi * (-2.0 * GRAD_F * rf[:-1] / dr)
    off_c = 2.0 * math.pi * (-2.0 * GRAD_C * rf[:-1] / dr)
    cross = 2.0 * math.pi * dr * r * d2fc
    hessian[idx, idx] = diag_f
    hessian[M + idx, M + idx] = diag_c
    hessian[idx, M + idx] = cross
    hessian[M + idx, idx] = cross
    hessian[idx[:-1], idx[:-1] + 1] = off_f
    hessian[idx[1:], idx[1:] - 1] = off_f
    hessian[M + idx[:-1], M + idx[:-1] + 1] = off_c
    hessian[M + idx[1:], M + idx[1:] - 1] = off_c
    measure = 2.0 * math.pi * r * dr
    mass = np.diag(np.concatenate([C_PSI * measure, 2.0 * A_COEF * measure]))
    charge_gradient = np.concatenate([np.zeros(M), 4.0 * math.pi * r * dr * c])
    return hessian, mass, charge_gradient, r


def reconstruct_spectrum(row: dict[str, Any]) -> dict[str, Any]:
    hessian, mass, charge_gradient, r = reconstruct_hessian(row)
    M = len(r)
    dr = float(row["dr"])
    tangent = sla.null_space(charge_gradient.reshape(1, -1))
    eigen_0 = sla.eigh(tangent.T @ hessian @ tangent, tangent.T @ mass @ tangent,
                      eigvals_only=True, subset_by_index=(0, 5), driver="gvx")
    modes: dict[str, list[float]] = {"0": eigen_0.tolist()}
    for mode in range(1, 5):
        angular = np.concatenate([
            2.0 * math.pi * GRAD_F * mode ** 2 * dr / r,
            2.0 * math.pi * GRAD_C * mode ** 2 * dr / r,
        ])
        h_mode = 0.5 * hessian + np.diag(angular)
        eigenvalues = sla.eigh(h_mode, 0.5 * mass, eigvals_only=True,
                               subset_by_index=(0, 5), driver="gvx")
        modes[str(mode)] = eigenvalues.tolist()
    translation = modes["1"][0]
    comparison = min(modes[str(mode)][0] for mode in (2, 3, 4))
    non_symmetry = [modes["0"][0], modes["1"][1]] + [modes[str(mode)][0] for mode in (2, 3, 4)]
    return {
        "modes": modes,
        "translation_eigenvalue": translation,
        "translation_soft_ratio": abs(translation) / max(abs(comparison), 1e-300),
        "minimum_non_symmetry_eigenvalue": min(non_symmetry),
        "non_symmetry_positive": min(non_symmetry) > 0.0,
    }


def validate_sources(primary: dict[str, Any], input_path: Path) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    identities = primary.get("identities")
    if not isinstance(identities, dict) or set(identities) != set(EXPECTED_SOURCES):
        return {}, ["identity inventory mismatch"]
    snapshot_dir = input_path.with_suffix(".sources")
    binding: dict[str, Any] = {}
    for name, expected_basename in EXPECTED_SOURCES.items():
        entry = identities[name]
        if not isinstance(entry, dict):
            failures.append(f"identity {name} is not an object")
            continue
        path_text = entry.get("path")
        digest = entry.get("sha256")
        snapshot_name = entry.get("snapshot")
        if not isinstance(path_text, str) or Path(path_text).name != expected_basename:
            failures.append(f"identity {name} path mismatch")
            continue
        if snapshot_name != expected_basename:
            failures.append(f"identity {name} snapshot mismatch")
            continue
        live = (ROOT / path_text).resolve()
        frozen = snapshot_dir / snapshot_name
        if not live.is_file() or not frozen.is_file():
            failures.append(f"identity {name} live or frozen source missing")
            continue
        live_digest = sha256_bytes(live.read_bytes())
        frozen_digest = sha256_bytes(frozen.read_bytes())
        if digest != live_digest or digest != frozen_digest:
            failures.append(f"identity {name} hash mismatch")
        if name == "independent" and live.resolve() != Path(__file__).resolve():
            failures.append("independent identity does not name this verifier")
        binding[name] = {"path": path_text, "declared": digest,
                         "live": live_digest, "frozen": frozen_digest}
    return binding, failures


def compare_fields(actual: dict[str, Any], expected: dict[str, Any], fields: tuple[str, ...],
                   tolerance: float = NORMALIZED_TOL) -> tuple[float, list[str]]:
    worst = 0.0
    failures: list[str] = []
    for field in fields:
        error = normalized_error(float(actual[field]), float(expected[field]))
        worst = max(worst, error)
        if error >= tolerance:
            failures.append(f"{field}: {error:.3e} >= {tolerance:.3e}")
    return worst, failures


def independent_classification(primary: dict[str, Any]) -> str:
    loop_rows = primary["leading_loops"]
    trial = primary["thin_trial"]
    spectrum = primary["transverse_spectrum"]
    bound_loops = [row for row in loop_rows if bool(row["bound"])]
    supported = [row for row in bound_loops if bool(row["geometry_qualified"])
                 and float(row["population_curvature"]) > 0.0]
    if not bound_loops:
        return "NO_BOUND_WOUND_LOOP_IN_SCHEDULE"
    if bool(trial["bound"]) and bool(trial["geometry_qualified"]) and float(trial["radial_derivative"]) > 0.0:
        return "BOUND_THIN_TRIAL_NO_THIN_STATIONARY_RADIUS"
    if not supported:
        return "BOUND_REDUCED_LOOP_OUTSIDE_THIN_DOMAIN"
    if bool(spectrum["non_symmetry_positive"]) and float(trial["radial_derivative"]) == 0.0:
        return "SUPPORTS_CONDITIONAL_WOUND_LOOP_GAP_MECHANISM"
    return "INCONCLUSIVE_STATIONARITY_OR_SPECTRUM"


def run(input_path: Path, output_path: Path) -> int:
    if output_path.exists():
        raise FileExistsError(f"Use a fresh output path: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_bytes = input_path.read_bytes()
    primary = json.loads(input_bytes)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "input": input_path.relative_to(ROOT).as_posix(),
        "input_sha256": sha256_bytes(input_bytes),
        "platform": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__},
        "checks": [], "failures": [],
    }

    add_check(receipt, "primary schema and status",
              primary.get("schema") == PRIMARY_SCHEMA and primary.get("status") == "PASS"
              and primary.get("failures") == []
              and isinstance(primary.get("checks"), list)
              and all(row.get("passed") is True for row in primary["checks"]),
              {"schema": primary.get("schema"), "status": primary.get("status"),
               "failures": primary.get("failures")})
    add_check(receipt, "primary finite numeric tree", finite_tree(primary), "all persisted numbers finite")
    declared_digest = primary.get("content_sha256")
    reproduced_digest = content_digest(primary)
    receipt["primary_content_digest"] = {"declared": declared_digest, "reproduced": reproduced_digest}
    add_check(receipt, "primary content digest reproduces", declared_digest == reproduced_digest,
              receipt["primary_content_digest"])

    binding, binding_failures = validate_sources(primary, input_path)
    receipt["source_binding"] = binding
    add_check(receipt, "live and frozen sources match manifest", not binding_failures, binding_failures)
    manifest_path = input_path.with_suffix(".inputs.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    manifest_ok = isinstance(manifest, dict) and manifest.get("identities") == primary.get("identities")
    add_check(receipt, "adjacent inputs manifest agrees", manifest_ok,
              {"path": str(manifest_path), "present": manifest_path.is_file()})

    profiles = primary.get("profiles")
    inventory_ok = (isinstance(profiles, list) and len(profiles) == len(DENSITIES)
                    and [float(row["density"]) for row in profiles] == list(DENSITIES))
    add_check(receipt, "profile inventory exact", inventory_ok,
              {"expected": len(DENSITIES), "actual": len(profiles) if isinstance(profiles, list) else None})
    profile_recon: list[dict[str, Any]] = []
    profile_failures: list[str] = []
    if inventory_ok:
        for row in profiles:
            recon = reconstruct_profile(row)
            worst, failures = compare_fields(row, recon, (
                "population", "energy", "energy_per_population", "width_rms",
                "f_min", "c_core", "tail_fraction_outside_6", "residual",
            ))
            if failures:
                profile_failures.extend(f"n={row['density']}: {message}" for message in failures)
            if recon["residual"] >= PROFILE_RESIDUAL_TOL:
                profile_failures.append(f"n={row['density']}: residual {recon['residual']:.3e}")
            profile_recon.append({"density": row["density"], "worst_error": worst,
                                  "residual": recon["residual"]})
    receipt["profile_reconstruction"] = profile_recon
    add_check(receipt, "profile functional reconstruction", not profile_failures, profile_failures)

    comparisons = primary.get("grid_comparisons", [])
    comparison_failures: list[str] = []
    if [float(row.get("density", -1)) for row in comparisons] != list(REFINEMENT_DENSITIES):
        comparison_failures.append("grid-comparison density inventory mismatch")
    for row in comparisons:
        expected_spacing = normalized_error(row["primary"], row["spacing"]["energy_per_population"])
        expected_domain = normalized_error(row["primary"], row["domain"]["energy_per_population"])
        if normalized_error(expected_spacing, row["spacing_error"]) >= NORMALIZED_TOL:
            comparison_failures.append(f"n={row['density']} spacing-error arithmetic")
        if normalized_error(expected_domain, row["domain_error"]) >= NORMALIZED_TOL:
            comparison_failures.append(f"n={row['density']} domain-error arithmetic")
        if expected_spacing >= GRID_REL_TOL or expected_domain >= GRID_REL_TOL:
            comparison_failures.append(f"n={row['density']} grid tolerance")
    add_check(receipt, "grid comparison arithmetic and gates", not comparison_failures, comparison_failures)

    density_nodes = np.asarray([row["density"] for row in profiles], dtype=np.float64)
    energy_nodes = np.asarray([row["energy_per_population"] for row in profiles], dtype=np.float64)
    energy_curve = PchipInterpolator(density_nodes, energy_nodes)
    bound_nodes = density_nodes[energy_nodes < B_COEF]

    def qcrit(density: float) -> float:
        energy = float(energy_curve(density))
        if energy >= B_COEF:
            return float("inf")
        return math.sqrt(8.0 * math.pi ** 2 * A_COEF * K_CX * energy * density ** 2
                         / (B_COEF - energy))

    q_min = piecewise_minimum(bound_nodes, qcrit)
    onset_expected = {
        "charge_per_winding": q_min["value"], "density": q_min["density"],
        "energy_per_population": float(energy_curve(q_min["density"])),
        "townes_density": TOWNES_DENSITY,
    }
    onset_worst, onset_failures = compare_fields(primary["binding_onset"], onset_expected,
                                                  tuple(onset_expected))
    if primary["binding_onset"]["density_bracket"] != q_min["bracket"]:
        onset_failures.append("density bracket mismatch")
    receipt["binding_onset"] = {"reconstructed": onset_expected, "worst_error": onset_worst}
    add_check(receipt, "binding onset reconstructs", not onset_failures, onset_failures)

    loop_failures: list[str] = []
    loop_reconstruction: list[dict[str, Any]] = []
    loop_rows = primary.get("leading_loops", [])
    if [float(row.get("charge", -1)) for row in loop_rows] != list(CHARGES):
        loop_failures.append("charge inventory mismatch")
    tail_curve = PchipInterpolator(density_nodes,
                                   np.asarray([row["tail_fraction_outside_6"] for row in profiles]))
    for stored, charge in zip(loop_rows, CHARGES):
        minimum = piecewise_minimum(
            bound_nodes,
            lambda density, q=charge: float(leading_row(q, density, float(energy_curve(density)))["mass"]),
        )
        expected = leading_row(charge, minimum["density"], float(energy_curve(minimum["density"])))
        expected["tail_fraction_outside_6"] = max(0.0, float(tail_curve(minimum["density"])))
        expected["density_curvature"] = float(energy_curve.derivative(2)(minimum["density"]))
        worst, failures = compare_fields(stored, expected, (
            "density", "energy_per_population", "auxiliary", "total_population", "length",
            "radius", "mass", "continuum_threshold", "binding_margin",
            "tail_fraction_outside_6", "population_curvature", "density_curvature",
        ))
        if bool(stored["bound"]) != bool(expected["bound"]):
            failures.append("bound classification mismatch")
        expected_geometry = bool(
            expected["radius"] >= MIN_LOOP_RADIUS
            and expected["tail_fraction_outside_6"] < TAIL_TOL
            and not minimum["endpoint"]
        )
        if bool(stored["geometry_qualified"]) != expected_geometry:
            failures.append("geometry qualification mismatch")
        if stored["density_bracket"] != minimum["bracket"]:
            failures.append("density bracket mismatch")
        loop_failures.extend(f"Q={charge}: {message}" for message in failures)
        loop_reconstruction.append({"charge": charge, "worst_error": worst,
                                    "mass": expected["mass"], "radius": expected["radius"]})
    receipt["leading_loop_reconstruction"] = loop_reconstruction
    add_check(receipt, "leading loop minima reconstruct", not loop_failures, loop_failures)

    torus_failures: list[str] = []
    torus_reconstruction: list[dict[str, Any]] = []
    torus_rows = primary.get("torus_grid", [])
    if len(torus_rows) != len(profiles):
        torus_failures.append("torus-grid row count mismatch")
    else:
        for profile, stored in zip(profiles, torus_rows):
            expected = reconstruct_torus(profile, 256.0, MIN_LOOP_RADIUS)
            worst, failures = compare_fields(stored, expected, (
                "metric_factor", "metric_factor_derivative", "tail_fraction_outside_6",
                "static_energy", "twist_energy", "temporal_charge_energy", "mass",
                "continuum_threshold", "binding_margin", "radial_derivative",
            ))
            if bool(stored["bound"]) != bool(expected["bound"]) or stored["radial_drive"] != expected["radial_drive"]:
                failures.append("torus classification mismatch")
            torus_failures.extend(f"n={profile['density']}: {message}" for message in failures)
            torus_reconstruction.append({"density": profile["density"], "worst_error": worst})
    receipt["torus_reconstruction"] = torus_reconstruction
    add_check(receipt, "torus metric and mass reconstruct", not torus_failures, torus_failures)

    trial = primary["thin_trial"]
    trial_profile = trial["profile"]
    expected_trial_profile = reconstruct_profile(trial_profile)
    expected_trial = reconstruct_torus(trial_profile, 256.0, MIN_LOOP_RADIUS)
    trial_worst, trial_failures = compare_fields(trial, expected_trial, (
        "metric_factor", "metric_factor_derivative", "tail_fraction_outside_6",
        "static_energy", "twist_energy", "temporal_charge_energy", "mass",
        "continuum_threshold", "binding_margin", "radial_derivative",
    ))
    profile_worst, profile_failures = compare_fields(trial_profile, expected_trial_profile, (
        "population", "energy", "energy_per_population", "width_rms",
        "f_min", "c_core", "tail_fraction_outside_6", "residual",
    ))
    trial_worst = max(trial_worst, profile_worst)
    trial_failures.extend(f"profile {message}" for message in profile_failures)
    trial_mass_nodes = np.asarray(
        [reconstruct_torus(profile, 256.0, MIN_LOOP_RADIUS)["mass"] for profile in profiles],
        dtype=np.float64,
    )
    trial_curve = PchipInterpolator(density_nodes, trial_mass_nodes)
    trial_minimum = piecewise_minimum(
        density_nodes, lambda density: float(trial_curve(density))
    )
    if normalized_error(trial["density"], trial_minimum["density"]) >= NORMALIZED_TOL:
        trial_failures.append("trial minimizing density mismatch")
    if normalized_error(trial["interpolation_mass"], trial_minimum["value"]) >= NORMALIZED_TOL:
        trial_failures.append("trial interpolation mass mismatch")
    if trial["density_bracket"] != trial_minimum["bracket"]:
        trial_failures.append("trial density bracket mismatch")
    if bool(trial["density_endpoint"]) != bool(trial_minimum["endpoint"]):
        trial_failures.append("trial density-endpoint mismatch")
    if expected_trial_profile["residual"] >= PROFILE_RESIDUAL_TOL:
        trial_failures.append("trial profile residual fails")
    if bool(trial["bound"]) != bool(expected_trial["bound"]):
        trial_failures.append("trial bound classification mismatch")
    expected_trial_geometry = expected_trial["tail_fraction_outside_6"] < TAIL_TOL
    if bool(trial["geometry_qualified"]) != bool(expected_trial_geometry):
        trial_failures.append("trial geometry qualification mismatch")
    if trial["radial_drive"] != expected_trial["radial_drive"]:
        trial_failures.append("trial radial-drive mismatch")
    receipt["thin_trial_reconstruction"] = {
        "worst_error": trial_worst, "profile_residual": expected_trial_profile["residual"],
        "mass": expected_trial["mass"], "binding_margin": expected_trial["binding_margin"],
        "interpolation_density": trial_minimum["density"],
        "interpolation_mass": trial_minimum["value"],
    }
    add_check(receipt, "fixed-radius thin trial reconstructs", not trial_failures, trial_failures)

    expected_spectrum = reconstruct_spectrum(trial_profile)
    stored_spectrum = primary["transverse_spectrum"]
    spectrum_failures: list[str] = []
    worst_eigen = 0.0
    for mode in range(5):
        error = array_error(stored_spectrum["modes"][str(mode)]["eigenvalues"],
                            expected_spectrum["modes"][str(mode)])
        worst_eigen = max(worst_eigen, error)
        if error >= EIGEN_TOL:
            spectrum_failures.append(f"m={mode} eigenvalue error {error:.3e}")
    for field in ("translation_eigenvalue", "translation_soft_ratio", "minimum_non_symmetry_eigenvalue"):
        error = normalized_error(stored_spectrum[field], expected_spectrum[field])
        worst_eigen = max(worst_eigen, error)
        if error >= EIGEN_TOL:
            spectrum_failures.append(f"{field} error {error:.3e}")
    if bool(stored_spectrum["non_symmetry_positive"]) != bool(expected_spectrum["non_symmetry_positive"]):
        spectrum_failures.append("spectrum positivity mismatch")
    receipt["spectrum_reconstruction"] = {"worst_normalized_error": worst_eigen,
                                           **expected_spectrum}
    add_check(receipt, "generalized transverse spectrum reconstructs",
              not spectrum_failures, spectrum_failures)

    mutated_mass = expected_trial["mass"] + 2.0 * math.pi * MIN_LOOP_RADIUS * 1e-3
    mass_mutation_error = normalized_error(mutated_mass, trial["mass"])
    mass_mutation_fires = mass_mutation_error >= NORMALIZED_TOL
    receipt["mass_mutation_control"] = {"energy_per_length_delta": 1e-3,
                                         "normalized_error": mass_mutation_error,
                                         "fires": mass_mutation_fires}
    add_check(receipt, "mass mutation control fires", mass_mutation_fires,
              receipt["mass_mutation_control"])

    positive_values = [expected_spectrum["modes"]["0"][0], expected_spectrum["modes"]["1"][1]]
    positive_values.extend(expected_spectrum["modes"][str(mode)][0] for mode in (2, 3, 4))
    mutated_values = list(positive_values)
    mutated_values[0] = -abs(mutated_values[0])
    spectrum_mutation_fires = all(value > 0.0 for value in positive_values) and not all(
        value > 0.0 for value in mutated_values)
    receipt["spectrum_mutation_control"] = {"original_minimum": min(positive_values),
                                             "mutated_minimum": min(mutated_values),
                                             "fires": spectrum_mutation_fires}
    add_check(receipt, "spectrum sign mutation control fires", spectrum_mutation_fires,
              receipt["spectrum_mutation_control"])

    reconstructed_classification = independent_classification(primary)
    receipt["classification"] = reconstructed_classification
    add_check(receipt, "scientific classification reconstructs",
              reconstructed_classification == primary.get("classification"),
              {"primary": primary.get("classification"),
               "independent": reconstructed_classification})
    scope = primary.get("scope", {})
    scope_ok = (scope.get("yang_mills_identification") == "UNRESOLVED"
                and scope.get("continuum_gauge_construction") == "UNRESOLVED"
                and scope.get("charge_quantization") == "UNRESOLVED"
                and scope.get("clay_verdict") is None)
    add_check(receipt, "Yang-Mills evidence boundary retained", scope_ok, scope)

    receipt["status"] = "PASS" if not receipt["failures"] else "FAIL"
    receipt["content_sha256"] = content_digest(receipt)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(f"Receipt: {output_path}")
    print(json.dumps({
        "status": receipt["status"], "checks": len(receipt["checks"]),
        "failures": receipt["failures"], "classification": receipt["classification"],
        "input_sha256": receipt["input_sha256"],
    }, indent=2))
    if receipt["status"] == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    print("NOT ALL CHECKS PASSED")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    input_path = args.input.absolute()
    output_path = args.output.absolute()
    try:
        return run(input_path, output_path)
    except FileExistsError as exc:
        print(f"Refusing to overwrite evidence: {exc}")
        return 2
    except Exception as exc:
        print(f"Verification error: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
