#!/usr/bin/env python3
"""Verify fixed instantaneous controls for filtered 3-D incompressible NS.

Run from the repository root as::

    python CassiTheory/computations/verify_navier_stokes_stress_geometry.py

The calculation is deliberately instantaneous.  It contains no flow-time
integration and no scan over a proposed regularity hypothesis.  SymPy proves
the stated identities; an independent NumPy FFT quadrature evaluates the
filtered fields at the origin for N=16,32,64, ell=0.5,1,2 and nu=1.

The final verdict describes only these fixed controls and algebraic/numerical
receipts.  It is not a regularity theorem and does not establish a universal
Cassi-to-Navier--Stokes constitutive law.
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

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
PROTOCOL_REL = "computations/navier_stokes_stress_geometry_prereg.md"
PROTOCOL_PATH = ROOT / PROTOCOL_REL
DEFAULT_OUTPUT = ROOT / "runs" / "navier_stokes_stress_geometry" / "verification.json"
SCHEMA = "cassi.navier-stokes.stress-geometry.verification.v1"
TOL = 1.0e-10


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, (float,)):
        if not math.isfinite(value):
            raise ValueError(f"non-finite numeric value: {value}")
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value


def residual(actual: Any, expected: Any) -> float:
    """Maximum absolute/scale-normalized residual, including shape checks."""
    aa = np.asarray(actual, dtype=float)
    ee = np.asarray(expected, dtype=float)
    if aa.shape != ee.shape:
        return math.inf
    if aa.size == 0:
        return 0.0
    rr = np.abs(aa - ee) / np.maximum(1.0, np.abs(ee))
    return float(np.max(rr))


def check(bucket: dict[str, Any], name: str, passed: bool, evidence: Any) -> None:
    row = {"name": name, "pass": bool(passed), "evidence": jsonable(evidence)}
    bucket["checks"].append(row)
    if not passed:
        bucket["failures"].append(name)


def spectral_derivative(field: np.ndarray, axis: int, wave_numbers: tuple[np.ndarray, ...]) -> np.ndarray:
    transformed = np.fft.fftn(field)
    shape = [1, 1, 1]
    shape[axis] = field.shape[axis]
    return np.fft.ifftn(1j * wave_numbers[axis].reshape(shape) * transformed).real


def gaussian_filter(field: np.ndarray, ell: float, k2: np.ndarray) -> np.ndarray:
    multiplier = np.exp(-0.5 * ell * ell * k2)
    return np.fft.ifftn(np.fft.fftn(field) * multiplier).real


def fft_witness(n: int, ell: float, nu: float) -> dict[str, Any]:
    """Compute every requested filtered quantity directly from FFT arrays."""
    # x,y,z are represented on [0,2*pi)^3, with index zero the origin.
    one = np.arange(n, dtype=float) * (2.0 * math.pi / n)
    x, y, z = np.meshgrid(one, one, one, indexing="ij")
    u = np.stack((np.sin(y), np.sin(z), np.sin(x)), axis=0)
    q = np.stack((np.sin(z) * np.cos(y), np.sin(x) * np.cos(z), np.sin(y) * np.cos(x)), axis=0)
    wave = tuple(np.fft.fftfreq(n, d=1.0 / n) for _ in range(3))
    kx, ky, kz = np.meshgrid(wave[0], wave[1], wave[2], indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    # The initial pressure is constant: its gradient is represented by zero.
    pressure_gradient = np.zeros_like(u)
    lap_u = np.stack(tuple(np.fft.ifftn(-k2 * np.fft.fftn(u[i])).real for i in range(3)), axis=0)
    ut_transport = -q
    ut_pressure = -pressure_gradient
    ut_viscous = nu * lap_u
    ut = ut_transport + ut_pressure + ut_viscous
    bar_u = np.stack(tuple(gaussian_filter(u[i], ell, k2) for i in range(3)), axis=0)
    bar_ut = np.stack(tuple(gaussian_filter(ut[i], ell, k2) for i in range(3)), axis=0)

    bar_uu = np.empty((3, 3, n, n, n), dtype=float)
    bar_uut = np.empty_like(bar_uu)
    split_tau_t: dict[str, np.ndarray] = {}
    for i in range(3):
        for j in range(3):
            bar_uu[i, j] = gaussian_filter(u[i] * u[j], ell, k2)
            bar_uut[i, j] = gaussian_filter(ut[i] * u[j] + u[i] * ut[j], ell, k2)
            for label, source in (("transport", ut_transport), ("pressure", ut_pressure), ("viscous", ut_viscous)):
                split_tau_t.setdefault(label, np.empty((3, 3), dtype=float))[i, j] = (
                    gaussian_filter(source[i] * u[j] + u[i] * source[j], ell, k2)[0, 0, 0]
                    - bar_u[i, 0, 0, 0] * gaussian_filter(source[j], ell, k2)[0, 0, 0]
                    - gaussian_filter(source[i], ell, k2)[0, 0, 0] * bar_u[j, 0, 0, 0]
                )

    tau_field = bar_uu - np.einsum("ixyz,jxyz->ijxyz", bar_u, bar_u)
    tau = tau_field[:, :, 0, 0, 0]
    tau_t = bar_uut[:, :, 0, 0, 0] - np.outer(bar_ut[:, 0, 0, 0], bar_u[:, 0, 0, 0]) - np.outer(bar_u[:, 0, 0, 0], bar_ut[:, 0, 0, 0])

    grad = np.empty((3, 3), dtype=float)
    grad_t = np.empty((3, 3), dtype=float)
    for i in range(3):
        for j in range(3):
            grad[i, j] = spectral_derivative(bar_u[i], j, wave)[0, 0, 0]
            grad_t[i, j] = spectral_derivative(bar_ut[i], j, wave)[0, 0, 0]
    S = 0.5 * (grad + grad.T)
    S_t = 0.5 * (grad_t + grad_t.T)
    # Resolved material derivative includes resolved advection.  It vanishes
    # at the origin only after bar_u is actually computed, not by closure.
    grad_tau = np.empty((3, 3, 3), dtype=float)
    for i in range(3):
        for j in range(3):
            for axis in range(3):
                grad_tau[i, j, axis] = spectral_derivative(tau_field[i, j], axis, wave)[0, 0, 0]
    resolved_advection = np.einsum("a,ija->ij", bar_u[:, 0, 0, 0], grad_tau)
    material_tau_t = tau_t + resolved_advection
    split_total = sum(split_tau_t.values())
    split_material = split_total + resolved_advection
    Pi = -float(np.sum(S * tau))
    Pi_t = -float(np.sum(S_t * tau) + np.sum(S * material_tau_t))
    divergence_q = sum(spectral_derivative(q[axis], axis, wave) for axis in range(3))

    g = math.exp(-0.5 * ell * ell)
    T = 0.5 * (1.0 - math.exp(-2.0 * ell * ell))
    tau_expected = T * np.eye(3)
    S_expected = 0.5 * g * np.array([[0.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]])
    tau_t_expected = -2.0 * nu * T * np.eye(3) - T * g * np.array([[0.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]])
    return {
        "N": n,
        "ell": ell,
        "nu": nu,
        "g": g,
        "T": T,
        "bar_u": bar_u[:, 0, 0, 0],
        "tau": tau,
        "S": S,
        "tau_t": tau_t,
        "material_tau_t": material_tau_t,
        "Pi": Pi,
        "Pi_t": Pi_t,
        "tau_expected": tau_expected,
        "S_expected": S_expected,
        "tau_t_expected": tau_t_expected,
        "tau_t_split": split_tau_t,
        "tau_t_split_residual": residual(split_material, material_tau_t),
        "resolved_advection_residual": float(np.max(np.abs(resolved_advection))),
        "pressure_residual": float(np.max(np.abs(split_tau_t["pressure"]))),
        "viscous_isotropic_residual": residual(split_tau_t["viscous"], -2.0 * nu * T * np.eye(3)),
        "divergence_q_residual": float(np.max(np.abs(divergence_q))),
        "S_t_trace": float(np.trace(S_t)),
        "Pi_expected": 0.0,
        "Pi_t_expected": 3.0 * T * g * g,
    }


def exact_controls() -> dict[str, Any]:
    """SymPy proof of the witness, helix, cutoff, and scaling identities."""
    x, y, z, ell, nu, sigma, a, k, t = sp.symbols("x y z ell nu sigma a k t", positive=True, real=True)
    coords = (x, y, z)
    u = sp.Matrix((sp.sin(y), sp.sin(z), sp.sin(x)))
    grad_u = u.jacobian(coords)
    q = sp.Matrix(tuple(sum(u[j] * sp.diff(u[i], coords[j]) for j in range(3)) for i in range(3)))
    div_q = sp.expand(sum(sp.diff(q[i], coords[i]) for i in range(3)))
    u_t = -q - nu * u
    g, T = sp.symbols("g T", positive=True, real=True)
    S = sp.Matrix(((0, g / 2, g / 2), (g / 2, 0, g / 2), (g / 2, g / 2, 0)))
    tau = T * sp.eye(3)
    tau_t = -2 * nu * T * sp.eye(3) - T * g * sp.Matrix(((0, 1, 1), (1, 0, 1), (1, 1, 0)))
    tau_t_dev = tau_t - sp.trace(tau_t) * sp.eye(3) / 3
    pi_t = -sp.trace(S.T * tau_t)

    exact: dict[str, Any] = {}
    exact["divergence_of_nonlinear_term"] = sp.simplify(div_q)
    exact["witness_velocity_at_origin"] = tuple(component.subs({x: 0, y: 0, z: 0}) for component in u)
    exact["witness_tangent_at_origin"] = tuple(component.subs({x: 0, y: 0, z: 0}) for component in u_t)
    exact["deviatoric_tau_t_plus_2TS"] = tau_t_dev + 2 * T * S
    exact["Pi_at_origin"] = -sp.trace(S.T * tau)
    exact["Pi_t_at_origin"] = sp.simplify(pi_t)
    exact["strain_norm"] = sp.simplify(sp.trace(S.T * S))

    s = sp.symbols("s", real=True)
    U = sp.symbols("U", positive=True, real=True)
    theta = sp.symbols("theta", real=True)
    M_helix = sp.diag(-sigma / 2, -sigma / 2, sigma)
    unit_tangent = sp.Matrix((s * sp.cos(theta), s * sp.sin(theta), 1)) / sp.sqrt(1 + s * s)
    half_unit_tangent = unit_tangent.subs(theta, theta + sp.pi)
    tangent = U * unit_tangent
    half_turn = U * half_unit_tangent
    alpha_from_contraction = sp.simplify((unit_tangent.T * M_helix * unit_tangent)[0])
    half_alpha_from_contraction = sp.simplify((half_unit_tangent.T * M_helix * half_unit_tangent)[0])
    alpha = sigma * (1 - s * s / 2) / (1 + s * s)
    phase_dyad = sp.simplify((tangent * tangent.T + half_turn * half_turn.T) / 2)
    phase_average = sp.simplify(phase_dyad.applyfunc(lambda entry: sp.integrate(entry, (theta, 0, 2 * sp.pi)) / (2 * sp.pi)))
    target_stress = U * U * sp.diag(s * s / (2 * (1 + s * s)), s * s / (2 * (1 + s * s)), 1 / (1 + s * s))
    dev = target_stress - sp.trace(target_stress) * sp.eye(3) / 3
    exact["helix_alpha_formula"] = sp.simplify(alpha_from_contraction - alpha)
    exact["helix_half_turn_alpha_difference"] = sp.simplify(half_alpha_from_contraction - alpha_from_contraction)
    exact["helix_phase_average_minus_target"] = phase_average - target_stress
    exact["helix_trace_minus_U2"] = sp.simplify(sp.trace(target_stress) - U * U)
    exact["helix_ratio_squared_minus_target_squared"] = sp.simplify(sp.trace(dev.T * dev) / (U ** 4) - (2 - s * s) ** 2 / (6 * (1 + s * s) ** 2))
    # For a0=2,k0=1,sigma=1, s(t)=2 exp(-3t/2), with crossing s^2=2.
    s_t = 2 * sp.exp(-sp.Rational(3, 2) * t)
    crossing = sp.log(2) / 3
    exact["helix_alpha_t0"] = sp.simplify(alpha.subs({sigma: 1, s: 2}))
    exact["helix_alpha_t1"] = sp.simplify(alpha.subs({sigma: 1, s: s_t.subs(t, 1)}))
    exact["helix_deformation_crossing"] = sp.simplify(s_t.subs(t, crossing) ** 2 - 2)

    m11, m22, m12, m13, m23 = sp.symbols("m11 m22 m12 m13 m23", real=True)
    m33 = -m11 - m22
    M = sp.Matrix(((m11, m12, m13), (m12, m22, m23), (m13, m23, m33)))
    X = sp.Matrix((x, y, z))
    A = -(X.cross(M * X)) / 3
    curl = lambda V: sp.Matrix((sp.diff(V[2], y) - sp.diff(V[1], z), sp.diff(V[0], z) - sp.diff(V[2], x), sp.diff(V[1], x) - sp.diff(V[0], y)))
    V = sp.simplify(curl(A))
    exact["curl_A_minus_Mx"] = sp.simplify(V - M * X)
    M0 = sp.diag(-sp.Rational(1, 2), -sp.Rational(1, 2), 1)
    A0 = sp.simplify(-(X.cross(M0 * X)) / 3)
    V0 = sp.simplify(curl(A0))
    exact["M0_A"] = A0
    exact["M0_V_minus_Mx"] = V0 - M0 * X
    exact["M0_div_V"] = sp.simplify(sum(sp.diff(V0[i], coords[i]) for i in range(3)))
    exact["M0_curl_V"] = sp.simplify(curl(V0))
    exact["M0_strain_V_minus_M"] = sp.simplify(V0.jacobian(coords) + V0.jacobian(coords).T) / 2 - M0

    lam, L = sp.symbols("lambda L", positive=True, real=True)
    velocity_exp = sp.Integer(1)
    derivative_exp = sp.Integer(1)
    spatial_jacobian_exp = sp.Integer(-3)
    tau_exp = 2 * velocity_exp
    strain_exp = velocity_exp + derivative_exp
    pi_exp = strain_exp + tau_exp
    energy_exp = 2 * velocity_exp + spatial_jacobian_exp
    # The d ell substitution contributes one power of lambda to the
    # spatially integrated stress in the R3 all-scale C integral.
    exact["C_scaling_prefactor_minus_one"] = sp.simplify(lam ** (tau_exp + spatial_jacobian_exp + 1) - 1)
    exact["tau_scaling_exponent"] = tau_exp
    exact["S_scaling_exponent"] = strain_exp
    exact["Pi_scaling_exponent"] = pi_exp
    exact["L2_energy_scaling_exponent"] = energy_exp
    exact["C_R3_scale_factor_minus_one"] = sp.simplify(lam ** (tau_exp + spatial_jacobian_exp + 1) - 1)
    # Restoring any fixed positive L2 energy with amplitude sqrt(lambda)
    # still makes strain grow as lambda^(5/2).
    exact["fixed_energy_strain_factor"] = sp.simplify(sp.sqrt(lam) * lam ** strain_exp)
    exact["fixed_energy_strain_factor_minus_lambda_5_2"] = sp.simplify(exact["fixed_energy_strain_factor"] - lam ** sp.Rational(5, 2))
    exact["fixed_energy_strain_factor_limit"] = sp.limit(exact["fixed_energy_strain_factor"], lam, sp.oo)
    exact["u_t_expression"] = u_t
    return exact


def zero_exact(value: Any) -> bool:
    if isinstance(value, sp.MatrixBase):
        return all(sp.simplify(v) == 0 for v in value)
    if isinstance(value, (tuple, list)):
        return all(zero_exact(v) for v in value)
    return sp.simplify(value) == 0


def run(output: Path) -> dict[str, Any]:
    exact = exact_controls()
    checks: dict[str, Any] = {"checks": [], "failures": []}
    exact_names = [
        "divergence_of_nonlinear_term", "witness_velocity_at_origin", "witness_tangent_at_origin",
        "deviatoric_tau_t_plus_2TS", "Pi_at_origin", "helix_alpha_formula",
        "helix_half_turn_alpha_difference", "helix_phase_average_minus_target", "helix_trace_minus_U2",
        "helix_ratio_squared_minus_target_squared", "helix_deformation_crossing", "curl_A_minus_Mx", "M0_V_minus_Mx", "M0_div_V", "M0_curl_V",
        "M0_strain_V_minus_M", "C_scaling_prefactor_minus_one", "C_R3_scale_factor_minus_one",
        "fixed_energy_strain_factor_minus_lambda_5_2",
    ]
    for name in exact_names:
        value = exact[name]
        check(checks, f"exact:{name}", zero_exact(value), str(value))
    check(checks, "exact:helix_alpha_t0_negative", exact["helix_alpha_t0"] == -sp.Rational(1, 5), str(exact["helix_alpha_t0"]))
    check(checks, "exact:helix_alpha_t1_positive", float(exact["helix_alpha_t1"].evalf()) > 0.0, str(exact["helix_alpha_t1"]))
    g_sym, T_sym = sp.symbols("g T", positive=True, real=True)
    check(checks, "exact:strain_norm_is_3g2_over_2", sp.simplify(exact["strain_norm"] - sp.Rational(3, 2) * g_sym * g_sym) == 0, str(exact["strain_norm"]))
    check(checks, "exact:Pi_t_is_3Tg2", sp.simplify(exact["Pi_t_at_origin"] - 3 * T_sym * g_sym * g_sym) == 0, str(exact["Pi_t_at_origin"]))
    check(checks, "exact:tau_scaling_exponent_2", exact["tau_scaling_exponent"] == 2, str(exact["tau_scaling_exponent"]))
    check(checks, "exact:S_scaling_exponent_2", exact["S_scaling_exponent"] == 2, str(exact["S_scaling_exponent"]))
    check(checks, "exact:Pi_scaling_exponent_4", exact["Pi_scaling_exponent"] == 4, str(exact["Pi_scaling_exponent"]))
    check(checks, "exact:L2_energy_scaling_exponent_minus_1", exact["L2_energy_scaling_exponent"] == -1, str(exact["L2_energy_scaling_exponent"]))
    check(checks, "exact:fixed_energy_strain_unbounded", exact["fixed_energy_strain_factor_limit"] == sp.oo, str(exact["fixed_energy_strain_factor_limit"]))
    numerical_rows: list[dict[str, Any]] = []
    for n in (16, 32, 64):
        for ell in (0.5, 1.0, 2.0):
            row = fft_witness(n, ell, 1.0)
            metrics = {
                "tau_residual": residual(row["tau"], row["tau_expected"]),
                "S_residual": residual(row["S"], row["S_expected"]),
                "tau_t_residual": residual(row["tau_t"], row["tau_t_expected"]),
                "material_tau_t_residual": residual(row["material_tau_t"], row["tau_t_expected"]),
                "Pi_residual": residual(row["Pi"], row["Pi_expected"]),
                "Pi_t_residual": residual(row["Pi_t"], row["Pi_t_expected"]),
                "split_residual": row["tau_t_split_residual"],
                "resolved_advection_residual": row["resolved_advection_residual"],
                "pressure_residual": row["pressure_residual"],
                "divergence_q_residual": row["divergence_q_residual"],
                "viscous_isotropic_residual": row["viscous_isotropic_residual"],
                "bar_u_residual": float(np.max(np.abs(row["bar_u"]))),
                "S_t_trace_residual": abs(row["S_t_trace"]),
            }
            row["metrics"] = metrics
            row["pass"] = all(math.isfinite(v) and v <= TOL for v in metrics.values())
            check(checks, f"fft:N{n}:ell{ell:g}", row["pass"], metrics)
            numerical_rows.append({
                "N": n, "ell": ell, "nu": 1.0, "metrics": metrics,
                "Pi": row["Pi"], "Pi_t": row["Pi_t"], "tau": row["tau"],
                "S": row["S"], "tau_t": row["tau_t"],
                "material_tau_t": row["material_tau_t"], "tau_t_split": row["tau_t_split"],
            })
    # A geometric verdict requires the relevant algebra and numerical quality.
    pi_t_positive = all(float(row["Pi_t"]) > TOL for row in numerical_rows)
    isotropy_quality = not any(
        name.startswith("fft:") or (
            name.startswith("exact:") and not name.startswith(
                ("exact:helix", "exact:curl_A", "exact:M0", "exact:C_", "exact:fixed_energy")
            )
        )
        for name in checks["failures"]
    )
    helix_quality = not any(name.startswith("exact:helix") for name in checks["failures"])
    classifications = {
        "isotropy_invariance": "CONTRADICTS" if isotropy_quality and pi_t_positive else "INCONCLUSIVE",
        "helix_shape_sustained_protection": "CONTRADICTS" if helix_quality else "INCONCLUSIVE",
        "arbitrary_data_regularity": "UNRESOLVED",
    }
    receipt = {
        "schema": SCHEMA,
        "identities": {
            "script": {"path": str(SCRIPT_PATH.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_bytes(SCRIPT_PATH)},
            "protocol": {"path": PROTOCOL_REL, "sha256": sha256_bytes(PROTOCOL_PATH) if PROTOCOL_PATH.exists() else None},
        },
        "scope": {
            "field": "u=(sin(y),sin(z),sin(x)) on T^3=(R/2pi Z)^3",
            "evaluation_point": "(0,0,0)",
            "nu": 1.0,
            "ell_values": [0.5, 1.0, 2.0],
            "FFT_resolutions": [16, 32, 64],
            "instantaneous": True,
            "flow_time_integration": False,
            "hypothesis_scan": False,
            "helix_assumptions": "equal-speed, equal-weight, zero-mean signed tangent fluctuations with two half-turn phases and uniform phase sampling; U is their common speed",
            "helix_deformation": "prescribed incompressible affine kinematics a=a0 exp(-sigma t/2), k=k0 exp(-sigma t), s=s0 exp(-3 sigma t/2), not a global NS solution",
            "cutoff_assumptions": "eta is C-infinity, eta=1 on the closed unit ball, eta=0 outside the open radius-2 ball; the added field V=curl(eta A) is compactly supported and divergence-free, equals Mx in B1, and has curl V=0 there",
            "scaling_scope": "R3 spatial integrals: tau_lambda=lambda^2 tau_(lambda ell)(lambda x), S_lambda=lambda^2 S_(lambda ell), Pi_lambda=lambda^4 Pi_(lambda ell), all-scale C invariant",
            "fixed_positive_energy_rescaling": "does not bound strain: restoring fixed L2 energy gives strain factor lambda^(5/2)",
            "universal_regulation_claim": False,
        },
        "exact": {name: str(value) for name, value in exact.items()},
        "numerical": numerical_rows,
        "tolerance": TOL,
        "checks": checks["checks"],
        "failures": checks["failures"],
        "numerical_pass": not any(name.startswith("fft:") for name in checks["failures"]),
        "control_classifications": classifications,
        "interpretation": "Passing algebra and FFT checks reproduces fixed counterexamples and identities; it does not imply a physical-regulation hypothesis or resolve arbitrary-data regularity.",
    }
    receipt = jsonable(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if receipt["failures"]:
        raise RuntimeError("verification failed: " + ", ".join(receipt["failures"]))
    for row in numerical_rows:
        m = row["metrics"]
        print(f"N={row['N']:2d} ell={row['ell']:.1f}: tau={m['tau_residual']:.3e} S={m['S_residual']:.3e} tau_t={m['tau_t_residual']:.3e} Pi={m['Pi_residual']:.3e} Pi_t={m['Pi_t_residual']:.3e}")
    print(f"isotropy invariance classification: {classifications['isotropy_invariance']}")
    print(f"helix shape classification: {classifications['helix_shape_sustained_protection']}")
    print("arbitrary-data regularity classification: UNRESOLVED")
    print("ALL CHECKS PASSED")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="fresh JSON receipt path")
    args = parser.parse_args()
    try:
        run(args.output.expanduser().resolve())
    except Exception as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
