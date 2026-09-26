#!/usr/bin/env python3
"""Source-bound point-core continuation of the G3 autonomous shell run."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE = ROOT / "computations" / "matter_formation_autonomous_shell.py"
PROTOCOL = ROOT / "computations" / "matter-formation-autonomous-shell-g3-point-core-prereg.md"
SCHEMA = "cassi.matter-formation.autonomous-shell-point-core.v1"


def load_base():
    spec = importlib.util.spec_from_file_location("cassi_autonomous_shell_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base source: {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_base()
base.SELF = SELF
base.ACTION_PREREG = PROTOCOL
base.PREREG = PROTOCOL
base.SCHEMA = SCHEMA
base.CORE_SMOOTH = 0.0


def canonical_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, BASE, PROTOCOL):
        target = source_dir / relative(path).replace("/", "__")
        shutil.copyfile(path, target)
        result[relative(path)] = raw_sha(target)
    return result


base.snapshot_sources = snapshot_sources

_write_json_exclusive = base.write_json_exclusive


def write_json_exclusive(path: Path, payload: dict[str, object]) -> None:
    if path.name == "result.json":
        payload = dict(payload)
        payload["verdict"] = str(payload["verdict"]).replace(
            "conditional autonomous radial formation",
            "conditional autonomous point-core radial formation",
        )
        payload["scope"] = (
            "finite-box spherical kappa=-1 covariance with self-consistent scalar "
            "backreaction from a prescribed finite-energy initial shell using the "
            "point-core 1/r radial connection; no continuum or all-sector claim"
        )
    _write_json_exclusive(path, payload)


base.write_json_exclusive = write_json_exclusive



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = base.run(args.output_dir.resolve())
    except (base.FormationError, OSError, ValueError, FloatingPointError, RuntimeError) as exc:
        print(f"point-core primary failed before receipt: {exc}")
        return 1
    print(
        __import__("json").dumps(
            {"output": str(args.output_dir.resolve()), "verdict": receipt["verdict"].replace("conditional autonomous radial formation", "conditional autonomous point-core radial formation"), "numerical_pass": receipt["numerical_pass"]}
        ),
        flush=True,
    )
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
