"""L23 shadow student training and checkpoint checks."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import numpy as np

from cassi_shadow_student import ShadowStudent, ShadowStudentError, train_candidate
from cassi_trace_store import TeacherTraceStore


def encoded(values: np.ndarray) -> str:
    return base64.b64encode(np.asarray(values, dtype="<f4").tobytes(order="C")).decode("ascii")


def main() -> None:
    positive = np.zeros(128, dtype=np.float32)
    positive[0] = 1.0
    negative = np.zeros(128, dtype=np.float32)
    negative[1] = 1.0
    with tempfile.TemporaryDirectory(prefix="cassi-l23-student-") as temporary:
        trace_path = Path(temporary) / "traces.sqlite3"
        candidate_path = Path(temporary) / "student-candidate.json"
        with TeacherTraceStore(trace_path) as store:
            ids = store.append_batch(
                "student-session",
                "student-request",
                [
                    {"token_index": 0, "field_sketch_f32_b64": encoded(positive), "selected_token_id": 101, "selected_piece": "A"},
                    {"token_index": 1, "field_sketch_f32_b64": encoded(positive), "selected_token_id": 101, "selected_piece": "A"},
                    {"token_index": 2, "field_sketch_f32_b64": encoded(negative), "selected_token_id": 202, "selected_piece": "B"},
                ],
            )
            student = ShadowStudent(model_sha256="m" * 64)
            student.fit((record_id, store.replay(record_id)) for record_id in ids)
            prediction_a = student.predict(positive)
            prediction_b = student.predict(negative)
            assert prediction_a is not None and prediction_a.token_id == 101
            assert prediction_b is not None and prediction_b.token_id == 202
            assert prediction_a.confidence > 0.5
            student.save(candidate_path)
            restored = ShadowStudent.load(candidate_path, expected_model_sha256="m" * 64)
            restored_a = restored.predict(positive)
            assert restored_a is not None and restored_a.token_id == 101
            candidate = train_candidate(store, candidate_path, model_sha256="m" * 64)
            assert candidate["status"] == "candidate" and candidate["trained_records"] == 3
            try:
                ShadowStudent.load(candidate_path, expected_model_sha256="wrong")
            except ShadowStudentError:
                pass
            else:
                raise AssertionError("model identity mismatch was accepted")
    print("L23 shadow student PASS")


if __name__ == "__main__":
    main()
