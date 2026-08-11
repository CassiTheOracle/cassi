"""
Verification for cosmology/cosmology-from-phi.md sec 4.2: Omega_DM/Omega_b = phi^3 + 1.

Part A: rung arithmetic for the phi^3 base.
  - alpha_EM^-1 rungs (repo's own placements, foundations/dimensionful-constants-status.md)
  - xi = phi^6 (rung 6) and G_eff,max/G = phi^3 (rung 3) -- the condensate gravitational scale
  - spans; which reading gives exactly 3 rungs?

Part B: the +1 capture term against the SPARC hydrostatic condensate fits
  (experiments/sparc_qi/sparc_qi_analysis_v9.py machinery, models A: r_half envelope,
   B: Yang-fraction envelope). For each fitted galaxy:
    M_bar  = baryonic mass within last measured radius r_max      (from data)
    M_tot  = total mass within r_max implied by the rotation curve (data)
    M_DM   = M_tot - M_bar  (naive DM; what any DM model must match at r_max)
    R_naive = M_DM/M_bar
    f_b     = M_bar/M_tot  (bound-baryon fraction within r_max)
    M_Y    = fitted condensate mass within r_max (hydrostatic profile, self-gravity only)
    R_cond  = M_Y/M_bar
  Plus the data-only core radius (half-max v_DM radius) and its ratio to r_half.
  Checks: does the +1's implied partition (M_Y/M_bar = phi^3, f_b = 1/(1+phi^3) = 0.191)
  hold in the fits? Is R_naive consistent with phi^3+1 = 5.236 or the observed 5.39?

Run from repo root:  python computations/dm_baryon_ratio_verification.py
"""
import numpy as np
import os, re, glob, math
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
XI = PHI**6            # 17.944
G_kpc = 4.302e-6       # (km/s)^2 kpc / M_sun
BOOST = np.sqrt(2 * (1 + XI))

print("=" * 78)
print("PART A: RUNG ARITHMETIC FOR THE phi^3 BASE")
print("=" * 78)
lnp = math.log(PHI)
def rung(x):
    return math.log(x) / lnp

print("\nalpha_EM^-1 placements (foundations/dimensionful-constants-status.md):")
for label, val in [('alpha_em^-1 (0 momentum)', 137.036),
                   ('alpha_em^-1 (m_Z)',        128.95),
                   ('alpha_em^-1 (M_GUT)',      225.0)]:
    print(f"  {label:24s} n = {rung(val):8.3f}")
print(f"  xi = phi^6 (gravitational amplification)      n = {rung(PHI**6):8.3f} (exact 6)")
print(f"  G_eff,max/G = phi^3 (saturation ceiling)      n = {rung(PHI**3):8.3f} (exact 3)")
print(f"  sin^2 theta_W = phi^-3 = fixed-point imbalance n = {rung(PHI**-3):8.3f} (exact -3)")
print("\nSpans:")
print(f"  xi(6)  - alpha_em^-1(0 momentum, 10.225): {6 - rung(137.036):+7.3f} rungs  (NOT 3)")
print(f"  xi(6)  - alpha_em^-1(m_Z,      10.098): {6 - rung(128.95):+7.3f} rungs  (NOT 3)")
print(f"  xi(6)  - alpha_em^-1(M_GUT,    11.255): {6 - rung(225.0):+7.3f} rungs  (NOT 3)")
print(f"  xi(6)  - sin^2 theta_W (rung 3 in exponent catalog): {6-3:+7.1f} rungs  (EXACT)")
print(f"  => xi * sin^2 theta_W = phi^6 * phi^-3 = phi^3 = {PHI**3:.6f} exactly")
print(f"  => Omega_DM/Omega_b = phi^3 = alpha_0^-1 = G_eff,max/G (xi-derivation sec 2.3)")
print(f"  alpha_EM^-1 nearest integer rung: 10.225 -> 10 (frac +0.225); 128.95 -> 10.098; 225 -> 11.255")

print()
print("=" * 78)
print("PART B: SPARC HYDROSTATIC CONDENSATE FITS -- BOUND-BARYON FRACTION")
print("=" * 78)

data_dir = os.path.join('experiments', 'sparc_qi', 'sparc_data')
files = sorted(glob.glob(f'{data_dir}/*_rotmod.dat'))

def parse_galaxy(fpath):
    name = os.path.basename(fpath).replace('_rotmod.dat', '')
    dist = None
    with open(fpath, 'r') as f:
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
    vbar2 = np.maximum(vgas**2 + vdisk**2 + vbul**2, 0.01)
    vdm2_obs = np.maximum(vobs**2 - vbar2, 0.01)
    vdm_obs = np.sqrt(vdm2_obs)
    M_bar = rad * vbar2 / G_kpc
    M_bar_final = M_bar[-1]
    r_half = rad[np.searchsorted(M_bar, M_bar[-1] / 2.0)] if M_bar[-1] > 0 else rad[-1]
    r_half = float(np.clip(r_half, rad[0], rad[-1]))
    k = max(3, int(0.25 * len(rad)))
    v_flat = float(np.sqrt(np.mean(vobs[-k:]**2)))
    return {'name': name, 'dist': dist, 'rad': rad, 'vobs': vobs, 'errv': errv,
            'vbar2': vbar2, 'vdm_obs': vdm_obs, 'M_bar': M_bar,
            'M_bar_final': M_bar_final, 'r_max': rad[-1], 'n_points': len(rad),
            'r_half': r_half, 'v_flat': v_flat}

galaxies = {}
for fpath in files:
    g = parse_galaxy(fpath)
    if g and g['n_points'] >= 8:
        galaxies[g['name']] = g
print(f"Parsed {len(galaxies)} galaxies with >=8 points")

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

rows = []
for name, g in galaxies.items():
    rad = g['rad']
    r_half = g['r_half']
    r_max = g['r_max']
    vbar2 = g['vbar2']
    vdm_obs = g['vdm_obs']
    vdm2_obs = vdm_obs**2
    obs_err = np.maximum(g['errv'], 1.0)
    vdm2_err = 2 * vdm_obs * obs_err
    err = np.maximum(vdm2_err, np.median(vdm2_obs) * 0.1)
    r_min = max(2e-3, 0.02 * rad[0])
    r_grid = np.geomspace(r_min, r_max, 700)
    M_bar_rad = rad * vbar2 / G_kpc
    M_bar_max = M_bar_rad[-1]

    # ---- data-pinned quantities at r_max ----
    M_tot_max = g['vobs'][-1]**2 * r_max / G_kpc
    M_DM_max = max(M_tot_max - M_bar_max, 0.0)
    R_naive = M_DM_max / max(M_bar_max, 1e-6)
    f_b = M_bar_max / max(M_tot_max, 1e-6)

    # ---- data-only core radius (half-max v_DM, rising side) ----
    vdm = g['vdm_obs']
    core_r = np.nan
    if vdm.max() > 0:
        half = 0.5 * vdm.max()
        idx = np.where(vdm >= half)[0]
        if len(idx):
            i0 = max(0, idx[0] - 1)
            core_r = float(np.interp(half, [vdm[i0], vdm[idx[0]]], [rad[i0], rad[idx[0]]]))

    # ---- grid fit (v9 machinery), models A (r_half) and B (Yang-fraction) ----
    def fit2_self(rho_c_cand, cs_cand, q_kind):
        M_Y, _ = hydrostatic_grid(r_grid, rho_c_cand, cs_cand, lambda r: 0.0 * r)
        MY_at_rad = np.empty((len(rho_c_cand), len(rad)))
        for j in range(len(rho_c_cand)):
            MY_at_rad[j] = np.interp(rad, r_grid, M_Y[j])
        if q_kind == 'rhalf':
            q = rad / (rad + r_half)
        else:
            alpha = MY_at_rad / (M_bar_rad + MY_at_rad)
            q = alpha
        v2_model = G_kpc * (M_bar_rad + (1 + XI * q) * MY_at_rad) / rad
        v2_dm = np.maximum(v2_model - vbar2, 0)
        d = (v2_dm - vdm2_obs) / err
        return np.sum(d * d, axis=1)

    best = {}
    for q_kind in ('rhalf', 'alpha'):
        chi2_best = np.inf
        rho_b, cs_b = 10**6.5, 10**1.25
        for span_r, span_c, n_r, n_c in [(3.5, 0.65, 18, 12), (0.4, 0.15, 9, 7), (0.08, 0.04, 5, 5)]:
            rho_c = np.logspace(np.log10(rho_b) - span_r, np.log10(rho_b) + span_r, n_r)
            cs_c = np.logspace(np.log10(cs_b) - span_c, np.log10(cs_b) + span_c, n_c)
            cand_r = np.repeat(rho_c, len(cs_c))
            cand_c = np.tile(cs_c, len(rho_c))
            chi2_r = fit2_self(cand_r, cand_c, q_kind)
            bi = int(np.nanargmin(chi2_r))
            if chi2_r[bi] < chi2_best:
                chi2_best = chi2_r[bi]
                rho_b, cs_b = cand_r[bi], cand_c[bi]
        best[q_kind] = (chi2_best, rho_b, cs_b)

    out = {}
    for q_kind in ('rhalf', 'alpha'):
        chi2_b, rho_b, cs_b = best[q_kind]
        M_Yb, _ = hydrostatic_grid(r_grid, np.array([rho_b]), np.array([cs_b]),
                                   lambda r: 0.0 * r)
        MYb_at_rad = np.interp(rad, r_grid, M_Yb[0])
        if q_kind == 'rhalf':
            qb = rad / (rad + r_half)
        else:
            qb = MYb_at_rad / (M_bar_rad + MYb_at_rad)
        v2_modelb = G_kpc * (M_bar_rad + (1 + XI * qb) * MYb_at_rad) / rad
        v2_dm_b = np.maximum(v2_modelb - vbar2, 0)
        vdm_b_rmax = np.sqrt(v2_dm_b[-1])
        asympt = BOOST * cs_b
        out[q_kind] = {'chi2': chi2_b, 'rho_c': rho_b, 'c_s': cs_b,
                       'MY_rmax': float(MYb_at_rad[-1]),
                       'q_rmax': float(qb[-1]),
                       'vdm_rmax': float(vdm_b_rmax),
                       'asympt': float(asympt),
                       'constrained': bool(vdm_b_rmax > 0.85 * asympt)}
    rows.append({'name': name, 'v_flat': g['v_flat'], 'r_half': r_half, 'r_max': r_max,
                 'M_bar_max': M_bar_max, 'M_tot_max': M_tot_max, 'M_DM_max': M_DM_max,
                 'R_naive': R_naive, 'f_b': f_b, 'core_r': core_r,
                 'MY_A': out['rhalf']['MY_rmax'], 'q_A': out['rhalf']['q_rmax'],
                 'chi2_A': out['rhalf']['chi2'], 'con_A': out['rhalf']['constrained'],
                 'MY_B': out['alpha']['MY_rmax'], 'q_B': out['alpha']['q_rmax'],
                 'chi2_B': out['alpha']['chi2'], 'con_B': out['alpha']['constrained']})

rows = [r for r in rows if np.isfinite(r['chi2_A']) and np.isfinite(r['chi2_B'])]
print(f"Galaxies with successful fits: {len(rows)}")

def report(tag, rs):
    if len(rs) == 0:
        print(f"  {tag}: (none)")
        return
    R = np.array([r['R_naive'] for r in rs])
    fb = np.array([r['f_b'] for r in rs])
    # condensate-mass ratios: M_Y(r_max)/M_bar(r_max), per model
    rcA = np.array([r['MY_A'] / max(r['M_bar_max'], 1e-6) for r in rs])
    rcB = np.array([r['MY_B'] / max(r['M_bar_max'], 1e-6) for r in rs])
    cr = np.array([r['core_r'] for r in rs])
    rh = np.array([r['r_half'] for r in rs])
    qA = np.array([r['q_A'] for r in rs])
    qB = np.array([r['q_B'] for r in rs])
    print(f"\n=== {tag} (n={len(rs)}) ===")
    print(f"  R_naive = M_DM(r_max)/M_bar(r_max):   median {np.median(R):6.2f}, "
          f"16-84% [{np.percentile(R,16):.2f}, {np.percentile(R,84):.2f}]")
    print(f"  f_b = M_bar(r_max)/M_tot(r_max):      median {np.median(fb):6.3f}  "
          f"(+1 implied 1/(1+phi^3) = {1/(1+PHI**3):.3f}; cosmic 0.157; phi^3-only 1/phi^3 = {1/PHI**3:.3f})")
    print(f"  R_cond(A) = M_Y/M_bar (r_half env):   median {np.median(rcA):6.2f}, "
          f"16-84% [{np.percentile(rcA,16):.2f}, {np.percentile(rcA,84):.2f}]   (phi^3 = {PHI**3:.2f})")
    print(f"  R_cond(B) = M_Y/M_bar (Yang-frac env): median {np.median(rcB):6.2f}, "
          f"16-84% [{np.percentile(rcB,16):.2f}, {np.percentile(rcB,84):.2f}]   (phi^3 = {PHI**3:.2f})")
    print(f"  q(r_max) A / B:                       median {np.median(qA):.2f} / {np.median(qB):.2f}")
    ok = np.isfinite(cr) & (cr > 0)
    if ok.sum() >= 8:
        print(f"  r_core data (half-max v_DM):          median {np.median(cr[ok]):6.2f} kpc; "
              f"r_core/r_half median {np.median(cr[ok]/rh[ok]):.3f} (phi^-1 = {1/PHI:.3f}, phi = {PHI:.3f}); "
              f"r_core/r_max median {np.median(cr[ok]/np.array([r['r_max'] for r in rs])[ok]):.3f}")

report("ALL GALAXIES", rows)
report("DWARFS (V_flat < 100 km/s)", [r for r in rows if r['v_flat'] < 100.0])
report("HIGH-V (V_flat >= 100 km/s)", [r for r in rows if r['v_flat'] >= 100.0])
report("CONSTRAINED under A", [r for r in rows if r['con_A']])

# +1 support check: fraction of galaxies whose R_naive brackets phi^3+1 or 5.39
R = np.array([r['R_naive'] for r in rows])
for target, lab in [(PHI**3, 'phi^3 = 4.236'), (PHI**3 + 1, 'phi^3+1 = 5.236'), (5.39, 'observed 5.39')]:
    print(f"  R_naive within 30% of {lab}: {100*np.mean(np.abs(R-target)/target < 0.30):5.1f}% of galaxies; "
          f"median R_naive/target = {np.median(R)/target:.2f}")

# does the +1's implied partition (M_Y/M_bar = phi^3) appear anywhere?
rcB = np.array([r['MY_B'] / max(r['M_bar_max'], 1e-6) for r in rows])
print(f"\n  M_Y/M_bar(B) vs phi^3: median ratio {np.median(rcB)/PHI**3:.2f} -> the condensate's own mass "
      f"ratio is ~{np.median(rcB)/PHI**3:.2f}x the phi^3 partition at r_max")

# equivalent closed forms
print(f"\n  phi^3 + 1 = 2 phi^2 = {2*PHI**2:.6f} (arithmetic identity; not a derivation)")
