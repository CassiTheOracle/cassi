"""Check derived next-generation field identities and important counterexamples.

These are small CPU/float64 mathematical checks, not a next-generation runtime
or a capability benchmark. They leave the variational source and all production
checkpoints untouched. Run from CassiFI with --output for a retained JSON result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from cassi_variational_field import VariationalField


def _energy(covariance: Tensor, observation: Tensor, ridge: float) -> Tensor:
    inverse = torch.linalg.inv(covariance)
    dimension = len(observation)
    return 0.5 * (
        torch.linalg.slogdet(covariance).logabsdet
        - dimension * math.log(ridge)
        + ridge * torch.trace(inverse)
        - dimension
        + observation @ inverse @ observation
    )


def _quadratic(hessian: Tensor, state: Tensor, force: Tensor | None = None) -> Tensor:
    value = 0.5 * state @ hessian @ state
    return value if force is None else value - force @ state

def _model_uncertainty_action_bound() -> dict[str, Any]:
    """Check a frozen linear model perturbation bound and its scope limits."""
    dtype = torch.float64
    A = torch.tensor([[2.0, 0.3], [0.3, 1.5]], dtype=dtype)
    B = torch.tensor([[0.7, -0.2], [0.1, 0.9]], dtype=dtype)
    b = torch.tensor([0.8, -0.6], dtype=dtype)
    c_u = torch.tensor([-1.0, 1.0], dtype=dtype)
    c_o = torch.tensor([0.3, 0.2], dtype=dtype)
    alpha, beta, radius = 0.05, 0.04, 0.05
    mu = float(torch.linalg.eigvalsh(A).min())
    K = -torch.linalg.solve(A, B)
    nominal = float(c_u @ (K @ b) + c_o @ b)
    input_term = radius * float(torch.linalg.vector_norm(K.T @ c_u + c_o))
    gamma_k = (beta + alpha * float(torch.linalg.matrix_norm(K, ord=2))) / (mu - alpha)
    model_term = float(torch.linalg.vector_norm(c_u)) * gamma_k * (
        float(torch.linalg.vector_norm(b)) + radius
    )
    total_bound = input_term + model_term
    assert abs(nominal - 0.9041924398625429) < 1e-12
    assert abs(input_term - 0.04557805231287515) < 1e-12
    assert abs(model_term - 0.08388602006513335) < 1e-12
    assert abs(total_bound - 0.1294640723780085) < 1e-12
    sensor_direction = K.T @ c_u + c_o
    sensor_delta = -radius * sensor_direction / torch.linalg.vector_norm(sensor_direction)
    sensor_witness_change = float(sensor_direction @ sensor_delta)
    assert abs(sensor_witness_change + input_term) < 1e-12

    generator_seed = 2026090501
    generator = torch.Generator().manual_seed(generator_seed)
    sampled_errors: list[float] = []
    maximum_resolvent_error = 0.0
    for _ in range(100):
        e_raw = torch.randn((2, 2), generator=generator, dtype=dtype)
        e_raw = (e_raw + e_raw.T) / 2.0
        E = alpha * e_raw / float(torch.linalg.matrix_norm(e_raw, ord=2))
        d_raw = torch.randn((2, 2), generator=generator, dtype=dtype)
        D = beta * d_raw / float(torch.linalg.matrix_norm(d_raw, ord=2))
        db_raw = torch.randn(2, generator=generator, dtype=dtype)
        db = radius * db_raw / float(torch.linalg.vector_norm(db_raw))
        K_new = -torch.linalg.solve(A + E, B + D)
        changed = float(c_u @ (K_new @ (b + db)) + c_o @ (b + db) - nominal)
        sampled_errors.append(abs(changed))
        resolvent = (A + E) @ (K_new - K) + D + E @ K
        resolvent_error = float(torch.linalg.vector_norm(resolvent))
        maximum_resolvent_error = max(maximum_resolvent_error, resolvent_error)
        assert resolvent_error < 1e-12
        assert float(torch.linalg.matrix_norm(K_new - K, ord=2)) <= gamma_k + 1e-12
        assert abs(changed) <= total_bound + 1e-12

    # A sign-flipped B is outside the declared D-ball and reverses the model.
    D_outside = -2.0 * B
    K_outside = -torch.linalg.solve(A, B + D_outside)
    assert float(torch.linalg.matrix_norm(D_outside, ord=2)) > beta
    outside_score = float(c_u @ (K_outside @ b) + c_o @ b)
    assert outside_score < 0.0 and nominal - total_bound > 0.0
    _, eigenvectors = torch.linalg.eigh(A)
    boundary_matrix = A - mu * torch.outer(eigenvectors[:, 0], eigenvectors[:, 0])
    boundary_eigenvalue = float(torch.linalg.eigvalsh(boundary_matrix).min())
    assert abs(boundary_eigenvalue) < 1e-12
    return {
        "nominal_score": nominal,
        "input_radius_term": input_term,
        "model_uncertainty_term": model_term,
        "conservative_total_bound": total_bound,
        "gamma_K": gamma_k,
        "generator_seed": generator_seed,
        "sensor_only_witness_absolute_error": abs(sensor_witness_change + input_term),
        "maximum_resolvent_absolute_error": maximum_resolvent_error,
        "sample_count": len(sampled_errors),
        "sampled_max_absolute_score_change": max(sampled_errors),
        "sampled_error_to_bound_ratio": max(sampled_errors) / total_bound,
        "sampled_fraction_within_bound": sum(
            error <= total_bound + 1e-12 for error in sampled_errors
        )
        / len(sampled_errors),
        "outside_set_opposite_action_score": outside_score,
        "singular_boundary_min_eigenvalue": boundary_eigenvalue,
        "boundary": (
            "The input term is attained sensor-only radius; total joint attainment "
            "is not established. A sampled fraction neither proves nor disproves "
            "joint attainability. Actions not ruled out are not safe or permitted "
            "actions, and nonlinear/KKT branches are outside this bound."
        ),
    }


def _query_adjoint_error_certificate() -> dict[str, Any]:
    """Check exact and imperfect adjoint residual certificates."""
    dtype = torch.float64
    A = torch.diag(torch.tensor([1e-6, 1.0], dtype=dtype))
    exact = torch.tensor([0.0, 1.0], dtype=dtype)
    approximate = torch.tensor([1000.0, 1.001], dtype=dtype)
    f = A @ exact
    c = torch.tensor([0.0, 1.0], dtype=dtype)
    p = torch.linalg.solve(A.T, c)
    phat = p + torch.tensor([1e-6, 1e-9], dtype=dtype)
    residual = A @ approximate - f
    adjoint_residual = A.T @ phat - c
    score_error = float(c @ (approximate - exact))
    exact_identity_error = abs(score_error - float(p @ residual))
    mu = float(torch.linalg.eigvalsh(A).min())
    imperfect_bound = abs(float(phat @ residual)) + float(
        torch.linalg.vector_norm(adjoint_residual)
        * torch.linalg.vector_norm(residual)
        / mu
    )
    assert exact_identity_error < 1e-12
    assert float(torch.linalg.vector_norm(adjoint_residual)) > 0.0
    assert score_error <= imperfect_bound
    approximate_score = float(c @ approximate)
    assert approximate_score - 0.9 > imperfect_bound
    assert 0.0 < approximate_score - 1.0005 <= imperfect_bound
    assert float(c @ exact) - 1.0005 < 0.0
    bad_mu = float(torch.linalg.eigvalsh(torch.diag(torch.tensor([0.0, 1.0]))).min())
    assert bad_mu <= 0.0
    return {
        "state_error_norm": float(torch.linalg.vector_norm(approximate - exact)),
        "score_error": score_error,
        "global_residual_norm": float(torch.linalg.vector_norm(residual)),
        "global_residual_bound_on_state_error": float(torch.linalg.vector_norm(residual)) / mu,
        "exact_adjoint_identity_absolute_error": exact_identity_error,
        "imperfect_adjoint_residual_norm": float(
            torch.linalg.vector_norm(adjoint_residual)
        ),
        "imperfect_score_error_bound": imperfect_bound,
        "separated_competitor_numerically_certified": approximate_score - 0.9 > imperfect_bound,
        "close_competitor_not_certified": approximate_score - 1.0005 <= imperfect_bound,
        "singular_conditional_refused": True,
        "boundary": (
            "A final conditional block (H_UU) is distinct from one implicit step "
            "(I/h+H_UU); a local certificate is not global settlement. Unbounded "
            "omitted factors prevent a sparse claim or performance claim."
        ),
    }


def _interference_budget_and_numerics() -> dict[str, Any]:
    """Check assembled-precision locality, flow drift, and numerical budgets."""
    dtype = torch.float64
    S = torch.tensor(
        [[2.0, 0.6, 0.4], [0.6, 1.5, 0.5], [0.4, 0.5, 1.8]], dtype=dtype
    )
    precision = torch.linalg.inv(S)
    w = torch.tensor([0.0, 0.0, 1.0], dtype=dtype)
    S_additive = S + 0.7 * torch.outer(w, w)
    precision_additive = torch.linalg.inv(S_additive)
    free_indices = torch.tensor([0, 2])
    free_before = float(torch.linalg.solve(
        precision[free_indices[:, None], free_indices], -precision[free_indices, 1]
    )[0])
    free_after = float(torch.linalg.solve(
        precision_additive[free_indices[:, None], free_indices], -precision_additive[free_indices, 1]
    )[0])
    observed = torch.tensor([1.0, 1.0], dtype=dtype)
    indices = torch.tensor([1, 2])
    clamp_before = float(S[0, indices] @ torch.linalg.solve(S[indices[:, None], indices], observed))
    clamp_after = float(
        S_additive[0, indices]
        @ torch.linalg.solve(S_additive[indices[:, None], indices], observed)
    )
    extra_precision = precision + torch.diag(torch.tensor([0.0, 0.0, 1.0], dtype=dtype))
    S_extra = torch.linalg.inv(extra_precision)
    S_extra_additive = torch.linalg.inv(
        precision_additive + torch.diag(torch.tensor([0.0, 0.0, 1.0], dtype=dtype))
    )
    extra_before = float(S_extra[0, 1] / S_extra[1, 1])
    extra_after = float(S_extra_additive[0, 1] / S_extra_additive[1, 1])
    assert abs(free_before - 0.4) < 1e-12
    assert abs(free_after - 0.4) < 1e-12
    assert abs(clamp_before - 0.4816326530612245) < 1e-12
    assert abs(clamp_after - 0.45714285714285713) < 1e-12
    assert abs(extra_before - 0.37468354430379736) < 1e-12
    assert abs(extra_after - 0.38) < 1e-12
    assert abs(float(precision_additive[0, 1] - precision[0, 1])) > 1e-3

    g, ridge = 0.2, 0.1
    # These are actually observed coordinates T=0 and O=0, with W=1; they are
    # not missing-value zero padding.
    x = torch.tensor([0.0, 0.0, 1.0], dtype=dtype)
    Q = torch.outer(x, x) + ridge * torch.eye(3, dtype=dtype)
    flow = (1.0 - g) * S + g * Q
    flow_ratio = float(flow[0, 1] / flow[1, 1])
    exact_relative_drift = g * ridge / ((1.0 - g) * float(S[1, 1]) + g * ridge)
    admissions = 3
    a = (1.0 - g) ** admissions
    repeated_flow = a * S + (1.0 - a) * Q
    repeated_ratio = float(repeated_flow[0, 1] / repeated_flow[1, 1])
    repeated_formula_ratio = float(
        S[0, 1] / (S[1, 1] + ridge * (a**-1.0 - 1.0))
    )
    assert abs(flow_ratio - 0.3934426229508197) < 1e-12
    assert abs(abs(flow_ratio - free_before) - 0.0065573770491803) < 1e-12
    assert abs(exact_relative_drift - 0.01639344262295082) < 1e-12
    assert abs(repeated_ratio - repeated_formula_ratio) < 1e-12

    # A fixed-profile float64 allowance is an engineering estimate, not interval arithmetic.
    S0 = torch.tensor([[1.0, 0.5], [0.5, 2.0]], dtype=dtype)
    x0 = torch.tensor([2.0, -1.0], dtype=dtype)
    Q0 = torch.outer(x0, x0) + 0.1 * torch.eye(2, dtype=dtype)
    target = 0.09
    g_cap = target / (4.05 - 3.1 * target)
    successor = (1.0 - g_cap) * S0 + g_cap * Q0
    beta_old = float(S0[1, 0] / S0[0, 0])
    beta_new = float(successor[1, 0] / successor[0, 0])
    actual_change = abs(beta_new - beta_old)
    condition = float(
        torch.linalg.matrix_norm(S0, ord=2)
        * torch.linalg.matrix_norm(torch.linalg.inv(S0), ord=2)
    )
    arithmetic_allowance = 128.0 * torch.finfo(dtype).eps * condition * (
        1.0 + float(torch.linalg.matrix_norm(successor, ord=2))
    )
    assert actual_change + arithmetic_allowance < 0.1
    from fractions import Fraction

    exact_target = Fraction(9, 100)
    exact_g = exact_target / (Fraction(405, 100) - Fraction(31, 10) * exact_target)
    exact_change = Fraction(405, 100) * exact_g / (1 + Fraction(31, 10) * exact_g)
    assert exact_change == exact_target
    exact_stored_change = abs(
        Fraction.from_float(float(successor[1, 0]))
        / Fraction.from_float(float(successor[0, 0])) - Fraction(1, 2)
    )
    query_arithmetic_error = abs(Fraction.from_float(actual_change) - exact_stored_change)
    assert float(query_arithmetic_error) <= arithmetic_allowance
    assert exact_stored_change + Fraction.from_float(arithmetic_allowance) < Fraction(1, 10)
    ill_covariance = torch.diag(torch.tensor([1.0, 1e-14], dtype=dtype))
    ill_condition = float(
        torch.linalg.matrix_norm(ill_covariance, ord=2)
        * torch.linalg.matrix_norm(torch.linalg.inv(ill_covariance), ord=2)
    )
    ill_allowance = 128.0 * torch.finfo(dtype).eps * ill_condition
    assert ill_allowance > 0.1 and ill_condition > condition
    Aplus = torch.tensor([[1.4, 0.1], [0.1, 1.1]], dtype=dtype)
    delta_a = torch.tensor([[0.2, 0.05], [0.05, 0.3]], dtype=dtype)
    delta_b = torch.tensor([[0.1, -0.2], [0.3, 0.4]], dtype=dtype)
    u = torch.tensor([0.5, -0.4], dtype=dtype)
    b_bound = torch.tensor([0.2, 0.7], dtype=dtype)
    A_free = Aplus - delta_a
    B_free = -torch.outer(A_free @ u, b_bound) / (b_bound @ b_bound)
    u = torch.linalg.solve(A_free, -B_free @ b_bound)
    successor_u = torch.linalg.solve(Aplus, -(B_free + delta_b) @ b_bound)
    v = -torch.linalg.solve(Aplus, delta_a @ u + delta_b @ b_bound)
    exact_update_identity_error = float(torch.linalg.vector_norm(successor_u - u - v))
    assert exact_update_identity_error < 1e-12
    eplus_matrix = torch.tensor([[1e-6, 2e-7], [2e-7, -1e-6]], dtype=dtype)
    ea_matrix = torch.tensor([[3e-7, -1e-7], [-1e-7, 2e-7]], dtype=dtype)
    eb_matrix = torch.tensor([[2e-7, 1e-7], [-1e-7, 3e-7]], dtype=dtype)
    Aplus_hat = Aplus + eplus_matrix
    delta_a_hat = delta_a + ea_matrix
    delta_b_hat = delta_b + eb_matrix
    u_hat = u + torch.tensor([2e-7, -1e-7], dtype=dtype)
    v_hat = v + torch.tensor([1e-6, -2e-6], dtype=dtype)
    eplus = float(torch.linalg.matrix_norm(eplus_matrix, ord=2))
    e_a = float(torch.linalg.matrix_norm(ea_matrix, ord=2))
    e_b = float(torch.linalg.matrix_norm(eb_matrix, ord=2))
    e_u = float(torch.linalg.vector_norm(u_hat - u))
    residual_bar = float(
        torch.linalg.vector_norm(Aplus_hat @ v_hat + delta_a_hat @ u_hat + delta_b_hat @ b_bound)
    )
    muplus = float(torch.linalg.eigvalsh(Aplus).min())
    true_update_bound = (
        residual_bar
        + eplus * float(torch.linalg.vector_norm(v_hat))
        + e_a * float(torch.linalg.vector_norm(u_hat))
        + (float(torch.linalg.matrix_norm(delta_a_hat, ord=2)) + e_a) * e_u
        + e_b * float(torch.linalg.vector_norm(b_bound))
    ) / muplus
    actual_update_error = float(torch.linalg.vector_norm(v_hat - v))
    query = torch.tensor([0.7, -0.2], dtype=dtype)
    query_rounding_allowance = 64.0 * torch.finfo(dtype).eps * float(
        torch.linalg.vector_norm(query) * (1.0 + torch.linalg.vector_norm(v_hat))
    )
    assert muplus > 0.0
    assert actual_update_error <= true_update_bound + 1e-12
    assert abs(float(query @ (v_hat - v))) <= float(
        torch.linalg.vector_norm(query)
    ) * true_update_bound + query_rounding_allowance
    return {
        "block_additive_locality": {
            "free_mean_before": free_before,
            "free_mean_after": free_after,
            "precision_TO_before": float(precision[0, 1]),
            "precision_TO_after": float(precision_additive[0, 1]),
            "clamped_mean_before": clamp_before,
            "clamped_mean_after": clamp_after,
            "extra_precision_free_mean_before": extra_before,
            "extra_precision_free_mean_after": extra_after,
        },
        "ridge_flow": {
            "actually_observed_coordinates": {"T": 0.0, "O": 0.0, "W": 1.0},
            "ratio_before": free_before,
            "ratio_after": flow_ratio,
            "absolute_drift": abs(flow_ratio - free_before),
            "exact_relative_drift": exact_relative_drift,
            "repeated_admissions": admissions,
            "retention_factor_a": a,
            "repeated_ratio": repeated_ratio,
            "repeated_formula_ratio": repeated_formula_ratio,
        },
        "exposure_cap": {
            "target_strictly_below_tolerance": target < 0.1,
            "g_cap": g_cap,
            "actual_query_change": actual_change,
            "conditioning": condition,
            "float64_arithmetic_allowance": arithmetic_allowance,
            "fraction_audit_target": float(exact_change),
            "stored_successor_exact_query_change": float(exact_stored_change),
            "query_arithmetic_absolute_error": float(query_arithmetic_error),
            "alternate_spd_profile_conditioning": ill_condition,
            "alternate_profile_allowance_exceeds_tolerance": ill_allowance > 0.1,
            "alternate_profile_allowance": ill_allowance,
        },
        "update_residual_bound": {
            "exact_update_identity_absolute_error": exact_update_identity_error,
            "assembled_precision_min_eigenvalue": muplus,
            "computed_equation_residual": residual_bar,
            "eplus": eplus,
            "eA": e_a,
            "eB": e_b,
            "eu": e_u,
            "true_update_error_norm": actual_update_error,
            "true_update_error_bound": true_update_bound,
            "query_rounding_allowance": query_rounding_allowance,
        },
        "boundary": (
            "A is assembled precision, not covariance; DeltaA and DeltaSigma are "
            "different. Residual, both block errors, and query rounding must be "
            "defensible bounds. Partial exposure preserves event identity and "
            "unexposed remainder; no lifetime noninterference is claimed."
        ),
    }


def _compositional_macro_margin() -> dict[str, Any]:
    """Check the directed product-ball lower bound and an attaining witness."""
    dtype = torch.float64
    K1 = torch.tensor([[1.0, 0.2], [0.0, 0.8]], dtype=dtype)
    K2 = torch.tensor([[0.9, 0.0], [0.1, 1.1]], dtype=dtype)
    x = torch.tensor([0.8, -0.3], dtype=dtype)
    d = torch.tensor([0.0, -2.0], dtype=dtype)
    radius, eps1, eps2 = 0.05, 0.02, 0.03
    F0, F1, F2 = K2 @ K1, K2, torch.eye(2, dtype=dtype)
    nominal = float(d @ F0 @ x)
    terms = [
        radius * float(torch.linalg.vector_norm(F0.T @ d)),
        eps1 * float(torch.linalg.vector_norm(F1.T @ d)),
        eps2 * float(torch.linalg.vector_norm(F2.T @ d)),
    ]
    lower = nominal - sum(terms)

    def opposite(direction: Tensor, amount: float) -> Tensor:
        return -amount * direction / torch.linalg.vector_norm(direction)

    x_error = opposite(F0.T @ d, radius)
    e1 = opposite(F1.T @ d, eps1)
    e2 = opposite(F2.T @ d, eps2)
    witness = float(d @ (F0 @ (x + x_error) + F1 @ e1 + e2))
    assert abs(nominal - 0.38) < 1e-12
    assert abs(terms[0] - 0.09055385138137419) < 1e-12
    assert abs(terms[1] - 0.04418144406874904) < 1e-12
    assert abs(terms[2] - 0.06) < 1e-12
    assert abs(lower - 0.18526470454987679) < 1e-12
    assert abs(witness - lower) < 1e-12
    assert float(torch.linalg.vector_norm(x_error)) <= radius + 1e-15
    assert float(torch.linalg.vector_norm(e1)) <= eps1 + 1e-15
    assert float(torch.linalg.vector_norm(e2)) <= eps2 + 1e-15
    tube_displacement_bound = radius * float(torch.linalg.matrix_norm(F0, ord=2)) + eps1 * float(
        torch.linalg.matrix_norm(F1, ord=2)
    ) + eps2
    outside_domain_refused = tube_displacement_bound > 0.02
    assert outside_domain_refused
    return {
        "nominal_score": nominal,
        "budget_terms": terms,
        "product_ball_lower_bound": lower,
        "attaining_witness_score": witness,
        "witness_absolute_error": abs(witness - lower),
        "tube_displacement_bound": tube_displacement_bound,
        "outside_domain_refused": outside_domain_refused,
        "boundary": (
            "The product set controls sharpness without stochastic independence. "
            "Directed application is not global overlapping-factor completion, and "
            "coupled disturbances need not jointly attain the displayed minimum."
        ),
    }


def _consequence_preserving_quotient() -> dict[str, Any]:
    """Check finite-test consequence quotient transfer and passive alias limits."""
    dtype = torch.float64
    risks = torch.tensor([[0.49, 0.51], [0.59, 0.41]], dtype=dtype)
    diameter = float(torch.max(torch.abs(risks[0] - risks[1])))
    representative = int(torch.argmin(risks[0]))
    new_excess = float(risks[1, representative] - torch.min(risks[1]))
    assert abs(diameter - 0.1) < 1e-12
    assert representative == 0
    assert abs(new_excess - 0.18) < 1e-12 and new_excess <= 2.0 * diameter
    x1 = torch.tensor([0.0, 1.0], dtype=dtype)
    x2_zero = torch.zeros(2, dtype=dtype)
    x2_one = torch.ones(2, dtype=dtype)
    alias_zero = torch.bitwise_xor(x1.to(torch.int64), x2_zero.to(torch.int64))
    alias_one = torch.bitwise_xor(x1.to(torch.int64), x2_one.to(torch.int64))
    assert torch.equal(x1.to(torch.int64), alias_zero)
    assert not torch.equal(x1.to(torch.int64), alias_one)
    return {
        "risk_table": risks.tolist(),
        "risk_diameter": diameter,
        "representative_action": representative,
        "transfer_optimize_transfer_excess": new_excess,
        "factor_two_bound": 2.0 * diameter,
        "passive_alias_agrees_when_x2_zero": True,
        "passive_alias_separates_when_x2_one": True,
        "boundary": (
            "Equivalence is only relative to declared finite traces and authorized "
            "interventions, not source identity. Bounded-diameter partitions, "
            "guards, support, and unresolved obligations remain; passive agreement "
            "does not guarantee an unperformed intervention."
        ),
    }


def _decision_directed_inquiry() -> dict[str, Any]:
    """Check cross-action separation, same-action overlap, and refusal semantics."""
    dtype = torch.float64
    actions = torch.tensor([0, 0, 1])
    radius = 0.1
    probe = torch.tensor([0.0, 2.0, 0.0], dtype=dtype)
    decision = torch.tensor([0.0, 0.05, 1.0], dtype=dtype)

    def cross_action_separation(centers: Tensor) -> float:
        gaps = [
            abs(float(centers[i] - centers[j])) - 2.0 * radius
            for i in range(len(centers))
            for j in range(i)
            if actions[i] != actions[j]
        ]
        return min(gaps)

    def k_value(centers: Tensor) -> int:
        endpoints = sorted(
            {float(center + sign * radius) for center in centers for sign in (-1.0, 1.0)}
        )
        points = endpoints + [(left + right) / 2.0 for left, right in zip(endpoints, endpoints[1:])]
        return max(
            len({int(actions[i]) for i, center in enumerate(centers) if abs(y - float(center)) <= radius + 1e-15})
            for y in points
        )

    probe_gap = cross_action_separation(probe)
    decision_gap = cross_action_separation(decision)
    probe_k, decision_k = k_value(probe), k_value(decision)
    touching = torch.tensor([0.0, 0.2], dtype=dtype)
    touching_gap = abs(float(touching[1] - touching[0])) - 2.0 * radius
    outside_outcome = 2.0
    outside_union_refused = not any(abs(outside_outcome - float(center)) <= radius for center in decision)
    assert abs(probe_gap - (-0.2)) < 1e-12
    assert abs(decision_gap - 0.75) < 1e-12
    assert probe_k == 2 and decision_k == 1
    assert touching_gap == 0.0
    assert outside_union_refused
    return {
        "probe_cross_action_separation_after_inflation": probe_gap,
        "decision_cross_action_separation_after_inflation": decision_gap,
        "probe_K_q": probe_k,
        "decision_K_q": decision_k,
        "selected_query": "decision",
        "touching_closed_intervals_unresolved": True,
        "outside_union_outcome_refused": outside_union_refused,
        "boundary": (
            "Outcome sets are inflated for declared sensor/model errors. Same-action "
            "alternatives may overlap; an outside-union outcome is coverage/model-set "
            "failure, never a nearest-hypothesis fallback. A_h containment is not "
            "permission to act."
        ),
    }


def _prequential_prefix_selection() -> dict[str, Any]:
    """Check prefix/Kraft/time-bound arithmetic and unit loss-range assumptions."""
    losses = torch.tensor([0.0, 0.0, 1.0, 1.0], dtype=torch.float64)
    constant_predictions = torch.tensor([0.0, 0.0, 0.0, 0.0], dtype=torch.float64)
    context_predictions = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64)
    constant_loss = float(torch.sum(torch.abs(losses - constant_predictions)))
    context_loss = float(torch.sum(torch.abs(losses - context_predictions)))
    lambda_loss_per_bit = 0.3
    constant_score = constant_loss + lambda_loss_per_bit * 1
    context_score = context_loss + lambda_loss_per_bit * 4
    kraft = 2.0 ** -1 + 2.0 ** -4
    n, code_length, delta = 10000, 20, 0.05
    radius = math.sqrt(
        n / 2.0 * (code_length * math.log(2.0) + math.log(2.0 * n * (n + 1) / delta))
    ) / n
    conditional_interval_width = (1.0 - 0.3) - (-0.3)
    union_interval_width = 1.0 - (-1.0)
    mgf_gaps = []
    for mu in (0.0, 0.3, 1.0):
        for theta in (-8.0, -4.0, 0.0, 4.0, 8.0):
            mgf = (1.0 - mu) * math.exp(theta * (-mu)) + mu * math.exp(theta * (1.0 - mu))
            mgf_gaps.append(mgf - math.exp(theta * theta / 8.0))
    allocation_delta = delta * 2.0 ** -code_length
    finite_prefix_allocation = sum(
        allocation_delta / (index * (index + 1)) for index in range(1, 10001)
    )
    assert abs(constant_loss - 2.0) < 1e-12 and abs(context_loss - 1.0) < 1e-12
    assert abs(constant_score - 2.3) < 1e-12 and abs(context_score - 2.2) < 1e-12
    assert kraft <= 1.0 and abs(conditional_interval_width - 1.0) < 1e-12
    assert union_interval_width == 2.0
    assert max(mgf_gaps) <= 1e-14
    assert finite_prefix_allocation < allocation_delta
    assert abs(finite_prefix_allocation - allocation_delta * n / (n + 1)) < 1e-20
    assert abs(radius - 0.04241026043557475) < 1e-12
    return {
        "constant_rule": {"loss": constant_loss, "prefix_bits": 1, "score": constant_score},
        "context_rule": {"loss": context_loss, "prefix_bits": 4, "score": context_score},
        "kraft_sum": kraft,
        "n": n,
        "code_length": code_length,
        "delta": delta,
        "average_bound_radius": radius,
        "candidate_total_error_allocation": allocation_delta,
        "allocation_delta_pn": allocation_delta / (n * (n + 1)),
        "finite_prefix_allocation": finite_prefix_allocation,
        "conditional_centered_loss_interval_width": conditional_interval_width,
        "union_of_history_support_width": union_interval_width,
        "maximum_grid_mgf_gap": max(mgf_gaps),
        "boundary": (
            "Complete online rules are frozen before outcomes; late activation earns "
            "future evidence only, and uncoded fitted pages are invalid. This is an "
            "analytic arithmetic illustration, not empirical calibration or future-"
            "regime coverage; promotion preserves guards and applicability."
        ),
    }


def run() -> dict[str, Any]:
    torch.set_num_threads(1)
    generator = torch.Generator().manual_seed(20260905)
    dtype = torch.float64
    checks: dict[str, Any] = {}

    # The natural gradient is Sigma-Q, not the Euclidean derivative of energy.
    ridge = 0.2
    raw = torch.randn(3, 3, generator=generator, dtype=dtype)
    covariance = ridge * torch.eye(3, dtype=dtype) + raw @ raw.T / 8.0
    observation = torch.tensor([0.4, -0.7, 0.2], dtype=dtype)
    target = torch.outer(observation, observation) + ridge * torch.eye(3, dtype=dtype)
    direction = torch.randn(3, 3, generator=generator, dtype=dtype)
    direction = (direction + direction.T) / 2.0
    inverse = torch.linalg.inv(covariance)
    metric_pairing = 0.5 * torch.trace(inverse @ (covariance - target) @ inverse @ direction)
    epsilon = 1e-6
    numeric_derivative = (
        _energy(covariance + epsilon * direction, observation, ridge)
        - _energy(covariance - epsilon * direction, observation, ridge)
    ) / (2.0 * epsilon)
    derivative_error = abs(float(numeric_derivative - metric_pairing))
    assert derivative_error < 1e-7
    exposure = 0.7
    successor = math.exp(-exposure) * covariance + (-math.expm1(-exposure)) * target
    drop = float(_energy(covariance, observation, ridge) - _energy(successor, observation, ridge))
    rate = -0.5 * torch.trace(inverse @ (covariance - target) @ inverse @ (covariance - target))
    assert drop > 0.0 and float(rate) <= 0.0
    checks["metric_flow"] = {
        "directional_derivative_absolute_error": derivative_error,
        "fixed_observation_energy_drop": drop,
        "instantaneous_energy_rate": float(rate),
    }

    # Count-weighted exposure is the same exact flow with a different clock.
    mass, weight = 7.0, 0.4
    gain = weight / (mass + weight)
    weighted = (1.0 - gain) * covariance + gain * target
    timed = math.exp(-math.log1p(weight / mass)) * covariance + (
        -math.expm1(-math.log1p(weight / mass))
    ) * target
    restored = ((mass + weight) * weighted - weight * target) / mass
    flow_error = float(torch.max(torch.abs(weighted - timed)))
    removal_error = float(torch.max(torch.abs(restored - covariance)))
    assert flow_error < 1e-12 and removal_error < 1e-12
    assert float(torch.linalg.eigvalsh(weighted).min()) >= ridge - 1e-12
    checks["weighted_exposure_and_exact_contribution_removal"] = {
        "equivalent_exposure": math.log1p(weight / mass),
        "flow_absolute_error": flow_error,
        "retraction_absolute_error": removal_error,
        "boundary": "Removal assumes the exact original contribution and no intervening decay or lossy compaction.",
    }

    # An explicit constant coordinate admits affine relations with the same core.
    model = VariationalField(3, ((0, 1, 2),), ridge=1e-6, observation_norm_bound=4.0)
    field = model.initial_state()
    mass = 1.0
    for value in torch.linspace(-1.0, 1.0, 65, dtype=dtype):
        x = float(value)
        field = model.observe(field, 0, [1.0, x, 1.5 * x + 0.7], exposure=math.log1p(1.0 / mass))
        mass += 1.0
    matrix = model.covariance(field, 0)
    given = torch.tensor([1.0, 0.37], dtype=dtype)
    predicted = matrix[2, :2] @ torch.linalg.solve(matrix[:2, :2], given)
    truth = 1.5 * float(given[1]) + 0.7
    affine_error = abs(float(predicted) - truth)
    assert affine_error < 1e-4
    checks["affine_constant_anchor"] = {
        "observations": 65,
        "query": [1.0, 0.37],
        "prediction": float(predicted),
        "target": truth,
        "absolute_error": affine_error,
        "boundary": "Synthetic fully observed affine relation; no discovered feature or scope.",
    }

    # Curvature is not evidence: a witnessed zero and an untouched prior match.
    empty = model.initial_state()
    witnessed_zero = model.observe(empty, 0, [0.0, 0.0, 0.0], exposure=0.5)
    same_prior = torch.equal(model.covariance(empty, 0), model.covariance(witnessed_zero, 0))
    assert same_prior
    checks["prior_curvature_is_not_evidence"] = {
        "empty_and_witnessed_zero_covariances_identical": same_prior,
        "prior_precision_diagonal": 1.0 / model.ridge,
        "conclusion": "Evidence occupancy and provenance require separate field-resident typed support; covariance alone cannot encode them.",
    }

    # Without active factor coverage, zero residual can leave any estimate intact.
    zero_hessian = torch.zeros(2, 2, dtype=dtype)
    unsupported = torch.tensor([3.0, -7.0], dtype=dtype)
    unchanged = torch.linalg.solve(torch.eye(2, dtype=dtype) + zero_hessian, unsupported)
    assert torch.equal(unsupported, unchanged)
    checks["uncovered_workspace_nullspace"] = {
        "hessian_rank": int(torch.linalg.matrix_rank(zero_hessian)),
        "gradient_norm": float(torch.linalg.vector_norm(zero_hessian @ unsupported)),
        "unchanged_arbitrary_estimate": unchanged.tolist(),
        "conclusion": "Residual settlement does not establish identifiability or evidence support.",
    }

    # A common quadratic admits exact implicit and coordinate-block decrement laws.
    raw = torch.randn(4, 4, generator=generator, dtype=dtype)
    hessian = raw.T @ raw + 0.4 * torch.eye(4, dtype=dtype)
    initial = torch.randn(4, generator=generator, dtype=dtype)
    duration = 0.8
    implicit = torch.linalg.solve(torch.eye(4, dtype=dtype) + duration * hessian, initial)
    delta = implicit - initial
    measured_drop = _quadratic(hessian, initial) - _quadratic(hessian, implicit)
    predicted_drop = delta @ delta / duration + 0.5 * delta @ hessian @ delta
    decrement_error = abs(float(measured_drop - predicted_drop))
    minimum_curvature = float(torch.linalg.eigvalsh(hessian).min())
    gradient_ratio = float(torch.linalg.vector_norm(hessian @ implicit) / torch.linalg.vector_norm(hessian @ initial))
    contraction_bound = 1.0 / (1.0 + duration * minimum_curvature)
    assert decrement_error < 1e-10 and gradient_ratio <= contraction_bound + 1e-12
    block = torch.tensor([1, 3])
    rest = torch.tensor([0, 2])
    local_hessian = hessian[block[:, None], block[None, :]]
    local_force = hessian[block[:, None], rest[None, :]] @ initial[rest]
    block_successor = initial.clone()
    block_successor[block] = torch.linalg.solve(
        torch.eye(2, dtype=dtype) + duration * local_hessian,
        initial[block] - duration * local_force,
    )
    block_delta = block_successor[block] - initial[block]
    block_drop = _quadratic(hessian, initial) - _quadratic(hessian, block_successor)
    block_identity = block_delta @ block_delta / duration + 0.5 * block_delta @ local_hessian @ block_delta
    block_error = abs(float(block_drop - block_identity))
    assert block_error < 1e-10 and torch.equal(initial[rest], block_successor[rest])
    checks["global_and_block_implicit_inference"] = {
        "energy_decrement_identity_error": decrement_error,
        "free_gradient_contraction_ratio": gradient_ratio,
        "contraction_bound": contraction_bound,
        "block_energy_decrement_identity_error": block_error,
        "nonblock_workspace_unchanged": True,
    }

    # Affine constrained proximal inference preserves feasibility and descends.
    constraint = torch.tensor([[1.0, 1.0, 0.0, 0.0]], dtype=dtype)
    boundary = constraint @ initial
    system = torch.zeros(5, 5, dtype=dtype)
    system[:4, :4] = torch.eye(4, dtype=dtype) / duration + hessian
    system[:4, 4:] = constraint.T
    system[4:, :4] = constraint
    answer = torch.linalg.solve(system, torch.cat((initial / duration, boundary)))
    constrained = answer[:4]
    delta = constrained - initial
    constrained_drop = _quadratic(hessian, initial) - _quadratic(hessian, constrained)
    lower_bound = delta @ delta / duration + 0.5 * delta @ hessian @ delta
    constraint_error = float(torch.max(torch.abs(constraint @ constrained - boundary)))
    assert constraint_error < 1e-12 and float(constrained_drop - lower_bound) >= -1e-10
    checks["affine_constrained_inference"] = {
        "constraint_absolute_error": constraint_error,
        "energy_drop": float(constrained_drop),
        "decrement_lower_bound": float(lower_bound),
    }

    # Eliminating internal coordinates preserves the boundary objective, including
    # the induced linear term and constant; it does not preserve every query.
    boundary_indices = torch.tensor([0, 3])
    interior = torch.tensor([1, 2])
    hbb = hessian[boundary_indices[:, None], boundary_indices[None, :]]
    hbi = hessian[boundary_indices[:, None], interior[None, :]]
    hii = hessian[interior[:, None], interior[None, :]]
    force = torch.randn(4, generator=generator, dtype=dtype)
    boundary_value = torch.tensor([0.3, -0.8], dtype=dtype)
    interior_value = torch.linalg.solve(hii, force[interior] - hbi.T @ boundary_value)
    schur = hbb - hbi @ torch.linalg.solve(hii, hbi.T)
    reduced_force = force[boundary_indices] - hbi @ torch.linalg.solve(hii, force[interior])
    constant = -0.5 * force[interior] @ torch.linalg.solve(hii, force[interior])
    full = torch.empty(4, dtype=dtype)
    full[boundary_indices], full[interior] = boundary_value, interior_value
    full_energy = _quadratic(hessian, full, force)
    reduced_energy = _quadratic(schur, boundary_value, reduced_force) + constant
    schur_error = abs(float(full_energy - reduced_energy))
    assert schur_error < 1e-10 and float(torch.linalg.eigvalsh(schur).min()) > 0.0
    checks["schur_boundary_abstraction"] = {
        "boundary_objective_absolute_error": schur_error,
        "minimum_reduced_eigenvalue": float(torch.linalg.eigvalsh(schur).min()),
        "boundary": "The preserved boundary set and all source factors must be fixed; internal queries and new constraints require expansion.",
    }

    # Composition of conditional means is not global overlapping-factor inference.
    pair = torch.tensor([[1.0, 0.5], [0.5, 1.0]], dtype=dtype)
    inverse = torch.linalg.inv(pair)
    chain_hessian = torch.zeros(3, 3, dtype=dtype)
    for scope in (torch.tensor([0, 1]), torch.tensor([1, 2])):
        chain_hessian[scope[:, None], scope[None, :]] += inverse
    joint_completion = torch.linalg.solve(chain_hessian[1:, 1:], -chain_hessian[1:, 0])
    conditional_composition = float((pair[1, 0] / pair[0, 0]) ** 2)
    assert abs(float(joint_completion[1]) - conditional_composition) > 0.1
    checks["joint_completion_is_not_functional_composition"] = {
        "pair_second_moment": pair.tolist(),
        "start_value": 1.0,
        "sequential_conditional_result": conditional_composition,
        "global_joint_result": float(joint_completion[1]),
        "conclusion": "Repeated marginal regularization changes the global estimate; do not call the two computations identical.",
    }

    # Discrete alternatives must survive continuous completion as alternatives.
    branch_ridge = 1e-4
    positive = torch.outer(torch.tensor([1.0, 1.0], dtype=dtype), torch.tensor([1.0, 1.0], dtype=dtype))
    negative = torch.outer(torch.tensor([1.0, -1.0], dtype=dtype), torch.tensor([1.0, -1.0], dtype=dtype))
    positive += branch_ridge * torch.eye(2, dtype=dtype)
    negative += branch_ridge * torch.eye(2, dtype=dtype)
    averaged = 0.5 * (positive + negative)
    branch_values = [float(matrix[1, 0] / matrix[0, 0]) for matrix in (positive, negative)]
    pooled_value = float(averaged[1, 0] / averaged[0, 0])
    assert branch_values[0] > 0.99 and branch_values[1] < -0.99 and pooled_value == 0.0
    checks["contradiction_preserving_branches"] = {
        "branch_predictions": branch_values,
        "pooled_prediction": pooled_value,
        "conclusion": "The pooled minimum is neither supported discrete alternative.",
    }

    # Distinct coordinate selectors admit diagonal bounds with local profiles.
    atlas_hessian = torch.zeros(4, 4, dtype=dtype)
    lower_diagonal = torch.zeros(4, dtype=dtype)
    upper_diagonal = torch.zeros(4, dtype=dtype)
    profiles = (((0, 1), 0.2, 1.5, 0.75), ((1, 2, 3), 0.4, 1.0, 2.0))
    for scope, chart_ridge, chart_bound, chart_weight in profiles:
        indices = torch.tensor(scope)
        selector = torch.eye(4, dtype=dtype)[indices]
        vector = torch.randn(len(scope), generator=generator, dtype=dtype)
        vector *= 0.8 * chart_bound / torch.linalg.vector_norm(vector)
        chart_covariance = chart_ridge * torch.eye(len(scope), dtype=dtype) + 0.6 * torch.outer(vector, vector)
        atlas_hessian += chart_weight * selector.T @ torch.linalg.solve(chart_covariance, selector)
        lower_diagonal[indices] += chart_weight / (chart_ridge + chart_bound**2)
        upper_diagonal[indices] += chart_weight / chart_ridge
    lower_margin = float(torch.linalg.eigvalsh(atlas_hessian - torch.diag(lower_diagonal)).min())
    upper_margin = float(torch.linalg.eigvalsh(torch.diag(upper_diagonal) - atlas_hessian).min())
    assert lower_margin >= -1e-12 and upper_margin >= -1e-12
    assert float(lower_diagonal.min()) > 0.0
    checks["heterogeneous_chart_spectral_bounds"] = {
        "lower_diagonal": lower_diagonal.tolist(),
        "hessian_eigenvalues": torch.linalg.eigvalsh(atlas_hessian).tolist(),
        "upper_diagonal": upper_diagonal.tolist(),
        "minimum_lower_bound_psd_margin": lower_margin,
        "minimum_upper_bound_psd_margin": upper_margin,
        "boundary": "Distinct coordinate selectors, positive fixed weights, and individually admissible ridge/norm profiles.",
    }
    checks["model_uncertainty_action_bound"] = _model_uncertainty_action_bound()
    checks["query_adjoint_error_certificate"] = _query_adjoint_error_certificate()
    checks["interference_budget_and_numerics"] = _interference_budget_and_numerics()
    checks["compositional_macro_margin"] = _compositional_macro_margin()
    checks["consequence_preserving_quotient"] = _consequence_preserving_quotient()
    checks["decision_directed_inquiry"] = _decision_directed_inquiry()
    checks["prequential_prefix_selection"] = _prequential_prefix_selection()

    sources = (Path(__file__), Path(__file__).with_name("cassi_variational_field.py"))
    return {
        "scope": "finite mathematical identities and counterexamples for the next-generation design",
        "device": "cpu",
        "dtype": "torch.float64",
        "seed": 20260905,
        "sources_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
        "checks": checks,
        "boundaries": [
            "No full next-generation runtime is implemented by this script.",
            "The seven design extensions are checked derived identities or finite illustrations, not implemented runtime policies.",
            "The top-level seed drives the original eleven checks only; randomized extensions record their own generator_seed inside the check payload.",
            "Float64 scale allowances are not general validated interval certificates, and conservative combined bounds need not be jointly attained.",
            "No autonomous scope, concept, language or policy learning is demonstrated.",
            "Energy and curvature do not establish truth, calibrated confidence, authority or efficiency.",
            "No prototype or live host state is loaded or changed.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(), indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
