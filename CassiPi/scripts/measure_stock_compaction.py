"""Account for stock Oh My Pi compaction cost across real local sessions.

Every stock compaction spends one provider call to summarize the current context
and then carries the summary forward. Oh My Pi records both sides of that trade in
its session transcripts: `tokensBefore` (the context the summarizer had to read),
`tokensAfter` (what the session retained), and the summary text itself.

This script reads the local session store and reports the totals, so the field-owned
path's cost can be compared with the ordinary host on the same machine. It reads
transcripts only; it makes no provider call and changes nothing.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any


SESSION_ROOT = Path.home() / ".omp" / "agent" / "sessions"
DEFAULT_RECEIPT = Path(__file__).resolve().parents[1] / "probes" / "receipts" / "stock-compaction-accounting.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan(root: Path, minimum_bytes: int) -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    totals = {"compactions": 0, "tokens_before": 0, "tokens_after": 0, "summary_chars": 0}
    scanned = 0
    for path in sorted(root.rglob("*.jsonl")):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < minimum_bytes:
            continue
        scanned += 1
        events = 0
        before = 0
        after = 0
        summary_chars = 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "tokensBefore" not in line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "compaction":
                    continue
                events += 1
                before += int(entry.get("tokensBefore") or 0)
                after += int(entry.get("tokensAfter") or 0)
                summary_chars += len(str(entry.get("summary") or ""))
        if events == 0:
            continue
        sessions.append(
            {
                "path": str(path),
                "bytes": size,
                "compactions": events,
                "tokens_before": before,
                "tokens_after": after,
                "summary_tokens_est": math.ceil(summary_chars / 4),
            }
        )
        totals["compactions"] += events
        totals["tokens_before"] += before
        totals["tokens_after"] += after
        totals["summary_chars"] += summary_chars
    sessions.sort(key=lambda row: row["tokens_before"], reverse=True)
    return {"sessions": sessions, "totals": totals, "scanned_sessions": scanned}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=SESSION_ROOT, help="Session store root.")
    parser.add_argument("--minimum-bytes", type=int, default=200_000, help="Skip transcripts smaller than this.")
    parser.add_argument("--top", type=int, default=8, help="How many sessions to list individually.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    result = scan(args.root, args.minimum_bytes)
    totals = result["totals"]
    receipt = {
        "schema": "cassipi.stock-compaction-accounting.v1",
        "created_at": _utc_now(),
        "session_root": str(args.root),
        "minimum_bytes": args.minimum_bytes,
        "scanned_sessions": result["scanned_sessions"],
        "sessions_with_compactions": len(result["sessions"]),
        "totals": {
            "compactions": totals["compactions"],
            "provider_input_tokens_spent_summarizing": totals["tokens_before"],
            "tokens_retained_after_compactions": totals["tokens_after"],
            "summary_tokens_est": math.ceil(totals["summary_chars"] / 4),
            "summary_chars": totals["summary_chars"],
        },
        "largest_sessions": result["sessions"][: args.top],
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "receipt": str(args.receipt),
                "sessions_with_compactions": receipt["sessions_with_compactions"],
                **receipt["totals"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
