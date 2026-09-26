#!/usr/bin/env python3
"""Pump-curve scaling of the churning-gate amplitude scan.

Analysis for §9.1 of `consciousness/neurodivergence-as-gate-configuration.md`:
how much imbalance epsilon a recurring in-channel Fire drive retains at
the churning site (low-q mixed-channel init, seed 42) as a function of
drive amplitude, at t = 4. Reads the canonical fresh-solver fine scan
and the earlier shared-solver scan, fits the pump branch (amp >= 0.10)
in log-log space, characterizes the quench branch (amp <= 0.06), and
locates the crossover (ref-floor crossing, eps_rel = 1.0 crossing,
pump onset at eps_rel = 1.3).

Data:
  runs/20260804_025306_churning_quench/results.json  (canonical: fresh solver per arm)
  runs/20260804_020249_churning_amp/results.json     (earlier: shared solver)

Paths are hardcoded rather than globbed: the runs/ JSONs are
gitignored and timestamped per launch, so a glob would silently pick
up a different run if the experiment is ever re-run. Update the paths
if a new canonical run supersedes these.

Usage: python two-fluid/churning_pump_scaling.py
Output: printed fits, exponents, residuals, crossover, synthesis table.
"""

import json

import numpy as np

CANON = "runs/20260804_025306_churning_quench/results.json"
EARLY = "runs/20260804_020249_churning_amp/results.json"

PUMP_AMPS = [0.10, 0.15, 0.20, 0.30]
QUENCH_FIT_AMPS = [0.05, 0.06]
REF_FLOOR = 0.8698906426469907   # undriven ref4 eps_rel at t = 4 (canonical run)
PUMP_CRIT = 1.3                  # pump criterion, eps_rel >= 1.3


def load_canonical(path):
    """Sorted (amps, eps_rel) of the fine scan plus the ref floor."""
    with open(path) as f:
        data = json.load(f)
    rows = data["meta"]["fine_scan"]["rows"]
    amps = np.array([float(k) for k in rows])
    eps = np.array([rows[k]["eps_rel"] for k in rows])
    order = np.argsort(amps)
    return amps[order], eps[order], data["ref4"]["t4"]["eps_rel"]


def load_early(path):
    """eps_rel by amp from the earlier shared-solver scan."""
    with open(path) as f:
        data = json.load(f)
    return {float(k): v["eps_rel"] for k, v in data["in_channel"].items()}


def loglog_fit(amps, eps):
    """OLS on ln eps = ln a + b ln amp; returns b, s_b, R^2, residuals."""
    x = np.log(amps)
    y = np.log(eps)
    b, ln_a = np.polyfit(x, y, 1)
    y_hat = b * x + ln_a
    resid = y - y_hat
    dof = len(x) - 2
    s_b = np.sqrt(resid @ resid / dof / np.sum((x - x.mean()) ** 2))
    r2 = 1.0 - (resid @ resid) / np.sum((y - y.mean()) ** 2)
    return b, s_b, r2, resid


def lin_fit(amps, eps):
    m, c = np.polyfit(amps, eps, 1)
    return m, c


def lin_interp_cross(amps, eps, target):
    """Linear interpolation of the amp where eps crosses `target`."""
    for i in range(len(amps) - 1):
        if (eps[i] - target) * (eps[i + 1] - target) <= 0:
            t = (target - eps[i]) / (eps[i + 1] - eps[i])
            return amps[i] + t * (amps[i + 1] - amps[i])
    return None


def main():
    amps, eps, floor = load_canonical(CANON)
    early = load_early(EARLY)

    print("=== Canonical fine scan "
          f"({CANON}) ===")
    print(f"ref floor (undriven, t = 4): eps_rel = {floor:.4f}\n")
    print(f"{'amp':>6s} {'eps_rel':>9s}")
    for a, e in zip(amps, eps):
        print(f"{a:6.3f} {e:9.3f}")

    print("\n=== Reproduction vs earlier shared-solver scan (<= 2% expected) ===")
    ok = True
    for a in amps:
        if a in early:
            d = abs(eps[amps == a][0] - early[a]) / eps[amps == a][0] * 100.0
            flag = "ok" if d <= 2.0 else "*** OUT OF TOLERANCE ***"
            ok = ok and d <= 2.0
            print(f"amp {a:6.3f}: canon {eps[amps == a][0]:7.4f} "
                  f"early {early[a]:7.4f}  |diff| {d:5.2f}%  {flag}")
    print("all shared amps within 2%: " + ("yes" if ok else "NO"))

    # ---- 1. pump branch ----
    pa = np.array([a for a in PUMP_AMPS])
    pe = np.array([eps[amps == a][0] for a in PUMP_AMPS])
    b, s_b, r2, resid = loglog_fit(pa, pe)
    print("\n=== 1. Pump branch (amp >= 0.10), log-log fit ===")
    print(f"fit: eps_rel = a * amp^b   (OLS on ln eps vs ln amp, n = {len(pa)})")
    print(f"b = {b:.4f} +/- {s_b:.4f}")
    print(f"R^2 = {r2:.4f}")
    print(f"a = {np.exp(np.mean(np.log(pe)) - b * np.mean(np.log(pa))):.1f}")
    print("residuals (ln eps, obs - fit):")
    for a, r in zip(pa, resid):
        print(f"  amp {a:5.2f}: {r:+.4f}")
    print(f"|b - 2| = {abs(b - 2.0):.3f}  ({abs(b - 2.0) / s_b:.1f} sigma)  "
          f"-> b = 2 (energy-driven, eps ~ amp^2) excluded"
          if abs(b - 2.0) / s_b > 3 else "b = 2 within ~3 sigma")
    print(f"|b - 1| = {abs(b - 1.0):.3f}  ({abs(b - 1.0) / s_b:.1f} sigma)  "
          f"-> b = 1 (linear) excluded"
          if abs(b - 1.0) / s_b > 3 else "b = 1 within ~3 sigma")
    closer = 1 if abs(b - 1.0) < abs(b - 2.0) else 2
    print(f"closer hypothesis: b = {closer} (by "
          f"{abs(abs(b - 1.0) - abs(b - 2.0)):.3f})")
    pair_b = np.log(pe[1:] / pe[:-1]) / np.log(pa[1:] / pa[:-1])
    print("pairwise exponents between consecutive amps:")
    for i in range(len(pa) - 1):
        print(f"  {pa[i]:5.2f} -> {pa[i + 1]:5.2f}: {pair_b[i]:.3f}")
    print("note: local exponent falls 1.59 -> 1.44 -> 1.31 and the "
          "residuals show a systematic - + + - pattern, so the power "
          "law is approximate, not clean.")

    # ---- 2. quench branch ----
    qa = np.array(QUENCH_FIT_AMPS)
    qe = np.array([eps[amps == a][0] for a in QUENCH_FIT_AMPS])
    m, c = lin_fit(qa, qe)
    print("\n=== 2. Quench branch (amp <= 0.06) ===")
    print(f"linear fit over amps {QUENCH_FIT_AMPS}: "
          f"eps_rel = {m:.2f} * amp {c:+.3f}")
    e0_25 = eps[amps == 0.025][0]
    e0_05 = eps[amps == 0.05][0]
    flat_slope = (e0_05 - e0_25) / 0.025
    extrap = m * 0.025 + c
    print(f"0.025 point: eps_rel = {e0_25:.3f}; flat segment 0.025->0.05 "
          f"slope = {flat_slope:.2f} per amp (nearly flat).")
    print(f"the {QUENCH_FIT_AMPS} line extrapolated to 0.025 would give "
          f"{extrap:.3f}, far below the observed {e0_25:.3f}: the branch "
          "is flat below ~0.05, then rising, not linear in amp.")
    print(f"quench depth vs floor {floor:.3f}: "
          f"{floor - e0_25:.3f} at 0.025 ({(floor - e0_25) / floor * 100:.0f}% "
          f"below floor), {floor - e0_05:.3f} at 0.05 "
          f"({(floor - e0_05) / floor * 100:.0f}% below floor)")

    # ---- 3. crossover ----
    a_floor = lin_interp_cross(amps, eps, floor)
    a_one = lin_interp_cross(amps, eps, 1.0)
    a_pump = lin_interp_cross(amps, eps, PUMP_CRIT)
    print("\n=== 3. Crossover (0.06-0.10) ===")
    print(f"ref-floor crossing (eps_rel = {floor:.3f}): amp ~ "
          f"{a_floor:.4f} (between 0.06 and 0.07)")
    print(f"no-net-effect crossing (eps_rel = 1.0): amp ~ {a_one:.4f} "
          "(between 0.07 and 0.08)")
    print(f"pump onset (eps_rel = {PUMP_CRIT}): amp ~ {a_pump:.4f} "
          "(between 0.08 and 0.09)")
    print(f"crossover width (ref-floor crossing -> pump onset): "
          f"{a_pump - a_floor:.4f} in amp "
          f"(flat-branch end ~0.05 -> pump onset: {a_pump - 0.05:.4f})")

    # ---- 4. synthesis ----
    print("\n=== 4. Synthesis ===")
    print(f"{'amp':>6s} {'eps_rel':>9s} {'branch':>12s}")
    for a, e in zip(amps, eps):
        if a <= 0.05:
            br = "quench (flat)"
        elif a < a_floor:
            br = "quench (rising)"
        elif a < a_pump:
            br = "crossover"
        else:
            br = "pump"
        print(f"{a:6.3f} {e:9.3f} {br:>12s}")
    print("\nQuench branch (~flat at 0.58-0.61, ~30% below the undriven "
          f"floor {floor:.3f}) up to amp ~0.05; crossover 0.05-0.084 "
          "(floor crossed at ~0.065, eps_rel = 1.0 at ~0.072, pump "
          f"criterion {PUMP_CRIT} at ~0.084); pump branch (amp >= 0.10) "
          f"approximated by eps_rel = a * amp^b with b = {b:.2f} +/- "
          f"{s_b:.2f} (R^2 = {r2:.3f}), but with decreasing local "
          "exponent (1.59 -> 1.44 -> 1.31) the scaling law is not "
          "clean: the curve is sub-quadratic, intermediate between "
          "linear and energy-driven, closer to linear.")


if __name__ == "__main__":
    main()
