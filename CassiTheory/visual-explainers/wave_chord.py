#!/usr/bin/env python3
"""
Wave Chord—damped-wave two-fluid simulation with Qi coherence feedback.

Solves the 2D damped wave equation with φ-dependent wave speed AND a dynamic
coherence field Qi that self-reinforces the standing wave pattern.

The key feedback loop:
    standing waves → high Qi → reduced damping → waves persist → Qi sustained

PDE:
    ∂_t E_Y = V_Y,   ∂_t V_Y = ∇·(c²(r)∇E_Y) − γ_eff·V_Y − λ·tanh(E_Y−φE_I)
    ∂_t E_I = V_I,   ∂_t V_I = ∇·(c²(r)∇E_I) − γ_eff·V_I + λ·tanh(E_Y−φE_I)
    ∂_t Qi  = α_Q·|E_Y|·|E_I| − δ_Q·Qi
    c²(r) = c₀² · |r−φ|/(α+|r−φ|)
    γ_eff = γ₀ · max(0, 1 − β·Qi/Q̄_i)

Run:  python visual-explainers/wave_chord.py
Out:  visual-explainers/wave_chord.png  +  wave_chord_final.png
"""

import numpy as np
import time

# ─────────────────────────────────────────────────────────────────────────────
# Framework parameters
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
LAM   = 0.05          # conversion rate λ (saturating via tanh)
GAMMA = 0.015         # base wave damping γ₀ (modulated by Qi)
C0    = 0.85          # base wave speed c₀
ALPHA = 0.20          # c² valley width

# Qi coherence parameters
ALPHA_Q = 0.02        # Qi growth rate from standing-wave coherence
DELTA_Q = 0.002       # Qi friction decay (slow—coherence persists)
BETA    = 0.8         # Qi → damping reduction strength (at Q̄, damping → 20% of γ₀)

# ─────────────────────────────────────────────────────────────────────────────
# Numerical parameters
# ─────────────────────────────────────────────────────────────────────────────
N = 256
L = 24.0
DT = 0.008
# Snapshot window: dense sampling of peak-contrast period
STEPS_SNAP = [0, 400, 800, 1000, 1500, 2000, 3000, 6000]
MAX_STEP = max(STEPS_SNAP)

dx = L / N
INIT_TOTAL = None

def make_field():
    global INIT_TOTAL
    x = np.linspace(0, L, N, endpoint=False)
    y = np.linspace(0, L, N, endpoint=False)
    XX, YY = np.meshgrid(x, y)
    EY = 1.0 + 0.32 * np.cos(2 * np.pi * XX / PHI)
    EI = 1.0 + 0.32 * np.cos(2 * np.pi * (YY - 0.25))
    VY = np.zeros_like(EY)
    VI = np.zeros_like(EY)
    # Qi initialized from initial coherence: |EY|·|EI| at t=0
    Qi = np.abs(EY) * np.abs(EI)
    INIT_TOTAL = EY.sum() + EI.sum()
    return EY, EI, VY, VI, Qi

EY, EI, VY, VI, Qi = make_field()

# ═══════════════════════════════════════════════════════════════════════════
# Physical terms
# ═══════════════════════════════════════════════════════════════════════════

def c_sq(r):
    """Wave speed squared: de-resonance TRAP—zero at r=φ, broad valley."""
    return C0**2 * np.abs(r - PHI) / (ALPHA + np.abs(r - PHI))

def laplacian_var_c2(f, c2):
    """∇·(c² ∇f) with central differences and half-point averaging of c²."""
    c2_xp = 0.5 * (c2 + np.roll(c2, -1, axis=1))
    c2_xm = 0.5 * (np.roll(c2, 1, axis=1) + c2)
    fp = np.roll(f, -1, axis=1) - f
    fm = f - np.roll(f, 1, axis=1)
    div_x = (c2_xp * fp - c2_xm * fm) / dx**2
    c2_yp = 0.5 * (c2 + np.roll(c2, -1, axis=0))
    c2_ym = 0.5 * (np.roll(c2, 1, axis=0) + c2)
    fp_y = np.roll(f, -1, axis=0) - f
    fm_y = f - np.roll(f, 1, axis=0)
    div_y = (c2_yp * fp_y - c2_ym * fm_y) / dx**2
    return div_x + div_y

def rhs(ey, ei, vy, vi, qi):
    """Return (a_Y, a_I) = accelerations.  Uses stage-local velocities and Qi."""
    ey_c = np.clip(ey, 0.05, 5.0)
    ei_c = np.clip(ei, 0.05, 5.0)
    r = ey_c / ei_c
    c2 = c_sq(r)
    wY = laplacian_var_c2(ey, c2)
    wI = laplacian_var_c2(ei, c2)
    conv = -LAM * np.tanh(ey - PHI * ei)
    # Qi-modulated damping: high Qi → low damping (waves persist)
    qi_mean = qi.mean() + 1e-10
    gamma_eff = GAMMA * np.maximum(0.0, 1.0 - BETA * qi / qi_mean)
    aY = wY - gamma_eff * vy + conv
    aI = wI - gamma_eff * vi - conv
    return aY, aI

def qi_rhs(ey, ei, qi):
    """Qi evolution: coherence source from |EY|·|EI|, friction decay."""
    coherence_source = ALPHA_Q * np.abs(ey) * np.abs(ei)
    friction_decay = DELTA_Q * qi
    return coherence_source - friction_decay

# ═══════════════════════════════════════════════════════════════════════════
# Standard RK4 for dE/dt = V,  dV/dt = F(E, V, Qi),  dQi/dt = G(E, Qi)
# ═══════════════════════════════════════════════════════════════════════════

def step_rk4(ey, ei, vy, vi, qi, dt):
    """One RK4 step for the 5-field system (EY, EI, VY, VI, Qi)."""
    # Stage 1
    k1e_y, k1e_i = vy, vi
    a1y, a1i = rhs(ey, ei, vy, vi, qi)
    k1v_y, k1v_i = a1y, a1i
    k1q = qi_rhs(ey, ei, qi)

    # Stage 2
    ey2 = ey + (dt/2)*k1e_y;  ei2 = ei + (dt/2)*k1e_i
    vy2 = vy + (dt/2)*k1v_y;  vi2 = vi + (dt/2)*k1v_i
    qi2 = qi + (dt/2)*k1q
    k2e_y, k2e_i = vy2, vi2
    a2y, a2i = rhs(ey2, ei2, vy2, vi2, qi2)
    k2v_y, k2v_i = a2y, a2i
    k2q = qi_rhs(ey2, ei2, qi2)

    # Stage 3
    ey3 = ey + (dt/2)*k2e_y;  ei3 = ei + (dt/2)*k2e_i
    vy3 = vy + (dt/2)*k2v_y;  vi3 = vi + (dt/2)*k2v_i
    qi3 = qi + (dt/2)*k2q
    k3e_y, k3e_i = vy3, vi3
    a3y, a3i = rhs(ey3, ei3, vy3, vi3, qi3)
    k3v_y, k3v_i = a3y, a3i
    k3q = qi_rhs(ey3, ei3, qi3)

    # Stage 4
    ey4 = ey + dt*k3e_y;  ei4 = ei + dt*k3e_i
    vy4 = vy + dt*k3v_y;  vi4 = vi + dt*k3v_i
    qi4 = qi + dt*k3q
    k4e_y, k4e_i = vy4, vi4
    a4y, a4i = rhs(ey4, ei4, vy4, vi4, qi4)
    k4v_y, k4v_i = a4y, a4i
    k4q = qi_rhs(ey4, ei4, qi4)

    # Assemble
    ey_new = ey + (dt/6)*(k1e_y + 2*k2e_y + 2*k3e_y + k4e_y)
    ei_new = ei + (dt/6)*(k1e_i + 2*k2e_i + 2*k3e_i + k4e_i)
    vy_new = vy + (dt/6)*(k1v_y + 2*k2v_y + 2*k3v_y + k4v_y)
    vi_new = vi + (dt/6)*(k1v_i + 2*k2v_i + 2*k3v_i + k4v_i)
    qi_new = qi + (dt/6)*(k1q + 2*k2q + 2*k3q + k4q)
    return ey_new, ei_new, vy_new, vi_new, qi_new

# ═══════════════════════════════════════════════════════════════════════════
# Integration
# ═══════════════════════════════════════════════════════════════════════════
print(f"N={N}  L={L:.0f}  c₀={C0}  α={ALPHA}  γ₀={GAMMA}  λ={LAM}  dt={DT}")
print(f"Qi: α_Q={ALPHA_Q}  δ_Q={DELTA_Q}  β={BETA}")
print(f"Feedback: standing waves → Qi → reduced γ → waves persist → Qi sustained")
t0 = time.time()

snapshots = [(0, EY.copy(), EI.copy(), Qi.copy())]

for t in range(1, MAX_STEP + 1):
    EY, EI, VY, VI, Qi = step_rk4(EY, EI, VY, VI, Qi, DT)
    # Mass rescaling
    s = INIT_TOTAL / (EY.sum() + EI.sum() + 1e-12)
    EY *= s; EI *= s
    # Floor clamp
    EY = np.maximum(EY, 0.01)
    EI = np.maximum(EI, 0.01)
    Qi = np.maximum(Qi, 0.0)
    if t in STEPS_SNAP:
        r_clamped = np.clip(EY, 0.05, 5.0) / np.clip(EI, 0.05, 5.0)
        c2_arr = c_sq(r_clamped)
        r_mean = r_clamped.mean()
        qi_mean = Qi.mean()
        gamma_eff_mean = GAMMA * max(0.0, 1.0 - BETA * qi_mean / (qi_mean + 1e-10))
        total = EY.sum() + EI.sum()
        print(f"  step {t:>6}  r̄={r_mean:.4f}  r̄/φ={r_mean/PHI:.4f}  "
              f"r_std={r_clamped.std():.4f}  "
              f"Q̄={qi_mean:.4f}  γ_eff={gamma_eff_mean:.5f}  "
              f"c²∈[{c2_arr.min():.4f},{c2_arr.max():.4f}]  "
              f"EY∈[{EY.min():.4f},{EY.max():.4f}]  "
              f"EI∈[{EI.min():.4f},{EI.max():.4f}]")
        snapshots.append((t, EY.copy(), EI.copy(), Qi.copy()))

elapsed = time.time() - t0
r_final = np.clip(EY, 0.05, 5.0) / np.clip(EI, 0.05, 5.0)
print(f"done: {MAX_STEP} steps in {elapsed:.1f}s  r̄={r_final.mean():.4f}  "
      f"r̄/φ={r_final.mean()/PHI:.4f}  r_std={r_final.std():.4f}  "
      f"Q̄={Qi.mean():.4f}")

# ═══════════════════════════════════════════════════════════════════════════
# Visualization—4 rows: E_Y, E_I, r, Qi
# ═══════════════════════════════════════════════════════════════════════════
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm

BG = "#060612"
YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
TEXT_MAIN, TEXT_SUB, RING = "#e0e0f0", "#a0a0c0", "#303050"
QI_COLOR = "#20d0a0"  # teal for Qi

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
QI_CMAP = LinearSegmentedColormap.from_list(
    "qi", [BG, "#0a2a20", "#104a38", "#188a68", QI_COLOR, "#80ffc0"])

# Pre-compute all fields and shared color scales
r_fields = []
for t_val, ey, ei, qi in snapshots:
    r = np.clip(ey, 0.05, 5.0) / np.clip(ei, 0.05, 5.0)
    r_fields.append(r)

all_r = np.concatenate([r.ravel() for r in r_fields])
r_vmin = float(np.percentile(all_r, 2))
r_vmax = float(np.percentile(all_r, 98))
r_vmin = min(r_vmin, PHI - 0.3)
r_vmax = max(r_vmax, PHI + 0.3)

all_qi = np.concatenate([s[3].ravel() for s in snapshots])
qi_vmax = float(np.percentile(all_qi, 99))
qi_vmax = max(qi_vmax, 0.01)
print(f"r scale: [{r_vmin:.3f}, {r_vmax:.3f}]  Qi scale: [0, {qi_vmax:.4f}]")

n_cols = len(snapshots)
fig, axes = plt.subplots(4, n_cols, figsize=(3.3 * n_cols, 10.5), dpi=160)
fig.subplots_adjust(left=0.06, right=0.97, top=0.87, bottom=0.08,
                    hspace=0.22, wspace=0.05)

col_titles = ["initial (t=0)"] + [f"t={s[0]}" for s in snapshots[1:]]

vmin_ey = max(min(s[1].min() for s in snapshots), 1e-4)
vmax_ey = max(s[1].max() for s in snapshots)
vmin_ei = max(min(s[2].min() for s in snapshots), 1e-4)
vmax_ei = max(s[2].max() for s in snapshots)

for col, (t_val, ey, ei, qi) in enumerate(snapshots):
    r = r_fields[col]
    axes[0, col].imshow(ey, extent=[0, L, 0, L], origin="lower",
                         cmap=LIN_GOLD, norm=LogNorm(vmin=vmin_ey, vmax=vmax_ey),
                         interpolation="bilinear")
    axes[1, col].imshow(ei, extent=[0, L, 0, L], origin="lower",
                         cmap=LIN_GOLD, norm=LogNorm(vmin=vmin_ei, vmax=vmax_ei),
                         interpolation="bilinear")
    axes[2, col].imshow(r, extent=[0, L, 0, L], origin="lower",
                         cmap=DIVERGE, vmin=r_vmin, vmax=r_vmax,
                         interpolation="bilinear")
    axes[3, col].imshow(qi, extent=[0, L, 0, L], origin="lower",
                         cmap=QI_CMAP, vmin=0, vmax=qi_vmax,
                         interpolation="bilinear")
    for ax in [axes[0, col], axes[1, col], axes[2, col], axes[3, col]]:
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
axes[3, 0].text(-0.22, 0.5, "Qi\n(coherence)", transform=axes[3, 0].transAxes,
                 fontsize=9.5, color=QI_COLOR, ha="right", va="center")

fig.suptitle("WAVE CHORD—de-resonance trapping + Qi coherence feedback",
             fontsize=15, fontweight="bold", color=YANG_PEAK, y=0.955)
fig.text(0.5, 0.915,
         f"∂_t Qi = α_Q·|EY|·|EI| − δ_Q·Qi  ·  γ_eff = γ₀·(1−β·Qi/Q̄)  ·  "
         f"α_Q={ALPHA_Q}, δ_Q={DELTA_Q}, β={BETA}  ·  "
         f"N={N}², γ₀={GAMMA}, λ={LAM}",
         ha="center", fontsize=7.8, color=TEXT_SUB)
fig.text(0.5, 0.02,
         "Qi (teal, bottom row): coherence density—high where standing waves are "
         "phase-locked  ·  feedback: high Qi → low γ_eff → waves persist → Qi sustained  ·  "
         "the checkerboard SELF-REINFORCES through Qi",
         ha="center", fontsize=7.8, color=TEXT_SUB, style="italic")

OUT = "visual-explainers/wave_chord.png"
fig.savefig(OUT, dpi=160, facecolor=BG)
print(f"wrote {OUT}")

# High-res final frame—4 panels
fig2, (ax1, ax2, ax3, ax4) = plt.subplots(1, 4, figsize=(32, 8), dpi=200)
plt.subplots_adjust(0, 0, 1, 1, wspace=0.02)
ey_last = snapshots[-1][1]
ei_last = snapshots[-1][2]
qi_last = snapshots[-1][3]
ax1.imshow(ey_last, extent=[0, L, 0, L], origin="lower", cmap=LIN_GOLD,
           norm=LogNorm(vmin=vmin_ey, vmax=vmax_ey), interpolation="bilinear")
ax1.set_title("E_Y (Yang)", color=YANG_BRIGHT, fontsize=12, pad=8)
ax2.imshow(ei_last, extent=[0, L, 0, L], origin="lower", cmap=LIN_GOLD,
           norm=LogNorm(vmin=vmin_ei, vmax=vmax_ei), interpolation="bilinear")
ax2.set_title("E_I (Yin)", color=YIN_LIGHT, fontsize=12, pad=8)
rf = r_fields[-1]
ax3.imshow(rf, extent=[0, L, 0, L], origin="lower", cmap=DIVERGE,
           vmin=r_vmin, vmax=r_vmax, interpolation="bilinear")
ax3.set_title(f"r = E_Y/E_I (t={snapshots[-1][0]})", color=TEXT_MAIN, fontsize=12, pad=8)
ax4.imshow(qi_last, extent=[0, L, 0, L], origin="lower", cmap=QI_CMAP,
           vmin=0, vmax=qi_vmax, interpolation="bilinear")
ax4.set_title(f"Qi (coherence, t={snapshots[-1][0]})", color=QI_COLOR, fontsize=12, pad=8)
for ax in [ax1, ax2, ax3, ax4]:
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
OUT2 = "visual-explainers/wave_chord_final.png"
fig2.savefig(OUT2, dpi=200, facecolor=BG)
print(f"wrote {OUT2}")
plt.close("all")
