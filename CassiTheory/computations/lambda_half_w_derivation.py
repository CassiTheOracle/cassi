#!/usr/bin/env python3
"""
Conditional Lambda=0.1 Audit: Doublet and Per-Cycle Bookkeeping
================================================================

Audits the fixed solver normalization used in
foundations/wu-xing-derivation.md (sec 7): lambda = 0.1.  The arithmetic
identity 1/(2*5) = 0.1 is retained as conditional bookkeeping for continuity,
but this script does not derive a dynamical rate from w = 5.
The numerical checks are conditional on lambda = 0.1:

1.  The retained 1/(2*w) arithmetic split agrees with the fixed audit input
    0.1; this is an arithmetic consistency check, not a rate derivation.
2.  r_0 = phi^-5/(2 - phi^-5) = 0.0472 (the document's w-conditioned
    primordial ratio).
3.  The attractor-approach time constant: the two-field conversion ODE in
    the code form (two-fluid/cassi_two_fluid_3d_gpu.py: conv =
    -lam*(ey - phi*ei), gated by (1-q)) relaxes the imbalance
    delta = ey - phi*ei as e^{-gamma t} with gamma =
    lam*(1-q0)*(1+phi) = lam/3 at the attractor gate value
    (1-q0) = phi^-2/3 => gamma = 1/30, tau = 30 when lambda = 0.1
    (foundations/spiral-dynamics.md sec 2.3).  Integrated ODE vs analytic.
4.  The phi-algebra identity (1-q0)*(1+phi) = (phi^-2/3)*(phi^2) = 1/3.
5.  Non-resonance: the selected value 0.1 is NOT a phi-power nor an
    integer combination A + B*phi in the tested finite ranges.
6.  Doublet symmetry: the two-field conversion conserves total mass exactly
    while the channels carry equal-and-opposite conversion flux.  This
    conservation identity holds for any lambda and does not calibrate it.
7.  Consequences quoted in the docs reproduce conditionally at lambda = 0.1:
    wake correction 2*lam*(1-q)/w^2 ~ 0.25% (wake-geometry.md),
    kinetic/conversion ratio lam*(1-q)/(c^2 k^2) ~ 2.5e-3
    (cascade-suppression-formula.md).

Run:  python computations/lambda_half_w_derivation.py
"""

import math

PHI = (1 + math.sqrt(5)) / 2
W = 5
LAMBDA_INPUT = 0.1


def main():
    print("═══ Conditional Lambda=0.1 Audit (wu-xing-derivation.md §7) ═══")
    print(f"  phi = {PHI:.15f},  w = {W},  lambda input = {LAMBDA_INPUT}")

    # ── 1. Retained 1/(2w) arithmetic bookkeeping, not a rate derivation ──
    print("\n── 1. Retained 1/(2w) arithmetic (conditional bookkeeping) ──")
    lam = LAMBDA_INPUT
    half = 1.0 / 2.0
    per_vertex = 1.0 / W
    bookkeeping = half * per_vertex
    print(f"  1/(2w)      = 1/{2 * W} = {bookkeeping}")
    print(f"  (1/2)(1/w)  = {half} * {per_vertex} = {bookkeeping}")
    assert lam == 0.1 and bookkeeping == lam
    print("  → fixed lambda input = 0.1; retained arithmetic agrees (no rate derivation)")

    # ── 2. r_0 = phi^-5/(2 - phi^-5) ──
    print("\n── 2. r_0 (primordial Yang/Yin ratio, §5.2) ──")
    g = 1.0 - PHI ** (-W)
    r0 = (1.0 - g) / (1.0 + g)
    r0b = PHI ** (-W) / (2.0 - PHI ** (-W))
    print(f"  gap g      = 1 - phi^-5 = {g:.6f}")
    print(f"  r_0        = phi^-5/(2 - phi^-5) = {r0b:.6f}")
    assert abs(r0 - r0b) < 1e-12 and abs(r0 - 0.04721) < 2e-4
    print("  → r_0 = 0.0472 ✓ (w-conditioned value used with lambda = 0.1)")

    # ── 3. Attractor-approach time constant, conditional on lambda = 0.1 ──
    print("\n── 3. Attractor-approach rate conditional on lambda = 0.1 ──")
    # Code-form ODE (gated): d ey = -lam*(1-q)*(ey - phi*ei), d ei = +lam*(1-q)*(ey - phi*ei)
    # Gate at the attractor: (1-q0) = phi^-2/3.
    q_open = PHI ** (-2) / 3.0
    gamma_an = lam * q_open * (1.0 + PHI)
    gamma_ungated = lam * (1.0 + PHI)
    print(f"  (1-q0) = phi^-2/3 = {q_open:.6f}")
    print(f"  gamma (gated, at attractor) = lam*(1-q0)*(1+phi) = {gamma_an:.6f}  (= lam/3 = 1/30)")
    print(f"  gamma (ungated)             = lam*(1+phi) = lam*phi^2 = {gamma_ungated:.6f}")
    print(f"  tau (gated) = 1/gamma = {1.0 / gamma_an:.4f}  (docs: radial relaxation rate gamma = lam/3)")
    assert abs(gamma_an - lam / 3.0) < 1e-12 and abs(1.0 / gamma_an - 30.0) < 1e-9

    # Numeric ODE integration of the imbalance decay vs the analytic e^{-gamma t}.
    dt = 1e-3
    n = 4000  # t in [0, 4]
    ey, ei = 1.5, 1.0  # delta0 = ey - phi*ei = 1.5 - 1.618
    d0 = ey - PHI * ei
    t_best, rel = 0.0, 0.0
    for i in range(n):
        t = i * dt
        delta = ey - PHI * ei
        conv = -lam * q_open * delta
        ey += dt * conv
        ei += dt * (-conv)
        if i == n // 2:
            t_best, rel = t, abs(delta / (d0 * math.exp(-gamma_an * t)) - 1.0)
    print(f"  ODE check (gated): |delta(t)/(delta0 e^-gamma t) - 1| at t=2: {rel:.2e} "
          f"(Euler truncation ~gamma^2 t dt/2 = {gamma_an ** 2 * 2.0 * dt / 2.0:.1e})")
    assert rel < 1e-5
    print("  → integrated two-field ODE reproduces e^{-(lam/3)t} for the fixed lambda input")

    # ── 4. phi-algebra identity (1-q0)(1+phi) = 1/3 ──
    print("\n── 4. phi-algebra: (1-q0)(1+phi) = (phi^-2/3)*phi^2 = 1/3 ──")
    lhs = q_open * (1.0 + PHI)
    print(f"  phi^-2*(1+phi) = {PHI ** -2 * (1.0 + PHI):.15f}  (= 1 exact, since 1+phi = phi^2)")
    assert abs(PHI ** -2 * (1.0 + PHI) - 1.0) < 1e-12
    print("  → gamma = lam*(1/3): the 1/3 is exact phi-algebra, not an approximation")

    # ── 5. Non-resonance of the selected normalization ──
    print("\n── 5. Non-resonance of selected lambda = 0.1 ──")
    pow_hits = [k for k in range(-20, 21) if abs(PHI ** k - lam) < 1e-9]
    comb_hits = [(a, b) for a in range(-1000, 1001) for b in range(-1000, 1001)
                 if abs(a + b * PHI - lam) < 1e-9]
    print(f"  phi^k = 0.1 for integer k in [-20, 20]: {pow_hits if pow_hits else 'none'}")
    print(f"  A + B*phi = 0.1 with |A|,|B| <= 1000: {comb_hits if comb_hits else 'none'}")
    assert not pow_hits and not comb_hits
    print("  → selected lambda = 1/10 is rational and non-resonant in the tested ranges")

    # ── 6. Doublet symmetry: equal-and-opposite flux, exact mass conservation ──
    print("\n── 6. Doublet symmetry of the conversion term ──")
    ey, ei = 1.5, 1.0
    conv = -lam * (ey - PHI * ei)
    d_ey, d_ei = conv, -conv
    print(f"  d(ey)/dt = {d_ey:+.6f},  d(ei)/dt = {d_ei:+.6f}  (equal and opposite)")
    print(f"  d(ey + ei)/dt = {d_ey + d_ei:+.2e}  (mass exactly conserved)")
    assert abs(d_ey + d_ei) < 1e-14
    print("  → equal-and-opposite redistribution conserves mass for the selected lambda;")
    print("    this identity does not calibrate the dynamical coefficient")

    # ── 7. Conditional lambda = 0.1 consequences quoted in the docs ──
    print("\n── 7. Consequences conditional on lambda = 0.1 ──")
    # wake-geometry.md: Lambda_eps/Lambda_Y = 1/sqrt(1 - 2*lam*(1-q)/w^2), w^2 = c^2 k^2 = 4 pi^2
    wsq = 4.0 * math.pi ** 2
    corr = 2.0 * lam / wsq  # (1-q) = 1 upper bound
    ratio = 1.0 / math.sqrt(1.0 - corr)
    print(f"  wake correction 2*lam/w^2 = {corr:.5f}  → Lambda_eps/Lambda_Y = {ratio:.6f} "
          f"(doc: 1.003, a 0.25% correction, not a factor phi)")
    assert abs(ratio - 1.003) < 2e-3
    # cascade-suppression-formula.md: lam*(1-q)/(c^2 k^2) ~ 2.5e-3
    kin_conv = lam / wsq
    print(f"  kinetic/conversion ratio lam/(c^2 k^2) = {kin_conv:.3e} (doc: 2.5e-3)")
    assert abs(kin_conv - 2.5e-3) < 1e-4

    print("\n→ ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
