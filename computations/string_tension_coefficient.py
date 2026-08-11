#!/usr/bin/env python3
"""
O(1) Coefficient of the Confinement String Tension: kappa = 2*pi?
================================================================

Numerical verification for `foundations/quark-confinement.md` §3:

- Rung 95:  Lambda_QCD = M_Pl / phi^95 = 0.17094 GeV
- Derived tension:  mu = kappa * Lambda_QCD^2,  kappa = O(1)
- Required coefficient:  kappa* = sigma / mu  (sigma measured)
- Candidate table: 2*pi (+2.0%), 2*phi^2+1 (+1.2%), 4*phi (+5.1%),
  phi^4 (+11.3%), pi (-49%), golden-angle family (-37%..-76%)
- sigma-range sensitivity: lattice determinations sqrt(sigma) = 0.42-0.44 GeV
  (sigma in [0.17, 0.21] GeV^2); the 2*pi closure sits inside the band
- Equivalent rung displacement of the 2.0% residual

Usage: python computations/string_tension_coefficient.py
"""
import math

phi = (1 + math.sqrt(5)) / 2
ell_pl = 1.616255e-35            # m (dimensionful-cascade.md)
hc_mev_fm = 197.3269804          # MeV fm
hc_gev_m = hc_mev_fm * 1e-18     # GeV m
M_pl = hc_gev_m / ell_pl         # GeV
sigma = 0.18                     # GeV^2, Cornell / lattice QCD tension (doc datum)

print("=" * 76)
print("RUNG 95  Lambda_QCD = M_Pl / phi^95")
Lam = M_pl / phi ** 95
mu = Lam ** 2
print(f"  phi^95            = {phi**95:.6e}")
print(f"  M_Pl              = {M_pl:.6e} GeV")
print(f"  Lambda_QCD        = {Lam:.6f} GeV")
print(f"  mu = Lambda^2     = {mu:.6f} GeV^2      sqrt(mu) = {math.sqrt(mu):.6f} GeV")
print()
print("REQUIRED COEFFICIENT  kappa* = sigma / mu   (sigma = 0.18 GeV^2, doc datum)")
kstar = sigma / mu
print(f"  kappa*            = {kstar:.6f}")
print()
print("CANDIDATES (residual = (k - k*)/k*)")
cands = [
    ("2*pi            (pitch convention 2*pi per rung)", 2 * math.pi),
    ("2*phi^2+1       (phi algebra; no mechanism)",      2 * phi ** 2 + 1),
    ("4*phi           (phi algebra)",                     4 * phi),
    ("phi^4           (phi algebra)",                     phi ** 4),
    ("pi              (circle of radius ell_95)",         math.pi),
    ("1/phi           (checkerboard cell ell^2/phi)",     1 / phi),
    ("2*pi/phi^2      (golden angle)",                    2 * math.pi / phi ** 2),
    ("2*pi/phi        (golden-angle complement)",         2 * math.pi / phi),
    ("2*pi/phi^3      (2*pi/phi^4 * phi)",                2 * math.pi / phi ** 3),
]
for name, k in sorted(cands, key=lambda kv: abs(kv[1] - kstar)):
    print(f"  {name:42s} k = {k:8.5f}  residual = {(k - kstar) / kstar * 100:+7.2f}%")
print()
print("2*pi CLOSURE  sigma_tube = 2*pi*Lambda_QCD^2")
two_pi_mu = 2 * math.pi * mu
print(f"  2*pi*mu           = {two_pi_mu:.6f} GeV^2")
print(f"  sigma (Cornell)   = {sigma:.4f} GeV^2  -> residual {((two_pi_mu - sigma) / sigma) * 100:+.2f}%")
print(f"  sigma at hit      = {two_pi_mu:.4f} GeV^2  sqrt(sigma) = {math.sqrt(two_pi_mu):.4f} GeV")
print()
print("SIGMA-RANGE SENSITIVITY (lattice determinations sqrt(sigma) = 0.42-0.44 GeV)")
for lab, s in [("sigma = 0.17 (band low)", 0.17),
               ("sigma = 0.18 (Cornell datum)", 0.18),
               ("sigma = 0.1936 (sqrt = 0.44 GeV)", 0.44 ** 2),
               ("sigma = 0.21 (band high)", 0.21)]:
    print(f"  {lab:28s}: 2*pi*mu/sigma = {two_pi_mu / s:6.3f}  residual = {(two_pi_mu - s) / s * 100:+7.2f}%")
print()
print("RUNG EQUIVALENT OF THE 2.0% RESIDUAL (delta n = ln(sigma/(2*pi*mu)) / (2 ln phi))")
dn = math.log(sigma / two_pi_mu) / (2 * math.log(phi))
print(f"  delta n = {dn:+.4f} rungs   (a 2.0% tension residual is a 1.0% Lambda / 0.02-rung displacement)")
print()
print("REPRODUCTION SCALE  Lambda* = sqrt(sigma / (2*pi))  and its rung")
Lam_star = math.sqrt(sigma / (2 * math.pi))
n_star = math.log(M_pl / Lam_star) / math.log(phi)
print(f"  Lambda*           = {Lam_star:.4f} GeV")
print(f"  rung(Lambda*)     = {n_star:.2f}   (rung 95 closes sigma to 2.0% with kappa = 2*pi)")
print(f"  mu/sigma ratios   = {mu / sigma:.3f} (k=1)   {mu / (phi * sigma):.3f} (k=1/phi)   {two_pi_mu / sigma:.3f} (k=2*pi)")
print()
print("VERDICT")
if abs((two_pi_mu - sigma) / sigma) < 0.05:
    print("  kappa = 2*pi closes the tension to {:.1f}% at the Cornell datum and sits inside".format(
        abs((two_pi_mu - sigma) / sigma) * 100))
    print("  the lattice band [0.17, 0.21] GeV^2; tier: Derived conditional on the 2*pi-per-rung")
    print("  winding reading (pitch convention, spiral-dynamics.md sec 1.1). The 2*phi^2+1 = 6.236")
    print("  candidate is numerically tighter (+1.2%) but has no mechanism; phi^4 and the")
    print("  golden-angle family are excluded.")
else:
    print("  no candidate closes; kappa = O(1) remains open.")
print("=" * 76)
