#!/usr/bin/env python3
"""TS7: channel-manifold representability of the two-strand trace.

Target TS7 of `hypotheses/two-strand-five-channel-matter-organization.md`
sec 7: characterize the first-quadrant bound and decide whether an
Earth/Metal/Water-reaching extension exists without new parameters.  This
script is a synthetic sweep over the solver's own 'five'-gate formula
(replicated read-only by `run_trauma_wake_lock.channel_openness`, the same
replication the two-strand probe and ke-ring tests use) -- no PDE evolution
is needed, because every object of the audit is a function of the local
field state (ey, ei) and the 1e-3 positivity clamp.

Question: can the current mechanism layer (positive fields under the
clamp + gate_model 'five') reach all five pentagon channels, in either of
the two trace projections?

  P1 -- phase-angle projection (diagnostic-only partition of the
        conversion source by theta = atan2(ei, ey) onto the nearest
        pentagon vertex): theta is pinned to the first quadrant, so the
        reachable sectors are Wood (0 deg) and Fire (72 deg) only
        (`consciousness/trauma-as-frozen-gate.md` sec 10.8).
  P2 -- gate-weighted projection (conv_c = -lam eta_c ch_open_c eps,
        doc sec 1.3): ch_open is a function of the single scalar
            eps_norm = eps^2 / (eps^2 + M + phi^-2),  M = (ey+ei)^2,
        so the trace vector moves on a 1-D curve.  This script computes
        the dominant channel on that curve and the eps_norm interval
        reachable under the positivity clamp.

Checks:
  C0  gate_profile replication vs the solver's channel_openness (exact).
  C1  dominant eta-weighted channel vs eps_norm on [0, 1] (full curve),
      sector boundaries, never-dominant channels (closed-form
      inequalities verified numerically).
  C2  positive-field reachability: max eps_norm over (r, s) with
      ey, ei >= 1e-3, vs the analytic bound f(r) <= phi^2/(phi^2+1).
  C3  event geometries (init formulas only, exactly as the committed
      scripts initialize them): the five phase-channel bound targets
      (amp 1.6) and the Wood/Fire binary (amp 0.8) of
      `run_trauma_phase_channels.py`, and the two-strand lobe cores
      (E_RIDGE = 0.65, BETA = 0.3) of `run_two_strand_probe.py`.
  C4  direction-blindness: a matched (M, |eps|) pair with opposite
      imbalance sign produces IDENTICAL ch_open (gate blind to the event
      direction) while the phase-angle sectors differ.
  C5  published two-strand run record 20260806_204217_two_strand:
      per-strand argmax of conv_gate vs the phase-angle dominant channel
      at t = 0, 2, 4, and the resulting sheng/ke relations.

Verdict: the mechanism layer is two-sector in BOTH projections (Wood,
Fire); Earth dominance needs eps_norm > 0.815, unreachable with positive
fields (max 0.724); Metal and Water never dominate at any imbalance, so
even a clamp relaxation gives at most three sectors.  Missing degrees of
freedom are documented in the verdict, not added here (TS7 stops at the
representability boundary; no solver extension).

Usage: python two-fluid/ts7_channel_manifold.py
Output: runs/<rid>_ts7_manifold/results.json + console report
"""

import os
import sys
import json
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T

PHI = T.PHI
PI = T.PHI_INV
CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
ETA = np.array([1.0, PI, PI, PI, PI])
CH_ANGLES_DEG = np.degrees(T.CH_ANGLES)      # [0, 72, 144, 216, 288]


def gate_profile(eps_norm):
    """Exact 'five'-gate replication (solver formula, read-only).

    Mirrors cassi_two_fluid_3d_gpu.compute_q_field 'five' branch and
    run_trauma_wake_lock.channel_openness: w1..w5 from eps_norm, baseline
    b_j = phi^-(3+j) with zero-based j in {0..4} (the one-based doctrine
    is b_i = phi^-(i+2), i = 1..5, giving the same
    {phi^-3, phi^-4, phi^-5, phi^-6, phi^-7}), eta couplings,
    Wood-closure redistribution.
    Returns (ch_open[5], one_minus_q) as arrays over eps_norm.
    """
    en = np.atleast_1d(eps_norm).astype(float)
    w1 = np.clip(1.0 - en, 0.0, 1.0)
    w2 = np.clip(4.0 * en * (1.0 - en), 0.0, 1.0)
    w3 = np.ones_like(en)
    w4 = en
    w5 = 1.0 / (1.0 + np.exp(-(en - 0.3) / 0.05))
    b = np.array([PHI ** -k for k in (3, 4, 5, 6, 7)])
    w = np.stack([w1, w2, w3, w4, w5], axis=0)
    wood_closed = b[0] * (1.0 - w1)                      # per eps_norm point
    active_open = np.maximum((b[1:, None] * w[1:]).sum(axis=0), 1e-30)
    # proportional redistribution: wood's closed share reopens onto each
    # other channel in proportion to its own b_c*w_c (solver formula)
    redist = (b[1:, None] * w[1:]) * (wood_closed / active_open)[None, :]
    ch = b[:, None] * w
    ch[1:] += redist
    return ch, (ETA[:, None] * ch).sum(axis=0)


def eps_norm_of(ey, ei):
    """eps_norm for a field state, per the solver formula."""
    M = (ey + ei) ** 2
    eps2 = (ey - PHI * ei) ** 2
    return eps2 / (eps2 + M + PI ** 2)


def phase_sector(theta_deg):
    """Nearest pentagon channel for an angle in degrees."""
    d = np.abs((theta_deg - CH_ANGLES_DEG + 180.0) % 360.0 - 180.0)
    return int(np.argmin(d))


def sector_of(theta_deg):
    return CHANNELS[phase_sector(theta_deg)]


def main():
    results = {'meta': {'target': 'TS7 channel-manifold representability',
                        'gate': "five (solver formula, replicated)",
                        'clamp': 'ey, ei >= 1e-3 (solver rk2_step)'},
               'C0': {}, 'C1': {}, 'C2': {}, 'C3': {}, 'C4': {}, 'C5': {}}

    # ── C0: replication check against the solver's channel_openness ───────
    import torch
    rng = np.random.default_rng(0)
    max_err = 0.0
    for _ in range(8):
        ey = rng.uniform(1e-3, 3.0)
        ei = rng.uniform(1e-3, 3.0)
        en = eps_norm_of(ey, ei)
        ch_mine, _ = gate_profile(np.array([en]))
        ch_ref, _ = T.channel_openness(torch.full((2, 2, 2), ey,
                                                  dtype=torch.float64),
                                       torch.full((2, 2, 2), ei,
                                                  dtype=torch.float64))
        err = np.abs(ch_mine[:, 0] -
                     np.array([float(v) for v in ch_ref[:, 0, 0, 0]])).max()
        max_err = max(max_err, err)
    results['C0'] = {'random_states': 8,
                     'max_abs_diff_vs_solver': float(max_err)}
    print("C0  gate_profile vs solver channel_openness: "
          f"max |diff| = {max_err:.2e} "
          f"({'EXACT' if max_err < 1e-12 else 'MISMATCH'})")

    # ── C1: the gate curve -- dominant channel vs eps_norm on [0, 1] ──────
    en_grid = np.linspace(0.0, 1.0, 200001)
    ch, oq = gate_profile(en_grid)
    wc = ETA[:, None] * ch
    dom = wc.argmax(axis=0)
    sw = np.where(np.diff(dom) != 0)[0]
    sectors = [(float(en_grid[i]), CHANNELS[dom[i]], CHANNELS[dom[i + 1]])
               for i in sw]
    never = [CHANNELS[c] for c in range(5) if (dom == c).sum() == 0]
    dom_intervals = []
    for c in range(5):
        m = dom == c
        if m.any():
            dom_intervals.append((CHANNELS[c], float(en_grid[m][0]),
                                  float(en_grid[m][-1])))
    results['C1'] = {'sector_transitions': sectors,
                     'dominance_intervals': dom_intervals,
                     'never_dominant': never,
                     'dominant_at_epsnorm_0': CHANNELS[dom[0]],
                     'dominant_at_epsnorm_1': CHANNELS[dom[-1]]}
    print("\nC1  gate curve: dominant eta*ch_open channel vs eps_norm")
    for ch_name, lo, hi in dom_intervals:
        print(f"    {ch_name:5s} dominant for eps_norm in "
              f"[{lo:.4f}, {hi:.4f}]")
    if never:
        print(f"    NEVER dominant at any eps_norm in [0,1]: "
              f"{', '.join(never)}")
    metal_earth = wc[3] - wc[2]
    water_earth = wc[4] - wc[2]
    results['C1']['max_Metal_minus_Earth'] = float(metal_earth.max())
    results['C1']['max_Water_minus_Earth'] = float(water_earth.max())
    print(f"    max(eta*ch_open[Metal]-eta*ch_open[Earth]) = "
          f"{metal_earth.max():+.4f} (must be < 0)")
    print(f"    max(eta*ch_open[Water]-eta*ch_open[Earth]) = "
          f"{water_earth.max():+.4f} (must be < 0)")

    # ── C2: positive-field reachability under the clamp ───────────────────
    rs = np.geomspace(1e-3, 1e3, 2001)       # r = ey / ei
    ss = np.geomspace(1e-3, 1e3, 2001)       # s = ei
    r, s = np.meshgrid(rs, ss)
    en = (s * s * (r - PHI) ** 2 /
          (s * s * ((r - PHI) ** 2 + (r + 1.0) ** 2) + PI ** 2))
    en_max = float(en.max())
    analytic = float(PHI ** 2 / (PHI ** 2 + 1.0))
    earth_at = [lo for ch_name, lo, hi in dom_intervals
                if ch_name == 'Earth'][0]
    results['C2'] = {'max_eps_norm_positive_fields': en_max,
                     'analytic_bound_f(r<=0)': analytic,
                     'earth_sector_threshold': earth_at,
                     'earth_reachable': en_max > earth_at,
                     'reachable_dominant': [c for c, lo, hi in dom_intervals
                                            if lo <= en_max]}
    print("\nC2  positive-field reachability (clamp ey, ei >= 1e-3)")
    print(f"    max eps_norm over (r, s): {en_max:.6f} "
          f"(analytic bound phi^2/(phi^2+1) = {analytic:.6f})")
    print(f"    Earth dominance needs eps_norm > {earth_at:.4f} "
          f"-> Earth {'REACHABLE' if en_max > earth_at else 'UNREACHABLE'}")
    print(f"    reachable dominant set: "
          f"{results['C2']['reachable_dominant']}")

    # ── C3: event geometries (init formulas of the committed scripts) ─────
    def clamp(ey, ei):
        return max(ey, 1e-3), max(ei, 1e-3)

    def gdom_of(en):
        idx = min(int(en * 200000 + 0.5), 200000)
        return CHANNELS[int(wc[:, idx].argmax())]

    c3 = {}
    print("\nC3  event cores: eps_norm | gate-dominant | theta | phase-sector")
    targets = {'Wood': 0.0, 'Fire': 72.0, 'Earth': 144.0,
               'Metal': 216.0, 'Water': 288.0}
    for ch_name, tgt in targets.items():
        best, best_err = None, 1e9
        for d in np.linspace(0.0, 2.0 * np.pi, 1440):
            th = np.degrees(np.arctan2(PI + 1.6 * np.sin(d),
                                       1.0 + 1.6 * np.cos(d))) % 360.0
            err = abs((th - tgt + 180.0) % 360.0 - 180.0)
            if err < best_err:
                best, best_err = d, err
        eyc, eic = clamp(1.0 + 1.6 * np.cos(best),
                         PI + 1.6 * np.sin(best))
        en = eps_norm_of(eyc, eic)
        th = np.degrees(np.arctan2(eic, eyc)) % 360.0
        c3[f'bound_{ch_name}'] = {
            'delta_deg': float(np.degrees(best)),
            'ey': float(eyc), 'ei': float(eic),
            'eps_norm': float(en), 'gate_dominant': gdom_of(en),
            'theta_deg': float(th), 'phase_sector': sector_of(th)}
        print(f"    bound {ch_name:5s} (tgt {tgt:5.1f}): "
              f"eps_norm={en:.3f} gate={gdom_of(en):5s} "
              f"theta={th:5.1f} phase={sector_of(th):5s}")
    for tag, d in [('fire', np.pi), ('wood', 1.5 * np.pi)]:
        eyc, eic = clamp(1.0 + 0.8 * np.cos(d), PI + 0.8 * np.sin(d))
        en = eps_norm_of(eyc, eic)
        th = np.degrees(np.arctan2(eic, eyc)) % 360.0
        c3[f'binary_{tag}'] = {
            'ey': float(eyc), 'ei': float(eic),
            'eps_norm': float(en), 'gate_dominant': gdom_of(en),
            'theta_deg': float(th), 'phase_sector': sector_of(th)}
        print(f"    binary {tag:4s}: eps_norm={en:.3f} gate={gdom_of(en):5s} "
              f"theta={th:5.1f} phase={sector_of(th):5s}")
    er, beta = 0.65, 0.3
    for tag, g1, g2 in [('lobe_A', 1.0, 0.0), ('lobe_B', 0.0, 1.0)]:
        rho = (1.0 + PI) * (1.0 + beta * (g1 + g2))
        eps = er * (g1 - g2)
        eyc, eic = clamp((PHI * rho + eps) / (1.0 + PHI),
                         (rho - eps) / (1.0 + PHI))
        en = eps_norm_of(eyc, eic)
        th = np.degrees(np.arctan2(eic, eyc)) % 360.0
        c3[tag] = {'ey': float(eyc), 'ei': float(eic),
                   'eps_norm': float(en), 'gate_dominant': gdom_of(en),
                   'theta_deg': float(th), 'phase_sector': sector_of(th)}
        print(f"    {tag:7s}: eps_norm={en:.3f} gate={gdom_of(en):5s} "
              f"theta={th:5.1f} phase={sector_of(th):5s}")
    results['C3'] = c3

    # ── C4: direction-blindness of the gate ───────────────────────────────
    S, eps0 = 2.5, 0.65
    ey_p = (PHI * S + eps0) / (1.0 + PHI)
    ei_p = (S - eps0) / (1.0 + PHI)
    ey_m = (PHI * S - eps0) / (1.0 + PHI)
    ei_m = (S + eps0) / (1.0 + PHI)
    wc_p = ETA[:, None] * gate_profile(np.array([eps_norm_of(ey_p, ei_p)]))[0]
    wc_m = ETA[:, None] * gate_profile(np.array([eps_norm_of(ey_m, ei_m)]))[0]
    conv_p = -T.LAM * wc_p[:, 0] * (ey_p - PHI * ei_p)
    conv_m = -T.LAM * wc_m[:, 0] * (ey_m - PHI * ei_m)
    th_p = np.degrees(np.arctan2(ei_p, ey_p))
    th_m = np.degrees(np.arctan2(ei_m, ey_m))
    blind = float(np.abs(wc_p - wc_m).max())
    results['C4'] = {
        'max_gate_weight_diff': blind,
        'conv_plus': conv_p.tolist(), 'conv_minus': conv_m.tolist(),
        'theta_plus_deg': float(th_p), 'theta_minus_deg': float(th_m),
        'phase_plus': sector_of(th_p), 'phase_minus': sector_of(th_m)}
    print("\nC4  direction-blindness (matched M, |eps|, opposite sign)")
    print(f"    max |eta*ch_open(+) - eta*ch_open(-)| = {blind:.2e} "
          f"({'IDENTICAL' if blind < 1e-12 else 'DIFFER'})")
    print(f"    conv(+eps): {np.round(conv_p, 5)}")
    print(f"    conv(-eps): {np.round(conv_m, 5)}  (sign flip only)")
    print(f"    theta: +eps -> {th_p:.1f} deg ({sector_of(th_p)}), "
          f"-eps -> {th_m:.1f} deg ({sector_of(th_m)})")

    # ── C5: published two-strand run record ───────────────────────────────
    rec = 'runs/20260806_204217_two_strand/results.json'
    c5 = {}
    if os.path.exists(rec):
        with open(rec) as f:
            rec_data = json.load(f)
        rel_names = {0: 'same', 1: 'sheng', 2: 'ke', 3: 'ke-rev',
                     4: 'sheng-rev'}
        for t_t, tr in rec_data['two_lobe']['traces'].items():
            sA, sB = tr['strand_A'], tr['strand_B']
            ia, ib = int(np.argmax(np.abs(sA['conv_gate']))), \
                     int(np.argmax(np.abs(sB['conv_gate'])))
            c5[t_t] = {'gate_dominant_A': CHANNELS[ia],
                       'gate_dominant_B': CHANNELS[ib],
                       'gate_sheng_ke': rel_names[(ib - ia) % 5],
                       'phase_dominant_A': sA['dominant'],
                       'phase_dominant_B': sB['dominant'],
                       'phase_sheng_ke': tr['sheng_ke']}
            print(f"\n    t={t_t}: gate-weighted -> {CHANNELS[ia]}/"
                  f"{CHANNELS[ib]} ({rel_names[(ib - ia) % 5]}); "
                  f"phase-angle -> {sA['dominant']}/{sB['dominant']} "
                  f"({tr['sheng_ke']})")
        results['C5'] = {'record': rec, 'traces': c5,
                         'channel_transitions': rec_data['two_lobe']
                         ['channel_transitions']}
        print(f"    channel_transitions over the run: "
              f"{results['C5']['channel_transitions']}")
    else:
        results['C5'] = {'record': rec, 'missing': True}
        print(f"\nC5  run record {rec} not present -- skipped "
              f"(regenerate with two-fluid/run_two_strand_probe.py)")

    # ── Verdict ────────────────────────────────────────────────────────────
    print("\n=== VERDICT (TS7) ===")
    print(f"Gate-weighted projection: reachable dominant set = "
          f"{results['C2']['reachable_dominant']} (2/5).")
    print(f"Phase-angle projection: reachable sectors = "
          f"['Wood', 'Fire'] (2/5).")
    print("No five-sector manifold in the current mechanism layer; "
          "both projections are two-sector (Wood, Fire).")
    print("Missing degrees of freedom:")
    print("  DOF-1 (clamp): a signed/negative field component -- needed "
          "for the far phase arc AND for eps_norm > "
          f"{results['C2']['earth_sector_threshold']:.3f} (Earth "
          "dominance).  Relaxing the clamp alone gives at most three "
          "sectors (Wood, Fire, Earth).")
    print("  DOF-2 (gate): an angle-dependent gate coupling -- the event "
          "direction enters the 'five' gate only through eps^2, so the "
          "gate is direction-blind and Metal/Water can never lead "
          "(eta*ch_open[Metal], eta*ch_open[Water] < "
          "eta*ch_open[Earth] identically).  Five-sector dominance "
          "requires a gate-model change, i.e. new model content, not a "
          "parameter re-fit.")

    # ── Save ──────────────────────────────────────────────────────────────
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_ts7_manifold"
    os.makedirs(rdir, exist_ok=True)
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")


if __name__ == "__main__":
    main()
