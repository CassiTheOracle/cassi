from __future__ import annotations

import json
import threading
from types import SimpleNamespace

from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner
from pcsx2.field import run_field_loop
from pcsx2.native_bridge import (
    BASELINE_CHUNK,
    DELTA,
    INPUT_EVENT,
    PAGE_BYTES,
    SESSION,
    NativeMessage,
)


class ScriptedNativeClient:
    def __init__(self, messages):
        self._messages = list(messages)
        self._expected_server_pid = 4242
        self.stream_server_pid = 4242

    def receive(self, timeout):
        assert self._messages, "field loop consumed beyond its two-delta bound"
        return self._messages.pop(0)


def _message(message_type, sequence, payload):
    return NativeMessage(
        type=message_type,
        sequence=sequence,
        payload=payload,
        raw=f"native-message-{sequence}".encode("ascii"),
    )


def _pad_event(frame_no, sample_no, active_low_buttons):
    return {
        "frame_no": frame_no,
        "sample_no": sample_no,
        "slot": 0,
        "source_bits": 0x01,
        "active_low_buttons": active_low_buttons,
        "physical_active_low_buttons": active_low_buttons,
        "virtual_active_high_mask": 0,
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


def _frame_label(source, prefix):
    matches = [label for label in source.labels if label.startswith(prefix)]
    assert len(matches) == 1
    return int(matches[0].removeprefix(prefix))


def test_run_field_loop_pairs_physical_edges_across_half_open_sparse_deltas(tmp_path):
    ram = bytes(PAGE_BYTES)
    messages = [
        _message(SESSION, 1, {
            "session_id": b"s" * 16,
            "stream_id": b"t" * 16,
            "producer_pid": 4242,
            "serial": "SLUS-20111",
            "current_crc": 0x1A2B3C4D,
            "title": "Sparse interval test",
            "disc_crc": 0x1A2B3C4D,
            "vm_generation": 1,
            "ram_size": PAGE_BYTES,
            "page_size": PAGE_BYTES,
        }),
        _message(BASELINE_CHUNK, 2, {
            "snapshot_id": 7,
            "frame_no": 0,
            "total_ram_size": PAGE_BYTES,
            "chunk_count": 1,
            "chunk_index": 0,
            "offset": 0,
            "data": memoryview(ram),
        }),
        _message(INPUT_EVENT, 3, _pad_event(60, 1, 0xFFFE)),
        _message(DELTA, 4, _delta(120, 1)),
        _message(INPUT_EVENT, 5, _pad_event(120, 2, 0xFFFF)),
        _message(DELTA, 6, _delta(240, 2)),
    ]
    atlas = SimpleNamespace(identity={
        "serial": "SLUS-20111",
        "pcsx2_crc": "1A2B3C4D",
    })

    # One PCSX2 temporal memory reserves tens of MiB of tensor state, so the
    # hosted entity raises its ceiling from the 64 MiB default; match that here.
    limits = CapacityLimits(max_state_bytes=1 << 30, max_workspace_bytes=1 << 30)
    with FieldIntelligenceOwner(tmp_path / "owner", limits=limits) as owner:
        result = run_field_loop(
            client=ScriptedNativeClient(messages),
            owner=owner,
            field_lock=threading.RLock(),
            atlas=atlas,
            program_id="sparse-delta-test",
            operation_id="sparse-delta-edges",
            artifact_home=tmp_path / "artifacts",
            expected_serial="SLUS-20111",
            expected_crc=0x1A2B3C4D,
            samples=2,
            allow_actions=False,
            foreground_guard=lambda: True,
        )

        assert result["status"] == "COMPLETE"
        assert result["frames_observed"] == 2
        assert result["learning"]["transitions"] == 2

        temporal = owner.state.temporal(result["memory_id"])
        observed_pairs = []
        for revision_id in temporal.source_revision_ids:
            source = owner.evidence.source(revision_id)
            episode = json.loads(owner.evidence.read(source))
            observed_pairs.append((
                episode["steps"][0]["action"],
                _frame_label(source, "native-input-frame-"),
                _frame_label(source, "native-frame-"),
            ))

        assert sorted(observed_pairs) == [
            ("pad-press-0001", 60, 120),
            ("pad-release-0001", 120, 240),
        ]
