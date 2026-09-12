#!/usr/bin/env python3
"""Independently verify the Q=256 incoming-momentum formation probe."""
from __future__ import annotations

import argparse
import copy
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
if str(COMPUTATIONS) not in sys.path:
    sys.path.insert(0, str(COMPUTATIONS))

import verify_matter_formation_wave_capture as independent  # noqa: E402
from matter_formation_q256_momentum_spec import (  # noqa: E402
    ARMS,
    COUPLED_CANDIDATES,
    GRID_SPECS,
    ROBUST_COMPARISON_OBSERVABLES,
    TOTAL_CHARGE,
)

PREREG = COMPUTATIONS / "matter_formation_q256_momentum_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_q256_momentum_spec.py"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_q256_momentum.py"
BASE_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
INDEPENDENT_ACTION_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"
VERIFIER_SOURCE = Path(__file__).resolve()
SCHEMA = "matter-formation-q256-packet-momentum-verification-v1"
PRIMARY_SCHEMA = "matter-formation-q256-packet-momentum-primary-v1"
METHOD_TOL = 0.05
SAMPLE_TIMES = (0.0, 32.0, 40.0, 48.0)


def _initial_independent(grid: independent.IndependentGrid, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, float]:
    """Separately assemble the declarative Q=256 preparation for RK4."""
    if arm not in ARMS:
        raise independent.VerificationError(f"unknown independent arm: {arm}")
    pair = arm != "single256"
    uncoupled = arm == "uncoupled_k05"
    wave_number = {"single256": 0.0, "pair_k025": 0.25, "pair_k05": 0.5, "pair_k10": 1.0, "antiphase_k05": 0.5, "uncoupled_k05": 0.5}[arm]
    omega = independent.OMEGA_INF if not pair else math.sqrt(independent.OMEGA_INF**2 + 8.0 * wave_number**2)
    if not pair:
        envelope = torch.exp(-(grid.r2 + grid.axial[None, :].square()) / 32.0)
        z = envelope.to(torch.complex128)
    else:
        right = torch.exp(-(grid.r2 + (grid.axial[None, :] + 12.0).square()) / 32.0)
        left = torch.exp(-(grid.r2 + (grid.axial[None, :] - 12.0).square()) / 32.0)
        phase_right = wave_number * (grid.axial[None, :] + 12.0)
        phase_left = -wave_number * (grid.axial[None, :] - 12.0)
        sign = -1.0 if arm == "antiphase_k05" else 1.0
        z = right * torch.exp(1j * phase_right) + sign * left * torch.exp(1j * phase_left)
    norm = torch.sum(grid.volume * (z.real.square() + z.imag.square()))
    z = z * math.sqrt(TOTAL_CHARGE / (2.0 * independent.A * omega * float(norm)))
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1], q[2] = z.real, z.imag
    v = torch.zeros_like(q)
    v[1], v[2] = omega * q[2], -omega * q[1]
    return q, v, (0.0 if uncoupled else independent.HC), TOTAL_CHARGE


independent.initial = _initial_independent
independent.SAMPLE_TIMES = SAMPLE_TIMES
independent.ARMS = ARMS


def _source_checks(input_dir: Path, receipt: dict[str, Any]) -> dict[str, bool]:
    paths = (PREREG, SPEC_SOURCE, PRIMARY_SOURCE, BASE_SOURCE, NEUTRAL_SOURCE, CLOUD_SOURCE, INDEPENDENT_ACTION_SOURCE, VERIFIER_SOURCE)
    recorded = receipt.get("source_sha256", {})
    checks: dict[str, bool] = {"protocol_live": receipt.get("protocol_sha256") == independent.sha256(PREREG)}
    for path in paths:
        key = path.relative_to(ROOT).as_posix()
        archived = input_dir / "sources" / key.replace("/", "__")
        expected = recorded.get(key)
        present = archived.is_file()
        archived_hash = independent.sha256(archived) if present else ""
        checks[key] = bool(present and isinstance(expected, str) and archived_hash == expected)
        checks[f"live_{key}"] = bool(checks[key] and independent.sha256(path) == archived_hash)
    checks["archive_bytes"] = bool(all(value for key, value in checks.items() if key != "protocol_live" and not key.startswith("live_")))
    checks["live_source_bytes"] = bool(all(value for key, value in checks.items() if key.startswith("live_")))
    return checks


def _corrupted_hash_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    row = next((item for item in mutated.get("rows", []) if item.get("grid") == "S1" and item.get("arm") == "pair_k05"), None)
    if not isinstance(row, dict) or not row.get("states"):
        return False
    row["states"][0]["sha256"] = "0" * 64
    details = independent.verify_primary_rows(input_dir, mutated)
    return bool(not details["pass"] and any("hash mismatch" in failure for item in details["details"] for failure in item["failures"]))


def _method_comparison(primary_row: dict[str, Any] | None, independent_row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"arm": independent_row.get("arm"), "errors": {}, "failures": [], "pass": False}
    if primary_row is None:
        result["failures"].append("primary T1 row missing")
        return result
    snapshots = independent_row.get("snapshots", {})
    trace = primary_row.get("trace", [])
    for time_value in SAMPLE_TIMES:
        values = snapshots.get(str(time_value), snapshots.get(time_value)) if isinstance(snapshots, dict) else None
        index = int(round(time_value / 0.5))
        if not isinstance(values, dict) or not isinstance(trace, list) or index < 0 or index >= len(trace):
            result["failures"].append(f"missing snapshot {time_value}")
            continue
        observed = trace[index] if isinstance(trace[index], dict) else {}
        if any(not independent.finite_number(observed.get(name)) or not independent.finite_number(values.get(name)) for name in independent.REQUIRED_OBSERVABLES):
            result["failures"].append(f"{time_value}:required observable missing or invalid")
            continue
        for name in ROBUST_COMPARISON_OBSERVABLES:
            observed_float = float(observed[name])
            rebuilt_float = float(values[name])
            result["errors"][f"{time_value}:{name}"] = abs(observed_float - rebuilt_float) / max(1.0, abs(observed_float), abs(rebuilt_float))
    result["pass"] = bool(result["errors"]) and not result["failures"] and max(result["errors"].values()) < METHOD_TOL
    return result


def _schedule_contract(receipt: dict[str, Any]) -> bool:
    if receipt.get("schema") != PRIMARY_SCHEMA:
        return False
    preparation = receipt.get("preparation", {})
    if preparation.get("total_charge") != TOTAL_CHARGE:
        return False
    rows = receipt.get("rows", [])
    expected = {(grid, arm) for grid in GRID_SPECS for arm in ARMS}
    actual = {(row.get("grid"), row.get("arm")) for row in rows if isinstance(row, dict)}
    if actual != expected or len(rows) != len(expected):
        return False
    comparisons = receipt.get("comparisons", [])
    expected_comparisons = {(f"S1_{arm}", f"S2_{arm}") for arm in ARMS} | {(f"S1_{arm}", f"T1_{arm}") for arm in ARMS}
    actual_comparisons = {(item.get("left"), item.get("right")) for item in comparisons if isinstance(item, dict)}
    return len(comparisons) == len(expected_comparisons) and actual_comparisons == expected_comparisons


def _formation_classification(receipt: dict[str, Any]) -> tuple[list[str], bool, str]:
    rows = {(row.get("grid"), row.get("arm")): row for row in receipt.get("rows", []) if isinstance(row, dict)}
    comparisons = {(item.get("left"), item.get("right")): item for item in receipt.get("comparisons", []) if isinstance(item, dict)}
    fully_compared: list[str] = []
    for arm in COUPLED_CANDIDATES:
        if not all(rows.get((grid, arm), {}).get("formation") is True for grid in ("S1", "S2", "T1")):
            continue
        if all(comparisons.get((f"S1_{arm}", other), {}).get("pass") is True for other in (f"S2_{arm}", f"T1_{arm}")):
            fully_compared.append(f"S1_{arm}")
    uncoupled = rows.get(("S1", "uncoupled_k05"), {})
    uncoupled_failed = bool(uncoupled.get("numerically_qualified") is True and uncoupled.get("formation") is not True)
    primary_comparison_pass = bool(receipt.get("numerical_pass") is True and len(receipt.get("comparisons", [])) == len(ARMS) * 2 and all(item.get("pass") is True for item in receipt.get("comparisons", [])))
    if not primary_comparison_pass:
        verdict = "INCONCLUSIVE"
    elif fully_compared and uncoupled_failed:
        verdict = "EMERGES—conditional Q=256 bound remnant in the declared incoming-momentum basin"
    else:
        verdict = "DOES NOT EMERGE in the specified Q=256 packet-momentum calculation"
    return fully_compared, uncoupled_failed, verdict


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise independent.VerificationError(f"refusing to overwrite existing verifier output: {output_path}")
    receipt = independent.strict_json(input_dir / "result.json")
    source_checks = _source_checks(input_dir, receipt)
    schedule_pass = _schedule_contract(receipt)
    snapshot_details = independent.verify_primary_rows(input_dir, receipt)
    base_row = next((row for row in receipt.get("rows", []) if row.get("grid") == "S1" and row.get("arm") == "pair_k05"), None)
    mutation = bool(isinstance(base_row, dict) and independent.mutation_control(input_dir, base_row))
    corrupted_hash_rejected = _corrupted_hash_control(input_dir, receipt)

    archive_dir = output_path.parent / f"{output_path.stem}_independent_states"
    if archive_dir.exists():
        raise independent.VerificationError(f"refusing to overwrite independent archive: {archive_dir}")
    archive_dir.mkdir(parents=True, exist_ok=False)
    independent_rows: list[dict[str, Any]] = []
    radius, spacing, dt = GRID_SPECS["T1"]
    for arm in ARMS:
        evolved = independent.independent_evolution(arm, radius, spacing, dt, archive_dir)
        independent_rows.append({**evolved, "snapshots": {str(t): values for t, values in evolved["snapshots"].items()}, "source": "fresh independent RK4 integration"})
    independent_complete, archive_validation = independent._validate_independent_archive(archive_dir, independent_rows)

    rows_by_arm = {row.get("arm"): row for row in receipt.get("rows", []) if row.get("grid") == "T1"}
    method_comparisons = [_method_comparison(rows_by_arm.get(item.get("arm")), item) for item in independent_rows]
    conservation_checks = [{"arm": item.get("arm"), "energy_drift": item.get("energy_drift"), "charge_drift": item.get("charge_drift"), "pass": bool(item.get("conservation_pass", False)), "raw_state_archive_complete": bool(item.get("raw_state_archive_complete", False))} for item in independent_rows]
    fully_compared, uncoupled_failed, verdict = _formation_classification(receipt)
    scalar_pass = bool(method_comparisons and all(item["pass"] for item in method_comparisons))
    independent_conservation_pass = bool(conservation_checks and all(item["pass"] for item in conservation_checks))
    primary_comparison_pass = bool(
        receipt.get("numerical_pass") is True
        and len(receipt.get("comparisons", [])) == len(ARMS) * 2
        and all(item.get("pass") is True for item in receipt.get("comparisons", []))
    )
    numeric_pass = bool(
        schedule_pass
        and all(source_checks.values())
        and snapshot_details["pass"]
        and mutation
        and corrupted_hash_rejected
        and primary_comparison_pass
        and scalar_pass
        and independent_conservation_pass
        and independent_complete
    )
    if not numeric_pass:
        verdict = "INCONCLUSIVE"
    result = {
        "schema": SCHEMA,
        "primary": str(input_dir),
        "primary_schema": receipt.get("schema"),
        "source_checks": source_checks,
        "schedule_contract_pass": schedule_pass,
        "snapshot_details": snapshot_details,
        "rejection_control_mutated_state_rejected": mutation,
        "rejection_control_corrupted_hash_rejected": corrupted_hash_rejected,
        "independent_evolution": independent_rows,
        "independent_archive_validation": archive_validation,
        "conservation_checks": conservation_checks,
        "method_comparisons": method_comparisons,
        "primary_comparison_pass": primary_comparison_pass,
        "independent_raw_archive_complete": independent_complete,
        "scalar_snapshot_comparison_pass": scalar_pass,
        "independent_conservation_pass": independent_conservation_pass,
        "fully_compared_candidates": fully_compared,
        "uncoupled_control_failed": uncoupled_failed,
        "verdict": verdict,
        "numeric_pass": numeric_pass,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
    }
    independent.write_json(output_path, result)
    return result


def run_smoke() -> int:
    grid = independent.IndependentGrid(16, 1.0)
    for arm in ARMS:
        q, v, coupling, charge = _initial_independent(grid, arm)
        measured = float((grid.volume * (-2.0 * independent.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        assert abs(measured - charge) / charge < 1.0e-12
        assert math.isfinite(float(grid.energy(q, v, coupling)))
    print('{"smoke":"PASS","arms":6,"total_charge":256.0}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?", default=ROOT / "runs" / "20260912_matter_formation_q256_momentum")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output_path = args.output.resolve() if args.output else input_dir / "verification.json"
    result = run(input_dir, output_path)
    print(independent.json.dumps({"output": str(output_path), "numeric_pass": result["numeric_pass"], "verdict": result["verdict"]}))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
