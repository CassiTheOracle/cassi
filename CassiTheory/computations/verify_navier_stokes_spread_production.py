#!/usr/bin/env python3
"""Verify the fixed spectral spread-production identities exactly.

Run from the CassiTheory root with a fresh output path. The computation is
symbolic and finite; it evolves no Navier–Stokes trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-spread-production-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_spread_production/verification.json"
SOURCES = (PROTOCOL, Path(__file__).resolve())


class Receipt:
    def __init__(self) -> None:
        self.checks: list[dict[str, object]] = []
        self.failures: list[str] = []

    def check(self, name: str, passed: bool, value: object = None) -> None:
        if any(row["name"] == name for row in self.checks):
            raise ValueError(f"Duplicate verification check: {name}")
        passed = bool(passed)
        row: dict[str, object] = {"name": name, "passed": passed}
        if value is not None:
            row["value"] = json_safe(value)
        self.checks.append(row)
        if not passed:
            self.failures.append(name)

    def exact(self, name: str, actual: sp.Expr, expected: sp.Expr = sp.S.Zero) -> None:
        residual = sp.factor(sp.cancel(actual - expected))
        self.check(name, residual == 0, {"actual": actual, "expected": expected, "residual": residual})


def json_safe(value: object) -> object:
    if isinstance(value, sp.Basic):
        return str(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def product_expectation(
    polynomial: sp.Expr,
    left: sp.Symbol,
    right: sp.Symbol,
    moments: dict[int, sp.Expr],
) -> sp.Expr:
    result = sp.S.Zero
    expanded = sp.Poly(sp.expand(polynomial), left, right)
    for (left_power, right_power), coefficient in expanded.terms():
        result += coefficient * moments[left_power] * moments[right_power]
    return sp.factor(result)


def expectation(
    polynomial: sp.Expr,
    variable: sp.Symbol,
    moments: dict[int, sp.Expr],
) -> sp.Expr:
    result = sp.S.Zero
    expanded = sp.Poly(sp.expand(polynomial), variable)
    for (power,), coefficient in expanded.terms():
        result += coefficient * moments[power]
    return sp.factor(result)


def atomic_moments(supports: Iterable[sp.Expr], weights: Iterable[sp.Expr]) -> dict[int, sp.Expr]:
    support_values = tuple(supports)
    weight_values = tuple(weights)
    if len(support_values) != len(weight_values) or not support_values:
        raise ValueError("Atomic supports and weights must be nonempty and equal in length")
    return {
        order: sp.factor(sum(weight * radius**order for radius, weight in zip(support_values, weight_values)))
        for order in range(5)
    }


def compute() -> dict[str, object]:
    book = Receipt()

    K, E, C, Y, G = sp.symbols("K E C Y G", positive=True)
    a, b, c, d = sp.symbols("a b c d", positive=True)
    r, s = sp.symbols("r s", nonnegative=True)
    v = b - a**2
    eta = v / b
    q = d + b**2 - 2 * a * c

    normalized_moments = {0: sp.S.One, 1: a, 2: b, 3: c, 4: d}
    pair_integrand = sp.expand((r - s) ** 2 * (r**2 + s**2) / 2)
    pair_average = product_expectation(pair_integrand, r, s, normalized_moments)
    book.exact("normalized pair identity", pair_average, q)

    M0, M1, M2, M3, M4 = sp.symbols("M0 M1 M2 M3 M4", positive=True)
    raw_moments = {0: M0, 1: M1, 2: M2, 3: M3, 4: M4}
    raw_pair = product_expectation(
        (r - s) ** 2 * (r**2 + s**2), r, s, raw_moments
    )
    book.exact(
        "unnormalized pair identity",
        raw_pair,
        2 * M0 * M4 + 2 * M2**2 - 4 * M1 * M3,
    )
    physical_raw_pair = sp.factor(
        raw_pair.subs({M0: 2 * K, M1: C, M2: 2 * E, M3: Y, M4: 2 * G})
    )
    physical_Q = 2 * K * G + 2 * E**2 - C * Y
    book.exact("physical pair coefficient", physical_raw_pair, 4 * physical_Q)

    h = sp.expand(d - 2 * a * c + a**2 * b)
    h_from_square = expectation(r**2 * (r - a) ** 2, r, normalized_moments)
    book.exact("quadratic spread remainder square", h_from_square, h)
    book.exact("quadratic spread decomposition", q, b * v + h_from_square)
    physical_substitutions = {
        a: C / (2 * K),
        b: E / K,
        c: Y / (2 * K),
        d: G / K,
    }
    book.exact(
        "Q minus optimal eta E squared coefficient",
        physical_Q - 2 * ((K * E - C**2 / 4) / (K * E)) * E**2,
        2 * K**2 * h.subs(physical_substitutions),
    )

    L = a * (3 * b - a**2)
    book.exact("eta C Y precursor expansion", b * (q - eta * a * c), b * d + b**3 - L * c)
    bd_gap_pair = product_expectation(
        r**2 * s**2 * (r - s) ** 2 / 2, r, s, normalized_moments
    )
    book.exact("third-fourth moment Cauchy pair", bd_gap_pair, b * d - c**2)
    book.exact(
        "eta C Y nonnegative decomposition",
        b * d + b**3 - L * c,
        (b * d - c**2) + (c - L / 2) ** 2 + b**3 - L**2 / 4,
    )
    book.exact(
        "eta C Y square completion",
        c**2 - L * c + b**3,
        (c - L / 2) ** 2 + b**3 - L**2 / 4,
    )
    x = sp.symbols("x", nonnegative=True)
    book.exact(
        "eta C Y bounded polynomial factor",
        1 - x**2 * (3 - x**2) ** 2 / 4,
        (1 - x**2) ** 2 * (4 - x**2) / 4,
    )
    book.exact(
        "physical eta C Y coefficient",
        physical_Q - ((K * E - C**2 / 4) / (K * E)) * C * Y / 2,
        2 * K**2 * (q - eta * a * c).subs(physical_substitutions),
    )

    central_fourth = sp.expand(d - 4 * a * c + 6 * a**2 * b - 3 * a**4)
    radial_third = sp.expand(c - 2 * a * b + a**3)
    central_from_binomial = expectation((r - a) ** 4, r, normalized_moments)
    radial_third_from_square = expectation(r * (r - a) ** 2, r, normalized_moments)
    book.exact("central fourth binomial expansion", central_from_binomial, central_fourth)
    book.exact("radial centered third square", radial_third_from_square, radial_third)
    book.exact(
        "central fourth Q decomposition",
        q - central_from_binomial,
        v**2 + 2 * a * radial_third_from_square,
    )
    book.exact(
        "physical centered fourth coefficient",
        2 * K * central_fourth.subs(physical_substitutions),
        physical_Q / K - 2 * K * (q - central_fourth).subs(physical_substitutions),
    )

    supports = (sp.S.Zero, sp.S.One, sp.Integer(2), sp.Integer(5))
    weights = (sp.Rational(1, 10), sp.Rational(1, 5), sp.Rational(3, 10), sp.Rational(2, 5))
    fixed = atomic_moments(supports, weights)
    fixed_values = {a: fixed[1], b: fixed[2], c: fixed[3], d: fixed[4]}
    fixed_v = sp.factor(v.subs(fixed_values))
    fixed_q = sp.factor(q.subs(fixed_values))
    fixed_h = sp.factor(h.subs(fixed_values))
    fixed_eta_cy_gap = sp.factor((q - eta * a * c).subs(fixed_values))
    fixed_central_gap = sp.factor((q - central_fourth).subs(fixed_values))
    book.check("fixed atom probability normalization", sum(weights) == 1, sum(weights))
    book.check("fixed atom positive variance", fixed_v > 0, fixed_v)
    book.check("fixed atom positive Q", fixed_q > 0, fixed_q)
    book.check("fixed atom eta E squared inequality", fixed_h >= 0, fixed_h)
    book.check("fixed atom eta C Y inequality", fixed_eta_cy_gap >= 0, fixed_eta_cy_gap)
    book.check("fixed atom centered fourth inequality", fixed_central_gap >= 0, fixed_central_gap)

    p, radius = sp.symbols("p radius", positive=True)
    two_atom = {
        a: p * radius,
        b: p * radius**2,
        c: p * radius**3,
        d: p * radius**4,
    }
    two_q = sp.factor(q.subs(two_atom))
    two_eta = sp.factor(eta.subs(two_atom))
    two_k = sp.factor(central_fourth.subs(two_atom))
    book.exact("two atom Q formula", two_q, p * (1 - p) * radius**4)
    book.exact("two atom eta formula", two_eta, 1 - p)
    book.exact(
        "sharp normalized q over eta a c ratio",
        sp.factor(two_q / (two_eta * two_atom[a] * two_atom[c])),
        1 / p,
    )
    book.exact(
        "sharp physical Q over eta E squared ratio",
        sp.factor(2 * two_q / (two_eta * two_atom[b] ** 2)),
        2 / p,
    )
    book.exact("two atom central ratio", sp.factor(two_k / two_q), p**3 + (1 - p) ** 3)
    book.exact(
        "normalized q over eta a c sharp limit",
        sp.limit(two_q / (two_eta * two_atom[a] * two_atom[c]), p, 1),
        1,
    )
    book.exact(
        "physical Q over eta E squared sharp limit",
        sp.limit(2 * two_q / (two_eta * two_atom[b] ** 2), p, 1),
        2,
    )
    book.exact("central fourth sharp limit", sp.limit(two_k / two_q, p, 1), 1)
    book.check(
        "two atom interior probability Q positive",
        two_q.subs({p: sp.Rational(1, 2), radius: 1}) > 0,
        two_q.subs({p: sp.Rational(1, 2), radius: 1}),
    )

    m, A, F, uB = sp.symbols("m A F uB", real=True)
    centered_pairing = K * (A - 2 * m * F + m**2 * uB)
    book.exact(
        "centered spread production identity",
        centered_pairing.subs({m: C / (2 * K), uB: 0}),
        K * A - C * F,
    )

    eps, nu, cS, sqrt_Y, sqrt_Q = sp.symbols(
        "eps nu cS sqrt_Y sqrt_Q", positive=True
    )
    critical_young_gap = (
        eps * sqrt_Y**2
        + 2 * cS**2 * sqrt_Q**2 / eps
        - 2 * sp.sqrt(2) * cS * sqrt_Y * sqrt_Q
    )
    critical_young_square = (
        sp.sqrt(eps) * sqrt_Y
        - sp.sqrt(2) * cS * sqrt_Q / sp.sqrt(eps)
    ) ** 2
    book.exact("critical Young square", critical_young_gap, critical_young_square)

    sqrt_KEY = sp.symbols("sqrt_KEY", positive=True)
    spread_young_gap = (
        nu * sqrt_Q**2 / 2
        + cS**2 * sqrt_KEY**2 / nu
        - sp.sqrt(2) * cS * sqrt_KEY * sqrt_Q
    )
    spread_young_square = (
        sp.sqrt(nu / 2) * sqrt_Q - cS * sqrt_KEY / sp.sqrt(nu)
    ) ** 2
    book.exact("spread production Young square", spread_young_gap, spread_young_square)

    V0, Vt, positive_slack = sp.symbols("V0 Vt positive_slack", nonnegative=True)
    signed_production = sp.symbols("signed_production", real=True)
    positive_production = signed_production + positive_slack
    integrated_Q = (V0 - Vt + signed_production) / nu
    integrated_bound_gap = sp.factor(
        2 * cS**2 * (V0 + positive_production) / nu**2
        - 2 * cS**2 * integrated_Q / nu
    )
    book.exact(
        "integrated positive-production implication",
        integrated_bound_gap,
        2 * cS**2 * (Vt + positive_slack) / nu**2,
    )

    interpolation_pair = product_expectation(
        r * s * (r - s) ** 2 / 2, r, s, normalized_moments
    )
    book.exact("critical interpolation pair identity", interpolation_pair, a * c - b**2)
    fixed_interpolation_gap = sp.factor(interpolation_pair.subs(fixed_values))
    book.check(
        "fixed atom critical interpolation inequality",
        fixed_interpolation_gap >= 0,
        fixed_interpolation_gap,
    )

    N = sp.symbols("N", positive=True, integer=True)
    delta_C = N**7 / 64 - N**6
    mixing_lower = delta_C / cS**2
    q_slack, mixing_Vt, mixing_positive_slack = sp.symbols(
        "q_slack mixing_Vt mixing_positive_slack", nonnegative=True
    )
    mixing_Q_integral = mixing_lower + q_slack
    mixing_signed_production = mixing_Vt + mixing_Q_integral
    mixing_positive_production = mixing_signed_production + mixing_positive_slack
    book.exact(
        "mixing critical-growth implication",
        cS**2 * mixing_Q_integral - delta_C,
        cS**2 * q_slack,
    )
    book.exact(
        "mixing spread-production implication",
        mixing_positive_production - mixing_lower,
        mixing_Vt + q_slack + mixing_positive_slack,
    )
    book.exact(
        "mixing Q lower-bound ratio",
        mixing_lower / N**6,
        (N / 64 - 1) / cS**2,
    )
    book.check(
        "mixing lower bound positive at first fixed integer",
        mixing_lower.subs({N: 65, cS: 1}) > 0,
        mixing_lower.subs({N: 65, cS: 1}),
    )
    mixing_ratio_limit = sp.limit(mixing_lower / N**6, N, sp.oo)
    book.check(
        "mixing lower-bound ratio diverges",
        mixing_ratio_limit == sp.oo,
        mixing_ratio_limit,
    )

    if not book.checks:
        raise RuntimeError("No verification checks were generated")

    return {
        "schema": "cassi.navier-stokes.spread-production.verification.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not book.failures else "FAIL",
        "classification": "DERIVED CONDITIONAL REDUCTION" if not book.failures else "INCONCLUSIVE",
        "scope": {
            "equation": "Unforced periodic three-dimensional incompressible Navier-Stokes",
            "kind": "Exact symbolic moment and coefficient audit; no trajectory evolution",
            "domain_assumptions": (
                "The accompanying proof supplies R>=0, 0<=a/sqrt(b)<=1, "
                "positive moment measures and the Prodi-Serrin continuation step"
            ),
            "remaining": "Uniform initial-data control of cumulative positive spread production is unresolved",
        },
        "check_count": len(book.checks),
        "failure_count": len(book.failures),
        "failures": book.failures,
        "checks": book.checks,
        "fixed_atom": {
            "supports": supports,
            "weights": weights,
            "moments": fixed,
        },
        "sharpness": {
            "measure": "(1-p) delta_0 + p delta_radius",
            "normalized_q_over_eta_a_c": sp.factor(
                two_q / (two_eta * two_atom[a] * two_atom[c])
            ),
            "physical_Q_over_eta_E2": sp.factor(
                2 * two_q / (two_eta * two_atom[b] ** 2)
            ),
            "central_fourth_over_q": sp.factor(two_k / two_q),
        },
        "mixing_family": {
            "viscosity": 1,
            "initial_critical_norm_squared": N**6,
            "endpoint_critical_lower_bound": N**7 / 64,
            "Q_integral_lower_bound": mixing_lower,
            "positive_production_integral_lower_bound": mixing_lower,
            "first_positive_integer_N": 65,
        },
        "versions": {
            "python": sys.version,
            "sympy": sp.__version__,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable receipt: {output}")

    source_hashes = {path.relative_to(ROOT).as_posix(): sha256(path) for path in SOURCES}
    result = compute()

    current_hashes = {path.relative_to(ROOT).as_posix(): sha256(path) for path in SOURCES}
    if current_hashes != source_hashes:
        raise RuntimeError("A frozen source changed during verification")

    output.parent.mkdir(parents=True, exist_ok=True)
    sources_dir = output.with_suffix(".sources")
    if sources_dir.exists():
        raise FileExistsError(f"Refusing to overwrite source snapshot directory: {sources_dir}")
    sources_dir.mkdir(parents=True)

    snapshots: list[dict[str, str]] = []
    for source in SOURCES:
        relative = source.relative_to(ROOT)
        snapshot = sources_dir / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source.read_bytes())
        snapshots.append(
            {
                "path": relative.as_posix(),
                "sha256": source_hashes[relative.as_posix()],
                "snapshot": snapshot.relative_to(output.parent).as_posix(),
                "snapshot_sha256": sha256(snapshot),
            }
        )

    manifest = output.with_suffix(".inputs.json")
    manifest_payload = {
        "schema": "cassi.navier-stokes.spread-production.inputs.v1",
        "created_utc": result["created_utc"],
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "sources": snapshots,
    }
    manifest.write_text(json.dumps(json_safe(manifest_payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result["input_manifest"] = {
        "path": manifest.relative_to(ROOT).as_posix(),
        "sha256": sha256(manifest),
    }
    result["sources"] = snapshots
    output.write_text(json.dumps(json_safe(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Receipt: {output}")
    print(json.dumps({key: result[key] for key in ("status", "classification", "check_count", "failure_count")}, indent=2))
    if result["status"] == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    print("FAILED CHECKS: " + ", ".join(result["failures"]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
