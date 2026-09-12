#!/usr/bin/env python3
"""Independent verifier for the spatial-convergence wave-capture calculation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import matter_formation_wave_capture as base
import verify_matter_formation_wave_capture as audit

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
PREREG = COMPUTATIONS / "matter_formation_wave_capture_spatial_convergence_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_wave_capture_spatial_convergence.py"
BASE_RUNNER_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
BASE_VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"
VERIFIER_SOURCE = Path(__file__).resolve()
BASELINE_RECEIPT = ROOT / "runs" / "20260911_matter_formation_wave_capture_v2" / "result.json"
BASELINE_RECEIPT_SHA256 = "c380ecb40c9c3239534e8546389ebfbac312d60e0df4238e7ce38e3a1780a052"
BASELINE_PROTOCOL_SHA256 = "8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba"
SCHEMA = "matter-formation-spatial-convergence-verification-20260911"
ARMS = ("pair256", "antiphase256")
SAMPLE_TIMES = base.SNAPSHOT_TIMES
INDEPENDENT_RADIUS = 192
INDEPENDENT_SPACING = 0.25
INDEPENDENT_DT = 0.00390625
METHOD_TOL = 0.05
DIAGNOSTIC_COMPONENTS = (
    "mediator_potential",
    "carrier_potential",
    "kinetic_energy",
    "radial_gradient",
    "axial_gradient",
)
EXPECTED_ROW_KEYS = {
    *((grid, arm) for grid in ("S0", "S1") for arm in ("pair256", "antiphase256", "single256", "uncoupled256")),
    *((grid, arm) for grid in ("S2", "D0") for arm in ("pair256", "antiphase256")),
}
EXPECTED_TRACE_LENGTH = int(round(base.T_FINAL / base.SAMPLE_DT)) + 1

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise audit.VerificationError(f"nonfinite JSON constant {value}: {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, audit.VerificationError) as error:
        if isinstance(error, audit.VerificationError):
            raise
        raise audit.VerificationError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise audit.VerificationError(f"object required: {path}")
    return value


def baseline_binding(receipt: dict[str, Any]) -> bool:
    baseline = receipt.get("baseline")
    return bool(
        isinstance(baseline, dict)
        and baseline.get("primary_receipt") == BASELINE_RECEIPT.relative_to(ROOT).as_posix()
        and baseline.get("primary_receipt_sha256") == BASELINE_RECEIPT_SHA256
        and baseline.get("protocol_sha256") == BASELINE_PROTOCOL_SHA256
        and BASELINE_RECEIPT.is_file()
        and sha256(BASELINE_RECEIPT) == BASELINE_RECEIPT_SHA256
    )


def source_checks(input_dir: Path, receipt: dict[str, Any]) -> dict[str, bool]:
    required = (
        PREREG,
        PRIMARY_SOURCE,
        BASE_RUNNER_SOURCE,
        NEUTRAL_SOURCE,
        CLOUD_SOURCE,
        BASE_VERIFIER_SOURCE,
        VERIFIER_SOURCE,
    )
    recorded = receipt.get("source_sha256", {})
    checks: dict[str, bool] = {"protocol_live": receipt.get("protocol_sha256") == sha256(PREREG)}
    for path in required:
        key = path.relative_to(ROOT).as_posix()
        archived = input_dir / "sources" / key.replace("/", "__")
        expected = recorded.get(key) if isinstance(recorded, dict) else None
        present = archived.is_file()
        archive_hash = sha256(archived) if present else ""
        checks[key] = bool(present and isinstance(expected, str) and archive_hash == expected)
        checks[f"live_{key}"] = bool(checks[key] and sha256(path) == archive_hash)
    checks["archive_bytes"] = bool(all(checks[key] for key in checks if key != "protocol_live" and not key.startswith("live_")))
    checks["live_source_bytes"] = bool(all(checks[key] for key in checks if key.startswith("live_")))
    return checks


def diagnostic_component_pass(receipt: dict[str, Any]) -> bool:
    rows = receipt.get("rows", [])
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_ROW_KEYS):
        return False
    keys: set[tuple[Any, Any]] = set()
    for row in rows:
        if not isinstance(row, dict):
            return False
        keys.add((row.get("grid"), row.get("arm")))
        trace = row.get("trace")
        if not isinstance(trace, list) or len(trace) != EXPECTED_TRACE_LENGTH:
            return False
        for sample in trace:
            if not isinstance(sample, dict) or any(not base.finite_number(sample.get(name)) for name in DIAGNOSTIC_COMPONENTS):
                return False
    return keys == EXPECTED_ROW_KEYS


def corrupted_hash_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    rows = mutated.get("rows", [])
    row = next((item for item in rows if item.get("grid") == "S0" and item.get("arm") == "pair256"), None)
    if not isinstance(row, dict) or not isinstance(row.get("states"), list) or not row["states"]:
        return False
    row["states"][0]["sha256"] = "0" * 64
    details = audit.verify_primary_rows(input_dir, mutated)
    return bool(
        not details["pass"]
        and any("hash mismatch" in failure for item in details["details"] for failure in item["failures"])
    )


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing verifier output: {output_path}")
    receipt = strict_json(input_dir / "result.json")
    if receipt.get("schema") != "matter-formation-spatial-convergence-primary-20260911":
        raise audit.VerificationError("spatial primary schema mismatch")
    checks = source_checks(input_dir, receipt)
    snapshot_details = audit.verify_primary_rows(input_dir, receipt)
    target_row = next(
        (row for row in receipt.get("rows", []) if row.get("grid") == "S0" and row.get("arm") == "pair256"),
        None,
    )
    if not isinstance(target_row, dict):
        raise audit.VerificationError("S0 pair256 row missing")
    mutation = audit.mutation_control(input_dir, target_row)
    corrupted = corrupted_hash_control(input_dir, receipt)

    archive_dir = output_path.parent / f"{output_path.stem}_independent_states"
    if archive_dir.exists():
        raise audit.VerificationError(f"refusing to overwrite independent archive: {archive_dir}")
    archive_dir.mkdir(parents=True, exist_ok=False)
    independent: list[dict[str, Any]] = []
    for arm in ARMS:
        evolved = audit.independent_evolution(
            arm,
            INDEPENDENT_RADIUS,
            INDEPENDENT_SPACING,
            INDEPENDENT_DT,
            archive_dir,
        )
        independent.append({
            **evolved,
            "snapshots": {str(time_value): values for time_value, values in evolved["snapshots"].items()},
            "source": "fresh independent RK4 integration",
        })
    independent_complete, archive_validation = audit._validate_independent_archive(archive_dir, independent)

    rows_by_arm = {
        row.get("arm"): row
        for row in receipt.get("rows", [])
        if row.get("grid") == "S1"
    }
    method_comparisons = [audit._method_comparison(rows_by_arm.get(item.get("arm")), item) for item in independent]
    conservation_checks = [
        {
            "arm": item.get("arm"),
            "energy_drift": item.get("energy_drift"),
            "charge_drift": item.get("charge_drift"),
            "pass": bool(item.get("conservation_pass", False)),
            "raw_state_archive_complete": bool(item.get("raw_state_archive_complete", False)),
        }
        for item in independent
    ]
    comparisons = receipt.get("comparisons", [])
    expected_comparisons = {
        (arm, "S0->S1", f"S0_{arm}", f"S1_{arm}") for arm in ARMS
    } | {
        (arm, "S1->S2", f"S1_{arm}", f"S2_{arm}") for arm in ARMS
    } | {
        (arm, "S0->D0", f"S0_{arm}", f"D0_{arm}") for arm in ARMS
    }
    seen_comparisons: set[tuple[Any, Any, Any, Any]] = set()
    primary_comparison_pass = bool(
        receipt.get("spatial_comparison_pass") is True
        and isinstance(comparisons, list)
        and len(comparisons) == len(expected_comparisons)
    )
    if primary_comparison_pass:
        for item in comparisons:
            if not isinstance(item, dict):
                primary_comparison_pass = False
                break
            identity = (item.get("arm"), item.get("level_pair"), item.get("left"), item.get("right"))
            if identity in seen_comparisons or identity not in expected_comparisons:
                primary_comparison_pass = False
                break
            seen_comparisons.add(identity)
            if not isinstance(item.get("errors"), dict):
                primary_comparison_pass = False
                break
            if item.get("level_pair") != "S0->S1" and item.get("pass") is not True:
                primary_comparison_pass = False
                break
        primary_comparison_pass = primary_comparison_pass and seen_comparisons == expected_comparisons
    scalar_pass = bool(method_comparisons and all(item["pass"] for item in method_comparisons))
    conservation_pass = bool(conservation_checks and all(item["pass"] for item in conservation_checks))
    result = {
        "schema": SCHEMA,
        "primary": str(input_dir),
        "source_checks": checks,
        "baseline_binding_pass": baseline_binding(receipt),
        "snapshot_details": snapshot_details,
        "diagnostic_component_pass": diagnostic_component_pass(receipt),
        "rejection_control_mutated_state_rejected": mutation,
        "rejection_control_corrupted_hash_rejected": corrupted,
        "independent_evolution": independent,
        "independent_archive_validation": archive_validation,
        "conservation_checks": conservation_checks,
        "method_comparisons": method_comparisons,
        "primary_comparison_pass": primary_comparison_pass,
        "independent_raw_archive_complete": independent_complete,
        "scalar_snapshot_comparison_pass": scalar_pass,
        "independent_conservation_pass": conservation_pass,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
    }
    result["numeric_pass"] = bool(
        result["baseline_binding_pass"]
        and all(checks.values())
        and snapshot_details["pass"]
        and result["diagnostic_component_pass"]
        and primary_comparison_pass
        and mutation
        and corrupted
        and scalar_pass
        and conservation_pass
        and independent_complete
    )
    base.write_json(output_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260911_matter_formation_wave_capture_spatial_convergence_20260911")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return base.run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(json.dumps({"output": str(output), "numeric_pass": result["numeric_pass"], "snapshot_pass": result["snapshot_details"]["pass"], "independent_archive_pass": result["independent_raw_archive_complete"]}))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
