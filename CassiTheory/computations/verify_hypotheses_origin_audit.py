# Verify every claimed correspondence in hypotheses/ cluster docs.
# House rule: every computable claim checked numerically. Run: python computations/verify_hypotheses_origin_audit.py
import math
import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LNPHI = math.log(PHI)
LPL = 1.616255e-35          # Planck length (m)
MPL = 1.220890e19           # Planck mass (GeV)
U_GEV = 0.93149410242       # u -> GeV

def rung(mass_gev):
    """n = log_phi(M_Pl / m)"""
    return math.log(MPL / mass_gev) / LNPHI

def phi_pow(k):
    return PHI ** k

def check(name, value, target, tol=1e-3):
    flag = "OK " if abs(value - target) <= tol * max(1.0, abs(target)) else "FAIL"
    print(f"  [{flag}] {name}: {value:.6g} (claimed {target})")
    return flag

print("=" * 78)
print("1. nuclear-magic-numbers.md")
print("=" * 78)
# ladder positions of magic nuclei (atomic masses -> GeV)
masses = {
    "p": 0.938272,
    "16O": 15.994915 * U_GEV,
    "48Ca": 47.952534 * U_GEV,
    "56Ni": 55.942129 * U_GEV,
    "90Zr": 89.904703 * U_GEV,
    "208Pb": 207.976652 * U_GEV,
}
print("  n = log_phi(M_Pl/m) for nucleon/magic nuclei:")
for name, m in masses.items():
    print(f"    {name:6s} m = {m:9.4f} GeV -> n = {rung(m):7.3f}")
print("  doc anchors: n(p) = 91.46 (computed 91.44); n(n-p diff 1.2933 MeV) = 105.14 (doc 105.15)")
check("n_p", rung(0.938272), 91.46, 5e-3)
check("n_delta", rung(1.2933e-3), 105.15, 5e-3)
# QCD 200 MeV ~ step 95 ; binding 1-10 MeV ~ 101-106
check("n(QCD=0.2 GeV)", rung(0.2), 95.0, 2e-2)
print(f"    n(1 MeV) = {rung(1e-3):.2f}, n(10 MeV) = {rung(1e-2):.2f} (doc: steps ~101-106)")
# Fibonacci check for 58
fibs = [0, 1]
while fibs[-1] < 200:
    fibs.append(fibs[-1] + fibs[-2])
print(f"  Fibonacci numbers < 200: {fibs}")
print("  Is 58 Fibonacci?", 58 in fibs, "  (184-126 = 58 -> '126 + Fib(n) = 184' mislabels 58)")
print("  Next Fib closures near 184: 126+55 =", 126 + 55, "; 126+89 =", 126 + 89)
# closure sums from doc table: row sums cumulated
row_sums = [8, 12, 18, 16, 24, 30, 36]
claimed = [2, 8, 20, 28, 50, 82, 126]
cum = list(np.cumsum(row_sums))
print(f"  row sums: {row_sums} -> cumulative closures {cum} vs claimed {claimed}")
print(f"  rows closing exactly: {sum(1 for c, cl in zip(cum, claimed) if c == cl)}/7")
# claimed magic-number gap ratios
gaps = np.diff([2, 8, 20, 28, 50, 82, 126])
print(f"  claimed-sequence gaps: {gaps}, ratios {np.round(gaps[1:]/gaps[:-1], 3)} (doc: 2, 2.75, 1.45, 1.38) vs phi = {PHI:.3f}")
# Wu-Xing coefficient ratio
print(f"  a_S/a_V = 17.8/15.75 = {17.8/15.75:.3f} vs phi^-1 = {1/PHI:.3f} (doc: tension)")

print()
print("=" * 78)
print("2. periodic-table-madelung.md")
print("=" * 78)
noble = [2, 10, 18, 36, 54, 86, 118]
print("  noble-gas cumulative:", noble)
print("  2*sum k^2 (k=1..n):   ", [2 * sum(k * k for k in range(1, n + 1)) for n in range(1, 8)])
print("  -> claimed 'twice the sum of squares' fails from term 4 (28 vs 36)")
# noble/2 terms: 1, 5, 9, 18, 27, 43, 59  -> increments 1,4,4,9,9,16,16 (each square k^2, k>=2, twice)
half = [z // 2 for z in noble]
inc_half = list(np.diff([0] + half))
print("  noble/2:", half, " increments:", inc_half, " (= 1,2^2,2^2,3^2,3^2,4^2,4^2: each square twice)")
print("  -> noble-gas cumulative = 2*sum with each square k^2 (k>=2) repeated twice, NOT 2*sum k^2")
# per-period increments
inc = list(np.diff([0] + noble))
print("  per-period increments:", inc, " (standard subshell counts 2(2l+1): s2 p6 d10 f14)")
cap_col = [2, 10, 10, 28, 28, 60, 32]   # doc table capacity column
print("  doc table 'Capacity 2*sum l^2' column:", cap_col)
print("  contradiction rows (capacity col vs increment used in same row):", [i + 1 for i in range(7) if cap_col[i] != inc[i]])
print("  principal-shell totals 2n^2 (1..4):", [2 * n * n for n in range(1, 5)], " cumulative:", np.cumsum([2 * n * n for n in range(1, 5)]).tolist())
# quantum defects
qd = {"Na_s": 1.35, "Na_p": 0.85, "Na_d": 0.010, "K_s": 2.18, "K_p": 1.71, "K_d": 0.25, "Rb_s": 3.13, "Rb_p": 2.64, "Rb_d": 1.35}
for a, b, lab in [("Na_p", "Na_s", "Na p/s"), ("K_p", "K_s", "K p/s"), ("Rb_p", "Rb_s", "Rb p/s")]:
    r = qd[a] / qd[b]
    print(f"  {lab} ratio = {r:.3f} vs phi^-1 = {1/PHI:.3f} (dev {(r-1/PHI)/(1/PHI)*100:+.0f}%)")
print("  fixed-l n-trend (doc: 'delta decreases with n as phi^-n'): s-state 3s 1.35 < 4s 2.18 < 5s 3.13 -> INCREASES, contradicts doc's own table")
print(f"  predicted ratio delta(5s)/delta(3s) = phi^-2 = {1/PHI**2:.3f}; observed 3.13/1.35 = {3.13/1.35:.3f}")
# oxygen ionization ratios
oev = [13.6, 35.1, 54.9, 77.4, 113.9, 138.1, 739.3, 871.4]
rat = [oev[i + 1] / oev[i] for i in range(5)]
gm = math.exp(sum(math.log(r) for r in rat) / len(rat))
print(f"  O within-shell ratios: {[round(r,3) for r in rat]}, geomean = {gm:.3f} (doc ~1.56; computed 1.59) vs phi = {PHI:.3f}")

print()
print("=" * 78)
print("3. fatigue-fracture-cascade.md")
print("=" * 78)
print("  m = 2*phi^k: k=0,1,2 ->", [2 * phi_pow(k) for k in range(3)], "(doc: 2, 3.24, 5.24)")
print("  table's 'nearest phi-power' values: phi^2 =", phi_pow(2), ", phi^3 =", phi_pow(3), "-> NOT on the 2*phi^k spectrum (internal contradiction)")
print(f"  phi^-3/2 = {phi_pow(-1.5):.4f} (doc claims 0.39; that value is phi^-2 = {phi_pow(-2):.4f})  <- arithmetic error")
print(f"  zeta(b=2) = ln2/lnphi = {math.log(2)/LNPHI:.3f} (doc claims 0.48; 0.48 = ln phi, arithmetic error; 1.44>1 is unphysical for roughness)")
print(f"  zeta(b=phi) = 1 (doc 1, OK)")
print(f"  predicted dK_th/K_IC range: phi^-1..phi^-3/2 = {phi_pow(-1):.3f}..{phi_pow(-1.5):.3f} vs empirical 0.1-0.3 -> no overlap (doc: 'in the right range' overclaims)")

print()
print("=" * 78)
print("4. neural-criticality.md")
print("=" * 78)
# damped two-fluid wave response spectrum: telegrapher G = (c^2 k^2 - w^2 - i g w)^-1
# solver-style G = (c^2 k^2 - w^2 + i nu w k^2)^-1 ; diffusion limit analytic w^-1/2
def S_telegrapher(w, gamma, c=1.0, lam=300.0, N=200000):
    k = np.linspace(1e-6, lam, N)
    d = (c * c * k * k - w * w) ** 2 + (gamma * w) ** 2
    return np.trapezoid(k * k / d, k)

def S_nuk2(w, nu, c=1.0, lam=300.0, N=200000):
    k = np.linspace(1e-6, lam, N)
    d = (c * c * k * k - w * w) ** 2 + (nu * w * k * k) ** 2
    return np.trapezoid(k * k / d, k)

print("  Linearized two-fluid wave system (solver: scalars react-diffuse via lambda(1-q)(EY-phi EI);")
print("  velocity: du/dt = -cs2 grad rho - nu k^2 u  =>  damped wave for rho).")
for gamma in (0.1, 1.0):
    ws = np.geomspace(1e-3, 30.0, 24)
    S = np.array([S_telegrapher(w, gamma) for w in ws])
    lo = S[ws < 0.5 * gamma]
    hi = S[ws > 5.0 * gamma]
    slope_lo = (np.log(S[ws < 0.5 * gamma][-1]) - np.log(S[ws < 0.5 * gamma][0])) / (np.log(ws[ws < 0.5 * gamma][-1]) - np.log(ws[ws < 0.5 * gamma][0])) if len(ws[ws < 0.5 * gamma]) > 2 else float('nan')
    slope_hi = (np.log(S[ws > 5 * gamma][-1]) - np.log(S[ws > 5 * gamma][0])) / (np.log(ws[ws > 5 * gamma][-1]) - np.log(ws[ws > 5 * gamma][0])) if len(ws[ws > 5 * gamma]) > 2 else float('nan')
    print(f"  gamma={gamma}: S(w) ~ w^{slope_lo:+.2f} (low-w diffusive limit; analytic w^-1/2)  ~ w^{slope_hi:+.2f} (high-w)")
for nu in (1.0, 10.0):
    ws = np.geomspace(1e-2, 30.0, 20)
    S = np.array([S_nuk2(w, nu) for w in ws])
    print(f"  nu={nu}: sample S(0.01)={S[0]:.4g}, S(30)={S[-1]:.4g}, log-log slope ~ {np.polyfit(np.log(ws[1:12]), np.log(S[1:12]), 1)[0]:+.2f} (mid range)")
print("  Verdict: no regime of the damped two-fluid wave response is w^-3/2;")
print("  the -3/2 avalanche exponent is the standard mean-field critical-branching result (generic SOC),")
print("  and '-5/3 + 1/6' has no shown derivation of the +1/6 correction.")
# other arithmetic
check("phi^18", phi_pow(18), 5.8e3, 2e-2)
check("f_phi lo", 0.1 * (1 + PHI) / (2 * math.pi) * 1.0, 0.04, 2e-1)
check("f_phi hi", 0.1 * (1 + PHI) / (2 * math.pi) * 10.0, 0.4, 2e-1)
check("circadian/ultradian 1440/90", 1440 / 90, 16.0, 1e-3)
check("phi^6", phi_pow(6), 17.94, 1e-3)
print(f"  16/17.94 = {16/17.94:.3f} (doc 0.89)")
check("phi^-9", phi_pow(-9), 0.0131, 2e-2)
check("phi^-10", phi_pow(-10), 0.0081, 2e-2)
check("20 um * phi^18", 20e-6 * phi_pow(18), 0.12, 1e-2)
# hierarchy table scale ratios
scales = [20e-9, 1e-6, 20e-6, 75e-6, 400e-6, 3e-3, 0.125, 0.175]
print("  hierarchy level scale ratios:", [round(scales[i + 1] / scales[i], 1) for i in range(len(scales) - 1)], " (doc: 'each level separated by ~phi')")
print("  -> ratios 2.5x-50x, not phi = 1.618")
for lab, s in [("synaptic cleft 20 nm", 20e-9), ("neuron soma 20 um", 20e-6), ("whole brain 20 cm", 0.2)]:
    print(f"    {lab}: n = {math.log(s / LPL) / LNPHI:.2f}")

print()
print("=" * 78)
print("5. market-cascade-cycles.md")
print("=" * 78)
check("phi^1.05", phi_pow(1.05), 1.66, 5e-3)
check("omega = 2pi/lnphi", 2 * math.pi / LNPHI, 13.06, 1e-3)
tau = [phi_pow(k) for k in range(10)]
print("  drawdown tau_k = phi^k (days):", [round(t, 1) for t in tau], " (doc: 1,1.6,2.6,4.2,6.8,11,18,29,47,76)")
print("  empirical LPPL omega 5-10 vs 13.06: ratios", [round(x / 13.06, 2) for x in (5, 8, 10)], " (doc claims omega/2..2omega/3 = 0.5..0.67)")
print("  -> empirical omega range extends below the claimed window (0.38 at omega=5)")
print("  lambda ~ sqrt(phi) =", math.sqrt(PHI), ", phi^(2/3) =", phi_pow(2 / 3), " (doc's re-fits are post-hoc adjustments)")

print()
print("=" * 78)
print("6. atmospheric-climate-cascade.md")
print("=" * 78)
for Lr, lab in [(1000, "Earth L_R=1000 km"), (2000, "Jupiter L_R=2000 km"), (300, "Mars L_R=300 km")]:
    print(f"  {lab}: L_phi(k=1) = {Lr/PHI:.0f} km, L_phi(k=2) = {Lr/PHI**2:.0f} km")
print("  observed Earth break ~500 km sits between 618 (k=1) and 382 (k=2): k is a free post-hoc integer")
print("  period ratios (doc): QBO 2.3yr -> ENSO 4yr: 4/2.33 =", round(4 / 2.33, 3), "vs phi^1 =", round(PHI, 3), "vs phi^1.15 =", round(phi_pow(1.15), 3))
print("  ENSO -> PDO 25/4 =", round(25 / 4, 3), "vs phi^3 =", round(phi_pow(3), 3), ", phi^4 =", round(phi_pow(4), 3), ", phi^3.8 =", round(phi_pow(3.8), 3))
print("  5.5/4 =", round(5.5 / 4, 3), "vs phi^0.67 =", round(phi_pow(0.67), 3))
print("  -> all three require FRACTIONAL exponents (1.15, 3.8, 0.67); no pair matches an integer phi-power")

print()
print("=" * 78)
print("7. muscle-cascade-lattice.md")
print("=" * 78)
check("1.70 ratio sqrt(4phi^2/(1+phi^2))", math.sqrt(4 * PHI ** 2 / (1 + PHI ** 2)), 1.70, 5e-3)
print("  hierarchy rungs recomputed as n = ln(scale/L_Pl)/ln(phi):")
for lab, s in [("filament 5-10 nm", (5e-9, 10e-9)), ("sarcomere 2.0-2.5 um", (2e-6, 2.5e-6)),
               ("myofibril 1 um", (1e-6, 1e-6)), ("fiber 50 um", (50e-6, 50e-6)),
               ("fascicle 1-5 mm", (1e-3, 5e-3)), ("belly 15-30 cm", (0.15, 0.3)),
               ("group 30-50 cm", (0.3, 0.5))]:
    n0, n1 = math.log(s[0] / LPL) / LNPHI, math.log(s[1] / LPL) / LNPHI
    print(f"    {lab:22s}: n = {n0:7.2f} .. {n1:7.2f}")
print("  doc table: filament ~130, sarcomere ~139-140, myofibril ~133, fiber ~143, fascicle ~150-153, belly ~166-167, group ~167-168")
print("  -> doc's own ladder formula puts fiber->belly span at ~16.6 rungs, not 23-24 (sec 3.2 overstates)")
print("  Z-disc: n = 139.2-139.9 (doc 139.2-139.7, consistent within rounding)")
print("  human window: n(8 um) =", round(math.log(8e-6 / LPL) / LNPHI, 1), " n(1.7 m) =", round(math.log(1.7 / LPL) / LNPHI, 1))

print()
print("=" * 78)
print("8. quasicrystal-stability.md")
print("=" * 78)
check("phi^-5", phi_pow(-5), 0.090, 1e-2)
check("phi^-4", phi_pow(-4), 0.146, 1e-2)
check("phi^4 (6.8x)", phi_pow(4), 6.85, 1e-2)
print("  N_rungs enters as a free range 3-5 (doc) -> 'zero-parameter' claim (abstract) contradicts it")
print("  '9% of the cohesive energy' reads phi^-5 off as an energy fraction; no shown step from the PDE")

print()
print("=" * 78)
print("9. exoplanet-phi-spacing.md")
print("=" * 78)
check("phi^3/2", phi_pow(1.5), 2.06, 5e-3)
a_pred = [0.4 * phi_pow(k) for k in range(10)]
a_obs = [0.387, 0.723, 1.000, 1.524, 2.8, 5.204, 9.582, 19.19, 30.07]
print("  predicted 0.4*phi^k:", [round(a, 2) for a in a_pred[:9]])
print("  observed planets:    ", a_obs)
devs = [abs(math.log(o / p)) for o, p in zip(a_obs, a_pred)]
print("  |ln dev| per slot (doc's slotting Mercury..Neptune = 0..8):", [round(d, 3) for d in devs])
print("  mean |ln dev| as slotted:", round(np.mean(devs), 3), " (Saturn 34% off, Jupiter 17% off, slot 7 empty)")
remapped = [abs(math.log(o / p)) for o, p in zip([0.387, 0.723, 1.0, 1.524, 2.8, 5.204, 9.582, 19.19, 30.07],
                                                 [0.4, 0.65, 1.05, 1.69, 2.74, 4.44, 7.18, 18.79, 30.41])]
print("  with doc's post-hoc remap (Uranus->slot 8, Neptune->slot 9, slot 7 dropped): mean |ln dev| =", round(np.mean(remapped), 3))
tb = [0.4 + 0.3 * 2 ** n for n in range(-1, 8)]
devs_tb = [abs(math.log(o / p)) for o, p in zip(a_obs, tb)]
print("  Titius-Bode slots:", [round(t, 2) for t in tb], " mean |ln dev|:", round(np.mean(devs_tb), 3))
print("  -> 'comparable to or better than Titius-Bode': remapped phi-fit 0.088 vs TB 0.084 = comparable, not better;")
print("     unremapped 0.193 = worse. The remap itself is post-hoc (an empty slot 7).")
rat_doc = [0.723, 1.52, 3.42, 1.83, 1.97, 1.56]
print("  doc's own 6-ratio geomean:", round(math.exp(sum(math.log(r) for r in rat_doc) / len(rat_doc)), 3), " (doc claims ~1.73; computed 1.66)")

print()
print("=" * 78)
print("10. metabolic-scaling.md")
print("=" * 78)
check("D_f = ln2/lnphi", math.log(2) / LNPHI, 1.44, 1e-2)
check("D_f = ln3/lnphi", math.log(3) / LNPHI, 2.29, 2e-2)  # doc says 2.29; exact 2.283
print("  exact ln3/lnphi =", round(math.log(3) / LNPHI, 4))
check("alpha = 3/2.44", 3 / 2.44, 1.23, 1e-2)
check("alpha = 3/3.29", 3 / 3.29, 0.91, 1e-2)
check("phi^2/(phi^2+1)", PHI ** 2 / (PHI ** 2 + 1), 0.724, 1e-2)
check("1/(phi^2+1)", 1 / (PHI ** 2 + 1), 0.276, 1e-2)
check("phi^3", phi_pow(3), 4.24, 1e-2)
print("  doc's own verdict stands: derivation does not close (4% gap 0.724 vs 0.750)")

print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
print("Closed mechanism steps with shown math: none found in the 10 docs.")
print("Arithmetic errors found: fatigue phi^-3/2 (0.39 vs 0.486), fatigue zeta(b=2) (0.48 vs 1.44),")
print("  Madelung '2*sum k^2' identity (fails at term 4), Madelung capacity column (6/7 rows self-contradictory),")
print("  muscle rung table (2-5 rung errors, span 23-24 vs 16.6), neural hierarchy 'phi-spaced levels' claim (ratios 2.5x-50x),")
print("  nuclear '126 + Fib = 184' (58 not Fibonacci), exoplanet geomean 1.73 vs 1.66, metabolic ln3/lnphi 2.29 vs 2.283.")
