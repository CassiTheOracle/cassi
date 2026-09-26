#!/usr/bin/env python3
"""Verify fixed critical-remainder identities and instantaneous NS controls.

Run from CassiTheory with --output pointing to a fresh receipt.
No Navier-Stokes trajectory is integrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sympy as sp

import verify_navier_stokes_depletion as depletion
import verify_navier_stokes_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-critical-recurrence-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_critical_recurrence/verification.json"
TOLERANCE = 1e-10
AMPLITUDES = (-4, -1, 1, 4)
VISCOSITIES = (sp.Rational(1, 100), sp.Integer(1))
GRIDS = (24, 32)
ZERO_MODE = (0, 0, 0)


def field_sum(*fields):
    result = {}
    for field in fields:
        for k, value in field.items():
            result[k] = result.get(k, sp.zeros(*value.shape)) + value
    return {k: sp.simplify(value) for k, value in result.items()
            if value != sp.zeros(*value.shape)}


def scale(field, factor):
    return {k: factor * value for k, value in field.items()}


def lap(field, power=1):
    return {k: transfer.mode_norm_sq(k)**power * value for k, value in field.items()}


def inner(left, right, power=0):
    total = 0
    for k in left.keys() & right.keys():
        if k == ZERO_MODE and power < 0:
            continue
        total += transfer.mode_norm(k)**power * sum(
            sp.conjugate(x)*y for x, y in zip(left[k], right[k]))
    return transfer.real_part(total)


def bilinear(left, right):
    result = {}
    for p, up in left.items():
        for q, uq in right.items():
            k = tuple(p[j]+q[j] for j in range(3))
            term = transfer.projected_convection(k, p, q, up, uq)
            result[k] = result.get(k, sp.zeros(3, 1)) + term
    return {k: sp.simplify(value) for k, value in result.items() if value != sp.zeros(3, 1)}


def strain(field):
    return {k: sp.I*(sp.Matrix(k)*value.T + value*sp.Matrix(k).T)/2
            for k, value in field.items() if k != ZERO_MODE}


def strain_project(field):
    result = {}
    for k, value in field.items():
        if k == ZERO_MODE:
            continue
        kk = sp.Matrix(k)
        v = transfer.leray_projector(k)*value*kk
        result[k] = sp.simplify((kk*v.T+v*kk.T)/transfer.mode_norm_sq(k))
    return result


def tensor_square(field):
    result = {}
    for p, value in field.items():
        for q, other in field.items():
            k = tuple(p[j]+q[j] for j in range(3))
            result[k] = result.get(k, sp.zeros(3, 3)) + value*other
    return {k: sp.simplify(value) for k, value in result.items() if value != sp.zeros(3, 3)}


def fixtures():
    cyclic = {}
    for k, component in (((0, 1, 0), 0), ((0, 0, 1), 1), ((1, 0, 0), 2)):
        coefficient = sp.zeros(3, 1)
        coefficient[component] = 1/(2*sp.I)
        transfer.add_real_mode(cyclic, k, coefficient)
    return {"cyclic": cyclic, "three_coordinate": transfer.three_dimensional_fixture(),
            "planar": transfer.planar_fixture()}


def exact_fixture(field, book, name):
    a, nu = sp.symbols("a nu", real=True)
    B = transfer.full_leray_B(field)
    L = lap(field)
    DB = field_sum(bilinear(field, B), bilinear(B, field))
    DL_LB = field_sum(bilinear(field, L), bilinear(L, field), lap(B))
    S, SB = strain(field), strain(B)
    Q = strain_project(tensor_square(S))
    R = field_sum(scale(SB, -1), scale(Q, -sp.Rational(2, 3)))
    LS = lap(S)
    moments = {p: inner(field, field, p) for p in (0, 1, 2, 3, 4, 5, 6)}
    first = {p: sp.factor(2*a**3*inner(field, B, p)-2*nu*a**2*moments[p+2])
             for p in (0, 1, 2, 4)}
    second = {p: sp.factor(2*a**4*(inner(B, B, p)+inner(field, DB, p))
                  -2*nu*a**3*(2*inner(B, L, p)+inner(field, DL_LB, p))
                  +4*nu**2*a**2*moments[p+4]) for p in (0, 1, 2)}
    K, E, G, C, Y = [a*a*moments[p]/div for p, div in ((0, 2), (2, 2), (4, 2), (1, 1), (3, 1))]
    A, F = a**3*inner(field, B, 2), a**3*inner(field, B, 1)
    f, fdot = sp.factor(A-3*nu*G), sp.factor((second[2]-nu*first[4])/2)
    M = field_sum(scale(LS, nu*a), scale(Q, 2*a*a/3))
    Ra = scale(R, a*a)
    D = field_sum(M, scale(Ra, sp.Rational(1, 2)))
    rnorm = inner(Ra, Ra)
    delta = sp.factor(rnorm-4*inner(D, D))
    W = sp.factor(a**3*inner(S, R, -1))
    J = sp.factor(a**3*inner(S, Q, -1))
    V = sp.factor(K*E-C*C/4)
    Vdot = sp.factor(first[0]*E/2+K*first[2]/2-C*first[1]/2)
    Vddot = sp.factor(second[0]*E/2+first[0]*first[2]/2+K*second[2]/2
                     -(first[1]**2+C*second[1])/2)
    book.exact(name+" energy nonlinear cancellation", inner(field, B), 0)
    book.exact(name+" remainder enstrophy orthogonality", inner(S, R), 0)
    book.exact(name+" strain projection norm", inner(S, S), moments[2]/2)
    book.exact(name+" kinetic budget", first[0]/2, -2*nu*E)
    book.exact(name+" strain budget", first[2]/2, f+nu*G)
    book.exact(name+" critical budget", first[1], 2*F-2*nu*Y)
    book.exact(name+" full M and R critical contributions", 2*F, -8*J/3-4*W)
    book.exact(name+" differentiated f squared remainder identity", fdot, -3*delta/2)
    book.exact(name+" variance production budget", Vdot+nu*(2*K*G+2*E*E-C*Y), K*A-C*F)
    return {key: sp.factor(value) for key, value in dict(
        K=K, E=E, G=G, C=C, Y=Y, A=A, F=F, f=f, fdot=fdot,
        delta=delta, rnorm=rnorm, W=W, V=V, Vdot=Vdot, Cdot=first[1],
        centered_slack=V*rnorm/E-W*W, Vddot=Vddot).items()}, (a, nu)


def fft_quantities(field, n, a, nu):
    shape = (n, n, n)
    frequencies = np.fft.fftfreq(n, d=1/n)
    k = np.stack(np.meshgrid(frequencies, frequencies, frequencies, indexing="ij"), axis=-1)
    r2 = np.sum(k*k, axis=-1)
    r = np.sqrt(r2)
    inverse_r2 = np.divide(1.0, r2, out=np.zeros(shape), where=r2 > 0)
    inverse_r = np.divide(1.0, r, out=np.zeros(shape), where=r > 0)
    axes = (0, 1, 2)
    def fft(value):
        return np.fft.fftn(value, axes=axes)
    def physical(value):
        return np.fft.ifftn(value, axes=axes).real
    def project_vector(value):
        return value-k*inverse_r2[..., None]*np.sum(k*value, axis=-1)[..., None]
    def gradient(value):
        return physical(1j*k[..., :, None]*fft(value)[..., None, :])
    def positive_lap(value):
        return physical(r2[..., None]*fft(value))
    def symgrad(value):
        grad = gradient(value)
        return (grad+np.swapaxes(grad, -1, -2))/2
    def project_tensor(value):
        valuehat = fft(value)
        v = project_vector(np.einsum("...ij,...j->...i", valuehat, k))
        return physical((k[..., :, None]*v[..., None, :]+v[..., :, None]*k[..., None, :])
                        *inverse_r2[..., None, None])
    def convection(left, right):
        return physical(project_vector(fft(-np.einsum("...j,...ji->...i", left, gradient(right)))))
    uhat = np.zeros(shape+(3,), dtype=complex)
    for wave, coefficient in field.items():
        uhat[tuple(component % n for component in wave)] = a*np.array(coefficient, dtype=complex).ravel()*n**3
    u = physical(uhat)
    B = convection(u, u)
    ut = B-nu*positive_lap(u)
    utt = convection(ut, u)+convection(u, ut)-nu*positive_lap(ut)
    U, T, TT, BH = (fft(value)/n**3 for value in (u, ut, utt, B))
    weight = np.sum(np.abs(U)**2, axis=-1)
    m = {p: float(np.sum(r**p*weight)) for p in (0, 1, 2, 3, 4)}
    dm = {p: float(2*np.real(np.sum(r[..., None]**p*np.conjugate(U)*T))) for p in (0, 1, 2, 4)}
    d2m = {p: float(2*np.sum(r[..., None]**p*(np.abs(T)**2+np.real(np.conjugate(U)*TT)))) for p in (0, 1, 2)}
    K, E, G, C, Y = m[0]/2, m[2]/2, m[4]/2, m[1], m[3]
    A = float(np.real(np.sum(r2[..., None]*np.conjugate(U)*BH)))
    F = float(np.real(np.sum(r[..., None]*np.conjugate(U)*BH)))
    grad, S = gradient(u), symgrad(u)
    omega = np.stack((grad[..., 1, 2]-grad[..., 2, 1],
                      grad[..., 2, 0]-grad[..., 0, 2],
                      grad[..., 0, 1]-grad[..., 1, 0]), axis=-1)
    Shat = fft(S)
    advS = np.zeros_like(S)
    for j in range(3):
        advS += u[..., j, None, None]*physical(1j*k[..., j, None, None]*Shat)
    Ssquare = np.matmul(S, S)
    R = project_tensor(advS+Ssquare/3+omega[..., :, None]*omega[..., None, :]/4)
    M = nu*physical(r2[..., None, None]*Shat)+2*project_tensor(Ssquare)/3
    rnorm = float(np.mean(np.sum(R*R, axis=(-1, -2))))
    D = M+R/2
    delta = rnorm-4*float(np.mean(np.sum(D*D, axis=(-1, -2))))
    inverseS = physical(inverse_r[..., None, None]*Shat)
    W = float(np.mean(np.sum(inverseS*R, axis=(-1, -2))))
    centered = inverseS-C*S/(2*E)
    centered_norm = float(np.mean(np.sum(centered*centered, axis=(-1, -2))))
    V = E*centered_norm
    Vdot = dm[0]*E/2+K*dm[2]/2-C*dm[1]/2
    Vddot = d2m[0]*E/2+dm[0]*dm[2]/2+K*d2m[2]/2-(dm[1]**2+C*d2m[1])/2
    return dict(K=K, E=E, G=G, C=C, Y=Y, A=A, F=F, f=A-3*nu*G,
                fdot=(d2m[2]-nu*dm[4])/2, delta=delta, rnorm=rnorm, W=W,
                V=V, Vdot=Vdot, Cdot=dm[1], centered_slack=centered_norm*rnorm-W*W,
                Vddot=Vddot)


def algebra(book):
    K, E, C, a = sp.symbols("K E C a", positive=True)
    polynomial = K-a*C+a*a*E
    center = C/(2*E)
    book.exact("centering minimizer", sp.diff(polynomial, a).subs(a, center), 0)
    book.exact("centering residual", polynomial.subs(a, center), K-C*C/(4*E))
    book.exact("centering convexity", sp.diff(polynomial, a, 2), 2*E)
    r, s, x, y = sp.symbols("r s x y", positive=True)
    m = {p: x*r**p+y*s**p for p in range(5)}
    V = (m[0]*m[2]-m[1]**2)/4
    heat = (m[0]*m[4]+m[2]**2)/2-m[1]*m[3]
    book.exact("positive two-frequency variance", V, x*y*(r-s)**2/4)
    book.exact("positive heat variance dissipation", heat, x*y*(r-s)**2*(r*r+s*s)/2)
    exponents = dict(K=-1, E=1, G=3, C=0, Y=2, V=0, W=2, rnorm=5)
    book.check("centered estimate critical scaling", 2*exponents["W"] == exponents["V"]-exponents["E"]+exponents["rnorm"], exponents)


def scalar_control(book):
    tau = sp.symbols("tau", positive=True)
    dt = lambda value: -sp.diff(value, tau)
    K, E, G = 8*tau**sp.Rational(1, 4), tau**(-sp.Rational(3, 4)), sp.Rational(3, 2)*tau**(-sp.Rational(7, 4))
    f, delta = -sp.Rational(3, 4)*tau**(-sp.Rational(7, 4)), sp.Rational(7, 8)*tau**(-sp.Rational(11, 4))
    radii = (tau**(-sp.Rational(1, 2))/4, sp.sqrt(46)*tau**(-sp.Rational(1, 2))/4)
    moments = {p: sp.simplify(2*K*(sp.Rational(44, 45)*radii[0]**p+sp.Rational(1, 45)*radii[1]**p)) for p in range(5)}
    C, Y = moments[1], moments[3]
    F = sp.simplify((dt(C)+2*Y)/2)
    for label, lhs, rhs in (("energy", dt(K), -2*E), ("enstrophy", dt(E), f+G),
                            ("departure", dt(f), -3*delta/2), ("moment zero", moments[0], 2*K),
                            ("moment two", moments[2], 2*E), ("moment four", moments[4], 2*G),
                            ("critical", dt(C)+2*Y, 2*F)):
        book.exact("scalar "+label, lhs, rhs)
    book.exact("scalar moment interpolation ratio", K*G/E**2, 12)
    book.check("scalar negative amplification", f.is_negative, f)
    book.check("scalar positive departure", delta.is_positive, delta)
    book.exact("scalar finite energy dissipation", sp.integrate(E, (tau, 0, 1)), 4)
    book.check("scalar divergent energy-enstrophy product", sp.limit(K*E, tau, 0, dir="+") == sp.oo, K*E)
    book.check("scalar divergent critical moment", sp.limit(C, tau, 0, dir="+") == sp.oo, C)
    for label, slack in (("critical Cauchy", 4*K*E-C*C), ("adjacent moments", C*Y-4*E*E), ("upper moments", 2*E*2*G-Y*Y)):
        book.check("scalar "+label, sp.simplify(slack).is_nonnegative, sp.simplify(slack))
    deficit = sp.simplify(G-E*E/K)
    criterion = sp.simplify(deficit**sp.Rational(2, 3))
    book.check("scalar divergent known deficit criterion", sp.integrate(criterion, (tau, 0, 1)) == sp.oo, criterion)
    return {key: str(sp.simplify(value)) for key, value in dict(K=K, E=E, G=G, f=f, delta=delta, C=C, Y=Y, F=F,
            variance=K*E-C*C/4, spectral_deficit=deficit, criterion_integrand=criterion).items()}


def compute(result):
    book = depletion.DepletionReceipt()
    result.update(checks=book.checks, failures=book.failures, exact_rows=[], grid_rows=[], formulas={})
    algebra(book)
    result["scalar_control"] = scalar_control(book)
    max_error = 0.0
    for name, field in fixtures().items():
        formulas, (a_symbol, nu_symbol) = exact_fixture(field, book, name)
        result["formulas"][name] = {key: str(value) for key, value in formulas.items()}
        if name == "cyclic":
            book.exact("cyclic zero variance", formulas["V"], 0)
            book.exact("cyclic zero variance first derivative", formulas["Vdot"], 0)
            book.exact("cyclic variance second derivative", formulas["Vddot"], sp.Rational(9, 16)*a_symbol**6*(3-2*sp.sqrt(2)))
        for a in AMPLITUDES:
            for nu in VISCOSITIES:
                exact = {key: sp.simplify(value.subs({a_symbol: a, nu_symbol: nu})) for key, value in formulas.items()}
                values = {key: float(value.evalf(40)) for key, value in exact.items()}
                row = dict(fixture=name, amplitude=a, viscosity=float(nu), exact={key: str(value) for key, value in exact.items()}, values=values,
                           departure_with_critical_growth=bool(exact["delta"]>0 and exact["Cdot"]>0),
                           negative_f_with_critical_growth=bool(exact["f"]<0 and exact["Cdot"]>0))
                result["exact_rows"].append(row)
                book.check(f"{name} a={a} nu={nu} centered inequality", exact["centered_slack"].is_nonnegative, exact["centered_slack"])
                if name == "cyclic":
                    book.check(f"{name} a={a} nu={nu} positive variance curvature", exact["Vddot"].is_positive, exact["Vddot"])
                for n in GRIDS:
                    observed = fft_quantities(field, n, a, float(nu))
                    errors = {key: abs(value-values[key])/max(1.0, abs(value), abs(values[key])) for key, value in observed.items()}
                    finite = all(math.isfinite(value) for value in list(observed.values())+list(errors.values()))
                    err = max(errors.values())
                    max_error = max(max_error, err)
                    result["grid_rows"].append(dict(fixture=name, amplitude=a, viscosity=float(nu), grid=n, values=observed, errors=errors))
                    book.check(f"FFT {name} a={a} nu={nu} N={n}", finite and err<TOLERANCE, dict(max_error=err, worst=max(errors, key=errors.get)))
    book.check("numerical comparisons present and finite", bool(result["grid_rows"]) and math.isfinite(max_error), max_error)
    success = not book.failures
    result.update(status="PASS" if success else "FAIL", check_count=len(book.checks), max_numerical_discrepancy=max_error,
                  control_classifications={
                      "zero_variance_preservation": "CONTRADICTS" if success else "INCONCLUSIVE",
                      "departure_implies_nonincreasing_critical_norm": "CONTRADICTS" if success and any(row["departure_with_critical_growth"] for row in result["exact_rows"]) else "INCONCLUSIVE",
                      "scalar_budget_closure": "CONTRADICTS" if success else "INCONCLUSIVE"},
                  scope=dict(NS_trajectory="NOT_RUN", arbitrary_data_regularity="UNRESOLVED", data_controlled_critical_production="UNRESOLVED"))
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path, snapshot_dir = output.with_suffix(".inputs.json"), output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = dict(protocol=PROTOCOL, script=Path(__file__).resolve(), depletion=Path(depletion.__file__).resolve(), transfer=Path(transfer.__file__).resolve())
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(payloads[key]).hexdigest()) for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir/path.name).write_bytes(payloads[key])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), identities=identities, numpy_version=np.__version__, sympy_version=sp.__version__)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    result = dict(schema="cassi.navier-stokes.critical-recurrence.verification.v1", **manifest)
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
    print(json.dumps({key: result.get(key) for key in ("status", "check_count", "max_numerical_discrepancy", "control_classifications", "error")}, indent=2))
    if success and result.get("status")=="PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
