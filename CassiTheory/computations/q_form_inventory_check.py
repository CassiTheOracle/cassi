#!/usr/bin/env python3
"""
q-form inventory check: canonical density/composition dependence and
reduction relations among the active q forms.
========================================================================

Forms (`foundations/cassi-theory-reference.md` sec. 2.4 + inventory note;
`foundations/unified-lagrangian.md` sec. 1.5/3.2):

  (1) canonical     q = rho^2 / (rho^2 + phi^-2 + eps^2), with
                    rho = E_Y + E_I, pi = E_Y - E_I, s = pi/rho, and
                    eps = E_Y - phi E_I.  For rho > 0 and E_Y,E_I >= 0,
                    -1 <= s <= 1 and
                    q(rho,s) = [1 + ((phi^2 s - phi^-1)/2)^2
                                  + phi^-2/rho^2]^-1.
                    Thus q depends on both density scale and composition;
                    q -> 0 is only the dilute rho -> 0 asymptote.
  (2) per-rung      q_i = 1 - phi^(-i-delta),              delta = 3
  (3) equilibrium   q = M_Qi/(M_Qi + phi^-2), M_Qi = rho^2 =
                    (Psi_0^2 + Psi_1^2)^2 (field power)
  (4) branch        q_alpha ~ |psi_alpha|^2  (inactive branch form;
                    quantum-measurement-derivation.md sec. 4.5; no consumers remain)

Verified here:
  1. The canonical fixed-point composition is s_eq = phi^-3, equivalently
     eps = 0. The solver reference E_Y = 1, E_I = phi^-1 has rho^2 = phi^2
     and q_ref ~ 0.872678. A separate low-density comparison rho^2 = phi^-6
     gives q ~ 0.127322; it is not a fixed-point density.
  2. The canonical q(rho,s) relation and feasible endpoint range for
     E_Y,E_I >= 0 are checked at finite density; q is not an independent
     free variable once rho and s are specified.
  3. The current equilibrium form q = M_Qi/(M_Qi + phi^-2), M_Qi = rho^2,
     agrees with the canonical q at eps = 0; an independently supplied eps^2
     is the only discrepancy away from that aligned state.
  4. E = M_Qi^2/(M_Qi + phi^-2) is the coherent field power
     E = q*M_Qi = rho^4/(rho^2+phi^-2) at the solver reference.
  5. Form (2) is a per-rung profile, not a universal equilibrium value.
     Its crossover with q_ref and with the low-density comparison is reported
     separately. The delta = 3 anchor 1 - q_0 = phi^-3 = (pi/rho)_eq
     and the per-rung step remain exact.

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


def canonical_q(rho2, s):
    """Canonical q for density power rho^2 and composition s=pi/rho."""
    if rho2 <= 0.0:
        raise ValueError("rho^2 must be positive for a canonical state")
    if not -1.0 <= s <= 1.0:
        raise ValueError("nonnegative E_Y,E_I require -1 <= s <= 1")
    imbalance_over_rho = (PHI2 * s - PHI ** -1) / 2.0
    return 1.0 / (1.0 + imbalance_over_rho ** 2 + PHI_M2 / rho2)

print("=" * 78)
print("  q-FORM INVENTORY: EQUIVALENCE / REDUCTION RELATIONS")
print("=" * 78)

# ---------------------------------------------------------------------------
print()
print("─ 1. Canonical reference composition and density normalization ─")
print()
print("  Canonical fixed point: aligned composition eps = 0, not a fixed density.")
s_eq = PHI_M3
rho2_ref = PHI2
q_ref = canonical_q(rho2_ref, s_eq)
rho2_low = PHI ** -6
q_low = canonical_q(rho2_low, s_eq)
print(f"  s_eq = (pi/rho)_eq = phi^-3 = {s_eq:.12f}")
print(f"  solver reference E_Y=1, E_I=phi^-1: rho^2 = phi^2 = {rho2_ref:.12f}")
print(f"  canonical q at solver reference = {q_ref:.12f}")
print(f"  separate low-density comparison rho^2 = phi^-6 = {rho2_low:.12f}")
print(f"  canonical q at low-density comparison = {q_low:.12f}")
print("  rho2_low = s_eq^2 is a scale coincidence, not a fixed-point condition.")
print(f"  complement relation for these chosen scales: q_low = 1-q_ref -> "
      f"{abs(q_low - (1.0 - q_ref)):.3e} residual")
print()
print("─ 1b. Canonical density/composition dependence and feasible q range ─")
print()
print("  Define rho = E_Y + E_I > 0, pi = E_Y - E_I, s = pi/rho.")
print("  Nonnegative E_Y,E_I imply -1 <= s <= 1; q is then fixed by rho^2 and s.")
print("  q(rho,s) = [1 + ((phi^2 s - phi^-1)/2)^2 + phi^-2/rho^2]^-1")
for label, r2 in (
    ("low-density comparison", rho2_low),
    ("unit-density comparison", 1.0),
    ("solver reference", rho2_ref),
    ("high-density comparison", PHI ** 6),
):
    q_yin = canonical_q(r2, -1.0)
    q_yang = canonical_q(r2, 1.0)
    q_align = canonical_q(r2, s_eq)
    assert 0.0 < q_yin <= q_yang <= q_align < 1.0
    print(f"  {label:>23}: rho^2={r2:>9.5f}, q(Yin,s=-1)={q_yin:.6f},"
          f" q(Yang,s=+1)={q_yang:.6f}, q(aligned)={q_align:.6f}")
print("  At finite positive density, canonical q is strictly between 0 and 1;")
print("  q -> 0 only as rho -> 0, while q -> 1 requires aligned composition")
print("  and rho -> infinity.")
# ---------------------------------------------------------------------------
print()
print("─ 2. Current equilibrium reduction: M_Qi = rho^2 = (Psi_0^2 + Psi_1^2)^2 ─")
print()
M_Qi = rho2_ref
q_mqi = M_Qi / (M_Qi + PHI_M2)
print(f"  M_Qi = rho^2 at solver reference = {M_Qi:.16f}")
print(f"  q(M_Qi) @ eps = 0                = {q_mqi:.16f}")
print(f"  canonical q_ref                 = {q_ref:.16f}")
print(f"  residual                          = {abs(q_mqi - q_ref):.3e}  (exact identity)")
print()
print("  Independent-eps^2 sweep at fixed solver-reference rho^2:")
print("  canonical density states instead obey eps^2 = rho^2*((phi^2*s - phi^-1)/2)^2;")
print("  the values below diagnose the equilibrium reduction with eps supplied independently.")
print("  relative residual (q(M_Qi) - q1)/q1 = eps^2/(rho^2 + phi^-2):")
for eps2 in (PHI ** -4, PHI_M2, 0.1, 1.0):
    q1 = rho2_ref / (rho2_ref + PHI_M2 + eps2)
    rel = (q_mqi - q1) / q1
    print(f"    eps^2 = {eps2:>8.4f} : q1 = {q1:.6f}, q(M_Qi) = {q_mqi:.6f}, "
          f"rel.resid = {rel:+.6f} ({rel * 100:+.2f}%)")

# ---------------------------------------------------------------------------
print()
print("─ 3. Qi coherent energy E_pow = M_Qi^2/(M_Qi + phi^-2) ─")
print()
E_pow_ref = M_Qi ** 2 / (M_Qi + PHI_M2)
print(f"  E_pow = M_Qi^2/(M_Qi + phi^-2) @ solver reference = {E_pow_ref:.6e}")
print(f"  E_pow = q*M_Qi                       @ solver reference = {q_ref * M_Qi:.6e}")
print(f"  identity |E_pow - q*M_Qi| = {abs(E_pow_ref - q_ref * M_Qi):.3e}  (exact)")

# ---------------------------------------------------------------------------
print()
print("─ 4. Form (2) per-rung profile versus named density comparisons ─")
print()
print(f"  q_i = 1 - phi^(-i-3); q_ref (solver reference) = {q_ref:.6f};"
      f" q_low (separate low-density comparison) = {q_low:.6f}")
print(f"  {'i':>3} {'q_i':>10} {'|q_i-q_ref|':>14} {'|q_i-q_low|':>14}")
for i in range(0, 6):
    qi = 1.0 - PHI ** (-i - 3)
    print(f"  {i:>3} {qi:>10.6f} {abs(qi - q_ref):>14.6f} {abs(qi - q_low):>14.6f}")
for label, qe in (("solver reference", q_ref), ("low-density comparison", q_low)):
    i_star = math.log(1.0 / (1.0 - qe)) / math.log(PHI) - 3.0
    print(f"  crossover rung i* (profile = {label}): {i_star:+.4f}")


# ---------------------------------------------------------------------------
print()
print("─ 5. Exact ties between forms (1) and (2) ─")
print()
print(f"  delta = 3 anchor:  1 - q_0 = phi^-3 = {PHI_M3:.12f}")
print(f"  (pi/rho)_eq        = (phi-1)/(phi+1) = {(PHI - 1.0) / (PHI + 1.0):.12f}")
print(f"  equality: {abs(PHI_M3 - (PHI - 1.0) / (PHI + 1.0)) < 1e-15}")
print(f"  per-rung step: 1 - q_{'{i+1}'} = phi^-1 (1 - q_i): "
      f"{PHI ** (-1) * PHI ** (-3):.12f} == phi^-4 = {PHI ** -4:.12f}")

# ---------------------------------------------------------------------------
print()
print("─ 6. Canonical finite-density limits ─")
print()
print("  Canonical q is positive for every finite rho^2 > 0 and q -> 0 only")
print("  in the dilute rho -> 0 asymptote; q -> 1 requires aligned composition")
print("  and rho -> infinity.")
print()
print("=" * 78)
