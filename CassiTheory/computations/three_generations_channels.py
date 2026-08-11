#!/usr/bin/env python3
"""
Three Generations: Channel Decomposition of the Rung Propagation
================================================================

Numerical verification for `foundations/three-generations.md` §2.3.

The counting rule N_gen = 3 is built from three exact or stated pieces:

1. Rung decomposition (exact identity):   phi^n = phi^(n-1) + phi^(n-2)
   -- two terms on the right, i.e. the two predecessor channels (n-1, n-2).
2. Solution space of the recurrence (exact): the second-order recurrence
   a_n = a_{n-1} + a_{n-2} has characteristic roots phi and -1/phi, so its
   solution space is spanned by {phi^n, (-1/phi)^n} -- dimension 2, one
   independent solution per predecessor rung. Initial data at rung n are
   exactly the two predecessors (n-1, n-2).
3. Propagation-channel postulate (Inputs box): a propagating mode at rung n
   opens one channel per term of the rung decomposition PLUS the direct rung
   itself (self-channel). Count: 2 + 1 = 3 channels.

Three-channel spread predictions checked below:
- Charged leptons:  m_mu/m_e ~ phi^11 (obs 207, +4.0%), m_tau/m_mu ~ phi^6
  (obs 16.8, -6.4%) -- both within 10%.
- Down-type:        phi^5 = 11.09 vs obs 20.4 / 43.5 (factor ~2-4 gap, as documented).
- Up-type:          phi^7 = 29.03, phi^8 = 46.98 vs obs 577 / 136 (factor ~20 / ~3 gap).
- Neutrinos (seesaw y^2 amplification): m2/m1 = phi^2 = 2.618,
  m3/m2 = phi^3.5 = 5.388; Delta m^2_31 / Delta m^2_21 =
  (phi^11 - 1)/(phi^4 - 1) = 33.823 vs observed 33.89 (0.2% residual).
  Note: the offsets are Mapped (fitted -- ledger row 483), so this match is
  by construction, not an independent prediction.

Usage: python computations/three_generations_channels.py
"""
import math

phi = (1 + math.sqrt(5)) / 2

print("=" * 76)
print("1. FIBONACCI DECOMPOSITION  phi^n = phi^(n-1) + phi^(n-2)")
print("   (exact for every real n:  phi^(n-2)(phi^2 - phi - 1) = 0)")
for n in (-3, 0, 1, 2, 7, 26, 80, 107, 292):
    lhs, rhs = phi ** n, phi ** (n - 1) + phi ** (n - 2)
    rel = abs(lhs - rhs) / lhs
    print(f"   n={n:>4}: phi^n={lhs:.10e}   phi^(n-1)+phi^(n-2)={rhs:.10e}"
          f"   |rel diff|={rel:.2e}")
print()
print("2. SOLUTION SPACE OF a_n = a_{n-1} + a_{n-2}  (order 2 -> dim 2)")
print(f"   characteristic roots: phi = {phi:.12f},  -1/phi = {-1/phi:.12f}")
print(f"   phi^2 - phi - 1              = {phi**2 - phi - 1:.3e}")
print(f"   (-1/phi)^2 - (-1/phi) - 1    = {(1/phi)**2 + (1/phi) - 1:.3e}")
print("   -> two independent solutions {phi^n, (-1/phi)^n}; the two")
print("      degrees of freedom are the two predecessor rungs (n-1, n-2).")
print()
print("3. CHANNEL COUNT  N_gen = 2 decomposition terms + 1 direct rung = 3")
print("   (propagation-channel postulate -- Inputs box)")
print()
print("4. THREE-CHANNEL SPREAD PREDICTIONS")
for k in (5, 6, 7, 8, 11):
    print(f"   phi^{k:<2} = {phi**k:9.5f}")
print(f"   log_phi(207)  = {math.log(207) / math.log(phi):.3f}   (m_mu/m_e, obs 207)")
print(f"   log_phi(16.8) = {math.log(16.8) / math.log(phi):.3f}   (m_tau/m_mu, obs 16.8)")
print(f"   207/phi^11    = {207 / phi**11:.4f}  (+4.0% above phi^11)")
print(f"   16.8/phi^6    = {16.8 / phi**6:.4f}  (-6.4% below phi^6)")
print(f"   m_c/m_u obs 577 vs phi^7 = {phi**7:.2f} (x{577 / phi**7:.1f})")
print(f"   m_t/m_c obs 136 vs phi^8 = {phi**8:.2f} (x{136 / phi**8:.1f})")
print(f"   m_s/m_d obs 20.4 vs phi^5 = {phi**5:.2f} (x{20.4 / phi**5:.1f})")
print(f"   m_b/m_s obs 43.5 vs phi^5 = {phi**5:.2f} (x{43.5 / phi**5:.1f})")
print()
print("5. NEUTRINOS (seesaw y^2: mass ratio = phi^(2*Delta))")
r21, r32 = phi ** 2, phi ** 3.5
print(f"   m2/m1 = phi^2    = {r21:.4f}   (pinned spectrum 0.00931/0.00356 = "
      f"{0.00931 / 0.00356:.4f})")
print(f"   m3/m2 = phi^3.5  = {r32:.4f}   (pinned spectrum 0.05019/0.00931 = "
      f"{0.05019 / 0.00931:.4f})")
print(f"   m3/m1 = phi^5.5  = {phi**5.5:.4f}   (pinned spectrum 0.05019/0.00356 = "
      f"{0.05019 / 0.00356:.4f})")
m1 = 0.00356
print(f"   Delta m^2_21/m1^2 + 1 = {7.41e-5 / m1**2 + 1:.4f} -> ratio "
      f"{math.sqrt(7.41e-5 / m1**2 + 1):.4f} (vs phi^2)")
print(f"   Delta m^2_31/m1^2 + 1 = {2.511e-3 / m1**2 + 1:.4f} -> ratio "
      f"{math.sqrt(2.511e-3 / m1**2 + 1):.4f} (vs phi^5.5)")
ratio = (phi ** 11 - 1) / (phi ** 4 - 1)
print(f"   Delta m^2_31 / Delta m^2_21 = (phi^11 - 1)/(phi^4 - 1) = "
      f"{ratio:.3f} vs observed 33.89 ({abs(ratio - 33.89) / 33.89 * 100:.2f}% residual)")
print("   [offsets Delta_1=1.00, Delta_2=1.75 are Mapped -- fitted to this")
print("    ratio; ledger row 483. The 0.2% residual is grid quantization.]")
print("=" * 76)
