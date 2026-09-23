#!/usr/bin/env python3
"""Run the bounded CassiPy curriculum and emit its stable receipt."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cassi_python import run_apprenticeship, verify_receipt


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".staging")
    staging.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(staging, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = run_apprenticeship()
    verify_receipt(receipt)
    if args.output:
        _write_receipt(args.output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
