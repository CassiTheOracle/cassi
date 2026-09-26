from __future__ import annotations

import json
import math

import numpy as np
import pytest

from cassi_resonant_field import (
    ResonantExchangeStage,
    ResonantHierarchy,
    ResonantHierarchySpec,
    ResonantNumericalError,
    ResonantRegionRecord,
    ResonantStageMismatchError,
    alignment_energy,
    alignment_gradients,
    alignment_step,
    apply_reciprocal_exchange,
    basis_change,
    flow_line,
    geometry_from_flow,
    initial_workspace,
    metric_edge_weights,
    metric_weighted_transform,
    moving_frame_rhs,
    passive_rotation_check,
    reciprocal_exchange,
    regional_kernel,
    regional_state,
    reverse_axis_representative,
    uniform_axial_divergence,
    unweighted_transform_error,
    workspace_from_regional_state,
)


def test_metric_restriction_is_reversible_and_unweighted_control_fails() -> None:
    values = np.array([0.7, -1.2, 2.5, 0.1])
    metric = np.array([1.0, 3.0, 2.0, 5.0])
    result = metric_weighted_transform(values, metric)
    assert result["roundtrip_error"] <= result["roundoff_bound"]
    assert result["roundtrip_error"] < 1e-14
    assert unweighted_transform_error(values, metric) > 1e-12


def test_reciprocal_exchange_cancels_and_nonreciprocal_control_does_not() -> None:
    gp = np.array([1.0, -2.0, 0.5])
    gc = np.array([-0.3, 1.5])
    transfer = np.array([[0.4, -0.2], [1.1, 0.7], [-0.9, 0.2]])
    result = reciprocal_exchange(gp, gc, transfer)
    assert abs(result["power_imbalance"]) <= 32 * np.finfo(float).eps
    bad_child = transfer.T @ gp
    nonreciprocal_imbalance = float(gp @ (transfer @ gc) + gc @ bad_child)
    assert abs(nonreciprocal_imbalance) > 1e-6


def test_stage_guard_and_interface_work_survive_regional_roundtrip() -> None:
    parent = ResonantRegionRecord("parent", content_version=2)
    child = ResonantRegionRecord("child", content_version=3)
    stage = ResonantExchangeStage.bind(parent, child, version="shared")
    old = ResonantExchangeStage.bind(parent, child, version="old")
    ws = initial_workspace()
    ws, receipt = apply_reciprocal_exchange(ws, [1.0], [2.0], [[0.5]], stage=stage, expected_stage=stage)
    assert abs(receipt["interface_transfer_work"]) <= 1e-15
    with pytest.raises(ResonantStageMismatchError):
        reciprocal_exchange([1.0], [2.0], [[0.5]], stage=old, expected_stage=stage)
    state = regional_state(ws, ticks=1)
    transition = regional_kernel(json.loads(json.dumps(state)), {}, 4096)
    assert transition.status == "done"
    restored = workspace_from_regional_state(transition.state, require_complete=True)
    assert restored.ledger["interface_transfer_work"] == ws.ledger["interface_transfer_work"]


def test_alignment_symmetry_tangency_and_unprojected_control() -> None:
    parent = np.array([1.0, 0.0, 0.0])
    child = np.array([-1.0, 0.0, 0.0])
    assert alignment_energy(parent, child) == pytest.approx(alignment_energy(-parent, child))
    assert alignment_energy(parent, parent, phase_parent=0.0, phase_child=0.0) == pytest.approx(0.0)
    assert alignment_energy(parent, child, phase_parent=0.0, phase_child=0.0) == pytest.approx(0.0)
    grads = alignment_gradients([1, 1, 0], [1, -1, 0], phase_parent=0.2, phase_child=0.9)
    assert grads["tangent_residual"] < 1e-14
    updated, tangent = alignment_step([1.0, 1.0, 0.0], [0.2, -0.4, 0.7])
    assert abs(np.linalg.norm(updated) - 1.0) < 1e-15
    assert tangent < 1e-14
    raw = np.array([1.0, 1.0, 0.0]) / math.sqrt(2)
    unprojected = raw - 0.2 * np.array([0.2, -0.4, 0.7])
    assert abs(np.linalg.norm(unprojected) - 1.0) > 1e-3


def test_hierarchy_bounds_acyclic_degenerate_axis_and_stale_coverage() -> None:
    ws = initial_workspace()
    hierarchy = ResonantHierarchy(ws, spec=ResonantHierarchySpec(max_nodes=2, coverage_limit=2))
    hierarchy.add_region(ResonantRegionRecord("child", parent_id="root", stale=True, signed_current=2.0))
    view = hierarchy.coarse_working_set()
    assert view["coverage"] == pytest.approx(0.5)
    assert view["stale_regions"] == ["child"]
    with pytest.raises(ResonantNumericalError):
        hierarchy.add_region(ResonantRegionRecord("overflow", parent_id="root"))
    with pytest.raises(ResonantNumericalError):
        ResonantHierarchy(ws, spec=ResonantHierarchySpec(parent_map={"a": "b", "b": "a"}),
                          regions={"a": ResonantRegionRecord("a", parent_id="b"),
                                   "b": ResonantRegionRecord("b", parent_id="a")})
    unresolved = __import__("cassi_resonant_field")._axis_projection(np.zeros((3, 3)))
    assert unresolved["resolved"] is False
    assert len(unresolved["unresolved_eigenspace"]) == 3


def test_basis_change_moving_frame_geometry_and_metric_readout() -> None:
    q = np.array([1.0, -2.0])
    p = np.array([0.5, 3.0])
    scale = np.diag([2.0, 0.5])
    changed = basis_change(q, p, scale, suspended_view={"version": 1})
    assert np.allclose(changed["q"], scale @ q)
    assert np.allclose(changed["p"], np.linalg.inv(scale).T @ p)
    assert "suspended_view" in changed["invalidated"]
    angle = 0.4
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    omega = np.array([[0.0, -1.0], [1.0, 0.0]])
    check = passive_rotation_check([1.0, 0.4], rotation, rotation @ omega)
    assert check["passive_work_with_term"] == pytest.approx(0.0, abs=1e-14)
    assert check["omitted_term_norm"] > 1e-6
    full = moving_frame_rhs([1.0, 0.4], rotation, rotation @ omega, [0.0, 0.0])
    omitted = moving_frame_rhs([1.0, 0.4], rotation, rotation @ omega, [0.0, 0.0], include_frame_motion=False)
    assert not np.allclose(full, omitted)
    radii, axial = flow_line(2.0, 1.0, [0.0, math.pi / 2], kappa=0.4, omega=2.0, axial_speed=3.0)
    assert radii[-1] == pytest.approx(2.0 * math.exp(-0.4 * math.pi / 4))
    assert axial[-1] == pytest.approx(1.0 + 3.0 * math.pi / 4)
    assert uniform_axial_divergence(0.4) == pytest.approx(-0.8)
    geometry = geometry_from_flow([0.0, 0.0, 2.0], signed_current=-3.0, handedness=1)
    assert geometry.signed_current == -3.0 and geometry.handedness == 1
    weights = metric_edge_weights([[0, 0], [2, 0], [2, 1]], [(0, 1), (1, 2)], [1, 4, 2])
    assert np.allclose(weights, [0.25, 1 / math.sqrt(8)])
    assert reverse_axis_representative([1.0, 0, 0], 1)[1] == 1


def test_activity_values_empty_bounded_and_geometry_sensitive() -> None:
    assert ResonantHierarchy(initial_workspace()).activity_values([]) == {}
    events = [{"sequence": 0, "region_id": "a"}, {"sequence": 1, "region_id": "a"}]
    first = ResonantHierarchy(initial_workspace(), spec=ResonantHierarchySpec(max_nodes=4, coverage_limit=4))
    first.add_region(ResonantRegionRecord("a", parent_id="root", signed_current=0.8, handedness=1))
    second = ResonantHierarchy(initial_workspace(), spec=ResonantHierarchySpec(max_nodes=4, coverage_limit=4))
    second.add_region(ResonantRegionRecord("a", parent_id="root", signed_current=-0.8, handedness=1))
    values = first.activity_values(events, flow={"kappa": 0.3, "omega": 1.0}, scale=1.0)
    alternate = second.activity_values(events, flow={"kappa": 0.3, "omega": 1.0}, scale=1.0)
    assert values and all(np.isfinite(v) and -1.0 <= v <= 1.0 for v in values.values())
    assert values != alternate
    degenerate = ResonantHierarchy(initial_workspace(), spec=ResonantHierarchySpec(max_nodes=1, coverage_limit=1))
    assert degenerate.activity_values([{"sequence": 0}]) == {0: 0.0}
