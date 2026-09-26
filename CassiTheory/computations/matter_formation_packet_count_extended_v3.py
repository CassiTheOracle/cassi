#!/usr/bin/env python3
"""Run the overlap-repaired axisymmetric four-to-six packet extension."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import matter_formation_packet_count_extended_v2 as base
from matter_formation_packet_count_extended_v3_spec import *  # noqa: F401,F403

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_extended_v3_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v3_spec.py"
VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v3.py"
V2_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_v2.py"
LOWER_PRIMARY = COMPUTATIONS / "matter_formation_packet_count.py"
LOWER_PREREG = COMPUTATIONS / "matter_formation_packet_count_prereg.md"
LOWER_SPEC = COMPUTATIONS / "matter_formation_packet_count_spec.py"
LOWER_VERIFIER = COMPUTATIONS / "verify_matter_formation_packet_count.py"
SCHEMA = "matter-formation-packet-count-extended-v3-primary-v1"


def patch_base() -> None:
    names = (
        "ARM_SPECS", "ARMS", "CANDIDATE_ARMS", "COMPARISON_OBSERVABLES", "CONTROL_ARMS",
        "GEOMETRIES", "GRID_SPECS", "INITIAL_CORE_FRACTION_MAX", "INITIAL_OVERLAP_MAX",
        "LATE_START", "R0", "RETAINED_FRACTION", "SAMPLE_DT", "SHARE_TOL", "SNAPSHOT_TIMES",
        "T_FINAL", "TOTAL_CHARGE", "WAVE_NUMBER", "WIDTH", "BINDING_RATIO_MAX",
    )
    for name in names:
        setattr(base, name, globals()[name])
    base.SELF = SELF
    base.PREREG = PREREG
    base.SPEC_SOURCE = SPEC_SOURCE
    base.VERIFIER_SOURCE = VERIFIER_SOURCE
    base.BASE_PRIMARY_SOURCE = LOWER_PRIMARY
    base.BASE_PREREG = LOWER_PREREG
    base.BASE_SPEC = LOWER_SPEC
    base.BASE_VERIFIER = LOWER_VERIFIER
    base.SCHEMA = SCHEMA
    base.GEOMETRIES = GEOMETRIES


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    paths = (
        SELF, PREREG, SPEC_SOURCE, VERIFIER_SOURCE, V2_SOURCE,
        LOWER_PRIMARY, LOWER_PREREG, LOWER_SPEC, LOWER_VERIFIER,
        base.NEUTRAL_SOURCE, base.CLOUD_SOURCE, base.WAVE_SOURCE, base.INDEPENDENT_WAVE_SOURCE,
    )
    result: dict[str, str] = {}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        shutil.copyfile(path, source_dir / relative.replace("/", "__"))
        result[relative] = base.sha256(path)
    return result


def run_campaign(output: Path) -> dict[str, Any]:
    patch_base()
    base.snapshot_sources = snapshot_sources
    return base.run_campaign(output)


def run_smoke() -> int:
    patch_base()
    return base.run_smoke()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count_extended_v3")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(base.dynamics.json.dumps({
        "output": str(args.output.resolve()),
        "verdict": receipt["verdict"],
        "first_new_forming_count": receipt["first_new_forming_count"],
        "minimum_packet_count": receipt["minimum_packet_count"],
        "numerical_pass": receipt["numerical_pass"],
    }), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
