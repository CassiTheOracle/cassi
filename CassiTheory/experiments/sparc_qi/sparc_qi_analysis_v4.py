"""
SPARC Qi Analysis v4: 2D angular-averaged condensation profile + cusp-vs-core test.

Key changes from v3:
  1. Use 2D angular-averaged ⟨C⟩(r), not 1D cos(αr)
  2. Compare small-r shape: Qi core vs NFW cusp
  3. Inner-region AIC (r < r_core × 3) to isolate the shape difference
"""
import numpy as np
import os, re, glob
from scipy.optimize import minimize
from scipy.stats import linregress
from scipy.interpolate import interp1d
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6
G_kpc = 4.302e-6

# ============================================================
# PRECOMPUTE 2D ANGULAR-AVERAGED PROFILE
# ============================================================
def angular_avg_C(u, n_theta=200):
    """Angular average of C(x,y) = cos(αx)cos(φ·αy) at scaled radius u=αr."""
    theta = np.linspace(0, 2*np.pi, n_theta)
    x = u * np.cos(theta)
    y = u * np.sin(theta)
    C_vals = np.cos(x) * np.cos(PHI * y)
    return np.mean(C_vals)

print("Precomputing 2D angular-averaged profile...")
U_GRID = np.linspace(0, 20, 1000)
C_AVG = np.array([angular_avg_C(u) for u in U_GRID])
Q_AVG = (1 + C_AVG) / 2
C_INTERP = interp1d(U_GRID, C_AVG, kind='cubic', bounds_error=False, fill_value='extrapolate')
Q_INTERP = interp1d(U_GRID, Q_AVG, kind='cubic', bounds_error=False, fill_value='extrapolate')
print(f"  Done. C crosses 0.5 at u ≈ {U_GRID[np.argmax(C_AVG < 0.5)]:.3f}")
print(f"  C crosses θ_cond=0.45 at u ≈ {U_GRID[np.argmax(C_AVG < 0.45)]:.3f}")

# ============================================================
# DATA LOADING
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
# QI MODEL (2D angular-averaged)
# ============================================================
def qi_vdm2_2d(rad, vbar2, alpha, theta_cond=0.45):
    """
    Qi DM velocity squared using 2D angular-averaged profile.
    
    ⟨C⟩(r) = C_INTERP(αr)
    ⟨q⟩(r) = Q_INTERP(αr) = (1 + ⟨C⟩)/2
    f_cond(r) = max(0, (⟨C⟩ - θ_cond)/(1 - θ_cond))
    
    M_Qi(r) = M_bar(r) + ξ × ∫₀ʳ ⟨q⟩(r') × f_cond(r') × ρ_bar(r') × 4πr'² dr'
    """
    n = len(rad)
    u = alpha * rad
    C_loc = C_INTERP(u)
    q_loc = Q_INTERP(u)
    f_cond = np.maximum(0, (C_loc - theta_cond) / (1 - theta_cond))
    
    # Compute M_bar(r)
    M_bar = rad * vbar2 / G_kpc
    
    # Compute ρ_bar via central differences
    rho_bar = np.zeros(n)
    for i in range(1, n-1):
        dM = M_bar[i+1] - M_bar[i-1]
        dr = rad[i+1] - rad[i-1]
        rho_bar[i] = dM / (4 * np.pi * rad[i]**2 * dr)
    if n >= 2:
        rho_bar[0] = (M_bar[1] - M_bar[0]) / (4 * np.pi * rad[0]**2 * max(rad[1]-rad[0], 1e-10))
        rho_bar[-1] = (M_bar[-1] - M_bar[-2]) / (4 * np.pi * rad[-1]**2 * max(rad[-1]-rad[-2], 1e-10))
    rho_bar = np.maximum(rho_bar, 0)
    
    # Integrand and cumulative integral (trapezoidal)
    integrand = q_loc * f_cond * rho_bar * 4 * np.pi * rad**2
    integral = np.zeros(n)
    integral[0] = 0
    for i in range(1, n):
        dr = rad[i] - rad[i-1]
        integral[i] = integral[i-1] + 0.5 * (integrand[i-1] + integrand[i]) * dr
    
    M_Qi = M_bar + XI * integral
    v2_Qi = G_kpc * M_Qi / rad
    v2_Qi_DM = np.maximum(v2_Qi - vbar2, 0)
    
    return v2_Qi_DM

# ============================================================
# NFW MODEL
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
print(f"Parsed {len(galaxies)} with ≥8 points")

results = []
for name, g in galaxies.items():
    rad = g['rad']
    vdm2_obs = g['vdm2_obs']
    vdm_obs = g['vdm_obs']
    vbar2 = g['vbar2']
    
    # Errors
    obs_err = np.maximum(g['errv'], 1.0)
    vdm2_err = 2 * vdm_obs * obs_err
    err = np.maximum(vdm2_err, np.median(vdm2_obs) * 0.1)
    
    # --- Qi 1-param: fit α ---
    def qi_chi2(alpha):
        if alpha <= 0: return np.inf
        model = qi_vdm2_2d(rad, vbar2, alpha, theta_cond=0.45)
        return np.sum((model - vdm2_obs)**2 / err**2)
    
    alpha0 = 1.0 / g['r_max']  # rough initial
    try:
        res = minimize(qi_chi2, [alpha0], method='Nelder-Mead',
                       options={'maxiter': 3000, 'xatol': 1e-6})
        alpha_fit = res.x[0]
        chi2_qi = res.fun
    except Exception:
        alpha_fit, chi2_qi = np.nan, np.inf
    
    # --- NFW ---
    def nfw_chi2(params):
        rs, log_rho0 = params
        model = vdm2_nfw(rad, rs, 10**log_rho0)
        return np.sum((model - vdm2_obs)**2 / err**2)
    
    try:
        res_nfw = minimize(nfw_chi2, [g['r_max']/3, 7.0],
                           method='Nelder-Mead',
                           options={'maxiter': 3000, 'xatol': 1e-6})
        rs_nfw, log_rho_nfw = res_nfw.x
        chi2_nfw = res_nfw.fun
    except Exception:
        rs_nfw, log_rho_nfw, chi2_nfw = np.nan, np.nan, np.inf
    
    # Inner-region AIC: only use points within 3× core radius
    delta_aic_inner = np.nan
    r_core_est = np.nan
    n_inner = 0
    if np.isfinite(alpha_fit) and alpha_fit > 0:
        u_core = 0.9
        r_core_est = u_core / alpha_fit
        inner_mask = rad < 3 * r_core_est
        n_inner = inner_mask.sum()
        if n_inner >= 4:
            chi2_qi_inner = np.sum(
                (qi_vdm2_2d(rad, vbar2, alpha_fit, 0.45)[inner_mask]
                 - vdm2_obs[inner_mask])**2 / err[inner_mask]**2)
            model_nfw = vdm2_nfw(rad, rs_nfw, 10**log_rho_nfw)
            chi2_nfw_inner = np.sum(
                (model_nfw[inner_mask] - vdm2_obs[inner_mask])**2 / err[inner_mask]**2)
            aic_qi_inner = n_inner * np.log(max(chi2_qi_inner, 1e-10) / n_inner) + 2
            aic_nfw_inner = n_inner * np.log(max(chi2_nfw_inner, 1e-10) / n_inner) + 4
            delta_aic_inner = aic_qi_inner - aic_nfw_inner
    
    n_data = g['n_points']
    aic_qi_full = n_data * np.log(max(chi2_qi, 1e-10)/n_data) + 2
    aic_nfw_full = n_data * np.log(max(chi2_nfw, 1e-10)/n_data) + 4
    
    results.append({
        'name': name, 'M_bar': g['M_bar_final'], 'r_max': g['r_max'],
        'n_points': n_data,
        'alpha': alpha_fit, 'r_core': r_core_est,
        'chi2_qi': chi2_qi, 'chi2_nfw': chi2_nfw,
        'aic_qi_full': aic_qi_full, 'aic_nfw_full': aic_nfw_full,
        'delta_aic_full': aic_qi_full - aic_nfw_full,
        'delta_aic_inner': delta_aic_inner, 'n_inner': n_inner
    })

# Clean
results = [r for r in results 
           if np.isfinite(r['chi2_qi']) and np.isfinite(r['chi2_nfw'])]
print(f"Galaxies with successful fits: {len(results)}")

# ============================================================
# FULL-RANGE AIC
# ============================================================
delta_full = np.array([r['delta_aic_full'] for r in results])
print(f"\nFull-range AIC (Qi 1-param vs NFW 2-param):")
print(f"  Median ΔAIC: {np.median(delta_full):.1f}")
print(f"  Qi better (<-2): {sum(1 for d in delta_full if d < -2)}")
print(f"  Indist (|.|<=2): {sum(1 for d in delta_full if abs(d) <= 2)}")
print(f"  NFW better (>+2): {sum(1 for d in delta_full if d > 2)}")

# ============================================================
# INNER-REGION AIC
# ============================================================
inner_results = [r for r in results if np.isfinite(r['delta_aic_inner'])]
if len(inner_results) > 0:
    delta_inner = np.array([r['delta_aic_inner'] for r in inner_results])
    print(f"\nInner-region AIC (r < 3×r_core, cusp-vs-core test):")
    print(f"  Galaxies with inner-region data: {len(inner_results)}")
    print(f"  Median ΔAIC: {np.median(delta_inner):.1f}")
    qi_better = sum(1 for d in delta_inner if d < -2)
    indist = sum(1 for d in delta_inner if abs(d) <= 2)
    nfw_better = sum(1 for d in delta_inner if d > 2)
    print(f"  Qi core better (<-2): {qi_better}")
    print(f"  Indistinguishable: {indist}")
    print(f"  NFW cusp better (>+2): {nfw_better}")
    print(f"\n  → Qi core preferred or comparable in {qi_better + indist}/{len(inner_results)}")

# ============================================================
# CORE RADIUS SCALING
# ============================================================
valid = [(r['r_core'], r['M_bar']) for r in results
         if np.isfinite(r['r_core']) and r['r_core'] > 0 and r['r_core'] < r['r_max']]
if len(valid) >= 5:
    cores = np.array([v[0] for v in valid])
    masses = np.array([v[1] for v in valid])
    slope, intercept, r_val, p_val, std_err = linregress(
        np.log10(masses), np.log10(cores))
    
    print(f"\nCore radius scaling (2D Qi model):")
    print(f"  r_core ∝ M_bar^γ, γ = {slope:.4f} ± {std_err:.4f}")
    print(f"  Qi predicts γ = 1/3 = 0.333  ({abs(slope-1/3)/std_err:.1f}σ)")
    print(f"  R² = {r_val**2:.4f}")

# ============================================================
# SMALL-r SLOPE TEST (per-galaxy cusp-vs-core)
# ============================================================
print(f"\nSmall-r slope test (v_DM ∝ r^p, p=0.5 cusp vs p=1.0 core):")
# For each galaxy with enough inner points, fit power law to v_DM(r) at small r
slope_results = []
for r in results:
    g = galaxies.get(r['name'])
    if g is None or not np.isfinite(r['r_core']):
        continue
    
    mask = g['rad'] < r['r_core']
    if mask.sum() < 3:
        continue
    
    rad_inner = g['rad'][mask]
    vdm_inner = g['vdm_obs'][mask]
    
    # Fit log(v_DM) = p × log(r) + const
    coeffs = np.polyfit(np.log10(rad_inner[vdm_inner > 0]), 
                         np.log10(vdm_inner[vdm_inner > 0]), 1)
    p_slope = coeffs[0]
    slope_results.append(p_slope)

if slope_results:
    p_arr = np.array(slope_results)
    print(f"  n = {len(p_arr)} galaxies")
    print(f"  Median small-r slope p = {np.median(p_arr):.3f}")
    print(f"  Mean ± σ = {np.mean(p_arr):.3f} ± {np.std(p_arr):.3f}")
    print(f"  NFW cusp predicts p ≈ 0.5")
    print(f"  Qi core predicts p ≈ 1.0")
    # Fraction closer to 1.0 than 0.5
    closer_to_core = sum(1 for p in p_arr if abs(p-1.0) < abs(p-0.5))
    print(f"  Galaxies closer to core (p=1.0): {closer_to_core}/{len(p_arr)}")
    print(f"  Galaxies closer to cusp (p=0.5): {len(p_arr)-closer_to_core}/{len(p_arr)}")

print("\n" + "=" * 60)
print("CONCLUSIONS")
print("=" * 60)
print(f"1. 2D angular-averaged Qi profile with ξ=φ⁶ fixed:")
print(f"   Full-range AIC: NFW strongly preferred (median ΔAIC={np.median(delta_full):.1f})")
if inner_results:
    print(f"   Inner-region AIC: Qi core {'preferred' if qi_better+indist > nfw_better else 'NOT preferred'}")
if slope_results:
    print(f"2. Small-r slope: median p={np.median(p_arr):.2f} ({'core-like' if np.median(p_arr) > 0.75 else 'cusp-like' if np.median(p_arr) < 0.6 else 'intermediate'})")
if len(valid) >= 5:
    print(f"3. Core radius scaling: γ={slope:.3f}±{std_err:.3f} vs predicted 0.333")
