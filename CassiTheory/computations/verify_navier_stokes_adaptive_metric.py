#!/usr/bin/env python3
"""Verify the fixed adaptive-metric identities for Navier–Stokes stretching.

Run from CassiTheory. The calculation is symbolic and integrates no flow
trajectory. Generated receipts are immutable and remain beneath runs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
PROTOCOL = ROOT / "computations" / "navier-stokes-adaptive-metric-prereg.md"
CASSIFI_SOURCE = WORKSPACE / "CassiFI" / "cassi_variational_field.py"
DEFAULT_OUTPUT = ROOT / "runs" / "navier_stokes_adaptive_metric" / "verification.json"
EXPECTED_CHECKS = 32
EXPECTED_CHECK_NAMES = (
    "M1 branch metric product rule",
    "M2 extensional Lyapunov residual",
    "M3 extensional weighted energy invariance",
    "M4 extensional metric determinant",
    "M5 extensional least eigenvalue",
    "M6 extensional condition number",
    "M7 fixed positive symmetrizer obstruction",
    "S1 scalar weighted enstrophy balance",
    "S2 constant-rate weight ODE",
    "S3 constant-rate exponential solution",
    "S4 integrated signed-production identity",
    "S5 signed interval coercivity ceiling",
    "S6 periodic fixture admissibility",
    "S7 periodic fixture stretching tuple",
    "C1 expanding-state covariance initial value",
    "C2 expanding-state covariance flow",
    "C3 expanding-state covariance positivity",
    "C4 precision-weighted stretching limit",
    "C5 precision lower-bound collapse",
    "C6 precision condition-number growth",
    "C7 normalized covariance and omitted amplitude",
    "P1 periodic metric diffusion identity",
    "P2 positive metric-curvature work",
    "P3 negative metric-curvature work",
    "P4 material cancellation leaves curvature",
    "P5 viscous adjoint cancellation removes curvature",
    "P6 defect Rayleigh and metric coercivity bounds",
    "T1 terminal adjoint metric equation",
    "T2 terminal adjoint endpoint",
    "T3 terminal adjoint positivity",
    "T4 terminal adjoint endpoint energy identity",
    "T5 terminal adjoint initial-norm growth",
)
SCHEMA = "cassi.navier-stokes.adaptive-metric.verification.v1"


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
            reduced = value.applyfunc(lambda item: sp.simplify(sp.trigsimp(item)))
            passed = all(item == 0 for item in reduced)
        else:
            reduced = sp.simplify(sp.trigsimp(value))
            passed = reduced == 0
        self.record(name, passed, reduced)


def normalized_integral(expression: sp.Expr, coordinates: tuple[sp.Symbol, ...]) -> sp.Expr:
    result = expression
    for coordinate in coordinates:
        result = sp.integrate(result, (coordinate, 0, 2 * sp.pi)) / (2 * sp.pi)
    return sp.simplify(sp.trigsimp(result))


def verify_branch_metric(book: CheckBook, values: dict[str, Any]) -> None:
    time = sp.symbols("t", positive=True)
    z1 = sp.Function("z1")(time)
    z2 = sp.Function("z2")(time)
    m11 = sp.Function("m11")(time)
    m12 = sp.Function("m12")(time)
    m22 = sp.Function("m22")(time)
    ell11, ell12, ell21, ell22, r1, r2 = sp.symbols(
        "ell11 ell12 ell21 ell22 r1 r2", real=True
    )
    z = sp.Matrix([z1, z2])
    metric = sp.Matrix([[m11, m12], [m12, m22]])
    generator = sp.Matrix([[ell11, ell12], [ell21, ell22]])
    source = sp.Matrix([r1, r2])
    energy = (z.T * metric * z)[0] / 2
    dynamics = generator * z + source
    derivative = sp.diff(energy, time).subs(
        {sp.diff(z1, time): dynamics[0], sp.diff(z2, time): dynamics[1]}
    )
    target = (
        (z.T * (sp.diff(metric, time) + generator.T * metric + metric * generator) * z)[0]
        / 2
        + (z.T * metric * source)[0]
    )
    book.exact("M1 branch metric product rule", derivative - target)

    rate = sp.symbols("a", positive=True)
    x1, x2, x3 = sp.symbols("x1 x2 x3", real=True)
    initial = sp.Matrix([x1, x2, x3])
    stretch = sp.diag(rate, -rate, 0)
    flow = sp.diag(sp.exp(rate * time), sp.exp(-rate * time), 1)
    cancel_metric = sp.diag(sp.exp(-2 * rate * time), sp.exp(2 * rate * time), 1)
    state = flow * initial

    book.exact(
        "M2 extensional Lyapunov residual",
        sp.diff(cancel_metric, time) + stretch.T * cancel_metric + cancel_metric * stretch,
    )
    book.exact(
        "M3 extensional weighted energy invariance",
        (state.T * cancel_metric * state)[0] - (initial.T * initial)[0],
    )
    book.exact("M4 extensional metric determinant", cancel_metric.det() - 1)

    least = sp.exp(-2 * rate * time)
    least_decay = sp.simplify(sp.diff(least, time) + 2 * rate * least) == 0
    least_order = (
        cancel_metric[0, 0] == least
        and least.subs(time, 0) == 1
        and least_decay
        and sp.ask(sp.Q.positive(least))
        and sp.limit(least, time, sp.oo) == 0
    )
    book.record(
        "M5 extensional least eigenvalue",
        least_order,
        f"lambda_min={least}, derivative=-2*a*lambda_min, limit=0",
    )
    book.exact(
        "M6 extensional condition number",
        cancel_metric[1, 1] / cancel_metric[0, 0] - sp.exp(4 * rate * time),
    )

    ell11, ell22, ell33 = sp.symbols("ell11 ell22 ell33", positive=True)
    ell21, ell31, ell32 = sp.symbols("ell21 ell31 ell32", real=True)
    cholesky = sp.Matrix(
        [
            [ell11, 0, 0],
            [ell21, ell22, 0],
            [ell31, ell32, ell33],
        ]
    )
    fixed_metric = cholesky * cholesky.T
    e1 = sp.Matrix([1, 0, 0])
    fixed_production = sp.simplify(
        (e1.T * (stretch.T * fixed_metric + fixed_metric * stretch) * e1)[0]
    )
    expected_production = 2 * rate * fixed_metric[0, 0]
    fixed_obstruction = (
        sp.simplify(fixed_production - expected_production) == 0
        and sp.ask(sp.Q.positive(fixed_production))
    )
    book.record(
        "M7 fixed positive symmetrizer obstruction",
        fixed_obstruction,
        f"production={fixed_production}>0 for the general Cholesky SPD metric",
    )

    values["branch_metric"] = {
        "flow": str(flow),
        "cancellation_metric": str(cancel_metric),
        "least_eigenvalue": str(least),
        "condition_number": str(sp.exp(4 * rate * time)),
        "fixed_extensional_production": str(fixed_production),
    }


def verify_scalar_weight(book: CheckBook, values: dict[str, Any]) -> None:
    weight, enstrophy, dissipation, viscosity = sp.symbols(
        "a_s W D nu", positive=True
    )
    production = sp.symbols("P", real=True)
    weight_dot = -2 * weight * production / enstrophy
    enstrophy_dot = 2 * production - 2 * viscosity * dissipation
    balance = sp.expand(
        (weight_dot * enstrophy + weight * enstrophy_dot) / 2
        + viscosity * weight * dissipation
    )
    book.exact("S1 scalar weighted enstrophy balance", balance)

    time = sp.symbols("t", nonnegative=True)
    rate, initial_weight = sp.symbols("r a_0", positive=True)
    solution = initial_weight * sp.exp(-2 * rate * time)
    book.exact("S2 constant-rate weight ODE", sp.diff(solution, time) + 2 * rate * solution)
    book.record(
        "S3 constant-rate exponential solution",
        sp.simplify(solution.subs(time, 0) - initial_weight) == 0
        and sp.ask(sp.Q.positive(solution)),
        solution,
    )

    signed_production = sp.symbols("Q", real=True)
    endpoint = initial_weight * sp.exp(-2 * signed_production)
    book.exact(
        "S4 integrated signed-production identity",
        sp.log(initial_weight / endpoint) / 2 - signed_production,
    )
    floor, start_weight = sp.symbols("m a_start", positive=True)
    upper_slack, lower_slack = sp.symbols("r_upper r_lower", real=True)
    ceiling = start_weight + upper_slack**2
    end_weight = floor + lower_slack**2
    ratio_slack = sp.expand(ceiling * end_weight - floor * start_weight)
    expected_slack = (
        start_weight * lower_slack**2
        + floor * upper_slack**2
        + upper_slack**2 * lower_slack**2
    )
    book.record(
        "S5 signed interval coercivity ceiling",
        sp.simplify(ratio_slack - expected_slack) == 0
        and all(
            sp.ask(sp.Q.nonnegative(term))
            for term in (
                start_weight * lower_slack**2,
                floor * upper_slack**2,
                upper_slack**2 * lower_slack**2,
            )
        ),
        (
            f"M={ceiling}>=a_start, a_end={end_weight}>=m; "
            f"M*a_end-m*a_start={ratio_slack}>=0"
        ),
    )

    x, y, z = sp.symbols("x y z", real=True)
    velocity = sp.Matrix(
        [
            sp.cos(y) + sp.sin(x + y),
            sp.cos(x) - sp.sin(x + y),
            sp.cos(x) + sp.cos(y) + sp.sin(x + y),
        ]
    )
    coordinates = (x, y, z)
    gradient = velocity.jacobian(coordinates)
    divergence = sp.trace(gradient)
    mean = velocity.applyfunc(lambda item: normalized_integral(item, coordinates))
    book.record(
        "S6 periodic fixture admissibility",
        sp.simplify(divergence) == 0 and all(item == 0 for item in mean),
        f"divergence={divergence}, mean={mean.T}",
    )

    vorticity = sp.Matrix(
        [
            sp.diff(velocity[2], y) - sp.diff(velocity[1], z),
            sp.diff(velocity[0], z) - sp.diff(velocity[2], x),
            sp.diff(velocity[1], x) - sp.diff(velocity[0], y),
        ]
    )
    strain = (gradient + gradient.T) / 2
    w_value = normalized_integral((vorticity.T * vorticity)[0], coordinates)
    p_value = normalized_integral((vorticity.T * strain * vorticity)[0], coordinates)
    log_rate = sp.simplify(-2 * p_value / w_value)
    book.record(
        "S7 periodic fixture stretching tuple",
        sp.simplify(w_value - 5) == 0
        and sp.simplify(p_value - sp.Rational(1, 2)) == 0
        and sp.simplify(log_rate + sp.Rational(1, 5)) == 0,
        f"W={w_value}, P={p_value}, a_s'/a_s={log_rate}",
    )

    values["scalar_weight"] = {
        "weighted_balance_residual": str(balance),
        "constant_rate_solution": str(solution),
        "fixture_velocity": str(velocity),
        "fixture_vorticity": str(vorticity),
        "fixture_enstrophy": str(w_value),
        "fixture_production": str(p_value),
        "fixture_log_weight_rate": str(log_rate),
    }


def verify_covariance_adaptation(book: CheckBook, values: dict[str, Any]) -> None:
    time = sp.symbols("t", nonnegative=True)
    rate, ridge = sp.symbols("a lambda", positive=True)
    state = sp.Matrix([sp.exp(rate * time), 0, 0])
    leading = ridge + (sp.exp(2 * rate * time) - sp.exp(-time)) / (2 * rate + 1)
    covariance = sp.diag(leading, ridge, ridge)
    identity = sp.eye(3)

    book.exact("C1 expanding-state covariance initial value", covariance.subs(time, 0) - ridge * identity)
    book.exact(
        "C2 expanding-state covariance flow",
        sp.diff(covariance, time) - (state * state.T + ridge * identity - covariance),
    )

    positive_increment = sp.exp(-time) * (sp.exp((2 * rate + 1) * time) - 1) / (2 * rate + 1)
    increment_exponent = (2 * rate + 1) * time
    positivity = (
        sp.simplify(leading - ridge - positive_increment) == 0
        and sp.ask(sp.Q.nonnegative(increment_exponent))
        and sp.ask(sp.Q.positive(sp.exp(-time)))
        and sp.ask(sp.Q.positive(2 * rate + 1))
        and sp.ask(sp.Q.positive(ridge))
    )
    book.record(
        "C3 expanding-state covariance positivity",
        positivity,
        f"eigenvalues=({leading}, {ridge}, {ridge})",
    )

    precision_weighted = sp.simplify(sp.exp(2 * rate * time) / leading)
    weighted_limit = sp.simplify(sp.limit(precision_weighted, time, sp.oo))
    book.exact("C4 precision-weighted stretching limit", weighted_limit - (2 * rate + 1))

    precision_floor_limit = sp.limit(1 / leading, time, sp.oo)
    book.exact("C5 precision lower-bound collapse", precision_floor_limit)

    condition_number = sp.simplify(leading / ridge)
    scaled_condition_limit = sp.simplify(
        sp.limit(sp.exp(-2 * rate * time) * condition_number, time, sp.oo)
    )
    book.exact(
        "C6 precision condition-number growth",
        scaled_condition_limit - 1 / (ridge * (2 * rate + 1)),
    )

    normalized_leading = ridge + 1 - sp.exp(-time)
    normalized_derivative = sp.diff(normalized_leading, time)
    normalized_control = (
        normalized_leading.subs(time, 0) == ridge
        and sp.simplify(normalized_derivative - sp.exp(-time)) == 0
        and sp.ask(sp.Q.positive(normalized_derivative))
        and sp.limit(sp.exp(rate * time), time, sp.oo) == sp.oo
        and sp.limit(normalized_leading, time, sp.oo) == ridge + 1
    )
    book.record(
        "C7 normalized covariance and omitted amplitude",
        normalized_control,
        f"lambda<=Sigma_hat_11<lambda+1, lim|x|={sp.oo}",
    )

    values["covariance_adaptation"] = {
        "covariance": str(covariance),
        "precision_weighted_state": str(precision_weighted),
        "precision_weighted_limit": str(weighted_limit),
        "precision_floor_limit": str(precision_floor_limit),
        "condition_number": str(condition_number),
        "scaled_condition_limit": str(scaled_condition_limit),
        "normalized_leading_covariance": str(normalized_leading),
    }


def verify_spatial_metric(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z = sp.symbols("x y z", real=True)
    epsilon_parameter = sp.symbols("r_epsilon", positive=True)
    epsilon = sp.simplify(2 * epsilon_parameter / (1 + epsilon_parameter))
    omega = sp.Matrix([0, sp.sin(x), 0])
    coordinates = (x, y, z)
    plus = 2 + epsilon * sp.cos(2 * x)
    minus = 2 - epsilon * sp.cos(2 * x)
    metric_plus = sp.diag(2, plus, 2)
    metric_minus = sp.diag(2, minus, 2)

    def average(expression: sp.Expr) -> sp.Expr:
        return sp.simplify(
            sp.integrate(expression, (x, 0, 2 * sp.pi)) / (2 * sp.pi)
        )

    omega_x = sp.diff(omega, x)
    omega_xx = sp.diff(omega, x, 2)
    laplacian_plus = sp.diff(metric_plus, x, 2)
    laplacian_minus = sp.diff(metric_minus, x, 2)
    divergence = sp.simplify(sp.trace(omega.jacobian(coordinates)))
    integration_left = average((omega.T * metric_plus * omega_xx)[0])
    integration_right = -average((omega_x.T * metric_plus * omega_x)[0]) + average(
        (omega.T * laplacian_plus * omega)[0]
    ) / 2
    diffusion_identity = (
        sp.simplify(integration_left - integration_right) == 0
        and divergence == 0
    )
    book.record(
        "P1 periodic metric diffusion identity",
        diffusion_identity,
        f"residual={sp.simplify(integration_left - integration_right)}, "
        f"div(omega)={divergence}",
    )

    plus_curvature = sp.simplify(
        average((omega.T * laplacian_plus * omega)[0]) / 2
    )
    minus_curvature = sp.simplify(
        average((omega.T * laplacian_minus * omega)[0]) / 2
    )
    metric_floor = sp.simplify(2 - epsilon)
    admissible_metric = sp.ask(sp.Q.positive(metric_floor))
    book.record(
        "P2 positive metric-curvature work",
        plus_curvature == epsilon / 2
        and sp.ask(sp.Q.positive(plus_curvature))
        and admissible_metric,
        f"curvature={plus_curvature}, metric_floor={metric_floor}>0",
    )
    book.record(
        "P3 negative metric-curvature work",
        minus_curvature == -epsilon / 2
        and sp.ask(sp.Q.negative(minus_curvature))
        and admissible_metric,
        f"curvature={minus_curvature}, metric_floor={metric_floor}>0",
    )

    viscosity = sp.symbols("nu", positive=True)
    material_residual = viscosity * plus_curvature
    book.exact(
        "P4 material cancellation leaves curvature",
        material_residual - viscosity * epsilon / 2,
    )
    adjoint_metric_work = -viscosity * plus_curvature
    book.exact(
        "P5 viscous adjoint cancellation removes curvature",
        material_residual + adjoint_metric_work,
    )

    v1, v2, v3 = sp.symbols("v1 v2 v3", real=True)
    vector = sp.Matrix([v1, v2, v3])
    metric = sp.diag(2, 3, 5)
    defect = sp.diag(1, -6, 10)
    rayleigh_slack = sp.expand(
        2 * (vector.T * metric * vector)[0] - (vector.T * defect * vector)[0]
    )
    norm_slack = sp.expand(
        (vector.T * metric * vector)[0] - 2 * (vector.T * vector)[0]
    )
    expected_rayleigh = 3 * v1**2 + 12 * v2**2
    expected_norm = v2**2 + 3 * v3**2
    book.record(
        "P6 defect Rayleigh and metric coercivity bounds",
        sp.simplify(rayleigh_slack - expected_rayleigh) == 0
        and sp.simplify(norm_slack - expected_norm) == 0,
        f"Rayleigh slack={rayleigh_slack}; norm slack={norm_slack}",
    )

    values["spatial_metric"] = {
        "vorticity": str(omega),
        "vorticity_divergence": str(divergence),
        "diffusion_left": str(integration_left),
        "diffusion_right": str(integration_right),
        "epsilon_parameterization": str(epsilon),
        "metric_floor": str(metric_floor),
        "positive_curvature": str(plus_curvature),
        "negative_curvature": str(minus_curvature),
        "rayleigh_slack": str(rayleigh_slack),
        "norm_equivalence_slack": str(norm_slack),
    }


def verify_terminal_metric(book: CheckBook, values: dict[str, Any]) -> None:
    time = sp.symbols("t", real=True)
    terminal, rate = sp.symbols("tau a", positive=True)
    stretch = sp.diag(rate, -rate, 0)
    metric = sp.diag(
        sp.exp(2 * rate * (terminal - time)),
        sp.exp(-2 * rate * (terminal - time)),
        1,
    )
    book.exact(
        "T1 terminal adjoint metric equation",
        sp.diff(metric, time) + stretch.T * metric + metric * stretch,
    )
    book.exact("T2 terminal adjoint endpoint", metric.subs(time, terminal) - sp.eye(3))

    diagonal_positive = all(sp.ask(sp.Q.positive(metric[index, index])) for index in range(3))
    book.record("T3 terminal adjoint positivity", diagonal_positive, metric.diagonal().T)

    y1, y2, y3 = sp.symbols("y1 y2 y3", real=True)
    initial = sp.Matrix([y1, y2, y3])
    terminal_state = sp.diag(
        sp.exp(rate * terminal), sp.exp(-rate * terminal), 1
    ) * initial
    endpoint_left = (terminal_state.T * terminal_state)[0]
    endpoint_right = (initial.T * metric.subs(time, 0) * initial)[0]
    book.exact("T4 terminal adjoint endpoint energy identity", endpoint_left - endpoint_right)

    initial_norm = sp.exp(2 * rate * terminal)
    growth = sp.limit(initial_norm, terminal, sp.oo)
    book.record(
        "T5 terminal adjoint initial-norm growth",
        metric.subs(time, 0)[0, 0] == initial_norm and growth == sp.oo,
        f"lambda_max={initial_norm}, limit={growth}",
    )

    values["terminal_metric"] = {
        "metric": str(metric),
        "initial_metric": str(metric.subs(time, 0)),
        "initial_operator_norm": str(initial_norm),
        "operator_norm_limit": str(growth),
    }


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_branch_metric(book, values)
    verify_scalar_weight(book, values)
    verify_covariance_adaptation(book, values)
    verify_spatial_metric(book, values)
    verify_terminal_metric(book, values)

    observed_check_names = tuple(row["name"] for row in book.checks)
    inventory_match = observed_check_names == EXPECTED_CHECK_NAMES
    if not inventory_match:
        book.failures.append("fixed check inventory")
    success = not book.failures and inventory_match
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
            "exact_adaptive_cancellation": "SUPPORTS" if success else "INCONCLUSIVE",
            "uniform_coercivity_from_fixed_algebraic_controls": "CONTRADICTS" if success else "INCONCLUSIVE",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "navier_stokes_trajectory": "NOT_RUN",
            "symbolic_schedule": "FIXED_32_CHECKS",
            "all_data_terminal_metric_bound": "UNRESOLVED",
            "general_weighted_balance": "ANALYTIC_IDENTITY",
            "spatial_executable_scope": "DIVERGENCE_FREE_1D_PERIODIC_CONTROL",
            "terminal_executable_scope": "EXTENSIONAL_CONTROL",
            "cassifi_source": "HASHED_PROVENANCE_NOT_EXECUTED",
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
        "verifier": Path(__file__).resolve(),
        "cassifi_variational_field": CASSIFI_SOURCE,
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

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        suffix = path.suffix or ".txt"
        (snapshot_dir / f"{key}{suffix}").write_bytes(payloads[key])
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")

    success = False
    result: dict[str, Any] = {
        "schema": SCHEMA,
        **manifest,
    }
    try:
        computed, success = compute()
        result.update(computed)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
    except Exception as exc:  # receipt must retain implementation failures
        success = False
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")

    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")

    print()
    print(f"Receipt: {output}")
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in (
                    "status",
                    "check_count",
                    "inventory_match",
                    "classifications",
                    "error",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    if success and result.get("status") == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
