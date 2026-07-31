"""
SPARC Rotation Curve Analysis: Test Qi dark matter profile predictions.

Run: python sparc_qi_analysis.py

Tests:
  1. Core radius scaling: r_core ∝ M_bar^{1/3} (zero-parameter prediction)
  2. Qi modulation: vDM² / vbar² should show φ-structured modulation
  3. Model comparison: Qi profile vs NFW for individual galaxies
"""
import numpy as np
import os, re, glob
from scipy.optimize import curve_fit
from scipy.stats import linregress
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# Constants
# ============================================================
PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6  # ≈ 17.944
G_kpc = 4.302e-6  # kpc (km/s)^2 / Msun
ELL_PL = 1.616255e-35 / 3.086e19  # Planck length in kpc
THETA_COND = 0.45  # condensation threshold (cosmological value)

# ============================================================
# Data loading
# ============================================================
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sparc_data')
files = sorted(glob.glob(f'{data_dir}/*_rotmod.dat'))

def parse_galaxy(fpath):
    """Parse a single SPARC rotmod file."""
    name = os.path.basename(fpath).replace('_rotmod.dat', '')
    
    with open(fpath, 'r') as f:
        dist = None
        for l in f:
            if l.startswith('# Distance'):
                dist = float(re.search(r'[\d.]+', l).group())
                break
    
    if dist is None:
        return None
    
    try:
        cols = np.loadtxt(fpath, comments='#')
    except Exception:
        return None
    
    if cols.ndim == 1 or len(cols) < 4:
        return None
    
    rad = cols[:, 0]
    vobs = cols[:, 1]
    errv = cols[:, 2]
    vgas = cols[:, 3]
    vdisk = cols[:, 4]
    vbul = cols[:, 5] if cols.shape[1] > 5 else np.zeros_like(rad)
    
    # Baryonic velocity squared
    vbar2 = np.maximum(vgas**2 + vdisk**2 + vbul**2, 0.01)
    # Dark matter velocity squared
    vdm2 = np.maximum(vobs**2 - vbar2, 0.01)
    vdm = np.sqrt(vdm2)
    
    # Baryonic mass enclosed (from vbar2)
    r_max = rad[-1]
    vbar_max = np.sqrt(vbar2[-1])
    M_bar = r_max * vbar_max**2 / G_kpc
    
    return {
        'name': name, 'dist': dist, 'M_bar': M_bar,
        'rad': rad, 'vobs': vobs, 'errv': errv,
        'vbar2': vbar2, 'vdm2': vdm2, 'vdm': vdm,
        'r_max': r_max, 'n_points': len(rad)
    }

def extract_core_radius(rad, vdm):
    """Extract core radius: where vDM reaches half its maximum."""
    vdm_max = np.max(vdm)
    if vdm_max < 1:
        return None, None
    
    half_max = vdm_max / 2
    # Find first radius where vdm crosses half_max
    idx = np.argmax(vdm >= half_max)
    if idx == 0:
        return rad[idx], rad[idx]
    
    # Interpolate for accuracy
    if idx < len(rad) - 1:
        # Linear interpolation between idx-1 and idx
        r1, v1 = rad[idx-1], vdm[idx-1]
        r2, v2 = rad[idx], vdm[idx]
        r_half = r1 + (half_max - v1) * (r2 - r1) / (v2 - v1)
    else:
        r_half = rad[idx]
    
    return r_half, rad[idx]

# ============================================================
# QI PROFILE FUNCTIONS
# ============================================================

def qi_modulation(r, alpha, xi_eff=None):
    """Qi coherence modulation: q(r) = (1 + cos(αr))/2."""
    if xi_eff is None:
        xi_eff = XI
    return xi_eff * (1 + np.cos(alpha * r)) / 2

def vdm2_qi_model(r, vbar2, rad_full, alpha, xi_eff):
    """
    Qi dark matter velocity squared.
    Uses the approximation: vDM²(r) = ξ · q(r) · vbar²(r)
    
    For the full integral model:
    vDM²(r) = ξ · G/r · ∫₀^r q(r') · ρ_bar(r') · 4πr'² dr'
    
    Here we use the simpler approximation for first pass.
    """
    q_r = (1 + np.cos(alpha * r)) / 2
    return xi_eff * q_r * vbar2

# ============================================================
# MAIN ANALYSIS
# ============================================================
print("=" * 60)
print("SPARC Qi Analysis: Dark Matter as Unharvested Coherence")
print("=" * 60)

# Load all galaxies
print(f"\nLoading {len(files)} SPARC galaxies...")
galaxies = {}
for fpath in files:
    g = parse_galaxy(fpath)
    if g and g['n_points'] >= 4:
        galaxies[g['name']] = g

print(f"Parsed {len(galaxies)} galaxies")

# Filter to well-measured galaxies (at least 6 data points, resolved core)
good = {}
for name, g in galaxies.items():
    if g['n_points'] >= 6 and g['vdm'][-1] > 3:  # DM signal > 3 km/s
        good[name] = g

print(f"Well-measured galaxies (≥6 pts, DM > 3 km/s): {len(good)}")

# ============================================================
# TEST 1: Core radius scaling
# ============================================================
print("\n" + "-" * 40)
print("TEST 1: Core radius scaling (r_core ∝ M_bar^{1/3})")
print("-" * 40)

core_data = []
for name, g in good.items():
    r_core, r_idx = extract_core_radius(g['rad'], g['vdm'])
    if r_core is not None and r_core > 0 and r_core < g['r_max']:
        core_data.append({
            'name': name,
            'r_core': r_core,
            'M_bar': g['M_bar'],
            'r_max': g['r_max']
        })

print(f"Galaxies with measurable core: {len(core_data)}")

if len(core_data) >= 5:
    log_M = np.array([np.log10(d['M_bar']) for d in core_data])
    log_R = np.array([np.log10(d['r_core']) for d in core_data])
    
    # Linear fit
    slope, intercept, r_val, p_val, std_err = linregress(log_M, log_R)
    
    print(f"\nPower-law fit: r_core ∝ M_bar^γ")
    print(f"  γ = {slope:.4f} ± {std_err:.4f}")
    print(f"  R² = {r_val**2:.4f}, p = {p_val:.4f}")
    print(f"  Qi prediction: γ = 1/3 = 0.3333")
    print(f"  NFW prediction: γ ≈ 0.5 (for r_s ∝ M_vir^{1/3}, but M_vir ∝ M_bar is not 1:1)")
    
    sigma = abs(slope - 1/3) / std_err
    print(f"\n  Deviation from γ=1/3: {sigma:.2f}σ")
    
    if sigma < 2:
        print("  ✓ Consistent with Qi prediction at <2σ")
    elif sigma < 3:
        print("  ~ Marginally consistent (2-3σ)")
    else:
        print("  ✗ Deviates from Qi prediction")
    
    # Print individual galaxies
    print(f"\n  {'Name':<20} {'M_bar (Msun)':<16} {'r_core (kpc)':<14}")
    print("  " + "-" * 50)
    for d in sorted(core_data, key=lambda x: x['M_bar'])[:10]:
        print(f"  {d['name']:<20} {d['M_bar']:.2e}      {d['r_core']:.4f}")

# ============================================================
# TEST 2: Qi modulation in well-measured galaxy
# ============================================================
print("\n" + "-" * 40)
print("TEST 2: Qi modulation in individual galaxies")
print("-" * 40)

# Pick a galaxy with many data points
candidates = sorted(good.items(), key=lambda x: x[1]['n_points'], reverse=True)
for name, g in candidates[:4]:
    print(f"\n--- {name} (D={g['dist']:.1f} Mpc, {g['n_points']} pts) ---")
    
    rad = g['rad']
    vbar2 = g['vbar2']
    vdm2 = g['vdm2']
    
    # Ratio vDM² / vbar²
    ratio = vdm2 / vbar2
    ratio_err = g['errv'] * 2 * g['vobs'] / vbar2  # rough error estimate
    
    # Fit Qi modulation: ratio(r) = ξ × (1 + cos(αr)) / 2
    # Simple approach: find best-fit α
    def qi_ratio(r, alpha, xi_eff):
        return xi_eff * (1 + np.cos(alpha * r)) / 2
    
    try:
        # Initial guess: α ~ 2π / r_max (one cycle in the data range)
        popt, pcov = curve_fit(
            qi_ratio, rad, ratio,
            p0=[2*np.pi/g['r_max'], 1.0],
            sigma=ratio_err, absolute_sigma=True,
            maxfev=5000
        )
        alpha_fit, xi_fit = popt
        alpha_err, xi_err = np.sqrt(np.diag(pcov))
        
        r_core_qi = np.pi / (2 * alpha_fit)  # where cos = 0, q = 0.5
        
        print(f"  Best-fit α = {alpha_fit:.4f} ± {alpha_err:.4f} kpc⁻¹")
        print(f"  Core radius r_core = {r_core_qi:.4f} kpc")
        print(f"  Best-fit ξ = {xi_fit:.2f} ± {xi_err:.2f}")
        print(f"  Predicted ξ = φ⁶ = {XI:.2f}")
        
        xi_sigma = abs(xi_fit - XI) / xi_err
        print(f"  Deviation from φ⁶: {xi_sigma:.1f}σ")
        
    except Exception as e:
        print(f"  Fit failed: {e}")

# ============================================================
# TEST 3: Compare with NFW for one well-measured galaxy
# ============================================================
print("\n" + "-" * 40)
print("TEST 3: Model comparison (Qi vs NFW)")
print("-" * 40)

# NFW dark matter velocity
def vdm2_nfw_model(r, rs, rho0):
    """NFW profile: v² = 4πGρ₀r_s³ × [ln(1+r/r_s) - (r/r_s)/(1+r/r_s)] / r"""
    x = r / rs
    term = np.log(1 + x) - x / (1 + x)
    return 4 * np.pi * G_kpc * rho0 * rs**3 * term / r

# Qi model: vDM²(r) = ξ × (1+cos(αr))/2 × vbar²(r)
def vdm2_qi_simple(params, rad, vbar2):
    alpha, xi_eff = params
    q_r = (1 + np.cos(alpha * rad)) / 2
    return xi_eff * q_r * vbar2

# Pick the galaxy with most points
best_name, best_g = candidates[0]
rad = best_g['rad']
vdm2_obs = best_g['vdm2']
vbar2 = best_g['vbar2']

print(f"\nGalaxy: {best_name} ({best_g['n_points']} points, M_bar={best_g['M_bar']:.1e} Msun)")

# Fit Qi
try:
    from scipy.optimize import minimize
    
    def qi_chi2(params):
        model = vdm2_qi_simple(params, rad, vbar2)
        return np.sum((model - vdm2_obs)**2 / np.maximum(vdm2_obs, 1.0))
    
    res_qi = minimize(qi_chi2, [2*np.pi/best_g['r_max'], 1.0], 
                       method='Nelder-Mead')
    alpha_qi, xi_qi = res_qi.x
    chi2_qi = res_qi.fun
    n_par_qi = 2
    
    print(f"  Qi model: α = {alpha_qi:.4f}, ξ = {xi_qi:.2f}, χ² = {chi2_qi:.1f}")
    print(f"    r_core_Qi = {np.pi/(2*alpha_qi):.3f} kpc")
    
except Exception as e:
    print(f"  Qi fit error: {e}")
    chi2_qi, n_par_qi = None, 2

# Fit NFW
try:
    def nfw_chi2(params):
        rs, log_rho0 = params
        model = vdm2_nfw_model(rad, rs, 10**log_rho0)
        return np.sum((model - vdm2_obs)**2 / np.maximum(vdm2_obs, 1.0))
    
    res_nfw = minimize(nfw_chi2, [best_g['r_max']/3, 7.0], 
                        method='Nelder-Mead')
    rs_nfw, log_rho0_nfw = res_nfw.x
    chi2_nfw = res_nfw.fun
    n_par_nfw = 2
    
    print(f"  NFW model: r_s = {rs_nfw:.3f} kpc, log ρ₀ = {log_rho0_nfw:.2f}, χ² = {chi2_nfw:.1f}")
    
except Exception as e:
    print(f"  NFW fit error: {e}")
    chi2_nfw, n_par_nfw = None, 2

# Compare
if chi2_qi and chi2_nfw:
    n_data = best_g['n_points']
    
    # AIC
    aic_qi = n_data * np.log(chi2_qi / n_data) + 2 * n_par_qi
    aic_nfw = n_data * np.log(chi2_nfw / n_data) + 2 * n_par_nfw
    
    delta_aic = aic_qi - aic_nfw
    
    print(f"\n  AIC comparison:")
    print(f"    AIC(Qi)  = {aic_qi:.1f}")
    print(f"    AIC(NFW) = {aic_nfw:.1f}")
    print(f"    ΔAIC = Qi − NFW = {delta_aic:.1f}")
    
    if delta_aic < -2:
        print("    → Qi strongly preferred")
    elif delta_aic < 0:
        print("    → Qi slightly preferred")
    elif delta_aic < 2:
        print("    → Models indistinguishable")
    elif delta_aic < 6:
        print("    → NFW slightly preferred")
    else:
        print("    → NFW strongly preferred")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Galaxies analyzed: {len(good)}")
print(f"Core radius scaling: γ = {slope:.3f} ± {std_err:.3f} (Qi predicts 0.333)")
print(f"ξ fitted: {xi_fit:.1f} ± {xi_err:.1f} (Qi predicts φ⁶ = {XI:.1f})")
print(f"\nQi profile: 2 free parameters (α, ξ)")
print(f"NFW profile: 2 free parameters (r_s, ρ₀)")
print(f"Qi advantage: functional form is theoretically derived (cosine), not empirical")
