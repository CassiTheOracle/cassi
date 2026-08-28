#!/usr/bin/env python3
r"""Path 3: Cold Collapse—φ-Damped N-body from Hot to Cold.

Quantifies how a φ-damped N-body system transitions from virial equilibrium
(Q ≈ 1, "hot") to a cold, over-contracted state (Q ≈ 0).

At d = φ⁻¹ ≈ 0.618, each step damps 38.2 % of the velocity, extracting
kinetic energy faster than gravity can regenerate it through contraction.
This produces a characteristic cold-collapse trajectory connecting the
initial Plummer equilibrium to a frozen, ultra-dense configuration.

Key observables:
  - Virial ratio Q(t) = 2K/|W|—collapses from 1 → 0
  - Half-mass radius R_half(t)—contracts from ∼2.0 → ∼1.2
  - Central density ρ_center(t)—rises by several orders of magnitude
  - Velocity dispersion σ_v(t)—traces the damping
  - Qi coherence q_mean(t)—measures structural stiffness

Analytical picture:
  dK/dt = -(1-d²)·K/dt + (GM²/2R²)·dR/dt
  → Quasi-steady Q_∞(d), R_half ∝ t^α in the late phase.

Usage:
    python experiments/path3_cold_collapse.py
"""

import math
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "two-fluid")))

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

PHI_INV2 = PHI_INV ** 2  # ≈ 0.382


# ═══════════════════════════════════════════════════════════════════════
#  Particle-level diagnostics
# ═══════════════════════════════════════════════════════════════════════


def compute_center_of_mass(pos: torch.Tensor, masses: torch.Tensor
                           ) -> torch.Tensor:
    """(3,) centre of mass vector."""
    return (masses[:, None] * pos).sum(dim=0) / masses.sum()


def get_half_mass_radius(pos: torch.Tensor, masses: torch.Tensor) -> float:
    """R_half from sorted particle radii (COM-centred)."""
    com = compute_center_of_mass(pos, masses)
    r = torch.sqrt(((pos - com[None, :]) ** 2).sum(dim=1))
    M = masses.sum().item()
    sorted_idx = torch.argsort(r)
    sorted_r = r[sorted_idx]
    cum_mass = torch.cumsum(masses[sorted_idx], dim=0)
    idx = torch.searchsorted(cum_mass, M / 2.0)
    return sorted_r[min(idx.item(), len(r) - 1)].item()


def compute_rms_velocity(vel: torch.Tensor) -> float:
    """Mass-weighted RMS speed."""
    return math.sqrt((vel ** 2).sum(dim=1).mean().item())


def compute_central_density(pos: torch.Tensor, masses: torch.Tensor,
                            r_small: float = 0.2) -> float:
    """Density within a small sphere of radius r_small around the COM."""
    com = compute_center_of_mass(pos, masses)
    r = torch.sqrt(((pos - com[None, :]) ** 2).sum(dim=1))
    mask = r < r_small
    n_inside = mask.sum().item()
    if n_inside == 0:
        return 0.0
    m_inside = masses[mask].sum().item()
    vol = (4.0 / 3.0) * math.pi * r_small ** 3
    return m_inside / vol


def compute_q_mean_from_grid(rho_grid: torch.Tensor) -> float:
    """Mean Qi coherence ⟨ρ/(ρ+φ⁻²)⟩ over non-vacuum cells."""
    if rho_grid is None or rho_grid.numel() == 0:
        return 1.0
    q = rho_grid / (rho_grid + PHI_INV2 + 1e-12)
    rho_max = rho_grid.max().item()
    if rho_max <= 0:
        return 1.0
    non_vac = rho_grid > 0.01 * rho_max
    if not non_vac.any():
        return 1.0
    return q[non_vac].mean().item()


# ═══════════════════════════════════════════════════════════════════════
#  Simulation runner with full trajectory tracking
# ═══════════════════════════════════════════════════════════════════════


def run_cold_collapse(N: int = 200, n_steps: int = 4000,
                      dt: float = 0.002, n_grid: int = 64,
                      sigma: float = 0.4, L: float = 20.0,
                      seed: int = 42, track_every: int = 10,
                      vel_damp: float = None,
                      verbose: bool = True) -> dict:
    """Run φ-damped N-body sim and track collapse trajectory.

    Args:
        vel_damp: velocity damping factor per step.
                  Defaults to PHI_INV (φ⁻¹ ≈ 0.618).

    Returns a dict with full time series and final snapshot.
    """
    if vel_damp is None:
        vel_damp = PHI_INV
    device = get_device()
    config = NBodyConfig(
        n_grid=n_grid, L=L, G=1.0, sigma=sigma,
        dt=dt, n_steps=n_steps, vel_damp=vel_damp,
        deposition_kernel='CIC', device=device,
    )

    if verbose:
        print(f"Device: {device}")
        print(f"N = {N}, steps = {n_steps}, dt = {dt}")
        print(f"d = {vel_damp:.4f}  (γ_eff = d/(1-d) = "
              f"{vel_damp/(1-vel_damp):.4f})")
        print(f"Grid: {n_grid}^3, L = {L}, sigma = {sigma}")
        print(f"T_total = {n_steps * dt:.1f}")
        print(f"Tracking every {track_every} steps")
        print("-" * 60)

    # Create ICs
    pos, vel, masses = plummer_sphere(N, 2.0, config, seed=seed)
    pos, vel, masses = pos.to(device), vel.to(device), masses.to(device)

    solver = NBodySolver3D(
        n_grid=config.n_grid, L=config.L, G=config.G,
        sigma=config.sigma, device=device,
        qi_gate=False, deposition_kernel=config.deposition_kernel,
    )

    # Storage for time series
    n_track = n_steps // track_every + 1
    t_arr = np.zeros(n_track)
    Q_arr = np.zeros(n_track)
    KE_arr = np.zeros(n_track)
    PE_arr = np.zeros(n_track)
    rh_arr = np.zeros(n_track)
    sigma_v_arr = np.zeros(n_track)
    rho_center_arr = np.zeros(n_track)
    q_mean_arr = np.zeros(n_track)

    t0 = time.time()
    accel = None
    idx = 0

    # Initial snapshot
    KE, PE, _ = solver.compute_energy(pos, vel, masses)
    rh = get_half_mass_radius(pos, masses)
    sv = compute_rms_velocity(vel)
    rc = compute_central_density(pos, masses)
    rho_grid = solver.deposit_density(pos, masses)
    qm = compute_q_mean_from_grid(rho_grid)

    t_arr[idx] = 0.0
    KE_arr[idx] = KE
    PE_arr[idx] = PE
    Q_arr[idx] = 2.0 * KE / (abs(PE) + 1e-10)
    rh_arr[idx] = rh
    sigma_v_arr[idx] = sv
    rho_center_arr[idx] = rc
    q_mean_arr[idx] = qm
    idx += 1

    if verbose:
        print(f"  t={0:8.4f}  Q={Q_arr[0]:.4f}  R_half={rh:.4f}  "
              f"σ_v={sv:.4f}  ρ_c={rc:.2f}  q̄={qm:.4f}")

    for step in range(n_steps):
        pos, vel, accel, _, _ = solver.leapfrog_step(
            pos, vel, masses, config.dt, accel=accel,
            vel_damp=vel_damp, qi_gate=False,
        )

        if (step + 1) % track_every == 0:
            phys_t = (step + 1) * dt
            KE, PE, _ = solver.compute_energy(pos, vel, masses)
            rh = get_half_mass_radius(pos, masses)
            sv = compute_rms_velocity(vel)
            rc = compute_central_density(pos, masses)
            rho_grid = solver.deposit_density(pos, masses)
            qm = compute_q_mean_from_grid(rho_grid)

            t_arr[idx] = phys_t
            KE_arr[idx] = KE
            PE_arr[idx] = PE
            Q_arr[idx] = 2.0 * KE / (abs(PE) + 1e-10)
            rh_arr[idx] = rh
            sigma_v_arr[idx] = sv
            rho_center_arr[idx] = rc
            q_mean_arr[idx] = qm

            if verbose and (step + 1) % 500 == 0:
                print(f"  t={phys_t:8.4f}  Q={Q_arr[idx]:.4f}  "
                      f"R_half={rh:.4f}  σ_v={sv:.4f}  "
                      f"ρ_c={rc:.2f}  q̄={qm:.4f}")

            idx += 1

    elapsed = time.time() - t0

    # Trim arrays to actual tracked length
    n_actual = idx
    t_arr = t_arr[:n_actual]
    Q_arr = Q_arr[:n_actual]
    KE_arr = KE_arr[:n_actual]
    PE_arr = PE_arr[:n_actual]
    rh_arr = rh_arr[:n_actual]
    sigma_v_arr = sigma_v_arr[:n_actual]
    rho_center_arr = rho_center_arr[:n_actual]
    q_mean_arr = q_mean_arr[:n_actual]

    if verbose:
        print(f"\n  Wall time: {elapsed:.1f}s  |  "
              f"{elapsed / n_steps * 1000:.2f} ms/step")
        print(f"  Tracked {n_actual} snapshots")

    return {
        't': t_arr,
        'Q': Q_arr,
        'KE': KE_arr,
        'PE': PE_arr,
        'R_half': rh_arr,
        'sigma_v': sigma_v_arr,
        'rho_center': rho_center_arr,
        'q_mean': q_mean_arr,
        'vel_damp': vel_damp,
        'pos': pos.cpu().numpy(),
        'vel': vel.cpu().numpy(),
        'masses': masses.cpu().numpy(),
        'N': N,
        'n_steps': n_steps,
        'dt': dt,
        'seed': seed,
        'wall_time': elapsed,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Analysis
# ═══════════════════════════════════════════════════════════════════════


def fit_contraction_power_law(t: np.ndarray, R_half: np.ndarray,
                              t_min_frac: float = 0.3
                              ) -> tuple:
    """Fit R_half ∝ t^α in the late-time regime.

    Uses data for t > t_min_frac * t_max (the late third by default).
    Returns (alpha, alpha_err, t_fit, R_fit).
    """
    mask = t > t_min_frac * t[-1]
    t_late = t[mask]
    rh_late = R_half[mask]

    if len(t_late) < 5:
        return 0.0, 0.0, np.array([]), np.array([])

    log_t = np.log(t_late)
    log_rh = np.log(rh_late)

    coeffs, cov = np.polyfit(log_t, log_rh, 1, cov=True)
    alpha = coeffs[0]
    alpha_err = math.sqrt(cov[0, 0]) if cov.shape == (2, 2) else 0.0

    # Predicted line
    t_fit = np.logspace(np.log10(t_late[0]), np.log10(t_late[-1]), 100)
    R_fit = np.exp(coeffs[1]) * t_fit ** alpha

    return alpha, alpha_err, t_fit, R_fit


def compute_effective_gamma(t: np.ndarray, R_half: np.ndarray
                            ) -> tuple:
    """d(ln R_half) / d(ln t) via Savitzky-Golay-style local fits.

    Returns (gamma, t_gamma) where gamma is the local slope.
    """
    log_t = np.log(np.maximum(t, 1e-10))
    log_rh = np.log(np.maximum(R_half, 1e-10))

    n = len(t)
    window = max(5, n // 20)  # adaptive window
    gamma = np.full(n, np.nan)
    t_gamma = t.copy()

    for i in range(n):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        if hi - lo < 3:
            continue
        p = np.polyfit(log_t[lo:hi], log_rh[lo:hi], 1)
        gamma[i] = p[0]

    return gamma, t_gamma


# ═══════════════════════════════════════════════════════════════════════
#  Plotting
# ═══════════════════════════════════════════════════════════════════════


def make_cold_collapse_figure(data: dict,
                              savepath: str = 'experiments/'
                                             'path3_cold_collapse.png'
                              ) -> None:
    """3-panel diagnostic figure."""
    t = data['t']
    Q = data['Q']
    R_half = data['R_half']
    rho_c = data['rho_center']
    sigma_v = data['sigma_v']
    q_mean = data['q_mean']

    # Power-law fit
    alpha, alpha_err, t_fit, R_fit = fit_contraction_power_law(t, R_half)
    gamma, t_gamma = compute_effective_gamma(t, R_half)

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))

    # ═══════════════════════════════════════════════════════════════════
    # Panel A: Time evolution
    # ═══════════════════════════════════════════════════════════════════
    ax = axes[0]
    color_Q = '#2c3e50'
    color_rh = '#c0392b'
    color_rho = '#8e44ad'

    ax_twin = ax.twinx()

    # Q(t)
    l1 = ax.plot(t, Q, '-', c=color_Q, lw=2, label='Q(t) = 2K/|W|')
    ax.set_ylabel('Virial ratio Q(t)', color=color_Q, fontsize=12)
    ax.tick_params(axis='y', labelcolor=color_Q)

    # R_half(t)
    l2 = ax_twin.plot(t, R_half, '--', c=color_rh, lw=2,
                      label='R_half(t)')
    ax_twin.set_ylabel('R_half(t)', color=color_rh, fontsize=12)
    ax_twin.tick_params(axis='y', labelcolor=color_rh)

    # ρ_center(t)—log scale, use a second twin or a separate axis
    # Use a separate left axis with log scale
    ax_rho = ax_twin.twinx()
    ax_rho.spines['right'].set_position(('outward', 60))
    l3 = ax_rho.semilogy(t, np.maximum(rho_c, 1e-10), ':',
                         c=color_rho, lw=1.5, label='ρ_center(t)')
    ax_rho.set_ylabel('ρ_center(t)', color=color_rho, fontsize=12)
    ax_rho.tick_params(axis='y', labelcolor=color_rho)

    # Combine legends
    lns = l1 + l2 + l3
    labs = [l.get_label() for l in lns]
    ax.legend(lns, labs, fontsize=9, loc='upper right')

    ax.set_xlabel('Time t', fontsize=12)
    ax.set_title('A. Collapse Time Series', fontsize=13)
    ax.grid(True, alpha=0.3)

    # ═══════════════════════════════════════════════════════════════════
    # Panel B: Q vs R_half phase space
    # ═══════════════════════════════════════════════════════════════════
    ax = axes[1]

    # Color by time
    cmap = plt.cm.viridis
    t_norm = t / t[-1] if t[-1] > 0 else np.zeros_like(t)
    colors = cmap(t_norm)

    scatter = ax.scatter(R_half, Q, c=t_norm, cmap=cmap, s=8, alpha=0.8,
                         label='Trajectory')

    # Start and end markers
    ax.scatter(R_half[0], Q[0], c='#2c3e50', s=150, marker='o', zorder=10,
               edgecolors='white', linewidths=2, label=f'Start (t=0)')
    ax.scatter(R_half[-1], Q[-1], c='#c0392b', s=150, marker='s',
              zorder=10, edgecolors='white', linewidths=2,
              label=f'End (t={t[-1]:.2f})')

    # Arrow showing direction
    arrow_idx = max(1, len(R_half) // 4)
    ax.annotate('', xy=(R_half[arrow_idx], Q[arrow_idx]),
                xytext=(R_half[0], Q[0]),
                arrowprops=dict(arrowstyle='->', color='gray',
                                lw=1.5, alpha=0.5))

    ax.set_xlabel('R_half', fontsize=12)
    ax.set_ylabel('Q = 2K/|W|', fontsize=12)
    ax.set_title('B. Phase Space: Q vs R_half', fontsize=13)
    ax.legend(fontsize=9)

    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax, shrink=0.7)
    cbar.set_label('t / T_total', fontsize=9)

    ax.grid(True, alpha=0.3)

    # ═══════════════════════════════════════════════════════════════════
    # Panel C: Contraction power-law index
    # ═══════════════════════════════════════════════════════════════════
    ax = axes[2]

    # Local slope γ(t) = d ln R / d ln t
    ax.plot(t_gamma, gamma, '-', c='#2980b9', lw=2, alpha=0.8,
            label='γ(t) = d ln R_half / d ln t')

    # Power-law fit result for late phase
    if len(t_fit) > 0:
        ax.axhline(alpha, color='#c0392b', ls='--', lw=1.5, alpha=0.7,
                   label=f'Late fit: α = {alpha:.3f} ± {alpha_err:.3f}')
        # Shade the fit region
        t_late_start = t[t > 0.3 * t[-1]][0] if np.any(t > 0.3 * t[-1]) else t[-1] * 0.3
        ax.axvspan(t_late_start, t[-1], color='red', alpha=0.05)

    ax.axhline(0, color='gray', ls=':', lw=0.7)

    ax.set_xlabel('Time t', fontsize=12)
    ax.set_ylabel('γ = d ln R_half / d ln t', fontsize=12)
    ax.set_title(f'C. Contraction Power-Law Index\n'
                 f'Late α = {alpha:.3f} ± {alpha_err:.3f}',
                 fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Summary
    summary = (
        f"Cold Collapse  |  d = φ⁻¹ = {PHI_INV:.4f}  |  "
        f"N = {data['N']}  |  "
        f"Q: {Q[0]:.4f} → {Q[-1]:.4f}  |  "
        f"R_half: {R_half[0]:.3f} → {R_half[-1]:.3f}  |  "
        f"α = {alpha:.3f}"
    )
    fig.text(0.5, 0.01, summary, ha='center', fontsize=10,
             family='monospace', transform=fig.transFigure)

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(savepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"\nSaved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
#  Sweep analysis & fitting
# ═══════════════════════════════════════════════════════════════════════


def fit_q_efold(t: np.ndarray, Q: np.ndarray,
                t_min_frac: float = 0.0,
                t_max_frac: float = 0.3) -> tuple:
    """Fit exponential Q(t) ≈ Q₀ · exp(-t/τ_Q) in the early regime.

    Uses data for t in [t_min_frac * t_max, t_max_frac * t_max].
    Returns (tau_Q, Q0, tau_Q_err).
    """
    lo = t_min_frac * t[-1]
    hi = t_max_frac * t[-1]
    mask = (t >= lo) & (t <= hi) & (Q > 1e-10)
    t_early = t[mask]
    Q_early = Q[mask]

    if len(t_early) < 3:
        return 0.0, 0.0, 0.0

    log_Q = np.log(Q_early)
    coeffs, cov = np.polyfit(t_early, log_Q, 1, cov=True)
    # log(Q) = log(Q0) - t/tau => slope = -1/tau
    tau_Q = -1.0 / coeffs[0] if coeffs[0] < 0 else float('inf')
    Q0 = np.exp(coeffs[1])
    tau_Q_err = abs(tau_Q * math.sqrt(cov[0, 0]) / coeffs[0]) if coeffs[0] < 0 else 0.0

    return tau_Q, Q0, tau_Q_err


def save_tracking_csv(data: dict, savepath: str) -> None:
    """Save tracking time series as CSV."""
    header = 't,Q,R_half,rho_center,sigma_v,q_mean'
    arr = np.column_stack([
        data['t'], data['Q'], data['R_half'],
        data['rho_center'], data['sigma_v'], data['q_mean'],
    ])
    np.savetxt(savepath, arr, delimiter=',', header=header,
               fmt='%.8e', comments='')
    print(f"  Saved: {savepath}")


def run_sweep(d_values: list = None,
              N: int = 150, n_steps: int = 1000,
              dt: float = 0.002, n_grid: int = 64,
              sigma: float = 0.4, L: float = 20.0,
              seed: int = 42, track_every: int = 10
              ) -> dict:
    """Run cold-collapse simulation for each d value.

    Returns dict of results keyed by d: {d: data_dict}.
    """
    if d_values is None:
        d_values = [0.3, 0.5, PHI_INV, 0.7, 0.8]

    results = {}
    print(f"\n{'='*64}")
    print(f"  Sweeping d = {d_values}")
    print(f"  N = {N}, steps = {n_steps}, dt = {dt}")
    print(f"{'='*64}")

    for d in d_values:
        d_label = f"d = {d:.4f}" if d != PHI_INV else f"d = φ⁻¹ = {d:.4f}"
        print(f"\n── {d_label} ──")
        data = run_cold_collapse(
            N=N, n_steps=n_steps, dt=dt,
            n_grid=n_grid, sigma=sigma, L=L,
            seed=seed, track_every=track_every,
            vel_damp=d, verbose=True,
        )
        results[d] = data

        # Save CSV
        d_str = f"{d:.3f}".replace('.', 'p')
        csv_path = f'experiments/path3_cold_collapse_d{d_str}.csv'
        save_tracking_csv(data, csv_path)

    return results


# ═══════════════════════════════════════════════════════════════════════
#  Sweep plotting
# ═══════════════════════════════════════════════════════════════════════


def make_sweep_figure(results: dict,
                      savepath: str = 'experiments/'
                                     'path3_cold_collapse_sweep.png'
                      ) -> None:
    """3-panel sweep figure: Q(t), universal rescaling, α(d)."""
    d_values = sorted(results.keys())
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(d_values)))
    markers = ['o', 's', 'D', '^', 'v']

    # Fit for each d
    d_arr = np.array(d_values)
    alpha_arr = np.zeros(len(d_values))
    alpha_err_arr = np.zeros(len(d_values))
    tau_arr = np.zeros(len(d_values))
    Q0_arr = np.zeros(len(d_values))

    fig, axes = plt.subplots(1, 3, figsize=(20, 7))

    # ═══════════════════════════════════════════════════════════════════
    # Panel A: Q(t) vs physical time
    # ═══════════════════════════════════════════════════════════════════
    ax = axes[0]

    for i, d in enumerate(d_values):
        data = results[d]
        t = data['t']
        Q = data['Q']
        R_half = data['R_half']

        label = f"d={d:.3f}" if d != PHI_INV else f"d=φ⁻¹={d:.3f}"
        ax.semilogy(t, Q, '-', c=colors[i], lw=2, label=label)

        # Analytical prediction: Q₀ · exp(−2·(1−d)·t/dt)
        Q0_init = Q[0]
        t_fine = np.linspace(0, t[-1], 200)
        Q_pred = Q0_init * np.exp(-2.0 * (1.0 - d) * t_fine / data['dt'])
        ax.plot(t_fine, Q_pred, '--', c=colors[i], lw=1, alpha=0.4)

        # Analytical e-folding time
        tau_Q_analytical = data['dt'] / (2.0 * abs(math.log(d))) if d > 0 else float('inf')

        # Fit e-folding from early data (first few steps before Q hits floor)
        # Use only data where Q > 0.1 * Q[0] for a clean fit
        early_mask = (Q > 0.1 * Q[0]) & (t < 0.1 * t[-1])
        if early_mask.sum() >= 3:
            tau_Q_fit, Q0_fit, tau_err = fit_q_efold(
                t[early_mask], Q[early_mask],
                t_min_frac=0.0, t_max_frac=1.0)
        else:
            tau_Q_fit = tau_Q_analytical
            Q0_fit = Q[0]
            tau_err = 0.0
        tau_arr[i] = tau_Q_fit
        Q0_arr[i] = Q[0]  # Always use actual initial Q

        # Fit late-time contraction power law
        alpha, alpha_err, _, _ = fit_contraction_power_law(
            t, R_half, t_min_frac=0.3)
        alpha_arr[i] = alpha
        alpha_err_arr[i] = alpha_err

    ax.set_xlabel('Physical time t', fontsize=12)
    ax.set_ylabel('Virial ratio Q(t)', fontsize=12)
    ax.set_title('A. Q(t)—Cold Collapse by Damping Rate\n'
                 '(solid = sim, dashed = Q₀·exp(−2(1−d)t/dt))',
                 fontsize=11)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3, which='both')

    # ═══════════════════════════════════════════════════════════════════
    # Panel B: Q(t)/Q(0) vs scaled time τ = t · d/(1-d)
    # ═══════════════════════════════════════════════════════════════════
    ax = axes[1]

    for i, d in enumerate(d_values):
        data = results[d]
        t = data['t']
        Q = data['Q']
        Q_norm = Q / Q[0]
        gamma_eff = d / (1.0 - d)
        tau = t * gamma_eff

        ax.semilogy(tau, Q_norm, '-', c=colors[i], lw=2,
                     label=f"d={d:.3f}  (γ_eff={gamma_eff:.2f})")

    # Universal collapse prediction: Q/Q₀ should follow a single master curve
    # Master curve: exp(-2·γ_eff·(1-d)/d · t)? No—in scaled units τ = t·γ_eff,
    # the analytical prediction Q₀·exp(−2·(1−d)·t/dt) becomes
    # Q₀·exp(−2·(1−d)·τ/(dt·γ_eff))
    # but γ_eff = d/(1-d), so (1-d)/γ_eff = (1-d)²/d
    # So Q = Q₀·exp(−2·(1-d)²·τ/(d·dt))
    # This still depends on d—showing that the simple exponential DOES NOT
    # collapse universally under this rescaling.
    # Instead, the collapse tests whether the *numerical* Q dynamics are universal.

    ax.set_xlabel('Scaled time τ = t · γ_eff = t · d/(1−d)', fontsize=12)
    ax.set_ylabel('Q(t) / Q(0)', fontsize=12)
    ax.set_title('B. Universal Collapse Test\n'
                 'Q/Q₀ vs τ = t · d/(1−d)', fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which='both')

    # ═══════════════════════════════════════════════════════════════════
    # Panel C: α(d) vs d—contraction exponent
    # ═══════════════════════════════════════════════════════════════════
    ax = axes[2]

    ax.errorbar(d_arr, alpha_arr, yerr=alpha_err_arr,
                fmt='o-', c='#c0392b', ms=8, lw=2, capsize=4,
                label='α(d) = late-time contraction exponent')

    # Universal exponent reference lines
    ax.axhline(-1.0/3.0, color='gray', ls=':', lw=1.5, alpha=0.7,
               label=r'$-\frac{1}{3}$ (homologous collapse)')
    ax.axhline(-0.5, color='gray', ls=':', lw=1, alpha=0.4,
               label=r'$-\frac{1}{2}$ (free-fall)')

    # φ⁻¹ vertical reference
    if PHI_INV in d_values:
        idx_phi = d_values.index(PHI_INV)
        ax.axvline(PHI_INV, color='#D4A574', ls='--', lw=2, alpha=0.7,
                   label=f'φ⁻¹ = {PHI_INV:.4f}')
        ax.annotate(f'α = {alpha_arr[idx_phi]:.3f}',
                    xy=(PHI_INV, alpha_arr[idx_phi]),
                    xytext=(PHI_INV + 0.08, alpha_arr[idx_phi] + 0.03),
                    fontsize=9, color='#8B6914',
                    arrowprops=dict(arrowstyle='->', color='#D4A574', lw=1))

    ax.set_xlabel('Damping rate d', fontsize=12)
    ax.set_ylabel('Contraction exponent α', fontsize=12)
    ax.set_title('C. Contraction Exponent vs Damping\n'
                 'R_half ∝ t^α (late 30 % of sim)', fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # ── Summary banner on figure ──
    phi_alpha = alpha_arr[d_values.index(PHI_INV)] if PHI_INV in d_values else 0
    summary = (
        f"Cold Collapse d-Sweep  |  N = 150  |  "
        f"Steps = 1000  |  "
        f"α(φ⁻¹) = {phi_alpha:.3f}  |  "
        f"α range: {alpha_arr.min():.3f} to {alpha_arr.max():.3f}"
    )
    fig.text(0.5, 0.01, summary, ha='center', fontsize=10,
             family='monospace', transform=fig.transFigure)

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(savepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"\nSaved: {savepath}")
    plt.close(fig)

    # ── Summary table on terminal ──
    print("\n" + "=" * 90)
    print(f"  {'d':>8s}  {'γ_eff':>8s}  {'Q₀':>10s}  {'Q_final':>10s}  "
          f"{'τ_Q(fit)':>10s}  {'τ_Q(ana)':>10s}  {'α':>8s}  {'α_err':>8s}")
    print(f"  {'─'*8}  {'─'*8}  {'─'*10}  {'─'*10}  {'─'*10}  "
          f"{'─'*10}  {'─'*8}  {'─'*8}")

    for i, d in enumerate(d_values):
        data = results[d]
        geff = d / (1.0 - d)
        tau_ana = data['dt'] / (2.0 * abs(math.log(d))) if d > 0 else float('inf')
        tau_str = f"{tau_arr[i]:.4f}" if np.isfinite(tau_arr[i]) else "∞"
        tau_ana_str = f"{tau_ana:.4f}" if np.isfinite(tau_ana) else "∞"
        print(f"  {d:8.4f}  {geff:8.4f}  {data['Q'][0]:10.4f}  "
              f"{data['Q'][-1]:10.6f}  {tau_str:>10s}  "
              f"{tau_ana_str:>10s}  {alpha_arr[i]:8.4f}  {alpha_err_arr[i]:8.4f}")

    # Universal collapse verdict
    print(f"  {'─'*90}")
    alpha_range = alpha_arr.max() - alpha_arr.min()
    if alpha_range < 0.05:
        print(f"  Verdict: α ≈ constant ({alpha_arr.mean():.3f}±"
              f"{alpha_arr.std():.3f})—UNIVERSAL contraction exponent")
    else:
        print(f"  Verdict: α varies with d (range = {alpha_range:.3f})"
              f"—NOT a single universal exponent")
    # Relationship characterization
    if alpha_range > 0.02:
        p = np.polyfit(d_arr, alpha_arr, 1)
        print(f"  α(d) ≈ {p[0]:.4f}·d + {p[1]:.4f}  (linear fit)")
    print("=" * 90)


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Path 3: Cold Collapse d-Sweep',
    )
    parser.add_argument('--sweep', action='store_true',
                        help='Run d-sweep instead of single d=φ⁻¹ sim')
    parser.add_argument('--d-values', type=str, default=None,
                        help='Comma-separated d values for sweep')
    args = parser.parse_args()

    if args.sweep:
        d_values = None
        if args.d_values:
            d_values = sorted([float(x.strip())
                               for x in args.d_values.split(',')])
        results = run_sweep(d_values=d_values)
        make_sweep_figure(
            results,
            savepath='experiments/path3_cold_collapse_sweep.png',
        )
        return

    # Original single-run mode
    print("=" * 64)
    print("  Path 3: Cold Collapse—φ-Damped N-body from Hot to Cold")
    print("=" * 64)

    # ── 1. Run simulation with tracking ──
    print("\n[1/3] Running φ-damped simulation with high-res tracking...")
    data = run_cold_collapse(
        N=200, n_steps=4000, dt=0.002,
        n_grid=64, sigma=0.4, L=20.0,
        seed=42, track_every=10,
    )

    # ── 2. Compute diagnostics ──
    print("\n[2/3] Analysis...")

    # Contraction power law
    alpha, alpha_err, t_fit, R_fit = fit_contraction_power_law(
        data['t'], data['R_half'], t_min_frac=0.3)

    # Local slope
    gamma, t_gamma = compute_effective_gamma(data['t'], data['R_half'])

    # ── 3. Print diagnostics ──
    print("\n[3/3] Diagnostics")
    print("=" * 60)
    print(f"  Virial ratio Q:")
    print(f"    Initial  = {data['Q'][0]:.6f}")
    print(f"    Final    = {data['Q'][-1]:.6f}")
    print(f"    ΔQ/Q₀    = {(data['Q'][-1] - data['Q'][0]) / data['Q'][0] * 100:.1f}%")
    print(f"  Half-mass radius R_half:")
    print(f"    Initial  = {data['R_half'][0]:.4f}")
    print(f"    Final    = {data['R_half'][-1]:.4f}")
    print(f"    ΔR/R₀    = {(data['R_half'][-1] - data['R_half'][0]) / data['R_half'][0] * 100:.1f}%")
    print(f"    Late α   = {alpha:.4f} ± {alpha_err:.4f}")
    print(f"  Central density ρ_center (r < 0.2):")
    print(f"    Initial  = {data['rho_center'][0]:.4f}")
    print(f"    Final    = {data['rho_center'][-1]:.4f}")
    print(f"    Ratio    = {data['rho_center'][-1] / max(data['rho_center'][0], 1e-30):.1f}x")
    print(f"  Velocity dispersion σ_v:")
    print(f"    Initial  = {data['sigma_v'][0]:.4f}")
    print(f"    Final    = {data['sigma_v'][-1]:.4f}")
    print(f"    Ratio    = {data['sigma_v'][-1] / max(data['sigma_v'][0], 1e-30):.4f}")
    print(f"  Qi coherence q̄:")
    print(f"    Initial  = {data['q_mean'][0]:.6f}")
    print(f"    Final    = {data['q_mean'][-1]:.6f}")
    print("=" * 60)

    # ── 4. Plot ──
    print("\nGenerating figure...")
    make_cold_collapse_figure(data, savepath='experiments/path3_cold_collapse.png')

    print("\nDone.")


if __name__ == '__main__':
    main()
