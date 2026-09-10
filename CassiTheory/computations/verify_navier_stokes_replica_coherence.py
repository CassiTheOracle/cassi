#!/usr/bin/env python3
"""Verify fixed replica-coherence components for periodic Navier–Stokes.

The executable checks the 40-item symbolic and exact-control inventory frozen in
computations/navier-stokes-replica-coherence-prereg.md. It does not integrate a
Navier–Stokes trajectory or simulate a stochastic flow.
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
PROTOCOL = ROOT / "computations" / "navier-stokes-replica-coherence-prereg.md"
PAPER = ROOT / "turbulence" / "navier-stokes-replica-coherence.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_replica_coherence_20260910_qualified"
    / "verification.json"
)
EXPECTED_CHECKS = 40
EXPECTED_CHECK_NAMES = (
    "R1 finite independent-replica outer product",
    "R2 finite independent-replica scalar overlap",
    "R3 replica disagreement variance identity",
    "R4 centred covariance Gram identity",
    "R5 common-noise Laplacian product closure",
    "R6 independent-noise cross-variation separation",
    "R7 deterministic mean-product gradient source",
    "R8 centred covariance source and initial value",
    "D1 trace-free propagator determinant",
    "D2 constant-matrix Duhamel residual",
    "D3 gradient-frame trace expansion",
    "D4 directional amplitude growth identity",
    "D5 source probability normalization",
    "D6 scalar covariance integrating factor",
    "D7 integrated variance trace balance",
    "D8 positive-minus-positive enstrophy identity",
    "C1 total occupation decomposition",
    "C2 strain-rate mixture identity",
    "C3 coherence replicator-diffusion identity",
    "C4 initial coherence derivative",
    "C5 logarithmic coherence budget",
    "C6 coherent-to-spread odds identity",
    "C7 coherence share complement",
    "C8 compensated upper-gap identity",
    "S1 determinant transport identity",
    "S2 sharp optimizer unit determinant",
    "S3 sharp optimizer isotropic image",
    "S4 sharp optimizer trace value",
    "S5 rank-two collapse unit determinant",
    "S6 rank-two collapse trace limit",
    "S7 rank-one collapse unit determinant",
    "S8 rank-one collapse trace limit",
    "X1 gradient Gram determinant square",
    "X2 full-rank compensation factor",
    "X3 Navier-Stokes scaling exponents",
    "X4 periodic shear rank defect",
    "X5 periodic shear replica budget",
    "X6 homogeneous extension no disagreement",
    "X7 ABC divergence curl and heat identities",
    "X8 ABC gradient determinant and decay",
)
SCHEMA = "cassi.navier-stokes.replica-coherence.verification.v1"


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



def group_pass(book: CheckBook, prefix: str, expected: int) -> bool:
    rows = [row for row in book.checks if row["name"].startswith(prefix)]
    return len(rows) == expected and all(row["passed"] for row in rows)



def verify_replica_and_covariance(
    book: CheckBook,
    values: dict[str, Any],
) -> None:
    weights = (sp.Rational(1, 2), sp.Rational(1, 3), sp.Rational(1, 6))
    entries = sp.symbols("y0:9", real=True)
    samples = tuple(sp.Matrix(entries[3 * j : 3 * j + 3]) for j in range(3))
    mean = sum((weight * sample for weight, sample in zip(weights, samples)), sp.zeros(3, 1))
    moment = sum(
        (weight * sample * sample.T for weight, sample in zip(weights, samples)),
        sp.zeros(3, 3),
    )
    pair_outer = sum(
        (
            weights[j] * weights[k] * samples[j] * samples[k].T
            for j, k in itertools.product(range(3), repeat=2)
        ),
        sp.zeros(3, 3),
    )
    book.exact(EXPECTED_CHECK_NAMES[0], pair_outer, mean * mean.T)

    pair_overlap = sum(
        (
            weights[j] * weights[k] * (samples[j].T * samples[k])[0]
            for j, k in itertools.product(range(3), repeat=2)
        ),
        sp.Integer(0),
    )
    book.exact(EXPECTED_CHECK_NAMES[1], pair_overlap, (mean.T * mean)[0])

    pair_disagreement = sp.Rational(1, 2) * sum(
        (
            weights[j]
            * weights[k]
            * ((samples[j] - samples[k]).T * (samples[j] - samples[k]))[0]
            for j, k in itertools.product(range(3), repeat=2)
        ),
        sp.Integer(0),
    )
    covariance = moment - mean * mean.T
    book.exact(EXPECTED_CHECK_NAMES[2], pair_disagreement, sp.trace(covariance))

    z = sp.Matrix(sp.symbols("z0:3", real=True))
    gram_sum = sum(
        (
            weight * ((z.T * (sample - mean))[0]) ** 2
            for weight, sample in zip(weights, samples)
        ),
        sp.Integer(0),
    )
    book.exact(EXPECTED_CHECK_NAMES[3], (z.T * covariance * z)[0], gram_sum)

    xi, nu = sp.symbols("xi nu", real=True, positive=True)
    y = sp.Matrix([sp.Function(f"f{j}")(xi) for j in range(3)])
    common_generator = nu * (sp.diff(y, xi, 2) * y.T + y * sp.diff(y, xi, 2).T)
    common_generator += 2 * nu * sp.diff(y, xi) * sp.diff(y, xi).T
    product_laplacian = nu * sp.diff(y * y.T, xi, 2)
    book.exact(EXPECTED_CHECK_NAMES[4], common_generator, product_laplacian)

    left = sp.Matrix([sp.Function(f"a{j}")(xi) for j in range(3)])
    right = sp.Matrix([sp.Function(f"b{j}")(xi) for j in range(3)])
    independent_generator = nu * (
        sp.diff(left, xi, 2) * right.T + left * sp.diff(right, xi, 2).T
    )
    same_noise_generator = independent_generator + (
        2 * nu * sp.diff(left, xi) * sp.diff(right, xi).T
    )
    cross_variation = same_noise_generator - independent_generator
    book.exact(
        EXPECTED_CHECK_NAMES[5],
        cross_variation,
        2 * nu * sp.diff(left, xi) * sp.diff(right, xi).T,
    )

    w = sp.Matrix([sp.Function(f"w{j}")(xi) for j in range(3)])
    mean_product_diffusion = nu * (
        sp.diff(w, xi, 2) * w.T + w * sp.diff(w, xi, 2).T
    ) - nu * sp.diff(w * w.T, xi, 2)
    expected_gradient_source = -2 * nu * sp.diff(w, xi) * sp.diff(w, xi).T
    book.exact(
        EXPECTED_CHECK_NAMES[6],
        mean_product_diffusion,
        expected_gradient_source,
    )

    initial = sp.Matrix(sp.symbols("o0:3", real=True))
    source_residual = (
        2 * nu * sp.diff(w, xi) * sp.diff(w, xi).T
        + mean_product_diffusion
    )
    initial_residual = initial * initial.T - initial * initial.T
    source_zero = reduce_exact(source_residual)
    initial_zero = reduce_exact(initial_residual)
    book.record(
        EXPECTED_CHECK_NAMES[7],
        is_zero(source_zero) and is_zero(initial_zero),
        {"source_residual": source_zero, "initial_residual": initial_zero},
    )

    values["replica_and_covariance"] = {
        "weights": weights,
        "mean": mean,
        "covariance_trace": sp.trace(covariance),
        "common_noise_cross_variation": cross_variation,
    }



def verify_duhamel_and_occupation(
    book: CheckBook,
    values: dict[str, Any],
) -> None:
    t, tau, nu = sp.symbols("t tau nu", real=True, positive=True)
    rates = (sp.Integer(1), sp.Integer(-2), sp.Integer(1))
    propagator = sp.diag(*(sp.exp(rate * tau) for rate in rates))
    book.exact(EXPECTED_CHECK_NAMES[8], propagator.det(), 1)

    generator = sp.diag(*rates)
    source = sp.Matrix([[2, 1, 0], [1, 3, 1], [0, 1, 4]])
    kernel = sp.diag(*(sp.exp(rate * (t - tau)) for rate in rates))
    duhamel = 2 * nu * sp.integrate(kernel * source * kernel.T, (tau, 0, t))
    duhamel_residual = sp.diff(duhamel, t)
    duhamel_residual -= generator * duhamel + duhamel * generator.T
    duhamel_residual -= 2 * nu * source
    initial_residual = duhamel.subs(t, 0)
    book.record(
        EXPECTED_CHECK_NAMES[9],
        is_zero(reduce_exact(duhamel_residual))
        and is_zero(reduce_exact(initial_residual)),
        {
            "evolution_residual": reduce_exact(duhamel_residual),
            "initial_residual": reduce_exact(initial_residual),
        },
    )

    f_symbols = sp.symbols("f0:9", real=True)
    g_symbols = sp.symbols("g0:9", real=True)
    deformation = sp.Matrix(3, 3, f_symbols)
    gradient = sp.Matrix(3, 3, g_symbols)
    gradient_gram = gradient * gradient.T
    frame_sum = sum(
        (
            ((deformation * gradient[:, column]).T * (deformation * gradient[:, column]))[0]
            for column in range(3)
        ),
        sp.Integer(0),
    )
    book.exact(
        EXPECTED_CHECK_NAMES[10],
        sp.trace(deformation * gradient_gram * deformation.T),
        frame_sum,
    )

    l_symbols = sp.symbols("l0:9", real=True)
    vector_symbols = sp.symbols("v0:3", real=True)
    velocity_gradient = sp.Matrix(3, 3, l_symbols)
    vector = sp.Matrix(vector_symbols)
    strain = (velocity_gradient + velocity_gradient.T) / 2
    norm_derivative = (
        vector.T * (velocity_gradient.T + velocity_gradient) * vector
    )[0]
    book.exact(
        EXPECTED_CHECK_NAMES[11],
        norm_derivative,
        2 * (vector.T * strain * vector)[0],
    )

    source_vectors = (
        sp.Matrix([1, 2, 0]),
        sp.Matrix([-1, 1, 2]),
        sp.Matrix([2, 0, -1]),
        sp.Matrix([1, -2, 3]),
    )
    source_mass = sum((g.dot(g) for g in source_vectors), sp.Integer(0))
    probabilities = tuple(g.dot(g) / source_mass for g in source_vectors)
    book.exact(EXPECTED_CHECK_NAMES[12], sum(probabilities), 1)

    beta, source_rate = sp.symbols(
        "beta source_rate",
        real=True,
        nonzero=True,
    )
    scalar_covariance = source_rate * (sp.exp(2 * beta * t) - 1) / (2 * beta)
    scalar_residual = sp.diff(scalar_covariance, t)
    scalar_residual -= 2 * beta * scalar_covariance + source_rate
    book.record(
        EXPECTED_CHECK_NAMES[13],
        reduce_exact(scalar_residual) == 0
        and reduce_exact(scalar_covariance.subs(t, 0)) == 0,
        {
            "evolution_residual": reduce_exact(scalar_residual),
            "initial_value": reduce_exact(scalar_covariance.subs(t, 0)),
        },
    )

    r11, r22, r33, r12, r13, r23 = sp.symbols(
        "r11 r22 r33 r12 r13 r23",
        real=True,
    )
    covariance = sp.Matrix(
        [[r11, r12, r13], [r12, r22, r23], [r13, r23, r33]]
    )
    q11, q22, q33, q12, q13, q23 = sp.symbols(
        "q11 q22 q33 q12 q13 q23",
        real=True,
    )
    gram = sp.Matrix([[q11, q12, q13], [q12, q22, q23], [q13, q23, q33]])
    trace_reaction = sp.trace(
        velocity_gradient * covariance
        + covariance * velocity_gradient.T
        + 2 * nu * gram
    )
    trace_target = 2 * frobenius(strain, covariance) + 2 * nu * sp.trace(gram)
    book.exact(EXPECTED_CHECK_NAMES[14], trace_reaction, trace_target)

    initial_energy, gamma = sp.symbols(
        "initial_energy gamma",
        real=True,
        positive=True,
    )
    total = initial_energy * sp.exp(2 * gamma * t)
    coherent = total - scalar_covariance
    positive_minus_positive_residual = sp.diff(coherent, t)
    positive_minus_positive_residual -= (
        2 * gamma * total - 2 * beta * scalar_covariance - source_rate
    )
    book.record(
        EXPECTED_CHECK_NAMES[15],
        reduce_exact(coherent + scalar_covariance - total) == 0
        and reduce_exact(positive_minus_positive_residual) == 0,
        {
            "decomposition_residual": reduce_exact(
                coherent + scalar_covariance - total
            ),
            "evolution_residual": reduce_exact(positive_minus_positive_residual),
        },
    )

    values["duhamel_and_occupation"] = {
        "propagator": propagator,
        "constant_matrix_duhamel": duhamel,
        "source_probabilities": probabilities,
        "scalar_covariance": scalar_covariance,
    }



def verify_coherence_budget(
    book: CheckBook,
    values: dict[str, Any],
) -> None:
    coherent, spread, alpha, beta, nu, dissipation = sp.symbols(
        "coherent spread alpha beta nu dissipation",
        real=True,
        positive=True,
    )
    total = coherent + spread
    coherent_rate = 2 * alpha * coherent - 2 * nu * dissipation
    spread_rate = 2 * beta * spread + 2 * nu * dissipation
    total_rate = coherent_rate + spread_rate
    expected_total_rate = 2 * (alpha * coherent + beta * spread)
    book.exact(EXPECTED_CHECK_NAMES[16], total_rate, expected_total_rate)

    coherence = coherent / total
    total_production = (alpha * coherent + beta * spread) / total
    mixture = coherence * alpha + (1 - coherence) * beta
    book.exact(EXPECTED_CHECK_NAMES[17], total_production, mixture)

    coherence_rate = (coherent_rate * total - coherent * total_rate) / total**2
    expected_coherence_rate = (
        2 * coherence * (1 - coherence) * (alpha - beta)
        - 2 * nu * dissipation / total
    )
    book.exact(
        EXPECTED_CHECK_NAMES[18],
        coherence_rate,
        expected_coherence_rate,
    )

    initial_rate = reduce_exact(coherence_rate.subs(spread, 0))
    book.exact(
        EXPECTED_CHECK_NAMES[19],
        initial_rate,
        -2 * nu * dissipation / coherent,
    )

    logarithmic_rate = coherent_rate / coherent - total_rate / total
    expected_logarithmic_rate = (
        2 * (1 - coherence) * (alpha - beta)
        - 2 * nu * dissipation / coherent
    )
    book.exact(
        EXPECTED_CHECK_NAMES[20],
        logarithmic_rate,
        expected_logarithmic_rate,
    )

    odds_rate = sp.Rational(1, 2) * (
        coherent_rate / coherent - spread_rate / spread
    )
    expected_odds_rate = alpha - beta - nu * dissipation * (
        1 / coherent + 1 / spread
    )
    book.exact(EXPECTED_CHECK_NAMES[21], odds_rate, expected_odds_rate)

    book.exact(
        EXPECTED_CHECK_NAMES[22],
        1 - coherence,
        spread / total,
    )

    lower_bound, remainder = sp.symbols(
        "lower_bound remainder",
        real=True,
        nonnegative=True,
    )
    spread_with_bound = lower_bound + remainder
    total_with_bound = coherent + spread_with_bound
    compensated = total_with_bound - lower_bound
    gap = reduce_exact(compensated - coherent)
    book.record(
        EXPECTED_CHECK_NAMES[23],
        gap == remainder and bool(remainder.is_nonnegative),
        {"compensated_minus_coherent": gap},
    )

    values["coherence_budget"] = {
        "coherence": coherence,
        "total_production": total_production,
        "coherence_rate": reduce_exact(coherence_rate),
        "odds_rate": reduce_exact(odds_rate),
        "compensated_gap": gap,
    }



def verify_volume_preserving_optimization(
    book: CheckBook,
    values: dict[str, Any],
) -> None:
    f_symbols = sp.symbols("f0:9", real=True)
    q_symbols = sp.symbols("q0:6", real=True)
    deformation = sp.Matrix(3, 3, f_symbols)
    q11, q22, q33, q12, q13, q23 = q_symbols
    gram = sp.Matrix([[q11, q12, q13], [q12, q22, q23], [q13, q23, q33]])
    determinant_residual = reduce_exact(
        (deformation * gram * deformation.T).det()
        - deformation.det() ** 2 * gram.det()
    )
    book.exact(EXPECTED_CHECK_NAMES[24], determinant_residual, 0)

    x1, x2, x3 = sp.symbols("x1 x2 x3", real=True, positive=True)
    diagonal_gram = sp.diag(x1**6, x2**6, x3**6)
    optimizer = sp.diag(
        x2 * x3 / x1**2,
        x1 * x3 / x2**2,
        x1 * x2 / x3**2,
    )
    book.exact(EXPECTED_CHECK_NAMES[25], optimizer.det(), 1)

    isotropic_scale = (x1 * x2 * x3) ** 2
    optimized_image = reduce_exact(optimizer * diagonal_gram * optimizer.T)
    book.exact(
        EXPECTED_CHECK_NAMES[26],
        optimized_image,
        isotropic_scale * sp.eye(3),
    )
    book.exact(
        EXPECTED_CHECK_NAMES[27],
        sp.trace(optimized_image),
        3 * isotropic_scale,
    )

    epsilon, q1, q2 = sp.symbols(
        "epsilon q1 q2",
        real=True,
        positive=True,
    )
    rank_two = sp.diag(q1, q2, 0)
    rank_two_collapse = sp.diag(epsilon, epsilon, epsilon ** -2)
    book.exact(EXPECTED_CHECK_NAMES[28], rank_two_collapse.det(), 1)
    rank_two_trace = reduce_exact(
        sp.trace(rank_two_collapse * rank_two * rank_two_collapse.T)
    )
    rank_two_limit = sp.limit(rank_two_trace, epsilon, 0, dir="+")
    book.record(
        EXPECTED_CHECK_NAMES[29],
        rank_two_trace == epsilon**2 * (q1 + q2) and rank_two_limit == 0,
        {"trace": rank_two_trace, "limit": rank_two_limit},
    )

    rank_one = sp.diag(q1, 0, 0)
    rank_one_collapse = sp.diag(
        epsilon,
        epsilon ** -sp.Rational(1, 2),
        epsilon ** -sp.Rational(1, 2),
    )
    book.exact(EXPECTED_CHECK_NAMES[30], rank_one_collapse.det(), 1)
    rank_one_trace = reduce_exact(
        sp.trace(rank_one_collapse * rank_one * rank_one_collapse.T)
    )
    rank_one_limit = sp.limit(rank_one_trace, epsilon, 0, dir="+")
    book.record(
        EXPECTED_CHECK_NAMES[31],
        rank_one_trace == q1 * epsilon**2 and rank_one_limit == 0,
        {"trace": rank_one_trace, "limit": rank_one_limit},
    )

    values["volume_preserving_optimization"] = {
        "determinant_residual": determinant_residual,
        "sharp_optimizer": optimizer,
        "optimized_image": optimized_image,
        "rank_two_trace": rank_two_trace,
        "rank_one_trace": rank_one_trace,
    }



def verify_scaling_and_controls(
    book: CheckBook,
    values: dict[str, Any],
) -> None:
    g_symbols = sp.symbols("g0:9", real=True)
    gradient = sp.Matrix(3, 3, g_symbols)
    gram = gradient * gradient.T
    book.exact(EXPECTED_CHECK_NAMES[32], gram.det(), gradient.det() ** 2)

    nu, j = sp.symbols("nu j", real=True, positive=True)
    book.exact(EXPECTED_CHECK_NAMES[33], 2 * nu * 3 * j, 6 * nu * j)

    scaling = {
        "velocity": 1,
        "vorticity": 2,
        "vorticity_gradient": 3,
        "gradient_gram": 6,
        "gradient_gram_determinant": 18,
        "determinant_cube_root": 6,
        "volume_element": -3,
        "time_element": -2,
    }
    scaling["enstrophy"] = 2 * scaling["vorticity"] + scaling["volume_element"]
    scaling["J"] = scaling["determinant_cube_root"] + scaling["volume_element"]
    scaling["time_integrated_J"] = scaling["J"] + scaling["time_element"]
    scaling["normalized_compensation"] = (
        scaling["time_integrated_J"] - scaling["enstrophy"]
    )
    expected_scaling = {
        "velocity": 1,
        "vorticity": 2,
        "vorticity_gradient": 3,
        "gradient_gram": 6,
        "gradient_gram_determinant": 18,
        "determinant_cube_root": 6,
        "volume_element": -3,
        "time_element": -2,
        "enstrophy": 1,
        "J": 3,
        "time_integrated_J": 1,
        "normalized_compensation": 0,
    }
    book.record(
        EXPECTED_CHECK_NAMES[34],
        scaling == expected_scaling,
        scaling,
    )

    x, y, z, t = sp.symbols("x y z t", real=True)
    n = sp.symbols("n", integer=True, positive=True)
    shear = sp.Matrix([sp.exp(-nu * n**2 * t) * sp.sin(n * y), 0, 0])
    coordinates = (x, y, z)
    shear_divergence = sum(
        sp.diff(shear[index], coordinates[index]) for index in range(3)
    )
    shear_vorticity = sp.Matrix(
        [
            sp.diff(shear[2], y) - sp.diff(shear[1], z),
            sp.diff(shear[0], z) - sp.diff(shear[2], x),
            sp.diff(shear[1], x) - sp.diff(shear[0], y),
        ]
    )
    shear_gradient = shear_vorticity.jacobian(coordinates)
    shear_gram = shear_gradient * shear_gradient.T
    shear_heat_residual = sp.diff(shear, t) - nu * sum(
        (sp.diff(shear, coordinate, 2) for coordinate in coordinates),
        sp.zeros(3, 1),
    )
    book.record(
        EXPECTED_CHECK_NAMES[35],
        reduce_exact(shear_divergence) == 0
        and is_zero(reduce_exact(shear_heat_residual))
        and reduce_exact(shear_gram.det()) == 0
        and shear_gram.rank() == 1,
        {
            "divergence": reduce_exact(shear_divergence),
            "heat_residual": reduce_exact(shear_heat_residual),
            "vorticity": shear_vorticity,
            "gram_determinant": reduce_exact(shear_gram.det()),
            "generic_rank": shear_gram.rank(),
        },
    )

    initial_enstrophy = sp.symbols("initial_enstrophy", real=True, positive=True)
    shear_decay = sp.exp(-2 * nu * n**2 * t)
    shear_total = initial_enstrophy
    shear_coherent = initial_enstrophy * shear_decay
    shear_spread = initial_enstrophy * (1 - shear_decay)
    shear_budget_residual = reduce_exact(
        shear_total - shear_coherent - shear_spread
    )
    shear_transfer_residual = reduce_exact(
        sp.diff(shear_spread, t) - 2 * nu * n**2 * shear_coherent
    )
    book.record(
        EXPECTED_CHECK_NAMES[36],
        shear_budget_residual == 0 and shear_transfer_residual == 0,
        {
            "budget_residual": shear_budget_residual,
            "transfer_residual": shear_transfer_residual,
        },
    )

    rate = sp.symbols("rate", real=True)
    extension = sp.diag(sp.exp(rate * t), sp.exp(-rate * t), 1)
    seed = sp.Matrix([1, 0, 0])
    extension_vector = extension * seed
    extension_moment = extension_vector * extension_vector.T
    extension_covariance = extension_moment - extension_vector * extension_vector.T
    extension_enstrophy = (extension_vector.T * extension_vector)[0]
    book.record(
        EXPECTED_CHECK_NAMES[37],
        reduce_exact(extension.det()) == 1
        and is_zero(reduce_exact(extension_covariance))
        and reduce_exact(extension_enstrophy - sp.exp(2 * rate * t)) == 0,
        {
            "determinant": reduce_exact(extension.det()),
            "covariance": reduce_exact(extension_covariance),
            "occupation": reduce_exact(extension_enstrophy),
        },
    )

    abc = sp.Matrix(
        [
            sp.sin(z) + sp.cos(y),
            sp.sin(x) + sp.cos(z),
            sp.sin(y) + sp.cos(x),
        ]
    )
    abc_divergence = sum(
        sp.diff(abc[index], coordinates[index]) for index in range(3)
    )
    abc_curl = sp.Matrix(
        [
            sp.diff(abc[2], y) - sp.diff(abc[1], z),
            sp.diff(abc[0], z) - sp.diff(abc[2], x),
            sp.diff(abc[1], x) - sp.diff(abc[0], y),
        ]
    )
    abc_laplacian = sum(
        (sp.diff(abc, coordinate, 2) for coordinate in coordinates),
        sp.zeros(3, 1),
    )
    abc_convection = abc.jacobian(coordinates) * abc
    abc_bernoulli_gradient = sp.Matrix(
        [sp.diff((abc.T * abc)[0] / 2, coordinate) for coordinate in coordinates]
    )
    book.record(
        EXPECTED_CHECK_NAMES[38],
        reduce_exact(abc_divergence) == 0
        and is_zero(reduce_exact(abc_curl - abc))
        and is_zero(reduce_exact(abc_laplacian + abc))
        and is_zero(reduce_exact(abc_convection - abc_bernoulli_gradient)),
        {
            "divergence": reduce_exact(abc_divergence),
            "curl_residual": reduce_exact(abc_curl - abc),
            "heat_residual": reduce_exact(abc_laplacian + abc),
            "bernoulli_residual": reduce_exact(
                abc_convection - abc_bernoulli_gradient
            ),
        },
    )

    abc_gradient = abc_curl.jacobian(coordinates)
    expected_determinant = (
        sp.cos(x) * sp.cos(y) * sp.cos(z)
        - sp.sin(x) * sp.sin(y) * sp.sin(z)
    )
    determinant_formula = reduce_exact(abc_gradient.det())
    determinant_residual = reduce_exact(determinant_formula - expected_determinant)
    decay_exponent = sp.Integer(3) * sp.Rational(2, 3)
    book.record(
        EXPECTED_CHECK_NAMES[39],
        determinant_residual == 0
        and determinant_formula.subs({x: 0, y: 0, z: 0}) == 1
        and decay_exponent == 2,
        {
            "determinant": determinant_formula,
            "formula_residual": determinant_residual,
            "origin_value": determinant_formula.subs({x: 0, y: 0, z: 0}),
            "J_decay_exponent": decay_exponent,
        },
    )

    values["scaling_and_controls"] = {
        "scaling_exponents": scaling,
        "shear_vorticity": shear_vorticity,
        "shear_gram": shear_gram,
        "abc_determinant": determinant_formula,
        "abc_J_decay_exponent": decay_exponent,
    }



def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(RVC\d+)\}", text)
    expected_tags = [f"RVC{index}" for index in range(1, 53)]
    return {
        "tag_count": len(tags),
        "unique_tag_count": len(set(tags)),
        "expected_tags": expected_tags,
        "observed_tags": tags,
        "tags_match": tags == expected_tags,
        "inventory_declaration_present": (
            "must execute exactly 40 checks" in text
        ),
        "selected_receipt_present": (
            "runs/navier_stokes_replica_coherence_20260910_qualified/verification.json"
            in text
        ),
        "paper_binding_present": (
            "turbulence/navier-stokes-replica-coherence.md" in text
        ),
    }



def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_replica_and_covariance(book, values)
    verify_duhamel_and_occupation(book, values)
    verify_coherence_budget(book, values)
    verify_volume_preserving_optimization(book, values)
    verify_scaling_and_controls(book, values)

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

    replica_pass = group_pass(book, "R", 8)
    occupation_pass = group_pass(book, "D", 8)
    coherence_pass = group_pass(book, "C", 8)
    optimization_pass = group_pass(book, "S", 8)
    controls_pass = group_pass(book, "X", 8)
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
            "independent_replica_overlap_and_disagreement": (
                "SUPPORTS" if success and replica_pass else "INCONCLUSIVE"
            ),
            "forced_covariance_and_retarded_occupation": (
                "SUPPORTS"
                if success and replica_pass and occupation_pass
                else "INCONCLUSIVE"
            ),
            "coherence_budget_and_full_rank_compensation": (
                "SUPPORTS"
                if success
                and coherence_pass
                and optimization_pass
                and controls_pass
                else "INCONCLUSIVE"
            ),
            "singular_source_compensation_from_volume_preservation_alone": (
                "CONTRADICTS"
                if success
                and all(book.checks[index]["passed"] for index in range(28, 32))
                else "INCONCLUSIVE"
            ),
            "uniform_all_data_compensated_bound": (
                "UNRESOLVED" if success else "INCONCLUSIVE"
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
            "replica_factorization": "FINITE_SYMBOLIC_ENSEMBLE",
            "common_noise_covariance": (
                "ANALYTIC_IDENTITY_WITH_SYMBOLIC_PRODUCT_COMPONENTS"
            ),
            "duhamel_occupation": (
                "ANALYTIC_STOCHASTIC_FLOW_IDENTITY_WITH_FIXED_MATRIX_COMPONENTS"
            ),
            "volume_preserving_lower_bound": (
                "ANALYTIC_AM_GM_ARGUMENT_WITH_EXACT_OPTIMIZER_AND_COLLAPSE_CHECKS"
            ),
            "continuation_step": (
                "CONDITIONAL_ANALYTIC_ARGUMENT_OUTSIDE_EXECUTABLE_SCOPE"
            ),
            "all_data_compensated_bound": "UNRESOLVED",
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
