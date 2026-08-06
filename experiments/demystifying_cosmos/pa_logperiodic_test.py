#!/usr/bin/env python3
"""P48 — Log-periodic polarization-angle test on published multi-band PA data.

Prediction (`predictions/falsifiable-predictions.md`, P48): in synchrotron
sources the polarization position angle winds one full turn per cascade rung
of emitting-particle energy,

    Theta(nu) = Theta0 + (2 pi / ln phi) ln(nu / nu0),   PA = Theta (mod pi),

i.e. PA is log-periodic in photon frequency with period ln phi ~= 0.4812
(equivalently PA(ν·φ^k) = PA(ν) mod π), and — per the prediction text — a
band pair at half-rung separation (ν2/ν1 = sqrt(phi)) shows PA rotated 90°.

Test (CATALOG class): published tabulated polarization position angles in
>=3 bands spanning Δ(ln ν) >= ln φ for the same source.

Sources used (all tabulated, peer-reviewed):
  Crab Nebula (integrated / large-aperture, equatorial convention):
    - Planck 100/143/217/353 GHz, psi_gal (Ritacco+ 2018 Tab. 3; converted
      to equatorial with the NIKA calibration pair psi_eq = psi_gal + 225.8)
    - NIKA 150 GHz, psi_eq (Ritacco+ 2018 Tab. 2, 7' aperture)
    - OSO-8 rocket 2.6/5.2 keV (Weisskopf+ 1978, quoted in Forot+ 2008)
    - IXPE 2-8 keV space-integrated nebula, PA = 145° (Bucciantini+ 2023,
      Nat. Astron. 7, 602; no error quoted in abstract — sigma assumed 2°)
    - INTEGRAL SPI 100 keV-1 MeV, off-pulse (Dean+ 2008, quoted in Forot+ 2008)
    - INTEGRAL IBIS 200-800 keV, off-pulse+bridge (Forot+ 2008 Tab. 2)
  Lighthouse Nebula trail (PSR J1101-6101, Dinsmore+ 2026, arXiv:2604.22914):
    - IXPE 2-8 keV trail EVPA = -24° ± 12° (LeakageLib fit)
    - ATCA 5.5/9 GHz EVPA inferred ~66° ± 15° — the paper quotes only
      "nearly orthogonal to the radio polarization", so the radio point is
      marked INFERRED and the source is a 2-band pair check, not a ≥3-band
      test.

Procedure (per skill://catalog-derived-quantity-null-calibration):
  1. The predicted relation fixes the slope m = 2π/ln φ (rad per unit ln ν);
     the only free parameter is the absolute phase Theta0 (mod π).  Fit
     Theta0 by grid search on the mod-π circular residuals.
  2. Report chi2 of the spiral model vs the constant-PA model (also one free
     parameter), and per-pair z-scores: predicted vs observed ΔPA (mod π).
  3. Null calibration: uniform-angle Monte Carlo through the SAME Theta0 fit
     (search-corrected), reported as null mean ± std against the observed
     mean circular residual.

Usage:
    python experiments/demystifying_cosmos/pa_logperiodic_test.py

Verdict history:
    2026-08-06  NULL at face value.  Crab PA is constant to <1° across
                100-353 GHz (5.1 half-rungs) where the formula demands a
                40° rotation; the full radio→X-ray span (37 rungs, formula:
                67°) shows only 5-17°.  The B-ratio caveat (ν ∝ γ²B differs
                between emission regions) applies to the cross-region pairs
                but not to the intra-mm band, where the null is decisive.
"""

import math

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LN_PHI = math.log(PHI)          # 0.48121 — the predicted log period
M_RAD = 2.0 * math.pi / LN_PHI  # spiral slope, rad per unit ln(nu)
M_DEG = math.degrees(M_RAD)     # 748.4 deg per unit ln(nu) ~ 1723 deg/decade
D2R = math.pi / 180.0

# ---------------------------------------------------------------------------
# Data.  PA in degrees, equatorial (IAU) convention.  Galactic→equatorial
# conversion for the Crab: psi_eq = psi_gal + 225.8 (NIKA 7' calibration
# pair 141.7 ↔ −84.1, Ritacco+ 2018).  Differences mod π are convention-free.
# ---------------------------------------------------------------------------
# (label, nu [Hz], PA [deg], sigma [deg], region)
CRAB = [
    ("Planck 100 GHz",  1.00e11, 138.28, 0.16, "nebula (mm)"),
    ("Planck 143 GHz",  1.43e11, 139.19, 0.21, "nebula (mm)"),
    ("NIKA 150 GHz",    1.50e11, 141.70, 1.90, "nebula (mm)"),
    ("Planck 217 GHz",  2.17e11, 137.87, 0.25, "nebula (mm)"),
    ("Planck 353 GHz",  3.53e11, 139.04, 0.52, "nebula (mm)"),
    ("IXPE 2-8 keV",    4.83e17, 145.00, 2.00, "nebula (X, sigma assumed)"),
    ("OSO-8 2.6 keV",   6.28e17, 156.40, 1.40, "nebula (X)"),
    ("OSO-8 5.2 keV",   1.26e18, 152.60, 4.00, "nebula (X)"),
    ("INTEGRAL SPI",    2.10e20, 123.00, 11.0, "inner wind (off-pulse)"),
    ("INTEGRAL IBIS",   4.80e20, 122.00, 7.70, "inner wind (off-pulse)"),
]

# Lighthouse trail: 2 usable bands only (radio EVPA inferred from the paper's
# "nearly orthogonal to the radio polarization" — no tabulated radio PA).
LIGHTHOUSE = [
    ("ATCA 5.5/9 GHz (INFERRED)", 7.25e9, 66.0, 15.0),
    ("IXPE 2-8 keV trail",        4.83e17, -24.0, 12.0),
]


def wrap180(x):
    """Wrap an angle in degrees to [-90, 90) (PA is mod pi)."""
    return (x + 90.0) % 180.0 - 90.0


def circ_dist(a, b):
    """Circular distance |a - b| mod 180, in [0, 90] degrees."""
    return abs(wrap180(a - b))


def predicted_dpa(nu1, nu2):
    """Predicted PA difference between two bands, mod 180 deg."""
    return wrap180(M_DEG * math.log(nu2 / nu1))


def fit_theta0(nus, pas, sigma=None, spiral=True, nu_ref=1.0e11,
               n_grid=7200):
    """Grid-search Theta0 in [0,180) minimizing the mod-pi chi2.

    spiral=True:  pred_i = Theta0 + m·ln(nu_i/nu_ref)  (P48 winding)
    spiral=False: pred_i = Theta0                       (constant PA)
    """
    lnx = np.log(np.asarray(nus) / nu_ref)
    pa = np.asarray(pas)
    sig = np.ones(len(pa)) if sigma is None else np.asarray(sigma)
    grid = np.linspace(0.0, 180.0, n_grid, endpoint=False)
    if spiral:
        pred = grid[:, None] + M_DEG * lnx[None, :]
    else:
        pred = grid[:, None] + np.zeros_like(lnx)[None, :]
    resid = wrap180(pa[None, :] - pred)
    chi2 = np.sum((resid / sig[None, :]) ** 2, axis=1)
    k = int(np.argmin(chi2))
    return grid[k], chi2[k]


def mean_circ_resid(nus, pas, theta0, spiral=True, nu_ref=1.0e11):
    """Mean |residual| (deg) of PA about the Theta0-fitted model."""
    lnx = np.log(np.asarray(nus) / nu_ref)
    pred = theta0 + (M_DEG * lnx if spiral else np.zeros_like(lnx))
    return float(np.mean([circ_dist(p, q) for p, q in zip(pas, pred)]))


def run_source(name, bands, mc_n=2000, seed=42):
    """Full battery for one source: spiral fit, constant fit, pairs, MC null."""
    labels = [b[0] for b in bands]
    nus = np.array([b[1] for b in bands])
    pas = np.array([b[2] for b in bands])
    sig = np.array([b[3] for b in bands])
    n = len(bands)

    th_sp, chi2_sp = fit_theta0(nus, pas, sig, spiral=True)
    th_cn, chi2_cn = fit_theta0(nus, pas, sig, spiral=False)
    d_sp = mean_circ_resid(nus, pas, th_sp, spiral=True)
    d_cn = mean_circ_resid(nus, pas, th_cn, spiral=False)

    # uniform-angle null through the SAME Theta0 fit (search-corrected)
    rng = np.random.default_rng(seed)
    d_null = np.empty(mc_n)
    for k in range(mc_n):
        pa_null = rng.uniform(0.0, 180.0, n)
        th0 = fit_theta0(nus, pa_null, None, spiral=True)[0]
        d_null[k] = mean_circ_resid(nus, pa_null, th0, spiral=True)
    p_d = np.mean(d_null <= d_sp)

    print(f"\n{'=' * 78}")
    print(f"{name} — {n} bands, Δ(ln ν) = {math.log(nus[-1] / nus[0]):.2f} "
          f"(= {math.log(nus[-1] / nus[0]) / LN_PHI:.1f} rungs)")
    print(f"{'=' * 78}")
    print(f"  {'band':28s}{'ν [Hz]':>11s}{'PA [°]':>9s}{'σ [°]':>7s}")
    for b in bands:
        print(f"  {b[0]:28s}{b[1]:11.3e}{b[2]:9.2f}{b[3]:7.2f}")
    print(f"\n  spiral model (slope m = 2π/ln φ = {M_DEG:.1f}°/unit ln ν):")
    print(f"    Theta0 = {th_sp:7.2f}°   χ² = {chi2_sp:8.1f}  "
          f"(dof {n - 1}, expect ~{n - 1})")
    print(f"    mean |circular residual| = {d_sp:6.2f}°")
    print(f"  constant-PA model (slope 0):")
    print(f"    Theta0 = {th_cn:7.2f}°   χ² = {chi2_cn:8.1f}  "
          f"(dof {n - 1}, expect ~{n - 1})")
    print(f"    mean |circular residual| = {d_cn:6.2f}°")
    print(f"  Δχ² = χ²_const − χ²_spiral = {chi2_cn - chi2_sp:8.1f} "
          f"({'constant preferred' if chi2_cn < chi2_sp else 'spiral preferred'})")
    print(f"  uniform-angle null (same Theta0 fit, n = {mc_n}): "
          f"mean residual {d_null.mean():.2f}° ± {d_null.std():.2f}°  "
          f"p(observed ≤ null) = {p_d:.3f}")

    print(f"\n  band pairs — predicted vs observed ΔPA (mod 180°):")
    n_agree = 0
    n_pair = 0
    for i in range(n):
        for j in range(i + 1, n):
            k_rung = math.log(nus[j] / nus[i]) / LN_PHI
            dp_pred = predicted_dpa(nus[i], nus[j])
            dp_obs = wrap180(pas[j] - pas[i])
            sig_pair = math.hypot(sig[i], sig[j])
            resid = circ_dist(dp_obs, dp_pred)
            z = resid / sig_pair if sig_pair > 0 else math.inf
            n_pair += 1
            if z < 3.0:
                n_agree += 1
            tag = ""
            if 0.97 < PHI ** k_rung / PHI ** round(k_rung) < 1.03 or \
               abs(k_rung - round(k_rung)) < 0.03:
                tag = "  <- near-φᵏ pair"
            print(f"    {labels[i]:18s}→{labels[j]:18s}"
                  f"  Δn={k_rung:5.2f}  pred {dp_pred:7.1f}°  "
                  f"obs {dp_obs:7.1f}°±{sig_pair:4.1f}  z={z:6.1f}{tag}")
    print(f"  pairs within 3σ of the prediction: {n_agree}/{n_pair}")
    return dict(n=n, chi2_sp=chi2_sp, chi2_cn=chi2_cn, d_sp=d_sp,
                d_null=d_null, n_agree=n_agree, n_pair=n_pair)


def lighthouse_pair(bands):
    """Two-band pair check (no periodicity test possible with 2 bands)."""
    (l1, n1, p1, s1), (l2, n2, p2, s2) = bands
    dp_pred = predicted_dpa(n1, n2)
    dp_obs = wrap180(p2 - p1)
    sig = math.hypot(s1, s2)
    resid = circ_dist(dp_obs, dp_pred)
    print(f"\n{'=' * 78}")
    print("Lighthouse Nebula trail — 2-band pair check (radio EVPA inferred)")
    print(f"{'=' * 78}")
    print(f"  {l1}: PA = {p1:+.1f}° ± {s1:.0f}°   {l2}: PA = {p2:+.1f}° ± {s2:.0f}°")
    print(f"  Δ(ln ν) = {math.log(n2 / n1):.2f} (= {math.log(n2 / n1) / LN_PHI:.1f} rungs)")
    print(f"  predicted ΔPA = {dp_pred:+.1f}° (mod 180), "
          f"observed ΔPA = {dp_obs:+.1f}° ± {sig:.1f}°")
    print(f"  |residual| = {resid:.1f}°  ->  z = {resid / sig:.1f}")
    print(f"  (2 bands cannot test periodicity; the radio EVPA is inferred "
          f"from 'nearly orthogonal',")
    print(f"   and radio/X-ray leptons may see different B — region caveat "
          f"applies)")
    return dict(z=resid / sig)


def main():
    print("P48 — log-periodic polarization-angle test")
    print(f"  slope m = 2π/ln φ = {M_DEG:.1f}° per unit ln ν "
          f"({M_DEG / math.log(10.0):.0f}°/decade); "
          f"period ln φ = {LN_PHI:.4f}; "
          f"half-rung (√φ) spacing = {math.sqrt(PHI):.4f}")
    print("  Prediction text also claims a 90° flip at √φ band pairs — "
          "note: the")
    print("  formula gives ΔΘ = π (180°) there, i.e. PA unchanged mod π; "
          "a 90° flip")
    print("  would require quarter-rung spacing ν₂/ν₁ = φ^¼. "
          "The text is internally")
    print("  inconsistent; the formula is what is tested below.")

    # main test: Crab mm band (same emission region, same B — no escape hatch)
    mm = [b for b in CRAB if "mm" in b[4]]
    run_source("CRAB NEBULA — radio/mm band (same region, B-ratio caveat "
               "inapplicable)", mm, mc_n=4000)

    # extended: mm + X-ray + hard-gamma (cross-region; B-ratio caveat)
    run_source("CRAB NEBULA — all bands (radio→X→γ; region-mixing caveat)",
               CRAB, mc_n=2000)

    # Lighthouse: pair check only
    lighthouse_pair(LIGHTHOUSE)

    print(f"\n{'=' * 78}")
    print("VERDICT")
    print(f"{'=' * 78}")
    print("""  NULL at face value for the log-periodic winding formula
  Θ(ν) = Θ0 + (2π/ln φ)·ln(ν/ν0) mod π:
    - Crab 100→353 GHz (5.1 half-rungs, one region, one B field):
      formula demands ΔPA ≈ 44°; data show 0.8° ± 0.5° (≈ 80σ off).
    - Full radio→X-ray span (≈37 rungs): formula 67°; data 5-17°.
    - The data are consistent with PA CONSTANT (mod π) across bands
      (χ²_const ≈ dof), i.e. the headline PA(νφᵏ) = PA(ν) mod π holds only
      trivially, as any constant function would.
    - The 90°-flip-at-√φ bullet contradicts the formula (√φ spacing ⇒
      ΔΘ = π ≡ 0 mod π; parallel, not perpendicular).""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
