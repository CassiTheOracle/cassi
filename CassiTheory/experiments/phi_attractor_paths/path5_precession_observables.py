#!/usr/bin/env python3
r"""Path 5: Cassi Softened-Gravity Precession vs Real Astronomical Observables.

Connects the analytical Cassi pericenter precession formula to real systems:

    Δφ_Cassi/orbit = -sqrt(2π) · (σ/a)³ · (1 + e²/4) / (1 - e²)³    (retrograde)

    Δφ_GR/orbit   = 6πGM / (a·c²·(1 - e²))                           (prograde)

For each system we compute:
  1. GR precession per orbit (Δφ_GR)
  2. σ_cancel: the softening length that makes |Δφ_Cassi| = Δφ_GR
  3. σ_detectable: the softening length where |Δφ_Cassi| = 10× obs. uncertainty
  4. Observational constraint on σ/a

Systems studied:
  - Mercury (solar system)
  - Binary pulsar PSR B1913+16 (Hulse-Taylor)
  - Double pulsar PSR J0737-3039
  - S2 star at Galactic Center (Sgr A*)

Produces:
  - Summary table on stdout
  - Log-log figure: experiments/path5_precession_observables.png

Usage:
    python experiments/path5_precession_observables.py
"""

import math
import sys
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ═══════════════════════════════════════════════════════════════════════
#  Physical constants
# ═══════════════════════════════════════════════════════════════════════

G = 6.6743e-11         # gravitational constant [m³ kg⁻¹ s⁻²]
C = 2.998e8            # speed of light [m s⁻¹]
MSUN = 1.989e30        # solar mass [kg]
AU = 1.496e11          # astronomical unit [m]
C1 = math.sqrt(2.0 * math.pi)  # ≈ 2.5066—Cassi precession prefactor


# ═══════════════════════════════════════════════════════════════════════
#  System definitions
# ═══════════════════════════════════════════════════════════════════════
#
# Each system:
#   name:        label
#   a:           semi-major axis [m]
#   e:           eccentricity
#   M:           central mass [kg]
#   dphi_obs:    observed precession [rad/orbit] (None if not directly observed)
#   dphi_unc:    observational uncertainty on precession [rad/orbit]
#   note:        brief description

SYSTEMS = [
    {
        'name': 'Mercury',
        'a': 0.387 * AU,            # 5.79e10 m
        'e': 0.206,
        'M': MSUN,                  # solar mass
        # Observed: 43.1 arcsec/century, ~415 orbits/century
        # Uncertainty ~0.1 arcsec/century (post-MESSENGER)
        'dphi_obs': 5.02e-7,
        'dphi_unc': 1.2e-9,         # ~0.1 arcsec/century per orbit
        'note': 'Solar system',
    },
    {
        'name': 'PSR B1913+16',
        'a': 1.95e9,                # semi-major axis [m]
        'e': 0.617,
        'M': 2.828 * MSUN,          # total mass
        # Observed: 4.226598°/year, T~7.75 hr → ~1131 orbits/year
        # Uncertainty ±0.000005°/year
        'dphi_obs': 6.53e-5,
        'dphi_unc': 7.7e-11,
        'note': 'Hulse-Taylor pulsar',
    },
    {
        'name': 'PSR J0737-3039',
        'a': 8.8e8,                 # semi-major axis [m]
        'e': 0.088,
        'M': 2.58 * MSUN,           # total mass
        # Observed: ~16.9°/year, T~2.45 hr → ~3578 orbits/year
        # Uncertainty ±0.0001°/year (conservative)
        'dphi_obs': 8.24e-5,
        'dphi_unc': 4.9e-10,
        'note': 'Double pulsar',
    },
    {
        'name': 'S2 (Galactic Center)',
        'a': 970.0 * AU,            # 1.451e14 m
        'e': 0.885,
        'M': 4.1e6 * MSUN,          # Sgr A*
        # GRAVITY collaboration 2020: ~12 arcmin/orbit
        # Uncertainty ~6 % initially, improved to ~10 % for conservative
        'dphi_obs': 0.00349,
        'dphi_unc': 0.00030,        # ~10 % uncertainty
        'note': 'Sgr A* star',
    },
]


def gr_precession(a, e, M):
    """GR pericenter precession per orbit [rad].

    Δφ_GR = 6πGM / (a·c²·(1−e²))
    """
    return 6.0 * math.pi * G * M / (a * C * C * (1.0 - e * e))


def cassi_precession(sigma, a, e):
    """Cassi softened-gravity pericenter precession per orbit [rad].

    Δφ_Cassi = −√(2π) · (σ/a)³ · (1+e²/4) / (1−e²)³

    Negative = retrograde.
    """
    ratio = sigma / a
    return -C1 * ratio ** 3 * (1.0 + e * e / 4.0) / (1.0 - e * e) ** 3


def sigma_cancel(a, e, M):
    """Softening length σ [m] that makes |Δφ_Cassi| = Δφ_GR.

    Solve: √(2π) · (σ/a)³ · (1+e²/4)/(1−e²)³ = 6πGM/(a·c²·(1−e²))

    →  σ/a = [ 6πGM · (1−e²)² / (a·c²·√(2π)·(1+e²/4)) ]^(1/3)
    """
    numerator = 6.0 * math.pi * G * M * (1.0 - e * e) ** 2
    denominator = a * C * C * C1 * (1.0 + e * e / 4.0)
    ratio = (numerator / denominator) ** (1.0 / 3.0)
    return a * ratio


def sigma_detectable(a, e, dphi_unc):
    """Softening length σ [m] where |Δφ_Cassi| = 10 × obs. uncertainty.

    Solve: √(2π) · (σ/a)³ · (1+e²/4)/(1−e²)³ = 10·δ_prec
    """
    ratio = ((10.0 * dphi_unc) * (1.0 - e * e) ** 3 / (C1 * (1.0 + e * e / 4.0))) ** (1.0 / 3.0)
    return a * ratio


def sigma_constraint(a, e, dphi_unc):
    """Upper limit on σ [m] from observational uncertainty.

    |Δφ_Cassi| < δ_prec  →  σ/a < [ δ_prec · (1−e²)³ / (√(2π)·(1+e²/4)) ]^(1/3)
    """
    ratio = (dphi_unc * (1.0 - e * e) ** 3 / (C1 * (1.0 + e * e / 4.0))) ** (1.0 / 3.0)
    return a * ratio


# ═══════════════════════════════════════════════════════════════════════
#  Compute results for each system
# ═══════════════════════════════════════════════════════════════════════

def compute_system_results(sys):
    """Compute all derived quantities for one system."""
    a = sys['a']
    e = sys['e']
    M = sys['M']
    dphi_unc = sys['dphi_unc']

    dphi_gr = gr_precession(a, e, M)
    s_cancel = sigma_cancel(a, e, M)
    s_detect = sigma_detectable(a, e, dphi_unc)
    s_limit = sigma_constraint(a, e, dphi_unc)

    return {
        'name': sys['name'],
        'a': a,
        'e': e,
        'M': M,
        'dphi_gr': dphi_gr,
        'dphi_unc': dphi_unc,
        'dphi_obs': sys['dphi_obs'],
        'sigma_cancel': s_cancel,
        'sigma_cancel_over_a': s_cancel / a,
        'sigma_detectable': s_detect,
        'sigma_detectable_over_a': s_detect / a,
        'sigma_limit': s_limit,
        'sigma_limit_over_a': s_limit / a,
        'note': sys['note'],
    }


def format_sci(value, precision=2):
    """Format a float in scientific notation, e.g. 5.02e-7."""
    if value == 0.0:
        return "0"
    exp = int(math.floor(math.log10(abs(value))))
    mant = value / (10.0 ** exp)
    return f"{mant:.{precision}f}e{exp}"


# ═══════════════════════════════════════════════════════════════════════
#  Table
# ═══════════════════════════════════════════════════════════════════════

def print_table(results):
    """Print formatted results table to stdout."""
    # Column widths
    w_name = 22
    w_prec = 16
    w_sig = 16
    w_ratio = 14

    sep = "─" * (w_name + w_prec + w_sig + w_sig + w_ratio + 12)
    sep += "─" * 22

    print("\n" + "=" * 110)
    print("  Cassi Softened-Gravity Precession vs Astronomical Observables")
    print("=" * 110)

    # ── Header ──
    hdr = (f"  {'System':<{w_name}s}"
           f"  {'GR precession':>{w_prec}s}"
           f"  {'σ_cancel (m)':>{w_sig}s}"
           f"  {'σ_detectable (m)':>{w_sig}s}"
           f"  {'Obs?':>10s}"
           f"  {'σ/a upper limit':>{w_ratio}s}")
    print(hdr)
    print("  " + sep)

    for r in results:
        gr_str = format_sci(r['dphi_gr'])
        sc_str = format_sci(r['sigma_cancel'])
        sd_str = format_sci(r['sigma_detectable'])
        constraint_str = format_sci(r['sigma_limit_over_a'])
        obs_str = "Yes" if r['dphi_obs'] is not None else "No"

        line = (f"  {r['name']:<{w_name}s}"
                f"  {gr_str:>{w_prec}s} rad/orb"
                f"  {sc_str:>{w_sig}s}"
                f"  {sd_str:>{w_sig}s}"
                f"  {obs_str:>10s}"
                f"  σ/a < {constraint_str:>{w_ratio-6}s}")
        print(line)

    print("  " + sep)

    # ── Constraint summary ──
    print("\n  Observational constraints on σ:")
    tightest = min(results, key=lambda r: r['sigma_limit'])
    print(f"    Tightest constraint:  σ < {format_sci(tightest['sigma_limit'])} m"
          f"  ({tightest['name']})")
    print(f"    Corresponds to σ/a < {format_sci(tightest['sigma_limit_over_a'])}")

    # Single σ check
    print(f"\n  Key Question: Is there a single σ that satisfies ALL systems?")
    max_allowed = min(r['sigma_limit'] for r in results)
    print(f"    Maximum σ allowed by all constraints: σ < {format_sci(max_allowed)} m")

    # Single σ sanity check
    print(f"    If σ = {format_sci(max_allowed * 0.5)} m (half the tightest bound):")
    for r in results:
        a = r['a']
        e = r['e']
        test_sigma = max_allowed * 0.5
        dphi_c = abs(cassi_precession(test_sigma, a, e))
        safe = dphi_c < r['dphi_unc']
        margin = r['dphi_unc'] / dphi_c if dphi_c > 0 else float('inf')
        status = "✓ safe" if safe else "✗ EXCLUDED"
        print(f"      {r['name']:<22s} |Δφ_Cassi| = {dphi_c:.2e} "
              f"rad/orb  uncertainty = {r['dphi_unc']:.2e}  "
              f"margin = {margin:.1f}x  {status}")

    print("\n  " + "═" * 110)
    print()

    return tightest


# ═══════════════════════════════════════════════════════════════════════
#  Figure
# ═══════════════════════════════════════════════════════════════════════

def make_figure(results, savepath='experiments/path5_precession_observables.png'):
    """Generate log-log constraint figure.

    Shows:
      - Cassi |Δφ| vs σ/a for several eccentricities (solid lines)
      - Horizontal lines for each system's GR precession (dashed)
      - Markers at σ_cancel for each system (where Cassi = GR)
      - Shaded exclusion region from observations
    """
    fig, ax = plt.subplots(1, 1, figsize=(10, 7))

    # ═══════════════════════════════════════════════════════════════════
    #  1. Cassi |Δφ| as function of σ/a for different eccentricities
    # ═══════════════════════════════════════════════════════════════════

    sigma_over_a = np.logspace(-8, 0, 200)
    e_curves = [0.1, 0.3, 0.5, 0.7, 0.9]
    colors_cassi = plt.cm.plasma_r(np.linspace(0.15, 0.75, len(e_curves)))
    cassi_lines = []

    for i, e_val in enumerate(e_curves):
        # |Δφ_Cassi| = C1 · (σ/a)³ · (1+e²/4) / (1−e²)³
        dphi = C1 * sigma_over_a ** 3 * (1.0 + e_val * e_val / 4.0) / (1.0 - e_val * e_val) ** 3
        line, = ax.loglog(
            sigma_over_a, dphi, '-', lw=1.8,
            color=colors_cassi[i],
            label=rf'$e = {e_val:.1f}$'
        )
        cassi_lines.append(line)

    # ═══════════════════════════════════════════════════════════════════
    #  2. GR precession horizontal lines for each system
    # ═══════════════════════════════════════════════════════════════════

    gr_colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12']
    gr_markers = ['o', 's', 'D', '^']
    gr_handles = []
    gr_labels = []

    for i, r in enumerate(results):
        dphi = r['dphi_gr']
        soa_cancel = r['sigma_cancel_over_a']

        # Horizontal line
        hline = ax.axhline(dphi, color=gr_colors[i], ls='--', lw=1.5, alpha=0.85)

        # Marker at crossing point—only if within plot range
        if soa_cancel > sigma_over_a[0] * 0.5 and soa_cancel < sigma_over_a[-1] * 2:
            ax.scatter(
                [soa_cancel], [dphi],
                marker=gr_markers[i], s=90, zorder=8,
                color=gr_colors[i], edgecolors='white', linewidths=0.8,
            )

        # Label near the line
        label = rf'{r["name"]}'  # GR = {dphi:.1e}
        gr_handles.append(hline)
        gr_labels.append(label)

        # Add σ_cancel annotation
        if soa_cancel > sigma_over_a[0] * 0.5 and soa_cancel < sigma_over_a[-1] * 2:
            ax.annotate(
                rf'$\sigma/a = {soa_cancel:.2e}$',
                xy=(soa_cancel, dphi),
                xytext=(soa_cancel * 2.5, dphi * 2.5),
                fontsize=6.5,
                color=gr_colors[i],
                arrowprops=dict(arrowstyle='->', color=gr_colors[i], lw=0.8),
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=gr_colors[i],
                         alpha=0.85, lw=0.5),
            )

    # ═══════════════════════════════════════════════════════════════════
    #  3. Observational exclusion region
    # ═══════════════════════════════════════════════════════════════════

    # Compute the most stringent σ/a constraint across all systems
    # For each σ, evaluate whether any system would detect it
    all_constraints = []
    for r in results:
        a = r['a']
        e = r['e']
        dphi_unc = r['dphi_unc']
        limit_ratio = (dphi_unc * (1.0 - e * e) ** 3 / (C1 * (1.0 + e * e / 4.0))) ** (1.0 / 3.0)
        all_constraints.append({
            'name': r['name'],
            'sigma_over_a_limit': limit_ratio,
        })

    tightest_constraint = min(all_constraints, key=lambda x: x['sigma_over_a_limit'])
    soa_limit = tightest_constraint['sigma_over_a_limit']

    # Shade EXCLUDED region (σ/a > limit → Cassi precession would exceed obs. uncertainty)
    # The excluded region is to the right of the tightest constraint
    ax.axvspan(soa_limit, sigma_over_a[-1] * 10,
               alpha=0.08, color='red', label='Excluded by observations')

    # Also shade a "tension" zone (1σ to 10σ)
    # Find 10× uncertainty for tightest system
    for r in results:
        if r['name'] == tightest_constraint['name']:
            # 10× uncertainty detectable level
            detectable_soa = ((10.0 * r['dphi_unc']) * (1.0 - r['e'] * r['e']) ** 3
                              / (C1 * (1.0 + r['e'] * r['e'] / 4.0))) ** (1.0 / 3.0)
            ax.axvspan(soa_limit, detectable_soa,
                       alpha=0.06, color='orange',
                       label='Detectable at 10σ')

    # Vertical line at tightest constraint
    ax.axvline(soa_limit, color='red', ls=':', lw=1.2, alpha=0.7)
    ax.annotate(
        rf'Tightest constraint: σ/a < {soa_limit:.1e}',
        xy=(soa_limit, 1e-11),
        xytext=(soa_limit * 0.4, 3e-12),
        fontsize=7.5,
        color='red',
        arrowprops=dict(arrowstyle='->', color='red', lw=0.8),
        bbox=dict(boxstyle='round,pad=0.2', fc='#FFEEEE', ec='red', alpha=0.8, lw=0.5),
    )

    # ═══════════════════════════════════════════════════════════════════
    #  Legend assembly
    # ═══════════════════════════════════════════════════════════════════

    # Cassi curves legend group
    leg1 = ax.legend(
        cassi_lines,
        [rf'$e = {e:.1f}$' for e in e_curves],
        title='Cassi $|\\Delta\\phi|$ per orbit',
        loc='upper left', fontsize=7.5, title_fontsize=8,
        framealpha=0.9,
    )
    ax.add_artist(leg1)

    # GR + constraints legend group
    extra_handles = list(gr_handles) + [
        plt.Line2D([0], [0], color='red', lw=0, marker='s',
                   markersize=0),  # dummy for spacing
        plt.Rectangle((0, 0), 1, 1, fc='red', alpha=0.08, lw=0),
        plt.Rectangle((0, 0), 1, 1, fc='orange', alpha=0.06, lw=0),
    ]
    extra_labels = list(gr_labels) + [
        '',
        'Excluded (σ bound)',
        'Detectable at 10σ',
    ]

    leg2 = ax.legend(
        extra_handles, extra_labels,
        title='GR precession / constraints',
        loc='lower right', fontsize=7.5, title_fontsize=8,
        framealpha=0.9,
    )
    ax.add_artist(leg2)

    # ═══════════════════════════════════════════════════════════════════
    #  Labels and styling
    # ═══════════════════════════════════════════════════════════════════

    ax.set_xlabel(r'Softening ratio $\sigma / a$ (dimensionless)',
                  fontsize=12)
    ax.set_ylabel(r'$|\Delta\varphi|$ per orbit [rad]',
                  fontsize=12)
    ax.set_title(
        r'Cassi Softened-Gravity Precession vs Astronomical Observables',
        fontsize=12, fontweight='bold',
    )
    ax.set_xlim(sigma_over_a[0], sigma_over_a[-1])
    ax.set_ylim(1e-12, 2.0)
    ax.grid(True, alpha=0.25, which='both', ls=':')

    # ═══════════════════════════════════════════════════════════════════
    #  Formula annotation
    # ═══════════════════════════════════════════════════════════════════

    formula_box = (
        r'$\Delta\varphi_{\mathrm{Cassi}} = '
        r'-\sqrt{2\pi}\left(\frac{\sigma}{a}\right)^{\!3}'
        r'\frac{1+e^2/4}{(1-e^2)^3}$'
        + '\n'
        + r'$\Delta\varphi_{\mathrm{GR}} = '
        r'\frac{6\pi GM}{a c^2 (1-e^2)}$'
    )
    ax.text(
        0.03, 0.03, formula_box,
        transform=ax.transAxes,
        fontsize=8,
        ha='left', va='bottom',
        bbox=dict(boxstyle='round,pad=0.4',
                  facecolor='wheat', alpha=0.85, ec='#B8860B', lw=0.8),
    )

    fig.tight_layout()
    fig.savefig(savepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"  Saved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
#  Diagnostic: how do σ_cancel values compare?
# ═══════════════════════════════════════════════════════════════════════

def print_analysis(results):
    """Print detailed analysis of σ consistency across systems."""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + "  ANALYSIS: Is there a single σ that satisfies all constraints?".center(78) + "║")
    print("╠" + "═" * 78 + "╣")

    print("║" + " " * 78 + "║")
    print("║" + "  The σ_cancel values span many orders of magnitude:".ljust(78) + "║")
    for r in results:
        print("║" + f"    {r['name']:<22s}  σ_cancel = {r['sigma_cancel']:.2e} m  "
              f"(σ/a = {r['sigma_cancel_over_a']:.2e})".ljust(78) + "║")

    print("║" + " " * 78 + "║")
    print("║" + "  This is because σ_cancel ∝ a^{{2/3}}: larger orbits need larger σ".ljust(78) + "║")
    print("║" + "  to generate the same precession amplitude.".ljust(78) + "║")
    print("║" + "  → A single σ CANNOT cancel GR in all systems simultaneously.".ljust(78) + "║")
    print("║" + " " * 78 + "║")

    # σ consistency check—what σ would explain GR in each system?
    print("║" + "  If Cassi were the ONLY precession mechanism (replacing GR):".ljust(78) + "║")

    # For each system, what σ would be needed to match GR observation?
    print("║" + "  Required σ to match observed GR precession:".ljust(78) + "║")
    for r in results:
        # Solve: Δφ_obs = |Δφ_Cassi|
        # This would mean Cassi, not GR, is causing the observed precession.
        # In that case the precession would be retrograde, which contradicts observations.
        # But for the exercise:
        dphi_obs = r['dphi_obs']
        e = r['e']
        if isinstance(dphi_obs, (int, float)) and dphi_obs > 0:
            A = C1 * (1.0 + e * e / 4.0) / (1.0 - e * e) ** 3
            sigma_match = r['a'] * (dphi_obs / A) ** (1.0 / 3.0)
            print("║" + f"    {r['name']:<22s}  σ = {sigma_match:.2e} m  "
                  f"(σ/a = {sigma_match/r['a']:.2e})".ljust(78) + "║")
        else:
            print("║" + f"    {r['name']:<22s}  [no observed precession]".ljust(78) + "║")

    print("║" + " " * 78 + "║")
    print("║" + "  The required σ varies by 4+ orders of magnitude across systems.".ljust(78) + "║")
    print("║" + "  Cassi softened gravity CANNOT replace GR as the dominant source of".ljust(78) + "║")
    print("║" + "  perihelion precession across all scales.".ljust(78) + "║")

    # Observational constraints
    print("║" + " " * 78 + "║")
    print("║" + "  Observational constraints on σ (from non-detection of Cassi):".ljust(78) + "║")
    for r in results:
        print("║" + f"    {r['name']:<22s}  σ < {r['sigma_limit']:.2e} m  "
              f"(σ/a < {r['sigma_limit_over_a']:.2e})".ljust(78) + "║")

    tightest = min(results, key=lambda r: r['sigma_limit'])
    print("║" + " " * 78 + "║")
    print("║" + f"  Tightest constraint: σ < {tightest['sigma_limit']:.2e} m  "
          f"({tightest['name']})".ljust(78) + "║")

    # Is a single σ possible?
    print("║" + " " * 78 + "║")
    if tightest['sigma_limit'] > 0:
        print("║" + "  Answer: YES—a single σ < {:.2e} m satisfies ALL current".format(
            tightest['sigma_limit']).ljust(78) + "║")
        print("║" + "  observational constraints. The Cassi softening length must be".ljust(78) + "║")
        print("║" + "  smaller than the tightest bound from binary pulsar timing.".ljust(78) + "║")
        print("║" + " " * 78 + "║")
        print("║" + "  However, this σ is a UPPER LIMIT, not a detection. A single σ < ~few × 10⁵ m".ljust(78) + "║")
        print("║" + "  is consistent with all observations—but Cassi precession would be".ljust(78) + "║")
        print("║" + "  undetectably small in all currently tested systems.".ljust(78) + "║")
        print("║" + " " * 78 + "║")
        print("║" + "  Implications:".ljust(78) + "║")
        print("║" + "  • A σ ≈ 300 km is consistent with all current data.".ljust(78) + "║")
        print("║" + "  • To detect Cassi, we need systems with smaller a or higher precision.".ljust(78) + "║")
        print("║" + "  • Tight binary pulsars in dense star clusters could be the best probes.".ljust(78) + "║")

    print("╚" + "═" * 78 + "╝")


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 64)
    print("  Path 5: Cassi Precession vs Astronomical Observables")
    print("=" * 64)

    # ── 1. Compute ──
    print("\n[1/4] Computing precession for real systems...")
    results = [compute_system_results(sys) for sys in SYSTEMS]

    for r in results:
        print(f"    {r['name']:<22s}  "
              f"a={r['a']:.2e} m  e={r['e']:.3f}  "
              f"Δφ_GR={r['dphi_gr']:.2e} rad/orbit  "
              f"σ_cancel={r['sigma_cancel']:.2e} m  "
              f"σ/α_limit={r['sigma_limit_over_a']:.2e}")

    # ── 2. Table ──
    print("\n[2/4] Summary table:")
    tightest = print_table(results)

    # ═══════════════════════════════════════════════════════════════════
    #  Detailed analysis
    # ═══════════════════════════════════════════════════════════════════

    print("[3/4] Detailed analysis:")
    print_analysis(results)

    # ═══════════════════════════════════════════════════════════════════
    #  Figure
    # ═══════════════════════════════════════════════════════════════════

    print("\n[4/4] Generating constraint figure...")
    make_figure(
        results,
        savepath='experiments/path5_precession_observables.png',
    )

    print("\nDone.")


if __name__ == '__main__':
    main()
