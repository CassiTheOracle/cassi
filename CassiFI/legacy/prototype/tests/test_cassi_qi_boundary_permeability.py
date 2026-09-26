from __future__ import annotations

import unittest

import torch

from cassi_qi_boundary import QiLinearBoundaryPort
from cassi_qi_boundary_permeability import (
    REQUIRED_OPENNESS_CONTROLS,
    QiBoundaryPermeabilityDescriptor,
    QiBoundaryPermeabilityProfile,
    QiPermeabilityError,
    QiSensoryOpennessReceipt,
    validate_permeability_profile,
    validate_sensory_openness_receipt,
)
from cassi_qi_scattering import validate_scattering_receipt
from cassi_qi_profile import canonical_hash


class BoundaryPermeabilityTest(unittest.TestCase):
    @staticmethod
    def make_profile(**overrides):
        port = QiLinearBoundaryPort.create(
            name="optical",
            observation_rows=((1 + 0j, 0j), (0j, 1 + 0j)),
            source_metric=(1.0, 1.0),
            field_metric=(1.0, 1.0),
            gain=1.0,
            port_indices=(0, 1),
        )
        descriptor = QiBoundaryPermeabilityDescriptor.create(
            port_id="optical",
            interface_id="sensory:optical:scale:0",
            scale=0,
            component=0,
            port=port,
            characteristic_basis=(1 + 0j, 0j),
            metric=(1.0, 1.0),
            geometry_sha256=canonical_hash({"scale": 0}, "cassi.qi-flow-test-geometry.v1"),
            operator_sha256=canonical_hash({"port": port.descriptor_sha256}, "cassi.qi-flow-test-operator.v1"),
            metric_sha256=canonical_hash({"metric": [1.0, 1.0]}, "cassi.qi-flow-test-metric.v1"),
        )
        return QiBoundaryPermeabilityProfile.create(descriptor=descriptor, **overrides)

    def test_positive_ingress_gate_live_frozen_and_controls(self):
        profile = self.make_profile()
        validate_permeability_profile(profile)
        open_state = torch.tensor([1 + 0j, 0j], dtype=torch.complex128)
        closed_state = torch.tensor([-1 + 0j, 0j], dtype=torch.complex128)
        gate = profile.derive_gate(open_state)
        self.assertGreater(gate.value, 0.5)
        live = profile.scatter(1 + 0.25j, duration=2.0, state=open_state, state_samples=(open_state, closed_state), state_gate_mode="live")
        frozen = profile.scatter(1 + 0.25j, duration=2.0, state=open_state, state_samples=(open_state, closed_state), state_gate_mode="frozen")
        self.assertGreater(live.W_transmitted.upper, 0.0)
        self.assertNotEqual(live.W_transmitted.lower, frozen.W_transmitted.lower)
        self.assertLessEqual(abs(live.closure_residual.upper), profile.scatter_bound)
        self.assertAlmostEqual(live.W_incident.upper, live.W_reflected.upper + live.W_transmitted.upper + live.W_absorbed.upper, places=12)
        reversed_current = profile.scatter(-(1 + 0.25j), duration=2.0, state=open_state)
        self.assertAlmostEqual(live.W_incident.upper / 2.0, reversed_current.W_incident.upper / 2.0, places=12)
        self.assertEqual(reversed_current.transmitted_amplitude, -profile.scatter(1 + 0.25j, duration=2.0, state=open_state).transmitted_amplitude)
        permuted = profile.scatter(1 + 0.25j, duration=2.0, state=closed_state, state_samples=(closed_state, open_state), state_gate_mode="live")
        self.assertAlmostEqual(live.W_transmitted.upper, permuted.W_transmitted.upper, places=12)

    def test_admission_receipt_and_rejection_do_not_mutate(self):
        profile = self.make_profile()
        state = torch.tensor([1 + 0j, 0j], dtype=torch.complex128)
        before = state.clone()
        accepted = profile.admit_scratch(state, incident_amplitude=1 + 0.25j, duration=1.0, source_cursor=19)
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.source_cursor_after, 19)
        self.assertTrue(torch.equal(state, before))
        validate_scattering_receipt(accepted.scattering_receipt, port=profile.descriptor.scattering_port(profile.profile_sha256))
        rejected = profile.admit_scratch(state, incident_amplitude=0j, duration=1.0, source_cursor=19)
        self.assertFalse(rejected.accepted)
        self.assertIn("ZERO_INCIDENT_WORK", rejected.failure_reason)
        self.assertTrue(torch.equal(rejected.state, before))
        self.assertEqual(rejected.predecessor_state_sha256, rejected.successor_state_sha256)
        self.assertEqual(rejected.source_cursor_before, rejected.source_cursor_after)

    def test_gate_off_and_openness_receipt(self):
        profile = self.make_profile(eta_trans_min=0.0, eta_trans_max=0.0, eta_abs_min=0.0, eta_abs_max=0.0)
        state = torch.tensor([0 + 0j, 0j], dtype=torch.complex128)
        off = profile.scatter(1 + 0j, duration=1.0, state=state)
        self.assertEqual(off.fractions.transmitted, 0.0)
        self.assertEqual(off.W_transmitted.upper, 0.0)
        self.assertFalse(profile.admit_scratch(state, incident_amplitude=1 + 0j, duration=1.0).accepted)
        profile = self.make_profile()
        pre = torch.tensor([-1 + 0j, 0j], dtype=torch.complex128)
        post = torch.tensor([1 + 0j, 0j], dtype=torch.complex128)
        pre_scatter = profile.scatter(1 + 0j, duration=1.0, state=pre)
        post_scatter = profile.scatter(1 + 0j, duration=1.0, state=post)
        receipt = QiSensoryOpennessReceipt.create(profile=profile, pre_state=pre, post_state=post, pre_scatter=pre_scatter, post_scatter=post_scatter, source_free_horizon=profile.recovery_horizon, recovery_work=0.1, downstream_return_sha256=(canonical_hash({"return": 1}, "cassi.qi-flow-test-return.v1"),), controls=REQUIRED_OPENNESS_CONTROLS)
        validate_sensory_openness_receipt(receipt)
        self.assertGreater(receipt.openness_post.lower, 0.0)

    def test_malformed_negative_unbounded_profiles_and_basis(self):
        with self.assertRaises(QiPermeabilityError):
            self.make_profile(kappa_min=-1.0)
        with self.assertRaises(QiPermeabilityError):
            self.make_profile(eta_trans_max=2.0)
        with self.assertRaises(QiPermeabilityError):
            self.make_profile(observable_norm_max=float("inf"))
        with self.assertRaises(QiPermeabilityError):
            self.make_profile(characteristic_basis=(2 + 0j, 0j))


if __name__ == "__main__":
    unittest.main()
