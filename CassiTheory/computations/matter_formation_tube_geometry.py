#!/usr/bin/env python3
"""Transverse structure of the trapped carrier tube and its response to bending and twist.

Run from the repository root:
    python computations/matter_formation_tube_geometry.py --output-dir runs/tube_geometry

The registered continuum functional (unchanged coefficients, see
``computations/matter_formation_continuum_minimizer.py`` and report
§35.1/§35.2/§36.2/§36.3) is

    E = int [ (1/2)|grad f|^2 + (k_Cx/2)|grad c|^2 + (u_rho/4)(f^2-1)^2
              + (B - h + h f^2)|c|^2 + (u_C/2)|c|^4 ]

with charge N = int |c|^2, k_Cx = u_C = 1, u_rho = 4, B = e_C + 1/(4a) = 19/4
and h = h_C = 2.9598260763447164.  The coefficients a = 1/16 and c_psi = 1/8
are the time-kinetic coefficients of carrier and mediator (report §35.1:
L = (c_psi/2) fdot^2 - (1/2)|grad f|^2 + a|zdot|^2 - (k_Cx/2)|grad z|^2 - V);
they normalize mode masses and do not enter the static energy.

The charge-constrained problem is the reduced functional of report §36.2,

    I(Q) = inf [G + int V + Q^2/(4aN)],   N = int c^2.

For a tube with static energy per unit length E(n), population density n and
signed-charge density q, the reduced energy per unit length is
E(n) + q^2/(4an).  Its deficit from the dilute-cloud threshold
Omega_inf*q is minimized at q_* = 2an Omega_inf.  Therefore a bound charged
tube exists at density n exactly when

    E(n)/n < B = a Omega_inf^2,   Omega_inf = sqrt(B/a) = 8.717797887081348.

This calculation imposes no transverse width.  It relaxes the carrier tube in the
transverse plane only (the configuration is translation invariant along its axis, and
axisymmetric around it), then asks what the same profile costs when the axis is bent into
a circle of radius R and when the carrier phase winds around that circle.

Three results are established:

* the tube digs its own waveguide: the carrier displaces the mediator from its vacuum and
  the displaced mediator is what binds the carrier, at every linear density above a
  critical one;
* an untwisted tube bends at identically zero energy cost -- every curvature-dependent
  term in the bent metric carries a factor cos(phi) that integrates out over the
  cross-section -- so an untwisted loop has no preferred radius;
* a twisted tube pays exactly the phase-gradient energy of the winding, whose closed form
  is 2*pi*(k_Cx/2)*w^2*N/R times the measure-weighted mean of 1/sqrt(1 - (a_i/R)^2), so a
  twisted loop is a spring with a preferred radius.

The calculation is a finite-grid variational relaxation.  It does not establish
continuum existence, nonlinear stability, or the physical identification of the tube.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from scipy.interpolate import CubicSpline

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-tube-geometry-v2"
VERDICT = "SUPPORTS-registered tube; exact free bending; winding supplies loop scale"

A_COEF = 1.0 / 16.0
CPSI = 1.0 / 8.0
UR = 4.0
UC = 1.0
K_CX = 1.0
# gradient coefficients as they appear in E: (1/2)|grad f|^2 and (K_Cx/2)|grad c|^2.
# c_Psi and a are the kinetic masses and do not enter the static functional.
GRAD_F = 1.0 / 2.0
GRAD_C = K_CX / 2.0
B_COEF = 19.0 / 4.0
H_COEF = 2.9598260763447164
OMEGA_INF = math.sqrt(B_COEF / A_COEF)

# The exact identity checked in C2 is the statement that the bent-metric energy of an
# axisymmetric cross-section equals the flat-cylinder energy.  It is an identity of the
# continuum functional, so the tolerance is the floating-point floor of the quadrature.
IDENTITY_TOL = 1e-10
SWEEPS = 4
TOWNES_MASS = 11.700896
WEAK_ATTRACTION = 2.0 * H_COEF * H_COEF / UR - UC
TOWNES_N_CRIT = K_CX * TOWNES_MASS / (2.0 * WEAK_ATTRACTION)
TORUS_AMAX = 6.0
TORUS_NPHI = 64
# The winding integrand carries 1/sqrt(1 - (kappa*a)^2), which is singular at the outer
# edge as kappa*a -> 1.  Tight tori therefore need a finer azimuthal grid for the phi
# integral, while the cross-section identity (no winding) does not.
TORUS_NPHI_FINE = 512


class Tube:
    """Transverse carrier/mediator problem for an axis-invariant tube (radial, variational).

    Registered functional of the matter-formation program:

        E = int [ (1/2)|grad f|^2 + (K_Cx/2)|grad c|^2 + (u_rho/4)(f^2-1)^2
                  + (B - h + h f^2)|c|^2 + (u_C/2)|c|^4 ] d^3x,      K_Cx = 1.

    The gradient coefficients are 1/2 for the mediator and K_Cx/2 for the carrier; c_Psi and
    a are the kinetic masses and do not appear in the static energy.  The outer boundary is
    the vacuum, f -> 1 and c -> 0, imposed as exact values on the last face.
    """

    def __init__(self, M: int = 800, rmax: float = 8.0):
        self.M = M
        self.rmax = rmax
        self.dr = rmax / M
        self.r = (np.arange(M) + 0.5) * self.dr
        self.rf = (np.arange(M) + 1.0) * self.dr
        self.rfm = np.concatenate([[0.0], self.rf[:-1]])

    def energy(self, f: np.ndarray, c: np.ndarray) -> float:
        dr, r, rf = self.dr, self.r, self.rf
        fe = np.concatenate([f, [1.0]])
        ce = np.concatenate([c, [0.0]])
        v = ((UR / 4.0) * (f * f - 1.0) ** 2
             + (B_COEF - H_COEF + H_COEF * f * f) * c * c
             + (UC / 2.0) * c ** 4)
        e = 2.0 * math.pi * np.sum(r * dr * v)
        e += 2.0 * math.pi * GRAD_F * np.sum(rf * dr * ((fe[1:] - fe[:-1]) / dr) ** 2)
        e += 2.0 * math.pi * GRAD_C * np.sum(rf * dr * ((ce[1:] - ce[:-1]) / dr) ** 2)
        return float(e)

    def f_energy(self, f: np.ndarray, c: np.ndarray) -> float:
        """The mediator-only part of E, for the f-block line search."""
        dr, r, rf = self.dr, self.r, self.rf
        fe = np.concatenate([f, [1.0]])
        v = (UR / 4.0) * (f * f - 1.0) ** 2 + H_COEF * f * f * c * c
        e = 2.0 * math.pi * np.sum(r * dr * v)
        e += 2.0 * math.pi * GRAD_F * np.sum(rf * dr * ((fe[1:] - fe[:-1]) / dr) ** 2)
        return float(e)

    def population(self, c: np.ndarray) -> float:
        return float(2.0 * math.pi * np.sum(self.r * self.dr * c * c))

    def rescale(self, c: np.ndarray, n_target: float) -> np.ndarray:
        return c * math.sqrt(n_target / max(self.population(c), 1e-300))

    def width_rms(self, c: np.ndarray) -> float:
        w = self.r * self.dr * c * c
        return float(math.sqrt(np.sum(w * self.r ** 2) / np.sum(w)))

    def f_min(self, f: np.ndarray) -> float:
        return float(np.min(f))

    def mu_ls(self, f: np.ndarray, c: np.ndarray) -> float:
        """Multiplier from the least-squares stationarity of the carrier equation."""
        dr, r, rf = self.dr, self.r, self.rf
        ce = np.concatenate([c, [0.0]])
        dV = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) * c + 2.0 * UC * c ** 3
        flux = rf * (ce[1:] - ce[:-1])
        lap = np.concatenate([[0.0], flux[:-1]]) - flux
        dEdc = 2.0 * math.pi * (dr * r * dV + (2.0 * GRAD_C / dr) * lap)
        dNdc = 4.0 * math.pi * r * dr * c
        return float(np.sum(dEdc * dNdc) / max(np.sum(dNdc * dNdc), 1e-300))

    def system(self, x: np.ndarray, n_target: float):
        """Gradient of E - mu*(N - n_target) with its Jacobian: exact discrete variational form."""
        M, dr, r, rf, rfm = self.M, self.dr, self.r, self.rf, self.rfm
        f, c, mu = x[:M], x[M:2 * M], x[2 * M]
        fe = np.concatenate([f, [1.0]])
        ce = np.concatenate([c, [0.0]])
        dVdf = UR * f * (f * f - 1.0) + 2.0 * H_COEF * f * c * c
        dVdc = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) * c + 2.0 * UC * c ** 3
        flux_f = rf * (fe[1:] - fe[:-1])
        flux_c = rf * (ce[1:] - ce[:-1])
        lap_f = np.concatenate([[0.0], flux_f[:-1]]) - flux_f
        lap_c = np.concatenate([[0.0], flux_c[:-1]]) - flux_c
        gf, gc = 2.0 * GRAD_F / dr, 2.0 * GRAD_C / dr
        res_f = 2.0 * math.pi * (dr * r * dVdf + gf * lap_f)
        res_c = 2.0 * math.pi * (dr * r * dVdc + gc * lap_c) - mu * 4.0 * math.pi * r * dr * c
        res_mu = self.population(c) - n_target
        res = np.concatenate([res_f, res_c, [res_mu]])

        d2ff = UR * (3.0 * f * f - 1.0) + 2.0 * H_COEF * c * c
        d2cc = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) + 6.0 * UC * c * c
        d2fc = 4.0 * H_COEF * f * c
        idx = np.arange(M)
        jac = np.zeros((2 * M + 1, 2 * M + 1))
        jac[idx, idx] = 2.0 * math.pi * (dr * r * d2ff + 2.0 * GRAD_F * (rf + rfm) / dr)
        jac[idx[:-1], idx[:-1] + 1] = 2.0 * math.pi * (-gf * rf[:-1])
        jac[idx[1:], idx[1:] - 1] = 2.0 * math.pi * (-gf * rfm[1:])
        jac[idx, M + idx] = 2.0 * math.pi * dr * r * d2fc
        jac[M + idx, idx] = 2.0 * math.pi * dr * r * d2fc
        jac[M + idx, M + idx] = (2.0 * math.pi * (dr * r * d2cc + 2.0 * GRAD_C * (rf + rfm) / dr)
                                 - mu * 4.0 * math.pi * r * dr)
        jac[M + idx[:-1], M + idx[:-1] + 1] = 2.0 * math.pi * (-gc * rf[:-1])
        jac[M + idx[1:], M + idx[1:] - 1] = 2.0 * math.pi * (-gc * rfm[1:])
        jac[M + idx, 2 * M] = -4.0 * math.pi * r * dr * c
        jac[2 * M, M + idx] = 4.0 * math.pi * r * dr * c
        return res, jac, np.ones(2 * M + 1)

    def f_newton(self, f: np.ndarray, c: np.ndarray, iters: int = 15) -> np.ndarray:
        M, dr, r, rf, rfm = self.M, self.dr, self.r, self.rf, self.rfm
        gf = 2.0 * GRAD_F / dr
        for _ in range(iters):
            fe = np.concatenate([f, [1.0]])
            dV = UR * f * (f * f - 1.0) + 2.0 * H_COEF * f * c * c
            flux = rf * (fe[1:] - fe[:-1])
            lap = np.concatenate([[0.0], flux[:-1]]) - flux
            res = 2.0 * math.pi * (dr * r * dV + gf * lap)
            d2 = UR * (3.0 * f * f - 1.0) + 2.0 * H_COEF * c * c
            idx = np.arange(M)
            jac = np.zeros((M, M))
            jac[idx, idx] = 2.0 * math.pi * (dr * r * d2 + 2.0 * GRAD_F * (rf + rfm) / dr)
            jac[idx[:-1], idx[:-1] + 1] = 2.0 * math.pi * (-gf * rf[:-1])
            jac[idx[1:], idx[1:] - 1] = 2.0 * math.pi * (-gf * rfm[1:])
            step = np.linalg.solve(jac, -res)
            if float(np.max(np.abs(step))) < 1e-13:
                return f
            e0 = self.f_energy(f, c)
            alpha = 1.0
            for _ in range(60):
                ft = np.clip(f + alpha * step, 0.0, 1.0)
                if self.f_energy(ft, c) < e0:
                    break
                alpha *= 0.5
            else:
                return f
            f = ft
        return f

    def c_newton(self, f: np.ndarray, c: np.ndarray, n_target: float, iters: int = 20) -> np.ndarray:
        M, dr, r, rf, rfm = self.M, self.dr, self.r, self.rf, self.rfm
        gc = 2.0 * GRAD_C / dr
        mu = self.mu_ls(f, c)
        for _ in range(iters):
            ce = np.concatenate([c, [0.0]])
            dV = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) * c + 2.0 * UC * c ** 3
            flux = rf * (ce[1:] - ce[:-1])
            lap = np.concatenate([[0.0], flux[:-1]]) - flux
            res = np.concatenate([
                2.0 * math.pi * (dr * r * dV + gc * lap) - mu * 4.0 * math.pi * r * dr * c,
                [self.population(c) - n_target]])
            d2 = 2.0 * (B_COEF - H_COEF + H_COEF * f * f) + 6.0 * UC * c * c
            idx = np.arange(M)
            jac = np.zeros((M + 1, M + 1))
            jac[idx, idx] = (2.0 * math.pi * (dr * r * d2 + 2.0 * GRAD_C * (rf + rfm) / dr)
                             - mu * 4.0 * math.pi * r * dr)
            jac[idx[:-1], idx[:-1] + 1] = 2.0 * math.pi * (-gc * rf[:-1])
            jac[idx[1:], idx[1:] - 1] = 2.0 * math.pi * (-gc * rfm[1:])
            jac[idx, M] = -4.0 * math.pi * r * dr * c
            jac[M, idx] = 4.0 * math.pi * r * dr * c
            step = np.linalg.solve(jac, -res)
            if float(np.max(np.abs(step[:M]))) < 1e-13 * max(1.0, float(np.max(np.abs(c)))):
                return c
            e0 = self.energy(f, c)
            accepted = False
            alpha = 1.0
            for _ in range(60):
                ct = self.rescale(np.maximum(c + alpha * step[:M], 0.0), n_target)
                if self.energy(f, ct) < e0:
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                return c
            c = self.rescale(np.maximum(c + alpha * step[:M], 0.0), n_target)
            mu = mu + alpha * step[M]
        return c

    def merit(self, x: np.ndarray, n_target: float) -> float:
        M = self.M
        f, c, mu = x[:M], x[M:2 * M], x[2 * M]
        g = self.population(c) - n_target
        return self.energy(f, c) - mu * g + 0.5 * g * g

    def joint_newton(self, f: np.ndarray, c: np.ndarray, n_target: float, iters: int = 60):
        """Damped Newton on the KKT system with an energy-merit line search."""
        M = self.M
        x = np.concatenate([f, c, [self.mu_ls(f, c)]])
        lam = 1e-9
        it = 0
        for it in range(iters):
            res, jac, _ = self.system(x, n_target)
            rn = float(np.max(np.abs(res)))
            if rn < 1e-11:
                break
            diag = np.abs(np.diag(jac)) + 1e-10
            accepted = False
            for _ in range(30):
                try:
                    step = np.linalg.solve(jac + lam * np.diag(diag), -res)
                except np.linalg.LinAlgError:
                    lam = max(lam * 10.0, 1e-10)
                    continue
                phi0 = self.merit(x, n_target)
                alpha = 1.0
                for _ in range(60):
                    xt = x + alpha * step
                    xt[:M] = np.clip(xt[:M], 0.0, 1.0)
                    xt[M:2 * M] = np.maximum(xt[M:2 * M], 0.0)
                    if self.merit(xt, n_target) < phi0:
                        accepted = True
                        break
                    alpha *= 0.5
                if accepted:
                    x = xt
                    lam = max(lam * 0.25, 1e-10)
                    break
                lam = max(lam * 10.0, 1e-10)
            if not accepted:
                break
        res, _, _ = self.system(x, n_target)
        return x[:M], x[M:2 * M], float(x[2 * M]), float(np.max(np.abs(res))), it + 1

    def solve(self, n_target: float, sigma: float = 0.5, sweeps: int = 40,
              f_init: np.ndarray | None = None, c_init: np.ndarray | None = None):
        """Block Gauss-Seidel sweeps (exact f, exact c) followed by a joint Newton polish."""
        r = self.r
        if c_init is None:
            c = self.rescale(np.exp(-r ** 2 / (2.0 * sigma ** 2)), n_target)
        else:
            c = self.rescale(np.asarray(c_init, dtype=float), n_target)
        f = (1.0 - 0.9 * (c / c.max()) ** 2) if f_init is None else np.asarray(f_init, dtype=float)
        sweep = 0
        for sweep in range(sweeps):
            f = self.f_newton(f, c)
            c = self.c_newton(f, c, n_target)
        f, c, mu, rn, it = self.joint_newton(f, c, n_target)
        return dict(f=f, c=c, mu=mu, energy=self.energy(f, c), population=self.population(c),
                    residual=rn, newton_iters=it, sweeps=sweep + 1, n=n_target)


class TorusSection:
    """Carrier/mediator cross-section carried around a circle of radius R.

    The three-dimensional measure in adapted coordinates (s along the circle, a across the
    tube, phi around it) is dV = R*a*(1 + kappa*a*cos(phi)) da dphi ds with kappa = 1/R, so
    the metric factor of the cross-section is g = 1 + kappa*a*cos(phi).  This class only
    evaluates energies and gradients of a supplied profile; it does not relax.
    """

    def __init__(self, Na: int = 400, amax: float = 8.0, Nphi: int = 16):
        self.da = amax / Na
        self.dphi = 2.0 * math.pi / Nphi
        self.a = (np.arange(Na) + 0.5) * self.da
        self.phi = np.arange(Nphi) * self.dphi
        self.Na, self.Nphi = Na, Nphi
        self.af = np.arange(1, Na + 1) * self.da

    def weights(self, kap: float):
        A = self.a[:, None]
        P = self.phi[None, :]
        Pf = P + 0.5 * self.dphi
        # The cross-section grid extends past the tube's support.  Where the metric factor
        # 1 + kappa*a*cos(phi) would vanish the cell is outside the torus: it carries no
        # measure and no gradient energy, and the winding term is capped there.
        g = np.maximum(1.0 + kap * A * np.cos(P), 0.0)
        VC = A * g * self.da * self.dphi
        gf = np.maximum(1.0 + kap * self.af[:, None] * np.cos(P), 0.0)
        Fa = np.zeros((self.Na + 1, self.Nphi))
        Fa[1:] = self.af[:, None] * gf * self.dphi / self.da
        Fp = np.maximum(1.0 + kap * A * np.cos(Pf), 0.0) * self.da / (A * self.dphi)
        return VC, Fa, Fp, g

    def energy(self, f: np.ndarray, c: np.ndarray, kap: float, w: float, R: float) -> float:
        VC, Fa, Fp, g = self.weights(kap)
        ip = np.empty_like(f); ip[:-1] = f[1:]; ip[-1] = 1.0
        im = np.empty_like(f); im[1:] = f[:-1]; im[0] = 0.0
        jp = np.roll(f, -1, axis=1); jm = np.roll(f, 1, axis=1)
        grad_f = np.sum(Fa[1:] * (ip - f) ** 2) + np.sum(Fp * (jp - f) ** 2)
        cip = np.empty_like(c); cip[:-1] = c[1:]; cip[-1] = 0.0
        cim = np.empty_like(c); cim[1:] = c[:-1]; cim[0] = 0.0
        cjp = np.roll(c, -1, axis=1); cjm = np.roll(c, 1, axis=1)
        grad_c = np.sum(Fa[1:] * (cip - c) ** 2) + np.sum(Fp * (cjp - c) ** 2)
        tw = (GRAD_C * w * w / R ** 2) / np.maximum(g, 1e-12) ** 2
        dens = ((UR / 4) * (f * f - 1) ** 2 + (B_COEF - H_COEF + H_COEF * f * f) * c * c
                + (UC / 2) * c ** 4 + tw * c * c)
        return float(np.sum(VC * dens) + GRAD_F * grad_f + GRAD_C * grad_c)

    def population(self, c: np.ndarray, kap: float) -> float:
        VC = self.weights(kap)[0]
        return float(np.sum(VC * c * c))

    def gradient(self, f: np.ndarray, c: np.ndarray, kap: float, w: float, R: float,
                 n_cross: float, lam: float = 0.0):
        """Exact discrete variational gradient, with the charge constraint N - n_cross."""
        VC, Fa, Fp, g = self.weights(kap)
        tw = (GRAD_C * w * w / R ** 2) / np.maximum(g, 1e-12) ** 2
        ip = np.empty_like(f); ip[:-1] = f[1:]; ip[-1] = 1.0
        im = np.empty_like(f); im[1:] = f[:-1]; im[0] = 0.0
        jp = np.roll(f, -1, axis=1); jm = np.roll(f, 1, axis=1)
        flux_f = Fa[1:] * (ip - f) - Fa[:-1] * (f - im) + Fp * (jp - f) - np.roll(Fp, 1, axis=1) * (f - jm)
        cip = np.empty_like(c); cip[:-1] = c[1:]; cip[-1] = 0.0
        cim = np.empty_like(c); cim[1:] = c[:-1]; cim[0] = 0.0
        cjp = np.roll(c, -1, axis=1); cjm = np.roll(c, 1, axis=1)
        flux_c = Fa[1:] * (cip - c) - Fa[:-1] * (c - cim) + Fp * (cjp - c) - np.roll(Fp, 1, axis=1) * (c - cjm)
        Rp = VC * (UR * f * (f * f - 1.0) + 2.0 * H_COEF * f * c * c) - 2.0 * GRAD_F * flux_f
        Rc = (VC * (2.0 * ((B_COEF - H_COEF + H_COEF * f * f) * c + UC * c ** 3 + tw * c)
                    - 2.0 * lam * c) - 2.0 * GRAD_C * flux_c)
        return Rp, Rc, n_cross - float(np.sum(VC * c * c))

    def hessian(self, f: np.ndarray, c: np.ndarray, kap: float, w: float, R: float, lam: float):
        """Symmetric Hessian of the discrete energy (charge constraint carried by lam)."""
        VC, Fa, Fp, g = self.weights(kap)
        Na, Np = self.Na, self.Nphi
        N = Na * Np
        idx = np.arange(N).reshape(Na, Np)
        iup = np.roll(idx, -1, axis=0); iup[-1] = 0
        idn = np.roll(idx, 1, axis=0)
        jup = np.roll(idx, -1, axis=1)
        jdn = np.roll(idx, 1, axis=1)
        diag = -(Fa[1:] + Fa[:-1]) - (Fp + np.roll(Fp, 1, axis=1))
        rows, cols, vals = [], [], []

        def add(r, c_, v):
            r, c_, v = np.asarray(r).ravel(), np.asarray(c_).ravel(), np.asarray(v).ravel()
            n = max(r.size, c_.size, v.size)
            if r.size == 1: r = np.full(n, r[0])
            if c_.size == 1: c_ = np.full(n, c_[0])
            if v.size == 1: v = np.full(n, v[0])
            rows.append(r); cols.append(c_); vals.append(v)

        for base, coef in ((0, 2.0 * GRAD_F), (N, 2.0 * GRAD_C)):
            add(base + idx, base + idx, -coef * diag)
            va = Fa[1:].copy(); va[-1] = 0.0
            add(base + idx, base + iup, -coef * va)
            add(base + idx, base + idn, -coef * Fa[:-1])
            add(base + idx, base + jup, -coef * Fp)
            add(base + idx, base + jdn, -coef * np.roll(Fp, 1, axis=1))
        add(idx, idx, VC * (UR * (3 * f * f - 1) + 2 * H_COEF * c * c))
        add(idx, N + idx, VC * (4 * H_COEF * f * c))
        add(N + idx, idx, VC * (4 * H_COEF * f * c))
        tw = (GRAD_C * w * w / R ** 2) / np.maximum(g, 1e-12) ** 2
        add(N + idx, N + idx, VC * (2.0 * (B_COEF - H_COEF + H_COEF * f * f)
                                    + 6 * UC * c * c + 2 * tw - 2 * lam))
        add(N + idx, 2 * N, -2 * VC * c)
        add(2 * N, N + idx, -2 * VC * c)
        return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                             shape=(2 * N + 1, 2 * N + 1))


def mode_block(H, t: TorusSection, m: int):
    """Restrict the Hessian to perturbations delta(a) cos(m phi), dropping the lambda row."""
    Na = t.Na
    v = sp.csr_matrix(np.cos(m * t.phi).reshape(-1, 1))
    K = sp.kron(sp.eye(Na, format="csr"), v)
    P = sp.bmat([[K, None], [None, K]], format="csr")
    Hm = (P.T @ H[:-1, :-1] @ P).toarray()
    return 0.5 * (Hm + Hm.T)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="runs/tube_geometry")
    ap.add_argument("--linear-density", type=float, default=math.pi)
    ap.add_argument("--quick", action="store_true", help="smaller grids for a fast run")
    args = ap.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    M = 200 if args.quick else 400
    Na = 150 if args.quick else 300
    n_target = args.linear_density
    checks: list[dict] = []
    receipt: dict = {"schema": SCHEMA, "verdict": VERDICT, "coefficients": {
        "a": A_COEF, "c_psi": CPSI, "u_rho": UR, "u_C": UC, "B": B_COEF, "h": H_COEF,
        "k_Cx": K_CX, "grad_f": GRAD_F, "grad_c": GRAD_C, "Omega_inf": OMEGA_INF,
        "townes_mass": TOWNES_MASS, "weak_attraction": WEAK_ATTRACTION,
        "townes_critical_linear_density": TOWNES_N_CRIT},
        "python": platform.python_version(), "numpy": np.__version__}

    def record(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    print("=" * 78)
    print("Field-tube transverse structure, bending and twist")
    print("=" * 78)

    # ---- C1: the relaxed flat tube ------------------------------------------------
    print("\nC1  Relaxed transverse profile (no imposed width)")
    t1 = Tube(M=M, rmax=8.0)
    s1 = t1.solve(n_target, sweeps=SWEEPS)
    e_per_charge = s1["energy"] / s1["population"]
    width = t1.width_rms(s1["c"])
    record("C1.1 radial relaxation converges", s1["residual"] < 1e-7,
           f"residual {s1['residual']:.2e} after {s1['sweeps']} block sweeps "
           f"and {s1['newton_iters']} joint-Newton iterations")
    record("C1.2 the carrier displaces the mediator from its vacuum",
           t1.f_min(s1["f"]) < 0.95,
           f"mediator minimum {t1.f_min(s1['f']):.5f} (vacuum 1, depth "
           f"{1.0 - t1.f_min(s1['f']):.4f}), carrier core {s1['c'][0]:.5f}, "
           f"width_rms {width:.4f}")
    binding_depth = B_COEF - e_per_charge
    q_opt = 2.0 * A_COEF * s1["population"] * OMEGA_INF
    record("C1.3 a charged tube binds at this density (registered criterion, report §36.2)",
           binding_depth > 0.0,
           f"E/n = {e_per_charge:.6f} < B = {B_COEF:.6f}; "
           f"threshold-optimal q/L = {q_opt:.6f}")
    omega_stationary = math.sqrt(max(s1["mu"], 0.0) / A_COEF)
    q_stationary = 2.0 * A_COEF * omega_stationary * s1["population"]
    receipt["flat"] = {"linear_density": s1["population"], "E_per_population": e_per_charge,
                       "binding_depth": binding_depth, "threshold_optimal_charge_density": q_opt,
                       "stationary_multiplier": s1["mu"],
                       "stationary_frequency": omega_stationary,
                       "stationary_charge_density": q_stationary,
                       "width_rms": width, "c_core": float(s1["c"][0]),
                       "f_min": float(s1["f"].min()), "residual": s1["residual"],
                       "energy": s1["energy"], "M": M,
                       "r": [round(float(v), 10) for v in t1.r],
                       "f_profile": [round(float(v), 10) for v in s1["f"]],
                       "c_profile": [round(float(v), 10) for v in s1["c"]]}

    # ---- C2: the exact bending identity -------------------------------------------
    print("\nC2  Bending an untwisted tube (exact identity, no relaxation needed)")
    t2 = TorusSection(Na=Na, amax=TORUS_AMAX, Nphi=TORUS_NPHI)
    sp_f = CubicSpline(t1.r, s1["f"])
    sp_c = CubicSpline(t1.r, s1["c"])

    def axisymmetric(kap, sec=None):
        sec = t2 if sec is None else sec
        A = sec.a[:, None]
        P = sec.phi[None, :]
        rp = np.sqrt(np.maximum(A ** 2 - 2 * A * 0.0 * np.cos(P) + 0.0, 0.0))
        f = np.clip(sp_f(rp), 0.0, 1.2)
        c = np.maximum(sp_c(rp), 0.0)
        VC = sec.weights(kap)[0]
        c = c * math.sqrt(n_target / max(float(np.sum(VC * c * c)), 1e-300))
        return f, c

    f_ax, c_ax = axisymmetric(0.0)
    ref_cross = t2.energy(f_ax, c_ax, 0.0, 0.0, 1.0)
    identity = []
    for R in (32.0, 16.0, 12.0, 8.0, 6.5, 6.1):
        kap = 1.0 / R
        f_k, c_k = axisymmetric(kap)
        d_cross = t2.energy(f_k, c_k, kap, 0.0, R) - ref_cross
        identity.append({"R": R, "kappa": kap, "dE_cross": d_cross,
                         "kappa_amax": kap * TORUS_AMAX})
    worst = max(abs(row["dE_cross"]) for row in identity)
    record("C2.1 bent-metric energy of the axisymmetric profile equals the flat one",
           worst < IDENTITY_TOL,
           f"max |dE_cross| = {worst:.2e} over physical tori R = 32 ... 6.1 "
           f"(cross-section cutoff {TORUS_AMAX:g}, kappa*amax up to "
           f"{identity[-1]['kappa_amax']:.4f})")
    flat_floor = max(abs(row["dE_cross"]) for row in identity if row["R"] >= 16.0)
    strong = abs(identity[-1]["dE_cross"])
    record("C2.2 the deviation does not grow with curvature",
           strong <= max(flat_floor, 1e-12) * 10.0,
           f"|dE_cross| at R>=16: {flat_floor:.2e}, at R={identity[-1]['R']:g}: {strong:.2e} "
           "(every curvature term carries cos(phi), whose cross-sectional integral vanishes)")
    receipt["bending_identity"] = identity

    # ---- C3: cross-section mode spectrum ------------------------------------------
    print("\nC3  Cross-section mode spectrum (is the tube a genuine minimum?)")
    Nm = 8
    t3 = TorusSection(Na=Na, amax=TORUS_AMAX, Nphi=Nm)
    f3 = np.repeat(s1["f"][:, None], Nm, axis=1) if Na == M else None
    if f3 is None:
        rr = t3.a
        f3 = np.clip(sp_f(rr), 0.0, 1.2)[:, None].repeat(Nm, axis=1)
        c3 = np.maximum(sp_c(rr), 0.0)[:, None].repeat(Nm, axis=1)
        VC = t3.weights(0.0)[0]
        c3 = c3 * math.sqrt(n_target / float(np.sum(VC * c3 * c3)))
    else:
        c3 = np.repeat(s1["c"][:, None], Nm, axis=1)
    # converge the charge multiplier for this grid by one Newton step on lambda only
    lam = 0.0
    for _ in range(20):
        Rp, Rc, G = t3.gradient(f3, c3, 0.0, 0.0, 1.0, n_target, lam)
        rn = max(float(np.abs(Rp).max()), float(np.abs(Rc).max()), abs(G))
        if rn < 1e-11 * max(1.0, n_target):
            break
        J = t3.hessian(f3, c3, 0.0, 0.0, 1.0, lam)
        d = spl.spsolve(J.tocsc(), -np.concatenate([Rp.ravel(), Rc.ravel(), [G]]))
        lam += d[-1]
    H = t3.hessian(f3, c3, 0.0, 0.0, 1.0, lam)
    sym = float(abs(H - H.T).max() / abs(H).max())
    record("C3.1 discrete Hessian is symmetric", sym < 1e-12, f"max asymmetry ratio {sym:.2e}")
    spectrum = {}
    for m in (0, 1, 2, 3, 4):
        Hm = mode_block(H, t3, m)
        if m == 0:
            VC = t3.weights(0.0)[0]
            gvec = np.zeros(2 * Na); gvec[Na:] = 2.0 * np.sum(VC * c3, axis=1)
            gh = gvec / np.linalg.norm(gvec)
            Q, _ = np.linalg.qr(np.eye(2 * Na) - np.outer(gh, gh))
            ev = np.linalg.eigvalsh(Q[:, :2 * Na - 1].T @ Hm @ Q[:, :2 * Na - 1])
        else:
            ev = np.linalg.eigvalsh(Hm)
        scale = float(np.abs(ev).max())
        spectrum[m] = {"min": float(ev[0]), "max": scale,
                       "relative_min": float(ev[0] / scale),
                       "negative": int((ev < -1e-6 * scale).sum())}
    others = min(spectrum[m]["relative_min"] for m in (2, 3, 4))
    record("C3.2 the translation mode is soft",
           abs(spectrum[1]["relative_min"]) < 0.2 * abs(others),
           f"m=1 relative eigenvalue {spectrum[1]['relative_min']:+.2e} versus "
           f"{others:+.2e} for m=2,3,4 (max {spectrum[1]['max']:.1f})")
    record("C3.3 all non-translation modes are positive",
           all(spectrum[m]["negative"] == 0 for m in (2, 3, 4))
           and all(spectrum[m]["min"] > 0 for m in (2, 3, 4)),
           "m=2,3,4 minima " + ", ".join(f"{spectrum[m]['min']:.4f}" for m in (2, 3, 4)))
    record("C3.4 the angular stiffness rises with m",
           spectrum[2]["min"] < spectrum[3]["min"] < spectrum[4]["min"],
           f"m=2 {spectrum[2]['min']:.4f} < m=3 {spectrum[3]['min']:.4f} < m=4 {spectrum[4]['min']:.4f}")
    receipt["modes"] = {str(k): v for k, v in spectrum.items()}

    # ---- C4: twist energy and its closed form -------------------------------------
    print("\nC4  Twisted tube: the winding energy and its closed form")
    twist_rows = []
    t2f = TorusSection(Na=Na, amax=TORUS_AMAX, Nphi=TORUS_NPHI_FINE)
    for R in (32.0, 16.0, 12.0, 8.0, 6.5, 6.1):
        kap = 1.0 / R
        sec = t2f if R <= 8.0 else t2
        f_k, c_k = axisymmetric(kap, sec)
        # Compare the complete-function energy difference with the independent analytic
        # phi integral int dphi/(1 + kappa*a*cos(phi)) = 2*pi/sqrt(1-(kappa*a)^2).
        unwound = sec.energy(f_k, c_k, kap, 0.0, R)
        measured = sec.energy(f_k, c_k, kap, 1.0, R) - unwound
        c_radial2 = c_k[:, 0] ** 2
        wgt = sec.a * sec.da * c_radial2
        closed = GRAD_C / R ** 2 * 2.0 * math.pi * float(np.sum(
            wgt / np.sqrt(1.0 - (sec.a / R) ** 2)))
        population = sec.population(c_k, kap)
        leading = GRAD_C * population / R ** 2
        enhancement = closed / leading
        mom2 = float(np.sum(wgt * sec.a ** 2) / np.sum(wgt))
        mom4 = float(np.sum(wgt * sec.a ** 4) / np.sum(wgt))
        series = 1.0 + 0.5 * kap ** 2 * mom2 + 0.375 * kap ** 4 * mom4
        twist_rows.append({"R": R, "kappa": kap, "measured": measured,
                           "closed_form": closed, "leading": leading,
                           "population": population, "metric_enhancement": enhancement,
                           "a2_moment": mom2, "a4_moment": mom4, "moment_series": series,
                           "nphi": sec.Nphi,
                           "ratio_measured_closed": measured / closed})
    worst_tw = max(abs(row["ratio_measured_closed"] - 1.0) for row in twist_rows)
    record("C4.1 the winding energy matches the analytic metric integral",
           worst_tw < 1e-10,
           f"max relative deviation {worst_tw:.2e} over physical tori R = 32 ... 6.1")
    # The tight rows resolve the singular phi integrand; the coarse grid is kept as the
    # measured resolution requirement rather than hidden behind a loosened tolerance.
    tight = twist_rows[-1]
    f_t, c_t = axisymmetric(tight["kappa"], t2)
    u_c = t2.energy(f_t, c_t, tight["kappa"], 0.0, tight["R"])
    m_c = t2.energy(f_t, c_t, tight["kappa"], 1.0, tight["R"]) - u_c
    cc = GRAD_C / tight["R"] ** 2 * 2.0 * math.pi * float(np.sum(
        (t2.a * t2.da * c_t[:, 0] ** 2) / np.sqrt(1.0 - (t2.a / tight["R"]) ** 2)))
    record("C4.5 the tight-torus integral needs the finer azimuthal grid",
           abs(m_c / cc - 1.0) > 10.0 * abs(tight["ratio_measured_closed"] - 1.0),
           f"at R = {tight['R']:g} the coarse Nphi = {TORUS_NPHI} grid deviates by "
           f"{abs(m_c / cc - 1.0):.2e} while Nphi = {TORUS_NPHI_FINE} gives "
           f"{abs(tight['ratio_measured_closed'] - 1.0):.2e}")
    row0 = twist_rows[0]
    record("C4.4 the enhancement equals the exact moment series",
           abs(row0["metric_enhancement"] - row0["moment_series"]) < 1e-6,
           f"enhancement {row0['metric_enhancement']:.9f} versus "
           f"1 + kappa^2<a^2>/2 + 3*kappa^4<a^4>/8 = {row0['moment_series']:.9f} "
           f"(a_rms {math.sqrt(row0['a2_moment']):.4f} from the charge measure)")
    record("C4.2 the leading (K_Cx/2) w^2 N/R^2 law holds at weak curvature",
           abs(twist_rows[0]["measured"] / twist_rows[0]["leading"] - 1.0) < 5e-3,
           f"R=32: measured {twist_rows[0]['measured']:.8f} vs "
           f"leading {twist_rows[0]['leading']:.8f} "
           f"({100 * (twist_rows[0]['measured'] / twist_rows[0]['leading'] - 1.0):+.3f}%)")
    record("C4.3 the metric enhancement grows with curvature",
           all(row["metric_enhancement"] > 1.0 for row in twist_rows)
           and all(twist_rows[i]["metric_enhancement"] < twist_rows[i + 1]["metric_enhancement"]
                   for i in range(len(twist_rows) - 1)),
           "enhancement: " + ", ".join(
               f"R={row['R']:g}: {row['metric_enhancement']:.6f}" for row in twist_rows))
    receipt["twist"] = twist_rows

    # ---- C5: transverse dilation family -------------------------------------------
    print("\nC5  Transverse dilation family (Derrick balance fixes the width)")
    dil_rows = []
    for lam in (0.8, 0.9, 1.0, 1.1, 1.25, 1.5):
        if lam == 1.0:
            cd, fd = s1["c"], s1["f"]
        else:
            cd = np.interp(t1.r / lam, t1.r, s1["c"], left=s1["c"][0], right=0.0) / lam
            fd = np.interp(t1.r / lam, t1.r, s1["f"], left=s1["f"][0], right=1.0)
        e = t1.energy(fd, cd * math.sqrt(n_target / t1.population(cd)))
        dil_rows.append({"lambda": lam, "dE": e - s1["energy"]})
    dilation_zero = next(row["dE"] for row in dil_rows if row["lambda"] == 1.0)
    record("C5.1 the relaxed width is the variational optimum",
           all(row["dE"] > 0 for row in dil_rows if row["lambda"] != 1.0)
           and abs(dilation_zero) < 1e-8,
           "dE(0.9)=" + f"{[r['dE'] for r in dil_rows if r['lambda'] == 0.9][0]:+.5f}"
           + ", dE(1.0)=" + f"{dilation_zero:+.2e}"
           + ", dE(1.1)=" + f"{[r['dE'] for r in dil_rows if r['lambda'] == 1.1][0]:+.5f}")
    receipt["dilation"] = dil_rows

    # ---- C6: critical linear density ----------------------------------------------
    print("\nC6  Critical linear density (bound tube versus dilute carrier)")
    crit = {}
    states = {}

    def row(nc: float):
        seed = states[min(states, key=lambda k: abs(k - nc))] if states else None
        st = t1.solve(nc, sweeps=SWEEPS,
                      f_init=None if seed is None else seed["f"],
                      c_init=None if seed is None else seed["c"])
        if st["residual"] >= 1e-7:
            retry = t1.solve(nc, sweeps=max(2 * SWEEPS, 8))
            if retry["residual"] < st["residual"]:
                st = retry
        if st["residual"] >= 1e-7:
            return {"E_per_population": float("nan"), "converged": False}
        states[nc] = st
        return {"E_per_population": st["energy"] / st["population"], "converged": True,
                "width_rms": t1.width_rms(st["c"]), "f_min": float(st["f"].min()),
                "multiplier": st["mu"], "residual": st["residual"]}

    lo, hi = 1.5, 2.5
    crit[hi] = row(hi)
    crit[lo] = row(lo)

    def bound(nc: float) -> bool:
        return bool(crit[nc]["converged"] and crit[nc]["E_per_population"] < B_COEF)

    for _ in range(5):
        mid = 0.5 * (lo + hi)
        crit[mid] = row(mid)
        if bound(mid):
            hi = mid
        else:
            lo = mid
    window = (lo, hi)
    receipt["critical"] = {str(k): v for k, v in sorted(crit.items())}
    receipt["critical_window"] = window
    receipt["weak_field_critical"] = {
        "townes_mass": TOWNES_MASS,
        "attraction": WEAK_ATTRACTION,
        "infinite_plane_density": TOWNES_N_CRIT,
    }
    print("   window scan: " + ", ".join(
        f"n={k:g}: E/n={crit[k]['E_per_population']:.5f}" for k in sorted(crit)))
    record("C6.1 the carrier is unbound below the finite-domain crossing",
           all(crit[k]["converged"] and crit[k]["E_per_population"] >= B_COEF
               for k in crit if k <= lo),
           f"E/n >= B = {B_COEF} at every scanned density n <= {lo:g}")
    record("C6.2 a bound tube exists above the finite-domain crossing",
           bound(hi) and crit[hi]["width_rms"] < 0.5 * t1.rmax,
           f"n = {hi:g}: E/n = {crit[hi]['E_per_population']:.6f} < B, width_rms "
           f"{crit[hi]['width_rms']:.4f}, f_min {crit[hi]['f_min']:.4f}")
    record("C6.3 the finite-domain crossing brackets the transition",
           window[0] < window[1] and bound(window[1]) and not bound(window[0]),
           f"critical linear density in ({window[0]:.6f}, {window[1]:.6f})")
    record("C6.4 the crossing approaches the Townes weak-field threshold from above",
           TOWNES_N_CRIT < window[0] and window[1] - TOWNES_N_CRIT < 0.35,
           f"finite R={t1.rmax:g} window {window}; infinite-plane Townes value "
           f"{TOWNES_N_CRIT:.6f}")

    # ---- C7: strong-density asymptote ---------------------------------------------
    print("\nC7  Strong-density tube (saturated mediator, growing radius)")
    strong = {}
    cur = (s1["f"], s1["c"])
    for nc in (8.0, 24.0, 48.0):
        prev_c = cur[1]
        lam = math.sqrt(nc / max(t1.population(prev_c), 1e-30))
        cd = np.interp(t1.r / lam, t1.r, cur[1], left=cur[1][0], right=0.0) / lam
        fd = np.interp(t1.r / lam, t1.r, cur[0], left=cur[0][0], right=1.0)
        s = t1.solve(nc, sweeps=SWEEPS, f_init=fd, c_init=cd)
        strong[nc] = {"E_per_charge": s["energy"] / s["population"],
                      "width_rms": t1.width_rms(s["c"]), "f_min": float(s["f"].min()),
                      "residual": s["residual"], "energy": s["energy"],
                      "population": s["population"],
                      "f_profile": [round(float(v), 10) for v in s["f"]],
                      "c_profile": [round(float(v), 10) for v in s["c"]]}
        cur = (s["f"], s["c"])
    asymptote = (B_COEF - H_COEF) + 0.5 * math.sqrt(2.0 * UC * UR)
    record("C7.1 the mediator is fully displaced in the core", strong[48.0]["f_min"] < 0.05,
           f"f_min = {strong[48.0]['f_min']:.2e} at n = 48")
    gaps = {nc: strong[nc]["E_per_charge"] - asymptote for nc in sorted(strong)}
    # the interface cost is a fixed surface term on a core of radius R ~ sqrt(n), so the
    # gap per charge falls as 1/sqrt(n): that is the flat-top structure test.
    scaled = {nc: gaps[nc] * math.sqrt(nc) for nc in sorted(gaps)}
    record("C7.2 the per-charge energy falls toward the saturated value",
           all(strong[a]["E_per_charge"] > strong[b]["E_per_charge"] for a, b in
               ((8.0, 24.0), (24.0, 48.0)))
           and gaps[48.0] > 0.0,
           f"E/N = " + ", ".join(f"{strong[k]['E_per_charge']:.4f}" for k in sorted(strong))
           + f"; flat-top asymptote (B-h)+sqrt(2 u_C u_rho)/2 = {asymptote:.4f}")
    record("C7.3 the residual gap is the interface surface term (gap ~ 1/sqrt(n))",
           max(scaled.values()) / min(scaled.values()) < 1.6,
           "gap*sqrt(n): " + ", ".join(f"n={k:g}: {scaled[k]:.4f}" for k in sorted(scaled)))
    receipt["strong"] = {str(k): v for k, v in strong.items()}

    # ---- receipt ------------------------------------------------------------------
    payload = json.dumps(receipt, indent=1, sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    receipt["content_sha256"] = digest
    (out_dir / "tube_geometry.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
    (out_dir / "tube_geometry_receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))

    failed = [c for c in checks if not c["pass"]]
    print("\n" + "=" * 78)
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed; receipt {digest[:16]} in {out_dir}")
    if failed:
        for c in failed:
            print(f"  FAILED: {c['check']}")
        print("NOT ALL CHECKS PASSED")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
