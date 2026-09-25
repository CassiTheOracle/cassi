#!/usr/bin/env python3
"""Perturbation growth across the pinch, the mechanism behind the zap-and-zip
contrast (run_zap_and_zip.py, run_zap_expansion.py).

The zap-and-zip run finds PCI 0.484 above the pinch and 0.141 below it
(σ = 0.005, site c1, gate live), nearly unchanged with the gate switched off at
the pulse (0.461, 0.144). Freezing the expansion leaves three quarters of the
gap (0.466 vs 0.203; verdict SHARED). In the prepared states the weak-force
attenuation sf = f²/(f² + σ_g²) is below 0.03 in 90% of cells, so the pulse
enters the flow only weakly. One twin pair per state (pulse and control trials
from identical noise) showed the pulse's imprint on the flow growing about
twentyfold per 5 time units above the pinch and two- to threefold below it.

Test: twin pairs in the zap-and-zip secondary protocol. Same prepared states
(t = 6), noise σ = 0.005, 2 time units of burn-in, pulse at c1, gate live or
switched off at the pulse, 20 time units recorded. Each pair runs a control and
a pulse trial from identical noise. Eight pairs per (state, gate), seeds
300000 + k shared by all four conditions.
Recorded every time unit: flow separation d_u(t) = ‖u_pulse − u_ctrl‖ / ‖u_ctrl‖
and Yang displacement d_Y(t) = Σ|EY_pulse − EY_ctrl| / Σ(pulse Yang).
Statistic: growth rate Λ = least-squares slope of ln d_u(t) over t = 4, 5, …, 12.
Verdicts:
  primary  SEPARATED if every above/live pair has a larger Λ than every
           below/live pair; OVERLAP otherwise.
  gate     GATE-INDEPENDENT if |median Λ(live) − median Λ(off)| < 0.05 in both
           states; GATE-DEPENDENT otherwise.
Stopping rule: one run of the declared pairs.

Usage (from the CassiTheory root, after run_zap_and_zip.py --run):
  python two-fluid/run_zap_chaos.py --run [--workers 12]
  python two-fluid/run_zap_chaos.py --analyze
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
import run_zap_and_zip as z  # noqa: E402

OUT = os.path.join(z.OUT, "chaos")
SIGMA = z.SIGMAS["secondary"][0]
SITE = "c1"
PAIRS = 8
SEED0 = 300000
SAMPLE = int(round(1.0 / z.DT))
FIT = (4.0, 12.0)
GATE_TOL = 0.05


def plan():
    return [{"key": f"{state}_{gate}_{k}", "state": state, "gate": gate, "seed": SEED0 + k}
            for state in z.STATES for gate in z.GATES for k in range(PAIRS)]


def pair_path(key):
    return os.path.join(OUT, "pairs", key + ".npz")


def trial(solver, prepared, gate, pulse, seed):
    u_hat, ey_hat, ei_hat = z.load_state(solver, prepared)
    gen = torch.Generator(device=solver.device)
    gen.manual_seed(seed)
    amp = SIGMA * math.sqrt(z.DT)
    shape = (z.N,) * 3

    def step(u_hat, ey_hat, ei_hat):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, z.DT)
        ny = torch.randn(shape, generator=gen, device=solver.device, dtype=torch.float64)
        ni = torch.randn(shape, generator=gen, device=solver.device, dtype=torch.float64)
        return (u_hat, ey_hat + torch.fft.fftn(amp * ny) * solver.dealias,
                ei_hat + torch.fft.fftn(amp * ni) * solver.dealias)

    for _ in range(z.N_BURN):
        u_hat, ey_hat, ei_hat = step(u_hat, ey_hat, ei_hat)
    if pulse is not None:
        ey, ei = z.fields(ey_hat, ei_hat)
        ey_hat, ei_hat = torch.fft.fftn(ey + pulse), torch.fft.fftn(ei - pulse)
    solver.qi_gate = gate
    snaps = []
    for k in range(1, z.N_WIN + 1):
        u_hat, ey_hat, ei_hat = step(u_hat, ey_hat, ei_hat)
        if k % SAMPLE == 0:
            u = torch.stack([torch.fft.ifftn(x).real for x in u_hat])
            ey, _ = z.fields(ey_hat, ei_hat)
            snaps.append((u, ey))
    return snaps


def worker(index, count):
    solver = z.build_solver()
    prepared = {s: torch.load(os.path.join(z.OUT, f"prepared_{s}.pt"), weights_only=False)
                for s in z.STATES}
    pulse = z.PULSE_A * z.pulse_profile(z.SITES[SITE], solver.device)
    t0 = time.time()
    todo = [t for i, t in enumerate(plan()) if i % count == index]
    for n, t in enumerate(todo):
        path = pair_path(t["key"])
        if os.path.exists(path):
            continue
        gate = z.GATES[t["gate"]]
        ctrl = trial(solver, prepared[t["state"]], gate, None, t["seed"])
        hit = trial(solver, prepared[t["state"]], gate, pulse, t["seed"])
        du = np.array([float((up - uc).pow(2).sum(0).mean().sqrt() / uc.pow(2).sum(0).mean().sqrt())
                       for (uc, _), (up, _) in zip(ctrl, hit)])
        dy = np.array([float((yp - yc).abs().sum() / pulse.sum()) for (_, yc), (_, yp) in zip(ctrl, hit)])
        np.savez(path + ".tmp.npz", du=du, dy=dy)
        os.replace(path + ".tmp.npz", path)
        print(f"[worker {index}] {n + 1}/{len(todo)} {t['key']} {time.time() - t0:.0f}s", flush=True)


def run(workers):
    os.makedirs(os.path.join(OUT, "pairs"), exist_ok=True)
    t0 = time.time()
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__),
                               "--worker", str(i), "--workers", str(workers)])
             for i in range(workers)]
    codes = [p.wait() for p in procs]
    missing = [t["key"] for t in plan() if not os.path.exists(pair_path(t["key"]))]
    print(f"workers exited {codes}; {len(plan()) - len(missing)} pairs in "
          f"{time.time() - t0:.0f}s; missing {len(missing)}", flush=True)


def growth(du):
    t = np.arange(1, len(du) + 1, dtype=float)
    m = (t >= FIT[0]) & (t <= FIT[1])
    return float(np.polyfit(t[m], np.log(du[m]), 1)[0])


def analyze():
    res = {"fit_window": FIT, "conditions": {}}
    lam = {}
    for state in z.STATES:
        for gate in z.GATES:
            files = [np.load(pair_path(f"{state}_{gate}_{k}")) for k in range(PAIRS)]
            du = np.stack([f["du"] for f in files])
            dy = np.stack([f["dy"] for f in files])
            rates = [growth(d) for d in du]
            lam[state, gate] = rates
            c = {"growth_rates": rates, "median_growth": float(np.median(rates)),
                 "doubling_time": float(math.log(2) / np.median(rates)),
                 "median_du": np.median(du, axis=0).tolist(), "median_dy": np.median(dy, axis=0).tolist()}
            res["conditions"][f"{state}/{gate}"] = c
            print(f"{state:6s} {gate:4s} Λ median {c['median_growth']:.3f} "
                  f"[{min(rates):.3f}, {max(rates):.3f}] doubling {c['doubling_time']:.1f}  "
                  f"d_u(t=5,10,15,20) {np.round(np.median(du, axis=0)[[4, 9, 14, 19]], 5)}  "
                  f"d_Y {np.round(np.median(dy, axis=0)[[4, 9, 14, 19]], 1)}", flush=True)
    primary = "SEPARATED" if min(lam["above", "live"]) > max(lam["below", "live"]) else "OVERLAP"
    gate_delta = {s: float(np.median(lam[s, "live"]) - np.median(lam[s, "off"])) for s in z.STATES}
    gate = "GATE-INDEPENDENT" if all(abs(d) < GATE_TOL for d in gate_delta.values()) else "GATE-DEPENDENT"
    res.update({"primary": primary, "gate_delta": gate_delta, "gate": gate})
    print(f"primary: {primary}; gate deltas {gate_delta}: {gate}")
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(res, f, indent=2)


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
