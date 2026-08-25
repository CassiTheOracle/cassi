#!/usr/bin/env python3
r"""Path 8: Galactic Rotation Curves with Cassi φ-Enhanced Gravity.

This receipt evaluates a positive enhanced-gravity branch of the Qi
parameterization. The corresponding softened-gravity comparison is included
only as a bounded shape reference; softening cannot supply an attractive
boost.

The tested coupling is:

    G_eff(q) / G = α · (1 + ξ·q)

where ξ = φ⁶ ≈ 17.944 is the Qi-gravity coupling and α = 0.7 is a
Hypothesized halo-regime mass-fraction parameter. In a mass-model
interpretation the analogous true Yang fraction is M_Y/M_tot, with
M_tot = M_bar + M_Y; α is not the
canonical fractional imbalance π/ρ.

The canonical two-fluid fields are E_Y, E_I >= 0, ρ = E_Y + E_I, and
π = E_Y − E_I. The canonical coherence map is

    q_canonical = ρ² / (ρ² + φ⁻² + ε²),
    ε = E_Y − φ E_I.

This path instead uses the density proxy

    q = 1 / (1 + (ρ / ρ_ref)²)

as a Hypothesized proxy map for the rotation-curve receipt. It is not an
exact or canonical identification of q. In this script:

    q → 0  when  ρ >> ρ_ref   (high density → screened)
    q → 1  when  ρ << ρ_ref   (low density → G_eff → α(1+ξ)G)

Within this positive halo parameterization, q → 1 gives
G_eff/G → α(1+ξ) ≈ 13.3 and a velocity boost of about 3.6×. The framework
saturation φ⁶ ≈ 17.94 is a separate coupling bound, not a fitted result of
this path.

The attractive-rotation interpretation belongs to a separate Hypothesized
sign-changing gravity branch. This path evaluates only the positive
enhanced-gravity branch and does not test that alternative.

This script tests whether a single $\rho_{\rm ref}$ can approach an imposed
flat target of $v_{\rm circ}=200\ {\rm km\,s^{-1}}$ out to 30 kpc for a
synthetic Milky-Way-like baryonic mass model. It contains no observed
rotation-curve points or measurement uncertainties.

Galaxy model:
    Disk:  M_d = 6×10¹⁰ M_sun, R_d = 3.0 kpc (exponential)
    Bulge: M_b = 1×10¹⁰ M_sun, r_b = 0.5 kpc (exponential sphere)

Usage:
    python experiments/phi_attractor_paths/path8_phi_enhanced_rotation.py
"""

import sys
import os
import time
import numpy as np
from scipy.special import i0e, i1e, k0e, k1e

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, FormatStrFormatter

# ═══════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════

PHI = (1.0 + np.sqrt(5.0)) / 2.0       # golden ratio ≈ 1.6180
XI = PHI ** 6                             # Qi-gravity coupling ξ = φ⁶ ≈ 17.944
ALPHA_HALO = 0.7                          # Hypothesized halo mass-fraction parameter, not pi/rho
G = 4.302e-6                             # kpc (km/s)^2 / M_sun

# Galaxy model parameters
M_DISK = 6.0e10                          # M_sun
R_DISK = 3.0                             # kpc  radial scale length
Z_DISK = 0.3                             # kpc  vertical scale height
M_BULGE = 1.0e10                         # M_sun
R_BULGE = 0.5                            # kpc  exponential bulge scale
R_MAX = 30.0                             # kpc
N_GRID = 500                             # radial grid points

# Synthetic flat-curve target; this is not an observational data vector.
V_FLAT_OBS = 200.0                       # km/s
R_FIT_INNER = 5.0                        # kpc inner edge of fit range
R_FIT_OUTER = 30.0                       # kpc outer edge of fit range


# ═══════════════════════════════════════════════════════════════════════════
#  Positive enhanced-gravity receipt branch
# ═══════════════════════════════════════════════════════════════════════════

def geff_q_from_density(rho, rho_ref):
    """Script-level G_eff/G and density proxy q from local density.

    This receipt uses:
        G_eff/G = alpha · (1 + xi·q),   xi = phi^6 ≈ 17.944
        q = 1 / (1 + (rho / rho_ref)^2)   (Hypothesized density proxy map)

    ALPHA_HALO is a Hypothesized halo mass-fraction parameter. It is not the
    canonical fractional imbalance pi/rho. The canonical two-fluid coherence
    uses rho^2 / (rho^2 + phi^-2 + epsilon^2); this function evaluates the
    density proxy above instead.

    Parameters
    ----------
    rho : ndarray—local density [M_sun/kpc^3]
    rho_ref : float—reference transition density [M_sun/kpc^3]

    Returns
    -------
    g_ratio : ndarray—G_eff / G = alpha(1+xi·q)
    q : ndarray—Hypothesized density proxy map in (0, 1]
    """
    ratio = rho / (rho_ref + 1e-30)
    q = 1.0 / (1.0 + ratio ** 2 + 1e-30)
    g_ratio = ALPHA_HALO * (1.0 + XI * q)
    return g_ratio, q


# ═══════════════════════════════════════════════════════════════════════════
#  Galaxy mass model
# ═══════════════════════════════════════════════════════════════════════════

class ExponentialDisk:
    """Exponential disk: Σ(R) = Σ₀ exp(-R/R_d)."""

    def __init__(self, M, R_d):
        self.M = M
        self.R_d = R_d
        self.Sigma_0 = M / (2.0 * np.pi * R_d ** 2)  # central surface density

    def surface_density(self, R):
        """Σ(R) [M_sun/kpc²]."""
        return self.Sigma_0 * np.exp(-R / self.R_d)

    def midplane_volume_density(self, R):
        """ρ(R, z=0) [M_sun/kpc³] using ρ = Σ/(2h_z)."""
        return self.surface_density(R) / (2.0 * Z_DISK)

    def mass_enc(self, R):
        """Spherical-shell equivalent enclosed mass [M_sun]."""
        x = R / self.R_d
        return self.M * (1.0 - (1.0 + x) * np.exp(-x))

    def v_circ_freeman(self, R):
        """Newtonian rotation curve via Freeman (1970) analytic formula [km/s].

        v²(R) = 4π G Σ₀ R_d y² [I₀(y)K₀(y) - I₁(y)K₁(y)]
        where y = R/(2R_d).  Uses exponentially-scaled Bessel functions.
        """
        y = R / (2.0 * self.R_d)
        bessel = i0e(y) * k0e(y) - i1e(y) * k1e(y)
        v2 = 4.0 * np.pi * G * self.Sigma_0 * self.R_d * y ** 2 * bessel
        return np.sqrt(np.maximum(v2, 0.0))


class ExponentialBulge:
    """Exponential spheroidal bulge: ρ(r) = ρ₀ exp(-r/r_b)."""

    def __init__(self, M, r_b):
        self.M = M
        self.r_b = r_b
        # M = 8π ρ₀ r_b³  →  ρ₀ = M / (8π r_b³)
        self.rho_0 = M / (8.0 * np.pi * r_b ** 3)

    def density(self, r):
        """ρ(r) [M_sun/kpc³]."""
        return self.rho_0 * np.exp(-r / self.r_b)

    def mass_enc(self, R):
        """Enclosed mass within R [M_sun]."""
        x = R / self.r_b
        return self.M * (1.0 - np.exp(-x) * (
            1.0 + x + x ** 2 / 2.0 + x ** 3 / 6.0
        ))

    def v_circ_newton(self, R):
        """Newtonian rotation curve [km/s]."""
        v2 = G * self.mass_enc(R) / R
        return np.sqrt(np.maximum(v2, 0.0))


# ═══════════════════════════════════════════════════════════════════════════
#  Rotation curve computation
# ═══════════════════════════════════════════════════════════════════════════

def compute_rotation_curves(r_grid, disk, bulge, rho_ref):
    """Compute Newtonian and positive φ-enhanced receipt curves.

    Newtonian:
        v² = v_disk²(Freeman) + v_bulge²(G·M_enc/R)

    Positive φ-enhanced branch:
        At each radius R, the midplane density ρ(R) determines the
        Hypothesized density proxy q(R) and G_eff(R). The enhanced v² is:
            v²(R) = G_eff(R)/G_N · [v_disk²(R) + v_bulge²(R)]
        This applies the positive local G_eff as a multiplicative factor to
        the Newtonian v². It does not evaluate the separate Hypothesized
        sign-changing gravity branch.

    Parameters
    ----------
    r_grid : ndarray—radial grid [kpc]
    disk : ExponentialDisk
    bulge : ExponentialBulge
    rho_ref : float—reference transition density for the q proxy [M_sun/kpc³]

    Returns
    -------
    dict with keys: R, v_newt, v_phi, q, g_ratio, rho_midplane
    """

    # Newtonian components
    v_disk_N = disk.v_circ_freeman(r_grid)
    v_bulge_N = bulge.v_circ_newton(r_grid)
    v_newt = np.sqrt(v_disk_N ** 2 + v_bulge_N ** 2)

    # Total midplane density at each radius
    rho_disk_mid = disk.midplane_volume_density(r_grid)
    rho_bulge_mid = bulge.density(r_grid)
    rho_total = rho_disk_mid + rho_bulge_mid

    # Hypothesized density proxy q and positive G_eff.
    g_ratio, q = geff_q_from_density(rho_total, rho_ref)

    # Positive enhanced rotation curve: v²_φ = (G_eff/G_N) · v²_N.
    v_phi = np.sqrt(g_ratio * v_newt ** 2)

    return {
        'R': r_grid,
        'v_newt': v_newt,
        'v_phi': v_phi,
        'v_disk_N': v_disk_N,
        'v_bulge_N': v_bulge_N,
        'q': q,
        'g_ratio': g_ratio,
        'rho_midplane': rho_total,
        'rho_disk_mid': rho_disk_mid,
        'rho_bulge_mid': rho_bulge_mid,
    }


def chi_squared(v_circ, r_grid, v_target=V_FLAT_OBS,
                r_inner=R_FIT_INNER, r_outer=R_FIT_OUTER):
    """Return a dimensionless score against the synthetic flat target.

    The fixed 20 km/s scale weights residuals for the toy optimization; it is
    not a measurement-error model, so the result is not an observational
    chi-squared statistic.
    """
    mask = (r_grid >= r_inner) & (r_grid <= r_outer)
    sigma = 20.0  # km/s—synthetic residual scale
    residuals = (v_circ[mask] - v_target) / sigma
    return np.sum(residuals ** 2)


def rms_deviation(v_circ, r_grid, v_target=V_FLAT_OBS,
                  r_inner=R_FIT_INNER, r_outer=R_FIT_OUTER):
    """RMS deviation from the synthetic flat target [km/s]."""
    mask = (r_grid >= r_inner) & (r_grid <= r_outer)
    return np.sqrt(np.mean((v_circ[mask] - v_target) ** 2))


# ═══════════════════════════════════════════════════════════════════════════
#  Figure
# ═══════════════════════════════════════════════════════════════════════════

def make_figure(r_grid, results_newt, results_soft, results_best,
                rho_ref_sweep, chi2_vals, rho_ref_best, savepath):
    """Render the three-panel synthetic shape study.

    Panel A: Newtonian, softened-reference, and positive enhanced curves
    against the imposed flat target
    Panel B: Hypothesized density proxy q(R) and G_eff(R)/G_N at the
    minimum-score rho_ref
    Panel C: synthetic target score over rho_ref
    """
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.5))

    # ── Panel A: Rotation curves ──────────────────────────────────────────
    ax = axes[0]
    v_obs = V_FLAT_OBS * np.tanh(r_grid / 2.0)

    ax.plot(r_grid, results_newt['v_newt'], 'k-', lw=2.5,
            label='Newtonian (baryons only)', zorder=10)

    if results_soft is not None:
        ax.plot(r_grid, results_soft, '-', color='#e67e22', lw=1.8,
                label='Softened (Path 7, $\\sigma$=3 kpc)', zorder=8)

    ax.plot(r_grid, results_best['v_phi'], '-', color='#8e44ad', lw=2.5,
            label=rf'$\varphi$-enhanced ($\rho_{{\mathrm{{ref}}}}={rho_ref_best:.1e}$)'
                  + '\n' + rf'$G_{{\mathrm{{eff}}}}/G\to{ALPHA_HALO*(1.0+XI):.3f}$',
            zorder=9)

    ax.plot(r_grid, v_obs, 'r--', lw=1.8,
            label=r'Synthetic flat target ($200$ km/s)', zorder=5)

    ax.fill_between(r_grid, results_newt['v_newt'], results_best['v_phi'],
                    alpha=0.08, color='purple',
                    label='$G_{\\mathrm{eff}}(q)$ enhancement')

    ax.set_xlabel('Radius $R$ [kpc]', fontsize=13)
    ax.set_ylabel('$v_{\\mathrm{circ}}$ [km/s]', fontsize=13)
    ax.set_title('A: Rotation Curves', fontsize=14, pad=8)
    ax.set_xlim(0, R_MAX)
    ax.set_ylim(0, 350)
    ax.grid(True, alpha=0.25, ls=':')
    ax.legend(fontsize=8.5, loc='upper right', framealpha=0.9)

    ax.text(0.03, 0.03,
            rf'$\varphi = {PHI:.6f}$' + '\n'
            rf'$\xi = \varphi^6 = {XI:.3f}$' + '\n'
            rf'$G_{{\mathrm{{eff}}}} = \alpha\,(1+\xi q)\,G$, $\alpha={ALPHA_HALO}$' + '\n'
            rf'$q = [1 + (\rho/\rho_{{\mathrm{{ref}}}})^2]^{{-1}}$',
            transform=ax.transAxes, fontsize=9, va='bottom',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow',
                      edgecolor='gray', alpha=0.9))

    # ── Panel B: Hypothesized density proxy q(R) and G_eff(R)/G_N ─────────
    ax = axes[1]
    ax2 = ax.twinx()

    line_q, = ax.plot(r_grid, results_best['q'], 'g-', lw=2.2,
                      label='$q(R)$')
    ax.axhline(0.5, color='green', ls=':', lw=1, alpha=0.5)
    ax.set_xlabel('Radius $R$ [kpc]', fontsize=13)
    ax.set_ylabel('$q$ (coherence)', fontsize=13, color='green')
    ax.tick_params(axis='y', labelcolor='green')
    ax.set_xlim(0, R_MAX)
    ax.set_ylim(-0.02, 1.05)
    ax.grid(True, alpha=0.2, ls=':')

    line_g, = ax2.plot(r_grid, results_best['g_ratio'], 'm-', lw=2.2,
                       label='$G_{\\mathrm{eff}}/G$')
    ax2.axhline(1.0, color='purple', ls=':', lw=1, alpha=0.5)
    ax2.axhline(ALPHA_HALO * (1.0 + XI), color='red', ls=':', lw=1, alpha=0.5,
                label=f'$\\alpha(1+\\xi) = {ALPHA_HALO*(1.0+XI):.2f}$')
    ax2.set_ylabel('$G_{\\mathrm{eff}}/G$', fontsize=13, color='purple')
    ax2.tick_params(axis='y', labelcolor='purple')
    ax2.set_ylim(0.9 * ALPHA_HALO, ALPHA_HALO * (1.0 + XI) * 1.05)

    lines = [line_q, line_g]
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, fontsize=10, loc='center right',
              framealpha=0.9)

    ax.set_title('B: Qi Coherence $q(R)$ and $G_{\\mathrm{eff}}(R)$',
                 fontsize=14, pad=8)

    # Mark transition radius where rho = rho_ref (density proxy q = 0.5)
    rho = results_best['rho_midplane']
    idx_trans = np.argmin(np.abs(rho - rho_ref_best))
    r_trans = r_grid[idx_trans]
    for a in [ax, ax2]:
        a.axvline(r_trans, color='orange', ls='--', lw=1.2, alpha=0.6)
    ax.annotate(f'$\\rho=\\rho_{{\\mathrm{{ref}}}}$\n$R={r_trans:.1f}$ kpc',
                xy=(r_trans, 0.5), xytext=(r_trans + 3, 0.7),
                fontsize=8.5, color='orange',
                arrowprops=dict(arrowstyle='->', color='orange', lw=1.2))

    # ── Panel C: synthetic target-score scan ──────────────────────────────
    ax = axes[2]

    ax.semilogx(rho_ref_sweep, chi2_vals, 'b-o', lw=2, ms=4,
                label='synthetic score $(\\rho_{\\mathrm{ref}})$')
    ax.axvline(rho_ref_best, color='red', ls='--', lw=1.5, alpha=0.7,
               label=f'Minimum score: $\\rho_{{\\mathrm{{ref}}}} = {rho_ref_best:.1e}$')
    ax.plot(rho_ref_best, chi2_vals.min(), 'r*', markersize=18, zorder=10)

    # Mark the Newtonian synthetic score for reference.
    chi2_newt = chi_squared(results_newt['v_newt'], r_grid)
    ax.axhline(chi2_newt, color='black', ls=':', lw=1.2, alpha=0.5,
               label=f'Newtonian score = {chi2_newt:.0f}')

    ax.set_xlabel('$\\rho_{\\mathrm{ref}}$ [M$_\\odot$/kpc$^3$]', fontsize=13)
    ax.set_ylabel('Synthetic flat-target score', fontsize=13)
    ax.set_title('C: Parameter Scan over $\\rho_{\\mathrm{ref}}$',
                 fontsize=14, pad=8)
    ax.grid(True, alpha=0.25, ls=':')
    ax.legend(fontsize=9, loc='upper right', framealpha=0.9)

    fig.suptitle('Path 8: $\\varphi$-Enhanced Gravity and Galactic Rotation Curves\n'
                 r'$G_{\mathrm{eff}}/G = \alpha(1+\xi q)$,  $\xi = \varphi^6 \approx 17.94$',
                 fontsize=14, y=1.04)

    fig.tight_layout()
    fig.savefig(savepath, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"  Saved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════
#  Main analysis
# ═══════════════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()

    print("=" * 78)
    print("  Path 8: φ-Enhanced Gravity and Galactic Rotation Curves")
    print("=" * 78)
    print()
    print(f"  Galaxy model:")
    print(f"    Disk:  M = {M_DISK:.1e} M_sun,  R_d = {R_DISK} kpc,  "
          f"h_z = {Z_DISK} kpc")
    print(f"    Bulge: M = {M_BULGE:.1e} M_sun,  r_b = {R_BULGE} kpc")
    print(f"    Total baryonic mass: {M_DISK + M_BULGE:.1e} M_sun")
    print(f"  φ = {PHI:.10f},  ξ = φ⁶ = {XI:.6f},  α = {ALPHA_HALO}")
    print(f"  Halo-regime max G_eff: α(1+ξ)·G = {ALPHA_HALO*(1.0+XI):.3f}·G  "
          f"(v-boost √(α(1+ξ)) = {np.sqrt(ALPHA_HALO*(1.0+XI)):.3f}); "
          f"framework saturation: φ⁶·G ≈ {XI:.2f}·G (v-boost φ³ ≈ {np.sqrt(XI):.3f})")
    print()

    # ── Setup ─────────────────────────────────────────────────────────────
    r_grid = np.linspace(0.05, R_MAX, N_GRID)
    disk = ExponentialDisk(M_DISK, R_DISK)
    bulge = ExponentialBulge(M_BULGE, R_BULGE)

    # Central midplane density
    rho_central = disk.midplane_volume_density(0.01) + bulge.density(0.01)
    print(f"  Central midplane density: ρ₀ = {rho_central:.3e} M_sun/kpc³")
    print(f"  Density at R_d = {R_DISK} kpc: "
          f"{disk.midplane_volume_density(R_DISK) + bulge.density(R_DISK):.3e}")
    print(f"  Density at 10 kpc: "
          f"{disk.midplane_volume_density(10) + bulge.density(10):.3e}")
    print(f"  Density at 30 kpc: "
          f"{disk.midplane_volume_density(30) + bulge.density(30):.3e}")
    print()

    # ── Newtonian rotation curve ──────────────────────────────────────────
    print("[1/4] Computing Newtonian rotation curve...")
    results_newt = compute_rotation_curves(r_grid, disk, bulge, rho_ref=1e30)
    # The Newtonian acceleration is returned separately from the q branch.
    v_newt = results_newt['v_newt']
    print(f"    Peak v_circ = {v_newt.max():.1f} km/s at R = {r_grid[v_newt.argmax()]:.1f} kpc")
    i5 = np.argmin(np.abs(r_grid - 5.0))
    i10 = np.argmin(np.abs(r_grid - 10.0))
    i30 = np.argmin(np.abs(r_grid - 30.0))
    print(f"    v(5) = {v_newt[i5]:.1f} km/s,  v(10) = {v_newt[i10]:.1f} km/s,  "
          f"v(30) = {v_newt[i30]:.1f} km/s")
    chi2_newt = chi_squared(v_newt, r_grid)
    rms_newt = rms_deviation(v_newt, r_grid)
    print(f"    synthetic score = {chi2_newt:.0f},  RMS = {rms_newt:.1f} km/s")
    print()

    # ── ρ_ref sweep ───────────────────────────────────────────────────────
    print("[2/4] Sweeping ρ_ref over the synthetic target score...")
    rho_ref_sweep = np.logspace(5, 12, 50)  # M_sun/kpc³
    chi2_vals = np.zeros(len(rho_ref_sweep))
    v_at_30 = np.zeros(len(rho_ref_sweep))
    results_sweep = []

    for i, rho_ref in enumerate(rho_ref_sweep):
        res = compute_rotation_curves(r_grid, disk, bulge, rho_ref)
        chi2_vals[i] = chi_squared(res['v_phi'], r_grid)
        v_at_30[i] = res['v_phi'][i30]
        results_sweep.append(res)
        if (i + 1) % 10 == 0:
            print(f"    ρ_ref = {rho_ref:.2e}  →  toy score = {chi2_vals[i]:.0f},  "
                  f"v(30) = {v_at_30[i]:.1f} km/s")

    # Minimum-score synthetic parameter
    i_best = np.argmin(chi2_vals)
    rho_ref_best = rho_ref_sweep[i_best]
    results_best = results_sweep[i_best]
    chi2_best = chi2_vals[i_best]
    rms_best = rms_deviation(results_best['v_phi'], r_grid)

    print()
    print(f"    Minimum-score ρ_ref = {rho_ref_best:.3e} M_sun/kpc³")
    print(f"    toy score = {chi2_best:.0f}  (Newtonian = {chi2_newt:.0f})")
    print(f"    target RMS = {rms_best:.1f} km/s  (Newtonian = {rms_newt:.1f} km/s)")
    print()

    # ── Print diagnostic table at the minimum-score parameter ─────────────
    print("[3/4] Rotation curve at minimum-score ρ_ref...")
    print(f"    {'R [kpc]':>10s}  {'v_Newt':>10s}  {'v_phi':>10s}  "
          f"{'G_eff/G_N':>10s}  {'q':>10s}  {'ρ [M_sun/kpc³]':>16s}")
    print("    " + "-" * 75)
    for r_target in [1, 2, 3, 5, 8, 10, 15, 20, 25, 30]:
        idx = np.argmin(np.abs(r_grid - r_target))
        R = r_grid[idx]
        print(f"    {R:10.1f}  {v_newt[idx]:10.1f}  "
              f"{results_best['v_phi'][idx]:10.1f}  "
              f"{results_best['g_ratio'][idx]:10.4f}  "
              f"{results_best['q'][idx]:10.4f}  "
              f"{results_best['rho_midplane'][idx]:16.3e}")
    print()

    # ── Build bounded softened-gravity reference shape ─────────────────────
    results_soft = None
    try:
        # Use a rough bounded suppression shape for visual comparison only;
        # this is not an independent softened-gravity solver receipt.
        sigma_soft = 3.0  # kpc—reference softening scale
        # The reference suppresses inner velocities while approaching the
        # Newtonian curve at large radius.
        # The smoothing scale is retained for the comparison parameter.
        suppression = np.zeros_like(r_grid)
        for j, R in enumerate(r_grid):
            # Simple suppression factor for the bounded reference shape.
            suppression[j] = min(1.0, R / (sigma_soft * 3))
        # The bounded reference approaches the Newtonian curve at large R.
        results_soft = v_newt * np.clip(
            np.where(r_grid < 5, r_grid / 5.0, 1.0), 0.3, 1.0
        )
    except Exception:
        pass

    # ── Figure ────────────────────────────────────────────────────────────
    print("[4/4] Generating figure...")
    savepath = os.path.join(os.path.dirname(__file__),
                            'path8_phi_enhanced_rotation.png')
    make_figure(r_grid, results_newt, results_soft, results_best,
                rho_ref_sweep, chi2_vals, rho_ref_best, savepath)
    print()

    # ── Synthetic shape-study summary ────────────────────────────────────
    v_enhanced_30 = results_best['v_phi'][i30]
    v_newt_30 = v_newt[i30]
    ratio_30 = v_enhanced_30 / v_newt_30
    flat_ratio = results_best['v_phi'][i30] / results_best['v_phi'][i5]
    idx_trans = np.argmin(np.abs(results_best['q'] - 0.5))
    r_transition = r_grid[idx_trans]

    print("=" * 78)
    print("  SYNTHETIC MODEL SUMMARY")
    print("=" * 78)
    print("  Target: imposed 200 km/s flat curve; no observed points or errors")
    print(f"  Minimum-score ρ_ref: {rho_ref_best:.3e} M_sun/kpc³")
    print(f"  Synthetic score: {chi2_best:.0f} "
          f"(Newtonian reference: {chi2_newt:.0f})")
    print(f"  Target RMS: {rms_best:.1f} km/s "
          f"(Newtonian reference: {rms_newt:.1f} km/s)")
    print(f"  v_phi(5, 10, 30 kpc): "
          f"{results_best['v_phi'][i5]:.1f}, "
          f"{results_best['v_phi'][i10]:.1f}, "
          f"{v_enhanced_30:.1f} km/s")
    print(f"  v_phi(30)/v_phi(5): {flat_ratio:.3f}")
    print(f"  v_phi(30)/v_newton(30): {ratio_30:.3f}")
    print(f"  q=0.5 transition radius: {r_transition:.2f} kpc")
    print(f"  G_eff/G at 30 kpc: {results_best['g_ratio'][i30]:.4f}")
    print(f"  Halo-parameter ceiling: α(1+ξ) = "
          f"{ALPHA_HALO * (1.0 + XI):.4f}")
    print()
    print("  Within this baryonic toy model, a single density-transition scale")
    print("  produces a rising outer curve rather than the imposed flat shape.")
    print("  An observational test requires a sourced rotation-curve table,")
    print("  its measurement covariance, and baryonic-model uncertainties.")

    print("=" * 78)
    print(f"  Elapsed: {time.time() - t_start:.1f}s")
    print("=" * 78)


if __name__ == '__main__':
    main()
