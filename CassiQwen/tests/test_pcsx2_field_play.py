from __future__ import annotations

import threading
from types import SimpleNamespace

from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner
from pcsx2.field import run_field_loop
from pcsx2.native_bridge import (
    ACTION_RECEIPT,
    BASELINE_CHUNK,
    DELTA,
    INPUT_EVENT,
    PAGE_BYTES,
    SESSION,
    NativeMessage,
)

SERIAL = "SLUS-20111"
CRC = 0x1A2B3C4D


def _message(message_type, sequence, payload):
    return NativeMessage(
        type=message_type,
        sequence=sequence,
        payload=payload,
        raw=f"native-message-{sequence}".encode("ascii"),
    )


def _pad_event(frame_no, sample_no, active_low_buttons, *, source_bits=0x01,
               virtual_mask=0, physical_low=None):
    return {
        "frame_no": frame_no,
        "sample_no": sample_no,
        "slot": 0,
        "source_bits": source_bits,
        "active_low_buttons": active_low_buttons,
        "physical_active_low_buttons": (
            active_low_buttons if physical_low is None else physical_low
        ),
        "virtual_active_high_mask": virtual_mask,
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
    }


def _delta(frame_no, first_byte):
    page = bytearray(PAGE_BYTES)
    page[0] = first_byte
    return {
        "snapshot_id": 7,
        "frame_no": frame_no,
        "pages": [(0, memoryview(bytes(page)))],
    }


def _receipt(request_id, result, reason, *, mask=0, frames=0, consumed=0,
             first_frame=0, last_frame=0):
    return {
        "request_id": request_id,
        "result": result,
        "reason": reason,
        "requested_mask": mask,
        "applied_mask": mask if result == 0 else 0,
        "requested_frames": frames,
        "consumed_frames": consumed,
        "first_frame": first_frame,
        "last_frame": last_frame,
        "first_active_low_buttons": 0xFFFF,
        "last_active_low_buttons": 0xFFFF,
        "source_bits": 0,
    }


class ScriptedPlayClient:
    """Answer each control frame with the native stream the loop expects.

    ``cancels`` maps a 1-based action ordinal to the cancel reason the emulated
    producer reports instead of applying the virtual press.
    """

    def __init__(self, *, samples, frame_step=120, cancels=None, physical_after=None,
                 human_edges=False):
        self._expected_server_pid = 4242
        self.stream_server_pid = 4242
        self._sequence = 0
        self._frame = 0
        self._samples = samples
        self._frame_step = frame_step
        self._cancels = dict(cancels or {})
        self._physical_after = set(physical_after or ())
        self._human_edges = human_edges
        self._messages = []
        self.actions = []
        self.enables = []
        self.cancels_sent = []
        self.controls_closed = 0
        self._baseline_sent = False

    # -- producer stream ------------------------------------------------------
    def _emit(self, message_type, payload):
        self._sequence += 1
        self._messages.append(_message(message_type, self._sequence, payload))

    def _emit_delta(self):
        self._frame += self._frame_step
        self._emit(DELTA, _delta(self._frame, 1 + (self._frame % 251)))

    def _emit_baseline(self):
        self._baseline_sent = True
        self._emit(SESSION, {
            "session_id": b"s" * 16,
            "stream_id": b"t" * 16,
            "producer_pid": 4242,
            "serial": SERIAL,
            "current_crc": CRC,
            "title": "Field play test",
            "disc_crc": CRC,
            "vm_generation": 1,
            "ram_size": PAGE_BYTES,
            "page_size": PAGE_BYTES,
        })
        self._emit(BASELINE_CHUNK, {
            "snapshot_id": 7,
            "frame_no": 0,
            "total_ram_size": PAGE_BYTES,
            "chunk_count": 1,
            "chunk_index": 0,
            "offset": 0,
            "data": memoryview(bytes(PAGE_BYTES)),
        })
        # One human press gives the field an observed consequence to acquire
        # toward, exactly as an earlier session would. Each native frame
        # interval carries one consumed edge, so the press and its release are
        # observed separately.
        if self._human_edges:
            self._emit(INPUT_EVENT, _pad_event(self._frame + 60, 1, 0xFFFE))
            self._emit_delta()
            self._emit(INPUT_EVENT, _pad_event(self._frame + 60, 2, 0xFFFF))
            self._emit_delta()

    def receive(self, *, timeout=None):
        if not self._baseline_sent:
            self._emit_baseline()
        if not self._messages:
            self._emit_delta()
        return self._messages.pop(0)

    # -- control --------------------------------------------------------------
    def connect_stream(self):
        return None

    def connect_control(self, session):
        return None

    def close_control(self):
        self.controls_closed += 1

    def close_stream(self):
        return None

    def close(self):
        return None

    def send_enable_actions(self, session_id, stream_id, request_id, *,
                            expected_serial, expected_current_crc, before_send=None):
        if before_send is not None:
            before_send(b"enable")
        self.enables.append(request_id.hex())
        self._emit(ACTION_RECEIPT, _receipt(request_id, 3, 0))
        return b""

    def send_action(self, session_id, stream_id, request_id, mask, duration_frames, *,
                    before_send=None):
        if before_send is not None:
            before_send(b"action")
        ordinal = len(self.actions) + 1
        self.actions.append({"mask": mask, "frames": duration_frames,
                             "request_id": request_id.hex()})
        if ordinal in self._physical_after:
            # A human press lands inside the armed window.
            self._frame += 10
            self._emit(INPUT_EVENT, _pad_event(self._frame, ordinal + 1, 0xFFBF))
            self._emit(ACTION_RECEIPT, _receipt(request_id, 1, 4, mask=mask,
                                                frames=duration_frames))
            self._emit(INPUT_EVENT, _pad_event(self._frame + 20, ordinal + 2, 0xFFFF))
            self._emit_delta()
            return b""
        reason = self._cancels.get(ordinal)
        if reason is not None:
            self._emit(ACTION_RECEIPT, _receipt(request_id, 1, reason, mask=mask,
                                                frames=duration_frames))
            self._emit_delta()
            return b""
        last_frame = self._frame + duration_frames
        self._emit(ACTION_RECEIPT, _receipt(
            request_id, 0, 0, mask=mask, frames=duration_frames,
            consumed=duration_frames, first_frame=self._frame + 1, last_frame=last_frame,
        ))
        self._emit(INPUT_EVENT, _pad_event(
            last_frame, ordinal + 1, (~mask) & 0xFFFF, source_bits=0x02,
            virtual_mask=mask, physical_low=0xFFFF,
        ))
        self._frame = last_frame
        self._emit_delta()
        return b""

    def send_cancel(self, session_id, stream_id, request_id, *, before_send=None):
        if before_send is not None:
            before_send(b"cancel")
        self.cancels_sent.append(request_id.hex())
        return b""


def _owner(tmp_path):
    # One PCSX2 temporal memory reserves tens of MiB of tensor state, so the
    # hosted entity raises its ceiling from the 64 MiB default; match that here.
    limits = CapacityLimits(max_state_bytes=1 << 30, max_workspace_bytes=1 << 30)
    return FieldIntelligenceOwner(tmp_path / "owner", limits=limits)


def _loop(tmp_path, owner, client, *, samples, steps, allow_actions=True,
          timeout_seconds=30.0, guard=lambda: True, max_action_frames=30,
          operation_id="field-play-test"):
    atlas = SimpleNamespace(identity={"serial": SERIAL, "pcsx2_crc": "1A2B3C4D"})
    return run_field_loop(
        client=client,
        owner=owner,
        field_lock=threading.RLock(),
        atlas=atlas,
        program_id="field-play-test",
        operation_id=operation_id,
        artifact_home=tmp_path / "artifacts",
        expected_serial=SERIAL,
        expected_crc=CRC,
        samples=samples,
        allow_actions=allow_actions,
        foreground_guard=guard,
        timeout_seconds=timeout_seconds,
        max_action_frames=max_action_frames,
        steps=steps,
    )


def _learn_a_consequence(tmp_path, owner):
    """An earlier bounded session leaves one observed consequence behind."""
    return _loop(
        tmp_path, owner, ScriptedPlayClient(samples=2, human_edges=True),
        samples=2, steps=1, allow_actions=False, operation_id="field-play-learn",
    )


def test_field_play_runs_a_sequence_of_field_selected_actions(tmp_path):
    client = ScriptedPlayClient(samples=3)
    with _owner(tmp_path) as owner:
        learned = _learn_a_consequence(tmp_path, owner)
        assert learned["learning"]["transitions"] == 2

        result = _loop(tmp_path, owner, client, samples=3, steps=3)

        assert result["status"] == "COMPLETE"
        assert result["play"]["steps"] == 3
        assert result["play"]["completed"] == 3
        assert result["play"]["stop_reason"] is None
        assert len(result["play"]["rows"]) == 3
        assert [row["status"] for row in result["play"]["rows"]] == ["CONFIRMED"] * 3
        assert all(row["result"] == 0 for row in result["play"]["rows"])
        assert all(row["consumed_frames"] == 30 for row in result["play"]["rows"])
        assert all(row["outcome_observation"] for row in result["play"]["rows"])
        assert all(row["novel_outcome"] is True for row in result["play"]["rows"])
        assert all(row["inquiry_status"] == "acquiring" for row in result["play"]["rows"])
        assert len({row["action"] for row in result["play"]["rows"]}) == 3
        assert len(client.actions) == 3
        # The native gate stays enabled across steps, so one ENABLE serves them.
        assert len(client.enables) == 1
        assert client.cancels_sent == []
        assert result["learning"]["transitions"] == 3
        assert result["learning"]["action_counts"]
        assert result["action"]["status"] == "CONFIRMED"
        assert owner.state.temporal(result["memory_id"]) is not None


def test_field_play_pauses_for_physical_input_and_stops_on_focus_loss(tmp_path):
    client = ScriptedPlayClient(samples=2, cancels={2: 3}, physical_after={1})
    with _owner(tmp_path) as owner:
        _learn_a_consequence(tmp_path, owner)
        result = _loop(tmp_path, owner, client, samples=2, steps=3)

        assert result["status"] == "COMPLETE"
        rows = result["play"]["rows"]
        assert rows[0]["status"] == "CANCELLED"
        assert rows[0]["reason"] == 4
        assert rows[0]["physical_override_observed"] is True
        assert result["play"]["physical_overrides"] == 1
        assert len(client.cancels_sent) == 1
        # A NotForeground receipt clears the native gate, so the run stops with
        # an explicit reason instead of arming another press.
        assert rows[1]["reason"] == 3
        assert result["play"]["completed"] == 2
        assert result["play"]["stop_reason"] == "foreground-lost"
        assert len(client.enables) == 1


def test_field_play_explores_a_control_when_its_memory_is_empty(tmp_path):
    """A field with no observed consequence yet explores, then acquires."""
    client = ScriptedPlayClient(samples=3)
    with _owner(tmp_path) as owner:
        result = _loop(tmp_path, owner, client, samples=3, steps=3,
                       operation_id="field-play-cold")

        assert result["status"] == "COMPLETE"
        rows = result["play"]["rows"]
        assert [row["status"] for row in rows] == ["CONFIRMED"] * 3
        assert rows[0]["inquiry_status"] == "exploring"
        assert rows[0]["inquiry_reason"] == "no-observed-successor-goal"
        # The least-tried control is the alphabetically first candidate, whose
        # mask is therefore the smallest one this session sends.
        assert rows[0]["mask"] == min(record["mask"] for record in client.actions)
        # The explored outcome becomes the goal the remaining steps acquire toward.
        assert [row["inquiry_status"] for row in rows[1:]] == ["acquiring", "acquiring"]
        assert len({row["action"] for row in rows}) >= 2
        assert result["learning"]["transitions"] == 3


def test_field_play_requires_actions_and_bounded_steps(tmp_path):
    client = ScriptedPlayClient(samples=1)
    with _owner(tmp_path) as owner:
        for steps, allow_actions in ((0, True), (65, True), (2, False)):
            try:
                _loop(tmp_path, owner, client, samples=1, steps=steps,
                      allow_actions=allow_actions, operation_id="field-play-bounds")
            except ValueError:
                continue
            raise AssertionError(f"steps={steps} allow_actions={allow_actions} should have been refused")
