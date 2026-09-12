#!/usr/bin/env python3
"""Independent verifier for the spatial-convergence wave-capture calculation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
import zipfile
from typing import Any

from pathlib import Path
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
BASELINE_SOURCE_SHA256 = {
    "computations/matter_formation_wave_capture.py": "31ab56d40524c505d90431b65b0072b998c65635313955d057b4d6d4b8e35b83",
    "computations/matter_formation_wave_capture_v2_prereg.md": "8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba",
    "computations/matter_formation_neutral_packets.py": "743e2e75e6b8bc5c5ffd6a75393a49b9da6e5481b9b0b4dee08b040b3f1b901f",
    "computations/matter_formation_radial_cloud.py": "7ed6029e878c6642ab22a6c2526b4a02b2107b1538b751a6c1ea66762f5f6cb4",
    "computations/verify_matter_formation_wave_capture.py": "a7bccd1c20904e43b05cc7559863747df2d8b61dca8ea61b216c29581545da8d",
}
BASELINE_SOURCE_ARCHIVE = BASELINE_RECEIPT.parent / "sources"
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
COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "binding_ratio",
    "shell_energy_fraction",
)
METHOD_COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "binding_ratio",
    "shell_energy_fraction",
    "core_energy",
    "mediator_depletion",
)
DECOMPOSITION_TOL = 1.0e-8
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


def baseline_source_archive_binding() -> bool:
    return all(
        (BASELINE_SOURCE_ARCHIVE / key.replace("/", "__")).is_file()
        and sha256(BASELINE_SOURCE_ARCHIVE / key.replace("/", "__")) == expected
        for key, expected in BASELINE_SOURCE_SHA256.items()
    )


def baseline_binding(receipt: dict[str, Any]) -> bool:
    baseline = receipt.get("baseline")
    return bool(
        isinstance(baseline, dict)
        and baseline.get("primary_receipt") == BASELINE_RECEIPT.relative_to(ROOT).as_posix()
        and baseline.get("primary_receipt_sha256") == BASELINE_RECEIPT_SHA256
        and baseline.get("protocol_sha256") == BASELINE_PROTOCOL_SHA256
        and baseline.get("source_sha256") == BASELINE_SOURCE_SHA256
        and baseline.get("source_archive") == BASELINE_SOURCE_ARCHIVE.relative_to(ROOT).as_posix()
        and baseline_source_archive_binding()
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
def safe_verify_primary_rows(input_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    try:
        return audit.verify_primary_rows(input_dir, receipt)
    except (OSError, ValueError, zipfile.BadZipFile, audit.VerificationError) as error:
        return {
            "pass": False,
            "details": [{"failures": [str(error)]}],
            "hash_attempted": 0,
            "hash_passed": 0,
            "reconstruction_attempted": 0,
            "reconstruction_passed": 0,
        }



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
def primary_decomposition_pass(input_dir: Path, receipt: dict[str, Any]) -> bool:
    rows = receipt.get("rows", [])
    if not isinstance(rows, list):
        return False
    try:
        for row in rows:
            if not isinstance(row, dict):
                return False
            initial = row.get("initial")
            states = row.get("states")
            trace = row.get("trace")
            if not isinstance(initial, dict) or not isinstance(states, list) or not isinstance(trace, list):
                return False
            for state in states:
                if not isinstance(state, dict) or not base.finite_number(state.get("time")):
                    return False
                time_value = float(state["time"])
                index = int(round(time_value / base.SAMPLE_DT))
                if index < 0 or index >= len(trace) or not isinstance(trace[index], dict):
                    return False
                grid, q, v = audit._validate_state_archive(input_dir, row, state)
                rebuilt = audit.metric(
                    grid,
                    q,
                    v,
                    float(row["coupling"]),
                    float(initial["charge"]),
                    float(initial["energy"]),
                )
                observed = trace[index]
                if any(
                    not audit._real_equal(rebuilt.get(name), observed.get(name))
                    for name in DIAGNOSTIC_COMPONENTS
                ):
                    return False
                component_total = sum(float(rebuilt[name]) for name in DIAGNOSTIC_COMPONENTS)
                allocated_total = float(audit.cell_energy(grid, q, v, float(row["coupling"])).sum())
                energy = float(rebuilt["energy"])
                if abs(component_total - energy) > DECOMPOSITION_TOL * max(1.0, abs(energy)):
                    return False
                if abs(allocated_total - energy) > DECOMPOSITION_TOL * max(1.0, abs(energy)):
                    return False
    except (KeyError, OSError, ValueError, TypeError, zipfile.BadZipFile, audit.VerificationError):
        return False
    return True


def independent_decomposition_pass(archive_dir: Path, independent: list[dict[str, Any]]) -> bool:
    try:
        for item in independent:
            radius = int(item["grid"])
            spacing = float(item["spacing"])
            coupling = audit.HC
            charge_reference = float(item["charge_reference"])
            energy_reference = float(item["energy_reference"])
            snapshots = item.get("snapshots")
            states = item.get("states")
            if not isinstance(snapshots, dict) or not isinstance(states, list):
                return False
            grid = audit.IndependentGrid(radius, spacing)
            for state in states:
                if not isinstance(state, dict):
                    return False
                state_path = audit._independent_state_path(archive_dir, state)
                with audit.np.load(state_path, allow_pickle=False) as data:
                    q = audit.torch.as_tensor(data["fields"], dtype=audit.torch.float64, device="cuda")
                    v = audit.torch.as_tensor(data["velocities"], dtype=audit.torch.float64, device="cuda")
                    embedded_time = float(audit.np.asarray(data["time"]).reshape(()))
                rebuilt = audit.metric(grid, q, v, coupling, charge_reference, energy_reference)
                observed = snapshots.get(str(embedded_time), snapshots.get(embedded_time))
                if not isinstance(observed, dict):
                    return False
                if any(
                    not audit._real_equal(rebuilt.get(name), observed.get(name))
                    for name in DIAGNOSTIC_COMPONENTS
                ):
                    return False
                component_total = sum(float(rebuilt[name]) for name in DIAGNOSTIC_COMPONENTS)
                allocated_total = float(audit.cell_energy(grid, q, v, coupling).sum())
                energy = float(rebuilt["energy"])
                if abs(component_total - energy) > DECOMPOSITION_TOL * max(1.0, abs(energy)):
                    return False
                if abs(allocated_total - energy) > DECOMPOSITION_TOL * max(1.0, abs(energy)):
                    return False
                del q, v
    except (KeyError, OSError, ValueError, TypeError, zipfile.BadZipFile, audit.VerificationError):
        return False
    return True



def corrupted_hash_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    rows = mutated.get("rows", [])
    row = next((item for item in rows if item.get("grid") == "S0" and item.get("arm") == "pair256"), None)
    if not isinstance(row, dict) or not isinstance(row.get("states"), list) or not row["states"]:
        return False
    row["states"][0]["sha256"] = "0" * 64
    details = safe_verify_primary_rows(input_dir, mutated)
    return bool(
        not details["pass"]
        and any("hash mismatch" in failure for item in details["details"] for failure in item["failures"])
    )


def corrupted_archive_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    rows = mutated.get("rows", [])
    row = next((item for item in rows if item.get("grid") == "S0" and item.get("arm") == "pair256"), None)
    if not isinstance(row, dict) or not isinstance(row.get("states"), list) or not row["states"]:
        return False
    state = row["states"][0]
    if not isinstance(state, dict):
        return False
    with tempfile.TemporaryDirectory(prefix="matter-formation-corrupt-") as directory:
        root = Path(directory)
        primary = root / "primary"
        primary.mkdir()
        corrupt = primary / "corrupt.npz"
        corrupt.write_bytes(b"not a zip archive")
        state["path"] = corrupt.name
        state["sha256"] = sha256(corrupt)
        details = safe_verify_primary_rows(root, mutated)
    failures = [failure.lower() for item in details["details"] for failure in item["failures"]]
    return bool(not details["pass"] and any(
        "zip" in failure or "archive" in failure or "pickled" in failure
        for failure in failures
    ))


def path_traversal_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    rows = mutated.get("rows", [])
    row = next((item for item in rows if item.get("grid") == "S0" and item.get("arm") == "pair256"), None)
    if not isinstance(row, dict) or not isinstance(row.get("states"), list) or not row["states"]:
        return False
    state = row["states"][0]
    if not isinstance(state, dict):
        return False
    state["path"] = "../escape.npz"
    details = safe_verify_primary_rows(input_dir, mutated)
    failures = [failure.lower() for item in details["details"] for failure in item["failures"]]
    return bool(not details["pass"] and any("escape" in failure or "path" in failure for failure in failures))


def strict_method_pass(result: dict[str, Any]) -> bool:
    errors = result.get("errors")
    expected = {f"{time_value}:{name}" for time_value in SAMPLE_TIMES for name in METHOD_COMPARISON_OBSERVABLES}
    if not isinstance(errors, dict) or set(errors) != expected or result.get("failures"):
        return False
    if any(not base.finite_number(value) for value in errors.values()):
        return False
    return max(errors.values(), default=float("inf")) < METHOD_TOL
def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing verifier output: {output_path}")
    receipt = strict_json(input_dir / "result.json")
    if receipt.get("schema") != "matter-formation-spatial-convergence-primary-20260911":
        raise audit.VerificationError("spatial primary schema mismatch")
    checks = source_checks(input_dir, receipt)
    snapshot_details = safe_verify_primary_rows(input_dir, receipt)
    target_row = next(
        (row for row in receipt.get("rows", []) if row.get("grid") == "S0" and row.get("arm") == "pair256"),
        None,
    )
    if not isinstance(target_row, dict):
        raise audit.VerificationError("S0 pair256 row missing")
    mutation = audit.mutation_control(input_dir, target_row)
    corrupted = corrupted_hash_control(input_dir, receipt)
    corrupted_archive = corrupted_archive_control(input_dir, receipt)
    traversal = path_traversal_control(input_dir, receipt)
    primary_decomposition = primary_decomposition_pass(input_dir, receipt)


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
    independent_decomposition = independent_decomposition_pass(archive_dir, independent)

    rows_by_arm = {
        row.get("arm"): row
        for row in receipt.get("rows", [])
        if row.get("grid") == "S1"
    }
    method_comparisons = [audit._method_comparison(rows_by_arm.get(item.get("arm")), item) for item in independent]
    for item in method_comparisons:
        item["pass"] = strict_method_pass(item)
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
    for item in comparisons if isinstance(comparisons, list) else []:
        if not isinstance(item, dict):
            primary_comparison_pass = False
            continue
        identity = (item.get("arm"), item.get("level_pair"), item.get("left"), item.get("right"))
        errors = item.get("errors")
        if identity in seen_comparisons or identity not in expected_comparisons:
            primary_comparison_pass = False
            continue
        seen_comparisons.add(identity)
        if (
            not isinstance(errors, dict)
            or set(errors) != set(COMPARISON_OBSERVABLES)
            or any(not base.finite_number(value) for value in errors.values())
        ):
            primary_comparison_pass = False
        if item.get("level_pair") != "S0->S1" and item.get("pass") is not True:
            primary_comparison_pass = False
    primary_comparison_pass = primary_comparison_pass and seen_comparisons == expected_comparisons
    diagnostic_pass = bool(diagnostic_component_pass(receipt) and primary_decomposition)
    scalar_pass = bool(method_comparisons and all(strict_method_pass(item) for item in method_comparisons))
    conservation_pass = bool(conservation_checks and all(item["pass"] for item in conservation_checks))
    result = {
        "schema": SCHEMA,
        "primary": str(input_dir),
        "source_checks": checks,
        "baseline_binding_pass": baseline_binding(receipt),
        "snapshot_details": snapshot_details,
        "diagnostic_component_pass": diagnostic_pass,
        "primary_decomposition_pass": primary_decomposition,
        "rejection_control_mutated_state_rejected": mutation,
        "rejection_control_corrupted_hash_rejected": corrupted,
        "rejection_control_corrupted_archive_rejected": corrupted_archive,
        "rejection_control_path_traversal_rejected": traversal,
        "independent_evolution": independent,
        "independent_archive_validation": archive_validation,
        "independent_decomposition_pass": independent_decomposition,
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
        and diagnostic_pass
        and primary_comparison_pass
        and mutation
        and corrupted
        and corrupted_archive
        and traversal
        and scalar_pass
        and independent_decomposition

        and conservation_pass
        and independent_complete
    )
    base.write_json(output_path, result)
    return result
def run_smoke() -> int:
    base.run_smoke()
    sample = {"energy": 5.0, **{name: 1.0 for name in DIAGNOSTIC_COMPONENTS}}
    rows = [
        {
            "grid": grid,
            "arm": arm,
            "trace": [dict(sample) for _ in range(EXPECTED_TRACE_LENGTH)],
        }
        for grid, arm in sorted(EXPECTED_ROW_KEYS)
    ]
    receipt = {"rows": rows}
    assert diagnostic_component_pass(receipt)
    truncated = copy.deepcopy(receipt)
    truncated["rows"][0]["trace"].pop()
    assert not diagnostic_component_pass(truncated)
    incomplete = {"errors": {"0.0:energy": 0.0}, "failures": []}
    assert not strict_method_pass(incomplete)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260911_matter_formation_wave_capture_spatial_convergence_20260911")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(json.dumps({"output": str(output), "numeric_pass": result["numeric_pass"], "snapshot_pass": result["snapshot_details"]["pass"], "independent_archive_pass": result["independent_raw_archive_complete"]}))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
