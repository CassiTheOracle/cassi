"""Focused W4R retention-core contract tests.

These tests intentionally exercise the dynamic W2 sheet and the pure law
without invoking artifact runners or verifiers.
"""

from __future__ import annotations

import unittest

import torch

from run_cassi_qi_topology import _retention_mapping, _state_from_phase
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_topology import (
    TopologyError,
    _reset_authorized,
    _coordinates_from_state,
    _replace_coordinates,
    _metric_cell_area,
    _sha256,
    _validate_numerical_certificate,
    barrier_bounds,
    load_w4r_topology_profile,
    make_topology_fixture,
    radial_curvature_bound,
    topological_force,
    topological_potential,
    topology_diagnostics,
)


class RetentionCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = load_w2_geometry_profile()
        cls.profile = load_w4r_topology_profile(geometry=cls.geometry)

    def test_dynamic_sheet_and_registered_algebra(self):
        shape = tuple(self.profile.payload["active_shape_yx"])
        self.assertEqual(shape, tuple(self.geometry.active_shapes[self.profile.slow_scale]))
        self.assertEqual(len(self.profile.edge_registry), 2 * shape[0] * shape[1])
        self.assertEqual(len(self.profile.cycle_registry["x_cycles"]), shape[0])
        self.assertEqual(len(self.profile.cycle_registry["y_cycles"]), shape[1])
        self.assertFalse(self.profile.payload["additional_state"])
        self.assertEqual((self.profile.a_topo, self.profile.b_topo), (0.0, 1.0))
        self.assertEqual(len(self.profile.payload["metric_diagonal"]), shape[0] * shape[1])

    def test_zero_and_one_sector_vectors(self):
        zero = topology_diagnostics(make_topology_fixture(geometry=self.geometry, kind="plane-wave"), geometry=self.geometry, profile=self.profile)
        one = topology_diagnostics(make_topology_fixture(geometry=self.geometry, kind="vortex"), geometry=self.geometry, profile=self.profile)
        self.assertEqual(zero["status"], "VALID")
        self.assertEqual(one["status"], "VALID")
        self.assertTrue(all(value == 0 for value in zero["sector_vector"][0]["n_x"]))
        self.assertTrue(any(value == 1 for value in one["sector_vector"][0]["n_x"]))
        self.assertEqual(len(one["sector_vector"][0]["p"]), self.profile.payload["active_shape_yx"][0])
    def test_runner_codewords_live_only_on_selected_sheet(self):
        retention = _retention_mapping(self.profile)
        cycle = _state_from_phase(geometry=self.geometry, retention=retention, kind="cycle-positive", wx=1.0)
        for scale in range(cycle.field.shape[0]):
            if scale != self.profile.slow_scale:
                self.assertTrue(torch.count_nonzero(cycle.field[scale]) == 0)
        self.assertEqual(topology_diagnostics(cycle, geometry=self.geometry, profile=self.profile)["status"], "VALID")
        pair = _state_from_phase(geometry=self.geometry, retention=retention, kind="vortex-antivortex")
        diagnostic = topology_diagnostics(pair, geometry=self.geometry, profile=self.profile)
        self.assertEqual(diagnostic["status"], "VALID")
        charges = [value for row in diagnostic["sector_vector"][0]["p"] for value in row]
        self.assertEqual(charges.count(1), 1)
        self.assertEqual(charges.count(-1), 1)
        self.assertEqual(sum(charges), 0)


    def test_phase_scramble_and_amplitude_guards(self):
        scrambled = topology_diagnostics(make_topology_fixture(geometry=self.geometry, kind="phase-scramble"), geometry=self.geometry, profile=self.profile)
        zero = topology_diagnostics(make_topology_fixture(geometry=self.geometry, kind="zero"), geometry=self.geometry, profile=self.profile)
        self.assertNotEqual(scrambled["status"], "VALID")
        self.assertEqual(zero["reason"], "amplitude-floor")

    def test_energy_is_current_even(self):
        state = make_topology_fixture(geometry=self.geometry, kind="plane-wave")
        energy = topological_potential(state, geometry=self.geometry, profile=self.profile)
        flipped = state.field.clone()
        modes = self.geometry.base_profile.state_layout["mode_count"]
        flipped[self.profile.slow_scale, 4 * modes:8 * modes, :] *= -1.0
        opposite = QiFlowStateV3(flipped.contiguous())
        opposite.validate(self.geometry.base_profile)
        self.assertEqual(energy, topological_potential(opposite, geometry=self.geometry, profile=self.profile))
        current_a = topology_diagnostics(state, geometry=self.geometry, profile=self.profile)["phase_current"]
        current_b = topology_diagnostics(opposite, geometry=self.geometry, profile=self.profile)["phase_current"]
        self.assertEqual(current_a, [-value for value in current_b])

    def test_force_is_smooth_and_slow_scale_only(self):
        state = make_topology_fixture(geometry=self.geometry, kind="ring")
        forces = topological_force(state, geometry=self.geometry, profile=self.profile)
        self.assertEqual(len(forces["D"]), len(self.geometry.active_shapes))
        self.assertTrue(torch.allclose(forces["D"][self.profile.slow_scale], torch.zeros_like(forces["D"][self.profile.slow_scale])))
        self.assertGreater(float(forces["C"][self.profile.slow_scale].abs().max()), 0.0)
        for scale in range(len(self.geometry.active_shapes) - 1):
            self.assertTrue(torch.allclose(forces["C"][scale], torch.zeros_like(forces["C"][scale])))

    def test_force_is_metric_gradient_of_topological_potential(self):
        state = make_topology_fixture(geometry=self.geometry, kind="ring")
        scale = self.profile.slow_scale
        d, c, vd, vc = _coordinates_from_state(state, self.geometry, scale)
        delta = 1.0e-6
        direction = torch.zeros_like(c)
        direction[0, 0, 0] = 1.0
        plus = _replace_coordinates(
            state,
            geometry=self.geometry,
            profile=self.profile,
            d=d,
            c=c + delta * direction,
            vd=vd,
            vc=vc,
        )
        minus = _replace_coordinates(
            state,
            geometry=self.geometry,
            profile=self.profile,
            d=d,
            c=c - delta * direction,
            vd=vd,
            vc=vc,
        )
        derivative = (
            topological_potential(plus, geometry=self.geometry, profile=self.profile)
            - topological_potential(minus, geometry=self.geometry, profile=self.profile)
        ) / (2.0 * delta)
        force = topological_force(state, geometry=self.geometry, profile=self.profile)["C"][scale][0, 0, 0].real.item()
        cell_area = _metric_cell_area(self.geometry, scale)
        self.assertAlmostEqual(derivative, -self.profile.w_c * cell_area * force, delta=2.0e-8)

    def test_barrier_curvature_and_reset_authorization(self):
        barrier = barrier_bounds(geometry=self.geometry, profile=self.profile)
        curvature = radial_curvature_bound(geometry=self.geometry, profile=self.profile)
        self.assertLess(barrier["lower"], barrier["upper"])
        self.assertTrue(curvature["valid"])
        state = make_topology_fixture(geometry=self.geometry, kind="plane-wave")
        with self.assertRaises(TopologyError):
            _reset_authorized({"authorized": True, "predecessor_state_sha256": "wrong", "reason": "test"}, "actual")
        with self.assertRaises(TopologyError):
            _reset_authorized({"authorized": False, "predecessor_state_sha256": "actual", "reason": "test"}, "actual")

    def test_g3n_ancestry_requires_all_w2_identities(self):
        body = {
            "schema": "cassi.qi-flow-numerical-certificate.v1",
            "w2_parent": {},
            "online_guard_contract": {
                "schema": "cassi.qi-flow-numerical-guard.v1",
            },
        }
        certificate = dict(body)
        certificate["self_sha256"] = _sha256(body, "cassi.qi-flow-numerical-certificate.v1")
        with self.assertRaises(TopologyError):
            _validate_numerical_certificate(certificate, self.geometry)


if __name__ == "__main__":
    unittest.main()
