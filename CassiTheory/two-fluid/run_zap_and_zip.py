#!/usr/bin/env python3
"""Zap-and-zip perturbational complexity test of the Qi-gate pinch
(consciousness/consciousness-from-phi.md §2.1; cassi-psychology.md §3).

Claim under test: above the pinch r = EY/EI = φ⁻¹ ≈ 0.618 the gate lets the
field's own coherence steer its evolution, and the psychology mapping places
deep anesthesia in the below-pinch regime. Massimini's zap-and-zip test reads
the level of consciousness from the brain's echo to a brief local pulse. The
perturbational complexity index (PCI; Casali et al. 2013, Sci Transl Med
5:198ra105) is high when the echo is both widespread and differentiated
(wakefulness 0.44–0.67) and low when it stays local or repeats one pattern
everywhere (NREM sleep and anesthesia 0.12–0.31; cutoff PCI* = 0.31).
Prediction: the canonical PDE field echoes with higher PCI above the pinch with
the gate live than (i) in the same state with the gate switched off at the pulse
and (ii) in a below-pinch state with the gate live.

Field: the canonical pinch-test configuration (run_pinch_correlation.py):
N = 48, L = 2π, λ = 0.02, D = 1e-4, ν = 5e-4, χ = 0, cs2 = 0, conversion Hubble
mode, single gate, amplitude 0.05, seed 42; dt = 0.02 (the pulse response
agrees with dt = 0.01 to 4% over the first five time units).
States, both prepared deterministically to t = 6 and pulsed at t = 8:
  below: r0 = 0.047 (r = 0.201 at t = 6; below φ⁻¹ through the window)
  above: r0 = 1.0   (r = 1.030 at t = 6)
Gate: live, or off (qi_gate = False) from the pulse onward in both arms.
Trials: K = 32 pulse trials per site and 32 control trials per condition. Each
trial loads the prepared state, runs 2 time units of spontaneous activity
(additive dealiased white noise on EY and EI, amplitude σ per √time), applies
the pulse (pulse arm only) and the gate setting, and records 20 time units at
0.2 spacing. Noise seeds depend only on (σ, arm, trial), so every condition
sees the same noise realizations.
Pulse: local balance shift δEY = +A·g(x), δEI = −A·g(x), A = 0.1, Gaussian g of
width 2 cells, at site c1 = box centre (24,24,24) or c2 = octant centre
(12,12,12).
Sources: EY averaged over 4³-cell blocks (12³ = 1728 sources) × 100 samples.
Binarization: Welch t (pulse vs control) per source and sample; a bit is
significant when |t| exceeds the 99th percentile of the matrix-wide max |t|
over 500 label permutations (family-wise α = 0.01).
PCI: Lempel–Ziv (1976) complexity c of the binary matrix with rows sorted by
total activity and read sample by sample, normalized as c·log2(L)/(L·H), with
L the matrix size and H the binary entropy of its fraction of significant bits.

Verdict (primary: σ = 0.02, PCI_max = max over the two sites):
  SUPPORTED   if PCI_max(above, live) exceeds both PCI_max(above, off) and
              PCI_max(below, live) by ≥ 0.05, and both orderings hold at each
              site.
  CONTRADICTS if PCI_max(above, live) falls ≥ 0.05 below either comparison.
  NULL        otherwise.
Secondary (reported outside the verdict): the gate × state interaction; the
σ = 0.005 repeat at c1; spread (fraction of sources ever significant); position
relative to PCI* = 0.31, whose calibration is human TMS–EEG.
Stopping rule: one run of the declared trials.

Usage (from the CassiTheory root):
  python two-fluid/run_zap_and_zip.py --run [--workers 8]   # trials → runs/zap_and_zip/
  python two-fluid/run_zap_and_zip.py --analyze             # PCI, verdict, figure
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI_INV  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "runs", "zap_and_zip")

# ---------------------------------------------------------------------------
# Frozen configuration
# ---------------------------------------------------------------------------
N = 48
L = 2.0 * np.pi
DT = 0.02
LAM = 0.02
D = 0.0001
NU = 0.0005
CHI = 0.0
AMPLITUDE = 0.05
SEED = 42
T_PREP = 6.0
T_BURN = 2.0
T_WIN = 20.0
REC_EVERY = 0.2
STATES = {"below": 0.047, "above": 1.0}
GATES = {"live": True, "off": False}
SITES = {"c1": (24, 24, 24), "c2": (12, 12, 12)}
PULSE_A = 0.1
PULSE_W = 2.0
BLOCK = 4
K = 32
SIGMAS = {"primary": (0.02, ("c1", "c2")), "secondary": (0.005, ("c1",))}
N_PERM = 500
ALPHA = 0.01
DELTA = 0.05
PCI_STAR = 0.31

N_BURN = int(round(T_BURN / DT))
N_WIN = int(round(T_WIN / DT))
REC_STEPS = int(round(REC_EVERY / DT))
N_REC = N_WIN // REC_STEPS
N_SRC = (N // BLOCK) ** 3


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------
def build_solver():
    return ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=NU, D=D, lam=LAM, chi=CHI,
        hubble_mode="conversion", cs2=0.0, qi_gate=True, qi_memory=False,
        mode="cosmos")


def fields(ey_hat, ei_hat):
    return torch.fft.ifftn(ey_hat).real, torch.fft.ifftn(ei_hat).real


def prepare(state):
    """Deterministic evolution from r0 to T_PREP; returns the full solver state."""
    solver = build_solver()
    solver.initial_ratio = 1.0 / STATES[state]      # solver takes <EI>/<EY>
    u_hat, ey_hat, ei_hat = solver.initial_expanding(amplitude=AMPLITUDE, seed=SEED)
    for _ in range(int(round(T_PREP / DT))):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
    ey, ei = fields(ey_hat, ei_hat)
    return {"u_hat": [x.cpu() for x in u_hat], "ey_hat": ey_hat.cpu(),
            "ei_hat": ei_hat.cpu(), "a": solver.a.cpu(),
            "H_smooth": solver._H_smooth.cpu(), "H": solver.H.cpu(),
            "r": float((ey.mean() / ei.mean()).item())}


def load_state(solver, prepared):
    dev = solver.device
    solver.a = prepared["a"].to(dev).clone()
    solver._H_smooth = prepared["H_smooth"].to(dev).clone()
    solver.H = prepared["H"].to(dev).clone()
    solver.qi_gate = True
    return ([x.to(dev).clone() for x in prepared["u_hat"]],
            prepared["ey_hat"].to(dev).clone(), prepared["ei_hat"].to(dev).clone())


def pulse_profile(site, device):
    i = torch.arange(N, device=device, dtype=torch.float64)
    axes = []
    for c in site:
        d = (i - c).abs()
        d = torch.minimum(d, N - d)
        axes.append(torch.exp(-d ** 2 / (2.0 * PULSE_W ** 2)))
    return axes[0][:, None, None] * axes[1][None, :, None] * axes[2][None, None, :]


def block_means(ey):
    b = N // BLOCK
    return ey.reshape(b, BLOCK, b, BLOCK, b, BLOCK).mean(dim=(1, 3, 5)).flatten()


def run_trial(solver, prepared, gate, site, sigma, seed):
    """One trial: burn-in with spontaneous activity, optional pulse, recording."""
    u_hat, ey_hat, ei_hat = load_state(solver, prepared)
    gen = torch.Generator(device=solver.device)
    gen.manual_seed(seed)
    amp = sigma * math.sqrt(DT)
    shape = (N, N, N)

    def noisy_step(u_hat, ey_hat, ei_hat):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
        ny = torch.randn(shape, generator=gen, device=solver.device, dtype=torch.float64)
        ni = torch.randn(shape, generator=gen, device=solver.device, dtype=torch.float64)
        ey_hat = ey_hat + torch.fft.fftn(amp * ny) * solver.dealias
        ei_hat = ei_hat + torch.fft.fftn(amp * ni) * solver.dealias
        return u_hat, ey_hat, ei_hat

    for _ in range(N_BURN):
        u_hat, ey_hat, ei_hat = noisy_step(u_hat, ey_hat, ei_hat)
    if site is not None:
        ey, ei = fields(ey_hat, ei_hat)
        g = PULSE_A * pulse_profile(site, solver.device)
        ey_hat, ei_hat = torch.fft.fftn(ey + g), torch.fft.fftn(ei - g)
    solver.qi_gate = gate
    rec = np.empty((N_REC, N_SRC), dtype=np.float32)
    ratio = np.empty(N_REC)
    q = np.empty(N_REC)
    for k in range(1, N_WIN + 1):
        u_hat, ey_hat, ei_hat = noisy_step(u_hat, ey_hat, ei_hat)
        if k % REC_STEPS == 0:
            j = k // REC_STEPS - 1
            ey, ei = fields(ey_hat, ei_hat)
            rec[j] = block_means(ey).cpu().numpy()
            ratio[j] = float((ey.mean() / ei.mean()).item())
            q[j] = float(solver.q_mean) if gate else 0.0
    return rec, ratio, q


# ---------------------------------------------------------------------------
# Trial plan
# ---------------------------------------------------------------------------
def trial_plan():
    plan = []
    for si, (slabel, (sigma, sites)) in enumerate(SIGMAS.items()):
        arms = ["ctrl"] + list(sites)
        for state in STATES:
            for gate in GATES:
                for ai, arm in enumerate(arms):
                    for k in range(K):
                        plan.append({
                            "key": f"{slabel}_{state}_{gate}_{arm}_{k:02d}",
                            "sigma": sigma, "state": state, "gate": gate,
                            "site": None if arm == "ctrl" else arm,
                            "seed": 100000 * (si + 1) + 1000 * ai + k})
    return plan


def trial_path(key):
    return os.path.join(OUT, "trials", key + ".npz")


def worker(index, count):
    solver = build_solver()
    prepared = {s: torch.load(os.path.join(OUT, f"prepared_{s}.pt"), weights_only=False)
                for s in STATES}
    todo = [t for i, t in enumerate(trial_plan()) if i % count == index]
    t0 = time.time()
    for n, t in enumerate(todo):
        path = trial_path(t["key"])
        if os.path.exists(path):
            continue
        site = SITES[t["site"]] if t["site"] else None
        rec, ratio, q = run_trial(solver, prepared[t["state"]], GATES[t["gate"]],
                                  site, t["sigma"], t["seed"])
        np.savez(path + ".tmp.npz", rec=rec, ratio=ratio, q=q)
        os.replace(path + ".tmp.npz", path)
        if n % 10 == 0:
            print(f"[worker {index}] {n + 1}/{len(todo)} {t['key']} "
                  f"{time.time() - t0:.0f}s", flush=True)


def run(workers):
    os.makedirs(os.path.join(OUT, "trials"), exist_ok=True)
    for s in STATES:
        path = os.path.join(OUT, f"prepared_{s}.pt")
        if not os.path.exists(path):
            p = prepare(s)
            torch.save(p, path)
            print(f"prepared {s}: r = {p['r']:.4f} at t = {T_PREP}", flush=True)
    t0 = time.time()
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__),
                               "--worker", str(i), "--workers", str(workers)])
             for i in range(workers)]
    codes = [p.wait() for p in procs]
    missing = [t["key"] for t in trial_plan() if not os.path.exists(trial_path(t["key"]))]
    print(f"workers exited {codes}; {len(trial_plan()) - len(missing)} trials in "
          f"{time.time() - t0:.0f}s; missing {len(missing)}", flush=True)


# ---------------------------------------------------------------------------
# Statistic
# ---------------------------------------------------------------------------
def lz76(s: bytes) -> int:
    """Lempel–Ziv (1976) phrase count, Kaspar–Schuster parsing."""
    n = len(s)
    c = 0
    l = 0
    while l < n:
        k = 1
        p = s.find(s[l:l + 1], 0, l) if l > 0 else -1
        while p != -1:
            k += 1
            if l + k > n:
                break
            if s[p + k - 1] != s[l + k - 1]:
                p = s.find(s[l:l + k], p + 1, l + k - 1)
        c += 1
        l += k
    return c


def pci(ss):
    """PCI of a binary (samples × sources) matrix."""
    size = ss.size
    p1 = float(ss.mean())
    if p1 <= 0.0 or p1 >= 1.0:
        return 0.0
    h = -(p1 * math.log2(p1) + (1.0 - p1) * math.log2(1.0 - p1))
    order = np.argsort(ss.sum(axis=0), kind="stable")
    s = np.ascontiguousarray(ss[:, order]).astype(np.uint8).tobytes()
    return lz76(s) * math.log2(size) / (size * h)


def welch_t(a, b):
    ma, mb = a.mean(0), b.mean(0)
    va, vb = a.var(dim=0, correction=1), b.var(dim=0, correction=1)
    return (ma - mb) / torch.sqrt(va / a.shape[0] + vb / b.shape[0] + 1e-30)


def significance(x, y, seed):
    """Binary matrix of family-wise significant pulse effects (samples × sources)."""
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    a = torch.as_tensor(x.reshape(x.shape[0], -1), device=dev, dtype=torch.float64)
    b = torch.as_tensor(y.reshape(y.shape[0], -1), device=dev, dtype=torch.float64)
    t = welch_t(a, b)
    z = torch.cat([a, b])
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    maxes = np.empty(N_PERM)
    for i in range(N_PERM):
        idx = torch.randperm(z.shape[0], generator=gen).to(dev)
        maxes[i] = float(welch_t(z[idx[:a.shape[0]]], z[idx[a.shape[0]:]]).abs().max())
    thr = float(np.quantile(maxes, 1.0 - ALPHA))
    ss = (t.abs() > thr).cpu().numpy().reshape(x.shape[1], x.shape[2])
    return ss, thr


def load_arm(slabel, state, gate, arm):
    recs, ratios, qs = [], [], []
    for k in range(K):
        with np.load(trial_path(f"{slabel}_{state}_{gate}_{arm}_{k:02d}")) as f:
            recs.append(f["rec"]); ratios.append(f["ratio"]); qs.append(f["q"])
    return np.stack(recs), np.stack(ratios), np.stack(qs)


def analyze():
    results = {"config": {
        "N": N, "dt": DT, "lam": LAM, "D": D, "nu": NU, "amplitude": AMPLITUDE,
        "seed": SEED, "t_prep": T_PREP, "t_burn": T_BURN, "t_win": T_WIN,
        "rec_every": REC_EVERY, "states": STATES, "sites": SITES,
        "pulse_A": PULSE_A, "pulse_w": PULSE_W, "block": BLOCK, "K": K,
        "sigmas": {k: v[0] for k, v in SIGMAS.items()}, "n_perm": N_PERM,
        "alpha": ALPHA, "delta": DELTA}, "conditions": {}}
    ss_store = {}
    times = REC_EVERY * np.arange(1, N_REC + 1)
    for si, (slabel, (sigma, sites)) in enumerate(SIGMAS.items()):
        for state in STATES:
            for gate in GATES:
                y, ratio, q = load_arm(slabel, state, gate, "ctrl")
                for site in sites:
                    x, _, _ = load_arm(slabel, state, gate, site)
                    ss, thr = significance(x, y, seed=7 + si)
                    active = ss.any(axis=0)
                    rows = ss.sum(axis=1)
                    key = f"{slabel}/{state}/{gate}/{site}"
                    results["conditions"][key] = {
                        "PCI": pci(ss), "threshold_t": thr,
                        "fraction_significant": float(ss.mean()),
                        "spread": float(active.mean()),
                        "last_significant_t": float(times[rows > 0].max()) if rows.any() else 0.0,
                        "peak_sources": int(rows.max()),
                        "peak_t": float(times[rows.argmax()]),
                        "r_start": float(ratio[:, 0].mean()), "r_end": float(ratio[:, -1].mean()),
                        "r_max": float(ratio.max()), "q_mean": float(q.mean())}
                    ss_store[key] = ss
                    c = results["conditions"][key]
                    print(f"{key:28s} PCI={c['PCI']:.3f} thr|t|={thr:5.2f} "
                          f"frac={c['fraction_significant']:.4f} spread={c['spread']:.3f} "
                          f"last={c['last_significant_t']:5.1f} peak={c['peak_sources']:4d}@{c['peak_t']:.1f} "
                          f"r {c['r_start']:.3f}->{c['r_end']:.3f} (max {c['r_max']:.3f}) "
                          f"q={c['q_mean']:.3f}", flush=True)

    cond = results["conditions"]

    def pmax(state, gate):
        return max(cond[f"primary/{state}/{gate}/{s}"]["PCI"] for s in SIGMAS["primary"][1])

    al, ao, bl, bo = pmax("above", "live"), pmax("above", "off"), pmax("below", "live"), pmax("below", "off")
    per_site = all(cond[f"primary/above/live/{s}"]["PCI"] > cond[f"primary/above/off/{s}"]["PCI"]
                   and cond[f"primary/above/live/{s}"]["PCI"] > cond[f"primary/below/live/{s}"]["PCI"]
                   for s in SIGMAS["primary"][1])
    if al - ao >= DELTA and al - bl >= DELTA and per_site:
        verdict = "SUPPORTED"
    elif al <= ao - DELTA or al <= bl - DELTA:
        verdict = "CONTRADICTS"
    else:
        verdict = "NULL"
    results["pci_max"] = {"above/live": al, "above/off": ao, "below/live": bl, "below/off": bo}
    results["interaction"] = (al - ao) - (bl - bo)
    results["verdict"] = verdict
    print(f"PCI_max  above/live={al:.3f} above/off={ao:.3f} below/live={bl:.3f} "
          f"below/off={bo:.3f}  interaction={results['interaction']:+.3f}")
    print(f"VERDICT: {verdict}")
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    figure(results, ss_store, times)


def figure(results, ss_store, times):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BG, TEXT_MAIN, TEXT_SUB, RING = "#060612", "#e0e0f0", "#a0a0c0", "#303050"
    YIN_LIGHT, YANG_BRIGHT = "#4a2a8e", "#daa520"
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "text.color": TEXT_MAIN, "axes.edgecolor": RING, "axes.labelcolor": TEXT_SUB,
        "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB, "font.size": 9})
    cond = results["conditions"]
    site = max(SIGMAS["primary"][1],
               key=lambda s: cond[f"primary/above/live/{s}"]["PCI"])
    panels = [("above", "live"), ("above", "off"), ("below", "live"), ("below", "off")]
    fig = plt.figure(figsize=(11, 6.2))
    for i, (state, gate) in enumerate(panels):
        ax = fig.add_axes([0.05 + (i % 2) * 0.3, 0.55 - (i // 2) * 0.45, 0.27, 0.34])
        key = f"primary/{state}/{gate}/{site}"
        ss = ss_store[key]
        order = np.argsort(ss.sum(axis=0), kind="stable")[::-1]
        ax.imshow(ss[:, order].T, aspect="auto", cmap=matplotlib.colors.ListedColormap([BG, YANG_BRIGHT]),
                  extent=[times[0], times[-1], ss.shape[1], 0], interpolation="nearest")
        ax.set_title(f"{state} pinch, gate {gate}: PCI = {cond[key]['PCI']:.2f}",
                     color=TEXT_MAIN, fontsize=9)
        ax.set_xlabel("time after pulse")
        ax.set_ylabel("sources (sorted)")
    ax = fig.add_axes([0.68, 0.1, 0.3, 0.79])
    labels = ["above\nlive", "above\noff", "below\nlive", "below\noff"]
    vals = [results["pci_max"][f"{s}/{g}"] for s, g in panels]
    ax.bar(labels, vals, color=[YANG_BRIGHT, YIN_LIGHT, YIN_LIGHT, YIN_LIGHT])
    ax.axhline(PCI_STAR, color=TEXT_SUB, lw=0.8, ls="--")
    ax.text(3.4, PCI_STAR, "human PCI* 0.31", color=TEXT_SUB, ha="right", va="bottom", fontsize=8)
    ax.set_ylabel("PCI (max over sites)")
    ax.set_title(f"verdict: {results['verdict']}", color=TEXT_MAIN, fontsize=9)
    fig.text(0.05, 0.95, "Zap and zip on the two-fluid field: PCI = c·log2(L)/(L·H) of the "
             "significant echo", color=TEXT_MAIN, fontsize=10)
    out = os.path.join(OUT, "zap_and_zip.png")
    fig.savefig(out, dpi=150, facecolor=BG)
    print(f"figure → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--worker", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if args.worker is not None:
        worker(args.worker, args.workers)
    elif args.run:
        run(args.workers)
    elif args.analyze:
        analyze()
    else:
        ap.print_help()
