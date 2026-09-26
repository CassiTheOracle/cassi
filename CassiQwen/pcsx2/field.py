"""Bounded native PCSX2 frame/input consumer for CassiFI temporal learning.

The bridge is the sole runtime source of RAM and consumed pad input.  Exact
framed messages are preserved in an append-only artifact; only bounded
categorical transitions and their source lineage enter the temporal owner.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid
from typing import Any
from .native_bridge import (
    ACTION_RECEIPT,
    BASELINE_CHUNK,
    DELTA,
    GAP,
    GAP_OUTPUT_QUEUE_FULL,
    INPUT_EVENT,
    MAX_RAM_BYTES,
    PAGE_BYTES,
    SESSION,
    VM_RESET,
    NativeBridgeError,
    NativeBridgeTimeout,
)


MAX_FIELD_SAMPLES = 2_048
MAX_POLL_MESSAGES_PER_SECOND = 240
MAX_PENDING_EVENTS = 8_192
MAX_ACTION_FRAMES = 120
MAX_PLAY_STEPS = 64
MAX_BASELINE_CHUNKS = MAX_RAM_BYTES // (1024 * 1024) + 1

_CHORD_SLOT_COUNT = 20
_CHORD_SLOT_ACTIONS = tuple(f"pad-chord-slot-{slot:02d}" for slot in range(_CHORD_SLOT_COUNT))
_ACTION_IDS = tuple(
    name
    for mask in (1 << bit for bit in range(16))
    for name in (f"pad-press-{mask:04x}", f"pad-release-{mask:04x}")
) + tuple(
    f"pad-{axis}-{state}"
    for axis in ("lx", "ly", "rx", "ry")
    for state in ("negative", "neutral", "positive")
) + _CHORD_SLOT_ACTIONS
_BUTTON_ACTIONS = tuple(f"pad-press-{1 << bit:04x}" for bit in range(16))
_PAGE_SIGNATURE_COUNT = 63
_OBSERVATION_IDS = ("ee-unchanged",) + tuple(
    f"ee-page-signature-{bucket:02d}"
    for bucket in range(_PAGE_SIGNATURE_COUNT)
)


class FieldLoopError(NativeBridgeError):
    """A bounded field loop stopped without claiming an unobserved outcome."""

    def __init__(self, code: str, message: str, result: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.code = code
        self.result = dict(result)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _bounded_text(value: Any, name: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{name} must be bounded nonempty text")
    return value


def _crc(value: Any, name: str) -> int:
    if type(value) is int:
        if not 0 <= value <= 0xFFFF_FFFF:
            raise ValueError(f"{name} must be a 32-bit CRC")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an integer or hexadecimal CRC")
    text = value.strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if not text or len(text) > 8:
        raise ValueError(f"{name} must be a 32-bit CRC")
    try:
        result = int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{name} must be a hexadecimal CRC") from exc
    if not 0 <= result <= 0xFFFF_FFFF:
        raise ValueError(f"{name} must be a 32-bit CRC")
    return result


def _digest(*parts: Any) -> str:
    body = b"\0".join(
        part if isinstance(part, bytes) else str(part).encode("utf-8")
        for part in parts
    )
    return hashlib.sha256(body).hexdigest()


def _hex_identity(value: Any, name: str) -> str:
    if not isinstance(value, bytes) or len(value) != 16 or value == bytes(16):
        raise NativeBridgeError(f"native {name} is not a nonzero 16-byte identity")
    return value.hex()


def _timestamp_label(frame_no: int, sample_no: int) -> str:
    return f"native-frame-{frame_no}-sample-{sample_no}"


def _gate_refusal_reason(reason_code: int) -> str:
    """Name a refused press by the native receipt reason that refused it."""
    if reason_code == 2:
        return "identity-changed"
    if reason_code == 1:
        return "gate-refused"
    return "action-refused"


def _action_button(action: str) -> int | None:
    if not action.startswith("pad-press-"):
        return None
    try:
        mask = int(action.removeprefix("pad-press-"), 16)
    except ValueError:
        return None
    return mask if 1 <= mask <= 0xFFFF else None


def _axis_bin(value: int) -> int:
    if value <= 85:
        return -1
    if value >= 171:
        return 1
    return 0


def _bin_name(value: int) -> str:
    return "negative" if value < 0 else "positive" if value > 0 else "neutral"


def _physical_active(payload: Mapping[str, Any]) -> bool:
    buttons = (~int(payload["physical_active_low_buttons"])) & 0xFFFF
    return bool(
        buttons
        or int(payload["lx"]) != 128
        or int(payload["ly"]) != 128
        or int(payload["rx"]) != 128
        or int(payload["ry"]) != 128
    )


def _event_action(
    event: Mapping[str, Any], previous: Mapping[str, Any] | None,
) -> tuple[str | None, str]:
    """Return one exact changed physical control or consumed virtual mask."""
    source_bits = int(event["source_bits"])
    physical_buttons = (~int(event["physical_active_low_buttons"])) & 0xFFFF
    previous_physical_buttons = (
        (~int(previous["physical_active_low_buttons"])) & 0xFFFF
        if previous is not None else 0
    )
    physical_signal = bool(source_bits & 0x01) or bool(
        previous is not None and int(previous["source_bits"]) & 0x01
    )
    if physical_signal:
        button_changes = physical_buttons ^ previous_physical_buttons
        axes = ("lx", "ly", "rx", "ry")
        old_axes = {
            axis: _axis_bin(int(previous[axis])) if previous is not None else 0
            for axis in axes
        }
        new_axes = {axis: _axis_bin(int(event[axis])) for axis in axes}
        changed_axes = [axis for axis in axes if new_axes[axis] != old_axes[axis]]
        if button_changes and changed_axes:
            return None, "physical-ambiguous"
        if button_changes:
            pressed = button_changes & physical_buttons
            released = button_changes & ~physical_buttons & 0xFFFF
            if pressed and released:
                return None, "physical-ambiguous"
            kind = "press" if pressed else "release"
            return f"pad-{kind}-{button_changes:04x}", (
                "physical-chord" if button_changes & (button_changes - 1) else "physical"
            )
        if len(changed_axes) == 1:
            axis = changed_axes[0]
            return f"pad-{axis}-{_bin_name(new_axes[axis])}", "physical"
        if changed_axes:
            return None, "physical-ambiguous"
        if not (source_bits & 0x02):
            return None, "physical-idle"

    if source_bits & 0x02:
        mask = int(event["virtual_active_high_mask"]) & 0xFFFF
        consumed = (~int(event["active_low_buttons"])) & 0xFFFF
        active = mask & consumed
        if active:
            return f"pad-press-{active:04x}", (
                "virtual" if active & (active - 1) == 0 else "virtual-chord"
            )
        return None, "virtual-idle"
    return None, "none"


def _observation_id(changed_regions: list[dict[str, Any]]) -> str:
    if not changed_regions:
        return "ee-unchanged"
    selected = sorted(
        (
            {"page_index": int(row["page_index"]), "sha256": str(row["sha256"])}
            for row in changed_regions[:16]
        ),
        key=lambda row: row["page_index"],
    )
    digest = hashlib.sha256(_canonical(selected)).digest()
    bucket = int.from_bytes(digest[:4], "big") % _PAGE_SIGNATURE_COUNT
    return f"ee-page-signature-{bucket:02d}"




def _receipt_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "request_id", "result", "reason", "requested_mask", "applied_mask",
        "requested_frames", "consumed_frames", "first_frame", "last_frame",
        "first_active_low_buttons", "last_active_low_buttons", "source_bits",
    )
    return {
        key: (value.hex() if isinstance((value := payload.get(key)), bytes) else value)
        for key in keys if key in payload
    }


class _Artifacts:
    """Create one exclusive raw stream and bounded sidecar journals."""

    def __init__(self, root: str | Path, run_key: str) -> None:
        directory = Path(root).expanduser() / "pcsx2-native-field"
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory / run_key
        self.directory.mkdir(parents=True, exist_ok=False)
        self.raw_path = self.directory / "stream.frames"
        self.observations_path = self.directory / "observations.jsonl"
        self.control_path = self.directory / "control.frames"
        self.raw = self.raw_path.open("xb")
        self.observations = self.observations_path.open("xb")
        self.control = self.control_path.open("xb")
        self._raw_hash = hashlib.sha256()
        self._observation_hash = hashlib.sha256()
        self._control_hash = hashlib.sha256()
        self._raw_bytes = 0
        self._observation_bytes = 0
        self._control_bytes = 0
        self._closed = False

    def write_frame(self, raw: bytes) -> tuple[int, int]:
        if not isinstance(raw, bytes) or not raw:
            raise NativeBridgeError("native bridge message has no immutable raw frame")
        offset = self._raw_bytes
        self.raw.write(raw)
        self._raw_hash.update(raw)
        self._raw_bytes += len(raw)
        return offset, len(raw)

    def observation(self, row: Mapping[str, Any]) -> None:
        body = _canonical(dict(row)) + b"\n"
        self.observations.write(body)
        self._observation_hash.update(body)
        self._observation_bytes += len(body)

    def control_request(self, raw: bytes, metadata: Mapping[str, Any]) -> tuple[int, int]:
        if not isinstance(raw, bytes) or not raw:
            raise NativeBridgeError("native control request has no exact encoded bytes")
        offset = self._control_bytes
        self.control.write(raw)
        self._control_hash.update(raw)
        self._control_bytes += len(raw)
        self.observation({
            "kind": "control-request", "observed_at": _now(),
            "control_offset": offset, "control_length": len(raw), **dict(metadata),
        })
        self.flush()
        return offset, len(raw)

    def flush(self) -> None:
        for stream in (self.raw, self.observations, self.control):
            stream.flush()
            os.fsync(stream.fileno())

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        self.raw.close()
        self.observations.close()
        self.control.close()
        self._closed = True

    def paths(self) -> dict[str, Any]:
        return {
            "raw": {
                "path": str(self.raw_path), "sha256": self._raw_hash.hexdigest(),
                "byte_length": self._raw_bytes,
            },
            "observations": {
                "path": str(self.observations_path),
                "sha256": self._observation_hash.hexdigest(),
                "byte_length": self._observation_bytes,
            },
            "control": {
                "path": str(self.control_path), "sha256": self._control_hash.hexdigest(),
                "byte_length": self._control_bytes,
            },
        }

    def write_result(self, result: Mapping[str, Any]) -> str:
        path = self.directory / "result.json"
        body = _canonical(dict(result)) + b"\n"
        with path.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        return str(path)


class _ChordCodec:
    """Append-only mapping from observed native chords to fixed owner slots."""

    def __init__(
        self,
        root: Path,
        *,
        memory_id: str,
        program_id: str,
        serial: str,
        crc: int,
        field_lock: Any,
    ) -> None:
        self.directory = root / f"{memory_id}-chords"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.memory_id = memory_id
        self.program_id = program_id
        self.serial = serial
        self.crc = crc
        self.field_lock = field_lock
        self.slots: list[dict[str, Any] | None] = [None] * _CHORD_SLOT_COUNT
        self._load()

    def _slot_path(self, index: int) -> Path:
        return self.directory / f"slot-{index:02d}.json"

    def _load(self) -> None:
        seen: set[tuple[str, int]] = set()
        for index in range(_CHORD_SLOT_COUNT):
            path = self._slot_path(index)
            if not path.exists():
                self.slots[index] = None
                continue
            try:
                raw = path.read_bytes()
                row = json.loads(raw.decode("utf-8"))
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                raise NativeBridgeError("persistent chord codec slot is unreadable") from exc
            if (
                not isinstance(row, dict)
                or set(row) != {
                    "schema", "memory_id", "program_id", "serial", "pcsx2_crc",
                    "slot", "kind", "mask",
                }
                or row["schema"] != "cassifi.pcsx2-chord-codec.v1"
                or row["memory_id"] != self.memory_id
                or row["program_id"] != self.program_id
                or row["serial"] != self.serial
                or row["pcsx2_crc"] != f"{self.crc:08x}"
                or type(row["slot"]) is not int or row["slot"] != index
                or row["kind"] not in ("press", "release")
                or type(row["mask"]) is not int
                or not 1 <= row["mask"] <= 0xFFFF
                or row["mask"] & (row["mask"] - 1) == 0
                or _canonical(row) + b"\n" != raw
            ):
                raise NativeBridgeError("persistent chord codec slot conflicts with this game identity")
            key = (row["kind"], row["mask"])
            if key in seen:
                raise NativeBridgeError("persistent chord codec maps one transition more than once")
            seen.add(key)
            self.slots[index] = row

    def lookup(self, kind: str, mask: int) -> str | None:
        for index, row in enumerate(self.slots):
            if row is not None and row["kind"] == kind and row["mask"] == mask:
                return _CHORD_SLOT_ACTIONS[index]
        return None

    def mask_for_action(self, action_id: str, *, kind: str = "press") -> int | None:
        try:
            index = _CHORD_SLOT_ACTIONS.index(action_id)
        except ValueError:
            return None
        row = self.slots[index]
        return int(row["mask"]) if row is not None and row["kind"] == kind else None
    def binding_for_action(self, action_id: str) -> Mapping[str, Any] | None:
        try:
            index = _CHORD_SLOT_ACTIONS.index(action_id)
        except ValueError:
            return None
        return self.slots[index]


    def bind(self, kind: str, mask: int) -> str | None:
        if (
            kind not in ("press", "release")
            or type(mask) is not int
            or not 1 <= mask <= 0xFFFF
            or mask & (mask - 1) == 0
        ):
            raise ValueError("chord codec accepts only exact multi-button transitions")
        with self.field_lock:
            self._load()
            known = self.lookup(kind, mask)
            if known is not None:
                return known
            for index, prior in enumerate(self.slots):
                if prior is not None:
                    continue
                row = {
                    "schema": "cassifi.pcsx2-chord-codec.v1",
                    "memory_id": self.memory_id,
                    "program_id": self.program_id,
                    "serial": self.serial,
                    "pcsx2_crc": f"{self.crc:08x}",
                    "slot": index,
                    "kind": kind,
                    "mask": mask,
                }
                try:
                    with self._slot_path(index).open("xb") as stream:
                        stream.write(_canonical(row) + b"\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                except FileExistsError:
                    self._load()
                    known = self.lookup(kind, mask)
                    if known is not None:
                        return known
                    continue
                self.slots[index] = row
                return _CHORD_SLOT_ACTIONS[index]
            return None


class _BaselineAssembly:
    __slots__ = (
        "snapshot_id", "frame_no", "total", "chunk_count", "memory",
        "chunks", "ranges",
    )

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.snapshot_id = payload["snapshot_id"]
        self.frame_no = int(payload["frame_no"])
        self.total = int(payload["total_ram_size"])
        self.chunk_count = int(payload["chunk_count"])
        if not 1 <= self.total <= MAX_RAM_BYTES or self.total % PAGE_BYTES:
            raise NativeBridgeError("SESSION baseline RAM size is outside the native bound")
        if not 1 <= self.chunk_count <= MAX_BASELINE_CHUNKS:
            raise NativeBridgeError("baseline chunk count exceeds its fixed bound")
        self.memory = bytearray(self.total)
        self.chunks: set[int] = set()
        self.ranges: list[tuple[int, int]] = []

    def add(self, payload: Mapping[str, Any]) -> bool:
        if (
            payload["snapshot_id"] != self.snapshot_id
            or int(payload["frame_no"]) != self.frame_no
            or int(payload["total_ram_size"]) != self.total
            or int(payload["chunk_count"]) != self.chunk_count
        ):
            raise NativeBridgeError("baseline chunks do not share one snapshot identity")
        index = int(payload["chunk_index"])
        offset = int(payload["offset"])
        data = payload["data"]
        if (
            index in self.chunks or index >= self.chunk_count
            or not isinstance(data, memoryview) or not len(data)
            or len(data) > 1024 * 1024 or offset < 0 or offset + len(data) > self.total
        ):
            raise NativeBridgeError("baseline chunk is duplicate or outside its fixed bounds")
        end = offset + len(data)
        if any(offset < prior_end and prior_start < end for prior_start, prior_end in self.ranges):
            raise NativeBridgeError("baseline chunks overlap")
        self.memory[offset:end] = data
        self.ranges.append((offset, end))
        self.chunks.add(index)
        return len(self.chunks) == self.chunk_count

    def complete(self) -> bytearray:
        if len(self.chunks) != self.chunk_count:
            raise NativeBridgeError("baseline snapshot is incomplete")
        cursor = 0
        for start, end in sorted(self.ranges):
            if start != cursor or end <= start:
                raise NativeBridgeError("baseline chunks do not exactly cover EE RAM")
            cursor = end
        if cursor != self.total:
            raise NativeBridgeError("baseline chunks do not cover the exact SESSION RAM size")
        return self.memory


def _source_input(
    *, source_id: str, content: bytes, observed_timestamp: str, scope: str,
    labels: tuple[str, ...],
) -> Any:
    try:
        from cassi_field_owner import SourceInput
    except ImportError:
        from CassiFI.cassi_field_owner import SourceInput  # type: ignore[no-redef]
    return SourceInput(
        source_id=source_id,
        content=content,
        media_type="application/json",
        codec="utf-8",
        observed_timestamp=observed_timestamp,
        scope=scope,
        claim_category="observed-interaction",
        fidelity="native-frame-correlated",
        labels=labels,
    )


def run_field_loop(
    *,
    client: Any,
    owner: Any,
    field_lock: Any,
    atlas: Any,
    program_id: str,
    operation_id: str,
    artifact_home: str | Path,
    expected_serial: str,
    expected_crc: int | str,
    samples: int,
    allow_actions: bool,
    foreground_guard: Callable[[], bool],
    timeout_seconds: float = 30.0,
    max_action_frames: int = 2,
    steps: int = 1,
) -> dict[str, Any]:
    """Consume one bounded native session and admit only observed transitions.

    ``steps`` above one keeps selecting and arming field-chosen actions until
    that many actions resolve, so one bounded session plays a short sequence of
    the field's own presses.  The caller binds ``client`` to the authorized
    foreground PID and performs program-scope/field-act admission.  This
    function never reads another process, writes PINE, closes the client, or
    manufactures a transition from a command request/receipt alone.
    """
    program_id = _bounded_text(program_id, "program_id", maximum=256)
    operation_id = _bounded_text(operation_id, "operation_id", maximum=256)
    expected_serial = _bounded_text(expected_serial, "expected_serial", maximum=256)
    if type(samples) is not int or not 1 <= samples <= MAX_FIELD_SAMPLES:
        raise ValueError(f"samples must be an integer from 1 through {MAX_FIELD_SAMPLES}")
    if type(allow_actions) is not bool:
        raise ValueError("allow_actions must be boolean")
    if type(max_action_frames) is not int or not 1 <= max_action_frames <= MAX_ACTION_FRAMES:
        raise ValueError(f"max_action_frames must be within 1..{MAX_ACTION_FRAMES}")
    if type(steps) is not int or not 1 <= steps <= MAX_PLAY_STEPS:
        raise ValueError(f"steps must be an integer from 1 through {MAX_PLAY_STEPS}")
    if steps > 1 and not allow_actions:
        raise ValueError("steps above one requires allow_actions")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0.1 <= float(timeout_seconds) <= 600.0
    ):
        raise ValueError("timeout_seconds must be finite and within 0.1..600 seconds")
    if not callable(foreground_guard):
        raise TypeError("foreground_guard must be callable")
    if not callable(getattr(client, "receive", None)):
        raise TypeError("client must be a bound NativeBridgeClient")
    if not hasattr(field_lock, "__enter__") or not hasattr(field_lock, "__exit__"):
        raise TypeError("field_lock must be a context manager")

    atlas_identity = getattr(atlas, "identity", None)
    if not isinstance(atlas_identity, Mapping):
        raise ValueError("atlas must expose a game identity mapping")
    atlas_serial = atlas_identity.get("serial")
    # The ISO boot name may use ``SLUS_209.40`` where PCSX2 reports ``SLUS-20940``.
    if (
        not isinstance(atlas_serial, str)
        or "".join(c for c in atlas_serial.upper() if c.isascii() and c.isalnum())
        != "".join(c for c in expected_serial.upper() if c.isascii() and c.isalnum())
    ):
        raise ValueError("expected serial does not match the supplied atlas")
    expected_crc_value = _crc(expected_crc, "expected_crc")
    atlas_crc_value = _crc(atlas_identity.get("pcsx2_crc"), "atlas pcsx2_crc")
    if atlas_crc_value != expected_crc_value:
        raise ValueError("expected CRC does not match the supplied atlas")

    memory_key = _digest("pcsx2-memory", program_id, expected_serial, f"{expected_crc_value:08x}")
    memory_id = f"pcsx2-memory-{memory_key[:32]}"
    participant_key = _digest(
        "pcsx2-participant", program_id, expected_serial, f"{expected_crc_value:08x}",
    )
    participant_id = f"pcsx2-participant-{participant_key[:32]}"
    scope = f"pcsx2-native:{program_id}:{expected_serial}:{expected_crc_value:08x}"
    temporal_context = {
        "world": "pcsx2-native-ee",
        "program_id": program_id,
        "serial": expected_serial,
        "pcsx2_crc": f"{expected_crc_value:08x}",
    }
    expected_pid = getattr(client, "_expected_server_pid", None)
    if type(expected_pid) is not int or not 1 <= expected_pid <= 0xFFFF_FFFF:
        raise ValueError("client must be bound to the exact foreground PCSX2 PID")
    field_root = Path(artifact_home).expanduser() / "pcsx2-native-field"
    field_root.mkdir(parents=True, exist_ok=True)
    chord_codec = _ChordCodec(
        field_root,
        memory_id=memory_id,
        program_id=program_id,
        serial=expected_serial,
        crc=expected_crc_value,
        field_lock=field_lock,
    )
    run_token = uuid.uuid4().hex
    run_key = _digest(program_id, operation_id, run_token)[:40]
    journal = _Artifacts(artifact_home, run_key)

    started = time.monotonic()
    deadline = started + float(timeout_seconds)
    max_messages = (
        256
        + samples * 4
        + steps * 8
        + int(math.ceil(float(timeout_seconds))) * MAX_POLL_MESSAGES_PER_SECOND
    )

    def fresh_action_state() -> dict[str, Any]:
        return {
            "status": "NOT_REQUESTED" if not allow_actions else "NO_SELECTION",
            "requested": False,
            "action_id": None,
            "mask": None,
            "duration_frames": None,
            "request_id": None,
            "enable_request_id": None,
            "enable_receipt": None,
            "terminal_receipt": None,
            "consumed_event": None,
            "outcome_observation": None,
            "cancel_sent": False,
        }

    state: dict[str, Any] = {
        "program_id": program_id,
        "operation_id": operation_id,
        "memory_id": memory_id,
        "participant_id": participant_id,
        "session_id": None,
        "identity": None,
        "status": "RUNNING",
        "reason": None,
        "frames_observed": 0,
        "messages_received": 0,
        "input_events_observed": 0,
        "gaps_observed": 0,
        "resets_observed": 0,
        "reconnects": 0,
        "first_frame": None,
        "last_frame": None,
        "baseline_sha256": None,
        "learning": {
            "transitions": 0,
            "action_counts": {},
            "outcome_counts": {},
            "last_source_revision_id": None,
            "last_learning_receipt": None,
            "last_advance_receipt": None,
        },
        "selection": None,
        "inquiry": None,
        "play": {
            "steps": steps if allow_actions else 0,
            "completed": 0,
            "rows": [],
            "stop_reason": None,
            "paused": False,
            "physical_overrides": 0,
        },
        "action": fresh_action_state(),
    }

    current_session: Mapping[str, Any] | None = None
    expected_reset: tuple[bytes, int] | None = None
    baseline: _BaselineAssembly | None = None
    ram: bytearray | None = None
    baseline_frame: int | None = None
    snapshot_id: int | None = None
    last_delta_frame: int | None = None
    owner_ready = False
    decision_attempted = False
    stream_ready = False
    reconnect_used = False
    action_sent = False
    action_terminal = False
    action_enable_sent = False
    action_outcome_confirmed = False
    cancel_in_progress = False
    cancelled_request_id: bytes | None = None
    steps_done = 0
    step_seen_outcomes: frozenset[str] = frozenset()
    selection_retry_at = 0.0
    closed_request: bytes | None = None
    current_action_id: str | None = None
    current_action_mask: int | None = None
    current_action_request: bytes | None = None
    current_enable_request: bytes | None = None
    current_action_terminal: Mapping[str, Any] | None = None
    step_retried = False
    input_frames: dict[int, list[dict[str, Any]]] = {}
    delta_frames: dict[int, dict[str, Any]] = {}
    delta_order: list[int] = []
    reconciled_frames: set[int] = set()
    previous_input: dict[int, Mapping[str, Any]] = {}
    last_physical_active = False

    def op_id(kind: str, *parts: Any) -> str:
        return "pcsx2-op-" + _digest(operation_id, kind, *parts)[:48]

    def call_owner(method: str, *args: Any, **kwargs: Any) -> Any:
        with field_lock:
            return getattr(owner, method)(*args, **kwargs)

    def guard_ok() -> bool:
        try:
            return foreground_guard() is True
        except Exception:
            return False
    def bind_event_action(
        action_id: str | None, source_kind: str,
    ) -> tuple[str | None, str]:
        if source_kind not in ("physical-chord", "virtual-chord") or action_id is None:
            return action_id, source_kind
        kind = "release" if action_id.startswith("pad-release-") else "press"
        prefix = f"pad-{kind}-"
        try:
            mask = int(action_id.removeprefix(prefix), 16)
        except ValueError:
            return None, f"{source_kind}-unbound"
        if source_kind == "physical-chord":
            slot_action = chord_codec.bind(kind, mask)
        else:
            slot_action = chord_codec.lookup("press", mask)
        if slot_action is None:
            return None, f"{source_kind}-unbound"
        return slot_action, source_kind


    def current_artifacts() -> dict[str, Any]:
        return journal.paths()

    def result_mapping(status: str, reason: str | None = None) -> dict[str, Any]:
        row = dict(state)
        row["status"] = status
        row["reason"] = reason
        row["artifacts"] = current_artifacts()
        row["artifact"] = dict(row["artifacts"]["raw"])
        row["observation_artifact"] = dict(row["artifacts"]["observations"])
        row["control_artifact"] = dict(row["artifacts"]["control"])
        row["elapsed_seconds"] = round(max(0.0, time.monotonic() - started), 6)
        return row

    def raise_field(code: str, message: str) -> None:
        result = result_mapping("PARTIAL", code)
        _cancel_pending(message)
        journal.observation({
            "kind": "field-loop-stop", "observed_at": _now(),
            "code": code, "message": message,
        })
        journal.close()
        result = result_mapping("PARTIAL", code)
        result["artifact"] = dict(result["artifacts"]["raw"])
        result["observation_artifact"] = dict(result["artifacts"]["observations"])
        result["control_artifact"] = dict(result["artifacts"]["control"])
        result_path = journal.write_result(result)
        result["result_path"] = result_path
        raise FieldLoopError(code, message, result)

    def _cancel_pending(reason: str) -> None:
        nonlocal cancel_in_progress, cancelled_request_id
        pending_id = current_action_request if action_sent and not action_terminal else None
        if pending_id is None and action_enable_sent and not action_sent and not action_terminal:
            pending_id = current_enable_request
        if (
            pending_id is None or cancel_in_progress or current_session is None
            or state["action"].get("cancel_sent") is True
        ):
            return
        cancel_in_progress = True
        cancelled_request_id = pending_id
        try:
            if not guard_ok():
                raise NativeBridgeError("foreground guard rejected cancellation")
            session_id = current_session["session_id"]
            stream_id = current_session["stream_id"]
            cancel_id = pending_id

            def before_send(raw: bytes) -> None:
                if not guard_ok():
                    raise NativeBridgeError("foreground guard rejected cancellation")
                journal.control_request(raw, {
                    "message": "CANCEL_ACTION", "request_id": cancel_id.hex(),
                    "reason": reason,
                })

            client.send_cancel(session_id, stream_id, cancel_id, before_send=before_send)
            state["action"]["cancel_sent"] = True
        except Exception as exc:
            journal.observation({
                "kind": "cancel-failed", "observed_at": _now(),
                "reason": reason, "error": type(exc).__name__,
            })
        finally:
            cancel_in_progress = False

    def ensure_temporal_owner(session: Mapping[str, Any]) -> None:
        nonlocal owner_ready
        if owner_ready:
            return
        if int(session["producer_pid"]) != expected_pid:
            raise NativeBridgeError("SESSION producer PID does not match the exact bound PCSX2 PID")
        with field_lock:
            row = None
            state_object = getattr(owner, "state", None)
            temporal_fields = getattr(state_object, "temporal_fields", ())
            for candidate in temporal_fields:
                if getattr(candidate, "memory_id", None) == memory_id:
                    row = candidate
                    break
            if row is None:
                owner.configure_temporal(
                    op_id("configure", memory_id),
                    memory_id=memory_id,
                    action_ids=_ACTION_IDS,
                    observation_ids=_OBSERVATION_IDS,
                    max_states=128,
                    context=temporal_context,
                )
                row = owner.state.temporal(memory_id)
            if (
                tuple(row.action_ids) != _ACTION_IDS
                or tuple(row.observation_ids) != _OBSERVATION_IDS
                or dict(row.context) != temporal_context
            ):
                raise NativeBridgeError("existing CassiFI temporal memory has a conflicting game/action schema")
            owner.bind_temporal(
                op_id("bind", session["session_id"], session["vm_generation"]),
                memory_id=memory_id,
                participant_id=participant_id,
                known_start=False,
            )
        owner_ready = True

    def admit_transition(
        action_id: str, observation_id: str, frame_no: int,
        event: Mapping[str, Any], delta: Mapping[str, Any], source_kind: str,
        request_id: bytes | None = None,
    ) -> None:
        if current_session is None or not owner_ready or action_id not in _ACTION_IDS or observation_id not in _OBSERVATION_IDS:
            return
        session_hex = current_session["session_id"].hex()
        stream_hex = current_session["stream_id"].hex()
        input_frame_no = int(event["frame_no"])
        sample_no = int(event["sample_no"])
        source_id = "pcsx2-source-" + _digest(
            program_id, session_hex, stream_hex, input_frame_no, frame_no, sample_no,
            action_id, observation_id, request_id.hex() if request_id else "human",
        )[:48]
        timestamp = _now()
        content = _canonical({
            "schema": "cassifi.temporal-episode.v1",
            "steps": [{"action": action_id, "observation": observation_id}],
        })
        selected_pages = tuple(delta["changed_regions"][:16])
        page_labels = tuple(
            f"ee-page-{int(row['page_index']):04x}-sha256-{str(row['sha256'])[:16]}"
            for row in selected_pages
        )
        chord_binding = chord_codec.binding_for_action(action_id)
        chord_labels = (
            (
                f"native-chord-kind-{chord_binding['kind']}",
                f"native-chord-mask-{int(chord_binding['mask']):04x}",
            )
            if chord_binding is not None else ()
        )
        labels = (
            f"native-session-{session_hex}", f"native-stream-{stream_hex}",
            f"native-input-frame-{input_frame_no}", f"native-frame-{frame_no}",
            f"native-sample-{sample_no}", f"native-slot-{int(event['slot'])}",
            f"input-source-{source_kind}", f"ram-observation-{observation_id}",
        ) + page_labels + chord_labels + (
            (f"action-request-{request_id.hex()}",) if request_id else ()
        )
        source = _source_input(
            source_id=source_id,
            content=content,
            observed_timestamp=timestamp,
            scope=scope,
            labels=labels,
        )
        with field_lock:
            learned = owner.learn_temporal(
                op_id("learn", session_hex, stream_hex, input_frame_no, frame_no, sample_no, source_id),
                memory_id=memory_id,
                source=source,
                context=temporal_context,
            )
            advanced = owner.advance_temporal(
                op_id("advance", session_hex, stream_hex, input_frame_no, frame_no, sample_no, source_id),
                memory_id=memory_id,
                participant_id=participant_id,
                action=action_id,
                observation=observation_id,
            )
            row = owner.state.temporal(memory_id)
            skill_id = f"ee-goal-{observation_id}"
            if skill_id not in row.skill_ids:
                owner.condense_temporal_skill(
                    op_id("condense", skill_id),
                    memory_id=memory_id,
                    skill_id=skill_id,
                    goal_observations=(observation_id,),
                    forbidden_observations=(),
                )
        state["learning"]["transitions"] += 1
        action_counts = state["learning"]["action_counts"]
        action_counts[action_id] = int(action_counts.get(action_id, 0)) + 1
        outcome_counts = state["learning"]["outcome_counts"]
        outcome_counts[observation_id] = int(outcome_counts.get(observation_id, 0)) + 1
        state["learning"]["last_source_revision_id"] = source.revision_id
        state["learning"]["last_learning_receipt"] = _small_receipt(learned)
        state["learning"]["last_advance_receipt"] = _small_receipt(advanced)
        journal.observation({
            "kind": "temporal-learning", "observed_at": timestamp,
            "session_id": session_hex, "stream_id": stream_hex,
            "input_frame_no": input_frame_no, "frame_no": frame_no, "sample_no": sample_no,
            "source_kind": source_kind, "source_id": source.source_id,
            "source_revision_id": source.revision_id,
            "request_id": request_id.hex() if request_id else None,
            "changed_pages": list(delta["changed_pages"]),
            "selected_page_signatures": selected_pages,
            "chord_binding": dict(chord_binding) if chord_binding is not None else None,
            "receipt": state["learning"]["last_learning_receipt"],
            "advance": state["learning"]["last_advance_receipt"],
        })

        if (
            allow_actions and not decision_attempted
            and source_kind in ("physical", "physical-chord")
        ):
            choose_and_enable(current_session)

    def _small_receipt(result: Mapping[str, Any]) -> dict[str, Any]:
        raw = result.get("receipt", {}) if isinstance(result, Mapping) else {}
        if not isinstance(raw, Mapping):
            return {}
        fields = (
            "status", "action", "observation", "supported", "unknown_successor",
            "memory_id", "state", "state_sha256", "memory_sha256",
            "source_revision_id", "participant_id", "reason",
        )
        return {key: raw[key] for key in fields if key in raw}

    def button_action_candidates(memory: Any) -> tuple[str, ...]:
        candidates = set(_BUTTON_ACTIONS)
        for action_id in _CHORD_SLOT_ACTIONS:
            if chord_codec.mask_for_action(action_id) is None:
                continue
            prediction = memory.predict(action_id, participant_id=participant_id)
            support = prediction.get("support", {}) if isinstance(prediction, Mapping) else {}
            if int(support.get("exposure", 0)) > 0:
                candidates.add(action_id)
        for skill_id in memory.formed_skill_ids:
            skill = memory.skill_action(skill_id, participant_id=participant_id)
            action_id = skill.get("action") if isinstance(skill, Mapping) else None
            if action_id in _CHORD_SLOT_ACTIONS and chord_codec.mask_for_action(action_id) is not None:
                candidates.add(action_id)
        return tuple(action for action in memory.action_ids if action in candidates)

    def choose_and_enable(session: Mapping[str, Any]) -> None:
        nonlocal decision_attempted, current_action_id, current_action_mask
        nonlocal current_action_request, current_enable_request, action_enable_sent
        nonlocal step_seen_outcomes
        if decision_attempted or not owner_ready:
            return
        if not allow_actions:
            decision_attempted = True
            state["action"]["status"] = "NOT_REQUESTED"
            return
        with field_lock:
            memory = owner.state.temporal(memory_id)
            button_actions = button_action_candidates(memory)
            action_rows = [
                {"action": action, "authorized": True, "feasible": True,
                 "represented_forbidden": False}
                for action in button_actions
            ]
            formed = tuple(memory.formed_skill_ids)
            if formed:
                selection = owner.select_temporal_action(
                    memory_id,
                    skill_ids=formed,
                    operations=action_rows,
                    participant_id=participant_id,
                    minimum_margin=1e-9,
                )
                selected = selection.get("selected") if isinstance(selection, Mapping) else None
                state["selection"] = {
                    "status": selection.get("status"),
                    "action": selected.get("action") if isinstance(selected, Mapping) else None,
                    "skill_id": selected.get("skill_id") if isinstance(selected, Mapping) else None,
                    "reason": selection.get("reason"),
                    "decision_sha256": selection.get("decision_sha256"),
                    "read_only": selection.get("read_only"),
                }
            else:
                state["selection"] = {"status": "unformed", "action": None}
            selected_action = state["selection"].get("action")
            observed_goals = set(state["learning"]["outcome_counts"])
            exposure: list[tuple[int, str]] = []
            for action in button_actions:
                prediction = memory.predict(action, participant_id=participant_id)
                support = prediction.get("support", {}) if isinstance(prediction, Mapping) else {}
                exposure.append((int(support.get("exposure", 0)), action))
                for outcome in support.get("outcomes", ()):
                    if isinstance(outcome, Mapping) and isinstance(outcome.get("observation"), str):
                        observed_goals.add(outcome["observation"])
            if selected_action is None:
                if not observed_goals:
                    if steps > 1 and exposure:
                        # A play session on a field that has never observed a
                        # consequence explores the least-tried control, which
                        # gives its own memory the first goal to acquire toward.
                        selected_action = sorted(exposure)[0][1]
                        state["inquiry"] = {
                            "status": "exploring",
                            "action": selected_action,
                            "reason": "no-observed-successor-goal",
                            "acquisition_allowed": True,
                        }
                    else:
                        state["inquiry"] = {
                            "status": "deferred",
                            "action": None,
                            "reason": "no-observed-successor-goal",
                            "acquisition_allowed": False,
                        }
                        return
                else:
                    inquiry_ops = [
                        {
                            "action": action,
                            "cost": 0.0,
                            "risk": 0.0,
                            "authorized": True,
                            "feasible": True,
                            "acquisition_allowed": True,
                        }
                        for action in button_actions
                    ]
                    inquiry = owner.inquire_temporal(
                        memory_id,
                        operations=inquiry_ops,
                        participant_id=participant_id,
                        goal_observations=tuple(sorted(observed_goals)),
                        horizon=3,
                        max_nodes=512,
                    )
                    state["inquiry"] = {
                        "status": inquiry.get("status"),
                        "action": inquiry.get("action"),
                        "reason": inquiry.get("reason"),
                        "acquisition_allowed": inquiry.get("acquisition_allowed"),
                        "decision_resolved": inquiry.get("decision_resolved"),
                        "work": dict(inquiry.get("work", {})),
                    }
                    if (
                        inquiry.get("action") is not None
                        and inquiry.get("acquisition_allowed") is True
                    ):
                        selected_action = inquiry["action"]
            decision_attempted = selected_action is not None
        if selected_action is None:
            state["action"]["status"] = "NO_SELECTION"
            return
        mask = _action_button(selected_action)
        if mask is None:
            mask = chord_codec.mask_for_action(selected_action)
        if mask is None:
            state["action"]["status"] = "NO_SELECTION"
            state["action"]["selection_error"] = "owner selected an unbound native button action"
            return
        arm_action(session, selected_action, mask)

    def arm_action(session: Mapping[str, Any], selected_action: str, mask: int) -> None:
        nonlocal current_action_id, current_action_mask, current_enable_request
        nonlocal current_action_request, step_seen_outcomes, action_enable_sent
        current_action_id = selected_action
        current_action_mask = mask
        current_enable_request = uuid.uuid4().bytes
        current_action_request = uuid.uuid4().bytes
        binding = chord_codec.binding_for_action(selected_action)
        step_seen_outcomes = frozenset(state["learning"]["outcome_counts"])
        state["action"].update({
            "status": "ENABLING",
            "requested": True,
            "cancel_sent": False,
            "action_id": selected_action,
            "mask": mask,
            "chord_binding": dict(binding) if binding is not None else None,
            "duration_frames": max_action_frames,
            "request_id": current_action_request.hex(),
            "enable_request_id": current_enable_request.hex(),
        })
        if current_session is None or not guard_ok():
            state["action"]["status"] = "CANCELLED"
            state["action"]["cancel_reason"] = "foreground guard rejected action enable"
            return
        if action_enable_sent:
            # The native gate still holds this session identity, so this step
            # proceeds straight to its own action.
            send_selected_action(session)
            return
        try:
            client.connect_control(session)

            def before_enable(raw: bytes) -> None:
                nonlocal action_enable_sent
                if not guard_ok():
                    raise NativeBridgeError("foreground guard rejected action enable")
                journal.control_request(raw, {
                    "message": "ENABLE_ACTIONS",
                    "request_id": current_enable_request.hex(),
                    "session_id": session["session_id"].hex(),
                    "stream_id": session["stream_id"].hex(),
                    "expected_serial": expected_serial,
                    "expected_crc": f"{expected_crc_value:08x}",
                })
                action_enable_sent = True

            client.send_enable_actions(
                session["session_id"], session["stream_id"], current_enable_request,
                expected_serial=expected_serial,
                expected_current_crc=expected_crc_value,
                before_send=before_enable,
            )
            action_enable_sent = True
        except Exception as exc:
            state["action"]["status"] = "UNRESOLVED" if action_enable_sent else "REJECTED"
            state["action"]["error"] = type(exc).__name__
            if action_enable_sent:
                _cancel_pending("enable-send-error")
            journal.observation({
                "kind": "enable-send-failed", "observed_at": _now(),
                "error": type(exc).__name__,
                "send_may_have_occurred": action_enable_sent,
            })

    def send_selected_action(session: Mapping[str, Any]) -> None:
        nonlocal action_sent
        if (
            current_action_id is None or current_action_mask is None
            or current_action_request is None or current_enable_request is None
            or not action_enable_sent or action_sent
            or state["action"]["status"] == "CANCELLED"
        ):
            return
        if not guard_ok():
            state["action"]["status"] = "CANCELLED"
            state["action"]["cancel_reason"] = "foreground guard rejected action send"
            _cancel_pending("foreground-guard")
            return

        def before_action(raw: bytes) -> None:
            nonlocal action_sent
            if not guard_ok():
                raise NativeBridgeError("foreground guard rejected virtual action")
            journal.control_request(raw, {
                "message": "ACTION", "request_id": current_action_request.hex(),
                "action_id": current_action_id, "mask": current_action_mask,
                "duration_frames": max_action_frames,
                "session_id": session["session_id"].hex(),
                "stream_id": session["stream_id"].hex(),
            })
            action_sent = True

        try:
            client.send_action(
                session["session_id"], session["stream_id"], current_action_request,
                current_action_mask, max_action_frames, before_send=before_action,
            )
            action_sent = True
            state["action"]["status"] = "SENT"
        except Exception as exc:
            if action_sent:
                state["action"]["status"] = "UNRESOLVED"
                _cancel_pending("action-send-error")
            elif not guard_ok():
                state["action"]["status"] = "CANCELLED"
                state["action"]["cancel_reason"] = "foreground guard rejected virtual action"
                _cancel_pending("foreground-guard")
            else:
                state["action"]["status"] = "REJECTED"
            state["action"]["error"] = type(exc).__name__
            journal.observation({
                "kind": "action-send-failed", "observed_at": _now(),
                "request_id": current_action_request.hex(),
                "error": type(exc).__name__,
                "send_may_have_occurred": action_sent,
            })

    def step_resolved() -> bool:
        if not action_terminal:
            return False
        if current_action_request is not None and current_action_request == closed_request:
            return False
        return state["action"]["status"] != "AWAITING_OUTCOME" or action_outcome_confirmed

    def close_step() -> None:
        nonlocal steps_done, closed_request
        closed_request = current_action_request
        play = state["play"]
        terminal = current_action_terminal or {}
        outcome = state["action"].get("outcome_observation")
        row = {
            "step": steps_done + 1,
            "action": current_action_id,
            "mask": current_action_mask,
            "duration_frames": max_action_frames,
            "status": state["action"]["status"],
            "result": int(terminal["result"]) if "result" in terminal else None,
            "reason": int(terminal["reason"]) if "reason" in terminal else None,
            "applied_mask": int(terminal["applied_mask"]) if "applied_mask" in terminal else None,
            "consumed_frames": (
                int(terminal["consumed_frames"]) if "consumed_frames" in terminal else None
            ),
            "first_frame": int(terminal["first_frame"]) if "first_frame" in terminal else None,
            "last_frame": int(terminal["last_frame"]) if "last_frame" in terminal else None,
            "outcome_observation": outcome,
            "outcome_frame": state["action"].get("outcome_frame"),
            "novel_outcome": bool(outcome is not None and outcome not in step_seen_outcomes),
            "physical_override_observed": bool(state["action"].get("physical_override_observed")),
            "selection_status": (state.get("selection") or {}).get("status"),
            "inquiry_status": (state.get("inquiry") or {}).get("status"),
            "inquiry_reason": (state.get("inquiry") or {}).get("reason"),
        }
        play["rows"].append(row)
        steps_done += 1
        play["completed"] = steps_done
        if row["physical_override_observed"]:
            play["physical_overrides"] = int(play["physical_overrides"]) + 1
        journal.observation({
            "kind": "play-step", "observed_at": _now(),
            "step": row["step"], "action": row["action"], "mask": row["mask"],
            "status": row["status"], "result": row["result"], "reason": row["reason"],
            "consumed_frames": row["consumed_frames"],
            "outcome_observation": row["outcome_observation"],
            "novel_outcome": row["novel_outcome"],
            "physical_override_observed": row["physical_override_observed"],
        })

    def gate_dropped() -> bool:
        terminal = current_action_terminal or {}
        if "reason" not in terminal:
            return False
        return int(terminal["reason"]) in (1, 2, 3)

    def retry_action(session: Mapping[str, Any]) -> None:
        nonlocal action_terminal, action_sent, action_outcome_confirmed
        nonlocal action_enable_sent, current_action_terminal, current_enable_request
        if not guard_ok():
            state["play"]["stop_reason"] = "foreground-lost"
            return
        journal.observation({
            "kind": "play-step-retry", "observed_at": _now(),
            "step": steps_done + 1, "action": current_action_id,
            "mask": current_action_mask, "reason": 1,
        })
        # The refused press never reached the game, so the step keeps its place
        # in the budget and is sent once more through a freshly enabled gate.
        action_terminal = False
        action_sent = False
        action_outcome_confirmed = False
        action_enable_sent = False
        current_action_terminal = None
        current_enable_request = None
        state["action"] = fresh_action_state()
        arm_action(session, current_action_id, current_action_mask)

    def arm_next_step(session: Mapping[str, Any]) -> None:
        nonlocal decision_attempted, action_terminal, action_sent, action_outcome_confirmed
        nonlocal action_enable_sent, current_action_id, current_action_mask
        nonlocal current_action_request, current_enable_request, current_action_terminal
        nonlocal closed_request, step_retried
        if not guard_ok():
            state["play"]["stop_reason"] = "foreground-lost"
            return
        dropped = gate_dropped()
        decision_attempted = False
        step_retried = False
        action_terminal = False
        action_sent = False
        action_outcome_confirmed = False
        closed_request = None
        current_action_id = None
        current_action_mask = None
        current_action_request = None
        current_action_terminal = None
        if dropped or not action_enable_sent:
            # A NotForeground/WrongGame/GateDisabled receipt clears the native
            # gate, so the next step re-establishes identity with its own ENABLE.
            action_enable_sent = False
            current_enable_request = None
        state["action"] = fresh_action_state()
        step_seen_outcomes = frozenset(state["learning"]["outcome_counts"])
        choose_and_enable(session)

    def stop_play(reason: str) -> None:
        play = state["play"]
        if play["stop_reason"] is None:
            play["stop_reason"] = reason
        if steps_done < steps and step_resolved():
            close_step()

    def physical_input_active() -> bool:
        return bool(last_physical_active)

    def invalidate_comparison(reason: str, *, close_control: bool = False) -> None:
        nonlocal baseline, ram, baseline_frame, snapshot_id, last_delta_frame
        nonlocal owner_ready
        _cancel_pending(reason)
        if close_control:
            try:
                client.close_control()
            except Exception:
                pass
        baseline = None
        ram = None
        baseline_frame = None
        snapshot_id = None
        last_delta_frame = None
        input_frames.clear()
        delta_frames.clear()
        delta_order.clear()
        reconciled_frames.clear()
        previous_input.clear()
        if owner_ready and current_session is not None:
            with field_lock:
                owner.bind_temporal(
                    op_id("rebind-unknown", current_session["stream_id"], current_session["vm_generation"], reason, state["gaps_observed"], state["resets_observed"]),
                    memory_id=memory_id,
                    participant_id=participant_id,
                    known_start=False,
                )
        journal.observation({
            "kind": "comparison-invalidated", "observed_at": _now(),
            "reason": reason,
            "session_id": current_session["session_id"].hex() if current_session else None,
            "stream_id": current_session["stream_id"].hex() if current_session else None,
        })

    def invalidate_input_history(reason: str) -> None:
        _cancel_pending(reason)
        if action_sent and not action_outcome_confirmed:
            state["action"]["status"] = "UNRESOLVED"
        input_frames.clear()
        delta_frames.clear()
        delta_order.clear()
        reconciled_frames.clear()
        previous_input.clear()
        if owner_ready and current_session is not None:
            with field_lock:
                owner.bind_temporal(
                    op_id(
                        "rebind-unknown", current_session["stream_id"],
                        current_session["vm_generation"], reason,
                        state["gaps_observed"], state["resets_observed"],
                    ),
                    memory_id=memory_id,
                    participant_id=participant_id,
                    known_start=False,
                )
        journal.observation({
            "kind": "input-history-invalidated", "observed_at": _now(),
            "reason": reason,
            "session_id": current_session["session_id"].hex() if current_session else None,
            "stream_id": current_session["stream_id"].hex() if current_session else None,
        })

    def reconcile_frame(frame_no: int) -> None:
        nonlocal action_outcome_confirmed
        if frame_no in reconciled_frames:
            return
        delta_row = delta_frames.get(frame_no)
        if delta_row is None or current_session is None:
            return
        first_input_frame = int(delta_row["previous_frame_no"])
        event_rows = [
            row
            for input_frame_no in sorted(input_frames)
            if first_input_frame <= input_frame_no < frame_no
            for row in input_frames[input_frame_no]
        ]
        if not event_rows:
            return
        input_frame_nos = sorted({
            int(row["payload"]["frame_no"]) for row in event_rows
        })

        virtual_rows = [
            row for row in event_rows
            if row["source_kind"] in ("virtual", "virtual-chord")
            or bool(int(row["payload"]["source_bits"]) & 0x02)
        ]
        if (
            action_sent and current_action_request is not None
            and current_action_mask is not None and virtual_rows
            and current_action_terminal is None
        ):
            # A sparse EE snapshot can arrive after the consumed pad samples.
            # Keep the interval pending until its native receipt proves them.
            return

        terminal = current_action_terminal
        receipt_authorized = (
            action_sent and current_action_request is not None
            and current_action_mask is not None and terminal is not None
            and int(terminal.get("result", -1)) == 0
            and int(terminal.get("consumed_frames", 0)) > 0
            and int(terminal.get("requested_mask", 0)) == current_action_mask
            and int(terminal.get("applied_mask", 0)) & current_action_mask == current_action_mask
        )
        matching_virtual = []
        if receipt_authorized:
            first_action_frame = int(terminal["first_frame"])
            last_action_frame = int(terminal["last_frame"])
            for row in virtual_rows:
                event = row["payload"]
                event_frame = int(event["frame_no"])
                consumed = (~int(event["active_low_buttons"])) & 0xFFFF
                if (
                    first_action_frame <= event_frame <= last_action_frame
                    and int(event["virtual_active_high_mask"]) & current_action_mask == current_action_mask
                    and consumed & current_action_mask == current_action_mask
                    and row["action_id"] == current_action_id
                ):
                    matching_virtual.append(row)
            matching_virtual = [
                row for row in matching_virtual
                if int(row["payload"]["frame_no"]) == last_action_frame
            ]
        physical_actions = [
            row for row in event_rows
            if row["source_kind"] in ("physical", "physical-chord")
            and row["action_id"] is not None
        ]
        if matching_virtual:
            if len(matching_virtual) != 1 or physical_actions:
                reconciled_frames.add(frame_no)
                journal.observation({
                    "frame_no": frame_no, "input_frame_nos": input_frame_nos,
                    "event_count": len(event_rows),
                    "reason": "virtual action coincided with another consumed control",
                })
                return
            reconciled_frames.add(frame_no)
            event_row = matching_virtual[0]
            event = event_row["payload"]
            input_frame_no = int(event["frame_no"])
            admit_transition(
                current_action_id,
                delta_row["observation_id"],
                frame_no,
                event,
                delta_row,
                "virtual-receipt-confirmed",
                request_id=current_action_request,
            )
            action_outcome_confirmed = True
            state["action"].update({
                "status": "CONFIRMED",
                "consumed_event": {
                    "input_frame_no": input_frame_no,
                    "frame_no": input_frame_no,
                    "sample_no": int(event["sample_no"]),
                    "slot": int(event["slot"]),
                    "source_bits": int(event["source_bits"]),
                    "active_low_buttons": int(event["active_low_buttons"]),
                    "virtual_active_high_mask": int(event["virtual_active_high_mask"]),
                },
                "outcome_observation": delta_row["observation_id"],
                "outcome_frame": frame_no,
            })
            journal.observation({
                "kind": "action-outcome-confirmed", "observed_at": _now(),
                "request_id": current_action_request.hex(),
                "input_frame_no": input_frame_no, "frame_no": frame_no,
                "mask": current_action_mask,
                "observation_id": delta_row["observation_id"],
                "source_revision_id": state["learning"]["last_source_revision_id"],
                "receipt": _receipt_summary(terminal),
            })
            return

        if virtual_rows and action_sent and current_action_request is not None:
            if terminal is None:
                return
            reconciled_frames.add(frame_no)
            journal.observation({
                "kind": "unmatched-virtual-input", "observed_at": _now(),
                "input_frame_nos": input_frame_nos, "frame_no": frame_no,
                "receipt": _receipt_summary(terminal),
            })
            return

        reconciled_frames.add(frame_no)
        if len(physical_actions) == 1 and not virtual_rows:
            event_row = physical_actions[0]
            admit_transition(
                event_row["action_id"], delta_row["observation_id"], frame_no,
                event_row["payload"], delta_row, event_row["source_kind"],
            )
        elif len(physical_actions) > 1 or (physical_actions and virtual_rows):
            journal.observation({
                "kind": "ambiguous-frame-input", "observed_at": _now(),
                "frame_no": frame_no, "input_frame_nos": input_frame_nos,
            })
    def on_delta(message: Any) -> None:
        nonlocal ram, snapshot_id, baseline_frame, last_delta_frame
        if ram is None or snapshot_id is None or baseline_frame is None:
            return
        payload = message.payload
        if payload["snapshot_id"] != snapshot_id:
            state["gaps_observed"] += 1
            invalidate_comparison("snapshot-id-mismatch")
            return
        frame_no = int(payload["frame_no"])
        if frame_no <= baseline_frame or (last_delta_frame is not None and frame_no <= last_delta_frame):
            state["gaps_observed"] += 1
            invalidate_comparison("non-increasing-frame")
            return
        page_count = len(ram) // PAGE_BYTES
        changed_pages: list[int] = []
        page_digests: list[dict[str, Any]] = []
        view = memoryview(ram)
        for page_index, data in payload["pages"]:
            page_index = int(page_index)
            if page_index >= page_count or not isinstance(data, memoryview) or len(data) != PAGE_BYTES:
                state["gaps_observed"] += 1
                invalidate_comparison("delta-page-out-of-range")
                return
            offset = page_index * PAGE_BYTES
            if view[offset:offset + PAGE_BYTES] != data:
                changed_pages.append(page_index)
                page_digests.append({
                    "page_index": page_index,
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
                view[offset:offset + PAGE_BYTES] = data
        page_digests.sort(key=lambda row: row["page_index"])
        observation = _observation_id(page_digests)
        observed_at = _now()
        previous_delta_frame = last_delta_frame
        delta_row = {
            "frame_no": frame_no,
            "previous_frame_no": previous_delta_frame,
            "observed_at": observed_at,
            "observation_id": observation,
            "changed_pages": tuple(changed_pages),
            "changed_regions": page_digests,
            "snapshot_id": f"{payload['snapshot_id']:016x}",
        }
        delta_frames[frame_no] = delta_row
        delta_order.append(frame_no)
        last_delta_frame = frame_no
        state["frames_observed"] += 1
        state["first_frame"] = frame_no if state["first_frame"] is None else state["first_frame"]
        state["last_frame"] = frame_no
        journal.observation({
            "kind": "ee-delta-observation", "observed_at": observed_at,
            "session_id": current_session["session_id"].hex() if current_session else None,
            "stream_id": current_session["stream_id"].hex() if current_session else None,
            "vm_generation": int(current_session["vm_generation"]) if current_session else None,
            "frame_no": frame_no,
            "snapshot_id": f"{payload['snapshot_id']:016x}",
            "state_sha256_at_baseline": state["baseline_sha256"],
            "observation_id": observation,
            "changed_page_count": len(changed_pages),
            "selected_page_signatures": page_digests[:16],
            "changed_regions": page_digests,
        })
        reconcile_frame(frame_no)
        while len(delta_order) > 4:
            old_frame = delta_order.pop(0)
            delta_frames.pop(old_frame, None)
            reconciled_frames.discard(old_frame)
        if delta_order:
            oldest_input_frame = min(
                int(delta_frames[delta_frame]["previous_frame_no"])
                for delta_frame in delta_order
            )
            for old_input_frame in tuple(input_frames):
                if old_input_frame < oldest_input_frame:
                    input_frames.pop(old_input_frame, None)

    def on_input(message: Any) -> None:
        nonlocal last_physical_active
        payload = dict(message.payload)
        state["input_events_observed"] += 1
        frame_no = int(payload["frame_no"])
        slot = int(payload["slot"])
        previous = previous_input.get(slot)
        raw_action_id, source_kind = _event_action(payload, previous)
        action_id, source_kind = bind_event_action(raw_action_id, source_kind)
        previous_input[slot] = payload
        chord_binding = chord_codec.binding_for_action(action_id) if action_id else None
        journal.observation({
            "kind": "consumed-input-event", "observed_at": _now(),
            "session_id": current_session["session_id"].hex() if current_session else None,
            "stream_id": current_session["stream_id"].hex() if current_session else None,
            "frame_no": frame_no, "sample_no": int(payload["sample_no"]),
            "slot": slot, "source_bits": int(payload["source_bits"]),
            "active_low_buttons": int(payload["active_low_buttons"]),
            "physical_active_low_buttons": int(payload["physical_active_low_buttons"]),
            "virtual_active_high_mask": int(payload["virtual_active_high_mask"]),
            "lx": int(payload["lx"]), "ly": int(payload["ly"]),
            "rx": int(payload["rx"]), "ry": int(payload["ry"]),
            "raw_action_id": raw_action_id,
            "action_id": action_id, "source_kind": source_kind,
            "chord_binding": dict(chord_binding) if chord_binding is not None else None,
        })
        if slot == 0 and state["input_events_observed"] <= MAX_PENDING_EVENTS:
            rows = input_frames.setdefault(frame_no, [])
            if len(rows) < 4:
                rows.append({
                    "payload": payload,
                    "action_id": action_id,
                    "source_kind": source_kind,
                    "sequence": int(message.sequence),
                })
            for delta_frame, delta_row in tuple(delta_frames.items()):
                if (
                    int(delta_row["previous_frame_no"]) <= frame_no < delta_frame
                ):
                    reconcile_frame(delta_frame)
        elif state["input_events_observed"] > MAX_PENDING_EVENTS:
            raise NativeBridgeError("consumed input evidence exceeded the bounded event limit")

        physical_active = _physical_active(payload)
        last_physical_active = bool(bool(int(payload["source_bits"]) & 0x01) and physical_active)
        previous_physical_active = (
            previous is not None
            and bool(int(previous["source_bits"]) & 0x01)
            and _physical_active(previous)
        )
        physical_release_to_idle = previous_physical_active and not physical_active
        if (
            action_enable_sent and not action_terminal
            and (
                (bool(int(payload["source_bits"]) & 0x01) and physical_active)
                or physical_release_to_idle
            )
        ):
            _cancel_pending("physical-override")
            state["action"]["physical_override_observed"] = True

    def on_receipt(message: Any) -> None:
        nonlocal action_terminal, action_enable_sent, current_action_terminal
        payload = message.payload
        receipt_id = payload["request_id"]
        if current_enable_request is not None and receipt_id == current_enable_request:
            state["action"]["enable_receipt"] = _receipt_summary(payload)
            if int(payload["result"]) == 3:
                action_enable_sent = True
                state["action"]["status"] = "ENABLED"
                send_selected_action(current_session or {})
            else:
                state["action"]["status"] = "REJECTED"
                action_terminal = True
                state["action"]["enable_rejection_reason_code"] = int(payload["reason"])
            journal.observation({
                "kind": "enable-receipt", "observed_at": _now(),
                "receipt": _receipt_summary(payload),
            })
            return
        if current_action_request is None or receipt_id != current_action_request:
            journal.observation({
                "kind": "unmatched-action-receipt", "observed_at": _now(),
                "receipt": _receipt_summary(payload),
            })
            return
        if int(payload["result"]) == 3:
            journal.observation({
                "kind": "unexpected-enable-receipt", "observed_at": _now(),
                "receipt": _receipt_summary(payload),
            })
            return
        current_action_terminal = dict(payload)
        action_terminal = True
        state["action"]["terminal_receipt"] = _receipt_summary(payload)
        result_code = int(payload["result"])
        if result_code == 0:
            if int(payload["consumed_frames"]) > 0:
                state["action"]["status"] = "AWAITING_OUTCOME"
            else:
                state["action"]["status"] = "COMPLETED_UNCONFIRMED"
        elif result_code == 1:
            state["action"]["status"] = "CANCELLED"
        elif result_code == 2:
            state["action"]["status"] = "REJECTED"
        elif result_code == 4:
            state["action"]["status"] = "EXPIRED"
        journal.observation({
            "kind": "action-terminal-receipt", "observed_at": _now(),
            "receipt": _receipt_summary(payload),
        })
        if (
            result_code == 0 and int(payload["consumed_frames"]) > 0
            and int(payload["requested_mask"]) == current_action_mask
            and int(payload["applied_mask"]) & current_action_mask == current_action_mask
        ):
            for delta_frame in tuple(delta_frames):
                reconcile_frame(delta_frame)

    def process_session(payload: Mapping[str, Any]) -> None:
        nonlocal current_session, expected_reset, baseline, ram
        nonlocal baseline_frame, snapshot_id, last_delta_frame, owner_ready
        session_id = payload["session_id"]
        stream_id = payload["stream_id"]
        _hex_identity(session_id, "session_id")
        stream_hex = _hex_identity(stream_id, "stream_id")
        if (
            int(payload["producer_pid"]) != expected_pid
            or int(getattr(client, "stream_server_pid", 0) or 0) != expected_pid
        ):
            raise NativeBridgeError("SESSION/pipe producer PID does not match the bound foreground PCSX2 PID")
        if payload["serial"] != expected_serial:
            raise NativeBridgeError("native SESSION serial does not match the authorized atlas")
        if int(payload["current_crc"]) != expected_crc_value:
            raise NativeBridgeError("native SESSION current CRC does not match the authorized atlas")
        if expected_reset is not None and (stream_id, int(payload["vm_generation"])) != expected_reset:
            raise NativeBridgeError("post-reset SESSION does not match the announced stream/generation")
        if current_session is not None:
            same_stream = current_session["stream_id"] == stream_id
            if not same_stream:
                invalidate_comparison("session-stream-change", close_control=True)
                state["resets_observed"] += 1
                owner_ready = owner_ready
        current_session = dict(payload)
        expected_reset = None
        state["session_id"] = session_id.hex()
        state["identity"] = {
            "serial": payload["serial"],
            "title": payload["title"],
            "disc_crc": int(payload["disc_crc"]),
            "current_crc": int(payload["current_crc"]),
            "producer_pid": int(payload["producer_pid"]),
            "vm_generation": int(payload["vm_generation"]),
            "ram_size": int(payload["ram_size"]),
            "page_size": int(payload["page_size"]),
            "session_id": session_id.hex(),
            "stream_id": stream_hex,
        }
        if int(payload["ram_size"]) > MAX_RAM_BYTES or int(payload["ram_size"]) % PAGE_BYTES:
            raise NativeBridgeError("SESSION EE RAM size exceeds the field loop bound")
        baseline = None
        ram = None
        baseline_frame = None
        snapshot_id = None
        last_delta_frame = None
        delta_order.clear()
        journal.observation({
            "kind": "native-session", "observed_at": _now(),
            "identity": dict(state["identity"]),
        })

    try:
        if getattr(client, "stream_server_pid", None) is None:
            client.connect_stream()
        if int(getattr(client, "stream_server_pid", 0) or 0) != expected_pid:
            raise NativeBridgeError("stream pipe is not owned by the bound foreground PCSX2 PID")
        stream_ready = True

        while state["messages_received"] < max_messages:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if steps_done > 0:
                    stop_play("physical-priority" if state["play"]["paused"] else "deadline")
                    break
                if (
                    steps > 1 and state["frames_observed"] >= samples
                    and not state["action"]["requested"]
                ):
                    # A bounded play session can end honestly without an act:
                    # the field had nothing to acquire toward in this window.
                    stop_play("no-selection")
                    break
                raise_field("timeout", "native field stream exceeded its bounded deadline")
            if action_sent and not action_terminal and not guard_ok():
                _cancel_pending("foreground-lost")
            try:
                message = client.receive(timeout=min(remaining, 2.0))
            except NativeBridgeTimeout as exc:
                if reconnect_used or time.monotonic() >= deadline:
                    raise_field("native-timeout", "native field stream timed out before the bounded sample completed")
                reconnect_used = True
                state["reconnects"] += 1
                if action_sent and not action_terminal:
                    _cancel_pending("stream-timeout")
                    state["action"]["status"] = "UNRESOLVED"
                invalidate_comparison("stream-timeout", close_control=True)
                client.connect_stream()
                if int(getattr(client, "stream_server_pid", 0) or 0) != expected_pid:
                    raise_field("producer-pid-mismatch", "reconnected stream is not owned by the bound foreground PCSX2 PID")
                journal.observation({
                    "kind": "stream-reconnected", "observed_at": _now(),
                    "error": type(exc).__name__,
                })
                continue
            except NativeBridgeError as exc:
                if reconnect_used or time.monotonic() >= deadline:
                    raise_field("native-bridge-error", f"native bridge failed: {type(exc).__name__}")
                journal.observation({
                    "kind": "stream-error", "observed_at": _now(),
                    "error": type(exc).__name__, "message": str(exc)[:240],
                })
                reconnect_used = True
                state["reconnects"] += 1
                if action_sent and not action_terminal:
                    _cancel_pending("stream-disconnected")
                    state["action"]["status"] = "UNRESOLVED"
                invalidate_comparison("stream-disconnected", close_control=True)
                try:
                    client.connect_stream()
                except Exception as connect_exc:
                    raise_field("reconnect-failed", f"native stream reconnect failed: {type(connect_exc).__name__}")
                continue

            state["messages_received"] += 1
            offset, raw_length = journal.write_frame(message.raw)
            journal.observation({
                "kind": "native-message", "observed_at": _now(),
                "sequence": int(message.sequence), "message_type": int(message.type),
                "sequence_gap": bool(message.sequence_gap),
                "raw_offset": offset, "raw_length": raw_length,
            })
            if message.sequence_gap:
                state["gaps_observed"] += 1
                invalidate_comparison("producer-sequence-gap")

            payload = message.payload
            if message.type == SESSION:
                process_session(payload)
            elif message.type == GAP:
                state["gaps_observed"] += 1
                gap_reason = int(payload["reason"])
                if gap_reason == GAP_OUTPUT_QUEUE_FULL:
                    # Lost pad/receipt events break temporal pairing; the independent
                    # EE snapshot chain remains valid and continues from its delta base.
                    invalidate_input_history("native-output-queue-gap")
                else:
                    invalidate_comparison("native-gap")
                journal.observation({
                    "kind": "native-gap", "observed_at": _now(),
                    "first_frame": int(payload["first_frame"]),
                    "last_frame": int(payload["last_frame"]),
                    "reason": gap_reason,
                })
            elif message.type == VM_RESET:
                state["resets_observed"] += 1
                _cancel_pending("vm-reset")
                expected_reset = (payload["new_stream_id"], int(payload["vm_generation"]))
                invalidate_comparison("vm-reset", close_control=True)
                journal.observation({
                    "kind": "vm-reset", "observed_at": _now(),
                    "old_stream_id": payload["old_stream_id"].hex(),
                    "new_stream_id": payload["new_stream_id"].hex(),
                    "vm_generation": int(payload["vm_generation"]),
                    "frame_no": int(payload["frame_no"]),
                    "reason": int(payload["reason"]),
                })
            elif message.type == BASELINE_CHUNK:
                if current_session is None:
                    raise NativeBridgeError("baseline arrived before a validated SESSION")
                if baseline is None:
                    baseline = _BaselineAssembly(payload)
                    if baseline.total != int(current_session["ram_size"]):
                        raise NativeBridgeError("baseline RAM length does not match its SESSION")
                if baseline.add(payload):
                    ram = baseline.complete()
                    baseline_frame = baseline.frame_no
                    snapshot_id = baseline.snapshot_id
                    last_delta_frame = baseline_frame
                    state["baseline_sha256"] = hashlib.sha256(ram).hexdigest()
                    journal.observation({
                        "kind": "ee-baseline-complete", "observed_at": _now(),
                        "session_id": current_session["session_id"].hex(),
                        "stream_id": current_session["stream_id"].hex(),
                        "vm_generation": int(current_session["vm_generation"]),
                        "frame_no": baseline_frame,
                        "snapshot_id": f"{snapshot_id:016x}",
                        "ram_size": len(ram),
                        "baseline_sha256": state["baseline_sha256"],
                        "chunk_count": baseline.chunk_count,
                    })
                    ensure_temporal_owner(current_session)
                    choose_and_enable(current_session)
                    for old_frame in tuple(input_frames):
                        if old_frame < baseline_frame:
                            input_frames.pop(old_frame, None)
            elif message.type == DELTA:
                on_delta(message)
            elif message.type == INPUT_EVENT:
                on_input(message)
            elif message.type == ACTION_RECEIPT:
                on_receipt(message)
            else:
                raise NativeBridgeError("native stream emitted an unsupported message type")
            if state["action"].get("enable_rejection_reason_code") is not None:
                reason_code = state["action"]["enable_rejection_reason_code"]
                if steps > 1:
                    # A refused gate cannot carry this session's presses; the
                    # play session reports it instead of failing the operation.
                    state["play"]["stop_reason"] = _gate_refusal_reason(reason_code)
                    break
                raise_field(
                    "action-enable-rejected",
                    f"native ENABLE_ACTIONS rejected the request with reason code {reason_code}",
                )

            if allow_actions and state["play"]["paused"] and not physical_input_active():
                state["play"]["paused"] = False
                if steps_done < steps and current_session is not None:
                    arm_next_step(current_session)

            if (
                allow_actions and steps_done < steps and not state["play"]["paused"]
                and owner_ready and not decision_attempted and not action_sent
                and current_session is not None and time.monotonic() >= selection_retry_at
            ):
                # A play session begins as soon as the field is ready: it
                # acquires toward a consequence its memory already holds, or
                # explores the least-tried control to observe its first one.
                selection_retry_at = time.monotonic() + 1.0
                choose_and_enable(current_session)

            if allow_actions and steps_done < steps and step_resolved():
                terminal = current_action_terminal or {}
                reason_code = int(terminal["reason"]) if "reason" in terminal else 0
                result_code = int(terminal["result"]) if "result" in terminal else None
                if result_code == 2 and reason_code == 1 and not step_retried and guard_ok():
                    # The gate dropped before this press reached the game, so the
                    # step keeps its place in the budget and is sent once more.
                    step_retried = True
                    retry_action(current_session or {})
                else:
                    close_step()
                    if steps_done < steps:
                        if reason_code == 4:
                            # The human took the pad: wait for it to go idle again.
                            state["play"]["paused"] = True
                        elif reason_code == 3 or not guard_ok():
                            state["play"]["stop_reason"] = "foreground-lost"
                        elif result_code == 2 or (result_code == 1 and reason_code == 2):
                            # The native side refused this press, so the step's
                            # action never reached the game.
                            state["play"]["stop_reason"] = _gate_refusal_reason(reason_code)
                        else:
                            arm_next_step(current_session or {})
                        if state["play"]["stop_reason"] is not None:
                            break

            if state["frames_observed"] >= samples:
                if not allow_actions or (steps == 1 and not state["action"]["requested"]):
                    break
                if steps_done >= steps:
                    break

        else:
            if steps_done > 0:
                stop_play("message-bound")
            else:
                raise_field("message-bound", "native field stream exceeded its bounded message count")

        if state["frames_observed"] < samples and state["play"]["stop_reason"] is None:
            raise_field("insufficient-samples", "native field stream ended before the requested delta sample count")
        if allow_actions and state["action"]["status"] == "AWAITING_OUTCOME" and state["play"]["stop_reason"] is None:
            raise_field("action-outcome-unconfirmed", "terminal action receipt lacks a matching consumed input event and successor frame")
        if allow_actions and state["action"]["status"] == "UNRESOLVED":
            raise_field("action-unresolved", "action outcome is unresolved after stream loss")
        if allow_actions and steps_done < steps:
            stop_play("step-budget-incomplete")
        if allow_actions and action_sent and not action_terminal:
            _cancel_pending("play-stop")
        state["status"] = "COMPLETE"
        state["reason"] = None
        state["artifacts"] = current_artifacts()
        state["artifact"] = dict(state["artifacts"]["raw"])
        state["observation_artifact"] = dict(state["artifacts"]["observations"])
        state["control_artifact"] = dict(state["artifacts"]["control"])
        state["elapsed_seconds"] = round(max(0.0, time.monotonic() - started), 6)
        journal.close()
        state["result_path"] = journal.write_result(state)
        return state

    except FieldLoopError:
        raise
    except Exception as exc:
        _cancel_pending(f"exception-{type(exc).__name__}")
        journal.observation({
            "kind": "field-loop-error", "observed_at": _now(),
            "error_type": type(exc).__name__,
        })
        journal.close()
        result = result_mapping("PARTIAL", "field-loop-error")
        result["error_type"] = type(exc).__name__
        result["artifact"] = dict(result["artifacts"]["raw"])
        result["observation_artifact"] = dict(result["artifacts"]["observations"])
        result["control_artifact"] = dict(result["artifacts"]["control"])
        result_path = journal.write_result(result)
        result["result_path"] = result_path
        raise FieldLoopError("field-loop-error", f"field loop failed: {type(exc).__name__}", result) from exc
    finally:
        if stream_ready and not journal._closed:
            try:
                journal.close()
            except Exception:
                pass
        # A later run must reach a fresh native control/stream instance; leaving
        # these handles open pins the producer's accept loops to this consumer.
        try:
            client.close()
        except Exception:
            pass


__all__ = ["FieldLoopError", "run_field_loop"]
