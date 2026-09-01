from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from cassi_qi_boundary import (
    QiActuatorDescriptor,
    QiAudioDescriptor,
    QiBoundaryCommitAStore,
    QiBoundaryError,
    QiBoundaryPacket,
    QiIngressJournal,
    QiLinearBoundaryPort,
    QiOpticalDescriptor,
    QiProprioceptiveDescriptor,
    QiTextDescriptor,
    apply_antialias,
    assert_disjoint_ports,
    passive_egress_receipt,
)
from cassi_qi_bootstrap import canonical_hash
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


def _scope(stream: str = "sensor", descriptor: str = D0, epoch: str = "epoch-1") -> QiSourceScope:
    return QiSourceScope(epoch, stream, descriptor)


def _cadence(
    source: QiSourceScope,
    interval: tuple[int, int] = (1, 4),
    *,
    priority: int = 0,
    first_sequence: int = 0,
    phase: tuple[int, int] = (0, 1),
) -> QiSourceCadence:
    return QiSourceCadence(
        source,
        QiClockTime.make(*interval),
        QiClockTime.make(*phase),
        priority,
        first_sequence=first_sequence,
    )


def _clock(*sources: QiSourceCadence) -> QiCausalClock:
    return QiCausalClock.create(
        tau_0=QiClockTime(1, 1),
        field_interval=QiClockTime(1, 4),
        field_steps_per_world_tick=2,
        sources=sources,
        max_clock_lcm=64,
    )


def _packet(
    clock: QiCausalClock,
    source: QiSourceScope,
    sequence: int = 0,
    *,
    frontier: QiClockTime = QiClockTime(1, 2),
    payload: bytes = b"frame",
    shape: tuple[int, ...] = (1,),
    dtype: str = "uint8",
) -> QiBoundaryPacket:
    return QiBoundaryPacket.create(
        clock=clock,
        scope=source,
        profile_sha256=D0,
        watermark_sha256=D1,
        ingress_journal_sha256=D2,
        source_sequence=sequence,
        cycle_frontier=frontier,
        payload_shape=shape,
        payload_dtype=dtype,
        payload=payload,
    )



def _identity_port(
    source_dimension: int,
    *,
    name: str = "port",
    field_dimension: int | None = None,
    port_indices: tuple[int, ...] | None = None,
) -> QiLinearBoundaryPort:
    width = source_dimension if field_dimension is None else field_dimension
    indices = tuple(range(source_dimension)) if port_indices is None else port_indices
    rows = []
    for index in indices:
        row = [0j] * width
        row[index] = 1.0 + 0.0j
        rows.append(row)
    return QiLinearBoundaryPort.create(
        name=name,
        observation_rows=rows,
        source_metric=tuple(1.0 + index for index in range(source_dimension)),
        field_metric=tuple(1.0 + index for index in range(width)),
        gain=1.0,
        port_indices=indices,
    )


class ClockAndAdmissionTest(unittest.TestCase):
    def test_exact_cadence_lcm_partition_and_admission_order(self) -> None:
        source = _scope("audio")
        cadence = _cadence(source, (1, 6), priority=3, first_sequence=7)
        clock = _clock(
            cadence,
            _cadence(_scope("video", D1), (1, 10), priority=1),
        )
        self.assertEqual(clock.lcm_denominator, 60)
        self.assertEqual(clock.ticks_per_field_step, 15)
        self.assertEqual(clock.ticks_per_world_tick, 30)
        self.assertEqual(dict(clock.ticks_per_source_interval)[source.key()], 10)
        self.assertEqual(clock.expected_capture(source, 7), (QiClockTime(0, 1), QiClockTime(1, 6)))
        self.assertEqual(clock.tick_at(QiClockTime(3, 5)), 36)
        self.assertEqual(clock.time_at_tick(36), QiClockTime(3, 5))

        same_interval = dict(
            capture_end=QiClockTime(1, 2),
            capture_start=QiClockTime(1, 4),
            scope=source,
            source_sequence=7,
            packet_sha256=D0,
        )
        by_priority = QiCausalClock.admission_key(descriptor_priority=0, **same_interval)
        later_priority = QiCausalClock.admission_key(descriptor_priority=1, **same_interval)
        self.assertLess(by_priority, later_priority)
        self.assertLess(
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=_scope("a"),
                source_sequence=7,
                packet_sha256=D0,
            ),
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=_scope("b"),
                source_sequence=7,
                packet_sha256=D0,
            ),
        )
        self.assertLess(
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            ),
            QiCausalClock.admission_key(
                capture_end=QiClockTime(2, 3),
                capture_start=QiClockTime(1, 3),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            ),
        )
        self.assertLess(
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            ),
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 3),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            ),
        )
        self.assertLess(
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            ),
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=8,
                packet_sha256=D0,
            ),
        )
        self.assertLess(
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            ),
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 2),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D1,
            ),
        )
        with self.assertRaises(QiClockError):
            QiCausalClock.admission_key(
                capture_end=QiClockTime(1, 4),
                capture_start=QiClockTime(1, 4),
                descriptor_priority=0,
                scope=source,
                source_sequence=7,
                packet_sha256=D0,
            )

    def test_zero_or_unaligned_schedule_fails_before_tick_derivation(self) -> None:
        with self.assertRaises(QiClockError):
            QiCausalClock.create(
                tau_0=QiClockTime(1, 1),
                field_interval=QiClockTime(1, 4),
                field_steps_per_world_tick=1,
                sources=(_cadence(_scope(), (0, 1)),),
                max_clock_lcm=64,
            )
        with self.assertRaises(QiClockError):
            QiCausalClock.create(
                tau_0=QiClockTime(1, 1),
                field_interval=QiClockTime(1, 2),
                field_steps_per_world_tick=1,
                sources=(_cadence(_scope(), (1, 2), phase=(1, 3)),),
                max_clock_lcm=8,
            )


class PacketIdentityAndAdmissionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = _scope()
        self.clock = _clock(_cadence(self.source))

    def test_packet_requires_detached_payload_and_strict_no_sample_shape(self) -> None:
        with self.assertRaises(QiBoundaryError):
            _packet(self.clock, self.source, payload=bytearray(b"frame"))
        with self.assertRaises(QiBoundaryError):
            _packet(self.clock, self.source, payload=b"", shape=(1,))
        with self.assertRaises(QiBoundaryError):
            QiBoundaryPacket.create(
                clock=self.clock,
                scope=self.source,
                profile_sha256=D0,
                watermark_sha256=D1,
                ingress_journal_sha256=D2,
                source_sequence=0,
                cycle_frontier=QiClockTime(1, 2),
                payload_shape=(1,),
                payload_dtype="none",
                payload=b"",
                valid=False,
                failure_reason="missing",
            )
        with self.assertRaises(QiBoundaryError):
            QiBoundaryPacket.no_sample(
                clock=self.clock,
                scope=self.source,
                profile_sha256=D0,
                watermark_sha256=D1,
                ingress_journal_sha256=D2,
                source_sequence=0,
                cycle_frontier=QiClockTime(1, 2),
                reason="",
            )

        no_sample = QiBoundaryPacket.no_sample(
            clock=self.clock,
            scope=self.source,
            profile_sha256=D0,
            watermark_sha256=D1,
            ingress_journal_sha256=D2,
            source_sequence=0,
            cycle_frontier=QiClockTime(1, 2),
            reason="sensor-muted",
        )
        self.assertFalse(no_sample.valid)
        self.assertEqual(no_sample.payload_shape, (0,))
        self.assertEqual(no_sample.payload_dtype, "none")
        self.assertEqual(no_sample.payload, b"")
        self.assertEqual(no_sample.failure_reason, "sensor-muted")

    def test_descriptor_and_source_identity_are_separate_and_complete(self) -> None:
        other_descriptor = _scope("sensor", D1)
        other_stream = _scope("other", D0)
        self.assertNotEqual(self.source.key(), other_descriptor.key())
        self.assertNotEqual(self.source.key(), other_stream.key())

        packet = _packet(self.clock, self.source)
        self.assertEqual(packet.scope, self.source)
        canonical = packet.canonical_payload()
        self.assertEqual(canonical["descriptor_sha256"], D0)
        self.assertEqual(canonical["source_epoch"], self.source.source_epoch)
        for required in (
            "source_stream_id",
            "profile_sha256",
            "clock_sha256",
            "watermark_sha256",
            "ingress_journal_sha256",
        ):
            with self.subTest(required=required):
                self.assertIn(required, canonical)


class LinearBoundaryTest(unittest.TestCase):
    def test_metric_adjoint_identity_is_exact_for_complex_port(self) -> None:
        port = QiLinearBoundaryPort.create(
            name="camera",
            observation_rows=((1.0 + 1.0j, 0.0j), (0.0j, 2.0 - 1.0j)),
            source_metric=(2.0, 3.0),
            field_metric=(4.0, 5.0),
            gain=1.5,
            port_indices=(0, 1),
        )
        field = torch.tensor([0.5 - 0.25j, -1.0 + 0.75j], dtype=torch.complex128)
        source = torch.tensor([0.25 + 1.0j, -0.5 + 0.125j], dtype=torch.complex128)
        self.assertLess(port.adjoint_residual(field, source), 1.0e-12)
        self.assertEqual(port.observe(field).shape, (2,))
        self.assertEqual(port.inject(source).shape, (2,))

    def test_negative_gain_and_port_coordinate_collisions_reject(self) -> None:
        with self.assertRaises(QiBoundaryError):
            QiLinearBoundaryPort.create(
                name="negative-gain",
                observation_rows=((1.0 + 0.0j,),),
                source_metric=(1.0,),
                field_metric=(1.0,),
                gain=-1.0,
                port_indices=(0,),
            )
        first = _identity_port(1, name="first", field_dimension=2, port_indices=(0,))
        second = _identity_port(1, name="second", field_dimension=2, port_indices=(0,))
        with self.assertRaises(QiBoundaryError):
            assert_disjoint_ports((first, second))
        assert_disjoint_ports((first, _identity_port(1, name="other", field_dimension=2, port_indices=(1,))))


class ModalityBoundaryTest(unittest.TestCase):
    def test_optical_calibrated_crop_resample_and_yang_yin_split(self) -> None:
        port = _identity_port(4, name="optical")
        descriptor = QiOpticalDescriptor.create(
            descriptor_id="optical-v1",
            sensor_shape_hwc=(2, 2, 1),
            retinal_shape_yx=(1, 2),
            active_sensor_indices=(1, 3),
            retinal_to_active_index=(1, 0),
            luminance_coefficients=(1.0,),
            raw_min=0.0,
            raw_max=10.0,
            midpoint=5.0,
            port=port,
        )
        source = descriptor.source_vector((1.0, 2.0, 8.0, 10.0))
        expected = torch.tensor([5.0, 0.0, 0.0, 3.0], dtype=torch.complex128)
        torch.testing.assert_close(source, expected, rtol=0.0, atol=0.0)
        with self.assertRaises(QiBoundaryError):
            descriptor.source_vector((1.0, 2.0, 8.0, 11.0))
        with self.assertRaises(QiBoundaryError):
            descriptor.source_vector((1.0, 2.0, 8.0))

    def test_audio_uses_real_orthonormal_rfft_and_matching_inverse(self) -> None:
        descriptor = QiAudioDescriptor.create(
            descriptor_id="audio-v1",
            sample_rate_hz=16_000,
            window=(1.0, 1.0, 1.0, 1.0),
            hop_samples=2,
            retained_bins=(0, 1, 2),
            port=_identity_port(3, name="audio"),
        )
        samples = torch.tensor([1.0, -2.0, 3.0, 4.0], dtype=torch.float64)
        source = descriptor.source_vector(tuple(samples.tolist()))
        expected = torch.fft.rfft(samples, norm="ortho").to(torch.complex128)
        torch.testing.assert_close(source, expected, rtol=0.0, atol=0.0)
        reconstructed = descriptor.reconstruct_window(source)
        torch.testing.assert_close(reconstructed, samples, rtol=0.0, atol=1.0e-12)

        with self.assertRaises(QiBoundaryError):
            QiAudioDescriptor.create(
                descriptor_id="one-bin",
                sample_rate_hz=16_000,
                window=(1.0,),
                hop_samples=1,
                retained_bins=(0,),
                port=_identity_port(1, name="one-bin"),
            )
        with self.assertRaises(QiBoundaryError):
            QiAudioDescriptor.create(
                descriptor_id="singular-window",
                sample_rate_hz=16_000,
                window=(1.0, 0.0, 1.0, 1.0),
                hop_samples=2,
                retained_bins=(0, 1, 2),
                port=_identity_port(3, name="singular-window"),
            )

    def test_proprioceptive_basis_is_injective_and_reconstructs_channels(self) -> None:
        descriptor = QiProprioceptiveDescriptor.create(
            descriptor_id="proprio-v1",
            channel_names=("joint", "contact"),
            units=("rad", "bool"),
            minimums=(0.0, 0.0),
            maximums=(1.0, 1.0),
            basis_rows=((1.0 + 0.0j, 0.0j), (0.0j, 1.0 + 0.0j), (1.0 + 0.0j, 1.0j)),
            port=_identity_port(3, name="proprio"),
            rank_tolerance=1.0e-10,
        )
        source = descriptor.source_vector((0.25, 0.75))
        expected = torch.tensor([-0.5 + 0.0j, 0.5 + 0.0j, -0.5 + 0.5j], dtype=torch.complex128)
        torch.testing.assert_close(source, expected, rtol=0.0, atol=0.0)
        reconstructed = descriptor.reconstruct_channels(source)
        for actual, expected_channel in zip(reconstructed, (0.25, 0.75), strict=True):
            self.assertAlmostEqual(actual, expected_channel, delta=1.0e-12)
        with self.assertRaises(QiBoundaryError):
            QiProprioceptiveDescriptor.create(
                descriptor_id="rank-one",
                channel_names=("a", "b"),
                units=("u", "u"),
                minimums=(0.0, 0.0),
                maximums=(1.0, 1.0),
                basis_rows=((1.0 + 0.0j, 1.0 + 0.0j), (2.0 + 0.0j, 2.0 + 0.0j)),
                port=_identity_port(2, name="rank-one"),
                rank_tolerance=1.0e-10,
            )
        with self.assertRaises(QiBoundaryError):
            QiProprioceptiveDescriptor.create(
                descriptor_id="zero-width",
                channel_names=("fixed",),
                units=("u",),
                minimums=(1.0,),
                maximums=(1.0,),
                basis_rows=((1.0 + 0.0j,),),
                port=_identity_port(1, name="zero-width"),
                rank_tolerance=1.0e-10,
            )

    def test_text_port_round_trips_every_frozen_symbol_and_uses_codec(self) -> None:
        descriptor = QiTextDescriptor.create(
            descriptor_id="text-v1",
            port=_identity_port(260, name="text"),
        )
        self.assertEqual(descriptor.codec.alphabet_size, 260)
        for symbol in range(260):
            source = torch.zeros(260, dtype=torch.complex128)
            source[symbol] = 1.0
            recovered = descriptor.port.observe(descriptor.port.inject(source))
            torch.testing.assert_close(recovered, source, rtol=0.0, atol=0.0)

        encoded = descriptor.encode_message("Qi")
        symbols = tuple(int(torch.argmax(row).item()) for row in encoded)
        self.assertEqual(descriptor.decode_symbols(symbols), "Qi")


class ActuatorAndReceiptTest(unittest.TestCase):
    def test_actuator_range_slew_and_quantization_guards(self) -> None:
        descriptor = QiActuatorDescriptor.create(
            descriptor_id="motor-v1",
            channel_names=("x",),
            minimums=(-1.0,),
            maximums=(1.0,),
            zero_points=(0.0,),
            slew_per_tick=(0.5,),
            quantization_step=(0.25,),
            port=_identity_port(1, name="motor"),
        )
        self.assertEqual(descriptor.quantize((0.26,), (0.0,)), (0.25,))
        with self.assertRaises(QiBoundaryError):
            descriptor.quantize((1.1,), (0.0,))
        with self.assertRaises(QiBoundaryError):
            descriptor.quantize((0.6,), (0.0,))
        with self.assertRaises(QiBoundaryError):
            descriptor.quantize((0.1,), (1.1,))

        with self.assertRaises(QiBoundaryError):
            QiActuatorDescriptor.create(
                descriptor_id="quantization-overflow",
                channel_names=("x",),
                minimums=(0.0,),
                maximums=(1.0,),
                zero_points=(0.5,),
                slew_per_tick=(2.0,),
                quantization_step=(0.6,),
                port=_identity_port(1, name="quantization-overflow"),
            ).quantize((1.0,), (0.5,))

    def test_fixed_antialias_receipt_carries_replayable_operator_identity(self) -> None:
        profile = QiAntialiasProfile(
            profile_id="aa-v1",
            coefficients=(0.25, 0.5, 0.25),
            phase=QiClockTime(0, 1),
            support_start=0,
            support_end=2,
            boundary_convention="finite-reflect",
            passband_tolerance=1.0e-6,
            stopband_tolerance=1.0e-6,
        )
        profile_sha = profile.payload()["self_sha256"]
        output, receipt = apply_antialias(
            torch.tensor([1.0, 2.0, 3.0, 4.0, 5.0], dtype=torch.float64),
            profile.coefficients,
            profile_sha256=profile_sha,
        )
        torch.testing.assert_close(
            output,
            torch.tensor([1.5, 2.0, 3.0, 4.0, 4.5], dtype=torch.float64),
            rtol=0.0,
            atol=0.0,
        )
        payload = receipt.payload()
        self.assertEqual(payload["profile_sha256"], profile_sha)
        self.assertEqual(payload["mode"], "fixed-fir-reflect-v1")
        self.assertEqual(
            payload["self_sha256"],
            canonical_hash({key: value for key, value in payload.items() if key != "self_sha256"}, "cassi.qi-flow-antialias-receipt.v1"),
        )
        with self.assertRaises(QiBoundaryError):
            apply_antialias(torch.ones(5, dtype=torch.float64), (0.25, 0.5, 0.5), profile_sha256=profile_sha)

    def test_passive_egress_rejects_energy_mismatch_without_event(self) -> None:
        rejected = passive_egress_receipt(
            event_id="egress-event",
            energy_before=10.0,
            energy_after=10.0,
            injected_work=1.0,
            uncertainty=0.0,
            tolerance=0.0,
            guard_valid=True,
        )
        self.assertFalse(rejected.committed)
        self.assertIsNone(rejected.event_id)
        self.assertEqual(rejected.rejection_reason, "energy-ledger-rejected")
        self.assertIsNone(rejected.payload()["event_id"])
        self.assertTrue(rejected.payload()["no_time_advancement"])

        guard_rejected = passive_egress_receipt(
            event_id="guard-event",
            energy_before=10.0,
            energy_after=11.0,
            injected_work=1.0,
            uncertainty=0.0,
            tolerance=0.0,
            guard_valid=False,
        )
        self.assertFalse(guard_rejected.committed)
        self.assertIsNone(guard_rejected.event_id)
        self.assertEqual(guard_rejected.rejection_reason, "guard-rejected")


class WatermarkAndJournalTest(unittest.TestCase):
    def test_scoped_watermarks_accept_only_contiguous_indexed_frames(self) -> None:
        first_scope = _scope("camera", D0)
        second_scope = _scope("camera", D1)
        empty = QiWatermark()
        first = empty.advance(
            scope=first_scope,
            capture_start=QiClockTime(0, 1),
            capture_end=QiClockTime(1, 4),
            source_sequence=0,
            frame_sha256=D1,
            first_sequence=0,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        duplicate = first.advance(
            scope=first_scope,
            capture_start=QiClockTime(0, 1),
            capture_end=QiClockTime(1, 4),
            source_sequence=0,
            frame_sha256=D1,
            first_sequence=0,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        self.assertIs(duplicate, first)
        scoped = first.advance(
            scope=second_scope,
            capture_start=QiClockTime(0, 1),
            capture_end=QiClockTime(1, 4),
            source_sequence=0,
            frame_sha256=D2,
            first_sequence=0,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        self.assertIsNotNone(scoped.frontier(first_scope))
        self.assertIsNotNone(scoped.frontier(second_scope))
        self.assertEqual([scope.key() for scope, _ in scoped.frontiers], sorted((first_scope.key(), second_scope.key())))

        common = dict(
            scope=first_scope,
            first_sequence=0,
            first_capture_start=QiClockTime(0, 1),
            cycle_frontier=QiClockTime(1, 2),
            indexed_in_commit_a=True,
        )
        with self.assertRaises(QiClockError):
            first.advance(capture_start=QiClockTime(1, 4), capture_end=QiClockTime(1, 2), source_sequence=2, frame_sha256=D2, **common)
        with self.assertRaises(QiClockError):
            first.advance(capture_start=QiClockTime(1, 4), capture_end=QiClockTime(3, 4), source_sequence=1, frame_sha256=D2, **common)
        with self.assertRaises(QiClockError):
            first.advance(capture_start=QiClockTime(0, 1), capture_end=QiClockTime(1, 4), source_sequence=0, frame_sha256=D2, **common)
        with self.assertRaises(QiClockError):
            first.advance(capture_start=QiClockTime(1, 4), capture_end=QiClockTime(1, 2), source_sequence=1, frame_sha256=D2, indexed_in_commit_a=False, **{key: value for key, value in common.items() if key != "indexed_in_commit_a"})
        with self.assertRaises(QiClockError):
            first.advance(capture_start=QiClockTime(1, 4), capture_end=QiClockTime(3, 4), source_sequence=1, frame_sha256=D2, **common)

    def test_content_addressed_journal_replays_exact_bytes_and_deduplicates_non_tail(self) -> None:
        source = _scope()
        clock = _clock(_cadence(source))
        packet0 = _packet(clock, source, 0, payload=b"zero")
        packet1 = _packet(clock, source, 1, payload=b"one")
        with tempfile.TemporaryDirectory() as temporary:
            journal = QiIngressJournal(temporary, max_bytes=1 << 20)
            entry0 = journal.append(packet0)
            entry1 = journal.append(packet1)
            self.assertTrue((Path(temporary) / "objects" / f"{entry0.frame_sha256}.json").exists())
            self.assertTrue((Path(temporary) / "objects" / f"{entry1.frame_sha256}.json").exists())
            self.assertEqual([row["packet"]["event_id"] for row in journal.replay()], [packet0.event_id, packet1.event_id])
            self.assertEqual(journal.append(packet1).head_sha256, entry1.head_sha256)
            self.assertEqual(journal.append(packet0).head_sha256, entry1.head_sha256)
            self.assertEqual(len(journal.replay()), 2)

            tiny = QiIngressJournal(Path(temporary) / "tiny", max_bytes=1)
            with self.assertRaises(QiBoundaryError):
                tiny.append(packet0)


class CommitATest(unittest.TestCase):
    def _fixtures(self, root: str) -> tuple[QiIngressJournal, QiBoundaryCommitAStore, QiBoundaryPacket, QiWatermark]:
        source = _scope()
        clock = _clock(_cadence(source))
        journal = QiIngressJournal(Path(root) / "journal", max_bytes=1 << 20)
        packet = _packet(clock, source)
        journal.append(packet)
        return journal, QiBoundaryCommitAStore(Path(root) / "commit"), packet, QiWatermark()

    def test_crash_before_commit_a_replays_frame_and_cannot_acknowledge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            journal, store, packet, _ = self._fixtures(temporary)
            self.assertEqual(journal.replay()[0]["packet"]["payload_base64"], "ZnJhbWU=")
            with patch.object(store, "_replace_pointer", side_effect=RuntimeError("crash before Commit A pointer")):
                with self.assertRaisesRegex(RuntimeError, "crash before Commit A pointer"):
                    store.commit(
                        journal=journal,
                        entry=journal.append(packet),
                        packet=packet,
                        watermark=QiWatermark(),
                        predecessor_head_sha256=D0,
                        candidate_state_sha256=D1,
                        candidate_state_object_sha256=D2,
                    )
            self.assertFalse(store.head_path.exists())
            commit_objects = tuple((Path(temporary) / "commit" / "objects").glob("*.json"))
            self.assertEqual(len(commit_objects), 1)
            with self.assertRaises(QiBoundaryError):
                store.acknowledge(packet.event_id)
            restarted = QiBoundaryCommitAStore(Path(temporary) / "commit")
            self.assertFalse(restarted.head_path.exists())
            with self.assertRaises(QiBoundaryError):
                restarted.acknowledge(packet.event_id)

    def test_commit_a_happy_path_advances_real_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            journal, store, packet, watermark = self._fixtures(temporary)
            entry = journal.append(packet)
            next_watermark, receipt = store.commit(
                journal=journal,
                entry=entry,
                packet=packet,
                watermark=watermark,
                predecessor_head_sha256=D0,
                candidate_state_sha256=D1,
                candidate_state_object_sha256=D2,
            )
            self.assertEqual(store.head_path.read_text(encoding="ascii").strip(), receipt.commit_sha256)
            self.assertEqual(receipt.event_id, packet.event_id)
            frontier = next_watermark.frontier(packet.scope)
            if frontier is None:
                self.fail("Commit A returned no frontier for its admitted source scope")
            self.assertEqual(frontier.capture_end, packet.capture_end)
            self.assertEqual(frontier.source_sequence, packet.source_sequence)
            self.assertEqual(frontier.frame_sha256, entry.frame_sha256)
            self.assertEqual(receipt.watermark_payload, next_watermark.payload())

    def test_commit_a_survives_restart_after_pointer_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            journal, store, packet, _ = self._fixtures(temporary)
            real_replace = store._replace_pointer

            def replace_then_crash(path: Path, digest: str) -> None:
                real_replace(path, digest)
                raise RuntimeError("crash after Commit A pointer")

            with patch.object(store, "_replace_pointer", side_effect=replace_then_crash):
                with self.assertRaisesRegex(RuntimeError, "crash after Commit A pointer"):
                    store.commit(
                        journal=journal,
                        entry=journal.append(packet),
                        packet=packet,
                        watermark=QiWatermark(),
                        predecessor_head_sha256=D0,
                        candidate_state_sha256=D1,
                        candidate_state_object_sha256=D2,
                    )
            self.assertTrue(store.head_path.exists())
            restarted = QiBoundaryCommitAStore(Path(temporary) / "commit")
            acknowledgement = restarted.acknowledge(packet.event_id)
            self.assertTrue(acknowledgement)
            with self.assertRaises(QiBoundaryError):
                restarted.acknowledge("wrong-event")


if __name__ == "__main__":
    unittest.main()
