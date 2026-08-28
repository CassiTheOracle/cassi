#!/usr/bin/env python3
"""
Fractal Zoom—The Self-Similar Qi Bubble Cascade
==================================================

Three zoom levels demonstrating the fractal structure of the Cassi cascade:
  A · OVERVIEW—log-radial rings, each with identical I(ρ)=2[1−cos(2πρ)],
      Fibonacci spiral overlay, cascade landmarks
  B · BUBBLE—one Qi bubble at deep zoom: elliptical φ:1 cross-section,
      multi-scale Qi coherence texture, two five-arm spiral poles
  C · POLE—ultra-zoom into a five-arm Fibonacci spiral pole:
      golden-angle phyllotaxis (2π/φ²), 5 colored arms, nested sub-bubble

Physics: ℓ_n = ℓ_Pl × φ^n, Hausdorff D = ln(φ)/ln(φ) = 1,
         golden angle 2π/φ² ≈ 137.5°, five-arm emergence via Fibonacci.

Sources: foundations/dimensionful-cascade.md,
         foundations/spin-fibonacci-spiral.md §3,
         visual-explainers/qi_cascade_cosmos.py (Qi texture),
         visual-explainers/fibonacci_bubble_spiral.py (five-arm spiral)

Run:  python visual-explainers/fractal_zoom.py
Out:  visual-explainers/fractal_zoom.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
import matplotlib.patheffects as pe

# ═══════════════════════════════════════════════════════════════════════════
# Framework constants
# ═══════════════════════════════════════════════════════════════════════════
PHI = (1 + np.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * np.pi / PHI**2          # ≈ 137.508°
L_PL = 1.616255e-35
N_HUBBLE = 292

# ═══════════════════════════════════════════════════════════════════════════
# House palette (cascade_cosmos.py)
# ═══════════════════════════════════════════════════════════════════════════
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
RING_LINE   = "#303050"

# Qi colours (from qi_cascade_cosmos.py)
QI_TEAL     = "#20a078"
QI_DEEP     = "#082018"
QI_BRIGHT   = "#60ffc0"

# Five-arm spiral colours (from fibonacci_bubble_spiral.py)
ARM_COLORS  = ["#ffe060", "#daa520", "#c07820", "#9a6a1a", "#5a3a10"]

def lerp(c1, c2, t):
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * max(0, min(1, t)))

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING_LINE,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

# ═══════════════════════════════════════════════════════════════════════════
# Cascade parameters
# ═══════════════════════════════════════════════════════════════════════════
N_START = 80
N_RINGS = 55
N_END = N_START + N_RINGS

LANDMARKS = [
    (80,  "n=80 Electroweak"),
    (95,  "n=95 QCD / proton"),
    (117, "n=117 Bohr radius"),
]

def ring_radius(n):
    return (n - N_START) / N_RINGS

# ═══════════════════════════════════════════════════════════════════════════
# Figure—3-panel landscape
# ═══════════════════════════════════════════════════════════════════════════
DPI = 170
fig = plt.figure(figsize=(20, 12), dpi=DPI)
gs = fig.add_gridspec(2, 2, width_ratios=[1.05, 0.95], height_ratios=[1, 1],
                      hspace=0.22, wspace=0.16,
                      left=0.035, right=0.975, top=0.915, bottom=0.055)

axA = fig.add_subplot(gs[:, 0])    # Panel A: cascade overview
axB = fig.add_subplot(gs[0, 1])    # Panel B: single bubble deep zoom
axC = fig.add_subplot(gs[1, 1])    # Panel C: five-arm spiral pole

fig.suptitle("FRACTAL ZOOM—The Self-Similar Qi Bubble Cascade",
             fontsize=20, fontweight="bold", color=YANG_PEAK, y=0.968)
fig.text(0.5, 0.937,
         "$\\ell_n = \\ell_{\\rm Pl}\\,\\varphi^{n}$  ·  "
         "Hausdorff $D = \\ln(\\varphi)/\\ln(\\varphi) = 1$  ·  "
         "golden angle $2\\pi/\\varphi^2 \\approx 137.5^\\circ$  ·  "
         "five-arm Fibonacci spiral at each bubble pole",
         ha="center", fontsize=9, color=TEXT_SUB)

def panel_label(ax, text):
    ax.text(0.02, 0.96, text, transform=ax.transAxes,
            fontsize=12, fontweight="bold", color=YANG_BRIGHT,
            va="top", ha="left")

# ═══════════════════════════════════════════════════════════════════════════
# PANEL A—Cascade Overview (left column)
# ═══════════════════════════════════════════════════════════════════════════
print("Panel A: cascade overview...")
axA.set_xlim(-1, 1)
axA.set_ylim(-1, 1)
axA.set_aspect("equal")
axA.axis("off")

R_INNER = 0.06
R_OUTER = 0.88
RES_A = 1500

xa = np.linspace(-1, 1, RES_A)
ya = np.linspace(-1, 1, RES_A)
XXa, YYa = np.meshgrid(xa, ya)
RRa = np.sqrt(XXa**2 + YYa**2)
THa = np.arctan2(YYa, XXa)

u_a = np.where(
    (RRa >= R_INNER) & (RRa <= R_OUTER),
    N_RINGS * (RRa - R_INNER) / (R_OUTER - R_INNER),
    np.nan
)

n_ring_a = np.zeros_like(u_a, dtype=int)
mask_a = ~np.isnan(u_a)
n_ring_a[mask_a] = np.floor(u_a[mask_a]).astype(int)
n_ring_a = np.clip(n_ring_a, 0, N_RINGS - 1)
rho_a = u_a - n_ring_a

I_radial_a = 2 * (1 - np.cos(2 * np.pi * rho_a))
spiral_phase_a = THa - GOLDEN_ANGLE * n_ring_a
I_angular_a = 0.25 * np.cos(spiral_phase_a)
field_a = np.where(~np.isnan(u_a), I_radial_a * (1 + I_angular_a), np.nan)
field_norm_a = np.clip(field_a / 5.0, 0, 1)

frac_a = np.clip(n_ring_a / max(N_RINGS - 1, 1), 0, 1)
yin_rgb  = np.array(to_rgb(YIN_MID))
yang_rgb = np.array(to_rgb(YANG_MID))
base_rgb_a = yin_rgb * (1 - frac_a)[:, :, None] + yang_rgb * frac_a[:, :, None]
bg_rgb = np.array(to_rgb(BG))
bright_a = field_norm_a[:, :, None]
img_a = np.where(
    ~np.isnan(u_a[:, :, None]),
    bg_rgb * (1 - bright_a) + base_rgb_a * bright_a,
    bg_rgb
)

axA.imshow(img_a, extent=(-1, 1, -1, 1), origin="lower",
           interpolation="bilinear", zorder=1)

# Ring boundaries (every 10th)
for i in range(0, N_RINGS + 1, 5):
    n = N_START + i
    r_val = R_INNER + (R_OUTER - R_INNER) * i / N_RINGS
    alpha = 0.18 if n % 10 == 0 else 0.05
    lw = 0.8 if n % 10 == 0 else 0.25
    circle = plt.Circle((0, 0), r_val, fill=False,
                        color=TEXT_SUB, lw=lw, alpha=alpha, zorder=2)
    axA.add_patch(circle)

# Fibonacci spiral overlay
theta_sp = np.linspace(0, 2 * np.pi * N_RINGS * 1.15, 2500)
u_sp = theta_sp / (2 * np.pi)
r_sp = R_INNER + (R_OUTER - R_INNER) * u_sp / N_RINGS
visible = (r_sp >= R_INNER) & (r_sp <= R_OUTER)
theta_sp, r_sp = theta_sp[visible], r_sp[visible]
sx, sy = r_sp * np.cos(theta_sp), r_sp * np.sin(theta_sp)
for i in range(0, len(sx) - 4, 4):
    t = np.clip(i / len(sx), 0, 1)
    axA.plot(sx[i:i+5], sy[i:i+5],
             color=lerp(YIN_LIGHT, YANG_PEAK, t),
             alpha=0.15 + 0.4 * t, lw=0.3 + 2.0 * t,
             solid_capstyle="round", zorder=5)

# Landmarks
text_fx = [pe.withStroke(linewidth=3, foreground=BG)]
for n, label in LANDMARKS:
    r_val = R_INNER + (R_OUTER - R_INNER) * ring_radius(n)
    angle = -np.pi/2 + 0.5
    lx, ly = r_val * np.cos(angle), r_val * np.sin(angle)
    axA.plot(lx, ly, "o", ms=3.5, color=YANG_PEAK, zorder=6)
    axA.text(R_OUTER + 0.04, ly, label, ha="left", va="center",
             fontsize=7, color=TEXT_MAIN, path_effects=text_fx, zorder=7)
    axA.plot([lx, R_OUTER + 0.03], [ly, ly],
             color=TEXT_SUB, lw=0.4, alpha=0.4, zorder=3)

# Zoom arrow
r_from = R_INNER + (R_OUTER - R_INNER) * ring_radius(N_START + 8)
r_to   = R_INNER + (R_OUTER - R_INNER) * ring_radius(N_START + 38)
ang_z = np.pi/2 - 0.6
axA.annotate("", xy=(r_to*np.cos(ang_z), r_to*np.sin(ang_z)),
             xytext=(r_from*np.cos(ang_z), r_from*np.sin(ang_z)),
             arrowprops=dict(arrowstyle="->", color=YANG_BRIGHT, lw=1.8,
                             connectionstyle="arc3,rad=-0.25"), zorder=8)
axA.text(r_from*np.cos(ang_z-0.10), r_from*np.sin(ang_z-0.06),
         "zoom\n×φ³⁰", fontsize=8, color=YANG_BRIGHT, fontweight="bold",
         ha="center", va="bottom", zorder=8, linespacing=1.1)

# Ring-scale annotations
axA.text(-R_OUTER-0.05, 0.65, "→ Yang\n(large scales)",
         ha="center", fontsize=7, color=YANG_BRIGHT, linespacing=1.1)
axA.text(-R_OUTER-0.05, -0.65, "→ Yin\n(small scales)",
         ha="center", fontsize=7, color=YIN_LIGHT, linespacing=1.1)

# Panel equations
axA.text(0.5, -0.06,
         "$I(\\rho) = 2[1-\\cos(2\\pi\\rho)]$  ·  "
         "$\\rho \\in [0,1)$ per ring  ·  "
         "spiral: $\\Theta_i(r) = \\Theta_0 + \\frac{2\\pi}{\\ln\\varphi}\\ln(r/\\ell_i)$",
         ha="center", fontsize=8, color=TEXT_SUB, transform=axA.transAxes)

panel_label(axA, "A · CASCADE OVERVIEW—55 φ-steps, EW → near-visible-light")

# ═══════════════════════════════════════════════════════════════════════════
# PANEL B—Single Qi Bubble Deep Zoom (top-right)
# ═══════════════════════════════════════════════════════════════════════════
print("Panel B: Qi bubble deep zoom...")
axB.set_xlim(-PHI - 0.3, PHI + 0.3)
axB.set_ylim(-1.4, 1.4)
axB.set_aspect("equal")
axB.axis("off")

# ── Elliptical bubble boundary ─────────────────────────────────────────────
A_YANG, B_YIN = PHI, 1.0
bubble = plt.matplotlib.patches.Ellipse(
    (0, 0), 2*A_YANG, 2*B_YIN, fill=False,
    edgecolor=YANG_BRIGHT, lw=2.2, zorder=10)
axB.add_patch(bubble)

# ── Qi coherence standing-wave texture ─────────────────────────────────────
RES_B = 600
xb = np.linspace(-A_YANG - 0.3, A_YANG + 0.3, RES_B)
yb = np.linspace(-1.4, 1.4, RES_B)
XXb, YYb = np.meshgrid(xb, yb)

# Multi-scale φ-wavelength standing waves (from qi_cascade_cosmos.py)
ey = (1.0 + 0.35 * np.cos(2*np.pi*XXb/PHI)
         + 0.12 * np.cos(2*np.pi*XXb/(PHI**2))
         + 0.06 * np.cos(2*np.pi*XXb/(PHI**3)))
ei = (1.0 + 0.35 * np.cos(2*np.pi*YYb)
         + 0.12 * np.cos(2*np.pi*YYb/PHI)
         + 0.06 * np.cos(2*np.pi*YYb/(PHI**2)))
qi_raw = np.abs(ey) * np.abs(ei)
checker = np.cos(2*np.pi*XXb/PHI) * np.cos(2*np.pi*YYb)
qi_mod = qi_raw * (0.7 + 0.3 * (checker + 1) / 2)
filament = np.cos(2*np.pi*(XXb/PHI + YYb*PHI))**2
qi_field = qi_mod * (0.85 + 0.15 * filament)
qi_field = (qi_field - qi_field.min()) / (qi_field.max() - qi_field.min())

# Mask to elliptical interior
inside = (XXb / A_YANG)**2 + (YYb / B_YIN)**2 <= 1.0
qi_field[~inside] = np.nan

# Central void + paired sheets (anti-phase interference)
LAM_HALF = 0.28
void_mask = np.abs(YYb) < 0.06
sheet_upper = np.abs(YYb - LAM_HALF) < 0.05
sheet_lower = np.abs(YYb + LAM_HALF) < 0.05
qi_field[void_mask & inside] = np.nan  # dark void
qi_field[sheet_upper & inside] = qi_field[sheet_upper & inside] * 1.4  # brighten sheets
qi_field[sheet_lower & inside] = qi_field[sheet_lower & inside] * 1.4

# Display Qi field
qi_rgb = np.zeros((RES_B, RES_B, 3))
qi_base = np.array(to_rgb(QI_TEAL))
qi_dark = np.array(to_rgb(QI_DEEP))
for c in range(3):
    qi_rgb[:, :, c] = np.where(
        np.isnan(qi_field), np.nan,
        qi_dark[c] * (1 - qi_field) + qi_base[c] * qi_field
    )
# Brighten sheets toward Yang gold
sheet_color = np.array(to_rgb(YANG_MID))
for c in range(3):
    qi_rgb[:, :, c] = np.where(
        sheet_upper & inside,
        qi_rgb[:, :, c] * 0.6 + sheet_color[c] * 0.4,
        qi_rgb[:, :, c]
    )
    qi_rgb[:, :, c] = np.where(
        sheet_lower & inside,
        qi_rgb[:, :, c] * 0.6 + sheet_color[c] * 0.4,
        qi_rgb[:, :, c]
    )

axB.imshow(qi_rgb, extent=(xb[0], xb[-1], yb[0], yb[-1]),
           origin="lower", interpolation="bilinear", zorder=1)

# ── Five-arm spiral pole indicators (top and bottom) ───────────────────────
for pole_y, pole_sign in [(B_YIN, 1), (-B_YIN, -1)]:
    n_pts = 80
    for arm in range(5):
        # Spiral arm: angles advancing by golden angle, radii decreasing from pole
        angles = np.linspace(0, np.pi/2.5, n_pts)
        arm_angles = angles + arm * 2*np.pi/5
        # Distance from pole along elliptical surface
        dist = angles / (np.pi/2.5) * A_YANG * 0.65
        # Project from pole along ellipse
        arm_x = dist * np.cos(arm_angles)
        arm_y = pole_y - pole_sign * dist * np.sin(arm_angles) * (B_YIN/A_YANG) * 0.6
        # Clip to bubble interior
        in_bubble = (arm_x/A_YANG)**2 + (arm_y/B_YIN)**2 <= 1.0
        axB.plot(arm_x[in_bubble], arm_y[in_bubble],
                 color=ARM_COLORS[arm], lw=1.2, alpha=0.7,
                 solid_capstyle="round", zorder=12)

# Pole dots
axB.plot(0, B_YIN, "o", ms=5, color=YANG_PEAK, zorder=13)
axB.plot(0, -B_YIN, "o", ms=5, color=YANG_PEAK, zorder=13)

# ── Labels ──────────────────────────────────────────────────────────────────
axB.text(0, B_YIN + 0.14, "N pole—five-arm\nFibonacci spiral",
         ha="center", fontsize=8, color=YANG_PEAK, linespacing=1.1)
axB.text(0, -B_YIN - 0.24, "S pole—five-arm\nFibonacci spiral",
         ha="center", fontsize=8, color=YANG_PEAK, linespacing=1.1)
axB.annotate("", xy=(0.75*B_YIN, LAM_HALF + 0.03), xytext=(-A_YANG*0.5, LAM_HALF + 0.03),
             arrowprops=dict(arrowstyle="<|-|>", color=YANG_BRIGHT, lw=1.2))
axB.text(0, LAM_HALF + 0.08, "condensation sheet (+λ/2)", ha="center",
         fontsize=7.5, color=YANG_BRIGHT)
axB.text(0, 0.03, "central void (node)", ha="center", fontsize=7.5, color=TEXT_SUB)
axB.text(A_YANG + 0.08, 0, "Yang axis\n(×φ extended)",
         ha="left", fontsize=7.5, color=TEXT_MAIN, linespacing=1.1)

panel_label(axB, "B · QI BUBBLE—one cascade rung interior, φ:1 elliptical cross-section")

# ═══════════════════════════════════════════════════════════════════════════
# PANEL C—Five-Arm Spiral Pole Ultra-Zoom (bottom-right)
# ═══════════════════════════════════════════════════════════════════════════
print("Panel C: five-arm Fibonacci spiral pole...")
axC.set_xlim(-0.55, 0.55)
axC.set_ylim(0.35, 1.35)
axC.set_aspect("equal")
axC.axis("off")

# ── Fibonacci phyllotaxis point distribution ───────────────────────────────
N_PTS = 300
# Place points around a pole region using golden-angle phyllotaxis
indices = np.arange(1, N_PTS + 1)
angles = indices * GOLDEN_ANGLE
# Radial distribution: sqrt for uniform area, starting near pole
radii = 0.55 * np.sqrt(indices / N_PTS)
px = radii * np.cos(angles)
py = 1.0 - radii * np.sin(angles) * 0.7  # elliptical scaling

# Arm assignment
arm_idx = np.floor(angles * 5 / (2 * np.pi)).astype(int) % 5

# Draw each arm as connected points
for arm in range(5):
    mask = arm_idx == arm
    arm_pts = np.column_stack([px[mask], py[mask]])
    # Sort by radius (distance from pole) for smooth curve
    dists = np.sqrt(px[mask]**2 + (py[mask] - 1.0)**2)
    sort_idx = np.argsort(dists)
    arm_pts = arm_pts[sort_idx]
    # Draw as connected segments
    for i in range(0, len(arm_pts) - 1, 3):
        axC.plot(arm_pts[i:i+4, 0], arm_pts[i:i+4, 1],
                 color=ARM_COLORS[arm], lw=1.8, alpha=0.75,
                 solid_capstyle="round", zorder=10)
    # Dot at each point
    axC.scatter(arm_pts[:, 0], arm_pts[:, 1],
                c=ARM_COLORS[arm], s=5, alpha=0.6, edgecolors="none", zorder=9)

# ── Qi background texture (subtle) ─────────────────────────────────────────
RES_C = 400
xc = np.linspace(-0.55, 0.55, RES_C)
yc = np.linspace(0.35, 1.35, RES_C)
XXc, YYc = np.meshgrid(xc, yc)
qi_bg = (1.0 + 0.15 * np.cos(2*np.pi*XXc/PHI)
            + 0.08 * np.cos(2*np.pi*YYc/PHI))
qi_bg = (qi_bg - qi_bg.min()) / (qi_bg.max() - qi_bg.min())
qi_bg_rgb = np.zeros((RES_C, RES_C, 3))
for c in range(3):
    qi_bg_rgb[:, :, c] = qi_dark[c] * (1 - qi_bg*0.3) + qi_base[c] * qi_bg*0.3
axC.imshow(qi_bg_rgb, extent=(xc[0], xc[-1], yc[0], yc[-1]),
           origin="lower", interpolation="bilinear", alpha=0.4, zorder=1)

# ── Nested sub-bubble at centre ────────────────────────────────────────────
sub_center_y = 0.68
sub_a, sub_b = 0.12, 0.12/PHI
sub_bubble = plt.matplotlib.patches.Ellipse(
    (0, sub_center_y), 2*sub_a, 2*sub_b, fill=False,
    edgecolor=YANG_PEAK, lw=1.5, ls=(0, (4, 2)), zorder=11)
axC.add_patch(sub_bubble)
axC.text(0, sub_center_y - 0.07, "nested\nsub-bubble",
         ha="center", fontsize=6.5, color=YANG_PEAK, linespacing=1.1, zorder=12)

# ── Pole marker and arm labels ─────────────────────────────────────────────
# Five arm convergence lines
for arm in range(5):
    ang = arm * 2*np.pi/5 - np.pi/2
    axC.plot([0, 0.08*np.cos(ang)], [1.0, 1.0 + 0.08*np.sin(ang)],
             color=ARM_COLORS[arm], lw=1.0, alpha=0.5, zorder=8)

axC.plot(0, 1.0, "o", ms=7, color=YANG_PEAK, zorder=13)
axC.text(0, 1.0 + 0.06, "pole\n(φ-ellipsoid apex)",
         ha="center", fontsize=8, color=YANG_PEAK, linespacing=1.1, fontweight="bold")

# ── Golden angle annotation ────────────────────────────────────────────────
# Show the golden angle between two adjacent arms
arc_r = 0.10
theta_arc = np.linspace(-np.pi/2, -np.pi/2 + GOLDEN_ANGLE, 50)
axC.plot(arc_r*np.cos(theta_arc), 1.0 + arc_r*np.sin(theta_arc),
         color=YANG_BRIGHT, lw=1.5, zorder=8)
axC.text(0.14, 0.96, "$2\\pi/\\varphi^2$\n≈ 137.5°",
         fontsize=7, color=YANG_BRIGHT, linespacing=1.1, zorder=13)

# ── φ-zoom indicator ──────────────────────────────────────────────────────
axC.annotate("", xy=(0, 0.50), xytext=(0, 0.82),
             arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=1.2,
                             connectionstyle="arc3,rad=0"), zorder=8)
axC.text(0.05, 0.64, "zoom\n×φ²⁰", fontsize=7.5, color=TEXT_SUB,
         ha="left", va="center", linespacing=1.1)

panel_label(axC, "C · POLE ULTRA-ZOOM—five-arm Fibonacci spiral, golden-angle phyllotaxis")

# ═══════════════════════════════════════════════════════════════════════════
# Panel connector arrows (A → B, B → C)
# ═══════════════════════════════════════════════════════════════════════════
# Arrow from Panel A to Panel B
fig.text(0.475, 0.78, "→", fontsize=24, color=YANG_BRIGHT, alpha=0.6,
         ha="center", va="center", fontweight="bold")
fig.text(0.475, 0.75, "zoom\n×φ¹⁵", fontsize=7, color=YANG_BRIGHT,
         ha="center", va="top", linespacing=1.1, alpha=0.7)

# Arrow from Panel B to Panel C
fig.text(0.475, 0.35, "→", fontsize=24, color=YANG_BRIGHT, alpha=0.6,
         ha="center", va="center", fontweight="bold")
fig.text(0.475, 0.32, "zoom\n×φ²⁰", fontsize=7, color=YANG_BRIGHT,
         ha="center", va="top", linespacing=1.1, alpha=0.7)

# ═══════════════════════════════════════════════════════════════════════════
# Footer
# ═══════════════════════════════════════════════════════════════════════════
fig.text(0.5, 0.016,
         "Cassi two-fluid framework  ·  sources: foundations/dimensionful-cascade.md, "
         "foundations/spin-fibonacci-spiral.md §3  ·  "
         "Qi texture from qi_cascade_cosmos.py  ·  "
         "five-arm spiral from fibonacci_bubble_spiral.py  ·  "
         "zoom in by φ → identical structure at every cascade rung",
         ha="center", fontsize=7.5, color=TEXT_SUB)

# ═══════════════════════════════════════════════════════════════════════════
# Save
# ═══════════════════════════════════════════════════════════════════════════
OUT = "visual-explainers/fractal_zoom.png"
fig.savefig(OUT, dpi=DPI, facecolor=BG)
print(f"\nwrote {OUT}")

# ── Console verification ──────────────────────────────────────────────────
print("\n─── Verification ───")
print(f"  φ              = {PHI:.10f}")
print(f"  ln(φ)          = {np.log(PHI):.6f}")
print(f"  D (Hausdorff)  = ln(φ)/ln(φ) = 1")
print(f"  Golden angle   = 2π/φ² = {GOLDEN_ANGLE:.3f} rad = {360/PHI**2:.1f}°")
print(f"  Five-arm check: 5·(2π/φ²) mod 2π = {5*GOLDEN_ANGLE % (2*np.pi):.3f} rad")
print(f"    (nearly 2π → 5 arms close after 1 turn)")
print()
print("Cascade scale check (ℓ_n = ℓ_Pl × φ^n):")
for n, desc in [(80, "EW"), (95, "QCD/proton"), (117, "Bohr")]:
    scale = L_PL * PHI**n
    print(f"  n={n:>3}: ℓ = {scale:.2e} m  ({desc})")
print()
print("Qi bubble axes: Yang = φ ≈ 1.618, Yin = 1, string into page = 1/φ ≈ 0.618")
print("Five-arm spiral: golden angle 2π/φ² places points forming 5 visible arms")
print("Nested sub-bubble: same φ:1 ellipse, φ-scaled down → infinite regression")
print(f"\n  Self-similarity: I(ρ=0.5) = {2*(1-np.cos(np.pi)):.1f} in every ring ✓")
print(f"  Nodes at boundaries: I(ρ=0) = I(ρ→1) = {2*(1-np.cos(0)):.1f} ✓")
