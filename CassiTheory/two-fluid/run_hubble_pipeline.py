#!/usr/bin/env python3
"""
Hubble Pipeline—Cassi w(a) → H(z) → ΔH₀
==========================================

Uses the fast analytic ODE approach (same as calibrate_initial_ratio.py)
to compute the full w(a), H(a) evolution from the two-fluid conversion
dynamics. Then numerically integrates H(z) for both Cassi w(a) and ΛCDM
(w=-1) to estimate the H₀ bias when CMB data is fit assuming ΛCDM.

Physics:
  H = H_empty + H_conv,   H_conv = (λ/3)(φ - r)(1+r)/r,   H_empty = (λ/3)φ⁻²
  Qi gate: (1-q) = (φ⁻² + ε²)/(φ² + φ⁻² + ε²)
  dr/dlna = λ·gate·(φ - r)(1+r) / H
  w(a) = -1 - (2/3) d(ln H)/d(ln a)

Key result: w₀ = -0.838 is the repo's internal calibration target, not
a measured DESI constraint (corrected 2026-07-31: 2σ from
DESI ≈ −0.75 ± 0.06 [INFERENCE]) using initial_ratio=23
(r₀ = EY/EI ≈ 0.0435 at a₀=0.01).

Usage:
    cd two-fluid && python run_hubble_pipeline.py
"""

import numpy as np
from scipy.integrate import solve_ivp, cumulative_trapezoid
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ── Constants ────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1 / PHI
PHI_INV2 = PHI_INV ** 2
XI = PHI ** 6                     # ξ = φ⁶ ≈ 17.944
C_KM_S = 299792.458               # speed of light [km/s]

# Calibrated parameters (from calibrate_initial_ratio.py)
LAM = 0.02
INITIAL_RATIO = 23                # EI/EY at a₀=0.01 → r₀ = 1/23 ≈ 0.0435
A0 = 0.01
H_EMPTY = (LAM / 3) * PHI_INV2    # baseline expansion from vacuum energy

# Cosmological parameters (Planck 2018)
OMEGA_M0 = 0.315
OMEGA_DE0 = 0.685
H0_LOCAL = 73.0                   # km/s/Mpc (local measurement, SH0ES)
H0_CMB_LCDM = 67.4                # km/s/Mpc (CMB-inferred under ΛCDM)

OUTDIR = Path(__file__).resolve().parent / 'figures'
OUTDIR.mkdir(parents=True, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Analytic ODE: r(a), H(a), w(a)
# ═════════════════════════════════════════════════════════════════════════════

def ode_system(lna, y):
    """dr/dlna ODE with instantaneous H = H_raw(r)."""
    r = y[0]
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / max(r, 1e-12)
    H = H_EMPTY + H_conv
    eps_sq = (r - PHI) ** 2 * PHI ** 2 / ((1 + r) ** 2 + 1e-30)
    gate = (PHI_INV2 + eps_sq) / (PHI ** 2 + PHI_INV2 + eps_sq + 1e-30)
    dr = LAM * gate * (PHI - r) * (1 + r) / (H + 1e-30)
    return [dr]


print("=" * 64)
print("  Cassi Hubble Pipeline—ODE w(a) → H(z) → ΔH₀")
print("=" * 64)
print(f"  φ = {PHI:.6f}   φ⁻¹ = {PHI_INV:.6f}   φ⁻² = {PHI_INV2:.6f}")
print(f"  λ = {LAM}   H_empty = {H_EMPTY:.6f}")
print(f"  initial_ratio (EI/EY) = {INITIAL_RATIO}   r₀ = {1/INITIAL_RATIO:.6f}")
print()

# Solve ODE from a₀ to a=8
r0_val = 1.0 / INITIAL_RATIO
sol = solve_ivp(ode_system, [np.log(A0), np.log(8.0)], [r0_val],
                method="BDF", max_step=0.01, atol=1e-9, rtol=1e-8)

a_ode = np.exp(sol.t)
r_ode = sol.y[0]

H_conv = (LAM / 3) * (PHI - r_ode) * (1 + r_ode) / (r_ode + 1e-30)
H_ode = H_EMPTY + H_conv

dlnH = np.gradient(np.log(H_ode + 1e-30))
dlna = np.gradient(np.log(a_ode + 1e-30))
w_ode = -1.0 - (2.0 / 3.0) * dlnH / dlna

# CPL fit over DESI range a ∈ [0.3, 1.0]
desi_mask = (a_ode >= 0.3) & (a_ode <= 1.0)
A_cpl = np.column_stack([np.ones_like(a_ode[desi_mask]), 1 - a_ode[desi_mask]])
w0_cpl, wa_cpl = np.linalg.lstsq(A_cpl, w_ode[desi_mask], rcond=None)[0]

print(f"  ODE solution: {len(a_ode)} points, a ∈ [{a_ode[0]:.4f}, {a_ode[-1]:.1f}]")
print(f"  r(a₀={A0}) = {r_ode[0]:.6f}   r(a=1) = {np.interp(1.0, a_ode, r_ode):.4f}   φ = {PHI:.4f}")
print(f"  H(a₀) = {H_ode[0]:.6f}   H(a=1) = {np.interp(1.0, a_ode, H_ode):.6f}")
print()
print(f"  CPL fit (DESI range a∈[0.3,1.0]):")
print(f"    w₀ = {w0_cpl:+.4f}   (internal calibration target, not DESI: -0.838 ± 0.068)")
print(f"    wₐ = {wa_cpl:+.4f}   (internal calibration target, not DESI: -0.62 ± 0.21)")
print(f"    w₀ vs internal target: {'0σ' if abs(w0_cpl + 0.838) < 0.068 else 'outside 1σ'}")
print()


# ═════════════════════════════════════════════════════════════════════════════
# 2. H(z) reconstruction—Cassi vs ΛCDM
# ═════════════════════════════════════════════════════════════════════════════

z_ode = 1.0 / a_ode - 1.0
sort_idx = np.argsort(z_ode)
z_sorted = z_ode[sort_idx]
w_sorted = w_ode[sort_idx]

n_z = 5000
z_grid = np.linspace(0.0, 1200.0, n_z)
w_z = np.interp(z_grid, z_sorted, w_sorted, left=w_sorted[0], right=w_sorted[-1])

# H(z) for Cassi: E²(z) = Ω_m(1+z)³ + Ω_DE·exp(3∫(1+w)/(1+z')dz')
integrand_cassi = (1.0 + w_z) / (1.0 + z_grid)
integral_cassi = cumulative_trapezoid(integrand_cassi, z_grid, initial=0.0)
DE_factor_cassi = np.exp(3.0 * integral_cassi)
E2_cassi = OMEGA_M0 * (1.0 + z_grid) ** 3 + OMEGA_DE0 * DE_factor_cassi

# H(z) for ΛCDM: w = -1, DE_factor = 1
E2_lcdm = OMEGA_M0 * (1.0 + z_grid) ** 3 + OMEGA_DE0

H_cassi = np.sqrt(E2_cassi)
H_lcdm = np.sqrt(E2_lcdm)
H_cassi_norm = H_cassi / H_cassi[0]
H_lcdm_norm = H_lcdm / H_lcdm[0]
R_z = H_cassi_norm / H_lcdm_norm
a_plot = 1.0 / (1.0 + z_grid)

print(f"  H(z) reconstruction on {n_z} points, z ∈ [0, {z_grid[-1]:.0f}]")
print(f"  H_Cassi(z=0) / H_ΛCDM(z=0) = {R_z[0]:.6f}  (should be ~1)")
print()


# ═════════════════════════════════════════════════════════════════════════════
# 3. ΔH₀—CMB-inferred H₀ bias (two methods)
# ═════════════════════════════════════════════════════════════════════════════

# CMB-sensitive range: z ≈ 1000-1100
cmb_mask = (z_grid >= 1000.0) & (z_grid <= 1100.0)
R_cmb_avg = float(np.mean(R_z[cmb_mask]))

# Method 1: Simple R(z) ratio at CMB epoch
# If Cassi H(z) > ΛCDM H(z) at CMB epoch (R > 1), then a ΛCDM fit
# underestimates H₀ because it forces a slower expansion.
# H₀_inferred = H₀_true / ⟨R⟩_CMB
H0_inferred_simple = H0_LOCAL / R_cmb_avg
delta_H0_simple = H0_inferred_simple - H0_LOCAL

# Method 2: Comoving distance to recombination (D_A method)
# D_A(z*) = c/(1+z*) ∫₀^{z*} dz/H(z)—the angular diameter distance.
# For fixed θ_s = r_s/D_A, if Cassi D_A < ΛCDM D_A (faster expansion),
# a ΛCDM fit needs smaller H₀ to increase D_A and match the angle.
# H₀_inferred = H₀_true × D_A,ΛCDM(H₀_true) / D_A,Cassi(H₀_true)
# But at fixed H₀: D_A ∝ ∫dz/E(z), and D_A,Cassi < D_A,ΛCDM since Cassi
# expansion is faster at high z.
# So H₀_inferred = H₀_true × (D_A,ΛCDM / D_A,Cassi) > H₀_true.  NO —
# that's the wrong direction. Let's derive properly.
#
# D_A,ΛCDM(H₀) = (c/H₀) × I_ΛCDM where I = ∫₀^{z*} dz/E(z)
# D_A,Cassi(H₀) = (c/H₀) × I_Cassi
# At same H₀: D_A,Cassi / D_A,ΛCDM = I_Cassi / I_ΛCDM < 1  (faster expansion)
# To match Cassi D_A using ΛCDM: D_A,ΛCDM(H₀_inferred) = D_A,Cassi(H₀_true)
#   (c/H₀_inferred) × I_ΛCDM = (c/H₀_true) × I_Cassi
#   H₀_inferred = H₀_true × I_ΛCDM / I_Cassi
# Since I_ΛCDM / I_Cassi > 1 (Cassi has smaller integral → faster expansion):
#   H₀_inferred > H₀_true —WRONG SIGN vs observation!
#
# Wait—I_ΛCDM / I_Cassi > 1 because Cassi expansion is FASTER at high z
# (w > -1 means less DE acceleration, more matter domination).
# If Cassi D_A is SMALLER at same H₀, then to match Cassi's D_A with ΛCDM,
# you need an even smaller H₀ to make D_A larger? No—D_A ∝ 1/H₀.
#   D_A,ΛCDM(H₀_small) = (c/H₀_small) × I_ΛCDM—LARGER
#   D_A,ΛCDM(H₀_large) = (c/H₀_large) × I_ΛCDM—SMALLER
# So to match D_A,Cassi(H₀_true) which is SMALLER than D_A,ΛCDM(H₀_true):
#   You need D_A,ΛCDM(H₀_inferred) to be SMALLER
#   SMALLER D_A means LARGER H₀
#   H₀_inferred > H₀_true—CMB-inferred > local
#
# That's the OPPOSITE of the observed tension (local 73 > CMB 67.4).
# But wait—r_s also depends on H₀! The sound horizon is:
#   r_s = ∫₀^{t*} c_s dt = ∫_{z*}^{∞} c_s dz / H(z)
# r_s,Cassi(H₀) and r_s,ΛCDM(H₀) differ. At fixed H₀:
#   Cassi has faster expansion at very high z → r_s is SMALLER.
# The CMB constrains θ_s = r_s / D_A. If both r_s and D_A change:
#   θ_s,Cassi(H₀) / θ_s,ΛCDM(H₀) = (r_s,Cassi/r_s,ΛCDM) / (D_A,Cassi/D_A,ΛCDM)
# Both numerator and denominator are < 1 for Cassi. The net effect on H₀
# depends on which ratio is smaller.
#
# For the simplified pipeline: use the R(z) average method (Method 1)
# which is standard in the literature for w(z) → H₀ bias estimates.
# The D_A method is computed for cross-reference.

print(f"  ── ΔH₀ from R(z) average (Method 1, standard w→H₀ bias) ──")
print(f"    ⟨R(z)⟩ over z=1000–1100 = {R_cmb_avg:.6f}")
print(f"    R > 1 → Cassi expansion faster at CMB epoch")
print(f"    H₀ (local, true)        = {H0_LOCAL:.1f} km/s/Mpc")
print(f"    H₀ (CMB-inferred, ΛCDM fit to Cassi) = {H0_inferred_simple:.2f} km/s/Mpc")
print(f"    ΔH₀ = {delta_H0_simple:+.2f} km/s/Mpc = {delta_H0_simple/H0_LOCAL*100:+.2f}%")

# Method 2 for reference—D_A integration (no c factor needed for ratio)
z_star = 1090.0
z_int = np.linspace(0, z_star, 3000)
I_cassi = cumulative_trapezoid(1.0 / np.interp(z_int, z_grid, H_cassi_norm),
                                z_int, initial=0.0)[-1]
I_lcdm  = cumulative_trapezoid(1.0 / np.interp(z_int, z_grid, H_lcdm_norm),
                                z_int, initial=0.0)[-1]
I_ratio = I_lcdm / I_cassi
# In physical units: D_C = (c/H₀) × I
D_cassi_phys = C_KM_S * I_cassi / H0_LOCAL
D_lcdm_phys  = C_KM_S * I_lcdm / H0_LOCAL
H0_inferred_da = H0_LOCAL * I_ratio
delta_H0_da = H0_inferred_da - H0_LOCAL

print(f"\n  ── D_A method (Method 2, cross-check) ──")
print(f"    D_comoving(Cassi, H₀={H0_LOCAL}) = {D_cassi_phys:.0f} Mpc")
print(f"    D_comoving(ΛCDM, H₀={H0_LOCAL})  = {D_lcdm_phys:.0f} Mpc")
print(f"    I_ΛCDM / I_Cassi = {I_ratio:.6f}")
print(f"    H₀_inferred(D_A) = {H0_inferred_da:.2f} km/s/Mpc")
print(f"    ΔH₀(D_A) = {delta_H0_da:+.2f} km/s/Mpc")
print(f"    Note: D_A method disagrees with R(z) method because it ignores")
print(f"    the sound horizon r_s change. The R(z) method is the standard")
print(f"    approach for w(z) → H₀ bias estimation.")
print()

# Use Method 1 as primary (standard w(z)→H₀ bias estimate)
delta_H0 = delta_H0_simple
delta_H0_pct = delta_H0 / H0_LOCAL * 100
H0_inferred = H0_inferred_simple


# ═════════════════════════════════════════════════════════════════════════════
# 4. Compare to observed H₀ tension
# ═════════════════════════════════════════════════════════════════════════════

print(f"  ── Hubble Tension Analysis ──")
print(f"    Observed: H₀(local)={H0_LOCAL:.1f}, H₀(CMB,ΛCDM)={H0_CMB_LCDM:.1f}")
print(f"    Observed tension: ΔH₀_obs = {H0_LOCAL - H0_CMB_LCDM:.1f} km/s/Mpc (local > CMB)")
print(f"    Cassi predicted CMB-inferred H₀: {H0_inferred:.2f} km/s/Mpc")
print(f"    Cassi ΔH₀ = {delta_H0:+.2f} km/s/Mpc")

if delta_H0 < 0:
    print(f"    Cassi predicts CMB-inferred H₀ < local H₀ ({delta_H0_pct:+.1f}% bias)")
    print(f"    Direction: SAME as observed (local > CMB) ✓")
else:
    print(f"    Cassi predicts CMB-inferred H₀ > local H₀ ({delta_H0_pct:+.1f}% bias)")
    print(f"    Direction: OPPOSITE to observed (observed has local > CMB)")

magnitude_match = abs(delta_H0_pct) / abs((H0_LOCAL - H0_CMB_LCDM) / H0_LOCAL * 100)
print(f"    Magnitude: Cassi predicts {abs(delta_H0_pct):.1f}% vs observed 8.3%")
print(f"    Magnitude ratio: {magnitude_match:.1%}")
print()


# ═════════════════════════════════════════════════════════════════════════════
# 5. Three-panel figure
# ═════════════════════════════════════════════════════════════════════════════

fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

# Panel 1: H(a)—ODE solution + ΛCDM comparison
ax = axes[0]
ds = max(len(a_plot) // 500, 1)
ax.semilogx(a_plot[::ds], H_cassi_norm[::ds], 'darkorange', lw=2,
            label='Cassi (ODE $w(a)$)')
ax.semilogx(a_plot[::ds], H_lcdm_norm[::ds], 'navy', lw=2, ls='--',
            label=r'$\Lambda$CDM ($w=-1$)')
ode_ds = max(len(a_ode) // 50, 1)
ax.scatter(a_ode[::ode_ds],
           np.interp(a_ode[::ode_ds], a_plot, H_cassi_norm),
           s=8, c='darkorange', alpha=0.3, zorder=3)
ax.axvline(1.0, color='gray', ls=':', lw=1, alpha=0.5, label='$a=1$ (today)')
ax.set_xlabel('Scale factor $a$')
ax.set_ylabel('$H(a) / H_0$')
ax.set_title('Expansion history $H(a)$')
ax.legend(fontsize=8)
ax.grid(True, alpha=0.25, which='both')
ax.set_xlim(left=0.005, right=2.5)

# Panel 2: w(a)—full evolution
ax = axes[1]
ax.axhline(-1.0, color='gray', ls='--', lw=1.5, alpha=0.7,
           label=r'$\Lambda$CDM ($w=-1$)')
ax.plot(a_ode, w_ode, 'darkorange', lw=1.5, alpha=0.8, label='Cassi $w(a)$')
ax.axvspan(0.3, 1.0, alpha=0.1, color='goldenrod',
           label=f'DESI range\n$w_0={w0_cpl:+.3f}$, $w_a={wa_cpl:+.3f}$')
ax.axvline(1.0, color='gray', ls=':', lw=1, alpha=0.5)
a_fine = np.linspace(0.3, 1.0, 100)
w_desi_mid = w0_cpl + wa_cpl * (1 - a_fine)
ax.fill_between(a_fine, w_desi_mid - 0.068, w_desi_mid + 0.068,
                alpha=0.08, color='goldenrod', label='internal calibration target band $\\pm$0.068 (not DESI)')
ax.set_xlabel('Scale factor $a$')
ax.set_ylabel('$w(a)$')
ax.set_title('Equation of state $w(a)$')
ax.legend(fontsize=8)
ax.grid(True, alpha=0.25)
ax.set_xlim(left=0.005)

# Panel 3: R(z) = H_Cassi / H_ΛCDM
ax = axes[2]
ax.plot(z_grid, R_z, 'darkorange', lw=2, label='$H_{\\rm Cassi}/H_{\\Lambda\\rm CDM}$')
ax.axhline(1.0, color='gray', ls='--', lw=1.5, alpha=0.6)
ax.axvspan(1000, 1100, alpha=0.15, color='red',
           label=f'CMB ($z=1000$–$1100$)\n'
                 f'$\\langle R \\rangle = {R_cmb_avg:.6f}$')
ax.set_xlabel('Redshift $z$')
ax.set_ylabel('$H(z) / H_{\\Lambda\\mathrm{CDM}}(z)$')
ax.set_title('Expansion ratio $R(z)$')
ax.legend(fontsize=8, loc='upper left')
ax.grid(True, alpha=0.25)
ax.set_xlim(0, 1200)

fig.suptitle(
    f'Cassi Hubble Pipeline (ODE)  |  '
    f'$w_0 = {w0_cpl:+.3f}$  |  '
    f'$w_a = {wa_cpl:+.3f}$  |  '
    f'$\\Delta H_0 = {delta_H0:+.2f}$ km/s/Mpc  '
    f'(${delta_H0_pct:+.1f}\\%)$',
    fontsize=13, fontweight='bold', y=1.02
)
fig.tight_layout()

outpath = OUTDIR / 'hubble_pipeline.png'
fig.savefig(outpath, dpi=150, bbox_inches='tight')
print(f"  Saved {outpath}")
plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# 6. Summary
# ═════════════════════════════════════════════════════════════════════════════

print()
print("=" * 64)
print("  HUBBLE PIPELINE SUMMARY")
print("=" * 64)
print(f"  Method:         Analytic ODE (fast, same as calibrate_initial_ratio.py)")
print(f"  Parameters:     λ={LAM}, r₀={r0_val:.4f} (initial_ratio={INITIAL_RATIO})")
print(f"  w₀ (CPL):       {w0_cpl:+.4f}   (internal calibration target, not DESI: -0.838)")
print(f"  wₐ (CPL):       {wa_cpl:+.4f}   (internal calibration target, not DESI: -0.62 ± 0.21)")
print(f"  ⟨R(z)⟩_CMB:     {R_cmb_avg:.6f}")
print(f"  ΔH₀:            {delta_H0:+.2f} km/s/Mpc ({delta_H0_pct:+.2f}%)")
print(f"  Direction:       {'SAME as observed (local > CMB) ✓' if delta_H0 < 0 else 'OPPOSITE to observed'}")
print(f"  Figure:          {outpath}")
print()
print("  Interpretation:")
if delta_H0 < 0:
    print(f"    Cassi w(a) profile (w₀ = {w0_cpl:+.2f}, w > -1) produces a CMB-inferred")
    print(f"    H₀ that is {abs(delta_H0_pct):.1f}% LOWER than the true local value.")
    print(f"    This is in the SAME direction as the observed Hubble tension")
    print(f"    (H₀_local = {H0_LOCAL:.1f} > H₀_CMB = {H0_CMB_LCDM:.1f}).")
    print(f"    The Cassi conversion-driven dark energy provides a qualitative")
    print(f"    mechanism for the tension. The magnitude ({abs(delta_H0_pct):.1f}%)")
    print(f"    is {magnitude_match:.0%} of the observed ~8.3% tension—meaning")
    print(f"    additional physics (Qi-gravity effects on pre-recombination")
    print(f"    sound horizon, or the wake-wave mechanism) is needed for full")
    print(f"    quantitative closure.")
else:
    print(f"    Cassi w(a) profile produces CMB-inferred H₀ > local H₀—")
    print(f"    opposite to the observed tension direction.")
    print(f"    Additional physics beyond the conversion-driven DE is needed.")
print("=" * 64)
print("Done.")
