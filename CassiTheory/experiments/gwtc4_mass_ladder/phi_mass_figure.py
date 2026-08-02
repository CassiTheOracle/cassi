#!/usr/bin/env python3
"""Figure for the GWTC-4.0 φ-periodic mass search (phi_mass_search.py).

Three panels: (A) event-weighted primary-mass distribution with the best-fit
smooth baseline M0 and comb model M1, integer rungs marked; (B) the period
scan S(T) with the predicted T = 1 rung (period ln φ) and the M0 null band;
(C) the rung-fraction histogram with the excess window |frac| < 0.15.

Usage:
  python experiments/gwtc4_mass_ladder/phi_mass_figure.py

Reads data/results.npz and data/samples_m1.npz (run phi_mass_search.py first).
Writes phi_mass_search.png next to the script (gitignored).
"""

import os
import math

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LN_PHI = math.log(PHI)
M_PL_KG = 2.176e-8
M_SUN_KG = 1.989e30
M_SUN_PER_M_PL = M_SUN_KG / M_PL_KG
FRAC_W = 0.15

# house palette
YIN_DEEP    = "#140a33"
YIN_MID     = "#2a1a5e"
YIN_LIGHT   = "#4a2a8e"
YANG_DARK   = "#5a3a10"
YANG_MID    = "#9a6a1a"
YANG_BRIGHT = "#daa520"
YANG_PEAK   = "#ffe060"
BG          = "#060612"
TEXT_MAIN   = "#e0e0f0"
TEXT_SUB    = "#a0a0c0"
RING        = "#303050"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING, "axes.labelcolor": TEXT_MAIN,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "font.size": 10,
})

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def rung(m):
    return np.log(m * M_SUN_PER_M_PL) / LN_PHI


def main():
    r = np.load(os.path.join(DATA, "results.npz"), allow_pickle=True)
    z = np.load(os.path.join(DATA, "samples_m1.npz"), allow_pickle=True)
    samples_raw = list(z["m1"])
    rng = np.random.default_rng(3)
    samples = [rng.choice(m, size=min(1500, len(m)), replace=False)
               for m in samples_raw]

    # event-weighted mass histogram
    allm = np.concatenate(samples)
    weights = np.concatenate([np.full(len(m), 1.0 / len(samples)) for m in samples])
    m_grid = np.logspace(math.log10(3.0), math.log10(200.0), 500)

    fig, (axA, axB, axC) = plt.subplots(1, 3, figsize=(16.5, 5.4),
                                        gridspec_kw={"width_ratios": [1.25, 1.0, 1.0]})

    # ---- Panel A: mass distribution -----------------------------------------
    bins = np.logspace(math.log10(3.0), math.log10(200.0), 60)
    axA.hist(allm, bins=bins, weights=weights, histtype="step", color=YANG_MID,
             lw=1.2, label="GWTC-4.0 events (posterior draws, event-weighted)")
    # model curves (from saved best fits), scaled to per-ln-m density matching
    # the histogram integral
    from phi_mass_search import p_model
    dlnm = np.log(m_grid[1] / m_grid[0])
    hist_weights, _ = np.histogram(allm, bins=bins, weights=weights)
    tot = hist_weights.sum()
    for theta, mode, color, ls, lab in (
            (r["theta0"], 0, YIN_LIGHT, "--", "M0 smooth baseline"),
            (r["theta1"], 1, YANG_PEAK, "-", "M1 (+ comb @ ln φ)")):
        p = p_model(m_grid, theta, mode)
        curve = m_grid * p
        curve *= tot / np.trapezoid(curve, np.log(m_grid))
        axA.plot(m_grid, curve, color=color, lw=1.6, ls=ls, label=lab)
    # integer rungs
    for n in range(184, 195):
        m_rung = M_PL_KG * PHI ** n / M_SUN_KG
        if 3.0 < m_rung < 200.0:
            axA.axvline(m_rung, color=RING, lw=0.7, alpha=0.8)
    axA.text(0.02, 0.97, "integer cascade rungs 184–194",
             transform=axA.transAxes, color=TEXT_SUB, fontsize=8, va="top")
    axA.set_xscale("log")
    axA.set_xlim(3.0, 200.0)
    axA.set_xlabel(r"primary mass $m_1$ [M$_{\odot}$]")
    axA.set_ylabel("event-weighted density")
    axA.set_title("A. Mass distribution vs rung comb", color=TEXT_MAIN, fontsize=12)
    axA.legend(loc="upper right", fontsize=8, facecolor=BG, edgecolor=RING)

    # ---- Panel B: period scan ------------------------------------------------
    ts = r["ts"]
    S = r["S"]
    sc = r["s_curves"]
    med = np.median(sc, axis=0)
    lo, hi = np.percentile(sc, [5, 95], axis=0)
    axB.plot(ts, S, color=YANG_PEAK, lw=1.8, label="observed S(T)")
    axB.fill_between(ts, lo, hi, color=YIN_MID, alpha=0.5,
                     label="M0 null 5–95% (bootstrap)")
    axB.plot(ts, med, color=YIN_LIGHT, lw=1.0, ls="--")
    axB.axvline(1.0, color=YANG_BRIGHT, lw=1.4, ls=":")
    axB.text(1.0, axB.get_ylim()[1] * 0.98, "T = 1 rung\n(period ln φ)",
             color=YANG_BRIGHT, ha="center", fontsize=8, va="top")
    axB.set_xlabel(r"comb period $T$ [rungs];  mass ratio $\varphi^T$")
    axB.set_ylabel(r"rung-fraction excess $S(T)$")
    axB.set_title("B. Period scan", color=TEXT_MAIN, fontsize=12)
    axB.legend(loc="upper left", fontsize=8, facecolor=BG, edgecolor=RING)

    # ---- Panel C: rung-fraction histogram ------------------------------------
    fracs = np.concatenate([rung(m) % 1.0 for m in samples])
    fracs = np.where(fracs > 0.5, fracs - 1.0, fracs)
    w_all = np.concatenate([np.full(len(m), 1.0 / len(samples)) for m in samples])
    axC.hist(fracs, bins=np.linspace(-0.5, 0.5, 41), weights=w_all,
             histtype="step", color=YANG_PEAK, lw=1.4)
    axC.axvspan(-FRAC_W, FRAC_W, color=YANG_DARK, alpha=0.25)
    axC.axvline(0, color=YANG_BRIGHT, lw=1.0, ls="--")
    axC.annotate(f"S(1) = {r['s1_obs']:+.3f}\np = {r['p_s1']:.2f}",
                 xy=(0.0, 0.0), xytext=(0.22, 0.85), textcoords="axes fraction",
                 color=YANG_PEAK, fontsize=9, ha="left")
    axC.text(0.02, 0.97, "integer-rung excess window $|\\mathrm{frac}| < 0.15$",
             transform=axC.transAxes, color=TEXT_SUB, fontsize=8, va="top")
    axC.set_xlabel(r"rung fraction  $n$ mod 1  ($n = \log_\varphi(m_1/M_{\mathrm{Pl}})$)")
    axC.set_ylabel("event-weighted density")
    axC.set_title("C. Distance from integer rungs", color=TEXT_MAIN, fontsize=12)

    fig.suptitle(
        f"GWTC-4.0 φ-periodic mass search — Δln L(M1−M0) = {r['lnl1'] - r['lnl0']:+.2f} "
        f"(p = {r['p_dlnl']:.2f}), no significant comb at period ln φ",
        color=TEXT_MAIN, fontsize=13, y=0.99)

    OUT = os.path.join(HERE, "phi_mass_search.png")
    fig.savefig(OUT, dpi=170, facecolor=BG, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  p_dlnl = {r['p_dlnl']:.3f},  p_s1 = {r['p_s1']:.3f},  "
          f"p_sbest = {r['p_sbest']:.3f}")


if __name__ == "__main__":
    main()
