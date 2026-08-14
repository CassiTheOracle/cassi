#!/usr/bin/env python3
"""Kepler multi-planet period-ratio phi test (Prediction 54).

Run from the repo root:
    python experiments/kepler_phi_ratios/run_phi_ratios.py

WHAT THIS TESTS
---------------
The Cassi exoplanet phi-spacing prediction (hypotheses/exoplanet-phi-spacing.md
§3) states that in multi-planet systems the distribution of ADJACENT-planet
PERIOD ratios P_out/P_in = (a_out/a_in)^(3/2) is enhanced at phi and at the
headline ratio phi^(3/2) = 2.058 (the boxed prediction), and that the specific
resonances populated are the Fibonacci convergents of phi -- not an arbitrary
set of rational ratios. The clean discriminating signal is the
phi^(3/2) = 2.06 window, which is NOT a standard mean-motion resonance and
therefore separates the phi prediction from the generic resonance-ubiquity
baseline. This is the Kepler/TESS catalog branch beside the DSHARP disk-gap
branch (Prediction 53); it has not previously been run on real data.

DATA
----
Primary sample: confirmed TRANSIT-discovered planets in MULTI-PLANET systems
seen by the original Kepler mission (NPC Exoplanet Archive ps table,
default_flag=1, discoverymethod='Transit', disc_facility CONTAINS 'Kepler').
K2/TESS transit multi-planet systems are pulled alongside as a cross-check.
For each system the planets are ordered by orbital period and the adjacent
period ratios P_outer/P_inner are formed. Data + hashes:
experiments/kepler_phi_ratios/data/parsed/<tag>_ratios.csv and
data/raw/sha256.txt (acquisition: acquire_kepler_catalog.py).

PRE-REGISTERED DECISION TREE  (written before any analysis run below)
----------------------------------------------------------------------
Ratios: adjacent P_out/P_in, ordered by period, within each host system,
pooled across all Kepler multi-planet systems.

Windows (fixed half-width 0.05 in ratio space):
  S     (headline, clean phi)  = phi^(3/2) +- 0.05  = [2.008, 2.108]
          (phi^(3/2) = 2.0582; NOT a standard 2-body resonance at exact 2.0,
           so this is the phi-non-convergent / non-resonance discriminator)
  PhiB  (phi attactor belt)    = [1.568, 1.668]  (phi=1.618 +- 0.05;
          captures the tight convergent cluster 8/5=1.6, 13/8=1.625,
          5/3=1.667 on its edge)
  Conv  (Fibonacci convergents, confounded by MMR) =
          [1.45,1.55] (3:2); [1.568,1.668] (phi belt); [1.95,2.05] (2:1)
  Ctrl  (non-phi, non-Fibonacci resonance controls; MUST NOT be elevated)
          [1.283,1.383] (4:3); [2.283,2.383] (7:3); [2.45,2.55] (5:2)

Null (folded-window, matching predictions 45/46 -- the null is the
distribution of ratio COUNTS over equal-width windows across the same ratio
range, never a unit interval): sweep a window of the same half-width 0.05
across the full sampled ratio range c in [1.0, 3.0]; let the null mean E and
std s be the mean/std of these sliding-window counts. The significance of a
target window is (N_target - E)/s: the number of sigma the count in that
window sits above the count density at a generic window of the same width,
automatically accounting for the global shape of the ratio distribution
(incl. the Kepler compact-system/peas-in-a-pod bias that piles counts at
small ratios).

Counts: N(S), N(PhiB), N(Conv_i), N(Ctrl_j).

Verdict (>= 2.0 sigma above the folded-window null mean; separation from the
non-phi controls requires them NOT to be elevated >= 2.0 sigma):
  SUPPORTS       if N(S) >= E + 2.0*s  AND  max_j (N(Ctrl_j) - E)/s < +2.0*s
                 (the phi^(3/2)=2.06 window is elevated; the non-phi,
                 non-Fibonacci resonance windows are not)
  SUPPORTS NULL  if N(S) <  E + 2.0*s  AND  at least one Ctrl window
                 >= E + 2.0*s  (a non-phi control is elevated while 2.06 is
                 not)
  INDETERMINATE  otherwise (2.06 not elevated and controls not elevated; or
                 both elevated).

Secondary record (NOT part of the verdict, reported for the doc): the
Fibonacci-convergent windows 3:2, phi-belt, 2:1 counts and their sigma. These
windows are ALSO standard mean-motion resonances, so their elevation is
predicted both by the phi mechanism and by generic resonance-locking; the
honest discriminator is the clean 2.06 window plus the requirement that the
non-Fibonacci controls (4:3, 7:3, 5:2) stay at baseline.

Detected-signal power: plant an artificial phi^(3/2) excess -- add K synthetic
adjacent ratios drawn from log-normal(log 2.058, scatter) to the observed
catalog (K = a few % of the sample) -- and measure the fraction of
realizations in which the decision tree returns SUPPORTS (200 realizations
per amplitude). This calibrates how the tree would score a genuine 2.06
signal at this sample size.

All outcomes are honest and reported; the verdict SHALL be reported verbatim
(SUPPORTS / SUPPORTS NULL / INDETERMINATE) with the numbers in the run JSON.
"""
import csv
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

PHI = (1 + 5 ** 0.5) / 2
PHI_32 = PHI ** 1.5          # 2.0582
HALF = 0.05                   # fixed window half-width

# Windows
W_S = (PHI_32 - HALF, PHI_32 + HALF)      # [2.0082, 2.1082]  clean phi^(3/2)
W_PHIB = (PHI - HALF, PHI + HALF)         # [1.568, 1.668]    phi belt
CONV_WIN = {                               # Fibonacci convergents (MMR-confounded)
    "3:2": (1.50 - HALF, 1.50 + HALF),     # [1.45, 1.55]
    "phi_belt": W_PHIB,                    # phi + 8/5 + 13/8 + 5:3 edge
    "2:1": (2.00 - HALF, 2.00 + HALF),     # [1.95, 2.05]
}
CTRL_WIN = {                               # non-phi, non-Fibonacci resonance controls
    "4:3": (4 / 3 - HALF, 4 / 3 + HALF),   # [1.2833, 1.3833]
    "7:3": (7 / 3 - HALF, 7 / 3 + HALF),   # [2.2833, 2.3833]
    "5:2": (5 / 2 - HALF, 5 / 2 + HALF),   # [2.45, 2.55]
}

SWEEP_LO, SWEEP_HI = 1.0, 3.0     # folded-window null sweep range
RATIO_MIN, RATIO_MAX = 1.0, 4.0   # accepted ratio range (transit cadence floor)

MYDIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(MYDIR, "data", "parsed", "kepler_ratios.csv")
K2CSV = os.path.join(MYDIR, "data", "parsed", "k2_tess_ratios.csv")
RUNS_DIR = os.path.join(MYDIR, "data", "runs")
os.makedirs(RUNS_DIR, exist_ok=True)

RNG = np.random.default_rng(20260813)
N_NULL = 1000
N_POWER = 200


def load_ratios(csv_path):
    """Return sorted numpy array of adjacent period ratios in [MIN, MAX]."""
    ratios = []
    flds = ["host", "pl_in", "pl_out", "period_in_d", "period_out_d", "ratio"]
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(
                (r for r in f if not r.lstrip().startswith("#")),
                fieldnames=flds):
            if row["ratio"] == "ratio":   # the (commented) header row
                continue
            try:
                q = float(row["ratio"])
            except (TypeError, ValueError):
                continue
            if RATIO_MIN <= q <= RATIO_MAX:
                ratios.append(q)
    return np.array(sorted(ratios), dtype=float)


def in_win(q, win):
    return win[0] <= q <= win[1]


def count_in(ratios, win):
    return int(np.sum((ratios >= win[0]) & (ratios <= win[1])))


def folded_null(ratios, half, lo, hi, n_steps=40001, seed=1):
    """Folded-window null: mean/std of equal-width-window counts sweeping the
    window center c over [lo, hi] across the same ratio distribution.

    Returns (E, s, centers, counts). The null is the distribution of COUNTS in
    a window of the same width at a generic location -- the predictions 45/46
    discipline (never a unit interval, same period window everywhere).
    """
    r = RNG  # deterministic given the run
    # Sample window centers uniformly over [lo, hi].
    centers = r.uniform(lo, hi, size=n_steps)
    counts = np.array([count_in(ratios, (c - half, c + half)) for c in centers])
    return float(counts.mean()), float(counts.std()), centers, counts


def evaluate_windows(ratios):
    """Compute counts + folded-null sigma for all signal/conv/control windows."""
    E, s, _, _ = folded_null(ratios, HALF, SWEEP_LO, SWEEP_HI)
    res = {"null": {"half": HALF, "sweep": [SWEEP_LO, SWEEP_HI],
                    "mean": E, "std": s}}
    for name, win in [("S_phi32", W_S), ("PhiB", W_PHIB)]:
        n = count_in(ratios, win)
        res[name] = {"window": list(win), "N": n,
                     "sigma": float((n - E) / s) if s else None}
    res["convergents"] = {}
    for name, win in CONV_WIN.items():
        n = count_in(ratios, win)
        res["convergents"][name] = {"window": list(win), "N": n,
                                    "sigma": float((n - E) / s) if s else None}
    res["controls"] = {}
    for name, win in CTRL_WIN.items():
        n = count_in(ratios, win)
        res["controls"][name] = {"window": list(win), "N": n,
                                 "sigma": float((n - E) / s) if s else None}
    return res, E, s


def decide(res):
    """Apply the pre-registered verdict rule. Returns (verdict, reason)."""
    E = res["null"]["mean"]
    s = res["null"]["std"]
    ns = res["S_phi32"]["N"]
    sig_s = (ns - E) / s
    max_ctrl_sig = max(v["sigma"] for v in res["controls"].values())
    if sig_s >= 2.0 and max_ctrl_sig < 2.0:
        return "SUPPORTS", (f"S_phi32 N={ns} at {sig_s:.2f} sigma >= 2.0; "
                            f"controls max {max_ctrl_sig:.2f} sigma < 2.0")
    if sig_s < 2.0 and max_ctrl_sig >= 2.0:
        return "SUPPORTS NULL", (f"S_phi32 N={ns} at {sig_s:.2f} sigma < 2.0; "
                                 f"a control window at {max_ctrl_sig:.2f} sigma")
    return "INDETERMINATE", (
        f"S_phi32 {sig_s:.2f} sigma; controls max {max_ctrl_sig:.2f} sigma")


def detection_power(ratios, amplitudes=(0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20),
                    scatter=0.02, n_real=N_POWER):
    """Plant a phi^(3/2) excess of K = round(len*amp) synthetic ratios drawn
    log-normal about log 2.058 with scatter; return the fraction of
    realizations in which the decision tree returns SUPPORTS for each amplitude
    (same E, s folded-null as the real run). Characterizes the amplitude at
    which a genuine 2.06 signal would be detected at this sample size."""
    n0 = len(ratios)
    E, s, _, _ = folded_null(ratios, HALF, SWEEP_LO, SWEEP_HI)
    out = {}
    for amp in amplitudes:
        k = max(1, int(round(n0 * amp)))
        hits = 0
        for _ in range(n_real):
            extra = np.exp(RNG.normal(math.log(PHI_32), scatter, size=k))
            rr = np.concatenate([ratios, extra])
            rr = rr[(rr >= RATIO_MIN) & (rr <= RATIO_MAX)]
            ns = count_in(rr, W_S)
            sig_s = (ns - E) / s
            ctr_sig = [(count_in(rr, w) - E) / s for w in CTRL_WIN.values()]
            if sig_s >= 2.0 and max(ctr_sig) < 2.0:
                hits += 1
        out[f"amp_{amp}"] = hits / n_real
    return out


def reshuffle_null(csv_path, n_real=1000, seed=7):
    """Secondary null (diagnostic only, NOT part of the pre-registered
    verdict): preserve each system's multiplicity and period span, but draw
    each planet's period independently log-uniform over the system's observed
    [P_min, P_max], then re-form adjacent ratios. Returns (mean, std) of the
    S_phi32-window count under this null, for the given sample."""
    per = {}
    flds = ["host", "pl_in", "pl_out", "period_in_d", "period_out_d", "ratio"]
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(
                (r for r in f if not r.lstrip().startswith("#")), fieldnames=flds):
            if row["host"] == "host":
                continue
            try:
                p = float(row["period_out_d"])
            except (TypeError, ValueError):
                continue
            per.setdefault(row["host"], []).append(p)
    loc = np.random.default_rng(seed)
    counts = []
    for _ in range(n_real):
        rr = []
        for host, ps in per.items():
            ps = sorted(ps)
            if len(ps) < 2:
                continue
            lo, hi = math.log(ps[0]), math.log(ps[-1])
            draws = np.sort(np.exp(loc.uniform(lo, hi, size=len(ps))))
            rr.extend(draws[i + 1] / draws[i] for i in range(len(draws) - 1))
        rr = np.array([r for r in rr if RATIO_MIN <= r <= RATIO_MAX])
        counts.append(count_in(rr, W_S))
    counts = np.array(counts)
    return float(counts.mean()), float(counts.std())


def main():
    ratios_all = load_ratios(CSV_PATH)
    if len(ratios_all) == 0:
        raise SystemExit("No Kepler ratios -- run acquire_kepler_catalog.py first")
    ratios = ratios_all
    res, E, s = evaluate_windows(ratios)
    verdict, reason = decide(res)

    # K2/TESS cross-check (not part of verdict; report for the doc).
    k2 = load_ratios(K2CSV)
    k2_res = None
    if len(k2):
        k2_res, _, _ = evaluate_windows(k2)

    # Detection power (headline).
    power = detection_power(ratios)

    # Secondary null diagnostic (not part of the verdict): per-system
    # period-reshuffle null for the headline window.
    rn_mean, rn_std = reshuffle_null(CSV_PATH)
    rn_sigma = (res["S_phi32"]["N"] - rn_mean) / rn_std if rn_std else None

    # Basic sample stats
    from collections import Counter
    hosts = {}
    flds = ["host", "pl_in", "pl_out", "period_in_d", "period_out_d", "ratio"]
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(
                (r for r in f if not r.lstrip().startswith("#")),
                fieldnames=flds):
            if row["host"] == "host":
                continue
            hosts.setdefault(row["host"], 0)
            hosts[row["host"]] += 1
    mult = Counter(hosts.values())

    result = {
        "prediction": "Prediction 54 (exoplanet period-ratio phi-spacing)",
        "phi_32": PHI_32, "phi": PHI,
        "windows": {"S_phi32": list(W_S), "phi_belt": list(W_PHIB),
                    "convergents": {k: list(v) for k, v in CONV_WIN.items()},
                    "controls": {k: list(v) for k, v in CTRL_WIN.items()}},
        "sample": {
            "source": "NASA Exoplanet Archive ps (default_flag=1), "
                      "Kepler transit multi-planet",
            "n_systems": len(hosts),
            "n_ratios": int(len(ratios)),
            "multiplicity": {k: v for k, v in sorted(mult.items())},
        },
        "null": {"method": "folded-window (predictions 45/46)",
                 "sweep": [SWEEP_LO, SWEEP_HI], "half": HALF,
                 "mean": E, "std": s, "n_steps": 40001},
        "signal": res,
        "reshuffle_null_diag": {"mean": rn_mean, "std": rn_std,
                                "S_phi32_sigma": rn_sigma},
        "k2_tess_crosscheck": k2_res,
        "verdict": verdict,
        "reason": reason,
        "detection_power": power,
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RUNS_DIR, f"{run_id}_phi_ratios.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Kepler ratios: {len(ratios)}; systems {len(hosts)}; null E={E:.3f} s={s:.3f}")
    for k in ("S_phi32", "PhiB"):
        w = res[k]["window"]
        print(f"  {k:8s} {w}: N={res[k]['N']:3d}  sigma={res[k]['sigma']:+.2f}")
    print("  convergents:")
    for k, v in res["convergents"].items():
        print(f"    {k:9s} {v['window']}: N={v['N']:3d}  sigma={v['sigma']:+.2f}")
    print("  controls:")
    for k, v in res["controls"].items():
        print(f"    {k:9s} {v['window']}: N={v['N']:3d}  sigma={v['sigma']:+.2f}")
    print(f"\nVERDICT: {verdict}")
    print(f"  {reason}")
    print(f"\nrun JSON: {out}")


if __name__ == "__main__":
    main()
