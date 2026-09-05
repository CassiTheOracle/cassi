"""Focused W5 law tests; no artifact runners, verifiers, or filesystem ancestry."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import unittest
from unittest.mock import patch

import torch

import cassi_qi_conversion as conversion
from cassi_qi_carrier import carrier_coordinates, load_w4_carrier_profile
from cassi_qi_field import QiFlowGeometryV2, QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_profile import load_development_profile
from cassi_qi_topology import load_w4r_topology_profile, make_topology_fixture
from cassi_qi_transport import load_w3_transport_profile


@dataclass
class _FakeStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: dict
    failure_reason: str | None = None
    intermediates: dict | None = None


def _fake_split(state, *, geometry_profile, transport_profile, carrier_profile, numerical_certificate, duration_s=None, potential_enabled=True, additional_force=None, center_map=None):
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
        return _FakeStep(state, center_state, True, receipt, None, intermediates)
    except Exception as exc:
        return _FakeStep(state, None, False, {"schema": "test-carrier-receipt", "status": "REJECTED"}, str(exc))


class W5ConversionCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = load_development_profile()
        cls.geometry = load_w2_geometry_profile(base_profile=base)
        cls.transport = load_w3_transport_profile(geometry_profile=cls.geometry)
        cls.carrier = load_w4_carrier_profile(geometry=cls.geometry, transport=cls.transport)
        cls.topology = load_w4r_topology_profile(geometry=cls.geometry, carrier_profile=cls.carrier)
        cls.profile = conversion.load_w5_conversion_profile(
            geometry_profile=cls.geometry,
            transport_profile=cls.transport,
            carrier_profile=cls.carrier,
            topology_profile=cls.topology,
        )
        cls.certificate = {}

    def _state(self, lanes: int = 2):
        return make_topology_fixture(geometry=self.geometry, kind="plane-wave", batch_lanes=lanes)

    def _run(self, state, **kwargs):
        values = {
            "geometry_profile": self.geometry,
            "transport_profile": self.transport,
            "carrier_profile": self.carrier,
            "topology_profile": self.topology,
            "conversion_profile": self.profile,
            "numerical_certificate": self.certificate,
            "duration_s": self.profile.h_min,
        }
        values.update(kwargs)
        with patch.object(conversion, "_transition_v4_carrier_split", _fake_split):
            return conversion.transition_w5_integrated(state, **values)

    def _clock_receipt(self, state):
        duration, rational = conversion._resolve_duration(self.profile, self.profile.h_min)
        process_rows = []
        _, conversion_rows, _ = conversion._frozen_q_map(
            state,
            geometry=self.geometry,
            profile=self.profile,
            carrier_profile=self.carrier,
            duration_s=duration,
            process_rows=process_rows,
        )
        conversion_row = {"lambda_rate": self.profile.lambda_rate, "rows": list(conversion_rows)}
        receipt = {
            "duration_s": duration,
            "duration_rational": dict(rational),
            "process_clock": conversion._process_clock_receipt(
                process_rows,
                conversion_rows,
                duration=duration,
                duration_rational=rational,
                lambda_rate=self.profile.lambda_rate,
                epsilon_guard=self.profile.epsilon_prog_min,
            ),
        }
        return receipt, conversion_row

    def _raw_hash(self, state):
        return hashlib.sha256(state.field.detach().contiguous().cpu().numpy().tobytes()).hexdigest()

    def test_profile_uses_dynamic_ancestry_and_full_registered_clock(self):
        self.assertEqual(self.profile.h_min, 0.001)
        self.assertEqual(self.profile.h_max, 0.01)
        self.assertEqual(self.profile.payload["clock"]["runtime_exact_rationals"], [{"numerator": 1, "denominator": 1000}, {"numerator": 1, "denominator": 100}])
        self.assertEqual(self.profile.payload["state_layout"]["component_count"], 9)
        self.assertTrue(self.profile.payload["no_extra_persistent_state"])


    def test_runtime_accepts_every_exact_rational_inside_registered_interval(self):
        duration, rational = conversion._resolve_duration(self.profile, 0.005)
        self.assertEqual(duration, 0.005)
        self.assertEqual(dict(rational), {"numerator": 1, "denominator": 200})
        malformed = replace(self.profile, runtime_durations=(self.profile.h_min, self.profile.h_min))
        with self.assertRaises(conversion.ConversionError):
            conversion._resolve_duration(malformed, duration)

    def test_zero_lambda_and_zero_ema_is_exact_whole_state_noop(self):
        state = self._state()
        result = self._run(state, conversion_enabled=False, epsilon_ema_enabled=False)
        self.assertTrue(result.committable)
        baseline = _fake_split(
            state,
            geometry_profile=self.geometry,
            transport_profile=self.transport,
            carrier_profile=self.carrier,
            numerical_certificate=self.certificate,
            center_map=None,
        ).candidate
        self.assertIsNotNone(baseline)
        self.assertEqual(self._raw_hash(result.candidate), self._raw_hash(baseline))
        identity = result.receipt["ema"]["joint_off_identity"]
        self.assertTrue(identity["equal"])
        self.assertEqual(identity["baseline_state_sha256"], identity["candidate_state_sha256"])
        self.assertEqual(result.receipt["conversion"]["q_evaluations"], 1)
        self.assertEqual(result.receipt["conversion"]["center_map_invocations"], 1)
        self.assertEqual(result.receipt["ema"]["updates"], 0)
        self.assertEqual(result.receipt["ema"]["tau"], 0.0)
        process = result.receipt["process_clock"]
        self.assertTrue(process["lambda_zero"])
        self.assertTrue(process["tau_F_defined"])
        self.assertTrue(process["chi_F_defined"])
        self.assertIsNotNone(process["delta_tau_F"])
        self.assertEqual(process["delta_chi_F"], {"min": 0.0, "max": 0.0, "mean": 0.0})
        self.assertTrue(process["observability"]["delta_tau_F"])
        self.assertTrue(process["observability"]["delta_chi_F"])
        self.assertFalse(process["observability"]["endpoint_tau_F"])
        for row in process["rows"]:
            q = row["q"]
            tau = row["delta_tau_F"]
            self.assertEqual(tau, row["tau_F_expected"])
            self.assertAlmostEqual(tau["min"], (1.0 - q["max"]) * self.profile.h_min)
            self.assertAlmostEqual(tau["max"], (1.0 - q["min"]) * self.profile.h_min)
            self.assertEqual(row["delta_chi_F"], {"min": 0.0, "max": 0.0, "mean": 0.0})
            self.assertTrue(row["tau_F_defined"])
            self.assertIsNone(row["tau_F_endpoint"])
            self.assertFalse(row["tau_F_endpoint_observable"])

    def test_lambda_zero_keeps_positions_and_velocities_but_updates_ema(self):
        state = self._state()
        result = self._run(state, conversion_enabled=False, epsilon_ema_enabled=True)
        self.assertTrue(result.committable)
        self.assertEqual(result.receipt["conversion"]["lambda_rate"], 0.0)
        self.assertGreater(result.receipt["ema"]["tau"], 0.0)
        self.assertTrue(any(row["post_max"] != row["pre_max"] for row in result.receipt["ema"]["rows"]))

    def test_enabled_conversion_receipts_account_for_process_age_and_exposure(self):
        receipt, conversion_row = self._clock_receipt(self._state())
        process = receipt["process_clock"]
        rows = process["rows"]
        conversion_rows = conversion_row["rows"]
        self.assertGreater(process["lambda_rate"], 0.0)
        self.assertTrue(process["coordinate_time_ground_truth"])
        self.assertEqual(process["coordinate_duration_s"], self.profile.h_min)
        self.assertEqual(process["evaluation_count"], len(conversion_rows))
        self.assertEqual(process["conversion_row_count"], len(conversion_rows))
        self.assertTrue(process["one_process_age_evaluation_per_conversion_row"])
        self.assertTrue(process["tau_F_defined"])
        self.assertTrue(process["observability"]["delta_tau_F"])
        self.assertEqual(len(rows), len(conversion_rows))
        for row, map_row in zip(rows, conversion_rows, strict=True):
            q = row["q"]
            tau = row["delta_tau_F"]
            chi = row["delta_chi_F"]
            self.assertEqual(tau, row["tau_F_expected"])
            self.assertEqual(chi, row["chi_F_expected"])
            self.assertAlmostEqual(tau["min"], (1.0 - q["max"]) * self.profile.h_min)
            self.assertAlmostEqual(tau["max"], (1.0 - q["min"]) * self.profile.h_min)
            self.assertAlmostEqual(tau["mean"], (1.0 - q["mean"]) * self.profile.h_min)
            for key in ("min", "max", "mean"):
                self.assertAlmostEqual(chi[key], tau[key] * process["lambda_rate"])
            self.assertAlmostEqual(q["min"], map_row["q_min"])
            self.assertAlmostEqual(q["max"], map_row["q_max"])
            self.assertTrue(math.isfinite(row["alpha_closure_abs"]))
        self.assertTrue(process["closure_finite"])
        self.assertTrue(math.isfinite(process["closure_abs"]))
        self.assertIsNone(conversion._validate_process_clock_receipt(receipt, conversion_row))

    def test_equal_conversion_age_has_equal_exposure_and_endpoint(self):
        rows = []
        for q_value, duration in ((0.2, 0.005), (0.6, 0.01)):
            q = torch.tensor([q_value], dtype=torch.float64)
            alpha = torch.exp(-(1.0 + self.profile.phi) * self.profile.lambda_rate * (1.0 - q) * duration)
            epsilon = torch.ones_like(q)
            rows.append(conversion._process_clock_row(
                scale=0,
                q=q,
                alpha=alpha,
                epsilon=epsilon,
                next_y=torch.sqrt(alpha),
                next_i=torch.zeros_like(q),
                duration=duration,
                lambda_rate=self.profile.lambda_rate,
                phi=self.profile.phi,
                epsilon_guard=self.profile.epsilon_prog_min,
            ))
        for row in rows:
            self.assertTrue(row["tau_F_endpoint_observable"])
            self.assertAlmostEqual(row["delta_tau_F"]["mean"], 0.004)
            self.assertAlmostEqual(row["tau_F_endpoint"]["mean"], 0.004)
            self.assertAlmostEqual(row["delta_chi_F"]["mean"], self.profile.lambda_rate * 0.004)
            self.assertAlmostEqual(row["chi_F_endpoint"]["mean"], self.profile.lambda_rate * 0.004)
        for key in ("delta_tau_F", "delta_chi_F", "alpha_expected", "alpha_endpoint"):
            self.assertAlmostEqual(rows[0][key]["mean"], rows[1][key]["mean"])

    def test_process_clock_validator_rejects_tampered_row_exposure(self):
        receipt, conversion_row = self._clock_receipt(self._state())
        tampered = dict(receipt)
        process = dict(tampered["process_clock"])
        rows = [dict(row) for row in process["rows"]]
        chi = dict(rows[0]["delta_chi_F"])
        chi["mean"] += 1.0e-4
        rows[0]["delta_chi_F"] = chi
        process["rows"] = rows
        tampered["process_clock"] = process
        with self.assertRaises(conversion.ConversionError):
            conversion._validate_process_clock_receipt(tampered, conversion_row)

    def test_factored_map_preserves_density_and_velocity_for_all_scales_and_batches(self):
        state = self._state(lanes=3)
        mapped, rows, branches = conversion._frozen_q_map(
            state,
            geometry=self.geometry,
            profile=self.profile,
            carrier_profile=self.carrier,
            duration_s=self.profile.h_min,
        )
        before = carrier_coordinates(state, geometry=self.geometry, profile=self.carrier)
        after = carrier_coordinates(mapped, geometry=self.geometry, profile=self.carrier)
        self.assertEqual(len(rows), state.field.shape[0])
        for d0, d1, c0, c1, vd0, vd1, vc0, vc1 in zip(before.d, after.d, before.c, after.c, before.vd, after.vd, before.vc, after.vc, strict=True):
            self.assertTrue(torch.isfinite(d1).all())
            self.assertTrue(torch.isfinite(c1).all())
            self.assertTrue(torch.equal(vd0, vd1))
            self.assertTrue(torch.equal(vc0, vc1))
            self.assertTrue(torch.isfinite(d0).all())
            self.assertTrue(torch.isfinite(c0).all())
        self.assertGreater(branches["yang-own-phase"], 0)

    def _sector_state(self, yang_amplitude: float, yin_amplitude: float, lanes: int = 2):
        state = QiFlowStateV3.create(self.geometry.base_profile, batch_lanes=lanes)
        surface = QiFlowGeometryV2(state, self.geometry)
        field = state.field.clone()
        modes = int(self.geometry.base_profile.state_layout["mode_count"])
        for scale, shape in enumerate(self.geometry.active_shapes):
            yang = torch.full((*shape, lanes), yang_amplitude, dtype=torch.float64)
            yin = torch.full((*shape, lanes), yin_amplitude, dtype=torch.float64)
            for component, value in enumerate((yang, torch.zeros_like(yang), yin, torch.zeros_like(yin))):
                field[scale, component * modes : (component + 1) * modes, :] = surface.grid_modes(scale, value)
        return QiFlowStateV3(field.contiguous())

    def test_signed_transfer_progress_for_yang_and_yin_heavy_sectors(self):
        yang_heavy = self._sector_state(0.30, 0.10)
        yin_heavy = self._sector_state(0.10, 0.30)
        _, positive_rows, _ = conversion._frozen_q_map(
            yang_heavy,
            geometry=self.geometry,
            profile=self.profile,
            carrier_profile=self.carrier,
            duration_s=self.profile.h_min,
        )
        _, negative_rows, _ = conversion._frozen_q_map(
            yin_heavy,
            geometry=self.geometry,
            profile=self.profile,
            carrier_profile=self.carrier,
            duration_s=self.profile.h_min,
        )
        self.assertTrue(all(row["transfer_min"] > 0.0 and row["signed_progress_min"] >= 0.0 for row in positive_rows))
        self.assertTrue(all(row["transfer_max"] < 0.0 and row["signed_progress_min"] >= 0.0 for row in negative_rows))

    def test_work_classification_accepts_only_resolved_dissipation(self):
        dissipative = conversion._classify_work(-1.0e-3, profile=self.profile)
        self.assertEqual(dissipative["classification"], "resolved-dissipation")
        self.assertEqual(dissipative["Q_conversion"], 1.0e-3)
        self.assertTrue(dissipative["sink"])
        numerical_zero = conversion._classify_work(0.0, profile=self.profile)

        self.assertEqual(numerical_zero["classification"], "numerical-zero")
        self.assertEqual(numerical_zero["Q_conversion"], 0.0)
        with self.assertRaises(conversion.ConversionError):
            conversion._classify_work(1.0e-3, profile=self.profile)
        with self.assertRaises(conversion.ConversionError):
            conversion._classify_work(-1.1e-9, profile=self.profile)
    def test_rejected_work_returns_complete_witness_without_candidate(self):
        state = self._state()
        before = self._raw_hash(state)
        with patch.object(conversion, "_classify_work", side_effect=conversion.ConversionError("forced work rejection")):
            result = self._run(state)
        self.assertFalse(result.committable)
        self.assertIsNone(result.candidate)
        self.assertIs(result.predecessor, state)
        self.assertEqual(before, self._raw_hash(state))
        self.assertIsNone(result.receipt["candidate_state_sha256"])
        self.assertTrue(result.receipt["energy"]["complete_component_recomputation"])
        self.assertEqual(result.receipt["energy"]["pre"], result.receipt["energy"]["hamiltonian_before"])
        self.assertEqual(result.receipt["energy"]["post"], result.receipt["energy"]["hamiltonian_after"])
        self.assertEqual(result.receipt["work_witness"]["rejection_reason"], "forced work rejection")
        witness = result.receipt["attempted_center_map_witness"]
        self.assertEqual(witness["input_state_sha256"], conversion._state_hash(state))
        self.assertEqual(witness["raw_domain"], conversion.W5_RAW_DOMAIN)
        self.assertEqual(witness["shape"], list(state.field.shape))
        self.assertEqual(witness["dtype"], "<f8")
        self.assertIsInstance(witness["output_state_sha256"], str)
        self.assertIsNone(witness["candidate_state_sha256"])
        self.assertEqual(dict(result.intermediates), {})


    def test_empty_sector_inherits_donor_phase_and_both_empty_stays_zero(self):
        state = QiFlowStateV3.create(self.geometry.base_profile, batch_lanes=1)
        surface = QiFlowGeometryV2(state, self.geometry)
        field = state.field.clone()
        modes = int(self.geometry.base_profile.state_layout["mode_count"])
        for scale in range(4):
            shape = self.geometry.active_shapes[scale]
            yang = torch.zeros((*shape, 1), dtype=torch.float64)
            yin = torch.zeros((*shape, 1), dtype=torch.complex128)
            yang[0, 0, 0] = 0.1
            yin[0, 1, 0] = 0.1j
            for component, value in enumerate((yang, torch.zeros_like(yang), yin.real, yin.imag)):
                field[scale, component * modes : (component + 1) * modes, :] = surface.grid_modes(scale, value.contiguous())
        prepared = QiFlowStateV3(field.contiguous())
        mapped, _, branches = conversion._frozen_q_map(prepared, geometry=self.geometry, profile=self.profile, carrier_profile=self.carrier, duration_s=self.profile.h_min)
        coords = carrier_coordinates(mapped, geometry=self.geometry, profile=self.carrier)
        self.assertGreater(abs(complex(coords.ey[0][0, 1, 0].item())), 0.0)
        self.assertGreater(abs(complex(coords.ei[0][0, 0, 0].item())), 0.0)
        self.assertEqual(branches["double-empty"], sum(math.prod(shape) - 2 for shape in self.geometry.active_shapes))

    def test_topology_force_is_combined_at_both_kicks_and_no_duplicate_time_advance(self):
        state = self._state()
        result = self._run(state, conversion_enabled=False, epsilon_ema_enabled=False)
        self.assertTrue(result.committable)
        self.assertEqual(result.receipt["topology"]["force_evaluations"], 2)
        self.assertTrue(result.receipt["topology"]["force_in_both_conservative_half_kicks"])
        self.assertEqual(result.receipt["stage_order"].count("w5_frozen_q_position_conversion"), 1)
        self.assertEqual(result.receipt["stage_order"].count("w5_single_post_step_epsilon2_ema"), 1)

    def test_work_ledger_is_center_delta_and_closes_once(self):
        state = self._state()
        result = self._run(state, conversion_enabled=False, epsilon_ema_enabled=False)
        self.assertTrue(result.committable)
        energy = result.receipt["energy"]
        self.assertEqual(energy["W_conversion"], 0.0)
        self.assertEqual(energy["Q_conversion"], 0.0)
        self.assertEqual(energy["work_classification"], "numerical-zero")
        self.assertFalse(energy["duplicate_composition_or_topology_accounting"])
        self.assertLessEqual(energy["conversion_work_closure_abs"], self.profile.work_tolerance)

    def test_invalid_duration_and_invalid_ema_reject_without_mutation(self):
        state = self._state()
        before = self._raw_hash(state)
        rejected = self._run(state, duration_s=self.profile.h_min / 2.0)
        self.assertFalse(rejected.committable)
        self.assertIsNone(rejected.candidate)
        self.assertEqual(before, self._raw_hash(rejected.predecessor))
        bad = state.field.clone()
        surface = QiFlowGeometryV2(state, self.geometry)
        modes = int(self.geometry.base_profile.state_layout["mode_count"])
        bad[0, 8 * modes : 9 * modes, :] = surface.grid_modes(0, torch.full((*self.geometry.active_shapes[0], 2), self.profile.epsilon2_ema_max + 1.0, dtype=torch.float64))
        malformed = QiFlowStateV3(bad.contiguous())
        rejected_bad = self._run(malformed)
        self.assertFalse(rejected_bad.committable)
        self.assertIsNone(rejected_bad.candidate)
        self.assertEqual(self._raw_hash(malformed), self._raw_hash(rejected_bad.predecessor))

    def test_force_only_extra_law_is_rejected(self):
        class ForceOnly:
            law_id = "unpaired"
            additional_force = staticmethod(lambda state, geometry, carrier, coords: ((torch.zeros_like(v) for v in coords.d), (torch.zeros_like(v) for v in coords.c)))
        result = self._run(self._state(), extra_conservative_law=ForceOnly())
        self.assertFalse(result.committable)
        self.assertIn("extra_conservative_law", result.failure_reason)


if __name__ == "__main__":
    unittest.main()
