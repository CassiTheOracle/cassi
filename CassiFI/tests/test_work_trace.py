"""Work trace module and executor projection-batcher wiring."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading

import numpy as np
import pytest

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

from cassi_work_trace import (  # noqa: E402
    SCHEMA,
    SUMMARY_SCHEMA,
    WorkTrace,
    WorkTraceError,
    active_trace,
    canonical_sha256,
    trace_work,
)
from programs.model.qwen_executor import (  # noqa: E402
    _ProjectionBatcher,
    _active_work_trace,
)


class _Clock:
    def __init__(self, step: int = 1_000_000):
        self.value = 0
        self.step = step

    def __call__(self) -> int:
        self.value += self.step
        return self.value


def test_rows_summary_and_digest_are_measured_and_canonical() -> None:
    trace = WorkTrace(clock=_Clock())
    with trace.span("stage", "qwen-ffn", rows=1, layer=3, source_sha256="a" * 64) as slot:
        slot["items"] = 2
    trace.record("wait", "projection-group", wait_ns=4_000_000, rows=1)
    trace.record("wait", "projection-group", wait_ns=20_000_000, rows=1)
    trace.record("cohort", "stage-batch", rows=4, items=1)

    rows = trace.rows()
    assert len(rows) == 4
    assert rows[0]["kind"] == "stage"
    assert rows[0]["name"] == "qwen-ffn"
    assert rows[0]["layer"] == 3
    assert rows[0]["duration_ns"] == 1_000_000
    assert rows[0]["items"] == 2

    summary = trace.summary()
    assert summary["schema"] == SUMMARY_SCHEMA
    assert summary["trace_schema"] == SCHEMA
    assert summary["row_count"] == 4
    assert summary["total_wait_ms"] == 24.0
    assert summary["wait_p50_ms"] == 4.0
    assert summary["wait_p95_ms"] == 20.0
    assert summary["wait_max_ms"] == 20.0
    groups = {(entry["kind"], entry["name"]): entry for entry in summary["groups"]}
    assert groups[("wait", "projection-group")]["wait_ms"] == 24.0
    assert groups[("cohort", "stage-batch")]["rows"] == 1
    assert groups[("cohort", "stage-batch")]["rows_measured"] == 4
    assert summary["trace_sha256"] == canonical_sha256(rows)
    assert json.loads(json.dumps(summary, sort_keys=True))["trace_sha256"] == summary["trace_sha256"]


def test_invalid_rows_are_refused_rather_than_recorded() -> None:
    trace = WorkTrace(clock=_Clock())
    with pytest.raises(WorkTraceError):
        trace.record("", "name")
    with pytest.raises(WorkTraceError):
        trace.record("stage", "")
    with pytest.raises(WorkTraceError):
        trace.record("stage", "name", -1)
    with pytest.raises(WorkTraceError):
        trace.record("stage", "name", 1, rows=-1)
    with pytest.raises(WorkTraceError):
        trace.record("stage", "name", 1, meta={"blob": "x" * 8_000})
    with pytest.raises(WorkTraceError):
        trace.record("stage", "name", 1, meta={"bad": float("nan")})
    assert trace.rows() == []
    with pytest.raises(WorkTraceError):
        with trace_work(object()):  # type: ignore[arg-type]
            pass


def test_active_trace_is_context_scoped_and_reaches_the_executor_helper() -> None:
    assert active_trace() is None
    assert _active_work_trace() is None
    with trace_work() as trace:
        assert active_trace() is trace
        assert _active_work_trace() is trace
    assert active_trace() is None


class _FakeBank:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, int]] = []
        self._lock = threading.Lock()
        self._weights = {
            "gate": np.arange(12, dtype=np.float32).reshape(3, 4) / 4.0,
            "up": np.arange(8, dtype=np.float32).reshape(2, 4) / 3.0,
        }

    def matvec(self, name: str, x: np.ndarray, expert: int | None = None) -> np.ndarray:
        with self._lock:
            self.calls.append((str(name), expert, int(np.asarray(x).shape[0])))
        return self._weights[str(name)] @ np.asarray(x, dtype=np.float32)

    def matvec_batch(
        self, name: str, x: np.ndarray, expert: int | None = None
    ) -> list[np.ndarray]:
        rows = np.asarray(x, dtype=np.float32)
        with self._lock:
            self.calls.append((str(name), expert, int(rows.shape[1])))
        weights = self._weights[str(name)]
        return [weights @ row for row in rows]


def test_batcher_records_grouped_projection_widths_and_caller_waits() -> None:
    rows = 4
    bank = _FakeBank()
    trace = WorkTrace()
    batcher = _ProjectionBatcher(bank, rows, wait_seconds=0.05, work_trace=trace)
    inputs = [np.arange(4, dtype=np.float32) + index for index in range(rows)]
    outputs: list[Any] = [None] * rows
    barrier = threading.Barrier(rows)

    def worker(index: int) -> None:
        barrier.wait()
        outputs[index] = batcher.matvec("gate", inputs[index])

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(rows)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    for index, output in enumerate(outputs):
        expected = bank.matvec("gate", inputs[index])
        assert np.allclose(output, expected)

    summary = trace.summary()
    groups = {(entry["kind"], entry["name"]): entry for entry in summary["groups"]}
    projection = groups[("projection", "gate")]
    assert projection["rows"] == 1
    assert projection["rows_measured"] == rows
    assert projection["items"] == 1
    wait = groups[("wait", "projection-group")]
    assert wait["rows"] == rows
    assert wait["wait_ms"] >= 0.0
    assert summary["row_count"] == rows + 1
    assert all(entry["name"] != "matvec" for entry in summary["groups"])


def test_untraced_batcher_keeps_its_original_behavior() -> None:
    bank = _FakeBank()
    batcher = _ProjectionBatcher(bank, 1)
    assert batcher.work_trace is None
    output = batcher.matvec("up", np.ones(4, dtype=np.float32))
    assert np.allclose(output, bank.matvec("up", np.ones(4, dtype=np.float32)))
