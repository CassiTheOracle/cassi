"""Growth past a declared scalar step budget must resume the same task state."""
from __future__ import annotations

from cassi_field_owner import FieldIntelligenceOwner, FieldIntelligenceSurface, RPC_SCHEMA
from cassi_field_program import SCHEMA as STRUCTURED_SCHEMA
from run_cassi_computer import program_arguments

LIMIT = 15
BUDGET = 64
GROWN = 4096


def call(owner, op, action, **arguments):
    return FieldIntelligenceSurface(owner).handle({
        "schema": RPC_SCHEMA, "request_id": op, "operation": "computer",
        "params": {"operation_id": op, "computer_id": "main", "action": action, "arguments": arguments},
    })["result"]


def computer_task(owner):
    return owner.state.computers[0].inspect()["task"]


def counting_document(limit: int) -> dict:
    return {
        "schema": STRUCTURED_SCHEMA,
        "main": [
            {"op": "set_acc", "value": 0},
            {"op": "while_acc", "condition": {"not_equals": int(limit)}, "body": [{"op": "add_acc", "value": 1}]},
            {"op": "push_acc", "stack": "left"},
        ],
    }


def test_step_budget_exhaustion_resumes_after_budget_growth(tmp_path):
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure", profile={"program_capacity": 2048, "stack_capacity": 16, "max_steps": BUDGET})
        call(owner, "load", "load", **program_arguments(counting_document(LIMIT)))
        call(owner, "advance", "advance", steps=BUDGET)
        task = computer_task(owner)
        assert task["status"] == "exhausted"
        assert task["reason"] == "step_budget"
        budgeted = task["transitions"]
        assert budgeted == BUDGET

        # Firing control: repeated advances without growth make no progress, so
        # a resumed task can only come from the declared growth action.
        call(owner, "repeat", "advance", steps=BUDGET)
        task = computer_task(owner)
        assert task["transitions"] == budgeted
        assert task["status"] == "exhausted"

        call(owner, "grow", "grow", stack_capacity=16, max_steps=GROWN)
        task = computer_task(owner)
        assert task["profile"]["max_steps"] == GROWN
        assert task["left"] == []

        call(owner, "finish", "advance", steps=GROWN)
        task = computer_task(owner)
        assert task["status"] == "halted"
        assert task["left"] == [LIMIT]
        assert task["transitions"] > budgeted
