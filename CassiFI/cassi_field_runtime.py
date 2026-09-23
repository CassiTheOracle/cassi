"""Exact packed residency and fenced candidate transport for field computers.

This module is deliberately a thin physical adapter.  It owns packed copies and
private candidate epochs; it never publishes a :class:`ComputerState` or makes
an adaptive scheduling choice.  The field owner remains the sole publisher.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import secrets
import time
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_computer import ComputerState, PagedComputerState
from cassi_field_runtime_native import (
    NativeFieldRuntimeClient,
    NativeFieldRuntimeError,
    NativeWordOperation,
)


PACKED_ABI_SCHEMA = "cassifi.field-runtime-packed.v1"
ATTACHMENT_SCHEMA = "cassifi.field-runtime-attachment.v1"
CANDIDATE_SCHEMA = "cassifi.field-runtime-candidate.v1"
PUBLICATION_SCHEMA = "cassifi.field-runtime-publication.v1"
DEFAULT_PAGE_BYTES = 64 * 1024
DEFAULT_EPOCH_TRANSITIONS = 64
DEFAULT_COMMAND_DISPATCHES = 32


class FieldRuntimeError(ValueError):
    """Invalid transport, residency, or fenced candidate operation."""


class UnsupportedImageEncoding(FieldRuntimeError):
    """The canonical field image cannot be represented by the packed ABI."""


class StaleRuntimeGeneration(FieldRuntimeError):
    """A request names an earlier service generation."""


class StalePublicationFence(FieldRuntimeError):
    """A candidate cannot publish through the current owner fence."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FieldRuntimeError("value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hex_digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FieldRuntimeError(f"{label} must be a lowercase sha256 digest")
    return value


def _positive_int(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FieldRuntimeError(f"{label} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise FieldRuntimeError(f"{label} must be {qualifier}")
    return value


def _packed_metadata(
    *,
    profile_sha256: str,
    state_sha256: str,
    catalog_sha256: str,
    shape: Sequence[int],
    word_count: int,
    page_bytes: int,
    page_sha256: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": PACKED_ABI_SCHEMA,
        "layout": "little-endian-u32-words",
        "profile_sha256": profile_sha256,
        "state_sha256": state_sha256,
        "catalog_sha256": catalog_sha256,
        "shape": [int(part) for part in shape],
        "word_count": word_count,
        "page_bytes": page_bytes,
        "page_sha256": list(page_sha256),
    }


@dataclass(frozen=True, slots=True)
class PackedFieldImage:
    """Immutable packed copy of one canonical float64/u32 field image."""

    profile_sha256: str
    state_sha256: str
    catalog_sha256: str
    shape: tuple[int, ...]
    payload: bytes = field(repr=False)
    page_bytes: int = DEFAULT_PAGE_BYTES
    page_sha256: tuple[str, ...] = ()
    transport_sha256: str = ""

    def __post_init__(self) -> None:
        _hex_digest(self.profile_sha256, "profile_sha256")
        _hex_digest(self.state_sha256, "state_sha256")
        _hex_digest(self.catalog_sha256, "catalog_sha256")
        if not self.shape or any(
            isinstance(part, bool) or not isinstance(part, int) or part < 1
            for part in self.shape
        ):
            raise FieldRuntimeError("packed shape must contain positive dimensions")
        if not isinstance(self.payload, bytes):
            raise FieldRuntimeError("packed payload must be immutable bytes")
        word_count = math.prod(self.shape)
        if len(self.payload) != 4 * word_count:
            raise FieldRuntimeError("packed payload size does not match shape")
        _positive_int(self.page_bytes, "page_bytes")
        expected_pages = tuple(
            hashlib.sha256(self.payload[start : start + self.page_bytes]).hexdigest()
            for start in range(0, len(self.payload), self.page_bytes)
        )
        if not expected_pages:
            expected_pages = (hashlib.sha256(b"").hexdigest(),)
        if self.page_sha256 and tuple(self.page_sha256) != expected_pages:
            raise FieldRuntimeError("packed page manifest mismatch")
        object.__setattr__(self, "page_sha256", expected_pages)
        metadata = _packed_metadata(
            profile_sha256=self.profile_sha256,
            state_sha256=self.state_sha256,
            catalog_sha256=self.catalog_sha256,
            shape=self.shape,
            word_count=word_count,
            page_bytes=self.page_bytes,
            page_sha256=expected_pages,
        )
        digest = hashlib.sha256(_canonical(metadata) + b"\0" + self.payload).hexdigest()
        if self.transport_sha256 and self.transport_sha256 != digest:
            raise FieldRuntimeError("packed transport digest mismatch")
        object.__setattr__(self, "transport_sha256", digest)

    @property
    def word_count(self) -> int:
        return math.prod(self.shape)

    def descriptor(self) -> dict[str, Any]:
        metadata = _packed_metadata(
            profile_sha256=self.profile_sha256,
            state_sha256=self.state_sha256,
            catalog_sha256=self.catalog_sha256,
            shape=self.shape,
            word_count=self.word_count,
            page_bytes=self.page_bytes,
            page_sha256=self.page_sha256,
        )
        metadata["transport_sha256"] = self.transport_sha256
        metadata["payload_bytes"] = len(self.payload)
        return metadata


def pack_field_image(
    field_image: np.ndarray,
    *,
    profile_sha256: str,
    state_sha256: str,
    catalog_sha256: str,
    page_bytes: int = DEFAULT_PAGE_BYTES,
) -> PackedFieldImage:
    """Pack a canonical finite integral-u32 float64 image without normalization."""

    if not isinstance(field_image, np.ndarray) or field_image.dtype != np.float64:
        raise FieldRuntimeError("field image must be a float64 numpy tensor")
    if field_image.ndim < 1 or any(part < 1 for part in field_image.shape):
        raise FieldRuntimeError("field image shape is invalid")
    if not np.all(np.isfinite(field_image)):
        raise UnsupportedImageEncoding("unsupported-image-encoding: nonfinite word")
    if np.any(field_image < 0.0) or np.any(field_image > float(0xFFFFFFFF)):
        raise UnsupportedImageEncoding("unsupported-image-encoding: word outside u32")
    if not np.all(field_image == np.floor(field_image)):
        raise UnsupportedImageEncoding("unsupported-image-encoding: fractional word")
    if np.any((field_image == 0.0) & np.signbit(field_image)):
        raise UnsupportedImageEncoding("unsupported-image-encoding: negative zero")
    words = np.asarray(field_image, dtype="<u4", order="C")
    return PackedFieldImage(
        profile_sha256=_hex_digest(profile_sha256, "profile_sha256"),
        state_sha256=_hex_digest(state_sha256, "state_sha256"),
        catalog_sha256=_hex_digest(catalog_sha256, "catalog_sha256"),
        shape=tuple(int(part) for part in field_image.shape),
        payload=words.tobytes(order="C"),
        page_bytes=_positive_int(page_bytes, "page_bytes"),
    )


def pack_computer_state(
    state: ComputerState | PagedComputerState,
    *,
    state_sha256: str,
    catalog_sha256: str,
    page_bytes: int = DEFAULT_PAGE_BYTES,
) -> PackedFieldImage:
    # A paged state materialises its whole logical image for this declared read;
    # the packed transport is page-addressed either way, so both forms pack the
    # same bytes.
    if not isinstance(state, (ComputerState, PagedComputerState)):
        raise FieldRuntimeError("state must be a ComputerState or PagedComputerState")
    return pack_field_image(
        state.field,
        profile_sha256=state.profile_sha256,
        state_sha256=state_sha256,
        catalog_sha256=catalog_sha256,
        page_bytes=page_bytes,
    )


def unpack_field_image(image: PackedFieldImage) -> np.ndarray:
    """Recover the exact canonical float64 bytes admitted by :func:`pack_field_image`."""

    if not isinstance(image, PackedFieldImage):
        raise FieldRuntimeError("packed image required")
    # Reconstructing any admitted word as binary64 is exact because every u32 is
    # representable.  Negative zero was rejected, so this recovers identical bytes.
    words = np.frombuffer(image.payload, dtype="<u4")
    result = words.astype(np.float64).reshape(image.shape)
    if result.tobytes(order="C") != words.astype(np.float64).reshape(image.shape).tobytes(order="C"):
        raise FieldRuntimeError("packed image reconstruction failed")
    return result


@dataclass(frozen=True, slots=True)
class ResidentAttachment:
    owner_id: str
    service_generation: int
    fence: int
    image: PackedFieldImage
    placement: str = "native-cpu"

    def descriptor(self) -> dict[str, Any]:
        return {
            "schema": ATTACHMENT_SCHEMA,
            "owner_id": self.owner_id,
            "service_generation": self.service_generation,
            "fence": self.fence,
            "placement": self.placement,
            "image": self.image.descriptor(),
        }


@dataclass(frozen=True, slots=True)
class CandidateEpoch:
    candidate_id: str
    owner_id: str
    service_generation: int
    fence: int
    lease_id: str
    predecessor_state_sha256: str
    image: PackedFieldImage
    logical_transitions: int
    dispatches: int
    events: tuple[Mapping[str, Any], ...]
    errors: tuple[Mapping[str, Any], ...]
    placement: str
    result_sha256: str

    def descriptor(self) -> dict[str, Any]:
        return {
            "schema": CANDIDATE_SCHEMA,
            "candidate_id": self.candidate_id,
            "owner_id": self.owner_id,
            "service_generation": self.service_generation,
            "fence": self.fence,
            "lease_id": self.lease_id,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "successor_state_sha256": self.image.state_sha256,
            "logical_transitions": self.logical_transitions,
            "dispatches": self.dispatches,
            "events": [dict(row) for row in self.events],
            "errors": [dict(row) for row in self.errors],
            "placement": self.placement,
            "result_sha256": self.result_sha256,
            "transport_sha256": self.image.transport_sha256,
        }


@dataclass(slots=True)
class _CandidateReservation:
    owner_id: str
    service_generation: int
    fence: int
    lease_id: str
    predecessor_state_sha256: str
    placement: str


class ResidentFieldRuntime:
    """Owner-separated packed residency with private, generation-fenced epochs."""

    def __init__(
        self,
        *,
        instance_id: str | None = None,
        launch_nonce: str | None = None,
        page_bytes: int = DEFAULT_PAGE_BYTES,
        max_epoch_transitions: int = DEFAULT_EPOCH_TRANSITIONS,
        max_command_dispatches: int = DEFAULT_COMMAND_DISPATCHES,
        native_client: NativeFieldRuntimeClient | None = None,
    ) -> None:
        if native_client is not None:
            if instance_id is not None and instance_id != native_client.instance_id:
                raise FieldRuntimeError("native client instance identity disagrees")
            if launch_nonce is not None and launch_nonce != native_client.launch_nonce:
                raise FieldRuntimeError("native client launch nonce disagrees")
            instance_id = native_client.instance_id
            launch_nonce = native_client.launch_nonce
        self.instance_id = instance_id or secrets.token_hex(16)
        self.launch_nonce = launch_nonce or secrets.token_hex(32)
        if not self.instance_id or not self.launch_nonce:
            raise FieldRuntimeError("runtime identity and nonce must be nonempty")
        self.page_bytes = _positive_int(page_bytes, "page_bytes")
        self.max_epoch_transitions = _positive_int(
            max_epoch_transitions, "max_epoch_transitions"
        )
        self.max_command_dispatches = _positive_int(
            max_command_dispatches, "max_command_dispatches"
        )
        self._native_client = native_client
        self.service_generation = (
            native_client.service_generation if native_client is not None else 1
        )
        self._attachments: dict[str, ResidentAttachment] = {}
        self._reservations: dict[str, _CandidateReservation] = {}
        self._owner_candidate: dict[str, str] = {}
        self._settled: dict[str, CandidateEpoch] = {}
        self._lost_generations: set[int] = set()

    def _attachment(self, owner_id: str) -> ResidentAttachment:
        attachment = self._attachments.get(owner_id)
        if attachment is None:
            raise FieldRuntimeError("owner is not resident")
        if attachment.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("resident attachment generation is stale")
        return attachment

    def attach(
        self,
        owner_id: str,
        state: ComputerState | PagedComputerState,
        *,
        state_sha256: str,
        catalog_sha256: str,
        fence: int,
        placement: str = "native-cpu",
    ) -> ResidentAttachment:
        if not isinstance(owner_id, str) or not owner_id:
            raise FieldRuntimeError("owner_id must be nonempty")
        if placement not in {"native-cpu", "vulkan"}:
            raise FieldRuntimeError("placement must be native-cpu or vulkan")
        fence = _positive_int(fence, "fence", allow_zero=True)
        current = self._attachments.get(owner_id)
        if current is not None and fence < current.fence:
            raise StalePublicationFence("attachment fence moved backwards")
        image = pack_computer_state(
            state,
            state_sha256=state_sha256,
            catalog_sha256=catalog_sha256,
            page_bytes=self.page_bytes,
        )
        if self._native_client is not None:
            native_attachment = self._native_client.attach(
                owner_id,
                state.field,
                profile_sha256=state.profile_sha256,
                state_sha256=state_sha256,
                catalog_sha256=catalog_sha256,
                fence=fence,
            )
            if native_attachment["packed_sha256"] != hashlib.sha256(
                image.payload
            ).hexdigest():
                raise FieldRuntimeError("native attachment packed image disagrees")
        attachment = ResidentAttachment(
            owner_id=owner_id,
            service_generation=self.service_generation,
            fence=fence,
            image=image,
            placement=placement,
        )
        self._attachments[owner_id] = attachment
        return attachment

    def begin_candidate(
        self,
        owner_id: str,
        *,
        predecessor_state_sha256: str,
        fence: int,
        lease_id: str,
        placement: str | None = None,
    ) -> str:
        attachment = self._attachment(owner_id)
        _hex_digest(predecessor_state_sha256, "predecessor_state_sha256")
        if predecessor_state_sha256 != attachment.image.state_sha256:
            raise StalePublicationFence("candidate predecessor is not published state")
        if fence != attachment.fence:
            raise StalePublicationFence("candidate fence is stale")
        if owner_id in self._owner_candidate:
            raise FieldRuntimeError("owner already has an in-flight candidate")
        if not isinstance(lease_id, str) or not lease_id:
            raise FieldRuntimeError("lease_id must be nonempty")
        actual_placement = placement or attachment.placement
        if actual_placement not in {"native-cpu", "vulkan"}:
            raise FieldRuntimeError("candidate placement is invalid")
        if self._native_client is None:
            candidate_id = secrets.token_hex(16)
        else:
            candidate_id = self._native_client.begin_candidate(
                owner_id,
                predecessor_state_sha256,
                fence=fence,
                lease_id=lease_id,
                placement=actual_placement,
            )
        self._reservations[candidate_id] = _CandidateReservation(
            owner_id=owner_id,
            service_generation=self.service_generation,
            fence=fence,
            lease_id=lease_id,
            predecessor_state_sha256=predecessor_state_sha256,
            placement=actual_placement,
        )
        self._owner_candidate[owner_id] = candidate_id
        return candidate_id

    def _settle_native_image(
        self,
        candidate_id: str,
        reservation: _CandidateReservation,
        image: PackedFieldImage,
        state: ComputerState | PagedComputerState,
    ) -> None:
        client = self._native_client
        if client is None:
            return
        predecessor = self._attachment(reservation.owner_id).image
        if predecessor.shape != image.shape:
            raise FieldRuntimeError("native candidate changed packed image shape")
        old_words = np.frombuffer(predecessor.payload, dtype="<u4")
        new_words = np.frombuffer(image.payload, dtype="<u4")
        changed = np.flatnonzero(old_words != new_words)
        if len(changed) > 65_536:
            raise FieldRuntimeError(
                "native candidate word delta exceeds epoch operation limit"
            )
        operations = [
            NativeWordOperation(
                "compare-set",
                int(index),
                int(old_words[index]),
                int(new_words[index]),
            )
            for index in changed
        ]
        for start in range(0, len(operations), 16_384):
            client.apply_word_operations(
                candidate_id, operations[start : start + 16_384]
            )
        exported, metadata = client.export_candidate(candidate_id, image.shape)
        if metadata["predecessor_state_sha256"] != (
            reservation.predecessor_state_sha256
        ):
            raise FieldRuntimeError("native candidate predecessor disagrees")
        if exported.tobytes(order="C") != state.field.tobytes(order="C"):
            raise FieldRuntimeError("native candidate field image disagrees")

    def settle_candidate(
        self,
        candidate_id: str,
        state: ComputerState | PagedComputerState,
        *,
        state_sha256: str,
        catalog_sha256: str,
        logical_transitions: int,
        dispatches: int,
        events: Sequence[Mapping[str, Any]] = (),
        errors: Sequence[Mapping[str, Any]] = (),
    ) -> CandidateEpoch:
        previous = self._settled.get(candidate_id)
        if previous is not None:
            if previous.image.state_sha256 != state_sha256:
                raise FieldRuntimeError("duplicate candidate result disagrees")
            return previous
        reservation = self._reservations.get(candidate_id)
        if reservation is None:
            raise FieldRuntimeError("candidate reservation is unknown")
        if reservation.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("candidate service generation is stale")
        transitions = _positive_int(
            logical_transitions, "logical_transitions", allow_zero=True
        )
        dispatch_count = _positive_int(dispatches, "dispatches", allow_zero=True)
        if transitions > self.max_epoch_transitions:
            raise FieldRuntimeError("candidate exceeds epoch transition limit")
        if dispatch_count > self.max_command_dispatches:
            raise FieldRuntimeError("candidate exceeds command dispatch limit")
        image = pack_computer_state(
            state,
            state_sha256=state_sha256,
            catalog_sha256=catalog_sha256,
            page_bytes=self.page_bytes,
        )
        self._settle_native_image(candidate_id, reservation, image, state)
        event_rows = tuple(dict(row) for row in events)
        error_rows = tuple(dict(row) for row in errors)
        body = {
            "owner_id": reservation.owner_id,
            "service_generation": reservation.service_generation,
            "fence": reservation.fence,
            "lease_id": reservation.lease_id,
            "predecessor_state_sha256": reservation.predecessor_state_sha256,
            "successor_transport_sha256": image.transport_sha256,
            "logical_transitions": transitions,
            "dispatches": dispatch_count,
            "events": event_rows,
            "errors": error_rows,
            "placement": reservation.placement,
        }
        candidate = CandidateEpoch(
            candidate_id=candidate_id,
            owner_id=reservation.owner_id,
            service_generation=reservation.service_generation,
            fence=reservation.fence,
            lease_id=reservation.lease_id,
            predecessor_state_sha256=reservation.predecessor_state_sha256,
            image=image,
            logical_transitions=transitions,
            dispatches=dispatch_count,
            events=event_rows,
            errors=error_rows,
            placement=reservation.placement,
            result_sha256=_digest(body),
        )
        self._settled[candidate_id] = candidate
        return candidate

    def validate_for_publication(
        self,
        candidate_id: str,
        *,
        owner_state_sha256: str,
        fence: int,
        lease_id: str,
    ) -> CandidateEpoch:
        candidate = self._settled.get(candidate_id)
        if candidate is None:
            raise FieldRuntimeError("candidate has not settled")
        attachment = self._attachment(candidate.owner_id)
        if candidate.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("candidate service generation is stale")
        if candidate.fence != fence or attachment.fence != fence:
            raise StalePublicationFence("candidate publication fence is stale")
        if candidate.lease_id != lease_id:
            raise StalePublicationFence("candidate lease is stale")
        if candidate.predecessor_state_sha256 != owner_state_sha256:
            raise StalePublicationFence("owner state changed before publication")
        if attachment.image.state_sha256 != owner_state_sha256:
            raise StalePublicationFence("resident predecessor changed")
        return candidate

    def confirm_publication(
        self,
        candidate_id: str,
        *,
        owner_state_sha256: str,
        fence: int,
        lease_id: str,
    ) -> Mapping[str, Any]:
        """Update the disposable cache only after the owner published the state."""

        candidate = self.validate_for_publication(
            candidate_id,
            owner_state_sha256=candidate_predecessor(self, candidate_id),
            fence=fence,
            lease_id=lease_id,
        )
        if owner_state_sha256 != candidate.image.state_sha256:
            raise StalePublicationFence("owner did not publish candidate successor")
        if self._native_client is not None:
            native_confirmation = self._native_client.confirm_cache(
                candidate_id,
                candidate.predecessor_state_sha256,
                owner_state_sha256,
                fence=fence,
                lease_id=lease_id,
            )
            if (
                native_confirmation["state_sha256"] != owner_state_sha256
                or native_confirmation["fence"] != fence + 1
            ):
                raise FieldRuntimeError("native cache confirmation disagrees")
        self._attachments[candidate.owner_id] = ResidentAttachment(
            owner_id=candidate.owner_id,
            service_generation=self.service_generation,
            fence=fence + 1,
            image=candidate.image,
            placement=candidate.placement,
        )
        self._retire_candidate(candidate_id)
        return {
            "schema": PUBLICATION_SCHEMA,
            "owner_id": candidate.owner_id,
            "candidate_id": candidate_id,
            "predecessor_state_sha256": candidate.predecessor_state_sha256,
            "state_sha256": owner_state_sha256,
            "service_generation": self.service_generation,
            "fence": fence + 1,
            "placement": candidate.placement,
            "logical_transitions": candidate.logical_transitions,
            "dispatches": candidate.dispatches,
            "result_sha256": candidate.result_sha256,
        }

    def cancel_candidate(self, candidate_id: str) -> Mapping[str, Any]:
        reservation = self._reservations.get(candidate_id)
        candidate = self._settled.get(candidate_id)
        if reservation is None and candidate is None:
            return {"candidate_id": candidate_id, "status": "already-retired"}
        owner_id = reservation.owner_id if reservation is not None else candidate.owner_id
        if self._native_client is not None:
            self._native_client.discard_candidate(candidate_id)
        self._retire_candidate(candidate_id)
        return {
            "candidate_id": candidate_id,
            "owner_id": owner_id,
            "status": "cancelled",
            "service_generation": self.service_generation,
        }

    def _retire_candidate(self, candidate_id: str) -> None:
        reservation = self._reservations.pop(candidate_id, None)
        candidate = self._settled.pop(candidate_id, None)
        owner_id = reservation.owner_id if reservation is not None else (
            candidate.owner_id if candidate is not None else None
        )
        if owner_id is not None and self._owner_candidate.get(owner_id) == candidate_id:
            del self._owner_candidate[owner_id]

    def detach(self, owner_id: str) -> None:
        candidate_id = self._owner_candidate.get(owner_id)
        if candidate_id is not None:
            self.cancel_candidate(candidate_id)
        if self._native_client is not None:
            self._native_client.detach(owner_id)
        self._attachments.pop(owner_id, None)

    def register_model(
        self,
        source_sha256: str,
        path: str,
        *,
        context_size: int = 32_768,
        gpu_layers: int = -1,
    ) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.register_model(
            source_sha256,
            path,
            context_size=context_size,
            gpu_layers=gpu_layers,
        )

    def step_model(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        *,
        sampler_mode: str,
        temperature: float,
        top_k: int,
        draw: float,
    ) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.step_model(
            task_id,
            source_sha256,
            tokens,
            sampler_mode=sampler_mode,
            temperature=temperature,
            top_k=top_k,
            draw=draw,
        )

    def drop_model_task(self, task_id: str) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.drop_model_task(task_id)

    def recover_native(
        self, native_client: NativeFieldRuntimeClient
    ) -> Mapping[str, Any]:
        """Replace disposable native state after loss; owner checkpoints survive."""

        if not isinstance(native_client, NativeFieldRuntimeClient):
            raise FieldRuntimeError("recovery requires a native runtime client")
        lost = self.service_generation
        affected = tuple(sorted(self._attachments))
        prior = self._native_client
        if prior is not None and prior is not native_client:
            try:
                prior.shutdown()
            except NativeFieldRuntimeError:
                pass
        self._lost_generations.add(lost)
        self.service_generation = lost + 1
        self._attachments.clear()
        self._reservations.clear()
        self._owner_candidate.clear()
        self._settled.clear()
        self._native_client = native_client
        self.instance_id = native_client.instance_id
        self.launch_nonce = native_client.launch_nonce
        return {
            "status": "native-recovered",
            "lost_generation": lost,
            "service_generation": self.service_generation,
            "native_service_generation": native_client.service_generation,
            "affected_owner_ids": list(affected),
        }

    def shutdown(self) -> Mapping[str, Any]:
        """Release disposable service resources without touching owner state."""

        affected = tuple(sorted(self._attachments))
        for candidate_id in tuple(self._reservations):
            self.cancel_candidate(candidate_id)
        client = self._native_client
        if client is not None:
            for owner_id in tuple(self._attachments):
                client.detach(owner_id)
            client.shutdown()
            self._native_client = None
        self._attachments.clear()
        self._reservations.clear()
        self._owner_candidate.clear()
        self._settled.clear()
        return {
            "status": "shutdown",
            "service_generation": self.service_generation,
            "affected_owner_ids": list(affected),
        }

    def lose_device(self) -> Mapping[str, Any]:
        """Invalidate every physical resource while preserving no owner authority."""

        lost = self.service_generation
        affected = tuple(sorted(self._attachments))
        self._lost_generations.add(lost)
        if self._native_client is not None:
            self._native_client.shutdown()
            self._native_client = None
        self.service_generation += 1
        self._attachments.clear()
        self._reservations.clear()
        self._owner_candidate.clear()
        self._settled.clear()
        return {
            "status": "device-lost",
            "lost_generation": lost,
            "service_generation": self.service_generation,
            "affected_owner_ids": list(affected),
            "recovery": "reattach-canonical-checkpoint",
        }

    def status(self) -> Mapping[str, Any]:
        native_status = (
            None if self._native_client is None else self._native_client.status()
        )
        return {
            "schema": "cassifi.field-runtime-status.v1",
            "instance_id": self.instance_id,
            "service_generation": self.service_generation,
            "page_bytes": self.page_bytes,
            "max_epoch_transitions": self.max_epoch_transitions,
            "max_command_dispatches": self.max_command_dispatches,
            "resident_owner_ids": sorted(self._attachments),
            "in_flight_candidate_ids": sorted(self._reservations),
            "lost_generations": sorted(self._lost_generations),
            "native_service": native_status,
        }


def candidate_predecessor(runtime: ResidentFieldRuntime, candidate_id: str) -> str:
    candidate = runtime._settled.get(candidate_id)
    if candidate is None:
        raise FieldRuntimeError("candidate has not settled")
    return candidate.predecessor_state_sha256


__all__ = [
    "ATTACHMENT_SCHEMA",
    "CANDIDATE_SCHEMA",
    "DEFAULT_COMMAND_DISPATCHES",
    "DEFAULT_EPOCH_TRANSITIONS",
    "DEFAULT_PAGE_BYTES",
    "FieldRuntimeError",
    "PACKED_ABI_SCHEMA",
    "PUBLICATION_SCHEMA",
    "NativeFieldRuntimeClient",
    "NativeFieldRuntimeError",
    "NativeWordOperation",
    "CandidateEpoch",
    "PackedFieldImage",
    "ResidentAttachment",
    "ResidentFieldRuntime",
    "StalePublicationFence",
    "StaleRuntimeGeneration",
    "UnsupportedImageEncoding",
    "pack_computer_state",
    "pack_field_image",
    "unpack_field_image",
]
