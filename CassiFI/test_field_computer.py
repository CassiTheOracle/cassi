"""Non-trivial public-contract tests for the field-owned computer.

The expected transition and TM models come from ``verify_field_computer`` and
never inspect implementation state.  These tests intentionally compare
intermediate stacks/PCs, not merely terminal status, so a wrong branch target,
empty-pop rule, direction, or tape orientation is observable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import numpy as np

import cassi_field_computer as computer_module
import cassi_field_regions as regions
from cassi_field_computer import ComputerProfile, ComputerState, FieldComputer
from cassi_field_regions import (
    D_BASE,
    D_RESERVED,
    DIRECTORY_WORDS,
    HEADER_WORDS,
    H_QUEUE,
    H_MAGIC,
    H_PROFILE_SHA,
    KernelCatalog,
    KernelResult,
    RegionalProfile,
)
import verify_field_computer as audit


def _assert_same(machine: FieldComputer, state: Any, expected: audit.RefState) -> None:
    actual = audit.semantic_snapshot(machine.inspect(state))
    assert actual == audit.reference_snapshot(expected)


def test_each_public_primitive_step_matches_independent_two_stack_model() -> None:
    program = (
        (audit.REF_POP, 0, 1, 0, 0),
        (audit.REF_BRANCH, audit.REF_EMPTY, 2, 4, 0),
        (audit.REF_PUSH, 1, 0, 3, 0),
        (audit.REF_JUMP, 6, 0, 0, 0),
        (audit.REF_PUSH, 0, 255, 5, 0),
        (audit.REF_JUMP, 6, 0, 0, 0),
        (audit.REF_HALT, 0, 0, 0, 0),
    )
    profile = ComputerProfile(program_capacity=32, stack_capacity=32, max_steps=100)
    machine = FieldComputer(profile)
    state = machine.initial(program, left=(), right=(17,))
    expected = audit.reference_initial(program, right=(17,), max_steps=100, stack_capacity=32)
    _assert_same(machine, state, expected)

    for _ in range(32):
        if machine.inspect(state)["status"] != "running":
            break
        state, event = machine.step(state)
        assert event is not None
        expected = audit.reference_step(expected, max_steps=100, stack_capacity=32)
        _assert_same(machine, state, expected)
    else:
        raise AssertionError("the branch program did not terminate")
    info = machine.inspect(state)
    assert info["status"] == "halted"
    assert tuple(info["left"]) == ()
    assert tuple(info["right"]) == (17, 0)


def test_empty_push_acc_fault_preserves_tape_and_does_not_choose_a_symbol() -> None:
    machine = FieldComputer(ComputerProfile(program_capacity=8, stack_capacity=8, max_steps=20))
    state = machine.initial(((audit.REF_PUSH_ACC, 0, 1, 0, 0), (audit.REF_HALT, 0, 0, 0, 0)))
    state, _ = machine.run(state)
    info = machine.inspect(state)
    assert info["status"] == "faulted"
    assert tuple(info["left"]) == ()
    assert tuple(info["right"]) == ()
    assert int(info["accumulator"]) == audit.REF_EMPTY
    assert int(info["resource_ledger"]["stack_writes"]) == 0


def test_resize_and_budget_boundaries_preserve_configuration() -> None:
    detail = audit.check_capacity_and_resize()
    assert detail["stack_exhausted"] == "exhausted"
    assert detail["resumed_status"] == "halted"
    budget = audit.check_nonhalting_and_field_budget()
    assert budget["partial_transitions"] == 7
    assert budget["terminal_transitions"] == 40
    assert budget["status"] == "exhausted"


def test_descriptor_round_trip_and_field_alias_protection() -> None:
    detail = audit.check_descriptor_and_immutability()
    assert detail["tampered_fields"] >= 1
    assert len(detail["state_sha256"]) == 64


def _step_until_terminal(machine: FieldComputer, state: Any) -> tuple[Any, int]:
    physical_cells = 0
    while machine.inspect(state)["status"] == "running":
        state, receipt = machine.step(state)
        physical = receipt["physical_copy_work"]
        physical_cells += physical["working_copy_cells"] + physical["sealed_copy_cells"]
    return state, physical_cells


def test_batched_run_is_full_field_equivalent_and_seals_once_across_boundaries() -> None:
    cases = (
        (
            ((1, 0, 7, 1, 0), (2, 0, 2, 0, 0), (3, 7, 3, 4, 0),
             (4, 1, 5, 0, 0), (1, 1, 99, 5, 0), (0, 0, 0, 0, 0)),
            8,
            100,
        ),
        (
            ((1, 0, 1, 1, 0), (1, 0, 2, 2, 0), (0, 0, 0, 0, 0)),
            1,
            100,
        ),
        (
            ((4, 0, 1, 0, 0), (0, 0, 0, 0, 0)),
            4,
            100,
        ),
    )
    reduced_cases = 0
    for program, stack_capacity, max_steps in cases:
        machine = FieldComputer(ComputerProfile(
            program_capacity=16,
            stack_capacity=stack_capacity,
            max_steps=max_steps,
        ))
        initial = machine.initial(program)
        stepped, step_physical = _step_until_terminal(machine, initial)
        batched, receipt = machine.run(initial)
        assert machine.descriptor(batched)["state_sha256"] == machine.descriptor(stepped)["state_sha256"]
        batch_physical = sum(receipt["physical_copy_work"].values())
        assert batch_physical == 2 * machine.profile.field_cells
        assert batch_physical <= step_physical
        reduced_cases += int(batch_physical < step_physical)
    assert reduced_cases == 2


def test_batched_pause_matches_public_steps_and_resumes_at_exact_checkpoint() -> None:
    program = (
        (1, 0, 4, 1, 0),
        (2, 0, 2, 0, 0),
        (4, 1, 3, 0, 0),
        (0, 0, 0, 0, 0),
    )
    machine = FieldComputer(ComputerProfile(program_capacity=8, stack_capacity=8, max_steps=20))
    initial = machine.initial(program)
    stepped = initial
    for _ in range(2):
        stepped, _ = machine.step(stepped)
    paused, pause_receipt = machine.run(initial, steps=2)
    assert pause_receipt["paused"] is True
    assert machine.descriptor(paused)["state_sha256"] == machine.descriptor(stepped)["state_sha256"]
    stepped_final, _ = _step_until_terminal(machine, stepped)
    batched_final, _ = machine.run(paused)
    assert machine.descriptor(batched_final)["state_sha256"] == machine.descriptor(stepped_final)["state_sha256"]


def test_hot_basic_blocks_are_field_learned_restart_stable_and_exact() -> None:
    program = (
        (1, 0, 7, 1, 0),
        (2, 0, 2, 0, 0),
        (4, 1, 3, 0, 0),
        (0, 0, 0, 0, 0),
    )
    machine = FieldComputer(ComputerProfile(program_capacity=8, stack_capacity=8, max_steps=20))
    state = machine.initial(program)
    cold, cold_receipt = machine.run(state, use_blocks=True)
    cold_plain, _ = machine.run(state, use_blocks=False)
    assert (
        machine.descriptor(cold)["state_sha256"]
        == machine.descriptor(cold_plain)["state_sha256"]
    )
    assert cold_receipt["specialization"] == {
        "enabled": True,
        "hot_threshold": 8,
        "derived_blocks": 0,
        "derivation_deferred": True,
        "block_invocations": 0,
        "block_transitions": 0,
    }
    for cycle in range(8):
        state, _ = machine.run(state, use_blocks=False)
        if cycle < 7:
            state, _ = machine.restart(state)
    learned = machine.inspect(state)["execution_learning"]
    assert learned["hot_pcs"] == [0, 1, 2, 3]
    restarted, restart_receipt = machine.restart(state, left=(9,))
    assert restart_receipt["retained_execution_observations"] == 32
    assert sum(restart_receipt["physical_copy_work"].values()) == 2 * machine.profile.field_cells

    specialized, specialized_receipt = machine.run(restarted, use_blocks=True)
    unspecialized, plain_receipt = machine.run(restarted, use_blocks=False)
    assert specialized_receipt["specialization"]["block_invocations"] > 0
    assert plain_receipt["specialization"]["block_invocations"] == 0
    assert machine.descriptor(specialized)["state_sha256"] == machine.descriptor(unspecialized)["state_sha256"]
    for key in (
        "status",
        "reason",
        "paused",
        "transitions_executed",
        "resource_ledger",
    ):
        assert specialized_receipt[key] == plain_receipt[key]
    assert specialized_receipt["specialization"]["derived_blocks"] > 0
    assert specialized_receipt["specialization"]["derivation_deferred"] is False

    fast_paused, fast_pause_receipt = machine.run(
        restarted,
        steps=2,
        use_blocks=True,
    )
    plain_paused, plain_pause_receipt = machine.run(
        restarted,
        steps=2,
        use_blocks=False,
    )
    assert (
        machine.descriptor(fast_paused)["state_sha256"]
        == machine.descriptor(plain_paused)["state_sha256"]
    )
    assert fast_pause_receipt["paused"] is True
    assert fast_pause_receipt["transitions_executed"] == 2
    assert (
        fast_pause_receipt["resource_ledger"]
        == plain_pause_receipt["resource_ledger"]
    )
    assert fast_pause_receipt["specialization"]["block_invocations"] == 1

def test_compiled_tm_boundaries_cover_algorithms_and_both_directions() -> None:
    detail = audit.check_turing_machine_boundaries()
    assert detail["machines"] >= 4
    assert all(row["status"] == "halted" for row in detail["outcomes"])
    assert len(set(detail["distinct_halt_pcs"])) == 2

def test_exhaustive_small_tm_table_coverage_is_bounded_and_independent() -> None:
    detail = audit.check_generated_tm_tables()
    assert detail["tables"] == 144
    assert detail["runs"] == 288
    assert detail["tm_horizon"] == 3
    assert detail["primitive_steps"] > 0

def test_malformed_programs_and_tm_descriptors_are_rejected() -> None:
    detail = audit.check_validation()
    assert detail["malformed_programs"] >= 8
    assert detail["compiler_refusals"] >= 4


def _propagation_program(frame: tuple[int, ...] = ()) -> tuple[tuple[int, ...], ...]:
    pushes = tuple(
        (computer_module.PUSH, 0, value, pc + 1, 0)
        for pc, value in enumerate(frame)
    )
    entry = len(pushes)
    return pushes + (
        (computer_module.PROPAGATE, 0, entry + 1, 0, 0),
        (computer_module.BRANCH, computer_module.PROPAGATION_PROGRESS, entry, entry + 2, 0),
        (computer_module.PUSH_ACC, 1, entry + 3, 0, 0),
        (computer_module.HALT, 0, 0, 0, 0),
    )


def _workspace(machine: FieldComputer, state: Any) -> dict[str, Any]:
    return computer_module.inspect_propagation_workspace(machine.inspect(state)["left"])


def test_stored_propagation_pause_reload_and_result_consumption(monkeypatch) -> None:
    from cassi_constraint_dynamics import ExcitableConstraintState
    from cassi_learning_computer import LearningComputer

    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("standalone state or solver is unavailable")

    monkeypatch.setattr(ExcitableConstraintState, "__post_init__", unavailable)
    monkeypatch.setattr(LearningComputer, "solve", unavailable)
    monkeypatch.setattr(LearningComputer, "continue_solve", unavailable)
    frame = computer_module.propagation_workspace(
        ((1,), (2,), (-1, 3)), variable_count=3, excitation=(0, 1024, 0),
    )
    program = _propagation_program((42,) + frame)
    machine = FieldComputer(ComputerProfile(
        program_capacity=len(program), stack_capacity=512, max_steps=1000,
    ))
    initial = machine.initial(program)
    paused, pause_receipt = machine.run(initial, steps=len(frame) + 2)
    assert pause_receipt["paused"]
    assert _workspace(machine, paused)["assignment"] == [0, 1, 0]
    saved = machine.descriptor(paused)
    restored_machine, restored = FieldComputer.from_descriptor(json.loads(json.dumps(saved)))
    assert restored_machine.descriptor(restored) == saved

    stepped = restored
    previous = saved["state_sha256"]
    while stepped.status == "running":
        stepped, receipt = restored_machine.step(stepped)
        assert receipt["previous_state_sha256"] == previous
        previous = receipt["state_sha256"]
    batched, resume_receipt = restored_machine.run(restored)
    direct, _ = machine.run(initial)
    assert resume_receipt["initial_state_sha256"] == pause_receipt["state_sha256"]
    assert (
        machine.state_sha256(direct)
        == restored_machine.state_sha256(batched)
        == previous
        == restored_machine.state_sha256(stepped)
    )
    info = machine.inspect(direct)
    assert info["status"] == "halted"
    assert info["right"] == [computer_module.PROPAGATION_SATISFIED]
    assert info["left"][0] == 42
    result = _workspace(machine, direct)
    assert result["assignment"] == [1, 1, 1]
    assert result["calls"] == 4
    assert result["work"] == {"clause_visits": 12, "literal_visits": 16}
    assert result["automaton"]["ticks"] == 12
    assert result["automaton"]["selections"] == 3


def test_automaton_excitation_changes_which_ready_deduction_executes_first() -> None:
    first_assignments = []
    for excitation in ((0, 0), (0, 1024)):
        frame = computer_module.propagation_workspace(
            ((1,), (2,)), variable_count=2, excitation=excitation,
        )
        machine = FieldComputer(ComputerProfile(
            program_capacity=4, stack_capacity=len(frame), max_steps=32,
        ))
        first, _ = machine.step(machine.initial(_propagation_program(), left=frame))
        first_assignments.append(_workspace(machine, first)["assignment"])
        terminal, _ = machine.run(first)
        assert _workspace(machine, terminal)["assignment"] == [1, 1]
        assert machine.inspect(terminal)["right"] == [computer_module.PROPAGATION_SATISFIED]
    assert first_assignments == [[1, 0], [0, 1]]


def test_owner_reopens_and_resumes_the_same_machine_propagation(tmp_path, monkeypatch) -> None:
    from cassi_field_owner import FieldIntelligenceOwner
    from cassi_learning_computer import LearningComputer

    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("solver operations are unavailable")

    monkeypatch.setattr(LearningComputer, "solve", unavailable)
    monkeypatch.setattr(LearningComputer, "continue_solve", unavailable)
    frame = computer_module.propagation_workspace(((1,), (2,)), variable_count=2)
    root = tmp_path / "computer"
    with FieldIntelligenceOwner(root) as owner:
        owner.operate_computer("configure", computer_id="main", action="configure", arguments={
            "profile": {"program_capacity": 4, "stack_capacity": len(frame), "max_steps": 32},
        })
        owner.operate_computer("load", computer_id="main", action="load", arguments={
            "program": _propagation_program(), "left": frame,
        })
        paused = owner.operate_computer(
            "pause", computer_id="main", action="advance", arguments={"steps": 1},
        )
        checkpoint = owner.state.state_sha256
        row = owner.state.computers[0]
        controller = row._controller()
        expected_field, _ = controller.run(row.field, steps=32)
        expected_task = controller.named_value(expected_field, "task")
        expected_session = controller.named_value(expected_field, "session")
        expected_field, _ = controller.write_named_value(
            expected_field,
            "session",
            {**expected_session, "status": expected_task["status"]},
        )
        expected_digest = controller.state_sha256(expected_field)
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == checkpoint
        completed = owner.operate_computer(
            "resume", computer_id="main", action="advance", arguments={"steps": 32},
        )
        assert completed["receipt"]["initial_state_sha256"] == paused["receipt"]["state_sha256"]
        assert completed["receipt"]["state_sha256"] == expected_digest
        task = owner.state.computers[0].inspect()["task"]
        assert task["right"] == [
            computer_module.PROPAGATION_SATISFIED,
        ]
        finished_checkpoint = owner.state.state_sha256
        repeated = owner.operate_computer(
            "resume", computer_id="main", action="advance", arguments={"steps": 32},
        )
        assert repeated["receipt"] == completed["receipt"]
        assert repeated["checkpoint_receipt"]["replayed"]
        assert owner.state.state_sha256 == finished_checkpoint


@pytest.mark.parametrize("clauses,variables,result,assignment", (
    (((1, 2),), 2, computer_module.PROPAGATION_FIXED_POINT, [0, 0]),
    (((1,), (-1,)), 1, computer_module.PROPAGATION_CONFLICT, None),
    (((1, -1),), 1, computer_module.PROPAGATION_SATISFIED, [0]),
    (((1, 1),), 1, computer_module.PROPAGATION_SATISFIED, [1]),
    ((), 0, computer_module.PROPAGATION_SATISFIED, []),
    (((),), 0, computer_module.PROPAGATION_CONFLICT, []),
))
def test_propagation_classifies_residual_clause_boundaries(clauses, variables, result, assignment) -> None:
    frame = computer_module.propagation_workspace(clauses, variable_count=variables)
    machine = FieldComputer(ComputerProfile(
        program_capacity=4, stack_capacity=len(frame), max_steps=32,
    ))
    final, _ = machine.run(machine.initial(_propagation_program(), left=frame))
    assert final.status == "halted"
    assert machine.inspect(final)["right"] == [result]
    if assignment is not None:
        assert _workspace(machine, final)["assignment"] == assignment


@pytest.mark.parametrize("corruption", ("truncated", "magic", "nonfinite_lanes"))
def test_malformed_propagation_faults_without_changing_input_or_accumulator(corruption) -> None:
    import struct

    frame = bytearray(computer_module.propagation_workspace(((1,),), variable_count=1))
    if corruption == "truncated":
        frame.pop()
    elif corruption == "magic":
        frame[0] ^= 1
    else:
        # Corrupt a real CFP1 lane block, not the outer float64 byte-symbol field.
        lanes_start = len(frame) - 4 - (4 + 8) * 8
        frame[lanes_start:lanes_start + 8] = struct.pack("<d", float("nan"))
    program = (
        (computer_module.POP, 1, 1, 0, 0),
        (computer_module.PROPAGATE, 0, 2, 0, 0),
        (computer_module.HALT, 0, 0, 0, 0),
    )
    machine = FieldComputer(ComputerProfile(
        program_capacity=3, stack_capacity=len(frame), max_steps=8,
    ))
    before, _ = machine.step(machine.initial(program, left=tuple(frame), right=(7,)))
    faulted, receipt = machine.step(before)
    old = machine.inspect(before)
    new = machine.inspect(faulted)
    assert new["status"] == "faulted"
    assert new["pc"] == old["pc"]
    assert new["left"] == old["left"]
    assert new["right"] == old["right"]
    assert new["accumulator"] == old["accumulator"] == 7
    assert receipt["previous_state_sha256"] == machine.state_sha256(before)


def test_legacy_descriptor_remains_exact_and_new_instruction_cannot_downgrade() -> None:
    machine = FieldComputer(ComputerProfile(program_capacity=4, stack_capacity=4, max_steps=8))
    old = machine.descriptor(machine.initial((
        (computer_module.PUSH, 0, 7, 1, 0), (computer_module.HALT, 0, 0, 0, 0),
    )))
    assert old["schema"] == "cassifi.field-computer.v1"
    restored_machine, restored = FieldComputer.from_descriptor(json.loads(json.dumps(old)))
    assert restored_machine.descriptor(restored) == old
    new = machine.descriptor(machine.initial(_propagation_program()))
    assert new["schema"] == "cassifi.field-computer.v2"
    with pytest.raises(computer_module.FieldComputerError):
        FieldComputer.from_descriptor({**new, "schema": old["schema"]})


def _regional_machine(
    *,
    catalog: KernelCatalog | None = None,
    mode_count: int = 16_384,
    max_steps: int = 128,
    max_events: int = 256,
) -> FieldComputer:
    selected = catalog or KernelCatalog({}, {})
    profile = RegionalProfile(
        mode_count=mode_count,
        max_steps=max_steps,
        max_events=max_events,
        kernel_names=selected.names,
    )
    return FieldComputer.regional(profile, catalog=selected)


def test_regional_computer_executes_cross_region_program_and_round_trips() -> None:
    machine = _regional_machine()
    initial = machine.initial(
        (
            {"op": "COPY", "source": "input", "target": "output", "next": 1},
            {"op": "YIELD", "next": 2},
            {"op": "HALT"},
        ),
        values={"input": {"token": 17}, "output": None},
    )
    after_copy, copy_receipt = machine.step(initial)
    assert machine.named_value(after_copy, "output") == {"token": 17}
    assert copy_receipt["operation"] == "COPY"
    after_copy_sha256 = machine.state_sha256(after_copy)
    assert machine.named_values(
        after_copy, ("input", "output")
    ) == {
        "input": {"token": 17},
        "output": {"token": 17},
    }
    assert machine.state_sha256(after_copy) == after_copy_sha256
    assert copy_receipt["previous_state_sha256"] == machine.state_sha256(
        initial
    )
    assert copy_receipt["state_sha256"] == after_copy_sha256
    assert after_copy.field.nbytes == initial.field.nbytes
    paused, run_receipt = machine.run(after_copy, steps=1)
    assert run_receipt["status"] == "running"
    assert machine.inspect(paused)["logical_transition"] == 2

    descriptor = json.loads(json.dumps(machine.descriptor(paused)))
    assert "field_b64" not in descriptor
    assert descriptor["page_words"] == 4096
    assert len(descriptor["field_pages"]) < (
        machine.profile.total_words + descriptor["page_words"] - 1
    ) // descriptor["page_words"]
    duplicated = json.loads(json.dumps(descriptor))
    duplicated["field_pages"].append(dict(duplicated["field_pages"][0]))
    with pytest.raises(
        computer_module.FieldComputerError,
        match="descriptor pages are invalid",
    ):
        FieldComputer.from_descriptor(duplicated)
    restored_machine, restored = FieldComputer.from_descriptor(descriptor)
    assert restored_machine.is_regional
    assert restored_machine.state_sha256(restored) == machine.state_sha256(paused)
    completed, completed_receipt = restored_machine.run(restored)
    assert restored_machine.inspect(completed)["status"] == "halted"
    assert completed_receipt["transitions_executed"] == 1

    restarted, restart_receipt = restored_machine.restart(completed, entry=0)
    assert restart_receipt["kind"] == "restart"
    assert restored_machine.inspect(restarted)["status"] == "running"
    intervened, intervention = restored_machine.intervene_automaton(
        restarted, site=0, excitation=3
    )
    assert intervention["kind"] == "automaton-intervention"
    assert restored_machine.state_sha256(intervened) != restored_machine.state_sha256(
        restarted
    )
    grown_machine, grown, growth = restored_machine.grow(
        intervened, mode_count=20_000, max_steps=256
    )
    assert growth["kind"] == "grow"
    assert grown_machine.named_value(grown, "output") == {"token": 17}
    assert grown.field.shape == grown_machine.profile.shape
    grown_machine.validate(grown)
    grown_descriptor = json.loads(json.dumps(grown_machine.descriptor(grown)))
    assert grown_descriptor["profile"]["mode_count"] == 20_000
    assert len(grown_descriptor["field_pages"]) <= len(descriptor["field_pages"])
    assert len(grown_descriptor["field_pages"]) < (
        grown_machine.profile.total_words + grown_descriptor["page_words"] - 1
    ) // grown_descriptor["page_words"]
    recovered_machine, recovered_grown = FieldComputer.from_descriptor(
        grown_descriptor
    )
    assert recovered_machine.profile.mode_count == 20_000
    assert recovered_machine.state_sha256(
        recovered_grown
    ) == grown_machine.state_sha256(grown)
    assert recovered_machine.named_value(
        recovered_grown, "output"
    ) == {"token": 17}


@pytest.mark.parametrize(
    "mutate",
    (
        lambda field: field.reshape(-1).__setitem__(H_MAGIC, 0.0),
        lambda field: field.reshape(-1).__setitem__(H_PROFILE_SHA, 0.0),
        lambda field: field.reshape(-1).__setitem__(
            HEADER_WORDS + DIRECTORY_WORDS + D_BASE,
            field.reshape(-1)[HEADER_WORDS + D_BASE],
        ),
        lambda field: field.reshape(-1).__setitem__(H_QUEUE + 1, 99.0),
        lambda field: field.reshape(-1).__setitem__(
            HEADER_WORDS + D_RESERVED, 1.0
        ),
        lambda field: field.reshape(-1).__setitem__(-1, float("nan")),
    ),
)
def test_regional_validator_rejects_header_directory_reference_and_lane_tampering(
    mutate,
) -> None:
    machine = _regional_machine()
    state = machine.initial(({"op": "HALT"},), values={"x": 1})
    tampered = np.array(state.field, copy=True)
    mutate(tampered)
    tampered.setflags(write=False)
    with pytest.raises(computer_module.FieldComputerError):
        machine.validate(ComputerState(tampered, machine.profile.fingerprint))


def test_regional_failed_move_is_atomic_and_fault_is_visible() -> None:
    machine = _regional_machine()
    state = machine.initial(
        (
            {
                "op": "ALLOC",
                "kind": 7,
                "codec": 1,
                "value": {"payload": "created"},
                "capacity": 32,
                "target": "tiny",
                "next": 1,
            },
            {"op": "HALT"},
        ),
        values={"tiny": 0},
        value_capacities={"tiny": 2},
    )
    region_count = len(machine.inspect(state)["regions"])
    faulted, receipt = machine.step(state)
    assert receipt["disposition"] == "fault"
    assert machine.inspect(faulted)["status"] == "faulted"
    assert len(machine.inspect(faulted)["regions"]) == region_count
    assert machine.named_value(faulted, "tiny") == 0


def test_regional_kernel_catalog_is_frozen_and_unknown_kernels_are_rejected() -> None:
    def identity(
        state: Any, _arguments: Any, _quantum: int
    ) -> KernelResult:
        return KernelResult(state=state, output=state, work=1)

    catalog = KernelCatalog({"identity": identity}, {"identity": 1})
    machine = _regional_machine(catalog=catalog)
    state = machine.initial(
        (
            {
                "op": "NATIVE",
                "kernel": "identity",
                "state": "source",
                "output": "target",
                "next": 1,
            },
            {"op": "HALT"},
        ),
        values={"source": [1, 2, 3], "target": None},
    )
    complete, receipt = machine.run(state)
    assert machine.named_value(complete, "target") == [1, 2, 3]
    assert receipt["transition_receipts"][0]["work"]["native"] == 1
    with pytest.raises(TypeError):
        exec("catalog.kernels['other'] = identity", locals())
    with pytest.raises(computer_module.FieldComputerError):
        machine.initial(
            ({"op": "NATIVE", "kernel": "missing", "state": "source"},),
            values={"source": None},
        )


def test_regional_automaton_intervention_changes_event_selection_causally() -> None:
    machine = _regional_machine()
    state = machine.initial(
        (
            {"op": "HALT"},
            {"op": "WRITE", "target": "winner", "value": "external", "next": 2},
            {"op": "HALT"},
        ),
        values={"winner": "root"},
    )
    queued, admission = machine.enqueue_event(state, {"pc": 1, "site": 1})
    assert admission["kind"] == "event-admission"
    baseline, baseline_receipt = machine.step(queued)
    assert baseline_receipt["event_id"] == 1
    assert machine.named_value(baseline, "winner") == "root"

    intervened, _ = machine.intervene_automaton(
        queued, site=1, excitation=machine.profile.automaton_scale
    )
    changed, changed_receipt = machine.step(intervened)
    assert changed_receipt["event_id"] == 2
    assert machine.named_value(changed, "winner") == "external"
    assert changed_receipt["eligibility_sha256"] != ""
    assert changed_receipt["automaton"]["selected_variable"] == 2


def test_regional_native_catalog_rejects_stateful_kernel_closures() -> None:
    mutable_bias = [1]

    def stateful(
        state: Any, _arguments: Any, _quantum: int
    ) -> KernelResult:
        return KernelResult(state=state, output=mutable_bias[0])

    catalog = KernelCatalog({"stateful": stateful}, {"stateful": 1})
    machine = _regional_machine(catalog=catalog)
    with pytest.raises(computer_module.FieldComputerError):
        machine.initial(
            (
                {
                    "op": "NATIVE",
                    "kernel": "stateful",
                    "state": "state",
                },
            ),
            values={"state": None},
        )


# -- Section 18: bounded-residency (paged) regional execution -------------


def _paged_machine(program_length: int = 4):
    machine = _regional_machine()
    program = tuple(
        {"op": "COPY", "source": "input", "target": "output", "next": index + 1}
        for index in range(program_length)
    ) + ({"op": "HALT"},)
    state = machine.initial(
        program, values={"input": {"token": 17}, "output": None}
    )
    return machine, program, state


def test_paged_state_matches_dense_execution_and_round_trips_bounded() -> None:
    machine, _program, state = _paged_machine(4)
    paged, record = machine.paged_state(state, resident_limit=4)
    assert isinstance(paged, computer_module.PagedComputerState)
    assert record["kind"] == "storage-only"
    assert paged.status == "running"
    assert paged.profile_sha256 == machine.profile.fingerprint
    assert paged.root_sha256 == paged.image.root_sha256
    assert paged.residency_report()["resident_pages"] <= 4

    dense_final, dense_receipt = machine.run(state, steps=6)
    paged_final, summary = machine.run_paged(paged, steps=6)
    assert summary["stop"] == "settled"
    assert summary["steps"] == dense_receipt["transitions_executed"]
    assert machine.inspect_paged(paged_final)["status"] == machine.inspect(
        dense_final
    )["status"]
    assert machine.materialise_paged(paged_final).status == "halted"
    assert np.array_equal(
        machine.materialise_paged(paged_final)._field, dense_final._field
    )
    # The paged state is a storage-only adoption: identity is unchanged.
    assert machine.state_sha256(
        machine.materialise_paged(paged_final)
    ) == machine.state_sha256(dense_final)

    descriptor, objects = machine.paged_chunks(paged_final)
    assert descriptor["schema"] == regions.PERSISTENCE_CHUNK_SCHEMA
    # The stored descriptor declares the same logical identity as the dense
    # twin, whether or not a commit audit digest was recorded.
    assert descriptor["state_sha256"] == machine.state_sha256(dense_final)
    reopened = machine.from_paged_chunks(descriptor, objects, resident_limit=3)
    assert reopened.root_sha256 == paged_final.root_sha256
    assert reopened.residency_report()["resident_pages"] <= 3
    assert np.array_equal(
        machine.materialise_paged(reopened)._field,
        machine.materialise_paged(paged_final)._field,
    )
    # A step past the halt is a no-op that keeps the same committed root.
    noop_state, noop_receipt = machine.step_paged(reopened)
    assert noop_receipt["kind"] == "noop"
    assert noop_state is reopened

    paged_descriptor = machine.descriptor_paged(
        paged_final, semantic={"family": "regional"}, resource={"stage": "test"}
    )
    assert paged_descriptor["schema"] == regions.PAGED_MANIFEST_SCHEMA
    assert paged_descriptor["root_sha256"] == paged_final.root_sha256
    assert paged_descriptor["semantic"] == {"family": "regional"}
    assert paged_descriptor["resource"] == {"stage": "test"}
    with pytest.raises(computer_module.FieldComputerError):
        machine.paged_state(
            computer_module.ComputerState(
                np.zeros(machine.profile.shape, dtype=np.float64), "0" * 64
            )
        )


def test_paged_residency_wait_is_a_continuation_that_resumes_exactly() -> None:
    machine = _regional_machine()
    program = tuple({"op": "YIELD", "next": index + 1} for index in range(600)) + (
        {"op": "HALT"},
    )
    state = machine.initial(
        program, values={"input": {"token": 17}, "output": None}
    )
    paged, _record = machine.paged_state(state, resident_limit=1)
    waited, summary = machine.run_paged(paged, steps=4)
    assert summary["stop"] == "wait"
    assert summary["wait"]["reason"] == "resource"
    continuation = regions.read_residency_continuation(summary["continuation"])
    assert continuation["root_sha256"] == paged.root_sha256
    assert continuation["page_versions"]
    assert continuation["segments"]
    # A wait commits nothing: the caller keeps the predecessor it passed in.
    assert waited is paged

    resumed = machine.resume_paged(paged, resident_limit=32)
    assert resumed.root_sha256 == paged.root_sha256
    assert resumed.residency_report()["resident_limit"] == 32
    continued, resumed_summary = machine.run_paged(resumed, steps=6)
    assert resumed_summary["stop"] != "wait"
    assert resumed_summary["residency"]["resident_pages"] > 1
    dense_final, _receipt = machine.run(state, steps=resumed_summary["steps"])
    assert np.array_equal(
        machine.materialise_paged(continued)._field, dense_final._field
    )


def test_paged_activity_selection_matches_dense_and_needs_a_regional_profile() -> None:
    machine = _regional_machine()
    state = machine.initial(
        (
            {"op": "HALT"},
            {"op": "WRITE", "target": "winner", "value": "external", "next": 2},
            {"op": "HALT"},
        ),
        values={"winner": "root"},
    )
    queued, _admission = machine.enqueue_event(state, {"pc": 1, "site": 1})
    baseline, baseline_receipt = machine.step(queued)
    assert machine.named_value(baseline, "winner") == "root"

    paged, _record = machine.paged_state(queued, resident_limit=6)
    modulated, paged_receipt = machine.step_paged(
        paged, activity={2: 1.0}, activity_weight=regions.ACTIVITY_UNIT
    )
    assert paged_receipt["event_id"] != baseline_receipt["event_id"]
    assert machine.materialise_paged(modulated).status == "running"
    dense_modulated, dense_receipt = machine.step(
        queued, activity={2: 1.0}, activity_weight=regions.ACTIVITY_UNIT
    )
    assert dense_receipt["event_id"] == paged_receipt["event_id"]
    assert (
        dense_receipt["activity_modulation"] == paged_receipt["activity_modulation"]
    )
    assert np.array_equal(
        machine.materialise_paged(modulated)._field, dense_modulated._field
    )
    assert machine.named_value(
        machine.materialise_paged(modulated), "winner"
    ) == "external"

    plain = FieldComputer(ComputerProfile(program_capacity=64, stack_capacity=64))
    plain_state = plain.initial(((audit.REF_HALT, 0, 0, 0, 0),))
    with pytest.raises(
        computer_module.FieldComputerError, match="requires a regional computer"
    ):
        plain.step(
            plain_state,
            activity={0: 1.0},
            activity_weight=regions.ACTIVITY_UNIT,
        )
    with pytest.raises(
        computer_module.FieldComputerError, match="requires a regional computer"
    ):
        plain.run(plain_state, activity={0: 1.0})
    with pytest.raises(
        computer_module.FieldComputerError,
        match="paged states require a regional computer profile",
    ):
        plain.paged_state(state)
