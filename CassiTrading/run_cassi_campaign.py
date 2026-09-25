from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_campaign import RollingCampaign, RollingCampaignConfig
from cassi_trading_foundry import generate_demo_bars


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the adaptive versus frozen Cassi market campaign")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-rolling-campaign-v1.json"))
    parser.add_argument("--bars", type=int, default=96)
    parser.add_argument("--max-windows", type=int, default=8)
    args = parser.parse_args()
    receipt = RollingCampaign(
        RollingCampaignConfig(max_windows=args.max_windows),
    ).run(generate_demo_bars(args.bars))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
