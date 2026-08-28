"""Focused W8 body contract tests.

These tests are intentionally self-contained and do not involve the flow
runtime or a world adapter.  The parent validation wave runs them.
"""

from __future__ import annotations

import inspect
import unittest

import torch

from cassi_qi_body import (
    BODY_PROFILE_SCHEMA,
    QiBodyError,
    QiBodyPrediction,
    QiBodyProfile,
    QiBodyRemapReceipt,
    QiBodySensorFrame,
    QiEfferenceCopy,
    QiEnvironmentSensorFrame,
    _f64_text,
)
from cassi_qi_boundary import QiBoundaryPacket, QiLinearBoundaryPort
from cassi_qi_clock import QiCausalClock, QiClockTime, QiSourceCadence, QiSourceScope


_ZERO = QiClockTime.make(0)
_ONE = QiClockTime.make(1)


def _port(name: str = "homeostasis", dimension: int = 2) -> QiLinearBoundaryPort:
    rows = [[0j] * dimension for _ in range(dimension)]
    for index in range(dimension):
        rows[index][index] = 1.0 + 0.0j
    return QiLinearBoundaryPort.create(
        name=name,
        observation_rows=rows,
        source_metric=[2.0 + index for index in range(dimension)],
        field_metric=[2.0 + index for index in range(dimension)],
        gain=1.0,
        port_indices=range(dimension),
    )


def _clock(scope: QiSourceScope, interval: QiClockTime = _ONE) -> QiCausalClock:
    return QiCausalClock.create(
        tau_0=_ONE,
        field_interval=interval,
        field_steps_per_world_tick=1,
        sources=(QiSourceCadence(scope, interval, _ZERO, 0),),
        max_clock_lcm=64,
    )


def _packet(
    scope: QiSourceScope,
    *,
    sequence: int = 0,
    frontier: QiClockTime = _ONE,
    valid: bool = True,
    clock: QiCausalClock | None = None,
) -> QiBoundaryPacket:
    clock = _clock(scope) if clock is None else clock
    params = inspect.signature(QiBoundaryPacket.create).parameters
    kwargs: dict[str, object] = {
        "clock": clock,
        "scope": scope,
        "source_sequence": sequence,
        "cycle_frontier": frontier,
        "payload_shape": (1,),
        "payload_dtype": "u8",
        "payload": b"x",
        "valid": valid,
    }
    # W7's current packet API carries these identities explicitly. Keeping the
    # helper signature-driven lets the focused test remain readable while the
    # parent boundary cutover lands.
    for name, value in {
        "profile_sha256": "1" * 64,
        "watermark_sha256": "2" * 64,
        "ingress_journal_sha256": "3" * 64,
    }.items():
        if name in params:
            kwargs[name] = value
    if not valid:
        no_sample_params = inspect.signature(QiBoundaryPacket.no_sample).parameters
        no_sample_kwargs = {
            "clock": clock,
            "scope": scope,
            "source_sequence": sequence,
            "cycle_frontier": frontier,
            "reason": "sensor unavailable",
        }
        for name, value in {
            "profile_sha256": "1" * 64,
            "watermark_sha256": "2" * 64,
            "ingress_journal_sha256": "3" * 64,
        }.items():
            if name in no_sample_params:
                no_sample_kwargs[name] = value
        return QiBoundaryPacket.no_sample(**no_sample_kwargs)
    return QiBoundaryPacket.create(**kwargs)


def _profile(*, port: QiLinearBoundaryPort | None = None) -> QiBodyProfile:
    return QiBodyProfile.create(
        profile_id="body-test-v1",
        channel_names=("temperature", "pressure"),
        lower_bounds=(-1.0, -2.0),
        upper_bounds=(1.0, 2.0),
        rest_values=(0.0, 0.0),
        relaxation_rates=(1.0, 2.0),
        drive_gains=(1.0, 0.5),
        energy_metric=(2.0, 3.0),
        integration_interval=_ONE,
        field_ports=() if port is None else (port,),
    )


class QiBodyContractTests(unittest.TestCase):
    def test_profile_is_immutable_and_rest_dynamics_are_bounded(self) -> None:
        profile = _profile()
        state = profile.initial_state()
        receipt = profile.transition(state, drive=(20.0, -20.0))
        self.assertEqual(receipt.successor.clock, _ONE)
        self.assertEqual(receipt.successor.values, (1.0, -2.0))
        self.assertEqual(receipt.clamped_channels, ("pressure", "temperature"))
        self.assertTrue(receipt.transition_sha256)
        with self.assertRaises((AttributeError, TypeError)):
            profile.channel_names += ("extra",)  # type: ignore[misc]

    def test_rest_is_fixed_and_perturbation_recovers(self) -> None:
        profile = _profile()
        rest = profile.initial_state()
        recovered = profile.transition(profile.initial_state(values=(0.8, -1.5)), drive=(0.0, 0.0))
        self.assertEqual(profile.transition(rest, drive=(0.0, 0.0)).successor.values, rest.values)
        self.assertLess(abs(recovered.successor.values[0]), 0.8)
        self.assertLess(abs(recovered.successor.values[1]), 1.5)

    def test_energy_work_closure_is_reported(self) -> None:
        profile = _profile()
        receipt = profile.transition(profile.initial_state(values=(0.25, -0.5)), drive=(0.0, 0.0))
        self.assertAlmostEqual(receipt.energy_delta - receipt.source_work + receipt.dissipation_work - receipt.clamp_work, 0.0, places=11)
        self.assertAlmostEqual(receipt.closure_residual, 0.0, places=11)

    def test_interval_ambiguity_is_rejected_before_state_change(self) -> None:
        profile = _profile()
        state = profile.initial_state()
        with self.assertRaises(QiBodyError):
            profile.transition(state, drive=(0.0, 0.0), dt=0.5)
        with self.assertRaises(QiBodyError):
            profile.transition(state, drive=(0.0, 0.0), start=_ZERO, end=_ONE, dt=_ONE)
        self.assertEqual(state.clock, _ZERO)

    def test_metric_adjoint_homeostasis_uses_registered_port(self) -> None:
        port = _port()
        profile = _profile(port=port)
        state = profile.initial_state(values=(0.25, -0.5))
        observation = profile.homeostasis_observation(state, field_state=torch.tensor([0.25 - 0.5j, 1.0 + 0.25j]))
        self.assertEqual(observation.port_name, port.name)
        self.assertLess(observation.metric_adjoint_residual, 1e-12)
        self.assertEqual(len(observation.observed), 2)
        self.assertTrue(observation.observation_sha256)

    def test_all_channels_and_batch_match_individual_replay(self) -> None:
        profile = _profile()
        states = (profile.initial_state(values=(0.2, 0.1)), profile.initial_state(values=(-0.3, 0.8)))
        drives = torch.tensor([[0.1, -0.2], [0.4, 0.3]], dtype=torch.float64)
        batch = profile.transition_batch(states, drives)
        individual = tuple(profile.transition(state, drives[index]) for index, state in enumerate(states))
        self.assertEqual(tuple(item.successor for item in batch), tuple(item.successor for item in individual))
        self.assertEqual(profile.advance_batch(states, drives), tuple(item.successor for item in individual))

    def test_source_and_clock_identity_mismatch_rejects(self) -> None:
        profile = _profile()
        state = profile.initial_state()
        port = _port("sensor")
        source = QiSourceScope("epoch", "environment", port.descriptor_sha256)
        wrong_source = QiSourceScope("other", "environment", port.descriptor_sha256)
        frame = QiEnvironmentSensorFrame.create(_packet(source), (0.1, 0.2))
        with self.assertRaises(QiBodyError):
            profile.transition(state, frames=(frame,), source=wrong_source)
        later_clock = _clock(source)
        later = QiEnvironmentSensorFrame.create(
            _packet(source, sequence=1, frontier=QiClockTime.make(2), clock=later_clock),
            (0.1, 0.2),
        )
        with self.assertRaises(QiBodyError):
            profile.transition(state, frames=(later,))

    def test_no_sample_is_an_explicit_guarded_noop(self) -> None:
        profile = _profile()
        descriptor = "a" * 64
        source = QiSourceScope("epoch", "environment", descriptor)
        frame = QiBodySensorFrame.create(_packet(source, valid=False), (0.0, 0.0))
        state = profile.initial_state()
        receipt = profile.transition(state, frames=(frame,))
        self.assertFalse(receipt.accepted)
        self.assertTrue(receipt.no_sample)
        self.assertEqual(receipt.successor, state)
        self.assertEqual(receipt.energy_delta, 0.0)

    def test_environment_and_body_frames_retain_w7_identities(self) -> None:
        profile = _profile()
        descriptor = "b" * 64
        source = QiSourceScope("epoch", "environment", descriptor)
        environment = QiEnvironmentSensorFrame.create(_packet(source), (0.2, 0.3))
        body = QiBodySensorFrame.create(_packet(source), (0.0, 0.0))
        receipt = profile.transition(profile.initial_state(), frames=(environment, body))
        self.assertEqual(receipt.packet_identities, (environment.packet_sha256, body.packet_sha256))
        self.assertEqual(receipt.source_identities, (environment.source_scope.key(), body.source_scope.key()))
        self.assertEqual(receipt.body_observation_sha256, body.frame_sha256)

    def test_transition_replay_is_byte_deterministic(self) -> None:
        profile = _profile()
        state = profile.initial_state(values=(0.2, -0.1))
        first = profile.transition(state, drive=(0.3, -0.4))
        second = profile.transition(state, drive=(0.3, -0.4))
        self.assertEqual(first.transition_sha256, second.transition_sha256)
        self.assertEqual(first.successor.state_sha256, second.successor.state_sha256)
        self.assertEqual(first.canonical_payload(), second.canonical_payload())

    def test_invalid_profile_rejects_nonphysical_declarations(self) -> None:
        with self.assertRaises(QiBodyError):
            QiBodyProfile.create(channel_names=("x",), lower_bounds=(1.0,), upper_bounds=(1.0,), integration_interval=_ONE)
        with self.assertRaises(QiBodyError):
            QiBodyProfile.create(channel_names=("x",), lower_bounds=(-1.0,), upper_bounds=(1.0,), rest_values=(2.0,), integration_interval=_ONE)

    def test_canonical_f64_channel_scalar_fixture(self) -> None:
        self.assertEqual(_f64_text("f64:3ff0000000000000", "fixture"), "f64:3ff0000000000000")
        with self.assertRaises(QiBodyError):
            _f64_text("f64:7ff8000000000000", "fixture")
        with self.assertRaises(QiBodyError):
            _f64_text("f64:8000000000000000", "fixture")

    def test_applied_efference_uses_frozen_v1_payload(self) -> None:
        efference = QiEfferenceCopy(
            efference_id="efference.test",
            world_id="world.test",
            episode_id="episode.test",
            session_id="session.test",
            cycle_number=8,
            action_id="action.test",
            command_sha256="c" * 64,
            proposal_sha256="d" * 64,
            reaction_sha256="e" * 64,
            committed_prior_head_sha256="f" * 64,
            application_tick=8,
            first_visible_observation_tick=8,
            actual_values=(("temperature", "f64:3ff0000000000000"),),
            body_transition=("body-frame-before", "body-frame-after", "3" * 64),
            terminal_ack_sha256="1" * 64,
            terminal_ack_bytes="YWNr",
            world_effect=True,
            consumption_status="pending",
        )
        payload = efference.canonical_payload()
        self.assertEqual(
            set(payload),
            {
                "schema",
                "efference_id",
                "world_id",
                "episode_id",
                "session_id",
                "cycle_number",
                "action_id",
                "command_sha256",
                "proposal_sha256",
                "reaction_sha256",
                "committed_prior_head_sha256",
                "application_tick",
                "first_visible_observation_tick",
                "actual_values",
                "body_transition",
                "terminal_ack_sha256",
                "terminal_ack_bytes",
                "world_effect",
                "consumption_status",
                "applied_efference_sha256",
            },
        )
        self.assertEqual(payload["schema"], "cassi.qi-flow-applied-efference.v1")
        self.assertEqual(payload["actual_values"][0]["value"], "f64:3ff0000000000000")
        self.assertEqual(payload["body_transition"]["remap_sha256"], "3" * 64)
        self.assertEqual(payload["terminal_ack_bytes"], "YWNr")
        self.assertEqual(payload["consumption_status"], "pending")
        consumed = efference.consume()
        self.assertEqual(consumed.consumption_status, "consumed")
        self.assertNotEqual(consumed.applied_efference_sha256, efference.applied_efference_sha256)
        with self.assertRaises(QiBodyError):
            consumed.consume()
    def test_factory_requires_terminal_ack_and_projects_transition(self) -> None:
        remap = QiBodyRemapReceipt(
            descriptor_sha256="a" * 64,
            body_frame_id="body-frame",
            predecessor_pose_sha256="b" * 64,
            successor_pose_sha256="c" * 64,
            scale_id="default",
            remap_mode="guarded-periodic",
            affine_a=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            affine_b=(0.0, 0.0, 0.0),
            work=0.0,
            mass_before=1.0,
            mass_after=1.0,
            minimum_before=0.0,
            minimum_after=0.0,
            diffusion_residual=0.0,
            forward_reverse_error=0.0,
            topology_permutation=(),
            admitted=True,
        )
        acknowledgement = {
            "schema": "cassi.qi-flow-tick-ack.v1",
            "world_id": "world.test",
            "episode_id": "episode.test",
            "profile_sha256": "5" * 64,
            "session_id": "session.test",
            "cycle_number": 1,
            "from_tick": 0,
            "to_tick": 1,
            "committed_prior_head_sha256": "8" * 64,
            "action_scope_sha256": "6" * 64,
            "idempotency_key": "idem.test",
            "canonical_intent_sha256": "7" * 64,
            "status": "applied",
            "terminal_status": "applied",
            "world_effect": "true",
            "action_id": "action.test",
            "requested_values": [{"channel_id": "temperature", "value": "f64:3ff0000000000000"}],
            "applied_values": [{"channel_id": "temperature", "value": "f64:3ff0000000000000"}],
            "application_tick": 1,
            "effective_tick": 1,
            "first_visible_observation_tick": 1,
            "body_transition": {
                "before_body_frame_id": "body-frame",
                "after_body_frame_id": "body-frame-next",
                "remap_sha256": remap.remap_sha256,
            },
            "original_terminal_ack_sha256": "4" * 64,
            "ack_bytes": "YWNr",
            "ack_sha256": "d" * 64,
        }
        class ValidatedAck:
            def canonical_payload(self, *, include_hash: bool = True) -> dict[str, object]:
                return dict(acknowledgement)

        validated_ack = ValidatedAck()
        factory_kwargs = {
            "terminal_ack_bytes": b"ack",
            "remap": remap,
            "efference_id": "efference.factory",
            "command_sha256": "e" * 64,
            "proposal_sha256": "f" * 64,
            "reaction_sha256": "1" * 64,
            "committed_prior_head_sha256": "2" * 64,
        }
        with self.assertRaises(QiBodyError):
            QiEfferenceCopy.from_validated_ack(acknowledgement, **factory_kwargs)
        efference = QiEfferenceCopy.from_validated_ack(validated_ack, **factory_kwargs)
        wrong_byte_kwargs = dict(factory_kwargs)
        wrong_byte_kwargs["terminal_ack_bytes"] = b"wrong"
        with self.assertRaises(QiBodyError):
            QiEfferenceCopy.from_validated_ack(validated_ack, **wrong_byte_kwargs)
        self.assertEqual(efference.terminal_ack_bytes, "YWNr")
        self.assertEqual(efference.body_transition[1], "body-frame-next")
        self.assertEqual(efference.terminal_ack_sha256, acknowledgement["original_terminal_ack_sha256"])
        self.assertNotEqual(efference.terminal_ack_sha256, acknowledgement["ack_sha256"])
        prediction = QiBodyPrediction.from_efference(
            predecessor=_profile().initial_state(),
            observation_tick=_ONE,
            predicted_world=(1.0 + 0.0j,),
            predicted_self=(0.25 + 0.0j,),
            efference=efference,
        )
        self.assertEqual(prediction.body_frame_id, "body-frame-next")
        self.assertEqual(prediction.efference_sha256, efference.applied_efference_sha256)
if __name__ == "__main__":
    unittest.main()
