"""L26 deterministic trace condensation and student promotion."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from .cassi_shadow_student import PROTOCOL as STUDENT_PROTOCOL, ShadowStudent, ShadowStudentError
    from .cassi_trace_store import TeacherTraceStore, TraceStoreError
except ImportError:  # direct script execution
    from cassi_shadow_student import PROTOCOL as STUDENT_PROTOCOL, ShadowStudent, ShadowStudentError
    from cassi_trace_store import TeacherTraceStore, TraceStoreError


PROTOCOL = "CassiQwen trace condensation"
VERSION = 1


class CondensationError(RuntimeError):
    """Condensation, provenance, or promotion failure."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return (json.dumps(dict(value), ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CondensationError(f"condensation payload is not finite JSON: {error}") from error


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical(value)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise CondensationError(f"checkpoint cannot be read: {path}") from error
    if not isinstance(value, dict):
        raise CondensationError(f"checkpoint is not an object: {path}")
    return value


def _evaluate(student: ShadowStudent, records: list[tuple[str, Mapping[str, Any]]]) -> dict[str, Any]:
    correct = 0
    covered = 0
    confidences: list[float] = []
    rows: list[dict[str, Any]] = []
    for record_id, trace in records:
        target = trace.get("selected_token_id")
        prediction = student.predict(trace.get("field_sketch_f32_b64"))
        predicted = prediction.token_id if prediction is not None else None
        if prediction is not None:
            covered += 1
            confidences.append(float(prediction.confidence))
        if prediction is not None and predicted == target:
            correct += 1
        rows.append({"record_id": record_id, "target_token_id": target, "predicted_token_id": predicted, "confidence": prediction.confidence if prediction is not None else None})
    total = len(records)
    return {
        "records": total,
        "covered": covered,
        "accuracy": float(correct / total) if total else None,
        "coverage": float(covered / total) if total else None,
        "mean_confidence": float(sum(confidences) / len(confidences)) if confidences else None,
        "rows": rows,
    }


def condense(
    store: TeacherTraceStore,
    candidate_path: Path,
    active_path: Path,
    *,
    model_sha256: str | None = None,
    keep_latest_per_session: int | None = None,
) -> dict[str, Any]:
    ids = store.list_ids()
    if not ids:
        raise CondensationError("cannot promote an empty trace journal")
    try:
        records = [(record_id, store.replay(record_id)) for record_id in ids]
    except TraceStoreError as error:
        raise CondensationError(str(error)) from error
    heldout_ids = ids[4::5]
    if len(ids) >= 2 and not heldout_ids:
        heldout_ids = [ids[-1]]
    heldout_set = set(heldout_ids)
    train_records = [(record_id, trace) for record_id, trace in records if record_id not in heldout_set]
    if not train_records:
        raise CondensationError("condensation split left no training records")
    train_student = ShadowStudent(model_sha256=model_sha256)
    train_student.fit(train_records)
    heldout_records = [(record_id, trace) for record_id, trace in records if record_id in heldout_set]
    diagnostics = _evaluate(train_student, heldout_records)
    train_student.save(candidate_path, status="candidate", source_trace_ids=[record_id for record_id, _ in train_records])
    candidate = _load(candidate_path)
    if candidate.get("protocol") != STUDENT_PROTOCOL or candidate.get("model_sha256") != model_sha256:
        raise CondensationError("candidate checkpoint identity mismatch")

    final_student = ShadowStudent(model_sha256=model_sha256)
    final_student.fit(records)
    source_ids = [record_id for record_id, _ in records]
    final_payload = final_student.checkpoint(status="active", source_trace_ids=source_ids)
    report: dict[str, Any] = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "created_at": time.time(),
        "promotion_policy": "structural_no_quality_gate",
        "trace_store": str(store.path),
        "source_trace_ids": source_ids,
        "source_records": len(records),
        "train_records": len(train_records),
        "heldout_ids": heldout_ids,
        "heldout": diagnostics,
        "candidate_path": str(Path(candidate_path)),
        "active_path": str(Path(active_path)),
        "model_sha256": model_sha256,
    }
    final_payload["condensation"] = report
    _atomic_json(active_path, final_payload)
    active = _load(active_path)
    try:
        ShadowStudent.load(active_path, expected_model_sha256=model_sha256)
    except ShadowStudentError as error:
        raise CondensationError(str(error)) from error
    if active.get("status") != "active" or active.get("source_trace_ids") != source_ids:
        raise CondensationError("active checkpoint lost promotion provenance")
    if keep_latest_per_session is not None:
        if keep_latest_per_session < 0:
            raise CondensationError("keep_latest_per_session must be non-negative")
        report["consolidated_records"] = store.consolidate(keep_latest_per_session=keep_latest_per_session)
        report["post_consolidation_stats"] = store.stats()
        final_payload["condensation"] = report
        _atomic_json(active_path, final_payload)
    report["candidate_sha256"] = hashlib.sha256(Path(candidate_path).read_bytes()).hexdigest()
    report["active_sha256"] = hashlib.sha256(Path(active_path).read_bytes()).hexdigest()
    return report
