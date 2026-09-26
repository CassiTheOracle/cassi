#!/usr/bin/env python3
"""
verify_twofluid_hcompletion.py -- harness gates for the wave-13 hcompletion probe.

Per twofluid_hcompletion_prereg.md S3. Runs (deterministic, matrix-free):
  G1 arm-A anchor:  anti-phase SHO period within wave-5's +-30% dispersion band of the k=0
                    prediction (engine form reproduces wave-5 g2).
  G2 determinism:   arm A and arm B 100-step double runs bitwise identical.
  G3 no-NaN:        both arms finite over a short run.
  G4 null-mode:     EY=phi*EI IC -> d = EY-phi*EI stays < 1e-12 in BOTH arms.
  G5 frequency-ratio: f_B/f_A in [1.141, 1.211] (1.176 +-3%).
  G6 energy-drift (REPORTED): drift_A and drift_B; the drift_B < 0.1*drift_A criterion is the
                    probe's decision tree, not a gate.
Prints ALL CHECKS PASSED on success.

Run from repo root:  python research/helix_solver/verify_twofluid_hcompletion.py
"""

import numpy as np

from two_fluid_shell import TwoFluidLine, make_ic, make_reference
import twofluid_hcompletion_probe as hp

results: list[tuple[str, bool, str]] = []


def gate(name, ok, msg):
    results.append((name, bool(ok), str(msg)))
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {msg}")


def run_n_steps(cls, n):
    g = cls(make_reference(hp.SPAN, hp.K))
    ey, ei = make_ic(g.z)
    vey = vei = np.zeros_like(ey)
    for _ in range(n):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
    return ey, ei


def main() -> None:
    # G1: arm-A anchor (reproduces wave-5 g2)
    print("== G1: arm-A anti-phase SHO period reproduces wave-5 ==")
    per, pred = hp.anti_phase_period(TwoFluidLine)
    ok = abs(per - pred) < 0.30 * pred
    gate("G1_armA_anchor", ok, f"period={per:.1f} steps vs k=0 prediction {pred:.1f} (+-30% band)")

    # G2: determinism
    print("== G2: determinism (arm A + arm B 100-step double run) ==")
    a1 = run_n_steps(TwoFluidLine, 100)
    a2 = run_n_steps(TwoFluidLine, 100)
    b1 = run_n_steps(hp.TwoFluidLineH, 100)
    b2 = run_n_steps(hp.TwoFluidLineH, 100)
    same = (np.array_equal(a1[0], a2[0]) and np.array_equal(a1[1], a2[1])
            and np.array_equal(b1[0], b2[0]) and np.array_equal(b1[1], b2[1]))
    gate("G2_determinism", same, "arm A and arm B 100-step double runs bitwise identical")

    # G3: no-NaN
    print("== G3: arms finite ==")
    fin_a = all(np.all(np.isfinite(x)) for x in a1)
    fin_b = all(np.all(np.isfinite(x)) for x in b1)
    gate("G3_no_nan", fin_a and fin_b, "arm A and arm B @100 finite")

    # G4: null-mode stationarity
    print("== G4: null-mode stationarity (EY=phi*EI -> d stays 0) ==")
    da = hp.null_mode_max_d(TwoFluidLine)
    db = hp.null_mode_max_d(hp.TwoFluidLineH)
    gate("G4_null_mode", da < 1e-12 and db < 1e-12, f"max|d| A={da:.2e}, B={db:.2e} (<1e-12)")

    # G5: frequency ratio
    print("== G5: frequency ratio f_B/f_A ==")
    f_a = hp.measure_frequency(TwoFluidLine)
    f_b = hp.measure_frequency(hp.TwoFluidLineH)
    ratio = f_b / f_a
    ok = hp.FREQ_RATIO_LO <= ratio <= hp.FREQ_RATIO_HI
    gate("G5_freq_ratio", ok,
         f"f_A={f_a:.4f} Hz, f_B={f_b:.4f} Hz, ratio={ratio:.4f} "
         f"(pred {hp.FREQ_RATIO_PRED:.4f}, band [{hp.FREQ_RATIO_LO:.4f},{hp.FREQ_RATIO_HI:.4f}])")

    # G6: energy drift REPORTED
    print("== G6: energy drift (REPORTED) ==")
    drift_a = hp.energy_drift(TwoFluidLine)
    drift_b = hp.energy_drift(hp.TwoFluidLineH)
    print(f"  drift_A = {drift_a:.3e}, drift_B = {drift_b:.3e}, ratio B/A = {drift_b/max(drift_a,1e-12):.3e}")
    print(f"  (criterion drift_B < 0.1*drift_A evaluated in the probe decision tree)")

    print()
    all_pass = all(ok for _, ok, _ in results)
    print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
