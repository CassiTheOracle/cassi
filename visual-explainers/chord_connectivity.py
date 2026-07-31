#!/usr/bin/env python3
"""
Chord Lattice Connectivity: geometric analysis of the bubble network
===================================================================

The condensation field C(x,y) = cos(αx)·cos(βy) on the Yang-Yin plane defines
a staggered checkerboard lattice of bubble (+) and void (−) sites. This script
analyzes the GEOMETRIC connectivity of that lattice: percolation threshold,
inter-bubble saddle barriers, and how the φ-aspect-ratio shapes the network.

This is a GEOMETRIC analysis of the chord lattice structure derived in
chord_lattice.py. Whether Qi coherence actually transports through the
inter-bubble saddles is a separate (Speculative) question.

Run:  python visual-explainers/chord_connectivity.py
Out:  visual-explainers/chord_connectivity.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from scipy import ndimage

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
LAM_I = 2.0
LAM_Y = PHI * LAM_I
ALPHA = 2 * np.pi / LAM_Y
BETA = 2 * np.pi / LAM_I               # β/α = φ

# House palette
YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
BG, TEXT_MAIN, TEXT_SUB, RING = "#060612", "#e0e0f0", "#a0a0c0", "#303050"
GREEN_SAFE, YELLOW_CAUTION, RED_DANGER = "#2ecc71", "#f1c40f", "#e74c3c"
SADDLE_COLOR = "#ff6b6b"

def lerp(c1, c2, t):
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * np.clip(t, 0, 1))

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

# Diverging colormap
CHORDMAP = LinearSegmentedColormap.from_list("chord", [
    (0.00, YIN_MID), (0.32, YIN_DEEP), (0.50, BG),
    (0.72, YANG_DARK), (1.00, YANG_PEAK)])

# ─────────────────────────────────────────────────────────────────────────────
# Condensation field
# ─────────────────────────────────────────────────────────────────────────────
NX, NY = 1600, 800
x = np.linspace(-3.5, 3.5, NX)
y = np.linspace(-3.5, 3.5, NY)
XX, YY = np.meshgrid(x, y)
C = np.cos(ALPHA * XX) * np.cos(BETA * YY)

# ─────────────────────────────────────────────────────────────────────────────
# Percolation analysis: connected components of {C ≥ θ}
# ─────────────────────────────────────────────────────────────────────────────
theta_values = np.linspace(0.9, -0.3, 61)
n_components = np.zeros(len(theta_values))

for i, theta in enumerate(theta_values):
    binary = (C >= theta).astype(np.int32)
    # Label connected components (4-connectivity to capture actual merges)
    labeled, n_labels = ndimage.label(binary)
    n_components[i] = n_labels

# Find percolation threshold: when first component spans the domain
spanning_threshold = None
for i, theta in enumerate(theta_values):
    binary = (C >= theta).astype(np.int32)
    labeled, n_labels = ndimage.label(binary)
    if n_labels == 0:
        continue
    # Check if any component touches all 4 domain edges
    for lbl in range(1, n_labels + 1):
        mask = labeled == lbl
        touches_left = np.any(mask[:, 0])
        touches_right = np.any(mask[:, -1])
        touches_top = np.any(mask[0, :])
        touches_bottom = np.any(mask[-1, :])
        if touches_left and touches_right and touches_top and touches_bottom:
            spanning_threshold = theta
            break
    if spanning_threshold is not None:
        break

# ─────────────────────────────────────────────────────────────────────────────
# Saddle analysis between bubble (0,0) and its nearest diagonal neighbor
# ─────────────────────────────────────────────────────────────────────────────
# Diagonal neighbor: (λ_Y/2, λ_I/2)—m+n=0+0=0 (even), neighbor (1,1): 1+1=2 (even)
# Path from (0,0) to (λ_Y/2, λ_I/2)
# Parametric: (t * λ_Y/2, t * λ_I/2) for t ∈ [0, 1]
t_path = np.linspace(0, 1, 500)
path_x = t_path * (LAM_Y / 2)
path_y = t_path * (LAM_I / 2)
C_path = np.cos(ALPHA * path_x) * np.cos(BETA * path_y)

# The saddle is at t = 0.5: C_saddle = cos(π/2)·cos(π/2) = 0
saddle_t = 0.5
saddle_C = 0.0

# Also analyze the axial path: (0,0) → (λ_Y, 0)  [never merges]
path_ax_x = np.linspace(0, LAM_Y, 500)
path_ax_y = np.zeros(500)
C_path_ax = np.cos(ALPHA * path_ax_x) * np.cos(BETA * path_ax_y)

# ─────────────────────────────────────────────────────────────────────────────
# Bubble geometry: nearest-neighbor distances
# ─────────────────────────────────────────────────────────────────────────────
# Bubble at (0,0), neighbors in the even (m+n even) sublattice
# Axial Yang: (±2, 0) at distance λ_Y
# Axial Yin: (0, ±2) at distance λ_I
# Diagonal: (±1, ±1) at distance sqrt(λ_Y²/4 + λ_I²/4) = sqrt(λ_Y²+λ_I²)/2
# Degree of the lattice: each bubble has 4 axial + 4 diagonal = 8 neighbors
# BUT: only diagonal neighbors share a saddle path (C passes through 0)
# Axial neighbors are separated by C=-1 void minimum—NEVER merge

diag_dist = np.sqrt(LAM_Y**2 + LAM_I**2) / 2
axial_yang_dist = LAM_Y
axial_yin_dist = LAM_I

# ─────────────────────────────────────────────────────────────────────────────
# Figure
# ─────────────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(19, 11), dpi=160, facecolor=BG)

# ── Panel A: Condensation field with contours at key θ ──────────────────────
axA = fig.add_axes([0.04, 0.54, 0.44, 0.42])
axA.set_facecolor(BG)

axA.imshow(C, extent=(-3.5, 3.5, -3.5, 3.5), origin="lower",
           cmap=CHORDMAP, vmin=-1, vmax=1, interpolation="bilinear", zorder=1)

# Contours: θ_cond=0.45 (original, isolated), θ=0 (percolation), θ=-0.3 (merged)
contour_levels = [0.45, 0.0, -0.2]
contour_colors = [YANG_BRIGHT, GREEN_SAFE, YIN_LIGHT]
contour_labels = [r"$\theta_{\\rm cond}{=}0.45$ (isolated bubbles)",
                  r"$\theta{=}0$ (percolation threshold)",
                  r"$\theta{=}{-}0.2$ (fully merged)"]

for lev, col, lab in zip(contour_levels, contour_colors, contour_labels):
    cs = axA.contour(XX, YY, C, levels=[lev], colors=[col],
                     linewidths=[1.2, 1.8, 1.0][contour_levels.index(lev)],
                     zorder=3)
    # Add manual label
    mid_idx = 0

# Bubble centers (m+n even) as dots
m_max = int(3.5 / (LAM_Y / 2)) + 1
n_max = int(3.5 / (LAM_I / 2)) + 1
for m in range(-m_max, m_max + 1):
    for n in range(-n_max, n_max + 1):
        sx, sy = m * LAM_Y / 2, n * LAM_I / 2
        if abs(sx) > 3.2 or abs(sy) > 3.2:
            continue
        if (m + n) % 2 == 0:
            axA.plot(sx, sy, "o", ms=4, mfc="none", mec=TEXT_MAIN, mew=0.7, zorder=5)
        else:
            axA.plot(sx, sy, "x", ms=3, mec=YIN_LIGHT, mew=0.5, zorder=5)

# Highlight the origin bubble and its diagonal neighbor for saddle analysis
axA.plot(0, 0, "o", ms=9, mfc="none", mec=YANG_PEAK, mew=2.0, zorder=6)
axA.plot(LAM_Y/2, LAM_I/2, "o", ms=9, mfc="none", mec=SADDLE_COLOR, mew=2.0, zorder=6)

# Saddle path: dashed line between (0,0) and (λ_Y/2, λ_I/2)
axA.plot([0, LAM_Y/2], [0, LAM_I/2], "--", color=SADDLE_COLOR, lw=1.5, alpha=0.8, zorder=4)
# Saddle marker
axA.plot(LAM_Y/4, LAM_I/4, "s", ms=7, color=SADDLE_COLOR, zorder=6, alpha=0.9)
axA.annotate("saddle\n$C{=}0$", xy=(LAM_Y/4, LAM_I/4),
             xytext=(LAM_Y/4 + 0.5, LAM_I/4 - 0.35),
             fontsize=7.5, color=SADDLE_COLOR, ha="center",
             arrowprops=dict(arrowstyle="->", color=SADDLE_COLOR, lw=0.9))

# Axial void: midpoint of axial path (never merges)
axA.plot(LAM_Y/2, 0, "x", ms=8, color=RED_DANGER, mew=2.5, zorder=6)
axA.annotate("axial void\n$C{=}{-}1$", xy=(LAM_Y/2, 0),
             xytext=(LAM_Y/2 + 0.55, -0.5),
             fontsize=7.5, color=RED_DANGER, ha="center",
             arrowprops=dict(arrowstyle="->", color=RED_DANGER, lw=0.9))

axA.set_xlim(-3.5, 3.5); axA.set_ylim(-3.5, 3.5)
axA.set_aspect("equal")
axA.set_xticks([]); axA.set_yticks([])
for sp in axA.spines.values():
    sp.set_visible(False)

axA.set_title("A. Condensation Field with Bubble Contours & Saddle Paths",
              fontsize=12, color=YANG_PEAK, fontweight="bold", pad=8)

# Legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], lw=1.5, color=YANG_BRIGHT, label=r"$\theta_{\rm cond}=0.45$ (isolated)"),
    Line2D([0], [0], lw=1.8, color=GREEN_SAFE, label=r"$\theta=0$ (percolation threshold)"),
    Line2D([0], [0], lw=1.0, color=YIN_LIGHT, label=r"$\theta=-0.2$ (merged)"),
    Line2D([0], [0], ls="--", lw=1.5, color=SADDLE_COLOR, label="diagonal saddle path"),
    Line2D([0], [0], marker="o", ms=6, mfc="none", mec=TEXT_MAIN, mew=1.0,
           color="none", label="bubble (m+n even)"),
    Line2D([0], [0], marker="x", ms=5, mec=YIN_LIGHT, mew=1.0,
           color="none", label="void (m+n odd)"),
]
axA.legend(handles=legend_elements, fontsize=7.5, loc="lower left",
           framealpha=0.85, facecolor=BG, edgecolor=RING)

# ── Panel B: Percolation curve ──────────────────────────────────────────────
axB = fig.add_axes([0.54, 0.54, 0.42, 0.42])
axB.set_facecolor(BG)

axB.plot(theta_values, n_components, color=YANG_BRIGHT, lw=2.0, zorder=3)
axB.axvline(x=0, color=GREEN_SAFE, lw=1.8, ls="--", alpha=0.8)
axB.axvline(x=0.45, color=YANG_MID, lw=1.2, ls=":", alpha=0.6)

# Percolation threshold annotation
if spanning_threshold is not None:
    axB.axvline(x=spanning_threshold, color=SADDLE_COLOR, lw=1.2, ls=":", alpha=0.7)
    axB.annotate(f"percolation\nθ ≈ {spanning_threshold:.2f}",
                 xy=(spanning_threshold, 20), xytext=(spanning_threshold + 0.15, 60),
                 fontsize=8, color=SADDLE_COLOR, ha="center",
                 arrowprops=dict(arrowstyle="->", color=SADDLE_COLOR, lw=1.0))

axB.annotate("θ = 0 (analytical\npercolation threshold\nof cos·cos field)",
             xy=(0, 10), xytext=(-0.35, 150),
             fontsize=8.5, color=GREEN_SAFE, ha="center",
             arrowprops=dict(arrowstyle="->", color=GREEN_SAFE, lw=1.2))

axB.annotate(r"θ_cond = 0.45" + "\n(isolated bubbles,\nused in chord_lattice.py)",
             xy=(0.45, n_components[np.argmin(np.abs(theta_values - 0.45))]),
             xytext=(0.45 - 0.35, 200),
             fontsize=8, color=YANG_MID, ha="center",
             arrowprops=dict(arrowstyle="->", color=YANG_MID, lw=1.0))

# Shade regimes
axB.axvspan(-0.3, 0, alpha=0.06, color=YIN_MID, zorder=0)
axB.axvspan(0, 0.9, alpha=0.04, color=YANG_MID, zorder=0)
axB.text(0.15, 0.92, "ISOLATED BUBBLES", transform=axB.transAxes,
         fontsize=8, color=TEXT_SUB, ha="center", fontstyle="italic")
axB.text(0.85, 0.92, "MERGED", transform=axB.transAxes,
         fontsize=8, color=YIN_LIGHT, ha="center", fontstyle="italic")

axB.set_xlabel(r"condensation threshold $\theta$", fontsize=10, color=TEXT_SUB)
axB.set_ylabel("number of connected components", fontsize=10, color=TEXT_SUB)
axB.set_xlim(-0.3, 0.9)
axB.set_title("B. Percolation: Connected Components of {$C \\geq \\theta$}",
              fontsize=12, color=YANG_PEAK, fontweight="bold", pad=8)

# ── Panel C: Saddle profile ─────────────────────────────────────────────────
axC = fig.add_axes([0.04, 0.06, 0.44, 0.36])
axC.set_facecolor(BG)

# Diagonal saddle path
axC.plot(t_path, C_path, color=SADDLE_COLOR, lw=2.0,
         label="diagonal: $(0,0) \\to (\\lambda_Y/2,\\,\\lambda_I/2)$")
# Axial path
axC.plot(t_path, C_path_ax, color=RED_DANGER, lw=1.5, ls="--",
         label="axial: $(0,0) \\to (\\lambda_Y,\\,0)$")

# Threshold lines
axC.axhline(y=0, color=GREEN_SAFE, lw=1.2, ls=":", alpha=0.7)
axC.axhline(y=0.45, color=YANG_MID, lw=1.0, ls=":", alpha=0.5)
axC.axhline(y=1.0, color=TEXT_SUB, lw=0.6, ls=":", alpha=0.3)
axC.axhline(y=-1.0, color=TEXT_SUB, lw=0.6, ls=":", alpha=0.3)

# Annotations
axC.annotate("bubble peak\n$C{=}1$", xy=(0, 1), xytext=(0.05, 0.85),
             fontsize=7.5, color=YANG_PEAK, ha="left",
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=0.8))
axC.annotate("bubble peak\n$C{=}1$", xy=(1, 1), xytext=(0.8, 0.85),
             fontsize=7.5, color=YANG_PEAK, ha="left",
             arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=0.8))
axC.annotate("saddle\n$C{=}0$", xy=(0.5, 0), xytext=(0.43, -0.15),
             fontsize=7.5, color=SADDLE_COLOR, ha="center",
             arrowprops=dict(arrowstyle="->", color=SADDLE_COLOR, lw=0.8))
axC.annotate("Qi barrier = $1 - C_{\\rm saddle} = 1$", xy=(0.5, 0),
             xytext=(0.6, 0.1),
             fontsize=7.5, color=SADDLE_COLOR, ha="left")
axC.annotate("axial void\n$C{=}{-}1$", xy=(0.5, -1), xytext=(0.55, -0.85),
             fontsize=7.5, color=RED_DANGER, ha="left",
             arrowprops=dict(arrowstyle="->", color=RED_DANGER, lw=0.8))

# Shade "connected" region for diagonal (C ≥ 0)
axC.axvspan(0.20, 0.80, alpha=0.06, color=GREEN_SAFE, zorder=0)
axC.text(0.50, 0.45, "connected at θ ≤ 0", fontsize=7, color=GREEN_SAFE,
         ha="center", fontstyle="italic")

# θ_cond threshold
axC.text(0.98, 0.15, r"$\theta_{\rm cond} = 0.45$" + "\n(not connected)",
         transform=axC.transAxes, fontsize=7.5, color=YANG_MID, ha="right")

axC.set_xlabel("path parameter $t \\in [0,1]$", fontsize=10, color=TEXT_SUB)
axC.set_ylabel("condensation field $C$", fontsize=10, color=TEXT_SUB)
axC.set_xlim(0, 1); axC.set_ylim(-1.1, 1.1)
axC.legend(fontsize=7.5, loc="upper right", framealpha=0.85,
           facecolor=BG, edgecolor=RING)
axC.set_title("C. Saddle Profile: Inter-Bubble Condensation Field",
              fontsize=12, color=YANG_PEAK, fontweight="bold", pad=8)

# ── Panel D: Findings + lattice analysis ─────────────────────────────────────
axD = fig.add_axes([0.54, 0.06, 0.42, 0.36])
axD.set_facecolor(BG)
axD.set_xlim(0, 1); axD.set_ylim(0, 1)
axD.axis("off")

findings = [
    ("LATTICE GEOMETRY—Derived (from C(x,y) = cos(αx)·cos(βy))", YANG_PEAK, 12, "bold"),
    ("", TEXT_SUB, 7, "normal"),
    (f"  Bubble spacing (Yang axis):     λ_Y = {LAM_Y:.4f}  (φ · λ_I)", TEXT_MAIN, 9, "normal"),
    (f"  Bubble spacing (Yin axis):       λ_I = {LAM_I:.4f}", TEXT_MAIN, 9, "normal"),
    (f"  Row stagger (anti-phase):        λ_Y/2 = {LAM_Y/2:.4f}", TEXT_MAIN, 9, "normal"),
    (f"  Diagonal neighbor distance:      {diag_dist:.4f}  = √(λ_Y²+λ_I²)/2", TEXT_MAIN, 9, "normal"),
    (f"  Bubble aspect ratio:             a_Yang/a_Yin = β/α = φ = {PHI:.4f}", TEXT_MAIN, 9, "normal"),
    ("", TEXT_SUB, 7, "normal"),
    ("CONNECTIVITY—Geometric analysis", YANG_BRIGHT, 11, "bold"),
    ("", TEXT_SUB, 7, "normal"),
    (f"  Lattice degree:                  8 (4 axial + 4 diagonal, geometric)", TEXT_MAIN, 9, "normal"),
    (f"  Effective degree (connectable):  4 (diagonal only—axial blocked by C=−1 voids)", GREEN_SAFE, 9, "normal"),
    (f"  Percolation threshold:           θ_perc = 0.0 (analytical, cos·cos product)", GREEN_SAFE, 9, "normal"),
    (f"  At θ_cond = 0.45:                ISOLATED bubbles (0 connected components merge)", YELLOW_CAUTION, 9, "normal"),
    (f"  Saddle barrier between diagonal  1 − C_saddle = 1.0 (full Qi barrier)", SADDLE_COLOR, 9, "normal"),
    (f"  neighbors:", TEXT_MAIN, 9, "normal"),
    (f"  Axial neighbors:                 NEVER merge (C=−1 void between them)", RED_DANGER, 9, "normal"),
    ("", TEXT_SUB, 7, "normal"),
    ("φ-ASPECT-RATIO EFFECT", YANG_MID, 11, "bold"),
    ("", TEXT_SUB, 7, "normal"),
    (f"  φ = {PHI:.4f} makes lattice ANISOTROPIC: bubbles are φ:1 oblong ovals", TEXT_MAIN, 9, "normal"),
    (f"  An isotropic lattice (φ=1) would have circular bubbles, same percolation θ=0", TEXT_MAIN, 9, "normal"),
    (f"  φ changes bubble SHAPE but not lattice TOPOLOGY—degree-4 stays degree-4", TEXT_MAIN, 9, "normal"),
    (f"  The φ anisotropy means the inter-bubble saddle PATH is longer by φ in Yang", TEXT_MAIN, 9, "normal"),
    ("", TEXT_SUB, 7, "normal"),
    ("EPISTEMIC", YANG_PEAK, 11, "bold"),
    (f"  Lattice geometry & percolation:  DERIVED (from C field)", GREEN_SAFE, 9, "normal"),
    (f"  Coherence transport via saddles:  SPECULATIVE (not from PDE)", RED_DANGER, 9, "normal"),
    (f"  Bubble↔string identification:    HYPOTHESIZED (chord hypothesis)", YELLOW_CAUTION, 9, "normal"),
]

y_pos = 0.97
for text, color, size, weight in findings:
    axD.text(0.02, y_pos, text, transform=axD.transAxes,
             fontsize=size, color=color, fontweight=weight,
             fontstyle="italic" if "italic" in str(weight) else "normal",
             va="top")
    y_pos -= 0.022 if text else 0.013

# ── Title ────────────────────────────────────────────────────────────────────
fig.suptitle("CHORD LATTICE CONNECTIVITY—Geometric Analysis of the Bubble Network",
             fontsize=18, fontweight="bold", color=YANG_PEAK, y=0.985)
fig.text(0.5, 0.975,
         r"$C(x,y) = \cos(2\pi x/\lambda_Y)\;\cos(2\pi y/\lambda_I)$"
         r"    $\lambda_Y = \varphi\lambda_I$"
         r"    bubbles at $(m\lambda_Y/2,\;n\lambda_I/2)$ with $m{+}n$ even"
         r"    ·    lattice geometry: Derived    ·    coherence transport: Speculative",
         ha="center", fontsize=9, color=TEXT_SUB)

OUT = "visual-explainers/chord_connectivity.png"
fig.savefig(OUT, dpi=160, facecolor=BG)
print(f"wrote {OUT}")

# ─────────────────────────────────────────────────────────────────────────────
# Console verification
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Chord Lattice Connectivity Analysis ──")
print(f"  PHI              = {PHI:.12f}")
print(f"  λ_I (Yin wake)   = {LAM_I:.4f}")
print(f"  λ_Y (Yang wake)  = {LAM_Y:.4f}  = φ · λ_I")
print(f"  β/α              = {BETA/ALPHA:.6f}  (= φ)")
print(f"")

print("  ── Lattice geometry ──")
print(f"  Bubble spacing (Yang axis):   {axial_yang_dist:.4f}")
print(f"  Bubble spacing (Yin axis):    {axial_yin_dist:.4f}")
print(f"  Row stagger:                  {LAM_Y/2:.4f}")
print(f"  Diagonal neighbor distance:   {diag_dist:.4f}")
print(f"  Axial neighbor distance:      {axial_yang_dist:.4f} (Yang), {axial_yin_dist:.4f} (Yin)")
print(f"")

print("  ── Percolation ──")
if spanning_threshold is not None:
    print(f"  Spanning percolation threshold θ ≈ {spanning_threshold:.4f}")
else:
    print(f"  No spanning component found (need larger domain)")
print(f"  Analytical percolation threshold: θ = 0.0 (cos·cos product field)")
print(f"  n_components at θ=0.45 (current): {n_components[np.argmin(np.abs(theta_values - 0.45))]}")
print(f"  n_components at θ=0:              {n_components[np.argmin(np.abs(theta_values - 0.0))]}")
print(f"")

print("  ── Saddle analysis ──")
print(f"  Diagonal saddle C = {saddle_C:.1f}  → Qi barrier = 1 − C_saddle = {1-saddle_C:.1f}")
print(f"  Axial path minimum C = {np.min(C_path_ax):.1f}  (at void midpoint)")
print(f"  Diagonal path minimum C = {np.min(C_path):.6f}  (at saddle midpoint)")
print(f"")

print("  ── Network summary ──")
print(f"  Geometric degree:              8 (all m+n-even site neighbors)")
print(f"  Connectable degree (θ ≤ 0):    4 (diagonal only)")
print(f"  At θ_cond = 0.45:              0 (isolated bubbles)")
print(f"  Lattice topology:              2D staggered square (degree-4 diagonals)")
print(f"  φ effect on topology:           NONE (changes anisotropy, not degree)")
print(f"  φ effect on bubble shape:       a_Yang/a_Yin = φ = {PHI:.4f}")
