from __future__ import annotations

import inspect
import unittest

import torch

import cassi_qi_transport as runtime_contract
from cassi_qi_field import (
    QiFlowStateV3,
    _w3_damped_spectral_propagate,
    transition_v3_transport,
)
from cassi_qi_geometry import (
    MODE_COUNT,
    PeriodicSheetGeometry,
    load_w2_geometry_profile,
)
from cassi_qi_profile import (
    PROFILE_MISMATCH,
    canonical_json_bytes,
    canonical_json_loads,
    finite_float,
    load_development_profile,
)
from cassi_qi_transport import (
    W3_G3_STAGE_SCHEDULE,
    W3_H_S,
    W3_STAGE_SCHEDULE_SCHEMA,
    build_w3_transport_profile,
    load_w3_transport_profile,
    projected_pseudospectral_operators,
    validate_w3_transport_profile,
    w3_stage_schedule,
)


class W3TransportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_profile = load_development_profile()
        cls.geometry_profile = load_w2_geometry_profile(base_profile=cls.base_profile)
        cls.surface = PeriodicSheetGeometry(cls.geometry_profile)
        cls.transport = load_w3_transport_profile(
            base_profile=cls.base_profile,
            geometry_profile=cls.geometry_profile,
        )
        cls.duration = finite_float(W3_H_S, name="W3 release step")

    @staticmethod
    def _complex(shape: tuple[int, ...], seed: int) -> torch.Tensor:
        generator = torch.Generator(device="cpu").manual_seed(seed)
        return (
            torch.randn(shape, dtype=torch.float64, generator=generator)
            + 1.0j * torch.randn(shape, dtype=torch.float64, generator=generator)
        ).contiguous()

    def _state(self, *, seed: int = 1) -> QiFlowStateV3:
        state = QiFlowStateV3.create(self.base_profile, batch_lanes=1)
        field = state.field.clone()
        generator = torch.Generator(device="cpu").manual_seed(seed)
        for scale in range(self.geometry_profile.scale_count):
            active = self.surface.active_site_count(scale)
            # Keep the fixture well inside the profile bound while exercising
            # every scale and every packed coordinate pair.
            for component in range(8):
                start = component * MODE_COUNT
                values = 1.0e-4 * torch.randn((active, 1), dtype=torch.float64, generator=generator)
                field[scale, start : start + active].copy_(values)
        return QiFlowStateV3(field.contiguous())

    @staticmethod
    def _conjugate_state(state: QiFlowStateV3) -> QiFlowStateV3:
        field = state.field.clone()
        for component in (1, 3, 5, 7):
            start = component * MODE_COUNT
            field[:, start : start + MODE_COUNT].neg_()
        return QiFlowStateV3(field.contiguous())

    def test_profile_binds_exact_current_w2_ancestry(self) -> None:
        parent = self.transport.parent_w2
        self.assertEqual(parent["profile_sha256"], self.geometry_profile.profile_sha256)
        self.assertEqual(parent["contract_root_sha256"], self.geometry_profile.contract_root_sha256)
        self.assertEqual(parent["geometry_contract_sha256"], self.geometry_profile.geometry_contract_sha256)
        self.assertEqual(parent["operator_semantic_sha256"], self.geometry_profile.operator_semantic_sha256)
        self.assertNotIn("run_id", parent)
        self.assertNotIn("path", parent)

        semantic = self.transport.semantic_payload
        self.assertEqual(
            semantic["geometry"]["profile_sha256"],
            self.geometry_profile.profile_sha256,
        )
        self.assertEqual(
            len(semantic["geometry"]["per_scale"]),
            self.geometry_profile.scale_count,
        )
        for scale, row in enumerate(semantic["geometry"]["per_scale"]):
            self.assertEqual(row["scale"], scale)
            self.assertEqual(row["shape_yx"], tuple(self.surface.sheet_shape(scale)))
            self.assertEqual(row["laplacian_symbol"], "-(kx^2+ky^2)")
            self.assertEqual(row["k2_symbol"], "kx^2+ky^2")

        self.assertIs(validate_w3_transport_profile(self.transport, geometry_profile=self.geometry_profile).__class__, self.transport.__class__)

    def test_all_scales_use_literal_k2_contract(self) -> None:
        operator = self.transport.semantic_payload["operator"]
        self.assertEqual(operator["spatial_operator_family"], "periodic-fft2.v1")
        self.assertEqual(operator["laplacian_symbol"], "-(kx^2+ky^2)")
        self.assertEqual(operator["transform_axes"], "(y,x)")
        self.assertEqual(operator["branches"], ("underdamped", "critical", "overdamped"))
        self.assertEqual(
            operator["damping"],
            "analytic-2x2-damped-oscillator-exactly-once",
        )
        self.assertEqual(
            self.transport.semantic_payload["dynamics"]["branch_evaluation"],
            "exactly-once-per-spectral-half-step",
        )

    def test_projected_operators_roundtrip_projector_and_metric_adjoint(self) -> None:
        for scale in range(self.geometry_profile.scale_count):
            ny, nx = self.surface.sheet_shape(scale)
            factors = tuple(
                int(value)
                for value in self.geometry_profile.payload["geometry_contract"]["per_scale_sheets"][scale]["oversampling"]["factors_yx"]
            )
            operators = projected_pseudospectral_operators(self.surface, scale)
            coarse = self._complex((ny, nx, 1), seed=31 + scale)
            fine = self._complex((ny * factors[0], nx * factors[1], 1), seed=41 + scale)

            interpolated = operators.I(coarse)
            restricted = operators.R(interpolated)
            projected = operators.P(fine)
            torch.testing.assert_close(restricted, coarse, rtol=0.0, atol=1.0e-10)
            torch.testing.assert_close(operators.P(projected), projected, rtol=0.0, atol=1.0e-10)
            torch.testing.assert_close(operators.I_adjoint(fine), operators.R(fine), rtol=0.0, atol=0.0)
            torch.testing.assert_close(operators.R_adjoint(coarse), operators.I(coarse), rtol=0.0, atol=0.0)

            left = self.surface.weighted_inner(interpolated, fine, scale=scale, refinement=factors)
            right = self.surface.weighted_inner(coarse, restricted if fine.data_ptr() == interpolated.data_ptr() else operators.R(fine), scale=scale)
            torch.testing.assert_close(left, right, rtol=0.0, atol=1.0e-9)

    def test_schedule_order_durations_and_canonical_release_default(self) -> None:
        schedule = w3_stage_schedule(self.duration)
        self.assertEqual(canonical_json_bytes(schedule), canonical_json_bytes(W3_G3_STAGE_SCHEDULE))
        self.assertIsNot(schedule, W3_G3_STAGE_SCHEDULE)
        self.assertEqual(schedule["substeps"], 7)
        self.assertEqual(W3_G3_STAGE_SCHEDULE["substeps"], 7)
        with self.assertRaises(TypeError):
            W3_G3_STAGE_SCHEDULE["stages"][0]["reads"][0] = "mutated"
        with self.assertRaises(AttributeError):
            W3_G3_STAGE_SCHEDULE["stages"].append({})
        self.assertEqual(schedule["schema"], W3_STAGE_SCHEDULE_SCHEMA)
        self.assertEqual([row["ordinal"] for row in schedule["stages"]], list(range(1, 8)))
        self.assertEqual(
            [row["name"] for row in schedule["stages"]],
            [
                "preflight",
                "first_local_force_velocity_half_kick",
                "first_analytic_damped_spectral_half_propagation",
                "centered_conversion_placeholder",
                "second_analytic_damped_spectral_half_propagation",
                "second_local_force_velocity_half_kick",
                "precommit",
            ],
        )
        durations = [finite_float(row["duration_s"], name="stage duration") for row in schedule["stages"]]
        expected = [0.0, self.duration / 2.0, self.duration / 2.0, self.duration, self.duration / 2.0, self.duration / 2.0, 0.0]
        self.assertEqual(durations, expected)
        self.assertEqual(schedule["stages"][3]["mode"], "inactive-w3")
        self.assertEqual(
            schedule["stages"][3]["dependencies"],
            ["first_analytic_damped_spectral_half_propagation"],
        )
        self.assertEqual(
            schedule["stages"][-1]["dependencies"],
            ["second_local_force_velocity_half_kick"],
        )

        refined = w3_stage_schedule(self.duration / 2.0)
        self.assertEqual(
            [finite_float(row["duration_s"], name="refined stage duration") for row in refined["stages"]],
            [0.0, self.duration / 4.0, self.duration / 4.0, self.duration / 2.0, self.duration / 4.0, self.duration / 4.0, 0.0],
        )

    def test_wrong_w2_profile_is_rejected_before_transport_build(self) -> None:
        altered = canonical_json_loads(canonical_json_bytes(self.geometry_profile.payload))
        altered["geometry_contract"]["per_scale_sheets"][0]["active_rectangle"]["shape_yx"][0] += 1
        with self.assertRaises(PROFILE_MISMATCH):
            build_w3_transport_profile(
                base_profile=self.base_profile,
                geometry_profile=altered,
            )

        with self.assertRaises(PROFILE_MISMATCH):
            validate_w3_transport_profile(
                self.transport.payload,
                geometry_profile=altered,
            )

    def test_source_rejection_zero_step_and_all_scale_transition(self) -> None:
        zero = QiFlowStateV3.create(self.base_profile, batch_lanes=1)
        before = zero.field.clone()
        zero_step = transition_v3_transport(
            zero,
            geometry_profile=self.geometry_profile,
            transport_profile=self.transport,
            duration_s=0.0,
        )
        self.assertTrue(zero_step.committable)
        self.assertIsNotNone(zero_step.candidate)
        torch.testing.assert_close(zero.field, before, rtol=0.0, atol=0.0)
        torch.testing.assert_close(zero_step.candidate.field, before, rtol=0.0, atol=0.0)

        rejected = transition_v3_transport(
            zero,
            geometry_profile=self.geometry_profile,
            transport_profile=self.transport,
            source={"forbidden": True},
        )
        self.assertFalse(rejected.committable)
        self.assertIsNone(rejected.candidate)
        torch.testing.assert_close(zero.field, before, rtol=0.0, atol=0.0)

        state = self._state(seed=53)
        step = transition_v3_transport(
            state,
            geometry_profile=self.geometry_profile,
            transport_profile=self.transport,
            duration_s=self.duration,
        )
        self.assertTrue(step.committable)
        self.assertIsNotNone(step.candidate)
        self.assertTrue(bool(torch.isfinite(step.candidate.field).all().item()))
        tails = self.surface.zero_tail_proof(step.candidate.field)
        self.assertTrue(tails["inactive_tail_is_exact_zero"])

    def test_exact_spectral_propagator_covers_all_three_branches(self) -> None:
        scale = 0
        shape = (*self.surface.sheet_shape(scale), 1)
        position = self._complex(shape, 301)
        velocity = self._complex(shape, 302)
        active = self.surface.active_site_count(scale)
        for omega, gamma, branch in (
            (2.0, 1.0, "underdamped"),
            (1.0, 2.0, "critical"),
            (0.5, 2.0, "overdamped"),
        ):
            full_position, full_velocity, counts = _w3_damped_spectral_propagate(
                self.surface,
                scale,
                position,
                velocity,
                duration_s=self.duration,
                c_m_per_s=0.0,
                omega_rad_per_s=omega,
                gamma_per_s=gamma,
            )
            half_position, half_velocity, _ = _w3_damped_spectral_propagate(
                self.surface,
                scale,
                position,
                velocity,
                duration_s=0.5 * self.duration,
                c_m_per_s=0.0,
                omega_rad_per_s=omega,
                gamma_per_s=gamma,
            )
            twice_position, twice_velocity, _ = _w3_damped_spectral_propagate(
                self.surface,
                scale,
                half_position,
                half_velocity,
                duration_s=0.5 * self.duration,
                c_m_per_s=0.0,
                omega_rad_per_s=omega,
                gamma_per_s=gamma,
            )
            self.assertEqual(counts[branch], active)
            self.assertLessEqual(float((twice_position - full_position).abs().max()), 1.0e-13)
            self.assertLessEqual(float((twice_velocity - full_velocity).abs().max()), 1.0e-13)

    def test_damping_work_is_dissipative_and_closes_energy(self) -> None:
        step = transition_v3_transport(
            self._state(seed=91),
            geometry_profile=self.geometry_profile,
            transport_profile=self.transport,
            duration_s=self.duration,
        )
        self.assertTrue(step.committable)
        self.assertIsNotNone(step.diagnostics)
        self.assertIsNotNone(step.ledger)
        self.assertLessEqual(step.diagnostics.damping_work, 0.0)
        self.assertAlmostEqual(
            step.diagnostics.post_energy - step.diagnostics.pre_energy,
            step.diagnostics.damping_work + step.ledger.numerical_residual,
            delta=1.0e-18,
        )
        self.assertLessEqual(abs(step.diagnostics.phase_continuity_residual), 1.0e-18)

    def test_phase_conjugation_and_profile_mismatch(self) -> None:
        state = self._state(seed=71)
        conjugate = self._conjugate_state(state)
        left = transition_v3_transport(
            state,
            geometry_profile=self.geometry_profile,
            transport_profile=self.transport,
            duration_s=self.duration,
        )
        right = transition_v3_transport(
            conjugate,
            geometry_profile=self.geometry_profile,
            transport_profile=self.transport,
            duration_s=self.duration,
        )
        self.assertTrue(left.committable)
        self.assertTrue(right.committable)
        self.assertIsNotNone(left.candidate)
        self.assertIsNotNone(right.candidate)
        expected = self._conjugate_state(left.candidate)
        torch.testing.assert_close(right.candidate.field, expected.field, rtol=0.0, atol=1.0e-9)

        altered = canonical_json_loads(canonical_json_bytes(self.geometry_profile.payload))
        altered["geometry_contract"]["per_scale_sheets"][0]["origin_m"][0] = "f64:3ff0000000000000"
        with self.assertRaises(PROFILE_MISMATCH):
            transition_v3_transport(
                state,
                geometry_profile=altered,
                transport_profile=self.transport,
                duration_s=self.duration,
            )

    def test_stale_single_sheet_semantics_are_not_exported(self) -> None:
        self.assertFalse(hasattr(runtime_contract, "W3_GRID_SHAPE"))
        source = inspect.getsource(runtime_contract).lower()
        for stale in ("fftn", "second-difference", "shared-eigenvalue", "(2, 4, 4)"):
            self.assertNotIn(stale, source)
        self.assertNotIn("unitary-3d", source)


if __name__ == "__main__":
    unittest.main()
