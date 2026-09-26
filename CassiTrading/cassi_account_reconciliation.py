"""Durable private account-event reconciliation without order submission.

This module consumes authenticated-feed records supplied by a venue adapter. It
cannot create, amend, cancel, or submit orders. Venue events are idempotent,
sequence gaps are quarantined, and an authoritative snapshot is required to
recover a divergent account stream.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from cassi_market_contracts import Event, canonical_bytes, digest_value
from cassi_market_ingestion import IngestionError, IngestionStore, parse_utc


ACCOUNT_EVENT_SCHEMA = "cassi.account-event.v1"
ACCOUNT_SNAPSHOT_SCHEMA = "cassi.account-snapshot.v1"
ACCOUNT_RECONCILIATION_SCHEMA = "cassi.account-reconciliation.v1"
_EVENT_TYPES = frozenset({"order", "fill", "balance", "position", "snapshot"})
_ORDER_STATUSES = frozenset({"pending", "open", "partially_filled", "filled", "cancelled", "rejected"})
_ORDER_TRANSITIONS = {
    "pending": frozenset({"pending", "open", "partially_filled", "filled", "cancelled", "rejected"}),
    "open": frozenset({"open", "partially_filled", "filled", "cancelled", "rejected"}),
    "partially_filled": frozenset({"partially_filled", "filled", "cancelled"}),
    "filled": frozenset({"filled"}),
    "cancelled": frozenset({"cancelled"}),
    "rejected": frozenset({"rejected"}),
}


class AccountReconciliationError(IngestionError):
    """A private account event cannot safely advance local account truth."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AccountReconciliationError(f"{name} must be nonempty text")
    return value


def _decimal(name: str, value: Any, *, minimum: Decimal | None = Decimal("0")) -> Decimal:
    if isinstance(value, bool):
        raise AccountReconciliationError(f"{name} must be decimal-compatible")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AccountReconciliationError(f"{name} must be decimal-compatible") from exc
    if not result.is_finite() or (minimum is not None and result < minimum):
        raise AccountReconciliationError(f"{name} is outside its valid range")
    return result


def _decimal_text(name: str, value: Any, *, minimum: Decimal | None = Decimal("0")) -> str:
    return format(_decimal(name, value, minimum=minimum), "f")


@dataclass(frozen=True, slots=True)
class AccountEvent:
    event_id: str
    venue: str
    account_id: str
    event_type: str
    occurred_at: str
    available_at: str
    payload: Mapping[str, Any]
    sequence: int | None = None
    source_revision: str = "private-feed-v1"
    source_span: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("event_id", "venue", "account_id", "event_type", "occurred_at", "available_at", "source_revision"):
            _text(name, getattr(self, name))
        if self.event_type not in _EVENT_TYPES:
            raise AccountReconciliationError(f"unsupported account event type: {self.event_type}")
        parse_utc(self.occurred_at)
        parse_utc(self.available_at)
        if parse_utc(self.available_at) < parse_utc(self.occurred_at):
            raise AccountReconciliationError("account event became available before it occurred")
        if self.sequence is not None and (
            isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0
        ):
            raise AccountReconciliationError("account event sequence must be a nonnegative integer")
        canonical_bytes(dict(self.payload))
        canonical_bytes(dict(self.source_span))
    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": ACCOUNT_EVENT_SCHEMA,
            "event_id": self.event_id,
            "venue": self.venue,
            "account_id": self.account_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "available_at": self.available_at,
            "sequence": self.sequence,
            "source_revision": self.source_revision,
            "payload": dict(self.payload),
            "source_span": dict(self.source_span),
        }

    def canonical_event(self, *, raw_id: int) -> Event:
        subject = str(self.payload.get("product") or self.payload.get("currency") or self.account_id)
        return Event(
            event_id=f"{self.venue}-private:{self.event_id}",
            source_id=f"{self.venue}-private",
            source_revision=self.source_revision,
            observed_at=self.occurred_at,
            available_at=self.available_at,
            event_type=f"account-{self.event_type}",
            subject_ids=(subject,),
            payload=self.as_dict(),
            coordinate_frame="venue-account-native",
            source_span={**dict(self.source_span), "raw_id": raw_id},
        )


class AccountReconciler:
    def __init__(self, store: IngestionStore) -> None:
        self.store = store
        self._db = sqlite3.connect(store.path, timeout=30.0, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=30000")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS account_event_log (
                event_id TEXT PRIMARY KEY,
                venue TEXT NOT NULL,
                account_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                sequence_value INTEGER,
                state TEXT NOT NULL CHECK(state IN ('applied', 'quarantined')),
                reason TEXT,
                occurred_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                document_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS account_event_sequence_idx
                ON account_event_log(venue, account_id, sequence_value);

            CREATE TABLE IF NOT EXISTS account_stream_state (
                venue TEXT NOT NULL,
                account_id TEXT NOT NULL,
                last_sequence INTEGER,
                reconciled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(venue, account_id)
            );

            CREATE TABLE IF NOT EXISTS account_orders (
                venue TEXT NOT NULL,
                account_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                product TEXT NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_size TEXT NOT NULL,
                filled_size TEXT NOT NULL,
                limit_price TEXT,
                updated_at TEXT NOT NULL,
                last_sequence INTEGER,
                PRIMARY KEY(venue, account_id, order_id)
            );

            CREATE TABLE IF NOT EXISTS account_fills (
                venue TEXT NOT NULL,
                account_id TEXT NOT NULL,
                fill_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                product TEXT NOT NULL,
                side TEXT NOT NULL,
                size TEXT NOT NULL,
                price TEXT NOT NULL,
                fee TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                sequence_value INTEGER,
                PRIMARY KEY(venue, account_id, fill_id)
            );

            CREATE TABLE IF NOT EXISTS account_balances (
                venue TEXT NOT NULL,
                account_id TEXT NOT NULL,
                currency TEXT NOT NULL,
                total TEXT NOT NULL,
                available TEXT NOT NULL,
                hold TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_sequence INTEGER,
                PRIMARY KEY(venue, account_id, currency)
            );

            CREATE TABLE IF NOT EXISTS account_positions (
                venue TEXT NOT NULL,
                account_id TEXT NOT NULL,
                product TEXT NOT NULL,
                size TEXT NOT NULL,
                entry_price TEXT,
                updated_at TEXT NOT NULL,
                last_sequence INTEGER,
                PRIMARY KEY(venue, account_id, product)
            );
            """
        )

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "AccountReconciler":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _stream_row(self, event: AccountEvent) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM account_stream_state WHERE venue = ? AND account_id = ?",
            (event.venue, event.account_id),
        ).fetchone()

    def _log(self, event: AccountEvent, *, state: str, reason: str | None) -> None:
        self._db.execute(
            "INSERT INTO account_event_log(event_id, venue, account_id, event_type, sequence_value, state, reason, "
            "occurred_at, available_at, document_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.venue,
                event.account_id,
                event.event_type,
                event.sequence,
                state,
                reason,
                event.occurred_at,
                event.available_at,
                canonical_bytes(event.as_dict()).decode("utf-8"),
            ),
        )

    def _quarantine(self, event: AccountEvent, reason: str) -> dict[str, Any]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._log(event, state="quarantined", reason=reason)
            self._db.execute(
                "INSERT INTO account_stream_state(venue, account_id, last_sequence, reconciled, updated_at) "
                "VALUES(?, ?, NULL, 0, ?) ON CONFLICT(venue, account_id) DO UPDATE SET reconciled = 0, updated_at = excluded.updated_at",
                (event.venue, event.account_id, event.available_at),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        self.store.set_state("account_reconciled", False, at=event.available_at)
        self.store.set_state("account_recovery_required", True, at=event.available_at)
        self.store.increment_metric("account_events_quarantined")
        return {"status": "QUARANTINED", "event_id": event.event_id, "reason": reason}

    def apply(self, event: AccountEvent) -> dict[str, Any]:
        existing = self._db.execute(
            "SELECT state, reason FROM account_event_log WHERE event_id = ?", (event.event_id,)
        ).fetchone()
        if existing is not None:
            self.store.increment_metric("account_event_duplicates")
            return {
                "status": "DUPLICATE",
                "event_id": event.event_id,
                "original_state": str(existing["state"]),
                "reason": existing["reason"],
            }
        raw = self.store.capture_raw(
            source_id=f"{event.venue}-private",
            session_id=f"account:{event.account_id}",
            channel=f"account:{event.event_type}",
            payload=event.as_dict(),
            sequence=event.sequence,
            observed_at=event.occurred_at,
            received_at=event.available_at,
        )
        canonical = event.canonical_event(raw_id=raw.raw_id)
        canonical_result = self.store.ingest_event(
            canonical,
            natural_key=f"account|{event.venue}|{event.account_id}|{event.event_id}",
            raw_id=raw.raw_id,
            semantic_value=event.as_dict(),
        )
        if canonical_result.status == "conflict":
            return self._quarantine(event, "canonical-account-event-conflict")

        stream = self._stream_row(event)
        previous_sequence = None if stream is None or stream["last_sequence"] is None else int(stream["last_sequence"])
        if event.event_type != "snapshot" and event.sequence is not None and previous_sequence is not None:
            if event.sequence <= previous_sequence:
                return self._quarantine(event, "out-of-order-account-sequence")
            if event.sequence != previous_sequence + 1:
                return self._quarantine(event, "account-sequence-gap")

        self._db.execute("BEGIN IMMEDIATE")
        try:
            if event.event_type == "order":
                self._apply_order(event)
            elif event.event_type == "fill":
                self._apply_fill(event)
            elif event.event_type == "balance":
                self._apply_balance(event)
            elif event.event_type == "position":
                self._apply_position(event)
            else:
                self._apply_snapshot(event)
            self._log(event, state="applied", reason=None)
            reconciled = 1 if event.event_type == "snapshot" else (0 if stream is None else int(stream["reconciled"]))
            self._db.execute(
                "INSERT INTO account_stream_state(venue, account_id, last_sequence, reconciled, updated_at) "
                "VALUES(?, ?, ?, ?, ?) ON CONFLICT(venue, account_id) DO UPDATE SET "
                "last_sequence = excluded.last_sequence, reconciled = excluded.reconciled, updated_at = excluded.updated_at",
                (event.venue, event.account_id, event.sequence, reconciled, event.available_at),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        self.store.increment_metric("account_events_applied")
        if event.event_type == "snapshot":
            self.store.set_state("account_reconciled", True, at=event.available_at)
            self.store.set_state("account_recovery_required", False, at=event.available_at)
        snapshot = self.snapshot(event.venue, event.account_id)
        return {
            "status": "APPLIED",
            "event_id": event.event_id,
            "event_type": event.event_type,
            "sequence": event.sequence,
            "account_sha256": snapshot["content_sha256"],
        }

    def _apply_order(self, event: AccountEvent) -> None:
        payload = event.payload
        order_id = _text("order_id", payload.get("order_id"))
        product = _text("product", payload.get("product"))
        side = _text("side", payload.get("side")).lower()
        if side not in {"buy", "sell"}:
            raise AccountReconciliationError("order side must be buy or sell")
        status = _text("status", payload.get("status")).lower()
        if status not in _ORDER_STATUSES:
            raise AccountReconciliationError("unknown order status")
        requested_size = _decimal_text("requested_size", payload.get("requested_size"))
        filled_size = _decimal_text("filled_size", payload.get("filled_size", "0"))
        if Decimal(filled_size) > Decimal(requested_size):
            raise AccountReconciliationError("order filled size exceeds requested size")
        limit_price = payload.get("limit_price")
        normalized_price = None if limit_price is None else _decimal_text("limit_price", limit_price)
        previous = self._db.execute(
            "SELECT status FROM account_orders WHERE venue = ? AND account_id = ? AND order_id = ?",
            (event.venue, event.account_id, order_id),
        ).fetchone()
        if previous is not None and status not in _ORDER_TRANSITIONS[str(previous["status"])]:
            raise AccountReconciliationError(f"order status regressed from {previous['status']} to {status}")
        self._db.execute(
            "INSERT INTO account_orders(venue, account_id, order_id, product, side, status, requested_size, filled_size, "
            "limit_price, updated_at, last_sequence) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(venue, account_id, order_id) DO UPDATE SET product = excluded.product, side = excluded.side, "
            "status = excluded.status, requested_size = excluded.requested_size, filled_size = excluded.filled_size, "
            "limit_price = excluded.limit_price, updated_at = excluded.updated_at, last_sequence = excluded.last_sequence",
            (
                event.venue,
                event.account_id,
                order_id,
                product,
                side,
                status,
                requested_size,
                filled_size,
                normalized_price,
                event.available_at,
                event.sequence,
            ),
        )

    def _apply_fill(self, event: AccountEvent) -> None:
        payload = event.payload
        fill_id = _text("fill_id", payload.get("fill_id"))
        order_id = _text("order_id", payload.get("order_id"))
        product = _text("product", payload.get("product"))
        side = _text("side", payload.get("side")).lower()
        if side not in {"buy", "sell"}:
            raise AccountReconciliationError("fill side must be buy or sell")
        self._db.execute(
            "INSERT INTO account_fills(venue, account_id, fill_id, order_id, product, side, size, price, fee, occurred_at, sequence_value) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.venue,
                event.account_id,
                fill_id,
                order_id,
                product,
                side,
                _decimal_text("size", payload.get("size")),
                _decimal_text("price", payload.get("price")),
                _decimal_text("fee", payload.get("fee", "0")),
                event.occurred_at,
                event.sequence,
            ),
        )

    def _apply_balance(self, event: AccountEvent) -> None:
        payload = event.payload
        currency = _text("currency", payload.get("currency"))
        total = _decimal("total", payload.get("total"))
        available = _decimal("available", payload.get("available"))
        hold = _decimal("hold", payload.get("hold"))
        if total != available + hold:
            raise AccountReconciliationError("balance total must equal available plus hold")
        self._db.execute(
            "INSERT INTO account_balances(venue, account_id, currency, total, available, hold, updated_at, last_sequence) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(venue, account_id, currency) DO UPDATE SET "
            "total = excluded.total, available = excluded.available, hold = excluded.hold, "
            "updated_at = excluded.updated_at, last_sequence = excluded.last_sequence",
            (
                event.venue,
                event.account_id,
                currency,
                format(total, "f"),
                format(available, "f"),
                format(hold, "f"),
                event.available_at,
                event.sequence,
            ),
        )

    def _apply_position(self, event: AccountEvent) -> None:
        payload = event.payload
        product = _text("product", payload.get("product"))
        size = _decimal_text("size", payload.get("size"), minimum=None)
        entry = payload.get("entry_price")
        entry_price = None if entry is None else _decimal_text("entry_price", entry)
        self._db.execute(
            "INSERT INTO account_positions(venue, account_id, product, size, entry_price, updated_at, last_sequence) "
            "VALUES(?, ?, ?, ?, ?, ?, ?) ON CONFLICT(venue, account_id, product) DO UPDATE SET "
            "size = excluded.size, entry_price = excluded.entry_price, updated_at = excluded.updated_at, "
            "last_sequence = excluded.last_sequence",
            (event.venue, event.account_id, product, size, entry_price, event.available_at, event.sequence),
        )

    def _apply_snapshot(self, event: AccountEvent) -> None:
        payload = event.payload
        orders = payload.get("orders", [])
        fills = payload.get("fills", [])
        balances = payload.get("balances", [])
        positions = payload.get("positions", [])
        if any(not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) for rows in (orders, fills, balances, positions)):
            raise AccountReconciliationError("account snapshot collections must be arrays")
        for table in ("account_orders", "account_fills", "account_balances", "account_positions"):
            self._db.execute(f"DELETE FROM {table} WHERE venue = ? AND account_id = ?", (event.venue, event.account_id))
        for index, row in enumerate(orders):
            if not isinstance(row, Mapping):
                raise AccountReconciliationError("account snapshot order must be an object")
            self._apply_order(self._nested_event(event, "order", index, row))
        for index, row in enumerate(fills):
            if not isinstance(row, Mapping):
                raise AccountReconciliationError("account snapshot fill must be an object")
            self._apply_fill(self._nested_event(event, "fill", index, row))
        for index, row in enumerate(balances):
            if not isinstance(row, Mapping):
                raise AccountReconciliationError("account snapshot balance must be an object")
            self._apply_balance(self._nested_event(event, "balance", index, row))
        for index, row in enumerate(positions):
            if not isinstance(row, Mapping):
                raise AccountReconciliationError("account snapshot position must be an object")
            self._apply_position(self._nested_event(event, "position", index, row))

    @staticmethod
    def _nested_event(parent: AccountEvent, event_type: str, index: int, payload: Mapping[str, Any]) -> AccountEvent:
        return AccountEvent(
            event_id=f"{parent.event_id}:{event_type}:{index}",
            venue=parent.venue,
            account_id=parent.account_id,
            event_type=event_type,
            occurred_at=parent.occurred_at,
            available_at=parent.available_at,
            sequence=parent.sequence,
            source_revision=parent.source_revision,
            payload=dict(payload),
            source_span=parent.source_span,
        )

    def snapshot(self, venue: str, account_id: str) -> dict[str, Any]:
        _text("venue", venue)
        _text("account_id", account_id)

        def rows(table: str, order: str) -> list[dict[str, Any]]:
            return [
                {key: row[key] for key in row.keys() if key not in {"venue", "account_id"}}
                for row in self._db.execute(
                    f"SELECT * FROM {table} WHERE venue = ? AND account_id = ? ORDER BY {order}",
                    (venue, account_id),
                )
            ]

        stream = self._db.execute(
            "SELECT last_sequence, reconciled, updated_at FROM account_stream_state WHERE venue = ? AND account_id = ?",
            (venue, account_id),
        ).fetchone()
        body: dict[str, Any] = {
            "schema": ACCOUNT_SNAPSHOT_SCHEMA,
            "venue": venue,
            "account_id": account_id,
            "last_sequence": None if stream is None else stream["last_sequence"],
            "reconciled": False if stream is None else bool(stream["reconciled"]),
            "updated_at": None if stream is None else stream["updated_at"],
            "orders": rows("account_orders", "order_id"),
            "fills": rows("account_fills", "fill_id"),
            "balances": rows("account_balances", "currency"),
            "positions": rows("account_positions", "product"),
        }
        body["content_sha256"] = digest_value(body)
        return body

    def compare_snapshot(
        self,
        venue: str,
        account_id: str,
        authoritative: Mapping[str, Any],
    ) -> dict[str, Any]:
        local = self.snapshot(venue, account_id)
        differences: list[dict[str, Any]] = []
        for collection, key in (
            ("orders", "order_id"),
            ("fills", "fill_id"),
            ("balances", "currency"),
            ("positions", "product"),
        ):
            expected_rows = authoritative.get(collection, [])
            if not isinstance(expected_rows, Sequence) or isinstance(expected_rows, (str, bytes)):
                raise AccountReconciliationError(f"authoritative {collection} must be an array")
            expected = {str(row[key]): dict(row) for row in expected_rows if isinstance(row, Mapping) and key in row}
            actual = {str(row[key]): dict(row) for row in local[collection]}
            if expected != actual:
                differences.append({"collection": collection, "expected": expected, "actual": actual})
        body: dict[str, Any] = {
            "schema": ACCOUNT_RECONCILIATION_SCHEMA,
            "venue": venue,
            "account_id": account_id,
            "status": "MATCH" if not differences else "MISMATCH",
            "differences": differences,
            "local_snapshot_sha256": local["content_sha256"],
        }
        body["content_sha256"] = digest_value(body)
        self.store.set_state("account_reconciled", not differences)
        self.store.set_state("account_recovery_required", bool(differences))
        return body


__all__ = [
    "ACCOUNT_EVENT_SCHEMA",
    "ACCOUNT_RECONCILIATION_SCHEMA",
    "ACCOUNT_SNAPSHOT_SCHEMA",
    "AccountEvent",
    "AccountReconciler",
    "AccountReconciliationError",
]
