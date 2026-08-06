#!/usr/bin/env python3
"""TR3 phase-matched trigger reactivation + WX2 damping-signature tests.

Part 1 — TR3 (`consciousness/trauma-as-frozen-gate.md` TR3): a locked site
re-activates only under a pentagon-phase-matched trigger. The RELEASE ->
RE-DRIVE protocol (never run before): lock Fire (standing event, delta=pi,
amp 0.8, the `run_trauma_phase_channels.py` Fire arm), release it by
undriven decay, then re-drive with a weak chronic site injection
(INJ_RATE = 0.04, the `run_trauma_driver.py` convention) in one of two
field-space directions:

    a  Fire trigger  (pure Yang deficit  ey -= I*dt at the site)
    b  Wood trigger  (pure Yin deficit   ei -= I*dt at the site)
    c  control       (no injection)

Verdict: SUPPORTED if (a) re-locks Fire and (b) stays released (no Fire
re-lock).

Representability bound (2026-07-31, `run_trauma_phase_channels.py`): the
1e-3 positivity clamp on ey/ei pins atan2(ei, ey) to the first quadrant at
every cell, so of the five pentagon channels only Wood (0 deg) and Fire
(72 deg) exist in the field angle; Earth (144), Metal (216), Water (288)
clamp out and are not testable. The binary tested here is Fire vs Wood.

Part 2 — WX2 (`foundations/wu-xing-cycle-structure.md` §4): the ke ring's
sub-critical damping signature. With kappa = phi^-1 = K_fw the one-cycle
ring gain is kappa^3 = phi^-3 = 0.236, so a driverless lock should decay
through the gate keeping (1 - kappa^3) = 0.764 of its excess per ring lap
while the other channels starve/elevate in the ke pattern.

Gate level (`run_trauma_c1_ring.py` conventions, numpy ke round): single-
lock states ch = b + D e_j, D = phi^-3, free laps without re-pinning;
per-lap retained fraction of the locked excess vs 0.764; fitted per-lap
decay constant vs kappa^3 = 0.236; per-channel starving profile over laps.

PDE level (gate_model='five_ke', standing lock, no driver): site ch_open
profile vs t for five_ke vs five (control); locked-channel excess decay
constant; per-site-period retention vs the 0.764-per-cycle prediction.

Usage: python two-fluid/run_trigger_wx2_tests.py
Output: runs/<id>_trigger_wx2/results.json + figure
"""

import os
import sys
import json
import time
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T
import run_trauma_ke_ring as KR

# ── shared parameters (wake-lock conventions) ─────────────────────────────
T.LAM = 0.1
T.DT = 0.001
T.REPORT = 50
T.AMP = 0.8
PHI = T.PHI
PHI_INV = T.PHI_INV

INJ_RATE = 0.04          # injection rate in epsilon/unit-time (driver conv.)
T_LOCK = 10.0            # lock phase horizon
T_REL = 40.0             # release phase horizon
T_REDRIVE = 50.0         # re-drive horizon

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
BASELINE = np.array([PHI ** -k for k in (3, 4, 5, 6, 7)])   # b_i
D_STRONG = PHI ** -3     # 0.236—the closure-scale excess (c1_ring D_STRONG)
KAPPA3 = PHI_INV ** 3    # 0.236—one-cycle ring gain


# ── Part 1 helpers ─────────────────────────────────────────────────────────

def init_event(solver, delta, amp):
    """Standing geometry with the event direction delta at the center
    (the `run_trauma_phase_channels.py` init)."""
    N_ = solver.N
    dev = solver.device
    ey = torch.ones((N_,) * 3, dtype=torch.float64, device=dev)
    ei = torch.full((N_,) * 3, T.PHI_INV, dtype=torch.float64, device=dev)
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    pattern = (torch.cos(2.0 * np.pi * x / N_).unsqueeze(1).unsqueeze(2) *
               torch.cos(2.0 * np.pi * x / N_).unsqueeze(0).unsqueeze(2) *
               torch.cos(2.0 * np.pi * x / N_).unsqueeze(0).unsqueeze(0))
    ey = ey - amp * np.cos(delta) * pattern
    ei = ei - amp * np.sin(delta) * pattern
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def run_phase(solver, state, tag, t0, t1, inject, hist=None, mask=None,
              measure_fn=T.measure):
    """Continue the fields in `state` from t0 to t1, appending diagnostics.

    state: (ey_hat, ei_hat, u_hat) tuple (not modified).
    inject: None | 'fire' (ey deficit at the site) | 'wood' (ei deficit).
    Returns (state_out, hist_out).
    """
    ey_hat, ei_hat, u_hat = state
    if mask is None:
        mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    if hist is None:
        hist = []
    n0 = int(round(t0 / T.DT))
    n1 = int(round(t1 / T.DT))
    print(f"=== phase {tag}: t={t0}..{t1}, inject={inject} ===")
    tstart = time.time()
    for step in range(n0, n1):
        t_now = step * T.DT
        if inject:
            inj = INJ_RATE * T.DT
            if inject == 'fire':
                ey = torch.fft.ifftn(ey_hat).real
                ey = ey - inj * mask
                ey_hat = torch.fft.fftn(ey)
            elif inject == 'wood':
                ei = torch.fft.ifftn(ei_hat).real
                ei = ei - inj * mask
                ei_hat = torch.fft.fftn(ei)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == n1 - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = measure_fn(solver, ey, ei, mask)
            d.update({'step': step, 't': t_now})
            hist.append(d)
    print(f"  [{tag}] {n1 - n0} steps in {time.time() - tstart:.1f}s")
    return (ey_hat, ei_hat, u_hat), hist


def at_t(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def dominant(phase_frac):
    return CHANNELS[int(np.argmax(phase_frac))]


def eps_rel(hist, t_from, t_to):
    return at_t(hist, t_to)['eps_site'] / max(at_t(hist, t_from)['eps_site'],
                                              1e-12)


# ── Part 2 helpers ─────────────────────────────────────────────────────────

def ke_round(ch):
    """One simultaneous ke round—the solver's five_ke algebra (numpy)."""
    excess = np.maximum(ch - BASELINE, 0.0)
    d = np.minimum(PHI_INV * excess, np.roll(ch, -2))   # i restrains i+2
    out = ch - np.roll(d, +2) + np.roll(d, +4)          # target loses, i+4 gains
    return np.maximum(out, 0.0)


def fit_decay(e, t):
    """Fit ln e = ln e0 - gamma t on the window where e > 0.02 (robust)."""
    e = np.asarray(e, dtype=float)
    t = np.asarray(t, dtype=float)
    m = e > 0.02
    if m.sum() < 3:
        m = e > 1e-3
    if m.sum() < 3:
        return None, None
    A = np.vstack([np.ones(m.sum()), -t[m]]).T
    (ln0, gam), *_ = np.linalg.lstsq(A, np.log(e[m]), rcond=None)
    return float(gam), float(np.exp(ln0))


# ── main ──────────────────────────────────────────────────────────────────

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  dt={T.DT}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_trigger_wx2"
    os.makedirs(rdir, exist_ok=True)

    results = {
        'meta': {'lam': T.LAM, 'amp': T.AMP, 'INJ_RATE': INJ_RATE,
                 'T_LOCK': T_LOCK, 'T_REL': T_REL, 'T_REDRIVE': T_REDRIVE,
                 'kappa3': float(KAPPA3), 'retain_pred': float(1 - KAPPA3),
                 'representability_bound':
                     'only Wood (0 deg) and Fire (72 deg) exist in the field '
                     'angle under the 1e-3 positivity clamp; Earth/Metal/'
                     'Water are not representable'},
        'tr3': {}, 'wx2_gate': {}, 'wx2_pde': {}, 'verdicts': {},
    }

    # ══════════════ Part 1: TR3 RELEASE -> RE-DRIVE ══════════════════════
    print("\n" + "=" * 72)
    print("PART 1 — TR3: PHASE-MATCHED TRIGGER REACTIVATION")
    print("=" * 72)
    fire_d, wood_d = np.pi, 1.5 * np.pi
    solver = T.build_solver(device)

    # lock phase: standing Fire event, t=0..10 (reproduces the phase-channel
    # Fire arm), then release t=10..40 with no injection.
    state = init_event(solver, fire_d, T.AMP)
    state, h = run_phase(solver, state, 'lock', 0.0, T_LOCK, None)
    state, h = run_phase(solver, state, 'release', T_LOCK, T_REL, None,
                         hist=h)
    with open(f"{rdir}/run_lock_release.json", "w") as f:
        json.dump({'hist': h}, f, indent=1)

    d_lock = at_t(h, T_LOCK)
    d_rel = at_t(h, T_REL)
    eps_start = h[0]['eps_site']
    rel = {
        'lock_t10': {'dominant': dominant(d_lock['phase_frac']),
                     'phase_frac': d_lock['phase_frac'],
                     'eps_site': d_lock['eps_site'],
                     'eps_rel': d_lock['eps_site'] / eps_start,
                     'q_gap': d_lock['q_glob'] - d_lock['q_site']},
        'released_t40': {'dominant': dominant(d_rel['phase_frac']),
                         'phase_frac': d_rel['phase_frac'],
                         'eps_site': d_rel['eps_site'],
                         'eps_rel': d_rel['eps_site'] / eps_start,
                         'q_gap': d_rel['q_glob'] - d_rel['q_site']},
    }
    print(f"lock   @t={T_LOCK:4.1f}: dominant={rel['lock_t10']['dominant']:5s} "
          f"eps_rel={rel['lock_t10']['eps_rel']:.2f} "
          f"q_gap={rel['lock_t10']['q_gap']:+.4f}")
    print(f"release@t={T_REL:4.1f}: dominant={rel['released_t40']['dominant']:5s} "
          f"eps_rel={rel['released_t40']['eps_rel']:.2f} "
          f"q_gap={rel['released_t40']['q_gap']:+.4f}")

    # re-drive arms from the released state, t=40..50 (each arm clones the
    # released fields so all three start from the identical state)
    arms = {}
    for tag, inject in [('a_fire', 'fire'), ('b_wood', 'wood'),
                        ('c_ctrl', None)]:
        s0 = tuple(t.clone() for t in state)
        _, h_arm = run_phase(solver, s0, f'redrive_{tag}', T_REL, T_REDRIVE,
                             inject)
        with open(f"{rdir}/run_{tag}.json", "w") as f:
            json.dump({'hist': h_arm}, f, indent=1)
        d50 = at_t(h_arm, T_REDRIVE)
        arms[tag] = {
            't50_dominant': dominant(d50['phase_frac']),
            't50_phase_frac': d50['phase_frac'],
            't50_eps_site': d50['eps_site'],
            't50_q_gap': d50['q_glob'] - d50['q_site'],
        }
        print(f"arm {tag}: t={T_REDRIVE:4.1f} dominant="
              f"{arms[tag]['t50_dominant']:5s} "
              f"eps={arms[tag]['t50_eps_site']:.3f} "
              f"q_gap={arms[tag]['t50_q_gap']:+.4f} "
              f"phase={['%.2f' % x for x in d50['phase_frac']]}")

    eps_c = arms['c_ctrl']['t50_eps_site']
    a = arms['a_fire']
    b = arms['b_wood']
    a_relock = (a['t50_dominant'] == 'Fire' and
                a['t50_eps_site'] > 3.0 * eps_c and
                a['t50_phase_frac'][1] > 0.5)
    b_fire_frac = b['t50_phase_frac'][1]
    c_fire_frac = arms['c_ctrl']['t50_phase_frac'][1]
    b_stays_released = (b_fire_frac <= c_fire_frac + 0.05 and
                        b['t50_eps_site'] <= 1.5 * eps_c)
    results['tr3'] = {
        'fire_event': float(np.degrees(fire_d)),
        'wood_event': float(np.degrees(wood_d)),
        'lock': rel['lock_t10'], 'release': rel['released_t40'],
        'arms': arms,
        'a_relock_fire': bool(a_relock),
        'b_stays_released': bool(b_stays_released),
        'b_fire_frac': b_fire_frac, 'ctrl_fire_frac': c_fire_frac,
    }
    verdict1 = a_relock and b_stays_released
    results['verdicts']['TR3_phase_matched_reactivation'] = bool(verdict1)
    print("\n--- TR3 verdict ---")
    print(f"(a) Fire trigger re-locks the released site: {a_relock} "
          f"(Fire frac {a['t50_phase_frac'][1]:.2f}, eps {a['t50_eps_site']:.3f}"
          f" = {a['t50_eps_site'] / eps_c:.0f}x control)")
    print(f"(b) Wood trigger leaves it released (Fire frac {b_fire_frac:.2f} "
          f"vs control {c_fire_frac:.2f}, eps {b['t50_eps_site']:.3f} vs "
          f"{eps_c:.3f}): {b_stays_released}")
    leg_a = ('phase-matched re-lock confirmed' if a_relock else
             'no re-lock under phase-matched trigger')
    leg_b = (' and mismatched stays released' if b_stays_released else
             '; mismatched Wood trigger re-activates the site into Wood—'
             'reactivation is channel-selective (trigger phase wins), not '
             'Fire-memory-specific')
    print(f"VERDICT: TR3 {'SUPPORTED' if verdict1 else 'PARTIAL'}—{leg_a}{leg_b}")
    print("  representability bound: only Wood/Fire exist in the field "
          "angle; Earth/Metal/Water clamp out (2026-07-31)")
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ══════════════ Part 2: WX2 damping signature ════════════════════════
    print("\n" + "=" * 72)
    print("PART 2 — WX2: DAMPING SIGNATURE OF A DRIVERLESS LOCK")
    print("=" * 72)

    # ── gate level (numpy ke round, c1_ring conventions) ─────────────────
    print(f"\n-- gate level: free laps, no re-pinning, D=phi^-3 --")
    print(f"baseline b_i = phi^-(3+i): {np.round(BASELINE, 4)}")
    gate = {'kappa3': float(KAPPA3),
            'retain_pred_1lap': float(1 - KAPPA3), 'locks': {}}
    for j in range(5):
        state0 = BASELINE.copy()
        state0[j] += D_STRONG
        rec = {'channel': CHANNELS[j], 'D': float(D_STRONG)}
        # free laps: 25 rounds = 5 ring laps
        states = [state0.copy()]
        for _ in range(25):
            states.append(ke_round(states[-1]))
        f_lap = [(states[5 * l][j] - BASELINE[j]) / D_STRONG
                 for l in range(6)]       # rounds 0,5,...,25
        # per-lap retained fraction (lap 1) vs (1-kappa^3)
        rec['lap_retained'] = [float(x) for x in f_lap]
        rec['lap1_retained_frac'] = float(f_lap[1])
        rec['lap1_vs_pred'] = float(f_lap[1] / (1 - KAPPA3))
        # exponential fit on positive early laps (lstsq in ln f vs lap)
        laps = np.arange(1, 6)
        fpos = np.array(f_lap[1:])
        m = fpos > 0.05
        if m.sum() >= 2:
            A = np.vstack([np.ones(m.sum()), laps[m]]).T
            (ln0, lr), *_ = np.linalg.lstsq(A, np.log(fpos[m]), rcond=None)
            r_fit = float(np.exp(lr))
        else:
            r_fit = None
        rec['fitted_per_lap_factor'] = r_fit
        rec['fitted_vs_pred'] = (r_fit / (1 - KAPPA3)) if r_fit else None
        # starving of the others over laps
        starve = {}
        for k in range(5):
            if k == j:
                continue
            ser = [states[l][k] for l in range(26)]
            t_starve = next((l for l, v in enumerate(ser) if v < 1e-4), None)
            starve[CHANNELS[k]] = {'min_openness': float(min(ser)),
                                   'starved_round': t_starve}
        rec['others'] = starve
        rec['round25_state'] = [float(x) for x in states[25]]
        rec['round25_locked_dev'] = float(states[25][j] - BASELINE[j])
        gate['locks'][CHANNELS[j]] = rec
        print(f"  {CHANNELS[j]:5s} lock: lap-retained {np.round(f_lap, 3)} "
              f"| lap1 frac={f_lap[1]:.3f} vs pred {1 - KAPPA3:.3f}"
              f"{'' if abs(f_lap[1]-(1-KAPPA3)) < 0.05 else '  (MISMATCH)'} "
              f"| fit/lap={r_fit if r_fit is None else round(r_fit, 3)} "
              f"vs {1 - KAPPA3:.3f}")
        print(f"        starving: {json.dumps(starve, indent=0)}")
        print(f"        round25: {np.round(states[25], 3)} "
              f"(locked dev {states[25][j] - BASELINE[j]:+.3f})")

    # aggregate gate verdict: does the locked excess retain (1-kappa^3) per
    # ring lap (5 rounds)? and does it decay at all (sub-critical)?
    f1 = [gate['locks'][c]['lap1_retained_frac'] for c in CHANNELS]
    rfit = [gate['locks'][c]['fitted_per_lap_factor'] for c in CHANNELS]
    rf = [x for x in rfit if x is not None]
    gate['verdict'] = {
        'lap1_retained_mean': float(np.mean(f1)),
        'lap1_pred': float(1 - KAPPA3),
        'fitted_per_lap_mean': (float(np.mean(rf)) if rf else None),
        'per_lap_pred': float(1 - KAPPA3),
    }
    results['wx2_gate'] = gate
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── PDE level (five_ke vs five, standing lock, no driver, t=40) ──────
    print("\n-- PDE level: standing lock, no driver, t=40 --")
    pde = {'runs': {}, 'locked_channel': 'Fire'}
    h_pde = {}
    for name, gm, ke in [('five', 'five', False), ('five_ke', 'five_ke', True)]:
        s = KR.build_solver(device, gm)
        print(f"\n=== run: {name} (gate={gm}, no driver) ===")
        ey_hat, ei_hat, u_hat = T.init_fields(s, 'standing', seed=42)
        mask = T.site_mask(s.N, T.R_SITE, s.device)
        n1 = int(round(40.0 / T.DT))
        tstart = time.time()
        hist = []
        for step in range(n1):
            u_hat, ey_hat, ei_hat = s.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
            if step % T.REPORT == 0 or step == n1 - 1:
                ey = torch.fft.ifftn(ey_hat).real
                ei = torch.fft.ifftn(ei_hat).real
                d = KR.measure(s, ey, ei, mask, ke=ke)
                d.update({'step': step, 't': step * T.DT})
                hist.append(d)
        print(f"  [{name}] {n1} steps in {time.time() - tstart:.1f}s")
        with open(f"{rdir}/pde_{name}.json", "w") as f:
            json.dump({'hist': hist}, f, indent=1)
        h_pde[name] = hist
        d2 = at_t(hist, 2.0)
        dev2 = np.array(d2['ch_site']) - BASELINE
        pde['runs'][name] = {
            't2_ch': d2['ch_site'], 't2_dev': dev2.tolist(),
            't2_dominant_excess': CHANNELS[int(np.argmax(dev2))],
        }
        print(f"  {name}: t=2 dominant excess channel: "
              f"{pde['runs'][name]['t2_dominant_excess']}")

    # locked channel excess decay: the measured t=2 dominant excess channel
    # (expected Fire for the standing event) plus Fire explicitly
    j_dom = CHANNELS.index(pde['runs']['five']['t2_dominant_excess'])
    p0 = T.dominant_period([d['eps_site'] for d in h_pde['five']], T.DT)
    for name in ('five', 'five_ke'):
        h = h_pde[name]
        t = np.array([d['t'] for d in h])
        for jl, jname in ((j_dom, 'locked_dominant'), (1, 'Fire')):
            e = np.array([d['ch_site'][jl] - BASELINE[jl] for d in h])
            gam, e0 = fit_decay(e, t)
            # per-site-period retention vs the 0.764-per-cycle prediction
            ret_p0 = float(np.exp(-gam * p0)) if gam else None
            pde['runs'][name].update({
                f'{jname}_excess_gamma': gam,
                f'{jname}_excess_e0': e0,
                f'{jname}_retained_per_P0': ret_p0,
                f'{jname}_excess_t40': float(e[-1]),
                f'{jname}_min_excess': float(e.min()),
                'retained_per_P0_pred': float(1 - KAPPA3),
            })
        # starving of the other channels over time
        pde['runs'][name]['min_ch'] = {
            CHANNELS[k]: float(min(d['ch_site'][k] for d in h))
            for k in range(5)}
        gam = pde['runs'][name]['locked_dominant_excess_gamma']
        ret = pde['runs'][name]['locked_dominant_retained_per_P0']
        print(f"  {name}: locked({CHANNELS[j_dom]}) excess "
              f"gamma={gam if gam is None else round(gam, 4)} "
              f"1/gam={None if gam is None else round(1 / gam, 1)} "
              f"| retained/P0={ret if ret is None else round(ret, 3)} "
              f"vs pred {1 - KAPPA3:.3f}")
    pde['P0'] = p0
    results['wx2_pde'] = pde

    # WX2 verdict: does the measured decay match the kappa^3 profile?
    g1 = gate['verdict']['lap1_retained_mean']
    w2_gate_ok = abs(g1 - (1 - KAPPA3)) < 0.05
    results['verdicts']['WX2_gate_lap1_retention'] = bool(w2_gate_ok)
    print("\n--- WX2 verdict ---")
    print(f"gate level: lap-1 retained fraction mean {g1:.3f} vs "
          f"(1-kappa^3) = {1 - KAPPA3:.3f} "
          f"-> {'MATCH' if w2_gate_ok else 'MISMATCH'}")
    print(f"  (simultaneous ke round caps magnitudes; the sign/alternation "
          f"pattern is the WX1-verified content, `run_trauma_c1_ring.py`)")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        # TR3: eps_site of the three arms
        colors = {'a_fire': 'C1', 'b_wood': 'C2', 'c_ctrl': 'gray'}
        for tag, c in colors.items():
            with open(f"{rdir}/run_{tag}.json") as f:
                hh = json.load(f)['hist']
            axes[0, 0].plot([d['t'] for d in hh],
                            [d['eps_site'] for d in hh], c, label=tag)
        axes[0, 0].axvline(T_REL, color='w', ls=':', alpha=0.6)
        axes[0, 0].set_title('TR3 re-drive: site |eps|')
        axes[0, 0].set_xlabel('t'); axes[0, 0].grid(alpha=0.3)
        axes[0, 0].legend(fontsize=8)
        # TR3: Fire fraction
        for tag, c in colors.items():
            with open(f"{rdir}/run_{tag}.json") as f:
                hh = json.load(f)['hist']
            axes[0, 1].plot([d['t'] for d in hh],
                            [d['phase_frac'][1] for d in hh], c, label=tag)
        axes[0, 1].set_title('TR3 re-drive: site Fire fraction')
        axes[0, 1].set_xlabel('t'); axes[0, 1].grid(alpha=0.3)
        axes[0, 1].legend(fontsize=8)
        # WX2 gate: locked excess per lap vs prediction
        laps = np.arange(6)
        for j in range(5):
            axes[1, 0].plot(laps, gate['locks'][CHANNELS[j]]['lap_retained'],
                            label=CHANNELS[j])
        axes[1, 0].axhline(1 - KAPPA3, color='w', ls=':', alpha=0.8,
                           label=f'pred (1-k^3)={1 - KAPPA3:.3f}')
        axes[1, 0].set_title('WX2 gate: locked excess fraction vs free lap')
        axes[1, 0].set_xlabel('ring lap (5 rounds)')
        axes[1, 0].grid(alpha=0.3); axes[1, 0].legend(fontsize=8)
        # WX2 PDE: locked-channel excess vs t for five / five_ke
        jl = CHANNELS.index(pde['runs']['five']['t2_dominant_excess'])
        for name, c in [('five', 'C0'), ('five_ke', 'C3')]:
            hh = h_pde[name]
            axes[1, 1].plot([d['t'] for d in hh],
                            [d['ch_site'][jl] - BASELINE[jl] for d in hh],
                            c, label=name)
        axes[1, 1].axhline(0, color='w', ls=':', alpha=0.5)
        axes[1, 1].set_title(f'WX2 PDE: site {CHANNELS[jl]} openness excess vs t')
        axes[1, 1].set_xlabel('t'); axes[1, 1].grid(alpha=0.3)
        axes[1, 1].legend(fontsize=8)
        fig.suptitle(f'TR3 trigger reactivation + WX2 damping signature '
                     f'({rid})')
        fig.tight_layout()
        fig.savefig(f"{rdir}/trigger_wx2.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/trigger_wx2.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    results['meta']['run_id'] = rid
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")


if __name__ == "__main__":
    main()
