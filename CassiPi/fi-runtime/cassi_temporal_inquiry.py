"""Pure, bounded inquiry over a learned :class:`TemporalField`.

The selector treats every candidate predictive state as an empirical hypothesis.
It never supplies hypotheses, reads hidden scenario labels, mutates the field, or
stores adaptive state.  A returned policy is only an observation-contingent
plan; callers must consume the real observation and invoke this function again.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from cassi_temporal_field import TemporalField


_MAX_OPERATIONS = 64
_MAX_HORIZON = 8
_MAX_NODES = 4096
_MAX_FORBIDDEN = 64
_MAX_IDENTIFIER = 256


class TemporalInquiryError(ValueError):
    """Invalid inquiry input or an exceeded bounded search budget."""


@dataclass(frozen=True, slots=True)
class _Hypothesis:
    origin: int
    current: int


@dataclass(frozen=True, slots=True)
class _Readout:
    outcomes: Mapping[str, int]
    gap: bool
    unknown_successor: bool
    missing_states: tuple[int, ...]
    exposure: int


@dataclass(frozen=True, slots=True)
class _Transition:
    # Every outcome is represented by its empirically supported successor.
    outcomes: Mapping[str, int]

@dataclass(frozen=True, slots=True)
class _Plan:
    status: str
    policy: Mapping[str, Any] | None
    all_resolved: bool
    guaranteed_eliminations: int
    any_elimination: bool
    worst_cost: float
    worst_risk: float
    steps: int
    reason: str


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_IDENTIFIER:
        raise TemporalInquiryError(f"{name} must be a bounded nonempty string")
    return value


def _nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TemporalInquiryError(f"{name} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise TemporalInquiryError(f"{name} must be a finite nonnegative number")
    return result


def _bounded_int(value: Any, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise TemporalInquiryError(f"{name} must be an integer in [{lower},{upper}]")
    return value


def _sequence(value: Any, name: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TemporalInquiryError(f"{name} must be an ordered sequence")
    return tuple(value)


def _operations(memory: TemporalField, value: Any) -> tuple[Mapping[str, Any], ...]:
    rows = _sequence(value, "operations")
    if not rows or len(rows) > _MAX_OPERATIONS:
        raise TemporalInquiryError("operations must be nonempty and bounded")
    required = {"action", "cost", "risk", "authorized", "feasible"}
    allowed = required | {"acquisition_allowed"}
    known_actions = set(memory.action_ids)
    seen: set[str] = set()
    normalized: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or not required.issubset(row) or not set(row).issubset(allowed):
            raise TemporalInquiryError("operation schema is closed")
        action = _identifier(row["action"], "operation action")
        if action not in known_actions:
            raise TemporalInquiryError(f"unknown operation action: {action}")
        if action in seen:
            raise TemporalInquiryError("operation actions must be unique")
        seen.add(action)
        cost = _nonnegative(row["cost"], "operation cost")
        risk = _nonnegative(row["risk"], "operation risk")
        if not isinstance(row["authorized"], bool) or not isinstance(row["feasible"], bool):
            raise TemporalInquiryError("operation authorization and feasibility must be boolean")
        acquisition_allowed = row.get("acquisition_allowed", False)
        if not isinstance(acquisition_allowed, bool):
            raise TemporalInquiryError("operation acquisition_allowed must be boolean")
        normalized.append({
            "action": action,
            "cost": cost,
            "risk": risk,
            "authorized": row["authorized"],
            "feasible": row["feasible"],
            "acquisition_allowed": acquisition_allowed,
        })
    return tuple(normalized)


def _forbidden(memory: TemporalField, value: Any) -> frozenset[str]:
    rows = _sequence(value, "forbidden_observations")
    if len(rows) > _MAX_FORBIDDEN:
        raise TemporalInquiryError("forbidden observations exceed bounded capacity")
    known = set(memory.observation_ids)
    result: set[str] = set()
    for item in rows:
        name = _identifier(item, "forbidden observation")
        if name not in known:
            raise TemporalInquiryError(f"unknown forbidden observation: {name}")
        if name in result:
            raise TemporalInquiryError("forbidden observations must be unique")
        result.add(name)
    return frozenset(result)


def _goals(memory: TemporalField, value: Any) -> tuple[str, ...]:
    rows = _sequence(value, "goal_observations")
    if len(rows) > _MAX_FORBIDDEN:
        raise TemporalInquiryError("goal observations exceed bounded capacity")
    known = set(memory.observation_ids)
    result: list[str] = []
    for item in rows:
        name = _identifier(item, "goal observation")
        if name not in known:
            raise TemporalInquiryError(f"unknown goal observation: {name}")
        if name in result:
            raise TemporalInquiryError("goal observations must be unique")
        result.append(name)
    return tuple(result)


def _candidate_states(memory: TemporalField, participant_id: str | None) -> tuple[int, ...]:
    if participant_id is not None:
        _identifier(participant_id, "participant_id")
    try:
        raw = memory.candidate_states(participant_id=participant_id)
    except Exception as exc:
        raise TemporalInquiryError("unable to derive candidate states from the field") from exc
    values = _sequence(raw, "candidate states")
    if not values:
        return ()
    result: list[int] = []
    seen: set[int] = set()
    for state in values:
        if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state < memory.state_count:
            raise TemporalInquiryError("field returned an invalid candidate state")
        if state not in seen:
            seen.add(state)
            result.append(state)
    return tuple(result)


def _readout(memory: TemporalField, state: int, action: str) -> _Readout:
    """Read one field-owned support row, retaining gaps for acquisition."""
    try:
        projection = memory.at_state(state)
        prediction = projection.predict(action)
    except Exception as exc:
        raise TemporalInquiryError("field counterfactual prediction failed") from exc
    if not isinstance(prediction, Mapping):
        raise TemporalInquiryError("field prediction is invalid")
    support = prediction.get("support")
    if not isinstance(support, Mapping):
        support = {}
    outcomes = support.get("outcomes", ())
    if isinstance(outcomes, (str, bytes)) or not isinstance(outcomes, Sequence):
        raise TemporalInquiryError("field prediction support has invalid outcomes")
    known_observations = set(memory.observation_ids)
    result: dict[str, int] = {}
    exposure = 0
    raw_unknown_successor = support.get("unknown_successor", prediction.get("unknown_successor", False))
    unknown_successor = bool(raw_unknown_successor)
    if not isinstance(raw_unknown_successor, bool):
        raise TemporalInquiryError("field prediction unknown_successor is invalid")
    for row in outcomes:
        if not isinstance(row, Mapping) or set(row) != {"observation", "count", "next_state"}:
            raise TemporalInquiryError("field prediction support has an invalid outcome row")
        observation = row["observation"]
        next_state = row["next_state"]
        count = row["count"]
        if observation not in known_observations or observation in result:
            raise TemporalInquiryError("field prediction contains an invalid or duplicate observation")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise TemporalInquiryError("field prediction support count is invalid")
        exposure += count
        if next_state is None or next_state == -1:
            unknown_successor = True
            continue
        if isinstance(next_state, bool) or not isinstance(next_state, int) or not 0 <= next_state < memory.state_count:
            raise TemporalInquiryError("field prediction contains an invalid successor state")
        result[observation] = next_state
    raw_missing = support.get("missing_states", prediction.get("missing_states", ()))
    if isinstance(raw_missing, (str, bytes)) or not isinstance(raw_missing, Sequence):
        raise TemporalInquiryError("field prediction missing_states is invalid")
    missing: list[int] = []
    for missing_state in raw_missing:
        if isinstance(missing_state, bool) or not isinstance(missing_state, int) or not 0 <= missing_state < memory.state_count:
            raise TemporalInquiryError("field prediction contains an invalid missing state")
        if missing_state not in missing:
            missing.append(missing_state)
    gap = (
        prediction.get("supported") is not True
        or not result
        or unknown_successor
        or bool(missing)
    )
    return _Readout(result, gap, unknown_successor, tuple(missing), exposure)


def _prediction(memory: TemporalField, state: int, action: str) -> _Transition | None:
    readout = _readout(memory, state, action)
    if readout.gap:
        return None
    return _Transition(readout.outcomes)


def _ordered_outcomes(memory: TemporalField, outcomes: set[str]) -> tuple[str, ...]:
    order = {name: index for index, name in enumerate(memory.observation_ids)}
    return tuple(sorted(outcomes, key=lambda name: order[name]))


def _decision_signature(
    memory: TemporalField,
    hypotheses: tuple[_Hypothesis, ...],
    skill_id: str | None,
    *,
    goal_policy: tuple[Sequence[str], Sequence[str], Any, Any] | None = None,
    require_full_coverage: bool = False,
) -> tuple[Any, ...] | None:
    """Return a decision-relevant common signature, ignoring empirical weights."""
    if not hypotheses:
        return None
    if skill_id is not None or goal_policy is not None:
        if skill_id is not None:
            try:
                skill_ids = set(memory.skill_ids)
            except Exception as exc:
                raise TemporalInquiryError("field does not expose skill identifiers") from exc
            if skill_id not in skill_ids:
                raise TemporalInquiryError(f"unknown skill_id: {skill_id}")

        def policy_readout(state: int) -> Mapping[str, Any]:
            projection = memory.at_state(state)
            if skill_id is not None:
                return projection.skill_action(skill_id)
            assert goal_policy is not None
            goals, _, ranks, policy = goal_policy
            return projection._policy_action(  # noqa: SLF001
                skill_id=None,
                goals=goals,
                ranks=ranks,
                policy=policy,
            )

        rows: list[tuple[Any, ...]] = []
        for hypothesis in hypotheses:
            try:
                readout = policy_readout(hypothesis.current)
            except Exception as exc:
                raise TemporalInquiryError("field counterfactual goal readout failed") from exc
            if not isinstance(readout, Mapping):
                return None
            status, action = readout.get("status"), readout.get("action")
            if status == "proposed" and isinstance(action, str) and action in memory.action_ids:
                remaining = readout.get("remaining_steps")
                if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < 1:
                    return None
                if require_full_coverage:
                    if not memory._action_fully_observed(  # noqa: SLF001
                        hypothesis.current, memory.action_ids.index(action),
                    ):
                        return None
                    if hypothesis.current != hypothesis.origin:
                        try:
                            origin = policy_readout(hypothesis.origin)
                        except Exception as exc:
                            raise TemporalInquiryError(
                                "field counterfactual goal readout failed"
                            ) from exc
                        origin_remaining = origin.get("remaining_steps")
                        if (
                            origin.get("status") != "proposed"
                            or isinstance(origin_remaining, bool)
                            or not isinstance(origin_remaining, int)
                            or remaining >= origin_remaining
                        ):
                            return None
                rows.append(("proposed", action))
            elif status == "complete":
                rows.append(("complete", None))
            else:
                return None
        return rows[0] if all(row == rows[0] for row in rows[1:]) else None

    # Without a requested goal, only differences in empirical support and
    # successor states count.  Frequencies/probability fields are deliberately
    # ignored: surprise is not a decision criterion.
    rows = []
    for hypothesis in hypotheses:
        transitions: list[tuple[Any, ...]] = []
        supported = False
        for action in memory.action_ids:
            transition = _prediction(memory, hypothesis.current, action)
            if transition is None:
                transitions.append((action, False, ()))
            else:
                supported = True
                transitions.append((action, True, tuple(
                    (observation, transition.outcomes[observation])
                    for observation in _ordered_outcomes(memory, set(transition.outcomes))
                )))
        if not supported:
            return None
        rows.append(tuple(transitions))
    return rows[0] if all(row == rows[0] for row in rows[1:]) else None


def _transition(memory: TemporalField, hypotheses: tuple[_Hypothesis, ...], operation: Mapping[str, Any], forbidden: frozenset[str]) -> tuple[dict[str, tuple[_Hypothesis, ...]], str | None]:
    action = operation["action"]
    rows: list[tuple[_Hypothesis, _Transition]] = []
    for hypothesis in hypotheses:
        row = _prediction(memory, hypothesis.current, action)
        if row is None:
            return {}, "unsupported-action"
        if forbidden.intersection(row.outcomes):
            return {}, "forbidden-observation"
        rows.append((hypothesis, row))
    outcomes: set[str] = set()
    for _, row in rows:
        outcomes.update(row.outcomes)
    branches: dict[str, tuple[_Hypothesis, ...]] = {}
    for observation in _ordered_outcomes(memory, outcomes):
        branches[observation] = tuple(
            _Hypothesis(hypothesis.origin, row.outcomes[observation])
            for hypothesis, row in rows if observation in row.outcomes
        )
    return branches, None


def _plan_key(plan: _Plan) -> tuple[Any, ...]:
    # Resolution outranks elimination; then worst-case sequence burden.
    rank = 2 if plan.all_resolved else 1 if plan.any_elimination else 0
    return (-rank, -plan.guaranteed_eliminations, plan.worst_cost, plan.worst_risk, plan.steps, repr(plan.policy))


def _acquisition_gap(
    memory: TemporalField,
    states: tuple[int, ...],
    operation: Mapping[str, Any],
    forbidden: frozenset[str],
    *,
    carried_unknown: bool = False,
) -> tuple[Mapping[str, Any] | None, str | None]:
    """Return field-derived gap evidence for a host-authorized acquisition."""
    probe_states = states if states else tuple(range(memory.state_count))
    missing_states: set[int] = set()
    observed_outcomes: set[str] = set()
    unknown_successor = carried_unknown
    exposed_states = 0
    for state in probe_states:
        readout = _readout(memory, state, operation["action"])
        if forbidden.intersection(readout.outcomes):
            return None, "forbidden-observation"
        if readout.outcomes:
            exposed_states += 1
            observed_outcomes.update(readout.outcomes)
        if readout.gap:
            missing_states.update(readout.missing_states or (state,))
            unknown_successor = unknown_successor or readout.unknown_successor
    if not missing_states and not carried_unknown:
        return None, "supported-action"
    return {
        "missing_states": sorted(missing_states),
        "unknown_successor": unknown_successor,
        "actual_exposure": exposed_states > 0,
        "exposed_states": exposed_states,
        "outcome_count": len(observed_outcomes),
    }, None


def _select_acquisition(
    memory: TemporalField,
    states: tuple[int, ...],
    operations: tuple[Mapping[str, Any], ...],
    forbidden: frozenset[str],
    rejection_reasons: set[str],
    *,
    carried_unknown: bool = False,
    recent_actions: Sequence[str] = (),
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    candidates: list[tuple[tuple[Any, ...], Mapping[str, Any], Mapping[str, Any]]] = []
    for operation in operations:
        if not operation["authorized"]:
            rejection_reasons.add("authority")
            continue
        if not operation["feasible"]:
            rejection_reasons.add("feasibility")
            continue
        if not operation["acquisition_allowed"]:
            rejection_reasons.add("acquisition-permission")
            continue
        gap, refusal = _acquisition_gap(
            memory, states, operation, forbidden, carried_unknown=carried_unknown,
        )
        if refusal is not None:
            rejection_reasons.add(refusal)
            continue
        if gap is None:
            continue
        repeated = sum(action == operation["action"] for action in recent_actions)
        candidates.append(((
            repeated,
            -gap["outcome_count"],
            -gap["exposed_states"],
            len(gap["missing_states"]),
            float(operation["cost"]),
            float(operation["risk"]),
            operation["action"],
        ), operation, gap))
    if not candidates:
        return None
    _, operation, gap = min(candidates, key=lambda item: item[0])
    return operation, gap


def choose_temporal_inquiry(
    memory: TemporalField,
    *,
    participant_id: str | None = None,
    operations: Sequence[Mapping[str, Any]],
    skill_id: str | None = None,
    goal_observations: Sequence[str] = (),
    horizon: int = 3,
    max_nodes: int = _MAX_NODES,
    forbidden_observations: Sequence[str] = (),
) -> Mapping[str, Any]:
    """Choose a bounded next action and policy from field-derived hypotheses.

    The result is JSON-compatible and contains no probabilities.  ``policy`` is
    a tree whose ``branches`` are keyed by observed outcomes; each branch keeps
    origin candidate IDs and current counterfactual states so coalescing does
    not manufacture certainty.  Only the root ``action`` is executable by a
    runtime adapter.  A permitted support gap returns ``status="acquiring"``
    with ``decision_resolved=False``; missing empirical outcomes never certify
    a decision.  ``goal_observations`` derives a transient field policy without
    adding a persistent skill.
    """
    if not isinstance(memory, TemporalField):
        raise TemporalInquiryError("memory must be a TemporalField")
    if skill_id is not None:
        _identifier(skill_id, "skill_id")
    goals = _goals(memory, goal_observations)
    if skill_id is not None and goals:
        raise TemporalInquiryError("skill_id and goal_observations are mutually exclusive")
    horizon = _bounded_int(horizon, "horizon", 1, _MAX_HORIZON)
    max_nodes = _bounded_int(max_nodes, "max_nodes", 1, _MAX_NODES)
    ops = _operations(memory, operations)
    forbidden = _forbidden(memory, forbidden_observations)
    try:
        goal_policy = (
            memory._derive_skill_policy(  # noqa: SLF001
                goal_observations=goals,
                forbidden_observations=tuple(forbidden),
            )
            if goals
            else None
        )
    except Exception as exc:
        raise TemporalInquiryError("unable to derive a transient goal policy") from exc
    candidates = _candidate_states(memory, participant_id)
    rejection_reasons: set[str] = set()
    try:
        carried = memory.predict(ops[0]["action"], participant_id=participant_id)
        carried_unknown = carried["support"]["unknown_successor"]
        recent_actions = tuple(
            row["action"] for row in memory.history(participant_id=participant_id)[-len(ops):]
            if isinstance(row.get("action"), str)
        )
    except Exception as exc:
        raise TemporalInquiryError("unable to read carried uncertainty from the field") from exc
    if not isinstance(carried_unknown, bool):
        raise TemporalInquiryError("field prediction unknown_successor is invalid")
    base_result = {
        "status": "unresolved",
        "action": None,
        "policy": None,
        "candidate_states": list(candidates),
        "costs": {"cost": 0.0, "risk": 0.0, "worst_case_cost": 0.0, "worst_case_risk": 0.0},
        "work": {"nodes": 0, "max_nodes": max_nodes, "depth": 0},
        "reason": "no-candidate-states",
        "acquisition_allowed": False,
        "decision_resolved": False,
        "acquisition": {
            "host_permitted": False,
            "acquisition_allowed": False,
            "decision_resolved": False,
            "missing_states": [],
            "unknown_successor": False,
        },
    }
    try:
        available_skill_ids = set(memory.skill_ids) if skill_id is not None else set()
    except Exception as exc:
        raise TemporalInquiryError("field does not expose skill identifiers") from exc
    if skill_id is not None and skill_id not in available_skill_ids:
        raise TemporalInquiryError(f"unknown skill_id: {skill_id}")

    def acquisition_result() -> dict[str, Any] | None:
        selected_acquisition = _select_acquisition(
            memory, candidates, ops, forbidden, rejection_reasons,
            carried_unknown=carried_unknown, recent_actions=recent_actions,
        )
        if selected_acquisition is None:
            return None
        operation, gap = selected_acquisition
        result = dict(base_result)
        result.update({
            "status": "acquiring",
            "action": operation["action"],
            "acquisition_allowed": True,
            "decision_resolved": False,
            "policy": {
                "action": operation["action"],
                "kind": "acquisition",
                "branches": {},
                "candidate_states": list(candidates),
                "missing_states": gap["missing_states"],
            },
            "costs": {
                "cost": float(operation["cost"]),
                "risk": float(operation["risk"]),
                "worst_case_cost": float(operation["cost"]),
                "worst_case_risk": float(operation["risk"]),
            },
            "reason": "acquisition-permitted",
            "acquisition": {
                "host_permitted": True,
                "acquisition_allowed": True,
                "decision_resolved": False,
                "missing_states": gap["missing_states"],
                "unknown_successor": gap["unknown_successor"],
                "actual_exposure": gap["actual_exposure"],
            },
        })
        return result

    if not candidates:
        acquired = acquisition_result()
        return base_result if acquired is None else acquired
    require_full_coverage = bool(
        memory.context_status(participant_id=participant_id).get("uncovered_history")
    )
    if goal_policy is not None and not carried_unknown:
        goals_for_policy, _, ranks, policy = goal_policy
        try:
            direct = memory._policy_action(  # noqa: SLF001
                skill_id=None,
                goals=goals_for_policy,
                ranks=ranks,
                policy=policy,
                participant_id=participant_id,
            )
        except Exception as exc:
            raise TemporalInquiryError("field transient goal readout failed") from exc
        if direct.get("status") == "complete":
            completed = dict(base_result)
            completed.update({
                "status": "complete",
                "reason": "goal-observation-consumed",
                "decision_resolved": True,
            })
            return completed
        direct_action = direct.get("action")
        direct_operation = next(
            (
                operation for operation in ops
                if operation["action"] == direct_action
                and operation["authorized"]
                and operation["feasible"]
            ),
            None,
        )
        if direct.get("status") == "proposed" and direct_operation is not None:
            resolved = dict(base_result)
            resolved.update({
                "status": "resolving",
                "action": direct_action,
                "policy": {
                    "action": direct_action,
                    "kind": "transient-goal",
                    "branches": {},
                    "candidate_states": list(candidates),
                },
                "costs": {
                    "cost": float(direct_operation["cost"]),
                    "risk": float(direct_operation["risk"]),
                    "worst_case_cost": float(direct_operation["cost"]),
                    "worst_case_risk": float(direct_operation["risk"]),
                },
                "reason": "goal-directed-action",
                "decision_resolved": True,
            })
            return resolved
    singleton_decision = (
        (skill_id is None and goal_policy is None)
        or _decision_signature(
            memory,
            (_Hypothesis(candidates[0], candidates[0]),),
            skill_id,
            goal_policy=goal_policy,
            require_full_coverage=require_full_coverage,
        ) is not None
    )
    if len(candidates) == 1 and not carried_unknown and singleton_decision:
        acquired = acquisition_result()
        if acquired is not None:
            return acquired
        base_result["status"] = "not-needed"
        base_result["reason"] = "fewer-than-two-candidates"
        return base_result

    hypotheses = tuple(_Hypothesis(state, state) for state in candidates)
    nodes = 0

    def search(current: tuple[_Hypothesis, ...], depth: int, separated: bool) -> _Plan:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise TemporalInquiryError("inquiry search exceeded max_nodes")
        signature = _decision_signature(
            memory,
            current,
            skill_id,
            goal_policy=goal_policy,
            require_full_coverage=require_full_coverage,
        )
        # A singleton branch is certified by guaranteed hypothesis elimination
        # even when its successor has no further supported action.
        if len(current) == 1 and separated:
            return _Plan("resolved", None, True, len(hypotheses) - 1, True, 0.0, 0.0, 0, "decision-resolved")
        # A common signature is useful only when the inquiry has either reached
        # one hypothesis or actually filtered observations.  This prevents a
        # transition that merely coalesces distinct hypotheses from claiming
        # perfect information.
        if (
            signature is not None
            and (len(current) == 1 or separated)
            and not (carried_unknown and depth == 0)
        ):
            return _Plan("resolved", None, True, len(hypotheses) - len(current), separated, 0.0, 0.0, 0, "decision-resolved")
        if depth >= horizon:
            return _Plan("unresolved", None, False, len(hypotheses) - len(current), separated, 0.0, 0.0, 0, "horizon-exhausted")

        feasible = [
            row for row in ops
            if row["authorized"] and row["feasible"]
            and (not carried_unknown or row["acquisition_allowed"])
        ]
        if not feasible:
            if not any(row["authorized"] for row in ops):
                rejection_reasons.add("authority")
            elif not any(row["feasible"] for row in ops):
                rejection_reasons.add("feasibility")
            elif carried_unknown:
                rejection_reasons.add("acquisition-permission")
            return _Plan("unresolved", None, False, len(hypotheses) - len(current), separated, 0.0, 0.0, 0, "no-authorized-feasible-operation")

        plans: list[_Plan] = []
        for operation in feasible:
            branches, refusal = _transition(memory, current, operation, forbidden)
            if refusal is not None:
                rejection_reasons.add(refusal)
                continue
            if not branches:
                rejection_reasons.add("unsupported-action")
                continue
            child_plans: dict[str, _Plan] = {}
            all_resolved = True
            any_elimination = False
            guaranteed = len(hypotheses)
            worst_cost = float(operation["cost"])
            worst_risk = float(operation["risk"])
            steps = 1
            for observation, child in branches.items():
                child_separated = separated or len(child) < len(current)
                plan = search(child, depth + 1, child_separated)
                child_plans[observation] = plan
                all_resolved = all_resolved and plan.all_resolved
                any_elimination = any_elimination or child_separated or plan.any_elimination
                guaranteed = min(guaranteed, plan.guaranteed_eliminations)
                worst_cost = max(worst_cost, float(operation["cost"]) + plan.worst_cost)
                worst_risk = max(worst_risk, float(operation["risk"]) + plan.worst_risk)
                steps = max(steps, 1 + plan.steps)
            if not all_resolved and not any_elimination:
                plans.append(_Plan(
                    "unresolved",
                    None,
                    False,
                    guaranteed,
                    False,
                    worst_cost,
                    worst_risk,
                    steps,
                    "horizon-exhausted" if steps >= horizon else "no-distinguishing-inquiry",
                ))
                continue
            policy = {
                "action": operation["action"],
                "branches": {
                    observation: {
                        "candidate_states": [row.origin for row in child],
                        "current_states": [row.current for row in child],
                        "status": child_plans[observation].status,
                        "policy": child_plans[observation].policy,
                    }
                    for observation, child in branches.items()
                },
            }
            plans.append(_Plan(
                "resolving" if all_resolved else "partial",
                policy,
                all_resolved,
                guaranteed,
                any_elimination,
                worst_cost,
                worst_risk,
                steps,
                "decision-resolved" if all_resolved else "guaranteed-elimination" if guaranteed else "possible-elimination",
            ))
        if not plans:
            return _Plan("unresolved", None, False, len(hypotheses) - len(current), separated, 0.0, 0.0, 0,
                         "forbidden-observation" if "forbidden-observation" in rejection_reasons else "unsupported-action")
        return min(plans, key=_plan_key)

    selected = search(hypotheses, 0, False)
    if selected.policy is None:
        acquired = acquisition_result()
        if acquired is not None:
            acquired["work"] = {"nodes": nodes, "max_nodes": max_nodes, "depth": 0}
            return acquired
        if "authority" in rejection_reasons and not any(row["authorized"] for row in ops):
            reason = "authority"
        elif "feasibility" in rejection_reasons and not any(row["feasible"] for row in ops):
            reason = "feasibility"
        elif "forbidden-observation" in rejection_reasons:
            reason = "forbidden-observation"
        elif carried_unknown and "acquisition-permission" in rejection_reasons:
            reason = "acquisition-permission"
        elif selected.reason == "unsupported-action":
            reason = "unsupported-action"
        elif selected.reason == "horizon-exhausted":
            reason = "horizon-exhausted"
        else:
            reason = "no-distinguishing-inquiry"
        base_result["reason"] = reason
        base_result["work"] = {"nodes": nodes, "max_nodes": max_nodes, "depth": 0}
        return base_result
    if carried_unknown:
        policy = dict(selected.policy)
        policy["kind"] = "context-recovery"
        policy["candidate_states"] = list(candidates)
        base_result.update({
            "status": "acquiring",
            "action": policy["action"],
            "policy": policy,
            "acquisition_allowed": True,
            "decision_resolved": False,
            "costs": {
                "cost": selected.worst_cost,
                "risk": selected.worst_risk,
                "worst_case_cost": selected.worst_cost,
                "worst_case_risk": selected.worst_risk,
            },
            "work": {"nodes": nodes, "max_nodes": max_nodes, "depth": selected.steps},
            "reason": "context-recovery-sequence",
            "acquisition": {
                "host_permitted": True,
                "acquisition_allowed": True,
                "decision_resolved": False,
                "missing_states": [],
                "unknown_successor": True,
                "actual_exposure": True,
                "strategy": "bounded-sequence",
            },
        })
        return base_result
    base_result.update({
        "status": selected.status,
        "action": selected.policy["action"],
        "policy": selected.policy,
        "decision_resolved": selected.all_resolved,
        "costs": {
            "cost": selected.worst_cost,
            "risk": selected.worst_risk,
            "worst_case_cost": selected.worst_cost,
            "worst_case_risk": selected.worst_risk,
        },
        "work": {"nodes": nodes, "max_nodes": max_nodes, "depth": selected.steps},
        "reason": selected.reason,
    })
    return base_result


__all__ = ["TemporalInquiryError", "choose_temporal_inquiry"]
