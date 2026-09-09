#!/usr/bin/env python3
"""Verify the fixed analytical strain-departure comparison.

Run from CassiTheory: python computations/verify_navier_stokes_strain_departure.py
Use --output with a fresh path. No Navier–Stokes trajectory is computed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import mpmath as mp
import numpy as np
import sympy as sp
from numpy.polynomial.hermite import hermgauss
from numpy.polynomial.laguerre import laggauss
from numpy.polynomial.legendre import leggauss

import verify_navier_stokes_depletion as depletion
import verify_navier_stokes_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-strain-departure-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_strain_departure/verification.json"
TOLERANCE = 1e-10


def gaussian_integral(polynomial, variables, rate):
    """Integrate a polynomial times exp(-rate |x|^2) exactly on R^3."""
    total = sp.Integer(0)
    for powers, coefficient in sp.Poly(sp.expand(polynomial), *variables).terms():
        if any(power % 2 for power in powers):
            continue
        moment = coefficient
        for power in powers:
            half = power // 2
            moment *= (sp.sqrt(sp.pi) * sp.factorial2(2 * half - 1)
                       / (2**half * rate**(sp.Rational(1, 2) + half)))
        total += moment
    return sp.simplify(total)


def exact_gaussian(book):
    x, y, z = variables = sp.symbols("x y z", real=True)
    velocity = sp.Matrix([x*(1-2*z*z), y*(1-2*z*z), 2*z*(x*x+y*y-1)])

    def derivative(poly, coordinate):
        return sp.diff(poly, coordinate) - 2*coordinate*poly

    gradient = sp.Matrix(3, 3, lambda i, j: derivative(velocity[i], variables[j]))
    strain = (gradient + gradient.T) / 2
    omega = sp.Matrix([gradient[2, 1]-gradient[1, 2],
                       gradient[0, 2]-gradient[2, 0],
                       gradient[1, 0]-gradient[0, 1]])
    integrate = lambda poly, rate: gaussian_integral(poly, variables, sp.Integer(rate))
    book.exact("Gaussian divergence", sp.trace(gradient), 0)
    book.exact("Gaussian azimuthal velocity", x*velocity[1]-y*velocity[0], 0)
    values = {
        "K": integrate(velocity.dot(velocity)/2, 2),
        "E": integrate(sum(entry**2 for entry in strain), 2),
        "G": integrate(sum(derivative(entry, coordinate)**2
                           for entry in strain for coordinate in variables), 2),
        "I": integrate(-strain.det(), 3),
    }
    book.exact("Gaussian enstrophy from independent curl",
               values["E"], integrate(omega.dot(omega)/2, 2))
    book.exact("Gaussian gradient from independent curl",
               values["G"], integrate(sum(derivative(entry, coordinate)**2
                                         for entry in omega for coordinate in variables)/2, 2))
    book.exact("Miller determinant integral", values["I"],
               8*sp.pi**sp.Rational(3, 2)/(81*sp.sqrt(3)))
    for name, value in values.items():
        book.check(f"Gaussian {name} positive", value > 0, value)
    return values


def cylindrical_integrals(order):
    """Independent cylindrical formulas, including rotation of the theta basis."""
    radial_nodes, radial_weights = laggauss(order)
    axial_nodes, axial_weights = hermgauss(order)
    weights = radial_weights[:, None] * axial_weights[None, :]
    result = {}
    for rate in (2, 3):
        r2 = radial_nodes[:, None]/rate
        z = axial_nodes[None, :]/math.sqrt(rate)
        r = np.sqrt(r2)
        ur = r*(1-2*z*z)
        uz = 2*z*(r2-1)
        srr = (1-2*z*z)*(1-2*r2)
        stt = 1-2*z*z
        szz = 2*(r2-1)*(1-2*z*z)
        srz = r*z*(1+2*z*z-2*r2)
        curl_factor = -14+4*r2+4*z*z
        omega = r*z*curl_factor
        omega_r = z*((1-2*r2)*curl_factor+8*r2)
        omega_z = r*((1-2*z*z)*curl_factor+8*z*z)
        omega_over_r = z*curl_factor
        polynomials = ({"K": (ur*ur+uz*uz)/2, "E": omega*omega/2,
                        "G": (omega_r**2+omega_z**2+omega_over_r**2)/2}
                       if rate == 2 else {"I": -stt*(srr*szz-srz*srz)})
        for name, polynomial in polynomials.items():
            result[name] = float(math.pi/(rate*math.sqrt(rate)) * np.sum(weights*polynomial))
    return result


def algebra(book):
    m2, mr, r2 = sp.symbols("m2 mr r2", real=True)
    book.exact("Projected remainder completion of squares",
               6*(m2+mr+r2/4)-sp.Rational(3, 2)*r2, 6*(m2+mr))
    nu, lap_dot, square_dot = sp.symbols("nu lap_dot square_dot", real=True)
    book.exact("Variational derivative of f",
               6*nu*lap_dot-4*square_dot, -6*(-nu*lap_dot+sp.Rational(2, 3)*square_dot))
    a, b, c, d, e, h, j, k, l, n, eps = sp.symbols("a b c d e h j k l n eps", real=True)
    strain = sp.Matrix([[a, b, c], [b, d, e], [c, e, -a-d]])
    direction = sp.Matrix([[h, j, k], [j, l, n], [k, n, -h-l]])
    book.exact("Trace-free determinant variation",
               sp.diff(sp.trace((strain+eps*direction)**3), eps).subs(eps, 0),
               3*sp.trace(strain**2*direction))
    K, E, G, f, f0 = sp.symbols("K E G f f0", positive=True)
    invariant = K*E**2+f0*K**2/(2*nu)
    derivative = sp.diff(invariant, K)*(-2*nu*E)+sp.diff(invariant, E)*(f+nu*G)
    book.exact("Coupled comparison monotonicity identity", derivative,
               2*K*E*(f-f0)+2*nu*E*(K*G-E**2))
    t, s = sp.symbols("t s", real=True)
    K0, E0 = sp.symbols("K0 E0", positive=True)
    defect, gradient = sp.Function("delta"), sp.Function("G")
    kinetic = (K0-2*nu*E0*t-nu*f0*t*t
               +sp.Rational(3, 2)*nu*sp.Integral((t-s)**2*defect(s), (s, 0, t))
               -2*nu**2*sp.Integral((t-s)*gradient(s), (s, 0, t)))
    book.exact("Cumulative defect third derivative", sp.diff(kinetic, t, 3),
               3*nu*defect(t)-2*nu**2*sp.diff(gradient(t), t))
    for degree, expected in ((0, K0), (1, -2*nu*E0),
                             (2, -2*nu*f0-2*nu**2*gradient(0))):
        book.exact(f"Cumulative defect initial derivative {degree}",
                   sp.diff(kinetic, t, degree).subs(t, 0).doit(), expected)
    x = sp.symbols("x", nonnegative=True)
    book.exact("Zero-chi comparison limit", sp.integrate(sp.sqrt(x), (x, 0, 1)), sp.Rational(2, 3))
    Tstar = K0/(nu*(E0+sp.sqrt(E0**2+f0*K0/nu)))
    book.exact("General-viscosity Miller deadline", 2*nu*E0*Tstar+nu*f0*Tstar**2, K0)
    for scale in (sp.Rational(1, 2), sp.Integer(1), sp.Integer(2)):
        book.exact(f"NS scaling chi lambda={scale}",
                   (scale**3*f0)*(K0/scale)/(2*nu*(scale*E0)**2), f0*K0/(2*nu*E0**2))
        book.exact(f"NS scaling deadline lambda={scale}",
                   Tstar.subs({K0: K0/scale, E0: scale*E0, f0: scale**3*f0}, simultaneous=True),
                   Tstar/scale**2)


def deadline_integral(chi, order):
    nodes, weights = leggauss(order)
    s = (nodes+1)/2
    return float(np.sum(weights*s*s/np.sqrt(1+chi*(1-s**4))))


def compute(result):
    book = depletion.DepletionReceipt()
    result["checks"] = book.checks
    result["failures"] = book.failures
    errors = []

    def compare(name, actual, expected):
        discrepancy = abs(actual-expected)/(1+abs(actual)+abs(expected))
        errors.append(discrepancy)
        book.check(name, math.isfinite(discrepancy) and discrepancy < TOLERANCE,
                   {"actual": actual, "expected": expected, "discrepancy": discrepancy})
        return discrepancy

    algebra(book)
    exact = exact_gaussian(book)
    result["gaussian_exact"] = {name: str(value) for name, value in exact.items()}
    result["gaussian_quadrature"] = []
    for order in (12, 20):
        values = cylindrical_integrals(order)
        row = {"order": order, "values": values, "errors": {}}
        result["gaussian_quadrature"].append(row)
        for name, value in values.items():
            row["errors"][name] = compare(f"Cylindrical {name} order={order}", value, float(exact[name]))

    result["deadline_rows"] = []
    def qualify_deadline(label, chi):
        with mp.workdps(50):
            high_chi = mp.mpf(str(chi))
            reference = mp.quad(lambda x: mp.sqrt(x/(1+high_chi*(1-x*x))), [0, 1])
            reference_text = mp.nstr(reference, 50)
        values = {str(order): deadline_integral(float(chi), order) for order in (64, 128)}
        row = {"label": label, "chi": float(chi), "integral_high_precision": reference_text,
               "integrals": values, "errors": {}}
        result["deadline_rows"].append(row)
        for order, value in values.items():
            row["errors"][order] = compare(f"Deadline {label} order={order}", value, float(reference))
        ratio = values["128"]*(math.sqrt(1+2*float(chi))+1)/2
        row["Tcmp_over_Tstar"] = ratio
        book.check(f"Earlier deadline {label}", math.isfinite(ratio) and 0 < ratio < 1, ratio)
        return values["128"], ratio

    for chi in (sp.Rational(1, 16), sp.Rational(1, 4), sp.Integer(1), sp.Integer(4), sp.Integer(16)):
        qualify_deadline(f"chi={chi}", float(chi))
    result["amplitude_rows"] = []
    for nu in (sp.Rational(1, 100), sp.Integer(1)):
        critical_amplitude = 3*nu*exact["G"]/(4*exact["I"])
        for multiplier in (2, 4):
            amplitude = multiplier*critical_amplitude
            K0, E0, G0 = (sp.simplify(amplitude**2*exact[name]) for name in ("K", "E", "G"))
            f0 = sp.simplify(-3*nu*G0+4*amplitude**3*exact["I"])
            chi = sp.simplify(f0*K0/(2*nu*E0**2))
            label = f"nu={nu},amplitude_multiple={multiplier}"
            book.check(f"Positive f0 {label}", f0 > 0, f0)
            integral, ratio = qualify_deadline(label, float(chi))
            Kf, Ef, nuf, ff = map(float, (K0, E0, nu, f0))
            Tstar = Kf/(nuf*(Ef+math.sqrt(Ef*Ef+ff*Kf/nuf)))
            Tcmp = Kf*integral/(2*nuf*Ef)
            row = {"nu": nuf, "amplitude_multiple": multiplier, "amplitude": float(amplitude),
                   "K0": Kf, "E0": Ef, "G0": float(G0), "f0": ff, "chi": float(chi),
                   "Tstar": Tstar, "Tcmp": Tcmp, "Tcmp_over_Tstar": ratio,
                   "initial_perturbative_condition": "NOT_EVALUATED"}
            result["amplitude_rows"].append(row)
            compare(f"Deadline ratio reconstruction {label}", Tcmp/Tstar, ratio)
    for multiplier in (2, 4):
        low, high = [row for row in result["amplitude_rows"] if row["amplitude_multiple"] == multiplier]
        compare(f"Viscosity-rescaled amplitude deadline m={multiplier}", low["Tcmp"]*(low["nu"]/high["nu"]), high["Tcmp"])
    book.check("Nonempty finite numerical schedule", bool(errors) and all(math.isfinite(v) for v in errors))
    result.update(status="PASS" if not book.failures else "FAIL", check_count=len(book.checks),
                  max_numerical_discrepancy=max(errors) if errors else None,
                  scope={"NS_trajectory": "NOT_RUN", "arbitrary_data_regularity": "UNRESOLVED",
                         "critical_work_control": "UNRESOLVED",
                         "continuum_comparison": "Analytical proof required; numerical rows qualify calculations only"})
    return not book.failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = {"protocol": PROTOCOL, "script": Path(__file__).resolve(),
               "depletion": Path(depletion.__file__).resolve(), "transfer": Path(transfer.__file__).resolve()}
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(payloads[key]).hexdigest()}
                  for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir/path.name).write_bytes(payloads[key])
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "identities": identities,
                "numpy_version": np.__version__, "sympy_version": sp.__version__, "mpmath_version": mp.__version__}
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    result = {"schema": "cassi.navier-stokes.strain-departure.verification.v1", **manifest}
    success = False
    try:
        success = compute(result)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    depletion.json_safe(result)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in ("status", "check_count", "max_numerical_discrepancy", "error")}, indent=2))
    if success and result.get("status") == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
