from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Generic, Literal, TypeVar, cast


PACKET_SCHEMA = "cassi.universal-boundary-packet.v1"
VIEW_SCHEMA = "cassi.typed-observation-view.v1"
JOURNAL_PACKET_SCHEMA = "cassi.ingress-journal.packet.v1"
JOURNAL_MANIFEST_SCHEMA = "cassi.ingress-journal.manifest.v1"
JOURNAL_HEAD_SCHEMA = "cassi.ingress-journal.head.v1"
ZERO_SHA256 = "0" * 64
_CHUNK_BYTES = 1024 * 1024

_JSON_CODEC = "cassi.codec.json-utf8.v1"
_RASTER_CODEC = "cassi.codec.raster-u8-c.v1"
_TEXT_CODEC = "cassi.codec.utf8.v1"
_CODE_CODEC = "cassi.codec.python-utf8.v1"
_AUDIO_CODEC = "cassi.codec.audio-f64le.v1"
_TENSOR_CODEC = "cassi.codec.tensor-c.v1"
_OPAQUE_CODEC = "cassi.codec.opaque-bytes.v1"

CODEC_JSON = _JSON_CODEC
CODEC_RASTER = _RASTER_CODEC
CODEC_TEXT = _TEXT_CODEC
CODEC_CODE = _CODE_CODEC
CODEC_AUDIO = _AUDIO_CODEC
CODEC_TENSOR = _TENSOR_CODEC
CODEC_OPAQUE = _OPAQUE_CODEC

_CODEC_MODALITY = {
    _JSON_CODEC: "json",
    _RASTER_CODEC: "raster",
    _TEXT_CODEC: "text",
    _CODE_CODEC: "code",
    _AUDIO_CODEC: "audio",
    _TENSOR_CODEC: "scientific_tensor",
    _OPAQUE_CODEC: "opaque",
}


class UniversalDataError(ValueError):
    """Invalid exact packet, observation view, journal, or admission record."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise UniversalDataError("value is not canonical JSON data") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _digest(value: str, name: str, *, allow_zero: bool = True) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
        or any(character not in "0123456789abcdef" for character in value)
        or (not allow_zero and value == ZERO_SHA256)
    ):
        raise UniversalDataError(f"{name} must be a lowercase 64-hex SHA-256 digest")
    return value


def _text(value: str, name: str, *, limit: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > limit:
        raise UniversalDataError(f"{name} must be nonempty and at most {limit} UTF-8 bytes")
    return value


def _integer(value: int, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise UniversalDataError(f"{name} must be an integer of at least {minimum}")
    return value


def _optional_integer(value: int | None, name: str) -> int | None:
    return None if value is None else _integer(value, name)


def _fraction_payload(value: Fraction) -> dict[str, int]:
    if not isinstance(value, Fraction):
        raise UniversalDataError("packet times must be fractions")
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_from_payload(value: Any, name: str) -> Fraction:
    if (
        not isinstance(value, dict)
        or set(value) != {"numerator", "denominator"}
        or isinstance(value["numerator"], bool)
        or not isinstance(value["numerator"], int)
        or isinstance(value["denominator"], bool)
        or not isinstance(value["denominator"], int)
        or value["denominator"] <= 0
    ):
        raise UniversalDataError(f"{name} must be a canonical rational time")
    return Fraction(value["numerator"], value["denominator"])

def descriptor_sha256(codec_id: str) -> str:
    codec = _text(codec_id, "codec_id")
    if codec not in _CODEC_MODALITY:
        raise UniversalDataError(f"unsupported codec: {codec}")
    return _sha256_json(
        {
            "schema": "cassi.deterministic-adapter-descriptor.v1",
            "codec_id": codec,
            "modality": _CODEC_MODALITY[codec],
            "lossless": True,
            "adaptive_state": False,
        }
    )


@dataclass(frozen=True, slots=True)
class BoundaryIdentity:
    run_id: str
    episode_id: str
    world_id: str
    session_id: str
    profile_sha256: str
    clock_sha256: str
    source_epoch: str
    source_stream_id: str
    body_frame_id: str

    def __post_init__(self) -> None:
        for name in ("run_id", "episode_id", "world_id", "session_id", "source_epoch", "source_stream_id", "body_frame_id"):
            _text(getattr(self, name), name)
        _digest(self.profile_sha256, "profile_sha256")
        _digest(self.clock_sha256, "clock_sha256")


@dataclass(frozen=True, slots=True)
class BoundaryPacket:
    schema: str
    identity: BoundaryIdentity
    descriptor_sha256: str
    event_id: str
    request_id: str
    logical_tick: int
    logical_time: Fraction
    capture_start: Fraction
    capture_end: Fraction
    source_sequence: int
    source_timestamp_ns_telemetry: int | None
    arrival_sequence_telemetry: int | None
    watermark_sha256: str
    ingress_journal_sha256: str
    antialias_receipt_sha256: str | None
    causal_parent_event_id: str | None
    causal_parent_action_id: str | None
    payload_shape: tuple[int, ...]
    payload_dtype: str
    payload: bytes
    payload_sha256: str
    valid: bool

    def __post_init__(self) -> None:
        if self.schema != PACKET_SCHEMA:
            raise UniversalDataError("boundary packet schema is unsupported")
        if not isinstance(self.identity, BoundaryIdentity):
            raise UniversalDataError("boundary packet identity is invalid")
        _digest(self.descriptor_sha256, "descriptor_sha256", allow_zero=False)
        _digest(self.event_id, "event_id", allow_zero=False)
        _text(self.request_id, "request_id")
        _integer(self.logical_tick, "logical_tick")
        for time in (self.logical_time, self.capture_start, self.capture_end):
            _fraction_payload(time)
        if self.capture_start > self.capture_end or self.capture_end > self.logical_time:
            raise UniversalDataError("capture times must be ordered and no later than logical time")
        _integer(self.source_sequence, "source_sequence")
        _optional_integer(self.source_timestamp_ns_telemetry, "source_timestamp_ns_telemetry")
        _optional_integer(self.arrival_sequence_telemetry, "arrival_sequence_telemetry")
        _digest(self.watermark_sha256, "watermark_sha256")
        _digest(self.ingress_journal_sha256, "ingress_journal_sha256")
        for name in ("antialias_receipt_sha256", "causal_parent_event_id"):
            value = getattr(self, name)
            if value is not None:
                _digest(value, name, allow_zero=False)
        if self.causal_parent_action_id is not None:
            _text(self.causal_parent_action_id, "causal_parent_action_id")
        if not isinstance(self.payload_shape, tuple) or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.payload_shape
        ):
            raise UniversalDataError("payload_shape must contain non-negative dimensions")
        _text(self.payload_dtype, "payload_dtype", limit=64)
        if not isinstance(self.valid, bool):
            raise UniversalDataError("packet valid flag must be boolean")
        if not isinstance(self.payload, bytes):
            raise UniversalDataError("packet payload must be owned immutable bytes")
        _digest(self.payload_sha256, "payload_sha256")
        if _sha256_bytes(self.payload) != self.payload_sha256:
            raise UniversalDataError("packet payload digest does not match its bytes")
        if self.valid and (not self.payload_shape or any(value == 0 for value in self.payload_shape)):
            raise UniversalDataError("valid packet shape must be nonempty and nonzero")
        if not self.valid and self.payload:
            raise UniversalDataError("invalid or no-sample packet cannot carry payload bytes")
        if self.event_id != _sha256_json(self.event_body()):
            raise UniversalDataError("boundary event identity does not match packet content")

    @classmethod
    def create(
        cls,
        *,
        identity: BoundaryIdentity,
        codec_id: str,
        request_id: str,
        logical_tick: int,
        logical_time: Fraction,
        capture_start: Fraction,
        capture_end: Fraction,
        source_sequence: int,
        payload_shape: Sequence[int],
        payload_dtype: str,
        payload: bytes,
        watermark_sha256: str = ZERO_SHA256,
        ingress_journal_sha256: str = ZERO_SHA256,
        source_timestamp_ns_telemetry: int | None = None,
        arrival_sequence_telemetry: int | None = None,
        antialias_receipt_sha256: str | None = None,
        causal_parent_event_id: str | None = None,
        causal_parent_action_id: str | None = None,
        valid: bool = True,
    ) -> BoundaryPacket:
        owned = bytes(payload)
        values = {
            "schema": PACKET_SCHEMA,
            "identity": identity,
            "descriptor_sha256": descriptor_sha256(codec_id),
            "event_id": ZERO_SHA256,
            "request_id": request_id,
            "logical_tick": logical_tick,
            "logical_time": logical_time,
            "capture_start": capture_start,
            "capture_end": capture_end,
            "source_sequence": source_sequence,
            "source_timestamp_ns_telemetry": source_timestamp_ns_telemetry,
            "arrival_sequence_telemetry": arrival_sequence_telemetry,
            "watermark_sha256": watermark_sha256,
            "ingress_journal_sha256": ingress_journal_sha256,
            "antialias_receipt_sha256": antialias_receipt_sha256,
            "causal_parent_event_id": causal_parent_event_id,
            "causal_parent_action_id": causal_parent_action_id,
            "payload_shape": tuple(payload_shape),
            "payload_dtype": payload_dtype,
            "payload": owned,
            "payload_sha256": _sha256_bytes(owned),
            "valid": valid,
        }
        provisional = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(provisional, name, value)
        values["event_id"] = _sha256_json(provisional.event_body())
        return cls(**values)

    def event_body(self) -> dict[str, Any]:
        return {
            "schema": "cassi.universal-boundary-event.v1",
            **self.metadata(include_event_id=False),
        }

    def metadata(self, *, include_event_id: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": self.schema,
            "run_id": self.identity.run_id,
            "episode_id": self.identity.episode_id,
            "world_id": self.identity.world_id,
            "session_id": self.identity.session_id,
            "profile_sha256": self.identity.profile_sha256,
            "clock_sha256": self.identity.clock_sha256,
            "descriptor_sha256": self.descriptor_sha256,
            "request_id": self.request_id,
            "logical_tick": self.logical_tick,
            "logical_time": _fraction_payload(self.logical_time),
            "capture_start": _fraction_payload(self.capture_start),
            "capture_end": _fraction_payload(self.capture_end),
            "source_epoch": self.identity.source_epoch,
            "source_stream_id": self.identity.source_stream_id,
            "source_sequence": self.source_sequence,
            "source_timestamp_ns_telemetry": self.source_timestamp_ns_telemetry,
            "arrival_sequence_telemetry": self.arrival_sequence_telemetry,
            "watermark_sha256": self.watermark_sha256,
            "ingress_journal_sha256": self.ingress_journal_sha256,
            "antialias_receipt_sha256": self.antialias_receipt_sha256,
            "causal_parent_event_id": self.causal_parent_event_id,
            "causal_parent_action_id": self.causal_parent_action_id,
            "body_frame_id": self.identity.body_frame_id,
            "payload_shape": list(self.payload_shape),
            "payload_dtype": self.payload_dtype,
            "payload_sha256": self.payload_sha256,
            "valid": self.valid,
        }
        if include_event_id:
            body["event_id"] = self.event_id
        return body

    @property
    def packet_sha256(self) -> str:
        return _sha256_json(self.metadata())


@dataclass(frozen=True, slots=True)
class JournalReference:
    packet_sha256: str
    packet_object_sha256: str
    payload_manifest_sha256: str
    journal_head_sha256: str
    source_stream_id: str
    source_sequence: int
    idempotency_event_id: str | None = None
    idempotency_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("packet_sha256", "packet_object_sha256", "payload_manifest_sha256", "journal_head_sha256"):
            _digest(getattr(self, name), name, allow_zero=False)
        _text(self.source_stream_id, "source_stream_id")
        _integer(self.source_sequence, "source_sequence")
        for name in ("idempotency_event_id", "idempotency_sha256"):
            value = getattr(self, name)
            if value is not None:
                _digest(value, name, allow_zero=False)


@dataclass(frozen=True, slots=True)
class JournalUsage:
    head_sha256: str
    logical_bytes: int
    packet_count: int
    physical_bytes: int
    object_count: int


@dataclass(frozen=True, slots=True)
class JournalAppendEstimate:
    logical_bytes: int
    packet_count: int
    physical_bytes: int
    object_count: int


class QiIngressJournal:
    """Bounded content-addressed packet/chunk ledger with deterministic replay."""

    def __init__(self, root: str | Path, *, max_bytes: int = 64 * 1024 * 1024) -> None:
        self.root = Path(root)
        self.max_bytes = _integer(max_bytes, "max_bytes", minimum=1)
        self.objects = self.root / "objects"
        self.blobs = self.root / "blobs"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.blobs.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.root / "APPEND.lock"
        self._lock_path.touch(exist_ok=True)
        self._thread_lock = threading.RLock()
        self._index_head: str | None = None
        self._event_index: dict[str, JournalReference] = {}
        self._idempotency_index: dict[str, tuple[str, JournalReference]] = {}
        self._stream_watermarks: dict[str, JournalReference] = {}

    @property
    def head_path(self) -> Path:
        return self.root / "HEAD"

    @contextmanager
    def _append_lock(self):
        with self._thread_lock:
            with self._lock_path.open("r+b") as handle:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    try:
                        yield
                    finally:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _put(path: Path, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = path / digest
        try:
            with target.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            try:
                existing = target.read_bytes()
            except OSError as exc:
                raise UniversalDataError(f"journal object {digest} is unreadable") from exc
            if existing != payload:
                raise UniversalDataError("content-addressed journal collision")
        QiIngressJournal._fsync_directory(path)
        return digest

    def _put_json(self, value: Mapping[str, Any]) -> str:
        return self._put(self.objects, canonical_json_bytes(dict(value)))

    @staticmethod
    def _idempotency_fingerprint(packet: BoundaryPacket) -> str:
        metadata = packet.metadata(include_event_id=False)
        metadata["ingress_journal_sha256"] = ZERO_SHA256
        return _sha256_json(
            {
                "schema": "cassi.ingress-journal.idempotency.v1",
                "metadata": metadata,
            }
        )

    @staticmethod
    def _packet_object(
        packet: BoundaryPacket,
        idempotency_event_id: str | None,
        idempotency_sha256: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": JOURNAL_PACKET_SCHEMA,
            "packet_sha256": packet.packet_sha256,
            "metadata": packet.metadata(),
            "idempotency_event_id": idempotency_event_id,
            "idempotency_sha256": idempotency_sha256,
        }
    def _rebuild_indexes(self, head_sha256: str) -> None:

        events: dict[str, JournalReference] = {}
        idempotency: dict[str, tuple[str, JournalReference]] = {}
        watermarks: dict[str, JournalReference] = {}
        for reference in self.replay():
            head = self._read_json(reference.journal_head_sha256)
            event_id = _digest(
                cast(str, head.get("event_id")),
                "journal event_id",
                allow_zero=False,
            )
            if event_id in events:
                raise UniversalDataError("ingress journal contains a duplicate event identity")
            events[event_id] = reference
            idempotency_event_id = head.get("idempotency_event_id")
            idempotency_sha256 = head.get("idempotency_sha256")
            if idempotency_event_id is not None or idempotency_sha256 is not None:
                event_key = _digest(
                    cast(str, idempotency_event_id),
                    "idempotency_event_id",
                    allow_zero=False,
                )
                fingerprint = _digest(
                    cast(str, idempotency_sha256),
                    "idempotency_sha256",
                    allow_zero=False,
                )
                if event_key in idempotency:
                    raise UniversalDataError(
                        "ingress journal contains a duplicate idempotency identity"
                    )
                idempotency[event_key] = (fingerprint, reference)
            previous = watermarks.get(reference.source_stream_id)
            if previous is not None and reference.source_sequence <= previous.source_sequence:
                raise UniversalDataError(
                    "ingress journal contains a nonincreasing stream sequence"
                )
            watermarks[reference.source_stream_id] = reference
        if self._head() != head_sha256:
            raise UniversalDataError("ingress journal advanced while rebuilding indexes")
        self._event_index = events
        self._idempotency_index = idempotency
        self._stream_watermarks = watermarks
        self._index_head = head_sha256

    def _ensure_indexes(self, head_sha256: str) -> None:
        if self._index_head != head_sha256:
            self._rebuild_indexes(head_sha256)

    def _read_json(self, digest: str) -> dict[str, Any]:
        _digest(digest, "journal object", allow_zero=False)
        try:
            raw = (self.objects / digest).read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UniversalDataError(f"journal object {digest} is unreadable") from exc
        if _sha256_bytes(raw) != digest or not isinstance(value, dict):
            raise UniversalDataError("journal object identity is invalid")
        return value

    def _head(self) -> str:
        if not self.head_path.exists():
            return ZERO_SHA256
        try:
            value = self.head_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError) as exc:
            raise UniversalDataError("ingress journal HEAD is unreadable") from exc
        return _digest(value, "journal HEAD")

    @property
    def head_sha256(self) -> str:
        return self._head()

    @staticmethod
    def _reference_from_head(head: Mapping[str, Any], head_sha256: str) -> JournalReference:
        return JournalReference(
            packet_sha256=cast(str, head.get("packet_sha256")),
            packet_object_sha256=cast(str, head.get("packet_object_sha256")),
            payload_manifest_sha256=cast(str, head.get("payload_manifest_sha256")),
            journal_head_sha256=head_sha256,
            source_stream_id=cast(str, head.get("source_stream_id")),
            source_sequence=cast(int, head.get("source_sequence")),
            idempotency_event_id=cast(str | None, head.get("idempotency_event_id")),
            idempotency_sha256=cast(str | None, head.get("idempotency_sha256")),
        )

    def _replace_head(self, digest: str) -> None:
        temporary = self.head_path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            handle.write((digest + "\n").encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.head_path)
        self._fsync_directory(self.root)

    @property
    def usage(self) -> JournalUsage:
        head_sha256 = self._head()
        logical_bytes = 0
        if head_sha256 != ZERO_SHA256:
            head = self._read_json(head_sha256)
            if head.get("schema") != JOURNAL_HEAD_SCHEMA:
                raise UniversalDataError("journal HEAD object schema is invalid")
            logical_bytes = _integer(
                cast(int, head.get("cumulative_bytes")),
                "cumulative_bytes",
            )
        files = tuple(path for path in self.root.rglob("*") if path.is_file())
        return JournalUsage(
            head_sha256=head_sha256,
            logical_bytes=logical_bytes,
            packet_count=len(self.replay()),
            physical_bytes=sum(path.stat().st_size for path in files),
            object_count=len(files),
        )

    def estimate_append(
        self,
        packet: BoundaryPacket,
        *,
        idempotency_event_id: str | None = None,
    ) -> JournalAppendEstimate:
        if not isinstance(packet, BoundaryPacket):
            raise UniversalDataError("journal estimate requires a boundary packet")
        if idempotency_event_id is not None:
            idempotency_event_id = _digest(
                idempotency_event_id,
                "idempotency_event_id",
                allow_zero=False,
            )
        idempotency_sha256 = (
            None
            if idempotency_event_id is None
            else self._idempotency_fingerprint(packet)
        )
        packet_object = self._packet_object(
            packet,
            idempotency_event_id,
            idempotency_sha256,
        )
        packet_bytes = canonical_json_bytes(packet_object)
        previous = self._head()
        prior_bytes = 0
        if previous != ZERO_SHA256:
            prior = self._read_json(previous)
            if prior.get("schema") != JOURNAL_HEAD_SCHEMA:
                raise UniversalDataError("journal HEAD object schema is invalid")
            prior_bytes = _integer(
                cast(int, prior.get("cumulative_bytes")),
                "cumulative_bytes",
            )
        physical_bytes = 65
        object_count = 1
        chunks = []
        for start in range(0, len(packet.payload), _CHUNK_BYTES):
            chunk = packet.payload[start : start + _CHUNK_BYTES]
            digest = _sha256_bytes(chunk)
            chunks.append({"sha256": digest, "bytes": len(chunk)})
            if not (self.blobs / digest).exists():
                physical_bytes += len(chunk)
                object_count += 1
        manifest = {
            "schema": JOURNAL_MANIFEST_SCHEMA,
            "payload_sha256": packet.payload_sha256,
            "payload_bytes": len(packet.payload),
            "chunks": chunks,
        }
        manifest_bytes = canonical_json_bytes(manifest)
        manifest_sha = _sha256_bytes(manifest_bytes)
        if not (self.objects / manifest_sha).exists():
            physical_bytes += len(manifest_bytes)
            object_count += 1
        packet_object_sha = _sha256_bytes(packet_bytes)
        if not (self.objects / packet_object_sha).exists():
            physical_bytes += len(packet_bytes)
            object_count += 1
        cumulative = prior_bytes + len(packet.payload) + len(packet_bytes)
        head = {
            "schema": JOURNAL_HEAD_SCHEMA,
            "previous_head_sha256": previous,
            "packet_sha256": packet.packet_sha256,
            "packet_object_sha256": packet_object_sha,
            "payload_manifest_sha256": manifest_sha,
            "event_id": packet.event_id,
            "idempotency_event_id": idempotency_event_id,
            "idempotency_sha256": idempotency_sha256,
            "source_stream_id": packet.identity.source_stream_id,
            "source_sequence": packet.source_sequence,
            "cumulative_bytes": cumulative,
        }
        head_bytes = canonical_json_bytes(head)
        head_sha = _sha256_bytes(head_bytes)
        if not (self.objects / head_sha).exists():
            physical_bytes += len(head_bytes)
            object_count += 1
        return JournalAppendEstimate(
            logical_bytes=len(packet.payload) + len(packet_bytes),
            packet_count=1,
            physical_bytes=physical_bytes,
            object_count=object_count,
        )

    def append(
        self,
        packet: BoundaryPacket,
        *,
        idempotency_event_id: str | None = None,
    ) -> JournalReference:
        if not isinstance(packet, BoundaryPacket):
            raise UniversalDataError("journal append requires a boundary packet")
        if idempotency_event_id is not None:
            idempotency_event_id = _digest(
                idempotency_event_id,
                "idempotency_event_id",
                allow_zero=False,
            )
        idempotency_sha256 = (
            None
            if idempotency_event_id is None
            else self._idempotency_fingerprint(packet)
        )
        with self._append_lock():
            previous = self._head()
            self._ensure_indexes(previous)
            existing_event = self._event_index.get(packet.event_id)
            if existing_event is not None:
                if self.read_packet(existing_event) != packet:
                    raise UniversalDataError(
                        "journal event identity conflicts with existing packet"
                    )
                return existing_event
            if idempotency_event_id is not None:
                existing = self._idempotency_index.get(idempotency_event_id)
                if existing is not None:
                    fingerprint, reference = existing
                    if fingerprint != idempotency_sha256:
                        raise UniversalDataError(
                            "idempotency event identity conflicts with existing payload"
                        )
                    return reference
            if packet.ingress_journal_sha256 != previous:
                raise UniversalDataError("packet ingress journal parent does not match HEAD")
            prior_stream = self._stream_watermarks.get(
                packet.identity.source_stream_id
            )
            if (
                prior_stream is not None
                and packet.source_sequence <= prior_stream.source_sequence
            ):
                raise UniversalDataError("packet source sequence is not strictly increasing")
            packet_object = self._packet_object(
                packet,
                idempotency_event_id,
                idempotency_sha256,
            )
            prior_bytes = 0
            if previous != ZERO_SHA256:
                prior = self._read_json(previous)
                if prior.get("schema") != JOURNAL_HEAD_SCHEMA:
                    raise UniversalDataError("journal HEAD object schema is invalid")
                prior_bytes = _integer(
                    cast(int, prior.get("cumulative_bytes")),
                    "cumulative_bytes",
                )
            cumulative = (
                prior_bytes
                + len(packet.payload)
                + len(canonical_json_bytes(packet_object))
            )
            if cumulative > self.max_bytes:
                raise UniversalDataError("ingress journal capacity would be exceeded")
            chunks = []
            for start in range(0, len(packet.payload), _CHUNK_BYTES):
                chunk = packet.payload[start : start + _CHUNK_BYTES]
                chunks.append(
                    {
                        "sha256": self._put(self.blobs, chunk),
                        "bytes": len(chunk),
                    }
                )
            manifest = {
                "schema": JOURNAL_MANIFEST_SCHEMA,
                "payload_sha256": packet.payload_sha256,
                "payload_bytes": len(packet.payload),
                "chunks": chunks,
            }
            manifest_sha = self._put_json(manifest)
            packet_object_sha = self._put_json(packet_object)
            head = {
                "schema": JOURNAL_HEAD_SCHEMA,
                "previous_head_sha256": previous,
                "packet_sha256": packet.packet_sha256,
                "packet_object_sha256": packet_object_sha,
                "payload_manifest_sha256": manifest_sha,
                "event_id": packet.event_id,
                "idempotency_event_id": idempotency_event_id,
                "idempotency_sha256": idempotency_sha256,
                "source_stream_id": packet.identity.source_stream_id,
                "source_sequence": packet.source_sequence,
                "cumulative_bytes": cumulative,
            }
            head_sha = self._put_json(head)
            if self._head() != previous:
                self._index_head = None
                raise UniversalDataError("ingress journal advanced concurrently")
            self._replace_head(head_sha)
            reference = JournalReference(
                packet_sha256=packet.packet_sha256,
                packet_object_sha256=packet_object_sha,
                payload_manifest_sha256=manifest_sha,
                journal_head_sha256=head_sha,
                source_stream_id=packet.identity.source_stream_id,
                source_sequence=packet.source_sequence,
                idempotency_event_id=idempotency_event_id,
                idempotency_sha256=idempotency_sha256,
            )
            self._event_index[packet.event_id] = reference
            if idempotency_event_id is not None:
                assert idempotency_sha256 is not None
                self._idempotency_index[idempotency_event_id] = (
                    idempotency_sha256,
                    reference,
                )
            self._stream_watermarks[packet.identity.source_stream_id] = reference
            self._index_head = head_sha
            return reference

    def read_payload(self, reference: JournalReference) -> bytes:
        manifest = self._read_json(reference.payload_manifest_sha256)
        if manifest.get("schema") != JOURNAL_MANIFEST_SCHEMA:
            raise UniversalDataError("payload manifest schema is invalid")
        chunks = manifest.get("chunks")
        if not isinstance(chunks, list):
            raise UniversalDataError("payload manifest chunks are invalid")
        payload = bytearray()
        for row in chunks:
            if not isinstance(row, dict) or set(row) != {"sha256", "bytes"}:
                raise UniversalDataError("payload chunk entry is invalid")
            digest = _digest(row["sha256"], "payload chunk", allow_zero=False)
            size = _integer(row["bytes"], "payload chunk bytes")
            try:
                chunk = (self.blobs / digest).read_bytes()
            except OSError as exc:
                raise UniversalDataError(f"payload chunk {digest} is unreadable") from exc
            if len(chunk) != size or _sha256_bytes(chunk) != digest:
                raise UniversalDataError("payload chunk identity is invalid")
            payload.extend(chunk)
        result = bytes(payload)
        if len(result) != manifest.get("payload_bytes") or _sha256_bytes(result) != manifest.get("payload_sha256"):
            raise UniversalDataError("replayed payload identity is invalid")
        return result

    def replay(self) -> tuple[JournalReference, ...]:
        cursor = self._head()
        rows: list[JournalReference] = []
        seen: set[str] = set()
        while cursor != ZERO_SHA256:
            if cursor in seen:
                raise UniversalDataError("ingress journal contains a cycle")
            seen.add(cursor)
            head = self._read_json(cursor)
            if head.get("schema") != JOURNAL_HEAD_SCHEMA:
                raise UniversalDataError("journal HEAD object schema is invalid")
            rows.append(self._reference_from_head(head, cursor))
            cursor = _digest(cast(str, head.get("previous_head_sha256")), "previous journal HEAD")
        rows.reverse()
        return tuple(rows)
    def read_packet(self, reference: JournalReference) -> BoundaryPacket:
        packet_object = self._read_json(reference.packet_object_sha256)
        if packet_object.get("schema") != JOURNAL_PACKET_SCHEMA:
            raise UniversalDataError("journal packet object schema is invalid")
        metadata_value = packet_object.get("metadata")
        if not isinstance(metadata_value, dict):
            raise UniversalDataError("journal packet metadata is invalid")
        metadata = cast(dict[str, Any], metadata_value)
        identity = BoundaryIdentity(
            run_id=metadata["run_id"],
            episode_id=metadata["episode_id"],
            world_id=metadata["world_id"],
            session_id=metadata["session_id"],
            profile_sha256=metadata["profile_sha256"],
            clock_sha256=metadata["clock_sha256"],
            source_epoch=metadata["source_epoch"],
            source_stream_id=metadata["source_stream_id"],
            body_frame_id=metadata["body_frame_id"],
        )
        packet = BoundaryPacket(
            schema=metadata["schema"],
            identity=identity,
            descriptor_sha256=metadata["descriptor_sha256"],
            event_id=metadata["event_id"],
            request_id=metadata["request_id"],
            logical_tick=metadata["logical_tick"],
            logical_time=_fraction_from_payload(metadata["logical_time"], "logical_time"),
            capture_start=_fraction_from_payload(metadata["capture_start"], "capture_start"),
            capture_end=_fraction_from_payload(metadata["capture_end"], "capture_end"),
            source_sequence=metadata["source_sequence"],
            source_timestamp_ns_telemetry=metadata.get("source_timestamp_ns_telemetry"),
            arrival_sequence_telemetry=metadata.get("arrival_sequence_telemetry"),
            watermark_sha256=metadata["watermark_sha256"],
            ingress_journal_sha256=metadata["ingress_journal_sha256"],
            antialias_receipt_sha256=metadata.get("antialias_receipt_sha256"),
            causal_parent_event_id=metadata.get("causal_parent_event_id"),
            causal_parent_action_id=metadata.get("causal_parent_action_id"),
            payload_shape=tuple(metadata["payload_shape"]),
            payload_dtype=metadata["payload_dtype"],
            payload=self.read_payload(reference),
            payload_sha256=metadata["payload_sha256"],
            valid=metadata["valid"],
        )
        if (
            packet.packet_sha256 != reference.packet_sha256
            or packet.packet_sha256 != packet_object.get("packet_sha256")
        ):
            raise UniversalDataError("replayed packet identity is invalid")
        return packet


PathSegment = str | int


@dataclass(frozen=True, slots=True)
class SourceLocation:
    packet_sha256: str
    codec_id: str
    path: tuple[PathSegment, ...] = ()
    span: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        _digest(self.packet_sha256, "source packet", allow_zero=False)
        descriptor_sha256(self.codec_id)
        if not isinstance(self.path, tuple) or any(
            isinstance(value, bool) or not isinstance(value, (str, int)) for value in self.path
        ):
            raise UniversalDataError("source path must contain strings or integers")
        if self.span is not None and (
            not isinstance(self.span, tuple)
            or len(self.span) != 2
            or self.span[0] < 0
            or self.span[1] < self.span[0]
        ):
            raise UniversalDataError("source span must be an ordered byte interval")


@dataclass(frozen=True, slots=True)
class Atom:
    source: SourceLocation
    primitive_type: Literal["null", "bool", "int", "float", "utf8", "bytes"]
    value: None | bool | int | float | str = None


@dataclass(frozen=True, slots=True)
class Collection:
    source: SourceLocation
    kind: Literal["sequence", "map", "syntax"]
    items: tuple[tuple[PathSegment, ObservationNode], ...]


@dataclass(frozen=True, slots=True)
class Tensor:
    source: SourceLocation
    dtype: str
    shape: tuple[int, ...]
    strides: tuple[int, ...]
    block_sha256: str
    units: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Relation:
    source: SourceLocation
    kind: str
    from_path: tuple[PathSegment, ...]
    to_path: tuple[PathSegment, ...]


@dataclass(frozen=True, slots=True)
class Event:
    source: SourceLocation
    before: SourceLocation
    operation: ObservationNode
    after: SourceLocation | None
    logical_time: Fraction


ObservationNode = Atom | Collection | Tensor | Relation | Event


def _validate_view_node(
    node: ObservationNode,
    packet: BoundaryPacket,
    codec_id: str,
) -> None:
    if not isinstance(node, (Atom, Collection, Tensor, Relation, Event)):
        raise UniversalDataError("observation view contains an unknown constructor")
    source = node.source
    if (
        not isinstance(source, SourceLocation)
        or source.packet_sha256 != packet.packet_sha256
        or source.codec_id != codec_id
        or (source.span is not None and source.span[1] > len(packet.payload))
    ):
        raise UniversalDataError("observation node provenance does not match its packet")
    if isinstance(node, Atom):
        valid = {
            "null": node.value is None,
            "bool": isinstance(node.value, bool),
            "int": isinstance(node.value, int) and not isinstance(node.value, bool),
            "float": isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
            and math.isfinite(float(node.value)),
            "utf8": isinstance(node.value, str),
            "bytes": node.value is None,
        }
        if node.primitive_type not in valid or not valid[node.primitive_type]:
            raise UniversalDataError("observation atom primitive and value disagree")
        return
    if isinstance(node, Collection):
        if (
            node.kind not in ("sequence", "map", "syntax")
            or not isinstance(node.items, tuple)
            or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or isinstance(item[0], bool)
                or not isinstance(item[0], (str, int))
                for item in node.items
            )
        ):
            raise UniversalDataError("observation collection is invalid")
        keys = tuple(item[0] for item in node.items)
        if len(set(keys)) != len(keys):
            raise UniversalDataError("observation collection paths must be unique")
        for key, child in node.items:
            if child.source.path != node.source.path + (key,):
                raise UniversalDataError(
                    "observation collection child path is not exact"
                )
            _validate_view_node(child, packet, codec_id)
        return
    if isinstance(node, Tensor):
        if (
            not node.shape
            or any(
                isinstance(size, bool) or not isinstance(size, int) or size < 1
                for size in node.shape
            )
            or len(node.strides) != len(node.shape)
            or any(
                isinstance(stride, bool)
                or not isinstance(stride, int)
                or stride < 1
                for stride in node.strides
            )
            or not isinstance(node.units, tuple)
            or any(not isinstance(unit, str) for unit in node.units)
        ):
            raise UniversalDataError("observation tensor shape or metadata is invalid")
        _text(node.dtype, "tensor dtype", limit=64)
        _digest(node.block_sha256, "tensor block_sha256", allow_zero=False)
        return
    if isinstance(node, Relation):
        _text(node.kind, "relation kind")
        for path in (node.from_path, node.to_path):
            if not isinstance(path, tuple) or any(
                isinstance(segment, bool)
                or not isinstance(segment, (str, int))
                for segment in path
            ):
                raise UniversalDataError("observation relation path is invalid")
        return
    if not isinstance(node.logical_time, Fraction):
        raise UniversalDataError("observation event logical time must be rational")
    if not isinstance(node.before, SourceLocation) or (
        node.after is not None and not isinstance(node.after, SourceLocation)
    ):
        raise UniversalDataError("observation event references are invalid")
    _validate_view_node(node.operation, packet, codec_id)
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class BoundaryResult(Generic[T]):
    status: Literal["selected", "ambiguous", "unsupported"]
    value: T | None
    alternatives: tuple[T, ...]
    reason: str | None
    evidence: tuple[JournalReference, ...]

    def require_selected(self) -> T:
        if self.status != "selected" or self.value is None:
            raise UniversalDataError(self.reason or f"boundary result is {self.status}")
        return self.value


@dataclass(frozen=True, slots=True)
class ObservationView:
    packet: BoundaryPacket
    codec_id: str
    modality: str
    root: ObservationNode

    def __post_init__(self) -> None:
        if descriptor_sha256(self.codec_id) != self.packet.descriptor_sha256:
            raise UniversalDataError("view codec does not match packet descriptor")
        if self.modality != _CODEC_MODALITY[self.codec_id]:
            raise UniversalDataError("view modality does not match codec")
        _validate_view_node(self.root, self.packet, self.codec_id)

    @property
    def view_sha256(self) -> str:
        return _sha256_json(
            {
                "schema": VIEW_SCHEMA,
                "packet_sha256": self.packet.packet_sha256,
                "codec_id": self.codec_id,
                "modality": self.modality,
                "root": _node_payload(self.root),
            }
        )

    def round_trip(self) -> bytes:
        return self.packet.payload


@dataclass(frozen=True, slots=True)
class MnemicObservationReference:
    record_id: str
    revision: str
    packet: JournalReference
    view_sha256: str

    def __post_init__(self) -> None:
        _text(self.record_id, "record_id")
        _digest(self.revision, "revision", allow_zero=False)
        if not isinstance(self.packet, JournalReference):
            raise UniversalDataError("Mnemic packet reference is invalid")
        _digest(self.view_sha256, "view_sha256", allow_zero=False)


@dataclass(frozen=True, slots=True)
class ThalamusAdmission:
    required: bool
    kind: str
    authority: str
    work_budget: int

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise UniversalDataError("Thalamus required flag must be boolean")
        _text(self.kind, "Thalamus kind", limit=64)
        _text(self.authority, "Thalamus authority", limit=64)
        _integer(self.work_budget, "Thalamus work_budget", minimum=1)


class _Pairs(list[tuple[str, Any]]):
    pass


def _source(packet: BoundaryPacket, codec_id: str, path: tuple[PathSegment, ...] = (), span: tuple[int, int] | None = None) -> SourceLocation:
    return SourceLocation(packet.packet_sha256, codec_id, path, span)


def _json_node(packet: BoundaryPacket, value: Any, path: tuple[PathSegment, ...]) -> ObservationNode:
    source = _source(packet, _JSON_CODEC, path)
    if isinstance(value, _Pairs):
        counts: Counter[str] = Counter()
        items = []
        for key, child in value:
            counts[key] += 1
            segment = f"{key}#{counts[key]}"
            items.append((segment, _json_node(packet, child, path + (segment,))))
        return Collection(source, "map", tuple(items))
    if isinstance(value, list):
        return Collection(
            source,
            "sequence",
            tuple((index, _json_node(packet, child, path + (index,))) for index, child in enumerate(value)),
        )
    if value is None:
        return Atom(source, "null", None)
    if isinstance(value, bool):
        return Atom(source, "bool", value)
    if isinstance(value, int):
        return Atom(source, "int", value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UniversalDataError("JSON view contains a non-finite number")
        return Atom(source, "float", value)
    if isinstance(value, str):
        return Atom(source, "utf8", value)
    raise UniversalDataError("JSON view contains an unsupported syntax value")


def _contiguous_strides(shape: tuple[int, ...]) -> tuple[int, ...]:
    stride = 1
    result = []
    for width in reversed(shape):
        result.append(stride)
        stride *= width
    return tuple(reversed(result))


def _line_offsets(payload: bytes) -> tuple[int, ...]:
    offsets = [0]
    for index, value in enumerate(payload):
        if value == 10:
            offsets.append(index + 1)
    return tuple(offsets)


def _ast_node(packet: BoundaryPacket, node: ast.AST, path: tuple[PathSegment, ...], offsets: tuple[int, ...]) -> ObservationNode:
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        lineno = cast(int, getattr(node, "lineno"))
        col_offset = cast(int, getattr(node, "col_offset"))
        end_lineno = cast(int, getattr(node, "end_lineno"))
        end_col_offset = cast(int, getattr(node, "end_col_offset"))
        start = offsets[lineno - 1] + col_offset
        end = offsets[end_lineno - 1] + end_col_offset
        span = (start, end)
    else:
        span = None
    items: list[tuple[PathSegment, ObservationNode]] = [
        ("node", Atom(_source(packet, _CODE_CODEC, path + ("node",), span), "utf8", type(node).__name__))
    ]
    for field_name, value in ast.iter_fields(node):
        field_path = path + (field_name,)
        if isinstance(value, ast.AST):
            items.append((field_name, _ast_node(packet, value, field_path, offsets)))
        elif isinstance(value, list):
            children = tuple(
                (index, _ast_node(packet, child, field_path + (index,), offsets))
                for index, child in enumerate(value)
                if isinstance(child, ast.AST)
            )
            if children:
                items.append((field_name, Collection(_source(packet, _CODE_CODEC, field_path, span), "sequence", children)))
        elif isinstance(value, (str, int, float, bool)) or value is None:
            primitive = "null" if value is None else "bool" if isinstance(value, bool) else "int" if isinstance(value, int) else "float" if isinstance(value, float) else "utf8"
            items.append((field_name, Atom(_source(packet, _CODE_CODEC, field_path, span), primitive, value)))
    return Collection(_source(packet, _CODE_CODEC, path, span), "syntax", tuple(items))


def adapt(
    packet: BoundaryPacket,
    codec_id: str,
    *,
    evidence: Sequence[JournalReference] = (),
) -> BoundaryResult[ObservationView]:
    """One deterministic ingress interface for every fixed lossless adapter."""

    if not isinstance(packet, BoundaryPacket):
        raise UniversalDataError("adapter requires a strict boundary packet")
    codec = _text(codec_id, "codec_id")
    refs = tuple(evidence)
    if codec not in _CODEC_MODALITY:
        return BoundaryResult("unsupported", None, (), "no_adapter", refs)
    if descriptor_sha256(codec) != packet.descriptor_sha256:
        return BoundaryResult("unsupported", None, (), "descriptor_mismatch", refs)
    if not packet.valid:
        return BoundaryResult(
            "unsupported",
            None,
            (),
            "invalid_or_no_sample",
            refs,
        )
    if codec in {_JSON_CODEC, _TEXT_CODEC, _CODE_CODEC, _OPAQUE_CODEC} and (
        packet.payload_dtype != "uint8"
        or packet.payload_shape != (len(packet.payload),)
    ):
        return BoundaryResult("unsupported", None, (), "malformed_input", refs)
    source = _source(packet, codec, (), (0, len(packet.payload)))
    try:
        if codec == _JSON_CODEC:
            decoded = json.loads(
                packet.payload.decode("utf-8"),
                object_pairs_hook=_Pairs,
            )
            root = _json_node(packet, decoded, ())
        elif codec in {_RASTER_CODEC, _AUDIO_CODEC, _TENSOR_CODEC}:
            widths = {
                "uint8": 1,
                "int8": 1,
                "uint16": 2,
                "int16": 2,
                "uint32": 4,
                "int32": 4,
                "float32": 4,
                "float64": 8,
            }
            width = widths.get(packet.payload_dtype)
            if codec == _RASTER_CODEC:
                if packet.payload_dtype != "uint8":
                    raise UniversalDataError("raster codec requires uint8 samples")
                width = 1
            elif codec == _AUDIO_CODEC:
                if packet.payload_dtype != "float64":
                    raise UniversalDataError("audio codec requires float64 samples")
                width = 8
            if (
                width is None
                or len(packet.payload)
                != math.prod(packet.payload_shape) * width
            ):
                raise UniversalDataError(
                    "tensor payload does not match its declared block"
                )
            root = Tensor(
                source,
                packet.payload_dtype,
                packet.payload_shape,
                _contiguous_strides(packet.payload_shape),
                packet.payload_sha256,
            )
        elif codec == _TEXT_CODEC:
            root = Atom(source, "utf8", packet.payload.decode("utf-8"))
        elif codec == _CODE_CODEC:
            text = packet.payload.decode("utf-8")
            root = _ast_node(
                packet,
                ast.parse(text),
                (),
                _line_offsets(packet.payload),
            )
        elif codec == _OPAQUE_CODEC:
            root = Atom(source, "bytes", None)
        else:
            return BoundaryResult("unsupported", None, (), "no_adapter", refs)
        view = ObservationView(packet, codec, _CODEC_MODALITY[codec], root)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        SyntaxError,
        UniversalDataError,
    ):
        return BoundaryResult("unsupported", None, (), "malformed_input", refs)
    second = ObservationView(packet, codec, _CODEC_MODALITY[codec], root)
    if view.view_sha256 != second.view_sha256 or view.round_trip() != packet.payload:
        raise UniversalDataError("adapter is not deterministic and lossless")
    return BoundaryResult("selected", view, (), None, refs)


def event_view(
    *,
    packet: BoundaryPacket,
    codec_id: str,
    before: ObservationView,
    operation: ObservationNode,
    after: ObservationView | None,
    evidence: Sequence[JournalReference] = (),
) -> BoundaryResult[ObservationView]:
    if descriptor_sha256(codec_id) != packet.descriptor_sha256:
        return BoundaryResult("unsupported", None, (), "descriptor_mismatch", tuple(evidence))
    root = Event(
        _source(packet, codec_id),
        _source(before.packet, before.codec_id),
        operation,
        None if after is None else _source(after.packet, after.codec_id),
        packet.logical_time,
    )
    view = ObservationView(packet, codec_id, _CODEC_MODALITY[codec_id], root)
    return BoundaryResult("selected", view, (), None, tuple(evidence))


def _source_payload(source: SourceLocation) -> dict[str, Any]:
    return {
        "packet_sha256": source.packet_sha256,
        "codec_id": source.codec_id,
        "path": list(source.path),
        "span": None if source.span is None else list(source.span),
    }


def _node_payload(node: ObservationNode) -> dict[str, Any]:
    if isinstance(node, Atom):
        return {"constructor": "Atom", "source": _source_payload(node.source), "primitive_type": node.primitive_type, "value": node.value}
    if isinstance(node, Collection):
        return {"constructor": "Collection", "source": _source_payload(node.source), "kind": node.kind, "items": [[key, _node_payload(value)] for key, value in node.items]}
    if isinstance(node, Tensor):
        return {"constructor": "Tensor", "source": _source_payload(node.source), "dtype": node.dtype, "shape": list(node.shape), "strides": list(node.strides), "block_sha256": node.block_sha256, "units": list(node.units)}
    if isinstance(node, Relation):
        return {"constructor": "Relation", "source": _source_payload(node.source), "kind": node.kind, "from_path": list(node.from_path), "to_path": list(node.to_path)}
    if isinstance(node, Event):
        return {"constructor": "Event", "source": _source_payload(node.source), "before": _source_payload(node.before), "operation": _node_payload(node.operation), "after": None if node.after is None else _source_payload(node.after), "logical_time": _fraction_payload(node.logical_time)}
    raise UniversalDataError("unknown observation constructor")
