"""Compare two `probe_cassi_qi_mode_bank.py` output directories arm by arm.

The readout taper weights scale `s` of a mode by `exp(-taper * s * damping * dt)` and
divides the readout by the weighted scale sum.  That divisor makes the flag exactly
inert on a field that has only one scale available, which is the regime the mode-bank
probe's own seed state sits in, so a taper run that reports no change has not shown the
flag is broken: it has shown the readout had nothing to weight.  This script prints both
halves of that statement: the per-arm logit deltas between the two runs, and the scale
population of the state each run started from.

    python research/compare_readout_taper_arms.py \
        --baseline _diag/qi-mode-bank-multiscale --variant _diag/qi-ms-taper-m2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STATE_MODE_COUNT = 6144
STATE_SCALES = 4
STATE_COMPONENTS = 9
STATE_FLOATS = STATE_MODE_COUNT * STATE_SCALES * STATE_COMPONENTS


def arm_dumps(directory: Path, key: str) -> dict[str, Path]:
    """Every arm's named dump, keyed by arm slot."""
    found: dict[str, Path] = {}
    for receipt_path in sorted(directory.glob("*/graph-trial-receipt.json")):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        dump = receipt_path.parent / receipt[key]["path"]
        if dump.is_file():
            found[receipt_path.parent.name] = dump
    if not found:
        raise SystemExit(f"no arms under {directory}")
    return found


def taper_of(directory: Path) -> float:
    """The taper the run recorded, read from any one of its receipts."""
    for receipt_path in sorted(directory.glob("*/graph-trial-receipt.json")):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        return float(receipt["configuration"].get("scale_read_taper", 0.0))
    raise SystemExit(f"no receipts under {directory}")


def state_population(directory: Path) -> list[tuple[float, float]]:
    """Per-scale rms and nonzero fraction of the state the run started from."""
    seed = directory / "seed" / "state-after.f32"
    if not seed.is_file():
        return []
    values = np.fromfile(seed, dtype=np.float32)
    if values.size != STATE_FLOATS:
        raise SystemExit(f"{seed} holds {values.size} floats, expected {STATE_FLOATS}")
    by_scale = values.reshape(STATE_SCALES, STATE_MODE_COUNT, STATE_COMPONENTS)
    return [(float(np.sqrt(np.mean(by_scale[k] ** 2))), float(np.mean(np.abs(by_scale[k]) > 1.0e-6)))
            for k in range(STATE_SCALES)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", required=True, help="probe output directory at the pinned readout")
    parser.add_argument("--variant", required=True, help="probe output directory carrying the taper")
    args = parser.parse_args()

    baseline_dir, variant_dir = Path(args.baseline), Path(args.variant)
    baseline, variant = arm_dumps(baseline_dir, "logits"), arm_dumps(variant_dir, "logits")
    baseline_state = arm_dumps(baseline_dir, "state_successor")
    variant_state = arm_dumps(variant_dir, "state_successor")
    print(f"baseline {baseline_dir} taper {taper_of(baseline_dir):g}")
    print(f"variant  {variant_dir} taper {taper_of(variant_dir):g}")

    for label, directory in (("baseline", baseline_dir), ("variant", variant_dir)):
        population = state_population(directory)
        if not population:
            continue
        rms = " ".join(f"{value:.2e}" for value, _ in population)
        live = " ".join(f"{fraction:.3f}" for _, fraction in population)
        print(f"{label} seed state rms per scale {rms}")
        print(f"{label} seed state nonzero fraction {live}")

    print()
    print(f"{'arm':<28}{'logits max|d|':>16}{'state max|d|':>16}")
    moved = 0
    for arm in sorted(baseline):
        if arm not in variant:
            continue
        left = np.fromfile(baseline[arm], dtype=np.float32)
        right = np.fromfile(variant[arm], dtype=np.float32)
        delta = float(np.max(np.abs(left - right)))
        if delta != 0.0:
            moved += 1
        state_delta = float("nan")
        if arm in baseline_state and arm in variant_state:
            state_delta = float(np.max(np.abs(
                np.fromfile(baseline_state[arm], dtype=np.float32)
                - np.fromfile(variant_state[arm], dtype=np.float32))))
        print(f"{arm:<28}{delta:>16.3e}{state_delta:>16.3e}")
    print()
    print(f"{moved} of {len(set(baseline) & set(variant))} arms moved; "
          f"reach-off is the control and must stay at exactly zero")
    print("the taper weights the readout alone, so every state delta must be exactly zero")
    return 0


if __name__ == "__main__":
    sys.exit(main())
