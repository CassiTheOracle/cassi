"""triaxial3d_relax_probe.py -- wave 7: the 3D sigma-relaxation time trace.

Per triaxial3d_relax_prereg.md. Deterministic, numpy, matrix-free. Tracks
sigma_x/y and sigma_x/z (and the peak |EY+EI| amplitude floor) at t = 200..2400
steps on the phi-arm and at key times on the symmetric control, from a
PHYSICALLY-ROUND seed, and renders the frozen verdict.

Run from the repo root:  python research/helix_solver/triaxial3d_relax_probe.py

Provenance note (2026-08-16): the 1.422/2.510 values are single-run outputs of
CassiTheory/visual-explainers/string_bubble_cascade.py, NOT engine measurements -- see
research/helix_solver/oblate_provenance_audit.md (commit 27ad20f) and oblate_claim_map.md (15db3c8).
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3

N = 64
PHI2 = PHI * PHI
TRACE = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400]
CTL_TRACE = [200, 1200, 2400]


def run_trace(h, measure_points):
    """Fresh two-fluid run from a round seed; yield (step, field, solver) at measure_points."""
    g = t3.TwoFluid3D(h)
    ey, ei = t3.seed_bubble3d(N, h)
    ve = wi = np.zeros_like(ey)
    peak0 = float(np.abs(ey + ei).max())
    it = iter(measure_points)
    nxt = next(it, None)
    for s in range(1, measure_points[-1] + 1):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        if s == nxt:
            yield s, ey, ei, g, peak0
            nxt = next(it, None)


def main() -> None:
    print("== Wave-7: the 3D sigma-relaxation time trace ==")
    ph = (PHI, 1.0, 1.0 / PHI)
    print(f"  doctrine anchors: phi={PHI:.3f}, phi^2={PHI2:.3f}; sim record (step~1100): "
          f"1.422, 2.510 (string_bubble_cascade.py)")
    print("  phi-arm sigma_x/y and sigma_x/z vs step:")
    rows_xy, rows_xz = [], []
    ambient_ok = True
    for s, ey, ei, g, peak0 in run_trace(ph, TRACE):
        rho = ey + ei
        sx, sy, sz = t3.sigma3(rho, g.h)
        peak = float(np.abs(rho).max())
        if peak < 0.10 * peak0:
            ambient_ok = False
        print(f"    t={s:>5}: sigma_x/y={sx/sy:.3f}  sigma_x/z={sx/sz:.3f}  peak/peak0={peak/peak0:.3f}")
        rows_xy.append((s, sx / sy))
        rows_xz.append((s, sx / sz))

    print()
    print("  symmetric control (isotropy invariant):")
    for s, ey, ei, g, peak0 in run_trace((1.0, 1.0, 1.0), CTL_TRACE):
        rho = ey + ei
        sx, sy, sz = t3.sigma3(rho, g.h)
        print(f"    t={s:>5}: sigma_x/y={sx/sy:.3f}  sigma_x/z={sx/sz:.3f}  (control must stay ~1.0)")

    # --- the frozen verdict -------------------------------------------------------
    r600_xy = dict(rows_xy)[600]
    r600_xz = dict(rows_xz)[600]
    rend_xy = dict(rows_xy)[2400]
    rend_xz = dict(rows_xz)[2400]
    d600 = abs(r600_xy - PHI) + abs(r600_xz - PHI2)
    dend = abs(rend_xy - PHI) + abs(rend_xz - PHI2)
    relax = dend < d600 * 0.85
    toward_sim = (abs(rend_xy - 1.422) < 0.15 * 1.422) and (abs(rend_xz - 2.510) < 0.15 * 2.510)
    intrinsic = abs((rend_xy - r600_xy) / max(r600_xy, 1e-9)) < 0.10 and \
        abs((rend_xz - r600_xz) / max(r600_xz, 1e-9)) < 0.10

    print()
    if not ambient_ok:
        print("  VERDICT: INCONCLUSIVE -- the peak |EY+EI| decayed below 10% of initial before 2400 steps")
        print("           (a decayed bubble's sigma moments are noise; the trace is flagged AMBIENT-DECAY)")
    elif relax:
        if toward_sim:
            print(f"  VERDICT: RELAXES (toward the SIM record) -- sigma_x/y {r600_xy:.2f}->{rend_xy:.2f}, "
                  f"sigma_x/z {r600_xz:.2f}->{rend_xz:.2f}; the 2400-step values approach the sim's 1.422/2.510")
        else:
            print(f"  VERDICT: RELAXES toward the DOCTRINE -- sigma_x/y {r600_xy:.2f}->{rend_xy:.2f}, "
                  f"sigma_x/z {r600_xz:.2f}->{rend_xz:.2f}; the wave-6 over-shoot was a short-run transient")
    elif intrinsic:
        print(f"  VERDICT: INTRINSIC -- sigma_x/y and sigma_x/z stay within 10% of the 600-step "
              f"values ({r600_xy:.2f}/{r600_xz:.2f} at t=600 -> {rend_xy:.2f}/{rend_xz:.2f} at t=2400); "
              f"the over-shoot is settled, not a transient")
    else:
        print("  VERDICT: mixed/non-monotonic relaxation -- see the trace")

    print()
    print("  NOTE: a monotonic relax toward phi/phi^2 (or through the sim record) would validate")
    print("  the oblate-triaxial direction AND the eventual magnitude; staying near the wave-6")
    print("  values would mark the over-drive intrinsic. This is a measurement, not a pin change.")
    print("done")


if __name__ == "__main__":
    main()
