#!/usr/bin/env python3
"""Verify the fixed forward adaptive-metric identities for Navier–Stokes.

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
PROTOCOL = ROOT / "computations" / "navier-stokes-forward-adaptive-metric-prereg.md"
PARENT_PROTOCOL = ROOT / "computations" / "navier-stokes-adaptive-metric-prereg.md"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "navier_stokes_forward_adaptive_metric" / "verification.json"
)
EXPECTED_CHECKS = 16
EXPECTED_CHECK_NAMES = (
    "F1 extensional forward metric residual",
    "F2 extensional metric symmetry",
    "F3 extensional metric positivity",
    "F4 extensional determinant",
    "F5 extensional least-eigenvalue collapse",
    "F6 homogeneous projected gauge",
    "F7 rescaled forward metric equation",
    "F8 projected defect identity",
    "F9 projected metric-work cancellation",
    "F10 extensional weighted-energy invariance",
    "F11 spatial log-determinant chain rule",
    "F12 fixed diagonal determinant-source positivity",
    "F13 periodic fixture admissibility",
    "F14 periodic fixture origin strain",
    "F15 strain and initial metric-derivative spectra",
    "F16 positive-metric norm equivalence",
)
SCHEMA = "cassi.navier-stokes.forward-adaptive-metric.verification.v1"


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


def verify_extensional_control(book: CheckBook, values: dict[str, Any]) -> None:
    time = sp.symbols("t", nonnegative=True)
    rate, viscosity = sp.symbols("a nu", positive=True)
    stretch = sp.diag(rate, -rate, 0)
    metric = sp.diag(sp.exp(-2 * rate * time), sp.exp(2 * rate * time), 1)

    book.exact(
        "F1 extensional forward metric residual",
        sp.diff(metric, time) + stretch.T * metric + metric * stretch,
    )
    book.exact("F2 extensional metric symmetry", metric - metric.T)

    diagonal_positive = all(
        sp.ask(sp.Q.positive(metric[index, index])) for index in range(3)
    )
    book.record("F3 extensional metric positivity", diagonal_positive, metric.diagonal().T)
    book.exact("F4 extensional determinant", sp.det(metric) - 1)

    least = metric[0, 0]
    ratio_middle = sp.simplify(metric[1, 1] / least)
    ratio_last = sp.simplify(metric[2, 2] / least)
    collapse = (
        sp.ask(sp.Q.nonnegative(rate * time))
        and ratio_middle == sp.exp(4 * rate * time)
        and ratio_last == sp.exp(2 * rate * time)
        and sp.limit(least, time, sp.oo) == 0
    )
    book.record(
        "F5 extensional least-eigenvalue collapse",
        collapse,
        f"lambda_min={least}, ratios=({ratio_middle}, {ratio_last}), limit=0",
    )

    laplacian = sp.zeros(3)
    state = sp.Matrix([sp.exp(rate * time), 0, 0])
    z_h = sp.simplify((state.T * metric * state)[0])
    j_h = sp.simplify((state.T * laplacian * state)[0])
    c_h = sp.simplify(j_h / z_h)
    gauge_rate = sp.simplify(-2 * viscosity * c_h)
    book.record(
        "F6 homogeneous projected gauge",
        j_h == 0 and c_h == 0 and gauge_rate == 0,
        f"J_H={j_h}, c_H={c_h}, beta'/beta={gauge_rate}",
    )

    values["extensional_control"] = {
        "metric": str(metric),
        "determinant": str(sp.det(metric)),
        "least_eigenvalue": str(least),
        "least_eigenvalue_limit": str(sp.limit(least, time, sp.oo)),
        "projected_gauge": str(c_h),
    }


def verify_projected_balance(book: CheckBook, values: dict[str, Any]) -> None:
    viscosity, beta = sp.symbols("nu beta", positive=True)
    c_h = sp.symbols("c_H", real=True)
    h_entries = sp.symbols("h0:9", real=True)
    a_entries = sp.symbols("a0:9", real=True)
    lap_entries = sp.symbols("l0:9", real=True)
    metric_h = sp.Matrix(3, 3, h_entries)
    velocity_gradient = sp.Matrix(3, 3, a_entries)
    laplacian_h = sp.Matrix(3, 3, lap_entries)

    derivative_h = (
        -velocity_gradient.T * metric_h
        - metric_h * velocity_gradient
        + viscosity * laplacian_h
    )
    gauge_derivative = -2 * viscosity * c_h * beta
    metric_g = beta * metric_h
    derivative_g = gauge_derivative * metric_h + beta * derivative_h
    laplacian_g = beta * laplacian_h

    forward_residual = (
        derivative_g
        + velocity_gradient.T * metric_g
        + metric_g * velocity_gradient
        - viscosity * laplacian_g
        + 2 * viscosity * c_h * metric_g
    )
    book.exact("F7 rescaled forward metric equation", forward_residual)

    defect = (
        derivative_g
        + velocity_gradient.T * metric_g
        + metric_g * velocity_gradient
        + viscosity * laplacian_g
    )
    projected_defect = 2 * viscosity * (laplacian_g - c_h * metric_g)
    book.exact("F8 projected defect identity", defect - projected_defect)

    z_h, j_h = sp.symbols("Z_H J_H", positive=True)
    projected_work = 2 * viscosity * beta * (j_h - (j_h / z_h) * z_h)
    book.exact("F9 projected metric-work cancellation", projected_work)

    time = sp.symbols("t", real=True)
    rate = sp.symbols("a", positive=True)
    z1, z2, z3 = sp.symbols("z1 z2 z3", real=True)
    state = sp.Matrix(
        [z1 * sp.exp(rate * time), z2 * sp.exp(-rate * time), z3]
    )
    extensional_metric = sp.diag(
        sp.exp(-2 * rate * time), sp.exp(2 * rate * time), 1
    )
    weighted_energy = sp.simplify((state.T * extensional_metric * state)[0])
    book.exact("F10 extensional weighted-energy invariance", sp.diff(weighted_energy, time))

    values["projected_balance"] = {
        "forward_residual": str(forward_residual),
        "defect_residual": str(defect - projected_defect),
        "projected_work": str(projected_work),
        "extensional_weighted_energy": str(weighted_energy),
    }


def verify_determinant_identity(book: CheckBook, values: dict[str, Any]) -> None:
    coordinate = sp.symbols("x", real=True)
    viscosity = sp.symbols("nu", positive=True)
    metric = sp.diag(
        sp.exp(coordinate),
        sp.exp(2 * coordinate),
        sp.exp(coordinate**2 + 1),
    )
    inverse = metric.inv()
    first = sp.diff(metric, coordinate)
    second = sp.diff(metric, coordinate, 2)

    determinant_chain_left = sp.trace(inverse * second) - sp.diff(
        sp.log(sp.det(metric)), coordinate, 2
    )
    determinant_chain_right = sp.trace((inverse * first) ** 2)
    book.exact(
        "F11 spatial log-determinant chain rule",
        determinant_chain_left - determinant_chain_right,
    )

    source = sp.simplify(viscosity * determinant_chain_right)
    expected_source = viscosity * (4 * coordinate**2 + 5)
    source_positive = (
        sp.simplify(source - expected_source) == 0
        and sp.ask(sp.Q.nonnegative(coordinate**2))
        and sp.ask(sp.Q.positive(viscosity))
    )
    book.record(
        "F12 fixed diagonal determinant-source positivity",
        source_positive,
        f"source={source}=nu*(4*x**2+5)>0",
    )

    values["determinant_identity"] = {
        "metric": str(metric),
        "chain_left": str(sp.simplify(determinant_chain_left)),
        "chain_right": str(sp.simplify(determinant_chain_right)),
        "source": str(source),
    }


def verify_periodic_control(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z = sp.symbols("x y z", real=True)
    coordinates = (x, y, z)
    velocity = sp.Matrix([sp.sin(y), sp.sin(z), sp.sin(x)])
    gradient = velocity.jacobian(coordinates)
    divergence = sp.simplify(sp.trace(gradient))
    mean = velocity.applyfunc(lambda item: normalized_integral(item, coordinates))
    book.record(
        "F13 periodic fixture admissibility",
        divergence == 0 and mean == sp.zeros(3, 1),
        f"divergence={divergence}, mean={mean.T}",
    )

    origin = {x: 0, y: 0, z: 0}
    strain = sp.simplify((gradient + gradient.T) / 2)
    strain_origin = strain.subs(origin)
    target = sp.Matrix(
        [
            [0, sp.Rational(1, 2), sp.Rational(1, 2)],
            [sp.Rational(1, 2), 0, sp.Rational(1, 2)],
            [sp.Rational(1, 2), sp.Rational(1, 2), 0],
        ]
    )
    book.exact("F14 periodic fixture origin strain", strain_origin - target)

    strain_spectrum = strain_origin.eigenvals()
    derivative_spectrum = (-2 * strain_origin).eigenvals()
    expected_strain = {sp.Integer(1): 1, -sp.Rational(1, 2): 2}
    expected_derivative = {sp.Integer(-2): 1, sp.Integer(1): 2}
    book.record(
        "F15 strain and initial metric-derivative spectra",
        strain_spectrum == expected_strain
        and derivative_spectrum == expected_derivative,
        f"spec(S)={strain_spectrum}, spec(H_t)={derivative_spectrum}",
    )

    values["periodic_control"] = {
        "velocity": str(velocity),
        "divergence": str(divergence),
        "mean": str(mean),
        "strain_origin": str(strain_origin),
        "strain_spectrum": str(strain_spectrum),
        "initial_metric_derivative_spectrum": str(derivative_spectrum),
    }


def verify_norm_equivalence(book: CheckBook, values: dict[str, Any]) -> None:
    lower = sp.symbols("m", positive=True)
    w1, w2, w3 = sp.symbols("w1 w2 w3", real=True)
    vector = sp.Matrix([w1, w2, w3])
    metric = sp.diag(lower, 2 * lower, 3 * lower)
    weighted = sp.expand((vector.T * metric * vector)[0])
    euclidean = sp.expand((vector.T * vector)[0])
    slack = sp.factor(weighted - lower * euclidean)
    expected_slack = lower * (w2**2 + 2 * w3**2)
    implication = (
        sp.simplify(slack - expected_slack) == 0
        and sp.ask(sp.Q.positive(lower))
        and all(symbol.is_real for symbol in (w1, w2, w3))
    )
    book.record(
        "F16 positive-metric norm equivalence",
        implication,
        f"z^T*G*z-m*|z|^2={slack}>=0",
    )

    values["norm_equivalence"] = {
        "metric": str(metric),
        "weighted_norm": str(weighted),
        "euclidean_norm": str(euclidean),
        "coercivity_slack": str(slack),
    }


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_extensional_control(book, values)
    verify_projected_balance(book, values)
    verify_determinant_identity(book, values)
    verify_periodic_control(book, values)
    verify_norm_equivalence(book, values)

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
            "forward_exact_cancellation": "SUPPORTS" if success else "INCONCLUSIVE",
            "positive_metric_propagation_on_smooth_interval": "SUPPORTS" if success else "INCONCLUSIVE",
            "uniform_coercivity_from_positivity_and_determinant": "CONTRADICTS" if success else "INCONCLUSIVE",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "navier_stokes_trajectory": "NOT_RUN",
            "symbolic_schedule": "FIXED_16_CHECKS",
            "uniform_metric_lower_bound": "UNRESOLVED",
            "positive_propagation_basis": "ANALYTIC_MAXIMUM_PRINCIPLE_PLUS_FIXED_CONTROLS",
            "general_matrix_pde_trajectory": "NOT_RUN",
            "determinant_executable_scope": "SPATIAL_CHAIN_RULE_FIXED_DIAGONAL_CONTROL",
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
        "parent_protocol": PARENT_PROTOCOL,
        "verifier": Path(__file__).resolve(),
    }
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {
        key: {
            "path": path.relative_to(ROOT).as_posix(),
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
    result: dict[str, Any] = {"schema": SCHEMA, **manifest}
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
