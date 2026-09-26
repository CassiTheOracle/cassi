#!/usr/bin/env python3
"""
Wu Xing Coherence Verification: is {w : E(w) <= phi^-w} = {1, 2, 3, 5}?
=======================================================================

Verifies the cascade upper bound of foundations/wu-xing-derivation.md §2:

1. Fibonacci identity |F_k*phi - F_{k+1}| = phi^-k, exact for all k.
2. The coherence criterion for ALL w in [1, 2000]:
   E(w) = min_p w*|phi - p/w| = ||w phi||  (distance from w*phi to nearest integer)
   The cycle closes coherently iff E(w) <= phi^-w (cascade signal at rung w).
   Claim: holds ONLY for w in {1, 2, 3, 5} (w = 5 passes at equality, E = phi^-5
   exactly by the identity; the check uses a 1e-12 float tolerance).
3. The k >= F_k table for Fibonacci cycles.
4. Explicit failures: w = 4, 6, 7 (and the w = 10 falsification, 22x).
5. Geometry lower bound: phi first appears in the chord ratios of the regular
   n-gon at n = 5 (verified for n = 3..12; n = 10 also contains phi but is
   cascade-killed per the doc's §2).

Run:  python computations/wu_xing_coherence_check.py
"""

import math

PHI = (1 + math.sqrt(5)) / 2
EPS = 1e-12


def E(w):
    """Accumulated phase error of a w-step cycle: ||w*phi||."""
    return abs(w * PHI - round(w * PHI))


def main():
    print("═══ Wu Xing Coherence Verification (wu-xing-derivation.md §2) ═══")
    print(f"  phi = {PHI:.15f}")

    # ── 1. Fibonacci identity |F_k*phi - F_{k+1}| = phi^-k ──
    F = [1, 1]
    for _ in range(30):
        F.append(F[-1] + F[-2])
    print("\n── 1. Fibonacci identity ──")
    ok_all = True
    for k in range(1, 13):
        ident = abs(F[k - 1] * PHI - F[k])
        exact = PHI ** (-k)
        ok = abs(ident - exact) < 1e-9
        ok_all &= ok
        print(f"  k={k:2d}  F_k={F[k-1]:3d}  |F_k*phi-F_{{k+1}}|={ident:.12f}  "
              f"phi^-k={exact:.12f}  {'✓' if ok else '✗'}")
    print(f"  → identity exact: {ok_all}")

    # ── 2. Criterion over ALL w in [1, 2000] ──
    print("\n── 2. Coherence criterion E(w) <= phi^-w for w in [1, 2000] ──")
    passes = [w for w in range(1, 2001) if E(w) <= PHI ** (-w) + EPS]
    print(f"  passing w: {passes}")
    assert passes == [1, 2, 3, 5], f"FAIL: passing set is {passes}"
    print("  → only w in {1, 2, 3, 5} pass (w = 5 at equality)")
    print("  explicit non-passers:")
    for w in [4, 6, 7, 8, 10, 13, 21]:
        print(f"    w={w:3d}: E={E(w):.6f}  phi^-w={PHI**(-w):.6f}  "
              f"pass={E(w) <= PHI**(-w) + EPS}")

    # ── 3. Fibonacci cycles: phi^-k <= phi^-F_k  <=>  k >= F_k ──
    print("\n── 3. Fibonacci cycle table (k >= F_k) ──")
    for k in range(1, 10):
        cond = PHI ** (-k) <= PHI ** (-F[k - 1]) + EPS
        print(f"  k={k}  F_k={F[k-1]:2d}  k>=F_k:{k >= F[k-1]!s:5s}  "
              f"phi^-k={PHI**(-k):.5f} <= phi^-F_k={PHI**(-F[k-1]):.5f}: {cond}")
    distinct_w = sorted({F[k - 1] for k in range(1, 6)})
    print(f"  → distinct coherent Fibonacci cycles: {distinct_w}")

    # ── 4. w = 10 falsification ──
    print("\n── 4. w = 10 falsification ──")
    e10 = 10 * abs(PHI - 16 / 10)
    s10 = PHI ** (-10)
    print(f"  10*|phi - 16/10| = {e10:.4f};  phi^-10 = {s10:.4f};  "
          f"factor = {e10 / s10:.1f}x")

    # ── 5. phi in chord ratios of the regular n-gon, n = 3..12 ──
    print("\n── 5. Geometry: phi in regular n-gon chord ratios ──")
    first = None
    for n in range(3, 13):
        chords = [2 * math.sin(k * math.pi / n) for k in range(1, n // 2 + 1)]
        hits = []
        for j in range(len(chords)):
            for k in range(j + 1, len(chords)):
                if abs(chords[j] / chords[k] - PHI) < EPS:
                    hits.append((j + 1, k + 1))
                if abs(chords[k] / chords[j] - PHI) < EPS:
                    hits.append((k + 1, j + 1))
        if hits and first is None:
            first = n
        print(f"  n={n:2d}: phi present={bool(hits)}  {hits}")
    print(f"  → first n with phi in chord ratios: {first}")
    assert first == 5, f"FAIL: first n is {first}"
    diag_side = (2 * math.sin(2 * math.pi / 5)) / (2 * math.sin(math.pi / 5))
    print(f"  pentagon diag/side = {diag_side:.12f} = phi: "
          f"{abs(diag_side - PHI) < EPS}")

    # ── 6. Consequences: gap and r0 ──
    print("\n── 6. Consequences ──")
    g = 1 - PHI ** (-5)
    r0 = PHI ** (-5) / (2 - PHI ** (-5))
    print(f"  g  = 1 - phi^-5 = {g:.10f}  (0.9098)")
    print(f"  r0 = phi^-5/(2 - phi^-5) = {r0:.10f}  (0.0472);  "
          f"E_I/E_Y = {1 / r0:.4f}")

    print("\n→ ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
