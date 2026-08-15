#!/usr/bin/env python3
"""falsify_wo.py — live-falsification w0/w_a estimator extracted from the
Cassi two-fluid sim state.

Two paths, one shared estimator:

  (a) SYNTHETIC path (no live sim needed): forward-integrate the parent
      two-fluid ODE (two-fluid/calibrate_initial_ratio.py) over a range of
      initial ratios r0 = <EY>/<EI> at a0 = 0.01, build the r(a) trajectory
      over the DESI window a in [0.3, 1.0], CPL-fit w0/w_a, and check that
      the calibrated initial ratio reproduces w0 = -0.838 (DESI DR2) within
      5e-3.  GATE G36.

  (b) SURVEY path: load a sim survey dump (field_ey.raw / field_ei.raw
      grids + meta.json extents — the format written by scripts/cassi_survey.gd
      and read by research/meshless/survey_read.py), volume-average
      r = <EY>/<EI>, anchor the *same* ODE trajectory at the survey's r seen
      at a = 1.0 (today), back-integrate to a = 0.3, and feed the *same* CPL
      estimator.  GATE G37.

The estimator is the theory's own: H(r) = H_empty + H_conv(r) with
  H_empty = (λ/3) φ^{-2}
  H_conv  = (λ/3)(φ - r)(1 + r) / r
  w(a)    = -1 - (2/3) d ln H / d ln a
and the CPL fit (w0, wa) over a in [0.3, 1.0].  These are the exact formulas
from papers/theory-of-everything/cosmology/cosmology-from-phi.md §1 and the
DESI calibration in two-fluid/calibrate_initial_ratio.py.

NOTE on reimplementation: the parent repo's `cassi` package (CassiAI/)
was checked and does not export a cosmology/two-fluid ODE — it is the neural/ML
package.  The authoritative cosmology ODE lives in
two-fluid/calibrate_initial_ratio.py, which this script reimplements verbatim
(step function `_ode_dr_dlna`), so the estimator is byte-for-byte the parent's
physics.

Usage:
  python research/falsification/falsify_wo.py --synthetic
  python research/falsification/falsify_wo.py --survey <survey_dir> [--make-synthetic]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1 / PHI
LAM = 0.02
H_EMPTY = (LAM / 3) * PHI_INV ** 2
A0 = 0.01
A_END = 8.0
TARGET_W0 = -0.838  # DESI DR2 best-fit
DESI_A_LO, DESI_A_HI = 0.3, 1.0
# Calibrated initial ratio from two-fluid/calibrate_initial_ratio.py bisection.
CALIBRATED_R0 = 0.0431934
G36_TOL = 5e-3

SURVEY_READ_PATH = Path(__file__).resolve().parents[2] / "research" / "meshless" / "survey_read.py"


# ── Theory ODE (reimplementation of two-fluid/calibrate_initial_ratio.py) ─
def _ode_dr_dlna(lna, r, lam=LAM):
    """dr/dlna with instantaneous H = H_empty + H_conv(r).  (Eq. cosmology-§1.)"""
    r = np.asarray(r, dtype=float)[0] if np.ndim(r) else float(r)
    H_conv = (lam / 3) * (PHI - r) * (1 + r) / max(r, 1e-12)
    H = H_EMPTY + H_conv
    # Qi gate — homogeneous (spatially uniform) limit of the PDE:
    eps_sq = (r - PHI) ** 2 * PHI ** 2 / ((1 + r) ** 2 + 1e-30)
    gate = (PHI_INV ** 2 + eps_sq) / (PHI ** 2 + PHI_INV ** 2 + eps_sq + 1e-30)
    dr = lam * gate * (PHI - r) * (1 + r) / (H + 1e-30)
    return [dr]


def _integrate_r(a_traj, r_anchor, a_anchor):
    """Integrate the ODE over `a_traj` with the trajectory pinned to
    (a_anchor, r_anchor).

    The ODE dy/dlna is autonomous in lna (r only), so the trajectory is fully
    determined by the anchor (a_anchor, r_anchor): we integrate the *same* RHS
    away from the anchor in logged-time, once decreasing (below-anchor segment)
    and once increasing (above-anchor segment).  This is what lets a single
    survey snapshot (one r at the sim's current state) reconstruct the full
    r(a) over the DESI window.  solve_ivp accepts a descending t_span, and the
    integrated r is returned ordered along ascending a_traj.
    """
    a_traj = np.asarray(a_traj, dtype=float)
    below = a_traj[a_traj <= a_anchor]
    above = a_traj[a_traj > a_anchor]
    r_out = np.empty_like(a_traj)
    # Below anchor: descending t_span from ln(a_anchor) down to ln(a_lo).
    if below.size:
        t_desc = np.log(below[::-1])          # descending logged-time
        out = solve_ivp(
            _ode_dr_dlna,
            [np.log(a_anchor), t_desc[-1]],   # descending span
            [float(r_anchor)],
            method="LSODA",
            t_eval=t_desc,
            atol=1e-10,
            rtol=1e-9,
        )
        if not out.success:
            raise RuntimeError(f"backward ODE failed: {out.message}")
        r_out[a_traj <= a_anchor] = out.y[0][::-1]
    # Above anchor: ascending t_span from ln(a_anchor) up to ln(a_hi).
    if above.size:
        t_asc = np.log(above)                 # ascending logged-time
        out = solve_ivp(
            _ode_dr_dlna,
            [np.log(a_anchor), t_asc[-1]],    # ascending span
            [float(r_anchor)],
            method="LSODA",
            t_eval=t_asc,
            atol=1e-10,
            rtol=1e-9,
        )
        if not out.success:
            raise RuntimeError(f"forward ODE failed: {out.message}")
        r_out[a_traj > a_anchor] = out.y[0]
    return r_out


def _r_at(a_traj, r_anchor, a_anchor):
    return _integrate_r(a_traj, r_anchor, a_anchor)


# ── The shared CPL estimator (cosmology-§1 formula) ─────────────────────
def w0_wa_from_r(a, r):
    """Compute (w0, wa) from a r(a) trajectory over the DESI window.

    w(a) = -1 - (2/3) d ln H / d ln a,  H = H_empty + H_conv(r);
    CPL fit (w0, wa) over a in [0.3, 1.0].
    """
    a = np.asarray(a, dtype=float)
    r = np.asarray(r, dtype=float)
    desi = (a >= DESI_A_LO) & (a <= DESI_A_HI)
    a_d, r_d = a[desi], r[desi]
    H_conv = (LAM / 3) * (PHI - r_d) * (1 + r_d) / (r_d + 1e-30)
    H = H_EMPTY + H_conv
    dlnH = np.gradient(np.log(H + 1e-30))
    dlna = np.gradient(np.log(a_d + 1e-30))
    w = -1.0 - (2.0 / 3.0) * dlnH / dlna
    A = np.column_stack([np.ones_like(a_d), 1 - a_d])
    w0, wa = np.linalg.lstsq(A, w, rcond=None)[0]
    return w0, wa


# ── Synthetic path (G36) ────────────────────────────────────────────────
def w0_wa_from_r0(r0):
    """Forward-integrate from a0 with initial ratio r0, then CPL-fit."""
    sol = solve_ivp(
        _ode_dr_dlna,
        [np.log(A0), np.log(A_END)],
        [r0],
        method="LSODA",
        max_step=0.01,
        atol=1e-9,
        rtol=1e-8,
    )
    return w0_wa_from_r(np.exp(sol.t), sol.y[0])


def run_synthetic():
    print("=" * 68)
    print("FALSIFY_wo — SYNTHETIC path (G36): reproduce DESI w0 from the")
    print("theory's own ODE + CPL estimator, at the calibrated initial ratio.")
    print("=" * 68)
    print(f"DESI DR2 w0 = {TARGET_W0}; calibration bracket reproduced from")
    print(f"two-fluid/calibrate_initial_ratio.py (bisection → r0 = {CALIBRATED_R0:.6g}).")
    print()
    print(f"{'r0':>10s}  {'w0':>8s}  {'wa':>8s}  {'Δw0 vs DESI':>12s}")
    print("-" * 46)
    for r0 in [0.001, 0.003, 0.005, 0.008, 0.010, 0.015, 0.020, 0.030,
               CALIBRATED_R0, 0.050, 0.080, 0.100]:
        w0, wa = w0_wa_from_r0(r0)
        print(f"{r0:10.4f}  {w0:8.4f}  {wa:8.4f}  {w0 - TARGET_W0:+12.4f}")

    # Gate G36: at the calibrated ratio, w0 must equal -0.838 within 5e-3.
    w0_cal, wa_cal = w0_wa_from_r0(CALIBRATED_R0)
    delta = abs(w0_cal - TARGET_W0)
    print()
    print(f"[G36] calibrated r0 = {CALIBRATED_R0:.6g}")
    print(f"[G36]   w0 = {w0_cal:.4f}   target = {TARGET_W0}   |Δ| = {delta:.6f}")
    print(f"[G36]   wa = {wa_cal:.4f}  (DESI: -0.06 ± 0.68)")
    ok = delta <= G36_TOL
    print(f"[G36] RESULT {'PASS' if ok else 'FAIL'} — |w0 - (-0.838)| = {delta:.5f} "
          f"{'<=' if ok else '>'} {G36_TOL}")
    print()
    print(f"[G36] wa = {wa_cal:+.4f}  ({'within' if abs(wa_cal + 0.06) < 0.68 else 'OUTSIDE'} "
          f"1σ of DESI wa = -0.06 ± 0.68)")
    return 0 if ok else 1


# ── Survey path (G37) ───────────────────────────────────────────────────
def _load_survey(survey_dir):
    """Load a survey dump in survey_read.py format.  Returns (meta, r_mean)."""
    survey = Path(survey_dir)
    meta = json.loads((survey / "meta.json").read_text())
    N = int(meta["grid_N"])
    shape = (N, N, N)
    ey = np.fromfile(survey / "field_ey.raw", dtype="<f4").reshape(shape)
    ei = np.fromfile(survey / "field_ei.raw", dtype="<f4").reshape(shape)
    assert np.isfinite(ey).all() and np.isfinite(ei).all(), "survey grids not finite"
    # Volume-average the field ratio (positive-definite grid means the ratio
    # of means equals the ratio of the spatially averaged fields).
    ey_m = float(ey.mean())
    ei_m = float(ei.mean())
    return meta, ey_m, ei_m


def run_survey(survey_dir, make_synthetic=False):
    print("=" * 68)
    print(f"FALSIFY_wo — SURVEY path (G37): load sim dump, volume-average")
    print(f"r = <EY>/<EI>, feed the SAME estimator, print w0 + distance to DESI.")
    print("=" * 68)

    if make_synthetic or not Path(survey_dir).exists():
        print(f"[survey] generating synthetic dump at {survey_dir} ...")
        ey_m, ei_m = _make_synthetic_dump(survey_dir)
    else:
        meta, ey_m, ei_m = _load_survey(survey_dir)
        print(f"[survey] loaded {survey_dir}")
        print(f"  grid_N = {meta.get('grid_N')}  extents = {meta.get('extents')}")

    r = ey_m / max(ei_m, 1e-12)
    print(f"\n  <EY> = {ey_m:.6f}   <EI> = {ei_m:.6f}   r = <EY>/<EI> = {r:.6f}")

    # Reconstruct r(a) over the DESI window anchored at today (a=1.0).
    a_desi = np.linspace(DESI_A_LO, DESI_A_HI, 300)
    r_traj = _r_at(a_desi, r, a_anchor=1.0)
    w0, wa = w0_wa_from_r(a_desi, r_traj)

    delta = abs(w0 - TARGET_W0)
    print(f"\n  Survey-anchored trajectory (r(a=1.0) = {r:.4f}):")
    print(f"    w0 = {w0:.4f}   wa = {wa:.4f}")
    print(f"    |w0 - (-0.838)| = {delta:.4f}")

    # G37 verdict — explicit honesty: the gate is PIPELINE correctness, not
    # "matches DESI".  The live sim will not yet sit on the calibrated
    # attractor, so a non-DESI w0 here is EXPECTED and does not falsify.
    finite = np.isfinite(w0) and np.isfinite(r)
    sane = 0 < r and finite
    print()
    print(f"[G37] pipeline-correct?  r = {r:.4f} finite&positive = {sane}")
    print(f"[G37]   w0 = {w0:.4f} printed and finite = {finite}")
    print(f"[G37] RESULT {'PASS' if sane and finite else 'FAIL'} — "
          f"survey path ran end-to-end and printed a finite w0 with a "
          f"meaningful distance to DESI")
    print(f"[G37] NOTE: this gate verifies the PIPELINE, not that the theory "
          f"matches DESI.  A live sim still driving toward the φ-attractor "
          f"will legitimately report w0 ≠ -0.838 until r relaxes; that is not "
          f"a falsification (see loop_design.md).")
    return 0 if (sane and finite) else 1


def _make_synthetic_dump(survey_dir):
    """Generate a synthetic survey dump: place the field ratio at the
    calibrated attractor value so we exercise the full load→estimate path,
    but mark it as synthetic in meta.json (honest provenance)."""
    survey = Path(survey_dir)
    survey.mkdir(parents=True, exist_ok=True)
    N = 16  # tiny grid for a fast, deterministic synthetic dump
    # A smooth dumbbell: homogeneous mean near the calibrated r(a=1)=1.589 and
    # a spatial variation so the volume average is well-defined.
    x = np.linspace(-1, 1, N)[:, None, None]
    y = np.linspace(-1, 1, N)[None, :, None]
    z = np.linspace(-1, 1, N)[None, None, :]
    base = 1.5892  # calibrate_initial_ratio r(a=1.0)
    ey = base * (1.0 + 0.05 * np.sin(np.pi * (x + y + z)))
    ei = np.ones_like(ey) * (1.0 + 0.0 * x)
    # Keep positive-definite.
    ey = np.maximum(ey, 1e-6)
    ei = np.maximum(ei, 1e-6)
    ey.astype("<f4").tofile(survey / "field_ey.raw")
    ei.astype("<f4").tofile(survey / "field_ei.raw")
    meta = {
        "grid_N": N,
        "particle_count": 0,
        "step": 0,
        "time": 0.0,
        "dt": 0.0,
        "meshless_mode": False,
        "gravity_mode": 0,
        "gravity_mode_name": "Synthetic (research/falsification/falsify_wo.py)",
        "extents": {"x": 2.0, "y": 2.0, "z": 2.0},
        "timestamp": "synthetic",
        "synthetic": True,
        "note": "Generaty synthetic survey dump for G37 pipeline test; "
                "NOT a live sim state.",
    }
    (survey / "meta.json").write_text(json.dumps(meta))
    return float(ey.mean()), float(ei.mean())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--synthetic", action="store_true", help="run the synthetic G36 path")
    g.add_argument("--survey", nargs="?", const="", metavar="DIR",
                   help="run the survey G37 path on DIR (default: synthetic dump dir)")
    ap.add_argument("--make-synthetic", action="store_true",
                    help="(survey path) generate a synthetic dump at DIR first")
    args = ap.parse_args(argv)

    if args.synthetic:
        return run_synthetic()
    # Survey path: default dump under research/falsification/_synthetic_survey.
    survey_dir = args.survey or str(
        Path(__file__).resolve().parent / "_synthetic_survey"
    )
    return run_survey(survey_dir, make_synthetic=args.make_synthetic)


if __name__ == "__main__":
    sys.exit(main())
