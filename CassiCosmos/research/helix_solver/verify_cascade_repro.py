#!/usr/bin/env python3
"""
verify_cascade_repro.py — wave-11 harness gates.

Imports the probe reimplementation and checks, in order:
  G1  Arm-0 reproduction: faithful port reproduces the oblate TRANSIENT at step 1100
      (coh sigma_x/z in [2.0,3.0] ~ 2.510) AND the energy (r-neutral) extents stay round
      (sigma_x/z < 1.1). This validates the harness against the source's known signature.
  G2  Determinism: two identical 100-step evolutions bitwise identical; and the Arm-4
      seed-42 IC perturbation reproduced bitwise across two builds.
  G3  No-NaN: short Arm-2 and Arm-4 evolutions finite.
  G4  Reconcile: the recorded final snapshot step equals the requested step.

Prints ALL CHECKS PASSED on success. Run from CassiCosmos/:
  python research/helix_solver/verify_cascade_repro.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cascade_repro_probe as crp


def gate(name, cond, detail):
    status = "PASS" if cond else "FAIL"
    print(f"GATE {name}: {status}  {detail}")
    return cond


def g1_reproduction():
    X, Y, Z, th3, GN, GS = crp.make_grid()
    EY, EI, VY, VI, m0 = crp.init_fields(X, Y, Z, th3, GN, GS, crp.PHI)
    snaps = crp.evolve(EY, EI, VY, VI, m0, X, Y, Z, crp.RECORD_STEP)
    r = crp._ratios(snaps[-1])
    ok_xz = crp.REPRO_XZ_LO <= r["coh_xz"] <= crp.REPRO_XZ_HI
    ok_xy = crp.REPRO_XY_LO <= r["coh_xy"] <= crp.REPRO_XY_HI
    ok_en = r["en_xz"] < crp.ENERGY_ROUND
    detail = (f"@1100 coh sigma_x/y={r['coh_xy']:.3f} (in [{crp.REPRO_XY_LO},{crp.REPRO_XY_HI}]) "
              f"coh sigma_x/z={r['coh_xz']:.3f} (in [{crp.REPRO_XZ_LO},{crp.REPRO_XZ_HI}]) "
              f"energy sigma_x/z={r['en_xz']:.3f} (round <{crp.ENERGY_ROUND})")
    return gate("G1_reproduction", ok_xz and ok_xy and ok_en, detail)


def run_n_steps(transverse_phi_factor, noise_seed, n_steps):
    X, Y, Z, th3, GN, GS = crp.make_grid()
    EY, EI, VY, VI, m0 = crp.init_fields(X, Y, Z, th3, GN, GS,
                                         transverse_phi_factor, noise_seed=noise_seed)
    for _ in range(n_steps):
        EY, EI, VY, VI = crp.rk4_step(EY, EI, VY, VI, m0)
    return EY, EI, VY, VI


def g2_determinism():
    A = run_n_steps(crp.PHI, None, 100)
    B = run_n_steps(crp.PHI, None, 100)
    same_a = all(np.array_equal(a, b) for a, b in zip(A, B))
    C = run_n_steps(crp.PHI, 42, 100)
    D = run_n_steps(crp.PHI, 42, 100)
    same_b = all(np.array_equal(a, b) for a, b in zip(C, D))
    detail = (f"faithful 100-step {'' if same_a else 'NOT '}identical; "
              f"seed-42 100-step {'' if same_b else 'NOT '}identical")
    return gate("G2_determinism", same_a and same_b, detail)


def g3_no_nan():
    X, Y, Z, th3, GN, GS = crp.make_grid()
    fin = True
    arms = [("arm2", crp.init_fields(X, Y, Z, th3, GN, GS, 1.0, noise_seed=None)),
            ("arm4", crp.init_fields(X, Y, Z, th3, GN, GS, crp.PHI, noise_seed=42))]
    for name, (EY, EI, VY, VI, m0) in arms:
        for _ in range(100):
            EY, EI, VY, VI = crp.rk4_step(EY, EI, VY, VI, m0)
        fin &= all(np.all(np.isfinite(a)) for a in (EY, EI, VY, VI))
    return gate("G3_no_nan", fin, "arm2@100 finite, arm4@100 finite")


def g4_reconcile():
    X, Y, Z, th3, GN, GS = crp.make_grid()
    EY, EI, VY, VI, m0 = crp.init_fields(X, Y, Z, th3, GN, GS, crp.PHI)
    snaps = crp.evolve(EY, EI, VY, VI, m0, X, Y, Z, 350)
    last_step = snaps[-1][0]
    return gate("G4_reconcile", last_step == 350, f"evolve(350) final recorded step = {last_step}")


if __name__ == "__main__":
    print("== cascade-repro verify gates ==")
    results = [g1_reproduction(), g2_determinism(), g3_no_nan(), g4_reconcile()]
    print()
    if all(results):
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
        sys.exit(1)
