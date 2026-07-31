#!/usr/bin/env python3
"""
String-Bubble-Cascade: 3D damped-wave two-fluid PDE simulation
===============================================================

The vibrating string's spiral of 5 coherence-channel arms becomes a pentagon
at the widest part of the Qi gate's pinch, expands into a spheroid, then meets
the string's anti-phase, triggering the φ-cascade.

Stages:
  1. Vibrating string: two counter-propagating spiral wave packets along z
  2. Pentagon at the pinch: m=5 mode emerges at equator as c² trap engages
  3. Spheroid (bubble): trapped energy forms triaxial φ-ellipsoid
  4. Cascade: anti-phase meeting releases wake waves at φ-scaled radii

Run:  python visual-explainers/string_bubble_cascade.py       # N=64, ~3-4 min
      python visual-explainers/string_bubble_cascade.py --N 96  # high-res, ~13 min
"""

import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LogNorm

# ─── Constants ───────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
SPIRAL_PITCH = 2 * np.pi / np.log(PHI)  # ≈ 13.06 rad per e-fold

# House palette (from spiral_string.py)
BG = "#060612"
TEXT_MAIN = "#e0e0f0"
TEXT_SUB = "#a0a0c0"
YANG_PEAK = "#ffe060"
YIN_LIGHT = "#4a2a8e"
YIN_MID = "#2a1a5e"
GREEN_SAFE = "#2ecc71"
SADDLE = "#ff6b6b"
RING = "#303050"
YANG_MID = "#9a6a1a"
WU_XING = ["#1a3a5c", "#2d6a4f", "#c0392b", "#d4a017", "#7d6e3a"]

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

# ─── CLI ─────────────────────────────────────────────────────────────────────
N_default = 64
steps_default = 15500
if "--N" in sys.argv:
    idx = sys.argv.index("--N")
    N_default = int(sys.argv[idx + 1])
if "--steps" in sys.argv:
    idx = sys.argv.index("--steps")
    steps_default = int(sys.argv[idx + 1])

N = N_default
L = 12.0
dx = L / N
dt = 0.006
steps = steps_default
save_interval = 100

# PDE parameters
c0 = 0.6
alpha_c2 = 0.15       # sharper c² valley—tighter r→φ pinning
gamma = 0.02           # light damping
lam = 0.1              # λ = 1/(2w) = 0.1 for w=5

# Initial condition parameters
E0 = 1.0               # background density
A_amp = 0.3            # wave packet amplitude
sigma_z = L / 8        # packet width along z
sigma_r = L / 8        # transverse width at equator
z_max = L / 4          # pole positions
eps5 = 0.05            # 5-fold seed amplitude
ell0 = L / 4           # logarithmic reference length for spiral

# Damping sponge (contingency—enabled if sponge_width > 0)
sponge_width = 0.0     # set to e.g. 2.0 if wrapping contaminates Panel E
sponge_ramp = 0.5

# ─── Grid ────────────────────────────────────────────────────────────────────
x = np.linspace(-L/2, L/2, N)
y = np.linspace(-L/2, L/2, N)
z = np.linspace(-L/2, L/2, N)
X, Y, Z = np.meshgrid(x, y, z, indexing='ij')  # axes: 0=x, 1=y, 2=z
R_xy = np.sqrt(X**2 + Y**2)  # radial distance in xy-plane
theta_xy = np.arctan2(Y, X)

# z-dependent quantities
z_flat = z  # shape (N,)
theta_z = SPIRAL_PITCH * np.log(np.maximum((z_flat + L/2 + dx) / ell0, 1e-6))
sigma0_z = np.full(N, sigma_r)  # constant transverse width—finite at all z
sigma_x_z = PHI * sigma0_z
sigma_y_z = sigma0_z

# Broadcast to 3D
theta_3d = theta_z[np.newaxis, np.newaxis, :]       # (1, 1, N)
sigma_x_3d = sigma_x_z[np.newaxis, np.newaxis, :]   # (1, 1, N)
sigma_y_3d = sigma_y_z[np.newaxis, np.newaxis, :]   # (1, 1, N)

# Gaussian packet envelopes along z (same for all bubbles—parallel chords)
z_N = -L/4   # forward packet center
z_S = +L/4   # anti-phase packet center
G_N = np.exp(-(Z - z_N)**2 / (2 * sigma_z**2))
G_S = np.exp(-(Z - z_S)**2 / (2 * sigma_z**2))

# ─── Multi-bubble lattice ────────────────────────────────────────────────────
bubble_centers = [(0.0, 0.0)]  # single bubble at origin
n_bubbles = len(bubble_centers)
n_strings = 5
A_amp_per = A_amp     # full amplitude for single bubble
A_ring_per = 0.15     # full ring amplitude
r0_ring = 0.8
sigma_ring = 0.4
sigma_z_ring = 1.5
print(f"  Lattice: {n_bubbles} bubbles × {n_strings} strings each")

# Initialize fields
EY = np.full((N, N, N), E0)
EI = np.full((N, N, N), E0)
VY = np.zeros((N, N, N))
VI = np.zeros((N, N, N))

for bx, by in bubble_centers:
    # Shifted coordinates for this bubble
    Xb = X - bx
    Yb = Y - by
    Rb = np.sqrt(Xb**2 + Yb**2)
    theta_b = np.arctan2(Yb, Xb)

    # Transverse profile centered at bubble position
    T_env_b = np.exp(-(Xb**2 / (2*sigma_x_3d**2 + 1e-12) +
                        Yb**2 / (2*sigma_y_3d**2 + 1e-12)))
    T_5fold_b = 1.0 + eps5 * np.cos(5.0 * theta_b + theta_3d)
    T_b = T_env_b * T_5fold_b

    # ── z-axis chord strings (forward + anti-phase packets) ──────────────
    EY_fwd_b = A_amp_per * G_N * T_b * np.cos(theta_3d + 5*theta_b)
    EI_fwd_b = A_amp_per * G_N * T_b * np.cos(theta_3d + 5*theta_b + np.pi/2)
    EY_anti_b = A_amp_per * G_S * T_b * np.cos(theta_3d + 5*theta_b + np.pi)
    EI_anti_b = A_amp_per * G_S * T_b * np.cos(theta_3d + 5*theta_b + np.pi + np.pi/2)

    EY += EY_fwd_b + EY_anti_b
    EI += EI_fwd_b + EI_anti_b

    # z-axis velocities: right-traveling for forward, left-traveling for anti-phase
    dEY_fwd_dz = np.gradient(EY_fwd_b, dx, axis=2)
    dEI_fwd_dz = np.gradient(EI_fwd_b, dx, axis=2)
    dEY_anti_dz = np.gradient(EY_anti_b, dx, axis=2)
    dEI_anti_dz = np.gradient(EI_anti_b, dx, axis=2)
    VY += -c0 * dEY_fwd_dz + c0 * dEY_anti_dz
    VI += -c0 * dEI_fwd_dz + c0 * dEI_anti_dz

    # ── 5 radial strings—bubble boundary in xy-plane ───────────────────
    for i in range(n_strings):
        theta_i = 2 * np.pi * i / n_strings
        dtheta = np.arctan2(np.sin(theta_b - theta_i), np.cos(theta_b - theta_i))
        ang_env = np.exp(-dtheta**2 / (2 * (np.pi/7)**2))
        rad_env = np.exp(-(Rb - r0_ring)**2 / (2 * sigma_ring**2))
        z_env = np.exp(-Z**2 / (2 * sigma_z_ring**2))
        ring = A_ring_per * rad_env * z_env * ang_env

        EY_ring = ring * np.cos(5*theta_b + theta_3d)
        EI_ring = ring * np.cos(5*theta_b + theta_3d + np.pi/2)
        EY += EY_ring
        EI += EI_ring

        # Outward radial velocity from bubble center: V = -c₀ · ∂(pert)/∂r
        r_safe = Rb + 1e-12
        ur_x, ur_y = Xb / r_safe, Yb / r_safe
        dEY_dr = ur_x * np.gradient(EY_ring, dx, axis=0) + ur_y * np.gradient(EY_ring, dx, axis=1)
        dEI_dr = ur_x * np.gradient(EI_ring, dx, axis=0) + ur_y * np.gradient(EI_ring, dx, axis=1)
        VY += -c0 * dEY_dr
        VI += -c0 * dEI_dr
mass0 = np.sum(EY + EI)

# CFL check
cfl = c0 * dt / dx
print(f"  CFL: c₀·dt/dx = {c0}×{dt}/{dx:.4f} = {cfl:.4f}")

# ─── PDE helpers ─────────────────────────────────────────────────────────────

def c2_field(EY, EI):
    """c²(r) = c₀² · |r−φ| / (α + |r−φ|) —de-resonance trap at r=φ."""
    r = EY / (EI + 1e-12)
    eps_r = np.abs(r - PHI)
    return c0**2 * eps_r / (alpha_c2 + eps_r)


def div_c2_grad(f, c2):
    """∇·(c²∇f) with half-point face averaging, 3D periodic."""
    result = np.zeros_like(f)
    for ax in range(3):
        c2_face = 0.5 * (c2 + np.roll(c2, -1, axis=ax))
        flux = c2_face * (np.roll(f, -1, axis=ax) - f) / dx
        result += (flux - np.roll(flux, 1, axis=ax)) / dx
    return result


def sponge_damping(VY, VI):
    """Damping sponge at boundaries to prevent wrapping (contingency)."""
    if sponge_width <= 0:
        return VY, VI
    r_rel = R_xy / (L/2)
    ramp = 0.5 * (1.0 + np.tanh((r_rel - (0.5 - sponge_width/L)) / sponge_ramp))
    mask = np.where(r_rel > 0.45, ramp, 1.0)
    return VY * mask, VI * mask


def rhs(EY, EI, VY, VI):
    """Right-hand side of the damped-wave PDE system."""
    c2 = c2_field(EY, EI)
    lap_EY = div_c2_grad(EY, c2)
    lap_EI = div_c2_grad(EI, c2)

    conv = lam * (EY - PHI * EI)  # conversion term

    dEY_dt = VY
    dVY_dt = lap_EY - gamma * VY - conv
    dEI_dt = VI
    dVI_dt = lap_EI - gamma * VI + conv  # note: +conv for EI (anti-phase)

    return dEY_dt, dVY_dt, dEI_dt, dVI_dt


def rk4_step(EY, EI, VY, VI):
    """One RK4 step for the second-order damped-wave system."""
    dEY1, dVY1, dEI1, dVI1 = rhs(EY, EI, VY, VI)

    dEY2, dVY2, dEI2, dVI2 = rhs(
        EY + 0.5*dt*dEY1, EI + 0.5*dt*dEI1,
        VY + 0.5*dt*dVY1, VI + 0.5*dt*dVI1)

    dEY3, dVY3, dEI3, dVI3 = rhs(
        EY + 0.5*dt*dEY2, EI + 0.5*dt*dEI2,
        VY + 0.5*dt*dVY2, VI + 0.5*dt*dVI2)

    dEY4, dVY4, dEI4, dVI4 = rhs(
        EY + dt*dEY3, EI + dt*dEI3,
        VY + dt*dVY3, VI + dt*dVI3)

    EY_new = EY + (dt/6.0) * (dEY1 + 2*dEY2 + 2*dEY3 + dEY4)
    EI_new = EI + (dt/6.0) * (dEI1 + 2*dEI2 + 2*dEI3 + dEI4)
    VY_new = VY + (dt/6.0) * (dVY1 + 2*dVY2 + 2*dVY3 + dVY4)
    VI_new = VI + (dt/6.0) * (dVI1 + 2*dVI2 + 2*dVI3 + dVI4)

    # Mass conservation: rescale E_Y, E_I only (not V)
    total = np.sum(EY_new + EI_new)
    scale = mass0 / max(total, 1e-12)
    EY_new *= scale
    EI_new *= scale

    # Damping sponge
    VY_new, VI_new = sponge_damping(VY_new, VI_new)

    return EY_new, EI_new, VY_new, VI_new


# ─── Diagnostics functions ───────────────────────────────────────────────────

def angular_spectrum(EY_eq):
    """Compute angular mode power P(m) from equatorial slice of EY.
    EY_eq: (N, N) slice at z = N//2."""
    # Radial mask: 0.2 < r < 0.7 * r_max
    r_max = L/2
    r_mask = (R_xy[:, :, 0] > 0.2 * r_max) & (R_xy[:, :, 0] < 0.7 * r_max)

    # Bin by theta into 72 angular bins
    n_bins = 72
    theta_bins = np.linspace(-np.pi, np.pi, n_bins + 1)
    theta_centers = 0.5 * (theta_bins[:-1] + theta_bins[1:])

    # Radial-weighted angular profile
    profile = np.zeros(n_bins)
    weights = np.zeros(n_bins)
    for i in range(n_bins):
        mask = r_mask & (theta_xy[:, :, 0] >= theta_bins[i]) & (theta_xy[:, :, 0] < theta_bins[i+1])
        w = np.sum(mask)
        if w > 0:
            profile[i] = np.sum(EY_eq[mask]) / w
            weights[i] = w

    # Subtract azimuthal mean (DC / m=0) to measure angular VARIATION, not absolute power.
    # The axisymmetric Gaussian envelope dominates m=0; without subtraction it drowns all modes.
    profile_var = profile - np.mean(profile)
    fft = np.fft.fft(profile_var)
    P_m = np.abs(fft[:11])**2  # modes 0..10 (m=0 is now ~0 by construction)
    # Normalize by non-DC power so fractions reflect relative angular structure
    total = np.sum(P_m[1:]) + 1e-12
    return P_m / total


def radial_energy_profile(EY_eq, EI_eq):
    """Radial energy profile E_rad(r) at equator."""
    energy = EY_eq**2 + EI_eq**2
    r_max = L/2
    n_bins = 50
    r_bins = np.linspace(0, r_max, n_bins + 1)
    r_centers = 0.5 * (r_bins[:-1] + r_bins[1:])

    profile = np.zeros(n_bins)
    R_2d = R_xy[:, :, 0]  # (N,N) radial grid at equator
    for i in range(n_bins):
        mask = (R_2d >= r_bins[i]) & (R_2d < r_bins[i+1])
        count = np.sum(mask)
        if count > 0:
            profile[i] = np.sum(energy[mask]) / count
    return r_centers, profile


def rms_extents(EY, EI):
    """Compute RMS extent of perturbation energy distribution in x, y, z.
    Uses (EY-E0)²+(EI-E0)² to isolate spatial structure from uniform background."""
    energy_pert = (EY - E0)**2 + (EI - E0)**2
    total = np.sum(energy_pert) + 1e-12

    x_c = np.sum(X * energy_pert) / total
    y_c = np.sum(Y * energy_pert) / total
    z_c = np.sum(Z * energy_pert) / total

    sx = np.sqrt(np.sum((X - x_c)**2 * energy_pert) / total)
    sy = np.sqrt(np.sum((Y - y_c)**2 * energy_pert) / total)
    sz = np.sqrt(np.sum((Z - z_c)**2 * energy_pert) / total)
    return sx, sy, sz


def coherence_extents(EY, EI):
    """Compute RMS extent of coherence-weighted distribution.
    Weights regions where r → φ—this measures the actual bubble shape,
    not the total energy spread (which thermalizes across the domain)."""
    r = EY / (EI + 1e-12)
    # Gaussian weight centered at r=φ—captures where c² trap pins coherence
    weight = np.exp(-(r - PHI)**2 / (2 * 0.08**2))
    total = np.sum(weight) + 1e-12

    x_c = np.sum(X * weight) / total
    y_c = np.sum(Y * weight) / total
    z_c = np.sum(Z * weight) / total

    sx = np.sqrt(np.sum((X - x_c)**2 * weight) / total)
    sy = np.sqrt(np.sum((Y - y_c)**2 * weight) / total)
    sz = np.sqrt(np.sum((Z - z_c)**2 * weight) / total)
    return sx, sy, sz


n_snapshots = steps // save_interval + 1
snapshot_steps = []
eq_energy_t = []
rms_sx_t, rms_sy_t, rms_sz_t = [], [], []
coh_sx_t, coh_sy_t, coh_sz_t = [], [], []   # coherence-weighted (bubble shape)
r_mean_t = []
P_m_history = []
radial_profiles = []   # list of (r_centers, profile) tuples
EY_eq_snapshots = []   # for panels
EY_xz_stage3, EI_xz_stage3 = None, None    # saved at t≈1200 for Panel C
eq_slice_t0 = EY[:, :, N//2]
eq_slice_EI_t0 = EI[:, :, N//2]
EY_xz_t0 = EY[:, N//2, :].copy()  # save for Panel A
eq_energy_t0 = np.sum(eq_slice_t0**2 + eq_slice_EI_t0**2)
eq_energy_t.append(eq_energy_t0)
sx0, sy0, sz0 = rms_extents(EY, EI)
rms_sx_t.append(sx0); rms_sy_t.append(sy0); rms_sz_t.append(sz0)
r_eq0 = np.mean(eq_slice_t0 / (eq_slice_EI_t0 + 1e-12))
csx0, csy0, csz0 = coherence_extents(EY, EI)
coh_sx_t.append(csx0); coh_sy_t.append(csy0); coh_sz_t.append(csz0)
r_mean_t.append(r_eq0)
P_m_history.append(angular_spectrum(eq_slice_t0))
r_c, r_prof = radial_energy_profile(eq_slice_t0, eq_slice_EI_t0)
radial_profiles.append((r_c, r_prof))
EY_eq_snapshots.append(("t=0", eq_slice_t0, eq_slice_EI_t0))
snapshot_steps.append(0)

# ─── Evolution ───────────────────────────────────────────────────────────────
print(f"\n  Grid: {N}³,  L={L},  dt={dt},  steps={steps}")
print(f"  Anti-phase meeting expected at t ≈ {(L/4)/c0:.1f} (step ~{int((L/4)/(c0*dt))})")
print(f"  Evolving", end="", flush=True)

for step in range(1, steps + 1):
    EY, EI, VY, VI = rk4_step(EY, EI, VY, VI)

    if step % save_interval == 0 or step == steps:
        eq_EY = EY[:, :, N//2]
        eq_EI = EI[:, :, N//2]

        eq_energy_t.append(np.sum(eq_EY**2 + eq_EI**2))
        sx, sy, sz = rms_extents(EY, EI)
        rms_sx_t.append(sx); rms_sy_t.append(sy); rms_sz_t.append(sz)
        r_mean_t.append(np.mean(eq_EY / (eq_EI + 1e-12)))
        csx, csy, csz = coherence_extents(EY, EI)
        coh_sx_t.append(csx); coh_sy_t.append(csy); coh_sz_t.append(csz)
        P_m_history.append(angular_spectrum(eq_EY))
        r_c, r_prof = radial_energy_profile(eq_EY, eq_EI)
        radial_profiles.append((r_c, r_prof))
        snapshot_steps.append(step)

        tag = f"t={step}"
        EY_eq_snapshots.append((tag, eq_EY, eq_EI))

    # Capture xz slice near step 15000 for Panel C (late-time bubble structure)
    if EY_xz_stage3 is None and step >= 15000:
        EY_xz_stage3 = EY[:, N//2, :].copy()
        EI_xz_stage3 = EI[:, N//2, :].copy()
print(" done.\n")

# Convert histories to arrays
eq_energy_t = np.array(eq_energy_t)
rms_sx_t = np.array(rms_sx_t)
rms_sy_t = np.array(rms_sy_t)
coh_sx_t = np.array(coh_sx_t)
coh_sy_t = np.array(coh_sy_t)
coh_sz_t = np.array(coh_sz_t)
rms_sz_t = np.array(rms_sz_t)
r_mean_t = np.array(r_mean_t)
P_m_arr = np.array(P_m_history)  # (n_snapshots, 11)
snapshot_steps = np.array(snapshot_steps)

# ─── Find key time indices ───────────────────────────────────────────────────
meeting_step_est = int((L/4) / (c0 * dt))  # ~833
idx_meeting = np.argmin(np.abs(snapshot_steps - meeting_step_est))

# Find where equatorial energy peaks (trapping)
idx_peak = np.argmax(eq_energy_t)

# Find pentagon snapshot: step closest to 1000
idx_stage2 = np.argmin(np.abs(snapshot_steps - 1000))

# Find spheroid/bubble snapshot: step closest to 15000 (late-time)
idx_bubble = np.argmin(np.abs(snapshot_steps - 15000))

# Final snapshot for cascade
idx_stage4 = -1

# Angular mode analysis at stage 2—measure on energy field (matches what the eye sees)
P_m_stage2 = P_m_arr[idx_stage2]
dominant_m = np.argmax(P_m_stage2[1:]) + 1  # skip m=0
m5_frac = P_m_stage2[5] / (np.sum(P_m_stage2[1:]) + 1e-12) * 100
# Pentagon confirmed if m=5 carries >30% of angular power (strong 5-fold signal)
pentagon_confirmed = m5_frac > 30.0

# Spheroid aspect ratios at bubble formation time—coherence-weighted (where r → φ)
asp_xy = coh_sx_t[idx_bubble] / max(coh_sy_t[idx_bubble], 1e-12)
asp_xz = coh_sx_t[idx_bubble] / max(coh_sz_t[idx_bubble], 1e-12)
spheroid_confirmed = abs(asp_xy - PHI) < 0.3
# Cascade analysis at final step
r_at_pinch = r_mean_t[idx_stage4]
r_c_final, r_prof_final = radial_profiles[-1]
# Find cascade wake-wave peaks in radial profile
r_min = 0.5
peak_idx_list = []
peak_radii_list = []
try:
    from scipy.signal import find_peaks
    peak_idx, _ = find_peaks(r_prof_final, height=np.max(r_prof_final)*0.05, distance=3)
    peak_radii = r_c_final[peak_idx]
    peak_idx_list = list(peak_idx)
    peak_radii_list = list(peak_radii)
except ImportError:
    pass

if len(peak_radii_list) == 0:
    # Simple peak finding without scipy
    for i in range(2, len(r_prof_final) - 2):
        if (r_prof_final[i] > r_prof_final[i-1] and r_prof_final[i] > r_prof_final[i-2] and
            r_prof_final[i] > r_prof_final[i+1] and r_prof_final[i] > r_prof_final[i+2] and
            r_prof_final[i] > np.max(r_prof_final)*0.05 and r_c_final[i] > r_min):
            peak_idx_list.append(i)
            peak_radii_list.append(r_c_final[i])

peak_radii = np.array(peak_radii_list)
peak_idx_arr = np.array(peak_idx_list, dtype=int)

phi_scaling_confirmed = False
phi_ratio_mean = 0.0
if len(peak_radii) >= 2:
    ratios = peak_radii[1:] / (peak_radii[:-1] + 1e-12)
    phi_ratio_mean = np.mean(ratios)
    phi_scaling_confirmed = abs(phi_ratio_mean - PHI) < 0.3

# ─── Figure ──────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 16), dpi=160, facecolor=BG)

# ── PANEL A: xz cross-section at t=0—vibrating string ─────────────────────
axA = fig.add_axes([0.04, 0.55, 0.29, 0.40])
axA.set_facecolor(BG)
tag0, eq_EY0, eq_EI0 = EY_eq_snapshots[0]
# xz cross-section at y = N//2 (saved before evolution)
EY_xz_0 = EY_xz_t0  # (N, N)—rows=x, cols=z
imA = axA.imshow(EY_xz_0.T, origin='lower', cmap='inferno',
                  extent=[-L/2, L/2, -L/2, L/2], aspect='auto',
                  norm=Normalize(vmin=E0-0.5*A_amp, vmax=E0+0.5*A_amp))

# Mark packet centers
axA.axhline(y=z_N, color=YANG_PEAK, lw=1.0, ls='--', alpha=0.7)
axA.axhline(y=z_S, color=YIN_LIGHT, lw=1.0, ls='--', alpha=0.7)
axA.annotate("forward\npacket", xy=(-L/4, z_N), fontsize=7, color=YANG_PEAK,
             ha='center', va='bottom')
axA.annotate("anti-phase\npacket", xy=(L/4, z_S), fontsize=7, color=YIN_LIGHT,
             ha='center', va='top')

# Equator line
axA.axhline(y=0, color=TEXT_SUB, lw=0.5, ls=':', alpha=0.4)

axA.set_xlabel("x (Yang axis)", fontsize=8, color=TEXT_SUB)
axA.set_ylabel("z (string axis)", fontsize=8, color=TEXT_SUB)
axA.set_title("A: Stage 1—Vibrating String (t=0)", fontsize=11, color=YANG_PEAK, pad=6)

# On-panel equation for spiral
axA.text(0.02, 0.96, r"$\Theta(z)=\frac{2\pi}{\ln\varphi}\ln\frac{z+L/2}{\ell_0}$",
         transform=axA.transAxes, fontsize=7.5, color=TEXT_SUB, va="top")
axA.text(0.02, 0.91, f"pitch = {SPIRAL_PITCH:.2f} rad per e-fold",
         transform=axA.transAxes, fontsize=7, color=TEXT_SUB, va="top")

# ── PANEL B: xy cross-section at t≈1000—pentagon at pinch ─────────────────
axB = fig.add_axes([0.36, 0.55, 0.29, 0.40])
axB.set_facecolor(BG)

tagB, eq_EY_B, eq_EI_B = EY_eq_snapshots[idx_stage2]
energy_B = eq_EY_B**2 + eq_EI_B**2
imB = axB.imshow(energy_B.T, origin='lower', cmap='inferno',
                  extent=[-L/2, L/2, -L/2, L/2], aspect='auto')

# Overlay pentagon outline if m=5 is dominant
if pentagon_confirmed:
    # Find arm radii for pentagon vertices
    pent_r = 0.3 * L/2  # visual pentagon radius
    pent_angles = np.linspace(0, 2*np.pi, 6)
    pent_x = pent_r * np.cos(pent_angles)
    pent_y = pent_r * np.sin(pent_angles)
    axB.plot(pent_x, pent_y, color=YANG_PEAK, lw=2.0, alpha=0.8)
    axB.scatter(pent_x[:-1], pent_y[:-1], c=WU_XING, s=30, edgecolors='white', linewidth=0.5)

axB.set_xlabel("x (Yang axis)", fontsize=8, color=TEXT_SUB)
axB.set_ylabel("y (Yin axis)", fontsize=8, color=TEXT_SUB)
axB.set_title(f"B: Stage 2—Pentagon at Pinch (step {snapshot_steps[idx_stage2]})",
              fontsize=11, color=YANG_PEAK, pad=6)

axB.text(0.02, 0.96, f"Dominant mode: m={dominant_m} ({P_m_stage2[dominant_m]*100:.1f}%)",
         transform=axB.transAxes, fontsize=7.5, color=GREEN_SAFE if pentagon_confirmed else SADDLE, va="top")
axB.text(0.02, 0.91, f"m=5 fraction: {m5_frac:.1f}%",
         transform=axB.transAxes, fontsize=7, color=YANG_PEAK, va="top")
axB.text(0.02, 0.86, f"Pentagon: {'YES' if pentagon_confirmed else 'NO'}",
         transform=axB.transAxes, fontsize=7.5,
         color=GREEN_SAFE if pentagon_confirmed else SADDLE,
         fontweight='bold', va="top")

# ── PANEL C: xz ratio field—bubble coherence boundary ──────────────────
axC = fig.add_axes([0.68, 0.55, 0.29, 0.40])
axC.set_facecolor(BG)

# Use xz slices captured at step ~1100—right after anti-phase meeting
if EY_xz_stage3 is not None and EI_xz_stage3 is not None:
    ratio_xz = EY_xz_stage3 / (EI_xz_stage3 + 1e-12)
    imC = axC.imshow(ratio_xz.T, origin='lower', cmap='RdBu_r',
                      extent=[-L/2, L/2, -L/2, L/2], aspect='auto',
                      vmin=PHI-0.8, vmax=PHI+0.8)
else:
    imC = axC.imshow(np.ones((N,N))*PHI, origin='lower', cmap='RdBu_r',
                      extent=[-L/2, L/2, -L/2, L/2], aspect='auto',
                      vmin=PHI-0.8, vmax=PHI+0.8)

axC.set_xlabel("x (Yang axis)", fontsize=8, color=TEXT_SUB)
axC.set_ylabel("z (string axis)", fontsize=8, color=TEXT_SUB)
axC.set_title(f"C: Stage 3—Bubble r=E_Y/E_I (step {snapshot_steps[idx_bubble]})",
              fontsize=11, color=YANG_PEAK, pad=6)

axC.text(0.02, 0.96, f"r at pinch = {r_mean_t[idx_bubble]:.3f} (φ={PHI:.3f})",
         transform=axC.transAxes, fontsize=7.5, color=YANG_PEAK, va="top")
axC.text(0.02, 0.91, f"Coherence σ_x/σ_z = {coh_sx_t[idx_bubble]/max(coh_sz_t[idx_bubble],1e-12):.3f}",
         transform=axC.transAxes, fontsize=7.5, color=TEXT_SUB, va="top")
axC.text(0.02, 0.86, f"m=5 at step: {P_m_arr[idx_bubble,5]*100:.0f}%",
         transform=axC.transAxes, fontsize=7.5, color=YANG_PEAK, va="top")

# ── PANEL D: Angular mode power P(m) vs time ────────────────────────────────
axD = fig.add_axes([0.04, 0.06, 0.29, 0.42])
axD.set_facecolor(BG)

# Heatmap: x=time steps, y=m=1..10, color=log10(P_m)
P_m_display = P_m_arr[:, 1:11]  # m=1..10
P_m_log = np.log10(np.maximum(P_m_display, 1e-6))
imD = axD.pcolormesh(snapshot_steps, np.arange(1, 11), P_m_log.T,
                      cmap='inferno', shading='auto', vmin=-3, vmax=0)

# Mark anti-phase meeting
axD.axvline(x=snapshot_steps[idx_meeting], color=YANG_PEAK, lw=1.5, ls='--', alpha=0.8)
axD.annotate("anti-phase\nmeeting", xy=(snapshot_steps[idx_meeting], 9.5),
             fontsize=7, color=YANG_PEAK, ha='center', va='bottom')

# Highlight m=5 row
axD.axhline(y=5, color=YANG_PEAK, lw=1.0, alpha=0.3)

axD.set_xlabel("step", fontsize=8, color=TEXT_SUB)
axD.set_ylabel("angular mode m", fontsize=8, color=TEXT_SUB)
axD.set_yticks([1, 3, 5, 7, 9])
axD.set_title("D: Angular Mode Spectrum (m=5 emergence)", fontsize=11, color=YANG_PEAK, pad=6)

axD.text(0.02, 0.96, r"$P(m)=|\sum E_Y(r,\theta)e^{im\theta}|^2$",
         transform=axD.transAxes, fontsize=7.5, color=TEXT_SUB, va="top")

# ── PANEL E: xy cross-section at t=2500—cascade ───────────────────────────
axE = fig.add_axes([0.36, 0.06, 0.29, 0.42])
axE.set_facecolor(BG)

tagE, eq_EY_E, eq_EI_E = EY_eq_snapshots[idx_stage4]
# Show ratio field r = E_Y/E_I—cascade rings remain visible even when energy is uniform
ratio_E = eq_EY_E / (eq_EI_E + 1e-12)
imE = axE.imshow(ratio_E.T, origin='lower', cmap='RdBu_r',
                  extent=[-L/2, L/2, -L/2, L/2], aspect='auto',
                  vmin=PHI-0.6, vmax=PHI+0.6)
axE.set_xlabel("x (Yang axis)", fontsize=8, color=TEXT_SUB)
axE.set_ylabel("y (Yin axis)", fontsize=8, color=TEXT_SUB)
axE.set_title(f"E: Stage 4—Cascade r-field (step {snapshot_steps[idx_stage4]})",
              fontsize=11, color=YANG_PEAK, pad=6)

axE.text(0.02, 0.96, f"<r> at pinch = {r_at_pinch:.3f} (φ={PHI:.3f})",
         transform=axE.transAxes, fontsize=7.5, color=YANG_PEAK, va="top")
axE.text(0.02, 0.91, f"E_eq peak at step {snapshot_steps[idx_peak]}",
         transform=axE.transAxes, fontsize=7, color=TEXT_SUB, va="top")
axE.text(0.02, 0.86, f"Cascade: {'YES' if phi_scaling_confirmed else 'NO'}",
         transform=axE.transAxes, fontsize=7.5,
         color=GREEN_SAFE if phi_scaling_confirmed else SADDLE,
         fontweight='bold', va="top")

# ── PANEL F: Radial energy profile at t=2500 ────────────────────────────────
axF = fig.add_axes([0.68, 0.06, 0.29, 0.42])
axF.set_facecolor(BG)

axF.plot(r_c_final, r_prof_final, color=YANG_PEAK, lw=2.0, alpha=0.9)

# Vertical dashed lines at φ-scaled radii
r0_wake = 0.5  # estimated first wake peak
for n in range(4):
    rn = r0_wake * PHI**n
    if rn < L/2:
        axF.axvline(x=rn, color=TEXT_SUB, lw=0.8, ls=':', alpha=0.6)
        axF.annotate(f"$r_0\\varphi^{{{n}}}$", xy=(rn, axF.get_ylim()[1]*0.85),
                     fontsize=6.5, color=TEXT_SUB, ha='center', rotation=90, va='top')

# Mark detected peaks
if len(peak_radii) > 0:
    axF.scatter(peak_radii, r_prof_final[peak_idx_arr],
                c=GREEN_SAFE, s=30, marker='o', edgecolors='white', linewidth=0.5, zorder=10)
axF.set_xlabel("radius r", fontsize=8, color=TEXT_SUB)
axF.set_ylabel(r"$E_Y^2+E_I^2$", fontsize=8, color=TEXT_SUB)
axF.set_title("F: Cascade Wake Waves at φ-Scaled Radii", fontsize=11, color=YANG_PEAK, pad=6)

if len(peak_radii) >= 2:
    ratio_str = ", ".join([f"{peak_radii[i+1]/peak_radii[i]:.2f}" for i in range(min(3, len(peak_radii)-1))])
    axF.text(0.02, 0.96, f"Peak ratios: {ratio_str}",
             transform=axF.transAxes, fontsize=7.5, color=GREEN_SAFE, va="top")
    axF.text(0.02, 0.91, f"Mean φ-ratio = {phi_ratio_mean:.3f} (φ={PHI:.3f})",
             transform=axF.transAxes, fontsize=7.5,
             color=GREEN_SAFE if phi_scaling_confirmed else SADDLE, va="top")

# ─── Suptitle and key equations ──────────────────────────────────────────────
fig.suptitle("STRING-BUBBLE-CASCADE: 3D Damped-Wave Two-Fluid PDE",
             fontsize=16, fontweight="bold", color=YANG_PEAK, y=0.995)

# On-panel key equations across the bottom margin
fig.text(0.5, 0.005,
         r"$c^2(r)=c_0^2|r-\varphi|/(\alpha+|r-\varphi|) \rightarrow 0\; \mathrm{at}\; r=\varphi$"
         r"$\quad|\quad$"
         r"$\mathrm{conv}=-\lambda(E_Y-\varphi E_I)$ (anti-phase)"
         r"$\quad|\quad$"
         r"$w=5,\; b_i=\varphi^{-(2+i)},\; \lambda=1/(2\cdot5)=0.1$"
         r"$\quad|\quad$"
         r"$\Theta(z)=(2\pi/\ln\varphi)\ln(z/\ell_0)$",
         ha="center", fontsize=7.5, color=TEXT_SUB)

OUT = "visual-explainers/string_bubble_cascade.png"
fig.savefig(OUT, dpi=160, facecolor=BG)
print(f"wrote {OUT}")

# ─── Console Verification ────────────────────────────────────────────────────
print()
print("  === String-Bubble-Cascade PDE Verification ===")
print(f"  φ = {PHI:.6f}")
print(f"  Spiral pitch = 2π/ln(φ) = {SPIRAL_PITCH:.2f} rad per e-fold")
print(f"  String length = L/2 = {L/2:.1f}")
print(f"  Spiral turns across string = {SPIRAL_PITCH * np.log(((z_S+L/2+dx)/(z_N+L/2+dx))) / (2*np.pi):.1f}")
print()
print(f"  Stage 1 (t=0): String initialized")
print(f"    Forward packet at z={z_N:.1f}, anti-phase at z={z_S:.1f}")
print(f"    5-fold seed amplitude = {eps5}")
print(f"    Initial equatorial energy = {eq_energy_t[0]:.4e}")
print()
print(f"  Stage 2 (t≈{snapshot_steps[idx_stage2]}): Pentagon at pinch")
print(f"    Pentagon confirmed: {'YES' if pentagon_confirmed else 'NO (m=5 fraction ' + f'{m5_frac:.1f}% below 30% threshold)'}")
print(f"    m=5 fraction: {m5_frac:.1f}%")
print()
print(f"  Stage 3 (t≈{snapshot_steps[idx_bubble]}): Bubble formation")
print(f"    Aspect ratio σ_x/σ_y = {asp_xy:.3f} (target: φ={PHI:.3f})")
print(f"    Aspect ratio σ_x/σ_z = {asp_xz:.3f} (target: φ²={PHI**2:.3f})")
print(f"    Spheroid confirmed: {'YES' if spheroid_confirmed else 'NO'}")
print()
print(f"  Stage 4 (t≈{snapshot_steps[idx_stage4]}): Cascade")
print(f"    Ratio at pinch: <r> = {r_at_pinch:.4f} (target: φ={PHI:.4f})")
print(f"    Equatorial energy peak at step {snapshot_steps[idx_peak]} (E_eq = {eq_energy_t[idx_peak]:.4e})")
print(f"    Release at step {snapshot_steps[idx_stage4]} (E_eq = {eq_energy_t[idx_stage4]:.4e})")
if len(peak_radii) >= 2:
    print(f"    Wake wave peaks at radii: {', '.join([f'{r:.3f}' for r in peak_radii])}")
    print(f"    φ-scaling: mean r_n/r_{{n-1}} = {phi_ratio_mean:.3f} (target: φ={PHI:.3f})")
else:
    print(f"    Wake wave peaks: {'none detected above threshold' if len(peak_radii)==0 else f'only 1 ({peak_radii[0]:.3f})'}")
print(f"    Cascade confirmed: {'YES' if phi_scaling_confirmed else 'NO'}")
print()
print(f"  Grid: {N}³, dt={dt}, steps={steps}")
print(f"  CFL: {cfl:.4f}")
print(f"  Runtime parameters: c₀={c0}, α={alpha_c2}, γ={gamma}, λ={lam}")
print()
