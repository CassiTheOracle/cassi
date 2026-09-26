"""Focused W6A intrinsic-capacity contract tests."""
from __future__ import annotations

import unittest
from functools import lru_cache
from types import SimpleNamespace

import torch

from cassi_qi_backend import QiCapacityProfile, QiDriveBundle, QiFlowStep
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_profile import QiFlowProfile
from cassi_qi_topology import load_w4r_topology_profile
from cassi_qi_capacity import (
    CapacityLadderError,
    IntrinsicCapacityError,
    build_capacity_ladder,
    build_intrinsic_capacity_profile,
    enumerate_intrinsic_capacity,
    validate_capacity_ladder,
    validate_intrinsic_capacity_receipt,
)
from cassi_qi_profile import finite_bits
from cassi_qi_scattering import CONTROLLER_GRAMMAR_ID, PERIODIC_FFT2_IDENTITY, QiInterval, QiPortDescriptor, QiScaleGeometryCandidate, QiTopologyCodebookEvidence, topology_witness_hash


_SHA = "a" * 64


def _geometry() -> QiScaleGeometryCandidate:
    shapes = ((1, 1),) * 4
    maps = (((1.0,),),) * 3
    return QiScaleGeometryCandidate(
        mode_id="temporal-full-rank",
        profile_sha256=_SHA,
        operator_sha256=_SHA,
        periodic_fft_identity=PERIODIC_FFT2_IDENTITY,
        active_shapes=shapes,
        active_site_counts=(1, 1, 1, 1),
        packed_mode_count=1,
        batch_lanes=1,
        bytes_per_value=8,
        active_bytes=8 * 9 * 4,
        packed_bytes=8 * 9 * 4,
        tail_bytes=0,
        restriction_maps=maps,
        adjoint_maps=maps,
        singular_spectra=((1.0,),) * 3,
        effective_ranks=(1, 1, 1),
        nullspace_dimensions=(0, 0, 0),
        nullspace_bases=((),) * 3,
        retained_subspaces=(((1.0 + 0.0j,),),) * 3,
        dark_mode_counts=(0, 0, 0),
        collision_counts=(0, 0, 0),
        rank_interval=QiInterval.exact(1.0),
        condition_interval=QiInterval.exact(1.0),
        cross_talk_interval=QiInterval.exact(0.0),
        work_interval=QiInterval.exact(0.0),
        cost_interval=QiInterval.exact(1.0),
    )


@lru_cache(maxsize=1)
def _canonical_dependencies() -> tuple[QiFlowProfile, QiCapacityProfile, object, QiFlowStateV3]:
    profile = QiFlowProfile.from_defaults()
    geometry = load_w2_geometry_profile(base_profile=profile)
    topology = load_w4r_topology_profile(geometry=geometry)
    backend = QiCapacityProfile.from_profile(profile, working_memory_budget=1 << 20)
    state = QiFlowStateV3.create(profile, batch_lanes=1)
    return profile, backend, topology, state


class _FixtureBackend:
    def __init__(self, *, profile: QiFlowProfile, capacity: QiCapacityProfile, fail: bool = False) -> None:
        self.identity = SimpleNamespace(profile_sha256=profile.profile_sha256)
        self.capacity = capacity
        self.fail = fail

    def execute_advance(self, state: QiFlowStateV3, drive: QiDriveBundle) -> QiFlowStep:
        if self.fail:
            return QiFlowStep(
                predecessor=state,
                candidate=None,
                committable=False,
                transaction_id=drive.transaction_id,
                operator_id="fixture",
                receipt={"transaction_id": drive.transaction_id, "failed": True},
                failure_reason="fixture failure",
            )
        field = state.field.clone()
        field[0, 0, 0] += float(drive.delta or 0.0)
        candidate = QiFlowStateV3(field)
        return QiFlowStep(
            predecessor=state,
            candidate=candidate,
            committable=True,
            transaction_id=drive.transaction_id,
            operator_id="fixture",
            receipt={"transaction_id": drive.transaction_id, "delta": float(drive.delta or 0.0)},
        )

def _codebook() -> QiTopologyCodebookEvidence:
    resolution = (1, 1)
    codewords = ((0,), (1,))
    return QiTopologyCodebookEvidence(
        codebook_id="fixture-codebook",
        resolution=resolution,
        codewords=codewords,
        witness_hashes=tuple(topology_witness_hash(word, resolution) for word in codewords),
        periodic_fft_identity=PERIODIC_FFT2_IDENTITY,
        metric_identity="metric-fixture",
        operator_identity="operator-fixture",
        amplitude_guard="guard-fixture",
        branch_guard="branch-fixture",
        edge_registry_identity="edge-fixture",
        realizable=True,
        resolution_scaled=True,
        zero_clock_remap_preserved=True,
        zero_clock_remap_identity="identity-remap.v1",
    )


def _ports() -> tuple[QiPortDescriptor, ...]:
    return tuple(
        QiPortDescriptor(
            port_id=f"port-{scale}",
            interface_id=f"interface-{scale}",
            kind="external",
            source_scale=None,
            target_scale=None,
            orientation=1,
            scale_geometry_mode="temporal-full-rank",
        )
        for scale in range(4)
    )


def _layout(batch_limit: int = 2) -> dict[str, object]:
    return {
        "layout_id": "cassi.qi-flow-state-layout.v3",
        "scale_count": 4,
        "component_count": 9,
        "mode_count": 1,
        "batch_limit": batch_limit,
        "active_shapes": [[1, 1]] * 4,
        "active_site_counts": [1] * 4,
        "shape": [4, 9, batch_limit],
    }


def _profile(*, operators: dict[str, object] | None = None, layout: dict[str, object] | None = None, phases: object = (0.0, 3.141592653589793)):
    if operators is None:
        operators = {f"port-{scale}": {"scale": scale, "reachability": ((1.0, 0.0), (0.0, 1.0)), "observability": ((1.0, 0.0), (0.0, 1.0))} for scale in range(4)}
    operators = {
        f"port-{scale}": dict(operators[f"port-{scale}"], scale=scale)
        for scale in range(4)
    }
    return build_intrinsic_capacity_profile(
        geometry=_geometry(),
        topology_codebook=_codebook(),
        ports=_ports(),
        state_layout=layout or _layout(),
        phase_codewords=phases,
        amplitude_codewords=(1.0, 2.0),
        scattering_operators=operators,
    )


class IntrinsicCapacityTests(unittest.TestCase):
    def test_complete_cartesian_enumeration_and_receipt_identity(self) -> None:
        profile = _profile()
        receipt = enumerate_intrinsic_capacity(profile)
        self.assertEqual(len(receipt.candidates), 4 * 2 * 2 * 2 * 2)
        self.assertEqual(len(receipt.admissible_set), len(receipt.candidates))
        self.assertEqual(receipt.capacity_levels["geometric"], 64)
        validate_intrinsic_capacity_receipt(receipt, profile=profile)
        self.assertEqual(receipt.self_sha256, enumerate_intrinsic_capacity(profile).self_sha256)

    def test_rank_deficiency_excludes_nullspace_and_collisions(self) -> None:
        rank_one = {"reachability": ((1.0, 0.0), (0.0, 0.0)), "observability": ((1.0, 0.0), (0.0, 0.0))}
        profile = _profile(operators={f"port-{scale}": rank_one for scale in range(4)})
        receipt = profile.enumerate()
        self.assertGreater(receipt.nullspace_counts["operator_reachable"], 0)
        self.assertGreater(receipt.collision_counts["pairs"], 0)
        self.assertLess(len(receipt.admissible_set), len(receipt.candidates))

    def test_reachable_observable_intersection_is_fixed_operator_rank(self) -> None:
        operators = {
            f"port-{scale}": {
                "reachability": ((1.0, 0.0), (0.0, 0.0)),
                "observability": ((0.0, 0.0), (0.0, 1.0)),
            }
            for scale in range(4)
        }
        profile = _profile(operators=operators)
        self.assertEqual(profile.proof_search_registry[0]["intersection_lower"], 0)
        self.assertEqual(profile.enumerate().capacity_levels["admissible"], 0)

    def test_identity_mismatch_and_semantic_label_rejection(self) -> None:
        bad_layout = _layout()
        bad_layout["active_shapes"] = [[1, 2]] * 4
        with self.assertRaises(IntrinsicCapacityError):
            _profile(layout=bad_layout)
        with self.assertRaises(IntrinsicCapacityError):
            _profile(phases={"label": (0.0,)})
def _ladder_work_partition() -> dict[str, object]:
    exact = {"lower": 1.0, "upper": 1.0, "unit": "joule"}
    zero = {"lower": 0.0, "upper": 0.0, "unit": "joule"}
    return {
        "incident": exact,
        "admitted": exact,
        "absorbed": zero,
        "reflected": zero,
        "damping_dissipation": zero,
        "port_reaction": zero,
        "conversion": zero,
        "residual": zero,
        "closure_residual": zero,
    }


def _ladder_topology_witness(index: int) -> dict[str, object]:
    h = lambda value: f"{value:064x}"
    one = finite_bits(1.0)
    zero = finite_bits(0.0)
    interval = {"lower": zero, "upper": one, "unit": "tick"}
    return {
        "witness_id": f"witness-{index}",
        "endpoint_state_sha256": h(10 + index),
        "grid_shape": [1, 1],
        "slow_scale": one,
        "edge_registry_sha256": h(20 + index),
        "edge_phase_raw_intervals": [
            {
                "edge_id": f"edge-{index}",
                "raw_phase_interval": interval,
                "uncertainty_half_width": zero,
                "branch_margin_lower_bound": one,
            }
        ],
        "endpoint_amplitude_witness": [
            {
                "site_id": f"site-{index}",
                "psi_modulus_interval": interval,
                "uncertainty_radius": zero,
                "lower_bound": one,
                "threshold": zero,
                "pass": True,
            }
        ],
        "endpoint_branch_witness": [
            {
                "edge_id": f"edge-{index}",
                "delta_interval": interval,
                "uncertainty_half_width": zero,
                "branch_margin_lower_bound": one,
                "pass": True,
            }
        ],
        "cycle_winding_witness": [
            {"axis": "x", "index": 0, "raw_interval": interval, "rounded_integer": 0, "integer_margin_lower_bound": one, "pass": True},
            {"axis": "y", "index": 0, "raw_interval": interval, "rounded_integer": 0, "integer_margin_lower_bound": one, "pass": True},
        ],
        "plaquette_witness": [
            {"origin": f"origin-{index}", "raw_interval": interval, "rounded_integer": 0, "integer_margin_lower_bound": one, "pass": True}
        ],
        "sector_vector": {"cycle_x": [0], "cycle_y": [0], "plaquette": [0]},
        "torus_algebra_witness": {
            "x_cycle_residual_intervals": [interval],
            "y_cycle_residual_intervals": [interval],
            "total_plaquette_interval": interval,
            "integer_closure": True,
            "max_residual_upper_bound": one,
            "pass": True,
        },
        "codebook_sha256": _canonical_dependencies()[2].topology_codebook_sha256,
        "sector_transport_sha256": h(30 + index),
        "minimum_amplitude_lower_bound": one,
        "minimum_branch_margin_lower_bound": one,
        "raw_witness_sha256": h(40 + index),
        "pass": True,
    }


def _ladder_kwargs() -> dict[str, object]:
    profile, backend, topology, state = _canonical_dependencies()
    basis = torch.eye(2, state.field.numel(), dtype=torch.float64)
    threshold = {"uncertainty": 0.0, "null_threshold": 0.0, "unit": "normalized"}
    return {
        "profile": profile,
        "backend_capacity": backend,
        "topology_profile": topology,
        "profile_sha256": profile.profile_sha256,
        "state_contract_sha256": profile.state_contract_sha256,
        "backend_capacity_sha256": backend.capacity_sha256,
        "topology_codebook_sha256": topology.topology_codebook_sha256,
        "topology_witnesses": (_ladder_topology_witness(1), _ladder_topology_witness(2)),
        "controller_grammar": "ordinary-v1",
        "physical_horizon": {"num": 1, "den": 1, "unit": "tick"},
        "work_budget": {"lower": 1.0, "upper": 2.0, "unit": "joule"},
        "geometric_capacity": 2,
        "reset_control": {"control": "reset", "drives": [0]},
        "saturation_control": {"control": "saturation", "drives": [1]},
        "overwrite_control": {"control": "overwrite", "drives": [2]},
        "washout_recovery_schedule": {"control": "washout-recovery", "drives": [0, 0]},
        "barrier_interval": {"lower": 1.0, "upper": 1.0, "unit": "tick"},
        "closure_residual": {"lower": 0.0, "upper": 0.0, "unit": "joule"},
        "analytic_source_basis": basis,
        "analytic_readout_basis": basis,
        "uncertainty_null_thresholds": threshold,
    }


class CapacityLadderTests(unittest.TestCase):
    def test_canonical_advance_ladder_is_nested_and_reproducible(self) -> None:
        profile, backend_capacity, _, initial_state = _canonical_dependencies()

        advance = _FixtureBackend(profile=profile, capacity=backend_capacity)

        work = _ladder_work_partition()
        trajectories = (
            {
                "trajectory_id": "ordinary-1",
                "drives": (0.1,),
                "source_work": {"lower": 1.0, "upper": 1.0, "unit": "joule"},
                "work_partition": work,
                "zero_clock_transport_sha256": "a" * 64,
                "observable": True,
                "usable": True,
            },
            {
                "trajectory_id": "ordinary-2",
                "drives": (0.2,),
                "source_work": {"lower": 1.0, "upper": 1.0, "unit": "joule"},
                "work_partition": work,
                "zero_clock_transport_sha256": "b" * 64,
                "observable": True,
                "usable": False,
            },
            {"trajectory_id": "reset", "kind": "reset", "acquisition": False, "drives": (0,)},
        )
        first = build_capacity_ladder(advance=advance, initial_state=initial_state, trajectories=trajectories, **_ladder_kwargs())
        second = build_capacity_ladder(advance=advance, initial_state=initial_state, trajectories=trajectories, **_ladder_kwargs())
        self.assertEqual(first.capacity_levels, {"geometric": 2, "reachable": 2, "observable": 2, "usable": 1, "retained": 0, "reusable": 0})
        self.assertEqual(first.capacity_ladder_sha256, second.capacity_ladder_sha256)
        self.assertEqual(first.trajectory_ids, ("ordinary-1", "ordinary-2", "reset"))
        self.assertFalse(any(item["trajectory_id"] == "reset" for item in first.reachability_witnesses))
        self.assertTrue(first.impulse_responses["coordinate"]["nullspace"]["dimension"] >= 0)
        self.assertFalse(first.delay_growth_retention_discrimination["retained_claim"])
        validate_capacity_ladder(first)
        expected_fields = {
            "schema", "receipt_id", "profile_sha256", "state_contract_sha256", "backend_capacity_sha256",
            "initial_state_sha256", "controller_grammar_sha256", "physical_horizon", "trajectory_set_sha256",
            "trajectory_ids", "work_budget", "capacity_levels", "capacity_intervals", "reachability_witnesses",
            "reset_control_sha256", "saturation_control_sha256", "overwrite_control_sha256",
            "washout_recovery_schedule_sha256", "consumed_semantic_subhashes", "topology_codebook_sha256",
            "topology_witnesses", "ladder_order", "acquisition_eligibility", "barrier_interval",
            "closure_residual", "reset_counts_as_acquisition",
        }
        self.assertEqual(set(first.payload()), expected_fields)
        self.assertEqual(set(first.to_dict()), expected_fields | {"self_sha256"})
        self.assertIn("impulse_responses", first.diagnostics_payload())

    def test_failed_canonical_step_and_behavioral_claim_fail_closed(self) -> None:
        profile, backend_capacity, _, initial_state = _canonical_dependencies()

        failed = _FixtureBackend(profile=profile, capacity=backend_capacity, fail=True)
        spec = {
            "trajectory_id": "failed",
            "drives": (1,),
            "source_work": {"lower": 1.0, "upper": 1.0, "unit": "joule"},
            "work_partition": _ladder_work_partition(),
            "zero_clock_transport_sha256": "a" * 64,
            "observable": True,
            "usable": True,
        }
        with self.assertRaises((CapacityLadderError, IntrinsicCapacityError)):
            build_capacity_ladder(advance=failed, initial_state=initial_state, trajectories=(spec,), **_ladder_kwargs())
        spec["retained"] = True

        advance = _FixtureBackend(profile=profile, capacity=backend_capacity)
        with self.assertRaises((CapacityLadderError, IntrinsicCapacityError)):
            build_capacity_ladder(advance=advance, initial_state=initial_state, trajectories=(spec,), **_ladder_kwargs())

    def test_endpoint_identity_mismatch_is_rejected(self) -> None:
        profile, backend_capacity, _, initial_state = _canonical_dependencies()

        advance = _FixtureBackend(profile=profile, capacity=backend_capacity)

        endpoint = initial_state.field.clone()
        endpoint[0, 0, 0] = 2.0
        spec = {
            "trajectory_id": "ordinary",
            "drives": (1,),
            "endpoint_state": QiFlowStateV3(endpoint),
            "source_work": {"lower": 1.0, "upper": 1.0, "unit": "joule"},
            "work_partition": _ladder_work_partition(),
            "zero_clock_transport_sha256": "a" * 64,
            "observable": True,
            "usable": True,
        }
        with self.assertRaises(IntrinsicCapacityError):
            build_capacity_ladder(
                advance=advance,
                initial_state=initial_state,
                trajectories=(spec,),
                **dict(_ladder_kwargs(), geometric_capacity=1, work_budget={"lower": 1.0, "upper": 1.0, "unit": "joule"}),
            )

    def test_live_path_rejects_noncanonical_state_unconserved_ledger_and_control_mismatch(self) -> None:
        profile, backend_capacity, _, initial_state = _canonical_dependencies()
        advance = _FixtureBackend(profile=profile, capacity=backend_capacity)

        spec = {
            "trajectory_id": "ordinary",
            "drives": (1,),
            "source_work": {"lower": 1.0, "upper": 1.0, "unit": "joule"},
            "work_partition": _ladder_work_partition(),
            "zero_clock_transport_sha256": "a" * 64,
            "observable": True,
            "usable": True,
        }
        with self.assertRaises((CapacityLadderError, IntrinsicCapacityError)):
            build_capacity_ladder(advance=advance, initial_state={"value": 0}, trajectories=(spec,), **_ladder_kwargs())

        bad_work = dict(_ladder_work_partition())
        bad_work["admitted"] = {"lower": 0.0, "upper": 0.0, "unit": "joule"}
        spec["work_partition"] = bad_work
        _, _, _, initial_state = _canonical_dependencies()
        with self.assertRaises((CapacityLadderError, IntrinsicCapacityError)):
            build_capacity_ladder(advance=advance, initial_state=initial_state, trajectories=(spec,), **_ladder_kwargs())

        spec["work_partition"] = _ladder_work_partition()
        with self.assertRaises((CapacityLadderError, IntrinsicCapacityError)):
            build_capacity_ladder(
                advance=advance,
                initial_state=initial_state,
                trajectories=(spec,),
                **dict(_ladder_kwargs(), reset_control_sha256="f" * 64),
            )



if __name__ == "__main__":
    unittest.main()
