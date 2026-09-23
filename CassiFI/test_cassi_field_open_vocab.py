from __future__ import annotations
import copy
import pytest

from cassi_field_atlas import canonical_json_bytes, sha256_value
from cassi_field_cognition import _semantic_dispatch, semantic_cognition_state
from cassi_field_open_vocab import (
    alpha_equivalent,
    canonical_term,
    check_guards,
    decode_lexeme,
    encode_lexeme,
    generate_relational_plan,
    induce_action_schema_candidates,
    instantiate_schema,
    repair_relational_plan,
    unify_terms,
)
from cassi_field_owner import AuthorityGrant, FieldIntelligenceOwner, SourceInput
from cassi_field_program import execute_semantic_program, semantic_program_payload
from cassi_field_regions import make_semantic_record


def atom(value: str):
    return {"kind": "atom", "type": {"kind": "named", "name": "entity"}, "value": value}


def episode(event: str, source: str, left: str, right: str):
    return {
        "event_id": event,
        "source_revision_id": source,
        "pre_state": {"kind": "record", "fields": {"at": atom(left)}},
        "action": {"kind": "constructor", "name": "move", "args": [atom(left), atom(right)]},
        "post_state": {"kind": "record", "fields": {"at": atom(right)}},
        "bindings": {"source": atom(left), "destination": atom(right)},
        "observation": {"success": True},
    }


def trajectory_episode(
    event: str,
    source: str,
    trajectory: str,
    index: int,
    left: str,
    right: str,
):
    value = episode(event, source, left, right)
    value["trajectory_id"] = trajectory
    value["trajectory_index"] = index
    return value



def procedure_episode(
    event: str,
    source: str,
    trajectory: str,
    index: int,
    operation: str,
    item: str,
    place: str,
):
    value = trajectory_episode(
        event, source, trajectory, index, item, place
    )
    if operation != "move":
        value["action"] = {
            "kind": "constructor",
            "name": operation,
            "args": [atom(item)],
        }
        value["bindings"] = {"item": atom(item)}
    return value

def _bridge_template(*, constructors: list[str]) -> dict:
    who = {"kind": "variable", "scope": "role", "name": "who", "type": "agent"}
    origin = {"kind": "variable", "scope": "role", "name": "origin", "type": "place"}
    destination = {"kind": "variable", "scope": "role", "name": "destination", "type": "place"}
    edge = {
        "kind": "constructor",
        "name": "adjacent",
        "args": [origin, destination],
        "type": "directed-route",
    }
    fact = {
        "kind": "constructor",
        "name": "world",
        "args": [
            {"kind": "atom", "type": "integer", "value": 3},
            who,
            origin,
            destination,
            edge,
        ],
    }
    return {
        "schema": "cassifi.open-vocab-template.v1",
        "term": {"kind": "record", "fields": {"world": fact}},
        "constructors": constructors,
    }


def _bridge_program_record(
    record_id: str,
    program: dict,
    support_root: str,
    *,
    role: str | None = None,
) -> dict:
    payload = {"program": program}
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
        derivation={"criterion": "focused-open-vocabulary-bridge"},
    )


def _bridge_fixture(*, constructors: list[str]):
    support_root = "a" * 64
    construction_ref = {
        "kind": "Program",
        "id": "test:construction:advance",
        "content_version": 1,
    }
    template_ref = {
        "kind": "Program",
        "id": "test:template:world",
        "content_version": 1,
    }
    construction = semantic_program_payload(
        program_kind="construction",
        body={
            "pattern": ["advance", "{who}", "from", "{origin}", "to", "{destination}"],
            "roles": ["who", "origin", "destination"],
            "meaning": {},
            "guards": {},
            "speech_act": "assertion",
            "source_policy": {"grants_authority": False},
        },
        max_work=8,
    )
    template = semantic_program_payload(
        program_kind="procedure",
        body={"template": _bridge_template(constructors=constructors)},
        max_work=8,
    )
    state = semantic_cognition_state(
        seed_records=[
            _bridge_program_record(
                construction_ref["id"],
                construction,
                support_root,
                role="construction",
            ),
            _bridge_program_record(template_ref["id"], template, support_root),
        ]
    )
    return state, construction_ref, template_ref, support_root


def _semantic_graph_projection(state: dict) -> dict:
    return copy.deepcopy(
        {
            key: state[key]
            for key in (
                "schema",
                "family",
                "scope",
                "frame",
                "invalidation",
                "records",
                "current",
                "indexes",
                "time",
                "beliefs",
                "libraries",
                "bounds",
            )
        }
    )


def test_semantic_open_vocab_bridge_returns_bindings_without_goal_state_write():
    state, construction_ref, template_ref, support_root = _bridge_fixture(
        constructors=["adjacent", "world"]
    )
    request = {
        "operation": "interpret-open-vocab",
        "operation_id": "focused-bridge-supported",
        "utterance": "advance captain from base to harbor",
        "construction_ref": construction_ref,
        "template_ref": template_ref,
        "support_refs": [],
        "source_revision_ids": [support_root],
        "context": {},
        "max_tokens": 128,
    }
    before = _semantic_graph_projection(state)
    result, work = _semantic_dispatch(state, request)
    after = _semantic_graph_projection(state)

    assert work > 0
    assert "goal_term" not in request
    assert result["schema"] == "cassifi.semantic-cognition-result.v1"
    assert result["operation"] == "interpret-open-vocab"
    assert result["status"] == "supported"
    assert result["interpretation_status"] == "understood"
    assert canonical_term(result["term"]) == result["term"]
    assert result["term"]["kind"] == "record"
    assert set(result["term"]["fields"]) == {"world"}
    rows = {row["role"]: row for row in result["binding_rows"]}
    assert set(rows) == {"who", "origin", "destination"}
    assert {role: row["surface"] for role, row in rows.items()} == {
        "who": "captain",
        "origin": "base",
        "destination": "harbor",
    }
    assert all(
        {"role", "surface", "term"}.issubset(row) and isinstance(row["term"], dict)
        for row in rows.values()
    )
    assert before == after


def test_semantic_open_vocab_bridge_refuses_unsupported_template_read_only():
    state, construction_ref, template_ref, support_root = _bridge_fixture(constructors=[])
    request = {
        "operation": "interpret-open-vocab",
        "operation_id": "focused-bridge-unsupported",
        "utterance": "advance captain from base to harbor",
        "construction_ref": construction_ref,
        "template_ref": template_ref,
        "support_refs": [],
        "source_revision_ids": [support_root],
    }
    before = _semantic_graph_projection(state)
    result, work = _semantic_dispatch(state, request)
    after = _semantic_graph_projection(state)

    assert work > 0
    assert result["status"] == "representation-insufficient"
    assert result["interpretation_status"] == "representation-insufficient"
    assert "term" not in result
    assert "plan" not in result
    assert before == after




def test_fixed_bytes_and_recursive_alpha_equivalence():
    encoded = encode_lexeme("NøNCE")
    assert decode_lexeme(encoded) == "NøNCE".encode("utf-8")
    left = {"kind": "variable", "name": "source", "scope": "schema", "type": "entity"}
    right = {"kind": "variable", "name": "renamed", "scope": "schema", "type": "entity"}
    assert alpha_equivalent(left, right)
    assert canonical_term({"kind": "record", "fields": {"x": atom("q")}})["fields"]["x"]["value"] == "q"


def test_nested_unification_and_occurs_type_refusals():
    var = {"kind": "variable", "name": "x", "scope": "schema", "type": "entity"}
    nested = {"kind": "constructor", "name": "pair", "args": [atom("a"), {"kind": "constructor", "name": "box", "args": [atom("b")]}]}
    assert unify_terms({"kind": "constructor", "name": "pair", "args": [var, nested["args"][1]]}, nested)["status"] == "supported"
    recursive = {"kind": "constructor", "name": "loop", "args": [var]}
    assert unify_terms(var, recursive)["reason"] == "occurs-check"
    integer = {"kind": "variable", "name": "i", "scope": "schema", "type": "integer"}
    assert unify_terms(integer, atom("not-an-integer"))["reason"] == "type-mismatch"


def test_induction_nonce_renaming_and_held_out_plan():
    def complete(event_id, source, left, right):
        return {
            **episode(event_id, source, left, right),
            "pre_state": {"kind": "record", "fields": {"at": atom(left), "available": atom(right)}},
            "post_state": {"kind": "record", "fields": {"at": atom(right), "available": atom(left)}},
        }
    result = induce_action_schema_candidates([complete("e1", "s1", "α", "β"), complete("e2", "s2", "γ", "δ")])
    assert result["status"] == "supported"
    schema = result["candidates"][0]
    held = complete("held", "s3", "new-a", "new-b")
    plan = generate_relational_plan(held["pre_state"], held["post_state"], [schema], limits={"max_depth": 2, "max_work": 32, "max_branches": 4})
    assert plan["status"] == "supported"
    assert len(plan["segments"]) == 1


def test_repeated_entity_roles_are_shared_across_pre_action_effect():
    result = induce_action_schema_candidates(
        [episode("e1", "s1", "α", "β"), episode("e2", "s2", "γ", "δ")]
    )
    schema = result["candidates"][0]
    source = schema["action"]["args"][0]["name"]
    destination = schema["action"]["args"][1]["name"]
    assert schema["preconditions"][0]["fields"]["at"]["name"] == source
    assert schema["effects"][0]["fields"]["at"]["name"] == destination
    swapped = instantiate_schema(schema, {f"schema:{source}": atom("β"), f"schema:{destination}": atom("α")})
    assert unify_terms(swapped["effects"][0], episode("held", "s", "α", "β")["post_state"])["status"] == "unresolved"

def test_schema_admission_rejects_support_mutation_without_state_write():
    state = semantic_cognition_state()
    episodes = [episode("e1", "s1", "a", "b"), episode("e2", "s2", "c", "d")]
    events = []
    for raw in episodes:
        result, _ = _semantic_dispatch(
            state,
            {
                "operation": "admit-open-vocab-episode",
                "event_id": raw["event_id"],
                "source_revision_id": raw["source_revision_id"],
                "episode": raw,
            },
        )
        events.append(result["event"])
    proposed, _ = _semantic_dispatch(
        state,
        {
            "operation": "propose-action-schema",
            "training_event_refs": events,
            "holdout_event_refs": [],
        },
    )
    candidate = dict(proposed["candidates"][0])
    candidate["support_event_refs"] = ["e1", "tampered"]
    before = len(state["records"])
    try:
        _semantic_dispatch(
            state,
            {
                "operation": "admit-action-schema",
                "candidate": candidate,
                "support_event_refs": events,
                "source_revision_ids": ["s1", "s2"],
            },
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "OPERATION_CONFLICT"
    else:
        raise AssertionError("tampered schema support was accepted")
    assert len(state["records"]) == before

def test_semantic_admission_and_idempotent_replay_without_hypothesis_write():
    state = semantic_cognition_state()
    raw = episode("evt", "source", "a", "b")
    request = {"operation": "admit-open-vocab-episode", "event_id": "evt", "source_revision_id": "source", "episode": raw}
    first, _ = _semantic_dispatch(state, request)
    before = len(state["records"])
    replay, _ = _semantic_dispatch(state, request)
    assert first["status"] == replay["status"] == "supported"
    assert replay["replayed"] is True
    assert len(state["records"]) == before
    changed = {**request, "episode": {**raw, "event_id": "different"}}
    try:
        _semantic_dispatch(state, changed)
    except Exception as exc:
        assert getattr(exc, "code", None) in {"OPERATION_CONFLICT", "SUPPORT_GAP"}
    else:
        raise AssertionError("conflicting replay was accepted")

def _fixed_schema(pre_value: str, post_value: str, name: str):
    return {
        "action": {"kind": "constructor", "name": name, "args": []},
        "preconditions": [{"kind": "record", "fields": {"at": atom(pre_value)}}],
        "effects": [{"kind": "record", "fields": {"at": atom(post_value)}}],
        "parameters": [],
    }


def test_scope_unit_frame_and_guard_refusals_are_explicit():
    local = {"kind": "variable", "name": "x", "scope": "local", "type": {"kind": "named", "name": "entity"}}
    free = {"kind": "variable", "name": "x", "scope": "free", "type": {"kind": "named", "name": "entity"}}
    assert unify_terms(local, free)["reason"] == "scope-mismatch"
    left = {"kind": "constructor", "name": "quantity", "unit": "m", "args": [atom("a")]}
    right = {"kind": "constructor", "name": "quantity", "unit": "s", "args": [atom("a")]}
    assert unify_terms(left, right)["reason"] == "unit-frame-mismatch"
    left["frame"], right["frame"] = "world", "body"
    assert unify_terms(left, right)["reason"] == "unit-frame-mismatch"
    assert check_guards([{"kind": "eq", "left": atom("a"), "right": atom("b")}]) == (False, "guard-contradiction")


def test_resource_bound_is_deterministic_and_statuses_are_distinct():
    schema = _fixed_schema("a", "b", "step")
    initial = {"kind": "record", "fields": {"at": atom("a")}}
    goal = {"kind": "record", "fields": {"at": atom("b")}}
    bounded = [generate_relational_plan(initial, goal, [schema], limits={"max_depth": 2, "max_work": 0}) for _ in range(2)]
    assert bounded[0] == bounded[1]
    assert bounded[0]["status"] == "resource-exhausted"
    alternatives = generate_relational_plan(initial, goal, [_fixed_schema("a", "b", "step-a"), _fixed_schema("a", "b", "step-b")], limits={"max_depth": 1, "max_work": 32, "max_branches": 8})
    assert alternatives["status"] == "alternatives"


def test_two_step_plan_and_observation_suffix_repair_rebind():
    first = _fixed_schema("a", "b", "first")
    second = _fixed_schema("b", "c", "second")
    initial = {"kind": "record", "fields": {"at": atom("a")}}
    goal = {"kind": "record", "fields": {"at": atom("c")}}
    plan = generate_relational_plan(initial, goal, [first, second], limits={"max_depth": 3, "max_work": 64})
    assert plan["status"] == "supported"
    assert len(plan["segments"]) == 2
    observation = {
        "event_id": "repair",
        "source_revision_id": "source",
        "pre_state": initial,
        "action": {"kind": "constructor", "name": "first", "args": []},
        "post_state": {"kind": "record", "fields": {"at": atom("b")}},
        "observation": {"success": True},
        "completed_segments": 1,
    }
    repaired = repair_relational_plan(plan, observation, [first, second], limits={"max_depth": 2, "max_work": 64})
    assert repaired["status"] == "supported"
    assert len(repaired["segments"]) == 2
    assert repaired["segments"][0] == plan["segments"][0]
    assert repaired["segments"][1]["action"]["name"] == "second"


def test_bounds_are_explicit_not_false_impossibility():
    schema = induce_action_schema_candidates([episode("e1", "s1", "a", "b"), episode("e2", "s2", "c", "d")])["candidates"][0]
    result = generate_relational_plan(episode("e", "s", "a", "b")["pre_state"], episode("e", "s", "a", "b")["post_state"], [schema], limits={"max_depth": 0, "max_work": 1, "max_branches": 1})
    assert result["status"] in {"unresolved", "resource-exhausted"}

def test_proposal_plan_repair_are_read_only_and_no_model_fallback():
    state = semantic_cognition_state()
    episodes = [episode("ro-1", "source-1", "a", "b"), episode("ro-2", "source-2", "c", "d")]
    event_refs = []
    for row in episodes:
        admitted, _ = _semantic_dispatch(
            state,
            {"operation": "admit-open-vocab-episode", "event_id": row["event_id"], "source_revision_id": row["source_revision_id"], "episode": row},
        )
        event_refs.append(admitted["event"])
    before = sha256_value(state)
    proposed, _ = _semantic_dispatch(
        state,
        {"operation": "propose-action-schema", "training_event_refs": event_refs, "holdout_event_refs": []},
    )
    assert proposed["status"] == "supported"
    assert sha256_value(state) == before
    initial = {"kind": "record", "fields": {"at": atom("a")}}
    goal = {"kind": "record", "fields": {"at": atom("b")}}
    schema = _fixed_schema("a", "b", "model-free")
    plan = generate_relational_plan(initial, goal, [schema])
    observation = {
        **episode("read-only", "source", "a", "b"),
        "post_state": goal,
        "completed_segments": 0,
    }
    repaired = repair_relational_plan(plan, observation, [schema])
    assert not any(key in repaired for key in ("model", "provider", "fallback"))
    assert sha256_value(state) == before


def test_owner_checkpoint_reload_preserves_semantic_records(tmp_path):
    home = tmp_path / "checkpoint"
    source = SourceInput(
        source_id="checkpoint-source",
        content=b"exact",
        media_type="text/plain",
        codec="utf-8",
        observed_timestamp="now",
        scope="test",
        claim_category="observation",
        fidelity="exact",
    )
    with FieldIntelligenceOwner(home) as owner:
        archived = owner.archive_source(operation_id="checkpoint-archive", source=source, context={})
        revision = archived["source"]["revision_id"]
        first = owner.inspect()

    with FieldIntelligenceOwner(home) as reloaded:
        second = reloaded.inspect()
        assert second["field_state_sha256"] == first["field_state_sha256"]
        assert second["checkpoint_manifest_sha256"] == first["checkpoint_manifest_sha256"]
        assert revision in reloaded.evidence.active_revision_ids()

def test_owner_revoked_source_is_stale_and_not_active(tmp_path):
    home = tmp_path / "revocation"
    source = SourceInput(
        source_id="revoked-source",
        content=b"revoked",
        media_type="text/plain",
        codec="utf-8",
        observed_timestamp="now",
        scope="test",
        claim_category="observation",
        fidelity="exact",
    )
    with FieldIntelligenceOwner(home) as owner:
        archived = owner.archive_source(operation_id="revoke-archive", source=source, context={})
        revision = archived["source"]["revision_id"]
        preview = owner.preview_forget([revision])
        grant = AuthorityGrant(
            grant_id="revoke-grant",
            issuer="test",
            generation=owner.authority_generation,
            operation="forget",
            target=sha256_value([revision]),
            scope="test",
        )
        owner.forget(
            operation_id="revoke-source",
            preview_id=preview["preview_id"],
            revision_ids=[revision],
            grant=grant,
            scope="test",
        )
        inspected = owner.inspect()
        assert revision not in inspected["evidence"]["active_revision_ids"]
        assert revision in inspected["evidence"]["revision_ids"]
        with pytest.raises(Exception) as exc:
            owner.archive_source(operation_id="revoke-reuse", source=source, context={})
        assert getattr(exc.value, "code", None) in {"SOURCE_REVOKED", "SOURCE_STALE", "SOURCE_CONFLICT"}

def test_owner_rejects_mutated_archived_episode_before_computer_route(tmp_path):
    payload = episode("source-event", "pending", "a", "b")
    payload_bytes = canonical_json_bytes({key: payload[key] for key in ("event_id", "pre_state", "action", "post_state", "observation", "bindings")})
    source = SourceInput(source_id="episode-source", content=payload_bytes, media_type="application/json", codec="utf-8", observed_timestamp="now", scope="test", claim_category="observation", fidelity="exact")
    with FieldIntelligenceOwner(tmp_path / "owner") as owner:
        revision = owner.archive_source(operation_id="archive-episode", source=source, context={})["source"]["revision_id"]
        mutated = {**payload, "source_revision_ids": [revision], "post_state": {"kind": "record", "fields": {"at": atom("mutated")}}}
        with pytest.raises(Exception) as exc:
            owner.admit_open_vocab_episode("admit-mutated", revision, mutated, "source-event")
        assert getattr(exc.value, "code", None) == "SOURCE_CONFLICT"

def test_nonfinite_numbers_are_rejected_but_finite_numbers_are_canonical():
    number = lambda value: {"kind": "atom", "type": "number", "value": value}
    assert canonical_term(number(1.25))["value"] == 1.25
    import math
    for value in (math.nan, math.inf, -math.inf):
        try:
            canonical_term(number(value))
        except Exception as exc:
            assert getattr(exc, "code", None) == "representation-insufficient"
        else:
            raise AssertionError("nonfinite number was accepted")

def test_guard_codec_type_and_holdout_fail_closed():
    assert unify_terms(atom("a"), atom("a"), guards=[{"kind": "applicable", "value": False}])["status"] == "unresolved"
    raw = bytes(range(256))
    assert decode_lexeme(raw) == raw
    with pytest.raises(Exception):
        decode_lexeme({"schema": "cassifi.open-vocab-byte-symbol.v1", "bytes": [1], "length": 2})
    with pytest.raises(Exception):
        decode_lexeme({"schema": "cassifi.open-vocab-byte-symbol.v1", "bytes": [256], "length": 1})
    integer = {**episode("i", "s", "a", "b"), "action": {"kind": "constructor", "name": "n", "args": [{"kind": "atom", "type": "integer", "value": 1}]}}
    boolean = {**episode("b", "s", "a", "b"), "action": {"kind": "constructor", "name": "n", "args": [{"kind": "atom", "type": "boolean", "value": True}]}}
    with pytest.raises(Exception):
        induce_action_schema_candidates([integer, boolean])
    contradiction = {**episode("h", "s", "a", "b"), "post_state": {"kind": "record", "fields": {"at": atom("wrong")}}, "action": {"kind": "constructor", "name": "unsafe", "args": []}}
    result = induce_action_schema_candidates([episode("t1", "s", "a", "b"), episode("t2", "s", "c", "d")], [contradiction])
    assert result["status"] == "unresolved"


def test_goal_binding_supports_effect_only_variable():
    schema = {
        "action": {"kind": "constructor", "name": "unsafe", "args": []},
        "preconditions": [{"kind": "record", "fields": {"at": atom("a")}}],
        "effects": [{"kind": "record", "fields": {"at": {"kind": "variable", "name": "x", "scope": "schema", "type": {"kind": "named", "name": "entity"}}}}],
        "parameters": [{"name": "x", "type": "entity"}],
    }
    result = generate_relational_plan({"kind": "record", "fields": {"at": atom("a")}}, {"kind": "record", "fields": {"at": atom("goal")}}, [schema])
    assert result["status"] == "supported"


def test_unbound_effect_only_variable_cannot_support_goal():
    schema = {
        "action": {"kind": "constructor", "name": "unsafe", "args": []},
        "preconditions": [{"kind": "record", "fields": {"at": atom("a")}}],
        "effects": [{"kind": "record", "fields": {"at": {"kind": "variable", "name": "x", "scope": "schema", "type": {"kind": "named", "name": "entity"}}, "status": atom("done")}}],
        "parameters": [{"name": "x", "type": "entity"}],
    }
    goal = {
        "kind": "record",
        "fields": {
            "at": {
                "kind": "variable",
                "name": "destination",
                "scope": "goal",
                "type": {"kind": "named", "name": "entity"},
            },
            "status": atom("done"),
        },
    }
    result = generate_relational_plan({"kind": "record", "fields": {"at": atom("a")}}, goal, [schema])
    assert result["status"] == "unresolved"

def test_goal_binds_novel_destination_and_multi_fact_transition():
    var = lambda name: {"kind": "variable", "name": name, "scope": "schema", "type": {"kind": "named", "name": "entity"}}
    schema = {
        "action": {"kind": "constructor", "name": "move", "args": [var("from"), var("to")]},
        "preconditions": [{"kind": "record", "fields": {"at": var("from")}}],
        "effects": [{"kind": "record", "fields": {"at": var("to")}}],
        "parameters": [{"name": "from", "type": "place"}, {"name": "to", "type": "place"}],
    }
    planned = generate_relational_plan({"kind": "record", "fields": {"at": atom("a")}}, {"kind": "record", "fields": {"at": atom("novel")}}, [schema])
    assert planned["status"] == "supported"
    assert planned["segments"][0]["action"]["args"][1]["value"] == "novel"
    multi = {
        "action": {"kind": "constructor", "name": "activate", "args": []},
        "preconditions": [{"kind": "record", "fields": {"at": atom("a")}}, {"kind": "record", "fields": {"ready": atom("yes")}}],
        "effects": [{"kind": "record", "fields": {"at": atom("b")}}, {"kind": "record", "fields": {"ready": atom("done")}}],
        "parameters": [],
    }
    initial = {"kind": "sequence", "items": [{"kind": "record", "fields": {"at": atom("a")}}, {"kind": "record", "fields": {"ready": atom("yes")}}, {"kind": "record", "fields": {"unaffected": atom("keep")}}]}
    goal = {"kind": "sequence", "items": [{"kind": "record", "fields": {"at": atom("b")}}, {"kind": "record", "fields": {"ready": atom("done")}}, {"kind": "record", "fields": {"unaffected": atom("keep")}}]}
    assert generate_relational_plan(initial, goal, [multi])["status"] == "supported"

def test_repair_rejects_bad_observation_and_plan_closure():
    schema = _fixed_schema("a", "b", "one")
    initial = {"kind": "record", "fields": {"at": atom("a")}}
    goal = {"kind": "record", "fields": {"at": atom("b")}}
    plan = generate_relational_plan(initial, goal, [schema])
    bad_digest = {**plan, "plan_id": "0" * 64}
    observation = {"event_id": "bad", "source_revision_id": "s", "pre_state": initial, "action": schema["action"], "post_state": goal, "observation": {"success": True}, "completed_segments": 1}
    assert repair_relational_plan(bad_digest, observation, [schema])["reason"] == "plan-digest-mismatch"
    bad_action = {**observation, "action": {"kind": "constructor", "name": "wrong", "args": []}}
    assert repair_relational_plan(plan, bad_action, [schema])["reason"] == "observation-action-mismatch"
    failed = {**observation, "observation": {"success": False}}
    assert repair_relational_plan(plan, failed, [schema])["reason"] == "observation-failed"
 
def test_autonomous_learning_discovers_action_schema_from_resident_episodes():
    state = semantic_cognition_state()
    for raw in (
        episode("resident-e1", "resident-s1", "alpha", "beta"),
        episode("resident-e2", "resident-s2", "gamma", "delta"),
    ):
        admitted, _ = _semantic_dispatch(
            state,
            {
                "operation": "admit-open-vocab-episode",
                "event_id": raw["event_id"],
                "source_revision_id": raw["source_revision_id"],
                "episode": raw,
            },
        )
        assert admitted["status"] == "supported"

    result, work = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-learn",
            "operation_id": "resident-schema-discovery",
            "goal": "learn how movement changes location",
        },
    )

    assert work > 0
    assert result["status"] == "supported"
    assert result["discovery"] == {
        "mode": "resident-open-vocabulary",
        "inspected_event_count": 2,
        "opportunity_count": 1,
    }
    assert result["selected"]["learning_kind"] == "action-schema"
    learning = result["learning"]
    assert learning["learning_kind"] == "action-schema"
    assert learning["admission"]["status"] == "supported"
    assert learning["admission"]["schema_ref"]["kind"] == "Program"
    assert learning["candidate"]["support_event_refs"] == [
        "resident-e1",
        "resident-e2",
    ]

def test_resident_procedure_discovery_requires_and_uses_trajectory_metadata():
    state = semantic_cognition_state()
    rows = [
        procedure_episode("t1-e0", "t1-s0", "route-a", 0, "open", "a", "a"),
        procedure_episode("t1-e1", "t1-s1", "route-a", 1, "move", "a", "left"),
        procedure_episode("t1-e2", "t1-s2", "route-a", 2, "check", "a", "a"),
        procedure_episode("t1-e3", "t1-s3", "route-a", 3, "close", "a", "a"),
        procedure_episode("t2-e0", "t2-s0", "route-b", 0, "open", "u", "u"),
        procedure_episode("t2-e1", "t2-s1", "route-b", 1, "move", "u", "right"),
        procedure_episode("t2-e2", "t2-s2", "route-b", 2, "check", "u", "u"),
        procedure_episode("t2-e3", "t2-s3", "route-b", 3, "close", "u", "u"),
    ]
    for raw in rows:
        admitted, _ = _semantic_dispatch(
            state,
            {
                "operation": "admit-open-vocab-episode",
                "event_id": raw["event_id"],
                "source_revision_id": raw["source_revision_id"],
                "episode": raw,
            },
        )
        assert admitted["status"] == "supported"

    discovered, work = _semantic_dispatch(
        state,
        {"operation": "discover-procedure", "max_candidates": 4},
    )

    assert work > 0
    assert discovered["status"] == "supported"
    opportunity = discovered["opportunities"][0]
    assert opportunity["learning_kind"] == "procedure"
    request = opportunity["request"]
    assert len(request["traces"]) == 2
    assert all(len(trace["steps"]) == 4 for trace in request["traces"])
    assert sorted(request["traces"][0]["support_event_refs"]) == [
        "t1-e0",
        "t1-e1",
        "t1-e2",
        "t1-e3",
    ]

    learned, _ = _semantic_dispatch(
        state,
        {
            "operation": "learn-procedure",
            "operation_id": "resident-route-procedure",
            **request,
        },
    )

    assert learned["status"] == "supported"
    assert learned["procedure"]["kind"] == "Program"
    assert learned["procedure"]["id"] == request["procedure_id"]
    procedure_record = state["records"][request["procedure_id"]][-1]
    dependency_ids = {
        dependency["id"] for dependency in procedure_record["dependencies"]
    }
    assert {"t1-e0", "t1-e1", "t1-e2", "t1-e3"} <= dependency_ids

    autonomous, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-learn",
            "operation_id": "resident-procedure-autonomy",
            "goal": "reuse a recurring route",
        },
    )
    assert autonomous["status"] == "supported"
    assert autonomous["selected"]["learning_kind"] == "procedure"
    assert autonomous["learning"]["procedure"]["id"] == request["procedure_id"]

    invoked, _ = _semantic_dispatch(
        state,
        {
            "operation": "invoke-procedure",
            "procedure_ref": autonomous["learning"]["procedure"],
            "bindings": {"role_0": "new-item", "role_1": "new-place"},
        },
    )
    assert invoked["status"] == "supported"
    assert len(invoked["proposed_actions"]) == 4
    assert invoked["proposed_actions"][1]["action"]["name"] == "move"

    cycle_one, _ = _semantic_dispatch(
        state,
        {"operation": "autonomous-learn", "goal": "continue learning"},
    )
    cycle_two, _ = _semantic_dispatch(
        state,
        {"operation": "autonomous-learn", "goal": "continue learning"},
    )
    assert cycle_one["event"]["id"] != cycle_two["event"]["id"]
    assert cycle_two.get("replayed", False) is False
    current_procedure = state["current"]["Program"][request["procedure_id"]]
    planned, _ = _semantic_dispatch(
        state,
        {
            "operation": "plan-procedure",
            "procedure_ref": current_procedure,
            "bindings": {"role_0": "new-item", "role_1": "new-place"},
            "goal": invoked["outcome"]["procedure_postconditions"],
            "plan_id": "resident-route-plan",
            "scope": "sandbox",
            "target": "route-execution",
        },
    )
    assert planned["status"] == "supported"
    assert planned["plan"]["kind"] == "Program"
    assert planned["proposal"]["status"] == "proposed"
    assert planned["proposal"]["action"]["operation"] == "invoke-procedure"
    assert planned["proposal"]["affordance"]["id"] == current_procedure["id"]


def test_resident_procedure_discovery_segments_untagged_events():
    state = semantic_cognition_state()
    rows = [
        procedure_episode("u1-e0", "u1-s0", "ignored-a", 0, "open", "a", "a"),
        procedure_episode("u1-e1", "u1-s1", "ignored-a", 1, "move", "a", "left"),
        procedure_episode("u1-e2", "u1-s2", "ignored-a", 2, "check", "a", "a"),
        procedure_episode("u1-e3", "u1-s3", "ignored-a", 3, "close", "a", "a"),
        procedure_episode("u2-e0", "u2-s0", "ignored-b", 0, "open", "u", "u"),
        procedure_episode("u2-e1", "u2-s1", "ignored-b", 1, "move", "u", "right"),
        procedure_episode("u2-e2", "u2-s2", "ignored-b", 2, "check", "u", "u"),
        procedure_episode("u2-e3", "u2-s3", "ignored-b", 3, "close", "u", "u"),
    ]
    for raw in rows:
        untagged = dict(raw)
        untagged.pop("trajectory_id")
        untagged.pop("trajectory_index")
        admitted, _ = _semantic_dispatch(
            state,
            {
                "operation": "admit-open-vocab-episode",
                "event_id": untagged["event_id"],
                "source_revision_id": untagged["source_revision_id"],
                "episode": untagged,
            },
        )
        assert admitted["status"] == "supported"

    discovered, work = _semantic_dispatch(
        state,
        {"operation": "discover-procedure", "max_candidates": 4},
    )

    assert work > 0
    assert discovered["status"] == "supported"
    request = discovered["opportunities"][0]["request"]
    assert len(request["traces"]) == 2
    assert all(trace["trace_id"].startswith("trajectory:inferred-trajectory:") for trace in request["traces"])
    assert all(trace["trajectory_source"] == "inferred" for trace in request["traces"])
    assert all(len(trace["steps"]) == 4 for trace in request["traces"])
    assert {
        event_id
        for trace in request["traces"]
        for event_id in trace["support_event_refs"]
    } == {f"u{route}-e{step}" for route in (1, 2) for step in range(4)}


def test_resident_procedure_discovery_keeps_failed_trajectories_as_holdout():
    state = semantic_cognition_state()
    rows = [
        procedure_episode("h1-e0", "h1-s0", "holdout-a", 0, "open", "a", "a"),
        procedure_episode("h1-e1", "h1-s1", "holdout-a", 1, "move", "a", "left"),
        procedure_episode("h1-e2", "h1-s2", "holdout-a", 2, "check", "a", "a"),
        procedure_episode("h1-e3", "h1-s3", "holdout-a", 3, "close", "a", "a"),
        procedure_episode("h2-e0", "h2-s0", "holdout-b", 0, "open", "u", "u"),
        procedure_episode("h2-e1", "h2-s1", "holdout-b", 1, "move", "u", "right"),
        procedure_episode("h2-e2", "h2-s2", "holdout-b", 2, "check", "u", "u"),
        procedure_episode("h2-e3", "h2-s3", "holdout-b", 3, "close", "u", "u"),
        procedure_episode("hf-e0", "hf-s0", "holdout-fail", 0, "open", "x", "x"),
        procedure_episode("hf-e1", "hf-s1", "holdout-fail", 1, "move", "x", "blocked"),
        procedure_episode("hf-e2", "hf-s2", "holdout-fail", 2, "check", "x", "x"),
        procedure_episode("hf-e3", "hf-s3", "holdout-fail", 3, "close", "x", "x"),
    ]
    for raw in rows[-4:]:
        raw["observation"] = {
            "success": False,
            "failure": {"reason": "blocked"},
        }
    for raw in rows:
        admitted, _ = _semantic_dispatch(
            state,
            {
                "operation": "admit-open-vocab-episode",
                "event_id": raw["event_id"],
                "source_revision_id": raw["source_revision_id"],
                "episode": raw,
            },
        )
        assert admitted["status"] == "supported"

    discovered, _ = _semantic_dispatch(
        state,
        {"operation": "discover-procedure", "max_candidates": 1},
    )
    assert discovered["status"] == "supported"
    request = discovered["opportunities"][0]["request"]
    assert [trace["trace_id"] for trace in request["holdout"]] == [
        "trajectory:holdout-fail"
    ]

    learned, _ = _semantic_dispatch(
        state,
        {
            "operation": "learn-procedure",
            "operation_id": "resident-procedure-holdout",
            **request,
        },
    )
    assert learned["status"] == "representation-insufficient"
    assert learned["candidates"][0]["statistics"]["unsafe_holdout_failures"] == [
        "trajectory:holdout-fail"
    ]


def test_autonomous_learning_scores_resident_outcomes():
    state = semantic_cognition_state()
    opportunity = {
        "candidate_id": "experience-construction",
        "learning_kind": "construction",
        "expected_gain": 1.0,
        "request": {
            "construction_id": "experience-location",
            "examples": [
                {
                    "text": "the key is in the drawer",
                    "bindings": {"item": "key", "place": "drawer"},
                },
                {
                    "text": "the cup is in the box",
                    "bindings": {"item": "cup", "place": "box"},
                },
            ],
            "meaning": {
                "object": {"$role": "place"},
                "relation": "located-in",
                "subject": {"$role": "item"},
            },
            "speech_act": "assertion",
        },
    }

    first, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-learn",
            "operation_id": "experience-cycle-one",
            "opportunities": [opportunity],
        },
    )
    assert first["status"] == "supported"

    second, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-learn",
            "operation_id": "experience-cycle-two",
            "opportunities": [opportunity],
        },
    )
    score = second["candidate_scores"][0]
    assert second["learning_experience"]["attempts"] == 1
    assert score["candidate_attempts"] == 1.0
    assert score["candidate_mean_reward"] == 1.0
    assert score["experience_adjustment"] > 0.0


def test_procedure_steps_select_feedback_branches():
    program = semantic_program_payload(
        program_kind="procedure",
        body={
            "effects": {},
            "failure_behavior": [],
            "postconditions": {},
            "roles": [],
            "steps": [
                {"action": {"name": "begin"}},
                {
                    "branches": [
                        {
                            "when": {
                                "context.procedure_feedback.status": "succeeded"
                            },
                            "step": {"action": {"name": "continue"}},
                        },
                        {
                            "when": {
                                "context.procedure_feedback.status": "failed"
                            },
                            "step": {"action": {"name": "recover"}},
                        },
                    ],
                    "default": {"action": {"name": "wait"}},
                },
            ],
        },
        max_horizon=2,
        max_branches=4,
        max_work=8,
    )

    initial = execute_semantic_program(program, {}, context={})
    assert initial["status"] == "supported"
    assert [step["action"]["name"] for step in initial["proposed_actions"]] == [
        "begin",
        "wait",
    ]
    assert initial["proposed_actions"][1]["branch_index"] is None

    recovered = execute_semantic_program(
        program,
        {},
        context={"procedure_feedback": {"status": "failed"}},
    )
    assert [step["action"]["name"] for step in recovered["proposed_actions"]] == [
        "begin",
        "recover",
    ]
    assert recovered["proposed_actions"][1]["branch_index"] == 1


def test_autonomous_agenda_prioritizes_pending_obligations():
    state = semantic_cognition_state()
    registered, _ = _semantic_dispatch(
        state,
        {
            "operation": "register",
            "kind": "Obligation",
            "record_id": "obligation:agenda-test",
            "payload": {
                "purpose": "prediction-assessment",
                "state": "pending",
            },
            "status": "active",
        },
    )
    obligation = registered["record"]

    agenda, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-test-cycle",
            "goal": "resolve what remains unknown",
        },
    )
    assert agenda["status"] == "supported"
    assert agenda["selected"]["kind"] == "resolve-obligation"
    assert agenda["selected"]["obligation"]["id"] == obligation["id"]
    assert agenda["selected"]["reason"] == "prediction-assessment"

    replay, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-test-cycle",
            "goal": "resolve what remains unknown",
        },
    )
    assert replay["replayed"] is True


def test_autonomous_agenda_honors_declared_obligation_priority():
    state = semantic_cognition_state()
    for record_id, priority in (
        ("obligation:lower-evidence", 0.25),
        ("obligation:higher-evidence", 0.75),
    ):
        _semantic_dispatch(
            state,
            {
                "operation": "register",
                "kind": "Obligation",
                "record_id": record_id,
                "payload": {
                    "purpose": "candidate-selection",
                    "priority": priority,
                    "state": "pending",
                },
                "status": "active",
            },
        )

    agenda, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-evidence-priority",
            "goal": "select from measured development evidence",
        },
    )

    assert agenda["selected"]["obligation"]["id"] == "obligation:higher-evidence"
    assert agenda["selected"]["priority"] == 1.75


def test_autonomous_curiosity_generates_prediction_error_goal():
    state = semantic_cognition_state()
    prediction, _ = _semantic_dispatch(
        state,
        {
            "operation": "register",
            "kind": "Assessment",
            "record_id": "prediction:curiosity-error",
            "payload": {
                "purpose": "prediction",
                "loss": 0.8,
            },
            "status": "assessed",
            "epistemic_kind": "observed",
        },
    )

    result, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-curiosity",
            "operation_id": "curiosity-error-cycle",
            "min_error": 0.2,
        },
    )
    assert result["status"] == "supported"
    assert result["goals"][0]["kind"] == "reduce-prediction-error"
    assert result["goals"][0]["source"]["id"] == prediction["record"]["id"]
    assert result["goals"][0]["request"]["operation"] == "query"

    replay, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-curiosity",
            "operation_id": "curiosity-error-cycle",
            "min_error": 0.2,
        },
    )
    assert replay["replayed"] is True


def test_autonomous_agenda_promotes_novel_observation_goal():
    state = semantic_cognition_state()
    observed, _ = _semantic_dispatch(
        state,
        {
            "operation": "observe",
            "delivery_id": "curiosity-delivery",
            "event_id": "event:curiosity-observation",
            "observations": [{"value": {"temperature": 21.0}}],
        },
    )

    agenda, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-curiosity-cycle",
            "max_items": 4,
        },
    )
    assert agenda["status"] == "supported"
    assert agenda["curiosity_goal_count"] >= 1
    assert agenda["selected"]["kind"] == "curiosity-goal"
    assert agenda["selected"]["goal"]["source"]["id"] == observed["event"]["id"]
    assert agenda["selected"]["request"]["operation"] == "query"
    replay, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-curiosity-cycle",
            "max_items": 4,
        },
    )
    assert replay["replayed"] is True
    assert replay["curiosity_goal_count"] == agenda["curiosity_goal_count"]


def test_autonomous_perception_selects_goal_relevant_observation_channel():
    state = semantic_cognition_state()
    goal = {
        "goal_id": "goal:temperature",
        "kind": "reduce-prediction-error",
        "objective": {
            "kind": "reduce-prediction-error",
            "requested": ["temperature"],
        },
    }
    result, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-perception",
            "operation_id": "perception-temperature-cycle",
            "goal": goal,
            "channels": [
                {
                    "channel_id": "camera:wide",
                    "provides": ["shape"],
                    "cost": 0.0,
                    "reliability": 1.0,
                    "request": {"adapter": "camera"},
                },
                {
                    "channel_id": "thermometer:ambient",
                    "provides": ["temperature"],
                    "cost": 2.0,
                    "reliability": 0.8,
                    "request": {"adapter": "thermometer", "scope": "ambient"},
                },
            ],
        },
    )
    assert result["status"] == "supported"
    assert result["selected_channel"]["channel_id"] == "thermometer:ambient"
    assert result["observation_request"]["request"]["adapter"] == "thermometer"
    assert result["channel_scores"][1]["coverage"] == 1.0

    replay, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-perception",
            "operation_id": "perception-temperature-cycle",
            "goal": goal,
            "channels": [
                {
                    "channel_id": "camera:wide",
                    "provides": ["shape"],
                    "cost": 0.0,
                    "reliability": 1.0,
                    "request": {"adapter": "camera"},
                },
                {
                    "channel_id": "thermometer:ambient",
                    "provides": ["temperature"],
                    "cost": 2.0,
                    "reliability": 0.8,
                    "request": {"adapter": "thermometer", "scope": "ambient"},
                },
            ],
        },
    )
    assert replay["replayed"] is True
    assert replay["selected_channel"]["channel_id"] == "thermometer:ambient"


def test_autonomous_agenda_turns_curiosity_into_active_perception_request():
    state = semantic_cognition_state()
    _semantic_dispatch(
        state,
        {
            "operation": "observe",
            "delivery_id": "active-perception-delivery",
            "event_id": "event:active-perception-observation",
            "observations": [{"value": {"temperature": 21.0}}],
        },
    )
    agenda, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-active-perception-cycle",
            "max_items": 1,
            "observation_channels": [
                {
                    "channel_id": "slow:generic",
                    "provides": ["shape"],
                    "cost": 5.0,
                    "reliability": 0.1,
                    "request": {"adapter": "generic"},
                },
                {
                    "channel_id": "focused:temperature",
                    "provides": ["temperature"],
                    "cost": 0.1,
                    "reliability": 0.9,
                    "request": {"adapter": "thermometer", "scope": "ambient"},
                },
            ],
        },
    )
    assert agenda["status"] == "supported"
    assert agenda["selected"]["kind"] == "active-perception"
    assert agenda["selected"]["request"]["channel_id"] == "focused:temperature"
    assert agenda["perception_event"]["kind"] == "Event"

    replay, _ = _semantic_dispatch(
        state,
        {
            "operation": "autonomous-agenda",
            "operation_id": "agenda-active-perception-cycle",
            "max_items": 1,
            "observation_channels": [
                {
                    "channel_id": "slow:generic",
                    "provides": ["shape"],
                    "cost": 0.0,
                    "reliability": 1.0,
                    "request": {"adapter": "generic"},
                },
                {
                    "channel_id": "focused:temperature",
                    "provides": ["temperature"],
                    "cost": 0.1,
                    "reliability": 0.9,
                    "request": {"adapter": "thermometer", "scope": "ambient"},
                },
            ],
        },
    )
    assert replay["replayed"] is True
    assert replay["selected"]["kind"] == "active-perception"
