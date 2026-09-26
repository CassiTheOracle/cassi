#!/usr/bin/env python3
"""Check the Planck-to-proton two-rail scale-current identities."""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
ELL_PL = 1.616255e-35  # m
HBAR_C = 0.1973269804e-15  # GeV m
M_PROTON = 0.93827208816  # GeV

rho = 1.0
k_over_hbar = 1.0
delta = 2.0 * math.pi
ell_proton = HBAR_C / M_PROTON
s_proton = math.log(ell_proton / ELL_PL) / math.log(PHI)

# Exact phi-composition and zero-total-current solution.
e_y = rho / PHI
e_i = rho / PHI**2
nu_y = delta / (PHI**2 * s_proton)
nu_i = -delta / (PHI * s_proton)
j_y = k_over_hbar * e_y * nu_y
j_i = k_over_hbar * e_i * nu_i
j_q = (j_y - j_i) / 2.0
j_q_expected = rho * delta / (PHI**3 * s_proton)

# K_s = hbar = 1 for the normalized energy check.
energy = 0.5 * s_proton * (e_y * nu_y**2 + e_i * nu_i**2)
energy_expected = rho * delta**2 / (2.0 * PHI**3 * s_proton)
tension_ratio = delta**2 / (2.0 * PHI**3 * s_proton**2)
selected_s = abs(delta) * math.sqrt(1.0 / (2.0 * PHI**3 * tension_ratio))

assert math.isclose(e_y / e_i, PHI, rel_tol=1e-14)
assert math.isclose(nu_i / nu_y, -PHI, rel_tol=1e-14)
assert math.isclose(s_proton * (nu_y - nu_i), delta, rel_tol=1e-14)
assert math.isclose(j_y + j_i, 0.0, abs_tol=1e-14)
assert math.isclose(j_q, j_q_expected, rel_tol=1e-14)
assert math.isclose(energy, energy_expected, rel_tol=1e-14)
assert math.isclose(selected_s, s_proton, rel_tol=1e-14)

print("Planck-to-proton scale-current check")
print(f"  proton reduced Compton wavelength = {ell_proton:.9e} m")
print(f"  scale endpoint s_p               = {s_proton:.9f}")
print(f"  nu_I / nu_Y                      = {nu_i / nu_y:.12f}")
print(f"  normalized total current         = {j_y + j_i:.3e}")
print(f"  hbar J_Q / (K_s rho)             = {j_q:.9f}")
print(f"  E_circ / (K_s rho)               = {energy:.9f}")
print(f"  T_s / (K_s rho), m=1             = {tension_ratio:.9e}")
print("ALL CHECKS PASSED")
