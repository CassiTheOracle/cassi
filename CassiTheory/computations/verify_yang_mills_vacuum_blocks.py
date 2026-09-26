#!/usr/bin/env python3
"""Verify fixed pure-SU(2) vacuum-geometry and Gaussian block controls.

Run from CassiTheory with --output pointing to a fresh immutable receipt.
The finite controls do not construct continuum four-dimensional Yang-Mills.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sympy as sp

import verify_yang_mills_loop_gap as receipt_checks

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/yang-mills-vacuum-block-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_vacuum_blocks/verification.json"
X_VALUES = (0.25, 1.0, 16.0)
FD_STEPS = (1e-3, 5e-4)
GAUSSIAN_SIZES = (4, 8, 16, 32, 64)
GAUSSIAN_MASSES = (0.0, 0.5)
GROUP_TOLERANCE = 1e-11
DERIVATIVE_TOLERANCE = 1e-9
LOCAL_ENERGY_TOLERANCE = 1e-5
MATRIX_TOLERANCE = 1e-10
MIXED_MARGIN = 1e-6

check = receipt_checks.check
exact = receipt_checks.exact

PAULI = (
    np.array(((0, 1), (1, 0)), dtype=complex),
    np.array(((0, -1j), (1j, 0)), dtype=complex),
    np.array(((1, 0), (0, -1)), dtype=complex),
)
IDENTITY_2 = np.eye(2, dtype=complex)
EDGES = ((0, 1), (1, 2), (3, 2), (0, 3), (1, 5), (4, 5), (0, 4))
WORDS = (
    ((0, 1), (1, 1), (2, -1), (3, -1)),
    ((0, 1), (4, 1), (5, -1), (6, -1)),
)


def normalized_error(actual, expected):
    actual = np.asarray(actual)
    expected = np.asarray(expected)
    return float(np.max(np.abs(actual - expected)
                        / np.maximum(1.0, np.maximum(np.abs(actual), np.abs(expected)))))


def matrix_json(matrix):
    return [[[float(value.real), float(value.imag)] for value in row]
            for row in np.asarray(matrix)]


def su2_exp(theta, axis):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    generator = sum((axis[index] * PAULI[index] for index in range(3)),
                    np.zeros((2, 2), dtype=complex))
    return math.cos(theta) * IDENTITY_2 + 1j * math.sin(theta) * generator


def factor(links, edge, orientation):
    return links[edge] if orientation == 1 else links[edge].conj().T


def holonomy(links, word):
    value = IDENTITY_2.copy()
    for edge, orientation in word:
        value = value @ factor(links, edge, orientation)
    return value


def character(links, word):
    value = np.trace(holonomy(links, word))
    if abs(value.imag) > 2e-12:
        raise ArithmeticError(f"SU(2) character acquired imaginary part {value.imag}")
    return float(value.real)


def character_derivative(links, word, target_edge, generator):
    value = np.zeros((2, 2), dtype=complex)
    position = next(index for index, (edge, _) in enumerate(word) if edge == target_edge)
    for index, (edge, orientation) in enumerate(word):
        current = factor(links, edge, orientation)
        if index == position:
            if orientation == 1:
                current = 0.5j * PAULI[generator] @ links[edge]
            else:
                current = links[edge].conj().T @ (-0.5j * PAULI[generator])
        value = current if index == 0 else value @ current
    trace = np.trace(value)
    if abs(trace.imag) > 2e-12:
        raise ArithmeticError(f"SU(2) derivative acquired imaginary part {trace.imag}")
    return float(trace.real)


def left_perturb(links, edge, generator, parameter):
    changed = [matrix.copy() for matrix in links]
    changed[edge] = su2_exp(parameter / 2.0, np.eye(3)[generator]) @ changed[edge]
    return changed


def fixture_observables(links):
    loops = [holonomy(links, word) for word in WORDS]
    characters = [float(np.trace(loop).real) for loop in loops]
    gradients = []
    for word in WORDS:
        active = {edge for edge, _ in word}
        gradient = np.zeros((len(EDGES), 3), dtype=float)
        for edge in active:
            for generator in range(3):
                gradient[edge, generator] = character_derivative(
                    links, word, edge, generator)
        gradients.append(gradient)
    total_gradient = gradients[0] + gradients[1]
    joined = float(np.trace(loops[0] @ loops[1]).real)
    self_squares = [float(np.sum(gradient * gradient)) for gradient in gradients]
    shared_cross = float(np.dot(gradients[0][0], gradients[1][0]))
    return dict(
        characters=characters,
        loop_matrices=[matrix_json(loop) for loop in loops],
        joined_trace=joined,
        gradients=[gradient.tolist() for gradient in gradients],
        self_gradient_squares=self_squares,
        shared_cross=shared_cross,
        total_gradient_square=float(np.sum(total_gradient * total_gradient)),
    )


def local_energy(observables, x, kappa):
    return (4.0 * x + (3.0 * kappa - x) * sum(observables["characters"])
            - kappa * kappa * observables["total_gradient_square"])


def five_point_controls(links, observables, x, kappa, step):
    analytic_gradients = [np.asarray(row) for row in observables["gradients"]]
    first_errors = []
    kinetic = 0.0
    base_sum = sum(observables["characters"])
    for edge in range(len(EDGES)):
        for generator in range(3):
            values = {}
            character_values = [{}, {}]
            for multiplier in (-2, -1, 1, 2):
                moved = left_perturb(links, edge, generator, multiplier * step)
                chars = [character(moved, word) for word in WORDS]
                values[multiplier] = math.exp(kappa * (sum(chars) - base_sum))
                for loop_index in range(2):
                    character_values[loop_index][multiplier] = chars[loop_index]
            for loop_index in range(2):
                derivative = (character_values[loop_index][-2]
                              - 8.0 * character_values[loop_index][-1]
                              + 8.0 * character_values[loop_index][1]
                              - character_values[loop_index][2]) / (12.0 * step)
                first_errors.append(abs(derivative
                                        - analytic_gradients[loop_index][edge, generator]))
            second = (-values[2] + 16.0 * values[1] - 30.0
                      + 16.0 * values[-1] - values[-2]) / (12.0 * step * step)
            kinetic -= second
    direct = kinetic + 4.0 * x - x * base_sum
    analytic = local_energy(observables, x, kappa)
    return dict(
        step=step,
        maximum_first_derivative_error=max(first_errors),
        direct_local_energy=direct,
        analytic_local_energy=analytic,
        local_energy_error=abs(direct - analytic),
        local_energy_normalized_error=abs(direct - analytic) / max(1.0, abs(analytic)),
    )


def make_fixtures():
    fixtures = [("identity", [IDENTITY_2.copy() for _ in EDGES])]
    commuting = [su2_exp(math.pi * (edge + 1) / 19.0, (0, 0, 1))
                 for edge in range(len(EDGES))]
    fixtures.append(("commuting", commuting))
    for sample in range(3):
        links = []
        for edge in range(len(EDGES)):
            theta = math.pi * (1 + ((edge + 1) * (sample + 2) % 17)) / 19.0
            axis = (1 + ((edge + sample) % 3),
                    ((2 * edge + sample) % 5) - 2,
                    ((3 * edge + 2 * sample) % 7) - 3)
            links.append(su2_exp(theta, axis))
        fixtures.append((f"noncommuting_{sample}", links))
    return fixtures


def gauge_transform(links):
    gauges = [su2_exp(math.pi * (vertex + 1) / 11.0,
                      np.eye(3)[vertex % 3]) for vertex in range(6)]
    return [gauges[source] @ link @ gauges[target].conj().T
            for link, (source, target) in zip(links, EDGES)]


def symbolic_controls(result):
    pauli = tuple(sp.Matrix(matrix) for matrix in (
        ((0, 1), (1, 0)), ((0, -sp.I), (sp.I, 0)), ((1, 0), (0, -1))))
    fierz_residuals = []
    for i in range(2):
        for j in range(2):
            for k in range(2):
                for ell in range(2):
                    lhs = sum(matrix[i, j] * matrix[k, ell] for matrix in pauli)
                    rhs = 2 * int(i == ell) * int(j == k) - int(i == j) * int(k == ell)
                    fierz_residuals.append(sp.simplify(lhs - rhs))
    check(result, "Pauli Fierz completeness", all(value == 0 for value in fierz_residuals),
          [str(value) for value in fierz_residuals])

    c = sp.Matrix(((1, 1, -1, -1, 0, 0, 0),
                   (1, 0, 0, 0, 1, -1, -1)))
    exact(result, "two-plaquette curl Gram matrix", c * c.T,
          sp.Matrix(((4, 1), (1, 4))))
    check(result, "two-plaquette positive curl eigenvalues",
          (c * c.T).eigenvals() == {sp.Integer(3): 1, sp.Integer(5): 1},
          {str(key): value for key, value in (c * c.T).eigenvals().items()})
    single = sp.Matrix(((1, 1, -1, -1),))
    exact(result, "single-square curl eigenvalue", single * single.T, sp.Matrix(((4,),)))

    lam, g, a = sp.symbols("lambda g a", positive=True)
    q_kernel = sp.sqrt(lam) / (sp.sqrt(2) * g**2)
    frequency = sp.sqrt(lam) / (sp.sqrt(2) * a)
    exact(result, "single-square weak mode frequency", frequency.subs(lam, 4),
          sp.sqrt(2) / a)
    exact(result, "single-square radial spacing", 2 * frequency.subs(lam, 4),
          2 * sp.sqrt(2) / a)
    kappa_three = sp.sqrt(2) / (g**2 * sp.sqrt(3))
    kappa_five = sp.sqrt(2) / (g**2 * sp.sqrt(5))
    check(result, "one scalar trial kernel cannot fit two curl modes",
          sp.simplify(kappa_three - kappa_five) != 0,
          {"lambda_3": str(kappa_three), "lambda_5": str(kappa_five)})

    t, momentum, fixed, delta = sp.symbols("t k g_star delta", real=True)
    function = sp.Function("g")
    ir_derivative = sp.diff(function(momentum * sp.exp(-t)), t).subs(t, 0)
    exact(result, "IR finite-step differential sign", ir_derivative,
          -momentum * sp.diff(function(momentum), momentum))
    multiplier, initial = sp.symbols("lambda_R g_0", real=True)
    iterate = fixed + multiplier**sp.Symbol("n", integer=True, nonnegative=True) * (initial - fixed)
    n = next(symbol for symbol in iterate.free_symbols if symbol.name == "n")
    exact(result, "affine RG map iterate", fixed + multiplier * (iterate - fixed),
          iterate.subs(n, n + 1))
    exact(result, "linearized discrete beta numerator",
          (fixed + multiplier * delta) - (fixed + delta), (multiplier - 1) * delta)

    result["analytic_formulas"] = dict(
        ground_state_transform="Omega^{-1}(h-E0)Omega f = -Omega^{-2} sum_eA X_eA(Omega^2 X_eA f)",
        physical_gap="g^2/(2a) times the gauge-invariant Poincare constant of mu=Omega^2 dU",
        weighted_cover_gap="Delta_phys >= g^2 lambda_loc/(2a A_AT rho)",
        continuum_target="lambda_loc/(A_AT rho) >= 2 a m_star/g^2",
        trial_local_energy="2 x N_p + (3 kappa-x) S - kappa^2 sum_eA (X_eA S)^2",
        trial_adjoint_projection="kappa^2 onto chi_1(U_p); requires analytical lattice proof",
        shared_link_fierz="sum_A (X V_p)(X V_q)=V_p V_q/4-Tr(A_p A_q)/2",
        weak_vacuum_kernel=str(q_kernel),
        weak_mode_frequency=str(frequency),
        trial_kernel="Q_trial=(kappa/2) C^T C; Q_exact=sqrt(C^T C)/(sqrt(2) g^2)",
        ir_beta_limit="beta_b=[g(k/b)-g(k)]/ln(b) -> -k dg/dk",
        fixed_map_linearization="beta_b=(lambda_R-1) delta g/ln(b); attraction requires |lambda_R|<1",
    )


def group_controls(result):
    result["group_fixtures"] = []
    result["local_energy_rows"] = []
    fixtures = make_fixtures()
    for name, links in fixtures:
        observables = fixture_observables(links)
        transformed = fixture_observables(gauge_transform(links))
        errors = dict(
            first_self=abs(observables["self_gradient_squares"][0]
                           - (4.0 - observables["characters"][0] ** 2)),
            second_self=abs(observables["self_gradient_squares"][1]
                            - (4.0 - observables["characters"][1] ** 2)),
            shared_fierz=abs(observables["shared_cross"]
                             - (observables["characters"][0] * observables["characters"][1] / 4.0
                                - observables["joined_trace"] / 2.0)),
        )
        check(result, f"fixed SU2 group identities {name}", max(errors.values()) < GROUP_TOLERANCE,
              errors)
        invariant_error = max(
            normalized_error(observables["characters"], transformed["characters"]),
            normalized_error(observables["joined_trace"], transformed["joined_trace"]),
            normalized_error(observables["self_gradient_squares"],
                             transformed["self_gradient_squares"]),
            normalized_error(observables["total_gradient_square"],
                             transformed["total_gradient_square"]),
        )
        check(result, f"fixed gauge invariance {name}", invariant_error < GROUP_TOLERANCE,
              invariant_error)
        result["group_fixtures"].append(dict(
            name=name, links=[matrix_json(matrix) for matrix in links],
            observables=observables, transformed_observables=transformed,
            identity_errors=errors, gauge_invariance_error=invariant_error))

        for x in X_VALUES:
            for label, kappa in (("zero", 0.0), ("strong_series", x / 3.0),
                                 ("weak_scale", math.sqrt(x))):
                fd_rows = [five_point_controls(links, observables, x, kappa, step)
                           for step in FD_STEPS]
                for fd in fd_rows:
                    check(result,
                          f"analytic character derivatives {name} x={x} kappa={label} h={fd['step']}",
                          fd["maximum_first_derivative_error"] <= DERIVATIVE_TOLERANCE,
                          fd["maximum_first_derivative_error"])
                    check(result,
                          f"direct local energy {name} x={x} kappa={label} h={fd['step']}",
                          fd["local_energy_normalized_error"] <= LOCAL_ENERGY_TOLERANCE,
                          fd)
                gauge_energy_error = abs(local_energy(observables, x, kappa)
                                         - local_energy(transformed, x, kappa))
                check(result, f"local-energy gauge invariance {name} x={x} kappa={label}",
                      gauge_energy_error < GROUP_TOLERANCE, gauge_energy_error)
                result["local_energy_rows"].append(dict(
                    fixture=name, x=x, kappa_label=label, kappa=kappa,
                    characters=observables["characters"],
                    joined_trace=observables["joined_trace"],
                    total_gradient_square=observables["total_gradient_square"],
                    analytic_local_energy=local_energy(observables, x, kappa),
                    gauge_energy_error=gauge_energy_error,
                    finite_difference=fd_rows))

    result["same_character_rows"] = []
    for label, axis in (("parallel", (0, 0, 1)), ("orthogonal", (1, 0, 0)),
                        ("antiparallel", (0, 0, -1))):
        links = [IDENTITY_2.copy() for _ in EDGES]
        links[1] = su2_exp(math.pi / 2.0, (0, 0, 1))
        links[4] = su2_exp(math.pi / 2.0, axis)
        observables = fixture_observables(links)
        result["same_character_rows"].append(dict(
            label=label, characters=observables["characters"],
            joined_trace=observables["joined_trace"],
            total_gradient_square=observables["total_gradient_square"],
            local_energy=local_energy(observables, 1.0, 1.0)))
    same = result["same_character_rows"]
    check(result, "same-character relative-holonomy witness",
          max(abs(value) for row in same for value in row["characters"]) < GROUP_TOLERANCE
          and normalized_error([row["joined_trace"] for row in same], (-2.0, 0.0, 2.0)) < GROUP_TOLERANCE
          and normalized_error([row["total_gradient_square"] for row in same], (10.0, 8.0, 6.0)) < GROUP_TOLERANCE
          and normalized_error([row["local_energy"] for row in same], (-6.0, -4.0, -2.0)) < GROUP_TOLERANCE,
          same)


def positive_square_root(matrix):
    values, vectors = np.linalg.eigh(matrix)
    if np.min(values) <= 0:
        raise ArithmeticError("Expected a positive definite matrix")
    return (vectors * np.sqrt(values)) @ vectors.T


def symplectic_values(covariance_q, covariance_p):
    root_q = positive_square_root(covariance_q)
    values = np.linalg.eigvalsh(root_q @ covariance_p @ root_q)
    return np.sqrt(np.maximum(values, 0.0))


def gaussian_controls(result):
    result["gaussian_rows"] = []
    for size in GAUSSIAN_SIZES:
        for mass in GAUSSIAN_MASSES:
            d_laplacian = (np.diag(np.full(size, 2.0 + mass * mass))
                           + np.diag(np.full(size - 1, -1.0), 1)
                           + np.diag(np.full(size - 1, -1.0), -1))
            q_primary = positive_square_root(d_laplacian)
            indices = np.arange(1, size + 1, dtype=float)
            sine_vectors = math.sqrt(2.0 / (size + 1)) * np.sin(
                np.pi * np.outer(indices, indices) / (size + 1))
            sine_values = mass * mass + 4.0 * np.sin(
                np.pi * indices / (2.0 * (size + 1))) ** 2
            q_sine = (sine_vectors * np.sqrt(sine_values)) @ sine_vectors.T
            reconstruction_error = normalized_error(q_primary, q_sine)
            check(result, f"independent sine square root N={size} m={mass}",
                  reconstruction_error <= MATRIX_TOLERANCE, reconstruction_error)

            diagonal = np.diag(q_primary)
            inverse_sqrt_diagonal = np.diag(1.0 / np.sqrt(diagonal))
            correlation_precision = inverse_sqrt_diagonal @ q_primary @ inverse_sqrt_diagonal
            correlation_values, correlation_vectors = np.linalg.eigh(correlation_precision)
            tensorization = 1.0 / correlation_values[0]
            first_vector = np.sqrt(diagonal) * correlation_vectors[:, 0]
            linear_ratio = (first_vector @ np.linalg.solve(q_primary, first_vector)
                            / (first_vector @ (first_vector / diagonal)))
            saturation_error = abs(linear_ratio - tensorization) / max(1.0, tensorization)
            check(result, f"linear tensorization saturation N={size} m={mass}",
                  saturation_error <= MATRIX_TOLERANCE,
                  dict(tensorization=tensorization, linear_ratio=linear_ratio,
                       error=saturation_error))

            expected_minimum = math.sqrt(mass * mass
                                         + 4.0 * math.sin(math.pi / (2.0 * (size + 1))) ** 2)
            minimum_q = float(np.linalg.eigvalsh(q_primary)[0])
            check(result, f"Gaussian Poincare spectrum N={size} m={mass}",
                  abs(minimum_q - expected_minimum) <= MATRIX_TOLERANCE,
                  dict(actual=minimum_q, expected=expected_minimum,
                       global_gap=2.0 * minimum_q,
                       minimum_conditional_gap=2.0 * float(np.min(diagonal))))
            if mass == 0.0:
                bound_error = max(0.0, 1.0 - float(np.min(diagonal)),
                                  float(np.max(diagonal)) - math.sqrt(2.0),
                                  1.0 / minimum_q - tensorization)
                check(result, f"massless conditional-gap obstruction N={size}",
                      bound_error <= MATRIX_TOLERANCE,
                      dict(diagonal_min=float(np.min(diagonal)),
                           diagonal_max=float(np.max(diagonal)),
                           tensorization=tensorization,
                           reciprocal_global_scale=1.0 / minimum_q,
                           bound_error=bound_error))

            retained = np.arange(0, size, 2)
            eliminated = np.arange(1, size, 2)
            q_rr = q_primary[np.ix_(retained, retained)]
            q_re = q_primary[np.ix_(retained, eliminated)]
            q_ee = q_primary[np.ix_(eliminated, eliminated)]
            q_eff = q_rr - q_re @ np.linalg.solve(q_ee, q_re.T)
            q_inverse_rr = np.linalg.inv(q_primary)[np.ix_(retained, retained)]
            marginal_error = normalized_error(np.linalg.inv(q_eff), q_inverse_rr)
            check(result, f"Gaussian Schur marginal N={size} m={mass}",
                  marginal_error <= MATRIX_TOLERANCE, marginal_error)

            covariance_q = q_inverse_rr / 2.0
            covariance_p = q_rr / 2.0
            pure_marginal_p = q_eff / 2.0
            momentum_difference = covariance_p - pure_marginal_p
            difference_expected = q_re @ np.linalg.solve(q_ee, q_re.T) / 2.0
            positivity_floor = float(np.min(np.linalg.eigvalsh(momentum_difference)))
            momentum_error = normalized_error(momentum_difference, difference_expected)
            symplectic = symplectic_values(covariance_q, covariance_p)
            check(result, f"reduced momentum and mixed-state witness N={size} m={mass}",
                  momentum_error <= MATRIX_TOLERANCE
                  and positivity_floor >= -MATRIX_TOLERANCE
                  and float(np.max(symplectic)) > 0.5 + MIXED_MARGIN,
                  dict(momentum_error=momentum_error,
                       positivity_floor=positivity_floor,
                       symplectic_min=float(np.min(symplectic)),
                       symplectic_max=float(np.max(symplectic))))

            result["gaussian_rows"].append(dict(
                size=size, mass=mass, dirichlet=d_laplacian.tolist(),
                precision=q_primary.tolist(), sine_precision=q_sine.tolist(),
                square_root_reconstruction_error=reconstruction_error,
                precision_diagonal=diagonal.tolist(),
                minimum_precision_eigenvalue=minimum_q,
                global_poincare_gap=2.0 * minimum_q,
                conditional_poincare_gaps=(2.0 * diagonal).tolist(),
                normalized_precision=correlation_precision.tolist(),
                approximate_tensorization=tensorization,
                linear_saturation_ratio=float(linear_ratio),
                retained=retained.tolist(), eliminated=eliminated.tolist(),
                marginal_precision=q_eff.tolist(),
                retained_position_covariance=covariance_q.tolist(),
                retained_momentum_covariance=covariance_p.tolist(),
                pure_marginal_momentum_covariance=pure_marginal_p.tolist(),
                discarded_momentum_term=momentum_difference.tolist(),
                symplectic_eigenvalues=symplectic.tolist()))

    uncoupled = np.diag((1.0, 2.0, 3.0, 4.0))
    retained, eliminated = np.array((0, 2)), np.array((1, 3))
    q_rr = uncoupled[np.ix_(retained, retained)]
    q_re = uncoupled[np.ix_(retained, eliminated)]
    q_ee = uncoupled[np.ix_(eliminated, eliminated)]
    q_eff = q_rr - q_re @ np.linalg.solve(q_ee, q_re.T)
    covariance_q = np.linalg.inv(uncoupled)[np.ix_(retained, retained)] / 2.0
    covariance_p = q_rr / 2.0
    symplectic = symplectic_values(covariance_q, covariance_p)
    check(result, "uncoupled Gaussian reduction control",
          normalized_error(q_rr - q_eff, np.zeros_like(q_rr)) <= MATRIX_TOLERANCE
          and normalized_error(symplectic, np.full(len(retained), 0.5)) <= MATRIX_TOLERANCE,
          dict(momentum_difference=(q_rr - q_eff).tolist(),
               symplectic_eigenvalues=symplectic.tolist()))
    result["uncoupled_gaussian"] = dict(
        precision=uncoupled.tolist(), retained=retained.tolist(), eliminated=eliminated.tolist(),
        marginal_precision=q_eff.tolist(),
        momentum_difference=((q_rr - q_eff) / 2.0).tolist(),
        symplectic_eigenvalues=symplectic.tolist())


def inventory_controls(result):
    local_keys = [(row["fixture"], row["x"], row["kappa_label"])
                  for row in result["local_energy_rows"]]
    gaussian_keys = [(row["size"], row["mass"]) for row in result["gaussian_rows"]]
    check(result, "complete unique local-energy schedule",
          len(local_keys) == 45 and len(local_keys) == len(set(local_keys)),
          dict(rows=len(local_keys), unique=len(set(local_keys))))
    check(result, "complete unique connected Gaussian schedule",
          len(gaussian_keys) == 10 and len(gaussian_keys) == len(set(gaussian_keys))
          and set(gaussian_keys) == {(size, mass) for size in GAUSSIAN_SIZES
                                    for mass in GAUSSIAN_MASSES},
          gaussian_keys)
    check(result, "complete fixture and same-character schedules",
          [row["name"] for row in result["group_fixtures"]]
          == ["identity", "commuting", "noncommuting_0", "noncommuting_1", "noncommuting_2"]
          and [row["label"] for row in result["same_character_rows"]]
          == ["parallel", "orthogonal", "antiparallel"],
          dict(fixtures=[row["name"] for row in result["group_fixtures"]],
               same_character=[row["label"] for row in result["same_character_rows"]]))


def compute(result):
    result.update(checks=[], failures=[])
    symbolic_controls(result)
    group_controls(result)
    gaussian_controls(result)
    inventory_controls(result)
    success = not result["failures"]
    massless_rows = [row for row in result["gaussian_rows"] if row["mass"] == 0.0]
    result.update(
        status="PASS" if success else "FAIL",
        check_count=len(result["checks"]),
        classifications=dict(
            finite_group_and_derivative_controls="SUPPORTS" if success else "INCONCLUSIVE",
            Gaussian_block_identities="SUPPORTS" if success else "INCONCLUSIVE",
            conditional_gap_only_uniform_implication="CONTRADICTS" if success else "INCONCLUSIVE",
            exact_trial_vacuum="REQUIRES_ANALYTICAL_RECONCILIATION",
            weighted_cover_gap="REQUIRES_ANALYTICAL_RECONCILIATION",
            exact_quantum_block_map="REQUIRES_ANALYTICAL_RECONCILIATION",
            continuum_mass_gap="UNRESOLVED"),
        measured_summary=dict(
            maximum_group_identity_error=max(max(row["identity_errors"].values())
                                             for row in result["group_fixtures"]),
            maximum_gauge_invariance_error=max(row["gauge_invariance_error"]
                                               for row in result["group_fixtures"]),
            maximum_first_derivative_error=max(
                fd["maximum_first_derivative_error"]
                for row in result["local_energy_rows"] for fd in row["finite_difference"]),
            maximum_local_energy_normalized_error=max(
                fd["local_energy_normalized_error"]
                for row in result["local_energy_rows"] for fd in row["finite_difference"]),
            maximum_gaussian_square_root_error=max(
                row["square_root_reconstruction_error"] for row in result["gaussian_rows"]),
            massless_tensorization_by_size=[dict(size=row["size"],
                                                  value=row["approximate_tensorization"])
                                             for row in massless_rows]),
        scope=dict(
            finite_rows="GROUP_AND_GAUSSIAN_CONTROLS_ONLY",
            trial_vacuum="ONE_PLAQUETTE_EXPONENTIAL_FAMILY_ONLY",
            interacting_vacuum_tensorization="UNRESOLVED",
            infinite_volume_GNS_gap="NOT_ESTABLISHED",
            continuum_construction="UNRESOLVED",
            continuum_mass="UNRESOLVED",
            cassi_microscopic_identification="UNRESOLVED"))
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path, snapshot_dir = output.with_suffix(".inputs.json"), output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = dict(protocol=PROTOCOL, verifier=Path(__file__).resolve(),
                   receipt_helper=Path(receipt_checks.__file__).resolve())
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: dict(path=path.relative_to(ROOT).as_posix(),
                            sha256=hashlib.sha256(payloads[key]).hexdigest())
                  for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[key])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), identities=identities,
                    numpy_version=np.__version__, sympy_version=sp.__version__)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
    result = dict(schema="cassi.yang-mills.vacuum-blocks.v1", **manifest)
    success = False
    try:
        success = compute(result)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in
                      ("status", "check_count", "classifications", "failures",
                       "measured_summary", "error")}, indent=2))
    if success and result.get("status") == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
