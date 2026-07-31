#!/usr/bin/env python3
r"""Path 2 Validation: Qi-hydrostatic model vs N-body simulation at d = φ⁻¹.

Compares the analytical Qi-hydrostatic equilibrium density profile to an
N-body simulation run at the Cassi canonical damping rate d = φ⁻¹ ≈ 0.618.

The simulation is evolved long enough (N=200, 4000 steps) to reach a relaxed
state. The radial density profile ρ(r), half-mass radius, and velocity
dispersion are extracted from the final snapshot. The Qi-hydrostatic model
is then fitted (by tuning P₀) to match the simulation's R_half, and the
full density profiles are compared on a 2-panel diagnostic figure.

Usage:
    python experiments/path2_validation.py
"""

import math
import sys
import os
import time

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

from experiments.phi_attractor_path2_qi_variational import (
    solve_qi_hydrostatic,
    qi_pressure,
    PHI_INV2,
)

# ═══════════════════════════════════════════════════════════════════════
#  Radial binning utilities
# ═══════════════════════════════════════════════════════════════════════


def compute_center_of_mass(pos: torch.Tensor, masses: torch.Tensor
                           ) -> torch.Tensor:
    """Compute (3,) center of mass vector."""
    total_mass = masses.sum()
    return (masses[:, None] * pos).sum(dim=0) / total_mass


def get_half_mass_radius(pos: torch.Tensor, masses: torch.Tensor) -> float:
    """Half-mass radius from sorted particle radii."""
    com = compute_center_of_mass(pos, masses)
    r = torch.sqrt(((pos - com[None, :]) ** 2).sum(dim=1))
    M = masses.sum().item()
    sorted_idx = torch.argsort(r)
    sorted_r = r[sorted_idx]
    cum_mass = torch.cumsum(masses[sorted_idx], dim=0)
    idx = torch.searchsorted(cum_mass, M / 2.0)
    idx = min(idx.item(), len(r) - 1)
    return sorted_r[idx].item()


def radial_profiles(pos: torch.Tensor, vel: torch.Tensor,
                    masses: torch.Tensor,
                    r_max: float, n_bins: int = 40) -> dict:
    """Bin particles radially and return density + velocity dispersion.

    Args:
        pos: (N, 3) positions
        vel: (N, 3) velocities
        masses: (N,) masses
        r_max: maximum radius for binning
        n_bins: number of spherical shells

    Returns:
        dict with keys:
            r_edges: (n_bins+1,) bin edges
            r_centers: (n_bins,) bin centres
            rho: (n_bins,) mass density in each shell [M / L^3]
            rho_err: (n_bins,) Poisson error estimate on rho
            sigma_v: (n_bins,) velocity dispersion in each shell
            n_particles: (n_bins,) particle count per shell
    """
    com = compute_center_of_mass(pos, masses)
    r = torch.sqrt(((pos - com[None, :]) ** 2).sum(dim=1))
    r_np = r.cpu().numpy()
    vel_np = vel.cpu().numpy()
    masses_np = masses.cpu().numpy()

    r_edges = np.linspace(0.0, r_max, n_bins + 1)
    r_centers = 0.5 * (r_edges[:-1] + r_edges[1:])

    rho = np.zeros(n_bins)
    rho_err = np.zeros(n_bins)
    sigma_v = np.zeros(n_bins)
    n_particles = np.zeros(n_bins, dtype=int)

    for i in range(n_bins):
        lo, hi = r_edges[i], r_edges[i + 1]
        mask = (r_np >= lo) & (r_np < hi)
        n = mask.sum()
        n_particles[i] = n
        if n == 0:
            rho[i] = 0.0
            rho_err[i] = 0.0
            sigma_v[i] = 0.0
            continue

        shell_mass = masses_np[mask].sum()
        shell_vol = (4.0 / 3.0) * np.pi * (hi ** 3 - lo ** 3)
        rho[i] = shell_mass / shell_vol if shell_vol > 0 else 0.0

        # Poisson noise: dN / N uncertainty
        if n > 0:
            rho_err[i] = rho[i] / math.sqrt(n)

        # Velocity dispersion in shell
        shell_vel = vel_np[mask]
        v_com = shell_vel.mean(axis=0)
        v_disp = shell_vel - v_com[None, :]
        sigma_v_sq = (masses_np[mask, None] * v_disp ** 2).sum() / shell_mass
        sigma_v[i] = math.sqrt(max(sigma_v_sq, 0.0))

    return {
        'r_edges': r_edges,
        'r_centers': r_centers,
        'rho': rho,
        'rho_err': rho_err,
        'sigma_v': sigma_v,
        'n_particles': n_particles,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Simulation runner
# ═══════════════════════════════════════════════════════════════════════


def run_phi_damped_simulation(N: int = 200, n_steps: int = 4000,
                              dt: float = 0.002, n_grid: int = 64,
                              sigma: float = 0.4, L: float = 20.0,
                              seed: int = 42, verbose: bool = True) -> dict:
    """Run φ-damped N-body simulation at d=φ⁻¹.

    Returns dict with final snapshot and diagnostics.
    """
    device = get_device()
    config = NBodyConfig(
        n_grid=n_grid, L=L, G=1.0, sigma=sigma,
        dt=dt, n_steps=n_steps, vel_damp=PHI_INV,
        deposition_kernel='CIC', device=device,
    )

    if verbose:
        print(f"Device: {device}")
        print(f"N = {N}, steps = {n_steps}, dt = {dt}")
        print(f"d = φ⁻¹ = {PHI_INV:.4f}")
        print(f"Grid: {n_grid}^3, L = {L}, sigma = {sigma}")
        print(f"T_total = {n_steps * dt:.1f}")
        print("-" * 60)

    # Initial conditions: Plummer sphere
    pos, vel, masses = plummer_sphere(N, 2.0, config, seed=seed)
    pos, vel, masses = pos.to(device), vel.to(device), masses.to(device)

    solver = NBodySolver3D(
        n_grid=config.n_grid, L=config.L, G=config.G,
        sigma=config.sigma, device=device,
        qi_gate=False, deposition_kernel=config.deposition_kernel,
    )

    # Measure initial R_half
    rh_init = get_half_mass_radius(pos, masses)
    if verbose:
        print(f"R_half_initial = {rh_init:.4f}")

    t0 = time.time()
    accel = None

    for step in range(n_steps):
        pos, vel, accel, _, _ = solver.leapfrog_step(
            pos, vel, masses, config.dt, accel=accel,
            vel_damp=PHI_INV, qi_gate=False,
        )

        if verbose and (step + 1) % 500 == 0:
            KE, PE, _ = solver.compute_energy(pos, vel, masses)
            rh = get_half_mass_radius(pos, masses)
            Q = 2.0 * KE / (abs(PE) + 1e-10)
            print(f"  step {step + 1:5d}/{n_steps}  |  "
                  f"E = {KE + PE:+.4f}  |  Q = {Q:.4f}  |  "
                  f"R_half = {rh:.4f}")

    elapsed = time.time() - t0

    # Final diagnostics
    rh_final = get_half_mass_radius(pos, masses)
    KE, PE, E_tot = solver.compute_energy(pos, vel, masses)

    if verbose:
        print(f"\n  Wall time: {elapsed:.1f}s")
        print(f"  R_half_initial = {rh_init:.4f}")
        print(f"  R_half_final   = {rh_final:.4f}")
        print(f"  KE = {KE:.4f}, PE = {PE:.4f}, E_tot = {E_tot:.4f}")
        print(f"  Virial Q = {2.0 * KE / (abs(PE) + 1e-10):.4f}")

    # Extract radial profile (use r_max = L/4 ≈ 5.0)
    r_max = L / 4.0
    n_bins = max(40, int(r_max / 0.12))  # ~0.12 bin width
    prof = radial_profiles(pos, vel, masses, r_max, n_bins)

    return {
        'pos': pos.cpu().numpy(),
        'vel': vel.cpu().numpy(),
        'masses': masses.cpu().numpy(),
        'rh_init': rh_init,
        'rh_final': rh_final,
        'KE': KE,
        'PE': PE,
        'E_tot': E_tot,
        'profile': prof,
        'N': N,
        'n_steps': n_steps,
        'dt': dt,
        'seed': seed,
        'wall_time': elapsed,
    }


# ═══════════════════════════════════════════════════════════════════════
#  P0 tuning
# ═══════════════════════════════════════════════════════════════════════


def tune_p0(M_tot: float, r_max: float, target_rhalf: float,
            n_radial: int = 300, sigma: float = 0.4,
            p0_guesses: list = None) -> tuple:
    """Brute-force search P₀ so model R_half matches target.

    Returns (best_P0, (r_grid, rho_best, P_best), search_log, is_boundary).
    """
    if p0_guesses is None:
        p0_guesses = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0,
                      7.0, 10.0, 15.0, 20.0, 30.0, 50.0, 70.0, 100.0,
                      150.0, 200.0, 300.0, 500.0, 700.0, 1000.0,
                      1500.0, 2000.0, 3000.0, 5000.0, 7000.0, 10000.0]

    best_p0 = None
    best_rh = None
    best_result = None
    best_diff = float('inf')
    search_log = []

    print(f"\n{'=' * 60}")
    print(f"  Tuning P₀ to match R_half = {target_rhalf:.4f}")
    print(f"  {'─' * 58}")
    print(f"  {'P₀':>8s}  {'R_half':>10s}  {'ρ(0)':>10s}  {'ΔR/R':>10s}")
    print(f"  {'─' * 42}")

    for p0 in p0_guesses:
        # Suppress the divide-by-zero from solve_qi_hydrostatic's internal R_half calc
        with np.errstate(all='ignore'):
            r_grid, rho, P = solve_qi_hydrostatic(
                M_tot=M_tot,
                r_max=r_max,
                n_radial=n_radial,
                sigma=sigma,
                P0=p0,
            )

        # Skip failed integrations (density zeroed out too early)
        if np.all(rho < 1e-12) or r_grid[-1] < 0.1:
            search_log.append((p0, np.nan, 0.0, np.nan))
            print(f"  {p0:8.3f}  {'FAIL':>10s}  {'—':>10s}  {'—':>10s}")
            continue

        # Compute R_half from model
        cum = np.cumsum(rho * r_grid ** 2)
        total_mass_model = cum[-1]
        if total_mass_model <= 0:
            search_log.append((p0, np.nan, rho[0], np.nan))
            print(f"  {p0:8.3f}  {'NO MASS':>10s}  {rho[0]:10.2f}  {'—':>10s}")
            continue

        rh_model = np.interp(0.5, cum / total_mass_model, r_grid)
        if np.isnan(rh_model):
            search_log.append((p0, np.nan, rho[0], np.nan))
            print(f"  {p0:8.3f}  {'NAN':>10s}  {rho[0]:10.2f}  {'—':>10s}")
            continue

        rho0_model = rho[0]
        diff = abs(rh_model - target_rhalf) / target_rhalf
        search_log.append((p0, rh_model, rho0_model, diff))
        print(f"  {p0:8.3f}  {rh_model:10.4f}  {rho0_model:10.2f}  {diff:10.4f}")

        if diff < best_diff:
            best_diff = diff
            best_p0 = p0
            best_rh = rh_model
            best_result = (r_grid, rho, P)

    print(f"  {'─' * 42}")
    if best_p0 is not None:
        print(f"  Best: P₀ = {best_p0:.4f}, R_half = {best_rh:.4f} "
              f"(Δ = {best_diff * 100:.2f}%)")
    else:
        print(f"  No valid P₀ found in search range")

    # Detect boundary solution: best P₀ at search edge
    max_p0 = max(p0_guesses)
    is_boundary = best_p0 is not None and best_p0 >= max_p0 * 0.99
    if is_boundary:
        print(f"  ⚠  P₀ = {best_p0:.1f} is at the upper search bound.")
        print(f"     The model R_half has a lower bound (~1.84 for M=200)")
        print(f"     due to the fixed central density heuristic in")
        print(f"     solve_qi_hydrostatic (ρ(0) ≈ "
              f"{M_tot/(4*np.pi*r_max**3/3)*10:.2f}).")
        print(f"     Simulation R_half ({target_rhalf:.3f}) is below this "
              f"bound—the cold-damped system is not in hydrostatic "
              f"equilibrium (Q ≈ 0).")

    return best_p0, best_result, search_log, is_boundary


# ═══════════════════════════════════════════════════════════════════════
#  Plotting
# ═══════════════════════════════════════════════════════════════════════


def make_validation_figure(sim_data: dict,
                           r_grid: np.ndarray, rho_model: np.ndarray,
                           best_p0: float,
                           savepath: str = 'experiments/path2_validation.png'
                           ) -> None:
    """2-panel diagnostic: density profile + residuals."""
    prof = sim_data['profile']
    r = prof['r_centers']
    rho_sim = prof['rho']
    rho_err = prof['rho_err']
    rh_sim = sim_data['rh_final']

    # Filter out empty bins
    ok_sim = rho_sim > 0
    r_filt = r[ok_sim]
    rho_filt = rho_sim[ok_sim]
    rho_err_filt = rho_err[ok_sim]

    # Compute R_half from model
    cum = np.cumsum(rho_model * r_grid ** 2)
    rh_model = np.interp(0.5, cum / cum[-1], r_grid)

    # φ⁻² crossing radius
    r_cross = np.interp(PHI_INV2, rho_model[::-1], r_grid[::-1])

    # Interpolate model onto simulation bins
    rho_model_at_sim = np.interp(r, r_grid, rho_model,
                                 left=rho_model[0], right=0.0)
    with np.errstate(all='ignore'):
        raw_res = (rho_sim - rho_model_at_sim) / rho_model_at_sim
    residual = np.where(rho_model_at_sim > 0, raw_res, 0.0)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12),
                                    height_ratios=[2, 1])

    # ═══════════════════════════════════════════════════════════════════
    # Panel A: Density profiles (log-log)
    # ═══════════════════════════════════════════════════════════════════
    ax1.errorbar(r_filt, rho_filt, yerr=rho_err_filt,
                 fmt='o', c='#2c3e50', ms=4, capsize=2, capthick=1,
                 lw=1, alpha=0.8, label='N-body simulation (binned)',
                 ecolor='#7f8c8d', elinewidth=0.8)

    ax1.loglog(r_grid, rho_model, 'r-', lw=2.5, alpha=0.9,
               label=f'Qi-hydrostatic (P₀ = {best_p0:.2f})')

    # φ⁻² horizontal reference line
    ax1.axhline(PHI_INV2, color='#D4A574', ls=':', lw=2, alpha=0.9,
                label=f'φ⁻² = {PHI_INV2:.4f}')

    # Crossing radius r(ρ = φ⁻²)
    ax1.axvline(r_cross, color='#D4A574', ls='--', lw=1.5, alpha=0.7)
    ax1.annotate(f'r(ρ=φ⁻²) = {r_cross:.3f}',
                 xy=(r_cross, PHI_INV2),
                 xytext=(r_cross * 1.5, PHI_INV2 * 3),
                 arrowprops=dict(arrowstyle='->', color='#D4A574', lw=1.2),
                 fontsize=9, color='#8B6914',
                 bbox=dict(boxstyle='round,pad=0.3',
                           facecolor='#FFF8DC', alpha=0.8))

    # Annotate R_half positions
    y_annot = max(rho_filt) * 0.1
    ax1.axvline(rh_sim, color='#2c3e50', ls='--', lw=1, alpha=0.5)
    ax1.text(rh_sim * 1.05, y_annot,
             f'R_half (sim) = {rh_sim:.3f}',
             rotation=90, fontsize=8, color='#2c3e50', alpha=0.7)

    ax1.axvline(rh_model, color='red', ls='--', lw=1, alpha=0.5)
    ax1.text(rh_model * 1.05, y_annot * 0.6,
             f'R_half (model) = {rh_model:.3f}',
             rotation=90, fontsize=8, color='red', alpha=0.7)

    ax1.set_xlabel('Radius r', fontsize=12)
    ax1.set_ylabel('Density ρ(r)', fontsize=12)
    ax1.set_title(
        f'A. Density Profile—N-body (d=φ⁻¹={PHI_INV:.4f}) vs '
        f'Qi-Hydrostatic Model\n'
        f'M = {sim_data["N"]}, steps = {sim_data["n_steps"]}, '
        f'dt = {sim_data["dt"]}, T = '
        f'{sim_data["n_steps"] * sim_data["dt"]:.1f}',
        fontsize=11
    )
    ax1.legend(fontsize=9, loc='upper right')
    ax1.grid(True, alpha=0.3, which='both')
    ax1.set_xlim(r_grid[1] if r_grid[0] == 0 else r_grid[0] * 0.9,
                 r_grid[-1] * 1.05)

    # ═══════════════════════════════════════════════════════════════════
    # Panel B: Residuals
    # ═══════════════════════════════════════════════════════════════════
    ok_res = rho_model_at_sim > 0
    r_res = r[ok_res]
    res_vals = residual[ok_res]

    ax2.axhline(0, color='gray', ls='-', lw=1, alpha=0.5)
    ax2.axhline(0.1, color='gray', ls=':', lw=0.7, alpha=0.3)
    ax2.axhline(-0.1, color='gray', ls=':', lw=0.7, alpha=0.3)

    if len(res_vals) > 0:
        rms_res = np.sqrt(np.mean(res_vals ** 2)) * 100
        ax2.semilogx(r_res, res_vals, 'o-', c='#c0392b', ms=4,
                     lw=1.2, alpha=0.8,
                     label=f'RMS residual = {rms_res:.1f}%')
    else:
        rms_res = 0.0
        ax2.text(0.5, 0.5, 'No overlapping bins',
                 ha='center', va='center',
                 transform=ax2.transAxes, fontsize=12)

    ax2.axvline(rh_sim, color='#2c3e50', ls='--', lw=1, alpha=0.4)
    ax2.axvline(r_cross, color='#D4A574', ls='--', lw=1, alpha=0.6)
    ax2.text(r_cross, ax2.get_ylim()[1] * 0.9, 'r(ρ=φ⁻²)',
             fontsize=8, color='#8B6914', ha='center')

    ax2.set_xlabel('Radius r', fontsize=12)
    ax2.set_ylabel('(ρ_sim − ρ_model) / ρ_model', fontsize=12)
    ax2.set_title('B. Fractional Residuals', fontsize=11)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(r_grid[1] if r_grid[0] == 0 else r_grid[0] * 0.9,
                 r_grid[-1] * 1.05)

    # Summary text
    summary = (
        f"Path 2 Validation  |  d = φ⁻¹ = {PHI_INV:.4f}  |  "
        f"Best P₀ = {best_p0:.3f}  |  "
        f"R_half: sim={rh_sim:.3f}  model={rh_model:.3f}  |  "
        f"RMS residual = {rms_res:.1f}%"
    )
    fig.text(0.5, 0.01, summary, ha='center', fontsize=10,
             family='monospace', transform=fig.transFigure)

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(savepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"\nSaved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    print("=" * 64)
    print("  Path 2 Validation: Qi-hydrostatic vs N-body Simulation")
    print("=" * 64)

    # ── 1. Run φ-damped simulation ──
    print("\n[1/4] Running φ-damped N-body simulation...")
    sim_data = run_phi_damped_simulation(
        N=200, n_steps=4000, dt=0.002,
        n_grid=64, sigma=0.4, L=20.0, seed=42,
    )
    rh_sim = sim_data['rh_final']
    rho_sim = sim_data['profile']['rho']
    first_ok = np.where(rho_sim > 0)[0]
    rho0_sim = rho_sim[first_ok[0]] if len(first_ok) > 0 else 0.0

    # ── 2. Tune P₀ ──
    print("\n[2/4] Tuning P₀ to match simulation R_half...")
    r_max = 5.0
    best_p0, best_result, search_log, is_boundary = tune_p0(
        M_tot=float(sim_data['N']),
        r_max=r_max,
        target_rhalf=rh_sim,
        n_radial=300,
        sigma=0.4,
    )

    if best_result is not None:
        r_grid, rho_model, P_model = best_result

        # Model diagnostics
        cum = np.cumsum(rho_model * r_grid ** 2)
        rh_model = np.interp(0.5, cum / cum[-1], r_grid)
        rho0_model = rho_model[0]
        r_cross = np.interp(PHI_INV2, rho_model[::-1], r_grid[::-1])

        # RMS residual (only where both sim and model have positive density)
        r_sim = sim_data['profile']['r_centers']
        with np.errstate(all='ignore'):
            rho_model_interp = np.interp(r_sim, r_grid, rho_model,
                                          left=rho_model[0], right=0.0)
        ok = (rho_sim > 0) & (rho_model_interp > 0)
        rms_res = np.nan
        if ok.any():
            res = (rho_sim[ok] - rho_model_interp[ok]) / rho_model_interp[ok]
            rms_res = float(np.sqrt(np.mean(res ** 2)) * 100)
    else:
        # Fallback: use last successful model (or a dummy)
        r_grid = np.linspace(0, r_max, 300)
        rho_model = np.zeros_like(r_grid)
        rh_model = 0.0
        rho0_model = 0.0
        r_cross = r_max
        rms_res = np.nan
        is_boundary = False

    # ── 3. Print diagnostics ──
    print("\n[3/4] Diagnostics")
    print("=" * 60)
    print(f"  Best-fit P₀                 = "
          f"{best_p0 if best_p0 is not None else 'N/A'}")
    print(f"  Central density ρ(0):")
    print(f"    Simulation (first bin)    = {rho0_sim:.4f}")
    print(f"    Model                     = {rho0_model:.4f}")
    if rho0_sim > 0:
        print(f"    Ratio ρ_model/ρ_sim       = "
              f"{rho0_model / rho0_sim:.4f}")
    print(f"  Half-mass radius R_half:")
    print(f"    Simulation                = {rh_sim:.4f}")
    print(f"    Model                     = {rh_model:.4f}")
    if rh_sim > 0:
        print(f"    ΔR/R_sim                  = "
              f"{abs(rh_model - rh_sim) / rh_sim * 100:.2f}%")
    print(f"  r(ρ = φ⁻²)                  = {r_cross:.4f}")
    if not np.isnan(rms_res):
        print(f"  RMS residual                 = {rms_res:.2f}%")
    if is_boundary:
        print(f"  ⚠  Boundary solution: P₀ at upper search bound.")
        print(f"     Model R_half cannot reach sim R_half due to")
        print(f"     fixed ρ(0) in solve_qi_hydrostatic.")
        print(f"     Cold collapse (Q ≈ 0) ≠ hydrostatic equilibrium.")
    print("=" * 60)

    # ── 4. Plot ──
    print("\n[4/4] Generating figure...")
    make_validation_figure(
        sim_data,
        r_grid, rho_model,
        best_p0 if best_p0 is not None else 0.0,
        savepath='experiments/path2_validation.png',
    )

    print("\nDone.")


if __name__ == '__main__':
    main()
