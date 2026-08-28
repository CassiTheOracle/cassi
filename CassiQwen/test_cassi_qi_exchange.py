from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import unittest

import torch

from cassi_qi_exchange import (
    load_w5_exchange_profile,
    transition_w5_exchange,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_numerical_certificate import raw_state_bytes_from_field


class ExchangeCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = load_w2_geometry_profile()
        cls.profile = load_w5_exchange_profile(geometry=cls.geometry)
        cls.certificate = json.loads(
            (
                Path(__file__).resolve().parent
                / "_diag"
                / "cassi-qi-flow-w3n-final"
                / "1b36f54f4e669b818bba422726d051f1f928db43e64d812c6bd8e93e1159bc48"
                / "certificate"
                / "certificate-root.json"
            ).read_text()
        )

    def manufactured(self, *, amplitude: float = 0.25, conjugate: bool = False) -> QiFlowStateV3:
        modes = 32
        field = torch.zeros((4, 9 * modes, 1), dtype=torch.float64)
        y, x = torch.meshgrid(torch.arange(4, dtype=torch.float64), torch.arange(4, dtype=torch.float64), indexing="ij")
        theta_yang = 0.45 * x + 0.2 * y
        theta_yin = 1.1 - 0.25 * x + 0.15 * y
        if conjugate:
            theta_yang, theta_yin = -theta_yang, -theta_yin
        for scale in range(4):
            real_yang = (amplitude * torch.cos(theta_yang)).repeat(2, 1, 1).reshape(modes)
            imag_yang = (amplitude * torch.sin(theta_yang)).repeat(2, 1, 1).reshape(modes)
            real_yin = (0.8 * amplitude * torch.cos(theta_yin)).repeat(2, 1, 1).reshape(modes)
            imag_yin = (0.8 * amplitude * torch.sin(theta_yin)).repeat(2, 1, 1).reshape(modes)
            field[scale, 0:modes, 0] = real_yang
            field[scale, modes:2 * modes, 0] = imag_yang
            field[scale, 2 * modes:3 * modes, 0] = real_yin
            field[scale, 3 * modes:4 * modes, 0] = imag_yin
        return QiFlowStateV3(field.contiguous())

    def step(self, state, **kwargs):
        return transition_w5_exchange(
            state,
            geometry_profile=self.geometry,
            exchange_profile=self.profile,
            numerical_certificate=self.certificate,
            **kwargs,
        )

    def test_zero_conversion_and_flux_is_exact_raw_noop(self):
        state = self.manufactured()
        step = self.step(state, conversion_enabled=False, flux_enabled=False)
        self.assertTrue(step.committable)
        self.assertEqual(raw_state_bytes_from_field(state.field), raw_state_bytes_from_field(step.candidate.field))
        self.assertEqual(step.receipt["continuity"]["aggregate"]["gamma_raw_integral"], 0.0)
        self.assertEqual(step.receipt["continuity"]["aggregate"]["integrated_divergence"], 0.0)

    def test_uniform_state_has_exact_zero_flux_and_periodic_closure(self):
        state = self.manufactured()
        for component in (0, 1, 2, 3):
            block = state.field[:, component * 32:(component + 1) * 32, :]
            block[:] = block[:, :1, :]
        step = self.step(state, conversion_enabled=True, flux_enabled=True)
        self.assertTrue(step.committable, step.failure_reason)
        aggregate = step.receipt["continuity"]["aggregate"]
        self.assertEqual(aggregate["integrated_divergence"], 0.0)
        self.assertEqual(aggregate["flux_yang_delta"], 0.0)
        self.assertEqual(aggregate["flux_yin_delta"], 0.0)

    def test_manufactured_periodic_flux_has_divergence_and_continuity_closure(self):
        step = self.step(self.manufactured(), conversion_enabled=False, flux_enabled=True)
        self.assertTrue(step.committable, step.failure_reason)
        aggregate = step.receipt["continuity"]["aggregate"]
        self.assertGreater(sum(abs(item["flux_yang_delta"]) for item in step.receipt["per_scale_work_source_ledger"]), 0.0)
        self.assertLessEqual(abs(aggregate["integrated_divergence"]), 1.0e-12)
        self.assertLessEqual(abs(aggregate["total_density_closure"]), 1.0e-12)

    def test_phase_current_conjugation_reverses_exchange(self):
        positive = self.step(self.manufactured(), conversion_enabled=True, flux_enabled=False)
        negative = self.step(self.manufactured(conjugate=True), conversion_enabled=True, flux_enabled=False)
        self.assertTrue(positive.committable, positive.failure_reason)
        self.assertTrue(negative.committable, negative.failure_reason)
        first = positive.receipt["continuity"]["aggregate"]["gamma_raw_integral"]
        second = negative.receipt["continuity"]["aggregate"]["gamma_raw_integral"]
        self.assertAlmostEqual(first, -second, places=13)

    def test_amplitude_scaling_has_quadratic_gamma_measurement(self):
        base = self.step(self.manufactured(amplitude=0.2), conversion_enabled=True, flux_enabled=False)
        doubled = self.step(self.manufactured(amplitude=0.4), conversion_enabled=True, flux_enabled=False)
        self.assertTrue(base.committable, base.failure_reason)
        self.assertTrue(doubled.committable, doubled.failure_reason)
        ratio = (
            doubled.receipt["continuity"]["aggregate"]["gamma_raw_integral"]
            / base.receipt["continuity"]["aggregate"]["gamma_raw_integral"]
        )
        self.assertAlmostEqual(ratio, 4.0, places=12)

    def test_position_updates_preserve_phase_and_leave_other_lanes_exact(self):
        state = self.manufactured()
        step = self.step(state)
        self.assertTrue(step.committable, step.failure_reason)
        modes = 32
        original, candidate = state.field.clone(), step.candidate.field.clone()
        for lane in (0, 1, 2, 3):
            original[:, lane * modes:(lane + 1) * modes, :] = candidate[:, lane * modes:(lane + 1) * modes, :]
        self.assertTrue(torch.equal(original, candidate))

    def test_bad_profile_certificate_and_nonfinite_state_reject_before_candidate(self):
        bad_profile = replace(self.profile, profile_sha256="0" * 64)
        rejected_profile = transition_w5_exchange(
            self.manufactured(),
            geometry_profile=self.geometry,
            exchange_profile=bad_profile,
            numerical_certificate=self.certificate,
        )
        self.assertFalse(rejected_profile.committable)
        bad_certificate = dict(self.certificate)
        bad_certificate["self_sha256"] = "0" * 64
        rejected_certificate = transition_w5_exchange(
            self.manufactured(),
            geometry_profile=self.geometry,
            exchange_profile=self.profile,
            numerical_certificate=bad_certificate,
        )
        self.assertFalse(rejected_certificate.committable)
        state = self.manufactured()
        state.field[0, 0, 0] = float("nan")
        rejected_nonfinite = self.step(state)
        self.assertFalse(rejected_nonfinite.committable)
        self.assertIsNone(rejected_nonfinite.candidate)


if __name__ == "__main__":
    unittest.main()
