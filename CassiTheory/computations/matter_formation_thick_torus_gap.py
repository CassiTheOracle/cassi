#!/usr/bin/env python3
"""Relax the charged wound carrier loop's cross-section in the exact toroidal metric.

Run from CassiTheory:
    python computations/matter_formation_thick_torus_gap.py \
        --output runs/20260921_matter_formation_thick_torus_gap/primary.json

The protocol is `computations/matter-formation-thick-torus-gap-prereg.md`.  The
functional, the grids, and the schedules are the registered ones; the geometry
module supplies the exact discrete torus energy, gradient, and Hessian, and this
program adds the charge-constrained relaxation, the scan, the refinement, the
constrained spectrum, and the controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from scipy.optimize import minimize

import matter_formation_tube_geometry as tube_geometry


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/matter-formation-thick-torus-gap-prereg.md"
GEOMETRY = ROOT / "computations/matter_formation_tube_geometry.py"
INDEPENDENT = ROOT / "computations/verify_matter_formation_thick_torus_gap.py"
DEFAULT_OUTPUT = ROOT / "runs/20260921_matter_formation_thick_torus_gap/primary.json"
SCHEMA = "cassi.matter-formation.thick-torus-gap.v1"

RADII = (5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0, 10.0, 12.0, 16.0)
DENSITIES = (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0, 32.0)
CHARGES = (64.0, 128.0, 256.0)
WINDING = 1

SCAN_NA, SCAN_NPHI = 200, 32
VALIDATION_NA, VALIDATION_AMAX, VALIDATION_NPHI = 300, 8.0, 32
RESOLUTION_NA, RESOLUTION_NPHI = 400, 64
SPECTRUM_NA, SPECTRUM_NPHI = 100, 16
SPECTRUM_RESOLUTION_NA, SPECTRUM_RESOLUTION_NPHI = 150, 24

POSITION_FRACTIONS = (0.0, 0.2, 0.35, 0.5, 0.65)
POSITION_ANGLES = (math.pi, 0.5 * math.pi, 0.0)

REFINE_DELTA = 0.25
REFINE_OFFSETS = (-4, -3, -2, -1, 0, 1, 2, 3, 4)

RESIDUAL_TOL = 1e-9
MAX_ITERATIONS = 600
STAGE_A_MAXITER = 4000
STAGE_A_MAXFUN = 8000
# Augmented-Lagrangian ladder: each step re-relaxes with a ten-times larger penalty and an
# updated multiplier, so the population constraint is carried by the penalty and the objective
# and its gradient stay an exact pair.
STAGE_A_PENALTY_STEPS = 6
MAX_FAILED_SOLVES = 8
GRID_REL_TOL = 5e-4
RECONSTRUCTION_TOL = 5e-9
VALIDATION_TOL = 1e-2
TRANSPORTED_TOL = 2e-3
OUTER_DECILE_TOL = 1e-3
GEOMETRY_RATIO_GATE = 0.85
SPECTRUM_RESOLUTION_TOL = 5e-2
SPECTRUM_MODE_COUNT = 8

INDEPENDENT_POINTS = ((6.5, 5.0), (8.0, 5.0), (10.0, 8.0))

A_COEF = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
B_COEF = 19.0 / 4.0
H_COEF = 2.9598260763447164
OMEGA_INF = math.sqrt(B_COEF / A_COEF)

# Frozen wound-loop receipt values used by the validation stage (prereg §3.2).
FLAT_ENERGY_PER_LENGTH_PI = 14.571946092025838
FLAT_ENERGY_PER_LENGTH_5 = 22.174477188390973
TRANSPORTED_METRIC_FACTOR_8 = 1.0118788464248585


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


def section_for(radius: float, Na: int, Nphi: int, amax: float | None = None) -> Any:
    """Torus section on the declared grid, with the radius-dependent weights cached."""
    section = tube_geometry.TorusSection(Na=Na, amax=0.9 * radius if amax is None else amax, Nphi=Nphi)
    cache: dict[float, Any] = {}
    original = section.weights

    def weights(kap: float):
        key = float(kap)
        if key not in cache:
            cache[key] = original(key)
        return cache[key]

    section.weights = weights  # type: ignore[method-assign]
    return section


def interp_seed(section: Any, a_source: np.ndarray, f_source: np.ndarray, c_source: np.ndarray,
                density: float, density_source: float) -> tuple[np.ndarray, np.ndarray]:
    """Lift a source cross-section profile onto this section's grid at the target density."""
    scale = math.sqrt(density / max(density_source, 1e-300))
    a = section.a
    f_row = np.interp(a, a_source, f_source, left=f_source[0], right=1.0)
    c_row = np.interp(a, a_source, c_source, left=c_source[0], right=0.0) * scale
    f = np.repeat(f_row[:, None], section.Nphi, axis=1)
    c = np.repeat(c_row[:, None], section.Nphi, axis=1)
    return f, c


def anchor_multiplier(section: Any, radius: float, w: float, density: float,
                      f: np.ndarray, c: np.ndarray) -> tuple[float, float]:
    """Least-squares multiplier of the current profile and its constraint residual.

    The multiplier is the projection of the constraint source term onto the constraint
    gradient, so the bordered stationarity residual of the returned configuration equals
    its tangential gradient residual.
    """
    kap = 1.0 / radius
    _, Rc, rc = section.gradient(f, c, kap, w, radius, density, 0.0)
    direction = (2.0 * section.weights(kap)[0]).ravel()
    weight = float(Rc.ravel() @ direction) / float(direction @ direction)
    return weight, float(rc)


def enforce_population(section: Any, radius: float, c: np.ndarray,
                       density: float) -> np.ndarray:
    """Rescale the carrier so the discrete constraint holds exactly."""
    total = section.population(c, 1.0 / radius)
    if total <= 0.0:
        return c
    return c * math.sqrt(density / total)


def solve_section(section: Any, radius: float, w: complex, density: float,
                  f0: np.ndarray, c0: np.ndarray, lam0: float = 0.0) -> dict[str, Any]:
    """Constrained relaxation: augmented-Lagrangian descent, then bordered Newton polish.

    Stage A minimizes the exact toroidal energy under the population constraint with an
    augmented Lagrangian: L-BFGS-B runs on E + mu*(N-n) + eta/2*(N-n)^2, whose gradient is built
    from the geometry module's own energy gradient (multiplier zero), so the objective and the
    gradient handed to the optimiser are an exact pair; mu and eta are updated between relaxations
    (a six-step, ten-times ladder).  Stage B polishes the bordered stationarity system with Newton
    steps under a residual-norm merit, which is the system whose residual the protocol gates.
    """
    kap = 1.0 / radius
    Na, Nphi = section.Na, section.Nphi
    N = Na * Nphi
    constraint_c = (2.0 * section.weights(kap)[0]).ravel()
    direction = np.concatenate([np.zeros(N), constraint_c])
    f = np.clip(np.array(f0, dtype=np.float64).copy(), 0.0, 1.0)
    c = enforce_population(section, radius,
                           np.maximum(np.array(c0, dtype=np.float64).copy(), 0.0), density)
    lam, _ = anchor_multiplier(section, radius, w, density, f, c)

    def profile(vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Unprojected: the population constraint is carried by the augmented Lagrangian below,
        # not projected out of the variables. Projecting a rescale inside the objective while
        # handing the optimiser a projected gradient gives an inconsistent pair (the rescale's
        # Jacobian is a rank-one term along c, the projection removes the direction
        # 2*VC*c, and VC varies spatially, so the two are not parallel); the measured
        # finite-difference mismatch of that pair was 1-25% relative.
        return vector[:N].reshape(Na, Nphi), vector[N:].reshape(Na, Nphi)

    def deficit_of(field_c: np.ndarray) -> float:
        return float(section.population(field_c, kap)) - density

    def objective(vector: np.ndarray, penalty: float, multiplier: float) -> float:
        field_f, field_c = profile(vector)
        deficit = deficit_of(field_c)
        return (float(section.energy(field_f, field_c, kap, w, radius))
                + multiplier * deficit + 0.5 * penalty * deficit * deficit)

    def objective_gradient(vector: np.ndarray, penalty: float, multiplier: float) -> np.ndarray:
        field_f, field_c = profile(vector)
        Rp, Rc, _ = section.gradient(field_f, field_c, kap, w, radius, density, 0.0)
        deficit = deficit_of(field_c)
        return (np.concatenate([Rp.ravel(), Rc.ravel()])
                + (multiplier + penalty * deficit) * direction)

    initial = np.concatenate([f.ravel(), c.ravel()])
    iterations = 0
    polished = 0
    multiplier = 0.0
    penalty = 1.0
    for _ in range(STAGE_A_PENALTY_STEPS):
        result = minimize(objective, initial, args=(penalty, multiplier),
                          jac=objective_gradient, method="L-BFGS-B",
                          options={"maxiter": STAGE_A_MAXITER, "maxfun": STAGE_A_MAXFUN,
                                   "ftol": 1e-16, "gtol": 1e-14})
        iterations += int(result.nit)
        stage_a_status = str(result.message)
        initial = result.x
        multiplier += penalty * deficit_of(profile(initial)[1])
        penalty *= 10.0
    f, c = profile(initial)
    lam, _ = anchor_multiplier(section, radius, w, density, f, c)

    for iteration in range(1, MAX_ITERATIONS + 1):
        polished = iteration
        Rp, Rc, rc = section.gradient(f, c, kap, w, radius, density, lam)
        residual_vector = np.concatenate([Rp.ravel(), Rc.ravel(), [rc]])
        norm = float(np.linalg.norm(residual_vector))
        if float(np.max(np.abs(residual_vector))) <= RESIDUAL_TOL:
            break
        jacobian = section.hessian(f, c, kap, w, radius, lam).tocsc()
        identity = sp.eye(2 * N + 1, format="csc")
        shift = 0.0
        accepted = False
        for _ in range(14):
            try:
                step_vector = spl.spsolve(jacobian + shift * identity, -residual_vector)
            except Exception:
                step_vector = np.full(2 * N + 1, np.nan)
            if np.all(np.isfinite(step_vector)):
                step = 1.0
                for _ in range(24):
                    trial_f = np.clip(f + step * step_vector[:N].reshape(Na, Nphi), 0.0, 1.0)
                    trial_c = enforce_population(
                        section, radius,
                        np.maximum(c + step * step_vector[N:2 * N].reshape(Na, Nphi), 0.0),
                        density)
                    trial_lam = lam + step * float(step_vector[2 * N])
                    Rp2, Rc2, rc2 = section.gradient(trial_f, trial_c, kap, w, radius, density,
                                                     trial_lam)
                    trial = np.concatenate([Rp2.ravel(), Rc2.ravel(), [rc2]])
                    if float(np.linalg.norm(trial)) < norm:
                        f, c, lam = trial_f, trial_c, trial_lam
                        accepted = True
                        break
                    step *= 0.5
            if accepted:
                break
            shift = 1e-12 if shift == 0.0 else shift * 100.0
        if not accepted:
            break

    Rp, Rc, rc = section.gradient(f, c, kap, w, radius, density, lam)
    residual = float(np.max(np.abs(np.concatenate([Rp.ravel(), Rc.ravel()]))))
    bordered = float(np.max(np.abs(np.concatenate([Rp.ravel(), Rc.ravel(), [rc]]))))
    return {
        "f": f,
        "c": c,
        "multiplier": float(lam),
        "residual": residual,
        "bordered_residual": bordered,
        "iterations": int(iterations + polished),
        "stage_a_status": stage_a_status,
        "converged": bool(bordered <= RESIDUAL_TOL),
    }


def energy_breakdown(section: Any, radius: float, w: float, f: np.ndarray,
                     c: np.ndarray) -> tuple[float, float]:
    """Static (including gradients) and winding parts of the exact torus energy."""
    kap = 1.0 / radius
    VC, Fa, Fp, g = section.weights(kap)
    ip = np.empty_like(f); ip[:-1] = f[1:]; ip[-1] = 1.0
    im = np.empty_like(f); im[1:] = f[:-1]; im[0] = 0.0
    jp = np.roll(f, -1, axis=1)
    grad_f = np.sum(Fa[1:] * (ip - f) ** 2) + np.sum(Fp * (jp - f) ** 2)
    cip = np.empty_like(c); cip[:-1] = c[1:]; cip[-1] = 0.0
    cim = np.empty_like(c); cim[1:] = c[:-1]; cim[0] = 0.0
    cjp = np.roll(c, -1, axis=1)
    grad_c = np.sum(Fa[1:] * (cip - c) ** 2) + np.sum(Fp * (cjp - c) ** 2)
    potential = ((U_RHO / 4.0) * (f * f - 1.0) ** 2
                 + (B_COEF - H_COEF + H_COEF * f * f) * c * c
                 + (U_C / 2.0) * c ** 4)
    twist = (tube_geometry.GRAD_C * w * w / radius ** 2) / np.maximum(g, 1e-12) ** 2
    static = float(np.sum(VC * potential) + tube_geometry.GRAD_F * grad_f
                   + tube_geometry.GRAD_C * grad_c)
    winding = float(np.sum(VC * twist * c * c))
    return static, winding


def support_geometry(section: Any, radius: float, c: np.ndarray) -> tuple[float, float, float]:
    """Containment radius, minimum metric factor over the support, outer-decile fraction."""
    VC = section.weights(1.0 / radius)[0]
    population_cells = VC * c * c
    total = float(np.sum(population_cells))
    a = section.a
    cumulative = np.cumsum(np.sum(population_cells, axis=1))
    if total <= 0.0:
        return float(a[-1]), 0.0, 0.0
    index = int(np.searchsorted(cumulative, 0.999 * total))
    index = min(index, a.size - 1)
    a99 = float(a[index])
    g = section.weights(1.0 / radius)[3]
    mask = a <= a99 + 1e-12
    min_metric = float(np.min(g[mask]))
    outer = float(np.sum(population_cells[a > 0.9 * section.a[-1] * 1.0]) / total)
    return a99, min_metric, outer


def scan_row(section: Any, radius: float, w: float, density: float, state: dict[str, Any]) -> dict[str, Any]:
    static, winding = energy_breakdown(section, radius, w, state["f"], state["c"])
    a99, min_metric, outer = support_geometry(section, radius, state["c"])
    population = section.population(state["c"], 1.0 / radius)
    return {
        "radius": float(radius),
        "density": float(density),
        "winding": int(WINDING) if w == 1 else (0 if w == 0 else -1),
        "Na": int(section.Na),
        "Nphi": int(section.Nphi),
        "amax": float(section.a[-1] + 0.5 * section.da),
        "energy": float(static + winding),
        "population": float(population),
        "multiplier": float(state["multiplier"]),
        "residual": float(state["residual"]),
        "iterations": int(state["iterations"]),
        "converged": bool(state["converged"]),
        "a99": float(a99),
        "min_metric_factor": float(min_metric),
        "outer_decile_fraction": float(outer),
        "static_energy": float(static),
        "twist_energy": float(winding),
    }


def profile_row(section: Any, radius: float, w: float, density: float, purpose: str,
                state: dict[str, Any]) -> dict[str, Any]:
    row = scan_row(section, radius, w, density, state)
    row["purpose"] = purpose
    row["f"] = np.asarray(state["f"], dtype=np.float64).tolist()
    row["c"] = np.asarray(state["c"], dtype=np.float64).tolist()
    return row


def charge_mass(energy: float, radius: float, density: float, charge: float) -> float:
    """Registered mass: loop length times the cross-section energy, plus the charge term."""
    return float(2.0 * math.pi * radius * energy) + charge ** 2 / (
        8.0 * math.pi * A_COEF * radius * density)


def mass_curve(rows: list[dict[str, Any]], charge: float) -> list[dict[str, Any]]:
    best: dict[float, dict[str, Any]] = {}
    for row in rows:
        radius = float(row["radius"])
        density = float(row["density"])
        mass = charge_mass(row["energy"], radius, density, charge)
        if radius not in best or mass < best[radius]["mass"]:
            best[radius] = {"radius": radius, "density": density, "mass": mass, "row": row}
    return [best[radius] for radius in sorted(best)]


def refine_radii(coarse_radii: list[float], argmin_index: int) -> list[float]:
    low = coarse_radii[max(argmin_index - 1, 0)]
    high = coarse_radii[min(argmin_index + 1, len(coarse_radii) - 1)]
    centre = coarse_radii[argmin_index]
    radii = sorted({round(centre + offset * REFINE_DELTA, 10) for offset in REFINE_OFFSETS
                    if low - 1e-12 <= centre + offset * REFINE_DELTA <= high + 1e-12})
    if not radii:
        radii = [centre]
    return radii


def curvature(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: row["radius"])
    radii = [row["radius"] for row in rows]
    masses = [row["mass"] for row in rows]
    index = int(min(range(len(masses)), key=lambda i: masses[i]))
    result: dict[str, Any] = {
        "radius": radii[index],
        "mass": masses[index],
        "density": rows[index]["density"],
        "index": index,
        "count": len(rows),
        "curvature_fit": None,
        "curvature_discrete": None,
        "radius_derivative_discrete": None,
    }
    if 0 < index < len(rows) - 1:
        left, centre, right = radii[index - 1], radii[index], radii[index + 1]
        span = right - left
        result["curvature_discrete"] = float(
            2.0 * ((masses[index + 1] - masses[index]) / (right - centre)
                   - (masses[index] - masses[index - 1]) / (centre - left)) / span)
        result["radius_derivative_discrete"] = float(
            (masses[index + 1] - masses[index - 1]) / span)
        window = range(max(index - 2, 0), min(index + 3, len(rows)))
        offsets = np.array([radii[i] - centre for i in window])
        values = np.array([masses[i] for i in window])
        if offsets.size >= 3:
            design = np.column_stack([np.ones_like(offsets), offsets ** 2])
            coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
            result["curvature_fit"] = float(2.0 * coefficients[1])
    return result


def tangent_basis(gradient: np.ndarray) -> Any:
    """Sparse basis of the Euclidean complement of the constraint gradient."""
    size = gradient.size
    pivot = int(np.argmax(np.abs(gradient)))
    keep = np.array([index for index in range(size) if index != pivot], dtype=np.int64)
    columns = np.concatenate([np.arange(keep.size, dtype=np.int64),
                              np.arange(keep.size, dtype=np.int64)])
    rows = np.concatenate([keep, np.full(keep.size, pivot, dtype=np.int64)])
    values = np.concatenate([np.ones(keep.size), -gradient[keep] / gradient[pivot]])
    return sp.csr_matrix((values, (rows, columns)), shape=(size, keep.size))


def constrained_spectrum(section: Any, radius: float, w: complex, density: float,
                         state: dict[str, Any], count: int = SPECTRUM_MODE_COUNT) -> dict[str, Any]:
    """Lowest generalized eigenvalues of the exact Hessian on the population tangent space."""
    kap = 1.0 / radius
    Na, Nphi = section.Na, section.Nphi
    N = Na * Nphi
    f = np.asarray(state["f"], dtype=np.float64)
    c = np.asarray(state["c"], dtype=np.float64)
    lam = float(state["multiplier"])
    hessian = section.hessian(f, c, kap, w, radius, lam)[:2 * N, :2 * N].tocsc()
    measure = section.weights(kap)[0].ravel()
    mass = sp.diags(np.concatenate([C_PSI * measure, 2.0 * A_COEF * measure])).tocsc()
    gradient = np.concatenate([np.zeros(N), 2.0 * measure * c.ravel()])
    basis = tangent_basis(gradient)
    reduced_hessian = (basis.T @ hessian @ basis).tocsc()
    reduced_mass = (basis.T @ mass @ basis).tocsc()
    scale = float(np.max(np.abs(reduced_hessian.diagonal()))) if reduced_hessian.nnz else 1.0
    shift = -1e-6 * max(scale, 1e-30)
    try:
        values, vectors = spl.eigsh(reduced_hessian, k=count, M=reduced_mass, sigma=shift,
                                    which="LM", maxiter=20000)
    except Exception as error:  # pragma: no cover - reported as a diagnostic
        return {"error": f"{type(error).__name__}: {error}", "min_eigenvalue": float("nan")}
    order = np.argsort(values)
    values = values[order]
    vectors = vectors[:, order]
    residual = 0.0
    for index in range(values.size):
        vector = vectors[:, index]
        image = reduced_hessian @ vector - values[index] * (reduced_mass @ vector)
        denominator = float(np.linalg.norm(reduced_mass @ vector)) or 1.0
        residual = max(residual, float(np.linalg.norm(image) / denominator))
    harmonics: list[int] = []
    for index in range(min(3, values.size)):
        full = np.asarray(basis @ vectors[:, index]).ravel()[N:]
        grid = full.reshape(Na, Nphi)
        power = []
        for mode in range(0, 5):
            weight = np.exp(-2j * math.pi * mode * np.arange(Nphi) / Nphi)
            power.append(float(np.sum(np.abs(grid @ weight) ** 2)))
        harmonics.append(int(np.argmax(power)))
    return {
        "radius": float(radius),
        "density": float(density),
        "Na": int(Na),
        "Nphi": int(Nphi),
        "amax": float(section.a[-1] + 0.5 * section.da),
        "eigenvalues": [float(value) for value in values],
        "frequencies": [float(math.sqrt(value)) if value > 0.0 else None for value in values],
        "min_eigenvalue": float(values[0]),
        "dominant_harmonics": harmonics,
        "eigenpair_residual": float(residual),
        "constraint": "fixed cross-section population",
    }


def lift_state(section: Any, source: dict[str, Any], density: float,
               density_source: float) -> tuple[np.ndarray, np.ndarray]:
    """Carry a relaxed two-dimensional cross-section onto this section's grid.

    The grid spans the same fraction of the section for every radius, so the profile is
    resampled in the normalized radial coordinate and the carrier's position in the disk is
    preserved.  The population is rescaled and re-enforced by the caller.
    """
    a_source = np.asarray(source["a"], dtype=np.float64)
    spacing = float(a_source[1] - a_source[0]) if a_source.size > 1 else 1.0
    extent = float(a_source[-1] + 0.5 * spacing)
    target = section.a / extent * float(a_source[-1] + 0.5 * spacing)
    field_f = np.empty((section.Na, section.Nphi), dtype=np.float64)
    field_c = np.empty((section.Na, section.Nphi), dtype=np.float64)
    source_f = np.asarray(source["f"], dtype=np.float64)
    source_c = np.asarray(source["c"], dtype=np.float64)
    if source_f.ndim == 1:
        source_f = np.repeat(source_f[:, None], section.Nphi, axis=1)
        source_c = np.repeat(source_c[:, None], section.Nphi, axis=1)
    for column in range(section.Nphi):
        field_f[:, column] = np.interp(target, a_source, source_f[:, column],
                                       left=source_f[0, column], right=1.0)
        field_c[:, column] = np.interp(target, a_source, source_c[:, column],
                                       left=source_c[0, column], right=0.0)
    field_c = field_c * math.sqrt(density / max(density_source, 1e-300))
    return field_f, field_c


def position_seed(section: Any, source: dict[str, Any], radius: float, density: float,
                  a0: float, phi0: float) -> tuple[np.ndarray, np.ndarray]:
    """Lift the registered flat profile onto a polar position of the torus section.

    The carrier of the flat problem is a localized cross-section around the axis; in the
    exact toroidal metric that carrier can sit anywhere in the disk.  This places the flat
    profile at polar position ``(a0, phi0)`` and rescales it to the requested population.
    """
    a = section.a[:, None]
    phi = section.phi[None, :]
    distance = np.sqrt(np.maximum(a ** 2 + a0 ** 2 - 2.0 * a * a0 * np.cos(phi - phi0), 0.0))
    source_a = np.asarray(source["a"], dtype=np.float64)
    f = np.interp(distance.ravel(), source_a, source["f"]).reshape(section.Na, section.Nphi)
    c = np.interp(distance.ravel(), source_a, source["c"]).reshape(section.Na, section.Nphi)
    c = enforce_population(section, radius, c, density)
    return np.clip(f, 0.0, 1.0), c


def best_position_seed(section: Any, radius: float, winding: float, density: float,
                       flat: dict[str, Any]) -> tuple[float, np.ndarray, np.ndarray]:
    """Lowest-energy lift of the registered flat profile over the sampled disk positions."""
    amax = float(section.a[-1] + 0.5 * section.da)
    best: tuple[float, np.ndarray, np.ndarray] | None = None
    for fraction in POSITION_FRACTIONS:
        for phi0 in POSITION_ANGLES:
            f0, c0 = position_seed(section, flat, radius, density, fraction * amax, phi0)
            value = float(section.energy(f0, c0, 1.0 / radius, winding, radius))
            if best is None or value < best[0]:
                best = (value, f0, c0)
    assert best is not None
    return best


def run_scan(radii: tuple[float, ...], densities: tuple[float, ...], winding: float,
             seed: dict[str, Any] | None, Na: int = SCAN_NA, Nphi: int = SCAN_NPHI,
             profiles: dict[tuple[float, float], dict[str, Any]] | None = None,
             store: set[tuple[float, float]] | None = None
             ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Relax every scheduled (radius, density) and return rows plus the last state per radius.

    Radii are visited from the smallest curvature to the largest, so each radius warm-starts
    from the previously relaxed one.  At every radius the carried profile competes with
    lifted copies of the registered flat profile placed at sampled positions of the disk,
    because the exact toroidal metric lets the carrier leave the axis.
    """
    rows: list[dict[str, Any]] = []
    last: dict[str, Any] = {}
    current = seed
    for radius in sorted(radii, reverse=True):
        section = section_for(radius, Na, Nphi)
        best: tuple[float, np.ndarray, np.ndarray, float] | None = None
        if current is not None:
            f0, c0 = lift_state(section, current, densities[0], current["density"])
            c0 = enforce_population(section, radius, c0, densities[0])
            try:
                best = (section.energy(f0, c0, 1.0 / radius, winding, radius), f0, c0,
                        float(current["multiplier"]))
            except Exception:  # pragma: no cover - a mismatched grid falls back to the sketch
                best = None
        if seed is not None:
            reference = flat_seed(densities[0]) if seed.get("density") != densities[0] else seed
            value, f0, c0 = best_position_seed(section, radius, winding, densities[0], reference)
            if best is None or value < best[0]:
                best = (value, f0, c0, 0.0)
        if best is None:  # pragma: no cover - the caller always supplies a seed
            raise RuntimeError("scan requires a seed")
        state: dict[str, Any] | None = None
        for density in densities:
            if state is None:
                _, f0, c0, lam0 = best
                state = solve_section(section, radius, winding, density, f0, c0, lam0)
            else:
                scale = math.sqrt(density / max(state["density"], 1e-300))
                f0, c0 = state["f"], state["c"] * scale
                state = solve_section(section, radius, winding, density, f0, c0,
                                      float(state["multiplier"]))
            state["density"] = float(density)
            rows.append(scan_row(section, radius, winding, density, state))
            if profiles is not None and store is not None and (radius, density) in store:
                profiles[(radius, density)] = profile_row(
                    section, radius, winding, density, "stored", state)
        last[f"{radius}"] = {
            "a": section.a.copy(),
            "f": state["f"].copy(),
            "c": state["c"].copy(),
            "density": float(densities[-1]),
            "radius": float(radius),
            "multiplier": float(state["multiplier"]),
        }
        current = last[f"{radius}"]
    return rows, last


def flat_seed(density: float) -> dict[str, Any]:
    """Registered flat-tube profile as the initial cross-section of the first solve."""
    tube = tube_geometry.Tube(M=200, rmax=8.0)
    state = tube.solve(density, sweeps=8)
    return {
        "a": tube.r.copy(),
        "f": np.asarray(state["f"], dtype=np.float64),
        "c": np.asarray(state["c"], dtype=np.float64),
        "density": float(density),
        "multiplier": float(state["mu"]),
    }


def freeze_sources(output: Path) -> tuple[dict[str, Any], Path, Path]:
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
    identities = {}
    payloads = {}
    for name, path in sources.items():
        payload = path.read_bytes()
        payloads[name] = payload
        identities[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_bytes(payload),
            "snapshot": path.name,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for name, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[name])
    manifest = {
        "schema": "cassi.matter-formation.thick-torus-gap.inputs.v1",
        "identities": identities,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest, manifest_path, snapshot_dir


def run(output: Path) -> int:
    manifest, manifest_path, snapshot_dir = freeze_sources(output)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "identities": manifest["identities"],
        "platform": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "coefficients": {
            "a": A_COEF,
            "c_psi": C_PSI,
            "u_rho": U_RHO,
            "u_C": U_C,
            "k_cx": K_CX,
            "b": B_COEF,
            "h": H_COEF,
            "omega_inf": OMEGA_INF,
        },
        "schedule": {
            "radii": list(RADII),
            "densities": list(DENSITIES),
            "charges": list(CHARGES),
            "winding": WINDING,
            "scan_grid": {"Na": SCAN_NA, "Nphi": SCAN_NPHI, "amax_rule": "0.9*R"},
            "validation_grid": {"Na": VALIDATION_NA, "Nphi": VALIDATION_NPHI,
                                "amax": VALIDATION_AMAX},
            "refinement": {"delta_R": REFINE_DELTA, "offsets": list(REFINE_OFFSETS)},
            "resolution_grid": {"Na": RESOLUTION_NA, "Nphi": RESOLUTION_NPHI},
            "spectrum_grid": {"Na": SPECTRUM_NA, "Nphi": SPECTRUM_NPHI},
            "spectrum_resolution_grid": {"Na": SPECTRUM_RESOLUTION_NA,
                                         "Nphi": SPECTRUM_RESOLUTION_NPHI},
            "convergence": {"residual_tol": RESIDUAL_TOL, "max_iterations": MAX_ITERATIONS,
                            "max_failed_solves": MAX_FAILED_SOLVES},
            "independent_points": [list(point) for point in INDEPENDENT_POINTS],
        },
        "validation": [],
        "scan": {"w1": [], "w0": []},
        "refinement": {"w1": []},
        "profiles": [],
        "summary": {},
        "spectrum": {},
        "controls": {},
        "classification": {},
        "protocol_additions": [
            {
                "name": "spectrum_eigenpair_residual",
                "reason": (
                    "the sparse shift-invert solve is iterative; recording the relative "
                    "eigenpair residual makes a non-converged eigenpair visible"
                ),
            },
            {
                "name": "profiles_for_independent_points",
                "reason": (
                    "the three rows the independent program re-solves are stored so it can "
                    "warm-start from the same configuration"
                ),
            },
        ],
        "checks": [],
        "failures": [],
        "status": "PASS",
    }

    coefficients_ok = (
        tube_geometry.A_COEF == A_COEF
        and tube_geometry.CPSI == C_PSI
        and tube_geometry.K_CX == K_CX
        and tube_geometry.UR == U_RHO
        and tube_geometry.UC == U_C
        and tube_geometry.B_COEF == B_COEF
        and tube_geometry.H_COEF == H_COEF
        and tube_geometry.GRAD_F == 0.5
        and tube_geometry.GRAD_C == 0.5
        and abs(tube_geometry.OMEGA_INF - OMEGA_INF) < 1e-12
    )
    add_check(receipt, "coefficient_agreement", coefficients_ok,
              {"geometry_module": tube_geometry.SCHEMA if hasattr(tube_geometry, "SCHEMA") else None})

    # --- validation stage -------------------------------------------------
    validation_rows = []
    for winding, label in ((0.0, "validation_flat_untwisted"), (1.0, "validation_flat_twisted")):
        section = section_for(64.0, VALIDATION_NA, VALIDATION_NPHI, amax=VALIDATION_AMAX)
        seed = flat_seed(math.pi)
        f0, c0 = interp_seed(section, seed["a"], seed["f"], seed["c"], math.pi, math.pi)
        state = solve_section(section, 64.0, winding, math.pi, f0, c0, seed["multiplier"])
        row = scan_row(section, 64.0, winding, math.pi, state)
        row["purpose"] = label
        row["energy_per_length"] = row["energy"]
        row["flat_energy_per_length"] = FLAT_ENERGY_PER_LENGTH_PI
        row["relative_error"] = normalized_error(row["energy_per_length"], FLAT_ENERGY_PER_LENGTH_PI)
        validation_rows.append(row)
        receipt["profiles"].append(profile_row(section, 64.0, winding, math.pi, label, state))
    receipt["validation"] = validation_rows
    add_check(receipt, "validation_flat_untwisted",
              bool(validation_rows[0]["converged"]
                   and validation_rows[0]["relative_error"] <= VALIDATION_TOL),
              {"relative_error": validation_rows[0]["relative_error"],
               "residual": validation_rows[0]["residual"]})
    add_check(receipt, "validation_flat_twisted",
              bool(validation_rows[1]["converged"]
                   and validation_rows[1]["relative_error"] <= VALIDATION_TOL),
              {"relative_error": validation_rows[1]["relative_error"],
               "twist_energy": validation_rows[1]["twist_energy"],
               "residual": validation_rows[1]["residual"]})

    # --- scan -------------------------------------------------------------
    seed = flat_seed(DENSITIES[0])
    stored_profiles: dict[tuple[float, float], dict[str, Any]] = {}
    store_coarse = {(radius, density) for radius, density in INDEPENDENT_POINTS
                    if radius in RADII and density in DENSITIES}
    scan_rows, _ = run_scan(RADII, DENSITIES, WINDING, seed, profiles=stored_profiles,
                            store=store_coarse)
    receipt["scan"]["w1"] = scan_rows

    expected = len(RADII) * len(DENSITIES)
    rows_complete = len(scan_rows) == expected
    finite = all(math.isfinite(row["energy"]) and math.isfinite(row["population"])
                 for row in scan_rows)
    add_check(receipt, "scan_rows_complete", bool(rows_complete and finite),
              {"rows": len(scan_rows), "expected": expected})

    constraint_ok = all(abs(row["population"] - row["density"])
                        <= 1e-9 * max(1.0, row["density"]) for row in scan_rows)
    add_check(receipt, "constraint_satisfied", bool(constraint_ok), {"rows": len(scan_rows)})

    decomposition_ok = all(
        abs(row["static_energy"] + row["twist_energy"] - row["energy"])
        <= 1e-12 * max(1.0, abs(row["energy"])) for row in scan_rows)
    add_check(receipt, "energy_decomposition", bool(decomposition_ok), {"rows": len(scan_rows)})

    # --- transported feasibility (V3) -------------------------------------
    transported = (2.0 * math.pi * 8.0 * FLAT_ENERGY_PER_LENGTH_5
                   + math.pi * K_CX * WINDING ** 2 * 5.0 * TRANSPORTED_METRIC_FACTOR_8 / 8.0)
    row_8_5 = min(scan_rows, key=lambda row: abs(row["radius"] - 8.0) + abs(row["density"] - 5.0))
    relaxed_total = 2.0 * math.pi * 8.0 * row_8_5["energy"]
    feasibility_ok = bool(row_8_5["converged"]
                          and relaxed_total <= transported * (1.0 + TRANSPORTED_TOL))
    receipt["validation"].append({
        "purpose": "validation_transported_feasibility",
        "radius": 8.0,
        "density": 5.0,
        "transported_mass_without_charge": transported,
        "relaxed_energy_per_length": row_8_5["energy"],
        "relaxed_mass_without_charge": relaxed_total,
        "relative_deficit": (transported - relaxed_total) / transported,
        "passed": feasibility_ok,
    })
    add_check(receipt, "validation_transported_feasibility", feasibility_ok,
              {"relaxed_mass_without_charge": relaxed_total, "transported": transported,
               "relative_deficit": (transported - relaxed_total) / transported})

    # --- coarse mass curves and refinement --------------------------------
    coarse_curves = {}
    refinement_radii: dict[float, list[float]] = {}
    for charge in CHARGES:
        curve = mass_curve(scan_rows, charge)
        coarse_curves[charge] = curve
        index = int(min(range(len(curve)), key=lambda i: curve[i]["mass"]))
        refinement_radii[charge] = refine_radii([entry["radius"] for entry in curve], index)

    union_radii = sorted({radius for radii in refinement_radii.values() for radius in radii})
    store_refined = {(radius, density) for radius, density in INDEPENDENT_POINTS
                     if radius in set(union_radii) and density in DENSITIES}
    refined_rows, _ = run_scan(tuple(union_radii), DENSITIES, WINDING, seed,
                               profiles=stored_profiles, store=store_refined)
    receipt["refinement"]["w1"] = refined_rows

    # --- winding-off control scan -----------------------------------------
    seed_w0 = flat_seed(DENSITIES[0])
    w0_rows, _ = run_scan(RADII, DENSITIES, 0.0, seed_w0)
    receipt["scan"]["w0"] = w0_rows

    # --- summaries --------------------------------------------------------
    def entry_for(rows: list[dict[str, Any]], radius: float, density: float) -> dict[str, Any]:
        for row in rows:
            if abs(row["radius"] - radius) < 1e-9 and abs(row["density"] - density) < 1e-9:
                return row
        raise KeyError((radius, density))

    for charge in CHARGES:
        curve = coarse_curves[charge]
        coarse_index = int(min(range(len(curve)), key=lambda i: curve[i]["mass"]))
        coarse_interior = 0 < coarse_index < len(curve) - 1
        refined_curve = mass_curve(refined_rows, charge)
        selected = [entry for entry in refined_curve
                    if entry["radius"] in refinement_radii[charge]]
        if not selected:
            selected = refined_curve
        shape = curvature(selected)
        refined_radius = shape["radius"]
        refined_density = shape["density"]
        row = entry_for(scan_rows + refined_rows, refined_radius, refined_density)
        temporal = charge ** 2 / (8.0 * math.pi * A_COEF * refined_radius * refined_density)
        mass = 2.0 * math.pi * refined_radius * row["energy"] + temporal
        threshold = OMEGA_INF * abs(charge)
        a99 = row["a99"]
        min_metric = row["min_metric_factor"]
        outer = row["outer_decile_fraction"]
        density_index = int(min(range(len(DENSITIES)), key=lambda i: abs(DENSITIES[i] - refined_density)))
        receipt["summary"][f"{int(charge)}"] = {
            "charge": float(charge),
            "threshold": float(threshold),
            "coarse_argmin_radius": float(curve[coarse_index]["radius"]),
            "coarse_argmin_density": float(curve[coarse_index]["density"]),
            "coarse_argmin_interior": bool(coarse_interior),
            "coarse_mass_curve": [[float(entry["radius"]), float(entry["mass"])] for entry in curve],
            "refined_set": [float(radius) for radius in refinement_radii[charge]],
            "refined_mass_curve": [[float(entry["radius"]), float(entry["mass"])] for entry in selected],
            "refined_radius": float(refined_radius),
            "refined_density": float(refined_density),
            "refined_argmin_index": int(shape["index"]),
            "density_schedule_index": int(density_index),
            "density_endpoint": bool(density_index in (0, len(DENSITIES) - 1)),
            "mass": float(mass),
            "static_energy": float(row["static_energy"]),
            "twist_energy": float(row["twist_energy"]),
            "temporal_charge_energy": float(temporal),
            "margin": float(threshold - mass),
            "bound": bool(mass < threshold),
            "curvature_fit": shape["curvature_fit"],
            "curvature_discrete": shape["curvature_discrete"],
            "radius_derivative_discrete": shape["radius_derivative_discrete"],
            "a99": float(a99),
            "a99_over_R": float(a99 / refined_radius),
            "min_metric_factor": float(min_metric),
            "outer_decile_fraction": float(outer),
            "geometry_qualified": bool(a99 / refined_radius <= GEOMETRY_RATIO_GATE
                                       and outer <= OUTER_DECILE_TOL),
        }

    # --- stored profiles --------------------------------------------------
    for (radius, density), row in sorted(stored_profiles.items()):
        receipt["profiles"].append(row)

    add_check(receipt, "stored_profiles_valid",
              bool(all(len(row["f"]) == row["Na"] and len(row["f"][0]) == row["Nphi"]
                       and len(row["c"]) == row["Na"] and len(row["c"][0]) == row["Nphi"]
                       for row in receipt["profiles"])),
              {"profiles": len(receipt["profiles"])})

    # --- constrained spectrum ---------------------------------------------
    for charge in CHARGES:
        summary = receipt["summary"][f"{int(charge)}"]
        section = section_for(summary["refined_radius"], SPECTRUM_NA, SPECTRUM_NPHI)
        value, f0, c0 = best_position_seed(section, summary["refined_radius"], WINDING,
                                           summary["refined_density"],
                                           flat_seed(summary["refined_density"]))
        state = solve_section(section, summary["refined_radius"], WINDING,
                              summary["refined_density"], f0, c0, 0.0)
        spectrum = constrained_spectrum(section, summary["refined_radius"], WINDING,
                                        summary["refined_density"], state)
        spectrum["stationarity_residual"] = float(state["residual"])
        spectrum["converged"] = bool(state["converged"])
        receipt["spectrum"][f"{int(charge)}"] = spectrum

    add_check(receipt, "spectrum_defined",
              bool(all(math.isfinite(receipt["spectrum"][f"{int(charge)}"].get("min_eigenvalue", float("nan")))
                       for charge in CHARGES)),
              {f"{int(charge)}": receipt["spectrum"][f"{int(charge)}"].get("min_eigenvalue")
               for charge in CHARGES})
    add_check(receipt, "spectrum_eigenpair_residual",
              bool(all(receipt["spectrum"][f"{int(charge)}"].get("eigenpair_residual", math.inf) < 1e-6
                       for charge in CHARGES)),
              {f"{int(charge)}": receipt["spectrum"][f"{int(charge)}"].get("eigenpair_residual")
               for charge in CHARGES})

    # --- controls ---------------------------------------------------------
    controls: dict[str, Any] = {}

    resolution_rows = []
    for radius, density in ((7.0, 5.0),):
        coarse = entry_for(scan_rows, radius, density)
        section = section_for(radius, RESOLUTION_NA, RESOLUTION_NPHI)
        _, f0, c0 = best_position_seed(section, radius, WINDING, density, flat_seed(density))
        state = solve_section(section, radius, WINDING, density, f0, c0, 0.0)
        fine = scan_row(section, radius, WINDING, density, state)
        resolution_rows.append({
            "radius": radius,
            "density": density,
            "coarse_energy": coarse["energy"],
            "fine_energy": fine["energy"],
            "relative_difference": normalized_error(fine["energy"], coarse["energy"]),
            "fine_residual": fine["residual"],
            "fine_converged": fine["converged"],
        })
    for charge in CHARGES:
        summary = receipt["summary"][f"{int(charge)}"]
        radius, density = summary["refined_radius"], summary["refined_density"]
        coarse = entry_for(scan_rows + refined_rows, radius, density)
        section = section_for(radius, RESOLUTION_NA, RESOLUTION_NPHI)
        _, f0, c0 = best_position_seed(section, radius, WINDING, density, flat_seed(density))
        state = solve_section(section, radius, WINDING, density, f0, c0, 0.0)
        fine = scan_row(section, radius, WINDING, density, state)
        resolution_rows.append({
            "radius": radius,
            "density": density,
            "charge": charge,
            "coarse_energy": coarse["energy"],
            "fine_energy": fine["energy"],
            "relative_difference": normalized_error(fine["energy"], coarse["energy"]),
            "fine_residual": fine["residual"],
            "fine_converged": fine["converged"],
        })
    controls["grid_resolution"] = resolution_rows
    add_check(receipt, "grid_resolution",
              bool(all(row["fine_converged"] and row["relative_difference"] <= GRID_REL_TOL
                       for row in resolution_rows)),
              {"worst": max(row["relative_difference"] for row in resolution_rows)})

    spectrum_resolution = {}
    for charge in CHARGES:
        summary = receipt["summary"][f"{int(charge)}"]
        if charge != max(CHARGES):
            continue
        section = section_for(summary["refined_radius"], SPECTRUM_RESOLUTION_NA,
                              SPECTRUM_RESOLUTION_NPHI)
        value, f0, c0 = best_position_seed(section, summary["refined_radius"], WINDING,
                                           summary["refined_density"],
                                           flat_seed(summary["refined_density"]))
        state = solve_section(section, summary["refined_radius"], WINDING,
                              summary["refined_density"], f0, c0, 0.0)
        fine = constrained_spectrum(section, summary["refined_radius"], WINDING,
                                    summary["refined_density"], state)
        base = receipt["spectrum"][f"{int(charge)}"]["min_eigenvalue"]
        spectrum_resolution = {
            "charge": charge,
            "coarse_min_eigenvalue": base,
            "fine_min_eigenvalue": fine.get("min_eigenvalue"),
            "same_sign": bool((base > 0) == (fine.get("min_eigenvalue", 0.0) > 0)),
            "absolute_difference": abs(fine.get("min_eigenvalue", float("nan")) - base),
            "tolerance": SPECTRUM_RESOLUTION_TOL * max(1.0, abs(base)),
            "fine_residual": fine.get("eigenpair_residual"),
        }
    controls["spectrum_resolution"] = spectrum_resolution
    add_check(receipt, "spectrum_resolution",
              bool(spectrum_resolution.get("same_sign")
                   and spectrum_resolution.get("absolute_difference", math.inf)
                   <= spectrum_resolution.get("tolerance", 0.0)),
              spectrum_resolution)

    mutation = {}
    sample = receipt["profiles"][0]
    section = section_for(sample["radius"], sample["Na"], sample["Nphi"], amax=sample["amax"])
    recomputed = section.energy(np.asarray(sample["f"]), np.asarray(sample["c"]),
                                1.0 / sample["radius"], sample["winding"], sample["radius"])
    mutation["clean_error"] = normalized_error(recomputed, sample["energy"])
    mutation["clean_passes"] = bool(mutation["clean_error"] <= RECONSTRUCTION_TOL)
    mutated = float(sample["energy"]) * (1.0 + 1e-6)
    mutation["mutated_error"] = normalized_error(recomputed, mutated)
    mutation["mutated_trips"] = bool(mutation["mutated_error"] > RECONSTRUCTION_TOL)
    controls["mutation"] = mutation
    add_check(receipt, "mutation_control",
              bool(mutation["clean_passes"] and mutation["mutated_trips"]), mutation)

    sign_flip = {}
    summary = receipt["summary"][f"{int(max(CHARGES))}"]
    section = section_for(summary["refined_radius"], SPECTRUM_NA, SPECTRUM_NPHI)
    _, f0, c0 = best_position_seed(section, summary["refined_radius"], WINDING,
                                   summary["refined_density"],
                                   flat_seed(summary["refined_density"]))
    state = solve_section(section, summary["refined_radius"], WINDING,
                          summary["refined_density"], f0, c0, 0.0)
    flipped = constrained_spectrum(section, summary["refined_radius"], 1j,
                                   summary["refined_density"], state)
    base = receipt["spectrum"][f"{int(max(CHARGES))}"]["min_eigenvalue"]
    sign_flip = {
        "charge": max(CHARGES),
        "base_min_eigenvalue": base,
        "flipped_min_eigenvalue": flipped.get("min_eigenvalue"),
        "decrease": base - flipped.get("min_eigenvalue", float("nan")),
        "flipped_negative": bool(flipped.get("min_eigenvalue", 0.0) < 0.0),
        "flipped_residual": flipped.get("eigenpair_residual"),
    }
    controls["winding_sign_flip"] = sign_flip
    add_check(receipt, "winding_sign_flip",
              bool(sign_flip["decrease"] > 1e-6 and sign_flip["flipped_negative"]), sign_flip)

    w0_curve = mass_curve(w0_rows, max(CHARGES))
    w0_index = int(min(range(len(w0_curve)), key=lambda i: w0_curve[i]["mass"]))
    w0_interior = 0 < w0_index < len(w0_curve) - 1
    w1_radius = receipt["summary"][f"{int(max(CHARGES))}"]["refined_radius"]
    w0_radius = float(w0_curve[w0_index]["radius"])
    controls["winding_off"] = {
        "charge": max(CHARGES),
        "interior": bool(w0_interior),
        "radius": w0_radius,
        "density": float(w0_curve[w0_index]["density"]),
        "mass": float(w0_curve[w0_index]["mass"]),
        "winding_on_radius": float(w1_radius),
        "radius_difference": abs(w0_radius - w1_radius),
        "mass_curve": [[float(entry["radius"]), float(entry["mass"])] for entry in w0_curve],
    }
    add_check(receipt, "winding_off_difference",
              bool((not w0_interior) or abs(w0_radius - w1_radius) > REFINE_DELTA),
              {"interior": w0_interior, "radius_difference": abs(w0_radius - w1_radius)})

    # --- convergence accounting -------------------------------------------
    all_rows = scan_rows + refined_rows + w0_rows
    failed = [row for row in all_rows if not row["converged"]]
    protected = {(round(row["radius"], 9), round(row["density"], 9))
                 for charge in CHARGES for row in mass_curve(scan_rows, charge)}
    protected |= {(round(row["radius"], 9), round(row["density"], 9)) for row in refined_rows}
    failed_protected = [row for row in failed
                        if (round(row["radius"], 9), round(row["density"], 9)) in protected]
    add_check(receipt, "solve_convergence",
              bool(len(failed) <= MAX_FAILED_SOLVES and not failed_protected),
              {"failed": len(failed), "total": len(all_rows),
               "failed_protected": len(failed_protected),
               "allowance": MAX_FAILED_SOLVES})

    # --- decision rule ----------------------------------------------------
    summaries = [receipt["summary"][f"{int(charge)}"] for charge in CHARGES]
    unresolved = {
        "yang_mills_identification": "UNRESOLVED",
        "continuum_gauge_construction": "UNRESOLVED",
        "charge_quantization": "UNRESOLVED",
        "clay_verdict": None,
    }
    classification: dict[str, Any] = {"unresolved": unresolved, "claim": None}
    if receipt["failures"]:
        classification["branch"] = "INCONCLUSIVE"
        classification["trigger"] = list(receipt["failures"])
    elif not any(summary["coarse_argmin_interior"] for summary in summaries):
        classification["branch"] = "NO_INTERIOR_STATIONARY_RADIUS_IN_SCHEDULE"
        classification["trigger"] = [summary["coarse_argmin_radius"] for summary in summaries]
    elif not all(summary["coarse_argmin_interior"] for summary in summaries):
        classification["branch"] = "RADIUS_SCHEDULE_BOUNDARY_LIMITED"
        classification["trigger"] = [
            {"charge": summary["charge"], "radius": summary["coarse_argmin_radius"]}
            for summary in summaries if not summary["coarse_argmin_interior"]]
    elif any(summary["density_endpoint"] for summary in summaries):
        classification["branch"] = "DENSITY_SCHEDULE_BOUNDARY_LIMITED"
        classification["trigger"] = [
            {"charge": summary["charge"], "density": summary["refined_density"]}
            for summary in summaries if summary["density_endpoint"]]
    elif not receipt["summary"][f"{int(max(CHARGES))}"]["bound"]:
        classification["branch"] = "THICK_TORUS_LOOP_UNBOUND_IN_SCHEDULE"
        classification["trigger"] = {"charge": max(CHARGES),
                                     "mass": receipt["summary"][f"{int(max(CHARGES))}"]["mass"],
                                     "threshold": receipt["summary"][f"{int(max(CHARGES))}"]["threshold"]}
    elif not all(summary["geometry_qualified"] for summary in summaries):
        classification["branch"] = "THICK_TORUS_STATIONARY_RADIUS_INSIDE_CORE_OVERLAP"
        classification["trigger"] = [
            {"charge": summary["charge"], "a99_over_R": summary["a99_over_R"]}
            for summary in summaries if not summary["geometry_qualified"]]
    else:
        unstable = [
            summary["charge"] for summary in summaries
            if not (isinstance(summary["curvature_fit"], float) and summary["curvature_fit"] > 0.0
                    and isinstance(summary["curvature_discrete"], float)
                    and summary["curvature_discrete"] > 0.0)]
        spectrum_negative = [
            charge for charge in CHARGES
            if not receipt["spectrum"][f"{int(charge)}"].get("min_eigenvalue", -1.0) > 0.0]
        if unstable or spectrum_negative:
            classification["branch"] = "THICK_TORUS_MARGINALLY_UNSTABLE_STATIONARY_RADIUS"
            classification["trigger"] = {"curvature": unstable, "spectrum": spectrum_negative}
        else:
            classification["branch"] = "SUPPORTS_CONDITIONAL_THICK_TORUS_GAP_MECHANISM"
            classification["trigger"] = [
                {"charge": summary["charge"], "radius": summary["refined_radius"],
                 "density": summary["refined_density"], "mass": summary["mass"],
                 "threshold": summary["threshold"], "margin": summary["margin"],
                 "curvature_fit": summary["curvature_fit"],
                 "min_eigenvalue": receipt["spectrum"][f"{int(summary['charge'])}"]["min_eigenvalue"]}
                for summary in summaries]
            classification["claim"] = (
                "For each scheduled charge the cross-section relaxed in the exact toroidal "
                "metric has an interior stationary radius with positive radius curvature and a "
                "positive constrained spectrum, and the mass there is below the dilute charged "
                "threshold by the reported margin."
            )
    receipt["classification"] = classification
    receipt["status"] = "PASS" if not receipt["failures"] else "FAIL"
    receipt["content_sha256"] = content_digest(receipt)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=1, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(f"receipt: {output}")
    print(f"manifest: {manifest_path}")
    print(f"sources: {snapshot_dir}")
    print(f"status: {receipt['status']}")
    print(f"checks: {sum(1 for row in receipt['checks'] if row['passed'])}/{len(receipt['checks'])}")
    if receipt["failures"]:
        print(f"failures: {receipt['failures']}")
    print(f"classification: {classification['branch']}")
    for charge in CHARGES:
        summary = receipt["summary"][f"{int(charge)}"]
        print(f"  Q={int(charge)}: R*={summary['refined_radius']:.4f} n*={summary['refined_density']:.4f} "
              f"M={summary['mass']:.6f} threshold={summary['threshold']:.6f} "
              f"margin={summary['margin']:.6f} curvature={summary['curvature_fit']} "
              f"lambda_min={receipt['spectrum'][f'{int(charge)}'].get('min_eigenvalue')}")
    return 0 if receipt["status"] == "PASS" else 1


def row_profile_f(row: dict[str, Any]) -> np.ndarray:
    return np.asarray(row["f"], dtype=np.float64)


def row_profile_c(row: dict[str, Any]) -> np.ndarray:
    return np.asarray(row["c"], dtype=np.float64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    arguments = parser.parse_args()
    return run(Path(arguments.output))


if __name__ == "__main__":
    raise SystemExit(main())
