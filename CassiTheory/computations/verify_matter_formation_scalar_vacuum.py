#!/usr/bin/env python3
"""Qualify the frozen local static scalar-vacuum energy; no spatial evolution.

Run from the CassiTheory root:
    python computations/verify_matter_formation_scalar_vacuum.py --output-dir runs/20260906_matter_formation_scalar_vacuum
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "computations/matter-formation-scalar-vacuum-prereg.md"
CONTINUUM = ROOT / "computations/matter-formation-continuum-admissibility-prereg.md"
VERDICT = "CONTRADICTS—global lower boundedness of the specified local static one-loop scalar energy"


def identity(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    try:
        name = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        name = resolved.as_posix()
    return {"path": name, "sha256": hashlib.sha256(resolved.read_bytes().replace(b"\r\n", b"\n")).hexdigest()}


def calculate() -> tuple[dict, list[dict]]:
    m, x, radius, width, amplitude, bound = sp.symbols("m x R w A M", positive=True)
    d = m - 1
    polynomial = 2 * d + 7 * d**2 + sp.Rational(26, 3) * d**3 + sp.Rational(25, 6) * d**4
    vacuum = -(m**4 * sp.log(m**2) - polynomial) / (16 * sp.pi**2)
    total = 72 * d**2 + vacuum
    leading = sp.limit(total / (m**4 * sp.log(m**2)), m, sp.oo)
    scalar_curvature = sp.diff(total, m, 2).subs(m, 1) / 16

    # Separate rational arithmetic: no logarithm, floating-point sign or SymPy limit.
    df = Fraction(63)
    pf = 2 * df + 7 * df**2 + Fraction(26, 3) * df**3 + Fraction(25, 6) * df**4
    bracket_lower = 8 * Fraction(64)**4 - pf
    zero_loop = Fraction(72) * df**2
    upper = zero_loop - bracket_lower / 160
    symbolic_upper = 72 * 63**2 - (8 * 64**4 - polynomial.subs(m, 64)) / 160

    # The two elementary strict bounds used by the rational sign argument.
    # Jensen applied to strictly convex 1/x on [1,2] gives log(2)>2/3.
    inverse_curvature = sp.diff(1 / x, x, 2)
    # This integral is strictly positive on (0,1), proving pi<22/7.
    pi_integral = sp.integrate(x**4 * (1 - x)**4 / (1 + x**2), (x, 0, 1))

    gradient = 2 * sp.pi * amplitude**2 / width**2 * sp.integrate(x**2, (x, radius, radius + width))
    gradient_closed = 2 * sp.pi * amplitude**2 * (radius**2 / width + radius + width / 3)
    shell = 4 * sp.pi * bound * (radius**2 * width + radius * width**2 + width**3 / 3)
    gradient_ratio = sp.limit(gradient.subs(width, sp.sqrt(radius)) / radius**3, radius, sp.oo)
    shell_ratio = sp.limit(shell.subs(width, sp.sqrt(radius)) / radius**3, radius, sp.oo)

    checks = []

    def check(name: str, condition) -> None:
        checks.append({"name": name, "pass": bool(condition)})

    check("reference_value", total.subs(m, 1) == 0)
    check("reference_slope", sp.diff(total, m).subs(m, 1) == 0)
    check("reference_mass_curvature", sp.diff(total, m, 2).subs(m, 1) == 144)
    check("reference_scalar_curvature", scalar_curvature == 9)
    check("large_field_coefficient", sp.simplify(leading + 1 / (16 * sp.pi**2)) == 0)
    check("strict_log_bound_identity", sp.simplify(inverse_curvature - 2 / x**3) == 0 and inverse_curvature.is_positive)
    check("witness_log_multiple", sp.expand_log(sp.log(sp.Integer(64)**2), force=True) == 12 * sp.log(2))
    check("strict_pi_bound_identity", sp.simplify(pi_integral - (sp.Rational(22, 7) - sp.pi)) == 0)
    check("pi_square_rational_bound", Fraction(22, 7)**2 < 10)
    check("positive_bracket_lower_bound", bracket_lower > 0)
    check("independent_rational_agreement", sp.simplify(symbolic_upper - sp.Rational(upper.numerator, upper.denominator)) == 0)
    check("negative_potential_upper_bound", upper < 0)
    check("gradient_integral", sp.simplify(gradient - gradient_closed) == 0)
    check("gradient_subvolume", gradient_ratio == 0)
    check("shell_subvolume", shell_ratio == 0)
    check("zero_loop_control", zero_loop > 0 and sp.diff(72 * d**2, m, 2) / 16 == 9)

    derived = {
        "reference_mass": 1,
        "yukawa_coupling": 0.25,
        "scalar_mass": 3,
        "witness_mass": 64,
        "witness_scalar": 252,
        "reference_scalar_curvature": float(scalar_curvature),
        "leading_coefficient_exact": str(leading),
        "leading_coefficient": float(leading),
        "bracket_lower_exact": str(bracket_lower),
        "potential_upper_exact": str(upper),
        "potential_upper": float(upper),
        "potential_at_witness": float(sp.N(total.subs(m, 64), 40)),
        "zero_loop_potential_at_witness": float(zero_loop),
        "gradient_over_volume_limit": float(gradient_ratio),
        "shell_over_volume_bound_limit": float(shell_ratio),
    }
    return derived, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, default=PREREG)
    args = parser.parse_args()
    target = args.output_dir / "results.json"
    if target.exists():
        parser.error(f"refusing to overwrite {target}")
    result = {"schema": "cassi-scalar-vacuum-boundary-v1", "identities": {},
              "derived": {}, "checks": [], "verdict": "INCONCLUSIVE",
              "numerical_pass": False, "failures": []}
    try:
        for key, path in (("program", Path(__file__)), ("prereg", args.prereg), ("continuum_prereg", CONTINUUM)):
            result["identities"][key] = identity(path)
        result["derived"], result["checks"] = calculate()
        result["failures"] = [item["name"] for item in result["checks"] if not item["pass"]]
        result["numerical_pass"] = not result["failures"]
        if result["numerical_pass"]:
            result["verdict"] = VERDICT
    except Exception as error:
        result["failures"].append(f"{type(error).__name__}: {error}")
    text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    print(text, end="")
    return 0 if result["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
