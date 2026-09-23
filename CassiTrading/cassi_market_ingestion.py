"""Durable, provenance-preserving market ingestion and health monitoring.

The host owns exact source messages, normalization, reconciliation, delivery
watermarks, and operational health.  Cassi receives only accepted canonical
market events.  This module deliberately has no order-submission capability.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, TYPE_CHECKING

from cassi_market_contracts import EVENT_SCHEMA, Event, canonical_bytes, digest_value
from cassi_trading_field import MarketBar

if TYPE_CHECKING:
    from cassi_paper import PaperSession


RAW_RECORDING_SCHEMA = "cassi.market-raw-recording.v1"
HEALTH_SCHEMA = "cassi.market-data-health.v1"
RECONCILIATION_SCHEMA = "cassi.market-reconciliation.v1"
PAPER_CONSUMER_SCHEMA = "cassi.market-paper-consumer.v1"
_SUPPORTED_GRANULARITIES = frozenset({60, 300, 900, 3600, 21600, 86400})


class IngestionError(ValueError):
    """Market data cannot be safely admitted or recovered."""


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise IngestionError("timestamp must be nonempty text")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise IngestionError(f"timestamp is not ISO-8601: {value}") from exc
    if parsed.tzinfo is None:
        raise IngestionError(f"timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def utc_stamp(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise IngestionError("UTC timestamp source must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def bucket_start(value: datetime, granularity: int) -> datetime:
    if granularity not in _SUPPORTED_GRANULARITIES:
        raise IngestionError("unsupported candle granularity")
    epoch = int(value.astimezone(timezone.utc).timestamp())
    return datetime.fromtimestamp(epoch - epoch % granularity, tz=timezone.utc)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _event_from_document(document: Mapping[str, Any]) -> Event:
    value = dict(document)
    if value.pop("schema", None) != EVENT_SCHEMA:
        raise IngestionError("stored canonical event schema mismatch")
    for name in ("subject_ids",):
        value[name] = tuple(value[name])
    return Event(**value)


def _bar_from_event(event: Event) -> MarketBar:
    if event.event_type != "market-bar":
        raise IngestionError("canonical event is not a market bar")
    try:
        return MarketBar(**dict(event.payload))
    except (TypeError, ValueError) as exc:
        raise IngestionError("canonical market bar payload is invalid") from exc


@dataclass(frozen=True, slots=True)
class RawCapture:
    raw_id: int
    source_id: str
    session_id: str
    channel: str
    sequence: str | None
    observed_at: str | None
    received_at: str
    received_monotonic_ns: int
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class IngestResult:
    status: str
    event: Event
    natural_key: str
    semantic_sha256: str
    raw_id: int | None
    seen_count: int


@dataclass(frozen=True, slots=True)
class HealthPolicy:
    heartbeat_yellow_seconds: float = 5.0
    heartbeat_red_seconds: float = 15.0
    market_yellow_seconds: float = 30.0
    market_red_seconds: float = 120.0
    reconcile_yellow_seconds: float = 90.0
    reconcile_red_seconds: float = 300.0
    exchange_time_delta_yellow_seconds: float = 5.0
    exchange_time_delta_red_seconds: float = 30.0
    backlog_yellow: int = 8
    backlog_red: int = 48
    disk_yellow_bytes: int = 2 * 1024**3
    disk_red_bytes: int = 512 * 1024**2

    def __post_init__(self) -> None:
        pairs = (
            ("heartbeat", self.heartbeat_yellow_seconds, self.heartbeat_red_seconds),
            ("market", self.market_yellow_seconds, self.market_red_seconds),
            ("reconcile", self.reconcile_yellow_seconds, self.reconcile_red_seconds),
            (
                "exchange-time-delta",
                self.exchange_time_delta_yellow_seconds,
                self.exchange_time_delta_red_seconds,
            ),
        )
        for name, yellow, red in pairs:
            if not math.isfinite(yellow) or not math.isfinite(red) or yellow <= 0.0 or red <= yellow:
                raise IngestionError(f"{name} health thresholds must satisfy 0 < yellow < red")
        if self.backlog_yellow < 1 or self.backlog_red <= self.backlog_yellow:
            raise IngestionError("backlog thresholds must satisfy 0 < yellow < red")
        if self.disk_red_bytes < 1 or self.disk_yellow_bytes <= self.disk_red_bytes:
            raise IngestionError("disk thresholds must satisfy 0 < red < yellow")


@dataclass(frozen=True, slots=True)
class DataHealth:
    state: str
    evaluated_at: str
    reasons: tuple[Mapping[str, Any], ...]
    metrics: Mapping[str, Any]
    can_observe: bool
    can_open_exposure: bool
    content_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": HEALTH_SCHEMA,
            "state": self.state,
            "evaluated_at": self.evaluated_at,
            "reasons": [dict(row) for row in self.reasons],
            "metrics": dict(self.metrics),
            "can_observe": self.can_observe,
            "can_open_exposure": self.can_open_exposure,
            "content_sha256": self.content_sha256,
        }


class IngestionStore:
    """SQLite/WAL authority for raw source data and canonical market events."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=30000")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS raw_messages (
                raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                sequence_value TEXT,
                observed_at TEXT,
                received_at TEXT NOT NULL,
                received_monotonic_ns INTEGER NOT NULL,
                payload_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS raw_source_channel_idx
                ON raw_messages(source_id, channel, raw_id);

            CREATE TABLE IF NOT EXISTS canonical_events (
                event_id TEXT PRIMARY KEY,
                natural_key TEXT NOT NULL,
                semantic_sha256 TEXT NOT NULL,
                source_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('accepted', 'conflict', 'superseded')),
                seen_count INTEGER NOT NULL DEFAULT 1,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                raw_id INTEGER REFERENCES raw_messages(raw_id),
                document_json TEXT NOT NULL,
                UNIQUE(natural_key, semantic_sha256)
            );
            CREATE INDEX IF NOT EXISTS canonical_natural_idx
                ON canonical_events(natural_key, state);
            CREATE INDEX IF NOT EXISTS canonical_type_time_idx
                ON canonical_events(event_type, observed_at);

            CREATE TABLE IF NOT EXISTS accepted_events (
                natural_key TEXT PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE REFERENCES canonical_events(event_id)
            );

            CREATE TABLE IF NOT EXISTS deliveries (
                consumer_id TEXT NOT NULL,
                event_id TEXT NOT NULL REFERENCES canonical_events(event_id),
                processed_at TEXT NOT NULL,
                disposition TEXT NOT NULL,
                receipt_sha256 TEXT,
                PRIMARY KEY(consumer_id, event_id)
            );

            CREATE TABLE IF NOT EXISTS state (
                name TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metrics (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reconciliations (
                reconciliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                natural_key TEXT NOT NULL,
                previous_event_id TEXT,
                selected_event_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                reconciled_at TEXT NOT NULL,
                receipt_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS health_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluated_at TEXT NOT NULL,
                state TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                document_json TEXT NOT NULL
            );
            """
        )

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "IngestionStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def increment_metric(self, name: str, amount: int = 1) -> int:
        if not isinstance(name, str) or not name.strip():
            raise IngestionError("metric name must be nonempty text")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise IngestionError("metric increment must be an integer")
        self._db.execute(
            "INSERT INTO metrics(name, value) VALUES(?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = value + excluded.value",
            (name, amount),
        )
        row = self._db.execute("SELECT value FROM metrics WHERE name = ?", (name,)).fetchone()
        return int(row["value"])

    def metric(self, name: str) -> int:
        row = self._db.execute("SELECT value FROM metrics WHERE name = ?", (name,)).fetchone()
        return 0 if row is None else int(row["value"])

    def metrics(self) -> dict[str, int]:
        return {str(row["name"]): int(row["value"]) for row in self._db.execute("SELECT name, value FROM metrics")}

    def set_state(self, name: str, value: Any, *, at: str | None = None) -> None:
        if not isinstance(name, str) or not name.strip():
            raise IngestionError("state name must be nonempty text")
        payload = canonical_bytes(value).decode("utf-8")
        stamp = at or utc_stamp()
        parse_utc(stamp)
        self._db.execute(
            "INSERT INTO state(name, value_json, updated_at) VALUES(?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at",
            (name, payload, stamp),
        )

    def get_state(self, name: str, default: Any = None) -> Any:
        row = self._db.execute("SELECT value_json FROM state WHERE name = ?", (name,)).fetchone()
        return default if row is None else json.loads(str(row["value_json"]))

    def state_updated_at(self, name: str) -> str | None:
        row = self._db.execute("SELECT updated_at FROM state WHERE name = ?", (name,)).fetchone()
        return None if row is None else str(row["updated_at"])

    def note_activity(self, name: str, *, at: str | None = None, value: Any = True) -> None:
        stamp = at or utc_stamp()
        self.set_state(f"activity:{name}", {"at": stamp, "value": value}, at=stamp)

    def activity_at(self, name: str) -> str | None:
        value = self.get_state(f"activity:{name}")
        return str(value["at"]) if isinstance(value, Mapping) and value.get("at") else None

    def capture_raw(
        self,
        *,
        source_id: str,
        session_id: str,
        channel: str,
        payload: Any,
        sequence: str | int | None = None,
        observed_at: str | None = None,
        received_at: str | None = None,
        received_monotonic_ns: int | None = None,
    ) -> RawCapture:
        for name, value in (("source_id", source_id), ("session_id", session_id), ("channel", channel)):
            if not isinstance(value, str) or not value.strip():
                raise IngestionError(f"{name} must be nonempty text")
        if observed_at is not None:
            parse_utc(observed_at)
        received = received_at or utc_stamp()
        parse_utc(received)
        monotonic_ns = time.monotonic_ns() if received_monotonic_ns is None else int(received_monotonic_ns)
        payload_bytes = canonical_bytes(payload)
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        cursor = self._db.execute(
            "INSERT INTO raw_messages(source_id, session_id, channel, sequence_value, observed_at, "
            "received_at, received_monotonic_ns, payload_sha256, payload_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                session_id,
                channel,
                None if sequence is None else str(sequence),
                observed_at,
                received,
                monotonic_ns,
                payload_sha256,
                payload_bytes.decode("utf-8"),
            ),
        )
        raw_id = cursor.lastrowid
        if raw_id is None:
            raise IngestionError("raw capture did not produce a durable row ID")
        self.increment_metric("raw_messages")
        self.note_activity("raw", at=received, value={"source_id": source_id, "channel": channel})
        return RawCapture(
            raw_id=int(raw_id),
            source_id=source_id,
            session_id=session_id,
            channel=channel,
            sequence=None if sequence is None else str(sequence),
            observed_at=observed_at,
            received_at=received,
            received_monotonic_ns=monotonic_ns,
            payload_sha256=payload_sha256,
        )

    def _stored_event(self, row: sqlite3.Row) -> Event:
        return _event_from_document(json.loads(str(row["document_json"])))

    def ingest_event(
        self,
        event: Event,
        *,
        natural_key: str,
        raw_id: int | None,
        semantic_value: Any | None = None,
        promote_after_confirmations: int | None = None,
        promotion_reason: str = "confirmed source revision",
    ) -> IngestResult:
        if not natural_key.strip():
            raise IngestionError("event natural key must be nonempty")
        semantic_sha256 = digest_value(event.payload if semantic_value is None else semantic_value)
        stamp = event.available_at
        parse_utc(event.observed_at)
        parse_utc(event.available_at)
        existing = self._db.execute(
            "SELECT * FROM canonical_events WHERE natural_key = ? AND semantic_sha256 = ?",
            (natural_key, semantic_sha256),
        ).fetchone()
        if existing is not None:
            seen_count = int(existing["seen_count"]) + 1
            self._db.execute(
                "UPDATE canonical_events SET seen_count = ?, last_seen_at = ?, raw_id = COALESCE(?, raw_id) WHERE event_id = ?",
                (seen_count, stamp, raw_id, existing["event_id"]),
            )
            self.increment_metric("canonical_duplicates")
            status = "duplicate"
            stored = self._stored_event(existing)
            if (
                str(existing["state"]) == "conflict"
                and promote_after_confirmations is not None
                and seen_count >= promote_after_confirmations
            ):
                self.promote_event(
                    natural_key,
                    str(existing["event_id"]),
                    reason=promotion_reason,
                    reconciled_at=stamp,
                )
                status = "promoted"
                self.increment_metric("canonical_promotions")
            return IngestResult(status, stored, natural_key, semantic_sha256, raw_id, seen_count)

        collision = self._db.execute(
            "SELECT natural_key, semantic_sha256 FROM canonical_events WHERE event_id = ?", (event.event_id,)
        ).fetchone()
        if collision is not None:
            raise IngestionError("event ID collides with different canonical content")
        accepted = self._db.execute(
            "SELECT event_id FROM accepted_events WHERE natural_key = ?", (natural_key,)
        ).fetchone()
        state = "accepted" if accepted is None else "conflict"
        subject_id = event.subject_ids[0] if event.subject_ids else "-"
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "INSERT INTO canonical_events(event_id, natural_key, semantic_sha256, source_id, event_type, "
                "subject_id, observed_at, available_at, state, seen_count, first_seen_at, last_seen_at, raw_id, document_json) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)",
                (
                    event.event_id,
                    natural_key,
                    semantic_sha256,
                    event.source_id,
                    event.event_type,
                    subject_id,
                    event.observed_at,
                    event.available_at,
                    state,
                    stamp,
                    stamp,
                    raw_id,
                    canonical_bytes(event.as_dict()).decode("utf-8"),
                ),
            )
            if accepted is None:
                self._db.execute(
                    "INSERT INTO accepted_events(natural_key, event_id) VALUES(?, ?)",
                    (natural_key, event.event_id),
                )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        self.increment_metric("canonical_accepted" if state == "accepted" else "canonical_conflicts")
        return IngestResult(state, event, natural_key, semantic_sha256, raw_id, 1)

    def promote_event(
        self,
        natural_key: str,
        selected_event_id: str,
        *,
        reason: str,
        reconciled_at: str | None = None,
    ) -> dict[str, Any]:
        stamp = reconciled_at or utc_stamp()
        parse_utc(stamp)
        selected = self._db.execute(
            "SELECT event_id, state FROM canonical_events WHERE natural_key = ? AND event_id = ?",
            (natural_key, selected_event_id),
        ).fetchone()
        if selected is None:
            raise IngestionError("selected reconciliation event does not exist")
        prior = self._db.execute(
            "SELECT event_id FROM accepted_events WHERE natural_key = ?", (natural_key,)
        ).fetchone()
        previous_event_id = None if prior is None else str(prior["event_id"])
        if previous_event_id == selected_event_id:
            raise IngestionError("selected reconciliation event is already accepted")
        body: dict[str, Any] = {
            "schema": RECONCILIATION_SCHEMA,
            "natural_key": natural_key,
            "previous_event_id": previous_event_id,
            "selected_event_id": selected_event_id,
            "reason": reason,
            "reconciled_at": stamp,
        }
        body["content_sha256"] = digest_value(body)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if previous_event_id is not None:
                self._db.execute(
                    "UPDATE canonical_events SET state = 'superseded' WHERE event_id = ?", (previous_event_id,)
                )
            self._db.execute(
                "UPDATE canonical_events SET state = 'accepted' WHERE event_id = ?", (selected_event_id,)
            )
            self._db.execute(
                "INSERT INTO accepted_events(natural_key, event_id) VALUES(?, ?) "
                "ON CONFLICT(natural_key) DO UPDATE SET event_id = excluded.event_id",
                (natural_key, selected_event_id),
            )
            self._db.execute(
                "INSERT INTO reconciliations(natural_key, previous_event_id, selected_event_id, reason, reconciled_at, receipt_json) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (
                    natural_key,
                    previous_event_id,
                    selected_event_id,
                    reason,
                    stamp,
                    canonical_bytes(body).decode("utf-8"),
                ),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        return body

    def ingest_bar(
        self,
        bar: MarketBar,
        *,
        source_id: str,
        source_revision: str,
        granularity: int,
        available_at: str,
        raw_id: int | None,
        origin: str,
        promote_after_confirmations: int | None = None,
    ) -> IngestResult:
        if granularity not in _SUPPORTED_GRANULARITIES:
            raise IngestionError("unsupported candle granularity")
        observed = parse_utc(bar.timestamp)
        available = parse_utc(available_at)
        aligned = bucket_start(observed, granularity)
        if observed != aligned:
            raise IngestionError("candle timestamp is not aligned to its declared granularity")
        if available.timestamp() < observed.timestamp() + granularity:
            raise IngestionError("closed candle became available before its interval ended")
        semantic_sha256 = digest_value(bar.as_dict())
        natural_key = f"market-bar|{source_id}|{bar.symbol}|{granularity}|{utc_stamp(observed)}"
        event_id = f"{source_id}:market-bar:{digest_value({'key': natural_key, 'bar': semantic_sha256})[:40]}"
        event = Event(
            event_id=event_id,
            source_id=source_id,
            source_revision=source_revision,
            observed_at=utc_stamp(observed),
            available_at=utc_stamp(available),
            event_type="market-bar",
            subject_ids=(bar.symbol,),
            payload=bar.as_dict(),
            units={
                "open": "price",
                "high": "price",
                "low": "price",
                "close": "price",
                "volume": "asset-units",
            },
            coordinate_frame="venue-native",
            uncertainty={"origin": origin, "closed": True, "granularity_seconds": granularity},
            source_span={"raw_id": raw_id} if raw_id is not None else {},
        )
        result = self.ingest_event(
            event,
            natural_key=natural_key,
            raw_id=raw_id,
            semantic_value=bar.as_dict(),
            promote_after_confirmations=promote_after_confirmations,
            promotion_reason="same revised REST candle confirmed on consecutive reconciliations",
        )
        self.increment_metric(f"bars_{result.status}")
        if result.status in {"accepted", "promoted"}:
            self.note_activity("bar", at=available_at, value={"symbol": bar.symbol, "observed_at": bar.timestamp})
        return result

    def event(self, event_id: str) -> Event:
        row = self._db.execute("SELECT * FROM canonical_events WHERE event_id = ?", (event_id,)).fetchone()
        if row is None:
            raise IngestionError(f"unknown canonical event: {event_id}")
        return self._stored_event(row)

    def accepted_events(
        self,
        *,
        event_type: str | None = None,
        subject_id: str | None = None,
    ) -> tuple[Event, ...]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if event_type is not None:
            clauses.append("e.event_type = ?")
            parameters.append(event_type)
        if subject_id is not None:
            clauses.append("e.subject_id = ?")
            parameters.append(subject_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._db.execute(
            "SELECT e.* FROM accepted_events a JOIN canonical_events e ON e.event_id = a.event_id"
            + where
            + " ORDER BY e.observed_at, e.event_id",
            tuple(parameters),
        ).fetchall()
        return tuple(self._stored_event(row) for row in rows)

    def accepted_bars(self, symbol: str) -> tuple[tuple[Event, MarketBar], ...]:
        return tuple((event, _bar_from_event(event)) for event in self.accepted_events(event_type="market-bar", subject_id=symbol))

    def bar_gaps(
        self,
        *,
        source_id: str,
        symbol: str,
        granularity: int,
        start: datetime,
        end: datetime,
    ) -> tuple[str, ...]:
        if end <= start:
            return ()
        aligned_start = bucket_start(start, granularity)
        aligned_end = bucket_start(end, granularity)
        rows = self._db.execute(
            "SELECT e.observed_at FROM accepted_events a JOIN canonical_events e ON e.event_id = a.event_id "
            "WHERE e.event_type = 'market-bar' AND e.source_id = ? AND e.subject_id = ? "
            "AND e.observed_at >= ? AND e.observed_at < ?",
            (source_id, symbol, utc_stamp(aligned_start), utc_stamp(aligned_end)),
        ).fetchall()
        present = {utc_stamp(parse_utc(str(row["observed_at"]))) for row in rows}
        missing: list[str] = []
        cursor = int(aligned_start.timestamp())
        stop = int(aligned_end.timestamp())
        while cursor < stop:
            stamp = utc_stamp(datetime.fromtimestamp(cursor, tz=timezone.utc))
            if stamp not in present:
                missing.append(stamp)
            cursor += granularity
        return tuple(missing)

    def unresolved_conflicts(self) -> int:
        row = self._db.execute("SELECT COUNT(*) AS count FROM canonical_events WHERE state = 'conflict'").fetchone()
        return int(row["count"])

    def latest_accepted_bar(self, symbol: str) -> tuple[Event, MarketBar] | None:
        row = self._db.execute(
            "SELECT e.* FROM accepted_events a JOIN canonical_events e ON e.event_id = a.event_id "
            "WHERE e.event_type = 'market-bar' AND e.subject_id = ? ORDER BY e.observed_at DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        event = self._stored_event(row)
        return event, _bar_from_event(event)

    def latest_accepted_market_event(self, symbol: str) -> Event | None:
        row = self._db.execute(
            "SELECT e.* FROM accepted_events a JOIN canonical_events e ON e.event_id = a.event_id "
            "WHERE e.event_type IN ('market-heartbeat', 'market-quote', 'market-trade') "
            "AND e.subject_id = ? ORDER BY e.available_at DESC, e.event_id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        return None if row is None else self._stored_event(row)

    def pending_events(
        self,
        consumer_id: str,
        *,
        event_type: str,
        subject_id: str,
        limit: int | None = None,
    ) -> tuple[Event, ...]:
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise IngestionError("pending event limit must be a positive integer")
        query = (
            "SELECT e.* FROM accepted_events a JOIN canonical_events e ON e.event_id = a.event_id "
            "LEFT JOIN deliveries d ON d.event_id = e.event_id AND d.consumer_id = ? "
            "WHERE d.event_id IS NULL AND e.event_type = ? AND e.subject_id = ? "
            "ORDER BY e.observed_at, e.event_id"
        )
        parameters: tuple[Any, ...] = (consumer_id, event_type, subject_id)
        if limit is not None:
            query += " LIMIT ?"
            parameters += (limit,)
        rows = self._db.execute(query, parameters).fetchall()
        return tuple(self._stored_event(row) for row in rows)

    def pending_count(self, consumer_id: str, *, event_type: str, subject_id: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) AS count FROM accepted_events a JOIN canonical_events e ON e.event_id = a.event_id "
            "LEFT JOIN deliveries d ON d.event_id = e.event_id AND d.consumer_id = ? "
            "WHERE d.event_id IS NULL AND e.event_type = ? AND e.subject_id = ?",
            (consumer_id, event_type, subject_id),
        ).fetchone()
        return int(row["count"])

    def delivery_count(self, consumer_id: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) AS count FROM deliveries WHERE consumer_id = ?", (consumer_id,)
        ).fetchone()
        return int(row["count"])

    def mark_delivered(
        self,
        consumer_id: str,
        event_id: str,
        *,
        disposition: str,
        receipt_sha256: str | None = None,
        processed_at: str | None = None,
    ) -> None:
        stamp = processed_at or utc_stamp()
        parse_utc(stamp)
        self._db.execute(
            "INSERT INTO deliveries(consumer_id, event_id, processed_at, disposition, receipt_sha256) "
            "VALUES(?, ?, ?, ?, ?) ON CONFLICT(consumer_id, event_id) DO NOTHING",
            (consumer_id, event_id, stamp, disposition, receipt_sha256),
        )

    def event_root(self, *, event_type: str | None = None, subject_id: str | None = None) -> str:
        return digest_value([event.as_dict() for event in self.accepted_events(event_type=event_type, subject_id=subject_id)])

    def raw_count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) AS count FROM raw_messages").fetchone()
        return int(row["count"])

    def export_recording(self, path: Path) -> dict[str, Any]:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        opener = gzip.open if path.suffix.lower() == ".gz" else open
        hasher = hashlib.sha256()
        count = 0
        with opener(path, "wt", encoding="utf-8", newline="\n") as handle:
            for row in self._db.execute("SELECT * FROM raw_messages ORDER BY raw_id"):
                record = {
                    "schema": RAW_RECORDING_SCHEMA,
                    "raw_id": int(row["raw_id"]),
                    "source_id": str(row["source_id"]),
                    "session_id": str(row["session_id"]),
                    "channel": str(row["channel"]),
                    "sequence": row["sequence_value"],
                    "observed_at": row["observed_at"],
                    "received_at": str(row["received_at"]),
                    "received_monotonic_ns": int(row["received_monotonic_ns"]),
                    "payload_sha256": str(row["payload_sha256"]),
                    "payload": json.loads(str(row["payload_json"])),
                }
                line = canonical_bytes(record) + b"\n"
                handle.write(line.decode("utf-8"))
                hasher.update(line)
                count += 1
        return {
            "schema": "cassi.market-recording-export.v1",
            "path": str(path),
            "records": count,
            "content_sha256": hasher.hexdigest(),
        }

    @staticmethod
    def iter_recording(path: Path) -> Iterator[dict[str, Any]]:
        path = Path(path)
        opener = gzip.open if path.suffix.lower() == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise IngestionError(f"invalid recording JSON at line {line_number}") from exc
                if record.get("schema") != RAW_RECORDING_SCHEMA:
                    raise IngestionError(f"recording schema mismatch at line {line_number}")
                if digest_value(record.get("payload")) != record.get("payload_sha256"):
                    raise IngestionError(f"recording payload digest mismatch at line {line_number}")
                parse_utc(str(record["received_at"]))
                yield record

    def save_health(self, health: DataHealth) -> None:
        document = health.as_dict()
        self._db.execute(
            "INSERT INTO health_snapshots(evaluated_at, state, content_sha256, document_json) VALUES(?, ?, ?, ?)",
            (
                health.evaluated_at,
                health.state,
                health.content_sha256,
                canonical_bytes(document).decode("utf-8"),
            ),
        )
        self.set_state("latest_health", document, at=health.evaluated_at)


class DataHealthMonitor:
    def __init__(
        self,
        store: IngestionStore,
        *,
        symbol: str,
        granularity: int,
        consumer_id: str | None = None,
        policy: HealthPolicy | None = None,
        require_heartbeat: bool = True,
        require_account_reconciliation: bool = False,
    ) -> None:
        if granularity not in _SUPPORTED_GRANULARITIES:
            raise IngestionError("unsupported health-monitor granularity")
        self.store = store
        self.symbol = symbol
        self.granularity = granularity
        self.consumer_id = consumer_id
        self.policy = policy or HealthPolicy()
        self.require_heartbeat = require_heartbeat
        self.require_account_reconciliation = require_account_reconciliation

    @staticmethod
    def _age(now: datetime, stamp: str | None) -> float | None:
        if stamp is None:
            return None
        return max(0.0, (now - parse_utc(stamp)).total_seconds())

    def evaluate(self, *, now: datetime | None = None) -> DataHealth:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        evaluated_at = utc_stamp(current)
        reasons: list[dict[str, Any]] = []

        def add(severity: str, code: str, **details: Any) -> None:
            reasons.append({"severity": severity, "code": code, **details})

        heartbeat_at = self.store.activity_at("heartbeat")
        market_at = self.store.activity_at("market") or self.store.activity_at("bar")
        reconcile_at = self.store.activity_at("reconcile")
        heartbeat_age = self._age(current, heartbeat_at)
        market_age = self._age(current, market_at)
        reconcile_age = self._age(current, reconcile_at)

        if self.require_heartbeat:
            if not self.store.get_state("subscription_confirmed", False):
                add("RED", "subscription-unconfirmed")
            if heartbeat_age is None:
                add("RED", "heartbeat-missing")
            elif heartbeat_age > self.policy.heartbeat_red_seconds:
                add("RED", "heartbeat-stale", age_seconds=heartbeat_age)
            elif heartbeat_age > self.policy.heartbeat_yellow_seconds:
                add("YELLOW", "heartbeat-delayed", age_seconds=heartbeat_age)

        if market_age is None:
            add("RED", "market-activity-missing")
        elif market_age > self.policy.market_red_seconds:
            add("RED", "market-data-stale", age_seconds=market_age)
        elif market_age > self.policy.market_yellow_seconds:
            add("YELLOW", "market-data-delayed", age_seconds=market_age)

        if reconcile_age is None:
            add("RED", "rest-reconciliation-missing")
        elif reconcile_age > self.policy.reconcile_red_seconds:
            add("RED", "rest-reconciliation-stale", age_seconds=reconcile_age)
        elif reconcile_age > self.policy.reconcile_yellow_seconds:
            add("YELLOW", "rest-reconciliation-delayed", age_seconds=reconcile_age)

        gap_count = int(self.store.get_state(f"bar_gap_count:{self.symbol}:{self.granularity}", 0))
        if gap_count:
            add("RED", "unresolved-bar-gaps", count=gap_count)
        conflicts = self.store.unresolved_conflicts()
        if conflicts:
            add("RED", "unresolved-source-conflicts", count=conflicts)
        if self.store.get_state("recovery_required", False):
            add("RED", "source-recovery-required")
        if self.require_account_reconciliation and not self.store.get_state("account_reconciled", False):
            add("RED", "account-unreconciled")

        latest_market = self.store.latest_accepted_market_event(self.symbol)
        latest_market_observed_at = None if latest_market is None else latest_market.observed_at
        latest_market_received_at = None if latest_market is None else latest_market.available_at
        exchange_to_receipt_wall_delta = (
            None
            if latest_market is None
            else (parse_utc(latest_market.available_at) - parse_utc(latest_market.observed_at)).total_seconds()
        )
        exchange_clock_lead_lower_bound = (
            None if exchange_to_receipt_wall_delta is None else max(0.0, -exchange_to_receipt_wall_delta)
        )
        if (
            exchange_to_receipt_wall_delta is not None
            and abs(exchange_to_receipt_wall_delta) > self.policy.exchange_time_delta_red_seconds
        ):
            add(
                "RED",
                "exchange-receipt-time-divergence",
                wall_delta_seconds=exchange_to_receipt_wall_delta,
            )
        elif (
            exchange_to_receipt_wall_delta is not None
            and abs(exchange_to_receipt_wall_delta) > self.policy.exchange_time_delta_yellow_seconds
        ):
            add(
                "YELLOW",
                "exchange-receipt-time-divergence",
                wall_delta_seconds=exchange_to_receipt_wall_delta,
            )
        latest = self.store.latest_accepted_bar(self.symbol)
        latest_bar_start = None if latest is None else latest[1].timestamp
        latest_bar_available_at = None if latest is None else latest[0].available_at
        candle_close_wall_delta = (
            None
            if latest is None
            else (
                parse_utc(latest[0].available_at)
                - parse_utc(latest[1].timestamp)
                - timedelta(seconds=self.granularity)
            ).total_seconds()
        )
        expected_latest = bucket_start(current, self.granularity).timestamp() - self.granularity
        if latest is None:
            add("RED", "closed-bar-missing")
        elif parse_utc(latest[1].timestamp).timestamp() < expected_latest:
            add("RED", "latest-closed-bar-missing", expected_start=utc_stamp(datetime.fromtimestamp(expected_latest, tz=timezone.utc)))

        backlog = (
            0
            if self.consumer_id is None
            else self.store.pending_count(self.consumer_id, event_type="market-bar", subject_id=self.symbol)
        )
        if backlog > self.policy.backlog_red:
            add("RED", "consumer-backlog", count=backlog)
        elif backlog > self.policy.backlog_yellow:
            add("YELLOW", "consumer-backlog", count=backlog)

        free_bytes = shutil.disk_usage(self.store.path.parent).free
        if free_bytes < self.policy.disk_red_bytes:
            add("RED", "disk-space-critical", free_bytes=free_bytes)
        elif free_bytes < self.policy.disk_yellow_bytes:
            add("YELLOW", "disk-space-low", free_bytes=free_bytes)

        state = "RED" if any(row["severity"] == "RED" for row in reasons) else "YELLOW" if reasons else "GREEN"
        metrics: dict[str, Any] = {
            "heartbeat_at": heartbeat_at,
            "heartbeat_age_seconds": heartbeat_age,
            "market_at": market_at,
            "market_age_seconds": market_age,
            "reconcile_at": reconcile_at,
            "reconcile_age_seconds": reconcile_age,
            "latest_market_event_type": None if latest_market is None else latest_market.event_type,
            "latest_market_observed_at": latest_market_observed_at,
            "latest_market_received_at": latest_market_received_at,
            "exchange_to_receipt_wall_delta_seconds": exchange_to_receipt_wall_delta,
            "exchange_clock_lead_lower_bound_seconds": exchange_clock_lead_lower_bound,
            "latest_bar_available_at": latest_bar_available_at,
            "candle_close_to_receipt_wall_delta_seconds": candle_close_wall_delta,
            "latest_bar_start": latest_bar_start,
            "bar_gap_count": gap_count,
            "unresolved_conflicts": conflicts,
            "consumer_backlog": backlog,
            "disk_free_bytes": free_bytes,
            "raw_messages": self.store.raw_count(),
            "counters": self.store.metrics(),
        }
        body = {
            "schema": HEALTH_SCHEMA,
            "state": state,
            "evaluated_at": evaluated_at,
            "reasons": reasons,
            "metrics": metrics,
            "can_observe": state in {"GREEN", "YELLOW"},
            "can_open_exposure": state == "GREEN",
        }
        health = DataHealth(
            state=state,
            evaluated_at=evaluated_at,
            reasons=tuple(reasons),
            metrics=metrics,
            can_observe=state in {"GREEN", "YELLOW"},
            can_open_exposure=state == "GREEN",
            content_sha256=digest_value(body),
        )
        self.store.save_health(health)
        return health


@dataclass(slots=True)
class CanonicalPaperConsumer:
    """Deliver canonical closed bars once, warming history without old fills."""

    store: IngestionStore
    session: "PaperSession"
    symbol: str
    consumer_id: str
    state_path: Path
    latest_path: Path
    _prepared: bool = field(default=False, init=False)

    def prepare(self) -> dict[str, Any]:
        if self._prepared:
            return {"status": "already-prepared", "warmed_bars": 0}
        accepted = self.store.accepted_bars(self.symbol)
        delivered = self.store.delivery_count(self.consumer_id)
        warmed = 0
        if delivered == 0 and accepted:
            if self.session.history:
                cutoff = self.session.history[-1].timestamp
            else:
                history = [bar for _, bar in accepted][-self.session.config.max_history :]
                self.session.history = history
                if history:
                    self.session.account.mark(history[-1])
                cutoff = history[-1].timestamp if history else ""
            for event, bar in accepted:
                if bar.timestamp <= cutoff:
                    self.store.mark_delivered(
                        self.consumer_id,
                        event.event_id,
                        disposition="history-warmup",
                        processed_at=utc_stamp(),
                    )
                    warmed += 1
            self.session.save_state(self.state_path)
        self._prepared = True
        return {"status": "prepared", "warmed_bars": warmed}

    def drain(self, health: DataHealth) -> dict[str, Any]:
        self.prepare()
        if not health.can_open_exposure:
            return {
                "schema": PAPER_CONSUMER_SCHEMA,
                "status": "BLOCKED_BY_DATA_HEALTH",
                "health_state": health.state,
                "processed": 0,
            }
        processed = 0
        latest_receipt: dict[str, Any] | None = None
        for event in self.store.pending_events(
            self.consumer_id,
            event_type="market-bar",
            subject_id=self.symbol,
        ):
            latest_receipt = self.session.process_event(event, data_health=health.as_dict())
            self.session.save_state(self.state_path)
            atomic_write_json(self.latest_path, latest_receipt)
            self.store.mark_delivered(
                self.consumer_id,
                event.event_id,
                disposition="paper-decision",
                receipt_sha256=str(latest_receipt["content_sha256"]),
            )
            processed += 1
        return {
            "schema": PAPER_CONSUMER_SCHEMA,
            "status": "PASS",
            "health_state": health.state,
            "processed": processed,
            "latest_receipt_sha256": None if latest_receipt is None else latest_receipt["content_sha256"],
        }


__all__ = [
    "CanonicalPaperConsumer",
    "DataHealth",
    "DataHealthMonitor",
    "HEALTH_SCHEMA",
    "HealthPolicy",
    "IngestResult",
    "IngestionError",
    "IngestionStore",
    "PAPER_CONSUMER_SCHEMA",
    "RAW_RECORDING_SCHEMA",
    "RawCapture",
    "atomic_write_json",
    "bucket_start",
    "parse_utc",
    "utc_stamp",
]
