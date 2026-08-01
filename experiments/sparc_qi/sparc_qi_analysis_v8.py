"""
SPARC Qi Analysis v8: physical origin of the c_s scatter.

The v7 per-galaxy fits give c_s with huge scatter (2.6-123 km/s) but no
mass trend. This script decomposes that scatter:

  1. Constrained galaxies: the rotation curve reaches the isothermal
     asymptote within the data (v_DM,model(r_max) > 0.85 * 6.15 * c_s).
     For these, c_s is pinned by the outer data and should equal the
     virial sound speed of the condensate:
         c_s = v_DM,flat / sqrt(2 (1 + xi)) = v_DM,flat / 6.15
  2. Unconstrained galaxies: the curve is still rising at r_max; c_s is
     bounded only from below (the bend must lie beyond the data) — the
     fitted value is a fit artifact, not physics.

Tests:
  A. Regression of log c_s vs log v_DM,flat (Vflat header, DM part):
     all galaxies vs constrained-only. Constrained slope ~ 1 with the
     ratio c_s / (v_DM,flat/6.15) ~ 1 => virial organization.
  B. Regression of log c_s vs log M_bar: constrained-only should recover
     the BTFR slope ~ 0.25 (v_flat ~ M^1/4) if the condensate virializes.
  C. Fixed-c_s refit: set c_s = v_DM,flat / 6.15 exactly (zero free
     EoS parameters) and fit only rho_c (1 param). Compare AIC vs the
     2-param v7 model and vs NFW.
  D. Residual scatter: for constrained galaxies, the ratio
     r_cs = c_s / (v_DM,flat/6.15) regressed against baryon fraction,
     Hubble type, and r_half — is the residual physical?
"""
import numpy as np
import os, re, glob
from scipy.stats import linregress
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6            # 17.944
G_kpc = 4.302e-6
BOOST = np.sqrt(2 * (1 + XI))   # 6.15: v_DM,flat / c_s

# ============================================================
# DATA LOADING (v7 + Vflat header)
# ============================================================
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sparc_data')
files = sorted(glob.glob(f'{data_dir}/*_rotmod.dat'))

def parse_galaxy(fpath):
    name = os.path.basename(fpath).replace('_rotmod.dat', '')
    dist = None
    with open(fpath, 'r') as f:
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

    M_bar = rad * vbar2 / G_kpc
    r_half = rad[np.searchsorted(M_bar, M_bar[-1] / 2.0)] if M_bar[-1] > 0 else rad[-1]
    r_half = float(np.clip(r_half, rad[0], rad[-1]))

    # flat-level estimators from the data (no Vflat header in these files):
    # median DM velocity over the outer 25% of points, baryon fraction there
    k = max(3, int(0.25 * len(rad)))
    vdm_flat = float(np.median(vdm_obs[-k:]))
    fb = float(np.mean(vbar2[-k:]) / np.mean(vobs[-k:]**2))

    return {
        'name': name, 'dist': dist, 'M_bar_final': M_bar_final,
        'rad': rad, 'vobs': vobs, 'errv': errv,
        'vbar2': vbar2, 'vdm2_obs': vdm2_obs, 'vdm_obs': vdm_obs,
        'r_max': rad[-1], 'n_points': len(rad), 'r_half': r_half,
        'M_bar': M_bar, 'vdm_flat': vdm_flat, 'fb': fb
    }

# ============================================================
# HYDROSTATIC INTEGRATOR (v7)
# ============================================================
def hydrostatic_grid(r_grid, rho_c_vec, cs_vec, Mbar_fn):
    n = len(r_grid)
    K = len(rho_c_vec)
    rho = np.empty((K, n))
    M = np.empty((K, n))
    rho[:, 0] = rho_c_vec
    M[:, 0] = 0.0
    cs2 = cs_vec**2
    for i in range(n - 1):
        r0, r1 = r_grid[i], r_grid[i + 1]
        h = r1 - r0
        h2 = h / 2
        Mb0 = Mbar_fn(r0); Mbm = Mbar_fn(r0 + h2); Mb1 = Mbar_fn(r1)
        r2 = r0 * r0
        rmid = r0 + h2; rmid2 = rmid * rmid
        r12 = r1 * r1
        dM1 = 4 * np.pi * r2 * rho[:, i]
        dr1 = -rho[:, i] * G_kpc * (Mb0 + M[:, i]) / (cs2 * r2)
        rho_k = rho[:, i] + h2 * dr1; M_k = M[:, i] + h2 * dM1
        dM2 = 4 * np.pi * rmid2 * rho_k
        dr2 = -rho_k * G_kpc * (Mbm + M_k) / (cs2 * rmid2)
        rho_k = rho[:, i] + h2 * dr2; M_k = M[:, i] + h2 * dM2
        dM3 = 4 * np.pi * rmid2 * rho_k
        dr3 = -rho_k * G_kpc * (Mbm + M_k) / (cs2 * rmid2)
        rho_k = rho[:, i] + h * dr3; M_k = M[:, i] + h * dM3
        dM4 = 4 * np.pi * r12 * rho_k
        dr4 = -rho_k * G_kpc * (Mb1 + M_k) / (cs2 * r12)
        rho[:, i + 1] = rho[:, i] + (h / 6) * (dr1 + 2 * dr2 + 2 * dr3 + dr4)
        M[:, i + 1] = M[:, i] + (h / 6) * (dM1 + 2 * dM2 + 2 * dM3 + dM4)
        bad = ~np.isfinite(rho[:, i + 1]) | ~np.isfinite(M[:, i + 1]) | (M[:, i + 1] > 1e15)
        if bad.any():
            rho[bad, i + 1:] = np.inf
            M[bad, i + 1:] = np.inf
            if bad.all():
                break
    return M, rho

def make_mbar_fn(rad, M_bar):
    logr = np.log(rad)
    Mb = M_bar
    def fn(r):
        x = np.log(np.asarray(r, dtype=float))
        return np.interp(x, logr, Mb, left=0.0, right=Mb[-1])
    return fn

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
    r_max = g['r_max']

    obs_err = np.maximum(g['errv'], 1.0)
    vdm2_err = 2 * vdm_obs * obs_err
    err = np.maximum(vdm2_err, np.median(vdm2_obs) * 0.1)

    r_min = max(2e-3, 0.02 * rad[0])
    r_grid = np.geomspace(r_min, r_max, 700)
    mbar_fn = make_mbar_fn(rad, g['M_bar'])

    def fit2_self(rho_c_cand, cs_cand):
        M_Y, _ = hydrostatic_grid(r_grid, rho_c_cand, cs_cand, lambda r: 0.0 * r)
        MY_at_rad = np.empty((len(rho_c_cand), len(rad)))
        for j in range(len(rho_c_cand)):
            MY_at_rad[j] = np.interp(rad, r_grid, M_Y[j])
        q = rad / (rad + r_half)
        v2_model = G_kpc * (rad * vbar2 / G_kpc + (1 + XI * q) * MY_at_rad) / rad
        v2_dm = np.maximum(v2_model - vbar2, 0)
        d = (v2_dm - vdm2_obs) / err
        return np.sum(d * d, axis=1), v2_dm

    # ---- A2 2-param fit (v7 machinery) ----
    chi2_A2 = np.inf
    best_rho2, best_cs2 = 10**6.5, 10**1.25
    for span_r, span_c, n_r, n_c in [(3.5, 0.65, 18, 12), (0.4, 0.15, 9, 7), (0.08, 0.04, 5, 5)]:
        rho_c = np.logspace(np.log10(best_rho2) - span_r, np.log10(best_rho2) + span_r, n_r)
        cs_c = np.logspace(np.log10(best_cs2) - span_c, np.log10(best_cs2) + span_c, n_c)
        cand_r = np.repeat(rho_c, len(cs_c))
        cand_c = np.tile(cs_c, len(rho_c))
        chi2_r, _ = fit2_self(cand_r, cand_c)
        best2 = int(np.nanargmin(chi2_r))
        if chi2_r[best2] < chi2_A2:
            chi2_A2 = chi2_r[best2]
            best_rho2, best_cs2 = cand_r[best2], cand_c[best2]
        else:
            best_rho2, best_cs2 = cand_r[best2], cand_c[best2]

    # best A2 curve + constrained flag
    M_Y2, _ = hydrostatic_grid(r_grid, np.array([best_rho2]), np.array([best_cs2]),
                               lambda r: 0.0 * r)
    MY2_at_rad = np.interp(rad, r_grid, M_Y2[0])
    q2 = rad / (rad + r_half)
    v2_model2 = G_kpc * (rad * vbar2 / G_kpc + (1 + XI * q2) * MY2_at_rad) / rad
    v2_dm_A2 = np.maximum(v2_model2 - vbar2, 0)
    vdm_A2_rmax = np.sqrt(v2_dm_A2[-1])
    asympt = BOOST * best_cs2
    constrained = vdm_A2_rmax > 0.85 * asympt

    # ---- fixed-c_s refit (c_s = v_DM,flat / BOOST, 1 param: rho_c) ----
    cs_fix = g['vdm_flat'] / BOOST
    chi2_C = np.inf
    best_rho_C = best_rho2
    for span_r, n_r in [(3.5, 18), (0.4, 9), (0.08, 5)]:
        rho_c = np.logspace(np.log10(best_rho_C) - span_r, np.log10(best_rho_C) + span_r, n_r)
        chi2_r, _ = fit2_self(rho_c, np.full(n_r, cs_fix))
        bi = int(np.nanargmin(chi2_r))
        if chi2_r[bi] < chi2_C:
            chi2_C = chi2_r[bi]
            best_rho_C = rho_c[bi]
        else:
            best_rho_C = rho_c[bi]

    # ---- NFW ----
    def vdm2_nfw(rad2, rs, rho0):
        x = rad2 / rs
        term = np.where(x < 1e-10, x/2, np.log(1 + x) - x/(1 + x))
        return 4 * np.pi * G_kpc * rho0 * rs**3 * term / rad2
    from scipy.optimize import minimize as _min
    def nfw_chi2(params):
        rs, log_rho0 = params
        model = vdm2_nfw(rad, rs, 10**log_rho0)
        return np.sum((model - vdm2_obs)**2 / err**2)
    try:
        res_nfw = _min(nfw_chi2, [g['r_max']/3, 7.0], method='Nelder-Mead',
                       options={'maxiter': 4000, 'xatol': 1e-7})
        rs_nfw, log_rho_nfw = res_nfw.x
        chi2_nfw = res_nfw.fun
    except Exception:
        rs_nfw, log_rho_nfw, chi2_nfw = np.nan, np.nan, np.inf

    n_data = g['n_points']
    aic = lambda c2, k: n_data * np.log(max(c2, 1e-10) / n_data) + 2 * k

    results.append({
        'name': name, 'M_bar': g['M_bar_final'], 'r_max': r_max,
        'r_half': r_half, 'n_points': n_data,
        'rho_c': best_rho2, 'c_s': best_cs2,
        'vdm_flat': g['vdm_flat'], 'fb': g['fb'], 'dist': g['dist'],
        'constrained': constrained, 'asympt': asympt, 'vdm_rmax': vdm_A2_rmax,
        'chi2_A2': chi2_A2, 'chi2_C': chi2_C, 'chi2_nfw': chi2_nfw,
        'aic_A2': aic(chi2_A2, 2), 'aic_C': aic(chi2_C, 1),
        'aic_nfw': aic(chi2_nfw, 2)
    })

results = [r for r in results
           if np.isfinite(r['chi2_A2']) and np.isfinite(r['chi2_nfw'])]
print(f"Galaxies with successful fits: {len(results)}")

con = [r for r in results if r['constrained']]
unc = [r for r in results if not r['constrained']]
print(f"\nConstrained (asymptote reached in data): {len(con)}/{len(results)}")
print(f"Unconstrained (still rising at r_max): {len(unc)}/{len(results)}")

# ============================================================
# A. c_s vs v_DM,flat
# ============================================================
def reg(x, y, label):
    slope, intercept, rv, pv, se = linregress(np.log10(x), np.log10(y))
    print(f"  {label}: slope = {slope:.3f} +- {se:.3f}, R^2 = {rv**2:.3f}, n = {len(x)}")
    return slope, se

print(f"\nA. log c_s vs log v_DM,flat:")
all_x = np.array([r['vdm_flat'] for r in results])
all_y = np.array([r['c_s'] for r in results])
reg(all_x, all_y, "ALL galaxies")
cx = np.array([r['vdm_flat'] for r in con])
cy = np.array([r['c_s'] for r in con])
s1, se1 = reg(cx, cy, "CONSTRAINED only")

ratio_all = all_y * BOOST / all_x
ratio_con = cy * BOOST / cx
print(f"  Ratio c_s*6.15/v_DM,flat (1.0 = virial):")
print(f"    ALL: median {np.median(ratio_all):.3f}, "
      f"scatter {np.std(np.log10(ratio_all)):.3f} dex")
print(f"    CONSTRAINED: median {np.median(ratio_con):.3f}, "
      f"scatter {np.std(np.log10(ratio_con)):.3f} dex")

# ============================================================
# B. c_s vs M_bar (BTFR slope)
# ============================================================
print(f"\nB. log c_s vs log M_bar (BTFR expectation ~0.25):")
mb_all = np.array([r['M_bar'] for r in results])
reg(mb_all, all_y, "ALL")
mb_con = np.array([r['M_bar'] for r in con])
sB, seB = reg(mb_con, cy, "CONSTRAINED only")

# ============================================================
# C. Fixed-c_s 1-param model vs 2-param and NFW
# ============================================================
dC2 = np.array([r['aic_C'] - r['aic_A2'] for r in results])
dCN = np.array([r['aic_C'] - r['aic_nfw'] for r in results])
dA2N = np.array([r['aic_A2'] - r['aic_nfw'] for r in results])
print(f"\nC. Fixed-c_s refit (c_s = v_DM,flat/6.15, 1 param rho_c):")
print(f"  Fixed vs 2-param: median dAIC = {np.median(dC2):.1f}")
print(f"  Fixed vs NFW: median dAIC = {np.median(dCN):.1f}, "
      f"Qi<NFW: {sum(1 for x in dCN if x < -2)}, "
      f"indist: {sum(1 for x in dCN if abs(x) <= 2)}, "
      f"NFW<Qi: {sum(1 for x in dCN if x > 2)}")
print(f"  (2-param vs NFW reference: {np.median(dA2N):.1f})")
con_C = np.array([r['aic_C'] - r['aic_nfw'] for r in con])
print(f"  Fixed vs NFW, CONSTRAINED only: median {np.median(con_C):.1f}")

# ============================================================
# D. Residual scatter correlations (constrained galaxies)
# ============================================================
print(f"\nD. Residual ratio r_cs = c_s/(v_DM,flat/6.15) vs galaxy properties:")
if len(con) >= 8:
    rc = cy * BOOST / cx
    fb_c = np.array([r['fb'] for r in con])
    rh_c = np.array([r['r_half'] for r in con])
    di_c = np.array([r['dist'] for r in con])
    vf_c = np.array([r['vdm_flat'] for r in con])
    np_c = np.array([r['n_points'] for r in con])
    for x, lab in [(fb_c, "baryon fraction (outer)"),
                   (rh_c, "r_half"),
                   (di_c, "distance"),
                   (vf_c, "v_DM,flat"),
                   (np_c, "n_points")]:
        slope, intercept, rv, pv, se = linregress(x, np.log10(rc))
        print(f"  log r_cs vs {lab}: slope = {slope:.3f} +- {se:.3f}, "
              f"R^2 = {rv**2:.3f} (p = {pv:.3f})")

print("\n" + "=" * 60)
print("CONCLUSIONS")
print("=" * 60)
print(f"1. Constrained fraction: {len(con)}/{len(results)}")
print(f"2. c_s-v_DM,flat slope (constrained): {s1:.3f} +- {se1:.3f}, "
      f"ratio median {np.median(ratio_con):.3f}")
print(f"3. c_s-M_bar slope (constrained): {sB:.3f} +- {seB:.3f} (BTFR ~0.25)")
print(f"4. Fixed-c_s vs NFW: median dAIC = {np.median(dCN):.1f}; "
      f"vs 2-param: {np.median(dC2):.1f}")
