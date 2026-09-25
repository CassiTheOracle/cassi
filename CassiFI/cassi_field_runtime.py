"""Exact packed residency and fenced candidate transport for field computers.

This module is deliberately a thin physical adapter.  It owns packed copies and
private candidate epochs; it never publishes a :class:`ComputerState` or makes
an adaptive scheduling choice.  The field owner remains the sole publisher.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import secrets
import time
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from cassi_field_computer import ComputerState, PagedComputerState
from cassi_field_regions import PERSISTENCE_PAGE_WORDS
from cassi_field_runtime_native import (
    NativeFieldRuntimeClient,
    NativeFieldRuntimeError,
    NativeGroupRow,
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
    if not isinstance(state, (ComputerState, PagedComputerState)):
        raise FieldRuntimeError("state must be a ComputerState or PagedComputerState")
    if isinstance(state, ComputerState):
        return pack_field_image(
            state.field,
            profile_sha256=state.profile_sha256,
            state_sha256=state_sha256,
            catalog_sha256=catalog_sha256,
            page_bytes=page_bytes,
        )
    total_words = state.image.profile.total_words
    packed = bytearray(total_words * 4)
    for page_index in range(state.image.page_count):
        page = state.image.page(page_index)
        if (
            not np.all(np.isfinite(page))
            or np.any(page < 0.0)
            or np.any(page > float(0xFFFFFFFF))
            or not np.all(page == np.floor(page))
            or np.any((page == 0.0) & np.signbit(page))
        ):
            raise UnsupportedImageEncoding("unsupported-image-encoding: paged u32 word")
        start = page_index * PERSISTENCE_PAGE_WORDS * 4
        payload = np.asarray(page, dtype="<u4", order="C").tobytes(order="C")
        packed[start : start + len(payload)] = payload
    return PackedFieldImage(
        profile_sha256=state.profile_sha256,
        state_sha256=_hex_digest(state_sha256, "state_sha256"),
        catalog_sha256=_hex_digest(catalog_sha256, "catalog_sha256"),
        shape=(1, total_words, 1),
        payload=bytes(packed),
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
    device_index: int | None = None
    device_identity: str | None = None

    def descriptor(self) -> dict[str, Any]:
        return {
            "schema": ATTACHMENT_SCHEMA,
            "owner_id": self.owner_id,
            "service_generation": self.service_generation,
            "fence": self.fence,
            "placement": self.placement,
            "device_index": self.device_index,
            "device_identity": self.device_identity,
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
    device_index: int | None = None
    device_identity: str | None = None

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
            "device_index": self.device_index,
            "device_identity": self.device_identity,
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
    device_index: int | None = None
    device_identity: str | None = None


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
        self._device_report: dict[str, Any] | None = None

    def device_report(self) -> Mapping[str, Any] | None:
        """Structured per-device report for the resident native service.

        ``None`` means no device evidence (no native client or a native
        build without device fields); unknown budget or identity values
        inside a report stay explicit ``None``.  Never a cross-API guess.
        """

        client = self._native_client
        if client is None:
            return None
        if self._device_report is None:
            self._device_report = client.device_report(refresh=True)
        return self._device_report

    def probe_vulkan(self) -> Mapping[str, Any]:
        """Forward an exact native Vulkan probe, including native memory evidence."""

        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native field runtime is not attached")
        probe = getattr(client, "probe_vulkan", None)
        if not callable(probe):
            raise FieldRuntimeError(
                "native field runtime does not expose Vulkan probing"
            )
        report = probe()
        if not isinstance(report, Mapping):
            raise FieldRuntimeError("native Vulkan probe returned an invalid report")
        device_report = report.get("device_report")
        if isinstance(device_report, Mapping):
            self._device_report = device_report
        return report

    def _device_identity(
        self, report: Mapping[str, Any] | None
    ) -> tuple[int | None, str | None]:
        if not isinstance(report, Mapping):
            return None, None
        index = report.get("device_index")
        identity = report.get("device_identity")
        return (
            index if isinstance(index, int) and not isinstance(index, bool) else None,
            identity if isinstance(identity, str) and identity else None,
        )

    def _verify_candidate_device(self, reservation: _CandidateReservation) -> None:
        """Refuse continuation or publication on a different physical device.

        Device evidence is re-queried from the resident service: a cached
        report captured at candidate begin would always agree with the
        reservation and could never detect a device change.
        """

        client = self._native_client
        if client is None:
            return
        report = client.device_report(refresh=True)
        self._device_report = report
        if not isinstance(report, Mapping):
            return
        index, identity = self._device_identity(report)
        if (
            reservation.device_index is not None
            and index is not None
            and index != reservation.device_index
        ):
            raise FieldRuntimeError(
                "wrong-device operation refused: candidate was placed on device "
                f"{reservation.device_index} but the resident service now reports "
                f"device {index}"
            )
        if (
            reservation.device_identity is not None
            and identity is not None
            and identity != reservation.device_identity
        ):
            raise FieldRuntimeError(
                "wrong-device operation refused: candidate was placed on device "
                f"{reservation.device_identity!r} but the resident service now "
                f"reports device {identity!r}"
            )

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
        if (
            current is not None
            and current.fence == fence
            and current.service_generation == self.service_generation
            and owner_id not in self._owner_candidate
            and current.image.state_sha256 == state_sha256
            and current.image.catalog_sha256 == catalog_sha256
            and current.image.profile_sha256 == state.profile_sha256
            and current.image.page_bytes == self.page_bytes
        ):
            # The service already holds this exact published image at this
            # fence (attached, or promoted by confirm_publication), so a
            # refresh keeps it resident and only relabels the placement.
            if current.placement != placement:
                current = replace(current, placement=placement)
                self._attachments[owner_id] = current
            return current
        image = pack_computer_state(
            state,
            state_sha256=state_sha256,
            catalog_sha256=catalog_sha256,
            page_bytes=self.page_bytes,
        )
        device_index, device_identity = self._device_identity(
            self.device_report() if self._native_client is not None else None
        )
        if self._native_client is not None:
            if isinstance(state, PagedComputerState):
                native_attachment = self._native_client.attach_packed(
                    owner_id,
                    image.shape,
                    image.payload,
                    profile_sha256=state.profile_sha256,
                    state_sha256=state_sha256,
                    catalog_sha256=catalog_sha256,
                    fence=fence,
                )
            else:
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
            device_index=device_index,
            device_identity=device_identity,
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
        requested_placement = placement or attachment.placement
        if requested_placement not in {
            "native-cpu",
            "native-cpu-continuation",
            "vulkan",
        }:
            raise FieldRuntimeError("candidate placement is invalid")
        wire_placement = (
            "native-cpu"
            if requested_placement == "native-cpu-continuation"
            else requested_placement
        )
        if self._native_client is None:
            candidate_id = secrets.token_hex(16)
            actual_placement = requested_placement
        else:
            candidate_id = self._native_client.begin_candidate(
                owner_id,
                predecessor_state_sha256,
                fence=fence,
                lease_id=lease_id,
                placement=wire_placement,
            )
            actual_placement = self._native_client.candidate_placement(candidate_id)
        if actual_placement not in {
            "native-cpu",
            "native-cpu-continuation",
            "vulkan",
        }:
            raise FieldRuntimeError("native candidate returned an unknown placement")
        device_index, device_identity = self._device_identity(
            self.device_report() if self._native_client is not None else None
        )
        self._reservations[candidate_id] = _CandidateReservation(
            owner_id=owner_id,
            service_generation=self.service_generation,
            fence=fence,
            lease_id=lease_id,
            predecessor_state_sha256=predecessor_state_sha256,
            placement=actual_placement,
            device_index=device_index,
            device_identity=device_identity,
        )
        self._owner_candidate[owner_id] = candidate_id
        return candidate_id

    def _settle_native_image(
        self,
        candidate_id: str,
        reservation: _CandidateReservation,
        image: PackedFieldImage,
        changed_pages: Sequence[int] | None,
    ) -> None:
        client = self._native_client
        if client is None:
            return
        predecessor = self._attachment(reservation.owner_id).image
        if predecessor.shape != image.shape:
            raise FieldRuntimeError("native candidate changed packed image shape")
        old_words = np.frombuffer(predecessor.payload, dtype="<u4")
        new_words = np.frombuffer(image.payload, dtype="<u4")
        if changed_pages is None:
            pages = range((len(old_words) + PERSISTENCE_PAGE_WORDS - 1) // PERSISTENCE_PAGE_WORDS)
        else:
            pages = tuple(changed_pages)
            if any(
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                or index * PERSISTENCE_PAGE_WORDS >= len(old_words)
                for index in pages
            ) or tuple(sorted(set(pages))) != pages:
                raise FieldRuntimeError("changed page indices must be unique, sorted, and in range")
        words_per_page = PERSISTENCE_PAGE_WORDS

        for page in pages:
            start = page * words_per_page
            stop = min(len(old_words), start + words_per_page)
            if np.array_equal(old_words[start:stop], new_words[start:stop]):
                continue
            old_payload = predecessor.payload[start * 4 : stop * 4]
            new_payload = image.payload[start * 4 : stop * 4]
            page_result = client.apply_candidate_page(
                candidate_id,
                page,
                hashlib.sha256(old_payload).hexdigest(),
                new_payload,
            )
            if page_result["placement"] != reservation.placement:
                reservation.placement = page_result["placement"]
        # The candidate is u32 words on both sides, so equal canonical float64
        # digests prove the native image equals the settled payload without
        # exporting it back through a staging mapping.
        finalized = client.candidate_digest(candidate_id)
        if finalized["predecessor_state_sha256"] != reservation.predecessor_state_sha256:
            raise FieldRuntimeError("native candidate predecessor disagrees")
        canonical = np.frombuffer(image.payload, dtype="<u4").astype("<f8")
        if (
            finalized["canonical_bytes"] != canonical.nbytes
            or finalized["canonical_bytes_sha256"] != hashlib.sha256(canonical).hexdigest()
        ):
            raise FieldRuntimeError("native candidate field image disagrees")

    def compute_words(
        self,
        candidate_id: str,
        operations: Iterable[NativeWordOperation],
    ) -> Mapping[str, Any]:
        """Run ordered u32 operations against the private native candidate."""

        reservation = self._reservations.get(candidate_id)
        if reservation is None or reservation.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("candidate reservation is unknown or stale")
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native computation requires a native field service")
        self._verify_candidate_device(reservation)
        result = client.apply_word_operations(candidate_id, operations)
        if result.get("placement") in {
            "native-cpu",
            "native-cpu-continuation",
            "vulkan",
        }:
            reservation.placement = str(result["placement"])
        return {
            "candidate_id": candidate_id,
            "owner_id": reservation.owner_id,
            "service_generation": reservation.service_generation,
            "fence": reservation.fence,
            "lease_id": reservation.lease_id,
            **result,
        }
    def export_candidate_words(
        self, candidate_id: str, shape: Sequence[int]
    ) -> tuple[np.ndarray, Mapping[str, Any]]:
        """Read back an exact private candidate without promoting its cache."""

        reservation = self._reservations.get(candidate_id)
        if reservation is None or reservation.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("candidate reservation is unknown or stale")
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native export requires a native field service")
        image, metadata = client.export_candidate(candidate_id, shape)
        if metadata.get("predecessor_state_sha256") != reservation.predecessor_state_sha256:
            raise StalePublicationFence("native export predecessor changed")
        return image, {
            **metadata,
            "candidate_id": candidate_id,
            "owner_id": reservation.owner_id,
            "service_generation": reservation.service_generation,
            "fence": reservation.fence,
            "lease_id": reservation.lease_id,
            "placement": reservation.placement,
        }




    def reduce_candidate(
        self,
        candidate_id: str,
        first_word: int,
        count: int,
        *,
        owner_id: str,
        fence: int,
        lease_id: str,
    ) -> Mapping[str, Any]:
        """Exact native reduction view of an active candidate's word range.

        The scalar is candidate-bound and uncommitted: it is produced by the
        resident native service for this candidate only, is never written to
        the published cache, and stops being queryable the moment the
        candidate is confirmed through :meth:`confirm_publication`, cancelled,
        or invalidated by a service-generation change (recovery or device
        loss).  Visibility therefore stays tied to the existing publication
        lifecycle; the owner alone decides what to publish.
        """

        if not isinstance(owner_id, str) or not owner_id:
            raise FieldRuntimeError("owner_id must be nonempty")
        if isinstance(first_word, bool) or not isinstance(first_word, int) or first_word < 0:
            raise FieldRuntimeError("first_word must be a nonnegative word index")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise FieldRuntimeError("count must be a positive word count")
        reservation = self._reservations.get(candidate_id)
        if reservation is None or reservation.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("candidate reservation is unknown or stale")
        if reservation.owner_id != owner_id:
            raise StalePublicationFence("candidate owner disagrees")
        attachment = self._attachment(owner_id)
        if reservation.fence != fence or attachment.fence != fence:
            raise StalePublicationFence("candidate reduction fence is stale")
        if reservation.lease_id != lease_id:
            raise StalePublicationFence("candidate lease is stale")
        if attachment.image.state_sha256 != reservation.predecessor_state_sha256:
            raise StalePublicationFence("resident predecessor changed")
        word_count = attachment.image.word_count
        if first_word >= word_count or count > word_count - first_word:
            raise FieldRuntimeError("reduction range is outside the resident image")
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native reduction requires a native field service")
        self._verify_candidate_device(reservation)
        result = client.reduce_candidate(candidate_id, first_word, count)
        if result["count"] != count:
            raise FieldRuntimeError("native reduction count disagrees")
        if result["fence"] != reservation.fence:
            raise StalePublicationFence("native reduction fence disagrees")
        if result["predecessor_state_sha256"] != reservation.predecessor_state_sha256:
            raise StalePublicationFence("native reduction predecessor disagrees")
        placement = str(result["placement"])
        if placement not in {"native-cpu", "native-cpu-continuation", "vulkan"}:
            raise FieldRuntimeError("native reduction returned an unknown placement")
        reservation.placement = placement
        return {
            "candidate_id": candidate_id,
            "owner_id": reservation.owner_id,
            "service_generation": reservation.service_generation,
            "fence": reservation.fence,
            "lease_id": reservation.lease_id,
            "predecessor_state_sha256": reservation.predecessor_state_sha256,
            "first_word": first_word,
            "count": count,
            "sum": int(result["sum"]),
            "status": "reduced",
            "placement": placement,
        }

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
        changed_pages: Sequence[int] | None = None,
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
        self._verify_candidate_device(reservation)
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
        self._settle_native_image(candidate_id, reservation, image, changed_pages)
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
            device_index=reservation.device_index,
            device_identity=reservation.device_identity,
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
        if candidate.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("candidate service generation is stale")
        self._verify_candidate_device(candidate)
        attachment = self._attachment(candidate.owner_id)
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
        owner_ack: Mapping[str, Any] | None = None,
        graph_site_receipt_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Commit field and provisional model state after owner publication."""

        graph_confirmation = (
            owner_ack is not None or graph_site_receipt_sha256 is not None
        )
        if graph_confirmation:
            if owner_ack is None or graph_site_receipt_sha256 is None:
                raise FieldRuntimeError(
                    "graph publication requires both owner_ack and "
                    "graph_site_receipt_sha256"
                )
            receipt_sha256 = _hex_digest(
                graph_site_receipt_sha256, "graph_site_receipt_sha256"
            )
            if not isinstance(owner_ack, Mapping):
                raise FieldRuntimeError("owner_ack must be a mapping")
            if set(owner_ack) != {
                "accepted_model_step",
                "accepted_token_id",
                "native_operation_id",
                "field_successor_sha256",
                "native_successor_sha256",
                "native_graph_site_receipt_sha256",
                "graph_receipt_wire_sha256",
                "ticket_id",
                "field_candidate_id",
            }:
                raise FieldRuntimeError(
                    "owner_ack must contain the exact native graph-site acknowledgement"
                )
            if owner_ack.get("accepted_model_step") is not True:
                raise FieldRuntimeError(
                    "owner_ack.accepted_model_step must be True"
                )
            if owner_ack.get("native_graph_site_receipt_sha256") != receipt_sha256:
                raise StalePublicationFence(
                    "owner acknowledgement names a different graph-site receipt"
                )
            accepted_token_id = owner_ack.get("accepted_token_id")
            if (
                isinstance(accepted_token_id, bool)
                or not isinstance(accepted_token_id, int)
                or accepted_token_id < 0
            ):
                raise FieldRuntimeError(
                    "owner_ack.accepted_token_id must be a nonnegative integer"
                )
            native_operation_id = owner_ack.get("native_operation_id")
            if not isinstance(native_operation_id, str) or not native_operation_id:
                raise FieldRuntimeError(
                    "owner_ack.native_operation_id must be a nonempty string"
                )
            ticket_id = owner_ack.get("ticket_id")
            if not isinstance(ticket_id, str) or not ticket_id:
                raise FieldRuntimeError("owner_ack.ticket_id must be a nonempty string")
            if owner_ack.get("field_candidate_id") != candidate_id:
                raise StalePublicationFence(
                    "owner acknowledgement names a different field candidate"
                )
            _hex_digest(
                owner_ack.get("field_successor_sha256"),
                "owner_ack.field_successor_sha256",
            )
            _hex_digest(
                owner_ack.get("native_successor_sha256"),
                "owner_ack.native_successor_sha256",
            )
            _hex_digest(
                owner_ack.get("graph_receipt_wire_sha256"),
                "owner_ack.graph_receipt_wire_sha256",
            )
            if self._native_client is None:
                raise FieldRuntimeError(
                    "graph publication requires an attached native model runtime"
                )
            self._require_graph_site_capabilities(self._native_client)

        candidate = self.validate_for_publication(
            candidate_id,
            owner_state_sha256=candidate_predecessor(self, candidate_id),
            fence=fence,
            lease_id=lease_id,
        )
        if owner_state_sha256 != candidate.image.state_sha256:
            raise StalePublicationFence("owner did not publish candidate successor")
        if graph_confirmation and (
            owner_ack["field_successor_sha256"] != candidate.image.state_sha256
        ):
            raise StalePublicationFence(
                "owner acknowledgement names a different field successor"
            )
        if self._native_client is not None:
            if graph_confirmation:
                native_confirmation = self._native_client.confirm_cache(
                    candidate_id,
                    candidate.predecessor_state_sha256,
                    owner_state_sha256,
                    fence=fence,
                    lease_id=lease_id,
                    graph_site_receipt_sha256=receipt_sha256,
                    owner_ack=owner_ack,
                )
            else:
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
            if graph_confirmation:
                accepted_model_step = native_confirmation.get("accepted_model_step")
                if (
                    native_confirmation.get("accepted_token_id")
                    != accepted_token_id
                    or isinstance(accepted_model_step, bool)
                    or not isinstance(accepted_model_step, int)
                    or accepted_model_step != 1
                ):
                    raise FieldRuntimeError(
                        "native graph-site confirmation disagrees with owner acknowledgement"
                    )
        self._attachments[candidate.owner_id] = ResidentAttachment(
            owner_id=candidate.owner_id,
            service_generation=self.service_generation,
            fence=fence + 1,
            image=candidate.image,
            placement=candidate.placement,
            device_index=candidate.device_index,
            device_identity=candidate.device_identity,
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
            "device_index": candidate.device_index,
            "device_identity": candidate.device_identity,
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

    @staticmethod
    def _require_graph_site_capabilities(client: Any) -> None:
        if not callable(getattr(client, "candidate_preflight", None)) or not callable(
            getattr(client, "rebuild_task_from_owner_history", None)
        ):
            raise FieldRuntimeError(
                "native model runtime does not support graph-site preflight and replay"
            )

    def candidate_preflight(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        *,
        sequence_id: str,
        sampler: Mapping[str, Any],
        native_operation_id: str,
    ) -> Mapping[str, Any]:
        """Ask the native client to measure the requested owner graph sequence."""

        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        self._require_graph_site_capabilities(client)
        if not isinstance(sequence_id, str) or not sequence_id:
            raise FieldRuntimeError("sequence_id must be a nonempty string")
        if not isinstance(native_operation_id, str) or not native_operation_id:
            raise FieldRuntimeError("native_operation_id must be a nonempty string")
        if not isinstance(sampler, Mapping):
            raise FieldRuntimeError("sampler must be a mapping")
        result = client.candidate_preflight(
            task_id,
            source_sha256,
            tokens,
            sequence_id=sequence_id,
            sampler=sampler,
            native_operation_id=native_operation_id,
        )
        if not isinstance(result, Mapping):
            raise FieldRuntimeError(
                "native graph-site preflight returned an invalid result"
            )
        return result

    def rebuild_task_from_owner_history(
        self,
        task_id: str,
        source_sha256: str,
        model_id: str,
        tokenizer_id: str,
        owner_history: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Recreate disposable model state from the owner's accepted history."""

        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        self._require_graph_site_capabilities(client)
        if not isinstance(owner_history, Mapping):
            raise FieldRuntimeError("owner_history must be a mapping")
        result = client.rebuild_task_from_owner_history(
            task_id,
            source_sha256,
            model_id,
            tokenizer_id,
            owner_history,
        )
        if not isinstance(result, Mapping):
            raise FieldRuntimeError(
                "native owner-history replay returned an invalid result"
            )
        return result

    def _require_active_model_candidate(self, candidate_id: str) -> None:
        reservation = self._reservations.get(candidate_id)
        if reservation is None:
            raise FieldRuntimeError("model candidate is not an active field candidate")
        if reservation.service_generation != self.service_generation:
            raise StaleRuntimeGeneration("model candidate service generation is stale")

    def step_model(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        *,
        sampler_mode: str = "greedy",
        temperature: float = 1.0,
        top_k: int = 0,
        draw: float = 0.0,
        native_operation_id: str | None = None,
        sequence_id: str | None = None,
        candidate_id: str | None = None,
        graph_site_ticket: Mapping[str, Any] | None = None,
        replay_step: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        graph_candidate = candidate_id is not None or graph_site_ticket is not None
        sequence_bound_candidate = graph_candidate or replay_step is not None
        if sequence_bound_candidate:
            if not isinstance(sequence_id, str) or not sequence_id:
                raise FieldRuntimeError(
                    "graph-site and replay steps require a nonempty sequence_id"
                )
            if native_operation_id is not None:
                if not isinstance(native_operation_id, str) or not native_operation_id:
                    raise FieldRuntimeError(
                        "native_operation_id must be a nonempty string"
                    )
        elif sequence_id is not None and (
            not isinstance(sequence_id, str) or not sequence_id
        ):
            # Ordinary steps may name the owner sequence so owner history
            # can rebuild them beside graph-site steps.
            raise FieldRuntimeError("sequence_id must be a nonempty string")
        if (
            not graph_candidate
            and native_operation_id is None
            and replay_step is None
        ):
            return client.step_model(
                task_id,
                source_sha256,
                tokens,
                sampler_mode=sampler_mode,
                temperature=temperature,
                top_k=top_k,
                draw=draw,
            )
        if sequence_bound_candidate:
            self._require_graph_site_capabilities(client)
        if graph_site_ticket is not None and not isinstance(
            graph_site_ticket, Mapping
        ):
            raise FieldRuntimeError("graph_site_ticket must be a mapping")
        if replay_step is not None and not isinstance(replay_step, Mapping):
            raise FieldRuntimeError("replay_step must be a mapping")
        if candidate_id is not None:
            if not isinstance(candidate_id, str) or not candidate_id:
                raise FieldRuntimeError("candidate_id must be a nonempty string")
            self._require_active_model_candidate(candidate_id)
        if graph_site_ticket is not None:
            if candidate_id is None:
                raise FieldRuntimeError(
                    "graph-site ticket requires an active field candidate"
                )
            if not isinstance(native_operation_id, str) or not native_operation_id:
                raise FieldRuntimeError(
                    "graph-site ticket requires a nonempty native_operation_id"
                )
            if graph_site_ticket.get("sequence_id") != sequence_id:
                raise StalePublicationFence(
                    "graph-site ticket names a different owner sequence"
                )
        elif candidate_id is not None and replay_step is None:
            raise FieldRuntimeError(
                "field candidate model step requires an owner graph-site ticket"
            )
        if replay_step is not None and replay_step.get("sequence_id") != sequence_id:
            raise StalePublicationFence(
                "replay step names a different owner sequence"
            )
        ticket_id: str | None = None
        if graph_site_ticket is not None:
            ticket_id = graph_site_ticket.get("ticket_id")
            if not isinstance(ticket_id, str) or not ticket_id:
                raise FieldRuntimeError(
                    "graph-site ticket must contain a nonempty ticket_id"
                )
        result = client.step_model(
            task_id,
            source_sha256,
            tokens,
            sampler_mode=sampler_mode,
            temperature=temperature,
            top_k=top_k,
            draw=draw,
            native_operation_id=native_operation_id,
            sequence_id=sequence_id,
            candidate_id=candidate_id,
            graph_site_ticket=graph_site_ticket,
            replay_step=replay_step,
        )
        if graph_site_ticket is not None:
            if not isinstance(result, Mapping):
                raise FieldRuntimeError(
                    "native graph-site step returned an invalid result"
                )
            if result.get("status") == "graph-site-rejected":
                receipt = result.get("graph_site_receipt")
                receipt_sha256 = _hex_digest(
                    result.get("graph_site_receipt_sha256"),
                    "graph_site_receipt_sha256",
                )
                native_receipt_sha256 = _hex_digest(
                    result.get("native_graph_site_receipt_sha256"),
                    "native_graph_site_receipt_sha256",
                )
                wire_sha256 = _hex_digest(
                    result.get("graph_receipt_wire_sha256"),
                    "graph_receipt_wire_sha256",
                )
                native_wire_sha256 = _hex_digest(
                    result.get("native_graph_site_receipt_wire_sha256"),
                    "native_graph_site_receipt_wire_sha256",
                )
                if (
                    result.get("rejected") is not True
                    or result.get("attempted") is not True
                    or result.get("admitted") is not False
                    or result.get("accepted") is not False
                    or result.get("provisional") is not False
                    or result.get("confirmable") is not False
                    or any(
                        key in result
                        for key in ("token", "selected_token_id", "accepted_token_id")
                    )
                    or not isinstance(receipt, Mapping)
                    or receipt.get("schema")
                    != "cassifi.native-graph-site-receipt.v1"
                    or receipt.get("admitted") is not False
                    or receipt.get("selected_token_id") != -1
                    or receipt.get("field_candidate_id") != candidate_id
                    or receipt.get("ticket_id") != ticket_id
                    or receipt.get("sequence_id") != sequence_id
                    or receipt.get("native_operation_id") != native_operation_id
                    or result.get("field_candidate_id") != candidate_id
                    or result.get("ticket_id") != ticket_id
                    or result.get("sequence_id") != sequence_id
                    or result.get("native_operation_id") != native_operation_id
                    or receipt_sha256 != native_receipt_sha256
                    or _digest(dict(receipt)) != receipt_sha256
                    or wire_sha256 != native_wire_sha256
                ):
                    raise FieldRuntimeError(
                        "native graph-site refusal receipt does not match its candidate"
                    )
                return result

            if (
                result.get("accepted") is not False
                or result.get("provisional") is not True
            ):
                raise FieldRuntimeError(
                    "native graph-site step did not return a provisional token"
                )
            if "accepted_token_id" in result:
                raise FieldRuntimeError(
                    "native graph-site step exposed an accepted token before publication"
                )
            selected_token_id = result.get("selected_token_id")
            if (
                isinstance(selected_token_id, bool)
                or not isinstance(selected_token_id, int)
                or selected_token_id < 0
            ):
                raise FieldRuntimeError(
                    "native graph-site step returned an invalid selected_token_id"
                )
            receipt = result.get("graph_site_receipt")
            if not isinstance(receipt, Mapping):
                raise FieldRuntimeError(
                    "native graph-site step omitted its measured receipt"
                )
            if receipt.get("schema") != "cassifi.native-graph-site-receipt.v1":
                raise FieldRuntimeError(
                    "native graph-site step returned an unknown receipt schema"
                )
            if receipt.get("field_candidate_id") != candidate_id:
                raise StalePublicationFence(
                    "native graph-site receipt names a different field candidate"
                )
            if receipt.get("ticket_id") != ticket_id:
                raise StalePublicationFence(
                    "native graph-site receipt names a different owner ticket"
                )
            if receipt.get("sequence_id") != sequence_id:
                raise StalePublicationFence(
                    "native graph-site receipt names a different owner sequence"
                )
            if receipt.get("native_operation_id") != native_operation_id:
                raise StalePublicationFence(
                    "native graph-site receipt names a different operation"
                )
            receipt_sha256 = _hex_digest(
                result.get("graph_site_receipt_sha256"),
                "graph_site_receipt_sha256",
            )
            native_receipt_sha256 = _hex_digest(
                result.get("native_graph_site_receipt_sha256"),
                "native_graph_site_receipt_sha256",
            )
            if (
                receipt_sha256 != native_receipt_sha256
                or _digest(receipt) != receipt_sha256
            ):
                raise FieldRuntimeError(
                    "native graph-site step receipt digest disagrees"
                )
            if result.get("field_candidate_id", candidate_id) != candidate_id:
                raise StalePublicationFence(
                    "native graph-site result names a different field candidate"
                )
            if (
                result.get("native_operation_id", native_operation_id)
                != native_operation_id
            ):
                raise StalePublicationFence(
                    "native graph-site result names a different operation"
                )
            if result.get("provisional") is True:
                result = dict(result)
                result.pop("token", None)
        return result


    def drop_model_task(self, task_id: str) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.drop_model_task(task_id)

    def create_group(self, source_sha256: str, capacity: int) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.create_group(source_sha256, capacity)

    def step_group(
        self, group_id: int, rows: Sequence[NativeGroupRow]
    ) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.step_group(group_id, rows)

    def drop_group(self, group_id: int) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.drop_group(group_id)

    def leave_group(self, group_id: int, row: int) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.leave_group(group_id, row)

    def join_group(self, group_id: int) -> Mapping[str, Any]:
        client = self._native_client
        if client is None:
            raise FieldRuntimeError("native model runtime is not attached")
        return client.join_group(group_id)

    def recover_native(
        self, native_client: NativeFieldRuntimeClient
    ) -> Mapping[str, Any]:
        """Replace disposable native state after loss; owner checkpoints survive."""

        if not isinstance(native_client, NativeFieldRuntimeClient):
            raise FieldRuntimeError("recovery requires a native runtime client")
        lost = self.service_generation
        if native_client is self._native_client or native_client.service_generation == lost:
            raise FieldRuntimeError("recovery requires a distinct native service generation")
        affected = tuple(sorted(self._attachments))
        prior = self._native_client
        if prior is not None and prior is not native_client:
            try:
                prior.shutdown()
            except NativeFieldRuntimeError:
                pass
        self._lost_generations.add(lost)
        self.service_generation = native_client.service_generation
        self._attachments.clear()
        self._reservations.clear()
        self._owner_candidate.clear()
        self._settled.clear()
        self._device_report = None
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
        self._device_report = None
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
        self._device_report = None
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
        if isinstance(native_status, Mapping) and "device" in native_status:
            self._device_report = native_status["device"]
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
            "device": self._device_report,
            "memory_report": (
                native_status.get("memory_report")
                if isinstance(native_status, Mapping)
                else None
            ),
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
    "NativeGroupRow",
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
