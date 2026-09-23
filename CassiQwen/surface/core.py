"""Host-owned source, grant, publication, and effect broker for Cassi Surface.

Backends supply mechanics only. This module is the sole route from a typed
intention to an external effect and deliberately keeps pixel/audio bytes out of
its durable JSONL control ledger and JSON-facing results.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Callable, Mapping

from .records import (
    MAX_ACCESSIBILITY_BYTES,
    AUDIO_SAMPLE_BYTES,
    MAX_AUDIO_BYTES,
    MAX_DETAIL_BYTES,
    MAX_FRAME_BYTES,
    MAX_IDENTIFIER,
    MAX_INTENT_BYTES,
    MAX_METADATA_BYTES,
    MAX_TEXT,
    PIXEL_CHANNELS,
    ControlIntent,
    EffectOutcome,
    ObservationPublication,
    SurfaceAuthorizationError,
    SurfaceBinding,
    SurfaceCapabilityError,
    SurfaceConflictError,
    SurfaceError,
    SurfaceValidationError,
    SurfaceWaitError,
    canonical_json,
    json_value,
    normalize_operations,
)


_LEDGER_NAME = "surface-effects.jsonl"
_LEDGER_VERSION = 1
_MAX_LEDGER_BYTES = 128 << 20
_MAX_LEDGER_LINE_BYTES = 64 << 10
_OPERATION_LEDGER_RESERVE = 64 << 10
_MAX_BINDINGS = 1024
_MAX_BACKENDS = 64
_MAX_PUBLICATIONS_PER_BINDING = 4
_MAX_PAGE_READ_BYTES = 4 << 20
_PAGE_COPY_BYTES = 1 << 20
_MAX_GRANT_TTL_NS = 3_600_000_000_000
_MAX_CONTROL_DURATION_NS = 300_000_000_000
_DEFAULT_HEARTBEAT_NS = 3_000_000_000
_MAX_HEARTBEAT_NS = 30_000_000_000
_MAX_GRANT_UPDATES = 4096
_CONTROL_PREFIXES = ("keyboard.", "pointer.", "touch.", "controller.", "text.", "input.")
_MEDIA_CONTROL_OPERATIONS = frozenset({"audio.capture", "audio.playback"})
_SUPPORTED_STATES = {"supported", "available"}


@dataclass(slots=True)
class _Publication:
    generation: int
    metadata: dict[str, Any]
    width: int
    height: int
    pixel_format: str
    source_epoch: int
    geometry_revision: int


@dataclass(slots=True)
class _BindingState:
    binding_id: str
    backend: Any
    record: SurfaceBinding
    backend_binding: Mapping[str, Any]
    lock: threading.RLock = field(default_factory=threading.RLock)
    publications: OrderedDict[int, _Publication] = field(default_factory=OrderedDict)
    state: str = "bound"
    inhibited: bool = False
    human_control: bool = False
    detached: bool = False
    last_sequence: int = 0
    capture_required_after_generation: int | None = None


@dataclass(slots=True)
class _Grant:
    grant_id: str
    mission_id: str
    binding_id: str
    operations: frozenset[str]
    scope: dict[str, Any]
    expires_ns: int
    issued_ns: int
    absolute_deadline_ns: int
    heartbeat_timeout_ns: int
    lease_deadline_ns: int
    max_updates: int
    next_sequence: int = 1
    heartbeat_sequence: int = 0
    input_domain: str | None = None
    input_domain_epoch: int | None = None
    focus_epoch: int | None = None
    controller: str = "cassi"
    active: bool = True


class SurfaceBroker:
    """Serialize source publications and authorize every external effect.

    ``authorizer`` is a host callback, invoked with a bounded JSON proposal.
    It must represent an explicit interactive/host approval and return literal
    ``True`` or ``{"approved": True}``; no grant is issued if it is absent.
    """

    def __init__(
        self,
        home: Path,
        field_owner: Any | None = None,
        authorizer: Callable[[Mapping[str, Any]], bool | Mapping[str, Any]] | None = None,
    ) -> None:
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self.home / _LEDGER_NAME
        self._field_owner = field_owner
        self._authorizer = authorizer
        self._lock = threading.RLock()
        self._ledger_lock = threading.RLock()
        self._watch = threading.Condition(self._lock)
        self._backends: dict[str, Any] = {}
        self._bindings: dict[str, _BindingState] = {}
        self._grants: dict[str, _Grant] = {}
        self._domain_leases: dict[str, str] = {}
        self._domain_epochs: dict[str, int] = {}
        self._operations: dict[str, dict[str, Any]] = {}
        self._op_reservations: dict[str, int] = {}
        self._ledger_reserved_bytes = 0
        self._closed = False
        self._bind_lock = threading.RLock()
        self._source_bindings: dict[tuple[str, str], str] = {}
        self._replay_ledger()
        self._recover_inflight()
        self._watchdog = threading.Thread(target=self._watchdog_loop, name="cassi-surface-watchdog", daemon=True)
        self._watchdog.start()

    # ---- backend and source discovery ---------------------------------

    def register_backend(self, backend: Any) -> dict[str, Any]:
        """Register an already host-created duck-protocol backend."""
        backend_id = getattr(backend, "backend_id", None)
        if not isinstance(backend_id, str) or not backend_id or len(backend_id) > 128:
            raise SurfaceValidationError("backend_id must be bounded nonempty text")
        required = ("describe", "sources", "bind", "capture", "dispatch", "neutralize", "close")
        if any(not callable(getattr(backend, name, None)) for name in required):
            raise SurfaceValidationError("backend does not implement the Surface backend protocol")
        with self._lock:
            self._assert_open()
            if backend_id in self._backends:
                raise SurfaceConflictError(f"backend already registered: {backend_id}")
            if len(self._backends) >= _MAX_BACKENDS:
                raise SurfaceWaitError({"kind": "capacity", "reason": "backend registry is full", "limit": _MAX_BACKENDS})
            self._backends[backend_id] = backend
        return {"backend_id": backend_id, "registered": True}

    def describe(self) -> dict[str, Any]:
        """Return bounded backend capability and authorized-source descriptors."""
        with self._lock:
            self._assert_open()
            backends = list(self._backends.items())
        result: list[dict[str, Any]] = []
        for backend_id, backend in backends:
            try:
                descriptor = backend.describe()
                safe_descriptor = json_value(descriptor, max_bytes=MAX_METADATA_BYTES, label="backend descriptor")
                if not isinstance(safe_descriptor, dict):
                    raise SurfaceValidationError("backend descriptor must be an object")
                sources = self._list_sources_from(backend_id, backend)
                revalidation_supported = callable(getattr(backend, "revalidate", None))
                result.append({
                    "backend_id": backend_id,
                    "status": "available" if revalidation_supported else "degraded",
                    "revalidation_supported": revalidation_supported,
                    "reason": None if revalidation_supported else "read-only source revalidation is unsupported",
                    "descriptor": safe_descriptor,
                    "sources": sources,
                })
            except SurfaceWaitError as exc:
                result.append({"backend_id": backend_id, "status": "degraded", "reason": exc.details})
            except Exception as exc:
                result.append({"backend_id": backend_id, "status": "unavailable", "reason": self._exception_reason(exc)})
        return {"version": 1, "backends": result}

    def list_sources(self, backend_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._assert_open()
            backend = self._backend(backend_id)
        return self._list_sources_from(backend_id, backend)

    def _list_sources_from(self, backend_id: str, backend: Any) -> list[dict[str, Any]]:
        values = backend.sources()
        if not isinstance(values, (list, tuple)) or len(values) > 4096:
            raise SurfaceValidationError("backend sources must be a bounded list")
        sources: list[dict[str, Any]] = []
        for source in values:
            if not isinstance(source, Mapping):
                raise SurfaceValidationError("backend source descriptor must be an object")
            record = SurfaceBinding.from_mapping(source, backend_id=backend_id)
            safe = record.to_dict("")
            for key in ("modalities", "capture_modalities", "operation_states", "channel_states", "limits"):
                if key in source:
                    extra = json_value(source[key], max_bytes=16 << 10, label=f"source {key}")
                    if key in {"modalities", "capture_modalities"}:
                        extra = list(self._normalize_modalities(extra))
                    safe[key] = extra
            sources.append(safe)
        return sources


    def bind(self, backend_id: str, source_id: str) -> dict[str, Any]:
        source_id = self._required_text(source_id, "source_id", 256)
        key = (self._required_text(backend_id, "backend_id", 128), source_id)
        # Rebind transitions are serialized and the prior source is neutralized
        # before a backend is asked to acquire another session.
        with self._bind_lock:
            with self._lock:
                self._assert_open()
                backend = self._backend(backend_id)
                previous_id = self._source_bindings.get(key)
                if previous_id is None and len(self._bindings) >= _MAX_BINDINGS:
                    raise SurfaceWaitError({"kind": "capacity", "reason": "binding registry is full", "limit": _MAX_BINDINGS})
            if previous_id is not None:
                previous = self._binding_state(previous_id)
                with previous.lock:
                    released = self.release(previous_id)
                if not released["neutralization"]["confirmed"] or not released["detached"]:
                    kind = "neutralization" if not released["neutralization"]["confirmed"] else "field-publication"
                    raise SurfaceWaitError({"kind": kind,
                                            "reason": "previous source binding remains attached until release is confirmed",
                                            "binding_id": previous_id, "state": released["state"]})
            raw_binding = backend.bind(source_id)
            record = SurfaceBinding.from_mapping(raw_binding, backend_id=backend_id, source_id=source_id)
            binding_id = token_urlsafe(24)
            domain = record.input_domain or record.environment_incarnation
            with self._lock:
                self._assert_open()
                if len(self._bindings) >= _MAX_BINDINGS:
                    raise SurfaceWaitError({"kind": "capacity", "reason": "binding registry is full", "limit": _MAX_BINDINGS})
                state = _BindingState(binding_id, backend, record, dict(raw_binding))
                self._bindings[binding_id] = state
                self._source_bindings[key] = binding_id
                if domain not in self._domain_epochs:
                    self._domain_epochs[domain] = record.input_domain_epoch or 0
            view = record.to_dict(binding_id)
            for name in ("modalities", "capture_modalities", "operation_states", "channel_states", "limits"):
                if name in raw_binding:
                    value = json_value(raw_binding[name], max_bytes=16 << 10, label=f"binding {name}")
                    if name in {"modalities", "capture_modalities"}:
                        value = list(self._normalize_modalities(value))
                    view[name] = value
            return view | {"state": state.state, "input_domain": domain}


    # ---- live observation data path -----------------------------------

    def capture(self, binding_id: str, *, mission_id: str | None = None,
                grant_id: str | None = None, channels: Any | None = None) -> dict[str, Any]:
        """Capture only the requested, authorized channels into one field-owned generation."""
        if self._field_owner is None:
            raise SurfaceCapabilityError("field owner is unavailable; observations cannot be published")
        if (mission_id is None) != (grant_id is None):
            raise SurfaceValidationError("mission_id and grant_id must be supplied together")
        state = self._binding_state(binding_id)
        with state.lock:
            self._ensure_attached(state)
            self._refresh_source_binding(state, capture=True)
            if state.record.capture_state not in {"live", "available", "supported"}:
                if state.record.capture_state in {"pending", "starting", "awaiting-baseline", "warming"}:
                    raise SurfaceWaitError({"kind": "capture", "reason": f"capture is {state.record.capture_state}",
                                            "binding_id": binding_id})
                raise SurfaceCapabilityError(f"capture is {state.record.capture_state}")
            available = self._available_modalities(state)
            requested = self._normalize_modalities(channels) if channels is not None else available
            unsupported = set(requested) - set(available)
            if unsupported:
                raise SurfaceCapabilityError(f"source does not advertise modalities: {', '.join(sorted(unsupported))}")
            if not requested:
                raise SurfaceAuthorizationError("observation channel scope is empty")

            audio_grant: _Grant | None = None
            audio_status: dict[str, str] | None = None
            effective = set(requested)
            if "audio" in requested:
                if mission_id is not None and grant_id is not None:
                    try:
                        audio_grant = self._audio_capture_grant(state, mission_id, grant_id)
                    except SurfaceError:
                        if requested == ("audio",):
                            raise
                        effective.discard("audio")
                        audio_status = {"status": "not-authorized"}
                else:
                    if requested == ("audio",):
                        raise SurfaceAuthorizationError("audio-only observation requires an explicit audio.capture grant")
                    effective.discard("audio")
                    audio_status = {"status": "not-authorized"}
            if not effective:
                raise SurfaceAuthorizationError("no requested observation channel is authorized")
            capture_binding = dict(state.backend_binding)
            capture_binding["_surface_requested_modalities"] = tuple(sorted(effective))
            capture_binding["_surface_audio_enabled"] = audio_grant is not None and "audio" in effective
            if audio_grant is not None and "audio" in effective:
                capture_binding["_surface_capture_authorization"] = self._capture_authorization_context(state, audio_grant)
            try:
                captured = state.backend.capture(capture_binding)
            except Exception as exc:
                raise SurfaceWaitError({"kind": "capture", "reason": "backend capture did not complete", "binding_id": binding_id,
                                        "error": self._exception_reason(exc)}) from exc
            if not isinstance(captured, Mapping):
                raise SurfaceValidationError("backend capture result must be an object")
            captured = dict(captured)
            if "pixels" not in effective:
                captured.pop("pixels", None)
            if "accessibility" not in effective:
                captured.pop("accessibility", None)
                captured.pop("screen_text", None)
            if "audio" not in effective:
                captured.pop("audio", None)
            raw_audio = captured.get("audio")
            if raw_audio is not None and not isinstance(raw_audio, Mapping):
                raise SurfaceValidationError("audio capture result must be an object")
            has_audio_bytes = isinstance(raw_audio, Mapping) and isinstance(raw_audio.get("samples"), bytes)
            if has_audio_bytes and (audio_grant is None or not self._capture_grant_is_current(state, audio_grant)):
                captured.pop("audio", None)
                audio_status = {"status": "not-authorized"}
            elif "audio" in effective and audio_grant is not None and not has_audio_bytes:
                audio_status = self._safe_audio_status(captured.get("audio_status"), fallback="unavailable")
            if "audio" in effective and audio_status is None and not has_audio_bytes:
                audio_status = self._safe_audio_status(captured.get("audio_status"), fallback="unavailable")
            if audio_status is not None and "audio" in effective:
                captured["audio_status"] = audio_status
            try:
                publication = ObservationPublication.from_capture(binding_id, state.record, captured)
            except SurfaceConflictError:
                state.state = "stale"
                state.inhibited = True
                self._invalidate_binding_grants(state, reason="source-or-geometry-changed")
                neutral = self._neutralize_backend(state)
                state.inhibited = not neutral["confirmed"]
                raise
            has_pixels = publication.has_pixels
            has_structure = publication.screen_text is not None or publication.accessibility is not None
            audio_bytes = publication.audio_bytes if audio_grant is not None and "audio" in effective else None
            audio_metadata = publication.audio_metadata if audio_bytes is not None else None
            if audio_bytes is not None and not self._capture_grant_is_current(state, audio_grant):
                audio_bytes = None
                audio_metadata = None
                audio_status = {"status": "not-authorized"}
            if not has_pixels and not has_structure and audio_bytes is None:
                if "audio" in effective and requested == ("audio",):
                    raise SurfaceAuthorizationError("audio.capture grant is not current; audio-only observation was not published")
                raise SurfaceCapabilityError("capture returned no authorized visual, structural, or audio observation")

            full_pixels: bytes | None = None
            digest: str | None = None
            changed_regions: list[dict[str, int]] = []
            coverage = publication.coverage
            if has_pixels:
                full_pixels = self._materialize_pixels(state, publication)
                coverage, full_pixels = self._mask_missing_regions(coverage, full_pixels,
                                                                    publication.width, publication.height,
                                                                    publication.pixel_format)
                digest = hashlib.sha256(full_pixels).hexdigest()
                changed_regions = self._validated_changed_regions(coverage, publication.width, publication.height)
            structure_bytes: bytes | None = None
            if has_structure:
                structure_value: Any = ({"accessibility": publication.accessibility,
                                         **({"screen_text": publication.screen_text} if publication.screen_text is not None else {})}
                                        if publication.accessibility is not None else publication.screen_text)
                structure_bytes = (canonical_json(structure_value) if publication.accessibility is not None
                                   else publication.screen_text.encode("utf-8"))
                if len(structure_bytes) > MAX_ACCESSIBILITY_BYTES:
                    raise SurfaceValidationError("encoded structural publication exceeds its bound")
            metadata = {
                "binding_id": publication.binding_id,
                "source_id": publication.source_id,
                "source_instance": publication.source_instance,
                "source_epoch": publication.source_epoch,
                "environment_incarnation": publication.environment_incarnation,
                "geometry_revision": publication.geometry_revision,
                "sequence": publication.sequence,
                "width": publication.width,
                "height": publication.height,
                "pixel_format": publication.pixel_format,
                "sample_time_ns": publication.sample_time_ns,
                "sample_clock_domain": self._optional_text(captured.get("sample_clock_domain"), "sample_clock_domain", 128),
                "sample_time_uncertainty_ns": self._optional_uint(captured.get("sample_time_uncertainty_ns"), "sample_time_uncertainty_ns"),
                "receipt_time_ns": publication.receipt_time_ns,
                "receipt_clock_domain": self._optional_text(captured.get("receipt_clock_domain"), "receipt_clock_domain", 128),
                "coverage": coverage,
                "screen_text": publication.screen_text if has_structure else None,
                "accessibility": publication.accessibility if has_structure else None,
                "accessibility_sample_time_ns": publication.accessibility_sample_time_ns,
                "provenance": publication.provenance,
                "audio": None,
                "byte_length": len(full_pixels) if full_pixels is not None else 0,
                "sha256": digest,
                "update_kind": ("delta-reconstructed" if publication.delta else "full" if has_pixels
                                else "structural" if has_structure else "audio"),
                "changed_regions": changed_regions,
            }
            if structure_bytes is not None:
                metadata["structure_byte_length"] = len(structure_bytes)
                metadata["structure_sha256"] = hashlib.sha256(structure_bytes).hexdigest()
                metadata["structure_codec"] = "json-utf8" if publication.accessibility is not None else "utf-8"
            if publication.delta:
                baseline = state.publications.get(publication.baseline_generation)
                if baseline is None or publication.sequence != baseline.metadata.get("sequence", 0) + 1:
                    raise SurfaceWaitError({"kind": "publication-baseline", "reason": "delta is not contiguous with its pinned baseline",
                                            "binding_id": binding_id, "generation": publication.baseline_generation})
                metadata["baseline_generation"] = publication.baseline_generation
            if state.publications:
                previous = state.publications[next(reversed(state.publications))]
                old = previous.metadata
                if publication.sequence == old.get("sequence") and publication.source_epoch == previous.source_epoch:
                    old_structure = old.get("structure")
                    old_audio = old.get("audio")
                    audio_admission = old.get("field", {}).get("audio", {}).get("audio", {})
                    same_sample = (
                        old.get("modalities") == sorted(
                            ({"pixels"} if has_pixels else set())
                            | ({"accessibility"} if has_structure else set())
                            | ({"audio"} if audio_bytes is not None else set())
                        )
                        and old.get("sha256") == digest
                        and old.get("coverage") == coverage
                        and (old_structure.get("sha256") if isinstance(old_structure, Mapping) else None)
                            == metadata.get("structure_sha256")
                        and (
                            audio_bytes is None and old_audio is None
                            or audio_bytes is not None
                            and isinstance(old_audio, Mapping)
                            and isinstance(audio_metadata, Mapping)
                            and old_audio.get("sequence") == audio_metadata.get("sequence")
                            and isinstance(audio_admission, Mapping)
                            and audio_admission.get("sha256") == hashlib.sha256(audio_bytes).hexdigest()
                        )
                    )
                    if same_sample:
                        if (state.capture_required_after_generation is not None
                                and previous.generation <= state.capture_required_after_generation):
                            raise SurfaceConflictError("a new source sample is required before control")
                        if audio_bytes is not None and not self._capture_grant_is_current(state, audio_grant):
                            raise SurfaceAuthorizationError("audio.capture grant expired before publication delivery")
                        return json_value(old, max_bytes=MAX_METADATA_BYTES, label="publication metadata")
                    raise SurfaceConflictError("source reused an observation sequence for different content or scope")
            while len(state.publications) >= _MAX_PUBLICATIONS_PER_BINDING:
                old_generation = next(iter(state.publications))
                if not self._release_generation(binding_id, old_generation):
                    raise SurfaceWaitError({"kind": "field-publication", "reason": "field owner cannot release an evicted generation",
                                            "binding_id": binding_id, "generation": old_generation})
                state.publications.pop(old_generation)

            admission: Mapping[str, Any] | None = None
            generation: int | None = None
            if has_pixels or has_structure:
                try:
                    admission = self._check_field_admission(
                        self._field_owner.admit_surface_publication(metadata, full_pixels))
                except Exception as exc:
                    if isinstance(exc, SurfaceError):
                        raise
                    raise SurfaceWaitError({"kind": "field-publication", "reason": "field owner could not admit the live generation",
                                            "binding_id": binding_id, "error": self._exception_reason(exc)}) from exc
                generation = self._positive_int(admission.get("generation"), "field generation")
            structure_admission: Mapping[str, Any] | None = None
            if has_pixels and has_structure:
                structure_publication = {
                    **metadata,
                    "generation": generation,
                    "modality": "structure",
                    "sample_time_ns": (publication.accessibility_sample_time_ns
                                       if publication.accessibility_sample_time_ns is not None
                                       else publication.sample_time_ns),
                    "coverage": captured.get("accessibility_coverage", {
                        "complete": True, "missing_regions": [], "redacted_regions": [],
                        "unknown_regions": [], "skipped_intervals": [],
                    }),
                    "structure": {
                        "codec": metadata["structure_codec"],
                        "byte_length": metadata["structure_byte_length"],
                        "sha256": metadata["structure_sha256"],
                    },
                }
                try:
                    structure_admission = self._check_field_admission(
                        self._field_owner.admit_surface_publication(structure_publication, None))
                    if structure_admission.get("generation") != generation:
                        raise SurfaceConflictError("field owner did not attach structure to the visual generation")
                except Exception as exc:
                    self._release_generation(binding_id, generation)
                    if isinstance(exc, SurfaceError):
                        raise
                    raise SurfaceWaitError({"kind": "field-structure", "reason": "field owner could not admit structural pages",
                                            "binding_id": binding_id, "error": self._exception_reason(exc)}) from exc
            audio_admission: Mapping[str, Any] | None = None
            if audio_bytes is not None and audio_metadata is not None:
                if not self._capture_grant_is_current(state, audio_grant):
                    if admission is None:
                        raise SurfaceAuthorizationError("audio.capture grant expired before audio admission")
                    audio_bytes = None
                    audio_metadata = None
                    audio_status = {"status": "not-authorized"}
                else:
                    audio_publication = self._audio_publication_metadata(publication, metadata, audio_metadata)
                    audio_metadata = dict(audio_metadata)
                    audio_metadata.update({key: audio_publication[key] for key in (
                        "binding_id", "source_id", "source_instance", "source_epoch",
                        "environment_incarnation", "geometry_revision", "coverage",
                    )})
                    try:
                        if generation is None:
                            audio_admission = self._check_field_admission(
                                self._field_owner.admit_surface_audio_publication(audio_publication, audio_bytes))
                            generation = self._positive_int(audio_admission.get("generation"), "field audio generation")
                        else:
                            audio_admission = self._check_field_admission(
                                self._field_owner.admit_surface_audio_publication(
                                    audio_publication, audio_bytes, generation=generation))
                            audio_generation = self._positive_int(audio_admission.get("generation"), "field audio generation")
                            if audio_generation != generation:
                                self._release_generation(binding_id, generation)
                                raise SurfaceConflictError("field owner did not attach audio to the shared publication generation")
                    except Exception as exc:
                        if generation is not None and admission is not None:
                            self._release_generation(binding_id, generation)
                        if isinstance(exc, SurfaceError):
                            raise
                        raise SurfaceWaitError({"kind": "field-audio", "reason": "field owner could not admit audio pages",
                                                "binding_id": binding_id, "error": self._exception_reason(exc)}) from exc
            if generation is None:
                raise SurfaceCapabilityError("capture produced no field-owned publication")
            if audio_admission is not None and not self._capture_grant_is_current(state, audio_grant):
                if not self._release_generation(binding_id, generation):
                    raise SurfaceWaitError({"kind": "field-audio", "reason": "expired audio publication could not be released",
                                            "binding_id": binding_id, "generation": generation})
                raise SurfaceAuthorizationError("audio.capture grant expired before publication became available")
            if (state.capture_required_after_generation is not None
                    and generation <= state.capture_required_after_generation):
                if generation not in state.publications and not self._release_generation(binding_id, generation):
                    raise SurfaceWaitError({"kind": "publication-freshness",
                                            "reason": "reused field generation could not be released",
                                            "binding_id": binding_id, "generation": generation})
                raise SurfaceConflictError("a fresh field-owned observation is required before control")
            field_metadata = {"publication": self._safe_field_admission(admission or audio_admission or {})}
            if audio_admission is not None:
                field_metadata["audio"] = self._safe_field_admission(audio_admission)
            if structure_admission is not None:
                field_metadata["structure"] = self._safe_field_admission(structure_admission)
            published_metadata = publication.metadata(generation, pixel_digest=digest,
                                                        byte_length=len(full_pixels) if full_pixels is not None else 0,
                                                        field_metadata=field_metadata)
            published_metadata.update({key: metadata[key] for key in (
                "sample_clock_domain", "sample_time_uncertainty_ns", "receipt_clock_domain",
                "coverage", "update_kind", "changed_regions",
            )})
            published_metadata["accessibility"] = None
            published_metadata["structure"] = self._structure_descriptor(structure_admission or admission or {}, metadata)
            published_metadata["visual_available"] = has_pixels
            published_metadata["audio_available"] = audio_admission is not None
            published_metadata["audio"] = audio_metadata
            published_metadata["modalities"] = sorted(
                ({"pixels"} if has_pixels else set()) |
                ({"accessibility"} if has_structure else set()) |
                ({"audio"} if audio_admission is not None else set()))
            if audio_status is not None and "audio" in requested:
                published_metadata["audio_status"] = audio_status
            if publication.delta:
                published_metadata["baseline_generation"] = publication.baseline_generation
            state.publications[generation] = _Publication(generation, published_metadata, publication.width,
                                                          publication.height, publication.pixel_format,
                                                          publication.source_epoch, publication.geometry_revision)
            state.last_sequence = max(state.last_sequence, publication.sequence)
            return json_value(published_metadata, max_bytes=MAX_METADATA_BYTES, label="publication metadata")

    def _refresh_source_binding(self, state: _BindingState, *, capture: bool = True) -> SurfaceBinding:
        """Use a read-only provider revalidation; never acquire another session."""
        revalidate = getattr(state.backend, "revalidate", None)
        if not callable(revalidate):
            state.state = "lost"
            self._invalidate_binding_grants(state, reason="backend-lacks-revalidation")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            raise SurfaceCapabilityError("backend does not support read-only source revalidation")
        try:
            result = revalidate(state.backend_binding)
        except Exception as exc:
            raise SurfaceWaitError({"kind": "source-revalidate", "reason": "backend revalidation did not complete",
                                    "binding_id": state.binding_id, "error": self._exception_reason(exc)}) from exc
        if not isinstance(result, Mapping) or result.get("supported") is not True:
            state.state = "lost"
            self._invalidate_binding_grants(state, reason="backend-revalidation-unsupported")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            raise SurfaceCapabilityError("backend revalidation is unsupported")
        if result.get("valid") is not True:
            state.state = "lost"
            self._invalidate_binding_grants(state, reason="source-revalidation-failed")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            raise SurfaceWaitError({"kind": "source-revalidate", "reason": "bound source is no longer valid",
                                    "binding_id": state.binding_id})
        try:
            current = SurfaceBinding.from_mapping(result, backend_id=state.record.backend_id,
                                                  source_id=state.record.source_id)
        except SurfaceError:
            raise
        old = state.record
        if (current.source_instance != old.source_instance
                or current.environment_incarnation != old.environment_incarnation
                or current.source_epoch != old.source_epoch
                or current.geometry_revision != old.geometry_revision):
            state.state = "stale"
            self._invalidate_binding_grants(state, reason="source-epoch-or-geometry-changed")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            raise SurfaceConflictError("source, environment, epoch, or geometry changed; bind the source again")
        authority_changed = (current.focus_epoch != old.focus_epoch
                            or current.input_domain_epoch != old.input_domain_epoch
                            or current.input_domain != old.input_domain
                            or current.input_state != old.input_state)
        state.backend_binding = dict(result)
        state.record = current
        if authority_changed:
            self._require_fresh_capture(state)
            self._invalidate_binding_grants(state, reason="focus-or-input-domain-epoch-changed")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            state.human_control = current.input_state == "suspended"
            state.state = ("human-control" if state.human_control else
                           "observation-only" if neutral["confirmed"] else "neutralization-pending")
            if not capture:
                raise SurfaceConflictError("focus or input-domain epoch changed at final dispatch fence")
        return current


    def _available_modalities(self, state: _BindingState) -> tuple[str, ...]:
        raw = state.backend_binding.get("modalities", state.backend_binding.get("capture_modalities"))
        if raw is None:
            # A bound nonzero raster is the one safe legacy inference. Audio
            # and structural support must be advertised explicitly.
            values = ("pixels",) if state.record.width and state.record.height else ()
        else:
            values = self._normalize_modalities(raw)
        available = set(values)
        if not state.record.width or not state.record.height:
            available.discard("pixels")
        if "audio" in available and "audio.capture" not in state.record.operations:
            available.discard("audio")
        return tuple(sorted(available))

    def _normalize_modalities(self, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple, set, frozenset)) or len(value) > 3:
            raise SurfaceValidationError("channels must be a bounded collection of modalities")
        allowed = {"pixels", "accessibility", "audio"}
        channels: set[str] = set()
        for item in value:
            if not isinstance(item, str) or item not in allowed:
                raise SurfaceValidationError("channels must use pixels, accessibility, or audio")
            channels.add(item)
        return tuple(sorted(channels))

    def _safe_audio_status(self, value: Any, *, fallback: str) -> dict[str, str]:
        raw = value.get("status") if isinstance(value, Mapping) else value
        allowed = {"unavailable", "not-authorized", "unsupported", "waiting", "muted",
                   "no-stream", "permission-denied", "captured"}
        status = raw if isinstance(raw, str) and raw in allowed else fallback
        return {"status": status}

    def _audio_capture_grant(self, state: _BindingState, mission_id: str, grant_id: str) -> _Grant:
        mission_id = self._required_text(mission_id, "mission_id", 192)
        grant_id = self._required_text(grant_id, "grant_id", MAX_IDENTIFIER)
        if "audio.capture" not in state.record.operations:
            raise SurfaceCapabilityError("source does not advertise audio.capture")
        with self._lock:
            grant = self._grants.get(grant_id)
            now = time.monotonic_ns()
            if (grant is None or not grant.active or grant.controller != "cassi"
                    or grant.mission_id != mission_id or grant.binding_id != state.binding_id
                    or "audio.capture" not in grant.operations
                    or now >= min(grant.expires_ns, grant.absolute_deadline_ns, grant.lease_deadline_ns)):
                raise SurfaceAuthorizationError("active audio.capture grant is required for this mission and binding")
            if (grant.scope.get("source_id") != state.record.source_id
                    or grant.scope.get("source_instance") != state.record.source_instance
                    or grant.scope.get("source_epoch") != state.record.source_epoch
                    or grant.scope.get("geometry_revision") != state.record.geometry_revision
                    or grant.scope.get("environment_incarnation") != state.record.environment_incarnation
                    or grant.scope.get("backend_input_domain") != state.record.input_domain
                    or grant.scope.get("backend_input_domain_epoch") != state.record.input_domain_epoch
                    or grant.focus_epoch != state.record.focus_epoch):
                raise SurfaceAuthorizationError("audio.capture grant source generation does not match")
            if grant.input_domain is not None:
                if self._domain_leases.get(grant.input_domain) != grant.grant_id:
                    raise SurfaceAuthorizationError("audio.capture input-domain lease is no longer current")
                if self._domain_epochs.get(grant.input_domain) != grant.input_domain_epoch:
                    raise SurfaceConflictError("audio.capture input-domain lease epoch changed")
            return grant

    def _capture_grant_is_current(self, state: _BindingState, grant: _Grant | None) -> bool:
        if grant is None:
            return False
        with self._lock:
            now = time.monotonic_ns()
            return (not self._closed and not state.detached and not state.human_control and not state.inhibited
                    and state.state not in {"stale", "lost", "paused", "reconciliation-required",
                                            "neutralization-pending", "input-suspended"}
                    and self._grants.get(grant.grant_id) is grant and grant.active
                    and grant.controller == "cassi" and "audio.capture" in grant.operations
                    and grant.binding_id == state.binding_id and now < min(
                        grant.expires_ns, grant.absolute_deadline_ns, grant.lease_deadline_ns)
                    and grant.scope.get("source_id") == state.record.source_id
                    and grant.scope.get("source_instance") == state.record.source_instance
                    and grant.scope.get("source_epoch") == state.record.source_epoch
                    and grant.scope.get("geometry_revision") == state.record.geometry_revision
                    and grant.scope.get("environment_incarnation") == state.record.environment_incarnation
                    and grant.scope.get("backend_input_domain") == state.record.input_domain
                    and grant.scope.get("backend_input_domain_epoch") == state.record.input_domain_epoch
                    and grant.focus_epoch == state.record.focus_epoch
                    and (grant.input_domain is None or (
                        self._domain_leases.get(grant.input_domain) == grant.grant_id
                        and self._domain_epochs.get(grant.input_domain) == grant.input_domain_epoch)))

    def _capture_authorization_context(self, state: _BindingState, grant: _Grant) -> dict[str, Any]:
        return {
            "mission_id": grant.mission_id,
            "grant_id": grant.grant_id,
            "binding_id": state.binding_id,
            "source_id": state.record.source_id,
            "source_instance": state.record.source_instance,
            "source_epoch": state.record.source_epoch,
            "environment_incarnation": state.record.environment_incarnation,
            "geometry_revision": state.record.geometry_revision,
            "operations": ["audio.capture"],
            "expires_ns": grant.expires_ns,
            "scope": dict(grant.scope),
            "validate": lambda: self._capture_grant_is_current(state, grant),
        }

    def _audio_publication_metadata(self, publication: ObservationPublication, metadata: Mapping[str, Any],
                                    audio: Mapping[str, Any]) -> dict[str, Any]:
        audio_coverage = audio.get("coverage")
        if not isinstance(audio_coverage, Mapping):
            raise SurfaceValidationError("audio coverage must be an object")
        return {
            "binding_id": publication.binding_id,
            "source_id": publication.source_id,
            "source_instance": publication.source_instance,
            "source_epoch": publication.source_epoch,
            "environment_incarnation": publication.environment_incarnation,
            "geometry_revision": publication.geometry_revision,
            "sequence": audio.get("sequence", publication.sequence),
            "sample_time_ns": audio.get("sample_time_ns"),
            "sample_clock_domain": audio.get("sample_clock_domain"),
            "sample_time_uncertainty_ns": audio.get("sample_time_uncertainty_ns"),
            "receipt_time_ns": audio.get("receipt_time_ns", publication.receipt_time_ns),
            "receipt_clock_domain": audio.get("receipt_clock_domain", metadata.get("receipt_clock_domain")),
            "coverage": json_value(audio_coverage, max_bytes=MAX_METADATA_BYTES, label="audio coverage"),
            "provenance": audio.get("provenance", publication.provenance),
            "audio_format": audio["audio_format"],
            "sample_rate_hz": audio["sample_rate_hz"],
            "channel_count": audio["channel_count"],
            "sample_count": audio["sample_count"],
            "byte_length": audio.get("byte_length"),
            "data_plane": "surface.read_audio_page",
            "frame_count": audio["sample_count"],
        }

    def _check_field_admission(self, admission: Any) -> Mapping[str, Any]:
        if not isinstance(admission, Mapping):
            raise SurfaceValidationError("field admission result must be an object")
        if admission.get("status") in {"wait", "resource-wait", "deferred"} or admission.get("accepted") is False:
            wait = admission.get("wait", admission)
            raise SurfaceWaitError(wait if isinstance(wait, Mapping) else {"kind": "field-publication", "reason": "field owner deferred publication"})
        return admission

    def _safe_field_admission(self, admission: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"status", "accepted", "generation", "byte_length", "sha256", "structure", "audio", "page_count"}
        result = {key: admission[key] for key in allowed if key in admission}
        return json_value(result, max_bytes=MAX_DETAIL_BYTES, label="safe field admission")

    def _structure_descriptor(self, admission: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any] | None:
        structure = admission.get("structure")
        if isinstance(structure, Mapping):
            return json_value(structure, max_bytes=MAX_DETAIL_BYTES, label="structure descriptor")
        if "structure_byte_length" not in metadata:
            return None
        return {"codec": metadata["structure_codec"], "byte_length": metadata["structure_byte_length"],
                "sha256": metadata["structure_sha256"]}

    def list_bindings(self) -> list[dict[str, Any]]:
        """Inspect attached bindings for mission-scoped viewer reconnection."""
        with self._lock:
            self._assert_open()
            binding_ids = tuple(self._bindings)
        result = []
        for binding_id in binding_ids:
            try:
                view = self.inspect_binding(binding_id)
            except SurfaceConflictError:
                continue
            if not view["detached"]:
                result.append(view)
        return result

    def inspect_binding(self, binding_id: str) -> dict[str, Any]:
        """Return current source and latest publication metadata, never page bytes."""
        state = self._binding_state(binding_id)
        with state.lock:
            latest = next(reversed(state.publications.values()), None) if state.publications else None
            return {
                **state.record.to_dict(binding_id),
                "state": state.state,
                "inhibited": state.inhibited,
                "human_control": state.human_control,
                "detached": state.detached,
                "pinned_generations": list(state.publications),
                "current_publication": None if latest is None else json_value(latest.metadata, max_bytes=MAX_METADATA_BYTES,
                                                                                label="publication metadata"),
            }

    def inspect_publication(self, binding_id: str, generation: int, source_epoch: int | None = None,
                            geometry_revision: int | None = None) -> dict[str, Any]:
        """Validate an annotation's exact displayed generation and return metadata only."""
        state = self._binding_state(binding_id)
        generation = self._positive_int(generation, "generation")
        with state.lock:
            publication = state.publications.get(generation)
            if publication is None:
                raise SurfaceConflictError("publication generation is not retained")
            if source_epoch is not None:
                source_epoch = self._bounded_int(source_epoch, "source_epoch", (1 << 63) - 1, minimum=1)
                if source_epoch != publication.source_epoch:
                    raise SurfaceConflictError("publication source epoch does not match the displayed source")
            if geometry_revision is not None:
                geometry_revision = self._bounded_int(geometry_revision, "geometry_revision", (1 << 63) - 1)
                if geometry_revision != publication.geometry_revision:
                    raise SurfaceConflictError("publication geometry does not match the displayed source")
            result = json_value(publication.metadata, max_bytes=MAX_METADATA_BYTES, label="publication metadata")
            result["is_latest"] = generation == next(reversed(state.publications))
            return result

    def _materialize_pixels(self, state: _BindingState, publication: ObservationPublication) -> bytes:
        expected = publication.expected_full_length
        if not publication.delta:
            if publication.baseline_generation is not None or publication.byte_ranges:
                raise SurfaceValidationError("full capture cannot carry delta references")
            if len(publication.pixel_bytes) != expected:
                raise SurfaceValidationError("pixel bytes do not match the declared dimensions and format")
            return publication.pixel_bytes
        if publication.baseline_generation not in state.publications:
            raise SurfaceWaitError({"kind": "publication-baseline", "reason": "delta baseline is not pinned",
                                    "binding_id": state.binding_id, "generation": publication.baseline_generation})
        baseline = state.publications[publication.baseline_generation]
        if (baseline.source_epoch != publication.source_epoch or baseline.geometry_revision != publication.geometry_revision
                or baseline.width != publication.width or baseline.height != publication.height
                or baseline.pixel_format != publication.pixel_format):
            raise SurfaceConflictError("delta baseline source epoch or geometry does not match")
        if self._field_owner is None:
            raise SurfaceCapabilityError("field owner is unavailable for delta reconstruction")
        output = bytearray(expected)
        offset = 0
        while offset < expected:
            length = min(_PAGE_COPY_BYTES, expected - offset)
            page = self._field_owner.read_surface_page(state.binding_id, publication.baseline_generation, offset, length)
            if not isinstance(page, bytes) or len(page) != length:
                raise SurfaceWaitError({"kind": "publication-baseline", "reason": "pinned baseline page is unavailable",
                                        "binding_id": state.binding_id, "generation": publication.baseline_generation,
                                        "offset": offset, "length": length})
            output[offset:offset + length] = page
            offset += length
        dest_end = 0
        source_ranges: list[tuple[int, int]] = []
        copied = 0
        for item in publication.byte_ranges:
            start, length, source_offset = item["offset"], item["length"], item["source_offset"]
            end = start + length
            source_end = source_offset + length
            if start < dest_end or end > expected or source_end > len(publication.pixel_bytes):
                raise SurfaceValidationError("delta ranges overlap or escape their declared buffers")
            if any(source_offset < end0 and source_end > start0 for start0, end0 in source_ranges):
                raise SurfaceValidationError("delta source ranges overlap")
            output[start:end] = publication.pixel_bytes[source_offset:source_end]
            dest_end = end
            source_ranges.append((source_offset, source_end))
            copied += length
        if copied != len(publication.pixel_bytes):
            raise SurfaceValidationError("delta byte ranges do not account for every captured byte")
        return bytes(output)

    def _mask_missing_regions(self, coverage_value: Mapping[str, Any], pixels: bytes, width: int, height: int,
                              pixel_format: str) -> tuple[dict[str, Any], bytes]:
        coverage = json_value(coverage_value, max_bytes=MAX_METADATA_BYTES, label="coverage")
        if not isinstance(coverage, dict):
            raise SurfaceValidationError("coverage must be an object")
        complete = coverage.get("complete", False)
        if not isinstance(complete, bool):
            raise SurfaceValidationError("coverage.complete must be boolean")
        coverage["complete"] = complete
        for key in ("missing_regions", "redacted_regions", "unknown_regions"):
            regions = coverage.get(key, [])
            if not isinstance(regions, list) or len(regions) > 4096:
                raise SurfaceValidationError(f"coverage.{key} must be a bounded region list")
            validated: list[dict[str, int]] = []
            for region in regions:
                if not isinstance(region, Mapping) or set(region) != {"x", "y", "width", "height"}:
                    raise SurfaceValidationError(f"coverage.{key} contains an invalid rectangle")
                x = self._bounded_int(region["x"], "region.x", width - 1)
                y = self._bounded_int(region["y"], "region.y", height - 1)
                rw = self._bounded_int(region["width"], "region.width", width, minimum=1)
                rh = self._bounded_int(region["height"], "region.height", height, minimum=1)
                if x + rw > width or y + rh > height:
                    raise SurfaceValidationError(f"coverage.{key} escapes the frame")
                validated.append({"x": x, "y": y, "width": rw, "height": rh})
            coverage[key] = validated
        coverage.setdefault("skipped_intervals", [])
        coverage["skipped_intervals"] = json_value(coverage["skipped_intervals"], max_bytes=MAX_METADATA_BYTES,
                                                    label="coverage.skipped_intervals")
        missing = list(coverage["missing_regions"]) + list(coverage["unknown_regions"])
        # A producer that cannot localize an incomplete current image cannot
        # present its bytes as known application content.
        if not complete and not missing:
            missing = [{"x": 0, "y": 0, "width": width, "height": height}]
            coverage["unknown_extent"] = True
        masked = list(coverage["redacted_regions"]) + missing
        if not masked:
            return coverage, pixels
        channels = PIXEL_CHANNELS[pixel_format]
        stride = width * channels
        output = bytearray(pixels)
        for region in masked:
            blank = bytes(region["width"] * channels)
            for y in range(region["y"], region["y"] + region["height"]):
                start = y * stride + region["x"] * channels
                output[start:start + len(blank)] = blank
        coverage["missing_regions"] = missing
        coverage.setdefault("redacted_regions", [])
        coverage.setdefault("unknown_regions", [])
        return coverage, bytes(output)

    def _validated_changed_regions(self, coverage: Mapping[str, Any], width: int, height: int) -> list[dict[str, int]]:
        regions = coverage.get("changed_regions", [])
        if not isinstance(regions, list) or len(regions) > 4096:
            raise SurfaceValidationError("coverage.changed_regions must be a bounded list")
        result: list[dict[str, int]] = []
        for item in regions:
            if not isinstance(item, Mapping) or set(item) != {"x", "y", "width", "height"}:
                raise SurfaceValidationError("changed region has an invalid shape")
            x = self._bounded_int(item["x"], "changed.x", width - 1)
            y = self._bounded_int(item["y"], "changed.y", height - 1)
            w = self._bounded_int(item["width"], "changed.width", width, minimum=1)
            h = self._bounded_int(item["height"], "changed.height", height, minimum=1)
            if x + w > width or y + h > height:
                raise SurfaceValidationError("changed region escapes frame")
            result.append({"x": x, "y": y, "width": w, "height": h})
        return result


    def read_page(self, binding_id: str, generation: int, offset: int, length: int) -> bytes:
        """Read raw pixels from the authenticated binary plane, never control JSON."""
        state = self._binding_state(binding_id)
        generation = self._positive_int(generation, "generation")
        offset = self._bounded_int(offset, "offset", MAX_FRAME_BYTES)
        length = self._bounded_int(length, "length", _MAX_PAGE_READ_BYTES, minimum=1)
        with state.lock:
            self._ensure_attached(state)
            publication = state.publications.get(generation)
            if publication is None:
                raise SurfaceConflictError("publication generation is no longer pinned")
            if self._field_owner is None:
                raise SurfaceCapabilityError("field owner is unavailable")
            if not publication.metadata.get("visual_available") or publication.pixel_format not in PIXEL_CHANNELS:
                raise SurfaceCapabilityError("publication has no pixel page")
            total = publication.width * publication.height * PIXEL_CHANNELS[publication.pixel_format]
            if offset + length > total:
                raise SurfaceValidationError("page range escapes the publication")
            page = self._field_owner.read_surface_page(binding_id, generation, offset, length)
            if not isinstance(page, bytes) or len(page) != length:
                raise SurfaceWaitError({"kind": "surface-page", "reason": "requested live page is unavailable",
                                        "binding_id": binding_id, "generation": generation})
            return page

    def read_audio_page(self, binding_id: str, generation: int, offset: int, length: int, *,
                        mission_id: str | None = None, grant_id: str | None = None) -> bytes:
        """Read a bounded audio page only under a current, explicit capture grant."""
        if mission_id is None or grant_id is None:
            raise SurfaceAuthorizationError("audio page reads require mission_id and an active audio.capture grant")
        state = self._binding_state(binding_id)
        generation = self._positive_int(generation, "generation")
        offset = self._bounded_int(offset, "offset", MAX_AUDIO_BYTES)
        length = self._bounded_int(length, "length", _MAX_PAGE_READ_BYTES, minimum=1)
        with state.lock:
            self._ensure_attached(state)
            grant = self._audio_capture_grant(state, mission_id, grant_id)
            if not self._capture_grant_is_current(state, grant):
                raise SurfaceAuthorizationError("audio page read grant is no longer current")
            publication = state.publications.get(generation)
            if publication is None:
                raise SurfaceConflictError("publication generation is no longer pinned")
            audio = publication.metadata.get("audio")
            if not publication.metadata.get("audio_available") or not isinstance(audio, Mapping):
                raise SurfaceCapabilityError("publication has no captured audio page")
            if (audio.get("binding_id") != binding_id or audio.get("source_epoch") != publication.source_epoch
                    or audio.get("geometry_revision") != publication.geometry_revision):
                raise SurfaceConflictError("audio page descriptor does not match its pinned source generation")
            total = self._bounded_int(audio.get("byte_length"), "audio byte_length", MAX_AUDIO_BYTES, minimum=1)
            if offset + length > total:
                raise SurfaceValidationError("audio page range escapes the publication")
            reader = getattr(self._field_owner, "read_surface_audio_page", None)
            if not callable(reader):
                raise SurfaceCapabilityError("field owner does not provide audio page reads")
            page = reader(binding_id, generation, offset, length)
            if not isinstance(page, bytes) or len(page) != length:
                raise SurfaceWaitError({"kind": "surface-audio-page", "reason": "requested live audio page is unavailable",
                                        "binding_id": binding_id, "generation": generation})
            if not self._capture_grant_is_current(state, grant):
                raise SurfaceAuthorizationError("audio page read grant expired before delivery")
            return page


    def read_text_page(self, binding_id: str, generation: int, offset: int, length: int) -> bytes:
        """Read bounded UTF-8 structural content from a field-owned generation."""
        state = self._binding_state(binding_id)
        generation = self._positive_int(generation, "generation")
        offset = self._bounded_int(offset, "offset", MAX_ACCESSIBILITY_BYTES)
        length = self._bounded_int(length, "length", _MAX_PAGE_READ_BYTES, minimum=1)
        with state.lock:
            self._ensure_attached(state)
            publication = state.publications.get(generation)
            if publication is None:
                raise SurfaceConflictError("publication generation is no longer pinned")
            structure = publication.metadata.get("structure")
            if not isinstance(structure, Mapping):
                raise SurfaceCapabilityError("publication has no structural page")
            total = self._bounded_int(structure.get("byte_length"), "structure byte_length", MAX_ACCESSIBILITY_BYTES)
            if offset + length > total:
                raise SurfaceValidationError("structural page range escapes the publication")
            reader = getattr(self._field_owner, "read_surface_text_page", None)
            if not callable(reader):
                raise SurfaceCapabilityError("field owner does not provide structural page reads")
            page = reader(binding_id, generation, offset, length)
            if not isinstance(page, bytes) or len(page) != length:
                raise SurfaceWaitError({"kind": "surface-text-page", "reason": "requested live structural page is unavailable",
                                        "binding_id": binding_id, "generation": generation})
            return page

    def observation_readout(self, binding_id: str, generation: int, *, modalities: Any | None = None,
                            mission_id: str | None = None, grant_id: str | None = None,
                            page_size: int = 128, cursors: Mapping[str, int] | None = None) -> dict[str, Any]:
        """Return an explicitly scoped field-owned readout for one retained generation."""
        if (mission_id is None) != (grant_id is None):
            raise SurfaceValidationError("mission_id and grant_id must be supplied together")
        state = self._binding_state(binding_id)
        generation = self._positive_int(generation, "generation")
        page_size = self._bounded_int(page_size, "page_size", 256, minimum=1)
        with state.lock:
            self._ensure_attached(state)
            publication = state.publications.get(generation)
            if publication is None:
                raise SurfaceConflictError("publication generation is no longer pinned")
            published_modalities = set(publication.metadata.get("modalities", ()))
            requested = (self._normalize_modalities(modalities) if modalities is not None else
                         tuple(sorted(published_modalities - {"audio"})))
            if not requested:
                raise SurfaceAuthorizationError("observation readout requires an explicit modality scope")
            if not set(requested).issubset(published_modalities):
                raise SurfaceCapabilityError("requested readout modality is absent from the publication")
            audio_grant: _Grant | None = None
            if "audio" in requested:
                if mission_id is None or grant_id is None:
                    raise SurfaceAuthorizationError("audio readout requires an active audio.capture grant")
                audio_grant = self._audio_capture_grant(state, mission_id, grant_id)
                if not self._capture_grant_is_current(state, audio_grant):
                    raise SurfaceAuthorizationError("audio readout grant is no longer current")
            reader = getattr(self._field_owner, "surface_observation_readout", None)
            if not callable(reader):
                raise SurfaceCapabilityError("field owner does not provide surface observation readouts")
            result = reader(binding_id, generation, modalities=requested,
                            page_size=page_size, cursors=cursors)
            result = json_value(result, max_bytes=MAX_METADATA_BYTES, label="surface observation readout")
            if not isinstance(result, dict) or result.get("schema") != "cassifi.surface-observation-readout.v1":
                raise SurfaceValidationError("field observation readout has an invalid schema")
            for key, expected in {
                "binding_id": binding_id,
                "source_id": state.record.source_id,
                "source_instance": state.record.source_instance,
                "source_epoch": publication.source_epoch,
                "environment_incarnation": state.record.environment_incarnation,
                "geometry_revision": publication.geometry_revision,
                "sequence": publication.metadata.get("sequence"),
                "generation": generation,
            }.items():
                if result.get(key) != expected:
                    raise SurfaceConflictError(f"field observation readout {key} does not match the pinned generation")
            if result.get("modalities") != list(requested):
                raise SurfaceConflictError("field observation readout does not match the requested modality scope")
            if not isinstance(result.get("stale"), bool):
                raise SurfaceValidationError("field observation readout must declare staleness")
            if audio_grant is not None and not self._capture_grant_is_current(state, audio_grant):
                raise SurfaceAuthorizationError("audio readout grant expired before delivery")
            return result

    # ---- host-issued authority and bounded control streams -------------

    def grant(self, mission_id: str, binding_id: str, operations: Any, expires_ns: int,
              scope: Mapping[str, Any]) -> dict[str, Any]:
        mission_id = self._required_text(mission_id, "mission_id", 192)
        requested = normalize_operations(operations)
        if not requested:
            raise SurfaceValidationError("grant must name at least one operation")
        expires_ns = self._positive_int(expires_ns, "expires_ns")
        now = time.monotonic_ns()
        if expires_ns <= now or expires_ns - now > _MAX_GRANT_TTL_NS:
            raise SurfaceValidationError("grant expiry must be in the future and within the one-hour limit")
        safe_scope = json_value(scope, max_bytes=MAX_METADATA_BYTES, label="grant scope")
        state = self._binding_state(binding_id)
        with state.lock:
            self._ensure_attached(state)
            self._refresh_source_binding(state, capture=False)
            if state.inhibited or state.state in {"paused", "reconciliation-required", "neutralization-pending",
                                                   "input-suspended", "stale", "lost"}:
                raise SurfaceWaitError({"kind": "control-state", "reason": f"binding is {state.state}",
                                        "binding_id": binding_id})
            self._require_supported_operations(state, requested)
            domain = self._input_domain(state.record)
            if "audio.playback" in requested:
                endpoint = (state.backend_binding.get("audio_session_endpoint_id")
                            or state.backend_binding.get("audio_endpoint_id"))
                endpoint = self._required_text(endpoint, "audio session endpoint id", 256)
                safe_scope["audio_recipient_scope"] = endpoint
            if "audio.capture" in requested and state.record.input_state not in {"available", "live", "supported"}:
                raise SurfaceCapabilityError(f"audio capture input is {state.record.input_state}")
            requires_input_lease = any(self._requires_input_lease(op) for op in requested)
            if requires_input_lease and state.record.input_state not in {"available", "live", "supported"}:
                raise SurfaceCapabilityError(f"input is {state.record.input_state}")
            duration = self._bounded_int(safe_scope.get("max_duration_ns", min(expires_ns - now, _MAX_CONTROL_DURATION_NS)),
                                         "max_duration_ns", _MAX_CONTROL_DURATION_NS, minimum=1)
            heartbeat = self._bounded_int(safe_scope.get("heartbeat_timeout_ns", _DEFAULT_HEARTBEAT_NS),
                                          "heartbeat_timeout_ns", _MAX_HEARTBEAT_NS, minimum=100_000_000)
            max_updates = self._bounded_int(safe_scope.get("max_updates", 1), "max_updates", _MAX_GRANT_UPDATES, minimum=1)
            max_payload = self._bounded_int(safe_scope.get("max_payload_bytes", MAX_INTENT_BYTES),
                                            "max_payload_bytes", MAX_INTENT_BYTES, minimum=1)
            duration = min(duration, expires_ns - now)
            safe_scope.update({"max_duration_ns": duration, "heartbeat_timeout_ns": heartbeat,
                               "max_updates": max_updates, "max_payload_bytes": max_payload,
                               "controller": "cassi", "input_domain": domain if requires_input_lease else None,
                               "backend_input_domain": state.record.input_domain,
                               "backend_input_domain_epoch": state.record.input_domain_epoch,
                               "environment_incarnation": state.record.environment_incarnation,
                               "source_id": state.record.source_id, "source_instance": state.record.source_instance,
                               "source_epoch": state.record.source_epoch,
                               "geometry_revision": state.record.geometry_revision})
            grant_id = token_urlsafe(32)
            proposal = {
                "purpose": "surface-grant", "grant_id": grant_id,
                "mission_id": mission_id, "binding_id": binding_id,
                "backend_id": state.record.backend_id, "source_id": state.record.source_id,
                "source_instance": state.record.source_instance, "source_epoch": state.record.source_epoch,
                "environment_incarnation": state.record.environment_incarnation,
                "geometry_revision": state.record.geometry_revision,
                "operations": list(requested), "expires_ns": expires_ns, "scope": safe_scope,
            }
        # Host prompts/providers are outside both the broker-global and
        # per-binding locks, so revoke and watchdog traffic stays responsive.
        decision = self._ask_authorizer(proposal)
        approved_operations, approved_scope = self._approved_decision(decision, requested, safe_scope)
        issued = time.monotonic_ns()
        if expires_ns <= issued:
            raise SurfaceAuthorizationError("grant expired before host approval completed")
        current_epoch: int | None = None
        reserved_domain = False
        with state.lock:
            self._ensure_attached(state)
            self._refresh_source_binding(state, capture=False)
            if self._input_domain(state.record) != domain:
                raise SurfaceConflictError("input domain changed during grant approval")
            self._require_supported_operations(state, tuple(approved_operations))
            if requires_input_lease and state.record.input_state not in {"available", "live", "supported"}:
                raise SurfaceCapabilityError(f"input is {state.record.input_state}")
            if "audio.playback" in approved_operations:
                current_endpoint = (state.backend_binding.get("audio_session_endpoint_id")
                                   or state.backend_binding.get("audio_endpoint_id"))
                if current_endpoint != approved_scope.get("audio_recipient_scope"):
                    raise SurfaceConflictError("audio playback endpoint changed during grant approval")
            with self._lock:
                self._assert_open()
                if state.human_control:
                    raise SurfaceAuthorizationError("human control currently owns this binding")
                if requires_input_lease and domain in self._domain_leases:
                    raise SurfaceWaitError({"kind": "input-lease", "reason": "input domain already has a controlling lease",
                                            "input_domain": domain})
                if requires_input_lease:
                    current_epoch = self._domain_epochs.get(domain, state.record.input_domain_epoch or 0) + 1
                    self._domain_epochs[domain] = current_epoch
                    self._domain_leases[domain] = grant_id
                    reserved_domain = True
            if approved_scope.get("max_payload_bytes", max_payload) > max_payload:
                self._drop_provisional_domain(domain, grant_id, reserved_domain)
                raise SurfaceAuthorizationError("host decision attempted to expand payload allowance")
            heartbeat = approved_scope["heartbeat_timeout_ns"]
            duration = min(approved_scope["max_duration_ns"], expires_ns - issued)
            grant = _Grant(
                grant_id, mission_id, binding_id, frozenset(approved_operations), approved_scope, expires_ns,
                issued, issued + duration, heartbeat, min(expires_ns, issued + duration, issued + heartbeat),
                approved_scope["max_updates"], 1, 0, domain if requires_input_lease else None,
                current_epoch, state.record.focus_epoch, "cassi", True,
            )
            try:
                self._append_event({"type": "grant_issued", "grant_digest": self._grant_digest(grant),
                                    "mission_id": mission_id, "binding_id": binding_id,
                                    "expires_ns": expires_ns, "operations": list(approved_operations),
                                    "scope_digest": hashlib.sha256(canonical_json(approved_scope)).hexdigest()})
            except Exception:
                self._drop_provisional_domain(domain, grant_id, reserved_domain)
                raise
            with self._watch:
                self._grants[grant_id] = grant
                self._watch.notify_all()
            return {"grant_id": grant_id, "mission_id": mission_id, "binding_id": binding_id,
                    "operations": list(approved_operations), "expires_ns": expires_ns,
                    "max_duration_ns": duration, "heartbeat_timeout_ns": heartbeat,
                    "max_updates": grant.max_updates, "input_domain": self._input_domain(state.record),
                    "input_domain_epoch": state.record.input_domain_epoch,
                    "input_lease_epoch": grant.input_domain_epoch, "focus_epoch": state.record.focus_epoch,
                    "state": "granted"}

    def _drop_provisional_domain(self, domain: str, grant_id: str, reserved: bool) -> None:
        if not reserved:
            return
        with self._lock:
            if self._domain_leases.get(domain) == grant_id:
                self._domain_leases.pop(domain, None)
                self._domain_epochs[domain] = self._domain_epochs.get(domain, 0) + 1
    def heartbeat(self, binding_id: str, grant_id: str, sequence: int) -> dict[str, Any]:
        """Renew an already granted stream only within its fixed authority envelope."""
        sequence = self._positive_int(sequence, "heartbeat sequence")
        now = time.monotonic_ns()
        with self._watch:
            grant = self._grants.get(grant_id)
            if grant is None or not grant.active or grant.binding_id != binding_id or grant.input_domain is None:
                raise SurfaceAuthorizationError("no active control stream for this binding")
            if now >= grant.lease_deadline_ns or now >= grant.absolute_deadline_ns or now >= grant.expires_ns:
                raise SurfaceAuthorizationError("control stream has expired")
            if sequence != grant.heartbeat_sequence + 1:
                raise SurfaceConflictError("duplicate or reordered heartbeat")
            grant.heartbeat_sequence = sequence
            grant.lease_deadline_ns = min(grant.expires_ns, grant.absolute_deadline_ns, now + grant.heartbeat_timeout_ns)
            self._watch.notify_all()
            return {"binding_id": binding_id, "grant_id": grant_id, "sequence": sequence,
                    "lease_deadline_ns": grant.lease_deadline_ns, "state": "active"}

    def submit_intent(self, intent: Mapping[str, Any]) -> dict[str, Any]:
        parsed = ControlIntent.from_mapping(intent)
        if parsed.operation == "audio.capture":
            raise SurfaceCapabilityError("audio.capture is requested through scoped capture channels, not dispatch intents")
        request_digest = hashlib.sha256(canonical_json(parsed.canonical())).hexdigest()
        with self._lock:
            self._assert_open()
            existing = self._operations.get(parsed.operation_id)
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise SurfaceConflictError("operation_id already names a different canonical request or scope")
                return self._operation_view(existing)
            state = self._bindings.get(parsed.binding_id)
            grant = self._grants.get(parsed.grant_id)
            if state is None or state.detached:
                raise SurfaceCapabilityError("binding is unavailable")
            if grant is None or not grant.active:
                raise SurfaceAuthorizationError("grant is absent, expired, or revoked")
            self._validate_intent_authority(parsed, state, grant)
            stream_sequence = grant.next_sequence
            if parsed.sequence is not None and parsed.sequence != stream_sequence:
                raise SurfaceConflictError("control update sequence is duplicate, reordered, or skipped")
            if grant.next_sequence > grant.max_updates:
                raise SurfaceAuthorizationError("bounded control stream has exhausted its update allowance")
            # Reserve the operation ID/digest durably before acquiring the final
            # per-source fence or calling any external provider.
            record = {
                "operation_id": parsed.operation_id,
                "request_digest": request_digest,
                "phase": "reserved",
                "mission_id": parsed.mission_id,
                "binding_id": parsed.binding_id,
                "grant_digest": self._grant_digest(grant),
                "operation": parsed.operation,
                "sequence": stream_sequence,
                "disposition": None,
                "delivered_count": 0,
                "ack_strength": None,
                "detail": None,
                "reconciliation": None,
            }
            self._reserve_ledger_capacity(parsed.operation_id)
            try:
                self._append_event({"type": "operation_reserved", **record}, operation_id=parsed.operation_id)
            except Exception:
                self._release_ledger_capacity(parsed.operation_id)
                raise
            self._operations[parsed.operation_id] = record
            grant.next_sequence += 1
            grant.lease_deadline_ns = min(grant.expires_ns, grant.absolute_deadline_ns,
                                          time.monotonic_ns() + grant.heartbeat_timeout_ns)
            self._watch.notify_all()
        # No broker-global lock spans the final checks or backend delivery.
        with state.lock:
            try:
                self._ensure_dispatch_fence(state, parsed, grant)
            except SurfaceError as exc:
                outcome = self._not_started(str(exc))
                self._settle_operation(parsed.operation_id, outcome)
                return self.inspect(parsed.operation_id)
            except Exception as exc:
                outcome = self._not_started(self._exception_reason(exc))
                self._settle_operation(parsed.operation_id, outcome)
                return self.inspect(parsed.operation_id)
            action = {"operation": parsed.operation, "arguments": parsed.payload}
            if parsed.operation == "audio.playback":
                try:
                    action = self._prepare_audio_playback_action(state, parsed, grant)
                except SurfaceError as exc:
                    self._settle_operation(parsed.operation_id, self._not_started(str(exc)))
                    return self.inspect(parsed.operation_id)
                authorization = action.get("_surface_audio_authorization")
                if not isinstance(authorization, Mapping) or not authorization["validate"]():
                    self._settle_operation(parsed.operation_id,
                                           self._not_started("audio.playback grant failed its final authorization check"))
                    return self.inspect(parsed.operation_id)
            self._append_event({"type": "operation_dispatching", "operation_id": parsed.operation_id,
                                "request_digest": request_digest}, operation_id=parsed.operation_id)
            with self._lock:
                record = self._operations.get(parsed.operation_id)
                if record is not None:
                    record["phase"] = "dispatching"
            try:
                backend_result = state.backend.dispatch(state.backend_binding, action)
                outcome_record = EffectOutcome.from_backend(backend_result)
                safe_outcome = self._safe_outcome(outcome_record)
            except Exception as exc:
                # Once dispatch is entered, exceptions cannot prove the provider
                # did not deliver anything; never retry this operation identity.
                safe_outcome = {"disposition": "unknown", "delivered_count": 0,
                                "ack_strength": "unknown", "detail": {"reason": self._exception_reason(exc)}}
            self._settle_operation(parsed.operation_id, safe_outcome)
            self._maybe_block_on_outcome(state, safe_outcome)
        return self.inspect(parsed.operation_id)

    def _playback_grant_is_current(self, state: _BindingState, grant: _Grant, endpoint: str) -> bool:
        current_endpoint = (state.backend_binding.get("audio_session_endpoint_id")
                            or state.backend_binding.get("audio_endpoint_id"))
        with self._lock:
            now = time.monotonic_ns()
            return (not self._closed and not state.detached and not state.inhibited and not state.human_control
                    and state.state not in {"stale", "lost", "paused", "reconciliation-required",
                                            "neutralization-pending", "input-suspended", "release-pending",
                                            "detached-neutralization-pending"}
                    and self._grants.get(grant.grant_id) is grant and grant.active
                    and grant.controller == "cassi" and "audio.playback" in grant.operations
                    and grant.binding_id == state.binding_id and grant.scope.get("audio_recipient_scope") == endpoint
                    and current_endpoint == endpoint
                    and now < min(grant.expires_ns, grant.absolute_deadline_ns, grant.lease_deadline_ns)
                    and grant.scope.get("source_id") == state.record.source_id
                    and grant.scope.get("source_instance") == state.record.source_instance
                    and grant.scope.get("source_epoch") == state.record.source_epoch
                    and grant.scope.get("geometry_revision") == state.record.geometry_revision
                    and grant.scope.get("environment_incarnation") == state.record.environment_incarnation
                    and grant.scope.get("backend_input_domain") == state.record.input_domain
                    and grant.scope.get("backend_input_domain_epoch") == state.record.input_domain_epoch
                    and grant.focus_epoch == state.record.focus_epoch
                    and (grant.input_domain is None or (
                        self._domain_leases.get(grant.input_domain) == grant.grant_id
                        and self._domain_epochs.get(grant.input_domain) == grant.input_domain_epoch)))

    def _prepare_audio_playback_action(self, state: _BindingState, intent: ControlIntent,
                                       grant: _Grant) -> dict[str, Any]:
        artifact_ref = intent.payload.get("artifact_ref")
        expected_keys = {"binding_id", "generation", "offset", "length"}
        if not isinstance(artifact_ref, Mapping) or set(artifact_ref) != expected_keys:
            raise SurfaceValidationError("audio.playback requires an exact field-owned artifact_ref")
        if artifact_ref.get("binding_id") != state.binding_id:
            raise SurfaceAuthorizationError("audio artifact belongs to another surface binding")
        generation = self._positive_int(artifact_ref.get("generation"), "artifact_ref.generation")
        offset = self._bounded_int(artifact_ref.get("offset"), "artifact_ref.offset", MAX_AUDIO_BYTES)
        length = self._bounded_int(artifact_ref.get("length"), "artifact_ref.length", _MAX_PAGE_READ_BYTES, minimum=1)
        publication = state.publications.get(generation)
        if publication is None:
            raise SurfaceConflictError("audio artifact generation is no longer pinned")
        audio = publication.metadata.get("audio")
        if not publication.metadata.get("audio_available") or not isinstance(audio, Mapping):
            raise SurfaceCapabilityError("audio artifact generation contains no audio")
        if (audio.get("binding_id") != state.binding_id or audio.get("source_epoch") != publication.source_epoch
                or audio.get("geometry_revision") != publication.geometry_revision):
            raise SurfaceConflictError("audio artifact descriptor does not match its pinned source generation")
        coverage = audio.get("coverage")
        if not isinstance(coverage, Mapping) or coverage.get("complete") is not True:
            raise SurfaceCapabilityError("audio artifact does not declare complete capture coverage")
        total = self._bounded_int(audio.get("byte_length"), "audio byte_length", MAX_AUDIO_BYTES, minimum=1)
        if offset + length > total:
            raise SurfaceValidationError("audio artifact range escapes the publication")
        audio_format = audio.get("audio_format")
        if audio_format not in AUDIO_SAMPLE_BYTES:
            raise SurfaceCapabilityError("audio artifact format is unsupported for playback")
        channels = self._bounded_int(audio.get("channel_count"), "audio channel_count", 8, minimum=1)
        frame_bytes = AUDIO_SAMPLE_BYTES[audio_format] * channels
        if offset % frame_bytes or length % frame_bytes:
            raise SurfaceValidationError("audio artifact range is not aligned to complete sample frames")
        endpoint = (state.backend_binding.get("audio_session_endpoint_id")
                    or state.backend_binding.get("audio_endpoint_id"))
        endpoint = self._required_text(endpoint, "audio session endpoint id", 256)
        if grant.scope.get("audio_recipient_scope") != endpoint:
            raise SurfaceAuthorizationError("audio playback recipient differs from the approved endpoint")
        allowed_ref = grant.scope.get("artifact_ref")
        if allowed_ref is not None and canonical_json(allowed_ref) != canonical_json(dict(artifact_ref)):
            raise SurfaceAuthorizationError("audio artifact is outside the approved playback scope")
        allowed_generation = grant.scope.get("publication_generation")
        if allowed_generation is not None and allowed_generation != generation:
            raise SurfaceAuthorizationError("audio artifact generation is outside the approved playback scope")
        reader = getattr(self._field_owner, "read_surface_audio_page", None)
        if not callable(reader):
            raise SurfaceCapabilityError("field owner does not provide audio page reads")
        if not self._playback_grant_is_current(state, grant, endpoint):
            raise SurfaceAuthorizationError("audio.playback grant is no longer current")
        audio_payload = reader(state.binding_id, generation, offset, length)
        if not isinstance(audio_payload, bytes) or len(audio_payload) != length:
            raise SurfaceWaitError({"kind": "surface-audio-page", "reason": "requested playback audio page is unavailable",
                                    "binding_id": state.binding_id, "generation": generation})
        sample_rate = self._bounded_int(audio.get("sample_rate_hz"), "audio sample_rate_hz", 192_000, minimum=1)
        frame_count = length // frame_bytes
        resolved_audio = {
            "samples": audio_payload,
            "format": audio_format,
            "sample_rate": sample_rate,
            "channels": channels,
            "recipient_scope": endpoint,
            "byte_length": length,
            "sha256": hashlib.sha256(audio_payload).hexdigest(),
            "duration_ms": (frame_count * 1_000 + sample_rate // 2) // sample_rate,
        }
        authorization = {
            "mission_id": intent.mission_id,
            "grant_id": grant.grant_id,
            "binding_id": state.binding_id,
            "operations": ["audio.playback"],
            "recipient_scope": endpoint,
            "validate": lambda: self._playback_grant_is_current(state, grant, endpoint),
        }
        return {"operation": intent.operation, "arguments": intent.payload,
                "_audio_payload": resolved_audio, "_surface_audio_authorization": authorization}

    def _validate_intent_authority(self, intent: ControlIntent, state: _BindingState, grant: _Grant) -> None:
        now = time.monotonic_ns()
        if not state or state.detached or state.state in {"detached", "stale", "lost"}:
            raise SurfaceCapabilityError("binding is detached or stale")
        if state.inhibited or state.state in {"paused", "reconciliation-required", "neutralization-pending",
                                               "input-suspended"}:
            raise SurfaceWaitError({"kind": "control-state", "reason": f"binding is {state.state}",
                                    "binding_id": state.binding_id})
        if state.human_control and grant.controller != "human":
            raise SurfaceAuthorizationError("human control has priority")
        if grant.controller == "human" and not state.human_control:
            raise SurfaceAuthorizationError("human control lease is no longer active")
        if intent.mission_id != grant.mission_id or intent.binding_id != grant.binding_id:
            raise SurfaceAuthorizationError("intent mission or binding is outside the issued grant")
        if intent.operation not in grant.operations:
            raise SurfaceAuthorizationError("operation is outside the issued grant")
        if intent.operation not in state.record.operations:
            raise SurfaceCapabilityError("operation is not advertised by the bound source")
        if intent.expected_source_epoch != state.record.source_epoch:
            raise SurfaceConflictError("intent source epoch is stale")
        if intent.expected_geometry_revision != state.record.geometry_revision:
            raise SurfaceConflictError("intent geometry revision is stale")
        if (self._requires_input_lease(intent.operation) and state.record.focus_epoch is not None
                and intent.expected_focus_epoch is None):
            raise SurfaceValidationError("focus-sensitive control requires an expected_focus_epoch")
        if intent.expected_focus_epoch is not None and intent.expected_focus_epoch != grant.focus_epoch:
            raise SurfaceConflictError("intent focus compare-and-set failed")
        if (intent.expected_input_domain_epoch is not None
                and intent.expected_input_domain_epoch != state.record.input_domain_epoch):
            raise SurfaceConflictError("backend input-domain epoch compare-and-set failed")
        if now >= grant.expires_ns or now >= grant.absolute_deadline_ns or now >= grant.lease_deadline_ns:
            raise SurfaceAuthorizationError("grant or control lease has expired")
        if grant.input_domain is not None:
            with self._lock:
                if self._domain_leases.get(grant.input_domain) != grant.grant_id:
                    raise SurfaceAuthorizationError("input-domain lease is no longer current")
                if self._domain_epochs.get(grant.input_domain) != grant.input_domain_epoch:
                    raise SurfaceConflictError("input-domain lease compare-and-set failed")
        if intent.deadline_ns is not None and time.monotonic_ns() >= intent.deadline_ns:
            raise SurfaceAuthorizationError("intent deadline has expired")
        if intent.created_ns is not None and intent.created_ns > time.monotonic_ns() + 5_000_000_000:
            raise SurfaceValidationError("intent creation time is in the future")
        if (grant.scope.get("source_id") != state.record.source_id
                or grant.scope.get("source_instance") != state.record.source_instance
                or grant.scope.get("source_epoch") != state.record.source_epoch
                or grant.scope.get("geometry_revision") != state.record.geometry_revision
                or grant.scope.get("environment_incarnation") != state.record.environment_incarnation):
            raise SurfaceAuthorizationError("grant source scope no longer matches the bound generation")
        scoped_target = grant.scope.get("semantic_target")
        if scoped_target is not None and intent.semantic_target != scoped_target:
            raise SurfaceAuthorizationError("semantic target is outside the grant scope")
        reservation = intent.resource_reservation
        allowed_bytes = grant.scope.get("max_payload_bytes", MAX_INTENT_BYTES)
        if len(canonical_json(intent.payload)) > allowed_bytes:
            raise SurfaceWaitError({"kind": "resource", "reason": "intent payload exceeds the granted byte allowance",
                                    "requested_bytes": len(canonical_json(intent.payload)), "available_bytes": allowed_bytes})
        if reservation is not None:
            allowed_reservation = grant.scope.get("resource_reservation")
            if allowed_reservation is not None and not self._mapping_subset(reservation, allowed_reservation):
                raise SurfaceAuthorizationError("resource reservation exceeds the granted allowance")

    def _ensure_dispatch_fence(self, state: _BindingState, intent: ControlIntent, grant: _Grant) -> None:
        self._ensure_attached(state)
        if state.inhibited:
            raise SurfaceAuthorizationError("source is inhibited pending confirmed neutralization")
        with self._lock:
            current_grant = self._grants.get(grant.grant_id)
            if current_grant is not grant or not grant.active:
                raise SurfaceAuthorizationError("grant was revoked before the final dispatch fence")
            if state.human_control and grant.controller != "human":
                raise SurfaceAuthorizationError("human control has priority")
            self._validate_intent_authority(intent, state, grant)
            op = self._operations.get(intent.operation_id)
            if op is None or op.get("phase") != "reserved":
                raise SurfaceConflictError("operation reservation is no longer dispatchable")

        current = self._refresh_source_binding(state, capture=False)
        if (current.source_instance != state.record.source_instance
                or current.environment_incarnation != state.record.environment_incarnation
                or current.source_epoch != intent.expected_source_epoch
                or current.geometry_revision != intent.expected_geometry_revision):
            state.state = "stale"
            self._invalidate_binding_grants(state, reason="source-identity-or-geometry-changed")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            raise SurfaceConflictError("source, environment, epoch, or geometry changed at final handoff")
        if self._requires_input_lease(intent.operation) and current.input_state not in {"available", "live", "supported"}:
            state.human_control = current.input_state == "suspended"
            state.state = "human-control" if state.human_control else "input-unavailable"
            self._require_fresh_capture(state)
            self._invalidate_binding_grants(state, reason="input-suspended")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            raise SurfaceCapabilityError(f"input is {current.input_state} at final handoff")
        if (self._requires_input_lease(intent.operation)
                and intent.expected_focus_epoch is None and current.focus_epoch is not None):
            raise SurfaceValidationError("focus-sensitive control requires an expected_focus_epoch")
        if intent.expected_focus_epoch is not None and current.focus_epoch != intent.expected_focus_epoch:
            raise SurfaceConflictError("backend focus compare-and-set failed")
        if intent.expected_input_domain_epoch is not None and intent.expected_input_domain_epoch != current.input_domain_epoch:
            raise SurfaceConflictError("backend input-domain epoch compare-and-set failed")

        if self._is_control_operation(intent.operation):
            dependencies = intent.dependency_versions
            publication_generation = dependencies.get("publication_generation") if isinstance(dependencies, Mapping) else None
            publication_generation = self._positive_int(publication_generation, "dependency_versions.publication_generation")
            publication = state.publications.get(publication_generation)
            if publication is None:
                raise SurfaceConflictError("control intent does not name a retained observation generation")
            metadata = publication.metadata
            if (metadata.get("binding_id") != state.binding_id
                    or metadata.get("source_instance") != current.source_instance
                    or metadata.get("source_epoch") != current.source_epoch
                    or metadata.get("environment_incarnation") != current.environment_incarnation
                    or metadata.get("geometry_revision") != current.geometry_revision):
                raise SurfaceConflictError("control observation dependency belongs to another source epoch")
            if (state.capture_required_after_generation is not None
                    and publication_generation <= state.capture_required_after_generation):
                raise SurfaceConflictError("control intent references an observation older than the latest safety boundary")
            if grant.scope.get("publication_generation") not in (None, publication_generation):
                raise SurfaceAuthorizationError("observation generation is outside the grant scope")
            if intent.operation == "audio.playback":
                artifact_ref = intent.payload.get("artifact_ref")
                if not isinstance(artifact_ref, Mapping) or artifact_ref.get("generation") != publication_generation:
                    raise SurfaceConflictError("audio.playback artifact and observation dependency differ")
                audio = metadata.get("audio")
                coverage = audio.get("coverage") if isinstance(audio, Mapping) else None
            else:
                coverage = metadata.get("coverage")
            if not isinstance(coverage, Mapping) or coverage.get("complete") is not True:
                raise SurfaceConflictError("control observation does not declare complete target coverage")

        if intent.semantic_target is not None:
            revalidate_target = getattr(state.backend, "revalidate_target", None)
            if not callable(revalidate_target):
                raise SurfaceCapabilityError("backend cannot validate semantic targets against the bound source")
            try:
                target_result = revalidate_target(state.backend_binding, intent.semantic_target)
            except Exception as exc:
                raise SurfaceWaitError({"kind": "semantic-target", "reason": "bound target validation did not complete",
                                        "binding_id": state.binding_id, "error": self._exception_reason(exc)}) from exc
            if not isinstance(target_result, Mapping) or target_result.get("supported") is not True:
                raise SurfaceCapabilityError("backend semantic target validation is unsupported")
            if target_result.get("valid") is not True:
                state.state = "stale"
                self._invalidate_binding_grants(state, reason="semantic-target-no-longer-valid")
                neutral = self._neutralize_backend(state)
                state.inhibited = not neutral["confirmed"]
                raise SurfaceConflictError("semantic target is stale or no longer observed")

        self._require_supported_operations(state, (intent.operation,))
        with self._lock:
            if self._grants.get(grant.grant_id) is not grant or not grant.active:
                raise SurfaceAuthorizationError("grant was revoked at the final dispatch fence")
            if grant.input_domain is not None and self._domain_leases.get(grant.input_domain) != grant.grant_id:
                raise SurfaceAuthorizationError("input-domain lease was revoked at the final dispatch fence")
            self._validate_intent_authority(intent, state, grant)

    # ---- operation ledger, inspection, reconciliation -----------------

    def inspect_grant(self, grant_id: str) -> dict[str, Any]:
        """Inspect grant status and limited program provenance without exposing arbitrary scope."""
        grant_id = self._required_text(grant_id, "grant_id", MAX_IDENTIFIER)
        now = time.monotonic_ns()
        with self._lock:
            grant = self._grants.get(grant_id)
            if grant is None:
                return {"grant_id": grant_id, "state": "unknown-grant", "active": False}
            deadline = min(grant.expires_ns, grant.absolute_deadline_ns, grant.lease_deadline_ns)
            active = grant.active and now < deadline
            status = "granted" if active else "expired" if grant.active else "revoked"
            result = {
                "grant_id": grant.grant_id,
                "mission_id": grant.mission_id,
                "binding_id": grant.binding_id,
                "operations": sorted(grant.operations),
                "controller": grant.controller,
                "state": status,
                "active": active,
                "expires_ns": grant.expires_ns,
                "lease_deadline_ns": grant.lease_deadline_ns,
                "focus_epoch": grant.focus_epoch,
                "input_lease_domain": grant.input_domain,
                "input_lease_epoch": grant.input_domain_epoch,
                "max_updates": grant.max_updates,
                "updates_remaining": max(0, grant.max_updates - grant.next_sequence + 1),
                "scope_digest": hashlib.sha256(canonical_json(grant.scope)).hexdigest(),
            }
            for key in ("program_id", "program_generation", "mission_sha256"):
                value = grant.scope.get(key)
                if (isinstance(value, str) and len(value) <= 256) or (
                        key == "program_generation" and isinstance(value, int) and not isinstance(value, bool)):
                    result[key] = value
            return result

    def inspect(self, operation_id: str) -> dict[str, Any]:
        operation_id = self._required_text(operation_id, "operation_id", 192)
        with self._lock:
            record = self._operations.get(operation_id)
            if record is None:
                return {"operation_id": operation_id, "state": "unknown-operation"}
            return self._operation_view(record)

    def reconcile(self, operation_id: str, outcome: Mapping[str, Any]) -> dict[str, Any]:
        operation_id = self._required_text(operation_id, "operation_id", 192)
        if not isinstance(outcome, Mapping):
            raise SurfaceValidationError("reconciliation outcome must be an object")
        allowed = {"status", "observation", "evidence_refs", "observed_ns", "source_epoch", "detail"}
        if set(outcome) - allowed or "status" not in outcome:
            raise SurfaceValidationError("reconciliation outcome has an invalid shape")
        status = outcome.get("status")
        if status not in {"observed-success", "observed-failure", "still-unknown", "continue-waiting"}:
            raise SurfaceValidationError("reconciliation status is unsupported")
        safe = json_value(dict(outcome), max_bytes=MAX_DETAIL_BYTES, label="reconciliation outcome")
        with self._lock:
            current = self._operations.get(operation_id)
            if current is None:
                raise SurfaceCapabilityError("operation is not present in the durable ledger")
            if current.get("phase") not in {"settled", "reconciled"}:
                raise SurfaceConflictError("operation has not crossed the dispatch fence")
            if current.get("disposition") not in {"unknown", "partially-delivered", "delivered", "rejected", "not-started"}:
                raise SurfaceConflictError("operation has no delivery outcome to reconcile")
            existing = current.get("reconciliation")
            if existing is not None:
                if canonical_json(existing) != canonical_json(safe):
                    raise SurfaceConflictError("operation already has a different reconciliation record")
                return self._operation_view(current)
        self._append_event({"type": "operation_reconciled", "operation_id": operation_id,
                            "request_digest": current["request_digest"], "reconciliation": safe})
        with self._lock:
            current["phase"] = "reconciled"
            current["reconciliation"] = safe
            return self._operation_view(current)

    def _reserve_ledger_capacity(self, operation_id: str) -> None:
        with self._ledger_lock:
            if operation_id in self._op_reservations:
                return
            self._refresh_ledger_size()
            if self._ledger_size + self._ledger_reserved_bytes + _OPERATION_LEDGER_RESERVE > _MAX_LEDGER_BYTES:
                raise SurfaceWaitError({"kind": "storage", "reason": "durable effect ledger has insufficient reserved space",
                                        "requested_bytes": _OPERATION_LEDGER_RESERVE,
                                        "available_bytes": max(0, _MAX_LEDGER_BYTES - self._ledger_size - self._ledger_reserved_bytes)})
            self._op_reservations[operation_id] = _OPERATION_LEDGER_RESERVE
            self._ledger_reserved_bytes += _OPERATION_LEDGER_RESERVE

    def _release_ledger_capacity(self, operation_id: str) -> None:
        with self._ledger_lock:
            reserved = self._op_reservations.pop(operation_id, 0)
            self._ledger_reserved_bytes = max(0, self._ledger_reserved_bytes - reserved)

    @property
    def _ledger_size(self) -> int:
        try:
            return self._ledger_path.stat().st_size
        except FileNotFoundError:
            return 0

    def _refresh_ledger_size(self) -> None:
        size = self._ledger_size
        if size > _MAX_LEDGER_BYTES:
            raise SurfaceWaitError({"kind": "storage", "reason": "durable effect ledger exceeds its configured hard limit",
                                    "available_bytes": 0, "used_bytes": size, "limit_bytes": _MAX_LEDGER_BYTES})

    def _append_event(self, event: Mapping[str, Any], *, operation_id: str | None = None) -> None:
        row = {"version": _LEDGER_VERSION, "written_ns": time.time_ns(), **dict(event)}
        encoded = canonical_json(row) + b"\n"
        if len(encoded) > _MAX_LEDGER_LINE_BYTES:
            raise SurfaceWaitError({"kind": "storage", "reason": "ledger record exceeds its bounded line size",
                                    "requested_bytes": len(encoded), "limit_bytes": _MAX_LEDGER_LINE_BYTES})
        with self._ledger_lock:
            self._refresh_ledger_size()
            reservation = self._op_reservations.get(operation_id or "", 0)
            other_reserved = self._ledger_reserved_bytes - reservation
            if self._ledger_size + other_reserved + len(encoded) > _MAX_LEDGER_BYTES:
                raise SurfaceWaitError({"kind": "storage", "reason": "durable effect ledger is full",
                                        "requested_bytes": len(encoded),
                                        "available_bytes": max(0, _MAX_LEDGER_BYTES - self._ledger_size - other_reserved)})
            self._append_file_locked(encoded)

    def _append_file_locked(self, encoded: bytes) -> None:
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._ledger_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
        try:
            self._lock_file(fd)
            # Recheck after taking the process-shared file lock.
            if os.fstat(fd).st_size + len(encoded) > _MAX_LEDGER_BYTES:
                raise SurfaceWaitError({"kind": "storage", "reason": "durable effect ledger is full",
                                        "requested_bytes": len(encoded), "limit_bytes": _MAX_LEDGER_BYTES})
            written = os.write(fd, encoded)
            if written != len(encoded):
                raise OSError("short durable ledger append")
            os.fsync(fd)
        finally:
            try:
                self._unlock_file(fd)
            finally:
                os.close(fd)

    def _lock_file(self, fd: int) -> None:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock_file(self, fd: int) -> None:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass

    def _replay_ledger(self) -> None:
        if not self._ledger_path.exists():
            return
        size = self._ledger_path.stat().st_size
        if size > _MAX_LEDGER_BYTES:
            raise SurfaceWaitError({"kind": "storage", "reason": "effect ledger exceeds the configured hard limit",
                                    "used_bytes": size, "limit_bytes": _MAX_LEDGER_BYTES})
        with self._ledger_path.open("rb") as stream:
            for line_number, line in enumerate(stream, 1):
                if len(line) > _MAX_LEDGER_LINE_BYTES:
                    raise SurfaceValidationError(f"effect ledger line {line_number} exceeds its bounded size")
                if not line.endswith(b"\n"):
                    raise SurfaceValidationError(f"effect ledger line {line_number} is incomplete")
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise SurfaceValidationError(f"effect ledger line {line_number} is invalid JSON") from exc
                if not isinstance(row, dict) or row.get("version") != _LEDGER_VERSION:
                    raise SurfaceValidationError(f"effect ledger line {line_number} has an unsupported version")
                self._apply_ledger_row(row)

    def _apply_ledger_row(self, row: Mapping[str, Any]) -> None:
        event_type = row.get("type")
        if event_type == "operation_reserved":
            operation_id = self._required_text(row.get("operation_id"), "ledger operation_id", 192)
            digest = self._required_digest(row.get("request_digest"))
            previous = self._operations.get(operation_id)
            if previous is not None and previous["request_digest"] != digest:
                raise SurfaceConflictError("effect ledger contains conflicting operation identity history")
            self._operations[operation_id] = {
                "operation_id": operation_id, "request_digest": digest, "phase": "reserved",
                "mission_id": self._optional_text(row.get("mission_id"), "mission_id", 192),
                "binding_id": self._optional_text(row.get("binding_id"), "binding_id", 192),
                "grant_digest": self._optional_text(row.get("grant_digest"), "grant_digest", 128),
                "operation": self._optional_text(row.get("operation"), "operation", 128),
                "sequence": row.get("sequence"), "disposition": None, "delivered_count": 0,
                "ack_strength": None, "detail": None, "reconciliation": None,
            }
        elif event_type == "operation_dispatching":
            record = self._operation_for_row(row)
            record["phase"] = "dispatching"
        elif event_type == "operation_outcome":
            record = self._operation_for_row(row)
            outcome = row.get("outcome")
            if not isinstance(outcome, Mapping):
                raise SurfaceValidationError("effect ledger outcome must be an object")
            parsed = EffectOutcome.from_backend(outcome)
            record.update({"phase": "settled", "disposition": parsed.disposition,
                           "delivered_count": parsed.delivered_count, "ack_strength": parsed.ack_strength,
                           "detail": parsed.detail})
        elif event_type == "operation_reconciled":
            record = self._operation_for_row(row)
            reconciliation = json_value(row.get("reconciliation"), max_bytes=MAX_DETAIL_BYTES, label="ledger reconciliation")
            record["phase"] = "reconciled"
            record["reconciliation"] = reconciliation
        # Grant/revoke/lease events are audit evidence only; grants are never
        # restored after a process restart.

    def _operation_for_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        operation_id = self._required_text(row.get("operation_id"), "ledger operation_id", 192)
        record = self._operations.get(operation_id)
        if record is None:
            raise SurfaceValidationError("effect ledger has a transition without a reservation")
        if row.get("request_digest") is not None and row.get("request_digest") != record["request_digest"]:
            raise SurfaceConflictError("effect ledger transition digest does not match reservation")
        return record

    def _recover_inflight(self) -> None:
        # Reserved without a dispatch fence is known not-started. A durable
        # dispatching record may have crossed the provider boundary and stays
        # unknown until a host owner reconciles it.
        for operation_id, record in list(self._operations.items()):
            if record["phase"] == "reserved":
                outcome = {"disposition": "not-started", "delivered_count": 0,
                           "ack_strength": "none", "detail": {"reason": "recovered before dispatch fence"}}
            elif record["phase"] == "dispatching":
                outcome = {"disposition": "unknown", "delivered_count": 0,
                           "ack_strength": "unknown", "detail": {"reason": "recovered during external delivery; reconciliation required"}}
            else:
                continue
            self._append_event({"type": "operation_outcome", "operation_id": operation_id,
                                "request_digest": record["request_digest"], "outcome": outcome})
            record.update({"phase": "settled", "disposition": outcome["disposition"],
                           "delivered_count": outcome["delivered_count"], "ack_strength": outcome["ack_strength"],
                           "detail": outcome["detail"]})

    def _settle_operation(self, operation_id: str, outcome: Mapping[str, Any]) -> None:
        safe = json_value(outcome, max_bytes=MAX_DETAIL_BYTES, label="effect outcome")
        with self._lock:
            record = self._operations.get(operation_id)
            if record is None:
                raise SurfaceConflictError("operation reservation disappeared")
            digest = record["request_digest"]
        self._append_event({"type": "operation_outcome", "operation_id": operation_id,
                            "request_digest": digest, "outcome": safe}, operation_id=operation_id)
        with self._lock:
            record = self._operations[operation_id]
            parsed = EffectOutcome.from_backend(safe)
            record.update({"phase": "settled", "disposition": parsed.disposition,
                           "delivered_count": parsed.delivered_count, "ack_strength": parsed.ack_strength,
                           "detail": parsed.detail})
        self._release_ledger_capacity(operation_id)

    def _operation_view(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "operation_id": record["operation_id"],
            "request_digest": record["request_digest"],
            "state": record["phase"],
            "mission_id": record.get("mission_id"),
            "binding_id": record.get("binding_id"),
            "operation": record.get("operation"),
            "sequence": record.get("sequence"),
            "disposition": record.get("disposition"),
            "delivered_count": record.get("delivered_count", 0),
            "ack_strength": record.get("ack_strength"),
            "detail": record.get("detail"),
            "reconciliation": record.get("reconciliation"),
            "reconciliation_required": record.get("disposition") in {"unknown", "partially-delivered"}
                                    and record.get("reconciliation") is None,
        }

    def _safe_outcome(self, outcome: EffectOutcome) -> dict[str, Any]:
        # Provider detail may echo typed text or credentials into the durable
        # host effect ledger; retain only bounded structural acknowledgements.
        detail: dict[str, Any] = {}
        if isinstance(outcome.detail, Mapping):
            for key in ("event_sequence", "source_epoch", "geometry_revision", "input_sequence", "actual_count"):
                value = outcome.detail.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    detail[key] = value
            status = outcome.detail.get("status")
            if status in {"queued", "inserted", "acknowledged", "rejected", "not-started"}:
                detail["status"] = status
            code = outcome.detail.get("code")
            if isinstance(code, int) and not isinstance(code, bool):
                detail["code"] = code
        elif outcome.detail:
            detail["reason"] = "backend detail withheld"
        return {"disposition": outcome.disposition, "delivered_count": outcome.delivered_count,
                "ack_strength": outcome.ack_strength, "detail": detail}

    def _not_started(self, reason: str) -> dict[str, Any]:
        return {"disposition": "not-started", "delivered_count": 0, "ack_strength": "none",
                "detail": {"reason": reason[:256]}}

    def _require_fresh_capture(self, state: _BindingState) -> None:
        latest = max(state.publications, default=0)
        previous = state.capture_required_after_generation or 0
        state.capture_required_after_generation = max(previous, latest)

    def _maybe_block_on_outcome(self, state: _BindingState, outcome: Mapping[str, Any]) -> None:
        if outcome.get("disposition") in {"unknown", "partially-delivered"}:
            self._invalidate_binding_grants(state, reason="uncertain-or-partial-delivery")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            state.state = "reconciliation-required" if neutral["confirmed"] else "neutralization-pending"
            self._require_fresh_capture(state)

    # ---- revoke, pause, human control, and source lifetime --------------

    def revoke(self, binding_id: str) -> dict[str, Any]:
        state = self._binding_state(binding_id)
        with state.lock:
            self._invalidate_binding_grants(state, reason="revoked")
            neutral = self._neutralize_backend(state)
            state.inhibited = not neutral["confirmed"]
            state.state = "revoked" if neutral["confirmed"] else "neutralization-pending"
            self._require_fresh_capture(state)
            self._cancel_reserved_operations(binding_id, "revoked before dispatch")
            self._append_event({"type": "binding_revoked", "binding_id": binding_id,
                                "source_epoch": state.record.source_epoch, "neutralization_confirmed": neutral["confirmed"]})
            return {"binding_id": binding_id, "state": state.state, "revoked": True, "neutralization": neutral,
                    "observation_attached": not state.detached}

    def take_control(self, binding_id: str, mission_id: str | None = None, operations: Any = None,
                     expires_ns: int | None = None) -> dict[str, Any]:
        state = self._binding_state(binding_id)
        if mission_id is None:
            raise SurfaceValidationError("human takeover must be bound to the active mission_id")
        mission_id = self._required_text(mission_id, "mission_id", 192)
        with state.lock:
            self._ensure_attached(state)
            self._refresh_source_binding(state, capture=False)
            domain = self._input_domain(state.record)
            if state.record.input_state not in {"available", "live", "supported"}:
                raise SurfaceCapabilityError(f"human input is {state.record.input_state}")
        human_operations = normalize_operations(operations) if operations is not None else tuple(
            operation for operation in state.record.operations if self._requires_input_lease(operation))
        if any(not self._requires_input_lease(operation) for operation in human_operations):
            raise SurfaceValidationError("human takeover can authorize only host input operations")
        if not human_operations:
            raise SurfaceCapabilityError("source has no advertised human input operations")
        self._require_supported_operations(state, human_operations)
        now = time.monotonic_ns()
        expires_ns = expires_ns or min(now + _MAX_CONTROL_DURATION_NS, now + 600_000_000_000)
        expires_ns = self._positive_int(expires_ns, "expires_ns")
        if expires_ns <= now or expires_ns - now > _MAX_GRANT_TTL_NS:
            raise SurfaceValidationError("human control expiry is outside the bounded lease interval")
        # Fencing and neutralization precede viewer input admission.
        revoked = self.revoke(binding_id)
        if not revoked["neutralization"]["confirmed"]:
            return {"binding_id": binding_id, "state": "takeover-pending", "human_control": False,
                    "neutralization": revoked["neutralization"]}
        grant_id = token_urlsafe(32)
        scope = {"controller": "human", "input_domain": domain,
                 "environment_incarnation": state.record.environment_incarnation,
                 "source_id": state.record.source_id, "source_instance": state.record.source_instance,
                 "source_epoch": state.record.source_epoch, "geometry_revision": state.record.geometry_revision,
                 "backend_input_domain_epoch": state.record.input_domain_epoch,
                 "max_duration_ns": min(expires_ns - now, _MAX_CONTROL_DURATION_NS),
                 "heartbeat_timeout_ns": _DEFAULT_HEARTBEAT_NS, "max_updates": _MAX_GRANT_UPDATES}
        proposal = {"purpose": "surface-human-control", "grant_id": grant_id, "mission_id": mission_id,
                    "binding_id": binding_id, "backend_id": state.record.backend_id, "source_id": state.record.source_id,
                    "source_instance": state.record.source_instance, "source_epoch": state.record.source_epoch,
                    "environment_incarnation": state.record.environment_incarnation,
                    "geometry_revision": state.record.geometry_revision, "operations": list(human_operations),
                    "expires_ns": expires_ns, "scope": scope}
        approved = self._ask_authorizer(proposal)
        approved_operations, approved_scope = self._approved_decision(approved, human_operations, scope)
        with state.lock:
            self._ensure_attached(state)
            self._refresh_source_binding(state, capture=False)
            if self._input_domain(state.record) != domain:
                raise SurfaceConflictError("input domain changed during human takeover approval")
            if state.record.input_state not in {"available", "live", "supported"}:
                raise SurfaceCapabilityError(f"human input is {state.record.input_state}")
            self._require_supported_operations(state, tuple(approved_operations))
            with self._lock:
                if domain in self._domain_leases:
                    raise SurfaceWaitError({"kind": "input-lease", "reason": "input domain is already leased"})
                epoch = self._domain_epochs.get(domain, state.record.input_domain_epoch or 0) + 1
                self._domain_epochs[domain] = epoch
                self._domain_leases[domain] = grant_id
            issued = time.monotonic_ns()
            if expires_ns <= issued:
                self._drop_provisional_domain(domain, grant_id, True)
                raise SurfaceAuthorizationError("human control expired before host approval completed")
            duration = min(approved_scope.get("max_duration_ns", _MAX_CONTROL_DURATION_NS), expires_ns - issued,
                           _MAX_CONTROL_DURATION_NS)
            grant = _Grant(grant_id, mission_id, binding_id, frozenset(approved_operations), approved_scope, expires_ns,
                           issued, issued + duration, approved_scope.get("heartbeat_timeout_ns", _DEFAULT_HEARTBEAT_NS),
                           min(expires_ns, issued + duration, issued + _DEFAULT_HEARTBEAT_NS),
                           approved_scope.get("max_updates", _MAX_GRANT_UPDATES), input_domain=domain,
                           input_domain_epoch=epoch, focus_epoch=state.record.focus_epoch, controller="human")
            try:
                self._append_event({"type": "human_control_issued", "grant_digest": self._grant_digest(grant),
                                    "mission_id": mission_id, "binding_id": binding_id,
                                    "expires_ns": expires_ns, "operations": list(approved_operations),
                                    "scope_digest": hashlib.sha256(canonical_json(approved_scope)).hexdigest()})
            except Exception:
                self._drop_provisional_domain(domain, grant_id, True)
                raise
            with self._watch:
                self._grants[grant_id] = grant
                state.human_control = True
                state.inhibited = False
                state.state = "human-control"
                self._watch.notify_all()
        return {"binding_id": binding_id, "mission_id": mission_id, "state": "human-control",
                "human_control": True, "grant_id": grant_id, "operations": list(approved_operations),
                "expires_ns": expires_ns, "input_domain_epoch": state.record.input_domain_epoch,
                "input_lease_epoch": epoch}

    def release_human(self, binding_id: str) -> dict[str, Any]:
        state = self._binding_state(binding_id)
        with state.lock:
            self._invalidate_binding_grants(state, reason="human-control-released")
            neutral = self._neutralize_backend(state)
            state.human_control = False
            state.inhibited = not neutral["confirmed"]
            state.state = "observation-only" if neutral["confirmed"] else "neutralization-pending"
            self._require_fresh_capture(state)
            self._cancel_reserved_operations(binding_id, "human control released before dispatch")
            self._append_event({"type": "human_control_released", "binding_id": binding_id,
                                "source_epoch": state.record.source_epoch, "neutralization_confirmed": neutral["confirmed"]})
            return {"binding_id": binding_id, "state": state.state, "human_control": False,
                    "neutralization": neutral, "fresh_grant_required": True}

    def pause(self, binding_id: str) -> dict[str, Any]:
        result = self.revoke(binding_id)
        state = self._binding_state(binding_id)
        state.state = "paused" if result["neutralization"]["confirmed"] else "neutralization-pending"
        result["state"] = state.state
        return result

    def resume(self, binding_id: str) -> dict[str, Any]:
        state = self._binding_state(binding_id)
        with state.lock:
            self._ensure_attached(state)
            self._refresh_source_binding(state, capture=False)
            if state.inhibited:
                raise SurfaceWaitError({"kind": "neutralization", "reason": "resume waits for confirmed neutralization",
                                        "binding_id": binding_id})
            self._require_fresh_capture(state)
            state.state = "observation-only"
            state.human_control = False
            return {"binding_id": binding_id, "state": state.state, "fresh_grant_required": True,
                    "capture_required": True}


    def release(self, binding_id: str) -> dict[str, Any]:
        """Detach one source binding without stopping its backend or environment."""
        state = self._binding_state(binding_id)
        with state.lock:
            was_detached = state.detached
            if not was_detached:
                self._invalidate_binding_grants(state, reason="source-released")
                self._cancel_reserved_operations(binding_id, "source released before dispatch")
            neutral = self._neutralize_backend(state)
            state.human_control = False
            state.inhibited = not neutral["confirmed"]
            if not neutral["confirmed"]:
                state.state = "detached-neutralization-pending"
                return {"binding_id": binding_id, "state": state.state, "detached": False,
                        "neutralization": neutral, "released_generations": [],
                        "backend_closed": False}
            released_generations = []
            for generation in list(state.publications):
                if not self._release_generation(binding_id, generation):
                    state.inhibited = True
                    state.state = "release-pending"
                    return {"binding_id": binding_id, "state": state.state, "detached": False,
                            "neutralization": neutral, "released_generations": released_generations,
                            "remaining_generations": list(state.publications), "backend_closed": False}
                state.publications.pop(generation, None)
                released_generations.append(generation)
            state.detached = True
            state.inhibited = False
            state.state = "detached"
            with self._lock:
                key = (state.record.backend_id, state.record.source_id)
                if self._source_bindings.get(key) == binding_id:
                    self._source_bindings.pop(key, None)
                if self._bindings.get(binding_id) is state:
                    self._bindings.pop(binding_id, None)
            if not was_detached:
                self._append_event({"type": "source_released", "binding_id": binding_id,
                                    "source_epoch": state.record.source_epoch,
                                    "neutralization_confirmed": neutral["confirmed"],
                                    "released_generations": released_generations})
            return {"binding_id": binding_id, "state": state.state, "detached": True,
                    "neutralization": neutral, "released_generations": released_generations,
                    "backend_closed": False}

    def _invalidate_binding_grants(self, state: _BindingState, *, reason: str) -> None:
        with self._watch:
            revoked: list[_Grant] = []
            for grant in self._grants.values():
                if grant.binding_id == state.binding_id and grant.active:
                    grant.active = False
                    revoked.append(grant)
                    if grant.input_domain and self._domain_leases.get(grant.input_domain) == grant.grant_id:
                        self._domain_leases.pop(grant.input_domain, None)
                        self._domain_epochs[grant.input_domain] = self._domain_epochs.get(grant.input_domain, 0) + 1
            for grant in revoked:
                self._grants.pop(grant.grant_id, None)
            self._watch.notify_all()
        for grant in revoked:
            self._append_event({"type": "grant_revoked", "grant_digest": self._grant_digest(grant),
                                "binding_id": state.binding_id, "reason": reason})

    def _cancel_reserved_operations(self, binding_id: str, reason: str) -> None:
        with self._lock:
            pending = [(op_id, row["request_digest"]) for op_id, row in self._operations.items()
                       if row.get("binding_id") == binding_id and row.get("phase") == "reserved"]
        for operation_id, digest in pending:
            outcome = self._not_started(reason)
            try:
                self._append_event({"type": "operation_outcome", "operation_id": operation_id,
                                    "request_digest": digest, "outcome": outcome}, operation_id=operation_id)
            except SurfaceWaitError:
                # It remains durably reserved, therefore restart will settle it
                # as not-started before granting any new authority.
                continue
            with self._lock:
                row = self._operations.get(operation_id)
                if row and row.get("phase") == "reserved":
                    row.update({"phase": "settled", "disposition": "not-started", "delivered_count": 0,
                                "ack_strength": "none", "detail": outcome["detail"]})
            self._release_ledger_capacity(operation_id)

    def _neutralize_backend(self, state: _BindingState) -> dict[str, Any]:
        try:
            raw = state.backend.neutralize(state.backend_binding)
            if not isinstance(raw, Mapping) or not isinstance(raw.get("confirmed"), bool):
                return {"confirmed": False, "detail": "backend returned an invalid neutralization acknowledgment"}
            detail = raw.get("detail")
            if isinstance(detail, str):
                detail = detail[:256]
            else:
                detail = {"status": "detail-withheld"}
            return {"confirmed": raw["confirmed"], "detail": detail}
        except Exception as exc:
            return {"confirmed": False, "detail": self._exception_reason(exc)}

    # ---- durable close and helper functions ----------------------------

    def close(self) -> None:
        with self._watch:
            if self._closed:
                return
            self._closed = True
            self._watch.notify_all()
            bindings = list(self._bindings.values())
            backends = list(self._backends.values())
        if threading.current_thread() is not self._watchdog:
            self._watchdog.join(timeout=2.0)
        for state in bindings:
            with state.lock:
                self._invalidate_binding_grants(state, reason="broker-closed")
                self._neutralize_backend(state)
                for generation in list(state.publications):
                    self._release_generation(state.binding_id, generation)
                state.publications.clear()
        for backend in backends:
            try:
                backend.close()
            except Exception:
                pass

    def _watchdog_loop(self) -> None:
        while True:
            with self._watch:
                if self._closed:
                    return
                now = time.monotonic_ns()
                expired = [grant for grant in self._grants.values()
                           if grant.active and grant.input_domain is not None
                           and now >= min(grant.expires_ns, grant.absolute_deadline_ns, grant.lease_deadline_ns)]
                if not expired:
                    deadlines = [min(grant.expires_ns, grant.absolute_deadline_ns, grant.lease_deadline_ns)
                                 for grant in self._grants.values() if grant.active and grant.input_domain is not None]
                    timeout = None if not deadlines else max(0.001, (min(deadlines) - now) / 1_000_000_000)
                    self._watch.wait(timeout)
                    continue
                for grant in expired:
                    grant.active = False
                    self._grants.pop(grant.grant_id, None)
                    if grant.input_domain and self._domain_leases.get(grant.input_domain) == grant.grant_id:
                        self._domain_leases.pop(grant.input_domain, None)
                        self._domain_epochs[grant.input_domain] = self._domain_epochs.get(grant.input_domain, 0) + 1
            for grant in expired:
                state = self._bindings.get(grant.binding_id)
                self._append_event({"type": "grant_expired", "grant_digest": self._grant_digest(grant),
                                    "binding_id": grant.binding_id, "mission_id": grant.mission_id})
                if state is None or state.detached:
                    continue
                with state.lock:
                    self._cancel_reserved_operations(grant.binding_id, "control lease expired before dispatch")
                    neutral = self._neutralize_backend(state)
                    state.inhibited = not neutral["confirmed"]
                    state.human_control = False
                    state.state = "lease-expired" if neutral["confirmed"] else "neutralization-pending"
                    self._require_fresh_capture(state)
                    self._append_event({"type": "lease_neutralized", "binding_id": grant.binding_id,
                                        "grant_digest": self._grant_digest(grant),
                                        "neutralization_confirmed": neutral["confirmed"]})

    def _release_generation(self, binding_id: str, generation: int) -> bool:
        release = getattr(self._field_owner, "release_surface_publication", None)
        if not callable(release):
            return False
        try:
            result = release(binding_id, generation)
        except Exception:
            return False
        return isinstance(result, Mapping) and result.get("status") == "released"

    def _require_supported_operations(self, state: _BindingState, operations: tuple[str, ...]) -> None:
        if any(operation not in state.record.operations for operation in operations):
            raise SurfaceCapabilityError("requested operation is not supported by the bound source")
        try:
            descriptor = state.backend.describe()
        except Exception as exc:
            raise SurfaceWaitError({"kind": "capability-query", "reason": "backend capability state is unavailable",
                                    "error": self._exception_reason(exc)}) from exc
        capabilities = descriptor.get("capabilities", {}) if isinstance(descriptor, Mapping) else {}
        if not isinstance(capabilities, Mapping):
            raise SurfaceValidationError("backend capabilities must be an object")
        bound_states = state.backend_binding.get("operation_states", {})
        if not isinstance(bound_states, Mapping):
            raise SurfaceValidationError("bound operation_states must be an object")
        for operation in operations:
            capability = bound_states.get(operation)
            if capability is None:
                capability = capabilities.get(operation)
            if capability is None:
                family = operation.split(".", 1)[0]
                capability = capabilities.get(family)
            if capability is None:
                continue
            if isinstance(capability, Mapping):
                status = capability.get("status")
                if status is None and isinstance(capability.get("supported"), bool):
                    status = "supported" if capability["supported"] else "unavailable"
                reason = capability.get("reason")
            else:
                status, reason = capability, None
            if status not in _SUPPORTED_STATES:
                detail = self._optional_text(reason, f"{operation} reason", 256)
                raise SurfaceCapabilityError(f"{operation} is {status or 'unavailable'}"
                                             + (f": {detail}" if detail else ""))


    def _ask_authorizer(self, proposal: Mapping[str, Any]) -> bool | Mapping[str, Any]:
        if self._authorizer is None:
            raise SurfaceAuthorizationError("host authorizer is not configured; authority fails closed")
        safe = json_value(proposal, max_bytes=MAX_METADATA_BYTES, label="host authorization proposal")
        try:
            decision = self._authorizer(safe)
        except Exception as exc:
            raise SurfaceAuthorizationError(f"host authorization failed closed: {self._exception_reason(exc)}") from exc
        if decision is True:
            return True
        if isinstance(decision, Mapping):
            result = json_value(decision, max_bytes=MAX_METADATA_BYTES, label="host authorization decision")
            if result.get("approved") is True:
                return result
        raise SurfaceAuthorizationError("host authorization was denied or did not provide explicit approval")

    def _approved_decision(self, decision: bool | Mapping[str, Any], requested_ops: tuple[str, ...],
                           requested_scope: Mapping[str, Any]) -> tuple[tuple[str, ...], dict[str, Any]]:
        if decision is True:
            return requested_ops, dict(requested_scope)
        if not isinstance(decision, Mapping) or decision.get("approved") is not True:
            raise SurfaceAuthorizationError("host authorizer did not approve the grant")
        approved_ops_value = decision.get("operations", list(requested_ops))
        approved_ops = normalize_operations(approved_ops_value)
        if not approved_ops or not set(approved_ops).issubset(requested_ops):
            raise SurfaceAuthorizationError("host decision attempted to expand grant operations")
        approved_scope_value = decision.get("scope", requested_scope)
        approved_scope = json_value(approved_scope_value, max_bytes=MAX_METADATA_BYTES, label="approved scope")
        if not isinstance(approved_scope, dict) or not self._mapping_subset(approved_scope, requested_scope):
            raise SurfaceAuthorizationError("host decision attempted to expand grant scope")
        # Requested defaults (limits and binding identities) remain pinned even
        # when a host decision narrows other optional metadata.
        for key in ("controller", "source_id", "source_instance", "source_epoch", "geometry_revision",
                    "environment_incarnation", "backend_input_domain", "backend_input_domain_epoch",
                    "input_domain", "max_duration_ns", "heartbeat_timeout_ns", "max_updates",
                    "program_id", "program_generation", "mission_sha256"):
            if key in requested_scope and approved_scope.get(key) != requested_scope[key]:
                raise SurfaceAuthorizationError(f"host decision changed protected grant field: {key}")
        return approved_ops, approved_scope

    def _mapping_subset(self, candidate: Mapping[str, Any], allowed: Mapping[str, Any]) -> bool:
        for key, value in candidate.items():
            if key not in allowed:
                return False
            parent = allowed[key]
            if isinstance(value, Mapping) and isinstance(parent, Mapping):
                if not self._mapping_subset(value, parent):
                    return False
            elif isinstance(value, list) and isinstance(parent, list):
                if not all(item in parent for item in value):
                    return False
            elif value != parent:
                return False
        return True

    def _grant_digest(self, grant: _Grant) -> str:
        data = {"grant_id": grant.grant_id, "mission_id": grant.mission_id, "binding_id": grant.binding_id,
                "operations": sorted(grant.operations), "scope": grant.scope, "expires_ns": grant.expires_ns,
                "controller": grant.controller, "input_domain_epoch": grant.input_domain_epoch}
        return hashlib.sha256(canonical_json(data)).hexdigest()

    def _binding_state(self, binding_id: str) -> _BindingState:
        binding_id = self._required_text(binding_id, "binding_id", 192)
        with self._lock:
            self._assert_open()
            state = self._bindings.get(binding_id)
            if state is None:
                raise SurfaceCapabilityError("binding does not exist")
            return state

    def _backend(self, backend_id: str) -> Any:
        backend = self._backends.get(backend_id)
        if backend is None:
            raise SurfaceCapabilityError(f"backend is not registered: {backend_id}")
        return backend

    def _ensure_attached(self, state: _BindingState) -> None:
        if state.detached or state.state == "detached":
            raise SurfaceCapabilityError("source binding is detached")
        if state.state in {"release-pending", "detached-neutralization-pending"}:
            raise SurfaceWaitError({"kind": "source-release", "reason": "source release must complete before reuse",
                                    "binding_id": state.binding_id, "state": state.state})
        if self._closed:
            raise SurfaceCapabilityError("surface broker is closed")

    def _assert_open(self) -> None:
        if self._closed:
            raise SurfaceCapabilityError("surface broker is closed")

    def _input_domain(self, binding: SurfaceBinding) -> str:
        return binding.input_domain or binding.environment_incarnation

    def _is_control_operation(self, operation: str) -> bool:
        return operation.startswith(_CONTROL_PREFIXES) or operation in _MEDIA_CONTROL_OPERATIONS

    def _requires_input_lease(self, operation: str) -> bool:
        return operation.startswith(_CONTROL_PREFIXES)

    def _required_text(self, value: Any, label: str, maximum: int = MAX_TEXT) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
            raise SurfaceValidationError(f"{label} must be bounded nonempty text")
        return value

    def _optional_text(self, value: Any, label: str, maximum: int = MAX_TEXT) -> str | None:
        if value is None:
            return None
        return self._required_text(value, label, maximum)

    def _positive_int(self, value: Any, label: str) -> int:
        return self._bounded_int(value, label, (1 << 63) - 1, minimum=1)

    def _optional_uint(self, value: Any, label: str) -> int | None:
        if value is None:
            return None
        return self._bounded_int(value, label, (1 << 63) - 1)

    def _bounded_int(self, value: Any, label: str, maximum: int, *, minimum: int = 0) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise SurfaceValidationError(f"{label} must be an integer in {minimum}..{maximum}")
        return value

    def _required_digest(self, value: Any) -> str:
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise SurfaceValidationError("ledger digest is invalid")
        return value

    def _exception_reason(self, exc: BaseException) -> str:
        # Exception text may echo user text, pixels, URLs, or credentials.
        return type(exc).__name__[:128]
