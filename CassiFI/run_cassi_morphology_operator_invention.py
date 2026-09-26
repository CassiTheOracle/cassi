#!/usr/bin/env python3
"""Run or verify the morphology-aware field-operator campaign exactly once."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_morphology_operator_invention import (
    preflight_morphology_operator,
    run_morphology_operator_invention,
    verify_morphology_operator_receipt,
)
from cassi_research_organism import ResearchOrganism


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--verify", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = args.workspace.resolve(strict=True)
    choices = int(args.preflight) + int(args.verify is not None) + int(args.out is not None)
    if choices != 1:
        raise SystemExit("choose exactly one of --preflight, --verify RECEIPT, or --out RECEIPT")
    if args.preflight:
        print(json.dumps(preflight_morphology_operator(workspace), ensure_ascii=False, sort_keys=True))
        return 0
    if args.verify is not None:
        receipt = json.loads(args.verify.read_text(encoding="utf-8"))
        print(json.dumps(verify_morphology_operator_receipt(receipt), ensure_ascii=False, sort_keys=True))
        return 0
    assert args.out is not None
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite morphology receipt: {args.out}")
    organism = ResearchOrganism(args.home, workspace=workspace)
    if not organism.manifest_path.exists():
        organism.initialize()
    receipt = run_morphology_operator_invention(organism, workspace=workspace)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
