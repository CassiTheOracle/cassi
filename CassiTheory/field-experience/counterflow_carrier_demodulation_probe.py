#!/usr/bin/env python3
"""Frozen Wave-3 carrier-demodulation confirmation.

Run from the CassiTheory repository root:
    python field-experience/counterflow_carrier_demodulation_probe.py

Protocol: field-experience/counterflow-carrier-demodulation-pre-registration.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from counterflow_amplitude_phase_kick_probe import (
    BLOCK_SIZE,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_SEED,
    DT,
    MATCHED_CARRIER,
    N,
    QUADRATURE_CARRIER,
    ROOT,
    STEPS,
    no_op_identity,
    paired_bootstrap,
    quality_checks,
    run_arm,
)

COHERENCE_MARGIN = 0.10


def carrier_coherence(response: np.ndarray, reference: np.ndarray) -> float:
    """Return the bounded magnitude of a response projection onto one carrier."""
    if response.size == 0:
        return 0.0
    denominator = math.sqrt(float(np.dot(response, response)) * float(np.dot(reference, reference)))
    if denominator == 0.0:
        return 0.0
    return float(abs(float(np.dot(reference, response))) / denominator)


def block_coherences(events: list[dict[str, Any]], reference: tuple[int, int, int, int]) -> list[float]:
    result: list[float] = []
    for start in range(0, len(events), BLOCK_SIZE):
        block = events[start:start + BLOCK_SIZE]
        response = np.asarray([float(event["response"]) for event in block], dtype=np.float64)
        carrier = np.asarray(
            [reference[int(event["event_index"]) % len(reference)] for event in block],
            dtype=np.float64,
        )
        result.append(carrier_coherence(response, carrier))
    return result


def metric_sanity() -> dict[str, float | bool]:
    reference = np.asarray([MATCHED_CARRIER[index % 4] for index in range(BLOCK_SIZE)], dtype=np.float64)
    quadrature = np.asarray([QUADRATURE_CARRIER[index % 4] for index in range(BLOCK_SIZE)], dtype=np.float64)
    zero = carrier_coherence(np.zeros(BLOCK_SIZE, dtype=np.float64), reference)
    matched = carrier_coherence(-reference, reference)
    quadrature_projection = carrier_coherence(quadrature, reference)
    return {
        "zero": zero,
        "matched": matched,
        "quadrature": quadrature_projection,
        "passes": bool(zero == 0.0 and matched == 1.0 and quadrature_projection == 0.0),
    }


def contrast_passes(value: dict[str, float | int | None]) -> bool:
    mean = value["mean"]
    lo = value["lo"]
    return bool(mean is not None and lo is not None and float(mean) >= COHERENCE_MARGIN and float(lo) > 0.0)


def classify(
    quality: dict[str, Any],
    contrasts: dict[str, dict[str, float | int | None]],
    runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not quality["valid"]:
        return {"verdict": "INVALID", "phase": False, "space": False, "counterflow": False}
    phase = contrast_passes(contrasts["phase"])
    space = contrast_passes(contrasts["space"])
    counterflow = contrast_passes(contrasts["counterflow_reversed"]) and contrast_passes(
        contrasts["counterflow_zero"]
    )
    positive = runs["matched"]["summary"]["initial"]["jpsi_z_right"]
    reversed_flow = runs["counterflow_reversed"]["summary"]["initial"]["jpsi_z_right"]
    counterflow = bool(counterflow and positive * reversed_flow < 0.0)
    passed = int(phase) + int(space) + int(counterflow)
    verdict = "NULL" if passed == 0 else "PARTIAL" if passed < 3 else "PHASE-SELECTIVE CHECKERBOARD COUNTERFLOW SUPPORT"
    return {"verdict": verdict, "phase": phase, "space": space, "counterflow": counterflow}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=None, help="optional output directory below runs/")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sanity = metric_sanity()
    print(f"Device: {device} N={N} t_end={STEPS * DT} metric_sanity={sanity}", flush=True)
    identity = no_op_identity(device)
    print(f"No-op canonical identity max|delta|={identity:.1e}", flush=True)

    if args.output_dir is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = ROOT / "runs" / f"{run_id}_counterflow_carrier_demodulation"
    else:
        outdir = Path(args.output_dir)
        if not outdir.is_absolute():
            outdir = ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=False)

    runs: dict[str, dict[str, Any]] = {}
    runs["baseline"] = run_arm("baseline", device, +1, False, None, None, outdir)
    runs["matched"] = run_arm("matched", device, +1, False, MATCHED_CARRIER, None, outdir)
    schedule = runs["matched"]["matched_schedule"]
    runs["carrier_quadrature"] = run_arm(
        "carrier_quadrature", device, +1, False, QUADRATURE_CARRIER, schedule, outdir
    )
    runs["spatial_shuffled"] = run_arm(
        "spatial_shuffled", device, +1, True, MATCHED_CARRIER, schedule, outdir
    )
    runs["counterflow_reversed"] = run_arm(
        "counterflow_reversed", device, -1, False, MATCHED_CARRIER, schedule, outdir
    )
    runs["counterflow_zero"] = run_arm(
        "counterflow_zero", device, 0, False, MATCHED_CARRIER, schedule, outdir
    )

    quality = quality_checks(identity, runs)
    quality["metric_sanity"] = sanity
    quality["valid"] = bool(quality["valid"] and sanity["passes"])
    coherence = {
        name: block_coherences(run["events"], MATCHED_CARRIER)
        for name, run in runs.items()
        if name != "baseline"
    }
    own_coherence = {
        "matched": block_coherences(runs["matched"]["events"], MATCHED_CARRIER),
        "carrier_quadrature": block_coherences(runs["carrier_quadrature"]["events"], QUADRATURE_CARRIER),
    }
    contrasts = {
        "phase": paired_bootstrap(coherence["matched"], coherence["carrier_quadrature"]),
        "space": paired_bootstrap(coherence["matched"], coherence["spatial_shuffled"]),
        "counterflow_reversed": paired_bootstrap(coherence["matched"], coherence["counterflow_reversed"]),
        "counterflow_zero": paired_bootstrap(coherence["matched"], coherence["counterflow_zero"]),
    }
    verdict = classify(quality, contrasts, runs)
    receipt = {
        "protocol": "field-experience/counterflow-carrier-demodulation-pre-registration.md",
        "script": "field-experience/counterflow_carrier_demodulation_probe.py",
        "config": {
            "N": N,
            "dt": DT,
            "steps": STEPS,
            "t_end": STEPS * DT,
            "block_size": BLOCK_SIZE,
            "coherence_margin": COHERENCE_MARGIN,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "matched_carrier": MATCHED_CARRIER,
            "quadrature_carrier": QUADRATURE_CARRIER,
        },
        "quality": quality,
        "coherence_blocks": coherence,
        "own_carrier_coherence_blocks": own_coherence,
        "contrasts": contrasts,
        "verdict": verdict,
        "summaries": {name: run["summary"] for name, run in runs.items()},
        "run_files": {name: f"run_{name}.json" for name in runs},
    }
    with (outdir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)
    print(json.dumps({"quality": quality, "contrasts": contrasts, "verdict": verdict}, indent=2), flush=True)
    print(f"Results: {outdir}", flush=True)


if __name__ == "__main__":
    main()
