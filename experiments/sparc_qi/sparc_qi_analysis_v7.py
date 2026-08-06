"""
SPARC Qi Analysis v7: hydrostatic equilibrium condensate.

The Yang condensate is no longer a fitted profile—it is the hydrostatic
equilibrium of an isothermal field (P_Y = c_s^2 rho_Y) supported against
the total potential (baryons + its own mass), with ordinary Newtonian
self-gravity:

    dM_Y/dr = 4 pi r^2 rho_Y
    drho_Y/dr = - rho_Y * G * (M_bar(r) + M_Y) / (c_s^2 r^2)

The xi = phi^6 boost applies to the condensate's influence on baryons
(the rotation curve), modulated by the coherence envelope measured in v6:

    v^2(r) = G [ M_bar(r) + (1 + xi * q(r)) M_Y(r) ] / r,
    q(r) = r / (r + r_half)

The condensate's internal support is ordinary gravity + pressure: the
enhancement is the field's grip on ordinary matter, not its own
self-gravity, so solar-system GR tests (q -> 0, no condensate) are
untouched.

Variants:
  A: per-galaxy (rho_c, c_s)—2 params, same count as NFW
  B: global c_s shared by all galaxies—1 param per galaxy

Emergent quantities (not fitted):
  - core radius (half-max v_DM) and its mass scaling gamma
    vs empirical gamma = 0.41 +- 0.02
  - the rho_c x (1+xi) ~ naive DM density relation
  - the c_s vs galaxy mass relation (Tully-Fisher-type)
  - flatness (RMS fractional deviation over all data points)

Asymptotic anchor: for the isothermal sphere M_Y ~ (2 c_s^2/G) r, so
v_inf^2 = 2 (1 + xi) c_s^2  =>  c_s ~ v_flat / sqrt(2(1+xi)) = v_flat/6.15.
"""
import numpy as np
import os, re, glob
from scipy.stats import linregress
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6            # 17.944
G_kpc = 4.302e-6

# ============================================================
# DATA LOADING (v6 + baryonic half-mass radius)
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

    M_bar = rad * vbar2 / G_kpc
    r_half = rad[np.searchsorted(M_bar, M_bar[-1] / 2.0)] if M_bar[-1] > 0 else rad[-1]
    r_half = float(np.clip(r_half, rad[0], rad[-1]))

    return {
        'name': name, 'dist': dist, 'M_bar_final': M_bar_final,
        'rad': rad, 'vobs': vobs, 'errv': errv,
        'vbar2': vbar2, 'vdm2_obs': vdm2_obs, 'vdm_obs': vdm_obs,
        'r_max': rad[-1], 'n_points': len(rad), 'r_half': r_half,
        'M_bar': M_bar
    }

# ============================================================
# HYDROSTATIC INTEGRATOR (batched over candidate parameters)
# ============================================================
def hydrostatic_grid(r_grid, rho_c_vec, cs_vec, Mbar_fn):
    """RK4 integration of the hydrostatic isothermal condensate.

    Batched over K candidate (rho_c, c_s) pairs: rho, M are [K, n].
    Mbar_fn: callable r -> cumulative baryonic mass (scalar interp).
    Returns M_Y [K,n], rho_Y [K,n] (inf where blown up).
    """
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
        Mb0 = Mbar_fn(r0)
        Mbm = Mbar_fn(r0 + h2)
        Mb1 = Mbar_fn(r1)
        r2 = r0 * r0
        rmid = r0 + h2
        rmid2 = rmid * rmid
        r12 = r1 * r1
        # k1
        dM1 = 4 * np.pi * r2 * rho[:, i]
        dr1 = -rho[:, i] * G_kpc * (Mb0 + M[:, i]) / (cs2 * r2)
        rho_k = rho[:, i] + h2 * dr1
        M_k = M[:, i] + h2 * dM1
        # k2
        dM2 = 4 * np.pi * rmid2 * rho_k
        dr2 = -rho_k * G_kpc * (Mbm + M_k) / (cs2 * rmid2)
        rho_k = rho[:, i] + h2 * dr2
        M_k = M[:, i] + h2 * dM2
        # k3
        dM3 = 4 * np.pi * rmid2 * rho_k
        dr3 = -rho_k * G_kpc * (Mbm + M_k) / (cs2 * rmid2)
        rho_k = rho[:, i] + h * dr3
        M_k = M[:, i] + h * dM3
        # k4
        dM4 = 4 * np.pi * r12 * rho_k
        dr4 = -rho_k * G_kpc * (Mb1 + M_k) / (cs2 * r12)
        rho[:, i + 1] = rho[:, i] + (h / 6) * (dr1 + 2 * dr2 + 2 * dr3 + dr4)
        M[:, i + 1] = M[:, i] + (h / 6) * (dM1 + 2 * dM2 + 2 * dM3 + dM4)
        # blow-up guard: freeze dead candidates at inf
        bad = ~np.isfinite(rho[:, i + 1]) | ~np.isfinite(M[:, i + 1]) | (M[:, i + 1] > 1e15)
        if bad.any():
            rho[bad, i + 1:] = np.inf
            M[bad, i + 1:] = np.inf
            if bad.all():
                break
    return M, rho

def make_mbar_fn(rad, M_bar):
    """Cumulative baryonic mass interpolant (linear in log r below/above data)."""
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

# global c_s scan (variant B)
CS_GRID = np.logspace(0.6, 1.9, 14)   # 4 .. 79 km/s

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

    def fit_grid(rho_c_cand, cs_cand):
        """chi2 for all (rho_c, cs) candidates."""
        M_Y, _ = hydrostatic_grid(r_grid, rho_c_cand, cs_cand, mbar_fn)
        # interpolate M_Y at data radii
        MY_at_rad = np.empty((len(rho_c_cand), len(rad)))
        for j in range(len(rho_c_cand)):
            MY_at_rad[j] = np.interp(rad, r_grid, M_Y[j])
        q = rad / (rad + r_half)
        v2_model = G_kpc * (rad * vbar2 / G_kpc + (1 + XI * q) * MY_at_rad) / rad
        v2_dm = np.maximum(v2_model - vbar2, 0)
        d = (v2_dm - vdm2_obs) / err
        chi2 = np.sum(d * d, axis=1)
        return chi2, v2_dm

    # ---- variant A: 2-param grid fit + refinement ----
    rho_grid = np.logspace(3.5, 9.0, 17)
    chi2_A, v2_dm_A = fit_grid(np.repeat(rho_grid, len(CS_GRID)),
                               np.tile(CS_GRID, len(rho_grid)))
    best = int(np.nanargmin(chi2_A))
    best_rho, best_cs = rho_grid[best // len(CS_GRID)], CS_GRID[best % len(CS_GRID)]
    chi2_A_best = chi2_A[best]

    # ---- variant A2: self-gravity-only support, INDEPENDENT wide search ----
    def fit_grid_self(rho_c_cand, cs_cand):
        M_Y, _ = hydrostatic_grid(r_grid, rho_c_cand, cs_cand, lambda r: 0.0 * r)
        MY_at_rad = np.empty((len(rho_c_cand), len(rad)))
        for j in range(len(rho_c_cand)):
            MY_at_rad[j] = np.interp(rad, r_grid, M_Y[j])
        q = rad / (rad + r_half)
        v2_model = G_kpc * (rad * vbar2 / G_kpc + (1 + XI * q) * MY_at_rad) / rad
        v2_dm = np.maximum(v2_model - vbar2, 0)
        d = (v2_dm - vdm2_obs) / err
        return np.sum(d * d, axis=1)

    chi2_A2 = np.inf
    best_rho2, best_cs2 = 10**6.5, 10**1.25
    for span_r, span_c, n_r, n_c in [(3.5, 0.65, 18, 12), (0.4, 0.15, 9, 7), (0.08, 0.04, 5, 5)]:
        rho_c = np.logspace(np.log10(best_rho2) - span_r, np.log10(best_rho2) + span_r, n_r)
        cs_c = np.logspace(np.log10(best_cs2) - span_c, np.log10(best_cs2) + span_c, n_c)
        cand_r = np.repeat(rho_c, len(cs_c))
        cand_c = np.tile(cs_c, len(rho_c))
        chi2_r = fit_grid_self(cand_r, cand_c)
        best2 = int(np.nanargmin(chi2_r))
        if chi2_r[best2] < chi2_A2:
            chi2_A2 = chi2_r[best2]
            best_rho2, best_cs2 = cand_r[best2], cand_c[best2]
        else:
            best_rho2, best_cs2 = cand_r[best2], cand_c[best2]

    # best A2 curve at data radii (for gamma / RMS statistics)
    M_Y2, _ = hydrostatic_grid(r_grid, np.array([best_rho2]), np.array([best_cs2]),
                               lambda r: 0.0 * r)
    MY2_at_rad = np.interp(rad, r_grid, M_Y2[0])
    q2 = rad / (rad + r_half)
    v2_model2 = G_kpc * (rad * vbar2 / G_kpc + (1 + XI * q2) * MY2_at_rad) / rad
    v2_dm_A2 = np.maximum(v2_model2 - vbar2, 0)

    # refinement rounds (5x5, then 3x3)
    for span_r, span_c, n_r, n_c in [(0.12, 0.06, 5, 5), (0.03, 0.015, 3, 3)]:
        rho_c = np.logspace(np.log10(best_rho) - span_r, np.log10(best_rho) + span_r, n_r)
        cs_c = np.logspace(np.log10(best_cs) - span_c, np.log10(best_cs) + span_c, n_c)
        cand_r = np.repeat(rho_c, len(cs_c))
        cand_c = np.tile(cs_c, len(rho_c))
        chi2_r, v2_dm_r = fit_grid(cand_r, cand_c)
        best = int(np.nanargmin(chi2_r))
        best_rho, best_cs = cand_r[best], cand_c[best]
        chi2_A_best = chi2_r[best]
        if n_r * n_c == 25:
            v2_dm_A = v2_dm_r[best]

    # ---- variant B: global c_s scan, 1-param rho_c per galaxy ----
    chi2_B = {}
    for cs_g in CS_GRID:
        chi2_B[cs_g] = np.inf
        for span_r, n_r in [(0.5, 13), (0.12, 5), (0.03, 3)]:
            rho_c = np.logspace(np.log10(best_rho) - span_r, np.log10(best_rho) + span_r, n_r)
            chi2_r, _ = fit_grid(rho_c, np.full(n_r, cs_g))
            bi = int(np.nanargmin(chi2_r))
            if chi2_r[bi] < chi2_B[cs_g]:
                chi2_B[cs_g] = chi2_r[bi]
                best_rho_B = rho_c[bi]

    # ---- NFW (same as v4-v6) ----
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

    # model half-max v_DM radius: DATA convention (max over data range,
    # same as the empirical gamma = 0.41 +- 0.02 measurement); from A2
    r_halfmax = np.nan
    if np.isfinite(chi2_A2) and len(v2_dm_A2) == len(rad):
        vdm_model = np.sqrt(np.maximum(v2_dm_A2, 0))
        vmax = vdm_model.max()
        if vmax > 0:
            idx = np.argmax(vdm_model >= 0.5 * vmax)
            r_halfmax = rad[idx]

    # naive DM mass inside r_max and model condensate mass there (13x check)
    M_dm_naive = r_max * vdm2_obs[-1] / G_kpc
    M_Y_rmax = np.interp(r_max, r_grid, M_Y2[0]) if np.isfinite(chi2_A2) else np.nan

    # flatness: RMS fractional deviation over all data points (variant A2)
    rms = np.nan
    if np.isfinite(chi2_A2) and len(v2_dm_A2) == len(rad):
        rms = np.sqrt(np.mean(((np.sqrt(np.maximum(v2_dm_A2, 0)) - vdm_obs) / np.maximum(vdm_obs, 5))**2))

    results.append({
        'name': name, 'M_bar': g['M_bar_final'], 'r_max': r_max,
        'r_half': r_half, 'n_points': n_data,
        'rho_c': best_rho2, 'c_s': best_cs2,
        'chi2_A': chi2_A_best, 'chi2_A2': chi2_A2, 'chi2_nfw': chi2_nfw,
        'chi2_B': chi2_B, 'best_cs_B': min(chi2_B, key=chi2_B.get),
        'aic_A': aic(chi2_A_best, 2), 'aic_nfw': aic(chi2_nfw, 2),
        'aic_A2': aic(chi2_A2, 2),
        'aic_B': aic(chi2_B[min(chi2_B, key=chi2_B.get)], 1),
        'r_halfmax': r_halfmax, 'rms': rms,
        'M_dm_naive': M_dm_naive, 'M_Y_rmax': M_Y_rmax
    })

results = [r for r in results
           if np.isfinite(r['chi2_A']) and np.isfinite(r['chi2_nfw'])]
print(f"Galaxies with successful fits: {len(results)}")

# ============================================================
# 1. AIC vs NFW
# ============================================================
dA = np.array([r['aic_A'] - r['aic_nfw'] for r in results])
dB = np.array([r['aic_B'] - r['aic_nfw'] for r in results])
print(f"\n1. AIC vs NFW (2-param, same penalty):")
print(f"   A: hydrostatic per-galaxy (rho_c, c_s): median {np.median(dA):.1f}, "
      f"Qi<NFW: {sum(1 for x in dA if x < -2)}, "
      f"indist: {sum(1 for x in dA if abs(x) <= 2)}, "
      f"NFW<Qi: {sum(1 for x in dA if x > 2)}")
print(f"   B: global c_s, 1-param per galaxy: median {np.median(dB):.1f}, "
      f"Qi<NFW: {sum(1 for x in dB if x < -2)}")
dA2 = np.array([r['aic_A2'] - r['aic_nfw'] for r in results if np.isfinite(r['aic_A2'])])
print(f"   A2: self-gravity-only support: median {np.median(dA2):.1f}, "
      f"Qi<NFW: {sum(1 for x in dA2 if x < -2)}, "
      f"NFW<Qi: {sum(1 for x in dA2 if x > 2)}")

# ============================================================
# 2. FITTED c_s DISTRIBUTION + RELATION
# ============================================================
cs_arr = np.array([r['c_s'] for r in results])
mb_arr = np.array([r['M_bar'] for r in results])
print(f"\n2. Fitted sound speed (variant A):")
print(f"   Median c_s = {np.median(cs_arr):.1f} km/s, range {cs_arr.min():.1f}..{cs_arr.max():.1f} km/s")
slope_cs, _, r_cs, _, se_cs = linregress(np.log10(mb_arr), np.log10(cs_arr))
print(f"   c_s ~ M_bar^alpha: alpha = {slope_cs:.3f} +- {se_cs:.3f} (R^2 = {r_cs**2:.2f})")
print(f"   (Tully-Fisher expectation v_flat ~ M^0.25 -> alpha ~ 0.25)")

# ============================================================
# 3. CENTRAL DENSITY 13x RELATION
# ============================================================
rho_arr = np.array([r['rho_c'] for r in results])
print(f"\n3. Central density relation (local DM ~1e7 M_sun/kpc^3, log10 ~ 7.0):")
print(f"   Median log10 rho_c = {np.median(np.log10(rho_arr)):.2f}")
print(f"   Median log10 [rho_c x (1+xi)] = {np.median(np.log10(rho_arr * (1 + XI))):.2f}")

# ============================================================
# 3b. MASS RATIO CHECK (13x relation, integrated)
# ============================================================
rat = np.array([r['M_Y_rmax'] * (1 + XI) / r['M_dm_naive'] for r in results
                if np.isfinite(r['M_Y_rmax']) and r['M_dm_naive'] > 0])
print(f"\n3b. Integrated 13x relation: (1+xi)*M_Y(r_max) / M_DM_naive(r_max):")
print(f"   Median ratio = {np.median(rat):.2f} (1.0 would mean the boost exactly"
      f" replaces the naive dark matter)")

# ============================================================
# 4. EMERGENT CORE SCALING vs EMPIRICAL gamma = 0.41 +- 0.02
# ============================================================
valid = [(r['r_halfmax'], r['M_bar']) for r in results
         if np.isfinite(r['r_halfmax']) and r['r_halfmax'] > 0
         and r['r_halfmax'] < r['r_max'] * 1.1]
if len(valid) >= 5:
    cores = np.array([v[0] for v in valid])
    masses = np.array([v[1] for v in valid])
    slope, _, r_val, _, std_err = linregress(np.log10(masses), np.log10(cores))
    print(f"\n4. Emergent core scaling (half-max v_DM, hydrostatic model):")
    print(f"   r_core ~ M_bar^gamma: gamma = {slope:.3f} +- {std_err:.3f}, R^2 = {r_val**2:.3f}")
    print(f"   Empirical: 0.41 +- 0.02 (methodology band 0.31-0.41)")
    print(f"   Model vs empirical: {(slope - 0.41)/std_err:.1f} sigma")

# ============================================================
# 5. FLATNESS
# ============================================================
rms_arr = np.array([r['rms'] for r in results if np.isfinite(r['rms'])])
print(f"\n5. Flatness (RMS fractional deviation of v_DM model vs observed):")
print(f"   Median RMS = {np.median(rms_arr):.3f} ({100*np.median(rms_arr):.1f}%)")

print("\n" + "=" * 60)
print("CONCLUSIONS")
print("=" * 60)
print(f"1. Hydrostatic per-galaxy (A) vs NFW: median dAIC = {np.median(dA):.1f}")
print(f"2. Global c_s (B) vs NFW: median dAIC = {np.median(dB):.1f}")
print(f"3. c_s median = {np.median(cs_arr):.1f} km/s, alpha = {slope_cs:.3f} +- {se_cs:.3f}")
print(f"4. log10 [rho_c x (1+xi)] median = {np.median(np.log10(rho_arr * (1 + XI))):.2f}")
if len(valid) >= 5:
    print(f"5. Emergent gamma (data convention) = {slope:.3f} +- {std_err:.3f} "
          f"vs empirical 0.41 +- 0.02")
