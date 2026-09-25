#!/usr/bin/env python3
"""Apply recorded private account events to Cassi's reconciliation store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from cassi_account_reconciliation import ACCOUNT_EVENT_SCHEMA, AccountEvent, AccountReconciler
from cassi_market_contracts import digest_value
from cassi_market_ingestion import IngestionStore, atomic_write_json


def _event(value: Mapping[str, Any]) -> AccountEvent:
    document = dict(value)
    if document.pop("schema", None) != ACCOUNT_EVENT_SCHEMA:
        raise ValueError("account event schema mismatch")
    return AccountEvent(
        event_id=str(document["event_id"]),
        venue=str(document["venue"]),
        account_id=str(document["account_id"]),
        event_type=str(document["event_type"]),
        occurred_at=str(document["occurred_at"]),
        available_at=str(document["available_at"]),
        sequence=document.get("sequence"),
        source_revision=str(document.get("source_revision", "private-feed-v1")),
        payload=dict(document["payload"]),
        source_span=dict(document.get("source_span", {})),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("_diag/market-ingestion/market.sqlite3"))
    parser.add_argument("--events", type=Path, required=True, help="JSONL account events from an authenticated feed recorder")
    parser.add_argument("--out", type=Path, default=Path("_diag/market-ingestion/account-reconciliation.json"))
    args = parser.parse_args()
    results: list[dict[str, Any]] = []
    identity: tuple[str, str] | None = None
    with IngestionStore(args.db) as store, AccountReconciler(store) as reconciler:
        with args.events.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    raise SystemExit(f"account event at line {line_number} is not an object")
                event = _event(value)
                current = (event.venue, event.account_id)
                if identity is None:
                    identity = current
                elif identity != current:
                    raise SystemExit("one reconciliation file must contain exactly one venue/account identity")
                results.append(reconciler.apply(event))
        if identity is None:
            raise SystemExit("account event file is empty")
        snapshot = reconciler.snapshot(*identity)
        body: dict[str, Any] = {
            "schema": "cassi.account-reconciliation-command.v1",
            "status": "PASS" if snapshot["reconciled"] else "RECOVERY_REQUIRED",
            "events": len(results),
            "applied": sum(row["status"] == "APPLIED" for row in results),
            "duplicates": sum(row["status"] == "DUPLICATE" for row in results),
            "quarantined": sum(row["status"] == "QUARANTINED" for row in results),
            "results": results,
            "snapshot": snapshot,
            "external_effect": "none",
            "order_submissions": 0,
        }
        body["content_sha256"] = digest_value(body)
        atomic_write_json(args.out, body)
        print(json.dumps(body, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
