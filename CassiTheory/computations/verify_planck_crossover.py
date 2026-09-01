# Verify the three-dimensional phase-resolution derivation of sigma = l_Pl/phi^3
# (delta = 3) and the conditional proton coherence-budget arithmetic.
# Run from the repo root:  python computations/verify_planck_crossover.py

import math

phi = (1.0 + math.sqrt(5.0)) / 2.0
l_Pl = 1.616255e-35     # m (CODATA 2018)
M_Pl = 1.2209e19        # GeV (sqrt(hbar c / G))
hbar_GeVs = 6.582119569e-25   # GeV*s
m_p = 0.938272          # GeV
sec_per_yr = 3.15576e7

print("== 1. sigma = l_Pl / phi^3 = l_Pl * phi^(-3), rung n = -3 ==")
print(f"  phi     = {phi:.10f}")
print(f"  phi^3   = {phi**3:.10f}   (cube of the per-axis factor phi; quoted 4.236)")
sigma = l_Pl / phi**3
print(f"  sigma   = {sigma:.6e} m   (quoted 3.82e-36 m)")
print(f"  rung    = log_phi(sigma/l_Pl) = {math.log(sigma / l_Pl) / math.log(phi):.10f}  (must be -3.000)")
assert math.isclose(sigma / l_Pl, phi**-3, rel_tol=1e-12)
assert math.isclose(math.log(sigma / l_Pl) / math.log(phi), -3.0, abs_tol=1e-9)

print("\n== 2. UV scale = 1/sigma = phi^3 * M_Pl ==")
Lambda = phi**3 * M_Pl
print(f"  Lambda_UV = {Lambda:.4e} GeV   (quoted 5.17e19)")
print(f"  sigma     = {1.0 / Lambda:.4e} GeV^-1   (quoted 1.93e-20)")
sigma_GeVinv = sigma / 0.19732698e-15
print(f"  sigma[GeV^-1] = {sigma_GeVinv:.6e}   (matches quoted 1.93e-20)")
print(f"  M_Pl*sigma    = {M_Pl * sigma_GeVinv:.10f}  = phi^-3 (identity exact in natural units; 8e-6 from rounded M_Pl)")
assert math.isclose(M_Pl * sigma_GeVinv, phi**-3, rel_tol=1e-4)
assert math.isclose(Lambda, 5.1718e19, rel_tol=1e-3)
assert math.isclose(sigma_GeVinv, 1.9336e-20, rel_tol=1e-3)

print("\n== 3. Cascade-suppression exponent N = n(n+1)/2 + delta*(n+1), delta = 3 ==")
def S(n, delta):
    return n * (n + 1) / 2.0 + delta * (n + 1)

n = 91.46   # registered proton budget coordinate (cassi-theory-reference §6.6)
N_prot = S(n, 3)
print(f"  n = {n}: N = {N_prot:.4f}  -> quoted exponent 4506 (4505.6 rounds to 4506)")
print(f"  delta=3 term contributes {N_prot - S(n, 0):.4f} of the exponent")
# direct per-step sum over the integer portion plus the declared fractional tail
i_floor = math.floor(n)
direct = sum((k + 3) for k in range(i_floor + 1))
frac = (n - i_floor) * (i_floor + 1 + 3)
print(f"  direct integer sum 0..{i_floor} = {direct}; + fractional tail = {direct + frac:.4f}")
assert 4505.0 < N_prot < 4507.0, "exponent must stay in the quoted 4506 window"
assert math.isclose(direct + frac, N_prot, rel_tol=1e-3)

print("\n== 4. Conditional cycle-to-time map (one Compton-cycle trial) ==")
omega_p = m_p / hbar_GeVs
log10_budget = N_prot * math.log10(phi)
log10_tau_yr = log10_budget - math.log10(omega_p) - math.log10(sec_per_yr)
print(f"  log10(modeled cycles) = {log10_budget:.4f}")
print(f"  omega_p               = {omega_p:.4e} s^-1")
print(f"  log10(conditional yr) = {log10_tau_yr:.4f}   (quoted ~10^910 yr)")
print("  physical rate remains unselected; this line only applies the declared trial map")
assert math.isclose(N_prot, 4505.5758, rel_tol=1e-12)
assert math.isclose(log10_tau_yr, 910.0, abs_tol=1.0)

print("\n== 5. Cross-check numbers cited in quantum-gravity.md §2.1 ==")
E77 = M_Pl * phi**-77
E80 = M_Pl * phi**-80
print(f"  E_77 = M_Pl*phi^-77 = {E77:.1f} GeV   (sector-coupling rung 77; quoted 987.7)")
print(f"  E_80 = M_Pl*phi^-80 = {E80:.1f} GeV   (EW VEV rung 80; quoted 233.2)")
print(f"  rung offset: 77 = 80 - 3")
print(f"  phi^3 * v_0 = {phi**3 * 246.0:.2f} GeV   (sector-coupling M_s reading; quoted 1042.07)")
print(f"  fixed-point pi/rho = (phi-1)/(phi+1) = {(phi - 1) / (phi + 1):.10f} == phi^-3 = {phi**-3:.10f}")
assert math.isclose(E77, 987.7, rel_tol=1e-3)
assert math.isclose(E80, 233.2, rel_tol=1e-3)

print("\nALL CHECKS PASSED")
