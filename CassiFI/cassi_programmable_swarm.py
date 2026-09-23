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
import uuid
from typing import Any, Mapping, MutableMapping, Sequence

from cassi_field_runtime import FieldRuntimeError, ResidentFieldRuntime
from cassi_learning_computer import LearningComputer
from programs.model.kernel import (
    REGIONAL_KERNEL_MAX_WORK as MODEL_KERNEL_MAX_WORK,
    REGIONAL_STATE_SCHEMA as MODEL_STATE_SCHEMA,
    regional_state as model_regional_state,
)
from programs.model.records import ModelPackage
from programs.model.runtime import RUNTIME_SCHEMA as MODEL_RUNTIME_SCHEMA, computation_view as model_view
from programs.model.runtime import seed_resident_prefix
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
# The native field runtime carries one computer image in a single staging
# payload, and that payload is bounded at 64 MiB on both sides of the pipe.
NATIVE_FIELD_PAYLOAD_BYTES = 64 << 20
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


class ProgrammableSwarm:
    """Coordinate field computations without merging independent member owners."""

    def __init__(self) -> None:
        self._members: MutableMapping[str, _Member] = {}
        self._model_backings: MutableMapping[str, Mapping[str, Any]] = {}
        self._resident_models: MutableMapping[str, Any] = {}

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
        if member.runtime is not None:
            if (
                isinstance(runtime_state, Mapping)
                and runtime_state.get("schema") == REGIONAL_STATE_SCHEMA
            ):
                for task_id, task in runtime_state.get("tasks", {}).items():
                    if isinstance(task, Mapping) and task.get("kind") == "model":
                        self._drop_native_model_tasks(member_id, str(task_id))
            member.runtime.detach(member.member_id)
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
        limits = getattr(member.owner, "limits", None)
        if limits is None:
            limits = getattr(getattr(member.owner, "raw_owner", None), "limits", None)
        ceiling = int(getattr(limits, "max_logical_bytes", 0) or 0)
        # A native runtime transports one computer image as a single staging
        # payload, and that payload has a declared bound, so growth of a
        # native-attached computer stops at the smaller of the two ceilings,
        # with a margin for the frame's own fields.
        bound = NATIVE_FIELD_PAYLOAD_BYTES - (1 << 20)
        ceiling = min(ceiling or bound, bound)
        bytes_per_mode = max(1, int(computer.nbytes) // max(1, current))
        target = min(target, max(1, (ceiling - 1) // bytes_per_mode))
        if target <= current:
            # The allocation cannot grow further, but its regions still can.
            # A same-size relayout gives every occupied value region the room
            # the faulted write needed, which is the only remedy left once the
            # image has reached its staging bound.
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
        steps: int = 1,
        lineage_id: str | None = None,
        operation_id: str | None = None,
        task_id: str | None = None,
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
                        and metadata.get("backend") == getattr(executor, "backend", None)
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
    def _drop_native_model_tasks(
        self,
        member_id: str,
        task_id: str,
        *,
        native_task_ids: Sequence[str] | None = None,
    ) -> Sequence[Mapping[str, Any]]:
        member = self._member(member_id)
        if member.runtime is None:
            return ()
        task_ids = (
            tuple(native_task_ids)
            if native_task_ids is not None
            else self._native_model_task_ids(member_id, task_id)
        )
        receipts: list[Mapping[str, Any]] = []
        for native_task_id in sorted(set(task_ids)):
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
            raise ProgrammableSwarmError(
                "native model source is not bound to an exact local GGUF backing"
            )
        registration = runtime.register_model(
            source_sha256,
            str(binding["path"]),
            context_size=int(binding["context_size"]),
            gpu_layers=int(binding["gpu_layers"]),
        )
        sampler = request.get("sampler")
        tokens = request.get("tokens")
        if not isinstance(sampler, Mapping) or not isinstance(tokens, Sequence):
            raise ProgrammableSwarmError("native model request payload is invalid")
        result = runtime.step_model(
            str(request["native_task_id"]),
            source_sha256,
            tuple(int(token) for token in tokens),
            sampler_mode=str(sampler.get("mode", "greedy")),
            temperature=float(sampler.get("temperature", 1.0)),
            top_k=int(sampler.get("top_k", 0)),
            draw=float(sampler.get("draw", 0.0)),
        )
        placement = self._task_placement(
            member_id,
            task_id,
            _runtime_state_snapshot=_runtime_state_snapshot,
        )
        if placement not in {"native-cpu", "vulkan"}:
            raise ProgrammableSwarmError("native model continuation lost physical placement")
        resumed = self.run_resident_candidate(
            member_id,
            task_id=task_id,
            steps=1,
            control={
                "operation": "resume-native-model",
                "operation_id": operation_id,
                "result": result,
            },
            _runtime_state_snapshot=_runtime_state_snapshot,
        )
        serviced = {
            **dict(resumed),
            "native_model": {
                "registration": _plain(registration),
                "step": _plain(result),
                "proposal_receipt": _plain(prior_receipt),
            },
        }
        if _cleanup:
            view = self.inspect(member_id, task_id=task_id)
            if view["status"] in {"completed", "faulted", "cancelled"}:
                cleanup = self._drop_native_model_tasks(member_id, task_id)
                if cleanup:
                    serviced["model_cleanup"] = list(cleanup)
        return serviced

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
        if placement in {"native-cpu", "vulkan"} and not resident_model:
            if member.runtime is None:
                raise ProgrammableSwarmError(
                    f"task requires unattached backend {placement!r}"
                )
            result = self.run_resident_candidate(
                member_id,
                task_id=selected,
                steps=steps,
                control=control,
                _runtime_state_snapshot=runtime_state,
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
        return _plain(state["tasks"][selected]["state"])

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
        attachment = member.runtime.attach(
            member.member_id,
            computer.field,
            state_sha256=computer.state_sha256,
            catalog_sha256=STANDARD_KERNEL_CATALOG.fingerprint,
            fence=member.fence,
            placement=selected_placement,
        )
        return attachment.descriptor()

    def run_resident_candidate(
        self,
        member_id: str,
        *,
        task_id: str | None = None,
        steps: int = 1,
        control: Mapping[str, Any] | None = None,
        lease_id: str | None = None,
        _runtime_state_snapshot: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Execute and byte-compare a private packed candidate before owner replay.

        Until the native service protocol is connected directly to the owner
        journal, the owner repeats the bounded logical quantum and publishes its
        own successor.  Exact equality then admits the packed result as the new
        disposable resident cache.  No effect request is dispatched by either
        speculative execution or replay.
        """

        member = self._member(member_id)
        runtime = member.runtime
        if runtime is None:
            raise ProgrammableSwarmError("member has no resident runtime")
        self.ensure_program_runtime(
            member_id,
            _runtime_state_snapshot=_runtime_state_snapshot,
        )
        predecessor = self._computer(member)
        if predecessor is None:
            raise ProgrammableSwarmError("member computer is not configured")
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
        self.refresh_residency(member_id, placement=placement)
        lease = lease_id or uuid.uuid4().hex
        candidate_id = runtime.begin_candidate(
            member.member_id,
            predecessor_state_sha256=predecessor.state_sha256,
            fence=member.fence,
            lease_id=lease,
            placement=placement,
        )
        try:
            candidate_row, candidate_receipt = predecessor.invoke(
                arguments=runtime_arguments, steps=1
            )
            from cassi_regional_catalog import STANDARD_KERNEL_CATALOG

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
            )
            publication = member.owner.operate_computer(
                self._operation_id(member, "resident-invoke"),
                computer_id=member.computer_id,
                action="invoke",
                arguments={"arguments": runtime_arguments, "steps": 1},
            )
            published = self._computer(member)
            if published is None or published.state_sha256 != candidate.image.state_sha256:
                runtime.cancel_candidate(candidate_id)
                raise ProgrammableSwarmError(
                    "resident candidate disagrees with authoritative owner execution"
                )
            runtime.validate_for_publication(
                candidate_id,
                owner_state_sha256=predecessor.state_sha256,
                fence=member.fence,
                lease_id=lease,
            )
            resident_receipt = runtime.confirm_publication(
                candidate_id,
                owner_state_sha256=published.state_sha256,
                fence=member.fence,
                lease_id=lease,
            )
            member.fence += 1
            return {
                "schema": SWARM_RESULT_SCHEMA,
                "candidate": candidate.descriptor(),
                "publication": _plain(publication),
                "residency": _plain(resident_receipt),
                "candidate_execution": "mirrored-validation",
                "authoritative_publisher": "field-owner",
            }
        except Exception:
            runtime.cancel_candidate(candidate_id)
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
