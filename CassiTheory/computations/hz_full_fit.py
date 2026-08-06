#!/usr/bin/env python3
"""
Full H(z) Simultaneous Fit: Planck + SH0ES vs Cassi w(a) Models
================================================================

The registry (`parameter-inventory.md` §10; `cosmology/observational_constraints.md`
row "Ω_m/H₀ compatibility") lists "full H(z) fit pending (C3/T4)": the
documented pipeline result ΔH₀ = −7.2 km/s/Mpc (−9.9%,
`foundations/refined-numeric-predictions.md` §2.8) is a bias estimate at a
fixed local H₀, not a simultaneous fit of the CMB and distance-ladder
anchors. This script performs that fit.

Models (zero free parameters each — w₀, w_a fixed by calibration):
  1. ΛCDM            w₀ = −1.000, w_a =  0.000   (reference)
  2. Cassi baseline  w₀ = −0.870, w_a = +0.012   (Calibrated, DESI-anchored)
  3. Cassi coupling  w₀ = −0.870, w_a = −0.380   (ratified conversion→expansion
                     coupling, wa-pentagon-gate.md)
  4. Cassi ODE       w(a) from the two-fluid r(a) ODE — the actual pipeline
                     model behind the documented ΔH₀ = −7.2 (CPL fit over the
                     DESI window: w₀ ≈ −0.839, w_a ≈ +0.439, the bare form
                     without the ξ correction)

Method (the pipeline's own bias relation, run_hubble_pipeline.py Method 1):
a ΛCDM fit to a universe whose true expansion is E(z; w(a)) infers
H₀_inferred = H₀_true / ⟨R⟩_CMB, where ⟨R⟩_CMB is the mean H(z) ratio over
z ∈ [1000, 1100]. Hence the CMB anchor in model M's frame is
H₀^CMB(M) = 67.4 × ⟨R⟩_CMB(M) (Planck 2018, 67.4 ± 0.5). The SH0ES anchor is
73.0 ± 1.0 (model-independent). A single H₀ is then fit to both anchors:
χ²(H₀) = ((H₀−H₀^CMB)/0.5)² + ((H₀−73.0)/1.0)², minimized in closed form.
A D_C(z*)-based cross-check (comoving distance ratio with radiation included,
as in computations/hubble_tension_pipeline.py §3) is reported per model.

The ODE machinery below is copied verbatim from
`two-fluid/run_hubble_pipeline.py` (attribution): constants, ode_system,
and the w(a) → H(z) reconstruction on z ∈ [0, 1200].

Usage:
    python computations/hz_full_fit.py
"""

import numpy as np
from scipy.integrate import solve_ivp, cumulative_trapezoid

# ═════════════════════════════════════════════════════════════════════════
# Constants — copied from two-fluid/run_hubble_pipeline.py (attribution)
# ═════════════════════════════════════════════════════════════════════════

PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1 / PHI
PHI_INV2 = PHI_INV ** 2
LAM = 0.02
INITIAL_RATIO = 23                 # EI/EY at a₀=0.01 → r₀ = 1/23 ≈ 0.0435
A0 = 0.01
H_EMPTY = (LAM / 3) * PHI_INV2     # baseline expansion from vacuum energy
OMEGA_M0 = 0.315
OMEGA_DE0 = 0.685
OMEGA_R0 = 9.0e-5                  # radiation (cross-check only)
H0_CMB_LCDM = 67.4                 # km/s/Mpc (Planck 2018, ΛCDM interpretation)
SIGMA_CMB = 0.5                    # km/s/Mpc
H0_SH0ES = 73.0                    # km/s/Mpc (local distance ladder)
SIGMA_SH0ES = 1.0                  # km/s/Mpc

# ═════════════════════════════════════════════════════════════════════════
# ODE w(a) — copied from two-fluid/run_hubble_pipeline.py (attribution)
# ═════════════════════════════════════════════════════════════════════════

def ode_system(lna, y):
    """dr/dlna ODE with instantaneous H = H_raw(r)."""
    r = y[0]
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / max(r, 1e-12)
    H = H_EMPTY + H_conv
    eps_sq = (r - PHI) ** 2 * PHI ** 2 / ((1 + r) ** 2 + 1e-30)
    gate = (PHI_INV2 + eps_sq) / (PHI ** 2 + PHI_INV2 + eps_sq + 1e-30)
    dr = LAM * gate * (PHI - r) * (1 + r) / (H + 1e-30)
    return [dr]


def cassi_ode_wa():
    """Solve the r(a) ODE from a₀=0.01 to a=8; return (a_ode, w_ode)."""
    sol = solve_ivp(ode_system, [np.log(A0), np.log(8.0)], [1.0 / INITIAL_RATIO],
                    method="BDF", max_step=0.01, atol=1e-9, rtol=1e-8)
    a_ode = np.exp(sol.t)
    r_ode = sol.y[0]
    H_conv = (LAM / 3) * (PHI - r_ode) * (1 + r_ode) / (r_ode + 1e-30)
    H_ode = H_EMPTY + H_conv
    dlnH = np.gradient(np.log(H_ode + 1e-30))
    dlna = np.gradient(np.log(a_ode + 1e-30))
    w_ode = -1.0 - (2.0 / 3.0) * dlnH / dlna
    return a_ode, w_ode


def cpl_w(a, w0, wa):
    """CPL parameterization: w(a) = w₀ + w_a (1 − a)."""
    return w0 + wa * (1.0 - a)


# ═════════════════════════════════════════════════════════════════════════
# H(z) reconstruction — same machinery as run_hubble_pipeline.py
# ═════════════════════════════════════════════════════════════════════════

def E2_and_DEfactor(z_grid, w_z, with_radiation=False):
    """E²(z) = Ω_m(1+z)³ + Ω_DE·DE_factor(z) [+ Ω_r(1+z)⁴].

    w_z is w(z) on the z_grid (interpolated). The dark-energy factor is
    exp(3 ∫₀^z (1+w)/(1+z') dz').
    """
    integrand = (1.0 + w_z) / (1.0 + z_grid)
    integral = cumulative_trapezoid(integrand, z_grid, initial=0.0)
    DE_factor = np.exp(3.0 * integral)
    E2 = (OMEGA_M0 * (1.0 + z_grid) ** 3
          + OMEGA_DE0 * DE_factor)
    if with_radiation:
        E2 = E2 + OMEGA_R0 * (1.0 + z_grid) ** 4
    return E2, DE_factor


def model_wz(w_kind, z_grid, a_ode=None, w_ode=None):
    """Return w(z) on z_grid for a model."""
    if w_kind == 'lcdm':
        return np.full_like(z_grid, -1.0)
    if w_kind == 'ode':
        z_ode = 1.0 / a_ode - 1.0
        sort_idx = np.argsort(z_ode)
        return np.interp(z_grid, z_ode[sort_idx], w_ode[sort_idx],
                         left=w_ode[sort_idx][0], right=w_ode[sort_idx][-1])
    w0, wa = w_kind
    a = 1.0 / (1.0 + z_grid)
    return cpl_w(a, w0, wa)


def D_C_ratio(z_star, z_grid, E2_model, E2_lcdm, n_steps=3000):
    """Comoving distance ratio I_model/I_ΛCDM to z* (radiation included)."""
    z_int = np.linspace(0.0, z_star, n_steps)
    I_model = cumulative_trapezoid(
        1.0 / np.sqrt(np.interp(z_int, z_grid, E2_model)), z_int, initial=0.0)[-1]
    I_lcdm = cumulative_trapezoid(
        1.0 / np.sqrt(np.interp(z_int, z_grid, E2_lcdm)), z_int, initial=0.0)[-1]
    return I_model / I_lcdm


# ═════════════════════════════════════════════════════════════════════════
# Models
# ═════════════════════════════════════════════════════════════════════════

Z_STAR = 1090.0
z_grid = np.linspace(0.0, 1200.0, 5000)
cmb_mask = (z_grid >= 1000.0) & (z_grid <= 1100.0)

a_ode, w_ode = cassi_ode_wa()
# CPL fit of the ODE w(a) over the DESI window (reference only)
desi_mask = (a_ode >= 0.3) & (a_ode <= 1.0)
A_cpl = np.column_stack([np.ones_like(a_ode[desi_mask]),
                         1 - a_ode[desi_mask]])
w0_ode, wa_ode = np.linalg.lstsq(A_cpl, w_ode[desi_mask], rcond=None)[0]

MODELS = [
    ("ΛCDM",                    'lcdm', None, None),
    ("Cassi baseline",          (-0.870, +0.012), None, None),
    ("Cassi coupling",          (-0.870, -0.380), None, None),
    ("Cassi ODE pipeline",      'ode', a_ode, w_ode),
]

print("=" * 88)
print("FULL H(z) SIMULTANEOUS FIT — Planck (67.4 ± 0.5) + SH0ES (73.0 ± 1.0)")
print("=" * 88)
print(f"  z_grid: {len(z_grid)} points, z ∈ [0, 1200]; CMB window z ∈ [1000, 1100]")
print(f"  ODE w(a): a ∈ [{a_ode[0]:.3f}, {a_ode[-1]:.1f}], "
      f"CPL fit over a ∈ [0.3, 1]: w₀ = {w0_ode:+.4f}, wₐ = {wa_ode:+.4f} "
      f"(bare form; doctrine values are the ξ-corrected pair −0.87, +0.012)")
print(f"  ODE w at a = 0.01 (z = 99, right-clamp for z > 99): {w_ode[0]:+.4f}")
print()

# ═════════════════════════════════════════════════════════════════════════
# Per-model computation
# ═════════════════════════════════════════════════════════════════════════

print(f"  {'Model':<22} {'w₀, wₐ':>12} {'⟨R⟩_CMB':>9} {'H₀^CMB':>8} "
      f"{'D_C ratio':>9} {'H₀*':>7} {'χ²_CMB':>7} {'χ²_SH0ES':>9} "
      f"{'χ²_tot':>7} {'sep (σ)':>8}")
print("  " + "-" * 104)

rows = []
for name, kind, a_ode_m, w_ode_m in MODELS:
    w_z = model_wz(kind, z_grid, a_ode_m, w_ode_m)
    E2, DE_factor = E2_and_DEfactor(z_grid, w_z)
    E2_lcdm, _ = E2_and_DEfactor(z_grid, np.full_like(z_grid, -1.0))
    E2_rad, _ = E2_and_DEfactor(z_grid, w_z, with_radiation=True)
    E2_lcdm_rad, _ = E2_and_DEfactor(z_grid, np.full_like(z_grid, -1.0),
                                     with_radiation=True)

    R_z = np.sqrt(E2 / E2_lcdm)
    R_cmb = float(np.mean(R_z[cmb_mask]))
    H0_cmb = H0_CMB_LCDM * R_cmb
    dc_ratio = D_C_ratio(Z_STAR, z_grid, E2_rad, E2_lcdm_rad)

    # Simultaneous fit: χ²(H₀) minimized in closed form (weighted mean)
    w_cmb = 1.0 / SIGMA_CMB ** 2
    w_sh = 1.0 / SIGMA_SH0ES ** 2
    H0_star = (w_cmb * H0_cmb + w_sh * H0_SH0ES) / (w_cmb + w_sh)
    chi2_cmb = ((H0_star - H0_cmb) / SIGMA_CMB) ** 2
    chi2_sh = ((H0_star - H0_SH0ES) / SIGMA_SH0ES) ** 2
    chi2_tot = chi2_cmb + chi2_sh
    sep_sigma = abs(H0_cmb - H0_SH0ES) / np.sqrt(SIGMA_CMB ** 2 + SIGMA_SH0ES ** 2)

    label = f"({kind[0]:+.3f}, {kind[1]:+.3f})" if isinstance(kind, tuple) else "—"
    rows.append(dict(name=name, R_cmb=R_cmb, H0_cmb=H0_cmb, dc_ratio=dc_ratio,
                     H0_star=H0_star, chi2_cmb=chi2_cmb, chi2_sh=chi2_sh,
                     chi2_tot=chi2_tot, sep_sigma=sep_sigma))
    print(f"  {name:<22} {label:>12} {R_cmb:9.5f} {H0_cmb:8.2f} "
          f"{dc_ratio:9.4f} {H0_star:7.2f} {chi2_cmb:7.2f} {chi2_sh:9.2f} "
          f"{chi2_tot:7.2f} {sep_sigma:8.2f}")

chi2_lcdm = rows[0]['chi2_tot']

# ═════════════════════════════════════════════════════════════════════════
# Verdict
# ═════════════════════════════════════════════════════════════════════════

print()
print("VERDICT")
print("-------")
print(f"  1. ΛCDM: anchors H₀^CMB = 67.4 vs H₀^SH0ES = 73.0 sit "
      f"{rows[0]['sep_sigma']:.1f}σ apart; χ² = {rows[0]['chi2_tot']:.1f} "
      f"for the best single H₀ = {rows[0]['H0_star']:.2f}. The tension is "
      f"unresolved (5.0σ is the standard Planck-vs-SH0ES statement).")
for r in rows[1:]:
    dchi2 = chi2_lcdm - r['chi2_tot']
    verdict = ("RESOLVED" if r['sep_sigma'] < 2.0
               else "PARTIAL" if r['sep_sigma'] < 4.0 else "NOT RESOLVED")
    print(f"  2. {r['name']}: H₀^CMB = {r['H0_cmb']:.2f} (⟨R⟩_CMB = {r['R_cmb']:.5f}); "
          f"anchors {r['sep_sigma']:.1f}σ apart; χ² = {r['chi2_tot']:.2f} "
          f"(Δχ² vs ΛCDM = {dchi2:+.1f}) → {verdict}.")
print("""
  The decisive comparison is the CMB-epoch expansion ratio ⟨R⟩_CMB:
    • The calibrated CPL values (baseline wₐ = +0.012 and the ratified
      coupling wₐ = −0.38) give ⟨R⟩_CMB ≈ 1.0000: dark energy is negligible
      at z ≈ 1000−1100 in both models, so the Cassi w(a) does NOT move the
      CMB anchor. Under the calibrated values the H₀ tension is not resolved
      by the w(a) mechanism (the D_C(z*) cross-check shifts the anchor by
      ≲2 km/s/Mpc, and in the wrong direction).
    • The documented ΔH₀ = −7.2 km/s/Mpc (−9.9%) comes from the ODE model,
      whose w(a) is clamped to +0.37 (radiation-like) at z > 99 — an
      extrapolation beyond the ODE's calibrated range (a ≥ 0.01) and outside
      the DESI-anchored window (a ∈ [0.3, 1]). That early-time behavior, not
      the calibrated w₀ = −0.87, drives the claimed resolution.
  Honest verdict: the full simultaneous fit does not support "evolving Ω_Λ
  reconciles H₀" with the calibrated baseline (χ² ≈ 25, same as ΛCDM). The
  framework's w(a) resolves the tension only if the ODE's radiation-like
  early-time extrapolation is physics; that requires a radiation-inclusive
  treatment of the two-fluid H(z) before the registry's "full H(z) fit"
  can be closed as a resolution.
""")
print("=" * 88)
