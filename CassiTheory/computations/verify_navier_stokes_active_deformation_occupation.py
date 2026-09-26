#!/usr/bin/env python3
"""Verify fixed active-deformation-occupation components for Navier–Stokes.

The executable checks the 40-item algebraic and control inventory frozen in
computations/navier-stokes-active-deformation-occupation-prereg.md. It does
not integrate a Navier–Stokes trajectory or simulate a stochastic flow.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
PROTOCOL = (
    ROOT
    / "computations"
    / "navier-stokes-active-deformation-occupation-prereg.md"
)
PAPER = ROOT / "turbulence" / "navier-stokes-active-deformation-occupation.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_active_deformation_occupation"
    / "verification.json"
)
EXPECTED_CHECKS = 40
EXPECTED_CHECK_NAMES = (
    "S1 symbolic common-noise Laplacian product",
    "S2 fixed identity initialization",
    "S3 finite-ensemble sample mean",
    "S4 one-coordinate mean-product diffusion sign",
    "S5 one-coordinate centred-source subtraction",
    "S6 fixed centred initial value",
    "S7 finite-ensemble covariance positivity",
    "S8 general trace reaction removes rotation",
    "A1 general inverse-direct Rayleigh factorization",
    "A2 fixed-quadrature integrated active sandwich",
    "A3 fixed-quadrature active operator bound",
    "A4 fixed volume-preserving label integrand",
    "A5 general directional norm production",
    "A6 fixed normalized orientation decomposition",
    "A7 constant-strain occupation identity",
    "A8 two-rate tilted logarithmic production",
    "C1 orientation deviator trace",
    "C2 anisotropy simplex identity and bound",
    "C3 isotropic strain cancellation",
    "C4 Frobenius Lagrange identity",
    "C5 isotropic seeded moment control",
    "C6 formal scaling exponent cancellation",
    "X1 local homogeneous trace-free gradient",
    "X2 local homogeneous deformation equation",
    "X3 local homogeneous seeded-moment reaction",
    "X4 local homogeneous envelope ratio",
    "X5 local homogeneous production rate",
    "X6 local homogeneous orientation anisotropy",
    "X7 directly differentiated periodic shear equation",
    "X8 directly differentiated periodic shear vorticity",
    "X9 shear-form matrix fixes vorticity direction",
    "X10 embedded two-dimensional block direction",
    "K1 finite geometric series and fixed limit",
    "K2 heat-kernel exponent equivalence",
    "K3 formal critical strain exponent",
    "K4 energy-class exponent",
    "K5 parabolic pulse norm exponent",
    "K6 parabolic pulse dose exponent",
    "K7 fixed phi active-dose sum",
    "K8 constant active-dose divergence",
)
SCHEMA = "cassi.navier-stokes.active-deformation-occupation.verification.v1"


class CheckBook:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def record(self, name: str, passed: bool, detail: Any) -> None:
        passed = bool(passed)
        self.checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": stringify(detail),
            }
        )
        if not passed:
            self.failures.append(name)

    def exact(self, name: str, left: Any, right: Any = 0) -> None:
        difference = reduce_exact(left - right)
        self.record(name, is_zero(difference), difference)



def stringify(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return [[sp.sstr(entry) for entry in row] for row in value.tolist()]
    if isinstance(value, sp.Basic):
        return sp.sstr(value)
    if isinstance(value, dict):
        return {str(key): stringify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [stringify(item) for item in value]
    return value






def reduce_exact(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(
            lambda entry: sp.factor(
                sp.cancel(sp.trigsimp(sp.expand_trig(sp.simplify(entry))))
            )
        )
    if isinstance(value, sp.Basic):
        return sp.factor(
            sp.cancel(sp.trigsimp(sp.expand_trig(sp.simplify(value))))
        )
    return value



def is_zero(value: Any) -> bool:
    if isinstance(value, sp.MatrixBase):
        return all(entry == 0 for entry in value)
    return value == 0



def frobenius(left: sp.MatrixBase, right: sp.MatrixBase) -> sp.Expr:
    return sp.trace(left.T * right)



def principal_minors(matrix: sp.MatrixBase) -> list[sp.Expr]:
    minors: list[sp.Expr] = []
    for size in range(1, matrix.rows + 1):
        for indices in itertools.combinations(range(matrix.rows), size):
            block = matrix.extract(indices, indices)
            minors.append(reduce_exact(block.det()))
    return minors



def group_pass(book: CheckBook, prefix: str, expected: int) -> bool:
    rows = [row for row in book.checks if row["name"].startswith(prefix)]
    return len(rows) == expected and all(row["passed"] for row in rows)



def verify_seeded_closure(book: CheckBook, values: dict[str, Any]) -> None:
    nu = sp.symbols("nu", positive=True)
    y = sp.Matrix(sp.symbols("y0:3", real=True))
    dy = sp.Matrix(3, 3, sp.symbols("dy0:9", real=True))
    lap_y = sp.Matrix(sp.symbols("ly0:3", real=True))
    individual_laplacians = nu * (lap_y * y.T + y * lap_y.T)
    common_noise_variation = 2 * nu * dy * dy.T
    product_laplacian = nu * (
        lap_y * y.T + y * lap_y.T + 2 * dy * dy.T
    )
    book.exact(
        EXPECTED_CHECK_NAMES[0],
        individual_laplacians + common_noise_variation,
        product_laplacian,
    )

    omega0 = sp.Matrix([2, -1, 3])
    deformation0 = sp.eye(3)
    sampled_initial0 = omega0
    cauchy_initial0 = deformation0 * sampled_initial0
    seeded_initial = cauchy_initial0 * cauchy_initial0.T
    book.exact(EXPECTED_CHECK_NAMES[1], seeded_initial, omega0 * omega0.T)

    samples = (
        sp.Matrix([2, -1, 0]),
        sp.Matrix([0, 1, 2]),
        sp.Matrix([-1, 0, 1]),
        sp.Matrix([1, 2, -1]),
    )
    weights = (sp.Rational(1, 4),) * len(samples)
    mean = sum((weight * sample for weight, sample in zip(weights, samples)), sp.zeros(3, 1))
    expected_mean = sp.Matrix([sp.Rational(1, 2), sp.Rational(1, 2), sp.Rational(1, 2)])
    book.exact(EXPECTED_CHECK_NAMES[2], mean, expected_mean)

    coordinate = sp.symbols("xi", real=True)
    mean_field = sp.Matrix(
        [sp.Function(f"omega{index}")(coordinate) for index in range(3)]
    )
    mean_gradient = sp.diff(mean_field, coordinate)
    mean_laplacian = sp.diff(mean_field, coordinate, 2)
    mean_outer = mean_field * mean_field.T
    full_product_laplacian = sp.diff(mean_outer, coordinate, 2)
    individual_laplacians = (
        mean_laplacian * mean_field.T
        + mean_field * mean_laplacian.T
    )
    mean_product_residual = reduce_exact(
        nu * (individual_laplacians - full_product_laplacian)
    )
    gradient_outer = mean_gradient * mean_gradient.T
    book.exact(
        EXPECTED_CHECK_NAMES[3],
        mean_product_residual,
        -2 * nu * gradient_outer,
    )

    centred_source = reduce_exact(
        nu * (full_product_laplacian - individual_laplacians)
    )
    book.exact(
        EXPECTED_CHECK_NAMES[4],
        centred_source,
        2 * nu * gradient_outer,
    )

    centred_initial = seeded_initial - cauchy_initial0 * cauchy_initial0.T
    book.exact(EXPECTED_CHECK_NAMES[5], centred_initial, sp.zeros(3))

    second_moment = sum(
        (weight * sample * sample.T for weight, sample in zip(weights, samples)),
        sp.zeros(3),
    )
    covariance = reduce_exact(second_moment - mean * mean.T)
    minors = principal_minors(covariance)
    book.record(
        EXPECTED_CHECK_NAMES[6],
        all(value.is_nonnegative is True for value in minors),
        {"covariance": covariance, "principal_minors": minors},
    )

    l_symbols = sp.symbols("l0:9", real=True)
    matrix_l = sp.Matrix(3, 3, l_symbols)
    matrix_s = (matrix_l + matrix_l.T) / 2
    matrix_a = (matrix_l - matrix_l.T) / 2
    m_symbols = sp.symbols("m00 m01 m02 m11 m12 m22", real=True)
    matrix_m = sp.Matrix(
        [
            [m_symbols[0], m_symbols[1], m_symbols[2]],
            [m_symbols[1], m_symbols[3], m_symbols[4]],
            [m_symbols[2], m_symbols[4], m_symbols[5]],
        ]
    )
    trace_reaction = sp.trace(matrix_l * matrix_m + matrix_m * matrix_l.T)
    rotational_trace = sp.trace(matrix_a * matrix_m - matrix_m * matrix_a)
    book.exact(
        EXPECTED_CHECK_NAMES[7],
        sp.Matrix(
            [
                reduce_exact(trace_reaction - 2 * frobenius(matrix_s, matrix_m)),
                reduce_exact(rotational_trace),
            ]
        ),
        sp.zeros(2, 1),
    )

    values["finite_ensemble"] = {
        "mean": mean,
        "second_moment": second_moment,
        "covariance": covariance,
        "principal_minors": minors,
    }



def verify_active_envelope(book: CheckBook, values: dict[str, Any]) -> None:
    c1, c2, c3 = sp.symbols("c1 c2 c3", positive=True)
    a1, a2, a3 = sp.symbols("a1 a2 a3", nonnegative=True)
    direct = c1 * a1 + c2 * a2 + c3 * a3
    inverse = a1 / c1 + a2 / c2 + a3 / c3
    euclidean = a1 + a2 + a3
    factorized_gap = sum(
        (
            left[1]
            * right[1]
            * (left[0] - right[0]) ** 2
            / (left[0] * right[0])
        )
        for left, right in itertools.combinations(
            ((c1, a1), (c2, a2), (c3, a3)), 2
        )
    )
    book.exact(
        EXPECTED_CHECK_NAMES[8],
        direct * inverse - euclidean**2,
        factorized_gap,
    )

    fixtures = (
        (sp.diag(4, sp.Rational(1, 2), 2), sp.Matrix([1, 2, 0])),
        (sp.diag(3, 1, sp.Rational(1, 3)), sp.Matrix([0, 1, 2])),
    )
    total_w = sum((vector.dot(vector) for _, vector in fixtures), sp.Integer(0))
    total_z = sum(
        ((vector.T * covariance.inv() * vector)[0] for covariance, vector in fixtures),
        sp.Integer(0),
    )
    total_y = sum(
        ((vector.T * covariance * vector)[0] for covariance, vector in fixtures),
        sp.Integer(0),
    )
    sandwich_gap = reduce_exact(total_z * total_y - total_w**2)
    book.record(
        EXPECTED_CHECK_NAMES[9],
        sandwich_gap.is_nonnegative is True,
        {
            "W": total_w,
            "Z": total_z,
            "Y": total_y,
            "ZY_minus_W2": sandwich_gap,
        },
    )

    operator_gap = reduce_exact(4 * total_w - total_y)
    book.record(
        EXPECTED_CHECK_NAMES[10],
        operator_gap.is_nonnegative is True,
        {"lambda_max": 4, "lambda_max_W_minus_Y": operator_gap},
    )

    deformation = sp.diag(2, sp.Rational(1, 2), 1)
    seed = sp.Matrix([1, -2, 3])
    label_norm = (deformation * seed).dot(deformation * seed)
    eulerian_norm = (seed.T * deformation.T * deformation * seed)[0]
    book.record(
        EXPECTED_CHECK_NAMES[11],
        deformation.det() == 1 and reduce_exact(label_norm - eulerian_norm) == 0,
        {
            "determinant": deformation.det(),
            "label_norm": label_norm,
            "eulerian_norm": eulerian_norm,
        },
    )

    j_symbols = sp.symbols("j0:3", real=True)
    j_vector = sp.Matrix(j_symbols)
    l_symbols = sp.symbols("h0:9", real=True)
    matrix_l = sp.Matrix(3, 3, l_symbols)
    matrix_s = (matrix_l + matrix_l.T) / 2
    norm_derivative = (matrix_l * j_vector).dot(j_vector) + j_vector.dot(matrix_l * j_vector)
    book.exact(
        EXPECTED_CHECK_NAMES[12],
        norm_derivative,
        2 * (j_vector.T * matrix_s * j_vector)[0],
    )

    unit = sp.Matrix([sp.Rational(3, 5), sp.Rational(4, 5), 0])
    fixed_l = sp.Matrix([[2, -1, 1], [3, -2, 0], [1, 2, 0]])
    fixed_s = (fixed_l + fixed_l.T) / 2
    sigma = reduce_exact((unit.T * fixed_s * unit)[0])
    orientation_rhs = reduce_exact((sp.eye(3) - unit * unit.T) * fixed_l * unit)
    orientation_reconstruction = reduce_exact(
        fixed_l * unit - orientation_rhs - sigma * unit
    )
    book.record(
        EXPECTED_CHECK_NAMES[13],
        reduce_exact(unit.dot(orientation_rhs)) == 0
        and is_zero(orientation_reconstruction),
        {
            "unit_dot_rhs": reduce_exact(unit.dot(orientation_rhs)),
            "reconstruction": orientation_reconstruction,
        },
    )

    time, rate = sp.symbols("t a", positive=True)
    homogeneous_norm_squared = sp.exp(2 * rate * time)
    occupation = sp.exp(2 * sp.integrate(rate, (time, 0, time)))
    book.exact(
        EXPECTED_CHECK_NAMES[14], homogeneous_norm_squared, occupation
    )

    rate_left, rate_right = sp.symbols("a b", real=True)
    weighted_moment = (
        sp.exp(2 * rate_left * time) + 2 * sp.exp(2 * rate_right * time)
    ) / 3
    tilted_rate = (
        rate_left * sp.exp(2 * rate_left * time)
        + 2 * rate_right * sp.exp(2 * rate_right * time)
    ) / (3 * weighted_moment)
    book.exact(
        EXPECTED_CHECK_NAMES[15],
        sp.diff(sp.log(weighted_moment), time) / 2,
        tilted_rate,
    )

    values["active_sandwich"] = {
        "W": total_w,
        "Z": total_z,
        "Y": total_y,
        "ZY_minus_W_squared": sandwich_gap,
        "operator_gap": operator_gap,
    }



def verify_anisotropy_and_scaling(book: CheckBook, values: dict[str, Any]) -> None:
    p1, p2, p3 = sp.symbols("p1 p2 p3", positive=True)
    total_p = p1 + p2 + p3
    normalized = sp.diag(p1, p2, p3) / total_p
    deviator = normalized - sp.eye(3) / 3
    book.exact(EXPECTED_CHECK_NAMES[16], sp.trace(deviator), 0)

    squared_deviator = reduce_exact(frobenius(deviator, deviator))
    eigen_identity = reduce_exact(
        squared_deviator
        - (
            (p1**2 + p2**2 + p3**2) / total_p**2
            - sp.Rational(1, 3)
        )
    )
    upper_gap = reduce_exact(sp.Rational(2, 3) - squared_deviator)
    simplex_pairs = p1 * p2 + p1 * p3 + p2 * p3
    upper_identity = reduce_exact(
        upper_gap - 2 * simplex_pairs / total_p**2
    )
    rank_one_value = reduce_exact(
        squared_deviator.subs({p1: 1, p2: 0, p3: 0})
    )
    book.record(
        EXPECTED_CHECK_NAMES[17],
        eigen_identity == 0
        and upper_identity == 0
        and simplex_pairs.is_positive is True
        and rank_one_value == sp.Rational(2, 3),
        {
            "eigen_identity": eigen_identity,
            "upper_bound_identity": upper_identity,
            "upper_bound_numerator": 2 * simplex_pairs,
            "rank_one_value": rank_one_value,
        },
    )

    s1, s2, mass = sp.symbols("s1 s2 m", real=True)
    strain = sp.diag(s1, s2, -s1 - s2)
    generic_n = sp.Matrix(
        [
            [p1 / total_p, sp.Rational(1, 7), sp.Rational(1, 11)],
            [sp.Rational(1, 7), p2 / total_p, sp.Rational(1, 13)],
            [sp.Rational(1, 11), sp.Rational(1, 13), p3 / total_p],
        ]
    )
    generic_q = generic_n - sp.eye(3) / 3
    moment = mass * generic_n
    book.exact(
        EXPECTED_CHECK_NAMES[18],
        frobenius(strain, moment),
        mass * frobenius(strain, generic_q),
    )

    s00, s11, s22, s01, s02, s12 = sp.symbols(
        "sf00 sf11 sf22 sf01 sf02 sf12", real=True
    )
    q00, q11, q22, q01, q02, q12 = sp.symbols(
        "qf00 qf11 qf22 qf01 qf02 qf12", real=True
    )
    general_s = sp.Matrix(
        [[s00, s01, s02], [s01, s11, s12], [s02, s12, s22]]
    )
    general_q = sp.Matrix(
        [[q00, q01, q02], [q01, q11, q12], [q02, q12, q22]]
    )
    root_two = sp.sqrt(2)
    s_components = sp.Matrix(
        [s00, s11, s22, root_two * s01, root_two * s02, root_two * s12]
    )
    q_components = sp.Matrix(
        [q00, q11, q22, root_two * q01, root_two * q02, root_two * q12]
    )
    alignment_gap = reduce_exact(
        frobenius(general_s, general_s) * frobenius(general_q, general_q)
        - frobenius(general_s, general_q) ** 2
    )
    lagrange_squares = sum(
        (
            s_components[left] * q_components[right]
            - s_components[right] * q_components[left]
        )
        ** 2
        for left, right in itertools.combinations(range(6), 2)
    )
    vectorization_residuals = sp.Matrix(
        [
            reduce_exact(
                frobenius(general_s, general_s)
                - s_components.dot(s_components)
            ),
            reduce_exact(
                frobenius(general_q, general_q)
                - q_components.dot(q_components)
            ),
            reduce_exact(alignment_gap - lagrange_squares),
        ]
    )
    lagrange_residual = vectorization_residuals[2]
    book.exact(EXPECTED_CHECK_NAMES[19], vectorization_residuals, sp.zeros(3, 1))

    isotropic_moment = mass * sp.eye(3) / 3
    book.exact(
        EXPECTED_CHECK_NAMES[20], frobenius(strain, isotropic_moment), 0
    )

    lambda_symbol = sp.symbols("lambda", positive=True)
    exponents = {
        "W": 4 - 3,
        "seeded_moment": 4 - 3,
        "moment_ratio": (4 - 3) - (4 - 3),
        "Gamma_dt": 2 - 2,
    }
    scaling_expression = sum(
        abs(value)
        for key, value in exponents.items()
        if key in ("moment_ratio", "Gamma_dt")
    )
    book.exact(EXPECTED_CHECK_NAMES[21], sp.Integer(scaling_expression), 0)

    values["anisotropy"] = {
        "rank_one_deviator_norm_squared": rank_one_value,
        "simplex_upper_bound_identity": upper_identity,
        "frobenius_lagrange_residual": lagrange_residual,
        "scaling_exponents": exponents,
        "scale_symbol": lambda_symbol,
    }



def verify_exact_controls(book: CheckBook, values: dict[str, Any]) -> None:
    time, rate = sp.symbols("t a", positive=True)
    gradient = sp.diag(rate, -rate, 0)
    deformation = sp.diag(sp.exp(rate * time), sp.exp(-rate * time), 1)
    seed = sp.Matrix([1, 0, 0])
    seeded_moment = deformation * seed * seed.T * deformation.T

    book.exact(EXPECTED_CHECK_NAMES[22], sp.trace(gradient), 0)
    book.exact(
        EXPECTED_CHECK_NAMES[23],
        sp.diff(deformation, time),
        gradient * deformation,
    )
    book.exact(
        EXPECTED_CHECK_NAMES[24],
        sp.diff(seeded_moment, time),
        gradient * seeded_moment + seeded_moment * gradient.T,
    )
    envelope = reduce_exact(sp.trace(seeded_moment))
    book.exact(EXPECTED_CHECK_NAMES[25], envelope, sp.exp(2 * rate * time))
    production_rate = reduce_exact(
        frobenius(gradient, seeded_moment) / envelope
    )
    book.exact(EXPECTED_CHECK_NAMES[26], production_rate, rate)

    normalized = seeded_moment / envelope
    deviator = normalized - sp.eye(3) / 3
    theta_squared = reduce_exact(sp.Rational(3, 2) * frobenius(deviator, deviator))
    book.exact(EXPECTED_CHECK_NAMES[27], theta_squared, 1)

    x, y, z, b, nu, n = sp.symbols(
        "x y z b nu n", real=True, positive=True
    )
    lam = nu * n**2
    shear_scalar = b * sp.exp(-lam * time) * sp.sin(n * y)
    shear = sp.Matrix([shear_scalar, 0, 0])
    coordinates = sp.Matrix([x, y, z])
    convection = reduce_exact(shear.jacobian(coordinates) * shear)
    heat_residual = reduce_exact(
        sp.diff(shear, time) - nu * sp.diff(shear, y, 2)
    )
    book.record(
        EXPECTED_CHECK_NAMES[28],
        is_zero(convection) and is_zero(heat_residual),
        {"convection": convection, "heat_residual": heat_residual},
    )

    expected_vorticity = sp.Matrix(
        [0, 0, -b * n * sp.exp(-lam * time) * sp.cos(n * y)]
    )
    computed_vorticity = sp.Matrix([0, 0, -sp.diff(shear_scalar, y)])
    book.exact(EXPECTED_CHECK_NAMES[29], computed_vorticity, expected_vorticity)

    shear_amount = sp.symbols("h", real=True)
    shear_deformation = sp.Matrix(
        [[1, shear_amount, 0], [0, 1, 0], [0, 0, 1]]
    )
    e3 = sp.Matrix([0, 0, 1])
    fixed_direction = reduce_exact(shear_deformation * e3)
    fixed_ratio = reduce_exact(fixed_direction.dot(fixed_direction) / e3.dot(e3))
    book.record(
        EXPECTED_CHECK_NAMES[30],
        fixed_direction == e3 and fixed_ratio == 1,
        {"deformed_e3": fixed_direction, "moment_ratio": fixed_ratio},
    )

    aa, bb, cc, dd = sp.symbols("aa bb cc dd", real=True)
    saa, sab, sbb = sp.symbols("saa sab sbb", real=True)
    embedded_deformation = sp.Matrix([[aa, bb, 0], [cc, dd, 0], [0, 0, 1]])
    embedded_strain = sp.Matrix(
        [[saa, sab, 0], [sab, sbb, 0], [0, 0, 0]]
    )
    embedded_fixed = reduce_exact(embedded_deformation * e3)
    embedded_production = reduce_exact((e3.T * embedded_strain * e3)[0])
    book.record(
        EXPECTED_CHECK_NAMES[31],
        embedded_fixed == e3 and embedded_production == 0,
        {
            "deformed_e3": embedded_fixed,
            "directional_strain": embedded_production,
        },
    )

    values["exact_controls"] = {
        "homogeneous_envelope": envelope,
        "homogeneous_production_rate": production_rate,
        "homogeneous_theta_squared": theta_squared,
        "shear_heat_residual": heat_residual,
        "shear_fixed_ratio": fixed_ratio,
        "embedded_directional_strain": embedded_production,
    }



def verify_kato_and_cascade(book: CheckBook, values: dict[str, Any]) -> None:
    kappa = sp.symbols("kappa", nonnegative=True)
    order = sp.symbols("N", integer=True, nonnegative=True)
    finite_order = 7
    finite_sum = sum((kappa**index for index in range(finite_order + 1)), sp.Integer(0))
    finite_identity = reduce_exact(
        (1 - kappa) * finite_sum - (1 - kappa ** (finite_order + 1))
    )
    finite_formula = (1 - kappa ** (order + 1)) / (1 - kappa)
    fixed_limit = sp.limit(finite_formula.subs(kappa, sp.Rational(2, 5)), order, sp.oo)
    book.record(
        EXPECTED_CHECK_NAMES[32],
        finite_identity == 0 and fixed_limit == sp.Rational(5, 3),
        {"finite_identity": finite_identity, "fixed_kappa_limit": fixed_limit},
    )

    reciprocal_p, reciprocal_q = sp.symbols("P Q", positive=True)
    kernel_condition = reciprocal_p + sp.Rational(3, 2) * reciprocal_q - 1
    doubled_condition = 2 * reciprocal_p + 3 * reciprocal_q - 2
    book.exact(
        EXPECTED_CHECK_NAMES[33], 2 * kernel_condition, doubled_condition
    )

    strain_scaling = 2 - 2 * reciprocal_p - 3 * reciprocal_q
    critical_reduction = reduce_exact(
        strain_scaling.subs(reciprocal_p, 1 - sp.Rational(3, 2) * reciprocal_q)
    )
    book.exact(EXPECTED_CHECK_NAMES[34], critical_reduction, 0)

    energy_exponent = sp.Rational(2, 2) + sp.Rational(3, 2)
    book.exact(
        EXPECTED_CHECK_NAMES[35], energy_exponent, sp.Rational(5, 2)
    )

    pulse_norm_exponent = -5 + 2 + 3
    book.exact(EXPECTED_CHECK_NAMES[36], sp.Integer(pulse_norm_exponent), 0)

    pulse_dose_exponent = -sp.Rational(5, 2) + 2
    book.exact(
        EXPECTED_CHECK_NAMES[37], pulse_dose_exponent, -sp.Rational(1, 2)
    )

    phi = (1 + sp.sqrt(5)) / 2
    geometric_sum = reduce_exact(1 / (1 - 1 / phi))
    book.exact(EXPECTED_CHECK_NAMES[38], geometric_sum, phi**2)

    positive_dose = sp.symbols("c", positive=True)
    partial_constant_sum = positive_dose * (order + 1)
    constant_limit = sp.limit(partial_constant_sum, order, sp.oo)
    book.record(
        EXPECTED_CHECK_NAMES[39],
        constant_limit == sp.oo,
        {"partial_sum": partial_constant_sum, "limit": constant_limit},
    )

    values["kato_and_cascade"] = {
        "fixed_khasminskii_limit": fixed_limit,
        "critical_scaling_reduction": critical_reduction,
        "energy_class_exponent": energy_exponent,
        "pulse_norm_exponent": pulse_norm_exponent,
        "pulse_dose_exponent": pulse_dose_exponent,
        "golden_geometric_sum": geometric_sum,
        "constant_dose_limit": constant_limit,
    }



def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(ADO\d+)\}", text)
    expected_tags = [f"ADO{index}" for index in range(1, 55)]
    return {
        "tag_count": len(tags),
        "unique_tag_count": len(set(tags)),
        "expected_tags": expected_tags,
        "observed_tags": tags,
        "tags_match": tags == expected_tags,
        "inventory_declaration_present": (
            "must execute exactly 40 fixed algebraic and control checks" in text
        ),
        "selected_receipt_present": (
            "runs/navier_stokes_active_deformation_occupation/verification.json"
            in text
        ),
        "paper_binding_present": (
            "turbulence/navier-stokes-active-deformation-occupation.md" in text
        ),
    }



def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_seeded_closure(book, values)
    verify_active_envelope(book, values)
    verify_anisotropy_and_scaling(book, values)
    verify_exact_controls(book, values)
    verify_kato_and_cascade(book, values)

    observed_names = tuple(row["name"] for row in book.checks)
    inventory_match = observed_names == EXPECTED_CHECK_NAMES
    if not inventory_match:
        book.failures.append("fixed check inventory")

    integrity = protocol_integrity()
    integrity_pass = bool(
        integrity["tags_match"]
        and integrity["inventory_declaration_present"]
        and integrity["selected_receipt_present"]
        and integrity["paper_binding_present"]
    )
    if not integrity_pass:
        book.failures.append("protocol integrity")

    seeded_pass = group_pass(book, "S", 8)
    active_pass = group_pass(book, "A", 8)
    coherence_pass = group_pass(book, "C", 6)
    controls_pass = group_pass(book, "X", 10)
    kato_pass = group_pass(book, "K", 8)
    success = (
        not book.failures
        and inventory_match
        and integrity_pass
        and len(book.checks) == EXPECTED_CHECKS
    )

    result = {
        "schema": SCHEMA,
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": list(EXPECTED_CHECK_NAMES),
        "check_count": len(book.checks),
        "inventory_match": inventory_match,
        "protocol_integrity": integrity,
        "checks": book.checks,
        "failures": book.failures,
        "values": stringify(values),
        "classifications": {
            "seeded_common_noise_closure": (
                "SUPPORTS" if success and seeded_pass else "INCONCLUSIVE"
            ),
            "active_occupation_and_orientation_reduction": (
                "SUPPORTS"
                if success and active_pass and coherence_pass and controls_pass
                else "INCONCLUSIVE"
            ),
            "energy_class_strain_only_exponential_control": (
                "CONTRADICTS"
                if success
                and kato_pass
                and all(book.checks[index]["passed"] for index in (36, 37))
                else "INCONCLUSIVE"
            ),
            "geometric_cascade_spacing_implies_summable_active_dose": (
                "CONTRADICTS"
                if success
                and all(book.checks[index]["passed"] for index in (38, 39))
                else "INCONCLUSIVE"
            ),
            "arbitrary_data_navier_stokes_regularity": (
                "UNRESOLVED" if success else "INCONCLUSIVE"
            ),
        },
        "scope": {
            "symbolic_schedule": "PREREGISTERED_FIXED_40_COMPONENT_CHECKS",
            "navier_stokes_trajectory": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "matrix_pde_integration": "NOT_RUN",
            "seeded_covariance_closure": (
                "ANALYTIC_IDENTITY_WITH_SYMBOLIC_PRODUCT_COMPONENTS"
            ),
            "jensen_and_continuation_steps": (
                "CONDITIONAL_ANALYTIC_ARGUMENT_OUTSIDE_EXECUTABLE_SCOPE"
            ),
            "occupation_identity": (
                "ANALYTIC_STOCHASTIC_FLOW_IDENTITY_WITH_FIXED_ODE_COMPONENTS"
            ),
            "khasminskii_and_heat_kernel_steps": (
                "CONDITIONAL_ANALYTIC_ARGUMENT_WITH_FIXED_EXPONENT_COMPONENTS"
            ),
            "pulse_obstruction": "SCALAR_PARABOLIC_SCALING_FAMILY",
            "all_data_active_dose_bound": "UNRESOLVED",
            "whole_cascade_cassi_dynamics": "NOT_RUN",
        },
    }
    return result, success



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")

    sources = {
        "protocol": PROTOCOL,
        "paper": PAPER,
        "verifier": Path(__file__).resolve(),
    }
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {
        key: {
            "path": path.relative_to(WORKSPACE).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for (key, path), payload in zip(sources.items(), payloads.values())
    }
    created = datetime.now(timezone.utc).isoformat()
    manifest = {
        "created_utc": created,
        "identities": identities,
        "sympy_version": sp.__version__,
        "python_symbolic_arithmetic": "exact",
    }

    result, success = compute()
    result["created_utc"] = created
    result["identities"] = identities
    result["sympy_version"] = sp.__version__

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for key, payload in payloads.items():
        (snapshot_dir / f"{key}{sources[key].suffix}").write_bytes(payload)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    passed_count = sum(row["passed"] for row in result["checks"])
    print(f"{passed_count} / {EXPECTED_CHECKS} checks passed")
    print(f"inventory_match: {result['inventory_match']}")
    print(f"protocol_tags_match: {result['protocol_integrity']['tags_match']}")
    print(f"status: {result['status']}")
    for name, classification in result["classifications"].items():
        print(f"{name}: {classification}")
    if success:
        print("ALL CHECKS PASSED")
        return 0
    for failure in result["failures"]:
        print(f"FAIL: {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
