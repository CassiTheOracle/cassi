from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from cassi_qi_boundary import QiBoundaryCommitAStore, QiBoundaryPacket, QiIngressJournal, passive_egress_receipt
from cassi_qi_bootstrap import canonical_hash
from cassi_qi_clock import QiCausalClock, QiClockTime, QiSourceCadence, QiSourceScope, QiWatermark

D0 = "0" * 64
D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64


def _fixture() -> tuple[QiCausalClock, QiSourceScope, QiBoundaryPacket]:
    scope = QiSourceScope("epoch-0", "sensor", D0)
    clock = QiCausalClock.create(
        tau_0=QiClockTime(1, 1),
        field_interval=QiClockTime(1, 2),
        field_steps_per_world_tick=2,
        sources=(QiSourceCadence(scope, QiClockTime(1, 3), QiClockTime(0, 1), 0),),
        max_clock_lcm=64,
    )
    capture_end = clock.expected_capture(scope, 0)[1]
    packet = QiBoundaryPacket.create(
        clock=clock,
        scope=scope,
        profile_sha256=D1,
        watermark_sha256=D2,
        ingress_journal_sha256=D3,
        source_sequence=0,
        cycle_frontier=capture_end,
        payload_shape=(2,),
        payload_dtype="uint8",
        payload=b"xy",
    )
    return clock, scope, packet


def run(*, evidence_path: str | Path = "_diag/cassi_qi_boundaries.json") -> dict[str, Any]:
    clock, _scope, packet = _fixture()
    with TemporaryDirectory() as temp:
        root = Path(temp)
        journal = QiIngressJournal(root / "journal", max_bytes=1 << 20)
        entry = journal.append(packet)
        duplicate = journal.append(packet)
        replay = journal.replay()
        store = QiBoundaryCommitAStore(root / "commit")
        watermark, commit = store.commit(
            journal=journal,
            entry=entry,
            packet=packet,
            watermark=QiWatermark(),
            predecessor_head_sha256=D4,
            candidate_state_sha256=canonical_hash({"state": 0}, "cassi.qi-flow-run-state.v1"),
            candidate_state_object_sha256=canonical_hash({"object": 0}, "cassi.qi-flow-run-state-object.v1"),
        )
        acknowledgement = store.acknowledge(packet.event_id)
    egress = passive_egress_receipt(
        event_id=packet.event_id,
        energy_before=1.0,
        energy_after=1.25,
        injected_work=0.25,
        uncertainty=1.0e-12,
        tolerance=1.0e-12,
        guard_valid=True,
    )
    if duplicate != entry or len(replay) != 1:
        raise RuntimeError("journal duplicate/replay contract failed")
    if watermark.frontier(packet.scope) is None or not egress.committed:
        raise RuntimeError("Commit A/passive egress contract failed")
    result = {
        "schema": "cassi.qi-flow-boundaries-run.v1",
        "status": "PASS",
        "clock_schema": clock.payload()["schema"],
        "clock_schedule_sha256": clock.schedule_sha256,
        "clock_lcm_denominator": clock.lcm_denominator,
        "clock_ticks_per_world_tick": clock.ticks_per_world_tick,
        "packet_event_id": packet.event_id,
        "packet_schema": packet.schema,
        "journal_entry_frame_sha256": entry.frame_sha256,
        "journal_entry_head_sha256": entry.head_sha256,
        "journal_replay_count": len(replay),
        "commit_sha256": commit.commit_sha256,
        "commit_event_id": commit.event_id,
        "acknowledgement_sha256": acknowledgement,
        "watermark_sequence": watermark.frontier(packet.scope).source_sequence,
        "passive_egress": egress.payload(),
    }
    path = Path(evidence_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
