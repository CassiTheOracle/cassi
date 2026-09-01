"""L26 trace condensation and structural promotion checks."""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

import numpy as np

from cassi_condensation import condense
from cassi_shadow_student import ShadowStudent
from cassi_trace_store import TeacherTraceStore


def encoded(index: int) -> str:
    vector = np.zeros(128, dtype=np.float32)
    vector[index % 4] = 1.0
    return base64.b64encode(vector.astype("<f4").tobytes(order="C")).decode("ascii")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cassi-l26-condense-") as temporary:
        root = Path(temporary)
        trace_path = root / "traces.sqlite3"
        candidate_path = root / "candidate.json"
        active_path = root / "active.json"
        with TeacherTraceStore(trace_path) as store:
            ids = store.append_batch(
                "condense-session",
                "condense-request",
                [
                    {"token_index": index, "field_sketch_f32_b64": encoded(index), "selected_token_id": 100 + index % 2, "selected_piece": str(index % 2)}
                    for index in range(5)
                ],
            )
            report = condense(store, candidate_path, active_path, model_sha256="m" * 64, keep_latest_per_session=2)
            assert report["promotion_policy"] == "structural_no_quality_gate"
            assert report["source_records"] == 5
            assert report["heldout"]["records"] == 1
            assert report["consolidated_records"] == 3
            active = ShadowStudent.load(active_path, expected_model_sha256="m" * 64)
            assert active.trained_records == 5
            assert active.labels == (100, 101)
            payload = json.loads(active_path.read_text(encoding="utf-8"))
            assert payload["status"] == "active"
            assert payload["source_trace_ids"] == report["source_trace_ids"]
            assert payload["condensation"]["promotion_policy"] == "structural_no_quality_gate"
    print("L26 condensation PASS")


if __name__ == "__main__":
    main()
