#!/usr/bin/env python3
"""
The Chord—how the strings pack
================================

The megacascade is not a 1D chain of bubbles: the strings themselves pack into
a larger structure in the doublet (Yang–Yin) plane. This script derives that
structure from the framework's own interference physics and plots ONE slice of
it—the goal is the correct *shape*, nothing more.

Derivation
----------
The two fluids are perpendicular axes of the SO(2) doublet, and each leaves a
standing wake system along its own axis (why-three-dimensions.md §3.1):

    Yang wake along the Yang axis:  wavelength Λ_Y
    Yin wake along the Yin axis:    wavelength Λ_I = Λ_Y / φ   (φ-scaled wakes)

Condensation requires BOTH fluids (conversion feeds one from the other), so the
condensation field is the PRODUCT of the two standing waves:

    C(x, y) = cos(2πx/Λ_Y) · cos(2πy/Λ_I)

Everything else follows, with no further assumptions:

1. Extrema sit at x = m·Λ_Y/2, y = n·Λ_I/2, with C = (−1)^(m+n).
   Anti-phase coupling (Δφ = π, confirmed by W1) makes the m+n even sublattice
   the condensate and the m+n odd sublattice the voids. That is exactly the
   staggered checkerboard:

       ~ • ~ • ~        row n even: bubbles at m even
       • ~ • ~ •        row n odd:  bubbles at m odd  (offset Λ_Y/2)
       ~ • ~ • ~

   The stagger is DERIVED (product of perpendicular anti-phase waves),
   not assumed.

2. Bubbles are the superlevel sets {C ≥ θ_cond}. Near each maximum,
   cos(αx)cos(βy) ≈ 1 − (α²x² + β²y²)/2, so the level set is an oval with
   semi-axis ratio

       a_Yang / a_Yin = β/α = Λ_Y/Λ_I = φ

  —the oblong φ:1 spheroid cross-section (why-three-dimensions.md §3.4)
   falls out of the same equation. The plot shows the EXACT level sets (no paraxial
   approximation).

3. Each site hosts a string piercing the page; along each string the bubbles
   stack at the cascade-step period (the chain view, cascade_cosmos.py panel A).
   This site↔string identification is the chord hypothesis; the lattice
   geometry itself (stagger, φ aspect) is structural.

Run:  python visual-explainers/chord_lattice.py
Out:  visual-explainers/chord_lattice.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgb

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
LAM_I = 2.0                    # Yin wake wavelength (display units)
LAM_Y = PHI * LAM_I            # Yang wake wavelength—φ-scaled
ALPHA = 2 * np.pi / LAM_Y      # Yang wavenumber
BETA = 2 * np.pi / LAM_I       # Yin wavenumber  (β/α = φ)
THETA_COND = 0.45              # condensation threshold on C ∈ [−1, 1]

# House palette
YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
BG, TEXT_MAIN, TEXT_SUB, RING = "#060612", "#e0e0f0", "#a0a0c0", "#303050"

def lerp(c1, c2, t):
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * np.clip(t, 0, 1))

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

# Diverging map over C ∈ [−1, +1]: Yin indigo (voids) → dark → Yang gold (condensate)
CHORDMAP = LinearSegmentedColormap.from_list("chord", [
    (0.00, YIN_MID), (0.32, YIN_DEEP), (0.50, BG),
    (0.72, YANG_DARK), (1.00, YANG_PEAK)])

# ─────────────────────────────────────────────────────────────────────────────
# The condensation field
# ─────────────────────────────────────────────────────────────────────────────
X0, X1 = -8.0, 8.0
Y0, Y1 = -3.45, 3.45
x = np.linspace(X0, X1, 1800)
y = np.linspace(Y0, Y1, 800)
XX, YY = np.meshgrid(x, y)
C = np.cos(ALPHA * XX) * np.cos(BETA * YY)

fig, ax = plt.subplots(figsize=(13.5, 8.6), dpi=170)
fig.subplots_adjust(left=0.03, right=0.99, top=0.875, bottom=0.215)
ax.set_xlim(X0, X1)
ax.set_ylim(Y0, Y1)
ax.set_aspect("equal")
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)

ax.imshow(C, extent=(X0, X1, Y0, Y1), origin="lower", cmap=CHORDMAP,
          vmin=-1, vmax=1, interpolation="bilinear", zorder=1)

# Bubbles: EXACT level sets C = θ_cond—oblong ovals, ratio → φ near maxima
ax.contour(XX, YY, C, levels=[THETA_COND], colors=[YANG_PEAK],
           linewidths=1.5, zorder=3)

# Highlight our bubble (site at the origin) with a heavier contour
mask = (np.abs(XX) < 1.3) & (np.abs(YY) < 0.9)
ax.contour(XX, YY, np.where(mask, C, np.nan), levels=[THETA_COND],
           colors=[YANG_PEAK], linewidths=3.4, zorder=4)

# Bubble centers (m+n even) get string-pierce markers; voids (m+n odd) get ×
m_max = int(X1 / (LAM_Y / 2)) + 1
n_max = int(Y1 / (LAM_I / 2)) + 1
for m in range(-m_max, m_max + 1):
    for n in range(-n_max, n_max + 1):
        sx, sy = m * LAM_Y / 2, n * LAM_I / 2
        if not (X0 < sx < X1 and Y0 < sy < Y1):
            continue
        if (m + n) % 2 == 0:   # condensate site—a string pierces the page
            ax.plot([sx], [sy], marker="o", ms=5.5, mfc="none",
                    mec=TEXT_MAIN, mew=0.9, zorder=5, alpha=0.85)
            ax.plot([sx], [sy], marker=".", ms=2.2, color=TEXT_MAIN,
                    zorder=5, alpha=0.85)
        else:                  # void site
            ax.plot([sx], [sy], marker="x", ms=4.5, mec=YIN_LIGHT,
                    mew=1.0, zorder=5, alpha=0.8)

# ─────────────────────────────────────────────────────────────────────────────
# Labels and lattice dimensions
# ─────────────────────────────────────────────────────────────────────────────
ax.annotate("OUR BUBBLE—one string's cross-section (Wu Xing, $w{=}5$)",
            xy=(0.62, 0.30), xytext=(2.2, -2.35), fontsize=8.5, color=YANG_PEAK,
            fontweight="bold",
            bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2),
            arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0))
ax.text(3 * LAM_Y / 2, -1.50, "$w{=}5$", fontsize=8, color=TEXT_SUB, ha="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.7, pad=1.5))
ax.text(-3 * LAM_Y / 2, 1.50, "$w{=}5$", fontsize=8, color=TEXT_SUB, ha="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.7, pad=1.5))

# Λ_Y: bubble spacing along Yang (arrow floats in the void band between rows 0 and 1)
ax.annotate("", xy=(LAM_Y, 0.5), xytext=(0, 0.5),
            arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.1))
ax.text(LAM_Y / 2, 0.5, "$\\Lambda_Y$—bubble\nspacing along Yang",
        fontsize=7.5, color=TEXT_MAIN, ha="center", va="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))
# Λ_I/2: row (string) spacing along Yin—bubble row to void row
ax.annotate("", xy=(-LAM_Y, 1.0), xytext=(-LAM_Y, 0),
            arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.1))
ax.text(-LAM_Y - 0.12, 0.5, "$\\Lambda_I/2$\nrow\nspacing", fontsize=7.5,
        color=TEXT_MAIN, ha="right", va="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))
# stagger: Λ_Y/2 offset of alternate rows (anti-phase), in the band above row 1
ax.annotate("", xy=(LAM_Y / 2, 1.5), xytext=(0, 1.5),
            arrowprops=dict(arrowstyle="<|-|>", color=YANG_BRIGHT, lw=1.1))
ax.text(LAM_Y / 4, 1.5, "stagger $\\Lambda_Y/2$\n(anti-phase)",
        fontsize=7.5, color=YANG_BRIGHT, ha="center", va="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))

# ─────────────────────────────────────────────────────────────────────────────
# The generating math + axis legend, in the clean bottom margin
# ─────────────────────────────────────────────────────────────────────────────
fig.suptitle("THE CHORD—strings packed on the anti-phase interference lattice",
             fontsize=17, fontweight="bold", color=YANG_PEAK, y=0.968)
fig.text(0.5, 0.135,
         "$C(x,y) = \\cos(2\\pi x/\\Lambda_Y)\\;\\cos(2\\pi y/\\Lambda_I)$,"
         "   $\\Lambda_Y = \\varphi\\,\\Lambda_I$       "
         "bubbles $=$ superlevel sets $\\{C \\geq \\theta_{\\rm cond}\\}$"
         "  →  oblong ovals, semi-axis ratio $\\Lambda_Y/\\Lambda_I = \\varphi$",
         ha="center", fontsize=10, color=TEXT_MAIN)
fig.text(0.5, 0.098,
         "sites $(m\\Lambda_Y/2,\\; n\\Lambda_I/2)$ with $m{+}n$ even  ·  voids $m{+}n$ odd"
         "—the stagger is derived (product of perpendicular anti-phase wakes), not assumed",
         ha="center", fontsize=9, color=TEXT_SUB)
fig.text(0.5, 0.055,
         "horizontal $=$ Yang axis (extended)   ·   vertical $=$ Yin axis (contracted)   ·   "
         "⊙ $=$ string pierces the page—bubbles stack along it at the cascade-step period"
         " (chain view: cascade_cosmos panel A)",
         ha="center", fontsize=8, color=TEXT_SUB)
fig.text(0.5, 0.912,
         "one cascade-step slice through the megacascade, viewed in the Yang–Yin (doublet) plane"
         "   ·   epistemic: lattice geometry structural; site ↔ string identification hypothesized",
         ha="center", fontsize=9.5, color=TEXT_SUB)

OUT = "visual-explainers/chord_lattice.png"
fig.savefig(OUT, dpi=170, facecolor=BG)
print(f"wrote {OUT}")

# ─────────────────────────────────────────────────────────────────────────────
# Verification of the derived geometry
# ─────────────────────────────────────────────────────────────────────────────
print("\nderived chord geometry:")
print(f"  wake ratio        Λ_Y/Λ_I = {LAM_Y / LAM_I:.6f}  (φ = {PHI:.6f})")
a_yang = np.arccos(THETA_COND) / ALPHA
a_yin = np.arccos(THETA_COND) / BETA
print(f"  oval semi-axes    a_Yang = {a_yang:.4f}, a_Yin = {a_yin:.4f}"
      f"  (at θ_cond = {THETA_COND})")
print(f"  oval axis ratio   a_Yang/a_Yin = {a_yang / a_yin:.6f}  (= β/α = φ exactly)")
print(f"  in-row spacing    Λ_Y   = {LAM_Y:.4f}   (bubble → bubble)")
print(f"  row spacing       Λ_I/2 = {LAM_I / 2:.4f}   (string → string)")
print(f"  row stagger       Λ_Y/2 = {LAM_Y / 2:.4f}   (anti-phase offset)")
