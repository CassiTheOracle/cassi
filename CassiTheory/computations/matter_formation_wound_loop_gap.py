#!/usr/bin/env python3
"""Apply the registered matter-formation tube to a wound charged-loop gap mechanism.

Run from CassiTheory:
    python computations/matter_formation_wound_loop_gap.py \
        --output runs/20260921_matter_formation_wound_loop_gap_recovery/primary.json
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

import matter_formation_tube_geometry as tube_geometry


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/matter-formation-wound-loop-gap-prereg.md"
GEOMETRY = ROOT / "computations/matter_formation_tube_geometry.py"
INDEPENDENT = ROOT / "computations/verify_matter_formation_wound_loop_gap.py"
DEFAULT_OUTPUT = ROOT / "runs/20260921_matter_formation_wound_loop_gap_recovery/primary.json"
FAILED_OUTPUT = ROOT / "runs/20260921_matter_formation_wound_loop_gap/primary.json"
SCHEMA = "cassi.matter-formation.wound-loop-gap.v1"

DENSITIES = (
    1.75, 1.875, 2.0, 2.25, 2.5, 2.75, 3.0, math.pi, 3.25, 3.5,
    3.75, 4.0, 4.5, 5.0, 6.0, 8.0, 12.0, 24.0, 48.0,
)
REFINEMENT_DENSITIES = (2.0, 4.0, 8.0)
CHARGES = (16.0, 64.0, 128.0, 256.0)
WINDING = 1
PRIMARY_M = 200
PRIMARY_RMAX = 8.0
SUPPORT_RADIUS = 6.0
MIN_LOOP_RADIUS = 8.0
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
TOWNES_MASS = 11.700896
OMEGA_INF = math.sqrt(B_COEF / A_COEF)
WEAK_ATTRACTION = 2.0 * H_COEF * H_COEF / U_RHO - U_C
TOWNES_DENSITY = K_CX * TOWNES_MASS / (2.0 * WEAK_ATTRACTION)


def normalized_error(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(1.0, abs(float(left)), abs(float(right)))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def content_digest(receipt: dict[str, Any]) -> str:
    body = dict(receipt)
    body.pop("content_sha256", None)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha256_bytes(encoded)


def add_check(receipt: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    if any(row["name"] == name for row in receipt["checks"]):
        raise ValueError(f"duplicate check: {name}")
    row = {"name": name, "passed": bool(passed), "detail": detail}
    receipt["checks"].append(row)
    if not passed:
        receipt["failures"].append(name)


def profile_row(tube: tube_geometry.Tube, state: dict[str, Any], density: float,
                include_arrays: bool = True) -> dict[str, Any]:
    f = np.asarray(state["f"], dtype=np.float64)
    c = np.asarray(state["c"], dtype=np.float64)
    population = tube.population(c)
    energy = tube.energy(f, c)
    mask = tube.r > SUPPORT_RADIUS
    tail = float(2.0 * math.pi * np.sum(tube.r[mask] * tube.dr * c[mask] ** 2) / population)
    row: dict[str, Any] = {
        "density": float(density),
        "population": population,
        "energy": energy,
        "energy_per_population": energy / population,
        "multiplier": float(state["mu"]),
        "residual": float(state["residual"]),
        "width_rms": tube.width_rms(c),
        "f_min": float(np.min(f)),
        "c_core": float(c[0]),
        "tail_fraction_outside_6": tail,
        "M": int(tube.M),
        "rmax": float(tube.rmax),
        "dr": float(tube.dr),
    }
    if include_arrays:
        row["f"] = f.tolist()
        row["c"] = c.tolist()
    return row


def solve_at(tube: tube_geometry.Tube, density: float,
             seed: dict[str, Any] | None = None) -> dict[str, Any]:
    state = tube.solve(
        density,
        sweeps=4,
        f_init=None if seed is None else seed["f"],
        c_init=None if seed is None else seed["c"],
    )
    if state["residual"] >= PROFILE_RESIDUAL_TOL:
        state = tube.solve(density, sweeps=8)
    return state


def interpolate_seed(source_tube: tube_geometry.Tube, state: dict[str, Any],
                     target_tube: tube_geometry.Tube) -> dict[str, np.ndarray]:
    return {
        "f": np.interp(target_tube.r, source_tube.r, state["f"], left=state["f"][0], right=1.0),
        "c": np.interp(target_tube.r, source_tube.r, state["c"], left=state["c"][0], right=0.0),
    }


def piecewise_minimum(nodes: np.ndarray, fn: Callable[[float], float]) -> dict[str, Any]:
    candidates: list[tuple[float, float, tuple[float, float]]] = []
    for lo, hi in zip(nodes[:-1], nodes[1:]):
        for x in (float(lo), float(hi)):
            candidates.append((float(fn(x)), x, (float(lo), float(hi))))
        result = minimize_scalar(fn, bounds=(float(lo), float(hi)), method="bounded",
                                 options={"xatol": 1e-11, "maxiter": 200})
        if result.success and math.isfinite(float(result.fun)):
            candidates.append((float(result.fun), float(result.x), (float(lo), float(hi))))
    value, point, bracket = min(candidates, key=lambda item: item[0])
    endpoint = abs(point - float(nodes[0])) < 1e-8 or abs(point - float(nodes[-1])) < 1e-8
    return {"value": value, "density": point, "bracket": list(bracket), "endpoint": endpoint}


def leading_loop_row(charge: float, density: float, energy_per_population: float) -> dict[str, Any]:
    winding_term = 2.0 * math.pi ** 2 * K_CX * WINDING ** 2 * density ** 2
    temporal_term = charge ** 2 / (4.0 * A_COEF)
    auxiliary = temporal_term + winding_term
    total_population = math.sqrt(auxiliary / energy_per_population)
    length = total_population / density
    mass = 2.0 * math.sqrt(energy_per_population * auxiliary)
    threshold = OMEGA_INF * abs(charge)
    return {
        "charge": float(charge),
        "winding": WINDING,
        "density": float(density),
        "energy_per_population": float(energy_per_population),
        "auxiliary": auxiliary,
        "total_population": total_population,
        "length": length,
        "radius": length / (2.0 * math.pi),
        "mass": mass,
        "continuum_threshold": threshold,
        "binding_margin": threshold - mass,
        "bound": bool(mass < threshold),
    }


def metric_factor(tube: tube_geometry.Tube, c: np.ndarray, radius: float) -> tuple[float, float, float]:
    support = tube.r <= SUPPORT_RADIUS
    r = tube.r[support]
    weights = r * tube.dr * np.asarray(c, dtype=np.float64)[support] ** 2
    denominator = float(np.sum(weights))
    root = np.sqrt(1.0 - (r / radius) ** 2)
    eta = float(np.sum(weights / root) / denominator)
    derivative = float(np.sum(-weights * r ** 2 / (radius ** 3 * root ** 3)) / denominator)
    population_inside = 2.0 * math.pi * denominator
    return eta, derivative, population_inside


def torus_mass(tube: tube_geometry.Tube, state: dict[str, Any], density: float,
               charge: float, radius: float) -> dict[str, Any]:
    f = np.asarray(state["f"], dtype=np.float64)
    c = np.asarray(state["c"], dtype=np.float64)
    energy = tube.energy(f, c)
    population = tube.population(c)
    eta, eta_derivative, population_inside = metric_factor(tube, c, radius)
    static = 2.0 * math.pi * radius * energy
    twist = math.pi * K_CX * WINDING ** 2 * density * eta / radius
    temporal = charge ** 2 / (8.0 * math.pi * A_COEF * radius * density)
    mass = static + twist + temporal
    radial_derivative = (
        2.0 * math.pi * energy
        + math.pi * K_CX * WINDING ** 2 * density
        * (eta_derivative / radius - eta / radius ** 2)
        - charge ** 2 / (8.0 * math.pi * A_COEF * density * radius ** 2)
    )
    tail = max(0.0, 1.0 - population_inside / population)
    return {
        "charge": float(charge),
        "winding": WINDING,
        "density": float(density),
        "radius": float(radius),
        "energy_per_length": energy,
        "population": population,
        "metric_factor": eta,
        "metric_factor_derivative": eta_derivative,
        "tail_fraction_outside_6": tail,
        "static_energy": static,
        "twist_energy": twist,
        "temporal_charge_energy": temporal,
        "mass": mass,
        "continuum_threshold": OMEGA_INF * abs(charge),
        "binding_margin": OMEGA_INF * abs(charge) - mass,
        "bound": bool(mass < OMEGA_INF * abs(charge)),
        "radial_derivative": radial_derivative,
        "radial_drive": "toward-smaller-R" if radial_derivative > 0.0 else "toward-larger-R",
    }


def transverse_spectrum(tube: tube_geometry.Tube, state: dict[str, Any],
                        density: float) -> dict[str, Any]:
    M = tube.M
    f = np.asarray(state["f"], dtype=np.float64)
    c = np.asarray(state["c"], dtype=np.float64)
    mu = float(state["mu"])
    residual, jacobian, _ = tube.system(np.concatenate([f, c, [mu]]), density)
    hessian_0 = np.asarray(jacobian[:-1, :-1], dtype=np.float64)
    measure = 2.0 * math.pi * tube.r * tube.dr
    mass_0 = np.diag(np.concatenate([C_PSI * measure, 2.0 * A_COEF * measure]))
    charge_gradient = np.concatenate([np.zeros(M), 4.0 * math.pi * tube.r * tube.dr * c])
    tangent = sla.null_space(charge_gradient.reshape(1, -1))
    h0 = tangent.T @ hessian_0 @ tangent
    w0 = tangent.T @ mass_0 @ tangent
    eigen_0 = sla.eigh(h0, w0, eigvals_only=True, subset_by_index=(0, 5),
                      driver="gvx", check_finite=True)
    modes: dict[str, Any] = {
        "0": {
            "eigenvalues": eigen_0.tolist(),
            "frequencies": [math.sqrt(value) if value > 0.0 else None for value in eigen_0],
            "constraint": "fixed transverse population",
        }
    }
    for mode in range(1, 5):
        angular = np.concatenate([
            2.0 * math.pi * tube_geometry.GRAD_F * mode ** 2 * tube.dr / tube.r,
            2.0 * math.pi * tube_geometry.GRAD_C * mode ** 2 * tube.dr / tube.r,
        ])
        h_mode = 0.5 * hessian_0 + np.diag(angular)
        w_mode = 0.5 * mass_0
        eigenvalues = sla.eigh(h_mode, w_mode, eigvals_only=True, subset_by_index=(0, 5),
                               driver="gvx", check_finite=True)
        modes[str(mode)] = {
            "eigenvalues": eigenvalues.tolist(),
            "frequencies": [math.sqrt(value) if value > 0.0 else None for value in eigenvalues],
        }
    translation = float(modes["1"]["eigenvalues"][0])
    comparison = min(float(modes[str(mode)]["eigenvalues"][0]) for mode in (2, 3, 4))
    non_symmetry = [float(modes["0"]["eigenvalues"][0]),
                    float(modes["1"]["eigenvalues"][1])]
    non_symmetry.extend(float(modes[str(mode)]["eigenvalues"][0]) for mode in (2, 3, 4))
    return {
        "density": float(density),
        "stationarity_residual": float(np.max(np.abs(residual))),
        "modes": modes,
        "translation_eigenvalue": translation,
        "translation_soft_ratio": abs(translation) / max(abs(comparison), 1e-300),
        "global_phase_mode": "exact zero mode, outside the real-amplitude Hessian",
        "minimum_non_symmetry_eigenvalue": min(non_symmetry),
        "non_symmetry_positive": bool(min(non_symmetry) > 0.0),
    }


def freeze_sources(output: Path) -> tuple[dict[str, Any], dict[str, bytes], Path, Path]:
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = {
        "protocol": PROTOCOL,
        "geometry": GEOMETRY,
        "primary": Path(__file__).resolve(),
        "independent": INDEPENDENT,
    }
    payloads = {name: path.read_bytes() for name, path in sources.items()}
    identities = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_bytes(payloads[name]),
            "snapshot": path.name,
        }
        for name, path in sources.items()
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for name, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[name])
    manifest = {
        "schema": "cassi.matter-formation.wound-loop-gap.inputs.v1",
        "identities": identities,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest, payloads, manifest_path, snapshot_dir


def run(output: Path) -> int:
    manifest, source_payloads, manifest_path, snapshot_dir = freeze_sources(output)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "identities": manifest["identities"],
        "platform": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "recovery": {
            "prior_failed_receipt": FAILED_OUTPUT.relative_to(ROOT).as_posix(),
            "defect": (
                "Path.resolve followed the runs junction before repo-relative "
                "manifest paths were recorded"
            ),
            "scientific_schedule_changed": False,
        },
        "coefficients": {
            "a": A_COEF, "c_psi": C_PSI, "k_Cx": K_CX, "u_C": U_C,
            "u_rho": U_RHO, "B": B_COEF, "h_C": H_COEF,
            "Omega_inf": OMEGA_INF, "townes_mass": TOWNES_MASS,
            "weak_attraction": WEAK_ATTRACTION, "townes_density": TOWNES_DENSITY,
        },
        "schedule": {
            "densities": list(DENSITIES), "refinement_densities": list(REFINEMENT_DENSITIES),
            "charges": list(CHARGES), "winding": WINDING,
            "primary_grid": {"M": PRIMARY_M, "rmax": PRIMARY_RMAX},
            "spacing_grid": {"M": 400, "rmax": 8.0},
            "domain_grid": {"M": 400, "rmax": 16.0},
            "support_radius": SUPPORT_RADIUS, "minimum_loop_radius": MIN_LOOP_RADIUS,
        },
        "checks": [], "failures": [],
    }
    try:
        constants_match = (
            tube_geometry.A_COEF == A_COEF
            and tube_geometry.CPSI == C_PSI
            and tube_geometry.K_CX == K_CX
            and tube_geometry.UR == U_RHO
            and tube_geometry.UC == U_C
            and tube_geometry.B_COEF == B_COEF
            and tube_geometry.H_COEF == H_COEF
            and tube_geometry.GRAD_F == 0.5
            and tube_geometry.GRAD_C == 0.5
        )
        add_check(receipt, "registered coefficients match corrected tube module", constants_match,
                  receipt["coefficients"])

        primary_tube = tube_geometry.Tube(M=PRIMARY_M, rmax=PRIMARY_RMAX)
        states: dict[float, dict[str, Any]] = {}
        profiles: list[dict[str, Any]] = []
        seed: dict[str, Any] | None = None
        for density in DENSITIES:
            state = solve_at(primary_tube, density, seed)
            states[float(density)] = state
            profiles.append(profile_row(primary_tube, state, density))
            seed = state
        receipt["profiles"] = profiles
        add_check(receipt, "complete primary density inventory",
                  [row["density"] for row in profiles] == list(DENSITIES),
                  {"expected": len(DENSITIES), "actual": len(profiles)})
        add_check(receipt, "all primary profiles converge",
                  all(row["residual"] < PROFILE_RESIDUAL_TOL for row in profiles),
                  {"worst_residual": max(row["residual"] for row in profiles),
                   "tolerance": PROFILE_RESIDUAL_TOL})

        comparisons: list[dict[str, Any]] = []
        for density in REFINEMENT_DENSITIES:
            source = states[density]
            source_e = next(row["energy_per_population"] for row in profiles
                            if row["density"] == density)
            spacing_tube = tube_geometry.Tube(M=400, rmax=8.0)
            spacing_seed = interpolate_seed(primary_tube, source, spacing_tube)
            spacing_state = solve_at(spacing_tube, density, spacing_seed)
            spacing_row = profile_row(spacing_tube, spacing_state, density, include_arrays=False)
            domain_tube = tube_geometry.Tube(M=400, rmax=16.0)
            domain_seed = interpolate_seed(primary_tube, source, domain_tube)
            domain_state = solve_at(domain_tube, density, domain_seed)
            domain_row = profile_row(domain_tube, domain_state, density, include_arrays=False)
            comparisons.append({
                "density": density,
                "primary": source_e,
                "spacing": spacing_row,
                "domain": domain_row,
                "spacing_error": normalized_error(source_e, spacing_row["energy_per_population"]),
                "domain_error": normalized_error(source_e, domain_row["energy_per_population"]),
            })
        receipt["grid_comparisons"] = comparisons
        add_check(receipt, "spacing and domain comparisons qualify",
                  all(row["spacing"]["residual"] < PROFILE_RESIDUAL_TOL
                      and row["domain"]["residual"] < PROFILE_RESIDUAL_TOL
                      and row["spacing_error"] < GRID_REL_TOL
                      and row["domain_error"] < GRID_REL_TOL for row in comparisons),
                  {"worst_spacing_error": max(row["spacing_error"] for row in comparisons),
                   "worst_domain_error": max(row["domain_error"] for row in comparisons),
                   "tolerance": GRID_REL_TOL})

        density_nodes = np.asarray([row["density"] for row in profiles], dtype=np.float64)
        energy_nodes = np.asarray([row["energy_per_population"] for row in profiles], dtype=np.float64)
        energy_curve = PchipInterpolator(density_nodes, energy_nodes)
        bound_mask = energy_nodes < B_COEF
        bound_nodes = density_nodes[bound_mask]
        if len(bound_nodes) < 2:
            raise RuntimeError("fewer than two bound density rows")

        def qcrit(density: float) -> float:
            energy = float(energy_curve(density))
            if energy >= B_COEF:
                return float("inf")
            return math.sqrt(8.0 * math.pi ** 2 * A_COEF * K_CX * energy * density ** 2
                             / (B_COEF - energy))

        q_min = piecewise_minimum(bound_nodes, qcrit)
        receipt["binding_onset"] = {
            "charge_per_winding": q_min["value"],
            "density": q_min["density"],
            "density_bracket": q_min["bracket"],
            "endpoint": q_min["endpoint"],
            "energy_per_population": float(energy_curve(q_min["density"])),
            "townes_density": TOWNES_DENSITY,
        }
        add_check(receipt, "binding-onset minimum is finite and interior",
                  math.isfinite(q_min["value"]) and q_min["value"] > 0.0 and not q_min["endpoint"],
                  receipt["binding_onset"])

        loop_rows: list[dict[str, Any]] = []
        for charge in CHARGES:
            def objective(density: float, q: float = charge) -> float:
                return leading_loop_row(q, density, float(energy_curve(density)))["mass"]

            minimum = piecewise_minimum(bound_nodes, objective)
            row = leading_loop_row(charge, minimum["density"],
                                   float(energy_curve(minimum["density"])))
            row.update(density_bracket=minimum["bracket"], density_endpoint=minimum["endpoint"],
                       density_curvature=float(energy_curve.derivative(2)(minimum["density"])))
            tail_curve = PchipInterpolator(density_nodes,
                                           np.asarray([p["tail_fraction_outside_6"] for p in profiles]))
            row["tail_fraction_outside_6"] = max(0.0, float(tail_curve(minimum["density"])))
            row["geometry_qualified"] = bool(
                row["radius"] >= MIN_LOOP_RADIUS
                and row["tail_fraction_outside_6"] < TAIL_TOL
                and not row["density_endpoint"]
            )
            row["population_curvature"] = 2.0 * row["auxiliary"] / row["total_population"] ** 3
            loop_rows.append(row)
        receipt["leading_loops"] = loop_rows
        add_check(receipt, "complete fixed-charge loop inventory",
                  [row["charge"] for row in loop_rows] == list(CHARGES),
                  {"expected": list(CHARGES), "actual": [row["charge"] for row in loop_rows]})
        add_check(receipt, "leading loop values are finite",
                  all(all(math.isfinite(float(row[key])) for key in
                          ("density", "mass", "radius", "binding_margin", "population_curvature"))
                      for row in loop_rows),
                  {"rows": len(loop_rows)})

        torus_grid_rows: list[dict[str, Any]] = []
        for density, state in states.items():
            torus_grid_rows.append(torus_mass(primary_tube, state, density, 256.0,
                                              MIN_LOOP_RADIUS))
        trial_nodes = np.asarray([row["density"] for row in torus_grid_rows])
        trial_masses = np.asarray([row["mass"] for row in torus_grid_rows])
        trial_curve = PchipInterpolator(trial_nodes, trial_masses)
        trial_minimum = piecewise_minimum(trial_nodes, lambda density: float(trial_curve(density)))
        nearest_density = min(states, key=lambda value: abs(value - trial_minimum["density"]))
        trial_state = solve_at(primary_tube, trial_minimum["density"], states[nearest_density])
        trial_profile = profile_row(primary_tube, trial_state, trial_minimum["density"])
        trial = torus_mass(primary_tube, trial_state, trial_minimum["density"], 256.0,
                           MIN_LOOP_RADIUS)
        trial.update(
            interpolation_mass=trial_minimum["value"],
            density_bracket=trial_minimum["bracket"],
            density_endpoint=trial_minimum["endpoint"],
            geometry_qualified=bool(trial["tail_fraction_outside_6"] < TAIL_TOL),
            profile=trial_profile,
        )
        receipt["torus_grid"] = torus_grid_rows
        receipt["thin_trial"] = trial
        add_check(receipt, "fixed-radius trial profile converges",
                  trial_profile["residual"] < PROFILE_RESIDUAL_TOL,
                  {"residual": trial_profile["residual"], "tolerance": PROFILE_RESIDUAL_TOL})
        add_check(receipt, "fixed-radius trial respects transported support",
                  trial["tail_fraction_outside_6"] < TAIL_TOL,
                  {"tail_fraction": trial["tail_fraction_outside_6"], "tolerance": TAIL_TOL})

        spectrum = transverse_spectrum(primary_tube, trial_state, trial_minimum["density"])
        receipt["transverse_spectrum"] = spectrum
        add_check(receipt, "translation mode is soft",
                  spectrum["translation_soft_ratio"] < 0.2,
                  {"eigenvalue": spectrum["translation_eigenvalue"],
                   "soft_ratio": spectrum["translation_soft_ratio"]})
        add_check(receipt, "non-symmetry transverse modes are positive",
                  spectrum["non_symmetry_positive"],
                  {"minimum": spectrum["minimum_non_symmetry_eigenvalue"]})

        bound_loops = [row for row in loop_rows if row["bound"]]
        supported = [row for row in bound_loops if row["geometry_qualified"]
                     and row["population_curvature"] > 0.0]
        if not bound_loops:
            classification = "NO_BOUND_WOUND_LOOP_IN_SCHEDULE"
        elif trial["bound"] and trial["geometry_qualified"] and trial["radial_derivative"] > 0.0:
            classification = "BOUND_THIN_TRIAL_NO_THIN_STATIONARY_RADIUS"
        elif not supported:
            classification = "BOUND_REDUCED_LOOP_OUTSIDE_THIN_DOMAIN"
        elif spectrum["non_symmetry_positive"] and trial["radial_derivative"] == 0.0:
            classification = "SUPPORTS_CONDITIONAL_WOUND_LOOP_GAP_MECHANISM"
        else:
            classification = "INCONCLUSIVE_STATIONARITY_OR_SPECTRUM"

        receipt["controls"] = {
            "zero_temporal_charge": {
                "result": "mass infimum tends to zero as n tends to zero",
                "finite_gap": False,
            },
            "zero_spatial_winding": {
                "result": "temporal charge supplies binding but no finite loop radius",
                "finite_loop_scale": False,
            },
        }
        receipt["classification"] = classification
        receipt["scope"] = {
            "conditional_scalar_loop_mechanism": (
                "SUPPORTS" if classification == "SUPPORTS_CONDITIONAL_WOUND_LOOP_GAP_MECHANISM"
                else "UNRESOLVED"
            ),
            "yang_mills_identification": "UNRESOLVED",
            "continuum_gauge_construction": "UNRESOLVED",
            "charge_quantization": "UNRESOLVED",
            "clay_verdict": None,
        }

        sources_stable = all(path.read_bytes() == source_payloads[name] for name, path in {
            "protocol": PROTOCOL, "geometry": GEOMETRY,
            "primary": Path(__file__).resolve(), "independent": INDEPENDENT,
        }.items())
        add_check(receipt, "frozen sources remain byte-identical", sources_stable,
                  {"manifest": str(manifest_path.relative_to(ROOT)),
                   "snapshots": str(snapshot_dir.relative_to(ROOT))})
        receipt["status"] = "PASS" if not receipt["failures"] else "FAIL"
    except Exception as exc:
        receipt["status"] = "ERROR"
        receipt["error"] = f"{type(exc).__name__}: {exc}"

    receipt["content_sha256"] = content_digest(receipt)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(f"Receipt: {output}")
    print(json.dumps({
        "status": receipt.get("status"),
        "classification": receipt.get("classification"),
        "checks": len(receipt.get("checks", [])),
        "failures": receipt.get("failures"),
        "binding_onset": receipt.get("binding_onset"),
        "thin_trial": None if "thin_trial" not in receipt else {
            key: receipt["thin_trial"][key] for key in
            ("density", "mass", "continuum_threshold", "binding_margin",
             "radial_derivative", "radial_drive")
        },
        "error": receipt.get("error"),
    }, indent=2))
    if receipt.get("status") == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    print("NOT ALL CHECKS PASSED")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        return run(args.output.absolute())
    except FileExistsError as exc:
        print(f"Refusing to overwrite evidence: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
