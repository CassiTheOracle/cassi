"""Condense durable traces into an active shadow-student checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .cassi_condensation import condense
    from .cassi_trace_store import TeacherTraceStore
except ImportError:  # direct script execution
    from cassi_condensation import condense
    from cassi_trace_store import TeacherTraceStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-store", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--active", type=Path, required=True)
    parser.add_argument("--model-sha256", default=None)
    parser.add_argument("--keep-latest-per-session", type=int, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    with TeacherTraceStore(args.trace_store) as store:
        report = condense(store, args.candidate, args.active, model_sha256=args.model_sha256, keep_latest_per_session=args.keep_latest_per_session)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"active": str(args.active), "promotion": "PROMOTE", "source_records": report["source_records"], "heldout": report["heldout"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
