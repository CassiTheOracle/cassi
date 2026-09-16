#!/usr/bin/env python3
"""Verify v3 after the complete provenance archive recovery."""
from __future__ import annotations

import argparse
from pathlib import Path

import verify_matter_formation_packet_count_extended_v3 as base

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_extended_v3_recovery_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3_recovery.py"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3_spec.py"
SCHEMA = "matter-formation-packet-count-extended-v3-recovery-verification-v1"
PRIMARY_SCHEMA = "matter-formation-packet-count-extended-v3-recovery-primary-v1"


def patch_base() -> None:
    base.SELF = SELF
    base.PREREG = PREREG
    base.PRIMARY_SOURCE = PRIMARY_SOURCE
    base.SPEC_SOURCE = SPEC_SOURCE
    base.SCHEMA = SCHEMA
    base.PRIMARY_SCHEMA = PRIMARY_SCHEMA
    base.V2_PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v2.py"
    base.V2_VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v2.py"


def run(input_dir: Path, output_path: Path):
    patch_base()
    return base.run(input_dir, output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count_extended_v3_recovery")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    input_dir = args.input.resolve()
    output = (args.output or input_dir / "verification.json").resolve()
    result = run(input_dir, output)
    print(base.base.lower_verify.independent_dynamics.json.dumps({
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
