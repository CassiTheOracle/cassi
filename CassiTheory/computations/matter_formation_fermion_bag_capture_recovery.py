#!/usr/bin/env python3
"""High-temporal-resolution primary recovery for radial fermion-bag capture."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE_PATH = ROOT / "computations" / "matter_formation_fermion_bag_capture.py"
PREREG = ROOT / "computations" / "matter-formation-fermion-bag-capture-recovery-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-bag-capture-recovery.v1"

_spec = importlib.util.spec_from_file_location("cassi_matter_bag_primary_base", BASE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(BASE_PATH)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

_base.SELF = SELF
_base.PREREG = PREREG
_base.SCHEMA = SCHEMA
_base.GRIDS = {
    "G0": (160, 0.1, 0.005),
    "G1": (240, 1.0 / 15.0, 0.0025),
    "G2": (320, 0.05, 0.00125),
}


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG, BASE_PATH):
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        target = source_dir / relative.replace("/", "__")
        target.write_bytes(path.read_bytes())
        result[relative] = _base.raw_sha(target)
    return result


_base.snapshot_sources = snapshot_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = _base.run(args.output_dir.resolve())
    except (FileExistsError, OSError, ValueError, FloatingPointError) as exc:
        print(f"fermion-bag recovery primary failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output_dir.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
