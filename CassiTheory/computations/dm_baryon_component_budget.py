"""
Component-level mass budget for Omega_DM/Omega_b = phi^3 + 1
(cosmology/cosmology-from-phi.md sec 4.2; Fit-Status Ledger row 502).

Question: is the "+1" a distinct reservoir (baryons captured into the Qi
condensate), a double count of Omega_b, or a calibration artifact?

Reservoirs under the framework:
    Omega_b,total  = Omega_b,primordial   (BBN/CMB-pinned; ALL baryons,
                     bound or free -- the denominator of the observed ratio)
                   = Omega_b,free + Omega_b,captured
    Omega_Qi       = Omega_c              (non-baryonic condensate; the only
                     non-baryonic mass in the framework; the observed
                     numerator is baryon-free BY CONSTRUCTION:
                     Omega_c = Omega_m - Omega_b)
    Omega_DM,obs   = Omega_c               (no baryons in it)

Readings of the "+1" (captured baryons):
  R1 = Omega_Qi/Omega_b,total = phi^3                    (condensate only)
  R2 = (Omega_Qi + Omega_b,captured)/Omega_b,total = phi^3 + f_cap
       with f_cap = Omega_b,captured/Omega_b,total       (+1 as reservoir)
  R3 = (Omega_Qi + Omega_b,captured)/Omega_b,free = (phi^3 + f)/(1 - f)
       (renormalized denominator: captured baryons moved OUT of the
        denominator AND counted IN the numerator -- the same baryons twice)

Part A: exact identities and the observed ratio.
Part B: the f_cap arithmetic -- what each reading requires.
Part C: SPARC data-pinned cross-check (no hydrostatic fits; the fitted
        M_Y/M_bar medians are quoted from dm_baryon_ratio_verification.py
        part B, v9 machinery).
Part D: verdict.

External input (flagged, not framework-derived): the cosmic baryon census
fraction in collapsed structures, f_cap ~ 0.10-0.20 (stars ~5-7% + cold ISM
~1-2% + hot halo/ICM gas ~4-8% of Omega_b; e.g. Fukugita, Hogan & Peebles
1998, ApJ 503, 518; Shull, Smith & Danforth 2012, ApJ 759, 23).

Run from repo root:  python computations/dm_baryon_component_budget.py
"""
import numpy as np
import os, re, glob, math
import warnings
warnings.filterwarnings('ignore')

PHI = (1 + np.sqrt(5)) / 2
PHI3 = PHI**3
G_kpc = 4.302e-6   # (km/s)^2 kpc / M_sun

print("=" * 78)
print("PART A: IDENTITIES AND THE OBSERVED RATIO")
print("=" * 78)
print(f"  phi^3            = {PHI3:.6f}")
print(f"  phi^3 + 1        = {PHI3 + 1:.6f}   == 2 phi^2 = {2 * PHI**2:.6f} (exact algebra identity, not a derivation)")
print(f"  1/(1+phi^3)      = {1 / (1 + PHI3):.6f}   (baryon fraction the +1 partition implies at fixed DM/bar = phi^3)")
print(f"  1/phi^3          = {1 / PHI3:.6f}   (baryon fraction under phi^3-only partition)")
R_planck = 0.11933 / 0.02242          # Planck 2018 TT,TE,EE+lowE+lensing+BAO
R_repo = 0.264 / 0.049                # repo's rounded 0.264/0.049
print(f"  observed          = {R_repo:.4f} (repo 0.264/0.049); {R_planck:.4f} (Planck 2018 Omc h2/Om b h2)")
print(f"  phi^3 alone       vs observed: {PHI3 / R_repo - 1:+.1%}  ({PHI3 / R_planck - 1:+.1%} vs Planck)")
print(f"  phi^3 + 1         vs observed: {PHI3 / R_repo + 1 / R_repo - 1:+.1%}  (residual of the selected combination)")

print()
print("=" * 78)
print("PART B: COMPONENT BUDGET -- WHAT EACH READING REQUIRES")
print("=" * 78)
print("""
  Reservoirs (framework):
    Omega_b,total = Omega_b,primordial = Omega_b,free + Omega_b,captured
    Omega_Qi = Omega_c   (non-baryonic condensate; observed numerator)
    Omega_DM,obs = Omega_c   (baryon-free by construction: Omega_c = Omega_m - Omega_b)
""")

f_cap_lo, f_cap_hi = 0.10, 0.20   # external cosmic census bracket
print(f"  Cosmic census f_cap = Omega_b,captured/Omega_b,total in [{f_cap_lo:.2f}, {f_cap_hi:.2f}] (external census, flagged)")
print()
print(f"  Reading 1 -- condensate only:  R1 = phi^3 = {PHI3:.3f}  ->  {(PHI3 / R_repo - 1):+.1%} vs observed")
print()
print("  Reading 2 -- +1 as a capture reservoir:  R2(f) = phi^3 + f_cap")
for f in (0.0, f_cap_lo, 0.15, f_cap_hi, 1.0):
    print(f"    f_cap = {f:4.2f}:  R2 = {PHI3 + f:6.3f}   ({(PHI3 + f) / R_repo - 1:+.1%} vs 5.39)")
f_need = R_repo - PHI3
print(f"    f_cap required to match observed 5.39: {f_need:.3f}  ->  exceeds 1 (the whole baryon budget): "
      f"{'IMPOSSIBLE' if f_need > 1 else 'possible'}")
print(f"    the +1 itself implies f_cap = 1.00 (ALL baryons captured), 5-10x the census bracket "
      f"[{f_cap_lo:.2f}, {f_cap_hi:.2f}]")
print()
print("  Reading 3 -- renormalized denominator (captured baryons counted in BOTH numerator and denominator):")
print("    R3(f) = (phi^3 + f_cap)/(1 - f_cap)")
for f in (0.10, 0.15, 0.1803, 0.20):
    print(f"    f_cap = {f:5.3f}:  R3 = {(PHI3 + f) / (1 - f):6.3f}")
f3 = (R_repo - PHI3) / (R_repo + 1)
print(f"    f_cap solving R3(f) = 5.39: f = {f3:.4f}  (sits INSIDE the census bracket -- numerically interesting)")
print("""    BUT: R3 is not the observed quantity. The observed denominator is Omega_b,total
    (BBN/CMB), and the observed numerator Omega_c contains no baryons. R3 moves the
    SAME baryons from denominator to numerator (+f_cap in the numerator, -f_cap in the
    denominator) -- an accounting double count, not a new reservoir. It cannot be
    compared against Omega_c/Omega_b,total.
""")

print("=" * 78)
print("PART C: SPARC DATA-PINNED CROSS-CHECK (no fits; 175 rotmod files)")
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
    if cols.ndim == 1 or len(cols) < 8:
        return None
    rad = cols[:, 0]
    vobs = cols[:, 1]
    vgas = cols[:, 3] if cols.shape[1] > 3 else np.zeros_like(rad)
    vdisk = cols[:, 4] if cols.shape[1] > 4 else np.zeros_like(rad)
    vbul = cols[:, 5] if cols.shape[1] > 5 else np.zeros_like(rad)
    vbar2 = np.maximum(vgas**2 + vdisk**2 + vbul**2, 0.01)
    M_bar = rad * vbar2 / G_kpc
    M_tot = rad * vobs**2 / G_kpc
    return {'name': name, 'M_bar_max': M_bar[-1], 'M_tot_max': M_tot[-1],
            'vobs': vobs, 'vbar2': vbar2, 'r_max': rad[-1]}

rows = []
for fpath in files:
    g = parse_galaxy(fpath)
    if g and g['M_tot_max'] > g['M_bar_max'] > 0:
        rows.append(g)
print(f"  Parsed {len(rows)} galaxies (>=8 points, M_tot > M_bar at r_max)")

R = np.array([(r['M_tot_max'] - r['M_bar_max']) / r['M_bar_max'] for r in rows])
fb = np.array([r['M_bar_max'] / r['M_tot_max'] for r in rows])
vflat = np.array([np.sqrt(np.mean(r['vobs'][-max(3, int(0.25 * len(r['vobs']))):]**2)) for r in rows])
dwarfs = vflat < 100.0

print(f"  f_b = M_bar(r_max)/M_tot(r_max):   median {np.median(fb):.3f}  "
      f"(+1-implied 1/(1+phi^3) = {1/(1+PHI3):.3f}; cosmic 1/(1+5.39) = {1/(1+R_repo):.3f}; "
      f"phi^3-only 1/phi^3 = {1/PHI3:.3f})")
print(f"    dwarfs median {np.median(fb[dwarfs]):.3f};  high-V median {np.median(fb[~dwarfs]):.3f}")
print(f"  R_naive = M_DM/M_bar at r_max:     median {np.median(R):.2f} "
      f"(16-84% [{np.percentile(R, 16):.2f}, {np.percentile(R, 84):.2f}])")
for target, lab in [(PHI3, 'phi^3'), (PHI3 + 1, 'phi^3+1'), (R_repo, 'observed 5.39')]:
    frac = 100 * np.mean(np.abs(R - target) / target < 0.30)
    print(f"    R_naive within 30% of {lab:14s}: {frac:5.1f}% of galaxies; median R/target = {np.median(R)/target:.2f}")
print("""  NOTE: f_b here is the baryon fraction of the ENCLOSED MASS within the last
  measured radius (galaxy-local), not the cosmic capture fraction f_cap. It does
  not support the +1's implied partition (0.19); the condensate fits add the
  model-dependent part (M_Y/M_bar medians 0.14 envelope A / 0.35 envelope B,
  dm_baryon_ratio_verification.py part B, v9 machinery).
""")

print("=" * 78)
print("PART D: VERDICT")
print("=" * 78)
print("""
  1. The +1 is NOT a distinct reservoir. There is no mass source for it:
     captured baryons are drawn from Omega_b,primordial, which is BBN/CMB-pinned
     and already sits in the denominator. As a capture term it is a DOUBLE COUNT
     of Omega_b (baryons in both numerator and denominator relative to the
     observed Omega_c/Omega_b, whose numerator is baryon-free by construction).
  2. As a capture fraction the +1 fails quantitatively: it implies f_cap = 1.00
     (all baryons captured) against the external census f_cap ~ 0.10-0.20
     (5-10x off); even f_cap = 1 leaves a 2.8% residual, and matching the
     observed value would need f_cap = 1.15 > 1 (impossible).
  3. The renormalized-denominator form R3(f) = (phi^3 + f)/(1 - f) hits the
     observed value at f = 0.18 -- inside the census bracket -- but that is an
     accounting artifact (the same baryons counted twice), not a comparison
     against the observed quantity.
  4. The +1 remains an unvalidated CALIBRATION ARTIFACT and is excluded from
     the current prediction. The defensible base prediction is the derived
     Omega_DM/Omega_b = phi^3 = 4.2361, leaving a 21% residual against the
     observed 5.39 (open tension, not a match).
""")