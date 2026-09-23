"""Behavioral contracts of the canonical circulation (design section 18).

These tests exercise the production path: the declared block interfaces, the
reciprocal exchange, the orientation retune, the measured geometry, and the
bounded pass cursor as they are reached from the regional kernel, the field
machine, and the owner's read-only diagnostics.
"""
from __future__ import annotations

import copy
import json
import math

import numpy as np
import pytest

from cassi_circulation import (
    CIRCULATION_ACTIVITY_SCALE,
    CIRCULATION_MAX_HALVINGS,
    CIRCULATION_REMAINDER_FRACTION,
    CIRCULATION_STEP,
    ResonantNumericalError,
    ResonantStageMismatchError,
    _bind_stage,
    _modulation_values,
    _operator_edges,
    _RegionalWaveOperator,
    circulation_activity,
    circulation_admit,
    circulation_alignment,
    circulation_frame_change,
    circulation_geometry,
    circulation_modulation,
    circulation_unit,
    initial_circulation,
    validate_circulation,
)
from cassi_resonant_field import (
    REGIONAL_KERNEL_NAME,
    ResonantHierarchy,
    ResonantHierarchySpec,
    ResonantProfile,
    ResonantRegionRecord,
    _page_from_state,
    _regional_canonical,
    _regional_profile_data,
    initial_workspace,
    regional_kernel,
    regional_state,
    resume_regional_state,
)


def _task(topology="meaningful-helix", *, ports=4, seed=7, scale=0.02, enabled=True, ticks=1):
    """One regional task carrying an excited field and a declared segment."""

    profile = ResonantProfile(ports_per_pool=ports, topology=topology)
    workspace = initial_workspace(profile)
    count = profile.port_count
    words = scale * np.random.default_rng(seed).standard_normal(4 * count)
    excited = type(workspace)(
        profile=profile, field_page=_page_from_state(workspace, words)
    )
    state = regional_state(excited, ticks=ticks, circulation=True)
    if not enabled:
        state["circulation"]["enabled"] = False
    return state


def _operator(task):
    return _RegionalWaveOperator(task["profile"], task["bindings"], None)


def _run(task, arguments, quantum=64):
    receipt = regional_kernel(task, arguments, quantum)
    while receipt.status == "yield":
        receipt = regional_kernel(receipt.state, arguments, quantum)
    return receipt


def test_operator_residual_is_roundoff_on_declared_blocks_and_visible_when_rewired():
    for topology in ("isolated", "meaningful-helix", "undivided"):
        table = _operator_edges(
            _regional_profile_data(ResonantProfile(ports_per_pool=4, topology=topology))
        )
        assert table["edges"]
        assert table["residual"] <= 1e-9, topology
    declared = _operator_edges(
        _regional_profile_data(ResonantProfile(ports_per_pool=4))
    )
    rewired = _operator_edges(
        _regional_profile_data(ResonantProfile(ports_per_pool=4, topology="rewired"))
    )
    assert rewired["residual"] > 1e6 * declared["residual"]


def test_every_exchange_cancels_first_order_work_and_bounds_its_remainder():
    task = _task()
    segment = task["circulation"]
    operator = _operator(task)
    seen = 0
    while segment["continuation"]["phase"] != "close":
        receipt = circulation_unit(task, operator=operator)
        if receipt["phase"] != "exchange":
            continue
        seen += 1
        assert receipt["allowance_met"] is True
        assert receipt["remainder"] <= (
            CIRCULATION_REMAINDER_FRACTION * receipt["transfer_scale"] + 1e-11
        )
        assert receipt["halvings"] <= 2
        if receipt["kind"] == "neck":
            assert abs(receipt["first_order_work"]) <= 1e-6 * max(
                1e-30, receipt["transfer_scale"]
            )
    assert seen == len(segment["edges"]) == len(segment["regions"]) * 2 - 1
    assert abs(segment["ledger"]["interface_transfer_work"]) > 0.0
    assert segment["ledger"]["interface_first_order_work"] == 0.0 or abs(
        segment["ledger"]["interface_first_order_work"]
    ) < 1e-6 * abs(segment["ledger"]["interface_transfer_work"])


def test_circulate_pass_closes_the_balance_and_measures_geometry_on_the_second_pass():
    receipt = _run(_task(), {"operation": "circulate", "ticks": 2}, quantum=64)
    assert receipt.status == "done"
    assert receipt.work == 42
    output = receipt.output
    assert abs(output["balance_defect"]) <= output["energy_roundoff_allowance"]
    assert output["circulation_parameter_work"] > 0.0
    readout = output["circulation"]
    assert readout["schema"] == "cassifi.resonant-circulation-readout.v1"
    assert readout["continuation"]["pass"] == 2
    assert readout["continuation"]["phase"] == "refresh"
    geometry = readout["geometry"]
    assert geometry["rates_measured"] is True
    assert geometry["coverage"] == 1.0
    assert geometry["kappa"] > 0.0 and geometry["omega"] > 0.0
    assert math.isclose(geometry["kappa_roundtrip"], geometry["kappa"],
                        rel_tol=1e-12, abs_tol=0.0)
    assert 0.0 < geometry["quarter_turn_contraction"] <= 1.0
    assert geometry["divergence"] == -2.0 * geometry["kappa"]
    assert geometry["handedness"] in (-1, 0, 1)
    assert readout["regions"]["scale-0"]["stale"] is False
    assert readout["ledger"]["stages"] == 2.0
    assert readout["attention"]["settled"] is True
    assert readout["views"]["detail"] == "rebuilt-on-refresh"


def test_circulate_is_bounded_and_resumes_to_identical_bytes():
    stepwise = _task()
    work = 0
    while True:
        receipt = regional_kernel(stepwise, {"operation": "circulate", "ticks": 2}, 1)
        work += receipt.work
        stepwise = receipt.state
        if receipt.status != "yield":
            break
    bulk = _run(_task(), {"operation": "circulate", "ticks": 2}, quantum=4096)
    assert work == bulk.work == 42
    assert _regional_canonical(stepwise) == _regional_canonical(bulk.state)
    assert stepwise["circulation"]["ledger"] == bulk.state["circulation"]["ledger"]
    assert json.loads(json.dumps(stepwise, allow_nan=False)) == stepwise


def test_bounded_dispatches_defer_and_discharge_circulation_units():
    """A dispatch that spends its whole allowance on field ticks still owes every
    completed tick its circulation unit.  The debt is carried on the segment,
    visible in the readout, discharged before further field work, and the bounded
    run lands on the same bytes as a bulk one.
    """

    task = _task(ticks=3)
    receipt = regional_kernel(task, {}, 1)
    deferred = 0
    while receipt.status == "yield":
        deferred = max(deferred, int(receipt.state["circulation"]["continuation"]["pending"]))
        receipt = regional_kernel(receipt.state, {}, 1)
    assert deferred == 1
    assert receipt.status == "done"
    segment = receipt.state["circulation"]
    assert int(segment["continuation"]["pending"]) == 0
    assert segment["ledger"]["exchanges"] == 2.0
    assert segment["continuation"]["pass"] == 0
    assert receipt.output["circulation"]["continuation"]["pending"] == 0

    def advance(quantum):
        task = _task(ticks=6)
        work = 0
        receipt = regional_kernel(task, {}, quantum)
        work += receipt.work
        while receipt.status == "yield":
            receipt = regional_kernel(receipt.state, {}, quantum)
            work += receipt.work
        return receipt, work

    stepwise, step_work = advance(1)
    bulk, bulk_work = advance(4096)
    assert step_work == bulk_work == 18
    assert _regional_canonical(stepwise.state) == _regional_canonical(bulk.state)
    assert stepwise.output["balance_defect"] == bulk.output["balance_defect"]
    assert abs(bulk.output["balance_defect"]) <= bulk.output["energy_roundoff_allowance"]


def test_circulate_requires_a_declared_and_enabled_segment():
    plain = regional_state(profile=ResonantProfile(ports_per_pool=4), ticks=1)
    fault = regional_kernel(plain, {"operation": "circulate", "ticks": 1}, 64)
    assert fault.status == "fault"
    assert "declared circulation segment" in fault.output["message"]
    fault = regional_kernel(_task(enabled=False), {"operation": "circulate", "ticks": 1}, 64)
    assert fault.status == "fault"
    assert "enabled circulation segment" in fault.output["message"]
    advanced = _run(_task(enabled=False), {}, quantum=4096)
    assert advanced.status == "done"
    assert advanced.output["circulation"]["continuation"]["pass"] == 0
    assert advanced.output["interface_transfer_work"] == 0.0
    assert advanced.output["circulation_parameter_work"] == 0.0


def test_stage_guard_refuses_a_foreign_version_and_rebinds_after_a_refresh():
    task = _task()
    segment = task["circulation"]
    version_before = int(segment["regions"]["scale-0"]["content_version"])
    with pytest.raises(ResonantStageMismatchError):
        _bind_stage(segment, "scale-0", "scale-0", version="scale-0@999")
    first = _bind_stage(segment, "scale-0", "scale-0")
    assert first["rebound"] is False
    assert first["stage"].digest == segment["stages"]["scale-0->scale-0"]["digest"]
    receipt = _run(task, {"operation": "circulate", "ticks": 1}, quantum=4096)
    assert receipt.status == "done"
    assert receipt.output["circulation"]["continuation"]["pass"] == 1
    rebound = _bind_stage(receipt.state["circulation"], "scale-0", "scale-0")
    assert rebound["rebound"] is True
    version_after = int(receipt.state["circulation"]["regions"]["scale-0"]["content_version"])
    assert version_after == version_before + 6
    assert rebound["stage"].parent_version == f"scale-0@{version_after}"
    assert rebound["stage"].digest != first["stage"].digest
    second = _run(
        resume_regional_state(receipt.state, ticks=1),
        {"operation": "circulate", "ticks": 2},
        quantum=4096,
    )
    exchanges = [row for row in second.state["circulation"]["stages"].values()]
    assert exchanges
    assert second.output["circulation"]["continuation"]["pass"] == 2
    assert int(second.state["circulation"]["regions"]["scale-0"]["content_version"]) == (
        version_after + 6
    )


def test_orientation_retune_descends_on_the_tangent_or_refuses_and_reports():
    task = _task()
    segment = task["circulation"]
    operator = _operator(task)
    descents, refusals = 0, 0
    while segment["continuation"]["phase"] != "close":
        receipt = circulation_unit(task, operator=operator)
        if receipt["phase"] != "align":
            continue
        assert receipt["tangent_residual"] <= 1e-9
        assert abs(receipt["phase_mismatch"]) <= np.pi + 1e-12
        if receipt["refused"] is None:
            descents += 1
            assert receipt["alignment_after"] < receipt["alignment_before"]
            assert receipt["parameter_work"] == pytest.approx(
                receipt["alignment_before"] - receipt["alignment_after"], rel=1e-12, abs=0
            )
            assert 0.0 < receipt["step"] <= CIRCULATION_STEP
        else:
            refusals += 1
            assert receipt["halvings"] == CIRCULATION_MAX_HALVINGS
            assert receipt["step"] == CIRCULATION_STEP / 2 ** CIRCULATION_MAX_HALVINGS
            assert receipt["alignment_after"] == receipt["alignment_before"]
            assert receipt["parameter_work"] == 0.0
    assert descents + refusals == len(segment["edges"]) - len(segment["regions"])
    assert descents >= 1


def test_attention_hysteresis_holds_an_unsettled_frame_and_releases_on_settle():
    task = _task()
    segment = task["circulation"]
    first = circulation_admit(segment, "scale-3", stages=2)
    assert first["admitted"] is True and first["retarget"] is True
    held = circulation_admit(segment, "scale-5", stages=2)
    assert held["admitted"] is False and held["released"] is False
    assert held["refused"] == "current organising frame is still settling"
    assert segment["attention"]["target"] == "scale-3"
    assert segment["attention"]["retargets"] == 1
    settled = _run(task, {"operation": "circulate", "ticks": 2}, quantum=4096)
    assert settled.status == "done"
    attention = settled.state["circulation"]["attention"]
    assert attention["settled"] is True and attention["remaining"] == 0
    released = circulation_admit(settled.state["circulation"], "scale-5", stages=1)
    assert released["admitted"] is True
    assert settled.state["circulation"]["attention"]["target"] == "scale-5"
    assert settled.state["circulation"]["attention"]["retargets"] == 2
    threshold = settled.state["circulation"]
    mean = circulation_alignment(threshold)["mean"]
    threshold["attention"] = {
        **threshold["attention"], "target": None, "settled": True,
        "entry_threshold": mean + 0.1, "progress": mean,
    }
    gated = circulation_admit(threshold, "scale-3", stages=1)
    assert gated["admitted"] is False
    assert gated["refused"] == "orientation is already aligned inside the entry threshold"


def test_activity_modulation_is_bounded_geometry_sensitive_and_single_sourced():
    receipt = _run(_task(), {"operation": "circulate", "ticks": 1}, quantum=4096)
    segment = receipt.state["circulation"]
    events = [{"sequence": index} for index in range(8)]
    report = circulation_activity(segment, events)
    values = report["values"]
    assert set(values) == set(range(8))
    assert all(-1.0 <= value <= 1.0 for value in values.values())
    assert report["authority"] == "eligible-work-modulation-only"
    assert report["coverage"] == 1.0
    assert any(abs(value) > 1e-6 for value in values.values())
    assert all(
        value == 0.0
        for value in circulation_activity(segment, events, scale=0.0)["values"].values()
    )
    degenerate = copy.deepcopy(segment)
    degenerate["geometry"] = {**segment["geometry"], "coverage": 0.0}
    assert all(
        value == 0.0
        for value in circulation_activity(degenerate, events)["values"].values()
    )
    with pytest.raises(ResonantNumericalError):
        circulation_activity(segment, [{"sequence": -1}])
    hierarchy = ResonantHierarchy(
        initial_workspace(), spec=ResonantHierarchySpec(max_nodes=8, coverage_limit=8)
    )
    records = [
        ResonantRegionRecord(
            identity=raw["identity"],
            signed_current=float(raw["signed_current"]),
            handedness=int(raw["handedness"]),
            stale=bool(raw["stale"]),
        )
        for _identity, raw in sorted(segment["regions"].items())
    ]
    for record in records:
        hierarchy.add_region(record)
    working = hierarchy.coarse_working_set()
    assert set(working["region_ids"]) >= {record.identity for record in records}
    declared = _modulation_values(
        records, events, coverage=working["coverage"],
        total_current=working["signed_current"],
        kappa=abs(working["signed_current"]) / (1.0 + abs(working["signed_current"])),
        omega=1.0, flow_handedness=0, scale=1.0,
    )
    assert hierarchy.activity_values(events) == declared
    geometry = circulation_geometry(segment)
    assert geometry["handedness"] != 0
    measured = _modulation_values(
        records, events, coverage=working["coverage"],
        total_current=working["signed_current"], kappa=geometry["kappa"],
        omega=geometry["omega"], flow_handedness=geometry["handedness"], scale=1.0,
    )
    assert hierarchy.activity_values(events, flow=geometry) == measured
    assert hierarchy.activity_values(events, flow=geometry) != declared


def test_passive_frame_change_moves_no_work_and_preserves_scalars():
    task = _task()
    segment = task["circulation"]
    before = json.loads(_regional_canonical(segment).decode("utf-8"))
    geometry_before = circulation_geometry(segment)
    rotation = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    report = circulation_frame_change(segment, rotation)
    validate_circulation(segment)
    assert report["proper"] is True and report["field_state_unchanged"] is True
    assert report["physical_work"] == 0.0 and report["parameter_work"] == 0.0
    assert segment["ledger"] == before["ledger"]
    assert circulation_geometry(segment) == geometry_before
    frame = np.asarray(segment["regions"]["scale-0"]["axial_frame"], dtype=np.float64)
    original = np.asarray(before["regions"]["scale-0"]["axial_frame"], dtype=np.float64)
    assert np.allclose(frame.T @ frame, np.eye(frame.shape[1]), atol=1e-12)
    assert not np.allclose(frame, original)
    with pytest.raises(ResonantNumericalError):
        circulation_frame_change(segment, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]])
    with pytest.raises(ResonantNumericalError):
        circulation_frame_change(segment, [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])


def test_machine_submits_and_resumes_a_circulating_regional_task():
    from cassi_learning_computer import LearningComputer

    computer = LearningComputer.initial("circulation-machine", profile=None)
    computer, receipt = computer.submit(
        kernel=REGIONAL_KERNEL_NAME,
        state=_task(),
        arguments={"operation": "circulate", "ticks": 1},
        steps=4096,
    )
    resident = computer.inspect()["task"]
    assert resident["phase"] == "done"
    assert resident["request"]["operation"] == "circulate"
    assert resident["circulation"]["continuation"]["pass"] == 1
    assert resident["result"]["logical_work"] == 21
    assert resident["circulation"]["ledger"]["stages"] == 1.0
    successor = resume_regional_state(resident, ticks=21)
    assert successor["circulation"]["ledger"] == resident["circulation"]["ledger"]
    assert successor["circulation"]["continuation"]["pass"] == 1
    computer, receipt = computer.submit(
        kernel=REGIONAL_KERNEL_NAME, state=successor, steps=4096
    )
    advanced = computer.inspect()["task"]
    assert advanced["continuation"]["tick"] == 21
    assert advanced["circulation"]["continuation"]["pass"] == 2
    assert advanced["circulation"]["ledger"]["stages"] == 2.0
    assert advanced["circulation"]["ledger"]["exchanges"] == 26.0
    assert abs(advanced["result"]["balance_defect"]) <= advanced["result"]["energy_roundoff_allowance"]
    dropped = resume_regional_state(resident, ticks=1, circulation=False)
    assert "circulation" not in dropped
    assert "circulation" in resume_regional_state(resident, ticks=1)


def test_owner_reports_the_resident_circulation_segment_read_only(tmp_path):
    from cassi_field_owner import (
        FieldIntelligenceOwner,
        FieldIntelligenceSurface,
        RPC_SCHEMA,
    )

    def call(owner, op, action, **arguments):
        return FieldIntelligenceSurface(owner).handle({
            "schema": RPC_SCHEMA, "request_id": op, "operation": "computer",
            "params": {"operation_id": op, "computer_id": "main",
                       "action": action, "arguments": arguments},
        })["result"]["receipt"]

    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure")
        assert call(owner, "circ-before", "circulation")["regional_circulation"] is None
        call(
            owner, "submit", "submit",
            kernel=REGIONAL_KERNEL_NAME, state=_task(),
            arguments={"operation": "circulate", "ticks": 1}, steps=4096,
        )
        after = call(owner, "circ-after", "circulation")
        readout = after["regional_circulation"]
        assert readout["enabled"] is True
        assert readout["continuation"]["pass"] == 1
        assert readout["geometry"]["coverage"] == 1.0
        assert readout["ledger"]["stages"] == 1.0
        assert after["authority"] == "operational-report-only"
        assert after["state_sha256"] == owner.state.computers[0].state_sha256
        assert json.loads(json.dumps(after, allow_nan=False)) == after
        assert call(owner, "circ-after", "circulation") == after


def _agenda_state(priorities):
    """One cognition state carrying the declared obligations."""

    from cassi_field_cognition import semantic_cognition_kernel, semantic_cognition_state

    state = semantic_cognition_state(scope="circulation-agenda")
    for record_id, priority in priorities:
        transition = semantic_cognition_kernel(
            state,
            {
                "operation": "register",
                "operation_id": f"register:{record_id}",
                "kind": "Obligation",
                "record_id": record_id,
                "payload": {
                    "purpose": "candidate-selection",
                    "priority": priority,
                    "state": "pending",
                },
                "status": "active",
            },
            4096,
        )
        assert transition.status == "done"
        state = transition.state
    return state


def _agenda(state, operation_id, **request):
    from cassi_field_cognition import semantic_cognition_kernel

    transition = semantic_cognition_kernel(
        state,
        {"operation": "autonomous-agenda", "operation_id": operation_id, **request},
        4096,
    )
    assert transition.status == "done"
    return transition.output


def test_flow_modulates_eligible_work_without_changing_eligibility():
    """Section 18.5: realised flow modulates eligible-work priority, bounded."""

    from cassi_field_atlas import FieldIntelligenceError

    state = _agenda_state(
        [("work:a", 0.0), ("work:b", 0.0), ("work:c", 0.0), ("work:d", 0.0)]
    )
    plain = _agenda(state, "agenda:plain", max_items=4)
    assert plain["circulation"] is None
    assert [row["priority"] for row in plain["agenda"]] == [1.0, 1.0, 1.0, 1.0]
    plain_order = [row["obligation"]["id"] for row in plain["agenda"]]

    segment = _run(
        _task(), {"operation": "circulate", "ticks": 1}, quantum=4096
    ).state["circulation"]
    events = [{"sequence": index} for index in range(4)]
    block = circulation_modulation(segment, events)
    assert block["authority"] == "eligible-work-modulation-only"
    assert block["scale"] == CIRCULATION_ACTIVITY_SCALE
    assert set(block["values"]) == {"0", "1", "2", "3"}
    assert any(value != 0.0 for value in block["values"].values())
    assert set(block["dependencies"]) >= {
        "basis",
        "kappa",
        "omega",
        "operator_digest",
        "pass",
        "stages",
    }

    modulated = _agenda(state, "agenda:modulated", max_items=4, circulation=block)
    assert modulated["circulation"]["dependencies"] == block["dependencies"]
    assert {row["obligation"]["id"] for row in modulated["agenda"]} == set(plain_order)
    bound = math.tanh(CIRCULATION_ACTIVITY_SCALE) + 1e-12
    for row in modulated["agenda"]:
        sequence = row["circulation_sequence"]
        assert block["values"][str(sequence)] == row["circulation_adjustment"]
        assert abs(row["circulation_adjustment"]) <= bound
        assert row["priority"] == row["base_priority"] + row["circulation_adjustment"]
    assert [row["obligation"]["id"] for row in modulated["agenda"]] != plain_order
    assert modulated["selected"]["obligation"]["id"] == modulated["agenda"][0]["obligation"]["id"]

    ranked = _agenda_state(
        [("work:a", 0.0), ("work:b", 0.0), ("work:c", 0.0), ("work:d", 3.0)]
    )
    assert _agenda(ranked, "agenda:ranked-plain", max_items=4)["agenda"][0][
        "obligation"
    ]["id"] == "work:d"
    ranked_flow = _agenda(
        ranked, "agenda:ranked-flow", max_items=4, circulation=block
    )
    assert ranked_flow["agenda"][0]["obligation"]["id"] == "work:d"
    assert ranked_flow["agenda"][0]["priority"] >= 4.0 - bound

    ineligible = _agenda_state([("work:a", 0.0), ("work:b", 0.0)])
    from cassi_field_cognition import semantic_cognition_kernel

    transition = semantic_cognition_kernel(
        ineligible,
        {
            "operation": "register",
            "operation_id": "register:work:done",
            "kind": "Obligation",
            "record_id": "work:done",
            "payload": {
                "purpose": "candidate-selection",
                "priority": 9.0,
                "state": "fulfilled",
            },
            "status": "active",
        },
        4096,
    )
    assert transition.status == "done"
    favoured = _agenda(
        transition.state, "agenda:ineligible", max_items=8, circulation=block
    )
    assert "work:done" not in {
        row["obligation"]["id"] for row in favoured["agenda"]
    }
    assert favoured["selected"]["obligation"]["id"] != "work:done"

    with pytest.raises(FieldIntelligenceError):
        _agenda(
            state,
            "agenda:bad-authority",
            max_items=2,
            circulation={**block, "authority": "evidence"},
        )
    with pytest.raises(FieldIntelligenceError):
        _agenda(
            state,
            "agenda:bad-value",
            max_items=2,
            circulation={**block, "values": {"0": 1.5}},
        )
    with pytest.raises(FieldIntelligenceError):
        _agenda(
            state,
            "agenda:bad-dependencies",
            max_items=2,
            circulation={**block, "dependencies": {}},
        )


def test_owner_produces_the_flow_modulation_of_its_resident_circulation(tmp_path):
    from cassi_field_owner import (
        FieldIntelligenceOwner,
        FieldIntelligenceSurface,
        RPC_SCHEMA,
    )

    def call(owner, op, action, **arguments):
        return FieldIntelligenceSurface(owner).handle({
            "schema": RPC_SCHEMA, "request_id": op, "operation": "computer",
            "params": {"operation_id": op, "computer_id": "main",
                       "action": action, "arguments": arguments},
        })["result"]["receipt"]

    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure")
        assert owner.circulation_modulation([{"sequence": 0}]) is None
        call(
            owner, "submit", "submit",
            kernel=REGIONAL_KERNEL_NAME, state=_task(),
            arguments={"operation": "circulate", "ticks": 1}, steps=4096,
        )
        events = [{"sequence": index} for index in range(3)]
        block = owner.circulation_modulation(events)
        assert block["authority"] == "eligible-work-modulation-only"
        assert block["enabled"] is True and block["region_count"] >= 2
        assert block["scale"] == CIRCULATION_ACTIVITY_SCALE
        assert set(block["values"]) == {"0", "1", "2"}
        assert set(block["dependencies"]) >= {
            "computer_id",
            "operator_digest",
            "resident_state_sha256",
            "stages",
            "state_sha256",
        }
        assert block["dependencies"]["computer_id"] == "main"
        assert block["dependencies"]["pass"] == 1
        assert block["dependencies"]["state_sha256"] == (
            owner.state.computers[0].state_sha256
        )
        assert json.loads(json.dumps(block, allow_nan=False)) == block
        assert owner.circulation_modulation(events, computer_id="absent") is None
        assert owner.circulation_modulation([])["values"] == {}
