#!/usr/bin/env python3
"""Run the thinking-enabled Qwen CassiPy teacher bridge."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cassi_python_teacher import run_teacher_bridge, verify_bridge_receipt


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
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8084")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_teacher_bridge(
        args.data_home,
        args.model,
        base_url=args.base_url,
        max_attempts=args.max_attempts,
        max_tokens=args.max_tokens,
    )
    _write_receipt(args.output, receipt)
    verify_bridge_receipt(receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
