#!/usr/bin/env python3
"""Cassi Boltzmann Pipeline—CAMB CMB power spectrum with Cassi cosmology.

Runs CAMB with four cosmology variants to isolate the Cassi CMB signatures:
  1. ΛCDM baseline (w = -1, standard P(k))
  2. Cassi CPL (w₀ = -0.839, wₐ = +0.439, standard P(k))
  3. Cassi full (CPL + Qi transfer function)
  4. Qi only (w = -1 + Qi transfer function)

Physics:
  - Modified background H(z) from Cassi w(a) > -1 shifts angular diameter
    distance D_A(z*) and sound horizon r_s, moving Cℓ peak positions.
  - Scale-dependent Qi coherence q(k) modifies effective gravity,
    G_eff(k) = G_N(1 + ξ · q(k)), imprinted as a primordial power modulation.
  - Faster high-z expansion in Cassi reduces r_s, shifting peaks to higher ℓ.

Usage:
    cd two-fluid && python run_boltzmann_cassi.py

Output:
    figures/boltzmann_cassi.png —4-panel diagnostic figure
    Console summary with key diagnostics.
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import camb
from camb import model


# ═════════════════════════════════════════════════════════════════════════════
# ── Constants ────────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

PHI = (1.0 + np.sqrt(5.0)) / 2.0          # ≈ 1.618034
PHI_INV = 1.0 / PHI                        # ≈ 0.618034
PHI_INV2 = PHI_INV ** 2                    # ≈ 0.381966
XI = PHI ** 6                              # ≈ 17.944—Qi-gravity coupling

# Cassi w(a) calibration (CPL form)
W0_CASSI = -0.839
WA_CASSI = +0.439

K_QI = 1.0          # [h/Mpc] Qi coherence scale at recombination (effective)
Q0 = 0.005           # Qi coherence amplitude at k → 0
K_PIVOT_CMB = 0.05   # [h/Mpc] pivot scale for normalization—T_Qi = 1 here
H0 = 67.4                     # [km/s/Mpc]
OMBH2 = 0.0224                # Ω_b h²
OMCH2 = 0.120                 # Ω_c h²
TAU = 0.054                   # optical depth to reionization
NS = 0.965                    # spectral index
AS = 2.1e-9                   # primordial amplitude
K_PIVOT = 0.05                # [Mpc⁻¹] pivot scale

LMAX = 2500
FIGURE_DIR = Path(__file__).resolve().parent / 'figures'


# ═════════════════════════════════════════════════════════════════════════════
# ── Qi Transfer Function ─────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def qi_coherence(k, q0=Q0, k_qi=K_QI):
    """Qi coherence amplitude q(k) at wavenumber k.

    The coherence decays exponentially at scales smaller than the Qi
    coherence length (≈ 1/k_Qi), suppressing the modification to G_eff
    at small scales.
    """
    return q0 * np.exp(-k / k_qi)


def qi_transfer(k, xi=XI, k_pivot=K_PIVOT_CMB, q0=Q0, k_qi=K_QI):
    """Modified primordial power transfer function T_Qi(k).

    T_Qi(k) = (1 + ξ · q(k)) / (1 + ξ · q(k_pivot))

    Normalised to unity at k = k_pivot so the standard amplitude As retains
    its meaning at the CMB anchor scale.  T_Qi(k) > 1 at k < k_pivot
    (larger scales) and T_Qi(k) < 1 at k > k_pivot.
    """
    q_k = qi_coherence(k, q0, k_qi)
    q_pivot = qi_coherence(k_pivot, q0, k_qi)
    return (1.0 + xi * q_k) / (1.0 + xi * q_pivot)


# ═════════════════════════════════════════════════════════════════════════════
# ── CAMB Runner ──────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def build_params(w=-1.0, wa=0.0):
    """Build a CAMBparams object with baseline cosmology.

    Parameters
    ----------
    w : float
        Dark energy equation of state parameter (constant or CPL w₀).
    wa : float
        Dark energy CPL evolution parameter (0 for constant w).

    Returns
    -------
    camb.CAMBparams
    """
    pars = camb.CAMBparams()
    pars.set_cosmology(H0=H0, ombh2=OMBH2, omch2=OMCH2, tau=TAU)
    pars.InitPower.set_params(ns=NS, As=AS, pivot_scalar=K_PIVOT)
    pars.set_dark_energy(w=w, wa=wa, dark_energy_model='ppf')
    pars.set_for_lmax(LMAX, lens_potential_accuracy=0)
    return pars


def run_camb(pars):
    """Run CAMB and return Cℓ TT power spectrum and derived params.

    Parameters
    ----------
    pars : camb.CAMBparams

    Returns
    -------
    ell : ndarray (LMAX+1,)
    cls_tt : ndarray (LMAX+1,)—TT in μK²
    cls_tt_unlensed : ndarray (LMAX+1,)—unlensed TT in μK²
    derived : dict—derived parameters
    """
    results = camb.get_results(pars)
    cls_dict = results.get_cmb_power_spectra(pars, CMB_unit='muK')

    # Shape: (n_ell, 4) → columns are TT, EE, BB, TE
    cls_total = cls_dict['total']
    cls_unlensed = cls_dict['unlensed_scalar']

    # ℓ array: same length as cls_total
    ell = np.arange(cls_total.shape[0])

    # Extract TT (column 0)
    cls_tt = cls_total[:, 0]
    cls_tt_unlensed = cls_unlensed[:, 0]

    derived = results.get_derived_params()
    return ell, cls_tt, cls_tt_unlensed, derived


def apply_qi_transfer(ell, cls_tt, cls_tt_unlensed, da_star, k_qi=K_QI,
                      q0=Q0, xi=XI):
    """Apply the Qi transfer function to Cℓ power spectra.

    Uses the flat-sky mapping k ≈ ℓ / D_A(z*) to translate the
    3D transfer function to angular multipole space.
    """
    # k for each ℓ
    k_eff = ell / da_star
    t_qi = qi_transfer(k_eff, xi=xi, q0=q0, k_qi=k_qi)

    # Apply as C_ℓ → C_ℓ × T_Qi(k_ℓ)²
    cls_tt_qi = cls_tt * t_qi ** 2
    cls_tt_unlensed_qi = cls_tt_unlensed * t_qi ** 2
    return cls_tt_qi, cls_tt_unlensed_qi, t_qi


# ═════════════════════════════════════════════════════════════════════════════
# ── Peak Detection ───────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def find_acoustic_peaks(ell, cls, n_peaks=5):
    """Locate acoustic peak positions via quadratic interpolation.

    Uses a simple derivative sign-change approach with sub-bin refinement.
    Returns ℓ positions of the first n_peaks peaks.
    """
    # Smooth slightly to avoid noise spikes
    from scipy.ndimage import uniform_filter1d
    cls_smooth = uniform_filter1d(cls, size=5, mode='constant')

    # Find sign changes of derivative
    deriv = np.diff(cls_smooth)
    peaks = []
    for i in range(1, len(deriv)):
        if deriv[i-1] >= 0 and deriv[i] < 0:
            # Sub-bin quadratic interpolation
            if i + 1 < len(cls_smooth):
                # Three-point quadratic fit around the peak
                x0, x1, x2 = ell[i-1], ell[i], ell[i+1]
                y0, y1, y2 = cls_smooth[i-1], cls_smooth[i], cls_smooth[i+1]

                # Vertex of quadratic through (x0,y0), (x1,y1), (x2,y2)
                denom = 2.0 * ((y0 - y1) * (x1 - x2) - (y1 - y2) * (x0 - x1))
                if abs(denom) > 1e-30:
                    x_peak = ((x0 + x1) * (y0 - y1) * (x1 - x2)
                              - (x1 + x2) * (y1 - y2) * (x0 - x1)
                              - (y0 - y1) * (y1 - y2) * (x0 - x2)) / denom
                else:
                    x_peak = x1
            else:
                x_peak = ell[i]

            if x_peak > 100:  # Ignore the low-ℓ rise
                peaks.append(x_peak)
                if len(peaks) >= n_peaks:
                    break

    return np.array(peaks)


# ═════════════════════════════════════════════════════════════════════════════
# ── Main Analysis ────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 72)
    print("CASSI BOLTZMANN PIPELINE—CAMB CMB Power Spectrum with Cassi Cosmology")
    print("=" * 72)
    print()
    print(f"CAMB version: {camb.__version__}")
    print()

    # ═══════════════════════════════════════════════════════════════════════
    # 1. Run ΛCDM baseline
    print("  Building parameters...")
    pars_lcdm = build_params(w=-1.0, wa=0.0)
    print("  Running CAMB...")
    ell_lcdm, cls_lcdm, cls_lcdm_unl, derived_lcdm = run_camb(pars_lcdm)
    da_lcdm = derived_lcdm['DAstar']
    rs_lcdm = derived_lcdm['rstar']
    rd_lcdm = derived_lcdm['rdrag']
    ts_lcdm = derived_lcdm['thetastar']
    zs_lcdm = derived_lcdm['zstar']
    print(f"  ℓ bins: {len(ell_lcdm)}")
    print(f"  D_A(z*):   {da_lcdm:.4f} Mpc")
    print(f"  r_s(z*):   {rs_lcdm:.4f} Mpc")
    print(f"  r_drag:    {rd_lcdm:.4f} Mpc")
    print(f"  θ*:        {ts_lcdm:.6f} rad")
    print(f"  z*:        {zs_lcdm:.2f}")
    n_lcdm = len(ell_lcdm)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. Run Cassi CPL (w₀, wₐ, standard P(k))
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*72}")
    print("2. CASSI CPL (w₀ = {:.3f}, wₐ = {:.3f}, standard P(k))".format(
        W0_CASSI, WA_CASSI))
    print(f"{'─'*72}")
    print("  Building parameters...")
    pars_cpl = build_params(w=W0_CASSI, wa=WA_CASSI)
    print(f"  DarkEnergy model: {type(pars_cpl.DarkEnergy).__name__}")
    print(f"  w = {pars_cpl.DarkEnergy.w:.4f},  wa = {pars_cpl.DarkEnergy.wa:.4f}")
    print("  Running CAMB...")
    ell_cpl, cls_cpl, cls_cpl_unl, derived_cpl = run_camb(pars_cpl)
    da_cpl = derived_cpl['DAstar']
    rs_cpl = derived_cpl['rstar']
    rd_cpl = derived_cpl['rdrag']
    ts_cpl = derived_cpl['thetastar']
    zs_cpl = derived_cpl['zstar']
    print(f"  ℓ bins: {len(ell_cpl)}")
    print(f"  D_A(z*):   {da_cpl:.4f} Mpc")
    print(f"  r_s(z*):   {rs_cpl:.4f} Mpc")
    print(f"  r_drag:    {rd_cpl:.4f} Mpc")
    print(f"  θ*:        {ts_cpl:.6f} rad")
    print(f"  z*:        {zs_cpl:.2f}")
    n_cpl = len(ell_cpl)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. Align ℓ grids—CAMB returns different lengths for different DE models
    # ═══════════════════════════════════════════════════════════════════════
    n_common = min(n_lcdm, n_cpl)
    ell = np.arange(n_common)  # common ℓ grid
    print(f"\n{'─'*72}")
    print(f"  Aligned ℓ grids: ΛCDM={n_lcdm}, CPL={n_cpl} → common={n_common}")
    print(f"{'─'*72}")
    # Truncate all arrays to common length
    cls_lcdm = cls_lcdm[:n_common]
    cls_lcdm_unl = cls_lcdm_unl[:n_common]
    cls_cpl = cls_cpl[:n_common]
    cls_cpl_unl = cls_cpl_unl[:n_common]

    # ═══════════════════════════════════════════════════════════════════════
    # 4. Cassi full (CPL + Qi transfer function)
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*72}")
    print("4. CASSI FULL (CPL + Qi transfer function)")
    print(f"{'─'*72}")
    print(f"  Qi parameters: q₀ = {Q0}, k_Qi = {K_QI} h/Mpc, ξ = φ⁶ ≈ {XI:.3f}")
    q_pivot = qi_coherence(K_PIVOT_CMB)
    t_pivot = 1 + XI * q_pivot
    print(f"  T_Qi pivot: k_pivot = {K_PIVOT_CMB} Mpc⁻¹, q_pivot = {q_pivot:.6f}")
    print(f"  1 + ξ·q_pivot = {t_pivot:.4f} (normalisation denominator)")
    cls_full, cls_full_unl, t_qi_vals = apply_qi_transfer(
        ell, cls_cpl, cls_cpl_unl, da_cpl)
    print(f"  T_Qi at ℓ=2 (k ≈ {2/da_cpl:.4f}):  {t_qi_vals[2]:.4f}")
    print(f"  T_Qi at ℓ=10 (k ≈ {10/da_cpl:.4f}): {t_qi_vals[10]:.4f}")
    print(f"  T_Qi at ℓ=100 (k ≈ {100/da_cpl:.4f}): {t_qi_vals[100]:.4f}")
    print(f"  T_Qi at ℓ=1000 (k ≈ {1000/da_cpl:.4f}): {t_qi_vals[1000]:.4f}")

    # ═══════════════════════════════════════════════════════════════════════
    # 5. Qi only (w = -1 + Qi transfer function)
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*72}")
    print("5. QI ONLY (w = -1, Qi transfer function)")
    print(f"{'─'*72}")
    cls_qi, cls_qi_unl, _ = apply_qi_transfer(
        ell, cls_lcdm, cls_lcdm_unl, da_lcdm)

    # ═══════════════════════════════════════════════════════════════════════
    # 6. Diagnostics
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*72}")
    print("6. DIAGNOSTICS")
    print(f"{'─'*72}")

    # Sound horizon shift
    drs = rs_cpl - rs_lcdm
    drs_pct = 100 * drs / rs_lcdm
    print(f"\n  6a. Sound horizon r_s(z*):")
    print(f"      ΛCDM:  {rs_lcdm:.3f} Mpc")
    print(f"      Cassi: {rs_cpl:.3f} Mpc")
    print(f"      Δr_s = {drs:.3f} Mpc ({drs_pct:+.4f}%)")

    # Angular scale shift
    dts = ts_cpl - ts_lcdm
    dts_pct = 100 * dts / ts_lcdm
    print(f"\n  6b. Angular scale θ*:")
    print(f"      ΛCDM:  {ts_lcdm:.6f} rad ({ts_lcdm * 180 / np.pi * 60:.3f} arcmin)")
    print(f"      Cassi: {ts_cpl:.6f} rad ({ts_cpl * 180 / np.pi * 60:.3f} arcmin)")
    print(f"      Δθ* = {dts:.6f} rad ({dts_pct:+.4f}%)")

    # Acoustic peak shifts
    print(f"\n  6c. Acoustic peak positions (first 3):")
    idx_lcdm = find_acoustic_peaks(ell[:2000], cls_lcdm[:2000], n_peaks=3)
    idx_cpl = find_acoustic_peaks(ell[:2000], cls_cpl[:2000], n_peaks=3)
    idx_full = find_acoustic_peaks(ell[:2000], cls_full[:2000], n_peaks=3)

    for i, (pl, pc, pf) in enumerate(zip(idx_lcdm, idx_cpl, idx_full), 1):
        dpeak = pc - pl
        print(f"      Peak {i}: ΛCDM ℓ = {pl:.1f},  Cassi ℓ = {pc:.1f},  "
              f"Δℓ = {dpeak:+.2f}")

    # Low-ℓ ISW ratio
    print(f"\n  6d. Low-ℓ enhancement (ISW regime):")
    ell_low = (ell >= 2) & (ell <= 30)
    ratio_cpl = cls_cpl[ell_low] / cls_lcdm[ell_low]
    ratio_full = cls_full[ell_low] / cls_lcdm[ell_low]
    mean_ratio_cpl = np.mean(ratio_cpl)
    mean_ratio_full = np.mean(ratio_full)
    ratio_qi = cls_qi[ell_low] / cls_lcdm[ell_low]
    mean_ratio_qi = np.mean(ratio_qi)
    print(f"      CPL/ΛCDM mean(ℓ=2-30): {mean_ratio_cpl:.4f}")
    print(f"      Full/ΛCDM mean(ℓ=2-30): {mean_ratio_full:.4f}")
    print(f"      Qi/ΛCDM mean(ℓ=2-30):   {mean_ratio_qi:.4f}")

    # H₀ consistency
    print(f"\n  6e. H₀ consistency check:")
    h0_input = H0
    # The angular scale θ* = r_s / D_A, so D_A = r_s / θ*
    da_cmb_lcdm = rs_lcdm / ts_lcdm
    da_cmb_cpl = rs_cpl / ts_cpl
    da_ratio = da_cmb_cpl / da_cmb_lcdm
    # H₀ ∝ 1/D_A(z*) for fixed Ω_m
    h0_shift_pct = 100 * (1 / da_ratio - 1)
    print(f"      H₀ input: {h0_input:.1f} km/s/Mpc (both models)")
    print(f"      D_A(z*) ΛCDM: {da_cmb_lcdm:.1f} Mpc")
    print(f"      D_A(z*) Cassi: {da_cmb_cpl:.1f} Mpc")
    print(f"      Implied H₀ shift: {h0_shift_pct:+.4f}%"
          f" ({h0_input * (1 + h0_shift_pct/100):.2f} km/s/Mpc effective)")

    # ═══════════════════════════════════════════════════════════════════════
    # 7. Figure: 4-panel summary
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*72}")
    print("7. RENDERING FIGURE")
    print(f"{'─'*72}")

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    outpath = FIGURE_DIR / 'boltzmann_cassi.png'

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(
        'Cassi Boltzmann Pipeline—CMB TT Power Spectrum with Modified Cosmology',
        fontsize=14, fontweight='bold', y=0.98)

    # ── Panel 1: Cℓ TT (log-log, ℓ = 2-2500) ────────────────────────────
    ax1 = axes[0, 0]
    ell_plot = ell[2:]  # Skip ℓ=0,1

    ax1.loglog(ell_plot, cls_lcdm[2:], 'k-', lw=1.8, label='ΛCDM baseline')
    ax1.loglog(ell_plot, cls_full[2:], 'C3-', lw=1.8, label='Cassi full (CPL + Qi)')
    ax1.loglog(ell_plot, cls_cpl[2:], 'C0--', lw=1.2, alpha=0.7, label='Cassi CPL only')
    ax1.loglog(ell_plot, cls_qi[2:], 'C2:', lw=1.2, alpha=0.7, label='Qi only')

    ax1.set_xlabel('Multipole ℓ', fontsize=12)
    ax1.set_ylabel(r'$C_\ell^{\rm TT}$ [$\mu$K$^2$]', fontsize=12)
    ax1.set_title('CMB Temperature Power Spectrum', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=9, loc='lower left')
    ax1.set_xlim(2, LMAX)
    ax1.grid(True, alpha=0.3, which='both')
    ax1.text(0.02, 0.02, 'log-log', transform=ax1.transAxes,
             fontsize=8, color='gray', va='bottom')

    # ── Panel 2: Residual ΔCℓ / Cℓ ──────────────────────────────────────
    ax2 = axes[0, 1]

    # Mask ℓ=0,1 and smooth for visual clarity
    mask = ell >= 2
    ell_m = ell[mask]

    # CPL residual
    resid_cpl = (cls_cpl[mask] - cls_lcdm[mask]) / cls_lcdm[mask] * 100
    resid_full = (cls_full[mask] - cls_lcdm[mask]) / cls_lcdm[mask] * 100
    resid_qi = (cls_qi[mask] - cls_lcdm[mask]) / cls_lcdm[mask] * 100

    # Smooth residuals for readability
    from scipy.ndimage import uniform_filter1d
    resid_cpl_s = uniform_filter1d(resid_cpl, size=9, mode='nearest')
    resid_full_s = uniform_filter1d(resid_full, size=9, mode='nearest')
    resid_qi_s = uniform_filter1d(resid_qi, size=9, mode='nearest')

    ax2.plot(ell_m, resid_cpl_s, 'C0-', lw=1.5, alpha=0.8, label='CPL—ΛCDM')
    ax2.plot(ell_m, resid_full_s, 'C3-', lw=1.8, label='Cassi full—ΛCDM')
    ax2.plot(ell_m, resid_qi_s, 'C2--', lw=1.2, alpha=0.7, label='Qi only—ΛCDM')

    ax2.axhline(0, color='k', lw=0.8, alpha=0.5)
    ax2.set_xlabel('Multipole ℓ', fontsize=12)
    ax2.set_ylabel(r'$\Delta C_\ell / C_\ell$ [%]', fontsize=12)
    ax2.set_title('Residual: Deviation from ΛCDM', fontsize=12, fontweight='bold')
    ax2.set_xlim(2, LMAX)
    ax2.legend(fontsize=9, loc='lower right')
    ax2.grid(True, alpha=0.3)

    # ── Panel 3: Low-ℓ zoom (ℓ = 2-50, ISW regime) ─────────────────────
    ax3 = axes[1, 0]

    low_mask = (ell >= 2) & (ell <= 50)
    ell_low_plot = ell[low_mask]

    ax3.plot(ell_low_plot, cls_lcdm[low_mask], 'k-', lw=2, label='ΛCDM baseline')
    ax3.plot(ell_low_plot, cls_full[low_mask], 'C3-', lw=2, label='Cassi full')
    ax3.plot(ell_low_plot, cls_cpl[low_mask], 'C0--', lw=1.2, alpha=0.7,
             label='Cassi CPL')
    ax3.plot(ell_low_plot, cls_qi[low_mask], 'C2:', lw=1.2, alpha=0.7,
             label='Qi only')

    ax3.set_xlabel('Multipole ℓ', fontsize=12)
    ax3.set_ylabel(r'$C_\ell^{\rm TT}$ [$\mu$K$^2$]', fontsize=12)
    ax3.set_title('Low-ℓ: ISW Regime', fontsize=12, fontweight='bold')
    ax3.set_xlim(2, 50)
    ax3.legend(fontsize=9, loc='upper right')
    ax3.grid(True, alpha=0.3)

    # Annotate ISW region
    ax3.axvspan(2, 10, alpha=0.08, color='C1', label='_nolegend_')
    ax3.text(4, 0.9 * ax3.get_ylim()[1], 'ISW\nplateau', fontsize=8,
             color='C1', alpha=0.7, fontstyle='italic')

    # ── Panel 4: T_Qi(k) vs k ────────────────────────────────────────────
    ax4 = axes[1, 1]

    k_grid = np.logspace(-3, 2, 500)  # [h/Mpc]
    t_grid = qi_transfer(k_grid)
    q_grid = qi_coherence(k_grid)

    ax4.semilogx(k_grid, t_grid, 'C3-', lw=2.5, label=r'$T_{\rm Qi}(k)$')
    ax4.axhline(1.0, color='k', lw=0.8, alpha=0.4, linestyle='--')
    ax4.axvline(K_PIVOT_CMB, color='gray', lw=0.8, alpha=0.5, linestyle=':',
                label=f'$k_{{\\rm pivot}} = {K_PIVOT_CMB}$')
    ax4.axvline(K_QI, color='C2', lw=1, alpha=0.6, linestyle='--',
                label=f'$k_{{\\rm Qi}} = {K_QI}$')

    # Add a second y-axis for q(k)
    ax4_twin = ax4.twinx()
    ax4_twin.semilogx(k_grid, q_grid, 'C2:', lw=1.5, alpha=0.7,
                      label=r'$q(k)$')
    ax4_twin.set_ylabel(r'$q(k)$', fontsize=11, color='C2')
    ax4_twin.tick_params(axis='y', labelcolor='C2')

    # Mark CMB ℓ range on top axis
    ax4_top = ax4.twiny()
    ell_top = np.array([10, 100, 1000, 2500])
    k_top = ell_top / da_lcdm
    ax4_top.set_xlim(ax4.get_xlim())
    ax4_top.set_xticks(k_top)
    ax4_top.set_xticklabels([f'ℓ={e}' for e in ell_top], fontsize=7)
    ax4_top.set_xlabel(r'ℓ $\approx k \cdot D_A(z_*)$', fontsize=10)

    ax4.set_xlabel('Wavenumber $k$ [$h$ / Mpc]', fontsize=12)
    ax4.set_ylabel(r'$T_{\rm Qi}(k)$', fontsize=12, color='C3')
    ax4.tick_params(axis='y', labelcolor='C3')
    ax4.set_title('Qi Transfer Function', fontsize=12, fontweight='bold')
    ax4.set_xlim(1e-3, 100)
    ax4.set_ylim(0, None)
    ax4.grid(True, alpha=0.3, which='both')

    # Combined legend
    lines1, labels1 = ax4.get_legend_handles_labels()
    lines2, labels2 = ax4_twin.get_legend_handles_labels()
    ax4.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')

    # ── Layout and save ──────────────────────────────────────────────────
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    print(f"\n  >>> Saved figure: {outpath}")
    plt.close(fig)

    # ═══════════════════════════════════════════════════════════════════════
    # 8. Summary
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print("SUMMARY OF RESULTS")
    print(f"{'='*72}")
    print(f"""
  Sound horizon:
    ΛCDM:  r_s(z*) = {rs_lcdm:.3f} Mpc
    Cassi: r_s(z*) = {rs_cpl:.3f} Mpc
    Δr_s = {drs:+.3f} Mpc ({drs_pct:+.4f}%)

  Angular scale:
    ΛCDM:  θ* = {ts_lcdm:.6f} rad ({ts_lcdm * 180 / np.pi * 60:.3f} arcmin)
    Cassi: θ* = {ts_cpl:.6f} rad ({ts_cpl * 180 / np.pi * 60:.3f} arcmin)
    Δθ* = {dts:.6f} rad ({dts_pct:+.4f}%)

  Peak positions:
""")
    for i, (pl, pc, pf) in enumerate(zip(idx_lcdm, idx_cpl, idx_full), 1):
        print(f"    Peak {i}: ΛCDM ℓ = {pl:.1f},  Cassi ℓ = {pc:.1f},  Δℓ = {pc-pl:+.2f}")

    print(f"""
  Low-ℓ ISW ratio (ℓ = 2-30):
    CPL / ΛCDM:    {mean_ratio_cpl:.4f}
    Full / ΛCDM:   {mean_ratio_full:.4f}
    Qi / ΛCDM:     {mean_ratio_qi:.4f}

  H₀ consistency from CMB:
    Implied H₀ shift from D_A(z*): {h0_shift_pct:+.4f}%
    Effective H₀: {h0_input * (1 + h0_shift_pct/100):.2f} km/s/Mpc

  Qi transfer function (T_Qi at selected k):
    T_Qi(k = 0.01) = {qi_transfer(0.01):.4f}
    T_Qi(k = 0.05) = {qi_transfer(0.05):.4f}  (pivot)
    T_Qi(k = 0.10) = {qi_transfer(0.10):.4f}
    T_Qi(k = 0.50) = {qi_transfer(0.50):.4f}
    T_Qi(k = 1.00) = {qi_transfer(1.00):.4f}
""")

    print(f"{'='*72}")
    print("CASSI BOLTZMANN PIPELINE—COMPLETE")
    print(f"{'='*72}")


if __name__ == '__main__':
    main()
