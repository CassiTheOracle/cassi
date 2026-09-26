#!/usr/bin/env python3
"""Run four evidence-grounded laboratories through a persistent Cassi organism."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_research_laboratories import run_laboratories
from cassi_research_organism import ResearchOrganism


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--cosmos-receipt",
        type=Path,
        default=Path("../CassiCosmos/_diag/topology_observatory_live.json"),
    )
    parser.add_argument(
        "--market-csv",
        type=Path,
        default=Path("../CassiTrading/_diag/coinbase-btcusd-1h-2016-to-2023.csv"),
    )
    parser.add_argument(
        "--external-market-csv",
        type=Path,
        default=Path("../CassiTrading/_diag/coinbase-btcusd-1h-2024.csv"),
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    organism = ResearchOrganism(args.home, workspace=args.workspace)
    if not organism.manifest_path.exists():
        organism.initialize()
    receipt = run_laboratories(
        organism,
        cosmos_receipt=args.cosmos_receipt.resolve(strict=True),
        market_csv=args.market_csv.resolve(strict=True),
        external_market_csv=args.external_market_csv.resolve(strict=True),
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
