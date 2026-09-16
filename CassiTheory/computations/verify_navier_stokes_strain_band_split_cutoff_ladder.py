#!/usr/bin/env python3
"""Read the vortex-stretching band split on a declared cutoff ladder on ROCm.

The preregistered schedule is
`computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md`. This
verifier loads the executed band machinery of
`computations/verify_navier_stokes_strain_band_split.py` from disk, accepts it
only at the SHA-256 recorded below, and reads the frozen statistic

    r_high(k_c) = I_high,+(k_c; T) / max(I_P(T), 1e-12)

at the declared ladder LADDER = (1, 2, 3, 4, 6, 8). One N=32 primary
trajectory per declared family supplies every cutoff: the evolution equation
carries no cutoff, and the frozen accumulation adds each band to its own
running integral, so the ladder is the same statistic read six times from the
same accepted states.

Run from the repository root:

    timeout 14400 python computations/verify_navier_stokes_strain_band_split_cutoff_ladder.py
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-strain-band-split-cutoff-ladder-prereg.md"
FROZEN_PROTOCOL = ROOT / "computations" / "navier-stokes-strain-band-split-prereg.md"
FROZEN_SCRIPT = ROOT / "computations" / "verify_navier_stokes_strain_band_split.py"
FROZEN_RECEIPT = ROOT / "runs" / "navier_stokes_strain_band_split" / "verification.json"
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT / "runs" / "navier_stokes_strain_band_split_cutoff_ladder" / "verification.json"
)
SCHEMA = "cassi.navier-stokes.strain-band-split-cutoff-ladder.verification.v1"
PROTOCOL_REVISION = "L1"

FROZEN_SCRIPT_SHA256 = "b31e1782e275f3073ba0c05d4912d1eedc0b6f543e735feebb17e773688dcb66"
LADDER = (1, 2, 3, 4, 6, 8)
GRID_CUTOFF = 32
GRID_SIZE = 6 * GRID_CUTOFF + 1
STEPS = 1024
DECLARED_RUNS = 6
HIGH_LEVEL = 0.5
LOW_LEVEL = 0.1
MONOTONE_TOLERANCE = 0.05
REPRODUCTION_TOLERANCE = 1.0e-9
BELTRAMI_REPRODUCTION_TOLERANCE = 1.0e-30

CLASS_NAMES = (
    "non_monotone",
    "located_crossover_both_levels",
    "located_crossover_low_level",
    "low_band_dominated_throughout",
    "high_band_dominated_throughout",
    "intermediate_throughout",
    "right_censored_above_low_level",
)
VERDICTS = ("SUPPORTS", "CONTRADICTS", "EMERGES", "DOES NOT EMERGE", "INCONCLUSIVE")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def level_reading(curve: dict[int, float], level: float) -> dict[str, Any]:
    """Locate the crossing of a level by the ladder's adjacent pairs."""
    brackets = [
        [left, right]
        for left, right in zip(LADDER, LADDER[1:])
        if curve[left] > level >= curve[right]
    ]
    if brackets:
        return {"state": "crossed", "brackets": brackets}
    if curve[LADDER[0]] <= level:
        return {"state": "below_throughout", "brackets": []}
    return {"state": "above_top", "brackets": []}


def family_class(curve: dict[int, float]) -> dict[str, Any]:
    """Classify one family's ladder curve by the prereg's ordered rules."""
    values = [curve[cutoff] for cutoff in LADDER]
    drops = [
        (values[index] - values[index + 1], LADDER[index], LADDER[index + 1])
        for index in range(len(LADDER) - 1)
    ]
    reversals = [
        [drops[first][1:], drops[second][1:]]
        for first in range(len(drops))
        for second in range(first + 1, len(drops))
        if drops[first][0] > MONOTONE_TOLERANCE and -drops[second][0] > MONOTONE_TOLERANCE
    ]
    high = level_reading(curve, HIGH_LEVEL)
    low = level_reading(curve, LOW_LEVEL)
    reading: dict[str, Any] = {
        "high_level": high,
        "low_level": low,
        "non_monotone_reversals": reversals,
        "intermediate_cutoffs": [
            cutoff
            for cutoff in LADDER
            if LOW_LEVEL < curve[cutoff] <= HIGH_LEVEL
        ],
    }
    if reversals:
        reading["class"] = "non_monotone"
    elif low["state"] == "crossed" and high["state"] == "crossed":
        reading["class"] = "located_crossover_both_levels"
        reading["qualifier"] = (
            "single step"
            if low["brackets"] == high["brackets"]
            else "gradual"
        )
    elif low["state"] == "crossed":
        reading["class"] = "located_crossover_low_level"
    elif max(values) <= LOW_LEVEL:
        reading["class"] = "low_band_dominated_throughout"
    elif min(values) > HIGH_LEVEL:
        reading["class"] = "high_band_dominated_throughout"
    elif min(values) > LOW_LEVEL and max(values) <= HIGH_LEVEL:
        reading["class"] = "intermediate_throughout"
    else:
        reading["class"] = "right_censored_above_low_level"
    reading["low_level_bracket"] = low["brackets"][0] if low["brackets"] else None
    reading["high_level_bracket"] = high["brackets"][0] if high["brackets"] else None
    return reading


def route(frozen_receipt: dict[str, Any]) -> dict[str, list[str]]:
    """Read the cutoff-sensitive and cutoff-stable family sets from the receipt."""
    verdicts = frozen_receipt["family_verdicts"]
    names = sorted(verdicts)
    sensitive = [
        name
        for name in names
        if len({entry["verdict"] for entry in verdicts[name]["per_cutoff"].values()}) > 1
    ]
    return {
        "cutoff_sensitive": sensitive,
        "cutoff_stable": [name for name in names if name not in sensitive],
        "families": names,
    }


def frozen_beltrami(frozen_receipt: dict[str, Any]) -> dict[str, Any]:
    for record in frozen_receipt["runs"]:
        if record["case"] == "beltrami" and record["run"] == "primary":
            if int(record["cutoff"]) == GRID_CUTOFF:
                return record
    raise RuntimeError("the frozen receipt carries no beltrami N=32 primary run")


def run_probe() -> dict[str, Any]:
    band = load_module("navier_stokes_strain_band_split", FROZEN_SCRIPT)
    frozen_digest = sha256(FROZEN_SCRIPT)
    frozen_band_cutoffs = tuple(band.BAND_CUTOFFS)
    band.BAND_CUTOFFS = LADDER
    frozen_receipt = json.loads(FROZEN_RECEIPT.read_text(encoding="utf-8"))
    sets = route(frozen_receipt)
    reference = frozen_beltrami(frozen_receipt)

    records: list[dict[str, Any]] = []
    started = time.time()
    with torch.no_grad():
        for case in band.CASES:
            print(
                f"[run] {case['name']} primary N={GRID_CUTOFF} M={GRID_SIZE} "
                f"steps={STEPS} ladder={list(LADDER)}",
                flush=True,
            )
            record = band.integrate_case(
                case, GRID_CUTOFF, GRID_SIZE, STEPS, "primary"
            )
            records.append(record)
            bands = ", ".join(
                f"k{cutoff} high={record['high_band_positive_integral'][str(cutoff)]:.6e}"
                for cutoff in LADDER
            )
            print(
                f"[done] {record['case']} I+={record['positive_stretching_integral']:.6e} "
                f"{bands}",
                flush=True,
            )
    elapsed = time.time() - started

    by_name = {record["case"]: record for record in records}
    checks: dict[str, Any] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    ratios = {
        name: band.case_ratios(by_name[name]) for name in band.TUBE_FAMILIES
    }
    curves = {
        name: {cutoff: ratios[name][str(cutoff)]["high_band_fraction"] for cutoff in LADDER}
        for name in band.TUBE_FAMILIES
    }
    readings = {name: family_class(curves[name]) for name in band.TUBE_FAMILIES}

    check("declared_run_count", len(records) == DECLARED_RUNS, len(records))
    check(
        "ladder_coverage",
        all(
            set(record["high_band_positive_integral"]) == {str(cutoff) for cutoff in LADDER}
            and set(record["low_band_positive_integral"]) == {str(cutoff) for cutoff in LADDER}
            for record in records
        ),
        sorted({tag for record in records for tag in record["high_band_positive_integral"]}),
    )
    check(
        "finite_values",
        all(band.all_finite(record) for record in records),
        sum(1 for record in records if not band.all_finite(record)),
    )
    normalization = max(
        record["initial_metadata"]["normalization_error"] for record in records
    )
    check("kinetic_normalization", normalization <= band.NORMALIZATION_BOUND, normalization)
    divergence = max(record["maximum_divergence_residual"] for record in records)
    check("divergence_residual", divergence <= band.DIVERGENCE_BOUND, divergence)
    identity = max(record["maximum_band_identity_residual"] for record in records)
    check("band_identity", identity <= band.BAND_IDENTITY_BOUND, identity)
    parseval = max(record["maximum_band_parseval_residual"] for record in records)
    check("band_parseval", parseval <= band.BAND_PARSEVAL_BOUND, parseval)
    increment = max(record["maximum_positive_energy_increment"] for record in records)
    check("energy_increment", increment <= band.ENERGY_INCREMENT_BOUND, increment)
    balance = max(
        abs(record["maximum_energy_balance_residual"])
        / max(1.0, abs(record["initial"]["energy_derivative"]), 2.0 * band.NU * record["initial"]["enstrophy"])
        for record in records
    )
    check("energy_balance", balance <= band.ENERGY_INCREMENT_BOUND, balance)
    beltrami_record = by_name["beltrami"]
    beltrami_control = beltrami_record["maximum_absolute_band_production"]
    check(
        "beltrami_band_control",
        beltrami_control <= band.BELTRAMI_BAND_BOUND,
        beltrami_control,
    )
    check(
        "source_binding",
        frozen_digest == FROZEN_SCRIPT_SHA256,
        {"measured": frozen_digest, "declared": FROZEN_SCRIPT_SHA256},
    )

    deltas: dict[str, float] = {}
    for name in band.TUBE_FAMILIES:
        frozen = frozen_receipt["ratios"][name]
        for cutoff in frozen_band_cutoffs:
            tag = str(cutoff)
            deltas[f"{name}:high@{tag}"] = band.relative_change(
                curves[name][cutoff], frozen[tag]["high_band_fraction"]
            )
            deltas[f"{name}:low@{tag}"] = band.relative_change(
                ratios[name][tag]["low_band_fraction"],
                frozen[tag]["low_band_fraction"],
            )
    worst_delta = max(deltas.values())
    check(
        "frozen_value_reproduction",
        worst_delta <= REPRODUCTION_TOLERANCE,
        {
            "worst": worst_delta,
            "bound": REPRODUCTION_TOLERANCE,
            "per_key": deltas,
        },
    )
    beltrami_deltas = {
        "positive_integral": abs(
            beltrami_record["positive_stretching_integral"]
            - reference["positive_stretching_integral"]
        ),
    }
    for cutoff in frozen_band_cutoffs:
        tag = str(cutoff)
        beltrami_deltas[f"low@{tag}"] = abs(
            beltrami_record["low_band_positive_integral"][tag]
            - reference["low_band_positive_integral"][tag]
        )
        beltrami_deltas[f"high@{tag}"] = abs(
            beltrami_record["high_band_positive_integral"][tag]
            - reference["high_band_positive_integral"][tag]
        )
    beltrami_worst = max(beltrami_deltas.values())
    check(
        "beltrami_frozen_reproduction",
        beltrami_worst <= BELTRAMI_REPRODUCTION_TOLERANCE,
        {
            "worst": beltrami_worst,
            "bound": BELTRAMI_REPRODUCTION_TOLERANCE,
            "per_key": beltrami_deltas,
        },
    )

    integrity_passed = all(entry["passed"] for entry in checks.values())
    classes = {name: readings[name]["class"] for name in band.TUBE_FAMILIES}
    located = {"located_crossover_both_levels", "located_crossover_low_level"}
    uncrossed = {
        "high_band_dominated_throughout",
        "intermediate_throughout",
        "right_censored_above_low_level",
    }
    if not integrity_passed:
        verdict = None
    elif "non_monotone" in classes.values():
        verdict = "CONTRADICTS"
    elif not any(value in uncrossed for value in classes.values()):
        verdict = "EMERGES"
    elif all(classes[name] in uncrossed for name in sets["cutoff_sensitive"]):
        verdict = "DOES NOT EMERGE"
    else:
        verdict = "INCONCLUSIVE"
    if verdict is not None and verdict not in VERDICTS:
        raise RuntimeError(f"undeclared verdict {verdict}")

    receipt = {
        "schema": SCHEMA,
        "protocol_revision": PROTOCOL_REVISION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if integrity_passed else "FAIL",
        "verdict": verdict,
        "verdict_scope": "cutoff-dependent band assignment of positive vortex-stretching production",
        "scope": {
            "equation": "unforced incompressible Navier-Stokes on the 2*pi torus",
            "nu": band.NU,
            "T": band.T_END,
            "grid_cutoff": GRID_CUTOFF,
            "grid_size": GRID_SIZE,
            "steps": STEPS,
            "ladder": list(LADDER),
            "frozen_cutoffs": list(frozen_band_cutoffs),
            "families": [case["name"] for case in band.CASES],
            "executions": DECLARED_RUNS,
        },
        "decision_parameters": {
            "high_level": HIGH_LEVEL,
            "low_level": LOW_LEVEL,
            "monotone_tolerance": MONOTONE_TOLERANCE,
            "reproduction_tolerance": REPRODUCTION_TOLERANCE,
            "beltrami_reproduction_tolerance": BELTRAMI_REPRODUCTION_TOLERANCE,
        },
        "checks": checks,
        "wall_time_seconds": elapsed,
        "source_hashes": {
            "computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md": sha256(PROTOCOL),
            "computations/navier-stokes-strain-band-split-prereg.md": sha256(FROZEN_PROTOCOL),
            "computations/verify_navier_stokes_strain_band_split_cutoff_ladder.py": sha256(SCRIPT),
            "computations/verify_navier_stokes_strain_band_split.py": frozen_digest,
            "runs/navier_stokes_strain_band_split/verification.json": sha256(FROZEN_RECEIPT),
        },
        "family_sets": sets,
        "ladder_table": {
            name: [
                {
                    "cutoff": cutoff,
                    "high_band_fraction": curves[name][cutoff],
                    "low_band_fraction": ratios[name][str(cutoff)]["low_band_fraction"],
                    "high_band_integral": by_name[name]["high_band_positive_integral"][str(cutoff)],
                    "low_band_integral": by_name[name]["low_band_positive_integral"][str(cutoff)],
                }
                for cutoff in LADDER
            ]
            for name in band.TUBE_FAMILIES
        },
        "family_readings": readings,
        "frozen_deltas": deltas,
        "beltrami_frozen_deltas": beltrami_deltas,
        "runs": records,
    }
    return receipt


def run_smoke() -> None:
    band = load_module("navier_stokes_strain_band_split", FROZEN_SCRIPT)
    frozen_digest = sha256(FROZEN_SCRIPT)
    if frozen_digest != FROZEN_SCRIPT_SHA256:
        raise SystemExit(f"smoke FAILED: frozen verifier digest {frozen_digest}")
    band.BAND_CUTOFFS = LADDER
    with torch.no_grad():
        for case in band.CASES[:2]:
            record = band.integrate_case(case, 8, 49, 16, "smoke")
            tags = sorted(record["high_band_positive_integral"], key=int)
            if tags != [str(cutoff) for cutoff in LADDER]:
                raise SystemExit(f"smoke FAILED: ladder tags drifted to {tags}")
            print(
                f"smoke: {record['case']} ladder={tags} "
                f"identity={record['maximum_band_identity_residual']:.2e} "
                f"parseval={record['maximum_band_parseval_residual']:.2e}"
            )
    print("smoke: PASS (ladder patched, six readings per state)")


def main() -> int:
    if not torch.cuda.is_available():
        raise SystemExit("ROCm Torch CUDA device is required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    arguments = parser.parse_args()
    if arguments.smoke:
        run_smoke()
        return 0

    receipt = run_probe()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    failed = [name for name, entry in receipt["checks"].items() if not entry["passed"]]
    print(f"status={receipt['status']} verdict={receipt['verdict']}")
    print(f"checks: {len(receipt['checks']) - len(failed)}/{len(receipt['checks'])} passed")
    for name in failed:
        print(f"FAILED {name}: {receipt['checks'][name]['detail']}")
    print(f"wall_time_seconds={receipt['wall_time_seconds']:.2f}")
    for name, entry in receipt["family_readings"].items():
        curve = ", ".join(
            f"k{cutoff}={entry_value:.6f}"
            for cutoff, entry_value in zip(
                LADDER,
                [
                    row["high_band_fraction"]
                    for row in receipt["ladder_table"][name]
                ],
            )
        )
        print(
            f"{name}: {entry['class']} "
            f"(low bracket {entry['low_level_bracket']}, "
            f"high bracket {entry['high_level_bracket']}) {curve}"
        )
    print(f"receipt: {arguments.output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
