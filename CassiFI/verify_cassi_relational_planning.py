"""Stdlib-only independent verifier for the relational-planning receipt."""
from __future__ import annotations
import argparse, base64, copy, hashlib, json, sys, tempfile
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassifi.relational-planning-receipt.v1"
CODEC = "cassifi.open-vocab-byte-symbol.v1"

def jb(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
def sha(value: Any) -> str:
    return hashlib.sha256(jb(value)).hexdigest()
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
def fail(msg: str) -> None:
    raise AssertionError(msg)
def b64json(value: str) -> Any:
    try: return json.loads(base64.b64decode(value).decode("utf-8"))
    except Exception as exc: fail(f"invalid canonical base64 JSON: {exc}")

def strip(value: Any, path: str = "$") -> Any:
    if path == "$.digest.content_sha256": return None
    if path in {"$.timing", "$.environment"} or path.endswith(".timing") or path.endswith(".elapsed_seconds"): return None
    if isinstance(value, Mapping):
        out = {}
        for key, child in value.items():
            val = strip(child, f"{path}.{key}")
            if val is not None: out[key] = val
        return out
    if isinstance(value, list): return [strip(x, f"{path}[{i}]") for i, x in enumerate(value)]
    return value
strip_digest = strip

_RAW_ATOM_TYPES = {"lexeme", "bytes", "integer", "number", "boolean"}


def validate_term(term: Any, scope: str = "free") -> None:
    if not isinstance(term, Mapping) or not isinstance(term.get("kind"), str):
        fail("term is not a tagged object")
    kind = term["kind"]
    if kind == "variable":
        if not isinstance(term.get("name"), str) or not isinstance(term.get("scope"), str):
            fail("invalid variable")
        return
    if kind == "atom":
        typ = term.get("type")
        if isinstance(typ, str):
            if typ not in _RAW_ATOM_TYPES:
                fail("invalid atom type")
            value = term.get("value")
            if typ == "lexeme":
                if isinstance(value, Mapping):
                    if value.get("schema") != CODEC or not isinstance(value.get("bytes"), list):
                        fail("noncanonical byte symbol")
                    raw = bytes(value["bytes"])
                    if value.get("length") != len(raw):
                        fail("byte length mismatch")
                    raw.decode("utf-8")
                elif not isinstance(value, str):
                    fail("invalid raw lexeme atom")
            elif typ == "bytes":
                fail("invalid raw byte atom")
            return
        if not isinstance(typ, Mapping) or typ.get("kind") not in {"atom", "named"}:
            fail("invalid atom type")
        if typ.get("kind") == "atom" and typ.get("name") in {"lexeme", "bytes"}:
            val = term.get("value")
            if not isinstance(val, Mapping) or val.get("schema") != CODEC or not isinstance(val.get("bytes"), list):
                fail("noncanonical byte symbol")
            raw = bytes(val["bytes"])
            if val.get("length") != len(raw):
                fail("byte length mismatch")
            raw.decode("utf-8")
        return
    if kind == "constructor":
        if not isinstance(term.get("name"), str) or not isinstance(term.get("args"), list):
            fail("invalid constructor")
        for arg in term["args"]:
            validate_term(arg, scope)
        return
    if kind == "record":
        if not isinstance(term.get("fields"), Mapping):
            fail("invalid record")
        for arg in term["fields"].values():
            validate_term(arg, scope)
        return
    if kind == "sequence":
        if not isinstance(term.get("items"), list):
            fail("invalid sequence")
        for arg in term["items"]:
            validate_term(arg, scope)
        return
    fail(f"unknown term kind {kind}")

def walk_terms(value: Any) -> None:
    if isinstance(value, Mapping):
        # Canonical term type descriptors are nested tagged mappings such as
        # {"kind": "atom", "name": "integer"}; they are not term nodes.
        if value.get("kind") in {"atom", "named"} and "type" not in value:
            return
        if value.get("kind") in {"variable", "atom", "constructor", "record", "sequence"}:
            validate_term(value)
        else:
            for child in value.values():
                walk_terms(child)
    elif isinstance(value, list):
        for child in value:
            walk_terms(child)

def substitute(term: Any, mapping: Mapping[str, Any]) -> Any:
    if isinstance(term, Mapping):
        if term.get("kind") == "variable":
            return substitute(mapping.get(f"{term.get('scope')}:{term.get('name')}", term), mapping)
        return {key: substitute(value, mapping) for key, value in term.items()}
    if isinstance(term, list):
        return [substitute(value, mapping) for value in term]
    return term
def canonical_public_term(value: Any) -> Any:
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if kind == "atom" and isinstance(value.get("type"), str):
            typ = str(value["type"])
            raw_value = value.get("value")
            if typ == "lexeme" and isinstance(raw_value, str):
                encoded = raw_value.encode("utf-8")
                raw_value = {
                    "bytes": list(encoded),
                    "length": len(encoded),
                    "schema": CODEC,
                }
            return {
                "kind": "atom",
                "type": {"kind": "atom", "name": typ},
                "value": raw_value,
            }
        return {key: canonical_public_term(child) for key, child in value.items()}
    if isinstance(value, list):
        return [canonical_public_term(child) for child in value]
    return value


def execute_plan(initial: Mapping[str, Any], plan: Mapping[str, Any], schemas: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = copy.deepcopy(initial)
    states = []
    for segment in plan.get("segments", []):
        schema = schemas.get(str(segment.get("schema_digest")))
        if not isinstance(schema, Mapping): fail("plan references unknown schema")
        bindings = {str(row.get("variable")): row.get("term") for row in segment.get("substitution", {}).get("bindings", [])}
        pre = substitute(schema["preconditions"][0], bindings)
        if pre != state: fail("plan segment precondition does not match current state")
        state = substitute(schema["effects"][0], bindings)
        if any(isinstance(node, Mapping) and node.get("kind") == "variable" for node in [state]): fail("plan effect remains unbound")
        states.append(copy.deepcopy(state))
    return state, states
def plan_structure(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"plan_id", "basis_field_sha256"}
    }
def forbidden_call_counts(receipt: Mapping[str, Any]) -> dict[str, int]:
    counts = {name: 0 for name in ("model_calls", "qwen_calls", "fallback_calls", "host_search_calls")}

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

    walk(receipt.get("owner_operations", []))
    return counts

def verify(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA or receipt.get("receipt_version") != 1:
        fail("receipt schema/version mismatch")
    digest_data = receipt.get("digest", {})
    if digest_data.get("algorithm") != "sha256" or digest_data.get("canonicalization") != "canonical_json_bytes":
        fail("digest convention mismatch")
    expected = sha(strip(receipt))
    if digest_data.get("content_sha256") != expected:
        fail("content digest mismatch")
    fixture = receipt.get("fixture", {})
    if not isinstance(fixture, Mapping):
        fail("fixture missing")
    sorts = fixture.get("sorts", [])
    if len(sorts) < 2:
        fail("fewer than two sorts")
    source_records = fixture.get("source_records", [])
    if not source_records:
        fail("source fixture is empty")
    required_source_keys = {"event_id", "pre_state", "action", "post_state", "observation", "bindings"}
    for source in source_records:
        raw = base64.b64decode(source.get("content_b64", ""))
        if hashlib.sha256(raw).hexdigest() != source.get("content_sha256"):
            fail("source digest mismatch")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            fail(f"source payload is not canonical JSON: {exc}")
        if not required_source_keys.issubset(payload):
            fail("source payload lacks grounded episode fields")
        if not isinstance(payload.get("observation"), Mapping) or payload["observation"].get("success") is not True:
            fail("source payload lacks closed success observation")
        walk_terms(payload)
    bridge = fixture.get("bridge")
    if not isinstance(bridge, Mapping):
        fail("open-vocabulary bridge fixture is missing")
    bridge_required = {
        "support_revision_id",
        "revoked_support_revision_id",
        "construction_ref",
        "template_ref",
        "alternate_construction_ref",
        "alternate_template_ref",
        "ambiguous_construction_ref",
        "unsupported_template_ref",
        "base_template",
        "alternate_template",
        "base_response",
        "alternate_response",
        "ambiguous_response",
        "unsupported_response",
        "stale_response",
        "revoked_response",
        "base_term",
        "alternate_term",
        "base_plan",
        "alternate_plan",
        "semantic_graph_before",
        "semantic_graph_after",
        "semantic_graph_projection_before",
        "semantic_graph_projection_after",
    }
    if not bridge_required.issubset(bridge):
        fail("open-vocabulary bridge fixture is incomplete")
    graph_before = bridge["semantic_graph_projection_before"]
    graph_after = bridge["semantic_graph_projection_after"]
    if not isinstance(graph_before, Mapping) or not isinstance(graph_after, Mapping):
        fail("semantic graph projection is missing")
    if sha(graph_before) != bridge.get("semantic_graph_before") or sha(graph_after) != bridge.get("semantic_graph_after"):
        fail("semantic graph digest does not match recorded projection")
    if graph_before != graph_after:
        fail("interpretation/planning mutated the persistent semantic graph")
    for value in (
        bridge.get("base_template"),
        bridge.get("alternate_template"),
        bridge.get("base_term"),
        bridge.get("alternate_term"),
        bridge.get("base_plan"),
        bridge.get("alternate_plan"),
    ):
        walk_terms(value)
    owner_operations = receipt.get("owner_operations", [])
    if not owner_operations:
        fail("owner operation ledger is empty")
    forbidden = set(
        fixture.get("reference", {}).get("must_not_appear_in_owner_requests", [])
    )
    decoded_requests = []
    for row in owner_operations:
        request = b64json(row.get("request_bytes_b64", ""))
        operation = str(row.get("operation"))
        operation_id = str(row.get("operation_id"))
        if operation == "configure":
            if request.get("action") != "configure" or request.get("computer_id") != "main":
                fail("configure owner request does not match its ledger row")
        elif request.get("operation") != operation:
            fail("owner request operation does not match its ledger row")
        elif request.get("params", {}).get("operation_id") != operation_id:
            fail("owner request operation id does not match its ledger row")
        decoded_requests.append(request)
        text = json.dumps(request, sort_keys=True, ensure_ascii=False)
        for key in forbidden:
            if key in text:
                fail(f"reference-only field leaked into owner request: {key}")
    bridge_rows = [
        (row, b64json(row.get("request_bytes_b64", "")), b64json(row.get("return_bytes_b64", "")))
        for row in owner_operations
        if row.get("operation") == "interpret_open_vocab"
    ]
    if len(bridge_rows) != 6:
        fail(f"expected six public interpretation calls, found {len(bridge_rows)}")
    rows_by_id = {str(request.get("params", {}).get("operation_id")): (row, request, returned) for row, request, returned in bridge_rows}
    expected_ids = {
        "interpret-base",
        "interpret-alternate",
        "interpret-ambiguous",
        "interpret-unsupported",
        "interpret-stale-support",
        "interpret-revoked-support",
    }
    if set(rows_by_id) != expected_ids:
        fail("interpretation operation ids do not cover the evidence cases")
    required_request_keys = {
        "operation_id",
        "utterance",
        "construction_ref",
        "template_ref",
        "support_refs",
    }
    for operation_id, (_, request, returned) in rows_by_id.items():
        if request.get("operation") != "interpret_open_vocab":
            fail("public bridge request did not use interpret_open_vocab")
        params = request.get("params", {})
        if not required_request_keys.issubset(params):
            fail(f"interpretation request lacks required fields: {operation_id}")
        if any(key in params for key in ("goal_term", "canonical_goal", "canonical_plan")):
            fail(f"caller planning state leaked into interpretation request: {operation_id}")
        expected_root = (
            bridge["revoked_support_revision_id"]
            if operation_id == "interpret-revoked-support"
            else bridge["support_revision_id"]
        )
        if params.get("source_revision_ids") != [expected_root]:
            fail(f"interpretation request lost its support root: {operation_id}")
        if not isinstance(params.get("support_refs"), list):
            fail(f"interpretation support_refs is not a list: {operation_id}")
        if not isinstance(returned, Mapping):
            fail(f"interpretation return is not an object: {operation_id}")
    base = bridge["base_response"]
    alternate = bridge["alternate_response"]
    ambiguous = bridge["ambiguous_response"]
    unsupported = bridge["unsupported_response"]
    stale = bridge["stale_response"]
    revoked = bridge["revoked_response"]
    if base.get("schema") != "cassifi.semantic-cognition-result.v1" or base.get("operation") != "interpret-open-vocab":
        fail("base interpretation result schema/operation mismatch")
    if base.get("status") != "supported" or base.get("interpretation_status") != "understood":
        fail("base interpretation did not produce understood support")
    if not isinstance(base.get("branch_id"), str) or not base["branch_id"]:
        fail("base interpretation lacks branch identity")
    if not isinstance(base.get("branch"), Mapping):
        fail("base interpretation lacks branch metadata")
    if base.get("term") != bridge.get("base_term"):
        fail("base term differs between response and bridge fixture")
    if not isinstance(base.get("bindings"), Mapping) or not isinstance(base.get("binding_rows"), list):
        fail("base interpretation lacks typed bindings")
    provenance = base.get("provenance")
    if isinstance(provenance, Mapping):
        fail("provenance must be emitted as the declared top-level result fields")
    for key, expected_value in (
        ("construction_ref", bridge["construction_ref"]),
        ("template_ref", bridge["template_ref"]),
    ):
        if base.get(key) != expected_value:
            fail(f"base interpretation provenance mismatch: {key}")
    if bridge["support_revision_id"] not in base.get("source_roots", []):
        fail("base interpretation omitted source root provenance")
    if alternate.get("status") != "supported" or alternate.get("interpretation_status") != "understood":
        fail("alternate interpretation did not produce understood support")
    if alternate.get("term") != bridge.get("alternate_term"):
        fail("alternate term differs between response and bridge fixture")
    if not isinstance(alternate.get("branch_id"), str) or not alternate["branch_id"]:
        fail("alternate interpretation lacks branch identity")
    if ambiguous.get("status") != "representation-insufficient" or ambiguous.get("interpretation_status") != "representation-insufficient":
        fail("ambiguous interpretation did not refuse with explicit representation gap")
    if "term" in ambiguous or "plan" in ambiguous or ambiguous.get("reason") != "no-representation":
        fail("ambiguous interpretation leaked a term/plan or refusal reason")
    if unsupported.get("status") != "representation-insufficient" or "term" in unsupported:
        fail("unsupported template did not refuse as representation-insufficient")
    if stale.get("status") != "support-gap" or "term" in stale or "plan" in stale:
        fail("stale semantic reference did not refuse with support-gap")
    if revoked.get("status") != "support-gap" or "term" in revoked or "plan" in revoked:
        fail("revoked source did not refuse with support-gap")
    if bridge.get("semantic_graph_before") != bridge.get("semantic_graph_after"):
        fail("interpretation/planning mutated the persistent semantic graph")
    graph_before = bridge.get("semantic_graph_projection_before")
    graph_after = bridge.get("semantic_graph_projection_after")
    if not isinstance(graph_before, Mapping) or not isinstance(graph_after, Mapping):
        fail("semantic graph projection is missing")
    if sha(graph_before) != bridge.get("semantic_graph_before") or sha(graph_after) != bridge.get("semantic_graph_after"):
        fail("semantic graph digest does not match recorded projection")
    if graph_before != graph_after:
        fail("interpretation/planning mutated the persistent semantic graph")
    base_plan = bridge["base_plan"]
    alternate_plan = bridge["alternate_plan"]
    if base_plan.get("schema") != "cassifi.open-vocab-plan.v1" or alternate_plan.get("schema") != "cassifi.open-vocab-plan.v1":
        fail("bridge plan schema mismatch")
    if base_plan.get("status") != "supported" or alternate_plan.get("status") != "supported":
        fail("bridge plan is not supported")
    if sha(plan_structure(base_plan)) != sha(plan_structure(alternate_plan)):
        fail("alpha-equivalent interpretation did not produce identical plan")
    binding_rows = base.get("binding_rows", [])
    bindings = base.get("bindings", {})
    if not isinstance(bindings, Mapping) or not isinstance(binding_rows, list):
        fail("base interpretation lacks binding closure")
    row_by_role = {str(row.get("role")): row for row in binding_rows if isinstance(row, Mapping)}
    if set(row_by_role) != set(str(key) for key in bindings):
        fail("base binding rows do not close over returned bindings")
    for role, row in row_by_role.items():
        if row.get("surface") != bindings.get(role):
            fail("base binding surface differs from returned binding")
        validate_term(row.get("term"))
    expected_term = substitute(
        bridge["base_template"].get("term"),
        {
            f"role:{role}": canonical_public_term(row.get("term"))
            for role, row in row_by_role.items()
        },
    )
    if expected_term != base.get("term"):
        fail("base template does not construct the returned term")
    if base.get("branch_id") == "0" * 64:
        fail("base branch identity is invalid")
    reference = fixture.get("reference", {})
    operations = receipt.get("owner_operations", [])
    forbidden = set(reference.get("must_not_appear_in_owner_requests", []))
    for row in operations:
        request = b64json(row.get("request_bytes_b64", ""))
        text = json.dumps(request, sort_keys=True, ensure_ascii=False)
        for key in forbidden:
            if key in text:
                fail(f"reference-only field leaked into owner request: {key}")
    walk_terms(fixture.get("reference", {}))
    cases = receipt.get("cases", [])
    ids = {str(row.get("case_id")) for row in cases}
    required = {
        "interpret_open_vocab",
        "interpret_alternate",
        "interpret_ambiguous",
        "interpret_unsupported",
        "interpret_stale_support",
        "interpret_revoked_support",
        "schema_induction",
        "heldout_base",
        "impossible_goal",
        "field_schema_lesion",
        "resource_exhaustion",
        "conflicting_replay",
    }
    if not required.issubset(ids):
        fail(f"required cases missing: {sorted(required - ids)}")
    expected_case_order = [
        "interpret_open_vocab",
        "interpret_alternate",
        "interpret_ambiguous",
        "interpret_unsupported",
        "interpret_stale_support",
        "interpret_revoked_support",
        "schema_induction",
        "heldout_base",
        "impossible_goal",
        "field_schema_lesion",
        "resource_exhaustion",
        "conflicting_replay",
    ]
    if [str(row.get("case_id")) for row in cases] != expected_case_order:
        fail("case order was changed")
    heldout = next(row for row in cases if row.get("case_id") == "heldout_base")
    if heldout.get("expected", {}).get("status") != "completed":
        fail("held-out expected status was changed")
    if not bool(heldout.get("observed", {}).get("completion")):
        fail("held-out goal did not complete")
    trace = heldout.get("trace", {})
    if trace.get("observations") != ["heldout-observation"]:
        fail("held-out observation trace is incomplete")
    if int(trace.get("action_step_count", 0)) < 3 or int(trace.get("repaired_action_step_count", 0)) < 3:
        fail("repair/repeated-variable evidence is too short")
    if int(trace.get("external_observation_count", 0)) < 1 or int(trace.get("repeated_variable_occurrences", 0)) < 2:
        fail("repair/repeated-variable evidence is missing")
    schemas = reference.get("canonical_schemas", [])
    initial = reference.get("canonical_term_graph", {}).get("initial")
    plan = reference.get("canonical_plan")
    final_expected = reference.get("canonical_final_world")
    if not isinstance(initial, Mapping) or not isinstance(plan, Mapping) or not isinstance(final_expected, Mapping):
        fail("independent reference is incomplete")
    schema_map = {str(row.get("schema_digest")): row for row in schemas if isinstance(row, Mapping)}
    final_actual, states = execute_plan(initial, plan, schema_map)
    if not isinstance(final_actual, Mapping) or len(states) < 3:
        fail("independent plan execution did not reach recorded final world")
    if final_actual != final_expected:
        fail("independent canonical plan did not reach recorded final world")
    repaired_plan = reference.get("canonical_repaired_plan")
    if not isinstance(repaired_plan, Mapping):
        fail("independent repaired plan is missing")
    repaired_actual, repaired_states = execute_plan(
        initial,
        repaired_plan,
        schema_map,
    )
    if repaired_actual != final_expected or len(repaired_states) < 3:
        fail("independent repaired suffix did not reach recorded final world")
    summary = receipt.get("summary", {})
    expected_summary = {
        "acceptance_rows": sum(1 for row in cases if row.get("kind") == "acceptance"),
        "control_rows": len(controls) if isinstance(controls := receipt.get("controls", []), list) else -1,
        "integrity_rows": sum(1 for row in cases if row.get("kind") == "integrity"),
        "completed_rows": sum(
            1
            for row in cases
            if row.get("observed", {}).get("completion") is True
        ),
        "explicit_refusal_rows": sum(
            1
            for row in cases
            if row.get("case_id")
            in {"interpret_ambiguous", "interpret_unsupported", "interpret_stale_support", "interpret_revoked_support"}
        ),
        "ambiguous_rows": sum(1 for row in cases if row.get("case_id") == "interpret_ambiguous"),
        "impossible_rows": sum(1 for row in cases if row.get("case_id") == "impossible_goal"),
        "budget_exhaustion_rows": sum(1 for row in cases if row.get("case_id") == "resource_exhaustion"),
    }
    for key, expected_value in expected_summary.items():
        if summary.get(key) != expected_value:
            fail(f"summary count mismatch: {key}")
    controls = receipt.get("controls", [])
    if not controls or any(not control.get("attempted") or not control.get("passed") for control in controls):
        fail("control row missing or failed")
    binding_swap = next((c for c in controls if c.get("control_id") == "binding_swap"), None)
    if binding_swap is None or "directed" not in str(binding_swap).lower() or "refusal" not in str(binding_swap).lower():
        fail("binding-swap control does not encode a semantically directed refusal")
    comparisons = receipt.get("comparisons", {})
    comparison_rows = comparisons.get("rows_compared", [])
    attempted_comparisons = sum(1 for row in comparison_rows if row.get("attempted"))
    passed_comparisons = sum(1 for row in comparison_rows if row.get("attempted") and row.get("passed"))
    if int(comparisons.get("attempted", 0)) != attempted_comparisons or int(comparisons.get("passed", 0)) != passed_comparisons:
        fail("comparison aggregate does not match per-row comparisons")
    if attempted_comparisons <= 0 or passed_comparisons != attempted_comparisons:
        fail("comparison aggregate is vacuous or failed")
    summary = receipt.get("summary", {})
    for key, value in forbidden_call_counts(receipt).items():
        if summary.get(key) != value or value != 0:
            fail(f"nonzero forbidden call counter: {key}")
    if summary.get("all_required_checks_pass") is not True:
        fail("runner did not report all required checks passing")
    return {
        "status": "verified",
        "content_sha256": digest_data["content_sha256"],
        "cases": len(cases),
        "operations": len(operations),
        "bridge_operations": len(bridge_rows),
    }
def fire(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures = []
    mutations = receipt.get("firing_mutations", [])
    if len(mutations) < 14:
        fail("firing mutation inventory is incomplete")

    def case(container: Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
        for item in container.get("cases", []):
            if item.get("case_id") == case_id:
                return item
        fail(f"mutation target case is missing: {case_id}")

    for mutation in mutations:
        altered = copy.deepcopy(receipt)
        target = mutation.get("mutation_id")
        if target == "fire_swap_cases":
            altered["cases"] = list(reversed(altered["cases"]))
        elif target == "fire_delete_observation":
            case(altered, "heldout_base")["trace"]["observations"] = []
        elif target == "fire_change_plan_digest":
            altered["state"]["plan_digest_after"] = "0" * 64
        elif target == "fire_set_model_call":
            altered["summary"]["model_calls"] = 1
        elif target == "fire_remove_source_digest":
            altered["fixture"]["source_records"][0].pop("content_sha256", None)
        elif target == "fire_change_expected_status":
            case(altered, "heldout_base")["expected"]["status"] = "impossible"
        elif target == "fire_empty_comparison":
            altered["comparisons"]["attempted"] = 0
        elif target == "fire_label_bytes":
            altered["fixture"]["source_records"][0]["content_b64"] = "AAAA"
        elif target == "fire_replay_request":
            altered["owner_operations"][0]["request_bytes_b64"] = "e30="
        elif target == "fire_summary_count":
            altered["summary"]["completed_rows"] = int(altered["summary"].get("completed_rows", 0)) + 1
        elif target == "fire_bridge_utterance":
            bindings = altered["fixture"]["bridge"]["base_response"].setdefault("bindings", {})
            bindings["who"] = "mutated-binding"
        elif target == "fire_bridge_template":
            altered["fixture"]["bridge"]["base_template"]["term"] = {
                "kind": "atom",
                "type": "integer",
                "value": 0,
            }
        elif target == "fire_bridge_branch":
            altered["fixture"]["bridge"]["base_response"]["branch_id"] = "0" * 64
        elif target == "fire_bridge_term":
            altered["fixture"]["bridge"]["base_term"] = {
                "kind": "atom",
                "type": "integer",
                "value": 0,
            }
        else:
            fail(f"unknown firing mutation {target}")
        if target != "fire_change_plan_digest":
            altered["digest"]["content_sha256"] = sha(strip_digest(altered))
        try:
            verify(altered)
        except Exception:
            failures.append({"mutation_id": target, "rejected": True})
        else:
            fail(f"firing mutation was accepted: {target}")
    return failures

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--receipt", type=Path, required=True); ap.add_argument("--compare", type=Path); ap.add_argument("--firing-mutations", action="store_true")
    args = ap.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8")); result = verify(receipt)
        if args.compare:
            other = json.loads(args.compare.read_text(encoding="utf-8")); other_result = verify(other)
            if result["content_sha256"] != other_result["content_sha256"]: fail("independent build content digest differs")
            result["comparison"] = "content digest matched"
        if args.firing_mutations: result["firing_mutations"] = fire(receipt)
    except Exception as exc:
        print(json.dumps({"status": "rejected", "message": str(exc)}, sort_keys=True)); return 1
    print(json.dumps(result, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
