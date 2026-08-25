"""
Path 10: conditional Cassi saturation ceiling—dwarf-galaxy screen
=================================================================

This script evaluates one sharply limited consequence of the optional
Qi-gravity chord ansatz:

    G_eff/G_N = 1 + (phi^6 - 1) q,       0 <= q <= 1.

At fixed baryonic composition this gives
v_c/v_Newt <= sqrt(phi^6) = phi^3. The phi^6 identity is Derived; using
it as a gravitational coupling and choosing this interpolation are
Hypothesized constitutive assumptions.

The velocity dispersions and projected half-light radii below are transcribed
from Tables 3 and 4 of McConnachie (2012), arXiv:1204.1562v2. Table 4's
stellar-mass column is a catalog proxy obtained with M_star/L_V = 1, not an
independently inferred stellar-mass posterior. We deproject the tabulated
projected half-light radius as r_1/2 = 4 R_e / 3, place half of that nominal
stellar-mass proxy inside r_1/2, and use the Wolf-et-al. spherical estimator
v_c(r_1/2) = sqrt(3) sigma_los.

This is a nominal catalog screen, not an observational verdict. It omits
fixed-M/L and stellar-population systematics, binary-star contamination,
membership and tidal systematics, anisotropy, nonsphericity, and uncertainty
in dynamical equilibrium. A publishable exclusion needs object-level
likelihoods and quality cuts fixed before inspecting the ceiling statistic.
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
# (name, sigma [km/s], -/+ sigma, projected R_e [pc], -/+ R_e,
#  nominal stellar-mass proxy [M_sun], assuming M_star/L_V = 1)
# Source: A. W. McConnachie, AJ 144, 4 (2012), arXiv:1204.1562v2,
# Tables 3 and 4. Asymmetric errors are retained where tabulated.

dwarfs = [
    ("Segue 1",         3.9, 0.8, 0.8,  29,  5,  8,      340),
    ("Segue 2",         3.4, 1.2, 2.5,  35,  3,  3,      860),
    ("Willman 1",       4.3, 1.3, 2.3,  25,  6,  6,     1000),
    ("Bootes I",        2.4, 0.5, 0.9, 242, 21, 21,    29000),
    ("Coma Berenices",  4.6, 0.8, 0.8,  77, 10, 10,     3700),
    ("Draco",           9.1, 1.2, 1.2, 221, 19, 19,   290000),
    ("Sculptor",        9.2, 1.4, 1.4, 283, 45, 45,  2300000),
    ("Fornax",         11.7, 0.9, 0.9, 710, 77, 77, 20000000),
]

# ── Computations ───────────────────────────────────────────────────────────
results = []

print("=" * 126)
print(f"PATH 10: CONDITIONAL CASSI {CEILING:.2f}x VELOCITY-BOOST CEILING—NOMINAL DWARF SCREEN")
print("=" * 126)
print()
print(f"{'Galaxy':<18} {'M* proxy':>10} {'sigma':>7} {'R_e':>6} {'v_obs':>8} "
      f"{'v_Newt':>8} {'v_chord':>8} {'v_MOND':>8} {'boost':>8} {'kin. interval':>17} {'screen':>9}")
print(f"{'':18} {'[M_sun]':>10} {'[km/s]':>7} {'[pc]':>6} {'[km/s]':>8} "
      f"{'[km/s]':>8} {'[km/s]':>8} {'[km/s]':>8} {'':>8} {'':>17} {'':>9}")
print("-" * 126)

for (name, sigma_v, sigma_minus, sigma_plus, r_e_pc, r_minus, r_plus,
     m_star_msun) in dwarfs:
    # Wolf et al. convention: deproject R_e and enclose half the stars.
    r_half_pc = (4.0 / 3.0) * r_e_pc
    m_enclosed_msun = 0.5 * m_star_msun
    r_m = r_half_pc * pc
    m_kg = m_enclosed_msun * M_sun
    sigma_ms = sigma_v * 1e3

    v_obs = np.sqrt(3.0) * sigma_ms
    v_newt = np.sqrt(G * m_kg / r_m)
    v_chord = CEILING * v_newt

    # Deep-MOND spherical screen at the same radius and enclosed mass.
    v_mond = (G * m_kg * a0_mond) ** 0.25
    ratio_obs_newt = v_obs / v_newt
    ratio_mond_newt = v_mond / v_newt

    # Propagate only the quoted kinematic and radius ranges. Stellar-mass
    # uncertainty and the larger systematics listed in the docstring remain open.
    sigma_lo_ms = max(0.0, sigma_v - sigma_minus) * 1e3
    sigma_hi_ms = (sigma_v + sigma_plus) * 1e3
    r_lo_m = (4.0 / 3.0) * max(1e-12, r_e_pc - r_minus) * pc
    r_hi_m = (4.0 / 3.0) * (r_e_pc + r_plus) * pc
    ratio_lo = np.sqrt(3.0) * sigma_lo_ms / np.sqrt(G * m_kg / r_lo_m)
    ratio_hi = np.sqrt(3.0) * sigma_hi_ms / np.sqrt(G * m_kg / r_hi_m)

    nominal_exceeded = ratio_obs_newt > CEILING
    quoted_range_exceeded = ratio_lo > CEILING
    screen_tag = ("quoted*" if quoted_range_exceeded else
                  "nominal" if nominal_exceeded else "inside")

    results.append({
        'name': name,
        'M_star': m_star_msun,
        'M_enclosed': m_enclosed_msun,
        'sigma_v': sigma_v,
        'r_e_pc': r_e_pc,
        'r_half_pc': r_half_pc,
        'v_obs': v_obs / 1e3,
        'v_Newt': v_newt / 1e3,
        'v_Cassi': v_chord / 1e3,
        'v_MOND': v_mond / 1e3,
        'ratio_obs_Newt': ratio_obs_newt,
        'ratio_MOND_Newt': ratio_mond_newt,
        'ratio_lo': ratio_lo,
        'ratio_hi': ratio_hi,
        'nominal_exceeded': nominal_exceeded,
        'quoted_range_exceeded': quoted_range_exceeded,
    })

    interval = f"[{ratio_lo:.1f}, {ratio_hi:.1f}]"
    print(f"{name:<18} {m_star_msun:>10.0f} {sigma_v:>7.1f} {r_e_pc:>6.0f} "
          f"{v_obs/1e3:>8.2f} {v_newt/1e3:>8.3f} {v_chord/1e3:>8.3f} "
          f"{v_mond/1e3:>8.3f} {ratio_obs_newt:>8.1f} {interval:>17} {screen_tag:>9}")

print("-" * 126)

n = len(results)
n_nominal = sum(r['nominal_exceeded'] for r in results)
n_quoted = sum(r['quoted_range_exceeded'] for r in results)
ratios = np.array([r['ratio_obs_Newt'] for r in results])

print()
print("NOMINAL SCREEN SUMMARY:")
print(f"  Nominal boosts above phi^3 = {CEILING:.3f}: {n_nominal}/{n}")
print(f"  Lower quoted sigma/R_e bound above phi^3: {n_quoted}/{n}")
print(f"  Median nominal v_obs/v_Newt: {np.median(ratios):.1f}")
print(f"  Nominal range: [{ratios.min():.1f}, {ratios.max():.1f}]")
print("  * 'quoted' propagates only the catalog sigma and R_e interval.")

# ── Interpretation ─────────────────────────────────────────────────────────
print()
print("=" * 126)
print("INTERPRETATION: SCREEN ONLY—NO OBSERVATIONAL VERDICT")
print("=" * 126)
print(
    "The nominal central values identify targets for a preregistered, "
    "object-level analysis. They do not by themselves falsify or support the "
    "optional chord ansatz. Stellar-mass posteriors, membership and binary "
    "models, tidal/equilibrium cuts, and a declared population likelihood are "
    "required before assigning a Cassi or MOND verdict."
)
print(
    "The ceiling applies only to a fixed-composition rescaling of G. It is not "
    "a prediction of the canonical two-fluid PDE, and it does not constrain a "
    "separate gravitating-field mass component."
)
print()

# ── Plot ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# Left panel: nominal boost vs the M_star/L_V = 1 catalog proxy.
ax = axes[0]
obs_ratios = np.array([r['ratio_obs_Newt'] for r in results])

# Color by type: ultra-faint vs classical
uf_names = ['Segue 1', 'Segue 2', 'Willman 1', 'Bootes I', 'Coma Berenices']

for r in results:
    if r['name'] in uf_names:
        color, marker, s = '#e74c3c', 'v', 120   # red triangles for ultra-faint
    else:
        color, marker, s = '#3498db', 'o', 100    # blue circles for classical
    ax.scatter(r['M_star'], r['ratio_obs_Newt'], c=color, marker=marker, s=s,
               zorder=5, edgecolors='white', linewidths=0.5)
    ax.annotate(r['name'], (r['M_star'], r['ratio_obs_Newt']),
               textcoords="offset points", xytext=(8, 4), fontsize=8,
               color=color)

# Newtonian line (v_obs/v_Newt = 1)
M_range = np.logspace(2, 8, 100)
ax.plot(M_range, np.ones_like(M_range), 'k--', alpha=0.5, linewidth=1.5, label='Newtonian (1.0)')

# Cassi saturation ceiling
ax.plot(M_range, np.full_like(M_range, CEILING), color='#2ecc71', linewidth=2.5,
        linestyle='-', label=f'Conditional chord ceiling ($\\phi^3$ = {CEILING:.2f})')

# MOND screen for a fiducial projected R_e = 100 pc, with
# r_1/2 = 4 R_e / 3 and M(<r_1/2) = M_star / 2.
r_fid = (4.0 / 3.0) * 100 * pc
m_enclosed_range = 0.5 * M_range * M_sun
v_mond_fid = (G * m_enclosed_range * a0_mond) ** 0.25
v_newt_fid = np.sqrt(G * m_enclosed_range / r_fid)
mond_ratio = v_mond_fid / v_newt_fid
ax.plot(M_range, mond_ratio, color='#e67e22', linewidth=2.5,
        linestyle='-.', label='Deep-MOND screen ($R_e=100$ pc)')

# MOND ratio for each galaxy's tabulated radius.
for r in results:
    ax.plot(r['M_star'], r['ratio_MOND_Newt'], 'x', color='#e67e22',
            markersize=8, markeredgewidth=2)

ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlabel('Catalog $M_\\star$ proxy ($M_\\star/L_V=1$) [$M_\\odot$]', fontsize=12)
ax.set_ylabel('$v_c(r_{1/2}) / v_{Newt}(r_{1/2})$', fontsize=12)
ax.set_title('Nominal Dwarf-Galaxy Ceiling Screen', fontsize=13, fontweight='bold')
ax.legend(loc='upper right', fontsize=9)
ax.grid(True, which='both', alpha=0.3)
ax.set_ylim(0.3, 80)
ax.set_xlim(2e2, 5e7)

ax.text(3e2, CEILING * 1.12,
        'conditional fixed-composition ceiling',
        fontsize=8, color='#2ecc71', alpha=0.8, va='bottom')

# Right panel: direct velocity comparison
ax2 = axes[1]
names = [r['name'] for r in results]
x_pos = np.arange(len(names))
width = 0.2

v_obs_arr = [r['v_obs'] for r in results]
v_Newt_arr = [r['v_Newt'] for r in results]
v_Cassi_arr = [r['v_Cassi'] for r in results]
v_MOND_arr = [r['v_MOND'] for r in results]

ax2.bar(x_pos - 1.5*width, v_Newt_arr, width,
        label='Newtonian stellar mass', color='#95a5a6', alpha=0.8)
ax2.bar(x_pos - 0.5*width, v_Cassi_arr, width,
        label=f'Chord ceiling ({CEILING:.2f}x)', color='#2ecc71', alpha=0.8)
ax2.bar(x_pos + 0.5*width, v_MOND_arr, width,
        label='Deep-MOND screen', color='#e67e22', alpha=0.8)
ax2.bar(x_pos + 1.5*width, v_obs_arr, width,
        label='$\\sqrt{3}\\,\\sigma_{los}$ estimator', color='#e74c3c', alpha=0.8)

ax2.set_xticks(x_pos)
ax2.set_xticklabels(names, rotation=45, ha='right', fontsize=9)
ax2.set_ylabel('Velocity at $r_{1/2}$ [km/s]', fontsize=12)
ax2.set_title('Nominal Screen Quantities', fontsize=13, fontweight='bold')
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
print("=" * 126)
print("DONE")
print("=" * 126)
