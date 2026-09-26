"""Focused proof for field-owned scalar block derivation and reuse."""
from __future__ import annotations

from cassi_field_computer import ComputerProfile
from cassi_field_owner import (
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
)
from cassi_field_program import (
    _scalar_step,
    compile_structured_program,
    regional_scalar_state,
)
from run_cassi_computer import program_arguments


def _call(owner, operation_id: str, action: str, **arguments):
    response = FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": operation_id,
            "operation": "computer",
            "params": {
                "operation_id": operation_id,
                "computer_id": "scalar",
                "action": action,
                "arguments": arguments,
            },
        }
    )
    return response["result"]


def _structured_program(limit: int) -> dict[str, object]:
    return {
        "schema": "cassifi.structured-field-program.v1",
        "main": [
            {"op": "set_acc", "value": 0},
            {
                "op": "while_acc",
                "condition": {"not_equals": limit},
                "body": [{"op": "add_acc", "value": 1}],
            },
            {"op": "push_acc", "stack": "left"},
        ],
    }


def _plain_scalar_outcome(program_arguments_value):
    compiled = compile_structured_program(_structured_program(63))
    profile = ComputerProfile(
        program_capacity=len(program_arguments_value["program"]) + 4,
        stack_capacity=8,
        max_steps=4096,
    )
    state = regional_scalar_state(compiled, profile)
    while state["status"] == "running":
        state = _scalar_step(state)
    return {
        key: state[key]
        for key in (
            "status",
            "reason",
            "pc",
            "accumulator",
            "left",
            "right",
            "transitions",
        )
    }


def test_public_scalar_block_promotion_preserves_plain_result(tmp_path):
    arguments = program_arguments(_structured_program(63))
    with FieldIntelligenceOwner(tmp_path / "promoted") as owner:
        _call(
            owner,
            "configure",
            "configure",
            profile={
                "program_capacity": len(arguments["program"]) + 4,
                "stack_capacity": 8,
                "max_steps": 4096,
            },
        )
        _call(owner, "load", "load", **arguments)
        run = _call(owner, "advance", "advance", steps=4096)
        task = owner.state.computers[0].inspect()["task"]
        outcome = task["outcome"]
        specialization = run["receipt"]["specialization"]

        observed = {
            key: outcome[key]
            for key in (
                "status",
                "reason",
                "pc",
                "accumulator",
                "left",
                "right",
            )
        }
        observed["transitions"] = outcome["resource_ledger"]["transitions"]
        observed["resource_ledger"] = {
            key: outcome["resource_ledger"][key]
            for key in (
                "transitions",
                "stack_reads",
                "stack_writes",
            )
        }
        expected = _plain_scalar_outcome(arguments)
        expected["resource_ledger"] = dict(observed["resource_ledger"])
        assert observed == expected
        assert specialization["derived_blocks"] == 54
        assert specialization["block_invocations"] == 32
        assert specialization["block_transitions"] == 1024
        assert specialization["scheduler_dispatches_saved"] == 992
        assert specialization["derived_blocks"] >= 1
        assert specialization["block_invocations"] >= 1
        assert specialization["transferable_procedures"] == 0
        assert specialization["derivation_deferred"] is False
        assert specialization["reason"] == "field-procedure-promoted"


def test_public_scalar_nonrepeating_program_does_not_promote(tmp_path):
    program = [
        [1, 0, 7, 1, 0],
        [2, 0, 2, 0, 0],
        [4, 0, 3, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    with FieldIntelligenceOwner(tmp_path / "negative") as owner:
        _call(
            owner,
            "configure",
            "configure",
            profile={"program_capacity": 8, "stack_capacity": 8, "max_steps": 20},
        )
        _call(owner, "load", "load", program=program, entry=0, left=[], right=[])
        run = _call(owner, "advance", "advance", steps=100)
        task = owner.state.computers[0].inspect()["task"]
        outcome = task["outcome"]
        specialization = run["receipt"]["specialization"]
        assert outcome["status"] == "halted"
        assert outcome["accumulator"] == 7
        assert outcome["left"] == [7]
        assert outcome["right"] == []
        assert outcome["resource_ledger"]["transitions"] == 4
        assert specialization["derived_blocks"] == 0
        assert specialization["block_invocations"] == 0
        assert specialization["block_transitions"] == 0
        assert specialization["scheduler_dispatches_saved"] == 0
        assert specialization["transferable_procedures"] == 0
