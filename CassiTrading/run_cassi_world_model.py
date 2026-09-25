from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_contracts import digest_value
from cassi_trading_foundry import generate_demo_bars
from cassi_world_model import MarketWorldModel, WORLD_MODEL_SCHEMA


RUNNER_SCHEMA = "cassi.market-world-model-run.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the chronological Cassi market world model")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-world-model-v1.json"))
    parser.add_argument("--bars", type=int, default=96)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.bars < 32 or args.batch_size < 1:
        raise SystemExit("--bars must be >= 32 and --batch-size must be positive")

    bars = generate_demo_bars(args.bars)
    events = tuple(
        bar.as_event(source_id="world-model-runner", source_revision="demo-bars.v1")
        for bar in bars
    )
    model = MarketWorldModel()
    updates = []
    for start in range(0, len(events), args.batch_size):
        updates.append(model.update(events[start : start + args.batch_size]))
    body = {
        "schema": RUNNER_SCHEMA,
        "world_model_schema": WORLD_MODEL_SCHEMA,
        "source_event_count": len(events),
        "source_event_root_sha256": digest_value([event.as_dict() for event in events]),
        "updates": updates,
        "snapshot": model.snapshot(),
    }
    body["content_sha256"] = digest_value(body)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": body["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
