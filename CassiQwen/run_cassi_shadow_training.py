"""Train an L23 shadow-student candidate from the durable trace journal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .cassi_shadow_student import train_candidate
    from .cassi_trace_store import TeacherTraceStore
except ImportError:  # direct script execution
    from cassi_shadow_student import train_candidate
    from cassi_trace_store import TeacherTraceStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-sha256", default=None)
    args = parser.parse_args()
    with TeacherTraceStore(args.trace_store) as store:
        checkpoint = train_candidate(store, args.output, model_sha256=args.model_sha256)
    print(json.dumps({"student": str(args.output), "status": checkpoint["status"], "trained_records": checkpoint["trained_records"], "labels": len(checkpoint["prototypes"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
