#!/usr/bin/env python3
"""Evaluate the frozen registered-coefficient Hopf size/connection trial.

python computations/matter_formation_relative_trial.py --output-dir runs/<fresh-name>

This is an exact trial-family calculation with independent radial quadrature,
not a solution of the field equations or a general Hopf stability theorem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import mpmath as mp
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
HEADING = "### 19.8 Registered-coefficient trial: pre-execution criteria\n"
PROTOCOL_SHA = "c8c3abd56f811291c4ef0cd2933d523a69c8499d47bea533140deec920065630"
VERDICT = "CONTRADICTS—local minimum of the registered-coefficient Hopf size/connection trial"
SIGMA = (sp.Matrix([[0, 1], [1, 0]]), sp.Matrix([[0, -sp.I], [sp.I, 0]]), sp.diag(1, -1))
IDENTITY = sp.eye(2)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_section(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("exactly one frozen heading is required")
    after = text.split(HEADING, 1)[1]
    end = re.search(r"\n#{1,3} ", after)
    return (HEADING + (after[:end.start()] if end else after)).rstrip() + "\n"


def clean(value):
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(lambda item: sp.factor(sp.cancel(item)))
    return sp.factor(sp.cancel(value))


def spin(vector):
    return sum((value * matrix for value, matrix in zip(vector, SIGMA)), sp.zeros(2))


def vector(matrix):
    return sp.Matrix([sp.trace(matrix * sigma) / 2 for sigma in SIGMA])


def calculate() -> tuple[list[dict], dict]:
    checks = []

    def group(name, residuals, predicates, evidence):
        residuals = {key: clean(value) for key, value in residuals.items()}
        identities = {}
        for key, value in residuals.items():
            passed = all(item == 0 for item in value) if isinstance(value, sp.MatrixBase) else value == 0
            identities[key] = {"pass": bool(passed), "residual": str(value)}
        flags = {key: bool(value) for key, value in predicates.items()}
        checks.append({"name": name, "pass": all(item["pass"] for item in identities.values()) and all(flags.values()),
                       "identities": identities, "predicates": flags,
                       "evidence": {key: str(value) for key, value in evidence.items()}})

    phi = (1 + sp.sqrt(5)) / 2
    c = sp.simplify(phi**-3)
    gamma_x, u_phi = sp.Integer(1), sp.Integer(4)
    p, q, gamma = sp.Rational(1, 8), gamma_x / 2, gamma_x / 2
    w = sp.simplify(u_phi * (1 + phi)**2 / 8)
    t = sp.factor(q / (p + q))
    xyz = sp.Matrix(sp.symbols("X Y Z", real=True))
    radius2 = xyz.dot(xyz)
    U3 = ((radius2**3 - 1) * IDENTITY + 2 * sp.I * radius2 * spin(xyz)) / (1 + radius2**3)
    av = sp.Matrix(sp.symbols("a0:3", real=True))
    dpsi = -sp.I * spin(av) * sp.Matrix([1, 0]) / 2
    r = sp.symbols("r", positive=True)
    group("registered_coefficients_and_profile", {
        "fundamental_coefficient": (dpsi.H * dpsi)[0] / 2 - p * av.dot(av),
        "stiffness_ratio": t - sp.Rational(4, 5),
        "profile_unitarity": U3.H * U3 - IDENTITY,
        "origin_matrix": U3.subs(dict.fromkeys(xyz, 0)) + IDENTITY,
        "squared_outer_distance": sp.trace((U3 - IDENTITY).H * (U3 - IDENTITY)) - 8 / (1 + radius2**3),
        "outer_limit": sp.limit(8 / (1 + r**6), r, sp.oo),
    }, {}, {"p": p, "q": q, "gamma": gamma, "w": w, "t": t,
            "profile": U3, "constant_boundary_composition": c})

    cf, sf, fp, eta, d = sp.symbols("cos_f sin_f fprime eta d", real=True)
    U = cf * IDENTITY + sp.I * sf * SIGMA[2]
    base = d * SIGMA[0] + eta * SIGMA[2]
    Nmat = U * base * U.H
    derivatives_U = (sp.I * sf * SIGMA[0] / r, sp.I * sf * SIGMA[1] / r,
                     fp * (-sf * IDENTITY + sp.I * cf * SIGMA[2]))
    derivatives_N = [du * base * U.H + U * base * du.H for du in derivatives_U]
    nv = vector(Nmat)
    dn = [vector(item) for item in derivatives_N]

    def unit_reduce(value):
        numerator, denominator = sp.cancel(value).as_numer_denom()
        numerator = sp.rem(numerator, cf**2 + sf**2 - 1, cf)
        numerator = sp.rem(numerator, d**2 + eta**2 - 1, d)
        return sp.factor(numerator / denominator)

    polar_A = unit_reduce(sum((item.T * item)[0] for item in dn))
    polar_B = unit_reduce(sum(nv.dot(dn[i].cross(dn[j]))**2 for i in range(3) for j in range(i + 1, 3)))
    expected_A = 4 * ((1 - eta**2) * fp**2 + (1 + eta**2) * sf**2 / r**2)
    expected_B = 16 * (eta**2 * sf**4 / r**4 + (1 - eta**2) * fp**2 * sf**2 / r**2)
    averaged_A = sp.expand(polar_A).subs(eta**2, sp.Rational(1, 3))
    averaged_B = sp.expand(polar_B).subs(eta**2, sp.Rational(1, 3))
    nx, ny, nz, cv, dv, aa, bb = sp.symbols("nx ny nz c dcomp arot brot", real=True)
    delta = aa * ((dv * nx + cv * nz) * nz - cv) - bb * dv * ny
    sphere_average = 0
    for powers, coefficient in sp.Poly(sp.expand(delta**2), nx, ny, nz).terms():
        if any(power % 2 for power in powers):
            continue
        moment = sp.prod(sp.factorial2(power - 1) for power in powers) / sp.factorial2(sum(powers) + 1)
        sphere_average += coefficient * moment
    sphere_average = sp.expand(sphere_average).subs(dv**2, 1 - cv**2)
    expected_C = aa**2 * (1 + 7 * cv**2) / 15 + bb**2 * (1 - cv**2) / 3
    group("angular_derivative_and_composition_integrals", {
        "polar_gradient": polar_A - expected_A,
        "polar_curvature": polar_B - expected_B,
        "averaged_gradient": averaged_A - sp.Rational(8, 3) * (fp**2 + 2 * sf**2 / r**2),
        "averaged_curvature": averaged_B - sp.Rational(16, 3) * (sf**4 / r**4 + 2 * fp**2 * sf**2 / r**2),
        "composition_moment": sphere_average - expected_C,
    }, {}, {"polar_A": polar_A, "polar_B": polar_B, "composition_moment": sp.factor(sphere_average),
            "rotation_coefficients": "arot=2 sin(f)^2; brot=sin(2f)",
            "eta": "reference projection along the spatial radial axis; its angular square average is 1/3"})

    sinf = 2 * r**3 / (1 + r**6)
    cosf = (r**6 - 1) / (1 + r**6)
    derivative = -6 * r**2 / (1 + r**6)
    densities = {
        "A": sp.Rational(32, 3) * sp.pi * (r**2 * derivative**2 + 2 * sinf**2),
        "B": sp.Rational(64, 3) * sp.pi * (2 * derivative**2 * sinf**2 + sinf**4 / r**2),
        "C": 4 * sp.pi * r**2 * (4 * (1 + 7 * c**2) * sinf**4 / 15
                                  + (1 - c**2) * 4 * sinf**2 * cosf**2 / 3),
        "degree": -2 * derivative * sinf**2 / sp.pi,
    }
    denominator_powers = {"A": 2, "B": 4, "C": 4, "degree": 3}
    exact = {}
    beta_terms = {}
    for name, density in densities.items():
        power = denominator_powers[name]
        numerator = sp.Poly(sp.cancel(density * (1 + r**6)**power), r)
        integral = 0
        terms = []
        for (exponent,), coefficient in numerator.terms():
            arg = sp.Rational(exponent + 1, 6)
            if not 0 < arg < power:
                raise ValueError(f"nonconvergent beta term: {name}, {exponent}, {power}")
            term = coefficient * sp.gamma(arg) * sp.gamma(power - arg) / (6 * sp.gamma(power))
            integral += term
            terms.append((exponent, power, term))
        exact[name] = sp.simplify(sp.expand_func(sp.gammasimp(integral)))
        beta_terms[name] = terms
    expected = {"A": 704 * sp.pi**2 / 27, "B": 42560 * sp.pi**2 / 729,
                "C": 16 * sp.pi**2 * (3 + c**2) / 45, "degree": sp.Integer(1)}
    quadrature = {}
    predicates = {}
    with mp.workdps(50):
        for name in ("A", "B", "C"):
            integrand = sp.lambdify(r, densities[name], "mpmath")
            value = mp.quad(integrand, [0, 1, mp.inf])
            reference = mp.mpf(str(sp.N(exact[name], 60)))
            relative_error = abs(value - reference) / abs(reference)
            predicates[f"{name}_quadrature"] = mp.isfinite(value) and value > 0 and relative_error <= mp.mpf("1e-35")
            quadrature[name] = {"value": mp.nstr(value, 50), "relative_error": mp.nstr(relative_error, 12)}
    group("radial_beta_and_independent_quadrature", {name: sp.simplify(exact[name] - expected[name]) for name in exact},
          predicates, {"exact_integrals": exact, "beta_terms": beta_terms, "quadrature_50_digits": quadrature})

    s, ts, x, kap = sp.symbols("s t x kappa", real=True)
    M = s**2 - 2 * ts * s + ts
    F = s**2 * (2 - s)**2
    y = sp.factor(-sp.diff(F, s) / sp.diff(M, s))
    K = 2 * s**3 - 3 * (1 + ts) * s**2 + 6 * ts * s - 2 * ts
    energy = x * M + F / x + kap * x**3
    computed_kappa = sp.simplify(w * exact["C"] * gamma * exact["B"] / (exact["A"]**2 * (p + q)**2))
    expected_kappa = 2128 * (3 + sp.sqrt(5)) / 27225
    gap = sp.simplify(computed_kappa - sp.Rational(16, 75))
    residuals = {
        "positive_M_certificate": M - (s - ts)**2 - ts * (1 - ts),
        "stationary_s_elimination": y * sp.diff(M, s) + sp.diff(F, s),
        "stationary_x_elimination": M - F / y + 3 * ((F - M * y) / (3 * y**2)) * y,
        "upper_bound": F / (3 * y**2) - (s - ts)**2 / (12 * (s - 1)**2),
        "lower_branch_ratio_bound": ts - (ts - s) / (1 - s) - s * (1 - ts) / (1 - s),
        "upper_branch_ratio_bound": sp.Rational(8, 5) - (s - t) / (s - 1) - (3 * s - 4) / (5 * (s - 1)),
        "connection_curvature": 2 * y + sp.diff(F, s, 2) - 4 * K / (s - ts),
        "monotonic_K": sp.diff(K, s) - 6 * (s - 1) * (s - ts),
        "negative_endpoint": K.subs({s: sp.Rational(4, 3), ts: t}) + sp.Rational(8, 135),
        "computed_kappa": sp.simplify(computed_kappa - expected_kappa),
    }
    group("untruncated_trial_instability_criterion", residuals, {},
          {"kappa": computed_kappa, "threshold": sp.Rational(16, 75), "gap": gap,
           "remaining_stationary_interval": "1 < s < 4/3; K increasing to a negative endpoint",
           "scope": "all sizes and real constant connection amplitudes for this one fixed Hopf shape"})
    measurements = {"A": str(exact["A"]), "B": str(exact["B"]), "C": str(exact["C"]),
                    "degree": str(exact["degree"]), "kappa": str(computed_kappa),
                    "kappa_decimal": str(sp.N(computed_kappa, 30)), "threshold": "16/75",
                    "criterion_met": bool(gap > 0), "quadrature": quadrature}
    return checks, measurements


def run(note: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-relative-trial-v1", "checks": [], "measurements": {},
               "numerical_pass": False, "verdict": "INCONCLUSIVE", "failures": [], "identities": {},
               "environment": {"sympy": sp.__version__, "mpmath": mp.__version__}}
    try:
        section = frozen_section(note)
        section_sha = digest(section.encode("utf-8"))
        if section_sha != PROTOCOL_SHA:
            raise ValueError("frozen relative-trial section hash mismatch")
        receipt["identities"] = {
            "program": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                        "sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))},
            "protocol": {"path": note.relative_to(ROOT).as_posix(), "heading": HEADING.strip(), "sha256": section_sha}}
        with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(section)
        receipt["checks"], receipt["measurements"] = calculate()
        receipt["failures"] = [row["name"] for row in receipt["checks"] if not row["pass"]]
        if len(receipt["checks"]) != 4:
            receipt["failures"].append("frozen exact-group count mismatch")
        receipt["numerical_pass"] = not receipt["failures"]
        if receipt["numerical_pass"]:
            receipt["verdict"] = VERDICT if receipt["measurements"]["criterion_met"] else "INCONCLUSIVE—sufficient trial instability criterion is not met"
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["verdict"] == VERDICT else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=NOTE)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/20260906_matter_formation_relative_trial")
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
