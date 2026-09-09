#!/usr/bin/env python3
"""Independent raw-array verifier for the finite-cylinder vortex-core rows.

This program intentionally does not import the primary minimizer and does not
read the report or notebook.  The action, regularity basis, quadrature and FE
operators are reconstructed here from the frozen PA2/PA12 formulas.  Its
scientific scope is conditional radial stationary cores and transverse carrier
modes; every receipt keeps ``complete_physical_matter_formation`` false.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import sympy as sp
from scipy.linalg import eigh
from scipy.special import jn_zeros

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = "foundations/particle-stationary-action-closure.md"
NOTEBOOK_PATH = "computations/matter-formation-continuum-report.md"
SCHEMA = "matter-formation-vortex-core-verification-v1"
PRIMARY_SCHEMA = "matter-formation-vortex-core-v1"
SUPPORTS = "SUPPORTS-conditional radial vortex binding"
NO_CARRIER = "DOES NOT EMERGE-finite-cylinder carrier binding"
INCONCLUSIVE = "INCONCLUSIVE"

RHO0 = 1.2
a = 0.83
d = 1.25
v = 0.9
g = 0.71
LAMBDA_RHO = 1.0
LAMBDA_PHI = 1.0
LAMBDA_H = 1.0
K_CX = 1.0
ETA_C = 1.0
PHI = (1.0 + math.sqrt(5.0)) / 2.0
C0 = PHI ** -3
J0 = 4.0 * a * RHO0 * d * v * v * (1.0 - C0 * C0) / (a * RHO0 + 4.0 * d * v * v)
A_RHO = a * (4.0 * d * v * v) ** 2 * (1.0 - C0 * C0) / (4.0 * LAMBDA_RHO * (a * RHO0 + 4.0 * d * v * v) ** 2)
GAUSS_X = np.array((-1.0 / math.sqrt(3.0), 1.0 / math.sqrt(3.0)))


def finite(x: Any) -> bool:
    if isinstance(x, (bool, np.bool_)) or x is None:
        return True
    if isinstance(x, (int, float, np.integer, np.floating)):
        return math.isfinite(float(x))
    if isinstance(x, (list, tuple)):
        return all(finite(vv) for vv in x)
    if isinstance(x, dict):
        return all(finite(vv) for vv in x.values())
    return True


def strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject(token: str) -> None:
        raise ValueError(f"nonfinite JSON token: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(value, dict) or not finite(value):
        raise ValueError("summary must be a finite JSON object")
    return value


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [jsonable(vv) for vv in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else {"invalid_numeric": str(value)}
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def check(bucket: dict[str, Any], name: str, passed: bool, evidence: Any) -> None:
    bucket.setdefault("checks", []).append({"name": name, "pass": bool(passed), "evidence": jsonable(evidence)})
    if not passed:
        bucket.setdefault("failures", []).append(name)


def close_value(actual: float, expected: float, tol: float) -> tuple[bool, float]:
    scale = max(1.0, abs(float(expected)))
    delta = abs(float(actual) - float(expected)) / scale
    return bool(math.isfinite(delta) and delta <= tol), delta


def close_array(actual: np.ndarray, expected: np.ndarray, tol: float) -> tuple[bool, float]:
    if actual.shape != expected.shape:
        return False, math.inf
    delta = np.max(np.abs(actual - expected) / np.maximum(1.0, np.abs(expected)))
    return bool(np.isfinite(delta) and delta <= tol), float(delta)


def regular_weights(r: np.ndarray | float, winding: int) -> tuple[np.ndarray | float, np.ndarray | float]:
    rr = np.asarray(r, dtype=float)
    w1 = rr / np.sqrt(1.0 + rr * rr)
    w3 = rr * rr / (1.0 + rr * rr)
    w1p = 1.0 / (1.0 + rr * rr) ** 1.5
    w3p = 2.0 * rr / (1.0 + rr * rr) ** 2
    return (w1, w1p) if winding else (np.ones_like(rr), np.zeros_like(rr))


def reconstruct_profiles(r: np.ndarray, y: np.ndarray, epsilon: int) -> dict[str, np.ndarray]:
    n_y, n_i = (1, 0) if epsilon == 1 else (0, 1)
    wp, wpp = regular_weights(r, n_y)
    wq, wqp = regular_weights(r, n_i)
    w1, w1p = regular_weights(r, 1)
    w3, w3p = (r * r / (1.0 + r * r), 2.0 * r / (1.0 + r * r) ** 2)
    weights = np.column_stack((wp, wq, np.ones_like(r), w1, w3))
    return {"weights": weights, "weight_derivatives": np.column_stack((wpp, wqp, np.zeros_like(r), w1p, w3p)), "physical": y * weights}


def gauss_reconstruct(r: np.ndarray, y: np.ndarray, epsilon: int) -> dict[str, np.ndarray]:
    n = r.size - 1
    mid = 0.5 * (r[:-1] + r[1:])
    half = 0.5 * (r[1:] - r[:-1])
    rq = mid[:, None] + half[:, None] * GAUSS_X[None, :]
    shape0 = (1.0 - GAUSS_X)[None, :] / 2.0
    shape1 = (1.0 + GAUSS_X)[None, :] / 2.0
    yq = shape0[:, :, None] * y[:-1, None, :] + shape1[:, :, None] * y[1:, None, :]
    ydq = (y[1:] - y[:-1])[:, None, :] / (r[1:] - r[:-1])[:, None, None]
    flat = reconstruct_profiles(rq.reshape(-1), yq.reshape(-1, 5), epsilon)
    fieldq = flat["physical"].reshape(n, 2, 5)
    weightq = flat["weights"].reshape(n, 2, 5)
    weightpq = flat["weight_derivatives"].reshape(n, 2, 5)
    derivq = weightpq * yq + weightq * ydq
    return {"r": rq, "y": yq, "derivatives_y": ydq, "fields": fieldq, "derivatives": derivq, "weights": weightq, "weight_derivatives": weightpq}


def symbolic_action() -> dict[str, Any]:
    p, q, u, pr, qr, ur = sp.symbols("p q u p_r q_r u_r", real=True)
    b1, b3, b1r, b3r, h, r = sp.symbols("b1 b3 b1_r b3_r h r", real=True)
    rho0, aa, dd, vv, gg, lamr, lamp, lamh, ph = sp.symbols("rho0 a d v g lambda_rho lambda_phi lambda_H phi", positive=True, real=True)
    fields = (p, q, u, b1, b3)
    derivs = (pr, qr, ur, b1r, b3r)
    rho = p * p + q * q
    delta = ((1 - ph) * rho + (1 + ph) * (u / vv) * (p * p - q * q)) / 2
    W = lamr * (rho - rho0) ** 2 / 4 + lamp * delta ** 2 / 2 + lamh * (u * u - vv * vv) ** 2 / 4
    fundamental_radial = aa / 2 * ((pr - h * q / 2) ** 2 + (qr + h * p / 2) ** 2)
    adjoint_radial = dd / 2 * (ur * ur + h * h * u * u)
    fundamental_angular = aa / (8 * r * r) * (((2 * sp.Symbol("nY") - b3) * p - b1 * q) ** 2 + ((2 * sp.Symbol("nI") + b3) * q - b1 * p) ** 2)
    adjoint_angular = dd * b1 * b1 * u * u / (2 * r * r)
    magnetic = dd / (2 * gg * gg * r * r) * ((b1r + h * (b3 - sp.Symbol("eps"))) ** 2 + (b3r - h * b1) ** 2)
    components = (fundamental_radial, adjoint_radial, fundamental_angular, adjoint_angular, magnetic, W)
    local = sum(components)
    H = sp.simplify(sp.diff(local, h, 2))
    L = sp.simplify(sp.diff(local, h).subs(h, 0))
    E0 = local.subs(h, 0)
    reduced = E0 - L * L / (2 * H)

    def source_components(eps: int) -> tuple[sp.Expr, ...]:
        """Derive all six densities from covariant components at theta=0."""
        ny, ni = (1, 0) if eps == 1 else (0, 1)
        sigma = (
            sp.Matrix([[0, 1], [1, 0]]),
            sp.Matrix([[0, -sp.I], [sp.I, 0]]),
            sp.Matrix([[1, 0], [0, -1]]),
        )
        psi = sp.Matrix([p, q])
        adjoint = sp.Matrix([0, 0, u])
        ar = sp.Matrix([0, h, 0])
        at = sp.Matrix([b1, 0, b3])
        matrix = lambda vector: sum((vector[j] * sigma[j] / 2 for j in range(3)), sp.zeros(2))
        norm = lambda vector: sp.expand((vector.conjugate().T * vector)[0])
        dr_psi = sp.Matrix([pr, qr]) - sp.I * matrix(ar) * psi
        dt_psi = sp.I * sp.Matrix([ny * p, ni * q]) - sp.I * matrix(at) * psi
        dr_adjoint = sp.Matrix([0, 0, ur]) + ar.cross(adjoint)
        dt_adjoint = at.cross(adjoint)
        curvature = sp.Matrix([b1r, 0, b3r]) - sp.Matrix([eps * h, 0, 0]) + ar.cross(at)
        source_rho = norm(psi)
        source_delta = ((1 - ph) * source_rho + (1 + ph) * (psi.conjugate().T * (2 * matrix(adjoint)) * psi)[0] / vv) / 2
        potential = lamr * (source_rho - rho0) ** 2 / 4 + lamp * source_delta ** 2 / 2 + lamh * (norm(adjoint) - vv * vv) ** 2 / 4
        return (
            aa * norm(dr_psi) / 2,
            dd * norm(dr_adjoint) / 2,
            aa * norm(dt_psi) / (2 * r * r),
            dd * norm(dt_adjoint) / (2 * r * r),
            dd * norm(curvature) / (2 * gg * gg * r * r),
            potential,
        )

    subs = {rho0: sp.Rational(6, 5), aa: sp.Rational(83, 100), dd: sp.Rational(5, 4), vv: sp.Rational(9, 10), gg: sp.Rational(71, 100), lamr: 1, lamp: 1, lamh: 1, ph: (1 + sp.sqrt(5)) / 2}
    jet = {p: sp.Rational(7, 10), q: sp.Rational(2, 5), u: sp.Rational(4, 5), pr: sp.Rational(1, 3), qr: -sp.Rational(2, 7), ur: sp.Rational(1, 6), b1: sp.Rational(3, 10), b3: sp.Rational(4, 5), b1r: -sp.Rational(1, 8), b3r: sp.Rational(2, 9), h: sp.Rational(1, 11), r: sp.Rational(5, 4), sp.Symbol("nY"): 1, sp.Symbol("nI"): 0, sp.Symbol("eps"): 1}
    exact = {}
    numeric = {}
    source_by_cap = {}
    for eps in (1, -1):
        ny, ni = (1, 0) if eps == 1 else (0, 1)
        source_by_cap[eps] = source_components(eps)
        direct = sum(source_by_cap[eps])
        target = local.subs({sp.Symbol("nY"): ny, sp.Symbol("nI"): ni, sp.Symbol("eps"): eps})
        exact[f"component_energy_epsilon_{eps}"] = sp.simplify(direct - target)
        witness = dict(jet)
        witness.update({sp.Symbol("nY"): ny, sp.Symbol("nI"): ni, sp.Symbol("eps"): eps})
        exact[f"rational_jet_epsilon_{eps}"] = sp.simplify((direct - target).subs(witness).subs(subs))
        values = {str(key): float(value) for key, value in (subs | witness).items()}
        reference = float(target.subs(witness).subs(subs))
        sigmas = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]])
        numeric[f"rotated_epsilon_{eps}"] = []
        for angle in np.linspace(0.0, 2.0 * math.pi, 17, endpoint=False):
            e1 = np.array([math.cos(eps * angle), -math.sin(eps * angle), 0.0])
            e2 = np.array([math.sin(eps * angle), math.cos(eps * angle), 0.0])
            e3 = np.array([0.0, 0.0, 1.0])
            ar = values["h"] * e2
            at = values["b1"] * e1 + values["b3"] * e3
            phase = np.exp(1j * np.array([ny, ni]) * angle)
            psi = np.array([values["p"], values["q"]]) * phase
            adjoint = values["u"] * e3
            dr_psi = np.array([values["p_r"], values["q_r"]]) * phase - 0.5j * np.einsum("a,aij->ij", ar, sigmas) @ psi
            dt_psi = 1j * np.array([ny, ni]) * psi - 0.5j * np.einsum("a,aij->ij", at, sigmas) @ psi
            dr_adjoint = values["u_r"] * e3 + np.cross(ar, adjoint)
            dt_adjoint = np.cross(at, adjoint)
            curvature = values["b1_r"] * e1 + values["b3_r"] * e3 - eps * values["h"] * e1 + np.cross(ar, at)
            norm = lambda vector: float(np.vdot(vector, vector).real)
            source_rho = norm(psi)
            source_delta = ((1 - PHI) * source_rho + (1 + PHI) * float(np.vdot(psi, np.einsum("a,aij->ij", adjoint, sigmas) @ psi).real) / v) / 2
            density = (
                a / 2 * (norm(dr_psi) + norm(dt_psi) / values["r"] ** 2)
                + d / 2 * (norm(dr_adjoint) + norm(dt_adjoint) / values["r"] ** 2)
                + d * norm(curvature) / (2 * g * g * values["r"] ** 2)
                + LAMBDA_RHO * (source_rho - RHO0) ** 2 / 4
                + LAMBDA_PHI * source_delta ** 2 / 2
                + LAMBDA_H * (norm(adjoint) - v * v) ** 2 / 4
            )
            numeric[f"rotated_epsilon_{eps}"].append(abs(density - reference) / max(1.0, abs(reference)))
    hessian = sp.simplify(sp.diff(local, h, 2))
    h_residual = sp.simplify(sp.diff(local, h).subs(h, -L / H))
    reduced_identity = sp.simplify(local.subs(h, -L / H) - reduced)
    envelope_residuals = [sp.simplify(sp.diff(reduced, xx) - sp.diff(local, xx).subs(h, -L / H)) for xx in fields + derivs]
    return {"local": local, "components": components, "source_components": source_by_cap, "fields": fields, "derivs": derivs, "H": H, "L": L, "E0": E0, "reduced": reduced, "exact": exact, "numeric": numeric, "hessian": hessian, "h_residual": h_residual, "reduced_identity": reduced_identity, "envelope_residuals": envelope_residuals, "jet": jet}

_ACTION = symbolic_action()


def constants_subs(epsilon: int) -> dict[sp.Symbol, float]:
    symbols = list(_ACTION["local"].free_symbols)
    by_name = {str(s): s for s in symbols}
    ny, ni = (1, 0) if epsilon == 1 else (0, 1)
    return {by_name["rho0"]: RHO0, by_name["a"]: a, by_name["d"]: d, by_name["v"]: v, by_name["g"]: g, by_name["lambda_rho"]: LAMBDA_RHO, by_name["lambda_phi"]: LAMBDA_PHI, by_name["lambda_H"]: LAMBDA_H, by_name["phi"]: PHI, by_name["nY"]: ny, by_name["nI"]: ni, by_name["eps"]: epsilon}


@lru_cache(maxsize=2)
def local_lambdas(epsilon: int) -> dict[str, Any]:
    subs = constants_subs(epsilon)
    source = sum(_ACTION["source_components"][epsilon])
    local = source.subs(subs)
    hsym = next(s for s in source.free_symbols if str(s) == "h")
    H = sp.diff(source, hsym, 2).subs(subs)
    L = sp.diff(source, hsym).subs(hsym, 0).subs(subs)
    # The only remaining free variables after constants are fields, derivatives, h and r.
    rsym = next(s for s in local.free_symbols if str(s) == "r")
    ordered = tuple(_ACTION["fields"]) + tuple(_ACTION["derivs"]) + (hsym, rsym)
    partials = [sp.lambdify(ordered, sp.diff(local, xx), "numpy") for xx in _ACTION["fields"]]
    dpartials = [sp.lambdify(ordered, sp.diff(local, xx), "numpy") for xx in _ACTION["derivs"]]
    component_fns = [sp.lambdify(ordered, component.subs(subs), "numpy") for component in _ACTION["source_components"][epsilon]]
    energy_fn = sp.lambdify(ordered, local, "numpy")
    h_fn = sp.lambdify(ordered, H, "numpy")
    l_fn = sp.lambdify(ordered, L, "numpy")
    return {"energy": energy_fn, "partials": partials, "dpartials": dpartials, "components": component_fns, "H": h_fn, "L": l_fn}



def assemble_carrier(r: np.ndarray, rho_q: np.ndarray, epsilon: int, fields_q: np.ndarray, *, potential_on: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = r.size - 1
    size = n
    stiffness = np.zeros((size, size), dtype=float)
    mass = np.zeros((size, size), dtype=float)
    potential = np.zeros((size, size), dtype=float)
    mid = 0.5 * (r[:-1] + r[1:])
    half = 0.5 * (r[1:] - r[:-1])
    for e in range(n):
        dr = r[e + 1] - r[e]
        for k, xi in enumerate(GAUSS_X):
            rq = mid[e] + half[e] * xi
            wt = half[e] * 2.0 * math.pi * rq
            shape = np.array([(1.0 - xi) / 2.0, (1.0 + xi) / 2.0])
            dshape = np.array([-1.0 / dr, 1.0 / dr])
            V = -ETA_C * (RHO0 - rho_q[e, k]) if potential_on else 0.0
            for i in range(2):
                gi = e + i
                if gi >= size:
                    continue
                for j in range(2):
                    gj = e + j
                    if gj >= size:
                        continue
                    stiffness[gi, gj] += wt * K_CX / 2.0 * dshape[i] * dshape[j]
                    mass[gi, gj] += wt * shape[i] * shape[j]
                    potential[gi, gj] += wt * V * shape[i] * shape[j]
    return stiffness + potential, mass, stiffness, potential


def eigensystem(matrix: np.ndarray, mass: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values, vectors = eigh(matrix, mass, subset_by_index=(0, min(2, matrix.shape[0] - 1)))
    return np.asarray(values, dtype=float), np.asarray(vectors, dtype=float)


def verify_row(path: Path, summary_row: dict[str, Any], epsilon: int, R: float, N: int) -> dict[str, Any]:
    out: dict[str, Any] = {"cap": "plus" if epsilon == 1 else "minus", "epsilon": epsilon, "R": R, "N": N, "npz": path.name, "checks": [], "failures": [], "raw_comparisons": {}}
    required_summary = ("cap", "epsilon", "R", "N", "npz", "energy", "energy_components", "renormalized_energy", "gradient_rms", "gradient_max", "h_stationarity_max", "minimum_rho", "minimum_u", "rho_origin", "carrier_eigenvalues", "carrier_control_eigenvalues", "carrier_residual", "carrier_orthogonality_error", "stationary", "tail", "optimizer")
    for key in required_summary:
        check(out, f"summary_field_{key}", key in summary_row, key)
    if isinstance(summary_row.get("energy_components"), dict):
        for key in ("fundamental_radial", "adjoint_radial", "fundamental_angular", "adjoint_angular", "magnetic", "potential"):
            check(out, f"summary_energy_component_{key}", key in summary_row["energy_components"], key)
    if isinstance(summary_row.get("tail"), dict):
        for key in ("mean_coefficient", "max_relative_error"):
            check(out, f"summary_tail_{key}", key in summary_row["tail"], key)
    if isinstance(summary_row.get("optimizer"), dict):
        for key in ("success", "status", "message", "nit", "nfev", "elapsed_seconds"):
            check(out, f"summary_optimizer_{key}", key in summary_row["optimizer"], key)
    try:
        with np.load(path, allow_pickle=False) as data:
            required = ("r", "y", "physical_fields", "quadrature_r", "quadrature_fields", "quadrature_derivatives", "h", "gradient_y", "energy", "energy_component_values", "carrier_eigenvalues", "carrier_eigenvectors", "control_eigenvalues", "control_eigenvectors")
            missing = [key for key in required if key not in data]
            check(out, "required_arrays_present", not missing, {"missing": missing})
            if missing:
                return out
            arrays_finite = all(np.all(np.isfinite(data[key])) for key in required)
            check(out, "required_arrays_finite", arrays_finite, None)
            if not arrays_finite:
                return out
            r = np.asarray(data["r"], dtype=float)
            y = np.asarray(data["y"], dtype=float)
            supplied_phys = np.asarray(data["physical_fields"], dtype=float)
            supplied_rq = np.asarray(data["quadrature_r"], dtype=float)
            supplied_fq = np.asarray(data["quadrature_fields"], dtype=float)
            supplied_dq = np.asarray(data["quadrature_derivatives"], dtype=float)
            supplied_h = np.asarray(data["h"], dtype=float)
            if r.size != N + 1 or y.shape != (N + 1, 5):
                check(out, "declared_grid_shape", False, {"r": r.shape, "y": y.shape, "expected": [N + 1, [N + 1, 5]]})
                return out
            grid_ok, grid_error = close_array(r, np.linspace(0.0, R, N + 1), 1e-11)
            check(out, "fixed_radial_grid", grid_ok, grid_error)
            if not grid_ok:
                return out
            recon_nodes = reconstruct_profiles(r, y, epsilon)
            recon_q = gauss_reconstruct(r, y, epsilon)
            check(out, "physical_fields_reconstructed", *close_array(recon_nodes["physical"], supplied_phys, 1e-11))
            check(out, "quadrature_r_reconstructed", *close_array(recon_q["r"], supplied_rq, 1e-11))
            check(out, "quadrature_fields_reconstructed", *close_array(recon_q["fields"], supplied_fq, 1e-11))
            check(out, "quadrature_derivatives_reconstructed", *close_array(recon_q["derivatives"], supplied_dq, 1e-11))
            if supplied_h.shape != (N, 2):
                check(out, "h_shape", False, supplied_h.shape)
                return out
            fns = local_lambdas(epsilon)
            nquad = N * 2
            fields = recon_q["fields"].reshape(nquad, 5)
            derivs = recon_q["derivatives"].reshape(nquad, 5)
            rq = recon_q["r"].reshape(nquad)
            args0 = tuple(fields[:, j] for j in range(5)) + tuple(derivs[:, j] for j in range(5)) + (np.zeros(nquad), rq)
            H0 = np.asarray(fns["H"](*args0), dtype=float).reshape(N, 2)
            L0 = np.asarray(fns["L"](*args0), dtype=float).reshape(N, 2)
            hcalc = -L0 / H0
            check(out, "positive_h_algebraic_coefficient", bool(np.all(H0 > 0.0)), {"minimum": float(np.min(H0))})
            check(out, "h_reconstructed", *close_array(hcalc, supplied_h, 1e-8))
            args_h = tuple(fields[:, j] for j in range(5)) + tuple(derivs[:, j] for j in range(5)) + (supplied_h.reshape(nquad), rq)
            density = np.asarray(fns["energy"](*args_h), dtype=float).reshape(N, 2)
            component_density = np.column_stack([np.asarray(fn(*args_h), dtype=float).reshape(-1) for fn in fns["components"]]).reshape(N, 2, 6)
            weight = 2.0 * math.pi * recon_q["r"]
            half = 0.5 * (r[1:] - r[:-1])
            energy_components = np.sum(weight[:, :, None] * component_density * half[:, None, None], axis=(0, 1))
            energy = float(np.sum(energy_components))
            hres = H0 * supplied_h + L0
            hres_norm = float(np.max(np.abs(hres) / np.maximum(1.0, np.abs(L0))))
            check(out, "h_stationarity_residual", hres_norm <= 1e-10, {"max_abs": float(np.max(np.abs(hres))), "normalized": hres_norm})

            # Envelope-theorem gradient: h is held at its reconstructed optimum.
            grad = np.zeros((N + 1, 5), dtype=float)
            lump = np.zeros(N + 1, dtype=float)
            for e in range(N):
                dr = r[e + 1] - r[e]
                for k, xi in enumerate(GAUSS_X):
                    rq0 = recon_q["r"][e, k]
                    wt = 2.0 * math.pi * rq0 * dr / 2.0
                    N0, N1 = (1.0 - xi) / 2.0, (1.0 + xi) / 2.0
                    node_shape = (N0, N1)
                    fvals = fields[e * 2 + k]
                    dvals = derivs[e * 2 + k]
                    arg = tuple(fvals) + tuple(dvals) + (supplied_h[e, k], rq0)
                    px = np.array([float(fn(*arg)) for fn in fns["partials"]])
                    pd = np.array([float(fn(*arg)) for fn in fns["dpartials"]])
                    for side, node in enumerate((e, e + 1)):
                        for j in range(5):
                            wj = recon_q["weights"][e, k, j]
                            wpj = recon_q["weight_derivatives"][e, k, j]
                            dN = -1.0 / dr if side == 0 else 1.0 / dr
                            dx = wj * node_shape[side]
                            ddx = wpj * node_shape[side] + wj * dN
                            grad[node, j] += wt * (px[j] * dx + pd[j] * ddx)
                        lump[node] += wt * node_shape[side]
            check(out, "raw_coefficient_gradient", *close_array(grad, np.asarray(data["gradient_y"]), 1e-8))
            check(out, "raw_array_energy", *close_value(energy, float(data["energy"]), 1e-8))
            check(out, "raw_array_energy_components", *close_array(energy_components, np.asarray(data["energy_component_values"]), 1e-8))
            bulk = np.array([math.sqrt(RHO0 * (1 + C0) / 2), math.sqrt(RHO0 * (1 - C0) / 2), v, a * RHO0 * math.sqrt(1 - C0 * C0) / (a * RHO0 + 4 * d * v * v), epsilon + C0])
            check(out, "exterior_boundary", *close_array(recon_nodes["physical"][-1], bulk, 1e-11))
            free_grad = grad[:-1].reshape(-1)
            free_mass = np.repeat(lump[:-1], 5)
            rms = math.sqrt(float(np.sum(free_grad * free_grad / free_mass) / np.sum(free_mass)))
            maxrel = float(np.max(np.abs(free_grad) / free_mass))
            check(out, "stationarity_rms_threshold", rms <= 1e-6, rms)
            check(out, "stationarity_max_threshold", maxrel <= 1e-4, maxrel)
            Eren = energy - math.pi * J0 / 4.0 * math.log(R)
            rho_q = np.sum(fields[:, :2] ** 2, axis=1).reshape(N, 2)
            tail_mask = (rq >= 16.0) & (rq <= 24.0)
            tail_values = rq[tail_mask] ** 2 * (RHO0 - rho_q.reshape(-1)[tail_mask])
            tail_mean_rel = float(abs(np.mean(tail_values) - A_RHO) / abs(A_RHO)) if tail_values.size else math.inf
            tail_max_rel = float(np.max(np.abs(tail_values - A_RHO)) / abs(A_RHO)) if tail_values.size else math.inf
            A, M, K, V = assemble_carrier(r, rho_q, epsilon, recon_q["fields"], potential_on=True)
            eig, vec = eigensystem(A, M)
            lump_mass = lump[:-1]
            leig, lvec = eigensystem(A, np.diag(lump_mass))
            zA, zM, zK, _ = assemble_carrier(r, rho_q, epsilon, recon_q["fields"], potential_on=False)
            zeig, zvec = eigensystem(zK, zM)
            zleig, zlvec = eigensystem(zK, np.diag(lump_mass))
            zero_ref = float(jn_zeros(0, 1)[0] ** 2 / (2.0 * R * R))
            zero_rel = abs(float(zeig[0]) - zero_ref) / max(abs(zero_ref), 1e-300)
            av, mv = A @ vec, M @ vec * eig[None, :]
            consistent_residual = np.linalg.norm(av - mv, axis=0) / np.maximum(1.0, np.maximum(np.linalg.norm(av, axis=0), np.linalg.norm(mv, axis=0)))
            orthogonality_error = float(np.max(np.abs(vec.T @ M @ vec - np.eye(vec.shape[1]))))
            out["derived"] = {
                "energy": energy, "energy_components": dict(zip(("fundamental_radial", "adjoint_radial", "fundamental_angular", "adjoint_angular", "magnetic", "potential"), energy_components)),
                "renormalized_energy": Eren, "h_stationarity_max": hres_norm, "stationarity_rms": rms, "stationarity_max": maxrel,
                "minimum_rho": float(np.min(np.sum(recon_nodes["physical"][:, :2] ** 2, axis=1))),
                "minimum_u": float(np.min(recon_nodes["physical"][:, 2])), "rho_origin": float(np.sum(recon_nodes["physical"][0, :2] ** 2)),
                "tail_mean_coefficient": float(np.mean(tail_values)) if tail_values.size else math.nan,
                "tail_mean_relative_deviation": tail_mean_rel, "tail_max_relative_deviation": tail_max_rel,
                "carrier_eigenvalues_consistent": eig, "carrier_eigenvalues_lumped": leig,
                "carrier_control_eigenvalues_consistent": zeig, "carrier_control_eigenvalues_lumped": zleig,
                "carrier_residual": float(np.max(np.abs(consistent_residual))), "carrier_orthogonality_error": orthogonality_error,
                "zero_attraction_eigenvalue_consistent": float(zeig[0]), "zero_attraction_eigenvalue_lumped": float(zleig[0]),
                "zero_attraction_reference": zero_ref, "zero_attraction_relative_error": zero_rel,
                "consistent_eigenpair_residuals": consistent_residual,
            }
            check(out, "zero_attraction_positive", float(zeig[0]) > 0.0 and float(zleig[0]) > 0.0, [float(zeig[0]), float(zleig[0])])
            if R == 64.0 and N == 1024:
                check(out, "zero_attraction_bessel_error", zero_rel < 1e-3, zero_rel)
            lumped_delta = abs(float(eig[0]) - float(leig[0])) / max(abs(float(eig[0])), 1e-6)
            if R == 64.0 and N == 1024:
                check(out, "consistent_lumped_lowest_relative_agreement", lumped_delta < 1e-2, lumped_delta)
            check(out, "consistent_eigenpair_residual", bool(np.max(np.abs(consistent_residual)) <= 1e-8), consistent_residual)
            check(out, "consistent_eigenpair_orthogonality", orthogonality_error <= 1e-8, orthogonality_error)
            primary_ev = np.asarray(data["carrier_eigenvalues"], dtype=float).reshape(-1) if "carrier_eigenvalues" in data else None
            primary_ctrl = np.asarray(data["control_eigenvalues"], dtype=float).reshape(-1) if "control_eigenvalues" in data else None
            check(out, "primary_consistent_eigenvalues", primary_ev is not None and primary_ev.shape == eig.shape and close_array(eig, primary_ev, 1e-8)[0], None if primary_ev is None else close_array(eig, primary_ev, 1e-8)[1])
            check(out, "primary_control_eigenvalues", primary_ctrl is not None and primary_ctrl.shape == zeig.shape and close_array(zeig, primary_ctrl, 1e-8)[0], None if primary_ctrl is None else close_array(zeig, primary_ctrl, 1e-8)[1])
            def compare_vectors(key: str, target: np.ndarray, mass: np.ndarray, operator: np.ndarray, values: np.ndarray) -> None:
                supplied_vec = np.asarray(data[key], dtype=float)
                expected_shape = (N + 1, 3)
                check(out, f"primary_{key}_shape", supplied_vec.shape == expected_shape, supplied_vec.shape)
                if supplied_vec.shape != expected_shape or values.shape != (3,):
                    return
                outer_error = float(np.max(np.abs(supplied_vec[-1])))
                check(out, f"primary_{key}_outer_dirichlet", outer_error <= 1e-11, outer_error)
                supplied_vec = supplied_vec[:-1]
                overlaps = np.abs(np.diag(supplied_vec.T @ mass @ target))
                gram_error = float(np.max(np.abs(supplied_vec.T @ mass @ supplied_vec - np.eye(3))))
                av = operator @ supplied_vec
                mv = (mass @ supplied_vec) * values[None, :]
                residuals = np.linalg.norm(av - mv, axis=0) / np.maximum(1.0, np.maximum(np.linalg.norm(av, axis=0), np.linalg.norm(mv, axis=0)))
                check(out, f"primary_{key}_eigenpair_equations", bool(np.max(residuals) < 1e-8), residuals)
                check(out, f"primary_{key}_mass_orthonormality", gram_error < 1e-8, gram_error)
                check(out, f"primary_{key}_overlap", bool(np.max(np.abs(overlaps - 1)) < 1e-8), overlaps)
            compare_vectors("carrier_eigenvectors", vec, M, A, primary_ev)
            compare_vectors("control_eigenvectors", zvec, zM, zK, primary_ctrl)

            summary_ev = np.asarray(summary_row.get("carrier_eigenvalues"), dtype=float)
            summary_ctrl = np.asarray(summary_row.get("carrier_control_eigenvalues"), dtype=float)
            check(out, "raw_summary_carrier_eigenvalues", summary_ev.shape == eig.shape and close_array(eig, summary_ev, 1e-8)[0], None if summary_ev.shape != eig.shape else close_array(eig, summary_ev, 1e-8)[1])
            check(out, "raw_summary_control_eigenvalues", summary_ctrl.shape == zeig.shape and close_array(zeig, summary_ctrl, 1e-8)[0], None if summary_ctrl.shape != zeig.shape else close_array(zeig, summary_ctrl, 1e-8)[1])
            derived_scalars = out["derived"]
            scalar_sources = {
                "energy": "energy", "renormalized_energy": "renormalized_energy", "h_stationarity_max": "h_stationarity_max",
                "stationarity_rms": "gradient_rms", "stationarity_max": "gradient_max", "minimum_rho": "minimum_rho",
                "minimum_u": "minimum_u", "rho_origin": "rho_origin", "carrier_residual": "carrier_residual",
                "carrier_orthogonality_error": "carrier_orthogonality_error",
            }
            for key, source_key in scalar_sources.items():
                supplied = summary_row.get(source_key)
                ok, err = close_value(float(derived_scalars[key]), float(supplied), 1e-8) if supplied is not None else (False, math.inf)
                out["raw_comparisons"][key] = {"supplied": supplied, "derived": float(derived_scalars[key]), "normalized_error": err, "pass": ok}
                check(out, f"raw_{key}", ok, out["raw_comparisons"][key])
            supplied_components = summary_row.get("energy_components")
            if isinstance(supplied_components, dict):
                for key, derived in derived_scalars["energy_components"].items():
                    supplied = supplied_components.get(key)
                    ok, err = (close_value(float(derived), float(supplied), 1e-8) if supplied is not None else (False, math.inf))
                    out["raw_comparisons"][f"energy_components.{key}"] = {"supplied": supplied, "derived": derived, "normalized_error": err, "pass": ok}
                    check(out, f"raw_energy_components_{key}", ok, out["raw_comparisons"][f"energy_components.{key}"])
            tail_meta = summary_row.get("tail", {})
            for key, supplied in (("tail_mean_coefficient", tail_meta.get("mean_coefficient")), ("tail_max_relative_deviation", tail_meta.get("max_relative_error"))):
                if supplied is not None:
                    ok, err = close_value(float(derived_scalars[key]), float(supplied), 1e-8)
                    check(out, f"raw_{key}", ok, {"supplied": supplied, "derived": derived_scalars[key], "normalized_error": err, "pass": ok})
            out["primary_metadata"] = {"stationary": summary_row.get("stationary"), "optimizer": summary_row.get("optimizer")}
            out["raw_comparisons"]["density_tail_samples"] = {"r": rq[tail_mask].tolist(), "derived": tail_values.tolist(), "target": A_RHO}
            summary_ok = all(item["pass"] for item in out["checks"] if item["name"].startswith("summary_"))
            raw_ok = all(item["pass"] for item in out["checks"] if item["name"].startswith("raw_"))
            out["qualified_stationary"] = bool(rms <= 1e-6 and maxrel <= 1e-4 and hres_norm <= 1e-10 and summary_ok and raw_ok and np.all(H0 > 0.0))
            out["finest_carrier_lowest"] = float(eig[0])
    except Exception as exc:  # preserve an explicit failed row rather than hiding it
        check(out, "row_execution", False, f"{type(exc).__name__}: {exc}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="primary vortex-core output directory")
    parser.add_argument("--output", type=Path, required=True, help="fresh verification output directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result: dict[str, Any] = {"schema": SCHEMA, "primary_schema": PRIMARY_SCHEMA, "source_path": SOURCE_PATH, "notebook_path": NOTEBOOK_PATH, "complete_physical_matter_formation": False, "library_versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "sympy": sp.__version__}, "source_primitive": {"checks": [], "failures": [], "exact_residuals": {}, "rotated_residuals": {}, "envelope_residuals": {}}, "rows": [], "comparisons": [], "checks": [], "failures": [], "verdict": INCONCLUSIVE, "numerical_pass": False}
    primitive = result["source_primitive"]
    for name, residual in _ACTION["exact"].items():
        primitive["exact_residuals"][name] = str(residual)
        check(primitive, name, residual == 0, str(residual))
    for name, residuals in _ACTION["numeric"].items():
        primitive["rotated_residuals"][name] = residuals
        check(primitive, name, max(residuals, default=math.inf) <= 1e-10, max(residuals, default=math.inf))
    check(primitive, "h_minimizer_identity", sp.simplify(_ACTION["h_residual"]) == 0, str(_ACTION["h_residual"]))
    h_witness_values: dict[str, float] = {}
    for eps in (1, -1):
        witness = dict(_ACTION["jet"])
        witness.update(constants_subs(eps))
        value = sp.simplify(_ACTION["H"].subs(witness))
        h_witness_values[str(eps)] = float(value)
        check(primitive, f"positive_h_hessian_at_exact_jet_{eps}", value > 0, str(value))
    primitive["h_hessian_formula"] = str(_ACTION["H"])
    for index, residual in enumerate(_ACTION["envelope_residuals"]):
        primitive["envelope_residuals"][str(index)] = str(residual)
        check(primitive, f"envelope_theorem_{index}", residual == 0, str(residual))
    check(primitive, "reduced_energy_identity", _ACTION["reduced_identity"] == 0, str(_ACTION["reduced_identity"]))
    primitive["h_hessian_exact_jet_values"] = h_witness_values
    try:
        primary_summary = strict_json(args.input / "summary.json")
        check(result, "primary_schema", primary_summary.get("schema") == PRIMARY_SCHEMA, primary_summary.get("schema"))
        check(result, "primary_formation_scope", primary_summary.get("complete_physical_matter_formation") is False, primary_summary.get("complete_physical_matter_formation"))
        rows = primary_summary.get("rows", [])
        if not isinstance(rows, list):
            raise ValueError("summary rows is not a list")
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("row is not an object")
            cap = item.get("cap")
            if cap not in ("plus", "minus"):
                raise ValueError(f"invalid cap {cap!r}")
            epsilon = int(item.get("epsilon"))
            if epsilon != (1 if cap == "plus" else -1):
                raise ValueError("cap and epsilon disagree")
            R = float(item.get("R"))
            N = int(item.get("N"))
            rel = item.get("npz")
            if not isinstance(rel, str):
                raise ValueError("row has no relative NPZ filename")
            result["rows"].append(verify_row(args.input / rel, item, epsilon, R, N))
        check(result, "all_expected_rows_present", len(result["rows"]) == 8, len(result["rows"]))
        check(result, "all_caps_and_grids_present", sorted((row["epsilon"], row["R"], row["N"]) for row in result["rows"]) == sorted([(1, 32.0, 256), (1, 32.0, 512), (1, 64.0, 512), (1, 64.0, 1024), (-1, 32.0, 256), (-1, 32.0, 512), (-1, 64.0, 512), (-1, 64.0, 1024)]), [(row["epsilon"], row["R"], row["N"]) for row in result["rows"]])
    except Exception as exc:
        check(result, "primary_input", False, f"{type(exc).__name__}: {exc}")
    by_cap: dict[int, list[dict[str, Any]]] = {1: [], -1: []}
    for row in result["rows"]:
        if row.get("epsilon") in by_cap:
            by_cap[row["epsilon"]].append(row)
    cap_ok: dict[str, bool] = {}
    for eps, rows in by_cap.items():
        rows = sorted(rows, key=lambda rr: (rr.get("R", 0.0), rr.get("N", 0)))
        qualified = all(bool(rr.get("qualified_stationary", False)) for rr in rows)
        fine32 = [rr for rr in rows if rr.get("R") == 32.0 and rr.get("N") == 512]
        fine64 = [rr for rr in rows if rr.get("R") == 64.0 and rr.get("N") == 1024]
        pair32 = [rr for rr in rows if rr.get("R") == 32.0]
        pair64 = [rr for rr in rows if rr.get("R") == 64.0]
        def one(name: str, value: bool, evidence: Any) -> None:
            check(result, f"cap_{eps}_{name}", value, evidence)
        if fine32 and fine64:
            e32 = fine32[0]["derived"]["renormalized_energy"]
            e64 = fine64[0]["derived"]["renormalized_energy"]
            b32 = fine32[0]["derived"]["carrier_eigenvalues_consistent"][0]
            b64 = fine64[0]["derived"]["carrier_eigenvalues_consistent"][0]
            one("renormalized_domain_agreement", abs(e32 - e64) / max(1.0, abs(e32), abs(e64)) < 1e-2, [e32, e64])
            one("lowest_bound_energy_agreement", abs(b32 - b64) / max(abs(b32), abs(b64), 1e-6) < 5e-2, [b32, b64])
            one("finest_R32_negative", b32 < -1e-6, b32)
            one("finest_R64_negative", b64 < -1e-6, b64)
        else:
            one("finest_rows_present", False, [(rr.get("R"), rr.get("N")) for rr in rows])
        for domain, pair in ((32.0, pair32), (64.0, pair64)):
            if len(pair) == 2:
                vals = [rr["derived"]["renormalized_energy"] for rr in pair]
                one(f"resolution_{int(domain)}", abs(vals[0] - vals[1]) / max(1.0, abs(vals[0]), abs(vals[1])) < 1e-3, vals)
            else:
                one(f"resolution_{int(domain)}_rows_present", False, len(pair))
        if fine64:
            tail = fine64[0]["derived"]["tail_max_relative_deviation"]
            one("R64_tail_coefficient", tail < 0.10, tail)
        else:
            one("R64_tail_present", False, None)
        cap_ok[str(eps)] = qualified
    row_checks = [item for row in result["rows"] for item in row.get("checks", [])]
    nonnegative_excluded = {f"cap_{eps}_{name}" for eps in (1, -1) for name in ("finest_R32_negative", "finest_R64_negative", "lowest_bound_energy_agreement")}
    base_num = all(item.get("pass", False) for item in result["checks"] if item["name"] not in nonnegative_excluded) and all(item.get("pass", False) for item in primitive["checks"]) and all(item.get("pass", False) for item in row_checks)
    radial_refinement = all(cap_ok.values()) and all(item.get("pass", False) for item in result["checks"] if str(item["name"]).startswith("cap_") and item["name"] not in nonnegative_excluded)
    finest = [rr for rr in result["rows"] if (rr.get("R"), rr.get("N")) in ((32.0, 512), (64.0, 1024)) and rr.get("qualified_stationary")]
    carrier_nonnegative = len(finest) == 4 and all(rr["finest_carrier_lowest"] >= 0.0 for rr in finest)
    carrier_negative = len(finest) == 4 and all(rr["finest_carrier_lowest"] < -1e-6 for rr in finest)
    if radial_refinement and base_num and carrier_nonnegative:
        result["verdict"] = NO_CARRIER
        result["numerical_pass"] = True
    elif radial_refinement and base_num and carrier_negative and all(item.get("pass", False) for item in result["checks"]):
        result["verdict"] = SUPPORTS
        result["numerical_pass"] = True
    else:
        result["verdict"] = INCONCLUSIVE
    result["adjudication"] = {"cap_qualified_stationarity": cap_ok, "radial_refinement_pass": radial_refinement, "qualified_finest_nonnegative_carrier": carrier_nonnegative, "scope": "conditional radial stationary cores and transverse carrier modes; no finite loop or carrier production"}
    result["source_action_mismatches"] = list(primitive.get("failures", []))
    result["regularity_premise_mismatches"] = sorted({failure for row in result["rows"] for failure in row.get("failures", []) if "reconstruct" in failure or "required_arrays" in failure or "summary_" in failure})
    result["failures"].extend(primitive.get("failures", []))
    for row in result["rows"]:
        result["failures"].extend(f"{row.get('npz', 'row')}:{failure}" for failure in row.get("failures", []))
    (args.output / "verification.json").write_text(json.dumps(jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
