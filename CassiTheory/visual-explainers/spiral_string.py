#!/usr/bin/env python3
"""Spiral String: 3D helix chord + Fibonacci pole projection
=============================================================

The chord string connecting the two poles of the triaxial phi-ellipsoid
does NOT vibrate in a 2D plane — it traces a 3D helix (spiral) because
the conversion term continuously rotates the (E_Y, E_I) doublet in its
internal SO(2) plane.

One full rotation per cascade rung: dTheta/d(ln z) = 2*pi/ln(phi).

At each pole, the helix endpoint projects as a pentagon when the Wu Xing
5-channel gate modulates the spiral at 5 equispaced phases (the 5 elements:
Water, Wood, Fire, Earth, Metal).

This script shows:
  Panel A: 3D bubble + spiral chord string + pole pentagons
  Panel B: Unwrapped spiral — z vs Theta with 5-phase Wu Xing bands
  Panel C: Pole projection — the pentagon traced by the rotating endpoint

Run:  python visual-explainers/spiral_string.py
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch, RegularPolygon
from mpl_toolkits.mplot3d import proj3d

PHI = (1 + np.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * np.pi / PHI**2  # ~137.508 deg

# House palette
BG = "#060612"
TEXT_MAIN = "#e0e0f0"
TEXT_SUB = "#a0a0c0"
YANG_PEAK = "#ffe060"
YIN_LIGHT = "#4a2a8e"
GREEN_SAFE = "#2ecc71"
SADDLE = "#ff6b6b"
WU_XING = ["#1a3a5c", "#2d6a4f", "#c0392b", "#d4a017", "#7d6e3a"]  # Water, Wood, Fire, Earth, Metal

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": "#303050",
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans",
})

# ─── Bubble geometry ─────────────────────────────────────────────────────────
AX, AY, AZ = PHI, 1.0, 1.0 / PHI  # triaxial ellipsoid axes
L_POLE = 2 * AZ  # pole-to-pole distance = 2/phi ~ 1.236
SPIRAL_PITCH = 2 * np.pi / np.log(PHI)  # one full turn per cascade rung: ~13.04 rad
N_TURNS = 3  # number of full spiral turns to show
N_PTS = 500

# ─── Compute spiral string ───────────────────────────────────────────────────
# The spiral: Theta(z) = Theta_0 + SPIRAL_PITCH * ln((z + AZ)/ell_0)
# We parametrize by z from -AZ to +AZ (south pole to north pole)
# At the poles (z = +/-AZ), the spiral radius goes to zero.
# The spiral radius follows the ellipsoid cross-section at that z:
#   r_ell(z) = sqrt(1 - z^2/AZ^2) * AX (if we're in x) ... 
# For simplicity, use a cylindrical spiral: r(z) = r_0 * sqrt(1 - z^2/AZ^2)
# where r_0 = AX (the equatorial radius along the long axis)

def spiral_xyz(z_vals, theta0=0, r0=AX):
    """Return x,y,z for the spiral string at given z positions."""
    x = np.zeros_like(z_vals)
    y = np.zeros_like(z_vals)
    for i, z in enumerate(z_vals):
        if abs(z) < 0.99 * AZ:
            # Ellipsoid radius at this z: cross-section of x^2/AX^2 + z^2/AZ^2 = 1
            r_ell = AX * np.sqrt(1 - (z / AZ)**2)
            r = r0 * np.sqrt(max(0, 1 - (z / AZ)**2))
            theta = theta0 + SPIRAL_PITCH * np.log((z + AZ) / (0.1 * AZ))
            x[i] = r * np.cos(theta)
            y[i] = r * np.sin(theta)
        else:
            x[i] = 0
            y[i] = 0
    return x, y

z_spiral = np.linspace(-AZ * 0.98, AZ * 0.98, N_PTS)
x_spiral, y_spiral = spiral_xyz(z_spiral)

# ─── Wu Xing 5-phase modulation ──────────────────────────────────────────────
# The 5 elements modulate the spiral at 5 equispaced phases.
# Each element corresponds to a 72-degree sector of the spiral.
# The pentagon at each pole has vertices at the 5 phase centers.

def wuxing_phase(theta):
    """Map angle theta to Wu Xing element index 0-4."""
    return int(np.floor((theta % (2 * np.pi)) / (2 * np.pi / 5))) % 5

# Phase of spiral at each pole
theta_spiral = SPIRAL_PITCH * np.log((z_spiral + AZ) / (0.1 * AZ))
theta_north = theta_spiral[-1] % (2 * np.pi)  # phase at north pole
theta_south = theta_spiral[0] % (2 * np.pi)   # phase at south pole

# Pentagon vertices at each pole (in the pole plane)
pentagon_radius = 0.25 * AX  # visual size of pentagon marker
def pentagon_vertices(theta_offset, r=pentagon_radius, z=AZ):
    """Return x,y,z for 5 pentagon vertices at given phase offset."""
    vx, vy, vz = [], [], []
    for i in range(5):
        angle = theta_offset + 2 * np.pi * i / 5 + np.pi / 2  # rotate so vertex is up
        vx.append(r * np.cos(angle))
        vy.append(r * np.sin(angle))
        vz.append(z)
    # Close the pentagon
    vx.append(vx[0])
    vy.append(vy[0])
    vz.append(vz[0])
    return vx, vy, vz

nx5, ny5, nz5 = pentagon_vertices(theta_north, z=AZ)
sx5, sy5, sz5 = pentagon_vertices(theta_south, z=-AZ)

# ─── Build figure ────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 10), dpi=150, facecolor=BG)

# ── PANEL A: 3D bubble + spiral string + pentagons ─────────────────────
ax3d = fig.add_axes([0.02, 0.08, 0.42, 0.88], projection='3d', facecolor=BG)
ax3d.set_facecolor(BG)

# Wireframe ellipsoid
u = np.linspace(0, 2 * np.pi, 80)
v = np.linspace(-np.pi / 2, np.pi / 2, 50)
x_ell = AX * np.outer(np.cos(u), np.cos(v))
y_ell = AY * np.outer(np.sin(u), np.cos(v))
z_ell = AZ * np.outer(np.ones_like(u), np.sin(v))
ax3d.plot_wireframe(x_ell, y_ell, z_ell, color=TEXT_SUB, alpha=0.12, lw=0.2)

# Spiral string — color-coded by Wu Xing element
for i in range(len(z_spiral) - 1):
    elem = wuxing_phase(theta_spiral[i])
    ax3d.plot(x_spiral[i:i+2], y_spiral[i:i+2], z_spiral[i:i+2],
              color=WU_XING[elem], lw=1.8, alpha=0.9)

# Chord reference line (straight z-axis)
ax3d.plot([0, 0], [0, 0], [-AZ * 1.3, AZ * 1.3],
          color=YANG_PEAK, lw=0.8, alpha=0.3, ls='--')

# Pentagon at north pole
ax3d.plot(nx5, ny5, nz5, color=YANG_PEAK, lw=2.0, alpha=0.9)
ax3d.scatter(nx5[:-1], ny5[:-1], [AZ]*5, c=WU_XING, s=40, edgecolors='white', linewidth=0.5, zorder=10)

# Pentagon at south pole
ax3d.plot(sx5, sy5, sz5, color=YANG_PEAK, lw=2.0, alpha=0.9)
ax3d.scatter(sx5[:-1], sy5[:-1], [-AZ]*5, c=WU_XING, s=40, edgecolors='white', linewidth=0.5, zorder=10)

# Pole markers
ax3d.scatter([0], [0], [AZ], c=YANG_PEAK, s=100, marker='*', edgecolors='white', linewidth=0.8, zorder=10)
ax3d.scatter([0], [0], [-AZ], c=YANG_PEAK, s=100, marker='*', edgecolors='white', linewidth=0.8, zorder=10)

ax3d.set_xlim(-AX * 1.3, AX * 1.3)
ax3d.set_ylim(-AY * 1.3, AY * 1.3)
ax3d.set_zlim(-AZ * 1.4, AZ * 1.4)
ax3d.set_box_aspect([AX, AY, AZ])
ax3d.axis('off')
ax3d.set_title("A: 3D Bubble + Spiral Chord String + Pole Pentagons",
               fontsize=11, color=YANG_PEAK, pad=12)

# ── PANEL B: Unwrapped spiral — z vs Theta with Wu Xing bands ──────────
ax_unwrap = fig.add_axes([0.50, 0.55, 0.47, 0.38])
ax_unwrap.set_facecolor(BG)

# Plot spiral: Theta vs z
ax_unwrap.plot(z_spiral, theta_spiral % (2 * np.pi), color=YANG_PEAK, lw=1.5, alpha=0.8)

# Wu Xing phase bands
for i in range(5):
    phi_lo = 2 * np.pi * i / 5
    phi_hi = 2 * np.pi * (i + 1) / 5
    ax_unwrap.axhspan(phi_lo, phi_hi, alpha=0.08, color=WU_XING[i])
    # Label at center of band
    ax_unwrap.text(-AZ * 0.9, (phi_lo + phi_hi) / 2,
                   ['Water', 'Wood', 'Fire', 'Earth', 'Metal'][i],
                   fontsize=7, color=WU_XING[i], ha='left', va='center',
                   fontweight='bold')

# Mark poles
ax_unwrap.axvline(x=-AZ, color=TEXT_SUB, ls=':', lw=0.8, alpha=0.5, label='South pole')
ax_unwrap.axvline(x=AZ, color=TEXT_SUB, ls=':', lw=0.8, alpha=0.5, label='North pole')

ax_unwrap.set_xlabel("z (chord axis)", fontsize=9, color=TEXT_SUB)
ax_unwrap.set_ylabel(r"$\Theta$ (radians mod $2\pi$)", fontsize=9, color=TEXT_SUB)
ax_unwrap.set_title("B: Unwrapped Spiral — z vs Theta with 5 Wu Xing Phase Bands",
                    fontsize=10, color=YANG_PEAK, pad=6)
ax_unwrap.set_xlim(-AZ * 1.05, AZ * 1.05)
ax_unwrap.set_ylim(0, 2 * np.pi)
ax_unwrap.set_yticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
ax_unwrap.set_yticklabels(['0', r'$\pi$/2', r'$\pi$', r'$3\pi$/2', r'$2\pi$'])
ax_unwrap.tick_params(labelsize=8)
ax_unwrap.legend(fontsize=7, loc='lower right')

# ── PANEL C: Pole projection — pentagon from spiral endpoint ───────────
ax_pole = fig.add_axes([0.50, 0.08, 0.22, 0.38])
ax_pole.set_facecolor(BG)
ax_pole.set_aspect('equal')

# Draw pentagon
pent_theta = np.linspace(0, 2 * np.pi, 6)
pent_x = pentagon_radius * np.cos(pent_theta + theta_north + np.pi / 2)
pent_y = pentagon_radius * np.sin(pent_theta + theta_north + np.pi / 2)
ax_pole.plot(pent_x, pent_y, color=YANG_PEAK, lw=2.0, alpha=0.9)

# 5 vertices colored by Wu Xing
for i in range(5):
    angle = theta_north + 2 * np.pi * i / 5 + np.pi / 2
    vx = pentagon_radius * np.cos(angle)
    vy = pentagon_radius * np.sin(angle)
    ax_pole.scatter(vx, vy, c=WU_XING[i], s=80, edgecolors='white', linewidth=0.8, zorder=5)
    # Element label
    label_r = pentagon_radius * 1.35
    ax_pole.text(label_r * np.cos(angle), label_r * np.sin(angle),
                 ['W', 'Wd', 'F', 'E', 'M'][i],
                 fontsize=7, color=WU_XING[i], ha='center', va='center', fontweight='bold')

# Spiral trace near pole (last few turns projected)
near_pole = z_spiral > 0.5 * AZ
ax_pole.plot(x_spiral[near_pole], y_spiral[near_pole],
             color=YANG_PEAK, lw=0.6, alpha=0.3)

# Center cross
ax_pole.axhline(y=0, color=TEXT_SUB, lw=0.3, alpha=0.3)
ax_pole.axvline(x=0, color=TEXT_SUB, lw=0.3, alpha=0.3)

ax_pole.set_xlim(-pentagon_radius * 1.8, pentagon_radius * 1.8)
ax_pole.set_ylim(-pentagon_radius * 1.8, pentagon_radius * 1.8)
ax_pole.set_title("C: North Pole Projection\nPentagon from 5 Wu Xing Phases",
                  fontsize=9, color=YANG_PEAK, pad=6)
ax_pole.set_xlabel("x", fontsize=8, color=TEXT_SUB)
ax_pole.set_ylabel("y", fontsize=8, color=TEXT_SUB)
ax_pole.tick_params(labelsize=7)

# ── PANEL D: Key equations + Wu Xing legend ────────────────────────────
ax_info = fig.add_axes([0.74, 0.08, 0.23, 0.38])
ax_info.set_facecolor(BG)
ax_info.set_xlim(0, 1)
ax_info.set_ylim(0, 1)
ax_info.axis('off')

equations = [
    ("SPIRAL STRING", YANG_PEAK, 12, "bold"),
    ("", TEXT_SUB, 6, "normal"),
    (r"$\Theta(z)=\frac{2\pi}{\ln\varphi}\ln\frac{z+\ell_z}{\ell_0}$", TEXT_MAIN, 9, "normal"),
    (r"$\frac{d\Theta}{d\ln z}=\frac{2\pi}{\ln\varphi}\approx 13.0$ rad", TEXT_MAIN, 9, "normal"),
    (r"One full turn per cascade rung $\Delta\ln z=\ln\varphi$", TEXT_MAIN, 9, "normal"),
    ("", TEXT_SUB, 6, "normal"),
    ("WU XING 5-CHANNEL GATE", YANG_PEAK, 11, "bold"),
    ("", TEXT_SUB, 5, "normal"),
    ("Each element = 72 deg phase sector of spiral", TEXT_MAIN, 8.5, "normal"),
    (r"$\varphi$ powers: $b_i=\varphi^{-k_i}$, $k_i\in\{3,4,5,6,7\}$", TEXT_MAIN, 8.5, "normal"),
    ("", TEXT_SUB, 5, "normal"),
    ("TWO-POLE PENTAGON", GREEN_SAFE, 11, "bold"),
    ("", TEXT_SUB, 5, "normal"),
    ("North: 5 spiral arms -> 5 pentagon vertices", TEXT_MAIN, 8.5, "normal"),
    ("South: 5 spiral arms -> 5 pentagon vertices", TEXT_MAIN, 8.5, "normal"),
    (r"Total: 10 vertices $\rightarrow \lambda=1/10$", GREEN_SAFE, 9.5, "bold"),
    ("", TEXT_SUB, 5, "normal"),
    (r"$C(5,2)=10=2\times 5$  $\checkmark$ self-consistent", TEXT_MAIN, 8.5, "normal"),
    ("", TEXT_SUB, 6, "normal"),
    ("EPISTEMIC: Derived from phi + cascade", TEXT_SUB, 7.5, "italic"),
    ("PDE rotation test: tracking dphi_5/dt", TEXT_SUB, 7.5, "italic"),
]

y = 0.97
for text, color, size, style in equations:
    if style == "italic":
        ax_info.text(0.02, y, text, transform=ax_info.transAxes,
                     fontsize=size, color=color, fontstyle='italic', va="top")
    else:
        ax_info.text(0.02, y, text, transform=ax_info.transAxes,
                     fontsize=size, color=color, fontweight=style, va="top")
    y -= 0.025 if text else 0.012
fig.suptitle("SPIRAL CHORD STRING: 3D Helix from SO(2) Doublet Rotation + Wu Xing Pentagon Poles",
             fontsize=15, fontweight="bold", color=YANG_PEAK, y=0.99)
fig.text(0.5, 0.975,
         r"Conversion term $\mathrm{conv}=-\lambda(E_Y-\varphi E_I)$ rotates $(E_Y,E_I)$ doublet $\rightarrow$ "
         r"$\Theta(z)\propto\ln z$ $\rightarrow$ "
         r"spiral string $\rightarrow$ rotating pentagon at each pole",
         ha="center", fontsize=8.5, color=TEXT_SUB)

# ── Console verification ───────────────────────────────────────────────
print()
print("  === Spiral String Verification ===")
print(f"  phi = {PHI:.6f}")
print(f"  Spiral pitch = 2*pi/ln(phi) = {SPIRAL_PITCH:.4f} rad per e-fold in z")
print(f"  Pole-to-pole distance L = 2/phi = {L_POLE:.4f}")
print(f"  Number of turns pole-to-pole: {SPIRAL_PITCH * np.log((AZ + AZ)/(0.1*AZ)) / (2*np.pi):.2f}")
print(f"  North pole phase: {np.degrees(theta_north):.1f} deg")
print(f"  South pole phase: {np.degrees(theta_south):.1f} deg")
print(f"  Phase difference: {np.degrees(theta_north - theta_south):.1f} deg")
print(f"  5/3 ratio check: 5/3 = {5/3:.4f} vs phi = {PHI:.4f} -> delta = {abs(5/3 - PHI):.4f}")
print()

OUT = "visual-explainers/spiral_string.png"
fig.savefig(OUT, dpi=150, facecolor=BG)
print(f"wrote {OUT}")
