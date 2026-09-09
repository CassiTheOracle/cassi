#!/usr/bin/env python3
"""Verify fixed forced NS budgets and Euclidean concentration scalings.

Run from CassiTheory with --output pointing to a fresh receipt path.
No Navier-Stokes trajectory or announced blow-up proof is computed.
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

import verify_navier_stokes_critical_recurrence as recurrence
import verify_navier_stokes_depletion as depletion
import verify_navier_stokes_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-forced-concentration-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_forced_concentration/verification.json"
VISCOSITIES = (sp.Rational(1, 100), sp.Integer(1))
GRIDS = (24, 32)
FORCES = ("zero", "drive", "brake", "laplacian", "off_support")
TOLERANCE = 1e-10


def force_field(u, name):
    if name == "zero":
        return {}
    if name == "drive":
        return u
    if name == "brake":
        return recurrence.scale(u, -1)
    if name == "laplacian":
        return recurrence.lap(u)
    result = {}
    for k, component in (((0, 0, 2), 0), ((2, 0, 0), 1), ((0, 2, 0), 2)):
        value = sp.zeros(3, 1)
        value[component] = -sp.I / 2
        transfer.add_real_mode(result, k, value)
    return result


def exact_row(u, g, nu, book, label):
    inner = recurrence.inner
    B = transfer.full_leray_B(u)
    ut = recurrence.field_sum(B, recurrence.scale(recurrence.lap(u), -nu), g)
    Bt = recurrence.field_sum(recurrence.bilinear(ut, u), recurrence.bilinear(u, ut))
    m = {p: inner(u, u, p) for p in (0, 1, 2, 3, 4)}
    dm = {p: 2 * inner(u, ut, p) for p in (0, 1, 2, 4)}
    K, E, G, C, Y = m[0] / 2, m[2] / 2, m[4] / 2, m[1], m[3]
    A, F = inner(u, B, 2), inner(u, B, 1)
    I0, I1, I2 = (inner(u, g, p) for p in (0, 1, 2))
    H2 = inner(g, g, -1)
    S, T = recurrence.strain(u), recurrence.strain(g)
    Q = recurrence.strain_project(recurrence.tensor_square(S))
    R = recurrence.field_sum(recurrence.scale(recurrence.strain(B), -1), recurrence.scale(Q, -sp.Rational(2, 3)))
    M = recurrence.field_sum(recurrence.scale(recurrence.lap(S), nu), recurrence.scale(Q, sp.Rational(2, 3)))
    D = recurrence.field_sum(M, recurrence.scale(R, sp.Rational(1, 2)))
    delta, MT = inner(R, R) - 4 * inner(D, D), inner(M, T)
    fdot = inner(ut, B, 2) + inner(u, Bt, 2) - 3 * nu * inner(u, ut, 4)
    V = K * E - C * C / 4
    Vdot = dm[0] * E / 2 + K * dm[2] / 2 - C * dm[1] / 2
    pressure = {}
    transfer.add_real_mode(pressure, (1, 1, 1), sp.I * sp.ones(3, 1) / 2)
    raw_force = recurrence.field_sum(g, pressure)
    projected = {k: transfer.leray_projector(k) * value for k, value in raw_force.items()}
    difference = recurrence.field_sum(projected, recurrence.scale(g, -1))
    book.exact(label + " pressure gradient removal", inner(difference, difference), 0)
    book.exact(label + " kinetic source budget", dm[0] / 2, -2 * nu * E + I0)
    book.exact(label + " strain source budget", dm[2] / 2, A - 2 * nu * G + I2)
    book.exact(label + " critical source budget", dm[1], 2 * F - 2 * nu * Y + 2 * I1)
    book.exact(label + " spread source budget", Vdot + nu * (2 * K * G + 2 * E * E - C * Y), K * A - C * F + E * I0 + K * I2 - C * I1)
    book.exact(label + " amplification source budget", fdot, -3 * delta / 2 - 6 * MT)
    slack = sp.simplify(Y * H2 - I1 * I1)
    book.check(label + " critical forcing duality", slack >= 0, slack)
    return {key: sp.simplify(value) for key, value in dict(
        K=K, E=E, G=G, C=C, Y=Y, A=A, F=F, f=A - 3 * nu * G,
        delta=delta, MT=MT, I0=I0, I1=I1, I2=I2, H2=H2, V=V,
        Kdot=dm[0] / 2, Edot=dm[2] / 2, Cdot=dm[1], Vdot=Vdot,
        fdot=fdot, duality_slack=slack).items()}


def spatial_row(name, force, n, nu):
    axes = (0, 1, 2)
    x, y, z = np.meshgrid(*(np.arange(n) * (2 * np.pi / n),) * 3, indexing="ij")
    k = np.stack(np.meshgrid(*(np.fft.fftfreq(n, d=1 / n),) * 3, indexing="ij"), axis=-1)
    r2, shape = np.sum(k * k, axis=-1), (n, n, n)
    r = np.sqrt(r2)
    inv2 = np.divide(1., r2, out=np.zeros(shape), where=r2 > 0)
    inv1 = np.divide(1., r, out=np.zeros(shape), where=r > 0)

    def fft(value):
        return np.fft.fftn(value, axes=axes)

    def physical(value):
        return np.fft.ifftn(value, axes=axes).real

    def project(value):
        return value - k * inv2[..., None] * np.sum(k * value, axis=-1)[..., None]

    def grad(value):
        return physical(1j * k[..., :, None] * fft(value)[..., None, :])

    def lap(value):
        return physical(r2[..., None] * fft(value))

    def convection(left, right):
        return physical(project(fft(-np.einsum("...j,...ji->...i", left, grad(right)))))

    def strain(value):
        derivative = grad(value)
        return (derivative + np.swapaxes(derivative, -1, -2)) / 2

    def project_tensor(value):
        hat = fft(value)
        v = project(np.einsum("...ij,...j->...i", hat, k))
        return physical((k[..., :, None] * v[..., None, :] + v[..., :, None] * k[..., None, :]) * inv2[..., None, None])

    if name == "cyclic":
        u = np.stack((np.sin(y), np.sin(z), np.sin(x)), axis=-1)
    else:
        u = np.stack((-2 * np.sin(2 * y) + 4 * np.sin(x + 2 * y) - 2 * np.sin(3 * z),
                      -2 * np.sin(x) - 2 * np.sin(x + 2 * y), -2 * np.sin(x)), axis=-1)
    if force == "zero":
        g = np.zeros_like(u)
    elif force == "drive":
        g = u
    elif force == "brake":
        g = -u
    elif force == "laplacian":
        g = lap(u)
    else:
        g = np.stack((np.sin(2 * z), np.sin(2 * x), np.sin(2 * y)), axis=-1)
    raw = g - np.sin(x + y + z)[..., None] * np.ones(3)
    g = physical(project(fft(raw)))
    B = convection(u, u)
    ut = B - nu * lap(u) + g
    Bt = convection(ut, u) + convection(u, ut)
    U, BH, UT, BT, GH = (fft(value) / n**3 for value in (u, B, ut, Bt, g))

    def inner(left, right, power):
        weight = inv1 if power == -1 else r**power
        return float(np.real(np.sum(weight[..., None] * np.conjugate(left) * right)))

    m = {p: inner(U, U, p) for p in (0, 1, 2, 3, 4)}
    dm = {p: 2 * inner(U, UT, p) for p in (0, 1, 2)}
    K, E, G, C, Y = m[0] / 2, m[2] / 2, m[4] / 2, m[1], m[3]
    A, F = inner(U, BH, 2), inner(U, BH, 1)
    I0, I1, I2 = (inner(U, GH, p) for p in (0, 1, 2))
    H2 = inner(GH, GH, -1)
    gradient, S, T = grad(u), strain(u), strain(g)
    omega = np.stack((gradient[..., 1, 2] - gradient[..., 2, 1],
                      gradient[..., 2, 0] - gradient[..., 0, 2],
                      gradient[..., 0, 1] - gradient[..., 1, 0]), axis=-1)
    advS, SH = np.zeros_like(S), fft(S)
    for j in range(3):
        advS += u[..., j, None, None] * physical(1j * k[..., j, None, None] * SH)
    S2 = np.matmul(S, S)
    R = project_tensor(advS + S2 / 3 + omega[..., :, None] * omega[..., None, :] / 4)
    M = nu * physical(r2[..., None, None] * SH) + 2 * project_tensor(S2) / 3
    delta = float(np.mean(np.sum(R * R - 4 * (M + R / 2)**2, axis=(-1, -2))))
    MT = float(np.mean(np.sum(M * T, axis=(-1, -2))))
    fdot = inner(UT, BH, 2) + inner(U, BT, 2) - 3 * nu * inner(U, UT, 4)
    V = K * E - C * C / 4
    Vdot = dm[0] * E / 2 + K * dm[2] / 2 - C * dm[1] / 2
    return dict(K=K, E=E, G=G, C=C, Y=Y, A=A, F=F, f=A - 3 * nu * G,
                delta=delta, MT=MT, I0=I0, I1=I1, I2=I2, H2=H2, V=V,
                Kdot=dm[0] / 2, Edot=dm[2] / 2, Cdot=dm[1], Vdot=Vdot,
                fdot=fdot, duality_slack=Y * H2 - I1 * I1)


def analytical_controls(book):
    d, a, h = sp.symbols("d a h", positive=True)
    book.exact("forcing Young completion", d * a*a + h*h / d - 2 * a * h, (sp.sqrt(d) * a - h / sp.sqrt(d))**2)
    zero, g = {}, force_field({}, "off_support")
    book.exact("rest kinetic first derivative", recurrence.inner(zero, g), 0)
    book.exact("rest critical first derivative", 2 * recurrence.inner(zero, g, 1), 0)
    kddot = recurrence.inner(g, g)
    cddot = 2 * recurrence.inner(g, g, 1)
    book.check("forcing from rest positive second derivatives", kddot > 0 and cddot > 0, dict(Kddot=kddot, Cddot=cddot))
    velocity, spatial, temporal, dimension = 1, 1, 2, 3
    force, pressure = velocity + temporal, 2 * velocity
    exponents = dict(ut=velocity + temporal, convection=2 * velocity + spatial,
                     laplacian=velocity + 2 * spatial, pressure_gradient=pressure + spatial,
                     force=force, K=2 * velocity - dimension,
                     E=2 * (velocity + spatial) - dimension,
                     G=2 * (velocity + 2 * spatial) - dimension,
                     C=2 * velocity + spatial - dimension,
                     Y=2 * velocity + 3 * spatial - dimension,
                     V=4 * velocity + 2 * spatial - 2 * dimension,
                     I0=velocity + force - dimension,
                     I1=velocity + spatial + force - dimension,
                     I2=velocity + 2 * spatial + force - dimension)
    book.check("parabolic equation homogeneous scaling", len({exponents[k] for k in ("ut", "convection", "laplacian", "pressure_gradient", "force")}) == 1, exponents)
    sobolev_exponent = force - sp.Rational(1, 2) * spatial - sp.Rational(dimension, 2)
    book.exact("rescaled force spatial norm exponent", sobolev_exponent, 1)
    book.exact("rescaled force spacetime norm exponent", 2 * sobolev_exponent - 2, 0)
    order, time_order = sp.symbols("order time_order", nonnegative=True, integer=True)
    derivative_factor = force + spatial * order + temporal * time_order
    profile_h = sp.symbols("h", positive=True)
    volume = sp.Rational(3, 2) - profile_h
    speed = -sp.Rational(1, 2) - profile_h
    book.exact("quoted core energy exponent", volume + 2 * speed, sp.Rational(1, 2) - 3 * profile_h)
    book.exact("quoted core cubic-speed exponent", volume + 3 * speed, -4 * profile_h)
    return dict(exponents=exponents, forcing_from_rest=dict(Kddot=str(kddot), Cddot=str(cddot)),
                force_derivative_exponent=str(derivative_factor),
                core_energy_exponent=str(volume + 2 * speed), core_cubic_speed_exponent=str(volume + 3 * speed))


def euclidean_control(book):
    x, y, z, r, ell = sp.symbols("x y z r ell", real=True, positive=True)
    xyz = (x, y, z)
    U = sp.Matrix([-2 * y, 2 * x, 0]) * sp.exp(-(x*x + y*y + z*z))
    book.exact("Gaussian solenoidal profile", sum(sp.diff(U[j], xyz[j]) for j in range(3)), 0)
    expected = {0: sp.pi**sp.Rational(3, 2) / sp.sqrt(2), 1: 8 * sp.pi / 3,
                2: 5 * sp.pi**sp.Rational(3, 2) / sp.sqrt(2), 3: 16 * sp.pi}
    rows, errors = {}, []
    with mp.workdps(60):
        for p in (0, 1, 2, 3):
            exact = sp.integrate(sp.pi * r**(p + 4) * sp.exp(-r*r / 2) / 3, (r, 0, sp.oo))
            book.exact(f"Gaussian radial moment {p}", exact, expected[p])
            numeric = mp.pi / 3 * mp.quad(lambda radius: radius**(p + 4) * mp.exp(-radius**2 / 2), [0, 1, mp.inf])
            target = mp.mpf(str(sp.N(exact, 65)))
            error = float(abs(numeric - target) / max(1, abs(numeric), abs(target)))
            book.check(f"Gaussian independent quadrature {p}", math.isfinite(error) and error < TOLERANCE, error)
            rows[str(p)] = dict(exact=str(exact), quadrature=str(numeric), discrepancy=error)
            errors.append(error)
    K, E, C = expected[0] / 2, expected[2] / 2, expected[1]
    eta = sp.simplify(1 - C*C / (4 * K * E))
    book.check("Gaussian nonzero spectral spread", eta > 0 and eta < 1, eta)
    book.exact("Gaussian maximum speed radius", sp.diff(4 * r*r * sp.exp(-2 * r*r), r).subs(r, 1 / sp.sqrt(2)), 0)
    book.exact("Gaussian maximum speed squared", (4 * r*r * sp.exp(-2 * r*r)).subs(r, 1 / sp.sqrt(2)), 2 / sp.E)
    book.exact("kinematic concentrating energy limit", sp.limit(ell * K, ell, 0, dir="+"), 0)
    book.check("kinematic concentrating speed limit", sp.limit(sp.sqrt(2 / sp.E) / ell, ell, 0, dir="+") == sp.oo)
    scaled_energy = sp.integrate(sp.pi * ell**6 * r**4 * sp.exp(-ell**2 * r*r / 2) / 6, (r, 0, sp.oo))
    scaled_critical = sp.integrate(sp.pi * ell**6 * r**5 * sp.exp(-ell**2 * r*r / 2) / 3, (r, 0, sp.oo))
    book.exact("kinematic energy scaling from Fourier integral", scaled_energy, ell * K)
    book.exact("kinematic critical norm invariance", scaled_critical, C)
    return dict(moments=rows, K=str(K), C=str(C), eta=str(eta), scope="KINEMATIC_ONLY"), errors


def compute(result):
    book = depletion.DepletionReceipt()
    result["analytical_controls"] = analytical_controls(book)
    result["euclidean_control"], errors = euclidean_control(book)
    exact_rows, spatial_rows = [], []
    for name in ("cyclic", "three_coordinate"):
        u = recurrence.fixtures()[name]
        book.check(name + " real solenoidal datum", transfer.is_real_field(u) and all(value == 0 for value in transfer.divergence(u).values()))
        for nu in VISCOSITIES:
            for force in FORCES:
                label = f"{name} nu={nu} g={force}"
                values = exact_row(u, force_field(u, force), nu, book, label)
                exact_rows.append(dict(name=name, nu=str(nu), force=force, values={key: str(value) for key, value in values.items()}))
                if force in ("drive", "brake"):
                    book.check(label + " source work sign", values["I1"] > 0 if force == "drive" else values["I1"] < 0, values["I1"])
                for n in GRIDS:
                    spatial = spatial_row(name, force, n, float(nu))
                    discrepancies = {key: abs(spatial[key] - float(sp.N(value, 18))) / max(1., abs(spatial[key]), abs(float(sp.N(value, 18)))) for key, value in values.items()}
                    quality = bool(discrepancies) and all(math.isfinite(spatial[key]) and math.isfinite(error) and error < TOLERANCE for key, error in discrepancies.items())
                    error = max(discrepancies.values())
                    book.check(label + f" independent FFT N={n}", quality, dict(max_error=error, discrepancies=discrepancies))
                    errors.extend(discrepancies.values())
                    spatial_rows.append(dict(name=name, nu=str(nu), force=force, n=n, values=spatial, discrepancies=discrepancies))
    success = not book.failures and bool(errors) and all(math.isfinite(error) and error < TOLERANCE for error in errors)
    result.update(status="PASS" if success else "FAIL", checks=book.checks, failures=book.failures,
                  check_count=len(book.checks), max_numerical_discrepancy=max(errors), exact_rows=exact_rows,
                  spatial_rows=spatial_rows, control_classifications=dict(
                      forced_budgets="PASS" if success else "INCONCLUSIVE",
                      kinematic_bounded_energy_speed_implies_critical_growth="CONTRADICTS" if success else "INCONCLUSIVE",
                      arbitrary_data_regularity="UNRESOLVED", unforced_blowup="UNRESOLVED",
                      nontrivial_blowup_limit="UNRESOLVED", announced_proof="NOT_AUDITED", NS_trajectory="NOT_RUN"))
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    output = parser.parse_args().output.resolve()
    manifest_path, snapshot_dir = output.with_suffix(".inputs.json"), output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = dict(protocol=PROTOCOL, script=Path(__file__).resolve(), recurrence=Path(recurrence.__file__).resolve(),
                   depletion=Path(depletion.__file__).resolve(), transfer=Path(transfer.__file__).resolve())
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(payloads[key]).hexdigest()) for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[key])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), identities=identities,
                    numpy_version=np.__version__, sympy_version=sp.__version__, mpmath_version=mp.__version__)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    result = dict(schema="cassi.navier-stokes.forced-concentration.verification.v1", **manifest)
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
    if success and result.get("status") == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
