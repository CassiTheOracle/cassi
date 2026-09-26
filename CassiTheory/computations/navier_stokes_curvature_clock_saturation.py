#!/usr/bin/env python
"""Saturation window of the vorticity-direction coherence margin.

Companion to `computations/navier_stokes_curvature_clock.py`.  The clock
measured the margin kappa a_n of the vorticity-direction coherence tube over
t in [0, 1/2]: it grows monotonically in all three declared families while its
rate decelerates.  This protocol, frozen in
`computations/navier-stokes-curvature-clock-saturation-prereg.md`, integrates the
same families over t in [0, 2] and decides whether the deceleration is the
approach to a finite limit below the pole.

Usage:
    python computations/navier_stokes_curvature_clock_saturation.py [--output DIR]

Exit status is 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLOCK_SCRIPT = ROOT / "computations" / "navier_stokes_curvature_clock.py"
LONG_TRAJECTORY_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
)
DEPLETION_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
)
PROTOCOL_SCRIPT = (
    ROOT
    / "computations"
    / "navier-stokes-curvature-clock-saturation-prereg.md"
)
DEFAULT_OUTPUT = ROOT / "runs" / "navier_stokes_curvature_clock_saturation"
SCHEMA = "navier-stokes-curvature-clock-saturation-v1"

HORIZON = 2.0
STEPS = 4096
CHECKPOINT_FRACTIONS = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)
TAIL_CUTOFF = 8
TAIL_THRESHOLD = 5.0e-2
INTEGRITY_TOLERANCE = 1.0e-12


def sha256(path: Path) -> str:
    """Blob-convention digest: line endings normalised, so a CRLF checkout agrees."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def enstrophy_tail(box, state) -> float:
    """Fraction of enstrophy carried by modes above TAIL_CUTOFF."""
    import torch

    coefficients = state
    wave = box.wave_numbers
    radial = torch.sqrt(torch.sum(wave * wave, dim=-1))
    density = torch.sum(torch.abs(coefficients) ** 2, dim=-1) * (radial * radial)
    total = float(torch.sum(density).item())
    if total <= 0.0:
        return 0.0
    tail = float(torch.sum(density * (radial > TAIL_CUTOFF)).item())
    return tail / total


def integrate_case(case: dict[str, Any], clock, long_trajectory, depletion) -> dict[str, Any]:
    box = long_trajectory.TorchGalerkinBox(clock.CUTOFF, clock.GRID_FACTOR * clock.CUTOFF + 1)
    state, metadata = depletion.initial_state(case, box)
    dt = HORIZON / float(STEPS)
    rhs = box.right_hand_side(state)
    checkpoint_steps = {int(round(f * STEPS)) for f in CHECKPOINT_FRACTIONS}
    checkpoints: list[dict[str, Any]] = []
    maximum_divergence = 0.0
    maximum_energy_increment = 0.0
    previous_energy = None

    def record(index: int, state_tensor) -> None:
        observables = box.spectral_observables(state_tensor, rhs)
        raw = clock.local_tensors(box, state_tensor)
        checkpoints.append(
            {
                "step": int(index),
                "time": float(index * dt),
                "raw": raw,
                "derived": clock.core_algebra(raw),
                "observables": {
                    "kinetic_energy": float(observables["energy"]),
                    "enstrophy": float(observables["enstrophy"]),
                    "production": float(observables["production"]),
                    "divergence_residual": float(observables["divergence_residual"]),
                    "enstrophy_tail": enstrophy_tail(box, state_tensor),
                },
            }
        )

    record(0, state)
    previous_energy = checkpoints[0]["observables"]["kinetic_energy"]
    for index in range(STEPS):
        state = long_trajectory.rk4_update(box, state, dt, rhs)
        rhs = box.right_hand_side(state)
        energy = float(box.spectral_observables(state, rhs)["energy"])
        maximum_energy_increment = max(maximum_energy_increment, energy - previous_energy)
        previous_energy = energy
        if index + 1 in checkpoint_steps:
            record(index + 1, state)
    for row in checkpoints:
        maximum_divergence = max(maximum_divergence, row["observables"]["divergence_residual"])

    rates = []
    for earlier, later in zip(checkpoints, checkpoints[1:]):
        span = later["time"] - earlier["time"]
        rate = (later["derived"]["margin"] - earlier["derived"]["margin"]) / span
        earlier["measured_rate"] = float(rate)
        earlier["rate_interval"] = span
        rates.append(float(rate))
    last = float(checkpoints[-1]["derived"]["margin"])
    span = float(checkpoints[-1]["time"] - checkpoints[-2]["time"])
    turnover = rates[-1] <= 0.0
    if turnover:
        rate_ratio = 0.0
        projection = last
        decay = "turnover"
    elif rates[-3] > 0.0 and rates[-1] > 0.0:
        rate_ratio = (rates[-1] / rates[-3]) ** (1.0 / 3.0)
        projection = (
            last + rates[-1] * span * rate_ratio / (1.0 - rate_ratio)
            if rate_ratio < 1.0
            else float("inf")
        )
        decay = "decelerating"
    else:
        rate_ratio = float("nan")
        projection = float("inf")
        decay = "non-monotone"
    if decay == "decelerating" and not (rates[-3] >= rates[-2] >= rates[-1]):
        decay = "non-monotone"
    return {
        "case": case["name"],
        "family": case["family"],
        "cutoff": clock.CUTOFF,
        "grid_size": clock.GRID_FACTOR * clock.CUTOFF + 1,
        "steps": STEPS,
        "nu": clock.NU,
        "horizon": HORIZON,
        "helix_curvature": clock.HELIX_CURVATURE[case["name"]],
        "initial_state": {
            "normalization_error": float(metadata["normalization_error"]),
            "projection_error": float(metadata["projection_error"]),
            "state_divergence_residual": float(metadata["state_divergence_residual"]),
            "geometry": metadata["geometry"],
        },
        "maximum_divergence_residual": maximum_divergence,
        "maximum_energy_increment": maximum_energy_increment,
        "rates": rates,
        "rate_ratio": rate_ratio,
        "decay": decay,
        "turnover": bool(turnover),
        "projected_limit": projection,
        "final_margin": last,
        "maximum_margin": max(float(row["derived"]["margin"]) for row in checkpoints),
        "maximum_enstrophy_tail": max(
            float(row["observables"]["enstrophy_tail"]) for row in checkpoints
        ),
        "checkpoints": checkpoints,
    }


def build_receipt() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    clock = load_module(CLOCK_SCRIPT)
    long_trajectory = load_module(LONG_TRAJECTORY_SCRIPT)
    depletion = load_module(DEPLETION_SCRIPT)

    print("Saturation window of the vorticity-direction coherence margin")
    print("=" * 78)
    cases = [case for case in depletion.CASES if case["name"] in clock.HELIX_CURVATURE]
    dynamics = []
    for case in cases:
        entry = integrate_case(case, clock, long_trajectory, depletion)
        dynamics.append(entry)
        name = entry["case"]
        margins = [float(row["derived"]["margin"]) for row in entry["checkpoints"]]
        rates = entry["rates"]
        print(f"  {name}: margins " + ", ".join(f"{value:.4f}" for value in margins))
        print(f"  {name}: rates   " + ", ".join(f"{value:.4f}" for value in rates))
        print(
            f"  {name}: decay {entry['decay']}  ratio {entry['rate_ratio']:.4f}  "
            f"projected limit {entry['projected_limit']:.4f}  "
            f"tail {entry['maximum_enstrophy_tail']:.2e}"
        )
        check(
            f"E1 {name}: integrity holds over the window",
            entry["maximum_divergence_residual"] <= INTEGRITY_TOLERANCE
            and entry["maximum_energy_increment"] <= INTEGRITY_TOLERANCE
            and float(entry["initial_state"]["normalization_error"]) <= INTEGRITY_TOLERANCE,
            f"divergence {entry['maximum_divergence_residual']:.2e}, "
            f"energy increment {entry['maximum_energy_increment']:.2e}",
        )
        check(
            f"E1 {name}: the initial state projects and normalizes",
            float(entry["initial_state"]["projection_error"]) <= 1.0e-1
            and float(entry["initial_state"]["state_divergence_residual"]) <= 1.0e-12,
            f"projection error {float(entry['initial_state']['projection_error']):.4f}, "
            f"state divergence {float(entry['initial_state']['state_divergence_residual']):.2e}",
        )
        check(
            f"E2 {name}: the coherence margin stays inside the pole",
            entry["maximum_margin"] < 1.0,
            f"largest margin {entry['maximum_margin']:.6f} over {len(margins)} checkpoints",
        )
        check(
            f"E3 {name}: the rate series is reported",
            True,
            f"classification {entry['decay']}; last three rates "
            + ", ".join(f"{value:.4f}" for value in rates[-3:]),
        )
        check(
            f"E4 {name}: the projected limit is reported",
            True,
            f"projected limit {entry['projected_limit']:.6f} at rate ratio "
            f"{entry['rate_ratio']:.4f} (projection, not a bound)",
        )
        check(
            f"E5 {name}: the resolution diagnostic is reported",
            True,
            f"largest enstrophy tail {entry['maximum_enstrophy_tail']:.2e} "
            f"above |k| = {TAIL_CUTOFF} "
            + (
                "(UNDER-RESOLVED: late-time numbers quoted with this qualification)"
                if entry["maximum_enstrophy_tail"] > TAIL_THRESHOLD
                else "(resolved)"
            ),
        )
        check(
            f"E6 {name}: the initial curvature anchors to the seeded helix",
            0.5
            <= float(entry["checkpoints"][0]["derived"]["kappa"]) / entry["helix_curvature"]
            <= 2.0,
            f"kappa(0) {float(entry['checkpoints'][0]['derived']['kappa']):.4f} "
            f"against the seeded {entry['helix_curvature']:.4f}",
        )

    saturating = [
        entry
        for entry in dynamics
        if entry["decay"] != "turnover" and entry["projected_limit"] < 1.0
    ]
    turning = [entry for entry in dynamics if entry["decay"] == "turnover"]
    status = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    body = {
        "schema": SCHEMA,
        "status": status,
        "verdict": (
            "MARGIN TURNS OVER BEFORE THE POLE IN "
            + ", ".join(entry["case"] for entry in turning)
            if turning
            else "SATURATION OR PROJECTED LIMIT REPORTED"
        ),
        "classification": " ".join(
            f"{entry['case']}: {entry['decay']} with rate ratio "
            f"{entry['rate_ratio']:.4f}, projected limit "
            f"{entry['projected_limit']:.4f}, largest margin "
            f"{entry['maximum_margin']:.4f}"
            + (
                " (under-resolved at late times)."
                if entry["maximum_enstrophy_tail"] > TAIL_THRESHOLD
                else " (resolved)."
            )
            for entry in dynamics
        ),
        "under_resolved": [
            entry["case"]
            for entry in dynamics
            if entry["maximum_enstrophy_tail"] > TAIL_THRESHOLD
        ],
        "scope": {
            "arbitrary_data_regularity": "UNRESOLVED",
            "equation": "original unforced 3-D incompressible Navier-Stokes",
            "backend": "torch-rocm",
            "families": [entry["case"] for entry in dynamics],
            "projection_is_a_bound": False,
            "time_integrability_of_the_modulus": "MEASURED ON THE DECLARED FAMILIES ONLY",
        },
        "parameters": {
            "horizon": HORIZON,
            "steps": STEPS,
            "checkpoint_fractions": list(CHECKPOINT_FRACTIONS),
            "tail_cutoff": TAIL_CUTOFF,
            "tail_threshold": TAIL_THRESHOLD,
            "integrity_tolerance": INTEGRITY_TOLERANCE,
            "cutoff": clock.CUTOFF,
            "grid_factor": clock.GRID_FACTOR,
            "nu": clock.NU,
        },
        "dynamics": dynamics,
        "checks": checks,
        "source_hashes": {
            "computations/navier-stokes-curvature-clock-saturation-prereg.md": sha256(
                PROTOCOL_SCRIPT
            ),
            "computations/navier_stokes_curvature_clock_saturation.py": sha256(
                Path(__file__).resolve()
            ),
            "computations/navier_stokes_curvature_clock.py": sha256(CLOCK_SCRIPT),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": sha256(
                LONG_TRAJECTORY_SCRIPT
            ),
            "computations/verify_navier_stokes_helical_dynamic_depletion.py": sha256(
                DEPLETION_SCRIPT
            ),
        },
    }
    return body


def json_safe(value):
    import numpy as np

    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    arguments = parser.parse_args()
    output = Path(arguments.output) if arguments.output else DEFAULT_OUTPUT
    if not output.is_absolute():
        output = ROOT / output
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    receipt = json_safe(build_receipt())
    digest = hashlib.sha256(
        json.dumps(receipt, indent=1, sort_keys=True).encode()
    ).hexdigest()
    receipt["content_sha256"] = digest
    payload = json.dumps(receipt, indent=1, sort_keys=True)
    (output / "curvature_clock_saturation.json").write_text(payload)
    (output / "curvature_clock_saturation_receipt.json").write_text(payload)
    for item in receipt["checks"]:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"  [{mark}] {item['name']}: {item['detail']}")
    print("=" * 78)
    print(f"status {receipt['status']}  content {digest[:16]}")
    print(f"receipt {output / 'curvature_clock_saturation_receipt.json'}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
