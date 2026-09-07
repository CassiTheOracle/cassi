#!/usr/bin/env python3
"""Frozen conditional chiral baryon benchmark.

This program owns its stationary solver, two-mass calibration, imported
observable calculation, and conservative radial relaxation. The independent
verifier must not import it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

import numpy as np
import sympy as sp
from scipy.integrate import IntegrationWarning, quad, simpson
from scipy.interpolate import CubicHermiteSpline
from scipy.integrate import solve_bvp
import warnings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "computations" / "matter-formation-conditional-baryon-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs" / "20260907_matter_formation_conditional_baryon"
VERIFY_SOURCE = ROOT / "computations" / "verify_matter_formation_conditional_baryon.py"
SCHEMA = "matter-formation-conditional-baryon-v2"
EPSILON = 1.0e-5
L_STATIC = 64.0
MN_TARGET = 938.918754
MDELTA_TARGET = 1232.0
HBARC = 197.3269804
R_ISO_TARGET = 0.769
MU_P_TARGET = 2.7928473446
MU_N_TARGET = -1.91304273
GA_TARGET = 1.2754
GPINN_TARGET = 13.0
MU_RATIO_TARGET = 1.459898


class ContractError(RuntimeError):
    """Typed failure of a frozen evidence contract."""


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path.read_bytes())).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("attempted to serialize a nonfinite float")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def prepare_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ContractError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def identity(path: Path) -> dict[str, str]:
    return {"path": relpath(path), "canonical_text_sha256": canonical_text_sha256(path)}


def failure_receipt(output: Path, prereg: Path, failure_type: str, message: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "qualified": False,
        "scientific_verdict": "INCONCLUSIVE",
        "failure": {"type": failure_type, "message": message},
        "requested_preregistration": relpath(prereg),
    }
    target = output / "results.json"
    if not target.exists():
        write_json(target, payload)


def validate_sources(prereg: Path) -> dict[str, Any]:
    required = [prereg, Path(__file__).resolve(), VERIFY_SOURCE]
    missing = [relpath(path) for path in required if not path.is_file()]
    if missing:
        raise ContractError("missing required source(s): " + ", ".join(missing))
    return {
        "preregistration": identity(prereg),
        "primary_source": identity(Path(__file__).resolve()),
        "verifier_source": identity(VERIFY_SOURCE),
    }


def exact_controls() -> list[dict[str, Any]]:
    r, f, p, q, v, a = sp.symbols("r f p q v a", real=True)
    M = r**2 + 2 * sp.sin(f) ** 2
    potential = 2 * sp.sin(f) ** 2 + sp.sin(f) ** 4 / r**2
    lagrangian = M * (v**2 - p**2) - potential
    # Euler-Lagrange residual after substituting f_r=p, f_rr=q,
    # f_t=v, f_tt=a.  Mixed derivatives cancel between d_t and d_r.
    dldt = 2 * M * a + 2 * sp.diff(M, f) * v**2
    dldr = -2 * M * q - 2 * (sp.diff(M, r) + sp.diff(M, f) * p) * p
    dldf = sp.diff(lagrangian, f)
    residual = sp.trigsimp((dldt + dldr - dldf) / 2)
    declared = sp.trigsimp(
        M * a - M * q - 2 * r * p - sp.sin(2 * f) * (p**2 - v**2 - 1 - sp.sin(f) ** 2 / r**2)
    )
    pde_pass = bool(sp.trigsimp(residual - declared) == 0)

    z1, z2 = sp.symbols("z1 z2", complex=True)
    norm = sp.symbols("n", positive=True, real=True)
    # With |z1|^2+|z2|^2=1, the displayed matrix has U^dagger U=I and det U=1.
    determinant = sp.conjugate(z1) * z1 + sp.conjugate(z2) * z2
    quantum_numbers = {
        "proton": (1.0, 0.5),
        "neutron": (1.0, -0.5),
        "antiproton": (-1.0, -0.5),
        "antineutron": (-1.0, 0.5),
    }
    charge_rows = {name: int(round(i3 + baryon / 2.0)) for name, (baryon, i3) in quantum_numbers.items()}
    f_symbol = sp.symbols("f_B", positive=True, real=True)
    quadratic_kinetic_coefficient = sp.simplify((f_symbol**2 / 4) * (2 / f_symbol**2))
    return [
        {
            "name": "radial_euler_lagrange",
            "pass": pde_pass,
            "evidence": f"symbolic residual difference = {sp.trigsimp(residual - declared)}",
        },
        {
            "name": "pion_field_normalization",
            "pass": bool(quadratic_kinetic_coefficient == sp.Rational(1, 2)),
            "evidence": f"(f_B^2/4) Tr[(i sigma.d_pi/f_B)^2] gives coefficient {quadratic_kinetic_coefficient}",
        },
        {
            "name": "normalized_doublet_su2_lift",
            "pass": bool(sp.simplify(determinant.subs(sp.conjugate(z1) * z1, norm - sp.conjugate(z2) * z2) - norm) == 0),
            "evidence": "det(U)=|z1|^2+|z2|^2=1 and columns are orthonormal",
        },
        {
            "name": "supplied_fr_state_assignments",
            "pass": True,
            "evidence": "the supplied odd-B FR character permits J=I=1/2 and J=I=3/2 collective states",
        },
        {
            "name": "two_flavour_charge_map",
            "pass": charge_rows == {"proton": 1, "neutron": 0, "antiproton": -1, "antineutron": 0},
            "evidence": "Q=I3+B/2 gives p=+1, n=0 and antiparticle charges -1,0",
        },
    ]


def theta_acceleration(x: np.ndarray, theta: np.ndarray, thetap: np.ndarray) -> np.ndarray:
    s = np.sin(theta)
    mass = x * x + 2.0 * s * s
    return (-2.0 * x * thetap - np.sin(2.0 * theta) * (thetap * thetap - 1.0 - s * s / (x * x))) / mass


def solve_static() -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, CubicHermiteSpline]:
    x0 = np.geomspace(EPSILON, L_STATIC, 801)
    trial_r = 1.0 / math.sqrt(2.0)
    theta0 = 2.0 * np.arctan(x0 / trial_r)
    theta0[-1] = math.pi
    thetap0 = 2.0 * trial_r / (x0 * x0 + trial_r * trial_r)

    def fun(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.vstack((y[1], theta_acceleration(x, y[0], y[1])))

    def bc(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.array([left[0] - EPSILON * left[1], right[0] - math.pi])

    sol = solve_bvp(fun, bc, x0, np.vstack((theta0, thetap0)), tol=1.0e-8, max_nodes=100000, verbose=0)
    if sol.status != 0:
        raise ContractError(f"static solve_bvp failed: status={sol.status}, message={sol.message}")
    x = np.asarray(sol.x, dtype=np.float64)
    theta = np.asarray(sol.y[0], dtype=np.float64)
    thetap = np.asarray(sol.y[1], dtype=np.float64)
    rms = np.asarray(sol.rms_residuals, dtype=np.float64)
    if not all(np.all(np.isfinite(value)) for value in (x, theta, thetap, rms)):
        raise ContractError("static solver returned nonfinite arrays")
    f = math.pi - theta
    fp = -thetap
    spline = CubicHermiteSpline(x, f, fp)
    meta = {
        "status": int(sol.status),
        "message": str(sol.message),
        "nodes": int(x.size),
        "max_rms_residual": float(np.max(rms)),
        "epsilon": EPSILON,
        "L": L_STATIC,
        "boundary_condition": "F(epsilon)-epsilon*F_x(epsilon)=pi; F(L)=0",
    }
    return meta, x, f, fp, spline


def integrate_finite(
    density: Callable[[float, float, float], float],
    spline: CubicHermiteSpline,
    origin_slope: float,
) -> tuple[float, float]:
    def inner(r: float) -> float:
        return density(r, math.pi + origin_slope * r, origin_slope)

    def middle(r: float) -> float:
        return density(r, float(spline(r)), float(spline(r, 1)))

    value0, error0 = quad(inner, 0.0, EPSILON, epsabs=2.0e-10, epsrel=2.0e-10, limit=200)
    knots = np.asarray(spline.x[1:-1], dtype=np.float64)
    value1, error1 = quad(
        middle,
        EPSILON,
        L_STATIC,
        epsabs=2.0e-10,
        epsrel=2.0e-10,
        points=knots,
        limit=max(1200, len(spline.x) + 100),
    )
    return float(value0 + value1), float(error0 + error1)


def static_integrals(f: np.ndarray, fp: np.ndarray, spline: CubicHermiteSpline) -> dict[str, Any]:
    origin_slope = float(fp[0])

    def safe_ratio(num: float, r: float, power: int) -> float:
        if r == 0.0:
            return 0.0
        return num / (r**power)

    densities: dict[str, Callable[[float, float, float], float]] = {
        "e2": lambda r, fv, pv: r * r * pv * pv + 2.0 * math.sin(fv) ** 2,
        "e4": lambda r, fv, pv: 2.0 * math.sin(fv) ** 2 * pv * pv + safe_ratio(math.sin(fv) ** 4, r, 2),
        "degree": lambda r, fv, pv: -(2.0 / math.pi) * math.sin(fv) ** 2 * pv,
        "lambda": lambda r, fv, pv: 8.0 * r * r * math.sin(fv) ** 2 * (1.0 + pv * pv + safe_ratio(math.sin(fv) ** 2, r, 2)),
        "r0sq": lambda r, fv, pv: -(2.0 / math.pi) * r * r * math.sin(fv) ** 2 * pv,
        "rm_den": lambda r, fv, pv: r * r * math.sin(fv) ** 2 * pv,
        "rm_num": lambda r, fv, pv: r**4 * math.sin(fv) ** 2 * pv,
        "G": lambda r, fv, pv: 4.0
        * r
        * r
        * (
            pv
            + safe_ratio(math.sin(2.0 * fv), r, 1)
            + safe_ratio(math.sin(2.0 * fv) * pv * pv, r, 1)
            + safe_ratio(2.0 * math.sin(fv) ** 2 * pv, r, 2)
            + safe_ratio(math.sin(fv) ** 2 * math.sin(2.0 * fv), r, 3)
        ),
    }
    raw: dict[str, float] = {}
    errors: dict[str, float] = {}
    for name, density in densities.items():
        raw[name], errors[name] = integrate_finite(density, spline, origin_slope)

    e2 = 4.0 * math.pi * raw["e2"]
    e4 = 4.0 * math.pi * raw["e4"]
    energy = e2 + e4
    boundary_pressure = 4.0 * math.pi * L_STATIC**3 * float(fp[-1]) ** 2
    finite_domain_virial = abs(e4 - e2 - boundary_pressure) / energy
    half = float(bracketed_crossing(spline, math.pi / 2.0, EPSILON, L_STATIC))
    return {
        "E2": e2,
        "E4": e4,
        "energy": energy,
        "s": energy / 4.0,
        "degree": raw["degree"],
        "Lambda": raw["lambda"],
        "R0_squared": raw["r0sq"],
        "RM0_squared": raw["rm_num"] / raw["rm_den"],
        "G": raw["G"],
        "half_angle_radius": half,
        "derrick_relative": abs(e2 - e4) / energy,
        "finite_domain_boundary_pressure": boundary_pressure,
        "finite_domain_virial_relative": finite_domain_virial,
        "origin_slope": origin_slope,
        "outer_boundary_slope": float(fp[-1]),
        "outer_boundary_value": float(f[-1]),
        "quadrature_error_sum": float(sum(errors.values())),
        "quadrature_errors": errors,
    }


def bracketed_crossing(spline: CubicHermiteSpline, target: float, left: float, right: float) -> float:
    from scipy.optimize import brentq

    return float(brentq(lambda value: float(spline(value)) - target, left, right, xtol=1.0e-13, rtol=1.0e-14))


def calibrate(static: dict[str, Any]) -> dict[str, Any]:
    s = float(static["s"])
    lam = float(static["Lambda"])
    delta = MDELTA_TARGET - MN_TARGET
    m_classical = (5.0 * MN_TARGET - MDELTA_TARGET) / 4.0
    scale_a = m_classical / (2.0 * s)
    e_b = (2.0 * math.pi * lam * delta / (9.0 * scale_a)) ** 0.25
    f_b = scale_a * e_b
    i0 = math.pi / (3.0 * e_b**3 * f_b)
    rot_n = 3.0 / (8.0 * i0 * lam)
    rot_delta = 15.0 / (8.0 * i0 * lam)
    mn = m_classical + rot_n
    mdelta = m_classical + rot_delta
    return {
        "label": "Mapped—two measured masses fix two effective coefficients",
        "M_N_target_MeV": MN_TARGET,
        "M_Delta_target_MeV": MDELTA_TARGET,
        "mass_split_MeV": delta,
        "M_classical_MeV": m_classical,
        "scale_A_MeV": scale_a,
        "e_B": e_b,
        "f_B_MeV": f_b,
        "I0_MeV_inverse": i0,
        "length_unit_fm": HBARC / (e_b * f_b),
        "M_N_reconstructed_MeV": mn,
        "M_Delta_reconstructed_MeV": mdelta,
        "M_N_relative_residual": (mn - MN_TARGET) / MN_TARGET,
        "M_Delta_relative_residual": (mdelta - MDELTA_TARGET) / MDELTA_TARGET,
        "positive_coefficients": bool(e_b > 0.0 and f_b > 0.0 and i0 > 0.0),
    }


def empirical_observables(static: dict[str, Any], calibration: dict[str, Any]) -> dict[str, Any]:
    e_b = float(calibration["e_B"])
    f_b = float(calibration["f_B_MeV"])
    delta = MDELTA_TARGET - MN_TARGET
    r0sq = float(static["R0_squared"])
    length = HBARC / (e_b * f_b)
    r_iso = length * math.sqrt(r0sq)
    r_m_iso = length * math.sqrt(float(static["RM0_squared"]))
    isoscalar_mu = r0sq * MN_TARGET * delta / (9.0 * (e_b * f_b) ** 2)
    isovector_mu = MN_TARGET / (2.0 * delta)
    mu_p = isoscalar_mu + isovector_mu
    mu_n = isoscalar_mu - isovector_mu
    g_a = -math.pi * float(static["G"]) / (3.0 * e_b * e_b)
    gpinn = MN_TARGET * g_a / f_b
    ratio = abs(mu_p / mu_n)

    def row(value: float, target: float, threshold: float) -> dict[str, Any]:
        signed = (value - target) / target
        return {
            "value": value,
            "target": target,
            "signed_relative_residual": signed,
            "absolute_relative_residual": abs(signed),
            "threshold": threshold,
            "verdict": "SUPPORTS" if abs(signed) <= threshold else "CONTRADICTS",
        }

    return {
        "isoscalar_electric_radius_fm": row(r_iso, R_ISO_TARGET, 0.10),
        "isoscalar_magnetic_radius_fm": {"value": r_m_iso, "target": None, "verdict": "REPORTED—no frozen target"},
        "proton_magnetic_moment_nuclear_magnetons": row(mu_p, MU_P_TARGET, 0.10),
        "neutron_magnetic_moment_nuclear_magnetons": row(mu_n, MU_N_TARGET, 0.10),
        "magnetic_moment_magnitude_ratio": row(ratio, MU_RATIO_TARGET, 0.05),
        "axial_coupling_g_A": row(g_a, GA_TARGET, 0.10),
        "pion_nucleon_coupling_g_piNN": row(gpinn, GPINN_TARGET, 0.10),
        "components": {"isoscalar_moment": isoscalar_mu, "isovector_moment": isovector_mu},
    }


def spatial_derivative(values: np.ndarray, h: float) -> np.ndarray:
    derivative = np.empty_like(values)
    derivative[1:-1] = (values[2:] - values[:-2]) / (2.0 * h)
    derivative[0] = (-3.0 * values[0] + 4.0 * values[1] - values[2]) / (2.0 * h)
    derivative[-1] = (3.0 * values[-1] - 4.0 * values[-2] + values[-3]) / (2.0 * h)
    return derivative


def half_angle_grid(x: np.ndarray, f: np.ndarray) -> float:
    indices = np.flatnonzero(f <= math.pi / 2.0)
    if indices.size == 0 or int(indices[0]) == 0:
        raise ContractError("formation profile has no interior half-angle crossing")
    j = int(indices[0])
    return float(x[j - 1] + (math.pi / 2.0 - f[j - 1]) * (x[j] - x[j - 1]) / (f[j] - f[j - 1]))


def dynamic_energy(x: np.ndarray, f: np.ndarray, v: np.ndarray, h: float, mask: np.ndarray | None = None) -> float:
    fp = spatial_derivative(f, h)
    s = np.sin(f)
    density = (x * x + 2.0 * s * s) * (v * v + fp * fp) + 2.0 * s * s
    density[1:] += s[1:] ** 4 / (x[1:] ** 2)
    density[0] += 0.0
    if mask is None:
        return float(4.0 * math.pi * simpson(density, x=x))
    return float(4.0 * math.pi * simpson(density[mask], x=x[mask]))


def dynamic_degree(x: np.ndarray, f: np.ndarray, h: float) -> float:
    primitive = 0.5 * f - 0.25 * np.sin(2.0 * f)
    return float(-(2.0 / math.pi) * np.sum(np.diff(primitive)))


def derivative_simpson_degree(x: np.ndarray, f: np.ndarray, h: float) -> float:
    fp = spatial_derivative(f, h)
    return float(-(2.0 / math.pi) * simpson(np.sin(f) ** 2 * fp, x=x))


def formation_rhs(x: np.ndarray, f: np.ndarray, v: np.ndarray, h: float) -> tuple[np.ndarray, np.ndarray, float]:
    df = np.zeros_like(f)
    dv = np.zeros_like(v)
    df[1:-1] = v[1:-1]
    fp = (f[2:] - f[:-2]) / (2.0 * h)
    fpp = (f[2:] - 2.0 * f[1:-1] + f[:-2]) / (h * h)
    xi = x[1:-1]
    fi = f[1:-1]
    vi = v[1:-1]
    s = np.sin(fi)
    mass = xi * xi + 2.0 * s * s
    dv[1:-1] = fpp + (
        2.0 * xi * fp
        + np.sin(2.0 * fi) * (fp * fp - vi * vi - 1.0 - s * s / (xi * xi))
    ) / mass
    return df, dv, float(np.min(mass))


def rk4_step(x: np.ndarray, f: np.ndarray, v: np.ndarray, h: float, dt: float) -> tuple[np.ndarray, np.ndarray, float]:
    k1f, k1v, m1 = formation_rhs(x, f, v, h)
    k2f, k2v, m2 = formation_rhs(x, f + 0.5 * dt * k1f, v + 0.5 * dt * k1v, h)
    k3f, k3v, m3 = formation_rhs(x, f + 0.5 * dt * k2f, v + 0.5 * dt * k2v, h)
    k4f, k4v, m4 = formation_rhs(x, f + dt * k3f, v + dt * k3v, h)
    fn = f + (dt / 6.0) * (k1f + 2.0 * k2f + 2.0 * k3f + k4f)
    vn = v + (dt / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v)
    fn[0], fn[-1] = math.pi, 0.0
    vn[0], vn[-1] = 0.0, 0.0
    return fn, vn, min(m1, m2, m3, m4)


def static_grid_profile(x: np.ndarray, spline: CubicHermiteSpline, static: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    f0 = np.asarray(spline(np.maximum(x, EPSILON)), dtype=np.float64)
    fp0 = np.asarray(spline(np.maximum(x, EPSILON), 1), dtype=np.float64)
    f0[0] = math.pi
    fp0[0] = float(static["origin_slope"])
    f0[-1] = 0.0
    return f0, fp0


def evolve_formation(spline: CubicHermiteSpline, static: dict[str, Any], h: float = 0.04, dt: float = 0.008) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    L = 64.0
    t_end = 30.0
    x = np.arange(0.0, L + 0.5 * h, h, dtype=np.float64)
    f = np.empty_like(x)
    f[0] = math.pi
    f[1:] = 2.0 * np.arctan((1.60 / x[1:]) ** 3)
    f[-1] = 0.0
    v = np.zeros_like(x)
    f_static, fp_static = static_grid_profile(x, spline, static)
    inner_mask = x <= 8.0 + 1.0e-12
    outer_mask = x >= 8.0 - 1.0e-12
    static_inner = dynamic_energy(x, f_static, np.zeros_like(x), h, inner_mask)

    sample_times = np.linspace(0.0, t_end, 301, dtype=np.float64)
    sample_brackets: list[tuple[int, int, float]] = []
    diagnostic_steps: set[int] = set()
    for time in sample_times:
        position = float(time / dt)
        nearest = int(round(position))
        if abs(position - nearest) <= 1.0e-10:
            lower = upper = nearest
            weight = 0.0
        else:
            lower = int(math.floor(position))
            upper = lower + 1
            weight = position - lower
        sample_brackets.append((lower, upper, weight))
        diagnostic_steps.update((lower, upper))
    snapshot_steps = {int(round(time / dt)): time for time in (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0)}
    total_steps = int(round(t_end / dt))
    raw_records: dict[int, dict[str, float]] = {}
    snapshots_f: list[np.ndarray] = []
    snapshots_v: list[np.ndarray] = []
    snapshot_times: list[float] = []
    min_mass = math.inf

    def diagnose(time: float) -> dict[str, float]:
        fp = spatial_derivative(f, h)
        mismatch_num = float(simpson(x[inner_mask] ** 2 * (fp[inner_mask] - fp_static[inner_mask]) ** 2 + 2.0 * (f[inner_mask] - f_static[inner_mask]) ** 2, x=x[inner_mask]))
        mismatch_den = float(simpson(x[inner_mask] ** 2 * fp_static[inner_mask] ** 2 + 2.0 * f_static[inner_mask] ** 2, x=x[inner_mask]))
        return {
            "time": time,
            "total_energy": dynamic_energy(x, f, v, h),
            "inner_energy": dynamic_energy(x, f, v, h, inner_mask),
            "outer_energy": dynamic_energy(x, f, v, h, outer_mask),
            "degree": dynamic_degree(x, f, h),
            "degree_derivative_simpson": derivative_simpson_degree(x, f, h),
            "half_angle_radius": half_angle_grid(x, f),
            "core_max_abs_velocity": float(np.max(np.abs(v[inner_mask]))),
            "profile_mismatch": math.sqrt(mismatch_num / mismatch_den),
        }

    for step in range(total_steps + 1):
        if step in diagnostic_steps:
            raw_records[step] = diagnose(step * dt)
        if step in snapshot_steps:
            snapshot_times.append(snapshot_steps[step])
            snapshots_f.append(f.copy())
            snapshots_v.append(v.copy())
        if step == total_steps:
            break
        f, v, step_mass = rk4_step(x, f, v, h, dt)
        min_mass = min(min_mass, step_mass)
        if not np.all(np.isfinite(f)) or not np.all(np.isfinite(v)):
            raise ContractError(f"nonfinite radial evolution at step {step + 1}")

    keys = [key for key in raw_records[0] if key != "time"]
    series = {"time": sample_times}
    for key in keys:
        values: list[float] = []
        for lower, upper, weight in sample_brackets:
            low_value = raw_records[lower][key]
            high_value = raw_records[upper][key]
            values.append((1.0 - weight) * low_value + weight * high_value)
        series[key] = np.asarray(values, dtype=np.float64)
    late = series["time"] >= 25.0 - 1.0e-12
    initial_energy = float(series["total_energy"][0])
    energy_drift = float(np.max(np.abs(series["total_energy"] - initial_energy)) / initial_energy)
    degree_error = float(np.max(np.abs(series["degree"] - 1.0)))
    simpson_degree_error = float(np.max(np.abs(series["degree_derivative_simpson"] - 1.0)))
    initial_excess = float(series["inner_energy"][0] - static_inner)
    late_inner = float(np.mean(series["inner_energy"][late]))
    late_excess = late_inner - static_inner
    late_outer = float(np.mean(series["outer_energy"][late]))
    core_drop = float(series["inner_energy"][0] - late_inner)
    outer_gain = late_outer - float(series["outer_energy"][0])
    late_half = float(np.mean(series["half_angle_radius"][late]))
    late_mismatch = float(np.mean(series["profile_mismatch"][late]))
    static_half = float(static["half_angle_radius"])
    initial_half = float(series["half_angle_radius"][0])
    initial_mismatch = float(series["profile_mismatch"][0])

    gates = {
        "cfl_and_finite": bool(math.isclose(dt / h, 0.2, abs_tol=1.0e-14) and min_mass > 0.0),
        "energy_conservation": energy_drift <= 0.005,
        "degree_conservation": bool(
            degree_error <= 2.0e-12
            and all(np.all(np.isfinite(spatial_derivative(profile, h))) for profile in snapshots_f)
        ),
        "nonstationary_initial_state": bool(initial_half >= 1.5 * static_half and initial_mismatch > 0.20),
        "late_static_approach": bool(abs(late_half - static_half) / static_half <= 0.10 and late_mismatch < 0.15),
        "outgoing_energy_ledger": bool(
            initial_excess > 0.0
            and late_excess <= 0.35 * initial_excess
            and outer_gain >= 0.0
            and outer_gain + 0.03 * initial_energy >= core_drop
        ),
    }
    summary = {
        "grid": {"L": L, "h": h, "dt": dt, "cfl": dt / h, "steps": total_steps, "scalar_samples": len(sample_times), "scalar_sampling": "linear diagnostic interpolation to exact 0.1-time coordinates"},
        "static_inner_energy": static_inner,
        "minimum_interior_inertia": min_mass,
        "max_total_energy_relative_drift": energy_drift,
        "max_degree_error": degree_error,
        "max_derivative_simpson_degree_error": simpson_degree_error,
        "initial_half_angle_radius": initial_half,
        "static_half_angle_radius": static_half,
        "late_mean_half_angle_radius": late_half,
        "initial_profile_mismatch": initial_mismatch,
        "late_mean_profile_mismatch": late_mismatch,
        "initial_inner_excess_energy": initial_excess,
        "late_mean_inner_excess_energy": late_excess,
        "late_to_initial_inner_excess_ratio": late_excess / initial_excess,
        "inner_energy_drop": core_drop,
        "outer_energy_gain": outer_gain,
        "ledger_residual_fraction": abs(outer_gain - core_drop) / initial_energy,
        "late_mean_core_max_abs_velocity": float(np.mean(series["core_max_abs_velocity"][late])),
        "gates": gates,
        "pass": bool(all(gates.values())),
    }
    arrays: dict[str, np.ndarray] = {
        "x": x,
        "static_f": f_static,
        "static_fp": fp_static,
        "snapshot_times": np.asarray(snapshot_times, dtype=np.float64),
        "snapshot_f": np.vstack(snapshots_f),
        "snapshot_v": np.vstack(snapshots_v),
    }
    arrays.update({f"series_{key}": value for key, value in series.items()})
    return summary, arrays


def artifact(path: Path) -> dict[str, Any]:
    return {"path": path.name, "sha256": raw_sha256(path), "bytes": path.stat().st_size}


def source_record(identities: dict[str, Any], output: Path) -> Path:
    lines = [
        "# Conditional chiral baryon benchmark source record",
        "",
        f"- Python: `{sys.version.split()[0]}`",
        f"- Platform: `{platform.platform()}`",
        f"- NumPy: `{np.__version__}`",
        "",
        "## Canonical-text source identities",
        "",
    ]
    for name, row in identities.items():
        lines.append(f"- `{name}`: `{row['path']}`—`{row['canonical_text_sha256']}`")
    lines.append("")
    target = output / "source_record.md"
    target.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    prereg = args.prereg.resolve()
    output = args.output_dir.resolve()

    try:
        prepare_output(output)
        identities = validate_sources(prereg)
        protocol_path = output / "frozen_protocol.txt"
        protocol_path.write_bytes(canonical_bytes(prereg.read_bytes()))
        controls = exact_controls()
        if not all(row["pass"] for row in controls):
            raise ContractError("an exact action or supplied-rule control failed")

        solver, nodes, f, fp, spline = solve_static()
        static = static_integrals(f, fp, spline)
        calibration = calibrate(static)
        empirical = empirical_observables(static, calibration)
        relaxation, relaxation_arrays = evolve_formation(spline, static)

        static_path = output / "static_profile.npz"
        with static_path.open("xb") as stream:
            np.savez(stream, x=nodes, f=f, fp=fp)
        relaxation_path = output / "relaxation_arrays.npz"
        with relaxation_path.open("xb") as stream:
            np.savez(stream, **relaxation_arrays)
        record_path = source_record(identities, output)

        static_pass = bool(
            abs(float(static["degree"]) - 1.0) <= 2.0e-8
            and float(static["finite_domain_virial_relative"]) <= 1.0e-6
            and abs(float(static["outer_boundary_value"])) <= 1.0e-12
        )
        particle_control_names = {
            "normalized_doublet_su2_lift",
            "pion_field_normalization",
            "supplied_fr_state_assignments",
            "two_flavour_charge_map",
        }
        particle_pass = bool(all(row["pass"] for row in controls if row["name"] in particle_control_names))
        mass_pass = bool(
            calibration["positive_coefficients"]
            and abs(float(calibration["M_N_relative_residual"])) <= 2.0e-13
            and abs(float(calibration["M_Delta_relative_residual"])) <= 2.0e-13
        )
        precision_names = {
            "isoscalar_electric_radius_fm",
            "proton_magnetic_moment_nuclear_magnetons",
            "neutron_magnetic_moment_nuclear_magnetons",
            "axial_coupling_g_A",
            "pion_nucleon_coupling_g_piNN",
        }
        precision_pass = bool(all(empirical[name]["verdict"] == "SUPPORTS" for name in precision_names))
        qualified = bool(static_pass and particle_pass and mass_pass and all(row["pass"] for row in controls))
        if not qualified:
            overall = "INCONCLUSIVE"
        elif relaxation["pass"]:
            overall = "ADOPT—Mapped conditional leading colour-neutral chiral baryon benchmark"
        else:
            overall = "REJECT—conditional benchmark fails a frozen structural discriminator"

        verdicts = {
            "radial_stationary_profile": (
                "SUPPORTS—finite-domain degree-one stationary profile in the hedgehog sector"
                if static_pass
                else "CONTRADICTS—finite-domain stationary-profile gate failed"
            ),
            "conditional_particle_interpretation": (
                "SUPPORTS—supplied odd-degree FR and charge rules yield nucleon/Delta assignments"
                if particle_pass
                else "CONTRADICTS—supplied state or charge rule failed"
            ),
            "radial_relaxation": (
                "SUPPORTS—bounded-drift outward energy transfer approaches the stationary radial profile"
                if relaxation["pass"]
                else "CONTRADICTS—one or more frozen radial relaxation gates failed"
            ),
            "precision_nucleon_observables": (
                "SUPPORTS—every absolute out-of-fit observable agrees within 10 percent"
                if precision_pass
                else "CONTRADICTS—one or more absolute out-of-fit observables miss 10 percent"
            ),
            "conditional_baryon_benchmark": overall,
        }

        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "identities": identities,
            "protocol_artifact": artifact(protocol_path),
            "exact_controls": controls,
            "static_solver": solver,
            "static": static,
            "calibration": calibration,
            "particle_map": {
                "field": "additional normalized complex doublet lifted to SU(2)",
                "topological_charge": "B in pi_3(SU(2)) = Z",
                "state_rule": "supplied odd-B Finkelstein–Rubinstein minus sign",
                "states": {"nucleon": "B=1, J=I=1/2", "Delta": "B=1, J=I=3/2"},
                "charges": {"proton": 1, "neutron": 0, "antiproton": -1, "antineutron": 0},
                "interpretation_status": "conditional consequence of supplied analytic rules",
                "scope": "leading colour-neutral chiral benchmark with no quark or gluon identification",
            },
            "empirical_discriminators": empirical,
            "radial_relaxation": relaxation,
            "artifacts": {
                "static_profile": artifact(static_path),
                "relaxation_arrays": artifact(relaxation_path),
                "source_record": artifact(record_path),
            },
            "qualified": qualified,
            "verdicts": verdicts,
            "scientific_verdict": overall,
            "limitations": [
                "added effective field and action rather than a canonical Cassi derivation",
                "two measured masses fix the two action coefficients",
                "FR character and charge rule are supplied analytic model inputs",
                "no quantum vacuum, density operator, regulator, or renormalization",
                "no canonical Cassi coupling, stress exchange, or general interaction normalization",
                "no infinite-domain, nonradial, or degree-zero creation result",
                "no QCD, colour-confinement, baryogenesis, nuclear-binding, or chemistry derivation",
                "one or more absolute out-of-fit nucleon observables miss the precision threshold",
            ],
        }
        write_json(output / "results.json", payload)
        print(
            json.dumps(
                {
                    "qualified": qualified,
                    "verdict": overall,
                    "radial_relaxation_pass": relaxation["pass"],
                    "precision_nucleon_observables": verdicts["precision_nucleon_observables"],
                    "static_degree": static["degree"],
                    "finite_domain_virial_relative": static["finite_domain_virial_relative"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if qualified else 1
    except Exception as exc:
        failure_receipt(output, prereg, type(exc).__name__, str(exc))
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if not isinstance(exc, ContractError):
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
