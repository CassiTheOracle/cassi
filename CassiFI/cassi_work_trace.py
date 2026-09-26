"""Narrow cost trace for ordinary Cassi work.

The trace answers one question at a time: where did wall time, waits, batches
and bytes go for work the machine actually performed.  It records measured
rows only, keeps the ordering, never infers a cause from utilization, and does
not rank bottlenecks.  Callers open spans around real operations and record
counters and waits at the point they happen; several threads may record
concurrently into one trace.

Rows are canonical JSON so a later report or comparison can digest them
exactly.  Nothing here reads a clock of its own beyond the injected one, so a
trace can be replayed in a test with fixed timestamps.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import threading
import time
from typing import Any, Iterator, Mapping, MutableMapping, Sequence

SCHEMA = "cassifi.work-trace.v1"
SUMMARY_SCHEMA = "cassifi.work-trace-summary.v1"
WAIT_KIND = "wait"

_MAX_ROWS = 1_000_000
_MAX_TEXT = 512
_MAX_META_BYTES = 4096


class WorkTraceError(ValueError):
    """A trace row, span, or summary value is not measurable or canonical."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkTraceError(f"{label} must be a nonempty string")
    if len(value) > _MAX_TEXT:
        raise WorkTraceError(f"{label} exceeds its bound")
    return value


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkTraceError(f"{label} must be a nonnegative integer")
    if value > _MAX_ROWS * 1_000_000:
        raise WorkTraceError(f"{label} exceeds its bound")
    return value


def _optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _count(value, label)


def _meta(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise WorkTraceError("span metadata must be a mapping")
    try:
        plain = json.loads(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise WorkTraceError("span metadata is not canonical JSON") from exc
    if len(json.dumps(plain, separators=(",", ":"), ensure_ascii=False)) > _MAX_META_BYTES:
        raise WorkTraceError("span metadata exceeds its bound")
    return plain


def canonical_sha256(value: Any, label: str = "work trace value") -> str:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise WorkTraceError(f"{label} is not canonical JSON") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _nearest_rank(values: Sequence[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _milliseconds(nanoseconds: int) -> float:
    return round(nanoseconds / 1_000_000.0, 6)


class WorkTrace:
    """Measured rows from one piece of ordinary work."""

    def __init__(self, *, clock: Any | None = None) -> None:
        self._clock = time.perf_counter_ns if clock is None else clock
        self._lock = threading.Lock()
        self._rows: list[dict[str, Any]] = []
        self._thread_local = threading.local()

    # -- recording -------------------------------------------------------
    def now(self) -> int:
        return int(self._clock())

    def record(
        self,
        kind: str,
        name: str,
        duration_ns: int = 0,
        *,
        wait_ns: int = 0,
        rows: int | None = None,
        items: int | None = None,
        bytes_moved: int | None = None,
        layer: int | None = None,
        source_sha256: str | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "kind": _text(kind, "row kind"),
            "name": _text(name, "row name"),
            "duration_ns": _count(duration_ns, "duration_ns"),
            "wait_ns": _count(wait_ns, "wait_ns"),
        }
        for key, value, label in (
            ("rows", rows, "rows"),
            ("items", items, "items"),
            ("bytes", bytes_moved, "bytes"),
            ("layer", layer, "layer"),
        ):
            resolved = _optional_int(value, label)
            if resolved is not None:
                row[key] = resolved
        if source_sha256 is not None:
            row["source_sha256"] = _text(source_sha256, "source_sha256")
        metadata = _meta(meta)
        if metadata is not None:
            row["meta"] = metadata
        with self._lock:
            if len(self._rows) >= _MAX_ROWS:
                raise WorkTraceError("work trace row bound reached")
            self._rows.append(row)
        return row

    @contextmanager
    def span(self, kind: str, name: str, **fields: Any) -> Iterator[MutableMapping[str, Any]]:
        """Time one real operation.  Fields measured while it runs win over the
        fields declared up front; accepted keys are those of `record`."""
        started = self.now()
        slot: MutableMapping[str, Any] = {}
        try:
            yield slot
        finally:
            duration = max(0, self.now() - started)
            self.record(kind, name, duration, **{**fields, **slot})

    # -- reading ---------------------------------------------------------
    def rows(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows]

    def __len__(self) -> int:
        with self._lock:
            return len(self._rows)

    def summary(self) -> dict[str, Any]:
        rows = self.rows()
        groups: dict[tuple[str, str], MutableMapping[str, Any]] = {}
        waits: list[int] = []
        for row in rows:
            key = (str(row["kind"]), str(row["name"]))
            group = groups.setdefault(
                key,
                {"rows": 0, "duration_ns": 0, "wait_ns": 0, "bytes": 0, "items": 0, "rows_measured": 0},
            )
            group["rows"] += 1
            group["duration_ns"] += int(row["duration_ns"])
            group["wait_ns"] += int(row["wait_ns"])
            group["bytes"] += int(row.get("bytes", 0))
            group["items"] += int(row.get("items", 0))
            group["rows_measured"] += int(row.get("rows", 0))
            if row["kind"] == WAIT_KIND or int(row["wait_ns"]) > 0:
                waits.append(int(row["wait_ns"]) or int(row["duration_ns"]))
        entries = []
        for (kind, name), group in sorted(groups.items()):
            entries.append(
                {
                    "kind": kind,
                    "name": name,
                    "rows": group["rows"],
                    "duration_ms": _milliseconds(group["duration_ns"]),
                    "wait_ms": _milliseconds(group["wait_ns"]),
                    "bytes": group["bytes"],
                    "items": group["items"],
                    "rows_measured": group["rows_measured"],
                }
            )
        summary = {
            "schema": SUMMARY_SCHEMA,
            "trace_schema": SCHEMA,
            "row_count": len(rows),
            "groups": entries,
            "total_duration_ms": _milliseconds(sum(int(row["duration_ns"]) for row in rows)),
            "total_wait_ms": _milliseconds(sum(int(row["wait_ns"]) for row in rows)),
            "wait_p50_ms": _milliseconds(_nearest_rank(waits, 0.50)),
            "wait_p95_ms": _milliseconds(_nearest_rank(waits, 0.95)),
            "wait_p99_ms": _milliseconds(_nearest_rank(waits, 0.99)),
            "wait_max_ms": _milliseconds(max(waits) if waits else 0),
        }
        summary["trace_sha256"] = canonical_sha256(rows, "work trace rows")
        return summary


_ACTIVE: ContextVar[WorkTrace | None] = ContextVar("cassifi_active_work_trace", default=None)


@contextmanager
def trace_work(trace: WorkTrace | None = None) -> Iterator[WorkTrace]:
    """Make `trace` the active trace for this context (a fresh one by default)."""
    if trace is not None and not isinstance(trace, WorkTrace):
        raise WorkTraceError("active work trace must be a WorkTrace")
    resolved = trace if trace is not None else WorkTrace()
    token = _ACTIVE.set(resolved)
    try:
        yield resolved
    finally:
        _ACTIVE.reset(token)


def active_trace() -> WorkTrace | None:
    """The active trace, or None when the caller is not tracing ordinary work."""
    return _ACTIVE.get()
