#!/usr/bin/env python3
"""Exact finite-Fourier verifier for the unforced 3-D incompressible NS transfer.

The script is an algebraic receipt, not a regularity proof.  It uses the
periodic convention T^3=(R/2pi Z)^3, normalized spatial mean/Parseval sums,
and mean-zero Fourier dictionaries.  Every Fourier mode has its conjugate
partner, and the nonlinear convolution is projected by the full Leray
projector, including modes absent from the initial field.  The heat corrector
is the cubic functional obtained by dividing each ordered interaction term by
its SUM heat divisor |a|^2+|p|^2+|q|^2.

The checks establish only the stated finite-dimensional identities.  They do
not establish a coercive estimate, a physical stress-regulation law, a PDE
existence theorem, or any universal sign for R=D Phi[B].  In particular, the
planar control is an adversarial sign control rather than a constitutive claim.
The Gaussian integral and scaling checks record analytic assumptions in a
finite Fourier setting; they do not turn those assumptions into estimates for
arbitrary solutions.

Run from the CassiTheory repository root:
    python computations/verify_navier_stokes_transfer.py

The default receipt is runs/navier_stokes_transfer/verification.json.  Pass
--output PATH to choose another JSON receipt.  The governing preregistration,
when present, is hashed but never modified:
computations/navier_stokes_stress_geometry_prereg.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Tuple

import sympy as sp


Vec = sp.Matrix
Mode = Tuple[int, int, int]
Field = Dict[Mode, Vec]

I = sp.I
ZERO = sp.Integer(0)


# ---------------------------------------------------------------------------
# Small exact-algebra helpers


def mode_norm_sq(k: Mode) -> sp.Expr:
    return sp.Integer(sum(component * component for component in k))


def mode_norm(k: Mode) -> sp.Expr:
    return sp.sqrt(mode_norm_sq(k))


def zero_vec() -> Vec:
    return Vec([ZERO, ZERO, ZERO])


def conjugate_vec(v: Vec) -> Vec:
    return v.applyfunc(sp.conjugate)


def inner_vec(x: Vec, y: Vec) -> sp.Expr:
    return sum(sp.conjugate(x[j]) * y[j] for j in range(3))


def real_part(value: sp.Expr) -> sp.Expr:
    return sp.simplify(sp.expand_complex(value).as_real_imag()[0])


def scalar(value: sp.Expr) -> sp.Expr:
    """Moderate simplification suitable for exact receipt values."""
    return sp.factor(sp.expand(value))


def is_zero(value: sp.Expr) -> bool:
    return sp.simplify(value) == ZERO


def is_positive(value: sp.Expr) -> bool:
    value = sp.simplify(value)
    if value.is_positive is True:
        return True
    try:
        return bool(value > ZERO)
    except TypeError:
        return False


def is_negative(value: sp.Expr) -> bool:
    value = sp.simplify(value)
    if value.is_negative is True:
        return True
    try:
        return bool(value < ZERO)
    except TypeError:
        return False


def receipt(value: object) -> object:
    if isinstance(value, sp.Basic):
        return str(sp.simplify(value))
    if isinstance(value, sp.MatrixBase):
        return [receipt(component) for component in value]
    if isinstance(value, dict):
        return {str(key): receipt(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [receipt(item) for item in value]
    return value

# ---------------------------------------------------------------------------
# Fourier dictionaries, Leray projection, and ordered NS convolution


def add_real_mode(field: MutableMapping[Mode, Vec], k: Mode, value: Vec) -> None:
    """Insert k and the forced real-field conjugate at -k."""
    if k == (0, 0, 0):
        raise ValueError("mean-zero fixtures may not contain mode zero")
    if any(sp.simplify(component) != ZERO for component in field.get(k, zero_vec())):
        raise ValueError(f"duplicate Fourier mode {k}")
    field[k] = value
    field[tuple(-component for component in k)] = conjugate_vec(value)


def get_mode(field: Mapping[Mode, Vec], k: Mode) -> Vec:
    return field.get(k, zero_vec())


def leray_projector(k: Mode) -> sp.Matrix:
    if k == (0, 0, 0):
        return sp.eye(3)
    kk = Vec(k)
    return sp.eye(3) - (kk * kk.T) / mode_norm_sq(k)


def projected_convection(a: Mode, p: Mode, q: Mode, up: Vec, uq: Vec) -> Vec:
    """One ordered term of B=-P[(u.grad)u], with derivative on q."""
    raw = -I * (Vec(q).dot(up)) * uq
    return leray_projector(a) * raw


def ordered_terms(field: Mapping[Mode, Vec]) -> Iterable[Tuple[Mode, Mode, Mode, Vec]]:
    """Yield all ordered (p,q) terms, retaining generated a=p+q."""
    modes = tuple(field)
    for p in modes:
        for q in modes:
            a = tuple(p[j] + q[j] for j in range(3))
            yield a, p, q, projected_convection(a, p, q, field[p], field[q])


def full_leray_B(field: Mapping[Mode, Vec]) -> Field:
    result: Field = {}
    for a, _p, _q, term in ordered_terms(field):
        result[a] = result.get(a, zero_vec()) + term
    simplified = {a: sp.simplify(value) for a, value in result.items()}
    return {a: value for a, value in simplified.items() if value != zero_vec()}


def scalar_F(field: Mapping[Mode, Vec]) -> sp.Expr:
    """F=<Lambda u,B> from ordered terms (only base u_a pairs contribute)."""
    total = ZERO
    for a, _p, _q, term in ordered_terms(field):
        ua = get_mode(field, a)
        total += mode_norm(a) * inner_vec(ua, term)
    return real_part(total)


def trilinear_term(
    a: Mode, p: Mode, q: Mode, xa: Vec, xp: Vec, xq: Vec
) -> sp.Expr:
    """|a| <x_a, -P_a[i(q.x_p)x_q]> for one cubic slot choice."""
    return mode_norm(a) * inner_vec(xa, projected_convection(a, p, q, xp, xq))


def phi_cubic(field: Mapping[Mode, Vec], nu: sp.Expr) -> sp.Expr:
    """Cubic Phi with the SUM heat divisor for every ordered term."""
    total = ZERO
    for a, p, q, _term in ordered_terms(field):
        divisor = nu * (mode_norm_sq(a) + mode_norm_sq(p) + mode_norm_sq(q))
        total += trilinear_term(a, p, q, get_mode(field, a), field[p], field[q]) / divisor
    return real_part(total)


def directional_phi(
    base: Mapping[Mode, Vec], direction: Mapping[Mode, Vec], nu: sp.Expr
) -> Tuple[sp.Expr, Dict[str, sp.Expr]]:
    """D Phi_base[direction], differentiating all three cubic slots.

    Each differentiated slot is summed over its own actual support.  This is
    essential for direction=B(base,base): B contains modes absent from the
    frozen base support, and those modes can occupy either input slot of the
    cubic interaction.  The output slot still uses base p,q, while an input
    slot uses the direction support and the other base input.
    """
    initial_modes = set(base)
    total = ZERO
    breakdown: Dict[str, sp.Expr] = {
        "output_initial": ZERO,
        "output_generated": ZERO,
        "advect_initial": ZERO,
        "advect_generated": ZERO,
        "target_initial": ZERO,
        "target_generated": ZERO,
    }

    # Output-slot derivative: p,q are both base modes and a=p+q.
    for p in base:
        for q in base:
            a = tuple(p[j] + q[j] for j in range(3))
            divisor = nu * (mode_norm_sq(a) + mode_norm_sq(p) + mode_norm_sq(q))
            value = trilinear_term(a, p, q, get_mode(direction, a), base[p], base[q]) / divisor
            key = "output_initial" if a in initial_modes else "output_generated"
            breakdown[key] += value
            total += value

    # Advecting-slot derivative: p is a direction mode, q is a base mode.
    for p in direction:
        for q in base:
            a = tuple(p[j] + q[j] for j in range(3))
            divisor = nu * (mode_norm_sq(a) + mode_norm_sq(p) + mode_norm_sq(q))
            value = trilinear_term(a, p, q, get_mode(base, a), direction[p], base[q]) / divisor
            key = "advect_initial" if p in initial_modes else "advect_generated"
            breakdown[key] += value
            total += value

    # Target-slot derivative: p is a base mode, q is a direction mode.
    for p in base:
        for q in direction:
            a = tuple(p[j] + q[j] for j in range(3))
            divisor = nu * (mode_norm_sq(a) + mode_norm_sq(p) + mode_norm_sq(q))
            value = trilinear_term(a, p, q, get_mode(base, a), base[p], direction[q]) / divisor
            key = "target_initial" if q in initial_modes else "target_generated"
            breakdown[key] += value
            total += value

    return real_part(total), {name: real_part(value) for name, value in breakdown.items()}


def field_inner(left: Mapping[Mode, Vec], right: Mapping[Mode, Vec]) -> sp.Expr:
    total = ZERO
    for k in set(left) | set(right):
        total += inner_vec(get_mode(left, k), get_mode(right, k))
    return real_part(total)


def quadratic_C(field: Mapping[Mode, Vec]) -> sp.Expr:
    return scalar(sum(mode_norm(k) * inner_vec(v, v) for k, v in field.items()))


def quadratic_Y(field: Mapping[Mode, Vec]) -> sp.Expr:
    return scalar(sum(mode_norm(k) ** 3 * inner_vec(v, v) for k, v in field.items()))

def lambda_field_inner(left: Mapping[Mode, Vec], right: Mapping[Mode, Vec]) -> sp.Expr:
    total = ZERO
    for k in set(left) | set(right):
        total += mode_norm(k) * inner_vec(get_mode(left, k), get_mode(right, k))
    return real_part(total)

def heat_direction(field: Mapping[Mode, Vec], nu: sp.Expr) -> Field:
    return {k: -nu * mode_norm_sq(k) * value for k, value in field.items()}


def divergence(field: Mapping[Mode, Vec]) -> Dict[Mode, sp.Expr]:
    return {k: sp.simplify(Vec(k).dot(value)) for k, value in field.items()}


def is_real_field(field: Mapping[Mode, Vec]) -> bool:
    for k, value in field.items():
        if k == (0, 0, 0):
            continue
        if any(sp.simplify(get_mode(field, tuple(-j for j in k))[j] - sp.conjugate(value[j])) != ZERO for j in range(3)):
            return False
    return True


def vorticity(field: Mapping[Mode, Vec]) -> Field:
    return {k: I * Vec(k).cross(value) for k, value in field.items()}




# ---------------------------------------------------------------------------
# Helical transfer identity


def helical_vorticities(field: Mapping[Mode, Vec]) -> Tuple[Field, Field]:
    omega_minus: Field = {}
    omega_plus: Field = {}
    for k, value in field.items():
        if k == (0, 0, 0):
            continue
        khat = Vec(k) / mode_norm(k)
        transverse = leray_projector(k)
        cross_matrix = sp.Matrix(
            [
                [ZERO, -khat[2], khat[1]],
                [khat[2], ZERO, -khat[0]],
                [-khat[1], khat[0], ZERO],
            ]
        )
        helical_operator = I * cross_matrix
        plus_u = (transverse + helical_operator) * value / 2
        minus_u = (transverse - helical_operator) * value / 2
        omega_plus[k] = I * Vec(k).cross(plus_u)
        omega_minus[k] = I * Vec(k).cross(minus_u)
    return omega_minus, omega_plus


def helical_I(field: Mapping[Mode, Vec]) -> sp.Expr:
    omega_minus, omega_plus = helical_vorticities(field)
    total = ZERO
    for a in set(field) | {tuple(p[j] + q[j] for j in range(3)) for p in omega_minus for q in omega_plus}:
        cross_sum = zero_vec()
        for p in omega_minus:
            for q in omega_plus:
                if tuple(p[j] + q[j] for j in range(3)) == a:
                    cross_sum += omega_minus[p].cross(omega_plus[q])
        total += inner_vec(get_mode(field, a), cross_sum)
    return real_part(total)


# ---------------------------------------------------------------------------
# Fixtures and exact-circle checks


def three_dimensional_fixture() -> Field:
    field: Field = {}
    add_real_mode(field, (1, 0, 0), I * Vec([0, 1, 1]))
    add_real_mode(field, (0, 2, 0), I * Vec([1, 0, 0]))
    add_real_mode(field, (1, 2, 0), I * Vec([-2, 1, 0]))
    add_real_mode(field, (0, 0, 3), I * Vec([1, 0, 0]))
    return field


def planar_fixture() -> Field:
    """Same p,q wavevectors as the 3-D fixture, with planar amplitudes."""
    field: Field = {}
    add_real_mode(field, (1, 0, 0), I * Vec([0, 1, 0]))
    add_real_mode(field, (0, 2, 0), I * Vec([1, 0, 0]))
    return field


def phase_tuned(field: Mapping[Mode, Vec], a: sp.Expr, b: sp.Expr) -> Field:
    result = dict(field)
    k = (1, 2, 0)
    z = a + I * b
    result[k] = z * field[k]
    result[tuple(-j for j in k)] = sp.conjugate(z) * field[tuple(-j for j in k)]
    return result


def circle_remainder(expr: sp.Expr, a: sp.Symbol, b: sp.Symbol) -> sp.Expr:
    """Reduce an exact polynomial modulo a^2+b^2-1, without samples."""
    numerator = sp.together(sp.expand(expr)).as_numer_denom()[0]
    polynomial = sp.Poly(numerator, b, domain="EX")
    relation = sp.Poly(b**2 + a**2 - 1, b, domain="EX")
    return sp.simplify(polynomial.rem(relation).as_expr())


# ---------------------------------------------------------------------------
# Receipt driver


class Receipt:
    def __init__(self) -> None:
        self.checks: Dict[str, Dict[str, object]] = {}
        self.failures: list[str] = []

    def check(self, name: str, passed: bool, value: object = None) -> None:
        passed = bool(passed)
        row: Dict[str, object] = {"passed": passed}
        if value is not None:
            row["value"] = receipt(value)
        self.checks[name] = row
        print(f"  {'PASS' if passed else 'FAIL'} {name}: {receipt(value) if value is not None else ''}")
        if not passed:
            self.failures.append(name)

    def exact(self, name: str, actual: sp.Expr, expected: sp.Expr) -> None:
        self.check(name, is_zero(actual - expected), actual)


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("runs/navier_stokes_transfer/verification.json"))
    args = parser.parse_args()

    receipt_book = Receipt()
    nu = sp.symbols("nu", positive=True, finite=True)
    alpha = sp.symbols("alpha", real=True)
    a_symbol, b_symbol = sp.symbols("a b", real=True)
    A = sp.symbols("A", positive=True, finite=True)

    u = three_dimensional_fixture()
    b = full_leray_B(u)
    phi = phi_cubic(u, nu)
    F0 = scalar_F(u)
    C0 = quadratic_C(u)
    Y0 = quadratic_Y(u)
    R3, breakdown3 = directional_phi(u, b, nu)

    print("Finite Fourier NS transfer verifier")
    print(f"  modes(initial)={len(u)} modes(B, generated included)={len(b)}")
    print(f"  C0={receipt(C0)}")
    print(f"  F0={receipt(F0)}")
    print(f"  Phi0={receipt(phi)}")
    print(f"  Y0={receipt(Y0)}")
    print(f"  R3={receipt(R3)}")
    print("  R3 breakdown (generated directional modes retained):")
    print("  R sign scope: fixture/control only; no universal sign is asserted.")
    for key in sorted(breakdown3):
        print(f"    {key}={receipt(breakdown3[key])}")

    # Core fixture identities.
    receipt_book.check("initial divergence", all(is_zero(value) for value in divergence(u).values()), divergence(u))
    receipt_book.check("initial reality", is_real_field(u))
    receipt_book.check("full B reality", is_real_field(b))
    receipt_book.check("full B divergence", all(is_zero(value) for value in divergence(b).values()))
    receipt_book.exact("C0 fixture", C0, 14 + 10 * sp.sqrt(5))
    receipt_book.exact("F0 fixture", F0, 14 - 6 * sp.sqrt(5))
    receipt_book.exact("Phi0 fixture", phi, F0 / (10 * nu))
    receipt_book.check("F0 positive", is_positive(F0), F0)

    nonlinear_energy_rate = 2 * field_inner(u, b)
    omega = vorticity(u)
    nonlinear_helicity_rate = 2 * field_inner(omega, b)
    receipt_book.exact("zero nonlinear energy rate", nonlinear_energy_rate, ZERO)
    receipt_book.exact("zero nonlinear helicity rate", nonlinear_helicity_rate, ZERO)

    helical_identity_rhs = 2 * helical_I(u)
    receipt_book.exact("F=2I helical projector identity", F0, helical_identity_rhs)
    print(f"  helical I={receipt(helical_identity_rhs / 2)}")

    # Heat and corrected derivatives.
    heat = heat_direction(u, nu)
    dphi_heat, _heat_breakdown = directional_phi(u, heat, nu)
    receipt_book.exact("Dphi[nu Delta u]=-F", dphi_heat, -F0)
    cprime_heat = 2 * lambda_field_inner(u, heat)
    cprime_full = cprime_heat + 2 * F0
    corrected_direct = cprime_full + 2 * dphi_heat + 2 * R3
    corrected_expected = -2 * nu * Y0 + 2 * R3
    receipt_book.exact("C prime NS decomposition", cprime_full, -2 * nu * Y0 + 2 * F0)
    receipt_book.exact("full corrected derivative", corrected_direct, corrected_expected)
    receipt_book.check("3-D R quartic sign is positive", is_positive(nu * R3), nu * R3)
    generated_components = [
        breakdown3["output_generated"],
        breakdown3["advect_generated"],
        breakdown3["target_generated"],
    ]
    generated = scalar(sum(generated_components))
    generated_keys = set(b) - set(u)
    receipt_book.check("generated B modes retained", bool(generated_keys), sorted(generated_keys))
    receipt_book.check("generated-mode contribution is nonzero", any(not is_zero(value) for value in generated_components), generated)

    # Large-amplitude positivity is a finite fixture check, not a PDE estimate.
    amplitude_400 = sp.Integer(400)
    cprime_400 = 2 * amplitude_400**2 * (amplitude_400 * F0 - Y0)
    receipt_book.check("C prime positive at amplitude 400, nu=1", is_positive(cprime_400), cprime_400)

    # Phase circle: exact polynomial reduction modulo a^2+b^2=1.
    phased = phase_tuned(u, a_symbol, b_symbol)
    C_phase = quadratic_C(phased)
    F_phase = scalar_F(phased)
    phi_phase = phi_cubic(phased, nu)
    receipt_book.check("phase C unchanged on rational circle", is_zero(circle_remainder(C_phase - C0, a_symbol, b_symbol)), C_phase - C0)
    receipt_book.check("phase F=a F0 on rational circle", is_zero(circle_remainder(F_phase - a_symbol * F0, a_symbol, b_symbol)), F_phase - a_symbol * F0)
    receipt_book.check("phase Phi=a Phi0 on rational circle", is_zero(circle_remainder(phi_phase - a_symbol * phi, a_symbol, b_symbol)), phi_phase - a_symbol * phi)
    cancellation_a = -5 * nu * C0 / (A * F0)
    cancellation = sp.factor(A**2 * C0 + 2 * A**3 * cancellation_a * phi)
    receipt_book.exact("phase cancellation C(Au)+2Phi(Au)=0", cancellation, ZERO)
    threshold = sp.factor(5 * C0 / F0)
    receipt_book.exact("admissible phase threshold", threshold, 155 + 70 * sp.sqrt(5))
    # The exact implication is represented by its boundary: at
    # A=(155+70*sqrt(5))*nu one has |a|=1, and larger A only decreases |a|.
    receipt_book.check("phase threshold is positive", is_positive(threshold), threshold)
    t = sp.symbols("t", positive=True, finite=True)
    rho = 1 + t
    admissible_A = threshold * nu * rho
    admissible_a_sq = sp.factor(cancellation_a.subs(A, admissible_A) ** 2)
    receipt_book.exact("phase square at A=(1+t)*threshold*nu", admissible_a_sq, 1 / (1 + t) ** 2)
    receipt_book.exact(
        "phase admissibility gap is nonnegative for t>0",
        sp.factor(1 - admissible_a_sq),
        t * (2 + t) / (1 + t) ** 2,
    )
    scaled_u = {k: A * value for k, value in u.items()}
    receipt_book.exact("cancellation C equals A^2 C0", quadratic_C(scaled_u), A**2 * C0)

    # The positive-completion derivative is verified symbolically for arbitrary alpha.
    # The corrected base derivative has no standalone cubic +2F; the alpha
    # term still uses the uncorrected C' through cprime_full.
    ealpha_direct = corrected_direct + alpha * (2 * C0 * cprime_full / nu**2)
    ealpha_expected = corrected_expected + 4 * alpha * C0 * (F0 - nu * Y0) / nu**2
    receipt_book.exact("positive-completion E_alpha derivative", ealpha_direct, ealpha_expected)
    R3_nu1 = R3.subs(nu, 1)
    ealpha_400_exact = (
        -2 * amplitude_400**2 * Y0
        + 2 * amplitude_400**4 * R3_nu1
        + 4 * amplitude_400**4 * C0 * (amplitude_400 * F0 - Y0)
    )
    receipt_book.check("E_alpha positive completion at A=400, alpha=1, nu=1", is_positive(ealpha_400_exact), ealpha_400_exact)

    # Planar adversarial control, with a direct ordered-slot derivation.
    planar = planar_fixture()
    planar_b = full_leray_B(planar)
    planar_R, planar_breakdown = directional_phi(planar, planar_b, nu)
    print(f"  planar R (direct ordered-slot derivation)={receipt(planar_R)}")
    for key in sorted(planar_breakdown):
        print(f"    planar {key}={receipt(planar_breakdown[key])}")
    receipt_book.check("planar control divergence", all(is_zero(value) for value in divergence(planar).values()))
    receipt_book.check("planar control reality", is_real_field(planar_b))
    receipt_book.check("planar R is negative", is_negative(planar_R), planar_R)
    if not is_negative(planar_R):
        print("  REVIEW planar expected-sign control: direct value is not negative")

    # Gaussian scalar integral coefficient: differentiate under the integral,
    # evaluate the Gaussian derivative integral, then integrate it from zero.
    x = sp.symbols("x", positive=True)
    ell = sp.symbols("ell", positive=True)
    derivative_integral = sp.integrate(sp.exp(-x * ell**2), (ell, 0, sp.oo))
    s = sp.symbols("s", positive=True)
    ibp_integral = sp.integrate(sp.sqrt(sp.pi) / (2 * sp.sqrt(s)), (s, 0, x))
    receipt_book.exact(
        "Gaussian derivative integral",
        derivative_integral,
        sp.sqrt(sp.pi) / (2 * sp.sqrt(x)),
    )
    receipt_book.exact("Gaussian J from IBP", ibp_integral, sp.sqrt(sp.pi * x))
    receipt_book.exact("Gaussian J boundary at zero", ibp_integral.subs(x, 0), ZERO)
    receipt_book.exact("Gaussian normalized coefficient", ibp_integral / sp.sqrt(sp.pi), sp.sqrt(x))
    print("  Gaussian convention: (1/sqrt(pi))*int_0^infty ell^-2*(1-exp(-x ell^2)) d ell = sqrt(x)")

    # Original NS scaling bookkeeping under u_lambda=lambda u(lambda x,lambda^2 t).
    # Derive the exponents from amplitude, coordinate, time, volume, and
    # derivative factors rather than comparing two copied dictionaries.
    scaling = {"u": sp.Integer(1), "x": sp.Integer(-1), "t": sp.Integer(-2)}
    u_exp, x_exp, t_exp = scaling["u"], scaling["x"], scaling["t"]
    b_exp = 2 * u_exp - x_exp
    f_exp = (u_exp - x_exp) + b_exp + 3 * x_exp
    derived_scaling = {
        "u": u_exp,
        "x": x_exp,
        "t": t_exp,
        "pressure": 2 * u_exp,
        "nu": t_exp - 2 * x_exp,
        "C=H^(1/2)^2": 2 * u_exp + 2 * sp.Rational(1, 2) * (-x_exp) + 3 * x_exp,
        "Y=H^(3/2)^2": 2 * u_exp + 2 * sp.Rational(3, 2) * (-x_exp) + 3 * x_exp,
        "F": f_exp,
        "Phi": f_exp + t_exp,
        "R=Dphi[B]": f_exp + t_exp + b_exp - u_exp,
    }
    expected_scaling = {"u": 1, "x": -1, "t": -2, "pressure": 2, "nu": 0, "C=H^(1/2)^2": 0, "Y=H^(3/2)^2": 2, "F": 2, "Phi": 0, "R=Dphi[B]": 2}
    for name, expected in expected_scaling.items():
        receipt_book.exact(f"NS scaling exponent {name}", derived_scaling[name], sp.Integer(expected))
    amplitude_homogeneity = {"C": 2, "F": 3, "Phi": 3, "R": 4, "C^2": 4}
    print(f"  NS scaling exponents: {receipt(derived_scaling)}")
    print(f"  amplitude homogeneity: {amplitude_homogeneity}")
    p_mode, q_mode = (1, 0, 0), (0, 2, 0)
    sum_divisor = nu * (mode_norm_sq(tuple(p_mode[j] + q_mode[j] for j in range(3))) + mode_norm_sq(p_mode) + mode_norm_sq(q_mode))
    difference_divisor = mode_norm_sq(tuple(p_mode[j] + q_mode[j] for j in range(3))) - mode_norm_sq(p_mode) - mode_norm_sq(q_mode)
    receipt_book.exact("fixture SUM heat divisor is 10 nu", sum_divisor, 10 * nu)
    receipt_book.exact("orthogonal quadratic difference divisor is zero", difference_divisor, ZERO)
    print("  SUM heat divisor is nu*(|a|^2+|p|^2+|q|^2); it is distinct from the quadratic interaction-difference divisor, which is zero when p dot q=0.")

    theory_root = Path(__file__).resolve().parents[1]
    protocol_path = theory_root / "computations/navier_stokes_stress_geometry_prereg.md"
    script_hash = sha256(Path(__file__).resolve())
    protocol_hash = sha256(protocol_path)
    if protocol_hash is None:
        print(f"  protocol SHA256: MISSING ({protocol_path})")
    else:
        print(f"  protocol SHA256: {protocol_hash}")

    output = {
        "schema": "navier_stokes_transfer_verification.v1",
        "script_sha256": script_hash,
        "protocol_sha256": protocol_hash,
        "checks": receipt_book.checks,
        "metrics": {
            "C0": receipt(C0),
            "F0": receipt(F0),
            "Phi0": receipt(phi),
            "Y0": receipt(Y0),
            "R3": receipt(R3),
            "R3_generated_directional": receipt(generated),
            "R_planar": receipt(planar_R),
            "threshold_over_nu": receipt(threshold),
            "initial_mode_count": len(u),
            "full_B_mode_count": len(b),
        },
        "scope": {
            "domain": "finite exact Fourier dictionaries on mean-zero T^3",
            "normalization": "normalized spatial mean/Parseval sum",
            "nu": "positive symbolic parameter",
            "limitations": "algebraic identities do not prove PDE estimates, global regularity, or a universal physical sign for R",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"  receipt written: {args.output}")

    if receipt_book.failures:
        message = "FAILED CHECKS: " + ", ".join(receipt_book.failures)
        print(message, file=sys.stderr)
        raise RuntimeError(message)
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
