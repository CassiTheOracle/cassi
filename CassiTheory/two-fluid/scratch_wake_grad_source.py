#!/usr/bin/env python3
"""Static gate-exact probe: wake sourced between the ridges (S_W ~ |grad eps|^2).

Run:  python two-fluid/scratch_wake_grad_source.py

SCRATCH analysis for the two-strand binding program (director review before
any doc/registry change; canonical solver untouched).  The eps^2 wake of
`hypotheses/two-strand-five-channel-matter-organization.md` §3.4 is slaved to
the ridge peaks and pushes outward (null across chi in {300,1000,3000});
rho-weighting and a cap are rejected.  The one open field-content candidate
is a wake sourced BETWEEN the ridges, S_W ~ |grad eps|^2, so that the
committed mass-like flux -chi_w div(E_a grad W) (attraction toward W maxima)
pulls the pair inward instead of sharpening each hump outward.

UNIT FINDING (director flag): the committed binding suite uses ell = P.SIG
= 5 CELLS against the solver's k in rad/L-units (L = 2*pi, N = 48, so the
box fundamental is k = 2*pi/L = 1.0 rad/L and 5 cells = 0.6545 L-units).
That operator is over-diffusive by (5/0.6545)^2 = 58.4x: ell^2 k^2 = 25 k^2
retains only ~4% of the box fundamental and ~0.25% of the pair-scale modes,
which is the measured "transfer W_peak ~ 1.6e-2 S_peak" (fftn/ifftn is
self-inverse; it is not an ifftn normalization).  This probe uses the
unit-covariant pair ELL_L = SIG*dx in BOTH the source and the wake
operator; the source combination ell^2 |grad eps|^2 is exactly unit-covariant
(ELL_L^2 |grad eps|_L^2 = SIG^2 |grad eps|_cells^2), so the source is
unchanged by the convention; the operator and every flux speed are not.

Exact dimensionless source (existing fields + the committed wake length,
unit-corrected; no new parameter, no arbitrary scale):

    S_W = (1-q) * ELL_L^2 * |grad eps|^2 / rho^2,
    eps = ey - PHI*ei,  rho = ey + ei,
    (1-q) = the solver's own 'five' gate (compute_q_field),
    grad eps = the solver's exact spectral gradient (L-units),
    ELL_L = P.SIG * L/N = 0.6545 L-units (the committed 5-cell length).

Dimensionless by construction; invariant under a uniform rescale
(eps, rho) -> c (eps, rho) (a shape measure, not a magnitude measure);
identically zero on the one-string (eps = 0 -> grad eps = 0 -> S_W = 0 ->
W stays 0 -> flux inert).

Wake operator (committed layer, unit-corrected):
    dW/dt = -W/tau_W + S_W/tau_W + (ELL_L^2/tau_W) laplacian(W),
    tau_W = 1/lam, spectral update
    W_hat <- [W_hat (1 - dt/tau (1 + ELL_L^2 k^2)) + (dt/tau) S_hat] * dealias.
Its exact fixed point on the frozen init fields is the gate-exact static
wake used here:

    W* = ifftn( S_hat * dealias / (1 + ELL_L^2 k^2) ).real

W* is the upper-envelope wake (the t=0 wake is 0 and ramps on the tau_W
timescale); a static verdict against W* is therefore the conservative gate.

Flux (committed sign, unchanged):  dE_a/dt  ⊃  -chi_w div(E_a grad W).
With W peaked between the ridges, grad W points away from the node, so the
flux carries density toward the node (contraction); the sign is the one
already committed in the binding suite -- only the source geometry changes.

Gates (all evaluated on the committed two-lobe init, N=48, lam=0.05,
sep=12, gate 'five', and on the sep=0 one-string reference):

  G1  midpoint source: S_W(mid) > 0, the S_W humps sit between the ridge
      centers (not on them), W*(mid) > W* at both ridge centers, and
      grad W* points inward at both ridge centers (dW*/dx < 0 at the right
      ridge, > 0 at the left).
  G2  no collapse: chi* is calibrated so the static flux speed at the
      ridges equals the measured escape drift (~0.2 cells/t, §3.3).  The
      imbalance feedback at the node flanks, R = |d eps/dt|_flux /
      (lam (1-q) |eps|), must be < 1 at chi* and at the top bracket
      coupling (conversion heals the imbalance faster than the flux
      amplifies it), and the initial ridge-centroid velocities from the
      flux must be inward (d-dot < 0).
  G3  one-string: max|S_W| == 0.0 exactly on sep=0 (and W* == 0 exactly).

Output (runs/ is gitignored): runs/<rid>_grad_source_probe/probe.json with
the axial profiles, gate data, chi* calibration, and verdicts.

The static probe decides whether a PDE bracket is warranted; it never
registers parameters and never touches the canonical solver.
"""

import os
import sys
import json
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_two_strand_probe as P      # committed two-lobe init, read-only
import run_trauma_wake_lock as T
import cassi_two_fluid_3d_gpu as C    # canonical solver, read-only

T.LAM = 0.05
T.DT = 0.001
SEP = 12
DX = T.L / T.N                       # 0.1309 L-units per cell
ELL_L = P.SIG * DX                   # committed 5-cell length, L-units
TAU_W = 1.0 / T.LAM                  # committed wake timescale = 1/lam
V_ESCAPE = 0.2                       # cells/t (TS1 late-window drift, §3.3)
ZONE_HALF = 2.5                      # node-flank amplification zone (cells)
BRACKET_FACTORS = (1.0 / 3.0, 1.0, 3.0)   # minimal bracket around chi*


def build_solver(device):
    return T.build_solver(device)


def grad_source(solver, ey, ei):
    """Exact discrete S_W = (1-q) ELL_L^2 |grad eps|^2 / rho^2."""
    eps = ey - C.PHI * ei
    rho = ey + ei
    _, one_minus_q = solver.compute_q_field(ey, ei)   # 'five' gate
    eps_hat = torch.fft.fftn(eps)
    g = solver._grad(eps_hat)
    grad2 = g[0] * g[0] + g[1] * g[1] + g[2] * g[2]
    return one_minus_q * ELL_L * ELL_L * grad2 / (rho * rho)


def wake_fixed_point(solver, S, ell):
    """Exact fixed point of the wake update on frozen fields:
    W_hat = S_hat * dealias / (1 + ell^2 k^2).  ell in L-units (k in
    rad/L-units); ell = ELL_L is the unit-corrected committed length,
    ell = P.SIG reproduces the committed suite's over-diffusive operator
    (reported for comparison only)."""
    S_hat = torch.fft.fftn(S)
    W_hat = S_hat * solver.dealias / (1.0 + ell * ell * solver.k2)
    return torch.fft.ifftn(W_hat).real


def axial(solver, f):
    """The ridge axis line x at (y, z) = (N/2, N/2)."""
    return f[:, solver.N // 2, solver.N // 2].cpu().numpy()


def ridge_positions(rho_ax):
    """Two rho maxima with parabolic refinement (suite convention)."""
    p = rho_ax
    pampl = (p - p.min()) / max(p.max() - p.min(), 1e-30)
    idx = np.where((pampl[1:-1] >= pampl[:-2]) &
                   (pampl[1:-1] >= pampl[2:]) &
                   (pampl[1:-1] > P.RIDGE_THRESH))[0] + 1
    if len(idx) < 2:
        return None
    out = []
    for i in idx:
        y0, y1, y2 = p[i - 1], p[i], p[i + 1]
        denom = y0 - 2.0 * y1 + y2
        d = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-14 else 0.0
        out.append(i + (d if abs(d) <= 2.0 else 0.0))
    return sorted(out)[:2]


def flux_rates(solver, W, ey, ei, chi_w):
    """Static flux rates on the frozen fields at coupling chi_w:
    returns (d_rho, d_eps) with the committed spectral form
    -chi_w div(E grad W) * dealias, physical space."""
    grad_w = solver._grad(torch.fft.fftn(W))
    rho = ey + ei
    eps = ey - C.PHI * ei
    fr = [chi_w * rho * g for g in grad_w]
    fe = [chi_w * (ey - C.PHI * ei) * g for g in grad_w]
    deal = solver.dealias
    d_rho = torch.fft.ifftn(-solver._divergence_of_flux(fr) * deal).real
    d_eps = torch.fft.ifftn(-solver._divergence_of_flux(fe) * deal).real
    return d_rho, d_eps


def ridge_centroid_velocity(solver, d_rho, rho, xk, sigma=P.SIG):
    """Mass-weighted x-velocity of the ridge ball at xk from the flux:
    v = <(x - xk) d_rho>_ball / <rho>_ball (cells/t; positive = outward)."""
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cy = cz = N_ / 2.0
    dd = (X - xk) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2
    w = torch.exp(-dd / (2.0 * sigma * sigma)) * \
        (dd <= P.R_SITE ** 2).to(torch.float64)
    num = float(((X - xk) * d_rho * w).sum())
    den = float((rho * w).sum())
    return num / den if den > 1e-30 else float('nan')


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  dt={T.DT}  "
          f"gate='five'  E_RIDGE={P.E_RIDGE}  BETA={P.BETA}  SIG={P.SIG}  "
          f"SEP={SEP}  ELL_L={ELL_L:.4f} L-units ({P.SIG} cells)  "
          f"tau_W={TAU_W}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_grad_source_probe"
    os.makedirs(rdir, exist_ok=True)

    out = {'meta': {'N': T.N, 'L': T.L, 'lam': T.LAM, 'dx': DX,
                    'ELL_L': ELL_L, 'tau_w': TAU_W, 'SEP': SEP,
                    'E_RIDGE': P.E_RIDGE, 'BETA': P.BETA, 'SIG': P.SIG,
                    'unit_finding': 'committed suite uses ell=5 cells '
                                    'against k in rad/L-units: over-diffusive '
                                    'by 58.4x; this probe uses ELL_L=SIG*dx '
                                    'in source AND operator',
                    'source': 'S_W = (1-q) ELL_L^2 |grad eps|^2 / rho^2',
                    'wake': 'W* = S_hat * dealias / (1 + ELL_L^2 k^2)',
                    'flux': 'dE_a/dt = -chi_w div(E_a grad W) (committed)',
                    'v_escape_cells_per_t': V_ESCAPE,
                    'bracket_factors': list(BRACKET_FACTORS)}}
    arms = {}

    for tag, sep in [('pair', SEP), ('one_string', 0.0)]:
        solver = build_solver(device)
        ey_hat, ei_hat, _ = P.two_lobe_init(solver, sep)
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        eps = ey - C.PHI * ei
        rho = ey + ei
        S = grad_source(solver, ey, ei)
        W = wake_fixed_point(solver, S, ELL_L)
        W_committed_op = wake_fixed_point(solver, S, P.SIG)  # comparison

        eps_ax = axial(solver, eps)
        rho_ax = axial(solver, rho)
        S_ax = axial(solver, S)
        W_ax = axial(solver, W)
        mid = solver.N // 2

        rec = {
            'S_mid': float(S_ax[mid]), 'W_mid': float(W_ax[mid]),
            'eps_mid': float(eps_ax[mid]), 'rho_mid': float(rho_ax[mid]),
            'S_max': float(S.max()), 'W_max': float(W.max()),
            'W_peak_ratio_S': float(W.max() / S.max()),
            'W_peak_ratio_S_committed_op': float(
                W_committed_op.max() / S.max()),
            'S_profile': S_ax.tolist(), 'W_profile': W_ax.tolist(),
            'eps_profile': eps_ax.tolist(), 'rho_profile': rho_ax.tolist(),
        }

        if sep > 1e-6:
            ridges = ridge_positions(rho_ax)
            if ridges is None:
                print(f"  [{tag}] ridge detection failed; aborting gates")
                continue
            x1, x2 = ridges
            i1, i2 = int(round(x1)), int(round(x2))
            rec['ridges'] = [x1, x2]
            rec['S_at_ridges'] = [float(S_ax[i1]), float(S_ax[i2])]
            rec['W_at_ridges'] = [float(W_ax[i1]), float(W_ax[i2])]
            rec['S_max_loc'] = None
            rec['W_max_loc'] = None
            lo, hi = i1 + 1, i2 - 1
            if hi > lo:
                j = lo + int(np.argmax(S_ax[lo:hi + 1]))
                k = lo + int(np.argmax(W_ax[lo:hi + 1]))
                rec['S_max_loc'] = float(j)
                rec['W_max_loc'] = float(k)
            gw = solver._grad(torch.fft.fftn(W))
            # k-space axis permutation: kz,ky,kx = meshgrid(k_1d,...) with
            # indexing='ij', so kz varies along dim 0 = physical x.  The
            # physical-x gradient is _grad(...)[2]; [0] is the physical-z
            # gradient (identically 0 on this z-symmetric init).
            gx = gw[2]
            rec['dWdx_at_ridges_cells'] = [
                float(gx[i1, solver.N // 2, solver.N // 2] / DX),
                float(gx[i2, solver.N // 2, solver.N // 2] / DX)]
            fd = (W_ax[i1 + 1] - W_ax[i1 - 1]) / 2.0
            rec['dWdx_fd_check_left'] = float(fd)

            # ── G1: midpoint source gate ────────────────────────────────
            xc = 0.5 * (x1 + x2)
            S_mid_ok = rec['S_mid'] > 0.0
            hump_between = (rec['S_max_loc'] is not None and
                            abs(rec['S_max_loc'] - xc) <= 1.0)
            W_peak_mid = (rec['W_max_loc'] is not None and
                          abs(rec['W_max_loc'] - xc) <= 1.0)
            W_above_ridges = (rec['W_mid'] > rec['W_at_ridges'][0] and
                              rec['W_mid'] > rec['W_at_ridges'][1])
            grad_inward = (rec['dWdx_at_ridges_cells'][0] > 0.0 and
                           rec['dWdx_at_ridges_cells'][1] < 0.0)
            g1 = {'S_mid_positive': S_mid_ok,
                  'S_hump_between_ridges': hump_between,
                  'W_peaks_at_midpoint': W_peak_mid,
                  'W_mid_above_ridges': W_above_ridges,
                  'gradW_inward_at_ridges': grad_inward,
                  'passed': (S_mid_ok and hump_between and W_peak_mid and
                             W_above_ridges and grad_inward)}
            rec['G1'] = g1

            # ── G2: no-collapse gate at the calibrated chi* ─────────────
            gw_ridge = max(abs(rec['dWdx_at_ridges_cells'][0]),
                           abs(rec['dWdx_at_ridges_cells'][1]))
            chi_star = (V_ESCAPE / gw_ridge) if gw_ridge > 1e-30 \
                else float('inf')
            rec['chi_star_calibrated'] = chi_star
            bracket = sorted({round(chi_star * f, 1) for f in BRACKET_FACTORS})

            za = max(mid - int(ZONE_HALF), 0)
            zb = min(mid + int(ZONE_HALF) + 1, T.N)
            _, one_minus_q = solver.compute_q_field(ey, ei)
            # Conversion damping of eps carries (1+PHI): d_eps/dt ⊃
            # -lam (1-q) eps (from ey) - PHI*(+lam (1-q) eps) (from ei)
            # = -lam (1-q) (1+PHI) eps.
            lam_conv = T.LAM * (1.0 + C.PHI) * one_minus_q * eps.abs()
            lam_zone = lam_conv[za:zb] + 1e-300
            # The exact node cell has eps == 0 identically (antisymmetric
            # init) and no imbalance to amplify; its R = 0/0 float noise.
            # The amplification zone is the node FLANK (|x-mid| in
            # [1, ZONE_HALF]): mask the node cell and the |eps| < 1e-6
            # cells.
            xidx = torch.arange(za, zb, device=eps.device)
            fm_np = ((np.abs(np.arange(za, zb) - mid) >= 1.0) &
                     (np.abs(eps_ax[za:zb]) >= 1e-6))
            flank_mask = torch.as_tensor(fm_np, device=eps.device)

            g2 = {'zone_half': ZONE_HALF, 'chi_star': chi_star,
                  'bracket': bracket}
            for chi_w in (chi_star, max(bracket)):
                d_rho, d_eps = flux_rates(solver, W, ey, ei, chi_w)
                # 3D masked max over the flank volume
                R_full = (d_eps[za:zb].abs() + 1e-300) / lam_zone
                fm3 = flank_mask.view(-1, 1, 1).expand(zb - za, T.N, T.N)
                R_max = float(R_full[fm3].max())
                # axial lead cell detail (the strongest amplification site
                # on the ridge axis)
                R_ax = (d_eps[:, mid, mid][za:zb].abs() + 1e-300) / \
                    (lam_conv[:, mid, mid][za:zb] + 1e-300)
                R_flank = R_ax[flank_mask]
                j_lead = int(R_flank.argmax())
                x_lead = za + int(torch.nonzero(flank_mask)[j_lead])
                g2_chi = {'R_max_node_flank': R_max,
                          'R_lead_detail': {
                              'x_cell': x_lead,
                              'R_axial': float(R_flank[j_lead]),
                              'd_eps_axial': float(
                                  d_eps[x_lead, mid, mid]),
                              'lam_conv_eps_axial': float(
                                  lam_conv[x_lead, mid, mid])},
                          'v_ridge1_cells_per_t': None,
                          'v_ridge2_cells_per_t': None,
                          'd_dot_cells_per_t': None,
                          'R_lt_1': R_max < 1.0,
                          'contraction': None}
                v1 = ridge_centroid_velocity(solver, d_rho, rho, x1)
                v2 = ridge_centroid_velocity(solver, d_rho, rho, x2)
                d_dot = v2 - v1
                g2_chi['v_ridge1_cells_per_t'] = v1
                g2_chi['v_ridge2_cells_per_t'] = v2
                g2_chi['d_dot_cells_per_t'] = d_dot
                g2_chi['contraction'] = d_dot < 0.0
                g2[f'chi_{chi_w:g}'] = g2_chi
                print(f"  [{tag}] chi={chi_w:8g}: R_max={R_max:.3f}  "
                      f"v1={v1:+.4f} v2={v2:+.4f} cells/t  "
                      f"d_dot={d_dot:+.4f}")
            top = max(bracket)
            g2['passed'] = (g2[f'chi_{chi_star:g}']['R_lt_1'] and
                            g2[f'chi_{chi_star:g}']['contraction'] and
                            g2[f'chi_{top:g}']['R_lt_1'] and
                            g2[f'chi_{top:g}']['contraction'])
            rec['G2'] = g2
        else:
            # ── G3: one-string ──────────────────────────────────────────
            # eps = 0 by construction on sep=0; the doublet reconstruction
            # (ey, ei) from (rho, eps) leaves float-level eps noise
            # (~1e-16 -> S ~ 1e-29).  Tolerance: the committed suite's T3
            # no-op standard (1e-20 field diffs; measured sep0 W_max there
            # ~1e-26, accepted as inert).
            S_max = float(S.max())
            W_max = float(W.max())
            g3 = {'max_S': S_max, 'max_W': W_max,
                  'S_exactly_zero': S_max == 0.0,
                  'W_exactly_zero': W_max == 0.0,
                  'tolerance': 1e-20,
                  'S_within_tol': S_max <= 1e-20,
                  'W_within_tol': W_max <= 1e-20}
            g3['passed'] = (g3['S_within_tol'] and g3['W_within_tol'])
            rec['G3'] = g3

        arms[tag] = rec
        if sep > 1e-6:
            print(f"  [{tag}] ridges=({x1:.2f},{x2:.2f})  "
                  f"S_mid={rec['S_mid']:.4e}  "
                  f"S(ridge)=[{rec['S_at_ridges'][0]:.2e},"
                  f"{rec['S_at_ridges'][1]:.2e}]  "
                  f"W_mid={rec['W_mid']:.4e}  "
                  f"W(ridge)=[{rec['W_at_ridges'][0]:.2e},"
                  f"{rec['W_at_ridges'][1]:.2e}]  "
                  f"S_max_loc={rec['S_max_loc']}  "
                  f"W_max_loc={rec['W_max_loc']}  "
                  f"dWdx(ridge)=[{rec['dWdx_at_ridges_cells'][0]:+.3f},"
                  f"{rec['dWdx_at_ridges_cells'][1]:+.3f}]  "
                  f"W/S={rec['W_peak_ratio_S']:.3f} "
                  f"(committed-op {rec['W_peak_ratio_S_committed_op']:.3f})")
        else:
            print(f"  [{tag}] S_max={rec['S_max']:.3e}  "
                  f"W_max={rec['W_max']:.3e}  "
                  f"S_exactly_zero={rec['G3']['S_exactly_zero']}  "
                  f"W_exactly_zero={rec['G3']['W_exactly_zero']}")

    out['arms'] = arms
    pair = arms.get('pair', {})
    one = arms.get('one_string', {})
    g1_ok = pair.get('G1', {}).get('passed', False)
    g2_ok = pair.get('G2', {}).get('passed', False)
    g3_ok = one.get('G3', {}).get('passed', False)
    gates = {'G1_midpoint_source': g1_ok,
             'G2_no_collapse': g2_ok,
             'G3_one_string': g3_ok,
             'all_passed': g1_ok and g2_ok and g3_ok}
    out['gates'] = gates

    with open(f"{rdir}/probe.json", "w") as f:
        json.dump(out, f, indent=1, default=float)

    print("\n=== STATIC GRAD-SOURCE WAKE PROBE ===")
    print(f"G1 midpoint source: {g1_ok}  "
          f"(S_mid>0: {pair.get('G1', {}).get('S_mid_positive')}, "
          f"S hump between: {pair.get('G1', {}).get('S_hump_between_ridges')}, "
          f"W peaks at mid: {pair.get('G1', {}).get('W_peaks_at_midpoint')}, "
          f"gradW inward: {pair.get('G1', {}).get('gradW_inward_at_ridges')})")
    chi_star = pair.get('G2', {}).get('chi_star', float('nan'))
    print(f"G2 no collapse: {g2_ok}  (chi* calibrated = {chi_star:.1f} "
          f"at {V_ESCAPE} cells/t escape drift; "
          f"bracket {pair.get('G2', {}).get('bracket')})")
    print(f"G3 one-string: {g3_ok}  "
          f"(max|S_W| = {one.get('G3', {}).get('max_S')})")
    print(f"ALL GATES: {'PASSED' if gates['all_passed'] else 'FAILED'}")
    print(f"\nProbe record: {rdir}/probe.json")
    if torch.cuda.is_available():
        torch.cuda.synchronize()   # ROCm teardown deadlocks on async work


if __name__ == "__main__":
    main()
