#!/usr/bin/env python3
"""Qualify frozen scalar continuum binding identities and a fixed trial.

Run from the repository root:
    python computations/matter_formation_continuum_minimizer.py --output-dir runs/repro_continuum_minimizer_primary

The algebraic result does not certify compactness, orbital stability, or
physical matter formation. Those require the separate mathematical review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
SCHEMA = "matter-formation-continuum-minimizer-v1"
VERDICT = "SUPPORTS-conditional continuum binding identities"
FROZEN = {
    "angular": ("### 36.1 Exact angular variational equations", "b0ab6d5fbae00699bc82b1cb2b31c6494d9a342b0ed9a3b0cd93e80038834f11"),
    "compactness": ("### 36.2 Continuum compactness and evolution obligations", "fef2d801ece9ac5511bddbdad4c2516487ba996552163e5c90696e1799819b61"),
    "trial": ("### 36.3 Explicit continuum binding trial", "a6ef6b749a7fddd5c4fe95c963c944bb3199587fa0ee6d3115104da6775cb551"),
    "protocol": ("### 36.4 Continuum qualification: pre-execution criteria", "170f95ab96f71659a41e6b65124ccc2bf784a22282ff3efda73b39fb9edc574d"),
    "parent": ("### 25.1 Exact carrier-free periodic background", "dce41f8119dd782a4d5593d93ad96a03fad6558bcd3711b8e729803e73e72e6a"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section(text: str, heading: str) -> bytes:
    matches = list(re.finditer(r"^" + re.escape(heading) + r"$", text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one frozen heading: {heading}")
    result = text[matches[0].start():]
    level = len(heading) - len(heading.lstrip("#"))
    end = re.search(r"\n#{1," + str(level) + r"} ", result)
    if end is not None:
        result = result[:end.start()]
    return (result.rstrip() + "\n").encode("utf-8")


def scientific_calculation() -> dict:
    checks: list[dict] = []

    def identity(name: str, actual: sp.Expr, expected: sp.Expr) -> None:
        residual = sp.factor(sp.together(actual - expected))
        if residual != 0:
            residual = sp.simplify(residual)
        checks.append({"name": name, "passed": bool(residual == 0),
                       "actual": str(actual), "expected": str(expected),
                       "residual": str(residual)})

    a, k, ur, uc, B, h = sp.symbols("a k u_rho u_C B h", positive=True)
    f, x, y = sp.symbols("f x y", real=True)
    n = x*x + y*y
    potential = ur*(f*f-1)**2/4 + (B-h+h*f*f)*n + uc*n*n/2
    coordinates = sp.Matrix([f, x, y])
    gradient = sp.Matrix([sp.diff(potential, coordinate) for coordinate in coordinates])
    hessian = sp.hessian(potential, coordinates)
    expected_hessian = sp.Matrix([
        [ur*(3*f*f-1)+2*h*n, 4*h*f*x, 4*h*f*y],
        [4*h*f*x, 2*(B-h+h*f*f+uc*(3*x*x+y*y)), 4*uc*x*y],
        [4*h*f*y, 4*uc*x*y, 2*(B-h+h*f*f+uc*(x*x+3*y*y))],
    ])
    for row in range(3):
        for column in range(row, 3):
            identity(f"angular_hessian_{row}_{column}", hessian[row, column], expected_hessian[row, column])
    u, v, w, cpsi = sp.symbols("u v w c_psi", real=True)
    variation = sp.Matrix([u, v, w])
    acceleration = -sp.diag(1/cpsi, 1/(2*a), 1/(2*a))*hessian*variation
    expected_acceleration = sp.Matrix([
        -((ur*(3*f*f-1)+2*h*n)*u+4*h*f*(x*v+y*w))/cpsi,
        -((B-h+h*f*f+uc*(3*x*x+y*y))*v+2*uc*x*y*w+2*h*f*x*u)/a,
        -((B-h+h*f*f+uc*(x*x+3*y*y))*w+2*uc*x*y*v+2*h*f*y*u)/a,
    ])
    for row in range(3):
        identity(f"angular_mass_normalization_{row}", acceleration[row], expected_acceleration[row])
    phase = hessian*sp.Matrix([0, -y, x])
    for row, expected in enumerate((0, -gradient[2], gradient[1])):
        identity(f"constant_phase_variation_{row}", phase[row], expected)

    r = sp.symbols("r", positive=True)
    g = sp.Function("g")(r)
    derivative = sp.diff(g, r)
    laplace_zero = sp.diff(g, r, 2) + 2*derivative/r
    laplace_one_derivative = sp.diff(derivative, r, 2) + 2*sp.diff(derivative, r)/r - 2*derivative/r**2
    identity("translation_angular_identity", laplace_one_derivative, sp.diff(laplace_zero, r))

    p, q, omega = sp.symbols("p q Omega", real=True)
    density = -2*a*(x*q-y*p)
    rotated_square = a*((p-omega*y)**2+(q+omega*x)**2)
    identity("temporal_charge_square", rotated_square, a*(p*p+q*q)+a*omega*omega*n-omega*density)
    K, Q, N = sp.symbols("K Q N", positive=True)
    total_square = K+a*omega**2*N-omega*Q
    identity("fixed_charge_velocity_projection", total_square.subs(omega, Q/(2*a*N)), K-Q**2/(4*a*N))

    G, P, s, lam = sp.symbols("G P s lambda", positive=True)
    energy = G+P+Q**2/(4*a*N)
    scaled = s**sp.Rational(1, 3)*G+s*P+(s*Q)**2/(4*a*s*N)
    identity("charge_and_space_dilation", scaled, s*energy-(s-s**sp.Rational(1, 3))*G)
    fixed_charge_dilation = lam*G+lam**3*P+Q**2/(4*a*lam**3*N)
    virial = sp.diff(fixed_charge_dilation, lam).subs(lam, 1)
    identity("fixed_charge_virial", virial, G+3*P-3*Q**2/(4*a*N))
    virial_potential = Q**2/(4*a*N)-G/3
    identity("energy_frequency_virial", energy.subs(P, virial_potential), Q**2/(2*a*N)+2*G/3)
    omega0, surplus = sp.symbols("Omega_0 surplus", positive=True)
    identity("frequency_lower_bound_identity", (G/3+P)/(a*N)-omega0**2,
             (G/3+P-a*omega0**2*N)/(a*N))

    delta, n0, R, t = sp.symbols("delta n_0 R t", positive=True)

    def V(mediator: sp.Expr, carrier: sp.Expr) -> sp.Expr:
        return ur*(mediator**2-1)**2/4+(B-h+h*mediator**2)*carrier**2+uc*carrier**4/2

    interface_carrier = sp.sqrt(n0)*(1-t)
    interface_measure = delta*(1+delta*t)**2
    Nstar = 4*sp.pi*n0*(sp.Rational(1, 3)+delta*(sp.Rational(1, 3)+delta/6+delta**2/30))
    Gstar = 2*sp.pi*(1+k*n0)/delta*(1+delta+delta**2/3)
    Pstar = sp.expand(4*sp.pi*(V(0, sp.sqrt(n0))/3 + sp.integrate(sp.expand(interface_measure*V(t, interface_carrier)), (t, 0, 1))))
    direct_Nstar = 4*sp.pi*(n0/3+sp.integrate(sp.expand(interface_measure*interface_carrier**2), (t, 0, 1)))
    direct_Gstar = 2*sp.pi*sp.integrate((1+delta*t)**2*(1+k*sp.diff(interface_carrier, t)**2)/delta, (t, 0, 1))
    identity("trial_population_integral", direct_Nstar, Nstar)
    identity("trial_gradient_integral", direct_Gstar, Gstar)
    radial_interface = (r/R-1)/delta
    radial_potential = V(radial_interface, sp.sqrt(n0)*(1-radial_interface))
    direct_P = 4*sp.pi*(V(0, sp.sqrt(n0))*R**3/3 + sp.integrate(sp.expand(r*r*radial_potential), (r, R, R*(1+delta))))
    identity("trial_potential_radial_measure", direct_P, Pstar*R**3)

    G0, P0, N0 = sp.symbols("G_star P_star N_star", positive=True)
    RQ = (Q/(2*sp.sqrt(a*P0*N0)))**sp.Rational(1, 3)
    trial_energy = G0*R+P0*R**3+Q**2/(4*a*N0*R**3)
    omega_trial = sp.sqrt(P0/(a*N0))
    Astar = G0/(2*sp.sqrt(a*P0*N0))**sp.Rational(1, 3)
    identity("trial_volume_kinetic_balance", (P0*R**3-Q**2/(4*a*N0*R**3)).subs(R, RQ), 0)
    identity("trial_energy_per_charge", sp.powdenest(trial_energy.subs(R, RQ)/Q, force=True), omega_trial+Astar*Q**sp.Rational(-2, 3))
    omega_ext, omega_trial_symbol, A = sp.symbols("Omega_ext Omega_trial A", positive=True)
    gap = sp.symbols("gap", positive=True)
    threshold = (A/gap)**sp.Rational(3, 2)
    identity("sufficient_charge_threshold", A*threshold**sp.Rational(-2, 3), gap)

    coefficients = {a: sp.Rational(1, 16), k: 1, ur: 4, uc: 1,
                    B: sp.Rational(19, 4), h: sp.Rational("2.9598260763447164"),
                    delta: sp.Rational(1, 4), n0: sp.sqrt(2)}
    Ns, Gs, Ps = [sp.simplify(expression.subs(coefficients)) for expression in (Nstar, Gstar, Pstar)]
    av = coefficients[a]
    exterior = sp.sqrt(coefficients[B]/av)
    trial_frequency = sp.sqrt(Ps/(av*Ns))
    scale_cost = Gs/(2*sp.sqrt(av*Ps*Ns))**sp.Rational(1, 3)
    frequency_gap = exterior-trial_frequency
    frequency_binds = bool(sp.N(frequency_gap, 80) > 0)
    charge_threshold = (scale_cost/frequency_gap)**sp.Rational(3, 2) if frequency_binds else None
    radius256 = (sp.Integer(256)/(2*sp.sqrt(av*Ps*Ns)))**sp.Rational(1, 3)
    energy_per_charge = trial_frequency+scale_cost*sp.Integer(256)**sp.Rational(-2, 3)
    expressions = {"N_star": Ns, "G_star": Gs, "P_star": Ps,
                   "omega_trial": trial_frequency, "A_star": scale_cost,
                   "Q_trial": charge_threshold, "R_256": radius256,
                   "energy_per_charge_256": energy_per_charge}
    precise = {key: str(sp.N(value, 80)) if value is not None else None for key, value in expressions.items()}
    numbers = {key: float(value) if value is not None else None for key, value in precise.items()}
    if not all(value is None or math.isfinite(value) for value in numbers.values()):
        raise FloatingPointError("Nonfinite primary continuum quantity")

    uncoupled_coefficients = dict(coefficients)
    uncoupled_coefficients[h] = 0
    uncoupled_ratio = sp.simplify(Pstar.subs(uncoupled_coefficients)/Ns)
    uncoupled_margin = uncoupled_ratio-coefficients[B]
    uncoupled_pass = bool(sp.N(uncoupled_margin, 80) >= 0)
    checks.append({"name": "disabled_coupling_no_binding", "passed": uncoupled_pass,
                   "actual": str(uncoupled_margin), "expected": "nonnegative"})
    passed = all(row["passed"] for row in checks)
    return {
        "checks": checks, "numbers": numbers, "precise": precise,
        "expressions": {key: str(value) if value is not None else None for key, value in expressions.items()},
        "omega_infty": float(sp.N(exterior, 80)),
        "trial_frequency_binds": frequency_binds,
        "trial_q256_bound": bool(sp.N(exterior-energy_per_charge, 80) > 0),
        "disabled_coupling": {"potential_per_population": float(sp.N(uncoupled_ratio, 80)),
                              "exterior_mass_coefficient": float(coefficients[B]),
                              "trial_binds": False if uncoupled_pass else None},
        "passed": passed,
    }


def run(output: Path, record: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": SCHEMA, "passed": False, "verdict": "INCONCLUSIVE",
        "numbers": {}, "precise": {}, "expressions": {}, "checks": [],
        "hashes": {}, "artifacts": {}, "trial_q256_bound": False,
        "omega_infty": None, "disabled_coupling": {}, "error": None,
        "complete_physical_matter_formation": False,
        "environment": {"python": platform.python_version(), "sympy": sp.__version__},
    }

    def retain(name: str, data: bytes) -> None:
        with (output/name).open("xb") as stream:
            stream.write(data)
        receipt["artifacts"][name] = sha256(data)

    try:
        retain("program_source.py", Path(__file__).read_bytes())
        text = record.read_text(encoding="utf-8").replace("\r\n", "\n")
        for name, (heading, expected) in FROZEN.items():
            frozen = section(text, heading)
            retain(f"{name}.txt", frozen)
            receipt["hashes"][name] = sha256(frozen)
            if receipt["hashes"][name] != expected:
                raise ValueError(f"Frozen {name} section hash mismatch")
        result = scientific_calculation()
        receipt.update(result)
        if receipt["passed"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["passed"] = False
        receipt["verdict"] = "INCONCLUSIVE"
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        with (output/"results.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"passed": receipt["passed"], "verdict": receipt["verdict"],
                      "check_count": len(receipt["checks"]), "numbers": receipt["numbers"],
                      "trial_q256_bound": receipt["trial_q256_bound"],
                      "error": receipt["error"]}, allow_nan=False))
    return 0 if receipt["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=NOTE)
    args = parser.parse_args()
    return run(args.output_dir.resolve(), args.record.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
