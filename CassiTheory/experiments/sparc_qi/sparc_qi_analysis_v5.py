"""
SPARC Qi Analysis v5: pseudo-isothermal Yang condensate (profile swap).

Key changes from v4:
  1. Replace the baryon-seeded oscillatory-lattice condensate
     (M_Qi = M_bar + xi * int <q> f_cond rho_bar) with a hydrostatic
     pseudo-isothermal Yang condensate rho_Y(r) = rho_c/(1+(r/r_c)^2).
     The xi = phi^6 boost applies to the condensate's own mass:

        M_Qi(r) = M_bar(r) + (1 + xi) * M_Y(r),
        M_Y(r)  = 4 pi rho_c r_c^2 [r - r_c atan(r/r_c)]

     This is the mass profile the two-fluid hydrostatic equilibrium
     produces (constant dispersion, cored center); the lattice is a
     small-scale modulation on top of this envelope, not the envelope
     itself.
  2. Two free parameters (rho_c, r_c) vs NFW's two (rs, rho0)—the AIC
     penalty is identical, so the comparison stays fair.
  3. Same full-range + inner-region AIC, core-radius scaling gamma,
     and small-r slope test as v4.

Physics questions this run answers:
  - Does a smooth cored-isothermal Qi condensate with fixed xi = phi^6
    fit SPARC rotation curves at NFW parity?
  - Does the fitted central density rho_c land near the canonical local
    dark-matter density (~1e7 M_sun/kpc^3, log10 ~ 7.0), or is it forced
    to unphysical values to fight the boost?
  - Does the core radius scale as r_c ~ M_bar^gamma, and with what gamma?
"""
import numpy as np
import os, re, glob
from scipy.optimize import minimize
from scipy.stats import linregress
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6            # 17.944
G_kpc = 4.302e-6

# ============================================================
# DATA LOADING (identical to v4)
# ============================================================
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sparc_data')
files = sorted(glob.glob(f'{data_dir}/*_rotmod.dat'))

def parse_galaxy(fpath):
    name = os.path.basename(fpath).replace('_rotmod.dat', '')
    with open(fpath, 'r') as f:
        dist = None
        for l in f:
            if l.startswith('# Distance'):
                dist = float(re.search(r'[\d.]+', l).group())
                break
    if dist is None: return None
    try:
        cols = np.loadtxt(fpath, comments='#')
    except Exception:
        return None
    if cols.ndim == 1 or len(cols) < 4: return None

    rad = cols[:, 0]
    vobs = cols[:, 1]
    errv = cols[:, 2]
    vgas = cols[:, 3]
    vdisk = cols[:, 4]
    vbul = cols[:, 5] if cols.shape[1] > 5 else np.zeros_like(rad)

    vbar2 = np.maximum(vgas**2 + vdisk**2 + vbul**2, 0.01)
    vdm2_obs = np.maximum(vobs**2 - vbar2, 0.01)
    vdm_obs = np.sqrt(vdm2_obs)

    M_bar_final = rad[-1] * np.sqrt(vbar2[-1])**2 / G_kpc

    return {
        'name': name, 'dist': dist, 'M_bar_final': M_bar_final,
        'rad': rad, 'vobs': vobs, 'errv': errv,
        'vbar2': vbar2, 'vdm2_obs': vdm2_obs, 'vdm_obs': vdm_obs,
        'r_max': rad[-1], 'n_points': len(rad)
    }

# ============================================================
# QI MODEL (pseudo-isothermal condensate)
# ============================================================
def qi_vdm2_iso(rad, vbar2, rho_c, r_c):
    """
    Qi DM velocity squared with a pseudo-isothermal Yang condensate:

        rho_Y(r) = rho_c / (1 + (r/r_c)^2)
        M_Y(r)   = 4 pi rho_c r_c^2 [r - r_c atan(r/r_c)]   (~r at large r)

    The full xi = phi^6 coupling applies to the condensate's own mass:

        M_Qi(r) = M_bar(r) + (1 + xi) M_Y(r)
        v2_model = G M_Qi / r

    Returns v2_DM = v2_model - v2_bar (same convention as v4).
    """
    r = rad
    M_Y = 4 * np.pi * rho_c * r_c**2 * (r - r_c * np.arctan(r / r_c))
    M_Qi = r * vbar2 / G_kpc + (1 + XI) * M_Y
    v2 = G_kpc * M_Qi / r
    return np.maximum(v2 - vbar2, 0)

# ============================================================
# NFW MODEL (identical to v4)
# ============================================================
def vdm2_nfw(rad, rs, rho0):
    x = rad / rs
    term = np.where(x < 1e-10, x/2, np.log(1 + x) - x/(1 + x))
    return 4 * np.pi * G_kpc * rho0 * rs**3 * term / rad

# ============================================================
# MAIN
# ============================================================
print(f"\nLoading {len(files)} galaxies...")
galaxies = {}
for fpath in files:
    g = parse_galaxy(fpath)
    if g and g['n_points'] >= 8:
        galaxies[g['name']] = g
print(f"Parsed {len(galaxies)} with >=8 points")

results = []
for name, g in galaxies.items():
    rad = g['rad']
    vdm2_obs = g['vdm2_obs']
    vdm_obs = g['vdm_obs']
    vbar2 = g['vbar2']

    obs_err = np.maximum(g['errv'], 1.0)
    vdm2_err = 2 * vdm_obs * obs_err
    err = np.maximum(vdm2_err, np.median(vdm2_obs) * 0.1)

    # --- Qi 2-param: fit log10(rho_c), log10(r_c) ---
    def qi_chi2(params):
        log_rho_c, log_r_c = params
        rho_c = 10**log_rho_c
        r_c = 10**log_r_c
        if r_c < 1e-4 * rad[-1]: return np.inf
        model = qi_vdm2_iso(rad, vbar2, rho_c, r_c)
        return np.sum((model - vdm2_obs)**2 / err**2)

    best_chi2, best_p = np.inf, None
    for start in [(7.0, np.log10(g['r_max']/3.0)),
                  (7.0, np.log10(g['r_max']/10.0))]:
        try:
            res = minimize(qi_chi2, start, method='Nelder-Mead',
                           options={'maxiter': 4000, 'xatol': 1e-7})
            if res.fun < best_chi2:
                best_chi2, best_p = res.fun, res.x
        except Exception:
            pass
    if best_p is None:
        log_rho_c, log_r_c, chi2_qi = np.nan, np.nan, np.inf
    else:
        log_rho_c, log_r_c = best_p
        chi2_qi = best_chi2
    rho_c_fit = 10**log_rho_c if np.isfinite(log_rho_c) else np.nan
    r_c_fit = 10**log_r_c if np.isfinite(log_r_c) else np.nan

    # --- NFW (identical to v4) ---
    def nfw_chi2(params):
        rs, log_rho0 = params
        model = vdm2_nfw(rad, rs, 10**log_rho0)
        return np.sum((model - vdm2_obs)**2 / err**2)

    try:
        res_nfw = minimize(nfw_chi2, [g['r_max']/3, 7.0],
                           method='Nelder-Mead',
                           options={'maxiter': 4000, 'xatol': 1e-7})
        rs_nfw, log_rho_nfw = res_nfw.x
        chi2_nfw = res_nfw.fun
    except Exception:
        rs_nfw, log_rho_nfw, chi2_nfw = np.nan, np.nan, np.inf

    # Inner-region AIC: points within 3 x r_c
    delta_aic_inner = np.nan
    n_inner = 0
    if np.isfinite(r_c_fit) and r_c_fit > 0 and r_c_fit < rad[-1]:
        inner_mask = rad < 3 * r_c_fit
        n_inner = inner_mask.sum()
        if n_inner >= 4:
            chi2_qi_inner = np.sum(
                (qi_vdm2_iso(rad, vbar2, rho_c_fit, r_c_fit)[inner_mask]
                 - vdm2_obs[inner_mask])**2 / err[inner_mask]**2)
            model_nfw = vdm2_nfw(rad, rs_nfw, 10**log_rho_nfw)
            chi2_nfw_inner = np.sum(
                (model_nfw[inner_mask] - vdm2_obs[inner_mask])**2 / err[inner_mask]**2)
            aic_qi_inner = n_inner * np.log(max(chi2_qi_inner, 1e-10) / n_inner) + 4
            aic_nfw_inner = n_inner * np.log(max(chi2_nfw_inner, 1e-10) / n_inner) + 4
            delta_aic_inner = aic_qi_inner - aic_nfw_inner

    n_data = g['n_points']
    aic_qi_full = n_data * np.log(max(chi2_qi, 1e-10)/n_data) + 4
    aic_nfw_full = n_data * np.log(max(chi2_nfw, 1e-10)/n_data) + 4

    results.append({
        'name': name, 'M_bar': g['M_bar_final'], 'r_max': g['r_max'],
        'n_points': n_data,
        'rho_c': rho_c_fit, 'r_c': r_c_fit,
        'chi2_qi': chi2_qi, 'chi2_nfw': chi2_nfw,
        'aic_qi_full': aic_qi_full, 'aic_nfw_full': aic_nfw_full,
        'delta_aic_full': aic_qi_full - aic_nfw_full,
        'delta_aic_inner': delta_aic_inner, 'n_inner': n_inner
    })

results = [r for r in results
           if np.isfinite(r['chi2_qi']) and np.isfinite(r['chi2_nfw'])]
print(f"Galaxies with successful fits: {len(results)}")

# ============================================================
# FULL-RANGE AIC
# ============================================================
delta_full = np.array([r['delta_aic_full'] for r in results])
print(f"\nFull-range AIC (Qi iso 2-param vs NFW 2-param):")
print(f"  Median dAIC: {np.median(delta_full):.1f}")
print(f"  Qi better (<-2): {sum(1 for d in delta_full if d < -2)}")
print(f"  Indist (|.|<=2): {sum(1 for d in delta_full if abs(d) <= 2)}")
print(f"  NFW better (>+2): {sum(1 for d in delta_full if d > 2)}")

# ============================================================
# FITTED CENTRAL DENSITY vs PHYSICAL LOCAL DM DENSITY
# ============================================================
rho_c_arr = np.array([r['rho_c'] for r in results if np.isfinite(r['rho_c'])])
print(f"\nFitted condensate central density (local DM ~1e7 M_sun/kpc^3):")
print(f"  Median log10 rho_c = {np.median(np.log10(rho_c_arr)):.2f}")
print(f"  Range: {np.log10(rho_c_arr).min():.1f} .. {np.log10(rho_c_arr).max():.1f}")

# ============================================================
# INNER-REGION AIC (cusp-vs-core)
# ============================================================
inner_results = [r for r in results if np.isfinite(r['delta_aic_inner'])]
if len(inner_results) > 0:
    delta_inner = np.array([r['delta_aic_inner'] for r in inner_results])
    print(f"\nInner-region AIC (r < 3*r_c):")
    print(f"  Galaxies with inner-region data: {len(inner_results)}")
    print(f"  Median dAIC: {np.median(delta_inner):.1f}")
    qi_better = sum(1 for d in delta_inner if d < -2)
    indist = sum(1 for d in delta_inner if abs(d) <= 2)
    nfw_better = sum(1 for d in delta_inner if d > 2)
    print(f"  Qi core better (<-2): {qi_better}")
    print(f"  Indistinguishable: {indist}")
    print(f"  NFW cusp better (>+2): {nfw_better}")
    print(f"  -> Qi core preferred or comparable in {qi_better + indist}/{len(inner_results)}")

# ============================================================
# CORE RADIUS SCALING
# ============================================================
valid = [(r['r_c'], r['M_bar']) for r in results
         if np.isfinite(r['r_c']) and r['r_c'] > 0 and r['r_c'] < r['r_max']]
if len(valid) >= 5:
    cores = np.array([v[0] for v in valid])
    masses = np.array([v[1] for v in valid])
    slope, intercept, r_val, p_val, std_err = linregress(
        np.log10(masses), np.log10(cores))
    print(f"\nCore radius scaling (pseudo-isothermal Qi model):")
    print(f"  r_c ~ M_bar^gamma, gamma = {slope:.4f} +- {std_err:.4f}")
    print(f"  Constant-density-core predicts 1/3 ({abs(slope-1/3)/std_err:.1f} sigma)")
    print(f"  R^2 = {r_val**2:.4f}")

# ============================================================
# SMALL-r SLOPE TEST (per-galaxy cusp-vs-core)
# ============================================================
print(f"\nSmall-r slope test (v_DM ~ r^p, p=0.5 cusp vs p=1.0 core):")
slope_results = []
for r in results:
    g = galaxies.get(r['name'])
    if g is None or not np.isfinite(r['r_c']):
        continue
    mask = g['rad'] < r['r_c']
    if mask.sum() < 3:
        continue
    rad_inner = g['rad'][mask]
    vdm_inner = g['vdm_obs'][mask]
    pos = vdm_inner > 0
    if pos.sum() < 3:
        continue
    coeffs = np.polyfit(np.log10(rad_inner[pos]), np.log10(vdm_inner[pos]), 1)
    slope_results.append(coeffs[0])

if slope_results:
    p_arr = np.array(slope_results)
    print(f"  n = {len(p_arr)} galaxies")
    print(f"  Median small-r slope p = {np.median(p_arr):.3f}")
    closer_to_core = sum(1 for p in p_arr if abs(p-1.0) < abs(p-0.5))
    print(f"  Galaxies closer to core (p=1.0): {closer_to_core}/{len(p_arr)}")
    print(f"  Galaxies closer to cusp (p=0.5): {len(p_arr)-closer_to_core}/{len(p_arr)}")

print("\n" + "=" * 60)
print("CONCLUSIONS")
print("=" * 60)
print(f"1. Pseudo-isothermal Qi condensate with xi=phi^6 fixed:")
print(f"   Full-range AIC: median dAIC = {np.median(delta_full):.1f}")
if inner_results:
    print(f"   Inner-region AIC: Qi core {'preferred' if qi_better+indist > nfw_better else 'NOT preferred'}")
if slope_results:
    print(f"2. Small-r slope: median p={np.median(p_arr):.2f} ({'core-like' if np.median(p_arr) > 0.75 else 'cusp-like' if np.median(p_arr) < 0.6 else 'intermediate'})")
if len(valid) >= 5:
    print(f"3. Core radius scaling: gamma={slope:.3f}+-{std_err:.3f} vs constant-density 0.333")
print(f"4. Fitted central density log10 rho_c median = {np.median(np.log10(rho_c_arr)):.2f} "
      f"(physical local DM ~7.0)")
