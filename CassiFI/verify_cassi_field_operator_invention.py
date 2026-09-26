#!/usr/bin/env python3
"""Independently reconstruct a Cassi field-operator invention receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_field_operator_invention import verify_operator_receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify_operator_receipt(receipt)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
