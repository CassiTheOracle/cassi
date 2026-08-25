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
set of rational ratios. The headline $\varphi^{3/2}=2.06$ center is distinct
from the exact 2:1 resonance, but its finite window overlaps the registered
2:1 interval and the conventional wide-of-resonance pile-up. It is therefore
not a mechanism-specific discriminator. This is the Kepler/TESS catalog branch
beside the DSHARP disk-gap branch (Prediction 53).

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

REGISTERED DECISION TREE
------------------------
Ratios: adjacent P_out/P_in, ordered by period, within each host system,
restricted to [1.0, 3.0], and pooled across all Kepler multi-planet systems.

Windows (fixed half-width 0.05 in ratio space):
  S     (headline phi target) = phi^(3/2) +- 0.05  = [2.008, 2.108]
          (phi^(3/2) = 2.0582; the finite interval is confounded by the
           conventional wide-of-2:1 excess)
  PhiB  (phi attactor belt)    = [1.568, 1.668]  (phi=1.618 +- 0.05;
          captures the tight convergent cluster 8/5=1.6, 13/8=1.625,
          5/3=1.667 on its edge)
  Conv  (Fibonacci convergents, confounded by MMR) =
          [1.45,1.55] (3:2); [1.568,1.668] (phi belt); [1.95,2.05] (2:1)
  Ctrl  (non-phi, non-Fibonacci resonance controls; MUST NOT be elevated)
          [1.283,1.383] (4:3); [2.283,2.383] (7:3); [2.45,2.55] (5:2)

Null (folded-window, matching predictions 45/46—the null is the
distribution of ratio COUNTS over equal-width windows across the registered
ratio support, never a unit interval): sweep a window of the same half-width
0.05 across the full sampled ratio range c in [1.0, 3.0]; let the null mean E
and std s be the mean/std of these sliding-window counts. The standardized
window-density score z_win = (N_target - E)/s records where a target sits
relative to generic equal-width windows. This is a descriptive spatial
reference over one observed catalog, not a repeated-catalog sampling
distribution, frequentist significance, or mechanism-specific null.

Counts: N(S), N(PhiB), N(Conv_i), N(Ctrl_j).

Verdict (registered classifier threshold z_win >= 2.0; separation from the
non-phi controls requires each control to remain below 2.0):
  SUPPORTS       if z_win(S) >= 2.0 AND max_j z_win(Ctrl_j) < 2.0
  SUPPORTS NULL  if z_win(S) < 2.0 AND max_j z_win(Ctrl_j) >= 2.0
  INDETERMINATE  otherwise.

These labels are outputs of the registered descriptive classifier. They do
not by themselves establish statistical significance or identify a physical
mechanism.

Secondary record (not part of the verdict): the Fibonacci-convergent windows
3:2, phi-belt, and 2:1 counts and z_win values. The headline
phi^(3/2) window overlaps the registered 2:1 window from 2.0082 to 2.05 and
also occupies the conventionally known pile-up immediately wide of 2:1.
Accordingly, the headline window is not a clean discriminator between a phi
mechanism and ordinary near-resonant orbital dynamics.

Classifier sensitivity: plant an artificial phi^(3/2) excess—add K synthetic
adjacent ratios drawn from log-normal(log 2.058, scatter) to the observed
catalog (K = a few percent of the sample)—and measure the fraction of
realizations in which the decision tree returns SUPPORTS (200 realizations
per amplitude). This measures sensitivity to that injection model, not power
against a physical resonant-dynamics null.

All outcomes are reported; the verdict SHALL be reported verbatim
(SUPPORTS / SUPPORTS NULL / INDETERMINATE) with the numbers in the run JSON.
"""
from collections import Counter
import hashlib
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
W_S = (PHI_32 - HALF, PHI_32 + HALF)      # [2.0082, 2.1082] phi^(3/2)
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

SWEEP_LO, SWEEP_HI = 1.0, 3.0
RATIO_MIN, RATIO_MAX = SWEEP_LO, SWEEP_HI

MYDIR = os.path.dirname(os.path.abspath(__file__))
DATADIR = os.path.join(MYDIR, "data")
CSV_PATH = os.path.join(DATADIR, "parsed", "kepler_ratios.csv")
K2CSV = os.path.join(DATADIR, "parsed", "k2_tess_ratios.csv")
RAW_KEPLER = os.path.join(DATADIR, "raw", "kepler_ps.csv")
RAW_K2_TESS = os.path.join(DATADIR, "raw", "k2_tess_ps.csv")
HASH_MANIFEST = os.path.join(DATADIR, "raw", "sha256.txt")
RUNS_DIR = os.path.join(DATADIR, "runs")
os.makedirs(RUNS_DIR, exist_ok=True)

RNG_SEED = 20260813
FOLDED_SEED = 1
FOLDED_STEPS = 40001
POWER_SCATTER = 0.02
N_POWER = 200
RESHUFFLE_SEED = 7
N_RESHUFFLE = 1000


def sha256_file(path):
    """Return the SHA-256 digest of one acquisition or parsed-data file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        digest.update(f.read())
    return digest.hexdigest()


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


def catalog_stats(csv_path, n_in_support):
    """Return audited system, planet, ratio, and multiplicity counts."""
    hosts = {}
    flds = ["host", "pl_in", "pl_out", "period_in_d", "period_out_d", "ratio"]
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(
                (r for r in f if not r.lstrip().startswith("#")),
                fieldnames=flds):
            if row["host"] == "host":
                continue
            planets = hosts.setdefault(row["host"], set())
            planets.add(row["pl_in"])
            planets.add(row["pl_out"])
    multiplicity = Counter(len(planets) for planets in hosts.values())
    return {
        "n_systems": len(hosts),
        "n_planets": sum(len(planets) for planets in hosts.values()),
        "n_adjacent_ratios_total": sum(len(planets) - 1 for planets in hosts.values()),
        "n_ratios_in_support": int(n_in_support),
        "planet_multiplicity": {
            k: v for k, v in sorted(multiplicity.items())
        },
    }


def in_win(q, win):
    return win[0] <= q <= win[1]


def count_in(ratios, win):
    return int(np.sum((ratios >= win[0]) & (ratios <= win[1])))


def resonance_overlap_diagnostic(ratios):
    """Partition the headline window at the registered 2:1-window boundary."""
    overlap_hi = min(W_S[1], CONV_WIN["2:1"][1])
    n_signal = count_in(ratios, W_S)
    n_overlap = count_in(ratios, (W_S[0], overlap_hi))
    n_above = int(np.sum(
        (ratios > overlap_hi) & (ratios <= W_S[1])
    ))
    return {
        "signal_window": list(W_S),
        "registered_2to1_overlap": [W_S[0], overlap_hi],
        "overlap_width_fraction": (
            (overlap_hi - W_S[0]) / (W_S[1] - W_S[0])
        ),
        "n_signal": n_signal,
        "n_in_registered_2to1_overlap": n_overlap,
        "n_above_registered_2to1_window": n_above,
        "interpretation": (
            "diagnostic only; the conventional wide-of-2:1 pile-up also "
            "extends above the registered 2:1 window"
        ),
    }


def folded_null(
        ratios, half, lo, hi, n_steps=FOLDED_STEPS, seed=FOLDED_SEED):
    """Return an equal-width-window density reference over one catalog.

    The returned mean and standard deviation describe the variation in counts
    as the window center moves across [lo, hi]. They are not sampling moments
    from repeated catalogs and do not define a frequentist significance.
    """
    # Use the declared seed locally so repeated evaluations apply an identical
    # center grid without depending on call order.  Searchsorted evaluates all
    # window counts without allocating one boolean array per center.
    centers = np.random.default_rng(seed).uniform(lo, hi, size=n_steps)
    ordered = np.sort(np.asarray(ratios, dtype=float))
    right = np.searchsorted(ordered, centers + half, side="right")
    left = np.searchsorted(ordered, centers - half, side="left")
    counts = right - left
    return float(counts.mean()), float(counts.std()), centers, counts


def evaluate_windows(ratios):
    """Compute counts and descriptive window scores for every fixed window."""
    E, s, _, _ = folded_null(ratios, HALF, SWEEP_LO, SWEEP_HI)
    res = {"null": {"half": HALF, "sweep": [SWEEP_LO, SWEEP_HI],
                    "mean": E, "std": s,
                    "interpretation": "descriptive window-density reference"}}
    for name, win in [("S_phi32", W_S), ("PhiB", W_PHIB)]:
        n = count_in(ratios, win)
        res[name] = {"window": list(win), "N": n,
                     "window_score": float((n - E) / s) if s else None}
    res["convergents"] = {}
    for name, win in CONV_WIN.items():
        n = count_in(ratios, win)
        res["convergents"][name] = {
            "window": list(win), "N": n,
            "window_score": float((n - E) / s) if s else None,
        }
    res["controls"] = {}
    for name, win in CTRL_WIN.items():
        n = count_in(ratios, win)
        res["controls"][name] = {
            "window": list(win), "N": n,
            "window_score": float((n - E) / s) if s else None,
        }
    return res, E, s


def decide(res):
    """Apply the registered descriptive classifier."""
    score_s = res["S_phi32"]["window_score"]
    max_ctrl_score = max(
        v["window_score"] for v in res["controls"].values()
    )
    if score_s >= 2.0 and max_ctrl_score < 2.0:
        return "SUPPORTS", (
            f"S_phi32 window score {score_s:.2f} >= 2.0; "
            f"controls max {max_ctrl_score:.2f} < 2.0")
    if score_s < 2.0 and max_ctrl_score >= 2.0:
        return "SUPPORTS NULL", (
            f"S_phi32 window score {score_s:.2f} < 2.0; "
            f"a control window score is {max_ctrl_score:.2f}")
    return "INDETERMINATE", (
        f"S_phi32 window score {score_s:.2f}; "
        f"controls max {max_ctrl_score:.2f}")


def classifier_sensitivity(
        ratios, amplitudes=(0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20),
        scatter=POWER_SCATTER, n_real=N_POWER, seed=RNG_SEED):
    """Measure SUPPORTS frequency under one synthetic injection family.

    Recomputing the folded-window reference after each injection preserves the
    registered analysis transformation at the injected sample size.
    """
    rng = np.random.default_rng(seed)
    n0 = len(ratios)
    out = {}
    for amp in amplitudes:
        k = max(1, int(round(n0 * amp)))
        hits = 0
        for _ in range(n_real):
            extra = np.exp(rng.normal(math.log(PHI_32), scatter, size=k))
            rr = np.concatenate([ratios, extra])
            rr = rr[(rr >= RATIO_MIN) & (rr <= RATIO_MAX)]
            result, _, _ = evaluate_windows(rr)
            verdict, _ = decide(result)
            if verdict == "SUPPORTS":
                hits += 1
        out[f"amp_{amp}"] = hits / n_real
    return out


def reshuffle_null(
        csv_path, n_real=N_RESHUFFLE, seed=RESHUFFLE_SEED):
    """Secondary null (diagnostic only, not part of the registered verdict).

    Preserve each system's planet multiplicity and exact observed period span,
    hold the two endpoints fixed, draw any interior periods log-uniformly, and
    re-form adjacent ratios. Two-planet systems are unchanged because their
    multiplicity and span leave no interior degree of freedom. Returns the
    mean/std headline-window count.
    """
    per = {}
    flds = ["host", "pl_in", "pl_out", "period_in_d", "period_out_d", "ratio"]
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(
                (r for r in f if not r.lstrip().startswith("#")),
                fieldnames=flds):
            if row["host"] == "host":
                continue
            try:
                p_in = float(row["period_in_d"])
                p_out = float(row["period_out_d"])
            except (TypeError, ValueError):
                continue
            planets = per.setdefault(row["host"], {})
            planets[row["pl_in"]] = p_in
            planets[row["pl_out"]] = p_out
    loc = np.random.default_rng(seed)
    counts = []
    for _ in range(n_real):
        rr = []
        for planets in per.values():
            ps = sorted(planets.values())
            lo, hi = math.log(ps[0]), math.log(ps[-1])
            interior = np.sort(loc.uniform(lo, hi, size=max(0, len(ps) - 2)))
            log_periods = np.concatenate(([lo], interior, [hi]))
            rr.extend(
                math.exp(log_periods[i + 1] - log_periods[i])
                for i in range(len(log_periods) - 1)
            )
        rr = np.array([r for r in rr if RATIO_MIN <= r <= RATIO_MAX])
        counts.append(count_in(rr, W_S))
    counts = np.array(counts)
    return float(counts.mean()), float(counts.std())


def main():
    ratios = load_ratios(CSV_PATH)
    if len(ratios) == 0:
        raise SystemExit("No Kepler ratios—run acquire_kepler_catalog.py first")
    res, E, s = evaluate_windows(ratios)
    verdict, reason = decide(res)

    # K2/TESS cross-check (not part of verdict; report for the doc).
    k2 = load_ratios(K2CSV)
    k2_res = None
    if len(k2):
        k2_res, _, _ = evaluate_windows(k2)
    primary_stats = catalog_stats(CSV_PATH, len(ratios))
    k2_stats = catalog_stats(K2CSV, len(k2)) if len(k2) else None

    # Sensitivity of the descriptive classifier to the declared injection.
    sensitivity = classifier_sensitivity(ratios)

    # Secondary null diagnostic (not part of the verdict): per-system
    # period-reshuffle null for the headline window.
    rn_mean, rn_std = reshuffle_null(CSV_PATH)
    rn_z = (res["S_phi32"]["N"] - rn_mean) / rn_std if rn_std else None


    result = {
        "prediction": "Prediction 54 (exoplanet period-ratio phi-spacing)",
        "phi_32": PHI_32, "phi": PHI,
        "windows": {"S_phi32": list(W_S), "phi_belt": list(W_PHIB),
                    "convergents": {k: list(v) for k, v in CONV_WIN.items()},
                    "controls": {k: list(v) for k, v in CTRL_WIN.items()}},
        "sample": {
            "source": "NASA Exoplanet Archive ps "
                      "(soltype='Published Confirmed', default_flag=1), "
                      "Kepler transit multi-planet",
            "support": [RATIO_MIN, RATIO_MAX],
            **primary_stats,
        },
        "data_receipt": {
            "raw_kepler_sha256": sha256_file(RAW_KEPLER),
            "parsed_kepler_sha256": sha256_file(CSV_PATH),
            "raw_k2_tess_sha256": sha256_file(RAW_K2_TESS),
            "parsed_k2_tess_sha256": sha256_file(K2CSV),
            "acquisition_manifest_sha256": sha256_file(HASH_MANIFEST),
        },
        "null": {"method": "folded-window density reference (descriptive)",
                 "sweep": [SWEEP_LO, SWEEP_HI], "half": HALF,
                 "mean": E, "std": s, "n_steps": FOLDED_STEPS,
                 "seed": FOLDED_SEED,
                 "boundary_rule": "centers span the full support, so edge "
                                  "windows are truncated"},
        "signal": res,
        "resonance_overlap_diagnostic": resonance_overlap_diagnostic(ratios),
        "reshuffle_null_diag": {
            "method": "fixed endpoints; log-uniform interior periods",
            "mean": rn_mean,
            "std": rn_std,
            "S_phi32_standardized_offset": rn_z,
            "seed": RESHUFFLE_SEED,
            "n_realizations": N_RESHUFFLE,
            "unchanged_two_planet_systems":
                primary_stats["planet_multiplicity"].get("2", 0),
        },
        "k2_tess_crosscheck": {
            "sample": k2_stats,
            "signal": k2_res,
            "resonance_overlap_diagnostic": resonance_overlap_diagnostic(k2),
        } if k2_res is not None else None,
        "verdict": verdict,
        "reason": reason,
        "classifier_sensitivity": {
            "model": "added log-normal ratios centered on phi^(3/2)",
            "log_scatter": POWER_SCATTER,
            "rng_seed": RNG_SEED,
            "n_realizations_per_amplitude": N_POWER,
            "rates": sensitivity,
        },
        "scope": (
            "descriptive registered classifier; no mechanism-level inference"
        ),
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RUNS_DIR, f"{run_id}_phi_ratios.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Kepler ratios: {len(ratios)}; systems {primary_stats['n_systems']}; "
          f"null E={E:.3f} s={s:.3f}")
    for k in ("S_phi32", "PhiB"):
        w = res[k]["window"]
        print(f"  {k:8s} {w}: N={res[k]['N']:3d}  "
              f"score={res[k]['window_score']:+.2f}")
    print("  convergents:")
    for k, v in res["convergents"].items():
        print(f"    {k:9s} {v['window']}: N={v['N']:3d}  "
              f"score={v['window_score']:+.2f}")
    print("  controls:")
    for k, v in res["controls"].items():
        print(f"    {k:9s} {v['window']}: N={v['N']:3d}  "
              f"score={v['window_score']:+.2f}")
    print(f"\nVERDICT: {verdict}")
    print(f"  {reason}")
    print(f"\nrun JSON: {out}")


if __name__ == "__main__":
    main()
