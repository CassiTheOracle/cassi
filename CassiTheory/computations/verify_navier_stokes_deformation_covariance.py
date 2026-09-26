#!/usr/bin/env python3
"""Verify fixed deformation-covariance identities for Navier–Stokes.

Run from CassiTheory. The calculation is exact symbolic algebra and fixed
finite controls; it integrates no Navier–Stokes trajectory. Generated
receipts are immutable and remain beneath runs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
PROTOCOL = ROOT / "computations" / "navier-stokes-deformation-covariance-prereg.md"
PAPER = ROOT / "turbulence" / "navier-stokes-deformation-covariance.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_deformation_covariance"
    / "verification.audit-qualified-final.json"
)
EXPECTED_CHECKS = 40
EXPECTED_CHECK_NAMES = (
    "F1 Stratonovich-Itô and covariance-product conversion",
    "C1 covariance and inverse initial identity",
    "C2 first-derivative inverse identity",
    "C3 second-derivative inverse identity",
    "C4 material-derivative inverse identity",
    "C5 assembled inverse covariance PDE",
    "C6 covariance and inverse symmetry",
    "C7 one-coordinate log-determinant chain component",
    "C8 diagonal-SPD quadratic log-determinant source component",
    "W1 matrix-weighted diffusion product rule",
    "W2 exact cancellation of both stretching terms",
    "W3 equivalent covariant diffusion expressions",
    "W4 covariant-square expansion",
    "W5 local covariant weighted-law residual",
    "W6 diagonal-SPD covariant dissipation nonnegativity",
    "W7 computed initial weighted enstrophy identity",
    "W8 algebraic continuation slack identity",
    "W9 exact active-distortion growth identity",
    "W10 logarithmic Gronwall branch and envelope",
    "P1 finite-ensemble covariance identity",
    "P2 finite-ensemble covariance positivity",
    "P3 finite-ensemble stochastic Cauchy mean",
    "P4 regression residual orthogonality",
    "P5 projection Pythagorean identity",
    "P6 projection Schur-complement nonnegativity",
    "P7 synthetic scalar accumulated-loss prototype",
    "P8 synthetic scalar positive-denominator rate prototype",
    "P9 projected-data identities",
    "P10 active Rayleigh quotient",
    "H1 inverse-Jensen matrix gap identity",
    "H2 inverse-Jensen gap positivity",
    "H3 repeated deterministic deformation equality",
    "X1 extensional covariance ODE",
    "X2 extensional inverse-metric ODE",
    "X3 extensional weighted energy invariance",
    "X4 extensional active-distortion formula",
    "X5 extensional covariance determinant",
    "X6 periodic shear Navier-Stokes residual",
    "X7 full periodic shear covariance PDE and initial residual",
    "X8 computed periodic shear inverse and inactive identities",
)
SCHEMA = "cassi.navier-stokes.deformation-covariance.verification.v3"


class CheckBook:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def record(self, name: str, passed: bool, detail: Any) -> None:
        passed = bool(passed)
        row = {"name": name, "passed": passed, "detail": str(detail)}
        self.checks.append(row)
        if not passed:
            self.failures.append(name)
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")

    def exact(self, name: str, value: sp.Expr | sp.MatrixBase) -> None:
        if isinstance(value, sp.MatrixBase):
            reduced = value.applyfunc(reduce_exact)
            passed = all(item == 0 for item in reduced)
        else:
            reduced = reduce_exact(value)
            passed = reduced == 0
        self.record(name, passed, reduced)


def reduce_exact(value: sp.Expr) -> sp.Expr:
    return sp.factor(sp.cancel(sp.trigsimp(sp.expand_trig(sp.simplify(value)))))


def all_principal_minors_nonnegative(matrix: sp.MatrixBase) -> tuple[bool, list[sp.Expr]]:
    minors: list[sp.Expr] = []
    for size in range(1, matrix.rows + 1):
        for indices in combinations(range(matrix.rows), size):
            minor = sp.factor(matrix.extract(indices, indices).det())
            minors.append(minor)
    passed = all(minor.is_nonnegative is True for minor in minors)
    return passed, minors


def verify_stochastic_conversion(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z = sp.symbols("x y z", real=True)
    coordinates = (x, y, z)
    viscosity = sp.symbols("nu", positive=True)
    sigma = sp.sqrt(2 * viscosity)
    deformation = sp.Matrix(
        [
            [1 + x + y**2, x * z, y],
            [z + x**2, 1 + y * z, x],
            [x * y, z**2, 1 + x * z],
        ]
    )
    deformation_gradient = [
        sp.diff(deformation, coordinate) for coordinate in coordinates
    ]
    deformation_laplacian = sum(
        (sp.diff(deformation, coordinate, 2) for coordinate in coordinates),
        sp.zeros(3),
    )
    covariance = deformation * deformation.T
    covariance_laplacian = sum(
        (sp.diff(covariance, coordinate, 2) for coordinate in coordinates),
        sp.zeros(3),
    )

    ito_correction = (
        sigma**2 * deformation_laplacian / 2
        - viscosity * deformation_laplacian
    )
    quadratic_variation = sigma**2 * sum(
        (gradient * gradient.T for gradient in deformation_gradient), sp.zeros(3)
    )
    diffusion_product = (
        viscosity * covariance_laplacian
        - viscosity
        * (
            deformation_laplacian * deformation.T
            + deformation * deformation_laplacian.T
        )
        - quadratic_variation
    )

    velocity = sp.Matrix(sp.symbols("u0:3", real=True))
    transport_deformation = sum(
        (
            velocity[index] * deformation_gradient[index]
            for index in range(len(coordinates))
        ),
        sp.zeros(3),
    )
    transport_covariance = sum(
        (
            velocity[index] * sp.diff(covariance, coordinates[index])
            for index in range(len(coordinates))
        ),
        sp.zeros(3),
    )
    transport_product = (
        transport_deformation * deformation.T
        + deformation * transport_deformation.T
        - transport_covariance
    )

    ell = sp.symbols("ell0:9", real=True)
    velocity_gradient = sp.Matrix(3, 3, ell)
    stretched_deformation = velocity_gradient * deformation
    stretching_product = (
        stretched_deformation * deformation.T
        + deformation * stretched_deformation.T
        - velocity_gradient * covariance
        - covariance * velocity_gradient.T
    )

    book.exact(
        "F1 Stratonovich-Itô and covariance-product conversion",
        sp.Matrix.vstack(
            ito_correction,
            diffusion_product,
            transport_product,
            stretching_product,
        ),
    )
    values["stochastic_conversion"] = {
        "noise_amplitude_squared": str(sigma**2),
        "ito_correction": str(ito_correction),
        "diffusion_product_residual": str(diffusion_product),
        "transport_product_residual": str(transport_product),
        "stretching_product_residual": str(stretching_product),
    }


def covariance_fixture() -> tuple[sp.Symbol, sp.Matrix, sp.Matrix]:
    coordinate = sp.symbols("x", real=True)
    factor = sp.Matrix(
        [
            [1, coordinate, 0],
            [0, 1, coordinate**2],
            [0, 0, 1],
        ]
    )
    covariance = factor * factor.T
    inverse = sp.simplify(covariance.inv())
    return coordinate, covariance, inverse


def verify_covariance_inverse(book: CheckBook, values: dict[str, Any]) -> None:
    coordinate, covariance, inverse = covariance_fixture()
    identity = sp.eye(3)

    book.exact(
        "C1 covariance and inverse initial identity",
        sp.Matrix.vstack(
            covariance.subs(coordinate, 0) - identity,
            inverse.subs(coordinate, 0) - identity,
        ),
    )

    first_covariance = sp.diff(covariance, coordinate)
    first_inverse = sp.diff(inverse, coordinate)
    book.exact(
        "C2 first-derivative inverse identity",
        first_inverse + inverse * first_covariance * inverse,
    )

    second_covariance = sp.diff(covariance, coordinate, 2)
    second_inverse = sp.diff(inverse, coordinate, 2)
    book.exact(
        "C3 second-derivative inverse identity",
        second_inverse
        - 2 * inverse * first_covariance * inverse * first_covariance * inverse
        + inverse * second_covariance * inverse,
    )

    speed = sp.symbols("v", real=True)
    time = sp.symbols("t", real=True)
    material_coordinate = coordinate + speed * time
    material_covariance = covariance.subs(coordinate, material_coordinate)
    material_inverse = inverse.subs(coordinate, material_coordinate)
    material_covariance_derivative = sp.diff(material_covariance, time)
    material_inverse_derivative = sp.diff(material_inverse, time)
    book.exact(
        "C4 material-derivative inverse identity",
        material_inverse_derivative
        + material_inverse * material_covariance_derivative * material_inverse,
    )

    viscosity = sp.symbols("nu", positive=True)
    ell = sp.symbols("ell0:9", real=True)
    velocity_gradient = sp.Matrix(3, 3, ell)
    covariance_material = (
        velocity_gradient * covariance
        + covariance * velocity_gradient.T
        + viscosity * second_covariance
    )
    inverse_material = -inverse * covariance_material * inverse
    assembled_residual = (
        inverse_material
        + velocity_gradient.T * inverse
        + inverse * velocity_gradient
        - viscosity * second_inverse
        + 2
        * viscosity
        * inverse
        * first_covariance
        * inverse
        * first_covariance
        * inverse
    )
    book.exact("C5 assembled inverse covariance PDE", assembled_residual)

    book.record(
        "C6 covariance and inverse symmetry",
        covariance == covariance.T and inverse == inverse.T,
        f"C-C^T={covariance - covariance.T}; G-G^T={inverse - inverse.T}",
    )

    logdet_chain = (
        sp.diff(sp.log(covariance.det()), coordinate, 2)
        - sp.trace(inverse * second_covariance)
        + sp.trace(inverse * first_covariance * inverse * first_covariance)
    )
    book.exact("C7 one-coordinate log-determinant chain component", logdet_chain)

    c1, c2, c3 = sp.symbols("c1 c2 c3", positive=True)
    h11, h22, h33, h12, h13, h23 = sp.symbols(
        "h11 h22 h33 h12 h13 h23", real=True
    )
    diagonal_inverse = sp.diag(1 / c1, 1 / c2, 1 / c3)
    symmetric_gradient = sp.Matrix(
        [[h11, h12, h13], [h12, h22, h23], [h13, h23, h33]]
    )
    logdet_source = sp.expand(
        sp.trace(
            diagonal_inverse
            * symmetric_gradient
            * diagonal_inverse
            * symmetric_gradient
        )
    )
    sum_of_squares = (
        h11**2 / c1**2
        + h22**2 / c2**2
        + h33**2 / c3**2
        + 2 * h12**2 / (c1 * c2)
        + 2 * h13**2 / (c1 * c3)
        + 2 * h23**2 / (c2 * c3)
    )
    source_nonnegative = (
        reduce_exact(logdet_source - sum_of_squares) == 0
        and all(value.is_positive is True for value in (c1, c2, c3))
        and all(
            value.is_real is True
            for value in (h11, h22, h33, h12, h13, h23)
        )
    )
    book.record(
        "C8 diagonal-SPD quadratic log-determinant source component",
        source_nonnegative,
        f"sum_of_squares={sum_of_squares}",
    )

    values["covariance_inverse"] = {
        "covariance": str(covariance),
        "inverse": str(inverse),
        "determinant": str(sp.factor(covariance.det())),
        "logdet_source": str(sum_of_squares),
    }


def verify_covariant_law(book: CheckBook, values: dict[str, Any]) -> None:
    coordinate, covariance, inverse = covariance_fixture()
    viscosity = sp.symbols("nu", positive=True)
    omega = sp.Matrix(
        [
            1 + coordinate + coordinate**2,
            2 - coordinate + coordinate**3,
            coordinate - 2 * coordinate**2,
        ]
    )
    omega_x = sp.diff(omega, coordinate)
    omega_xx = sp.diff(omega, coordinate, 2)
    inverse_x = sp.diff(inverse, coordinate)
    inverse_xx = sp.diff(inverse, coordinate, 2)
    covariance_x = sp.diff(covariance, coordinate)
    covariance_xx = sp.diff(covariance, coordinate, 2)
    weighted_density = (omega.T * inverse * omega)[0]

    diffusion_product_residual = (
        (omega.T * inverse * omega_xx)[0]
        + sp.Rational(1, 2) * (omega.T * inverse_xx * omega)[0]
        - sp.Rational(1, 2) * sp.diff(weighted_density, coordinate, 2)
        + (omega_x.T * inverse * omega_x)[0]
        + 2 * (omega.T * inverse_x * omega_x)[0]
    )
    book.exact(
        "W1 matrix-weighted diffusion product rule", diffusion_product_residual
    )

    ell = sp.symbols("a0:9", real=True)
    velocity_gradient = sp.Matrix(3, 3, ell)
    w1, w2, w3 = sp.symbols("w1 w2 w3", real=True)
    generic_omega = sp.Matrix([w1, w2, w3])
    stretch_cancellation = (
        (generic_omega.T * inverse * velocity_gradient * generic_omega)[0]
        - sp.Rational(1, 2)
        * (
            generic_omega.T
            * (velocity_gradient.T * inverse + inverse * velocity_gradient)
            * generic_omega
        )[0]
    )
    book.exact(
        "W2 exact cancellation of both stretching terms", stretch_cancellation
    )

    diffusion_first = (
        (omega_x.T * inverse * omega_x)[0]
        + 2 * (omega.T * inverse_x * omega_x)[0]
    )
    diffusion_second = (
        (omega_x.T * inverse * omega_x)[0]
        - 2 * (omega.T * inverse * covariance_x * inverse * omega_x)[0]
    )
    book.exact(
        "W3 equivalent covariant diffusion expressions",
        diffusion_first - diffusion_second,
    )

    covariance_curvature = (
        omega.T
        * inverse
        * covariance_x
        * inverse
        * covariance_x
        * inverse
        * omega
    )[0]
    covariant_gradient = omega_x - covariance_x * inverse * omega
    covariant_square = (covariant_gradient.T * inverse * covariant_gradient)[0]
    book.exact(
        "W4 covariant-square expansion",
        covariant_square - diffusion_second - covariance_curvature,
    )

    covariance_material = (
        velocity_gradient * covariance
        + covariance * velocity_gradient.T
        + viscosity * covariance_xx
    )
    inverse_material = -inverse * covariance_material * inverse
    omega_material = velocity_gradient * omega + viscosity * omega_xx
    density_material = (
        2 * (omega.T * inverse * omega_material)[0]
        + (omega.T * inverse_material * omega)[0]
    )
    local_law_residual = (
        sp.Rational(1, 2) * density_material
        - viscosity
        * (
            sp.Rational(1, 2) * sp.diff(weighted_density, coordinate, 2)
            - covariant_square
        )
    )
    book.exact("W5 local covariant weighted-law residual", local_law_residual)

    c1, c2, c3 = sp.symbols("d1 d2 d3", positive=True)
    q1, q2, q3 = sp.symbols("q1 q2 q3", real=True)
    q = sp.Matrix([q1, q2, q3])
    positive_inverse = sp.diag(1 / c1, 1 / c2, 1 / c3)
    positive_square = (q.T * positive_inverse * q)[0]
    declared_sum = q1**2 / c1 + q2**2 / c2 + q3**2 / c3
    dissipation_nonnegative = (
        reduce_exact(positive_square - declared_sum) == 0
        and all(value.is_positive is True for value in (c1, c2, c3))
        and all(value.is_real is True for value in (q1, q2, q3))
    )
    book.record(
        "W6 diagonal-SPD covariant dissipation nonnegativity",
        dissipation_nonnegative,
        f"sum_of_squares={declared_sum}",
    )

    initial_inverse = inverse.subs(coordinate, 0)
    initial_weighted_density = (
        generic_omega.T * initial_inverse * generic_omega
    )[0]
    book.exact(
        "W7 computed initial weighted enstrophy identity",
        initial_weighted_density - (generic_omega.T * generic_omega)[0],
    )

    total_enstrophy, retained_energy, residual_energy = sp.symbols(
        "W Z residual", positive=True
    )
    initial_enstrophy = retained_energy + residual_energy
    active_distortion = total_enstrophy / retained_energy
    continuation_slack = sp.factor(
        active_distortion * initial_enstrophy - total_enstrophy
    )
    expected_slack = total_enstrophy * residual_energy / retained_energy
    continuation_valid = (
        reduce_exact(continuation_slack - expected_slack) == 0
        and sp.ask(sp.Q.nonnegative(expected_slack)) is True
    )
    book.record(
        "W8 algebraic continuation slack identity",
        continuation_valid,
        f"slack={expected_slack}",
    )

    time = sp.symbols("t", nonnegative=True)
    w_function = sp.Function("W", positive=True)(time)
    z_function = sp.Function("Z", positive=True)(time)
    production = sp.Function("P", real=True)(time)
    dissipation = sp.Function("D", nonnegative=True)(time)
    covariant_dissipation = sp.Function("D_C", nonnegative=True)(time)
    growth_rate = sp.diff(sp.log(w_function / z_function), time).subs(
        {
            sp.diff(w_function, time): 2 * production - 2 * viscosity * dissipation,
            sp.diff(z_function, time): -2 * viscosity * covariant_dissipation,
        }
    )
    growth_target = (
        2 * production / w_function
        + 2
        * viscosity
        * (covariant_dissipation / z_function - dissipation / w_function)
    )
    book.exact(
        "W9 exact active-distortion growth identity", growth_rate - growth_target
    )

    active_quotient = sp.Function("A", positive=True)(time)
    gamma = sp.symbols("Gamma", real=True)
    active_branch_residual = sp.diff(
        1 + sp.log(active_quotient), time
    ).subs(sp.diff(active_quotient, time), gamma * active_quotient) - gamma

    rate = sp.symbols("b", nonnegative=True)
    slack = sp.symbols("s", nonnegative=True)
    comparison = sp.Function("Y", positive=True)(time)
    weighted_comparison_derivative = sp.diff(
        sp.exp(-rate * time) * comparison, time
    ).subs(sp.diff(comparison, time), rate * comparison - slack)
    weighted_target = -slack * sp.exp(-rate * time)

    initial_log_envelope = sp.symbols("Y0", positive=True)
    log_envelope = initial_log_envelope * sp.exp(rate * time)
    envelope_residual = sp.diff(log_envelope, time) - rate * log_envelope
    inactive_branch_slack = rate
    envelope_valid = (
        reduce_exact(active_branch_residual) == 0
        and reduce_exact(weighted_comparison_derivative - weighted_target) == 0
        and weighted_target.is_nonpositive is True
        and inactive_branch_slack.is_nonnegative is True
        and reduce_exact(envelope_residual) == 0
        and reduce_exact(log_envelope.subs(time, 0) - initial_log_envelope) == 0
    )
    distortion_envelope = sp.exp(log_envelope - 1)
    book.record(
        "W10 logarithmic Gronwall branch and envelope",
        envelope_valid,
        (
            f"active_branch_residual={reduce_exact(active_branch_residual)}; "
            f"weighted_derivative={weighted_target}; "
            f"inactive_slack={inactive_branch_slack}; "
            f"A_bound={distortion_envelope}"
        ),
    )

    values["covariant_law"] = {
        "covariant_square": str(sp.factor(covariant_square)),
        "continuation_slack": str(expected_slack),
        "active_growth_rate": str(growth_target),
        "logarithmic_envelope": str(log_envelope),
    }


def projection_fixture() -> tuple[list[sp.Matrix], list[sp.Matrix], sp.Matrix, sp.Matrix]:
    deformations = [
        sp.eye(3),
        sp.Matrix([[1, 1, 0], [0, 1, 0], [0, 0, 1]]),
        sp.Matrix([[1, 0, 0], [0, 1, 1], [0, 0, 1]]),
        sp.Matrix([[1, 0, 0], [0, 1, 0], [1, 0, 1]]),
    ]
    data = [
        sp.Matrix([1, 2, -1]),
        sp.Matrix([0, -1, 3]),
        sp.Matrix([2, 1, 1]),
        sp.Matrix([-1, 2, 0]),
    ]
    scale = sp.Rational(1, 2)
    operator = sp.Matrix.hstack(*(scale * deformation for deformation in deformations))
    sampled_data = sp.Matrix.vstack(*(scale * vector for vector in data))
    return deformations, data, operator, sampled_data


def verify_projection(book: CheckBook, values: dict[str, Any]) -> None:
    deformations, data, operator, sampled_data = projection_fixture()
    covariance = sp.simplify(operator * operator.T)
    inverse = sp.simplify(covariance.inv())
    projector = sp.simplify(operator.T * inverse * operator)
    identity = sp.eye(sampled_data.rows)
    omega = sp.simplify(operator * sampled_data)
    projected = sp.simplify(projector * sampled_data)
    residual = sp.simplify((identity - projector) * sampled_data)

    direct_covariance = sum(
        (deformation * deformation.T for deformation in deformations), sp.zeros(3)
    ) / 4
    book.exact("P1 finite-ensemble covariance identity", covariance - direct_covariance)

    principal_minors = [
        sp.factor(covariance[:size, :size].det()) for size in range(1, 4)
    ]
    book.record(
        "P2 finite-ensemble covariance positivity",
        all(value.is_positive is True for value in principal_minors),
        f"leading_principal_minors={principal_minors}",
    )

    direct_mean = sum(
        (deformation * vector for deformation, vector in zip(deformations, data)),
        sp.zeros(3, 1),
    ) / 4
    book.exact("P3 finite-ensemble stochastic Cauchy mean", omega - direct_mean)

    book.exact("P4 regression residual orthogonality", operator * residual)

    full_norm = (sampled_data.T * sampled_data)[0]
    projected_norm = (projected.T * projected)[0]
    residual_norm = (residual.T * residual)[0]
    book.exact(
        "P5 projection Pythagorean identity",
        full_norm - projected_norm - residual_norm,
    )

    schur_gap = sp.simplify(full_norm - (omega.T * inverse * omega)[0])
    schur_valid = (
        reduce_exact(schur_gap - residual_norm) == 0
        and schur_gap.is_nonnegative is True
    )
    book.record(
        "P6 projection Schur-complement nonnegativity",
        schur_valid,
        f"gap={schur_gap}; residual_norm={residual_norm}",
    )

    time = sp.symbols("t", nonnegative=True)
    integration_time = sp.symbols("s", nonnegative=True)
    viscosity = sp.symbols("nu", positive=True)
    initial_energy = sp.symbols("W0", positive=True)
    positive_denominator = sp.symbols("Z_C_positive", positive=True)
    dissipation_profile = 1 + integration_time**2
    accumulated_loss = 2 * viscosity * sp.integrate(
        dissipation_profile, (integration_time, 0, time)
    )
    retained = initial_energy - accumulated_loss
    synthetic_loss = initial_energy - retained
    book.exact(
        "P7 synthetic scalar accumulated-loss prototype",
        synthetic_loss - accumulated_loss,
    )

    current_dissipation = dissipation_profile.subs(integration_time, time)
    normalized_rate = 2 * viscosity * current_dissipation / retained
    rate_residuals = sp.Matrix(
        [
            sp.diff(synthetic_loss, time)
            - 2 * viscosity * current_dissipation,
            sp.diff(synthetic_loss, time)
            / (initial_energy - synthetic_loss)
            - normalized_rate,
            sp.diff(-sp.log(retained), time) - normalized_rate,
            (
                retained.subs(
                    initial_energy,
                    accumulated_loss + positive_denominator,
                )
                - positive_denominator
            ),
        ]
    )
    reduced_rates = rate_residuals.applyfunc(reduce_exact)
    positive_branch_valid = (
        all(item == 0 for item in reduced_rates)
        and positive_denominator.is_positive is True
    )
    book.record(
        "P8 synthetic scalar positive-denominator rate prototype",
        positive_branch_valid,
        (
            f"formal_residuals={reduced_rates}; "
            f"surviving_denominator={positive_denominator}>0"
        ),
    )

    projected_identities = sp.Matrix.vstack(
        projected - operator.T * inverse * omega,
        operator * projected - omega,
        sp.Matrix([projected_norm - (omega.T * inverse * omega)[0]]),
    )
    book.exact("P9 projected-data identities", projected_identities)

    output_norm = (operator * projected).dot(operator * projected)
    active_quotient = sp.factor(output_norm / projected_norm)
    expected_quotient = sp.factor(
        (omega.T * omega)[0] / (omega.T * inverse * omega)[0]
    )
    book.exact("P10 active Rayleigh quotient", active_quotient - expected_quotient)

    values["projection"] = {
        "deformation_count": len(deformations),
        "covariance": str(covariance),
        "inverse_covariance": str(inverse),
        "omega": str(omega),
        "projected_norm": str(projected_norm),
        "residual_norm": str(residual_norm),
        "active_rayleigh_quotient": str(active_quotient),
        "synthetic_accumulated_loss": str(accumulated_loss),
        "synthetic_positive_denominator_rate": str(normalized_rate),
        "synthetic_positive_denominator_marker": str(positive_denominator),
    }


def verify_harmonic_gap(book: CheckBook, values: dict[str, Any]) -> None:
    deformations, _, _, _ = projection_fixture()
    tensors = [deformation * deformation.T for deformation in deformations]
    covariance = sum(tensors, sp.zeros(3)) / len(tensors)
    inverse_covariance = sp.simplify(covariance.inv())
    inverse_mean = sum((tensor.inv() for tensor in tensors), sp.zeros(3)) / len(tensors)
    gap = sp.simplify(inverse_mean - inverse_covariance)
    square_mean = sum(
        (
            (tensor.inv() - inverse_covariance)
            * tensor
            * (tensor.inv() - inverse_covariance)
            for tensor in tensors
        ),
        sp.zeros(3),
    ) / len(tensors)
    book.exact("H1 inverse-Jensen matrix gap identity", gap - square_mean)

    principal_nonnegative, principal_minors = all_principal_minors_nonnegative(gap)
    book.record(
        "H2 inverse-Jensen gap positivity",
        gap == gap.T and principal_nonnegative,
        f"principal_minors={principal_minors}",
    )

    deterministic = sp.Matrix([[1, 2, 0], [0, 1, 1], [0, 0, 1]])
    deterministic_tensor = deterministic * deterministic.T
    repeated_tensors = [deterministic_tensor for _ in range(3)]
    deterministic_covariance = (
        sum(repeated_tensors, sp.zeros(3)) / len(repeated_tensors)
    )
    deterministic_inverse_mean = sum(
        (tensor.inv() for tensor in repeated_tensors), sp.zeros(3)
    ) / len(repeated_tensors)
    deterministic_gap = sp.simplify(
        deterministic_inverse_mean - deterministic_covariance.inv()
    )
    book.exact(
        "H3 repeated deterministic deformation equality",
        deterministic_gap,
    )

    values["inverse_jensen_gap"] = {
        "inverse_arithmetic_mean": str(inverse_covariance),
        "arithmetic_mean_inverse_metric": str(inverse_mean),
        "gap": str(gap),
        "principal_minors": [str(value) for value in principal_minors],
        "deterministic_gap": str(deterministic_gap),
    }


def verify_exact_controls(book: CheckBook, values: dict[str, Any]) -> None:
    time = sp.symbols("t", nonnegative=True)
    rate = sp.symbols("a", positive=True)
    stretch = sp.diag(rate, -rate, 0)
    deformation = sp.diag(sp.exp(rate * time), sp.exp(-rate * time), 1)
    covariance = deformation * deformation.T
    inverse = sp.simplify(covariance.inv())

    book.exact(
        "X1 extensional covariance ODE",
        sp.diff(covariance, time) - stretch * covariance - covariance * stretch.T,
    )
    book.exact(
        "X2 extensional inverse-metric ODE",
        sp.diff(inverse, time) + stretch.T * inverse + inverse * stretch,
    )

    x1, x2, x3 = sp.symbols("x1 x2 x3", real=True)
    initial_vorticity = sp.Matrix([x1, x2, x3])
    vorticity = deformation * initial_vorticity
    book.exact(
        "X3 extensional weighted energy invariance",
        (vorticity.T * inverse * vorticity)[0]
        - (initial_vorticity.T * initial_vorticity)[0],
    )

    active_vorticity = deformation * sp.Matrix([1, 0, 0])
    active_distortion = sp.factor(
        (active_vorticity.T * active_vorticity)[0]
        / (active_vorticity.T * inverse * active_vorticity)[0]
    )
    book.exact(
        "X4 extensional active-distortion formula",
        active_distortion - sp.exp(2 * rate * time),
    )
    book.exact("X5 extensional covariance determinant", covariance.det() - 1)

    x, y, z = sp.symbols("x y z", real=True)
    viscosity = sp.symbols("nu", positive=True)
    mode = sp.symbols("n", positive=True, integer=True)
    amplitude = sp.symbols("b", positive=True)
    decay = viscosity * mode**2
    velocity = sp.Matrix(
        [amplitude * sp.exp(-decay * time) * sp.sin(mode * y), 0, 0]
    )
    coordinates = (x, y, z)
    gradient = velocity.jacobian(coordinates)
    divergence = sp.trace(gradient)
    advection = gradient * velocity
    laplacian_velocity = velocity.applyfunc(
        lambda item: sum(sp.diff(item, coordinate, 2) for coordinate in coordinates)
    )
    momentum_residual = sp.diff(velocity, time) + advection - viscosity * laplacian_velocity
    book.exact(
        "X6 periodic shear Navier-Stokes residual",
        sp.Matrix.vstack(sp.Matrix([divergence]), momentum_residual),
    )

    shear_rate = amplitude * mode * sp.exp(-decay * time) * sp.cos(mode * y)
    q0 = (
        amplitude**2
        * mode**2
        / (4 * decay**2)
        * (1 - (1 + 2 * decay * time) * sp.exp(-2 * decay * time))
    )
    q2 = (
        amplitude**2
        * mode**2
        / (4 * decay**2)
        * sp.exp(-4 * decay * time)
        * (sp.exp(2 * decay * time) * (2 * decay * time - 1) + 1)
    )
    shear_covariance = sp.Matrix(
        [
            [1 + q0 + q2 * sp.cos(2 * mode * y), time * shear_rate, 0],
            [time * shear_rate, 1, 0],
            [0, 0, 1],
        ]
    )
    source = time * amplitude**2 * mode**2 * sp.exp(-2 * decay * time)
    q0_residual = reduce_exact(sp.diff(q0, time) - source)
    q2_residual = reduce_exact(
        sp.diff(q2, time) + 4 * decay * q2 - source
    )
    off_diagonal_residual = reduce_exact(
        sp.diff(time * shear_rate, time)
        - viscosity * sp.diff(time * shear_rate, y, 2)
        - shear_rate
    )
    reaction_residual = reduce_exact(
        2 * time * shear_rate**2
        - source * (1 + sp.cos(2 * mode * y))
    )
    covariance_residual = sp.Matrix(
        [
            [
                q0_residual
                + q2_residual * sp.cos(2 * mode * y)
                - reaction_residual,
                off_diagonal_residual,
                0,
            ],
            [off_diagonal_residual, 0, 0],
            [0, 0, 0],
        ]
    )
    covariance_initial_residual = shear_covariance.subs(time, 0) - sp.eye(3)
    book.exact(
        "X7 full periodic shear covariance PDE and initial residual",
        sp.Matrix.vstack(covariance_residual, covariance_initial_residual),
    )

    shear_c11 = shear_covariance[0, 0]
    shear_c12 = shear_covariance[0, 1]
    shear_block_determinant = sp.factor(shear_c11 - shear_c12**2)
    shear_inverse = sp.Matrix(
        [
            [1 / shear_block_determinant, -shear_c12 / shear_block_determinant, 0],
            [
                -shear_c12 / shear_block_determinant,
                shear_c11 / shear_block_determinant,
                0,
            ],
            [0, 0, 1],
        ]
    )
    inactive_axis = sp.Matrix([0, 0, 1])
    shear_vorticity = -shear_rate * inactive_axis
    inverse_identity_residual = shear_covariance * shear_inverse - sp.eye(3)
    inverse_axis_residual = shear_inverse * inactive_axis - inactive_axis
    inverse_action_residual = shear_inverse * shear_vorticity - shear_vorticity
    shear_euclidean = (shear_vorticity.T * shear_vorticity)[0]
    shear_weighted = (shear_vorticity.T * shear_inverse * shear_vorticity)[0]
    global_enstrophy = (
        amplitude**2 * mode**2 * sp.exp(-2 * decay * time) / 2
    )
    integrated_euclidean = sp.integrate(
        shear_euclidean, (y, 0, 2 * sp.pi)
    ) / (2 * sp.pi)
    integrated_weighted = sp.integrate(
        shear_weighted, (y, 0, 2 * sp.pi)
    ) / (2 * sp.pi)
    inactive_identities = sp.Matrix.vstack(
        inverse_identity_residual.reshape(9, 1),
        inverse_axis_residual,
        inverse_action_residual,
        sp.Matrix(
            [
                shear_weighted - shear_euclidean,
                integrated_euclidean - global_enstrophy,
                integrated_weighted - global_enstrophy,
            ]
        ),
    )
    book.exact(
        "X8 computed periodic shear inverse and inactive identities",
        inactive_identities,
    )

    values["exact_controls"] = {
        "extensional_covariance": str(covariance),
        "extensional_inverse": str(inverse),
        "extensional_active_distortion": str(active_distortion),
        "shear_covariance": str(shear_covariance),
        "shear_inverse": str(shear_inverse),
        "shear_determinant": str(sp.factor(shear_covariance.det())),
        "shear_inverse_33": str(shear_inverse[2, 2]),
        "shear_active_distortion": str(
            sp.simplify(global_enstrophy / integrated_weighted)
        ),
    }


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_stochastic_conversion(book, values)
    verify_covariance_inverse(book, values)
    verify_covariant_law(book, values)
    verify_projection(book, values)
    verify_harmonic_gap(book, values)
    verify_exact_controls(book, values)

    observed_check_names = tuple(row["name"] for row in book.checks)
    inventory_match = observed_check_names == EXPECTED_CHECK_NAMES
    if not inventory_match:
        book.failures.append("fixed check inventory")
    success = not book.failures and inventory_match
    weighted_law_rows = [
        row for row in book.checks if row["name"].startswith(("F1 ", "C", "W"))
    ]
    projection_rows = [
        row
        for row in book.checks
        if row["name"].startswith("H")
        or any(
            row["name"].startswith(f"P{index} ")
            for index in (1, 2, 3, 4, 5, 6, 9, 10)
        )
    ]
    extensional_rows = [
        row
        for row in book.checks
        if any(row["name"].startswith(f"X{index} ") for index in range(1, 6))
    ]
    weighted_law_pass = (
        len(weighted_law_rows) == 19
        and all(row["passed"] for row in weighted_law_rows)
    )
    projection_checks_pass = (
        len(projection_rows) == 11
        and all(row["passed"] for row in projection_rows)
    )
    extensional_controls_pass = (
        len(extensional_rows) == 5
        and all(row["passed"] for row in extensional_rows)
    )
    result = {
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": list(EXPECTED_CHECK_NAMES),
        "check_count": len(book.checks),
        "inventory_match": inventory_match,
        "checks": book.checks,
        "failures": book.failures,
        "values": values,
        "classifications": {
            "covariance_inverse_weighted_law": (
                "SUPPORTS" if weighted_law_pass else "INCONCLUSIVE"
            ),
            "finite_ensemble_projection_and_inverse_jensen": (
                "SUPPORTS" if projection_checks_pass else "INCONCLUSIVE"
            ),
            "coercivity_from_positivity_determinant_and_exact_cancellation": (
                "CONTRADICTS" if extensional_controls_pass else "INCONCLUSIVE"
            ),
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "navier_stokes_trajectory": "NOT_RUN",
            "symbolic_schedule": "AUDIT_RECHECKED_FIXED_40_CHECKS",
            "matrix_pde_integration": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "stochastic_flow_spde": "CITATION_DERIVED_WITH_SYMBOLIC_CONVERSION_CHECK",
            "all_data_active_distortion_bound": "UNRESOLVED",
            "covariance_inverse_law": "ANALYTIC_IDENTITY_WITH_FIXED_SYMBOLIC_CHECKS",
            "determinant_inequality": (
                "ANALYTIC_ARGUMENT_WITH_C7_C8_ALGEBRAIC_COMPONENTS"
            ),
            "inverse_deformation_metric_comparison": (
                "ANALYTIC_REFERENCE_WITH_H1_H3_FIXED_MATRIX_GAP_CHECKS"
            ),
            "projection_executable_scope": "FIXED_FOUR_MEMBER_ENSEMBLE",
            "endpoint_regression_bridge": (
                "ANALYTIC_IDENTITY_WITH_P7_P8_SYNTHETIC_SCALAR_PROTOTYPES"
            ),
            "control_executable_scope": "EXTENSIONAL_AND_PERIODIC_SHEAR",
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
    result.update(
        {
            "schema": SCHEMA,
            "created_utc": created,
            "source_sha256": identities,
            "sympy_version": sp.__version__,
            "python_symbolic_arithmetic": "exact",
        }
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        suffix = path.suffix or ".txt"
        (snapshot_dir / f"{key}{suffix}").write_bytes(path.read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(f"Receipt: {output}")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "check_count",
                    "inventory_match",
                    "classifications",
                    "failures",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    if success:
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
