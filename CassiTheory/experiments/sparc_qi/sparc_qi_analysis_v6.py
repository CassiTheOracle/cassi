"""
SPARC Qi Analysis v6: coherence-budget envelope.

The v5 uniform boost (1 + xi) works, but the framework's coherence budget
says q is not uniform: baryonic activity (star formation, bars, spiral
shocks) destroys coherence, and the de-resonance attractor rebuilds it on
the scale of the baryonic distribution. The boost therefore recovers
outside the baryonic scale:

    q(r) = r / (r + r_q),   r_q = r_half (baryonic half-mass radius)

with the condensate's own mass staying pseudo-isothermal:

    M_Qi(r) = M_bar(r) + (1 + xi * q(r)) * M_Y(r),
    M_Y(r)  = 4 pi rho_c r_c^2 [r - r_c atan(r/r_c)]

Three variants:
  A: r_q = r_half fixed from data        (2 params: rho_c, r_c)
  B: r_q = a * r_half, a free            (3 params)
  C: uniform boost q = 1 (v5 model)      (2 params, in-script baseline)

Questions this run answers:
  1. Does the coherence envelope (A) fit SPARC as well as the uniform
     boost with the same parameter count—but with the core coming from
     physics instead of the profile?
  2. Does the optimal scale a in variant B land at ~1, confirming that
     baryonic activity sets the decoherence scale?
  3. Does the model's half-max v_DM radius scale as M_bar^gamma with
     gamma ~ 0.41, matching the empirical core-radius scaling? If
     gamma_model ~ gamma_size (the size-mass slope), the coherence budget
     explains the core scaling as a baryonic-size effect rather than the
     constant-density 1/3.
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
# DATA LOADING (v5 + baryonic half-mass radius)
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

    # baryonic half-mass radius: M_bar(r_half) = M_bar(r_max)/2
    M_bar = rad * vbar2 / G_kpc
    r_half = rad[np.searchsorted(M_bar, M_bar[-1] / 2.0)] if M_bar[-1] > 0 else rad[-1]
    r_half = float(np.clip(r_half, rad[0], rad[-1]))

    return {
        'name': name, 'dist': dist, 'M_bar_final': M_bar_final,
        'rad': rad, 'vobs': vobs, 'errv': errv,
        'vbar2': vbar2, 'vdm2_obs': vdm2_obs, 'vdm_obs': vdm_obs,
        'r_max': rad[-1], 'n_points': len(rad), 'r_half': r_half
    }

# ============================================================
# QI MODELS
# ============================================================
def qi_vdm2(rad, vbar2, rho_c, r_c, q_func):
    """v2_DM for the two-component condensate with boost envelope q(r)."""
    r = rad
    M_Y = 4 * np.pi * rho_c * r_c**2 * (r - r_c * np.arctan(r / r_c))
    M_Qi = r * vbar2 / G_kpc + (1 + XI * q_func(r)) * M_Y
    v2 = G_kpc * M_Qi / r
    return np.maximum(v2 - vbar2, 0)

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
    r_half = g['r_half']

    obs_err = np.maximum(g['errv'], 1.0)
    vdm2_err = 2 * vdm_obs * obs_err
    err = np.maximum(vdm2_err, np.median(vdm2_obs) * 0.1)

    def fit2(q_func):
        def chi2(params):
            log_rho_c, log_r_c = params
            rho_c, r_c = 10**log_rho_c, 10**log_r_c
            if r_c < 1e-4 * rad[-1]: return np.inf
            model = qi_vdm2(rad, vbar2, rho_c, r_c, q_func)
            return np.sum((model - vdm2_obs)**2 / err**2)
        best_c, best_p = np.inf, None
        for start in [(7.0, np.log10(g['r_max']/3.0)),
                      (7.0, np.log10(g['r_max']/10.0))]:
            try:
                res = minimize(chi2, start, method='Nelder-Mead',
                               options={'maxiter': 4000, 'xatol': 1e-7})
                if res.fun < best_c:
                    best_c, best_p = res.fun, res.x
            except Exception:
                pass
        return best_c, best_p

    def fit3():
        def chi2(params):
            log_rho_c, log_r_c, log_a = params
            rho_c, r_c, a = 10**log_rho_c, 10**log_r_c, 10**log_a
            if r_c < 1e-4 * rad[-1]: return np.inf
            q = lambda r: r / (r + a * r_half)
            model = qi_vdm2(rad, vbar2, rho_c, r_c, q)
            return np.sum((model - vdm2_obs)**2 / err**2)
        best_c, best_p = np.inf, None
        for start in [(7.0, np.log10(g['r_max']/3.0), 0.0),
                      (7.0, np.log10(g['r_max']/10.0), 0.3)]:
            try:
                res = minimize(chi2, start, method='Nelder-Mead',
                               options={'maxiter': 5000, 'xatol': 1e-7})
                if res.fun < best_c:
                    best_c, best_p = res.fun, res.x
            except Exception:
                pass
        return best_c, best_p

    # Variant A: r_q = r_half fixed (2 params)
    qA = lambda r: r / (r + r_half)
    chi2_A, pA = fit2(qA)

    # Variant B: r_q = a * r_half free (3 params)
    chi2_B, pB = fit3()

    # Variant C: uniform boost q = 1, v5 model (2 params)
    chi2_C, pC = fit2(lambda r: np.ones_like(r))

    # NFW (2 params)
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

    n_data = g['n_points']
    aic = lambda c2, k: n_data * np.log(max(c2, 1e-10) / n_data) + 2 * k

    # Model half-max v_DM radius for variant A (evaluate on fine grid)
    r_halfmax_A = np.nan
    if pA is not None:
        rho_c, r_c = 10**pA[0], 10**pA[1]
        grid = np.linspace(rad[0], 3 * rad[-1], 2000)
        vDM_grid = np.sqrt(qi_vdm2(grid, np.zeros_like(grid), rho_c, r_c, qA))
        # v_DM from the condensate alone (subtract vbar on data grid only)
        vDM_full = np.sqrt(qi_vdm2(grid, np.zeros_like(grid), rho_c, r_c, qA))
        vmax = vDM_full.max()
        if vmax > 0:
            idx = np.argmax(vDM_full >= 0.5 * vmax)
            r_halfmax_A = grid[idx]

    results.append({
        'name': name, 'M_bar': g['M_bar_final'], 'r_max': g['r_max'],
        'r_half': r_half, 'n_points': n_data,
        'chi2_A': chi2_A, 'chi2_B': chi2_B, 'chi2_C': chi2_C,
        'chi2_nfw': chi2_nfw,
        'a_fit': 10**pB[2] if pB is not None else np.nan,
        'aic_A': aic(chi2_A, 2), 'aic_B': aic(chi2_B, 3),
        'aic_C': aic(chi2_C, 2), 'aic_nfw': aic(chi2_nfw, 2),
        'r_halfmax_A': r_halfmax_A
    })

results = [r for r in results
           if np.isfinite(r['chi2_A']) and np.isfinite(r['chi2_nfw'])]
print(f"Galaxies with successful fits: {len(results)}")

def report(label, key, nfw=True):
    d = np.array([(r[key] - r['aic_nfw']) if nfw else r[key] for r in results])
    print(f"{label}:")
    print(f"  Median dAIC: {np.median(d):.1f}")

# ============================================================
# 1. AIC COMPARISONS
# ============================================================
print(f"\n1. AIC vs NFW (2-param, same penalty):")
for label, key in [("A: coherence envelope (r_q = r_half)", 'aic_A'),
                   ("C: uniform boost (v5 model)", 'aic_C')]:
    d = np.array([r[key] - r['aic_nfw'] for r in results])
    print(f"  {label}: median {np.median(d):.1f}, "
          f"Qi<NFW: {sum(1 for x in d if x < -2)}, "
          f"indist: {sum(1 for x in d if abs(x) <= 2)}, "
          f"NFW<Qi: {sum(1 for x in d if x > 2)}")
d = np.array([r['aic_B'] - r['aic_nfw'] for r in results])
print(f"  B: coherence envelope, a free (3-param): median {np.median(d):.1f}, "
      f"Qi<NFW: {sum(1 for x in d if x < -2)}")

# A vs C directly (same params, envelope vs uniform)
d_ac = np.array([r['aic_A'] - r['aic_C'] for r in results])
print(f"\n2. Envelope (A) vs uniform boost (C), same 2 params:")
print(f"  Median dAIC = {np.median(d_ac):.1f} "
      f"({'envelope better' if np.median(d_ac) < 0 else 'uniform better'})")
print(f"  Envelope better (<-2): {sum(1 for x in d_ac if x < -2)}, "
      f"indist: {sum(1 for x in d_ac if abs(x) <= 2)}, "
      f"uniform better (>+2): {sum(1 for x in d_ac if x > 2)}")

# ============================================================
# 3. FITTED DECOHERENCE SCALE (variant B)
# ============================================================
a_arr = np.array([r['a_fit'] for r in results if np.isfinite(r['a_fit'])])
print(f"\n3. Optimal decoherence scale a (r_q = a * r_half):")
print(f"  Median a = {np.median(a_arr):.3f}")
print(f"  Fraction with 0.3 < a < 3: {sum(1 for x in a_arr if 0.3 < x < 3)/len(a_arr):.2f}")

# ============================================================
# 4. CORE RADIUS SCALING: model vs empirical gamma = 0.41 +- 0.02
# ============================================================
valid = [(r['r_halfmax_A'], r['M_bar']) for r in results
         if np.isfinite(r['r_halfmax_A']) and r['r_halfmax_A'] > 0
         and r['r_halfmax_A'] < r['r_max'] * 1.1]
if len(valid) >= 5:
    cores = np.array([v[0] for v in valid])
    masses = np.array([v[1] for v in valid])
    slope, intercept, r_val, p_val, std_err = linregress(
        np.log10(masses), np.log10(cores))
    print(f"\n4. Model core scaling (half-max v_DM, variant A):")
    print(f"  r_core ~ M_bar^gamma, gamma = {slope:.3f} +- {std_err:.3f}, R^2 = {r_val**2:.3f}")
    print(f"  Empirical: 0.41 +- 0.02  |  constant-density: 1/3")
    print(f"  Model vs empirical: {(slope - 0.41)/std_err:.1f} sigma")

# size-mass relation: r_half vs M_bar
valid2 = [(r['r_half'], r['M_bar']) for r in results if r['r_half'] > 0]
if len(valid2) >= 5:
    rh = np.array([v[0] for v in valid2]); mb = np.array([v[1] for v in valid2])
    slope2, _, r2, _, se2 = linregress(np.log10(mb), np.log10(rh))
    print(f"  Size-mass: r_half ~ M_bar^{slope2:.3f} +- {se2:.3f} (R^2 = {r2**2:.2f})")
    print(f"  -> gamma_model ~ gamma_size: core as baryonic-size effect "
          f"({abs(slope - slope2)/np.hypot(std_err, se2):.1f} sigma apart)")

# ============================================================
# 5. SMALL-r SLOPE (cusp-vs-core binary)
# ============================================================
print(f"\n5. Small-r slope test (v_DM ~ r^p, p=0.5 cusp vs p=1.0 core):")
slope_results = []
for r in results:
    g = galaxies.get(r['name'])
    if g is None: continue
    # use the model's half-max radius as the core scale for the mask
    r_core_m = r['r_halfmax_A']
    if not np.isfinite(r_core_m): continue
    mask = g['rad'] < r_core_m
    if mask.sum() < 3: continue
    vdm_inner = g['vdm_obs'][mask]
    pos = vdm_inner > 0
    if pos.sum() < 3: continue
    coeffs = np.polyfit(np.log10(g['rad'][mask][pos]),
                        np.log10(vdm_inner[pos]), 1)
    slope_results.append(coeffs[0])
if slope_results:
    p_arr = np.array(slope_results)
    print(f"  n = {len(p_arr)} galaxies, median p = {np.median(p_arr):.3f}")
    closer_core = sum(1 for p in p_arr if abs(p-1.0) < abs(p-0.5))
    print(f"  Closer to core (p=1.0): {closer_core}/{len(p_arr)}")

print("\n" + "=" * 60)
print("CONCLUSIONS")
print("=" * 60)
print(f"1. Coherence envelope (A) vs NFW: median dAIC = "
      f"{np.median(np.array([r['aic_A']-r['aic_nfw'] for r in results])):.1f}")
print(f"2. Envelope vs uniform boost: median dAIC = {np.median(d_ac):.1f}")
print(f"3. Optimal a = {np.median(a_arr):.3f}")
if len(valid) >= 5:
    print(f"4. Model gamma = {slope:.3f} +- {std_err:.3f} vs empirical 0.41 +- 0.02")
