from __future__ import annotations

import unittest

from cassi_qi_clock import (
    QiAntialiasProfile,
    QiCausalClock,
    QiClockError,
    QiClockTime,
    QiSourceCadence,
    QiSourceScope,
    QiWatermark,
)


D0 = "0" * 64
D1 = "1" * 64
D2 = "2" * 64


def scope(name: str = "stream") -> QiSourceScope:
    return QiSourceScope("epoch-1", name, D0)


def cadence(name: str, interval: tuple[int, int], *, priority: int) -> QiSourceCadence:
    return QiSourceCadence(
        scope(name),
        QiClockTime.make(*interval),
        QiClockTime(0, 1),
        priority,
        first_sequence=7,
    )


class ClockTimeTest(unittest.TestCase):
    def test_reduced_arithmetic_and_order_are_exact(self) -> None:
        half = QiClockTime.make(2, 4)
        third = QiClockTime(1, 3)
        self.assertEqual(half, QiClockTime(1, 2))
        self.assertEqual(half + third, QiClockTime(5, 6))
        self.assertEqual(half - third, QiClockTime(1, 6))
        self.assertLess(third, half)
        with self.assertRaises(QiClockError):
            QiClockTime(2, 4)
        with self.assertRaises(QiClockError):
            third - half

    def test_clock_derives_lcm_and_integer_ticks(self) -> None:
        clock = QiCausalClock.create(
            tau_0=QiClockTime(1, 1),
            field_interval=QiClockTime(1, 4),
            field_steps_per_world_tick=3,
            sources=(cadence("audio", (1, 6), priority=1), cadence("video", (1, 10), priority=0)),
            max_clock_lcm=120,
        )
        self.assertEqual(clock.lcm_denominator, 60)
        self.assertEqual(clock.ticks_per_field_step, 15)
        self.assertEqual(clock.ticks_per_world_tick, 45)
        self.assertEqual(dict(clock.ticks_per_source_interval), {
            scope("audio").key(): 10,
            scope("video").key(): 6,
        })
        self.assertEqual(clock.tick_at(QiClockTime(3, 5)), 36)
        self.assertEqual(clock.time_at_tick(36), QiClockTime(3, 5))
        self.assertEqual(clock.payload()["schedule_sha256"], clock.schedule_sha256)

    def test_registered_capture_cadence_is_exact(self) -> None:
        source = cadence("audio", (1, 4), priority=0)
        clock = QiCausalClock.create(
            tau_0=QiClockTime(1, 1),
            field_interval=QiClockTime(1, 8),
            field_steps_per_world_tick=2,
            sources=(source,),
            max_clock_lcm=32,
        )
        start, end = clock.expected_capture(source.scope, 9)
        self.assertEqual((start, end), (QiClockTime(1, 2), QiClockTime(3, 4)))
        clock.validate_capture(
            scope=source.scope,
            source_sequence=9,
            capture_start=start,
            capture_end=end,
            cycle_frontier=QiClockTime(1, 1),
        )
        with self.assertRaises(QiClockError):
            clock.validate_capture(
                scope=source.scope,
                source_sequence=9,
                capture_start=QiClockTime(1, 2),
                capture_end=QiClockTime(7, 8),
                cycle_frontier=QiClockTime(1, 1),
            )
        with self.assertRaises(QiClockError):
            clock.validate_capture(
                scope=source.scope,
                source_sequence=9,
                capture_start=start,
                capture_end=end,
                cycle_frontier=QiClockTime(1, 2),
            )

    def test_lcm_and_unaligned_phase_fail_closed(self) -> None:
        with self.assertRaises(QiClockError):
            QiCausalClock.create(
                tau_0=QiClockTime(1, 1),
                field_interval=QiClockTime(1, 7),
                field_steps_per_world_tick=1,
                sources=(cadence("audio", (1, 11), priority=0),),
                max_clock_lcm=32,
            )
        shifted = QiSourceCadence(scope(), QiClockTime(1, 2), QiClockTime(1, 3), 0)
        with self.assertRaises(QiClockError):
            QiCausalClock.create(
                tau_0=QiClockTime(1, 1),
                field_interval=QiClockTime(1, 2),
                field_steps_per_world_tick=1,
                sources=(shifted,),
                max_clock_lcm=8,
            )

    def test_source_scope_separator_is_rejected(self) -> None:
        with self.assertRaises(QiClockError):
            QiSourceScope("bad\x1fepoch", "stream", D0)

    def test_admission_order_uses_exact_intervals_before_telemetry(self) -> None:
        early = QiCausalClock.admission_key(
            capture_end=QiClockTime(1, 2),
            capture_start=QiClockTime(1, 4),
            descriptor_priority=9,
            scope=scope("a"),
            source_sequence=1,
            packet_sha256=D1,
        )
        late = QiCausalClock.admission_key(
            capture_end=QiClockTime(2, 3),
            capture_start=QiClockTime(1, 3),
            descriptor_priority=0,
            scope=scope("b"),
            source_sequence=0,
            packet_sha256=D2,
        )
        self.assertLess(early, late)


class WatermarkTest(unittest.TestCase):
    def test_contiguous_commit_and_byte_identical_duplicate(self) -> None:
        source = scope()
        empty = QiWatermark()
        first = empty.advance(
            scope=source,
            capture_start=QiClockTime(0, 1),
            capture_end=QiClockTime(1, 4),
            source_sequence=7,
            frame_sha256=D1,
            first_sequence=7,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        duplicate = first.advance(
            scope=source,
            capture_start=QiClockTime(0, 1),
            capture_end=QiClockTime(1, 4),
            source_sequence=7,
            frame_sha256=D1,
            first_sequence=7,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        self.assertIs(duplicate, first)
        second = first.advance(
            scope=source,
            capture_start=QiClockTime(1, 4),
            capture_end=QiClockTime(1, 2),
            source_sequence=8,
            frame_sha256=D2,
            first_sequence=7,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        self.assertEqual(second.frontier(source).source_sequence, 8)
        self.assertNotEqual(first.payload()["self_sha256"], second.payload()["self_sha256"])

    def test_gap_future_conflict_and_unindexed_frames_reject(self) -> None:
        source = scope()
        base = QiWatermark().advance(
            scope=source,
            capture_start=QiClockTime(0, 1),
            capture_end=QiClockTime(1, 4),
            source_sequence=7,
            frame_sha256=D1,
            first_sequence=7,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        common = dict(
            scope=source,
            first_sequence=7,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        with self.assertRaises(QiClockError):
            base.advance(capture_start=QiClockTime(1, 4), capture_end=QiClockTime(1, 2), source_sequence=9, frame_sha256=D2, **common)
        with self.assertRaises(QiClockError):
            base.advance(capture_start=QiClockTime(1, 4), capture_end=QiClockTime(3, 4), source_sequence=8, frame_sha256=D2, **common)
        with self.assertRaises(QiClockError):
            base.advance(capture_start=QiClockTime(0, 1), capture_end=QiClockTime(1, 4), source_sequence=7, frame_sha256=D2, **common)
        with self.assertRaises(QiClockError):
            QiWatermark().advance(
                scope=source,
                capture_start=QiClockTime(0, 1),
                capture_end=QiClockTime(1, 4),
                source_sequence=7,
                frame_sha256=D1,
                first_sequence=7,
                first_capture_start=QiClockTime(0, 1),
                cycle_frontier=QiClockTime(1, 2),
                indexed_in_commit_a=False,
            )


class AntialiasProfileTest(unittest.TestCase):
    def test_profile_binds_coefficients_adjoint_and_response(self) -> None:
        profile = QiAntialiasProfile(
            profile_id="half-band-3",
            coefficients=(0.25, 0.5, 0.25),
            phase=QiClockTime(0, 1),
            support_start=0,
            support_end=2,
            boundary_convention="periodic",
            passband_tolerance=1e-6,
            stopband_tolerance=1e-6,
        )
        payload = profile.payload()
        self.assertEqual(payload["adjoint_coefficients"], [0.25, 0.5, 0.25])
        self.assertEqual(len(payload["response_sha256"]), 64)
        self.assertEqual(len(payload["self_sha256"]), 64)

    def test_profile_rejects_undeclared_or_nonfinite_operator(self) -> None:
        with self.assertRaises(QiClockError):
            QiAntialiasProfile("bad", (float("nan"),), QiClockTime(0, 1), 0, 0, "periodic", 0.0, 0.0)
        with self.assertRaises(QiClockError):
            QiAntialiasProfile("bad", (1.0,), QiClockTime(0, 1), 0, 0, "nearest", 0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
