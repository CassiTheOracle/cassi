#!/usr/bin/env python3
"""Cassi Neutron Stars—Soliton Matter at Maximum Density."""

import math
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
XI = 18.0
M_SUN = 1.989e30
G = 6.6743e-11
C = 2.998e8


def geff_ns(r):
    rc, rh = 1.5e4, 3e4
    if r < rc:
        return 1.0
    elif r < rh:
        x = (r - rc) / (rh - rc)
        return 1.0 + (XI * PHI_INV**3 - 1.0) * x**2
    return XI * PHI_INV**3


def tov_rhs(r, y):
    m, P = y
    rho = (P / 1.6e18) ** (1/3) if P > 0 else 0
    ge = geff_ns(r)
    if r < 1e-10 or rho < 1e-10 or m < 1:
        return [4*math.pi*r*r*rho, 0.0]
    fac = ge * G * m * rho / (r * r * C * C)
    dp = -fac * (1 + P/(rho*C*C)) * (1 + 4*math.pi*r**3*P/(m*C*C))
    dp /= (1 - 2*ge*G*m/(r*C*C))
    return [4*math.pi*r*r*rho, dp]


def solve_ns(rho_c, max_r=3e4):
    r_min = 1.0
    P_c = 1.6e18 * rho_c**3
    m0 = (4/3) * math.pi * r_min**3 * rho_c
    sol = solve_ivp(tov_rhs, (r_min, max_r), [m0, P_c],
                    method='RK45', rtol=1e-6, atol=1e-8,
                    events=lambda r, y: y[1] - 1e-8)
    if len(sol.t) < 2:
        return None
    return sol.y[0, -1] / M_SUN, sol.t[-1] / 1000


def main():
    print("=" * 65)
    print("CASSI NEUTRON STARS—Soliton Matter")
    print("=" * 65)
    print("\nMass-Radius:")
    print(f"  {'ρ_c (g/cm³)':>14s}  {'M (M☉)':>8s}  {'R (km)':>8s}")
    for rho in np.logspace(17.5, 19, 8):
        res = solve_ns(rho)
        if res:
            m, r = res
            print(f"  {rho:14.2e}  {m:8.3f}  {r:8.1f}")
    print("\nDone.")
    print("=" * 65)


if __name__ == '__main__':
    main()
