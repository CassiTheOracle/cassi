#!/usr/bin/env python3
"""ALMA DSHARP disk-gap phi-ring-ladder ratio test (Prediction 53).

Run from the repo root:
    python experiments/dsharp_phi_gaps/stack_phi_gaps.py

WHAT THIS TESTS
---------------
The Cassi ring ladder (fundations/bubble-edge-geometry.md sec. 3.1) reads a
bubble shell of radius R as carrying matter rings at r_k = R * phi^-k with
void troughs at R * phi^-(k+1/2); successive matter-ring ratio phi^-1 =
0.6180, null interleaved ratio phi^-1/2 = 0.7862. In a protoplanetary disk
the condensation wake plays the bubble shell: the density nodes (the future
disk gaps) should sit at phi-spaced radii. This script tests the pooled
successive-gap radial ratio distribution of the ALMA DSHARP survey against
the signal window centered on phi^-1 = 0.6180 and the null window centered
on phi^-1/2 = 0.7862.

DATA
----
Gap radial positions come from the DSHARP annular-substructure table
(tab:ringpositions) of Huang et al. (2018), arXiv:1812.04041 (the survey's
substructure paper; sample per Andrews et al. 2018, arXiv:1812.04040).
The 18 single-disk DSHARP systems are used; the appended comparison disks
TW Hya and HL Tau (explicitly not part of the 18-disk sample) are excluded
from the primary pool and reported separately. Data file:
experiments/dsharp_phi_gaps/data/parsed/dsharp_gaps.csv (machine-parsed
from the paper's LaTeX source, hashes in data/raw/sha256.txt).

PRE-REGISTERED DECISION TREE  (written before any analysis run below)
----------------------------------------------------------------------
For each disk, its detected gaps are sorted by radius (ascending) and the
successive (inner/outer) radial ratios q = r_k / r_k+1  (< 1) are formed for
each adjacent pair; these are pooled across all 18 disks. (Gaps = the
survey's DARK "D" annular substructures.)

Windows (fixed):
  W1  (signal) = [0.6180 - 0.08, 0.6180 + 0.08] = [0.538, 0.698]
  W2  (null)   = [0.7862 - 0.05, 0.7862 + 0.05] = [0.736, 0.836]

Null (uniform-in-log-radius): for each disk, draw the SAME number of gap
positions as that disk's observed count, independently from a log-uniform
distribution over that disk's observed gap radial span [r_min, r_max];
form successive ratios exactly as for the data; pool. 1000 realizations.
Under this null, let E1 = mean count in W1, E2 = mean count in W2, and
s1, s2 = the empirical standard deviations (Poisson-like). The comparison is
a distribution, never a single draw.

Counts: N1 = number of pooled observed successive-gap ratios in W1,
       N2 = number pooled observed ratios in W2.

Verdict (>= 2 sigma, i.e. >= 2.0-sigma above null mean; separation from the
other window means the other window is NOT elevated >= 2.0 sigma):
  SUPPORTS       if N1 >= E1 + 2.0*s1   AND   N2 <  E2 + 2.0*s2
  SUPPORTS NULL  if N2 >= E2 + 2.0*s2   AND   N1 <  E1 + 2.0*s1
  INDETERMINATE  otherwise (including both elevated or neither).

Per-disk verdicts are also reported (each disk with >= 2 gaps: SUPPORTED /
NULL / INDETERMINATE on its own ratios vs the two windows), but the pooled
verdict is the headline (the test is statistical across disks, not
per-disk: planet-carving in individual disks is the standard alternative
explanation, and a thin multi-gap disk is a single realisation).

Detected-signal power: plant a synthetic phi-ladder of gaps (successive
ratio phi^-1 = 0.6180, outermost at each disk's observed outermost gap) at
known placement purity, add varying scatter (log-normal sigma from 0 to
0.2 in ln r), and measure the fraction of realizations in which the
decision tree returns SUPPORTS (200 realizations per step). This calibrates
how a truely phi-laddered disk-gap sample would be scored.

All outcomes are honest and reported.
"""
import csv
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1.0 / PHI          # 0.6180
PHI_HALF = PHI ** -0.5       # 0.7862

W1 = (PHI_INV - 0.08, PHI_INV + 0.08)   # [0.538, 0.698]
W2 = (PHI_HALF - 0.05, PHI_HALF + 0.05)  # [0.736, 0.836]

DSHARP_18 = [
    "AS 209", "DoAr 25", "DoAr 33", "Elias 20", "Elias 24", "Elias 27",
    "GW Lup", "HD 142666", "HD 143006", "HD 163296", "IM Lup", "MY Lup",
    "RU Lup", "SR 4", "Sz 114", "Sz 129", "WaOph 6", "WSB 52",
]

MYDIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(MYDIR, "data", "parsed", "dsharp_gaps.csv")
RUNS_DIR = os.path.join(MYDIR, "data", "runs")
os.makedirs(RUNS_DIR, exist_ok=True)

RNG = np.random.default_rng(20260813)
N_NULL = 1000
N_POWER = 200


def load_gaps(include_approx=True):
    """Return {source: sorted list of (r0_au, is_approx)} for DSHARP-18."""
    per = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(
            (row for row in f if not row.lstrip().startswith("#")),
            fieldnames=["source", "feature", "r0_au", "is_approx", "method", "unc"])
        for row in reader:
            src = row["source"].strip()
            if src not in DSHARP_18:
                continue
            val = float(row["r0_au"])
            approx = int(row["is_approx"]) == 1
            if not include_approx and approx:
                continue
            per.setdefault(src, []).append((val, approx))
    # sort each disk's gaps by radius ascending
    for src in per:
        per[src].sort()
    return per


def successive_ratios(gaps):
    """Return list of inner/outer successive radial ratios (< 1)."""
    radii = [g[0] for g in gaps]
    radii.sort()
    return [radii[i] / radii[i + 1] for i in range(len(radii) - 1)]


def null_ratios(gaps, rng):
    """One null realization: log-uniform gap positions per disk over each
    disk's observed radial span, return pooled successive ratios."""
    pooled = []
    for src, gg in gaps.items():
        radii = [g[0] for g in gg]
        k = len(radii)
        if k < 2:
            continue
        lo, hi = min(radii), max(radii)
        if lo <= 0 or hi <= lo:
            continue
        draws = rng.uniform(math.log(lo), math.log(hi), size=k)
        draws = np.sort(np.exp(draws))
        pooled.extend(draws[i] / draws[i + 1] for i in range(k - 1))
    return pooled


def in_window(q, win):
    return win[0] <= q <= win[1]


def main():
    gaps = load_gaps(include_approx=True)
    total_gaps = sum(len(v) for v in gaps.values())
    disks_with_pairs = {s: v for s, v in gaps.items() if len(v) >= 2}

    # Observed pooled successive ratios.
    pooled = []
    per_disk_ratios = {}
    for src in sorted(gaps):
        r = successive_ratios(gaps[src])
        if r:
            per_disk_ratios[src] = r
            pooled.extend(r)
    pooled = sorted(pooled)

    N1 = sum(1 for q in pooled if in_window(q, W1))
    N2 = sum(1 for q in pooled if in_window(q, W2))

    # Null distribution.
    null_N1 = []
    null_N2 = []
    for _ in range(N_NULL):
        nr = null_ratios(gaps, RNG)
        null_N1.append(sum(1 for q in nr if in_window(q, W1)))
        null_N2.append(sum(1 for q in nr if in_window(q, W2)))
    null_N1 = np.array(null_N1)
    null_N2 = np.array(null_N2)
    E1, s1 = null_N1.mean(), null_N1.std()
    E2, s2 = null_N2.mean(), null_N2.std()

    sup = (N1 >= E1 + 2.0 * s1) and (N2 < E2 + 2.0 * s2)
    supn = (N2 >= E2 + 2.0 * s2) and (N1 < E1 + 2.0 * s1)
    if sup:
        verdict = "SUPPORTS"
    elif supn:
        verdict = "SUPPORTS NULL"
    else:
        verdict = "INDETERMINATE"

    # Per-disk verdicts.
    disk_verdicts = {}
    for src, rr in per_disk_ratios.items():
        n1 = sum(1 for q in rr if in_window(q, W1))
        n2 = sum(1 for q in rr if in_window(q, W2))
        # per-disk: classify vs the two windows without a formal sigma.
        if n1 > 0 and n2 == 0:
            dv = "SUPPORTED"
        elif n2 > 0 and n1 == 0:
            dv = "NULL"
        else:
            dv = "INDETERMINATE"
        disk_verdicts[src] = {"ratios": [round(q, 3) for q in rr], "n1": n1,
                              "n2": n2, "verdict": dv}

    # Planted-signal detection power: synthetic phi-ladder of gaps per disk.
    power = {}
    for scatter in (0.0, 0.05, 0.10, 0.15, 0.20):
        hits = 0
        for _ in range(N_POWER):
            planted = {src: [] for src in gaps}
            for src, gg in gaps.items():
                radii = sorted(g[0] for g in gg)
                k = len(radii)
                if k == 0:
                    continue
                outer = radii[-1]  # anchor at the disk's outermost gap
                # phi-ladder inward from outer: r_j = outer * phi^-j ...
                # successive ratio phi^-1 exactly, with log-normal scatter.
                lg = math.log(outer)
                pos = [lg]
                for j in range(1, k):
                    lg = lg - math.log(PHI) + RNG.normal(0, scatter)
                    pos.append(lg)
                planted[src] = [(math.exp(p), False) for p in pos]
            pcr = []
            for src in planted:
                pcr.extend(successive_ratios(planted[src]))
            pn1 = sum(1 for q in pcr if in_window(q, W1))
            pn2 = sum(1 for q in pcr if in_window(q, W2))
            psup = (pn1 >= E1 + 2.0 * s1) and (pn2 < E2 + 2.0 * s2)
            psupn = (pn2 >= E2 + 2.0 * s2) and (pn1 < E1 + 2.0 * s1)
            if psup and not psupn:
                hits += 1
        power[scatter] = hits / N_POWER

    # Sensitivity: exclude approximate (visual/~) gaps.
    gaps_ex = load_gaps(include_approx=False)
    pooled_ex = []
    for src in sorted(gaps_ex):
        pooled_ex.extend(successive_ratios(gaps_ex[src]))
    N1_ex = sum(1 for q in pooled_ex if in_window(q, W1))
    N2_ex = sum(1 for q in pooled_ex if in_window(q, W2))
    ne = len(pooled_ex)
    # Sensitivity's own null (same log-uniform construction on the
    # approx-excluded gaps, independent realizations).
    null_e1, null_e2 = [], []
    for _ in range(N_NULL):
        nr = null_ratios(gaps_ex, RNG)
        null_e1.append(sum(1 for q in nr if in_window(q, W1)))
        null_e2.append(sum(1 for q in nr if in_window(q, W2)))
    null_e1 = np.array(null_e1); null_e2 = np.array(null_e2)
    E1x, s1x = null_e1.mean(), null_e1.std()
    E2x, s2x = null_e2.mean(), null_e2.std()

    result = {
        "phi_inv": PHI_INV, "phi_half": PHI_HALF,
        "windows": {"W1_signal": list(W1), "W2_null": list(W2)},
        "n_disks_18": len(gaps), "total_gaps": total_gaps,
        "disks_with_gt1_gap": len(disks_with_pairs),
        "n_pooled_successive_ratios": len(pooled),
        "pooled_ratios": pooled,
        "N1_in_W1": N1, "N2_in_W2": N2,
        "null": {"n_realizations": N_NULL, "E1_W1": float(E1),
                 "s1_W1": float(s1), "E2_W2": float(E2), "s2_W2": float(s2),
                 "sig1": float((N1 - E1) / s1) if s1 else None,
                 "sig2": float((N2 - E2) / s2) if s2 else None},
        "per_disk": disk_verdicts,
        "verdict": verdict,
        "detection_power": {str(k): v for k, v in power.items()},
        "sensitivity_excl_approx": {
            "n_pooled": ne, "N1_in_W1": N1_ex, "N2_in_W2": N2_ex,
            "null_E1_W1": float(E1x), "null_s1_W1": float(s1x),
            "null_E2_W2": float(E2x), "null_s2_W2": float(s2x),
            "sig1": float((N1_ex - E1x) / s1x) if s1x else None,
            "sig2": float((N2_ex - E2x) / s2x) if s2x else None},
    }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RUNS_DIR, f"{run_id}_gaps.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items()
                      if k != "pooled_ratios"}, indent=2))
    print(f"\nrun JSON: {out}")
    print("\nFull pooled-ratio list:")
    print("  " + ", ".join(f"{q:.3f}" for q in pooled))


if __name__ == "__main__":
    main()
