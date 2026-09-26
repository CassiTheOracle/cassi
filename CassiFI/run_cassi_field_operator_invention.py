#!/usr/bin/env python3
"""Run the frozen Cassi field-owned operator-invention campaign once."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_field_operator_invention import run_operator_invention
from cassi_research_organism import ResearchOrganism


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = args.workspace.resolve(strict=True)
    organism = ResearchOrganism(args.home, workspace=workspace)
    if not organism.manifest_path.exists():
        organism.initialize()
    receipt = run_operator_invention(organism, workspace=workspace)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
