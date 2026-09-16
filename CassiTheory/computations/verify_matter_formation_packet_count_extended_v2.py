#!/usr/bin/env python3
"""Independently verify the axisymmetric four-to-six packet extension."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import verify_matter_formation_packet_count as lower_verify
from matter_formation_packet_count_extended_spec import (
    ARM_SPECS,
    ARMS,
    CANDIDATE_ARMS,
    COMPARISON_OBSERVABLES,
    GEOMETRIES,
    GRID_SPECS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    LATE_START,
    LOWER_PRIMARY_RECEIPT_SHA256,
    LOWER_VERIFICATION_RECEIPT_SHA256,
    R0,
    RETAINED_FRACTION,
    SAMPLE_DT,
    SHARE_TOL,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    WAVE_NUMBER,
    WIDTH,
    BINDING_RATIO_MAX,
)

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_extended_v2_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v2.py"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_spec.py"
PRIMARY_SCHEMA = "matter-formation-packet-count-extended-v2-primary-v1"
SCHEMA = "matter-formation-packet-count-extended-v2-verification-v1"
BASE_PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count.py"
BASE_PREREG = COMPUTATIONS / "matter_formation_packet_count_prereg.md"
BASE_SPEC = COMPUTATIONS / "matter_formation_packet_count_spec.py"
BASE_VERIFIER = COMPUTATIONS / "verify_matter_formation_packet_count.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
WAVE_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
INDEPENDENT_WAVE_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"


def patch_lower_verifier() -> None:
    """Use the lower verifier's independent kernels with the new frozen schedule."""
    lower_verify.PREREG = PREREG
    lower_verify.PRIMARY_SOURCE = PRIMARY_SOURCE
    lower_verify.SPEC_SOURCE = SPEC_SOURCE
    lower_verify.NEUTRAL_SOURCE = NEUTRAL_SOURCE
    lower_verify.CLOUD_SOURCE = CLOUD_SOURCE
    lower_verify.WAVE_SOURCE = WAVE_SOURCE
    lower_verify.INDEPENDENT_WAVE_SOURCE = INDEPENDENT_WAVE_SOURCE
    lower_verify.SELF = SELF
    lower_verify.SCHEMA = SCHEMA
    lower_verify.PRIMARY_SCHEMA = PRIMARY_SCHEMA
    lower_verify.ARM_SPECS = ARM_SPECS
    lower_verify.ARMS = ARMS
    lower_verify.COMPARISON_OBSERVABLES = COMPARISON_OBSERVABLES
    lower_verify.GEOMETRIES = GEOMETRIES
    lower_verify.GRID_SPECS = GRID_SPECS
    lower_verify.INITIAL_CORE_FRACTION_MAX = INITIAL_CORE_FRACTION_MAX
    lower_verify.INITIAL_OVERLAP_MAX = INITIAL_OVERLAP_MAX
    lower_verify.LATE_START = LATE_START
    lower_verify.R0 = R0
    lower_verify.RETAINED_FRACTION = RETAINED_FRACTION
    lower_verify.SAMPLE_DT = SAMPLE_DT
    lower_verify.SHARE_TOL = SHARE_TOL
    lower_verify.SNAPSHOT_TIMES = SNAPSHOT_TIMES
    lower_verify.T_FINAL = T_FINAL
    lower_verify.TOTAL_CHARGE = TOTAL_CHARGE
    lower_verify.WAVE_NUMBER = WAVE_NUMBER
    lower_verify.WIDTH = WIDTH
    lower_verify.BINDING_RATIO_MAX = BINDING_RATIO_MAX
    lower_verify.lower_lineage_context = lower_lineage_context
    lower_verify.derive_packet_count = derive_packet_count


def lower_lineage_context() -> dict[str, Any]:
    primary_path = ROOT / "runs" / "20260912_matter_formation_packet_count" / "result.json"
    verification_path = primary_path.parent / "verification.json"
    observed_primary = lower_verify.sha256(primary_path) if primary_path.is_file() else None
    observed_verification = lower_verify.sha256(verification_path) if verification_path.is_file() else None
    return {
        "historical_primary_expected": LOWER_PRIMARY_RECEIPT_SHA256,
        "historical_verification_expected": LOWER_VERIFICATION_RECEIPT_SHA256,
        "observed_primary": observed_primary,
        "observed_verification": observed_verification,
        "historical_lineage_accepted": bool(
            observed_primary == LOWER_PRIMARY_RECEIPT_SHA256
            and observed_verification == LOWER_VERIFICATION_RECEIPT_SHA256
        ),
        "use": "diagnostic_context_only",
    }


def _fully_compared(rows: dict[tuple[str, str], dict[str, Any]], comparisons: list[dict[str, Any]], arm: str) -> bool:
    if not all(rows.get((grid, arm), {}).get("numerically_qualified") is True for grid in GRID_SPECS):
        return False
    relevant = [
        item for item in comparisons
        if item.get("left", "").endswith(f"_{arm}") or item.get("right", "").endswith(f"_{arm}")
    ]
    return bool(len(relevant) == 2 and all(item.get("pass") is True for item in relevant))


def derive_packet_count(receipt: dict[str, Any], comparisons: list[dict[str, Any]], primary_ok: bool) -> dict[str, Any]:
    rows = {(row.get("grid"), row.get("arm")): row for row in receipt.get("rows", []) if isinstance(row, dict)}
    candidate_details: dict[str, bool] = {}
    first_new_forming_count: int | None = None
    for count in (4, 5, 6):
        arm = f"n{count}_inward"
        complete = _fully_compared(rows, comparisons, arm)
        forms = bool(complete and all(rows.get((grid, arm), {}).get("formation") is True for grid in GRID_SPECS))
        candidate_details[arm] = forms
        if primary_ok and first_new_forming_count is None and forms:
            first_new_forming_count = count
    return {
        "historical_lower_lineage_accepted": False,
        "candidate_formation_by_arm": candidate_details,
        "first_new_forming_count": first_new_forming_count,
        "minimum_packet_count": None,
        "packet_count_minimum_established": False,
        "pass": bool(primary_ok),
        "scope": "new four-to-six ring-family formation only; no inherited minimum claim",
    }


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    patch_lower_verifier()
    result = lower_verify.run(input_dir, output_path)
    result["lower_lineage_context"] = lower_lineage_context()
    first_count = result["packet_count_reconstruction"]["first_new_forming_count"]
    if not result["numeric_pass"]:
        result["verdict"] = "INCONCLUSIVE"
    elif first_count is not None:
        result["verdict"] = f"EMERGES—conditional N={first_count} ring-family formation in the four-to-six extension"
    else:
        result["verdict"] = "DOES NOT EMERGE in the specified four-to-six ring-family extension"
    result["first_new_forming_count"] = first_count
    result["minimum_packet_count"] = None
    result["packet_count_minimum_established"] = False
    result["complete_physical_matter_formation"] = False
    result["gravitational_capture_established"] = False
    result["physical_size_map_established"] = False
    lower_verify.write_json(output_path, result)
    return result


def run_smoke() -> int:
    patch_lower_verifier()
    records = []
    for arm in ARMS:
        grid = lower_verify.independent_dynamics.IndependentGrid(48, 1.0)
        _q, _v, coupling, declared, metadata = lower_verify.assemble_independent(grid, arm)
        records.append({"arm": arm, "packet_count": metadata["packet_count"], "charge": declared, "coupling": coupling})
    print(lower_verify.independent_dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count_extended_v2")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(lower_verify.independent_dynamics.json.dumps({
        "output": str(output),
        "numeric_pass": result["numeric_pass"],
        "first_new_forming_count": result["packet_count_reconstruction"]["first_new_forming_count"],
        "historical_lower_lineage_accepted": result["lower_lineage_context"]["historical_lineage_accepted"],
        "archive_pass": result["independent_raw_archive_complete"],
        "method_pass": result["independent_method_pass"],
    }), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
