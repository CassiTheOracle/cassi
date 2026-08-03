#!/usr/bin/env python3
"""Numerical verification of the two-fluid phase-operator derivation.

Claims checked (hypotheses/riemann-two-fluid-phase-operator.md):

C1. phi(u) = J_kappa(E e^u) solves the massless phase-fluctuation equation
      phi'' + (E^2 e^{2u} - kappa^2) phi = 0        (kappa = |s - 1/2|)
    obtained from theta_tt - theta_rr - 2(1-s) theta_r/r = 0 on the
    self-similar background R_0 = A r^{-s}; s = 3/2 (D = 3) gives kappa = 1.

C2a. Interior cavity (regular at r -> 0, Dirichlet at r = L):
     eigenvalues are EXACTLY E_n = j_{kappa,n}/L (Bessel zeros), counting
     ~ EL/pi (linear). Verified via jn_zeros and the ODE residual.

C2b. Exterior problems do NOT give the Bessel-zero spectrum:
     - box [0, U] in u (walls at r = 1 and r = e^U): eigenvalues have mean
       spacing pi/(e^U - 1) -> 0 as U -> oo (continuum in the limit),
       Weyl-linear counting N_box(E) ~ (E/pi)(e^U - 1).
     - half-line r >= L: continuous spectrum (no L^2 eigenvalues).
     Independent shooting of the radial ODE confirms the box eigenvalues.

C3. The exact spectra count LINEARLY in E; the Riemann-von Mangoldt count
    grows like (E/2pi)ln(E/2pi) - the naive operator FAILS the acceptance
    test at leading order. The logarithmic shape appears only in the
    semiclassical phase-space count (E-dependent boundary, SR-L type).

C4. Bessel-zero asymptotics j_{kappa,n} ~ pi(n + kappa/2 - 1/4) sanity.

Run from repo root:
  python experiments/riemann_phi_search/run_phase_operator_check.py
"""

import math

import numpy as np
from scipy.special import jv, yv, jn_zeros
from scipy.optimize import brentq
from scipy.integrate import solve_ivp

PHI = (1 + math.sqrt(5)) / 2


def jprime(nu, z):
    return 0.5 * (jv(nu - 1, z) - jv(nu + 1, z))


def jsecond(nu, z):
    return 0.25 * (jv(nu - 2, z) - 2 * jv(nu, z) + jv(nu + 2, z))


def check_ode_residual(kappa, E, u_lo, u_hi, n=400_000):
    """C1: residual of J_kappa(E e^u) in phi'' + (E^2 e^{2u} - kappa^2) phi = 0."""
    u = np.linspace(u_lo, u_hi, n)
    z = E * np.exp(u)
    J = jv(kappa, z)
    dJ = jprime(kappa, z) * z
    d2J = jsecond(kappa, z) * z**2 + jprime(kappa, z) * z
    resid = d2J + (E**2 * np.exp(2 * u) - kappa**2) * J
    return float(np.max(np.abs(resid)))


def char(kappa, L, U, E):
    """Characteristic determinant of the box [ln L, U] (Dirichlet both ends)."""
    a, b = E * L, E * math.exp(U)
    return jv(kappa, a) * yv(kappa, b) - yv(kappa, a) * jv(kappa, b)


def char_roots(kappa, L, U, E_max, n_scan=20_000):
    grid = np.linspace(1e-3, E_max, n_scan)
    vals = np.array([char(kappa, L, U, e) for e in grid])
    idx = np.where(np.signbit(vals[:-1]) != np.signbit(vals[1:]))[0]
    roots = []
    for i in idx:
        try:
            roots.append(brentq(lambda e: char(kappa, L, U, e),
                                grid[i], grid[i + 1], maxiter=300))
        except ValueError:
            pass
    return np.array(roots)


def shoot_box_eigenvalues(s, L, R, E_max, n_grid=600, n_max=3):
    """C2b: radial ODE psi_rr + 2(1-s) psi_r/r + E^2 psi = 0, psi(L)=psi(R)=0.

    Shoot from r = R (psi(R)=0, psi'(R)=1) inward; roots of psi(L; E).
    """
    def psiL(E):
        sol = solve_ivp(lambda r, y: [y[1], -2 * (1 - s) * y[1] / r - E**2 * y[0]],
                        [R, L], [0.0, 1.0], rtol=1e-9, atol=1e-11,
                        max_step=(R - L) / 2000)
        return sol.y[0, -1]

    E_grid = np.linspace(1e-3, E_max, n_grid)
    vals = np.array([psiL(e) for e in E_grid])
    idx = np.where(np.signbit(vals[:-1]) != np.signbit(vals[1:]))[0]
    roots = []
    for i in idx[:n_max]:
        roots.append(brentq(psiL, E_grid[i], E_grid[i + 1], maxiter=300))
    return np.array(roots)


def main():
    print(f"phi = {PHI:.6f}; framework background s = 3/2 (D = 3) -> kappa = |s-1/2| = 1")

    # ---- C1: ODE residual ----
    print("\n[C1] ODE residual of J_kappa(E e^u)")
    for kappa, E in [(1.0, 2.5), (1.0, 20.0), (0.5, 3.0), (2.0, 7.0)]:
        r = check_ode_residual(kappa, E, -3.0, 2.5)
        print(f"  kappa={kappa:.1f} E={E:5.1f}:  max|residual| = {r:.2e}")

    # ---- C2a: interior cavity eigenvalues E_n = j_{kappa,n}/L ----
    print("\n[C2a] interior cavity (regular at r=0, wall at r=L=1):")
    print("  eigenvalues E_n = j_{1,n}/L exactly (analytic); verify ODE residual at E = j_{1,1}:")
    jz = jn_zeros(1, 6)
    r = check_ode_residual(1.0, jz[0], -3.0, 0.0)
    print(f"  j_1,1 = {jz[0]:.6f}: residual at the eigenvalue = {r:.2e}")
    print(f"  j_1,n = {np.round(jz, 4)}  -> counting ~ E*L/pi (linear)")

    # ---- C2b: exterior box - spacing -> 0, Weyl-linear counting ----
    print("\n[C2b] exterior box [0, U] (walls at r=1 and r=e^U), kappa=1:")
    for U in [2.0, 4.0]:
        roots = char_roots(1.0, 1.0, U, 40.0)
        spac = np.mean(np.diff(roots[:6]))
        pred = math.pi / (math.exp(U) - 1.0)
        print(f"  U={U:.0f}: first roots={np.round(roots[:3], 5)}  "
              f"mean spacing={spac:.5f}  pi/(e^U-1)={pred:.5f}  (spacing -> 0: continuum)")
    roots8 = char_roots(1.0, 1.0, 8.0, 2.0, n_scan=8_000)
    print(f"  U=8: first roots collapse toward 0: {np.round(roots8[:3], 5)}")

    # independent shooting of the radial ODE (s = 3/2)
    U = 2.0
    roots_char = char_roots(1.0, 1.0, U, 10.0)
    roots_shoot = shoot_box_eigenvalues(1.5, 1.0, math.exp(U), 10.0)
    diff = np.abs(roots_char[:3] - roots_shoot) if len(roots_shoot) else [np.nan]
    print(f"  shooting cross-check (s=3/2, [1, e^{U:.0f}]): char={np.round(roots_char[:3], 6)} "
          f"shoot={np.round(roots_shoot[:3], 6)}  max|diff|={np.max(diff):.2e}")

    # ---- C3: acceptance test - linear vs logarithmic ----
    print("\n[C3] acceptance test: exact counting is LINEAR, R-vM is LOGARITHMIC")
    U = 2.0
    roots = char_roots(1.0, 1.0, U, 100.0, n_scan=30_000)
    for E in [25.0, 50.0, 100.0]:
        n_box = int(np.sum(roots <= E))
        weyl = E / math.pi * (math.exp(U) - 1.0)
        rvm = E / (2 * math.pi) * math.log(E / (2 * math.pi)) \
            - E / (2 * math.pi) + 7 / 8
        print(f"  E={E:6.1f}:  box count={n_box:4d}   Weyl linear={weyl:7.1f}"
              f"   R-vM log={rvm:7.1f}")

    # ---- C4: Bessel-zero asymptotics ----
    print("\n[C4] Bessel-zero asymptotics j_{1,n} ~ pi(n + 1/4)")
    jz25 = jn_zeros(1, 25)
    n = np.arange(1, 26)
    asym = math.pi * (n + 0.25)
    print(f"  max rel diff over n=1..25: {np.max(np.abs(jz25 - asym) / jz25):.2e}")

    # ---- semiclassical pinning (analytic, reported) ----
    print("\n[semiclassical pinning, analytic]")
    print("  A(E) = E ln(E/(L p_min)) - E + L p_min")
    print("  N(E) = (E/2pi) ln(E/(L p_min)) - E/2pi + L p_min/2pi")
    print("  log match to R-vM forces L p_min = 2pi (order-unity; no phi-power)")
    print("  constant: L p_min/2pi = 1 vs theorem 7/8 -> corner-phase gap 1/8")
    print("  (the log shape is semiclassical only; exact spectra of the derived")
    print("   operator are linear/continuous - the SR-L-type E-dependent boundary")
    print("   is what the framework does not supply)")


if __name__ == "__main__":
    main()
