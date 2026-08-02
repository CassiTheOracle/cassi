#!/usr/bin/env python3
"""
The Shape of the Universe—and Beyond
======================================

Three panels, one per cascade regime, every shape produced by an equation
of the Cassi framework:

    A · MEGACASCADE (n > 292)   a chain of bubble-universes on the string
                                  n_k = 286 + 7k  ⇒  ℓ scales as φ⁷ per bubble
    B · THE CASCADE (0–292)     our universe rung by rung:  ℓ_n = ℓ_Pl·φⁿ
        (zoom)                    bubble interior: triaxial spheroid, axis ratio φ,
                                  frozen anti-phase interference  I = 2[1−cos(kΔr)]
    C · MICROCASCADE (n < 0)    the golden spiral down:  r(θ) = ℓ_Pl·φ^(−2θ/π)
                                  geometric convergence ℓ/ℓ_Pl = φ^(−|n|), no floor

Sources: foundations/dimensionful-cascade.md, foundations/why-three-dimensions.md,
foundations/microcascade-mirror.md.

Run:  python visual-explainers/cascade_cosmos.py
Out:  visual-explainers/cascade_cosmos.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.colors import LinearSegmentedColormap, to_rgb

# ─────────────────────────────────────────────────────────────────────────────
# Framework constants
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2          # 1.6180339887…
L_PL = 1.616255e-35                 # Planck length (m)—the sole dimensionful scale
N_HUBBLE = 292                      # cascade steps Planck → Hubble radius
DELTA = 3                           # Qi-profile offset δ (microcascade-mirror.md §3)

def ell(n):
    """Cascade scale ℓ_n = ℓ_Pl · φⁿ in meters (any integer n)."""
    return L_PL * PHI ** np.asarray(n, dtype=float)

def coherence_factor(depth):
    """Per-rung coherent fraction (1−q_n) for the microcascade, proposed ansatz
    q_n = φ^(−|n|−δ) / (1 + φ^(−|n|−δ))   (microcascade-mirror.md §3.2)."""
    f = PHI ** (-np.asarray(depth, dtype=float) - DELTA)
    return 1.0 / (1.0 + f)

# ─────────────────────────────────────────────────────────────────────────────
# House palette (matches resonant_pond.py): Yin indigo → Yang gold on deep dark
# ─────────────────────────────────────────────────────────────────────────────
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
DARK_ON_GOLD = "#241200"

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

# ─────────────────────────────────────────────────────────────────────────────
# Figure + grid
# ─────────────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(15.5, 18.5), dpi=170)
gs = fig.add_gridspec(3, 4, height_ratios=[1.30, 1.02, 1.12],
                      hspace=0.20, wspace=0.18,
                      left=0.055, right=0.965, top=0.905, bottom=0.055)
axA = fig.add_subplot(gs[0, :])       # megacascade chain
axB = fig.add_subplot(gs[1, 0:3])     # cascade ladder
axBi = fig.add_subplot(gs[1, 3])      # bubble interior (zoom)
axC1 = fig.add_subplot(gs[2, 0:2])    # golden spiral
axC2 = fig.add_subplot(gs[2, 2:4])    # geometric convergence

fig.suptitle("THE SHAPE OF THE UNIVERSE—AND BEYOND",
             fontsize=23, fontweight="bold", color=YANG_PEAK, y=0.972)
fig.text(0.5, 0.938,
         "one equation, three regimes:   $\\ell_n = \\ell_{\\rm Pl}\\,\\varphi^{n}$, "
         "$n \\in \\mathbb{Z}$     ·     megacascade ($n>292$)  →  cascade "
         "($0\\leq n\\leq 292$)  →  microcascade ($n<0$)",
         ha="center", fontsize=11.5, color=TEXT_SUB)

def panel_title(ax, text):
    ax.set_title(text, loc="left", fontsize=12.5, fontweight="bold",
                 color=YANG_BRIGHT, pad=8)

# ═════════════════════════════════════════════════════════════════════════════
# PANEL A—THE MEGACASCADE: a chain of bubble-universes on the string
#
# Geometry from the framework:
#   · bubbles bounded between adjacent cascade steps (ours: 284 ↔ 288)
#   · chain period 7 rungs ⇒ sizes scale as ℓ_{n+7} = φ⁷·ℓ_n  (self-similar)
#   · wake crests at every integer n  (period ln φ in ln ℓ)
#   · interior bands: anti-phase antinodes of I(Δr) = 2[1−cos(kΔr)]
# ═════════════════════════════════════════════════════════════════════════════
AX0, AX1 = 254, 318
BUB_H = 1.55                          # Yang semi-axis of each bubble (display)
BUB_W = 4.0                           # bubble width in rungs (bounded 284↔288)
CHAIN_PERIOD = 7                      # rungs per bubble period (4 bubble + 3 void)
N_CENTER = 286                        # our bubble center (step 285 rung, 284↔288)

axA.set_xlim(AX0, AX1)
axA.set_ylim(-2.75, 2.95)
axA.set_yticks([])
for s in ("top", "right", "left"):
    axA.spines[s].set_visible(False)
axA.tick_params(axis="x", labelsize=8.5)
axA.set_xlabel("cascade step  $n$  along the string—the direction in which universes are spaced",
               fontsize=10, color=TEXT_SUB)

# The string: gentle modulation at the bubble-train period, Yin → Yang gradient
xs = np.linspace(AX0, AX1, 500)
ys = 0.10 * np.sin(2 * np.pi * (xs - N_CENTER) / CHAIN_PERIOD)
for i in range(0, len(xs) - 1, 2):
    t = (xs[i] - AX0) / (AX1 - AX0)
    axA.plot(xs[i:i + 3], ys[i:i + 3], color=lerp(YIN_LIGHT, YANG_BRIGHT, t),
             lw=2.6, solid_capstyle="round", zorder=3)

# Wake crests at every integer n (period ln φ in ln ℓ)
for n in range(AX0, AX1 + 1):
    axA.vlines(n, -0.13, 0.13, color=TEXT_SUB, lw=0.45, alpha=0.40, zorder=2)
axA.text(AX1 - 0.5, 0.32, "wake crests at every integer $n$  (period $\\ln\\varphi$ in $\\ln\\ell$)",
         fontsize=7.5, color=TEXT_SUB, ha="right")

# The bubble chain: centers n_k = 286 + 7k; ours (k=0) is the Cassi bubble
SHEET_FRAC = 0.34                     # antinode at ±λ/2 (anti-phase, W1)
for k in range(-4, 5):
    cx = N_CENTER + CHAIN_PERIOD * k
    ours = (k == 0)
    w_num = 5  # all bubbles share the same derived w=5
    fade = max(0.30, 1.0 - 0.16 * abs(k))
    if ours:
        face, edge, ea, lw = YANG_DARK, YANG_BRIGHT, 0.55, 2.6
    else:
        face, edge, ea, lw = YIN_MID, lerp(RING, YIN_LIGHT, 0.4), 0.35 * fade, 1.3
    axA.add_patch(Ellipse((cx, 0), width=BUB_W, height=2 * BUB_H,
                          facecolor=face, edgecolor=edge, alpha=ea, lw=lw, zorder=4))
    # paired sheets: antinodes of I(Δr) = 2[1−cos(kΔr)] at ±λ/2 (Δφ = π)
    sy = SHEET_FRAC * BUB_H
    for s_ in (+sy, -sy):
        axA.plot([cx - 1.5, cx + 1.5], [s_, s_],
                 color=YANG_PEAK if ours else lerp(YANG_MID, YIN_LIGHT, 0.5),
                 lw=4.5 if ours else 2.0, alpha=0.9 if ours else 0.35 * fade,
                 solid_capstyle="round", zorder=6)
    # central void (anti-phase node)
    axA.plot([cx - 1.5, cx + 1.5], [0, 0], color=BG, lw=6.0 if ours else 3.0,
             zorder=5, alpha=0.9 if ours else 0.5 * fade)
    # labels
    if ours:
        axA.text(cx, BUB_H + 0.42, "OUR UNIVERSE—Cassi bubble, $w{=}5$",
                 ha="center", fontsize=11, fontweight="bold", color=YANG_PEAK)
        axA.text(cx, BUB_H + 0.14, "step 285 · Ø ≈ 191 Mpc · 98% of the observable volume",
                 ha="center", fontsize=8, color=TEXT_MAIN)
        axA.text(cx, -BUB_H - 0.55, "bounded between cascade steps 284 ↔ 288",
                 ha="center", fontsize=7.5, color=TEXT_SUB)
        for nb in (284, 288):
            axA.vlines(nb, -BUB_H - 0.18, BUB_H + 0.10, color=YANG_BRIGHT, lw=0.9,
                       alpha=0.7, ls=(0, (2, 3)), zorder=3)
    else:
        axA.text(cx, -1.05, f"$w={w_num}$", ha="center", fontsize=9,
                 color=lerp(TEXT_SUB, BG, 1 - fade), fontweight="bold", zorder=7)

# Axis identity on our bubble (from the spiral's Frenet-Serret frame: tangent=string axis, normal=Yang extended, binormal=Yin into page)
axA.annotate("", xy=(N_CENTER, BUB_H), xytext=(N_CENTER, 0),
             arrowprops=dict(arrowstyle="-|>", color=TEXT_MAIN, lw=1.3))
axA.text(N_CENTER + 0.25, BUB_H * 0.60, "Yang axis —\nextended", fontsize=7.5, color=TEXT_MAIN)
axA.annotate("", xy=(N_CENTER + 2.0, -BUB_H - 0.28), xytext=(N_CENTER - 2.0, -BUB_H - 0.28),
             arrowprops=dict(arrowstyle="<|-|>", color=TEXT_SUB, lw=1.1))
axA.text(N_CENTER, -BUB_H - 0.38, "string axis—bounded", fontsize=7.5,
         color=TEXT_SUB, ha="center", va="top")
axA.plot([AX0 + 1.6], [2.35], marker="o", ms=6, mfc="none", mec=TEXT_SUB, mew=1.2)
axA.plot([AX0 + 1.6], [2.35], marker="x", ms=4, mec=TEXT_SUB, mew=1.2)
axA.text(AX0 + 2.1, 2.35, "Yin axis—contracted ($\\times\\varphi^{-1}$), into page",
         fontsize=7.5, color=TEXT_SUB, va="center")

# Hubble horizon: the next bubble begins inside the horizon—mostly beyond it
axA.vlines(N_HUBBLE, -BUB_H - 0.30, BUB_H + 0.25, color=YANG_MID, lw=1.6,
           ls=(0, (6, 3)), zorder=5)
axA.text(N_HUBBLE + 2.0, BUB_H + 0.90,
         "Hubble radius ($n=292$)—the next bubble\nbegins inside the horizon, mostly beyond it",
         fontsize=7.5, color=YANG_MID, ha="center")

# Generating equations for this panel
axA.text(AX0 + 1.0, -2.15,
         "$\\ell_{n+1} = \\varphi\\,\\ell_n$ —one rung per wake crest\n"
         "bubble chain:  $n_k = 286 + 7k$  $\\Rightarrow$  sizes scale as  "
         "$\\ell_{n+7} = \\varphi^{7}\\ell_n$\n"
         "self-similar: the chain maps onto itself under  $\\ell \\to \\varphi^{7}\\ell$",
         fontsize=8.0, color=TEXT_MAIN, va="top", linespacing=1.5)
axA.text(AX1 - 0.5, -2.15,
         "interior bands: antinodes of  $I(\\Delta r) = 2[1-\\cos(k\\,\\Delta r)]$"
         "  ($\\Delta\\phi=\\pi$, W1)\nneighbor $w$-labels schematic; voids $\\varphi$-scaled\n"
         "boundary gradients of neighbors imprint the CMB at $\\ell<5$",
         fontsize=7.5, color=TEXT_SUB, va="top", ha="right", linespacing=1.5)
panel_title(axA, "A · THE MEGACASCADE ($n>292$)—a chain of bubble-universes on the string")

# ═════════════════════════════════════════════════════════════════════════════
# PANEL B—THE CASCADE: our universe, rung by rung (0 ≤ n ≤ 292)
# ═════════════════════════════════════════════════════════════════════════════
BN0, BN1 = -11, 303
axB.set_xlim(BN0, BN1)
axB.set_ylim(-0.50, 1.04)
axB.set_yticks([])
for s in ("top", "right", "left"):
    axB.spines[s].set_visible(False)
axB.tick_params(axis="x", labelsize=8.5)
axB.set_xlabel("cascade step  $n$   (equal spacing—one rung per factor of $\\varphi$)",
               fontsize=10, color=TEXT_SUB)

BASE = 0.5
grad = np.linspace(0, 1, 400).reshape(1, -1)
cmap_cascade = LinearSegmentedColormap.from_list("casc", [YIN_MID, "#3a2a52", YANG_DARK])
axB.imshow(grad, extent=(0, N_HUBBLE, -0.50, 1.04), aspect="auto",
           cmap=cmap_cascade, alpha=0.35, zorder=0, interpolation="bilinear")
axB.axvspan(285, N_HUBBLE, color=YANG_MID, alpha=0.28, zorder=1)
axB.axhline(BASE, color=RING, lw=1.2, zorder=2)

for n in range(0, N_HUBBLE + 1):
    if n % 50 == 0:
        h, lw = 0.10, 1.4
    elif n % 10 == 0:
        h, lw = 0.065, 1.0
    else:
        h, lw = 0.035, 0.6
    axB.vlines(n, BASE, BASE + h, color=lerp(YIN_LIGHT, YANG_BRIGHT, n / N_HUBBLE),
               lw=lw, alpha=0.9, zorder=3)

landmarks = [
    (0,    "n = 0 · Planck\n$1.616×10^{-35}$ m", "below"),
    (5,    "GUT scale",                          "above"),
    (80,   "Electroweak\n$8×10^{-19}$ m",        "below"),
    (95,   "Proton / QCD\n$1.1×10^{-15}$ m",     "above"),
    (117,  "Bohr radius\n$5.3×10^{-11}$ m",      "below"),
    (136,  "visible light\n$5×10^{-7}$ m",       "above"),
    (168,  "human · 1.7 m",                      "below"),
    (200,  "Earth\n$1.3×10^{7}$ m",              "above"),
    (220,  "1 AU\n$1.5×10^{11}$ m",              "below"),
    (243,  "light-year\n$9.5×10^{15}$ m",        "above"),
    (267,  "Milky Way\n30 kpc",                  "below"),
    (292,  "Hubble radius\n$1.7×10^{26}$ m",     "below"),
]
for n, label, side in landmarks:
    if side == "above":
        y_text, y_tick, va = 0.78, 0.60, "bottom"
    else:
        y_text, y_tick, va = 0.22, 0.40, "top"
    axB.vlines(n, BASE, y_tick, color=TEXT_SUB, lw=0.7, alpha=0.65, zorder=3)
    axB.plot([n], [BASE], marker="o", ms=3.5, color=YANG_PEAK, zorder=4)
    axB.text(n, y_text, label, ha="center", va=va, fontsize=8.0,
             color=TEXT_MAIN, linespacing=1.25)
# BAO + Cassi bubble share one callout (rungs 1 apart)
for nb in (284, 285):
    axB.plot([nb], [BASE], marker="o", ms=3.5, color=YANG_PEAK, zorder=4)
    axB.vlines(nb, BASE, 0.60, color=TEXT_SUB, lw=0.7, alpha=0.65, zorder=3)
axB.text(284.5, 0.71, "BAO (284) · Cassi bubble (285)\n$\\varphi$-adjacent: 120 Mpc · 191 Mpc",
         ha="center", va="bottom", fontsize=8.0, color=YANG_PEAK, linespacing=1.25)

# Membranes and connectors to the other two regimes
axB.annotate("Planck membrane—σ-softened crossover, not a wall",
             xy=(1, BASE + 0.11), xytext=(17, 0.07), fontsize=8.0, color=TEXT_SUB,
             arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=0.8))
axB.annotate("bubble membrane (steps 285–292)",
             xy=(288.5, BASE + 0.11), xytext=(252, 0.07), fontsize=8.0, color=YANG_MID,
             arrowprops=dict(arrowstyle="->", color=YANG_MID, lw=0.8))
axB.text(-9, 0.97, "↓  $n<0$: continues into the MICROCASCADE (panel C)",
         fontsize=8.5, color=YIN_LIGHT, va="top")
axB.text(302, 0.97, "↑  $n>292$: continues into the MEGACASCADE (panel A)",
         fontsize=8.5, color=YANG_BRIGHT, va="top", ha="right")
axB.text(146, 0.97,
         "$\\ell_n = \\ell_{\\rm Pl}\\,\\varphi^{n}$      $n = \\log_\\varphi(\\ell/\\ell_{\\rm Pl})$"
         "      every rung an integer",
         ha="center", va="top", fontsize=9.5, color=TEXT_MAIN)
panel_title(axB, "B · THE CASCADE ($0 \\leq n \\leq 292$)—our universe, rung by rung")

# ── Panel B zoom: inside the Cassi bubble (triaxial cross-section) ──────────
A_YANG, B_YIN = PHI, 1.0     # axis ratio = freeze-out ratio r → φ (§3.4)
axBi.set_xlim(-2.05, 2.05)
axBi.set_ylim(-1.82, 1.62)
axBi.set_aspect("equal")
axBi.set_xticks([]); axBi.set_yticks([])
for s in axBi.spines.values():
    s.set_visible(False)

LAM_HALF = 0.34                       # λ/2 in units of the Yin semi-axis
K = np.pi / LAM_HALF
yy, xx = np.mgrid[-1:1:600j, -PHI:PHI:900j]
I = 2 * (1 - np.cos(K * yy)) + 0.8 * (1 - np.cos(K * yy / PHI))
inside = (xx / A_YANG) ** 2 + (yy / B_YIN) ** 2 <= 1.0
I = np.where(inside, I, np.nan)
axBi.imshow(I, extent=(-PHI, PHI, -1, 1), origin="lower", cmap=GOLDMAP,
            vmin=0, vmax=3.2, interpolation="bilinear", zorder=2)
axBi.add_patch(Ellipse((0, 0), 2 * A_YANG, 2 * B_YIN, fill=False,
                       edgecolor=YANG_BRIGHT, lw=2.2, zorder=4))
# sheet planes clipped to the elliptical envelope
x_mid = A_YANG
axBi.plot([-x_mid, x_mid], [0, 0], color=YIN_LIGHT, lw=1.1, ls=(0, (4, 3)), zorder=5)
for s_ in (+LAM_HALF, -LAM_HALF):
    x_clip = A_YANG * np.sqrt(1 - s_ ** 2)
    axBi.plot([-x_clip, x_clip], [s_, s_], color=YANG_PEAK, lw=1.2,
              ls=(0, (5, 3)), alpha=0.9, zorder=5)
axBi.text(0, 0.045, "central void (node)", ha="center", fontsize=7.5,
          color=TEXT_MAIN, zorder=6)
axBi.text(0, LAM_HALF + 0.05, "paired sheet ($+\\lambda/2$)", ha="center",
          fontsize=7.5, color=DARK_ON_GOLD, fontweight="bold", zorder=6)
axBi.text(0, -LAM_HALF - 0.14, "paired sheet ($-\\lambda/2$)", ha="center",
          fontsize=7.5, color=DARK_ON_GOLD, fontweight="bold", zorder=6)
axBi.contour(xx, yy, np.nan_to_num(I), levels=[1.6],
             colors=[TEXT_SUB], linewidths=0.6, zorder=5)
axBi.text(0, -1.70, "faint contour: condensation threshold $\\theta_{\\rm cond}$",
          fontsize=7.0, color=TEXT_SUB, ha="center")
axBi.annotate("", xy=(A_YANG + 0.22, -1.26), xytext=(-A_YANG - 0.22, -1.26),
              arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.2))
axBi.text(0, -1.42, "Yang axis—extended ($\\times\\varphi$)", ha="center",
          fontsize=8.0, color=TEXT_MAIN)
axBi.annotate("", xy=(0, B_YIN + 0.16), xytext=(0, -B_YIN - 0.16),
              arrowprops=dict(arrowstyle="<|-|>", color=TEXT_SUB, lw=1.1))
axBi.text(0.09, B_YIN + 0.24, "Yin axis—contracted ($\\times 1$)", fontsize=8.0,
          color=TEXT_SUB)
axBi.plot([-1.72], [1.24], marker="o", ms=7, mfc="none", mec=TEXT_SUB, mew=1.3)
axBi.plot([-1.72], [1.24], marker="x", ms=4.5, mec=TEXT_SUB, mew=1.2)
axBi.text(-1.58, 1.24, "string axis $\\perp$ page", fontsize=7.5,
          color=TEXT_SUB, va="center")
axBi.text(0, 1.50,
          "$I(\\Delta r) = 2[1-\\cos(k\\,\\Delta r)]$,  $\\Delta\\phi=\\pi$  ·  axis ratio $\\varphi:1$",
          ha="center", fontsize=8.0, color=TEXT_MAIN, style="italic")
panel_title(axBi, "B (zoom) · INSIDE THE BUBBLE")

# ═════════════════════════════════════════════════════════════════════════════
# PANEL C—THE MICROCASCADE (n < 0)
# ═════════════════════════════════════════════════════════════════════════════

# ── C1: the golden spiral down—r(θ) = ℓ_Pl · φ^(−2θ/π) ─────────────────────
axC1.set_xlim(-1.12, 1.12)
axC1.set_ylim(-1.12, 1.12)
axC1.set_aspect("equal")
axC1.set_xticks([]); axC1.set_yticks([])
for s in axC1.spines.values():
    s.set_visible(False)

TH_MAX = 7 * np.pi                    # 14 quarter-turns = 14 rungs of depth
th = np.linspace(0, TH_MAX, 2100)
r = PHI ** (-2 * th / np.pi)          # contracts by φ every quarter-turn
xs, ys = r * np.cos(th), r * np.sin(th)
for i in range(0, len(th) - 3, 3):
    depth = th[i] / TH_MAX            # 0 at Planck → 1 at depth
    axC1.plot(xs[i:i + 5], ys[i:i + 5],
              color=lerp(YANG_PEAK, YIN_DEEP, depth ** 0.7),
              lw=2.4, solid_capstyle="round", zorder=3)

# Rung markers at integer n (θ = |n|·π/2, r = φ^n); labels hand-placed
rung_labels = {-1: (-0.62, 0.86), -5: (-0.42, 0.30), -10: (-0.62, -0.30)}
for n in range(-1, -15, -1):
    tn = abs(n) * np.pi / 2
    rn = PHI ** n
    xn, yn = rn * np.cos(tn), rn * np.sin(tn)
    axC1.plot([xn], [yn], marker="o", ms=3.5, color=YANG_PEAK, zorder=4)
    if n in rung_labels:
        axC1.annotate(f"$n={n}$:  $\\ell/\\ell_{{\\rm Pl}}=\\varphi^{{{n}}}={float(PHI**n):.3g}$",
                      xy=(xn, yn), xytext=rung_labels[n],
                      fontsize=7.5, color=TEXT_MAIN,
                      arrowprops=dict(arrowstyle="-", color=TEXT_SUB, lw=0.6))

# Entry (Planck) and the unreachable center
axC1.plot([1], [0], marker="o", ms=7, mfc=BG, mec=YANG_PEAK, mew=1.8, zorder=5)
axC1.annotate("n = 0 · Planck membrane—entry\n(σ-softened crossover, not a wall)",
              xy=(1, 0), xytext=(0.42, 0.68), fontsize=8.0, color=YANG_PEAK,
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=0.9))
axC1.plot([0], [0], marker="o", ms=5, color=YIN_LIGHT, zorder=5)
axC1.annotate("$\\ell \\to 0$—never reached:\ninfinitely many turns inside  ($n \\to -\\infty$)",
              xy=(0, 0), xytext=(-1.08, -0.55), fontsize=8.0, color=YIN_LIGHT,
              arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=0.9))
axC1.text(0, -1.08,
          "$r(\\theta) = \\ell_{\\rm Pl}\\,\\varphi^{-2\\theta/\\pi}$"
          " —contracts by $\\varphi$ every quarter-turn",
          ha="center", fontsize=9.0, color=TEXT_MAIN)
panel_title(axC1, "C · THE MICROCASCADE ($n<0$)—the golden spiral")

# ── C2: geometric convergence—no floor ──────────────────────────────────────
depth = np.arange(0, 41)
ratio = PHI ** (-depth.astype(float))
axC2.semilogy(depth, ratio, color=YANG_PEAK, lw=2.2, zorder=3,
              label="$\\ell_n/\\ell_{\\rm Pl} = \\varphi^{-|n|}$  (exact)")
axC2.plot(depth, ratio, "o", ms=3, color=YANG_BRIGHT, zorder=4)
axC2.set_xlim(0, 40)
axC2.set_ylim(1e-9, 2.0)
axC2.set_xlabel("depth below the Planck scale  $|n|$", fontsize=10, color=TEXT_SUB)
axC2.set_ylabel("$\\ell_n / \\ell_{\\rm Pl}$", fontsize=10, color=TEXT_SUB)
axC2.tick_params(labelsize=8.5)
axC2.grid(True, which="major", color=RING, lw=0.4, alpha=0.5)
for s in ("top",):
        axC2.spines[s].set_visible(False)

# Coherence ansatz on a twin axis: (1−q_n) → 1 with depth
axC2b = axC2.twinx()
axC2b.plot(depth, coherence_factor(depth), color=YIN_LIGHT, lw=1.6,
           ls=(0, (5, 3)), label="$(1-q_n) \\to 1$  (proposed ansatz, §3.2)")
axC2b.set_ylim(0.75, 1.005)
axC2b.set_ylabel("per-rung coherence  $1-q_n$", fontsize=9, color=YIN_LIGHT)
axC2b.tick_params(axis="y", labelsize=8, colors=YIN_LIGHT)
axC2b.spines["right"].set_color(YIN_LIGHT)
axC2b.spines["top"].set_visible(False)

# Annotations
axC2.annotate("straight on semilog = exact geometric convergence\n"
              "— a floor would bend this line",
              xy=(20, PHI ** -20), xytext=(8.5, 3e-6), fontsize=8.0, color=YANG_PEAK,
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=0.9))
axC2.annotate("", xy=(39.5, 2.2e-9), xytext=(36, 6e-8),
              arrowprops=dict(arrowstyle="-|>", color=YANG_PEAK, lw=1.4))
axC2.text(39.5, 5e-9, "$n \\to -\\infty$", fontsize=8.5, color=YANG_PEAK, ha="right")
axC2.text(1.2, 1.25,
          "0.618", fontsize=7.5, color=TEXT_MAIN)
axC2.text(10.2, 1.3e-2, "$8×10^{-3}$", fontsize=7.5, color=TEXT_MAIN)
axC2.text(20.2, 1.1e-4, "$6.6×10^{-5}$", fontsize=7.5, color=TEXT_MAIN)
axC2.text(0.5, 4.5e-9,
          "$E_{\\rm micro} = \\sum_{n}(1-q_n) \\to \\infty$ —the infinite reservoir"
          " (formal divergence, §3.3)\nmirror of the megacascade: expansion "
          "$\\ell\\to\\infty$  ↔  contraction $\\ell\\to 0$—one symmetry, $\\ell\\to\\varphi\\ell$",
          fontsize=7.8, color=TEXT_SUB, va="bottom", linespacing=1.5)

# Combined legend
h1, l1 = axC2.get_legend_handles_labels()
h2, l2 = axC2b.get_legend_handles_labels()
axC2.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8, frameon=False,
            labelcolor=TEXT_MAIN)
panel_title(axC2, "C · GEOMETRIC CONVERGENCE—no floor")

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
fig.text(0.5, 0.016,
         "Cassi two-fluid framework · sources: foundations/dimensionful-cascade.md,"
         " foundations/why-three-dimensions.md, foundations/microcascade-mirror.md"
         " · every shape computed from the equation shown on its panel",
         ha="center", fontsize=8, color=TEXT_SUB)

OUT = "visual-explainers/cascade_cosmos.png"
fig.savefig(OUT, dpi=170, facecolor=BG)
print(f"wrote {OUT}")

# Console verification of the math used in the figure
print("\ncascade spot-checks (ℓ_n = ℓ_Pl · φⁿ):")
for n, expect in [(0, 1.616e-35), (95, 1.1e-15), (117, 5.3e-11),
                  (168, 1.7), (285, 5.9e24), (292, 1.7e26), (-50, 5.7e-46)]:
    print(f"  n={n:>4}: {float(ell(n)):.3e} m   (doc: {expect:.1e})")
print(f"\nmicrocascade ansatz: (1−q_0⁻) = {coherence_factor(0):.3f}"
      f"  (doc: 1−0.191 = 0.809)")
