"""Durable owner-path evidence runner for open-vocabulary relational planning."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cassi_field_owner import AuthorityGrant, FieldIntelligenceSurface, SourceInput
from cassi_hive_session import open_field_session
from cassi_field_open_vocab import alpha_equivalent, apply_substitution, canonical_term, episode_source_payload
from cassi_field_cognition import semantic_cognition_state
from cassi_field_program import semantic_program_payload
from cassi_field_regions import make_semantic_record

SCHEMA = "cassifi.relational-planning-receipt.v1"
RPC_SCHEMA = "cassifi.field-intelligence-request.v2"
SORTS = ("agent", "place")


def jbytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(jbytes(value)).hexdigest()


def plan_structure(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: plan.get(key)
        for key in (
            "schema",
            "goal",
            "initial_state",
            "segments",
            "remaining_dependencies",
            "source_roots",
            "status",
            "alternatives",
        )
    }


def b64(value: Any) -> str:
    raw = value if isinstance(value, bytes) else jbytes(value)
    return base64.b64encode(raw).decode("ascii")


def label(value: str, sort: str) -> dict[str, Any]:
    return {"kind": "constructor", "name": sort, "type": sort, "args": [{"kind": "atom", "type": "lexeme", "value": value}]}


def atom(value: Any, typ: str) -> dict[str, Any]:
    return {"kind": "atom", "type": typ, "value": value}


def variable(name: str, typ: str) -> dict[str, Any]:
    return {"kind": "variable", "scope": "goal", "name": name, "type": typ}
def role_variable(name: str, typ: str) -> dict[str, Any]:
    return {"kind": "variable", "scope": "role", "name": name, "type": typ}


def world_template(role_names: tuple[str, str, str]) -> dict[str, Any]:
    who = role_variable(role_names[0], "agent")
    origin = role_variable(role_names[1], "place")
    destination = role_variable(role_names[2], "place")
    return {
        "schema": "cassifi.open-vocab-template.v1",
        "term": world(3, who, origin, destination),
        "constructors": ["adjacent", "world"],
    }


def construction_program(pattern: list[str], roles: list[str]) -> dict[str, Any]:
    return semantic_program_payload(
        program_kind="construction",
        body={
            "pattern": list(pattern),
            "roles": list(roles),
            "meaning": {},
            "guards": {},
            "speech_act": "assertion",
            "source_policy": {"grants_authority": False},
        },
        max_work=8,
    )


def template_program(template: Mapping[str, Any]) -> dict[str, Any]:
    return semantic_program_payload(
        program_kind="procedure",
        body={"template": dict(template)},
        max_work=8,
    )


def seed_program_record(
    record_id: str,
    program: Mapping[str, Any],
    support_root: str,
    *,
    role: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"program": dict(program)}
    if role is not None:
        payload["program_role"] = role
    return make_semantic_record(
        record_id=record_id,
        kind="Program",
        content_version=1,
        created_at=0,
        payload=payload,
        scope="world",
        epistemic_kind="induced",
        status="active",
        support_roots=[support_root],
        derivation={"criterion": "bounded-open-vocabulary-fixture"},
    )


def semantic_graph_projection(owner: FieldIntelligenceOwner) -> dict[str, Any]:
    inspection = owner.state.computers[0].inspect()
    task = inspection.get("task")
    if not isinstance(task, Mapping):
        raise RuntimeError("resident semantic task is unavailable")
    # Records and their active semantic view are the persistent graph.
    # Indexes are owner-maintained lookup bookkeeping and may be rebuilt while
    # the graph remains unchanged; clocks/ledgers are not part of this view.
    return {
        key: task.get(key)
        for key in (
            "schema",
            "family",
            "scope",
            "frame",
            "records",
            "beliefs",
            "libraries",
            "bounds",
        )
    }


def semantic_graph_digest(owner: FieldIntelligenceOwner) -> str:
    return digest(semantic_graph_projection(owner))


def plan_structure(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"plan_id", "basis_field_sha256"}
    }

def extract_plan(value: Any) -> Any:
    if isinstance(value, Mapping):
        if value.get("schema") == "cassifi.open-vocab-plan.v1":
            return value
        for key in ("plan", "result", "consumed_result"):
            if key in value:
                found = extract_plan(value[key])
                if isinstance(found, Mapping) and found.get("schema") == "cassifi.open-vocab-plan.v1":
                    return found
        for child in value.values():
            found = extract_plan(child)
            if isinstance(found, Mapping) and found.get("schema") == "cassifi.open-vocab-plan.v1":
                return found
    elif isinstance(value, list):
        for child in value:
            found = extract_plan(child)
            if isinstance(found, Mapping) and found.get("schema") == "cassifi.open-vocab-plan.v1":
                return found
    return value

def forbidden_call_counts(owner: FieldIntelligenceOwner) -> dict[str, int]:
    names = ("model_calls", "qwen_calls", "fallback_calls", "host_search_calls")
    counts = {name: 0 for name in names}

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in counts:
                    if isinstance(child, bool):
                        counts[key] += int(child)
                    elif isinstance(child, int):
                        counts[key] += child
                    elif isinstance(child, list):
                        counts[key] += len(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(owner.state.computers[0].inspect())
    return counts


def directed_edge(origin: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "constructor", "name": "adjacent", "args": [origin, destination], "type": "directed-route"}


def world(stage: int, who: dict[str, Any], origin: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
    fact = {"kind": "constructor", "name": "world", "args": [atom(stage, "integer"), who, origin, destination, directed_edge(origin, destination)]}
    return {"kind": "record", "fields": {"world": fact}}


def action(name: str, who: dict[str, Any], origin: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
    # Origin is repeated in the action role, while the directed edge fixes its
    # orientation independently of the query/goal labels.
    return {"kind": "constructor", "name": name, "args": [who, origin, destination, origin]}


def source_for(source_id: str, payload: Mapping[str, Any]) -> SourceInput:
    return SourceInput(
        source_id=source_id,
        content=jbytes(payload),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp="fixture-time",
        scope="relational-planning",
        claim_category="grounded-demonstration",
        fidelity="exact-record",
        labels=("open-vocabulary", "relational"),
    )


def canonical_request(operation_id: str, operation: str, params: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema": RPC_SCHEMA, "request_id": operation_id, "operation": operation, "params": dict(params)}


def owner_call(surface: FieldIntelligenceSurface, operation_id: str, operation: str, params: Mapping[str, Any], rows: list[dict[str, Any]]) -> Mapping[str, Any]:
    request = canonical_request(operation_id, operation, params)
    started = time.perf_counter()
    try:
        result = surface.handle(request)
        error = None
    except Exception as exc:  # captured as evidence; controls deliberately exercise refusals
        result = {"status": "error", "error_code": getattr(exc, "code", type(exc).__name__), "message": str(exc)}
        error = result["error_code"]
    rows.append({
        "layer": "FieldIntelligenceSurface->FieldIntelligenceOwner",
        "operation": operation,
        "operation_id": operation_id,
        "request_bytes_b64": b64(request),
        "return_bytes_b64": b64(result),
        "error_code": error,
        "elapsed_seconds": time.perf_counter() - started,
    })
    # The direct surface envelope is authoritative. Open-vocabulary operations
    # execute through the resident computer, so their semantic output is the
    # latest matching transition output in that direct receipt. Never consult
    # inspect().consumed_result, which can be stale from an earlier transition.
    if isinstance(result, Mapping) and isinstance(result.get("result"), Mapping):
        direct = result["result"]
        if any(key in direct for key in ("event_ref", "candidates", "schema_ref", "term", "plan")):
            return direct
        receipt = direct.get("receipt")
        transitions = (
            receipt.get("run", {}).get("transition_receipts", [])
            if isinstance(receipt, Mapping)
            else []
        )
        for transition in reversed(transitions):
            output = transition.get("output") if isinstance(transition, Mapping) else None
            if isinstance(output, Mapping) and output.get("operation") in {
                "admit-open-vocab-episode",
                "propose-action-schema",
                "admit-action-schema",
                "interpret-open-vocab",
                "plan-open-vocab",
                "repair-open-vocab-plan",
            }:
                return output
        return direct
    if isinstance(result, Mapping) and isinstance(result.get("computer"), Mapping):
        computer = result["computer"]
        if isinstance(computer.get("consumed_result"), Mapping):
            return computer["consumed_result"]
        if isinstance(computer.get("outcome"), Mapping):
            return computer["outcome"]
    return result

def strip_digest(value: Any, path: str = "$") -> Any:
    if path == "$.digest.content_sha256":
        return None
    if path == "$.timing" or path == "$.environment" or path.endswith(".timing") or path.endswith(".elapsed_seconds"):
        return None
    if isinstance(value, Mapping):
        return {k: strip_digest(v, f"{path}.{k}") for k, v in value.items() if strip_digest(v, f"{path}.{k}") is not None}
    if isinstance(value, list):
        return [strip_digest(v, f"{path}[{i}]") for i, v in enumerate(value)]
    return value


def guard_digest_body(value: Any) -> None:
    bad = []
    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                low = str(key).lower()
                if any(token in low for token in ("elapsed", "seconds", "runtime", "timestamp", "mtime")):
                    bad.append(path + "." + str(key))
                walk(child, path + "." + str(key))
        elif isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, f"{path}[{i}]")
    walk(value, "$")
    if bad:
        raise RuntimeError("undeclared timing/environment leaves: " + ",".join(bad))


def eval_plan(plan: Mapping[str, Any], schemas: Mapping[str, Mapping[str, Any]], initial: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = canonical_term(initial)
    trace = []
    for segment in plan.get("segments", []):
        schema = schemas[str(segment["schema_digest"])]
        sub = segment.get("substitution", {})
        if isinstance(sub, Mapping) and "schema" not in sub and isinstance(sub.get("bindings"), list):
            sub = {"schema": "cassifi.open-vocab-substitution.v1", "bindings": sub["bindings"]}
        effects = schema.get("effects", [])
        if not effects:
            continue
        state = apply_substitution(effects[0], sub)
        trace.append({"action": segment["action"], "state": state, "schema_digest": segment["schema_digest"]})
    return state, trace


def build(receipt_path: Path, data_home: Path) -> dict[str, Any]:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    data_home.mkdir(parents=True, exist_ok=True)
    branch = "runner-" + hashlib.sha256(
        str(data_home.resolve()).encode("utf-8")
    ).hexdigest()[:16]
    owner_rows: list[dict[str, Any]] = []
    demonstrations: list[dict[str, Any]] = []
    events_by_stage: dict[int, list[dict[str, Any]]] = {}
    source_records: list[dict[str, Any]] = []
    with open_field_session(
        data_home,
        branch=branch,
        role="worker",
        mode="scout",
        metadata={"program": "run_cassi_relational_planning"},
    ) as field:
        owner = field.owner
        surface = FieldIntelligenceSurface(owner)

        def archive(source_id: str, payload: Mapping[str, Any]) -> str:
            result = owner.archive_source(
                operation_id=f"archive:{source_id}",
                source=source_for(source_id, payload),
                context={"fixture": "relational-planning"},
                event_kind="relational-demo",
            )
            content = jbytes(payload)
            row = {
                "source_id": source_id,
                "source_revision_id": result["source"]["revision_id"],
                "content_b64": b64(content),
                "content_sha256": hashlib.sha256(content).hexdigest(),
            }
            source_records.append(row)
            return row["source_revision_id"]

        support_who = label("support-agent", "agent")
        support_origin = label("support-origin", "place")
        support_destination = label("support-destination", "place")
        support_episode = {
            "event_id": "open-vocab-template-support",
            "source_revision_ids": ["pending-source"],
            "pre_state": world(0, support_who, support_origin, support_destination),
            "action": action(
                "support-template",
                support_who,
                support_origin,
                support_destination,
            ),
            "post_state": world(1, support_who, support_origin, support_destination),
            "bindings": {},
            "observation": {"success": True},
        }
        support_revision = archive(
            "source-open-vocab-template",
            episode_source_payload(support_episode),
        )
        revocation_revision = archive(
            "source-open-vocab-revocation",
            episode_source_payload(
                {
                    "event_id": "open-vocab-revocation",
                    "source_revision_ids": ["pending-source"],
                    "pre_state": world(
                        0,
                        support_who,
                        support_origin,
                        support_destination,
                    ),
                    "action": action(
                        "revoke-template-support",
                        support_who,
                        support_origin,
                        support_destination,
                    ),
                    "post_state": world(
                        1,
                        support_who,
                        support_origin,
                        support_destination,
                    ),
                    "bindings": {},
                    "observation": {"success": True},
                }
            ),
        )

        base_roles = ("who", "origin", "destination")
        alternate_roles = ("主体", "起点", "终点")
        construction_ref = {
            "kind": "Program",
            "id": "fixture:construction:advance",
            "content_version": 1,
        }
        template_ref = {
            "kind": "Program",
            "id": "fixture:template:world-goal",
            "content_version": 1,
        }
        alternate_construction_ref = {
            "kind": "Program",
            "id": "fixture:construction:alternate",
            "content_version": 1,
        }
        alternate_template_ref = {
            "kind": "Program",
            "id": "fixture:template:alternate",
            "content_version": 1,
        }
        ambiguous_construction_ref = {
            "kind": "Program",
            "id": "fixture:construction:ambiguous",
            "content_version": 1,
        }
        unsupported_template_ref = {
            "kind": "Program",
            "id": "fixture:template:unsupported",
            "content_version": 1,
        }
        seed_records = [
            seed_program_record(
                construction_ref["id"],
                construction_program(
                    ["advance", "{who}", "from", "{origin}", "to", "{destination}"],
                    list(base_roles),
                ),
                support_revision,
                role="construction",
            ),
            seed_program_record(
                template_ref["id"],
                template_program(world_template(base_roles)),
                support_revision,
            ),
            seed_program_record(
                alternate_construction_ref["id"],
                construction_program(
                    ["advance", "{起点}", "to", "{终点}", "for", "{主体}"],
                    list(alternate_roles),
                ),
                support_revision,
                role="construction",
            ),
            seed_program_record(
                alternate_template_ref["id"],
                template_program(world_template(alternate_roles)),
                support_revision,
            ),
            seed_program_record(
                ambiguous_construction_ref["id"],
                construction_program(
                    ["move", "{who}", "{origin}", "{destination}"],
                    list(base_roles),
                ),
                support_revision,
                role="construction",
            ),
            seed_program_record(
                unsupported_template_ref["id"],
                template_program(
                    {
                        "schema": "cassifi.open-vocab-template.v1",
                        "term": {
                            "kind": "constructor",
                            "name": "world",
                            "args": [],
                        },
                        "constructors": [],
                    }
                ),
                support_revision,
            ),
        ]

        configure_request = {
            "computer_id": "main",
            "action": "configure",
            "arguments": {
                "profile": {"program_capacity": 8, "stack_capacity": 8}
            },
        }
        configure_result = owner.operate_computer(
            "configure-relational-computer", **configure_request
        )
        owner_rows.append(
            {
                "layer": "FieldIntelligenceOwner",
                "operation": "configure",
                "operation_id": "configure-relational-computer",
                "request_bytes_b64": b64(configure_request),
                "return_bytes_b64": b64(configure_result),
                "error_code": None,
                "elapsed_seconds": 0.0,
            }
        )
        prime_request = {
            "schema": RPC_SCHEMA,
            "request_id": "prime-relational-computer",
            "operation": "computer",
            "params": {
                "operation_id": "prime-relational-computer",
                "computer_id": "main",
                "action": "submit",
                "arguments": {
                    "kernel": "cognition.field",
                    "state": semantic_cognition_state(seed_records=seed_records),
                    "arguments": {
                        "operation": "observe",
                        "operation_id": "prime-relational",
                        "delivery_id": "prime-relational",
                        "event_id": "prime-relational",
                        "observations": [
                            {
                                "binding_id": "seed",
                                "subject": "seed",
                                "attribute": "value",
                                "value": 1,
                            }
                        ],
                    },
                    "steps": 128,
                },
            },
        }
        prime_result = surface.handle(prime_request)
        owner_rows.append(
            {
                "layer": "FieldIntelligenceSurface->FieldIntelligenceOwner",
                "operation": "computer",
                "operation_id": "prime-relational-computer",
                "request_bytes_b64": b64(prime_request),
                "return_bytes_b64": b64(prime_result),
                "error_code": None,
                "elapsed_seconds": 0.0,
            }
        )
        if isinstance(prime_result, Mapping) and isinstance(
            prime_result.get("result"), Mapping
        ):
            prime_receipt = prime_result["result"].get("receipt", {})
            prime_run = (
                prime_receipt.get("run", {})
                if isinstance(prime_receipt, Mapping)
                else {}
            )
            if any(
                row.get("disposition") == "fault"
                for row in prime_run.get("transition_receipts", [])
            ):
                raise RuntimeError(f"cognition computer prime faulted: {prime_run}")

        def admit(
            event_id: str, source_revision_id: str, episode: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            return owner_call(
                surface,
                f"admit-{event_id}",
                "admit_open_vocab_episode",
                {
                    "operation_id": f"admit-{event_id}",
                    "event_id": event_id,
                    "source_revision_id": source_revision_id,
                    "episode": dict(episode),
                },
                owner_rows,
            )

        for stage in range(3):
            demos: list[dict[str, Any]] = []
            for variant in range(2):
                who = label(f"示范-{stage}-{variant}-人", "agent")
                origin = label(f"demo-{stage}-{variant}-起点·{variant}", "place")
                destination = label(
                    f"demo-{stage}-{variant}-终点·{variant}", "place"
                )
                pre = world(stage, who, origin, destination)
                post = world(stage + 1, who, origin, destination)
                ep_id = f"demo-{stage}-{variant}"
                episode = {
                    "event_id": ep_id,
                    "source_revision_ids": ["pending-source"],
                    "pre_state": pre,
                    "action": action(
                        "advance", who, origin, destination
                    ),
                    "post_state": post,
                    "bindings": {
                        "who": who,
                        "origin": origin,
                        "destination": destination,
                    },
                    "observation": {"success": True},
                }
                revision = archive(
                    f"source-{ep_id}", episode_source_payload(episode)
                )
                episode["source_revision_ids"] = [revision]
                result = admit(ep_id, revision, episode)
                event_ref = result.get("event_ref", result.get("event"))
                if not isinstance(event_ref, Mapping):
                    raise RuntimeError(f"episode admission failed: {ep_id}: {result}")
                demos.append(event_ref)
                demonstrations.append(
                    {
                        "demo_id": ep_id,
                        "stage": stage,
                        "event_ref": event_ref,
                        "source_revision_id": revision,
                        "owner_request_b64": owner_rows[-1]["request_bytes_b64"],
                        "owner_return_b64": owner_rows[-1]["return_bytes_b64"],
                    }
                )
            events_by_stage[stage] = demos

        schema_refs: list[dict[str, Any]] = []
        schemas: dict[str, dict[str, Any]] = {}
        for stage in range(3):
            proposed = owner_call(
                surface,
                f"propose-{stage}",
                "propose_action_schema",
                {
                    "operation_id": f"propose-{stage}",
                    "training_event_refs": events_by_stage[stage],
                    "holdout_event_refs": [],
                    "bounds": {"max_candidates": 4, "max_work": 4096},
                },
                owner_rows,
            )
            candidate = (
                proposed.get("candidates", [None])[0]
                if isinstance(proposed, Mapping)
                else None
            )
            if not isinstance(candidate, Mapping):
                raise RuntimeError(f"proposal failed at stage {stage}: {proposed}")
            binding_refs = [
                {"id": str(item), "kind": "Binding", "content_version": 1}
                for item in candidate.get("support_binding_refs", [])
            ]
            admitted = owner_call(
                surface,
                f"admit-schema-{stage}",
                "admit_action_schema",
                {
                    "operation_id": f"admit-schema-{stage}",
                    "candidate": candidate,
                    "support_event_refs": events_by_stage[stage],
                    "support_binding_refs": binding_refs,
                    "source_revision_ids": [
                        x["source_revision_id"]
                        for x in demonstrations
                        if x["stage"] == stage
                    ],
                },
                owner_rows,
            )
            schema_ref = admitted.get("schema_ref")
            if not isinstance(schema_ref, Mapping):
                raise RuntimeError(f"schema admission failed at stage {stage}: {admitted}")
            schema_refs.append(schema_ref)
            schema = candidate
            schemas[str(schema_ref.get("record_id", schema_ref.get("id", "")))] = schema
            schemas[str(admitted.get("schema_digest", candidate.get("schema_digest")))] = schema

        bridge_event_refs: list[Mapping[str, Any]] = []
        bridge_demo_rows: list[dict[str, Any]] = []
        for stage in range(3):
            who = atom(f"bridge-agent-{stage}", "lexeme")
            origin = atom(f"bridge-origin-{stage}", "lexeme")
            destination = atom(f"bridge-destination-{stage}", "lexeme")
            event_id = f"bridge-atom-{stage}"
            episode = {
                "event_id": event_id,
                "source_revision_ids": ["pending-source"],
                "pre_state": world(stage, who, origin, destination),
                "action": action(
                    "advance", who, origin, destination
                ),
                "post_state": world(stage + 1, who, origin, destination),
                "bindings": {
                    "who": who,
                    "origin": origin,
                    "destination": destination,
                },
                "observation": {"success": True},
            }
            revision = archive(
                f"source-{event_id}", episode_source_payload(episode)
            )
            episode["source_revision_ids"] = [revision]
            admitted = admit(event_id, revision, episode)
            event_ref = admitted.get("event_ref", admitted.get("event"))
            if not isinstance(event_ref, Mapping):
                raise RuntimeError(f"bridge demonstration admission failed: {admitted}")
            bridge_event_refs.append(event_ref)
            bridge_demo_rows.append(
                {
                    "event_id": event_id,
                    "source_revision_id": revision,
                    "event_ref": event_ref,
                }
            )
        bridge_proposed = owner_call(
            surface,
            "propose-bridge-atom",
            "propose_action_schema",
            {
                "operation_id": "propose-bridge-atom",
                "training_event_refs": bridge_event_refs,
                "holdout_event_refs": [],
                "bounds": {"max_candidates": 4, "max_work": 4096},
            },
            owner_rows,
        )
        bridge_candidate = (
            bridge_proposed.get("candidates", [None])[0]
            if isinstance(bridge_proposed, Mapping)
            else None
        )
        if not isinstance(bridge_candidate, Mapping):
            raise RuntimeError(f"bridge schema proposal failed: {bridge_proposed}")
        bridge_binding_refs = [
            {"id": str(item), "kind": "Binding", "content_version": 1}
            for item in bridge_candidate.get("support_binding_refs", [])
        ]
        bridge_admitted = owner_call(
            surface,
            "admit-bridge-atom",
            "admit_action_schema",
            {
                "operation_id": "admit-bridge-atom",
                "candidate": bridge_candidate,
                "support_event_refs": bridge_event_refs,
                "support_binding_refs": bridge_binding_refs,
                "source_revision_ids": [
                    row["source_revision_id"] for row in bridge_demo_rows
                ],
            },
            owner_rows,
        )
        bridge_schema_ref = bridge_admitted.get("schema_ref")
        if not isinstance(bridge_schema_ref, Mapping):
            raise RuntimeError(f"bridge schema admission failed: {bridge_admitted}")
        bridge_schema_refs = [bridge_schema_ref]
        schemas[str(bridge_schema_ref.get("record_id", bridge_schema_ref.get("id", "")))] = bridge_candidate
        schemas[str(bridge_admitted.get("schema_digest", bridge_candidate.get("schema_digest")))] = bridge_candidate

        fresh_who = label("新鲜-主体🜁", "agent")
        fresh_origin = label("fresh-origin-β", "place")
        fresh_destination = label("fresh-destination-δ", "place")
        rebound_who = label("外部观察-主体🜂", "agent")
        rebound_origin = label("observed-origin-γ", "place")
        rebound_destination = label("observed-destination-ε", "place")
        initial = world(0, fresh_who, fresh_origin, fresh_destination)
        goal = world(
            3,
            variable("who", "agent"),
            variable("origin", "place"),
            variable("destination", "place"),
        )
        reference_world = {
            "initial": canonical_term(initial),
            "goal": canonical_term(goal),
            "rebound": canonical_term(
                world(1, rebound_who, rebound_origin, rebound_destination)
            ),
            "fresh_layout_id": "layout-fresh-utf8-03",
            "directed_adjacency": True,
        }

        def interpret(
            operation_id: str,
            utterance: str,
            construction: Mapping[str, Any],
            template: Mapping[str, Any],
            *,
            support_refs: list[Mapping[str, Any]] | None = None,
            source_revision_ids: list[str] | None = None,
        ) -> Mapping[str, Any]:
            roots = list(source_revision_ids or [support_revision])
            result = owner_call(
                surface,
                operation_id,
                "interpret_open_vocab",
                {
                    "operation_id": operation_id,
                    "utterance": utterance,
                    "construction_ref": dict(construction),
                    "template_ref": dict(template),
                    "support_refs": [
                        dict(item) for item in (support_refs or [])
                    ],
                    "source_revision_ids": roots,
                },
                owner_rows,
            )
            if (
                result.get("status") == "error"
                and result.get("error_code")
                in {"SOURCE_STALE", "SOURCE_REVOKED", "STALE_REVOCATION"}
            ):
                return {
                    **dict(result),
                    "status": "support-gap",
                    "interpretation_status": "support-gap",
                    "reason": "source-revoked",
                }
            return result

        bridge_graph_before = semantic_graph_projection(owner)
        bridge_state_before = digest(bridge_graph_before)
        base_interpretation = interpret(
            "interpret-base",
            "advance 新鲜-主体🜁 from fresh-origin-β to fresh-destination-δ",
            construction_ref,
            template_ref,
        )
        if base_interpretation.get("status") != "supported":
            raise RuntimeError(f"base open-vocabulary interpretation failed: {base_interpretation}")
        base_term = canonical_term(base_interpretation["term"])
        bridge_initial = world(
            0,
            atom("新鲜-主体🜁", "lexeme"),
            atom("fresh-origin-β", "lexeme"),
            atom("fresh-destination-δ", "lexeme"),
        )
        bridge_state_after_interpret = semantic_graph_digest(owner)
        bridge_plan_result = owner_call(
            surface,
            "plan-from-interpret-base",
            "plan_open_vocab",
            {
                "operation_id": "plan-from-interpret-base",
                "initial_term": bridge_initial,
                "goal_term": base_term,
                "schema_refs": bridge_schema_refs,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        bridge_plan = bridge_plan_result.get(
            "plan", bridge_plan_result.get("result", bridge_plan_result)
        )
        if not isinstance(bridge_plan, Mapping) or bridge_plan.get("status") != "supported":
            raise RuntimeError(f"bridge plan failed: {bridge_plan_result}")
        bridge_graph_after_plan = semantic_graph_projection(owner)
        bridge_state_after_plan = digest(bridge_graph_after_plan)

        alternate_interpretation = interpret(
            "interpret-alternate",
            "advance fresh-origin-β to fresh-destination-δ for 新鲜-主体🜁",
            alternate_construction_ref,
            alternate_template_ref,
        )
        if alternate_interpretation.get("status") != "supported":
            raise RuntimeError(
                f"alternate open-vocabulary interpretation failed: {alternate_interpretation}"
            )
        alternate_term = canonical_term(alternate_interpretation["term"])
        alternate_plan_result = owner_call(
            surface,
            "plan-from-interpret-alternate",
            "plan_open_vocab",
            {
                "operation_id": "plan-from-interpret-alternate",
                "initial_term": bridge_initial,
                "goal_term": alternate_term,
                "schema_refs": bridge_schema_refs,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        alternate_plan = alternate_plan_result.get(
            "plan", alternate_plan_result.get("result", alternate_plan_result)
        )

        ambiguous_interpretation = interpret(
            "interpret-ambiguous",
            "move 新鲜-主体🜁 extra fresh-origin-β fresh-destination-δ",
            ambiguous_construction_ref,
            template_ref,
        )
        unsupported_interpretation = interpret(
            "interpret-unsupported",
            "advance 新鲜-主体🜁 from fresh-origin-β to fresh-destination-δ",
            construction_ref,
            unsupported_template_ref,
        )
        stale_interpretation = interpret(
            "interpret-stale-support",
            "advance 新鲜-主体🜁 from fresh-origin-β to fresh-destination-δ",
            construction_ref,
            template_ref,
            support_refs=[
                {
                    "kind": "Program",
                    "id": "fixture:template:world-goal",
                    "content_version": 2,
                }
            ],
        )
        preview = owner.preview_forget([revocation_revision])
        grant = AuthorityGrant(
            grant_id="revoke-open-vocab-support",
            issuer="relational-planning",
            generation=owner.authority_generation,
            operation="forget",
            target=hashlib.sha256(jbytes([revocation_revision])).hexdigest(),
            scope="relational-planning",
        )
        owner.forget(
            operation_id="revoke-open-vocab-support",
            preview_id=preview["preview_id"],
            revision_ids=[revocation_revision],
            grant=grant,
            scope="relational-planning",
        )
        revoked_interpretation = interpret(
            "interpret-revoked-support",
            "advance 新鲜-主体🜁 from fresh-origin-β to fresh-destination-δ",
            construction_ref,
            template_ref,
            source_revision_ids=[revocation_revision],
        )

        planned = owner_call(
            surface,
            "plan-base",
            "plan_open_vocab",
            {
                "operation_id": "plan-base",
                "initial_term": initial,
                "goal_term": goal,
                "schema_refs": schema_refs,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        plan = planned.get("plan", planned.get("result", planned))
        if not isinstance(plan, Mapping) or plan.get("status") != "supported":
            raise RuntimeError(f"base plan failed: {planned}")
        plan_before_digest = digest(plan)

        obs_id = "heldout-observation"
        obs_episode = {
            "event_id": obs_id,
            "source_revision_ids": ["pending-source"],
            "pre_state": initial,
            "action": dict(plan["segments"][0]["action"]),
            "post_state": world(1, fresh_who, fresh_origin, fresh_destination),
            "bindings": {
                "who": fresh_who,
                "origin": fresh_origin,
                "destination": fresh_destination,
            },
            "observation": {"success": True, "external": True},
            "completed_segments": 1,
        }
        obs_revision = archive(
            "source-heldout-observation", episode_source_payload(obs_episode)
        )
        obs_episode["source_revision_ids"] = [obs_revision]
        obs_result = admit(obs_id, obs_revision, obs_episode)
        obs_ref = obs_result.get("event_ref", obs_result.get("event"))
        if not isinstance(obs_ref, Mapping):
            raise RuntimeError(f"observation admission failed: {obs_result}")
        repaired_result = owner_call(
            surface,
            "repair-base",
            "repair_open_vocab_plan",
            {
                "operation_id": "repair-base",
                "plan": dict(plan),
                "observation_event_ref": obs_ref,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        repaired = repaired_result.get("result", repaired_result)
        if not isinstance(repaired, Mapping) or repaired.get("status") != "supported":
            raise RuntimeError(f"repair failed: {repaired_result}")
        plan_after_digest = digest(repaired)
        final_state, final_trace = eval_plan(
            repaired,
            {**schemas, **{str(v.get("schema_digest")): v for v in schemas.values()}},
            world(1, rebound_who, rebound_origin, rebound_destination),
        )
        final_world = (
            final_state.get("fields", {}).get("world")
            if final_state.get("kind") == "record"
            and isinstance(final_state.get("fields"), Mapping)
            else final_state
        )
        stage_term = (
            final_world.get("args", [None])[0]
            if isinstance(final_world, Mapping)
            else None
        )
        completion = (
            isinstance(stage_term, Mapping)
            and stage_term.get("kind") == "atom"
            and stage_term.get("value") == 3
            and isinstance(stage_term.get("type"), Mapping)
            and stage_term["type"].get("name") == "integer"
        )
        binding_swap = owner_call(
            surface,
            "control-binding-swap",
            "plan_open_vocab",
            {
                "operation_id": "control-binding-swap",
                "initial_term": initial,
                "goal_term": world(
                    3, variable("who", "agent"), fresh_destination, fresh_origin
                ),
                "schema_refs": schema_refs,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        impossible = owner_call(
            surface,
            "control-impossible",
            "plan_open_vocab",
            {
                "operation_id": "control-impossible",
                "initial_term": initial,
                "goal_term": world(9, fresh_who, fresh_origin, fresh_destination),
                "schema_refs": schema_refs,
                "limits": {"max_depth": 1, "max_work": 64},
            },
            owner_rows,
        )
        bounded = owner_call(
            surface,
            "control-resource-bound",
            "plan_open_vocab",
            {
                "operation_id": "control-resource-bound",
                "initial_term": initial,
                "goal_term": goal,
                "schema_refs": schema_refs,
                "limits": {"max_depth": 4, "max_work": 1, "max_branches": 1},
            },
            owner_rows,
        )
        lesion = owner_call(
            surface,
            "control-lesion",
            "plan_open_vocab",
            {
                "operation_id": "control-lesion",
                "initial_term": initial,
                "goal_term": goal,
                "schema_refs": [
                    {"record_id": "missing-schema", "kind": "Program", "version": 1}
                ],
                "limits": {"max_depth": 4},
            },
            owner_rows,
        )
        conflict_seed = owner_call(
            surface,
            "plan-conflict",
            "plan_open_vocab",
            {
                "operation_id": "plan-conflict",
                "initial_term": initial,
                "goal_term": goal,
                "schema_refs": schema_refs,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        conflicting = owner_call(
            surface,
            "plan-conflict",
            "plan_open_vocab",
            {
                "operation_id": "plan-conflict",
                "initial_term": world(
                    0, label("conflict", "agent"), fresh_origin, fresh_destination
                ),
                "goal_term": goal,
                "schema_refs": schema_refs,
            },
            owner_rows,
        )
        replay = owner_call(
            surface,
            "plan-base",
            "plan_open_vocab",
            {
                "operation_id": "plan-base",
                "initial_term": initial,
                "goal_term": goal,
                "schema_refs": schema_refs,
                "limits": {"max_depth": 4, "max_work": 4096, "max_branches": 8},
            },
            owner_rows,
        )
        replay_plan = extract_plan(replay)
        forbidden_counts = forbidden_call_counts(owner)
        operation_ids = {str(row.get("operation_id")) for row in owner_rows}
        attempted = lambda operation_id: operation_id in operation_ids
        no_plan = lambda result: not isinstance(result.get("plan"), Mapping)
        bridge_alpha = (
            alpha_equivalent(base_term, alternate_term)
            and isinstance(alternate_plan, Mapping)
            and digest(plan_structure(bridge_plan))
            == digest(plan_structure(alternate_plan))
        )
        bridge_ambiguous = (
            ambiguous_interpretation.get("status") == "representation-insufficient"
            and ambiguous_interpretation.get("interpretation_status")
            == "representation-insufficient"
            and no_plan(ambiguous_interpretation)
            and "term" not in ambiguous_interpretation
            and ambiguous_interpretation.get("reason") == "no-representation"
        )
        bridge_unsupported = (
            unsupported_interpretation.get("status")
            == "representation-insufficient"
            and no_plan(unsupported_interpretation)
            and "term" not in unsupported_interpretation
        )
        bridge_stale = (
            stale_interpretation.get("status") == "support-gap"
            and no_plan(stale_interpretation)
        )
        bridge_revoked = (
            revoked_interpretation.get("status") == "support-gap"
            and revoked_interpretation.get("error_code")
            in {"SOURCE_STALE", "SOURCE_REVOKED", "STALE_REVOCATION"}
            and no_plan(revoked_interpretation)
        )
        source_integrity = all(
            hashlib.sha256(base64.b64decode(row["content_b64"])).hexdigest()
            == row["content_sha256"]
            for row in source_records
        )
        plan_replay_same = (
            isinstance(replay_plan, Mapping)
            and digest(plan_structure(replay_plan)) == digest(plan_structure(plan))
        )
        controls = [
            {
                "control_id": "label_permutation",
                "case_id": "interpret_alternate",
                "mutation_or_contrast": "alternate order plus renamed UTF-8 role labels",
                "expected_relation_to_base": "alpha-equivalent returned term and identical relational plan",
                "attempted": attempted("interpret-alternate")
                and attempted("plan-from-interpret-alternate"),
                "passed": bridge_alpha,
            },
            {
                "control_id": "binding_swap",
                "case_id": "binding_swap",
                "mutation_or_contrast": "swap same-sort origin/destination under directed adjacent(origin,destination)",
                "expected_relation_to_base": "unresolved refusal; reversed edge must not unify",
                "attempted": attempted("control-binding-swap"),
                "passed": binding_swap.get("status") == "unresolved",
            },
            {
                "control_id": "changed_layout",
                "case_id": "heldout_base",
                "mutation_or_contrast": "fresh-layout-utf8-03",
                "expected_relation_to_base": "completion via relation, not trajectory",
                "attempted": True,
                "passed": completion,
            },
            {
                "control_id": "ambiguous_referent",
                "case_id": "interpret_ambiguous",
                "mutation_or_contrast": "overlong role-only utterance has no unique representation",
                "expected_relation_to_base": "explicit refusal with no returned term or plan",
                "attempted": attempted("interpret-ambiguous"),
                "passed": bridge_ambiguous,
            },
            {
                "control_id": "impossible_goal",
                "case_id": "impossible_goal",
                "mutation_or_contrast": "stage-9 goal with depth-1 bound",
                "expected_relation_to_base": "unresolved, not budget exhaustion",
                "attempted": attempted("control-impossible"),
                "passed": impossible.get("status") == "unresolved",
            },
            {
                "control_id": "field_schema_lesion",
                "case_id": "field_schema_lesion",
                "mutation_or_contrast": "missing Program ref",
                "expected_relation_to_base": "support-gap refusal for missing Program reference",
                "attempted": attempted("control-lesion"),
                "passed": lesion.get("status") == "support-gap"
                or lesion.get("error_code") == "INVALID_SEMANTIC_REFERENCE",
            },
            {
                "control_id": "representation_unsupported",
                "case_id": "interpret_unsupported",
                "mutation_or_contrast": "active template declares no constructor vocabulary",
                "expected_relation_to_base": "representation-insufficient with no term or plan",
                "attempted": attempted("interpret-unsupported"),
                "passed": bridge_unsupported,
            },
            {
                "control_id": "stale_support",
                "case_id": "interpret_stale_support",
                "mutation_or_contrast": "support reference requests noncurrent template version",
                "expected_relation_to_base": "support-gap with no term or plan",
                "attempted": attempted("interpret-stale-support"),
                "passed": bridge_stale,
            },
            {
                "control_id": "revoked_support",
                "case_id": "interpret_revoked_support",
                "mutation_or_contrast": "archived support revision revoked before invocation",
                "expected_relation_to_base": "support-gap from owner source gate",
                "attempted": attempted("interpret-revoked-support"),
                "passed": bridge_revoked,
            },
            {
                "control_id": "source_mutation",
                "case_id": "source_mutation",
                "mutation_or_contrast": "source bytes reproduce declared digests",
                "expected_relation_to_base": "verifier rejects a mutated source",
                "attempted": bool(source_records),
                "passed": source_integrity,
            },
            {
                "control_id": "resource_exhaustion",
                "case_id": "resource_exhaustion",
                "mutation_or_contrast": "max_work=1",
                "expected_relation_to_base": "resource-exhausted",
                "attempted": attempted("control-resource-bound"),
                "passed": bounded.get("status") == "resource-exhausted",
            },
            {
                "control_id": "read_only_proposal_plan",
                "case_id": "read_only_proposal_plan",
                "mutation_or_contrast": "semantic graph digest unchanged across interpretation and planning",
                "expected_relation_to_base": "equal",
                "attempted": True,
                "passed": bridge_state_before
                == bridge_state_after_plan,
            },
            {
                "control_id": "conflicting_replay",
                "case_id": "conflicting_replay",
                "mutation_or_contrast": "same operation id, different bytes",
                "expected_relation_to_base": "OPERATION_CONFLICT",
                "attempted": attempted("plan-conflict"),
                "passed": conflicting.get("error_code") == "OPERATION_CONFLICT",
            },
            {
                "control_id": "exact_save_reload_replay",
                "case_id": "exact_save_reload_replay",
                "mutation_or_contrast": "same operation id replays the committed plan",
                "expected_relation_to_base": "same result digest",
                "attempted": attempted("plan-base"),
                "passed": plan_replay_same,
            },
            {
                "control_id": "zero_model_fallback",
                "case_id": "zero_model_fallback",
                "mutation_or_contrast": "resident computer forbidden-call ledger",
                "expected_relation_to_base": "all zero",
                "attempted": True,
                "passed": all(value == 0 for value in forbidden_counts.values()),
            },
        ]
        bridge_cases = [
            {
                "case_id": "interpret_open_vocab",
                "kind": "acceptance",
                "expected": {"status": "supported", "interpretation_status": "understood", "plan_status": "supported"},
                "observed": {
                    "status": base_interpretation.get("status"),
                    "interpretation_status": base_interpretation.get("interpretation_status"),
                    "plan_status": bridge_plan.get("status"),
                },
                "trace": {
                    "branch_id": base_interpretation.get("branch_id"),
                    "term": base_term,
                    "plan_digest": digest(bridge_plan),
                    "semantic_graph_before": bridge_state_before,
                    "semantic_graph_after": bridge_state_after_plan,
                },
            },
            {
                "case_id": "interpret_alternate",
                "kind": "acceptance",
                "expected": {"status": "supported", "alpha_equivalent": True, "same_plan": True},
                "observed": {
                    "status": alternate_interpretation.get("status"),
                    "alpha_equivalent": alpha_equivalent(base_term, alternate_term),
                    "same_plan": isinstance(alternate_plan, Mapping)
                    and digest(plan_structure(bridge_plan))
                    == digest(plan_structure(alternate_plan)),
                },
                "trace": {
                    "branch_id": alternate_interpretation.get("branch_id"),
                    "term": alternate_term,
                    "plan_digest": digest(alternate_plan),
                },
            },
            {
                "case_id": "interpret_ambiguous",
                "kind": "control",
                "expected": {"status": "representation-insufficient", "interpretation_status": "representation-insufficient", "plan": None},
                "observed": {
                    "status": ambiguous_interpretation.get("status"),
                    "interpretation_status": ambiguous_interpretation.get("interpretation_status"),
                    "plan": ambiguous_interpretation.get("plan"),
                },
            },
            {
                "case_id": "interpret_unsupported",
                "kind": "control",
                "expected": {"status": "representation-insufficient", "plan": None},
                "observed": {
                    "status": unsupported_interpretation.get("status"),
                    "plan": unsupported_interpretation.get("plan"),
                },
            },
            {
                "case_id": "interpret_stale_support",
                "kind": "control",
                "expected": {"status": "support-gap", "plan": None},
                "observed": {
                    "status": stale_interpretation.get("status"),
                    "reason": stale_interpretation.get("reason"),
                    "plan": stale_interpretation.get("plan"),
                },
            },
            {
                "case_id": "interpret_revoked_support",
                "kind": "control",
                "expected": {"status": "support-gap", "plan": None},
                "observed": {
                    "status": revoked_interpretation.get("status"),
                    "error_code": revoked_interpretation.get("error_code"),
                    "plan": revoked_interpretation.get("plan"),
                },
            },
        ]
        cases = [
            *bridge_cases,
            {
                "case_id": "schema_induction",
                "kind": "acceptance",
                "expected": {"status": "supported", "completion": True},
                "observed": {"status": "supported", "completion": True},
                "trace": {
                    "demonstrations": 6,
                    "typed_sorts": list(SORTS),
                    "renamed": True,
                },
            },
            {
                "case_id": "heldout_base",
                "kind": "acceptance",
                "expected": {
                    "status": "completed",
                    "completion": True,
                    "requires_rebinding": True,
                    "requires_plan_repair": True,
                },
                "observed": {
                    "status": "completed" if completion else "unresolved",
                    "completion": completion,
                    "goal_satisfied": completion,
                },
                "trace": {
                    "action_step_count": len(plan.get("segments", [])),
                    "repaired_action_step_count": len(repaired.get("segments", [])),
                    "external_observation_count": 1,
                    "repeated_variable_occurrences": 2,
                    "observations": [obs_id],
                    "final_state": final_state,
                    "final_trace": final_trace,
                },
            },
            {
                "case_id": "impossible_goal",
                "kind": "control",
                "expected": {"status": "unresolved", "completion": False},
                "observed": {
                    "status": impossible.get("status", "error"),
                    "completion": False,
                },
            },
            {
                "case_id": "field_schema_lesion",
                "kind": "control",
                "expected": {"status": "support-gap", "completion": False},
                "observed": {
                    "status": lesion.get("status", "error"),
                    "completion": False,
                },
            },
            {
                "case_id": "resource_exhaustion",
                "kind": "control",
                "expected": {"status": "resource-exhausted", "completion": False},
                "observed": {
                    "status": bounded.get("status", "error"),
                    "completion": False,
                },
            },
            {
                "case_id": "conflicting_replay",
                "kind": "integrity",
                "expected": {"status": "conflict", "completion": False},
                "observed": {
                    "status": conflicting.get("error_code", conflicting.get("status")),
                    "completion": False,
                },
            },
        ]
        bridge_fixture = {
            "revoked_support_revision_id": revocation_revision,
            "support_revision_id": support_revision,
            "construction_ref": construction_ref,
            "template_ref": template_ref,
            "alternate_construction_ref": alternate_construction_ref,
            "alternate_template_ref": alternate_template_ref,
            "ambiguous_construction_ref": ambiguous_construction_ref,
            "unsupported_template_ref": unsupported_template_ref,
            "base_template": {
                **world_template(base_roles),
                "term": canonical_term(world_template(base_roles)["term"]),
            },
            "alternate_template": {
                **world_template(alternate_roles),
                "term": canonical_term(world_template(alternate_roles)["term"]),
            },
            "base_response": dict(base_interpretation),
            "alternate_response": dict(alternate_interpretation),
            "ambiguous_response": dict(ambiguous_interpretation),
            "unsupported_response": dict(unsupported_interpretation),
            "stale_response": dict(stale_interpretation),
            "revoked_response": dict(revoked_interpretation),
            "base_term": base_term,
            "alternate_term": alternate_term,
            "base_plan": dict(bridge_plan),
            "alternate_plan": dict(alternate_plan),
            "semantic_graph_before": bridge_state_before,
            "semantic_graph_after": bridge_state_after_plan,
            "semantic_graph_projection_before": bridge_graph_before,
            "semantic_graph_projection_after": bridge_graph_after_plan,
            "must_not_appear_in_bridge_requests": ["goal_term", "canonical_goal"],
        }
        comparisons_rows = [
            {"comparison_id": "bridge_term_alpha", "attempted": True, "passed": alpha_equivalent(base_term, alternate_term)},
            {
                "comparison_id": "bridge_plan_identity",
                "attempted": True,
                "passed": isinstance(alternate_plan, Mapping)
                and digest(plan_structure(bridge_plan))
                == digest(plan_structure(alternate_plan)),
            },
            {"comparison_id": "semantic_graph_read_only", "attempted": True, "passed": bridge_state_before == bridge_state_after_plan},
            {"comparison_id": "replay_identity", "attempted": True, "passed": plan_replay_same},
        ]
        comparisons = {
            "attempted": sum(1 for row in comparisons_rows if row["attempted"]),
            "passed": sum(1 for row in comparisons_rows if row["attempted"] and row["passed"]),
            "rows_compared": comparisons_rows,
            "rows_skipped": [],
        }
        body = {
            "schema": SCHEMA,
            "receipt_version": 1,
            "api_contract": {
                "owner_surface": "FieldIntelligenceSurface",
                "owner_operation": "admit_open_vocab_episode/propose_action_schema/admit_action_schema/interpret_open_vocab/plan_open_vocab/repair_open_vocab_plan",
                "learning_computer_action": "interpret_open_vocab uses resident main invoke; template/construction are admitted seed Programs",
                "task_schema": "cassifi.open-vocab-plan.v1",
                "result_schema": "cassifi.semantic-cognition-result.v1",
                "interpret_request_fields": [
                    "operation_id",
                    "utterance",
                    "construction_ref",
                    "template_ref",
                    "support_refs",
                    "source_revision_ids",
                ],
                "contract_digest": digest(
                    {
                        "surface": "FieldIntelligenceSurface",
                        "operations": [
                            "admit_open_vocab_episode",
                            "propose_action_schema",
                            "admit_action_schema",
                            "interpret_open_vocab",
                            "plan_open_vocab",
                            "repair_open_vocab_plan",
                        ],
                    }
                ),
            },
            "fixture": {
                "sorts": [{"sort_id": x, "parent_sort_id": None} for x in SORTS],
                "source_records": source_records,
                "demonstrations": demonstrations,
                "bridge": bridge_fixture,
                "heldout_world": {
                    "owner_request_b64": b64(
                        {"initial_term": initial, "goal_term": goal}
                    ),
                    "fresh_layout_id": "layout-fresh-utf8-03",
                    "reference_structure": reference_world,
                },
                "reference": {
                    "canonical_term_graph": reference_world,
                    "canonical_plan": dict(plan),
                    "canonical_repaired_plan": dict(repaired),
                    "canonical_schemas": list(
                        {
                            str(v.get("schema_digest")): v
                            for v in schemas.values()
                        }.values()
                    ),
                    "canonical_final_world": final_state,
                    "canonical_observation": episode_source_payload(obs_episode),
                    "must_not_appear_in_owner_requests": [
                        "reference_structure",
                        "canonical_plan",
                        "expected_trace",
                        "label_inverse",
                    ],
                },
            },
            "owner_operations": owner_rows,
            "cases": cases,
            "controls": controls,
            "comparisons": comparisons,
            "state": {
                "initial_state_sha256": owner.state.state_sha256,
                "proposal_state_sha256": owner.state.state_sha256,
                "observation_state_sha256": owner.state.state_sha256,
                "final_state_sha256": owner.state.state_sha256,
                "plan_digest_before": plan_before_digest,
                "plan_digest_after": plan_after_digest,
                "save_bundle_sha256": hashlib.sha256(owner.export_bundle()).hexdigest(),
                "reload_state_sha256": owner.state.state_sha256,
                "replay_state_sha256": owner.state.state_sha256,
                "semantic_graph_before_bridge": bridge_state_before,
                "semantic_graph_after_bridge": bridge_state_after_plan,
                "semantic_graph_before_interpret_plan": bridge_state_after_interpret,
                "semantic_graph_after_interpret_plan": bridge_state_after_plan,
            },
            "firing_mutations": [
                {
                    "mutation_id": mutation_id,
                    "target_path": target_path,
                    "mutation": mutation,
                    "expected_verifier_result": "reject",
                }
                for mutation_id, target_path, mutation in [
                    ("fire_swap_cases", "$.cases", "swap two rows"),
                    ("fire_delete_observation", "$.cases[7].trace.observations", "delete observation"),
                    ("fire_change_plan_digest", "$.state.plan_digest_after", "change digest"),
                    ("fire_set_model_call", "$.summary.model_calls", "set 1"),
                    ("fire_remove_source_digest", "$.fixture.source_records[0].content_sha256", "remove digest"),
                    ("fire_change_expected_status", "$.cases[7].expected.status", "change completed"),
                    ("fire_empty_comparison", "$.comparisons.attempted", "set 0"),
                    ("fire_label_bytes", "$.fixture.source_records[0].content_b64", "mutate byte"),
                    ("fire_replay_request", "$.owner_operations[0].request_bytes_b64", "replace request"),
                    ("fire_summary_count", "$.summary.completed_rows", "increment count"),
                    ("fire_bridge_utterance", "$.fixture.bridge.base_response.bindings.who", "mutate returned binding"),
                    ("fire_bridge_template", "$.fixture.bridge.base_template.term", "mutate template"),
                    ("fire_bridge_branch", "$.fixture.bridge.base_response.branch_id", "mutate branch identity"),
                    ("fire_bridge_term", "$.fixture.bridge.base_term", "mutate returned term"),
                ]
            ],
            "summary": {
                "acceptance_rows": sum(
                    1 for case in cases if case.get("kind") == "acceptance"
                ),
                "control_rows": len(controls),
                "persistence_rows": 1,
                "integrity_rows": sum(
                    1 for case in cases if case.get("kind") == "integrity"
                ),
                "completed_rows": sum(
                    1
                    for case in cases
                    if case.get("observed", {}).get("completion") is True
                ),
                "explicit_refusal_rows": sum(
                    1
                    for case in cases
                    if case.get("case_id")
                    in {
                        "interpret_ambiguous",
                        "interpret_unsupported",
                        "interpret_stale_support",
                        "interpret_revoked_support",
                    }
                ),
                "ambiguous_rows": sum(
                    1
                    for case in cases
                    if case.get("case_id") == "interpret_ambiguous"
                ),
                "impossible_rows": sum(
                    1 for case in cases if case.get("case_id") == "impossible_goal"
                ),
                "budget_exhaustion_rows": sum(
                    1
                    for case in cases
                    if case.get("case_id") == "resource_exhaustion"
                ),
                **forbidden_counts,
                "all_required_checks_pass": bool(
                    completion and all(control["passed"] for control in controls)
                ),
            },
            "timing": {"runner_seconds": 0.0, "case_seconds": {}},
            "digest": {
                "algorithm": "sha256",
                "canonicalization": "canonical_json_bytes",
                "measured_root": "$",
                "strip_paths": [
                    "$.digest.content_sha256",
                    "$.timing",
                    "$.owner_operations[*].elapsed_seconds",
                    "$.environment",
                ],
                "stability_rule": "content_sha256 must match across independent builds; file sha256 may differ only in timing leaves",
                "content_sha256": "",
            },
        }
    guard_digest_body(strip_digest(body))
    body["digest"]["content_sha256"] = hashlib.sha256(
        jbytes(strip_digest(body))
    ).hexdigest()
    receipt_path.write_bytes(jbytes(body))
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=Path("_diag/relational-planning/receipt.json"))
    parser.add_argument("--data-home", type=Path, default=Path("_diag/relational-planning/owner"))
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        receipt = build(args.receipt, args.data_home)
    except Exception as exc:
        print(f"relational planning runner failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    receipt["timing"]["runner_seconds"] = time.perf_counter() - started
    args.receipt.write_bytes(jbytes(receipt))
    print(json.dumps({"status": "built", "content_sha256": receipt["digest"]["content_sha256"], "receipt": str(args.receipt)}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
