"""Durable compact teacher-trace journal for the persistent Cassi provider."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping


PROTOCOL = "CassiQwen teacher trace store"
VERSION = 1


class TraceStoreError(RuntimeError):
    """Trace schema, transaction, checksum, or replay failure."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(dict(value), ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise TraceStoreError(f"trace is not finite JSON: {error}") from error


class TeacherTraceStore:
    """SQLite WAL journal with compressed, checksummed trace payloads."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trace_records (
                record_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                token_index INTEGER NOT NULL,
                created_at REAL NOT NULL,
                payload_zlib BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL,
                raw_bytes INTEGER NOT NULL,
                compressed_bytes INTEGER NOT NULL,
                UNIQUE(session_id, request_id, token_index)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trace_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO trace_meta(key, value) VALUES('protocol', ?)",
            (f"{PROTOCOL} v{VERSION}",),
        )

    def close(self) -> None:
        self._connection.close()

    def append_batch(self, session_id: str, request_id: str, records: Iterable[Mapping[str, Any]]) -> list[str]:
        if not session_id or not request_id:
            raise TraceStoreError("session_id and request_id are required")
        prepared: list[tuple[str, int, float, bytes, str, int, int]] = []
        for value in records:
            item = dict(value)
            token_index = item.get("token_index")
            if not isinstance(token_index, int) or isinstance(token_index, bool) or token_index < 0:
                raise TraceStoreError("trace token_index must be a non-negative integer")
            item.update({"protocol": PROTOCOL, "version": VERSION, "session_id": session_id, "request_id": request_id})
            raw = _canonical(item)
            compressed = zlib.compress(raw, level=9)
            record_id = hashlib.sha256(f"{session_id}\0{request_id}\0{token_index}".encode("utf-8")).hexdigest()
            prepared.append((record_id, token_index, time.time(), compressed, hashlib.sha256(raw).hexdigest(), len(raw), len(compressed)))
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            for record_id, token_index, created_at, compressed, payload_sha, raw_bytes, compressed_bytes in prepared:
                self._connection.execute(
                    """
                    INSERT INTO trace_records(record_id, session_id, request_id, token_index, created_at,
                        payload_zlib, payload_sha256, raw_bytes, compressed_bytes)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (record_id, session_id, request_id, token_index, created_at, compressed, payload_sha, raw_bytes, compressed_bytes),
                )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise TraceStoreError(f"trace batch conflicts with existing lineage: {error}") from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        return [row[0] for row in prepared]

    def replay(self, record_id: str) -> dict[str, Any]:
        row = self._connection.execute(
            "SELECT payload_zlib, payload_sha256, raw_bytes FROM trace_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise TraceStoreError(f"trace record not found: {record_id}")
        compressed, expected_sha, expected_bytes = bytes(row[0]), str(row[1]), int(row[2])
        try:
            raw = zlib.decompress(compressed)
            value = json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        except (zlib.error, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise TraceStoreError(f"trace payload cannot be replayed: {record_id}") from error
        if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha or not isinstance(value, dict):
            raise TraceStoreError(f"trace checksum/shape mismatch: {record_id}")
        return value

    def list_ids(self, session_id: str | None = None) -> list[str]:
        if session_id is None:
            rows = self._connection.execute("SELECT record_id FROM trace_records ORDER BY created_at, record_id").fetchall()
        else:
            rows = self._connection.execute("SELECT record_id FROM trace_records WHERE session_id = ? ORDER BY token_index, record_id", (session_id,)).fetchall()
        return [str(row[0]) for row in rows]

    def stats(self) -> dict[str, int]:
        row = self._connection.execute("SELECT COUNT(*), COALESCE(SUM(raw_bytes), 0), COALESCE(SUM(compressed_bytes), 0) FROM trace_records").fetchone()
        return {"records": int(row[0]), "raw_bytes": int(row[1]), "compressed_bytes": int(row[2])}

    def consolidate(self, *, keep_latest_per_session: int) -> int:
        if keep_latest_per_session < 0:
            raise TraceStoreError("keep_latest_per_session must be non-negative")
        rows = self._connection.execute(
            """
            SELECT record_id FROM (
                SELECT record_id, ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY created_at DESC, token_index DESC) AS rank
                FROM trace_records
            ) WHERE rank > ?
            """,
            (keep_latest_per_session,),
        ).fetchall()
        ids = [str(row[0]) for row in rows]
        if ids:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.executemany("DELETE FROM trace_records WHERE record_id = ?", ((record_id,) for record_id in ids))
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
        return len(ids)

    def __enter__(self) -> "TeacherTraceStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
