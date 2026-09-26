#!/usr/bin/env python3
"""Independently verify the overlap-repaired four-to-six extension."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import verify_matter_formation_packet_count_extended_v2 as base
from matter_formation_packet_count_extended_v3_spec import *  # noqa: F401,F403

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_extended_v3_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3.py"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3_spec.py"
V2_PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v2.py"
V2_VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v2.py"
SCHEMA = "matter-formation-packet-count-extended-v3-verification-v1"
PRIMARY_SCHEMA = "matter-formation-packet-count-extended-v3-primary-v1"


def patch_base() -> None:
    for name in (
        "ARM_SPECS", "ARMS", "CANDIDATE_ARMS", "COMPARISON_OBSERVABLES", "GEOMETRIES",
        "GRID_SPECS", "INITIAL_CORE_FRACTION_MAX", "INITIAL_OVERLAP_MAX", "LATE_START", "R0",
        "RETAINED_FRACTION", "SAMPLE_DT", "SHARE_TOL", "SNAPSHOT_TIMES", "T_FINAL",
        "TOTAL_CHARGE", "WAVE_NUMBER", "WIDTH", "BINDING_RATIO_MAX",
    ):
        setattr(base, name, globals()[name])
    base.SELF = SELF
    base.PREREG = PREREG
    base.PRIMARY_SOURCE = PRIMARY_SOURCE
    base.SPEC_SOURCE = SPEC_SOURCE
    base.SCHEMA = SCHEMA
    base.PRIMARY_SCHEMA = PRIMARY_SCHEMA


def source_archive_check(input_dir: Path, result: dict[str, Any]) -> bool:
    source_hashes = result.get("source_checks", {})
    rows = result.get("primary_source_sha256", {})
    expected = {
        "computations/matter_formation_packet_count_extended_v2.py": V2_PRIMARY_SOURCE,
        "computations/verify_matter_formation_packet_count_extended_v2.py": V2_VERIFIER_SOURCE,
    }
    checks = []
    for relative, live in expected.items():
        archived = input_dir / "sources" / relative.replace("/", "__")
        checks.append(
            archived.is_file()
            and base.lower_verify.sha256(archived) == base.lower_verify.sha256(live)
        )
    result["v2_source_archive_checks"] = checks
    return bool(checks and all(checks))


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    patch_base()
    result = base.run(input_dir, output_path)
    archive_pass = source_archive_check(input_dir, result)
    result["v3_source_archive_pass"] = archive_pass
    result["lower_lineage_context"] = base.lower_lineage_context()
    result["minimum_packet_count"] = None
    result["packet_count_minimum_established"] = False
    result["numeric_pass"] = bool(result["numeric_pass"] and archive_pass)
    result["verdict"] = (
        "INCONCLUSIVE"
        if not result["numeric_pass"]
        else (
            f"EMERGES—conditional N={result['first_new_forming_count']} ring-family formation in the R0=32 extension"
            if result.get("first_new_forming_count") is not None
            else "DOES NOT EMERGE in the specified R0=32 four-to-six ring-family extension"
        )
    )
    result["complete_physical_matter_formation"] = False
    result["gravitational_capture_established"] = False
    result["physical_size_map_established"] = False
    base.lower_verify.write_json(output_path, result)
    return result


def run_smoke() -> int:
    patch_base()
    return base.run_smoke()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count_extended_v3")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(base.lower_verify.independent_dynamics.json.dumps({
        "output": str(output),
        "numeric_pass": result["numeric_pass"],
        "verdict": result["verdict"],
        "first_new_forming_count": result.get("first_new_forming_count"),
        "historical_lower_lineage_accepted": result["lower_lineage_context"]["historical_lineage_accepted"],
        "archive_pass": result["independent_raw_archive_complete"],
        "method_pass": result["independent_method_pass"],
    }), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
