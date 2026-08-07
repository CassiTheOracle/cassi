#!/usr/bin/env python3
"""Interlaced-wake two-strand binding suite: T0-T8 acceptance tests for the
inter-strand imbalance-gradient wake (E1/E3 candidate, director-approved
design 2026-08-07).

Run:  python two-fluid/run_two_strand_interlaced_wake.py            (t=40)
      python two-fluid/run_two_strand_interlaced_wake.py --calibrate
      python two-fluid/run_two_strand_interlaced_wake.py --tend 4   (smoke)
      python two-fluid/run_two_strand_interlaced_wake.py --arms <tag> --tend 80
            (t=80 plateau on the binding arm, fresh solver)

Scratch layer on the canonical solver (cassi_two_fluid_3d_gpu.py is never
edited; the layer subclasses ExpandingTwoFluid3DGPU):

DESIGN (hypotheses/two-strand-five-channel-matter-organization.md §3.4/§5
E1/E3, the director-approved interlaced-wake term).  The two nulls that
frame it: the eps^2-sourced wake peaks at the ridge cores (outward flux,
wrong direction) and collapses via the eps^3 Keller-Segel feedback; the
J/curl-J/phase-curvature candidates are proportional to Delta_theta^2,
which relaxes 0.265 -> 0.042 rad by t=40 (E7), so their binding force
evaporates.  The interlaced source is the imbalance-gradient density:

    S = (1-q) |grad eps|^2 / rho,   eps = EY - phi EI,  rho = EY + EI

which on the committed sep=12 init peaks at the pair midpoint (measured
43x the eps-extremum value, the points where the null eps^2-wake
peaked): the wake sits BETWEEN the strands, and the mass-like flux pulls
both ridges inward.  The eps-feedback through div(eps grad W) relaxes
the imbalance at the eps-extrema (div * eps > 0 there: W* rises toward
the midpoint max, so lap W* > 0 at the extrema -- the opposite sign of
the eps^2-wake's core blowup); the flank feedback is envelope-bounded
wall sharpening, not the eps^3 collapse (T2 checks the signs every run).

    Wake field W (updated ONCE per rk2_step, after the clamp, from the
    final clamped fields -- the IIR-memory discipline):
        dW/dt = -W/tau_W + S/tau_W + (ell^2/tau_W) laplacian(W)
        tau_W = 1/lam (the framework conversion timescale)
        ell = ELL_L = SIG*(L/N) L-units (the unit-covariant operator
        length; protocol -- the ridge width SIG is initialization, E4
        open; the raw-cells length over-diffuses 58.4x, documented in
        run_two_strand_binding_unit_corrected.py)
        spectral update: W_hat <- [W_hat (1 - dt/tau_W (1 + ell^2 k^2))
                                   + (dt/tau_W) S_hat] * dealias
        W(0) = 0 (protocol: the wake is caused by the pair; a nonzero
        W(0) would be a drive, not the model)

    Aggregation flux (mass-like, both components, added in rhs after the
    canonical gate/conv block):
        dE_a/dt  ⊃  -g div(E_a grad W)        (a = Y, I)
    The divergence form conserves each component's total mass exactly.
    g = 0: every hook is guarded, so the layer is bit-inert (T0).

PROVENANCE (parameter-inventory.md §9/§10 discipline):
    g     NEW dimensionless constant -- the one new degree of the model
          term.  Hypothesized tier; NOT a phi-power; registered in the
          §9 symbol table + §10 ledger only if T4 and T5 pass (the
          director's registration condition); otherwise the
          non-registration is recorded explicitly in the verdicts.
    tau_W = 1/lam   framework (conversion timescale; lam = 1/(2w) = 0.1
          derived; 0.05 in the probe protocol)
    ell  = ELL_L = SIG*(L/N)   PROTOCOL (ridge-width initialization, E4
          open) -- flagged as protocol so it cannot masquerade as a
          framework scale
    S    existing fields only: the canonical Qi coherence gate (1-q) with
          q = rho^2/(rho^2 + phi^-2 + eps^2), rho, |grad eps|^2 (the
          conversion dynamics keep the 'five' gate untouched)
    S_FLOOR = 1e-20   NUMERICAL (protocol, like the solver's 1e-30
          guards): the sep0 one-string state carries float-noise eps ~
          1e-14 from the separate ey/ei pipelines, so the noise-level
          source is ~1e-25 -- 5 orders below the floor, 16 orders below
          the pair source.  Flooring S keeps W identically zero on the
          one-string state: the exact one-string limit becomes bit-exact
          (T3).  Not a physics threshold; never engages on the pair.
    W(0) protocol: identically zero

COUPLING CALIBRATION (PRE-REGISTERED, before any run): the wake fixed
point on the frozen sep=12 init, W* = ifftn(S_hat * dealias /
(1 + ELL_L^2 k^2)), defines the static flux speed at the ridge OUTER
slopes, v = g |dW*/dx| (cells/t per unit g; the symmetric gradient at the
ridge cores is ~0 by symmetry, so the outer slopes carry the
calibration).  g* is set so that v at the outer slopes equals the
measured escape drift V_ESCAPE = 0.2 cells/t (the TS1 late-window rate,
doc §3.3); the bracket is the minimal (g*/3, g*, 3 g*) triple.

ARMS (fresh solver per arm, N=48, lam=0.05, dt=0.001, gate 'five';
t = 4 = 0.2/lambda for the characterization window, t = 40 = 2/lambda
for the lock-timescale verdicts, t = 80 = 4/lambda for the d0 plateau on
the binding arm):
  ctrl    canonical ExpandingTwoFluid3DGPU, sep12  -- T0 control + T8
          continuity + T4/T7 control
  g0      interlaced sep12, g = 0                  -- T0 bit-exact no-op
  i12_lo  interlaced sep12, g = g*/3              -- T4 (sub-critical)
  i12_*   interlaced sep12, g = g*                -- T4 + T6 + T7
  i12_hi  interlaced sep12, g = 3 g*              -- T4
  s0_0    interlaced sep0,  g = 0                 -- T3 reference
  s0_s    interlaced sep0,  g = g*                -- T3 one-string
  <tag>_t80 interlaced sep12 at the binding g, t = 80 -- T5 (run with
          --arms <tag> --tend 80 after the t=40 suite)

VERDICTS (results.json), T0-T8 exactly as designed:
  T0  bit-exact no-op at g = 0 vs canonical: max|dEY| = max|dEI| =
      max|du| = 0.0 at t=4 and t=40, full histories equal.
  T1  source geometry: S(mid)/S(eps-extremum) > 10 on the frozen sep12
      init (the extrema are where the null eps^2-wake peaked); S and W*
      peaks within +-1 cell of the pair midpoint; W* bounded (max <= 10).
  T2  anti-collapse signs: div(eps grad W*) * eps > 0 at both eps-
      extrema on the frozen init (the cores relax; the eps^2-wake
      collapse was the opposite sign there); the four density-ridge
      flanks recorded as data (envelope-bounded sharpening, not the core
      blowup).
  T3  one-string preservation: sep0 at g* == sep0 at g=0 with field and
      history diffs EXACTLY 0.0 at t=4 and t=40 (S = 0 identically on
      sep0, so W stays identically 0 and the flux is identically 0).
  T4  binding at t=40: TS1 band (back-20% mean d in [0.25 d0, 1.2 d0]),
      d(40) < d(20) - 0.3, d(t) <= d_ctrl(t) + 0.5 for t >= 20, two-hump
      axial rho profile at t=40 with a real midpoint dip persistent over
      every 1.0 checkpoint in t in [30,40]; monotone-in-g across the
      bracket (d40 strictly decreasing, dip depth strictly increasing).
  T5  d0 plateau at t=80 on the binding arm: |d(80) - d(60)| < 0.05
      cells; d0/sigma in (1.5, 2.4) with sigma = SIG (protocol); sharp
      sub-check d0 = phi*sigma = 8.09 cells (Speculative, NS7-gated).
  T6  no clamp pathologies at g*: zero floor touches, mass drift <=
      1e-11, W bounded (no NaN, max <= 10), smooth.
  T7  parity/phase constraints at g*: Rc drift <= 2x the control's; the
      bound state stays on the even-multiple interlace branch
      (delta_theta_end <= 0.15 rad, TS5 coincident pentagons preserved).
  T8  continuity: ctrl passes the published t=4 baseline (reproduction
      check) and the t=40 TS1 record (d 9.90 -> 15.73, back-20% 15.00,
      delta_theta_end 0.042, A_plus_end 0.090, q_mid_end 0.7081).

REGISTRATION RULE (director): g is registered in parameter-inventory.md
§9/§10 (Hypothesized, not counted in the §7 totals) if and only if T4
and T5 pass; otherwise the non-registration is recorded explicitly in
the doc update and in this suite's verdicts.

MEASURED OUTCOME (2026-08-07, run record 20260807_150042_interlaced_wake,
regenerated by this script): T0-T3 and T8 PASS (bit-exact no-op, source
geometry 65x, anti-collapse frozen-init signs, bit-exact one-string,
continuity); T4/T6/T7 NULL — every bracket coupling {154.66, 463.99,
1391.96} collapses (NaN at t = 0.9 / 0.5 / 0.3): the mass-like flux
sharpens the eps-wall to grid scale, |grad eps|^2 grows without bound
(the (1-q) gate floor keeps the source alive), and the recorded W_max
grows super-linearly up to the NaN step (2.6e-6 -> 0.0138 on the last
valid snapshot of the g/3 arm; 0.0063 at g*; 0.0019 at 3g*).  The
wake family is closed as an E1 mechanism; g is NOT registered (T4 null
— every bracket arm NaN; T5 not run — no binding arm existed).  The
frozen-init anti-collapse audit (T2) does not bound the
dynamical self-sharpening: the eps-envelope acquires grid-scale ripple
whose |grad eps|^2 drives the source without bound.

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_interlaced_wake/run_<arm>.json   per-arm histories
  runs/<rid>_interlaced_wake/results.json     meta + summaries + verdicts
  runs/<rid>_interlaced_wake_t80/             the T5 continuation
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
import run_two_strand_probe as P            # baseline probe, read-only
import run_two_strand_binding_suite as B    # committed suite (analysis
                                            # functions + init), read-only
import cassi_two_fluid_3d_gpu as C          # canonical solver, read-only

T = B.T
LAM = 0.05
DT = 0.001
SEP = 12                     # baseline pair separation (cells)
V_ESCAPE = 0.2               # cells/t (TS1 late-window drift, doc §3.3)
BRACKET_FACTORS = (1.0 / 3.0, 1.0, 3.0)   # minimal bracket around g*
DX = T.L / T.N               # 0.13090 L-units per cell
ELL_L = P.SIG * DX           # unit-covariant operator length: 0.65450
W_MAX_BOUND = 10.0           # T6 wake boundedness ceiling (committed)
S_FLOOR = 1e-20              # numerical source floor (protocol, like the
                             # solver's 1e-30 guards): the one-string sep0
                             # state carries float-noise eps ~ 1e-14 from
                             # the separate ey/ei diffusion pipelines, so
                             # |grad eps|^2/rho ~ 1e-25 there; flooring S
                             # at 1e-20 (5 orders above the noise, 16
                             # orders below the pair source ~ 1e-4) keeps
                             # W identically zero on the one-string state
                             # in finite precision: the exact one-string
                             # limit of the term becomes bit-exact (T3).
                             # Not a physics threshold; never engages on
                             # the pair.
D0_SIGMA_BAND = (1.5, 2.4)   # T5 dimensionless d0 band (design)
PHI_SIGMA = C.PHI * P.SIG    # 8.0902 cells -- the sharp sub-check


def tag_of(g):
    """Arm tag for a coupling value: 400.0 -> 'i12_400', 133.3 -> 'i12_133.3'."""
    return f"i12_{'%.4g' % g}"


def _round_g(x):
    return float(round(x, 3))


def calibrate(solver):
    """Static source-geometry, flank-damping, and flux/escape calibration
    on the frozen sep=12 init (pre-registered rule; no run needed).

    Wake fixed point with the unit-covariant operator,
        W* = ifftn(S_hat * dealias / (1 + ELL_L^2 k^2)),  S = (1-q)
        |grad eps|^2 / rho,
    defines the static flux speed at the ridge outer slopes,
        v [cells/t] = g * |dW*/dx|  (per-cell gradient),
    and g* = V_ESCAPE / max|dW*/dx| over the two outer slopes
    (x = ridge +- SIG).  The gradient axis follows the unit-corrected
    suite: the physical-x gradient (the ridge axis) is _grad(...)[2],
    per-cell = per-L * dx (verified against a 4th-order central
    difference on the axial profile).  The T1 geometry audit and the T2
    flank-damping audit are computed here from the same snapshot.
    """
    ey_hat, ei_hat, _ = B.two_lobe_init(solver, SEP)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    eps = ey - C.PHI * ei
    rho = ey + ei
    # Design source gate: canonical Qi coherence q (see _update_wake).
    M = rho * rho
    eps2 = eps * eps
    one_minus_q = 1.0 - M / (M + C.PHI_INV * C.PHI_INV + eps2)
    geps = solver._grad(torch.fft.fftn(eps))
    ge2 = sum(g * g for g in geps)
    S = one_minus_q * ge2 / rho
    S = torch.where(S < S_FLOOR, torch.zeros_like(S), S)
    S_hat = torch.fft.fftn(S)
    W_hat = S_hat * solver.dealias / (1.0 + ELL_L * ELL_L * solver.k2)
    W = torch.fft.ifftn(W_hat).real
    gw = solver._grad(torch.fft.fftn(W))

    cy = cz = solver.N // 2
    S_ax = S[:, cy, cz].cpu().numpy()
    W_ax = W[:, cy, cz].cpu().numpy()
    rho_ax = rho[:, cy, cz].cpu().numpy()

    # T1 geometry.  The source reference is the imbalance EXTREMA (the
    # points where the null eps^2-wake peaked): the interlaced source must
    # dominate the midpoint over the extrema by > 10x (design audit on the
    # committed init: 43x).  The density ridges sit at 19.05/28.95 (the
    # cross-ridge tails pull the rho peaks inward, doc §3.4) and are NOT
    # the right reference: the eps^2-source is also small at the density
    # ridges (it peaks at the eps-extrema, 1.65 cells outward).
    eps_ax = eps[:, cy, cz].abs().cpu().numpy()
    e_left = int(np.argmax(eps_ax[: solver.N // 2]))
    e_right = solver.N // 2 + int(np.argmax(eps_ax[solver.N // 2:]))
    s_peak_i = int(np.argmax(S_ax))
    s_mid = float(S_ax[solver.N // 2])
    s_core = max(float(S_ax[e_left]), float(S_ax[e_right]))
    w_peak_i = int(np.argmax(W_ax))
    t1 = {
        'S_peak_x': s_peak_i, 'S_mid': s_mid,
        'S_eps_extremum': s_core,
        'S_mid_over_core': s_mid / max(s_core, 1e-30),
        'eps_extrema': [e_left, e_right],
        'W_peak_x': w_peak_i, 'W_max': float(W.max()),
        'peak_at_mid': abs(s_peak_i - solver.N / 2.0) <= 1.0
                       and abs(w_peak_i - solver.N / 2.0) <= 1.0,
    }

    # T2 anti-collapse signs.  dt_eps ⊃ -g div(eps grad W), so the wake's
    # eps-feedback relaxes the imbalance where div(eps grad W) * eps > 0.
    # The Keller-Segel collapse of the null eps^2-wake was the opposite
    # sign at the extrema: its source sat ON the extrema, so lap W < 0
    # there and dt_eps aligned with eps (explosive).  The interlaced
    # source sits at the node, so W* rises toward the midpoint max,
    # lap W* > 0 at the extrema: the cores relax.  The four density-ridge
    # flanks (x = ridge +- SIG) are recorded as data: their feedback is
    # envelope-bounded wall sharpening (the local eps cannot exceed the
    # E(g1-g2) envelope), not the core blowup; the criterion rests on the
    # extrema.
    lapW = torch.fft.ifftn(-solver.k2 * torch.fft.fftn(W)).real
    t2 = {}
    for name, i in (('eps_extremum_left', e_left),
                    ('eps_extremum_right', e_right)):
        geps_i = [float(g[i, cy, cz].cpu()) for g in geps]
        gw_i = [float(g[i, cy, cz].cpu()) for g in gw]
        e_val = float(eps[i, cy, cz].cpu())
        div_ew = float(np.sum([a * b for a, b in zip(geps_i, gw_i)])
                       + e_val * lapW[i, cy, cz].cpu().item())
        t2[name] = {'x': i, 'eps': e_val, 'div_eps_gradW': div_ew,
                    'relaxing': div_ew * e_val > 0.0}

    p = rho_ax
    pampl = (p - p.min()) / max(p.max() - p.min(), 1e-30)
    idx = np.where((pampl[1:-1] >= pampl[:-2]) &
                   (pampl[1:-1] >= pampl[2:]) &
                   (pampl[1:-1] > P.RIDGE_THRESH))[0] + 1
    ridges = []
    for i in idx:
        y0, y1, y2 = p[i - 1], p[i], p[i + 1]
        denom = y0 - 2.0 * y1 + y2
        d = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-14 else 0.0
        ridges.append(i + (d if abs(d) <= 2.0 else 0.0))
    ridges = sorted(ridges)[:2]
    r1, r2 = ridges[0], ridges[1]

    flanks = {
        'inner_left': int(round(r1 + P.SIG)),   # toward the midpoint
        'inner_right': int(round(r2 - P.SIG)),
        'outer_left': int(round(r1 - P.SIG)),
        'outer_right': int(round(r2 + P.SIG)),
    }
    for name, i in flanks.items():
        i = max(1, min(solver.N - 2, i))
        geps_i = [float(g[i, cy, cz].cpu()) for g in geps]
        gw_i = [float(g[i, cy, cz].cpu()) for g in gw]
        e_val = float(eps[i, cy, cz].cpu())
        div_ew = float(np.sum([a * b for a, b in zip(geps_i, gw_i)])
                       + e_val * lapW[i, cy, cz].cpu().item())
        t2[name] = {'x': i, 'eps': e_val, 'div_eps_gradW': div_ew,
                    'div_eps_gradW_times_eps': div_ew * e_val}

    # Calibration (pre-registered rule): outer-slope gradients.
    g_outer = []
    for name in ('outer_left', 'outer_right'):
        i = flanks[name]
        g_outer.append(float(gw[2][i, cy, cz] * DX))
    gmax = max(abs(g) for g in g_outer)
    g_star = V_ESCAPE / gmax if gmax > 1e-30 else float('inf')
    bracket = sorted({_round_g(g_star * f) for f in BRACKET_FACTORS})
    if len(bracket) < 3:
        bracket = sorted({round(g_star * f, 2) for f in BRACKET_FACTORS})

    # FD4 cross-check on the axial profile at the outer slopes.
    fd = {}
    for name in ('outer_left', 'outer_right'):
        i = flanks[name]
        fd[name] = float((-W_ax[i + 2] + 8.0 * W_ax[i + 1] - 8.0 * W_ax[i - 1]
                          + W_ax[i - 2]) / 12.0)

    return {
        'ridges': ridges, 'DX': DX, 'ELL_L': ELL_L,
        'ell_committed_cells': P.SIG,
        'S_max': float(S.max()), 'W_max_corrected': float(W.max()),
        'W_peak_ratio_S_corrected': float(W.max() / max(S.max(), 1e-30)),
        'T1': t1, 'T2': t2,
        'gradW_outer_slopes_cells_per_t_per_g': g_outer,
        'fd4_check': fd,
        'axis_verified': all(
            abs(g_outer[k] - fd[n]) < 2e-3 * max(abs(fd[n]), 1e-30)
            for k, n in enumerate(('outer_left', 'outer_right'))),
        'g_star': g_star, 'bracket': bracket,
        'bracket_factors': list(BRACKET_FACTORS),
        'v_escape_cells_per_t': V_ESCAPE,
        'pre_registration': 'g* = V_ESCAPE / max|dW*/dx| at the ridge '
                            'outer slopes (x = ridge +- SIG) on the '
                            'frozen sep12 init, recorded before any arm '
                            'is run',
    }


# ── The scratch layer (canonical solver untouched) ───────────────────────

class InterlacedWakeLayer(C.ExpandingTwoFluid3DGPU):
    """ExpandingTwoFluid3DGPU + the interlaced-wake scratch layer.

    g = 0 reproduces the canonical solver bit-for-bit (every hook is
    guarded; W is never allocated).  tau_w = 1/lam is a framework anchor;
    ell = ELL_L is a protocol length (SIG ridge width in L-units, E4
    open); g is the new model constant under test (Hypothesized).
    """

    def __init__(self, g=0.0, ell=ELL_L, tau_w=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.g = g
        self.ell = ell
        self.tau_w = tau_w if tau_w is not None else 1.0 / self.lam
        self.W = None  # wake field, allocated lazily (never at g = 0)

    def _update_wake(self, ey, ei, dt):
        """One IIR step of the wake field from the final clamped fields."""
        if self.W is None:
            self.W = torch.zeros_like(ey)
        eps = ey - C.PHI * ei
        rho = ey + ei
        # The design's source gate is the canonical Qi coherence q =
        # rho^2/(rho^2 + phi^-2 + eps^2) (not the 'five' conversion-gate
        # openness, which is direction-blind and flattens the
        # mid-vs-core contrast); the conversion dynamics keep the 'five'
        # gate untouched.
        M = rho * rho
        eps2 = eps * eps
        one_minus_q = 1.0 - M / (M + C.PHI_INV * C.PHI_INV + eps2)
        geps = self._grad(torch.fft.fftn(eps))
        ge2 = sum(g * g for g in geps)
        S = one_minus_q * ge2 / rho
        S = torch.where(S < S_FLOOR, torch.zeros_like(S), S)
        Wh = torch.fft.fftn(self.W)
        factor = 1.0 - (dt / self.tau_w) * (1.0 + self.ell * self.ell * self.k2)
        Wh = (Wh * factor + (dt / self.tau_w) * torch.fft.fftn(S)) * self.dealias
        self.W = torch.fft.ifftn(Wh).real

    def rhs(self, u_hat, ey_hat, ei_hat):
        if self.g == 0.0:
            # canonical path, zero extra operations: bit-for-bit no-op
            return super().rhs(u_hat, ey_hat, ei_hat)
        r = list(super().rhs(u_hat, ey_hat, ei_hat))
        if self.W is not None:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            grad_w = self._grad(torch.fft.fftn(self.W))
            # dE_a/dt ⊃ -g div(E_a grad W); divergence-form flux conserves
            # each component's total mass exactly.
            fy = [self.g * ey * g for g in grad_w]
            fi = [self.g * ei * g for g in grad_w]
            r[1] = r[1] - self._divergence_of_flux(fy) * self.dealias
            r[2] = r[2] - self._divergence_of_flux(fi) * self.dealias
        return tuple(r)

    def rk2_step(self, u_hat, ey_hat, ei_hat, dt):
        u_hat, ey_hat, ei_hat = super().rk2_step(u_hat, ey_hat, ei_hat, dt)
        if self.g != 0.0:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            self._update_wake(ey, ei, dt)
        return u_hat, ey_hat, ei_hat


# ── Builders (fresh solver per arm) ─────────────────────────────────────

def build_canonical(device):
    return B.build_canonical(device)


def build_interlaced(device, g, ell=ELL_L, tau_w=None):
    solver = InterlacedWakeLayer(
        N=T.N, L=T.L, nu=T.NU, D=T.D, lam=T.LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True, qi_memory=False,
        device=device, g=g, ell=ell, tau_w=tau_w)
    solver.gate_model = 'five'
    return solver


def build_for(kind, device, g):
    if kind == 'canonical':
        return build_canonical(device)
    return build_interlaced(device, g)


# ── Run one arm ──────────────────────────────────────────────────────────

def run_case(builder, sep, tag, outdir, steps, report):
    """Evolve one arm (fresh solver), recording diagnostics every `report`
    steps plus the axial rho profile and box rho mean at every record."""
    solver = builder()
    print(f"\n=== run: {tag} (sep={sep}, g={getattr(solver, 'g', 0.0)}) ===")
    ey_hat, ei_hat, u_hat = B.two_lobe_init(solver, sep)
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
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
        if step % report == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            if bool(torch.isnan(ey).any()) or bool(torch.isnan(ei).any()):
                nan_abort = step
                print(f"  [{tag}] NaN in the fields at step {step} "
                      f"(t={step * DT:.3f}); aborting the arm")
                break
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = B.measure_strands_safe(solver, ey, ei, rho_prof, centers,
                                       prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * DT,
                      'rho_prof_ax': (ey + ei)[:, cy, cz].cpu().numpy().tolist(),
                      'rho_mean': float((ey + ei).mean())})
            if d['ey_min'] < 1.01e-3 or d['ei_min'] < 1.01e-3:
                floor_touch += 1
            if getattr(solver, 'W', None) is not None:
                d['W_max'] = float(solver.W.max())
                d['W_mean'] = float(solver.W.mean())
            hist.append(d)
            if step % (10 * report) == 0 or step == steps - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                wtxt = (f" | W_max={d['W_max']:.4f}" if 'W_max' in d else '')
                print(f"  t={step*DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                      f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}"
                      f"{wtxt}")
    ey1 = torch.fft.ifftn(ey_hat).real
    ei1 = torch.fft.ifftn(ei_hat).real
    mass1 = float((ey1 + ei1).sum())
    mass_drift = abs(mass1 - mass0) / mass0
    w_end = (float(solver.W.max())
             if getattr(solver, 'W', None) is not None else 0.0)
    grad_w_end = 0.0
    if getattr(solver, 'W', None) is not None:
        gw = solver._grad(torch.fft.fftn(solver.W))
        grad_w_end = float(max(g.cpu().abs().max() for g in gw))
    elapsed = time.time() - t0
    meta = {'elapsed': elapsed, 'floor_touch': floor_touch,
            'mass0': mass0, 'mass1': mass1, 'mass_drift': mass_drift,
            'W_max_end': w_end, 'grad_w_max_end': grad_w_end,
            'nan_abort': nan_abort}
    print(f"  [{tag}] {steps} steps in {elapsed:.1f}s "
          f"(floor touches: {floor_touch}, mass drift: {mass_drift:.2e}, "
          f"W_max_end: {w_end:.4f}, |gradW|_max_end: {grad_w_end:.4f})")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'sep': sep,
                       'g': getattr(solver, 'g', 0.0),
                       'hist': hist, 'meta': meta}, f, indent=1)
    return hist, meta, (u_hat, ey_hat, ei_hat), solver


# ── Arm definitions and verdicts ─────────────────────────────────────────

def arm_defs(g_star):
    lo, star, hi = (_round_g(g_star * BRACKET_FACTORS[0]),
                    _round_g(g_star), _round_g(g_star * BRACKET_FACTORS[2]))
    return [
        ('ctrl', 'canonical', SEP, 0.0),
        ('g0', 'interlaced', SEP, 0.0),
        (tag_of(lo), 'interlaced', SEP, lo),
        (tag_of(star), 'interlaced', SEP, star),
        (tag_of(hi), 'interlaced', SEP, hi),
        ('s0_0', 'interlaced', 0.0, 0.0),
        ('s0_s', 'interlaced', 0.0, star),
    ], star


def run_arms(rdir, arm_list, device, defs, steps, report):
    arms, meta, states = {}, {}, {}
    for spec in defs:
        tag = spec[0]
        if tag not in arm_list:
            continue
        kind, sep = spec[1], spec[2]
        g = spec[3]
        h, m, st, _ = run_case(
            lambda: build_for(kind, device, g), sep, tag, rdir,
            steps, report)
        torch.save({'u': [x.cpu() for x in st[0]],
                    'ey': st[1].cpu(), 'ei': st[2].cpu()},
                   f"{rdir}/state_{tag}.pt")
        arms[tag], meta[tag], states[tag] = h, m, st
    return arms, meta, states


def load_arms(rdir, arm_list):
    arms, meta, states = {}, {}, {}
    for tag in arm_list:
        with open(f"{rdir}/run_{tag}.json") as f:
            rec = json.load(f)
        arms[tag] = rec['hist']
        meta[tag] = rec['meta']
        st = torch.load(f"{rdir}/state_{tag}.pt", map_location='cpu')
        states[tag] = (st['u'], st['ey'], st['ei'])
    return arms, meta, states


def compute_verdicts(arms, meta, states, rdir, g_star, calib, t_end, steps):
    defs, star = arm_defs(g_star)
    required = {s[0] for s in defs}
    missing = sorted(required - set(arms))
    if missing:
        print(f"[verdicts skipped: arm subset lacks {missing}; "
              f"run the full arm set for T0-T8]")
        return None
    sums = {tag: B.arm_summary(h) for tag, h in arms.items()}
    full = t_end >= 40.0 - 1e-9

    # T0 bit-exact no-op
    t0_ok, t0_d = B.t1_verdict(arms['ctrl'], arms['g0'],
                               states['ctrl'], states['g0'])
    # T8 continuity
    repro_ok, repro_got, repro_ref, repro_tol = \
        B.reproduction_check(arms['ctrl'])
    last = arms['ctrl'][-1]
    ts1_ref = {'d_end': 15.7346, 'd_back_mean': 14.9966,
               'delta_theta_end': 0.0420, 'A_plus_end': 0.0898,
               'q_mid_end': 0.7081}
    ts1_tol = {'d_end': 0.10, 'd_back_mean': 0.10,
               'delta_theta_end': 0.010, 'A_plus_end': 0.020,
               'q_mid_end': 0.002}
    cs = sums['ctrl']
    ts1_got = {'d_end': last['d'], 'd_back_mean': cs['d_back_mean'],
               'delta_theta_end': last['delta_theta'],
               'A_plus_end': last['A_plus'], 'q_mid_end': last['q_mid']}
    t8_ok = (repro_ok and
             all(abs(ts1_got[k] - ts1_ref[k]) <= ts1_tol[k]
                 for k in ts1_ref))

    # T1 / T2 from the frozen-init calibration
    t1_ok = (calib['T1']['S_mid_over_core'] > 10.0
             and calib['T1']['peak_at_mid']
             and calib['T1']['W_max'] <= W_MAX_BOUND)
    t2_ok = (calib['T2']['eps_extremum_left']['relaxing']
             and calib['T2']['eps_extremum_right']['relaxing'])

    # T3 one-string bit-exact
    t3_ok, t3_d = True, {}
    du, dey, dei = B.state_diff(states['s0_0'], states['s0_s'])
    hd = B.hist_diff(arms['s0_0'], arms['s0_s'])
    at4 = None
    r4_0 = [d for d in arms['s0_0'] if abs(d['t'] - 4.0) < 1e-9]
    r4_s = [d for d in arms['s0_s'] if abs(d['t'] - 4.0) < 1e-9]
    if r4_0 and r4_s:
        at4 = B.hist_diff(r4_0, r4_s)
    t3_ok = (du == 0.0 and dey == 0.0 and dei == 0.0 and hd == 0.0
             and (at4 is None or at4 == 0.0))
    t3_d = {'max_du': du, 'max_dey': dey, 'max_dei': dei,
            'max_hist_diff': hd, 't4_hist_diff': at4}

    # T4 binding at the lock timescale (only on full runs)
    t4 = {}
    for spec in defs:
        tag = spec[0]
        if tag.startswith('i12_') and tag != 'g0':
            g = spec[3]
            ok, d = B.t2_verdict(arms[tag], arms['ctrl'], g)
            t4[tag] = {'verdict': 'passed' if ok else 'null',
                       'detail': d, 'ts1_outcome': B.ts1_outcome(d, sums[tag])}
    order = [s[0] for s in defs if s[0].startswith('i12_') and s[0] != 'g0']
    d40s = [t4[t]['detail']['d40'] for t in order]
    depths = [t4[t]['detail']['two_hump_t40_detail'].get('dip_depth')
              for t in order]
    mono_d = all(d40s[i] > d40s[i + 1] for i in range(len(d40s) - 1))
    mono_depth = all(depths[i] is not None and depths[i + 1] is not None
                     and depths[i] < depths[i + 1]
                     for i in range(len(depths) - 1))
    mono = mono_d and mono_depth

    # T6 telemetry at g*
    star_tag = tag_of(star)
    w_series = [d.get('W_max', 0.0) for d in arms[star_tag]]
    w_has_nan = any(np.isnan(v) for v in w_series)
    t6_ok, t6_d = B.t4_verdict(meta[star_tag], meta['ctrl'], t4[star_tag],
                               sums[star_tag]['W_max_over_run'],
                               meta[star_tag]['grad_w_max_end'], w_has_nan)

    # T7 parity/phase constraints at g*
    rc_ok = sums[star_tag]['Rc_drift'] <= 2.0 * sums['ctrl']['Rc_drift'] + 1e-9
    dth_ok = sums[star_tag]['delta_theta_end'] <= 0.15
    t7_ok = rc_ok and dth_ok
    t7_d = {'Rc_drift_star': sums[star_tag]['Rc_drift'],
            'Rc_drift_ctrl': sums['ctrl']['Rc_drift'],
            'Rc_ok': rc_ok,
            'delta_theta_end_star': sums[star_tag]['delta_theta_end'],
            'delta_theta_ok': dth_ok}

    results = {
        'meta': {'N': T.N, 'lam': LAM, 'dt': DT, 'steps': steps,
                 't_end': t_end, 'gate_model': 'five (solver)',
                 'E_RIDGE': P.E_RIDGE, 'BETA': P.BETA, 'SIG': P.SIG,
                 'SEP': SEP, 'R_SITE': P.R_SITE,
                 'G_STAR': star, 'G_BRACKET': [round(g_star * f, 3)
                                               for f in BRACKET_FACTORS],
                 'tau_w': 1.0 / LAM, 'ell_L': ELL_L,
                 'ell_provenance': 'PROTOCOL: ELL_L = SIG*(L/N), the '
                                   'unit-covariant ridge-width operator '
                                   'length (E4 open; not a framework '
                                   'constant)',
                 'g_provenance': 'NEW dimensionless constant (the one new '
                                 'degree); Hypothesized tier, not a '
                                 'phi-power; registered in '
                                 'parameter-inventory.md §9/§10 only if '
                                 'T4 and T5 pass',
                 'W0': 'identically zero (protocol: the wake is caused by '
                       'the pair)',
                 'calibration': calib,
                 'layer': 'interlaced wake W: dW/dt = -W/tau + S/tau + '
                          '(ELL_L^2/tau) laplacian(W), '
                          'S = (1-q) |grad eps|^2 / rho; flux: '
                          'dE_a/dt ⊃ -g div(E_a grad W)',
                 'arms': meta,
                 'criteria': {
                     'T0': 'g=0 bit-exact vs canonical: max|dEY|=max|dEI|'
                           '=max|du|=0.0 at t=4 and t=40, full histories '
                           'equal',
                     'T1': 'S(mid)/S(eps-extremum) > 10 on the frozen '
                           'sep12 init (the extrema are where the null '
                           'eps^2-wake peaked); S and W* peaks within '
                           '+-1 cell of the midpoint; W* max <= 10',
                     'T2': 'div(eps grad W*) * eps > 0 at both eps-'
                           'extrema on the frozen init (the cores relax; '
                           'the eps^2-wake collapse was the opposite sign '
                           'there); the four density-ridge flanks recorded '
                           'as data (envelope-bounded sharpening, not the '
                           'core blowup)',
                     'T3': 'sep0 at g* == sep0 at g=0: field/history diffs '
                           'EXACTLY 0.0 at t=4 and t=40',
                     'T4': 'TS1 band at t=40; d(40) < d(20) - 0.3; '
                           'd(t) <= d_ctrl(t) + 0.5 for t >= 20; two-hump '
                           'persistence over t in [30,40]; monotone-in-g '
                           'across the calibrated bracket',
                     'T5': 't=80 plateau on the binding arm: '
                           '|d(80) - d(60)| < 0.05; d0/sigma in (1.5, 2.4); '
                           'sharp sub-check d0 = phi*sigma = 8.09 cells',
                     'T6': 'no floor touches, ey/ei >= 1.01e-3, mass drift '
                           '<= 1e-11, W bounded (max <= 10, no NaN), smooth',
                     'T7': 'Rc drift at g* <= 2x control; '
                           'delta_theta_end <= 0.15 rad (even-multiple '
                           'interlace branch, TS5 preserved)',
                     'T8': 'ctrl passes the published t=4 baseline and the '
                           't=40 TS1 record'}},
        'arms': sums,
        'reproduction_t4': {'ok': repro_ok, 'got': repro_got,
                            'published_ref': repro_ref, 'tol': repro_tol},
        'ts1_record_t40': {'got': ts1_got, 'ref': ts1_ref, 'tol': ts1_tol},
        'verdicts': {
            'T0': {'test': 'bit-exact no-op at g = 0 vs canonical',
                   'verdict': 'passed' if t0_ok else 'null', 'data': t0_d},
            'T1': {'test': 'source geometry (midpoint peak > 10x the '
                           'eps-extrema)',
                   'verdict': 'passed' if t1_ok else 'null',
                   'data': calib['T1']},
            'T2': {'test': 'anti-collapse signs (cores relax: '
                           'div(eps grad W) * eps > 0 at both extrema)',
                   'verdict': 'passed' if t2_ok else 'null',
                   'data': calib['T2']},
            'T3': {'test': 'one-string bit-exact preservation',
                   'verdict': 'passed' if t3_ok else 'null', 'data': t3_d},
            'T4': {'test': 'monotone binding at finite coupling',
                   'arms': t4,
                   'monotone_in_g': mono,
                   'monotone_in_g_data': {'d40': d40s, 'dip_depth': depths,
                                          'd40_strict': mono_d,
                                          'depth_strict': mono_depth}},
            'T5': {'test': 'd0 plateau at t=80 (run via --arms <tag> '
                           '--tend 80)',
                   'verdict': 'not-run', 'data': None},
            'T6': {'test': 'no clamp pathologies at g*',
                   'verdict': 'passed' if t6_ok else 'null', 'data': t6_d},
            'T7': {'test': 'parity/phase constraints at g*',
                   'verdict': 'passed' if t7_ok else 'null', 'data': t7_d},
            'T8': {'test': 'continuity (ctrl reproduces the published '
                           'records)',
                   'verdict': 'passed' if t8_ok else 'null',
                   'data': {'reproduction_t4': repro_ok,
                            'ts1_record': ts1_got}},
            'registration_rule': 'g registered in parameter-inventory.md '
                                 '§9/§10 iff T4 and T5 both pass; else '
                                 'non-registration recorded explicitly',
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== INTERLACED-WAKE SUITE VERDICTS "
          f"(t={t_end}, lock timescale) ===")
    for tag in sorted(sums):
        s = sums[tag]
        print(f"{tag:6s}: ns1={s['ns1']:>9s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back {s['d_back_mean']:.2f}) | "
              f"A+= {s['A_plus_end']:.3f} | q_mid {s['q_mid_end']:.3f} vs "
              f"q_flank {s['q_flank_end']:.3f} | "
              f"W_max {s['W_max_over_run']:.4f} | "
              f"ey_min {s['ey_min']:.4f}")
    print(f"\nT0 (bit-exact no-op): {t0_d['max_du']:.3e} "
          f"{t0_d['max_dey']:.3e} {t0_d['max_dei']:.3e} -> "
          f"{'PASSED' if t0_ok else 'NULL'}")
    print(f"T1 (geometry): S(mid)/S(core) = {calib['T1']['S_mid_over_core']:.1f}x "
          f"S_peak_x={calib['T1']['S_peak_x']} W_peak_x={calib['T1']['W_peak_x']} "
          f"-> {'PASSED' if t1_ok else 'NULL'}")
    t2s = ', '.join(f"{k}={v['div_eps_gradW']:+.2e}(e={v['eps']:+.2f})"
                    for k, v in calib['T2'].items())
    print(f"T2 (anti-collapse signs): {t2s} -> {'PASSED' if t2_ok else 'NULL'}")
    print(f"T3 (one-string bit-exact): max|dEY| {t3_d['max_dey']:.3e} "
          f"hist {t3_d['max_hist_diff']:.3e} -> "
          f"{'PASSED' if t3_ok else 'NULL'}")
    for t in order:
        g = dict((s[0], s[3]) for s in defs)[t]
        dd = t4[t]['detail']
        print(f"T4 {t} (g={g}): "
              f"ts1={t4[t]['ts1_outcome']:>9s} two_hump={dd['two_hump_t40']} "
              f"persist={dd['persistence_frac_30_40']:.2f} "
              f"d40={dd['d40']:.2f} d20={dd['d20']:.2f} "
              f"turn={dd['turnaround']} over_ctrl={dd['max_over_ctrl_t_ge_20']:.2f} "
              f"band={dd['ts1_band']} -> {t4[t]['verdict'].upper()}")
    print(f"T4 monotone-in-g: d40 {[f'{v:.2f}' for v in d40s]} -> "
          f"{'PASSED' if mono else 'NULL'}")
    print(f"T6 (telemetry): floor {meta[star_tag]['floor_touch']} "
          f"mass_drift {meta[star_tag]['mass_drift']:.2e} "
          f"W_max {sums[star_tag]['W_max_over_run']:.4f} -> "
          f"{'PASSED' if t6_ok else 'NULL'}")
    print(f"T7 (parity/phase): Rc_drift {sums[star_tag]['Rc_drift']:.2f} vs "
          f"{sums['ctrl']['Rc_drift']:.2f} (ctrl), "
          f"dth_end {sums[star_tag]['delta_theta_end']:.3f} -> "
          f"{'PASSED' if t7_ok else 'NULL'}")
    print(f"T8 (continuity): t4 {'OK' if repro_ok else 'MISMATCH'}, "
          f"t40 TS1 record {'OK' if t8_ok else 'MISMATCH'}")
    print(f"g* = {star:.3f} (pre-registered escape-slope calibration); "
          f"bracket = {[round(g_star*f, 3) for f in BRACKET_FACTORS]}")
    print(f"\nResults: {rdir}/results.json")
    return results


def compute_t5(rdir, hist, g, sig=P.SIG):
    """T5: d0 plateau on the t=80 binding arm."""
    recs = [d for d in hist if 60.0 - 1e-9 <= d['t'] <= 80.0 + 1e-9]
    d60 = next((d['d'] for d in recs if abs(d['t'] - 60.0) < 1e-9), None)
    d80 = hist[-1]['d'] if hist else None
    plateau = (d60 is not None and d80 is not None
               and abs(d80 - d60) < 0.05)
    d0 = float(np.mean([d['d'] for d in recs])) if recs else float('nan')
    d0_sigma = d0 / sig
    band_ok = D0_SIGMA_BAND[0] < d0_sigma < D0_SIGMA_BAND[1]
    s = B.arm_summary(hist)
    band_ok = band_ok and (s['ns1'] == 'persisted' or s['ns1'] == 'reference')
    merged = s['merged_at_end'] or s['ns1'] == 'merged'
    t5_ok = plateau and band_ok and not merged
    t5 = {
        'verdict': 'passed' if t5_ok else 'null',
        'g': g, 't_window': [60.0, 80.0],
        'd60': d60, 'd80': d80, 'plateau': plateau,
        'd0': d0, 'd0_over_sigma': d0_sigma,
        'band': list(D0_SIGMA_BAND), 'band_ok': band_ok,
        'phi_sigma': PHI_SIGMA, 'd0_minus_phi_sigma': d0 - PHI_SIGMA,
        'ns1': s['ns1'], 'merged': merged,
        'd_start': s['d_start'], 'd_max': s['d_max'],
        'delta_theta_end': s['delta_theta_end'],
        'W_max_over_run': s['W_max_over_run'],
    }
    with open(f"{rdir}/results_t5.json", "w") as f:
        json.dump(t5, f, indent=2)
    print(f"\nT5 (d0 plateau, t=80, g={g}): "
          f"d60={d60:.3f} d80={d80:.3f} plateau={plateau} "
          f"d0={d0:.3f} d0/sigma={d0_sigma:.3f} band={band_ok} "
          f"|d0 - phi*sigma|={abs(d0 - PHI_SIGMA):.3f} -> "
          f"{'PASSED' if t5_ok else 'NULL'}")
    return t5


def main():
    mode = 'run'
    t_end = 40
    arm_list = None
    rdir = None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == '--analyze':
            mode = 'analyze'
        elif argv[i] == '--calibrate':
            mode = 'calibrate'
        elif argv[i] == '--tend':
            t_end = float(argv[i + 1])
            i += 1
        elif argv[i] == '--arms':
            arm_list = argv[i + 1].split(',')
            i += 1
        elif argv[i] == '--rdir':
            rdir = argv[i + 1]
            i += 1
        i += 1
    steps = int(t_end / DT)
    report = 200 if t_end >= 80.0 - 1e-9 else 100
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    cal_solver = build_canonical(device)
    calib = calibrate(cal_solver)
    del cal_solver
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    print(f"\nDevice: {device}  N={T.N}  lam={LAM}  dt={DT}  "
          f"t={t_end}  gate='five'  E_RIDGE={P.E_RIDGE}  BETA={P.BETA}  "
          f"SIG={P.SIG}  SEP={SEP}")
    print(f"PRE-REGISTERED calibration (frozen sep12 init): "
          f"S(mid)/S(core) = {calib['T1']['S_mid_over_core']:.1f}x, "
          f"S_peak_x = {calib['T1']['S_peak_x']} (mid = {T.N/2}), "
          f"W_peak_x = {calib['T1']['W_peak_x']}, "
          f"gradW outer slopes = "
          f"[{calib['gradW_outer_slopes_cells_per_t_per_g'][0]:+.5f},"
          f"{calib['gradW_outer_slopes_cells_per_t_per_g'][1]:+.5f}] "
          f"cells/t per g (FD4 check [{calib['fd4_check']['outer_left']:+.5f},"
          f"{calib['fd4_check']['outer_right']:+.5f}], "
          f"axis_verified={calib['axis_verified']})")
    g_star = calib['g_star']
    print(f"g* = {g_star:.3f} (v_escape = {V_ESCAPE} cells/t); "
          f"bracket = {calib['bracket']}")

    if mode == 'calibrate':
        return

    defs, star = arm_defs(g_star)
    if arm_list is None:
        arm_list = [s[0] for s in defs]
    print(f"arms: {arm_list}")

    if rdir is None:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_interlaced_wake_t{int(t_end)}" if t_end >= 80 else \
            "_interlaced_wake"
        rdir = f"runs/{rid}{suffix}"
    os.makedirs(rdir, exist_ok=True)

    if mode == 'run':
        arms, meta, states = run_arms(rdir, arm_list, device, defs,
                                      steps, report)
    else:
        arms, meta, states = load_arms(rdir, arm_list)
    results = compute_verdicts(arms, meta, states, rdir, g_star, calib,
                               t_end, steps)
    if torch.cuda.is_available():
        torch.cuda.synchronize()   # ROCm teardown deadlocks on async work

    # T5 continuation: t=80 plateau on the binding arm (fresh solver).
    # Invoked as a single-arm run:  --arms <tag> --tend 80 --rdir <dir>
    if t_end >= 80.0 - 1e-9 and arm_list and len(arm_list) == 1:
        tag = arm_list[0]
        with open(f"{rdir}/run_{tag}.json") as f:
            rec = json.load(f)
        t5 = compute_t5(rdir, arms[tag], rec['g'])
        with open(f"{rdir}/results_t5.json", "w") as f:
            json.dump(t5, f, indent=2)
        print(f"\nT5 record: {rdir}/results_t5.json")
    elif results is not None:
        print("T5 not run: invoke --arms <binding-tag> --tend 80 after "
              "the t=40 suite.")


if __name__ == "__main__":
    main()
