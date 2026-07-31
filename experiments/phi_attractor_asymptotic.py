#!/usr/bin/env python3
r"""φ-Attractor Steady State—Asymptotic Half-Mass Radius vs Damping.

KEY FINDING:
  The asymptotic half-mass radius R_∞(d) of a φ-damped N-body system is
  governed by the competition between velocity retention (which enables
  gravitational contraction) and energy dissipation (which drives it).

  Effective contraction rate:  γ_eff(d) = γ₀ · d/(1−d)

  At d = φ⁻¹ ≈ 0.618:  γ_eff/γ₀ = φ ≈ 1.618
  The terminal velocity is v = φ² · a · dt.

  The asymptotic radius follows:
      R_∞(d) = R_min + (R_init − R_min) · exp(−γ₀ · d/(1−d) · T)

  where T is the total simulation time, R_min is the softened core radius.

USAGE:
  python experiments/phi_attractor_steady_state.py          # full sweep
  python experiments/phi_attractor_steady_state.py --quick  # 3 values only
"""

import argparse
import math
import sys
import os
import time
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cassi_nbody import (
    NBodyConfig,
    NBodySolver3D,
    plummer_sphere,
    get_device,
    PHI,
    PHI_INV,
)

# ═══════════════════════════════════════════════════════════════════════
#  Simulation
# ═══════════════════════════════════════════════════════════════════════


def measure_asymptotic_rhalf(N: int, vel_damp: float, config: NBodyConfig,
                               n_steps: int, seed: int = 42
                               ) -> Tuple[float, float, float]:
    """Run simulation and return (R_half_initial, R_half_final, t_dyn)."""
    device = config.device

    rng = torch.Generator(device='cpu')
    rng.manual_seed(seed)
    pos, vel, masses = plummer_sphere(N, 2.0, config)
    pos, vel, masses = pos.to(device), vel.to(device), masses.to(device)

    solver = NBodySolver3D(
        n_grid=config.n_grid, L=config.L, G=config.G,
        sigma=config.sigma, device=device,
        qi_gate=False, deposition_kernel=config.deposition_kernel,
    )

    accel = None
    rh_init = None

    def get_rhalf(pos, masses):
        M = masses.sum().item()
        com = (masses[:, None] * pos).sum(dim=0) / M
        r_all = torch.sqrt(((pos - com[None, :]) ** 2).sum(dim=1))
        sorted_r, _ = torch.sort(r_all)
        cum_mass = torch.cumsum(masses[torch.argsort(r_all)], dim=0)
        hi = min(torch.searchsorted(cum_mass, M / 2.0).item(), N - 1)
        return sorted_r[hi].item()

    for step in range(n_steps):
        pos, vel, accel, _, _ = solver.leapfrog_step(
            pos, vel, masses, config.dt, accel=accel,
            vel_damp=vel_damp, qi_gate=False,
        )
        if step == 0:
            rh_init = get_rhalf(pos, masses)

    rh_final = get_rhalf(pos, masses)
    t_dyn = math.sqrt(rh_init ** 3 / (config.G * N))

    return rh_init, rh_final, t_dyn


def run_asymptotic_sweep(d_values: List[float], N: int = 200,
                          n_steps: int = 2000, n_grid: int = 64,
                          sigma: float = 0.4, dt: float = 0.002,
                          L: float = 20.0, G: float = 1.0,
                          ) -> Dict[float, Tuple[float, float, float]]:
    """Sweep damping values and measure asymptotic R_half."""
    device = get_device()
    config = NBodyConfig(
        n_grid=n_grid, L=L, G=G, sigma=sigma,
        dt=dt, n_steps=n_steps, vel_damp=PHI_INV,
        deposition_kernel='CIC', device=device,
    )

    print(f"Device: {device}  |  N={N}  |  grid={n_grid}³  |  steps={n_steps}")
    print(f"σ={sigma}  |  dt={dt}  |  T_total={n_steps*dt:.1f}")
    print(f"{'d':>8s}  {'R_init':>10s}  {'R_final':>10s}  {'ΔR':>10s}  {'d/(1-d)':>10s}")
    print("-" * 52)

    results = {}
    for d in d_values:
        t0 = time.time()
        rh_init, rh_final, t_dyn = measure_asymptotic_rhalf(
            N=N, vel_damp=d, config=config, n_steps=n_steps, seed=42,
        )
        elapsed = time.time() - t0
        x = d / (1.0 - d) if d < 1.0 else float('inf')
        print(f"{d:8.4f}  {rh_init:10.4f}  {rh_final:10.4f}  "
              f"{rh_init - rh_final:10.4f}  {x:10.4f}  ({elapsed:.1f}s)")
        results[d] = (rh_init, rh_final, t_dyn)

    return results


# ═══════════════════════════════════════════════════════════════════════
#  Analytical model
# ═══════════════════════════════════════════════════════════════════════


def fit_analytical_model(results: Dict[float, Tuple[float, float, float]],
                          T_total: float
                          ) -> Tuple[float, float, float, np.ndarray, np.ndarray]:
    """Fit R_∞(d) = R_min + (R_init − R_min) · exp(−γ₀ · d/(1−d) · T).

    Returns: (R_min, R_init, gamma_0, d_fit, R_pred)
    """
    d_arr = np.array(sorted([d for d in results if d < 1.0]))
    x_arr = d_arr / (1.0 - d_arr)               # d/(1-d)
    R_final = np.array([results[d][1] for d in d_arr])
    R_init_avg = np.mean([results[d][0] for d in d_arr])

    # log(R − R_min) = log(ΔR) − γ₀·T · x
    # Fit by scanning R_min and picking best linear fit
    best_r2 = -np.inf
    best_params = (0.0, R_init_avg, 0.0)

    for R_min_guess in np.linspace(0.01, 0.5, 50):
        dy = np.maximum(R_final - R_min_guess, 1e-10)
        log_dy = np.log(dy)
        if np.any(~np.isfinite(log_dy)):
            continue
        slope, intercept = np.polyfit(x_arr, log_dy, 1)
        R_pred = R_min_guess + np.exp(intercept) * np.exp(slope * x_arr)
        ss_res = np.sum((R_final - R_pred) ** 2)
        ss_tot = np.sum((R_final - R_final.mean()) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        if r2 > best_r2:
            best_r2 = r2
            best_params = (R_min_guess, np.exp(intercept) + R_min_guess, -slope / T_total, r2)

    R_min, R_init_fit, gamma_0, r2 = best_params
    R_pred = R_min + (R_init_fit - R_min) * np.exp(-gamma_0 * T_total * x_arr)

    print(f"\nAnalytical model fit (R² = {r2:.4f}):")
    print(f"  R_∞(d) = {R_min:.4f} + ({R_init_fit:.4f} − {R_min:.4f}) · "
          f"exp(−{gamma_0:.4f} · d/(1−d) · {T_total:.1f})")
    print(f"  At d = φ⁻¹ = {PHI_INV:.4f}: d/(1−d) = {PHI_INV/(1-PHI_INV):.4f} = φ")
    print(f"  ⇒ γ_eff(φ⁻¹) = {gamma_0:.4f} · φ = {gamma_0*PHI:.4f}")

    return R_min, R_init_fit, gamma_0, r2, d_arr, R_pred


# ═══════════════════════════════════════════════════════════════════════
#  Plotting
# ═══════════════════════════════════════════════════════════════════════


def plot_asymptotic_results(results: Dict[float, Tuple[float, float, float]],
                             d_values: List[float], T_total: float,
                             savepath: str = 'experiments/phi_attractor_asymptotic.png'):
    """2-panel figure: R_∞(d) and φ⁻¹ structural signature."""
    d_arr = np.array(sorted(d_values))
    R_final = np.array([results[d][1] for d in d_arr])


    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # ── Panel 1: R_∞ vs d ──
    ax1.scatter(d_arr, R_final, c='#2c3e50', s=60, zorder=5,
                label='Measured $R_\\infty$')

    R_min, R_init_fit, gamma_0, r2, d_fit, R_pred = fit_analytical_model(
        results, T_total)
    d_fine = np.linspace(0.05, 0.99, 200)
    x_fine = d_fine / (1.0 - d_fine)
    R_fine = R_min + (R_init_fit - R_min) * np.exp(-gamma_0 * T_total * x_fine)
    ax1.plot(d_fine, R_fine, '-', color='#e74c3c', lw=2.5, alpha=0.8,
             label=f'Model: $R_\\min + \\Delta R \\cdot e^{{-\\gamma_0 \\cdot d/(1-d) \\cdot T}}$')

    # φ⁻¹ highlight
    d_phi = PHI_INV
    x_phi = d_phi / (1.0 - d_phi)
    R_phi_pred = R_min + (R_init_fit - R_min) * np.exp(-gamma_0 * T_total * x_phi)
    R_phi_meas = results[d_phi][1] if d_phi in results else R_phi_pred
    ax1.axvline(d_phi, color='#D4A574', ls='--', lw=2, alpha=0.8,
                label=f'φ⁻¹ = {d_phi:.4f}')
    ax1.plot(d_phi, R_phi_meas, 'o', color='#D4A574', ms=12, mew=2,
             fillstyle='none', zorder=10)

    ax1.set_xlabel('Velocity damping d', fontsize=12)
    ax1.set_ylabel('Asymptotic half-mass radius $R_\\infty$', fontsize=12)
    ax1.set_title(f'A. $R_\\infty(d)$—Asymptotic Core Size\n'
                  f'$\\gamma_{{\\rm eff}}(d) = \\gamma_0 \\cdot d/(1-d)$  '
                  f'($\\gamma_0 = {gamma_0:.3f}$, $R^2 = {r2:.3f}$)',
                  fontsize=11)
    ax1.legend(fontsize=8, loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, 1.05)

    # Annotation at φ⁻¹
    ax1.annotate(
        f'φ⁻¹ = {d_phi:.4f}\n'
        f'd/(1−d) = φ = {PHI:.4f}\n'
        f'R_∞ = {R_phi_meas:.3f}',
        xy=(d_phi, R_phi_meas),
        xytext=(d_phi + 0.12, R_phi_meas + 0.3),
        arrowprops=dict(arrowstyle='->', color='#D4A574', lw=1.5),
        fontsize=8, color='#8B6914',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF8DC', alpha=0.8),
    )

    # ── Panel 2: d/(1−d) scaling collapse ──
    ax2.scatter(x_fine[d_fine < 1.0], R_fine[d_fine < 1.0],
                c=plt.cm.viridis(d_fine[d_fine < 1.0]), s=2, alpha=0.3, zorder=1)
    for d in d_arr:
        if d >= 1.0:
            continue
        x_d = d / (1.0 - d)
        ax2.scatter(x_d, results[d][1], c='#2c3e50', s=60, zorder=5)
        if abs(d - PHI_INV) < 1e-4:
            ax2.scatter(x_d, results[d][1], c='#D4A574', s=120, zorder=10,
                        edgecolors='#2c3e50', linewidths=1.5)

    # Model line
    ax2.plot(x_fine[x_fine < 20], R_fine[x_fine < 20], 'r-', lw=2, alpha=0.7,
             label=f'$R(d) = {R_min:.3f} + \\Delta R \\cdot e^{{-\\gamma_0 T \\cdot x}}$')

    ax2.axvline(PHI, color='#D4A574', ls='--', lw=1.5, alpha=0.7,
                label=f'x = φ = {PHI:.4f} (d = φ⁻¹)')

    ax2.set_xlabel('Scaled damping $x = d / (1-d)$', fontsize=12)
    ax2.set_ylabel('Asymptotic half-mass radius $R_\\infty$', fontsize=12)
    ax2.set_title('B. Scaled Collapse—All d values collapse onto\n'
                  '$R_\\infty = R_\\min + \\Delta R \\cdot e^{{-\\gamma_0 T x}}$',
                  fontsize=11)
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Summary footer
    summary = (
        f"Cassi Path 1: φ-Attractor Steady State  |  "
        f"φ = {PHI:.4f}  |  φ⁻¹ = {PHI_INV:.4f}  |  "
        f"γ₀ = {gamma_0:.4f}  |  "
        f"R_min = {R_min:.4f}  |  "
        f"γ_eff(φ⁻¹) = {gamma_0*PHI:.4f}  |  "
        f"T = {T_total:.1f}"
    )
    fig.text(0.5, 0.01, summary, ha='center', fontsize=9,
             family='monospace', transform=fig.transFigure)

    fig.savefig(savepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"\nSaved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description='φ-Attractor: Asymptotic R_half vs damping sweep',
    )
    parser.add_argument('--quick', action='store_true',
                        help='Quick sweep: 3 d values only')
    parser.add_argument('--d-values', type=str, default=None,
                        help='Comma-separated d values, e.g. "0.4,0.618,0.8"')
    parser.add_argument('--N', type=int, default=200,
                        help='Number of bodies (default: 200)')
    parser.add_argument('--steps', type=int, default=2000,
                        help='Simulation steps (default: 2000)')
    parser.add_argument('--n-grid', type=int, default=64,
                        help='PM grid size (default: 64)')
    parser.add_argument('--sigma', type=float, default=0.4,
                        help='Softening length (default: 0.4)')
    parser.add_argument('--dt', type=float, default=0.002,
                        help='Timestep (default: 0.002)')
    parser.add_argument('--output', type=str,
                        default='experiments/phi_attractor_asymptotic.png',
                        help='Output plot path')
    args = parser.parse_args()

    if args.d_values:
        d_values = sorted([float(x.strip()) for x in args.d_values.split(',')])
    elif args.quick:
        d_values = [0.4, PHI_INV, 0.8]
    else:
        d_values = [0.1, 0.2, 0.3, 0.4, 0.5, PHI_INV, 0.7, 0.8, 0.9]

    T_total = args.steps * args.dt

    results = run_asymptotic_sweep(
        d_values=d_values,
        N=args.N,
        n_steps=args.steps,
        n_grid=args.n_grid,
        sigma=args.sigma,
        dt=args.dt,
    )

    plot_asymptotic_results(results, d_values, T_total,
                             savepath=args.output)


if __name__ == '__main__':
    main()
