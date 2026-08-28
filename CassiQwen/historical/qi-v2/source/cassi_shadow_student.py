"""Compact field-conditioned shadow student for the experimental provider.

This is deliberately a small, inspectable learner rather than a second language
model.  It learns cosine prototypes from the durable L22 field sketches and
predicts only token IDs observed in teacher traces.  The native Qwen teacher
remains the fallback; the student is usable for shadow receipts, bounded
correction, and exact selective-cache hits without a quality gate.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

try:
    from .cassi_trace_store import TeacherTraceStore
except ImportError:  # direct script execution
    from cassi_trace_store import TeacherTraceStore


PROTOCOL = "CassiQwen shadow student"
VERSION = 1
FEATURE_DIM = 128


class ShadowStudentError(RuntimeError):
    """Student checkpoint, feature, or training failure."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return (json.dumps(dict(value), ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ShadowStudentError(f"student checkpoint is not finite JSON: {error}") from error


def _decode_sketch(value: Any) -> np.ndarray:
    if not isinstance(value, str) or len(value) % 4:
        raise ShadowStudentError("field_sketch_f32_b64 must be padded base64")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise ShadowStudentError("field sketch is not canonical base64") from error
    if base64.b64encode(raw).decode("ascii") != value or len(raw) != FEATURE_DIM * 4:
        raise ShadowStudentError("field sketch has the wrong byte length")
    array = np.frombuffer(raw, dtype="<f4").copy()
    if not np.isfinite(array).all():
        raise ShadowStudentError("field sketch contains non-finite values")
    norm = float(np.linalg.norm(array.astype(np.float64)))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ShadowStudentError("field sketch must have positive norm")
    return np.ascontiguousarray(array)


def _normalised(value: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(value.astype(np.float64)))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ShadowStudentError("student prototype has invalid norm")
    return np.ascontiguousarray(value.astype(np.float64) / norm, dtype=np.float64)


def _sketch_payload(value: np.ndarray) -> tuple[str, str]:
    array = np.asarray(value, dtype="<f4")
    if array.shape != (FEATURE_DIM,) or not np.isfinite(array).all():
        raise ShadowStudentError("student feature has the wrong shape")
    raw = array.tobytes(order="C")
    return base64.b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
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


@dataclass
class _Prototype:
    token_id: int
    piece: str
    count: int
    sum_vector: np.ndarray

    def centroid(self) -> np.ndarray:
        return _normalised(self.sum_vector)


@dataclass(frozen=True)
class StudentPrediction:
    token_id: int
    piece: str
    score: float
    confidence: float
    count: int
    neighbors: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "piece": self.piece,
            "score": self.score,
            "confidence": self.confidence,
            "count": self.count,
            "neighbors": [dict(row) for row in self.neighbors],
        }


class ShadowStudent:
    """Nearest-prototype student trained from compact teacher records."""

    def __init__(self, *, model_sha256: str | None = None) -> None:
        self.model_sha256 = model_sha256
        self._prototypes: dict[int, _Prototype] = {}
        self._records = 0
        self._source_ids: list[str] = []

    @property
    def trained_records(self) -> int:
        return self._records

    @property
    def labels(self) -> tuple[int, ...]:
        return tuple(sorted(self._prototypes))

    def clear(self) -> None:
        self._prototypes.clear()
        self._records = 0
        self._source_ids = []

    def update(self, trace: Mapping[str, Any], *, record_id: str | None = None) -> None:
        token_id = trace.get("selected_token_id")
        if not isinstance(token_id, int) or isinstance(token_id, bool) or token_id < 0:
            raise ShadowStudentError("teacher trace selected_token_id is invalid")
        piece = trace.get("selected_piece", "")
        if not isinstance(piece, str):
            raise ShadowStudentError("teacher trace selected_piece is invalid")
        sketch = _decode_sketch(trace.get("field_sketch_f32_b64"))
        prototype = self._prototypes.get(token_id)
        if prototype is None:
            prototype = _Prototype(token_id=token_id, piece=piece, count=0, sum_vector=np.zeros(FEATURE_DIM, dtype=np.float64))
            self._prototypes[token_id] = prototype
        prototype.sum_vector += sketch.astype(np.float64)
        prototype.count += 1
        if piece:
            prototype.piece = piece
        self._records += 1
        if record_id is not None:
            self._source_ids.append(str(record_id))

    def fit(self, traces: Iterable[tuple[str, Mapping[str, Any]]]) -> int:
        self.clear()
        count = 0
        for record_id, trace in traces:
            self.update(trace, record_id=record_id)
            count += 1
        return count

    def predict(self, sketch: Any, *, top_k: int = 4) -> StudentPrediction | None:
        if top_k <= 0:
            raise ShadowStudentError("student top_k must be positive")
        if not self._prototypes:
            return None
        query = _normalised(_decode_sketch(sketch) if isinstance(sketch, str) else np.asarray(sketch, dtype=np.float32))
        rows: list[tuple[float, int, _Prototype]] = []
        for token_id, prototype in self._prototypes.items():
            score = float(np.dot(query, prototype.centroid()))
            rows.append((score, token_id, prototype))
        rows.sort(key=lambda row: (-row[0], row[1]))
        best_score, _, best = rows[0]
        second_score = rows[1][0] if len(rows) > 1 else -1.0
        confidence = max(0.0, min(1.0, 0.5 * (best_score - second_score + 1.0)))
        neighbors = tuple(
            {
                "token_id": token_id,
                "piece": prototype.piece,
                "score": score,
                "count": prototype.count,
                "rank": rank,
            }
            for rank, (score, token_id, prototype) in enumerate(rows[:top_k])
        )
        return StudentPrediction(best.token_id, best.piece, best_score, confidence, best.count, neighbors)

    def checkpoint(self, *, status: str = "candidate", source_trace_ids: Iterable[str] | None = None) -> dict[str, Any]:
        if status not in {"candidate", "active"}:
            raise ShadowStudentError("student status must be candidate or active")
        prototypes: list[dict[str, Any]] = []
        for token_id in sorted(self._prototypes):
            prototype = self._prototypes[token_id]
            centroid = np.asarray(prototype.centroid(), dtype="<f4")
            raw = centroid.tobytes(order="C")
            prototypes.append(
                {
                    "token_id": token_id,
                    "piece": prototype.piece,
                    "count": prototype.count,
                    "centroid_f32_b64": base64.b64encode(raw).decode("ascii"),
                    "centroid_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        ids = list(source_trace_ids) if source_trace_ids is not None else list(self._source_ids)
        return {
            "protocol": PROTOCOL,
            "version": VERSION,
            "status": status,
            "model_sha256": self.model_sha256,
            "feature_dim": FEATURE_DIM,
            "trained_records": self._records,
            "source_trace_ids": ids,
            "prototypes": prototypes,
        }

    def save(self, path: Path, *, status: str = "candidate", source_trace_ids: Iterable[str] | None = None) -> None:
        _atomic_json(Path(path), self.checkpoint(status=status, source_trace_ids=source_trace_ids))

    @classmethod
    def load(cls, path: Path, *, expected_model_sha256: str | None = None) -> "ShadowStudent":
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise ShadowStudentError(f"student checkpoint cannot be read: {path}") from error
        if not isinstance(value, Mapping) or value.get("protocol") != PROTOCOL or value.get("version") != VERSION:
            raise ShadowStudentError("student checkpoint protocol/version mismatch")
        if value.get("feature_dim") != FEATURE_DIM:
            raise ShadowStudentError("student checkpoint feature dimension mismatch")
        checkpoint_model = value.get("model_sha256")
        if expected_model_sha256 is not None and checkpoint_model != expected_model_sha256:
            raise ShadowStudentError("student checkpoint model identity mismatch")
        student = cls(model_sha256=str(checkpoint_model) if checkpoint_model is not None else None)
        prototypes = value.get("prototypes")
        if not isinstance(prototypes, list):
            raise ShadowStudentError("student checkpoint prototypes are malformed")
        for row in prototypes:
            if not isinstance(row, Mapping):
                raise ShadowStudentError("student checkpoint prototype is malformed")
            token_id, piece, count = row.get("token_id"), row.get("piece", ""), row.get("count")
            if not isinstance(token_id, int) or isinstance(token_id, bool) or token_id < 0 or not isinstance(piece, str) or not isinstance(count, int) or count <= 0:
                raise ShadowStudentError("student checkpoint prototype metadata is invalid")
            encoded = row.get("centroid_f32_b64")
            centroid = _decode_sketch(encoded)
            digest = row.get("centroid_sha256")
            if digest != hashlib.sha256(np.asarray(centroid, dtype="<f4").tobytes(order="C")).hexdigest():
                raise ShadowStudentError("student checkpoint centroid checksum mismatch")
            student._prototypes[token_id] = _Prototype(token_id, piece, count, centroid.astype(np.float64) * count)
        records = value.get("trained_records", 0)
        if not isinstance(records, int) or records < 0:
            raise ShadowStudentError("student checkpoint trained_records is invalid")
        if sum(prototype.count for prototype in student._prototypes.values()) != records:
            raise ShadowStudentError("student checkpoint prototype counts do not match trained_records")
        source_ids = value.get("source_trace_ids", [])
        if not isinstance(source_ids, list) or not all(isinstance(item, str) for item in source_ids) or len(source_ids) != records:
            raise ShadowStudentError("student checkpoint source IDs are invalid")
        student._records = records
        student._source_ids = list(source_ids)
        return student


def train_candidate(store: TeacherTraceStore, path: Path, *, model_sha256: str | None = None) -> dict[str, Any]:
    ids = store.list_ids()
    student = ShadowStudent(model_sha256=model_sha256)
    student.fit((record_id, store.replay(record_id)) for record_id in ids)
    student.save(path, status="candidate", source_trace_ids=ids)
    return student.checkpoint(status="candidate", source_trace_ids=ids)
