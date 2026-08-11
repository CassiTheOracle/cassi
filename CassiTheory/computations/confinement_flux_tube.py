#!/usr/bin/env python3
"""
Saturated-Gate Flux Tube: Confinement String Tension from the Cascade
======================================================================

Numerical verification for `foundations/quark-confinement.md`:

- Rung 95:  ell_95 = ell_Pl * phi^95 = 1.154 fm,  Lambda_QCD = hbar*c/ell_95 = 0.171 GeV
- Tube extensivity:  E(r) = mu * r + 2 E_core  ->  F = -mu (constant; linear confinement)
- String tension:    mu = kappa * Lambda_QCD^2 = kappa * (M_Pl / phi^95)^2,  kappa = O(1)
- Comparison:        mu vs measured sigma ~ 0.18 GeV^2  (sqrt(sigma) = 0.424 GeV)
- String breaking:   r_b = 2 m_q / sigma vs lattice QCD r_b ~ 1.2 fm

Usage: python computations/confinement_flux_tube.py
"""
import math

phi = (1 + math.sqrt(5)) / 2
ell_pl = 1.616255e-35            # m (dimensionful-cascade.md)
hc_mev_fm = 197.3269804          # MeV fm
hc_gev_m = hc_mev_fm * 1e-18     # GeV m
M_pl = hc_gev_m / ell_pl         # GeV
sigma = 0.18                     # GeV^2, measured string tension (Cornell / lattice QCD)
fm_per_gev = 0.1973269804        # fm per GeV^-1


def rung(length_m):
    """Cascade rung n = log_phi(length / ell_Pl)."""
    return math.log(length_m / ell_pl) / math.log(phi)


print("=" * 76)
print("RUNG 95 (dimensionful-cascade.md: QCD confinement at step 95)")
print(f"  phi^95            = {phi**95:.6e}")
ell95 = ell_pl * phi ** 95
print(f"  ell_95            = {ell95:.4e} m = {ell95 * 1e15:.4f} fm")
Lam95 = hc_gev_m / ell95
print(f"  Lambda_QCD = E_95 = hbar c / ell_95 = {Lam95:.4f} GeV")
print(f"                       (= M_Pl / phi^95 = {M_pl / phi**95:.4f} GeV; identity to 1e-5)")
print()
print("STRING TENSION  mu = kappa * Lambda_QCD^2 = kappa * (M_Pl / phi^95)^2")
mu1 = Lam95 ** 2
mu_phi = mu1 / phi
print(f"  mu (kappa=1)         = {mu1:.4f} GeV^2     sqrt(mu) = {math.sqrt(mu1):.4f} GeV")
print(f"  mu (kappa=1/phi)     = {mu_phi:.4f} GeV^2     sqrt(mu) = {math.sqrt(mu_phi):.4f} GeV")
print(f"  measured sigma       = {sigma:.2f} GeV^2     sqrt(sigma) = {math.sqrt(sigma):.4f} GeV")
print(f"  mu / sigma           = {mu1 / sigma:.3f} (kappa=1)   {mu_phi / sigma:.3f} (kappa=1/phi)")
Lam_s = math.sqrt(sigma)
print(f"  Lambda reproducing sigma: sqrt(sigma) = {Lam_s:.4f} GeV")
print(f"      -> rung n* = log_phi(hbar c/(Lam_s ell_Pl)) = {rung(hc_gev_m / Lam_s):.2f}")
E93 = hc_gev_m / (ell_pl * phi ** 93)
print(f"  rung-93 energy E_93 = {E93:.4f} GeV = {E93 / Lam_s:.4f} x sqrt(sigma)")
print()
print("STRING BREAKING  r_b = 2 m_q / sigma  (sigma = 0.18 GeV^2)")
for lab, mq in [("pion floor m_pi = 0.140 GeV (rung 95.4)", 0.140),
                ("constituent m_N/3 = 0.313 GeV (rung 93.7)", 0.313)]:
    rb = 2 * mq / sigma
    print(f"  {lab}: r_b = {rb:.2f} GeV^-1 = {rb * fm_per_gev:.2f} fm")
rb_lat = 1.2
print(f"  lattice r_b ~ {rb_lat} fm implies 2 m_q = {sigma * rb_lat / fm_per_gev:.3f} GeV")
print("=" * 76)
