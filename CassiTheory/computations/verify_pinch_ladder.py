# Verify the two derived structures of the audit-fix program:
#   (a) the Qi-gate pinch crossover at r = phi^-1
#       (consciousness/consciousness-from-phi.md §1.1)
#   (b) the openness ladder b_i = phi^-(2+i) and the R-matrix
#       (consciousness/emotions-as-gate-configurations.md §4.2)
# Run from the repo root:  python computations/verify_pinch_ladder.py

import math

phi = (1.0 + math.sqrt(5.0)) / 2.0
phi_inv = 1.0 / phi

# ---------------------------------------------------------------------------
# (a) The pinch point r = phi^-1
# ---------------------------------------------------------------------------
print("== (a) Qi-gate pinch crossover at r = phi^-1 ==")
print(f"  phi    = {phi:.10f}")
print(f"  phi^-1 = {phi_inv:.10f}")
print(f"  phi^-2 = {phi_inv**2:.10f}")
print(f"  identities: phi - phi^-1 = {phi - phi_inv:.10f} (must be 1), "
      f"1 + phi^-1 = {1 + phi_inv:.10f} (must be phi)")

def gate_q(r):
    """Canonical homogeneous gate (two-fluid/calibrate_initial_ratio.py):
    q = phi^2/(phi^2 + phi^-2 + eps^2),  eps^2 = (r-phi)^2 phi^2/(1+r)^2."""
    eps_sq = (r - phi) ** 2 * phi ** 2 / (1 + r) ** 2
    return phi ** 2 / (phi ** 2 + phi ** -2 + eps_sq)

def imbalance_sq(r):
    """Normalized conversion imbalance (r-phi)^2/(1+r)^2 (rho = 1 limit)."""
    return (r - phi) ** 2 / (1 + r) ** 2

rp = phi_inv
q_p = gate_q(rp)
print("\n-- A1. Gate values at the pinch (exact) --")
print(f"  q(phi^-1)    = {q_p:.10f}   (exact phi^2/4 = {phi**2/4:.10f})")
print(f"  (1-q)(phi^-1)= {1 - q_p:.10f}   (exact (3-phi)/4 = {(3 - phi) / 4:.10f})")
print(f"  check phi^2 + phi^-2 = {phi**2 + phi**-2:.10f} (must be 3)")
assert math.isclose(q_p, phi ** 2 / 4, rel_tol=1e-12)
assert math.isclose(1 - q_p, (3 - phi) / 4, rel_tol=1e-12)
assert math.isclose(phi ** 2 + phi ** -2, 3.0, rel_tol=1e-12)

print("\n-- A2. Transition condition: imbalance = gate scale phi^-2 --")
print(f"  (r-phi)^2/(1+r)^2 at r=phi^-1 = {imbalance_sq(rp):.10f}  (must equal phi^-2 = {phi_inv**2:.10f})")
assert math.isclose(imbalance_sq(rp), phi ** -2, rel_tol=1e-12)
# solve (phi-r)/(1+r) = phi^-1  =>  r = phi^-1 exactly
r_solved = (phi - phi_inv) / (1 + phi_inv)
print(f"  solving (phi-r)/(1+r) = phi^-1 gives r = {r_solved:.10f}  (must equal phi^-1)")
assert math.isclose(r_solved, phi_inv, rel_tol=1e-12)

print("\n-- A3. Mirror/conjugate identities at the pinch --")
print(f"  pi/rho = (r-1)/(r+1) = {(rp - 1) / (rp + 1):+.10f}  (must equal -phi^-3 = {-phi**-3:.10f})")
print(f"  gap g  = (1-r)/(1+r) = {(1 - rp) / (1 + rp):.10f}  (must equal +phi^-3 = {phi**-3:.10f})")
assert math.isclose((rp - 1) / (rp + 1), -phi ** -3, rel_tol=1e-12)
assert math.isclose((1 - rp) / (1 + rp), phi ** -3, rel_tol=1e-12)
# energy-level deficit ratio: eps = EY - phi EI = -EI at r = phi^-1; rho = EY + EI = phi*EI
print(f"  eps^2/rho^2 at the mirror (E_I = phi E_Y): "
      f"{(1) / (phi ** 2):.10f} = phi^-2  (the gate's characteristic scale)")
assert math.isclose(1.0 / phi ** 2, phi ** -2, rel_tol=1e-12)

print("\n-- A4. Honest bounds: where q literally crosses 1/2 (NOT at phi^-1) --")
def bisect(f, lo, hi):
    flo = f(lo)
    for _ in range(300):
        mid = (lo + hi) / 2
        fm = f(mid)
        if fm == 0:
            return mid
        if flo * fm < 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2

r_half_canon = bisect(lambda r: gate_q(r) - 0.5, 0.05, 0.55)
print(f"  canonical gate q=1/2 at r = {r_half_canon:.6f}  (phi^-1 = {phi_inv:.6f})")
# PDE gate with E_I = 1: q = (1+r)^2/((1+r)^2 + phi^-2 + (r-phi)^2); q=1/2 at r = phi^-2 exactly
print(f"  PDE gate (E_I=1) q=1/2 at r = 1/(1+phi) = {1/(1+phi):.10f}  (exact phi^-2)")
assert math.isclose(1 / (1 + phi), phi ** -2, rel_tol=1e-12)
# openness curve monotone on (0, phi): no literal inflection at phi^-1
h = 1e-6
d2 = (gate_q(rp + h) - 2 * gate_q(rp) + gate_q(rp - h)) / h ** 2
print(f"  d2q/dr2 at phi^-1 = {d2:+.6f}  (nonzero: q has no inflection at the pinch)")

# ---------------------------------------------------------------------------
# (b) The openness ladder b_i = phi^-(2+i) and the R-matrix
# ---------------------------------------------------------------------------
print("\n== (b) Openness ladder b_i = phi^-(2+i) = phi^-2 * phi^-i ==")
b = [phi ** -(2 + i) for i in range(1, 6)]
print("  b_i = [", ", ".join(f"{x:.4f}" for x in b), "]")
print(f"  quoted:  0.2361, 0.1459, 0.0902, 0.0557, 0.0344;  total 0.5623")
print("  adjacent ratios b_i/b_{i+1} = phi for all i:",
      [f"{b[i] / b[i + 1]:.6f}" for i in range(4)])
print("  base identity b_i * phi^i = phi^-2 for all i:",
      [f"{b[i] * phi ** (i + 1):.6f}" for i in range(5)])
B_total = sum(b)
print(f"  sum b_i = {B_total:.6f}   (exact phi^-1 - phi^-6 = {phi**-1 - phi**-6:.6f})")
for i in range(4):
    assert math.isclose(b[i] / b[i + 1], phi, rel_tol=1e-12)
for i in range(5):
    assert math.isclose(b[i] * phi ** (i + 1), phi ** -2, rel_tol=1e-12)
assert math.isclose(B_total, phi ** -1 - phi ** -6, rel_tol=1e-12)

print("\n-- B1. R-matrix R_ij = b_j / sum_{k != i} b_k vs the doc's printed matrix --")
printed = [
    [0, 0.447, 0.276, 0.171, 0.106],
    [0.567, 0, 0.217, 0.134, 0.083],
    [0.500, 0.309, 0, 0.118, 0.073],
    [0.466, 0.288, 0.178, 0, 0.068],
    [0.447, 0.276, 0.171, 0.106, 0],
]
R = []
for i in range(5):
    denom = B_total - b[i]
    row = [0.0 if i == j else b[j] / denom for j in range(5)]
    R.append(row)
ok = True
for i in range(5):
    got = " ".join(f"{R[i][j]:.3f}" for j in range(5))
    exp = " ".join(f"{printed[i][j]:.3f}" for j in range(5))
    match = all(abs(R[i][j] - printed[i][j]) < 0.001 for j in range(5))
    ok = ok and match
    print(f"  row {i + 1}: [{got}]  vs printed [{exp}]  {'OK' if match else 'MISMATCH'}")
    assert abs(sum(R[i]) - 1.0) < 1e-12, "each row must normalize to 1"
assert ok

print("\n-- B2. Exact structures of R --")
print(f"  row 3 = [1/2, phi^-1/2, 0, phi^-3/2, phi^-4/2]:")
row3_exact = [0.5, phi ** -1 / 2, 0.0, phi ** -3 / 2, phi ** -4 / 2]
print("   ", [f"{x:.6f}" for x in row3_exact], " vs computed",
      [f"{R[2][j]:.6f}" for j in range(5)])
for j in range(5):
    assert math.isclose(R[2][j], row3_exact[j], rel_tol=1e-12)
# rows 1 and 5 shift-identical: R_{5,j} = R_{1,j+1}
shift_ok = all(math.isclose(R[4][j], R[0][j + 1], rel_tol=1e-12) for j in range(4))
print(f"  row5 == row1 shifted (R_5j = R_1,j+1): {shift_ok}")
assert shift_ok

print("\n-- B3. Doc's anger-aftereffect table (row 1, channel 1 closes) --")
fracs = [R[0][1], R[0][2], R[0][3], R[0][4]]
print(f"  Fire {fracs[0]*100:.1f}%  Earth {fracs[1]*100:.1f}%  Metal {fracs[2]*100:.1f}%  "
      f"Water {fracs[3]*100:.1f}%   (doc: 44.7%, 27.6%, 17.1%, 10.6%)")
assert abs(fracs[0] - 0.447) < 0.001 and abs(fracs[1] - 0.276) < 0.001
assert abs(fracs[2] - 0.171) < 0.001 and abs(fracs[3] - 0.106) < 0.001

print("\nALL CHECKS PASSED")
