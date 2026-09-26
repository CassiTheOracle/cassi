#!/usr/bin/env python3
"""Exercise the positive-part Galerkin remainder branch on a real ROCm run."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = (
    ROOT / "computations" / "navier-stokes-galerkin-positive-remainder-firing-audit-prereg.md"
)
SCRIPT = Path(__file__).resolve()
FIXED_H3_PROTOCOL = (
    ROOT / "computations" / "navier-stokes-galerkin-fixed-h3-rocm-prereg.md"
)
FIXED_H3_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_fixed_h3_rocm.py"
)
DEFAULT_OUTPUT = (
    ROOT.parent
    / "runs"
    / "navier_stokes_galerkin_positive_remainder_firing_audit_20260914"
    / "verification.json"
)
SCHEMA = "cassi.navier-stokes.galerkin-positive-remainder-firing-audit.v1"


def _load_fixed_h3() -> Any:
    spec = importlib.util.spec_from_file_location("fixed_h3_probe", FIXED_H3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load fixed-H3 probe: {FIXED_H3_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixed_h3: Any = _load_fixed_h3()

RADIUS = 32.0
CUTOFF = 8
PRIMARY_GRID = 33
REFINED_GRID = 49
PRIMARY_STEPS = 1024
REFINED_STEPS = 2048


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_change(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def all_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_finite(item) for item in value)
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, str) or value is None:
        return True
    return False


def run_audit() -> dict[str, Any]:
    fixed_h3.RADIUS = RADIUS
    records: list[dict[str, Any]] = []
    with torch.no_grad():
        for label, grid_size, steps in (
            ("primary", PRIMARY_GRID, PRIMARY_STEPS),
            ("time_refined", PRIMARY_GRID, REFINED_STEPS),
            ("grid_refined", REFINED_GRID, PRIMARY_STEPS),
        ):
            record = fixed_h3.integrate_case(
                "base", CUTOFF, grid_size, steps, label
            )
 
            records.append(record)

    by_run = {record["run"]: record for record in records}
    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    check("finite_states_and_observables", all_finite(records), {"runs": len(records)})

    normalization_error = max(
        record["initial_metadata"]["normalization_error"] for record in records
    )
    check(
        "projected_h3_normalization",
        normalization_error <= 1e-10,
        {"maximum": normalization_error, "bound": 1e-10},
    )

    initial_remainders = {
        record["run"]: record["initial"]["remainder"] for record in records
    }
    check(
        "positive_initial_remainder",
        all(value > 0.0 for value in initial_remainders.values()),
        {"values": initial_remainders},
    )

    integrals = {
        record["run"]: record["positive_remainder_integral"] for record in records
    }
    check(
        "positive_integrated_remainder",
        integrals["primary"] > 0.0 and by_run["primary"]["positive_remainder_max"] > 0.0,
        {"integrals": integrals, "primary_max": by_run["primary"]["positive_remainder_max"]},
    )

    expected_attempts = {
        "primary": PRIMARY_STEPS + 1,
        "time_refined": REFINED_STEPS + 1,
        "grid_refined": PRIMARY_STEPS + 1,
    }
    actual_attempts = {
        record["run"]: record["positive_remainder_evaluation_count"]
        for record in records
    }
    check(
        "positive_part_attempt_count",
        actual_attempts == expected_attempts,
        {"expected": expected_attempts, "actual": actual_attempts},
    )

    max_divergence = max(record["max_divergence_residual"] for record in records)
    check(
        "divergence_residual",
        max_divergence <= 1e-10,
        {"maximum": max_divergence, "bound": 1e-10},
    )

    max_direct_relative_error = max(
        record["max_direct_spectral_relative_error"] for record in records
    )
    check(
        "direct_strain_production_agreement",
        max_direct_relative_error <= 1e-9,
        {"maximum": max_direct_relative_error, "bound": 1e-9},
    )

    max_energy_increment = max(
        record["max_positive_energy_increment"] for record in records
    )
    energy_bound = 1e-9 * max(
        1.0, max(record["initial"]["energy"] for record in records)
    )
    check(
        "kinetic_energy_dissipation",
        max_energy_increment <= energy_bound,
        {"maximum": max_energy_increment, "bound": energy_bound},
    )

    timestep_change = relative_change(
        integrals["primary"], integrals["time_refined"]
    )
    grid_change = relative_change(integrals["primary"], integrals["grid_refined"])
    check(
        "timestep_refinement",
        timestep_change <= 1e-6,
        {"relative_change": timestep_change, "bound": 1e-6},
    )
    check(
        "product_grid_refinement",
        grid_change <= 1e-6,
        {"relative_change": grid_change, "bound": 1e-6},
    )

    all_passed = all(entry["passed"] for entry in checks.values())
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_passed else "FAIL",
        "classification": (
            "PASS—positive-part firing control only" if all_passed else "FAIL"
        ),
        "scope": {
            "backend": "torch-rocm",
            "device": torch.cuda.get_device_name(0),
            "dtype": str(fixed_h3.DTYPE),
            "nu": fixed_h3.NU,
            "T": fixed_h3.T_END,
            "radius": RADIUS,
            "arm": "base",
            "cutoff": CUTOFF,
            "primary_grid": PRIMARY_GRID,
            "refined_grid": REFINED_GRID,
            "primary_steps": PRIMARY_STEPS,
            "refined_steps": REFINED_STEPS,
            "theorem_target": "UNRESOLVED",
            "cutoff_uniform_bound": "UNRESOLVED",
            "arbitrary_data_regularity": "UNRESOLVED",
        },
        "checks": checks,
        "integrated_remainder": integrals,
        "positive_part_attempts": actual_attempts,
        "runs": records,
        "source_hashes": {
            "computations/navier-stokes-galerkin-positive-remainder-firing-audit-prereg.md": sha256(
                PROTOCOL
            ),
            "computations/verify_navier_stokes_galerkin_positive_remainder_firing_audit.py": sha256(
                SCRIPT
            ),
            "computations/navier-stokes-galerkin-fixed-h3-rocm-prereg.md": sha256(
                FIXED_H3_PROTOCOL
            ),
            "computations/verify_navier_stokes_galerkin_fixed_h3_rocm.py": sha256(
                FIXED_H3_SCRIPT
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_smoke() -> None:
    fixed_h3.RADIUS = RADIUS
    with torch.no_grad():
        record = fixed_h3.integrate_case("base", CUTOFF, PRIMARY_GRID, 16, "smoke")
    if not all_finite(record):
        raise RuntimeError("smoke produced a nonfinite value")
    if record["initial"]["remainder"] <= 0.0:
        raise RuntimeError("smoke failed to enter positive initial remainder branch")
    if record["positive_remainder_integral"] <= 0.0:
        raise RuntimeError("smoke failed to produce a positive integrated remainder")
    print("smoke: PASS (ROCm, R=32, N=8, positive remainder branch)")


def main() -> int:
    if not torch.cuda.is_available():
        raise SystemExit("ROCm Torch CUDA device is required")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        run_smoke()
        return 0
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    receipt = run_audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + chr(10), encoding="utf-8")
    print(f"status: {receipt['status']}")
    print(f"classification: {receipt['classification']}")
    for name, entry in receipt["checks"].items():
        print(f"{name}: {'PASS' if entry['passed'] else 'FAIL'}")
    print(f"runs: {len(receipt['runs'])}")
    print(f"receipt: {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
