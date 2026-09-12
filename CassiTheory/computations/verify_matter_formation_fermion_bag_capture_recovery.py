#!/usr/bin/env python3
"""Independent DOP853 verification for the radial recovery campaign."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE_PATH = ROOT / "computations" / "verify_matter_formation_fermion_bag_capture.py"
PRIMARY = ROOT / "computations" / "matter_formation_fermion_bag_capture_recovery.py"
PREREG = ROOT / "computations" / "matter-formation-fermion-bag-capture-recovery-prereg.md"
PRIMARY_BASE_PATH = ROOT / "computations" / "matter_formation_fermion_bag_capture.py"
SCHEMA = "cassi.matter-formation.fermion-bag-capture-recovery-verification.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.fermion-bag-capture-recovery.v1"

_spec = importlib.util.spec_from_file_location("cassi_matter_bag_verifier_base", BASE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(BASE_PATH)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

_base.SELF = SELF
_base.PRIMARY = PRIMARY
_base.PREREG = PREREG
_base.SCHEMA = SCHEMA
_base.PRIMARY_SCHEMA = PRIMARY_SCHEMA
_base.GRIDS = {
    "G0": (160, 0.1, 0.005),
    "G1": (240, 1.0 / 15.0, 0.0025),
    "G2": (320, 0.05, 0.00125),
}


_original_writer = _base.write_json_exclusive
_original_independent_evolve = _base.independent_evolve


def independent_evolve(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
    row, arrays = _original_independent_evolve(*args, **kwargs)
    dt = args[2] if len(args) >= 3 else kwargs["dt"]
    row["dt"] = float(dt)
    return row, arrays


def write_json_exclusive(path: Path, value: dict[str, object]) -> None:
    if path.name == "verification.json" and "identities" in value:
        source_dir = path.parent / "sources"
        for source in (BASE_PATH, PRIMARY, PRIMARY_BASE_PATH):
            relative = source.resolve().relative_to(ROOT.resolve()).as_posix()
            target = source_dir / relative.replace("/", "__")
            shutil.copyfile(source, target)
            value["identities"]["archived_source_sha256"][relative] = _base.raw_sha(target)
    _original_writer(path, value)


_base.independent_evolve = independent_evolve
_base.write_json_exclusive = write_json_exclusive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = _base.run(args.input_dir.resolve(), args.output.resolve())
    except (FileExistsError, OSError, ValueError, RuntimeError) as exc:
        print(f"fermion-bag recovery verifier failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
