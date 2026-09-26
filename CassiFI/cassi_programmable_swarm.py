"""Field-owned general computation across independent CassiFI member owners.

Python programs, model inference, research workspaces, branches, effects, and
learned methods remain canonical values inside each member's authoritative
``LearningComputer.field``.  ``ProgrammableSwarm`` coordinates those owners
and optional disposable packed residency without sharing mutable field state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import time
import uuid
from typing import Any, Callable, Mapping, MutableMapping, Sequence

import backend_policy

from cassi_field_runtime import FieldRuntimeError, NativeGroupRow, ResidentFieldRuntime
from cassi_learning_computer import LearningComputer
from programs.model.kernel import (
    REGIONAL_KERNEL_MAX_WORK as MODEL_KERNEL_MAX_WORK,
    REGIONAL_STATE_SCHEMA as MODEL_STATE_SCHEMA,
    regional_state as model_regional_state,
)
from programs.model.records import ModelPackage
from programs.model.runtime import RUNTIME_SCHEMA as MODEL_RUNTIME_SCHEMA, computation_view as model_view
from programs.model.runtime import seed_resident_prefix
from programs.model.runtime import _resident_qwen_graph
from programs.python.compiler import compile_python
from programs.python.kernel import (
    REGIONAL_KERNEL_MAX_WORK as PYTHON_KERNEL_MAX_WORK,
    REGIONAL_STATE_SCHEMA as PYTHON_STATE_SCHEMA,
    regional_state as python_regional_state,
)
from programs.python.records import PythonProgram, canonical_json_bytes
from programs.python.runtime import (
    RUNTIME_SCHEMA as PYTHON_RUNTIME_SCHEMA,
    computation_view,
    optimizer_status as python_optimizer_status,
)
from programs.runtime.kernel import (
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    regional_kernel,
    regional_state,
)
from programs.workspace.kernel import (
    REGIONAL_STATE_SCHEMA as WORKSPACE_STATE_SCHEMA,
    regional_state as workspace_regional_state,
)
from programs.workspace.runtime import RUNTIME_SCHEMA as WORKSPACE_SCHEMA, inspect as workspace_view


CONTRIBUTION_SCHEMA = "cassifi.programmable-contribution.v1"
SWARM_RESULT_SCHEMA = "cassifi.programmable-swarm-result.v1"
TASK_RELEASE_SCHEMA = "cassifi.programmable-swarm-task-release.v1"
TASK_RECLAIM_SCHEMA = "cassifi.programmable-swarm-task-reclaim.v1"
TERMINAL_TASK_STATUSES = frozenset({"completed", "faulted", "cancelled"})
CAPACITY_GROWTH_ATTEMPTS = 3
PROGRAM_COMPUTER_PROFILE: Mapping[str, Any] = {
    "mode_count": 196_608,
    "directory_capacity": 256,
    "max_native_work": 32,
}


class ProgrammableSwarmError(ValueError):
    """A programmable member, contribution, or lifecycle request is invalid."""


def _plain(value: Any) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ProgrammableSwarmError("value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _token_history_digest(tokens: Sequence[int]) -> str:
    """Digest a token history as packed little-endian int32, as native does."""

    digest = hashlib.sha256()
    for token in tokens:
        digest.update(int(token).to_bytes(4, "little", signed=True))
    return digest.hexdigest()



def _runtime_run(result: Any) -> Mapping[str, Any] | None:
    """The field run a runtime invocation reported, wherever the receipt nests it."""

    if not isinstance(result, Mapping):
        return None
    receipt = result.get("receipt")
    run = receipt.get("run") if isinstance(receipt, Mapping) else None
    if run is None:
        run = result.get("run")
    return run if isinstance(run, Mapping) else None


def _runtime_output(result: Any) -> Mapping[str, Any] | None:
    """The output of the last transition one runtime invocation committed."""

    run = _runtime_run(result)
    if not isinstance(run, Mapping):
        return None
    transitions = run.get("transition_receipts")
    if not isinstance(transitions, Sequence) or not transitions:
        return None
    last = transitions[-1]
    if not isinstance(last, Mapping):
        return None
    output = last.get("output")
    return _plain(output) if isinstance(output, Mapping) else None


def _runtime_fault_detail(result: Any) -> str | None:
    """The kernel fault one runtime invocation reported, if it faulted at all."""

    run = _runtime_run(result)
    if not isinstance(run, Mapping) or run.get("reason") != "kernel-fault":
        return None
    transitions = run.get("transition_receipts")
    detail = ""
    if isinstance(transitions, Sequence) and transitions:
        last = transitions[-1]
        if isinstance(last, Mapping):
            detail = str(last.get("fault_detail") or "")
    return detail or "no fault detail"


def _task_summary(task: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "schema": "cassifi.field-program-task-view.v1",
        "task_id": task["task_id"],
        "kind": task["kind"],
        "status": task["status"],
        "request_sha256": task["request_sha256"],
        "created_sequence": task["created_sequence"],
        "logical_work": task["logical_work"],
        "last_work": task["last_work"],
        "last_output": _plain(task.get("last_output")),
        "state_sha256": _digest(task["state"]),
    }


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in value)
    ):
        raise ProgrammableSwarmError(f"{label} must be bounded nonempty text")
    return value




@dataclass(frozen=True, slots=True)
class ProgrammableContribution:
    """Content-bound program or method shared between independent owners."""

    contribution_id: str
    provider_member_id: str
    kind: str
    record: Mapping[str, Any]
    dependencies: tuple[str, ...] = ()
    applicability: Mapping[str, Any] = field(default_factory=dict)
    observed_behavior: Mapping[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()
    sha256: str = ""

    def __post_init__(self) -> None:
        _text(self.contribution_id, "contribution_id")
        _text(self.provider_member_id, "provider_member_id")
        if self.kind not in {
            "python-program",
            "interpreter-program",
            "representation-program",
            "world-program",
            "instrument-program",
            "constructor-program",
            "compiled-method",
            "partial-method",
        }:
            raise ProgrammableSwarmError("contribution kind is unsupported")
        if not isinstance(self.record, Mapping):
            raise ProgrammableSwarmError("contribution record must be a mapping")
        record = _plain(self.record)
        dependencies = tuple(sorted({_text(value, "dependency") for value in self.dependencies}))
        lineage = tuple(_text(value, "lineage") for value in self.lineage)
        applicability = _plain(self.applicability)
        observed = _plain(self.observed_behavior)
        body = {
            "contribution_id": self.contribution_id,
            "provider_member_id": self.provider_member_id,
            "kind": self.kind,
            "record": record,
            "dependencies": list(dependencies),
            "applicability": applicability,
            "observed_behavior": observed,
            "lineage": list(lineage),
        }
        digest = _digest(body)
        if self.sha256 and self.sha256 != digest:
            raise ProgrammableSwarmError("contribution digest mismatch")
        object.__setattr__(self, "record", record)
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "applicability", applicability)
        object.__setattr__(self, "observed_behavior", observed)
        object.__setattr__(self, "lineage", lineage)
        object.__setattr__(self, "sha256", digest)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CONTRIBUTION_SCHEMA,
            "contribution_id": self.contribution_id,
            "provider_member_id": self.provider_member_id,
            "kind": self.kind,
            "record": _plain(self.record),
            "dependencies": list(self.dependencies),
            "applicability": _plain(self.applicability),
            "observed_behavior": _plain(self.observed_behavior),
            "lineage": list(self.lineage),
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProgrammableContribution":
        if not isinstance(value, Mapping) or value.get("schema") != CONTRIBUTION_SCHEMA:
            raise ProgrammableSwarmError("programmable contribution is invalid")
        required = {
            "schema",
            "contribution_id",
            "provider_member_id",
            "kind",
            "record",
            "dependencies",
            "applicability",
            "observed_behavior",
            "lineage",
            "sha256",
        }
        if set(value) != required:
            raise ProgrammableSwarmError("programmable contribution keys are invalid")
        return cls(
            contribution_id=value["contribution_id"],
            provider_member_id=value["provider_member_id"],
            kind=value["kind"],
            record=value["record"],
            dependencies=tuple(value["dependencies"]),
            applicability=value["applicability"],
            observed_behavior=value["observed_behavior"],
            lineage=tuple(value["lineage"]),
            sha256=value["sha256"],
        )


@dataclass(slots=True)
class _Member:
    member_id: str
    owner: Any
    computer_id: str
    runtime: ResidentFieldRuntime | None
    placement: str
    fence: int = 0
    selected_task_id: str | None = None
    workspace_task_id: str | None = None
    candidate_snapshots: MutableMapping[str, tuple[str, str]] = field(default_factory=dict)

class ProgrammableSwarm:
    """Coordinate field computations without merging independent member owners."""

    def __init__(self) -> None:
        self._members: MutableMapping[str, _Member] = {}
        self._model_backings: MutableMapping[str, Mapping[str, Any]] = {}
        self._resident_models: MutableMapping[str, Any] = {}
        self._native_groups: MutableMapping[tuple[int, int], MutableMapping[str, Any]] = {}
        self._native_task_sync: MutableMapping[
            tuple[int, str], MutableMapping[str, Any]
        ] = {}
        self._pending_native_publications: MutableMapping[
            tuple[int, str], MutableMapping[str, Any]
        ] = {}

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._members))

    def bind_model_backing(
        self,
        source_sha256: str,
        path: str,
        *,
        context_size: int = 32_768,
        gpu_layers: int = -1,
    ) -> Mapping[str, Any]:
        if (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise ProgrammableSwarmError("model source identity must be a lowercase SHA-256 digest")
        if not isinstance(path, str) or not path:
            raise ProgrammableSwarmError("model backing path must be nonempty text")
        if isinstance(context_size, bool) or not isinstance(context_size, int) or context_size < 2:
            raise ProgrammableSwarmError("model context size is invalid")
        if isinstance(gpu_layers, bool) or not isinstance(gpu_layers, int) or gpu_layers < -1:
            raise ProgrammableSwarmError("model GPU layer count is invalid")
        binding = {
            "source_sha256": source_sha256,
            "path": path,
            "context_size": context_size,
            "gpu_layers": gpu_layers,
        }
        prior = self._model_backings.get(source_sha256)
        if prior is not None and prior != binding:
            raise ProgrammableSwarmError("model source identity is already bound differently")
        self._model_backings[source_sha256] = binding
        return {
            "status": "bound",
            "source_sha256": source_sha256,
            "context_size": context_size,
            "gpu_layers": gpu_layers,
        }

    def bind_resident_model(
        self, source_sha256: str, executor: Any
    ) -> Mapping[str, Any]:
        if (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise ProgrammableSwarmError("model source identity must be a lowercase SHA-256 digest")
        if not callable(getattr(executor, "execute_stage", None)):
            raise ProgrammableSwarmError("resident model requires a stage executor")
        if getattr(executor, "source_sha256", None) != source_sha256:
            raise ProgrammableSwarmError("resident executor model identity disagrees")
        backend = getattr(executor, "backend", None)
        if not isinstance(backend, str) or not backend:
            raise ProgrammableSwarmError("resident model requires an executor backend identity")
        prior = self._resident_models.get(source_sha256)
        if prior is not None and prior is not executor:
            raise ProgrammableSwarmError("resident model already has an attached executor")
        self._resident_models[source_sha256] = executor
        return {
            "status": "bound",
            "source_sha256": source_sha256,
            "executor": "cassi-resident-qwen",
            "backend": backend,
        }

    def replace_resident_model(
        self, source_sha256: str, old_executor: Any, new_executor: Any,
        *, pending_task: tuple[str, str] | None = None,
    ) -> Mapping[str, Any]:
        """Swap quiescent banks only after the owner's last stage settles.

        A proposed membrane operation may have completed without an
        acknowledgement, so it cannot be transferred or replayed on a new
        backend. The field task and its durable snapshot remain unchanged.
        """
        if self._resident_models.get(source_sha256) is not old_executor:
            raise ProgrammableSwarmError("resident bank changed before replacement")
        if (
            getattr(old_executor, "source_sha256", None) != source_sha256
            or getattr(new_executor, "source_sha256", None) != source_sha256
            or getattr(old_executor, "backend", None) == getattr(new_executor, "backend", None)
            or not callable(getattr(new_executor, "execute_stage", None))
            or not callable(getattr(old_executor, "is_quiescent", None))
            or not callable(getattr(new_executor, "is_quiescent", None))
            or not new_executor.is_quiescent()
            or not old_executor.is_quiescent()
        ):
            raise ProgrammableSwarmError("resident bank replacement requires quiescent compatible banks")
        retained = False
        for member_id in self._members:
            for task_id, task in self._runtime_state(member_id)["tasks"].items():
                state = task.get("state")
                resident = state.get("resident_model") if isinstance(state, Mapping) else None
                if (
                    task.get("kind") != "model"
                    or not isinstance(resident, Mapping)
                    or resident.get("source_sha256") != source_sha256
                ):
                    continue
                if pending_task != (member_id, task_id) or retained:
                    raise ProgrammableSwarmError("resident model tasks must be reclaimed before bank replacement")
                retained = True
                request_state = state.get("request")
                if not isinstance(request_state, Mapping) or request_state.get("visual_embedding_id") is not None:
                    raise ProgrammableSwarmError("visual resident tasks cannot migrate banks")
                operations = state.get("operations")
                if (
                    state.get("phase") != "running"
                    or not isinstance(operations, Mapping)
                    or any(
                        isinstance(operation, Mapping) and operation.get("phase") == "proposed"
                        for operation in operations.values()
                    )
                ):
                    raise ProgrammableSwarmError("resident task has no settled stage boundary")
                snapshot = resident.get("snapshot")
                if (
                    not isinstance(snapshot, Mapping)
                    or snapshot.get("schema") != "cassifi.resident-model-snapshot-descriptor.v1"
                ):
                    raise ProgrammableSwarmError("resident stage lacks a matching durable snapshot")
                loader = getattr(new_executor, "_load_state", None)
                if not callable(loader):
                    raise ProgrammableSwarmError("successor cannot read resident snapshot")
                try:
                    _, metadata = loader({"snapshot": snapshot})
                except Exception as exc:
                    raise ProgrammableSwarmError("successor cannot restore resident snapshot") from exc
                position = resident.get("position")
                if (
                    metadata.get("source_sha256") != source_sha256
                    or metadata.get("architecture") != getattr(new_executor, "architecture", None)
                    or metadata.get("backend") not in {old_executor.backend, new_executor.backend}
                    or isinstance(position, bool)
                    or not isinstance(position, int)
                    or isinstance(metadata.get("position"), bool)
                    or not isinstance(metadata.get("position"), int)
                    or metadata["position"] > position
                ):
                    raise ProgrammableSwarmError("resident snapshot identity or position differs")
        if pending_task is not None and not retained:
            raise ProgrammableSwarmError("resident stage task is no longer pending")
        self._resident_models[source_sha256] = new_executor
        return {
            "status": "replaced",
            "source_sha256": source_sha256,
            "backend": new_executor.backend,
            "pending_task": None if pending_task is None else pending_task[1],
        }

    def unbind_resident_model(self, source_sha256: str) -> None:
        self._resident_models.pop(source_sha256, None)

    def add_member(
        self,
        member_id: str,
        owner: Any,
        *,
        computer_id: str | None = None,
        runtime: ResidentFieldRuntime | None = None,
        placement: str = "native-cpu",
    ) -> None:
        member_id = _text(member_id, "member_id")
        if member_id in self._members:
            raise ProgrammableSwarmError("member already exists")
        if not callable(getattr(owner, "operate_computer", None)):
            raise ProgrammableSwarmError("member owner lacks operate_computer")
        if placement not in {"logical-cpu", "native-cpu", "vulkan"}:
            raise ProgrammableSwarmError("member placement is invalid")
        if runtime is not None:
            native_owner = getattr(owner, "raw_owner", owner)
            bind_runtime = getattr(native_owner, "bind_regional_runtime", None)
            if callable(bind_runtime):
                bind_runtime(
                    computer_id or f"python-{member_id}", runtime, member_id,
                    "native-cpu" if placement == "logical-cpu" else placement,
                )
        self._members[member_id] = _Member(
            member_id=member_id,
            owner=owner,
            computer_id=computer_id or f"python-{member_id}",
            runtime=runtime,
            placement=placement,
        )

    def remove_member(self, member_id: str) -> None:
        member = self._member(member_id)
        computer = self._computer(member)
        runtime_state = None if computer is None else computer.inspect().get("task")
        self._release_native_seats(
            lambda entry: entry["member_id"] == member_id, "member removal"
        )
        if member.runtime is not None:
            if (
                isinstance(runtime_state, Mapping)
                and runtime_state.get("schema") == REGIONAL_STATE_SCHEMA
            ):
                for task_id, task in runtime_state.get("tasks", {}).items():
                    if isinstance(task, Mapping) and task.get("kind") == "model":
                        self._drop_native_model_tasks(member_id, str(task_id))
            member.runtime.detach(member.member_id)
        native_owner = getattr(member.owner, "raw_owner", member.owner)
        unbind_runtime = getattr(native_owner, "unbind_regional_runtime", None)
        if callable(unbind_runtime):
            unbind_runtime(member.computer_id, member_id)
        del self._members[member_id]

    def _member(self, member_id: str) -> _Member:
        try:
            return self._members[member_id]
        except KeyError as exc:
            raise ProgrammableSwarmError("unknown programmable member") from exc

    @staticmethod
    def _operation_id(member: _Member, verb: str) -> str:
        return f"swarm-{member.member_id}-{verb}-{uuid.uuid4().hex}"

    @staticmethod
    def _computer(member: _Member) -> LearningComputer | None:
        owner = member.owner
        state = getattr(owner, "state", None)
        if state is None:
            raw_owner = getattr(owner, "raw_owner", None)
            state = getattr(raw_owner, "state", None)
        computers = getattr(state, "computers", ())
        return next(
            (row for row in computers if row.computer_id == member.computer_id),
            None,
        )

    def resident_field_state_sha256(self, member_id: str) -> str:
        """Read the complete owner epoch used to reject unrelated field edits."""

        member = self._member(member_id)
        owner_state = getattr(member.owner, "state", None)
        if owner_state is None:
            raw_owner = getattr(member.owner, "raw_owner", None)
            owner_state = getattr(raw_owner, "state", None)
        state_sha256 = getattr(owner_state, "state_sha256", None)
        if (
            not isinstance(state_sha256, str)
            or len(state_sha256) != 64
            or any(character not in "0123456789abcdef" for character in state_sha256)
        ):
            raise ProgrammableSwarmError("member field epoch has no exact state identity")
        return state_sha256

    def ensure_computer(
        self,
        member_id: str,
        *,
        profile: Mapping[str, Any] | None = None,
        resource_limits: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Install the member's computer under the caller's declared policy.

        A member's computer is where staged work runs, so the floor that
        opened the member has to reach it: a computer left on the default
        policy stages a resident model under a placeholder share while the
        field's own declaration sits unused.
        """

        member = self._member(member_id)
        existing = self._computer(member)
        if existing is not None:
            if resource_limits is None:
                return existing.inspect()
            # A declaration made after the computer exists still lands: the
            # resources action is the durable policy path for a live computer.
            return member.owner.operate_computer(
                self._operation_id(member, "resources"),
                computer_id=member.computer_id,
                action="resources",
                arguments={"limits": dict(resource_limits)},
            )
        arguments: dict[str, Any] = {
            "profile": dict(PROGRAM_COMPUTER_PROFILE if profile is None else profile),
        }
        if resource_limits is not None:
            arguments["resource_limits"] = dict(resource_limits)
        return member.owner.operate_computer(
            self._operation_id(member, "configure"),
            computer_id=member.computer_id,
            action="configure",
            arguments=arguments,
        )

    def ensure_program_runtime(
        self,
        member_id: str,
        *,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Install the heterogeneous field scheduler, preserving any direct task."""

        member = self._member(member_id)
        computer = self._computer(member)
        if computer is None:
            # ``ensure_computer`` only renders the existing computer when one is
            # already installed, so skip the call in that common case.
            self.ensure_computer(member_id)
            computer = self._computer(member)
        if computer is None:
            raise ProgrammableSwarmError("member computer is not configured")
        resident = (
            _runtime_state_snapshot
            if _runtime_state_snapshot is not None
            else computer.named_value("task")
        )
        if isinstance(resident, Mapping) and resident.get("schema") == REGIONAL_STATE_SCHEMA:
            return _plain(resident)
        state = regional_state(
            owner_id=member.computer_id,
            member_id=member.member_id,
            runtime_id=f"runtime:{member.computer_id}",
        )
        legacy_kind = None
        if isinstance(resident, Mapping):
            legacy_kind = {
                PYTHON_STATE_SCHEMA: "python",
                MODEL_STATE_SCHEMA: "model",
                WORKSPACE_STATE_SCHEMA: "workspace",
            }.get(resident.get("schema"))
        if legacy_kind is not None:
            task_id = f"imported-{_digest(resident)[:16]}"
            state = regional_kernel(
                state,
                {
                    "operation": "submit-task",
                    "task_id": task_id,
                    "kind": legacy_kind,
                    "state": resident,
                },
                1,
            ).state
            member.selected_task_id = task_id
            if legacy_kind == "workspace":
                member.workspace_task_id = task_id
        elif isinstance(resident, Mapping) and resident.get("status") != "idle":
            raise ProgrammableSwarmError(
                "member computer contains a non-program regional task"
            )
        member.owner.operate_computer(
            self._operation_id(member, "runtime"),
            computer_id=member.computer_id,
            action="submit",
            arguments={
                "kernel": REGIONAL_KERNEL_NAME,
                "state": state,
                "kind": "field-program-runtime",
                "arguments": {"operation": "list-tasks"},
                "steps": 1,
            },
        )
        if member.runtime is not None:
            self.refresh_residency(member_id)
        return self.raw_runtime_state(member_id)

    def _has_program_runtime(self, member_id: str) -> bool:
        """Whether the member's computer already carries the field scheduler."""

        member = self._member(member_id)
        computer = self._computer(member)
        if computer is None:
            return False
        resident = computer.named_value("task")
        return bool(
            isinstance(resident, Mapping) and resident.get("schema") == REGIONAL_STATE_SCHEMA
        )

    def _runtime_state(self, member_id: str) -> Mapping[str, Any]:
        member = self._member(member_id)
        computer = self._computer(member)
        if computer is None:
            raise ProgrammableSwarmError("member computer is not configured")
        # ``inspect`` also renders and digests the session and policy records.
        # Every step needs only the runtime task, so read the named value.
        task = computer.named_value("task")
        if not isinstance(task, Mapping) or task.get("schema") != REGIONAL_STATE_SCHEMA:
            raise ProgrammableSwarmError("member has no field program runtime")
        return task

    def raw_runtime_state(self, member_id: str) -> Mapping[str, Any]:
        """Expose the authoritative resident scheduler state to integrations."""

        return self._runtime_state(member_id)

    def _invoke_runtime(
        self,
        member_id: str,
        arguments: Mapping[str, Any],
        *,
        _ensure_runtime: bool = True,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        if _ensure_runtime and not self._has_program_runtime(member_id):
            self.ensure_program_runtime(member_id)
        result = self._runtime_invocation(member_id, arguments)
        for _attempt in range(CAPACITY_GROWTH_ATTEMPTS):
            detail = _runtime_fault_detail(result)
            if detail is None:
                break
            if "exceeds allocated capacity" not in detail:
                break
            if self._grow_computer_capacity(member_id) is None:
                break
            result = self._runtime_invocation(member_id, arguments)
        if member.runtime is not None:
            self.refresh_residency(member_id)
        detail = _runtime_fault_detail(result)
        if detail is not None:
            # The runtime kernel faulted, so the requested operation never took
            # effect.  Report the fault where it happened instead of leaving a
            # later lookup to fail with a misleading unknown-task error.
            raise ProgrammableSwarmError("field program kernel faulted: " + detail)
        return result

    def _runtime_invocation(
        self,
        member_id: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        return member.owner.operate_computer(
            self._operation_id(member, "runtime-invoke"),
            computer_id=member.computer_id,
            action="invoke",
            arguments={"arguments": _plain(arguments), "steps": 1},
        )

    def _grow_computer_capacity(self, member_id: str) -> int | None:
        """Grow the program computer after a regional capacity fault.

        A continuation keeps its whole state inside one runtime region, and that
        region is sized from the computer's profile.  A continuation that grows
        past that size faults the kernel, and the regional implementation's own
        remedy is growth: the field is re-laid into a larger allocation with its
        header, regions and records copied.  The owner's action takes the
        regional stack capacity, which is the computer's mode count.  Growth is
        refused, not raised, when the workspace budget is already met, so the
        caller reports the fault it started with.
        """

        member = self._member(member_id)
        computer = self._computer(member)
        if computer is None:
            return None
        current = int(computer.profile.mode_count)
        target = current + max(65_536, current // 2)
        # Growth must fit the owner's persisted per-computer policy and any
        # tighter residency-manager policy visible on a paged computer.
        authorized_limits: list[int] = []
        owner = member.owner
        policy_reader = getattr(owner, "resource_limits", None)
        if callable(policy_reader):
            owner_limits = policy_reader(member.computer_id)
        else:
            owner_limits = policy_reader
        raw_owner = getattr(owner, "raw_owner", None)
        if owner_limits is None and raw_owner is not None:
            raw_policy_reader = getattr(raw_owner, "resource_limits", None)
            owner_limits = (
                raw_policy_reader(member.computer_id)
                if callable(raw_policy_reader)
                else raw_policy_reader
            )
        if owner_limits is None:
            owner_limits = getattr(owner, "limits", None)
        if owner_limits is None:
            owner_limits = getattr(raw_owner, "limits", None)
        owner_ceiling = int(
            (
                owner_limits.get("max_logical_bytes", 0)
                if isinstance(owner_limits, Mapping)
                else getattr(owner_limits, "max_logical_bytes", 0)
            )
            or 0
        )
        if owner_ceiling > 0:
            authorized_limits.append(owner_ceiling)
        resource_reader = getattr(computer, "resources", None)
        resource_report = resource_reader() if callable(resource_reader) else None
        computer_limits = (
            resource_report.get("limits")
            if isinstance(resource_report, Mapping)
            else None
        )
        computer_ceiling = (
            int(computer_limits.get("max_logical_bytes", 0) or 0)
            if isinstance(computer_limits, Mapping)
            else 0
        )
        if computer_ceiling > 0:
            authorized_limits.append(computer_ceiling)
        ceiling = min(authorized_limits) if authorized_limits else int(computer.nbytes)
        bytes_per_mode = max(1, int(computer.nbytes) // max(1, current))
        target = min(target, max(1, ceiling // bytes_per_mode))
        if target <= current:
            # The authorized byte ceiling cannot admit another mode, but the
            # existing regions may still need a same-size relayout.
            before = member.owner.state.state_sha256
            member.owner.operate_computer(
                self._operation_id(member, f"computer-relocate:{before}"),
                computer_id=member.computer_id,
                action="grow",
                arguments={
                    "stack_capacity": current,
                    "relocate_regions": True,
                },
                expected_state_sha256=before,
            )
            return current
        before = member.owner.state.state_sha256
        member.owner.operate_computer(
            self._operation_id(member, f"computer-grow:{before}"),
            computer_id=member.computer_id,
            action="grow",
            arguments={"stack_capacity": target},
            expected_state_sha256=before,
        )
        grown = self._computer(member)
        if grown is None or int(grown.profile.mode_count) != target:
            raise ProgrammableSwarmError("program computer growth was not committed")
        if int(grown.nbytes) > ceiling:
            raise ProgrammableSwarmError(
                "grown program computer exceeds its authorized logical-byte limit"
            )
        return target

    def _submit_task(
        self,
        member_id: str,
        *,
        task_id: str,
        kind: str,
        state: Mapping[str, Any],
        steps: int,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        task_id = _text(task_id, "task_id")
        submitted = self._invoke_runtime(
            member_id,
            {
                "operation": "submit-task",
                "task_id": task_id,
                "kind": kind,
                "state": state,
            },
        )
        member.selected_task_id = task_id
        advanced = None
        if steps:
            advanced = self.step(member_id, task_id=task_id, steps=steps)
        return {
            "schema": SWARM_RESULT_SCHEMA,
            "task_id": task_id,
            "kind": kind,
            "submitted": submitted,
            "advanced": advanced,
            "view": self.inspect(member_id, task_id=task_id),
        }

    def start_python(
        self,
        member_id: str,
        source: str | PythonProgram | Mapping[str, Any],
        *,
        mode: str = "exec",
        module: str = "__main__",
        package: str | None = None,
        filename: str = "<field>",
        inputs: Mapping[str, Any] | None = None,
        capabilities: Sequence[str] = (),
        limits: Mapping[str, int] | None = None,
        module_sources: Mapping[str, Mapping[str, Any]] | None = None,
        placement: str | None = None,
        steps: int = 1,
        lineage_id: str | None = None,
        operation_id: str | None = None,
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        guest_operation_id = operation_id or self._operation_id(member, "python")
        from cassi_regional_catalog import STANDARD_KERNEL_CATALOG

        state = python_regional_state(
            source,
            mode=mode,
            module=module,
            package=package,
            filename=filename,
            inputs=inputs,
            owner_id=member.computer_id,
            member_id=member.member_id,
            lineage_id=lineage_id or guest_operation_id,
            operation_id=guest_operation_id,
            capabilities=capabilities,
            limits=limits,
            module_sources=module_sources,
            backend_policy=placement or member.placement,
            regional_catalog_sha256=STANDARD_KERNEL_CATALOG.fingerprint,
        )
        return self._submit_task(
            member_id,
            task_id=task_id or guest_operation_id,
            kind="python",
            state=state,
            steps=steps,
        )

    def start_model(
        self,
        member_id: str,
        package: ModelPackage | Mapping[str, Any],
        *,
        prompt_tokens: Sequence[int],
        max_new_tokens: int = 1,
        stop_tokens: Sequence[int] = (),
        sampler: Mapping[str, Any] | None = None,
        output_tensors: Sequence[str] = (),
        limits: Mapping[str, int] | None = None,
        placement: str | None = None,
        resident_prefix: Mapping[str, Any] | None = None,
        rng_seed: int = 1,
        graph_site_modes: Mapping[str, str] | None = None,
        steps: int = 1,
        lineage_id: str | None = None,
        operation_id: str | None = None,
        task_id: str | None = None,
        visual_embedding_id: str | None = None,
        visual_embedding_positions: Mapping[str, int] | None = None,
        visual_rope_positions: Mapping[str, Sequence[int]] | None = None,
        visual_image_grid: Sequence[int] | None = None,
        visual_placeholder_token_id: int | None = None,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        guest_operation_id = operation_id or self._operation_id(member, "model")
        model_task_id = task_id or guest_operation_id
        state = model_regional_state(
            package,
            prompt_tokens=prompt_tokens,
            owner_id=member.computer_id,
            member_id=member.member_id,
            lineage_id=lineage_id or guest_operation_id,
            operation_id=guest_operation_id,
            max_new_tokens=max_new_tokens,
            stop_tokens=stop_tokens,
            sampler=sampler,
            output_tensors=output_tensors,
            limits=limits,
            backend_policy=placement or member.placement,
            rng_seed=rng_seed,
            graph_site_modes=graph_site_modes,
        )
        has_visual_metadata = any(
            value is not None
            for value in (
                visual_embedding_id,
                visual_embedding_positions,
                visual_rope_positions,
                visual_image_grid,
                visual_placeholder_token_id,
            )
        )
        if has_visual_metadata:
            if (
                not _resident_qwen_graph(state)
                or not isinstance(visual_embedding_id, str)
                or not visual_embedding_id
                or len(visual_embedding_id) > 128
                or not isinstance(visual_embedding_positions, Mapping)
                or not visual_embedding_positions
                or not isinstance(visual_rope_positions, Mapping)
                or set(visual_rope_positions) != set(visual_embedding_positions)
                or not isinstance(visual_image_grid, Sequence)
                or isinstance(visual_image_grid, (str, bytes))
                or len(visual_image_grid) != 2
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 1
                    for value in visual_image_grid
                )
                or visual_image_grid[0] * visual_image_grid[1]
                != len(visual_embedding_positions)
                or len(visual_embedding_positions) > 512
                or isinstance(visual_placeholder_token_id, bool)
                or not isinstance(visual_placeholder_token_id, int)
                or visual_placeholder_token_id < 0
                or resident_prefix is not None
            ):
                raise ProgrammableSwarmError(
                    "visual image placeholders require a cold resident Qwen graph"
                )
            grid_rows, grid_columns = visual_image_grid
            normalized_positions: dict[str, int] = {}
            normalized_axes: dict[str, list[int]] = {}
            row_indices: set[int] = set()
            image_start: int | None = None
            for raw_position, raw_index in visual_embedding_positions.items():
                if (
                    not isinstance(raw_position, str)
                    or not raw_position.isdecimal()
                    or str(int(raw_position)) != raw_position
                    or isinstance(raw_index, bool)
                    or not isinstance(raw_index, int)
                    or raw_index < 0
                    or raw_position in normalized_positions
                ):
                    raise ProgrammableSwarmError(
                        "visual image placeholder mapping is invalid"
                    )
                position = int(raw_position)
                axes = visual_rope_positions[raw_position]
                if (
                    position >= len(prompt_tokens)
                    or int(prompt_tokens[position]) != visual_placeholder_token_id
                    or raw_index in row_indices
                    or not isinstance(axes, Sequence)
                    or isinstance(axes, (str, bytes))
                    or len(axes) != 4
                    or any(
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or value < 0
                        for value in axes
                    )
                    or (image_start is not None and axes[0] != image_start)
                    or position != axes[0] + raw_index
                    or list(axes)
                    != [
                        axes[0],
                        axes[0] + raw_index // grid_columns,
                        axes[0] + raw_index % grid_columns,
                        0,
                    ]
                ):
                    raise ProgrammableSwarmError(
                        "visual image placeholder mapping does not match prompt tokens or grid"
                    )
                normalized_positions[raw_position] = raw_index
                normalized_axes[raw_position] = list(axes)
                image_start = axes[0]
                row_indices.add(raw_index)
            if row_indices != set(range(len(row_indices))):
                raise ProgrammableSwarmError(
                    "visual image embedding rows are not a contiguous sequence"
                )
            assert image_start is not None
            state["request"]["visual_embedding_id"] = visual_embedding_id
            state["request"]["visual_embedding_positions"] = normalized_positions
            state["request"]["visual_rope_positions"] = normalized_axes
            state["request"]["visual_image_grid"] = [
                grid_rows,
                grid_columns,
            ]
            state["request"]["visual_image_start"] = image_start
            state["request"]["visual_rope_delta"] = (
                len(normalized_positions) - max(grid_rows, grid_columns)
            )
            state["request"]["visual_placeholder_token_id"] = (
                visual_placeholder_token_id
            )
        existing_task = None
        try:
            existing_task = self._runtime_state(member_id)["tasks"].get(model_task_id)
        except ProgrammableSwarmError:
            pass
        existing_state = (
            existing_task.get("state")
            if isinstance(existing_task, Mapping)
            and existing_task.get("kind") == "model"
            else None
        )
        existing_request = (
            existing_state.get("request")
            if isinstance(existing_state, Mapping)
            else None
        )
        existing_prefix = (
            existing_request.get("prefix_reuse")
            if isinstance(existing_request, Mapping)
            else None
        )
        if isinstance(existing_task, Mapping):
            # A pending task's original cache seed is part of its immutable
            # request identity. Rebuild that same seed even though its live
            # field epoch has since advanced through the pending task.
            if isinstance(existing_prefix, Mapping):
                if not seed_resident_prefix(state, existing_prefix):
                    raise ProgrammableSwarmError(
                        "pending resident prefix request could not be reconstructed"
                    )
            # Existing cold requests stay cold on retry; never change their
            # request identity because a cache became available later.
        elif isinstance(resident_prefix, Mapping):
            expected_epoch = resident_prefix.get("field_epoch_sha256")
            try:
                current_epoch = self.resident_field_state_sha256(member_id)
            except Exception:
                current_epoch = None
            if current_epoch == expected_epoch:
                graph = state["package"]["graph"]
                terminal = (
                    graph[-2]
                    if len(graph) >= 2 and graph[-1].get("op") == "qwen-head"
                    else None
                )
                resident_state = state.get("resident_model")
                source = (
                    resident_state.get("source_sha256")
                    if isinstance(resident_state, Mapping)
                    else None
                )
                executor = self._resident_models.get(source)
                loader = getattr(executor, "_load_state", None)
                snapshot = resident_prefix.get("snapshot")
                if (
                    terminal is not None
                    and callable(loader)
                    and isinstance(snapshot, Mapping)
                    and resident_prefix.get("backend") == getattr(executor, "backend", None)
                ):
                    try:
                        _, metadata = loader({"snapshot": snapshot})
                    except Exception:
                        metadata = None
                    if (
                        isinstance(metadata, Mapping)
                        and metadata.get("source_sha256") == source
                        and metadata.get("architecture") == getattr(executor, "architecture", None)
                        and metadata.get("backend") in {"cpu", "vulkan"}
                        and metadata.get("stage") == terminal.get("stage")
                        and metadata.get("layer") == terminal.get("parameters", {}).get("layer")
                        and metadata.get("position") == resident_prefix.get("position")
                        and metadata.get("token") == resident_prefix.get("token")
                    ):
                        seed_resident_prefix(state, resident_prefix)
        return self._submit_task(
            member_id,
            task_id=model_task_id,
            kind="model",
            state=state,
            steps=steps,
        )

    def execute_resident_visual_stage(
        self,
        member_id: str,
        request: Mapping[str, Any],
        *,
        image_png: bytes,
    ) -> Mapping[str, Any]:
        """Run a transient Qwen projector stage under the member's owner field."""

        if not isinstance(request, Mapping) or not isinstance(image_png, bytes):
            raise ProgrammableSwarmError(
                "resident visual stage requires a canonical request and PNG bytes"
            )
        member = self._member(member_id)
        source_sha256 = request.get("source_sha256")
        executor = (
            self._resident_models.get(source_sha256)
            if isinstance(source_sha256, str)
            else None
        )
        execute_stage = getattr(
            member.owner, "execute_resident_model_stage", None
        )
        if executor is None or not callable(execute_stage):
            raise ProgrammableSwarmError(
                "member owner has no bound resident Qwen visual stage"
            )
        resident_operation_id = request.get("operation_id")
        if not isinstance(resident_operation_id, str) or not resident_operation_id:
            raise ProgrammableSwarmError(
                "resident visual request has no operation identity"
            )
        return execute_stage(
            f"swarm-{member.member_id}-visual-{resident_operation_id[:48]}",
            computer_id=member.computer_id,
            task_id=f"resident-qwen-visual:{resident_operation_id[:48]}",
            resident_operation_id=resident_operation_id,
            request=request,
            executor=executor,
            resume_task=False,
            transient_payload=image_png,
        )
    def start_workspace(
        self,
        member_id: str,
        *,
        workspace_id: str = "research",
        principal: str | None = None,
        limits: Mapping[str, int] | None = None,
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        workspace_id = _text(workspace_id, "workspace_id")
        task_id = task_id or f"workspace:{workspace_id}"
        state = workspace_regional_state(
            owner_id=member.computer_id,
            member_id=member.member_id,
            workspace_id=workspace_id,
            principal=principal or member.member_id,
            limits=limits,
        )
        result = self._submit_task(
            member_id,
            task_id=task_id,
            kind="workspace",
            state=state,
            steps=0,
        )
        member.workspace_task_id = task_id
        return result

    def select_task(self, member_id: str, task_id: str) -> Mapping[str, Any]:
        member = self._member(member_id)
        task_id = _text(task_id, "task_id")
        result = self._invoke_runtime(
            member_id, {"operation": "select-task", "task_id": task_id}
        )
        member.selected_task_id = task_id
        return result

    def list_tasks(self, member_id: str) -> Sequence[Mapping[str, Any]]:
        state = self._runtime_state(member_id)
        return tuple(_task_summary(state["tasks"][task_id]) for task_id in sorted(state["tasks"]))

    def reclaim_stranded_tasks(
        self,
        member_id: str,
        *,
        reason: str = "stranded continuation",
    ) -> Mapping[str, Any]:
        """Fault and release tasks whose owning continuation is gone.

        A field program task holds its whole continuation inside the bounded
        runtime task region, and only the process that submitted it can advance
        it.  A task left behind by an ended process can therefore never finish,
        yet it keeps its share of the region until it is terminal and removed,
        and once the region is full no new task can start at all.  Every task
        except the member's own workspace is reclaimed here, which is what a
        restart needs before it can submit work again.
        """

        member = self._member(member_id)
        reason = _text(reason, "reason")
        state = self._runtime_state(member_id)
        stranded = [
            task_id
            for task_id, task in sorted(state["tasks"].items())
            if str(task.get("kind")) != "workspace"
            and str(task.get("status")) not in TERMINAL_TASK_STATUSES
        ]
        reclaimed: list[dict[str, Any]] = []
        for task_id in stranded:
            native_cleanup = list(self._drop_native_model_tasks(member_id, task_id))
            faulted = self._invoke_runtime(
                member_id,
                {"operation": "fault-task", "task_id": task_id, "reason": reason},
            )
            removal = self._invoke_runtime(
                member_id, {"operation": "remove-task", "task_id": task_id}
            )
            if member.selected_task_id == task_id:
                member.selected_task_id = None
            if member.workspace_task_id == task_id:
                member.workspace_task_id = None
            reclaimed.append(
                {
                    "task_id": task_id,
                    "kind": str(state["tasks"][task_id].get("kind")),
                    "status": (_runtime_output(faulted) or {}).get("status"),
                    "native_cleanup": native_cleanup,
                    "removal": _runtime_output(removal),
                }
            )
        return {
            "schema": TASK_RECLAIM_SCHEMA,
            "reason": reason,
            "reclaimed": reclaimed,
            "retained": sorted(
                task_id
                for task_id in self._runtime_state(member_id)["tasks"]
            ),
        }

    def release_task(self, member_id: str, task_id: str) -> Mapping[str, Any]:
        """Release one field program task and reclaim its runtime region.

        A continuation keeps its whole state resident in the runtime task region
        until it is removed, and that region is bounded.  A long-lived member
        therefore releases each continuation it no longer needs instead of
        accumulating one task per operation.
        """

        member = self._member(member_id)
        selected = _text(task_id, "task_id")
        state = self._runtime_state(member_id)
        task = state["tasks"].get(selected)
        if not isinstance(task, Mapping):
            return {
                "schema": TASK_RELEASE_SCHEMA,
                "task_id": selected,
                "status": "absent",
                "cancelled": False,
                "native_cleanup": [],
            }
        native_cleanup = list(self._drop_native_model_tasks(member_id, selected))
        cancelled = False
        if str(task.get("status")) not in TERMINAL_TASK_STATUSES:
            cancelled = True
            try:
                self._invoke_runtime(
                    member_id,
                    {
                        "operation": "advance-task",
                        "task_id": selected,
                        "arguments": {"operation": "cancel"},
                    },
                )
            except ProgrammableSwarmError:
                # A task kernel that does not declare cancellation faults the
                # task, which is still a terminal state the runtime can release.
                pass
        removal = self._invoke_runtime(
            member_id, {"operation": "remove-task", "task_id": selected}
        )
        if member.selected_task_id == selected:
            member.selected_task_id = None
        if member.workspace_task_id == selected:
            member.workspace_task_id = None
        removal_run = _runtime_run(removal)
        output = _runtime_output(removal)
        return {
            "schema": TASK_RELEASE_SCHEMA,
            "task_id": selected,
            "status": "released",
            "cancelled": cancelled,
            "native_cleanup": native_cleanup,
            "removal": {
                "run_status": None if not isinstance(removal_run, Mapping) else removal_run.get("status"),
                "task_status": (
                    output.get("status")
                    if isinstance(output, Mapping)
                    else None
                ),
            },
        }

    def _task_placement(
        self,
        member_id: str,
        task_id: str,
        *,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
    ) -> str:
        state = (
            _runtime_state_snapshot
            if _runtime_state_snapshot is not None
            else self._runtime_state(member_id)
        )
        task = state["tasks"].get(task_id)
        if not isinstance(task, Mapping):
            raise ProgrammableSwarmError("field program task is unknown")
        substate = task.get("state")
        if not isinstance(substate, Mapping):
            raise ProgrammableSwarmError("field program task state is invalid")
        if task.get("kind") == "python":
            placement = substate.get("backend", {}).get("policy")
        elif task.get("kind") == "model":
            placement = substate.get("placement", {}).get("requested")
            if placement == "auto":
                placement = substate.get("placement", {}).get("actual")
        else:
            placement = "logical-cpu"
        return (
            placement
            if placement in {"logical-cpu", "native-cpu", "vulkan"}
            else "logical-cpu"
        )

    def _native_model_task_ids(
        self,
        member_id: str,
        task_id: str,
        *,
        branch_id: str | None = None,
    ) -> tuple[str, ...]:
        state = self._runtime_state(member_id)
        task = state["tasks"].get(task_id)
        if not isinstance(task, Mapping) or task.get("kind") != "model":
            return ()
        substate = task.get("state")
        if not isinstance(substate, Mapping):
            return ()
        task_ids: set[str] = set()
        for operation in substate.get("operations", {}).values():
            if not isinstance(operation, Mapping):
                continue
            request = operation.get("request")
            native_task_id = (
                request.get("native_task_id")
                if isinstance(request, Mapping)
                else None
            )
            if not isinstance(native_task_id, str):
                continue
            if branch_id is None or native_task_id.endswith(f":{branch_id}"):
                task_ids.add(native_task_id)
        return tuple(sorted(task_ids))

    def _drop_native_group(
        self, key: tuple[int, int], reason: str
    ) -> Mapping[str, Any]:
        group = self._native_groups.get(key)
        if group is None:
            return {"status": "group-absent", "group_id": key[1], "reason": reason}
        for row in group.get("seats", ()):
            if not isinstance(row, Mapping):
                continue
            native_task_id = row.get("native_task_id")
            if isinstance(native_task_id, str):
                self._native_task_sync.pop(
                    (id(group["runtime"]), native_task_id), None
                )
        group["retire_requested"] = True
        if group["service_generation"] != group["runtime"].service_generation:
            self._native_groups.pop(key, None)
            return {
                "status": "group-expired",
                "group_id": group["group_id"],
                "reason": reason,
                "group_service_generation": group["service_generation"],
                "runtime_service_generation": group["runtime"].service_generation,
            }
        try:
            dropped = _plain(group["runtime"].drop_group(group["group_id"]))
            self._native_groups.pop(key, None)
            return {**dict(dropped), "reason": reason}
        except Exception as exc:
            return {
                "status": "group-cleanup-unavailable",
                "group_id": group["group_id"],
                "reason": str(exc),
                "cleanup_reason": reason,
            }

    def _leave_native_seats(
        self,
        key: tuple[int, int],
        departures: Sequence[tuple[int, str]],
    ) -> Mapping[str, Any]:
        """Free group seats while the group and its other sequences stay resident."""

        group = self._native_groups.get(key)
        if group is None:
            return {"status": "group-absent", "group_id": key[1]}
        runtime = group["runtime"]
        if (
            group.get("retire_requested")
            or group["service_generation"] != runtime.service_generation
        ):
            return self._drop_native_group(
                key, departures[0][1] if departures else "native seat release"
            )
        left: list[Mapping[str, Any]] = []
        for seat, reason in departures:
            entry = group["seats"][seat]
            if entry is None:
                continue
            try:
                released = runtime.leave_group(group["group_id"], seat)
            except Exception as exc:
                return {
                    "status": "group-seat-release-failed",
                    "group_id": group["group_id"],
                    "seat": seat,
                    "reason": str(exc),
                    "group_cleanup": _plain(
                        self._drop_native_group(key, "native seat release failed")
                    ),
                }
            group["seats"][seat] = None
            self._native_task_sync.pop((id(runtime), entry["native_task_id"]), None)
            left.append(
                {
                    "seat": seat,
                    "status": released.get("status")
                    if isinstance(released, Mapping)
                    else None,
                    "member_id": entry["member_id"],
                    "task_id": entry["task_id"],
                    "native_task_id": entry["native_task_id"],
                    "history_length": len(entry["history"]),
                    "reason": reason,
                }
            )
        receipt: dict[str, Any] = {
            "status": "group-seats-left",
            "group_id": group["group_id"],
            "seats": left,
        }
        if all(entry is None for entry in group["seats"]):
            # A fully idle group keeps its context for the next fresh cohort;
            # one idle group per runtime and source bounds the held memory.
            receipt["idle_retention"] = [
                _plain(
                    self._drop_native_group(
                        other_key, "one idle native group is kept per runtime and source"
                    )
                )
                for other_key, other in tuple(self._native_groups.items())
                if other_key != key
                and other["runtime"] is runtime
                and other["source_sha256"] == group["source_sha256"]
                and all(other_entry is None for other_entry in other["seats"])
            ]
        return receipt

    def _release_native_seats(
        self,
        matches: Callable[[Mapping[str, Any]], bool],
        reason: str,
        *,
        runtime: ResidentFieldRuntime | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        receipts: list[Mapping[str, Any]] = []
        for key, group in tuple(self._native_groups.items()):
            if runtime is not None and group["runtime"] is not runtime:
                continue
            departures = tuple(
                (seat, reason)
                for seat, entry in enumerate(group["seats"])
                if entry is not None and matches(entry)
            )
            if departures:
                receipts.append(self._leave_native_seats(key, departures))
        return tuple(receipts)

    def _release_native_task_seats(
        self, member_id: str, task_id: str, reason: str
    ) -> tuple[Mapping[str, Any], ...]:
        return self._release_native_seats(
            lambda entry: entry["member_id"] == member_id and entry["task_id"] == task_id,
            reason,
        )

    def _drop_native_model_tasks(
        self,
        member_id: str,
        task_id: str,
        *,
        native_task_ids: Sequence[str] | None = None,
    ) -> Sequence[Mapping[str, Any]]:
        group_cleanup = list(
            self._release_native_task_seats(member_id, task_id, "native model task cleanup")
        )
        member = self._member(member_id)
        if member.runtime is None:
            return tuple(group_cleanup)
        task_ids = (
            tuple(native_task_ids)
            if native_task_ids is not None
            else self._native_model_task_ids(member_id, task_id)
        )
        receipts: list[Mapping[str, Any]] = group_cleanup
        for native_task_id in sorted(set(task_ids)):
            task_key = (id(member.runtime), native_task_id)
            self._native_task_sync.pop(task_key, None)
            self._pending_native_publications.pop(task_key, None)
            try:
                receipts.append(_plain(member.runtime.drop_model_task(native_task_id)))
            except FieldRuntimeError as exc:
                receipts.append(
                    {
                        "status": "model-task-cleanup-unavailable",
                        "task_id": native_task_id,
                        "reason": str(exc),
                    }
                )
        return tuple(receipts)

    def _is_resident_model_task(
        self,
        member_id: str,
        task_id: str,
        *,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
    ) -> bool:
        state = (
            _runtime_state_snapshot
            if _runtime_state_snapshot is not None
            else self._runtime_state(member_id)
        )
        task = state["tasks"].get(task_id)
        if not isinstance(task, Mapping) or task.get("kind") != "model":
            return False
        graph = task["state"].get("package", {}).get("graph", ())
        return any(
            isinstance(operation, Mapping)
            and str(operation.get("op", "")).startswith("qwen-")
            for operation in graph
        )

    def _pending_resident_model_request(
        self,
        member_id: str,
        task_id: str,
        *,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
    ) -> tuple[str, Mapping[str, Any]] | None:
        state = (
            _runtime_state_snapshot
            if _runtime_state_snapshot is not None
            else self._runtime_state(member_id)
        )
        task = state["tasks"].get(task_id)
        if not isinstance(task, Mapping) or task.get("kind") != "model":
            return None
        substate = task["state"]
        if substate.get("phase") != "waiting" or substate.get("wait_reason") != "resident-model-stage":
            return None
        operation_id = substate.get("await_target")
        operation = substate.get("operations", {}).get(operation_id)
        if (
            not isinstance(operation_id, str)
            or not isinstance(operation, Mapping)
            or operation.get("phase") != "proposed"
            or not isinstance(operation.get("request"), Mapping)
        ):
            raise ProgrammableSwarmError("resident model wait state is invalid")
        return operation_id, operation["request"]

    def _service_resident_model_wait(
        self,
        member_id: str,
        task_id: str,
        prior_receipt: Mapping[str, Any] | None,
        *,
        _pending: tuple[str, Mapping[str, Any]] | None = None,
        _pending_checked: bool = False,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
        _batch_to_token: bool = False,
    ) -> Mapping[str, Any]:
        pending = (
            _pending
            if _pending_checked
            else self._pending_resident_model_request(
                member_id,
                task_id,
                _runtime_state_snapshot=_runtime_state_snapshot,
            )
        )
        if pending is None:
            return prior_receipt or {
                "schema": SWARM_RESULT_SCHEMA,
                "view": self.inspect(member_id, task_id=task_id),
                "receipt": None,
            }
        operation_id, request = pending
        executor = self._resident_models.get(str(request.get("source_sha256", "")))
        if executor is None:
            raise ProgrammableSwarmError("resident model stage has no bound executor")
        member = self._member(member_id)
        execute_stage = getattr(
            member.owner,
            "execute_resident_model_stage",
            None,
        )
        if not callable(execute_stage):
            raise ProgrammableSwarmError(
                "member owner does not expose neural membrane stage execution"
            )
        membrane_operation_id = "swarm-neural-" + _digest(
            {
                "member_id": member_id,
                "task_id": task_id,
                "resident_operation_id": operation_id,
                "request": request,
                "batch_to_token": _batch_to_token,
            }
        )
        coupled = execute_stage(
            membrane_operation_id,
            computer_id=member.computer_id,
            task_id=task_id,
            resident_operation_id=operation_id,
            request=request,
            executor=executor,
            resume_task=True,
            batch_to_token=_batch_to_token,
        )
        result = coupled.get("stage_result")
        membrane_receipt = coupled.get("membrane_receipt")
        resume_receipt = coupled.get("resume_receipt")
        checkpoint_receipt = coupled.get("_checkpoint_receipt")
        batched_membranes = coupled.get("membrane_receipts")
        rehearsals = coupled.get("_rehearsal_receipts")
        if (
            not isinstance(result, Mapping)
            or not isinstance(membrane_receipt, Mapping)
            or not isinstance(resume_receipt, Mapping)
            or not isinstance(checkpoint_receipt, Mapping)
        ):
            raise ProgrammableSwarmError(
                "owner returned an invalid neural membrane stage result"
            )
        if _batch_to_token and (
            not isinstance(batched_membranes, list)
            or not batched_membranes
            or any(not isinstance(row, Mapping) for row in batched_membranes)
        ):
            raise ProgrammableSwarmError(
                "owner returned an invalid neural membrane token batch"
            )
        result = dict(result)
        resumed = {
            "receipt": dict(resume_receipt),
            "checkpoint_receipt": dict(checkpoint_receipt),
        }
        if member.runtime is not None:
            self.refresh_residency(member_id)
        membrane_rows = (
            [dict(row) for row in batched_membranes]
            if _batch_to_token
            else [dict(membrane_receipt)]
        )
        return {
            **dict(resumed),
            "resident_model": {
                "stage": request["stage"],
                "executor": "cassi-resident-qwen",
                "backend": result["backend"],
                "snapshot": result["snapshot"],
                "stage_count": len(membrane_rows),
                "neural_membranes": membrane_rows,
                "neural_membrane": {
                    "schema": membrane_receipt["schema"],
                    "state_sha256": membrane_receipt["state_sha256"],
                    "profile_sha256": membrane_receipt["profile_sha256"],
                    "site_count": membrane_receipt["site_count"],
                    "site_trace_sha256": membrane_receipt[
                        "site_trace_sha256"
                    ],
                    "changed_words": membrane_receipt["changed_words"],
                    "predecessor_state_sha256": membrane_receipt[
                        "predecessor_state_sha256"
                    ],
                    "sites": [
                        dict(row) for row in membrane_receipt["sites"]
                    ],
                    "migration": (
                        None
                        if membrane_receipt["migration"] is None
                        else dict(membrane_receipt["migration"])
                    ),
                    "gain_ppm": membrane_receipt["gain_ppm"],
                },
                **(
                    {"rehearsals": [dict(row) for row in rehearsals]}
                    if isinstance(rehearsals, list) and rehearsals
                    else {}
                ),
            },
        }

    def _pending_native_model_request(
        self,
        member_id: str,
        task_id: str,
        *,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
    ) -> tuple[str, Mapping[str, Any]] | None:
        state = (
            _runtime_state_snapshot
            if _runtime_state_snapshot is not None
            else self._runtime_state(member_id)
        )
        task = state["tasks"].get(task_id)
        if not isinstance(task, Mapping) or task.get("kind") != "model":
            return None
        substate = task.get("state")
        if (
            not isinstance(substate, Mapping)
            or substate.get("phase") != "waiting"
            or substate.get("wait_reason") != "native-model-token"
        ):
            return None
        operation_id = substate.get("await_target")
        operation = substate.get("operations", {}).get(operation_id)
        if (
            not isinstance(operation_id, str)
            or not isinstance(operation, Mapping)
            or operation.get("phase") != "proposed"
            or not isinstance(operation.get("request"), Mapping)
        ):
            raise ProgrammableSwarmError("native model wait state is invalid")
        return operation_id, operation["request"]

    def _native_wait_record(
        self,
        member_id: str,
        task_id: str,
        operation_id: str,
        request: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> MutableMapping[str, Any]:
        member = self._member(member_id)
        source_sha256 = request.get("source_sha256")
        native_task_id = request.get("native_task_id")
        tokens = request.get("tokens")
        sampler = request.get("sampler")
        if (
            request.get("schema") != "cassifi.native-model-token-request.v1"
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
            or not isinstance(native_task_id, str)
            or not native_task_id
            or not isinstance(tokens, Sequence)
            or isinstance(tokens, (str, bytes, bytearray, Mapping))
            or not tokens
            or not isinstance(sampler, Mapping)
        ):
            raise ProgrammableSwarmError("native model request payload is invalid")
        history: list[int] = []
        for token in tokens:
            if (
                isinstance(token, bool)
                or not isinstance(token, int)
                or not 0 <= token <= 0x7FFFFFFF
            ):
                raise ProgrammableSwarmError("native model request history is invalid")
            history.append(token)
        mode = sampler.get("mode", "greedy")
        temperature = sampler.get("temperature", 1.0)
        top_k = sampler.get("top_k", 0)
        draw = sampler.get("draw", 0.0)
        if (
            mode not in {"greedy", "categorical"}
            or isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
            or temperature <= 0.0
            or isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 0 <= top_k <= 0xFFFFFFFF
            or isinstance(draw, bool)
            or not isinstance(draw, (int, float))
            or not math.isfinite(draw)
            or not 0.0 <= draw < 1.0
        ):
            raise ProgrammableSwarmError("native model request sampler is invalid")
        model_program_id = request.get("model_program_id")
        source_id = request.get("source_id")
        attribution = request.get("attribution")
        if (
            not isinstance(model_program_id, str)
            or not model_program_id
            or (source_id is not None and not isinstance(source_id, str))
            or not isinstance(attribution, str)
            or not attribution
        ):
            raise ProgrammableSwarmError("native model request site is invalid")
        run = request.get("run")
        run_plan: dict[str, Any] | None = None
        if run is not None:
            bound = run.get("bound") if isinstance(run, Mapping) else None
            operation_ids = run.get("operation_ids") if isinstance(run, Mapping) else None
            draws = run.get("draws") if isinstance(run, Mapping) else None
            if (
                isinstance(bound, bool)
                or not isinstance(bound, int)
                or not 2 <= bound <= 8
                or not isinstance(operation_ids, list)
                or not isinstance(draws, list)
                or len(operation_ids) != bound
                or len(draws) != bound
                or operation_ids[0] != operation_id
                or len(set(operation_ids)) != bound
                or any(
                    not isinstance(item, str) or not item for item in operation_ids
                )
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or not math.isfinite(item)
                    or not 0.0 <= item < 1.0
                    for item in draws
                )
                or draws[0] != draw
            ):
                raise ProgrammableSwarmError("native model token run plan is invalid")
            run_plan = {
                "bound": bound,
                "operation_ids": tuple(operation_ids),
                "draws": tuple(float(item) for item in draws),
            }
            draft_tokens = run.get("draft_tokens") if isinstance(run, Mapping) else None
            if draft_tokens is not None:
                if (
                    not isinstance(draft_tokens, list)
                    or len(draft_tokens) != bound - 1
                    or any(
                        isinstance(item, bool)
                        or not isinstance(item, int)
                        or not 0 <= item <= 0x7FFFFFFF
                        for item in draft_tokens
                    )
                ):
                    raise ProgrammableSwarmError(
                        "native model token run draft is invalid"
                    )
                run_plan["draft_tokens"] = tuple(draft_tokens)
        tasks = state.get("tasks")
        task = tasks.get(task_id) if isinstance(tasks, Mapping) else None
        if not isinstance(task, Mapping) or not isinstance(task.get("state"), Mapping):
            raise ProgrammableSwarmError("native model task state is unavailable")
        model_state = task["state"]
        package = model_state.get("package", {})
        tokenizer = package.get("tokenizer", {}) if isinstance(package, Mapping) else {}
        program = package.get("program", {}) if isinstance(package, Mapping) else {}
        tokenizer_id = (
            program.get("tokenizer_sha256") if isinstance(program, Mapping) else None
        )
        identity = model_state.get("identity")
        if (
            not isinstance(tokenizer_id, str)
            or len(tokenizer_id) != 64
            or any(character not in "0123456789abcdef" for character in tokenizer_id)
            or not isinstance(identity, Mapping)
            or any(
                not isinstance(identity.get(name), str) or not identity[name]
                for name in ("owner_id", "member_id", "operation_id")
            )
        ):
            raise ProgrammableSwarmError(
                "native model task lacks its exact owner/tokenizer identity"
            )
        sequence_id = ":".join(
            str(identity[name]) for name in ("owner_id", "member_id", "operation_id")
        )
        vocab_size = (
            int(tokenizer.get("vocab_size", tokenizer.get("token_count", 0)))
            if isinstance(tokenizer, Mapping)
            else 0
        )
        record = {
            "member_id": member_id,
            "task_id": task_id,
            "operation_id": operation_id,
            "request": request,
            "state": state,
            "runtime": member.runtime,
            "source_sha256": source_sha256,
            "model_id": source_sha256,
            "tokenizer_id": tokenizer_id,
            "sequence_id": sequence_id,
            "native_task_id": native_task_id,
            "row_identity": (member_id, task_id, native_task_id),
            "history": tuple(history),
            "sampler": {
                "mode": str(mode),
                "temperature": float(temperature),
                "top_k": top_k,
                "draw": float(draw),
            },
            "sampler_key": (str(mode), float(temperature), top_k),
            "site": (model_program_id, source_id, attribution),
            "binding": self._model_backings.get(source_sha256),
            "placement": self._task_placement(
                member_id, task_id, _runtime_state_snapshot=state
            ),
            "vocab_size": vocab_size,
            "run": run_plan,
            "stop_tokens": frozenset(
                int(token)
                for token in (model_state.get("request") or {}).get("stop_tokens", ())
            ),
        }
        record["native_graph_site_potential"] = (
            self._native_graph_site_potential(record)
        )
        return record

    @staticmethod
    def _native_graph_site_potential(record: Mapping[str, Any]) -> bool:
        state = record.get("state")
        task_id = record.get("task_id")
        source_sha256 = record.get("source_sha256")
        if not isinstance(state, Mapping) or not isinstance(task_id, str):
            return False
        tasks = state.get("tasks")
        task = tasks.get(task_id) if isinstance(tasks, Mapping) else None
        task_state = task.get("state") if isinstance(task, Mapping) else None
        task_request = (
            task_state.get("request") if isinstance(task_state, Mapping) else None
        )
        modes = (
            task_request.get("graph_site_modes")
            if isinstance(task_request, Mapping)
            else None
        )
        if not isinstance(modes, Mapping):
            modes = {}
        policies = state.get("model_policies")
        source_policy = (
            policies.get(source_sha256)
            if isinstance(policies, Mapping) and isinstance(source_sha256, str)
            else None
        )
        graph_state = (
            source_policy.get("graph_sites")
            if isinstance(source_policy, Mapping)
            else None
        )
        if (
            not isinstance(graph_state, Mapping)
            or graph_state.get("source_sha256") != source_sha256
            or not isinstance(graph_state.get("methods"), Mapping)
        ):
            return False
        from programs.model.graph_site import SPECIALISTS, configured_mode

        for row in graph_state["methods"].values():
            if not isinstance(row, Mapping):
                continue
            specialist = row.get("specialist")
            if specialist not in SPECIALISTS:
                continue
            mode = configured_mode(modes, specialist)
            applicability = row.get("applicability")
            if (
                mode in {"auto", "replace"}
                and row.get("admitted") is True
                and row.get("backed_off") is False
                and isinstance(row.get("method"), Mapping)
                and isinstance(applicability, Mapping)
                and applicability.get("source_sha256") == source_sha256
            ):
                return True
        return False

    def _prepare_native_graph_site_dispatch(
        self, record: MutableMapping[str, Any]
    ) -> Mapping[str, Any] | None:
        if not self._native_graph_site_potential(record):
            return None
        runtime = record["runtime"]
        try:
            preflight = runtime.candidate_preflight(
                record["native_task_id"],
                record["source_sha256"],
                record["history"],
                sequence_id=record["sequence_id"],
                sampler=record["sampler"],
                native_operation_id=record["operation_id"],
            )
        except Exception as exc:
            message = str(exc)
            if message.startswith(
                (
                    "native graph-site preflight refused:",
                    "native graph-site preflight reports no supported sites:",
                    "native graph-site preflight API is unavailable or incompatible:",
                    "native model runtime does not support graph-site preflight and replay",
                )
            ):
                # Graph sites act at decode boundaries.  A sequence whose
                # prompt is still unserviced reaches its first boundary after
                # one ordinary token, so the singleton defers its token run.
                record["native_graph_site_deferred"] = (
                    "native_sequence_not_at_single_token_boundary" in message
                )
                return None
            raise
        if not isinstance(preflight, Mapping):
            raise ProgrammableSwarmError(
                "native graph-site preflight is not an object"
            )
        normalized_preflight = _plain(preflight)
        if not isinstance(normalized_preflight, MutableMapping):
            raise ProgrammableSwarmError(
                "native graph-site preflight is not canonical data"
            )
        if normalized_preflight.get("schema") not in {
            None,
            "cassifi.native-graph-site-preflight.v1",
        }:
            raise ProgrammableSwarmError(
                "native graph-site preflight has an unsupported schema"
            )
        normalized_preflight["schema"] = (
            "cassifi.native-graph-site-preflight.v1"
        )
        if (
            normalized_preflight.get("ready") is not True
            or normalized_preflight.get("task_id") != record["native_task_id"]
            or normalized_preflight.get("native_operation_id")
            != record["operation_id"]
            or normalized_preflight.get("sequence_id") != record["sequence_id"]
            or normalized_preflight.get("source_sha256")
            != record["source_sha256"]
            or normalized_preflight.get("input_tokens")
            != list(record["history"])
            or normalized_preflight.get("sampler") != dict(record["sampler"])
            or normalized_preflight.get("next_position")
            != len(record["history"])
        ):
            raise ProgrammableSwarmError(
                "native graph-site preflight does not match its exact WAIT request"
            )
        member = self._member(record["member_id"])
        try:
            ticket = member.owner.issue_native_graph_site_ticket(
                computer_id=member.computer_id,
                task_id=record["native_task_id"],
                operation_id=record["operation_id"],
                preflight=normalized_preflight,
            )
        except Exception as exc:
            if (
                getattr(exc, "code", None) == "NATIVE_GRAPH_SITE_UNAVAILABLE"
                and str(exc)
                == "no native preflight site matches an admitted owner graph-site method"
            ):
                return None
            raise
        normalized_ticket = _plain(ticket)
        if not isinstance(normalized_ticket, Mapping) or (
            normalized_ticket.get("task_id") != record["native_task_id"]
            or normalized_ticket.get("operation_id") != record["operation_id"]
            or normalized_ticket.get("native_operation_id")
            != record["operation_id"]
            or normalized_ticket.get("sequence_id") != record["sequence_id"]
            or normalized_ticket.get("source_sha256")
            != record["source_sha256"]
            or normalized_ticket.get("sampler") != dict(record["sampler"])
        ):
            raise ProgrammableSwarmError(
                "owner-issued native graph-site ticket disagrees with its WAIT request"
            )
        return {
            "ticket": normalized_ticket,
            "preflight": normalized_preflight,
            "reservation_state_sha256": member.owner.state.state_sha256,
            "task_id": record["native_task_id"],
            "source_sha256": record["source_sha256"],
            "sequence_id": record["sequence_id"],
            "native_operation_id": record["operation_id"],
            "tokens": list(record["history"]),
            "sampler": dict(record["sampler"]),
        }

    @staticmethod
    def _is_native_digest(value: Any) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    def _native_owner_replay_history(
        self, record: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        member = self._member(record["member_id"])
        replay = getattr(member.owner, "native_graph_site_replay_history", None)
        if not callable(replay):
            raise ProgrammableSwarmError(
                "field owner does not expose authoritative native replay history"
            )
        try:
            history = replay(
                record["native_task_id"],
                record["source_sha256"],
                record["model_id"],
                record["tokenizer_id"],
            )
        except Exception as exc:
            raise ProgrammableSwarmError(
                f"native model owner history is unavailable: {exc}"
            ) from exc
        if (
            not isinstance(history, Mapping)
            or history.get("schema")
            != "cassifi.native-graph-site-replay-history.v1"
            or history.get("task_id") != record["native_task_id"]
            or history.get("model_task_id") != record["task_id"]
            or history.get("source_sha256") != record["source_sha256"]
            or history.get("model_id") != record["model_id"]
            or history.get("tokenizer_id") != record["tokenizer_id"]
            or history.get("history_complete") is not True
        ):
            raise ProgrammableSwarmError(
                "native model owner history has a different task/model identity"
            )
        prompt = history.get("prompt_tokens")
        steps = history.get("accepted_steps")
        if (
            isinstance(prompt, (str, bytes, bytearray, Mapping))
            or not isinstance(prompt, Sequence)
            or not prompt
            or isinstance(steps, (str, bytes, bytearray, Mapping))
            or not isinstance(steps, Sequence)
        ):
            raise ProgrammableSwarmError(
                "native model owner history is missing its prompt or accepted steps"
            )
        expected_tokens: list[int] = []
        for token in prompt:
            if (
                isinstance(token, bool)
                or not isinstance(token, int)
                or not 0 <= token <= 0x7FFFFFFF
            ):
                raise ProgrammableSwarmError(
                    "native model owner prompt contains an invalid token"
                )
            expected_tokens.append(token)
        graph_receipts: list[str] = []
        normalized_steps: list[Mapping[str, Any]] = []
        seen_operations: set[str] = set()
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                raise ProgrammableSwarmError(
                    "native model owner history contains a malformed accepted step"
                )
            native_operation_id = step.get("native_operation_id")
            owner_operation_id = step.get("owner_operation_id")
            input_tokens = step.get("input_tokens")
            accepted_token = step.get("accepted_token_id")
            sampler = step.get("sampler")
            position = step.get("position")
            token_count = step.get("token_count")
            if (
                not isinstance(native_operation_id, str)
                or not native_operation_id
                or native_operation_id in seen_operations
                or not isinstance(owner_operation_id, str)
                or not owner_operation_id
                or step.get("task_id") != record["native_task_id"]
                or step.get("source_sha256") != record["source_sha256"]
                or step.get("history_complete") is not True
                or step.get("selected_token") != accepted_token
                or isinstance(input_tokens, (str, bytes, bytearray, Mapping))
                or not isinstance(input_tokens, Sequence)
                or list(input_tokens) != expected_tokens
                or step.get("input_tokens_sha256")
                != _token_history_digest(input_tokens)
                or isinstance(position, bool)
                or not isinstance(position, int)
                or position != len(expected_tokens)
                or isinstance(step.get("sequence_index"), bool)
                or step.get("sequence_index") != step_index
                or isinstance(token_count, bool)
                or not isinstance(token_count, int)
                or token_count != len(expected_tokens) + 1
                or isinstance(accepted_token, bool)
                or not isinstance(accepted_token, int)
                or not 0 <= accepted_token <= 0x7FFFFFFF
                or not isinstance(sampler, Mapping)
                or set(sampler) != {"mode", "temperature", "top_k", "draw"}
                or step.get("sampler_sha256") != _digest(dict(sampler))
                or not self._is_native_digest(step.get("replay_sha256"))
                or not self._is_native_digest(step.get("stage_trace_sha256"))
            ):
                raise ProgrammableSwarmError(
                    "native owner replay step is discontinuous or lacks exact evidence"
                )
            if step.get("sequence_id") not in {
                record["native_task_id"],
                record["sequence_id"],
            }:
                raise ProgrammableSwarmError(
                    "native owner replay step names a different logical sequence"
                )
            graph_ticket = step.get("graph_site_ticket")
            graph_receipt = step.get("graph_site_receipt")
            if graph_ticket is not None or graph_receipt is not None:
                if not isinstance(graph_ticket, Mapping) or not isinstance(
                    graph_receipt, Mapping
                ):
                    raise ProgrammableSwarmError(
                        "native owner graph history has an incomplete ticket bundle"
                    )
                receipt_sha256 = step.get("native_graph_site_receipt_sha256")
                wire_sha256 = step.get("graph_receipt_wire_sha256")
                if (
                    graph_ticket.get("task_id") != record["native_task_id"]
                    or graph_ticket.get("model_task_id") != record["task_id"]
                    or graph_ticket.get("operation_id") != native_operation_id
                    or graph_ticket.get("native_operation_id")
                    != native_operation_id
                    or graph_ticket.get("sequence_id") != record["sequence_id"]
                    or graph_ticket.get("source_sha256")
                    != record["source_sha256"]
                    or graph_ticket.get("model_id") != record["model_id"]
                    or graph_ticket.get("tokenizer_id") != record["tokenizer_id"]
                    or step.get("sequence_id") != record["sequence_id"]
                    or graph_ticket.get("ticket_id") != step.get("ticket_id")
                    or graph_ticket.get("ticket_sha256")
                    != step.get("ticket_sha256")
                    or graph_ticket.get("native_guard", {}).get("candidate_id")
                    != graph_ticket.get("ticket_id")
                    or graph_receipt.get("task_id") != record["native_task_id"]
                    or graph_receipt.get("sequence_id") != record["sequence_id"]
                    or graph_receipt.get("native_operation_id")
                    != native_operation_id
                    or graph_receipt.get("selected_token_id") != accepted_token
                    or graph_receipt.get("field_candidate_id")
                    != step.get("field_candidate_id")
                    or not self._is_native_digest(receipt_sha256)
                    or receipt_sha256 != _digest(dict(graph_receipt))
                    or not self._is_native_digest(wire_sha256)
                    or step.get("native_graph_site_receipt_wire_sha256")
                    != wire_sha256
                ):
                    raise ProgrammableSwarmError(
                        "native owner graph history does not match its accepted step"
                    )
                graph_receipts.append(receipt_sha256)
            seen_operations.add(native_operation_id)
            normalized_steps.append(dict(step))
            expected_tokens.append(accepted_token)
        if tuple(expected_tokens) != tuple(record["history"]):
            raise ProgrammableSwarmError(
                "native request history differs from field-owner accepted tokens"
            )
        payload = _plain(
            {
                **dict(history),
                "prompt_tokens": list(prompt),
                "accepted_steps": normalized_steps,
            }
        )
        return {
            "payload": payload,
            "tokens": tuple(expected_tokens),
            "graph_receipts": tuple(graph_receipts),
            "has_graph_history": bool(graph_receipts),
            "accepted_steps": tuple(normalized_steps),
        }

    def _ensure_native_task_history(
        self,
        record: MutableMapping[str, Any],
        owner_history: Mapping[str, Any],
        *,
        require_cache: bool = True,
    ) -> Mapping[str, Any]:
        runtime = record["runtime"]
        task_key = (id(runtime), record["native_task_id"])
        pending = self._pending_native_publications.get(task_key)
        if pending is not None:
            if pending["service_generation"] == runtime.service_generation:
                self._release_native_task_seats(
                    record["member_id"],
                    record["task_id"],
                    "native publication is awaiting cache reconciliation",
                )
                raise ProgrammableSwarmError(
                    "native model task cannot advance while owner publication "
                    "lacks native cache confirmation"
                )
            self._pending_native_publications.pop(task_key, None)
            self._native_task_sync.pop(task_key, None)
        if not require_cache:
            return {
                "status": "owner-history-current",
                "replayed_steps": 0,
                "history_signature": (
                    tuple(record["history"]),
                    tuple(owner_history["graph_receipts"]),
                ),
            }
        history_signature = (
            tuple(record["history"]),
            tuple(owner_history["graph_receipts"]),
        )
        current = self._native_task_sync.get(task_key)
        if (
            current is not None
            and current["cache_ready"] is True
            and current["service_generation"] == runtime.service_generation
            and current["history_signature"] == history_signature
        ):
            return {
                "status": "native-history-current",
                "replayed_steps": 0,
                "history_signature": history_signature,
            }
        steps = owner_history["accepted_steps"]
        if steps:
            rebuilt = runtime.rebuild_task_from_owner_history(
                record["native_task_id"],
                record["source_sha256"],
                record["model_id"],
                record["tokenizer_id"],
                owner_history["payload"],
            )
            if (
                not isinstance(rebuilt, Mapping)
                or rebuilt.get("status") != "history-replayed"
                or rebuilt.get("task_id") != record["native_task_id"]
                or rebuilt.get("source_sha256") != record["source_sha256"]
                or rebuilt.get("model_sha256") != record["model_id"]
                or rebuilt.get("tokenizer_sha256") != record["tokenizer_id"]
                or rebuilt.get("replayed_steps") != len(steps)
                or rebuilt.get("token_count") != len(record["history"])
            ):
                self._native_task_sync.pop(task_key, None)
                raise ProgrammableSwarmError(
                    "native task rebuild did not reproduce the exact owner history"
                )
        else:
            dropped = runtime.drop_model_task(record["native_task_id"])
            if (
                not isinstance(dropped, Mapping)
                or dropped.get("task_id") != record["native_task_id"]
            ):
                self._native_task_sync.pop(task_key, None)
                raise ProgrammableSwarmError(
                    "native task reset did not confirm its exact task identity"
                )
            rebuilt = {
                "status": "history-empty",
                "task_id": record["native_task_id"],
                "replayed_steps": 0,
                "token_count": len(record["history"]),
            }
        self._native_task_sync[task_key] = {
            "service_generation": runtime.service_generation,
            "history_signature": history_signature,
            "cache_ready": True,
        }
        return _plain(rebuilt)

    def _remember_native_task_step(
        self,
        record: Mapping[str, Any],
        owner_history: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> None:
        run_steps = result.get("steps")
        tokens = [
            step.get("token") if isinstance(step, Mapping) else None
            for step in (run_steps if isinstance(run_steps, list) else [result])
        ]
        if not tokens or any(
            isinstance(token, bool)
            or not isinstance(token, int)
            or token < 0
            for token in tokens
        ):
            raise ProgrammableSwarmError(
                "native model continuation returned no accepted token"
            )
        graph_receipts = tuple(owner_history["graph_receipts"])
        receipt_sha = result.get("native_graph_site_receipt_sha256")
        if receipt_sha is not None:
            if not self._is_native_digest(receipt_sha):
                raise ProgrammableSwarmError(
                    "native graph-site continuation returned an invalid receipt digest"
                )
            graph_receipts = (*graph_receipts, receipt_sha)
        task_key = (id(record["runtime"]), record["native_task_id"])
        self._native_task_sync[task_key] = {
            "service_generation": record["runtime"].service_generation,
            "cache_ready": True,
            "history_signature": (
                tuple(record["history"]) + tuple(tokens),
                graph_receipts,
            ),
        }

    def _collect_native_wait_records(
        self,
        member_id: str,
        task_id: str,
        operation_id: str,
        request: Mapping[str, Any],
        runtime_state_snapshot: Mapping[str, Any] | None,
    ) -> tuple[list[MutableMapping[str, Any]], list[Mapping[str, Any]]]:
        selected_state = (
            runtime_state_snapshot
            if runtime_state_snapshot is not None
            else self._runtime_state(member_id)
        )
        selected = self._native_wait_record(
            member_id, task_id, operation_id, request, selected_state
        )
        selected["owner_history"] = self._native_owner_replay_history(selected)
        selected["history_sync"] = self._ensure_native_task_history(
            selected, selected["owner_history"], require_cache=False
        )
        records: list[MutableMapping[str, Any]] = [selected]
        incompatible: list[Mapping[str, Any]] = []
        selected_key = (member_id, task_id)
        for candidate_member_id in sorted(self._members):
            candidate_member = self._member(candidate_member_id)
            if candidate_member.runtime is None:
                continue
            try:
                state = (
                    selected_state
                    if candidate_member_id == member_id
                    else self._runtime_state(candidate_member_id)
                )
            except Exception as exc:
                incompatible.append(
                    {
                        "member_id": candidate_member_id,
                        "reason": f"native wait state unavailable: {exc}",
                    }
                )
                continue
            tasks = state.get("tasks", {})
            if not isinstance(tasks, Mapping):
                continue
            for candidate_task_id in sorted(tasks):
                if (candidate_member_id, candidate_task_id) == selected_key:
                    continue
                task = tasks[candidate_task_id]
                if (
                    not isinstance(task, Mapping)
                    or task.get("kind") != "model"
                    or self._is_resident_model_task(
                        candidate_member_id,
                        candidate_task_id,
                        _runtime_state_snapshot=state,
                    )
                ):
                    continue
                try:
                    pending = self._pending_native_model_request(
                        candidate_member_id,
                        candidate_task_id,
                        _runtime_state_snapshot=state,
                    )
                    if pending is None:
                        continue
                    candidate_operation_id, candidate_request = pending
                    record = self._native_wait_record(
                        candidate_member_id,
                        candidate_task_id,
                        candidate_operation_id,
                        candidate_request,
                        state,
                    )
                    record["owner_history"] = self._native_owner_replay_history(
                        record
                    )
                    record["history_sync"] = self._ensure_native_task_history(
                        record,
                        record["owner_history"],
                        require_cache=False,
                    )
                except Exception as exc:
                    incompatible.append(
                        {
                            "member_id": candidate_member_id,
                            "task_id": candidate_task_id,
                            "reason": f"native wait is not group-compatible: {exc}",
                        }
                    )
                    continue
                records.append(record)
        return records, incompatible

    @staticmethod
    def _native_group_incompatibility(
        baseline: Mapping[str, Any], candidate: Mapping[str, Any]
    ) -> str | None:
        if baseline["owner_history"]["has_graph_history"]:
            return "native group replay does not support prior owner graph-site interventions"
        if candidate["owner_history"]["has_graph_history"]:
            return "native group replay does not support prior owner graph-site interventions"
        if (
            baseline.get("native_graph_site_potential") is True
            or candidate.get("native_graph_site_potential") is True
        ):
            return "owner-admitted native graph-site replacement requires singleton dispatch"
        if candidate["runtime"] is not baseline["runtime"]:
            return "different runtime object"
        if candidate["source_sha256"] != baseline["source_sha256"]:
            return "different GGUF source"
        if len(candidate["history"]) != len(baseline["history"]):
            return "different native token history length"
        if candidate["site"] != baseline["site"]:
            return "incompatible model program/source site"
        if candidate["sampler_key"] != baseline["sampler_key"]:
            return "incompatible sampler mode, temperature, or top_k"
        if candidate["binding"] != baseline["binding"]:
            return "different registered GGUF backing parameters"
        if candidate["placement"] != baseline["placement"]:
            return "different native physical placement"
        if candidate["placement"] not in {"native-cpu", "vulkan"}:
            return "unsupported native placement"
        return None

    @staticmethod
    def _native_group_row(
        record: Mapping[str, Any],
        history: Sequence[int],
        next_token: int,
        accept_sampled: bool,
    ) -> NativeGroupRow:
        sampler = record["sampler"]
        return NativeGroupRow(
            tokens=tuple(history),
            next_token=next_token,
            accept_sampled=accept_sampled,
            sampler_mode=sampler["mode"],
            temperature=sampler["temperature"],
            top_k=sampler["top_k"],
            draw=sampler["draw"],
        )

    @staticmethod
    def _validate_native_group_result(
        result: Any,
        *,
        expected_token: int,
        expected_count: int,
        vocab_size: int,
        require_not_end: bool = False,
    ) -> Mapping[str, Any]:
        if not isinstance(result, Mapping):
            raise ProgrammableSwarmError("native group returned a malformed row")
        token = result.get("token")
        sampled_token = result.get("sampled_token")
        token_count = result.get("token_count")
        end_of_generation = result.get("end_of_generation")
        replay = result.get("replay_sha256")
        trace = result.get("stage_trace_sha256")
        counters = tuple(
            result.get(name)
            for name in (
                "exact_stages",
                "embedding_stages",
                "attention_stages",
                "ffn_stages",
                "head_stages",
                "ggml_nodes",
                "logical_weight_bytes",
            )
        )
        if (
            isinstance(token, bool)
            or not isinstance(token, int)
            or token != expected_token
            or isinstance(sampled_token, bool)
            or not isinstance(sampled_token, int)
            or not 0 <= sampled_token < vocab_size
            or isinstance(token_count, bool)
            or token_count != expected_count
            or not isinstance(end_of_generation, bool)
            or (require_not_end and end_of_generation)
            or not isinstance(replay, str)
            or len(replay) != 64
            or any(character not in "0123456789abcdef" for character in replay)
            or not isinstance(trace, str)
            or len(trace) != 64
            or any(character not in "0123456789abcdef" for character in trace)
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in counters
            )
            or counters[1] < 1
            or counters[4] != 1
            or counters[2] != counters[3]
            or counters[0] != counters[1] + counters[2] + counters[3] + counters[4]
            or counters[5] < counters[0]
            or counters[6] < 1
        ):
            raise ProgrammableSwarmError("native group row did not pass exact result checks")
        return result

    @staticmethod
    def _native_group_step_result(
        record: Mapping[str, Any], row: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Name one fused group row as its task's accepted native step.

        The owner replays accepted history as singleton steps, so the row keeps
        the singleton sequence position (seq 0) and marks its execution: the
        token and replay digest match a singleton step, while the stage trace
        measures the fused batch.
        """

        history = [int(token) for token in record["history"]]
        sampler = dict(record["sampler"])
        token = int(row["token"])
        return {
            **dict(row),
            "status": "model-advanced",
            "execution": "native-group",
            "token": token,
            "selected_token_id": token,
            "accepted_token_id": token,
            "accepted": True,
            "provisional": False,
            "task_id": record["native_task_id"],
            "sequence_id": record["sequence_id"],
            "seq_id": 0,
            "position": len(history),
            "source_sha256": record["source_sha256"],
            "native_operation_id": record["operation_id"],
            "input_tokens": history,
            "input_tokens_sha256": _token_history_digest(history),
            "sampler": sampler,
            "sampler_sha256": _digest(sampler),
        }

    @staticmethod
    def _native_seat_entry(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "row_identity": record["row_identity"],
            "member_id": record["member_id"],
            "task_id": record["task_id"],
            "native_task_id": record["native_task_id"],
            "history": (),
            "sampled_token": None,
            "site": record["site"],
            "sampler_key": record["sampler_key"],
            "vocab_size": record["vocab_size"],
        }

    @staticmethod
    def _native_seat_matches(
        group: Mapping[str, Any],
        entry: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> bool:
        return (
            entry["sampled_token"] is not None
            and entry["history"] == tuple(record["history"])
            and entry["site"] == record["site"]
            and entry["sampler_key"] == record["sampler_key"]
            and entry["vocab_size"] == record["vocab_size"]
            and group["source_sha256"] == record["source_sha256"]
            and group["binding"] == dict(record["binding"])
            and group["placement"] == record["placement"]
        )

    @staticmethod
    def _native_history_is_fresh(record: Mapping[str, Any]) -> bool:
        owner_history = record["owner_history"]
        return (
            len(record["history"]) > 0
            and not owner_history["accepted_steps"]
            and tuple(owner_history["payload"]["prompt_tokens"]) == tuple(record["history"])
        )

    def _native_seated(self, record: Mapping[str, Any]) -> bool:
        return any(
            group["runtime"] is record["runtime"]
            and not group.get("retire_requested")
            and any(
                entry is not None and entry["row_identity"] == record["row_identity"]
                for entry in group["seats"]
            )
            for group in self._native_groups.values()
        )

    def _native_home_group(
        self, record: Mapping[str, Any]
    ) -> tuple[tuple[int, int], MutableMapping[str, Any]] | None:
        """Find the group whose seat holds this row's exact native sequence."""

        runtime = record["runtime"]
        home: tuple[tuple[int, int], MutableMapping[str, Any]] | None = None
        for key, group in tuple(self._native_groups.items()):
            if group.get("retire_requested"):
                self._drop_native_group(key, "retrying retired native group cleanup")
                continue
            if group["runtime"] is not runtime:
                continue
            if group["service_generation"] != runtime.service_generation:
                self._drop_native_group(key, "native runtime service generation changed")
                continue
            for seat, entry in enumerate(group["seats"]):
                if entry is None or entry["row_identity"] != record["row_identity"]:
                    continue
                if home is None and self._native_seat_matches(group, entry, record):
                    home = (key, group)
                else:
                    self._leave_native_seats(
                        key, ((seat, "seat history, site, sampler, or backing changed"),)
                    )
        return home

    @staticmethod
    def _native_seat_requests(
        group: Mapping[str, Any], requests: Mapping[int, NativeGroupRow]
    ) -> list[NativeGroupRow]:
        # Free seats still take part in the fused round; the runtime replaces
        # their request with a wiped greedy placeholder and reports no member.
        template = next(iter(requests.values()))
        placeholder = NativeGroupRow(
            tokens=(),
            next_token=0,
            accept_sampled=False,
            sampler_mode=template.sampler_mode,
            temperature=template.temperature,
            top_k=template.top_k,
            draw=0.0,
        )
        return [requests.get(seat, placeholder) for seat in range(len(group["seats"]))]

    @staticmethod
    def _native_group_results(advanced: Any, group: Mapping[str, Any]) -> Sequence[Any]:
        rows = advanced.get("rows") if isinstance(advanced, Mapping) else None
        if (
            not isinstance(advanced, Mapping)
            or advanced.get("status") != "group-advanced"
            or advanced.get("group_id") != group["group_id"]
            or not isinstance(rows, Sequence)
            or len(rows) != len(group["seats"])
        ):
            raise ProgrammableSwarmError("native group response is invalid")
        if advanced.get("native_graph_candidate") != "unavailable_native_group_candidate":
            raise ProgrammableSwarmError(
                "native group candidate capability is not an explicit per-row refusal"
            )
        return rows

    def _seat_fresh_native_group(
        self,
        runtime: ResidentFieldRuntime,
        source_sha256: str,
        records: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[int, int], MutableMapping[str, Any], str]:
        binding = dict(records[0]["binding"])
        placement = records[0]["placement"]
        idle: tuple[tuple[int, int], MutableMapping[str, Any]] | None = None
        for key, group in tuple(self._native_groups.items()):
            if (
                group["runtime"] is not runtime
                or group["source_sha256"] != source_sha256
                or any(entry is not None for entry in group["seats"])
            ):
                continue
            if (
                idle is None
                and group["service_generation"] == runtime.service_generation
                and group["binding"] == binding
                and group["placement"] == placement
                and len(group["seats"]) >= len(records)
            ):
                idle = (key, group)
            else:
                self._drop_native_group(key, "idle native group cannot seat the new cohort")
        if idle is not None:
            key, group = idle
            try:
                for record in records:
                    joined = runtime.join_group(group["group_id"])
                    seat = joined.get("row") if isinstance(joined, Mapping) else None
                    if (
                        not isinstance(joined, Mapping)
                        or joined.get("status") != "group-row-joined"
                        or isinstance(seat, bool)
                        or not isinstance(seat, int)
                        or not 0 <= seat < len(group["seats"])
                        or group["seats"][seat] is not None
                    ):
                        raise ProgrammableSwarmError(
                            "native group did not seat a newcomer in a free seat"
                        )
                    group["seats"][seat] = self._native_seat_entry(record)
            except Exception:
                self._drop_native_group(key, "idle native group seating failed")
                raise
            return key, group, "idle-group-joined"
        created = runtime.create_group(source_sha256, len(records))
        group_id = created.get("group_id") if isinstance(created, Mapping) else None
        if (
            not isinstance(created, Mapping)
            or created.get("status") != "group-created"
            or created.get("capacity") != len(records)
            or isinstance(group_id, bool)
            or not isinstance(group_id, int)
            or group_id < 1
        ):
            if isinstance(group_id, int) and not isinstance(group_id, bool) and group_id > 0:
                try:
                    runtime.drop_group(group_id)
                except Exception:
                    pass
            raise ProgrammableSwarmError("native runtime returned an invalid group identity")
        key = (id(runtime), group_id)
        group = {
            "runtime": runtime,
            "service_generation": runtime.service_generation,
            "group_id": group_id,
            "source_sha256": source_sha256,
            "binding": binding,
            "placement": placement,
            "seats": [self._native_seat_entry(record) for record in records],
        }
        self._native_groups[key] = group
        return key, group, "group-created"

    def _advance_native_group(
        self,
        runtime: ResidentFieldRuntime,
        source_sha256: str,
        records: Sequence[MutableMapping[str, Any]],
        home: tuple[tuple[int, int], MutableMapping[str, Any]] | None,
    ) -> Mapping[str, Any]:
        """Run one fused accepted round for the seated rows of a native group.

        A home group continues its seated rows in place; seats whose owner is
        absent from this round or whose history moved leave, and the rest keep
        their resident sequences.  A fresh prompt cohort takes seats in an idle
        group or a new one and replays its prompts in lockstep first.
        """

        replay_rounds = 0
        departures: list[Mapping[str, Any]] = []
        step_started_ns = time.perf_counter_ns()
        if home is not None:
            key, group = home
            seating = "continuing"
            by_identity = {record["row_identity"]: record for record in records}
            leaving: list[tuple[int, str]] = []
            for seat, entry in enumerate(group["seats"]):
                if entry is None:
                    continue
                record = by_identity.get(entry["row_identity"])
                if record is None:
                    leaving.append(
                        (seat, "seat owner is not ready or compatible for the fused round")
                    )
                elif not self._native_seat_matches(group, entry, record):
                    leaving.append((seat, "seat history, site, sampler, or backing changed"))
            if leaving:
                released = self._leave_native_seats(key, leaving)
                departures.append(released)
                if released.get("status") != "group-seats-left":
                    raise ProgrammableSwarmError("native group seat release failed")
            served = tuple(
                (seat, by_identity[entry["row_identity"]])
                for seat, entry in enumerate(group["seats"])
                if entry is not None
            )
            if not served:
                raise ProgrammableSwarmError("native group has no seated row to continue")
            requests = {
                seat: self._native_group_row(
                    record,
                    record["history"],
                    int(group["seats"][seat]["sampled_token"]),
                    True,
                )
                for seat, record in served
            }
        else:
            if any(not self._native_history_is_fresh(record) for record in records):
                raise ProgrammableSwarmError(
                    "native group cannot safely reseed generated-token history; "
                    "singleton owner-history replay is required"
                )
            if any(
                group["runtime"] is runtime and group.get("retire_requested")
                for group in self._native_groups.values()
            ):
                raise ProgrammableSwarmError(
                    "native group cleanup is unresolved; refusing to create a replacement"
                )
            key, group, seating = self._seat_fresh_native_group(
                runtime, source_sha256, records
            )
            seat_of = {
                entry["row_identity"]: seat
                for seat, entry in enumerate(group["seats"])
                if entry is not None
            }
            served = tuple(
                sorted(
                    ((seat_of[record["row_identity"]], record) for record in records),
                    key=lambda item: item[0],
                )
            )
            sampled: dict[int, int] = {}
            try:
                for index in range(len(records[0]["history"])):
                    replay = {
                        seat: self._native_group_row(
                            record,
                            record["history"][:index],
                            record["history"][index],
                            False,
                        )
                        for seat, record in served
                    }
                    rows = self._native_group_results(
                        runtime.step_group(
                            group["group_id"], self._native_seat_requests(group, replay)
                        ),
                        group,
                    )
                    for seat, record in served:
                        self._validate_native_group_result(
                            rows[seat],
                            expected_token=record["history"][index],
                            expected_count=index + 1,
                            vocab_size=record["vocab_size"],
                            require_not_end=True,
                        )
                        sampled[seat] = int(rows[seat]["sampled_token"])
                    replay_rounds += 1
            except Exception:
                self._drop_native_group(key, "group prompt replay failed")
                raise
            requests = {
                seat: self._native_group_row(record, record["history"], sampled[seat], True)
                for seat, record in served
            }
        try:
            rows = self._native_group_results(
                runtime.step_group(group["group_id"], self._native_seat_requests(group, requests)),
                group,
            )
            validated = tuple(
                self._validate_native_group_result(
                    rows[seat],
                    expected_token=requests[seat].next_token,
                    expected_count=len(record["history"]) + 1,
                    vocab_size=record["vocab_size"],
                )
                for seat, record in served
            )
        except Exception:
            self._drop_native_group(key, "group advancement failed")
            raise
        for (seat, record), result in zip(served, validated):
            group["seats"][seat] = {
                **group["seats"][seat],
                "history": tuple(record["history"]) + (int(result["token"]),),
                "sampled_token": int(result["sampled_token"]),
            }
        group["native_graph_candidate"] = "unavailable_native_group_candidate"
        return {
            "group": group,
            "served": served,
            "results": validated,
            "elapsed": (time.perf_counter_ns() - step_started_ns) / 1e9,
            "replay_rounds": replay_rounds,
            "seating": seating,
            "departures": tuple(departures),
        }

    def _continue_native_model_wait(
        self,
        record: Mapping[str, Any],
        result: Mapping[str, Any] | None,
        registration: Mapping[str, Any],
        prior_receipt: Mapping[str, Any] | None,
        *,
        cleanup: bool,
        use_seconds: float | None = None,
        graph_bundle: Mapping[str, Any] | None = None,
        grouped: bool = False,
    ) -> Mapping[str, Any]:
        member_id = record["member_id"]
        task_id = record["task_id"]
        placement = record["placement"]
        if placement not in {"native-cpu", "vulkan"}:
            raise ProgrammableSwarmError("native model continuation lost physical placement")
        run_steps = result.get("steps") if isinstance(result, Mapping) else None
        if use_seconds is not None:
            backend_policy.record_cost(
                placement,
                scope="model-transformer",
                work=(
                    sum(
                        len(record["history"]) + index
                        for index in range(len(run_steps))
                    )
                    if isinstance(run_steps, list)
                    else len(record["history"])
                ),
                use_seconds=use_seconds,
            )
        control = {
            "operation": "resume-native-model",
            "operation_id": record["operation_id"],
            "result": result,
        }
        resumed = self.run_resident_candidate(
            member_id,
            task_id=task_id,
            steps=1,
            control=control,
            operation_id=f"resident-model-resume:{record['operation_id']}",
            predecessor_state_sha256=(
                graph_bundle["reservation_state_sha256"]
                if graph_bundle is not None
                else None
            ),
            _runtime_state_snapshot=record["state"],
            _native_graph_site=graph_bundle,
        )
        resume_status = resumed.get("status")
        withheld = resume_status in {
            "cache-reconciliation-required",
            "publication-reconciliation-required",
        }
        step_result = (
            graph_bundle.get("result")
            if graph_bundle is not None
            else result
        )
        if (
            not withheld
            and graph_bundle is not None
            and graph_bundle.get("accepted") is True
        ):
            owner_ack = graph_bundle.get("owner_ack")
            if not isinstance(owner_ack, Mapping):
                raise ProgrammableSwarmError(
                    "native graph-site publication omitted its owner acknowledgment"
                )
            accepted_token = owner_ack.get("accepted_token_id")
            if isinstance(accepted_token, bool) or not isinstance(
                accepted_token, int
            ):
                raise ProgrammableSwarmError(
                    "native graph-site acknowledgment omitted its accepted token"
                )
            step_result = {
                **dict(step_result or {}),
                "status": "model-advanced",
                "accepted": True,
                "provisional": False,
                "accepted_token_id": accepted_token,
                "token": accepted_token,
                "sampled_token": accepted_token,
            }
        if grouped:
            self._native_task_sync.pop(
                (id(record["runtime"]), record["native_task_id"]), None
            )
        elif not withheld and isinstance(step_result, Mapping):
            self._remember_native_task_step(
                record, record["owner_history"], step_result
            )
        native_model: dict[str, Any] = {
            "registration": _plain(registration),
            "proposal_receipt": _plain(prior_receipt),
        }
        if not withheld and isinstance(step_result, Mapping):
            if isinstance(run_steps, list):
                native_model["step"] = _plain(run_steps[-1])
                native_model["run"] = {
                    "length": len(run_steps),
                    "tokens": [int(step["token"]) for step in run_steps],
                }
            else:
                native_model["step"] = _plain(step_result)
        serviced: dict[str, Any] = {
            **dict(resumed),
            "native_model": native_model,
        }
        if cleanup:
            view = self.inspect(member_id, task_id=task_id)
            if view["status"] in {"completed", "faulted", "cancelled"}:
                native_cleanup = self._drop_native_model_tasks(member_id, task_id)
                if native_cleanup:
                    serviced["model_cleanup"] = list(native_cleanup)
        return serviced

    def _service_native_group_cohort(
        self,
        records: Sequence[MutableMapping[str, Any]],
        registration: Mapping[str, Any],
        selected_identity: tuple[str, str, str],
        prior_receipt: Mapping[str, Any] | None,
        incompatible: Sequence[Mapping[str, Any]],
        *,
        home: tuple[tuple[int, int], MutableMapping[str, Any]] | None,
        cleanup: bool,
    ) -> Mapping[str, Any]:
        runtime = records[0]["runtime"]
        source_sha256 = records[0]["source_sha256"]
        selected_record = next(
            row for row in records if row["row_identity"] == selected_identity
        )
        try:
            advanced = self._advance_native_group(runtime, source_sha256, records, home)
        except Exception as exc:
            fallback_reason = f"group advancement failed: {exc}"
            attempted = [
                {
                    "member_id": record["member_id"],
                    "task_id": record["task_id"],
                    "native_task_id": record["native_task_id"],
                    "operation_id": record["operation_id"],
                    "history_length": len(record["history"]),
                    "history_sha256": _digest(list(record["history"])),
                    "site": list(record["site"]),
                    "sampler": _plain(record["sampler"]),
                    "fallback_reason": fallback_reason,
                }
                for record in records
            ]
            return self._service_native_singleton(
                selected_record,
                registration,
                prior_receipt,
                incompatible=incompatible,
                fallback_reason=fallback_reason,
                attempted_cohort=attempted,
                cleanup=cleanup,
            )
        group = advanced["group"]
        served = advanced["served"]
        results = advanced["results"]
        replay_rounds = advanced["replay_rounds"]
        key = (id(runtime), int(group["group_id"]))
        placement = records[0]["placement"]
        if placement not in {"native-cpu", "vulkan"}:
            self._drop_native_group(key, "unsupported group placement")
            raise ProgrammableSwarmError("native model continuation lost physical placement")
        try:
            backend_policy.record_cost(
                placement,
                scope="model-transformer",
                work=len(served) * (replay_rounds + 1),
                use_seconds=advanced["elapsed"],
            )
        except Exception:
            self._drop_native_group(key, "native group cost recording failed")
            raise
        services: list[Mapping[str, Any]] = []
        terminal_seats: list[tuple[int, str, str]] = []
        try:
            for (seat, record), result in zip(served, results):
                service = self._continue_native_model_wait(
                    record,
                    self._native_group_step_result(record, result),
                    registration,
                    prior_receipt
                    if record["row_identity"] == selected_identity
                    else None,
                    cleanup=False,
                    grouped=True,
                )
                if service.get("status") in {
                    "replayed",
                    "cache-reconciliation-required",
                    "physical-reconciliation-required",
                }:
                    raise ProgrammableSwarmError(
                        "native group continuation requires publication reconciliation"
                    )
                services.append(service)
                view = self.inspect(record["member_id"], task_id=record["task_id"])
                if view["status"] in {"completed", "faulted", "cancelled"}:
                    terminal_seats.append((seat, record["member_id"], record["task_id"]))
        except Exception:
            self._drop_native_group(key, "owner continuation did not settle group rows")
            raise
        group_receipt: dict[str, Any] = {
            "status": "group-advanced",
            "dispatch": "native-group",
            "group_id": group["group_id"],
            "group_capacity": len(group["seats"]),
            "seating": advanced["seating"],
            "source_sha256": source_sha256,
            "cohort_width": len(served),
            "replay_rounds": replay_rounds,
            "accepted_sample_rounds": 1,
            "fused_rounds": replay_rounds + 1,
            "native_graph_candidate": group["native_graph_candidate"],
            "elapsed_seconds": advanced["elapsed"],
            "incompatible_ready": [_plain(row) for row in incompatible],
            "cohort": [
                {
                    "seat": seat,
                    "member_id": record["member_id"],
                    "task_id": record["task_id"],
                    "native_task_id": record["native_task_id"],
                    "operation_id": record["operation_id"],
                    "history_length": len(record["history"]),
                    "history_sha256": _digest(list(record["history"])),
                    "site": list(record["site"]),
                    "sampler": _plain(record["sampler"]),
                    "token": int(result["token"]),
                    "sampled_token": int(result["sampled_token"]),
                    "token_count": int(result["token_count"]),
                    "replay_sha256": result["replay_sha256"],
                    "stage_trace_sha256": result["stage_trace_sha256"],
                    "owner_receipt": _plain(service),
                }
                for (seat, record), result, service in zip(served, results, services)
            ],
        }
        if advanced["departures"]:
            group_receipt["seat_departures"] = [
                _plain(row) for row in advanced["departures"]
            ]
        if terminal_seats:
            # Finished rows free their seats; the others keep their resident
            # sequences and continue in the same group.
            group_receipt["seat_release"] = _plain(
                self._leave_native_seats(
                    key,
                    tuple(
                        (seat, "group row reached a terminal task state")
                        for seat, _, _ in terminal_seats
                    ),
                )
            )
            for _, terminal_member_id, terminal_task_id in terminal_seats:
                if cleanup or (terminal_member_id, terminal_task_id) != selected_identity[:2]:
                    native_cleanup = self._drop_native_model_tasks(
                        terminal_member_id, terminal_task_id
                    )
                    if native_cleanup:
                        group_receipt.setdefault("model_cleanup", []).append(
                            {
                                "member_id": terminal_member_id,
                                "task_id": terminal_task_id,
                                "receipts": list(native_cleanup),
                            }
                        )
        selected_index = next(
            index
            for index, (_, record) in enumerate(served)
            if record["row_identity"] == selected_identity
        )
        selected_service = dict(services[selected_index])
        selected_native = dict(selected_service["native_model"])
        selected_native["group"] = group_receipt
        selected_service["native_model"] = selected_native
        selected_service["native_group"] = group_receipt
        return selected_service

    def _service_native_singleton(
        self,
        record: MutableMapping[str, Any],
        registration: Mapping[str, Any],
        prior_receipt: Mapping[str, Any] | None,
        *,
        incompatible: Sequence[Mapping[str, Any]],
        fallback_reason: str,
        attempted_cohort: Sequence[Mapping[str, Any]] = (),
        cleanup: bool,
    ) -> Mapping[str, Any]:
        runtime = record["runtime"]
        cleanup_receipts = self._release_native_seats(
            lambda entry: entry["row_identity"] == record["row_identity"],
            "singleton native dispatch",
            runtime=runtime,
        )
        sampler = record["sampler"]
        task_key = (id(runtime), record["native_task_id"])
        if attempted_cohort:
            self._native_task_sync.pop(task_key, None)
        history_sync = self._ensure_native_task_history(
            record, record["owner_history"], require_cache=True
        )
        record["history_sync"] = history_sync
        graph_bundle = self._prepare_native_graph_site_dispatch(record)
        if graph_bundle is None:
            step_started_ns = time.perf_counter_ns()
            run = record["run"]
            if run is None or record.get("native_graph_site_deferred") is True:
                result = runtime.step_model(
                    record["native_task_id"],
                    record["source_sha256"],
                    record["history"],
                    sampler_mode=sampler["mode"],
                    temperature=sampler["temperature"],
                    top_k=sampler["top_k"],
                    draw=sampler["draw"],
                    sequence_id=record["sequence_id"],
                    native_operation_id=record["operation_id"],
                )
            else:
                # One owner round admits the whole run; the native context
                # extends its KV cache incrementally across positions.  A
                # run that carries the program's draft tokens commits the
                # whole round through a single verification pass instead.
                history = list(record["history"])
                steps: list[Mapping[str, Any]] = []
                draft_tokens = run.get("draft_tokens")
                if draft_tokens:
                    verified = runtime.verify_model_draft(
                        record["native_task_id"],
                        record["source_sha256"],
                        history,
                        draft_tokens,
                        sampler_mode=sampler["mode"],
                        temperature=sampler["temperature"],
                        top_k=sampler["top_k"],
                        draws=run["draws"],
                        operation_ids=run["operation_ids"],
                        sequence_id=record["sequence_id"],
                        stop_tokens=record["stop_tokens"],
                    )
                    steps = list(verified["rows"])
                else:
                    for draw, operation_id in zip(run["draws"], run["operation_ids"]):
                        step = runtime.step_model(
                            record["native_task_id"],
                            record["source_sha256"],
                            history,
                            sampler_mode=sampler["mode"],
                            temperature=sampler["temperature"],
                            top_k=sampler["top_k"],
                            draw=draw,
                            sequence_id=record["sequence_id"],
                            native_operation_id=operation_id,
                        )
                        steps.append(step)
                        token = int(step["token"])
                        history.append(token)
                        if (
                            step.get("end_of_generation") is True
                            or token in record["stop_tokens"]
                        ):
                            break
                result = {"steps": steps}
            elapsed = (time.perf_counter_ns() - step_started_ns) / 1e9
        else:
            result = None
            elapsed = None
        serviced = dict(
            self._continue_native_model_wait(
                record,
                result,
                registration,
                prior_receipt,
                cleanup=cleanup,
                use_seconds=elapsed,
                graph_bundle=graph_bundle,
            )
        )
        native_model = serviced.get("native_model")
        step_result = (
            native_model.get("step") if isinstance(native_model, Mapping) else None
        )
        cohort_row: dict[str, Any] = {
            "member_id": record["member_id"],
            "task_id": record["task_id"],
            "native_task_id": record["native_task_id"],
            "operation_id": record["operation_id"],
            "history_length": len(record["history"]),
            "history_sha256": _digest(list(record["history"])),
            "site": list(record["site"]),
            "sampler": _plain(record["sampler"]),
        }
        group_receipt: dict[str, Any] = {
            "status": "singleton-dispatched",
            "dispatch": "native-singleton",
            "cohort_width": 1,
            "attempted_width": len(attempted_cohort) if attempted_cohort else 1,
            "source_sha256": record["source_sha256"],
            "cohort": [cohort_row],
            "incompatible_ready": [_plain(row) for row in incompatible],
            "fallback_reason": fallback_reason,
            "history_sync": _plain(history_sync),
        }
        if isinstance(step_result, Mapping):
            cohort_row.update(
                {
                    "token": int(step_result["token"]),
                    "sampled_token": int(
                        step_result.get("sampled_token", step_result["token"])
                    ),
                    "token_count": int(step_result["token_count"]),
                    "replay_sha256": step_result["replay_sha256"],
                    "stage_trace_sha256": step_result["stage_trace_sha256"],
                }
            )
            run_receipt = native_model.get("run")
            if isinstance(run_receipt, Mapping):
                cohort_row["run"] = _plain(run_receipt)
        else:
            group_receipt["status"] = "singleton-reconciliation-required"
            group_receipt["resume_status"] = serviced.get("status")
        if attempted_cohort:
            group_receipt["attempted_cohort"] = [_plain(row) for row in attempted_cohort]
        if cleanup_receipts:
            group_receipt["seat_release"] = [_plain(row) for row in cleanup_receipts]
        serviced["native_group"] = group_receipt
        serviced["native_model"] = {
            **dict(native_model or {}),
            "group": group_receipt,
        }
        return serviced

    def _service_native_model_wait(
        self,
        member_id: str,
        task_id: str,
        prior_receipt: Mapping[str, Any] | None,
        *,
        _pending: tuple[str, Mapping[str, Any]] | None = None,
        _pending_checked: bool = False,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
        _cleanup: bool = True,
    ) -> Mapping[str, Any]:
        pending = (
            _pending
            if _pending_checked
            else self._pending_native_model_request(
                member_id,
                task_id,
                _runtime_state_snapshot=_runtime_state_snapshot,
            )
        )
        if pending is None:
            return prior_receipt or {
                "schema": SWARM_RESULT_SCHEMA,
                "view": self.inspect(member_id, task_id=task_id),
                "receipt": None,
            }
        operation_id, request = pending
        member = self._member(member_id)
        runtime = member.runtime
        if runtime is None:
            raise ProgrammableSwarmError("native model request has no attached runtime")
        source_sha256 = str(request.get("source_sha256", ""))
        binding = self._model_backings.get(source_sha256)
        if binding is None:
            self._release_native_task_seats(
                member_id, task_id, "native model source backing is unavailable"
            )
            raise ProgrammableSwarmError(
                "native model source is not bound to an exact local GGUF backing"
            )
        selected_state = (
            _runtime_state_snapshot
            if _runtime_state_snapshot is not None
            else self._runtime_state(member_id)
        )
        try:
            selected = self._native_wait_record(
                member_id, task_id, operation_id, request, selected_state
            )
        except Exception:
            self._release_native_task_seats(
                member_id, task_id, "native model request identity changed"
            )
            raise
        selected["owner_history"] = self._native_owner_replay_history(selected)
        selected["history_sync"] = self._ensure_native_task_history(
            selected, selected["owner_history"], require_cache=False
        )
        try:
            registration = runtime.register_model(
                source_sha256,
                str(binding["path"]),
                context_size=int(binding["context_size"]),
                gpu_layers=int(binding["gpu_layers"]),
            )
        except Exception:
            self._release_native_task_seats(
                member_id, task_id, "native model registration failed"
            )
            raise
        if (
            not isinstance(registration, Mapping)
            or registration.get("source_sha256") != source_sha256
            or registration.get("context_size") != int(binding["context_size"])
        ):
            self._release_native_task_seats(
                member_id, task_id, "native model registration identity disagrees"
            )
            raise ProgrammableSwarmError("native model registration source identity disagrees")
        records, incompatible = self._collect_native_wait_records(
            member_id,
            task_id,
            operation_id,
            request,
            _runtime_state_snapshot,
        )
        selected = next(
            record
            for record in records
            if record["row_identity"] == selected["row_identity"]
        )
        def defer(candidate: Mapping[str, Any], reason: str) -> None:
            incompatible.append(
                {
                    "member_id": candidate["member_id"],
                    "task_id": candidate["task_id"],
                    "native_task_id": candidate["native_task_id"],
                    "operation_id": candidate["operation_id"],
                    "reason": reason,
                }
            )

        peers: list[MutableMapping[str, Any]] = []
        for candidate in records:
            if candidate["row_identity"] == selected["row_identity"]:
                continue
            if candidate["member_id"] == member_id:
                defer(candidate, "group serving requires distinct member owners")
                continue
            reason = self._native_group_incompatibility(selected, candidate)
            if reason is None:
                peers.append(candidate)
            else:
                defer(candidate, reason)
        # A seated row continues in its home group with whichever seated peers
        # are ready; fresh prompts form or reuse a group together.
        home = (
            self._native_home_group(selected)
            if self._native_group_incompatibility(selected, selected) is None
            else None
        )
        selected_fresh = self._native_history_is_fresh(selected)
        grouped: list[MutableMapping[str, Any]] = []
        for candidate in peers:
            if home is not None:
                seated = any(
                    entry is not None and entry["row_identity"] == candidate["row_identity"]
                    for entry in home[1]["seats"]
                )
                reason = None if seated else "peer is not seated in the selected row's native group"
            elif not selected_fresh:
                reason = "selected row continues generated history outside a native group"
            elif self._native_seated(candidate):
                reason = "peer continues in another native group"
            elif not self._native_history_is_fresh(candidate):
                reason = "peer has generated history outside a native group"
            else:
                reason = None
            if reason is None:
                grouped.append(candidate)
            else:
                defer(candidate, reason)
        grouped.sort(
            key=lambda row: (
                row["member_id"],
                row["task_id"],
                row["operation_id"],
            )
        )
        for candidate in grouped[7:]:
            defer(candidate, "native group capacity is limited to eight rows")
        cohort = sorted(
            [selected, *grouped[:7]],
            key=lambda row: (
                row["member_id"],
                row["task_id"],
                row["operation_id"],
            ),
        )
        if home is not None or len(cohort) >= 2:
            return self._service_native_group_cohort(
                cohort,
                registration,
                selected["row_identity"],
                prior_receipt,
                incompatible,
                home=home,
                cleanup=_cleanup,
            )
        return self._service_native_singleton(
            selected,
            registration,
            prior_receipt,
            incompatible=incompatible,
            fallback_reason=(
                "no other same-runtime, same-source native model wait with equal history, "
                "sampler, site, backing, and placement was ready; singleton dispatched immediately"
            ),
            cleanup=_cleanup,
        )

    def step(
        self,
        member_id: str,
        *,
        steps: int = 1,
        control: Mapping[str, Any] | None = None,
        task_id: str | None = None,
        _batch_to_token: bool = False,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        runtime_state = self._runtime_state(member_id)
        selected = (
            task_id
            or member.selected_task_id
            or runtime_state.get("selected_task_id")
        )
        if not isinstance(selected, str):
            raise ProgrammableSwarmError("no field program task is selected")
        if (
            isinstance(steps, bool)
            or not isinstance(steps, int)
            or not 1 <= steps <= max(PYTHON_KERNEL_MAX_WORK, MODEL_KERNEL_MAX_WORK)
        ):
            raise ProgrammableSwarmError("task quantum is outside its bound")
        member.selected_task_id = selected
        placement = self._task_placement(
            member_id,
            selected,
            _runtime_state_snapshot=runtime_state,
        )
        resident_model = self._is_resident_model_task(
            member_id,
            selected,
            _runtime_state_snapshot=runtime_state,
        )
        pending = None
        if placement in {"native-cpu", "vulkan"} and not resident_model:
            if member.runtime is None:
                raise ProgrammableSwarmError(
                    f"task requires unattached backend {placement!r}"
                )
            # A task already waiting on its native token proposal has no
            # program work to advance; servicing the proposal is its step.
            if control is None:
                pending = self._pending_native_model_request(
                    member_id,
                    selected,
                    _runtime_state_snapshot=runtime_state,
                )
            result = (
                None
                if pending is not None
                else self.run_resident_candidate(
                    member_id,
                    task_id=selected,
                    steps=steps,
                    control=control,
                    _runtime_state_snapshot=runtime_state,
                )
            )
        else:
            result = self._invoke_runtime(
                member_id,
                {
                    "operation": "advance-task",
                    "task_id": selected,
                    "quantum": steps,
                    "arguments": {} if control is None else _plain(control),
                },
            )
        if resident_model:
            serviced = self._service_resident_model_wait(
                member_id,
                selected,
                result,
                _batch_to_token=_batch_to_token,
            )
        elif pending is not None:
            serviced = self._service_native_model_wait(
                member_id,
                selected,
                None,
                _pending=pending,
                _pending_checked=True,
                _runtime_state_snapshot=runtime_state,
                _cleanup=False,
            )
        else:
            serviced = self._service_native_model_wait(
                member_id,
                selected,
                result,
                _cleanup=False,
            )
        view = self.inspect(member_id, task_id=selected)
        if (
            view["status"] in {"completed", "faulted", "cancelled"}
            and "model_cleanup" not in serviced
        ):
            cleanup = self._drop_native_model_tasks(member_id, selected)
            if cleanup:
                return {**dict(serviced), "model_cleanup": list(cleanup)}
        return serviced

    def run_to_boundary(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        quantum: int = min(64, REGIONAL_KERNEL_MAX_WORK),
        max_groups: int = 1_024,
    ) -> Mapping[str, Any]:
        if not 1 <= quantum <= max(PYTHON_KERNEL_MAX_WORK, MODEL_KERNEL_MAX_WORK):
            raise ProgrammableSwarmError("quantum is outside the program bound")
        if isinstance(max_groups, bool) or not isinstance(max_groups, int) or max_groups < 1:
            raise ProgrammableSwarmError("max_groups must be positive")
        last: Mapping[str, Any] | None = None
        for _ in range(max_groups):
            state = self._runtime_state(member_id)
            view = self._view_from_runtime_state(
                member_id,
                state,
                task_id=task_id,
            )
            if view["status"] in {
                "completed",
                "faulted",
                "cancelled",
                "paused",
                "resource-paused",
            }:
                return {"schema": SWARM_RESULT_SCHEMA, "view": view, "receipt": last}
            selected = task_id or self._member(member_id).selected_task_id
            if view["status"] == "waiting":
                if isinstance(selected, str):
                    pending = self._pending_resident_model_request(
                        member_id,
                        selected,
                        _runtime_state_snapshot=state,
                    )
                    if pending is not None:
                        last = self._service_resident_model_wait(
                            member_id,
                            selected,
                            last,
                            _pending=pending,
                            _pending_checked=True,
                            _runtime_state_snapshot=state,
                            _batch_to_token=True,
                        )
                        continue
                    pending = self._pending_native_model_request(
                        member_id,
                        selected,
                        _runtime_state_snapshot=state,
                    )
                    if pending is not None:
                        last = self._service_native_model_wait(
                            member_id,
                            selected,
                            last,
                            _pending=pending,
                            _pending_checked=True,
                            _runtime_state_snapshot=state,
                        )
                        continue
                return {"schema": SWARM_RESULT_SCHEMA, "view": view, "receipt": last}
            last = self.step(
                member_id,
                task_id=task_id,
                steps=quantum,
                _batch_to_token=True,
            )
        return {
            "schema": SWARM_RESULT_SCHEMA,
            "view": self.inspect(member_id, task_id=task_id),
            "receipt": last,
            "unfinished_reason": "group-limit",
        }

    def _view_from_runtime_state(
        self,
        member_id: str,
        state: Mapping[str, Any],
        *,
        task_id: str | None = None,
        offset: int = 0,
        limit: int = 64,
        category: str = "objects",
        principal: str | None = None,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        selected = task_id or member.selected_task_id or state.get("selected_task_id")
        if not isinstance(selected, str) or selected not in state["tasks"]:
            raise ProgrammableSwarmError("field program task is unknown")
        task = state["tasks"][selected]
        substate = task["state"]
        if task["kind"] == "python":
            rendered = computation_view(substate, offset=offset, limit=limit).as_dict()
        elif task["kind"] == "model":
            rendered = model_view(substate, offset=offset, limit=limit)
        elif task["kind"] == "workspace":
            rendered = workspace_view(
                substate,
                principal=principal or substate["identity"]["principal"],
                category=category,
                offset=offset,
                limit=limit,
            )
        else:
            raise ProgrammableSwarmError("field program task kind is unsupported")
        scheduler = _task_summary(task)
        return {
            **_plain(rendered),
            "task_id": selected,
            "kind": task["kind"],
            "status": scheduler["status"],
            "scheduler": scheduler,
        }

    def inspect(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        offset: int = 0,
        limit: int = 64,
        category: str = "objects",
        principal: str | None = None,
    ) -> Mapping[str, Any]:
        state = self._runtime_state(member_id)
        return self._view_from_runtime_state(
            member_id,
            state,
            task_id=task_id,
            offset=offset,
            limit=limit,
            category=category,
            principal=principal,
        )

    def raw_state(
        self, member_id: str, *, task_id: str | None = None
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        state = self._runtime_state(member_id)
        selected = task_id or member.selected_task_id or state.get("selected_task_id")
        if not isinstance(selected, str) or selected not in state["tasks"]:
            raise ProgrammableSwarmError("field program task is unknown")
        projected = _plain(state["tasks"][selected]["state"])
        resident = projected.get("resident_model")
        if isinstance(resident, dict) and "graph_sites" not in resident:
            policy = state.get("model_policies", {}).get(resident.get("source_sha256"), {})
            if isinstance(policy.get("graph_sites"), Mapping):
                resident["graph_sites"] = _plain(policy["graph_sites"])
        return projected

    def optimize_python(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        kind: str = "constant-fold",
        budget: int = PYTHON_KERNEL_MAX_WORK,
        arguments: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if (
            isinstance(budget, bool)
            or not isinstance(budget, int)
            or not 1 <= budget <= PYTHON_KERNEL_MAX_WORK
        ):
            raise ProgrammableSwarmError("optimization budget is outside its bound")
        control = {
            "operation": "optimize",
            "kind": _text(kind, "optimization kind"),
            **_plain(dict(arguments or {})),
        }
        return self.step(
            member_id,
            task_id=task_id,
            steps=budget,
            control=control,
        )

    def optimizer_status(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        state = self.raw_state(member_id, task_id=task_id)
        if state.get("schema") != PYTHON_RUNTIME_SCHEMA:
            raise ProgrammableSwarmError(
                "optimizer status requires a Python computation"
            )
        return _plain(python_optimizer_status(state))

    def invalidate_optimization(
        self,
        member_id: str,
        artifact_id: str,
        *,
        reason: str = "dependency-correction",
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            steps=1,
            control={
                "operation": "invalidate-optimization",
                "artifact_id": _text(artifact_id, "artifact_id"),
                "reason": _text(reason, "invalidation reason"),
            },
        )

    def begin_branch(
        self,
        member_id: str,
        branch_id: str,
        *,
        task_id: str | None = None,
        assumptions: Sequence[Mapping[str, Any]] = (),
        effect_policy: str = "forbid",
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={
                "operation": "begin-branch",
                "branch_id": _text(branch_id, "branch_id"),
                "assumptions": [_plain(value) for value in assumptions],
                "effect_policy": effect_policy,
            },
        )

    def commit_branch(
        self,
        member_id: str,
        branch_id: str,
        *,
        task_id: str | None = None,
        expected_base_sha256: str | None = None,
        require_no_reference_escape: bool = False,
    ) -> Mapping[str, Any]:
        selected = task_id or self._member(member_id).selected_task_id
        if not isinstance(selected, str):
            raise ProgrammableSwarmError("no field program task is selected")
        branch_id = _text(branch_id, "branch_id")
        native_task_ids = self._native_model_task_ids(
            member_id, selected, branch_id=branch_id
        )
        control: dict[str, Any] = {
            "operation": "commit",
            "branch_id": branch_id,
            "require_no_reference_escape": require_no_reference_escape,
        }
        if expected_base_sha256 is not None:
            control["expected_base_sha256"] = _text(
                expected_base_sha256, "expected_base_sha256"
            )
        result = self.step(member_id, task_id=selected, control=control)
        cleanup = self._drop_native_model_tasks(
            member_id, selected, native_task_ids=native_task_ids
        )
        return {**dict(result), "branch_model_cleanup": list(cleanup)}

    def rollback_branch(
        self, member_id: str, branch_id: str, *, task_id: str | None = None
    ) -> Mapping[str, Any]:
        selected = task_id or self._member(member_id).selected_task_id
        if not isinstance(selected, str):
            raise ProgrammableSwarmError("no field program task is selected")
        branch_id = _text(branch_id, "branch_id")
        native_task_ids = self._native_model_task_ids(
            member_id, selected, branch_id=branch_id
        )
        result = self.step(
            member_id,
            task_id=selected,
            control={"operation": "rollback", "branch_id": branch_id},
        )
        cleanup = self._drop_native_model_tasks(
            member_id, selected, native_task_ids=native_task_ids
        )
        return {**dict(result), "branch_model_cleanup": list(cleanup)}

    def cancel(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        reason: str = "cancelled",
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={"operation": "cancel", "reason": reason},
        )

    def pause(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        reason: str = "requested",
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={"operation": "pause", "reason": reason},
        )

    def continue_task(
        self, member_id: str, *, task_id: str | None = None
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={"operation": "continue"},
        )

    def revoke(
        self,
        member_id: str,
        capability: str,
        *,
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={"operation": "revocation", "capability": capability},
        )

    def resume_external(
        self,
        member_id: str,
        operation_id: str,
        *,
        task_id: str | None = None,
        value: Any = None,
        exception: str | None = None,
        exception_type: str = "RuntimeError",
    ) -> Mapping[str, Any]:
        control: dict[str, Any] = {
            "operation": "resume",
            "operation_id": _text(operation_id, "operation_id"),
        }
        if exception is None:
            control["value"] = _plain(value)
        else:
            control["exception"] = exception
            control["exception_type"] = exception_type
        return self.step(member_id, task_id=task_id, control=control)

    def resume_external_model(
        self,
        member_id: str,
        operation_id: str,
        result: Mapping[str, Any],
        *,
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={
                "operation": "resume-external",
                "operation_id": _text(operation_id, "operation_id"),
                "result": _plain(result),
            },
        )

    def begin_speculation(
        self,
        member_id: str,
        draft_tokens: Sequence[int],
        *,
        task_id: str | None = None,
        draft_program_id: str = "attributed-draft",
    ) -> Mapping[str, Any]:
        return self.step(
            member_id,
            task_id=task_id,
            control={
                "operation": "begin-speculation",
                "draft_tokens": [int(token) for token in draft_tokens],
                "draft_program_id": _text(draft_program_id, "draft_program_id"),
            },
        )

    def workspace_command(
        self,
        member_id: str,
        command: Mapping[str, Any],
        *,
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        selected = task_id or member.workspace_task_id
        if selected is None:
            raise ProgrammableSwarmError("member has no selected research workspace")
        return self.step(
            member_id,
            task_id=selected,
            steps=1,
            control=command,
        )

    def repair(
        self,
        member_id: str,
        source: str,
        *,
        frame_id: str,
        pc: int = 0,
        filename: str = "<repair>",
        task_id: str | None = None,
    ) -> Mapping[str, Any]:
        program = compile_python(source, source_name=filename)
        return self.step(
            member_id,
            task_id=task_id,
            control={
                "operation": "repair",
                "program": program.as_dict(),
                "frame_id": _text(frame_id, "frame_id"),
                "pc": pc,
            },
        )

    def refresh_residency(
        self, member_id: str, *, placement: str | None = None
    ) -> Mapping[str, Any]:
        member = self._member(member_id)
        if member.runtime is None:
            raise ProgrammableSwarmError("member has no resident runtime")
        computer = self._computer(member)
        if computer is None:
            raise ProgrammableSwarmError("member computer is not configured")
        from cassi_regional_catalog import STANDARD_KERNEL_CATALOG

        selected_placement = placement or (
            "native-cpu" if member.placement == "logical-cpu" else member.placement
        )
        prior = getattr(member.runtime, "_attachments", {}).get(member.member_id)
        transfer_started_ns = time.perf_counter_ns()
        attachment = member.runtime.attach(
            member.member_id,
            computer.field,
            state_sha256=computer.state_sha256,
            catalog_sha256=STANDARD_KERNEL_CATALOG.fingerprint,
            fence=member.fence,
            placement=selected_placement,
        )
        native_owner = getattr(member.owner, "raw_owner", member.owner)
        bind_runtime = getattr(native_owner, "bind_regional_runtime", None)
        if callable(bind_runtime):
            bind_runtime(member.computer_id, member.runtime, member.member_id,
                selected_placement)
        if prior is not None and attachment.image is prior.image:
            return attachment.descriptor()  # resident image reused, nothing moved
        transfer_seconds = (time.perf_counter_ns() - transfer_started_ns) / 1e9
        resident_bytes = len(attachment.image.payload)
        native_client = getattr(member.runtime, "_native_client", None)
        if native_client is not None:
            try:
                backend_policy.record_capability(native_client.status())
            except Exception:
                pass  # capability evidence stays absent, never invented
        backend_policy.record_cost(
            selected_placement,
            scope="residency",
            copy_bytes=resident_bytes,
            copy_seconds=transfer_seconds,
            resident_bytes=resident_bytes,
        )
        return attachment.descriptor()

    @staticmethod
    def _resident_vram_device(
        runtime: ResidentFieldRuntime, admission: Any
    ) -> str | None:
        """Resolve the registered device that must charge a vulkan candidate.

        The resident service's reported device index is matched against the
        admission manager's declared vram devices.  Exactly one registered
        device is the single-device default; a known resident index that is
        not declared, or several devices without a match, refuses instead of
        guessing.  No declaration at all keeps the legacy default-device
        accounting until owner glue registers the physical device.
        """

        manager = getattr(admission, "manager", None)
        registered = getattr(manager, "_vram_devices", None)
        registered = dict(registered) if isinstance(registered, Mapping) else {}
        report = runtime.device_report()
        index = (
            report.get("device_index") if isinstance(report, Mapping) else None
        )
        if isinstance(index, int) and not isinstance(index, bool):
            key = str(index)
            if key in registered:
                return key
            if registered:
                raise ProgrammableSwarmError(
                    f"resident device index {index} is not declared for physical admission"
                )
            return None
        keys = sorted(registered)
        if not keys:
            return None
        if len(keys) == 1:
            return keys[0]
        raise ProgrammableSwarmError(
            "vulkan placement cannot select between registered vram devices "
            f"{keys} without a matching resident device index"
        )

    def migrate_member_placement(
        self,
        member_id: str,
        *,
        candidate_placement: str,
        bounded_remaining_work: int | None = None,
    ) -> Mapping[str, Any]:
        """Promote a member's resident placement only at a safe boundary.

        The move is admitted only when no candidate is in flight, the
        published predecessor identity (exact state digest and fence) is
        still valid, and a bounded remaining-work forecast strictly beats
        the measured migration cost: probed setup plus a copy charged on
        both source and destination until the old representation retires.
        Without complete measured evidence the placement is held; nothing
        migrates on an unmeasured guess.
        """
        member = self._member(member_id)
        if member.runtime is None:
            raise ProgrammableSwarmError("member has no resident runtime")
        if candidate_placement not in {"native-cpu", "vulkan"}:
            raise ProgrammableSwarmError("member placement is invalid")
        if candidate_placement == member.placement:
            return {
                "decision": "hold",
                "current": member.placement,
                "candidate": candidate_placement,
                "reason": "already-placed",
                "measured": None,
            }
        computer = self._computer(member)
        if computer is None:
            raise ProgrammableSwarmError("member computer is not configured")
        runtime = member.runtime
        in_flight = getattr(runtime, "_owner_candidate", {}).get(member.member_id)
        attachment = getattr(runtime, "_attachments", {}).get(member.member_id)
        device_report = (
            runtime.device_report() if getattr(runtime, "_native_client", None) else None
        )
        candidate_index = (
            device_report.get("device_index")
            if isinstance(device_report, Mapping)
            else None
        )
        if not (
            isinstance(candidate_index, int) and not isinstance(candidate_index, bool)
        ):
            candidate_index = None
        if candidate_placement == "vulkan" and candidate_index is None:
            # A vulkan placement claims a physical device; without measured
            # device evidence it would be a false claim, so the move is held
            # before any cost forecast runs.
            return {
                "decision": "hold",
                "current": member.placement,
                "candidate": candidate_placement,
                "reason": "vulkan-device-unknown",
                "measured": None,
            }
        current_index = (
            attachment.device_index if attachment is not None else None
        )
        if (
            current_index is not None
            and candidate_index is not None
            and current_index != candidate_index
        ):
            # Moving the resident backing to a different physical device would
            # need source and destination reservations plus exact owner
            # version/dependency fencing; the native service has no
            # synchronized cross-device resident move, so refuse cleanly
            # rather than claim one.
            return {
                "decision": "hold",
                "current": member.placement,
                "candidate": candidate_placement,
                "reason": "cross-device-resident-migration-unsupported",
                "measured": None,
            }
        boundary_safe = (
            in_flight is None
            and attachment is not None
            and attachment.image.state_sha256 == computer.state_sha256
            and attachment.fence == member.fence
        )
        migration_bytes = len(attachment.image.payload) if attachment is not None else 1
        decision = backend_policy.migration_decision(
            current=member.placement,
            candidate=candidate_placement,
            scope="field-program",
            bounded_remaining_work=bounded_remaining_work,
            migration_bytes=migration_bytes,
            predecessor_state_sha256=computer.state_sha256,
            expected_state_sha256=(
                attachment.image.state_sha256 if attachment is not None else None
            ),
            fence=member.fence,
            expected_fence=attachment.fence if attachment is not None else None,
            boundary_safe=boundary_safe,
        )
        if decision["decision"] != "migrate":
            return decision
        descriptor = self.refresh_residency(member_id, placement=candidate_placement)
        member.placement = candidate_placement
        return {**decision, "attachment": descriptor}

    def run_resident_candidate(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        steps: int = 1,
        control: Mapping[str, Any] | None = None,
        lease_id: str | None = None,
        operation_id: str | None = None,
        predecessor_state_sha256: str | None = None,
        predecessor_computer_state_sha256: str | None = None,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
        _native_graph_site: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Execute a CPU-produced private candidate and publish it once through its owner.

        The owner admits the immutable successor against the exact atlas and
        computer predecessors. Resident field-runtime state is a disposable
        packed mirror; it is not the computation backend for this operation.
        No effect request is dispatched by candidate execution or publication.
        """
        member = self._member(member_id)
        runtime = member.runtime
        if runtime is None:
            raise ProgrammableSwarmError("member has no resident runtime")
        predecessor = self._computer(member)
        if predecessor is None:
            raise ProgrammableSwarmError("member computer is not configured")
        current_owner_state_sha256 = member.owner.state.state_sha256
        current_computer_state_sha256 = predecessor.state_sha256
        selected = task_id or member.selected_task_id
        if selected is None:
            state = (
                _runtime_state_snapshot
                if _runtime_state_snapshot is not None
                else self._runtime_state(member_id)
            )
            selected = state.get("selected_task_id")
        if not isinstance(selected, str):
            raise ProgrammableSwarmError("no field program task is selected")
        placement = self._task_placement(
            member_id,
            selected,
            _runtime_state_snapshot=_runtime_state_snapshot,
        )
        if placement not in {"native-cpu", "vulkan"}:
            raise ProgrammableSwarmError(
                "resident execution requires a native-cpu or vulkan task"
            )
        runtime_arguments = {
            "operation": "advance-task",
            "task_id": selected,
            "quantum": steps,
            "arguments": {} if control is None else _plain(control),
        }
        operation_id = operation_id or uuid.uuid4().hex
        prior_snapshot = member.candidate_snapshots.get(operation_id)
        owner_predecessor_sha256 = (
            predecessor_state_sha256
            if predecessor_state_sha256 is not None
            else (
                prior_snapshot[0]
                if prior_snapshot is not None
                else current_owner_state_sha256
            )
        )
        computer_predecessor_sha256 = (
            predecessor_computer_state_sha256
            if predecessor_computer_state_sha256 is not None
            else (
                prior_snapshot[1]
                if prior_snapshot is not None
                else current_computer_state_sha256
            )
        )
        member.candidate_snapshots.setdefault(
            operation_id,
            (owner_predecessor_sha256, computer_predecessor_sha256),
        )
        owner_arguments = {"arguments": runtime_arguments, "steps": 1}
        replay = None
        if _native_graph_site is None:
            replay = member.owner.replay_computer_candidate(
                operation_id,
                computer_id=member.computer_id,
                action="invoke",
                arguments=owner_arguments,
                expected_state_sha256=owner_predecessor_sha256,
                predecessor_computer_state_sha256=computer_predecessor_sha256,
            )
        if replay is not None:
            receipt = replay.get("receipt")
            published = self._computer(member)
            if (
                not isinstance(receipt, Mapping)
                or published is None
                or (
                    published.state_sha256
                    != receipt.get("computer_logical_state_sha256")
                    if "computer_logical_state_sha256" in receipt
                    else _digest(published.as_dict())
                    != receipt.get("computer_state_sha256")
                )
            ):
                raise ProgrammableSwarmError(
                    "resident candidate replay differs from the retained computer"
                )
            self.ensure_program_runtime(
                member_id,
                _runtime_state_snapshot=_runtime_state_snapshot,
            )
            self.refresh_residency(member_id, placement=placement)
            return {
                "schema": SWARM_RESULT_SCHEMA,
                "status": "replayed",
                "placement": placement,
                "operation_id": operation_id,
                "predecessor_state_sha256": owner_predecessor_sha256,
                "predecessor_computer_state_sha256": computer_predecessor_sha256,
                "receipt": dict(receipt),
                "checkpoint_receipt": dict(replay["checkpoint_receipt"]),
                "computer": published.as_dict(),
            }
        if (
            owner_predecessor_sha256 != current_owner_state_sha256
            or computer_predecessor_sha256 != current_computer_state_sha256
        ):
            raise ProgrammableSwarmError(
                "resident candidate predecessors changed before admission"
            )
        self.ensure_program_runtime(
            member_id,
            _runtime_state_snapshot=_runtime_state_snapshot,
        )
        lease = lease_id or uuid.uuid4().hex
        admission = getattr(member.owner, "physical_admission", None)
        attempt = 1
        if admission is not None:
            while True:
                attempt_status = admission.get_activity_status(
                    f"resident-candidate:{operation_id}:attempt:{attempt}"
                )["status"]
                if attempt_status == "not-admitted":
                    break
                if attempt_status != "retired":
                    raise ProgrammableSwarmError(
                        "resident candidate has a prior physical attempt requiring reconciliation"
                    )
                attempt += 1
        field_bytes = max(0, int(predecessor.nbytes))
        physical_resources = {
            "physical_cores": 1,
            "ram_bytes": field_bytes * 4,
            "vram_bytes": field_bytes if placement == "vulkan" else 0,
            "transfer_bytes": field_bytes * 2,
            "peak_bytes": field_bytes,
        }
        vram_device = (
            self._resident_vram_device(runtime, admission)
            if placement == "vulkan" and admission is not None
            else None
        )
        physical_lease = (
            admission.acquire(
                f"resident-candidate:{operation_id}:attempt:{attempt}",
                priority="foreground",
                continuation_id=operation_id,
                locality_id=hashlib.sha256(
                    f"{admission.owner_id}\0{predecessor.state_sha256}".encode("utf-8")
                ).hexdigest(),
                batch_id=hashlib.sha256(
                    f"{predecessor.state_sha256}\0{placement}\0one".encode("utf-8")
                ).hexdigest(),
                resources=physical_resources,
                vram_device=vram_device,
            )
            if admission is not None
            else None
        )
        owner_published = False
        cache_confirmed = False
        candidate_id: str | None = None
        try:
            if physical_lease is not None:
                physical_lease.mark_stage("transfer", "start")
            try:
                self.refresh_residency(member_id, placement=placement)
            finally:
                if physical_lease is not None:
                    physical_lease.mark_stage("transfer", "end")
            candidate_id = runtime.begin_candidate(
                member.member_id,
                predecessor_state_sha256=predecessor.state_sha256,
                fence=member.fence,
                lease_id=lease,
                placement=placement,
            )
            if physical_lease is not None:
                if placement == "native-cpu":
                    cache_bytes = min(field_bytes, admission.manager.limits.cpu_cache_bytes)
                    physical_lease.reserve_cache_window(cache_bytes)
                compute_started_ns = physical_lease.mark_stage("compute", "start")
            else:
                compute_started_ns = time.perf_counter_ns()
            graph_publication: MutableMapping[str, Any] | None = None
            if _native_graph_site is not None:
                if not isinstance(_native_graph_site, MutableMapping):
                    raise ProgrammableSwarmError(
                        "native graph-site dispatch plan is not mutable"
                    )
                graph_step_started_ns = time.perf_counter_ns()
                graph_step = runtime.step_model(
                    _native_graph_site["task_id"],
                    _native_graph_site["source_sha256"],
                    _native_graph_site["tokens"],
                    sampler_mode=_native_graph_site["sampler"]["mode"],
                    temperature=_native_graph_site["sampler"]["temperature"],
                    top_k=_native_graph_site["sampler"]["top_k"],
                    draw=_native_graph_site["sampler"]["draw"],
                    native_operation_id=_native_graph_site[
                        "native_operation_id"
                    ],
                    sequence_id=_native_graph_site["sequence_id"],
                    candidate_id=candidate_id,
                    graph_site_ticket=_native_graph_site["ticket"],
                )
                if not isinstance(graph_step, Mapping):
                    raise ProgrammableSwarmError(
                        "native graph-site step returned an invalid result"
                    )
                control_arguments = runtime_arguments.get("arguments")
                if not isinstance(control_arguments, MutableMapping):
                    raise ProgrammableSwarmError(
                        "native model control arguments are not mutable"
                    )
                if graph_step.get("status") == "graph-site-rejected":
                    refusal_receipt = graph_step.get("graph_site_receipt")
                    if not isinstance(refusal_receipt, Mapping):
                        raise ProgrammableSwarmError(
                            "native graph-site refusal omitted its measured receipt"
                        )
                    cancellation = runtime.cancel_candidate(candidate_id)
                    if cancellation.get("status") not in {
                        "cancelled",
                        "already-retired",
                    }:
                        raise ProgrammableSwarmError(
                            "refused graph-site candidate cancellation was not confirmed"
                        )
                    candidate_id = None
                    rejection = {
                        "receipt": _plain(refusal_receipt),
                        "receipt_sha256": graph_step[
                            "native_graph_site_receipt_sha256"
                        ],
                        "wire_sha256": graph_step[
                            "graph_receipt_wire_sha256"
                        ],
                    }
                    fallback_step = runtime.step_model(
                        _native_graph_site["task_id"],
                        _native_graph_site["source_sha256"],
                        _native_graph_site["tokens"],
                        sampler_mode=_native_graph_site["sampler"]["mode"],
                        temperature=_native_graph_site["sampler"]["temperature"],
                        top_k=_native_graph_site["sampler"]["top_k"],
                        draw=_native_graph_site["sampler"]["draw"],
                    )
                    if not isinstance(fallback_step, Mapping):
                        raise ProgrammableSwarmError(
                            "ordinary native fallback returned an invalid result"
                        )
                    fallback_result = dict(fallback_step)
                    fallback_result["graph_site_rejection"] = rejection
                    control_arguments["result"] = fallback_result
                    _native_graph_site.update(
                        {
                            "accepted": False,
                            "result": fallback_result,
                            "rejection": rejection,
                        }
                    )
                    candidate_id = runtime.begin_candidate(
                        member.member_id,
                        predecessor_state_sha256=predecessor.state_sha256,
                        fence=member.fence,
                        lease_id=lease,
                        placement=placement,
                    )
                elif (
                    graph_step.get("accepted") is False
                    and graph_step.get("provisional") is True
                ):
                    graph_publication = {
                        **dict(_native_graph_site),
                        "accepted": True,
                        "field_candidate_id": candidate_id,
                        "receipt": _plain(
                            graph_step["graph_site_receipt"]
                        ),
                        "receipt_sha256": graph_step[
                            "native_graph_site_receipt_sha256"
                        ],
                        "wire_sha256": graph_step[
                            "graph_receipt_wire_sha256"
                        ],
                        "step": _plain(graph_step),
                        "result": _plain(graph_step),
                    }
                    _native_graph_site.update(graph_publication)
                    control_arguments["result"] = _plain(graph_step)
                    control_arguments["native_graph_site"] = {
                        "ticket": graph_publication["ticket"],
                        "receipt": graph_publication["receipt"],
                        "native_graph_site_receipt_sha256": graph_publication[
                            "receipt_sha256"
                        ],
                        "graph_receipt_wire_sha256": graph_publication[
                            "wire_sha256"
                        ],
                        "field_candidate_id": candidate_id,
                        "step": graph_publication["step"],
                    }
                else:
                    raise ProgrammableSwarmError(
                        "native graph-site step was neither measured nor refused"
                    )
                graph_step_elapsed = (
                    time.perf_counter_ns() - graph_step_started_ns
                ) / 1e9
                backend_policy.record_cost(
                    placement,
                    scope="model-transformer",
                    work=len(_native_graph_site["tokens"]),
                    use_seconds=graph_step_elapsed,
                )
            try:
                candidate_row, candidate_receipt = predecessor.invoke(
                    arguments=runtime_arguments, steps=1
                )
            except BaseException:
                raise
            else:
                if physical_lease is not None:
                    compute_ended_ns = physical_lease.mark_stage("compute", "end")
                    physical_lease.release_cache_window()
                else:
                    compute_ended_ns = time.perf_counter_ns()
            changed_pages: tuple[int, ...] | None = None
            run_receipt = candidate_receipt.get("run")
            transition_receipts = (
                run_receipt.get("transition_receipts")
                if isinstance(run_receipt, Mapping)
                else None
            )
            if isinstance(transition_receipts, (list, tuple)):
                reported_pages: set[int] = set()
                for transition_receipt in transition_receipts:
                    commit = (
                        transition_receipt.get("commit")
                        if isinstance(transition_receipt, Mapping)
                        else None
                    )
                    pages = commit.get("changed_pages") if isinstance(commit, Mapping) else None
                    if isinstance(pages, (list, tuple)) and all(
                        isinstance(page, int) and not isinstance(page, bool) and page >= 0
                        for page in pages
                    ):
                        reported_pages.update(pages)
                if reported_pages:
                    changed_pages = tuple(sorted(reported_pages))

            from cassi_regional_catalog import STANDARD_KERNEL_CATALOG

            if physical_lease is not None:
                physical_lease.mark_stage("commit", "start")
            logical_work = int(candidate_receipt.get("work", 0))
            candidate = runtime.settle_candidate(
                candidate_id,
                candidate_row.field,
                state_sha256=candidate_row.state_sha256,
                catalog_sha256=STANDARD_KERNEL_CATALOG.fingerprint,
                logical_transitions=min(logical_work, runtime.max_epoch_transitions),
                dispatches=1 if logical_work else 0,
                events=tuple(candidate_receipt.get("events", ())),
                errors=(),
                changed_pages=changed_pages,
            )
            backend_policy.record_cost(
                candidate.placement,
                scope="field-program",
                work=logical_work,
                use_seconds=(compute_ended_ns - compute_started_ns) / 1e9,
            )
            runtime.validate_for_publication(
                candidate_id,
                owner_state_sha256=predecessor.state_sha256,
                fence=member.fence,
                lease_id=lease,
            )
            publish_arguments: dict[str, Any] = {}
            if graph_publication is not None:
                publish_arguments = {
                    "field_candidate_id": candidate_id,
                    "graph_ticket": graph_publication["ticket"],
                    "native_graph_site_receipt": graph_publication["receipt"],
                    "native_graph_site_receipt_sha256": graph_publication[
                        "receipt_sha256"
                    ],
                    "graph_receipt_wire_sha256": graph_publication["wire_sha256"],
                    "native_graph_site_step": graph_publication["step"],
                }
            publication = member.owner.publish_computer_candidate(
                operation_id,
                computer_id=member.computer_id,
                action="invoke",
                arguments=owner_arguments,
                expected_state_sha256=owner_predecessor_sha256,
                predecessor_computer_state_sha256=computer_predecessor_sha256,
                candidate_row=candidate_row,
                candidate_receipt=candidate_receipt,
                **publish_arguments,
            )
            owner_published = True
            owner_ack: Mapping[str, Any] | None = None
            if graph_publication is not None:
                owner_ack = publication.get("native_graph_site_ack")
                if not isinstance(owner_ack, Mapping):
                    raise ProgrammableSwarmError(
                        "native graph-site publication omitted its owner acknowledgment"
                    )
                _native_graph_site["owner_ack"] = _plain(owner_ack)
            published = self._computer(member)
            if published is None or published.state_sha256 != candidate.image.state_sha256:
                raise ProgrammableSwarmError(
                    "owner-admitted resident candidate disagrees with its published state"
                )
            confirm_arguments: dict[str, Any] = {}
            if owner_ack is not None:
                confirm_arguments = {
                    "owner_ack": owner_ack,
                    "graph_site_receipt_sha256": graph_publication["receipt_sha256"],
                }
            resident_receipt = runtime.confirm_publication(
                candidate_id,
                owner_state_sha256=published.state_sha256,
                fence=member.fence,
                lease_id=lease,
                **confirm_arguments,
            )
            if physical_lease is not None:
                physical_lease.mark_stage("commit", "end")
            cache_confirmed = True
            member.fence += 1
            if physical_lease is not None:
                physical_lease.retire(status="completed")
            return {
                "schema": SWARM_RESULT_SCHEMA,
                "operation_id": operation_id,
                "predecessor_state_sha256": owner_predecessor_sha256,
                "predecessor_computer_state_sha256": computer_predecessor_sha256,
                "candidate": candidate.descriptor(),
                "requested_placement": placement,
                "placement": candidate.placement,
                "backend_evidence": {
                    "observed_use_seconds": (compute_ended_ns - compute_started_ns) / 1e9,
                    "observed_work": logical_work,
                    "capability": backend_policy.observed_capability(),
                    "device": runtime.device_report(),
                    "physical_vram_device": physical_lease.vram_device
                    if physical_lease is not None
                    else None,
                },
                "publication": _plain(publication),
                "residency": _plain(resident_receipt),
                "candidate_execution": "owner-admitted-private-candidate",
                "authoritative_publisher": "field-owner",
            }
        except BaseException as exc:
            if physical_lease is not None:
                physical_lease.finish_open_stages()
            if owner_published and cache_confirmed:
                reservation_id = (
                    physical_lease.reservation_id
                    if physical_lease is not None
                    else None
                )
                fence_error = None
                if physical_lease is not None:
                    try:
                        physical_lease.fence(
                            f"owner and native cache confirmed for candidate {candidate_id}; physical lease settlement requires reconciliation"
                        )
                    except BaseException as fence_exc:
                        fence_error = str(fence_exc)
                return {
                    "schema": SWARM_RESULT_SCHEMA,
                    "status": "physical-reconciliation-required",
                    "candidate_id": candidate_id,
                    "candidate": candidate.descriptor(),
                    "publication": _plain(publication),
                    "checkpoint_receipt": _plain(
                        publication.get("checkpoint_receipt")
                    ),
                    "residency": _plain(resident_receipt),
                    "physical_reservation_id": reservation_id,
                    "physical_lease_fenced": (
                        physical_lease is not None and fence_error is None
                    ),
                    "physical_lease_fence_error": fence_error,
                }
            if owner_published and not cache_confirmed:
                reservation_id = (
                    physical_lease.reservation_id
                    if physical_lease is not None
                    else None
                )
                fence_error = None
                if physical_lease is not None:
                    try:
                        physical_lease.fence(
                            f"owner published candidate {candidate_id}; native cache confirmation requires reconciliation"
                        )
                    except BaseException as fence_exc:
                        fence_error = str(fence_exc)
                return {
                    "schema": SWARM_RESULT_SCHEMA,
                    "status": "cache-reconciliation-required",
                    "candidate_id": candidate_id,
                    "candidate": candidate.descriptor(),
                    "candidate_execution": "owner-admitted-private-candidate",
                    "native_candidate_status": "retained-private",
                    "publication": _plain(publication),
                    "checkpoint_receipt": _plain(
                        publication.get("checkpoint_receipt")
                    ),
                    "physical_reservation_id": reservation_id,
                    "physical_lease_fenced": (
                        physical_lease is not None and fence_error is None
                    ),
                    "physical_lease_fence_error": fence_error,
                    "reconciliation_error": str(exc),
                }
            cancellation_confirmed = candidate_id is None
            if candidate_id is not None and not owner_published:
                try:
                    cancellation = runtime.cancel_candidate(candidate_id)
                    cancellation_confirmed = cancellation.get("status") in {
                        "cancelled",
                        "already-retired",
                    }
                except BaseException:
                    cancellation_confirmed = False
            if physical_lease is not None:
                if cancellation_confirmed:
                    physical_lease.retire(status="failed")
                else:
                    physical_lease.fence(
                        f"candidate {candidate_id} cancellation was not confirmed"
                    )
            if not cancellation_confirmed:
                raise ProgrammableSwarmError(
                    "native candidate cancellation was not confirmed; physical lease fenced"
                ) from exc
            raise

    def recover_runtime(self, runtime: ResidentFieldRuntime) -> Mapping[str, Any]:
        recovered: list[str] = []
        for member_id in self.member_ids:
            member = self._members[member_id]
            if member.runtime is runtime:
                member.fence += 1
                self.refresh_residency(member_id)
                recovered.append(member_id)
        return {
            "status": "reattached",
            "service_generation": runtime.service_generation,
            "member_ids": recovered,
        }

    def contribution(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        program_id: str | None = None,
        kind: str = "python-program",
        contribution_id: str | None = None,
        dependencies: Sequence[str] = (),
        applicability: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        observed_behavior: Mapping[str, Any] | None = None,
        lineage: Sequence[str] = (),
    ) -> ProgrammableContribution:
        state = self.raw_state(member_id, task_id=task_id)
        artifact_row: Mapping[str, Any] | None = None
        if kind == "compiled-method":
            if state.get("schema") != PYTHON_RUNTIME_SCHEMA:
                raise ProgrammableSwarmError(
                    "compiled methods require a resident Python computation"
                )
            if not isinstance(artifact_id, str) or not artifact_id:
                raise ProgrammableSwarmError(
                    "compiled method contribution requires an artifact_id"
                )
            candidate = state.get("optimizer", {}).get("artifacts", {}).get(
                artifact_id
            )
            if not isinstance(candidate, Mapping):
                raise ProgrammableSwarmError(
                    "compiled artifact is not resident in member state"
                )
            artifact_row = candidate
            record = candidate["artifact"]
        elif state.get("schema") == PYTHON_RUNTIME_SCHEMA:
            selected = program_id or state["identity"]["program_id"]
            try:
                record = state["programs"][selected]
            except KeyError as exc:
                raise ProgrammableSwarmError(
                    "program is not resident in member state"
                ) from exc
        elif state.get("schema") == MODEL_RUNTIME_SCHEMA:
            selected = program_id or state["package"]["program"]["program_id"]
            if selected != state["package"]["program"]["program_id"]:
                raise ProgrammableSwarmError(
                    "model program is not resident in member state"
                )
            record = state["package"]
        elif state.get("schema") == WORKSPACE_SCHEMA:
            if program_id is None:
                raise ProgrammableSwarmError(
                    "workspace contribution requires a resident record id"
                )
            try:
                record = state["objects"][program_id]
            except KeyError as exc:
                raise ProgrammableSwarmError(
                    "workspace record is not resident in member state"
                ) from exc
        else:
            raise ProgrammableSwarmError(
                "member task cannot produce a contribution"
            )
        inherited_dependencies = tuple(record.get("dependencies", ()))
        resolved_applicability = applicability or {}
        resolved_behavior = observed_behavior or {}
        if artifact_row is not None:
            resolved_applicability = applicability or {
                "target_profile": record["target_profile"],
                "program_id": record["program_id"],
                "program_sha256": record["program_sha256"],
            }
            resolved_behavior = observed_behavior or {
                "hits": int(artifact_row["hits"]),
                "deoptimizations": int(artifact_row["deoptimizations"]),
                "logical_work": int(artifact_row["logical_work"]),
                "physical_work": int(artifact_row["physical_work"]),
            }
        return ProgrammableContribution(
            contribution_id=contribution_id
            or f"program-{_digest(record)[:24]}",
            provider_member_id=member_id,
            kind=kind,
            record=record,
            dependencies=tuple(dependencies) or inherited_dependencies,
            applicability=resolved_applicability,
            observed_behavior=resolved_behavior,
            lineage=tuple(lineage),
        )

    def admit_contribution(
        self,
        member_id: str,
        contribution_value: ProgrammableContribution | Mapping[str, Any],
        *,
        task_id: str | None = None,
        steps: int = 0,
    ) -> Mapping[str, Any]:
        contribution = (
            contribution_value
            if isinstance(contribution_value, ProgrammableContribution)
            else ProgrammableContribution.from_dict(contribution_value)
        )
        if contribution.kind == "compiled-method":
            if task_id is None:
                raise ProgrammableSwarmError(
                    "compiled method admission requires a target task_id"
                )
            return self.step(
                member_id,
                task_id=task_id,
                steps=1,
                control={
                    "operation": "admit-optimization",
                    "artifact": contribution.record,
                    "contribution_sha256": contribution.sha256,
                    "provider_member_id": contribution.provider_member_id,
                },
            )
        if contribution.record.get("schema") == PythonProgram.SCHEMA:
            return self.start_python(
                member_id,
                contribution.record,
                task_id=task_id or contribution.contribution_id,
                steps=steps,
                lineage_id=contribution.sha256,
                operation_id=contribution.contribution_id,
            )
        raise ProgrammableSwarmError(
            "contribution is not an executable program or compiled method"
        )


    @staticmethod
    def publish_contribution(
        hive_field: Any,
        contribution: ProgrammableContribution,
        *,
        domain: str,
        branch_id: str,
        reliability: float,
        work_units: int,
        roles: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        from cassi_hive_collective import HiveOffer
        from cassi_hive_store import make_document

        document = make_document(CONTRIBUTION_SCHEMA, contribution.as_dict())
        candidate_id = hive_field.hive.put_document(document)
        offer = HiveOffer(
            offer_id=f"offer-{contribution.sha256[:24]}",
            provider_instance_id=hive_field.identity.instance_id,
            candidate_id=candidate_id,
            kind=contribution.kind,
            domain=_text(domain, "domain"),
            branch_id=_text(branch_id, "branch_id"),
            reliability=float(reliability),
            work_units=work_units,
            roles=tuple(roles),
            diversity_keys=(contribution.provider_member_id, contribution.sha256),
        )
        offer_id = hive_field.skills.publish_offer(offer)
        return {
            "contribution_sha256": contribution.sha256,
            "candidate_id": candidate_id,
            "offer_id": offer_id,
        }

    @staticmethod
    def load_contribution(hive_field: Any, candidate_id: str) -> ProgrammableContribution:
        document = hive_field.hive.get_document(candidate_id)
        if document.get("schema") != CONTRIBUTION_SCHEMA:
            raise ProgrammableSwarmError("hive candidate is not a programmable contribution")
        content = document.get("content")
        if not isinstance(content, Mapping):
            raise ProgrammableSwarmError("hive contribution content is invalid")
        return ProgrammableContribution.from_dict(content)


__all__ = [
    "CONTRIBUTION_SCHEMA",
    "PROGRAM_COMPUTER_PROFILE",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "SWARM_RESULT_SCHEMA",
    "ProgrammableContribution",
    "ProgrammableSwarm",
    "ProgrammableSwarmError",
    "regional_kernel",
    "regional_state",
]
