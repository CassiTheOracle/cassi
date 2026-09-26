#!/usr/bin/env python3
"""Multi-scale axial soliton probe (Amendment 2): does a phi-spaced stack
retain a standing-wave envelope under prescribed density-plane-angle winding?

Run:  python two-fluid/run_soliton_axial_stack_probe.py
      (--steps N and --arm TAG repeatable override)

Probe scope: the script specifies per-layer density-plane angles and a
coherence-excess profile, then evolves the canonical solver on a fresh arm.
It measures envelope retention and records the `J_z`/`F_c` diagnostics from the
read-only lattice-stack machinery. Those values are named spatial projections
of the density-doublet diagnostic; a constitutive map would be required for
an inter-rung transport interpretation.

Theory context (from `foundations/qi-flow-double-helix.md`):

    J_z = [J_d]_z = (E_Y² + E_I²) ∂_z θ_d
        (named axial projection of the density-plane current)
    layer angle increment dtheta selected by the arm
    density-angle relaxation Δθ_d(ε_0) recorded as an angular response

The density-plane angle is the state coordinate evolved by this probe.
The `dtheta` input selects the closure increment (the default is 2pi/5;
the π step is the P_parallel=2 comparison). The spatial projections are
diagnostics of the simulated field; they do not supply a scale-transport
law.

The single-scale Wave-0 probe has no cascade extent, density-plane-angle
advance, or lower-rung coupling. This probe extends the shipped
lattice-stack machinery (`run_lattice_stack_probe`, read-only—zero new terms,
canonical solver, fresh solver per arm) with an axial, phi-spaced multi-rung
stack carrying a per-layer density-plane-angle increment and a coherence
excess prescribed at the fine (lower-rung) end.

Geometry (this probe's extension):
  - M two-lobe coherence layers along z (the string axis), positions z_i set
    by the CASCADE ladder around the lump center: innermost gap s_min (fine,
    lower rungs), gaps grow by phi outward: gap_k = s_min * phi^k.
  - per-layer density-plane angle theta_{d,i} = i*dtheta (closure steps:
    2pi/5 pentagon, pi/5 decagon, and pi for the P_parallel=2 comparison).
  - a coherence-excess perturbation eps0 stronger at the fine shells
    (epsilon_0 * exp(-|i|*phi^-1)); the density-angle relaxation response
    Delta-theta_d(eps_0) is recorded in the axial diagnostics.

Arms (pairwise phi-spacing x fine-excess, vs uniform space + no excess):

  A_phi_en  phi-spaced + density-angle increment + fine-excess
             -- the owner's full mechanism
  A_phi_ne  phi-spaced + density-angle increment, no excess
             -- is the fine-excess load-bearing?
  A_uni_en  uniform + density-angle increment + fine-excess
             -- is phi-spacing load-bearing?
  A_uni_ne  uniform + density-angle increment, no excess
             -- base control (uniform stack)
  m1        single layer (M=1) -- known TS1 escape control

Verdict (extends pre-reg L5): H-HOLDS iff A_phi_en keeps C_abs(40) >= 0.5 and
A_peak(40)/A_peak(0) >= 0.5 while A_uni_ne and m1 escape (C_abs -> ~0) and
mass/charge drift <= 1e-6. Attribution: which element (phi-spacing /
density-angle increment / fine-excess) is necessary, by pairwise contrast.

Output: runs/<rid>_soliton_axial/run_<arm>.json + results.json
(commit the script only; runs/ is gitignored).
"""

import os
import sys
import json
import time
import math
import argparse
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_lattice_stack_probe as L
import run_trauma_wake_lock as T
import run_two_strand_probe as P

PHI = (1.0 + math.sqrt(5)) / 2.0
PHI_INV = 1.0 / PHI

SIG = L.SIG
SEP = L.SEP
E_RIDGE = L.E_RIDGE
BETA = L.BETA
RHO0 = L.RHO0
CHANNELS = L.CHANNELS

STEPS = 40000          # t = 40000 * 0.001 = 40 = 2/lambda (lock timescale)
N = T.N

PHI_STEP = 2.0 * math.pi / 5.0   # pentagon step (R = phi); decagon pi/5; pi anti


def phi_spaced_zs(N, M, s_min=3.0):
    """Axial positions of M shells spaced by the cascade ladder (gaps grow by
    phi outward from the fine center). Returns zs (list), each within [0,N).
    M odd preferred for symmetry about the center. Fine shells (small gaps,
    lower rungs) sit at the center; coarse shells (large gaps, upper rungs)
    at the edges -- the 'lower scales feed up' ordering."""
    cx = N / 2.0
    if M == 1:
        return [cx]
    half = (M - 1) // 2
    # build symmetric positions
    left = [cx]
    right = [cx]
    for k in range(half):
        # gap between consecutive shells; outer gaps larger
        g = s_min * PHI ** k
        left = [left[0] - g] + left
        right = right + [right[-1] + g]
    zs = left + right[1:]
    return [z % N for z in zs]


def ecc_weights(M, eps0, phi_inv=PHI_INV):
    """Per-shell coherence-excess weight: strongest at the fine (center)
    shells, decaying phi^-|i| outward. eps_count = number of center shells
    that get the full eps0."""
    w = []
    half = (M - 1) / 2.0
    for i in range(M):
        d = abs(i - half)
        w.append(eps0 * phi_inv ** d)
    return w


def stack_init_ext(solver, M, dtheta, zs, ecc=None):
    """M two-lobe layers along z at *given* positions zs (phi-spaced or
    uniform), per-layer density-plane angle theta_{d,i} = i*dtheta, plus an
    optional per-shell coherence-excess ecc[i] added to the eps perturbation.
    The excess profile is prescribed at the fine end and its response is
    recorded by the spatial diagnostics. Reuses the base two-lobe
    construction.

    ecc = None  -> exact base layer shape (no added excess).
    Returns (ey_hat, ei_hat, u_hat, zs).
    """
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - SEP / 2.0, cx + SEP / 2.0
    rho = torch.full((N_, N_, N_), RHO0, dtype=torch.float64, device=dev)
    eps = torch.zeros_like(rho)
    offsets = (0.0, float(N_), -float(N_))
    for i, zi in enumerate(zs):
        th = i * dtheta
        ct, st = math.cos(th), math.sin(th)
        g1 = torch.zeros_like(X)
        g2 = torch.zeros_like(X)
        for off in offsets:
            zc = Z - zi + off
            g1 = g1 + torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * SIG ** 2))
            g2 = g2 + torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * SIG ** 2))
        gp = g1 + g2
        gm = g1 - g2
        rho += RHO0 * BETA * gp * ct - E_RIDGE * gm * st
        e_delta = ecc[i] if ecc is not None else 0.0
        # the excess rides the density doublet in the density-plane
        # representation: add it to the eps perturbation (positive eps =
        # EY > phi*EI, coherence excess)
        eps += RHO0 * BETA * gp * st + E_RIDGE * gm * ct + e_delta * gp
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat, zs


def run_case_ext(solver, M, dtheta, zs, ecc, tag, outdir, steps=STEPS):
    """Evolve one arm (fresh solver), recording diagnostics -- mirrors the base
    run_case but with the extended init (zs + ecc)."""
    print(f"\n=== run: {tag} (M={M}, dtheta={dtheta:.4f} rad, "
          f"zs=[{', '.join(f'{z:.1f}' for z in zs)}], "
          f"ecc={'' if ecc is None else '[' + ', '.join(f'{e:.3f}' for e in ecc) + ']'}, "
          f"t={steps * T.DT}) ===")
    ey_hat, ei_hat, u_hat, zs2 = stack_init_ext(solver, M, dtheta, zs, ecc)
    centers = [solver.N / 2.0 - SEP / 2.0, solver.N / 2.0 + SEP / 2.0]
    windows = L.layer_windows(solver.N, zs2, solver.device)

    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    r0 = L.resonance_t0(solver, ey0, ei0, windows, zs2, M, dtheta)
    r0['min_ey'] = float(ey0.min())
    r0['min_ei'] = float(ei0.min())
    print(f"  t=0: A_tot={r0['A_tot']:.3f} ratio={r0['ratio_vs_analytic']:.4f} "
          f"R={L.resonance(M, dtheta):.4f} | adv_dev={r0['max_advance_dev']:.4f} "
          f"| min {r0['min_ey']:.4f}/{r0['min_ei']:.4f} "
          f"| floor {r0['floor_ey']}/{r0['floor_ei']}")

    t0 = time.time()
    hist = []
    prev = None
    profiles = {}
    S0 = L.slab_phasor(ey0, ei0, RHO0).cpu().numpy()
    J0, F0, _, _ = L.current_profiles(solver, ey0, ei0, zs2)
    profiles['0.0'] = {'A': np.abs(S0).tolist(), 'arg': np.angle(S0).tolist(),
                       'Jz': J0.tolist(), 'Fc': F0.tolist()}

    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = L.measure(solver, ey, ei, rho_prof, centers, prev,
                          windows, zs2, RHO0 if step == 0 else float((ey + ei).mean()))
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)
            if abs(step * T.DT - 4.0) < 0.6 or abs(step * T.DT - 40.0) < 0.6 \
                    or step == steps - 1:
                rho_m = float((ey + ei).mean())
                Sn = L.slab_phasor(ey, ei, rho_m).cpu().numpy()
                Jn, Fn, _, _ = L.current_profiles(solver, ey, ei, zs2)
                profiles[f"{step * T.DT:.1f}"] = {
                    'A': np.abs(Sn).tolist(), 'arg': np.angle(Sn).tolist(),
                    'Jz': Jn.tolist(), 'Fc': Fn.tolist()}
            if step % 1000 == 0 or step == steps - 1:
                s0 = d['strands'][0]
                print(f"  t={step*T.DT:6.2f} | d={d['d']:6.3f} Rc={d['Rc']:6.2f} "
                      f"| A_peak={d['A_peak']:7.2f} C_abs={d['C_abs']:+.3f} "
                      f"wind={d['winding']:+6.3f} |Jz|={d['Jz_abs_mean']:7.1f} "
                      f"q_mid={d['q_mid']:.4f} | mass drift "
                      f"{(d['mass'] - hist[0]['mass'])/max(hist[0]['mass'],1e-30):.2e}")
    elapsed = time.time() - t0
    print(f"  [{tag}] {steps} steps in {elapsed:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'M': M, 'dtheta': dtheta, 'zs': zs2,
                       'ecc': None if ecc is None else ecc, 'steps': steps,
                       'R': L.resonance(M, dtheta),
                       'resonance_t0': r0, 'profiles': profiles,
                       'hist': hist}, f, indent=1)
    return {'tag': tag, 'M': M, 'dtheta': dtheta, 'elapsed': elapsed,
            'resonance_t0': r0, 'hist': hist, 'profiles': profiles}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS)
    parser.add_argument('--arm', action='append', default=None)
    parser.add_argument('--depth-sweep', action='store_true',
                        help='retention-vs-rung-depth: phi-spaced + pentagon + '
                             'fine-excess at M in {7,9,11} with s_min scaled '
                             'to fit the box (tests owner: more cascade rungs '
                             '=> more stable envelope, i.e. cascade suppression)')
    args = parser.parse_args()
    steps = args.steps

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={N}  lam={T.LAM}  t={steps * T.DT}  "
          f"gate='five'  SIG={SIG}  SEP={SEP}  E_RIDGE={E_RIDGE}  BETA={BETA}")

    if args.depth_sweep:
        # s_min per M: outer offset = s_min * sum_k phi^k (half-rungs) must <= N/2.
        # M chosen NON-degenerate at 2pi/5 (M%5 != 0 -> R != 0).
        smin = {7: 3.0, 9: 2.4, 11: 1.5}
        depth = []
        for M_ in sorted(smin):
            zs = phi_spaced_zs(N, M_, smin[M_])
            assert len(zs) == M_, f"phi_spaced_zs({M_}) -> {len(zs)}"
            depth.append((f"d{M_}", M_, PHI_STEP, zs, ecc_weights(M_, 0.30)))
        arms = depth
        print("DEPTH SWEEP (phi-spaced + pentagon + fine-excess): "
              + ", ".join(a[0] for a in arms))
    else:
        M = 7                       # odd symmetric phi-stack; pentagon 2pi/5 -> R = phi
        #                             (non-degenerate; M=5+2pi/5 exactly cancels, R=0)
        zs_phi = phi_spaced_zs(N, M, s_min=3.0)
        spacing = N / M
        zs_uni = [N / 2.0 + (i - (M - 1) / 2.0) * spacing for i in range(M)]
        eps0 = 0.30                 # fine-end coherence excess (E_RIDGE-scaled)
        arms = [
            ('A_phi_en', M, PHI_STEP, zs_phi, ecc_weights(M, eps0)),
            ('A_phi_ne', M, PHI_STEP, zs_phi, None),
            ('A_uni_en', M, PHI_STEP, zs_uni, ecc_weights(M, eps0)),
            ('A_uni_ne', M, PHI_STEP, zs_uni, None),
            ('m1',      1, 0.0,     [N / 2.0], None),
        ]
        print("Arms: " + ", ".join(a[0] for a in arms))
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_soliton_axial"
    os.makedirs(rdir, exist_ok=True)

    runs = []
    for tag, M_, dtheta, zs, ecc in arms:
        solver = T.build_solver(device)     # fresh solver per arm
        r = run_case_ext(solver, M_, dtheta, zs, ecc, tag, rdir, steps)
        r['summary'] = L.summarize_arm(r)
        runs.append(r)

    # Self-lock verdict from the summaries.
    print("\n=== SOLITON-AXIAL (Amendment 2) t=40 SUMMARY ===")
    for r in runs:
        s = r['summary']
        print(f"  {r['tag']:9s}: t4 d={s['t4']['d']:6.2f} C_abs={s['t4']['C_abs']:+.3f} "
              f"A_ratio4={s['A_peak_ratio_t4']:.3f} | t40 d={s['t40']['d']:6.2f} "
              f"C_abs={s['t40']['C_abs']:+.3f} A_ratio40={s['A_peak_ratio_t40']:.3f} "
              f"wind40={s['t40']['winding']:+.3f} |Jz|0={r['hist'][0]['Jz_abs_mean']:8.1f} "
              f"mass_drift={s['mass_drift']:.1e}")

    by_tag = {r['tag']: r for r in runs}
    results_meta = {'N': N, 'lam': T.LAM, 'dt': T.DT,
                    't_end': runs[0]['hist'][-1]['t'],
                    'gate_model': 'five (solver)',
                    'geometry': 'axial cascade stack',
                    'amendment': '2'}

    if args.depth_sweep:
        # retention-vs-rung-depth: does more cascade rungs stabilize the
        # envelope (the cascade-suppression mechanism the owner named)?
        order = sorted(by_tag, key=lambda t: int(t[1:]))
        rows = []
        trend_mono_up = True
        prev = None
        for tag in order:
            s = by_tag[tag]['summary']
            c40 = s['t40']['C_abs']
            a40 = s['A_peak_ratio_t40']
            rows.append({'M': int(tag[1:]), 'C_abs_t40': c40,
                         'A_ratio_t40': a40, 'Jz0': by_tag[tag]['hist'][0]['Jz_abs_mean'],
                         'mass_drift': s['mass_drift']})
            print(f"  depth {tag}: M={tag[1:]:>2} C_abs(40)={c40:+.3f} "
                  f"A_ratio(40)={a40:.3f} |Jz|0={by_tag[tag]['hist'][0]['Jz_abs_mean']:7.1f}")
            if prev is not None and c40 <= prev:
                trend_mono_up = False
            prev = c40
        # The claim: envelope retention improves (C_abs(40) non-decreasing) as
        # the number of cascade rungs M increases.
        claim = ('SUPPORTS' if rows[-1]['C_abs_t40'] > rows[0]['C_abs_t40'] + 0.05
                 else ('WEAK-SUPPORTS' if trend_mono_up else 'DOES NOT SUPPORT'))
        print(f"\n=== CASCADE-SUPPRESSION DEPTH VERDICT: {claim} ===")
        print("(more rungs -> higher C_abs(40) = coherence structure survives "
              "longer = the depth scaling is the cascade-suppression mechanism)")
        print(f"Results: {rdir}/results.json")
        results = dict(results_meta)
        results.update({
            'mode': 'depth-sweep', 'rungs': {t[1:]: r['summary'] for t, r in by_tag.items()},
            'retention_vs_M': rows,
            'verdict': claim,
            'verdict_note': 'C_abs(40) non-decreasing with rung count M = the '
                            'envelope is more stable with more cascade rungs, '
                            'i.e. cascade suppression (phi^-1 per rung coupling).'})
    else:
        a_ok = ('A_phi_en' in by_tag and
                by_tag['A_phi_en']['summary']['t40']['C_abs'] >= 0.5 and
                by_tag['A_phi_en']['summary']['A_peak_ratio_t40'] >= 0.5 and
                by_tag['A_phi_en']['summary']['mass_drift'] <= 1e-6)
        uni_esc = ('A_uni_ne' in by_tag and
                   by_tag['A_uni_ne']['summary']['t40']['C_abs'] < 0.05)
        m1_esc = ('m1' in by_tag and
                  not by_tag['m1']['summary']['t40']['two_hump']['present'])
        verdict = 'H-HOLDS' if (a_ok and uni_esc and m1_esc) else 'H-DISPERSES'
        expl = []
        if a_ok:
            expl.append("A_phi_en holds envelope to t=40")
        else:
            expl.append("A_phi_en does not hold envelope to t=40")
        if uni_esc:
            expl.append("uniform control escapes")
        else:
            expl.append("uniform control does NOT escape")
        if m1_esc:
            expl.append("single-layer m1 escapes (TS1, expected)")
        else:
            expl.append("m1 does not escape")
        print(f"\n=== VERDICT: {verdict} ===  ({'; '.join(expl)})")
        print(f"Results: {rdir}/results.json")
        results = dict(results_meta)
        results.update({
            'mode': 'arm-matrix',
            'zs_phi': zs_phi, 'zs_uni': zs_uni,
            'arms': {r['tag']: {'M': r['M'], 'dtheta': r['dtheta'],
                                'R_pred': L.resonance(r['M'], r['dtheta']),
                                'resonance_t0': r['resonance_t0'],
                                'summary': r['summary'],
                                'elapsed_s': r['elapsed'],
                                'Jz_abs_mean_0': r['hist'][0]['Jz_abs_mean']}
                     for r in runs},
            'verdict': verdict,
            'verdict_explanation': expl})
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
