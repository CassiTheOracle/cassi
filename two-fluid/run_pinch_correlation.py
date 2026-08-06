#!/usr/bin/env python3
"""Pinch-crossing two-point correlation test (consciousness/consciousness-from-phi.md §2.1).

Claim under test: the Qi-gate pinch at r = EY/EI = φ⁻¹ ≈ 0.618 is the threshold
where a field becomes self-referential. Testable prediction (documented in the
paper as never-run): start a PDE field sub-pinch, evolve it through the pinch,
and measure the radial two-point autocorrelation of the ratio field
r(x) = EY(x)/EI(x). Before the pinch it should be random or scale-free; after
crossing it should develop peaks at φ-scaled separations.

Runs (fresh ExpandingTwoFluid3DGPU per run, qi_gate=True, seed=42):
  A: r0 = 0.50 (sub-pinch) — crosses the pinch at measured t_c, then runs to
     t_c + 56 (just over one conversion timescale 1/λ = 50 after crossing).
  B: r0 = 0.75 (above pinch) — counterfactual, same duration, no crossing.

Epochs (absolute-time windows, shared between A and B):
  pre/early : t in [t_cA − 2.0, t_cA − 0.4]   (5 snapshots, 0.4 apart)
  post/late : t in [t_cA + 50, t_cA + 51.6]   (5 snapshots, 0.4 apart)

Observable: C(d) = <f(x) f(x+d)>/<f²>, f = r/<r> − 1, radially shell-averaged
over the periodic box (FFT autocorrelation), d in cells. φ-separations
d_k = round((N/4)·φ^k), k = −2..2 → {5,7,12,19,31}; controls at the decade
midpoints round((N/4)·φ^(k+1/2)) → {6,9,15,25,40}.

Statistics per snapshot:
  Δ_res = mean ε(d_φ) − mean ε(d_ctl), ε = detrended C(d) (poly-3 in ln d,
  fit over d ≥ 3) — removes the monotone-decay confound.
  Log-periodic scan (house method, fixed ω₀ = 2π/ln φ): residual power at
  T = ln φ, dAIC vs smooth-only, ω-specificity percentile p_spec.

Verdict: SUPPORTED if (a) post Δ_res > 0 with bootstrap 95% CI excluding 0,
(b) pre epoch shows no such preference, (c) counterfactual B-late shows no
such development. AMBIGUOUS if the structure develops without the crossing
contrast; NULL otherwise.

Usage:
  python run_pinch_correlation.py --run A                     # crossing run
  python run_pinch_correlation.py --run B --steps N --out DIR # counterfactual
  python run_pinch_correlation.py --analyze DIR               # stats + figure + verdict
  (--resume DIR restarts an interrupted --run; checkpoints every 4000 steps)
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime

import numpy as np

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------
N = 48
L = 2.0 * np.pi
DT = 0.002
LAM = 0.02
D = 0.0001
NU = 0.0005
CHI = 0.0
SEED = 42
AMPLITUDE = 0.05
N_MAX_STEPS = 40000          # t = 80 — ample for crossing (~t 9–13) + post window
POST_UNITS = 56.0            # stop at t_c + 56 (> 1/λ = 50)
MONITOR_EVERY = 25           # steps between r_mean / clamp checks
SNAPSHOT_EVERY = 200         # steps between C(d) snapshots (t spacing 0.4)
CKPT_EVERY = 4000            # steps between checkpoints
PHI_INV_TOL = 0.0            # crossing: first monitor time with r_mean >= φ⁻¹

# φ-scaled separations relative to the box quarter-scale d0 = N/4 = 12
D0 = N // 4
PHI_SEPS = sorted({int(np.round(D0 * PHI**k)) for k in range(-2, 3)})
CTL_SEPS = sorted({int(np.round(D0 * PHI**(k + 0.5))) for k in range(-2, 3)})
D_MAX = int(np.sqrt(3.0) * (N // 2)) + 1      # 42 → d = 1..41
D_VALS = np.arange(1, D_MAX, dtype=float)     # shell centres

LN_PHI = np.log(PHI)
OMEGA0 = 2.0 * np.pi / LN_PHI                 # ~13.06, fixed zero-parameter period


# ---------------------------------------------------------------------------
# Observable
# ---------------------------------------------------------------------------
def ratio_field(ey, ei):
    return ey / ei


def radial_autocorr(f):
    """Normalized circular radial autocorrelation of f (3D tensor).

    C(d) = <f(x) f(x+d)> / <f²> averaged over lattice vectors |d| in
    [d−0.5, d+0.5). Returns array indexed d = 1..41.
    """
    F = torch.fft.fftn(f)
    c = torch.fft.ifftn(F * F.conj()).real
    c0 = float(c[0, 0, 0].item())
    cn = c.cpu().numpy()
    i = np.arange(N)
    di = np.minimum(i, N - i)
    DX, DY, DZ = np.meshgrid(di, di, di, indexing="ij")
    Dm = np.sqrt(DX**2 + DY**2 + DZ**2)
    edges = np.arange(0.5, D_MAX + 0.5)
    counts, _ = np.histogram(Dm.ravel(), bins=edges)
    sums, _ = np.histogram(Dm.ravel(), bins=edges, weights=cn.ravel())
    C = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    return C / c0


def radial_autocorr_masked(f, mask):
    """Masked radial autocorrelation: pairs with a floored cell excluded.

    C(v) = Σ_x f(x)f(x+v) / Σ_x m(x)m(x+v), normalized by C(0). Both sums via
    FFT; mask m ∈ {0,1} marks valid cells.
    """
    F = torch.fft.fftn(f)
    M = torch.fft.fftn(mask)
    num = torch.fft.ifftn(F * F.conj()).real
    den = torch.fft.ifftn(M * M.conj()).real
    num_np = num.cpu().numpy()
    den_np = den.cpu().numpy()
    i = np.arange(N)
    di = np.minimum(i, N - i)
    DX, DY, DZ = np.meshgrid(di, di, di, indexing="ij")
    Dm = np.sqrt(DX**2 + DY**2 + DZ**2)
    edges = np.arange(0.5, D_MAX + 0.5)
    counts, _ = np.histogram(Dm.ravel(), bins=edges)
    s_num, _ = np.histogram(Dm.ravel(), bins=edges, weights=num_np.ravel())
    s_den, _ = np.histogram(Dm.ravel(), bins=edges, weights=den_np.ravel())
    with np.errstate(divide="ignore", invalid="ignore"):
        C = np.divide(s_num, s_den, out=np.zeros_like(s_num), where=s_den > 0)
    c0 = (num_np[0, 0, 0] / den_np[0, 0, 0]) if den_np[0, 0, 0] > 0 else 1.0
    return C / c0


def smooth_gaussian(f, sigma):
    """Fourier Gaussian smoothing (wrap-around, exact periodicity)."""
    k2 = solver_k2(f.device)
    kernel = torch.exp(-0.5 * (sigma ** 2) * k2)
    F = torch.fft.fftn(f)
    return torch.fft.ifftn(F * kernel).real


_K2_CACHE = {}


def solver_k2(device):
    """Cached |k|² for the current N on the given device."""
    key = (N, str(device))
    if key not in _K2_CACHE:
        k1 = 2.0 * np.pi * torch.fft.fftfreq(N, d=L / N, device=device)
        kz, ky, kx = torch.meshgrid(k1, k1, k1, indexing="ij")
        _K2_CACHE[key] = kx ** 2 + ky ** 2 + kz ** 2
    return _K2_CACHE[key]


def snapshot_metrics(solver, u_hat, ey_hat, ei_hat):
    """All observables for the current field state.

    g = clip(ln r, ±6); floored cells (ey or ei < 0.01) are NaN in g_masked.
    Observables (radial C(d)):
      C_raw  — raw g (clamp artifacts included; reference only)
      C_mask — masked g (primary: clamp cells excluded)
      C_s2, C_s4 — masked g, Gaussian-smoothed σ=2/4 cells (wake-scale probe)
    Also stores the physical mean ratio r_bar = <ey>/<ei>, u_max, floor counts.
    """
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    r = ratio_field(ey, ei)
    g = torch.clamp(torch.log(r), -6.0, 6.0)
    floor_mask = ((ey >= 0.01) & (ei >= 0.01)).to(torch.float64)
    g_masked = g * floor_mask          # floored cells contribute 0 to sums
    g_bar = g_masked.sum() / (floor_mask.sum() + 1e-30)
    g_c = g - g.mean()

    C_raw = radial_autocorr(g_c)
    C_mask = radial_autocorr_masked((g - g_bar) * floor_mask, floor_mask)
    # Normalized convolution: smoothed masked field / smoothed mask.
    for sig in (2.0, 4.0):
        g_s = smooth_gaussian(g_masked, sig) / (smooth_gaussian(floor_mask, sig) + 1e-30)
        if sig == 2.0:
            C_s2 = radial_autocorr(g_s - g_s.mean())
        else:
            C_s4 = radial_autocorr(g_s - g_s.mean())

    u = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
    u_max = max(float(u[d].abs().max().item()) for d in range(3))
    k, Pk = solver.power_spectrum(g_c)
    return {
        "C_raw": C_raw.tolist(),
        "C_mask": C_mask.tolist(),
        "C_s2": C_s2.tolist(),
        "C_s4": C_s4.tolist(),
        "k": k.tolist(),
        "Pk": Pk.tolist(),
        "r_bar": float((ey.mean() / ei.mean()).item()),
        "r_cells": float(r.mean().item()),
        "delta_rms": float(g.std().item()),
        "u_max": u_max,
        "n_floor_ey": int((ey < 0.01).sum().item()),
        "n_floor_ei": int((ei < 0.01).sum().item()),
    }


# ---------------------------------------------------------------------------
# Detrending and φ-statistics
# ---------------------------------------------------------------------------
def detrend(C, order=3, d_min=3):
    """Remove the smooth baseline (poly in ln d) from C(d), d >= d_min.

    Returns (d_fit, epsilon) where epsilon = C − baseline. The central peak
    (d < d_min) is excluded from the fit and from the residual scan.
    """
    mask = D_VALS >= d_min
    d_fit = D_VALS[mask]
    C_fit = C[mask]
    x = np.log(d_fit)
    coeffs = np.polyfit(x, C_fit, order)
    baseline = np.polyval(coeffs, x)
    return d_fit, C_fit - baseline


def phi_ctl_stats(d_fit, eps, phi_seps=None, ctl_seps=None):
    """Mean residual at φ-separations minus mean at control separations."""
    if phi_seps is None:
        phi_seps = [s for s in PHI_SEPS if d_fit.min() <= s <= d_fit.max()]
    if ctl_seps is None:
        ctl_seps = [s for s in CTL_SEPS if d_fit.min() <= s <= d_fit.max()]
    in_phi = np.isin(d_fit, phi_seps)
    in_ctl = np.isin(d_fit, ctl_seps)
    phi_m = float(eps[in_phi].mean()) if in_phi.any() else np.nan
    ctl_m = float(eps[in_ctl].mean()) if in_ctl.any() else np.nan
    return phi_m, ctl_m, phi_m - ctl_m


def logperiodic_scan(d_fit, eps, periods=None):
    """House φ-periodicity test: smooth-subtract, cos/sin least squares at
    fixed periods, no phase search. Returns power(T) over the grid plus the
    ω-specificity of T = ln φ."""
    x = np.log(d_fit)
    xc = x - x.mean()
    if periods is None:
        periods = np.linspace(0.30, 0.90, 400)
    powers = np.zeros(len(periods))
    rss0 = float(np.sum(eps**2))
    n = len(eps)
    for i, T in enumerate(periods):
        s = np.sin(2 * np.pi * xc / T)
        co = np.cos(2 * np.pi * xc / T)
        A = np.sum(eps * s) / np.sum(s**2)
        B = np.sum(eps * co) / np.sum(co**2)
        powers[i] = A**2 + B**2
        if abs(T - LN_PHI) < 0.03:
            resid_osc = eps - A * s - B * co
            rss_osc = float(np.sum(resid_osc**2))
            # dAIC = AIC(osc) − AIC(smooth): 2 extra params for the oscillation
            dAIC = n * np.log(rss_osc / max(rss0, 1e-30)) + 4.0
    p_phi = powers[np.argmin(np.abs(periods - LN_PHI))]
    excl = np.abs(periods - LN_PHI) >= 0.03
    p_spec = float(np.mean(powers[excl] <= p_phi)) if excl.any() else np.nan
    best_i = int(np.argmax(powers))
    return {
        "periods": periods.tolist(),
        "powers": powers.tolist(),
        "best_T": float(periods[best_i]),
        "best_power": float(powers[best_i]),
        "power_at_ln_phi": float(p_phi),
        "dAIC": float(dAIC),
        "p_spec": p_spec,
    }


def bootstrap_delta_res(d_fit, eps_list, phi_seps=None, ctl_seps=None,
                        n_boot=2000, seed=42):
    """Bootstrap distribution of Δ_res over the epoch's snapshots."""
    rng = np.random.default_rng(seed)
    vals = np.array([phi_ctl_stats(d_fit, e, phi_seps, ctl_seps)[2]
                     for e in eps_list])
    m = len(vals)
    boot = np.array([vals[rng.integers(0, m, size=m)].mean() for _ in range(n_boot)])
    return {
        "mean": float(vals.mean()),
        "std": float(vals.std(ddof=1)) if m > 1 else 0.0,
        "boot_mean": float(boot.mean()),
        "boot_std": float(boot.std()),
        "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
        "z": float(boot.mean() / max(boot.std(), 1e-12)),
    }


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------
def build_solver():
    return ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=NU, D=D, lam=LAM, chi=CHI,
        hubble_mode="conversion", cs2=0.0, qi_gate=True, qi_memory=False,
        mode="cosmos")


def save_meta(out_dir, meta):
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


def evolve(run_label, out_dir, r0, n_steps, resume=False):
    """Run one fresh solver evolution, writing snapshots + checkpoints."""
    os.makedirs(out_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[{run_label}] device={device} r0(EY/EI)={r0:.3f} "
          f"steps={n_steps} dt={DT} seed={SEED}", flush=True)

    meta = {
        "run": run_label, "r0": r0, "N": N, "dt": DT, "lam": LAM, "D": D,
        "nu": NU, "chi": CHI, "seed": SEED, "amplitude": AMPLITUDE,
        "qi_gate": True, "gate_model": "single", "hubble_mode": "conversion",
        "n_steps_target": n_steps, "t_c": None, "crossed": False,
        "n_steps_done": 0,
    }
    ckpt_path = os.path.join(out_dir, "checkpoint_last.pt")
    snap_path = os.path.join(out_dir, "snapshots.json")

    solver = build_solver()
    if resume and os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, weights_only=False)
        step0 = ckpt["step"] + 1
        u_hat = ckpt["u_hat"]
        ey_hat = ckpt["ey_hat"]
        ei_hat = ckpt["ei_hat"]
        solver.a = ckpt["a"]
        solver._H_smooth = ckpt["H_smooth"]
        solver.H = ckpt["H_smooth"]
        meta["t_c"] = ckpt["t_c"]
        meta["crossed"] = ckpt["crossed"]
        with open(snap_path) as f:
            snapshots = json.load(f)
        print(f"[{run_label}] resumed at step {step0} (t_c={meta['t_c']})",
              flush=True)
    else:
        step0 = 0
        solver.initial_ratio = 1.0 / r0          # solver takes <EI>/<EY>
        u_hat, ey_hat, ei_hat = solver.initial_expanding(
            amplitude=AMPLITUDE, seed=SEED)
        snapshots = []

    save_meta(out_dir, meta)
    crossed = meta["crossed"]
    t_c = meta["t_c"]
    was_below = None   # first monitor sets: initial r_mean below the pinch?

    t_start = time.time()
    last_report = 0.0
    for step in range(step0, n_steps + 1):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt=DT)
        t = step * DT

        if step % MONITOR_EVERY == 0:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            r_mean = float((ey.mean() / ei.mean()).item())
            ey_min = float(ey.min().item())
            ei_min = float(ei.min().item())
            if was_below is None:
                was_below = r_mean < PHI_INV - 1e-3
            # "Crossing" = the field passed the pinch from below. Run B
            # (r0 above the pinch) never triggers it and runs its full budget.
            if not crossed and was_below and r_mean >= PHI_INV - PHI_INV_TOL:
                crossed = True
                t_c = t
                meta["t_c"] = t_c
                meta["crossed"] = True
                save_meta(out_dir, meta)
                print(f"[{run_label}] *** PINCH CROSSING at t = {t_c:.3f} "
                      f"(r_mean = {r_mean:.4f}) ***", flush=True)
            if t - last_report >= 2.0:
                print(f"[{run_label}] t={t:6.2f} r_mean={r_mean:.4f} "
                      f"a={float(solver.a):.3f} H={float(solver.H):.4f} "
                      f"ey_min={ey_min:.3f} ei_min={ei_min:.3f} "
                      f"q={float(solver.q_mean):.3f}", flush=True)
                last_report = t
            meta["ey_min_last"] = ey_min
            meta["ei_min_last"] = ei_min
            meta["n_steps_done"] = step

        if step % SNAPSHOT_EVERY == 0:
            s = snapshot_metrics(solver, u_hat, ey_hat, ei_hat)
            s["step"] = step
            s["t"] = t
            s["a"] = float(solver.a.item())
            s["H"] = float(solver.H.item())
            snapshots.append(s)

        if step % CKPT_EVERY == 0 and step > 0:
            torch.save({
                "step": step, "u_hat": u_hat, "ey_hat": ey_hat, "ei_hat": ei_hat,
                "a": solver.a, "H_smooth": solver._H_smooth,
                "t_c": t_c, "crossed": crossed,
            }, ckpt_path)
            with open(snap_path, "w") as f:
                json.dump(snapshots, f)
            save_meta(out_dir, meta)

        if crossed and t >= t_c + POST_UNITS:
            print(f"[{run_label}] finished at t = {t:.2f} "
                  f"(t_c + {t - t_c:.1f} units)", flush=True)
            break

    if not crossed and r0 < PHI_INV:
        print(f"[{run_label}] WARNING: no pinch crossing by t = {n_steps * DT:.1f}",
              flush=True)

    meta["n_steps_done"] = step
    meta["t_final"] = step * DT
    meta["elapsed_s"] = time.time() - t_start
    save_meta(out_dir, meta)
    with open(snap_path, "w") as f:
        json.dump(snapshots, f)
    torch.save({
        "step": step, "u_hat": u_hat, "ey_hat": ey_hat, "ei_hat": ei_hat,
        "a": solver.a, "H_smooth": solver._H_smooth,
        "t_c": t_c, "crossed": crossed,
    }, ckpt_path)
    print(f"[{run_label}] done: {step} steps in {meta['elapsed_s']:.1f}s",
          flush=True)
    return meta


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def select_epoch(snapshots, t_c, phase, n_max=5, margin=0.1):
    """Phase 'pre'/'early': last n_max snapshots strictly before t_c − margin.
    Phase 'post'/'late': first n_max snapshots at or after t_c + 50.
    Spacing-independent (snapshot cadence may vary with dt)."""
    if phase in ("pre", "early"):
        picked = [s for s in snapshots if s["t"] <= t_c - margin]
        return picked[-n_max:]
    picked = [s for s in snapshots if s["t"] >= t_c + 50.0]
    return picked[:n_max]


def analyze(run_dir):
    """Merge runs A + B, compute epoch statistics, figure, verdict."""
    a_dir = os.path.join(run_dir, "A")
    b_dir = os.path.join(run_dir, "B")
    with open(os.path.join(a_dir, "meta.json")) as f:
        metaA = json.load(f)
    with open(os.path.join(b_dir, "meta.json")) as f:
        metaB = json.load(f)
    with open(os.path.join(a_dir, "snapshots.json")) as f:
        snapsA = json.load(f)
    with open(os.path.join(b_dir, "snapshots.json")) as f:
        snapsB = json.load(f)

    # Rebuild N-dependent globals from the run's own grid (analyze may be
    # invoked without --N; smoke tests run at reduced resolution).
    global N, DT, D0, PHI_SEPS, CTL_SEPS, D_MAX, D_VALS
    N = metaA["N"]
    D0 = N // 4
    PHI_SEPS = sorted({int(np.round(D0 * PHI**k)) for k in range(-2, 3)})
    CTL_SEPS = sorted({int(np.round(D0 * PHI**(k + 0.5))) for k in range(-2, 3)})
    D_MAX = int(np.sqrt(3.0) * (N // 2)) + 1
    D_VALS = np.arange(1, D_MAX, dtype=float)

    t_c = metaA["t_c"]
    if t_c is None:
        print("FAILED: run A never crossed the pinch — no epochs defined.")
        return None

    pre = select_epoch(snapsA, t_c, "pre")
    post = select_epoch(snapsA, t_c, "post")
    early = select_epoch(snapsB, t_c, "early")
    late = select_epoch(snapsB, t_c, "late")
    # Supplementary windows (transient check): first 5 snapshots after
    # t_c + 10 and t_c + 25 (well before the mandated t_c + 50 epoch).
    mid10 = [s for s in snapsA if s["t"] >= t_c + 10.0][:5]
    mid25 = [s for s in snapsA if s["t"] >= t_c + 25.0][:5]
    if len(pre) < 3 or len(post) < 3 or len(early) < 3 or len(late) < 3:
        print(f"FAILED: epochs too thin (pre={len(pre)} post={len(post)} "
              f"early={len(early)} late={len(late)}); run more steps.")
        return None

    def epoch_curves(epoch, key="C_mask"):
        return np.array([np.array(s[key]) for s in epoch])

    def epoch_residuals(epoch, key="C_mask"):
        return [detrend(c)[1] for c in epoch_curves(epoch, key)]

    d_fit = detrend(epoch_curves(pre)[0])[0]
    OBS = ["C_mask", "C_s2", "C_s4", "C_raw"]
    res = {}
    for name, epoch in [("pre", pre), ("mid10", mid10), ("mid25", mid25),
                        ("post", post), ("early", early), ("late", late)]:
        entry = {
            "n_snaps": len(epoch),
            "t_range": [epoch[0]["t"], epoch[-1]["t"]],
            "r_bar_range": [epoch[0]["r_bar"], epoch[-1]["r_bar"]],
            "u_max_range": [epoch[0]["u_max"], epoch[-1]["u_max"]],
            "n_floor_ey": [s["n_floor_ey"] for s in epoch],
            "n_floor_ei": [s["n_floor_ei"] for s in epoch],
        }
        for obs in OBS:
            Cs = epoch_curves(epoch, obs)
            eps_list = epoch_residuals(epoch, obs)
            phi_m, ctl_m, _ = phi_ctl_stats(d_fit, np.mean(eps_list, axis=0))
            lp = logperiodic_scan(d_fit, np.mean(eps_list, axis=0))
            entry[f"{obs}_C_mean"] = np.mean(Cs, axis=0).tolist()
            entry[f"{obs}_eps_mean"] = np.mean(eps_list, axis=0).tolist()
            entry[f"{obs}_delta_res"] = bootstrap_delta_res(d_fit, eps_list)
            entry[f"{obs}_phi_sep_mean"] = float(phi_m)
            entry[f"{obs}_ctl_sep_mean"] = float(ctl_m)
            entry[f"{obs}_logperiodic"] = lp
        dR = entry["C_mask_delta_res"]
        print(f"  {name:5s}: t∈[{epoch[0]['t']:.1f},{epoch[-1]['t']:.1f}] "
              f"r̄∈[{epoch[0]['r_bar']:.3f},{epoch[-1]['r_bar']:.3f}] "
              f"Δ_res(mask)={dR['mean']:+.5f} "
              f"[{dR['ci95'][0]:+.5f},{dR['ci95'][1]:+.5f}] "
              f"Δ_res(s2)={entry['C_s2_delta_res']['mean']:+.5f} "
              f"dAIC={entry['C_mask_logperiodic']['dAIC']:+.1f} "
              f"floored={np.mean(entry['n_floor_ey']):.0f}+"
              f"{np.mean(entry['n_floor_ei']):.0f}/snap")
        res[name] = entry

    # Peak identification in the post epoch (primary observable)
    C_post = np.mean(epoch_curves(post, "C_mask"), axis=0)
    C_pre = np.mean(epoch_curves(pre, "C_mask"), axis=0)
    C_pre_std = np.std(epoch_curves(pre, "C_mask"), axis=0, ddof=1) + 1e-12
    smooth = np.convolve(C_post, np.ones(3) / 3, mode="same")
    peaks = []
    for d in range(3, len(smooth) - 1):
        if smooth[d] > smooth[d - 1] and smooth[d] >= smooth[d + 1]:
            dsep = min(abs(d + 1 - s) for s in PHI_SEPS)
            peaks.append({
                "d": float(d + 1), "C": float(smooth[d]),
                "dist_to_phi_sep": float(dsep),
                "z_vs_pre": float((C_post[d] - C_pre[d]) / C_pre_std[d]),
            })
    peaks.sort(key=lambda p: -p["C"])
    res["post_peaks"] = peaks[:8]

    # Verdict (primary observable: masked log-ratio field)
    def verdict_for(obs):
        dA = res["post"][f"{obs}_delta_res"]
        dB = res["late"][f"{obs}_delta_res"]
        dPre = res["pre"][f"{obs}_delta_res"]
        cond = {
            "post φ-preference (Δ_res > 0, CI excludes 0)":
                dA["mean"] > 0 and dA["ci95"][0] > 0,
            "pre epoch no φ-preference (CI contains 0)":
                dPre["ci95"][0] < 0 < dPre["ci95"][1],
            "counterfactual contrast (B-late Δ_res ≤ A-post, CI not > 0)":
                dB["ci95"][1] <= 0 or dB["ci95"][1] < dA["ci95"][0],
        }
        n_pass = sum(cond.values())
        if n_pass == 3:
            label = "SUPPORTED"
        elif n_pass >= 1 and dA["mean"] > 0:
            label = "AMBIGUOUS"
        else:
            label = "NULL"
        return {"label": label, "conditions": cond, "n_pass": n_pass}

    verdict = verdict_for("C_mask")
    verdict["cross_checks"] = {
        obs: verdict_for(obs)["label"] for obs in OBS
    }
    res["verdict"] = verdict

    print("\n  Verdict conditions (primary: masked log-ratio):")
    for k, v in verdict["conditions"].items():
        print(f"    [{'x' if v else ' '}] {k}")
    print(f"  VERDICT: {verdict['label']}")
    print(f"  Cross-check by observable: "
          + ", ".join(f"{o}={l}" for o, l in verdict["cross_checks"].items()))

    results = {
        "claim": "consciousness/consciousness-from-phi.md §2.1 — pinch-point "
                 "two-point correlation test (never-run; this is the first run)",
        "params": {k: metaA[k] for k in
                   ["N", "dt", "lam", "D", "nu", "chi", "seed", "amplitude",
                    "qi_gate", "gate_model", "hubble_mode"]},
        "conventions": {
            "ratio": "r(x) = EY(x)/EI(x); pinch at r = φ⁻¹ ≈ 0.618",
            "d0": "N/4 = 12 cells (box quarter-scale)",
            "phi_separations": PHI_SEPS,
            "control_separations": CTL_SEPS,
            "observable_primary": "C(d) of g = clip(ln r, ±6), cells floored "
                                  "at the solver clamp (ey or ei < 0.01) "
                                  "excluded (masked autocorrelation)",
            "observable_probes": "C(d) of masked g smoothed with σ = 2 and "
                                 "4 cells (wake-scale probe); C_raw includes "
                                 "clamp cells (reference only)",
            "post_epoch_offset_units": "t_c + 50..52 (1/λ = 50); mid10/mid25 "
                                       "supplementary transient windows",
        },
        "run_A": {"r0": metaA["r0"], "t_c": t_c,
                  "n_steps": metaA["n_steps_done"],
                  "t_final": metaA["t_final"],
                  "crossed": metaA["crossed"],
                  "elapsed_s": metaA["elapsed_s"],
                  "ey_min_last": metaA.get("ey_min_last"),
                  "ei_min_last": metaA.get("ei_min_last")},
        "run_B": {"r0": metaB["r0"], "t_c": None, "crossed": False,
                  "n_steps": metaB["n_steps_done"],
                  "t_final": metaB["t_final"],
                  "elapsed_s": metaB["elapsed_s"],
                  "ey_min_last": metaB.get("ey_min_last"),
                  "ei_min_last": metaB.get("ei_min_last")},
        "epochs": {k: {kk: vv for kk, vv in v.items()
                       if not kk.endswith("_C_mean") and not kk.endswith("_eps_mean")}
                   for k, v in res.items() if k in
                   ("pre", "mid10", "mid25", "post", "early", "late")},
        "post_peaks": res["post_peaks"],
        "verdict": res["verdict"],
        "curves": {
            k: {"d": D_VALS.tolist(), "d_fit": d_fit.tolist(),
                **{f"{o}_C": res[k][f"{o}_C_mean"] for o in OBS},
                **{f"{o}_eps": res[k][f"{o}_eps_mean"] for o in OBS}}
            for k in ("pre", "mid10", "mid25", "post", "early", "late")
        },
    }
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {os.path.join(run_dir, 'results.json')}")
    return results


def make_figure(run_dir, results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t_c = results["run_A"]["t_c"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))

    # Panel 1: r̄(t) ratio-of-means for both runs
    ax = axes[0, 0]
    for label, sub in [("A (r0=0.50, crossing)", "A"), ("B (r0=0.75, no crossing)", "B")]:
        with open(os.path.join(run_dir, sub, "snapshots.json")) as f:
            snaps = json.load(f)
        ax.plot([s["t"] for s in snaps], [s["r_bar"] for s in snaps],
                label=label, lw=1.5)
    ax.axhline(PHI_INV, color="k", ls="--", lw=1, label="pinch r = φ⁻¹")
    ax.axvline(t_c, color="C0", ls=":", lw=1)
    ax.axvspan(t_c - 2.0, t_c - 0.4, color="C0", alpha=0.08)
    ax.axvspan(t_c + 50.0, t_c + 51.6, color="C0", alpha=0.08)
    ax.set_xlabel("t"); ax.set_ylabel("r̄ = ⟨EY⟩/⟨EI⟩")
    ax.set_title("Mean ratio evolution (epochs shaded)")
    ax.legend(fontsize=7); ax.grid(alpha=0.3)

    # Panels 2–5: C(d) masked (primary) and smoothed σ=2 probe, A and B
    pairs = [("pre", "post", "Run A: sub-pinch → crossing"),
             ("early", "late", "Run B: above pinch, no crossing")]
    for col, (epoch_pre, epoch_post, title) in enumerate(pairs, start=1):
        cur_pre = results["curves"][epoch_pre]
        cur_post = results["curves"][epoch_post]
        ax = axes[0, col]
        ax.plot(cur_pre["d"], cur_pre["C_mask_C"], "-o", ms=3, label=epoch_pre)
        ax.plot(cur_post["d"], cur_post["C_mask_C"], "-o", ms=3, label=epoch_post)
        for s in PHI_SEPS:
            ax.axvline(s, color="tab:green", ls="-", lw=0.8, alpha=0.6)
        for s in CTL_SEPS:
            ax.axvline(s, color="tab:red", ls="--", lw=0.8, alpha=0.6)
        ax.set_xlabel("d (cells)"); ax.set_ylabel("C(d)")
        ax.set_title(f"{title}: C(d), masked ln r")
        ax.legend(fontsize=7); ax.grid(alpha=0.3)

        ax = axes[1, col - 1]
        ax.plot(cur_pre["d_fit"], cur_pre["C_s2_eps"], "-o", ms=3, label=epoch_pre)
        ax.plot(cur_post["d_fit"], cur_post["C_s2_eps"], "-o", ms=3, label=epoch_post)
        ax.axhline(0, color="k", lw=0.6)
        for s in PHI_SEPS:
            ax.axvline(s, color="tab:green", ls="-", lw=0.8, alpha=0.6)
        for s in CTL_SEPS:
            ax.axvline(s, color="tab:red", ls="--", lw=0.8, alpha=0.6)
        ax.set_xlabel("d (cells)"); ax.set_ylabel("ε(d) = C − baseline")
        ax.set_title(f"{title}: detrended residual, σ=2 probe")
        ax.legend(fontsize=7); ax.grid(alpha=0.3)

    # Panel 6: Δ_res bootstrap bars (primary + σ=2 probe)
    ax = axes[1, 2]
    names = ["A pre", "A post", "B early", "B late"]
    width = 0.35
    for j, obs, lab in [(0, "C_mask", "masked"), (1, "C_s2", "σ=2")]:
        means = [results["epochs"][n][f"{obs}_delta_res"]["mean"] for n in
                 ("pre", "post", "early", "late")]
        cis = [results["epochs"][n][f"{obs}_delta_res"]["ci95"] for n in
               ("pre", "post", "early", "late")]
        errs = [[m - lo, hi - m] for m, (lo, hi) in zip(means, cis)]
        ax.bar(np.arange(4) + (j - 0.5) * width, means, width=width,
               yerr=np.array(errs).T, color=["C3", "C0"][j], alpha=0.75,
               capsize=3, label=lab)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(4)); ax.set_xticklabels(names)
    ax.set_ylabel("Δ_res = ε̄(φ-seps) − ε̄(ctl-seps)")
    ax.set_title(f"φ-preference (95% CI) — verdict: {results['verdict']['label']}")
    ax.legend(fontsize=7); ax.grid(alpha=0.3)

    fig.suptitle(f"Pinch-crossing two-point correlation — "
                 f"t_c = {t_c:.2f}, N={results['params']['N']}",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(run_dir, "pinch_correlation.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"Figure written to {out}")


# ---------------------------------------------------------------------------
# Self-test: planted-signal and null calibration of the statistics
# ---------------------------------------------------------------------------
def self_test():
    """Verify Δ_res and the log-periodic scan fire on a planted φ signal and
    stay quiet on a null — house calibration habit."""
    rng = np.random.default_rng(7)
    d = D_VALS                       # full-length; detrend masks d >= 3 internally
    x = np.log(d)
    null_ok = True
    sig_ok = True
    for _ in range(50):
        # null: smooth decay + noise
        C = np.exp(-d / 12.0) * (1 + 0.03 * rng.standard_normal(len(d)))
        df, eps = detrend(C)
        pm, cm, dres = phi_ctl_stats(df, eps)
        if not (abs(dres) < 1.5 * 0.02):
            null_ok = False
        # planted: φ-log-periodic wiggle at 3% of amplitude
        C2 = np.exp(-d / 12.0) * (1 + 0.03 * np.cos(OMEGA0 * x))
        df, eps2 = detrend(C2)
        pm, cm, dres2 = phi_ctl_stats(df, eps2)
        if not (dres2 > 2e-3):
            sig_ok = False
    df, eps3 = detrend(np.exp(-d / 12.0) * (1 + 0.05 * np.cos(OMEGA0 * x)))
    lp = logperiodic_scan(df, eps3)
    # p_spec is underpowered here by construction: with ~2.6 φ-periods of
    # dynamic range (d = 3..41) the spectral peak is ~0.38 wide in relative
    # period, so neighbouring frequencies fit almost as well (p_spec ~ 1 even
    # for a true signal). The honest gates are Δ_res (zero-parameter φ vs √φ
    # midpoint positions) and the fixed-frequency dAIC at ω₀ = 2π/ln φ.
    sig_spec = lp["dAIC"] < -2
    print(f"[self-test] null stays quiet: {null_ok} | "
          f"planted φ-signal detected: {sig_ok} | "
          f"fixed-ω dAIC={lp['dAIC']:.1f} (p_spec={lp['p_spec']:.3f}, "
          f"broad-peak caveat): {sig_spec}")
    return null_ok and sig_ok and sig_spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", choices=["A", "B"])
    ap.add_argument("--steps", type=int, default=N_MAX_STEPS)
    ap.add_argument("--out", default=None, help="run directory (A or B)")
    ap.add_argument("--resume", default=None, help="run directory to resume")
    ap.add_argument("--analyze", default=None, help="run directory to analyze")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--N", type=int, default=48, help="grid size (smoke tests)")
    ap.add_argument("--dt", type=float, default=0.002, help="time step")
    args = ap.parse_args()

    if args.N != 48 or args.dt != 0.002:
        global N, DT, D0, PHI_SEPS, CTL_SEPS, D_MAX, D_VALS
        N, DT = args.N, args.dt
        D0 = N // 4
        PHI_SEPS = sorted({int(np.round(D0 * PHI**k)) for k in range(-2, 3)})
        CTL_SEPS = sorted({int(np.round(D0 * PHI**(k + 0.5))) for k in range(-2, 3)})
        D_MAX = int(np.sqrt(3.0) * (N // 2)) + 1
        D_VALS = np.arange(1, D_MAX, dtype=float)
        print(f"[main] override N={N} dt={DT} (d0={D0}, "
              f"φ-seps={PHI_SEPS}, ctl-seps={CTL_SEPS})")

    if args.self_test:
        ok = self_test()
        sys.exit(0 if ok else 1)

    if args.analyze:
        res = analyze(args.analyze)
        if res is None:
            sys.exit(1)
        make_figure(args.analyze, res)
        return

    if args.run is None:
        ap.error("specify --run A, --run B, --analyze DIR, or --self-test")

    if args.run == "A":
        if args.out is not None:
            run_dir = args.out
        else:
            rid = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = os.path.join("runs", f"{rid}_pinch_correlation")
        os.makedirs(run_dir, exist_ok=True)
        evolve("A", os.path.join(run_dir, "A"), r0=0.50,
               n_steps=args.steps, resume=args.resume is not None)
        print(f"\nRun directory: {run_dir}")
        print(f"Next: python run_pinch_correlation.py --run B --steps "
              f"<steps_A> --out {run_dir}")
    else:  # B
        if args.out is None:
            ap.error("--run B requires --out <run directory from run A>")
        run_dir = args.out
        os.makedirs(run_dir, exist_ok=True)
        evolve("B", os.path.join(run_dir, "B"), r0=0.75,
               n_steps=args.steps, resume=args.resume is not None)
        print(f"\nNext: python run_pinch_correlation.py --analyze {run_dir}")


if __name__ == "__main__":
    main()
