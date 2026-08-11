#!/usr/bin/env python3
"""
q-form inventory check: equivalence/reduction relations among the q
definitions (consistency sweep 2026-08-11)
========================================================================

Forms (`foundations/cassi-theory-reference.md` sec. 2.4 + inventory note;
`foundations/unified-lagrangian.md` sec. 1.5/3.2):

  (1) canonical     q = rho^2 / (rho^2 + phi^-2 + eps^2),  eps^2 = (Psi_0 - phi Psi_1)^2
  (2) per-rung      q_i = 1 - phi^(-i-delta),              delta = 3
  (3) equilibrium   q = M/(M + phi^-2),  M = rho^2 (field power)
                    (as written in unified-lagrangian.md, M = Psi_0^2 + Psi_1^2 = rho,
                    a density -- dimensionally inconsistent with (1); the
                    reduction is M -> rho^2, the solver's M_qi = (E_Y+E_I)^2)
  (4) branch        q_alpha ~ |psi_alpha|^2  (removed 2026-08-11, quantum-
                    measurement-derivation.md sec. 4.5; no consumers remain)

Verified here:
  1. q_eq = phi^-2/(phi^2 + phi^-2) ~ 0.1273 pins the fixed-point power
     rho^2 = phi^-6 (rho = phi^-3); gate closure 1-q = phi^-2/(phi^2+phi^-2)
     under the solver normalization rho^2 = phi^2 (ns_gate_correction.py).
  2. Form (3) as written (M = rho): q3 = rho/(rho + phi^-2) = phi^-1 ~ 0.382
     at the fixed point -- NOT q_eq (residual 0.2546, ratio phi^2+phi^-2 = 3).
  3. Form (3) with M = rho^2: q3 = rho^2/(rho^2 + phi^-2) = q_eq EXACTLY at
     eps = 0 (residual < 1e-16); the omitted eps^2 is the only discrepancy
     away from equilibrium (relative residual -eps^2/(rho^2+phi^-2+eps^2)).
  4. E = M^2/(M + phi^-2) (unified-lagrangian sec. 1.5) with M = rho^2 is the
     coherent field power E = q*rho^2 = rho^4/(rho^2+phi^-2) at equilibrium.
  5. Form (2) is a per-rung dephasing profile, not the equilibrium value of
     (1): residuals |q_i - q_eq| = 0.64-0.85 for i = 0..5 (reference
     normalization); crossover only at the sub-Planckian rung i* ~ -2.72
     (solver/closure normalization rho^2 = phi^2: i* ~ +1.28). Exact ties:
     the delta = 3 anchor 1 - q_0 = phi^-3 = (pi/rho)_eq and the per-rung
     step 1 - q_{i+1} = phi^-1 (1 - q_i).

Usage: python computations/q_form_inventory_check.py
"""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI2 = PHI ** 2
PHI_M2 = PHI ** (-2)
PHI3 = PHI ** 3
PHI_M3 = PHI ** (-3)

def rjust(x, w=18):
    return f"{x:>{w}}"

print("=" * 78)
print("  q-FORM INVENTORY: EQUIVALENCE / REDUCTION RELATIONS")
print("=" * 78)

# ---------------------------------------------------------------------------
print()
print("─ 1. Fixed-point value and normalizations of the canonical form (1) ─")
print()
# q = rho^2/(rho^2 + phi^-2 + eps^2); at eps = 0, q_eq = phi^-2/(phi^2 + phi^-2)
q_eq = PHI_M2 / (PHI2 + PHI_M2)
print(f"  q_eq = phi^-2/(phi^2 + phi^-2)      = {q_eq:.12f}  (docs: ~0.127)")
print(f"  => fixed-point power rho^2 = phi^-6 = {PHI ** -6:.12f}")
print(f"  => fixed-point density  rho = phi^-3 = {PHI_M3:.12f}  (== (pi/rho)_eq)")
print(f"  check: rho^2/(rho^2 + phi^-2) @ rho^2 = phi^-6 : "
      f"{(PHI ** -6) / (PHI ** -6 + PHI_M2):.12f}")
rho2_eq = PHI ** -6
# solver closure normalization (ns_gate_correction.py): rho^2 = phi^2
rho2_solver = PHI2
q_solver_closure = rho2_solver / (rho2_solver + PHI_M2)
print(f"  solver closure normalization rho^2 = phi^2 : q = {q_solver_closure:.12f},"
      f" 1-q = {1.0 - q_solver_closure:.12f} (== phi^-2/(phi^2+phi^-2) = q_eq value)")
# saturation limit
for r2 in (1.0, PHI ** 6):
    print(f"  saturation rho^2 = {r2:>7.3f} : q = {r2 / (r2 + PHI_M2):.12f}")

# ---------------------------------------------------------------------------
print()
print("─ 2. Form (3) as written (M = rho, a density): q3 = rho/(rho + phi^-2) ─")
print()
rho_eq = PHI_M3                       # reference fixed-point density
q3_written = rho_eq / (rho_eq + PHI_M2)
print(f"  q3_written @ fixed point = {q3_written:.12f}  (== phi^-1)")
print(f"  q_eq                     = {q_eq:.12f}")
print(f"  residual |q3_written - q_eq| = {abs(q3_written - q_eq):.12f}")
print(f"  ratio q3_written/q_eq        = {q3_written / q_eq:.12f}  (== phi^2 + phi^-2 = 3)")
print(f"  -> dimensionally inconsistent as written: numerator M (density) vs rho^2 (power).")

# ---------------------------------------------------------------------------
print()
print("─ 3. Form (3) reduced, M = rho^2 (field power, solver's M_qi) ─")
print()
rho4 = rho2_eq ** 2
q3_reduced = rho2_eq / (rho2_eq + PHI_M2)
print(f"  q3_reduced @ eps = 0    = {q3_reduced:.16f}")
print(f"  q_eq                   = {q_eq:.16f}")
print(f"  residual                = {abs(q3_reduced - q_eq):.3e}  (exact identity)")
print()
print("  Away from equilibrium (eps^2 > 0): the omitted term is the only discrepancy.")
print("  relative residual (q3_reduced - q1)/q1 = eps^2/(rho^2 + phi^-2 + eps^2):")
for eps2 in (PHI ** -4, PHI_M2, 0.1, 1.0):
    q1 = rho2_eq / (rho2_eq + PHI_M2 + eps2)
    rel = (q3_reduced - q1) / q1
    print(f"    eps^2 = {eps2:>8.4f} : q1 = {q1:.6f}, q3 = {q3_reduced:.6f}, "
          f"rel.resid = {rel:+.6f} ({rel * 100:+.2f}%)")

# ---------------------------------------------------------------------------
print()
print("─ 4. Qi coherent energy E = M^2/(M + phi^-2), M = rho^2 (sec. 1.5) ─")
print()
E_eq = rho4 / (rho2_eq + PHI_M2)
print(f"  E = rho^4/(rho^2 + phi^-2) @ fixed point = {E_eq:.6e}")
print(f"  E = q*rho^2                    @ fixed point = {q_eq * rho2_eq:.6e}")
print(f"  identity |E - q*rho^2| = {abs(E_eq - q_eq * rho2_eq):.3e}  (exact)")

# ---------------------------------------------------------------------------
print()
print("─ 5. Form (2) per-rung profile vs canonical equilibrium value ─")
print()
print(f"  q_i = 1 - phi^(-i-3);  q_eq (reference norm) = {q_eq:.6f};"
      f"  q_eq (closure norm, rho^2 = phi^2) = {q_solver_closure:.6f}")
print(f"  {'i':>3} {'q_i':>10} {'|q_i-q_eq(ref)|':>16} {'|q_i-q_eq(clos)|':>16}")
for i in range(0, 6):
    qi = 1.0 - PHI ** (-i - 3)
    print(f"  {i:>3} {qi:>10.6f} {abs(qi - q_eq):>16.6f} {abs(qi - q_solver_closure):>16.6f}")
# crossover rung where 1 - q_i = 1 - q_eq  <=>  phi^(-i-3) = 1 - q_eq
for label, qe in (("reference", q_eq), ("closure", q_solver_closure)):
    i_star = math.log(1.0 / (1.0 - qe)) / math.log(PHI) - 3.0
    print(f"  crossover rung i* (profile = canonical value, {label} norm): {i_star:+.4f}")

# ---------------------------------------------------------------------------
print()
print("─ 6. Exact ties between forms (1) and (2) ─")
print()
print(f"  delta = 3 anchor:  1 - q_0 = phi^-3 = {PHI_M3:.12f}")
print(f"  (pi/rho)_eq        = (phi-1)/(phi+1) = {(PHI - 1.0) / (PHI + 1.0):.12f}")
print(f"  equality: {abs(PHI_M3 - (PHI - 1.0) / (PHI + 1.0)) < 1e-15}")
print(f"  per-rung step: 1 - q_{'{i+1}'} = phi^-1 (1 - q_i): "
      f"{PHI ** (-1) * PHI ** (-3):.12f} == phi^-4 = {PHI ** -4:.12f}")
print()
print("=" * 78)
