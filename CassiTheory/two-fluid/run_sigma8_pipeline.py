#!/usr/bin/env python3
"""
Cassi σ₈ Pipeline
=================

Builds Eisenstein-Hu initial conditions, runs a short PDE simulation,
extracts the density field and Qi coherence q(k), computes the Qi-gravity
modified power spectrum G_eff(k) = G_N · (1 + ξ · q(k)), and reports
Δσ₈ = σ₈(Cassi) - σ₈(ΛCDM).

All σ₈ computations use the discrete P(k)-integral formula as the
declared convention: the IC density contrast is rescaled so σ₈ from the
LINEAR P(k) integral equals the target, and pk_norm ≡ 1 downstream (the
former tophat-field rescale + P(k) fudge is removed — it was N-dependent:
σ₈_field ≈ 0.0068/0.0011/0.0002 at N=32/64/128 for a σ₈_Pk = 0.8 IC; the
percentage ratios are convention-robust, the absolute levels are not).

Usage:
    cd two-fluid
    python run_sigma8_pipeline.py
"""

import sys
import time
import torch
import numpy as np
sys.path.insert(0, '.')
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import simpson

from cassi_two_fluid_3d_gpu import (
    ExpandingTwoFluid3DGPU, PHI, PHI_INV,
    eisenstein_hu_transfer, generate_pk_field,
    lcdm_growth_factor, get_device
)

# ── Physical constants ──────────────────────────────────────────────────────
PHI_VAL = PHI                        # (1+√5)/2 ≈ 1.618
PHI_INV_VAL = PHI_INV                # ≈ 0.618
PHI_INV2 = PHI_INV_VAL ** 2          # ≈ 0.382
XI = PHI_VAL ** 6                    # φ⁶ ≈ 17.944 (Qi-gravity coupling)

# Cosmological parameters (Planck 2018)
OMEGA_M = 0.315
OMEGA_B = 0.049
OMEGA_L = 1.0 - OMEGA_M
HUBBLE_H = 0.673
N_S = 0.965

# Box: L=2π in simulation units, ~125 Mpc/h comoving
L_BOX_MPC = 125.0       # Physical box size (Mpc/h)
L = 2.0 * np.pi          # Simulation box length
R8_MPC = 8.0             # σ₈ filter radius (Mpc/h)
R8_SIM = R8_MPC / L_BOX_MPC * L   # σ₈ filter radius in sim units

# Simulation parameters
N = 32
DT = 0.001
N_STEPS = 1500
REPORT_EVERY = 100
SEED = 42
DEVICE = get_device()

# Cassi two-fluid parameters
LAM = 0.1
CHI = 1.0
CS2 = 0.01
HYPER_NU = 0.0
# r₀ = 1/INITIAL_RATIO (EI/EY): the operational doctrine value 1/23 ≈ 0.0435
# (DESI-anchored calibration, run_hubble_pipeline.py); the derived doctrine
# r₀ = φ⁻⁵/(2−φ⁻⁵) ≈ 0.0472 is 8.6% away and indistinguishable for σ₈.
INITIAL_RATIO = 23
HUBBLE_MODE = 'stress_energy'
SIGMA8_TARGET = 0.8

# Output
SCRIPT_DIR = Path(__file__).resolve().parent
OUTDIR = SCRIPT_DIR / 'figures'
OUTDIR.mkdir(parents=True, exist_ok=True)


# ── Helper functions ────────────────────────────────────────────────────────

def tophat_window_k(kR):
    """Fourier transform of 3D tophat: W(kR) = 3[sin(kR)-kR cos(kR)]/(kR)³."""
    x = np.where(kR < 1e-10, 1e-10, kR)
    return 3.0 * (np.sin(x) - x * np.cos(x)) / (x ** 3)


def sigma_R_from_pk(k, Pk, R):
    """σ²(R) = (1/2π²) ∫ P(k) |W(kR)|² k² dk (simpson)."""
    W = tophat_window_k(k * R)
    integrand = Pk * W ** 2 * k ** 2
    sigma2 = simpson(integrand, k) / (2.0 * np.pi ** 2)
    return np.sqrt(max(sigma2, 0.0))


def sigma_R_from_field(delta, k_mag, R):
    """σ(R) from 3D density field via tophat filtering in k-space."""
    delta_k = np.fft.fftn(delta)
    W = tophat_window_k(k_mag * R)
    W[0, 0, 0] = 1.0
    delta_R = np.fft.ifftn(delta_k * W).real
    return float(np.std(delta_R))


def build_k_mag_3d(N, L):
    """3D |k| grid in simulation units."""
    k_1d = 2.0 * np.pi * np.fft.fftfreq(N, d=L / N)
    kz, ky, kx = np.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
    return np.sqrt(kx ** 2 + ky ** 2 + kz ** 2)


def compute_q_field(ey, ei, eps=1e-30):
    """3D Qi coherence field q(x) = M²/(M² + φ⁻² + ε²)."""
    M = ey + ei
    eps_sq = (ey - PHI_VAL * ei) ** 2
    q = M ** 2 / (M ** 2 + PHI_INV2 + eps_sq + eps)
    return q


def compute_q_radial_profile(q_field, solver, n_bins=16):
    """Radial q(k) profile: bin real-space q(x) by |k|."""
    q_np = q_field.cpu().numpy() if isinstance(q_field, torch.Tensor) else q_field
    N = solver.N
    dx = solver.dx
    k_1d = 2.0 * np.pi * np.fft.fftfreq(N, d=dx)
    kz, ky, kx = np.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
    k_mag = np.sqrt(kx ** 2 + ky ** 2 + kz ** 2)
    k_min = k_mag[k_mag > 0].min()
    k_max = k_mag.max()
    bins = np.linspace(k_min, k_max, n_bins + 1)
    k_out = 0.5 * (bins[:-1] + bins[1:])
    q_binned = np.zeros(n_bins)
    counts = np.zeros(n_bins)
    for i in range(n_bins):
        mask = (k_mag >= bins[i]) & (k_mag < bins[i + 1])
        if mask.any():
            q_binned[i] = q_np[mask].mean()
            counts[i] = mask.sum()
    valid = counts > 0
    return k_out[valid], q_binned[valid]


def d_growth(a_targets, omega_m=OMEGA_M, omega_l=OMEGA_L):
    """ΛCDM linear growth factor D(a) on a fine grid, interpolated."""
    a_grid = np.sort(np.unique(np.concatenate([
        [1.0],
        np.linspace(0.1, 3.0, 500),
        np.atleast_1d(np.asarray(a_targets, dtype=float)),
    ])))
    D = lcdm_growth_factor(a_grid, omega_m, omega_l)
    return float(np.interp(a_targets, a_grid, D))


def eh_pk_func(k_val):
    """Eisenstein-Hu P(k) at simulation k values (same map as module)."""
    kp = np.maximum(k_val * L_BOX_MPC / L, 1e-30)
    T = eisenstein_hu_transfer(kp, omega_m=OMEGA_M, omega_b=OMEGA_B, h=HUBBLE_H)
    return np.where(k_val > 0, kp ** N_S * T ** 2, 0.0)


def build_normalized_ics(N, L, sigma8_target, initial_ratio,
                         fraction=0.3, seed=SEED, device=DEVICE):
    """Build EY/EI with the density contrast normalised to σ₈ = target.

    Convention: the LINEAR P(k) integral — sigma_R_from_pk over the
    solver's power_spectrum (Eisenstein-Hu, seed 42) — is the σ₈
    definition; pk_norm ≡ 1. The field-space tophat σ₈ of the same IC is
    reported as the cross-check (the discrete-convention gap between the
    two is N-dependent — the origin of the removed tophat rescale + fudge).

    Construction:
    1. Generate Gaussian random field with EH shape
    2. Build EY/EI with anti-correlated fluctuations
    3. Compute the density contrast δ_ρ and its σ₈ via the P(k) integral
    4. Rescale δ_ρ to match target σ₈ (applied after construction,
       avoiding clamping nonlinearity)
    5. Reconstruct EY/EI from rescaled density
    """
    k_mag = build_k_mag_3d(N, L)

    delta_raw = generate_pk_field(N, L, eh_pk_func, seed=seed, device=device)

    # Build EY/EI
    rho_mean = 1.618
    EI_mean = rho_mean * initial_ratio / (1.0 + initial_ratio)
    EY_mean = rho_mean / (1.0 + initial_ratio)

    EI = EI_mean * (1.0 + delta_raw * fraction)
    EY = EY_mean * (1.0 - delta_raw * fraction)
    EI = torch.clamp(EI, min=1e-4)
    EY = torch.clamp(EY, min=1e-4)

    rho = EY + EI
    delta_rho = (rho / rho.mean() - 1.0).cpu().numpy()

    # σ₈ of the raw density contrast in the P(k)-integral convention
    solver_tmp = ExpandingTwoFluid3DGPU(
        N=N, L=L, lam=LAM, chi=CHI, cs2=CS2,
        hubble_mode=HUBBLE_MODE, initial_ratio=initial_ratio,
        qi_gate=True, device=device)
    k_tmp, Pk_tmp = solver_tmp.power_spectrum(
        torch.tensor(delta_rho, device=device))
    sigma8_pk_raw = sigma_R_from_pk(k_tmp, Pk_tmp, R8_SIM)
    print(f"  σ₈ of raw density contrast (P(k) integral): {sigma8_pk_raw:.4f}")

    # Rescale density field to target σ₈
    scale = sigma8_target / sigma8_pk_raw if sigma8_pk_raw > 0 else 1.0
    rho_np = rho.cpu().numpy()
    rho_mean_np = float(rho_np.mean())
    delta_rho_target = delta_rho * scale  # scaled density contrast
    rho_target = rho_mean_np * (1.0 + delta_rho_target)  # scaled total density
    rho_target_t = torch.tensor(rho_target, device=device, dtype=torch.float64)

    # Redistribute EY/EI proportionally to preserve the ratio field
    ratio_ey = EY / rho
    ratio_ei = EI / rho
    EY_scaled = ratio_ey * rho_target_t
    EI_scaled = ratio_ei * rho_target_t

    # Recompute diagnostics
    rho_check = EY_scaled + EI_scaled
    delta_check = (rho_check / rho_check.mean() - 1.0).cpu().numpy()
    sigma8_pk_final = sigma_R_from_pk(k_tmp, Pk_tmp * scale ** 2, R8_SIM)
    sigma8_f_field = sigma_R_from_field(delta_check, k_mag, R8_SIM)

    q_init = float(compute_q_field(EY_scaled, EI_scaled).mean().cpu())
    delta_rms_init = float(np.std(delta_check))

    print(f"  σ₈ after scaling (P(k) integral): {sigma8_pk_final:.4f} "
          f"(target={sigma8_target})")
    print(f"  σ₈ of the same IC, field-space tophat (cross-check): "
          f"{sigma8_f_field:.4f}")
    print(f"  δ_rms after scaling: {delta_rms_init:.4f}")
    print(f"  q_ref: {q_init:.4f}")

    pk_norm = 1.0  # the P(k)-integral is the convention; no fudge
    Pk_init_norm = Pk_tmp * scale ** 2

    return EY_scaled, EI_scaled, k_mag, q_init, delta_check, pk_norm, k_tmp, Pk_init_norm


# ── Main pipeline ───────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("CASSI σ₈ PIPELINE")
    print("=" * 65)
    print(f"  N={N}³, L={L:.4f} (≈{L_BOX_MPC} Mpc/h), dt={DT}, steps={N_STEPS}")
    print(f"  R₈ = {R8_MPC} Mpc/h → {R8_SIM:.4f} sim-units")
    print(f"  ξ = φ⁶ = {XI:.4f}")
    print(f"  Device: {DEVICE}")
    print(f"  Hubble mode: {HUBBLE_MODE}, initial_ratio (EI/EY): {INITIAL_RATIO}")
    print(f"  σ₈ target: {SIGMA8_TARGET}")
    print()

    # ── 1. Build initial conditions ────────────────────────────────────────
    t0 = time.time()
    print("[1/5] Building Eisenstein-Hu initial conditions...")
    EY, EI, k_mag, q_ref, delta_ic, pk_norm, k_init, Pk_init_norm = \
        build_normalized_ics(N, L, SIGMA8_TARGET, INITIAL_RATIO,
                             seed=SEED, device=DEVICE)

    # Pk_init_norm is already normalized
    sigma8_pk_init = sigma_R_from_pk(k_init, Pk_init_norm, R8_SIM)
    sigma8_f_init = sigma_R_from_field(delta_ic, k_mag, R8_SIM)
    print(f"  σ₈(IC) from P(k) norm:  {sigma8_pk_init:.4f}")
    print(f"  σ₈(IC) from field:      {sigma8_f_init:.4f}")
    print(f"  IC build time: {time.time() - t0:.2f}s")
    print()

    # ── 2. Run PDE simulation ──────────────────────────────────────────────
    print("[2/5] Running PDE simulation...")
    solver = ExpandingTwoFluid3DGPU(
        N=N, L=L, lam=LAM, chi=CHI, cs2=CS2,
        hubble_mode=HUBBLE_MODE, initial_ratio=INITIAL_RATIO,
        qi_gate=True, a0=1.0, device=DEVICE)

    u_hat = [torch.zeros((N, N, N), dtype=torch.complex128, device=DEVICE)
             for _ in range(3)]
    ey_hat = torch.fft.fftn(EY)
    ei_hat = torch.fft.fftn(EI)

    snapshots = []

    # ── Pre-loop: capture initial state (before any PDE step) ──
    q_init_3d = compute_q_field(EY, EI)
    snapshots.append({
        'step': 0, 't': 0.0,
        'a': float(solver.a.cpu()),
        'H': float(solver.H.cpu()),
        'delta_rms': float(np.std(delta_ic)),
        'q_mean': float(q_init_3d.mean().cpu()),
        'k': k_init,
        'Pk': Pk_init_norm.copy(),
        'k_q': np.array([]),
        'q_profile': np.array([]),
        'delta': delta_ic.copy(),
    })
    print(f"  IC (pre-step)   | a={float(solver.a.cpu()):.3f} | δ_rms={snapshots[-1]['delta_rms']:.4f} | "
          f"q_mean={snapshots[-1]['q_mean']:.4f}")
    step_t0 = time.time()

    for step in range(N_STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)

        if step % REPORT_EVERY == 0 or step == N_STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho = ey + ei
            rho_ms = rho.mean().item()
            delta_t = rho / rho_ms - 1.0 if rho_ms > 0 else torch.zeros_like(rho)

            # Raw P(k) then normalize
            k_cur, Pk_raw = solver.power_spectrum(delta_t)
            Pk_cur = Pk_raw * pk_norm

            # Qi coherence
            q_3d = compute_q_field(ey, ei)
            q_mean_cur = float(q_3d.mean().cpu())
            k_q, q_profile = compute_q_radial_profile(q_3d, solver)

            a_cur = float(solver.a.cpu())
            H_cur = float(solver.H.cpu())
            delta_rms_cur = float(delta_t.std().cpu())

            snapshots.append({
                'step': step, 't': step * DT,
                'a': a_cur, 'H': H_cur,
                'delta_rms': delta_rms_cur,
                'q_mean': q_mean_cur,
                'k': k_cur, 'Pk': Pk_cur,
                'k_q': k_q, 'q_profile': q_profile,
                'delta': delta_t.cpu().numpy().copy(),
            })

            print(f"  step {step:4d} | t={step*DT:.3f} | a={a_cur:.3f} | "
                  f"H={H_cur:.4f} | δ_rms={delta_rms_cur:.4f} | "
                  f"q_mean={q_mean_cur:.4f}")

    elapsed = time.time() - step_t0
    print(f"  Simulation: {elapsed:.1f}s ({elapsed / N_STEPS:.4f}s/step)")
    print()

    # ── 3. Compute G_eff(k) and Cassi P(k) ─────────────────────────────────
    print("[3/5] Computing G_eff(k) and Cassi P(k)...")
    final = snapshots[-1]
    a_init = snapshots[0]['a']
    a_final = final['a']

    # ΛCDM growth
    D_init = d_growth(a_init)
    D_final = d_growth(a_final)

    # P_ΛCDM(k) = P_initial(k) × [D(a_final)/D(a_init)]²
    Pk_lcdm = Pk_init_norm * (D_final / D_init) ** 2

    # P_Cassi(k) from measured density field
    Pk_cassi = final['Pk']

    # Qi enhancement
    q_final = final['q_mean']
    G_eff_factor = (1.0 + XI * q_final) / (1.0 + XI * q_ref)

    # Scale-independent Cassi formula
    Pk_cassi_formula = Pk_lcdm * G_eff_factor ** 2

    # Scale-dependent q(k) → G_eff(k)
    k_q = final['k_q']
    q_eff = final['q_profile']
    valid_q = np.isfinite(k_q) & (k_q > 0)
    if valid_q.sum() > 1:
        q_interp = np.interp(final['k'], k_q[valid_q], q_eff[valid_q],
                             left=q_ref, right=q_final)
        G_eff_k = (1.0 + XI * q_interp) / (1.0 + XI * q_ref)
        Pk_cassi_kdep = Pk_lcdm * G_eff_k ** 2
    else:
        Pk_cassi_kdep = Pk_cassi_formula

    # G_eff(k)
    if valid_q.sum() > 1:
        G_eff_over_GN = 1.0 + XI * q_eff
    else:
        G_eff_over_GN = np.array([1.0 + XI * q_final])

    print(f"  q_ref (initial):    {q_ref:.4f}")
    print(f"  q_mean (final):     {q_final:.4f}")
    print(f"  G_eff/G_N (abs):    {1.0 + XI * q_final:.4f}")
    print(f"  G_eff/G_ref factor: {G_eff_factor:.4f}")
    print(f"  ΛCDM growth: D({a_final:.3f})/D({a_init:.3f}) = "
          f"{D_final:.4f} / {D_init:.4f} = {D_final / D_init:.4f}")
    print()

    # ── 4. Compute σ₈ for Cassi vs ΛCDM ────────────────────────────────────
    print("[4/5] Computing σ₈...")
    sigma8_lcdm = sigma_R_from_pk(final['k'], Pk_lcdm, R8_SIM)
    sigma8_cassi = sigma_R_from_pk(final['k'], Pk_cassi, R8_SIM)
    sigma8_cassi_f = sigma_R_from_field(final['delta'], k_mag, R8_SIM)
    sigma8_cassi_formula = sigma_R_from_pk(final['k'], Pk_cassi_formula, R8_SIM)
    sigma8_cassi_kdep = sigma_R_from_pk(final['k'], Pk_cassi_kdep, R8_SIM)

    delta_sigma8 = sigma8_cassi - sigma8_lcdm

    print(f"  σ₈(ΛCDM):             {sigma8_lcdm:.4f}")
    print(f"  σ₈(Cassi, P(k)):     {sigma8_cassi:.4f}")
    print(f"  σ₈(Cassi, field):    {sigma8_cassi_f:.4f}")
    print(f"  σ₈(Cassi, formula):  {sigma8_cassi_formula:.4f}")
    print(f"  σ₈(Cassi, k-dep.):   {sigma8_cassi_kdep:.4f}")
    print(f"  Δσ₈ (Pk):            {delta_sigma8:+.4f}")
    print()

    # ── 5. Plot ────────────────────────────────────────────────────────────
    print("[5/5] Plotting results...")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

    # Panel 1: P(k) at final step
    ax = axes[0]
    v_c = Pk_cassi > 0
    v_l = Pk_lcdm > 0
    ax.loglog(final['k'][v_c], Pk_cassi[v_c], 'darkorange', lw=2,
              marker='o', markersize=4, label=f'Cassi (a={a_final:.3f})')
    ax.loglog(final['k'][v_l], Pk_lcdm[v_l], 'steelblue', lw=2, ls='--',
              label=f'ΛCDM linear (a={a_final:.3f})')
    ax.loglog(k_init[v_l], Pk_init_norm[v_l],
              'gray', lw=1.5, ls=':', label='Initial P(k)')
    ax.set_xlabel('k (simulation units)')
    ax.set_ylabel('P(k)')
    ax.set_title('Power Spectrum at Final Step')
    ax.legend(fontsize=9)
    ax.grid(True, which='both', ls='--', alpha=0.4)

    # Panel 2: G_eff(k)/G_N
    ax = axes[1]
    if valid_q.sum() > 1:
        ax.semilogx(k_q[valid_q], G_eff_over_GN[valid_q], 'darkorange', lw=2,
                    marker='s', markersize=5)
        ax.axhline(y=1.0 + XI * q_final, color='gray', ls='--', lw=1,
                   label=f'scale-indep (ξ·q̄={XI * q_final:.3f})')
    else:
        ax.axhline(y=1.0 + XI * q_final, color='darkorange', lw=2,
                   label=f'G_eff/G_N = {1.0 + XI * q_final:.3f}')
    ax.axhline(y=1.0, color='black', ls='-', lw=0.8, label='G_N (Newton)')
    ax.set_xlabel('k (simulation units)')
    ax.set_ylabel('G_eff(k) / G_N')
    ax.set_title(f'Qi-Gravity Enhancement (ξ = {XI:.1f})')
    ax.legend(fontsize=9)
    ax.grid(True, which='both', ls='--', alpha=0.4)
    ax.set_ylim(bottom=0)

    # Panel 3: σ₈ evolution
    ax = axes[2]
    a_hist = np.array([s['a'] for s in snapshots])
    sigma8_cassi_hist = np.array([
        sigma_R_from_pk(s['k'], s['Pk'], R8_SIM) for s in snapshots
    ])
    sigma8_lcdm_hist = np.array([
        sigma_R_from_pk(k_init,
                        Pk_init_norm * (d_growth(s['a']) / D_init) ** 2,
                        R8_SIM)
        for s in snapshots
    ])

    ax.plot(a_hist, sigma8_cassi_hist, 'darkorange', lw=2, marker='o',
            markersize=4, label='Cassi (measured)')
    ax.plot(a_hist, sigma8_lcdm_hist, 'steelblue', lw=2, ls='--', marker='s',
            markersize=4, label='ΛCDM (linear)')
    ax.axhline(y=SIGMA8_TARGET, color='black', ls=':', lw=1.5, alpha=0.7,
               label=f'σ₈ = {SIGMA8_TARGET} (observed)')
    ax.set_xlabel('a (scale factor)')
    ax.set_ylabel('σ₈')
    ax.set_title('σ₈ Evolution')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.suptitle(f'Cassi σ₈ Pipeline  |  N={N}³  |  '
                 f'ξ = {XI:.1f}  |  Δσ₈ = {delta_sigma8:+.4f}',
                 fontsize=13, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    outpath = OUTDIR / 'sigma8_pipeline.png'
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    print(f"  Saved {outpath}")
    plt.close(fig)
    print()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("=" * 65)
    print("σ₈ PIPELINE RESULTS")
    print("=" * 65)
    print(f"  σ₈(ΛCDM):             {sigma8_lcdm:.4f}")
    print(f"  σ₈(Cassi, measured):  {sigma8_cassi:.4f}")
    print(f"  Δσ₈ = σ₈(Cassi) - σ₈(ΛCDM): {delta_sigma8:+.4f}")
    print(f"  q_ref (initial):      {q_ref:.4f}")
    print(f"  q_mean (final):       {q_final:.4f}")
    print(f"  ξ = φ⁶:               {XI:.4f}")
    print(f"  G_eff/G_N (final):    {1.0 + XI * q_final:.4f}")
    print(f"  Final a:              {a_final:.4f}")
    print(f"  Final H:              {final['H']:.4f}")
    print(f"  Final δ_rms:          {final['delta_rms']:.4f}")
    print("=" * 65)

    return {
        'sigma8_lcdm': sigma8_lcdm,
        'sigma8_cassi_measured': sigma8_cassi,
        'delta_sigma8': delta_sigma8,
        'q_ref': q_ref,
        'q_final': q_final,
        'xi': XI,
        'G_eff_over_GN': float(1.0 + XI * q_final),
        'a_final': a_final,
        'delta_rms_final': final['delta_rms'],
        'pk_norm': pk_norm,
        'n_steps': N_STEPS,
        'elapsed_s': elapsed,
    }


if __name__ == '__main__':
    results = main()
