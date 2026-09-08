#!/usr/bin/env python3
"""Conditional SU(2)-chiral structure and massive radial calibration.

This program is deliberately separate from the registered Cassi matter fields.  It
records the continuum action identities, the primitive even-parity lattice
geometry, the finite-site topology/regulator boundary, and an independent
massive hedgehog calculation at the frozen pion parameter.  Nothing here is a
canonical matter-formation derivation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any, Callable
import numpy as np
import sympy as sp
from scipy.integrate import quad, solve_bvp
from scipy.interpolate import CubicHermiteSpline
from scipy.optimize import brentq

SCHEMA = "matter-formation-chiral-lattice-structure-v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
P_PRIMITIVE = 2.0
MU = 0.5266577616452649
KAPPA = 1.0
L_RADIAL = 64.0
EPS_RADIAL = 1.0e-5
HBARC = 197.3269804
MN_TARGET = 938.918754
MDELTA_TARGET = 1232.0
MPI_TARGET = 138.039
ROOT = Path(__file__).resolve().parents[1]
CONDITIONAL_SCRIPT = ROOT / "computations" / "matter_formation_conditional_baryon.py"
CONDITIONAL_PREREG = ROOT / "computations" / "matter-formation-conditional-baryon-prereg.md"


class NumericalFailure(RuntimeError):
    """A numerical or evidence-contract failure."""
def protocol_sha256() -> str:
    report = Path(__file__).resolve().with_name("matter-formation-continuum-report.md")
    text = report.read_text(encoding="utf-8")
    data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    start_marker = b"<!-- chiral-lattice-protocol:start -->"
    end_marker = b"<!-- chiral-lattice-protocol:end -->"
    start = data.find(start_marker)
    end = data.find(end_marker)
    if start < 0 or end < 0 or end <= start + len(start_marker):
        raise NumericalFailure("chiral lattice protocol markers missing or out of order")
    inner = data[start + len(start_marker) : end]
    return hashlib.sha256(inner).hexdigest()



def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()
def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (float, int, str, bool)) or value is None:
        return value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def finite_tree(value: Any, label: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            errors.extend(finite_tree(child, f"{label}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            errors.extend(finite_tree(child, f"{label}[{index}]"))
    elif isinstance(value, np.ndarray):
        if not np.all(np.isfinite(value)):
            errors.append(label)
    elif isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        errors.append(label)
    return errors


def exact_action_controls() -> dict[str, Any]:
    """Differentiate the action, then check a rational tangent-space witness."""
    eta = sp.diag(1, -1, -1, -1)
    kappa, mu2, n0 = sp.symbols("kappa mu2 n0", real=True)
    d = [[sp.symbols(f"d{m}{a}", real=True) for a in range(4)] for m in range(4)]

    def dot(mu: int, nu: int) -> sp.Expr:
        return sum(d[mu][a] * d[nu][a] for a in range(4))

    x = sp.expand(sum(eta[m, m] * dot(m, m) for m in range(4)))
    y = sp.expand(
        sum(eta[m, m] * eta[n, n] * dot(m, n) ** 2 for m in range(4) for n in range(4))
    )
    lagrangian = sp.Rational(1, 2) * x - kappa * sp.Rational(1, 4) * (x**2 - y) - mu2 * (1 - n0)
    pi: list[list[sp.Expr]] = []
    pi_expected: list[list[sp.Expr]] = []
    for m in range(4):
        row: list[sp.Expr] = []
        expected_row: list[sp.Expr] = []
        for a in range(4):
            row.append(sp.diff(lagrangian, d[m][a]))
            expected_row.append(
                eta[m, m] * d[m][a] * (1 - kappa * x)
                + kappa
                * sum(
                    eta[m, m] * eta[q, q] * dot(m, q) * d[q][a] for q in range(4)
                )
            )
        pi.append(row)
        pi_expected.append(expected_row)
    pi_residual = max(abs(sp.simplify(pi[m][a] - pi_expected[m][a])) for m in range(4) for a in range(4))

    stress: list[list[sp.Expr]] = []
    stress_antisym: list[sp.Expr] = []
    for m in range(4):
        row = []
        for nu in range(4):
            row.append(
                sp.expand(
                    sum(pi[m][a] * eta[nu, nu] * d[nu][a] for a in range(4))
                    - eta[m, nu] * lagrangian
                )
            )
        stress.append(row)
    for m in range(4):
        for nu in range(4):
            stress_antisym.append(sp.simplify(stress[m][nu] - stress[nu][m]))

    # Exact rational tangent-space witness for the Legendre/Hamiltonian split.
    n = sp.Matrix([1, 0, 0, 0])
    velocity = sp.Matrix([0, 2, -1, 1])
    gradients = [sp.Matrix([0, 1, 2, 0]), sp.Matrix([0, 0, 1, 1]), sp.Matrix([0, 1, -1, 2])]
    s = sum(q.dot(q) for q in gradients)
    matrix = (1 + 2 * s) * sp.eye(4)
    for q in gradients:
        matrix -= 2 * q * q.T
    momentum = matrix * velocity
    kinetic = sp.Rational(1, 2) * velocity.dot(momentum)
    v2 = sp.Rational(1, 2) * s
    v4 = sp.Rational(1, 2) * 2 * sum(
        gradients[a].dot(gradients[a]) * gradients[b].dot(gradients[b])
        - gradients[a].dot(gradients[b]) ** 2
        for a in range(3) for b in range(a + 1, 3)
    )
    # Minkowski action evaluated on (velocity, spatial gradients), with n0=1.
    xw = velocity.dot(velocity) - s
    yw = velocity.dot(velocity) ** 2 - 2 * sum(
        (velocity.dot(q)) ** 2 for q in gradients
    ) + sum(
        gradients[a].dot(gradients[b]) ** 2 for a in range(3) for b in range(3)
    )
    lw = sp.Rational(1, 2) * xw - sp.Rational(2, 4) * (xw**2 - yw)
    h_legendre = sp.expand(momentum.dot(velocity) - lw)
    h_split = sp.expand(kinetic + v2 + v4)
    inverse_residual = sp.simplify(matrix.inv() * momentum - velocity)
    return {
        "action": "L = 1/2 X - kappa/4 (X^2-Y) - mu^2(1-n0), eta=diag(+1,-1,-1,-1)",
        "X_definition": "X = partial_mu n dot partial^mu n",
        "Y_definition": "Y = (partial_mu n dot partial_nu n)(partial^mu n dot partial^nu n)",
        "Pi_formula": "Pi^mu_A = (1-kappa X) partial^mu n_A + kappa partial_nu n_A (partial^mu n dot partial^nu n)",
        "stress_formula": "T^{mu nu} = Pi^mu dot partial^nu n - eta^{mu nu} L (symmetric)",
        "isospin_current_formula": "j^mu = n_vec cross Pi_vec^mu",
        "pi_symbolic_max_residual": str(pi_residual),
        "stress_antisymmetry_residuals": [str(v) for v in stress_antisym],
        "projected_lattice_equations": "n'=v; p'=-P grad_density(H)-n(p dot v), with P=I-n n^T and periodic signed unit-index differences",
        "hamiltonian_decomposition": {
            "M_definition": "M=(1+kappa*S)I-kappa sum_a d_a d_a^T; p=M v",
            "S_definition": "S=sum_a |d_a|^2; d_a=partial_a n-n(n dot partial_a n)",
            "H_definition": "H_density=.5 p dot M^{-1}p + .5 S + .5 kappa sum_{a<b} (|d_a|^2|d_b|^2-(d_a dot d_b)^2) + mu^2(1-n0)",
            "witness_kappa": 2,
            "witness_legendre_minus_split": str(h_legendre - h_split),
            "witness_inverse_M_p_minus_v": [str(v) for v in inverse_residual],
            "witness_pass": bool(h_legendre == h_split and all(v == 0 for v in inverse_residual)),
        },
        "massive_vacuum": "n=e0; quadratic fluctuations in each of the three n_vec directions have mass mu",
    }


def primitive_geometry() -> dict[str, Any]:
    """Return columns, even-parity primitive basis, and the unweighted dyad."""
    phi = PHI
    p = P_PRIMITIVE
    a0 = np.array(
        [[0.5, 0.5, 0.0], [0.5 / phi, 0.0, 0.5 / phi], [0.0, 1.0, 1.0]],
        dtype=np.float64,
    )
    col_norms = np.linalg.norm(a0, axis=0)
    unit_links = a0 / col_norms[np.newaxis, :]
    dyad = 2.0 * unit_links @ unit_links.T
    eigvals = np.linalg.eigvalsh(dyad)
    metric = a0.T @ a0
    # The supplied A0 columns already are the even-parity primitive basis;
    # no additional parity transform is applied.
    even_integer = np.eye(3, dtype=np.int64)
    even_basis = a0.copy()
    exact_det = sp.simplify(
        sp.det(
            sp.Matrix(
                [
                    [sp.Rational(1, 2), sp.Rational(1, 2), 0],
                    [1 / (1 + sp.sqrt(5)), 0, 1 / (1 + sp.sqrt(5))],
                    [0, 1, 1],
                ]
            )
        )
    )
    det_a0 = float(np.linalg.det(a0))
    return {
        "phi": phi,
        "p": p,
        "A0_columns": a0,
        "column_norms": col_norms,
        "A_definition": "A=(L/N) A0; columns are the three primitive physical links",
        "physical_gradient": "G_a=sum_i (A^{-1})_{ia} Delta_i",
        "metric_A0": metric,
        "metric_convention": "g=A^T A on primitive coordinate components; physical Jacobian is |det A|",
        "A0_det_symbolic": str(exact_det),
        "A0_det_numeric": det_a0,
        "A_det": "det(A)=(L/N)^3 det(A0), so |det(A)|=(L/N)^3 p/(4 phi)",
        "even_parity_site_set": "sites indexed by Z^3 in the supplied even-parity primitive basis; no additional parity restriction or basis transform",
        "even_parity_integer_basis_columns": even_integer,
        "even_parity_physical_basis_columns": even_basis,
        "even_basis_det_over_A_det": int(round(abs(np.linalg.det(even_integer)))),
        "six_unit_link_dyad": dyad,
        "six_unit_link_dyad_eigenvalues": eigvals,
        "six_unit_link_dyad_isotropic": bool(np.max(eigvals) - np.min(eigvals) <= 1.0e-12),
        "anisotropy_statement": "For phi and p=2 the equal-weight normalized six-link dyad is anisotropic; summing equal-length-normalized links alone does not reproduce an isotropic gradient.",
    }


def massive_acceleration(radius: np.ndarray, field: np.ndarray, slope: np.ndarray) -> np.ndarray:
    sine = np.sin(field)
    denominator = radius * radius + 2.0 * sine * sine
    numerator = (
        -2.0 * radius * slope
        - np.sin(2.0 * field) * (slope * slope - 1.0 - sine * sine / (radius * radius))
        + MU * MU * radius * radius * sine
    )
    return numerator / denominator


def solve_massive_profile() -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, CubicHermiteSpline]:
    radius = np.geomspace(EPS_RADIAL, L_RADIAL, 1001)
    width = 1.0 / math.sqrt(2.0)
    theta0 = 2.0 * np.arctan(radius / width)
    theta_slope0 = 2.0 * width / (radius * radius + width * width)
    # theta=pi-F keeps the small regular-origin variable accurate.
    def fun(r: np.ndarray, y: np.ndarray) -> np.ndarray:
        theta, theta_p = y
        sine = np.sin(theta)
        theta_pp = (
            -2.0 * r * theta_p
            - np.sin(2.0 * theta) * (theta_p * theta_p - 1.0 - sine * sine / (r * r))
            - MU * MU * r * r * sine
        ) / (r * r + 2.0 * sine * sine)
        return np.vstack((theta_p, theta_pp))

    def bc(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.array([left[0] - EPS_RADIAL * left[1], right[0] - math.pi])

    solution = solve_bvp(fun, bc, radius, np.vstack((theta0, theta_slope0)), tol=1.0e-8, max_nodes=100000, verbose=0)
    if solution.status != 0:
        raise NumericalFailure(f"massive solve_bvp failed: status={solution.status}, message={solution.message}")
    nodes = np.asarray(solution.x, dtype=np.float64)
    field = math.pi - np.asarray(solution.y[0], dtype=np.float64)
    slope = -np.asarray(solution.y[1], dtype=np.float64)
    residuals = np.asarray(solution.rms_residuals, dtype=np.float64)
    if not all(np.all(np.isfinite(v)) for v in (nodes, field, slope, residuals)):
        raise NumericalFailure("massive profile contains nonfinite values")
    spline = CubicHermiteSpline(nodes, field, slope)
    return (
        {
            "status": int(solution.status),
            "message": str(solution.message),
            "nodes": int(nodes.size),
            "max_rms_residual": float(np.max(residuals)),
            "epsilon": EPS_RADIAL,
            "L": L_RADIAL,
            "mu": MU,
            "boundary_condition": "F(epsilon)-epsilon F'(epsilon)=pi; F(64)=0",
            "solver_coordinate": "theta=pi-F; regular-origin condition theta(epsilon)-epsilon theta'(epsilon)=0",
        },
        nodes,
        field,
        slope,
        spline,
    )


def integrate_profile(
    density: Callable[[float, float, float], float], spline: CubicHermiteSpline, origin_slope: float
) -> tuple[float, float]:
    def inner(r: float) -> float:
        return density(r, math.pi + origin_slope * r, origin_slope)

    def middle(r: float) -> float:
        return density(r, float(spline(r)), float(spline(r, 1)))

    value0, error0 = quad(inner, 0.0, EPS_RADIAL, epsabs=2.0e-9, epsrel=2.0e-9, limit=200)
    knots = np.asarray(spline.x[1:-1], dtype=np.float64)
    value1, error1 = quad(
        middle,
        EPS_RADIAL,
        L_RADIAL,
        epsabs=2.0e-9,
        epsrel=2.0e-9,
        points=knots,
        limit=max(1500, len(spline.x) + 100),
    )
    return float(value0 + value1), float(error0 + error1)


def massive_integrals(field: np.ndarray, slope: np.ndarray, spline: CubicHermiteSpline) -> dict[str, Any]:
    origin_slope = float(slope[0])

    def ratio(value: float, radius: float, power: int) -> float:
        return 0.0 if radius == 0.0 else value / radius**power

    densities: dict[str, Callable[[float, float, float], float]] = {
        "E2_raw": lambda r, f, fp: r * r * fp * fp + 2.0 * math.sin(f) ** 2,
        "E4_raw": lambda r, f, fp: 2.0 * math.sin(f) ** 2 * fp * fp + ratio(math.sin(f) ** 4, r, 2),
        "Em_raw": lambda r, f, fp: MU * MU * r * r * (1.0 - math.cos(f)),
        "degree": lambda r, f, fp: -(2.0 / math.pi) * math.sin(f) ** 2 * fp,
        "Lambda": lambda r, f, fp: 8.0 * r * r * math.sin(f) ** 2 * (1.0 + fp * fp + ratio(math.sin(f) ** 2, r, 2)),
        "R0_squared": lambda r, f, fp: -(2.0 / math.pi) * r * r * math.sin(f) ** 2 * fp,
        "RM_den": lambda r, f, fp: r * r * math.sin(f) ** 2 * fp,
        "RM_num": lambda r, f, fp: r**4 * math.sin(f) ** 2 * fp,
        "G": lambda r, f, fp: 4.0 * r * r * (
            fp
            + ratio(math.sin(2.0 * f), r, 1)
            + ratio(math.sin(2.0 * f) * fp * fp, r, 1)
            + ratio(2.0 * math.sin(f) ** 2 * fp, r, 2)
            + ratio(math.sin(f) ** 2 * math.sin(2.0 * f), r, 3)
        ),
    }
    raw: dict[str, float] = {}
    errors: dict[str, float] = {}
    for name, density in densities.items():
        raw[name], errors[name] = integrate_profile(density, spline, origin_slope)
    e2 = 4.0 * math.pi * raw["E2_raw"]
    e4 = 4.0 * math.pi * raw["E4_raw"]
    em = 8.0 * math.pi * raw["Em_raw"]
    total = e2 + e4 + em
    primary_energy = total / 2.0
    virial_residual = abs(e2 - e4 + 3.0 * em) / total
    half = float(brentq(lambda r: float(spline(r)) - math.pi / 2.0, EPS_RADIAL, L_RADIAL, xtol=1.0e-13, rtol=1.0e-14))
    return {
        "E2": e2,
        "E4": e4,
        "Em": em,
        "energy_total": total,
        "energy_primary_action_normalized": primary_energy,
        "virial_relative": virial_residual,
        "s": total / 4.0,
        "energy_convention": "E2 and E4 use inherited 4pi radial calibration kernels; Em uses 8pi to produce the supplied mu^2 r^2 sin(F) ODE. E_primary_action_normalized=energy_total/2, while calibration s=energy_total/4.",
        "degree": raw["degree"],
        "Lambda": raw["Lambda"],
        "R0_squared": raw["R0_squared"],
        "RM0_squared": raw["RM_num"] / raw["RM_den"],
        "G": raw["G"],
        "half_angle_radius": half,
        "origin_slope": origin_slope,
        "outer_boundary_value": float(field[-1]),
        "outer_boundary_slope": float(slope[-1]),
        "quadrature_error_sum": float(sum(errors.values())),
        "quadrature_errors": errors,
    }


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
        "label": "Mapped—two measured masses fix two effective coefficients for this massive profile",
        "M_N_target_MeV": MN_TARGET,
        "M_Delta_target_MeV": MDELTA_TARGET,
        "M_pi_reference_MeV": MPI_TARGET,
        "mass_split_MeV": delta,
        "M_classical_MeV": m_classical,
        "scale_A_MeV": scale_a,
        "e_B": e_b,
        "f_B_MeV": f_b,
        "I0_MeV_inverse": i0,
        "length_unit_fm": HBARC / (e_b * f_b),
        "M_pi_reconstructed_MeV": MU * e_b * f_b,
        "M_pi_relative_residual": (MU * e_b * f_b - MPI_TARGET) / MPI_TARGET,
        "M_N_reconstructed_MeV": mn,
        "M_Delta_reconstructed_MeV": mdelta,
        "M_N_relative_residual": (mn - MN_TARGET) / MN_TARGET,
        "M_Delta_relative_residual": (mdelta - MDELTA_TARGET) / MDELTA_TARGET,
        "positive_coefficients": bool(e_b > 0.0 and f_b > 0.0 and i0 > 0.0),
        "calibration_formulas": {
            "M_classical": "(5 M_N - M_Delta)/4",
            "A": "M_classical/(2 s)",
            "e_B": "(2 pi Lambda (M_Delta-M_N)/(9 A))^(1/4)",
            "f_B": "A e_B",
            "I0": "pi/(3 e_B^3 f_B)",
            "length_unit": "hbar c/(e_B f_B)",
        },
    }


def massive_observables(static: dict[str, Any], calibration: dict[str, Any]) -> dict[str, Any]:
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
        "isoscalar_electric_radius_fm": row(r_iso, 0.769, 0.10),
        "isoscalar_magnetic_radius_fm": {"value": r_m_iso, "target": None, "verdict": "REPORTED—no frozen target"},
        "proton_magnetic_moment_nuclear_magnetons": row(mu_p, 2.7928473446, 0.10),
        "neutron_magnetic_moment_nuclear_magnetons": row(mu_n, -1.91304273, 0.10),
        "magnetic_moment_magnitude_ratio": row(ratio, 1.459898, 0.05),
        "axial_coupling_g_A": row(g_a, 1.2754, 0.10),
        "pion_nucleon_coupling_g_piNN": row(gpinn, 13.0, 0.10),
        "components": {"isoscalar_moment": isoscalar_mu, "isovector_moment": isovector_mu},
        "formulas": {
            "R0_squared": "-(2/pi) integral r^2 sin(F)^2 F' dr",
            "isoscalar_radius": "length_unit sqrt(R0_squared)",
            "RM0_squared": "integral r^4 sin(F)^2 F' dr / integral r^2 sin(F)^2 F' dr",
            "isoscalar_magnetic_radius": "length_unit sqrt(RM0_squared)",
            "mu_p_n": "R0_squared M_N (M_Delta-M_N)/(9(e_B f_B)^2) +/- M_N/(2(M_Delta-M_N))",
            "G": "4 integral r^2 [F' + sin(2F)/r + sin(2F)F'^2/r + 2sin(F)^2F'/r^2 + sin(F)^2sin(2F)/r^3] dr",
            "g_A": "-pi G/(3 e_B^2)",
            "g_piNN": "M_N g_A/f_B",
        },
        "formula_scope": "Imported leading-order conditional chiral-model formulas; not canonical Cassi predictions.",
    }
def topology_boundary() -> dict[str, Any]:
    return {
        "simply_connected": True,
        "pi_1": 0,
        "integer_B_topological_protection": False,
        "enforced_odd_FR_character": False,
        "reasoning": "S^3 is simply connected and a finite Cartesian product is simply connected; finite-site smooth interactions have no noncontractible loop on which to impose an odd FR character or a continuum degree-one protection.",
        "conditional_regulator": "A scalar Laplace–Beltrami Hamiltonian on this compact manifold defines a conditional regulated quantum model.",
        "not_derived": "Its ground state/excitation state and continuum EFT counterterms do not derive fermionic statistics.",
        "scope": "The continuum hedgehog degree and supplied FR rule remain separate conditional inputs.",
    }


def failure_receipt(output: Path, error: Exception) -> None:
    output.mkdir(parents=True, exist_ok=True)
    target = output / "results.json"
    payload = {
        "schema": SCHEMA,
        "scientific_verdict": "INCONCLUSIVE",
        "failure_type": type(error).__name__,
        "failure": str(error),
        "source_sha256": raw_sha256(Path(__file__)),
    }
    write_json(target, payload)


def run(output: Path) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise NumericalFailure(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    protocol_digest = protocol_sha256()
    action = exact_action_controls()
    geometry = primitive_geometry()
    if not action["hamiltonian_decomposition"]["witness_pass"]:
        raise NumericalFailure("exact Hamiltonian witness failed")
    if geometry["six_unit_link_dyad_isotropic"]:
        raise NumericalFailure("anisotropy boundary unexpectedly became isotropic")
    solver, nodes, field, slope, spline = solve_massive_profile()
    static = massive_integrals(field, slope, spline)
    calibration = calibrate(static)
    observables = massive_observables(static, calibration)
    profile_path = output / "massive_profile.npz"
    with profile_path.open("xb") as stream:
        np.savez(stream, r=nodes, F=field, Fp=slope, basis=np.array([MU, L_RADIAL, EPS_RADIAL], dtype=np.float64))
    artifact = {"file": profile_path.name, "sha256": raw_sha256(profile_path), "bytes": profile_path.stat().st_size}
    source_provenance = {
        "conditional_baryon_script": {
            "path": "computations/matter_formation_conditional_baryon.py",
            "canonical_text_sha256": canonical_text_sha256(CONDITIONAL_SCRIPT),
        },
        "conditional_baryon_prereg": {
            "path": "computations/matter-formation-conditional-baryon-prereg.md",
            "canonical_text_sha256": canonical_text_sha256(CONDITIONAL_PREREG),
        },
        "G_convention": "Inherited conditional-baryon G integrand includes the explicit leading factor 4.",
    }
    checks = {
        "exact_action_momentum": action["pi_symbolic_max_residual"] == "0",
        "exact_stress_symmetric": all(v == "0" for v in action["stress_antisymmetry_residuals"]),
        "exact_hamiltonian_split": bool(action["hamiltonian_decomposition"]["witness_pass"]),
        "primitive_det_nonzero": abs(float(geometry["A0_det_numeric"])) > 0.0,
        "six_link_dyad_anisotropic": not geometry["six_unit_link_dyad_isotropic"],
        "massive_profile_finite": not bool(finite_tree(static)),
        "massive_degree_near_one": abs(float(static["degree"]) - 1.0) <= 2.0e-8,
        "massive_boundary_value": abs(float(static["outer_boundary_value"])) <= 2.0e-10,
        "massive_virial": float(static["virial_relative"]) <= 1.0e-7,
        "pion_reconstruction_finite": math.isfinite(float(calibration["M_pi_reconstructed_MeV"])),
        "mass_reconstruction": abs(float(calibration["M_N_relative_residual"])) <= 2.0e-12 and abs(float(calibration["M_Delta_relative_residual"])) <= 2.0e-12,
        "positive_calibration": bool(calibration["positive_coefficients"]),
    }
    if not all(checks.values()):
        raise NumericalFailure(f"numerical evidence check failed: {[k for k, v in checks.items() if not v]}")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "source_sha256": raw_sha256(Path(__file__)),
        "protocol_path": "computations/matter-formation-continuum-report.md",
        "source_provenance": source_provenance,
        "protocol_sha256": protocol_digest,
        "mode": "conditional continuum action/current/stress/vacuum plus independent massive radial calibration",
        "parameters": {"N": None, "L": L_RADIAL, "mu": MU, "kappa": KAPPA, "p": P_PRIMITIVE, "phi": PHI, "hbar_c_MeV_fm": HBARC, "M_pi_reference_MeV": MPI_TARGET},
        "action_derivation": action,
        "primitive_geometry": geometry,
        "topology_regulator_boundary": topology_boundary(),
        "massive_bvp_solver": solver,
        "massive_static": static,
        "massive_calibration": calibration,
        "massive_observables": observables,
        "artifacts": {"massive_profile": artifact},
        "checks": checks,
        "analytic_scope_statements": [
            "The action, current, stress tensor, Hamiltonian split, and three equal radial vacuum masses are continuum algebra statements for an added O(4) chiral field.",
            "The finite-site topology and scalar Laplace–Beltrami regulator statements are conditional mathematical boundaries, not a quantum completion.",
            "The primitive-link dyad is a geometry diagnostic; equal normalized links do not repair anisotropy for phi and p=2.",
            "The massive BVP and coefficient extraction are an independent conditional hedgehog benchmark; masses are calibration targets, while radii, moments, g_A, and g_piNN are out-of-fit diagnostics.",
            "Physical Cassi matter formation remains open; no fermionic statistics, canonical density-to-phase map, microscopic vacuum, renormalization, QCD, or particle identification is derived.",
        ],
        "scientific_verdict": "QUALIFIED_CONDITIONAL_STRUCTURE_ONLY",
    }
    write_json(output / "results.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        print(f"NumericalFailure: output directory is not empty: {output}", file=sys.stderr)
        return 2
    try:
        payload = run(output)
        print(json.dumps({"schema": payload["schema"], "scientific_verdict": payload["scientific_verdict"], "checks": payload["checks"]}, indent=2))
        return 0
    except Exception as exc:
        if not output.exists() or not any(output.iterdir()):
            try:
                failure_receipt(output, exc)
            except Exception:
                pass
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
