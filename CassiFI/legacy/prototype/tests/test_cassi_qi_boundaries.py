from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import torch

from cassi_qi_boundary import (
    QiBoundaryCommitAStore,
    QiBoundaryError,
    QiBoundaryPacket,
    QiIngressJournal,
    QiLinearBoundaryPort,
    apply_antialias,
    passive_egress_receipt,
)
from cassi_qi_bootstrap import canonical_hash
from cassi_qi_clock import (
    QiCausalClock,
    QiClockError,
    QiClockTime,
    QiSourceCadence,
    QiSourceScope,
    QiWatermark,
)
from run_cassi_qi_boundaries import run as run_boundaries
from run_cassi_qi_boundary_permeability import run as run_permeability
from verify_cassi_qi_boundaries import verify as verify_boundaries
from verify_cassi_qi_boundary_permeability import verify as verify_permeability

D0 = "0" * 64
D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64


def _scope(stream: str = "sensor") -> QiSourceScope:
    return QiSourceScope("epoch-0", stream, D0)


def _clock() -> QiCausalClock:
    scope = _scope()
    return QiCausalClock.create(
        tau_0=QiClockTime(1, 1),
        field_interval=QiClockTime(1, 2),
        field_steps_per_world_tick=2,
        sources=(
            QiSourceCadence(scope, QiClockTime(1, 3), QiClockTime(0, 1), 0),
        ),
        max_clock_lcm=64,
    )


def _packet(clock: QiCausalClock, sequence: int = 0) -> QiBoundaryPacket:
    scope = _scope()
    frontier = clock.expected_capture(scope, sequence)[1]
    return QiBoundaryPacket.create(
        clock=clock,
        scope=scope,
        profile_sha256=D1,
        watermark_sha256=D2,
        ingress_journal_sha256=D3,
        source_sequence=sequence,
        cycle_frontier=frontier,
        payload_shape=(2,),
        payload_dtype="uint8",
        payload=b"xy",
    )


class BoundaryClockTest(unittest.TestCase):
    def test_exact_lcm_schedule_and_half_open_admission(self) -> None:
        clock = _clock()
        self.assertEqual(clock.lcm_denominator, 6)
        self.assertEqual(clock.ticks_per_field_step, 3)
        self.assertEqual(clock.ticks_per_world_tick, 6)
        self.assertEqual(clock.tick_at(QiClockTime(1, 2)), 3)
        self.assertEqual(clock.time_at_tick(3), QiClockTime(1, 2))
        scope = _scope()
        start, end = clock.expected_capture(scope, 1)
        self.assertEqual((start, end), (QiClockTime(1, 3), QiClockTime(2, 3)))
        clock.validate_capture(
            scope=scope,
            source_sequence=1,
            capture_start=start,
            capture_end=end,
            cycle_frontier=end,
        )
        with self.assertRaises(QiClockError):
            clock.validate_capture(
                scope=scope,
                source_sequence=1,
                capture_start=start,
                capture_end=end,
                cycle_frontier=start,
            )

    def test_clock_rejects_nonreduced_and_unaligned_values(self) -> None:
        with self.assertRaises(QiClockError):
            QiClockTime(2, 4)
        with self.assertRaises(QiClockError):
            _clock().tick_at(QiClockTime(1, 4))


class BoundaryIngressTest(unittest.TestCase):
    def test_packet_journal_replay_commit_a_and_ack(self) -> None:
        clock = _clock()
        packet = _packet(clock)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            journal = QiIngressJournal(root / "journal", max_bytes=1 << 20)
            entry = journal.append(packet)
            duplicate = journal.append(packet)
            self.assertEqual(entry, duplicate)
            replay = journal.replay()
            self.assertEqual(len(replay), 1)
            self.assertEqual(replay[0]["packet"]["event_id"], packet.event_id)

            store = QiBoundaryCommitAStore(root / "commit")
            watermark, receipt = store.commit(
                journal=journal,
                entry=entry,
                packet=packet,
                watermark=QiWatermark(),
                predecessor_head_sha256=D4,
                candidate_state_sha256=canonical_hash({"state": 0}, "cassi.qi-flow-test-state.v1"),
                candidate_state_object_sha256=canonical_hash({"object": 0}, "cassi.qi-flow-test-state-object.v1"),
            )
            self.assertEqual(watermark.frontier(packet.scope).source_sequence, 0)
            self.assertEqual(receipt.event_id, packet.event_id)
            self.assertTrue(store.acknowledge(packet.event_id))

    def test_rejected_no_sample_is_explicit_and_immutable(self) -> None:
        clock = _clock()
        no_sample = QiBoundaryPacket.no_sample(
            clock=clock,
            scope=_scope(),
            profile_sha256=D1,
            watermark_sha256=D2,
            ingress_journal_sha256=D3,
            source_sequence=0,
            cycle_frontier=QiClockTime(1, 3),
            reason="sensor-muted",
        )
        self.assertFalse(no_sample.valid)
        self.assertEqual(no_sample.payload, b"")
        self.assertEqual(no_sample.payload_shape, (0,))
        self.assertEqual(no_sample.payload_dtype, "none")
        self.assertEqual(no_sample.failure_reason, "sensor-muted")
        with self.assertRaises(QiBoundaryError):
            QiBoundaryPacket.create(
                clock=clock,
                scope=_scope(),
                profile_sha256=D1,
                watermark_sha256=D2,
                ingress_journal_sha256=D3,
                source_sequence=0,
                cycle_frontier=QiClockTime(1, 3),
                payload_shape=(1,),
                payload_dtype="uint8",
                payload=bytearray(b"x"),
            )

    def test_antialias_receipt_is_content_addressed(self) -> None:
        values = torch.tensor([0.0, 1.0, 0.0], dtype=torch.float64)
        output, receipt = apply_antialias(values, (0.25, 0.5, 0.25), profile_sha256=D1)
        self.assertEqual(tuple(output.shape), (3,))
        payload = receipt.payload()
        self.assertEqual(payload["schema"], "cassi.qi-flow-antialias-receipt.v1")
        self.assertEqual(payload["profile_sha256"], D1)
        self.assertEqual(payload["source_shape"], [3])
        self.assertEqual(payload["output_shape"], [3])


class PassiveEgressTest(unittest.TestCase):
    def test_passive_egress_closes_work_without_advancing_time(self) -> None:
        accepted = passive_egress_receipt(
            event_id="event-0",
            energy_before=1.0,
            energy_after=1.25,
            injected_work=0.25,
            uncertainty=1.0e-12,
            tolerance=1.0e-12,
            guard_valid=True,
        )
        self.assertTrue(accepted.committed)
        self.assertEqual(accepted.event_id, "event-0")
        self.assertTrue(accepted.payload()["no_time_advancement"])

        rejected = passive_egress_receipt(
            event_id="event-0",
            energy_before=1.0,
            energy_after=1.25,
            injected_work=0.25,
            uncertainty=0.0,
            tolerance=0.0,
            guard_valid=False,
        )
        self.assertFalse(rejected.committed)
        self.assertIsNone(rejected.event_id)
        self.assertEqual(rejected.rejection_reason, "guard-rejected")


class EvidenceVerifierFiniteTest(unittest.TestCase):
    def test_boundary_verifier_rejects_nonfinite_residual(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = run_boundaries(evidence_path=Path(temp) / "boundary.json")
        result["passive_egress"] = {**result["passive_egress"], "residual": float("nan")}
        with self.assertRaises(ValueError):
            verify_boundaries(result)

    def test_permeability_verifier_rejects_nonfinite_encoded_work(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            destination = Path(temp) / "permeability.json"
            result = run_permeability(evidence_path=destination)
            self.assertTrue(destination.is_file())
        result["live_admitted_work"] = {
            **result["live_admitted_work"],
            "upper": "f64:7ff8000000000000",
        }
        with self.assertRaises(ValueError):
            verify_permeability(result)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                run_permeability(evidence_path=Path(temp) / "outside.json")


if __name__ == "__main__":
    unittest.main()
