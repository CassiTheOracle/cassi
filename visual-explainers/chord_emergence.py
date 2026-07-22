#!/usr/bin/env python3
"""
Chord emergence: a minimal 2D two-fluid PDE simulation.

Solves the governing equations from TOE.md §1.3 (diffusion + conversion +
chemotaxis), domain-averaged for simplicity (no bulk velocity):

    ∂_t E_Y  =   D ∇²E_Y  −  λ (E_Y − φ E_I)  −  (χ/φ) ∇·(E_Y ∇Φ)
    ∂_t E_I  =   D ∇²E_I  +  λ (E_Y − φ E_I)  +  χ     ∇·(E_I ∇Φ)
    ∇²Φ      = −4π G ρ ,   ρ = E_Y + E_I

The question: do two perpendicular anti-phase standing waves seeded into this
PDE spontaneously form the staggered checkerboard chord lattice?

Run:  python visual-explainers/chord_emergence.py
Out:  visual-explainers/chord_emergence.png
"""

import numpy as np
from numpy.fft import fft2, ifft2, fftfreq

# ─────────────────────────────────────────────────────────────────────────────
# Framework parameters  (TOE.md §1.3 + dimensionful-cascade.md)
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
LAM = 0.02          # conversion rate λ
DIFF = 0.08         # diffusion coefficient D
CHI  = 0.08         # Yin chemotactic mobility χ (small: pattern, not depletion)
CHI_Y = CHI / PHI   # Yang chemotactic mobility χ/φ

# ─────────────────────────────────────────────────────────────────────────────
# Numerical parameters
# ─────────────────────────────────────────────────────────────────────────────
N = 64                # grid points per dimension
L = 10.0              # domain size (periodic)
DT = 0.05             # time step
STEPS_SNAP = [0, 120, 240, 400]
MAX_STEP = max(STEPS_SNAP)

dx = L / N
x = np.linspace(0, L, N, endpoint=False)
y = np.linspace(0, L, N, endpoint=False)
XX, YY = np.meshgrid(x, y)

# Fourier frequencies for diffusion and Poisson equation
kx = 2 * np.pi * fftfreq(N, dx)
ky = 2 * np.pi * fftfreq(N, dx)
KX, KY = np.meshgrid(kx, ky)
K2 = KX**2 + KY**2
K2[0, 0] = 1.0               # avoid division by zero; DC mode handled separately
LAPLACIAN = -K2               # fft(∇²f) = -k² fft(f)

# ─────────────────────────────────────────────────────────────────────────────
# Initial conditions: perpendicular anti-phase standing waves at φ-scaled
# wavelengths. E_Y varies along x (long wavelength φ), E_I varies along y
# (short wavelength 1) with a quarter-wave offset (anti-phase).
# ─────────────────────────────────────────────────────────────────────────────
LAM_X = PHI         # Yang wake wavelength (long axis, φ-scaled)
LAM_Y_W = 1.0       # Yin wake wavelength (short axis)
EY0 = 1.0 + 0.3 * np.cos(2 * np.pi * XX / LAM_X)
EI0 = 1.0 + 0.3 * np.cos(2 * np.pi * (YY - LAM_Y_W/4) / LAM_Y_W)

EY = EY0.copy()
EI = EI0.copy()

snapshots = [(0, EY.copy(), EI.copy())]
INIT_TOTAL = EY.sum() + EI.sum()

# ─────────────────────────────────────────────────────────────────────────────
# Right-hand side (real-space nonlinear terms)
# ─────────────────────────────────────────────────────────────────────────────
def rhs(ey, ei):
    """Conversion + chemotaxis (diffusion is handled implicitly in Fourier)."""
    rho = ey + ei
    rho_k = fft2(rho)
    phi_k = np.where(K2 > 1e-12, rho_k / K2, 0.0)
    dphix_k, dphiy_k = 1j * KX * phi_k, 1j * KY * phi_k
    dphi_dx = np.real(ifft2(dphix_k))
    dphi_dy = np.real(ifft2(dphiy_k))
    div_ey_grad = (np.gradient(ey * dphi_dx, dx, axis=1) +
                   np.gradient(ey * dphi_dy, dx, axis=0))
    div_ei_grad = (np.gradient(ei * dphi_dx, dx, axis=1) +
                   np.gradient(ei * dphi_dy, dx, axis=0))
    rhs_ey = -LAM * (ey - PHI * ei) - CHI_Y * div_ey_grad
    rhs_ei = +LAM * (ey - PHI * ei) + CHI * div_ei_grad
    return rhs_ey, rhs_ei

# ─────────────────────────────────────────────────────────────────────────────
# RK2 step: spectral diffusion (exact) + explicit real-space nonlinear terms
# ─────────────────────────────────────────────────────────────────────────────
def step(ey, ei, dt):
    """RK2 midpoint with implicit spectral diffusion."""
    rey1, rei1 = rhs(ey, ei)
    ey_k, ei_k = fft2(ey), fft2(ei)
    decay_half = np.exp(DIFF * LAPLACIAN * dt / 2)
    ey_half_k = ey_k * decay_half + fft2(rey1) * dt / 2
    ei_half_k = ei_k * decay_half + fft2(rei1) * dt / 2
    ey_half = np.real(ifft2(ey_half_k))
    ei_half = np.real(ifft2(ei_half_k))
    rey2, rei2 = rhs(ey_half, ei_half)
    decay_full = np.exp(DIFF * LAPLACIAN * dt)
    ey_new_k = ey_k * decay_full + fft2(rey2) * dt
    ei_new_k = ei_k * decay_full + fft2(rei2) * dt
    return np.real(ifft2(ey_new_k)), np.real(ifft2(ei_new_k))

# ─────────────────────────────────────────────────────────────────────────────
# Integration loop
# ─────────────────────────────────────────────────────────────────────────────
print(f"N={N}  L={L:.0f}  λ={LAM}  D={DIFF}  χ={CHI}  dt={DT}")
next_snap = 1
for t in range(1, MAX_STEP + 1):
    EY, EI = step(EY, EI, DT)
    scale = INIT_TOTAL / (EY.sum() + EI.sum() + 1e-12)
    EY *= scale; EI *= scale
    if next_snap < len(STEPS_SNAP) and t >= STEPS_SNAP[next_snap]:
        r_mean = EY.mean() / EI.mean()
        print(f"  step {t:>4}  EY mean={EY.mean():.4f}  EI mean={EI.mean():.4f}"
              f"  r̄={r_mean:.4f}  r̄/φ={r_mean/PHI:.4f}")
        snapshots.append((t, EY.copy(), EI.copy()))
        next_snap += 1

r_final = EY.mean() / EI.mean()
print(f"done: r̄(E_Y/E_I) = {r_final:.4f}  (φ = {PHI:.6f}, ratio = {r_final/PHI:.4f})")

# ─────────────────────────────────────────────────────────────────────────────
# Visualization: E_Y, E_I, r = E_Y/E_I  ×  4 snapshots
# ─────────────────────────────────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

BG = "#060612"
YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
TEXT_MAIN, TEXT_SUB, RING = "#e0e0f0", "#a0a0c0", "#303050"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

DIVERGE = LinearSegmentedColormap.from_list(
    "diverge", [YIN_MID, YIN_DEEP, BG, YANG_DARK, YANG_PEAK])
LIN_GOLD = LinearSegmentedColormap.from_list(
    "gold", [BG, YIN_DEEP, YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK])

n_cols = len(snapshots)
fig, axes = plt.subplots(3, n_cols, figsize=(3.5 * n_cols, 8.5), dpi=160)
fig.subplots_adjust(left=0.06, right=0.96, top=0.86, bottom=0.10,
                    hspace=0.20, wspace=0.06)

col_titles = ["initial (t=0)"] + [f"t={s[0]}" for s in snapshots[1:]]

vmin_ey = min(s[1].min() for s in snapshots)
vmax_ey = max(s[1].max() for s in snapshots)
vmin_ei = min(s[2].min() for s in snapshots)
vmax_ei = max(s[2].max() for s in snapshots)

for col, (t_val, ey, ei) in enumerate(snapshots):
    r = np.clip(ey / (ei + 1e-12), 0.2, PHI * 3)
    axes[0, col].imshow(ey, extent=[0, L, 0, L], origin="lower",
                         cmap=LIN_GOLD, vmin=vmin_ey, vmax=vmax_ey,
                         interpolation="bilinear")
    axes[1, col].imshow(ei, extent=[0, L, 0, L], origin="lower",
                         cmap=LIN_GOLD, vmin=vmin_ei, vmax=vmax_ei,
                         interpolation="bilinear")
    axes[2, col].imshow(r, extent=[0, L, 0, L], origin="lower",
                         cmap=DIVERGE, vmin=PHI - 0.9, vmax=PHI + 0.9,
                         interpolation="bilinear")
    for ax in [axes[0, col], axes[1, col], axes[2, col]]:
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0, col].set_title(col_titles[col], fontsize=9.5, color=YANG_BRIGHT, pad=4)

axes[0, 0].text(-0.22, 0.5, "E_Y\n(Yang)", transform=axes[0, 0].transAxes,
                 fontsize=9.5, color=TEXT_MAIN, ha="right", va="center")
axes[1, 0].text(-0.22, 0.5, "E_I\n(Yin)", transform=axes[1, 0].transAxes,
                 fontsize=9.5, color=TEXT_MAIN, ha="right", va="center")
axes[2, 0].text(-0.22, 0.5, "r = E_Y/E_I", transform=axes[2, 0].transAxes,
                 fontsize=9.5, color=TEXT_MAIN, ha="right", va="center")

fig.suptitle("CHORD EMERGENCE — two-fluid PDE (diffusion + conversion + chemotaxis)",
             fontsize=15, fontweight="bold", color=YANG_PEAK, y=0.955)
fig.text(0.5, 0.910,
         f"λ={LAM}  D={DIFF}  χ={CHI}  χ_Y=χ/φ={CHI/PHI:.3f}  N={N}²  "
         f"init: anti-phase standing waves at λ_x=φ, λ_y=1  ·  mass conserved",
         ha="center", fontsize=8, color=TEXT_SUB)
fig.text(0.5, 0.035,
         "r = E_Y/E_I (bottom row): gold ≈ φ (attractor), indigo ≠ φ  —  "
         "watch the PDE decide whether a checkerboard emerges",
         ha="center", fontsize=8, color=TEXT_SUB, style="italic")

OUT = "visual-explainers/chord_emergence.png"
fig.savefig(OUT, dpi=160, facecolor=BG)
print(f"wrote {OUT}")
