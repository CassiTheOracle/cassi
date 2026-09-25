"""A continuing research mission on the existing field-owned regional computer.

The Python object is a disposable I/O driver. Mission, agenda, selection history,
continuation, observations and learned procedures live in cognition.field. The
only additional files are immutable inputs/results and the existing hive's
non-adaptive control plane. No model is called and live source is never replaced.
"""
from __future__ import annotations

import base64
import math
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_atlas import canonical_json_bytes, sha256_value
from cassi_field_cognition import semantic_cognition_state
from cassi_field_input import CODEC_JSON
from cassi_field_owner import CapacityLimits, FieldIntelligenceError, FieldIntelligenceOwner, SourceInput
from cassi_field_program import semantic_program_payload
from cassi_field_regions import make_semantic_record
from cassi_hive_policy import SkillPolicy
from cassi_hive_session import attach_field_session, open_field_session

SCHEMA = "cassifi.research-residency.v1"
MISSION_ID = "research:mission"
CATALOG_ID = "research:catalog"
CURSOR_PREFIX = "research:cursor:"
WORK_PREFIX = "research:work:"
WORKING_FIELD_PREFIX = "research:working-field:"
WORKING_FIELD_SCHEMA = "cassifi.research-working-field.v1"
REGIONAL_WORK_MEMORY_COMPUTER_ID = "field-qwen:work-memory"
REGIONAL_ASSESSMENT_BINDING_SCHEMA = (
    "cassifi.research-organism.regional-assessment-binding.v1"
)
MAX_WORKING_FIELDS = 128
DEFAULT_PROFILE = {"mode_count": 786_432, "default_value_words": 4_096}
DEFAULT_MISSION = "Understand and improve Cassi"
MAX_WORK_ITEMS = 32
MAX_RESULT_BYTES = 1_048_576
MAX_FIELD_OBSERVATIONS = 16


class ResidencyError(RuntimeError):
    """A residency cannot continue without changing its declared conditions."""


def _plain(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def _transition_receipts(value: Any) -> list[Mapping[str, Any]]:
    """Collect bounded regional receipts from any committed computer result."""
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        rows = value.get("transition_receipts")
        if isinstance(rows, list):
            found.extend(row for row in rows if isinstance(row, Mapping))
        for key in ("receipt", "run", "receipts", "result"):
            nested = value.get(key)
            if isinstance(nested, list):
                for item in nested:
                    found.extend(_transition_receipts(item))
            elif isinstance(nested, Mapping):
                found.extend(_transition_receipts(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_transition_receipts(item))
    return found

def _commit_bytes(path: Path, content: bytes) -> None:
    """Publish once; retrying an acknowledged operation may not change its bytes."""
    if path.exists():
        if path.read_bytes() != content:
            raise ResidencyError(f"immutable research artifact changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _work_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not items or len(items) > MAX_WORK_ITEMS:
        raise ResidencyError(f"research requires 1..{MAX_WORK_ITEMS} work items")
    result = []
    identities: set[str] = set()
    for raw in items:
        item = _plain(dict(raw))
        identity = item.get("id")
        request = item.get("request")
        if (not isinstance(identity, str) or not identity or len(identity) > 128
                or identity in identities or any(ord(c) < 32 for c in identity)):
            raise ResidencyError("work identities must be unique bounded strings")
        if not isinstance(request, dict) or not isinstance(request.get("kind"), str):
            raise ResidencyError("each work item requires a typed request")
        if "operation_id" in request:
            raise ResidencyError("the residency, not a work item, assigns operation identity")
        if not isinstance(item.get("summary"), str) or not item["summary"]:
            raise ResidencyError("each work item requires a summary")
        identities.add(identity)
        result.append({"id": identity, "summary": item["summary"], "request": request})
    if len(canonical_json_bytes(result)) > 65536:
        raise ResidencyError("research work catalog exceeds 64 KiB")
    return result


def initial_work(workspace: Path) -> list[dict[str, Any]]:
    from cassi_research_worlds import initial_work as world_work

    prefix = "CassiFI/" if (Path(workspace) / "CassiFI").is_dir() else ""
    source_paths = [
        f"{prefix}cassi_research_residency.py",
        f"{prefix}cassi_field_regions.py",
        f"{prefix}cassi_field_computer.py",
    ]
    world_items = []
    for raw in world_work(workspace):
        request = dict(raw["request"])
        request.pop("operation_id", None)
        world_items.append({
            "id": raw["id"],
            "summary": raw["summary"],
            "request": request,
        })
    candidate_rows = [
        ("module-boundary-import-alias", "module-boundary-v1", "import-alias"),
        ("module-boundary-import-alias-drift", "module-boundary-v1", "import-alias-drift"),
        ("api-successor-clean-cutover", "api-successor-v1", "clean-cutover"),
        ("api-successor-offset-drift", "api-successor-v1", "offset-drift"),
    ]
    return _work_items([
        {"id": "self-study", "summary": "Identify structural costs in Cassi's resident computer",
         "request": {"kind": "self-study", "source_paths": source_paths}},
        *[
            {"id": item_id,
             "summary": f"Evaluate the isolated {variant} architecture candidate",
             "request": {"kind": "candidate-development",
                         "source_regime": "cassimindfield-lab-example-v1",
                         "compiler_family": family, "variant_key": variant}}
            for item_id, family, variant in candidate_rows
        ],
        *world_items,
    ])


def _declared_communication_route(request: Any, operation_id: str) -> str | None:
    """Resolve a declared route; bounded lists select by stable work identity."""
    declared = request.get("communication_route") if isinstance(request, Mapping) else None
    if isinstance(declared, str):
        return declared or None
    if not isinstance(declared, list) or not declared:
        return None
    routes: list[str] = []
    for candidate in declared:
        if (
            not isinstance(candidate, str)
            or not candidate
            or len(candidate.encode("utf-8")) > 256
            or any(ord(character) < 32 for character in candidate)
        ):
            return None
        routes.append(candidate)
    index = int(
        hashlib.sha256(str(operation_id).encode("utf-8")).hexdigest()[:8], 16
    ) % len(routes)
    return routes[index]


class ResearchResidency:
    """Fixed resumable driver; all evolving research state belongs to the owner."""

    def __init__(self, home: Path, session: Any) -> None:
        self.home = Path(home).resolve()
        self.session = session
        self.owner = session.owner

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> ResearchResidency:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _computer(self) -> Any:
        return next((row for row in self.owner.state.computers
                     if row.computer_id == "research"), None)

    def _task(self) -> Mapping[str, Any]:
        computer = self._computer()
        if computer is None:
            raise ResidencyError("research computer is not initialized")
        task = computer._value("task")
        if not isinstance(task, Mapping) or task.get("family") != "cognition.field":
            raise ResidencyError("research computer is not the resident cognition field")
        return task

    def _communication_locality(self) -> Mapping[str, Any] | None:
        communication = self._task().get("communication")
        locality = (
            communication.get("locality")
            if isinstance(communication, Mapping)
            else None
        )
        return (
            locality
            if isinstance(locality, Mapping)
            and locality.get("schema") == "cassifi.field-communication-locality.v1"
            else None
        )

    def _communication_topology(
        self, *, require_current: bool = False,
    ) -> Mapping[str, Any] | None:
        communication = self._task().get("communication")
        topology = (
            communication.get("topology")
            if isinstance(communication, Mapping)
            else None
        )
        if (
            not isinstance(topology, Mapping)
            or topology.get("schema") != "cassifi.research-communication-topology.v1"
        ):
            return None
        if require_current:
            for dependency in topology.get("dependencies", []):
                if not isinstance(dependency, Mapping):
                    return None
                record = self._record(str(dependency.get("id")))
                if (
                    record is None
                    or any(
                        record.get(key) != dependency.get(key)
                        for key in ("id", "kind", "content_version")
                    )
                    or record.get("status") == "invalidated"
                ):
                    return None
        return topology

    def _record(self, identity: str) -> Mapping[str, Any] | None:
        history = self._task()["records"].get(identity)
        return history[-1] if history else None

    def _required_record(self, identity: str) -> Mapping[str, Any]:
        record = self._record(identity)
        if record is None:
            raise ResidencyError(f"resident record is missing: {identity}")
        return record
    def _catalog(self) -> list[dict[str, Any]]:
        payload = _plain(self._required_record(CATALOG_ID)["payload"])
        if not isinstance(payload, dict) or not isinstance(payload.get("work"), list):
            raise ResidencyError("resident research catalog is invalid")
        return _work_items(payload["work"])


    def _cursor(self) -> dict[str, Any]:
        rows = self._task()["current"]["Value"]
        ids = [key for key in rows if key.startswith(CURSOR_PREFIX)]
        if not ids:
            raise ResidencyError("research continuation is missing")
        return _plain(self._required_record(max(ids))["payload"])

    def _settle(self) -> None:
        for _ in range(64):
            computer = self._computer()
            session = computer._value("session")
            if session["status"] == "halted":
                return
            if session["status"] != "running":
                raise ResidencyError(f"research execution is {session['status']}; continuation retained")
            # State-derived identity also recovers an advance interrupted after publication.
            identity = f"research:advance:{computer.state_sha256}"
            self.owner.operate_computer(identity, computer_id="research", action="advance",
                                        arguments={"steps": 4096})
        raise ResidencyError("research work window exhausted; continuation retained")

    def semantic(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Use one owner path and recover exact prior results from the resident index."""
        request = _plain(dict(request))
        identity = request.get("operation_id")
        if not isinstance(identity, str) or not identity:
            raise ResidencyError("semantic research requests require operation_id")
        self._settle()
        prior = self._task()["indexes"]["operations"].get(identity)
        if prior is not None:
            if prior["request_sha256"] != sha256_value(request):
                raise ResidencyError("research operation identity was reused with different content")
            return _plain(prior["result"])
        self.owner.operate_computer(identity, computer_id="research", action="invoke",
                                    arguments={"arguments": request, "steps": 4096})
        self._settle()
        result = self._task()["indexes"]["operations"].get(identity)
        if result is None:
            raise ResidencyError("research operation did not publish a semantic result")
        answer = _plain(result["result"])
        if answer.get("status") == "resource-exhausted":
            raise ResidencyError("semantic resources exhausted; research continuation retained")
        return answer
    def _communicate_resident_method(self, operation_id: str, intent: Any) -> dict[str, Any]:
        """Join one durable owner execution for an exact method/dependency version set."""
        method_ref = _plain(intent.method_ref)
        input_refs = [_plain(ref) for ref in intent.input_refs]
        dependency_refs = [_plain(ref) for ref in intent.dependency_versions]
        computer_id = intent.computer_id
        input_bindings = dict(intent.input_bindings)
        action = _plain(intent.action)
        context = _plain(intent.context)
        consumer_work_ref = (
            None if intent.consumer_work_ref is None
            else _plain(intent.consumer_work_ref)
        )
        execution_args = {
            "method_ref": method_ref,
            "input_refs": input_refs,
            "computer_id": computer_id,
            "input_bindings": input_bindings,
            "action": action,
            "context": context,
        }
        shared_operation_id = "research:method-need:" + sha256_value({
            **execution_args,
            "dependency_versions": dependency_refs,
        })[:40]
        continuation_id = "communication:continuation:" + hashlib.sha256(
            operation_id.encode("utf-8")
        ).hexdigest()[:32]
        schema = "cassifi.research-method-need-continuation.v1"
        record = self._record(continuation_id)
        continuation = (
            record.get("payload")
            if isinstance(record, Mapping) and isinstance(record.get("payload"), Mapping)
            else None
        )
        expected = {
            "schema": schema,
            "operation_id": operation_id,
            "intent_sha256": intent.identity,
            **execution_args,
            "consumer_work_ref": consumer_work_ref,
            "dependency_versions": dependency_refs,
            "shared_operation_id": shared_operation_id,
        }
        if continuation is not None:
            if any(continuation.get(key) != value for key, value in expected.items()):
                raise ResidencyError("resident method continuation changed its exact method or input versions")
            if continuation.get("status") == "completed":
                result_ref = continuation.get("result_ref")
                if not isinstance(result_ref, Mapping):
                    raise ResidencyError("completed resident method continuation omitted its result reference")
                return _plain(result_ref)

        # A fresh Need must still name current consumer work.  A completed
        # continuation above is an exact durable join and intentionally does
        # not become stale merely because that work has since advanced.
        if consumer_work_ref is not None:
            work_id = consumer_work_ref["id"]
            if consumer_work_ref["kind"] == "Program":
                self._working_field_exact_ref(consumer_work_ref, require_current=True)
            else:
                history = self._task()["records"].get(work_id, [])
                exact = next(
                    (row for row in history if all(
                        row.get(key) == consumer_work_ref.get(key)
                        for key in ("id", "kind", "content_version")
                    )),
                    None,
                )
                current = self._task()["current"].get("Obligation", {}).get(work_id)
                if (
                    exact is None
                    or exact.get("status") not in {"active", "pending"}
                    or not isinstance(current, Mapping)
                    or any(current.get(key) != consumer_work_ref.get(key)
                           for key in ("id", "kind", "content_version"))
                ):
                    raise ResidencyError("consumer Obligation ref is stale or inactive")
        if continuation is None:
            continuation = {**expected, "status": "waiting"}
            self._register(
                operation_id + ":method-need",
                continuation_id,
                "Value",
                continuation,
                epistemic_kind="derived",
            )
        execution = self.owner.acquired_method_operation(
            shared_operation_id,
            action="execute-bound",
            arguments=execution_args,
        )
        result_ref = execution.get("result_ref") if isinstance(execution, Mapping) else None
        if not isinstance(result_ref, Mapping):
            raise ResidencyError("owner-bound resident method execution omitted its committed result reference")
        continuation = {**expected, "status": "completed", "result_ref": _plain(result_ref)}
        self._register(
            operation_id + ":method-result",
            continuation_id,
            "Value",
            continuation,
            epistemic_kind="derived",
        )
        return _plain(result_ref)

    def communicate(
        self,
        operation_id: str,
        *,
        intent: Any,
        dispatch: Mapping[str, Any] | None = None,
        maximum_advances: int = 4096,
    ) -> dict[str, Any]:
        """Admit or resume one exact typed intent through the continuing field."""
        from cassi_field_communication import (
            CONSUMPTION_SCHEMA,
            FieldIntent,
            RESULT_SCHEMA,
            admit_intent,
        )
        from cassi_field_regions import (
            RegionalFieldError,
            communication_receive_dispatches,
        )
        from cassi_learning_computer import STANDARD_KERNEL_CATALOG
        if not isinstance(operation_id, str) or not operation_id or len(operation_id.encode("utf-8")) > 96:
            raise ResidencyError("communication operation_id must be bounded for durable continuation")
        if (
            isinstance(maximum_advances, bool)
            or not isinstance(maximum_advances, int)
            or not 1 <= maximum_advances <= 4096
        ):
            raise ResidencyError("communication advance bound must be in 1..4096")
        if not isinstance(intent, FieldIntent):
            raise ResidencyError("communication requires a validated FieldIntent")
        if intent.method_ref is not None:
            result_ref = self._communicate_resident_method(operation_id, intent)
            actual_use = self.acknowledge_communication_use(
                intent=intent,
                result_ref=result_ref,
                delay=0,
            )
            return {
                "schema": "cassifi.research-communication-receipt.v1",
                "status": "completed",
                "operation_id": operation_id,
                "intent_sha256": intent.identity,
                "result_ref": _plain(result_ref),
                "actual_use": actual_use,
                "work_credit": _plain(actual_use["work_credit"]),
                "field_state_sha256": self.owner.state.state_sha256,
            }
        computer = self._computer()
        if computer is None:
            raise ResidencyError("research computer is not initialized")
        dispatch_field = (
            computer.field.image if computer.is_paged else computer.field._field
        )
        try:
            registered_dispatches = (
                computer._bounded(
                    communication_receive_dispatches,
                    dispatch_field,
                    computer.profile,
                    STANDARD_KERNEL_CATALOG,
                )
                if computer.is_paged
                else communication_receive_dispatches(
                    dispatch_field,
                    computer.profile,
                    STANDARD_KERNEL_CATALOG,
                )
            )
        except RegionalFieldError as exc:
            raise ResidencyError(
                "research computer has no valid registered RECEIVE dispatch"
            ) from exc
        matching_dispatches = [
            row for row in registered_dispatches
            if intent.receiver == f"regional-object:{row['target_id']}"
        ]
        if len(matching_dispatches) != 1:
            raise ResidencyError(
                "communication receiver does not name one registered RECEIVE target"
            )
        registered_dispatch = matching_dispatches[0]
        if dispatch is None:
            dispatch = registered_dispatch
        elif (
            not isinstance(dispatch, Mapping)
            or sha256_value(dict(dispatch)) != sha256_value(registered_dispatch)
        ):
            raise ResidencyError(
                "communication dispatch differs from its registered RECEIVE instruction"
            )
        continuation_id = "communication:continuation:" + hashlib.sha256(
            operation_id.encode("utf-8")
        ).hexdigest()[:32]
        continuation_schema = "cassifi.research-communication-continuation.v1"
        continuation_record = self._record(continuation_id)
        continuation = (
            continuation_record.get("payload")
            if continuation_record is not None
            and isinstance(continuation_record.get("payload"), Mapping)
            else None
        )
        dispatch_sha256 = sha256_value(dict(dispatch))
        if continuation is not None:
            if (
                continuation.get("schema") != continuation_schema
                or continuation.get("operation_id") != operation_id
                or continuation.get("intent_sha256") != intent.identity
                or continuation.get("dispatch_sha256") != dispatch_sha256
            ):
                raise ResidencyError("communication continuation identity was reused with different content")
            admitted = continuation.get("admission")
            event_id = continuation.get("event_id")
            if not isinstance(admitted, Mapping):
                raise ResidencyError("communication continuation omitted its exact admission")
        else:
            replay = self.owner._committed_replay(operation_id, require_retained=True)
            if replay is None:
                admitted = admit_intent(
                    self.owner,
                    operation_id=operation_id,
                    computer_id="research",
                    expected_state_sha256=self.owner.state.state_sha256,
                    intent=intent,
                    dispatch=dispatch,
                )
            else:
                manifest, checkpoint = replay
                transition = manifest.get("transition")
                request = transition.get("request") if isinstance(transition, Mapping) else None
                arguments = request.get("arguments") if isinstance(request, Mapping) else None
                if (
                    not isinstance(transition, Mapping)
                    or transition.get("kind") != "computer"
                    or not isinstance(request, Mapping)
                    or request.get("computer_id") != "research"
                    or request.get("action") != "communicate"
                    or not isinstance(arguments, Mapping)
                    or arguments.get("intent") != intent.as_dict()
                    or arguments.get("dispatch") != dict(dispatch)
                    or arguments.get("event") != intent.regional_event(**dict(dispatch))
                ):
                    raise ResidencyError("committed communication admission conflicts with this intent")
                stored_result = transition.get("result")
                if not isinstance(stored_result, Mapping):
                    raise ResidencyError("committed communication admission result is malformed")
                admitted = {
                    **dict(stored_result),
                    "checkpoint_receipt": checkpoint.as_dict(),
                }
            admission_receipt = admitted.get("receipt")
            if not isinstance(admission_receipt, Mapping):
                raise ResidencyError("owner communication admission omitted its receipt")
            event_id = admission_receipt.get("event_id")
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id < 1:
            raise ResidencyError("owner communication admission omitted its regional event identity")
        if isinstance(continuation, Mapping) and continuation.get("event_id") != event_id:
            raise ResidencyError("communication continuation event identity changed")
        if isinstance(continuation, Mapping) and continuation.get("status") in {
            "completed", "cancelled",
        }:
            result = (
                continuation.get("result")
                if continuation.get("status") == "completed"
                else continuation.get("cancellation_result")
            )
            if not isinstance(result, Mapping):
                raise ResidencyError("terminal communication continuation has no exact result")
            return _plain(result)
        if continuation is None:
            continuation = {
                "schema": continuation_schema,
                "operation_id": operation_id,
                "intent_sha256": intent.identity,
                "dispatch_sha256": dispatch_sha256,
                "admission": _plain(admitted),
                "event_id": event_id,
                "sequence": 0,
                "pending_operation_id": "research:communication-advance:" + sha256_value({
                    "operation_id": operation_id,
                    "event_id": event_id,
                    "sequence": 0,
                    "owner_state_sha256": self.owner.state.state_sha256,
                })[:32],
                "settled_work_credit": None,
                "status": "waiting",
            }
            self._register(
                "research:communication-continuation:" + hashlib.sha256(
                    operation_id.encode("utf-8")
                ).hexdigest()[:32] + ":0",
                continuation_id,
                "Value",
                continuation,
                epistemic_kind="derived",
            )
        def complete(result_ref: Mapping[str, Any]) -> dict[str, Any]:
            use = self.acknowledge_communication_use(
                intent=intent,
                result_ref=result_ref,
                delay=int(continuation.get("sequence", 0)) + 1,
            )
            result = {
                "schema": "cassifi.research-communication-receipt.v1",
                "status": "completed",
                "operation_id": operation_id,
                "intent_sha256": intent.identity,
                "admission": _plain(admitted),
                "result_ref": _plain(result_ref),
                "actual_use": use,
                "work_credit": _plain(use["work_credit"]),
                "field_state_sha256": self.owner.state.state_sha256,
            }
            completed = {
                **dict(continuation),
                "status": "completed",
                "settled_work_credit": _plain(use["work_credit"]),
                "result": result,
            }
            self._register(
                "research:communication-continuation:" + hashlib.sha256(
                    operation_id.encode("utf-8")
                ).hexdigest()[:32] + ":complete",
                continuation_id,
                "Value",
                completed,
                epistemic_kind="derived",
            )
            return result

        for _ in range(maximum_advances):
            recovered = self.owner._consumed_communication_result(
                "research", event_id, intent.identity, allow_pending=True,
            )
            if recovered is not None:
                return complete(recovered)
            advance_id = continuation.get("pending_operation_id")
            if not isinstance(advance_id, str) or not advance_id:
                raise ResidencyError("communication continuation has no pending advance identity")
            advanced = self.owner.operate_computer(
                advance_id,
                computer_id="research",
                action="advance",
                arguments={"steps": 1},
            )
            if not isinstance(advanced, Mapping):
                raise ResidencyError("owner advance omitted its committed response")
            step_receipt = advanced.get("receipt")
            transitions = (
                step_receipt.get("transition_receipts")
                if isinstance(step_receipt, Mapping)
                else None
            )
            if not isinstance(transitions, list):
                raise ResidencyError("owner advance omitted committed transition receipts")
            event_runs = [
                run for run in (transitions or [])
                if isinstance(run, Mapping) and run.get("event_id") == event_id
            ]
            if len(event_runs) > 1:
                raise ResidencyError("owner advance returned ambiguous transitions for one communication event")
            if event_runs and event_runs[0].get("operation") != "RECEIVE":
                raise ResidencyError("owner executed the communication event without its required RECEIVE")
            if event_runs:
                run = event_runs[0]
                output = run.get("output")
                if (
                    not isinstance(output, Mapping)
                    or output.get("schema") != CONSUMPTION_SCHEMA
                    or output.get("intent_sha256") != intent.identity
                ):
                    raise ResidencyError("owner RECEIVE did not consume this exact communication intent")
                checkpoint = advanced.get("checkpoint_receipt")
                checkpoint_sha256 = (
                    checkpoint.get("state_sha256")
                    if isinstance(checkpoint, Mapping)
                    else None
                )
                result_ref = {
                    "schema": RESULT_SCHEMA,
                    "operation_id": advance_id,
                    "event_id": event_id,
                    "owner_state_sha256": checkpoint_sha256,
                    "output": _plain(output),
                }
                return complete(result_ref)
            sequence = int(continuation.get("sequence", 0)) + 1
            pending_operation_id = "research:communication-advance:" + sha256_value({
                "operation_id": operation_id,
                "event_id": event_id,
                "sequence": sequence,
                "owner_state_sha256": self.owner.state.state_sha256,
            })[:32]
            continuation = {
                **dict(continuation),
                "sequence": sequence,
                "pending_operation_id": pending_operation_id,
                "settled_work_credit": None,
                "status": "waiting",
            }
            self._register(
                "research:communication-continuation:" + hashlib.sha256(
                    operation_id.encode("utf-8")
                ).hexdigest()[:32] + f":{sequence}",
                continuation_id,
                "Value",
                continuation,
                epistemic_kind="derived",
            )
        return {
            "schema": "cassifi.research-communication-receipt.v1",
            "status": "pending",
            "operation_id": operation_id,
            "intent_sha256": intent.identity,
            "admission": _plain(admitted),
            "event_id": event_id,
            "sequence": continuation.get("sequence", 0),
            "pending_operation_id": continuation.get("pending_operation_id"),
            "settled_work_credit": None,
        }

    def cancel_communication(
        self,
        operation_id: str,
        *,
        intent: Any,
    ) -> dict[str, Any]:
        """Fence one admitted regional intent or acknowledge a raced RECEIVE."""
        from cassi_field_communication import (
            CANCELLATION_SCHEMA,
            FieldIntent,
            validate_communication_cancellation,
        )

        if (
            not isinstance(operation_id, str)
            or not operation_id
            or len(operation_id.encode("utf-8")) > 96
        ):
            raise ResidencyError("communication operation_id must be bounded for cancellation")
        if not isinstance(intent, FieldIntent) or intent.method_ref is not None:
            raise ResidencyError("only an admitted regional communication event can be cancelled")
        continuation_id = "communication:continuation:" + hashlib.sha256(
            operation_id.encode("utf-8")
        ).hexdigest()[:32]
        record = self._record(continuation_id)
        continuation = (
            record.get("payload")
            if isinstance(record, Mapping) and isinstance(record.get("payload"), Mapping)
            else None
        )
        if (
            not isinstance(continuation, Mapping)
            or continuation.get("schema") != "cassifi.research-communication-continuation.v1"
            or continuation.get("operation_id") != operation_id
            or continuation.get("intent_sha256") != intent.identity
        ):
            raise ResidencyError("communication cancellation has no matching durable admission")
        event_id = continuation.get("event_id")
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id < 1:
            raise ResidencyError("communication cancellation has no exact admitted event")
        if continuation.get("status") == "completed":
            result = continuation.get("result")
            if not isinstance(result, Mapping):
                raise ResidencyError("completed communication continuation has no exact result")
            return _plain(result)
        if continuation.get("status") == "cancelled":
            result = continuation.get("cancellation_result")
            if not isinstance(result, Mapping):
                raise ResidencyError("cancelled communication continuation has no exact fence")
            return _plain(result)
        cancel_id = "research:communication-cancel:" + sha256_value({
            "operation_id": operation_id,
            "event_id": event_id,
            "intent_sha256": intent.identity,
        })[:40]
        cancelled = self.owner.operate_computer(
            cancel_id,
            computer_id="research",
            action="cancel-communication",
            arguments={
                "event_id": event_id,
                "intent_sha256": intent.identity,
            },
        )
        receipt = cancelled.get("receipt") if isinstance(cancelled, Mapping) else None
        cancellation = (
            receipt.get("communication_cancellation")
            if isinstance(receipt, Mapping)
            else None
        )
        try:
            status, result_ref = validate_communication_cancellation(
                cancellation,
                intent=intent,
                event_id=event_id,
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ResidencyError("owner did not authenticate the exact communication cancellation") from exc
        if status == "consumed":
            if not isinstance(result_ref, Mapping):
                raise ResidencyError("consumed communication cancellation omitted its committed result")
            actual_use = self.acknowledge_communication_use(
                intent=intent,
                result_ref=result_ref,
                delay=int(continuation.get("sequence", 0)) + 1,
            )
            result = {
                "schema": "cassifi.research-communication-receipt.v1",
                "status": "completed",
                "operation_id": operation_id,
                "intent_sha256": intent.identity,
                "admission": _plain(continuation["admission"]),
                "result_ref": _plain(result_ref),
                "actual_use": actual_use,
                "work_credit": _plain(actual_use["work_credit"]),
                "field_state_sha256": self.owner.state.state_sha256,
                "cancellation": _plain(cancellation),
            }
            completed = {
                **dict(continuation),
                "status": "completed",
                "settled_work_credit": _plain(actual_use["work_credit"]),
                "result": result,
                "cancellation": _plain(cancellation),
            }
            self._register(
                cancel_id + ":consumed",
                continuation_id,
                "Value",
                completed,
                epistemic_kind="derived",
            )
            return result
        cancellation_result = {
            "schema": CANCELLATION_SCHEMA,
            "status": "cancelled",
            "operation_id": operation_id,
            "intent_sha256": intent.identity,
            "event_id": event_id,
            "cancellation": _plain(cancellation),
        }
        terminal = {
            **dict(continuation),
            "status": "cancelled",
            "settled_work_credit": None,
            "cancellation": _plain(cancellation),
            "cancellation_result": cancellation_result,
        }
        self._register(
            cancel_id + ":cancelled",
            continuation_id,
            "Value",
            terminal,
            epistemic_kind="derived",
        )
        return cancellation_result

    def restart_communication(
        self,
        previous_operation_id: str,
        operation_id: str,
        *,
        intent: Any,
        dispatch: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Re-admit a cancelled exact intent under a new durable attempt identity."""
        from cassi_field_communication import FieldIntent

        if not isinstance(intent, FieldIntent) or intent.method_ref is not None:
            raise ResidencyError("only a regional communication intent can be restarted")
        if not isinstance(dispatch, Mapping):
            raise ResidencyError("communication restart requires its exact registered dispatch")
        if (
            not isinstance(previous_operation_id, str)
            or not previous_operation_id
            or len(previous_operation_id.encode("utf-8")) > 96
            or not isinstance(operation_id, str)
            or not operation_id
            or len(operation_id.encode("utf-8")) > 96
        ):
            raise ResidencyError("communication restart operation identities must be bounded")
        previous_id = "communication:continuation:" + hashlib.sha256(
            previous_operation_id.encode("utf-8")
        ).hexdigest()[:32]
        record = self._record(previous_id)
        previous = (
            record.get("payload")
            if isinstance(record, Mapping) and isinstance(record.get("payload"), Mapping)
            else None
        )
        if (
            not isinstance(previous, Mapping)
            or previous.get("operation_id") != previous_operation_id
            or previous.get("intent_sha256") != intent.identity
            or previous.get("dispatch_sha256") != sha256_value(dict(dispatch))
            or previous.get("status") != "cancelled"
            or not isinstance(previous.get("cancellation"), Mapping)
            or previous["cancellation"].get("status") != "cancelled"
        ):
            raise ResidencyError("communication restart requires the exact previously cancelled intent and dispatch")
        if operation_id == previous_operation_id:
            raise ResidencyError("communication restart requires a fresh operation identity")
        return self.communicate(operation_id, intent=intent, dispatch=dispatch)

    def acknowledge_communication_use(
        self,
        *,
        intent: Any,
        result_ref: Mapping[str, Any],
        delay: int,
    ) -> dict[str, Any]:
        """Admit actual receiver or method use from its committed owner result."""
        from cassi_field_communication import (
            ACK_SCHEMA,
            LOCALITY_SCHEMA,
            RECORD_RESULT_SCHEMA,
            FieldIntent,
            actual_use_ack,
        )

        if not isinstance(intent, FieldIntent):
            raise ResidencyError("receiver use requires its admitted FieldIntent")
        if not isinstance(result_ref, Mapping):
            raise ResidencyError("receiver use requires a committed transition reference")
        result_operation = result_ref.get("operation_id")
        if not isinstance(result_operation, str) or not result_operation:
            raise ResidencyError("receiver use must reference a committed owner operation")
        if intent.method_ref is not None:
            with self.owner._lock:
                replay = self.owner._committed_replay(
                    result_operation,
                    require_retained=True,
                )
            if replay is None:
                raise ResidencyError("resident method result is not committed")
            manifest, _ = replay
            transition = manifest.get("transition")
            request = transition.get("request") if isinstance(transition, Mapping) else None
            arguments = request.get("arguments") if isinstance(request, Mapping) else None
            committed = transition.get("result") if isinstance(transition, Mapping) else None
            method = committed.get("method") if isinstance(committed, Mapping) else None
            value = committed.get("result") if isinstance(committed, Mapping) else None
            expected_args = {
                "method_ref": _plain(intent.method_ref),
                "input_refs": [_plain(ref) for ref in intent.input_refs],
                "computer_id": intent.computer_id,
                "input_bindings": dict(intent.input_bindings),
                "action": _plain(intent.action),
                "context": _plain(intent.context),
            }
            if (
                not isinstance(transition, Mapping)
                or transition.get("kind") != "acquired-method"
                or not isinstance(request, Mapping)
                or request.get("action") != "execute-bound"
                or arguments != expected_args
                or not isinstance(method, Mapping)
                or method.get("method_id") != intent.method_ref["method_id"]
                or method.get("method_generation", method.get("method_version")) != intent.method_ref["method_generation"]
                or method.get("source_sha256") != intent.method_ref["source_sha256"]
                or not isinstance(value, Mapping)
                or sha256_value(value) != result_ref.get("result_sha256")
                or result_ref.get("schema") != "cassifi.owner-method-result-ref.v1"
                or result_ref.get("operation_id") != result_operation
                or result_ref.get("method_id") != intent.method_ref["method_id"]
                or result_ref.get("method_generation") != intent.method_ref["method_generation"]
                or result_ref.get("source_sha256") != intent.method_ref["source_sha256"]
            ):
                raise ResidencyError("resident method ACK does not authenticate this exact committed execution")
        elif set(intent.payload_ref) == {"id", "kind", "content_version"}:
            if result_ref.get("schema") != RECORD_RESULT_SCHEMA:
                raise ResidencyError("record intent requires a committed resident record result")
        else:
            with self.owner._lock:
                replay = self.owner._committed_replay(
                    result_operation, require_retained=True
                )
            if replay is None:
                raise ResidencyError("receiver use operation is not committed")
            manifest, checkpoint = replay
            transition = manifest.get("transition")
            request = transition.get("request") if isinstance(transition, Mapping) else None
            result = transition.get("result") if isinstance(transition, Mapping) else None
            if (
                not isinstance(transition, Mapping)
                or transition.get("kind") != "computer"
                or not isinstance(request, Mapping)
                or request.get("computer_id") != "research"
                or not isinstance(result, Mapping)
            ):
                raise ResidencyError("receiver use computer operation omitted its committed receipt")
            state_sha256 = checkpoint.as_dict().get("state_sha256")
            if state_sha256 != result_ref.get("owner_state_sha256"):
                raise ResidencyError("receiver use checkpoint does not match its committed operation")
            transitions = _transition_receipts(result)
            if not transitions:
                raise ResidencyError("receiver use operation omitted committed transition receipts")
            matching = [
                item for item in transitions
                if item.get("operation") == "RECEIVE"
                and item.get("event_id") == result_ref.get("event_id")
                and item.get("output") == result_ref.get("output")
            ]
            if len(matching) != 1:
                raise ResidencyError("receiver use does not match one exact committed RECEIVE transition")
        use_sha256 = sha256_value({
            "intent_sha256": intent.identity,
            "consumer_use_id": intent.consumer_use_id,
        })
        ack_operation_id = "communication:ack:" + use_sha256[:40]
        ack = actual_use_ack(
            operation_id=ack_operation_id,
            intent=intent,
            result_ref=result_ref,
            delay=delay,
        )
        if ack["use_sha256"] != use_sha256:
            raise ResidencyError("receiver-use identity digest changed during acknowledgment")
        work_outcome: dict[str, Any] = {
            "status": "unknown",
            "work_unblocked": None,
            "completed": None,
            "settled_work_credit": _plain(ack["work_credit"]),
        }
        work_ref = intent.consumer_work_ref
        if work_ref is not None and work_ref["kind"] == "Obligation":
            history = self._task()["records"].get(work_ref["id"], [])
            prior = next(
                (row for row in history if all(
                    row.get(key) == work_ref.get(key)
                    for key in ("id", "kind", "content_version")
                )),
                None,
            )
            latest = history[-1] if history else None
            if prior is None:
                raise ResidencyError("consumer work reference disappeared before actual-use observation")
            if isinstance(latest, Mapping) and latest.get("content_version", 0) > work_ref["content_version"]:
                before_payload = prior.get("payload", {})
                after_payload = latest.get("payload", {})
                before_state = (
                    before_payload.get("state")
                    if isinstance(before_payload, Mapping)
                    else None
                )
                after_state = (
                    after_payload.get("state")
                    if isinstance(after_payload, Mapping)
                    else None
                )
                before_status = prior.get("status")
                after_status = latest.get("status")
                was_waiting = before_status in {"pending", "waiting"} or before_state in {
                    "pending", "waiting",
                }
                unblocked = after_status in {
                    "running", "in_progress", "resolved", "completed", "complete",
                } or after_state in {"running", "in_progress", "resolved", "completed", "complete"}
                if was_waiting and unblocked:
                    completed = after_status in {
                        "resolved", "completed", "complete",
                    } or after_state in {"resolved", "completed", "complete"}
                    work_outcome = {
                        "status": "observed",
                        "work_unblocked": True,
                        "completed": completed,
                        "consumer_work_ref": dict(work_ref),
                        "successor_work_ref": {
                            key: latest[key] for key in ("id", "kind", "content_version")
                        },
                        "before_status": before_status,
                        "after_status": after_status,
                    }
        route = f"{intent.sender}->{intent.receiver}:{intent.kind}"
        ack["locality_observation"] = {
            "use_sha256": ack["use_sha256"],
            "route": route,
            "delay": delay,
        }
        ack["work_outcome"] = work_outcome
        ack["settled_work_credit"] = _plain(ack["work_credit"])
        ack_id = "communication:use:" + ack["use_sha256"][:40]
        prior_ack = self._record(ack_id)
        prior_payload = (
            prior_ack.get("payload")
            if prior_ack is not None and isinstance(prior_ack.get("payload"), Mapping)
            else None
        )
        if prior_payload is not None:
            if (
                prior_payload.get("intent_sha256") != intent.identity
                or prior_payload.get("consumer_use_id") != intent.consumer_use_id
                or prior_payload.get("result_ref") != _plain(result_ref)
            ):
                raise ResidencyError("consumer_use_id was reused for different receiver output")
            prior_credit = prior_payload.get("work_credit")
            if prior_credit is not None and prior_credit != ack["work_credit"]:
                raise ResidencyError("consumer_use_id was reused with a different settled work credit")
            ack = {
                **dict(prior_payload),
                "work_credit": _plain(ack["work_credit"]),
                "settled_work_credit": _plain(ack["work_credit"]),
            }
        committed_ack = self._register(
            ack_operation_id,
            ack_id,
            "Event",
            ack,
            epistemic_kind="derived",
        )
        current_event = self._task().get("current", {}).get("Event", {}).get(ack_id)
        if (
            not isinstance(current_event, Mapping)
            or current_event.get("id") != ack_id
            or current_event.get("kind") != "Event"
            or not isinstance(current_event.get("content_version"), int)
        ):
            raise ResidencyError("actual-use acknowledgment Event was not admitted")
        locality = self._communication_locality()
        if locality is None:
            raise ResidencyError("durable communication locality state is unavailable")
        locality_state_ref = {
            "schema": "cassifi.semantic-communication-locality-ref.v1",
            "path": "communication.locality",
            "owner_state_sha256": self.owner.state.state_sha256,
            "locality_sha256": sha256_value(locality),
        }
        return {
            "schema": ACK_SCHEMA,
            "acknowledgment": _plain(committed_ack),
            "ack_event_ref": dict(current_event),
            "locality": {
                "schema": LOCALITY_SCHEMA,
                "record": dict(current_event),
                "state_ref": locality_state_ref,
                "payload": _plain(locality),
                "route": route,
            },
            "work_credit": _plain(ack["work_credit"]),
        }
    def _register(self, operation_id: str, record_id: str, kind: str,
                  payload: Mapping[str, Any], *, status: str = "active",
                  roots: Sequence[str] = (), dependencies: Sequence[Mapping[str, Any]] = (),
                  epistemic_kind: str = "derived") -> dict[str, Any]:
        record_payload = dict(payload)
        if kind == "Program" and record_payload.get("program_role") == "working-field":
            record_payload["program"] = semantic_program_payload(
                program_kind="procedure",
                body={
                    key: _plain(record_payload[key])
                    for key in ("field_id", "question", "purpose", "status", "transition")
                },
                reads=["field-records", "world-evidence"],
                writes=["working-field"],
                emits=["research-continuation"],
                max_work=64,
                max_horizon=256,
                applicability={"owner": "research-residency"},
            )
        request = {"operation": "register", "operation_id": operation_id,
                   "record_id": record_id, "kind": kind, "payload": record_payload,
                   "status": status, "epistemic_kind": epistemic_kind,
                   "support_roots": list(roots)}
        if dependencies:
            request["dependencies"] = [dict(ref) for ref in dependencies]
        return self.semantic(request)

    @staticmethod
    def _working_field_record_id(field_id: str) -> str:
        return WORKING_FIELD_PREFIX + hashlib.sha256(
            field_id.encode("utf-8")
        ).hexdigest()[:32]

    @staticmethod
    def _working_field_ref(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: record[key]
            for key in ("id", "kind", "content_version")
        }

    @staticmethod
    def _working_field_identity(value: Any, name: str) -> str:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 128
            or any(ord(char) < 32 for char in value)
        ):
            raise ResidencyError(f"{name} must be a unique bounded string")
        return value

    @staticmethod
    def _working_field_text(value: Any, name: str, *, maximum: int = 2048) -> str:
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > maximum
            or any(ord(char) < 32 and char not in "\t\n\r" for char in value)
        ):
            raise ResidencyError(f"{name} must be nonempty bounded text")
        return value.strip()

    def _working_field_prospect(self, value: Any) -> Any:
        """New prospective work is comparable; historical descriptions stay readable."""
        if not isinstance(value, Mapping) or not any(
            key in value for key in ("value", "uncertainty", "cost")
        ):
            return self._working_field_json(value, "expected_contribution", maximum=8192)
        if not {"kind", "value", "uncertainty", "cost"} <= set(value):
            raise ResidencyError("prospective contribution requires kind, value, uncertainty and cost")
        if set(value) - {"kind", "value", "uncertainty", "cost", "dependency_refs"}:
            raise ResidencyError("prospective contribution has unknown keys")
        kind = self._working_field_text(value["kind"], "contribution kind", maximum=128)
        numbers = {}
        for key in ("value", "uncertainty", "cost"):
            number = value[key]
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise ResidencyError(f"contribution {key} must be finite and nonnegative")
            number = float(number)
            if not math.isfinite(number) or number < 0 or (key != "cost" and number > 1):
                raise ResidencyError(f"contribution {key} is out of range")
            numbers[key] = number
        return {
            "kind": kind,
            **numbers,
            "dependency_refs": self._working_field_refs(
                value.get("dependency_refs", []), "contribution dependency_refs",
                require_current=True,
            ),
        }

    def _working_field_exact_ref(
        self,
        value: Any,
        *,
        require_current: bool,
        require_active: bool = True,
    ) -> tuple[dict[str, Any], Mapping[str, Any]]:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"id", "kind", "content_version"}
            or not isinstance(value.get("id"), str)
            or not isinstance(value.get("kind"), str)
            or isinstance(value.get("content_version"), bool)
            or not isinstance(value.get("content_version"), int)
            or value["content_version"] < 1
        ):
            raise ResidencyError("working-field references must be exact typed record refs")
        history = self._task()["records"].get(value["id"], [])
        record = next(
            (
                row for row in history
                if isinstance(row, Mapping)
                and all(row.get(key) == value.get(key)
                        for key in ("id", "kind", "content_version"))
            ),
            None,
        )
        if record is None:
            raise ResidencyError("working-field reference is unavailable")
        latest = history[-1] if history else None
        if require_current and (
            not isinstance(latest, Mapping)
            or any(latest.get(key) != value.get(key)
                   for key in ("id", "kind", "content_version"))
        ):
            raise ResidencyError("working-field dependency is stale")
        if require_active and record.get("status") != "active":
            raise ResidencyError("working-field reference is not active")
        return dict(value), record

    def _register_regional_assessment(
        self,
        operation_id: str,
        *,
        regional_memory: Any,
        assessment_ref: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Register a verified foreign assessment pointer, never its interpretation."""
        operation_id = self._working_field_identity(
            operation_id, "regional assessment operation_id"
        )
        if not isinstance(assessment_ref, Mapping):
            raise ResidencyError("regional assessment reference must be typed")
        reference = dict(assessment_ref)
        if (
            set(reference) != {"id", "kind", "content_version"}
            or not isinstance(reference.get("id"), str)
            or reference.get("kind") != "Assessment"
            or isinstance(reference.get("content_version"), bool)
            or not isinstance(reference.get("content_version"), int)
            or reference["content_version"] < 1
        ):
            raise ResidencyError("regional assessment reference must be an exact typed Assessment ref")

        owner = getattr(regional_memory, "owner", None)
        if not isinstance(owner, FieldIntelligenceOwner):
            raise ResidencyError("regional assessment owner is unavailable")
        if getattr(regional_memory, "_closed", True) is not False:
            raise ResidencyError("regional work-memory is closed")
        memory_home = getattr(regional_memory, "data_home", None)
        if (
            memory_home is None
            or Path(memory_home).resolve() != Path(owner.data_home).resolve()
        ):
            raise ResidencyError("regional assessment memory does not match its owner")

        lock = getattr(owner, "_lock", None)
        if lock is None or not hasattr(lock, "__enter__"):
            raise ResidencyError("regional assessment owner lock is unavailable")
        with lock:
            computers = [
                computer
                for computer in owner.state.computers
                if computer.computer_id == REGIONAL_WORK_MEMORY_COMPUTER_ID
            ]
            if len(computers) != 1:
                raise ResidencyError("regional work-memory computer is unavailable")
            task = computers[0]._value("task")
            if (
                not isinstance(task, Mapping)
                or task.get("family") != "cognition.field"
                or not isinstance(task.get("records"), Mapping)
                or not isinstance(task.get("current"), Mapping)
            ):
                raise ResidencyError("regional work-memory semantic task is invalid")

            history = task["records"].get(reference["id"])
            if not isinstance(history, list) or not history:
                raise ResidencyError("regional assessment reference is unavailable")
            record = next(
                (
                    row
                    for row in history
                    if isinstance(row, Mapping)
                    and all(
                        row.get(key) == reference.get(key)
                        for key in ("id", "kind", "content_version")
                    )
                ),
                None,
            )
            latest = history[-1]
            current = task["current"].get("Assessment")
            current_ref = (
                current.get(reference["id"])
                if isinstance(current, Mapping)
                else None
            )
            if (
                record is None
                or record.get("kind") != "Assessment"
                or record.get("epistemic_kind") != "assessed"
                or record.get("status") != "active"
                or not isinstance(latest, Mapping)
                or any(
                    latest.get(key) != reference.get(key)
                    for key in ("id", "kind", "content_version")
                )
                or not isinstance(current_ref, Mapping)
                or any(
                    current_ref.get(key) != reference.get(key)
                    for key in ("id", "kind", "content_version")
                )
            ):
                raise ResidencyError("regional assessment reference is stale or inactive")

            payload = record.get("payload")
            if not isinstance(payload, Mapping):
                raise ResidencyError("regional assessment payload is malformed")
            method_outcome = payload.get("method_outcome")
            affect_outcome = payload.get("affect_outcome")
            director_operation_id = (
                method_outcome.get("operation_id")
                if isinstance(method_outcome, Mapping)
                and method_outcome.get("schema") == "cassi.entity.method-outcome.v1"
                else None
            )
            director_result_sha256 = (
                method_outcome.get("result_sha256")
                if isinstance(method_outcome, Mapping)
                else None
            )
            if (
                not isinstance(affect_outcome, Mapping)
                or affect_outcome.get("schema") != "cassifi.affect-outcome.v1"
                or not isinstance(director_operation_id, str)
                or not director_operation_id
                or not isinstance(director_result_sha256, str)
                or len(director_result_sha256) != 64
                or any(char not in "0123456789abcdef" for char in director_result_sha256)
                or reference["id"]
                != (
                    "assessment:entity-research-outcome:"
                    + hashlib.sha256(
                        director_operation_id.encode("utf-8")
                    ).hexdigest()
                )
            ):
                raise ResidencyError("regional Assessment is not a director research outcome")
            source_revision_id = payload.get("source_revision_id")
            declared_content_sha256 = payload.get("source_content_sha256")
            if (
                not isinstance(source_revision_id, str)
                or not source_revision_id
                or not isinstance(declared_content_sha256, str)
                or len(declared_content_sha256) != 64
                or any(char not in "0123456789abcdef" for char in declared_content_sha256)
            ):
                raise ResidencyError("regional assessment omits its exact result source identity")
            try:
                active_revision_ids = owner.evidence.active_revision_ids()
                source = owner.evidence.source(source_revision_id)
                source_bytes = owner.evidence.read(source)
            except FieldIntelligenceError as exc:
                raise ResidencyError("regional assessment result source is unavailable") from exc
            content_sha256 = hashlib.sha256(source_bytes).hexdigest()
            if (
                source_revision_id not in active_revision_ids
                or source.status != "active"
                or source.revision_id != source_revision_id
                or source.source_id
                != f"entity-research-result:{director_operation_id}"
                or source.content_sha256 != declared_content_sha256
                or content_sha256 != declared_content_sha256
                or content_sha256 != director_result_sha256
            ):
                raise ResidencyError("regional assessment result source is stale or corrupt")
            source_identity = {
                "content_sha256": content_sha256,
                "source_id": source.source_id,
                "external_revision": source.revision_id,
            }
            owner_identity = hashlib.sha256(
                str(Path(owner.data_home).resolve()).encode("utf-8")
            ).hexdigest()

        token = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
        record_id = f"event:regional-assessment-binding:{token}"
        binding_payload = {
            "schema": REGIONAL_ASSESSMENT_BINDING_SCHEMA,
            "epistemic_role": "interpretive-assessment-pointer",
            "external_computer_id": REGIONAL_WORK_MEMORY_COMPUTER_ID,
            "external_owner_sha256": owner_identity,
            "external_assessment_ref": reference,
            "result_source": source_identity,
        }
        self._register(
            f"research:regional-assessment-bind:{token}",
            record_id,
            "Event",
            binding_payload,
            epistemic_kind="derived",
        )
        local_record = self._record(record_id)
        if (
            local_record is None
            or local_record.get("kind") != "Event"
            or local_record.get("status") != "active"
            or local_record.get("epistemic_kind") != "derived"
            or local_record.get("payload") != binding_payload
        ):
            raise ResidencyError("regional assessment binding was not published exactly")
        return self._working_field_ref(local_record)


    def _working_field_refs(
        self,
        values: Any,
        name: str,
        *,
        require_current: bool,
        require_active: bool = True,
    ) -> list[dict[str, Any]]:
        if values is None:
            values = []
        if not isinstance(values, list) or len(values) > 64:
            raise ResidencyError(f"{name} must be a bounded list of typed refs")
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str, int]] = set()
        for value in values:
            reference, _ = self._working_field_exact_ref(
                value,
                require_current=require_current,
                require_active=require_active,
            )
            key = (
                reference["id"], reference["kind"], reference["content_version"]
            )
            if key not in seen:
                seen.add(key)
                normalized.append(reference)
        return normalized

    @staticmethod
    def _working_field_json(value: Any, name: str, *, maximum: int = 16384) -> Any:
        try:
            normalized = _plain(value)
            encoded = canonical_json_bytes(normalized)
        except (TypeError, ValueError) as exc:
            raise ResidencyError(f"{name} must be bounded JSON data") from exc
        if len(encoded) > maximum:
            raise ResidencyError(f"{name} exceeds its {maximum}-byte bound")
        return normalized

    def _working_field_current(self, field_id: str) -> Mapping[str, Any] | None:
        record = self._record(self._working_field_record_id(field_id))
        if record is None:
            return None
        payload = record.get("payload")
        if (
            record.get("kind") != "Program"
            or not isinstance(payload, Mapping)
            or payload.get("program_role") != "working-field"
            or payload.get("working_field_schema") != WORKING_FIELD_SCHEMA
            or payload.get("field_id") != field_id
        ):
            raise ResidencyError("working-field Program identity is inconsistent")
        return record

    def _working_field_projection(
        self, record: Mapping[str, Any]
    ) -> dict[str, Any]:
        payload = record["payload"]
        child_refs = []
        for child_id in payload.get("child_field_ids", []):
            child = self._working_field_current(str(child_id))
            if child is not None:
                child_refs.append(self._working_field_ref(child))
        return {
            "field_id": payload["field_id"],
            "program_id": record["id"],
            "program_ref": self._working_field_ref(record),
            "question": payload["question"],
            "purpose": payload["purpose"],
            "status": payload["status"],
            "parent_ref": _plain(payload.get("parent_ref")),
            "branch_purpose": payload.get("branch_purpose"),
            "child_refs": child_refs,
            "assumptions": _plain(payload.get("assumptions", [])),
            "evidence_refs": _plain(payload.get("evidence_refs", [])),
            "provenance_refs": _plain(payload.get("provenance_refs", [])),
            "merge_parent_ids": _plain(payload.get("merge_parent_ids", [])),
            "merge_parent_refs": _plain(payload.get("merge_parent_refs", [])),
            "merge_parent_contributions": _plain(
                payload.get("merge_parent_contributions", [])
            ),
            "expected_contribution": _plain(payload.get("expected_contribution")),
            "contribution": _plain(payload.get("contribution")),
            "measured_cost": _plain(payload.get("measured_cost")),
            "eligible": (
                payload.get("status") == "active"
                and not self._working_field_applicable_dependencies(record)[1]
            ),
            "obstacle": _plain(payload.get("obstacle")),
            "reopen_condition": _plain(payload.get("reopen_condition")),
            "continuation_ref": _plain(payload.get("continuation_ref")),
            "dependencies": _plain(record.get("dependencies", [])),
            "transition": _plain(payload.get("transition", {})),
            "last_operation": _plain(payload.get("last_operation", {})),
            "opportunity_count": int(payload.get("opportunity_count", 0)),
            "role_bindings": _plain(payload.get("role_bindings", [])),
            "region_refs": _plain(payload.get("region_refs", [])),
        }

    def working_fields(self, *, limit: int = 32) -> dict[str, Any]:
        """Return a bounded projection of the current owner-held working Programs."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_WORKING_FIELDS:
            raise ResidencyError(
                f"working-field inspection limit must be in [1, {MAX_WORKING_FIELDS}]"
            )
        task = self._task()
        records = []
        for record_id, reference in task["current"]["Program"].items():
            history = task["records"].get(record_id, [])
            record = history[-1] if history else None
            payload = record.get("payload") if isinstance(record, Mapping) else None
            if (
                isinstance(payload, Mapping)
                and payload.get("program_role") == "working-field"
                and payload.get("working_field_schema") == WORKING_FIELD_SCHEMA
                and record.get("kind") == "Program"
                and reference.get("content_version") == record.get("content_version")
            ):
                records.append(record)
        records.sort(key=lambda row: (row["payload"]["field_id"], row["id"]))
        total_count = len(records)
        return {
            "status": "supported",
            "items": [
                self._working_field_projection(record)
                for record in records[:limit]
            ],
            "total_count": total_count,
            "limit": limit,
            "truncated": total_count > limit,
        }

    def _working_field_operation_digest(
        self, action: str, field_id: str, update: Mapping[str, Any]
    ) -> str:
        return sha256_value({
            "action": action,
            "field_id": field_id,
            "update": _plain(dict(update)),
        })

    def _working_field_transition(
        self,
        record: Mapping[str, Any],
        *,
        operation_id: str,
        operation_digest: str,
        reason: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = _plain(record["payload"])
        transition = payload.get("transition", {})
        sequence = (
            int(transition.get("sequence", 0))
            if isinstance(transition, Mapping) else 0
        )
        payload.update(_plain(dict(changes)))
        payload["transition"] = {
            "sequence": sequence + 1,
            "owner_generation_before": self.owner.state.generation,
            "reason": reason,
        }
        payload["last_operation"] = {
            "id": operation_id,
            "sha256": operation_digest,
        }
        return payload

    def _working_field_last_operation_matches(
        self,
        record: Mapping[str, Any] | None,
        operation_id: str,
        operation_digest: str,
    ) -> bool:
        if record is None:
            return False
        last = record.get("payload", {}).get("last_operation")
        if not isinstance(last, Mapping) or last.get("id") != operation_id:
            return False
        if last.get("sha256") != operation_digest:
            raise ResidencyError("working-field operation identity was reused with different content")
        return True

    def _working_field_applicable_dependencies(
        self, record: Mapping[str, Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        applicable: list[dict[str, Any]] = []
        stale: list[dict[str, Any]] = []
        for raw_ref in record.get("dependencies", []):
            reference, exact = self._working_field_exact_ref(
                raw_ref,
                require_current=False,
                require_active=False,
            )

            history = self._task()["records"][reference["id"]]
            latest = history[-1]
            if (
                all(latest.get(key) == reference.get(key)
                    for key in ("id", "kind", "content_version"))
                and latest.get("status") == "active"
                and exact.get("status") == "active"
            ):
                applicable.append(reference)
            else:
                stale.append(reference)
        return applicable, stale

    def _working_field_wake_receipt(
        self, operation_id: str, field_id: str, digest: str
    ) -> dict[str, Any] | None:
        operation = self._task()["indexes"]["operations"].get(operation_id + ":receipt")
        if not isinstance(operation, Mapping):
            return None
        result = operation.get("result")
        event_ref = result.get("record") if isinstance(result, Mapping) else None
        if not isinstance(event_ref, Mapping):
            raise ResidencyError("working-field wake receipt is malformed")
        event, record = self._working_field_exact_ref(
            event_ref, require_current=False, require_active=False
        )
        payload = record.get("payload")
        if (
            event.get("kind") != "Event"
            or not isinstance(payload, Mapping)
            or payload.get("working_field_event_schema") != WORKING_FIELD_SCHEMA
            or payload.get("operation_id") != operation_id
            or payload.get("field_id") != field_id
            or payload.get("request_sha256") != digest
        ):
            raise ResidencyError("working-field operation identity was reused with different content")
        program_ref = payload.get("program_ref")
        if not isinstance(program_ref, Mapping):
            raise ResidencyError("working-field wake receipt omits its Program ref")
        _, program_record = self._working_field_exact_ref(
            program_ref, require_current=False, require_active=False
        )
        return self._working_field_projection(program_record)

    def _working_field_store_wake_receipt(
        self,
        operation_id: str,
        field_id: str,
        digest: str,
        result: Mapping[str, Any],
        trigger_ref: Mapping[str, Any] | None,
        reopened: Sequence[Mapping[str, Any]],
        *,
        require_current_trigger: bool = True,
    ) -> None:
        program_ref = result.get("program_ref")
        if not isinstance(program_ref, Mapping) or not isinstance(trigger_ref, Mapping):
            raise ResidencyError("working-field wake receipt requires exact resident refs")
        reopened_refs = [
            dict(item["program_ref"])
            for item in reopened
            if isinstance(item.get("program_ref"), Mapping)
        ]
        trigger, trigger_record = self._working_field_exact_ref(
            trigger_ref, require_current=require_current_trigger
        )
        if trigger["kind"] != "Event" or trigger_record.get("status") != "active":
            raise ResidencyError("working-field wake trigger is unavailable")
        committed_ref, committed = self._working_field_exact_ref(
            program_ref,
            require_current=require_current_trigger,
            require_active=require_current_trigger,
        )
        committed_payload = committed.get("payload")
        if (
            committed_ref["kind"] != "Program"
            or not isinstance(committed_payload, Mapping)
            or committed_payload.get("field_id") != field_id
            or committed_payload.get("status") != "active"
            or (
                not require_current_trigger
                and (
                    committed_payload.get("last_wake_request_id") != operation_id
                    or committed_payload.get("last_wake_request_sha256") != digest
                    or committed_payload.get("last_wake_trigger_ref") != trigger
                )
            )
        ):
            raise ResidencyError("working-field wake Program provenance is unavailable")
        dependencies = [trigger, committed_ref] if require_current_trigger else []
        receipt_id = "research:working-field:wake-receipt:" + hashlib.sha256(
            operation_id.encode("utf-8")
        ).hexdigest()[:32]
        self._register(
            operation_id + ":receipt",
            receipt_id,
            "Event",
            {
                "working_field_event_schema": WORKING_FIELD_SCHEMA,
                "operation_id": operation_id,
                "field_id": field_id,
                "request_sha256": digest,
                "program_ref": dict(program_ref),
                "trigger_ref": dict(trigger_ref),
                "reopened_program_refs": reopened_refs,
            },
            dependencies=dependencies,
        )

    def _register_working_field_relevance(
        self,
        operation_id: str,
        field_id: str,
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = record["payload"]
        condition_id = "working-field:" + hashlib.sha256(
            field_id.encode("utf-8")
        ).hexdigest()[:24]
        self.semantic({
            "operation": "register-relevance",
            "operation_id": operation_id,
            "condition_id": condition_id,
            "condition": payload["reopen_condition"],
            "target_refs": [self._working_field_ref(record)],
            "reason": {
                "kind": "working-field-rest",
                "field_id": field_id,
                "reason": payload["rest_reason"],
            },
        })
        relevance = self._record("memory:relevance:" + condition_id)
        if (
            relevance is None
            or relevance.get("status") != "active"
            or relevance.get("payload", {}).get("memory_role") != "relevance-condition"
        ):
            raise ResidencyError("resting working-field relevance Program was not registered")
        return {
            key: relevance[key] for key in ("id", "kind", "content_version")
        }

    def _working_field_dependencies(
        self, record: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        return self._working_field_refs(
            record.get("dependencies", []),
            "working-field dependencies",
            require_current=True,
        )

    def _working_field_validate_condition(self, value: Any) -> dict[str, Any]:
        condition = self._working_field_json(
            value, "reopen_condition", maximum=8192
        )
        clauses = condition.get("clauses") if isinstance(condition, Mapping) else None
        if not isinstance(clauses, list) or not clauses or len(clauses) > 64:
            raise ResidencyError("reopen_condition requires 1..64 relevance clauses")
        for clause in clauses:
            if (
                not isinstance(clause, Mapping)
                or set(clause) != {"field", "operator", "value"}
                or not isinstance(clause.get("field"), str)
                or not clause["field"]
                or len(clause["field"]) > 128
                or clause.get("operator") not in {"equals", "in", "not-equals"}
                or clause.get("operator") == "in"
                and not isinstance(clause.get("value"), list)
            ):
                raise ResidencyError("reopen_condition contains an unsupported relevance clause")
        return dict(condition)

    def _match_working_field_event(
        self,
        operation_id: str,
        event_id: str,
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized_context = self._working_field_json(
            dict(context), "reopen context", maximum=8192
        )
        combined: dict[str, Any] | None = None
        offset: int | None = None
        while True:
            page_id = operation_id + ":match"
            if offset is not None:
                page_id += f":{offset}"
            request: dict[str, Any] = {
                "operation": "match-relevance",
                "operation_id": page_id,
                "event_id": event_id,
                "context": normalized_context,
                "maximum": MAX_WORKING_FIELDS,
            }
            if offset is not None:
                request["cursor"] = offset
            page = self.semantic(request)
            if combined is None:
                combined = dict(page)
                combined["wakeups"] = list(page.get("wakeups", []))
                combined["unknown"] = list(page.get("unknown", []))
                combined["suppressed"] = list(page.get("suppressed", []))
            else:
                for key in ("wakeups", "unknown", "suppressed"):
                    combined[key].extend(page.get(key, []))
                combined["searched"] += page.get("searched", 0)
                combined["next_cursor"] = page.get("next_cursor")
                combined["limitation"] = page.get("limitation")
                if page.get("status") == "supported":
                    combined["status"] = "supported"
            next_offset = page.get("next_cursor")
            if next_offset is None:
                return combined or {"status": "supported", "wakeups": []}
            if (
                isinstance(next_offset, bool)
                or not isinstance(next_offset, int)
                or next_offset <= (offset or 0)
            ):
                raise ResidencyError("working-field relevance pagination did not advance")
            offset = next_offset

    def advance_working_field(
        self,
        operation_id: str,
        *,
        field_id: str,
        action: str,
        update: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Apply one owner-bound working-field transition using resident records."""
        operation_id = self._working_field_identity(operation_id, "operation_id")
        field_id = self._working_field_identity(field_id, "field_id")
        if len(operation_id) > 192 or not isinstance(action, str):
            raise ResidencyError("working-field operation identity or action is invalid")
        normalized = self._working_field_json(
            dict(update), "working-field update", maximum=32768
        )
        if not isinstance(normalized, dict):
            raise ResidencyError("working-field update must be a mapping")
        digest = self._working_field_operation_digest(action, field_id, normalized)
        current = self._working_field_current(field_id)
        direct_reopen = action == "reopen" and "wakeup_ref" not in normalized
        if direct_reopen:
            receipt = self._working_field_wake_receipt(
                operation_id, field_id, digest
            )
            if receipt is not None:
                return receipt
            if current is not None:
                current_payload = current.get("payload", {})
                if current_payload.get("last_wake_request_id") == operation_id:
                    if current_payload.get("last_wake_request_sha256") != digest:
                        raise ResidencyError(
                            "working-field operation identity was reused with different content"
                        )
                if (
                    current_payload.get("status") == "active"
                    and current_payload.get("last_wake_request_id") == operation_id
                ):
                    trigger_ref = current_payload.get("last_wake_trigger_ref")
                    wakeup_ref = current_payload.get("last_wakeup_ref")
                    trigger, trigger_record = self._working_field_exact_ref(
                        trigger_ref, require_current=False
                    )
                    _, wakeup_record = self._working_field_exact_ref(
                        wakeup_ref, require_current=False
                    )
                    if (
                        trigger["kind"] != "Event"
                        or trigger_record.get("status") != "active"
                        or wakeup_record.get("payload", {}).get("memory_role")
                        != "relevance-wakeup"
                        or wakeup_record.get("payload", {}).get("event_id")
                        != trigger["id"]
                    ):
                        raise ResidencyError("working-field wake provenance is unavailable")
                    result = self._working_field_projection(current)
                    self._working_field_store_wake_receipt(
                        operation_id,
                        field_id,
                        digest,
                        result,
                        trigger_ref,
                        [result],
                        require_current_trigger=False,
                    )
                    return result
        replayed = self._working_field_last_operation_matches(
            current, operation_id, digest
        )
        if replayed and action not in {"branch", "merge"}:
            if action == "rest" and current is not None:
                self._register_working_field_relevance(
                    operation_id + ":relevance", field_id, current
                )
            return self._working_field_projection(current)
        record_id = self._working_field_record_id(field_id)

        if action == "merge":
            parent_ids = normalized.get("parent_field_ids")
            parent_refs = normalized.get("parent_refs")
            if (not isinstance(parent_ids, list) or not 2 <= len(parent_ids) <= MAX_WORKING_FIELDS
                    or any(not isinstance(item, str) for item in parent_ids)
                    or len(set(parent_ids)) != len(parent_ids)
                    or not isinstance(parent_refs, list) or len(parent_refs) != len(parent_ids)):
                raise ResidencyError("merge requires distinct parent IDs and exact refs")
            question = self._working_field_text(normalized.get("question"), "question")
            purpose = self._working_field_text(normalized.get("purpose"), "purpose")
            expected = self._working_field_prospect(normalized.get("expected_contribution"))
            if expected is None:
                raise ResidencyError("expected_contribution is required")
            parents = []
            exact_refs = []
            for parent_id, raw_ref in zip(parent_ids, parent_refs):
                parent_id = self._working_field_identity(parent_id, "parent_field_id")
                if parent_id == field_id:
                    raise ResidencyError("a working field cannot merge itself")
                parent = self._working_field_current(parent_id)
                if parent is None:
                    raise ResidencyError("merge parent is unavailable")
                if replayed:
                    if parent_id not in current["payload"].get("merge_parent_ids", []):
                        raise ResidencyError("merge replay parents differ from the published lineage")
                    normalized_ref, _ = self._working_field_exact_ref(
                        raw_ref, require_current=False, require_active=False)
                    if normalized_ref != current["payload"]["merge_parent_refs"][len(parents)]:
                        raise ResidencyError("merge replay parent refs differ from the published lineage")
                    exact = current["payload"]["merge_parent_refs"][len(parents)]
                else:
                    exact, exact_record = self._working_field_exact_ref(raw_ref, require_current=True)
                    if exact != self._working_field_ref(parent) or exact_record["id"] != parent["id"]:
                        raise ResidencyError("merge parent ref is stale or foreign")
                    if parent["payload"].get("status") != "active":
                        raise ResidencyError("only active working fields can be merged")
                parents.append(parent)
                exact_refs.append(exact)
            if current is not None:
                if not replayed or current["payload"].get("merge_parent_refs") != exact_refs:
                    raise ResidencyError("merge field identity already exists")
                merged = current
            else:
                if self.working_fields(limit=MAX_WORKING_FIELDS)["total_count"] >= MAX_WORKING_FIELDS:
                    raise ResidencyError("working-field capacity is exhausted")
                lineage = {}
                for parent in parents:
                    seen = set()
                    frontier = list(parent["payload"].get("merge_parent_ids", []))
                    raw_parent = parent["payload"].get("parent_ref")
                    if isinstance(raw_parent, Mapping) and isinstance(raw_parent.get("id"), str):
                        parent_record = self._record(raw_parent["id"])
                        if parent_record is not None:
                            frontier.append(parent_record.get("payload", {}).get("field_id", ""))
                    while frontier:
                        ancestor = frontier.pop()
                        if not isinstance(ancestor, str) or not ancestor or ancestor in seen:
                            continue
                        seen.add(ancestor)
                        ancestor_record = self._working_field_current(ancestor)
                        if ancestor_record is not None:
                            ancestor_payload = ancestor_record["payload"]
                            frontier.extend(ancestor_payload.get("merge_parent_ids", []))
                            ancestor_ref = ancestor_payload.get("parent_ref")
                            if isinstance(ancestor_ref, Mapping) and isinstance(ancestor_ref.get("id"), str):
                                linked_parent = self._record(ancestor_ref["id"])
                                if linked_parent is not None:
                                    frontier.append(linked_parent.get("payload", {}).get("field_id", ""))
                    lineage[parent["payload"]["field_id"]] = seen
                parent_names = set(lineage)
                if any(a in lineage[b] or b in lineage[a]
                       for index, a in enumerate(parent_names)
                       for b in list(parent_names)[index + 1:]):
                    raise ResidencyError("ancestor/descendant fields cannot be merged")
                all_evidence = []
                all_provenance = []
                all_dependencies = []
                all_assumptions = []
                for parent in parents:
                    payload = parent["payload"]
                    all_evidence.extend(payload.get("evidence_refs", []))
                    all_provenance.extend(payload.get("provenance_refs", []))
                    all_dependencies.extend(parent.get("dependencies", []))
                    all_assumptions.extend(payload.get("assumptions", []))
                evidence = self._working_field_refs(
                    [*all_evidence, *normalized.get("evidence_refs", [])],
                    "evidence_refs", require_current=False, require_active=False)
                dependencies = self._working_field_refs(
                    [*all_dependencies, *normalized.get("dependencies", [])],
                    "dependencies", require_current=False, require_active=False)
                assumptions = self._working_field_json(
                    [*all_assumptions, *normalized.get("assumptions", [])],
                    "assumptions", maximum=8192)
                if not isinstance(assumptions, list) or len(assumptions) > 64:
                    raise ResidencyError("assumptions must be a bounded list")
                payload = {
                    "program_role": "working-field",
                    "working_field_schema": WORKING_FIELD_SCHEMA,
                    "field_id": field_id, "question": question, "purpose": purpose,
                    "status": "active", "parent_ref": None, "parent_field_ids": list(parent_ids),
                    "merge_parent_ids": list(parent_ids), "merge_parent_refs": exact_refs,
                    "merge_parent_contributions": [
                        {
                            "field_id": parent["payload"]["field_id"],
                            "program_ref": exact_refs[index],
                            "contribution": _plain(parent["payload"].get("contribution")),
                            "evidence_refs": _plain(parent["payload"].get("evidence_refs", [])),
                            "provenance_refs": _plain(parent["payload"].get("provenance_refs", [])),
                        }
                        for index, parent in enumerate(parents)
                    ],
                    "child_field_ids": [], "assumptions": assumptions,
                    "evidence_refs": evidence,
                    "provenance_refs": self._working_field_refs(
                        [*all_provenance, *normalized.get("provenance_refs", [])],
                        "provenance_refs",
                        require_current=False, require_active=False),
                    "expected_contribution": expected, "contribution": None,
                    "obstacle": None, "reopen_condition": None,
                    "transition": {"sequence": 0, "owner_generation_before": self.owner.state.generation,
                                   "reason": "merged"},
                    "opportunity_count": 0, "role_bindings": normalized.get("role_bindings", []),
                    "region_refs": normalized.get("region_refs", []),
                    "last_operation": {"id": operation_id, "sha256": digest},
                }
                self._register(operation_id + ":program", record_id, "Program", payload,
                               dependencies=dependencies)
                merged = self._working_field_current(field_id)
                if merged is None:
                    raise ResidencyError("merged working field was not published")
            # Parent transitions use deterministic operation identities, so partial
            # retries resume safely after any already-published parent transition.
            for parent_id in parent_ids:
                parent = self._working_field_current(parent_id)
                if parent is None:
                    raise ResidencyError("merge parent disappeared")
                children = list(parent["payload"].get("child_field_ids", []))
                if field_id not in children:
                    children.append(field_id)
                    linked = self._working_field_transition(
                        parent, operation_id=operation_id + ":parent-link:" + parent_id,
                        operation_digest=digest, reason="merge-linked",
                        changes={"child_field_ids": children})
                    self._register(operation_id + ":parent-link:" + parent_id, parent["id"],
                                   "Program", linked,
                                   dependencies=self._working_field_dependencies(parent))
                    parent = self._working_field_current(parent_id)
                if parent["payload"].get("status") == "active":
                    rest_update = {
                        "expected_ref": self._working_field_ref(parent),
                        "reason": "combined-into-" + field_id,
                        "reopen_condition": {
                            "clauses": [{"field": "manual_merge_reopen", "operator": "equals",
                                         "value": field_id}],
                        },
                    }
                    self.advance_working_field(
                        operation_id + ":parent-rest:" + parent_id,
                        field_id=parent_id, action="rest", update=rest_update)
            return self._working_field_projection(self._working_field_current(field_id))
        record_id = self._working_field_record_id(field_id)

        if action == "open":
            if current is not None:
                raise ResidencyError("working-field identity is already open")
            if self.working_fields(limit=MAX_WORKING_FIELDS)["total_count"] >= MAX_WORKING_FIELDS:
                raise ResidencyError("working-field capacity is exhausted")
            question = self._working_field_text(normalized.get("question"), "question")
            purpose = self._working_field_text(normalized.get("purpose"), "purpose")
            expected = self._working_field_prospect(
                normalized.get("expected_contribution")
            )
            if expected is None:
                raise ResidencyError("expected_contribution is required")
            provenance = self._working_field_refs(
                normalized.get("provenance_refs", []),
                "provenance_refs",
                require_current=False,
                require_active=False,
            )
            evidence = self._working_field_refs(
                normalized.get("evidence_refs", []),
                "evidence_refs",
                require_current=False,
                require_active=False,
            )
            dependencies = self._working_field_refs(
                normalized.get("dependencies", []),
                "dependencies",
                require_current=True,
            )
            if isinstance(expected, Mapping) and "value" in expected:
                for ref in expected["dependency_refs"]:
                    if ref not in dependencies:
                        dependencies.append(ref)
            continuation_value = normalized.get("continuation_ref")
            continuation_ref = None
            if continuation_value is not None:
                continuation_ref, _ = self._working_field_exact_ref(
                    continuation_value,
                    require_current=True,
                    require_active=False,
                )
                if continuation_ref not in dependencies:
                    dependencies.append(continuation_ref)
            assumptions = self._working_field_json(
                normalized.get("assumptions", []),
                "assumptions",
                maximum=8192,
            )
            if not isinstance(assumptions, list) or len(assumptions) > 64:
                raise ResidencyError("assumptions must be a bounded list")
            role_bindings = self._working_field_json(
                normalized.get("role_bindings", []),
                "role_bindings",
                maximum=8192,
            )
            region_refs = self._working_field_json(
                normalized.get("region_refs", []),
                "region_refs",
                maximum=8192,
            )
            if not isinstance(region_refs, list) or len(region_refs) > 64:
                raise ResidencyError("region_refs must be a bounded list")
            payload = {
                "program_role": "working-field",
                "working_field_schema": WORKING_FIELD_SCHEMA,
                "field_id": field_id,
                "question": question,
                "purpose": purpose,
                "status": "active",
                "parent_ref": None,
                "branch_purpose": None,
                "child_field_ids": [],
                "assumptions": assumptions,
                "evidence_refs": evidence,
                "provenance_refs": provenance,
                "expected_contribution": expected,
                "contribution": None,
                "obstacle": _plain(normalized.get("obstacle")),
                "reopen_condition": None,
                "continuation_ref": continuation_ref,
                "transition": {
                    "sequence": 0,
                    "owner_generation_before": self.owner.state.generation,
                    "reason": "opened",
                },
                "opportunity_count": 0,
                "role_bindings": role_bindings,
                "region_refs": region_refs,
                "last_operation": {"id": operation_id, "sha256": digest},
            }
            self._register(
                operation_id + ":program",
                record_id,
                "Program",
                payload,
                dependencies=dependencies,
            )
            opened = self._working_field_current(field_id)
            if opened is None:
                raise ResidencyError("working-field Program was not published")
            return self._working_field_projection(opened)

        if action == "branch":
            parent_id = self._working_field_identity(
                normalized.get("parent_field_id"), "parent_field_id"
            )
            parent = self._working_field_current(parent_id)
            if parent is None:
                raise ResidencyError("working-field branch parent is unavailable")
            supplied_parent_ref, _ = self._working_field_exact_ref(
                normalized.get("parent_ref"), require_current=False
            )
            parent_payload = parent["payload"]
            child_ids = list(parent_payload.get("child_field_ids", []))
            if replayed:
                if field_id not in child_ids:
                    if self._working_field_ref(parent) != supplied_parent_ref:
                        raise ResidencyError("branch parent changed before child linkage")
                    child_ids.append(field_id)
                    parent_dependencies = self._working_field_dependencies(parent)
                    parent_payload = self._working_field_transition(
                        parent,
                        operation_id=operation_id + ":parent",
                        operation_digest=digest,
                        reason="branch-opened",
                        changes={"child_field_ids": child_ids},
                    )
                    self._register(
                        operation_id + ":parent",
                        parent["id"],
                        "Program",
                        parent_payload,
                        dependencies=parent_dependencies,
                    )
                return self._working_field_projection(current)
            if parent_payload.get("status") != "active":
                raise ResidencyError("working-field branch parent is not active")
            if self._working_field_ref(parent) != supplied_parent_ref:
                raise ResidencyError("branch parent Program ref is stale")
            if current is not None:
                raise ResidencyError("working-field branch identity already exists")
            if self.working_fields(limit=MAX_WORKING_FIELDS)["total_count"] >= MAX_WORKING_FIELDS:
                raise ResidencyError("working-field capacity is exhausted")
            branch_purpose = self._working_field_text(
                normalized.get("branch_purpose"), "branch_purpose"
            )
            question = self._working_field_text(normalized.get("question"), "question")
            purpose = self._working_field_text(
                normalized.get("purpose", branch_purpose), "purpose"
            )
            parent_payload = parent["payload"]
            provenance = self._working_field_refs(
                normalized.get("provenance_refs", parent_payload.get("provenance_refs", [])),
                "provenance_refs",
                require_current=False,
                require_active=False,
            )
            evidence = self._working_field_refs(
                normalized.get("evidence_refs", parent_payload.get("evidence_refs", [])),
                "evidence_refs",
                require_current=False,
                require_active=False,
            )
            dependencies = self._working_field_refs(
                normalized.get("dependencies", parent.get("dependencies", [])),
                "dependencies",
                require_current=True,
            )
            continuation_value = normalized.get(
                "continuation_ref", parent_payload.get("continuation_ref")
            )
            continuation_ref = None
            if continuation_value is not None:
                continuation_ref, _ = self._working_field_exact_ref(
                    continuation_value,
                    require_current=True,
                    require_active=False,
                )
                if continuation_ref not in dependencies:
                    dependencies.append(continuation_ref)
            assumptions = self._working_field_json(
                normalized.get("assumptions", parent_payload.get("assumptions", [])),
                "assumptions",
                maximum=8192,
            )
            if not isinstance(assumptions, list) or len(assumptions) > 64:
                raise ResidencyError("assumptions must be a bounded list")
            expected = self._working_field_prospect(
                normalized.get(
                    "expected_contribution",
                    parent_payload.get("expected_contribution"),
                )
            )
            if expected is None:
                raise ResidencyError("expected_contribution is required")
            if isinstance(expected, Mapping) and "value" in expected:
                for ref in expected["dependency_refs"]:
                    if ref not in dependencies:
                        dependencies.append(ref)
            payload = {
                "program_role": "working-field",
                "working_field_schema": WORKING_FIELD_SCHEMA,
                "field_id": field_id,
                "question": question,
                "purpose": purpose,
                "status": "active",
                "parent_ref": supplied_parent_ref,
                "branch_purpose": branch_purpose,
                "child_field_ids": [],
                "assumptions": assumptions,
                "evidence_refs": evidence,
                "provenance_refs": provenance,
                "expected_contribution": expected,
                "contribution": None,
                "obstacle": _plain(normalized.get("obstacle")),
                "reopen_condition": None,
                "continuation_ref": continuation_ref,
                "transition": {
                    "sequence": 0,
                    "owner_generation_before": self.owner.state.generation,
                    "reason": "branched",
                },
                "opportunity_count": 0,
                "role_bindings": self._working_field_json(
                    normalized.get("role_bindings", []),
                    "role_bindings",
                    maximum=8192,
                ),
                "region_refs": self._working_field_json(
                    normalized.get("region_refs", parent_payload.get("region_refs", [])),
                    "region_refs",
                    maximum=8192,
                ),
                "last_operation": {"id": operation_id, "sha256": digest},
            }
            self._register(
                operation_id + ":program",
                record_id,
                "Program",
                payload,
                dependencies=dependencies,
            )
            branch = self._working_field_current(field_id)
            if branch is None:
                raise ResidencyError("working-field branch Program was not published")
            parent = self._working_field_current(parent_id)
            if parent is None:
                raise ResidencyError("branch parent disappeared after publication")
            parent_payload = _plain(parent["payload"])
            child_ids = list(parent_payload.get("child_field_ids", []))
            if field_id not in child_ids:
                if self._working_field_ref(parent) != supplied_parent_ref:
                    raise ResidencyError("branch parent changed before child linkage")
                child_ids.append(field_id)
                parent_dependencies = self._working_field_dependencies(parent)
                parent_payload = self._working_field_transition(
                    parent,
                    operation_id=operation_id + ":parent",
                    operation_digest=digest,
                    reason="branch-opened",
                    changes={"child_field_ids": child_ids},
                )
                self._register(
                    operation_id + ":parent",
                    parent["id"],
                    "Program",
                    parent_payload,
                    dependencies=parent_dependencies,
                )
            return self._working_field_projection(branch)

        if action not in {"contribute", "rest", "reopen"}:
            raise ResidencyError("working-field action must be open, branch, contribute, rest, or reopen")
        if current is None:
            raise ResidencyError("working-field Program is missing")
        expected_ref, _ = self._working_field_exact_ref(
            normalized.get("expected_ref"), require_current=True
        )
        if expected_ref != self._working_field_ref(current):
            raise ResidencyError("working-field transition targets a stale Program")
        payload = current["payload"]
        field_status = payload.get("status")
        dependencies, stale_dependencies = self._working_field_applicable_dependencies(
            current
        )
        changes: dict[str, Any] = {}
        if stale_dependencies:
            changes["stale_dependency_refs"] = self._working_field_refs(
                [
                    *payload.get("stale_dependency_refs", []),
                    *stale_dependencies,
                ],
                "stale_dependency_refs",
                require_current=False,
                require_active=False,
            )
        reason: str

        if action == "contribute":
            if field_status != "active":
                raise ResidencyError("resting working fields require a relevant wake before contribution")
            if stale_dependencies:
                raise ResidencyError("working-field contribution depends on stale records")
            contribution = self._working_field_json(
                normalized.get("contribution"),
                "contribution",
                maximum=8192,
            )
            measured_cost = (
                contribution.get("measured_cost")
                if isinstance(contribution, Mapping) else None
            )
            if measured_cost is not None:
                if (not isinstance(measured_cost, Mapping)
                        or set(measured_cost) != {"value", "unit"}
                        or isinstance(measured_cost.get("value"), bool)
                        or not isinstance(measured_cost.get("value"), (int, float))):
                    raise ResidencyError("measured_cost requires a finite nonnegative value and explicit unit")
                try:
                    cost_value = float(measured_cost["value"])
                except (OverflowError, ValueError) as exc:
                    raise ResidencyError(
                        "measured_cost requires a finite nonnegative value and explicit unit"
                    ) from exc
                if not math.isfinite(cost_value) or cost_value < 0:
                    raise ResidencyError("measured_cost requires a finite nonnegative value and explicit unit")
                measured_cost = {
                    "value": cost_value,
                    "unit": self._working_field_text(
                        measured_cost["unit"], "measured_cost.unit", maximum=64),
                }
            evidence = self._working_field_refs(
                normalized.get("evidence_refs", []),
                "evidence_refs",
                require_current=True,
            )
            provenance = self._working_field_refs(
                normalized.get("provenance_refs", []),
                "provenance_refs",
                require_current=False,
                require_active=False,
            )
            changes.update({
                "contribution": {
                    "value": contribution,
                    "measured_cost": measured_cost,
                    "evidence_refs": evidence,
                    "provenance_refs": provenance,
                },
                "measured_cost": (
                    measured_cost if measured_cost is not None else payload.get("measured_cost")
                ),
                "evidence_refs": self._working_field_refs(
                    [*payload.get("evidence_refs", []), *evidence],
                    "evidence_refs",
                    require_current=False,
                    require_active=False,
                ),
                "provenance_refs": self._working_field_refs(
                    [*payload.get("provenance_refs", []), *provenance],
                    "provenance_refs",
                    require_current=False,
                    require_active=False,
                ),
                "opportunity_count": int(payload.get("opportunity_count", 0)) + 1,
            })
            reason = self._working_field_text(
                normalized.get("reason", "contribution-recorded"),
                "reason",
                maximum=512,
            )
        elif action == "rest":
            if field_status != "active":
                raise ResidencyError("only an active working field can rest")
            rest_reason = self._working_field_text(
                normalized.get("reason"), "reason", maximum=512
            )
            condition = self._working_field_validate_condition(
                normalized.get("reopen_condition")
            )
            changes.update({
                "status": "resting",
                "obstacle": self._working_field_json(
                    normalized.get("obstacle", payload.get("obstacle")),
                    "obstacle",
                    maximum=8192,
                ),
                "reopen_condition": condition,
                "rest_reason": rest_reason,
            })
            reason = "rested:" + rest_reason
        else:
            if field_status != "resting":
                raise ResidencyError("only a resting working field can reopen")
            trigger_ref, trigger_record = self._working_field_exact_ref(
                normalized.get("trigger_ref"), require_current=True
            )
            if trigger_record.get("status") != "active":
                raise ResidencyError("working-field wake trigger is not active")
            context = normalized.get("context")
            if not isinstance(context, Mapping):
                raise ResidencyError("working-field reopen requires observation context")
            supplied_wakeup = normalized.get("wakeup_ref")
            if supplied_wakeup is None:
                resumed = self._wake_resting_working_fields(
                    operation_id + ":fanout",
                    trigger_ref,
                    context,
                    request_id=operation_id,
                    request_digest=digest,
                )
                reopened = next(
                    (item for item in resumed if item["field_id"] == field_id),
                    None,
                )
                if reopened is None:
                    raise ResidencyError(
                        "working-field wake condition did not match the observation"
                    )
                self._working_field_store_wake_receipt(
                    operation_id,
                    field_id,
                    digest,
                    reopened,
                    trigger_ref,
                    resumed,
                )
                return reopened
            if not isinstance(supplied_wakeup, Mapping):
                raise ResidencyError("working-field wakeup ref must be a mapping")
            candidate_wakeups = [supplied_wakeup]
            condition_ref = None
            wakeup_ref = None
            target_ref = self._working_field_ref(current)
            for raw_wakeup_ref in candidate_wakeups:
                if not isinstance(raw_wakeup_ref, Mapping):
                    continue
                wakeup = self._record(str(raw_wakeup_ref.get("id")))
                if (
                    wakeup is None
                    or wakeup.get("status") != "active"
                    or any(wakeup.get(key) != raw_wakeup_ref.get(key)
                           for key in ("id", "kind", "content_version"))
                    or wakeup.get("payload", {}).get("memory_role") != "relevance-wakeup"
                    or wakeup.get("payload", {}).get("event_id") != trigger_ref["id"]
                ):
                    continue
                targets = wakeup["payload"].get("target_refs", [])
                if not any(
                    isinstance(ref, Mapping)
                    and all(ref.get(key) == target_ref.get(key)
                            for key in ("id", "kind", "content_version"))
                    for ref in targets
                ):
                    continue
                raw_condition_ref = wakeup["payload"].get("condition_ref")
                if not isinstance(raw_condition_ref, Mapping):
                    continue
                condition = self._record(str(raw_condition_ref.get("id")))
                if (
                    condition is None
                    or condition.get("status") != "active"
                    or condition.get("payload", {}).get("memory_role") != "relevance-condition"
                    or condition.get("payload", {}).get("condition")
                    != payload.get("reopen_condition")
                    or any(condition.get(key) != raw_condition_ref.get(key)
                           for key in ("id", "kind", "content_version"))
                ):
                    continue
                condition_ref = dict(raw_condition_ref)
                wakeup_ref = self._working_field_ref(wakeup)
                break
            if condition_ref is None or wakeup_ref is None:
                raise ResidencyError("working-field wake condition did not match the observation")
            dependencies = self._working_field_refs(
                [*dependencies, trigger_ref],
                "working-field reopen dependencies",
                require_current=True,
            )
            wake_provenance = self._working_field_refs(
                [
                    *payload.get("provenance_refs", []),
                    condition_ref,
                    wakeup_ref,
                ],
                "working-field wake provenance",
                require_current=False,
                require_active=False,
            )
            changes.update({
                "status": "active",
                "last_wakeup_ref": wakeup_ref,
                "last_wake_trigger_ref": trigger_ref,
                "last_wake_condition_ref": condition_ref,
                "last_wake_reason": _plain(
                    self._record(condition_ref["id"])["payload"].get("reason", {})
                ),
                "provenance_refs": wake_provenance,
            })
            request_id = normalized.get("reopen_request_id")
            request_digest = normalized.get("reopen_request_sha256")
            if request_id is not None:
                request_id = self._working_field_identity(
                    request_id, "reopen_request_id"
                )
                if (
                    len(request_id) > 192
                    or not isinstance(request_digest, str)
                    or len(request_digest) != 64
                    or any(char not in "0123456789abcdef" for char in request_digest)
                ):
                    raise ResidencyError("working-field reopen request identity is invalid")
                changes.update({
                    "last_wake_request_id": request_id,
                    "last_wake_request_sha256": request_digest,
                })
            elif request_digest is not None:
                raise ResidencyError("working-field reopen request digest has no identity")
            reason = "reopened-by-relevant-observation"

        next_payload = self._working_field_transition(
            current,
            operation_id=operation_id,
            operation_digest=digest,
            reason=reason,
            changes=changes,
        )
        self._register(
            operation_id + ":program",
            record_id,
            "Program",
            next_payload,
            dependencies=dependencies,
        )
        updated = self._working_field_current(field_id)
        if updated is None:
            raise ResidencyError("working-field transition was not published")
        if action == "rest":
            try:
                self._register_working_field_relevance(
                    operation_id + ":relevance", field_id, updated
                )
            except (ResidencyError, FieldIntelligenceError):
                restore_payload = self._working_field_transition(
                    updated,
                    operation_id=operation_id + ":restore",
                    operation_digest=digest,
                    reason="rest-transition-could-not-register-wake",
                    changes={"status": "active"},
                )
                self._register(
                    operation_id + ":restore",
                    record_id,
                    "Program",
                    restore_payload,
                    dependencies=dependencies,
                )
                raise
            updated = self._working_field_current(field_id)
            if updated is None:
                raise ResidencyError("resting working-field Program was not retained")
        return self._working_field_projection(updated)

    def _wake_resting_working_fields(
        self,
        operation_id: str,
        trigger_ref: Mapping[str, Any],
        context: Mapping[str, Any],
        *,
        request_id: str | None = None,
        request_digest: str | None = None,
    ) -> list[dict[str, Any]]:
        """Route one current observation through the resident relevance Programs."""
        if (request_id is None) != (request_digest is None):
            raise ResidencyError("working-field reopen request identity is incomplete")
        trigger, trigger_record = self._working_field_exact_ref(
            trigger_ref, require_current=True
        )
        if trigger_record.get("status") != "active":
            return []
        fields = self.working_fields(limit=MAX_WORKING_FIELDS)
        if fields["truncated"]:
            raise ResidencyError("working-field wake fan-out exceeds its declared bound")
        resting = {
            tuple(item["program_ref"][key] for key in ("id", "kind", "content_version")):
                item
            for item in fields["items"]
            if item["status"] == "resting"
        }
        if not resting:
            return []
        matched = self._match_working_field_event(
            operation_id + ":relevance",
            trigger["id"],
            context,
        )
        if matched.get("status") != "supported":
            return []
        resumed = []
        for raw_wakeup_ref in matched.get("wakeups", []):
            if not isinstance(raw_wakeup_ref, Mapping):
                continue
            wakeup = self._record(str(raw_wakeup_ref.get("id")))
            if (
                wakeup is None
                or wakeup.get("status") != "active"
                or any(wakeup.get(key) != raw_wakeup_ref.get(key)
                       for key in ("id", "kind", "content_version"))
            ):
                continue
            for target in wakeup.get("payload", {}).get("target_refs", []):
                if not isinstance(target, Mapping):
                    continue
                key = tuple(target.get(name) for name in ("id", "kind", "content_version"))
                item = resting.get(key)
                if item is None:
                    continue
                wake_operation = "research:working-field:wake:" + hashlib.sha256(
                    (
                        operation_id + "\0" + item["field_id"] + "\0"
                        + str(wakeup["id"])
                    ).encode("utf-8")
                ).hexdigest()[:32]
                wake_update = {
                    "expected_ref": item["program_ref"],
                    "trigger_ref": trigger,
                    "context": dict(context),
                    "wakeup_ref": self._working_field_ref(wakeup),
                }
                if request_id is not None and request_digest is not None:
                    wake_update.update({
                        "reopen_request_id": request_id,
                        "reopen_request_sha256": request_digest,
                    })
                try:
                    resumed.append(self.advance_working_field(
                        wake_operation,
                        field_id=item["field_id"],
                        action="reopen",
                        update=wake_update,
                    ))
                except ResidencyError as exc:
                    if str(exc) in {
                        "working-field transition targets a stale Program",
                        "only a resting working field can reopen",
                    }:
                        continue
                    raise
                break
        return resumed

    def _ensure_catalog_working_fields(self) -> None:
        for item in self._catalog():
            field_id = item["id"]
            request = item["request"]
            question = request.get("question")
            if not isinstance(question, str) or not question.strip():
                question = item["summary"]
            operation_id = (
                "research:working-field:catalog-open:"
                + hashlib.sha256(field_id.encode("utf-8")).hexdigest()[:24]
            )
            self.advance_working_field(
                operation_id,
                field_id=field_id,
                action="open",
                update={
                    "question": question,
                    "purpose": item["summary"],
                    "expected_contribution": {
                        "kind": "observed-research-result",
                        "summary": item["summary"],
                    },
                },
            )

    def _checkpoint(self, cursor: Mapping[str, Any], **updates: Any) -> None:
        successor = {**dict(cursor), **updates, "sequence": int(cursor["sequence"]) + 1}
        for key in ("recalled_episode", "source_revision_id", "learning_status", "learning_event"):
            successor.pop(key, None)
        selected = successor.get("selected")
        if isinstance(selected, Mapping):
            successor["selected"] = {"id": selected["id"]}
        identity = f"{CURSOR_PREFIX}{successor['sequence']:012d}"
        self._register(identity, identity, "Value", successor)

    def initialize(self, *, workspace: Path, mission: str = DEFAULT_MISSION,
                   work: Sequence[Mapping[str, Any]] | None = None,
                   profile: Mapping[str, int] | None = None) -> None:
        workspace = Path(workspace).resolve(strict=True)
        if not workspace.is_dir() or not isinstance(mission, str) or not mission.strip():
            raise ResidencyError("a workspace directory and a nonempty mission are required")
        catalog = _work_items(initial_work(workspace) if work is None else work)
        manifest = {"schema": SCHEMA, "mission": mission, "workspace": str(workspace),
                    "work": catalog, "profile": dict(profile or DEFAULT_PROFILE),
                    "authority": {"live_source_replacement": False, "external_actions": False}}
        if self._computer() is not None:
            computer_session = self._computer()._value("session")
            if computer_session.get("kernel") == "cognition.field":
                self._settle()
                resident = self._record(MISSION_ID)
                if resident is None or resident["payload"] != manifest:
                    raise ResidencyError("existing residency has a different mission or configuration")
                self._ensure_catalog_working_fields()
                return
        self.owner.operate_computer("research:configure", computer_id="research", action="configure",
                                    arguments={"profile": manifest["profile"]})
        seed = []
        for identity, payload in (
            (MISSION_ID, manifest),
            (CATALOG_ID, {"work": catalog}),
            (f"{CURSOR_PREFIX}{0:012d}", {"sequence": 0, "round": 0, "completed": 0,
              "phase": "seed", "remaining": [], "selected": None}),
        ):
            seed.append(make_semantic_record(record_id=identity, kind="Value", content_version=1,
                        created_at=0, payload=payload, scope="research-residency",
                        epistemic_kind="asserted", status="active"))
        self.owner.operate_computer("research:initialize", computer_id="research", action="submit",
            arguments={"kernel": "cognition.field", "kind": "research-residency",
                       "state": semantic_cognition_state(scope="research-residency", seed_records=seed,
                           bounds={"max_records": 16384, "max_operations": 16384, "max_versions": 128}),
                       "arguments": {"operation": "inspect", "operation_id": "research:initialized"},
                       "steps": 4096})
        self._settle()
        self._ensure_catalog_working_fields()

    def inspect(self) -> dict[str, Any]:
        task = self._task()
        cursor = self._cursor()
        mission = self._required_record(MISSION_ID)["payload"]
        outcomes = []
        for identity in task["current"]["Assessment"]:
            if identity.startswith("research:outcome:"):
                record = self._required_record(identity)
                payload = record["payload"]
                outcomes.append({
                    "operation_id": payload["work_operation_id"],
                    "work_id": payload["question_id"],
                    "status": payload["result_status"],
                    "summary": payload["summary"],
                    "source_revision_id": payload["source_revision_id"],
                })
        memory_roles: dict[str, int] = {}
        for family in task["current"].values():
            for reference in family.values():
                record = task["records"][reference["id"]][-1]
                role = record["payload"].get("memory_role")
                if isinstance(role, str):
                    memory_roles[role] = memory_roles.get(role, 0) + 1
        working_fields = self.working_fields(limit=16)
        computer = self._computer()
        return {
            "schema": SCHEMA,
            "mission": mission["mission"],
            "workspace": mission["workspace"],
            "phase": cursor["phase"],
            "round": cursor["round"],
            "completed": cursor["completed"],
            "selected": cursor.get("selected"),
            "remaining": cursor["remaining"],
            "outcomes": outcomes[-16:],
            "working_fields": working_fields,
            "resident_records": len(task["records"]),
            "resident_operations": len(task["indexes"]["operations"]),
            "learned_procedures": len(task["libraries"]["procedures"]),
            "living_memory": {
                "roles": dict(sorted(memory_roles.items())),
                "recall_episodes": memory_roles.get("recall-episode", 0),
                "prospective_conditions": memory_roles.get(
                    "relevance-condition", 0
                ),
                "relevance_wakeups": memory_roles.get("relevance-wakeup", 0),
                "hypotheses": memory_roles.get("quiet-synthesis", 0),
                "maintenance_assessments": memory_roles.get(
                    "maintenance-assessment", 0
                ),
            },
            "field_state_sha256": computer.state_sha256,
            "owner_state_sha256": self.owner.state.state_sha256,
            "computer_status": computer._value("session")["status"],
            "authority": mission["authority"],
            "hive": _plain(self.session.status()),
        }

    def _work_id(self, cursor: Mapping[str, Any], item_id: str) -> str:
        return f"{WORK_PREFIX}{int(cursor['round']):08d}:{item_id}"
    def _adapter_artifact_home(self, workspace: Path, operation_id: str) -> Path:
        """Keep adapter-generated candidate/source artifacts outside the source tree."""
        workspace = workspace.resolve(strict=True)
        residency = self.home.resolve()
        residency_key = hashlib.sha256(str(residency).encode("utf-8")).hexdigest()[:16]
        root = workspace.parent / f".{workspace.name}-research-artifacts" / residency_key
        if root.resolve().is_relative_to(workspace):
            temp_root = Path(os.environ.get("TEMP", os.environ.get("TMP", str(workspace.parent))))
            root = temp_root / "cassi-research-artifacts" / residency_key
        return root / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
    def _communication_route_order(self, item_ids: Sequence[str]) -> list[str]:
        """Apply actual-use locality only as a bounded eligible-work hint."""
        from cassi_field_communication import LOCALITY_SCHEMA, anticipate_routes

        locality_payload = self._communication_locality()
        routes = (
            locality_payload.get("routes")
            if isinstance(locality_payload, Mapping)
            and locality_payload.get("schema") == LOCALITY_SCHEMA
            and isinstance(locality_payload.get("routes"), Mapping)
            else {}
        )
        items = {item["id"]: item for item in self._catalog()}
        item_routes: dict[str, str] = {}
        for item_id in item_ids:
            item = items.get(item_id)
            request = item.get("request") if isinstance(item, Mapping) else None
            hinted = _declared_communication_route(request, item_id)
            if hinted is not None and hinted in routes:
                item_routes[item_id] = hinted
        if not item_routes:
            return list(item_ids)
        anticipated = set(anticipate_routes(
            {"schema": LOCALITY_SCHEMA, "routes": routes, "observations": []},
            tuple(dict.fromkeys(item_routes.values())),
            limit=min(8, len(set(item_routes.values()))),
        ))
        order = {item_id: index for index, item_id in enumerate(item_ids)}
        return sorted(
            item_ids,
            key=lambda item_id: (
                0 if item_id in item_routes and item_routes[item_id] in anticipated else 1,
                -float(routes.get(item_routes.get(item_id, ""), {}).get("affinity", 0.0)),
                order[item_id],
            ),
        )


    def _circulation_modulation(self, count: int) -> Mapping[str, Any] | None:
        """The bounded eligible-work modulation of the resident circulation.

        Work sites are the eligible continuations this residency presents, in
        its declared fairness order.  The realised flow supplies a bounded
        priority pattern only: eligibility, authority, and the fairness rule
        stay the owner's, and flow magnitude is never evidence.  No resident
        circulation means no hint, which is the declared no-flow case.
        """
        if count <= 0:
            return None
        return self.owner.circulation_modulation(
            [{"sequence": index} for index in range(count)]
        )

    def _choose(self, cursor: Mapping[str, Any], identity: str) -> str:
        modulation = self._circulation_modulation(len(cursor["remaining"]))
        relevant_by_item: dict[str, list[dict[str, Any]]] = {}
        for item_id in cursor["remaining"]:
            matched = self._match_research_memory(cursor, item_id)
            relevant = self._relevant_assessments(
                matched, self._work_id(cursor, item_id) + ":candidate-memory-v3", limit=8
            )
            if not relevant:
                continue
            relevant_by_item[item_id] = relevant
            priority_operation_id = (
                identity + ":memory-priority:"
                + hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:16]
            )
            if priority_operation_id in self._task()["indexes"]["operations"]:
                continue
            weight = sum(row["priority"] for row in relevant)
            result = sum(
                (1.0 if row["result_status"] in {"observed", "supported"}
                 else -1.0 if row["result_status"] in {"support-gap", "rejected"}
                 else 0.0) * row["priority"]
                for row in relevant
            )
            record_id = self._work_id(cursor, item_id)
            obligation = self._required_record(record_id)
            payload = dict(obligation["payload"])
            base_priority = float(payload.get("priority", 0.0))
            payload["priority"] = base_priority + 0.25 * result / max(weight, 1e-12)
            dependencies = list(obligation.get("dependencies", []))
            dependencies.extend(
                row["wakeup_ref"] for row in relevant
                if not any(
                    ref.get("id") == row["wakeup_ref"]["id"]
                    and ref.get("content_version") == row["wakeup_ref"]["content_version"]
                    for ref in dependencies if isinstance(ref, Mapping)
                )
            )
            roots = list(obligation.get("support_roots", []))
            roots.extend(row["source_revision_id"] for row in relevant)
            self._register(
                priority_operation_id,
                record_id, "Obligation", payload, status=obligation["status"],
                roots=sorted(set(roots)), dependencies=dependencies,
                epistemic_kind=obligation.get("epistemic_kind", "asserted"),
            )
        request = {
            "operation": "autonomous-agenda",
            "operation_id": identity + ":agenda",
            "goal": {"objective": self._required_record(MISSION_ID)["payload"]["mission"]},
            "obligation_prefix": f"{WORK_PREFIX}{int(cursor['round']):08d}:",
            "eligible_work_order": [
                self._work_id(cursor, item_id)
                for item_id in self._communication_route_order(cursor["remaining"])
            ],
            "max_items": 128,
        }
        if modulation is not None:
            request["circulation"] = modulation
        agenda = self.semantic(request)
        if relevant_by_item:
            allowed = {self._work_id(cursor, item_id): item_id for item_id in cursor["remaining"]}
            for item in agenda["agenda"]:
                obligation = item.get("obligation", {})
                if obligation.get("id") in allowed:
                    selected_id = allowed[obligation["id"]]
                    return selected_id
        candidates = []
        for item_id in self._communication_route_order(cursor["remaining"]):
            reference = self._task()["current"]["Obligation"][self._work_id(cursor, item_id)]
            candidates.append({"candidate_id": item_id, "reference": reference})
        selection = self.semantic({
            "operation": "history-select",
            "operation_id": identity + ":history",
            "candidates": candidates,
        })
        selected = selection.get("selected")
        if selected is not None:
            return selected["candidate_id"]
        allowed = {self._work_id(cursor, item_id): item_id for item_id in cursor["remaining"]}
        for item in agenda["agenda"]:
            obligation = item.get("obligation", {})
            if obligation.get("id") in allowed:
                return allowed[obligation["id"]]
        raise ResidencyError("field agenda did not select any available research obligation")


    def _selection_event_for_work(
        self,
        cursor: Mapping[str, Any],
        selected_id: str,
        operation_id: str,
        obligation: Mapping[str, Any],
    ) -> dict[str, Any]:
        if obligation.get("id") != operation_id or obligation.get("kind") != "Obligation":
            raise ResidencyError("selected research obligation is unavailable")
        selection_sequence = int(cursor["sequence"]) - 2
        if selection_sequence < 0:
            raise ResidencyError("research selection phase is unavailable")
        selection_identity = f"research:phase:{selection_sequence:012d}"
        operations = self._task()["indexes"]["operations"]
        obligation_ref = {
            key: obligation[key] for key in ("id", "kind", "content_version")
        }
        memory_prioritized = any(
            key.startswith(selection_identity + ":memory-priority:")
            for key in operations
        )
        selection_event = None
        selected_by_history = False
        history_operation = operations.get(selection_identity + ":history")
        history_result = (
            history_operation.get("result")
            if isinstance(history_operation, Mapping) else None
        )
        if not memory_prioritized and isinstance(history_result, Mapping):
            history_selection = history_result.get("selected")
            if history_selection is not None:
                if (not isinstance(history_selection, Mapping)
                        or history_selection.get("candidate_id") != selected_id):
                    raise ResidencyError("research history selection does not match its work")
                history_ref = history_selection.get("reference")
                if (not isinstance(history_ref, Mapping)
                        or any(history_ref.get(key) != value
                               for key, value in obligation_ref.items())):
                    raise ResidencyError("research history reference does not match its work")
                selection_event = history_result.get("event")
                selected_by_history = True
        if selection_event is None:
            agenda_operation = operations.get(selection_identity + ":agenda")
            agenda_result = (
                agenda_operation.get("result")
                if isinstance(agenda_operation, Mapping) else None
            )
            if not isinstance(agenda_result, Mapping):
                raise ResidencyError("research agenda result is unavailable")
            agenda_rows = agenda_result.get("agenda")
            if (not isinstance(agenda_rows, list)
                    or not any(
                        isinstance(row, Mapping)
                        and isinstance(row.get("obligation"), Mapping)
                        and all(
                            row["obligation"].get(key) == value
                            for key, value in obligation_ref.items()
                        )
                        for row in agenda_rows
                    )):
                raise ResidencyError("research agenda selection does not match its work")
            selection_event = agenda_result.get("event")
        if (not isinstance(selection_event, Mapping)
                or selection_event.get("kind") != "Event"):
            raise ResidencyError("selected research work has no agenda event")
        event = self._record(str(selection_event.get("id")))
        if (event is None or event["status"] != "active"
                or any(event.get(key) != selection_event.get(key)
                       for key in ("id", "kind", "content_version"))):
            raise ResidencyError("selected research agenda event is stale")
        if selected_by_history:
            payload = event.get("payload", {}).get("history_selection", {})
            history_selection = (
                payload.get("selected") if isinstance(payload, Mapping) else None
            )
            history_ref = (
                history_selection.get("reference")
                if isinstance(history_selection, Mapping) else None
            )
            if (not isinstance(history_selection, Mapping)
                    or history_selection.get("candidate_id") != selected_id
                    or not isinstance(history_ref, Mapping)
                    or any(history_ref.get(key) != value
                           for key, value in obligation_ref.items())):
                raise ResidencyError("selected research history event is inconsistent")
        else:
            dependencies = event.get("dependencies", [])
            if (not isinstance(dependencies, list)
                    or not any(
                        isinstance(ref, Mapping)
                        and all(ref.get(key) == value
                                for key, value in obligation_ref.items())
                        for ref in dependencies
                    )):
                raise ResidencyError("selected research agenda event omits its obligation")
        return dict(selection_event)

    def _execute_collective_method(
        self,
        request: Mapping[str, Any],
        operation_id: str,
    ) -> dict[str, Any]:
        synthesis_id = request.get("synthesis_id")
        bindings = request.get("bindings")
        if not isinstance(synthesis_id, str) or not synthesis_id:
            return {
                "status": "support-gap",
                "summary": "No retained collective method identity was supplied.",
                "evidence": {
                    "operation_id": operation_id,
                    "support_gap": "missing-synthesis-id",
                },
            }
        if not isinstance(bindings, Mapping):
            return {
                "status": "rejected",
                "summary": "Collective method bindings must be a typed mapping.",
                "evidence": {
                    "operation_id": operation_id,
                    "synthesis_id": synthesis_id,
                    "rejected": "invalid-bindings",
                },
            }
        organism_home = self.home.parent
        if not (organism_home / "manifest.json").is_file():
            return {
                "status": "support-gap",
                "summary": "No field-owned research organism is attached.",
                "evidence": {
                    "operation_id": operation_id,
                    "synthesis_id": synthesis_id,
                    "support_gap": "missing-organism-manifest",
                },
            }
        raw_owner = getattr(self.session, "raw_owner", None)
        hive = getattr(self.session, "hive", None)
        if raw_owner is None or hive is None:
            return {
                "status": "support-gap",
                "summary": "The resident owner and Hive session are unavailable.",
                "evidence": {
                    "operation_id": operation_id,
                    "synthesis_id": synthesis_id,
                    "support_gap": "missing-owner-hive-session",
                },
            }
        field_home = getattr(self.session, "field_home", None)
        identity = getattr(self.session, "identity", None)
        if (
            field_home is None
            or Path(field_home).resolve() != self.home / "field"
            or identity is None
            or getattr(identity, "hive_id", None) != getattr(hive, "hive_id", None)
            or getattr(identity, "branch", None) != getattr(hive, "branch", None)
            or getattr(identity, "hive_id", None) != "main"
            or getattr(identity, "branch", None) != "main"
        ):
            return {
                "status": "support-gap",
                "summary": "The live field does not match the organism root Hive.",
                "evidence": {
                    "operation_id": operation_id,
                    "synthesis_id": synthesis_id,
                    "support_gap": "owner-hive-context-mismatch",
                },
            }

        from cassi_research_organism import OrganismError, ResearchOrganism

        try:
            organism = ResearchOrganism(
                organism_home,
                hive_home=Path(hive.root).parent,
                root_owner=raw_owner,
                root_lock=hive._lock,
            )
            receipt = organism.execute_collective_synthesis(
                synthesis_id,
                operation_id,
                bindings,
                expected_program_ref=request.get("expected_program_ref"),
                maximum_work=request.get("maximum_work"),
            )
        except OrganismError as exc:
            reason = str(exc)
            if reason in {
                "collective synthesis has unresolved capability gaps",
                "collective synthesis has no executable resident program",
                "collective continuation method changed after suspension",
            }:
                return {
                    "status": "support-gap",
                    "summary": "The retained collective method is unavailable.",
                    "evidence": {
                        "operation_id": operation_id,
                        "synthesis_id": synthesis_id,
                        "support_gap": reason,
                    },
                }
            if reason in {
                "collaborative method rejected its bindings",
                "collaborative execution work bound is invalid",
                "collective method exceeds the declared execution work bound",
            } or reason.startswith("synthesis_id "):
                return {
                    "status": "rejected",
                    "summary": "The collective method rejected this request.",
                    "evidence": {
                        "operation_id": operation_id,
                        "synthesis_id": synthesis_id,
                        "rejected": reason,
                    },
                }
            raise ResidencyError(
                "retained collective method execution failed"
            ) from exc

        outputs = receipt.get("outputs")
        observations = []
        if isinstance(outputs, Mapping):
            observations = [
                {
                    "subject": f"{operation_id}:output:{name}",
                    "attribute": "collective-method-output",
                    "value": {"sha256": sha256_value(value)},
                    "frame": {
                        "program_ref": receipt["program_ref"],
                        "synthesis_id": synthesis_id,
                    },
                }
                for name, value in outputs.items()
                if isinstance(name, str)
            ]
        return {
            "status": "supported",
            "summary": f"Executed retained collective method {synthesis_id}.",
            "outputs": _plain(outputs),
            "evidence": {
                "execution_event_id": (
                    f"event:collaboration-execution:{operation_id}"
                ),
                "maximum_work": receipt["maximum_work"],
                "method_sha256": receipt["method_sha256"],
                "operation_id": operation_id,
                "program_ref": receipt["program_ref"],
                "synthesis_id": synthesis_id,
                "work": receipt["work"],
            },
            "observations": observations,
        }

    def record_root_method_assessment(
        self,
        operation_id: str,
        *,
        result: Mapping[str, Any],
        program_ref: Mapping[str, Any],
        execution_event_ref: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Archive and assess one root-authored typed-method execution."""
        operation_id = self._working_field_identity(
            operation_id, "research method operation_id"
        )
        normalized = _plain(result)
        if (
            not isinstance(normalized, dict)
            or normalized.get("status") != "supported"
            or not isinstance(normalized.get("summary"), str)
            or not isinstance(normalized.get("evidence"), Mapping)
        ):
            raise ResidencyError(
                "root research method result must be a supported typed receipt"
            )
        program_ref = _plain(program_ref)
        execution_event_ref = _plain(execution_event_ref)
        for reference, expected_kind in (
            (program_ref, "Program"),
            (execution_event_ref, "Event"),
        ):
            if (
                not isinstance(reference, Mapping)
                or reference.get("kind") != expected_kind
                or not isinstance(reference.get("id"), str)
                or isinstance(reference.get("content_version"), bool)
                or not isinstance(reference.get("content_version"), int)
            ):
                raise ResidencyError(
                    "root research method assessment has an invalid dependency"
                )
            record = self._record(str(reference["id"]))
            if (
                record is None
                or record.get("status") != "active"
                or any(
                    record.get(key) != reference.get(key)
                    for key in ("id", "kind", "content_version")
                )
            ):
                raise ResidencyError(
                    "root research method assessment dependency is stale"
                )
        evidence = normalized["evidence"]
        source_ids = evidence.get("source_ids")
        source_provenance = evidence.get("source_provenance")
        if (
            evidence.get("support_status") != "supported"
            or not isinstance(evidence.get("research_program_id"), str)
            or not isinstance(evidence.get("question_id"), str)
            or not isinstance(evidence.get("question"), str)
            or not isinstance(evidence.get("question_sha256"), str)
            or evidence.get("question_sha256")
            != sha256_value(evidence["question"])
            or not isinstance(evidence.get("source_identity_sha256"), str)
            or len(evidence["source_identity_sha256"]) != 64
            or not isinstance(source_ids, list)
            or any(not isinstance(source_id, str) for source_id in source_ids)
            or len(set(source_ids)) != len(source_ids)
            or not isinstance(source_provenance, Mapping)
            or set(source_ids) != set(source_provenance)
            or evidence.get("program_ref") != program_ref
        ):
            raise ResidencyError(
                "root research method assessment evidence is malformed"
            )
        evidence_sha256 = hashlib.sha256(
            canonical_json_bytes(evidence)
        ).hexdigest()

        output_bytes = canonical_json_bytes(normalized)
        if len(output_bytes) > MAX_RESULT_BYTES:
            raise ResidencyError(
                "root research method assessment exceeds its result bound"
            )
        source = SourceInput(
            source_id=operation_id,
            content=output_bytes,
            media_type="application/json",
            codec=CODEC_JSON,
            observed_timestamp=operation_id,
            scope="research-residency",
            claim_category="research-method-result",
            fidelity="exact-observed-bytes",
            labels=("research-residency", "root-research-method"),
        )
        archived = self.owner.archive_source(
            operation_id=operation_id + ":archive",
            source=source,
            context={"work_operation_id": operation_id},
        )
        archived_source = archived.get("source")
        source_revision_id = (
            archived_source.get("revision_id")
            if isinstance(archived_source, Mapping)
            else None
        )
        if not isinstance(source_revision_id, str) or not source_revision_id:
            raise ResidencyError(
                "root research method result archive omitted its source revision"
            )
        observed = self.semantic(
            {
                "operation": "observe",
                "operation_id": operation_id + ":observe",
                "delivery_id": operation_id + ":delivery",
                "event_id": operation_id + ":event",
                "observations": self._observations(operation_id, normalized),
                "source": {"source_revision_id": source_revision_id},
                "support_roots": [source_revision_id],
            }
        )
        observation_ref = observed.get("event")
        if not isinstance(observation_ref, Mapping) or observation_ref.get(
            "kind"
        ) != "Event":
            raise ResidencyError(
                "root research method observation did not return its event"
            )
        observation = self._record(str(observation_ref.get("id")))
        if (
            observation is None
            or observation.get("status") != "active"
            or any(
                observation.get(key) != observation_ref.get(key)
                for key in ("id", "kind", "content_version")
            )
        ):
            raise ResidencyError(
                "root research method observation event is stale"
            )

        assessment_id = "research:root-method-assessment:" + operation_id
        assessment = self._register(
            operation_id + ":assess",
            assessment_id,
            "Assessment",
            {
                "schema": "cassifi.research-residency-root-method-assessment.v1",
                "assessment_kind": "typed-method-execution",
                "work_operation_id": operation_id,
                "research_program_id": evidence["research_program_id"],
                "question_id": evidence["question_id"],
                "question": evidence["question"],
                "question_sha256": evidence["question_sha256"],
                "method_id": evidence.get("method_id"),
                "method_sha256": evidence.get("method_sha256"),
                "status": "supported",
                "result_status": "supported",
                "summary": normalized["summary"],
                "source_revision_id": source_revision_id,
                "source_identity_sha256": evidence[
                    "source_identity_sha256"
                ],
                "source_ids": _plain(evidence["source_ids"]),
                "source_provenance": _plain(evidence["source_provenance"]),
                "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
                "evidence_sha256": evidence_sha256,
                "program_ref": dict(program_ref),
                "execution_event_ref": dict(execution_event_ref),
                "observation_event_ref": dict(observation_ref),
            },
            roots=[source_revision_id],
            dependencies=[
                dict(program_ref),
                dict(execution_event_ref),
                dict(observation_ref),
            ],
            epistemic_kind="assessed",
        )
        assessment_ref = assessment.get("record")
        if not isinstance(assessment_ref, Mapping):
            raise ResidencyError(
                "root research method assessment was not committed"
            )
        record = self._record(str(assessment_ref.get("id")))
        if (
            record is None
            or record.get("status") != "active"
            or any(
                record.get(key) != assessment_ref.get(key)
                for key in ("id", "kind", "content_version")
            )
        ):
            raise ResidencyError(
                "root research method assessment record is stale"
            )
        return {
            "assessment_ref": dict(assessment_ref),
            "observation_event_ref": dict(observation_ref),
            "source_revision_id": source_revision_id,
            "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        }

    def _execute(self, cursor: Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
        selected = cursor["selected"]
        item = next(item for item in self._catalog() if item["id"] == selected["id"])
        operation_id = self._work_id(cursor, item["id"])
        request = {**item["request"], "operation_id": operation_id}
        directory = self.home / "artifacts" / hashlib.sha256(operation_id.encode()).hexdigest()
        output_path = directory / "result.json"
        marker = directory / "request.json"
        request_bytes = canonical_json_bytes(request)
        if marker.exists() and marker.read_bytes() != request_bytes:
            raise ResidencyError("research artifact request does not match the resident work")
        if output_path.exists():
            output_bytes = output_path.read_bytes()
            output = json.loads(output_bytes)
        elif marker.exists() and request["kind"] not in {"collective-method", "acquired-method"}:
            # Even read-only observations may change. An ambiguous interrupted sample
            # is recorded as missing, never silently replaced by a later sample.
            output = {"status": "support-gap", "summary": "Previous execution has no durable acknowledgment; no action was repeated.",
                      "evidence": {"operation_id": operation_id, "ambiguous_execution": True}}
            output_bytes = canonical_json_bytes(output)
            _commit_bytes(output_path, output_bytes)
        else:
            if not marker.exists():
                _commit_bytes(marker, request_bytes)
            workspace = Path(self._required_record(MISSION_ID)["payload"]["workspace"])
            kind = request["kind"]
            if kind == "acquired-method":
                method_action = request.get("action", "select-execute")
                method_arguments = request.get("arguments")
                if not isinstance(method_arguments, Mapping):
                    raise ResidencyError("acquired method work requires typed arguments")
                method_operation_id = "research:acquired-method:" + hashlib.sha256(
                    operation_id.encode("utf-8")
                ).hexdigest()
                try:
                    method_result = self.owner.acquired_method_operation(
                        method_operation_id,
                        action=method_action,
                        arguments=method_arguments,
                    )
                except FieldIntelligenceError as exc:
                    if exc.code not in {"METHOD_GUARD_FAILED", "METHOD_UNIT_MISMATCH", "METHOD_INPUT_MISMATCH"}:
                        raise
                    method_result = {"result": {"status": "no-compatible-method"}}
                if method_result.get("result", {}).get("status") == "no-compatible-method":
                    fallback = request.get("fallback_request")
                    if not isinstance(fallback, Mapping) or not isinstance(fallback.get("kind"), str):
                        output = {
                            "status": "support-gap",
                            "summary": "No admitted method matched and no authorized fallback was declared.",
                            "evidence": {"operation_id": operation_id, "support_gap": "method-guard-mismatch"},
                        }
                    else:
                        from cassi_research_worlds import execute_work
                        output = execute_work(
                            {**dict(fallback), "operation_id": operation_id},
                            workspace=workspace,
                            artifact_home=self._adapter_artifact_home(workspace, operation_id),
                            semantic=self.semantic,
                        )
                else:
                    method = method_result.get("method", {})
                    execution = method_result.get("result", {})
                    output = {
                        "status": "supported" if execution.get("status") in {"executed", "supported", "outcome-recorded"} else "rejected",
                        "summary": f"Executed acquired method {method.get('method_id', 'unknown')}.",
                        "outputs": _plain(execution),
                        "evidence": {
                            "operation_id": method_operation_id,
                            "method_id": method.get("method_id"),
                            "method_version": method.get("method_version"),
                            "source_revision_ids": execution.get("source_revision_ids", []),
                            "checkpoint_receipt": method_result.get("checkpoint_receipt"),
                        },
                    }
            elif kind == "collective-method":
                output = self._execute_collective_method(request, operation_id)
            else:
                if kind in {"self-study", "candidate-development"}:
                    from cassi_research_development import execute_work
                else:
                    from cassi_research_worlds import execute_work
                output = execute_work(
                    request,
                    workspace=workspace,
                    artifact_home=self._adapter_artifact_home(workspace, operation_id),
                    semantic=self.semantic,
                )
            if not isinstance(output, dict) or output.get("status") not in {
                    "observed", "supported", "support-gap", "rejected"}:
                raise ResidencyError("research adapter returned an invalid result")
            output_bytes = canonical_json_bytes(output)
            if len(output_bytes) > MAX_RESULT_BYTES:
                raise ResidencyError("research result exceeds its 1 MiB evidence bound")
            _commit_bytes(output_path, output_bytes)
        return output, str(output_path.relative_to(self.home)), hashlib.sha256(output_bytes).hexdigest()


    def _observations(self, operation_id: str, output: Mapping[str, Any]) -> list[dict[str, Any]]:
        def bounded(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
            normalized = [dict(row) for row in rows]
            if len(normalized) <= MAX_FIELD_OBSERVATIONS:
                return normalized
            last = len(normalized) - 1
            indices = [
                (index * last) // (MAX_FIELD_OBSERVATIONS - 1)
                for index in range(MAX_FIELD_OBSERVATIONS)
            ]
            return [normalized[index] for index in indices]

        raw = output.get("observations")
        if isinstance(raw, list) and raw and all(
            isinstance(row, Mapping)
            and isinstance(row.get("subject"), str)
            and "value" in row
            for row in raw
        ):
            return bounded(raw)
        evidence = output.get("evidence")
        continuation = evidence.get("continuation") if isinstance(evidence, Mapping) else None
        rows = continuation.get("observations") if isinstance(continuation, Mapping) else None
        if isinstance(rows, list):
            consequences = []
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    continue
                step = row.get("step", row.get("bar_index", index))
                consequences.append({
                    "subject": f"{operation_id}:step:{step}",
                    "attribute": "world-consequence",
                    "value": dict(row),
                    "frame": {"step": step, "operation_id": operation_id},
                })
            if consequences:
                return bounded(consequences)
        return [{
            "subject": operation_id,
            "attribute": "result",
            "value": {"status": output["status"], "summary": output["summary"]},
        }]


    def _candidate_procedure_opportunity(
        self, operation_id: str, output: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Turn repeated successful candidate runs into admissible procedure evidence."""
        task = self._task()
        current_events = task.get("current", {}).get("Event", {})
        records = task.get("records", {})
        if not isinstance(current_events, Mapping) or not isinstance(records, Mapping):
            return None
        current_event_id = f"{operation_id}:event"
        if current_event_id not in current_events:
            return None
        candidate_ids = {
            str(item["id"])
            for item in self._catalog()
            if isinstance(item.get("request"), Mapping)
            and item["request"].get("kind") == "candidate-development"
        }

        def supported_event(event_id: str) -> bool:
            operation = event_id[: -len(":event")]
            history = records.get(f"research:outcome:{operation}")
            if not isinstance(history, list) or not history:
                return False
            payload = history[-1].get("payload", {})
            return isinstance(payload, Mapping) and payload.get("status") == "supported"

        event_ids = sorted(
            event_id
            for event_id in current_events
            if isinstance(event_id, str)
            and event_id.endswith(":event")
            and any(
                event_id.endswith(f":{candidate_id}:event")
                for candidate_id in candidate_ids
            )
            and supported_event(event_id)
        )
        procedure_id = (
            "resident-procedure:candidate-development:"
            "cassimindfield-lab-example-v1"
        )
        procedures = task.get("libraries", {}).get("procedures", {})
        programs = task.get("current", {}).get("Program", {})
        if procedure_id in procedures or procedure_id in programs:
            return None
        if len(event_ids) < 3:
            return None
        selected_ids = event_ids[:3]
        support_refs = [
            current_events[event_id]
            for event_id in selected_ids
            if isinstance(current_events[event_id], Mapping)
            and {"id", "kind", "content_version"} <= set(current_events[event_id])
        ]
        if len(support_refs) != len(selected_ids):
            return None

        def trace(event_id: str, index: int) -> dict[str, Any]:
            return {
                "context": {"source_regime": "cassimindfield-lab-example-v1"},
                "effects": {"result_status": "supported"},
                "failure": None,
                "outcome": {"result_status": "supported"},
                "rare_case": False,
                "steps": [
                    {
                        "action": {"kind": "candidate-development", "phase": "compile"},
                        "transition": {
                            "pre_state_shape": "source",
                            "post_state_shape": "candidate",
                        },
                    },
                    {
                        "action": {"kind": "candidate-development", "phase": "measure"},
                        "transition": {
                            "pre_state_shape": "candidate",
                            "post_state_shape": "assessment",
                        },
                    },
                ],
                "success": True,
                "support_event_refs": [event_id],
                "trace_id": f"candidate-development:{index}:{event_id}",
                "trajectory_source": "declared",
                "work": 2,
            }

        training = [
            trace(event_id, index)
            for index, event_id in enumerate(selected_ids[:2])
        ]
        holdout = [trace(selected_ids[2], 2)]
        return {
            "candidate_id": procedure_id,
            "learning_kind": "procedure",
            "expected_gain": 2.0,
            "urgency": 0.75,
            "novelty": 1.5,
            "priority": 1.0,
            "cost": 2.0,
            "risk": 0.0,
            "request": {
                "procedure_id": procedure_id,
                "max_length": 2,
                "min_length": 2,
                "support_event_refs": support_refs,
                "support_roots": [],
                "traces": training,
                "holdout": holdout,
            },
        }

    def _output(self, cursor: Mapping[str, Any]) -> tuple[dict[str, Any], bytes]:
        path = (self.home / cursor["output_path"]).resolve()
        if not path.is_relative_to(self.home / "artifacts"):
            raise ResidencyError("research result escapes its artifact home")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != cursor["output_sha256"]:
            raise ResidencyError("acknowledged research result changed")
        return json.loads(content), content
    def _research_context(self, item_id: str) -> dict[str, Any]:
        item = next(item for item in self._catalog() if item["id"] == item_id)
        context: dict[str, Any] = {
            "question_id": item_id,
            "compiler_family": item["request"]["kind"],
        }
        related_keys = {
            "domain", "mission_id", "program_id", "project_id", "source_id",
            "source_regime", "source_revision", "topic",
        }
        for source in (item["request"],):
            if not isinstance(source, Mapping):
                continue
            for key in related_keys:
                value = source.get(key)
                if (isinstance(value, (str, int, bool))
                        or isinstance(value, float) and math.isfinite(value)):
                    context[key] = value
            nested = source.get("source")
            if isinstance(nested, Mapping):
                for key in ("source_id", "source_regime", "source_revision"):
                    value = nested.get(key)
                    if isinstance(value, str) and value:
                        context[key] = value
        return context

    def _match_research_memory(
        self,
        cursor: Mapping[str, Any],
        item_id: str,
        *,
        event_suffix: str = "candidate-memory-v3",
        operation_suffix: str = "candidate-memory-v3",
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ask the continuing field which stored results apply to this work."""
        operation_id = self._work_id(cursor, item_id)
        event_id = operation_id + ":" + event_suffix
        match_context = (
            self._research_context(item_id)
            if context is None else dict(context)
        )
        offset: int | None = None
        combined: dict[str, Any] | None = None
        while True:
            page_id = operation_id + ":" + operation_suffix
            if offset is not None:
                page_id += f":{offset}"
            request: dict[str, Any] = {
                "operation": "match-relevance",
                "operation_id": page_id,
                "event_id": event_id,
                "context": match_context,
                "maximum": 512,
            }
            if offset is not None:
                request["cursor"] = offset
            page = self.semantic(request)
            if combined is None:
                combined = dict(page)
                for key in ("wakeups", "unknown", "suppressed"):
                    combined[key] = list(page.get(key, []))
            else:
                for key in ("wakeups", "unknown", "suppressed"):
                    combined[key].extend(page.get(key, []))
                combined["searched"] += page.get("searched", 0)
                combined["next_cursor"] = page.get("next_cursor")
                combined["limitation"] = page.get("limitation")
                if page.get("status") == "supported":
                    combined["status"] = "supported"
            next_offset = page.get("next_cursor")
            if next_offset is None:
                return combined
            if (isinstance(next_offset, bool) or not isinstance(next_offset, int)
                    or next_offset <= (offset or 0)):
                raise ResidencyError("field relevance pagination did not advance")
            offset = next_offset

    def _relevant_assessments(
        self, matched: Mapping[str, Any], event_id: str, *, limit: int
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        records = self._task()["records"]
        for wakeup_ref in matched.get("wakeups", []):
            if not isinstance(wakeup_ref, Mapping):
                continue
            wakeup = self._record(str(wakeup_ref.get("id")))
            if (wakeup is None or wakeup["status"] != "active"
                    or any(wakeup.get(key) != wakeup_ref.get(key)
                           for key in ("id", "kind", "content_version"))
                    or wakeup["payload"].get("memory_role") != "relevance-wakeup"
                    or wakeup["payload"].get("event_id") != event_id):
                continue
            condition_ref = wakeup["payload"].get("condition_ref")
            if (not isinstance(condition_ref, Mapping)
                    or condition_ref.get("kind") != "Program"
                    or not isinstance(condition_ref.get("id"), str)
                    or isinstance(condition_ref.get("content_version"), bool)
                    or not isinstance(condition_ref.get("content_version"), int)):
                continue
            condition = next(
                (
                    row for row in records.get(condition_ref["id"], [])
                    if isinstance(row, Mapping)
                    and all(row.get(key) == condition_ref.get(key)
                            for key in ("id", "kind", "content_version"))
                ),
                None,
            )
            current_condition = self._record(condition_ref["id"])
            if (condition is None or condition.get("status") != "active"
                    or current_condition is None
                    or current_condition["status"] != "active"
                    or condition["payload"].get("memory_role") != "relevance-condition"):
                continue
            priority = condition["payload"].get("priority", 0.5)
            if isinstance(priority, bool) or not isinstance(priority, (int, float)):
                continue
            for raw_ref in reversed(wakeup["payload"].get("target_refs", [])):
                if len(rows) >= limit:
                    return rows
                if not isinstance(raw_ref, Mapping) or raw_ref.get("kind") != "Assessment":
                    continue
                record_id = raw_ref.get("id")
                if not isinstance(record_id, str) or record_id in seen:
                    continue
                record = self._record(record_id)
                if (record is None or record["status"] != "active"
                        or any(record.get(key) != raw_ref.get(key)
                               for key in ("id", "kind", "content_version"))):
                    continue
                payload = record["payload"]
                revision_id = payload.get("source_revision_id")
                expected = payload.get("output_sha256")
                if (not isinstance(revision_id, str) or not isinstance(expected, str)
                        or revision_id not in record["support_roots"]
                        or not isinstance(payload.get("question_id"), str)
                        or not isinstance(payload.get("summary"), str)):
                    continue
                try:
                    source = self.owner.exact_recall(
                        revision_id=revision_id,
                        allowed_labels=frozenset({"research-residency"}),
                    )
                except FieldIntelligenceError:
                    continue
                if source["content_sha256"] != expected:
                    raise ResidencyError("relevant research source differs from its assessment")
                previous = json.loads(base64.b64decode(source["bytes_base64"]))
                if (not isinstance(previous, Mapping)
                        or previous.get("status") != payload.get("result_status")
                        or previous.get("summary") != payload["summary"]):
                    raise ResidencyError("relevant research assessment disagrees with its source")
                seen.add(record_id)
                rows.append({
                    "record_ref": {
                        key: record[key] for key in ("id", "kind", "content_version")
                    },
                    "question_id": payload["question_id"],
                    "source_revision_id": revision_id,
                    "result_status": previous["status"],
                    "priority": float(priority),
                    "wakeup_ref": {
                        key: wakeup[key] for key in ("id", "kind", "content_version")
                    },
                })
        return rows

    def _recalled_related_results(
        self,
        cursor: Mapping[str, Any],
        operation_id: str,
        output: Mapping[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        matched = self._match_research_memory(cursor, cursor["selected"]["id"])
        relevant = self._relevant_assessments(
            matched, operation_id + ":candidate-memory-v3", limit=4
        )
        if not relevant:
            return None
        selected_refs = [row["record_ref"] for row in relevant]
        comparisons = [
            {
                "question_id": row["question_id"],
                "previous_source_revision_id": row["source_revision_id"],
                "previous_status": row["result_status"],
                "current_status": output["status"],
                "status_changed": row["result_status"] != output["status"],
            }
            for row in relevant
        ]
        requested = self.semantic({
            "operation": "recall-request",
            "operation_id": operation_id + ":related-recall-v5-request",
            "episode_id": operation_id + ":related-results-v5",
            "question": {
                "work_operation_id": operation_id,
                "question_id": cursor["selected"]["id"],
            },

            "context": {},
            "intended_use": {"kind": "assess-result-against-field-relevant-research"},
            "fidelity": {"kind": "exact-archived-results"},
            "allowance": {"max_records": len(selected_refs)},
            "selected_refs": selected_refs,
            "search": {"kind": "resident-field-relevance"},
            "cue_refs": [],
        })
        used = self.semantic({
            "operation": "recall-use",
            "operation_id": operation_id + ":related-recall-v5-use",
            "episode_ref": requested["episode"],
            "use_id": operation_id + ":related-assessment-v5",
            "selected_refs": selected_refs,
            "consumer": {
                "kind": "resident-research-assessment",
                "work_operation_id": operation_id,
                "comparisons": comparisons,
            },
        })
        settled = self.semantic({
            "operation": "recall-outcome",
            "operation_id": operation_id + ":related-recall-v5-outcome",
            "episode_ref": used["episode"],
            "outcome_id": operation_id + ":related-comparison-v5",
            "consequence": {"kind": "current-work-observed", "comparisons": comparisons},
            "usefulness": 0.0,
        })
        return settled["episode"], comparisons



    def _remember_research_result(
        self, operation_id: str, outcome_ref: Mapping[str, Any], question_id: str
    ) -> None:
        """Connect source-backed outcomes to existing relevance programs."""
        context = self._research_context(question_id)
        fields = (
            "compiler_family", "domain", "mission_id", "program_id",
            "project_id", "source_id", "source_regime", "topic",
        )
        for field in fields:
            if field not in context:
                continue
            value = context[field]
            identity = (
                value if field == "compiler_family" else f"{field}\0{value}"
            )
            condition_id = "resident-research:" + hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:24]
            history = self._task()["records"].get(
                "memory:relevance:" + condition_id, []
            )
            previous_targets = next(
                (
                    record["payload"].get("target_refs", [])
                    for record in reversed(history)
                    if isinstance(record.get("payload"), Mapping)
                    and isinstance(record["payload"].get("target_refs"), list)
                ),
                [],
            )
            targets: list[dict[str, Any]] = []
            for ref in previous_targets:
                if not isinstance(ref, Mapping):
                    continue
                record = self._record(str(ref.get("id")))
                if (record is not None and record["status"] == "active"
                        and all(record.get(key) == ref.get(key)
                                for key in ("id", "kind", "content_version"))
                        and record["id"] != outcome_ref.get("id")):
                    targets.append({
                        key: record[key]
                        for key in ("id", "kind", "content_version")
                    })
            targets = [*targets[-7:], dict(outcome_ref)]
            self.semantic({
                "operation": "register-relevance",
                "operation_id": (
                    operation_id + ":remember-relevance-v2:"
                    + hashlib.sha256(field.encode("utf-8")).hexdigest()[:12]
                ),
                "condition_id": condition_id,
                "condition": {"clauses": [{
                    "field": field, "operator": "equals", "value": value,
                }]},
                "target_refs": targets,
                "reason": {"kind": "resident-research-result", "question_id": question_id},
                "priority": 0.65 if field == "compiler_family" else 0.8,
            })



    def _revise_communication_topology(
        self,
        operation_id: str,
        *,
        outcome_ref: Mapping[str, Any],
        question_id: str,
        compiler_family: str,
        result_status: str,
    ) -> None:
        """Learn bounded route usefulness only from a committed research outcome."""
        request = next(
            (
                item["request"]
                for item in self._catalog()
                if item["id"] == question_id
            ),
            None,
        )
        route = _declared_communication_route(request, operation_id)
        if route is None:
            return
        self._learn_communication_topology(
            operation_id,
            outcome_ref=outcome_ref,
            route=route,
            question_id=question_id,
            compiler_family=compiler_family,
            result_status=result_status,
        )

    def _learn_communication_topology(
        self,
        operation_id: str,
        *,
        outcome_ref: Mapping[str, Any],
        route: str,
        question_id: str,
        compiler_family: str,
        result_status: str,
    ) -> None:
        """Learn bounded route usefulness only from a committed outcome, by exact route."""
        if result_status in {"observed", "supported"}:
            outcome = "successful"
        elif result_status in {"failed", "rejected", "support-gap"}:
            outcome = "unsuccessful"
        else:
            return
        outcome_key = {
            "id": outcome_ref.get("id"),
            "kind": outcome_ref.get("kind"),
            "content_version": outcome_ref.get("content_version"),
        }
        topology_operation_id = "research:communication-topology-outcome:" + sha256_value({
            "outcome_ref": outcome_key,
            "route": route,
        })
        prior_operation = self._task()["indexes"]["operations"].get(
            topology_operation_id
        )
        if prior_operation is not None:
            prior_result = prior_operation.get("result")
            if not isinstance(prior_result, Mapping):
                raise ResidencyError(
                    "communication topology operation identity collision"
                )
            if prior_result.get("operation") == "register":
                prior_ref = prior_result.get("record")
                if (
                    not isinstance(prior_ref, Mapping)
                    or prior_ref.get("id") != "communication:topology"
                    or prior_ref.get("kind") != "Value"
                ):
                    raise ResidencyError(
                        "communication topology operation identity collision"
                    )
                state = self._communication_topology()
                entries = (
                    state.get("outcomes", [])
                    if isinstance(state, Mapping)
                    else []
                )
                prior_entry = next(
                    (
                        row for row in entries
                        if isinstance(row, Mapping)
                        and row.get("topology_operation_id") == topology_operation_id
                    ),
                    None,
                )
                if prior_entry is not None and (
                    prior_entry.get("outcome_ref") != outcome_key
                    or prior_entry.get("route") != route
                ):
                    raise ResidencyError(
                        "communication topology operation identity collision"
                    )
            elif (
                prior_result.get("operation") != "learn-communication-topology"
                or prior_result.get("topology_operation_id") != topology_operation_id
                or prior_result.get("outcome_ref") != outcome_key
                or prior_result.get("route") != route
            ):
                raise ResidencyError(
                    "communication topology operation identity collision"
                )
            return
        locality_payload = self._communication_locality()
        if (
            not isinstance(locality_payload, Mapping)
            or not isinstance(locality_payload.get("observations"), list)
        ):
            return
        uses: list[str] = []
        dependencies: list[dict[str, Any]] = [dict(outcome_ref)]
        for observation in locality_payload["observations"][-64:]:
            if not isinstance(observation, Mapping) or observation.get("route") != route:
                continue
            use_sha256 = observation.get("use_sha256")
            if not isinstance(use_sha256, str):
                continue
            ack = self._record("communication:use:" + use_sha256[:40])
            ack_payload = ack.get("payload") if isinstance(ack, Mapping) else None
            if (
                not isinstance(ack_payload, Mapping)
                or ack_payload.get("status") != "used"
                or ack_payload.get("use_sha256") != use_sha256
            ):
                continue
            uses.append(use_sha256)
            if isinstance(ack, Mapping):
                dependencies.append({
                    key: ack[key] for key in ("id", "kind", "content_version")
                })
        if not uses:
            return
        unique_dependencies = {
            (ref["id"], ref["kind"], ref["content_version"]): ref
            for ref in dependencies
        }
        selected_dependencies = list(unique_dependencies.values())
        bounded_dependencies = (
            selected_dependencies[:1] + selected_dependencies[1:][-31:]
        )
        self.semantic({
            "operation": "learn-communication-topology",
            "operation_id": topology_operation_id,
            "route": route,
            "outcome": outcome,
            "outcome_ref": outcome_key,
            "result_status": result_status,
            "work_operation_id": operation_id,
            "use_sha256s": uses[-64:],
            "question_id": question_id,
            "compiler_family": compiler_family,
            "dependencies": bounded_dependencies,
        })

    def advance(self) -> dict[str, Any]:
        """Advance one durable phase, preserving every boundary on interruption."""
        self._settle()
        cursor = self._cursor()
        identity = f"research:phase:{int(cursor['sequence']):012d}"
        phase = cursor["phase"]
        if phase == "seed":
            for item in self._catalog():
                record_id = self._work_id(cursor, item["id"])
                self._register(record_id + ":open", record_id, "Obligation",
                    {"purpose": "research", "status": "pending", "question_id": item["id"],
                     "compiler_family": item["request"]["kind"], "summary": item["summary"],
                     "request": item["request"]}, status="pending", epistemic_kind="asserted")
            self._checkpoint(cursor, phase="choose",
                             remaining=[item["id"] for item in self._catalog()])
        elif phase == "choose":
            selected_id = self._choose(cursor, identity)
            self._checkpoint(cursor, phase="execute", selected={"id": selected_id})
        elif phase == "execute":
            _, path, digest = self._execute(cursor)
            self._checkpoint(cursor, phase="admit", output_path=path, output_sha256=digest)
        elif phase == "admit":
            output, content = self._output(cursor)
            selected_id = cursor["selected"]["id"]
            operation_id = self._work_id(cursor, selected_id)
            obligation = self._required_record(operation_id)
            if (obligation["kind"] != "Obligation"
                    or obligation["payload"].get("question_id") != selected_id):
                raise ResidencyError("selected research obligation is unavailable")
            self._selection_event_for_work(
                cursor, selected_id, operation_id, obligation
            )
            source = SourceInput(
                source_id=operation_id, content=content, media_type="application/json",
                codec=CODEC_JSON, observed_timestamp=operation_id,
                scope="research-residency", claim_category="research-operation-result",
                fidelity="exact-observed-bytes", labels=("research-residency",),
            )
            archive = self.owner.archive_source(
                operation_id=operation_id + ":archive", source=source,
                context={"work_operation_id": operation_id},
            )
            root = archive["source"]["revision_id"]
            observations = self._observations(operation_id, output)
            observed = self.semantic({
                "operation": "observe",
                "operation_id": operation_id + ":observe",
                "delivery_id": operation_id + ":delivery",
                "event_id": operation_id + ":event",
                "observations": observations,
                "source": {"source_revision_id": root},
                "support_roots": [root],
            })
            observation_event = observed.get("event")
            if not isinstance(observation_event, Mapping) or observation_event.get("kind") != "Event":
                raise ResidencyError("research observation did not return its event")
            observation_record = self._record(str(observation_event.get("id")))
            if (observation_record is None or observation_record["status"] != "active"
                    or any(observation_record.get(key) != observation_event.get(key)
                           for key in ("id", "kind", "content_version"))):
                raise ResidencyError("research observation event is stale")
            item = next(item for item in self._catalog() if item["id"] == selected_id)
            recalled = self._recalled_related_results(cursor, operation_id, output)
            assessment_dependencies: list[Mapping[str, Any]] = [dict(observation_event)]
            if recalled is not None:
                assessment_dependencies.append(recalled[0])
            self._register(
                operation_id + ":assess", "research:outcome:" + operation_id,
                "Assessment",
                {
                    "work_operation_id": operation_id,
                    "question_id": item["id"],
                    "compiler_family": item["request"]["kind"],
                    "status": (
                        "supported"
                        if output["status"] in {"observed", "supported"}
                        else "failed"
                    ),
                    "result_status": output["status"],
                    "summary": output["summary"],
                    "source_revision_id": root,
                    "output_sha256": cursor["output_sha256"],
                },
                roots=[
                    root,
                    *(
                        [row["previous_source_revision_id"] for row in recalled[1]]
                        if recalled else []
                    ),
                ],
                dependencies=assessment_dependencies,
                epistemic_kind="assessed",
            )
            self._checkpoint(cursor, phase="learn")
        elif phase == "learn":
            output, _ = self._output(cursor)
            operation_id = self._work_id(cursor, cursor["selected"]["id"])
            request: dict[str, Any] = {
                "operation": "autonomous-learn",
                "operation_id": identity + ":learn",
                "goal": {
                    "objective": self._required_record(MISSION_ID)["payload"]["mission"]
                },
            }
            valid_opportunities: list[dict[str, Any]] = []
            raw_opportunities = output.get("learning_opportunities")
            if isinstance(raw_opportunities, list):
                valid_opportunities.extend(
                    dict(row)
                    for row in raw_opportunities
                    if isinstance(row, Mapping)
                    and row.get("learning_kind") == "predictive-state"
                    and isinstance(row.get("request"), Mapping)
                    and {"examples", "representation_id", "signature"}
                    <= set(row["request"])
                )
            procedure = self._candidate_procedure_opportunity(operation_id, output)
            if procedure is not None:
                valid_opportunities.append(procedure)
            if valid_opportunities:
                request["opportunities"] = valid_opportunities
            learning_result = self.semantic(request)
            learning_event_ref = learning_result.get("event")
            if isinstance(learning_event_ref, Mapping):
                learning_event = self._record(str(learning_event_ref.get("id")))
                if (
                    learning_event is None
                    or learning_event.get("status") != "active"
                    or any(
                        learning_event.get(key) != learning_event_ref.get(key)
                        for key in ("id", "kind", "content_version")
                    )
                ):
                    raise ResidencyError("research learning event is invalid")
                selected_learning = learning_result.get("selected")
                learning = learning_result.get("learning")
                method_ref = (
                    learning.get("procedure")
                    if isinstance(learning, Mapping)
                    else None
                )
                if (
                    learning_result.get("status") == "supported"
                    and isinstance(selected_learning, Mapping)
                    and selected_learning.get("learning_kind") == "procedure"
                    and isinstance(method_ref, Mapping)
                ):
                    exact_method_ref, method_record = self._working_field_exact_ref(
                        method_ref, require_current=True
                    )
                    if (
                        exact_method_ref["kind"] == "Program"
                        and method_record.get("status") == "active"
                        and method_record.get("payload", {}).get("program_role")
                        == "procedure"
                    ):
                        context = self._research_context(cursor["selected"]["id"])
                        context.update({
                            "event_kind": "method-acquired",
                            "method_changed": True,
                            "method_id": exact_method_ref["id"],
                            "method_content_version": exact_method_ref[
                                "content_version"
                            ],
                            "method_role": "procedure",
                        })
                        method_event_id = (
                            "research:method-acquired-event:"
                            + hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:24]
                        )
                        method_event = self._register(
                            operation_id + ":method-acquired-event",
                            method_event_id,
                            "Event",
                            {
                                "event_kind": "method-acquired",
                                "context": context,
                                "learning_event_ref": dict(learning_event_ref),
                                "method_ref": exact_method_ref,
                            },
                            dependencies=[learning_event_ref, exact_method_ref],
                        )
                        method_event_ref = method_event.get("record")
                        if not isinstance(method_event_ref, Mapping):
                            raise ResidencyError(
                                "research method-acquired event was not registered"
                            )
                        self._wake_resting_working_fields(
                            operation_id + ":acquired-method-wake",
                            method_event_ref,
                            context,
                        )
            elif learning_event_ref is not None:
                raise ResidencyError("research learning event is invalid")
            self._checkpoint(cursor, phase="finish")
        elif phase == "finish":
            output, _ = self._output(cursor)
            selected = cursor["selected"]["id"]
            operation_id = self._work_id(cursor, selected)
            outcome_record = self._required_record(
                "research:outcome:" + operation_id
            )
            previous_sequence = int(cursor["sequence"]) - 1
            learning_id = f"research:phase:{previous_sequence:012d}:learn"
            learning_operation = self._task()["indexes"]["operations"].get(learning_id)
            if not isinstance(learning_operation, Mapping):
                raise ResidencyError("completed research learning record is unavailable")
            learning_result = learning_operation.get("result")
            if not isinstance(learning_result, Mapping):
                raise ResidencyError("completed research learning result is invalid")
            learning_event_ref = learning_result.get("event")
            if isinstance(learning_event_ref, Mapping):
                if learning_event_ref.get("kind") != "Event":
                    raise ResidencyError("completed research learning event is invalid")
                learning_event = self._record(str(learning_event_ref.get("id")))
                if (learning_event is None or learning_event["status"] != "active"
                        or any(learning_event.get(key) != learning_event_ref.get(key)
                               for key in ("id", "kind", "content_version"))):
                    raise ResidencyError("completed research learning event is stale")
                dependencies = [
                    dict(ref) for ref in outcome_record.get("dependencies", [])
                    if isinstance(ref, Mapping)
                ]
                if not any(
                    all(ref.get(key) == learning_event_ref.get(key)
                        for key in ("id", "kind", "content_version"))
                    for ref in dependencies
                ):
                    dependencies.append(dict(learning_event_ref))
                    self._register(
                        operation_id + ":link-learning",
                        outcome_record["id"],
                        "Assessment",
                        outcome_record["payload"],
                        status=outcome_record["status"],
                        roots=outcome_record["support_roots"],
                        dependencies=dependencies,
                        epistemic_kind=outcome_record.get("epistemic_kind", "assessed"),
                    )
                    outcome_record = self._required_record(
                        "research:outcome:" + operation_id
                    )
            elif learning_event_ref is not None:
                raise ResidencyError("completed research learning event is invalid")
            if any(
                isinstance(ref, Mapping)
                and ref.get("kind") == "Obligation"
                and ref.get("id") == operation_id
                for ref in outcome_record.get("dependencies", [])
            ):
                recalled = self._recalled_related_results(
                    cursor, operation_id, output
                )
                observation_ref = next(
                    (
                        ref for ref in outcome_record.get("dependencies", [])
                        if isinstance(ref, Mapping)
                        and ref.get("kind") == "Event"
                        and ref.get("id") == operation_id + ":event"
                    ),
                    None,
                )
                if not isinstance(observation_ref, Mapping):
                    raise ResidencyError(
                        "completed research observation event is unavailable"
                    )
                assessment_dependencies: list[Mapping[str, Any]] = [
                    dict(observation_ref)
                ]
                if recalled is not None:
                    assessment_dependencies.append(recalled[0])
                if isinstance(learning_event_ref, Mapping):
                    assessment_dependencies.append(dict(learning_event_ref))
                self._register(
                    operation_id + ":assessment-lineage-v1",
                    outcome_record["id"],
                    "Assessment",
                    outcome_record["payload"],
                    status=outcome_record["status"],
                    roots=outcome_record["support_roots"],
                    dependencies=assessment_dependencies,
                    epistemic_kind=outcome_record.get("epistemic_kind", "assessed"),
                )
                outcome_record = self._required_record(
                    "research:outcome:" + operation_id
                )
            outcome_ref = {
                "id": outcome_record["id"],
                "kind": outcome_record["kind"],
                "content_version": outcome_record["content_version"],
            }
            event_context = self._research_context(selected)
            event_context["result_status"] = output["status"]
            self._match_research_memory(
                cursor,
                selected,
                event_suffix="event",
                operation_suffix="completed-memory-v3",
                context=event_context,
            )
            self.semantic({
                "operation": "maintain-memory",
                "operation_id": operation_id + ":memory-maintenance-v3",
                "purpose": {
                    "kind": "completed-research-review",
                    "question_id": selected,
                },
                "target_refs": [outcome_ref],
                "allowance": {"max_records": 32, "max_work": 64},
            })
            self._remember_research_result(operation_id, outcome_ref, selected)
            event_context = self._research_context(selected)
            event_context["event_kind"] = "research-result"
            event_context["result_status"] = output["status"]
            observation_ref = next(
                (
                    ref for ref in outcome_record.get("dependencies", [])
                    if isinstance(ref, Mapping)
                    and ref.get("kind") == "Event"
                    and ref.get("id") == operation_id + ":event"
                ),
                None,
            )
            if not isinstance(observation_ref, Mapping):
                raise ResidencyError("research outcome omits its observation Event")
            observation_ref, observation_record = self._working_field_exact_ref(
                observation_ref, require_current=True
            )
            if observation_record.get("status") != "active":
                raise ResidencyError("research observation Event is not active")
            self._wake_resting_working_fields(
                operation_id + ":observation-wake",
                observation_ref,
                event_context,
            )
            item = next(item for item in self._catalog() if item["id"] == selected)
            self._revise_communication_topology(
                operation_id,
                outcome_ref=outcome_ref,
                question_id=selected,
                compiler_family=item["request"]["kind"],
                result_status=output["status"],
            )
            self._register(
                operation_id + ":resolve",
                operation_id,
                "Obligation",
                {
                    "purpose": "research",
                    "status": "resolved",
                    "question_id": selected,
                    "compiler_family": item["request"]["kind"],
                    "summary": item["summary"],
                    "request": item["request"],
                },
                status="resolved",
                roots=outcome_record["support_roots"],
                dependencies=[outcome_ref],
            )
            work = _plain(self._catalog())
            continuation = output.get("continuation_request")
            if continuation is not None:
                for item in work:
                    if item["id"] == selected:
                        item["request"] = continuation
            for followup in output.get("follow_up_requests", []):
                if not any(item["id"] == followup["id"] for item in work):
                    work.append(followup)
            work = _work_items(work)
            self._register(operation_id + ":catalog", CATALOG_ID, "Value", {"work": work})
            remaining = [item_id for item_id in cursor["remaining"] if item_id != selected]
            next_cursor = {"sequence": cursor["sequence"], "round": cursor["round"] + int(not remaining),
                           "completed": cursor["completed"] + 1, "phase": "choose" if remaining else "seed",
                           "remaining": remaining, "selected": None}
            self._checkpoint(next_cursor)
        else:
            raise ResidencyError(f"unknown resident phase: {phase}")
        return self.inspect()


def attach_research_residency(
    owner: FieldIntelligenceOwner,
    data_home: Path,
    *,
    hive_home: Path | None = None,
    role: str = "research-root",
) -> ResearchResidency:
    """Attach a residency to an already-live owner without taking ownership."""
    home = Path(data_home).resolve()
    policy = SkillPolicy.for_mode(
        "isolated",
        import_enabled=False,
        export_enabled=False,
        apply_mode="never",
        sync_mode="manual",
        export_mode="on-close",
    )
    session = attach_field_session(
        owner,
        data_home=home / "field",
        hive_home=hive_home or home / "hive",
        mode="isolated",
        role=role,
        policy=policy,
    )
    return ResearchResidency(home, session)


def open_research_residency(
    data_home: Path,
    *,
    hive_home: Path | None = None,
    import_skills: bool = False,
    export_skills: bool = False,
    limits: CapacityLimits | None = None,
) -> ResearchResidency:
    home = Path(data_home).resolve()
    policy = SkillPolicy.for_mode(
        "isolated",
        import_enabled=import_skills,
        export_enabled=export_skills,
        apply_mode="verified" if import_skills else "never",
        sync_mode="manual",
        export_mode="on-close",
    )
    owner = (
        None
        if limits is None
        else FieldIntelligenceOwner(home / "field", limits=limits)
    )
    try:
        session = open_field_session(
            home / "field",
            hive_home=hive_home or home / "hive",
            mode="isolated",
            role="research-resident",
            policy=policy,
            owner=owner,
            owns_owner=owner is not None,
        )
    except BaseException:
        if owner is not None:
            owner.close()
        raise
    return ResearchResidency(home, session)
