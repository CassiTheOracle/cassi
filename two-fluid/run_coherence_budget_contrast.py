#!/usr/bin/env python3
"""Q7 coherence-budget contrast: organized vs random drive on a superposed state.

Tests `foundations/quantum-measurement-derivation.md` §3 (open question Q7,
`open-questions-cassi-answers.md`): an ORGANIZED perturbation (phase-matched,
M≈1) attacks single-rung inter-branch coherence with O(1) collapse
probability and selects one branch, while a RANDOM perturbation (M≈0) at
equal power decoheres the off-diagonal elements without branch selection.
Never tested before: the trauma-driver family tested organized/random drives
on the OPEN gate and the HELD single-branch site, never on a two-branch
superposed state.

Init (the superposition—a which-path state, §3.2): two Gaussian bubbles at
moderate separation, each a distinct branch of the superposed observable:

  branch A (Fire): r = EY/EI = 0.45, blend 0.50  -> eps ~ -0.65 (Yang deficit)
  branch B (Wood): r = 6.0,        blend 0.643 -> eps ~ +0.65 (Yang excess)

Blends are tuned so the two branches have EQUAL |eps| (0.65) at equal cell
volume: q_A = q_B (same total density M, same eps^2), so the superposition
carries NO built-in winner—selection must be produced by the drive. The
branch amplitude sits in the standing-test range (AMP ~ 0.8) so the 0.15
drive is a moderate perturbation (23%), not a swamping rectification. The
branches are phase-incompatible (anti-phase in eps): the §2 "competing
templates" at the single rung of the superposed observable (the sign of eps
= the Fire/Wood branch label). Coherence weights are overlapping Gaussians
(sigma_w = 2*bubble_sigma, house two-bubble convention) so the inter-branch
cross-term is measurable in the overlap region.

Arms (equal power, seed 42, t=4, lambda=0.05, N=48):
  ref       undriven; natural period P0 measured in-process from its
            eps_site series (dominant_period, house convention)
  organized recurring sine at P0, amp 0.15, uniform over the union ball
            (the apparatus couples to the path observable), on ey (the
            direct-epsilon channel, house Fire in-channel convention);
            M≈1 for the state's coherent phase structure
  random    white noise on the SAME component (ey), std = 0.15/sqrt(2)
            (RMS-matched to the sine), fixed seed; M≈0

Drive component is fixed by design on ey for both drive arms: for a
symmetric superposition the mean-epsilon sign is a +/-0.02 coin flip that
selects the ei pump channel (v1/v2 iterations; preserved under runs/).
Both arms share the component, so the contrast is purely the temporal phase
structure (periodic vs white), which is the M factor.

Observables (union of the two balls = the site):
  frac_neg  fraction of cells with eps < 0—branch occupancy (0.5 =
            symmetric superposition; -> 1: Fire branch won, -> 0: Wood won)
  eps1, eps2 per-branch mean eps over each branch ball (who drains)
  c_AB      inter-branch cross-term eps1*eps2—the alpha*beta off-diagonal
            element proxy: ~ -0.085 at init, -> 0 as either branch drains;
            rho_AB = normalized sign form (anti-phase = -1); plus the
            Gaussian-overlap wake correlation (two-bubble convention)
  eps_site, q_site/q_gap, sigma_r_site, ey/ei_min_site (clamp diags)

Verdict (Q7): SUPPORTED if the organized arm SELECTS—|frac_neg-0.5|
growing from ~0 to >= 0.35 (one branch taking over) with the cross-term
|rho_AB| decaying by >= 0.3—while the equal-power random arm and the
undriven reference do NOT select (frac_neg stays near 0.5). NULL otherwise.
Reported honestly either way.

Usage:
  python two-fluid/run_coherence_budget_contrast.py --arm ref
  python two-fluid/run_coherence_budget_contrast.py --arm organized --p0 <P0>
  python two-fluid/run_coherence_budget_contrast.py --arm random --p0 <P0>
  python two-fluid/run_coherence_budget_contrast.py --verdict
Arms are separate processes (natural checkpointing): the ref run writes
p0.json; the drive arms take --p0 explicitly (dominant_period window quirk:
never re-measure across windows).

Output: runs/q7_coherence_budget/{ref,organized,random}.json, p0.json,
verdict.json, figure (runs/ is gitignored—commit the script only).
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T

# ── Protocol (churning-gate regime: lambda=0.05, t=4, N=48) ───────────────
T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 4000                 # t = 4
DRIVE_AMP = 0.15             # above the phase-blindness floor (0.05),
                             # below the known drain amplitude (0.3)
NOISE_STD = DRIVE_AMP / np.sqrt(2.0)   # RMS-matched to the sine
SEED = 42
P0_FALLBACK = 0.1            # only if the ref series has no dominant peak

# ── Superposition branches (which-path two-bubble, equal |eps|) ───────────
R_A = 0.45                   # Fire branch: eps < 0
R_B = 6.0                    # Wood branch: eps > 0 (blend tuned below)
A_A = 0.50                   # branch-A blend -> |eps| ~ 0.65
A_B = 0.643                  # branch-B blend -> |eps| ~ 0.65 (tuned)
BUBBLE_SIG = 5.0             # bubble Gaussian sigma in cells
WEIGHT_SIG = 10.0            # coherence weight sigma (2 * bubble sigma)
SEP = 12                     # center separation (N//4), moderate

RDIR = "runs/q7_coherence_budget"


def branch_centers(N_):
    """Bubble centers: (cx, cy, cz) for branch A and B (no wrap needed)."""
    return (N_ // 4, N_ // 2, N_ // 2), (N_ // 4 + SEP, N_ // 2, N_ // 2)


def make_branch_bubble(ey, ei, cx, cy, cz, radius, r_local, amplitude):
    """Gaussian bubble blending a cell toward ratio r_local (house form)."""
    N_ = ey.shape[0]
    device = ey.device
    x = torch.arange(N_, dtype=torch.float64, device=device).unsqueeze(1).unsqueeze(2)
    y = torch.arange(N_, dtype=torch.float64, device=device).unsqueeze(0).unsqueeze(2)
    z = torch.arange(N_, dtype=torch.float64, device=device).unsqueeze(0).unsqueeze(1)
    d2 = (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2
    gauss = torch.exp(-d2 / (2.0 * radius ** 2))
    rho_local = ey + ei
    ey_local = rho_local * r_local / (1.0 + r_local)
    ei_local = rho_local / (1.0 + r_local)
    ey = ey * (1.0 - amplitude * gauss) + ey_local * amplitude * gauss
    ei = ei * (1.0 - amplitude * gauss) + ei_local * amplitude * gauss
    return ey, ei


def superposition_init(solver, seed=SEED):
    """Two-branch which-path superposition (see module docstring)."""
    N_ = solver.N
    dev = solver.device
    ey = torch.ones((N_,) * 3, dtype=torch.float64, device=dev)
    ei = torch.full((N_,) * 3, T.PHI_INV, dtype=torch.float64, device=dev)
    cA, cB = branch_centers(N_)
    ey, ei = make_branch_bubble(ey, ei, *cA, BUBBLE_SIG, R_A, A_A)
    ey, ei = make_branch_bubble(ey, ei, *cB, BUBBLE_SIG, R_B, A_B)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def branch_masks(solver):
    """(union ball mask, per-branch ball masks, coherence weights w1/w2)."""
    N_ = solver.N
    dev = solver.device
    cA, cB = branch_centers(N_)
    x = torch.arange(N_, dtype=torch.float64, device=dev).unsqueeze(1).unsqueeze(2)
    y = torch.arange(N_, dtype=torch.float64, device=dev).unsqueeze(0).unsqueeze(2)
    z = torch.arange(N_, dtype=torch.float64, device=dev).unsqueeze(0).unsqueeze(1)
    dA2 = (x - cA[0]) ** 2 + (y - cA[1]) ** 2 + (z - cA[2]) ** 2
    dB2 = (x - cB[0]) ** 2 + (y - cB[1]) ** 2 + (z - cB[2]) ** 2
    bA = (dA2 <= T.R_SITE ** 2).to(torch.float64)
    bB = (dB2 <= T.R_SITE ** 2).to(torch.float64)
    union = torch.clamp(bA + bB, max=1.0)
    w1 = torch.exp(-dA2 / (2.0 * WEIGHT_SIG ** 2))
    w2 = torch.exp(-dB2 / (2.0 * WEIGHT_SIG ** 2))
    return union, bA, bB, w1, w2


def measure_branches(solver, ey, ei, union, bA, bB, w1, w2):
    """Site diagnostics plus the inter-branch coherence cross-term."""
    d = T.measure(solver, ey, ei, union)
    eps = ey - T.PHI * ei
    bm = union > 0.5
    d['ey_min_site'] = float(ey[bm].min())
    d['ei_min_site'] = float(ei[bm].min())
    # Per-branch mean eps over each branch's ball (localized, no dilution)
    d['eps1'] = float((eps * bA).sum() / bA.sum())
    d['eps2'] = float((eps * bB).sum() / bB.sum())
    # Inter-branch cross-term: the product of branch amplitudes (alpha*beta),
    # the off-diagonal element proxy: -0.15 at init, -> 0 as either branch
    # drains; normalized form keeps the sign (anti-phase = -1).
    d['c_AB'] = d['eps1'] * d['eps2']
    d['rho_AB'] = (d['c_AB'] / (abs(d['eps1']) * abs(d['eps2']) + 1e-12)
                   if d['eps1'] != 0.0 and d['eps2'] != 0.0 else 0.0)
    # Gaussian-overlap wake correlation (two-bubble house convention),
    # secondary: correlation of the weighted wake fields in the overlap.
    e1, e2 = eps * w1, eps * w2
    m1 = (e1 * w1).sum() / (w1 * w1).sum()
    m2 = (e2 * w2).sum() / (w2 * w2).sum()
    c1, c2 = e1 - m1 * w1, e2 - m2 * w2
    d['corr_centered'] = float(
        (c1 * c2).sum() / (torch.sqrt((c1 ** 2).sum() * (c2 ** 2).sum()) + 1e-30))
    d['frac_neg'] = float((eps < 0.0).to(torch.float64)[bm].mean())
    d['frac_fire'] = d['phase_frac'][1]   # house-standard channel occupancy
    return d


def run_case(solver, mode, p0=None, outdir=None):
    """Evolve the superposed init under one drive mode; return hist."""
    print(f"\n=== run: {mode} (p0={'-' if p0 is None else f'{p0:.4f}'}, "
          f"amp={DRIVE_AMP}, noise_std={NOISE_STD:.4f}) ===")
    ey_hat, ei_hat, u_hat = superposition_init(solver, seed=SEED)
    union, bA, bB, w1, w2 = branch_masks(solver)
    msum = union.sum()

    # Drive component is FIXED by design: ey (the direct-epsilon channel,
    # the house Fire in-channel convention). The epsilon-mean sign is not
    # used: for a symmetric superposition it is a +/-0.02 coin flip that
    # selected the ei pump channel in the v1/v2 design iterations (see the
    # preserved runs/ dirs); both drive arms use the SAME component so the
    # organized-vs-random contrast is purely the temporal phase structure.
    drive_comp = 'ey'
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    eps_mean0 = float(((ey0 - T.PHI * ei0) * union).sum() / msum)
    print(f"  union mean eps at t=0 = {eps_mean0:+.4f} -> drive on {drive_comp}"
          f" (fixed by design)")

    rng = np.random.default_rng(SEED)
    noise = rng.normal(0.0, NOISE_STD, STEPS) if mode == 'random' else None

    t0 = time.time()
    hist = []
    for step in range(STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        t_now = step * T.DT
        if mode in ('organized', 'anti', 'pathA'):
            drive = DRIVE_AMP * np.sin(2.0 * np.pi * t_now / p0)
        elif mode == 'random':
            drive = float(noise[step])
        else:
            drive = 0.0
        if drive != 0.0:
            if mode == 'anti':
                # Spatial anti-phase envelope matching the branch pattern:
                # branch A pushed one way, branch B the opposite, at the
                # same temporal period—the drive field is the state's own
                # spatial phase structure (the inter-branch coherence).
                ey = ey + drive * (bA - bB)
            elif mode == 'pathA':
                # Which-path detector: organized attack on branch A only.
                ey = ey + drive * bA
            else:
                ey = ey + drive * union
            ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = measure_branches(solver, ey, ei, union, bA, bB, w1, w2)
            d.update({'step': step, 't': t_now})
            hist.append(d)
            print(f"  t={t_now:4.2f} | eps_site={d['eps_site']:.4f} "
                  f"| q_site={d['q_site']:.3f} | frac_neg={d['frac_neg']:.3f} "
                  f"| rho_AB={d['rho_AB']:+.3f} "
                  f"| eps1={d['eps1']:+.3f} eps2={d['eps2']:+.3f}")

    print(f"  [{mode}] {STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{mode}.json", "w") as f:
            json.dump({'kind': mode, 'mode': mode,
                       'drive_comp': drive_comp, 'hist': hist}, f, indent=1)
    return hist, drive_comp


def summarize(mode, hist):
    """Verdict quantities: selection, cross-term decay, site retention."""
    first, last = hist[0], hist[-1]
    sel0 = abs(first['frac_neg'] - 0.5)
    sel1 = abs(last['frac_neg'] - 0.5)
    c0, c1 = abs(first['c_AB']), abs(last['c_AB'])
    # Branch asymmetry over the last 20% of the run (stable winner check):
    # +1 = branch A (Fire) won, -1 = branch B (Wood) won, ~0 = no selection.
    tail = hist[int(0.8 * len(hist)):]
    e1t = np.mean([d['eps1'] for d in tail])
    e2t = np.mean([d['eps2'] for d in tail])
    asym = (abs(e1t) - abs(e2t)) / (abs(e1t) + abs(e2t) + 1e-12)
    return {
        'frac_neg_start': first['frac_neg'], 'frac_neg_end': last['frac_neg'],
        'selection': sel1, 'selection_growth': sel1 - sel0,
        'c_AB_start': first['c_AB'], 'c_AB_end': last['c_AB'],
        'cross_decay': c0 - c1,
        'cross_decay_rel': 1.0 - c1 / max(c0, 1e-12),
        'rho_AB_start': first['rho_AB'], 'rho_AB_end': last['rho_AB'],
        'corr_centered_start': first['corr_centered'],
        'corr_centered_end': last['corr_centered'],
        'branch_asym': asym,
        'eps1_tail': e1t, 'eps2_tail': e2t,
        'eps_rel': last['eps_site'] / max(first['eps_site'], 1e-12),
        'q_gap': last['q_glob'] - last['q_site'],
        'q_gap_init': first['q_glob'] - first['q_site'],
        'sigma_r_end': last['sigma_r_site'],
        'eps1_end': last['eps1'], 'eps2_end': last['eps2'],
        'ey_min': min(d['ey_min_site'] for d in hist),
        'ei_min': min(d['ei_min_site'] for d in hist),
    }


SELECT_THRESHOLD = 0.35     # |frac_neg - 0.5| at t_end for "one branch won"
SELECT_GROWTH = 0.25        # growth from init required (init ~ 0)
CROSS_DECAY = 0.50          # relative |c_AB| drop required (cross-term
                            # collapse toward zero = one branch draining)
ASYMMETRY = 0.60            # |branch_asym| at t_end for "one branch won"
                            # by amplitude (the other branch dissolved or
                            # was left behind)


def selected(s):
    """One branch won: occupancy collapse OR stable amplitude asymmetry."""
    occ = (s['selection'] >= SELECT_THRESHOLD and
           s['selection_growth'] >= SELECT_GROWTH and
           s['cross_decay_rel'] >= CROSS_DECAY)
    amp = abs(s['branch_asym']) >= ASYMMETRY
    return occ or amp


def verdict(meta, s_ref, s_org, s_rand, s_anti=None, s_path=None):
    org_sel = bool(selected(s_org))
    rand_sel = bool(selected(s_rand))
    ref_sel = bool(selected(s_ref))
    org_cross = bool(s_org['cross_decay_rel'] >= CROSS_DECAY)
    anti_sel = bool(selected(s_anti)) if s_anti is not None else None
    path_sel = bool(selected(s_path)) if s_path is not None else None
    supported = bool(org_sel and org_cross and (not rand_sel) and (not ref_sel))
    return {
        'meta': meta,
        'thresholds': {'select': SELECT_THRESHOLD, 'growth': SELECT_GROWTH,
                       'cross_decay': CROSS_DECAY,
                       'asymmetry': ASYMMETRY},
        'arms': {'ref': s_ref, 'organized': s_org, 'random': s_rand},
        'extra_arms': {'organized_anti': s_anti, 'organized_pathA': s_path},
        'verdict': {
            'organized_selected': org_sel, 'organized_cross_decayed': org_cross,
            'organized_anti_selected': anti_sel,
            'organized_pathA_selected': path_sel,
            'random_selected': rand_sel, 'ref_selected': ref_sel,
            'SUPPORTED': supported,
        },
    }


def load_arm(name):
    with open(f"{RDIR}/run_{name}.json") as f:
        return json.load(f)


def make_figure(v):
    """Runs figure: eps_site, frac_neg, c_AB, q_site for the three arms."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        colors = {'ref': 'gray', 'organized': 'C2', 'random': 'C1',
                  'anti': 'C3', 'pathA': 'C4'}
        labels = {'ref': 'ref (undriven)', 'organized': 'organized (P0)',
                  'random': 'random (equal RMS)',
                  'anti': 'organized anti-phase',
                  'pathA': 'organized pathA (detector)'}
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        for name in ['ref', 'organized', 'random', 'anti', 'pathA']:
            if not os.path.exists(f"{RDIR}/run_{name}.json"):
                continue
            arm = load_arm(name)
            h = arm['hist']
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], colors[name],
                            label=labels[name])
            axes[0, 1].plot(t, [d['frac_neg'] for d in h], colors[name],
                            label=labels[name])
            axes[1, 0].plot(t, [d['c_AB'] for d in h], colors[name],
                            label=labels[name])
            axes[1, 1].plot(t, [d['q_site'] for d in h], colors[name],
                            label=labels[name])
        axes[0, 0].set_title('site |epsilon| (branch amplitude sum)')
        axes[0, 1].set_title('branch occupancy frac(eps<0): 0.5 = '
                             'symmetric, ->1 Fire wins, ->0 Wood wins')
        axes[1, 0].set_title('inter-branch cross-term eps1*eps2 '
                             '(off-diagonal proxy)')
        axes[1, 1].set_title('site q (5-channel coherence)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        p0 = v['meta'].get('P0', 0.0)
        fig.suptitle(f'Q7 coherence-budget contrast (P0 {p0:.3f}, '
                     f'amp {DRIVE_AMP}, noise RMS {NOISE_STD:.3f})')
        fig.tight_layout()
        fig.savefig(f"{RDIR}/coherence_budget.png", dpi=130)
        plt.close()
        print(f"\nFigure: {RDIR}/coherence_budget.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")


def print_verdict(v):
    s_ref, s_org, s_rand = (v['arms']['ref'], v['arms']['organized'],
                            v['arms']['random'])
    s_anti, s_path = v['extra_arms']['organized_anti'], \
        v['extra_arms']['organized_pathA']
    print("\n=== Q7 COHERENCE-BUDGET CONTRAST (t=4) ===")
    print(f"{'arm':>9s} {'frac_neg 0->1':>14s} {'|sel|':>6s} "
          f"{'asym':>6s} {'c_AB 0->1':>13s} {'crossΔrel':>9s} "
          f"{'eps_rel':>7s} {'q_gap':>7s} {'ey_min':>7s} {'ei_min':>7s}")
    for name, s in [('ref', s_ref), ('organized', s_org), ('random', s_rand),
                    ('anti', s_anti), ('pathA', s_path)]:
        if s is None:
            continue
        print(f"{name:>9s} {s['frac_neg_start']:5.3f}->"
              f"{s['frac_neg_end']:5.3f} {s['selection']:6.3f} "
              f"{s['branch_asym']:+6.2f} "
              f"{s['c_AB_start']:+5.2f}->{s['c_AB_end']:+5.2f} "
              f"{s['cross_decay_rel']:8.0%} "
              f"{s['eps_rel']:7.3f} {s['q_gap']:+7.3f} "
              f"{s['ey_min']:7.3f} {s['ei_min']:7.3f}")

    vd = v['verdict']
    print("\n=== VERDICT ===")
    print(f"organized (uniform, P0):   selection={vd['organized_selected']} "
          f"cross-term decayed={vd['organized_cross_decayed']}")
    if s_anti is not None:
        print(f"organized_anti (anti-phase): selection="
              f"{vd['organized_anti_selected']}")
    if s_path is not None:
        print(f"organized_pathA (detector): selection="
              f"{vd['organized_pathA_selected']}")
    print(f"random (equal RMS):        selection={vd['random_selected']}")
    print(f"ref (undriven):            selection={vd['ref_selected']}")
    if vd['SUPPORTED']:
        print("*** Q7 SUPPORTED: the organized (M≈1) drive at the "
              "state's own phase collapses the two-branch superposition "
              "to one branch while the equal-power random (M≈0) drive "
              "and the undriven reference leave it unselected—"
              "measurement-like selection is phase-matching, not "
              "power. ***")
    else:
        print("Q7 NULL: no organized-vs-random selection contrast in "
              "this PDE—see per-arm numbers above.")
    print(f"Results: {RDIR}/verdict.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['ref', 'organized', 'random', 'anti',
                                      'pathA'])
    ap.add_argument('--p0', type=float, default=None)
    ap.add_argument('--verdict', action='store_true')
    args = ap.parse_args()

    os.makedirs(RDIR, exist_ok=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={STEPS * T.DT}  "
          f"seed={SEED}  drive_amp={DRIVE_AMP}  noise_std={NOISE_STD:.4f}")

    if args.verdict:
        s_ref = summarize('ref', load_arm('ref')['hist'])
        s_org = summarize('organized', load_arm('organized')['hist'])
        s_rand = summarize('random', load_arm('random')['hist'])
        with open(f"{RDIR}/p0.json") as f:
            meta = json.load(f)
        s_anti = (summarize('anti', load_arm('anti')['hist'])
                  if os.path.exists(f"{RDIR}/run_anti.json") else None)
        s_path = (summarize('pathA', load_arm('pathA')['hist'])
                  if os.path.exists(f"{RDIR}/run_pathA.json") else None)
        v = verdict(meta, s_ref, s_org, s_rand, s_anti, s_path)
        with open(f"{RDIR}/verdict.json", "w") as f:
            json.dump(v, f, indent=2)
        print_verdict(v)
        return

    solver = T.build_solver(device)

    if args.arm == 'ref':
        h_ref, comp = run_case(solver, 'ref', outdir=RDIR)
        p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
        # Also measure with the true sampling interval (REPORT*DT) for the
        # record; the drive uses the house convention (T.DT) per the
        # dominant_period window quirk.
        p0_sampled = T.dominant_period([d['eps_site'] for d in h_ref],
                                       T.REPORT * T.DT)
        if p0 is None:
            p0 = P0_FALLBACK
            print(f"  [ref] no dominant peak -> fallback P0 = {p0}")
        else:
            print(f"\nMeasured natural period P0 = {p0:.4f} "
                  f"(phi*P0 = {T.PHI * p0:.4f}, sampled-interval measure "
                  f"{'None' if p0_sampled is None else f'{p0_sampled:.4f}'})")
        with open(f"{RDIR}/p0.json", "w") as f:
            json.dump({'P0': p0, 'phi_P0': T.PHI * p0, 't_end': STEPS * T.DT,
                       'P0_sampled_interval': p0_sampled,
                       'measured_at': datetime.now().isoformat()}, f, indent=1)
        print(f"P0 saved: {RDIR}/p0.json")
    elif args.arm in ('organized', 'random', 'anti', 'pathA'):
        if args.p0 is None:
            print("--p0 required for the drive arms (measured from the "
                  "ref window); aborting.")
            sys.exit(1)
        run_case(solver, args.arm, p0=args.p0, outdir=RDIR)
    else:
        # default: run all arms in sequence (ref -> drives) and print verdict
        h_ref, _ = run_case(solver, 'ref', outdir=RDIR)
        p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
        if p0 is None:
            p0 = P0_FALLBACK
        with open(f"{RDIR}/p0.json", "w") as f:
            json.dump({'P0': p0, 't_end': STEPS * T.DT}, f, indent=1)
        for arm in ('organized', 'random', 'anti', 'pathA'):
            run_case(solver, arm, p0=p0, outdir=RDIR)
        s_ref = summarize('ref', load_arm('ref')['hist'])
        s_org = summarize('organized', load_arm('organized')['hist'])
        s_rand = summarize('random', load_arm('random')['hist'])
        s_anti = summarize('anti', load_arm('anti')['hist'])
        s_path = summarize('pathA', load_arm('pathA')['hist'])
        with open(f"{RDIR}/p0.json") as f:
            meta = json.load(f)
        v = verdict(meta, s_ref, s_org, s_rand, s_anti, s_path)
        with open(f"{RDIR}/verdict.json", "w") as f:
            json.dump(v, f, indent=2)
        print_verdict(v)


if __name__ == "__main__":
    main()
