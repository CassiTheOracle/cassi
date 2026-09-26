"""Measure what a rate-dependent read gate does to the mode bank's kernel family.

The pinned readout averages `chi` over the available scales, so a mode reads at the
same rate whatever symbol the bank gives it and the kernels differ only in where they
leave that shared curve. `FieldConfig.scale_read_taper` weights scale `s` of a mode by
`exp(taper * s * damping * dt)`, which reads each mode at the scales that resolve it.
This reports the two things that decide whether the bank family opens:

  * the kernel table -- the anchor-normalized readout of a single bin at several
    damping values, which shows what shape a bin can carry;
  * the shape rank and the multi-start floor -- how many independent shapes the 32
    bins span, and the best mean log-profile error any population of them reaches.

`train_field_bank.py` searches the rate grid as well; this holds the grid fixed so the
two readout variants are compared on the same bins.
"""

from __future__ import annotations

import argparse

import numpy as np
from scipy.optimize import minimize

from run_cassi_field_memory_study import FieldConfig
from train_field_bank import bin_kernels, load_target, rate_grid


def family_floor(kernels, target, window, starts, seed=20260921):
    """Best anchor-relative mean log-profile error over the simplex of populations."""
    anchor = int(np.argmax(window))
    reference = (target / target[anchor])[window]
    active = kernels[:, window]
    anchor_energy = kernels[:, anchor]

    def objective(counts):
        counts = np.maximum(counts, 0.0)
        total = counts.sum()
        if total <= 0.0:
            return 1.0e6
        counts = counts / total
        profile = np.sqrt(np.maximum(counts @ active, 1.0e-30))
        root = np.sqrt(max(float(counts @ anchor_energy), 1.0e-30))
        return float(np.mean(np.abs(np.log(np.maximum(profile / root, 1.0e-9))
                                    - np.log(np.maximum(reference, 1.0e-9)))))

    rng = np.random.default_rng(seed)
    results = [minimize(objective, s, method="SLSQP",
                        bounds=[(0.0, 1.0)] * kernels.shape[0],
                        constraints=[{"type": "eq", "fun": lambda c: float(c.sum() - 1.0)}],
                        options={"maxiter": 600, "ftol": 1e-12})
               for s in [np.ones(kernels.shape[0]) / kernels.shape[0]]
               + [rng.random(kernels.shape[0]) for _ in range(starts)]]
    best = min(results, key=lambda r: r.fun)
    return float(best.fun), int(np.count_nonzero(np.maximum(best.x, 0.0) > 1e-6))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True, help="measured profile to fit")
    parser.add_argument("--bins", type=int, default=32)
    parser.add_argument("--starts", type=int, default=10, help="random starts per floor")
    parser.add_argument("--tapers", default="0,-1,-2,-4")
    parser.add_argument("--table-tapers", default="0,-2")
    parser.add_argument("--table-ages", default="16,22,30,40,62,234,568,1024")
    parser.add_argument("--table-damping", default="0.448,0.831,2.4,36.8,375")
    args = parser.parse_args()

    ages = np.unique(np.round(np.geomspace(1.0, 1024.0, 48)).astype(np.int64))
    target, _ = load_target(args.profile, ages)
    window = ages >= 16
    anchor = int(np.argmax(window))
    tapers = [float(v) for v in args.tapers.split(",")]

    def config(taper):
        return FieldConfig(mode_count=6144, wave_mode_count=3072,
                           read_absolute=True, unwritten_latch=True, scale_read_taper=taper)

    print("kernel table: readout energy at age / energy at age 16, one bin per row")
    table_ages = [int(v) for v in args.table_ages.split(",")]
    sel = [int(np.argmin(np.abs(ages - a))) for a in table_ages]
    damping = np.array([float(v) for v in args.table_damping.split(",")])
    for taper in [float(v) for v in args.table_tapers.split(",")]:
        kernels = bin_kernels(config(taper), damping, ages, 16)
        shaped = kernels / kernels[:, sel[0]][:, None]
        print()
        print(f"taper {taper:g}")
        print("  %-9s %s" % ("damping", " ".join("%-8d" % a for a in table_ages)))
        for b, d in enumerate(damping):
            print("  %-9.3f %s" % (d, " ".join("%-8.4f" % shaped[b, i] for i in sel)))
        spread = shaped[:, sel[2]]
        print("  spread across damping at age %d: %.4f..%.4f"
              % (table_ages[2], spread.min(), spread.max()))

    print()
    print("shape rank and multi-start family floor on the fixed rate grid")
    print("%-7s %-10s %-9s %-9s %-10s %s" % ("taper", "shape rank", "sv2/sv1", "sv3/sv1",
                                             "floor", "bins used"))
    half_lives = np.geomspace(0.25, 618.5417955350765, args.bins)
    rates = rate_grid(half_lives, config(0.0).dt)
    for taper in tapers:
        kernels = bin_kernels(config(taper), rates, ages, 16)
        shaped = kernels / kernels[:, anchor][:, None]
        sv = np.linalg.svd(shaped[:, window], compute_uv=False)
        sv = sv / sv[0]
        floor, used = family_floor(kernels, target, window, args.starts)
        print("%-7.2f %-10d %-9.2e %-9.2e %-10.6f %d"
              % (taper, int(np.count_nonzero(sv > 1e-3)), sv[1], sv[2], floor, used))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
