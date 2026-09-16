from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable, Mapping, Sequence
import uuid


IMPORT_PREVIEW_SCHEMA = "cassipi.import-preview.v1"
IMPORT_COMMIT_SCHEMA = "cassipi.import-commit.v1"
IMPORT_PLAN_SCHEMA = "cassipi.import-plan.v1"
SUPPORTED_ADAPTERS = frozenset({"mnemic", "thalamus", "mnemopi", "omp-session"})
MEMORY_SCOPES = frozenset({"task", "branch", "session", "project", "profile"})
MAX_RECORDS = 100_000
MAX_RECORD_BYTES = 768 * 1024
MAX_JSONL_BYTES = 512 * 1024 * 1024
ZERO_SHA256 = "0" * 64


class ImportError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True, slots=True)
class ImportRecord:
    key: str
    content: bytes
    timestamp: str
    message_role: str
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ScanResult:
    adapter_version: str
    records: tuple[ImportRecord, ...]
    source_bytes: int


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _closed(
    value: Any,
    required: set[str],
    *,
    optional: set[str] | None = None,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ImportError("INVALID_IMPORT_REQUEST", f"{label} must be an object")
    keys = set(value)
    allowed = required | (optional or set())
    if keys != required and (keys - allowed or required - keys):
        raise ImportError(
            "INVALID_IMPORT_REQUEST",
            f"{label} has invalid fields",
            details={"missing": sorted(required - keys), "unknown": sorted(keys - allowed)},
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ImportError("INVALID_IMPORT_REQUEST", f"{label} must be non-empty text")
    return value


def _digest(value: Any, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ImportError("INVALID_IMPORT_REQUEST", f"{label} must be a SHA-256 digest")
    return text


def _timestamp(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000.0 if abs(float(value)) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            )
        except (OverflowError, OSError, ValueError):
            pass
    if isinstance(value, str) and value:
        return value
    return "1970-01-01T00:00:00.000Z"


def _json_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {
            "bytes": len(value),
            "sha256": _sha256_bytes(value),
        }
    return str(value)


def _bounded_record(record: ImportRecord) -> ImportRecord:
    if not record.content or len(record.content) > MAX_RECORD_BYTES:
        raise ImportError(
            "IMPORT_RECORD_TOO_LARGE",
            "a legacy record exceeds the supported exact-source byte limit",
            details={"record_key": record.key, "bytes": len(record.content), "limit": MAX_RECORD_BYTES},
        )
    try:
        record.content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ImportError(
            "IMPORT_RECORD_NOT_UTF8",
            "a legacy record is not valid UTF-8",
            details={"record_key": record.key},
        ) from exc
    return record


def _sqlite(path: Path) -> sqlite3.Connection:
    wal_path = path.with_name(f"{path.name}-wal")
    if wal_path.exists() and wal_path.stat().st_size:
        raise ImportError(
            "IMPORT_LIVE_SQLITE_UNSUPPORTED",
            "legacy SQLite source has a live WAL; create a consistent backup or export before importing",
            details={"wal_path": str(wal_path), "wal_bytes": wal_path.stat().st_size},
        )
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except sqlite3.Error as exc:
        raise ImportError("IMPORT_SOURCE_UNREADABLE", f"cannot open legacy SQLite store: {exc}") from exc


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _require_columns(
    connection: sqlite3.Connection,
    table: str,
    required: set[str],
) -> None:
    if table not in _tables(connection):
        raise ImportError("IMPORT_SCHEMA_UNSUPPORTED", f"legacy store is missing table {table}")
    missing = required - _columns(connection, table)
    if missing:
        raise ImportError(
            "IMPORT_SCHEMA_UNSUPPORTED",
            f"legacy table {table} has an unsupported schema",
            details={"missing_columns": sorted(missing)},
        )


def _count(connection: sqlite3.Connection, table: str) -> int:
    value = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    if value > MAX_RECORDS:
        raise ImportError(
            "IMPORT_TOO_MANY_RECORDS",
            "legacy source exceeds the bounded import record limit",
            details={"records": value, "limit": MAX_RECORDS},
        )
    return value


def _scan_mnemic(path: Path) -> ScanResult:
    connection = _sqlite(path)
    try:
        _require_columns(
            connection,
            "mnemic_field_events",
            {"stream_id", "sequence", "previous_event_id", "event_id", "payload", "created_at"},
        )
        _count(connection, "mnemic_field_events")
        records: list[ImportRecord] = []
        previous_by_stream: dict[str, str] = {}
        for row in connection.execute(
            "SELECT stream_id, sequence, previous_event_id, event_id, payload, created_at "
            "FROM mnemic_field_events ORDER BY stream_id, sequence"
        ):
            payload = row["payload"]
            if not isinstance(payload, str):
                raise ImportError("IMPORT_SCHEMA_UNSUPPORTED", "Mnemic event payload is not text")
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ImportError("IMPORT_SOURCE_CORRUPT", "Mnemic event payload is invalid JSON") from exc
            if not isinstance(decoded, Mapping):
                raise ImportError("IMPORT_SOURCE_CORRUPT", "Mnemic event payload is not an object")
            stream_id = str(row["stream_id"])
            previous = previous_by_stream.get(stream_id)
            if previous is not None and str(row["previous_event_id"]) != previous:
                raise ImportError(
                    "IMPORT_SOURCE_CORRUPT",
                    "Mnemic event predecessor chain is discontinuous",
                    details={"stream_id": stream_id, "sequence": int(row["sequence"])},
                )
            previous_by_stream[stream_id] = str(row["event_id"])
            provenance: dict[str, Any] = {
                "legacy_event_id": str(row["event_id"]),
                "legacy_previous_event_id": str(row["previous_event_id"]),
                "legacy_sequence": int(row["sequence"]),
                "legacy_stream_id": stream_id,
            }
            for name in ("kind", "operation", "context_session_id", "turn_id"):
                if name in decoded:
                    provenance[name] = _json_scalar(decoded[name])
            records.append(
                _bounded_record(
                    ImportRecord(
                        key=f"{stream_id}:{int(row['sequence'])}:{row['event_id']}",
                        content=payload.encode("utf-8"),
                        timestamp=_timestamp(row["created_at"]),
                        message_role="custom",
                        provenance=provenance,
                    )
                )
            )
        return ScanResult("mnemic-field-journal.v1", tuple(records), path.stat().st_size)
    finally:
        connection.close()


def _scan_thalamus(path: Path) -> ScanResult:
    connection = _sqlite(path)
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in {2, 3}:
            raise ImportError(
                "IMPORT_SCHEMA_UNSUPPORTED",
                "Thalamus store user_version is unsupported",
                details={"user_version": version, "supported": [2, 3]},
            )
        _require_columns(
            connection,
            "dropped_messages",
            {"id", "session_id", "pass_number", "msg_index", "role", "content", "slot", "composite", "created_at"},
        )
        _require_columns(
            connection,
            "recall_queue",
            {"id", "session_id", "content", "role", "source", "label", "created_at"},
        )
        if _count(connection, "dropped_messages") + _count(connection, "recall_queue") > MAX_RECORDS:
            raise ImportError("IMPORT_TOO_MANY_RECORDS", "Thalamus source exceeds the import limit")
        records: list[ImportRecord] = []
        for row in connection.execute(
            "SELECT id, session_id, pass_number, msg_index, role, content, slot, composite, created_at "
            "FROM dropped_messages ORDER BY id"
        ):
            records.append(
                _bounded_record(
                    ImportRecord(
                        key=f"dropped:{int(row['id'])}",
                        content=str(row["content"]).encode("utf-8"),
                        timestamp=_timestamp(row["created_at"]),
                        message_role=str(row["role"]),
                        provenance={
                            "legacy_table": "dropped_messages",
                            "legacy_id": int(row["id"]),
                            "legacy_session_id": str(row["session_id"]),
                            "legacy_pass_number": int(row["pass_number"]),
                            "legacy_message_index": int(row["msg_index"]),
                            "legacy_slot": str(row["slot"]),
                            "legacy_composite": float(row["composite"]),
                        },
                    )
                )
            )
        for row in connection.execute(
            "SELECT id, session_id, content, role, source, label, created_at FROM recall_queue ORDER BY id"
        ):
            records.append(
                _bounded_record(
                    ImportRecord(
                        key=f"recall:{int(row['id'])}",
                        content=str(row["content"]).encode("utf-8"),
                        timestamp=_timestamp(row["created_at"]),
                        message_role=str(row["role"]),
                        provenance={
                            "legacy_table": "recall_queue",
                            "legacy_id": int(row["id"]),
                            "legacy_session_id": str(row["session_id"]),
                            "legacy_source": str(row["source"]),
                            "legacy_label": _json_scalar(row["label"]),
                        },
                    )
                )
            )
        return ScanResult(f"thalamus.sqlite.user-version-{version}", tuple(records), path.stat().st_size)
    finally:
        connection.close()


def _scan_mnemopi(path: Path) -> ScanResult:
    connection = _sqlite(path)
    try:
        tables = _tables(connection)
        selected = [table for table in ("working_memory", "episodic_memory") if table in tables]
        if not selected:
            raise ImportError(
                "IMPORT_SCHEMA_UNSUPPORTED",
                "Mnemopi store has neither working_memory nor episodic_memory",
            )
        records: list[ImportRecord] = []
        schema_rows: dict[str, list[str]] = {}
        for table in selected:
            _require_columns(connection, table, {"id", "content"})
            _count(connection, table)
            columns = _columns(connection, table)
            schema_rows[table] = sorted(columns)
            optional = [
                name
                for name in (
                    "source",
                    "timestamp",
                    "created_at",
                    "session_id",
                    "importance",
                    "metadata_json",
                    "veracity",
                    "memory_type",
                    "scope",
                    "author_id",
                    "author_type",
                    "channel_id",
                    "trust_tier",
                    "superseded_by",
                    "valid_until",
                )
                if name in columns
            ]
            query_columns = ["id", "content", *optional]
            query = f"SELECT {', '.join(query_columns)} FROM {table} ORDER BY id"
            for row in connection.execute(query):
                provenance = {
                    "legacy_table": table,
                    **{f"legacy_{name}": _json_scalar(row[name]) for name in optional},
                }
                timestamp = row["timestamp"] if "timestamp" in optional else None
                if not timestamp and "created_at" in optional:
                    timestamp = row["created_at"]
                records.append(
                    _bounded_record(
                        ImportRecord(
                            key=f"{table}:{row['id']}",
                            content=str(row["content"]).encode("utf-8"),
                            timestamp=_timestamp(timestamp),
                            message_role="custom",
                            provenance=provenance,
                        )
                    )
                )
        if len(records) > MAX_RECORDS:
            raise ImportError("IMPORT_TOO_MANY_RECORDS", "Mnemopi source exceeds the import limit")
        schema_hash = _sha256_bytes(_canonical_json(schema_rows))[:16]
        return ScanResult(f"mnemopi.beam.{schema_hash}", tuple(records), path.stat().st_size)
    finally:
        connection.close()


def _scan_omp_session(path: Path) -> ScanResult:
    if path.stat().st_size > MAX_JSONL_BYTES:
        raise ImportError(
            "IMPORT_SOURCE_TOO_LARGE",
            "Oh My Pi session file exceeds the bounded import size",
            details={"bytes": path.stat().st_size, "limit": MAX_JSONL_BYTES},
        )
    records: list[ImportRecord] = []
    session_header: Mapping[str, Any] | None = None
    known_ids: set[str] = set()
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            if len(raw) > MAX_RECORD_BYTES:
                raise ImportError(
                    "IMPORT_RECORD_TOO_LARGE",
                    "Oh My Pi session line exceeds the exact-source byte limit",
                    details={"line": line_number, "bytes": len(raw)},
                )
            try:
                value = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ImportError(
                    "IMPORT_SOURCE_CORRUPT",
                    "Oh My Pi session contains invalid JSONL",
                    details={"line": line_number},
                ) from exc
            if not isinstance(value, Mapping):
                raise ImportError("IMPORT_SOURCE_CORRUPT", "Oh My Pi session line is not an object")
            if value.get("type") == "title":
                continue
            if session_header is None:
                if value.get("type") != "session" or not isinstance(value.get("id"), str):
                    raise ImportError("IMPORT_SCHEMA_UNSUPPORTED", "Oh My Pi session header is missing")
                version = value.get("version", 1)
                if isinstance(version, bool) or not isinstance(version, int) or version < 1 or version > 3:
                    raise ImportError(
                        "IMPORT_SCHEMA_UNSUPPORTED",
                        "Oh My Pi session version is unsupported",
                        details={"version": version, "supported": [1, 2, 3]},
                    )
                session_header = value
                continue
            entry_id = value.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                continue
            if entry_id in known_ids:
                raise ImportError(
                    "IMPORT_SOURCE_CORRUPT",
                    "Oh My Pi session contains a duplicate entry identity",
                    details={"entry_id": entry_id},
                )
            parent_id = value.get("parentId")
            if parent_id is not None and (not isinstance(parent_id, str) or parent_id not in known_ids):
                raise ImportError(
                    "IMPORT_SOURCE_CORRUPT",
                    "Oh My Pi session contains a dangling parent identity",
                    details={"entry_id": entry_id, "parent_id": parent_id},
                )
            known_ids.add(entry_id)
            if value.get("type") not in {
                "message",
                "custom_message",
                "compaction",
                "branch_summary",
                "tts_injection",
            }:
                continue
            message = value.get("message")
            role = message.get("role") if isinstance(message, Mapping) else value.get("role")
            records.append(
                _bounded_record(
                    ImportRecord(
                        key=entry_id,
                        content=raw.rstrip(b"\r\n"),
                        timestamp=_timestamp(value.get("timestamp")),
                        message_role=role if isinstance(role, str) and role else "custom",
                        provenance={
                            "legacy_entry_id": entry_id,
                            "legacy_parent_id": parent_id,
                            "legacy_session_id": session_header["id"],
                            "legacy_entry_type": str(value.get("type")),
                            "legacy_cwd": _json_scalar(session_header.get("cwd")),
                        },
                    )
                )
            )
            if len(records) > MAX_RECORDS:
                raise ImportError("IMPORT_TOO_MANY_RECORDS", "Oh My Pi session exceeds the import limit")
    if session_header is None:
        raise ImportError("IMPORT_SCHEMA_UNSUPPORTED", "Oh My Pi session header is missing")
    return ScanResult(
        f"omp-session.v{session_header.get('version', 1)}",
        tuple(records),
        path.stat().st_size,
    )


def _scan(adapter: str, path: Path) -> ScanResult:
    scanners = {
        "mnemic": _scan_mnemic,
        "thalamus": _scan_thalamus,
        "mnemopi": _scan_mnemopi,
        "omp-session": _scan_omp_session,
    }
    return scanners[adapter](path)


def _stable_scan(adapter: str, path: Path) -> tuple[ScanResult, str]:
    before_sha256 = _sha256_file(path)
    before_bytes = path.stat().st_size
    scan = _scan(adapter, path)
    after_sha256 = _sha256_file(path)
    after_bytes = path.stat().st_size
    if (
        before_sha256 != after_sha256
        or before_bytes != after_bytes
        or scan.source_bytes != after_bytes
    ):
        raise ImportError(
            "IMPORT_SOURCE_CHANGED",
            "legacy source changed while it was being read; create a stable snapshot before importing",
        )
    return scan, after_sha256




def _record_projection_eligible(record: ImportRecord) -> bool:
    terminal_values = {"deleted", "inactive", "invalidated", "revoked", "superseded", "tombstone"}
    if record.message_role.strip().lower() in terminal_values:
        return False
    return not any(
        isinstance(value, str) and value.strip().lower() in terminal_values
        for key, value in record.provenance.items()
        if key in {"kind", "legacy_state", "state", "status"}
    )

def _dataset_sha256(scan: ScanResult) -> str:
    digest = hashlib.sha256()
    digest.update(scan.adapter_version.encode("utf-8"))
    digest.update(b"\0")
    for record in scan.records:
        digest.update(record.key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_bytes(record.content).encode("ascii"))
        digest.update(b"\0")
        digest.update(_canonical_json(record.provenance))
    return digest.hexdigest()


class CassiPiLegacyImporter:
    """Read-only, schema-aware, resumable predecessor import."""

    def __init__(self, adapter: Any, data_home: Path) -> None:
        self.adapter = adapter
        self.root = data_home / "imports"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _scope(value: Mapping[str, Any]) -> dict[str, str]:
        return {
            name: _text(value[name], name)
            for name in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")
        }

    @staticmethod
    def _validate_stored_plan(
        value: Any,
        *,
        preview_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        try:
            plan = _closed(
                value,
                {"schema", "preview_id", "binding", "scope"},
                label="stored import plan",
            )
            if plan["schema"] != IMPORT_PLAN_SCHEMA:
                raise ValueError("stored import plan schema is incompatible")
            if _digest(plan["preview_id"], "stored preview_id") != preview_id:
                raise ValueError("stored import plan identity differs from its file")
            raw_scope = _closed(
                plan["scope"],
                {"profile_id", "project_id", "session_id", "branch_id", "task_scope"},
                label="stored import scope",
            )
            scope = CassiPiLegacyImporter._scope(raw_scope)
            binding = _closed(
                plan["binding"],
                {
                    "adapter",
                    "adapter_version",
                    "dataset_sha256",
                    "required_disk_bytes",
                    "memory_scope",
                    "profile_id",
                    "project_id",
                    "record_count",
                    "schema",
                    "source_path",
                    "source_bytes",
                    "source_file_sha256",
                },
                label="stored import binding",
            )
            if binding["schema"] != "cassipi.import-binding.v1":
                raise ValueError("stored import binding schema is incompatible")
            adapter = _text(binding["adapter"], "stored adapter")
            if adapter not in SUPPORTED_ADAPTERS:
                raise ValueError("stored import adapter is unsupported")
            _text(binding["adapter_version"], "stored adapter_version")
            _digest(binding["dataset_sha256"], "stored dataset_sha256")
            _digest(binding["source_file_sha256"], "stored source_file_sha256")
            _text(binding["source_path"], "stored source_path")
            memory_scope = _text(binding["memory_scope"], "stored memory_scope")
            if memory_scope not in MEMORY_SCOPES:
                raise ValueError("stored memory scope is unsupported")
            for name in ("required_disk_bytes", "record_count", "source_bytes"):
                item = binding[name]
                if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                    raise ValueError(f"stored {name} must be a nonnegative integer")
            for name in ("profile_id", "project_id"):
                if _text(binding[name], f"stored {name}") != scope[name]:
                    raise ValueError(f"stored binding {name} differs from its scope")
            normalized_binding = dict(binding)
            if _sha256_bytes(_canonical_json(normalized_binding)) != preview_id:
                raise ValueError("stored import binding does not match its preview identity")
        except (ImportError, KeyError, TypeError, ValueError) as exc:
            raise ImportError(
                "IMPORT_PLAN_CORRUPT",
                "stored import preview violates its closed schema or content identity",
            ) from exc
        return dict(plan), normalized_binding, scope

    @classmethod
    def _read_stored_plan(
        cls,
        path: Path,
        *,
        preview_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        try:
            encoded = path.read_bytes()
            value = json.loads(encoded.decode("utf-8"))
            if _canonical_json(value) != encoded:
                raise ValueError("stored import preview is not canonical JSON")
        except FileNotFoundError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ImportError(
                "IMPORT_PLAN_CORRUPT",
                "stored import preview is unreadable",
            ) from exc
        return cls._validate_stored_plan(value, preview_id=preview_id)

    def _plan_path(self, preview_id: str) -> Path:
        return self.root / f"{preview_id}.json"

    def preview(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        value = _closed(
            request,
            {
                "schema",
                "adapter",
                "source_path",
                "memory_scope",
                "profile_id",
                "project_id",
                "session_id",
                "branch_id",
                "task_scope",
            },
            label="import preview request",
        )
        if value["schema"] != IMPORT_PREVIEW_SCHEMA:
            raise ImportError("PROTOCOL_MISMATCH", "import preview schema is incompatible")
        adapter_name = _text(value["adapter"], "adapter")
        if adapter_name not in SUPPORTED_ADAPTERS:
            raise ImportError(
                "IMPORT_ADAPTER_UNSUPPORTED",
                "legacy import adapter is unsupported",
                details={"adapter": adapter_name, "supported": sorted(SUPPORTED_ADAPTERS)},
            )
        memory_scope = _text(value["memory_scope"], "memory_scope")
        if memory_scope not in MEMORY_SCOPES:
            raise ImportError("INVALID_MEMORY_SCOPE", "memory scope is unsupported")
        path = Path(_text(value["source_path"], "source_path")).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ImportError("IMPORT_SOURCE_UNREADABLE", "legacy import source is not a file")
        scope = self._scope(value)
        scan, source_file_sha256 = _stable_scan(adapter_name, path)
        dataset_sha256 = _dataset_sha256(scan)
        content_counts: dict[str, int] = {}
        source_scope_counts: dict[str, int] = {}
        missing_provenance_records = 0
        required_disk_bytes = 0
        scope_rank = {"task": 1, "branch": 2, "session": 3, "project": 4, "profile": 5, "global": 6}
        wider_scope_records = 0
        for record in scan.records:
            content_sha256 = _sha256_bytes(record.content)
            content_counts[content_sha256] = content_counts.get(content_sha256, 0) + 1
            required_disk_bytes += len(record.content) + len(_canonical_json(record.provenance)) + 2048
            if not record.provenance:
                missing_provenance_records += 1
            legacy_scope = record.provenance.get("legacy_scope")
            if isinstance(legacy_scope, str) and legacy_scope:
                source_scope_counts[legacy_scope] = source_scope_counts.get(legacy_scope, 0) + 1
                if scope_rank.get(legacy_scope, 0) > scope_rank[memory_scope]:
                    wider_scope_records += 1
        projection_ineligible_records = sum(
            1 for record in scan.records if not _record_projection_eligible(record)
        )
        duplicate_count = sum(count - 1 for count in content_counts.values() if count > 1)
        duplicate_groups = sum(1 for count in content_counts.values() if count > 1)
        available_disk_bytes = shutil.disk_usage(self.root).free
        binding = {
            "adapter": adapter_name,
            "adapter_version": scan.adapter_version,
            "dataset_sha256": dataset_sha256,
            "memory_scope": memory_scope,
            "required_disk_bytes": required_disk_bytes,
            "profile_id": scope["profile_id"],
            "project_id": scope["project_id"],
            "record_count": len(scan.records),
            "schema": "cassipi.import-binding.v1",
            "source_path": str(path),
            "source_bytes": scan.source_bytes,
            "source_file_sha256": source_file_sha256,
        }
        preview_id = _sha256_bytes(_canonical_json(binding))
        plan = {
            "schema": IMPORT_PLAN_SCHEMA,
            "preview_id": preview_id,
            "binding": binding,
            "scope": scope,
        }
        plan_path = self._plan_path(preview_id)
        if plan_path.exists():
            existing, _, _ = self._read_stored_plan(
                plan_path,
                preview_id=preview_id,
            )
            if existing != plan:
                raise ImportError("IMPORT_PLAN_CONFLICT", "stored import preview conflicts with its identity")
        else:
            _atomic_json(plan_path, plan)
        return {
            "schema": IMPORT_PREVIEW_SCHEMA,
            "preview_id": preview_id,
            "adapter": adapter_name,
            "adapter_version": scan.adapter_version,
            "source_path": str(path),
            "source_file_sha256": source_file_sha256,
            "projection_eligible_records": len(scan.records) - projection_ineligible_records,
            "projection_ineligible_records": projection_ineligible_records,
            "dataset_sha256": dataset_sha256,
            "source_bytes": scan.source_bytes,
            "record_count": len(scan.records),
            "duplicate_content_records": duplicate_count,
            "duplicate_content_groups": duplicate_groups,
            "duplicate_policy": "preserve-distinct-provenance",
            "missing_provenance_records": missing_provenance_records,
            "source_scope_counts": dict(sorted(source_scope_counts.items())),
            "wider_scope_records": wider_scope_records,
            "required_disk_bytes": required_disk_bytes,
            "available_disk_bytes": available_disk_bytes,
            "disk_space_sufficient": available_disk_bytes >= required_disk_bytes,
            "memory_scope": memory_scope,
            "scope": scope,
            "provenance": "read-only source; exact imported bytes retain legacy record identity",
        }

    def commit(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        value = _closed(
            request,
            {
                "schema",
                "preview_id",
                "profile_id",
                "project_id",
                "session_id",
                "branch_id",
                "task_scope",
            },
            label="import commit request",
        )
        if value["schema"] != IMPORT_COMMIT_SCHEMA:
            raise ImportError("PROTOCOL_MISMATCH", "import commit schema is incompatible")
        preview_id = _digest(value["preview_id"], "preview_id")
        scope = self._scope(value)
        plan_path = self._plan_path(preview_id)
        try:
            _, binding, stored_scope = self._read_stored_plan(
                plan_path,
                preview_id=preview_id,
            )
        except FileNotFoundError as exc:
            raise ImportError("IMPORT_PREVIEW_NOT_FOUND", "import preview is unavailable") from exc
        if stored_scope != scope:
            raise ImportError("IMPORT_SCOPE_CONFLICT", "import commit scope differs from its preview")
        path = Path(_text(binding["source_path"], "source_path")).resolve(strict=True)
        scan, source_file_sha256 = _stable_scan(_text(binding["adapter"], "adapter"), path)
        if (
            scan.adapter_version != binding["adapter_version"]
            or len(scan.records) != binding["record_count"]
            or scan.source_bytes != binding["source_bytes"]
            or source_file_sha256 != binding["source_file_sha256"]
            or _dataset_sha256(scan) != binding["dataset_sha256"]
        ):
            raise ImportError(
                "IMPORT_SOURCE_CHANGED",
                "legacy source changed after preview; create a new preview before importing",
            )
        if shutil.disk_usage(self.root).free < int(binding["required_disk_bytes"]):
            raise ImportError(
                "IMPORT_DISK_SPACE",
                "insufficient disk space for the previewed legacy import",
                details={
                    "required_disk_bytes": int(binding["required_disk_bytes"]),
                    "available_disk_bytes": shutil.disk_usage(self.root).free,
                },
            )
        producer_id = f"import:{preview_id[:32]}"
        bindings = self.adapter.bindings(
            {
                "schema": "cassipi.host-bindings.v1",
                "profile_id": scope["profile_id"],
                "project_id": scope["project_id"],
                "session_id": scope["session_id"],
                "branch_id": scope["branch_id"],
                "producer_id": producer_id,
            }
        )
        ordered = sorted(bindings["bindings"], key=lambda row: row["producer_sequence"])
        known: dict[tuple[str, str], str] = {}
        for row in ordered:
            native_entry_id = row.get("native_entry_id")
            if not isinstance(native_entry_id, str):
                continue
            for source in row.get("sources", []):
                if isinstance(source, Mapping):
                    content_sha256 = source.get("content_sha256")
                    revision_id = source.get("revision_id")
                    if isinstance(content_sha256, str) and isinstance(revision_id, str):
                        known[(native_entry_id, content_sha256)] = revision_id
        last_event_id = ordered[-1]["event_id"] if ordered else None
        next_sequence = int(ordered[-1]["producer_sequence"]) + 1 if ordered else 0
        imported = 0
        skipped = 0
        for record in scan.records:
            content_sha256 = _sha256_bytes(record.content)
            native_entry_id = f"legacy:{binding['adapter']}:{record.key}"
            if (native_entry_id, content_sha256) in known:
                skipped += 1
                continue
            owner = self.adapter.owner_status()
            identity = _sha256_bytes(
                f"{preview_id}\0{native_entry_id}\0{content_sha256}".encode("utf-8")
            )
            result = self.adapter.observe(
                {
                    "schema": "cassipi.observe.v1",
                    "operation_id": f"import:{identity}",
                    "native_identity": f"{native_entry_id}:{content_sha256}:import",
                    "producer_id": producer_id,
                    "producer_sequence": next_sequence,
                    "predecessor_event_id": last_event_id,
                    **scope,
                    "parent_head_id": owner["field_head_sha256"],
                    "event_kind": "import",
                    "source": {
                        "source_id": f"legacy:{binding['adapter']}:{binding['dataset_sha256']}:{record.key}",
                        "content_base64": base64.b64encode(record.content).decode("ascii"),
                        "content_sha256": content_sha256,
                        "mime_type": "application/vnd.cassipi.legacy-record+json"
                        if binding["adapter"] in {"mnemic", "omp-session"}
                        else "text/plain",
                        "codec": "utf-8",
                        **scope,
                        "native_source_entry_id": native_entry_id,
                        "author_origin": f"legacy:{binding['adapter']}",
                        "message_role": record.message_role,
                        "observed_timestamp": record.timestamp,
                        "claim_category": "imported-summary",
                        "fidelity": "exact-observed-bytes",
                    },
                    "payload": {
                        "memory_scope": binding["memory_scope"],
                        "import_adapter": binding["adapter"],
                        "import_preview_id": preview_id,
                        "legacy_provenance": dict(record.provenance),
                        "legacy_role": record.message_role,
                        "projection_eligible": _record_projection_eligible(record),
                    },
                    "native_entry_id": native_entry_id,
                }
            )
            last_event_id = result["event_id"]
            next_sequence += 1
            imported += 1
        owner = self.adapter.owner_status()
        return {
            "schema": IMPORT_COMMIT_SCHEMA,
            "preview_id": preview_id,
            "record_count": len(scan.records),
            "imported_records": imported,
            "already_committed_records": skipped,
            "field_head_sha256": owner["field_head_sha256"],
            "generation_id": owner["generation_id"],
            "status": "committed",
        }
