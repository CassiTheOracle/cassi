"""L22 durable teacher-trace journal checks."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from cassi_trace_store import TeacherTraceStore, TraceStoreError


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cassi-l22-traces-") as temporary:
        path = Path(temporary) / "teacher-traces.sqlite3"
        first = {
            "token_index": 0,
            "field_step": 256,
            "field_sha256": "a" * 64,
            "field_sketch_f32_b64": "AAAAAA==",
            "selected_token_id": 11,
            "selected_piece": "rain",
            "teacher_top_k": [{"token_id": 11, "piece": "rain", "logit": 3.0, "rank": 0}],
        }
        second = {**first, "token_index": 1, "field_step": 512, "selected_token_id": 12, "selected_piece": "y"}
        with TeacherTraceStore(path) as store:
            ids = store.append_batch("session-a", "request-a", [first, second])
            assert len(ids) == 2 and ids == store.list_ids("session-a")
            assert store.replay(ids[0]) == {
                **first,
                "protocol": "CassiQwen teacher trace store",
                "version": 1,
                "session_id": "session-a",
                "request_id": "request-a",
            }
            assert store.stats()["records"] == 2

            try:
                store.append_batch("session-a", "request-a", [first])
            except TraceStoreError:
                pass
            else:
                raise AssertionError("duplicate lineage was accepted")
            assert store.stats()["records"] == 2

            store.append_batch("session-a", "request-b", [{**first, "token_index": 0, "selected_token_id": 99}])
            assert store.stats()["records"] == 3
            assert store.consolidate(keep_latest_per_session=2) == 1
            assert store.stats()["records"] == 2

            # Corruption must fail closed at replay rather than returning a partial record.
            corrupt_id = store.list_ids("session-a")[0]
            store._connection.execute("UPDATE trace_records SET payload_zlib = ? WHERE record_id = ?", (sqlite3.Binary(b"not-zlib"), corrupt_id))
            try:
                store.replay(corrupt_id)
            except TraceStoreError:
                pass
            else:
                raise AssertionError("corrupt payload replayed")

    print("L22 trace store PASS")


if __name__ == "__main__":
    main()
