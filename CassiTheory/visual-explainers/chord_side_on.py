#!/usr/bin/env python3
"""
The Chord, side-on — bubbles threaded on strings
================================================

The user's picture, derived: the megacascade in the (string × Yin) slice.
Rows are strings (~); bubbles are WAISTED lobe-pairs threaded on them,
staggered by half a period between adjacent strings:

    {  }~{  }~{  }~
     ~{  }~{  }~{  }
    {  }~{  }~{  }~

Why waisted and not ovals
-------------------------
The membrane envelope of a bubble is a convex triaxial oval (level set of the
wake-interference product). But the CONDENSATE inside cannot fill the oval:
the W1 experiment confirmed anti-phase conversion (corr(E_Y,E_I) = −1), which
puts a NODE on the bubble midplane — the central void of the paired-sheet
morphology (why-three-three-dimensions.md §4). Including the node, the
condensate field of one bubble centered at (z₀, y_s) is

    B(z, y) = cos(2π(z−z₀)/P_∥) · [1 − cos(π(y−y_s)/d)]

      · zero ON the string (the midplane node — the string threads the void)
      · twin lobes at y = y_s ± d  (the paired sheets seen edge-on)
      · superlevel sets {B ≥ θ} are waisted lobe-pairs:  {  }

The lattice placement (stagger) comes from the anti-phase checkerboard derived
in chord_lattice.py: sites z = m·P_∥ on even strings, z = (m+½)·P_∥ on odd
strings; strings spaced s in the Yin direction.

What is derived vs open
-----------------------
Derived (structural): the stagger; the node on the string; the twin-lobe
shape; φ-ratios between wake-generated periods in the doublet plane.
Open (not yet derived): the absolute scales, P_∥/s, and θ_cond — candidates:
the wake spacing c(r)·τ(r) of dimensionful-cascade.md §5.1.
Spacing ratio P_∥/s in this plot is illustrative.

Run:  python visual-explainers/chord_side_on.py
Out:  visual-explainers/chord_side_on.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.colors import LinearSegmentedColormap, to_rgb

# ─────────────────────────────────────────────────────────────────────────────
# Lattice + lobe parameters (display units; ratio P_∥/s illustrative)
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
P_PAR = 3.0                 # along-string bubble period (cascade-step train)
S_ROW = 2.2                 # string spacing (Yin direction)
D_LOBE = 0.35 * S_ROW       # lobe offset from string (the ±λ/2 sheets)
ALPHA = 2 * np.pi / P_PAR   # wavenumber along string
BETA = np.pi / D_LOBE       # internal anti-phase wavenumber (node on string)
THETA = 1.3                 # condensation threshold on B ∈ [0, 2]

# House palette
YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
BG, TEXT_MAIN, TEXT_SUB, RING = "#060612", "#e0e0f0", "#a0a0c0", "#303050"

def lerp(c1, c2, t):
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * np.clip(t, 0, 1))

GOLDMAP = LinearSegmentedColormap.from_list(
    "gold", [BG, YIN_DEEP, YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK])

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

X0, X1 = -8.6, 8.6
ROWS = [-2 * S_ROW, -S_ROW, 0.0, S_ROW, 2 * S_ROW]
Y0, Y1 = -3.75, 3.75        # middle three strings full, outer rows hinted

fig, ax = plt.subplots(figsize=(13.5, 9.2), dpi=170)
fig.subplots_adjust(left=0.03, right=0.99, top=0.855, bottom=0.20)
ax.set_xlim(X0, X1)
ax.set_ylim(Y0, Y1)
ax.set_aspect("equal")
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)

# ─────────────────────────────────────────────────────────────────────────────
# The condensate: per-bubble waisted lobe-pairs on the staggered lattice
# ─────────────────────────────────────────────────────────────────────────────
x = np.linspace(X0, X1, 1700)
y = np.linspace(Y0, Y1, 1100)
XX, YY = np.meshgrid(x, y)
B = np.zeros_like(XX)

ENV_Z, ENV_Y = 1.15, S_ROW / 2 - 0.02    # membrane: bounded along string, contracted Yin

sites = []   # (z0, y_string, row_index)
for i, ys in enumerate(ROWS):
    offset = 0.0 if i % 2 == 0 else P_PAR / 2     # anti-phase stagger
    m0 = int(np.floor((X0 - offset) / P_PAR))
    m1 = int(np.ceil((X1 - offset) / P_PAR))
    for m in range(m0, m1 + 1):
        z0 = offset + m * P_PAR
        sites.append((z0, ys, i))
        # each bubble owns its lattice cell — window kills spurious far-period lobes
        cell = (np.abs(XX - z0) <= P_PAR / 2) & (np.abs(YY - ys) <= S_ROW / 2)
        B_site = np.where(cell,
                          np.cos(ALPHA * (XX - z0)) * (1 - np.cos(BETA * (YY - ys))),
                          -1.0)
        B = np.maximum(B, B_site)
        # membrane envelope around each lobe-pair (groups the { } visually)
        if abs(z0) > 1e-9 and abs(z0) < X1 - 1.3:
            ax.add_patch(Ellipse((z0, ys), 2 * ENV_Z, 2 * ENV_Y, fill=False,
                                 edgecolor=RING, lw=0.8, ls=(0, (4, 4)),
                                 alpha=0.55, zorder=2))

# Field glow (gamma-compressed so sub-threshold channels stay dark) + exact contours
B_show = np.where(B > 0.02, B, np.nan)
ax.imshow(B_show ** 2.2, extent=(X0, X1, Y0, Y1), origin="lower", cmap=GOLDMAP,
          vmin=0, vmax=2.0 ** 2.2, interpolation="bilinear", zorder=1)
ax.contour(XX, YY, B, levels=[THETA], colors=[YANG_PEAK], linewidths=1.4, zorder=3)

# The strings: wavy lines threading the lobe-pairs (visible in the node channel)
for i, ys in enumerate(ROWS):
    xs_line = np.linspace(X0, X1, 900)
    ys_line = ys + 0.055 * np.sin(2 * np.pi * xs_line / (P_PAR / 7))  # wake crests per rung
    for j in range(0, len(xs_line) - 2, 2):
        t = (xs_line[j] - X0) / (X1 - X0)
        ax.plot(xs_line[j:j + 3], ys_line[j:j + 3],
                color=lerp(YIN_LIGHT, YANG_BRIGHT, t), lw=1.8,
                solid_capstyle="round", zorder=2, alpha=0.9)

# ─────────────────────────────────────────────────────────────────────────────
# Our bubble: highlight + membrane envelope (envelope vs condensate)
# ─────────────────────────────────────────────────────────────────────────────
mask = (np.abs(XX) < P_PAR / 2) & (np.abs(YY) < S_ROW / 2 + 0.1)
ax.contour(XX, YY, np.where(mask, B, np.nan), levels=[THETA],
           colors=[YANG_PEAK], linewidths=3.4, zorder=4)
ax.add_patch(Ellipse((0, 0), 2 * ENV_Z, 2 * ENV_Y, fill=False,
                     edgecolor=TEXT_SUB, lw=1.3, ls=(0, (5, 4)), alpha=0.9, zorder=5))

ax.annotate("OUR BUBBLE — waisted condensate + membrane\n"
            "envelope (dashed): the string threads the void",
            xy=(0.45, -0.70), xytext=(2.75, -2.05), fontsize=8.5, color=YANG_PEAK,
            fontweight="bold",
            bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2),
            arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0))
ax.text(1.5 * P_PAR, S_ROW + 1.25, "$w{=}4$", fontsize=8, color=TEXT_SUB,
        ha="center", bbox=dict(facecolor=BG, edgecolor="none", alpha=0.7, pad=1.5))
ax.text(-1.5 * P_PAR, -S_ROW - 1.25, "$w{=}6$", fontsize=8, color=TEXT_SUB,
        ha="center", bbox=dict(facecolor=BG, edgecolor="none", alpha=0.7, pad=1.5))

# ─────────────────────────────────────────────────────────────────────────────
# Lattice dimensions
# ─────────────────────────────────────────────────────────────────────────────
# P_∥: along-string period, drawn in the clear stretch of string 0's node channel
ax.annotate("", xy=(P_PAR - 0.45, 0.0), xytext=(0.45, 0.0),
            arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.1))
ax.text(P_PAR / 2, -0.22, "$P_\\parallel$ — bubble period along the string",
        fontsize=7.5, color=TEXT_MAIN, ha="center", va="top",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=1.5))
# s: string spacing
ax.annotate("", xy=(X0 + 0.55, S_ROW), xytext=(X0 + 0.55, 0),
            arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.1))
ax.text(X0 + 0.35, S_ROW / 2, "$s$ —\nstring\nspacing", fontsize=7.5,
        color=TEXT_MAIN, ha="right", va="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=1.5))
# stagger: P_∥/2 offset of alternate strings, in the void channel of row +1
ax.annotate("", xy=(P_PAR / 2, S_ROW), xytext=(0, S_ROW),
            arrowprops=dict(arrowstyle="<|-|>", color=YANG_BRIGHT, lw=1.1))
ax.text(P_PAR / 4, S_ROW + 0.30, "stagger $P_\\parallel/2$ (anti-phase)",
        fontsize=7.5, color=YANG_BRIGHT, ha="center", va="center",
        bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))


# ─────────────────────────────────────────────────────────────────────────────
# Titles + generating math (clean margins)
# ─────────────────────────────────────────────────────────────────────────────
fig.suptitle("THE CHORD, SIDE-ON — bubbles threaded on strings",
             fontsize=17, fontweight="bold", color=YANG_PEAK, y=0.968)
fig.text(0.5, 0.920,
         "the (string × Yin) slice of the megacascade  ·  "
         "condensate is waisted because the midplane is an anti-phase node (W1)",
         ha="center", fontsize=9.5, color=TEXT_SUB)
fig.text(0.5, 0.128,
         "per bubble:  $B(z,y) = \\cos(2\\pi(z-z_0)/P_\\parallel)\\,"
         "[1-\\cos(\\pi(y-y_s)/d)] \\geq \\theta$"
         "   →   twin lobes straddling the string:  {  }",
         ha="center", fontsize=10, color=TEXT_MAIN)
fig.text(0.5, 0.092,
         "lattice: sites $z = mP_\\parallel$ (even strings), $z = (m{+}\\frac{1}{2})P_\\parallel$"
         " (odd strings) — stagger derived from the anti-phase checkerboard (chord_lattice.py)",
         ha="center", fontsize=9, color=TEXT_SUB)
fig.text(0.5, 0.050,
         "derived: the stagger, the node on the string, the twin-lobe shape   ·   "
         "open: absolute scales, $P_\\parallel/s$, $\\theta_{\\rm cond}$"
         " (candidate: wake spacing $c(r)\\,\\tau(r)$)   ·   spacing ratio illustrative",
         ha="center", fontsize=8, color=TEXT_SUB)

OUT = "visual-explainers/chord_side_on.png"
fig.savefig(OUT, dpi=170, facecolor=BG)
print(f"wrote {OUT}")

# ─────────────────────────────────────────────────────────────────────────────
# Verification of the lobe geometry
# ─────────────────────────────────────────────────────────────────────────────
z_half = np.arccos(THETA / 2) / ALPHA          # at the antinode, [1−cos] = 2
y_half = (np.pi - np.arccos(1 - THETA)) / BETA  # half-height about y = d
print("\nderived lobe geometry (θ = %.2f):" % THETA)
print(f"  lobe half-width along string : {z_half:.4f}  (period P_∥ = {P_PAR})")
print(f"  lobe half-height (Yin)       : {y_half:.4f}  (offset d = {D_LOBE})")
print(f"  lobe aspect (z:y)            : {z_half / y_half:.4f}")
print(f"  string gap between lobe-pairs: {P_PAR - 2 * z_half:.4f}")
print(f"  void band between strings    : {S_ROW - 2 * (D_LOBE + y_half):.4f}")
