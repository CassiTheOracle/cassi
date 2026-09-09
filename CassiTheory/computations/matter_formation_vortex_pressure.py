#!/usr/bin/env python3
"""Check vortex loading identities and diagnose the retained unloaded cores.

Run from the repository root:
  python computations/matter_formation_vortex_pressure.py --manifest runs/20260908_matter_formation_vortex_pressure/manifest.json

No core is reoptimized. The finite-element virial residuals are descriptive
post-calculation diagnostics, separate from the frozen core qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
RHO0, A, D, V, G = 1.2, 0.83, 1.25, 0.9, 0.71
PHI = (1.0 + math.sqrt(5.0)) / 2.0
C0 = PHI ** -3
J0 = 4 * A * RHO0 * D * V**2 * (1 - C0**2) / (A * RHO0 + 4 * D * V**2)
C = math.pi * J0 / 4
COMPONENTS = ("fundamental_radial", "adjoint_radial", "fundamental_angular", "adjoint_angular", "magnetic", "potential")
SIGMA = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]], dtype=complex)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_identities() -> dict:
    S, M, P, T, I, U, eps = sp.symbols("S M V K I U epsilon", real=True)
    n, K, k, c, scale, amp, L, Q, gamma = sp.symbols("n K_Cx k C scale amp L Q gamma", positive=True)
    w = sp.Symbol("w", integer=True)
    energy = S + M + P + T + I + U + eps * n
    amplitude_energy = S + M + P + amp * (T + I + eps * n) + amp**2 * U
    mu = sp.diff(amplitude_energy, amp).subs(amp, 1) / n
    population_residual = sp.expand((mu - eps) * n - T - I - 2 * U)
    branch = sp.Function("e0")
    ring_energy = L * branch(Q / L) + K * (2 * sp.pi * w / L)**2 * Q / 2
    n_expr, k_expr = Q / L, 2 * sp.pi * w / L
    tension_general = sp.diff(ring_energy, L)
    expected = branch(n_expr) - n_expr * sp.diff(branch(n_expr), Q) * L - K * k_expr**2 * n_expr
    fixed_population_residual = sp.simplify(tension_general - expected)
    tau = sp.expand(energy - n * mu - K * k**2 * n)
    tension_residual = sp.expand(tau - (S + M + P - U - K * k**2 * n))
    dilation = S - c * sp.log(scale) + (M + T + U) / scale**2 + P * scale**2 + I + eps * n
    virial = sp.diff(dilation, scale).subs(scale, 1)
    virial_residual = sp.expand(virial - (2 * (P - M - T - U) - c))
    potential_on_shell = sp.solve(virial, P)[0]
    combined = sp.expand(tau.subs(P, potential_on_shell))
    combined_residual = sp.expand(combined - (S + 2 * M + T + c / 2 - K * k**2 * n))
    current_required = sp.solve(combined, k**2)[0]
    mu0 = sp.Symbol("mu0", real=True)
    escape_residual = sp.simplify(2 * n * (mu0 + K * current_required / 2 - eps) - (S + 2 * M + T + c / 2 - 2 * n * (eps - mu0)))
    ir_energy = L * (branch(Q / L) + c * sp.log(gamma * L)) + K * k_expr**2 * Q / 2
    ir_residual = sp.simplify(sp.diff(ir_energy, L) - tension_general - c * sp.log(gamma * L) - c)

    p, q, u, b1, b3, sig, h, pr, qr, ur, b1r, b3r, fr = sp.symbols("p q u b1 b3 sig h pr qr ur b1r b3r fr", real=True)
    aa, dd, gg, rr = sp.symbols("a d g r", positive=True)
    radial = aa * ((pr - h * q / 2)**2 + (qr + h * p / 2)**2) / 2 + dd * (ur**2 + h**2 * u**2) / 2
    magnetic = dd * ((b1r + h * (b3 - sig))**2 + (b3r - h * b1)**2) / (2 * gg**2 * rr**2)
    quadratic = radial + magnetic + K * fr**2 / 2
    jets = (pr, qr, ur, b1r, b3r, h, fr)
    boundary_residual = sp.expand(sum(x * sp.diff(quadratic, x) for x in jets) - 2 * quadratic)
    residuals = {
        "population_from_amplitude_variation": population_residual,
        "length_derivative_fixed_population_and_winding": fixed_population_residual,
        "population_reduced_tension": tension_residual,
        "transverse_dilation": virial_residual,
        "combined_stress": combined_residual,
        "loop_escape_overlap": escape_residual,
        "logarithmic_exterior_length_derivative": ir_residual,
        "boundary_momentum_contraction": boundary_residual,
    }
    return {
        "residuals": {name: str(value) for name, value in residuals.items()},
        "checks": {name: bool(value == 0) for name, value in residuals.items()},
        "current_free_tension": str(combined.subs(k, 0)),
        "required_current_wave_number_squared": str(current_required),
        "scope": "Stationary, localized, carrier-loaded straight cores and leading slender-loop stress; no loaded family or three-dimensional loop is solved.",
    }


def profiles(r: np.ndarray, coefficients: np.ndarray, slopes: np.ndarray, cap: int) -> tuple[np.ndarray, np.ndarray]:
    weights = np.ones_like(coefficients)
    derivatives = np.zeros_like(coefficients)
    w1 = r / np.sqrt(1 + r**2)
    w1p = (1 + r**2)**-1.5
    weights[:, 0 if cap == 1 else 1] = w1
    derivatives[:, 0 if cap == 1 else 1] = w1p
    weights[:, 3], derivatives[:, 3] = w1, w1p
    weights[:, 4], derivatives[:, 4] = r**2 / (1 + r**2), 2 * r / (1 + r**2)**2
    return coefficients * weights, slopes * weights + coefficients * derivatives


def component_densities(r: np.ndarray, fields: np.ndarray, derivatives: np.ndarray, cap: int) -> tuple[np.ndarray, np.ndarray]:
    p, q, u, b1, b3 = fields.T
    pr, qr, ur, b1r, b3r = derivatives.T
    rho = p**2 + q**2
    H = A * rho / 4 + D * u**2 + D * ((b3 - cap)**2 + b1**2) / (G**2 * r**2)
    source = A * (p * qr - q * pr) / 2 + D * ((b3 - cap) * b1r - b1 * b3r) / (G**2 * r**2)
    if not np.all(np.isfinite(H) & (H > 0)):
        raise ValueError("Nonpositive or nonfinite radial connection coefficient")
    h = -source / H
    zeros = np.zeros_like(r)
    ar = np.column_stack((zeros, h, zeros))
    at = np.column_stack((b1, zeros, b3))
    adjoint = np.column_stack((zeros, zeros, u))
    psi = np.column_stack((p, q)).astype(complex)
    ny, ni = (1, 0) if cap == 1 else (0, 1)
    dr_psi = np.column_stack((pr, qr)) - 0.5j * np.einsum("na,aij,nj->ni", ar, SIGMA, psi)
    dt_psi = 1j * psi * np.array([ny, ni]) - 0.5j * np.einsum("na,aij,nj->ni", at, SIGMA, psi)
    dr_phi = np.column_stack((zeros, zeros, ur)) + np.cross(ar, adjoint)
    dt_phi = np.cross(at, adjoint)
    curvature = np.column_stack((b1r - cap * h, zeros, b3r)) + np.cross(ar, at)
    norm = lambda x: np.sum(np.abs(x)**2, axis=1)
    spin = np.einsum("ni,aij,nj->na", psi.conj(), SIGMA, psi).real
    delta = ((1 - PHI) * norm(psi) + (1 + PHI) * np.sum(spin * adjoint, axis=1) / V) / 2
    potential = (rho - RHO0)**2 / 4 + delta**2 / 2 + (u**2 - V**2)**2 / 4
    densities = np.column_stack((A * norm(dr_psi) / 2, D * norm(dr_phi) / 2, A * norm(dt_psi) / (2 * r**2), D * norm(dt_phi) / (2 * r**2), D * norm(curvature) / (2 * G**2 * r**2), potential))
    return densities, H * h + source


def retained_row(row: dict) -> dict:
    path = ROOT / row["path"]
    if sha256(path) != row["sha256"]:
        raise ValueError(f"Input hash mismatch: {row['path']}")
    with np.load(path, allow_pickle=False) as data:
        r, y = np.asarray(data["r"]), np.asarray(data["y"])
        reference = np.asarray(data["energy_component_values"])
        reference_total = float(data["energy"])
    if y.shape != (row["N"] + 1, 5) or r.shape != (row["N"] + 1,):
        raise ValueError("Unexpected retained grid shape")
    if not all(np.all(np.isfinite(x)) for x in (r, y, reference, reference_total)):
        raise ValueError("Nonfinite retained data")
    if not np.array_equal(r, np.linspace(0, row["R"], row["N"] + 1)):
        raise ValueError("Retained grid differs from declared schedule")
    cap = row["epsilon"]
    dr = np.diff(r)
    t = (1 + np.array([-1, 1]) / math.sqrt(3)) / 2
    rq = r[:-1, None] + dr[:, None] * t
    yq = y[:-1, None, :] * (1 - t[None, :, None]) + y[1:, None, :] * t[None, :, None]
    slopes = np.diff(y, axis=0) / dr[:, None]
    field, derivative = profiles(rq.ravel(), yq.reshape(-1, 5), np.repeat(slopes, 2, axis=0), cap)
    density, hres = component_densities(rq.ravel(), field, derivative, cap)
    weights = (math.pi * rq * dr[:, None]).ravel()
    energies = np.sum(weights[:, None] * density, axis=0)
    component_error = float(np.max(np.abs(energies - reference) / np.maximum(1, np.abs(reference))))
    total_error = abs(float(np.sum(energies)) - reference_total) / max(1, abs(reference_total))
    outer_fields, outer_derivatives = profiles(r[-1:], y[-1:], slopes[-1:], cap)
    outer_density, outer_hres = component_densities(r[-1:], outer_fields, outer_derivatives, cap)
    outer = outer_density[0]
    momentum_contraction = 2 * (outer[0] + outer[1] + outer[4])
    boundary = float(2 * math.pi * r[-1]**2 * (np.sum(outer) - momentum_contraction))
    scalar_gradient = float(np.sum(energies[:4]))
    magnetic, potential = map(float, energies[4:])
    residual = 2 * (potential - magnetic) - boundary
    return {
        "cap": "plus" if cap == 1 else "minus", "epsilon": cap, "R": row["R"], "N": row["N"],
        "path": row["path"], "sha256": row["sha256"], "component_energies": dict(zip(COMPONENTS, energies.tolist())),
        "checks": {"component_reconstruction": component_error <= 1e-8, "total_energy_reconstruction": total_error <= 1e-8},
        "component_error": component_error, "total_error": total_error,
        "radial_connection_residual_max_abs": max(float(np.max(np.abs(hres))), float(np.max(np.abs(outer_hres)))),
        "boundary_B_R": boundary, "asymptotic_C": C, "boundary_minus_asymptote": boundary - C,
        "virial_residual": residual, "virial_residual_normalized": residual / max(1, abs(boundary)),
        "unloaded_tension_from_energy": float(np.sum(energies)),
        "unloaded_tension_from_virial": scalar_gradient + 2 * magnetic + boundary / 2,
    }


def calculate(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256(Path(__file__)) != manifest["source"]["sha256"]:
        raise ValueError("Calculation source differs from frozen manifest")
    section = manifest_path.parent / manifest["section"]["snapshot"]
    if sha256(section) != manifest["section"]["sha256"]:
        raise ValueError("Frozen section hash mismatch")
    expected = [(cap, R, N) for cap in (1, -1) for R, N in ((32, 256), (32, 512), (64, 512), (64, 1024))]
    if [(x["epsilon"], x["R"], x["N"]) for x in manifest["arrays"]] != expected:
        raise ValueError("Input rows differ from the frozen eight-row schedule")
    identities = exact_identities()
    rows = [retained_row(x) for x in manifest["arrays"]]
    refinements = []
    for cap in (1, -1):
        for radius in (32, 64):
            pair = [x for x in rows if x["epsilon"] == cap and x["R"] == radius]
            coarse, fine = [abs(x["virial_residual"]) for x in pair]
            refinements.append({"epsilon": cap, "R": radius, "coarse_abs_residual": coarse, "fine_abs_residual": fine, "fine_over_coarse": fine / coarse if coarse else None})
    passed = all(identities["checks"].values()) and all(all(x["checks"].values()) for x in rows)
    return {"schema": "matter-formation-vortex-pressure-v1", "verdict": "PASS" if passed else "FAIL", "identities": identities, "rows": rows, "refinements": refinements, "virial_diagnostic_has_acceptance_threshold": False, "complete_physical_matter_formation": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = calculate(args.manifest.resolve())
        text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    except Exception as exc:
        result = {"schema": "matter-formation-vortex-pressure-v1", "verdict": "INCONCLUSIVE", "error": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
        text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    print(text)
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
