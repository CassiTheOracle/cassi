"""Public semantic-kernel coverage for field-owned affect and regulation.

These tests intentionally exercise only the semantic operation contract.  Affect
is derived from canonical Event/Assessment records; it is not an independent
adaptive store and it does not alter observation, support, truth, permission,
or reporting semantics.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes
from cassi_field_cognition import semantic_cognition_kernel, semantic_cognition_state
from cassi_field_affect import affect_evidence
from cassi_field_regions import make_semantic_record


def step(state: Mapping[str, Any], **request: Any) -> tuple[dict[str, Any], Mapping[str, Any]]:
    transition = semantic_cognition_kernel(state, request, 4096)
    assert transition.status == "done"
    return transition.state, transition.output


def evidence_ref(record_id: str, kind: str = "Assessment", version: int = 1) -> dict[str, Any]:
    return {"id": record_id, "kind": kind, "content_version": version}


def research_record(
    record_id: str,
    *,
    source_revision_id: str,
    output_sha256: str,
    accuracy: float = 1.0,
    mean_abs_error: float = 0.0,
    content_version: int = 1,
    supersedes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fixture matching the Assessment payload emitted by ResearchOrganism._run_candidate."""
    payload = {
        "schema": "cassifi.research-organism-campaign.v1",
        "actor": "root",
        "candidate_id": "candidate-affect",
        "split": "development",
        "round": 1,
        "output_sha256": output_sha256,
        "source_revision_id": source_revision_id,
        "evidence_sha256": output_sha256,
        "metrics": {
            "accuracy": accuracy,
            "correct_steps": int(round(accuracy * 4)),
            "mean_abs_error": mean_abs_error,
            "steps": 4,
            "trace_sha256": output_sha256,
        },
        "learning": None,
        "learning_mode": "development",
    }
    return make_semantic_record(
        record_id=record_id,
        kind="Assessment",
        content_version=content_version,
        created_at=content_version,
        payload=payload,
        scope="research-organism:root",
        epistemic_kind="assessed",
        status="active",
        supersedes=supersedes,
        derivation={"operation": "research-organism:_run_candidate"},
    )
def test_recall_consequence_is_eligible_grounded_affect_evidence() -> None:
    episode_ref = {
        "id": "memory:recall:episode",
        "kind": "Event",
        "content_version": 2,
    }
    use_ref = {
        "id": "memory:use:decision",
        "kind": "Event",
        "content_version": 1,
    }
    outcome_ref = {
        "id": "memory:consequence:decision",
        "kind": "Event",
        "content_version": 1,
    }
    record = make_semantic_record(
        record_id="memory:assessment:decision",
        kind="Assessment",
        content_version=1,
        created_at=5,
        payload={
            "memory_role": "recall-assessment",
            "episode_ref": episode_ref,
            "use_ref": use_ref,
            "outcome_ref": outcome_ref,
            "usefulness": -0.25,
            "causal_claim": "not-established",
            "premise_truth_changed": False,
        },
        scope="field-qwen-work-memory",
        epistemic_kind="assessed",
        dependencies=(episode_ref, use_ref, outcome_ref),
        status="active",
        derivation={"operation": "recall-outcome"},
    )

    evidence = affect_evidence(record)

    assert evidence["kind"] == "retrieval"
    assert evidence["reward"] == -0.25
    assert evidence["measurement"] == {"usefulness": -0.25}
    assert evidence["operation_ref"] == use_ref
    assert evidence["actual_result_ref"] == outcome_ref




def learning_request(operation_id: str, *, project_id: str | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {
        "operation": "autonomous-learn",
        "operation_id": operation_id,
        "goal": "retain a reusable location method",
        "opportunities": [
            {
                "candidate_id": f"candidate:{operation_id}",
                "learning_kind": "construction",
                "expected_gain": 4.0,
                "novelty": 1.0,
                "request": {
                    "construction_id": f"construction:{operation_id}",
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
        ],
    }
    if project_id is not None:
        request["project_id"] = project_id
        request["object_id"] = "location-method"
    return request


def seed_assessment(
    state: Mapping[str, Any], record: Mapping[str, Any]
) -> dict[str, Any]:
    seeded = dict(state)
    seeded["records"] = {record["id"]: [dict(record)]}
    seeded["current"] = {**state["current"], "Assessment": {record["id"]: evidence_ref(record["id"])}}
    return json.loads(canonical_json_bytes(seeded))


def register_obligation(state: Mapping[str, Any], record_id: str, priority: float, affect: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"purpose": "candidate-selection", "priority": priority, "state": "pending"}
    if affect is not None:
        payload["affect"] = dict(affect)
    state, _ = step(
        state,
        operation="register",
        operation_id=f"register:{record_id}",
        kind="Obligation",
        record_id=record_id,
        payload=payload,
        status="active",
    )
    return state


def test_same_experience_under_different_operation_ids_appraises_once() -> None:
    state = semantic_cognition_state()
    state, learned = step(state, **learning_request("learn:grounded"))
    ref = learned["event"]

    state, first = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:first-id",
        evidence=ref,
        project_id="project-a",
        object_id="object-a",
    )
    state, second = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:second-id",
        evidence=ref,
        project_id="project-a",
        object_id="object-a",
    )

    assert first["context"]["evidence_count"] == 1
    assert second["context"]["evidence_count"] == 1
    assert second["context"]["layers"]["local"]["count"] == 1
    appraisal_rows = [
        history[-1]
        for history in state["records"].values()
        if history and isinstance(history[-1].get("payload"), Mapping)
        and "affect_appraisal" in history[-1]["payload"]
    ]
    assert len(appraisal_rows) == 1

    appraisal = state["records"][first["appraisal"]["id"]][-1]["payload"]["affect_appraisal"]
    assert appraisal["schema"] == "cassifi.affect-appraisal.v2"
    assert appraisal["context_ref"]["kind"] == "Value"
    assert appraisal["appraisal_program_ref"]["kind"] == "Program"
    assert set(appraisal["signals"]) == {
        "progress", "obstruction", "activation", "controllability",
        "uncertainty", "novelty", "capacity",
    }
    assert all(
        set(signal) == {"status", "value", "basis_refs"}
        for signal in appraisal["signals"].values()
    )
    choice = state["records"][first["regulation"]["id"]][-1]["payload"]["affect_regulation"]
    assert choice["schema"] == "cassifi.affect-regulation.v2"
    assert choice["selected_program_ref"]["kind"] == "Program"
    assert choice["proposed_actions"]
    obligation = state["records"][first["outcome_obligation"]["id"]][-1]
    assert obligation["payload"]["state"] == "pending"

def test_one_experience_can_have_distinct_stable_contextual_projections() -> None:
    record = research_record(
        "assessment:rebind", source_revision_id="revision:rebind", output_sha256="a" * 64
    )
    state = seed_assessment(semantic_cognition_state(), record)
    state, first = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:project-a",
        evidence=evidence_ref(record["id"]),
        project_id="project-a",
        object_id="object-a",
    )
    state, second = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:project-b",
        evidence=evidence_ref(record["id"]),
        project_id="project-b",
        object_id="object-b",
    )
    assert first["appraisal"]["id"] != second["appraisal"]["id"]
    assert first["context"]["evidence_count"] == 1
    assert second["context"]["evidence_count"] == 1
    first_concern = first["context"]["concerns"][0]
    second_concern = second["context"]["concerns"][0]
    assert first_concern["project_id"] == "project-a"
    assert second_concern["project_id"] == "project-b"
    assert first_concern["experience_refs"] == [evidence_ref(record["id"])]
    assert second_concern["experience_refs"] == [evidence_ref(record["id"])]
    assert first_concern["concern_id"] != second_concern["concern_id"]
    assert len([
        history[-1]
        for history in state["records"].values()
        if "affect_appraisal" in history[-1]["payload"]
    ]) == 2

def test_explicit_context_change_revises_same_affect_projection() -> None:
    record = research_record(
        "assessment:context-revision",
        source_revision_id="revision:context-revision",
        output_sha256="c" * 64,
    )
    state = seed_assessment(semantic_cognition_state(), record)
    state, first = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:context-revision:first",
        evidence=evidence_ref(record["id"]),
        project_id="context-project",
        object_id="context-object",
    )
    state, context = step(
        state,
        operation="register",
        operation_id="register:context-revision",
        record_id="value:explicit-affect-context",
        kind="Value",
        payload={"schema": "test.affect-context.v1", "condition": "changed"},
        status="active",
    )
    state, revised = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:context-revision:second",
        evidence=evidence_ref(record["id"]),
        project_id="context-project",
        object_id="context-object",
        context_ref=context["record"],
    )
    assert revised["appraisal"]["id"] == first["appraisal"]["id"]
    assert revised["appraisal"]["content_version"] == 2
    history = state["records"][first["appraisal"]["id"]]
    appraisal = history[-1]["payload"]["affect_appraisal"]
    assert appraisal["origin"] == "live"
    assert appraisal["revises_ref"] == first["appraisal"]



def test_introspection_and_regulation_refs_cannot_become_evidence() -> None:
    state = semantic_cognition_state()
    state, inspected = step(
        state,
        operation="affect-state",
        operation_id="affect:introspection",
    )
    context = inspected["context"]
    assert context["project_id"] == "global"
    assert context["object_id"] is None
    assert context["schema"] == "cassifi.affect-context.v3"
    assert context["concerns"] == []
    assert context["evidence_count"] == 0
    assert context["regulation"]["strength"] == 0.0
    assert context["regulation"]["mode"] in {"explore", "persist", "verify", "consolidate"}
    for layer in context["layers"].values():
        for timescale in ("fast", "slow"):
            for signal in layer[timescale].values():
                assert signal == {
                    "status": "unknown", "value": None, "basis_refs": [],
                }
    for name, value in context["effective"].items():
        if name == "progress":
            assert -1.0 <= value <= 1.0
        else:
            assert 0.0 <= value <= 1.0
    with pytest.raises(FieldIntelligenceError):
        step(
            state,
            operation="appraise-experience",
            operation_id="appraise:introspection",
            evidence=inspected["context"],
            project_id="project-a",
            object_id="object-a",
        )

    state, regulated = step(
        state,
        operation="regulate-affect",
        operation_id="regulate:empty",
        project_id="project-a",
        object_id="object-a",
    )
    with pytest.raises(FieldIntelligenceError):
        step(
            state,
            operation="appraise-experience",
            operation_id="appraise:regulation",
            evidence=regulated["regulation"],
            project_id="project-a",
            object_id="object-a",
        )


def test_revoked_or_revised_evidence_does_not_remain_trusted() -> None:
    original = research_record(
        "assessment:withdrawn", source_revision_id="revision:withdrawn", output_sha256="b" * 64
    )
    state = seed_assessment(semantic_cognition_state(), original)
    state, _ = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:withdrawn",
        evidence=evidence_ref(original["id"]),
        project_id="project-a",
        object_id="object-a",
    )
    state, _ = step(
        state,
        operation="revoke",
        operation_id="revoke:withdrawn",
        target=evidence_ref(original["id"]),
        reason="research-world evidence was withdrawn",
    )
    state, context = step(
        state,
        operation="affect-state",
        operation_id="affect:after-revoke",
        project_id="project-a",
        object_id="object-a",
    )
    assert context["context"]["evidence_count"] == 0

    revised = research_record(
        "assessment:revision", source_revision_id="revision:revision", output_sha256="c" * 64
    )
    state = seed_assessment(semantic_cognition_state(), revised)
    state, _ = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:revision-old",
        evidence=evidence_ref(revised["id"]),
        project_id="project-a",
        object_id="object-a",
    )
    state, corrected = step(
        state,
        operation="correct",
        operation_id="correct:revision",
        target=evidence_ref(revised["id"]),
        correction_id="revision-correction",
        replacement={"metrics": {"accuracy": 0.5, "mean_abs_error": 1.0}},
    )
    assert corrected["current"]["content_version"] == 2
    state, context = step(
        state,
        operation="affect-state",
        operation_id="affect:after-revision",
        project_id="project-a",
        object_id="object-a",
    )
    assert context["context"]["evidence_count"] == 0


def test_assessed_research_world_fixture_is_admitted_but_frozen_reporting_is_refused() -> None:
    record = research_record(
        "assessment:development", source_revision_id="revision:development", output_sha256="d" * 64,
        accuracy=0.75, mean_abs_error=0.25,
    )
    state = seed_assessment(semantic_cognition_state(), record)
    state, result = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:development",
        evidence=evidence_ref(record["id"]),
        project_id="research",
        object_id="candidate-affect",
    )
    assert result["context"]["evidence_count"] == 1
    assert result["appraisal"]["kind"] == "Event"

    frozen = research_record(
        "assessment:frozen", source_revision_id="revision:frozen", output_sha256="e" * 64
    )
    frozen["payload"]["learning_mode"] = "frozen-reporting"
    frozen_state = seed_assessment(semantic_cognition_state(), frozen)
    with pytest.raises(FieldIntelligenceError):
        step(
            frozen_state,
            operation="appraise-experience",
            operation_id="appraise:frozen",
            evidence=evidence_ref(frozen["id"]),
            project_id="research",
            object_id="candidate-affect",
        )


def test_save_reload_preserves_affect_context_and_learning_selection() -> None:
    state = semantic_cognition_state()
    state, learned = step(
        state,
        **learning_request("learn:persistent", project_id="project-persistent"),
    )
    selected_id = learned["selected"]["candidate_id"]
    state, before = step(
        state,
        operation="affect-state",
        operation_id="affect:before-reload",
        project_id="project-persistent",
        object_id="location-method",
    )
    reloaded = json.loads(canonical_json_bytes(state))
    same_next_request = learning_request("learn:next", project_id="project-persistent")
    original_after, original_choice = step(state, **same_next_request)
    reloaded_after, reloaded_choice = step(reloaded, **same_next_request)
    assert original_choice["selected"] == reloaded_choice["selected"]
    assert original_choice["selected"]["candidate_id"] != selected_id
    _, after = step(
        reloaded_after,
        operation="affect-state",
        operation_id="affect:after-reload",
        project_id="project-persistent",
        object_id="location-method",
    )
    assert after["context"]["evidence_count"] == before["context"]["evidence_count"] + 1
    assert original_after["current"]["Event"] == reloaded_after["current"]["Event"]


def test_two_projects_keep_distinct_local_affect_states() -> None:
    first = research_record("assessment:project-a", source_revision_id="revision:a", output_sha256="f" * 64, accuracy=1.0, mean_abs_error=0.0)
    second = research_record("assessment:project-b", source_revision_id="revision:b", output_sha256="0" * 64, accuracy=0.25, mean_abs_error=2.0)
    state = seed_assessment(semantic_cognition_state(), first)
    state["records"][second["id"]] = [second]
    state["current"]["Assessment"][second["id"]] = evidence_ref(second["id"])
    state, _ = step(state, operation="appraise-experience", operation_id="appraise:project-a", evidence=evidence_ref(first["id"]), project_id="project-a", object_id="object-a")
    state, _ = step(state, operation="appraise-experience", operation_id="appraise:project-b", evidence=evidence_ref(second["id"]), project_id="project-b", object_id="object-b")
    _, first_context = step(state, operation="affect-state", operation_id="affect:project-a", project_id="project-a", object_id="object-a")
    _, second_context = step(state, operation="affect-state", operation_id="affect:project-b", project_id="project-b", object_id="object-b")
    assert first_context["context"]["layers"]["local"]["count"] == 1
    assert second_context["context"]["layers"]["local"]["count"] == 1
    assert first_context["context"]["effective"] != second_context["context"]["effective"]


def test_grounded_experience_can_change_agenda_choice_without_changing_obligations() -> None:
    record = research_record("assessment:agenda", source_revision_id="revision:agenda", output_sha256="1" * 64, accuracy=1.0, mean_abs_error=0.0)
    baseline = seed_assessment(semantic_cognition_state(), record)

    affect_a = {"project_id": "agenda-project", "object_id": "agenda-object", "novelty": 1.0, "uncertainty": 0.0, "cost": 0.0, "expected_gain": 0.0}
    affect_b = {"project_id": "agenda-project", "object_id": "agenda-object", "novelty": 0.0, "uncertainty": 0.0, "cost": 0.0, "expected_gain": 0.0}
    baseline = register_obligation(baseline, "obligation:explore", 0.45, affect_a)
    baseline = register_obligation(baseline, "obligation:steady", 0.50, affect_b)
    experienced, _ = step(json.loads(canonical_json_bytes(baseline)), operation="appraise-experience", operation_id="appraise:agenda", evidence=evidence_ref(record["id"]), project_id="agenda-project", object_id="agenda-object")
    for record_id in (record["id"], "obligation:explore", "obligation:steady"):
        assert baseline["records"][record_id] == experienced["records"][record_id]

    _, baseline_agenda = step(baseline, operation="autonomous-agenda", operation_id="agenda:baseline", project_id="agenda-project")
    _, experienced_agenda = step(experienced, operation="autonomous-agenda", operation_id="agenda:experienced", project_id="agenda-project")
    assert {row["obligation"]["id"] for row in baseline_agenda["agenda"]} == {"obligation:explore", "obligation:steady"}
    experienced_ids = {
        row["obligation"]["id"] for row in experienced_agenda["agenda"]
    }
    assert {"obligation:explore", "obligation:steady"} <= experienced_ids
    assert any(item.startswith("obligation:affect-outcome:") for item in experienced_ids)
    baseline_scores = {row["obligation"]["id"]: row["priority"] for row in baseline_agenda["agenda"]}
    experienced_scores = {
        row["obligation"]["id"]: row["priority"]
        for row in experienced_agenda["agenda"]
        if row["obligation"]["id"] in baseline_scores
    }
    assert experienced_scores != baseline_scores
    assert baseline_agenda["selected"]["obligation"]["id"] != experienced_agenda["selected"]["obligation"]["id"]

def test_regulation_learns_from_a_later_outcome_not_from_its_own_record() -> None:
    first = research_record(
        "assessment:regulated:first",
        source_revision_id="revision:regulated:first",
        output_sha256="2" * 64,
        accuracy=0.5,
        mean_abs_error=1.0,
    )
    second = research_record(
        "assessment:regulated:second",
        source_revision_id="revision:regulated:second",
        output_sha256="3" * 64,
        accuracy=1.0,
        mean_abs_error=0.0,
    )
    state = seed_assessment(semantic_cognition_state(), first)
    state, _ = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:regulated:first",
        evidence=evidence_ref(first["id"]),
        project_id="regulated",
        object_id="object",
    )
    state, regulated = step(
        state,
        operation="regulate-affect",
        operation_id="regulate:decision",
        project_id="regulated",
        object_id="object",
    )
    assert all(
        value["count"] == 0
        for value in regulated["context"]["regulation"]["learned_outcomes"].values()
    )
    state, _ = step(
        state,
        operation="register",
        operation_id="register:regulated:second",
        kind="Assessment",
        record_id=second["id"],
        payload=second["payload"],
        status="active",
        epistemic_kind="assessed",
        scope="research-organism:root",
    )
    state, after = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:regulated:second",
        evidence=evidence_ref(second["id"]),
        project_id="regulated",
        object_id="object",
    )
    learned = after["context"]["regulation"]["learned_outcomes"]
    assert sum(value["count"] for value in learned.values()) == 1
    assert after["context"]["regulation"]["mode"] in {
        "explore",
        "persist",
        "verify",
        "consolidate",
    }
    assert regulated["regulation"]["kind"] == "Event"

def test_regulation_outcome_joins_actual_action_result_and_resolves_once() -> None:
    record = research_record(
        "assessment:outcome", source_revision_id="revision:outcome",
        output_sha256="4" * 64, accuracy=1.0, mean_abs_error=0.0,
    )
    state = seed_assessment(semantic_cognition_state(), record)
    state, appraised = step(
        state,
        operation="appraise-experience",
        operation_id="appraise:outcome",
        evidence=evidence_ref(record["id"]),
        project_id="outcome-project",
        object_id="outcome-object",
    )
    choice = state["records"][appraised["regulation"]["id"]][-1][
        "payload"
    ]["affect_regulation"]
    action = choice["proposed_actions"][0]
    action_record_id = "event:actual-affect-action"
    state, _ = step(
        state,
        operation="register",
        operation_id="register:actual-affect-action",
        record_id=action_record_id,
        kind="Event",
        payload={
            "affect_action": {
                "schema": "cassifi.affect-action.v1",
                "episode_id": choice["episode_id"],
                "action_id": action["action_id"],
                "operation": action["operation"],
                "status": "executed",
            }
        },
        status="active",
    )
    result = research_record(
        "assessment:actual-result",
        source_revision_id="revision:actual-result",
        output_sha256="5" * 64,
        accuracy=1.0,
        mean_abs_error=0.0,
    )
    state, _ = step(
        state,
        operation="register",
        operation_id="register:actual-result",
        record_id=result["id"],
        kind="Assessment",
        payload=result["payload"],
        status="active",
    )
    state, assessed = step(
        state,
        operation="assess-affect-outcome",
        operation_id="assess:affect-outcome",
        outcome_obligation_ref=appraised["outcome_obligation"],
        actual_action_refs=[
            {"id": action_record_id, "kind": "Event", "content_version": 1},
        ],
        actual_result_refs=[evidence_ref(result["id"])],
        consequence={
            "status": "observed",
            "progress": 0.5,
            "information_gain": 1.0,
            "capability_change": 0.25,
            "cost": {"resident_steps": 1},
            "limitations": [],
        },
        attribution="association",
    )
    assessment = state["records"][assessed["assessment"]["id"]][-1]["payload"]
    assert assessment["choice_ref"] == appraised["regulation"]
    assert assessment["covered_action_ids"] == [action["action_id"]]
    obligation = state["records"][appraised["outcome_obligation"]["id"]][-1]
    assert obligation["payload"]["state"] == "resolved"
    with pytest.raises(FieldIntelligenceError, match="not pending"):
        step(
            state,
            operation="assess-affect-outcome",
            operation_id="assess:affect-outcome:duplicate",
            outcome_obligation_ref=assessed["outcome_obligation"],
            actual_action_refs=[
                {"id": action_record_id, "kind": "Event", "content_version": 1},
            ],
            actual_result_refs=[evidence_ref(result["id"])],
            consequence={"status": "observed"},
            attribution="association",
        )


def test_legacy_affect_choice_migrates_once_with_unknown_consequence_links() -> None:
    state = semantic_cognition_state()
    state, _ = step(
        state,
        operation="register",
        operation_id="register:legacy-affect",
        record_id="event:legacy-affect-choice",
        kind="Event",
        payload={
            "affect_regulation": {
                "schema": "cassifi.affect-regulation.v1",
                "project_id": "legacy-project",
                "object_id": "legacy-object",
                "mode": "verify",
                "strength": 0.4,
                "scores": {"verify": 0.8},
            }
        },
        status="active",
    )
    state, _ = step(
        state,
        operation="affect-state",
        operation_id="affect:migrate:first",
        project_id="legacy-project",
        object_id="legacy-object",
    )
    history = state["records"]["event:legacy-affect-choice"]
    assert len(history) == 2
    migrated = history[-1]["payload"]["affect_regulation"]
    assert migrated["schema"] == "cassifi.affect-regulation.v2"
    assert migrated["origin"] == "migrated"
    assert migrated["migration"]["unknown_fields"] == [
        "goal_ref", "actual_action_refs", "actual_result_refs",
        "consequence_assessment_ref",
    ]
    assert migrated["proposed_actions"] == []
    assert migrated["outcome_obligation_ref"] is None
    record_count = len(state["records"])
    state, _ = step(
        state,
        operation="affect-state",
        operation_id="affect:migrate:again",
        project_id="legacy-project",
        object_id="legacy-object",
    )
    assert len(state["records"]) == record_count


def test_grounded_regulation_keeps_working_as_concern_history_grows() -> None:
    state = semantic_cognition_state()
    for role in ("question", "goal"):
        state, _ = step(
            state,
            operation="register",
            operation_id=f"register:long-lived:{role}",
            kind="Value",
            record_id=f"value:long-lived:{role}",
            payload={"role": role, "meaning": "investigate measured resonance"},
            status="active",
        )
    concern_refs = {
        "question_ref": evidence_ref("value:long-lived:question", "Value"),
        "goal_ref": evidence_ref("value:long-lived:goal", "Value"),
    }
    for index in range(32):
        record = research_record(
            f"assessment:long-lived:{index}",
            source_revision_id=f"revision:long-lived:{index}",
            output_sha256=f"{index + 1:064x}",
        )
        state, _ = step(
            state,
            operation="register",
            operation_id=f"register:long-lived:assessment:{index}",
            record_id=record["id"],
            kind="Assessment",
            payload=record["payload"],
            status="active",
            epistemic_kind="assessed",
            scope="research-organism:root",
        )
        state, appraised = step(
            state,
            operation="appraise-experience",
            operation_id=f"appraise:long-lived:{index}",
            evidence=evidence_ref(record["id"]),
            project_id="long-lived",
            **concern_refs,
        )
    assert appraised["regulation"]["kind"] == "Event"
    assert appraised["context"]["evidence_count"] == 32
    concern = next(
        row for row in appraised["context"]["concerns"]
        if row["concern_ref"]["question_ref"] == concern_refs["question_ref"]
    )
    assert evidence_ref(record["id"]) in concern["experience_refs"]
