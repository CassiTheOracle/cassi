#!/usr/bin/env python3
"""Verify the frozen local SU(2) conditional transport expansion."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-transport-expansion-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_transport_expansion" / "verification.json"
KAPPAS = (0.5, 1.0, 2.0, 4.0)
BOUNDARIES = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 2.0))
TANGENTS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
TOLERANCE = 1.0e-11

Poly = dict[tuple[int, int, int], float]
ZERO: Poly = {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(*polynomials: Poly) -> Poly:
    out: Poly = {}
    for polynomial in polynomials:
        for exponent, value in polynomial.items():
            out[exponent] = out.get(exponent, 0.0) + value
            if abs(out[exponent]) < 1.0e-13:
                del out[exponent]
    return out


def scale(factor: float, polynomial: Poly) -> Poly:
    return {
        exponent: factor * value
        for exponent, value in polynomial.items()
        if abs(factor * value) >= 1.0e-13
    }


def multiply(left: Poly, right: Poly) -> Poly:
    out: Poly = {}
    for left_exp, left_value in left.items():
        for right_exp, right_value in right.items():
            exponent = tuple(a + b for a, b in zip(left_exp, right_exp))
            out[exponent] = out.get(exponent, 0.0) + left_value * right_value
    return {exponent: value for exponent, value in out.items() if abs(value) >= 1.0e-13}


def constant(value: float) -> Poly:
    return {} if abs(value) < 1.0e-13 else {(0, 0, 0): value}


def variable(index: int) -> Poly:
    exponent = [0, 0, 0]
    exponent[index] = 1
    return {tuple(exponent): 1.0}


def derivative(polynomial: Poly, index: int) -> Poly:
    out: Poly = {}
    for exponent, value in polynomial.items():
        power = exponent[index]
        if power == 0:
            continue
        reduced = list(exponent)
        reduced[index] -= 1
        reduced_tuple = tuple(reduced)
        out[reduced_tuple] = out.get(reduced_tuple, 0.0) + power * value
    return out


def gradient(polynomial: Poly) -> tuple[Poly, Poly, Poly]:
    return tuple(derivative(polynomial, index) for index in range(3))  # type: ignore[return-value]


def laplacian(polynomial: Poly) -> Poly:
    return add(*(derivative(derivative(polynomial, index), index) for index in range(3)))  # type: ignore[arg-type]


def gaussian_moment(power: int, variance: float) -> float:
    if power % 2:
        return 0.0
    value = 1.0
    for order in range(1, power // 2 + 1):
        value *= (2 * order - 1) * variance
    return value


def expectation(polynomial: Poly, variance: float) -> float:
    return sum(
        value
        * gaussian_moment(exponent[0], variance)
        * gaussian_moment(exponent[1], variance)
        * gaussian_moment(exponent[2], variance)
        for exponent, value in polynomial.items()
    )


def dot(left: tuple[Poly, Poly, Poly], right: tuple[Poly, Poly, Poly]) -> Poly:
    return add(*(multiply(a, b) for a, b in zip(left, right)))  # type: ignore[arg-type]


def norm_squared(vector: tuple[Poly, Poly, Poly]) -> Poly:
    return dot(vector, vector)


def vector_constant(values: tuple[float, float, float]) -> tuple[Poly, Poly, Poly]:
    return tuple(constant(value) for value in values)  # type: ignore[return-value]


def add_vectors(left: tuple[Poly, Poly, Poly], right: tuple[Poly, Poly, Poly]) -> tuple[Poly, Poly, Poly]:
    return tuple(add(a, b) for a, b in zip(left, right))  # type: ignore[return-value]


def a_term(q: tuple[float, float, float], r: tuple[Poly, Poly, Poly]) -> Poly:
    q_squared = sum(value * value for value in q)
    r_squared = norm_squared(r)
    q_dot_r = add(*(scale(value, coordinate) for value, coordinate in zip(q, r)))  # type: ignore[arg-type]
    return add(
        add(constant(q_squared * q_squared / 384.0), scale(1.0 / 384.0, multiply(r_squared, r_squared))),
        add(
            scale(q_squared / 64.0, r_squared),
            scale(1.0 / 96.0, multiply(q_dot_r, add(constant(q_squared), r_squared))),
        ),
    )


def l0(polynomial: Poly, kappa: float) -> Poly:
    result = scale(-1.0, laplacian(polynomial))
    for index in range(3):
        result = add(result, scale(kappa / 2.0, multiply(variable(index), derivative(polynomial, index))))
    return result


def basis() -> tuple[tuple[int, int, int], ...]:
    exponents: list[tuple[int, int, int]] = []
    for first in range(4):
        for second in range(4 - first):
            for third in range(4 - first - second):
                exponent = (first, second, third)
                if any(exponent):
                    exponents.append(exponent)
    return tuple(exponents)


BASIS = basis()
BASIS_INDEX = {exponent: index for index, exponent in enumerate(BASIS)}


def monomial(exponent: tuple[int, int, int]) -> Poly:
    return {exponent: 1.0}


def invert_l0(rhs: Poly, kappa: float) -> Poly:
    matrix = np.zeros((len(BASIS), len(BASIS)), dtype=float)
    for column, exponent in enumerate(BASIS):
        image = l0(monomial(exponent), kappa)
        for target, value in image.items():
            if target in BASIS_INDEX:
                matrix[BASIS_INDEX[target], column] = value
    variance = 2.0 / kappa
    rhs_mean = expectation(rhs, variance)
    if abs(rhs_mean) > 1.0e-9:
        raise ValueError(f"Poisson right-hand side is not Gaussian-centered: mean={rhs_mean}, rhs={rhs}")
    vector = np.array([rhs.get(exponent, 0.0) for exponent in BASIS], dtype=float)
    coefficients = np.linalg.solve(matrix, vector)
    solution: Poly = {
        exponent: float(value)
        for exponent, value in zip(BASIS, coefficients)
        if abs(value) >= 1.0e-12
    }
    solution[(0, 0, 0)] = -expectation(solution, variance)
    if abs(expectation(solution, variance)) > 1.0e-10:
        raise ValueError("Poisson solution was not centered")
    residual = add(l0(solution, kappa), scale(-1.0, rhs))
    residual_error = max((abs(value) for value in residual.values()), default=0.0)
    if residual_error > 1.0e-9:
        raise ValueError(f"Poisson reconstruction failed: residual={residual_error}")
    return solution


def scalar_part(polynomial: Poly) -> float:
    return polynomial.get((0, 0, 0), 0.0)


def row(kappa: float, z: tuple[float, float, float], xi: tuple[float, float, float]) -> dict[str, Any]:
    variance = 2.0 / kappa
    r = tuple(add(variable(index), constant(-z[index] / 2.0)) for index in range(3))  # type: ignore[assignment]
    r_squared = norm_squared(r)
    phi = add(scale(kappa, add(a_term((0.0, 0.0, 0.0), r), a_term(z, r))), scale(-1.0 / 12.0, r_squared))

    score_first: list[Poly] = []
    for index in range(3):
        derivative_action = scale(-kappa / 96.0, multiply(r[index], r_squared))
        leading_action = scale(kappa / 4.0, r[index])
        covariance = expectation(multiply(leading_action, phi), variance) - expectation(leading_action, variance) * expectation(phi, variance)
        score_first.append(add(scale(-1.0, derivative_action), add(constant(expectation(derivative_action, variance)), constant(covariance))))

    w0 = add(*(scale(-xi[index] / 2.0, variable(index)) for index in range(3)))  # type: ignore[arg-type]
    grad_w0 = gradient(w0)
    grad_phi = gradient(phi)

    metric = [[ZERO for _ in range(3)] for _ in range(3)]
    for i in range(3):
        for j in range(3):
            metric[i][j] = scale(
                1.0 / 12.0,
                add((r_squared if i == j else ZERO), scale(-1.0, multiply(r[i], r[j]))),
            )

    l1_w: list[Poly] = []
    for j in range(3):
        divergence = ZERO
        for i in range(3):
            divergence = add(
                divergence,
                add(
                    derivative(metric[i][j], i),
                    scale(-kappa / 2.0, multiply(variable(i), metric[i][j])),
                ),
            )
        l1_w.append(
            add(
                scale(-scalar_part(grad_w0[j]), grad_phi[j]),
                scale(-scalar_part(grad_w0[j]), divergence),
            )
        )
    score_projection = add(*(scale(xi[index], score_first[index]) for index in range(3)))
    l1_projection = add(*(scale(xi[index], l1_w[index]) for index in range(3)))
    rhs = add(score_projection, scale(-1.0, l1_projection))
    try:
        w1 = invert_l0(rhs, kappa)
    except ValueError as exc:
        raise ValueError(f"Poisson failure at kappa={kappa}, z={z}, xi={xi}") from exc

    cross = 2.0 * expectation(dot(grad_w0, gradient(w1)), variance)

    metric_cost = 0.0
    for i in range(3):
        for j in range(3):
            metric_cost += scalar_part(grad_w0[i]) * scalar_part(grad_w0[j]) * expectation(metric[i][j], variance)

    coefficient = cross + metric_cost
    expected = -1.0 / (4.0 * kappa) + (
        sum(value * value for value in z)
        - sum(z[index] * xi[index] for index in range(3)) ** 2
    ) / 64.0
    finite_values = [coefficient, expected, cross, metric_cost, 0.25]
    if not all(math.isfinite(value) for value in finite_values):
        raise FloatingPointError(f"nonfinite local coefficient: {finite_values}")
    return {
        "kappa": kappa,
        "z": list(z),
        "xi": list(xi),
        "theta0_squared": 0.25,
        "poisson_contribution": cross,
        "metric_contribution": metric_cost,
        "c1": coefficient,
        "expected_c1": expected,
        "absolute_error": abs(coefficient - expected),
    }


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), **details}


def compute_receipt() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for kappa in KAPPAS:
        for z in BOUNDARIES:
            for xi in TANGENTS:
                measured = row(kappa, z, xi)
                rows.append(measured)
                finite = all(math.isfinite(float(measured[key])) for key in ("theta0_squared", "poisson_contribution", "metric_contribution", "c1", "expected_c1", "absolute_error"))
                checks.append(check(f"finite_k{kappa:g}_z{z}_x{xi}", finite))
                checks.append(check(f"theta0_k{kappa:g}_z{z}_x{xi}", abs(measured["theta0_squared"] - 0.25) <= TOLERANCE, measured=measured["theta0_squared"], expected=0.25))
                checks.append(check(f"c1_k{kappa:g}_z{z}_x{xi}", measured["absolute_error"] <= TOLERANCE, measured=measured["c1"], expected=measured["expected_c1"], error=measured["absolute_error"]))

    checks.append(check("fixed_schedule", len(rows) == 48 and len(checks) == 144, rows=len(rows), checks=len(checks)))
    checks.append(check("finite_summary", all(math.isfinite(float(row_value["absolute_error"])) for row_value in rows)))
    alpha = (0.0, 1.0, 0.0)
    xi = (1.0, 0.0, 0.0)
    transverse = sum(value * value for value in alpha) - sum(alpha[j] * xi[j] for j in range(3)) ** 2
    checks.append(check("boundary_target_nonzero", abs(transverse) > 1.0e-12, transverse=transverse))
    for index, u in enumerate((1.0e-2, 1.0e-3, 1.0e-4)):
        root = math.sqrt(u)
        z = (alpha[0] / root, alpha[1] / root, alpha[2] / root)
        expected = transverse / 64.0
        try:
            boundary = row(1.0, z, xi)
            measured = u * (boundary["c1"] + 0.25)
            failure = None
        except Exception as error:  # noqa: BLE001
            measured = float("nan")
            failure = f"{type(error).__name__}: {error}"
        checks.append(
            check(
                f"boundary_scaling_{index}",
                failure is None and math.isfinite(measured) and abs(measured - expected) <= TOLERANCE,
                kappa=1.0,
                u=u,
                z=list(z),
                measured=measured,
                expected=expected,
                failure=failure,
                chart_annotation="z grows as u^{-1/2}; the boundary contribution is routed through the verified c1 row",
            )
        )
    passed = all(item["pass"] for item in checks)
    boundary_checks = [item for item in checks if item["name"].startswith("boundary_scaling_") or item["name"] == "boundary_target_nonzero"]
    boundary_ok = len(boundary_checks) == 4 and all(item["pass"] for item in boundary_checks)
    return {
        "schema": "cassi.yang-mills.su2-transport-expansion.v1",
        "verdict": "PASS" if passed else "FAIL",
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "protocol_sha256": sha256(PROTOCOL),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(SOURCE),
        "tolerance": TOLERANCE,
        "schedule": {"kappas": list(KAPPAS), "boundaries": [list(z) for z in BOUNDARIES], "tangents": [list(xi) for xi in TANGENTS]},
        "summary": {"rows": len(rows), "checks": len(checks), "passed": sum(item["pass"] for item in checks), "failed": sum(not item["pass"] for item in checks), "max_error": max(row_value["absolute_error"] for row_value in rows)},
        "classifications": {"local_chart_expansion": "SUPPORTS" if passed else "INCONCLUSIVE", "full_holonomy_boundary_uniformity": "REJECT_CHART_UNIFORMITY" if passed and boundary_ok else "INCONCLUSIVE", "exact_interacting_vacuum": "UNRESOLVED"},
        "rows": rows,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest = output.with_suffix(".inputs.json")
    snapshots = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest, snapshots)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = {"protocol": PROTOCOL.read_bytes(), "verifier": SOURCE.read_bytes()}
    identities = {
        key: {"path": (PROTOCOL if key == "protocol" else SOURCE).relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(value).hexdigest()}
        for key, value in source_bytes.items()
    }
    snapshots.mkdir()
    shutil.copy2(PROTOCOL, snapshots / PROTOCOL.name)
    shutil.copy2(SOURCE, snapshots / SOURCE.name)
    manifest.write_text(json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(), "identities": identities}, indent=2) + "\n", encoding="utf-8")
    receipt = compute_receipt()
    receipt["inputs"] = {"manifest": manifest.relative_to(ROOT).as_posix(), "snapshots": snapshots.relative_to(ROOT).as_posix()}
    if PROTOCOL.read_bytes() != source_bytes["protocol"] or SOURCE.read_bytes() != source_bytes["verifier"]:
        raise RuntimeError("frozen source changed during execution")
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], **receipt["summary"], "classifications": receipt["classifications"]}, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
