"""
SPARC Qi Analysis v3: Proper numerical integral with condensed density cutoff.

Correct model:
  M_Qi(r) = M_bar(r) + ξ × ∫₀ʳ q(r') × ρ_cond(r') × 4πr'² dr'
  v²_Qi(r) = G × M_Qi(r) / r

where:
  q(r') = (1 + cos(αr'))/2
  ρ_cond(r') = ρ_bar(r') × max(0, (C(r') - θ_cond)/(1 - θ_cond))^n_cond
  C(r') = cos(αr') (1D radial slice)

ξ = φ⁶ is FIXED. Free parameters: α (1 param) or (α, θ_cond) (2 params).
"""
import numpy as np
import os, re, glob
from scipy.optimize import minimize
from scipy.stats import linregress
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6  # ≈ 17.944—FIXED
G_kpc = 4.302e-6

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
    
    M_bar_final = rad[-1] * np.sqrt(vbar2[-1])**2 / G_kpc
    
    return {
        'name': name, 'dist': dist, 'M_bar_final': M_bar_final,
        'rad': rad, 'vobs': vobs, 'errv': errv,
        'vbar2': vbar2, 'vdm2_obs': vdm2_obs,
        'r_max': rad[-1], 'n_points': len(rad)
    }

def qi_vdm2(rad, vbar2, alpha, theta_cond=0.45, n_cond=1.0):
    """
    Qi dark matter velocity squared using proper numerical integral.
    
    Parameters:
      α: spatial frequency (sets core radius)
      θ_cond: condensation threshold (default 0.45)
      n_cond: condensation exponent (default 1.0)
    
    Model:
      M_Qi[i] = M_bar[i] + ξ × Σ_{j<i} q(r_j) × ρ_cond(r_j) × 4πr_j² × Δr_j
      v²_Qi_DM[i] = G × (M_Qi[i] - M_bar[i]) / r[i]
    
    ξ = φ⁶ is FIXED.
    """
    n = len(rad)
    
    # Compute M_bar at each radius
    M_bar = rad * vbar2 / G_kpc
    
    # Compute ρ_bar: dM_bar/dr / (4πr²) using central differences
    rho_bar = np.zeros(n)
    # Interior points: central difference
    for i in range(1, n-1):
        dM = M_bar[i+1] - M_bar[i-1]
        dr = rad[i+1] - rad[i-1]
        rho_bar[i] = dM / (4 * np.pi * rad[i]**2 * dr)
    # Endpoints: one-sided
    if n >= 2:
        rho_bar[0] = (M_bar[1] - M_bar[0]) / (4 * np.pi * rad[0]**2 * max(rad[1]-rad[0], 1e-10))
        rho_bar[-1] = (M_bar[-1] - M_bar[-2]) / (4 * np.pi * rad[-1]**2 * max(rad[-1]-rad[-2], 1e-10))
    
    rho_bar = np.maximum(rho_bar, 0)  # density must be non-negative
    
    # Condensation field and cutoff
    C = np.cos(alpha * rad)
    # Condensed fraction: max(0, (C - θ_cond)/(1 - θ_cond))
    f_cond = np.maximum(0, (C - theta_cond) / (1 - theta_cond))
    f_cond = f_cond ** n_cond
    rho_cond = rho_bar * f_cond
    
    # Qi coherence
    q = (1 + C) / 2
    
    # Integrate: cumulative sum ∫₀ʳ q(r') × ρ_cond(r') × 4πr'² dr'
    # Trapezoidal integration
    integral = np.zeros(n)
    integrand = q * rho_cond * 4 * np.pi * rad**2
    
    # Cumulative trapezoidal
    integral[0] = 0
    for i in range(1, n):
        dr = rad[i] - rad[i-1]
        integral[i] = integral[i-1] + 0.5 * (integrand[i-1] + integrand[i]) * dr
    
    # Qi-enhanced enclosed mass
    M_Qi = M_bar + XI * integral
    
    # Qi DM velocity squared
    v2_Qi = G_kpc * M_Qi / rad
    v2_Qi_DM = np.maximum(v2_Qi - vbar2, 0)
    
    return v2_Qi_DM

# ============================================================
# MAIN
# ============================================================
print("=" * 60)
print("SPARC Qi Analysis v3: Proper integral, ξ = φ⁶ fixed")
print("=" * 60)

print(f"Loading {len(files)} galaxies...")
galaxies = {}
for fpath in files:
    g = parse_galaxy(fpath)
    if g and g['n_points'] >= 8:
        galaxies[g['name']] = g
print(f"Parsed {len(galaxies)} galaxies with ≥8 points")

# Fit to each galaxy
results = []
for name, g in galaxies.items():
    rad = g['rad']
    vdm2_obs = g['vdm2_obs']
    vbar2 = g['vbar2']
    obs_err = np.maximum(g['errv'], 1.0)
    vdm2_err = 2 * g['vobs'] * obs_err / np.sqrt(np.maximum(vdm2_obs, 1.0))
    err = np.maximum(vdm2_err, np.median(vdm2_obs) * 0.1)
    
    # --- Qi 1-param: fit α, fix θ_cond=0.45 ---
    def qi_chi2_1p(alpha):
        model = qi_vdm2(rad, vbar2, alpha[0], theta_cond=0.45, n_cond=1.0)
        return np.sum((model - vdm2_obs)**2 / err**2)
    
    alpha0 = 2.0 / g['r_max']  # initial: ~2 oscillations in data range
    try:
        res1 = minimize(qi_chi2_1p, [alpha0], method='Nelder-Mead',
                        options={'maxiter': 3000, 'xatol': 1e-6})
        alpha_1p = res1.x[0]
        chi2_1p = res1.fun
        r_core = np.pi / (2 * alpha_1p) if alpha_1p > 0 else np.inf
    except Exception:
        alpha_1p, chi2_1p, r_core = np.nan, np.inf, np.nan
    
    # --- Qi 2-param: fit α and θ_cond ---
    def qi_chi2_2p(params):
        alpha, theta = params
        if alpha <= 0 or theta <= 0 or theta >= 0.99:
            return np.inf
        model = qi_vdm2(rad, vbar2, alpha, theta_cond=theta, n_cond=1.0)
        return np.sum((model - vdm2_obs)**2 / err**2)
    
    try:
        res2 = minimize(qi_chi2_2p, [alpha0, 0.45], method='Nelder-Mead',
                        options={'maxiter': 5000, 'xatol': 1e-6})
        alpha_2p, theta_2p = res2.x
        chi2_2p = res2.fun
    except Exception:
        alpha_2p, theta_2p, chi2_2p = np.nan, np.nan, np.inf
    
    # --- NFW 2-param ---
    def nfw_chi2(params):
        rs, log_rho0 = params
        x = rad / rs
        term = np.where(x < 1e-10, x/2, np.log(1 + x) - x/(1 + x))
        model = 4 * np.pi * G_kpc * 10**log_rho0 * rs**3 * term / rad
        return np.sum((model - vdm2_obs)**2 / err**2)
    
    try:
        res_nfw = minimize(nfw_chi2, [g['r_max']/3, 7.0],
                           method='Nelder-Mead',
                           options={'maxiter': 3000, 'xatol': 1e-6})
        rs_nfw, log_rho_nfw = res_nfw.x
        chi2_nfw = res_nfw.fun
    except Exception:
        rs_nfw, log_rho_nfw, chi2_nfw = np.nan, np.nan, np.inf
    
    n_data = g['n_points']
    
    # AIC comparison
    def aic(chi2, k):
        return n_data * np.log(max(chi2, 1e-10) / n_data) + 2 * k
    
    aic_qi_1p = aic(chi2_1p, 1) if np.isfinite(chi2_1p) else np.inf
    aic_qi_2p = aic(chi2_2p, 2) if np.isfinite(chi2_2p) else np.inf
    aic_nfw = aic(chi2_nfw, 2) if np.isfinite(chi2_nfw) else np.inf
    
    results.append({
        'name': name, 'M_bar': g['M_bar_final'], 'r_max': g['r_max'],
        'n_points': n_data,
        'alpha_1p': alpha_1p, 'r_core': r_core,
        'theta_2p': theta_2p,
        'chi2_qi_1p': chi2_1p, 'chi2_qi_2p': chi2_2p, 'chi2_nfw': chi2_nfw,
        'aic_qi_1p': aic_qi_1p, 'aic_qi_2p': aic_qi_2p, 'aic_nfw': aic_nfw,
    })

# Clean
results = [r for r in results 
           if np.isfinite(r['aic_nfw']) and np.isfinite(r['aic_qi_1p'])]

print(f"\nGalaxies with successful fits: {len(results)}")

# ============================================================
# MODEL COMPARISON
# ============================================================

# Qi 1-param (α only) vs NFW 2-param
delta_1p = np.array([r['aic_qi_1p'] - r['aic_nfw'] for r in results])
n_qi_better = sum(1 for d in delta_1p if d < -2)
n_nfw_better = sum(1 for d in delta_1p if d > 2)
n_indist = sum(1 for d in delta_1p if abs(d) <= 2)

print(f"\n=== Model Comparison ===")
print(f"Qi (1 param: α) vs NFW (2 params: r_s, ρ₀):")
print(f"  ξ = φ⁶ = {XI:.2f} (FIXED, not fitted)")
print(f"  θ_cond = 0.45 (FIXED, cosmological value)")
print(f"\n  Qi strongly preferred  (ΔAIC < −2): {n_qi_better}")
print(f"  NFW strongly preferred (ΔAIC > +2): {n_nfw_better}")
print(f"  Indistinguishable       (|ΔAIC| ≤ 2): {n_indist}")

print(f"\n  Median ΔAIC (Qi − NFW): {np.median(delta_1p):.1f}")
print(f"  Mean ΔAIC ± σ: {np.mean(delta_1p):.1f} ± {np.std(delta_1p):.1f}")

# Qi 2-param vs NFW 2-param
delta_2p = np.array([r['aic_qi_2p'] - r['aic_nfw'] for r in results])
n2_better = sum(1 for d in delta_2p if d < -2)
n2_worse = sum(1 for d in delta_2p if d > 2)
n2_indist = sum(1 for d in delta_2p if abs(d) <= 2)

print(f"\nQi (2 params: α, θ_cond) vs NFW (2 params: r_s, ρ₀):")
print(f"  Qi better: {n2_better}, NFW better: {n2_worse}, Indist: {n2_indist}")
print(f"  Median ΔAIC: {np.median(delta_2p):.1f}")

# ============================================================
# FITTED PARAMETERS
# ============================================================

# θ_cond from 2-param fits
theta_fits = np.array([r['theta_2p'] for r in results 
                       if np.isfinite(r['theta_2p']) and 0 < r['theta_2p'] < 1])
if len(theta_fits) > 0:
    print(f"\nFitted θ_cond (n={len(theta_fits)} galaxies):")
    print(f"  Range: {theta_fits.min():.3f} – {theta_fits.max():.3f}")
    print(f"  Median: {np.median(theta_fits):.3f}")
    print(f"  Mean ± σ: {theta_fits.mean():.3f} ± {theta_fits.std():.3f}")
    print(f"  Cosmological value: θ_cond = 0.45")
    sigma_theta = abs(np.median(theta_fits) - 0.45) / (theta_fits.std() / np.sqrt(len(theta_fits)))
    print(f"  Deviation from 0.45: {sigma_theta:.1f}σ")

# Core radius scaling
valid_cores = [(r['r_core'], r['M_bar']) 
               for r in results 
               if r['r_core'] > 0 and r['r_core'] < r['r_max']]

if len(valid_cores) >= 5:
    core_vals = np.array([c[0] for c in valid_cores])
    mass_vals = np.array([c[1] for c in valid_cores])
    
    slope, intercept, r_val, p_val, std_err = linregress(
        np.log10(mass_vals), np.log10(core_vals))
    
    print(f"\nCore radius scaling:")
    print(f"  r_core ∝ M_bar^γ")
    print(f"  γ = {slope:.4f} ± {std_err:.4f}  (Qi predicts 1/3 = 0.333)")
    print(f"  Deviation: {abs(slope - 1/3)/std_err:.2f}σ")
    print(f"  R² = {r_val**2:.4f}")
    print(f"  n = {len(valid_cores)}")

# ============================================================
# DETAIL ON BEST/WORST
# ============================================================
print(f"\n--- Best Qi 1-param fits ---")
for r in sorted(results, key=lambda x: x['aic_qi_1p'] - x['aic_nfw'])[:5]:
    print(f"  {r['name']:<20} ΔAIC={r['aic_qi_1p']-r['aic_nfw']:7.1f}  "
          f"r_core={r['r_core']:7.2f} kpc  M_bar={r['M_bar']:.1e}")

print(f"\n--- Worst Qi 1-param fits ---")
for r in sorted(results, key=lambda x: x['aic_nfw'] - x['aic_qi_1p'])[:5]:
    print(f"  {r['name']:<20} ΔAIC={r['aic_qi_1p']-r['aic_nfw']:7.1f}  "
          f"r_core={r['r_core']:7.2f} kpc  M_bar={r['M_bar']:.1e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Galaxies analyzed: {len(results)}")
print(f"Qi 1-param vs NFW 2-param: Qi better/indist in {n_qi_better+n_indist}/{len(results)}")
print(f"Core radius γ = {slope:.3f}±{std_err:.3f} vs predicted 0.333")
