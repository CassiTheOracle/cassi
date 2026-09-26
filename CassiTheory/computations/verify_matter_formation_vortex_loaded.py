#!/usr/bin/env python3
"""Independently verify self-consistent carrier-loaded radial vortex cores.

The verifier consumes the primary raw arrays and a hash-bound section manifest.
It never imports or executes the loaded-core primary solver.  The unloaded
five-field action and its Pauli/component reconstruction are imported only from
``verify_matter_formation_vortex_core``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy import sparse

from verify_matter_formation_vortex_core import (
    C0,
    GAUSS_X,
    J0,
    K_CX,
    RHO0,
    ETA_C,
    a,
    d,
    gauss_reconstruct,
    local_lambdas,
    reconstruct_profiles,
    v,
)

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = "computations/matter-formation-continuum-report.md"
SECTION_HEADING = "## 46. Working notes:"
SCHEMA = "matter-formation-loaded-vortex-verification-v1"
PRIMARY_SCHEMA = "matter-formation-loaded-vortex-v1"
MANIFEST_SCHEMA = "matter-formation-loaded-vortex-manifest-v1"
INCONCLUSIVE = "INCONCLUSIVE"
SUPPORTS = "SUPPORTS-conditional loaded-core current/escape overlap"
NO_EMERGENCE = "DOES NOT EMERGE in the specified schedule"
CAPS = ("plus", "minus")
EPSILONS = {"plus": 1, "minus": -1}
POPULATIONS = (1.0, 16.0, 64.0)
GRIDS = ((32.0, 256), (32.0, 512), (64.0, 512), (64.0, 1024))
CORE_COMPONENTS = (
    "fundamental_radial",
    "adjoint_radial",
    "fundamental_angular",
    "adjoint_angular",
    "magnetic",
    "potential",
)
CARRIER_COMPONENTS = ("carrier_gradient", "carrier_interaction", "carrier_quartic")
COMPONENTS = CORE_COMPONENTS + CARRIER_COMPONENTS
REQUIRED_NPZ = (
    "r",
    "y",
    "physical_fields",
    "quadrature_r",
    "quadrature_fields",
    "quadrature_derivatives",
    "f",
    "f_q",
    "df_q",
    "h",
    "gradient_y",
    "gradient_f",
    "carrier_constrained_gradient",
    "energy",
    "energy_component_values",
)
LAMBDA_C = 1.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: Any) -> bool:
    if value is None or isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, np.ndarray):
        return bool(np.all(np.isfinite(value)))
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
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
        raise ValueError("JSON value must be a finite object")
    return value


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def check(bucket: dict[str, Any], name: str, passed: bool, evidence: Any) -> None:
    item = {"name": name, "pass": bool(passed), "evidence": jsonable(evidence)}
    bucket.setdefault("checks", []).append(item)
    if not passed:
        bucket.setdefault("failures", []).append(name)


def close_value(actual: float, expected: float, tolerance: float) -> tuple[bool, float]:
    try:
        scale = max(1.0, abs(float(expected)))
        error = abs(float(actual) - float(expected)) / scale
    except (TypeError, ValueError, OverflowError):
        return False, math.inf
    return bool(math.isfinite(error) and error <= tolerance), float(error)


def close_array(actual: np.ndarray, expected: np.ndarray, tolerance: float) -> tuple[bool, float]:
    if actual.shape != expected.shape:
        return False, math.inf
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        return False, math.inf
    error = np.max(np.abs(actual - expected) / np.maximum(1.0, np.abs(expected))) if actual.size else 0.0
    return bool(np.isfinite(error) and error <= tolerance), float(error)


def expected_rows() -> list[tuple[str, int, float, int, float]]:
    return [(cap, EPSILONS[cap], n, int(R), N) for cap in CAPS for n in POPULATIONS for R, N in GRIDS]


def safe_relative_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid relative path: {value!r}")
    path = (root / value).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise ValueError(f"path escapes root: {value}")
    return path


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = strict_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")
    section = manifest.get("section")
    if not isinstance(section, dict):
        raise ValueError("manifest section is missing")
    if section.get("path") != NOTEBOOK or section.get("heading") != SECTION_HEADING:
        raise ValueError("manifest section identity mismatch")
    snapshot_name = section.get("snapshot")
    snapshot = safe_relative_path(manifest_path.parent, snapshot_name)
    live = safe_relative_path(ROOT, section["path"])
    expected_hash = section.get("sha256")
    if not isinstance(expected_hash, str) or sha256(snapshot) != expected_hash:
        raise ValueError("section snapshot hash mismatch")
    section_text = snapshot.read_text(encoding="utf-8")
    live_text = live.read_text(encoding="utf-8")
    at = live_text.find(SECTION_HEADING)
    if at < 0 or live_text[at : at + len(section_text)] != section_text:
        raise ValueError("live report does not contain the exact frozen section snapshot")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest sources are missing")
    source_receipts: list[dict[str, Any]] = []
    for receipt in sources:
        if not isinstance(receipt, dict):
            raise ValueError("invalid source receipt")
        path = safe_relative_path(ROOT, receipt.get("path"))
        frozen = safe_relative_path(manifest_path.parent, receipt.get("snapshot"))
        expected = receipt.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected or sha256(frozen) != expected:
            raise ValueError(f"source hash mismatch: {receipt.get('path')}")
        source_receipts.append({"path": receipt["path"], "snapshot": receipt["snapshot"], "sha256": expected})
    required_sources = {
        "computations/matter_formation_vortex_core.py",
        "computations/verify_matter_formation_vortex_core.py",
        "computations/matter_formation_vortex_loaded.py",
        "computations/verify_matter_formation_vortex_loaded.py",
    }
    listed_sources = {item["path"] for item in source_receipts}
    if not required_sources.issubset(listed_sources):
        raise ValueError("manifest omits a required calculation source")

    arrays = manifest.get("arrays")
    if not isinstance(arrays, list):
        raise ValueError("manifest arrays are missing")
    expected_old = {
        f"runs/20260908_matter_formation_vortex_core/primary/cap_{cap}_N{N}_R{int(R)}.npz"
        for cap in CAPS
        for R, N in GRIDS
    }
    if {item.get("path") for item in arrays if isinstance(item, dict)} != expected_old:
        raise ValueError("manifest arrays differ from the eight qualified unloaded inputs")
    array_receipts: list[dict[str, Any]] = []
    for receipt in arrays:
        if not isinstance(receipt, dict):
            raise ValueError("invalid array receipt")
        path = safe_relative_path(ROOT, receipt.get("path"))
        expected = receipt.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected:
            raise ValueError(f"array hash mismatch: {receipt.get('path')}")
        array_receipts.append({"path": receipt["path"], "sha256": expected})
    return {
        "schema": manifest["schema"],
        "section": {"path": section["path"], "heading": section["heading"], "snapshot": section["snapshot"], "sha256": expected_hash},
        "sources": source_receipts,
        "arrays": array_receipts,
    }


def bulk_checks() -> dict[str, Any]:
    rho, s, lr, eta, lc, r0 = sp.symbols("rho s lambda_rho eta_C lambda_C rho0", positive=True)
    W = lr * (rho - r0) ** 2 / 4 - eta * (r0 - rho) * s + lc * s**2 / 2
    rho_star = r0 - 2 * eta * s / lr
    s_cut = lr * r0 / (2 * eta)
    W_interior = sp.factor(W.subs(rho, rho_star))
    W_depleted = W.subs(rho, 0)
    s_star = r0 * sp.sqrt(lr / (2 * lc))
    mu_star = r0 * (sp.sqrt(lr * lc / 2) - eta)
    convex_square = lr * (rho - r0 + 2 * eta * s / lr)**2 / 4 + (lc / 2 - eta**2 / lr) * s**2
    grand_square = (sp.sqrt(lr) * (rho - r0) / 2 + sp.sqrt(lc / 2) * s)**2 + (eta - sp.sqrt(lr * lc / 2)) * rho * s
    checks: list[dict[str, Any]] = []

    def exact(name: str, expression: sp.Expr) -> None:
        residual = sp.simplify(expression)
        checks.append({"name": name, "pass": bool(residual == 0), "residual": str(residual)})

    exact("rho_stationary_equation", sp.diff(W, rho).subs(rho, rho_star))
    exact("strict_density_curvature", sp.diff(W, rho, 2) - lr / 2)
    exact("depleted_boundary_gradient", sp.diff(W, rho).subs(rho, 0) - eta * (s - s_cut))
    exact("interior_reduced_density", W_interior - (lc / 2 - eta**2 / lr) * s**2)
    exact("constrained_branch_matching", (W_interior - W_depleted).subs(s, s_cut))
    exact("depleted_coexistence_stationarity", sp.diff(W_depleted / s, s).subs(s, s_star))
    exact("coexistence_chemical_potential", (W_depleted / s).subs(s, s_star) - mu_star)
    exact("energy_complete_square", W - convex_square)
    exact("grand_potential_complete_square", W - mu_star * s - grand_square)
    exact("loaded_grand_potential_zero", (W - mu_star * s).subs({rho: 0, s: s_star}))
    exact("vacuum_grand_potential_zero", (W - mu_star * s).subs({rho: r0, s: 0}))

    values: dict[str, Any] = {}
    for lam in (1, 2, 4):
        sub = {r0: sp.Rational(6, 5), lr: 1, eta: 1, lc: lam}
        cutoff = sp.simplify(s_cut.subs(sub))
        reduced = sp.simplify(W_interior.subs(sub))
        row: dict[str, Any] = {
            "lambda_C": lam,
            "s_cutoff": str(cutoff),
            "interior_reduced_W": str(reduced),
            "depleted_W_over_s": str(sp.factor((W_depleted / s).subs(sub))),
        }
        if lam == 1:
            ss = sp.simplify(s_star.subs(sub))
            mm = sp.simplify(mu_star.subs(sub))
            cross = sp.simplify((eta - sp.sqrt(lr * lc / 2)).subs(sub))
            row.update({"branch": "coexistence", "s_star": float(ss), "mu_star": float(mm), "s_star_exact": str(ss), "mu_star_exact": str(mm)})
            checks.append({"name": "lambda_1_two_global_minima", "pass": bool(ss > cutoff and mm < 0 and cross > 0), "evidence": row})
        elif lam == 2:
            cross = sp.simplify((eta - sp.sqrt(lr * lc / 2)).subs(sub))
            flat = sp.simplify(grand_square.subs(sub).subs(rho, rho_star.subs(sub)))
            row.update({"branch": "flat", "flat_interval": ["0", str(cutoff)]})
            checks.append({"name": "lambda_2_flat_mixture_interval", "pass": bool(cross == 0 and flat == 0 and reduced == 0), "evidence": row})
        else:
            coefficient = sp.simplify((lc / 2 - eta**2 / lr).subs(sub))
            dilute = sp.limit((W_interior / s).subs(sub), s, 0, dir="+")
            row.update({"branch": "diffuse_infimum", "infimum": str(dilute), "positive_quartic_remainder": str(coefficient)})
            checks.append({"name": "lambda_4_positive_energy_and_dilute_infimum", "pass": bool(coefficient > 0 and dilute == 0), "evidence": row})
        values[str(lam)] = row
    return {"checks": checks, "values": values, "rho_star": str(rho_star), "W": str(W), "grand_potential_square": str(grand_square), "critical_lambda_C": str(2 * eta**2 / lr)}


def quadrature_f(r: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = r.size - 1
    dr = np.diff(r)
    t0 = (1.0 - GAUSS_X) / 2.0
    t1 = (1.0 + GAUSS_X) / 2.0
    fq = t0[None, :] * f[:-1, None] + t1[None, :] * f[1:, None]
    dfq = np.broadcast_to(((f[1:] - f[:-1]) / dr)[:, None], (n, 2)).copy()
    rq = 0.5 * (r[:-1] + r[1:])[:, None] + 0.5 * dr[:, None] * GAUSS_X[None, :]
    return rq, fq, dfq


def assemble_full_mass(r: np.ndarray) -> tuple[sparse.csr_matrix, np.ndarray]:
    diagonal = np.zeros(r.size, dtype=np.float64)
    off_diagonal = np.zeros(r.size - 1, dtype=np.float64)
    lump = np.zeros(r.size, dtype=np.float64)
    shapes = np.column_stack(((1.0 - GAUSS_X) / 2.0, (1.0 + GAUSS_X) / 2.0))
    for e, dr in enumerate(np.diff(r)):
        rq = 0.5 * (r[e] + r[e + 1]) + 0.5 * dr * GAUSS_X
        weights = 2.0 * math.pi * rq * dr / 2.0
        local_mass = shapes.T @ (weights[:, None] * shapes)
        diagonal[e : e + 2] += np.diag(local_mass)
        off_diagonal[e] = local_mass[0, 1]
        lump[e : e + 2] += shapes.T @ weights
    return sparse.diags((off_diagonal, diagonal, off_diagonal), (-1, 0, 1), format="csr"), lump


def expected_boundary(epsilon: int) -> np.ndarray:
    return np.array(
        [
            math.sqrt(RHO0 * (1.0 + C0) / 2.0),
            math.sqrt(RHO0 * (1.0 - C0) / 2.0),
            v,
            a * RHO0 * math.sqrt(1.0 - C0 * C0) / (a * RHO0 + 4.0 * d * v * v),
            epsilon + C0,
        ],
        dtype=np.float64,
    )


def verify_row(npz_path: Path, summary_row: dict[str, Any], epsilon: int, population: float, R: float, N: int, lambda_c: float) -> dict[str, Any]:
    cap = "plus" if epsilon == 1 else "minus"
    out: dict[str, Any] = {
        "cap": cap, "epsilon": epsilon, "n": population, "R": R, "N": N,
        "npz": npz_path.name, "checks": [], "failures": [], "raw_comparisons": {},
        "summary_exception": summary_row.get("exception"), "optimizer": summary_row.get("optimizer"),
    }
    try:
        with np.load(npz_path, allow_pickle=False) as data:
            missing = [key for key in REQUIRED_NPZ if key not in data]
            check(out, "required_arrays_present", not missing, {"missing": missing})
            if missing:
                return out
            names_present = "energy_component_names" in data
            if names_present:
                names = [str(item) for item in np.asarray(data["energy_component_names"]).reshape(-1)]
                check(out, "energy_component_names", names == list(COMPONENTS), names)
                if names != list(COMPONENTS):
                    return out
            arrays = {key: np.asarray(data[key]) for key in REQUIRED_NPZ}
            arrays_finite = all(
                not np.iscomplexobj(value)
                and np.issubdtype(value.dtype, np.number)
                and np.all(np.isfinite(value))
                for value in arrays.values()
            )
            check(out, "required_arrays_real_and_finite", arrays_finite, None)
            if not arrays_finite:
                return out
            arrays = {key: value.astype(np.float64, copy=False) for key, value in arrays.items()}
            r, y, supplied_phys = arrays["r"], arrays["y"], arrays["physical_fields"]
            f = arrays["f"]
            if r.shape != (N + 1,) or y.shape != (N + 1, 5) or supplied_phys.shape != (N + 1, 5) or f.shape != (N + 1,):
                check(out, "declared_shapes", False, {"r": r.shape, "y": y.shape, "physical_fields": supplied_phys.shape, "f": f.shape})
                return out
            check(out, "fixed_radial_grid", *close_array(r, np.linspace(0.0, R, N + 1), 1e-11))
            if out["failures"]:
                return out
            recon_nodes = reconstruct_profiles(r, y, epsilon)
            recon_q = gauss_reconstruct(r, y, epsilon)
            rq, fq, dfq = quadrature_f(r, f)
            check(out, "physical_fields_reconstructed", *close_array(recon_nodes["physical"], supplied_phys, 1e-11))
            check(out, "quadrature_r_reconstructed", *close_array(recon_q["r"], arrays["quadrature_r"], 1e-11))
            check(out, "quadrature_fields_reconstructed", *close_array(recon_q["fields"], arrays["quadrature_fields"], 1e-11))
            check(out, "quadrature_derivatives_reconstructed", *close_array(recon_q["derivatives"], arrays["quadrature_derivatives"], 1e-11))
            check(out, "carrier_quadrature_r_reconstructed", *close_array(rq, arrays["quadrature_r"], 1e-11))
            check(out, "carrier_f_q_reconstructed", *close_array(fq, arrays["f_q"], 1e-11))
            check(out, "carrier_df_q_reconstructed", *close_array(dfq, arrays["df_q"], 1e-11))
            check(out, "carrier_outer_dirichlet", abs(float(f[-1])) <= 1e-11, f[-1])

            if arrays["h"].shape != (N, 2):
                check(out, "h_shape", False, arrays["h"].shape)
                return out
            fields = recon_q["fields"].reshape(-1, 5)
            derivs = recon_q["derivatives"].reshape(-1, 5)
            flat_r = recon_q["r"].reshape(-1)
            fns = local_lambdas(epsilon)
            args_zero = tuple(fields[:, j] for j in range(5)) + tuple(derivs[:, j] for j in range(5)) + (np.zeros(N * 2), flat_r)
            H = np.asarray(fns["H"](*args_zero), dtype=float).reshape(N, 2)
            L = np.asarray(fns["L"](*args_zero), dtype=float).reshape(N, 2)
            check(out, "positive_h_algebraic_coefficient", bool(np.all(np.isfinite(H) & (H > 0.0))), {"minimum": float(np.min(H))})
            h = arrays["h"]
            hcalc = -L / H
            check(out, "h_reconstructed", *close_array(hcalc, h, 1e-8))
            args_h = tuple(fields[:, j] for j in range(5)) + tuple(derivs[:, j] for j in range(5)) + (h.reshape(-1), flat_r)
            core_density = np.column_stack([np.asarray(fn(*args_h), dtype=float).reshape(-1) for fn in fns["components"]]).reshape(N, 2, 6)
            core_components = np.sum((2.0 * math.pi * recon_q["r"] * 0.5 * np.diff(r)[:, None])[..., None] * core_density, axis=(0, 1))
            rho_q = np.sum(fields[:, :2] ** 2, axis=1).reshape(N, 2)
            qweight = 2.0 * math.pi * recon_q["r"] * 0.5 * np.diff(r)[:, None]
            carrier_gradient = float(np.sum(qweight * (K_CX / 2.0) * dfq**2))
            carrier_interaction = float(np.sum(qweight * (-ETA_C * (RHO0 - rho_q) * fq**2)))
            carrier_quartic = float(np.sum(qweight * (lambda_c * fq**4) / 2.0))
            carrier_components = np.array([carrier_gradient, carrier_interaction, carrier_quartic], dtype=np.float64)
            components = np.concatenate((core_components, carrier_components))
            energy = float(np.sum(components))
            hres = H * h + L
            hnorm = float(np.max(np.abs(hres) / np.maximum(1.0, np.abs(L))))
            check(out, "h_stationarity_residual", hnorm <= 1e-10, {"max_abs": float(np.max(np.abs(hres))), "normalized": hnorm})

            # Envelope derivative for y, with carrier density backreaction.
            core_gradient = np.zeros((N + 1, 5), dtype=np.float64)
            carrier_gradient_f = np.zeros(N + 1, dtype=np.float64)
            for e, dr in enumerate(np.diff(r)):
                for k, xi in enumerate(GAUSS_X):
                    weight = 2.0 * math.pi * recon_q["r"][e, k] * dr / 2.0
                    shape = np.array([(1.0 - xi) / 2.0, (1.0 + xi) / 2.0])
                    vals = fields[2 * e + k]
                    ders = derivs[2 * e + k]
                    arg = tuple(vals) + tuple(ders) + (h[e, k], recon_q["r"][e, k])
                    px = np.array([float(fn(*arg)) for fn in fns["partials"]])
                    pd = np.array([float(fn(*arg)) for fn in fns["dpartials"]])
                    f2 = float(fq[e, k] ** 2)
                    px[0] += 2.0 * ETA_C * vals[0] * f2
                    px[1] += 2.0 * ETA_C * vals[1] * f2
                    local_f = -2.0 * ETA_C * (RHO0 - rho_q[e, k]) * fq[e, k] + 2.0 * lambda_c * fq[e, k] ** 3
                    for side, node in enumerate((e, e + 1)):
                        dshape = (-1.0 / dr) if side == 0 else (1.0 / dr)
                        for j in range(5):
                            wj = recon_q["weights"][e, k, j]
                            wpj = recon_q["weight_derivatives"][e, k, j]
                            core_gradient[node, j] += weight * (px[j] * wj * shape[side] + pd[j] * (wpj * shape[side] + wj * dshape))
                        carrier_gradient_f[node] += weight * (K_CX * dfq[e, k] * dshape + local_f * shape[side])
            mass_full, lump = assemble_full_mass(r,)
            population_calc = float(f @ (mass_full @ f))
            mu_relative = float((carrier_gradient + carrier_interaction + 2.0 * carrier_quartic) / population_calc)
            constrained_gradient = carrier_gradient_f - 2.0 * mu_relative * (mass_full @ f)
            tau0 = energy - population_calc * mu_relative
            C = math.pi * J0 / 4.0
            k2 = (tau0 + C) / (K_CX * population_calc)
            escape_margin = -mu_relative - (tau0 + C) / (2.0 * population_calc)
            free_core = core_gradient[:-1].reshape(-1)
            core_mass = np.repeat(lump[:-1], 5)
            free_carrier = constrained_gradient[:-1]
            carrier_mass = lump[:-1]
            core_rms = math.sqrt(float(np.sum(free_core * free_core / core_mass) / np.sum(core_mass)))
            core_max = float(np.max(np.abs(free_core) / core_mass))
            carrier_rms = math.sqrt(float(np.sum(free_carrier * free_carrier / carrier_mass) / np.sum(carrier_mass)))
            carrier_max = float(np.max(np.abs(free_carrier) / carrier_mass))
            population_error = abs(population_calc - population) / max(1.0, abs(population))
            stationary = bool(
                core_rms < 1e-6
                and core_max < 1e-3
                and carrier_rms < 1e-6
                and carrier_max < 1e-3
                and hnorm < 1e-10
                and population_error < 1e-10
                and np.all(np.isfinite(core_gradient))
                and np.all(np.isfinite(carrier_gradient_f))
                and np.all(np.isfinite(constrained_gradient))
                and np.all(H > 0.0)
            )
            check(out, "raw_core_gradient", *close_array(core_gradient, arrays["gradient_y"], 1e-8))
            check(out, "raw_carrier_gradient", *close_array(carrier_gradient_f, arrays["gradient_f"], 1e-8))
            check(out, "raw_constrained_carrier_gradient", *close_array(constrained_gradient, arrays["carrier_constrained_gradient"], 1e-8))
            check(out, "raw_energy", *close_value(energy, float(arrays["energy"]), 1e-8))
            check(out, "raw_energy_components", *close_array(components, arrays["energy_component_values"], 1e-8))
            check(out, "population_target", population_error <= 1e-10, {"derived": population_calc, "target": population, "normalized_error": population_error})
            check(out, "core_stationarity_rms", core_rms < 1e-6, core_rms)
            check(out, "core_stationarity_max", core_max < 1e-3, core_max)
            check(out, "carrier_stationarity_rms", carrier_rms < 1e-6, carrier_rms)
            check(out, "carrier_stationarity_max", carrier_max < 1e-3, carrier_max)
            check(out, "exterior_boundary", *close_array(recon_nodes["physical"][-1], expected_boundary(epsilon), 1e-11))

            derived = {
                "energy": energy,
                "energy_components": dict(zip(COMPONENTS, components.tolist())),
                "population": population_calc,
                "mu_relative": mu_relative,
                "tau0": tau0,
                "k2": k2,
                "escape_margin": escape_margin,
                "C": C,
                "gradient_rms": core_rms,
                "gradient_max": core_max,
                "carrier_gradient_rms": carrier_rms,
                "carrier_gradient_max": carrier_max,
                "h_stationarity_max": hnorm,
                "population_error": population_error,
                "stationary": stationary,
                "mass_full_times_f": mass_full @ f,
                "gradient_y": core_gradient,
                "gradient_f": carrier_gradient_f,
                "carrier_constrained_gradient": constrained_gradient,
            }
            out["derived"] = derived
            summary_scalars = ("energy", "population", "mu_relative", "tau0", "k2", "escape_margin", "C", "gradient_rms", "gradient_max", "carrier_gradient_rms", "carrier_gradient_max", "h_stationarity_max")
            for key in summary_scalars:
                supplied = summary_row.get(key)
                ok, err = close_value(derived[key], supplied, 1e-8) if supplied is not None else (False, math.inf)
                out["raw_comparisons"][key] = {"supplied": supplied, "derived": derived[key], "normalized_error": err, "pass": ok}
                check(out, f"summary_{key}", ok, out["raw_comparisons"][key])
            supplied_components = summary_row.get("energy_components")
            if not isinstance(supplied_components, dict):
                check(out, "summary_energy_components_object", False, supplied_components)
            else:
                for key, value in derived["energy_components"].items():
                    supplied = supplied_components.get(key)
                    ok, err = close_value(value, supplied, 1e-8) if supplied is not None else (False, math.inf)
                    check(out, f"summary_energy_component_{key}", ok, {"supplied": supplied, "derived": value, "normalized_error": err})
            check(out, "summary_stationary", summary_row.get("stationary") is stationary, {"supplied": summary_row.get("stationary"), "derived": stationary})
            for key in ("cap", "epsilon", "n", "R", "N", "npz"):
                expected = cap if key == "cap" else epsilon if key == "epsilon" else population if key == "n" else R if key == "R" else N if key == "N" else npz_path.name
                check(out, f"summary_identity_{key}", summary_row.get(key) == expected, {"supplied": summary_row.get(key), "expected": expected})
            optimizer = summary_row.get("optimizer")
            check(out, "summary_optimizer_metadata", isinstance(optimizer, dict) and all(key in optimizer for key in ("success", "status", "message", "nit", "nfev", "elapsed_seconds")), optimizer)
            summary_exception = summary_row.get("exception")
            check(out, "summary_exception_absent", summary_exception is None, summary_exception)
            out["summary_exception"] = summary_exception
            out["optimizer"] = optimizer
            out["derived"]["minimum_rho"] = float(np.min(np.sum(recon_nodes["physical"][:, :2] ** 2, axis=1)))
            out["derived"]["minimum_u"] = float(np.min(recon_nodes["physical"][:, 2]))
            out["derived"]["tail_mean_coefficient"] = float(np.mean((recon_q["r"].reshape(-1) ** 2) * (RHO0 - rho_q.reshape(-1)))) if np.any((flat_r >= 16.0) & (flat_r <= 24.0)) else None
            out["qualified_stationary"] = stationary and not out["failures"]
    except Exception as exc:
        check(out, "row_execution", False, f"{type(exc).__name__}: {exc}")
    return out


def compare_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refinements: list[dict[str, Any]] = []
    domains: list[dict[str, Any]] = []
    for cap in CAPS:
        for n in POPULATIONS:
            for R, coarse_N, fine_N in ((32.0, 256, 512), (64.0, 512, 1024)):
                pair = [row for row in rows if row.get("cap") == cap and row.get("n") == n and row.get("R") == R and row.get("N") in (coarse_N, fine_N)]
                pair.sort(key=lambda row: row.get("N", 0))
                entry: dict[str, Any] = {"cap": cap, "n": n, "R": R, "coarse_N": coarse_N, "fine_N": fine_N, "checks": [], "pass": False}
                if len(pair) == 2 and all("derived" in row for row in pair):
                    for key in ("energy", "mu_relative", "tau0", "escape_margin"):
                        ok, err = close_value(pair[1]["derived"][key], pair[0]["derived"][key], 1e-3)
                        entry["checks"].append({"quantity": key, "pass": ok, "normalized_error": err, "coarse": pair[0]["derived"][key], "fine": pair[1]["derived"][key]})
                    entry["pass"] = all(item["pass"] for item in entry["checks"])
                refinements.append(entry)
            pair = [row for row in rows if row.get("cap") == cap and row.get("n") == n and (row.get("R"), row.get("N")) in ((32.0, 512), (64.0, 1024))]
            pair.sort(key=lambda row: row.get("R", 0))
            entry = {"cap": cap, "n": n, "dr": 1.0 / 16.0, "checks": [], "pass": False}
            if len(pair) == 2 and all("derived" in row for row in pair):
                ok, err = close_value(pair[1]["derived"]["mu_relative"], pair[0]["derived"]["mu_relative"], 1e-3)
                entry["checks"].append({"quantity": "mu_relative", "pass": ok, "normalized_error": err, "R32": pair[0]["derived"]["mu_relative"], "R64": pair[1]["derived"]["mu_relative"]})
                ren32 = pair[0]["derived"]["energy"] - pair[0]["derived"]["C"] * math.log(32.0)
                ren64 = pair[1]["derived"]["energy"] - pair[1]["derived"]["C"] * math.log(64.0)
                ok, err = close_value(ren64, ren32, 1e-3)
                entry["checks"].append({"quantity": "E-C*ln(R)", "pass": ok, "normalized_error": err, "R32": ren32, "R64": ren64})
                entry["pass"] = all(item["pass"] for item in entry["checks"])
            domains.append(entry)
    return refinements, domains


def calculate(manifest_path: Path, input_dir: Path) -> dict[str, Any]:
    manifest = verify_manifest(manifest_path)
    summary_path = input_dir / "summary.json"
    summary = strict_json(summary_path)
    if summary.get("schema") != PRIMARY_SCHEMA or summary.get("complete_physical_matter_formation") is not False:
        raise ValueError("primary summary schema or scope mismatch")
    parameters = summary.get("parameters")
    if parameters is not None:
        if not isinstance(parameters, dict):
            raise ValueError("optional primary parameters metadata is malformed")
        if "lambda_C" in parameters and parameters["lambda_C"] != LAMBDA_C:
            raise ValueError("primary optional lambda_C metadata disagrees with supplied witness")
        if "epsilon_infinity_subtracted" in parameters and parameters["epsilon_infinity_subtracted"] is not True:
            raise ValueError("primary optional zero-reference metadata disagrees with frozen action")
    lambda_c = LAMBDA_C
    supplied_rows = summary.get("rows")
    if not isinstance(supplied_rows, list):
        raise ValueError("primary rows are missing")
    expected = expected_rows()
    if len(supplied_rows) != len(expected):
        raise ValueError("primary row count differs from the fixed 24-row schedule")
    for row, target in zip(supplied_rows, expected):
        if not isinstance(row, dict):
            raise ValueError("primary row is not an object")
        cap, epsilon, n, R, N = target
        if (row.get("cap"), row.get("epsilon"), float(row.get("n")), float(row.get("R")), int(row.get("N"))) != (cap, epsilon, n, R, N):
            raise ValueError("primary rows differ from the fixed cap/population/grid schedule")
        expected_name = f"cap_{cap}_n{int(n)}_N{N}_R{int(R)}.npz"
        if row.get("npz") != expected_name:
            raise ValueError("primary row NPZ basename mismatch")
        if "exception" not in row:
            raise ValueError("primary row exception receipt is missing")
        if not isinstance(row.get("optimizer"), dict):
            raise ValueError("primary optimizer metadata missing")
    rows: list[dict[str, Any]] = []
    for row, target in zip(supplied_rows, expected):
        cap, epsilon, n, R, N = target
        npz_path = safe_relative_path(input_dir, row["npz"])
        rows.append(verify_row(npz_path, row, epsilon, n, R, N, lambda_c))
    refinements, domains = compare_rows(rows)
    row_qualified = bool(rows) and all(bool(row.get("qualified_stationary")) for row in rows)
    refinement_ok = all(bool(item["pass"]) for item in refinements)
    domain_ok = all(bool(item["pass"]) for item in domains)
    bulk_result = bulk_checks()
    bulk_ok = all(bool(item.get("pass")) for item in bulk_result["checks"])
    all_qualified = bool(row_qualified and refinement_ok and domain_ok and bulk_ok)
    finest = [row for row in rows if row.get("n") == 64.0 and (row.get("R"), row.get("N")) in ((32.0, 512), (64.0, 1024))]
    escape_by_cap: dict[str, dict[str, float]] = {}
    k2_by_cap: dict[str, dict[str, float]] = {}
    for cap in CAPS:
        escape_by_cap[cap] = {str(int(row["R"])): float(row["derived"]["escape_margin"]) for row in finest if row.get("cap") == cap and "derived" in row}
        k2_by_cap[cap] = {str(int(row["R"])): float(row["derived"]["k2"]) for row in finest if row.get("cap") == cap and "derived" in row}
    finest_evidence = all(
        cap in escape_by_cap
        and all(str(R) in escape_by_cap[cap] and str(R) in k2_by_cap[cap] for R in (32, 64))
        for cap in CAPS
    )
    if all_qualified and finest_evidence:
        # The local overlap witness requires one cap with positive loop-current
        # k^2 and a strict escape margin on both finest domains.
        positive_overlap = any(
            all(escape_by_cap[cap][str(R)] > 1e-3 and k2_by_cap[cap][str(R)] > 0.0 for R in (32, 64))
            for cap in CAPS
        )
        nonpositive_both = all(
            escape_by_cap[cap][str(R)] <= 0.0
            for cap in CAPS for R in (32, 64)
        )
        verdict = SUPPORTS if positive_overlap else NO_EMERGENCE if nonpositive_both else INCONCLUSIVE
    else:
        verdict = INCONCLUSIVE
    verdict_evidence = {
        "escape_margin_finest": escape_by_cap,
        "k2_finest": k2_by_cap,
        "support_requires_escape_gt_1e-3_and_k2_gt_0_on_both_R": True,
    }
    aggregate_checks = [
        {"name": "bulk_identities", "pass": bulk_ok},
        {"name": "all_rows_reconstructed", "pass": row_qualified},
        {"name": "all_refinements", "pass": refinement_ok},
        {"name": "domain_sensitivity", "pass": domain_ok},
    ]
    aggregate_failures = [item["name"] for item in aggregate_checks if not item["pass"]]
    return {
        "schema": SCHEMA,
        "checks": aggregate_checks,
        "failures": aggregate_failures,
        "manifest": manifest,
        "primary": {"input": str(summary_path.relative_to(ROOT)), "schema": summary["schema"], "row_count": len(supplied_rows), "lambda_C": lambda_c},
        "bulk": bulk_result,
        "rows": rows,
        "refinement_comparisons": refinements,
        "domain_comparisons": domains,
        "all_rows_reconstructed": row_qualified,
        "all_refinements_qualified": refinement_ok,
        "domain_sensitivity_qualified": domain_ok,
        "bulk_identities_qualified": bulk_ok,
        "verdict_evidence": verdict_evidence,
        "numerical_pass": all_qualified,
        "verdict": verdict,
        "scope": "Self-consistent neutral carrier loading of the prescribed radial vortex cores; no loop solution, formation history, physical mass, spin or statistics.",
        "complete_physical_matter_formation": False,
    }
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True, help="primary loaded-vortex output directory")
    parser.add_argument("--output", type=Path, required=True, help="new verification output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = calculate(args.manifest.resolve(), args.input.resolve())
        code = 0 if result["numerical_pass"] else 1
    except Exception as exc:
        result = {
            "schema": SCHEMA,
            "verdict": INCONCLUSIVE,
            "numerical_pass": False,
            "checks": [],
            "failures": [f"{type(exc).__name__}: {exc}"],
            "complete_physical_matter_formation": False,
        }
        code = 1
    (output / "verification.json").write_text(json.dumps(jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(jsonable(result), sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
