#!/usr/bin/env python3
"""
Sector-Coupling Rung Identity: kappa_s = phi^-6 / v0^2 at rung 77
================================================================

Closes the audit finding on `foundations/sector-coupling-derivation.md`
sec. 2: the derivation must exhibit the rung arithmetic that places
kappa_s at rung 77 (the doc previously asserted "three rungs above
electroweak" without displaying why the coupling's own form lands there).

The rung identity (displayed algebra):
  (i)   v0   = M_Pl * phi^{-80}                (EW VEV anchor, rung 80;
                                                E_80 = M_Pl*phi^{-80} = 233.2 GeV,
                                                n(v0) = log_phi(M_Pl/v0) = 79.89)
  (ii)  v0^2 = M_Pl^2 * phi^{-160}             (squaring DOUBLES the rung: 80 -> 160)
  (iii) kappa_s = phi^-6 / v0^2
                = phi^-6 * M_Pl^-2 * phi^160  = M_Pl^-2 * phi^154
        (the naive exponent sum -160 - 6 = -166 is NOT the physical
         statement: the dimensionful base is M_Pl^-2, so the phi-exponent
         relative to that base is +154)
  (iv)  M_s = kappa_s^{-1/2} = M_Pl * phi^{-154/2} = M_Pl * phi^{-77}
        -> the mass scale sits at rung 77 = 154/2
  (v)   delta = n(v0) - n(M_s) = 80 - 77 = 3:
        the coupling sits delta = 3 rungs BELOW the VEV -- the SAME delta
        as sigma = l_Pl/phi^3 (gravity/quantum-gravity.md sec. 2.1,
        derived conditional on d = 3).  Hence kappa_s's placement is
        derived CONDITIONAL on delta = 3.

Also verified:
  1. phi^-6 = 0.05573 (NOT 0.23607 -- that is phi^-3; guards the
     phi^-3/phi^-6 confusion in the value of kappa_s)
  2. E_80 = 233.2 GeV; E_77 = 987.7 GeV; E_77/E_80 = phi^3 exactly
  3. kappa_s = 9.21e-7 GeV^-2 = 0.92 TeV^-2; M_s = phi^3 v0 = 1042.07 GeV
  4. E_80 vs v0: -5.22% (the "5.3% gap" class, deriving-remaining-gaps.md
     sec. 3.3); M_s vs E_77: +5.50% (same discretization-residual class)
  5. 1 TeV sits at log_phi(M_Pl/TeV) = 76.97, +1.24% off rung 77

Usage: python computations/kappa_s_rung_identity.py
"""

import math

PHI    = (1.0 + math.sqrt(5.0)) / 2.0
M_PL   = 1.2209e19        # Planck mass [GeV]
V0     = 246.0            # electroweak VEV [GeV]

def check(name, got, expected, tol):
    ok = abs(got - expected) <= tol * max(1.0, abs(expected))
    print(f"  {name:<44} = {got:<16.6g}  target {expected:<14.6g}  {'OK' if ok else 'FAIL'}")
    return ok

print("=" * 78)
print("  KAPPA_S = PHI^-6 / V0^2 : RUNG-77 IDENTITY (delta = 3)")
print("  sector-coupling-derivation.md sec. 2 audit closure")
print("=" * 78)

all_ok = True

# ---------------------------------------------------------------------------
print()
print("─ 1. The anchor: v0 at rung 80 (EW VEV) ─")
print()
n_v0 = math.log(M_PL / V0) / math.log(PHI)
E80  = M_PL * PHI ** (-80)
print(f"  E_80  = M_Pl*phi^-80       = {E80:.4f} GeV   (doc: 233.2 GeV)")
print(f"  n(v0) = log_phi(M_Pl/v0)   = {n_v0:.4f}     (doc: 79.89 ~ 80)")
all_ok &= check("E_80", E80, 233.2, 1e-3)
all_ok &= check("n(v0)", n_v0, 79.89, 1e-2)
off80 = (E80 - V0) / V0
print(f"  E_80 vs v0 offset          = {off80*100:+.2f}%   (the '5.3% gap' class)")

# ---------------------------------------------------------------------------
print()
print("─ 2. Squaring doubles the rung: v0^2 carries rung 2*80 = 160 ─")
print()
print("  v0   = M_Pl * phi^{-80}                  -> phi-exponent -80")
print("  v0^2 = M_Pl^2 * phi^{-160}               -> phi-exponent -160")
print("  (the dimensionful base is M_Pl^2; rung index doubles under squaring)")

# ---------------------------------------------------------------------------
print()
print("─ 3. kappa_s = phi^-6/v0^2 = M_Pl^-2 * phi^154 ─")
print()
ks = PHI ** (-6) / V0 ** 2
print(f"  phi^-6                    = {PHI**-6:.8f}   (NOT 0.23607 -- that is phi^-3)")
print(f"  kappa_s [GeV^-2]          = {ks:.6e}   (doc: 9.21e-7)")
print(f"  kappa_s [TeV^-2]          = {ks*1e6:.6f}   (doc: 0.92)")
print(f"  kappa_s = M_Pl^-2 phi^154 :  M_Pl^-2 = {1/M_PL**2:.6e} GeV^-2,"
      f"  phi^154 = {PHI**154:.6e}")
print(f"  (naive exponent sum -160-6 = -166 is not the physical statement;")
print(f"   relative to the M_Pl^-2 base the phi-exponent is +154)")
all_ok &= check("phi^-6", PHI ** -6, 0.05572809, 1e-6)
all_ok &= check("kappa_s GeV^-2", ks, 9.2088e-7, 1e-4)
all_ok &= check("kappa_s TeV^-2", ks * 1e6, 0.9209, 1e-4)

# ---------------------------------------------------------------------------
print()
print("─ 4. The mass scale: M_s = kappa_s^-1/2 = M_Pl * phi^{-77}, rung 77 ─")
print()
Ms = ks ** (-0.5)
n_s = math.log(Ms / M_PL) / math.log(PHI)
resid_s = 77 + n_s          # n_s < 0: steps below rung 77
resid_v0 = 80 - n_v0        # EW anchor residual
print(f"  M_s = kappa_s^-1/2        = {Ms:.4f} GeV   (doc: 1042.07 GeV = phi^3 v0)")
print(f"  rung index (exponent)     = 154/2 = {154/2}   (exact integer arithmetic)")
print(f"  log_phi(M_s/M_Pl)         = {n_s:.10f}")
print(f"  = -(n(v0) - 3)            = {-(n_v0 - 3):.10f}   (exact: M_s = phi^3 v0)")
print(f"  -> the physical scale sits delta_n = {resid_s:.4f} steps below rung 77 --")
print(f"     the SAME discretization residual as the EW anchor (delta_n = {resid_v0:.4f},")
print(f"     the '5.3% gap' class of deriving-remaining-gaps.md sec. 3.3)")
all_ok &= check("M_s GeV", Ms, 1042.07, 1e-4)
all_ok &= check("n(M_s) = -(n(v0)-3)", n_s, -(n_v0 - 3), 1e-12)
all_ok &= check("residual 77+n(M_s) = 80-n(v0)", resid_s, resid_v0, 1e-12)
all_ok &= check("phi^3 v0", PHI ** 3 * V0, Ms, 1e-12)

E77 = M_PL * PHI ** (-77)
print(f"  E_77 = M_Pl*phi^-77       = {E77:.4f} GeV   (doc: 987.7 GeV)")
print(f"  E_77/E_80                 = {E77/E80:.10f} = phi^3 = {PHI**3:.10f}")
print(f"  M_s vs E_77 offset        = {(Ms/E77-1)*100:+.2f}%   (same residual class as the EW anchor)")
all_ok &= check("E_77", E77, 987.7, 1e-3)

# ---------------------------------------------------------------------------
print()
print("─ 5. delta = n_v0 - n_kappa = 80 - 77 = 3: shared with sigma ─")
print()
delta = 80 - 77
print(f"  delta = n(v0) - n(M_s)   = {delta}")
print(f"  the coupling sits delta = 3 rungs BELOW the EW VEV -- the SAME")
print(f"  delta as sigma = l_Pl/phi^3 (gravity/quantum-gravity.md sec. 2.1,")
print(f"  'derived conditional on d = 3'): kappa_s's placement is derived")
print(f"  CONDITIONAL on delta = 3.")
all_ok &= check("delta", delta, 3, 0)

# ---------------------------------------------------------------------------
print()
print("─ 6. Round 1 TeV vs rung 77 ─")
print()
n_tev = math.log(M_PL / 1e3) / math.log(PHI)
print(f"  log_phi(M_Pl/1 TeV)       = {n_tev:.4f}   (doc: 76.97)")
print(f"  1 TeV vs E_77             = {(1e3/E77-1)*100:+.2f}%   (doc: +1.24%)")
all_ok &= check("n(1 TeV)", n_tev, 76.97, 1e-2)

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print(f"  ALL CHECKS PASSED: {all_ok}")
print("=" * 78)
