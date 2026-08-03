"""
Path 10: Cassi saturation ceiling vs MOND — Ultra-Faint Dwarf Galaxy Test
=========================================================================

Tests the key prediction from Path 9 (`path9_cassi_vs_mond.py`):
  - Cassi full-coupling ceiling: v_obs/v_Newt <= sqrt(phi^6) = phi^3 ~ 4.24
    (SATURATES), with xi = phi^6 ~ 17.944 the derived Qi-gravity coupling:
    the max boost G_eff/G_N -> phi^6 at q -> 1
    (foundations/xi-derivation.md; revised 2026-08-03)
  - MOND:            v_obs/v_Newt ~ sqrt(a0/a)          (GROWS unboundedly)

Revised 2026-08-03: the earlier ceiling sqrt(phi) ~ 1.27 came from the
withdrawn approximate coupling G_eff/G_N = 1 + (phi-1)q and is obsolete.
The corrected coupling G_eff/G_N = 1 + (phi^6-1)q saturates at the derived
max boost phi^6 ~ 17.94, i.e. a velocity ceiling sqrt(phi^6) = phi^3 ~ 4.24
(reached only where q -> 1, i.e. rho << rho_ref — exactly the ultra-faint
regime).

Ultra-faint dwarfs (a << a0) are the decisive test case.
At a ~ 0.001 a0:
  Cassi predicts: ratio <= 4.24 (ceiling, phi^3)
  MOND predicts:  ratio ~ sqrt(1000) ~ 31

Data: observed line-of-sight velocity dispersions, half-light radii,
and estimated baryonic (stellar) masses for 8 classical + ultra-faint dwarfs.

Convention: v_circ = sqrt(3) * sigma_v  (isotropic virial)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

# ── Constants ──────────────────────────────────────────────────────────────
G       = 6.674e-11      # m^3 / (kg s^2)
M_sun   = 1.989e30       # kg
pc      = 3.086e16       # m
a0_mond = 1.2e-10        # m/s^2  (MOND acceleration scale)
PHI     = (1.0 + np.sqrt(5.0)) / 2.0   # golden ratio ~ 1.618
XI      = PHI ** 6                      # Qi-gravity coupling xi = phi^6 ~ 17.944
CEILING = np.sqrt(XI)                   # velocity ceiling sqrt(phi^6) = phi^3 ~ 4.24
                                         # (max boost G_eff/G_N = phi^6 at q -> 1)

# ── Dwarf Galaxy Catalog ───────────────────────────────────────────────────
# (name, sigma_v [km/s], r_half [pc], M_baryon [M_sun])
# Sources: Simon & Geha 2007, Walker et al. 2009, Martin et al. 2007,
#          Mateo 1998, Battaglia & Nipoti 2012 review
# Values are representative literature consensus.

dwarfs = [
    # Ultra-faint dwarfs (lowest mass, lowest acceleration)
    ("Segue 1",          3.7,    29,    1e3),
    ("Segue 2",          3.4,    35,    1e3),
    ("Willman 1",        4.0,    21,    1e5),
    ("Bootes I",         6.6,    12,   3e4),   # Martin et al. 2008: r_half ~ 12.8 pc
    ("Coma Berenices",   4.6,    11,   1e4),   # Martin et al. 2008: r_half ~ 11.0 pc
    # Classical dwarfs
    ("Draco",            9.1,   200,   3e5),
    ("Sculptor",         9.2,   280,   5e6),
    ("Fornax",          11.7,   700,   2e7),
]

# ── Computations ───────────────────────────────────────────────────────────
results = []

print("=" * 112)
print(f"PATH 10: CASSI {CEILING:.2f}x SATURATION CEILING vs MOND — ULTRA-FAINT DWARF GALAXY TEST")
print("=" * 112)
print()
print(f"{'Galaxy':<20} {'M_bary':>10} {'sigma_v':>8} {'v_obs':>8} {'v_Newt':>8} "
      f"{'v_Cassi':>8} {'v_MOND':>8} {'v_obs/':>8} {'MOND/':>8} {'Cassi':>8} {'ceil?':>7}")
print(f"{'':20} {'[M_sun]':>10} {'[km/s]':>8} {'[km/s]':>8} {'[km/s]':>8} "
      f"{'[km/s]':>8} {'[km/s]':>8} {'v_Newt':>8} {'v_Newt':>8} {'fit?':>8} "
      f"{'>' + f'{CEILING:.2f}':>7}")
print("-" * 112)

for name, sigma_v, r_half_pc, M_bary_msun in dwarfs:
    # Convert to SI
    M_kg   = M_bary_msun * M_sun
    r_m    = r_half_pc * pc
    sigma_ms = sigma_v * 1e3  # km/s -> m/s

    # Observed circular velocity (isotropic virial: v_circ = sqrt(3) * sigma)
    v_obs = np.sqrt(3) * sigma_ms  # m/s

    # Newtonian prediction at r_half
    v_Newt = np.sqrt(G * M_kg / r_m)  # m/s

    # Cassi prediction (saturated at the full-coupling ceiling)
    v_Cassi = CEILING * v_Newt  # m/s

    # MOND prediction (deep MOND limit: v^4 = G M a0)
    v_MOND = (G * M_kg * a0_mond) ** 0.25  # m/s

    # Ratios
    ratio_obs_Newt = v_obs / v_Newt
    ratio_MOND_Newt = v_MOND / v_Newt

    # Which model fits? Within factor 2 of observed
    cassi_ok = abs(np.log2(v_obs / v_Cassi)) < 1.0
    mond_ok  = abs(np.log2(v_obs / v_MOND)) < 1.0
    newt_ok  = abs(np.log2(v_obs / v_Newt)) < 1.0

    # Decisive test: does the observed boost exceed the Cassi ceiling?
    exceeded = ratio_obs_Newt > CEILING

    cassi_tag = "YES" if cassi_ok else "no"
    mond_tag  = "YES" if mond_ok else "no"
    ceil_tag  = "EXCEEDS" if exceeded else "ok"

    results.append({
        'name': name,
        'M_bary': M_bary_msun,
        'sigma_v': sigma_v,
        'r_half_pc': r_half_pc,
        'v_obs': v_obs / 1e3,      # km/s
        'v_Newt': v_Newt / 1e3,    # km/s
        'v_Cassi': v_Cassi / 1e3,  # km/s
        'v_MOND': v_MOND / 1e3,    # km/s
        'ratio_obs_Newt': ratio_obs_Newt,
        'ratio_MOND_Newt': ratio_MOND_Newt,
        'cassi_ok': cassi_ok,
        'mond_ok': mond_ok,
        'newt_ok': newt_ok,
        'exceeded': exceeded,
    })

    print(f"{name:<20} {M_bary_msun:>10.0e} {sigma_v:>8.1f} {v_obs/1e3:>8.2f} "
          f"{v_Newt/1e3:>8.3f} {v_Cassi/1e3:>8.3f} {v_MOND/1e3:>8.3f} "
          f"{ratio_obs_Newt:>8.1f} {ratio_MOND_Newt:>8.1f} {cassi_tag:>8} {ceil_tag:>7}")

print("-" * 112)

# ── Summary Statistics ─────────────────────────────────────────────────────
n = len(results)
n_cassi = sum(1 for r in results if r['cassi_ok'])
n_mond  = sum(1 for r in results if r['mond_ok'])
n_newt  = sum(1 for r in results if r['newt_ok'])
n_exceed = sum(1 for r in results if r['exceeded'])

print()
print("MODEL CONSISTENCY (within factor 2 of observed sigma_v):")
print(f"  Newtonian: {n_newt}/{n} galaxies")
print(f"  Cassi (sqrt(phi^6) = phi^3 = {CEILING:.2f}):  {n_cassi}/{n} galaxies")
print(f"  MOND (a0 = 1.2e-10 m/s^2): {n_mond}/{n} galaxies")
print(f"  Observed boost EXCEEDS the Cassi ceiling ({CEILING:.2f}x): {n_exceed}/{n} galaxies")

# Also compute median ratios
ratios = [r['ratio_obs_Newt'] for r in results]
print()
print(f"Median v_obs/v_Newt = {np.median(ratios):.1f}")
print(f"Range: [{min(ratios):.1f}, {max(ratios):.1f}]")
print(f"Cassi ceiling: {CEILING:.2f}")
print(f"MOND range for these masses: [{min(r['ratio_MOND_Newt'] for r in results):.1f}, "
      f"{max(r['ratio_MOND_Newt'] for r in results):.1f}]")

# ── The Verdict ────────────────────────────────────────────────────────────
print()
print("=" * 112)
print("VERDICT:")
print("=" * 112)

if n_exceed == 0:
    verdict = (f"(a) Cassi ceiling consistent — no dwarf exceeds v_obs/v_Newt = "
               f"{CEILING:.2f} (the phi^3 saturation ceiling)")
elif n_exceed < n:
    verdict = (f"(b) Ceiling exceeded in {n_exceed}/{n} dwarfs — the Cassi "
               f"saturation limit sqrt(phi^6) = phi^3 ~ {CEILING:.2f} is falsified for the "
               f"lowest-mass systems; MOND's unbounded growth is preferred there")
    if n_mond > n_cassi:
        verdict += f"\n  MOND fits {n_mond} galaxies vs Cassi's {n_cassi}."
        verdict += ("\n  This falsifies the pure G-rescaling sector only (boost = (G_eff/G)")
        verdict += ("\n  acting on baryonic mass). The coherence-condensate sector")
        verdict += ("\n  (speculations/dark-matter-as-qi-coherence.md) carries the boost in")
        verdict += ("\n  Yang-field mass instead: v^2 = G[M_bar + (1+xi q) M_Y]/r — no phi^3")
        verdict += ("\n  ceiling there, but M_Y/M_bar ~ 15 at q -> 1 is required, four-plus")
        verdict += ("\n  decades below the SPARC calibration range (uncalibrated, not falsified).")
    else:
        verdict += f"\n  MOND fits {n_mond} galaxies vs Cassi's {n_cassi}."
else:
    verdict = (f"(c) Dark matter / MOND — ALL galaxies show v_obs/v_Newt beyond the "
               f"Cassi ceiling {CEILING:.2f}")
    if n_mond > n_cassi:
        verdict += f"\n  MOND fits {n_mond} galaxies vs Cassi's {n_cassi}."
    else:
        verdict += f"\n  Neither modified gravity model fits well."

print(f"  {verdict}")

# Extra analysis: does v_obs/v_Newt grow with decreasing mass (MOND) or stay flat (Cassi)?
M_arr = np.array([r['M_bary'] for r in results])
ratio_arr = np.array([r['ratio_obs_Newt'] for r in results])
log_M = np.log10(M_arr)
log_r = np.log10(ratio_arr)

# Simple linear regression in log space
coeffs = np.polyfit(log_M, log_r, 1)
slope = coeffs[0]
print()
print(f"  Slope of log(v_obs/v_Newt) vs log(M): {slope:.3f}")
if slope < -0.1:
    print("  -> Ratio INCREASES with decreasing mass (consistent with MOND/dark matter)")
elif slope > 0.1:
    print("  -> Ratio DECREASES with decreasing mass (unexpected)")
else:
    print("  -> Ratio is roughly CONSTANT with mass (consistent with Cassi saturation)")

print()

# ── Plot ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# Left panel: v_obs/v_Newt vs M_baryon (log-log)
ax = axes[0]
masses = np.array([r['M_bary'] for r in results])
obs_ratios = np.array([r['ratio_obs_Newt'] for r in results])

# Color by type: ultra-faint vs classical
uf_names = ['Segue 1', 'Segue 2', 'Willman 1', 'Bootes I', 'Coma Berenices']
classical_names = ['Draco', 'Sculptor', 'Fornax']

for r in results:
    if r['name'] in uf_names:
        color, marker, s = '#e74c3c', 'v', 120   # red triangles for ultra-faint
    else:
        color, marker, s = '#3498db', 'o', 100    # blue circles for classical
    ax.scatter(r['M_bary'], r['ratio_obs_Newt'], c=color, marker=marker, s=s,
               zorder=5, edgecolors='white', linewidths=0.5)
    ax.annotate(r['name'], (r['M_bary'], r['ratio_obs_Newt']),
               textcoords="offset points", xytext=(8, 4), fontsize=8,
               color=color)

# Newtonian line (v_obs/v_Newt = 1)
M_range = np.logspace(2, 8, 100)
ax.plot(M_range, np.ones_like(M_range), 'k--', alpha=0.5, linewidth=1.5, label='Newtonian (1.0)')

# Cassi saturation ceiling
ax.plot(M_range, np.full_like(M_range, CEILING), color='#2ecc71', linewidth=2.5,
        linestyle='-', label=f'Cassi ceiling ($\\sqrt{{\\phi^6}}$ = $\\phi^3$ = {CEILING:.2f})')

# MOND prediction curve: v_MOND/v_Newt = (G M a0)^{1/4} / (GM/r)^{1/2}
# = (a0)^{1/4} * r^{1/2} / (G M)^{1/4}; fiducial r = 100 pc
r_fid = 100 * pc  # 100 pc fiducial half-light radius
mond_ratio = (a0_mond)**0.25 * r_fid**0.5 / (G * M_range * M_sun)**0.25
ax.plot(M_range * M_sun / M_sun, mond_ratio, color='#e67e22', linewidth=2.5,
        linestyle='-.', label='MOND ($v^4 = GMa_0$, r=100pc)')

# MOND ratio for EACH galaxy's actual r_half as small markers
for r in results:
    M_kg = r['M_bary'] * M_sun
    r_m = r['r_half_pc'] * pc
    v_MOND_i = (G * M_kg * a0_mond)**0.25
    v_Newt_i = (G * M_kg / r_m)**0.5
    mond_r_i = v_MOND_i / v_Newt_i
    ax.plot(r['M_bary'], mond_r_i, 'x', color='#e67e22', markersize=8, markeredgewidth=2)

ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlabel('Baryonic Mass $M_{bary}$ [$M_\\odot$]', fontsize=12)
ax.set_ylabel('$v_{obs} / v_{Newt}$', fontsize=12)
ax.set_title('Dwarf Galaxy Velocity Ratios vs Baryonic Mass', fontsize=13, fontweight='bold')
ax.legend(loc='upper right', fontsize=9)
ax.grid(True, which='both', alpha=0.3)
ax.set_ylim(0.3, 50)
ax.set_xlim(5e2, 5e7)

# Factor-2 acceptance band around the Cassi ceiling
ax.axhspan(0.5 * CEILING, 2.0 * CEILING, alpha=0.08, color='green', label='_nolegend_')
ax.text(1e3, 0.5 * CEILING * 1.15,
        f'Cassi band ($\\times 0.5$–$\\times 2$ of {CEILING:.2f}$\\times$ ceiling)',
        fontsize=8, color='green', alpha=0.7, va='bottom')

# Right panel: direct velocity comparison
ax2 = axes[1]
names = [r['name'] for r in results]
x_pos = np.arange(len(names))
width = 0.2

v_obs_arr = [r['v_obs'] for r in results]
v_Newt_arr = [r['v_Newt'] for r in results]
v_Cassi_arr = [r['v_Cassi'] for r in results]
v_MOND_arr = [r['v_MOND'] for r in results]

bars1 = ax2.bar(x_pos - 1.5*width, v_Newt_arr, width, label='Newtonian', color='#95a5a6', alpha=0.8)
bars2 = ax2.bar(x_pos - 0.5*width, v_Cassi_arr, width,
                label=f'Cassi ({CEILING:.2f}x)', color='#2ecc71', alpha=0.8)
bars3 = ax2.bar(x_pos + 0.5*width, v_MOND_arr, width, label='MOND', color='#e67e22', alpha=0.8)
bars4 = ax2.bar(x_pos + 1.5*width, v_obs_arr, width, label='Observed', color='#e74c3c', alpha=0.8)

ax2.set_xticks(x_pos)
ax2.set_xticklabels(names, rotation=45, ha='right', fontsize=9)
ax2.set_ylabel('Velocity [km/s]', fontsize=12)
ax2.set_title('Predicted vs Observed Velocities', fontsize=13, fontweight='bold')
ax2.legend(fontsize=9)
ax2.grid(True, axis='y', alpha=0.3)
ax2.set_yscale('log')

plt.tight_layout()

# Save
out_path = os.path.join(os.path.dirname(__file__), 'path10_dwarf_galaxies.png')
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"Plot saved to: {out_path}")
plt.close()

print()
print("=" * 112)
print("DONE")
print("=" * 112)
