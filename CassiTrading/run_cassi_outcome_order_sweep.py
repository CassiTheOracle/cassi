from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_outcome_order_sweep import run_outcome_order_sweep


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure field phase response to outcome order")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-outcome-order-v1.json"))
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    receipt = run_outcome_order_sweep(repeats=args.repeats)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
