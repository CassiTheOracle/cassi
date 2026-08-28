"""Focused W4 reciprocal carrier contract tests.

The certificate is discovered from the current source-exact W3N PASS tree; no
run identifier is part of the test or of the live carrier law.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

import torch

from cassi_qi_carrier import (
    _replace_coordinates,
    _spectral_half,
    _transition_v4_carrier_split,
    carrier_coordinates,
    carrier_total_energy,
    composition_forces,
    composition_reversal_fixture,
    load_w4_carrier_profile,
    negate_differential_coordinate,
    phase_current_reversal,
    phase_shuffled_equal_energy,
    transition_v4_carrier,
    yang_yin_exchange,
)
from cassi_qi_field import QiFlowGeometryV2, QiFlowStateV3, _w3_damped_spectral_propagate
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_profile import canonical_hash
from cassi_qi_transport import load_w3_transport_profile
from cassi_qi_numerical_certificate import NUMERICAL_CERTIFICATE_DOMAIN


class CarrierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.geometry = load_w2_geometry_profile()
        cls.transport = load_w3_transport_profile(geometry=cls.geometry)
        cls.profile = load_w4_carrier_profile(geometry=cls.geometry, transport=cls.transport)
        roots = sorted(
            (
                Path(__file__).resolve().parent
                / "_diag"
                / "cassi-qi-flow-w3n-periodic-fft2-final"
            ).glob("*/certificate/certificate-root.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        cls.certificate = None
        for root in roots:
            candidate = json.loads(root.read_text(encoding="utf-8"))
            accepted = candidate.get("accepted_w3_artifact_identity")
            if (
                candidate.get("self_sha256")
                == canonical_hash(
                    {key: value for key, value in candidate.items() if key != "self_sha256"},
                    NUMERICAL_CERTIFICATE_DOMAIN,
                )
                and candidate.get("profile_sha256") == cls.transport.profile_sha256
                and candidate.get("transport_semantic_sha256") == cls.transport.transport_semantic_sha256
                and candidate.get("operator_semantic_sha256") == cls.geometry.operator_semantic_sha256
                and candidate.get("w2_parent") == dict(cls.transport.parent_w2)
                and isinstance(accepted, dict)
                and accepted.get("profile_sha256") == cls.transport.profile_sha256
                and accepted.get("contract_root_sha256") == cls.transport.contract_root_sha256
                and accepted.get("semantic_sha256") == cls.transport.transport_semantic_sha256
                and accepted.get("parent_w2_profile_sha256") == cls.geometry.profile_sha256
                and accepted.get("parent_w2_contract_root_sha256") == cls.geometry.contract_root_sha256
            ):
                cls.certificate = candidate
                break
        if cls.certificate is None:
            raise FileNotFoundError("current source-exact W3N certificate tree is missing")
        cls.fixture = composition_reversal_fixture(geometry=cls.geometry, profile=cls.profile)

    def _step(self, state: QiFlowStateV3, *, potential: bool = True):
        return transition_v4_carrier(
            state,
            geometry_profile=self.geometry,
            transport_profile=self.transport,
            carrier_profile=self.profile,
            numerical_certificate=self.certificate,
            potential_enabled=potential,
        )

    def test_fixture_is_equal_density_equal_energy_opposite_epsilon_zero_velocity(self) -> None:
        minus = self.fixture["minus"]
        plus = self.fixture["plus"]
        modes = int(self.geometry.base_profile.state_layout["mode_count"])
        self.assertTrue(
            torch.equal(
                minus.field[:, 4 * modes : 8 * modes, :],
                torch.zeros_like(minus.field[:, 4 * modes : 8 * modes, :]),
            )
        )
        self.assertTrue(
            torch.equal(
                plus.field[:, 4 * modes : 8 * modes, :],
                torch.zeros_like(plus.field[:, 4 * modes : 8 * modes, :]),
            )
        )
        self.assertAlmostEqual(self.fixture["full_energy"]["minus"], self.fixture["full_energy"]["plus"], places=12)
        eps_minus = composition_forces(minus, geometry=self.geometry, profile=self.profile)[2]
        eps_plus = composition_forces(plus, geometry=self.geometry, profile=self.profile)[2]
        for left, right in zip(eps_minus, eps_plus, strict=True):
            self.assertTrue(torch.allclose(left, -right, atol=1.0e-12, rtol=1.0e-12))

    def test_all_scales_and_variable_batch_use_periodic_fft2(self) -> None:
        torch.manual_seed(4)
        state = QiFlowStateV3.create(self.geometry.base_profile, batch_lanes=2)
        modes = int(self.geometry.base_profile.state_layout["mode_count"])
        state.field[:, : 8 * modes, :] = 1.0e-4 * torch.randn_like(state.field[:, : 8 * modes, :])
        before = state.field.clone()
        result = self._step(state, potential=False)
        self.assertTrue(result.committable, result.failure_reason)
        self.assertIsNotNone(result.candidate)
        self.assertTrue(torch.equal(state.field, before))
        self.assertEqual(result.candidate.field.shape[2], 2)
        for row in result.receipt["stage_evidence"]:
            if "spectral" in row:
                self.assertEqual(len(row["spectral"]["branches"]), state.field.shape[0])

    def test_analytic_c_semigroup_matches_w3_helper(self) -> None:
        state = self.fixture["plus"]
        values = carrier_coordinates(state, geometry=self.geometry, profile=self.profile)
        half = 0.5 * self.transport.pinned_parameters.h
        _, transformed, evidence = _spectral_half(
            state,
            values,
            geometry=self.geometry,
            profile=self.profile,
            duration=half,
        )
        surface = QiFlowGeometryV2(state, self.geometry)._surface
        for scale, (position, velocity) in enumerate(zip(values.c, values.vc, strict=True)):
            expected_position, expected_velocity, expected_branch = _w3_damped_spectral_propagate(
                surface,
                scale,
                position,
                velocity,
                duration_s=half,
                c_m_per_s=self.profile.c_c[scale],
                omega_rad_per_s=self.profile.omega_c[scale],
                gamma_per_s=self.profile.gamma_c[scale],
            )
            self.assertTrue(torch.allclose(expected_position, transformed.c[scale], atol=1.0e-15, rtol=1.0e-15))
            self.assertTrue(torch.allclose(expected_velocity, transformed.vc[scale], atol=1.0e-15, rtol=1.0e-15))
            self.assertEqual(evidence["branches"][scale]["C"], expected_branch)

    def test_reciprocal_force_finite_difference_and_phase_conjugation(self) -> None:
        state = self.fixture["plus"]
        fd, fc, eps, potentials = composition_forces(state, geometry=self.geometry, profile=self.profile)
        self.assertTrue(all(torch.isfinite(force).all() for force in (*fd, *fc)))
        self.assertTrue(all(torch.isfinite(value).all() for value in eps))
        self.assertTrue(all(torch.isfinite(torch.tensor(value)) for value in potentials))
        phase = phase_current_reversal(state, geometry=self.geometry)
        rfd, rfc, reps, rpotentials = composition_forces(phase, geometry=self.geometry, profile=self.profile)
        for expected, actual in zip(fd, rfd, strict=True):
            self.assertTrue(torch.allclose(actual, expected.conj(), atol=1.0e-12, rtol=1.0e-12))
        for expected, actual in zip(fc, rfc, strict=True):
            self.assertTrue(torch.allclose(actual, expected.conj(), atol=1.0e-12, rtol=1.0e-12))
        for expected, actual in zip(eps, reps, strict=True):
            self.assertTrue(torch.allclose(actual, expected, atol=1.0e-12, rtol=1.0e-12))
        self.assertEqual(potentials, rpotentials)

    def test_phase_current_reversal_preserves_positive_zero(self) -> None:
        state = self.fixture["plus"]
        modes = int(self.geometry.base_profile.state_layout["mode_count"])
        field = state.field.clone()
        field[:, modes, :] = 0.0
        reversed_state = phase_current_reversal(QiFlowStateV3(field), geometry=self.geometry)
        self.assertFalse(torch.signbit(reversed_state.field[:, modes, :]).any().item())

    def test_seven_stage_schedule_and_work_closure(self) -> None:
        result = self._step(self.fixture["plus"])
        self.assertTrue(result.committable, result.failure_reason)
        stages = result.receipt["stage_evidence"]
        self.assertEqual([row["ordinal"] for row in stages], list(range(1, 8)))
        self.assertEqual(result.receipt["split"], "combined-dc-symmetric-seven-stage.v2")
        composition = result.receipt["composition"]
        self.assertLessEqual(abs(composition["coordinate_work_closure"]), 1.0e-12)
        self.assertTrue(torch.isfinite(torch.tensor(composition["total_coupled_closure"])))

    def test_potential_off_is_exact_uncoupled_combined_dc_reference(self) -> None:
        off = self._step(self.fixture["plus"], potential=False)
        reference = _transition_v4_carrier_split(
            self.fixture["plus"],
            geometry_profile=self.geometry,
            transport_profile=self.transport,
            carrier_profile=self.profile,
            numerical_certificate=self.certificate,
            potential_enabled=False,
        )
        self.assertTrue(off.committable and reference.committable)
        self.assertTrue(torch.equal(off.candidate.field, reference.candidate.field))
        self.assertEqual(off.receipt["potential_off_identity"], "uncoupled-combined-dc-reference-v1")

    def test_source_and_guard_rejection_leave_no_candidate(self) -> None:
        bad_certificate = copy.deepcopy(self.certificate)
        bad_certificate["profile_sha256"] = "0" * 64
        bad_certificate["self_sha256"] = canonical_hash(
            {key: value for key, value in bad_certificate.items() if key != "self_sha256"},
            NUMERICAL_CERTIFICATE_DOMAIN,
        )
        rejected = transition_v4_carrier(
            self.fixture["plus"],
            geometry_profile=self.geometry,
            transport_profile=self.transport,
            carrier_profile=self.profile,
            numerical_certificate=bad_certificate,
        )
        self.assertFalse(rejected.committable)
        self.assertIsNone(rejected.candidate)
        invalid = self.fixture["plus"].field.clone().fill_(1.0e9)
        rejected = self._step(QiFlowStateV3(invalid.contiguous()))
        self.assertFalse(rejected.committable)
        self.assertIsNone(rejected.candidate)

    def test_controls_preserve_registered_invariants(self) -> None:
        original = carrier_coordinates(self.fixture["plus"], geometry=self.geometry, profile=self.profile)
        negated = carrier_coordinates(
            negate_differential_coordinate(self.fixture["plus"], geometry=self.geometry, profile=self.profile),
            geometry=self.geometry,
            profile=self.profile,
        )
        for d, negated_d, c, negated_c in zip(original.d, negated.d, original.c, negated.c, strict=True):
            self.assertTrue(torch.allclose(negated_d, -d, atol=1.0e-12, rtol=1.0e-12))
            self.assertTrue(torch.allclose(negated_c, c, atol=1.0e-12, rtol=1.0e-12))
        shuffled = phase_shuffled_equal_energy(self.fixture["plus"], geometry=self.geometry)
        self.assertAlmostEqual(
            carrier_total_energy(shuffled, geometry=self.geometry, profile=self.profile),
            carrier_total_energy(self.fixture["plus"], geometry=self.geometry, profile=self.profile),
            places=12,
        )
        exchanged = yang_yin_exchange(self.fixture["plus"], geometry=self.geometry, profile=self.profile)
        eps = composition_forces(self.fixture["plus"], geometry=self.geometry, profile=self.profile)[2]
        exchanged_eps = composition_forces(exchanged, geometry=self.geometry, profile=self.profile)[2]
        for expected, actual in zip(eps, exchanged_eps, strict=True):
            self.assertTrue(torch.allclose(actual, -expected, atol=1.0e-12, rtol=1.0e-12))


if __name__ == "__main__":
    unittest.main()
