"""One field-resident scheduler for heterogeneous programmable continuations.

Each member still has one authoritative ``LearningComputer.field``.  Python,
model, and research-workspace continuations are typed values inside this state;
this fixed scheduler only selects and advances their declared regional kernels.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Callable, Mapping, MutableMapping

from cassi_field_regions import KernelResult
from programs.model.kernel import ModelKernelError, regional_kernel as model_kernel
from programs.model.runtime import (
    RUNTIME_SCHEMA as MODEL_RUNTIME_SCHEMA,
    advance as model_advance,
    computation_view as model_view,
)
from programs.python.kernel import regional_kernel as python_kernel
from programs.python.records import canonical_json_bytes, digest_value
from programs.python.runtime import RUNTIME_SCHEMA as PYTHON_RUNTIME_SCHEMA, computation_view as python_view
from programs.workspace.kernel import regional_kernel as workspace_kernel
from programs.workspace.runtime import RUNTIME_SCHEMA as WORKSPACE_RUNTIME_SCHEMA, inspect as workspace_view


REGIONAL_KERNEL_NAME = "field-program-runtime"
REGIONAL_STATE_SCHEMA = "cassifi.field-program-runtime.v1"
REGIONAL_KERNEL_MAX_WORK = 32
_TASK_SCHEMAS: Mapping[str, tuple[str, Callable[[Any, Mapping[str, Any], int], KernelResult]]] = {
    "python": (PYTHON_RUNTIME_SCHEMA, python_kernel),
    "model": (MODEL_RUNTIME_SCHEMA, model_kernel),
    "workspace": (WORKSPACE_RUNTIME_SCHEMA, workspace_kernel),
}
_TERMINAL = {"completed", "faulted", "cancelled"}

_EVENT_WINDOW = 32
"""Events retained in state after an operation; the operation returns its own.

The host records each operation's events in its own ledger and each task
carries its own events in its projection, so the scheduler's log is a
diagnostic tail rather than a record.  Retaining a whole turn's worth instead
made the log the bulk of the state that every later operation deep-copies,
encodes, and commits -- measured on the real kernel, 256 rows were 48 KB of a
50 KB state and about nine times the per-operation cost of a state without
them.
"""


def _retain_events(state: MutableMapping[str, Any]) -> None:
    retention = min(int(state["limits"]["max_events"]), _EVENT_WINDOW)
    events = state["events"]
    if len(events) > retention:
        del events[: len(events) - retention]


class ProgramRuntimeError(ValueError):
    """A heterogeneous task or scheduler request is invalid."""


def _plain(value: Any) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ProgramRuntimeError("program runtime value is not canonical JSON") from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 512:
        raise ProgramRuntimeError(f"{label} must be bounded nonempty text")
    return value


def _positive(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        raise ProgramRuntimeError(f"{label} is outside its bound")
    return value


def _phase(state: Mapping[str, Any]) -> str:
    phase = str(state.get("phase", "running"))
    if (
        phase != "running"
        or state.get("schema") != "cassifi.field-python-runtime.v1"
    ):
        return phase
    nested = state.get("tasks")
    if not isinstance(nested, Mapping) or not nested:
        return phase
    statuses = {
        str(task.get("status", "running"))
        for task in nested.values()
        if isinstance(task, Mapping)
    }
    if statuses and not statuses.intersection({"ready", "running"}):
        if "waiting" in statuses:
            return "waiting"
    return phase

def _task_status(task: Mapping[str, Any]) -> str:
    phase = _phase(task["state"])
    return {
        "running": "running",
        "active": "ready",
        "paused": "paused",
        "resource-paused": "resource-paused",
        "waiting": "waiting",
        "completed": "completed",
        "faulted": "faulted",
        "cancelled": "cancelled",
    }.get(phase, str(task.get("status", "ready")))


def _event(state: MutableMapping[str, Any], kind: str, payload: Mapping[str, Any]) -> None:
    retained = int(state["limits"]["max_events"])
    if len(state["events"]) >= retained:
        del state["events"][: len(state["events"]) - retained + 1]
    sequence = int(state["counters"]["event"])
    state["counters"]["event"] = sequence + 1
    state["events"].append(
        {
            "schema": "cassifi.field-program-event.v1",
            "sequence": sequence,
            "kind": kind,
            "payload": _plain(payload),
        }
    )


def _validate_substate(kind: str, value: Any) -> Mapping[str, Any]:
    contract = _TASK_SCHEMAS.get(kind)
    if contract is None:
        raise ProgramRuntimeError("program task kind is unsupported")
    if not isinstance(value, Mapping) or value.get("schema") != contract[0]:
        raise ProgramRuntimeError("program task state does not match its kind")
    return _plain(value)


def _submit(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if len(state["tasks"]) >= int(state["limits"]["max_tasks"]):
        raise ProgramRuntimeError("program task limit exhausted")
    task_id = _text(arguments.get("task_id"), "task_id")
    kind = _text(arguments.get("kind"), "kind")
    substate = _validate_substate(kind, arguments.get("state"))
    existing = state["tasks"].get(task_id)
    request_sha256 = digest_value({"kind": kind, "state": substate})
    if existing is not None:
        if existing["request_sha256"] != request_sha256:
            raise ProgramRuntimeError("program task identity conflict")
        return _plain(existing)
    if kind == "model":
        resident = substate.get("resident_model")
        if isinstance(resident, MutableMapping):
            source = resident.get("source_sha256")
            if source:
                retained_policy = state.get("model_policies", {}).get(source)
                if retained_policy is None:
                    retained_policy = _plain(resident.get("policies", {}))
                    retained_policy["graph_sites"] = _plain(resident.get("graph_sites", {}))
                    state.setdefault("model_policies", {})[source] = retained_policy
                resident["policies"] = _plain({
                    key: value for key, value in retained_policy.items() if key != "graph_sites"
                })
                resident.pop("graph_sites", None)
    task = {
        "schema": "cassifi.field-program-task.v1",
        "task_id": task_id,
        "kind": kind,
        "state": substate,
        "status": "ready",
        "request_sha256": request_sha256,
        "created_sequence": int(state["counters"]["task"]),
        "last_output": None,
        "last_work": 0,
        "logical_work": 0,
        "nested_events": [],
    }
    state["counters"]["task"] += 1
    task["status"] = _task_status(task)
    state["tasks"][task_id] = task
    state["queue"].append(task_id)
    state["selected_task_id"] = task_id
    _event(state, "program-task-submitted", {"task_id": task_id, "kind": kind, "status": task["status"]})
    return _task_projection(task)


def _task_projection(task: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "schema": "cassifi.field-program-task-view.v1",
        "task_id": task["task_id"],
        "kind": task["kind"],
        "status": _task_status(task),
        "request_sha256": task["request_sha256"],
        "created_sequence": task["created_sequence"],
        "logical_work": task["logical_work"],
        "last_work": task["last_work"],
        "last_output": _plain(task.get("last_output")),
        "state_sha256": digest_value(task["state"]),
    }


def _select_runnable(state: MutableMapping[str, Any]) -> str | None:
    queue = list(state["queue"])
    if not queue:
        return None
    start = int(state["scheduler_cursor"]) % len(queue)
    for offset in range(len(queue)):
        index = (start + offset) % len(queue)
        task_id = queue[index]
        task = state["tasks"].get(task_id)
        if task is None:
            continue
        if _task_status(task) in {"ready", "running"}:
            state["scheduler_cursor"] = (index + 1) % len(queue)
            return task_id
    return None


def _advance_task(
    state: MutableMapping[str, Any],
    task_id: str,
    *,
    arguments: Mapping[str, Any],
    quantum: int,
    project: bool = True,
) -> tuple[Mapping[str, Any], int, str]:
    task = state["tasks"].get(task_id)
    if not isinstance(task, MutableMapping):
        raise ProgramRuntimeError("program task is unknown")
    kind = str(task["kind"])
    kernel = _TASK_SCHEMAS[kind][1]
    effective_quantum = min(quantum, 1 if kind == "workspace" else 64)
    resident = task["state"].get("resident_model") if kind == "model" else None
    source = resident.get("source_sha256") if isinstance(resident, Mapping) else None
    branch_active = bool(task["state"].get("branch_stack"))
    if isinstance(resident, MutableMapping) and source and (
        (not branch_active and arguments.get("operation") != "commit")
        or (branch_active and "graph_sites" not in resident)
    ):
        retained_policy = state.get("model_policies", {}).get(source)
        if retained_policy is not None:
            if not branch_active:
                resident["policies"] = _plain({
                    key: value for key, value in retained_policy.items() if key != "graph_sites"
                })
            retained_sites = retained_policy.get("graph_sites")
            if isinstance(retained_sites, Mapping):
                resident["graph_sites"] = _plain(retained_sites)
    if kind == "model" and not project:
        # The resident-cycle caller owns this model state. Returning through
        # KernelResult here would canonicalize the whole model state and
        # materialize its field-word image at every stage; the enclosing
        # scheduler/field commit seals the state at its actual boundary.
        if (
            not isinstance(task["state"], Mapping)
            or task["state"].get("schema") != MODEL_RUNTIME_SCHEMA
        ):
            raise ModelKernelError("field model state is invalid")
        if not isinstance(arguments, Mapping):
            raise ModelKernelError("field model arguments must be a mapping")
        if (
            isinstance(effective_quantum, bool)
            or not isinstance(effective_quantum, int)
            or not 1 <= effective_quantum <= 64
        ):
            raise ModelKernelError("field model quantum is outside its bound")
        try:
            (
                model_state,
                result_status,
                result_work,
                result_output,
                result_events,
            ) = model_advance(
                task["state"], dict(arguments), effective_quantum, _owned_state=True
            )
        except ValueError as exc:
            raise ModelKernelError(str(exc)) from exc
        task["state"] = model_state
    else:
        result = kernel(task["state"], dict(arguments), effective_quantum)
        result_status = result.status
        result_work = result.work
        result_output = result.output
        result_events = result.events
        task["state"] = result.state if kind == "model" else _plain(result.state)
    # The private model advance retains its canonical result; other kernels
    # retain defensive normalization.
    successor_resident = task["state"].get("resident_model") if kind == "model" else None
    if (
        source
        and isinstance(successor_resident, MutableMapping)
        and not branch_active
        and not task["state"].get("branch_stack")
        and _phase(task["state"]) != "faulted"
        and isinstance(successor_resident.get("policies"), MutableMapping)
    ):
        retained_policy = dict(successor_resident["policies"])
        retained_policy.pop("graph_sites", None)
        successor_resident["policies"] = retained_policy
        successor_sites = successor_resident.get("graph_sites")
        if isinstance(successor_sites, Mapping):
            # The retained store is a separate record: writing the graph-site
            # block into the same dict that was just published as the task's
            # policies would smuggle the detached sites back into the state.
            retained_policy = {
                **retained_policy,
                "graph_sites": (
                    successor_sites if not project else _plain(successor_sites)
                ),
            }
        # The fast model cycle owns this whole scheduler state until its
        # model-state write. The next dispatch detaches the retained policy
        # above, so a later fault cannot rewrite the last successful one.
        state.setdefault("model_policies", {})[source] = retained_policy
    if (source and isinstance(successor_resident, MutableMapping)
            and not task["state"].get("branch_stack")):
        successor_resident.pop("graph_sites", None)
    task["status"] = _task_status(task)
    task["last_output"] = _plain(result_output)
    task["last_work"] = int(result_work)
    task["logical_work"] = int(task["logical_work"]) + int(result_work)
    task["nested_events"] = [_plain(row) for row in result_events]
    state["selected_task_id"] = task_id
    state["ledger"]["logical_work"] += int(result_work)
    state["ledger"]["dispatches"] += 1
    _event(
        state,
        "program-task-advanced",
        {
            "task_id": task_id,
            "kind": kind,
            "status": task["status"],
            "work": int(result_work),
            "nested_events": len(result_events),
        },
    )
    return (
        _task_projection(task) if project else {"status": task["status"]},
        int(result_work),
        str(result_status),
    )


def task_view(
    state: Mapping[str, Any],
    task_id: str,
    *,
    principal: str | None = None,
    category: str = "objects",
    offset: int = 0,
    limit: int = 64,
) -> Mapping[str, Any]:
    if not isinstance(state, Mapping) or state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise ProgramRuntimeError("program runtime state is invalid")
    task = state["tasks"].get(task_id)
    if not isinstance(task, Mapping):
        raise ProgramRuntimeError("program task is unknown")
    kind = str(task["kind"])
    substate = task["state"]
    if kind == "python":
        return python_view(substate, offset=offset, limit=limit).as_dict()
    if kind == "model":
        return model_view(substate, offset=offset, limit=limit)
    return workspace_view(
        substate,
        principal=principal or str(substate["identity"]["principal"]),
        category=category,
        offset=offset,
        limit=limit,
    )


def _handle(
    state: MutableMapping[str, Any],
    arguments: Mapping[str, Any],
    quantum: int,
) -> tuple[Mapping[str, Any] | None, int, str]:
    operation = arguments.get("operation")
    if operation is None:
        task_id = _select_runnable(state)
        if task_id is None:
            return {"status": "idle"}, 1, "blocked"
        return _advance_task(state, task_id, arguments={}, quantum=quantum)
    if operation == "submit-task":
        return _submit(state, arguments), 1, "yield"
    if operation == "advance-task":
        task_id = _text(arguments.get("task_id"), "task_id")
        nested = arguments.get("arguments", {})
        if not isinstance(nested, Mapping):
            raise ProgramRuntimeError("nested program arguments must be a mapping")
        nested_quantum = _positive(arguments.get("quantum", quantum), "nested quantum")
        return _advance_task(state, task_id, arguments=nested, quantum=nested_quantum)
    if operation == "select-task":
        task_id = _text(arguments.get("task_id"), "task_id")
        if task_id not in state["tasks"]:
            raise ProgramRuntimeError("program task is unknown")
        state["selected_task_id"] = task_id
        return _task_projection(state["tasks"][task_id]), 1, "yield"
    if operation == "inspect-task":
        task_id = _text(arguments.get("task_id"), "task_id")
        return task_view(
            state,
            task_id,
            principal=arguments.get("principal"),
            category=str(arguments.get("category", "objects")),
            offset=int(arguments.get("offset", 0)),
            limit=int(arguments.get("limit", 64)),
        ), 1, "yield"
    if operation == "list-tasks":
        rows = [_task_projection(row) for _, row in sorted(state["tasks"].items(), key=lambda item: int(item[1]["created_sequence"]))]
        return {
            "schema": "cassifi.field-program-task-list.v1",
            "selected_task_id": state.get("selected_task_id"),
            "tasks": rows,
        }, 1, "yield"
    if operation == "fault-task":
        task_id = _text(arguments.get("task_id"), "task_id")
        reason = _text(arguments.get("reason", "stranded continuation"), "reason")
        task = state["tasks"].get(task_id)
        if not isinstance(task, MutableMapping):
            raise ProgramRuntimeError("program task is unknown")
        status = _task_status(task)
        if status in _TERMINAL:
            return {"task_id": task_id, "status": status}, 1, "yield"
        substate = task["state"]
        if not isinstance(substate, MutableMapping):
            raise ProgramRuntimeError("program task state is invalid")
        substate["phase"] = "faulted"
        task["status"] = "faulted"
        _event(state, "program-task-faulted", {"task_id": task_id, "reason": reason})
        return {"task_id": task_id, "status": "faulted"}, 1, "yield"
    if operation == "remove-task":
        task_id = _text(arguments.get("task_id"), "task_id")
        task = state["tasks"].get(task_id)
        if not isinstance(task, Mapping):
            raise ProgramRuntimeError("program task is unknown")
        if _task_status(task) not in _TERMINAL:
            raise ProgramRuntimeError("only a terminal task may be removed")
        del state["tasks"][task_id]
        state["queue"] = [item for item in state["queue"] if item != task_id]
        if state.get("selected_task_id") == task_id:
            state["selected_task_id"] = state["queue"][-1] if state["queue"] else None
        _event(state, "program-task-removed", {"task_id": task_id})
        return {"task_id": task_id, "status": "removed"}, 1, "yield"
    raise ProgramRuntimeError("program runtime operation is unsupported")


def regional_state(
    *,
    owner_id: str,
    member_id: str,
    runtime_id: str,
    max_tasks: int = 256,
    max_events: int = 16_384,
    imported_task: Mapping[str, Any] | None = None,
    imported_kind: str | None = None,
    imported_task_id: str = "imported-task",
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "schema": REGIONAL_STATE_SCHEMA,
        "identity": {
            "owner_id": _text(owner_id, "owner_id"),
            "member_id": _text(member_id, "member_id"),
            "runtime_id": _text(runtime_id, "runtime_id"),
        },
        "tasks": {},
        "model_policies": {},
        "queue": [],
        "selected_task_id": None,
        "scheduler_cursor": 0,
        "events": [],
        "counters": {"event": 1, "task": 1},
        "limits": {
            "max_tasks": _positive(max_tasks, "max_tasks"),
            "max_events": _positive(max_events, "max_events"),
        },
        "ledger": {"logical_work": 0, "dispatches": 0},
    }
    if imported_task is not None:
        if imported_kind is None:
            imported_kind = next((kind for kind, (schema, _) in _TASK_SCHEMAS.items() if imported_task.get("schema") == schema), None)
        if imported_kind is None:
            raise ProgramRuntimeError("imported task schema is unsupported")
        _submit(state, {"task_id": imported_task_id, "kind": imported_kind, "state": imported_task})
    canonical_json_bytes(state)
    return state


def regional_kernel(state: Any, arguments: Mapping[str, Any], quantum: int) -> KernelResult:
    if not isinstance(state, Mapping) or state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise ProgramRuntimeError("field program runtime state is invalid")
    if not isinstance(arguments, Mapping):
        raise ProgramRuntimeError("field program runtime arguments must be a mapping")
    if isinstance(quantum, bool) or not isinstance(quantum, int) or not 1 <= quantum <= REGIONAL_KERNEL_MAX_WORK:
        raise ProgramRuntimeError("field program runtime quantum is outside its bound")
    current = copy.deepcopy(dict(state))
    event_start = len(current["events"])
    output, work, status = _handle(current, arguments, quantum)
    # The task's own events travel in its projection, so retaining a window of
    # the scheduler's log cannot hide them from the caller.
    _retain_events(current)
    canonical_json_bytes(current)
    return KernelResult(
        state=current,
        status=status,
        work=max(1, min(int(work), quantum)),
        output=output,
        events=(),
    )


__all__ = [
    "ProgramRuntimeError",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "regional_kernel",
    "regional_state",
    "task_view",
]
