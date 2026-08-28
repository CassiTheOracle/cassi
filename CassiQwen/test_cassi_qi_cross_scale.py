"""Focused W6 reciprocal-link and FFT2 Hodge contract checks.

These tests intentionally use only the fixed W2 geometry and the in-memory
state tensor; no receipt, artifact, runner, or alternate state is involved.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import unittest
from unittest.mock import patch

import torch

import cassi_qi_conversion as conversion
from cassi_qi_carrier import carrier_coordinates, load_w4_carrier_profile
from cassi_qi_cross_scale import (
    CrossScaleError,
    QiCrossScaleLaw,
    QiCrossScaleProfile,
    _component_grid,
    _fallback_coordinates,
    _transition_w6_split,
    cross_scale_continuity,
    cross_scale_energy,
    cross_scale_forces,
    cross_scale_phase_current,
    hodge_decompose,
    link_off,
    load_w6_cross_scale_profile,
    phase_current_reversal,
    phase_shuffled_equal_energy,
    spatial_currents,
    transition_w6_integrated,
    validate_w6_cross_scale_profile,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import PeriodicSheetGeometry, load_w2_geometry_profile
from cassi_qi_profile import load_development_profile
from cassi_qi_topology import load_w4r_topology_profile, make_topology_fixture
from cassi_qi_transport import load_w3_transport_profile
@dataclass
class _FakeCarrierStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: dict
    failure_reason: str | None = None
    intermediates: dict | None = None


def _fake_carrier_split(
    state,
    *,
    geometry_profile,
    transport_profile,
    carrier_profile,
    numerical_certificate,
    duration_s=None,
    potential_enabled=True,
    additional_force=None,
    center_map=None,
):
    del transport_profile, numerical_certificate, duration_s, potential_enabled
    coordinates = carrier_coordinates(state, geometry=geometry_profile, profile=carrier_profile)
    try:
        first = additional_force(state, geometry_profile, carrier_profile, coordinates) if additional_force else None
        centered = center_map(state, geometry_profile, carrier_profile, coordinates) if center_map else coordinates
        if isinstance(centered, QiFlowStateV3):
            center_state = centered
        else:
            center_state = conversion._replace_coordinates(
                state,
                geometry=geometry_profile,
                profile=carrier_profile,
                d=centered.d,
                c=centered.c,
                vd=centered.vd,
                vc=centered.vc,
            )
        center_coordinates = carrier_coordinates(center_state, geometry=geometry_profile, profile=carrier_profile)
        second = additional_force(center_state, geometry_profile, carrier_profile, center_coordinates) if additional_force else None
        receipt = {
            "schema": "test-carrier-receipt",
            "status": "PASS",
            "center_map": "profile-bound-center-map.v1",
            "stage_schedule": {
                "stages": [
                    {"ordinal": 1, "name": "preflight"},
                    {"ordinal": 2, "name": "first_local_force_velocity_half_kick"},
                    {"ordinal": 3, "name": "first_analytic_damped_spectral_half_propagation"},
                    {"ordinal": 4, "name": "centered_conversion_placeholder"},
                    {"ordinal": 5, "name": "second_analytic_damped_spectral_half_propagation"},
                    {"ordinal": 6, "name": "second_local_force_velocity_half_kick"},
                    {"ordinal": 7, "name": "precommit"},
                ]
            },
            "force_evaluations": 2 if additional_force else 0,
            "force_callbacks": {"first": first is not None, "second": second is not None},
        }
        intermediates = {
            "predecessor": QiFlowStateV3(state.field.detach().contiguous().clone()),
            "post-first-kick": QiFlowStateV3(state.field.detach().contiguous().clone()),
            "post-first-spectral/pre-center": QiFlowStateV3(state.field.detach().contiguous().clone()),
            "post-center": QiFlowStateV3(center_state.field.detach().contiguous().clone()),
            "post-second-spectral": QiFlowStateV3(center_state.field.detach().contiguous().clone()),
            "post-second-kick/pre-EMA": QiFlowStateV3(center_state.field.detach().contiguous().clone()),
        }
        return _FakeCarrierStep(state, center_state, True, receipt, None, intermediates)
    except Exception as exc:
        return _FakeCarrierStep(state, None, False, {"schema": "test-carrier-receipt", "status": "REJECTED"}, str(exc))


class _RuntimeFixtures:
    """W1-W5 parent profiles for the focused private-transition smoke."""

    @classmethod
    def build(cls):
        base = load_development_profile()
        geometry = load_w2_geometry_profile(base_profile=base)
        transport = load_w3_transport_profile(geometry_profile=geometry)
        carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
        topology = load_w4r_topology_profile(geometry=geometry, carrier_profile=carrier)
        conversion_profile = conversion.load_w5_conversion_profile(
            geometry_profile=geometry,
            transport_profile=transport,
            carrier_profile=carrier,
            topology_profile=topology,
        )
        cross_scale = load_w6_cross_scale_profile(geometry_profile=geometry, carrier_profile=carrier)
        state = make_topology_fixture(geometry=geometry, kind="plane-wave", batch_lanes=2)
        return geometry, transport, carrier, topology, conversion_profile, cross_scale, state


class CrossScaleCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.geometry = PeriodicSheetGeometry()
        cls.scales = cls.geometry.profile.scale_count
        cls.modes = int(cls.geometry.profile.base_profile.state_layout["mode_count"])
        cls.profile = QiCrossScaleProfile(
            scale_count=cls.scales,
            g_D=tuple(0.25 + 0.1 * i for i in range(cls.scales - 1)),
            g_C=tuple(0.4 + 0.1 * i for i in range(cls.scales - 1)),
            phi=(1.0 + 5.0**0.5) / 2.0,
            c_D=tuple(1.0 for _ in range(cls.scales)),
            c_C=tuple(2.0 for _ in range(cls.scales)),
            tolerances={"operator": 1e-8, "energy": 1e-8, "work": 1e-8, "current": 1e-8, "hodge": 1e-8},
        )
        cls.law = QiCrossScaleLaw(cls.profile)

    def state(self, batch: int = 2) -> torch.Tensor:
        value = torch.zeros((self.scales, 9 * self.modes, batch), dtype=torch.float64)
        value[:, 0, :] = 1.0
        value[:, self.modes, :] = 0.25
        value[:, 2 * self.modes + 1, :] = -0.1
        value[:, 4 * self.modes, :] = 0.05
        value[:, 6 * self.modes + 1, :] = 0.02
        return value.contiguous()

    def test_fallback_C_uses_C_metric_weight(self) -> None:
        state = self.state(batch=1)
        _d_values, c_values, _vd_values, vc_values = _fallback_coordinates(state, self.geometry, self.profile)
        ey = torch.complex(_component_grid(state, self.geometry, 0, 0), _component_grid(state, self.geometry, 0, 1))
        ei = torch.complex(_component_grid(state, self.geometry, 0, 2), _component_grid(state, self.geometry, 0, 3))
        vy = torch.complex(_component_grid(state, self.geometry, 0, 4), _component_grid(state, self.geometry, 0, 5))
        vi = torch.complex(_component_grid(state, self.geometry, 0, 6), _component_grid(state, self.geometry, 0, 7))
        self.assertTrue(torch.allclose(c_values[0], self.profile.w_C * (self.profile.phi * ey + ei)))
        self.assertTrue(torch.allclose(vc_values[0], self.profile.w_C * (self.profile.phi * vy + vi)))

    def test_phi_and_speeds_are_required(self) -> None:
        common = {
            "scale_count": self.scales,
            "g_D": self.profile.g_D,
            "g_C": self.profile.g_C,
            "phi": self.profile.phi,
            "c_D": self.profile.c_D,
            "c_C": self.profile.c_C,
        }
        for omitted in ("phi", "c_D", "c_C"):
            candidate = dict(common)
            candidate[omitted] = None
            with self.assertRaises(CrossScaleError):
                QiCrossScaleProfile(**candidate)

    def test_serialized_profile_preserves_and_checks_root_identity(self) -> None:
        serialized = dict(self.profile.payload)
        serialized["root"] = dict(self.profile.root)
        serialized["root_sha256"] = self.profile.root_sha256
        restored = validate_w6_cross_scale_profile(serialized)
        self.assertEqual(restored.profile_sha256, self.profile.profile_sha256)
        self.assertEqual(restored.root_sha256, self.profile.root_sha256)
        self.assertEqual(restored.operator_identity, self.profile.operator_identity)
        tampered = dict(serialized)
        tampered["root_sha256"] = "0" * 64
        with self.assertRaises(CrossScaleError):
            validate_w6_cross_scale_profile(tampered)

        tampered_root = dict(serialized)
        tampered_root["root"] = dict(serialized["root"])
        tampered_root["root"]["tampered"] = True
        with self.assertRaises(CrossScaleError):
            validate_w6_cross_scale_profile(tampered_root)

    def test_profile_and_law_are_immutable(self) -> None:
        with self.assertRaises((AttributeError, TypeError)):
            self.profile.g_D = (1.0,)  # type: ignore[misc]
        self.assertEqual(self.law.law_id, self.profile.law_id)
        self.assertEqual(self.profile.scale_count, self.scales)
        self.assertEqual(len(self.profile.g_D), self.scales - 1)

    def test_reciprocal_forces_and_link_off(self) -> None:
        state = self.state()
        forces = self.law.additional_force(state, self.geometry)
        self.assertEqual(tuple(force.shape[-1] for force in forces[0]), (2,) * self.scales)
        self.assertTrue(torch.isfinite(cross_scale_energy(state, geometry=self.geometry, profile=self.profile)))
        off = link_off(self.law)
        off_energy = off.energy(state, self.geometry)
        self.assertEqual(float(off_energy), 0.0)
        self.assertTrue(all(torch.count_nonzero(force) == 0 for force in off.additional_force(state, self.geometry)[0]))

    def test_phase_reversal_and_equal_energy_shuffle_do_not_mutate(self) -> None:
        state = self.state()
        original = state.clone()
        reversed_state = phase_current_reversal(state)
        shuffled_state = phase_shuffled_equal_energy(state)
        self.assertTrue(torch.equal(state, original))
        self.assertEqual(reversed_state.shape, state.shape)
        self.assertEqual(shuffled_state.shape, state.shape)
        self.assertTrue(torch.equal(shuffled_state.square().sum(), state.square().sum()))
        current = cross_scale_phase_current(state, geometry=self.geometry, profile=self.profile)
        reversed_current = cross_scale_phase_current(reversed_state, geometry=self.geometry, profile=self.profile)
        for before, after in zip(current, reversed_current, strict=True):
            self.assertTrue(torch.allclose(after, -before, atol=1e-9, rtol=1e-9))

    def test_hodge_reconstruction_and_symbol_rejection(self) -> None:
        state = self.state()
        current = spatial_currents(state, geometry=self.geometry, profile=self.profile, coordinate="D")[0]
        result = hodge_decompose(current, geometry=self.geometry, scale=0)
        self.assertTrue(torch.allclose(result.longitudinal + result.transverse + result.harmonic, current.to(torch.complex128), atol=1e-8, rtol=1e-8))
        with self.assertRaises(CrossScaleError):
            hodge_decompose(current, geometry=self.geometry, scale=0, derivative_symbols={"kx": [0.0], "ky": [0.0]})

    def test_continuity_has_exact_endpoint_zero_rows(self) -> None:
        state = self.state()
        receipt = cross_scale_continuity(state, state, geometry=self.geometry, profile=self.profile, duration_s=1.0)
        self.assertTrue(receipt["per_scale"][0]["endpoint_incoming_exact_zero"])
        self.assertTrue(receipt["per_scale"][-1]["endpoint_outgoing_exact_zero"])
        self.assertTrue(torch.allclose(receipt["internal_K_cancellation"], torch.zeros_like(receipt["internal_K_cancellation"])))

    def test_private_w6_transition_contract_is_wired_to_w5(self) -> None:
        signature = inspect.signature(_transition_w6_split)
        self.assertIn("cross_scale_law", signature.parameters)
        self.assertIn("extra_conservative_law", inspect.signature(__import__("cassi_qi_conversion", fromlist=["_transition_w5_split"])._transition_w5_split).parameters)


if __name__ == "__main__":
    unittest.main()
