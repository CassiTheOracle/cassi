#!/usr/bin/env python3
"""Verify fixed helical-spread and phase-current coercivity identities.

Run from CassiTheory with --output pointing to a fresh receipt.
No candidate singular trajectory is integrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-helical-spread-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_helical_spread/verification.json"
SOURCE_PATHS = (
    "computations/navier-stokes-helical-spread-prereg.md",
    "computations/verify_navier_stokes_helical_spread.py",
)


class Receipt:
    def __init__(self) -> None:
        self.checks: list[dict[str, object]] = []
        self.failures: list[str] = []
        self.nonfinite_values: list[str] = []

    def check(self, name: str, passed: bool, value: object = None) -> None:
        if any(row["name"] == name for row in self.checks):
            raise ValueError(f"Duplicate verification name: {name}")
        row: dict[str, object] = {"name": name, "passed": bool(passed)}
        if value is not None:
            if not finite_object(value):
                self.nonfinite_values.append(name)
            row["value"] = json_safe(value)
        self.checks.append(row)
        if not passed:
            self.failures.append(name)

    def exact(self, name: str, actual: sp.Expr, expected: sp.Expr) -> None:
        actual = sp.simplify(actual)
        expected = sp.simplify(expected)
        residual = sp.simplify(actual - expected)
        self.check(
            name,
            residual == 0,
            {"actual": actual, "expected": expected, "residual": residual},
        )


def json_safe(value: object) -> object:
    if isinstance(value, sp.Basic):
        return str(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_expression(value: sp.Expr) -> bool:
    return not sp.sympify(value).has(sp.oo, -sp.oo, sp.zoo, sp.nan)


def finite_object(value: object) -> bool:
    if isinstance(value, sp.Basic):
        return finite_expression(value)
    if isinstance(value, dict):
        return all(finite_object(key) and finite_object(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_object(item) for item in value)
    return True


def signed_moments(
    supports: tuple[sp.Expr, ...], weights: tuple[sp.Expr, ...]
) -> dict[int, sp.Expr]:
    return {
        order: sp.simplify(
            sum(weight * support**order for support, weight in zip(supports, weights))
        )
        for order in range(5)
    }


def pair_spread(
    supports: tuple[sp.Expr, ...], weights: tuple[sp.Expr, ...]
) -> tuple[sp.Expr, sp.Expr]:
    variance = sp.Rational(1, 8) * sum(
        left_weight * right_weight * (left - right) ** 2
        for left, left_weight in zip(supports, weights)
        for right, right_weight in zip(supports, weights)
    )
    dissipation = sp.Rational(1, 4) * sum(
        left_weight
        * right_weight
        * (left - right) ** 2
        * (left**2 + right**2)
        for left, left_weight in zip(supports, weights)
        for right, right_weight in zip(supports, weights)
    )
    return sp.simplify(variance), sp.simplify(dissipation)


def jacobian(vector: sp.Matrix, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    return sp.Matrix(
        len(vector),
        len(coordinates),
        lambda row, column: sp.diff(vector[row], coordinates[column]),
    )


def curl(vector: sp.Matrix, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    x, y, z = coordinates
    return sp.Matrix(
        [
            sp.diff(vector[2], y) - sp.diff(vector[1], z),
            sp.diff(vector[0], z) - sp.diff(vector[2], x),
            sp.diff(vector[1], x) - sp.diff(vector[0], y),
        ]
    )


def laplacian(vector: sp.Matrix, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    return sp.Matrix(
        [
            sum(sp.diff(component, coordinate, 2) for coordinate in coordinates)
            for component in vector
        ]
    )


def normalized_torus_average(
    expression: sp.Expr, coordinates: tuple[sp.Symbol, ...]
) -> sp.Expr:
    result = sp.expand_trig(sp.expand(expression))
    for coordinate in coordinates:
        result = sp.integrate(result, (coordinate, 0, 2 * sp.pi)) / (2 * sp.pi)
        result = sp.simplify(result)
    return sp.simplify(result)


def vector_average(
    vector: sp.Matrix, coordinates: tuple[sp.Symbol, ...]
) -> sp.Matrix:
    return vector.applyfunc(lambda value: normalized_torus_average(value, coordinates))


def field_quantities(
    velocity: sp.Matrix,
    coordinates: tuple[sp.Symbol, ...],
    lambda_velocity: sp.Matrix,
    lambda_cubed_velocity: sp.Matrix,
) -> dict[str, sp.Expr | sp.Matrix]:
    gradient = jacobian(velocity, coordinates)
    strain = sp.simplify((gradient + gradient.T) / 2)
    vorticity = curl(velocity, coordinates)
    curl_vorticity = curl(vorticity, coordinates)
    vorticity_gradient = jacobian(vorticity, coordinates)
    kinetic = normalized_torus_average(velocity.dot(velocity), coordinates) / 2
    enstrophy = normalized_torus_average(vorticity.dot(vorticity), coordinates) / 2
    palinstrophy = normalized_torus_average(
        sum(entry**2 for entry in vorticity_gradient), coordinates
    ) / 2
    critical = normalized_torus_average(velocity.dot(lambda_velocity), coordinates)
    critical_dissipation = normalized_torus_average(
        velocity.dot(lambda_cubed_velocity), coordinates
    )
    helicity = normalized_torus_average(velocity.dot(vorticity), coordinates)
    helicity_dissipation = normalized_torus_average(
        vorticity.dot(curl_vorticity), coordinates
    )
    production = normalized_torus_average(
        (vorticity.T * strain * vorticity)[0], coordinates
    )
    cancellation = normalized_torus_average(
        (velocity.T * strain * vorticity)[0], coordinates
    )
    return {
        "gradient": gradient,
        "strain": strain,
        "vorticity": vorticity,
        "K": sp.simplify(kinetic),
        "E": sp.simplify(enstrophy),
        "G": sp.simplify(palinstrophy),
        "C": sp.simplify(critical),
        "Y": sp.simplify(critical_dissipation),
        "H": sp.simplify(helicity),
        "J": sp.simplify(helicity_dissipation),
        "A": sp.simplify(production),
        "u_S_omega": sp.simplify(cancellation),
    }


def gaussian_polynomial_integral(
    polynomial: sp.Expr,
    rate: sp.Expr,
    coordinates: tuple[sp.Symbol, ...],
) -> sp.Expr:
    expanded = sp.Poly(sp.expand(polynomial), *coordinates)
    total = sp.Integer(0)
    for powers, coefficient in expanded.terms():
        term = coefficient
        for power in powers:
            if power % 2:
                term = 0
                break
            term *= sp.gamma(sp.Rational(power + 1, 2)) / rate ** sp.Rational(
                power + 1, 2
            )
        total += term
    return sp.simplify(total)


def verify_moment_identities(book: Receipt) -> dict[str, object]:
    K, E, G, C, Y = sp.symbols("K E G C Y", positive=True, finite=True)
    H, J = sp.symbols("H J", real=True, finite=True)
    lam = sp.symbols("lambda", real=True, finite=True)
    lambda_b = H / (2 * K)
    residual = 2 * E - 2 * lam * H + 2 * K * lam**2
    residual_minimum = 2 * E - H**2 / (2 * K)
    variance_b = K * E - H**2 / 4
    residual_gradient = 2 * G - 2 * lambda_b * J + 2 * E * lambda_b**2
    dissipation_b = 2 * K * G + 2 * E**2 - H * J

    book.exact(
        "Beltrami residual square completion",
        residual,
        residual_minimum + 2 * K * (lam - lambda_b) ** 2,
    )
    book.exact("Beltrami residual stationary coefficient", sp.diff(residual, lam).subs(lam, lambda_b), 0)
    book.exact("helical variance residual identity", variance_b, K * residual_minimum / 2)
    book.exact(
        "helical dissipation residual identity",
        dissipation_b,
        E * residual_minimum + K * residual_gradient,
    )

    M0, M1, M2, M3, M4 = sp.symbols("M0 M1 M2 M3 M4", real=True)
    pair_variance = (2 * M0 * M2 - 2 * M1**2) / 8
    pair_dissipation = (2 * M0 * M4 + 2 * M2**2 - 4 * M1 * M3) / 4
    substitutions = {M0: 2 * K, M1: H, M2: 2 * E, M3: J, M4: 2 * G}
    book.exact("signed pair variance expansion", pair_variance.subs(substitutions), variance_b)
    book.exact("signed pair dissipation expansion", pair_dissipation.subs(substitutions), dissipation_b)

    plus_c, minus_c, plus_y, minus_y = sp.symbols(
        "C_plus C_minus Y_plus Y_minus", nonnegative=True, finite=True
    )
    signed_h = plus_c - minus_c
    radial_c = plus_c + minus_c
    signed_j = plus_y - minus_y
    radial_y = plus_y + minus_y
    variance_radial = K * E - radial_c**2 / 4
    dissipation_radial = 2 * K * G + 2 * E**2 - radial_c * radial_y
    book.exact(
        "opposite-helicity variance split",
        (K * E - signed_h**2 / 4) - variance_radial,
        plus_c * minus_c,
    )
    book.exact(
        "opposite-helicity dissipation split",
        (2 * K * G + 2 * E**2 - signed_h * signed_j) - dissipation_radial,
        2 * (plus_c * minus_y + minus_c * plus_y),
    )

    nu = sp.symbols("nu", positive=True, finite=True)
    nonlinear_a, transfer_f = sp.symbols("A F", real=True, finite=True)
    k_dot = -2 * nu * E
    e_dot = nonlinear_a - 2 * nu * G
    h_dot = -2 * nu * J
    c_dot = 2 * transfer_f - 2 * nu * Y
    variance_b_dot = sp.diff(K * E - H**2 / 4, K) * k_dot
    variance_b_dot += sp.diff(K * E - H**2 / 4, E) * e_dot
    variance_b_dot += sp.diff(K * E - H**2 / 4, H) * h_dot
    book.exact(
        "helical variance evolution budget",
        variance_b_dot + nu * dissipation_b,
        K * nonlinear_a,
    )
    mixing = (C**2 - H**2) / 4
    mixing_dot = sp.diff(mixing, C) * c_dot + sp.diff(mixing, H) * h_dot
    book.exact(
        "opposite-helicity mixing evolution budget",
        mixing_dot,
        C * transfer_f - nu * (C * Y - H * J),
    )

    c_b, residual_l3 = sp.symbols("c_B R_B", positive=True, finite=True)
    enstrophy_young = (
        nu * G
        + c_b**2 * E * residual_l3**2 / (2 * nu)
        - c_b * sp.sqrt(2 * E * G) * residual_l3
    )
    enstrophy_square = (
        sp.sqrt(nu * G)
        - c_b * sp.sqrt(2 * E) * residual_l3 / (2 * sp.sqrt(nu))
    ) ** 2
    book.exact("enstrophy Young square", enstrophy_young, enstrophy_square)

    Q = sp.symbols("Q", positive=True, finite=True)
    production_young = (
        nu * Q / 2
        + c_b**2 * K * E * residual_l3**2 / nu
        - c_b * sp.sqrt(2 * K * E * Q) * residual_l3
    )
    production_square = (
        sp.sqrt(nu * Q / 2)
        - c_b * sp.sqrt(2 * K * E) * residual_l3 / sp.sqrt(2 * nu)
    ) ** 2
    book.exact("radial production Young square", production_young, production_square)

    I, K0, E0, V0 = sp.symbols("I K0 E0 V0", positive=True, finite=True)
    enstrophy_bound = E0 * sp.exp(c_b**2 * I / (2 * nu))
    integrated_source = c_b**2 * K0 * enstrophy_bound * I / nu
    positive_production_bound = V0 + 2 * integrated_source
    book.exact(
        "integrated positive-production coefficient",
        positive_production_bound - V0,
        2 * c_b**2 * K0 * E0 * I * sp.exp(c_b**2 * I / (2 * nu)) / nu,
    )

    scaling = {
        "K": -1,
        "E": 1,
        "G": 3,
        "H": 0,
        "J": 2,
        "lambda_B": 1,
        "r_amplitude": 2,
        "r_L3": 1,
        "dt": -2,
        "I_B": 0,
        "V_B": 0,
        "Q_B": 2,
        "A": 3,
    }
    book.exact("Beltrami coefficient scaling exponent", scaling["H"] - scaling["K"], scaling["lambda_B"])
    book.exact("Beltrami residual integral scaling exponent", 2 * scaling["r_L3"] + scaling["dt"], scaling["I_B"])
    book.exact("helical variance scaling exponent", scaling["K"] + scaling["E"], scaling["V_B"])
    book.exact("helical dissipation scaling exponent", scaling["K"] + scaling["G"], scaling["Q_B"])
    book.exact("helical production scaling exponent", scaling["K"] + scaling["A"], scaling["Q_B"])

    return {
        "lambda_B": lambda_b,
        "D_B": residual_minimum,
        "D_B1": residual_gradient,
        "V_B": variance_b,
        "Q_B": dissipation_b,
        "scaling_exponents": scaling,
    }


def verify_atomic_measure(book: Receipt) -> dict[str, object]:
    supports = tuple(map(sp.Integer, (-3, -1, 2, 5)))
    weights = (
        sp.Rational(1, 10),
        sp.Rational(1, 5),
        sp.Rational(3, 10),
        sp.Rational(2, 5),
    )
    moments = signed_moments(supports, weights)
    K = moments[0] / 2
    H = moments[1]
    E = moments[2] / 2
    J = moments[3]
    G = moments[4] / 2
    radial_c = sum(weight * abs(support) for support, weight in zip(supports, weights))
    radial_y = sum(weight * abs(support) ** 3 for support, weight in zip(supports, weights))
    plus_c = sum(weight * support for support, weight in zip(supports, weights) if support > 0)
    minus_c = sum(-weight * support for support, weight in zip(supports, weights) if support < 0)
    plus_y = sum(weight * support**3 for support, weight in zip(supports, weights) if support > 0)
    minus_y = sum(-weight * support**3 for support, weight in zip(supports, weights) if support < 0)
    variance_b = sp.simplify(K * E - H**2 / 4)
    dissipation_b = sp.simplify(2 * K * G + 2 * E**2 - H * J)
    variance_radial = sp.simplify(K * E - radial_c**2 / 4)
    dissipation_radial = sp.simplify(2 * K * G + 2 * E**2 - radial_c * radial_y)
    pair_variance, pair_dissipation = pair_spread(supports, weights)
    lambda_b = H / (2 * K)
    residual = sum(
        weight * (support - lambda_b) ** 2
        for support, weight in zip(supports, weights)
    )
    residual_gradient = sum(
        weight * support**2 * (support - lambda_b) ** 2
        for support, weight in zip(supports, weights)
    )

    book.exact("fixed atom total mass", sum(weights), 1)
    book.check("fixed atom positive weights", all(weight > 0 for weight in weights), weights)
    book.exact("fixed atom signed first moment", H, plus_c - minus_c)
    book.exact("fixed atom radial first moment", radial_c, plus_c + minus_c)
    book.exact("fixed atom signed third moment", J, plus_y - minus_y)
    book.exact("fixed atom radial third moment", radial_y, plus_y + minus_y)
    book.exact("fixed atom helical pair variance", pair_variance, variance_b)
    book.exact("fixed atom helical pair dissipation", pair_dissipation, dissipation_b)
    book.exact("fixed atom residual variance", residual, 2 * variance_b / K)
    book.exact("fixed atom residual dissipation", E * residual + K * residual_gradient, dissipation_b)
    book.exact("fixed atom radial-helical variance difference", variance_b - variance_radial, plus_c * minus_c)
    book.exact(
        "fixed atom radial-helical dissipation difference",
        dissipation_b - dissipation_radial,
        2 * (plus_c * minus_y + minus_c * plus_y),
    )
    book.check("fixed atom positive helical variance", variance_b > 0, variance_b)
    book.check("fixed atom positive helical dissipation", dissipation_b > 0, dissipation_b)

    shell_supports = (sp.Integer(-2), sp.Integer(2))
    shell_weights = (sp.Rational(1, 3), sp.Rational(2, 3))
    shell_moments = signed_moments(shell_supports, shell_weights)
    shell_k = shell_moments[0] / 2
    shell_e = shell_moments[2] / 2
    shell_h = shell_moments[1]
    shell_c = sum(
        weight * abs(support)
        for support, weight in zip(shell_supports, shell_weights)
    )
    shell_v = sp.simplify(shell_k * shell_e - shell_c**2 / 4)
    shell_vb = sp.simplify(shell_k * shell_e - shell_h**2 / 4)
    book.exact("mixed-helicity shell zero radial spread", shell_v, 0)
    book.check("mixed-helicity shell positive helical spread", shell_vb > 0, shell_vb)

    return {
        "supports": supports,
        "weights": weights,
        "moments": moments,
        "radial_moments": {1: radial_c, 3: radial_y},
        "V": variance_radial,
        "V_B": variance_b,
        "Q": dissipation_radial,
        "Q_B": dissipation_b,
        "lambda_B": lambda_b,
        "mixed_shell": {"V": shell_v, "V_B": shell_vb},
    }


def verify_periodic_controls(book: Receipt) -> dict[str, object]:
    x, y, z, t = sp.symbols("x y z t", real=True)
    coordinates = (x, y, z)
    amplitude, nu = sp.symbols("a nu", positive=True, finite=True)
    n = sp.symbols("n", integer=True, positive=True)
    heat_amplitude = amplitude * sp.exp(-nu * n**2 * t)

    beltrami = heat_amplitude * sp.Matrix([sp.sin(n * z), sp.cos(n * z), 0])
    beltrami_quantities = field_quantities(
        beltrami, coordinates, n * beltrami, n**3 * beltrami
    )
    beltrami_omega = beltrami_quantities["vorticity"]
    beltrami_convection = beltrami_quantities["gradient"] * beltrami
    beltrami_pde = sp.diff(beltrami, t) - nu * laplacian(beltrami, coordinates)
    beltrami_divergence = sp.simplify(
        sum(sp.diff(beltrami[index], coordinates[index]) for index in range(3))
    )
    book.exact("Beltrami heat flow divergence free", beltrami_divergence, 0)
    book.check("Beltrami heat flow curl eigenfield", all(sp.simplify(value) == 0 for value in beltrami_omega - n * beltrami), beltrami_omega)
    book.check("Beltrami heat flow zero convection", all(sp.simplify(value) == 0 for value in beltrami_convection), beltrami_convection)
    book.check("Beltrami heat flow PDE", all(sp.simplify(value) == 0 for value in beltrami_pde), beltrami_pde)
    beltrami_v = sp.simplify(beltrami_quantities["K"] * beltrami_quantities["E"] - beltrami_quantities["C"] ** 2 / 4)
    beltrami_vb = sp.simplify(beltrami_quantities["K"] * beltrami_quantities["E"] - beltrami_quantities["H"] ** 2 / 4)
    beltrami_q = sp.simplify(2 * beltrami_quantities["K"] * beltrami_quantities["G"] + 2 * beltrami_quantities["E"] ** 2 - beltrami_quantities["C"] * beltrami_quantities["Y"])
    beltrami_qb = sp.simplify(2 * beltrami_quantities["K"] * beltrami_quantities["G"] + 2 * beltrami_quantities["E"] ** 2 - beltrami_quantities["H"] * beltrami_quantities["J"])
    for label, value in (("radial spread", beltrami_v), ("helical spread", beltrami_vb), ("radial dissipation", beltrami_q), ("helical dissipation", beltrami_qb)):
        book.exact(f"Beltrami heat flow zero {label}", value, 0)

    shear = heat_amplitude * sp.Matrix([sp.sin(n * y), 0, 0])
    shear_quantities = field_quantities(shear, coordinates, n * shear, n**3 * shear)
    shear_convection = shear_quantities["gradient"] * shear
    shear_pde = sp.diff(shear, t) - nu * laplacian(shear, coordinates)
    book.check("shear heat flow divergence free", sp.simplify(sum(sp.diff(shear[index], coordinates[index]) for index in range(3))) == 0, shear)
    book.check("shear heat flow zero convection", all(sp.simplify(value) == 0 for value in shear_convection), shear_convection)
    book.check("shear heat flow PDE", all(sp.simplify(value) == 0 for value in shear_pde), shear_pde)
    shear_v = sp.simplify(shear_quantities["K"] * shear_quantities["E"] - shear_quantities["C"] ** 2 / 4)
    shear_vb = sp.simplify(shear_quantities["K"] * shear_quantities["E"] - shear_quantities["H"] ** 2 / 4)
    shear_q = sp.simplify(2 * shear_quantities["K"] * shear_quantities["G"] + 2 * shear_quantities["E"] ** 2 - shear_quantities["C"] * shear_quantities["Y"])
    shear_qb = sp.simplify(2 * shear_quantities["K"] * shear_quantities["G"] + 2 * shear_quantities["E"] ** 2 - shear_quantities["H"] * shear_quantities["J"])
    book.exact("shear heat flow zero helicity", shear_quantities["H"], 0)
    book.exact("shear heat flow zero helicity dissipation", shear_quantities["J"], 0)
    book.exact("shear heat flow zero radial spread", shear_v, 0)
    book.exact("shear heat flow zero radial dissipation", shear_q, 0)
    expected_shear_vb = amplitude**4 * n**2 * sp.exp(-4 * nu * n**2 * t) / 16
    book.exact("shear heat flow helical spread", shear_vb, expected_shear_vb)
    book.exact("shear heat flow helical dissipation", shear_qb, 4 * n**2 * shear_vb)

    triad = (
        sp.Matrix([0, 1, 1]) * sp.cos(x)
        + sp.Matrix([1, 0, 1]) * sp.cos(y)
        + sp.Matrix([1, -1, 1]) * sp.sin(x + y)
    )
    triad_lambda = (
        sp.Matrix([0, 1, 1]) * sp.cos(x)
        + sp.Matrix([1, 0, 1]) * sp.cos(y)
        + sp.sqrt(2) * sp.Matrix([1, -1, 1]) * sp.sin(x + y)
    )
    triad_lambda_cubed = (
        sp.Matrix([0, 1, 1]) * sp.cos(x)
        + sp.Matrix([1, 0, 1]) * sp.cos(y)
        + 2 * sp.sqrt(2) * sp.Matrix([1, -1, 1]) * sp.sin(x + y)
    )
    triad_quantities = field_quantities(
        triad, coordinates, triad_lambda, triad_lambda_cubed
    )
    triad_divergence = sp.simplify(
        sum(sp.diff(triad[index], coordinates[index]) for index in range(3))
    )
    expected = {
        "K": sp.Rational(7, 4),
        "E": sp.Rational(5, 2),
        "G": sp.Integer(4),
        "C": 2 + 3 * sp.sqrt(2) / 2,
        "Y": 2 + 3 * sp.sqrt(2),
        "H": sp.Integer(0),
        "J": sp.Integer(0),
        "A": sp.Rational(1, 2),
        "u_S_omega": sp.Integer(0),
    }
    book.exact("triad divergence", triad_divergence, 0)
    for key, target in expected.items():
        book.exact(f"triad {key}", triad_quantities[key], target)
    lambda_test = sp.symbols("lambda_test", real=True, finite=True)
    residual_work = normalized_torus_average(
        (
            (triad_quantities["vorticity"] - lambda_test * triad).T
            * triad_quantities["strain"]
            * triad_quantities["vorticity"]
        )[0],
        coordinates,
    )
    book.exact("triad residual stretching identity", residual_work, expected["A"])
    for fixed_lambda in (sp.Integer(-2), sp.Rational(3, 5)):
        book.exact(
            f"triad residual stretching lambda {fixed_lambda}",
            residual_work.subs(lambda_test, fixed_lambda),
            expected["A"],
        )
    triad_convection = triad_quantities["gradient"] * triad
    triad_lambda_squared = -laplacian(triad, coordinates)
    nonlinear_enstrophy = normalized_torus_average(
        triad_lambda_squared.dot(-triad_convection), coordinates
    )
    book.exact("triad convection and stretching production agree", nonlinear_enstrophy, expected["A"])

    return {
        "Beltrami": {key: value for key, value in beltrami_quantities.items() if isinstance(value, sp.Expr)},
        "shear": {key: value for key, value in shear_quantities.items() if isinstance(value, sp.Expr)},
        "triad": {key: value for key, value in triad_quantities.items() if isinstance(value, sp.Expr)},
        "triad_residual_work": residual_work,
    }


def verify_phase_geometry(book: Receipt) -> dict[str, object]:
    c = sp.symbols("c", positive=True, finite=True)
    theta_gradient, alpha_gradient, c_gradient = sp.symbols(
        "theta_gradient alpha_gradient c_gradient", real=True, finite=True
    )
    connection = theta_gradient + c * alpha_gradient
    weighted_phase = c * (theta_gradient + alpha_gradient) ** 2 + (1 - c) * theta_gradient**2
    projective_coordinate = c_gradient**2 / (4 * c * (1 - c)) + c * (1 - c) * alpha_gradient**2
    spinor_coordinate = weighted_phase + c_gradient**2 / (4 * c * (1 - c))
    book.exact(
        "doublet phase variance decomposition",
        weighted_phase,
        connection**2 + c * (1 - c) * alpha_gradient**2,
    )
    book.exact(
        "doublet gradient connection decomposition",
        spinor_coordinate,
        connection**2 + projective_coordinate,
    )

    beta, alpha = sp.symbols("beta alpha", real=True, finite=True)
    beta_j, beta_k, alpha_j, alpha_k = sp.symbols(
        "beta_j beta_k alpha_j alpha_k", real=True, finite=True
    )
    bloch = sp.Matrix(
        [sp.sin(beta) * sp.cos(alpha), -sp.sin(beta) * sp.sin(alpha), sp.cos(beta)]
    )
    bloch_beta = bloch.diff(beta)
    bloch_alpha = bloch.diff(alpha)
    derivative_j = bloch_beta * beta_j + bloch_alpha * alpha_j
    derivative_k = bloch_beta * beta_k + bloch_alpha * alpha_k
    pullback = sp.trigsimp(bloch.dot(derivative_j.cross(derivative_k)))
    expected_pullback = -sp.sin(beta) * (beta_j * alpha_k - beta_k * alpha_j)
    curvature = (
        -sp.sin(beta) * beta_j * alpha_k / 2
        + sp.sin(beta) * beta_k * alpha_j / 2
    )
    book.exact("Bloch pullback orientation", pullback, expected_pullback)
    book.exact("Berry curvature half-pullback identity", curvature, pullback / 2)

    sigma_one, sigma_two, kappa = sp.symbols(
        "sigma_one sigma_two kappa", nonnegative=True, finite=True
    )
    mermin_ho_slack = kappa * (sigma_one**2 + sigma_two**2) / 4 - kappa * sigma_one * sigma_two / 2
    book.exact(
        "Mermin-Ho singular-value square",
        mermin_ho_slack,
        kappa * (sigma_one - sigma_two) ** 2 / 4,
    )

    x, y, z = sp.symbols("x y z", real=True)
    coordinates = (x, y, z)
    delta = sp.Rational(1, 4)
    radius_squared = x**2 + y**2 + z**2
    profile_a = delta * sp.exp(-radius_squared)
    profile_b = x * sp.exp(-radius_squared)
    cross_gradient = sp.simplify(
        sp.Matrix([sp.diff(profile_a, coordinate) for coordinate in coordinates]).cross(
            sp.Matrix([sp.diff(profile_b, coordinate) for coordinate in coordinates])
        )
    )
    reduced_cross = sp.simplify(cross_gradient / sp.exp(-2 * radius_squared))
    expected_cross = sp.Matrix([0, -2 * delta * z, 2 * delta * y])
    book.check(
        "Gaussian phase cross-gradient",
        all(sp.simplify(value) == 0 for value in reduced_cross - expected_cross),
        reduced_cross,
    )
    cross_polynomial = sp.expand(sum(component**2 for component in expected_cross))
    cross_integral = gaussian_polynomial_integral(cross_polynomial, sp.Integer(4), coordinates)
    expected_integral = delta**2 * sp.pi ** sp.Rational(3, 2) / 8
    book.exact("Gaussian phase cross-gradient integral", cross_integral, expected_integral)
    book.check("Gaussian composition remains positive", sp.Rational(1, 2) > 0 and sp.Rational(1, 2) + delta < 1, {"minimum": sp.Rational(1, 2), "maximum": sp.Rational(1, 2) + delta})

    theta_function = sp.Function("theta")(*coordinates)
    c_function = sp.Function("c")(*coordinates)
    alpha_function = sp.Function("alpha")(*coordinates)
    grad_theta = sp.Matrix([sp.diff(theta_function, coordinate) for coordinate in coordinates])
    grad_c = sp.Matrix([sp.diff(c_function, coordinate) for coordinate in coordinates])
    grad_alpha = sp.Matrix([sp.diff(alpha_function, coordinate) for coordinate in coordinates])
    chart_vorticity = grad_c.cross(grad_alpha)
    chart_connection = grad_theta + c_function * grad_alpha
    helicity_density = sp.expand(chart_connection.dot(chart_vorticity))
    boundary_density = sum(
        sp.diff(theta_function * chart_vorticity[index], coordinates[index])
        for index in range(3)
    )
    divergence_vorticity = sum(
        sp.diff(chart_vorticity[index], coordinates[index]) for index in range(3)
    )
    book.exact("positive-chart vorticity divergence", divergence_vorticity, 0)
    book.exact("positive-chart helicity boundary identity", helicity_density, boundary_density)

    epsilon, P0, P1, omega0, residual3 = sp.symbols(
        "epsilon P0 P1 omega0 residual3", positive=True, finite=True
    )
    phase_energy = P0 + epsilon * P1
    vorticity_l2_squared = omega0 / epsilon**2
    residual_l3_squared = residual3 / epsilon**3
    book.exact("concentrating family connection-energy exponent", sp.Integer(1) - 2 * sp.Rational(1, 2), 0)
    book.exact("concentrating family composition-energy exponent", 3 - 2, 1)
    book.exact("concentrating family enstrophy exponent", 3 - 2 * (1 + sp.Rational(3, 2)), -2)
    book.exact("concentrating family residual L3-squared exponent", 2 * (1 + sp.Rational(3, 2) - 1), 3)
    book.exact("concentrating family bounded phase energy", sp.limit(phase_energy, epsilon, 0, dir="+"), P0)
    book.check("concentrating family enstrophy diverges", sp.limit(vorticity_l2_squared, epsilon, 0, dir="+") == sp.oo, {"power": -2})
    book.check("concentrating family residual L3 diverges", sp.limit(residual_l3_squared, epsilon, 0, dir="+") == sp.oo, {"power": -3})
    kappa_symbol = sp.symbols("kappa", positive=True, finite=True)
    book.exact(
        "concentrating family exact enstrophy coefficient",
        kappa_symbol**2 * cross_integral / epsilon**2,
        kappa_symbol**2 * delta**2 * sp.pi ** sp.Rational(3, 2) / (8 * epsilon**2),
    )

    return {
        "Bloch_pullback": pullback,
        "Berry_curvature": curvature,
        "cross_gradient": cross_gradient,
        "cross_integral": cross_integral,
        "phase_energy_scaling": phase_energy,
        "vorticity_L2_squared_scaling": vorticity_l2_squared,
        "residual_L3_squared_scaling": residual_l3_squared,
    }


def compute() -> dict[str, object]:
    book = Receipt()
    moment_results = verify_moment_identities(book)
    atom_results = verify_atomic_measure(book)
    periodic_results = verify_periodic_controls(book)
    phase_results = verify_phase_geometry(book)

    book.check(
        "all direct expressions finite",
        not book.nonfinite_values,
        {"nonfinite_checks": book.nonfinite_values},
    )

    success = not book.failures
    return {
        "schema": "cassi.navier-stokes.helical-spread.verification.v1",
        "status": "PASS" if success else "FAIL",
        "classification": {
            "helical_spread_and_residual_criterion": (
                "DERIVED CONDITIONAL REDUCTION" if success else "INCONCLUSIVE"
            ),
            "first_order_phase_energy_coercivity": (
                "CONTRADICTS" if success else "INCONCLUSIVE"
            ),
            "arbitrary_data_residual_bound": "UNRESOLVED",
            "full_bubble_dynamic_exclusion": "UNRESOLVED",
            "global_regularity": "UNRESOLVED",
            "singular_trajectory": "NOT RUN",
        },
        "scope": {
            "equation": "original unforced 3-D incompressible Navier-Stokes",
            "trajectory_search": "NOT RUN",
            "parameter_search": "NOT RUN",
            "phase_family": "smooth one-band kinematic initial data on R^3",
            "literature_priority": "NOT ASSESSED",
        },
        "check_count": len(book.checks),
        "failure_count": len(book.failures),
        "failures": book.failures,
        "checks": book.checks,
        "moment_identities": json_safe(moment_results),
        "fixed_atomic_measure": json_safe(atom_results),
        "periodic_controls": json_safe(periodic_results),
        "phase_geometry": json_safe(phase_results),
        "versions": {
            "python": __import__("sys").version,
            "sympy": sp.__version__,
        },
    }


def snapshot_sources(output: Path) -> tuple[Path, list[dict[str, str]]]:
    snapshot_root = output.parent / f"{output.stem}.sources"
    if snapshot_root.exists():
        raise FileExistsError(f"Source snapshot directory already exists: {snapshot_root}")
    snapshots: list[dict[str, str]] = []
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        snapshots.append(
            {
                "path": relative,
                "sha256": sha256(source),
                "snapshot": destination.relative_to(ROOT).as_posix(),
                "snapshot_sha256": sha256(destination),
            }
        )
    return snapshot_root, snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite retained receipt: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    result = compute()
    created_utc = datetime.now(timezone.utc).isoformat()
    result["created_utc"] = created_utc
    snapshot_root, snapshots = snapshot_sources(output)
    manifest = output.with_suffix(".inputs.json")
    if manifest.exists():
        raise FileExistsError(f"Refusing to overwrite retained manifest: {manifest}")
    manifest_payload = {
        "schema": "cassi.navier-stokes.helical-spread.inputs.v1",
        "created_utc": created_utc,
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "sources": snapshots,
    }
    manifest.write_text(
        json.dumps(json_safe(manifest_payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result["input_manifest"] = {
        "path": manifest.relative_to(ROOT).as_posix(),
        "sha256": sha256(manifest),
    }
    result["sources"] = snapshots
    result["source_snapshot_root"] = snapshot_root.relative_to(ROOT).as_posix()
    output.write_text(
        json.dumps(json_safe(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Receipt: {output}")
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("status", "classification", "check_count", "failure_count")
            },
            indent=2,
        )
    )
    if result["status"] == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    print("FAILED CHECKS: " + ", ".join(result["failures"]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
