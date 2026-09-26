#!/usr/bin/env python3
"""Verify cumulative critical transfer in an unforced invariant NS family.

Run from CassiTheory with a fresh --output path. The continuum comparison
argument is analytical; the trajectories are qualified Fourier approximations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
import sympy as sp
from scipy.integrate import solve_ivp

import verify_navier_stokes_depletion as depletion
import verify_navier_stokes_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/navier-stokes-mixing-budget-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/navier_stokes_mixing_budget/verification.json"
PARAMETERS = (2, 4, 8, 16, 32, 64, 128, 256)
TIMES = np.linspace(0.0, 0.5, 1001)
SPATIAL_INDICES = (0, 250, 500, 750, 1000)
TOLERANCE = 1e-8


def numerical_check(book, errors, name, actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    scale = np.maximum(1.0, np.maximum(np.abs(actual), np.abs(expected)))
    error = float(np.max(np.abs(actual - expected) / scale))
    errors.append({"name": name, "error": error})
    book.check(name, math.isfinite(error) and error < TOLERANCE, error)
    return error


def analytical_controls(book):
    x, y, z, theta = sp.symbols("x y z theta", real=True)
    a, A, b, t, nu, N, c = sp.symbols("a A b t nu N c", positive=True)
    profile = sp.sin(x - a * sp.sin(y))

    def mean_square(expression):
        shifted = expression.subs(x, theta + a * sp.sin(y))
        x_mean = sp.integrate(sp.expand(shifted**2), (theta, 0, 2 * sp.pi)) / (2 * sp.pi)
        return sp.simplify(sp.integrate(sp.expand(x_mean), (y, 0, 2 * sp.pi)) / (2 * sp.pi))

    dx, dy = sp.diff(profile, x), sp.diff(profile, y)
    lap = sp.diff(profile, x, 2) + sp.diff(profile, y, 2)
    m2 = sp.Rational(1, 2) + a**2 / 4
    m4 = sp.Rational(1, 2) + 3 * a**2 / 4 + 3 * a**4 / 16
    my = a**2 + 21 * a**4 / 16 + 5 * a**6 / 32
    book.exact("comparison L2 moment", mean_square(profile), sp.Rational(1, 2))
    book.exact("comparison gradient moment", mean_square(dx) + mean_square(dy), m2)
    book.exact("comparison Laplacian moment", mean_square(lap), m4)
    book.exact("comparison x-Laplacian derivative", mean_square(sp.diff(lap, x)), m4)
    book.exact("comparison y-Laplacian derivative", mean_square(sp.diff(lap, y)), my)
    book.exact("critical moment interpolation polynomial", 16 * m2**3 - a**2 * m4,
               (a**6 + 12 * a**4 + 40 * a**2 + 32) / 16)
    book.exact("Laplacian source upper polynomial", (1 + a**2)**2 / 2 - m4,
               a**2 / 4 + 5 * a**4 / 16)
    book.exact("y-source upper polynomial", (a + a**3)**2 - my,
               11 * a**4 / 16 + 27 * a**6 / 32)

    phase = A * (1 - sp.exp(-t))
    comparison = profile.subs(a, phase)
    U = A * sp.exp(-nu * t) * sp.sin(y)
    v = sp.Function("v")(x, y, t)
    velocity = sp.Matrix([U, 0, b * v])
    jacobian = velocity.jacobian((x, y, z))
    book.exact("full velocity incompressibility", sp.trace(jacobian), 0)
    book.exact("full pressure Poisson source", sp.trace(jacobian * jacobian), 0)
    convection = jacobian * velocity
    book.check("complete invariant convection",
               sp.simplify(convection - sp.Matrix([0, 0, b * U * sp.diff(v, x)])) == sp.zeros(3, 1))
    book.exact("horizontal unforced heat equation", sp.diff(U, t) - nu * sp.diff(U, y, 2), 0)
    book.exact("comparison exact transport", sp.diff(comparison, t)
               + U.subs(nu, 1) * sp.diff(comparison, x), 0)
    e = sp.Function("e")(x, y, t)
    transport = sp.diff(e, t) + U * sp.diff(e, x) - nu * (sp.diff(e, x, 2) + sp.diff(e, y, 2))
    derivative_transport = sp.diff(e, y, t) + U * sp.diff(e, y, x) - nu * (sp.diff(e, y, x, 2) + sp.diff(e, y, 3))
    book.exact("error y-derivative commutator", sp.diff(transport, y) - derivative_transport,
               sp.diff(U, y) * sp.diff(e, x))

    s = sp.symbols("s", nonnegative=True)
    B0 = (t + A**2 * t**3 / 3) / sp.sqrt(2)
    By = A * t**2 * (sp.Rational(1, 2) + 1 / (2 * sp.sqrt(2))) + A**3 * t**4 * (sp.Rational(1, 4) + 1 / (12 * sp.sqrt(2)))
    book.exact("integrated error L2 source", sp.integrate((1 + A**2 * s**2) / sp.sqrt(2), (s, 0, t)), B0)
    book.exact("integrated error gradient source", sp.integrate(A * s + A**3 * s**3 + A * B0.subs(t, s), (s, 0, t)), By)
    k1 = sp.Rational(1, 2) + 1 / (2 * sp.sqrt(2))
    k3 = sp.Rational(1, 4) + 1 / (12 * sp.sqrt(2))
    replacement = {A: N**3, t: c / N**2}
    book.exact("uniform B0 comparison factor", 4 * c**3 / (3 * sp.sqrt(2)) - B0.subs(replacement, simultaneous=True),
               c * (N**2 * c**2 - 1) / (sp.sqrt(2) * N**2))
    book.exact("uniform By comparison factor", (k1 + k3) * c**4 * N - By.subs(replacement, simultaneous=True),
               k1 * c**2 * (N**2 * c**2 - 1) / N)
    constant = sp.Rational(16, 9) + 8 * (k1 + k3) / (3 * sp.sqrt(2))
    book.exact("uniform critical error constant", constant, sp.Rational(23, 9) + sp.sqrt(2))
    book.check("strict critical error margin", bool(sp.simplify(4 - constant).is_positive), 4 - constant)
    initial = nu**2 * N**6
    book.exact("viscosity-scaled cumulative lower bound", nu**2 * (N**7 / 128 - N**6 / 2),
               initial**sp.Rational(7, 6) / (128 * nu**sp.Rational(1, 3)) - initial / 2)
    book.exact("unit-budget analytic witness N256", sp.Rational(256, 128) - sp.Rational(1, 2), sp.Rational(3, 2))

    field = {}
    transfer.add_real_mode(field, (0, 1, 0), sp.Matrix([-sp.I * A / 2, 0, 0]))
    coefficients = dict(zip(range(-2, 3), (2, -1, 3, 2, -2)))
    for j, value in coefficients.items():
        transfer.add_real_mode(field, (1, j, 0), sp.Matrix([0, 0, -sp.I * b * value / 2]))
    actual_B = transfer.full_leray_B(field)
    expected_B = {}
    for j in range(-3, 4):
        value = -A * (coefficients.get(j - 1, 0) - coefficients.get(j + 1, 0)) / 2
        if value != 0:
            transfer.add_real_mode(expected_B, (1, j, 0), sp.Matrix([0, 0, -sp.I * b * value / 2]))
    book.check("full Leray convolution including generated endpoints",
               all(sp.simplify(actual_B.get(k, sp.zeros(3, 1)) - expected_B.get(k, sp.zeros(3, 1))) == sp.zeros(3, 1)
                   for k in actual_B.keys() | expected_B.keys()))
    telescoped = A * b**2 / 4 * sum((sp.sqrt(1 + j*j) - sp.sqrt(1 + (j+1)**2)) * value * coefficients.get(j+1, 0)
                                   for j, value in coefficients.items())
    book.exact("full critical pairing telescopes", transfer.scalar_F(field), telescoped)
    book.exact("normalized critical Fourier moment", transfer.quadratic_C(field),
               A**2 / 2 + b**2 / 2 * sum(sp.sqrt(1+j*j) * value**2 for j, value in coefficients.items()))
    book.exact("normalized critical dissipation moment", transfer.quadratic_Y(field),
               A**2 / 2 + b**2 / 2 * sum(sp.sqrt(1+j*j)**3 * value**2 for j, value in coefficients.items()))
    translated = {**field, (0, 0, 0): sp.Matrix([2, -3, 5])}
    for name, pairing in (("C", transfer.quadratic_C), ("Y", transfer.quadratic_Y), ("F", transfer.scalar_F)):
        book.exact(f"constant-mean invariance {name}", pairing(translated), pairing(field))
    j = sp.symbols("j", real=True)
    book.exact("frequency-weight Lipschitz bound", 1 - sp.diff(sp.sqrt(1 + j*j), j)**2, 1 / (1 + j*j))
    book.exact("integrated family upper bound", sp.integrate(A * b**2 * sp.exp(-3 * nu * s) / 4, (s, 0, t)),
               A * b**2 * (1 - sp.exp(-3 * nu * t)) / (12 * nu))


def quantities(n, modes, times, coefficients):
    r2 = 1.0 + modes*modes
    r = np.sqrt(r2)
    square = coefficients * coefficients
    passive = np.sum(square, axis=0)
    heat = np.exp(-times / n**2)
    q = n * heat
    F = q / 4 * np.einsum("j,jt,jt->t", r[:-1] - r[1:], coefficients[:-1], coefficients[1:])
    return {"C": (heat*heat + r @ square) / 2,
            "Y": (heat*heat + (r*r2) @ square) / 2,
            "K": (heat*heat + passive) / 4,
            "D": (heat*heat + r2 @ square) / 2, "F": F,
            "passive_L2_squared": passive / 2,
            "boundary_residual": np.abs(q) * np.sqrt(square[0] + square[-1]) / (2 * math.sqrt(2))}


def integrate(n, cutoff, rtol, atol, shear=True):
    modes = np.arange(-cutoff, cutoff + 1)
    r2 = 1.0 + modes*modes
    r = np.sqrt(r2)
    r3 = r*r2
    shear_factor = float(shear)
    delta = r[:-1] - r[1:]
    epsilon = 1 / n**2
    size = len(modes)

    def rhs(s, state):
        coefficients = state[:size]
        square = coefficients * coefficients
        heat = shear_factor * math.exp(-epsilon * s)
        q = n * heat
        derivative = np.empty_like(state)
        derivative[:size] = -epsilon * r2 * coefficients
        derivative[1:size] -= q / 2 * coefficients[:-1]
        derivative[:size-1] += q / 2 * coefficients[1:]
        Y = (heat*heat + np.dot(r3, square)) / 2
        D = (heat*heat + np.dot(r2, square)) / 2
        F = q / 4 * np.dot(delta, coefficients[:-1] * coefficients[1:])
        derivative[size:] = (epsilon * Y, F, max(F - epsilon * Y / 2, 0.0), epsilon * D)
        return derivative

    initial = np.zeros(size + 4)
    initial[cutoff] = 1.0
    solution = solve_ivp(rhs, (0.0, 0.5), initial, method="DOP853", rtol=rtol, atol=atol,
                         max_step=1 / (8 * n), t_eval=TIMES)
    return modes, solution, rhs


def spatial_quantities(n, modes, s, coefficients, coefficient_derivative):
    nx, ny = 8, 4 * int(modes[-1]) + 8
    envelope_hat = np.zeros((2, ny), dtype=complex)
    envelope_hat[0, modes % ny] = ny * coefficients
    envelope_hat[1, modes % ny] = ny * coefficient_derivative
    envelope, envelope_derivative = np.fft.ifft(envelope_hat, axis=1)
    x = np.arange(nx)[:, None] * (2 * np.pi / nx)
    y = np.arange(ny)[None, :] * (2 * np.pi / ny)
    phase = np.exp(1j * x)
    velocity = np.zeros((3, nx, ny))
    velocity[0] = np.exp(-s / n**2) * np.sin(y)
    velocity[2] = np.imag(phase * envelope[None, :])
    temporal = np.zeros_like(velocity)
    temporal[0] = -velocity[0] / n**2
    temporal[2] = np.imag(phase * envelope_derivative[None, :])
    transformed = np.fft.fftn(velocity, axes=(1, 2))
    kx, ky = np.meshgrid(np.fft.fftfreq(nx) * nx, np.fft.fftfreq(ny) * ny, indexing="ij")
    k2 = kx*kx + ky*ky
    radius = np.sqrt(k2)

    def physical(spectrum):
        return np.fft.ifftn(spectrum, axes=(1, 2)).real

    dx = physical(1j * kx * transformed)
    dy = physical(1j * ky * transformed)
    raw_B = -n * (velocity[0] * dx + velocity[1] * dy)
    Bhat = np.fft.fftn(raw_B, axes=(1, 2))
    kdot = kx * Bhat[0] + ky * Bhat[1]
    inverse = np.zeros_like(k2)
    np.divide(1.0, k2, out=inverse, where=k2 != 0)
    Bhat[0] -= kx * inverse * kdot
    Bhat[1] -= ky * inverse * kdot
    projected_B = physical(Bhat)
    momentum_rhs = projected_B - physical(k2 * transformed) / n**2
    momentum_scale = np.maximum(1.0, np.maximum(np.abs(temporal), np.abs(momentum_rhs)))
    Lambda = physical(radius * transformed)
    Lambda3 = physical(radius**3 * transformed)
    average = lambda array: float(np.mean(np.sum(array, axis=0)))
    return {"C": average(velocity * Lambda), "Y": average(velocity * Lambda3),
            "K": average(velocity * velocity) / 2, "D": average(dx*dx + dy*dy),
            "F": average(Lambda * projected_B),
            "divergence": float(np.max(np.abs(dx[0] + dy[1]))),
            "pressure_projection": float(np.max(np.abs(projected_B - raw_B))),
            "momentum_residual": float(np.max(np.abs(temporal - momentum_rhs) / momentum_scale)),
            "odd_phase": float(np.max(np.abs(transformed.real)) / max(1.0, np.max(np.abs(transformed))))}


def comparison_bounds(n):
    t, A = 0.5 / n**2, float(n**3)
    a = A * -math.expm1(-t)
    B0 = (t + A*A*t**3 / 3) / math.sqrt(2)
    By = A*t*t * (0.5 + 1 / (2*math.sqrt(2))) + A**3*t**4 * (0.25 + 1 / (12*math.sqrt(2)))
    reference_lower = (0.5 + a*a / 4)**1.5 / math.sqrt(0.5 + 3*a*a / 4 + 3*a**4 / 16)
    error_squared = B0 * math.hypot(B0, By)
    lower_C = math.exp(-2*t) / 2 + max(math.sqrt(reference_lower) - math.sqrt(error_squared), 0.0)**2
    return {"phase": a, "B0": B0, "By": By, "critical_error_squared_bound": error_squared,
            "C_lower_comparison": lower_C, "C_lower_uniform": n / 64,
            "W_lower_uniform": n / 128 - 0.5, "W_lower_comparison": max((lower_C - 1) / 2, 0.0),
            "W_upper_family": A * -math.expm1(-3*t) / 12,
            "W_upper_short_time": n / 8}


def compute(book, result, arrays, errors):
    analytical_controls(book)
    rows = result["trajectory_rows"] = []
    spatial_rows = result["spatial_rows"] = []
    for n in PARAMETERS:
        runs = []
        for label, cutoff, rtol, atol in (("coarse", max(32, 2*n), 1e-11, 1e-13),
                                          ("fine", max(48, 3*n), 1e-13, 1e-15)):
            modes, solution, rhs = integrate(n, cutoff, rtol, atol)
            prefix = f"N{n}_{label}"
            arrays[prefix + "_modes"] = modes
            arrays[prefix + "_times"] = solution.t
            arrays[prefix + "_state"] = solution.y
            book.check(prefix + " integration", solution.success and len(solution.t) == len(TIMES), solution.message)
            if not solution.success or len(solution.t) != len(TIMES):
                raise RuntimeError(f"Incomplete {prefix} trajectory: {solution.message}")
            size = len(modes)
            values = quantities(n, modes, TIMES, solution.y[:size])
            JY, JF, W, JD = solution.y[size:]
            book.check(prefix + " finite states", np.isfinite(solution.y).all())
            numerical_check(book, errors, prefix + " critical balance", values["C"] + 2*JY, 1 + 2*JF)
            numerical_check(book, errors, prefix + " kinetic balance", values["K"] + JD, 0.5)
            numerical_check(book, errors, prefix + " passive decay bound",
                            np.maximum(values["passive_L2_squared"] - 0.5*np.exp(-2*TIMES/n**2), 0), 0)
            numerical_check(book, errors, prefix + " generated endpoint residual", values["boundary_residual"], 0)
            numerical_check(book, errors, prefix + " cumulative half-margin bound",
                            np.maximum(values["C"] + JY - 1 - 2*W, 0), 0)
            numerical_check(book, errors, prefix + " family upper bound",
                            np.maximum(W - n**3 * -np.expm1(-3*TIMES/n**2) / 12, 0), 0)
            runs.append((modes, solution, values, rhs))
        coarse_modes, coarse_solution, coarse, _ = runs[0]
        modes, solution, fine, rhs = runs[1]
        offset = int(modes[-1] - coarse_modes[-1])
        numerical_check(book, errors, f"N{n} coefficient convergence", coarse_solution.y[:len(coarse_modes)],
                        solution.y[offset:offset+len(coarse_modes)])
        for key in ("C", "Y", "K", "D", "F"):
            numerical_check(book, errors, f"N{n} {key} convergence", coarse[key], fine[key])
        numerical_check(book, errors, f"N{n} accumulated budget convergence", coarse_solution.y[-4:], solution.y[-4:])
        for index in SPATIAL_INDICES:
            derivative = rhs(TIMES[index], solution.y[:, index])[:len(modes)]
            spatial = spatial_quantities(n, modes, TIMES[index], solution.y[:len(modes), index], derivative)
            discrepancies = {}
            for key in ("C", "Y", "K", "D", "F"):
                discrepancies[key] = numerical_check(book, errors, f"N{n} s={TIMES[index]:g} spatial {key}",
                                                      spatial[key], fine[key][index])
            for key in ("divergence", "pressure_projection", "momentum_residual", "odd_phase"):
                discrepancies[key] = numerical_check(book, errors, f"N{n} s={TIMES[index]:g} {key}", spatial[key], 0)
            spatial_rows.append({"N": n, "scaled_time": float(TIMES[index]), "values": spatial, "errors": discrepancies})
        bounds = comparison_bounds(n)
        final_W = float(solution.y[-2, -1])
        numerical_check(book, errors, f"N{n} continuum C lower bound", max(bounds["C_lower_uniform"] - fine["C"][-1], 0), 0)
        numerical_check(book, errors, f"N{n} comparison C lower bound", max(bounds["C_lower_comparison"] - fine["C"][-1], 0), 0)
        numerical_check(book, errors, f"N{n} continuum W lower bound", max(bounds["W_lower_uniform"] - final_W, 0), 0)
        row = {"N": n, "viscosity": 1, "velocity_amplitude": n**3, "physical_time": 0.5/n**2,
               "initial_C": n**6, "final_C_over_initial_C": float(fine["C"][-1]),
               "W_over_initial_C": final_W, "integrated_Y_over_initial_C": float(solution.y[-4, -1]),
               "integrated_F_over_initial_C": float(solution.y[-3, -1]), "bounds_over_initial_C": bounds,
               "coarse_cutoff": int(coarse_modes[-1]), "fine_cutoff": int(modes[-1]),
               "coarse_function_evaluations": coarse_solution.nfev, "fine_function_evaluations": solution.nfev}
        rows.append(row)
        print("TRAJECTORY " + json.dumps(row, sort_keys=True))

    modes, heat, _ = integrate(2, 48, 1e-13, 1e-15, shear=False)
    arrays["heat_modes"], arrays["heat_times"], arrays["heat_state"] = modes, heat.t, heat.y
    book.check("zero-shear control integration", heat.success and len(heat.t) == len(TIMES), heat.message)
    if not heat.success or len(heat.t) != len(TIMES):
        raise RuntimeError("Incomplete zero-shear control")
    expected = np.zeros_like(heat.y)
    expected[48] = np.exp(-TIMES / 4)
    expected[-4] = -np.expm1(-TIMES / 2) / 4
    expected[-1] = expected[-4]
    numerical_check(book, errors, "zero-shear exact heat solution and budgets", heat.y, expected)
    return not book.failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    output = parser.parse_args().output.resolve()
    manifest_path, snapshot_dir = output.with_suffix(".inputs.json"), output.with_suffix(".sources")
    trajectory_path = output.with_suffix(".trajectories.npz")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir, trajectory_path)):
        raise FileExistsError(f"Use a fresh output path; existing evidence is immutable: {output}")
    sources = {"protocol": PROTOCOL, "script": Path(__file__).resolve(),
               "depletion": Path(depletion.__file__).resolve(), "transfer": Path(transfer.__file__).resolve()}
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(payloads[key]).hexdigest()}
                  for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[key])
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "identities": identities,
                "numpy_version": np.__version__, "sympy_version": sp.__version__, "scipy_version": scipy.__version__}
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    book, arrays, errors = depletion.DepletionReceipt(), {}, []
    result = {"schema": "cassi.navier-stokes.mixing-budget.verification.v1", **manifest,
              "scope": "Unforced periodic invariant-class NS trajectories and exact analytical controls. "
                       "Numerical approximations have resolution checks; continuum bounds have a separate analytical proof. "
                       "General nonlinear data-controlled closure and arbitrary-data regularity remain UNRESOLVED.",
              "checks": book.checks, "failures": book.failures}
    success = False
    try:
        success = compute(book, result, arrays, errors)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
        result["status"] = "PASS" if success else "FAIL"
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    if arrays:
        with trajectory_path.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        result["trajectories"] = {"path": trajectory_path.relative_to(ROOT).as_posix(),
                                  "sha256": hashlib.sha256(trajectory_path.read_bytes()).hexdigest()}
    result.update(check_count=len(book.checks), numerical_errors=errors,
                  max_numerical_discrepancy=max((row["error"] for row in errors), default=0.0))
    witness = next((row for row in result.get("trajectory_rows", []) if row["N"] == 256), None)
    result["control_classifications"] = {
        "numerical_reduction": "PASS" if success and result["status"] == "PASS" else "FAIL",
        "unit_initial_critical_budget": "CONTRADICTS" if success and result["status"] == "PASS" and witness
            and witness["W_over_initial_C"] > 1 and witness["bounds_over_initial_C"]["W_lower_uniform"] > 1 else "INCONCLUSIVE"}
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
