"""lapweight_crossing_probe.py -- U2: the lap-weight degeneracy crossing curve.

Per lapweight_crossing_prereg.md. For the box family h = (phi, 1.0, s), scan the
axial Laplacian coefficient az(s) (and supplementary ax/ay) from the wave-8
lap_weights formula; run the anchor gate on (phi,1,phi^2); bisect to find s*,
the s where az(s) = 0. Deterministic, numpy only.

Run from the repo root:  python research/helix_solver/lapweight_crossing_probe.py
"""

import numpy as np

try:
    from phi_grid import PHI
except Exception:  # pragma: no cover
    PHI = (1.0 + np.sqrt(5.0)) / 2.0

try:
    # Prefer the wave-8 upstream; identical local fallback (prereg §1).
    from triaxial3d import lap_weights as _upstream_lap_weights
    LAP_SOURCE = "imported from triaxial3d.py"
except Exception:
    _upstream_lap_weights = None
    LAP_SOURCE = "local copy (fallback)"


def lap_weights(h):
    """Exact copy of triaxial3d.py:37-48 (prereg §1). Used when the import fails."""
    hx, hy, hz = h
    h02 = min(h) ** 2
    bxy = (1.0 / 3.0) * h02 / (hx * hx + hy * hy)
    bxz = (1.0 / 3.0) * h02 / (hx * hx + hz * hz)
    byz = (1.0 / 3.0) * h02 / (hy * hy + hz * hz)
    ax = h02 / (hx * hx) - 2.0 * (bxy + bxz)
    ay = h02 / (hy * hy) - 2.0 * (bxy + byz)
    az = h02 / (hz * hz) - 2.0 * (bxz + byz)
    return ax, ay, az, bxy, bxz, byz


if _upstream_lap_weights is not None:
    _lap_weights = _upstream_lap_weights
else:
    _lap_weights = lap_weights

PHI2 = PHI * PHI

# Frozen pins (prereg §2)
ANCHOR = (0.127, 0.731, -0.009, 0.092, 0.035, 0.042)   # wave-8 (phi,1,phi^2), 3dp
ANCHOR_TOL = 5e-4                                       # rounds to same 3 dp
S_LO, S_HI = 0.5, 2.0 * PHI2 + 2.0                      # [0.5, 2φ²+2]
N_SCAN = 400000                                         # fine scan steps
BAND_LO, BAND_HI = PHI2 * 0.9, PHI2 * 1.1               # [2.356, 2.880]
BISECT_ATOL = 1e-12


def az_of(s):
    return _lap_weights((PHI, 1.0, s))[2]


def find_crossings(f, lo, hi, n_steps):
    """Detect sign changes of f on a uniform grid; return bracket pairs."""
    sv = np.linspace(lo, hi, n_steps)
    fv = np.array([f(s) for s in sv])
    brackets = []
    # Crossings: product of adjacent signs < 0, or an exact zero (its own bracket).
    for i in range(len(sv) - 1):
        a, b = fv[i], fv[i + 1]
        if a == 0.0 or (a * b < 0.0):
            brackets.append((sv[i], sv[i + 1]))
    # Merge any consecutive brackets that share a zero on the grid.
    merged = []
    for br in brackets:
        if merged and abs(br[0] - merged[-1][1]) < 1e-15:
            merged[-1] = (merged[-1][0], br[1])
        else:
            merged.append(br)
    return merged, sv, fv


def bisect(f, lo, hi, atol=BISECT_ATOL):
    """Bisect f(s)=0 on [lo,hi]. Returns (root, residual)."""
    flo, fhi = f(lo), f(hi)
    # handle an exact-zero endpoint
    if flo == 0.0:
        return lo, 0.0
    if fhi == 0.0:
        return hi, 0.0
    if flo * fhi > 0.0:
        return None, None
    while hi - lo > atol:
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if fm == 0.0:
            return mid, 0.0
        if fm * flo < 0.0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    root = 0.5 * (lo + hi)
    return root, f(root)


def main():
    print("== U2: lap-weight degeneracy crossing curve (h=(phi,1,s)) ==")
    print(f"  PHI = {PHI:.10f}, PHI^2 = {PHI2:.6f}")
    print(f"  formula source: {LAP_SOURCE}")
    print(f"  scan range: [S_LO, S_HI] = [{S_LO}, {S_HI:.6f}] ({N_SCAN} steps)")
    print(f"  verdict band: [PHI^2*0.9, PHI^2*1.1] = [{BAND_LO:.6f}, {BAND_HI:.6f}]")
    print()

    # ---- 0. Anchor gate (prereg §2.1) ----
    w = _lap_weights((PHI, 1.0, PHI2))
    print("  --- anchor gate: lap_weights((phi,1,phi^2)) vs wave-8 ---")
    names = ("ax", "ay", "az", "bxy", "bxz", "byz")
    gate_ok = True
    for nm, got, exp in zip(names, w, ANCHOR):
        diff = abs(got - exp)
        ok = diff < ANCHOR_TOL
        gate_ok &= ok
        print(f"    {nm}: {got:.4f}  target {exp:.3f}  |diff|={diff:.2e}  "
              f"{'OK' if ok else 'FAIL'}")
    print(f"  anchor gate: {'PASSED' if gate_ok else 'FAILED'}")

    # ---- 1. Scan az(s) ----
    def _az(s):
        return _lap_weights((PHI, 1.0, s))[2]

    brackets, sv, fv = find_crossings(_az, S_LO, S_HI, N_SCAN)
    print(f"\n  --- az(s) scan: {len(brackets)} bracket(s) over [{S_LO}, {S_HI:.6f}] ---")

    # ---- 2. Bisection to s* ----
    roots = []
    for (lo, hi) in brackets:
        r, res = bisect(_az, lo, hi)
        if r is not None:
            roots.append((r, res))

    # ---- 3. Supplementary ax(s), ay(s) crossings (no verdict) ----
    def _ax(s):
        return _lap_weights((PHI, 1.0, s))[0]

    def _ay(s):
        return _lap_weights((PHI, 1.0, s))[1]

    ax_br, _, _ = find_crossings(_ax, S_LO, S_HI, N_SCAN)
    ay_br, _, _ = find_crossings(_ay, S_LO, S_HI, N_SCAN)
    ax_roots = [bisect(_ax, lo, hi)[0] for (lo, hi) in ax_br if bisect(_ax, lo, hi)[0] is not None]
    ay_roots = [bisect(_ay, lo, hi)[0] for (lo, hi) in ay_br if bisect(_ay, lo, hi)[0] is not None]

    print("  trace table (az(s) sampled):")
    for s_show in [0.5, 1.0, 1.618, 2.0, BAND_LO, PHI2, BAND_HI, 3.0, 4.0, 5.0, 7.236]:
        print(f"    s={s_show:8.4f}  az={_az(s_show):+.6f}  ax={_ax(s_show):+.6f}  ay={_ay(s_show):+.6f}")
    print()
    print(f"  az crossings found: {len(roots)}")
    for i, (r, res) in enumerate(roots):
        print(f"    crossing {i+1}: s* = {r:.6f}  az(s*) = {res:.2e}")

    # ---- 4. Decision tree (prereg §3) ----
    verdict = "INCONCLUSIVE"
    detail = ""
    n_az = len(roots)
    if not gate_ok:
        verdict, detail = "INCONCLUSIVE", "anchor gate failed; no verdict read"
    elif n_az == 0:
        verdict, detail = "CONTRADICTS", "no az sign change in scan range"
    elif n_az == 1:
        s_star = roots[0][0]
        if BAND_LO <= s_star <= BAND_HI:
            verdict = "SUPPORTS"
            detail = (f"az has exactly one sign change at s*={s_star:.6f} "
                      f"in [{BAND_LO:.3f},{BAND_HI:.3f}]")
        else:
            verdict = "CONTRADICTS"
            detail = (f"single crossing s*={s_star:.6f} outside band "
                      f"[{BAND_LO:.3f},{BAND_HI:.3f}]")
    else:
        # >1 crossing: check for a near-zero plateau touching the band edge
        plateau = False
        for i in range(len(sv) - 1):
            if abs(fv[i]) < 1e-4 and (sv[i] <= BAND_HI):
                # wide plateau near band: span check
                j = i
                while j < len(sv) and abs(fv[j]) < 1e-4:
                    j += 1
                if sv[j - 1] - sv[i] >= 0.05 and not (sv[i] > BAND_HI or sv[j - 1] < BAND_LO):
                    plateau = True
                    break
        if plateau:
            verdict, detail = "INCONCLUSIVE", "near-zero plateau spanning the band edge; s* ambiguous"
        else:
            verdict, detail = "INCONCLUSIVE", f"multiple az crossings ({n_az}); degenerate"

    print()
    print(f"  VERDICT: {verdict}")
    print(f"    reason: {detail}")
    print()
    print("  supplementary (NO verdict): ax crossings at s = "
          + (", ".join(f"{r:.3f}" for r in ax_roots) if ax_roots else "none"))
    print("  supplementary (NO verdict): ay crossings at s = "
          + (", ".join(f"{r:.3f}" for r in ay_roots) if ay_roots else "none"))
    print()
    print("  " + ("ALL CHECKS PASSED" if gate_ok else "ALL CHECKS FAILED"))


if __name__ == "__main__":
    main()
