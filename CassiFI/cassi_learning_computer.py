"""One public record over the universal regional field computer."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from cassi_computation_policy import (
    METHODS,
    PolicyState,
    _profile_for,
    audit_result,
    compile_source,
    encode_regional_policy,
    initial_policy,
    regional_state as policy_regional_state,
    regional_kernel as policy_regional_kernel,
)
from cassi_constraint_field import (
    REGIONAL_KERNEL_NAME as CONSTRAINT_KERNEL,
    regional_state as constraint_regional_state,
)
from cassi_field_computer import (
    ComputerProfile,
    ComputerState,
    FieldComputer,
    _canonical_instruction,
)
from cassi_field_program import (
    SCALAR_PROCEDURE_KERNEL,
    SCALAR_REGIONAL_KERNEL,
    SCALAR_REGIONAL_STATE_SCHEMA,
    CompiledFieldProgram,
    regional_scalar_state,
)
from cassi_field_regions import RegionalProfile
from cassi_regional_catalog import STANDARD_KERNEL_CATALOG

SCHEMA = "cassifi.learning-computer.v3"
PREVIOUS_SCHEMA = "cassifi.learning-computer.v2"
LEGACY_SCHEMA = "cassifi.learning-computer.v1"
_TASK_WORDS = 98_304
_OUTCOME_WORDS = 98_304
_RESULT_WORDS = 98_304
_POLICY_WORDS = 24_576
_SESSION_WORDS = 16_384
_CONFIG_WORDS = 1_024
_ARGUMENT_WORDS = 16_384
_FRAME_WORDS = _TASK_WORDS
INVOCATION_FRAMES_SCHEMA = "cassifi.learning-computer-invocation-frames.v2"
PREVIOUS_INVOCATION_FRAMES_SCHEMA = "cassifi.learning-computer-invocation-frames.v1"
CHILD_RETURN_SCHEMA = "cassifi.learning-computer-child-return.v2"
PREVIOUS_CHILD_RETURN_SCHEMA = "cassifi.learning-computer-child-return.v1"
ROOT_RESOURCE_NAMES = (
    "branch_count",
    "evidence_reads",
    "frontier_size",
    "model_calls",
    "refinement_depth",
    "storage_words",
    "work",
)


class LearningComputerError(ValueError):
    """Invalid computer image or operation outside its declared bounds."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LearningComputerError("computer value is not canonical JSON") from exc

def _resource_map(
    value: Mapping[str, Any],
    label: str,
    *,
    require_work: bool = False,
) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(ROOT_RESOURCE_NAMES):
        raise LearningComputerError(
            f"{label} must declare every root resource"
        )
    result: dict[str, int] = {}
    for name in ROOT_RESOURCE_NAMES:
        raw = value[name]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise LearningComputerError(
                f"{label} {name} must be a nonnegative integer"
            )
        result[name] = raw
    if require_work and result["work"] < 1:
        raise LearningComputerError(f"{label} work must be positive")
    return result


def _zero_resources() -> dict[str, int]:
    return {name: 0 for name in ROOT_RESOURCE_NAMES}


def _program_and_entries() -> tuple[tuple[dict[str, Any], ...], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    entries: dict[str, int] = {}
    copy_rows: dict[str, int] = {}
    for kernel in STANDARD_KERNEL_CATALOG.names:
        entries[kernel] = len(rows)
        rows.append(
            {
                "op": "NATIVE",
                "kernel": kernel,
                "state": "task",
                "arguments": "arguments",
                "output": "outcome",
                "next": len(rows) + 1,
            }
        )
        copy_rows[kernel] = len(rows)
        rows.append(
            {
                "op": "COPY",
                "source": "outcome",
                "target": "result",
                "next": len(rows) + 1,
            }
        )
        rows.append({"op": "HALT"})
    rows[entries[SCALAR_REGIONAL_KERNEL]]["next"] = entries[
        SCALAR_PROCEDURE_KERNEL
    ]
    rows[entries[SCALAR_PROCEDURE_KERNEL]]["next"] = copy_rows[
        SCALAR_PROCEDURE_KERNEL
    ]
    return tuple(rows), entries


_PROGRAM, _ENTRIES = _program_and_entries()


def _regional_profile(
    value: Mapping[str, Any] | None,
    *,
    max_field_bytes: int | None = None,
) -> tuple[RegionalProfile, ComputerProfile]:
    raw = dict(value or {})
    legacy_keys = {"program_capacity", "stack_capacity", "max_steps"}
    if set(raw).issubset(legacy_keys):
        try:
            scalar = ComputerProfile(**raw)
            if (
                max_field_bytes is None
                or max_field_bytes >= 65_536 * 9 * 8
            ):
                mode_count = 65_536
            else:
                if (
                    isinstance(max_field_bytes, bool)
                    or not isinstance(max_field_bytes, int)
                    or max_field_bytes < 1
                ):
                    raise LearningComputerError(
                        "max_field_bytes must be positive"
                    )
                mode_count = max(
                    2_000,
                    scalar.program_capacity,
                    scalar.stack_capacity,
                )
                if mode_count * 9 * 8 > max_field_bytes:
                    raise LearningComputerError(
                        "scalar profile exceeds max_field_bytes"
                    )
            small = mode_count < 65_536
            return (
                RegionalProfile(
                    mode_count=mode_count,
                    directory_capacity=64 if small else 256,
                    max_steps=max(1_000_000, scalar.max_steps),
                    max_events=16 if small else 256,
                    max_registry_entries=128 if small else 4096,
                    automaton_sites=8 if small else 64,
                    registry_words=1_024 if small else 24_576,
                    queue_words=256 if small else 16_384,
                    program_words=1_024 if small else 16_384,
                    ledger_words=128 if small else 2_048,
                    default_value_words=128 if small else 4_096,
                    reclaim_quantum=64 if small else 1_024,
                    max_native_work=32,
                    kernel_names=STANDARD_KERNEL_CATALOG.names,
                ),
                scalar,
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid scalar profile") from exc
    raw.setdefault("mode_count", 65_536)
    raw.setdefault("directory_capacity", 256)
    raw.setdefault("max_native_work", 32)
    raw.setdefault("kernel_names", STANDARD_KERNEL_CATALOG.names)
    if tuple(raw["kernel_names"]) != STANDARD_KERNEL_CATALOG.names:
        raise LearningComputerError("regional profile kernel catalog is fixed")
    raw["kernel_names"] = tuple(raw["kernel_names"])
    try:
        regional = RegionalProfile(**raw)
        if (
            max_field_bytes is not None
            and regional.state_bytes > max_field_bytes
        ):
            raise LearningComputerError(
                "regional profile exceeds max_field_bytes"
            )
        scalar = ComputerProfile(max_steps=regional.max_steps)
    except (TypeError, ValueError) as exc:
        raise LearningComputerError("invalid regional profile") from exc
    return regional, scalar


def _regional_capacities(
    regional: RegionalProfile,
    values: Mapping[str, Any],
    *,
    max_field_bytes: int | None = None,
) -> dict[str, int]:
    """Plan named value regions from the resolved field workspace.

    The 65,536-mode image is the historical compatibility point.  Its
    capacities are intentionally kept as literals because changing any of
    them changes the initial field image digest.  Larger images receive the
    same resource mix at the field's actual word scale instead of falling
    through to the compact bootstrap allocation.
    """

    policy_words = (len(_canonical(values["policy"])) + 7) // 4
    if regional.mode_count < 65_536:
        capacities = {
            "arguments": 256,
            "config": 128,
            "outcome": 512,
            "result": 512,
            "policy": max(10_240, policy_words),
            "session": 256,
            "frames": 512,
            "task": 512,
        }
    elif regional.mode_count == 65_536:
        capacities = {
            "arguments": _ARGUMENT_WORDS,
            "config": _CONFIG_WORDS,
            "outcome": _OUTCOME_WORDS,
            "result": _RESULT_WORDS,
            "policy": _POLICY_WORDS,
            "session": _SESSION_WORDS,
            "frames": _FRAME_WORDS,
            "task": _TASK_WORDS,
        }
    else:
        reference_words = 65_536 * 9
        workspace_words = regional.total_words
        if max_field_bytes is not None:
            if (
                isinstance(max_field_bytes, bool)
                or not isinstance(max_field_bytes, int)
                or max_field_bytes < 1
            ):
                raise LearningComputerError("max_field_bytes must be positive")
            workspace_words = min(workspace_words, max_field_bytes // 8)

        def scaled(base: int) -> int:
            return max(
                base,
                (base * workspace_words + reference_words - 1)
                // reference_words,
            )

        capacities = {
            "arguments": scaled(_ARGUMENT_WORDS),
            "config": scaled(_CONFIG_WORDS),
            "outcome": scaled(_OUTCOME_WORDS),
            "result": scaled(_RESULT_WORDS),
            "policy": max(scaled(_POLICY_WORDS), policy_words),
            "session": scaled(_SESSION_WORDS),
            "frames": scaled(_FRAME_WORDS),
            "task": scaled(_TASK_WORDS),
        }

    if max_field_bytes is None:
        workspace_words = regional.total_words
    else:
        workspace_words = min(regional.total_words, max_field_bytes // 8)
    arena_start = 64 + 16 * regional.directory_capacity
    bootstrap_words = (
        regional.registry_words
        + regional.queue_words
        + regional.program_words
        + regional.ledger_words
        + (4 * regional.automaton_sites + 8)
        + regional.default_value_words
    )
    if (
        workspace_words < arena_start + bootstrap_words
        or sum(capacities.values())
        > workspace_words - arena_start - bootstrap_words
    ):
        raise LearningComputerError(
            "regional image does not fit the declared workspace"
        )
    return capacities


@dataclass(frozen=True, slots=True)
class LearningComputer:
    """Task-oriented view of one authoritative regional field image."""

    computer_id: str
    profile: RegionalProfile
    field: ComputerState

    def __post_init__(self) -> None:
        if (
            not isinstance(self.computer_id, str)
            or not self.computer_id
            or len(self.computer_id) > 256
        ):
            raise LearningComputerError(
                "computer_id must be a nonempty bounded string"
            )
        if not isinstance(self.profile, RegionalProfile):
            raise LearningComputerError("regional profile required")
        try:
            self._controller().validate(self.field)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid regional computer image") from exc

    def _controller(self) -> FieldComputer:
        return FieldComputer.regional(
            self.profile, catalog=STANDARD_KERNEL_CATALOG
        )

    @classmethod
    def initial(
        cls,
        computer_id: str,
        profile: Mapping[str, Any] | None = None,
        *,
        max_field_bytes: int | None = None,
    ) -> LearningComputer:
        regional, scalar = _regional_profile(
            profile, max_field_bytes=max_field_bytes
        )
        machine = FieldComputer.regional(
            regional, catalog=STANDARD_KERNEL_CATALOG
        )
        values = {
            "arguments": {},
            "config": {
                "schema": "cassifi.learning-computer-config.v1",
                "scalar_profile": scalar.as_dict(),
            },
            "outcome": None,
            "result": None,
            "frames": {
                "schema": INVOCATION_FRAMES_SCHEMA,
                "allowances": {},
                "consumed_returns": [],
                "max_depth": regional.max_scope_depth,
                "stack": [],
            },
            "policy": encode_regional_policy(initial_policy()),
            "session": {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "idle",
                "status": "idle",
            },
            "task": {
                "schema": "cassifi.learning-computer-idle.v1",
                "status": "idle",
            },
        }
        capacities = _regional_capacities(
            regional, values, max_field_bytes=max_field_bytes
        )
        try:
            state = machine.initial(
                _PROGRAM,
                entry=1,
                values=values,
                value_capacities=capacities,
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                "regional image does not fit the declared workspace"
            ) from exc
        return cls(computer_id, regional, state)

    @property
    def nbytes(self) -> int:
        return self.field.nbytes

    @property
    def state_sha256(self) -> str:
        return self._controller().state_sha256(self.field)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "computer_id": self.computer_id,
            "field": self._controller().descriptor(self.field),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LearningComputer:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"schema", "computer_id", "field"}
            or value.get("schema") != SCHEMA
        ):
            if isinstance(value, Mapping) and value.get("schema") in {
                PREVIOUS_SCHEMA,
                LEGACY_SCHEMA,
            }:
                raise LearningComputerError(
                    "legacy computer requires explicit migrate_legacy"
                )
            raise LearningComputerError("invalid learning computer record")
        try:
            machine, state = FieldComputer.from_descriptor(
                value["field"], catalog=STANDARD_KERNEL_CATALOG
            )
            if not machine.is_regional:
                raise LearningComputerError("regional field descriptor required")
            return cls(str(value["computer_id"]), machine.profile, state)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid learning computer field") from exc

    @classmethod
    def migrate_legacy(cls, value: Mapping[str, Any]) -> LearningComputer:
        """Explicitly translate a safe v1/v2 checkpoint into the v3 image."""

        if not isinstance(value, Mapping) or value.get("schema") not in {
            PREVIOUS_SCHEMA,
            LEGACY_SCHEMA,
        }:
            raise LearningComputerError("legacy computer record required")
        if value.get("continuation") is not None:
            raise LearningComputerError(
                "active legacy solver continuation has no safe migration boundary"
            )
        try:
            profile_value = dict(value["profile"])
            policy = PolicyState.from_dict(value["policy"])
            successor = cls.initial(str(value["computer_id"]), profile_value)
            controller = successor._controller()
            field, _receipt = controller.write_named_value(
                successor.field, "policy", encode_regional_policy(policy)
            )
            successor = replace(successor, field=field)
            descriptor = value.get("machine")
            if descriptor is None:
                return successor
            legacy_machine, legacy_state = FieldComputer.from_descriptor(
                descriptor
            )
            inspected = legacy_machine.inspect(legacy_state)
            parts = legacy_state._field.reshape(
                1, 9, legacy_machine.profile.mode_count, 1
            )[0, :, :, 0]
            program = tuple(
                (
                    int(parts[0, index]),
                    int(parts[1, index]),
                    int(parts[2, index]),
                    int(parts[3, index]),
                    int(parts[4, index]),
                )
                for index in range(int(inspected["program_length"]))
            )
            compiled = CompiledFieldProgram(
                program=program,
                entry=int(inspected["pc"]),
                left=tuple(inspected["left"]),
                right=tuple(inspected["right"]),
                source_sha256=hashlib.sha256(
                    _canonical({"program": program})
                ).hexdigest(),
                source_nodes=len(program),
            )
            task = regional_scalar_state(compiled, legacy_machine.profile)
            task.update(
                {
                    "accumulator": int(inspected["accumulator"]),
                    "status": str(inspected["status"]),
                    "reason": str(inspected["reason"]),
                    "transitions": int(
                        inspected["resource_ledger"]["transitions"]
                    ),
                    "stack_reads": int(
                        inspected["resource_ledger"]["stack_reads"]
                    ),
                    "stack_writes": int(
                        inspected["resource_ledger"]["stack_writes"]
                    ),
                    "field_cells_copied": int(
                        inspected["resource_ledger"]["field_cells_copied"]
                    ),
                    "pc_observations": list(
                        inspected["execution_learning"]["pc_observations"]
                    ),
                    "outcome": (
                        None
                        if inspected["status"] == "running"
                        else inspected
                    ),
                }
            )
            state, _receipt = controller.restart(
                successor.field,
                entry=_ENTRIES[SCALAR_REGIONAL_KERNEL],
                values={
                    "task": task,
                    "outcome": task["outcome"],
                    "result": task["outcome"],
                    "session": {
                        "schema": "cassifi.learning-computer-session.v1",
                        "kind": "scalar",
                        "status": inspected["status"],
                    },
                },
            )
            return replace(successor, field=state)
        except (KeyError, TypeError, ValueError) as exc:
            raise LearningComputerError("legacy migration failed") from exc

    def _value(self, name: str) -> Any:
        return self._controller().named_value(self.field, name)
    def inspect(self) -> dict[str, Any]:
        controller = self._controller()
        machine = controller.inspect(self.field)
        values = controller.named_values(
            self.field,
            ("frames", "task", "session", "policy", "outcome", "result"),
        )
        task = values["task"]
        session = values["session"]
        policy = values["policy"]
        frames = self._invocation_frames(values["frames"])
        return {
            "schema": SCHEMA,
            "computer_id": self.computer_id,
            "field_bytes": self.nbytes,
            "state_sha256": machine["state_sha256"],
            "status": machine["status"],
            "logical_transition": machine["logical_transition"],
            "task": task,
            "task_state_sha256": hashlib.sha256(_canonical(task)).hexdigest(),
            "session": session,
            "session_state_sha256": hashlib.sha256(
                _canonical(session)
            ).hexdigest(),
            "policy_state_sha256": hashlib.sha256(
                _canonical(policy)
            ).hexdigest(),
            "outcome": values["outcome"],
            "consumed_result": values["result"],
            "invocation_depth": len(frames["stack"]),
            "invocation_frames": frames,
            "active_invocation": (
                None
                if not frames["stack"]
                else {
                    "call_id": frames["stack"][-1]["call_id"],
                    "dependencies": frames["stack"][-1]["dependencies"],
                    "return_binding": frames["stack"][-1]["return_binding"],
                }
            ),
            "resource_ledger": machine["resource_ledger"],
        }

    def explain(
        self,
        source: Mapping[str, Any],
        *,
        budget: int = 2000,
        explore: bool = True,
    ) -> Mapping[str, Any]:
        """Project the prospective policy selection without publishing state."""

        del explore
        task = policy_regional_state(
            source,
            learn=False,
            lifetime_budget=budget,
            max_field_bytes=self.nbytes,
            policy=self._value("policy"),
        )
        transition = policy_regional_kernel(task, {}, 1)
        if transition.status != "done" or not isinstance(
            transition.output, Mapping
        ):
            raise LearningComputerError(
                "policy projection did not produce a selection"
            )
        selection = transition.output.get("selection")
        method = transition.output.get("method")
        if not isinstance(selection, Mapping) or not isinstance(method, str):
            raise LearningComputerError("policy selection is unavailable")
        return {
            "selected_method": method,
            "selection": dict(selection),
            "policy_state_sha256": self.inspect()["policy_state_sha256"],
        }

    def _scalar_profile(self) -> ComputerProfile:
        config = self._value("config")
        if not isinstance(config, Mapping):
            raise LearningComputerError("computer configuration is invalid")
        try:
            return ComputerProfile(**dict(config["scalar_profile"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise LearningComputerError("scalar profile is invalid") from exc

    def _invocation_frames(self, value: Any | None = None) -> dict[str, Any]:
        try:
            raw = self._value("frames") if value is None else value
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                "computer image predates resident invocation frames"
            ) from exc
        if not isinstance(raw, Mapping):
            raise LearningComputerError("resident invocation frames are invalid")
        frames = json.loads(_canonical(raw).decode("utf-8"))
        if frames.get("schema") == PREVIOUS_INVOCATION_FRAMES_SCHEMA:
            legacy_frame_keys = {
                "arguments",
                "call_id",
                "dependencies",
                "kernel",
                "outcome",
                "result",
                "return_binding",
                "session",
                "task",
            }
            if (
                set(frames) != {"schema", "max_depth", "stack"}
                or not isinstance(frames["stack"], list)
                or any(
                    not isinstance(frame, dict)
                    or set(frame) != legacy_frame_keys
                    for frame in frames["stack"]
                )
            ):
                raise LearningComputerError(
                    "legacy resident invocation frames are invalid"
                )
            frames = {
                "schema": INVOCATION_FRAMES_SCHEMA,
                "allowances": {},
                "consumed_returns": [],
                "max_depth": frames["max_depth"],
                "stack": [
                    {
                        **frame,
                        "allowance_id": None,
                        "dispatch_work": 0,
                        "expected_return": {},
                        "phase": "running-child",
                        "request_sha256": hashlib.sha256(
                            _canonical(
                                {
                                    "arguments": frame.get("arguments"),
                                    "call_id": frame.get("call_id"),
                                    "dependencies": frame.get("dependencies"),
                                    "kernel": frame.get("kernel"),
                                    "return_binding": frame.get(
                                        "return_binding"
                                    ),
                                    "task": frame.get("task"),
                                }
                            )
                        ).hexdigest(),
                        "reservation": None,
                        "reservation_sha256": None,
                    }
                    for frame in frames["stack"]
                ],
            }
        if (
            set(frames)
            != {
                "allowances",
                "consumed_returns",
                "max_depth",
                "schema",
                "stack",
            }
            or frames.get("schema") != INVOCATION_FRAMES_SCHEMA
            or frames.get("max_depth") != self.profile.max_scope_depth
            or not isinstance(frames.get("allowances"), dict)
            or not isinstance(frames.get("consumed_returns"), list)
            or not isinstance(frames.get("stack"), list)
            or len(frames["stack"]) > self.profile.max_scope_depth
        ):
            raise LearningComputerError("resident invocation frames are invalid")
        for allowance_id, raw_allowance in frames["allowances"].items():
            if (
                not isinstance(allowance_id, str)
                or not allowance_id
                or len(allowance_id.encode("utf-8")) > 512
                or not isinstance(raw_allowance, dict)
                or set(raw_allowance)
                != {
                    "charged",
                    "consumed_call_ids",
                    "limits",
                    "reserved",
                }
                or not isinstance(raw_allowance["consumed_call_ids"], list)
                or len(set(raw_allowance["consumed_call_ids"]))
                != len(raw_allowance["consumed_call_ids"])
                or any(
                    not isinstance(call_id, str) or not call_id
                    for call_id in raw_allowance["consumed_call_ids"]
                )
            ):
                raise LearningComputerError(
                    "resident root allowance is invalid"
                )
            limits = _resource_map(
                raw_allowance["limits"], "root allowance limits", require_work=True
            )
            charged = _resource_map(
                raw_allowance["charged"], "root allowance charged resources"
            )
            reserved = _resource_map(
                raw_allowance["reserved"], "root allowance reservations"
            )
            if any(
                charged[name] + reserved[name] > limits[name]
                for name in ROOT_RESOURCE_NAMES
            ):
                raise LearningComputerError(
                    "resident root allowance exceeds its limits"
                )
        consumed_ids: set[str] = set()
        for marker in frames["consumed_returns"]:
            if (
                not isinstance(marker, dict)
                or set(marker)
                != {"call_id", "child_return_sha256", "return_binding"}
                or not isinstance(marker["call_id"], str)
                or not marker["call_id"]
                or marker["call_id"] in consumed_ids
                or not isinstance(marker["return_binding"], str)
                or not marker["return_binding"]
                or not isinstance(marker["child_return_sha256"], str)
                or len(marker["child_return_sha256"]) != 64
            ):
                raise LearningComputerError(
                    "resident consumed-return marker is invalid"
                )
            consumed_ids.add(marker["call_id"])
        required_frame_keys = {
            "allowance_id",
            "arguments",
            "call_id",
            "dependencies",
            "dispatch_work",
            "expected_return",
            "kernel",
            "outcome",
            "phase",
            "request_sha256",
            "reservation",
            "reservation_sha256",
            "result",
            "return_binding",
            "session",
            "task",
        }
        for frame in frames["stack"]:
            if (
                not isinstance(frame, dict)
                or set(frame) != required_frame_keys
                or not isinstance(frame["call_id"], str)
                or not frame["call_id"]
                or frame["call_id"] in consumed_ids
                or not isinstance(frame["dependencies"], list)
                or not isinstance(frame["kernel"], str)
                or frame["kernel"] not in _ENTRIES
                or not isinstance(frame["return_binding"], str)
                or not frame["return_binding"]
                or not isinstance(frame["session"], dict)
                or not isinstance(frame["task"], dict)
                or not isinstance(frame["arguments"], dict)
                or not isinstance(frame["expected_return"], dict)
                or frame["phase"] != "running-child"
                or not isinstance(frame["request_sha256"], str)
                or len(frame["request_sha256"]) != 64
                or isinstance(frame["dispatch_work"], bool)
                or not isinstance(frame["dispatch_work"], int)
                or frame["dispatch_work"] < 0
            ):
                raise LearningComputerError(
                    "resident invocation frame is invalid"
                )
            allowance_id = frame["allowance_id"]
            if allowance_id is None:
                if (
                    frame["reservation"] is not None
                    or frame["reservation_sha256"] is not None
                ):
                    raise LearningComputerError(
                        "unbudgeted invocation frame carries a reservation"
                    )
            else:
                if (
                    allowance_id not in frames["allowances"]
                    or not isinstance(frame["reservation"], dict)
                    or not isinstance(frame["reservation_sha256"], str)
                    or len(frame["reservation_sha256"]) != 64
                ):
                    raise LearningComputerError(
                        "budgeted invocation frame is invalid"
                    )
                reservation = _resource_map(
                    frame["reservation"],
                    "resident invocation reservation",
                    require_work=True,
                )
                if (
                    hashlib.sha256(_canonical(reservation)).hexdigest()
                    != frame["reservation_sha256"]
                    or frame["dispatch_work"] > reservation["work"]
                ):
                    raise LearningComputerError(
                        "resident invocation reservation diverges"
                    )
        return frames

    def call(
        self,
        *,
        call_id: str,
        kernel: str,
        state: Mapping[str, Any] | None = None,
        return_binding: str,
        arguments: Mapping[str, Any] | None = None,
        dependencies: Sequence[Mapping[str, Any]] = (),
        kind: str | None = None,
        steps: int = 1,
        allowance_id: str | None = None,
        allowance: Mapping[str, Any] | None = None,
        reservation: Mapping[str, Any] | None = None,
        expected_return: Mapping[str, Any] | None = None,
        request_identity: Mapping[str, Any] | None = None,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Suspend the resident caller and run a child in the same image."""

        if (
            not isinstance(call_id, str)
            or not call_id
            or len(call_id.encode("utf-8")) > 512
            or not isinstance(return_binding, str)
            or not return_binding
            or len(return_binding.encode("utf-8")) > 512
        ):
            raise LearningComputerError(
                "call and return-binding identities must be bounded text"
            )
        if kernel not in STANDARD_KERNEL_CATALOG.names:
            raise LearningComputerError("kernel is not in the fixed catalog")
        if state is not None and not isinstance(state, Mapping):
            raise LearningComputerError("child task state must be a mapping")
        if arguments is not None and not isinstance(arguments, Mapping):
            raise LearningComputerError("child arguments must be a mapping")
        if expected_return is not None and not isinstance(
            expected_return, Mapping
        ):
            raise LearningComputerError("expected child return must be a mapping")
        if request_identity is not None and not isinstance(
            request_identity, Mapping
        ):
            raise LearningComputerError("child request identity must be a mapping")
        if (
            isinstance(dependencies, (str, bytes))
            or not isinstance(dependencies, Sequence)
            or any(not isinstance(item, Mapping) for item in dependencies)
        ):
            raise LearningComputerError(
                "child dependencies must be typed mappings"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError("child steps must be a positive integer")
        controller = self._controller()
        resident = controller.named_values(
            self.field,
            ("arguments", "frames", "outcome", "result", "session", "task"),
        )
        parent_session = resident["session"]
        parent_task = resident["task"]
        if (
            not isinstance(parent_session, Mapping)
            or not isinstance(parent_session.get("kernel"), str)
            or not isinstance(parent_task, Mapping)
        ):
            raise LearningComputerError(
                "no fixed-catalog regional caller is resident"
            )
        child_state = dict(parent_task) if state is None else dict(state)
        normalized_arguments = dict(arguments or {})
        normalized_dependencies = [
            json.loads(_canonical(item).decode("utf-8"))
            for item in dependencies
        ]
        normalized_expected_return = json.loads(
            _canonical(dict(expected_return or {})).decode("utf-8")
        )
        request = json.loads(
            _canonical(
                dict(
                    request_identity
                    or {
                        "arguments": normalized_arguments,
                        "call_id": call_id,
                        "dependencies": normalized_dependencies,
                        "kernel": kernel,
                        "return_binding": return_binding,
                        "state": child_state,
                    }
                )
            ).decode("utf-8")
        )
        request_sha256 = hashlib.sha256(_canonical(request)).hexdigest()
        frames = self._invocation_frames(resident["frames"])
        if len(frames["stack"]) >= frames["max_depth"]:
            raise LearningComputerError("resident invocation depth is exhausted")
        if (
            any(frame["call_id"] == call_id for frame in frames["stack"])
            or any(
                marker["call_id"] == call_id
                for marker in frames["consumed_returns"]
            )
        ):
            raise LearningComputerError("resident call identity is duplicated")
        normalized_reservation: dict[str, int] | None = None
        reservation_sha256: str | None = None
        if allowance_id is None:
            if allowance is not None or reservation is not None:
                raise LearningComputerError(
                    "root allowance identity is required for reservations"
                )
        else:
            if (
                not isinstance(allowance_id, str)
                or not allowance_id
                or len(allowance_id.encode("utf-8")) > 512
            ):
                raise LearningComputerError(
                    "root allowance identity must be bounded text"
                )
            if reservation is None:
                raise LearningComputerError(
                    "budgeted child call requires a reservation"
                )
            if allowance_id not in frames["allowances"]:
                if allowance is None:
                    raise LearningComputerError(
                        "new root allowance requires explicit limits"
                    )
                frames["allowances"][allowance_id] = {
                    "charged": _zero_resources(),
                    "consumed_call_ids": [],
                    "limits": _resource_map(
                        allowance, "root allowance limits", require_work=True
                    ),
                    "reserved": _zero_resources(),
                }
            elif allowance is not None:
                supplied_allowance = _resource_map(
                    allowance, "root allowance limits", require_work=True
                )
                if (
                    supplied_allowance
                    != frames["allowances"][allowance_id]["limits"]
                ):
                    raise LearningComputerError(
                        "root allowance limits cannot be reset"
                    )
            root_allowance = frames["allowances"][allowance_id]
            normalized_reservation = _resource_map(
                reservation, "child reservation", require_work=True
            )
            if any(
                root_allowance["charged"][name]
                + root_allowance["reserved"][name]
                + normalized_reservation[name]
                > root_allowance["limits"][name]
                for name in ROOT_RESOURCE_NAMES
            ):
                raise LearningComputerError("root allowance is exhausted")
            for name in ROOT_RESOURCE_NAMES:
                root_allowance["reserved"][name] += normalized_reservation[name]
            reservation_sha256 = hashlib.sha256(
                _canonical(normalized_reservation)
            ).hexdigest()
        frame = {
            "allowance_id": allowance_id,
            "arguments": resident["arguments"],
            "call_id": call_id,
            "dependencies": normalized_dependencies,
            "dispatch_work": 0,
            "expected_return": normalized_expected_return,
            "kernel": parent_session["kernel"],
            "outcome": resident["outcome"],
            "phase": "running-child",
            "request_sha256": request_sha256,
            "reservation": normalized_reservation,
            "reservation_sha256": reservation_sha256,
            "result": resident["result"],
            "return_binding": return_binding,
            "session": dict(parent_session),
            "task": dict(parent_task),
        }
        frames["stack"].append(frame)
        field, frame_receipt = controller.write_named_value(
            self.field, "frames", frames
        )
        staged = replace(self, field=field)
        session_kind = kernel if kind is None else kind
        if (
            not isinstance(session_kind, str)
            or not session_kind
            or len(session_kind) > 256
        ):
            raise LearningComputerError(
                "child task kind must be a bounded string"
            )
        scheduled, admission = staged._schedule(
            kernel,
            child_state,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": session_kind,
                "kernel": kernel,
                "parent_call_id": call_id,
                "status": "running",
                "task_sha256": hashlib.sha256(
                    _canonical(child_state)
                ).hexdigest(),
            },
            normalized_arguments,
        )
        successor, run = scheduled.advance(steps=steps)
        return successor, {
            "schema": "cassifi.learning-computer-call-receipt.v2",
            "call_id": call_id,
            "kernel": kernel,
            "request_sha256": request_sha256,
            "reservation_sha256": reservation_sha256,
            "return_binding": return_binding,
            "frame": frame_receipt,
            "admission": admission,
            "run": run,
            "state_sha256": successor.state_sha256,
        }

    def _active_child_return(
        self,
        frames: Mapping[str, Any],
        *,
        status: str,
        run_receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if (
            status
            not in {
                "cancelled",
                "counter-exhausted",
                "exhausted",
                "faulted",
                "halted",
            }
            or not frames["stack"]
        ):
            raise LearningComputerError("active child return status is invalid")
        frame = frames["stack"][-1]
        resident = self._controller().named_values(
            self.field,
            ("arguments", "outcome", "result", "session", "task"),
        )
        task = resident["task"]
        continuation = self.as_dict()
        resources = _zero_resources()
        resources["work"] = int(frame["dispatch_work"])
        resources["storage_words"] = (
            len(_canonical(continuation)) + 3
        ) // 4
        for source in (resident["result"], resident["outcome"], task):
            if not isinstance(source, Mapping):
                continue
            raw_resources = source.get("resources")
            if not isinstance(raw_resources, Mapping):
                continue
            for name in ROOT_RESOURCE_NAMES:
                if name in {"storage_words", "work"}:
                    continue
                raw = raw_resources.get(name)
                if (
                    not isinstance(raw, bool)
                    and isinstance(raw, int)
                    and raw >= 0
                ):
                    resources[name] = max(resources[name], raw)
        task_sha256 = hashlib.sha256(_canonical(task)).hexdigest()
        return {
            "schema": CHILD_RETURN_SCHEMA,
            "arguments": resident["arguments"],
            "call_id": frame["call_id"],
            "continuation": continuation,
            "continuation_sha256": self.state_sha256,
            "dependencies": frame["dependencies"],
            "kernel": (
                resident["session"].get("kernel")
                if isinstance(resident["session"], Mapping)
                else None
            ),
            "outcome": resident["outcome"],
            "request_sha256": frame["request_sha256"],
            "resources": resources,
            "result": resident["result"],
            "run": dict(run_receipt or {}),
            "session": resident["session"],
            "state_sha256": self.state_sha256,
            "status": status,
            "task": task,
            "task_sha256": task_sha256,
        }

    def cancel_call(
        self, *, call_id: str
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Return one active child with an exact resumable continuation."""

        frames = self._invocation_frames()
        if not frames["stack"] or frames["stack"][-1]["call_id"] != call_id:
            raise LearningComputerError("active resident call does not match")
        return self._return_from_call(
            frames,
            self._active_child_return(frames, status="cancelled"),
        )

    def _return_from_call(
        self,
        frames: dict[str, Any],
        child_return: Mapping[str, Any],
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        required_return_keys = {
            "arguments",
            "call_id",
            "continuation",
            "continuation_sha256",
            "dependencies",
            "kernel",
            "outcome",
            "request_sha256",
            "resources",
            "result",
            "run",
            "session",
            "schema",
            "state_sha256",
            "status",
            "task",
            "task_sha256",
        }
        if (
            not frames["stack"]
            or not isinstance(child_return, Mapping)
            or set(child_return) != required_return_keys
            or child_return.get("schema") != CHILD_RETURN_SCHEMA
        ):
            raise LearningComputerError("child return envelope is invalid")
        frame = frames["stack"][-1]
        if (
            child_return.get("call_id") != frame["call_id"]
            or child_return.get("request_sha256") != frame["request_sha256"]
            or child_return.get("status")
            not in {
                "cancelled",
                "counter-exhausted",
                "exhausted",
                "faulted",
                "halted",
            }
            or not isinstance(child_return.get("continuation"), Mapping)
            or not isinstance(child_return.get("run"), Mapping)
        ):
            raise LearningComputerError("child return identity is invalid")
        restored_child = LearningComputer.from_dict(
            child_return["continuation"]
        )
        if (
            restored_child.computer_id != self.computer_id
            or restored_child.profile != self.profile
            or restored_child.state_sha256
            != child_return.get("continuation_sha256")
            or child_return.get("state_sha256")
            != child_return.get("continuation_sha256")
        ):
            raise LearningComputerError(
                "child continuation does not match its return envelope"
            )
        for name, expected in frame["expected_return"].items():
            actual = child_return.get(name)
            if isinstance(expected, list):
                matched = actual in expected
            else:
                matched = actual == expected
            if not matched:
                raise LearningComputerError(
                    f"child return violates expected {name}"
                )
        resources = _resource_map(
            child_return["resources"], "child return resources"
        )
        if frame["allowance_id"] is not None:
            reservation = _resource_map(
                frame["reservation"],
                "resident invocation reservation",
                require_work=True,
            )
            exceeded = [
                name
                for name in ROOT_RESOURCE_NAMES
                if resources[name] > reservation[name]
            ]
            if exceeded:
                raise LearningComputerError(
                    "child return exceeds its root reservation: "
                    + ", ".join(exceeded)
                )
            root_allowance = frames["allowances"][frame["allowance_id"]]
            for name in ROOT_RESOURCE_NAMES:
                root_allowance["reserved"][name] -= reservation[name]
                root_allowance["charged"][name] += resources[name]
            root_allowance["consumed_call_ids"].append(frame["call_id"])
        child_return_sha256 = hashlib.sha256(
            _canonical(child_return)
        ).hexdigest()
        compact_return = {
            key: json.loads(_canonical(value).decode("utf-8"))
            for key, value in child_return.items()
            if key != "continuation"
        }
        compact_return["child_return_sha256"] = child_return_sha256
        compact_return["continuation"] = {
            "computer_id": restored_child.computer_id,
            "profile_sha256": restored_child.profile.fingerprint,
            "state_sha256": restored_child.state_sha256,
        }
        frames["consumed_returns"].append(
            {
                "call_id": frame["call_id"],
                "child_return_sha256": child_return_sha256,
                "return_binding": frame["return_binding"],
            }
        )
        frames["stack"].pop()
        parent_task = dict(frame["task"])
        returns = parent_task.get("invocation_returns", {})
        if not isinstance(returns, Mapping):
            raise LearningComputerError(
                "resident caller return bindings are invalid"
            )
        bound_returns = dict(returns)
        if frame["return_binding"] in bound_returns:
            raise LearningComputerError(
                "resident return binding is already occupied"
            )
        bound_returns[frame["return_binding"]] = compact_return
        parent_task["invocation_returns"] = bound_returns
        state, receipt = self._controller().restart(
            self.field,
            entry=_ENTRIES[frame["kernel"]],
            values={
                "arguments": frame["arguments"],
                "frames": frames,
                "outcome": frame["outcome"],
                "result": frame["result"],
                "session": {
                    **frame["session"],
                    "status": "running",
                    "returned_call_id": frame["call_id"],
                },
                "task": parent_task,
            },
        )
        successor = replace(self, field=state)
        return successor, {
            "schema": "cassifi.learning-computer-return-receipt.v2",
            "call_id": frame["call_id"],
            "child_return": dict(child_return),
            "child_return_sha256": child_return_sha256,
            "return_binding": frame["return_binding"],
            "remaining_depth": len(frames["stack"]),
            "resources": resources,
            "restart": receipt,
            "status": child_return["status"],
            "state_sha256": successor.state_sha256,
        }

    def _schedule(
        self,
        kernel: str,
        task: Mapping[str, Any],
        session: Mapping[str, Any],
        arguments: Mapping[str, Any] | None = None,
    ) -> tuple[LearningComputer, dict[str, Any]]:
        if kernel not in _ENTRIES:
            raise LearningComputerError("kernel is not in the fixed catalog")
        state, receipt = self._controller().restart(
            self.field,
            entry=_ENTRIES[kernel],
            values={
                "arguments": dict(arguments or {}),
                "task": task,
                "outcome": None,
                "result": None,
                "session": session,
            },
        )
        return replace(self, field=state), receipt

    def load(
        self,
        program: Sequence[Sequence[int]],
        *,
        left: Sequence[int] = (),
        right: Sequence[int] = (),
        entry: int = 0,
    ) -> tuple[LearningComputer, dict[str, Any]]:
        try:
            previous_task = self._value("task")
            transferable: Sequence[Mapping[str, Any]] = ()
            if (
                isinstance(previous_task, Mapping)
                and previous_task.get("schema") == SCALAR_REGIONAL_STATE_SCHEMA
                and isinstance(previous_task.get("procedure_learning"), Mapping)
            ):
                raw_transferable = previous_task["procedure_learning"].get(
                    "transferable", ()
                )
                if not isinstance(raw_transferable, list):
                    raise LearningComputerError(
                        "stored transferable procedure library is invalid"
                    )
                transferable = raw_transferable
            rows = tuple(tuple(row) for row in program)
            if not rows:
                raise LearningComputerError("program must not be empty")
            normalized = tuple(
                _canonical_instruction(
                    row, len(rows), f"program[{index}]"
                )
                for index, row in enumerate(rows)
            )
            scalar_profile = self._scalar_profile()
            compiled = CompiledFieldProgram(
                program=normalized,
                entry=int(entry),
                left=tuple(int(value) for value in left),
                right=tuple(int(value) for value in right),
                source_sha256=hashlib.sha256(
                    _canonical(
                        {
                            "program": normalized,
                            "entry": entry,
                            "left": list(left),
                            "right": list(right),
                        }
                    )
                ).hexdigest(),
                source_nodes=len(normalized),
            )
            task = regional_scalar_state(
                compiled,
                scalar_profile,
                transferable_procedures=transferable,
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid scalar program") from exc
        return self._schedule(
            SCALAR_REGIONAL_KERNEL,
            task,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "scalar",
                "status": "running",
                "source_sha256": compiled.source_sha256,
            },
        )
    def submit(
        self,
        *,
        kernel: str,
        state: Mapping[str, Any],
        kind: str | None = None,
        arguments: Mapping[str, Any] | None = None,
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Validate and start one typed task through its fixed kernel."""

        if kernel not in STANDARD_KERNEL_CATALOG.names:
            raise LearningComputerError("kernel is not in the fixed catalog")
        if not isinstance(state, Mapping):
            raise LearningComputerError(
                "regional task state must be a mapping"
            )
        if arguments is not None and not isinstance(arguments, Mapping):
            raise LearningComputerError(
                "regional task arguments must be a mapping"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError(
                "regional admission steps must be a positive integer"
            )
        session_kind = kernel if kind is None else kind
        if (
            not isinstance(session_kind, str)
            or not session_kind
            or len(session_kind) > 256
        ):
            raise LearningComputerError(
                "regional task kind must be a bounded string"
            )
        scheduled, admission = self._schedule(
            kernel,
            state,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": session_kind,
                "kernel": kernel,
                "status": "running",
                "task_sha256": hashlib.sha256(
                    _canonical(state)
                ).hexdigest(),
            },
            arguments,
        )
        successor, run = scheduled.advance(steps=steps)
        return successor, {
            "schema": "cassifi.learning-computer-submit-receipt.v1",
            "kernel": kernel,
            "kind": session_kind,
            "admission": admission,
            "run": run,
            "state_sha256": successor.state_sha256,
        }

    def invoke(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Resume resident state without crossing an authority boundary."""

        if not isinstance(arguments, Mapping):
            raise LearningComputerError(
                "regional task arguments must be a mapping"
            )
        if (
            arguments.get("operation")
            in {"authorize-action", "dispatch-action"}
            or "authority" in arguments
        ):
            raise LearningComputerError(
                "action authorization and dispatch require the owner boundary"
            )
        return self._invoke_resident(arguments=arguments, steps=steps)

    def _authorized_invoke(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Cross the atlas-owned authority boundary for an exact action phase."""

        if (
            not isinstance(arguments, Mapping)
            or arguments.get("operation")
            not in {"authorize-action", "dispatch-action"}
            or not isinstance(arguments.get("authority"), Mapping)
        ):
            raise LearningComputerError(
                "authorized invocation requires an owner-bound action phase"
            )
        return self._invoke_resident(arguments=arguments, steps=steps)

    def _invoke_resident(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Resume resident family state with one typed operation request."""
        session = self._value("session")
        task = self._value("task")
        if (
            not isinstance(session, Mapping)
            or not isinstance(task, Mapping)
            or not isinstance(session.get("kernel"), str)
        ):
            raise LearningComputerError(
                "no fixed-catalog regional task is resident"
            )
        if not isinstance(arguments, Mapping):
            raise LearningComputerError(
                "regional task arguments must be a mapping"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError(
                "regional invocation steps must be a positive integer"
            )
        kernel = str(session["kernel"])
        scheduled, admission = self._schedule(
            kernel,
            task,
            {
                **dict(session),
                "status": "running",
                "invocation_sha256": hashlib.sha256(
                    _canonical(dict(arguments))
                ).hexdigest(),
            },
            arguments,
        )
        successor, run = scheduled.advance(steps=steps)
        return successor, {
            "schema": "cassifi.learning-computer-invoke-receipt.v1",
            "kernel": kernel,
            "admission": admission,
            "run": run,
            "state_sha256": successor.state_sha256,
        }

    def advance(
        self, *, steps: int
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task_before = self._value("task")
        if (
            not isinstance(task_before, Mapping)
            or task_before.get("status") == "idle"
        ):
            raise LearningComputerError("no task is loaded")
        try:
            state, receipt = self._controller().run(self.field, steps=steps)
            successor = replace(self, field=state)
            resident = successor._controller().named_values(
                successor.field,
                ("frames", "outcome", "result", "task", "session"),
            )
            task = resident["task"]
            session = resident["session"]
            frames = successor._invocation_frames(resident["frames"])
            if frames["stack"]:
                run_work = receipt.get("work", 0)
                if (
                    isinstance(run_work, bool)
                    or not isinstance(run_work, int)
                    or run_work < 0
                ):
                    raise LearningComputerError(
                        "child run work accounting is invalid"
                    )
                frames["stack"][-1]["dispatch_work"] += run_work
                if receipt.get("status") in {
                    "halted",
                    "exhausted",
                    "faulted",
                    "counter-exhausted",
                }:
                    child_return = successor._active_child_return(
                        frames,
                        status=str(receipt["status"]),
                        run_receipt=receipt,
                    )
                    successor, returned = successor._return_from_call(
                        frames, child_return
                    )
                    return successor, {
                        **dict(receipt),
                        "paused": True,
                        "return": returned,
                        "state_sha256": successor.state_sha256,
                        "status": "returned",
                    }
                state, _ = successor._controller().write_named_value(
                    successor.field, "frames", frames
                )
                successor = replace(successor, field=state)
            if isinstance(session, Mapping) and isinstance(task, Mapping):
                scalar_session = session.get("kind") == "scalar"
                regional_session = (
                    session.get("kernel") in STANDARD_KERNEL_CATALOG.names
                    and receipt.get("status") in {
                        "running", "halted", "waiting", "exhausted",
                        "faulted", "counter-exhausted",
                    }
                )
                if scalar_session or regional_session:
                    task_status = (
                        task.get("status", "running")
                        if scalar_session else receipt["status"]
                    )
                    updated_session = {
                        **dict(session),
                        "status": task_status,
                    }
                    state, _ = (
                        successor._controller().write_named_value(
                            successor.field, "session", updated_session
                        )
                    )
                    successor = replace(successor, field=state)
            outcome = dict(receipt)
            outcome["state_sha256"] = successor.state_sha256
            if isinstance(task, Mapping):
                projected_status = task.get(
                    "status", outcome.get("status")
                )
                outcome["status"] = projected_status
                outcome["reason"] = task.get(
                    "reason", outcome.get("reason")
                )
                outcome["paused"] = projected_status in {
                    "running", "yield", "waiting"
                }
                terminal = task.get("outcome")
                if isinstance(terminal, Mapping):
                    specialization = terminal.get("specialization")
                    if isinstance(specialization, Mapping):
                        outcome["specialization"] = dict(specialization)
            return successor, outcome
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("computer advance failed") from exc

    def restart(
        self,
        *,
        left: Sequence[int] = (),
        right: Sequence[int] = (),
        entry: int = 0,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task = self._value("task")
        if (
            not isinstance(task, Mapping)
            or task.get("schema") != SCALAR_REGIONAL_STATE_SCHEMA
        ):
            raise LearningComputerError("no scalar program is loaded")
        compiled = CompiledFieldProgram(
            program=tuple(
                (
                    int(row[0]),
                    int(row[1]),
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                )
                for row in task["program"]
            ),
            entry=int(entry),
            left=tuple(int(value) for value in left),
            right=tuple(int(value) for value in right),
            source_sha256=hashlib.sha256(
                _canonical({"program": task["program"]})
            ).hexdigest(),
            source_nodes=len(task["program"]),
        )
        prepared = regional_scalar_state(compiled, self._scalar_profile())
        prepared["pc_observations"] = [
            int(value) for value in task["pc_observations"]
        ]
        prepared["procedure_learning"] = json.loads(
            _canonical(task["procedure_learning"]).decode("utf-8")
        )
        return self._schedule(
            SCALAR_REGIONAL_KERNEL,
            prepared,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "scalar",
                "status": "running",
                "source_sha256": compiled.source_sha256,
            },
        )

    def grow(
        self,
        *,
        stack_capacity: int,
        max_steps: int | None = None,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        scalar = self._scalar_profile()
        try:
            scalar = ComputerProfile(
                program_capacity=scalar.program_capacity,
                stack_capacity=int(stack_capacity),
                max_steps=scalar.max_steps if max_steps is None else int(max_steps),
            )
            controller = self._controller()
            current = self
            field_growth: Mapping[str, Any] | None = None
            if (
                (max_steps is not None and max_steps > self.profile.max_steps)
                or stack_capacity > self.profile.mode_count
            ):
                controller, state, field_growth = controller.grow(
                    self.field,
                    mode_count=max(self.profile.mode_count, stack_capacity),
                    max_steps=max_steps,
                )
                current = replace(
                    self, profile=controller.profile, field=state
                )
            config = {
                "schema": "cassifi.learning-computer-config.v1",
                "scalar_profile": scalar.as_dict(),
            }
            state, config_receipt = current._controller().write_named_value(
                current.field, "config", config
            )
            current = replace(current, field=state)
            task = current._value("task")
            resumed: Mapping[str, Any] | None = None
            if (
                isinstance(task, Mapping)
                and task.get("schema")
                == SCALAR_REGIONAL_STATE_SCHEMA
            ):
                updated_task = {**dict(task), "profile": scalar.as_dict()}
                if task.get("status") == "exhausted" and task.get(
                    "reason"
                ) in {"stack_capacity", "step_budget"}:
                    updated_task.update(
                        {"status": "running", "reason": "running", "outcome": None}
                    )
                    session = current._value("session")
                    if not isinstance(session, Mapping):
                        raise LearningComputerError(
                            "scalar session is invalid"
                        )
                    current, resumed = current._schedule(
                        SCALAR_REGIONAL_KERNEL,
                        updated_task,
                        {**dict(session), "status": "running"},
                    )
                else:
                    state, resumed = (
                        current._controller().write_named_value(
                            current.field, "task", updated_task
                        )
                    )
                    current = replace(current, field=state)
            return current, {
                "schema": SCHEMA,
                "kind": "growth",
                "field_growth": (
                    None
                    if field_growth is None
                    else dict(field_growth)
                ),
                "configuration": config_receipt,
                "resumed_task": (
                    None if resumed is None else dict(resumed)
                ),
            }
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("computer growth failed") from exc

    def _select(
        self,
        source: Mapping[str, Any],
        *,
        budget: int,
        method: str | None,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task = policy_regional_state(
            source,
            policy=self._value("policy"),
            learn=False,
            method=method,
            lifetime_budget=budget,
        )
        compiled = compile_source(source)
        current, _ = self._schedule(
            "learning.computation-policy",
            task,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "selection",
                "status": "running",
                "source_sha256": compiled.sha256,
            },
        )
        state, _ = current._controller().run(current.field)
        current = replace(current, field=state)
        outcome = current._value("outcome")
        if not isinstance(outcome, Mapping) or outcome.get("status") != "selected":
            raise LearningComputerError("method selection did not complete")
        return current, outcome

    def _finish_solver(
        self,
        source: Mapping[str, Any],
        *,
        elapsed_ns: int,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task = self._value("task")
        session = self._value("session")
        if not isinstance(task, Mapping) or not isinstance(session, Mapping):
            raise LearningComputerError("solver state is invalid")
        result = task.get("result")
        if not isinstance(result, Mapping):
            raise LearningComputerError("solver terminal result is absent")
        compiled = compile_source(source)
        audit = audit_result(compiled, result)
        current = self
        observation = None
        if bool(session.get("learn")):
            feedback_id = hashlib.sha256(
                _canonical(
                    {
                        "computer_id": self.computer_id,
                        "source_sha256": compiled.sha256,
                        "method": session["method"],
                        "result_sha256": hashlib.sha256(
                            _canonical(result)
                        ).hexdigest(),
                        "predecessor": session["selection_state_sha256"],
                    }
                )
            ).hexdigest()
            policy_task = policy_regional_state(
                source,
                policy=self._value("policy"),
                learn=True,
                method=str(session["method"]),
                lifetime_budget=int(session["lifetime_budget"]),
                feedback={
                    "id": feedback_id,
                    "method": session["method"],
                    "status": result["status"],
                    "elapsed_ns": max(1, int(elapsed_ns)),
                    "work": int(session["spent_work"]),
                },
            )
            current, _ = self._schedule(
                "learning.computation-policy",
                policy_task,
                {
                    **dict(session),
                    "status": "learning",
                    "feedback_id": feedback_id,
                },
            )
            field, _ = current._controller().run(current.field)
            current = replace(current, field=field)
            completed_policy = current._value("task")
            observation = completed_policy["result"]["observation"]
            field, _ = current._controller().write_named_value(
                current.field,
                "policy",
                completed_policy["continuation"]["policy"],
            )
            current = replace(current, field=field)
        terminal_session = {
            **dict(session),
            "status": "terminal",
            "result_status": result["status"],
            "learning_applied": observation is not None,
        }
        field, _ = current._controller().write_named_value(
            current.field, "session", terminal_session
        )
        current = replace(current, field=field)
        field, _ = current._controller().write_named_value(
            current.field, "outcome", result
        )
        current = replace(current, field=field)
        return current, {
            "schema": "cassifi.learning-computer-solve-receipt.v3",
            "status": result["status"],
            "method": session["method"],
            "selection": session["selection"],
            "result": result,
            "audit": audit,
            "observation": observation,
            "continuation": None,
            "state_sha256": current.state_sha256,
        }

    def _run_solver(
        self,
        source: Mapping[str, Any],
        *,
        budget: int,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise LearningComputerError("budget must be a positive integer")
        session = self._value("session")
        if not isinstance(session, Mapping) or session.get("kind") != "solve":
            raise LearningComputerError("no regional solver task is active")
        started = time.perf_counter_ns()
        field, run_receipt = self._controller().run(
            self.field, steps=budget
        )
        elapsed = max(1, time.perf_counter_ns() - started)
        current = replace(self, field=field)
        task = current._value("task")
        if not isinstance(task, Mapping):
            raise LearningComputerError("regional solver task is invalid")
        spent = int(task["ledger"]["primitive_work"])
        updated_session = {**dict(session), "spent_work": spent}
        field, _ = current._controller().write_named_value(
            current.field, "session", updated_session
        )
        current = replace(current, field=field)
        if task.get("result") is None:
            return current, {
                "schema": "cassifi.learning-computer-solve-receipt.v3",
                "status": "running",
                "method": session["method"],
                "selection": session["selection"],
                "result": None,
                "audit": None,
                "observation": None,
                "continuation": {
                    "source_sha256": session["source_sha256"],
                    "method": session["method"],
                    "spent_work": spent,
                    "remaining_lifetime_budget": max(
                        0, int(session["lifetime_budget"]) - spent
                    ),
                    "learning_deferred": bool(session["learn"]),
                },
                "run": run_receipt,
                "state_sha256": current.state_sha256,
            }
        return current._finish_solver(source, elapsed_ns=elapsed)

    def solve(
        self,
        source: Mapping[str, Any],
        *,
        budget: int = 2000,
        learn: bool = True,
        method: str | None = None,
        max_field_bytes: int = 134_217_728,
        lifetime_budget: int = 4096,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        if method is not None and method not in METHODS:
            raise LearningComputerError("unknown computation method")
        compiled = compile_source(source)
        selected_computer, selection = self._select(
            source, budget=budget, method=method
        )
        selected_method = str(selection["method"])
        try:
            solver_profile = _profile_for(
                compiled,
                selected_method,
                hybrid_budget=lifetime_budget,
                search_budget=lifetime_budget,
                max_field_bytes=max_field_bytes,
            )
            task = constraint_regional_state(compiled, solver_profile)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("regional solver admission failed") from exc
        current, _ = selected_computer._schedule(
            CONSTRAINT_KERNEL,
            task,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "solve",
                "status": "running",
                "source_sha256": compiled.sha256,
                "method": selected_method,
                "selection": selection["selection"],
                "selection_state_sha256": selected_computer.state_sha256,
                "learn": bool(learn),
                "lifetime_budget": int(lifetime_budget),
                "spent_work": 0,
                "replaced_task": (
                    isinstance(self._value("session"), Mapping)
                    and self._value("session").get("status") == "running"
                ),
            },
        )
        return current._run_solver(source, budget=budget)

    def continue_solve(
        self,
        source: Mapping[str, Any],
        *,
        budget: int = 2000,
        max_field_bytes: int = 134_217_728,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        del max_field_bytes
        session = self._value("session")
        compiled = compile_source(source)
        if (
            not isinstance(session, Mapping)
            or session.get("kind") != "solve"
            or session.get("status") != "running"
        ):
            raise LearningComputerError("no solver continuation is available")
        if session.get("source_sha256") != compiled.sha256:
            raise LearningComputerError(
                "continued source differs from retained solver source"
            )
        return self._run_solver(source, budget=budget)