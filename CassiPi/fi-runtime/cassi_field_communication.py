"""Typed version-bound intents and locality hints for the regional event path.

Durable intent, work execution, acknowledgments and learned state remain in the
field owner; this module is a validator and pure value transformer only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence

from cassi_field_atlas import canonical_json_bytes, sha256_value
INTENT_SCHEMA = "cassifi.field-communication-intent.v1"
ACK_SCHEMA = "cassifi.field-communication-use.v1"
CONSUMPTION_SCHEMA = "cassifi.field-communication-consumption.v1"
RESULT_SCHEMA = "cassifi.field-communication-result.v1"
RECORD_RESULT_SCHEMA = "cassifi.field-communication-record-result.v1"
CANCELLATION_SCHEMA = "cassifi.field-communication-cancellation.v1"
WORK_CREDIT_SCHEMA = "cassifi.field-communication-work-credit.v1"
LOCALITY_SCHEMA = "cassifi.field-communication-locality.v1"
MAX_DEPENDENCIES = 32
MAX_CHANGED_PAGES = 4096
MAX_LOCALITY_ROUTES = 256
MAX_LOCALITY_OBSERVATIONS = 64
MAX_ROUTE_ANTICIPATION = 8

class FieldCommunicationError(ValueError):
    """A communication intent is malformed or not bound to its exact field."""


def _text(value: Any, label: str, *, maximum: int = 128) -> str:
    if (not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum
            or any(ord(char) < 32 for char in value)):
        raise FieldCommunicationError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: Any, label: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise FieldCommunicationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0, maximum: int = 2**31 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise FieldCommunicationError(f"{label} is outside its declared integer bounds")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise FieldCommunicationError(f"{label} must be a typed object")
    result = dict(value)
    try:
        canonical_json_bytes(result)
    except (TypeError, ValueError) as exc:
        raise FieldCommunicationError(f"{label} must be canonical JSON") from exc
    return result


@dataclass(frozen=True, slots=True)
class FieldIntent:
    """One immutable Send, Need, or Subscribe bound to exact object versions."""

    kind: Literal["send", "need", "subscribe"]
    sender: str
    receiver: str
    payload_ref: Mapping[str, Any]
    dependency_versions: tuple[Mapping[str, Any], ...]
    urgency: Literal["foreground", "background"]
    consumer_use_id: str
    method_ref: Mapping[str, Any] | None = None
    input_refs: tuple[Mapping[str, Any], ...] = ()
    computer_id: str | None = None
    input_bindings: Mapping[str, int] | None = None
    consumer_work_ref: Mapping[str, Any] | None = None
    action: Mapping[str, Any] | None = None
    context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"send", "need", "subscribe"}:
            raise FieldCommunicationError("kind must be send, need, or subscribe")
        _text(self.sender, "sender")
        _text(self.receiver, "receiver")
        if self.sender == self.receiver:
            raise FieldCommunicationError("communication must cross a receiver boundary")
        if self.urgency not in {"foreground", "background"}:
            raise FieldCommunicationError("urgency must be foreground or background")
        payload = _mapping(self.payload_ref, "payload_ref")
        regional_keys = {"predecessor_root_sha256", "root_sha256", "source_sha256",
                          "changed_pages", "object_id", "object_version"}
        record_keys = {"id", "kind", "content_version"}
        is_record_payload = set(payload) == record_keys
        if is_record_payload:
            _text(payload.get("id"), "payload_ref.id")
            _text(payload.get("kind"), "payload_ref.kind")
            _integer(payload.get("content_version"), "payload_ref.content_version", minimum=1)
        elif set(payload) == regional_keys:
            for key in ("predecessor_root_sha256", "root_sha256", "source_sha256"):
                _digest(payload.get(key), f"payload_ref.{key}")
            _integer(payload.get("object_id"), "payload_ref.object_id", minimum=1)
            _integer(payload.get("object_version"), "payload_ref.object_version", minimum=1)
            pages = payload.get("changed_pages")
            if (not isinstance(pages, (list, tuple)) or len(pages) > MAX_CHANGED_PAGES
                    or any(isinstance(page, bool) or not isinstance(page, int) or page < 0 for page in pages)
                    or list(pages) != sorted(set(pages))):
                raise FieldCommunicationError("changed_pages must be bounded, sorted and unique")
            payload["changed_pages"] = tuple(pages)
        else:
            raise FieldCommunicationError(
                "payload_ref must bind one exact regional object version or resident record version"
            )
        dependency_by_id: dict[int, Mapping[str, Any]] = {}
        for ref in self.dependency_versions:
            dependency = _mapping(ref, "dependency version")
            if set(dependency) != {"object_id", "object_version", "source_sha256"}:
                raise FieldCommunicationError("dependency versions must bind object id, version, and source digest")
            object_id = _integer(dependency["object_id"], "dependency object_id", minimum=1)
            _integer(dependency["object_version"], "dependency object_version", minimum=1)
            _digest(dependency["source_sha256"], "dependency source_sha256")
            previous = dependency_by_id.get(object_id)
            if previous is not None and dict(previous) != dependency:
                raise FieldCommunicationError("dependency object has conflicting exact versions")
            dependency_by_id[object_id] = MappingProxyType(dependency)
        if not is_record_payload:
            source_ref = {"object_id": payload["object_id"],
                          "object_version": payload["object_version"],
                          "source_sha256": payload["source_sha256"]}
            previous_source = dependency_by_id.get(source_ref["object_id"])
            if previous_source is not None and dict(previous_source) != source_ref:
                raise FieldCommunicationError("source object conflicts with its declared dependency version")
            dependency_by_id[source_ref["object_id"]] = MappingProxyType(source_ref)
        if len(dependency_by_id) > MAX_DEPENDENCIES:
            raise FieldCommunicationError("dependency_versions exceeds its bound")
        dependencies = tuple(
            dependency_by_id[object_id] for object_id in sorted(dependency_by_id)
        )
        input_rows = []
        for ref in self.input_refs:
            binding = _mapping(ref, "input object binding")
            if set(binding) != {"object_id", "object_version", "source_sha256"}:
                raise FieldCommunicationError("input bindings must name exact object versions")
            _integer(binding["object_id"], "input object_id", minimum=1)
            _integer(binding["object_version"], "input object_version", minimum=1)
            _digest(binding["source_sha256"], "input source_sha256")
            input_rows.append(MappingProxyType(binding))
        input_rows.sort(key=lambda binding: binding["object_id"])
        if len(input_rows) > MAX_DEPENDENCIES or len({
            binding["object_id"] for binding in input_rows
        }) != len(input_rows):
            raise FieldCommunicationError("input bindings must be bounded and object-unique")
        if self.method_ref is None:
            if (input_rows or self.computer_id is not None or self.input_bindings is not None
                    or self.consumer_work_ref is not None or self.action is not None
                    or self.context is not None):
                raise FieldCommunicationError("method execution bindings require an exact resident method reference")
            method_ref = None
            input_bindings = None
            consumer_work_ref = None
            action = None
            context = None
        else:
            method = _mapping(self.method_ref, "resident method reference")
            if set(method) != {"method_id", "method_generation", "source_sha256"}:
                raise FieldCommunicationError("resident method reference must bind id, generation, and source")
            _text(method["method_id"], "method_id")
            _integer(method["method_generation"], "method_generation", minimum=1)
            _digest(method["source_sha256"], "method source_sha256")
            method_ref = MappingProxyType(method)
            if self.kind != "need":
                raise FieldCommunicationError("resident methods may only be referenced by Need intents")
            if not input_rows or not isinstance(self.computer_id, str):
                raise FieldCommunicationError("resident method Need requires exact computer and input bindings")
            _text(self.computer_id, "computer_id")
            if not isinstance(self.input_bindings, Mapping) or not self.input_bindings:
                raise FieldCommunicationError("resident method Need requires named input bindings")
            input_bindings = {}
            bound_ids = {binding["object_id"] for binding in input_rows}
            for name, object_id in self.input_bindings.items():
                _text(name, "method input name")
                input_bindings[name] = _integer(object_id, "method input object_id", minimum=1)
            if any(object_id not in bound_ids for object_id in input_bindings.values()):
                raise FieldCommunicationError("named method inputs must resolve to an exact input object binding")
            if not isinstance(self.action, Mapping) or not isinstance(self.context, Mapping):
                raise FieldCommunicationError("resident method action and context must be canonical objects")
            try:
                action = dict(self.action)
                context = dict(self.context)
                canonical_json_bytes(action)
                canonical_json_bytes(context)
            except (TypeError, ValueError) as exc:
                raise FieldCommunicationError("resident method action and context must be canonical JSON") from exc
            input_bindings = MappingProxyType(input_bindings)
            action = MappingProxyType(action)
            context = MappingProxyType(context)
            if self.consumer_work_ref is None:
                consumer_work_ref = None
            else:
                work_ref = _mapping(self.consumer_work_ref, "consumer work reference")
                if set(work_ref) != {"id", "kind", "content_version"}:
                    raise FieldCommunicationError("consumer work reference must bind an exact resident record version")
                _text(work_ref["id"], "consumer work id")
                if work_ref["kind"] not in {"Obligation", "Program"}:
                    raise FieldCommunicationError("consumer work reference must name an Obligation or WorkingField Program")
                _integer(work_ref["content_version"], "consumer work content_version", minimum=1)
                consumer_work_ref = MappingProxyType(work_ref)
            if any(binding not in dependencies for binding in input_rows):
                raise FieldCommunicationError("input bindings must also be declared dependencies")
        object.__setattr__(self, "input_refs", tuple(input_rows))
        object.__setattr__(self, "method_ref", method_ref)
        object.__setattr__(self, "input_bindings", input_bindings)
        object.__setattr__(self, "consumer_work_ref", consumer_work_ref)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "context", context)
        _text(self.consumer_use_id, "consumer_use_id")
        object.__setattr__(self, "payload_ref", MappingProxyType(payload))
        object.__setattr__(self, "dependency_versions", dependencies)

    def as_dict(self) -> dict[str, Any]:
        payload = dict(self.payload_ref)
        if "changed_pages" in self.payload_ref:
            payload["changed_pages"] = list(self.payload_ref["changed_pages"])
        result = {
            "schema": INTENT_SCHEMA,
            "kind": self.kind,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload_ref": payload,
            "dependency_versions": {
                str(ref["object_id"]): dict(ref)
                for ref in self.dependency_versions
            },
            "urgency": self.urgency,
            "consumer_use_id": self.consumer_use_id,
        }
        if self.method_ref is not None:
            result.update({
                "method_ref": dict(self.method_ref),
                "input_refs": [dict(ref) for ref in self.input_refs],
                "computer_id": self.computer_id,
                "input_bindings": dict(self.input_bindings),
                "consumer_work_ref": (
                    None if self.consumer_work_ref is None
                    else dict(self.consumer_work_ref)
                ),
                "action": dict(self.action),
                "context": dict(self.context),
            })
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FieldIntent:
        required = {"schema", "kind", "sender", "receiver", "payload_ref",
                    "dependency_versions", "urgency", "consumer_use_id"}
        method_keys = {
            "method_ref", "input_refs", "computer_id", "input_bindings",
            "consumer_work_ref", "action", "context",
        }
        keys = frozenset(value) if isinstance(value, Mapping) else frozenset()
        if keys not in {frozenset(required), frozenset(required | method_keys)}:
            raise FieldCommunicationError("communication intent has an invalid shape")
        if value.get("schema") != INTENT_SCHEMA:
            raise FieldCommunicationError("communication intent schema is unsupported")
        versions = value.get("dependency_versions")
        if isinstance(versions, Mapping):
            version_rows = []
            for key, ref in versions.items():
                if not isinstance(ref, Mapping) or str(ref.get("object_id")) != key:
                    raise FieldCommunicationError("dependency version key does not match its object")
                version_rows.append(ref)
            versions = version_rows
        if not isinstance(versions, list):
            raise FieldCommunicationError("dependency_versions must be an object")
        inputs = value.get("input_refs", [])
        if not isinstance(inputs, list):
            raise FieldCommunicationError("input_refs must be a list")
        return cls(
            value["kind"], value["sender"], value["receiver"],
            value["payload_ref"], tuple(versions), value["urgency"],
            value["consumer_use_id"], value.get("method_ref"), tuple(inputs),
            value.get("computer_id"), value.get("input_bindings"),
            value.get("consumer_work_ref"), value.get("action"),
            value.get("context"),
        )

    @property
    def identity(self) -> str:
        return sha256_value(self.as_dict())

    def regional_event(self, *, program_id: int, scope_id: int, pc: int,
                       site: int, target_id: int) -> dict[str, Any]:
        """Lower intent to the registered receiver and its versioned source."""
        for label, value, minimum in (("program_id", program_id, 1),
                                      ("scope_id", scope_id, 1), ("pc", pc, 0),
                                      ("site", site, 0), ("target_id", target_id, 1)):
            _integer(value, label, minimum=minimum)
        if self.receiver != f"regional-object:{target_id}":
            raise FieldCommunicationError("receiver must bind to the dispatched regional target")
        dependencies = {
            str(ref["object_id"]): ref["object_version"]
            for ref in self.dependency_versions
        }
        return {
            "kind": f"communication:{self.kind}",
            "payload": {"field_communication": self.as_dict()},
            "dependencies": dependencies,
            "pc": pc,
            "priority": 1 if self.urgency == "foreground" else 0,
            "program_id": program_id,
            "scope_id": scope_id,
            "site": site,
            "target_id": target_id,
        }

def admit_intent(
    owner: Any,
    *,
    operation_id: str,
    computer_id: str,
    expected_state_sha256: str | None,
    intent: "FieldIntent",
    dispatch: Mapping[str, Any],
) -> dict[str, Any]:
    """Admit one typed intent through the owner's registered communicate path."""
    event = intent.regional_event(**dict(dispatch))
    return owner.operate_computer(
        operation_id,
        computer_id=computer_id,
        action="communicate",
        arguments={
            "intent": intent.as_dict(),
            "dispatch": dict(dispatch),
            "event": event,
        },
        expected_state_sha256=expected_state_sha256,
    )


def validate_communication_cancellation(
    value: Mapping[str, Any],
    *,
    intent: FieldIntent,
    event_id: int,
) -> tuple[Literal["cancelled", "consumed"], Mapping[str, Any] | None]:
    """Authenticate an owner cancellation fence and any raced receiver use.

    Cancellation is a committed owner transition, not a local continuation
    flag.  If consumption won the race, the owner must return the exact
    committed RECEIVE reference so the caller can admit its ordinary ACK.
    """
    _integer(event_id, "cancelled event_id", minimum=1)
    if not isinstance(value, Mapping):
        raise FieldCommunicationError("communication cancellation receipt is invalid")
    cancellation = _mapping(value, "communication cancellation")
    if set(cancellation) != {
        "schema", "status", "event_id", "intent_sha256", "result_ref",
    } or cancellation.get("schema") != CANCELLATION_SCHEMA:
        raise FieldCommunicationError("communication cancellation receipt schema is invalid")
    if cancellation.get("event_id") != event_id:
        raise FieldCommunicationError("communication cancellation event identity changed")
    if cancellation.get("intent_sha256") != intent.identity:
        raise FieldCommunicationError("communication cancellation intent identity changed")
    status = cancellation.get("status")
    result_ref = cancellation.get("result_ref")
    if status == "cancelled":
        if result_ref is not None:
            raise FieldCommunicationError("cancelled communication unexpectedly has a result")
        return "cancelled", None
    if status != "consumed" or not isinstance(result_ref, Mapping):
        raise FieldCommunicationError("communication cancellation status is invalid")
    result = _mapping(result_ref, "raced communication result")
    if result.get("schema") != RESULT_SCHEMA or result.get("event_id") != event_id:
        raise FieldCommunicationError("raced communication result is not the exact committed event")
    # Validate all source, receiver, consumer-use, and output digests before
    # allowing residency to create the ordinary actual-use acknowledgment.
    actual_use_ack(
        operation_id="communication-cancellation-validation",
        intent=intent,
        result_ref=result,
        delay=0,
    )
    return "consumed", MappingProxyType(result)


def _settled_work_credit(*, use_sha256: str, intent_sha256: str,
                         consumer_use_id: str) -> dict[str, Any]:
    """One deduplicable credit exists only after authenticated actual use."""
    return {
        "schema": WORK_CREDIT_SCHEMA,
        "status": "settled",
        "units": 1,
        "use_sha256": use_sha256,
        "intent_sha256": intent_sha256,
        "consumer_use_id": consumer_use_id,
    }


def actual_use_ack(*, operation_id: str, intent: FieldIntent,
                   result_ref: Mapping[str, Any], delay: int) -> dict[str, Any]:
    """Validate a committed receiver or resident-method result before ACKing use."""
    _text(operation_id, "operation_id")
    result = _mapping(result_ref, "result_ref")
    if intent.method_ref is not None:
        required = {
            "schema", "operation_id", "method_id", "method_generation",
            "source_sha256", "result_sha256",
        }
        if set(result) != required or result.get("schema") != "cassifi.owner-method-result-ref.v1":
            raise FieldCommunicationError("result_ref is not a committed resident method result")
        if (result.get("method_id") != intent.method_ref["method_id"]
                or result.get("method_generation") != intent.method_ref["method_generation"]
                or result.get("source_sha256") != intent.method_ref["source_sha256"]):
            raise FieldCommunicationError("method result does not match the exact Need method version")
        _text(result.get("operation_id"), "result operation_id")
        _digest(result.get("source_sha256"), "result source_sha256")
        _digest(result.get("result_sha256"), "result result_sha256")
        _integer(result.get("method_generation"), "result method_generation", minimum=1)
    elif result.get("schema") == RECORD_RESULT_SCHEMA:
        required = {
            "schema", "operation_id", "id", "kind", "content_version",
            "status", "record_sha256", "output",
        }
        if set(result) != required:
            raise FieldCommunicationError("result_ref is not a committed resident record result")
        _text(result.get("operation_id"), "result operation_id")
        _text(result.get("id"), "result id")
        _text(result.get("kind"), "result kind")
        _integer(result.get("content_version"), "result content_version", minimum=1)
        status = result.get("status")
        if not isinstance(status, str) or not status:
            raise FieldCommunicationError("record result status must be a non-empty string")
        _digest(result.get("record_sha256"), "result record_sha256")
        record_output = _mapping(result.get("output"), "record result output")
        if set(record_output) != {"result_sha256"}:
            raise FieldCommunicationError("record result output schema is invalid")
        _digest(record_output.get("result_sha256"), "record result_sha256")
    else:
        required = {"schema", "operation_id", "event_id", "owner_state_sha256", "output"}
        if set(result) != required or result.get("schema") != RESULT_SCHEMA:
            raise FieldCommunicationError("result_ref is not a committed regional RECEIVE transition")
        _text(result.get("operation_id"), "result operation_id")
        _integer(result.get("event_id"), "result event_id", minimum=1)
        _digest(result.get("owner_state_sha256"), "result owner_state_sha256")
        output = _mapping(result.get("output"), "RECEIVE output")
        expected_output_keys = {
            "schema", "intent_sha256", "consumer_use_id", "receiver",
            "source_object_id", "source_object_version", "source_root_sha256",
            "source_sha256", "target_id", "target_version", "result_sha256",
        }
        if set(output) != expected_output_keys or output.get("schema") != CONSUMPTION_SCHEMA:
            raise FieldCommunicationError("RECEIVE output schema is invalid")
        payload = intent.payload_ref
        expected = {
            "intent_sha256": intent.identity,
            "consumer_use_id": intent.consumer_use_id,
            "receiver": intent.receiver,
            "source_object_id": payload["object_id"],
            "source_object_version": payload["object_version"],
            "source_root_sha256": payload["root_sha256"],
            "source_sha256": payload["source_sha256"],
        }
        if any(output.get(key) != value for key, value in expected.items()):
            raise FieldCommunicationError("RECEIVE output does not prove use of this exact intent source")
        target_id = _integer(output.get("target_id"), "RECEIVE target_id", minimum=1)
        if intent.receiver != f"regional-object:{target_id}":
            raise FieldCommunicationError("RECEIVE target does not match the bound receiver")
        _integer(output.get("target_version"), "RECEIVE target_version", minimum=1)
        _digest(output.get("result_sha256"), "RECEIVE result_sha256")
    delay = _integer(delay, "actual-use delay")
    body = {
        "schema": ACK_SCHEMA,
        "operation_id": operation_id,
        "intent_sha256": intent.identity,
        "consumer_use_id": intent.consumer_use_id,
        "receiver": intent.receiver,
        "result_ref": result,
        "delay": delay,
        "status": "used",
    }
    body["use_sha256"] = sha256_value({
        "intent_sha256": intent.identity,
        "consumer_use_id": intent.consumer_use_id,
    })
    body["work_credit"] = _settled_work_credit(
        use_sha256=body["use_sha256"],
        intent_sha256=intent.identity,
        consumer_use_id=intent.consumer_use_id,
    )
    return body


def learn_locality(state: Mapping[str, Any] | None, *, use: Mapping[str, Any],
                   route: str) -> dict[str, Any]:
    """Pure bounded preference update from an admitted delayed receiver use."""
    _text(route, "route", maximum=256)
    if not isinstance(use, Mapping) or use.get("schema") != ACK_SCHEMA or use.get("status") != "used":
        raise FieldCommunicationError("locality requires an actual receiver-use acknowledgment")
    identity = {
        "intent_sha256": _digest(use.get("intent_sha256"), "use.intent_sha256"),
        "consumer_use_id": _text(use.get("consumer_use_id"), "use.consumer_use_id"),
    }
    declared = use.get("use_sha256")
    if declared != sha256_value(identity):
        raise FieldCommunicationError("actual-use identity digest mismatch")
    delay = _integer(use.get("delay"), "actual-use delay")
    previous = {"schema": LOCALITY_SCHEMA, "observations": [], "routes": {}}
    if state is not None:
        if not isinstance(state, Mapping) or state.get("schema") != LOCALITY_SCHEMA:
            raise FieldCommunicationError("locality state schema is invalid")
        previous = dict(state)
    observations = list(previous.get("observations", []))
    if any(isinstance(row, Mapping) and row.get("use_sha256") == declared for row in observations):
        return previous
    observations.append({"use_sha256": declared, "route": route, "delay": delay})
    observations = observations[-MAX_LOCALITY_OBSERVATIONS:]
    routes = dict(previous.get("routes", {}))
    row = dict(routes.get(route, {"uses": 0, "delay_mean": 0.0, "affinity": 0.5}))
    count = _integer(row.get("uses", 0), "route use count") + 1
    mean = float(row.get("delay_mean", 0.0))
    if not math.isfinite(mean) or mean < 0.0:
        raise FieldCommunicationError("route delay mean is invalid")
    mean += (float(delay) - mean) / count
    routes[route] = {"uses": count, "delay_mean": mean,
                     "affinity": 1.0 / (1.0 + math.log1p(mean))}
    if len(routes) > MAX_LOCALITY_ROUTES:
        evict = min(routes, key=lambda key: (routes[key]["uses"], key))
        if evict == route:
            evict = min(
                (key for key in routes if key != route),
                key=lambda key: (routes[key]["uses"], key),
            )
        del routes[evict]
    return {
        "schema": LOCALITY_SCHEMA,
        "observations": observations,
        "routes": routes,
        "last_use_sha256": declared,
    }


def anticipate_routes(state: Mapping[str, Any], routes: Sequence[str], *, limit: int = 4) -> tuple[str, ...]:
    """Return bounded locality hints; never creates or admits work."""
    if not isinstance(state, Mapping) or state.get("schema") != LOCALITY_SCHEMA:
        raise FieldCommunicationError("locality state schema is invalid")
    limit = _integer(limit, "anticipation limit", minimum=1, maximum=MAX_ROUTE_ANTICIPATION)
    candidates = tuple(dict.fromkeys(_text(route, "route", maximum=256) for route in routes))
    preferences = state.get("routes", {})
    if not isinstance(preferences, Mapping):
        raise FieldCommunicationError("locality route table is invalid")
    return tuple(sorted(candidates, key=lambda route: (-float(preferences.get(route, {}).get("affinity", 0.0)), route))[:limit])
