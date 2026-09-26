#!/usr/bin/env python3
"""Verify the fixed Gaussian fine-scale NS transfer controls.

Run from CassiTheory: python computations/verify_navier_stokes_depletion.py
The default receipt is anchored to CassiTheory; --output must be a fresh path.
This executes algebra and instantaneous Fourier quadrature, not a trajectory.
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
from numpy.polynomial.legendre import leggauss

import verify_navier_stokes_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-depletion-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_depletion/verification.json"
LENGTHS = (sp.Rational(1, 2), sp.Integer(1), sp.Integer(2))
VISCOSITIES = (sp.Rational(1, 100), sp.Integer(1))
TOLERANCE = 1e-10
AXES = (1, 2, 3)


class DepletionReceipt(transfer.Receipt):
    def check(self, name: str, passed: bool, value: object = None) -> None:
        if name in self.checks:
            raise ValueError(f"Duplicate verification check: {name}")
        super().check(name, passed, value)


def json_safe(value):
    """Preserve nonfinite failure values as explicit JSON markers."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": str(value)}
    if isinstance(value, dict):
        for key in value:
            value[key] = json_safe(value[key])
    elif isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = json_safe(item)
    elif isinstance(value, tuple):
        return [json_safe(item) for item in value]
    return value


def fixtures():
    cyclic, shear = {}, {}
    for k, v in (((0, 1, 0), (1, 0, 0)), ((0, 0, 1), (0, 1, 0)),
                 ((1, 0, 0), (0, 0, 1))):
        transfer.add_real_mode(cyclic, k, -sp.I * sp.Matrix(v) / 2)
    transfer.add_real_mode(shear, (0, 1, 0), -sp.I * sp.Matrix([1, 0, 0]) / 2)
    return {"cyclic": cyclic, "planar": transfer.planar_fixture(),
            "three_coordinate": transfer.three_dimensional_fixture(), "shear": shear}


def atoms(left, advecting, carried):
    """Keep triad geometry in its coefficient; group only equal heat exponents."""
    result = {}
    for p, up in advecting.items():
        for q, uq in carried.items():
            a = tuple(p[j] + q[j] for j in range(3))
            if a not in left or a == (0, 0, 0):
                continue
            coefficient = transfer.real_part(transfer.inner_vec(
                left[a], transfer.projected_convection(a, p, q, up, uq)))
            a2 = int(transfer.mode_norm_sq(a))
            total2 = a2 + int(transfer.mode_norm_sq(p) + transfer.mode_norm_sq(q))
            key = (a2, total2)
            result[key] = result.get(key, sp.Integer(0)) + coefficient
    return {key: sp.factor(value) for key, value in result.items() if value != 0}


def derivative_atoms(u, direction):
    result = {}
    for part in (atoms(direction, u, u), atoms(u, direction, u), atoms(u, u, direction)):
        for key, value in part.items():
            result[key] = result.get(key, sp.Integer(0)) + value
    return {key: sp.factor(value) for key, value in result.items() if value != 0}


def value_from_atoms(rows, length=None):
    total = sp.Integer(0)
    for (a2, total2), coefficient in rows.items():
        weight = sp.sqrt(a2)
        if length is not None:
            weight = sp.exp(-length**2 * a2 / 2) * (weight - sp.sqrt(sp.Rational(total2, 2)))
        total += coefficient * weight
    return sp.simplify(total)


def split_values(rows, length):
    total = value_from_atoms(rows)
    coarse = value_from_atoms(rows, length)
    return total, coarse, sp.simplify(total - coarse)


def scalar_number(value):
    return float(sp.N(value, 18))


def scaled(field, factor):
    return {k: factor * value for k, value in field.items()}


def numeric_atoms(left, advecting, carried):
    result = {}
    for p, up in advecting.items():
        for q, uq in carried.items():
            a = tuple(p[j] + q[j] for j in range(3))
            if a not in left or a == (0, 0, 0):
                continue
            av = np.asarray(a, dtype=float)
            a2 = int(av @ av)
            raw = -1j * np.dot(q, up) * uq
            raw -= av * (av @ raw) / a2
            coefficient = float(np.vdot(left[a], raw).real)
            key = (a2, a2 + sum(v*v for v in p) + sum(v*v for v in q))
            result[key] = result.get(key, 0.0) + coefficient
    return result


def numeric_derivative_atoms(u, direction):
    result = {}
    for part in (numeric_atoms(direction, u, u), numeric_atoms(u, direction, u),
                 numeric_atoms(u, u, direction)):
        for key, value in part.items():
            result[key] = result.get(key, 0.0) + value
    return result


def exponential_difference(a, b, ell):
    """exp(-b ell^2)-exp(-a ell^2), retaining precision at small ell."""
    if a == b:
        return np.zeros_like(ell)
    return (np.sign(a - b) * np.exp(-min(a, b) * ell**2)
            * -np.expm1(-abs(a - b) * ell**2))


def mean_from_atoms(rows, ell, length):
    return sum(float(coefficient) * math.exp(-length*length*a2/2)
               * float(exponential_difference(a2, total2/2, np.asarray(ell)))
               for (a2, total2), coefficient in rows.items())


def integrated_atoms(rows, length, order):
    nodes, weights = leggauss(order)
    s = (nodes + 1) / 2
    ell = s / (1 - s)
    measure = weights / (2 * (1 - s)**2 * ell**2 * math.sqrt(math.pi))
    total = 0.0
    for (a2, total2), coefficient in rows.items():
        total += coefficient * math.exp(-length*length*a2/2) * float(
            measure @ exponential_difference(a2, total2/2, ell))
    return total


def spatial_state(name, n):
    x, y, z = np.meshgrid(*(np.arange(n) * (2*np.pi/n),)*3, indexing="ij")
    zero = np.zeros_like(x)
    if name == "cyclic":
        u = np.stack((np.sin(y), np.sin(z), np.sin(x)))
    elif name == "planar":
        u = np.stack((-2*np.sin(2*y), -2*np.sin(x), zero))
    elif name == "three_coordinate":
        u = np.stack((-2*np.sin(2*y)+4*np.sin(x+2*y)-2*np.sin(3*z),
                      -2*np.sin(x)-2*np.sin(x+2*y), -2*np.sin(x)))
    else:
        u = np.stack((np.sin(y), zero, zero))
    k = np.asarray(np.meshgrid(*(np.fft.fftfreq(n)*n,)*3, indexing="ij"))
    k2 = np.sum(k*k, axis=0)
    uhat = np.fft.fftn(u, axes=AXES)
    gradient = np.asarray([[np.fft.ifftn(1j*k[j]*uhat[i]).real
                            for j in range(3)] for i in range(3)])
    raw = -np.einsum("jxyz,ijxyz->ixyz", u, gradient)
    vhat = np.fft.fftn(raw, axes=AXES)
    denominator = np.where(k2 == 0, 1, k2)
    vhat -= k * (np.sum(k*vhat, axis=0) / denominator)
    vhat[:, 0, 0, 0] = 0
    v = np.fft.ifftn(vhat, axes=AXES).real
    uu = np.einsum("ixyz,jxyz->ijxyz", u, u)
    uv = np.einsum("ixyz,jxyz->ijxyz", u, v) + np.einsum("ixyz,jxyz->ijxyz", v, u)
    return {"u": uhat, "v": vhat, "k": k, "k2": k2,
            "uu": np.fft.fftn(uu, axes=(2, 3, 4)),
            "uv": np.fft.fftn(uv, axes=(2, 3, 4))}


def grid_means(state, ell, length):
    g = np.exp(-ell*ell*state["k2"]/2)
    h = np.exp(-length*length*state["k2"]/2)
    u = np.fft.ifftn(state["u"]*g, axes=AXES).real
    v = np.fft.ifftn(state["v"]*g, axes=AXES).real
    tau = np.fft.ifftn(state["uu"]*g, axes=(2, 3, 4)).real - np.einsum("ixyz,jxyz->ijxyz", u, u)
    tau_dot = (np.fft.ifftn(state["uv"]*g, axes=(2, 3, 4)).real
               - np.einsum("ixyz,jxyz->ijxyz", u, v)
               - np.einsum("ixyz,jxyz->ijxyz", v, u))
    values = []
    for multiplier in (g, g*h):
        gradient = np.asarray([[np.fft.ifftn(1j*state["k"][j]*state["u"][i]*multiplier).real
                                for j in range(3)] for i in range(3)])
        gradient_dot = np.asarray([[np.fft.ifftn(1j*state["k"][j]*state["v"][i]*multiplier).real
                                    for j in range(3)] for i in range(3)])
        strain = (gradient + gradient.swapaxes(0, 1)) / 2
        strain_dot = (gradient_dot + gradient_dot.swapaxes(0, 1)) / 2
        values.extend((-float(np.mean(np.sum(strain*tau, axis=(0, 1)))),
                       -float(np.mean(np.sum(strain_dot*tau + strain*tau_dot, axis=(0, 1))))))
    full, full_dot, coarse, coarse_dot = values
    return {"coarse": coarse, "fine": full-coarse,
            "coarse_dot": coarse_dot, "fine_dot": full_dot-coarse_dot}


def field_on_grid(field, n):
    result = np.zeros((3, n, n, n), dtype=complex)
    for k, value in field.items():
        result[(slice(None),) + tuple(v % n for v in k)] = np.asarray(value, dtype=complex).reshape(3)
    return result


def compute(result):
    book = DepletionReceipt()
    result["checks"] = book.checks
    result["failures"] = book.failures
    exact_rows, grid_rows, quadrature_rows, absorption_rows = [], [], [], []
    result.update(exact_rows=exact_rows, grid_rows=grid_rows,
                  quadrature_rows=quadrature_rows, absorption_rows=absorption_rows)

    def close(label, actual, expected):
        actual, expected = float(actual), float(expected)
        error = abs(actual-expected) / max(1, abs(actual), abs(expected))
        book.check(label, math.isfinite(error) and error < TOLERANCE, error)
        return error

    r, length, lam = sp.symbols("r L lambda", positive=True)
    kernel_squared = (2*sp.pi*length**2)**(-3) * sp.exp(-r*r/length**2)
    gradient_norm = sp.integrate(4*sp.pi*r**4*kernel_squared/length**4, (r, 0, sp.oo))
    book.exact("Gaussian gradient norm", gradient_norm, 3/(16*sp.pi**sp.Rational(3, 2)*length**5))
    book.exact("Euclidean coarse rate scaling", (length/lam)**(-sp.Rational(5, 2))*lam**(-sp.Rational(1, 2))/length**(-sp.Rational(5, 2)), lam**2)

    for name, u in fixtures().items():
        print(f"FIXTURE {name}", flush=True)
        b = transfer.full_leray_B(u)
        heat = transfer.heat_direction(u, sp.Integer(1))
        base, nonlinear, viscous = atoms(u, u, u), derivative_atoms(u, b), derivative_atoms(u, heat)
        c, y, bnorm = transfer.quadratic_C(u), transfer.quadratic_Y(u), transfer.field_inner(b, b)
        f = transfer.scalar_F(u)
        book.check(f"{name}: real and solenoidal", transfer.is_real_field(u) and transfer.is_real_field(b)
                   and all(v == 0 for v in transfer.divergence(u).values())
                   and all(v == 0 for v in transfer.divergence(b).values()))
        book.exact(f"{name}: kinetic energy cancellation", transfer.field_inner(u, b), 0)
        book.exact(f"{name}: transfer atoms", value_from_atoms(base), f)
        book.exact(f"{name}: zero split length", value_from_atoms(base, sp.Integer(0)), f)
        book.exact(f"{name}: zero length derivative", value_from_atoms(nonlinear, sp.Integer(0)), value_from_atoms(nonlinear))
        if name == "cyclic":
            book.exact("cyclic: C", c, sp.Rational(3, 2))
            book.exact("cyclic: Y", y, sp.Rational(3, 2))
            book.exact("cyclic: nonlinear norm", bnorm, sp.Rational(3, 4))
            book.exact("cyclic: full transfer derivative", value_from_atoms(nonlinear), 3*(sp.sqrt(2)-1)/4)
            for nu in VISCOSITIES:
                direction = {k: b.get(k, transfer.zero_vec()) + nu*heat.get(k, transfer.zero_vec()) for k in set(b) | set(heat)}
                ydot = 2*sum(transfer.mode_norm(k)**3 * transfer.real_part(transfer.inner_vec(u[k], direction[k])) for k in u)
                second_c = 2*(value_from_atoms(nonlinear)+nu*value_from_atoms(viscous))-2*nu*ydot
                book.exact(f"cyclic: C second derivative nu={nu}", second_c, 3*(sp.sqrt(2)-1)/2+6*nu**2)
        if name == "planar":
            book.exact("planar: full transfer derivative", value_from_atoms(nonlinear), bnorm*(sp.sqrt(5)-sp.Rational(7, 3)))
        if name in ("cyclic", "planar", "shear"):
            book.exact(f"{name}: initial transfer", f, 0)
        if name == "shear":
            book.exact("shear: nonlinear acceleration", bnorm, 0)

        reverse = scaled(u, -1)
        reversed_b = transfer.full_leray_B(reverse)
        reverse_rows = (atoms(reverse, reverse, reverse), derivative_atoms(reverse, reversed_b),
                        derivative_atoms(reverse, transfer.heat_direction(reverse, sp.Integer(1))))
        large = scaled(u, 8)
        large_b = transfer.full_leray_B(large)
        large_rows = (atoms(large, large, large), derivative_atoms(large, large_b),
                      derivative_atoms(large, transfer.heat_direction(large, sp.Integer(1))))
        book.exact(f"{name}: C amplitude degree", transfer.quadratic_C(large), 64*c)
        book.exact(f"{name}: Y amplitude degree", transfer.quadratic_Y(large), 64*y)
        for ell_split in LENGTHS:
            f_all, fc, ff = split_values(base, ell_split)
            df, dfc, dff = split_values(nonlinear, ell_split)
            vf, vfc, vff = split_values(viscous, ell_split)
            if name == "cyclic":
                book.exact(f"cyclic: fine derivative L={ell_split}", dff, (1-sp.exp(-ell_split**2/2))*3*(sp.sqrt(2)-1)/4)
                book.exact(f"cyclic: viscous derivative L={ell_split}", vff, 0)
            if name == "planar":
                expected = bnorm*((1-sp.exp(-ell_split**2/2))*(1-sp.sqrt(5))-4*(1-sp.exp(-2*ell_split**2))*(2-sp.sqrt(5)))/3
                book.exact(f"planar: fine derivative L={ell_split}", dff, expected)
            for idx, (row, sign, degree) in enumerate(zip((base, nonlinear, viscous), (-1, 1, -1), (3, 4, 3))):
                target = split_values(row, ell_split)
                negative = split_values(reverse_rows[idx], ell_split)
                amplified = split_values(large_rows[idx], ell_split)
                for component in range(3):
                    book.exact(f"{name}: reversal {idx}/{component} L={ell_split}", negative[component], sign*target[component])
                    book.exact(f"{name}: degree {degree} direction {idx}/{component} L={ell_split}", amplified[component], 8**degree*target[component])
            exact_rows.append({"fixture": name, "L": float(ell_split), "C": str(c), "Y": str(y),
                               "F": str(f_all), "F_coarse": str(fc), "F_fine": str(ff),
                               "DF_B": str(df), "DF_coarse_B": str(dfc), "DF_fine_B": str(dff),
                               "DF_fine_heat_unit": str(vff), "DF_fine_B_value": scalar_number(dff),
                               "B_mode_count": len(b), "B_norm_squared": str(bnorm)})
            for amplitude in (1, 8):
                for nu in VISCOSITIES:
                    residual = sp.simplify((amplitude**3*ff-nu*amplitude**2*y/2)/(amplitude**2*c))
                    absorption_rows.append({"fixture": name, "L": float(ell_split), "amplitude": amplitude,
                                            "nu": float(nu), "residual": str(residual), "value": scalar_number(residual)})

        for n in (16, 24, 32):
            state = spatial_state(name, n)
            numerical_u, numerical_b = state["u"]/n**3, state["v"]/n**3
            close(f"{name}: real-space velocity N={n}", np.linalg.norm(numerical_u-field_on_grid(u, n)), 0)
            close(f"{name}: full projected nonlinear direction N={n}", np.linalg.norm(numerical_b-field_on_grid(b, n)), 0)
            nu_dict = {k: numerical_u[(slice(None),)+tuple(v % n for v in k)] for k in u}
            generated = {tuple(p[j]+q[j] for j in range(3)) for p in u for q in u}
            nb_dict = {k: numerical_b[(slice(None),)+tuple(v % n for v in k)] for k in generated}
            numeric_base = numeric_atoms(nu_dict, nu_dict, nu_dict)
            numeric_dot = numeric_derivative_atoms(nu_dict, nb_dict)
            for ell_split in LENGTHS:
                split_float = float(ell_split)
                targets = split_values(base, ell_split)
                dot_targets = split_values(nonlinear, ell_split)
                for ell in (0.5, 1.0, 2.0):
                    measured = grid_means(state, ell, split_float)
                    coarse = mean_from_atoms(base, ell, split_float)
                    coarse_dot = mean_from_atoms(nonlinear, ell, split_float)
                    expected = {"coarse": coarse, "fine": mean_from_atoms(base, ell, 0)-coarse,
                                "coarse_dot": coarse_dot,
                                "fine_dot": mean_from_atoms(nonlinear, ell, 0)-coarse_dot}
                    errors = {key: close(f"{name}: {key} N={n} ell={ell} L={ell_split}", measured[key], expected[key]) for key in measured}
                    grid_rows.append({"fixture": name, "N": n, "ell": ell, "L": split_float,
                                      "measured": measured, "errors": errors})
                for order in (128, 192):
                    full = integrated_atoms(numeric_base, 0, order)
                    coarse = integrated_atoms(numeric_base, split_float, order)
                    full_dot = integrated_atoms(numeric_dot, 0, order)
                    coarse_dot = integrated_atoms(numeric_dot, split_float, order)
                    measured = {"coarse": coarse, "fine": full-coarse,
                                "coarse_dot": coarse_dot, "fine_dot": full_dot-coarse_dot}
                    expected = dict(zip(measured, map(scalar_number, (targets[1], targets[2], dot_targets[1], dot_targets[2]))))
                    errors = {key: close(f"{name}: integral {key} N={n} order={order} L={ell_split}", measured[key], expected[key]) for key in measured}
                    quadrature_rows.append({"fixture": name, "N": n, "order": order, "L": split_float,
                                           "measured": measured, "errors": errors})

    all_errors = [value for row in grid_rows+quadrature_rows for value in row["errors"].values()]
    finite = all(math.isfinite(row["value"]) for row in absorption_rows)
    book.check("absorption diagnostics finite", finite)
    book.check("numerical comparisons present and finite",
               bool(all_errors) and all(math.isfinite(error) for error in all_errors))
    quality = not book.failures
    cyclic_positive = all(row["DF_fine_B_value"] > TOLERANCE for row in exact_rows if row["fixture"] == "cyclic")
    positive = any(row["DF_fine_B_value"] > TOLERANCE for row in exact_rows)
    negative = any(row["DF_fine_B_value"] < -TOLERANCE for row in exact_rows)
    absorption_failure = any(row["value"] > TOLERANCE for row in absorption_rows)
    result.update(status="PASS" if quality else "FAIL",
                  max_numerical_discrepancy=max(all_errors) if all_errors else None,
                  check_count=len(book.checks), control_classifications={
                      "automatic_nonpositive_response": "CONTRADICTS" if quality and cyclic_positive else "INCONCLUSIVE",
                      "two_sided_nonlinear_response": "SUPPORTS" if quality and positive and negative else "INCONCLUSIVE",
                      "viscous_only_absorption_theta_half": "CONTRADICTS" if quality and absorption_failure else "INCONCLUSIVE"})
    return quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if output.exists() or manifest_path.exists() or snapshot_dir.exists():
        raise FileExistsError(f"Use a fresh output path; existing evidence is immutable: {output}")
    sources = {"protocol": PROTOCOL, "script": Path(__file__).resolve(),
               "transfer": Path(transfer.__file__).resolve()}
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: {"path": path.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(payloads[key]).hexdigest()} for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir/path.name).write_bytes(payloads[key])
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "identities": identities,
                "numpy_version": np.__version__, "sympy_version": sp.__version__}
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    result = {"schema": "cassi.navier-stokes.depletion.verification.v2", **manifest,
              "scope": "Exact identities and instantaneous controls; no time-integrated trajectory. "
                       "Data-controlled cumulative depletion and arbitrary-data regularity: "
                       "UNRESOLVED (scope limitations, not measured probe classifications).",
              "control_classifications": {
                  "automatic_nonpositive_response": "INCONCLUSIVE",
                  "two_sided_nonlinear_response": "INCONCLUSIVE",
                  "viscous_only_absorption_theta_half": "INCONCLUSIVE"}}
    success = False
    try:
        success = compute(result)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    json_safe(result)
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
