#!/usr/bin/env python3
"""φ-periodic (log-periodic) search on GWTC-4.0 primary black-hole masses.

The hypothesis (analyses/gwtc4-mass-ladder.md §3): if black-hole formation
freezes out at activated cascade rungs, the intrinsic primary-mass
distribution carries a log-periodic comb at period ln φ — equivalently,
period 1 in rung space n = log_φ(m1/M_Pl).

Models (m1 ∈ [2, 200] M_sun):
  M0   smooth baseline: power law + two Gaussians (FullPop-4.0-style shape)
  M1   M0 × (1 + A cos(2π n))              — comb at the PREDICTED period, ψ=0
  M1ψ  M0 × (1 + A cos(2π n + ψ))          — predicted period, free phase
  M2   M0 × (1 + A cos(2π n/T + ψ))        — free period (look-elsewhere control)

Estimator: for each event, L_i(Λ) = mean_s p(m1_s | Λ) over the stored
posterior samples. This is unbiased for ∫ p(d_i|m1) p(m1|Λ) dm1 for any
positive reference prior (the PE prior cancels analytically), so no prior
reconstruction is needed. Selection effects enter only through smooth
multiplicative factors; the comb is (nearly) orthogonal to any smooth
envelope — quantified numerically with VT(m) ∝ m^a, a ∈ {0,1,2}, and folded
into the reported Δln L as a systematic bracket.

Significance: parametric bootstrap. N_BS mock catalogs are drawn by
importance-resampling each real posterior under the fitted M0 (preserving
the real measurement widths and the implicit selection), refit, and the null
distributions of Δln L(M1)−Δln L(M0) and of the rung-fraction excess
statistic S(T) are compared with the observed values.

Usage:
  python experiments/gwtc4_mass_ladder/phi_mass_search.py [--quick]

Data: experiments/gwtc4_mass_ladder/data/samples_m1.npz (from extract_samples.py)
      — posterior samples of mass_1_source, C00:Mixed (equal-weight waveform
      mixture), GWTC-4.0 PE data release (zenodo record 17602505).

Epistemic tiers (see analyses/gwtc4-mass-ladder.md):
  rung relation N_BH = log_φ(M/M_Pl)      Derived
  integer-rung comb hypothesis            Speculative — this script tests it
  GR-exact ringdown                       Derived (untested here)
"""

import os
import math
import sys

import numpy as np
from scipy import integrate, optimize

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LN_PHI = math.log(PHI)                    # 0.48121 — THE predicted log period
M_PL_KG = 2.176e-8
M_SUN_KG = 1.989e30
M_SUN_PER_M_PL = M_SUN_KG / M_PL_KG       # 9.1406e37

M_LO, M_HI = 2.0, 200.0                   # analysis range (M_sun)
N_THIN = 1500                             # samples per event (main fits)
N_BS = 60                                 # bootstrap mocks
T_SCAN = np.linspace(0.3, 2.0, 171)       # period scan (rungs)
FRAC_W = 0.15                             # rung-fraction window for S(T)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "samples_m1.npz")

# comb modes: 0 none, 1 fixed T & ψ (A), 2 fixed T free ψ (A,ψ), 3 free (A,ψ,T)
MODE_K = {0: 10, 1: 11, 2: 12, 3: 13}
MODE_NAME = {0: "M0 smooth", 1: "M1 comb @ lnφ (ψ=0)",
             2: "M1ψ comb @ lnφ (ψ free)", 3: "M2 comb (free period)"}

# smooth parameter order: alpha, f10, mu10, s10, f20, mu20, s20, f35, mu35, s35
N_SMOOTH = 10


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────
def rung(m):
    """N_BH = log_phi(M/M_Pl) — coherence-capacity rungs (quantum-gravity §7.4)."""
    return np.log(m * M_SUN_PER_M_PL) / LN_PHI


_LNM = np.linspace(math.log(M_LO), math.log(M_HI), 4000)
_MG = np.exp(_LNM)


def _smooth_unnorm(m, alpha, f10, mu10, s10, f20, mu20, s20, f35, mu35, s35):
    """m^alpha · (1 + bumps); bumps are LINEAR-mass Gaussians (LVK FullPop
    convention: sigma ~2-4 M_sun at mu ~10, ~35; the mu20 bump absorbs the
    possible ~20 M_sun feature) normalized so f is the peak excess."""
    g10 = np.exp(-0.5 * ((m - mu10) / s10) ** 2)
    g20 = np.exp(-0.5 * ((m - mu20) / s20) ** 2)
    g35 = np.exp(-0.5 * ((m - mu35) / s35) ** 2)
    return m ** alpha * (1.0 + f10 * g10 + f20 * g20 + f35 * g35)


def _smooth_norm(alpha, f10, mu10, s10, f20, mu20, s20, f35, mu35, s35):
    # log-grid Jacobian: ∫f(m)dm = ∫f(e^x)·e^x dx
    y = _smooth_unnorm(_MG, alpha, f10, mu10, s10, f20, mu20, s20,
                       f35, mu35, s35) * _MG
    return integrate.simpson(y, x=_LNM)


def p_model(m, theta, mode, T_fixed=1.0, psi_fixed=0.0):
    """Normalized population density on [M_LO, M_HI].

    theta = [alpha, f10, mu10, s10, f20, mu20, s20, f35, mu35, s35,
             (A), (psi), (T)] per mode.  The comb product is renormalized
    (Z = ∫ p0·C dm), so p(m|Λ) is a proper probability density in every
    mode."""
    alpha, f10, mu10, s10, f20, mu20, s20, f35, mu35, s35 = theta[:N_SMOOTH]
    norm = _smooth_norm(alpha, f10, mu10, s10, f20, mu20, s20, f35, mu35, s35)
    p = _smooth_unnorm(m, alpha, f10, mu10, s10, f20, mu20, s20,
                       f35, mu35, s35) / norm
    if mode >= 1:
        A = theta[N_SMOOTH]
        psi = theta[N_SMOOTH + 1] if mode >= 2 else psi_fixed
        T = theta[N_SMOOTH + 2] if mode >= 3 else T_fixed
        C = 1.0 + A * np.cos(2.0 * np.pi * rung(m) / T + psi)
        p = p * C
        # renormalize the comb product: Z = ∫ p0·C dm over the analysis range
        Cg = 1.0 + A * np.cos(2.0 * np.pi * rung(_MG) / T + psi)
        Z = integrate.simpson(
            _smooth_unnorm(_MG, alpha, f10, mu10, s10, f20, mu20, s20,
                           f35, mu35, s35) / norm * Cg * _MG, x=_LNM)
        p = p / Z
    return np.maximum(p, 1e-300)


B_SMOOTH = [(-6.0, 4.0), (0.0, 3.0), (7.0, 15.0), (0.5, 6.0),
            (0.0, 3.0), (14.0, 26.0), (0.5, 6.0),
            (0.0, 3.0), (28.0, 45.0), (1.0, 10.0)]
B_A = (-0.98, 0.98)
B_PSI = (0.0, 2.0 * math.pi)
B_T = (0.3, 2.0)
BOUNDS = {0: B_SMOOTH, 1: B_SMOOTH + [B_A],
          2: B_SMOOTH + [B_A, B_PSI], 3: B_SMOOTH + [B_A, B_PSI, B_T]}


# ─────────────────────────────────────────────────────────────────────────────
# Likelihood + fits
# ─────────────────────────────────────────────────────────────────────────────
def prepare_samples(samples):
    """Concatenate per-event samples and record event boundaries for
    vectorized per-event means via np.add.reduceat."""
    starts = np.cumsum([0] + [len(m) for m in samples])
    m_all = np.concatenate(samples)
    counts = np.diff(starts)
    return m_all, starts[:-1], counts


def loglike(theta, samples, mode, T_fixed=1.0, psi_fixed=0.0,
            prepared=None):
    """ln L = Σ_i ln mean_s p(m1_is | θ).  Unbiased importance estimator.

    Vectorized: the model is evaluated on the concatenated sample array and
    per-event means computed with reduceat."""
    if prepared is None:
        m_all, starts, counts = prepare_samples(samples)
    else:
        m_all, starts, counts = prepared
    p = p_model(m_all, theta, mode, T_fixed, psi_fixed)
    sums = np.add.reduceat(p, starts)
    return float(np.sum(np.log(sums / counts)))


def fit_model(samples, mode, T_fixed=1.0, psi_fixed=0.0, n_start=10,
              x0=None, seed=11, maxiter=400, prepared=None):
    """Multi-start L-BFGS-B fit; returns (theta_best, lnL_best, n_eval)."""
    rng = np.random.default_rng(seed)
    bounds = BOUNDS[mode]
    best, best_lnl = None, -np.inf
    n_eval = 0
    for i in range(n_start):
        if x0 is not None and i == 0:
            x0i = np.array(x0, dtype=float)
            if len(x0i) < len(bounds):
                x0i = np.append(x0i, np.zeros(len(bounds) - len(x0i)))
        else:
            x0i = np.array([b[0] + rng.random() * (b[1] - b[0]) for b in bounds])
        res = optimize.minimize(
            lambda t: -loglike(t, samples, mode, T_fixed, psi_fixed, prepared),
            x0i, method="L-BFGS-B", bounds=bounds,
            options={"maxiter": maxiter, "ftol": 1e-11, "gtol": 1e-8})
        n_eval += res.nfev
        if -res.fun > best_lnl:
            best_lnl = -res.fun
            best = res.x
    return best, best_lnl, n_eval


# ─────────────────────────────────────────────────────────────────────────────
# Rung-fraction statistic
# ─────────────────────────────────────────────────────────────────────────────
def frac_stat(samples, T=1.0, w=FRAC_W):
    """Event-weighted excess of |n/T mod 1| < w over the phase-averaged floor.

    S = (1/Nev) Σ_i [ f_i(w) − w ]  with f_i = Σ_s I(|frac| < w)/N_i.
    Under a smooth population S ≈ 0; a comb at period T gives S > 0."""
    total = 0.0
    for m1 in samples:
        n = rung(m1) / T
        frac = n - np.floor(n + 0.5)          # ∈ [−0.5, 0.5)
        total += np.mean(np.abs(frac) < w)
    return total / len(samples) - w


def period_scan(samples, ts=None):
    """S(T) over the scan grid; returns (T_grid, S, T_best, S_best)."""
    ts = T_SCAN if ts is None else ts
    S = np.array([frac_stat(samples, T=t) for t in ts])
    k = int(np.argmax(S))
    return ts, S, ts[k], S[k]


# ─────────────────────────────────────────────────────────────────────────────
# Selection-orthogonality check
# ─────────────────────────────────────────────────────────────────────────────
def selection_correction(theta_M1, a=1.5):
    """ε = ∫VT·p0·C / ∫VT·p0 − 1 for VT(m) = m^a on the analysis range."""
    m = _MG
    p0 = _smooth_unnorm(m, *theta_M1[:N_SMOOTH])
    C = 1.0 + theta_M1[N_SMOOTH] * np.cos(2.0 * np.pi * rung(m))
    vt = m ** a
    num = integrate.simpson(vt * p0 * C * m, x=_LNM)
    den = integrate.simpson(vt * p0 * m, x=_LNM)
    return num / den - 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────
def draw_mock(samples, theta_M0, rng, vt_a=1.5, n_draw=500):
    """Fully synthetic null catalog under M0.

    True masses are drawn from p_M0(m)·VT(m) with VT = m^vt_a (smooth
    selection); each mock event's posterior shape is a randomly transplanted
    real posterior, shifted in ln m to the drawn true mass.  This preserves
    the real measurement widths while making the mass positions an
    independent M0 draw — a proper null for the comb statistics."""
    n_ev = len(samples)
    p0 = _smooth_unnorm(_MG, *theta_M0[:N_SMOOTH])
    p0 /= integrate.simpson(p0 * _MG, x=_LNM)
    pdf = p0 * _MG ** vt_a * _MG          # per-ln-m density incl. dm Jacobian
    pdf /= integrate.simpson(pdf, x=_LNM)
    dx = _LNM[1] - _LNM[0]
    cdf = np.concatenate([[0.0], np.cumsum(pdf) * dx])
    cdf /= cdf[-1]
    u = rng.random(n_ev)
    idx = np.clip(np.searchsorted(cdf, u) - 1, 0, len(_LNM) - 1)
    m_true = np.exp(_LNM[idx] + (rng.random(n_ev) - 0.5) * dx)
    mock = []
    for i in range(n_ev):
        j = int(rng.integers(n_ev))
        base = samples[j]
        shift = math.log(m_true[i]) - float(np.mean(np.log(base)))
        mock.append(base * math.exp(shift))
    return mock


def bootstrap_null(samples, theta_M0, n_mocks=N_BS, seed=7):
    """Null distributions of ΔlnL(M1−M0), S(1), S(T) curves under M0.

    Mocks are fully synthetic (draw_mock): true masses from p_M0·VT with
    transplanted real posterior shapes.  The selection-normalization
    correction −N·ln(1+ε) is applied to ΔlnL the same way as for the data."""
    rng = np.random.default_rng(seed)
    n_ev = len(samples)
    dlnl_null, dlnlc_null, s1_null, sbest_null, tbest_null = [], [], [], [], []
    dlnl2_null = []
    s_curves = []
    for k in range(n_mocks):
        mock = draw_mock(samples, theta_M0, rng)
        prep = prepare_samples(mock)
        t0, lnl0, _ = fit_model(mock, 0, n_start=1, x0=theta_M0,
                                seed=k, maxiter=150, prepared=prep)
        t1, lnl1, _ = fit_model(mock, 1, n_start=1,
                                x0=np.append(t0, 0.0), seed=k + 100,
                                maxiter=100, prepared=prep)
        # free-period comb (single start at the discovered T ~ 1.4)
        x2 = np.append(np.append(t0, 0.0), [2.0, 1.4])
        t2m, lnl2m, _ = fit_model(mock, 3, n_start=1, x0=x2,
                                  seed=k + 200, maxiter=80, prepared=prep)
        d = lnl1 - lnl0
        dlnl_null.append(d)
        dlnl2_null.append(lnl2m - lnl0)
        eps = selection_correction(t1, a=1.5)
        dlnlc_null.append(d - n_ev * math.log1p(eps))
        s1_null.append(frac_stat(mock, T=1.0))
        _, S, tbest, sbest = period_scan(mock)
        s_curves.append(S)
        sbest_null.append(sbest)
        tbest_null.append(tbest)
        if (k + 1) % 25 == 0:
            print(f"    bootstrap {k+1}/{n_mocks}")
    return (np.array(dlnl_null), np.array(dlnlc_null), np.array(dlnl2_null),
            np.array(s1_null), np.array(sbest_null), np.array(tbest_null),
            np.array(s_curves))


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────
def bic(lnl, k, n_ev):
    return -2.0 * lnl + k * math.log(n_ev)


def main():
    quick = "--quick" in sys.argv
    global N_THIN, N_BS
    n_bs_env = os.environ.get("NBS", "")
    if quick:
        N_THIN = 800
        N_BS = 20
    if n_bs_env.isdigit():
        N_BS = int(n_bs_env)
    n_bs = N_BS
    if not os.path.exists(DATA):
        print(f"missing {DATA} — run extract_samples.py first")
        sys.exit(1)
    z = np.load(DATA, allow_pickle=True)
    events = z["events"]
    samples_raw = list(z["m1"])
    n_all = len(events)
    keep = [i for i, m in enumerate(samples_raw) if np.median(m) < M_HI
            and np.percentile(m, 95) > M_LO * 0.5]
    samples_full = [samples_raw[i] for i in keep]
    rng = np.random.default_rng(3)
    samples = [rng.choice(m, size=min(N_THIN, len(m)), replace=False)
               for m in samples_full]
    prepared = prepare_samples(samples)
    print(f"events kept: {len(samples)}/{n_all}")
    print(f"  excluded: {[str(events[i]) for i in range(n_all) if i not in keep]}")
    print()

    print("fitting M0 (smooth baseline) ...")
    theta0, lnl0, ne0 = fit_model(samples, 0, prepared=prepared)
    print(f"  ln L = {lnl0:.2f}  ({ne0} evals)")

    print("fitting M1 (comb at ln φ, ψ=0) ...")
    t1, lnl1, ne1 = fit_model(samples, 1, x0=np.append(theta0, 0.0),
                              prepared=prepared)
    print(f"  A = {t1[N_SMOOTH]:+.3f}, ln L = {lnl1:.2f}  ({ne1} evals)")

    print("fitting M1ψ (comb at ln φ, ψ free) ...")
    t2, lnl2, ne2 = fit_model(samples, 2, x0=np.append(theta0, 0.0),
                              n_start=6, prepared=prepared)
    print(f"  A = {t2[N_SMOOTH]:+.3f}, ψ = {t2[N_SMOOTH + 1]:.3f}, "
          f"ln L = {lnl2:.2f}  ({ne2} evals)")

    print("fitting M2 (free period) ...")
    best_m2 = (None, -np.inf)
    for T0, psi0 in ((0.5, 0.0), (0.8, 1.0), (1.0, 0.0), (1.4, 2.0), (1.8, 4.0)):
        x0 = np.append(np.append(theta0, 0.0), [psi0, T0])
        t3, lnl3, _ = fit_model(samples, 3, x0=x0, n_start=2, prepared=prepared)
        if lnl3 > best_m2[1]:
            best_m2 = (t3, lnl3)
    t3, lnl3 = best_m2
    print(f"  A = {t3[N_SMOOTH]:+.3f}, ψ = {t3[N_SMOOTH + 1]:.3f}, "
          f"T = {t3[N_SMOOTH + 2]:.3f} rungs, ln L = {lnl3:.2f}")

    ts, S, T_best_scan, S_best_scan = period_scan(samples)
    print(f"  period-scan (frac statistic): T* = {T_best_scan:.3f} rungs, "
          f"S* = {S_best_scan:+.4f}")
    print()

    print(f"bootstrap null ({n_bs} mocks under M0) ...")
    nulls = bootstrap_null(samples, theta0, n_mocks=n_bs)
    dlnl_null, dlnlc_null, dlnl2_null, s1_null, sbest_null, tbest_null = nulls[:6]
    s_curves = nulls[6]

    # ---- report
    n_ev = len(samples)
    print()
    print("=" * 76)
    print("GWTC-4.0 φ-PERIODIC MASS SEARCH — RESULTS")
    print("=" * 76)
    print(f"events: {n_ev}   samples/event (thin): {N_THIN}   "
          f"analysis range: [{M_LO}, {M_HI}] M_sun")
    print(f"M0 baseline: alpha={theta0[0]:.3f}  bump10=({theta0[2]:.1f}, "
          f"σ={theta0[3]:.2f}, f={theta0[1]:.2f})  "
          f"bump20=({theta0[5]:.1f}, σ={theta0[6]:.2f}, f={theta0[4]:.2f})  "
          f"bump35=({theta0[8]:.1f}, σ={theta0[9]:.2f}, f={theta0[7]:.2f})")
    print()
    print(f"{'model':27s} {'k':>2s} {'ln L':>10s} {'ΔlnL vs M0':>12s} "
          f"{'BIC':>10s} {'ΔBIC':>8s}")
    rows = [("M0 smooth (3 bumps)", 10, lnl0), ("M1 comb @ lnφ (ψ=0)", 11, lnl1),
            ("M1ψ comb @ lnφ (ψ free)", 12, lnl2),
            ("M2 comb (free period)", 13, lnl3)]
    b0 = bic(lnl0, 10, n_ev)
    for name, k, lnl in rows:
        b = bic(lnl, k, n_ev)
        print(f"{name:27s} {k:2d} {lnl:10.2f} {lnl - lnl0:12.2f} "
              f"{b:10.1f} {b - b0:8.1f}")
    print()
    print("Selection-orthogonality of the comb (VT ∝ m^a, at M1 best fit):")
    for a in (0.0, 1.0, 2.0):
        eps = selection_correction(t1, a=a)
        print(f"  a = {a}:  ε = {eps:+.4f}   "
              f"(bias in Δln L ≈ {-n_ev * eps:+.2f})")
    print()
    print(f"Rung-fraction test (excess at integer rungs, window w = {FRAC_W}):")
    s1_obs = frac_stat(samples, T=1.0)
    print(f"  S(period = ln φ)  = {s1_obs:+.4f}")
    print(f"  best period       = {S_best_scan:+.4f} at T* = "
          f"{T_best_scan:.3f} rungs (mass ratio φ^{T_best_scan:.2f} = "
          f"{PHI**T_best_scan:.2f})")
    print()
    dlnl_null, dlnlc_null, dlnl2_null, s1_null, sbest_null, tbest_null = nulls[:6]
    # selection-corrected Δln L (VT ∝ m^1.5 reference, bracket a = 0 and 2)
    eps15 = selection_correction(t1, a=1.5)
    dlnl_corr = (lnl1 - lnl0) - n_ev * math.log1p(eps15)
    eps_lo = selection_correction(t1, a=0.0)
    eps_hi = selection_correction(t1, a=2.0)
    dlnl_corr_lo = (lnl1 - lnl0) - n_ev * math.log1p(eps_lo)
    dlnl_corr_hi = (lnl1 - lnl0) - n_ev * math.log1p(eps_hi)
    p_dlnl = np.mean(dlnl_null >= lnl1 - lnl0)
    p_dlnlc = np.mean(dlnlc_null >= dlnl_corr)
    p_dlnl2 = np.mean(dlnl2_null >= lnl3 - lnl0)
    p_s1 = np.mean(s1_null >= s1_obs)
    p_sbest = np.mean(sbest_null >= S_best_scan)
    print(f"Null (bootstrap under M0, n = {len(dlnl_null)}):")
    print(f"  Δln L(M1−M0): observed {lnl1 - lnl0:+.2f}, null median "
          f"{np.median(dlnl_null):+.2f}, null 95% "
          f"{np.percentile(dlnl_null, 95):+.2f}, p = {p_dlnl:.3f}")
    print(f"  Δln L corr (VT∝m^1.5): observed {dlnl_corr:+.2f} "
          f"(bracket {dlnl_corr_lo:+.2f}..{dlnl_corr_hi:+.2f}), null median "
          f"{np.median(dlnlc_null):+.2f}, p = {p_dlnlc:.3f}")
    print(f"  S(ln φ):      observed {s1_obs:+.4f}, null median "
          f"{np.median(s1_null):+.4f}, p = {p_s1:.3f}")
    print(f"  S(best):      observed {S_best_scan:+.4f}, null median "
          f"{np.median(sbest_null):+.4f}, p = {p_sbest:.3f} "
          f"(null T* median {np.median(tbest_null):.2f})")
    print(f"  Δln L(M2−M0, free period): observed {lnl3 - lnl0:+.2f}, "
          f"null median {np.median(dlnl2_null):+.2f}, null 95% "
          f"{np.percentile(dlnl2_null, 95):+.2f}, p = {p_dlnl2:.3f}")
    print()
    print("VERDICT")
    d_obs = lnl1 - lnl0
    if p_dlnlc < 0.01 and t1[N_SMOOTH] > 0.0:
        print("  Comb at period ln φ preferred over the smooth baseline at p < 1% "
              "with positive amplitude (selection-corrected).")
    elif p_dlnlc < 0.05:
        print("  Marginal preference (p < 5%) for a comb at period ln φ "
              "(selection-corrected).")
    else:
        print("  No significant comb at the predicted period ln φ — consistent "
              "with the face-value rung analysis (peaks at 186.4/187.9/189.0).")
    print("=" * 76)

    # ---- persist for the figure script
    out = os.path.join(HERE, "data", "results.npz")
    np.savez(out,
             events=np.array(events),
             theta0=theta0, lnl0=lnl0,
             theta1=t1, lnl1=lnl1,
             theta2=t2, lnl2=lnl2,
             theta3=t3, lnl3=lnl3,
             ts=ts, S=S, T_best_scan=T_best_scan, S_best_scan=S_best_scan,
             s1_obs=s1_obs,
             dlnl_null=dlnl_null, dlnlc_null=dlnlc_null, dlnl2_null=dlnl2_null,
             s1_null=s1_null,
             sbest_null=sbest_null, tbest_null=tbest_null,
             s_curves=s_curves,
             dlnl_corr=dlnl_corr, dlnl_corr_lo=dlnl_corr_lo,
             dlnl_corr_hi=dlnl_corr_hi,
             p_dlnl=p_dlnl, p_dlnlc=p_dlnlc, p_dlnl2=p_dlnl2,
             p_s1=p_s1, p_sbest=p_sbest)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
