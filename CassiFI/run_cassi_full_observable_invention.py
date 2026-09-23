#!/usr/bin/env python3
"""Run the frozen Cassi full-observable field-invention campaign once."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_full_observable_invention import DEFAULT_CAMPAIGN_KIND, run_full_observable_invention
from cassi_research_organism import ResearchOrganism


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--campaign-kind", default=DEFAULT_CAMPAIGN_KIND)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = args.workspace.resolve(strict=True)
    organism = ResearchOrganism(args.home, workspace=workspace)
    if args.out.exists():
        raise SystemExit(
            f"refusing to overwrite frozen full-observable receipt: {args.out}"
        )
    if not organism.manifest_path.exists():
        organism.initialize()
    receipt = run_full_observable_invention(
        organism,
        workspace=workspace,
        campaign_kind=args.campaign_kind,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
