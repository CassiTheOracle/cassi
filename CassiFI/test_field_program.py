"""Behavioral tests for the deterministic structured field-program frontend."""
from __future__ import annotations

import pytest

from cassi_field_computer import ComputerProfile, FieldComputer
from cassi_field_program import (
    REGIONAL_SOURCE_SCHEMA,
    SCALAR_REGIONAL_KERNEL,
    SCHEMA,
    CompiledFieldProgram,
    FieldProgramError,
    compile_regional_program,
    compile_structured_program,
    regional_scalar_state,
    scalar_regional_kernel,
)
from cassi_field_regions import KernelCatalog, RegionalProfile


def _source() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "constants": {"ONE": 1, "LIMIT": 3},
        "functions": {
            "increment": [{"op": "add_acc", "value": "ONE"}],
        },
        "main": [
            {
                "op": "with_var",
                "name": "limit",
                "value": "LIMIT",
                "body": [
                    {"op": "set_acc", "value": 0},
                    {"op": "repeat", "count": 2, "body": [{"op": "call", "function": "increment"}]},
                    {
                        "op": "if_acc",
                        "condition": {"equals": 2},
                        "then": [{"op": "call", "function": "increment"}],
                        "else": [{"op": "set_acc", "value": 255}],
                    },
                    {
                        "op": "while_acc",
                        "condition": {"not_equals": 5},
                        "body": [{"op": "call", "function": "increment"}],
                    },
                    {"op": "push_acc", "stack": "left"},
                    {"op": "load_var", "name": "limit"},
                ],
            }
        ],
        "left": [],
        "right": [],
        "scratch_stack": "left",
    }


def test_structured_program_executes_functions_flow_arithmetic_and_lexical_variable() -> None:
    compiled = compile_structured_program(_source(), max_instructions=8192)
    assert compiled == compile_structured_program(_source(), max_instructions=8192)
    assert compiled.entry == 0
    assert len(compiled.source_sha256) == 64
    baseline = compile_structured_program(
        _source(),
        max_instructions=8192,
        optimize_known_values=False,
    )
    assert compiled.source_sha256 == baseline.source_sha256
    assert compiled.source_nodes == baseline.source_nodes
    assert len(compiled.program) < len(baseline.program)

    profile = ComputerProfile(
        program_capacity=len(compiled.program) + 8,
        stack_capacity=16,
        max_steps=10_000,
    )
    machine = FieldComputer(profile)
    state = machine.initial(
        compiled.program,
        entry=compiled.entry,
        left=compiled.left,
        right=compiled.right,
    )
    state, receipt = machine.run(state)
    info = machine.inspect(state)

    baseline_machine = FieldComputer(
        ComputerProfile(
            program_capacity=len(baseline.program) + 8,
            stack_capacity=16,
            max_steps=10_000,
        )
    )
    baseline_state, _ = baseline_machine.run(
        baseline_machine.initial(
            baseline.program,
            entry=baseline.entry,
            left=baseline.left,
            right=baseline.right,
        )
    )
    baseline_info = baseline_machine.inspect(baseline_state)
    for key in (
        "status",
        "reason",
        "accumulator",
        "left",
        "right",
    ):
        assert info[key] == baseline_info[key]
    assert receipt["transitions_executed"] > 0
    assert info["status"] == "halted"
    assert tuple(info["left"]) == (5,)
    assert tuple(info["right"]) == ()
    assert info["accumulator"] == 3

def test_lexical_binding_isolated_by_balanced_user_stack_effects_and_nested_scopes() -> None:
    source = {
        "schema": SCHEMA,
        "main": [
            {
                "op": "with_var",
                "name": "outer",
                "value": 7,
                "body": [
                    {"op": "push", "stack": "right", "value": 99},
                    {"op": "pop", "stack": "right"},
                    {
                        "op": "with_var",
                        "name": "inner",
                        "value": 8,
                        "body": [
                            {"op": "load_var", "name": "inner"},
                            {"op": "push_acc", "stack": "left"},
                        ],
                    },
                    {"op": "load_var", "name": "outer"},
                    {"op": "push_acc", "stack": "left"},
                ],
            }
        ],
    }
    compiled = compile_structured_program(source)
    machine = FieldComputer(
        ComputerProfile(
            program_capacity=len(compiled.program) + 2,
            stack_capacity=8,
            max_steps=64,
        )
    )
    state, _ = machine.run(
        machine.initial(compiled.program, left=compiled.left, right=compiled.right)
    )
    info = machine.inspect(state)
    assert info["status"] == "halted"
    assert info["accumulator"] == 7
    assert info["left"] == [8, 7]
    assert info["right"] == []


def test_live_lexical_binding_rejects_burial_boundary_crossing_and_unbalanced_flow() -> None:
    invalid_bodies = (
        [
            {"op": "push", "stack": "right", "value": 99},
            {"op": "load_var", "name": "saved"},
        ],
        [{"op": "pop", "stack": "right"}],
        [
            {
                "op": "if_acc",
                "condition": {"equals": 0},
                "then": [{"op": "push", "stack": "right", "value": 1}],
                "else": [],
            }
        ],
        [
            {
                "op": "while_acc",
                "condition": {"equals": 0},
                "body": [{"op": "push", "stack": "right", "value": 1}],
            }
        ],
    )
    for body in invalid_bodies:
        source = {
            "schema": SCHEMA,
            "main": [
                {
                    "op": "with_var",
                    "name": "saved",
                    "value": 7,
                    "body": body,
                }
            ],
        }
        with pytest.raises(FieldProgramError, match="lexical"):
            compile_structured_program(source)


def test_unknown_byte_addition_wraps_255_to_zero_with_bounded_lowering_cost() -> None:
    source = {
        "schema": SCHEMA,
        "right": [255],
        "main": [
            {"op": "pop", "stack": "right"},
            {"op": "add_acc", "value": 1},
            {"op": "push_acc", "stack": "left"},
        ],
    }
    compiled = compile_structured_program(source)
    assert len(compiled.program) > 500
    machine = FieldComputer(
        ComputerProfile(
            program_capacity=len(compiled.program) + 2,
            stack_capacity=4,
            max_steps=300,
        )
    )
    state, receipt = machine.run(
        machine.initial(compiled.program, left=compiled.left, right=compiled.right)
    )
    info = machine.inspect(state)
    assert info["status"] == "halted"
    assert info["left"] == [0]
    assert receipt["transitions_executed"] <= 261


def test_static_value_folding_matches_same_source_unoptimized_lowering() -> None:
    common = {
        "schema": SCHEMA,
        "functions": {
            "plus_three": [
                {"op": "add_acc", "value": 3}
            ],
        },
        "main": [
            {
                "op": "repeat",
                "count": 2,
                "body": [
                    {
                        "op": "call",
                        "function": "plus_three",
                    }
                ],
            },
            {"op": "sub_acc", "value": 1},
            {
                "op": "if_acc",
                "condition": {"not_equals": 0},
                "then": [{"op": "add_acc", "value": 2}],
                "else": [{"op": "set_acc", "value": 88}],
            },
            {
                "op": "while_acc",
                "condition": {"equals": 0},
                "body": [{"op": "set_acc", "value": 1}],
            },
            {"op": "push_acc", "stack": "left"},
        ],
    }
    static_source = {
        **common,
        "main": [
            {"op": "set_acc", "value": 250},
            *common["main"],
        ],
    }
    optimized = compile_structured_program(static_source)
    baseline = compile_structured_program(
        static_source,
        optimize_known_values=False,
    )
    assert optimized.source_sha256 == baseline.source_sha256
    assert optimized.source_nodes == baseline.source_nodes
    assert len(optimized.program) * 20 < len(baseline.program)

    def execute(
        compiled: CompiledFieldProgram,
    ) -> dict[str, object]:
        program = compiled.program
        machine = FieldComputer(
            ComputerProfile(
                program_capacity=len(program) + 2,
                stack_capacity=8,
                max_steps=5000,
            )
        )
        state, _ = machine.run(
            machine.initial(
                program,
                left=compiled.left,
                right=compiled.right,
            )
        )
        return machine.inspect(state)

    optimized_result = execute(optimized)
    baseline_result = execute(baseline)
    for key in (
        "status",
        "reason",
        "accumulator",
        "left",
        "right",
    ):
        assert optimized_result[key] == baseline_result[key]
    assert optimized_result["accumulator"] == 1
    assert optimized_result["left"] == [1]


def test_constant_condition_discards_unreachable_expensive_lowering() -> None:
    source = {
        "schema": SCHEMA,
        "right": [9],
        "main": [
            {"op": "set_acc", "value": 1},
            {
                "op": "if_acc",
                "condition": {"equals": 1},
                "then": [{"op": "set_acc", "value": 7}],
                "else": [
                    {"op": "pop", "stack": "right"},
                    {"op": "add_acc", "value": 1},
                ],
            },
            {"op": "push_acc", "stack": "left"},
        ],
    }
    compiled = compile_structured_program(
        source,
        max_instructions=16,
    )
    machine = FieldComputer(
        ComputerProfile(
            program_capacity=16,
            stack_capacity=4,
            max_steps=16,
        )
    )
    state, receipt = machine.run(
        machine.initial(
            compiled.program,
            left=compiled.left,
            right=compiled.right,
        )
    )
    info = machine.inspect(state)
    assert receipt["transitions_executed"] == 6
    assert info["status"] == "halted"
    assert info["left"] == [7]
    assert info["right"] == [9]

def test_while_loop_obeys_explicit_machine_step_boundary_and_resumes() -> None:
    source = {
        "schema": SCHEMA,
        "main": [
            {"op": "set_acc", "value": 1},
            {"op": "while_acc", "condition": {"equals": 1}, "body": []},
        ],
    }
    compiled = compile_structured_program(source)
    machine = FieldComputer(ComputerProfile(
        program_capacity=len(compiled.program) + 2,
        stack_capacity=4,
        max_steps=7,
    ))
    state = machine.initial(compiled.program)
    state, receipt = machine.run(state)
    assert receipt["transitions_executed"] == 7
    assert machine.inspect(state)["status"] == "exhausted"


def test_structured_source_rejects_ambiguous_or_unbounded_forms() -> None:
    malformed = [
        {"schema": "wrong", "main": []},
        {"schema": SCHEMA, "main": [{"op": "unknown"}]},
        {"schema": SCHEMA, "main": [{"op": "repeat", "count": 1025, "body": []}]},
        {
            "schema": SCHEMA,
            "functions": {"recurse": [{"op": "call", "function": "recurse"}]},
            "main": [{"op": "call", "function": "recurse"}],
        },
        {
            "schema": SCHEMA,
            "main": [
                {
                    "op": "with_var",
                    "name": "outer",
                    "value": 1,
                    "body": [
                        {
                            "op": "with_var",
                            "name": "inner",
                            "value": 2,
                            "body": [{"op": "load_var", "name": "outer"}],
                        }
                    ],
                }
            ],
        },
        {"schema": SCHEMA, "main": [], "extra": True},
    ]
    for source in malformed:
        with pytest.raises(FieldProgramError):
            compile_structured_program(source)

    with pytest.raises(FieldProgramError, match="max_instructions"):
        compile_structured_program(
            {"schema": SCHEMA, "main": [{"op": "add_acc", "value": 1}]},
            max_instructions=32,
        )


def test_regional_compiler_resolves_labels_and_executes_without_host_callbacks() -> None:
    compiled = compile_regional_program(
        {
            "schema": REGIONAL_SOURCE_SCHEMA,
            "entry": "copy",
            "values": {"source": {"answer": 42}, "target": None},
            "value_capacities": {"target": 16},
            "instructions": [
                {
                    "label": "copy",
                    "op": "COPY",
                    "source": "source",
                    "target": "target",
                    "next": "done",
                },
                {"label": "unreachable", "op": "YIELD", "next": "done"},
                {"label": "done", "op": "HALT"},
            ],
        }
    )
    assert compiled.entry == 0
    assert compiled.program[0]["next"] == 2
    machine = FieldComputer.regional(RegionalProfile())
    state = machine.initial(
        compiled.program,
        entry=compiled.entry,
        values=compiled.values,
        value_capacities=compiled.value_capacities,
    )
    completed, receipt = machine.run(state)
    assert receipt["transitions_executed"] == 2
    assert machine.named_value(completed, "target") == {"answer": 42}


@pytest.mark.parametrize(
    "source",
    (
        {
            "schema": REGIONAL_SOURCE_SCHEMA,
            "instructions": [
                {"label": "same", "op": "HALT"},
                {"label": "same", "op": "HALT"},
            ],
        },
        {
            "schema": REGIONAL_SOURCE_SCHEMA,
            "entry": "missing",
            "instructions": [{"op": "HALT"}],
        },
        {
            "schema": REGIONAL_SOURCE_SCHEMA,
            "values": {},
            "value_capacities": {"missing": 1},
            "instructions": [{"op": "HALT"}],
        },
    ),
)
def test_regional_compiler_rejects_ambiguous_or_unbounded_references(source) -> None:
    with pytest.raises(FieldProgramError):
        compile_regional_program(source)


def test_scalar_continuation_is_retained_and_rescheduled_inside_regional_field(monkeypatch) -> None:
    compiled = compile_structured_program(
        {
            "schema": SCHEMA,
            "main": [
                {"op": "set_acc", "value": 9},
                {"op": "push_acc", "stack": "left"},
            ],
        },
        optimize_known_values=False,
    )
    scalar_profile = ComputerProfile(
        program_capacity=len(compiled.program) + 2,
        stack_capacity=8,
        max_steps=64,
    )
    catalog = KernelCatalog(
        {SCALAR_REGIONAL_KERNEL: scalar_regional_kernel},
        {SCALAR_REGIONAL_KERNEL: 1},
    )
    machine = FieldComputer.regional(
        RegionalProfile(kernel_names=catalog.names),
        catalog=catalog,
    )
    state = machine.initial(
        (
            {
                "op": "NATIVE",
                "kernel": SCALAR_REGIONAL_KERNEL,
                "state": "scalar",
                "output": "outcome",
                "next": 1,
            },
            {"op": "HALT"},
        ),
        values={
            "scalar": regional_scalar_state(compiled, scalar_profile),
            "outcome": None,
        },
    )
    def reject_legacy(*_args, **_kwargs):
        raise AssertionError("regional scalar execution reached the legacy machine")

    monkeypatch.setattr(FieldComputer, "__init__", reject_legacy)
    monkeypatch.setattr(FieldComputer, "from_descriptor", reject_legacy)
    paused, pause_receipt = machine.run(state, steps=1)
    assert pause_receipt["transition_receipts"][0]["disposition"] == "yield"
    retained = machine.named_value(paused, "scalar")
    assert retained["transitions"] == 1
    assert retained["pc"] != compiled.entry
    assert retained["outcome"] is None
    assert machine.named_value(paused, "outcome") is None

    completed, receipt = machine.run(paused)
    assert receipt["status"] == "halted"
    assert machine.named_value(completed, "outcome")["left"] == [9]
    assert machine.named_value(completed, "scalar")["outcome"]["status"] == "halted"
    assert receipt["transitions_executed"] > 1
