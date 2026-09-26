#!/usr/bin/env python3
"""Independent verification of the conditional chiral baryon benchmark.

This file imports nothing from the primary calculation. It uses an independent
static mesh, fixed Gauss–Legendre quadrature, the complementary angle
theta=pi-F, and a second radial resolution.
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
from numpy.polynomial.legendre import leggauss
from scipy.integrate import simpson, solve_bvp
from scipy.interpolate import CubicHermiteSpline
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "computations" / "matter-formation-conditional-baryon-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "matter_formation_conditional_baryon.py"
DEFAULT_PRIMARY = ROOT / "runs" / "20260907_matter_formation_conditional_baryon"
DEFAULT_OUTPUT = ROOT / "runs" / "20260907_matter_formation_conditional_baryon_verification"
SCHEMA = "matter-formation-conditional-baryon-verification-v2"
EPS = 1.0e-5
BOUND = 64.0
MN = 938.918754
MDELTA = 1232.0
HBARC = 197.3269804
TARGETS = {
    "isoscalar_electric_radius_fm": (0.769, 0.10),
    "proton_magnetic_moment_nuclear_magnetons": (2.7928473446, 0.10),
    "neutron_magnetic_moment_nuclear_magnetons": (-1.91304273, 0.10),
    "magnetic_moment_magnitude_ratio": (1.459898, 0.05),
    "axial_coupling_g_A": (1.2754, 0.10),
    "pion_nucleon_coupling_g_piNN": (13.0, 0.10),
}


class VerificationError(RuntimeError):
    """Typed verifier contract failure."""


def normalized(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_text_digest(path: Path) -> str:
    return hashlib.sha256(normalized(path.read_bytes())).hexdigest()


def raw_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def make_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise VerificationError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationError("nonfinite verifier output")
    return value


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def fail(output: Path, primary: Path, prereg: Path, failure_type: str, message: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    target = output / "verification.json"
    if not target.exists():
        save_json(
            target,
            {
                "schema": SCHEMA,
                "qualified": False,
                "verdict": "INCONCLUSIVE",
                "failure": {"type": failure_type, "message": message},
                "requested_primary": relative(primary),
                "requested_preregistration": relative(prereg),
            },
        )


def finite_tree(value: Any, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(finite_tree(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(finite_tree(item, f"{path}[{index}]"))
    elif isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{path} is nonfinite")
    return errors
def independent_model_controls() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    radius, field, field_r, field_rr, field_t, field_tt = sp.symbols(
        "r F F_r F_rr F_t F_tt", real=True
    )
    inertia = radius**2 + 2 * sp.sin(field) ** 2
    lagrangian = inertia * (field_t**2 - field_r**2) - (
        2 * sp.sin(field) ** 2 + sp.sin(field) ** 4 / radius**2
    )
    dldt = 2 * inertia * field_tt + 2 * sp.diff(inertia, field) * field_t**2
    dldr = -2 * inertia * field_rr - 2 * (
        sp.diff(inertia, radius) + sp.diff(inertia, field) * field_r
    ) * field_r
    residual = sp.trigsimp((dldt + dldr - sp.diff(lagrangian, field)) / 2)
    declared = sp.trigsimp(
        inertia * field_tt
        - inertia * field_rr
        - 2 * radius * field_r
        - sp.sin(2 * field)
        * (field_r**2 - field_t**2 - 1 - sp.sin(field) ** 2 / radius**2)
    )

    z1, z2, norm = sp.symbols("z1 z2 n", complex=True)
    determinant = sp.conjugate(z1) * z1 + sp.conjugate(z2) * z2
    f_symbol = sp.symbols("f_B", positive=True, real=True)
    kinetic_coefficient = sp.simplify((f_symbol**2 / 4) * (2 / f_symbol**2))
    assignments = {
        "nucleon": {"B": 1, "J": "1/2", "I": "1/2"},
        "Delta": {"B": 1, "J": "3/2", "I": "3/2"},
    }
    quantum_numbers = {
        "proton": (1, 0.5),
        "neutron": (1, -0.5),
        "antiproton": (-1, -0.5),
        "antineutron": (-1, 0.5),
    }
    charges = {name: int(round(i3 + baryon / 2.0)) for name, (baryon, i3) in quantum_numbers.items()}
    controls = [
        {
            "name": "radial_euler_lagrange",
            "pass": bool(sp.trigsimp(residual - declared) == 0),
            "evidence": f"independent symbolic residual difference = {sp.trigsimp(residual - declared)}",
        },
        {
            "name": "pion_field_normalization",
            "pass": bool(kinetic_coefficient == sp.Rational(1, 2)),
            "evidence": f"independent quadratic kinetic coefficient = {kinetic_coefficient}",
        },
        {
            "name": "normalized_doublet_su2_lift",
            "pass": bool(
                sp.simplify(
                    determinant.subs(
                        sp.conjugate(z1) * z1,
                        norm - sp.conjugate(z2) * z2,
                    )
                    - norm
                )
                == 0
            ),
            "evidence": "independent determinant and column-norm reduction gives |z1|^2+|z2|^2=1",
        },
        {
            "name": "supplied_fr_state_assignments",
            "pass": assignments
            == {
                "nucleon": {"B": 1, "J": "1/2", "I": "1/2"},
                "Delta": {"B": 1, "J": "3/2", "I": "3/2"},
            },
            "evidence": "odd B has supplied FR character -1 and the declared J=I half-integer states are allowed",
        },
        {
            "name": "two_flavour_charge_map",
            "pass": charges == {"proton": 1, "neutron": 0, "antiproton": -1, "antineutron": 0},
            "evidence": "independent Q=I3+B/2 evaluation",
        },
    ]
    particle_map = {
        "field": "additional normalized complex doublet lifted to SU(2)",
        "topological_charge": "B in pi_3(SU(2)) = Z",
        "state_rule": "supplied odd-B Finkelstein–Rubinstein minus sign",
        "states": {"nucleon": "B=1, J=I=1/2", "Delta": "B=1, J=I=3/2"},
        "charges": charges,
        "interpretation_status": "conditional consequence of supplied analytic rules",
        "scope": "leading colour-neutral chiral benchmark with no quark or gluon identification",
    }
    return controls, particle_map


def theta_ode(radius: np.ndarray, angle: np.ndarray, slope: np.ndarray) -> np.ndarray:
    sine = np.sin(angle)
    inertia = radius**2 + 2.0 * sine**2
    return (-2.0 * radius * slope - np.sin(2.0 * angle) * (slope**2 - 1.0 - sine**2 / radius**2)) / inertia


def independent_static() -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, CubicHermiteSpline]:
    left = np.geomspace(EPS, 1.0, 651)
    right = np.linspace(1.0, BOUND, 751)[1:]
    mesh = np.concatenate((left, right))
    scale = 0.82
    guess = 2.0 * np.arctan(mesh / scale)
    guess[-1] = math.pi
    guess_p = 2.0 * scale / (mesh**2 + scale**2)

    def equations(radius: np.ndarray, state: np.ndarray) -> np.ndarray:
        return np.vstack((state[1], theta_ode(radius, state[0], state[1])))

    def boundaries(near: np.ndarray, far: np.ndarray) -> np.ndarray:
        return np.asarray((near[0] - EPS * near[1], far[0] - math.pi))

    result = solve_bvp(equations, boundaries, mesh, np.vstack((guess, guess_p)), tol=1.0e-8, max_nodes=150000, verbose=0)
    if result.status != 0:
        raise VerificationError(f"independent static solve failed: {result.status} {result.message}")
    radius = np.asarray(result.x, dtype=np.float64)
    f = math.pi - np.asarray(result.y[0], dtype=np.float64)
    fp = -np.asarray(result.y[1], dtype=np.float64)
    residuals = np.asarray(result.rms_residuals, dtype=np.float64)
    if not all(np.all(np.isfinite(array)) for array in (radius, f, fp, residuals)):
        raise VerificationError("independent static solution is nonfinite")
    spline = CubicHermiteSpline(radius, f, fp)
    return (
        {
            "status": int(result.status),
            "message": str(result.message),
            "nodes": int(radius.size),
            "max_rms_residual": float(np.max(residuals)),
            "boundary_condition": "F(epsilon)-epsilon*F_x(epsilon)=pi; F(L)=0",
        },
        radius,
        f,
        fp,
        spline,
    )


def fixed_quadrature(
    density: Callable[[float, float, float], float],
    spline: CubicHermiteSpline,
    origin_slope: float,
) -> float:
    nodes, weights = leggauss(32)
    edges = np.concatenate(
        (
            np.asarray((0.0, EPS)),
            np.geomspace(EPS, 1.0, 181)[1:],
            np.linspace(1.0, BOUND, 421)[1:],
        )
    )
    total = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        midpoint = 0.5 * (lower + upper)
        halfwidth = 0.5 * (upper - lower)
        for node, weight in zip(nodes, weights):
            radius = midpoint + halfwidth * float(node)
            if radius < EPS:
                value, slope = math.pi + origin_slope * radius, origin_slope
            else:
                value, slope = float(spline(radius)), float(spline(radius, 1))
            total += halfwidth * float(weight) * density(radius, value, slope)
    return float(total)


def independent_integrals(f: np.ndarray, fp: np.ndarray, spline: CubicHermiteSpline) -> dict[str, float]:
    slope0 = float(fp[0])

    def div(number: float, radius: float, power: int) -> float:
        return number / radius**power if radius != 0.0 else 0.0

    fields: dict[str, Callable[[float, float, float], float]] = {
        "e2": lambda r, y, p: r**2 * p**2 + 2.0 * math.sin(y) ** 2,
        "e4": lambda r, y, p: 2.0 * math.sin(y) ** 2 * p**2 + div(math.sin(y) ** 4, r, 2),
        "degree": lambda r, y, p: -(2.0 / math.pi) * math.sin(y) ** 2 * p,
        "lambda": lambda r, y, p: 8.0 * r**2 * math.sin(y) ** 2 * (1.0 + p**2 + div(math.sin(y) ** 2, r, 2)),
        "r0": lambda r, y, p: -(2.0 / math.pi) * r**2 * math.sin(y) ** 2 * p,
        "rm2": lambda r, y, p: r**2 * math.sin(y) ** 2 * p,
        "rm4": lambda r, y, p: r**4 * math.sin(y) ** 2 * p,
        "g": lambda r, y, p: 4.0
        * r**2
        * (
            p
            + div(math.sin(2.0 * y), r, 1)
            + div(math.sin(2.0 * y) * p**2, r, 1)
            + div(2.0 * math.sin(y) ** 2 * p, r, 2)
            + div(math.sin(y) ** 2 * math.sin(2.0 * y), r, 3)
        ),
    }
    values = {name: fixed_quadrature(fun, spline, slope0) for name, fun in fields.items()}
    e2 = 4.0 * math.pi * values["e2"]
    e4 = 4.0 * math.pi * values["e4"]
    energy = e2 + e4
    boundary_pressure = 4.0 * math.pi * BOUND**3 * float(fp[-1]) ** 2
    finite_domain_virial = abs(e4 - e2 - boundary_pressure) / energy
    half = float(brentq(lambda r: float(spline(r)) - math.pi / 2.0, EPS, BOUND, xtol=1.0e-13, rtol=1.0e-14))
    return {
        "E2": e2,
        "E4": e4,
        "energy": energy,
        "s": energy / 4.0,
        "degree": values["degree"],
        "Lambda": values["lambda"],
        "R0_squared": values["r0"],
        "RM0_squared": values["rm4"] / values["rm2"],
        "G": values["g"],
        "half_angle_radius": half,
        "derrick_relative": abs(e2 - e4) / energy,
        "finite_domain_boundary_pressure": boundary_pressure,
        "finite_domain_virial_relative": finite_domain_virial,
        "origin_slope": slope0,
        "outer_boundary_slope": float(fp[-1]),
        "outer_boundary_value": float(f[-1]),
    }


def independent_calibration(static: dict[str, float]) -> dict[str, float | bool | str]:
    gap = MDELTA - MN
    classical = (5.0 * MN - MDELTA) / 4.0
    a = classical / (2.0 * static["s"])
    e = (2.0 * math.pi * static["Lambda"] * gap / (9.0 * a)) ** 0.25
    f = a * e
    inertia_scale = math.pi / (3.0 * e**3 * f)
    mn_back = classical + 3.0 / (8.0 * inertia_scale * static["Lambda"])
    delta_back = classical + 15.0 / (8.0 * inertia_scale * static["Lambda"])
    return {
        "label": "Mapped—two measured masses fix two effective coefficients",
        "e_B": e,
        "f_B_MeV": f,
        "I0_MeV_inverse": inertia_scale,
        "length_unit_fm": HBARC / (e * f),
        "M_classical_MeV": classical,
        "M_N_reconstructed_MeV": mn_back,
        "M_Delta_reconstructed_MeV": delta_back,
        "positive_coefficients": bool(e > 0.0 and f > 0.0 and inertia_scale > 0.0),
    }


def independent_observables(static: dict[str, float], calibration: dict[str, Any]) -> dict[str, Any]:
    e = float(calibration["e_B"])
    f = float(calibration["f_B_MeV"])
    gap = MDELTA - MN
    r0 = static["R0_squared"]
    radius = HBARC * math.sqrt(r0) / (e * f)
    magnetic_radius = HBARC * math.sqrt(static["RM0_squared"]) / (e * f)
    iso_scalar = r0 * MN * gap / (9.0 * (e * f) ** 2)
    iso_vector = MN / (2.0 * gap)
    proton = iso_scalar + iso_vector
    neutron = iso_scalar - iso_vector
    ga = -math.pi * static["G"] / (3.0 * e**2)
    gpinn = MN * ga / f
    raw = {
        "isoscalar_electric_radius_fm": radius,
        "proton_magnetic_moment_nuclear_magnetons": proton,
        "neutron_magnetic_moment_nuclear_magnetons": neutron,
        "magnetic_moment_magnitude_ratio": abs(proton / neutron),
        "axial_coupling_g_A": ga,
        "pion_nucleon_coupling_g_piNN": gpinn,
    }
    rows: dict[str, Any] = {}
    for name, value in raw.items():
        target, threshold = TARGETS[name]
        residual = (value - target) / target
        rows[name] = {
            "value": value,
            "target": target,
            "signed_relative_residual": residual,
            "absolute_relative_residual": abs(residual),
            "threshold": threshold,
            "verdict": "SUPPORTS" if abs(residual) <= threshold else "CONTRADICTS",
        }
    rows["isoscalar_magnetic_radius_fm"] = {"value": magnetic_radius, "target": None, "verdict": "REPORTED—no frozen target"}
    rows["components"] = {"isoscalar_moment": iso_scalar, "isovector_moment": iso_vector}
    return rows


def derivative(y: np.ndarray, dx: float) -> np.ndarray:
    answer = np.empty_like(y)
    answer[1:-1] = (y[2:] - y[:-2]) / (2.0 * dx)
    answer[0] = (-3.0 * y[0] + 4.0 * y[1] - y[2]) / (2.0 * dx)
    answer[-1] = (3.0 * y[-1] - 4.0 * y[-2] + y[-3]) / (2.0 * dx)
    return answer


def energy(radius: np.ndarray, theta: np.ndarray, speed: np.ndarray, dx: float, select: np.ndarray | None = None) -> float:
    slope = derivative(theta, dx)
    sine = np.sin(theta)
    density = (radius**2 + 2.0 * sine**2) * (speed**2 + slope**2) + 2.0 * sine**2
    density[1:] += sine[1:] ** 4 / radius[1:] ** 2
    if select is not None:
        radius = radius[select]
        density = density[select]
    return float(4.0 * math.pi * simpson(density, x=radius))


def degree(radius: np.ndarray, theta: np.ndarray, dx: float) -> float:
    primitive = 0.5 * theta - 0.25 * np.sin(2.0 * theta)
    return float((2.0 / math.pi) * np.sum(np.diff(primitive)))


def derivative_simpson_degree(radius: np.ndarray, theta: np.ndarray, dx: float) -> float:
    return float((2.0 / math.pi) * simpson(np.sin(theta) ** 2 * derivative(theta, dx), x=radius))


def crossing(radius: np.ndarray, theta: np.ndarray) -> float:
    locations = np.flatnonzero(theta >= math.pi / 2.0)
    if locations.size == 0 or int(locations[0]) == 0:
        raise VerificationError("independent formation has no half-angle crossing")
    j = int(locations[0])
    return float(radius[j - 1] + (math.pi / 2.0 - theta[j - 1]) * (radius[j] - radius[j - 1]) / (theta[j] - theta[j - 1]))


def theta_rhs(radius: np.ndarray, theta: np.ndarray, speed: np.ndarray, dx: float) -> tuple[np.ndarray, np.ndarray, float]:
    angle_rate = np.zeros_like(theta)
    acceleration = np.zeros_like(speed)
    angle_rate[1:-1] = speed[1:-1]
    slope = (theta[2:] - theta[:-2]) / (2.0 * dx)
    curvature = (theta[2:] - 2.0 * theta[1:-1] + theta[:-2]) / dx**2
    r = radius[1:-1]
    y = theta[1:-1]
    w = speed[1:-1]
    sine = np.sin(y)
    inertia = r**2 + 2.0 * sine**2
    acceleration[1:-1] = curvature + (
        2.0 * r * slope
        + np.sin(2.0 * y) * (slope**2 - w**2 - 1.0 - sine**2 / r**2)
    ) / inertia
    return angle_rate, acceleration, float(np.min(inertia))


def theta_step(radius: np.ndarray, theta: np.ndarray, speed: np.ndarray, dx: float, dt: float) -> tuple[np.ndarray, np.ndarray, float]:
    a1, b1, m1 = theta_rhs(radius, theta, speed, dx)
    a2, b2, m2 = theta_rhs(radius, theta + dt * a1 / 2.0, speed + dt * b1 / 2.0, dx)
    a3, b3, m3 = theta_rhs(radius, theta + dt * a2 / 2.0, speed + dt * b2 / 2.0, dx)
    a4, b4, m4 = theta_rhs(radius, theta + dt * a3, speed + dt * b3, dx)
    theta_next = theta + dt * (a1 + 2.0 * a2 + 2.0 * a3 + a4) / 6.0
    speed_next = speed + dt * (b1 + 2.0 * b2 + 2.0 * b3 + b4) / 6.0
    theta_next[0], theta_next[-1] = 0.0, math.pi
    speed_next[0], speed_next[-1] = 0.0, 0.0
    return theta_next, speed_next, min(m1, m2, m3, m4)


def static_on_grid(radius: np.ndarray, spline: CubicHermiteSpline, static: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    f = np.asarray(spline(np.maximum(radius, EPS)), dtype=np.float64)
    fp = np.asarray(spline(np.maximum(radius, EPS), 1), dtype=np.float64)
    f[0] = math.pi
    fp[0] = float(static["origin_slope"])
    f[-1] = 0.0
    return f, fp


def independent_formation(spline: CubicHermiteSpline, static: dict[str, float]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    dx, dt, final_time = 0.03, 0.006, 30.0
    radius = np.arange(0.0, BOUND + dx / 2.0, dx)
    f_initial = np.empty_like(radius)
    f_initial[0] = math.pi
    f_initial[1:] = 2.0 * np.arctan((1.60 / radius[1:]) ** 3)
    f_initial[-1] = 0.0
    theta = math.pi - f_initial
    speed = np.zeros_like(theta)
    f_static, fp_static = static_on_grid(radius, spline, static)
    theta_static = math.pi - f_static
    inner = radius <= 8.0 + 1.0e-12
    outer = radius >= 8.0 - 1.0e-12
    static_inner = energy(radius, theta_static, np.zeros_like(radius), dx, inner)
    final_step = int(round(final_time / dt))

    sample_times = np.linspace(0.0, final_time, 301, dtype=np.float64)
    sample_brackets: list[tuple[int, int, float]] = []
    diagnostic_steps: set[int] = set()
    for sample_time in sample_times:
        position = float(sample_time / dt)
        lower = int(math.floor(position + 1.0e-12))
        upper = min(lower + 1, final_step)
        weight = position - lower
        if abs(weight) <= 1.0e-10:
            upper = lower
            weight = 0.0
        sample_brackets.append((lower, upper, weight))
        diagnostic_steps.update((lower, upper))

    requested_snapshots = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0)
    snapshot_brackets: list[tuple[float, int, int, float]] = []
    snapshot_steps: set[int] = set()
    for snapshot_time in requested_snapshots:
        position = float(snapshot_time / dt)
        lower = int(math.floor(position + 1.0e-12))
        upper = min(lower + 1, final_step)
        weight = position - lower
        if abs(weight) <= 1.0e-10:
            upper = lower
            weight = 0.0
        snapshot_brackets.append((snapshot_time, lower, upper, weight))
        snapshot_steps.update((lower, upper))

    raw_rows: dict[int, dict[str, float]] = {}
    state_rows: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    minimum_inertia = math.inf

    def measure(time: float) -> dict[str, float]:
        f_now = math.pi - theta
        fp_now = -derivative(theta, dx)
        numerator = float(
            simpson(
                radius[inner] ** 2 * (fp_now[inner] - fp_static[inner]) ** 2
                + 2.0 * (f_now[inner] - f_static[inner]) ** 2,
                x=radius[inner],
            )
        )
        denominator = float(
            simpson(
                radius[inner] ** 2 * fp_static[inner] ** 2 + 2.0 * f_static[inner] ** 2,
                x=radius[inner],
            )
        )
        return {
            "time": time,
            "total_energy": energy(radius, theta, speed, dx),
            "inner_energy": energy(radius, theta, speed, dx, inner),
            "outer_energy": energy(radius, theta, speed, dx, outer),
            "degree": degree(radius, theta, dx),
            "degree_derivative_simpson": derivative_simpson_degree(radius, theta, dx),
            "half_angle_radius": crossing(radius, theta),
            "core_max_abs_velocity": float(np.max(np.abs(speed[inner]))),
            "profile_mismatch": math.sqrt(numerator / denominator),
        }

    for step in range(final_step + 1):
        if step in diagnostic_steps:
            raw_rows[step] = measure(step * dt)
        if step in snapshot_steps:
            state_rows[step] = (theta.copy(), speed.copy())
        if step == final_step:
            break
        theta, speed, local_min = theta_step(radius, theta, speed, dx, dt)
        minimum_inertia = min(minimum_inertia, local_min)
        if not np.all(np.isfinite(theta)) or not np.all(np.isfinite(speed)):
            raise VerificationError(f"nonfinite independent evolution at step {step + 1}")

    series: dict[str, np.ndarray] = {"time": sample_times}
    scalar_keys = [key for key in raw_rows[0] if key != "time"]
    for key in scalar_keys:
        series[key] = np.asarray(
            [
                (1.0 - weight) * raw_rows[lower][key] + weight * raw_rows[upper][key]
                for lower, upper, weight in sample_brackets
            ],
            dtype=np.float64,
        )

    snap_theta: list[np.ndarray] = []
    snap_speed: list[np.ndarray] = []
    for _, lower, upper, weight in snapshot_brackets:
        lower_theta, lower_speed = state_rows[lower]
        upper_theta, upper_speed = state_rows[upper]
        snap_theta.append((1.0 - weight) * lower_theta + weight * upper_theta)
        snap_speed.append((1.0 - weight) * lower_speed + weight * upper_speed)

    late = series["time"] >= 25.0 - 1.0e-12
    total0 = float(series["total_energy"][0])
    inner0 = float(series["inner_energy"][0])
    outer0 = float(series["outer_energy"][0])
    late_inner = float(np.mean(series["inner_energy"][late]))
    late_outer = float(np.mean(series["outer_energy"][late]))
    excess0 = inner0 - static_inner
    excess_late = late_inner - static_inner
    drop = inner0 - late_inner
    gain = late_outer - outer0
    static_half = float(static["half_angle_radius"])
    half0 = float(series["half_angle_radius"][0])
    late_half = float(np.mean(series["half_angle_radius"][late]))
    mismatch0 = float(series["profile_mismatch"][0])
    late_mismatch = float(np.mean(series["profile_mismatch"][late]))
    drift = float(np.max(np.abs(series["total_energy"] - total0)) / total0)
    degree_error = float(np.max(np.abs(series["degree"] - 1.0)))
    simpson_degree_error = float(np.max(np.abs(series["degree_derivative_simpson"] - 1.0)))
    gates = {
        "cfl_and_finite": bool(math.isclose(dt / dx, 0.2, abs_tol=1.0e-14) and minimum_inertia > 0.0),
        "energy_conservation": drift <= 0.005,
        "degree_conservation": bool(
            degree_error <= 2.0e-12
            and all(np.all(np.isfinite(derivative(math.pi - profile, dx))) for profile in snap_theta)
        ),
        "nonstationary_initial_state": bool(half0 >= 1.5 * static_half and mismatch0 > 0.20),
        "late_static_approach": bool(abs(late_half - static_half) / static_half <= 0.10 and late_mismatch < 0.15),
        "outgoing_energy_ledger": bool(
            excess0 > 0.0
            and excess_late <= 0.35 * excess0
            and gain >= 0.0
            and gain + 0.03 * total0 >= drop
        ),
    }
    summary = {
        "grid": {
            "L": BOUND,
            "h": dx,
            "dt": dt,
            "cfl": dt / dx,
            "steps": final_step,
            "scalar_samples": len(sample_times),
            "scalar_sampling": "linear diagnostic interpolation to exact 0.1-time coordinates",
        },
        "static_inner_energy": static_inner,
        "minimum_interior_inertia": minimum_inertia,
        "max_total_energy_relative_drift": drift,
        "max_degree_error": degree_error,
        "max_derivative_simpson_degree_error": simpson_degree_error,
        "initial_half_angle_radius": half0,
        "static_half_angle_radius": static_half,
        "late_mean_half_angle_radius": late_half,
        "initial_profile_mismatch": mismatch0,
        "late_mean_profile_mismatch": late_mismatch,
        "initial_inner_excess_energy": excess0,
        "late_mean_inner_excess_energy": excess_late,
        "late_to_initial_inner_excess_ratio": excess_late / excess0,
        "inner_energy_drop": drop,
        "outer_energy_gain": gain,
        "ledger_residual_fraction": abs(gain - drop) / total0,
        "late_mean_core_max_abs_velocity": float(np.mean(series["core_max_abs_velocity"][late])),
        "gates": gates,
        "pass": bool(all(gates.values())),
    }
    arrays: dict[str, np.ndarray] = {
        "x": radius,
        "static_f": f_static,
        "static_fp": fp_static,
        "snapshot_times": np.asarray(requested_snapshots, dtype=np.float64),
        "snapshot_theta": np.vstack(snap_theta),
        "snapshot_theta_t": np.vstack(snap_speed),
    }
    arrays.update({f"series_{key}": value for key, value in series.items()})
    return summary, arrays


def comparison(name: str, primary: float, independent: float, relative_tolerance: float, absolute_tolerance: float = 0.0) -> dict[str, Any]:
    difference = abs(primary - independent)
    scale = max(abs(primary), abs(independent), 1.0e-300)
    allowed = max(absolute_tolerance, relative_tolerance * scale)
    return {
        "name": name,
        "primary": primary,
        "independent": independent,
        "absolute_difference": difference,
        "allowed_difference": allowed,
        "pass": difference <= allowed,
    }


def has_keys(obj: dict[str, Any], expected: set[str], label: str) -> dict[str, Any]:
    actual = set(obj)
    return {
        "name": f"{label}_key_set",
        "pass": actual == expected,
        "missing": sorted(expected - actual),
        "extra": sorted(actual - expected),
    }


def validate_primary(primary_dir: Path, prereg: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, np.ndarray]]:
    result_path = primary_dir / "results.json"
    if not result_path.is_file():
        raise VerificationError(f"missing primary receipt: {result_path}")
    primary = json.loads(result_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    finite_errors = finite_tree(primary)
    checks.append({"name": "primary_json_finite", "pass": not finite_errors, "errors": finite_errors})
    checks.append(
        has_keys(
            primary,
            {
                "schema",
                "identities",
                "protocol_artifact",
                "exact_controls",
                "static_solver",
                "static",
                "calibration",
                "particle_map",
                "empirical_discriminators",
                "radial_relaxation",
                "artifacts",
                "qualified",
                "verdicts",
                "scientific_verdict",
                "limitations",
            },
            "primary_top_level",
        )
    )
    checks.append({"name": "primary_schema_exact", "pass": primary.get("schema") == "matter-formation-conditional-baryon-v2"})

    expected_identities = {
        "preregistration": prereg,
        "primary_source": PRIMARY_SOURCE,
        "verifier_source": Path(__file__).resolve(),
    }
    checks.append(
        has_keys(
            primary.get("identities", {}),
            set(expected_identities),
            "identity",
        )
    )
    for name, path in expected_identities.items():
        row = primary.get("identities", {}).get(name, {})
        expected_hash = canonical_text_digest(path)
        checks.append(
            {
                "name": f"identity_{name}",
                "pass": bool(
                    set(row) == {"path", "canonical_text_sha256"}
                    and row.get("path") == relative(path)
                    and row.get("canonical_text_sha256") == expected_hash
                ),
                "recorded": row,
                "expected_path": relative(path),
                "expected_canonical_text_sha256": expected_hash,
            }
        )

    protocol = primary_dir / "frozen_protocol.txt"
    protocol_row = primary.get("protocol_artifact", {})
    checks.append(
        {
            "name": "frozen_protocol_exact",
            "pass": bool(
                protocol.is_file()
                and normalized(protocol.read_bytes()) == normalized(prereg.read_bytes())
                and set(protocol_row) == {"path", "sha256", "bytes"}
                and protocol_row.get("path") == "frozen_protocol.txt"
                and protocol_row.get("sha256") == raw_digest(protocol)
                and protocol_row.get("bytes") == protocol.stat().st_size
            ),
            "recorded": protocol_row,
        }
    )

    expected_artifacts = {
        "static_profile": "static_profile.npz",
        "relaxation_arrays": "relaxation_arrays.npz",
        "source_record": "source_record.md",
    }
    checks.append(has_keys(primary.get("artifacts", {}), set(expected_artifacts), "artifact"))
    arrays: dict[str, np.ndarray] = {}
    for label, filename in expected_artifacts.items():
        path = primary_dir / filename
        recorded = primary.get("artifacts", {}).get(label, {})
        okay = bool(
            path.is_file()
            and set(recorded) == {"path", "sha256", "bytes"}
            and recorded.get("path") == filename
            and recorded.get("sha256") == raw_digest(path)
            and recorded.get("bytes") == path.stat().st_size
        )
        checks.append({"name": f"artifact_{label}_identity", "pass": okay, "recorded": recorded})
        if path.suffix == ".npz" and path.is_file():
            with np.load(path, allow_pickle=False) as archive:
                for key in archive.files:
                    arrays[f"{label}.{key}"] = np.asarray(archive[key])

    expected_static_arrays = {"static_profile.x", "static_profile.f", "static_profile.fp"}
    expected_relaxation_arrays = {
        "relaxation_arrays.x",
        "relaxation_arrays.static_f",
        "relaxation_arrays.static_fp",
        "relaxation_arrays.snapshot_times",
        "relaxation_arrays.snapshot_f",
        "relaxation_arrays.snapshot_v",
        "relaxation_arrays.series_time",
        "relaxation_arrays.series_total_energy",
        "relaxation_arrays.series_inner_energy",
        "relaxation_arrays.series_outer_energy",
        "relaxation_arrays.series_degree",
        "relaxation_arrays.series_degree_derivative_simpson",
        "relaxation_arrays.series_half_angle_radius",
        "relaxation_arrays.series_core_max_abs_velocity",
        "relaxation_arrays.series_profile_mismatch",
    }
    expected_array_keys = expected_static_arrays | expected_relaxation_arrays
    checks.append(
        {
            "name": "primary_array_key_set",
            "pass": set(arrays) == expected_array_keys,
            "missing": sorted(expected_array_keys - set(arrays)),
            "extra": sorted(set(arrays) - expected_array_keys),
        }
    )
    snapshot_f = arrays.get("relaxation_arrays.snapshot_f", np.empty((0, 0)))
    snapshot_v = arrays.get("relaxation_arrays.snapshot_v", np.empty((1, 1)))
    series_time = arrays.get("relaxation_arrays.series_time", np.empty(0))
    snapshot_times = arrays.get("relaxation_arrays.snapshot_times", np.empty(0))
    shape_pass = bool(
        arrays.get("static_profile.x", np.empty(0)).shape
        == arrays.get("static_profile.f", np.empty(1)).shape
        == arrays.get("static_profile.fp", np.empty(2)).shape
        and snapshot_f.shape == snapshot_v.shape
        and snapshot_f.ndim == 2
        and snapshot_f.shape[0] == snapshot_times.size == 7
        and snapshot_f.shape[1] == arrays.get("relaxation_arrays.x", np.empty(0)).size
        and series_time.shape == (301,)
        and all(
            arrays.get(key, np.empty(0)).shape == (301,)
            for key in expected_relaxation_arrays
            if key.startswith("relaxation_arrays.series_")
        )
    )
    checks.append({"name": "primary_array_shapes", "pass": shape_pass})
    checks.append({"name": "primary_array_finite", "pass": bool(arrays and all(np.all(np.isfinite(value)) for value in arrays.values()))})
    checks.append(
        {
            "name": "primary_exact_sample_coordinates",
            "pass": bool(
                np.array_equal(series_time, np.linspace(0.0, 30.0, 301, dtype=np.float64))
                and np.array_equal(snapshot_times, np.asarray((0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0)))
            ),
        }
    )
    checks.append(
        {
            "name": "primary_boundary_values_exact",
            "pass": bool(
                snapshot_f.size
                and np.all(snapshot_f[:, 0] == math.pi)
                and np.all(snapshot_f[:, -1] == 0.0)
                and np.all(snapshot_v[:, 0] == 0.0)
                and np.all(snapshot_v[:, -1] == 0.0)
            ),
        }
    )

    expected_control_names = {
        "radial_euler_lagrange",
        "pion_field_normalization",
        "normalized_doublet_su2_lift",
        "supplied_fr_state_assignments",
        "two_flavour_charge_map",
    }
    controls = primary.get("exact_controls", [])
    checks.append(
        {
            "name": "primary_exact_control_set",
            "pass": bool(
                isinstance(controls, list)
                and {row.get("name") for row in controls if isinstance(row, dict)} == expected_control_names
                and all(set(row) == {"name", "pass", "evidence"} and row.get("pass") is True for row in controls)
            ),
        }
    )
    checks.append(
        {
            "name": "primary_static_solver_pass",
            "pass": bool(
                primary.get("static_solver", {}).get("status") == 0
                and primary.get("static_solver", {}).get("max_rms_residual", math.inf) <= 1.0e-7
            ),
        }
    )
    checks.append(
        {
            "name": "primary_qualification_consistent",
            "pass": bool(
                primary.get("qualified") is True
                and primary.get("verdicts", {}).get("conditional_baryon_benchmark")
                == primary.get("scientific_verdict")
            ),
        }
    )
    return primary, checks, arrays


def artifact(path: Path) -> dict[str, Any]:
    return {"path": path.name, "sha256": raw_digest(path), "bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--primary-dir", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    prereg = args.prereg.resolve()
    primary_dir = args.primary_dir.resolve()
    output = args.output_dir.resolve()

    try:
        make_output(output)
        required = [prereg, PRIMARY_SOURCE, Path(__file__).resolve()]
        absent = [relative(path) for path in required if not path.is_file()]
        if absent:
            raise VerificationError("missing verifier source input(s): " + ", ".join(absent))

        primary, checks, primary_arrays = validate_primary(primary_dir, prereg)
        protocol_path = output / "frozen_protocol.txt"
        protocol_path.write_bytes(normalized(prereg.read_bytes()))

        independent_controls, particle_expected = independent_model_controls()
        solver, nodes, f, fp, spline = independent_static()
        static = independent_integrals(f, fp, spline)
        calibration = independent_calibration(static)
        empirical = independent_observables(static, calibration)
        relaxation, relaxation_arrays = independent_formation(spline, static)

        profile_path = output / "independent_static_profile.npz"
        sample_x = np.linspace(0.0, BOUND, 6401)
        sample_f, sample_fp = static_on_grid(sample_x, spline, static)
        with profile_path.open("xb") as stream:
            np.savez(stream, x=sample_x, f=sample_f, fp=sample_fp, solver_x=nodes, solver_f=f, solver_fp=fp)
        dynamics_path = output / "independent_relaxation_arrays.npz"
        with dynamics_path.open("xb") as stream:
            np.savez(stream, **relaxation_arrays)

        for name in (
            "E2",
            "E4",
            "energy",
            "s",
            "degree",
            "Lambda",
            "R0_squared",
            "RM0_squared",
            "G",
            "half_angle_radius",
            "derrick_relative",
        ):
            checks.append(comparison(f"static_{name}", float(primary["static"][name]), float(static[name]), 3.0e-5, 1.0e-12))
        for name in (
            "e_B",
            "f_B_MeV",
            "I0_MeV_inverse",
            "length_unit_fm",
            "M_classical_MeV",
            "M_N_reconstructed_MeV",
            "M_Delta_reconstructed_MeV",
        ):
            checks.append(comparison(f"calibration_{name}", float(primary["calibration"][name]), float(calibration[name]), 8.0e-5))
        for name in TARGETS:
            checks.append(
                comparison(
                    f"empirical_{name}",
                    float(primary["empirical_discriminators"][name]["value"]),
                    float(empirical[name]["value"]),
                    8.0e-5,
                )
            )
            checks.append(
                {
                    "name": f"empirical_verdict_{name}",
                    "pass": primary["empirical_discriminators"][name]["verdict"] == empirical[name]["verdict"],
                    "primary": primary["empirical_discriminators"][name]["verdict"],
                    "independent": empirical[name]["verdict"],
                }
            )
        checks.append(
            comparison(
                "empirical_isoscalar_magnetic_radius",
                float(primary["empirical_discriminators"]["isoscalar_magnetic_radius_fm"]["value"]),
                float(empirical["isoscalar_magnetic_radius_fm"]["value"]),
                8.0e-5,
            )
        )

        primary_relaxation = primary["radial_relaxation"]
        for name in (
            "late_mean_half_angle_radius",
            "late_mean_profile_mismatch",
            "late_to_initial_inner_excess_ratio",
            "inner_energy_drop",
            "outer_energy_gain",
        ):
            checks.append(
                comparison(
                    f"relaxation_{name}",
                    float(primary_relaxation[name]),
                    float(relaxation[name]),
                    0.05,
                )
            )
        checks.append(
            comparison(
                "relaxation_late_mean_core_max_abs_velocity",
                float(primary_relaxation["late_mean_core_max_abs_velocity"]),
                float(relaxation["late_mean_core_max_abs_velocity"]),
                0.0,
                5.0e-4,
            )
        )
        checks.append(
            {
                "name": "relaxation_gate_key_set",
                "pass": set(primary_relaxation["gates"]) == set(relaxation["gates"]),
                "primary": sorted(primary_relaxation["gates"]),
                "independent": sorted(relaxation["gates"]),
            }
        )
        for name, independent_pass in relaxation["gates"].items():
            primary_pass = primary_relaxation["gates"].get(name)
            checks.append(
                {
                    "name": f"relaxation_gate_{name}",
                    "pass": bool(primary_pass is True and independent_pass is True),
                    "primary": primary_pass,
                    "independent": independent_pass,
                }
            )

        primary_controls = {row["name"]: row for row in primary["exact_controls"]}
        independent_control_pass = bool(all(row["pass"] is True for row in independent_controls))
        checks.append({"name": "independent_exact_controls", "pass": independent_control_pass, "controls": independent_controls})
        for row in independent_controls:
            primary_row = primary_controls.get(row["name"], {})
            checks.append(
                {
                    "name": f"control_{row['name']}_agreement",
                    "pass": bool(primary_row.get("pass") is True and row["pass"] is True),
                    "primary": primary_row,
                    "independent": row,
                }
            )
        checks.append({"name": "particle_map_exact", "pass": primary.get("particle_map") == particle_expected})
        checks.append({"name": "calibration_label_exact", "pass": primary["calibration"].get("label") == calibration["label"]})

        independent_static_pass = bool(
            abs(static["degree"] - 1.0) <= 2.0e-8
            and static["finite_domain_virial_relative"] <= 1.0e-6
            and abs(static["outer_boundary_value"]) <= 1.0e-12
        )
        independent_particle_pass = primary.get("particle_map") == particle_expected
        independent_mass_pass = bool(
            calibration["positive_coefficients"]
            and abs((calibration["M_N_reconstructed_MeV"] - MN) / MN) <= 1.0e-10
            and abs((calibration["M_Delta_reconstructed_MeV"] - MDELTA) / MDELTA) <= 1.0e-10
        )
        checks.append({"name": "independent_static_gate", "pass": independent_static_pass})
        checks.append({"name": "independent_mass_reconstruction", "pass": independent_mass_pass})
        if (
            independent_control_pass
            and independent_static_pass
            and independent_particle_pass
            and independent_mass_pass
            and relaxation["pass"]
        ):
            independent_overall = "ADOPT—Mapped conditional leading colour-neutral chiral baryon benchmark"
        else:
            independent_overall = "REJECT—conditional benchmark fails a frozen structural discriminator"
        checks.append(
            {
                "name": "overall_verdict_exact",
                "pass": primary.get("scientific_verdict") == independent_overall,
                "primary": primary.get("scientific_verdict"),
                "independent": independent_overall,
            }
        )
        checks.append(
            {
                "name": "verdict_dictionary_exact",
                "pass": primary.get("verdicts", {}).get("conditional_baryon_benchmark") == independent_overall,
            }
        )
        checks.append(
            {
                "name": "declared_scope_preserved",
                "pass": bool(
                    primary.get("limitations")
                    == [
                        "added effective field and action rather than a canonical Cassi derivation",
                        "two measured masses fix the two action coefficients",
                        "FR character and charge rule are supplied analytic model inputs",
                        "no quantum vacuum, density operator, regulator, or renormalization",
                        "no canonical Cassi coupling, stress exchange, or general interaction normalization",
                        "no infinite-domain, nonradial, or degree-zero creation result",
                        "no QCD, colour-confinement, baryogenesis, nuclear-binding, or chemistry derivation",
                        "one or more absolute out-of-fit nucleon observables miss the precision threshold",
                    ]
                    and primary.get("verdicts", {}).get("precision_nucleon_observables")
                    == "CONTRADICTS—one or more absolute out-of-fit observables miss 10 percent"
                ),
            }
        )

        check_names = [row["name"] for row in checks]
        checks.append(
            {
                "name": "unique_check_names",
                "pass": len(check_names) == len(set(check_names)),
                "duplicates": sorted({name for name in check_names if check_names.count(name) > 1}),
            }
        )
        qualified = bool(all(row.get("pass") is True for row in checks))
        payload = {
            "schema": SCHEMA,
            "identities": {
                "preregistration": {
                    "path": relative(prereg),
                    "canonical_text_sha256": canonical_text_digest(prereg),
                },
                "primary_source": {
                    "path": relative(PRIMARY_SOURCE),
                    "canonical_text_sha256": canonical_text_digest(PRIMARY_SOURCE),
                },
                "verifier_source": {
                    "path": relative(Path(__file__).resolve()),
                    "canonical_text_sha256": canonical_text_digest(Path(__file__).resolve()),
                },
                "primary_receipt": {
                    "path": relative(primary_dir / "results.json"),
                    "sha256": raw_digest(primary_dir / "results.json"),
                },
            },
            "protocol_artifact": artifact(protocol_path),
            "independent_exact_controls": independent_controls,
            "independent_static_solver": solver,
            "independent_static": static,
            "independent_calibration": calibration,
            "independent_particle_map": particle_expected,
            "independent_empirical_discriminators": empirical,
            "independent_radial_relaxation": relaxation,
            "checks": checks,
            "failed_checks": [row["name"] for row in checks if row.get("pass") is not True],
            "artifacts": {
                "independent_static_profile": artifact(profile_path),
                "independent_relaxation_arrays": artifact(dynamics_path),
            },
            "qualified": qualified,
            "scientific_verdict": independent_overall if qualified else "INCONCLUSIVE",
            "reproduced_primary_verdict": independent_overall,
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
                "sympy": sp.__version__,
            },
        }
        save_json(output / "verification.json", payload)
        print(
            json.dumps(
                {
                    "qualified": qualified,
                    "failed_checks": payload["failed_checks"],
                    "reproduced_primary_verdict": independent_overall,
                    "radial_relaxation_pass": relaxation["pass"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if qualified else 1
    except Exception as exc:
        fail(output, primary_dir, prereg, type(exc).__name__, str(exc))
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if not isinstance(exc, VerificationError):
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
