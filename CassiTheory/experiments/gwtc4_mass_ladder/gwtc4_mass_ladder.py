#!/usr/bin/env python3
"""GWTC-4.0 masses on the Cassi cascade ladder—rung mapping analysis.

What this does
--------------
The framework's one derived mass-to-rung relation is the black-hole
coherence-capacity rung (gravity/quantum-gravity.md §7.4):

    N_BH = log_phi(M / M_Pl)

This script maps the GWTC-4.0 population peaks and headline events onto that
ladder and asks two questions:

  1. Do the LVK primary-mass peaks (10, ~20, 35 M_sun) sit at integer cascade
     rungs?  (Naive "activated-rung" ladder hypothesis — SPECULATIVE, no
     framework derivation exists for stellar-mass black holes.)
  2. Where do the mass-gap edges (5, 130 M_sun) and the headline events land?

Epistemic tier
--------------
- N_BH = log_phi(M/M_Pl): Derived (quantum-gravity.md).
- Stellar-BH zone rung map (182-194): NEW territory — the ladder has no
  claims there between the rung-185 and rung-200 anchors. Hypothesized.
- The integer-rung peak hypothesis: Speculative; verdict from this script is
  the point of the analysis.

Data provenance (all from the GWTC-4.0 catalog paper, arXiv:2508.18082,
and the LVK population paper via the AAS Nova roundup, 2026-07-29):
- Peaks at 10, 35 and possibly 20 M_sun (population paper figure; ± widths
  are visual estimates from that figure, not the quoted fit errors).
- GW231123_135430: m1 = 137(+23/-18), m2 = 101(+22/-51), M = 236(+29/-48).
- GW230814_230901: m1 = 33.6(+2.8/-2.2), m2 = 28.3(+2.1/-3.0), M = 61.8(+2.0/-2.1),
  z = 0.06, SNR = 42.1 (loudest ever through O4a).
- GW231028_153006: M = 152(+29/-14), z = 0.39.
- GW230814_061920: M = 110, m1 = 69, m2 = 42 (medians; CI sides truncated
  in PDF extraction).
- GW230627_015337: m1 = 8.4(+1.3/-1.3), m2 = 5.79(+0.95/-0.92), M = 14.19(+0.77/-0.45).
- Lower mass gap ~5 M_sun, pair-instability upper edge ~130 M_sun (paper §3.1.1).

Usage
-----
  python experiments/gwtc4_mass_ladder/gwtc4_mass_ladder.py

Writes the figure next to the script (PNG is gitignored — commit the script
only) and prints the verification block.
"""

import math

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgb

# ─────────────────────────────────────────────────────────────────────────────
# Constants (house style)
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1.0 + math.sqrt(5.0)) / 2.0
LN_PHI = math.log(PHI)          # 0.48121... the inter-rung log period
M_PL_KG = 2.176e-8              # Planck mass
M_SUN_KG = 1.989e30             # solar mass
M_SUN_PER_M_PL = M_SUN_KG / M_PL_KG   # 9.1406e37

# House palette (from visual-explainers/cascade_cosmos.py)
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

# ─────────────────────────────────────────────────────────────────────────────
# The rung mapping
# ─────────────────────────────────────────────────────────────────────────────
def rung(m_msun):
    """N_BH = log_phi(M/M_Pl): coherence-capacity rungs (quantum-gravity.md §7.4)."""
    return math.log(m_msun * M_SUN_PER_M_PL) / LN_PHI


def mass_at_rung(n):
    """Inverse: the solar mass at a given rung."""
    return M_PL_KG * PHI ** n / M_SUN_KG


def rung_frac(n):
    """Distance from the nearest integer rung, in rung units (0 = on grid)."""
    return n - round(n)


# ─────────────────────────────────────────────────────────────────────────────
# Data (provenance in docstring)
# ─────────────────────────────────────────────────────────────────────────────
# (peak, +/- visual width, label, tentative?)
PEAKS = [
    (10.0, 1.0, r"10 M$_{\odot}$", False),
    (20.0, 2.0, r"~20 M$_{\odot}$", True),
    (35.0, 2.0, r"35 M$_{\odot}$", False),
]

# (label, m1, m1_lo, m1_hi, m2, m2_lo, m2_hi, M, M_lo, M_hi)
EVENTS = [
    ("GW230627_015337", 8.4, 1.3, 1.3, 5.79, 0.92, 0.95, 14.19, 0.45, 0.77),
    ("GW230814_061920", 69.0, 17.0, 17.0, 42.0, 16.0, 16.0, 110.0, 22.0, 20.0),
    ("GW230814_230901", 33.6, 2.2, 2.8, 28.3, 3.0, 2.1, 61.8, 2.1, 2.0),
    ("GW231028_153006", 96.0, 30.0, 30.0, 60.0, 20.0, 20.0, 152.0, 14.0, 29.0),
    ("GW231123_135430", 137.0, 18.0, 23.0, 101.0, 51.0, 22.0, 236.0, 48.0, 29.0),
]
# GW231028 component medians are not quoted in the extracted text; M is.
# GW231123 component medians are from the paper's summary table.
for i, ev in enumerate(EVENTS):
    if ev[0] == "GW231028_153006":
        EVENTS[i] = ("GW231028_153006 (M)", None, None, None, None, None, None, 152.0, 14.0, 29.0)
    if ev[0] == "GW230814_061920":
        EVENTS[i] = ("GW230814_061920 (M)", None, None, None, None, None, None, 110.0, 22.0, 20.0)

GAP_LO, GAP_HI = 5.0, 130.0          # lower gap edge, pair-instability edge

# Framework anchors nearest this zone (dimensionful-cascade.md): rung 185
# (Mt Everest) and rung 200 (Earth diameter). Drawn in plot().

ZONE_LO, ZONE_HI = 182.0, 196.0      # plotted ladder window

# ─────────────────────────────────────────────────────────────────────────────
# Verification block (console)
# ─────────────────────────────────────────────────────────────────────────────
def verify():
    print("=" * 72)
    print("GWTC-4.0 MASS-LADDER VERIFICATION  (N_BH = log_phi(M/M_Pl))")
    print("=" * 72)
    print(f"  phi = {PHI:.6f}   ln phi = {LN_PHI:.6f}   M_sun/M_Pl = {M_SUN_PER_M_PL:.4e}")
    print(f"  1 M_sun  -> rung {rung(1.0):.2f}   (doc value ~180 [10^38 M_Pl]; exact 181.6)")
    print(f"  check:   mass_at_rung(181.64) = {mass_at_rung(rung(1.0)):.3f} M_sun")
    print()
    print("  LVK primary-mass peaks:")
    for m, w, label, tent in PEAKS:
        n = rung(m)
        print(f"    {label:12s} {m:5.1f} +- {w:<4.1f} M_sun -> rung {n:7.2f}  "
              f"(frac {rung_frac(n):+.2f}, nearest integer {round(n)})")
    for i in range(len(PEAKS) - 1):
        d = math.log(PEAKS[i + 1][0] / PEAKS[i][0]) / LN_PHI
        print(f"    spacing {PEAKS[i][2]:>8s} -> {PEAKS[i+1][2]:>8s}: mass ratio "
              f"{PEAKS[i+1][0]/PEAKS[i][0]:.3f} = phi^{d:.2f}  ({d:.2f} rungs)")
    print()
    print("  Gap edges:")
    print(f"    lower gap   ~5 M_sun   -> rung {rung(GAP_LO):7.2f}")
    print(f"    pair-inst. ~130 M_sun  -> rung {rung(GAP_HI):7.2f}")
    print(f"    gap span: {rung(GAP_HI) - rung(GAP_LO):.2f} rungs")
    print()
    print("  Headline events (total masses):")
    for name, m1, m1lo, m1hi, m2, m2lo, m2hi, M, Mlo, Mhi in EVENTS:
        n = rung(M)
        print(f"    {name:22s} M = {M:6.1f} -> rung {n:7.2f}  "
              f"(90% CI {rung(M - Mlo):.2f}..{rung(M + Mhi):.2f}, frac {rung_frac(n):+.2f})")
    print()
    print("  Naive phi-ladder grid anchored at the 35 M_sun peak:")
    for k in range(0, 5):
        m = 35.0 / PHI ** k
        print(f"    peak_k{k}: {m:6.2f} M_sun -> rung {rung(m):7.2f}  (observed peaks: "
              f"{[p for p in (10.0, 20.0, 35.0) if abs(p - m) < 0.75 * m * 0.15]})")
    print()
    print("  VERDICTS")
    print("  1. Integer-rung ladder: peak rungs 186.4/187.9/189.0, spacings 1.44/1.16")
    print("     rungs -> NOT an integer grid; 10 M_sun peak sits 0.43 rungs off.")
    print("  2. Near-integer coincidences to track: 35 M_sun -> 189.03, GW231123")
    print("     total 236 M_sun -> 193.00 (CI 192.5..193.4), lower gap edge -> 185.0.")
    print("  3. Proper test needs full posteriors + GWTC-5: log-periodic search at")
    print("     Delta(ln m) = k ln phi on the m1 posterior samples.")
    print("=" * 72)


# ─────────────────────────────────────────────────────────────────────────────
# Figure
# ─────────────────────────────────────────────────────────────────────────────
def plot():
    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(13.5, 5.6), gridspec_kw={"width_ratios": [1.35, 1.0]})

    # ---- Panel A: the ladder zone -------------------------------------------
    ns = np.linspace(ZONE_LO, ZONE_HI, 600)
    for n in range(int(ZONE_LO), int(ZONE_HI) + 1):
        axA.axvline(n, color=RING, lw=0.8, zorder=1)
    # Framework anchors nearest this zone (dimensionful-cascade.md); rung 200
    # sits outside the window — annotate the right edge instead.
    for n, lab in [(185, "rung 185\n(Mt Everest)")]:
        axA.axvline(n, color=YIN_LIGHT, lw=1.4, ls="--", zorder=1)
        axA.text(n, 2.6, lab, color=YIN_LIGHT, ha="center", va="bottom",
                 fontsize=8.5)
    axA.text(ZONE_HI - 0.15, 0.32, r"next anchor: rung 200 (Earth diameter) $\rightarrow$",
             color=YIN_LIGHT, ha="right", va="bottom", fontsize=8.5)

    # Gap band (5 -> 130 M_sun)
    n_glo, n_ghi = rung(GAP_LO), rung(GAP_HI)
    axA.axvspan(n_glo, n_ghi, color=YIN_MID, alpha=0.35, zorder=0)
    axA.text((n_glo + n_ghi) / 2, 2.6, r"stellar BH zone" "\n" r"(gap 5-130 M$_{\odot}$)",
             color=TEXT_SUB, ha="center", va="top", fontsize=9)

    # Peaks as vertical bands
    for m, w, label, tent in PEAKS:
        n = rung(m)
        dn = math.log(1 + w / m) / LN_PHI
        color = YANG_BRIGHT if not tent else YANG_MID
        axA.axvspan(n - dn, n + dn, color=color, alpha=0.30, zorder=2)
        axA.axvline(n, color=color, lw=2.2, ls="--", zorder=3)
        axA.text(n, 2.4, label, color=color, ha="center", va="bottom", fontsize=11,
                 fontweight="bold", zorder=5)

    # Events (total mass) with 90% CI bars; labels staggered above/below
    for idx, (name, m1, m1lo, m1hi, m2, m2lo, m2hi, M, Mlo, Mhi) in enumerate(EVENTS):
        n = rung(M)
        dn_lo = math.log(1 + Mlo / M) / LN_PHI
        dn_hi = math.log(1 + Mhi / M) / LN_PHI
        axA.errorbar(n, 1.0, xerr=[[dn_lo], [dn_hi]], fmt="o", color=YANG_PEAK,
                     markersize=5, elinewidth=1.6, capsize=3, zorder=4)
        label = name.replace("_", "\n")
        ly = 0.55 if idx % 2 == 0 else 1.85
        axA.text(n, ly, label, color=YANG_PEAK, ha="center", va="top",
                 fontsize=7.5, zorder=5)

    # Unmapped-zone bracket
    axA.annotate("", xy=(rung(1.0) + 0.3, 3.35), xytext=(rung(130.0) + 0.3, 3.35),
                 arrowprops=dict(arrowstyle="<->", color=TEXT_SUB, lw=1.2))
    axA.text((rung(1.0) + rung(130.0)) / 2 + 0.3, 3.5,
             "no framework claims between anchors\n(N_BH = log$_\\varphi$(M/M_Pl), q-gravity silent here)",
             color=TEXT_SUB, ha="center", va="bottom", fontsize=8.5)

    axA.set_xlim(ZONE_LO, ZONE_HI)
    axA.set_ylim(0.0, 3.9)
    axA.set_xlabel("cascade rung $n$  ($\\ell_n = \\ell_{\\mathrm{Pl}}\\,\\varphi^{n}$)")
    axA.set_yticks([])
    axA.set_title("GWTC-4.0 masses on the cascade ladder", color=TEXT_MAIN, fontsize=12)
    axA.text(0.01, 0.98, "$N_{\\mathrm{BH}} = \\log_\\varphi(M/M_{\\mathrm{Pl}})$",
             transform=axA.transAxes, color=YANG_MID, fontsize=12, va="top")
    axA.text(0.01, 0.90, "shaded = LVK m$_1$ peaks | points = event total masses",
             transform=axA.transAxes, color=TEXT_SUB, fontsize=8.5, va="top")

    # ---- Panel B: distance from the integer grid ----------------------------
    fracs_peaks = [rung_frac(rung(m)) for m, w, label, tent in PEAKS]
    fracs_events = [rung_frac(rung(ev[7])) for ev in EVENTS]

    axB.axhline(0, color=YANG_PEAK, lw=1.0, ls="--")
    for i, (m, w, label, tent) in enumerate(PEAKS):
        color = YANG_BRIGHT if not tent else YANG_MID
        axB.scatter(fracs_peaks[i], i, s=90, color=color, zorder=3)
        axB.annotate(f"{label}\n$n={rung(m):.2f}$", xy=(fracs_peaks[i], i),
                     xytext=(fracs_peaks[i], i + 0.28), ha="center", fontsize=8.5,
                     color=color)
    for i, ev in enumerate(EVENTS):
        axB.scatter(fracs_events[i], -0.9 - 0.35 * i, s=55, color=YANG_PEAK, zorder=3)
        axB.annotate(ev[0] + f" M={ev[7]:.0f}", xy=(fracs_events[i], -0.9 - 0.35 * i),
                     xytext=(fracs_events[i], -0.9 - 0.35 * i + 0.3), ha="center",
                     fontsize=7.5, color=YANG_PEAK)

    # Naive phi-grid prediction (integer k anchored at 35 M_sun)
    for k in range(1, 5):
        m = 35.0 / PHI ** k
        n = rung(m)
        axB.scatter(rung_frac(n), 2.4 - 0.35 * k, marker="D", s=55,
                    facecolor="none", edgecolor=YIN_LIGHT, zorder=2)
        axB.annotate(f"{m:.1f}", xy=(rung_frac(n), 2.4 - 0.35 * k),
                     xytext=(rung_frac(n), 2.4 - 0.35 * k + 0.25), ha="center",
                     fontsize=7.5, color=YIN_LIGHT)

    axB.axvspan(-0.5, 0.5, color=YANG_DARK, alpha=0.12, zorder=1)
    axB.set_xlim(-0.5, 0.5)
    axB.set_ylim(-3.1, 2.9)
    axB.set_xticks([-0.5, 0, 0.5])
    axB.set_xlabel("rung position modulo integer grid  ($n$ mod 1)")
    axB.set_yticks([])
    axB.set_title("Distance from nearest integer rung", color=TEXT_MAIN, fontsize=12)
    axB.text(0.01, 0.98, "gold: peaks/events   hollow diamonds: naive $\\varphi$-grid\n"
                         "(35/\\varphi$^k$) — where a $\\Delta n = 1$ ladder would put peaks",
             transform=axB.transAxes, color=TEXT_SUB, fontsize=8.5, va="top")

    fig.suptitle("GWTC-4.0 on the Cassi ladder: peaks at $n$ = 186.4, 187.9, 189.0 — "
                 "spacings 1.44, 1.16 rungs, not an integer grid",
                 color=TEXT_MAIN, fontsize=13, y=0.99)

    OUT = "experiments/gwtc4_mass_ladder/gwtc4_mass_ladder.png"
    fig.savefig(OUT, dpi=170, facecolor=BG, bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    verify()
    plot()
