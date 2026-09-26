"""Reconstruct grounded affect from canonical field records.

This module is deliberately pure.  Appraisal and regulation learning live in
the owner's semantic records and executable Programs; these helpers validate
eligible outcomes and project the current, dependency-supported view.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from cassi_field_atlas import FieldIntelligenceError, sha256_value

AFFECT_CONTEXT_SCHEMA = "cassifi.affect-context.v3"
AFFECT_CONCERN_SCHEMA = "cassifi.affect-concern.v1"
AFFECT_APPRAISAL_SCHEMA = "cassifi.affect-appraisal.v2"
AFFECT_REGULATION_SCHEMA = "cassifi.affect-regulation.v2"
AFFECT_OUTCOME_SCHEMA = "cassifi.affect-outcome.v1"
AFFECT_MODES = ("explore", "persist", "verify", "consolidate")
AFFECT_SIGNAL_NAMES = (
    "progress", "obstruction", "activation", "controllability",
    "uncertainty", "novelty", "capacity",
)
_NEUTRAL = {
    "progress": 0.0, "obstruction": 0.0, "activation": 0.0,
    "controllability": 0.5, "uncertainty": 0.5, "novelty": 0.0,
    "capacity": 1.0,
}
_INACTIVE = frozenset({"invalidated", "revoked", "retracted"})
_OUTCOME_KINDS = frozenset({
    "investigation", "computation", "retrieval", "source-study", "inquiry",
    "delegation", "teaching", "consolidation", "regulation", "capacity",
    "infrastructure",
})


def _number(
    value: Any, label: str, *, minimum: float = 0.0, maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldIntelligenceError("INVALID_AFFECT", f"{label} must be numeric")
    result = float(value)
    if (
        not math.isfinite(result) or result < minimum
        or (maximum is not None and result > maximum)
    ):
        raise FieldIntelligenceError("INVALID_AFFECT", f"{label} is outside its bounds")
    return result


def _reference(value: Any, label: str, *, nullable: bool = False) -> dict[str, Any] | None:
    if value is None and nullable:
        return None
    if (
        not isinstance(value, Mapping)
        or set(value) != {"id", "kind", "content_version"}
        or not isinstance(value.get("id"), str)
        or not isinstance(value.get("kind"), str)
        or isinstance(value.get("content_version"), bool)
        or not isinstance(value.get("content_version"), int)
        or value["content_version"] < 1
    ):
        raise FieldIntelligenceError("INVALID_AFFECT", f"{label} must be a semantic reference")
    return dict(value)


def _references(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FieldIntelligenceError("INVALID_AFFECT", f"{label} must be a reference list")
    return [
        dict(_reference(item, f"{label} item") or {})
        for item in value
    ]


def known_signal(name: str, value: Any, basis_refs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    minimum = -1.0 if name == "progress" else 0.0
    return {
        "status": "known",
        "value": _number(value, f"affect {name}", minimum=minimum, maximum=1.0),
        "basis_refs": _references(basis_refs, f"affect {name} basis_refs"),
    }


def unknown_signal(name: str) -> dict[str, Any]:
    if name not in AFFECT_SIGNAL_NAMES:
        raise FieldIntelligenceError("INVALID_AFFECT", "unknown affect signal name")
    return {"status": "unknown", "value": None, "basis_refs": []}


def validate_signals(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or set(value) != set(AFFECT_SIGNAL_NAMES):
        raise FieldIntelligenceError("INVALID_AFFECT", "affect signals must contain exactly seven dimensions")
    result: dict[str, dict[str, Any]] = {}
    for name in AFFECT_SIGNAL_NAMES:
        signal = value[name]
        if not isinstance(signal, Mapping) or set(signal) != {"status", "value", "basis_refs"}:
            raise FieldIntelligenceError("INVALID_AFFECT", f"affect {name} signal is malformed")
        if signal["status"] == "unknown":
            if signal["value"] is not None or signal["basis_refs"]:
                raise FieldIntelligenceError("INVALID_AFFECT", f"unknown affect {name} must have null value and no basis")
            result[name] = unknown_signal(name)
        elif signal["status"] == "known":
            result[name] = known_signal(name, signal["value"], signal["basis_refs"])
        else:
            raise FieldIntelligenceError("INVALID_AFFECT", f"affect {name} status is unsupported")
    return result


def affect_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Decode one eligible, actually executed outcome without inventing meaning."""
    payload = record["payload"]
    if record.get("status") in _INACTIVE:
        raise FieldIntelligenceError("INVALID_AFFECT", "affect evidence is inactive")
    learning = payload.get("autonomous_learning")
    if (
        record["kind"] == "Event" and isinstance(learning, Mapping)
        and record.get("derivation", {}).get("operation") == "autonomous-learn"
    ):
        result = learning.get("learning")
        if not isinstance(result, Mapping) or not learning.get("selected_candidate_id"):
            raise FieldIntelligenceError("INVALID_AFFECT", "a learning decision is not a learning outcome")
        status = result.get("status")
        rewards = {
            "supported": 1.0, "active": 1.0, "completed": 1.0,
            "candidate": 0.25, "resource-exhausted": -0.5,
            "representation-insufficient": -1.0, "support-gap": -1.0,
        }
        if status not in rewards:
            raise FieldIntelligenceError("INVALID_AFFECT", "learning outcome has no grounded appraisal")
        return {
            "experience_key": f"learning:{record['id']}", "kind": "acquisition",
            "reward": rewards[status],
            "capacity": 0.0 if status == "resource-exhausted" else 1.0,
            "measurement": None,
        }
    if (
        record["kind"] == "Assessment"
        and record.get("epistemic_kind") == "assessed"
        and payload.get("memory_role") == "recall-assessment"
    ):
        episode_ref = _reference(
            payload.get("episode_ref"), "recall assessment episode_ref"
        )
        use_ref = _reference(payload.get("use_ref"), "recall assessment use_ref")
        outcome_ref = _reference(
            payload.get("outcome_ref"), "recall assessment outcome_ref"
        )
        usefulness = _number(
            payload.get("usefulness"),
            "recall usefulness",
            minimum=-1.0,
            maximum=1.0,
        )
        assert episode_ref is not None and use_ref is not None and outcome_ref is not None
        return {
            "experience_key": (
                f"retrieval:{episode_ref['id']}:{episode_ref['content_version']}"
            ),
            "kind": "retrieval",
            "reward": usefulness,
            "capacity": 1.0,
            "measurement": {"usefulness": usefulness},
            "operation_ref": use_ref,
            "actual_result_ref": outcome_ref,
        }
    if (
        record["kind"] == "Assessment" and record.get("epistemic_kind") == "assessed"
        and payload.get("schema") == "cassifi.research-organism-campaign.v1"
        and payload.get("learning_mode") == "development"
        and isinstance(payload.get("source_revision_id"), str) and payload["source_revision_id"]
        and isinstance(payload.get("output_sha256"), str) and payload["output_sha256"]
        and isinstance(payload.get("metrics"), Mapping)
    ):
        metrics = payload["metrics"]
        return {
            "experience_key": f"research:{payload['source_revision_id']}",
            "kind": "research", "reward": None, "capacity": 1.0,
            "measurement": {
                "accuracy": _number(metrics.get("accuracy"), "research accuracy", maximum=1.0),
                "error": _number(metrics.get("mean_abs_error"), "research error"),
            },
        }
    report = payload if payload.get("schema") == "cassifi.affect-report.v1" else None
    if (
        record["kind"] == "Event"
        and record.get("epistemic_kind") == "attributed"
        and isinstance(report, Mapping)
        and isinstance(report.get("message_id"), str)
        and report["message_id"]
        and report.get("interpretation_status")
        in {"interpreted", "tentative", "restricted", "unknown"}
    ):
        return {
            "experience_key": f"cooperation:{report['message_id']}",
            "kind": "cooperation",
            "reward": None,
            "capacity": 1.0,
            "measurement": None,
            "source_evidence_roots": list(report.get("evidence_roots", [])),
        }
    outcome = payload.get("affect_outcome")
    if (
        record["kind"] == "Assessment" and record.get("epistemic_kind") == "assessed"
        and isinstance(outcome, Mapping) and outcome.get("schema") == AFFECT_OUTCOME_SCHEMA
        and outcome.get("outcome_kind") in _OUTCOME_KINDS
    ):
        operation_ref = _reference(outcome.get("operation_ref"), "affect outcome operation_ref")
        result_ref = _reference(outcome.get("actual_result_ref"), "affect outcome actual_result_ref")
        assert operation_ref is not None and result_ref is not None
        measurement = outcome.get("measurement")
        if measurement is not None and not isinstance(measurement, Mapping):
            raise FieldIntelligenceError("INVALID_AFFECT", "affect outcome measurement must be an object")
        return {
            "experience_key": str(outcome.get("experience_key") or f"outcome:{operation_ref['id']}"),
            "kind": str(outcome["outcome_kind"]),
            "reward": (
                None if outcome.get("progress") is None
                else _number(outcome["progress"], "outcome progress", minimum=-1.0, maximum=1.0)
            ),
            "capacity": (
                None if outcome.get("capacity") is None
                else _number(outcome["capacity"], "outcome capacity", maximum=1.0)
            ),
            "measurement": None if measurement is None else dict(measurement),
            "operation_ref": operation_ref,
            "actual_result_ref": result_ref,
        }
    raise FieldIntelligenceError(
        "INVALID_AFFECT", "affect requires an eligible executed outcome, not a decision, mood, or report"
    )


def _live_record(state: Mapping[str, Any], ref: Mapping[str, Any]) -> Mapping[str, Any] | None:
    history = state["records"].get(ref.get("id"), [])
    if not history:
        return None
    record = history[-1]
    if record["content_version"] != ref.get("content_version") or record["kind"] != ref.get("kind"):
        return None
    return None if record["status"] in _INACTIVE else record


def affect_appraisals(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = []
    for record_id in state["current"]["Event"]:
        record = state["records"][record_id][-1]
        value = record["payload"].get("affect_appraisal")
        if (
            not isinstance(value, Mapping)
            or value.get("schema") != AFFECT_APPRAISAL_SCHEMA
            or record.get("derivation", {}).get("operation") != "appraise-experience"
            or record["status"] in _INACTIVE
        ):
            continue
        source = _live_record(state, value["experience_ref"])
        if source is not None:
            rows.append(record)
    rows.sort(key=lambda record: (record["created_at"], record["id"]))
    live: list[Mapping[str, Any]] = []
    accepted: set[tuple[str, int]] = set()
    for record in rows:
        supported = True
        for ref in record["dependencies"]:
            dependency = _live_record(state, ref)
            if dependency is None or (
                "affect_appraisal" in dependency["payload"]
                and (ref["id"], ref["content_version"]) not in accepted
            ):
                supported = False
                break
        if supported:
            validate_signals(record["payload"]["affect_appraisal"]["signals"])
            live.append(record)
            accepted.add((record["id"], record["content_version"]))
    return live


def appraisal_signals(
    evidence: Mapping[str, Any],
    prior: list[Mapping[str, Any]],
    *,
    evidence_ref: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    measurement = evidence["measurement"]
    prior_measurement = next(
        (
            row["payload"]["affect_appraisal"].get("measurement")
            for row in reversed(prior)
            if row["payload"]["affect_appraisal"].get("measurement") is not None
        ),
        None,
    )
    if measurement is None:
        progress = evidence.get("reward")
        obstruction = None if progress is None else max(0.0, -float(progress))
        uncertainty = 1.0 / (1.0 + len(prior))
    elif "accuracy" in measurement and "error" in measurement:
        progress = (
            None if prior_measurement is None
            else (
                float(prior_measurement["error"]) - float(measurement["error"])
            ) / max(float(prior_measurement["error"]), float(measurement["error"]), 1e-12)
        )
        obstruction = 1.0 - _number(measurement["accuracy"], "measurement accuracy", maximum=1.0)
        uncertainty = max(obstruction, 1.0 / (1.0 + len(prior)))
    else:
        progress = evidence.get("reward")
        obstruction = None
        uncertainty = 1.0 / (1.0 + len(prior))
    novelty = 1.0 / (1.0 + len(prior))
    activation = min(
        1.0,
        ((0.0 if progress is None else abs(float(progress)))
         + (0.0 if obstruction is None else obstruction) + novelty) / 2.0,
    )
    controllability = (
        None if progress is None and obstruction is None
        else max(0.0, min(1.0, 0.5 + 0.5 * float(progress or 0.0) - 0.25 * float(obstruction or 0.0)))
    )
    values = {
        "progress": progress, "obstruction": obstruction, "activation": activation,
        "controllability": controllability, "uncertainty": uncertainty,
        "novelty": novelty, "capacity": evidence.get("capacity"),
    }
    return {
        name: (
            unknown_signal(name) if value is None
            else known_signal(name, value, [evidence_ref])
        )
        for name, value in values.items()
    }


def projection_key(
    *, owner_lineage: str, experience_key: str, project_id: str,
    question_ref: Mapping[str, Any] | None, object_refs: Sequence[Mapping[str, Any]],
    goal_ref: Mapping[str, Any] | None,
) -> str:
    return sha256_value({
        "owner_lineage": owner_lineage,
        "experience_key": experience_key,
        "project_id": project_id,
        "question_id": None if question_ref is None else question_ref["id"],
        "object_ids": sorted(ref["id"] for ref in object_refs),
        "goal_id": None if goal_ref is None else goal_ref["id"],
    })


def affect_concern_ref(
    *, project_id: str, question_ref: Mapping[str, Any] | None,
    object_refs: Sequence[Mapping[str, Any]], goal_ref: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the stable, version-aware identity of one bound concern."""
    if not isinstance(project_id, str) or not project_id:
        raise FieldIntelligenceError("INVALID_AFFECT", "affect concern project_id is invalid")
    question = _reference(question_ref, "affect concern question_ref", nullable=True)
    objects = _references(object_refs, "affect concern object_refs")
    goal = _reference(goal_ref, "affect concern goal_ref", nullable=True)
    objects.sort(key=lambda ref: (ref["id"], ref["kind"], ref["content_version"]))
    unique: dict[tuple[str, str, int], dict[str, Any]] = {
        (ref["id"], ref["kind"], ref["content_version"]): ref for ref in objects
    }
    objects = list(unique.values())
    identity = {
        "project_id": project_id,
        "question_id": None if question is None else question["id"],
        "object_ids": sorted({ref["id"] for ref in objects}),
        "goal_id": None if goal is None else goal["id"],
    }
    return {
        "concern_id": sha256_value(identity),
        "project_id": project_id,
        "question_ref": question,
        "object_refs": objects,
        "goal_ref": goal,
    }


def affect_concern_id(
    *, project_id: str, question_ref: Mapping[str, Any] | None,
    object_refs: Sequence[Mapping[str, Any]], goal_ref: Mapping[str, Any] | None,
) -> str:
    return str(affect_concern_ref(
        project_id=project_id, question_ref=question_ref,
        object_refs=object_refs, goal_ref=goal_ref,
    )["concern_id"])


def _unique_refs(refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique = {
        (ref["id"], ref["kind"], ref["content_version"]): dict(ref)
        for ref in refs
    }
    return [unique[key] for key in sorted(unique)]


def _concern_projection(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, tuple[dict[str, Any], list[Mapping[str, Any]]]] = {}
    for row in rows:
        value = row["payload"]["affect_appraisal"]
        concern_ref = affect_concern_ref(
            project_id=value["project_id"],
            question_ref=value.get("question_ref"),
            object_refs=value.get("object_refs", []),
            goal_ref=value.get("goal_ref"),
        )
        slot = grouped.get(concern_ref["concern_id"])
        if slot is None:
            grouped[concern_ref["concern_id"]] = (concern_ref, [row])
        else:
            slot[1].append(row)

    projections: list[dict[str, Any]] = []
    for concern_id in sorted(grouped):
        concern_ref, source_rows = grouped[concern_id]
        live_rows = _deduplicate(source_rows)
        layer = _dimension_layer(live_rows)
        effective_dimensions: dict[str, dict[str, Any]] = {}
        for name in AFFECT_SIGNAL_NAMES:
            fast, slow = layer["fast"][name], layer["slow"][name]
            if fast["status"] != "known" or slow["status"] != "known":
                effective_dimensions[name] = unknown_signal(name)
                continue
            basis = _unique_refs([*fast["basis_refs"], *slow["basis_refs"]])
            effective_dimensions[name] = known_signal(
                name, 0.65 * fast["value"] + 0.35 * slow["value"], basis,
            )
        appraisal_refs = [
            {"id": row["id"], "kind": row["kind"],
             "content_version": int(row["content_version"])}
            for row in live_rows
        ]
        experience_refs = [
            row["payload"]["affect_appraisal"]["experience_ref"]
            for row in live_rows
        ]
        evidence_refs = [
            ref
            for row in live_rows
            for signal in validate_signals(
                row["payload"]["affect_appraisal"]["signals"]
            ).values()
            if signal["status"] == "known"
            for ref in signal["basis_refs"]
        ]
        projections.append({
            "schema": AFFECT_CONCERN_SCHEMA,
            **concern_ref,
            "concern_ref": dict(concern_ref),
            "fast": layer["fast"],
            "slow": layer["slow"],
            "timescales": {
                "immediate": layer["fast"],
                "ongoing": layer["slow"],
            },
            "effective_dimensions": effective_dimensions,
            "appraisal_refs": _unique_refs(appraisal_refs),
            "experience_refs": _unique_refs(experience_refs),
            "evidence_refs": _unique_refs(evidence_refs),
            "experience_keys": sorted({
                row["payload"]["affect_appraisal"]["experience_key"]
                for row in live_rows
            }),
            "count": len(live_rows),
        })
    return projections


def _dimension_layer(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    fast = {name: {"status": "unknown", "value": None, "basis_refs": []} for name in AFFECT_SIGNAL_NAMES}
    slow = {name: {"status": "unknown", "value": None, "basis_refs": []} for name in AFFECT_SIGNAL_NAMES}
    for record in rows:
        signals = validate_signals(record["payload"]["affect_appraisal"]["signals"])
        for name, signal in signals.items():
            if signal["status"] != "known":
                continue
            for target, rate in ((fast, 0.5), (slow, 0.125)):
                prior = _NEUTRAL[name] if target[name]["status"] == "unknown" else target[name]["value"]
                target[name] = {
                    "status": "known",
                    "value": prior + rate * (signal["value"] - prior),
                    "basis_refs": [*target[name]["basis_refs"], *signal["basis_refs"]],
                }
    return {"count": len(rows), "fast": fast, "slow": slow}


def _deduplicate(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        value = row["payload"]["affect_appraisal"]
        prior = latest.get(value["experience_key"])
        if prior is None or (row["created_at"], row["id"]) > (prior["created_at"], prior["id"]):
            latest[value["experience_key"]] = row
    return sorted(latest.values(), key=lambda row: (row["created_at"], row["id"]))


def _object_matches(
    state: Mapping[str, Any], ref: Mapping[str, Any], object_id: str,
) -> bool:
    if ref["id"] == object_id:
        return True
    record = _live_record(state, ref)
    return bool(
        record is not None
        and record["kind"] == "Binding"
        and record["payload"].get("binding_kind") == "affect-object"
        and record["payload"].get("external_identity") == object_id
    )


def affect_context(
    state: Mapping[str, Any], project_id: str = "global", object_id: str | None = None,
) -> dict[str, Any]:
    rows = affect_appraisals(state)
    project = [row for row in rows if row["payload"]["affect_appraisal"]["project_id"] == project_id]
    local = [
        row for row in project
        if object_id is not None and any(
            _object_matches(state, ref, object_id)
            for ref in row["payload"]["affect_appraisal"]["object_refs"]
        )
    ]
    selected = {
        "global": _deduplicate(rows),
        "project": _deduplicate(project),
        "local": _deduplicate(local),
    }
    dimensions = {name: _dimension_layer(scope) for name, scope in selected.items()}
    weights = (
        {"global": 0.1, "project": 0.2, "local": 0.7} if local
        else ({"global": 0.25, "project": 0.75} if project else {"global": 1.0})
    )
    effective_dimensions: dict[str, dict[str, Any]] = {}
    effective: dict[str, float] = {}
    for signal_name in AFFECT_SIGNAL_NAMES:
        terms: list[tuple[float, float, list[dict[str, Any]]]] = []
        for layer_name, weight in weights.items():
            layer = dimensions[layer_name]
            fast, slow = layer["fast"][signal_name], layer["slow"][signal_name]
            if fast["status"] == "known" and slow["status"] == "known":
                terms.append((
                    weight,
                    0.65 * fast["value"] + 0.35 * slow["value"],
                    [*fast["basis_refs"], *slow["basis_refs"]],
                ))
        if not terms:
            effective_dimensions[signal_name] = unknown_signal(signal_name)
            effective[signal_name] = _NEUTRAL[signal_name]
            continue
        total_weight = sum(term[0] for term in terms)
        value = sum(weight * value for weight, value, _ in terms) / total_weight
        basis = {
            (ref["id"], ref["kind"], ref["content_version"]): ref
            for _, _, refs in terms for ref in refs
        }
        effective_dimensions[signal_name] = known_signal(signal_name, value, list(basis.values()))
        effective[signal_name] = value
    p = effective
    scores = {
        "explore": p["novelty"] * p["controllability"] + 0.5 * p["uncertainty"],
        "persist": p["controllability"] + max(0.0, p["progress"]),
        "verify": p["obstruction"] + p["uncertainty"] * (1.0 - p["controllability"]),
        "consolidate": 1.0 - p["capacity"] + 0.5 * max(0.0, p["progress"]) * (1.0 - p["novelty"]),
    }
    learned = {mode: {"count": 0, "reward_sum": 0.0, "mean": 0.0} for mode in AFFECT_MODES}
    for record in local or project:
        value = record["payload"]["affect_appraisal"]
        mode = value.get("preceding_mode")
        progress = value["signals"]["progress"]
        if mode in learned and progress["status"] == "known":
            learned[mode]["count"] += 1
            learned[mode]["reward_sum"] += progress["value"]
    for mode, outcome in learned.items():
        if outcome["count"]:
            outcome["mean"] = outcome["reward_sum"] / outcome["count"]
            scores[mode] += 0.25 * outcome["mean"]
    mode = max(AFFECT_MODES, key=lambda name: (scores[name], -AFFECT_MODES.index(name)))
    return {
        "schema": AFFECT_CONTEXT_SCHEMA,
        "project_id": project_id,
        "object_id": object_id,
        "evidence_count": len({row["payload"]["affect_appraisal"]["experience_key"] for row in rows}),
        "layers": dimensions,
        "effective": effective,
        "effective_dimensions": effective_dimensions,
        "concerns": _concern_projection(rows),
        "regulation": {
            "mode": mode,
            "strength": min(1.0, len(selected["local"] or selected["project"] or selected["global"]) / 4.0),
            "scores": scores,
            "learned_outcomes": learned,
        },
    }


def affect_adjustment(context: Mapping[str, Any], features: Mapping[str, Any]) -> float:
    values = {
        key: _number(features.get(key, 0.0), f"affect {key}")
        for key in ("novelty", "uncertainty", "cost", "expected_gain", "risk")
    }
    mode = context["regulation"]["mode"]
    drive = {
        "explore": values["novelty"] + values["uncertainty"] - values["risk"],
        "persist": values["expected_gain"] - 0.25 * values["cost"],
        "verify": values["uncertainty"] - values["risk"] - 0.5 * values["novelty"],
        "consolidate": values["expected_gain"] - values["cost"] - values["novelty"],
    }[mode]
    return 0.5 * float(context["regulation"]["strength"]) * math.tanh(drive)
