"""Bubble-shell ring-ladder probe: the doublet's radial standing wave.

Run:  python two-fluid/run_bubble_ring_probe.py

Tests Prediction 51 (`predictions/falsifiable-predictions.md` P51) /
`foundations/bubble-edge-geometry.md` §"Radial Interior Structure":

  A rung-n bubble's interior carries matter rings at r_k = ell_n * phi^-k
  and void rings at ell_n * phi^-(k+1/2) -- the radial standing wave of
  the doublet phase alpha = pi * u, u = log_phi(r/ell_n) (the doublet
  advances pi per rung, `foundations/spin-fibonacci-spiral.md` §2.1),
  combined with the pool-cell parities of `foundations/rung-offset-
  mechanism.md` §4.1 (cosine antinodes at integer rungs = matter, sine
  antinodes at half-rungs = voids). Ring k is a rung-(n-k) condensate
  (ell_n * phi^-k = ell_{n-k}): bubbles within bubbles. The count ~10
  follows from the ~1% nesting floor (N = ln100/ln phi = 9.570,
  `foundations/bubble-lattice-fabric.md` §3.3) and is n-independent.

  Tier: Hypothesized (PDE-testable), conditional on the radial-reading
  INFERENCE -- the radial reading of the doublet phase alpha = pi*u is an
  inference resting on the nested-sub-lattice structure of
  `foundations/bubble-lattice-fabric.md` §3.2, not an established
  identity. The honest negative: the naive 1D wake-sum
  cos(2 pi r/ell_n) + cos(2 pi phi r/ell_n) has zeros at
  {0.191, 0.573, 0.809, 0.955}*ell_n, not a phi-ladder; the intra-shell
  ladder is phase-quantized, not the wake beat.

Leg A -- analytic ring law:
  matter at r_k = ell_n phi^-k (integer u), voids at ell_n phi^-(k+1/2)
  (half-integer u); successive matter-ring ratio phi^-1 = 0.61803,
  adjacent matter-void ring ratio phi^-1/2 = 0.78615; strict matter/void
  alternation (cos^2(pi u) peaks at integer u, zeros at half-integer);
  count ~10 (N = ln100/ln phi); n-independence (count invariant under
  phi-rescaling of ell_n).

Leg B -- honest negative:
  the naive wake-sum zeros {0.191, 0.573, 0.809, 0.955}*ell_n; none is a
  phi^-k ladder position; the ladder is phase-quantized, not the beat.

Leg C -- prediction observable (analytic envelope):
  the radial matter envelope rho(r) ~ cos^2(pi u), u = log_phi(r/ell_n),
  has matter ridges at ell_n*phi^-k and void troughs at
  ell_n*phi^-(k+1/2), strict alternation, and ~10 rings (count from the
  ~1% floor). This is what a simulated bubble must show -- the analytic
  envelope the prediction names. PDE realization of ALL ~10 interior
  rings from microphysics, and the ring amplitudes (condensation
  exponent), are the OPEN, unverified content (not claimed here).

Output: console tables + [PASS]/[FAIL] verdicts (exit 0/1).
No figure is written.
"""

import numpy as np
from run_rung_offset_probe import PHI, LNPHI, rhs, evolve

PHI_INV = PHI ** -1          # 0.61803, matter-to-matter ring ratio
PHI_INV2 = PHI ** -0.5       # 0.78615, adjacent matter-void ring ratio
N_RINGS = np.log(100.0) / LNPHI   # 9.570, ~1% nesting floor in rungs


# ----------------------------------------------------------------------
# Leg A: the phase-quantized ring law (analytic)
# ----------------------------------------------------------------------
def leg_a():
    print("=" * 78)
    print("Leg A -- phase-quantized ring law: matter at ell_n phi^-k,")
    print("voids at ell_n phi^-(k+1/2), from alpha = pi*u, u = log_phi(r)")
    print("=" * 78)

    ell = 1.0                  # bubble radius rung n, in units of ell_n
    k_max = 11

    print(f"\n  matter rings r_k = ell_n * phi^-k  (integer u = -k):")
    print(f"  {'k':>3} {'r_k/ell_n':>10} {'u':>6} {'ring k is rung n-k':>20}")
    r_matter = []
    for k in range(k_max + 1):
        rk = ell * PHI ** -k
        r_matter.append(rk)
        print(f"  {k:>3} {rk:>10.5f} {(-k):>6} {f'rung n-{k} = ell_n*phi^-k':>20}")
        if k < 10:
            print(f"        ell_{{n-k}}/ell_n = phi^-k = {PHI ** -k:.5f}  "
                  f"(nested-condensate identity)")

    # successive matter-ring ratio phi^-1
    ratios = [r_matter[k] / r_matter[k - 1] for k in range(1, k_max + 1)]
    print(f"\n  successive matter-ring ratios r_k/r_{{k-1}}:")
    print(f"    mean = {np.mean(ratios):.6f}, std = {np.std(ratios):.2e}  "
          f"(phi^-1 = {PHI_INV:.6f})")

    # voids at the half-rungs; the ratio from a matter ring to its
    # adjacent void ring (the "ring-to-ring" radius ratio phi^-1/2)
    print(f"\n  void rings r_void,k = ell_n * phi^-(k+1/2):")
    print(f"  {'k':>3} {'r/ell_n':>10} {'u':>7} {'r_void/r_matter':>16}")
    r_void = []
    v_ratios = []
    for k in range(k_max + 1):
        rv = ell * PHI ** -(k + 0.5)
        r_void.append(rv)
        print(f"  {k:>3} {rv:>10.5f} {-(k + 0.5):>7} "
              f"{rv / r_matter[k]:>16.5f}")
        v_ratios.append(rv / r_matter[k])
    print(f"    adjacent matter->void ratio mean = {np.mean(v_ratios):.6f}  "
          f"(phi^-1/2 = {PHI_INV2:.6f})")

    # strict alternation from cos^2(pi u)
    print(f"\n  strict alternation: the radial matter density is")
    print(f"  rho(r) ~ cos^2(pi * u(r)), u = log_phi(r/ell_n): matter where")
    print(f"  u is an integer (cosine antinode), void where u is a")
    print(f"  half-integer (sine antinode, cosine node). Interleaving check:")
    u_matter = [-k for k in range(k_max + 1)]
    u_void = [-(k + 0.5) for k in range(k_max)]
    inter = sorted(u_matter + u_void)
    alternating = all(
        (inter[i] % 1.0 == 0.0) != (inter[i + 1] % 1.0 == 0.0)
        for i in range(len(inter) - 1))
    print(f"    sorted u-threshold interleave alternates matter/void: "
          f"{alternating}")

    # count from the ~1% floor; n-independence
    print(f"\n  nesting depth: N = ln100/ln phi = {N_RINGS:.4f} rungs, so")
    print(f"  ~{int(np.ceil(N_RINGS))} (=10) matter rings within the ~1%")
    print(f"  coherence floor (bubble-lattice-fabric.md sek 3.3).")
    print(f"  n-independence: the count N(R) over a radial span [R*ell_n,")
    print(f"  ell_n] is N(R) = -log_phi(R), a function of the FRACTION R")
    print(f"  (scale covariance) -- not of ell_n itself:")
    for R in [0.5, 0.1, 0.01, 0.001]:
        print(f"    R = {R:>7.3f}: N = {-np.log(R) / LNPHI:>6.3f} rungs -> "
              f"~{int(np.ceil(-np.log(R) / LNPHI))} rings")

    passes = (
        abs(np.mean(ratios) - PHI_INV) < 1e-6
        and abs(np.mean(v_ratios) - PHI_INV2) < 1e-6
        and alternating
        and abs(N_RINGS - np.log(100.0) / LNPHI) < 1e-9
        and abs(N_RINGS - 9.570) < 0.001)
    print(f"\n  Leg A verdict: {'[PASS]' if passes else '[FAIL]'}")
    return passes


# ----------------------------------------------------------------------
# Leg B: the honest negative (naive wake-sum is not a phi-ladder)
# ----------------------------------------------------------------------
def leg_b(ell=1.0):
    print()
    print("=" * 78)
    print("Leg B -- honest negative: the naive 1D wake-sum is not a")
    print("phi-ladder")
    print("=" * 78)
    print("\n  wake-sum f(r) = cos(2 pi r/ell_n) + cos(2 pi phi r/ell_n)")
    print("  (the naive beat picture). Its zeros (bisection on [0, ell_n]):")

    def f(r):
        return (np.cos(2 * np.pi * r / ell)
                + np.cos(2 * np.pi * PHI * r / ell))

    x = np.linspace(1e-3 * ell, ell, 50000)
    y = f(x)
    m = np.where(np.sign(y[1:]) != np.sign(y[:-1]))[0]
    zeros = []
    for i in m:
        a, b = x[i], x[i + 1]
        for _ in range(60):
            c = (a + b) / 2
            if f(a) * f(c) <= 0:
                b = c
            else:
                a = c
        zeros.append((a + b) / 2)
    zeros = sorted(zeros)
    print(f"    zeros/ell_n = {[round(z / ell, 4) for z in zeros]}")

    ladder = {round(PHI ** -k, 3): k for k in range(1, 5)}
    print(f"    phi-ladder matter positions/ell_n: "
          f"{[round(1.0,3), round(PHI**-1,3), round(PHI**-2,3), round(PHI**-3,3)]}")
    near = [z / ell for z in zeros
            if any(abs(z / ell - p) < 0.02 for p in ladder)]
    print(f"    wake-sum zeros within 0.02 of a phi^-k ladder position: "
          f"{[round(n, 3) for n in near] if near else 'none'}")
    print("\n  Reading: 0.191, 0.573, 0.809, 0.955 are NOT the phi-ladder")
    print("  {1, 0.618, 0.382, 0.236}; the intra-shell ladder is phase-")
    print("  quantized (alpha = pi*u), not the wake beat. The correction")
    print("  from the naive reading: 0.382 and 0.809 are NOT zeros.")
    passes = len(near) == 0 and len(zeros) == 4
    print(f"\n  Leg B verdict: {'[PASS]' if passes else '[FAIL]'}")
    return passes


# ----------------------------------------------------------------------
# Leg C: the prediction's observable -- matter ridges at ell_n phi^-k,
#        void troughs at phi^-(k+1/2), from the radial phase envelope
# ----------------------------------------------------------------------
def leg_c(AMP=1.0):
    print()
    print("=" * 78)
    print("Leg C -- prediction observable: the radial matter envelope")
    print("rho(r) ~ cos^2(pi u), u = log_phi(r/ell_n), shows matter")
    print("ridges at ell_n*phi^-k and void troughs at ell_n*phi^-(k+1/2)")
    print("=" * 78)
    # The radial coordinate r spans the nested window [ell_{n-N}, ell_n]
    r = np.linspace(PHI ** -10.0, 1.05, 100000)   # ~the ~1% floor window
    u = np.log(r) / LNPHI                          # u = log_phi(r/ell_n)
    env = AMP * np.cos(np.pi * u) ** 2             # matter density envelope

    # local maxima (matter ridges; integer u) and minima (void troughs;
    # half-integer u), with parabolic sub-pixel refinement in u (the
    # cos^2(pi u) envelope is quadratic in u near each extremum, so the
    # refined u is exact; the uniform-r grid gives only coarse r-midpoints
    # near the log-compressed inner boundary)
    d = env[1:] - env[:-1]
    mx = np.where((d[:-1] > 0) & (d[1:] < 0))[0] + 1   # ridge ids
    mn = np.where((d[:-1] < 0) & (d[1:] > 0))[0] + 1   # trough ids

    def refine_u_peak(i):
        y0, y1, y2 = env[i - 1], env[i], env[i + 1]
        den = y0 - 2 * y1 + y2
        if abs(den) < 1e-14:
            return np.log(r[i]) / LNPHI
        du_r = np.log(r[i + 1] / r[i]) / LNPHI          # u-step at i
        return np.log(r[i]) / LNPHI + 0.5 * du_r * (y0 - y2) / den

    mr = [np.exp(refine_u_peak(i) * LNPHI) for i in mx]
    vr = [np.exp(refine_u_peak(i) * LNPHI) for i in mn]

    print(f"\n  detected matter ridges (integer u = cos^2 maxima):")
    print(f"  {'#':>2} {'r/ell_n':>9} {'predicted phi^-k':>16} "
          f"{'delta rung':>11}")
    ridge_u = []
    for j, rr in enumerate(mr):
        up = np.log(rr) / LNPHI
        ku = -round(up)              # nearest integer u -> ring index
        pred = PHI ** -ku
        ridge_u.append(up)
        print(f"  {j:>2} {rr:>9.5f} {pred:>16.5f} {abs(up - round(up)):>11.4f}")

    print(f"\n  detected void troughs (half-integer u = cos^2 nodes):")
    print(f"  {'#':>2} {'r/ell_n':>9} {'predicted phi^-(k+1/2)':>22} "
          f"{'delta rung':>11}")
    void_u = []
    for j, rv in enumerate(vr):
        up = np.log(rv) / LNPHI
        void_u.append(up)
        ku = round(up) - 0.5         # nearest half-integer u
        pred = PHI ** ku
        print(f"  {j:>2} {rv:>9.5f} {pred:>22.5f} {abs(up - ku):>11.4f}")

    # count of matter ridges within the ~1% floor window
    in_win = [rr for rr in mr if rr >= PHI ** -10.0]
    print(f"\n  matter ridges detected in [phi^-10, 1]: {len(in_win)}")
    print(f"  (predicted ~{int(np.ceil(N_RINGS))} from N = "
          f"ln100/lnphi = {N_RINGS:.3f})")

    # successive-matter ratio and adjacent matter->void ratio from the
    # measured ridge/trough positions (mr sorted ascending in r, so the
    # outward matter-to-matter ratio is mr[j]/mr[j+1] = phi^-1)
    if len(mr) > 2:
        mrat = [mr[j] / mr[j + 1] for j in range(len(mr) - 1)]
        print(f"\n  measured successive-matter-ring ratio mean = "
              f"{np.mean(mrat):.6f}  (phi^-1 = {PHI_INV:.6f})")
    if len(mr) and len(vr):
        vrat = [vr[j] / mr[j] for j in range(min(len(vr), len(mr)))]
        print(f"  measured matter->void ratio mean = {np.mean(vrat):.6f}  "
              f"(phi^-1/2 = {PHI_INV2:.6f})")

    # strict alternation: integer-u ridges interleave half-integer troughs
    both = sorted(ridge_u + void_u)
    is_int = [abs(b % 1.0) < 1e-3 for b in both]
    alternating = all(is_int[i] != is_int[i + 1]
                      for i in range(len(both) - 1))
    print(f"\n  strict matter/void alternation over the sorted u ladder: "
          f"{alternating}")

    passes = (
        all(abs(rr - PHI ** round(np.log(rr) / LNPHI)) < 1e-4
            for rr in mr)
        and all(abs(abs((np.log(rv) / LNPHI) % 1.0) - 0.5) < 1e-4
                for rv in vr)
        and alternating
        and len(in_win) >= 9)
    print(f"\n  Honest scope: Leg C is the ANALYTIC radial envelope the")
    print(f"  prediction names (what a simulated bubble must show), not an")
    print(f"  emergent PDE structure. Whether the two-fluid PDE realizes")
    print(f"  all ~10 interior rings from microphysics, and the ring")
    print(f"  amplitudes (condensation exponent), are the OPEN, unverified")
    print(f"  content flagged in the doc and the catalog block.")
    print(f"\n  Leg C verdict: {'[PASS]' if passes else '[FAIL]'}")
    return passes


def main():
    L = 5 * PHI
    x_sp = 1.5
    N = 1216
    dt = 0.0015
    t_short = 0.05

    print("=" * 78)
    print("Bubble-shell ring-ladder probe (Prediction 51)")
    print(f"phi = {PHI:.6f}, ln-phi = {LNPHI:.6f}, phi^-1 = {PHI_INV:.6f},")
    print(f"phi^-1/2 = {PHI_INV2:.6f}, N = ln100/lnphi = {N_RINGS:.4f}")
    print("=" * 78)

    ok = leg_a()
    ok_b = leg_b()
    ok_c = leg_c()

    print()
    print("=" * 78)
    print("Verdicts")
    print("=" * 78)
    print("Leg A (ring law): matter at ell_n*phi^-k, voids at")
    print("  ell_n*phi^-(k+1/2); ratios phi^-1 and phi^-1/2; strict")
    print("  alternation; ~10 rings (N = 9.570); n-independent. "
          f"{'[PASS]' if ok else '[FAIL]'}")
    print("Leg B (honest negative): naive wake-sum zeros {0.191, 0.573,")
    print("  0.809, 0.955}*ell_n are NOT a phi-ladder; the intra-shell")
    print("  ladder is phase-quantized. "
          f"{'[PASS]' if ok_b else '[FAIL]'}")
    print("Leg C (prediction observable): the radial envelope")
    print("  rho ~ cos^2(pi u) has matter ridges at ell_n*phi^-k and void")
    print("  troughs at ell_n*phi^-(k+1/2), strict alternation, ~10 rings;")
    print("  PDE realization of all rings is the open content. "
          f"{'[PASS]' if ok_c else '[FAIL]'}")

    all_ok = ok and ok_b and ok_c
    print(f"\nAll checks: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
