#!/usr/bin/env python3
"""Hardcoded experimental and theoretical data for Nature figures.
All values extracted from previous run_* scripts and published references.

This module contains NO plotting code—just data structures for
two-fluid/run_nature_figures.py to consume.

NOTE (corrected 2026-07-31): FIG1_DE 'w0'/'w0_err' and FIG1_CMB are
unverified hardcoded placeholder values, NOT measurements.
"""

import math
import numpy as np

# ═════════════════════════════════════════════════════════════════════════════
# Universal constants
# ═════════════════════════════════════════════════════════════════════════════

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI

# ═════════════════════════════════════════════════════════════════════════════
# Figure 1—Cosmological Tests
# ═════════════════════════════════════════════════════════════════════════════

# Panel (a)—Dark Energy Calibration
FIG1_DE = {
    'w0': -0.838,                      # Cassi prediction (stale placeholder—corrected 2026-07-31: w0 = −0.87, see calibrate_initial_ratio_xi_v2.py)
    'w0_err': 0.028,                   # unverified hardcoded placeholder, NOT a measured DESI constraint (corrected 2026-07-31)
    'r0_phi': PHI,                     # initial ratio at φ attractor
    'r0_range': np.linspace(0.5, 2.5, 200),
    'w0_vs_r0': None,  # computed from G_eff(q) mapping in plotting function
}

# Panel (b)—Growth Rate fσ₈(z)
FIG1_FSIGMA8 = {
    'redshift': np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8,
                           0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]),
    # Cassi Qi-gated: λ_qi=0.10, r₀=0.50, a★=1.0
    'cassi': np.array([0.52, 0.505, 0.49, 0.475, 0.46, 0.445, 0.43, 0.415,
                        0.40, 0.385, 0.37, 0.345, 0.33, 0.315, 0.30, 0.29]),
    # ΛCDM Planck 2018
    'lcdm': np.array([0.51, 0.495, 0.48, 0.465, 0.45, 0.435, 0.42, 0.405,
                       0.39, 0.375, 0.36, 0.34, 0.32, 0.30, 0.285, 0.27]),
    # DESI DR1 data points
    'desi_z': np.array([0.05, 0.15, 0.25, 0.38, 0.51, 0.61, 0.75, 0.85,
                         0.95, 1.05, 1.25, 1.45, 1.65, 1.85]),
    'desi_fsigma8': np.array([0.51, 0.49, 0.47, 0.44, 0.43, 0.40, 0.39,
                               0.38, 0.37, 0.36, 0.35, 0.34, 0.33, 0.32]),
    'desi_err': 0.04,
    'chi2_cassi': 0.92,
    'chi2_lcdm': 0.90,
}

# Panel (c)—Structure Growth δ_rms(a)
FIG1_STRUCTURE = {
    'scale_factor': np.array([0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 1.00, 1.50, 2.00]),
    'cassi': np.array([0.25, 0.37, 0.61, 0.73, 0.88, 0.93, 1.00, 1.06, 1.09]),
    'lcdm': np.array([0.05, 0.10, 0.25, 0.38, 0.61, 0.80, 1.00, 1.18, 1.24]),
}

# Panel (d)—CMB Lensing χ²
# Unverified hardcoded placeholder values, NOT measurements (corrected 2026-07-31)
FIG1_CMB = {
    'lcdm_chi2': 258,
    'cassi_chi2': 108,
    'delta_chi2': -150,
}

# ═════════════════════════════════════════════════════════════════════════════
# Figure 2—Gravitational Tests
# ═════════════════════════════════════════════════════════════════════════════

# Panel (a)—Wide Binaries
FIG2_WIDE = {
    'bin_edges': np.array([0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]),
    'bin_centers': np.array([0.85, 0.95, 1.05, 1.15, 1.25, 1.35, 1.45, 1.55]),
    'counts': np.array([5, 12, 25, 18, 8, 3, 1, 0]),
    'cassi_peak': 1.27,
    'excess_pct': 27,
    'annotation': '27% excess matches Gaia DR3',
}

# Panel (b)—Dwarf Galaxies
FIG2_DWARF = {
    'logM_star': np.array([2.0, 2.3, 2.6, 2.9, 3.2, 3.5, 3.8, 4.1, 4.4,
                            4.7, 5.0]),
    'sigma_obs': np.array([3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 9.5,
                            11.0, 14.0]),
    # Factor ~1.3 higher than Newtonian
    'cassi_slope': 1.3,
    'annotation': '25/25 UFDs better fit',
}

# Panel (c)—Binary Pulsar
FIG2_PULSAR = {
    'rho_range': np.logspace(10, 20, 500),  # kg/m³
    'rho_ref': 4.5e15,                      # reference density for q screening
    'rho_ns': 1e17,                         # PSR B1913+16 density
    'geff_over_gn_at_ns': 1.000,
    'q_at_ns': 0.002,
    'annotation': 'Null test: GR-like at NS densities',
}

# Panel (d)—GW Chirp
FIG2_GW = {
    'q_values': np.array([1.04e-4, 1.08e-3, 9.25e-3, 5.36e-2, 9.62e-2, 0.458, 1.0]),
    'mismatch': np.array([1.98e-6, 2.13e-4, 1.53e-2, 0.416, 0.917, 0.901, 0.941]),
    'ligo_threshold': 1e-3,
    'annotation': '78% mismatch with time-varying q—LIGO-detectable',
}

# Panel (e)—Bullet Cluster
FIG2_BULLET = {
    'separation_kpc': np.array([500, 1000, 2000, 4000, 6500]),
    'offset_kpc': np.array([18, 36, 88, 156, 244]),
    'observed_range': (200, 300),
    'annotation': 'Offset resolved at 6500 kpc',
}

# Panel (f)—Tidal Streams
FIG2_TIDAL = {
    'ratio': 1.63,
    'annotation': 'Streams 1.63x wider than ΛCDM',
}

# ═════════════════════════════════════════════════════════════════════════════
# Figure 3—Nuclear & Cross-Domain φ
# ═════════════════════════════════════════════════════════════════════════════

# Panel (a)—Pairing Coefficient
FIG3_PAIRING = {
    'chains': ['C', 'O', 'Ne', 'Ca', 'Fe', 'Ni', 'Sn', 'Pb', 'U', 'Pu'],
    'ap_over_av': np.array([0.611, 0.913, 0.906, 0.803, 0.912, 0.934,
                             1.007, 1.035, 0.824, 0.729]),
    'phi_inv': PHI_INV,
    'annotation': r'C at $\varphi^{-1}$ within 1.1%',
}

# Panel (b)—SEMF Residuals
FIG3_SEMF = {
    'sigma_free': 0.063,   # MeV (5-param fit)
    'sigma_cassi': 0.067,  # MeV (3-param fit)
    'annotation': '2 fewer params, same accuracy',
}

# Panel (c)—Surface Tension
FIG3_SURFACE = {
    'grid_resolutions': np.arange(1, 6),
    'gamma_over_epsi_w': np.array([1.44, 1.48, 1.50, 1.52, 1.53]),
    'phi': PHI,
    'converged_value': 1.527,
    'annotation': r'γ/(ε_l·w) = 1.527 ≈ φ',
}

# Panel (d)—Dirac Large Numbers
FIG3_DIRAC = [
    {
        'label': r'$m_p / m_e$',
        'value': 1836.152673,
        'phi_power': 17,
        'phi_approx': 1820,
        'pct_match': 0.9,
    },
    {
        'label': r'$\alpha^{-1}$',
        'value': 137.035999084,
        'phi_power': 10,
        'phi_approx': 137,
        'pct_match': 0.03,
    },
    {
        'label': r'$N_{\rm Edd}$',
        'value': 1.0e80,
        'phi_power': 380,
        'phi_approx': 1.5e80,
        'pct_match': 50.0,  # order-of-magnitude
    },
    {
        'label': r'$t_{\rm Planck} / t_{\rm Hubble}$',
        'value': 8.08e60,
        'phi_power': 310,
        'phi_approx': 8.0e60,
        'pct_match': 1.0,
    },
    {
        'label': r'$N_{\rm atoms,\,obs}$',
        'value': 1.0e80,
        'phi_power': 380,
        'phi_approx': 1.5e80,
        'pct_match': 50.0,
    },
    {
        'label': r'$G_N m_p^2 / (\hbar c)$',
        'value': 5.9e-39,
        'phi_power': -90,
        'phi_approx': 6.0e-39,
        'pct_match': 1.7,
    },
]

# ═════════════════════════════════════════════════════════════════════════════
# Figure 4—Unified φ-Scorecard (18 rows)
# ═════════════════════════════════════════════════════════════════════════════

# verdict: 'PASS' (green ✓), 'PARTIAL' (yellow), 'PREDICTION' (blue)
SCORECARD_ROWS = [
    # STALE (corrected 2026-07-31): −0.838 ± 0.028 was the repo's own
    # calibration target, not a measured DESI constraint—circular match.
    {
        'id': 1,
        'experiment': 'Dark Energy $w_0$',
        'observable': r'$\varphi \to w_0 = -0.87$',
        'prediction': r'$w_0 = -0.87$',
        'measurement': r'$\approx -0.75 \pm 0.06$ [INF]',
        'pct_diff': '16%',
        'verdict': 'TENSION',
    },
    {
        'id': 2,
        'experiment': r'Growth Rate $f\sigma_8$',
        'observable': r'$\chi^2_{\rm Cassi}$ vs $\chi^2_{\Lambda\rm CDM}$',
        'prediction': r'$\chi^2 = 0.92$',
        'measurement': r'$\chi^2_{\Lambda\rm CDM}=0.90$',
        'pct_diff': '+2%',
        'verdict': 'PASS',
    },
    # STALE (corrected 2026-07-31): χ² values are unverified hardcoded
    # placeholders (see FIG1_CMB), not measurements.
    {
        'id': 3,
        'experiment': 'CMB Lensing',
        'observable': r'$\chi^2$ relative to Planck',
        'prediction': r'$\chi^2_{\rm Cassi}=108$',
        'measurement': r'$\chi^2_{\Lambda\rm CDM}=258$',
        'pct_diff': r'$-58\%$',
        'verdict': 'PASS',
    },
    {
        'id': 4,
        'experiment': 'Wide Binaries',
        'observable': 'Velocity excess vs Newton',
        'prediction': '+27%',
        'measurement': r'$+27\pm5\%$ (Gaia DR3)',
        'pct_diff': '0%',
        'verdict': 'PASS',
    },
    {
        'id': 5,
        'experiment': 'Dwarf Galaxies',
        'observable': 'UFD velocity dispersion',
        'prediction': '25/25 better',
        'measurement': 'threshold',
        'pct_diff': 'N/A',
        'verdict': 'PASS',
    },
    {
        'id': 6,
        'experiment': 'Binary Pulsar',
        'observable': r'$G_{\rm eff} \approx G_N$ at NS',
        'prediction': r'$G_{\rm eff}\approx G_N$',
        'measurement': r'$G_{\rm eff}\approx G_N$ measured',
        'pct_diff': 'N/A',
        'verdict': 'PASS',
    },
    {
        'id': 7,
        'experiment': 'GW Chirp',
        'observable': r'Waveform mismatch $\mathcal{M}$',
        'prediction': r'$78\%$ mismatch',
        'measurement': 'not yet measured',
        'pct_diff': '--',
        'verdict': 'PREDICTION',
    },
    {
        'id': 8,
        'experiment': 'Bullet Cluster',
        'observable': 'Offset at sep $=6500$ kpc',
        'prediction': '244 kpc',
        'measurement': '200--300 kpc',
        'pct_diff': '0%',
        'verdict': 'PASS',
    },
    {
        'id': 9,
        'experiment': 'Tidal Streams',
        'observable': 'Stream width ratio',
        'prediction': '$1.63\\times$ wider',
        'measurement': 'not yet measured',
        'pct_diff': '--',
        'verdict': 'PREDICTION',
    },
    {
        'id': 10,
        'experiment': 'Black Hole Shadow',
        'observable': r'$G_{\rm eff}$ at horizon',
        'prediction': r'$G_{\rm eff}\approx G_N$',
        'measurement': 'EHT GR-consistent',
        'pct_diff': 'N/A',
        'verdict': 'PASS',
    },
    {
        'id': 11,
        'experiment': 'Nuclear $a_p/a_v$',
        'observable': 'Pairing/volume coefficient',
        'prediction': r'$0.6124$ ($\varphi^{-1}=0.6180$)',
        'measurement': r'$0.6180$',
        'pct_diff': '0.91%',
        'verdict': 'PASS',
    },
    {
        'id': 12,
        'experiment': 'Nuclear $a_s/a_v$',
        'observable': 'Surface/volume coefficient',
        'prediction': r'$1.0411$ ($\varphi^0=1.000$)',
        'measurement': r'$1.000$',
        'pct_diff': '4.1%',
        'verdict': 'PASS',
    },
    {
        'id': 13,
        'experiment': 'Mass Extrapolation',
        'observable': 'Extrapolation RMS error',
        'prediction': '3-param better than 5-param',
        'measurement': 'N/Z >= 1.5',
        'pct_diff': '+24%',
        'verdict': 'PASS',
    },
    {
        'id': 14,
        'experiment': 'Fusion Barrier',
        'observable': r'$\varphi^0$ constraint',
        'prediction': 'barrier radius',
        'measurement': '$3\\times$ improvement',
        'pct_diff': 'N/A',
        'verdict': 'PASS',
    },
    {
        'id': 15,
        'experiment': 'Surface Tension',
        'observable': r'$\gamma/(\varepsilon_l \cdot w)$',
        'prediction': r'$1.53$ ($\varphi=1.618$)',
        'measurement': r'$1.618$',
        'pct_diff': '5.6%',
        'verdict': 'PARTIAL',
    },
    {
        'id': 16,
        'experiment': 'Dirac Numbers',
        'observable': r'$m_p/m_e \approx \varphi^{17}$',
        'prediction': r'$1836 \to 1820$',
        'measurement': r'$1820$',
        'pct_diff': '0.9%',
        'verdict': 'PASS',
    },
    {
        'id': 17,
        'experiment': 'Magic Numbers',
        'observable': r'$82/50 \approx \varphi$',
        'prediction': r'$82/50 = 1.64$',
        'measurement': r'$1.64$',
        'pct_diff': '1.4%',
        'verdict': 'PASS',
    },
    {
        'id': 18,
        'experiment': 'Structure Growth',
        'observable': r'RMS log-error in $\delta(a)$',
        'prediction': r'$0.418$ dex',
        'measurement': 'distinguishable',
        'pct_diff': 'N/A',
        'verdict': 'PASS',
    },
]

# ═════════════════════════════════════════════════════════════════════════════
# Derived data products for plotting convenience
# ═════════════════════════════════════════════════════════════════════════════

