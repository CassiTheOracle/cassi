#!/usr/bin/env python3
"""Verify the preregistered Cassi fluid reductions and actual native solver controls.

Run from CassiTheory. Existing receipts, source snapshots and arrays are refused.
The momentum obstruction and conditional NS benchmarks qualify separate claims.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sympy as sp
import torch

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/cassi-fluid-feasibility-prereg.md"
SOLVER = ROOT / "two-fluid/cassi_two_fluid_3d_gpu.py"
DEFAULT_OUTPUT = ROOT / "runs/cassi_fluid_feasibility/verification.json"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
NU = 0.2


class Receipt:
    def __init__(self, result):
        self.result = result
        self.checks = result.setdefault("checks", {})
        self.arrays = {}

    def check(self, name, passed, evidence=None):
        if name in self.checks:
            raise ValueError(f"Duplicate check: {name}")
        self.checks[name] = dict(passed=bool(passed), evidence=evidence)
        print(f"{'PASS' if passed else 'FAIL'} {name}: {evidence}", flush=True)

    def exact(self, name, actual, expected=0):
        residual = sp.simplify(actual - expected)
        self.check(name, residual == 0, str(residual))

    def near(self, name, actual, expected, tolerance=1e-10):
        actual, expected = np.asarray(actual), np.asarray(expected)
        finite = bool(np.isfinite(actual).all() and np.isfinite(expected).all())
        error = float(np.max(np.abs(actual - expected)) / max(1.0, float(np.max(np.abs(expected))))) if finite else None
        self.check(name, finite and error <= tolerance, dict(error=error, tolerance=tolerance))
        return error


def algebra(book):
    Y, I, lr, lp, n0, m, h, k, n = sp.symbols("Y I lambda_rho lambda_phi n0 m hbar k n", positive=True)
    p = (1 + sp.sqrt(5)) / 2
    rho, eps = Y + I, Y - p * I
    potential = lr * (rho - n0)**2 / 4 + lp * eps**2 / 2
    mu = sp.Matrix([sp.diff(potential, a) for a in (Y, I)])
    pressure = Y * mu[0] + I * mu[1] - potential
    book.exact("algebra.pressure", pressure, lr * (rho**2 - n0**2) / 4 + lp * eps**2 / 2)
    for a in (Y, I):
        book.exact(f"algebra.gibbs_duhem.{a}", sp.diff(pressure, a), Y * sp.diff(mu[0], a) + I * sp.diff(mu[1], a))
    H = sp.hessian(potential, (Y, I))
    book.exact("algebra.hessian_first_minor", H[0, 0], lr / 2 + lp)
    book.exact("algebra.hessian_determinant", H.det(), lr * lp * (1 + p)**2 / 2)
    x = sp.symbols("x y z", real=True)
    R = sp.Function("R")(*x)
    lapR = sum(sp.diff(R, a, 2) for a in x)
    Q = -h**2 * lapR / (2 * m * R)
    Tq = sp.Matrix(3, 3, lambda i, j: h**2 / (2*m) * (sp.diff(R, x[i])*sp.diff(R, x[j]) - R*sp.diff(R, x[i], x[j])))
    for i in range(3):
        book.exact(f"algebra.quantum_divergence.{i}", sum(sp.diff(Tq[i, j], x[j]) for j in range(3)), R**2 * sp.diff(Q, x[i]))
        for j in range(3):
            density_form = h**2/(4*m) * (sp.diff(R**2, x[i])*sp.diff(R**2, x[j])/R**2 - sp.diff(R**2, x[i], x[j]))
            book.exact(f"algebra.quantum_density_form.{i}.{j}", Tq[i, j], density_form)
    vy = sp.Matrix(sp.symbols("vy0:3", real=True))
    vi = sp.Matrix(sp.symbols("vi0:3", real=True))
    u, w = (Y*vy + I*vi)/rho, vy-vi
    cf = m*Y*I/rho
    book.exact("algebra.kinetic_split", m*(Y*vy.dot(vy)+I*vi.dot(vi))/2, m*rho*u.dot(u)/2+cf*w.dot(w)/2)
    for i in range(3):
        for j in range(3):
            book.exact(f"algebra.momentum_split.{i}.{j}", m*(Y*vy[i]*vy[j]+I*vi[i]*vi[j]), m*rho*u[i]*u[j]+cf*w[i]*w[j])
    branch = {Y: p*n/(1+p), I: n/(1+p)}
    book.exact("algebra.golden_relative_mu", (mu[0]-mu[1]).subs(branch))
    book.exact("algebra.golden_pressure", pressure.subs(branch), lr*(n**2-n0**2)/4)
    book.exact("algebra.golden_counterflow_mass", cf.subs(branch), m*n/p**3)
    fractions = sp.Matrix([p/(1+p), 1/(1+p)])
    mode_matrix = k**2/m * sp.diag(branch[Y], branch[I])*H + h**2*k**4/(4*m**2)*sp.eye(2)
    omega2 = n*lr*k**2/(2*m) + h**2*k**4/(4*m**2)
    for i in range(2):
        book.exact(f"algebra.longitudinal_dispersion.{i}", (mode_matrix*fractions)[i], omega2*fractions[i])
    phase = sp.Function("theta")(*x)
    book.exact("algebra.common_phase_curl", sp.diff(phase, x[0], x[1])-sp.diff(phase, x[1], x[0]))
    ar, ai, br, bi = sp.symbols("ar ai br bi", real=True)
    psi = sp.Matrix([ar+sp.I*ai, br+sp.I*bi])
    pauli = (sp.Matrix([[0, 1], [1, 0]]), sp.Matrix([[0, -sp.I], [sp.I, 0]]), sp.diag(1, -1))
    book.exact("algebra.pauli_gauss_source", sum((sp.conjugate(psi).T*s*psi)[0]**2 for s in pauli), (sp.conjugate(psi).T*psi)[0]**2)
    kap, ref = sp.symbols("kappa I_ref", positive=True)
    ry, ri = -kap*eps, kap*eps
    book.exact("algebra.conversion_sum", ry+ri)
    book.exact("algebra.imbalance_decay", ry-p*ri, -(1+p)*kap*eps)
    book.exact("algebra.reaction_Y_boundary", ry.subs(Y, 0), kap*p*I)
    book.exact("algebra.reaction_I_boundary", ri.subs(I, 0), kap*Y)
    book.exact("algebra.imbalance_dissipation", eps*(ry-p*ri), -(1+p)*kap*eps**2)
    entropy = Y*sp.log(Y/(p*ref))-Y+p*ref+I*sp.log(I/ref)-I+ref
    production = sp.diff(entropy, Y)*ry+sp.diff(entropy, I)*ri
    book.exact("algebra.relative_entropy_reaction", sp.expand_log(production + kap*eps*sp.log(Y/(p*I)), force=True))
    book.exact("algebra.entropy_diffusion_Y", sp.diff(entropy, Y, 2), 1/Y)
    book.exact("algebra.entropy_diffusion_I", sp.diff(entropy, I, 2), 1/I)
    e, r, c = sp.symbols("e rho c", positive=True)
    primitive = sp.log(e)+r**2/c*(sp.log(e)-sp.log(c+e**2)/2)
    book.exact("algebra.gated_reaction_primitive", sp.diff(primitive, e), (r**2+c+e**2)/(e*(c+e**2)))
    b, t, boost = sp.symbols("b t boost", real=True)
    qx = x[0]-boost*t-b*t**2/4
    density, imbalance, speed = 4+sp.cos(qx), b*sp.sin(qx), boost+b*t/2
    book.exact("algebra.native_density_translation", sp.diff(density, t)+speed*sp.diff(density, x[0]))
    book.exact("algebra.native_imbalance_translation", sp.diff(imbalance, t)+speed*sp.diff(imbalance, x[0]))
    book.exact("algebra.native_force_mean", sp.integrate(b*sp.sin(x[0])**2, (x[0], 0, 2*sp.pi))/(2*sp.pi), b/2)
    book.exact("algebra.native_acceleration", sp.diff(speed, t), b/2)
    book.result["analytical_scope"] = {
        "stress": "Ungauged three-dimensional positive-density first-order matter reduction; K_x=hbar^2/m is supplied.",
        "entropy": "Relative entropy is a scalar mathematical Lyapunov functional; physical temperature and thermodynamic identification are absent.",
        "positivity": "Continuum comparison under smooth common incompressible advection, equal nonnegative diffusion and nonnegative reaction rate; no spectral positivity theorem.",
        "common_phase": "Golden composition and common phase together define a compatible branch; arbitrary initial data need not enter it.",
        "missing": ["derived positive viscosity", "material normalization and equation of state", "closed native internal force", "rotational hydrodynamic limit", "physical entropy and heat transport"],
    }
    xx, yy, zz = x
    tgv = sp.Matrix([sp.sin(xx)*sp.cos(yy)*sp.cos(zz), -sp.cos(xx)*sp.sin(yy)*sp.cos(zz), 0])
    grad = tgv.jacobian(x)
    omega = sp.Matrix([grad[2, 1]-grad[1, 2], grad[0, 2]-grad[2, 0], grad[1, 0]-grad[0, 1]])
    stretch = (omega.T*(grad+grad.T)*omega)[0]/2
    stretch_form = sp.cos(xx)*sp.cos(yy)*sp.cos(zz)*sp.sin(zz)**2*(sp.cos(xx)**2*sp.sin(yy)**2-sp.sin(xx)**2*sp.cos(yy)**2)
    book.exact("algebra.tgv_stretching_density", stretch, stretch_form)
    book.exact("algebra.tgv_mean_stretching", sp.integrate(stretch_form, (xx, 0, 2*sp.pi)))


def load_solver():
    spec = importlib.util.spec_from_file_location("cassi_fluid_native", SOLVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model(native, N, *, expanding=False, gate=False, lam=0.0, forced=False):
    settings = dict(N=N, L=2*math.pi, nu=NU, D=0.0, lam=lam, chi=0.0, alpha_disp=None, rho_ext=None, device="cpu")
    if expanding:
        obj = native.ExpandingTwoFluid3DGPU(**settings, H0=0.0, a0=1.0, hubble_mode="friedmann", hyper_nu=0.0, cs2=0.0, qi_gate=gate, phi_inv2=PHI**-2, qi_memory=False, wu_xing=False)
        obj.gate_model = "single"
        return obj
    if forced:
        class PrescribedShearForce(native.TwoFluid3DGPU):
            """Add only the frozen external shear force at every native RHS stage."""
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.external_hat = torch.fft.fftn(0.1*torch.sin(self.Y))

            def rhs(self, u_hat, ey_hat, ei_hat):
                du, dy, di = super().rhs(u_hat, ey_hat, ei_hat)
                du[0] = du[0] + self.external_hat
                return du, dy, di
        return PrescribedShearForce(**settings)
    return native.TwoFluid3DGPU(**settings)


def make_state(obj, velocity, Y, I):
    zeros = torch.zeros_like(obj.Z)
    u = [torch.fft.fftn(zeros+a) for a in velocity]
    return u, torch.fft.fftn(zeros+Y), torch.fft.fftn(zeros+I)


def real_state(state):
    u, Y, I = state
    return np.stack([torch.fft.ifftn(a).real.numpy() for a in u]), torch.fft.ifftn(Y).real.numpy(), torch.fft.ifftn(I).real.numpy()


def diagnostics(obj, state, time):
    uh, yh, ih = state
    volume = obj.N**3
    norm = volume**2
    K = float(sum(torch.sum(torch.abs(a)**2) for a in uh)/(2*norm))
    E = float(sum(torch.sum(obj.k2*torch.abs(a)**2) for a in uh)/(2*norm))
    divh = 1j*sum(k*a for k, a in zip((obj.kx, obj.ky, obj.kz), uh))
    div = float(torch.max(torch.abs(torch.fft.ifftn(divh))))
    y, i = torch.fft.ifftn(yh).real, torch.fft.ifftn(ih).real
    power = 0.0
    if hasattr(obj, "external_hat"):
        power = float(torch.sum(torch.real(torch.conj(uh[0])*obj.external_hat))/norm)
    return [time, K, E, div, *[float(a[0, 0, 0].real/volume) for a in uh], float(y.mean()), float(i.mean()), float(y.min()), float(i.min()), 2*NU*E, power]


def evolve(book, name, obj, initial, T, dt):
    steps = int(round(T/dt))
    if not math.isclose(steps*dt, T, rel_tol=0.0, abs_tol=1e-14):
        raise ValueError("The frozen endpoint must be exactly partitioned")
    state = initial
    hist = [diagnostics(obj, state, 0.0)]
    for j in range(steps):
        state = obj.rk2_step(*state, dt)
        hist.append(diagnostics(obj, state, (j+1)*dt))
    hist = np.asarray(hist)
    u, Y, I = real_state(state)
    book.arrays[f"{name}.history"] = hist
    book.arrays[f"{name}.u"] = u
    book.arrays[f"{name}.Y"] = Y
    book.arrays[f"{name}.I"] = I
    defect = hist[-1, 1]-hist[0, 1]+float(np.trapezoid(hist[:, 11]-hist[:, 12], hist[:, 0]))
    row = dict(N=obj.N, T=T, dt=dt, steps=steps, energy_initial=float(hist[0, 1]), energy_final=float(hist[-1, 1]), enstrophy_final=float(hist[-1, 2]), divergence_max=float(hist[:, 3].max()), mean_velocity=hist[-1, 4:7].tolist(), minimum_Y=float(hist[:, 9].min()), minimum_I=float(hist[:, 10].min()), viscous_external_energy_defect=defect, density_sum_drift=float(np.max(np.abs(hist[:, 7]+hist[:, 8]-hist[0, 7]-hist[0, 8]))))
    book.result.setdefault("trajectories", {})[name] = row
    book.check(f"{name}.finite", np.isfinite(hist).all() and np.isfinite(u).all() and np.isfinite(Y).all() and np.isfinite(I).all())
    book.near(f"{name}.divergence", hist[:, 3], 0.0)
    book.near(f"{name}.density_sum", hist[:, 7]+hist[:, 8], hist[0, 7]+hist[0, 8])
    return state, row


def reaction_reference(Y, I, t, gated):
    rho, e0 = Y+I, Y-PHI*I
    if not gated:
        e = e0*math.exp(-0.3*(1+PHI)*t)
    else:
        c = PHI**-2
        lo, hi = 0.0, abs(e0)
        for _ in range(90):
            mid = (lo+hi)/2
            elapsed = (math.log(abs(e0)/mid)+rho*rho/c*math.log((abs(e0)/math.sqrt(c+e0*e0))/(mid/math.sqrt(c+mid*mid))))/(0.3*(1+PHI))
            if elapsed > t:
                lo = mid
            else:
                hi = mid
        e = math.copysign((lo+hi)/2, e0)
    return (PHI*rho+e)/(1+PHI), (rho-e)/(1+PHI)


def reaction_controls(book, native):
    for label, expanding, gate in (("base", False, False), ("expanding_ungated", True, False), ("expanding_gated", True, True)):
        for Y, I in ((2.0, 1.0), (1.0, 2.0), (0.0, 1.0), (1.0, 0.0)):
            obj = model(native, 8, expanding=expanding, gate=gate, lam=0.3)
            state = make_state(obj, (0, 0, 0), Y, I)
            du, dy, di = real_state(obj.rhs(*state))
            q = (Y+I)**2/((Y+I)**2+PHI**-2+(Y-PHI*I)**2)
            conv = 0.3*(1-q if gate else 1)*(Y-PHI*I)
            tag = f"reaction_rhs.{label}.{Y:g}_{I:g}"
            book.near(tag+".Y", dy, -conv)
            book.near(tag+".I", di, conv)
            book.near(tag+".velocity", du, 0.0)
    for label, gated in (("base", False), ("expanding_gated", True)):
        for Y, I in ((2.0, 1.0), (1.0, 2.0)):
            errors = []
            for dt in (0.004, 0.002):
                obj = model(native, 8, expanding=gated, gate=gated, lam=0.3)
                name = f"reaction.{label}.{Y:g}_{I:g}.dt{dt}"
                final, row = evolve(book, name, obj, make_state(obj, (0, 0, 0), Y, I), 0.2, dt)
                _, actualY, actualI = real_state(final)
                reference = reaction_reference(Y, I, 0.2, gated)
                err = book.near(name+".endpoint", [actualY.mean(), actualI.mean()], reference, 2e-6)
                errors.append(err)
                row.update(endpoint_error=err, reference=list(reference), qi_gate=gated, gate_model="single" if gated else None, qi_memory=False, phi_inv2=PHI**-2 if gated else None, lam=0.3)
            if errors[0] > 1e-10:
                book.check(f"reaction.{label}.{Y:g}_{I:g}.refinement", errors[1] <= errors[0]/3, dict(coarse=errors[0], fine=errors[1]))
    for expanding in (False, True):
        obj = model(native, 8, expanding=expanding)
        u, Y, I = real_state(obj.rk2_step(*make_state(obj, (0, 0, 0), 1e-4, 1.0), 0.01))
        factor = 1.0001/1.001
        expected = (0.001*factor, factor) if expanding else (1e-4, 1.0)
        name = f"floor_control.{expanding}"
        book.near(name, [Y.mean(), I.mean()], expected)
        book.result.setdefault("floor_control", {})[str(expanding)] = dict(final_Y=float(Y.mean()), final_I=float(I.mean()), delta_Y=float(Y.mean()-1e-4), density_sum=float((Y+I).mean()), classification="discrete_intervention" if expanding else "stationary_continuum_control")


def force_controls(book, native):
    quadrature_x = np.arange(16384)*2*math.pi/16384
    s = np.sin(quadrature_x)
    attenuated_mean = float(np.mean(s**6/(s**4+0.2**2+1e-10)))
    rows = book.result.setdefault("force_controls", [])
    for N in (16, 24):
        for b in (-1, 1):
            for boost in (0, 1):
                obj = model(native, N)
                rho, pi = 4+torch.cos(obj.Z), b*torch.sin(obj.Z)
                state = make_state(obj, (boost, 0, 0), (rho+pi)/2, (rho-pi)/2)
                du, dy, di = real_state(obj.rhs(*state))
                name = f"native_force.N{N}.b{b}.boost{boost}"
                expected_u = np.zeros_like(du)
                expected_u[0] = b/2
                book.near(name+".projected_force", du, expected_u)
                dxY = (-torch.sin(obj.Z)+b*torch.cos(obj.Z))/2
                dxI = (-torch.sin(obj.Z)-b*torch.cos(obj.Z))/2
                book.near(name+".density_translation", [dy, di], [-boost*dxY.numpy(), -boost*dxI.numpy()])
                work = float(boost*np.mean(du[0]))
                book.near(name+".kinetic_work", work, boost*b/2)
                rows.append(dict(N=N, b=b, boost=boost, mean_force=np.mean(du, axis=(1, 2, 3)).tolist(), kinetic_work=work))
            obj = model(native, N, expanding=True)
            rho, pi = 4+torch.cos(obj.Z), b*torch.sin(obj.Z)
            du, _, _ = real_state(obj.rhs(*make_state(obj, (0, 0, 0), (rho+pi)/2, (rho-pi)/2)))
            mean = np.mean(du, axis=(1, 2, 3))
            book.near(f"attenuated_force.N{N}.b{b}", mean, [b*attenuated_mean, 0, 0], 1e-2)
            rows.append(dict(N=N, b=b, expanding=True, mean_force=mean.tolist(), independent_mean=b*attenuated_mean))
        errors = []
        for dt in (0.004, 0.002):
            obj = model(native, N)
            rho, pi = 4+torch.cos(obj.Z), torch.sin(obj.Z)
            name = f"self_acceleration.N{N}.dt{dt}"
            final, row = evolve(book, name, obj, make_state(obj, (0, 0, 0), (rho+pi)/2, (rho-pi)/2), 0.2, dt)
            u, Y, I = real_state(final)
            xx = obj.Z.numpy()-0.2**2/4
            expected = np.zeros_like(u)
            expected[0] = 0.1
            err = book.near(name+".velocity", u, expected, 2e-6)
            book.near(name+".rho", Y+I, 4+np.cos(xx), 2e-6)
            book.near(name+".pi", Y-I, np.sin(xx), 2e-6)
            row.update(velocity_error=err, expected_mean_velocity=[0.1, 0, 0], energy_scope="native self-force supplies energy; viscous/external-only defect is expected nonzero")
            errors.append(err)
    book.result["force_classification"] = "CONTRADICTS" if all(book.checks[f"native_force.N{N}.b{b}.boost{v}.projected_force"]["passed"] for N in (16, 24) for b in (-1, 1) for v in (0, 1)) else "INCONCLUSIVE"


def numpy_reference(N):
    x = np.arange(N)*2*math.pi/N
    z, y, x = np.meshgrid(x, x, x, indexing="ij")
    initial = np.stack((np.sin(x)*np.cos(y)*np.cos(z), -np.cos(x)*np.sin(y)*np.cos(z), np.zeros_like(x)))
    wave = np.fft.fftfreq(N, 1/N)
    kz, ky, kx = np.meshgrid(wave, wave, wave, indexing="ij")
    ks = np.stack((kx, ky, kz))
    k2 = np.sum(ks*ks, axis=0)
    safe = np.where(k2 == 0, 1.0, k2)
    mask = np.all(np.abs(ks) < N/3, axis=0)

    def rhs(uh):
        u = np.fft.ifftn(uh, axes=(-3, -2, -1)).real
        adv = np.empty_like(u)
        for i in range(3):
            grad = np.fft.ifftn(1j*ks*uh[i], axes=(-3, -2, -1)).real
            adv[i] = np.sum(u*grad, axis=0)
        r = (-np.fft.fftn(adv, axes=(-3, -2, -1))-NU*k2*uh)*mask
        return r - ks*(np.sum(ks*r, axis=0)/safe)

    uh = np.fft.fftn(initial, axes=(-3, -2, -1))
    dt = 0.00025
    for _ in range(200):
        a = rhs(uh)
        b = rhs(uh+dt*a/2)
        c = rhs(uh+dt*b/2)
        d = rhs(uh+dt*c)
        uh += dt*(a+2*b+2*c+d)/6
    final = np.fft.ifftn(uh, axes=(-3, -2, -1)).real
    return initial, final, dict(energy=float(np.sum(np.abs(uh)**2)/(2*N**6)), enstrophy=float(np.sum(k2*np.abs(uh)**2)/(2*N**6)))


def flow_controls(book, native):
    for N in (16, 24):
        for kind in ("shear", "taylor_green_2d", "forced_shear"):
            errors = []
            for dt in (0.004, 0.002):
                obj = model(native, N, forced=kind == "forced_shear")
                zeros = torch.zeros_like(obj.Z)
                initial = (torch.sin(obj.Y), zeros, zeros)
                if kind == "taylor_green_2d":
                    initial = (torch.sin(obj.Z)*torch.cos(obj.Y), -torch.cos(obj.Z)*torch.sin(obj.Y), zeros)
                elif kind == "forced_shear":
                    initial = (zeros, zeros, zeros)
                name = f"flow.{kind}.N{N}.dt{dt}"
                final, row = evolve(book, name, obj, make_state(obj, initial, PHI, 1), 0.2, dt)
                u, _, _ = real_state(final)
                if kind == "forced_shear":
                    expected = np.zeros_like(u)
                    expected[0] = 0.1/NU*(1-math.exp(-NU*0.2))*torch.sin(obj.Y).numpy()
                else:
                    decay = math.exp(-NU*0.2*(2 if kind == "taylor_green_2d" else 1))
                    expected = np.stack([a.numpy()*decay for a in initial])
                err = book.near(name+".endpoint", u, expected, 2e-6)
                row.update(endpoint_error=err, lam=0.0, D=0.0, chi=0.0, nu=NU, forcing="prescribed_shear" if kind == "forced_shear" else "none")
                errors.append(err)
            if errors[0] > 1e-10:
                book.check(f"flow.{kind}.N{N}.refinement", errors[1] <= errors[0]/3, dict(coarse=errors[0], fine=errors[1]))
    fine = {}
    reference_rows = {}
    for N in (16, 24):
        initial, reference, ref_stats = numpy_reference(N)
        book.arrays[f"reference.taylor_green_3d.N{N}.u"] = reference
        reference_rows[str(N)] = dict(N=N, dt=0.00025, steps=200, **ref_stats)
        errors = []
        for dt in (0.002, 0.001):
            obj = model(native, N)
            init = tuple(torch.from_numpy(initial[i].copy()) for i in range(3))
            name = f"flow.taylor_green_3d.N{N}.dt{dt}"
            final, row = evolve(book, name, obj, make_state(obj, init, PHI, 1), 0.05, dt)
            u, _, _ = real_state(final)
            err = book.near(name+".independent_reference", u, reference, 2e-5)
            errors.append(err)
            row.update(endpoint_error=err, velocity_change=float(np.max(np.abs(u-initial))), vertical_velocity_max=float(np.max(np.abs(u[2]))), energy_reference=ref_stats["energy"], enstrophy_reference=ref_stats["enstrophy"])
            if dt == 0.001:
                fine[N] = u
        if errors[0] > 1e-10:
            book.check(f"flow.taylor_green_3d.N{N}.refinement", errors[1] < errors[0], dict(coarse=errors[0], fine=errors[1]))
    book.result["independent_reference"] = reference_rows
    book.result["cross_grid_shared_samples"] = dict(N_shared=8, max_velocity_difference=float(np.max(np.abs(fine[16][:, ::2, ::2, ::2]-fine[24][:, ::3, ::3, ::3]))), scope="Recorded short-time comparison; no continuum convergence theorem")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    arrays_path = output.with_suffix(".trajectories.npz")
    if any(p.exists() for p in (output, manifest_path, snapshot_dir, arrays_path)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = {"protocol": PROTOCOL, "verifier": Path(__file__).resolve(), "solver": SOLVER}
    for name, rel in {
        "first_order_action": "foundations/interscale-current-soliton.md",
        "temporal_completion": "foundations/particle-stationary-action-closure.md",
        "stress_boundary": "foundations/interscale-stress-attenuation-boundary.md",
        "canonical_density": "foundations/cassi-theory-reference.md",
    }.items():
        sources[name] = ROOT/rel
    payloads = {name: path.read_bytes() for name, path in sources.items()}
    identities = {name: dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(payloads[name]).hexdigest()) for name, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for name, path in sources.items():
        (snapshot_dir/path.name).write_bytes(payloads[name])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), identities=identities, python=platform.python_version(), numpy=np.__version__, sympy=sp.__version__, torch=torch.__version__, device="cpu", floating_dtype="float64", complex_dtype="complex128", torch_threads=1)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
    result = dict(schema="cassi.fluid-feasibility.verification.v1", **manifest)
    book = Receipt(result)
    try:
        torch.set_default_dtype(torch.float64)
        torch.set_num_threads(1)
        algebra(book)
        native = load_solver()
        reaction_controls(book, native)
        force_controls(book, native)
        flow_controls(book, native)
        result["history_columns"] = ["time", "kinetic_energy", "enstrophy", "divergence_max", "mean_u_x", "mean_u_y", "mean_u_z", "mean_Y", "mean_I", "minimum_Y", "minimum_I", "viscous_dissipation", "external_power"]
        with arrays_path.open("xb") as stream:
            np.savez_compressed(stream, **book.arrays)
        result["raw_arrays"] = dict(path=arrays_path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(arrays_path.read_bytes()).hexdigest(), keys=sorted(book.arrays))
        if any(path.read_bytes() != payloads[name] for name, path in sources.items()):
            raise RuntimeError("A frozen input changed during execution")
        result["status"] = "PASS" if book.checks and all(row["passed"] for row in book.checks.values()) else "FAIL"
        result["promotion"] = "REJECT"
        result["promotion_scope"] = "Supplied sectors do not constitute a derived closed positive-viscosity ordinary-fluid replacement; future completions remain open."
        result["concentration_arrest"] = "NOT_RUN"
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
        if book.arrays and not arrays_path.exists():
            with arrays_path.open("xb") as stream:
                np.savez_compressed(stream, **book.arrays)
    result["check_count"] = len(book.checks)
    result["failed_checks"] = [name for name, row in book.checks.items() if not row["passed"]]
    result["trajectory_count"] = len(result.get("trajectories", {}))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in ("status", "check_count", "failed_checks", "trajectory_count", "force_classification", "promotion", "concentration_arrest", "error")}, indent=2))
    if result["status"] == "PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
