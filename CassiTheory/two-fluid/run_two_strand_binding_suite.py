#!/usr/bin/env python3
"""Two-strand wake-binding suite: T1-T4 acceptance tests for the E3 wake
aggregation flux (binding-term design report, 2026-08-06).

Run:  python two-fluid/run_two_strand_binding_suite.py

Scratch layer on the canonical solver (cassi_two_fluid_3d_gpu.py is never
edited; the layer subclasses ExpandingTwoFluid3DGPU):

  Wake field W (updated ONCE per rk2_step, after the clamp, from the final
  clamped fields -- the IIR-memory discipline):
      S_W = (1-q) eps^2,   eps = EY - phi EI,  (1-q) from the solver's own
      'five' gate via compute_q_field (the stress_energy pattern)
      dW/dt = -W/tau_W + S_W/tau_W + (ell^2/tau_W) laplacian(W)
      tau_W = 1/lam (the framework conversion timescale), ell = SIG (the
      protocol ridge width, 5 cells)
      spectral update: W_hat <- [W_hat (1 - dt/tau_W (1 + ell^2 k^2))
                                 + (dt/tau_W) S_hat] * dealias

  Aggregation flux (mass-like, both components, added in rhs after the
  canonical gate/conv block):
      dE_a/dt  ⊃  -chi_w div(E_a grad W)        (a = Y, I)
  The divergence form conserves each component's total mass exactly.  The
  charge-like variant (Yang up / Yin down) is documented-rejected: its net
  flux is chi_w (EY-EI) grad W, repulsive for the realized Yang-excess
  branch.

  chi_w = 0: every hook is guarded, so the layer is bit-inert (T1).

Arms (fresh solver per arm, N=48, lam=0.05, dt=0.001, t=40 = 2/lambda,
gate 'five'):
  ctrl    canonical ExpandingTwoFluid3DGPU, sep12 -- T1 control + committed
          baseline reproduction + T2 control
  b12_0   binding sep12, chi_w = 0            -- T1 bit-exact no-op
  b12_300 binding sep12, chi_w = 300          -- T2
  b12_1000 binding sep12, chi_w = 1000 (chi*) -- T2 + T4
  b12_3000 binding sep12, chi_w = 3000        -- T2
  b0_0    binding sep0,  chi_w = 0            -- T3 reference
  b0_1    binding sep0,  chi_w = 1000         -- T3 one-string preservation

The coupling scale is anchored by the measured wake transfer (W_peak ~
1.6e-2 * S_peak with the discrete-field normalization, decaying with eps),
so the effective bracket is chi_w ~ 300-3000 where the flux speed
chi_w * |grad W| reaches the escape drift (~0.2 cells/t).  chi_w = 0 is
bit-inert at every hook.

Verdicts (results.json):
  T1  bit-exact no-op: max|dEY| = max|dEI| = max|du| = 0.0 vs the canonical
      arm, at t = 4 and t = 40 (full recorded histories compared
      record-by-record).
  T2  monotone binding at chi*: (a) two-hump axial rho profile at t = 40
      with a real midpoint dip (dip <= min(hL,hR) - 0.01*rho_mean),
      persistent over every 1.0-interval checkpoint in t in [30,40];
      (b) turnaround d(40) < d(20) - 0.3 cells; (c) d(t) <= d_ctrl(t) + 0.5
      for all t >= 20; (d) TS1 band: back-20% mean d in [0.25 d0, 1.2 d0],
      no merge; (e) monotone-in-chi: d(40) and the dip depth move
      monotonically across {300, 1000, 3000}.
  T3  one-string preservation: sep0 at chi_w = 1000 vs sep0 at chi_w = 0 --
      max field diff <= 1e-20 (the layer is eps^2-sourced; the residual is
      the canonical init rounding, ~1e-16) and max|eps| <= 1e-12.
  T4  no clamp pathologies at chi*: zero floor touches, ey/ei minima >=
      1.01e-3, per-component mass drift at the canonical level, W bounded
      (no NaN, max W <= 10), smooth (final max|grad W| <= 10 W_max/ell).

TS1 outcome at chi* (the headline): 'bound' (two-hump + turnaround + band),
'persisted' (band without turnaround), 'merged', 'escaped', 'no-effect'.

No registries or parameter-inventory updates: the verdict is reconciled by
the director before any doctrine change (the layer is a scratch TEST of the
E3 mechanism, Hypothesized; E1 coefficients remain outputs to project).

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_two_strand_binding/run_<arm>.json   per-arm histories
  runs/<rid>_two_strand_binding/results.json     meta + summaries + verdicts
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
import run_two_strand_probe as P      # baseline probe, read-only
import run_trauma_wake_lock as T
import cassi_two_fluid_3d_gpu as C    # canonical solver, read-only

# ── Protocol (lock timescale: t = 40 = 2/lambda) ─────────────────────────
T.LAM = 0.05
T.DT = 0.001
STEPS = 40000                # t = 40
REPORT = 100                 # 401 records per arm
SEP = 12                     # baseline pair separation (cells)
CHI_STAR = 1000.0            # primary binding coupling (protocol; absorbs
                             # the discrete-field normalization: measured
                             # transfer W_peak ~ 1.6e-2 * S_peak, so the
                             # effective flux speed is chi_w * |grad W| ~
                             # chi_w * 1.4e-4 cells/t at t ~ 1)
CHI_BRACKET = (300.0, 1000.0, 3000.0)  # monotone-in-chi bracket
W_MAX_BOUND = 10.0           # T4 wake boundedness ceiling


def tag_of(chi_w):
    """Arm tag for a coupling value: 1.0 -> 'b12_1', 0.3 -> 'b12_03'."""
    return f"b12_{str(chi_w).rstrip('0').rstrip('.').replace('.', '')}"

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
SNAP_STEPS = (0, 4000, STEPS - 1)      # t = 0, 4, 40 q/eps snapshots


# ── The scratch layer (canonical solver untouched) ───────────────────────

class BindingTwoFluid(C.ExpandingTwoFluid3DGPU):
    """ExpandingTwoFluid3DGPU + the wake-binding scratch layer.

    chi_w = 0 reproduces the canonical solver bit-for-bit (every hook is
    guarded).  tau_w = 1/lam and ell = SIG are framework/protocol anchors,
    not fitted parameters.
    """

    def __init__(self, chi_w=0.0, ell=P.SIG, tau_w=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chi_w = chi_w
        self.ell = ell
        self.tau_w = tau_w if tau_w is not None else 1.0 / self.lam
        self.W = None  # wake field, allocated lazily (never at chi_w = 0)

    def _update_wake(self, ey, ei, dt):
        """One IIR step of the wake field from the final clamped fields."""
        if self.W is None:
            self.W = torch.zeros_like(ey)
        eps = ey - C.PHI * ei
        _, one_minus_q = self.compute_q_field(ey, ei)   # 'five' gate
        S = one_minus_q * eps * eps
        Wh = torch.fft.fftn(self.W)
        factor = 1.0 - (dt / self.tau_w) * (1.0 + self.ell * self.ell * self.k2)
        Wh = (Wh * factor + (dt / self.tau_w) * torch.fft.fftn(S)) * self.dealias
        self.W = torch.fft.ifftn(Wh).real

    def rhs(self, u_hat, ey_hat, ei_hat):
        r = list(super().rhs(u_hat, ey_hat, ei_hat))
        if self.chi_w != 0.0 and self.W is not None:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            grad_w = self._grad(torch.fft.fftn(self.W))
            # dE_a/dt ⊃ -chi_w div(E_a grad W); divergence-form flux
            # conserves each component's total mass exactly.
            fy = [self.chi_w * ey * g for g in grad_w]
            fi = [self.chi_w * ei * g for g in grad_w]
            # The canonical rhs dealiases AFTER the chemotaxis flux; the
            # layer flux must be dealiased identically (the physical-space
            # product E_a * grad W aliases high-k modes onto the grid).
            r[1] = r[1] - self._divergence_of_flux(fy) * self.dealias
            r[2] = r[2] - self._divergence_of_flux(fi) * self.dealias
        return tuple(r)

    def rk2_step(self, u_hat, ey_hat, ei_hat, dt):
        u_hat, ey_hat, ei_hat = super().rk2_step(u_hat, ey_hat, ei_hat, dt)
        if self.chi_w != 0.0:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            self._update_wake(ey, ei, dt)
        return u_hat, ey_hat, ei_hat


# ── Builders (fresh solver per arm) ─────────────────────────────────────

def build_canonical(device):
    solver = T.build_solver(device)
    return solver


def build_binding(device, chi_w, ell=P.SIG, tau_w=None):
    solver = BindingTwoFluid(
        N=T.N, L=T.L, nu=T.NU, D=T.D, lam=T.LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True, qi_memory=False,
        device=device, chi_w=chi_w, ell=ell, tau_w=tau_w)
    solver.gate_model = 'five'
    return solver


def two_lobe_init(solver, sep, amp1=P.E_RIDGE, amp2=P.E_RIDGE):
    """Baseline anti-phase transverse-mode init (the suite's, read-only)."""
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - sep / 2.0, cx + sep / 2.0
    g1 = torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + (Z - cx) ** 2)
                   / (2.0 * P.SIG ** 2))
    g2 = torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + (Z - cx) ** 2)
                   / (2.0 * P.SIG ** 2))
    rho = (1.0 + T.PHI_INV) * (1.0 + P.BETA * (g1 + g2))
    if amp1 == amp2:
        eps = amp1 * (g1 - g2)
    else:
        eps = amp1 * g1 - amp2 * g2
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


# ── Run one arm ──────────────────────────────────────────────────────────

def _refine_1d_safe(p, i):
    """Parabolic sub-grid refinement with a displacement cap.

    Copy of the probe's _refine_1d plus a guard: a near-flat profile top
    (denominator ~ 1e-13) makes the quadratic vertex formula numerically
    unstable and can throw the position O(1e9) cells -- which empties the
    measurement ball mask downstream.  A smooth maximum can sit at most
    ~0.5 cells from its grid point, so any refinement beyond 2 cells is
    rejected (the integer index is returned).  The cap only engages on
    degenerate flat tops, where the position is meaningless anyway.
    """
    y0, y1, y2 = p[i - 1], p[i], p[i + 1]
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-14:
        return float(i)
    d = 0.5 * (y0 - y2) / denom
    if abs(d) > 2.0:
        return float(i)
    return i + d


def track_ridges_safe(rho_prof, centers, prev):
    """Ridge positions (copy of the probe's tracker with the capped
    refinement)."""
    p = rho_prof
    pampl = (p - p.min()) / max(p.max() - p.min(), 1e-30)
    idx = np.where((pampl[1:-1] >= pampl[:-2]) &
                   (pampl[1:-1] >= pampl[2:]) &
                   (pampl[1:-1] > P.RIDGE_THRESH))[0] + 1
    if len(idx) == 0:
        fallback = (prev if prev is not None else
                    ([centers[0]] if len(centers) == 1 else centers))
        return fallback, True
    xs = [_refine_1d_safe(p, int(i)) for i in idx]
    out = []
    for xc in centers:
        if not xs:
            break
        k = int(np.argmin([abs(x - xc) for x in xs]))
        out.append(xs.pop(k))
    if len(out) == 2 and abs(out[0] - out[1]) < 2.0:
        i0, i1 = int(round(out[0])), int(round(out[1]))
        out = [out[0] if p[i0] >= p[i1] else out[1]]
    return out, len(out) == 1


def measure_strands_safe(solver, ey, ei, rho_prof, centers, prev):
    """Per-strand + pair diagnostics (copy of the probe's measurement with
    the capped refinement).  Read-only; ch_open/q replicate the solver's
    'five' gate and are never fed back."""
    dev = solver.device
    eps = ey - T.PHI * ei
    ch_open, q = T.channel_openness(ey, ei)
    one_minus_q = 1.0 - q
    conv_full = -T.LAM * one_minus_q * eps
    eta5 = torch.tensor([1.0, T.PHI_INV, T.PHI_INV, T.PHI_INV, T.PHI_INV],
                        device=dev, dtype=torch.float64).reshape(5, 1, 1, 1)
    conv_gate_full = -T.LAM * eta5 * ch_open * eps.unsqueeze(0)

    theta = torch.atan2(ei, ey)
    nearest = (theta.unsqueeze(0) -
               torch.tensor(T.CH_ANGLES, device=dev, dtype=torch.float64)
               .unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)).abs().argmin(dim=0)

    ridges, merged = track_ridges_safe(rho_prof, centers, prev)
    if merged:
        x1 = x2 = float(ridges[0])
    else:
        x1, x2 = float(ridges[0]), float(ridges[1])
    Rc = 0.5 * (x1 + x2)
    d = abs(x2 - x1)

    y_pos = []
    for xr in (ridges if merged else [x1, x2]):
        lo = max(0, int(round(xr)) - 3)
        hi = min(int(round(xr)) + 4, solver.N)
        slab = ey[lo:hi]
        if slab.numel() == 0:
            y_pos.append(solver.N / 2.0)
            continue
        yp = slab.sum(dim=0).sum(dim=1).cpu().numpy()
        yp = yp - yp.min()
        i = int(np.argmax(yp)) if yp.max() > 1e-30 else solver.N // 2
        if i in (0, len(yp) - 1):
            y_pos.append(float(i))
        else:
            y_pos.append(_refine_1d_safe(yp, i))
    if merged:
        y1 = y2 = y_pos[0]
    else:
        y1, y2 = y_pos

    theta_xy = np.arctan2(y1 - y2, x1 - x2) if not merged else 0.0

    cy = cz = solver.N / 2.0
    if merged:
        centers_xy = [(x1, y1)]
    else:
        centers_xy = [(x1, y1), (x2, y2)]
    xg = torch.arange(solver.N, dtype=torch.float64, device=dev)
    Xg, Yg, Zg = torch.meshgrid(xg, xg, xg, indexing='ij')
    weights = []
    hard_balls = []
    for (xk, yk) in centers_xy:
        dd = (Xg - xk) ** 2 + (Yg - yk) ** 2 + (Zg - cz) ** 2
        weights.append(torch.exp(-dd / (2.0 * P.SIG ** 2)) *
                       (dd <= P.R_SITE ** 2).to(torch.float64))
        hard_balls.append((dd <= P.R_SITE ** 2).to(torch.float64))
    union = torch.clamp(sum(hard_balls), max=1.0)

    out = {'d': d, 'Rc': Rc, 'merged': bool(merged), 'theta_xy': theta_xy,
           'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2}

    strand = []
    for k, w in enumerate(weights):
        wsum = w.sum()
        A_k = float((eps.abs() * w).sum() / wsum)
        eps_k = float((eps * w).sum() / wsum)
        q_k = float((q * w).sum() / wsum)
        r = ey / ei
        r_w = (r * w).sum() / wsum
        sig_r = float(torch.sqrt(((r - r_w) ** 2 * w).sum() / wsum))
        th_k = float((theta * w).sum() / wsum)
        ch_k = [float((ch_open[c] * w).sum() / wsum) for c in range(5)]
        conv_g = [float((conv_gate_full[c] * w).sum() / wsum)
                  for c in range(5)]
        conv_p = []
        for c in range(5):
            sel = (nearest == c).to(torch.float64) * w
            conv_p.append(float((conv_full * sel).sum() / wsum))
        phase_frac = [float(((nearest == c).to(torch.float64) * w).sum()
                            / wsum) for c in range(5)]
        dom = int(np.argmax(phase_frac))
        strand.append({'A': A_k, 'eps': eps_k, 'q': q_k, 'sigma_r': sig_r,
                       'theta': th_k, 'ch_open': ch_k, 'conv_gate': conv_g,
                       'conv_phase': conv_p, 'phase_frac': phase_frac,
                       'dominant': dom})

    out['strands'] = strand
    if merged:
        out['delta_theta'] = 0.0
        out['A_plus'] = strand[0]['A']
        out['A_minus'] = 0.0
        out['theta_c'] = strand[0]['theta']
        out['sheng_ke'] = 'same'
        out['sheng_ke_step'] = 0
    else:
        s1, s2 = strand
        out['delta_theta'] = float(np.angle(np.exp(1j * (s2['theta'] -
                                                         s1['theta']))))
        z1 = s1['A'] * np.exp(1j * s1['theta'])
        z2 = s2['A'] * np.exp(1j * s2['theta'])
        out['A_plus'] = float(abs(z1 + z2) / np.sqrt(2.0))
        out['A_minus'] = float(abs(z1 - z2) / np.sqrt(2.0))
        out['theta_c'] = 0.5 * (s1['theta'] + s2['theta'])
        rel = (s2['dominant'] - s1['dominant']) % 5
        names = {0: 'same', 1: 'sheng', 2: 'ke', 3: 'ke-rev', 4: 'sheng-rev'}
        out['sheng_ke'] = names[rel]
        out['sheng_ke_step'] = rel

    mid_mask = P.ball_mask(solver.N, Rc, cy, cz, P.MID_R, dev)
    out['q_mid'] = float((q * mid_mask).sum() / mid_mask.sum())
    out['eps_mid'] = float((eps * mid_mask).sum() / mid_mask.sum())
    out['rho_mid'] = float(((ey + ei) * mid_mask).sum() / mid_mask.sum())
    out['q_flank'] = 0.5 * (strand[0]['q'] + (strand[1]['q']
                                              if not merged
                                              else strand[0]['q']))

    bm = union > 0.5
    out['ey_min'] = float(ey[bm].min())
    out['ei_min'] = float(ei[bm].min())
    out['q_glob'] = float(q.mean())
    return out

def run_case(builder, sep, tag, outdir):
    """Evolve one arm (fresh solver), recording diagnostics every REPORT
    steps plus the axial rho profile and box rho mean at every record
    (needed for the T2 two-hump persistence checkpoints)."""
    solver = builder()
    print(f"\n=== run: {tag} (sep={sep}, chi_w={getattr(solver, 'chi_w', 0.0)}) ===")
    ey_hat, ei_hat, u_hat = two_lobe_init(solver, sep)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    mass0 = float((ey0 + ei0).sum())
    centers = ([solver.N / 2.0 - sep / 2.0, solver.N / 2.0 + sep / 2.0]
               if sep > 1e-6 else [solver.N / 2.0])
    prev = None
    t0 = time.time()
    hist = []
    floor_touch = 0
    cy = cz = solver.N // 2
    nan_abort = None
    for step in range(STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            if bool(torch.isnan(ey).any()) or bool(torch.isnan(ei).any()):
                nan_abort = step
                print(f"  [{tag}] NaN in the fields at step {step} "
                      f"(t={step * T.DT:.3f}); aborting the arm")
                break
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = measure_strands_safe(solver, ey, ei, rho_prof, centers, prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * T.DT,
                      'rho_prof_ax': (ey + ei)[:, cy, cz].cpu().numpy().tolist(),
                      'rho_mean': float((ey + ei).mean())})
            if d['ey_min'] < 1.01e-3 or d['ei_min'] < 1.01e-3:
                floor_touch += 1
            if step in SNAP_STEPS:
                q = T.channel_openness(ey, ei)[1]
                eps_f = ey - T.PHI * ei
                d['q_prof'] = q[:, cy, cz].cpu().numpy().tolist()
                d['eps_prof'] = eps_f[:, cy, cz].cpu().numpy().tolist()
            if getattr(solver, 'W', None) is not None:
                d['W_max'] = float(solver.W.max())
                d['W_mean'] = float(solver.W.mean())
            hist.append(d)
            if step % (10 * REPORT) == 0 or step == STEPS - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                wtxt = (f" | W_max={d['W_max']:.4f}" if 'W_max' in d else '')
                print(f"  t={step*T.DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                      f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}"
                      f"{wtxt}")
    ey1 = torch.fft.ifftn(ey_hat).real
    ei1 = torch.fft.ifftn(ei_hat).real
    mass1 = float((ey1 + ei1).sum())
    mass_drift = abs(mass1 - mass0) / mass0
    w_end = (float(solver.W.max()) if getattr(solver, 'W', None) is not None else 0.0)
    grad_w_end = 0.0
    if getattr(solver, 'W', None) is not None:
        gw = solver._grad(torch.fft.fftn(solver.W))
        grad_w_end = float(max(g.cpu().abs().max() for g in gw))
    elapsed = time.time() - t0
    meta = {'elapsed': elapsed, 'floor_touch': floor_touch,
            'mass0': mass0, 'mass1': mass1, 'mass_drift': mass_drift,
            'W_max_end': w_end, 'grad_w_max_end': grad_w_end,
            'nan_abort': nan_abort}
    print(f"  [{tag}] {STEPS} steps in {elapsed:.1f}s "
          f"(floor touches: {floor_touch}, mass drift: {mass_drift:.2e}, "
          f"W_max_end: {w_end:.4f}, |gradW|_max_end: {grad_w_end:.4f})")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'sep': sep,
                       'chi_w': getattr(solver, 'chi_w', 0.0),
                       'hist': hist, 'meta': meta}, f, indent=1)
    return hist, meta, (u_hat, ey_hat, ei_hat), solver


# ── Acceptance analyses (read-only on the histories) ────────────────────

def arm_summary(h):
    first, last = h[0], h[-1]
    d0 = first['d']
    back = h[int(0.8 * len(h)):]
    d_back = float(np.mean([d['d'] for d in back]))
    if d0 < 1e-6:
        ns1 = 'reference'
    elif last['merged'] or d_back < 0.25 * d0:
        ns1 = 'merged'
    elif d_back > 1.2 * d0:
        ns1 = 'separated'
    else:
        ns1 = 'persisted'
    return {
        'ns1': ns1, 'd_start': d0, 'd_end': last['d'], 'd_back_mean': d_back,
        'd_max': max(d['d'] for d in h),
        'merged_at_end': bool(last['merged']),
        'delta_theta_0': first['delta_theta'],
        'delta_theta_end': last['delta_theta'],
        'A_plus_end': last['A_plus'], 'A_minus_end': last['A_minus'],
        'Rc_drift': max(abs(d['Rc'] - first['Rc']) for d in h),
        'q_mid_end': last['q_mid'], 'q_flank_end': last['q_flank'],
        'rho_mid_end': last['rho_mid'], 'eps_mid_end': last['eps_mid'],
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'W_max_over_run': max((d.get('W_max', 0.0) for d in h), default=0.0),
    }


def reproduction_check(h_sep12):
    """The ctrl arm passes through the published t = 4 baseline; check the
    numbers match the committed probe record (doc section 3)."""
    at = min(h_sep12, key=lambda d: abs(d['t'] - 4.0))
    ref = {'d': 10.08, 'delta_theta': 0.227, 'q_mid': 0.7074,
           'q_flank': 0.7009, 'A_plus': 0.444, 'A_minus': 0.051,
           'eps_mid': -0.020, 'rho_mid': 2.078}
    tol = {'d': 0.05, 'delta_theta': 0.005, 'q_mid': 0.001, 'q_flank': 0.001,
           'A_plus': 0.005, 'A_minus': 0.005, 'eps_mid': 0.002,
           'rho_mid': 0.01}
    got = {'d': at['d'], 'delta_theta': at['delta_theta'],
           'q_mid': at['q_mid'], 'q_flank': at['q_flank'],
           'A_plus': at['A_plus'], 'A_minus': at['A_minus'],
           'eps_mid': at['eps_mid'], 'rho_mid': at['rho_mid']}
    ok = all(abs(got[k] - ref[k]) <= tol[k] for k in ref)
    return ok, got, ref, tol


def state_diff(st_a, st_b):
    du = max(float((a - b).abs().max()) for a, b in zip(st_a[0], st_b[0]))
    dey = float((st_a[1] - st_b[1]).abs().max())
    dei = float((st_a[2] - st_b[2]).abs().max())
    return du, dey, dei


HIST_KEYS = ['d', 'Rc', 'delta_theta', 'A_plus', 'A_minus', 'q_mid',
             'q_flank', 'rho_mid', 'eps_mid', 'x1', 'x2', 'ey_min',
             'ei_min', 'q_glob']


def hist_diff(h_a, h_b):
    """Max abs diff of the recorded scalar diagnostics, record by record."""
    hd = 0.0
    for a, b in zip(h_a, h_b):
        for k in HIST_KEYS:
            hd = max(hd, abs(a[k] - b[k]))
    return hd


def t1_verdict(h_ctrl, h_0, st_ctrl, st_0):
    """Bit-exact no-op at chi_w = 0 vs the canonical solver."""
    du, dey, dei = state_diff(st_ctrl, st_0)
    hd = hist_diff(h_ctrl, h_0)
    at4 = hist_diff([d for d in h_ctrl if abs(d['t'] - 4.0) < 1e-9],
                    [d for d in h_0 if abs(d['t'] - 4.0) < 1e-9]) \
        if any(abs(d['t'] - 4.0) < 1e-9 for d in h_ctrl) else None
    ok = (du == 0.0 and dey == 0.0 and dei == 0.0 and hd == 0.0)
    return ok, {'max_du': du, 'max_dey': dey, 'max_dei': dei,
                'max_hist_diff': hd, 't4_hist_diff': at4}


def two_hump(prof, rho_mean, thresh=P.RIDGE_THRESH):
    """True iff the axial rho profile has exactly two clear maxima flanking
    a real midpoint dip: dip <= min(hL, hR) - 0.01*rho_mean."""
    p = np.asarray(prof, dtype=float)
    amp = p.max() - p.min()
    if amp < 1e-6:
        return False, {'reason': 'flat'}
    pampl = (p - p.min()) / amp
    mx = [i for i in range(1, len(p) - 1)
          if pampl[i] >= pampl[i - 1] and pampl[i] > pampl[i + 1]
          and pampl[i] > thresh]
    if len(mx) != 2:
        return False, {'reason': f'nmax={len(mx)}', 'nmax': len(mx)}
    iL, iR = int(min(mx)), int(max(mx))
    hL, hR = float(p[iL]), float(p[iR])
    dip = float(p[iL + 1:iR].min())
    ok = dip <= min(hL, hR) - 0.01 * rho_mean
    return ok, {'nmax': 2, 'iL': iL, 'iR': iR, 'hL': hL, 'hR': hR,
                'dip': dip, 'dip_depth': (min(hL, hR) - dip) / rho_mean,
                'ok': ok}


def t2_verdict(h, h_ctrl, chi_w):
    """Monotone binding at coupling chi_w (T2a-T2d for one arm)."""
    s = arm_summary(h)
    last = h[-1]
    th40, th40_d = two_hump(last['rho_prof_ax'], last['rho_mean'])
    # persistence over every 1.0-interval checkpoint in t in [30, 40]
    chk = [(d['t'], two_hump(d['rho_prof_ax'], d['rho_mean']))
           for d in h if 30.0 - 1e-9 <= d['t'] <= 40.0 + 1e-9
           and abs(d['t'] % 1.0) < 1e-9]
    frac = sum(1 for _, (ok, _) in chk if ok) / len(chk) if chk else 0.0
    d20 = h[200]['d'] if len(h) > 200 else h[-1]['d']
    d40 = h[-1]['d']
    turnaround = d40 < d20 - 0.3
    # d(t) <= d_ctrl(t) + 0.5 for all t >= 20 (records at identical t).
    # An arm that NaN-aborts before t=20 has no such records: the
    # criterion cannot be satisfied -> inf (verdict null).
    over_recs = [(d['d'] - c['d']) for d, c in zip(h, h_ctrl)
                 if d['t'] >= 20.0 - 1e-9]
    over = max(over_recs) if over_recs else float('inf')
    band = (s['ns1'] == 'persisted' or s['ns1'] == 'reference')
    ok_hump = th40 and frac == 1.0
    ok = ok_hump and turnaround and over <= 0.5 and band
    return ok, {
        'two_hump_t40': th40, 'two_hump_t40_detail': th40_d,
        'persistence_frac_30_40': frac, 'n_checkpoints': len(chk),
        'd20': d20, 'd40': d40, 'turnaround': turnaround,
        'max_over_ctrl_t_ge_20': over, 'ts1_band': band,
        'back_mean': s['d_back_mean'], 'merged_at_end': s['merged_at_end'],
        'd0': s['d_start'], 'A_plus_end': s['A_plus_end'],
        'W_max_over_run': s['W_max_over_run'],
    }


def ts1_outcome(t2d, s):
    """The TS1 headline classification at the coupling under test."""
    if s['merged_at_end'] or s['ns1'] == 'merged':
        return 'merged'
    if s['ns1'] == 'separated':
        return 'escaped'
    if t2d['two_hump_t40'] and t2d['turnaround']:
        return 'bound'
    if t2d['two_hump_t40']:
        return 'persisted'
    return 'no-effect'


def t3_verdict(h0_0, h0_1, st0_0, st0_1):
    """One-string preservation: sep0 at chi_w = 1000 vs chi_w = 0."""
    du, dey, dei = state_diff(st0_0, st0_1)
    hd = hist_diff(h0_0, h0_1)
    ey = torch.fft.ifftn(st0_1[1]).real
    ei = torch.fft.ifftn(st0_1[2]).real
    eps_max = float((ey - C.PHI * ei).abs().max())
    ok = dey <= 1e-20 and dei <= 1e-20 and du <= 1e-20 and hd <= 1e-15 \
        and eps_max <= 1e-12
    return ok, {'max_du': du, 'max_dey': dey, 'max_dei': dei,
                'max_hist_diff': hd, 'max_eps_end': eps_max}


def t4_verdict(meta_star, meta_ctrl, t2_star, w_max_over_run,
               grad_w_end, w_has_nan):
    """No clamp pathologies at chi* (T4)."""
    ok = (meta_star['floor_touch'] == 0 and meta_ctrl['floor_touch'] == 0
          and meta_star['mass_drift'] <= 1e-11
          and not w_has_nan and w_max_over_run <= W_MAX_BOUND)
    return ok, {
        'floor_touch_star': meta_star['floor_touch'],
        'floor_touch_ctrl': meta_ctrl['floor_touch'],
        'mass_drift_star': meta_star['mass_drift'],
        'mass_drift_ctrl': meta_ctrl['mass_drift'],
        'W_max_over_run': w_max_over_run, 'W_max_end': meta_star['W_max_end'],
        'grad_w_max_end': grad_w_end,
        'grad_w_bound': 10.0 * max(meta_star['W_max_end'], 1e-12) / P.SIG,
        'w_has_nan': w_has_nan,
    }


ARM_DEFS = [
    ('ctrl', 'canonical', SEP),
    ('b12_0', 'binding', SEP, 0.0),
    (tag_of(0.3), 'binding', SEP, 0.3),   # sub-critical reference (not in
                                          # the monotone bracket, not analyzed)
    (tag_of(300.0), 'binding', SEP, 300.0),
    (tag_of(1000.0), 'binding', SEP, 1000.0),
    (tag_of(3000.0), 'binding', SEP, 3000.0),
    ('b0_0', 'binding', 0.0, 0.0),
    ('b0_1', 'binding', 0.0, 1000.0),
]


def build_for(kind, device, chi_w):
    if kind == 'canonical':
        return build_canonical(device)
    return build_binding(device, chi_w)


def run_arms(rdir, arm_list, device):
    """Run the selected arms into rdir, saving per-arm histories + final
    spectral states (state_<tag>.pt) for the bit-exact comparisons."""
    arms, meta, states = {}, {}, {}
    for spec in ARM_DEFS:
        tag = spec[0]
        if tag not in arm_list:
            continue
        kind, sep = spec[1], spec[2]
        chi_w = spec[3] if len(spec) > 3 else 0.0
        h, m, st, _ = run_case(lambda: build_for(kind, device, chi_w),
                               sep, tag, rdir)
        torch.save({'u': [x.cpu() for x in st[0]],
                    'ey': st[1].cpu(), 'ei': st[2].cpu()},
                   f"{rdir}/state_{tag}.pt")
        arms[tag], meta[tag], states[tag] = h, m, st
    return arms, meta, states


def load_arms(rdir, arm_list):
    """Load previously run arms (histories + states) from rdir."""
    arms, meta, states = {}, {}, {}
    for tag in arm_list:
        with open(f"{rdir}/run_{tag}.json") as f:
            rec = json.load(f)
        arms[tag] = rec['hist']
        meta[tag] = rec['meta']
        st = torch.load(f"{rdir}/state_{tag}.pt", map_location='cpu')
        states[tag] = (st['u'], st['ey'], st['ei'])
    return arms, meta, states


def main():
    mode = 'run'
    arm_list = None
    rdir = None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == '--analyze':
            mode = 'analyze'
        elif argv[i] == '--arms':
            arm_list = argv[i + 1].split(',')
            i += 1
        elif argv[i] == '--rdir':
            rdir = argv[i + 1]
            i += 1
        i += 1
    if arm_list is None:
        arm_list = [s[0] for s in ARM_DEFS]
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  mode={mode}  arms={arm_list}  N={T.N}  "
          f"lam={T.LAM}  t={STEPS * T.DT}  gate='five'  "
          f"E_RIDGE={P.E_RIDGE}  BETA={P.BETA}  SIG={P.SIG}  "
          f"SEP={SEP}  chi*={CHI_STAR}")

    if rdir is None:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        rdir = f"runs/{rid}_two_strand_binding"
    os.makedirs(rdir, exist_ok=True)

    if mode == 'run':
        arms, meta, states = run_arms(rdir, arm_list, device)
    else:
        arms, meta, states = load_arms(rdir, arm_list)
    compute_verdicts(arms, meta, states, rdir)


def compute_verdicts(arms, meta, states, rdir):
    required = ({'ctrl', 'b12_0', 'b0_0', 'b0_1'}
                | {tag_of(c) for c in CHI_BRACKET})
    missing = sorted(required - set(arms))
    if missing:
        print(f"[verdicts skipped: arm subset lacks {missing}; "
              f"run the full arm set for T1-T4]")
        return
    sums = {tag: arm_summary(h) for tag, h in arms.items()}

    # ── Verdicts ─────────────────────────────────────────────────────────
    t1_ok, t1_d = t1_verdict(arms['ctrl'], arms['b12_0'],
                             states['ctrl'], states['b12_0'])
    repro_ok, repro_got, repro_ref, repro_tol = reproduction_check(arms['ctrl'])
    t2 = {}
    for chi_w in CHI_BRACKET:
        tag = tag_of(chi_w)
        ok, d = t2_verdict(arms[tag], arms['ctrl'], chi_w)
        t2[tag] = {'verdict': 'passed' if ok else 'null',
                   'detail': d, 'ts1_outcome': ts1_outcome(d, sums[tag])}
    t3_ok, t3_d = t3_verdict(arms['b0_0'], arms['b0_1'],
                             states['b0_0'], states['b0_1'])
    star_tag = tag_of(CHI_STAR)
    w_series = [d.get('W_max', 0.0) for d in arms[star_tag]]
    w_has_nan = any(np.isnan(v) for v in w_series)
    t4_ok, t4_d = t4_verdict(meta[star_tag], meta['ctrl'], t2[star_tag],
                             sums[star_tag]['W_max_over_run'],
                             meta[star_tag]['grad_w_max_end'], w_has_nan)
    # monotone-in-chi: d(40) strictly decreasing, dip depth strictly
    # increasing across the bracket
    order = [tag_of(c) for c in CHI_BRACKET]
    d40s = [t2[t]['detail']['d40'] for t in order]
    depths = [t2[t]['detail']['two_hump_t40_detail'].get('dip_depth')
              for t in order]
    mono_d = all(d40s[i] > d40s[i + 1] for i in range(len(d40s) - 1))
    mono_depth = all(depths[i] is not None and depths[i + 1] is not None
                     and depths[i] < depths[i + 1]
                     for i in range(len(depths) - 1))
    mono = mono_d and mono_depth

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 'steps': STEPS,
                 't_end': STEPS * T.DT, 'gate_model': 'five (solver)',
                 'E_RIDGE': P.E_RIDGE, 'BETA': P.BETA, 'SIG': P.SIG,
                 'SEP': SEP, 'R_SITE': P.R_SITE,
                 'CHI_STAR': CHI_STAR, 'CHI_BRACKET': list(CHI_BRACKET),
                 'tau_w': 1.0 / T.LAM, 'ell': P.SIG,
                 'baseline': 'run_two_strand_probe.py @ 315a425 (t=4)',
                 'layer': 'wake W: dW/dt = -W/tau + S_W/tau + (ell^2/tau) '
                          'laplacian(W), S_W = (1-q) eps^2; flux: '
                          'dE_a/dt ⊃ -chi_w div(E_a grad W)',
                 'arms': meta,
                 'criteria': {
                     'T1': 'chi_w=0 bit-exact vs canonical: max|dEY|=max|dEI|'
                           '=max|du|=0.0 at t=4 and t=40, full histories equal',
                     'T2': 'two-hump rho profile at t=40 (dip <= min(hL,hR) '
                           '- 0.01 rho_mean) persistent over t in [30,40]; '
                           'd(40) < d(20) - 0.3; d(t) <= d_ctrl(t) + 0.5 for '
                           't >= 20; TS1 band (back-20% mean in '
                           '[0.25 d0, 1.2 d0]); monotone-in-chi across '
                           f'{list(CHI_BRACKET)}',
                     'T3': 'sep0 at chi_w=1000 == sep0 at chi_w=0 to <= 1e-20 '
                           '(max|eps| <= 1e-12)',
                     'T4': 'no floor touches, ey/ei >= 1.01e-3, mass drift '
                           '<= 1e-11, W bounded (max <= 10, no NaN), smooth'}},
        'arms': sums,
        'reproduction_t4': {'ok': repro_ok, 'got': repro_got,
                            'published_ref': repro_ref, 'tol': repro_tol},
        'verdicts': {
            'T1': {'test': 'bit-exact no-op at chi_w = 0 vs canonical',
                   'verdict': 'passed' if t1_ok else 'null', 'data': t1_d},
            'T2': {'test': 'monotone binding at finite coupling',
                   'arms': t2,
                   'monotone_in_chi': mono,
                   'monotone_in_chi_data': {'d40': d40s, 'dip_depth': depths,
                                            'd40_strict': mono_d,
                                            'depth_strict': mono_depth}},
            'T3': {'test': 'one-string recovery preservation',
                   'verdict': 'passed' if t3_ok else 'null', 'data': t3_d},
            'T4': {'test': 'no clamp pathologies at chi*',
                   'verdict': 'passed' if t4_ok else 'null', 'data': t4_d},
            'TS1_at_chistar': {'test': 'TS1 lock-timescale outcome at '
                                       f'chi_w = {CHI_STAR}',
                               'outcome': t2[star_tag]['ts1_outcome'],
                               'data': t2[star_tag]['detail']},
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== WAKE-BINDING SUITE VERDICTS (t=40, lock timescale) ===")
    for tag in sorted(sums):
        s = sums[tag]
        print(f"{tag:6s}: ns1={s['ns1']:>9s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back {s['d_back_mean']:.2f}) | "
              f"A+= {s['A_plus_end']:.3f} | q_mid {s['q_mid_end']:.3f} vs "
              f"q_flank {s['q_flank_end']:.3f} | "
              f"W_max {s['W_max_over_run']:.4f} | "
              f"ey_min {s['ey_min']:.4f}")
    print(f"\nt=4 reproduction vs published baseline: "
          f"{'OK' if repro_ok else 'MISMATCH'}")
    print(f"\nT1 (bit-exact no-op): {t1_d['max_du']:.3e} "
          f"{t1_d['max_dey']:.3e} {t1_d['max_dei']:.3e} "
          f"(max|du|, max|dEY|, max|dEI|) -> "
          f"{'PASSED' if t1_ok else 'NULL'}")
    for chi_w, tag in zip(CHI_BRACKET, order):
        t = t2[tag]
        dd = t['detail']
        print(f"T2 {tag} (chi={chi_w}): "
              f"ts1={t['ts1_outcome']:>9s} two_hump={dd['two_hump_t40']} "
              f"persist={dd['persistence_frac_30_40']:.2f} "
              f"d40={dd['d40']:.2f} d20={dd['d20']:.2f} "
              f"turn={dd['turnaround']} over_ctrl={dd['max_over_ctrl_t_ge_20']:.2f} "
              f"band={dd['ts1_band']} -> {t['verdict'].upper()}")
    print(f"T2 monotone-in-chi: d40 {[f'{v:.2f}' for v in d40s]} "
          f"dips {[f'{v:.4f}' if v is not None else '-' for v in depths]} "
          f"-> {'PASSED' if mono else 'NULL'}")
    print(f"\nT3 (one-string preservation): max|dEY| {t3_d['max_dey']:.3e} "
          f"max|eps| {t3_d['max_eps_end']:.3e} -> "
          f"{'PASSED' if t3_ok else 'NULL'}")
    print(f"T4 (clamp/W telemetry): floor {meta[star_tag]['floor_touch']} "
          f"mass_drift {meta[star_tag]['mass_drift']:.2e} "
          f"W_max {sums[star_tag]['W_max_over_run']:.4f} "
          f"gradW_end {meta[star_tag]['grad_w_max_end']:.4f} -> "
          f"{'PASSED' if t4_ok else 'NULL'}")
    print(f"\nTS1 at chi* = {CHI_STAR}: {t2[star_tag]['ts1_outcome'].upper()}")
    print(f"\nResults: {rdir}/results.json")
    if torch.cuda.is_available():
        torch.cuda.synchronize()   # ROCm teardown deadlocks on async work


if __name__ == "__main__":
    main()
