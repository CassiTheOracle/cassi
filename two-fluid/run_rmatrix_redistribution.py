#!/usr/bin/env python3
"""R-matrix (adiabatic redistribution) gate-level test.

Claim under test: `consciousness/emotions-as-gate-configurations.md` §4.2—
the R-matrix R_ij. When channel k closes, its coherence redistributes to the
other four in proportion to their baseline openness:

    d b_i^(redist) = [ b_i / sum_{j != k} b_j ] * d b_k ,   b_i = phi^-(2+i)

Rows quoted in the doc (Wood closure blend 44.7% Fire, 27.6% Earth, 17.1%
Metal, 10.6% Water). The ke-ring algebra is gate-verified
(`two-fluid/run_trauma_c1_ring.py`, 2026-07-31/08-01), but the sheng
adiabatic-redistribution rows have never been measured at the mechanism
layer—the gate itself.

Mechanism: `gate_model='five'` in `two-fluid/cassi_two_fluid_3d_gpu.py`
(compute_q_field / rhs): channel openness ch = b * w(eps_norm) with
w-shape (1-eps_norm, 4 eps_norm (1-eps_norm), 1, eps_norm,
sigmoid((eps_norm-0.3)/0.05)). Only WOOD closure (w1 < 1) triggers a
redistribution term, allocated by ACTIVE openness b_i w_i, not baseline.

Protocol (gate is quasi-static—no memory when qi_memory=False, so the
drive-axis readout IS the saturated steady state):

  Part A - drive-axis scan, the primary measurement. The gate input is the
      single axis eps_norm in (0,1). For each channel k, the closure drive
      is x_k* = argmin w_k(x); at that drive the net excesses
      d_i = ch_i - b_i (i != k) are the shares that land in the other
      channels (net of each channel's own co-closure loss). Measured blend
      vs R-row k, residuals, ordering, verdict.
      The numpy replica is cross-validated against the solver's own
      compute_q_field over the whole sweep (exact float64 match).
  Part B - PDE site cross-check: standing Yang-deficit event, N=16,
      gate 'five'; measure ch_site at saturation, read the site's eps_norm,
      compare the site blend against the Part-A curve at that eps_norm,
      then release the deficit and verify the blend collapses (the
      redistribution exists only while the drive holds).

Verdicts: SUPPORTED if the measured blend matches the R-row within the
tolerance (0.02 = 2 percentage points; the algebra is exact float64, so any
larger residual is structural, not run resolution); PARTIAL if the
redistribution is present but the fractions deviate; NULL if the
redistribution is uniform or absent.

Usage: python two-fluid/run_rmatrix_redistribution.py
Output: runs/<id>_rmatrix/results.json
"""

import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV
import run_trauma_wake_lock as T

PHI_INV2 = PHI_INV ** 2          # 0.381966...—the doc's normalizer
SOLVER_PHI_INV2 = 0.382          # the solver's constructor default (line 299)
TOL = 0.02                       # verdict tolerance, 2 percentage points

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
BASELINE = np.array([PHI ** -k for k in (3, 4, 5, 6, 7)])
ETA = np.array([1.0, PHI_INV, PHI_INV, PHI_INV, PHI_INV])

NX = 999                          # drive-axis grid points
GRID = np.linspace(0.001, 0.999, NX)

# ── the doc's R-matrix (computed from the formula, cross-checked below) ──
R_MATRIX = np.zeros((5, 5))
for k in range(5):
    for i in range(5):
        if i != k:
            R_MATRIX[k, i] = BASELINE[i] / (BASELINE.sum() - BASELINE[k])
# doc-quoted values (rounded to 3 decimals), for the cross-check
DOC_ROWS = {
    'Wood':  (0.000, 0.447, 0.276, 0.171, 0.106),
    'Fire':  (0.567, 0.000, 0.217, 0.134, 0.083),
    'Earth': (0.500, 0.309, 0.000, 0.118, 0.073),
    'Metal': (0.466, 0.288, 0.178, 0.000, 0.068),
    'Water': (0.447, 0.276, 0.171, 0.106, 0.000),
}


def gate(x, phi_inv2=SOLVER_PHI_INV2):
    """The solver's 'five' gate algebra, vectorized over drive axis x.

    Replicates the rhs()/compute_q_field gate block line for line
    (`two-fluid/cassi_two_fluid_3d_gpu.py`, gate_model='five'):
    w-shape, wood_closed, active-openness allocation, ch_open.
    """
    x = np.atleast_1d(np.asarray(x, float))
    w1 = np.clip(1.0 - x, 0.0, 1.0)
    w2 = np.clip(4.0 * x * (1.0 - x), 0.0, 1.0)
    w3 = np.ones_like(x)
    w4 = x
    w5 = 1.0 / (1.0 + np.exp(-(x - 0.3) / 0.05))
    w = np.stack([w1, w2, w3, w4, w5], axis=0)               # (5, n)
    wood_closed = BASELINE[0] * (1.0 - w1)
    active_open = (BASELINE[1:, None] * w[1:]).sum(axis=0)
    redist = wood_closed * (BASELINE[1:, None] * w[1:]) / np.maximum(active_open, 1e-30)
    ch = BASELINE[:, None] * w
    ch[1:] += redist
    return w, ch


def ke_round(ch):
    """One simultaneous ke round—the solver's five_ke ring (numpy)."""
    excess = np.maximum(ch - BASELINE, 0.0)
    d = np.minimum(PHI_INV * excess, np.roll(ch, -2))
    return np.maximum(ch - np.roll(d, +2) + np.roll(d, +4), 0.0)


def blend_from_ch(ch, k):
    """Net-excess blend: shares of max(ch_i - b_i, 0) landing at i != k.

    The net excess is the total openness change of channel i relative to
    baseline—redistribution gain minus any co-closure loss of its own.
    """
    d = ch - BASELINE
    gains = np.where(np.arange(5) != k, np.maximum(d, 0.0), 0.0)
    tot = gains.sum()
    shares = gains / tot if tot > 0 else np.zeros(5)
    return shares, d


def ordering_match(measured, row, k):
    """Rank equality of the measured shares vs the row over the 4 receivers."""
    j = [i for i in range(5) if i != k]
    m_ord = [i for i in sorted(j, key=lambda i: -measured[i])]
    r_ord = [i for i in sorted(j, key=lambda i: -row[i])]
    return m_ord == r_ord


def verdict_for(shares, row, k, present):
    """SUPPORTED / PARTIAL / NULL for one closing channel."""
    if not present:
        return 'NULL'
    resid = np.abs(shares - row).max()
    if resid <= TOL:
        return 'SUPPORTED'
    return 'PARTIAL'


def build_fields_for_x(x, phi_inv2=SOLVER_PHI_INV2):
    """Consistent (ey, ei) fields whose gate input equals eps_norm = x.

    With M_qi = 1 and eps_sq = x(1+phi_inv2)/(1-x), eps_norm =
    eps_sq/(eps_sq + 1 + phi_inv2) = x exactly. The gate algebra never
    requires ei > 0, so no positivity constraint is imposed.
    """
    eps_sq = x * (1.0 + phi_inv2) / (1.0 - x)
    eps, m = np.sqrt(eps_sq), 1.0
    ey = (eps + PHI * m) / (1.0 + PHI)
    ei = (m - eps) / (1.0 + PHI)
    return ey, ei


# ── Part B PDE parameters ─────────────────────────────────────────────────
PDE_N = 16
PDE_STEPS_SAT = 300            # t = 0.3—saturation readout
PDE_STEPS_REL = 1700           # release tail to t = 2.0
PDE_REPORT = 50
PDE_R_SITE = 3.0


def run_pde_cross_check(rdir):
    """Standing Yang-deficit event at the site; measure the blend, release."""
    dev = torch.device('cpu')
    T.N, T.L, T.DT, T.STEPS = PDE_N, 2.0 * np.pi, 0.001, PDE_STEPS_SAT + PDE_STEPS_REL
    T.R_SITE = PDE_R_SITE
    solver = T.build_solver(dev)
    solver.gate_model = 'five'
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(PDE_N, PDE_R_SITE, dev)
    xc = torch.arange(PDE_N, dtype=torch.float64, device=dev) * (T.L / PDE_N)
    pattern = T.AMP * (torch.cos(2.0 * np.pi * xc / T.L).unsqueeze(1).unsqueeze(2)
                       * torch.cos(2.0 * np.pi * xc / T.L).unsqueeze(0).unsqueeze(2)
                       * torch.cos(2.0 * np.pi * xc / T.L).unsqueeze(0).unsqueeze(0))
    hist = []
    released = False
    t0 = time.time()
    for step in range(PDE_STEPS_SAT + PDE_STEPS_REL):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step == PDE_STEPS_SAT - 1:          # release: remove the deficit
            ey = torch.clamp(torch.fft.ifftn(ey_hat).real - pattern, min=1e-3)
            ey_hat = torch.fft.fftn(ey)
            released = True
        if step % PDE_REPORT == 0 or step in (PDE_STEPS_SAT - 1, PDE_STEPS_SAT + PDE_STEPS_REL - 1):
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            # site-mean gate input eps_norm (the Part-A drive axis)
            eps_sq = (ey - PHI * ei) ** 2
            m_qi = (ey + ei) ** 2
            xn = eps_sq / (eps_sq + m_qi + SOLVER_PHI_INV2 + 1e-30)
            d['x_site'] = float((xn * mask).sum() / mask.sum())
            d.update({'step': step, 't': step * T.DT, 'released': released})
            hist.append(d)
    print(f"  PDE cross-check: {PDE_STEPS_SAT + PDE_STEPS_REL} steps in "
          f"{time.time() - t0:.1f}s")
    with open(f"{rdir}/run_pde_site.json", "w") as f:
        json.dump({'hist': hist}, f, indent=1)
    return hist


def main():
    rdir = os.path.join("runs", datetime.now().strftime("%Y%m%d_%H%M%S") + "_rmatrix")
    os.makedirs(rdir, exist_ok=True)

    print("=" * 76)
    print("R-MATRIX (ADIABATIC REDISTRIBUTION) GATE-LEVEL TEST")
    print(f"baselines b_i = phi^-(2+i): {np.round(BASELINE, 4)}")
    print(f"tolerance: {TOL} (2 pp); gate algebra is exact float64—larger")
    print("residuals are structural (allocation rule), not run resolution")
    print("=" * 76)

    # ── doc row cross-check ────────────────────────────────────────────────
    doc_dev = max(abs(R_MATRIX[k] - np.array(DOC_ROWS[CHANNELS[k]])).max()
                  for k in range(5))
    print(f"\nR-matrix from the formula vs doc-quoted rows: max dev {doc_dev:.4f} "
          f"(doc rounds to 3 decimals)")

    # ── Part A: drive-axis scan ────────────────────────────────────────────
    w_all, ch_all = gate(GRID)                    # (5, NX)
    results = {'meta': {'claim': 'emotions-as-gate-configurations.md s4.2 R-matrix',
                        'gate_model': 'five', 'qi_memory': False,
                        'tolerance': TOL, 'nx': NX,
                        'phi_inv2_solver': SOLVER_PHI_INV2,
                        'phi_inv2_doc': PHI_INV2,
                        'doc_row_max_dev': doc_dev,
                        'baselines': BASELINE.tolist()},
               'r_rows': {CHANNELS[k]: R_MATRIX[k].tolist() for k in range(5)},
               'rows': {}, 'wood_extra': {}, 'pde': {}}

    print("\n── Part A: gate-level drive-axis scan ──")
    for k in range(5):
        ik = int(np.argmin(w_all[k]))
        xk = float(GRID[ik])
        wk = float(w_all[k, ik])
        dbk = float(BASELINE[k] * (1.0 - wk))
        ch = ch_all[:, ik]
        shares, d = blend_from_ch(ch, k)
        row = R_MATRIX[k]
        # attribution counterfactual: same state with the gate's single
        # redistribution term (wood_closed) zeroed
        xw = GRID[ik]
        ch_nr = np.array([BASELINE[0] * np.clip(1.0 - xw, 0.0, 1.0),
                          BASELINE[1] * np.clip(4.0 * xw * (1.0 - xw), 0.0, 1.0),
                          BASELINE[2],
                          BASELINE[3] * xw,
                          BASELINE[4] / (1.0 + np.exp(-(xw - 0.3) / 0.05))])
        nr_excess = float(np.maximum(ch_nr - BASELINE, 0.0).sum())
        if k != 0:
            if k == 2:
                verdict = 'NULL'
                notes = ("w3 = 1 identically—no drive closes Earth in this "
                         "gate shape (db_k = 0); no blend can be measured")
            else:
                verdict = 'NULL'
                notes = ("no gate term keys on this channel's closure; the "
                         "excess at its closure drive is the Wood-redistribution "
                         "tail (counterfactual with redist zeroed: excess "
                         f"{nr_excess:.2e})")
        elif shares.sum() < 1e-9:
            verdict = 'NULL'
            notes = "no redistribution fires at the Wood closure drive"
        else:
            verdict = verdict_for(shares, row, k, True)
            notes = f"redist term attributable: counterfactual excess {nr_excess:.2e}"
        ord_ok = ordering_match(shares, row, k) if verdict != 'NULL' else None
        zero_sh = [CHANNELS[i] for i in range(5) if i != k and row[i] > TOL and shares[i] < 1e-9]
        resid = np.abs(shares - row)
        rec = {'closure_drive_x': xk, 'w_k': wk, 'db_k': dbk,
               'measured_blend': shares.tolist(), 'row': row.tolist(),
               'residuals': resid.tolist(), 'max_abs_residual': float(resid.max()),
               'excess_sum_at_closure': float(np.maximum(d, 0.0).sum()),
               'ordering_match': ord_ok, 'zero_share_row_channels': zero_sh,
               'no_redist_counterfactual_excess': nr_excess,
               'notes': notes, 'verdict': verdict}
        results['rows'][CHANNELS[k]] = rec
        print(f"\n── closure: {CHANNELS[k]:6s} at drive x={xk:.4f} "
              f"(w_k={wk:.4f}, db_k={dbk:.4f}) ──")
        print(f"  measured blend: {np.round(shares, 3)}")
        print(f"  R-row         : {np.round(row, 3)}")
        print(f"  residuals     : {np.round(resid, 3)}   max={resid.max():.3f}")
        print(f"  ordering match: {ord_ok}   zero-share row channels: {zero_sh}")
        print(f"  counterfactual: redist-zeroed excess {nr_excess:.2e}")
        print(f"  verdict       : {verdict}   {notes}")

    # ── Wood extras ────────────────────────────────────────────────────────
    k = 0
    row = R_MATRIX[0]
    full = ch_all[:, -1]
    shares_full, _ = blend_from_ch(full, 0)
    best = min((float(np.abs(blend_from_ch(ch_all[:, i], 0)[0] - row).sum()),
                float(GRID[i]), blend_from_ch(ch_all[:, i], 0)[0].copy())
               for i in range(NX))
    ke_ch = ke_round(full)
    shares_ke, _ = blend_from_ch(ke_ch, 0)
    rest = gate(0.001)[1][:, 0]
    rest_excess = float(np.maximum(rest - BASELINE, 0).sum())
    wood_extra = {
        'full_closure_blend': shares_full.tolist(),
        'best_l1_drive': {'x': best[1], 'l1': best[0], 'blend': best[2].tolist()},
        'blend_vs_drive': [
            {'x': float(GRID[i]), 'blend': blend_from_ch(ch_all[:, i], 0)[0].tolist()}
            for i in range(0, NX, NX // 20)],
        'uniform_null_rejected': bool(
            shares_full[[1, 2, 3, 4]][shares_full[[1, 2, 3, 4]] > 0].std() > 1e-3),
        'five_ke_one_round_blend': shares_ke.tolist(),
        'release_resting_excess_sum': rest_excess,
    }
    results['wood_extra'] = wood_extra
    print("\n── Wood-closure detail ──")
    print(f"  full-closure blend (x→1): {np.round(shares_full, 3)} "
          f"(Fire co-closes: w2→0)")
    print(f"  best-L1 drive: x={best[1]:.4f}  L1={best[0]:.3f}  "
          f"blend={np.round(best[2], 3)}")
    print(f"  uniform-null rejected: {wood_extra['uniform_null_rejected']} "
          f"(3 unequal recipients at full closure)")
    print(f"  one ke round on the full-closure state -> blend "
          f"{np.round(shares_ke, 3)} (ke ring re-allocates excesses; the")
    print(f"  claim's row is the sheng layer alone)")
    print(f"  release (drive → 0): resting excess sum {rest_excess:.2e}—the")
    print(f"  blend exists only while the drive holds (quasi-static gate)")

    # ── cross-validation: replica vs the solver's own gate ─────────────────
    solver = ExpandingTwoFluid3DGPU(
        N=8, L=2.0 * np.pi, nu=0.0005, D=0.0002, lam=0.1, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True,
        qi_memory=False, device='cpu')
    solver.gate_model = 'five'
    xs_cv = GRID[::NX // 40]
    errs = []
    for x in xs_cv:
        ey, ei = build_fields_for_x(x)
        ey = torch.tensor([[[ey]]], dtype=torch.float64)
        ei = torch.tensor([[[ei]]], dtype=torch.float64)
        _, omq = solver.compute_q_field(ey, ei)
        _, ch_rep = gate(x)
        omq_rep = float((ETA * ch_rep[:, 0]).sum())
        errs.append(abs(float(omq[0, 0, 0]) - omq_rep))
    cv_max = max(errs)
    results['cross_validation'] = {'n_points': len(xs_cv),
                                   'max_one_minus_q_err': cv_max,
                                   'passed': bool(cv_max < 1e-12)}
    print(f"\n── cross-validation (replica vs solver.compute_q_field) ──")
    print(f"  {len(xs_cv)} drive points, max |one_minus_q - replica| = {cv_max:.2e} "
          f"{'OK' if cv_max < 1e-12 else 'FAIL'}")

    # ── Part B: PDE site cross-check ───────────────────────────────────────
    print("\n── Part B: PDE site cross-check (standing deficit, N=16) ──")
    hist = run_pde_cross_check(rdir)
    sat = min((d for d in hist if not d['released']), key=lambda d: abs(d['t'] - 0.3))
    rel = min((d for d in hist if d['released']), key=lambda d: abs(d['t'] - 0.35))
    end = hist[-1]
    ch_sat = np.array(sat['ch_open'])
    d_sat = ch_sat - BASELINE
    shares_site, _ = blend_from_ch(ch_sat, 0)
    x_site = sat['x_site']
    shares_curve, _ = blend_from_ch(gate(x_site)[1][:, 0], 0)
    curve_err = float(np.abs(shares_site - shares_curve).max())
    elev = [CHANNELS[i] for i in range(5) if d_sat[i] > 1e-4]
    dep = [CHANNELS[i] for i in range(5) if d_sat[i] < -1e-4]
    pde = {'N': PDE_N, 'x_site': x_site,
           'ch_site_sat': ch_sat.tolist(), 'dev_sat': d_sat.tolist(),
           'elevated': elev, 'depressed': dep,
           'measured_site_blend': shares_site.tolist(),
           'curve_blend_at_x': shares_curve.tolist(),
           'err_vs_curve': curve_err,
           'after_release_t035': {'ch': rel['ch_open'], 'eps_site': rel['eps_site']},
           'end_t2': {'ch': end['ch_open'], 'eps_site': end['eps_site']}}
    results['pde'] = pde
    print(f"  site x_eps ~ {x_site:.3f} (Wood w1 ~ {1 - x_site:.3f})")
    print(f"  ch_site(t=0.3): {np.round(ch_sat, 4)}   elevated: {elev}   "
          f"depressed: {dep}")
    print(f"  site blend: {np.round(shares_site, 3)}   "
          f"curve@x: {np.round(shares_curve, 3)}   err={curve_err:.3f}")
    print(f"  after release (t=0.35): ch {np.round(np.array(rel['ch_open']), 4)}")
    print(f"  t=2.0: ch {np.round(np.array(end['ch_open']), 4)}  "
          f"eps_site {end['eps_site']:.4f}")

    # ── overall verdict ────────────────────────────────────────────────────
    per_row = {CHANNELS[k]: results['rows'][CHANNELS[k]]['verdict'] for k in range(5)}
    overall = 'SUPPORTED' if all(v == 'SUPPORTED' for v in per_row.values()) else \
        ('PARTIAL' if any(v == 'PARTIAL' for v in per_row.values()) else 'NULL')
    results['verdict'] = {'overall': overall, 'per_row': per_row}
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 76)
    print("VERDICT: " + overall)
    for c in CHANNELS:
        print(f"  {c:6s} closure: {per_row[c]}")
    print("  The mechanism implements the sheng redistribution only for the")
    print("  Wood row (wood_closed = b1*(1-w1) in the gate block), and that")
    print("  row allocates by ACTIVE openness b_i*w_i, not the baseline b_i")
    print("  of the claim—Fire co-closes at strong drive (w2 -> 0) and")
    print("  receives zero instead of 44.7%; Earth/Metal/Water receive the")
    print("  whole blend in row order. Rows 2-5 have no gate term: those")
    print("  closures release no coherence to the other channels (NULL).")
    print(f"Results: {rdir}/results.json")
    print("=" * 76)


if __name__ == "__main__":
    main()
