"""Focused W6T contract tests; the parent wave runs these tests."""
from __future__ import annotations

from dataclasses import replace
import unittest

import torch

from cassi_qi_scattering import (
    CANDIDATE_MODE_IDS,
    CONTROLLER_GRAMMAR_ID,
    PERIODIC_FFT2_IDENTITY,
    QiInterval,
    QiPortDescriptor,
    QiScaleGeometryProfile,
    QiScaleGeometryThresholds,
    ScatteringError,
    build_qi_scattering_receipt,
    build_scale_geometry_comparison,
    build_topology_codebook_evidence,
    declare_scale_interfaces,
    materialize_candidate_operator_data,
    pair_internal_scattering_receipts,
    replay_scattering_receipt,
    select_scale_geometry,
    validate_scattering_receipt,
    validate_scattering_receipt_set,
    validate_scale_geometry_comparison,
    validate_topology_codebook_evidence,
    topology_witness_hash,
    validate_zero_clock_remap_preservation,
)


class _Geometry:
    """Small deterministic periodic geometry double for operator materialization."""

    def sheet_shape(self, scale: int) -> tuple[int, int]:
        return (4, 8)

    def active_site_count(self, scale: int) -> int:
        return 32

    def cross_scale_matrix(self, source: int, target: int) -> torch.Tensor:
        return torch.eye(32, dtype=torch.complex128)

    def cross_scale_adjoint_matrix(self, source: int, target: int) -> torch.Tensor:
        return torch.eye(32, dtype=torch.complex128)

    def metric_matrix(self, scale: int) -> torch.Tensor:
        return torch.eye(32, dtype=torch.float64)


class _ScatteringTests(unittest.TestCase):
    def _candidate_rows(self) -> tuple[QiScaleGeometryProfile, dict[str, object]]:
        profile = QiScaleGeometryProfile(
            thresholds=QiScaleGeometryThresholds(r_min=1, kappa_max=10, chi_max=1, w_max=100, c_max=1000),
        )
        state = torch.zeros((4, 9 * 32, 2), dtype=torch.float64)
        temporal = materialize_candidate_operator_data(
            "temporal-full-rank", geometry=_Geometry(), profile=profile, state=state, work_interval=1,
        )
        pyramid = materialize_candidate_operator_data(
            "spatiotemporal-pyramid", geometry=_Geometry(), profile=profile, state=state, work_interval=1,
        )
        return profile, {"temporal-full-rank": temporal, "spatiotemporal-pyramid": pyramid}

    def _receipt(self, port: QiPortDescriptor, rows: dict[str, object], **kwargs: object):
        return build_qi_scattering_receipt(
            port=port, step=1, head_sha256="h", incoming_trajectory_sha256="traj", stage_id="stage",
            tick_interval=1, profile_sha256=port.profile_sha256, operator_sha256=port.operator_sha256, metric_sha256=port.metric_sha256,
            active_rank=4, nullspace_sha256="null", pre_state_sha256="pre", post_state_sha256="post",
            work_rows=rows, **kwargs,
        )

    def test_both_modes_materialize_fixed_state_bytes_rank_and_nullspace(self) -> None:
        profile, candidates = self._candidate_rows()
        temporal, pyramid = candidates["temporal-full-rank"], candidates["spatiotemporal-pyramid"]
        self.assertEqual(CANDIDATE_MODE_IDS, ("temporal-full-rank", "spatiotemporal-pyramid"))
        self.assertEqual(temporal.active_shapes, ((4, 8),) * 4)
        self.assertEqual(pyramid.active_shapes, ((4, 8), (4, 4), (2, 4), (2, 2)))
        self.assertEqual(temporal.packed_bytes, 9 * 8 * 2 * 4 * 32)
        self.assertEqual(pyramid.active_bytes, 9 * 8 * 2 * (32 + 16 + 8 + 4))
        self.assertEqual(pyramid.packed_bytes - pyramid.active_bytes, pyramid.tail_bytes)
        self.assertEqual(temporal.effective_ranks, (32, 32, 32))
        self.assertEqual(pyramid.effective_ranks, (16, 8, 4))
        self.assertEqual(pyramid.nullspace_dimensions, (16, 8, 4))
        self.assertEqual(pyramid.dark_mode_counts, pyramid.nullspace_dimensions)
        self.assertEqual(pyramid.collision_counts, pyramid.nullspace_dimensions)
        standalone = materialize_candidate_operator_data("temporal-full-rank", geometry=_Geometry(), profile=None, state=torch.zeros((4, 9 * 32, 1), dtype=torch.float64), work_interval=1)
        self.assertTrue(standalone.profile_sha256)
        with self.assertRaises(ScatteringError):
            materialize_candidate_operator_data("spatiotemporal-pyramid", geometry=_Geometry(), profile=profile, state=torch.ones((4, 9 * 32, 1), dtype=torch.float64), work_interval=1)
        with self.assertRaises(ScatteringError):
            materialize_candidate_operator_data("spatiotemporal-pyramid", geometry=_Geometry(), profile=profile, state=torch.zeros((4, 9 * 32, 1), dtype=torch.float64), work_interval=1, full_spectrum_claim=True)

    def test_selector_feasibility_tie_overlap_and_no_feasible_fail_closed(self) -> None:
        def row(mode: str, rank: object = 4, condition: object = 2, cross_talk: object = 0.1, work: object = 2, cost: object = 3):
            return {"mode_id": mode, "rank_interval": rank, "condition_interval": condition, "cross_talk_interval": cross_talk, "work_interval": work, "cost_interval": cost}

        thresholds = QiScaleGeometryThresholds(r_min=1, kappa_max=10, chi_max=1, w_max=10, c_max=10)
        selected = select_scale_geometry({"temporal-full-rank": row("temporal-full-rank", rank=8), "spatiotemporal-pyramid": row("spatiotemporal-pyramid", rank=4)}, thresholds=thresholds)
        self.assertEqual(selected.status, "SELECTED")
        self.assertEqual(selected.selected_mode, "temporal-full-rank")
        tie = select_scale_geometry({"temporal-full-rank": row("temporal-full-rank"), "spatiotemporal-pyramid": row("spatiotemporal-pyramid")}, thresholds=thresholds)
        self.assertEqual(tie.selected_mode, "spatiotemporal-pyramid")
        overlap = select_scale_geometry({"temporal-full-rank": row("temporal-full-rank", rank=QiInterval(3, 5)), "spatiotemporal-pyramid": row("spatiotemporal-pyramid", rank=QiInterval(4, 4))}, thresholds=thresholds)
        self.assertEqual(overlap.status, "FAIL")
        self.assertIn("overlap", overlap.failure_reason or "")
        unresolved = select_scale_geometry({"temporal-full-rank": row("temporal-full-rank", rank=QiInterval.unresolved(1, 10)), "spatiotemporal-pyramid": row("spatiotemporal-pyramid", rank=QiInterval.unresolved(1, 10))}, thresholds=thresholds)
        self.assertEqual(unresolved.status, "FAIL")
        no_feasible = select_scale_geometry({"temporal-full-rank": row("temporal-full-rank", rank=0), "spatiotemporal-pyramid": row("spatiotemporal-pyramid", rank=0)}, thresholds=thresholds)
        self.assertEqual(no_feasible.failure_reason, "empty-feasible-set")
        with self.assertRaises(ScatteringError):
            select_scale_geometry({"temporal-full-rank": row("temporal-full-rank"), "spatiotemporal-pyramid": row("spatiotemporal-pyramid")}, thresholds=thresholds, selector_id="first-candidate-passing-all-registered-thresholds-v1")

    def test_comparison_freezes_controls_and_selector_receipt(self) -> None:
        profile, candidates = self._candidate_rows()
        direct = select_scale_geometry(candidates, thresholds=profile.thresholds)
        self.assertEqual(direct.selected_mode, "temporal-full-rank")
        comparison = build_scale_geometry_comparison(profile, candidates)
        self.assertEqual(comparison.status, "SELECTED")
        self.assertEqual(comparison.selected_mode, "temporal-full-rank")
        self.assertEqual(comparison.profile.periodic_fft_identity, PERIODIC_FFT2_IDENTITY)
        self.assertEqual(comparison.profile.controller_grammar, CONTROLLER_GRAMMAR_ID)
        validate_scale_geometry_comparison(comparison)
        with self.assertRaises(TypeError):
            comparison.profile.work_budget["W_incident"] = QiInterval.exact(0)  # type: ignore[index]
        with self.assertRaises(ScatteringError):
            bad = replace(candidates["temporal-full-rank"], controller_grammar="changed")
            build_scale_geometry_comparison(profile, {**candidates, "temporal-full-rank": bad})

    def test_topology_resolution_and_zero_clock_remap_guards(self) -> None:
        evidence = build_topology_codebook_evidence(
            codebook_id="cb", resolution=(4, 4), codewords=((0,), (1,)), witness_hashes=(topology_witness_hash((0,), (4, 4)), topology_witness_hash((1,), (4, 4))),
            periodic_fft_identity=PERIODIC_FFT2_IDENTITY, metric_identity="metric", operator_identity="operator",
            amplitude_guard="amp", branch_guard="branch", edge_registry_identity="edges",
            zero_clock_remap_identity="remap-v1",
        )
        validate_topology_codebook_evidence(evidence, resolution=(4, 4), periodic_fft_identity=PERIODIC_FFT2_IDENTITY)
        validate_zero_clock_remap_preservation(evidence)
        with self.assertRaises(ScatteringError):
            validate_topology_codebook_evidence(evidence, resolution=(2, 2), periodic_fft_identity=PERIODIC_FFT2_IDENTITY)
        with self.assertRaises(ScatteringError):
            validate_zero_clock_remap_preservation(evidence, remap={(0,): (9,)})
        with self.assertRaises(ScatteringError):
            replace(evidence, resolution_scaled=False)

    def test_internal_pair_and_external_reflection_transmission_matched_work(self) -> None:
        descriptor = declare_scale_interfaces(scale_count=2, scale_geometry_mode="temporal-full-rank")[0]
        reverse = QiPortDescriptor(descriptor.port_id, descriptor.interface_id, "internal", 1, 0, -1, descriptor.scale_geometry_mode, descriptor.profile_sha256, descriptor.operator_sha256, descriptor.metric_sha256, descriptor.permeability_profile_sha256)
        source = self._receipt(descriptor, {"W_incident": {"row_id": "src-i", "value": 1}, "W_reflected": {"row_id": "src-r", "value": 0}, "W_transmitted": {"row_id": "shared-t", "value": 1}, "W_absorbed": {"row_id": "src-a", "value": 0}})
        target = self._receipt(reverse, {"W_incident": {"row_id": "dst-i", "value": 1}, "W_reflected": {"row_id": "dst-r", "value": 0}, "W_transmitted": {"row_id": "shared-t", "value": 1}, "W_absorbed": {"row_id": "dst-a", "value": 0}})
        pair_internal_scattering_receipts(source, target)
        external = QiPortDescriptor("port", "port", "external", None, None, 1, "temporal-full-rank")
        reflection = self._receipt(external, {"W_incident": 1, "W_reflected": 1, "W_transmitted": 0, "W_absorbed": 0})
        transmission = self._receipt(external, {"W_incident": 1, "W_reflected": 0, "W_transmitted": 1, "W_absorbed": 0})
        matched = self._receipt(external, {"W_incident": 1, "W_reflected": 0, "W_transmitted": 0, "W_absorbed": 1})
        for receipt in (reflection, transmission, matched):
            validate_scattering_receipt(receipt, port=external)
        reversed_source = source.with_orientation_reversed() if hasattr(source, "with_orientation_reversed") else None
        self.assertIsNotNone(reversed_source)
        self.assertEqual(reversed_source.orientation, -1)
        validate_scattering_receipt_set((source, target), declared_interfaces=(descriptor,))

    def test_missing_hidden_ports_mutated_rows_volatile_and_closure_rejected(self) -> None:
        port = QiPortDescriptor("external", "external", "external", None, None, 1, "temporal-full-rank")
        raw = {"W_incident": {"row_id": "i", "value": 1, "volatile_telemetry": 1}, "W_reflected": {"row_id": "r", "value": 0, "volatile_telemetry": 2}, "W_transmitted": {"row_id": "t", "value": 1, "volatile_telemetry": 3}, "W_absorbed": {"row_id": "a", "value": 0, "volatile_telemetry": 4}}
        receipt = self._receipt(port, raw)
        mutated = {**raw, "W_transmitted": {"row_id": "t", "value": 0}}
        with self.assertRaises(ScatteringError):
            replay_scattering_receipt(receipt, mutated)
        changed_telemetry = {channel: {**value, "volatile_telemetry": 99} for channel, value in raw.items()}
        replay_scattering_receipt(receipt, changed_telemetry)
        with self.assertRaises(ScatteringError):
            validate_scattering_receipt_set((receipt,), declared_interfaces=())
        hidden = QiPortDescriptor("hidden", "hidden", "external", None, None, 1, "temporal-full-rank")
        with self.assertRaises(ScatteringError):
            validate_scattering_receipt_set((receipt,), declared_interfaces=(), external_ports=(hidden,))
        with self.assertRaises(ScatteringError):
            self._receipt(port, {"W_incident": 1, "W_reflected": 0, "W_transmitted": 0, "W_absorbed": 0}, closure_residual=0, closure_bound=0)


if __name__ == "__main__":
    unittest.main()
