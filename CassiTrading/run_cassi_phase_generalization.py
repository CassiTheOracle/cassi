from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_phase_generalization import run_phase_generalization


def main() -> int:
    parser = argparse.ArgumentParser(description="Run prospective field-phase prediction across source regimes")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-phase-generalization-v1.json"))
    parser.add_argument("--bars", type=int, default=352)
    args = parser.parse_args()
    receipt = run_phase_generalization(bar_count=args.bars)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
