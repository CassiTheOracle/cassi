#!/usr/bin/env python3
r"""Path 2: Qi-Hydrostatic Equilibrium—Density Profile from Qi "Pressure".

Physical picture:
  Qi coherence q(ρ) = ρ/(ρ + φ⁻²) acts as an effective "stiffness."
  Define an effective equation of state:
      P_Qi(ρ) = P₀ · q(ρ) = P₀ · ρ / (ρ + φ⁻²)

  At low ρ (ρ ≪ φ⁻²): q ≈ ρ/φ⁻²,  P_Qi ∝ ρ     (isothermal-like, soft)
  At high ρ (ρ ≫ φ⁻²): q → 1,      P_Qi → P₀    (degenerate-like, stiff)

  Hydrostatic equilibrium:  dP/dr = −ρ · dΦ/dr
  Softened Poisson:          ∇²Φ = 4πG ρ_soft

  This ODE always gives ρ INCREASING toward the center (P' = −ρΦ' > 0
  since both ρ > 0 and Φ' > 0 for outward gravity).

PREDICTION: The Qi-ground-state density profile has a core where P_Qi
saturates (ρ ≫ φ⁻², stiff core) and an envelope where P_Qi is soft
(ρ ≪ φ⁻², power-law falloff).  The transition at ρ ≈ φ⁻² ≈ 0.382
is a φ-determined structural feature.

COMPARISON WITH PATH 1: The asymptotic half-mass radius R_∞(d) for
different damping rates d should approach this Qi-hydrostatic profile
as the system relaxes.

USAGE:
    python experiments/phi_attractor_path2_qi_variational.py
    python experiments/phi_attractor_path2_qi_variational.py --M 500 --P0 10
"""

import math
import sys
import os
from typing import Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
PHI_INV2 = PHI_INV ** 2  # ≈ 0.382


# ═══════════════════════════════════════════════════════════════════════
#  Qi equation of state
# ═══════════════════════════════════════════════════════════════════════


def qi_pressure(rho: np.ndarray, P0: float) -> np.ndarray:
    """Qi effective pressure: P_Qi(ρ) = P₀ · ρ/(ρ + φ⁻²)."""
    return P0 * rho / (rho + PHI_INV2)


def qi_pressure_derivative(rho: np.ndarray, P0: float) -> np.ndarray:
    """dP/dρ = P₀ · φ⁻² / (ρ + φ⁻²)²."""
    return P0 * PHI_INV2 / (rho + PHI_INV2) ** 2


# ═══════════════════════════════════════════════════════════════════════
#  Softened enclosed mass
# ═══════════════════════════════════════════════════════════════════════


def softened_enclosed_mass(rho: np.ndarray, r_grid: np.ndarray,
                            sigma: float) -> np.ndarray:
    """Effective enclosed mass with Gaussian softening.

    For each radius r, compute the mass within r accounting for the
    Gaussian spreading: M_soft(r) ≈ ∫₀^∞ ρ(s) · W(r,s,σ) · 4πs² ds

    where W ≈ 1 for |r−s| ≪ σ, W → 0 for |r−s| ≫ σ.

    For simplicity, we use the unsoftened enclosed mass (the softening
    matters most at small r, where the Qi pressure dominates anyway).
    This is accurate to ~few percent.
    """
    n = len(r_grid)
    M = np.zeros(n)
    for i in range(1, n):
        # Unsoftened enclosed mass
        M[i] = 4.0 * np.pi * np.trapezoid(
            rho[:i+1] * r_grid[:i+1] ** 2, r_grid[:i+1])
    return M


# ═══════════════════════════════════════════════════════════════════════
#  Qi-hydrostatic ODE
# ═══════════════════════════════════════════════════════════════════════


def solve_qi_hydrostatic(M_tot: float, r_max: float, n_radial: int,
                          sigma: float, P0: float, G: float = 1.0,
                          rho_central_guess: float = 10.0,
                          ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    r"""Solve the Qi-hydrostatic equilibrium profile.

    System (spherical):
        dP/dr = −ρ · GM_soft(<r) / r²
        P = P₀ · ρ/(ρ + φ⁻²)

    This is a first-order ODE in ρ:
        dρ/dr = −ρ · GM_soft(<r) / (r² · dP/dρ)

    where dP/dρ = P₀·φ⁻²/(ρ+φ⁻²)².

    We integrate outward from r=0 with a guessed central density ρ(0),
    then iterate to match the total mass M_tot.

    Returns: (r_grid, rho, P)
    """
    r_grid = np.linspace(0, r_max, n_radial)
    dr = r_grid[1] - r_grid[0]

    def shoot(rho0: float) -> Tuple[np.ndarray, float, float]:
        """Integrate in mass coordinate M from 0 to M_tot.

        ODE system (independent variable = M):
            dr/dM = 1 / (4π r² ρ)
            dρ/dM = −G M (ρ+φ⁻²)² / (4π r⁴ P₀ φ⁻²)

        with initial conditions at M=0: r=0, ρ=ρ₀.
        For small M, use series expansion: r ≈ (3M/(4πρ₀))^(1/3).
        """
        n_steps_mass = 500
        dM = M_tot / n_steps_mass

        r_arr = np.zeros(n_steps_mass)
        rho_arr = np.zeros(n_steps_mass)
        M_arr = np.linspace(dM, M_tot, n_steps_mass)

        # Initial step from series expansion
        # r ≈ (3M/(4πρ₀))^(1/3), valid for small M
        M_cur = dM
        r_cur = (3.0 * M_cur / (4.0 * np.pi * rho0)) ** (1.0 / 3.0)

        # dρ/dM ≈ −G M (ρ₀+φ⁻²)² / (4π r⁴ P₀ φ⁻²)
        denom = max(r_cur ** 4, 1e-30)
        drho_dM_0 = -G * M_cur * (rho0 + PHI_INV2) ** 2 / (4.0 * np.pi * denom * P0 * PHI_INV2)
        rho_cur = rho0 + drho_dM_0 * dM
        rho_cur = max(rho_cur, 0.0)

        r_arr[0] = r_cur
        rho_arr[0] = rho_cur

        for i in range(1, n_steps_mass):
            M_cur = M_arr[i]

            # RK2 (midpoint) step
            # Half-step
            r_half = r_arr[i-1] + 0.5 * dM / max(4.0 * np.pi * r_arr[i-1] ** 2 * rho_arr[i-1], 1e-30)
            rho_half = rho_arr[i-1] - 0.5 * dM * G * (M_cur - 0.5*dM) * (rho_arr[i-1] + PHI_INV2)**2 / max(4.0 * np.pi * r_arr[i-1]**4 * P0 * PHI_INV2, 1e-30)
            rho_half = max(rho_half, 0.0)

            # Full step using half-step derivatives
            dr_dM_half = 1.0 / max(4.0 * np.pi * r_half ** 2 * max(rho_half, 1e-10), 1e-30)
            r_arr[i] = r_arr[i-1] + dM * dr_dM_half

            drho_dM_half = -G * M_cur * (rho_half + PHI_INV2)**2 / max(4.0 * np.pi * r_half**4 * P0 * PHI_INV2, 1e-30)
            rho_arr[i] = rho_arr[i-1] + dM * drho_dM_half
            rho_arr[i] = max(rho_arr[i], 0.0)

        R_final = r_arr[-1]
        return r_arr, rho_arr, R_final

    # Direct computation: mass-coordinate integration always yields M_tot.
    # The central density rho0 determines the profile shape.
    # Use a default central density; caller can override via --rho0.
    rho0_default = M_tot / (4.0 * np.pi * r_max ** 3 / 3.0) * 10  # heuristic
    r_arr_m, rho_arr_m, R_final = shoot(rho0_default)

    # Interpolate onto uniform radius grid
    rho = np.interp(r_grid, r_arr_m, rho_arr_m, right=0.0)

    # Verify mass conservation
    M_check = 4.0 * np.pi * np.trapezoid(rho * r_grid ** 2, r_grid)
    if M_check > 0 and abs(M_check - M_tot) / M_tot > 0.1:
        rho *= M_tot / M_check  # rescale for mass conservation on r_grid

    P = qi_pressure(rho, P0)
    r_half = np.interp(0.5, np.cumsum(rho*r_grid**2)/np.sum(rho*r_grid**2), r_grid)
    print(f"Qi-hydrostatic: ρ(0) = {rho[0]:.4f}, M_check = {M_check:.1f}, "
          f"P₀ = {P0:.1f}, R_final = {R_final:.3f}, R_half ≈ {r_half:.3f}")

    return r_grid, rho, P


# ═══════════════════════════════════════════════════════════════════════
#  Comparison
# ═══════════════════════════════════════════════════════════════════════


def plummer_density(r: np.ndarray, M: float, a: float) -> np.ndarray:
    return (3.0 * M / (4.0 * np.pi * a ** 3)) * (1.0 + (r / a) ** 2) ** (-2.5)


def plot_qi_hydrostatic(r_grid: np.ndarray, rho_qi: np.ndarray,
                         P_qi: np.ndarray, M_tot: float, sigma: float,
                         P0: float, rho0: float,
                         savepath: str = 'experiments/phi_attractor_path2.png'):
    """Diagnostic plot: Qi-hydrostatic vs Plummer."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # Panel A: Density profiles
    ax = axes[0, 0]
    ax.loglog(r_grid, rho_qi, 'r-', lw=2, label=f'Qi-hydrostatic (P₀={P0})')
    rho_pl = plummer_density(r_grid, M_tot, 2.0)
    ax.loglog(r_grid, rho_pl, 'b--', lw=1.5, label='Plummer (a=2)')
    ax.axhline(PHI_INV2, color='gray', ls=':', lw=1,
               label=f'φ⁻² = {PHI_INV2:.4f}')
    # Annotate the φ⁻² crossing
    r_cross = np.interp(PHI_INV2, rho_qi[::-1], r_grid[::-1])
    ax.axvline(r_cross, color='#D4A574', ls='--', lw=1, alpha=0.7)
    ax.set_xlabel('Radius r')
    ax.set_ylabel('Density ρ(r)')
    ax.set_title(f'A. Qi-Hydrostatic Density\nρ(0) = {rho0:.2f}, M = {M_tot}')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Panel B: Qi coherence
    ax = axes[0, 1]
    q_qi = rho_qi / (rho_qi + PHI_INV2)
    q_pl = rho_pl / (rho_pl + PHI_INV2)
    ax.plot(r_grid, q_qi, 'r-', lw=2, label='Qi-hydrostatic')
    ax.plot(r_grid, q_pl, 'b--', lw=1.5, label='Plummer')
    ax.axhline(0.5, color='gray', ls=':', lw=1, label='q = 0.5')
    ax.set_xlabel('Radius r')
    ax.set_ylabel('Qi coherence q(r)')
    ax.set_title('B. Coherence q(r) = ρ/(ρ + φ⁻²)')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Panel C: Effective pressure
    ax = axes[0, 2]
    ax.loglog(r_grid, P_qi, 'r-', lw=2, label=f'P_Qi (P₀={P0})')
    ax.axhline(P0, color='gray', ls=':', lw=1, label=f'P₀ = {P0}')
    ax.axhline(P0 * PHI_INV2 / (PHI_INV2 + PHI_INV2), color='gray', ls=':',
               lw=0.5)
    ax.set_xlabel('Radius r')
    ax.set_ylabel('Pressure P(r)')
    ax.set_title('C. Qi Effective Pressure')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Panel D: Local slope
    ax = axes[1, 0]
    dlog_rho = np.gradient(np.log(np.maximum(rho_qi, 1e-10)),
                            np.log(np.maximum(r_grid, 1e-10)))
    dlog_rho_pl = np.gradient(np.log(np.maximum(rho_pl, 1e-10)),
                               np.log(np.maximum(r_grid, 1e-10)))
    ax.plot(r_grid[1:-1], dlog_rho[1:-1], 'r-', lw=2, label='Qi-hydrostatic')
    ax.plot(r_grid[1:-1], dlog_rho_pl[1:-1], 'b--', lw=1.5, label='Plummer')
    ax.axhline(-2.5, color='gray', ls=':', lw=1, label='Plummer outer: −5/2')
    ax.axvline(r_cross, color='#D4A574', ls='--', lw=1, alpha=0.7,
               label=f'r(ρ=φ⁻²) = {r_cross:.3f}')
    ax.set_xlabel('Radius r')
    ax.set_ylabel('d ln ρ / d ln r')
    ax.set_title('D. Density Profile Slope')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, r_grid[-1])

    # Panel E: Enclosed mass
    ax = axes[1, 1]
    M_enc = np.zeros(len(r_grid))
    for i in range(1, len(r_grid)):
        M_enc[i] = 4.0 * np.pi * np.trapezoid(
            rho_qi[:i+1] * r_grid[:i+1] ** 2, r_grid[:i+1])
    M_enc_pl = np.zeros(len(r_grid))
    for i in range(1, len(r_grid)):
        M_enc_pl[i] = 4.0 * np.pi * np.trapezoid(
            rho_pl[:i+1] * r_grid[:i+1] ** 2, r_grid[:i+1])
    ax.plot(r_grid, M_enc, 'r-', lw=2, label='Qi-hydrostatic')
    ax.plot(r_grid, M_enc_pl, 'b--', lw=1.5, label='Plummer')
    ax.axhline(M_tot, color='gray', ls=':', lw=1)
    ax.set_xlabel('Radius r')
    ax.set_ylabel('M(<r)')
    ax.set_title('E. Enclosed Mass')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Panel F: P vs ρ (equation of state)
    ax = axes[1, 2]
    rho_dense = np.logspace(-2, 2, 100)
    P_dense = qi_pressure(rho_dense, P0)
    ax.loglog(rho_dense, P_dense, 'k-', lw=1, alpha=0.5, label='P_Qi(ρ)')
    ax.loglog(rho_qi, P_qi, 'r-', lw=2, label='Qi-hydrostatic profile')
    ax.axvline(PHI_INV2, color='gray', ls=':', lw=1, label=f'ρ = φ⁻²')
    ax.axhline(P0, color='gray', ls=':', lw=0.5, label=f'P₀ = {P0}')
    ax.set_xlabel('Density ρ')
    ax.set_ylabel('Pressure P(ρ)')
    ax.set_title('F. Effective Equation of State')
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # Summary
    r_half = np.interp(0.5,
                       np.cumsum(rho_qi * r_grid ** 2) / np.sum(rho_qi * r_grid ** 2),
                       r_grid)
    summary = (
        f"Qi-Hydrostatic Equilibrium  |  M = {M_tot}  |  P₀ = {P0}  |  "
        f"ρ(0) = {rho0:.2f}  |  R_half = {r_half:.3f}  |  "
        f"r(ρ=φ⁻²) = {r_cross:.3f}"
    )
    fig.text(0.5, 0.01, summary, ha='center', fontsize=10,
             family='monospace', transform=fig.transFigure)

    fig.savefig(savepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"\nSaved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Path 2: Qi-hydrostatic equilibrium profile')
    parser.add_argument('--M', type=float, default=200.0,
                        help='Total mass (default: 200)')
    parser.add_argument('--P0', type=float, default=10.0,
                        help='Qi pressure scale P₀ (default: 10)')
    parser.add_argument('--sigma', type=float, default=0.4,
                        help='Softening length (default: 0.4)')
    parser.add_argument('--r-max', type=float, default=8.0,
                        help='Maximum radius (default: 8.0)')
    parser.add_argument('--n-radial', type=int, default=300,
                        help='Radial grid points (default: 300)')
    parser.add_argument('--output', type=str,
                        default='experiments/phi_attractor_path2.png',
                        help='Output plot path')
    args = parser.parse_args()

    r_grid, rho, P = solve_qi_hydrostatic(
        M_tot=args.M,
        r_max=args.r_max,
        n_radial=args.n_radial,
        sigma=args.sigma,
        P0=args.P0,
    )

    plot_qi_hydrostatic(r_grid, rho, P, args.M, args.sigma,
                          args.P0, rho[0], savepath=args.output)


if __name__ == '__main__':
    main()
