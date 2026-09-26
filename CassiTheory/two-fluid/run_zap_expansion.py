#!/usr/bin/env python3
"""Expansion-frozen follow-up to the zap-and-zip test (run_zap_and_zip.py).

The zap-and-zip run finds the canonical field's echo to a local pulse far more
complex above the pinch than below it (PCI 0.484 vs 0.141 at σ = 0.005, site
c1, gate live), and switching the gate off at the pulse leaves both nearly
unchanged (0.461 and 0.144). The two prepared states differ in composition
(r = 1.03 vs 0.20 at t = 6) and in expansion: the conversion Hubble law
H = (λ/3)[φ⁻² + (φ − r)(1 + r)/r] gives H = 0.010 above and 0.059 below, so
Hubble drag −H·u damps the below-pinch flow about six times faster.

Question: does the expansion carry the complexity gap?
Arms: the zap-and-zip secondary protocol (σ = 0.005, site c1, gate live, K = 32
pulse and 32 control trials per state, the same noise seeds) with the
expansion frozen from the start of each trial: H = 0 and the scale factor held
at its prepared value (a = 1.065 above, 1.562 below), so the comoving 1/a
factors on advection, force, and diffusion still differ between the states.
Statistic: PCI exactly as in run_zap_and_zip.py (significance seed 8).
gap_live = PCI(above) - PCI(below) from the zap-and-zip run (0.343);
gap_frozen = PCI(above, frozen) - PCI(below, frozen).
Verdict:
  EXPANSION  if gap_frozen <= 0.5 * gap_live
  STATE      if gap_frozen >= 0.8 * gap_live
  SHARED     otherwise.
Stopping rule: one run of the declared trials.

Usage (from the CassiTheory root, after run_zap_and_zip.py --run):
  python two-fluid/run_zap_expansion.py --run [--workers 12]
  python two-fluid/run_zap_expansion.py --analyze
"""

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_zap_and_zip as z  # noqa: E402

OUT = os.path.join(z.OUT, "expansion_frozen")
SIGMA = z.SIGMAS["secondary"][0]
SITE = "c1"
ARMS = ("ctrl", SITE)
SIG_SEED = 8

_load_state = z.load_state


def _load_frozen(solver, prepared):
    state = _load_state(solver, prepared)
    solver.H = torch.zeros_like(solver.H)
    solver._H_smooth = torch.zeros_like(solver._H_smooth)
    return state


z.load_state = _load_frozen


def frozen_solver():
    solver = z.build_solver()
    solver._update_hubble = lambda ey, ei: None
    return solver


def plan():
    trials = []
    for state in z.STATES:
        for ai, arm in enumerate(ARMS):
            for k in range(z.K):
                trials.append({"key": f"{state}_{arm}_{k:02d}", "state": state,
                               "site": None if arm == "ctrl" else arm,
                               "seed": 100000 * 2 + 1000 * ai + k})
    return trials


def trial_path(key):
    return os.path.join(OUT, "trials", key + ".npz")


def worker(index, count):
    solver = frozen_solver()
    prepared = {s: torch.load(os.path.join(z.OUT, f"prepared_{s}.pt"), weights_only=False)
                for s in z.STATES}
    todo = [t for i, t in enumerate(plan()) if i % count == index]
    t0 = time.time()
    for n, t in enumerate(todo):
        path = trial_path(t["key"])
        if os.path.exists(path):
            continue
        site = z.SITES[t["site"]] if t["site"] else None
        rec, ratio, q = z.run_trial(solver, prepared[t["state"]], True, site, SIGMA, t["seed"])
        np.savez(path + ".tmp.npz", rec=rec, ratio=ratio, q=q, a=float(solver.a), H=float(solver.H))
        os.replace(path + ".tmp.npz", path)
        print(f"[worker {index}] {n + 1}/{len(todo)} {t['key']} {time.time() - t0:.0f}s", flush=True)


def run(workers):
    os.makedirs(os.path.join(OUT, "trials"), exist_ok=True)
    t0 = time.time()
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__),
                               "--worker", str(i), "--workers", str(workers)])
             for i in range(workers)]
    codes = [p.wait() for p in procs]
    missing = [t["key"] for t in plan() if not os.path.exists(trial_path(t["key"]))]
    print(f"workers exited {codes}; {len(plan()) - len(missing)} trials in "
          f"{time.time() - t0:.0f}s; missing {len(missing)}", flush=True)


def load(state, arm):
    files = [np.load(trial_path(f"{state}_{arm}_{k:02d}")) for k in range(z.K)]
    return (np.stack([f["rec"] for f in files]), np.stack([f["ratio"] for f in files]),
            [float(f["a"]) for f in files], [float(f["H"]) for f in files])


def analyze():
    with open(os.path.join(z.OUT, "results.json")) as f:
        live = json.load(f)["conditions"]
    times = z.REC_EVERY * np.arange(1, z.N_REC + 1)
    res = {"sigma": SIGMA, "site": SITE, "conditions": {}}
    for state in z.STATES:
        y, _, _, _ = load(state, "ctrl")
        x, ratio, a_end, h_end = load(state, SITE)
        ss, thr = z.significance(x, y, seed=SIG_SEED)
        rows = ss.sum(axis=1)
        c = {"PCI": z.pci(ss), "threshold_t": thr, "fraction_significant": float(ss.mean()),
             "spread": float(ss.any(axis=0).mean()),
             "last_significant_t": float(times[rows > 0].max()) if rows.any() else 0.0,
             "peak_sources": int(rows.max()), "peak_t": float(times[rows.argmax()]),
             "r_start": float(ratio[:, 0].mean()), "r_end": float(ratio[:, -1].mean()),
             "a_end": [min(a_end), max(a_end)], "H_end": [min(h_end), max(h_end)],
             "PCI_live": live[f"secondary/{state}/live/{SITE}"]["PCI"]}
        res["conditions"][state] = c
        print(f"{state:6s} frozen PCI={c['PCI']:.3f} (live {c['PCI_live']:.3f}) "
              f"spread={c['spread']:.3f} peak={c['peak_sources']}@{c['peak_t']:.1f} "
              f"last={c['last_significant_t']:.1f} r {c['r_start']:.3f}->{c['r_end']:.3f} "
              f"a_end={c['a_end']} H_end={c['H_end']}", flush=True)
    cond = res["conditions"]
    gap_live = cond["above"]["PCI_live"] - cond["below"]["PCI_live"]
    gap_frozen = cond["above"]["PCI"] - cond["below"]["PCI"]
    if gap_frozen <= 0.5 * gap_live:
        verdict = "EXPANSION"
    elif gap_frozen >= 0.8 * gap_live:
        verdict = "STATE"
    else:
        verdict = "SHARED"
    res.update({"gap_live": gap_live, "gap_frozen": gap_frozen, "verdict": verdict})
    print(f"gap_live={gap_live:.3f} gap_frozen={gap_frozen:.3f} VERDICT: {verdict}")
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
