#!/usr/bin/env python3
"""
The Cosmic Cascade: Six Pieces, One Universe
=============================================

14-panel visual explainer showing how six fundamental pieces assemble
into everything we observe. Each panel introduces one piece or shows
what emerges when they interact.

Panels:
  1 · THE CONSTANT          φ—the maximally irrational number
  2 · THE TWO COMPONENTS    r(x,t) is the master variable
  3 · THE SCALE LADDER      ℓ_n = ℓ_Pl × φ^n—all 292 rungs
  4 · THE MICROCASCADE      n < 0—infinite descent
  5 · THE PLANCK MEMBRANE   n = 0—where gravity becomes soft
  6 · THE GATE              r = 1/φ—the self-referential threshold
  7 · STANDING WAVES        particles, mass, quantum mechanics emerge
  8 · THE BUBBLE            w = 5—the universe's structural atom
  9 · THE CHECKERBOARD      how bubbles arrange—why space is 3D
 10 · VOIDS AND BARRIERS    q = 0—impenetrable, bubbles never merge
 11 · THE CMB AXIS          our neighbor's shadow at 12.2°
 12 · THE COSMIC WEB        interference made visible at large scale
 13 · EQUILIBRIUM FLOW      r → φ is dark energy, w₀ = −0.87
 14 · THE MEGACASCADE       n > 292—self-similar forever

Run:  python visual-explainers/universe_answers.py
Out:  visual-explainers/universe_answers.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Polygon
from matplotlib.colors import LinearSegmentedColormap, to_rgb

# ═══════════════════════════════════════════════════════════════════════════════
# Framework constants
# ═══════════════════════════════════════════════════════════════════════════════
PHI = (1 + np.sqrt(5)) / 2
L_PL = 1.616255e-35
N_HUBBLE = 292
DELTA = 3

def ell(n):
    return L_PL * PHI ** np.asarray(n, dtype=float)

def coherence_factor(depth):
    f = PHI ** (-np.asarray(depth, dtype=float) - DELTA)
    return 1.0 / (1.0 + f)

# ═══════════════════════════════════════════════════════════════════════════════
# House palette
# ═══════════════════════════════════════════════════════════════════════════════
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
AMBER       = "#d4850a"
GREEN_OK    = "#2ecc71"

def lerp(c1, c2, t):
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * np.clip(t, 0, 1))

GOLDMAP = LinearSegmentedColormap.from_list(
    "gold", [BG, YIN_DEEP, YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK])
DIVERGING = LinearSegmentedColormap.from_list(
    "diverge", [YIN_MID, YIN_DEEP, BG, YANG_DARK, YANG_PEAK])

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

# ═══════════════════════════════════════════════════════════════════════════════
# Figure + grid: 14 rows, 24×90 inches
# ═══════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(24, 90), dpi=120)
heights = [1.0, 1.2, 1.8, 1.3, 1.3, 1.4, 1.4, 1.5, 2.0, 1.4, 1.4, 1.8, 1.5, 2.0]
gs = fig.add_gridspec(14, 3, height_ratios=heights,
                      hspace=0.25, wspace=0.15,
                      left=0.04, right=0.97, top=0.985, bottom=0.012)

fig.suptitle("THE COSMIC CASCADE—Six Pieces, One Universe",
             fontsize=28, fontweight="bold", color=YANG_PEAK, y=0.995)
fig.text(0.5, 0.990, "$\\varphi \\approx 1.618$  ·  $\\ell_n = \\ell_{\\rm Pl}\\,\\varphi^{n}$"
         "  ·  292 rungs  ·  $r = 1/\\varphi$—the gate  ·  $w = 5$—the bubble  ·  "
         "checkerboard lattice",
         ha="center", fontsize=10, color=TEXT_SUB)

def panel_title(ax, text):
    ax.set_title(text, loc="left", fontsize=11.5, fontweight="bold",
                 color=YANG_BRIGHT, pad=6)

def eq_text(ax, x, y, text, fontsize=8.0):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=fontsize,
            color=TEXT_MAIN, va="top", ha="left", linespacing=1.3)

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 1—THE CONSTANT
# ═══════════════════════════════════════════════════════════════════════════════
ax1 = fig.add_subplot(gs[0, :])
ax1.set_xlim(-2.5, 2.5); ax1.set_ylim(-1.5, 1.5)
ax1.set_aspect("equal"); ax1.axis("off")

# φ large and centered
ax1.text(0, 0.55, r"$\varphi \approx 1.618$", ha="center", fontsize=42,
         color=YANG_PEAK, fontweight="bold")
ax1.text(0, 0.05, "the maximally irrational number", ha="center", fontsize=14,
         color=TEXT_MAIN, style="italic")
ax1.text(0, -0.30, r"$[1; 1, 1, 1, \ldots]$ —slowest-converging continued fraction",
         ha="center", fontsize=10, color=TEXT_SUB)

# Ghost ladders for other constants
for const, label, xpos, fail_at in [
    (2.0, "2", -1.8, 4), (np.e, "e", -0.9, 6), (np.pi, r"$\pi$", 0.9, 3),
    (1.5, "3/2", 1.8, 2)]:
    # Broken rung lines
    xs_g = np.linspace(xpos - 0.5, xpos + 0.5, 20)
    for i in range(1, 8):
        y_g = -0.7 + i * 0.22
        if i < fail_at:
            ax1.plot([xpos - 0.15, xpos + 0.15], [y_g, y_g],
                     color=lerp(YIN_LIGHT, TEXT_SUB, 0.3), lw=1.2, alpha=0.5)
        elif i == fail_at:
            ax1.plot([xpos - 0.15, xpos + 0.15], [y_g, y_g],
                     color="#cc3333", lw=2.0, alpha=0.8)
            ax1.text(xpos + 0.25, y_g, "resonates", fontsize=6.5, color="#cc3333", va="center")
            # Shattered fragments
            for _ in range(6):
                dx = np.random.uniform(-0.12, 0.12)
                dy = np.random.uniform(-0.04, 0.04)
                ax1.plot([xpos - 0.08 + dx], [y_g + dy], marker=".",
                         ms=2, color="#cc3333", alpha=0.6)
        else:
            break
    ax1.text(xpos, -0.95, label, ha="center", fontsize=10, color=TEXT_SUB)

# φ's infinite stable ladder
for i in range(1, 8):
    y_l = -0.7 + i * 0.22
    ax1.plot([-0.05, 0.05], [y_l, y_l], color=YANG_PEAK, lw=1.8, alpha=0.9)
# Continue upward and downward with arrows
ax1.annotate("", xy=(0, 1.2), xytext=(0, 0.85),
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.5))
ax1.annotate("", xy=(0, -1.25), xytext=(0, -0.7),
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.5))
ax1.text(0.12, -1.32, r"$\infty$", fontsize=11, color=YANG_PEAK, ha="center")
ax1.text(0.12, 1.25, r"$\infty$", fontsize=11, color=YANG_PEAK, ha="center")

eq_text(ax1, 0.02, 0.08,
        r"$\varphi = \frac{1+\sqrt{5}}{2}$     "
        r"$\varphi^{-1} = \varphi - 1$     "
        r"de-resonance: $\varphi$ is maximally irrational")
panel_title(ax1, r"1 · THE CONSTANT—$\varphi$ is the only number that produces stable, non-resonant scale separation")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 2—THE TWO COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════
ax2 = fig.add_subplot(gs[1, :])
ax2.set_xlim(0, 12); ax2.set_ylim(0, 6); ax2.axis("off")

# Two perpendicular wave systems
x_w = np.linspace(0, 12, 300)
y_w = np.linspace(0, 6, 150)
XX, YY = np.meshgrid(x_w, y_w)
# Gold waves moving right, indigo waves moving up
field = (np.sin(XX * 1.8 + 0.3 * YY) + np.cos(YY * 2.5 + 0.2 * XX)) / 2
r_field = np.clip((field + 1) / 2, 0.01, PHI)
# Color by local ratio
rgb = np.zeros((150, 300, 3))
for i in range(150):
    for j in range(300):
        t = np.clip(r_field[i, j] / PHI, 0, 1)
        rgb[i, j] = lerp(YIN_MID, YANG_PEAK, t)
ax2.imshow(rgb, extent=(0, 12, 0, 6), origin="lower", zorder=1)

for i in range(0, 13):
    ax2.axvline(i, color=YANG_BRIGHT, lw=0.3, alpha=0.15, zorder=2)
for j in range(0, 7):
    ax2.axhline(j, color=YIN_LIGHT, lw=0.3, alpha=0.15, zorder=2)

# Perpendicular arrows
ax2.annotate("", xy=(11, 1.5), xytext=(1, 1.5),
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=2.5))
ax2.text(6, 1.85, "component 1—gold", ha="center", fontsize=11, color=YANG_PEAK, fontweight="bold")
ax2.annotate("", xy=(3.5, 5.5), xytext=(3.5, 0.5),
             arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=2.5))
ax2.text(3.5, 5.8, "component 2—indigo", ha="center", fontsize=11, color=YIN_LIGHT, fontweight="bold")

# r annotation
ax2.text(6, 3.0, r"$r(x,t) = \frac{|\psi_1(x,t)|^2}{|\psi_2(x,t)|^2}$",
         ha="center", fontsize=16, color=TEXT_MAIN, fontweight="bold",
         bbox=dict(facecolor=BG, edgecolor=RING, alpha=0.85, pad=8))
ax2.text(6, 2.4, "the master variable—every structure traces back to $r$ at that point",
         ha="center", fontsize=10, color=TEXT_SUB,
         bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=4))

eq_text(ax2, 0.02, 0.05, r"$\partial_t r = \nabla^2 r + \text{coupling}$     "
        r"$r \ll 1$: dense, stable     $r \gg 1$: rapid conversion, expansion     "
        r"attractor: $r \to \varphi$")
panel_title(ax2, "2 · THE TWO COMPONENTS—space has two perpendicular aspects; their local ratio $r$ is the master variable")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 3—THE SCALE LADDER
# ═══════════════════════════════════════════════════════════════════════════════
ax3 = fig.add_subplot(gs[2, :])
ax3.set_xlim(-5, N_HUBBLE + 8); ax3.set_ylim(-0.3, 1.3)
ax3.set_yticks([])
for s in ("top", "right", "left"): ax3.spines[s].set_visible(False)
ax3.tick_params(axis="x", labelsize=8.5)

# Gradient background
grad = np.linspace(0, 1, 500).reshape(1, -1)
cmap_ladder = LinearSegmentedColormap.from_list("ladder", [YIN_MID, "#3a2a52", YANG_DARK, YANG_MID])
ax3.imshow(grad, extent=(0, N_HUBBLE, -0.3, 1.3), aspect="auto",
           cmap=cmap_ladder, alpha=0.25, zorder=0)

# Base line + rungs
BASE = 0.5
ax3.axhline(BASE, color=RING, lw=1.2, zorder=2)
for n in range(0, N_HUBBLE + 1):
    if n % 50 == 0:    h, lw = 0.10, 1.4
    elif n % 10 == 0:  h, lw = 0.065, 1.0
    else:              h, lw = 0.035, 0.6
    ax3.vlines(n, BASE, BASE + h, color=lerp(YIN_LIGHT, YANG_BRIGHT, n / N_HUBBLE),
               lw=lw, alpha=0.85, zorder=3)

# Key landmarks
landmarks = [
    (0,   "n = 0 · Planck\n1.6×10⁻³⁵ m", "below"),
    (80,  "Electroweak\n8×10⁻¹⁹ m", "below"),
    (95,  "Proton / QCD\n1.1×10⁻¹⁵ m", "above"),
    (117, "Bohr radius\n5.3×10⁻¹¹ m", "below"),
    (168, "human · 1.7 m", "below"),
    (267, "Milky Way\n30 kpc", "below"),
    (284, "BAO", "above"),
    (285, "bubble", "above"),
    (292, "Hubble radius\n1.7×10²⁶ m", "below"),
]
for n, label, side in landmarks:
    y_text = 0.80 if side == "above" else 0.20
    y_tick = 0.62 if side == "above" else 0.38
    va = "bottom" if side == "above" else "top"
    ax3.vlines(n, BASE, y_tick, color=TEXT_SUB, lw=0.7, alpha=0.6, zorder=3)
    ax3.plot([n], [BASE], marker="o", ms=3, color=YANG_PEAK, zorder=4)
    ax3.text(n, y_text, label, ha="center", va=va, fontsize=7.5,
             color=TEXT_MAIN, linespacing=1.2)

# Planck membrane highlight
ax3.axvspan(-1, 3, color=YANG_PEAK, alpha=0.12, zorder=1)
ax3.text(1.5, 1.12, "Planck\nmembrane", ha="center", fontsize=8,
         color=YANG_PEAK, fontweight="bold")

# Continuation arrows
ax3.annotate("↓ microcascade (n<0)", xy=(-2, 0.5), xytext=(-2, 0.98),
             fontsize=8.5, color=YIN_LIGHT, ha="center",
             arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=1.0))
ax3.annotate("↑ megacascade (n>292)", xy=(N_HUBBLE + 3, 0.5), xytext=(N_HUBBLE + 3, 0.98),
             fontsize=8.5, color=YANG_BRIGHT, ha="center",
             arrowprops=dict(arrowstyle="->", color=YANG_BRIGHT, lw=1.0))

ax3.text(N_HUBBLE / 2, 1.15, r"$\ell_n = \ell_{\rm Pl}\,\varphi^{n}$     "
         r"$n = \log_\varphi(\ell/\ell_{\rm Pl})$     every rung an integer",
         ha="center", fontsize=10, color=TEXT_MAIN)
ax3.set_xlabel(r"cascade step  $n$   (equal spacing—one rung per factor of $\varphi$)",
               fontsize=9.5, color=TEXT_SUB)
panel_title(ax3, r"3 · THE SCALE LADDER—$\ell_n = \ell_{\rm Pl} \times \varphi^n$, 292 rungs from Planck to today's horizon rung")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 4—THE MICROCASCADE
# ═══════════════════════════════════════════════════════════════════════════════
ax4 = fig.add_subplot(gs[3, 0:2])
ax4.set_xlim(-1.15, 1.15); ax4.set_ylim(-1.15, 1.15)
ax4.set_aspect("equal"); ax4.set_xticks([]); ax4.set_yticks([])
for s in ax4.spines.values(): s.set_visible(False)

TH_MAX = 8 * np.pi
th = np.linspace(0, TH_MAX, 2400)
r = PHI ** (-2 * th / np.pi)
xs, ys = r * np.cos(th), r * np.sin(th)
for i in range(0, len(th) - 3, 3):
    depth = th[i] / TH_MAX
    ax4.plot(xs[i:i + 5], ys[i:i + 5],
             color=lerp(YANG_PEAK, YIN_DEEP, depth ** 0.7), lw=2.2, solid_capstyle="round", zorder=3)

for n in range(-1, -16, -1):
    tn = abs(n) * np.pi / 2
    rn = PHI ** n
    ax4.plot([rn * np.cos(tn)], [rn * np.sin(tn)], marker="o", ms=2.5, color=YANG_PEAK, zorder=4)

ax4.plot([1], [0], marker="o", ms=8, mfc=BG, mec=YANG_PEAK, mew=2, zorder=5)
ax4.annotate("n = 0 · Planck membrane", xy=(1, 0), xytext=(0.45, 0.72),
             fontsize=8.5, color=YANG_PEAK,
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0))
ax4.plot([0], [0], marker="o", ms=5, color=YIN_LIGHT, zorder=5)
ax4.annotate(r"$\ell \to 0$—never reached", xy=(0, 0), xytext=(-1.0, -0.65),
             fontsize=8, color=YIN_LIGHT,
             arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=0.9))
eq_text(ax4, 0.02, 0.05, r"$r(\theta) = \ell_{\rm Pl}\,\varphi^{-2\theta/\pi}$—contracts by $\varphi$ every quarter-turn")
panel_title(ax4, r"4 · THE MICROCASCADE ($n<0$)—the ladder descends forever, each rung $\varphi\times$ smaller")

# Convergence plot (right side)
ax4b = fig.add_subplot(gs[3, 2])
depth = np.arange(0, 41)
ratio = PHI ** (-depth.astype(float))
ax4b.semilogy(depth, ratio, color=YANG_PEAK, lw=2.2, zorder=3)
ax4b.plot(depth, ratio, "o", ms=2.5, color=YANG_BRIGHT, zorder=4)
ax4b.set_xlim(0, 40); ax4b.set_ylim(1e-9, 2)
ax4b.set_xlabel("depth  $|n|$", fontsize=9, color=TEXT_SUB)
ax4b.set_ylabel(r"$\ell_n / \ell_{\rm Pl}$", fontsize=9, color=TEXT_SUB)
ax4b.tick_params(labelsize=7.5)
ax4b.grid(True, which="major", color=RING, lw=0.3, alpha=0.4)
for s in ("top",): ax4b.spines[s].set_visible(False)

ax4b2 = ax4b.twinx()
ax4b2.plot(depth, coherence_factor(depth), color=YIN_LIGHT, lw=1.6, ls=(0, (5, 3)))
ax4b2.set_ylim(0.75, 1.005)
ax4b2.set_ylabel(r"coherence $1-q_n$", fontsize=8.5, color=YIN_LIGHT)
ax4b2.tick_params(axis="y", labelsize=7, colors=YIN_LIGHT)
ax4b2.spines["right"].set_color(YIN_LIGHT)
ax4b2.spines["top"].set_visible(False)
ax4b.annotate("straight = geometric convergence\n— no floor", xy=(20, PHI ** -20),
              xytext=(8, 3e-6), fontsize=7.5, color=YANG_PEAK,
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=0.8))
panel_title(ax4b, "convergence—no floor")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 5—THE PLANCK MEMBRANE
# ═══════════════════════════════════════════════════════════════════════════════
ax5 = fig.add_subplot(gs[4, :])
sigma = 1.0 / PHI ** 3
r = np.logspace(-2, 2, 400)

# Abramowitz-Stegun erf approximation (avoids scipy dependency)
def _erf(x):
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    t = 1.0 / (1.0 + p * np.abs(x))
    y = 1.0 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * np.exp(-x * x)
    return np.sign(x) * y

F_erf = -(1 / r**2) * (_erf(r / (sigma * np.sqrt(2))) - np.sqrt(2 / np.pi) * (r / sigma) * np.exp(-r**2 / (2 * sigma**2)))
ax5.loglog(r, np.abs(F_erf), color=YANG_PEAK, lw=2.5, zorder=3)
ax5.axvline(x=sigma, color=YIN_LIGHT, lw=1.2, ls="--", alpha=0.8)
ax5.text(sigma * 1.2, 5e-3, r"$\sigma = \ell_{\rm Pl}/\varphi^3$",
         fontsize=9, color=YIN_LIGHT, rotation=90, va="bottom")

# Annotation zones
ax5.annotate(r"$F \propto 1/r^2$" + "\n(inverse-square gravity)", xy=(30, 0.001),
             xytext=(50, 0.003), fontsize=9, color=YANG_BRIGHT,
             arrowprops=dict(arrowstyle="->", color=YANG_BRIGHT, lw=1.0))
ax5.annotate(r"$F \propto -r$" + "\n(harmonic core)", xy=(0.5, 0.5),
             xytext=(0.1, 8), fontsize=9, color=YANG_PEAK, fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0))
ax5.annotate(r"$F \to 0$" + "\n(no force at zero)", xy=(0.02, 0.003),
             xytext=(0.005, 0.002), fontsize=9, color=TEXT_SUB,
             arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=0.8))

ax5.set_xlabel(r"distance  $r/\sigma$", fontsize=10, color=TEXT_SUB)
ax5.set_ylabel(r"$|F(r)|$", fontsize=10, color=TEXT_SUB)
ax5.tick_params(labelsize=8)
ax5.grid(True, which="major", color=RING, lw=0.3, alpha=0.4)

eq_text(ax5, 0.65, 0.92,
        r"$F(r) = -\frac{1}{r^2}\left[{\rm erf}\!\left(\frac{r}{\sigma\sqrt{2}}\right)"
        r"- \sqrt{\frac{2}{\pi}}\frac{r}{\sigma}e^{-r^2/2\sigma^2}\right]$"
        r"     $\sigma = \ell_{\rm Pl}/\varphi^3$")
panel_title(ax5, "5 · THE PLANCK MEMBRANE ($n=0$)—where gravity transitions from inverse-square to harmonic to nothing")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 6—THE GATE
# ═══════════════════════════════════════════════════════════════════════════════
ax6 = fig.add_subplot(gs[5, :])
r_gate = np.linspace(0.01, PHI, 400)
q_gate = r_gate**2 / (r_gate**2 + PHI**(-2) + np.abs(r_gate - PHI)**2)
open_gate = 1 - q_gate

ax6.plot(r_gate, open_gate, color=YANG_PEAK, lw=2.8, zorder=3)
ax6.fill_between(r_gate, open_gate, alpha=0.12, color=YANG_PEAK)

# The pinch
pinch_r = 1.0 / PHI
pinch_open = 1 - pinch_r**2 / (pinch_r**2 + PHI**(-2) + (PHI - pinch_r)**2)
ax6.axvline(x=pinch_r, color=YANG_BRIGHT, lw=1.8, ls="--", alpha=0.9)
ax6.plot([pinch_r], [pinch_open], marker="o", ms=12, mfc=BG, mec=YANG_PEAK, mew=2.5, zorder=5)

ax6.annotate(r"$r = 1/\varphi \approx 0.618$" + "\nthe pinch—self-referential threshold",
             xy=(pinch_r, pinch_open), xytext=(pinch_r + 0.3, pinch_open + 0.15),
             fontsize=9.5, color=YANG_PEAK, fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.3))

# Two inset boxes for the two applications
bbox_props = dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor=RING, alpha=0.9)
ax6.text(0.15, 0.78, "←  INFLATION ENDS\n$n \\approx 20$–$60$\n"
         "gate wide open → closes\nat $r=1/\\varphi$\nautomatic, no fine-tuning",
         transform=ax6.transAxes, fontsize=8, color=YANG_BRIGHT,
         bbox=bbox_props, va="top")
ax6.text(0.70, 0.78, "AWARENESS BEGINS  →\n$n \\approx 142$–$168$\n"
         "same threshold, different rung\nfield becomes self-referential\nstructural basis of consciousness",
         transform=ax6.transAxes, fontsize=8, color=YIN_LIGHT,
         bbox=bbox_props, va="top", ha="right")

ax6.set_xlabel(r"local ratio  $r$", fontsize=10, color=TEXT_SUB)
ax6.set_ylabel(r"gate openness  $1-q$", fontsize=10, color=TEXT_SUB)
ax6.set_xlim(0, PHI + 0.05); ax6.set_ylim(-0.02, 0.65)
ax6.tick_params(labelsize=8)

eq_text(ax6, 0.02, 0.06,
        r"$q(r) \approx \frac{r^3}{1+r^3}$     "
        r"$1-q \approx \frac{1}{1+r^3}$     "
        r"$r = 1/\varphi$—the pinch")
panel_title(ax6, r"6 · THE GATE—when $r$ crosses $1/\varphi$, the field becomes self-referential. Same geometry, different scales.")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 7—STANDING WAVES
# ═══════════════════════════════════════════════════════════════════════════════
ax7 = fig.add_subplot(gs[6, :])
ax7.set_xlim(0, 14); ax7.set_ylim(0, 6); ax7.axis("off")

# Standing wave: two wave systems locking
x_s = np.linspace(0, 14, 500)
y_s = np.linspace(0, 6, 200)
XX_s, YY_s = np.meshgrid(x_s, y_s)
# Localized standing wave at center
r2 = (XX_s - 7)**2 / 9 + (YY_s - 3)**2 / 4
envelope = np.exp(-r2 / 0.8)
wave = envelope * (np.sin(XX_s * 2.5) * np.cos(YY_s * 1.8) + np.cos(XX_s * 1.8) * np.sin(YY_s * 2.5))
rgb_s = np.zeros((200, 500, 3))
for i in range(200):
    for j in range(500):
        t_s = np.clip((wave[i, j] + 1) / 2, 0, 1)
        rgb_s[i, j] = lerp(YIN_DEEP, YANG_PEAK, t_s)
ax7.imshow(rgb_s, extent=(0, 14, 0, 6), origin="lower", zorder=1)

# Particle label
ax7.text(7, 4.8, "a particle—trapped standing-wave energy",
         ha="center", fontsize=13, color=YANG_PEAK, fontweight="bold",
         bbox=dict(facecolor=BG, edgecolor=YANG_PEAK, alpha=0.85, pad=6))
ax7.text(7, 4.3, "mass is the energy cost of maintaining the interference pattern",
         ha="center", fontsize=9.5, color=TEXT_MAIN,
         bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=4))

# Mass hierarchy as addresses
for i, (label, rung, mass_ev) in enumerate([
        ("e", 117, 0.511e6), (r"$\mu$", 123, 105.7e6), (r"$\tau$", 128, 1777e6)]):
    y_pos = 1.0 - i * 0.7
    ax7.text(0.5, y_pos, f"{label}: {mass_ev/1e6:.0f} MeV  (rung {rung})",
             fontsize=9, color=TEXT_MAIN,
             bbox=dict(facecolor=BG, edgecolor=RING, alpha=0.8, pad=3))

eq_text(ax7, 0.02, 0.05,
        r"$\psi = \psi_1 + i\psi_2$     "
        r"$a_0 = \ell_{\rm Pl}\,\varphi^{117}$     "
        r"$m \propto \varphi^{-k}$—mass as geometric address")
panel_title(ax7, "7 · STANDING WAVES—when the two components lock into stable interference, you get a particle. Mass is trapped standing-wave energy.")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 8—THE BUBBLE
# ═══════════════════════════════════════════════════════════════════════════════
ax8 = fig.add_subplot(gs[7, 0:2])
ax8.set_xlim(-2.8, 2.8); ax8.set_ylim(-2.4, 2.4)
ax8.set_aspect("equal"); ax8.set_xticks([]); ax8.set_yticks([])
for s in ax8.spines.values(): s.set_visible(False)

# Pentagon vertices
angles = np.linspace(np.pi/2, np.pi/2 + 2*np.pi, 6)
pent_x = 2.0 * np.cos(angles)
pent_y = 2.0 * np.sin(angles)

# Interference inside bubble—approximate with field
yy8, xx8 = np.mgrid[-2.4:2.4:400j, -2.8:2.8:500j]
# Check if inside pentagon
from matplotlib.path import Path
pent_path = Path(np.column_stack([pent_x, pent_y]))
pts = np.column_stack([xx8.ravel(), yy8.ravel()])
inside_8 = pent_path.contains_points(pts).reshape(xx8.shape)

I8 = np.where(inside_8,
              np.sin(xx8 * 2.5)**2 * np.cos(yy8 * 1.8)**2 + 0.3,
              np.nan)
ax8.imshow(I8, extent=(-2.8, 2.8, -2.4, 2.4), origin="lower",
           cmap=GOLDMAP, vmin=0, vmax=2.5, interpolation="bilinear", zorder=2)

# Pentagon outline
ax8.add_patch(Polygon(np.column_stack([pent_x, pent_y]), fill=False,
                      edgecolor=YANG_PEAK, lw=3.0, zorder=4))

# Vertex labels
for i in range(5):
    ax8.plot([pent_x[i]], [pent_y[i]], marker="o", ms=7, mfc=BG, mec=YANG_PEAK, mew=2, zorder=5)
ax8.text(0, 2.25, r"$w = 5$", ha="center", fontsize=16, color=YANG_PEAK, fontweight="bold")

# Failed configurations
for w_fail, cx, cy, color in [(3, -2.0, -1.6, YIN_MID), (4, 0, -1.6, YIN_MID),
                                (6, -1.0, -1.2, YIN_MID), (7, 1.0, -1.2, YIN_MID)]:
    af = np.linspace(np.pi/2, np.pi/2 + 2*np.pi, w_fail + 1)
    fx = cx + 0.6 * np.cos(af); fy = cy + 0.6 * np.sin(af)
    ax8.plot(fx, fy, color=color, lw=1.0, alpha=0.5, ls="--")
    ax8.text(cx, cy - 0.9, f"w={w_fail}", ha="center", fontsize=7, color=color, alpha=0.5)
    # X mark through failed
    ax8.plot([cx-0.35, cx+0.35], [cy, cy], color="#cc3333", lw=1.0, alpha=0.4)

ax8.text(-1.5, -2.1, r"$g = 1 - \varphi^{-5}$—the gap that stabilizes $w=5$",
         ha="center", fontsize=9, color=TEXT_MAIN)
eq_text(ax8, 0.02, 0.05,
        r"$w = 5$     $g = 1 - \varphi^{-5}$     "
        r"$\lambda_1 = \ell_{\rm bubble},\; \lambda_2 = \ell_{\rm bubble}/\varphi$")
panel_title(ax8, "8 · THE BUBBLE—the universe's structural atom. Only five sides work. $w=5$, or nothing.")

# Right: bubble cross-section equation
ax8b = fig.add_subplot(gs[7, 2])
ax8b.set_xlim(-2, 2); ax8b.set_ylim(-2.5, 2.5)
ax8b.set_aspect("equal"); ax8b.set_xticks([]); ax8b.set_yticks([])
for s in ax8b.spines.values(): s.set_visible(False)

# Elliptical bubble cross-section with axis ratio φ
ellipse = Ellipse((0, 0), 3.2, 2.0, fill=False, edgecolor=YANG_BRIGHT, lw=2.2, zorder=3)
ax8b.add_patch(ellipse)
# φ:1 axes
ax8b.annotate("", xy=(1.6, 0), xytext=(-1.6, 0),
              arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.2))
ax8b.text(0, 0.25, r"$\varphi : 1$ axis ratio", ha="center", fontsize=9, color=TEXT_MAIN)
ax8b.annotate("", xy=(0, 1.0), xytext=(0, -1.0),
              arrowprops=dict(arrowstyle="<|-|>", color=TEXT_SUB, lw=1.0))
ax8b.text(0.15, 1.1, "1", fontsize=9, color=TEXT_SUB, ha="center")
# Axis labels
ax8b.text(1.7, -0.15, "Yang", fontsize=9, color=YANG_BRIGHT, ha="center")
ax8b.text(0.2, -1.9, "Yin", fontsize=9, color=TEXT_SUB, ha="center")
eq_text(ax8b, 0.02, 0.05, "triaxial spheroid\naxis ratio $\\varphi:1$")
panel_title(ax8b, "cross-section")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 9—CHECKERBOARD LATTICE
# ═══════════════════════════════════════════════════════════════════════════════
ax9 = fig.add_subplot(gs[8, :])
LAM_I9 = 2.0; LAM_Y9 = PHI * LAM_I9
ALPHA9 = 2 * np.pi / LAM_Y9; BETA9 = 2 * np.pi / LAM_I9
X09, X19 = -6.5, 6.5; Y09, Y19 = -2.3, 2.3

x9 = np.linspace(X09, X19, 1000)
y9 = np.linspace(Y09, Y19, 400)
XX9, YY9 = np.meshgrid(x9, y9)
C9 = np.cos(ALPHA9 * XX9) * np.cos(BETA9 * YY9)

ax9.imshow(C9, extent=(X09, X19, Y09, Y19), origin="lower", cmap=DIVERGING,
           vmin=-1, vmax=1, interpolation="bilinear", zorder=1)
ax9.contour(XX9, YY9, C9, levels=[0.45], colors=[YANG_PEAK], linewidths=1.5, zorder=3)

# Our bubble highlight
mask9 = (np.abs(XX9) < 1.1) & (np.abs(YY9) < 0.7)
ax9.contour(XX9, YY9, np.where(mask9, C9, np.nan), levels=[0.45],
            colors=[YANG_PEAK], linewidths=3.5, zorder=4)

# Site markers
m_max9 = int(X19 / (LAM_Y9 / 2)) + 1
n_max9 = int(Y19 / (LAM_I9 / 2)) + 1
for m in range(-m_max9, m_max9 + 1):
    for n in range(-n_max9, n_max9 + 1):
        sx, sy = m * LAM_Y9 / 2, n * LAM_I9 / 2
        if not (X09 < sx < X19 and Y09 < sy < Y19): continue
        if (m + n) % 2 == 0:
            ax9.plot([sx], [sy], marker="o", ms=4, mfc="none", mec=TEXT_MAIN, mew=0.7, zorder=5, alpha=0.8)
        else:
            ax9.plot([sx], [sy], marker="x", ms=3, mec=YIN_LIGHT, mew=0.8, zorder=5, alpha=0.7)

# Our bubble label
ax9.annotate("OUR BUBBLE", xy=(0.55, 0.25), xytext=(2.0, -1.65),
             fontsize=9, color=YANG_PEAK, fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0),
             bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))

# Dimension labels
ax9.annotate("", xy=(LAM_Y9, 0.4), xytext=(0, 0.4),
             arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.0))
ax9.text(LAM_Y9 / 2, 0.4, r"$\Lambda_Y$", fontsize=8, color=TEXT_MAIN, ha="center", va="center",
         bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=1))
ax9.annotate("", xy=(-LAM_Y9, 0.8), xytext=(-LAM_Y9, 0),
             arrowprops=dict(arrowstyle="<|-|>", color=TEXT_MAIN, lw=1.0))
ax9.text(-LAM_Y9 - 0.1, 0.4, r"$\Lambda_I/2$", fontsize=8, color=TEXT_MAIN, ha="right", va="center",
         bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=1))

ax9.set_xlim(X09, X19); ax9.set_ylim(Y09, Y19); ax9.set_aspect("equal")
ax9.set_xticks([]); ax9.set_yticks([])
for s in ax9.spines.values(): s.set_visible(False)

eq_text(ax9, 0.02, 0.05,
        r"$C(x,y) = \cos(2\pi x/\Lambda_Y)\,\cos(2\pi y/\Lambda_I)$     "
        r"$\Lambda_I = \Lambda_Y/\varphi$     "
        r"$\text{Three dimensions} = \text{Frenet-Serret frame: } \mathbf{T}, \mathbf{N}, \mathbf{B}$")
panel_title(ax9, "9 · THE CHECKERBOARD LATTICE—bubbles arrange in a staggered grid. Three dimensions from the spiral's Frenet-Serret frame: tangent (string axis), normal (Yang), binormal (Yin).")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 10—VOIDS AND BARRIERS
# ═══════════════════════════════════════════════════════════════════════════════
ax10 = fig.add_subplot(gs[9, :])
x10 = np.linspace(-4, 4, 500)
y10 = np.linspace(-1.5, 1.5, 200)
XX10, YY10 = np.meshgrid(x10, y10)
C10 = np.cos(2 * np.pi * XX10 / (PHI * 2)) * np.cos(2 * np.pi * YY10 / 2)

# Surface plot via imshow with contours
ax10.imshow(C10, extent=(-4, 4, -1.5, 1.5), origin="lower", cmap=DIVERGING,
            vmin=-1, vmax=1, interpolation="bilinear", zorder=1)
# Deep troughs (axial voids) and shallow saddles (diagonal)
cs_void = ax10.contour(XX10, YY10, C10, levels=[-0.95], colors=[YIN_LIGHT],
                        linewidths=2.0, zorder=3)
cs_saddle = ax10.contour(XX10, YY10, C10, levels=[0.0], colors=[YANG_MID],
                          linewidths=1.2, ls="--", alpha=0.7, zorder=3)

# Annotations
ax10.annotate("axial void\n$C = -1$\n$q = 0$—impenetrable", xy=(-PHI, 0),
              xytext=(-3.5, 0.8), fontsize=8.5, color=YIN_LIGHT, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=1.0),
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=3))
ax10.annotate("diagonal saddle\n$C = 0$\nweaker, but still no merger", xy=(PHI/2, 0.5),
              xytext=(1.8, 1.0), fontsize=8.5, color=YANG_MID,
              arrowprops=dict(arrowstyle="->", color=YANG_MID, lw=1.0),
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=3))
ax10.annotate("edge 1.70× steeper\ntoward void", xy=(-0.8, -0.7),
              xytext=(-1.5, -1.2), fontsize=7.5, color=TEXT_SUB,
              arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=0.8))

ax10.set_xticks([]); ax10.set_yticks([])
for s in ax10.spines.values(): s.set_visible(False)

eq_text(ax10, 0.02, 0.05,
        r"$C(x,y) = \cos(2\pi x/\Lambda_Y)\,\cos(2\pi y/\Lambda_I)$     "
        r"$C_{\rm axial} = -1\;(q=0)$     $C_{\rm diag} = 0$     "
        r"$\nabla C_{\rm void}/\nabla C_{\rm neighbor} = \sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$")
panel_title(ax10, "10 · VOIDS AND BARRIERS—the space between bubbles. $C=-1$ is absolute void ($q=0$). Nothing crosses. Bubbles never merge.")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 11—THE CMB AXIS
# ═══════════════════════════════════════════════════════════════════════════════
ax11 = fig.add_subplot(gs[10, 0:2])
ax11.set_xlim(-1.3, 1.3); ax11.set_ylim(-0.75, 0.75)
ax11.set_aspect("equal"); ax11.set_xticks([]); ax11.set_yticks([])
for s in ax11.spines.values(): s.set_visible(False)

# Simplified Mollweide projection—oval sky
theta = np.linspace(0, 2*np.pi, 300)
sky_x = 1.0 * np.cos(theta)
sky_y = 0.55 * np.sin(theta)
ax11.fill(sky_x, sky_y, facecolor=YIN_DEEP, edgecolor=RING, lw=1.5, alpha=0.7, zorder=1)

# CMB texture—random noise with large-scale structure
np.random.seed(42)
noise = np.random.randn(80, 140) * 0.3
# Add a quadrupole pattern
qx, qy = np.meshgrid(np.linspace(-1, 1, 140), np.linspace(-0.55, 0.55, 80))
quadrupole = 0.6 * (qx**2 - qy**2)
inside_sky = (qx**2 / 1.0**2 + qy**2 / 0.55**2) <= 1.0
cmb_field = np.where(inside_sky, noise + quadrupole, np.nan)
ax11.imshow(cmb_field, extent=(-1, 1, -0.55, 0.55), origin="lower",
            cmap=LinearSegmentedColormap.from_list("cmb", [YIN_MID, YANG_DARK, YANG_MID, YANG_PEAK]),
            vmin=-0.8, vmax=0.8, interpolation="bilinear", zorder=2)

# Re-draw sky outline
ax11.plot(sky_x, sky_y, color=RING, lw=1.5, zorder=3)

# Dipole arrow (motion direction)
dipole_angle = np.radians(30)
ax11.annotate("", xy=(0.5 * np.cos(dipole_angle), 0.5 * 0.55 * np.sin(dipole_angle)),
              xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=2.5))
ax11.text(0.55 * np.cos(dipole_angle), 0.55 * 0.55 * np.sin(dipole_angle),
          "dipole\n(motion)", fontsize=8, color=YANG_PEAK, fontweight="bold", ha="center")

# Quadrupole-octopole axis at 12.2° from dipole
qo_angle = dipole_angle + np.radians(12.2)
ax11.annotate("", xy=(0.7 * np.cos(qo_angle), 0.7 * 0.55 * np.sin(qo_angle)),
              xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=2.0, ls="--"))
ax11.text(0.75 * np.cos(qo_angle), 0.75 * 0.55 * np.sin(qo_angle),
          "quadrupole-\noctopole axis", fontsize=8, color=YIN_LIGHT, fontweight="bold", ha="center")

# Angle arc
arc_r = 0.25
arc_th = np.linspace(dipole_angle, qo_angle, 30)
ax11.plot(arc_r * np.cos(arc_th), arc_r * 0.55 * np.sin(arc_th), color=YANG_BRIGHT, lw=1.5)
ax11.text(arc_r * 0.7 * np.cos((dipole_angle + qo_angle) / 2),
          arc_r * 0.7 * 0.55 * np.sin((dipole_angle + qo_angle) / 2),
          r"$12.2^\circ$", fontsize=9, color=YANG_BRIGHT, fontweight="bold", ha="center")

eq_text(ax11, 0.02, 0.05, r"$\theta_{\rm align} = 12.2^\circ$     "
        r"triaxial spheroid geometry     our neighbor's shadow")
panel_title(ax11, "11 · THE CMB AXIS—our neighbor bubble imprints a preferred direction. The quadrupole-octopole axis sits at 12.2° from the dipole.")

# Right: triaxial spheroid inset
ax11b = fig.add_subplot(gs[10, 2])
ax11b.set_xlim(-2, 2); ax11b.set_ylim(-2, 2)
ax11b.set_aspect("equal"); ax11b.set_xticks([]); ax11b.set_yticks([])
for s in ax11b.spines.values(): s.set_visible(False)

# Triaxial spheroid: ellipse with different axes

e11 = Ellipse((0, 0), 3.2, 2.0, fill=False, edgecolor=YANG_BRIGHT, lw=2.0, zorder=3)
ax11b.add_patch(e11)
# Dipole arrow
ax11b.annotate("", xy=(1.4, 0.5), xytext=(0, 0),
               arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=2.2))
ax11b.text(1.8, 0.6, "dipole", fontsize=8, color=YANG_PEAK)
# Boundary normal
ax11b.annotate("", xy=(-0.4, 1.0), xytext=(0, 0),
               arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=1.8, ls="--"))
ax11b.text(-0.6, 1.2, "boundary\nnormal", fontsize=8, color=YIN_LIGHT)
ax11b.text(0, -1.8, r"$\varphi$", fontsize=10, color=YANG_BRIGHT, ha="center")
ax11b.text(1.9, -0.1, "1", fontsize=10, color=TEXT_SUB, ha="center", va="center")
eq_text(ax11b, 0.02, 0.05, r"triaxial spheroid\n$\ell_{285} \approx 191$ Mpc")
panel_title(ax11b, "bubble geometry")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 12—THE COSMIC WEB
# ═══════════════════════════════════════════════════════════════════════════════
ax12 = fig.add_subplot(gs[11, :])
x12 = np.linspace(0, 16, 600)
y12 = np.linspace(0, 8, 300)
XX12, YY12 = np.meshgrid(x12, y12)
# Anti-phase interference
I12 = 2 * (1 - np.cos(2 * np.pi * XX12 / (PHI * 2))) * (1 - np.cos(2 * np.pi * YY12 / 2))
I12 = np.log(np.clip(I12, 0.01, 10))

ax12.imshow(I12, extent=(0, 16, 0, 8), origin="lower", cmap=GOLDMAP,
            vmin=0, vmax=3.5, interpolation="bilinear", zorder=1)

# Paired sheet markers
for i in range(0, 9):
    x_pos = i * PHI
    ax12.axvline(x_pos, color=YANG_PEAK, lw=0.8, alpha=0.4, ls="--", zorder=2)
    ax12.axvline(x_pos + PHI/2, color=YIN_LIGHT, lw=0.5, alpha=0.3, ls=":", zorder=2)

ax12.annotate("paired sheets—anti-phase coupling\n(Δφ = π, W1 confirmed)",
              xy=(PHI * 2, 5.5), xytext=(PHI * 3.5, 6.5), fontsize=8.5, color=YANG_PEAK,
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0),
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=3))
ax12.annotate(r"$\Delta(\ln k) = \ln\varphi \approx 0.4812$" + "\nlog-periodic P(k) signal",
              xy=(PHI * 0.5, 1.5), xytext=(2.5, 0.8), fontsize=8.5, color=YANG_BRIGHT,
              arrowprops=dict(arrowstyle="->", color=YANG_BRIGHT, lw=1.0),
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=3))

ax12.set_xticks([]); ax12.set_yticks([])
for s in ax12.spines.values(): s.set_visible(False)

eq_text(ax12, 0.02, 0.05,
        r"$I(\Delta r) = 2[1 - \cos(k\,\Delta r)]$  $(\Delta\phi = \pi)$     "
        r"$\Delta(\ln k) = \ln\varphi \approx 0.4812$     "
        r"BAO at rung 284, bubble at rung 285")
panel_title(ax12, "12 · THE COSMIC WEB—the interference pattern at large scale. Paired sheets, φ-spaced voids, log-periodic signal. The web IS the interference.")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 13—EQUILIBRIUM FLOW
# ═══════════════════════════════════════════════════════════════════════════════
ax13 = fig.add_subplot(gs[12, :])
# r(t) approaching φ
a_arr = np.linspace(0.01, 1.0, 300)
z = 1/a_arr - 1  # redshift-like
r_t = PHI - (PHI - 0.3) * a_arr**0.6  # toy evolution toward φ

ax13.plot(a_arr, r_t, color=YANG_PEAK, lw=3.0, zorder=3)
ax13.axhline(y=PHI, color=YANG_BRIGHT, lw=1.5, ls="--", alpha=0.8)
ax13.text(0.85, PHI + 0.02, r"$r = \varphi$—attractor", fontsize=9,
          color=YANG_BRIGHT, va="bottom")
ax13.annotate("today\n$w_0 = -0.87$", xy=(0.33, r_t[100]), xytext=(0.12, r_t[100] + 0.05),
              fontsize=9, color=YANG_PEAK, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.0))
ax13.fill_between(a_arr, r_t, PHI, alpha=0.12, color=YANG_PEAK)

# DESI DR2 anchor (≈ −0.75 ± 0.06 [INFERENCE]); the former w₀ target was the
# repo's own calibration value (circular) — retargeted to −0.87
# (calibration target, not a prediction; synced to doctrine settlement 2026-08-03)
ax13.errorbar([0.33], [PHI - 0.02], yerr=0.008, fmt="o", ms=8,
              color=YANG_BRIGHT, capsize=4, zorder=5)
ax13.annotate("DESI DR2\n$w_0 \\approx -0.75 \\pm 0.06$", xy=(0.33, PHI - 0.02),
              xytext=(0.5, PHI - 0.08), fontsize=8.5, color=YANG_BRIGHT,
              arrowprops=dict(arrowstyle="->", color=YANG_BRIGHT, lw=0.8))

ax13.set_xlabel("scale factor  $a$", fontsize=10, color=TEXT_SUB)
ax13.set_ylabel(r"local ratio  $r$", fontsize=10, color=TEXT_SUB)
ax13.set_xlim(0, 1.05); ax13.set_ylim(0.25, PHI + 0.1)
ax13.tick_params(labelsize=8)

eq_text(ax13, 0.65, 0.92,
        r"$w_0 = -0.87$     $w_a = +0.012$     "
        r"$H_{\rm empty} = \lambda\varphi^{-2}/3$     "
        r"$r \to \varphi$—the attractor")
panel_title(ax13, r"13 · EQUILIBRIUM FLOW—everything drifts toward $r = \varphi$. The residual energy pushes space outward—that's dark energy. $w_0 = -0.87$ (corrected 2026-07-31).")

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 14—THE MEGACASCADE
# ═══════════════════════════════════════════════════════════════════════════════
ax14 = fig.add_subplot(gs[13, :])
AX0, AX1 = 282, 310
BUB_H14 = 1.6; BUB_W14 = 4.0; CHAIN_PERIOD = 7; N_CENTER = 286

ax14.set_xlim(AX0, AX1); ax14.set_ylim(-3.0, 3.2)
ax14.set_yticks([])
for s in ("top", "right", "left"): ax14.spines[s].set_visible(False)
ax14.tick_params(axis="x", labelsize=8.5)

# Gradient background
grad14 = np.linspace(0, 1, 300).reshape(1, -1)
ax14.imshow(grad14, extent=(AX0, AX1, -3.0, 3.2), aspect="auto",
            cmap=LinearSegmentedColormap.from_list("mega", [YIN_DEEP, YANG_DARK]), alpha=0.2, zorder=0)

# String
xs14 = np.linspace(AX0, AX1, 400)
ys14 = 0.08 * np.sin(2 * np.pi * (xs14 - N_CENTER) / CHAIN_PERIOD)
for i in range(0, len(xs14) - 1, 2):
    t14 = (xs14[i] - AX0) / (AX1 - AX0)
    ax14.plot(xs14[i:i + 3], ys14[i:i + 3], color=lerp(YIN_LIGHT, YANG_BRIGHT, t14),
              lw=2.4, solid_capstyle="round", zorder=3)

# Wake crests
for n in range(AX0, AX1 + 1):
    ax14.vlines(n, -0.12, 0.12, color=TEXT_SUB, lw=0.4, alpha=0.35, zorder=2)

# Bubble chain
SHEET_FRAC = 0.34
for k in range(-1, 4):
    cx = N_CENTER + CHAIN_PERIOD * k
    ours = (k == 0)
    w_num = 5
    fade = max(0.30, 1.0 - 0.18 * abs(k))
    if ours:
        face, edge, ea, lw = YANG_DARK, YANG_PEAK, 0.55, 2.8
    else:
        face, edge, ea, lw = YIN_MID, lerp(RING, YIN_LIGHT, 0.4), 0.35 * fade, 1.3
    ax14.add_patch(Ellipse((cx, 0), width=BUB_W14, height=2 * BUB_H14,
                           facecolor=face, edgecolor=edge, alpha=ea, lw=lw, zorder=4))
    # Paired sheets
    sy = SHEET_FRAC * BUB_H14
    for s_ in (+sy, -sy):
        ax14.plot([cx - 1.5, cx + 1.5], [s_, s_],
                  color=YANG_PEAK if ours else lerp(YANG_MID, YIN_LIGHT, 0.5),
                  lw=4.5 if ours else 2.0, alpha=0.9 if ours else 0.35 * fade,
                  solid_capstyle="round", zorder=6)
    # Central void
    ax14.plot([cx - 1.5, cx + 1.5], [0, 0], color=BG, lw=6.0 if ours else 3.0,
              zorder=5, alpha=0.9 if ours else 0.5 * fade)
    if ours:
        ax14.text(cx, BUB_H14 + 0.45, "OUR BUBBLE—$w{=}5$", ha="center",
                  fontsize=11, fontweight="bold", color=YANG_PEAK)
        ax14.text(cx, BUB_H14 + 0.15, "step 285 · Ø ≈ 191 Mpc",
                  ha="center", fontsize=8, color=TEXT_MAIN)
        ax14.text(cx, -BUB_H14 - 0.6, f"$n_k = 286 + 7k$, $k=0$",
                  ha="center", fontsize=7.5, color=TEXT_SUB)
    else:
        ax14.text(cx, -1.1, f"$w={w_num}$", ha="center", fontsize=9,
                  color=lerp(TEXT_SUB, BG, 1 - fade), fontweight="bold", zorder=7)

# Hubble horizon
ax14.vlines(N_HUBBLE, -BUB_H14 - 0.3, BUB_H14 + 0.2, color=YANG_MID, lw=1.6,
            ls=(0, (6, 3)), zorder=5)
ax14.text(N_HUBBLE + 1.5, BUB_H14 + 0.9, "Hubble radius ($n=292$)\n"
          "next bubble begins\ninside the horizon",
          fontsize=7.5, color=YANG_MID, ha="center")

ax14.set_xlabel("cascade step  $n$  along the connecting axis", fontsize=9, color=TEXT_SUB)
eq_text(ax14, 0.02, 0.05,
        r"$n_k = 286 + 7k$     $\ell_{n_k} \propto \varphi^{7k}$     "
        r"self-similar: $\ell \to \varphi^7\ell$     no largest scale")
panel_title(ax14, r"14 · THE MEGACASCADE ($n>292$)—the ladder continues upward forever. Larger bubbles, same geometry. Self-similar under $\ell \to \varphi^7\ell$.")

# ═══════════════════════════════════════════════════════════════════════════════
# Footer
fig.text(0.5, 0.003,
         r"six pieces—one universe  ·  $\varphi$  ·  two components  ·  scale ladder  ·  "
         "the gate  ·  the bubble  ·  the lattice  ·  everything else emerges",
         ha="center", fontsize=9, color=TEXT_SUB)

OUT = "visual-explainers/universe_answers.png"
fig.savefig(OUT, dpi=120, facecolor=BG)
print(f"wrote {OUT}")

# ═══════════════════════════════════════════════════════════════════════════════
# Console verification
# ═══════════════════════════════════════════════════════════════════════════════
print("\nverification: scale spot-checks (ℓ_n = ℓ_Pl · φⁿ)")
for n, label, expect in [
    (0, "Planck", 1.616e-35), (80, "EW", 8.0e-19), (95, "QCD", 1.1e-15),
    (117, "Bohr", 5.3e-11), (267, "MW", 9.3e20), (285, "bubble", 5.9e24),
    (292, "Hubble", 1.7e26), (-50, "micro", 5.7e-46),
]:
    val = float(ell(n))
    ok = "✓" if abs(val/expect - 1) < 0.15 else "?"
    print(f"  n={n:>4} {label:10s}: {val:.3e} m  (expect {expect:.1e})  {ok}")

print("\nkey φ-powers:")
for k, label in [(1, "φ⁻¹"), (2, "φ⁻²"), (3, "sin²θ_W"), (6, "ξ"), (12, "r≈0.003"),
                 (44, "η≈6e-10"), (80, "v₀/M_Pl"), (89, "θ̄≈1e-19")]:
    val = PHI ** k
    print(f"  φ^{k:>3} = {val:.6e}  ({label})")

print(f"\nmicrocascade ansatz: (1−q_0⁻) = {coherence_factor(0):.3f}  (doc: ≈0.809)")
