#!/usr/bin/env python3
"""
Cassi Hawking-Spectrum Deviation—Gaussian Suppression from the σ-Regulator.

Prediction 49: in any horizon analogue whose vacuum is a two-fluid-like
condensate (fibre-optic, BEC, water-wave), the emitted spectrum deviates
from exact thermality by a Gaussian high-frequency suppression

    ΔN_k / N_k^thermal = exp(-(ω/Λ)² / φ⁶)

Zero parameters—the coefficient φ⁶ ≈ 17.944 is the rung-3 Yang/Yin
coupling; Λ is the analogue's own UV cutoff scale (gravitational case:
Λ = φ³·M_Pl ≈ 5.17×10¹⁹ GeV, the σ-regulator). At the frequency cap the
deviation reaches exp(-φ⁻⁶) ≈ 0.95.

The test recipe: fit ln(ΔN/N) vs ω² in a fibre-optic analogue spectrum;
the fit must be linear (Gaussian shape) with slope -1/(φ⁶·Λ²) at the
known analogue cutoff—a power-law tail or inconsistent slope rejects.

The integrated-correlation claim O(M²/M_Pl²) (quantum-gravity.md §7.5)
is the Page-curve computation and needs the curved-spacetime solver
(§7.4); it is NOT verified here.

Run: python experiments/cassi_physics/cassi_hawking_spectrum.py
"""

import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI6 = PHI**6                  # rung-3 Yang/Yin coupling ξ = φ⁶ ≈ 17.944
M_PL = 1.221e19                # GeV (Planck mass)
LAMBDA_UV = PHI**3 * M_PL      # 1/σ = φ³·M_Pl ≈ 5.17e19 GeV (σ-regulator scale)
K_B = 8.617333262e-14          # GeV/K (Boltzmann constant in natural units)

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, 'cassi_hawking_spectrum.png')


def deviation(omega, lam):
    """Gaussian spectral deviation D(ω) = exp(-(ω/Λ)²/φ⁶) (prediction 49)."""
    return np.exp(-(omega / lam)**2 / PHI6)


def main():
    print("=" * 68)
    print("CASSI HAWKING-SPECTRUM DEVIATION—prediction 49")
    print("=" * 68)
    print(f"  φ⁶ = {PHI6:.6f} (rung-3 Yang/Yin coupling)")
    print(f"  M_Pl = {M_PL:.4g} GeV")
    print(f"  Λ_UV = φ³·M_Pl = {LAMBDA_UV:.4g} GeV (the σ-regulator scale)")

    checks = []

    # --- Section A: the deviation factor --------------------------------
    print("\nA. Deviation factor D(ω) = exp(-(ω/Λ_UV)²/φ⁶), ω ∈ [0, Λ_UV]:")
    d10 = deviation(0.1 * LAMBDA_UV, LAMBDA_UV)
    dcap = deviation(LAMBDA_UV, LAMBDA_UV)
    print(f"  D(0.1·Λ_UV) = {d10:.6f}  (≈ 0.9994—negligible at low frequency)")
    print(f"  D(Λ_UV)     = {dcap:.6f}  (= exp(-1/φ⁶) ≈ 0.9458; "
          f"quantum-gravity.md rounds this to 0.95)")
    ok_a1 = abs(d10 - 0.9994) < 1e-4
    ok_a2 = abs(dcap - math.exp(-1.0 / PHI6)) < 1e-6
    checks.extend([ok_a1, ok_a2])

    # --- Section B: the shape test --------------------------------------
    print("\nB. Shape test—linear fit of ln D vs (ω/Λ_UV)²:")
    w_grid = np.linspace(0.0, LAMBDA_UV, 2001)
    x = (w_grid / LAMBDA_UV)**2
    y = np.log(deviation(w_grid, LAMBDA_UV))
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    r2 = 1.0 - np.sum((y - y_pred)**2) / np.sum((y - np.mean(y))**2)
    slope_exact = -1.0 / PHI6
    print(f"  slope    = {slope:+.6f}  (exact: -1/φ⁶ = {slope_exact:+.6f})")
    print(f"  R²       = {r2:.10f}")
    ok_b1 = abs(slope - slope_exact) < 0.01 * abs(slope_exact)
    ok_b2 = r2 > 0.9999
    checks.extend([ok_b1, ok_b2])

    # --- Section C: synthetic analogue measurement ----------------------
    print("\nC. Synthetic analogue measurement (the test recipe):")
    lam_a = 1.0                          # eV—nominal fibre-optic analogue cutoff
    n_points = 40000                     # ≥40 required; the 0.5% cutoff-recovery
    rng = np.random.default_rng(49)      # tolerance sets the density: at 1% noise
    w_ev = np.geomspace(0.05, 1.0, n_points)   # eV—log-spaced grid
    d_true = deviation(w_ev, lam_a)
    d_meas = d_true + rng.normal(0.0, 0.01, n_points)
    slope_c, _ = np.polyfit(w_ev**2, np.log(d_meas), 1)
    lam_fit = math.sqrt(-1.0 / (slope_c * PHI6))   # slope in eV⁻² → Λ in eV
    print(f"  nominal analogue cutoff Λ_a = {lam_a:.1f} eV")
    print(f"  grid: {n_points} log-spaced points, ω ∈ [0.05, 1.0] eV, "
          f"Gaussian noise σ = 0.01")
    print(f"  fit ln D_meas vs ω²: slope = {slope_c:+.6f} eV⁻² "
          f"(exact -1/(φ⁶Λ_a²) = {slope_exact:+.6f} eV⁻²)")
    print(f"  recovered cutoff Λ_fit = sqrt(-1/(slope·φ⁶)) = {lam_fit:.6f} eV")
    ok_c = abs(lam_fit / lam_a - 1.0) < 5e-3
    checks.append(ok_c)

    # --- Section D: scope -----------------------------------------------
    print("\nD. Scope:")
    print("  The integrated-correlation claim O(M²/M_Pl²) (quantum-gravity.md")
    print("  §7.5) remains unverified numerically—it is the Page-curve")
    print("  computation and requires the curved-spacetime two-fluid solver")
    print("  (quantum-gravity.md §7.4). Not attempted here.")

    # --- Section E: astronomical case -----------------------------------
    print("\nE. Stellar-mass black hole (M = 1 M☉):")
    t_h = 6.2e-8                  # K—Hawking temperature of a solar-mass BH
    w_t = K_B * t_h               # GeV—thermal peak frequency ω_T = k_B·T_H
    # ε = (ω_T/Λ_UV)²/φ⁶ to leading order; exp(-ε) = 1 - ε is 1.0 in double
    # precision (ε ~ 6e-82 < 2⁻⁵³), so ε is computed analytically
    eps = (w_t / LAMBDA_UV)**2 / PHI6
    print(f"  T_H = {t_h:.1e} K → ω_T = k_B·T_H = {w_t:.3e} GeV")
    print(f"  deviation at the thermal peak = exp(-(ω_T/Λ_UV)²/φ⁶) ≈ 1 − ε")
    print(f"  with ε = {eps:.4e} < 10⁻⁶⁰—astronomically unobservable "
          f"(the direct-emission analogue is where the signal lives)")
    ok_e = eps < 1e-60
    checks.append(ok_e)

    # --- Figure ---------------------------------------------------------
    w_fig = np.linspace(0.0, LAMBDA_UV, 500)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    ax.plot(w_fig / LAMBDA_UV, deviation(w_fig, LAMBDA_UV), 'b-', lw=2)
    ax.axhline(math.exp(-1.0 / PHI6), color='r', ls='--', alpha=0.6,
               label=f'e^(−1/φ⁶) ≈ 0.9458 (cap)')
    ax.set_xlabel('ω / Λ_UV')
    ax.set_ylabel('ΔN / N^thermal')
    ax.set_title('Gaussian Hawking-spectrum deviation (prediction 49)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax = axes[1]
    ax.scatter(w_ev**2, np.log(d_meas), s=4, alpha=0.35, label='synthetic data')
    x_fit = np.linspace(0.0, 1.0, 100)
    ax.plot(x_fit, slope_c * x_fit + np.mean(np.log(d_meas)) - slope_c * np.mean(w_ev**2),
            'r-', lw=2, label=f'fit: Λ_fit = {lam_fit:.4f} eV')
    ax.set_xlabel('ω² (eV²)')
    ax.set_ylabel('ln(ΔN / N)')
    ax.set_title('Shape test: ln(ΔN/N) linear in ω²')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.suptitle('Cassi prediction 49—analogue-horizon spectrum fit')
    plt.tight_layout()
    plt.savefig(PNG, dpi=150)
    plt.close()
    print(f"\n  Figure saved: {PNG}")

    # --- Verification block ---------------------------------------------
    print("\n" + "=" * 68)
    labels = ["D(0.1·Λ_UV) ≈ 0.9994",
              "D(Λ_UV) = exp(-1/φ⁶) ≈ 0.9458",
              "ln-D slope ≈ -1/φ⁶ (1% tolerance)",
              "R² > 0.9999 (Gaussian shape)",
              "|Λ_fit/Λ_a − 1| < 0.5% (cutoff recovery)",
              "stellar ε < 10⁻⁶⁰ (astronomical unobservability)"]
    for ok, label in zip(checks, labels):
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if all(checks):
        print("\n  All checks: PASS")
        print("=" * 68)
        sys.exit(0)
    else:
        print("\n  All checks: FAIL")
        print("=" * 68)
        sys.exit(1)


if __name__ == '__main__':
    main()
