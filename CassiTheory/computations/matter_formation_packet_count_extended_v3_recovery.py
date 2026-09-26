#!/usr/bin/env python3
"""Rerun v3 with the complete source archive."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import matter_formation_packet_count_extended_v3 as base

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_extended_v3_recovery_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3_spec.py"
VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v3_recovery.py"
V3_PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3.py"
V3_VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v3.py"
V2_PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v2.py"
V2_VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v2.py"
LOWER_PRIMARY = COMPUTATIONS / "matter_formation_packet_count.py"
LOWER_PREREG = COMPUTATIONS / "matter_formation_packet_count_prereg.md"
LOWER_SPEC = COMPUTATIONS / "matter_formation_packet_count_spec.py"
LOWER_VERIFIER = COMPUTATIONS / "verify_matter_formation_packet_count.py"
SCHEMA = "matter-formation-packet-count-extended-v3-recovery-primary-v1"


def patch_base() -> None:
    base.SELF = SELF
    base.PREREG = PREREG
    base.SPEC_SOURCE = SPEC_SOURCE
    base.VERIFIER_SOURCE = VERIFIER_SOURCE
    base.V2_SOURCE = V2_PRIMARY_SOURCE
    base.SCHEMA = SCHEMA


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    paths = (
        SELF, PREREG, SPEC_SOURCE, VERIFIER_SOURCE,
        V3_PRIMARY_SOURCE, V3_VERIFIER_SOURCE, V2_PRIMARY_SOURCE, V2_VERIFIER_SOURCE,
        LOWER_PRIMARY, LOWER_PREREG, LOWER_SPEC, LOWER_VERIFIER,
        base.base.NEUTRAL_SOURCE, base.base.CLOUD_SOURCE,
        base.base.WAVE_SOURCE, base.base.INDEPENDENT_WAVE_SOURCE,
    )
    result: dict[str, str] = {}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        shutil.copyfile(path, source_dir / relative.replace("/", "__"))
        result[relative] = base.base.sha256(path)
    return result


def run_campaign(output: Path):
    patch_base()
    base.snapshot_sources = snapshot_sources
    return base.run_campaign(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count_extended_v3_recovery")
    args = parser.parse_args(argv)
    receipt = run_campaign(args.output.resolve())
    print(base.base.dynamics.json.dumps({
        "output": str(args.output.resolve()),
        "verdict": receipt["verdict"],
        "first_new_forming_count": receipt["first_new_forming_count"],
        "minimum_packet_count": receipt["minimum_packet_count"],
        "numerical_pass": receipt["numerical_pass"],
    }), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
