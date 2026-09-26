"""Revision-bound shared research workspace stored in the regional field task.

The workspace is an operational index over typed program values, guidance,
branches, comparisons, forecasts, outcomes, and retained methods.  It contains
no host planner and performs no external effect: investigation requests bind to
other owner-held program continuations by reference.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping, MutableMapping, Sequence

from programs.python.records import (
    CanonicalRecord,
    ConstructorProgram,
    DesignProblem,
    InstrumentProgram,
    ReasoningStudy,
    RepresentationProgram,
    WorkspaceBinding,
    WorldProgram,
    canonical_json_bytes,
    decode_record,
    digest_value,
)


RUNTIME_SCHEMA = "cassifi.research-workspace-runtime.v1"
RESULT_SCHEMA = "cassifi.research-workspace-result.v1"
_ALLOWED_SCHEMAS = {
    RepresentationProgram.SCHEMA,
    WorldProgram.SCHEMA,
    DesignProblem.SCHEMA,
    ReasoningStudy.SCHEMA,
    InstrumentProgram.SCHEMA,
    ConstructorProgram.SCHEMA,
    WorkspaceBinding.SCHEMA,
    "cassifi.model-program.v1",
    "cassifi.tensor-view.v1",
    "cassifi.computation-view.v1",
    "cassifi.python-program.v1",
}
_ID_FIELDS = (
    "representation_id",
    "world_id",
    "problem_id",
    "study_id",
    "instrument_id",
    "constructor_id",
    "binding_id",
    "program_id",
    "tensor_id",
    "computation_id",
)
DEFAULT_LIMITS = {
    "max_objects": 4_096,
    "max_guidance": 4_096,
    "max_branches": 1_024,
    "max_events": 16_384,
    "max_page": 256,
}
_WORKBENCH_SCHEMA = "cassifi.research-workbench.v1"
_WORKBENCH_CATEGORIES = (
    "claims",
    "methods",
    "guidance",
    "observations",
    "results",
    "constraints",
    "counterexamples",
    "continuations",
    "evidence",
)

def _workbench_template() -> dict[str, Any]:
    return {
        "schema": _WORKBENCH_SCHEMA,
        "programs": {},
        "approaches": {},
        "dependency_versions": {},
        "wakeups": {},
        "sync_requests": {},
    }


def _ensure_workbench(state: MutableMapping[str, Any]) -> bool:
    """Migrate a pre-workbench state exactly once, without discarding evidence."""
    changed = False
    if not isinstance(state.get("workbench"), MutableMapping):
        state["workbench"] = _workbench_template()
        changed = True
    workbench = state["workbench"]
    for key, default in _workbench_template().items():
        if key not in workbench:
            workbench[key] = copy.deepcopy(default)
            changed = True
    return changed


def _workbench_program(
    state: MutableMapping[str, Any],
    program: str,
    *,
    create: bool = True,
) -> MutableMapping[str, Any] | None:
    _ensure_workbench(state)
    programs = state["workbench"]["programs"]
    row = programs.get(program)
    if row is None and create:
        row = {
            "schema": "cassifi.research-workbench-program.v1",
            "program": program,
            "mission": None,
            "questions": {},
            "records": {},
            "result": None,
            "status": None,
            "continuation_refs": [],
            "pending_operations": {},
            "operations": {},
            "context_requests": {},
            "outcome_inputs": None,
            "dependency_versions": {},
            "next_action": None,
        }
        programs[program] = row
    return row


def _wb_unique(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result


def _wb_refs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return _wb_unique([item for item in value if isinstance(item, str)])
    return []


def _wb_record_key(kind: str, value: Mapping[str, Any]) -> str:
    for field in ("key", "record_id", "claim_id", "method_id", "guidance_id", "ref", "id"):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            return raw
    return f"{kind}:{digest_value(value)[:24]}"


def _wb_record(
    program: MutableMapping[str, Any],
    kind: str,
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    raw = _plain(value)
    key = _wb_record_key(kind, raw)
    existing = program["records"].get(key)
    if existing is not None:
        if existing.get("sha256") != digest_value(raw):
            raise WorkspaceRuntimeError("workbench record identity conflict")
        return existing
    raw_dependencies = raw.get("dependencies", ())
    if isinstance(raw_dependencies, Mapping):
        dependencies = _wb_unique(raw_dependencies.keys())
        dependency_versions = _plain(raw_dependencies)
    else:
        dependencies = _wb_refs(raw_dependencies)
        dependency_versions = _plain(raw.get("dependency_versions", {}))
    source_refs = _wb_refs(raw.get("source_refs", raw.get("sources", ())))
    wrapper_keys = {
        "key",
        "kind",
        "value",
        "source_refs",
        "dependencies",
        "dependency_versions",
        "protected",
        "page",
        "pages",
        "version",
        "content_version",
    }
    stored_value = raw.get("value") if "value" in raw and set(raw).issubset(wrapper_keys) else raw
    row = {
        "key": key,
        "kind": kind,
        "value": _plain(stored_value),
        "source_refs": source_refs,
        "dependencies": dependencies,
        "dependency_versions": dependency_versions if isinstance(dependency_versions, Mapping) else {},
        "version": raw.get("version", raw.get("content_version")),
        "protected": bool(raw.get("protected", False) or kind in {"constraints", "counterexamples"}),
        "valid": True,
        "sha256": digest_value(raw),
    }
    if "page" in raw:
        row["page"] = raw["page"]
    if "pages" in raw:
        row["pages"] = raw["pages"]
    program["records"][key] = row
    return row


def _text_list(values: Any, label: str) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise WorkspaceRuntimeError(f"{label} list is invalid")
    return [_text(item, label) for item in values]


def _wb_find_record(
    state: Mapping[str, Any],
    reference: str,
    *,
    program: str | None = None,
) -> tuple[str, Mapping[str, Any]] | None:
    programs = state.get("workbench", {}).get("programs", {})
    selected = [programs[program]] if program in programs else [] if program else list(programs.values())
    for item in selected:
        if reference in item.get("records", {}):
            return item.get("program", ""), item["records"][reference]
        for key, row in item.get("records", {}).items():
            row_value = row.get("value", {})
            row_id = row_value.get("id") if isinstance(row_value, Mapping) else None
            if reference in row.get("source_refs", ()) or reference == row_id:
                return item.get("program", ""), row
    return None


def _workbench_view(state: Mapping[str, Any], program: str) -> Mapping[str, Any]:
    row = state.get("workbench", {}).get("programs", {}).get(program)
    if row is None:
        return {
            "schema": _WORKBENCH_SCHEMA,
            "program": program,
            "field_revision": state["state_sha256"],
            "mission": None,
            "questions": {},
            "records": {},
            "result": None,
            "status": None,
            "continuation_refs": [],
            "outcome_inputs": None,
            "dependency_versions": {},
            "next_action": None,
            "approaches": [],
            "wakeups": [],
        }
    approaches = [
        row_item
        for row_item in state.get("workbench", {}).get("approaches", {}).values()
        if row_item.get("program") == program
    ]
    wakeups = [
        row_item
        for row_item in state.get("workbench", {}).get("wakeups", {}).values()
        if row_item.get("program") == program and not row_item.get("consumed", False)
    ]
    return {
        "schema": _WORKBENCH_SCHEMA,
        "program": program,
        "field_revision": state["state_sha256"],
        **_plain(row),
        "approaches": sorted((_plain(item) for item in approaches), key=lambda item: item["request_id"]),
        "wakeups": sorted((_plain(item) for item in wakeups), key=lambda item: item["wake_id"]),
    }


class WorkspaceRuntimeError(ValueError):
    """A workspace command violates identity, revision, or access rules."""


def _plain(value: Any) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise WorkspaceRuntimeError("workspace value is not canonical JSON") from exc
def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4_096:
        raise WorkspaceRuntimeError(f"{label} must be bounded nonempty text")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise WorkspaceRuntimeError(f"{label} must be an integer >= {minimum}")
    return value


def _limit(state: Mapping[str, Any], name: str) -> int:
    return int(state["limits"][name])


def _revision_body(state: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "objects": state["objects"],
        "latest": state["latest"],
        "access": state["access"],
        "guidance": state["guidance"],
        "branches": state["branches"],
        "comparisons": state["comparisons"],
        "retained": state["retained"],
        "forecasts": state["forecasts"],
        "outcomes": state["outcomes"],
        "dependency_status": state["dependency_status"],
        "workbench": state.get("workbench", _workbench_template()),
        "phase": state["phase"],
    }


def _refresh(state: MutableMapping[str, Any]) -> None:
    state["revision"] = int(state["revision"]) + 1
    state["state_sha256"] = digest_value(_revision_body(state))


def _event(state: MutableMapping[str, Any], kind: str, payload: Mapping[str, Any]) -> None:
    if len(state["events"]) >= _limit(state, "max_events"):
        raise WorkspaceRuntimeError("workspace event limit exhausted")
    sequence = int(state["counters"]["event"])
    state["counters"]["event"] = sequence + 1
    state["events"].append(
        {
            "schema": "cassifi.research-workspace-event.v1",
            "sequence": sequence,
            "kind": _text(kind, "event kind"),
            "revision": int(state["revision"]),
            "field_revision": state["state_sha256"],
            "payload": _plain(payload),
        }
    )


def _expected_revision(state: Mapping[str, Any], arguments: Mapping[str, Any]) -> None:
    expected = arguments.get("expected_field_revision")
    if expected is not None and expected != state["state_sha256"]:
        raise WorkspaceRuntimeError("workspace target revision is stale")


def _record_identity(value: Mapping[str, Any]) -> tuple[str, int]:
    identifier = next((value[field] for field in _ID_FIELDS if isinstance(value.get(field), str)), None)
    if identifier is None:
        raise WorkspaceRuntimeError("workspace record has no supported identity")
    version = value.get("version", 1)
    return _text(identifier, "record identity"), _integer(version, "record version", minimum=1)


def _record_dependencies(value: Mapping[str, Any]) -> list[str]:
    result: set[str] = set()
    for key in (
        "dependencies",
        "construction_dependencies",
        "operator_refs",
        "product_lineage",
        "question_refs",
        "object_refs",
    ):
        raw = value.get(key, ())
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            result.update(str(item) for item in raw)
    for key in (
        "state_program_ref",
        "transition_program_ref",
        "readout_program_ref",
        "callable_program_ref",
        "world_version",
        "method_version",
        "original_episode",
    ):
        raw = value.get(key)
        if isinstance(raw, str) and raw:
            result.add(raw)
    return sorted(result)


def _resolve_key(state: Mapping[str, Any], reference: str) -> str | None:
    if reference in state["objects"]:
        return reference
    return state["latest"].get(reference)


def _can_read(state: Mapping[str, Any], key: str, principal: str) -> bool:
    access = state["access"].get(key, {})
    return access.get("visibility") == "shared" or principal in access.get("principals", []) or principal == state["identity"]["principal"]


def _admit_record(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    if len(state["objects"]) >= _limit(state, "max_objects"):
        raise WorkspaceRuntimeError("workspace object limit exhausted")
    raw = arguments.get("record")
    if not isinstance(raw, Mapping) or raw.get("schema") not in _ALLOWED_SCHEMAS:
        raise WorkspaceRuntimeError("workspace record schema is unsupported")
    try:
        record: CanonicalRecord = decode_record(raw)
    except ValueError as exc:
        raise WorkspaceRuntimeError(str(exc)) from exc
    value = record.as_dict()
    identifier, version = _record_identity(value)
    key = f"{identifier}@{version}"
    digest = digest_value(value)
    existing = state["objects"].get(key)
    if existing is not None:
        if existing["sha256"] != digest:
            raise WorkspaceRuntimeError("record identity and version conflict")
        return _plain(existing)
    current_key = state["latest"].get(identifier)
    if current_key is not None:
        current_version = int(state["objects"][current_key]["version"])
        if version <= current_version:
            raise WorkspaceRuntimeError("record version does not advance its identity")
    visibility = str(arguments.get("visibility", "private"))
    if visibility not in {"private", "shared"}:
        raise WorkspaceRuntimeError("record visibility is invalid")
    principals = sorted({_text(item, "principal") for item in arguments.get("principals", ())})
    principal = _text(str(arguments.get("principal", state["identity"]["principal"])), "principal")
    if principal not in principals:
        principals.append(principal)
        principals.sort()
    dependencies = _record_dependencies(value)
    missing = [reference for reference in dependencies if _resolve_key(state, reference) is None]
    row = {
        "key": key,
        "identifier": identifier,
        "version": version,
        "schema": value["schema"],
        "record": value,
        "sha256": digest,
        "dependencies": dependencies,
        "missing_dependencies": missing,
        "status": "unresolved" if missing else "admitted",
        "origin": _plain(arguments.get("origin", {"kind": "field-program"})),
    }
    state["objects"][key] = row
    state["latest"][identifier] = key
    state["access"][key] = {"visibility": visibility, "principals": principals}
    state["dependency_status"][key] = {"valid": not missing, "invalidated_by": [], "missing": missing}
    _refresh(state)
    _event(state, "workspace-record-admitted", {"key": key, "sha256": digest, "status": row["status"]})
    return _plain(row)


def _propose(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if len(state["guidance"]) >= _limit(state, "max_guidance"):
        raise WorkspaceRuntimeError("workspace guidance limit exhausted")
    request_id = _text(arguments.get("request_id"), "request_id")
    principal = _text(arguments.get("principal"), "principal")
    payload = {
        "principal": principal,
        "request_id": request_id,
        "target_refs": [_text(item, "target reference") for item in arguments.get("target_refs", ())],
        "expected_versions": _plain(arguments.get("expected_versions", {})),
        "intended_role": _text(arguments.get("intended_role"), "intended_role"),
        "arguments": _plain(arguments.get("arguments", {})),
        "dependencies": [_text(item, "dependency") for item in arguments.get("dependencies", ())],
        "source_refs": [_text(item, "source reference") for item in arguments.get("source_refs", ())],
    }
    request_sha256 = digest_value(payload)
    existing = state["guidance"].get(request_id)
    if existing is not None:
        if existing["request_sha256"] != request_sha256:
            raise WorkspaceRuntimeError("guidance request identity conflict")
        return _plain(existing)
    statuses: list[str] = []
    resolved: list[str] = []
    for reference in payload["target_refs"]:
        key = _resolve_key(state, reference)
        if key is None:
            statuses.append("ambiguous")
            continue
        if not _can_read(state, key, principal):
            statuses.append("inaccessible")
            continue
        expected_version = payload["expected_versions"].get(reference)
        if expected_version is not None and int(expected_version) != int(state["objects"][key]["version"]):
            statuses.append("stale")
            continue
        statuses.append("resolved")
        resolved.append(key)
    if "inaccessible" in statuses:
        disposition = "inaccessible"
    elif "stale" in statuses:
        disposition = "stale"
    elif "ambiguous" in statuses or not resolved:
        disposition = "ambiguous"
    else:
        disposition = "admitted"
    row = {
        "schema": "cassifi.workspace-guidance.v1",
        **payload,
        "request_sha256": request_sha256,
        "field_revision": state["state_sha256"],
        "resolved_targets": resolved,
        "disposition": disposition,
        "consequences": [],
    }
    state["guidance"][request_id] = row
    _refresh(state)
    _event(state, "workspace-guidance-proposed", {"request_id": request_id, "disposition": disposition})
    return _plain(row)


def _branch_evidence(state: Mapping[str, Any], references: Sequence[str]) -> Mapping[str, Any]:
    snapshot: dict[str, Any] = {}
    for reference in _wb_unique(references):
        object_key = _resolve_key(state, reference)
        if object_key is not None:
            row = state["objects"][object_key]
            snapshot[reference] = {
                "reference": reference,
                "key": object_key,
                "sha256": row["sha256"],
                "version": int(row["version"]),
            }
            continue
        found = _wb_find_record(state, reference)
        if found is None:
            raise WorkspaceRuntimeError("branch evidence reference is unknown")
        _, row = found
        snapshot[reference] = {
            "reference": reference,
            "key": row["key"],
            "sha256": row["sha256"],
            "version": row.get("value", {}).get("version"),
        }
    return snapshot


def _verify_branch_evidence(state: Mapping[str, Any], branch: Mapping[str, Any]) -> None:
    for reference, expected in branch.get("evidence_snapshot", {}).items():
        object_key = _resolve_key(state, reference)
        actual: Mapping[str, Any] | None = None
        if object_key is not None:
            actual = state["objects"][object_key]
        else:
            found = _wb_find_record(state, reference)
            if found is not None:
                actual = found[1]
        if actual is None or actual.get("sha256") != expected.get("sha256"):
            raise WorkspaceRuntimeError("branch evidence is stale or conflicting")


def _investigate(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    if len(state["branches"]) >= _limit(state, "max_branches"):
        raise WorkspaceRuntimeError("workspace branch limit exhausted")
    request_id = _text(arguments.get("request_id"), "request_id")
    guidance = state["guidance"].get(request_id)
    if not isinstance(guidance, Mapping) or guidance["disposition"] != "admitted":
        raise WorkspaceRuntimeError("investigation requires admitted guidance")
    branch_id = _text(arguments.get("branch_id"), "branch_id")
    if branch_id in state["branches"]:
        raise WorkspaceRuntimeError("workspace branch identity already exists")
    if arguments.get("effect_policy", "forbid") != "forbid":
        raise WorkspaceRuntimeError("workspace investigations forbid external effects")
    evidence_refs = _wb_unique([
        *[_text(item, "evidence reference") for item in arguments.get("evidence_refs", ())],
        *[_text(item, "held-fixed reference") for item in arguments.get("held_fixed", ())],
        *[_text(item, "source reference") for item in arguments.get("source_refs", ())],
    ])
    branch = {
        "schema": "cassifi.workspace-investigation-branch.v1",
        "branch_id": branch_id,
        "request_id": request_id,
        "predecessor_revision": state["state_sha256"],
        "program_refs": [_text(item, "program reference") for item in arguments.get("program_refs", ())],
        "program": arguments.get("program"),
        "question_id": arguments.get("question_id"),
        "hypothesis": _plain(arguments.get("hypothesis", arguments.get("assumptions", []))),
        "assumptions": _plain(arguments.get("assumptions", [])),
        "held_fixed": _text_list(arguments.get("held_fixed", ()), "held-fixed reference"),
        "evidence_refs": evidence_refs,
        "evidence_snapshot": _branch_evidence(state, evidence_refs),
        "continuation_refs": _wb_refs(arguments.get("continuation_refs", arguments.get("continuations", ()))),
        "readouts": _plain(arguments.get("readouts", [])),
        "effect_policy": "forbid",
        "status": "running",
        "result": None,
        "actual_cost": None,
    }
    state["branches"][branch_id] = branch
    _refresh(state)
    _event(state, "workspace-investigation-started", {"branch_id": branch_id, "request_id": request_id})
    return _plain(branch)


def _settle_branch(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    branch_id = _text(arguments.get("branch_id"), "branch_id")
    branch = state["branches"].get(branch_id)
    if not isinstance(branch, MutableMapping) or branch["status"] not in {"running", "paused"}:
        raise WorkspaceRuntimeError("workspace branch is not active")
    _verify_branch_evidence(state, branch)
    disposition = str(arguments.get("disposition", "completed"))
    if disposition not in {"completed", "failed", "cancelled", "exhausted", "infeasible", "unresolved"}:
        raise WorkspaceRuntimeError("branch disposition is invalid")
    result = _plain(arguments.get("result"))
    if disposition == "completed":
        if not isinstance(result, Mapping) or result.get("complete", True) is False or result.get("conflict", False):
            raise WorkspaceRuntimeError("branch result is incomplete or conflicting")
        if result.get("field_revision") is not None and result["field_revision"] != state["state_sha256"]:
            raise WorkspaceRuntimeError("branch result revision is stale")
    branch["status"] = disposition
    branch["result"] = result
    branch["actual_cost"] = _plain(arguments.get("actual_cost", {}))
    branch["successor_refs"] = [_text(item, "successor reference") for item in arguments.get("successor_refs", ())]
    guidance = state["guidance"].get(branch["request_id"])
    if isinstance(guidance, MutableMapping) and branch_id not in guidance["consequences"]:
        guidance["consequences"].append(branch_id)
    _refresh(state)
    _event(state, "workspace-investigation-settled", {"branch_id": branch_id, "disposition": disposition})
    return _plain(branch)


def _compare(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    comparison_id = _text(arguments.get("comparison_id"), "comparison_id")
    if comparison_id in state["comparisons"]:
        raise WorkspaceRuntimeError("comparison identity already exists")
    branch_ids = [_text(item, "branch_id") for item in arguments.get("branch_ids", ())]
    if len(branch_ids) < 2 or any(item not in state["branches"] for item in branch_ids):
        raise WorkspaceRuntimeError("comparison requires at least two known branches")
    for branch_id in branch_ids:
        branch = state["branches"][branch_id]
        if branch["status"] not in {"completed", "failed", "cancelled", "exhausted", "infeasible", "unresolved"}:
            raise WorkspaceRuntimeError("comparison requires settled branches")
        _verify_branch_evidence(state, branch)
    shared = _plain(arguments.get("shared_conditions", {}))
    differences = _plain(arguments.get("differences", []))
    evidence_refs = _wb_unique(
        reference
        for branch_id in branch_ids
        for reference in state["branches"][branch_id].get("evidence_refs", ())
    )
    row = {
        "schema": "cassifi.workspace-comparison.v1",
        "comparison_id": comparison_id,
        "branch_ids": branch_ids,
        "shared_conditions": shared,
        "differences": differences,
        "evidence_refs": evidence_refs,
        "readouts": {item: _plain(state["branches"][item].get("result")) for item in branch_ids},
        "interpretation": _plain(arguments.get("interpretation", {})),
        "scope": _text(str(arguments.get("scope", "within-recorded-execution")), "scope"),
    }
    state["comparisons"][comparison_id] = row
    _refresh(state)
    _event(state, "workspace-comparison-recorded", {"comparison_id": comparison_id, "branch_ids": branch_ids})
    return _plain(row)


def _retain(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    retention_id = _text(arguments.get("retention_id"), "retention_id")
    if retention_id in state["retained"]:
        existing = state["retained"][retention_id]
        if existing["request_sha256"] != digest_value({key: value for key, value in arguments.items() if key != "expected_field_revision"}):
            raise WorkspaceRuntimeError("retention identity conflict")
        return _plain(existing)
    object_refs = [_text(item, "object reference") for item in arguments.get("object_refs", ())]
    resolved = [_resolve_key(state, item) for item in object_refs]
    if any(item is None for item in resolved):
        raise WorkspaceRuntimeError("retention names an unknown object")
    workbench_refs = _wb_refs(arguments.get("workbench_refs", arguments.get("evidence_refs", ())))
    for reference in workbench_refs:
        found = _wb_find_record(state, reference)
        if found is None or not found[1].get("valid", True):
            raise WorkspaceRuntimeError("retention names stale or unknown workbench evidence")
    applicability = _plain(arguments.get("applicability", {}))
    exceptions = _plain(arguments.get("exceptions", []))
    row = {
        "schema": "cassifi.workspace-retention.v1",
        "retention_id": retention_id,
        "object_refs": object_refs,
        "resolved_objects": resolved,
        "workbench_refs": workbench_refs,
        "comparison_refs": [_text(item, "comparison reference") for item in arguments.get("comparison_refs", ())],
        "applicability": applicability,
        "exceptions": exceptions,
        "status": "retained",
        "request_sha256": digest_value({key: value for key, value in arguments.items() if key != "expected_field_revision"}),
    }
    state["retained"][retention_id] = row
    _refresh(state)
    _event(state, "workspace-method-retained", {"retention_id": retention_id, "objects": resolved})
    return _plain(row)


def _sync_workbench(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    _ensure_workbench(state)
    program_name = _text(arguments.get("program"), "program")
    request_id = _text(arguments.get("request_id"), "request_id")
    outcome = arguments.get("outcome", {})
    if outcome is None:
        outcome = {}
    if not isinstance(outcome, Mapping):
        raise WorkspaceRuntimeError("workbench outcome must be a mapping")
    payload = {
        "program": program_name,
        "request_id": request_id,
        "operation": _text(arguments.get("operation", "sync-workbench"), "operation"),
        "outcome": _plain(outcome),
    }
    request_sha256 = digest_value(payload)
    previous = state["workbench"]["sync_requests"].get(request_id)
    operation_id = outcome.get("operation_id", arguments.get("operation_id"))
    if previous is not None and previous["request_sha256"] == request_sha256:
        view = _workbench_view(state, previous["program"])
        view["consumed_wakeups"] = previous.get("consumed_wakeups", [])
        return view
    if previous is not None and previous.get("operation_id") != operation_id:
        raise WorkspaceRuntimeError("workbench request identity conflict")
    program = _workbench_program(state, program_name)
    assert program is not None

    def refs_from(value: Any) -> list[str]:
        if isinstance(value, Mapping):
            result = []
            for key in (
                "continuation_refs",
                "continuations",
                "continuation",
                "continuation_ref",
                "result_ref",
                "refs",
                "references",
            ):
                result.extend(_wb_refs(value.get(key, ())))
            return _wb_unique(result)
        return _wb_refs(value)

    if "mission" in outcome:
        program["mission"] = _plain(outcome["mission"])
    if "question" in outcome:
        question = outcome["question"]
        question_id = _text(
            outcome.get("question_id", arguments.get("question_id", digest_value(question)[:24])),
            "question_id",
        )
        previous = program["questions"].get(question_id, {})
        same_question = previous.get("question") == _plain(question)
        program["questions"][question_id] = {
            "question_id": question_id,
            "question": _plain(question),
            "required_refs": _wb_refs(outcome.get(
                "required_refs",
                previous.get("required_refs", ()) if same_question else (),
            )),
            "protected_refs": _wb_refs(outcome.get(
                "protected_refs",
                previous.get("protected_refs", ()) if same_question else (),
            )),
            "next_action": _plain(outcome.get(
                "next_action",
                previous.get("next_action") if same_question else None,
            )),
        }
    if "questions" in outcome:
        questions = outcome["questions"]
        if isinstance(questions, Mapping):
            questions = [{"question_id": key, "question": value} for key, value in questions.items()]
        if isinstance(questions, Sequence) and not isinstance(questions, (str, bytes)):
            for item in questions:
                if not isinstance(item, Mapping):
                    continue
                question_id = _text(item.get("question_id", item.get("id", digest_value(item)[:24])), "question_id")
                program["questions"][question_id] = {
                    "question_id": question_id,
                    "question": _plain(item.get("question", item)),
                    "required_refs": _wb_refs(item.get("required_refs", item.get("required", ()))),
                    "protected_refs": _wb_refs(item.get("protected_refs", item.get("protected", ()))),
                    "next_action": _plain(item.get("next_action")),
                }
    for kind in _WORKBENCH_CATEGORIES:
        values = outcome.get(kind, ())
        if isinstance(values, Mapping):
            values = [dict(value, key=key) if isinstance(value, Mapping) else {"key": key, "value": value} for key, value in values.items()]
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            for item in values:
                if isinstance(item, Mapping):
                    _wb_record(program, kind, item)
    records = outcome.get("records", ())
    if isinstance(records, Mapping):
        records = [dict(value, key=key) if isinstance(value, Mapping) else {"key": key, "value": value} for key, value in records.items()]
    if isinstance(records, Sequence) and not isinstance(records, (str, bytes)):
        for item in records:
            if isinstance(item, Mapping):
                _wb_record(program, str(item.get("kind", "evidence")), item)
    candidate_program = outcome.get("candidate_program")
    if isinstance(candidate_program, Mapping):
        for kind in ("claims", "methods", "guidance", "observations", "constraints", "counterexamples"):
            values = candidate_program.get(kind, ())
            if isinstance(values, Mapping):
                values = list(values.values())
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                for item in values:
                    if isinstance(item, Mapping):
                        _wb_record(program, kind, item)
        current_question_id = candidate_program.get("current_question_id")
        if isinstance(current_question_id, str) and current_question_id in program["questions"]:
            program["questions"][current_question_id]["next_action"] = _plain(candidate_program.get("next_action"))
    if "deliverable_state" in outcome:
        _wb_record(program, "results", {"key": f"deliverable:{operation_id or request_id}", "value": outcome["deliverable_state"]})

    status = str(outcome.get("status", "observed"))
    consumed_wakeups: list[str] = []
    projected_status = outcome.get("program_status")
    if projected_status is None and isinstance(outcome.get("program"), Mapping):
        projected_status = outcome["program"].get("status")
    if projected_status is None and isinstance(outcome.get("candidate_program"), Mapping):
        projected_status = outcome["candidate_program"].get("status")
    if projected_status is None and status in {"executed", "committed"}:
        projected_status = status
    if projected_status is not None:
        program["status"] = _plain(projected_status)
    if projected_status is not None and projected_status != "blocked":
        for wake_id, wake in state["workbench"]["wakeups"].items():
            if wake.get("program") == program_name and not wake.get("consumed", False):
                wake["consumed"] = True
                consumed_wakeups.append(wake_id)
    if operation_id is not None:
        operation_id = _text(operation_id, "operation_id")
        plan = _plain(outcome.get("plan", {}))
        if isinstance(plan, Mapping):
            plan_versions = plan.get("dependency_versions", plan.get("dependencies", {}))
            if isinstance(plan_versions, Mapping):
                for key, value in plan_versions.items():
                    identity = _text(key, "dependency identity")
                    program["dependency_versions"][identity] = _plain(value)
                    state["workbench"]["dependency_versions"][identity] = _plain(value)
        refs = _wb_unique([*refs_from(plan), *refs_from(outcome)])
        if status == "planned":
            program["pending_operations"][operation_id] = {
                "continuation_refs": refs,
                "next_action": _plain(outcome.get("next_action", plan.get("next_action") if isinstance(plan, Mapping) else None)),
            }
            program["continuation_refs"] = _wb_unique([*program["continuation_refs"], *refs])
        elif status in {"executed", "committed"}:
            pending = program["pending_operations"].pop(operation_id, {})
            pending_refs = pending.get("continuation_refs", [])
            program["continuation_refs"] = [ref for ref in program["continuation_refs"] if ref not in pending_refs]
            if refs:
                program["continuation_refs"] = _wb_unique([*program["continuation_refs"], *refs])
        program["operations"][operation_id] = {
            "operation_id": operation_id,
            "status": status,
            "plan": plan,
            "outcome": _plain(outcome),
            "field_revision": state["state_sha256"],
        }
        if "next_action" in outcome:
            program["next_action"] = _plain(outcome["next_action"])
        elif isinstance(plan, Mapping) and "next_action" in plan:
            program["next_action"] = _plain(plan["next_action"])
    if status == "context_request":
        question = _plain(outcome.get("question", {}))
        gaps = _wb_unique(outcome.get("gaps", ()))
        context_key = digest_value({"program": program_name, "question": question, "gaps": gaps})
        program["context_requests"][context_key] = {
            "context_request_id": context_key,
            "reason": _plain(outcome.get("reason")),
            "gaps": gaps,
            "question": question,
        }
    if "result" in outcome:
        program["result"] = _plain(outcome["result"])
    elif status == "committed" and "synthesis" in outcome:
        program["result"] = _plain(outcome["synthesis"])
    continuation_refs = refs_from(outcome.get("continuation_refs", ()))
    if continuation_refs:
        program["continuation_refs"] = _wb_unique([*program["continuation_refs"], *continuation_refs])
    if isinstance(outcome.get("continuation"), Mapping):
        continuation = outcome["continuation"]
        ref = _text(continuation.get("ref", continuation.get("id", digest_value(continuation)[:24])), "continuation ref")
        _wb_record(program, "continuations", {**continuation, "key": ref})
        program["continuation_refs"] = _wb_unique([*program["continuation_refs"], ref])
    if "outcome_inputs" in outcome or "inputs" in outcome:
        program["outcome_inputs"] = _plain(outcome.get("outcome_inputs", outcome.get("inputs")))
    versions = outcome.get("dependency_versions", outcome.get("dependencies", {}))
    if isinstance(versions, Mapping):
        for key, value in versions.items():
            identity = _text(key, "dependency identity")
            program["dependency_versions"][identity] = _plain(value)
            state["workbench"]["dependency_versions"][identity] = _plain(value)
    state["workbench"]["sync_requests"][request_id] = {
        "request_sha256": request_sha256,
        "operation_id": operation_id,
        "program": program_name,
        "field_revision": state["state_sha256"],
        "consumed_wakeups": consumed_wakeups,
    }
    _refresh(state)
    _event(state, "workspace-workbench-synced", {"program": program_name, "request_id": request_id, "status": status})
    view = _workbench_view(state, program_name)
    view["consumed_wakeups"] = consumed_wakeups
    return view


def _record_approach(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    _ensure_workbench(state)
    request_id = _text(arguments.get("request_id"), "request_id")
    program = _text(arguments.get("program", "__workspace__"), "program")
    action = _text(arguments.get("action"), "action")
    action_arguments = _plain(arguments.get("arguments", {}))
    dependencies = _plain(arguments.get("dependencies", {}))
    program_row = _workbench_program(state, program, create=False)
    if (not dependencies) and isinstance(program_row, Mapping):
        dependencies = _plain(program_row.get("dependency_versions", {}))
    if not isinstance(dependencies, Mapping):
        raise WorkspaceRuntimeError("approach dependencies must be a mapping")
    reopen_when = _plain(arguments.get("reopen_when", {"any_dependency_change": True}))
    if not isinstance(reopen_when, Mapping):
        raise WorkspaceRuntimeError("approach reopen_when must be a mapping")
    payload = {
        "program": program,
        "question_id": arguments.get("question_id"),
        "action": action,
        "arguments": action_arguments,
        "reason": _text(arguments.get("reason"), "reason"),
        "dependencies": dependencies,
        "reopen_when": reopen_when,
    }
    request_sha256 = digest_value(payload)
    existing = state["workbench"]["approaches"].get(request_id)
    if existing is not None:
        if existing["request_sha256"] != request_sha256:
            raise WorkspaceRuntimeError("approach request identity conflict")
        return _plain(existing)
    failure_identity = digest_value(
        {"program": program, "action": action, "arguments": action_arguments, "dependencies": dependencies}
    )
    for prior in state["workbench"]["approaches"].values():
        if prior.get("failure_identity") == failure_identity and prior.get("status") in {"blocked", "failed", "woken"}:
            row = _plain(prior)
            row["duplicate_of"] = prior["request_id"]
            return row
    row = {
        "schema": "cassifi.workspace-approach-failure.v1",
        "request_id": request_id,
        "program": program,
        "question_id": arguments.get("question_id"),
        "action": action,
        "arguments": action_arguments,
        "reason": _text(arguments.get("reason"), "reason"),
        "dependencies": dependencies,
        "reopen_when": reopen_when,
        "status": "blocked",
        "failure_identity": failure_identity,
        "request_sha256": request_sha256,
        "field_revision": state["state_sha256"],
        "wakeup_count": 0,
        "invalidated_by": [],
    }
    state["workbench"]["approaches"][request_id] = row
    _refresh(state)
    _event(state, "workspace-approach-blocked", {"request_id": request_id, "program": program})
    return _plain(row)


def _dependency_change(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    _ensure_workbench(state)
    request_id = _text(arguments.get("request_id"), "request_id")
    changes = _plain(arguments.get("changes", {}))
    if not isinstance(changes, Mapping) or not changes:
        raise WorkspaceRuntimeError("dependency changes must be a nonempty mapping")
    payload = {"request_id": request_id, "changes": changes}
    request_sha256 = digest_value(payload)
    previous = state["workbench"]["sync_requests"].get(f"dependency:{request_id}")
    if previous is not None:
        if previous["request_sha256"] != request_sha256:
            raise WorkspaceRuntimeError("dependency change identity conflict")
        return _plain(previous["result"])
    invalidated: list[str] = []
    for identity, version in changes.items():
        identity = _text(identity, "dependency identity")
        state["workbench"]["dependency_versions"][identity] = _plain(version)
    for program in state["workbench"]["programs"].values():
        for key, record in program["records"].items():
            for identity, expected in record.get("dependency_versions", {}).items():
                if identity in changes and expected != changes[identity]:
                    record["valid"] = False
                    invalidated.append(key)
                    break
    wakeups: list[str] = []
    for approach in state["workbench"]["approaches"].values():
        affected = [identity for identity in approach["dependencies"] if identity in changes and approach["dependencies"][identity] != changes[identity]]
        if not affected:
            continue
        approach["status"] = "woken"
        approach["invalidated_by"].append({"changes": _plain({key: changes[key] for key in affected})})
        wake_id = digest_value({"failure_identity": approach["failure_identity"], "changes": {key: changes[key] for key in affected}})
        wake = state["workbench"]["wakeups"].get(wake_id)
        if wake is None:
            wake = {
                "schema": "cassifi.workspace-wakeup.v1",
                "wake_id": wake_id,
                "request_id": approach["request_id"],
                "program": approach["program"],
                "dependencies": affected,
                "changes": _plain({key: changes[key] for key in affected}),
                "consumed": False,
            }
            state["workbench"]["wakeups"][wake_id] = wake
            approach["wakeup_count"] += 1
            wakeups.append(wake_id)
        elif not wake.get("consumed", False):
            wakeups.append(wake_id)
    result = {
        "schema": "cassifi.workspace-dependency-change.v1",
        "request_id": request_id,
        "changes": _plain(changes),
        "invalidated": _wb_unique(invalidated),
        "wakeups": _wb_unique(wakeups),
    }
    state["workbench"]["sync_requests"][f"dependency:{request_id}"] = {
        "request_sha256": request_sha256,
        "result": result,
    }
    _refresh(state)
    _event(state, "workspace-dependency-changed", {"request_id": request_id, "wakeups": wakeups})
    result["field_revision"] = state["state_sha256"]
    return result


def _context_entry(program: str, row: Mapping[str, Any], *, reason: str, relevance: float) -> Mapping[str, Any]:
    return {
        "key": row["key"],
        "kind": row["kind"],
        "value": _plain(row["value"]),
        "source_refs": _plain(row.get("source_refs", [])),
        "dependencies": _plain(row.get("dependencies", [])),
        "reason": reason,
        "relevance": relevance,
        "priority": 2 if row.get("protected") else 1,
        "program": program,
    }


def _context_entry(program: str, row: Mapping[str, Any], *, reason: str, relevance: float) -> Mapping[str, Any]:
    value = _plain(row["value"])
    entry = {
        "key": row["key"],
        "kind": row["kind"],
        "value": value,
        "source_refs": _plain(row.get("source_refs", [])),
        "dependencies": _plain(row.get("dependencies", [])),
        "version": row.get("version", value.get("version") if isinstance(value, Mapping) else None),
        "reason": reason,
        "relevance": relevance,
        "priority": 2 if row.get("protected") else 1,
        "program": program,
    }
    if "page" in row:
        entry["page"] = row["page"]
    elif "pages" in row:
        entry["pages"] = row["pages"]
    return entry


def select_context(
    state: Mapping[str, Any],
    question: Any,
    question_id: str | None = None,
    maximum: int = 64,
) -> Mapping[str, Any]:
    maximum = _integer(maximum, "maximum", minimum=1)
    if maximum > int(state.get("limits", DEFAULT_LIMITS).get("max_page", 256)):
        raise WorkspaceRuntimeError("context maximum exceeds its bound")
    workbench = state.get("workbench", {})
    programs = workbench.get("programs", {}) if isinstance(workbench, Mapping) else {}
    query = json.dumps(_plain(question), sort_keys=True, ensure_ascii=False).lower()
    words = {word for word in query.replace("_", " ").split() if len(word) > 2}
    required_refs: list[tuple[str, str]] = []
    target_program = None
    for program_name, program in programs.items():
        for qid, qrow in program.get("questions", {}).items():
            if question_id is not None and qid == question_id:
                target_program = program_name
                required_refs.extend((program_name, ref) for ref in _wb_refs(qrow.get("required_refs", ())))
                required_refs.extend((program_name, ref) for ref in _wb_refs(qrow.get("protected_refs", ())))
            elif question_id is None and str(qrow.get("question", "")).lower() == query:
                target_program = program_name
                required_refs.extend((program_name, ref) for ref in _wb_refs(qrow.get("required_refs", ())))
                required_refs.extend((program_name, ref) for ref in _wb_refs(qrow.get("protected_refs", ())))
        for key, row in program.get("records", {}).items():
            if row.get("protected"):
                required_refs.append((program_name, key))
    if target_program is None and len(programs) == 1:
        target_program = next(iter(programs))
    required: list[Mapping[str, Any]] = []
    selected_rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    gaps: list[str] = []
    frontier = list(required_refs)
    while frontier:
        program_name, reference = frontier.pop(0)
        program = programs.get(program_name, {})
        row = program.get("records", {}).get(reference)
        if row is None:
            row = next((item for item in program.get("records", {}).values() if reference in item.get("source_refs", ())), None)
        if row is None:
            gaps.append(reference)
            continue
        token = (program_name, row["key"])
        if token in selected_rows:
            continue
        selected_rows[token] = row
        required.append(_context_entry(program_name, row, reason="required-or-protected", relevance=2.0))
        frontier.extend((program_name, dep) for dep in row.get("dependencies", ()))
    candidates: list[tuple[float, str, str, Mapping[str, Any]]] = []
    for program_name, program in programs.items():
        if target_program is not None and program_name != target_program:
            continue
        for key, row in program.get("records", {}).items():
            if (program_name, key) in selected_rows:
                continue
            text = json.dumps(row.get("value", {}), sort_keys=True, ensure_ascii=False).lower()
            overlap = len(words.intersection(text.replace("_", " ").split()))
            relevance = float(overlap) / max(1, len(words))
            if overlap:
                candidates.append((relevance, program_name, key, row))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected = list(required)
    for relevance, program_name, key, row in candidates:
        if len(selected) >= maximum:
            break
        selected_rows[(program_name, key)] = row
        selected.append(_context_entry(program_name, row, reason="question-match", relevance=relevance))
        for dep in row.get("dependencies", ()):
            dep_row = programs.get(program_name, {}).get("records", {}).get(dep)
            if dep_row is None:
                gaps.append(dep)
            elif len(selected) < maximum and (program_name, dep) not in selected_rows:
                selected_rows[(program_name, dep)] = dep_row
                selected.append(_context_entry(program_name, dep_row, reason="dependency-closure", relevance=relevance * 0.9))
    program_row = programs.get(target_program, {}) if target_program else {}
    failed = [
        _plain(row)
        for row in workbench.get("approaches", {}).values()
        if row.get("status") in {"blocked", "failed", "woken"} and (target_program is None or row.get("program") == target_program)
    ]
    wakeups = [
        _plain(row)
        for row in workbench.get("wakeups", {}).values()
        if not row.get("consumed", False) and (target_program is None or row.get("program") == target_program)
    ]
    consumed = [
        row["wake_id"]
        for row in workbench.get("wakeups", {}).values()
        if row.get("consumed", False) and (target_program is None or row.get("program") == target_program)
    ]
    return {
        "schema": "cassifi.research-workbench-context.v1",
        "field_revision": state["state_sha256"],
        "required": required[:maximum],
        "required_omitted": max(0, len(required) - maximum),
        "selected": selected[:maximum],
        "gaps": _wb_unique(gaps),
        "continuation": _plain(program_row.get("continuation_refs", [])),
        "next_action": _plain(program_row.get("next_action")),
        "failed_approaches": failed,
        "wakeups": wakeups,
        "wakeups_consumed": consumed,
        "resource_policy": _plain(program_row.get("resource_policy", {})),
    }

def _record_forecast(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    forecast_id = _text(arguments.get("forecast_id"), "forecast_id")
    if forecast_id in state["forecasts"]:
        raise WorkspaceRuntimeError("forecast identity already exists")
    world_ref = _text(arguments.get("world_ref"), "world_ref")
    world_key = _resolve_key(state, world_ref)
    if world_key is None or state["objects"][world_key]["schema"] != WorldProgram.SCHEMA:
        raise WorkspaceRuntimeError("forecast requires a known world program")
    row = {
        "schema": "cassifi.workspace-forecast.v1",
        "forecast_id": forecast_id,
        "world_ref": world_key,
        "inputs": _plain(arguments.get("inputs", {})),
        "horizon": _plain(arguments.get("horizon", {})),
        "observable": _plain(arguments.get("observable", {})),
        "prediction": _plain(arguments.get("prediction")),
        "uncertainty": _plain(arguments.get("uncertainty", {})),
        "status": "unobserved",
        "outcome_id": None,
    }
    state["forecasts"][forecast_id] = row
    _refresh(state)
    _event(state, "workspace-forecast-recorded", {"forecast_id": forecast_id, "world_ref": world_key})
    return _plain(row)


def _record_outcome(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    outcome_id = _text(arguments.get("outcome_id"), "outcome_id")
    if outcome_id in state["outcomes"]:
        raise WorkspaceRuntimeError("outcome identity already exists")
    forecast_id = arguments.get("forecast_id")
    if forecast_id is not None and forecast_id not in state["forecasts"]:
        raise WorkspaceRuntimeError("outcome names an unknown forecast")
    row = {
        "schema": "cassifi.workspace-observed-outcome.v1",
        "outcome_id": outcome_id,
        "forecast_id": forecast_id,
        "artifact_ref": _text(arguments.get("artifact_ref"), "artifact_ref"),
        "observation": _plain(arguments.get("observation")),
        "conditions": _plain(arguments.get("conditions", {})),
        "origin": _plain(arguments.get("origin", {})),
    }
    state["outcomes"][outcome_id] = row
    if forecast_id is not None:
        state["forecasts"][forecast_id]["status"] = "observed"
        state["forecasts"][forecast_id]["outcome_id"] = outcome_id
    _refresh(state)
    _event(state, "workspace-outcome-recorded", {"outcome_id": outcome_id, "forecast_id": forecast_id})
    return _plain(row)


def _invalidate(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    reference = _text(arguments.get("reference"), "reference")
    key = _resolve_key(state, reference)
    if key is None:
        raise WorkspaceRuntimeError("invalidated object is unknown")
    reason = _text(arguments.get("reason"), "reason")
    affected: list[str] = []
    frontier = [reference, key]
    while frontier:
        dependency = frontier.pop()
        for candidate, row in state["objects"].items():
            if candidate in affected:
                continue
            if dependency in row["dependencies"]:
                state["dependency_status"][candidate]["valid"] = False
                state["dependency_status"][candidate]["invalidated_by"].append({"reference": key, "reason": reason})
                affected.append(candidate)
                frontier.extend((candidate, row["identifier"]))
    state["dependency_status"][key]["valid"] = False
    state["dependency_status"][key]["invalidated_by"].append({"reference": key, "reason": reason})
    _refresh(state)
    _event(state, "workspace-dependency-invalidated", {"reference": key, "affected": affected, "reason": reason})
    return {"reference": key, "affected": affected, "reason": reason}


def _control_branch(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _expected_revision(state, arguments)
    branch_id = _text(arguments.get("branch_id"), "branch_id")
    branch = state["branches"].get(branch_id)
    if not isinstance(branch, MutableMapping):
        raise WorkspaceRuntimeError("workspace branch is unknown")
    action = str(arguments.get("action"))
    if action == "pause" and branch["status"] == "running":
        branch["status"] = "paused"
    elif action == "resume" and branch["status"] == "paused":
        branch["status"] = "running"
    elif action == "cancel" and branch["status"] in {"running", "paused"}:
        branch["status"] = "cancelled"
    else:
        raise WorkspaceRuntimeError("workspace branch control transition is invalid")
    _refresh(state)
    _event(state, "workspace-branch-controlled", {"branch_id": branch_id, "action": action, "status": branch["status"]})
    return _plain(branch)


def inspect(
    state: Mapping[str, Any],
    *,
    principal: str,
    category: str = "objects",
    offset: int = 0,
    limit: int = 64,
) -> Mapping[str, Any]:
    offset = _integer(offset, "offset")
    limit = _integer(limit, "limit", minimum=1)
    if limit > _limit(state, "max_page"):
        raise WorkspaceRuntimeError("workspace page exceeds its bound")
    if category == "objects":
        rows = [
            {**_plain(row), "access": _plain(state["access"][key]), "dependency_status": _plain(state["dependency_status"][key])}
            for key, row in sorted(state["objects"].items())
            if _can_read(state, key, principal)
        ]
    elif category in {"guidance", "branches", "comparisons", "retained", "forecasts", "outcomes"}:
        rows = [_plain(row) for _, row in sorted(state[category].items())]
    elif category == "workbench":
        rows = [_workbench_view(state, name) for name in sorted(state.get("workbench", {}).get("programs", {}))]
    elif category == "context":
        rows = [_workbench_view(state, name) for name in sorted(state.get("workbench", {}).get("programs", {}))]
    elif category == "events":
        rows = [_plain(row) for row in state["events"]]
    else:
        raise WorkspaceRuntimeError("workspace inspection category is unsupported")
    selected = rows[offset : offset + limit]
    return {
        "schema": "cassifi.research-workspace-view.v1",
        "workspace_id": state["identity"]["workspace_id"],
        "owner_id": state["identity"]["owner_id"],
        "principal": principal,
        "field_revision": state["state_sha256"],
        "revision": int(state["revision"]),
        "phase": state["phase"],
        "category": category,
        "rows": selected,
        "page": {"offset": offset, "limit": limit, "returned": len(selected), "total": len(rows)},
    }


def handle(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    operation = str(arguments.get("operation", ""))
    if operation == "inspect":
        return inspect(
            state,
            principal=_text(arguments.get("principal", state["identity"]["principal"]), "principal"),
            category=str(arguments.get("category", "objects")),
            offset=int(arguments.get("offset", 0)),
            limit=int(arguments.get("limit", 64)),
        )
    if operation in {"sync-workbench", "sync"}:
        return _sync_workbench(state, arguments)
    if operation == "select-context":
        return select_context(
            state,
            arguments.get("question", ""),
            arguments.get("question_id"),
            int(arguments.get("maximum", 64)),
        )
    if operation in {"record-approach", "record-failure"}:
        return _record_approach(state, arguments)
    if operation in {"dependency-change", "change-dependency"}:
        return _dependency_change(state, arguments)
    if operation == "admit-record":
        return _admit_record(state, arguments)
    if operation == "propose":
        return _propose(state, arguments)
    if operation == "investigate":
        return _investigate(state, arguments)
    if operation == "settle-branch":
        return _settle_branch(state, arguments)
    if operation == "compare":
        return _compare(state, arguments)
    if operation == "retain":
        return _retain(state, arguments)
    if operation == "record-forecast":
        return _record_forecast(state, arguments)
    if operation == "record-outcome":
        return _record_outcome(state, arguments)
    if operation == "invalidate":
        return _invalidate(state, arguments)
    if operation == "control-branch":
        return _control_branch(state, arguments)
    if operation == "pause":
        _expected_revision(state, arguments)
        state["phase"] = "paused"
        _refresh(state)
        _event(state, "workspace-paused", {})
        return {"status": "paused", "field_revision": state["state_sha256"]}
    if operation == "resume":
        _expected_revision(state, arguments)
        state["phase"] = "active"
        _refresh(state)
        _event(state, "workspace-resumed", {})
        return {"status": "active", "field_revision": state["state_sha256"]}
    raise WorkspaceRuntimeError("workspace operation is unsupported")


def initial_state(
    *,
    owner_id: str,
    member_id: str,
    workspace_id: str,
    principal: str,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    resolved_limits = dict(DEFAULT_LIMITS)
    for name, value in dict(limits or {}).items():
        if name not in resolved_limits:
            raise WorkspaceRuntimeError(f"unknown workspace limit {name!r}")
        resolved_limits[name] = _integer(value, name, minimum=1)
    state: dict[str, Any] = {
        "schema": RUNTIME_SCHEMA,
        "identity": {
            "owner_id": _text(owner_id, "owner_id"),
            "member_id": _text(member_id, "member_id"),
            "workspace_id": _text(workspace_id, "workspace_id"),
            "principal": _text(principal, "principal"),
        },
        "objects": {},
        "latest": {},
        "access": {},
        "guidance": {},
        "branches": {},
        "comparisons": {},
        "workbench": _workbench_template(),
        "retained": {},
        "forecasts": {},
        "outcomes": {},
        "dependency_status": {},
        "events": [],
        "counters": {"event": 1},
        "limits": resolved_limits,
        "phase": "active",
        "revision": 0,
        "state_sha256": "0" * 64,
        "last_result": None,
        "ledger": {"operations": 0},
    }
    state["state_sha256"] = digest_value(_revision_body(state))
    canonical_json_bytes(state)
    return state


def advance(
    state: Mapping[str, Any],
    arguments: Mapping[str, Any],
    quantum: int,
) -> tuple[dict[str, Any], str, int, Mapping[str, Any], tuple[Mapping[str, Any], ...]]:
    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA:
        raise WorkspaceRuntimeError("research workspace state is invalid")
    if not isinstance(arguments, Mapping):
        raise WorkspaceRuntimeError("workspace arguments must be a mapping")
    _integer(quantum, "quantum", minimum=1)
    current = copy.deepcopy(dict(state))
    operation = str(arguments.get("operation", ""))
    read_only = operation in {"inspect", "select-context"}
    if not read_only:
        _ensure_workbench(current)
    event_start = len(current["events"])
    result = handle(current, arguments)
    if not read_only:
        current["last_result"] = _plain(result)
        current["ledger"]["operations"] += 1
    status = "blocked" if current["phase"] == "paused" else "yield"
    events = tuple(copy.deepcopy(current["events"][event_start:]))
    canonical_json_bytes(current)
    return current, status, 1, result, events


__all__ = [
    "DEFAULT_LIMITS",
    "RESULT_SCHEMA",
    "RUNTIME_SCHEMA",
    "WorkspaceRuntimeError",
    "advance",
    "handle",
    "initial_state",
    "inspect",
    "select_context",
]
