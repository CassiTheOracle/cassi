"""Pure, bounded inquiry over a learned :class:`TemporalField`.

The selector treats every candidate predictive state as an empirical hypothesis.
It never supplies hypotheses, reads hidden scenario labels, mutates the field, or
stores adaptive state.  A returned policy is only an observation-contingent
plan; callers must consume the real observation and invoke this function again.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import cassi_field_regions
from cassi_temporal_field import TemporalField


_MAX_OPERATIONS = 64
_MAX_HORIZON = 8
_MAX_NODES = 4096
_MAX_FORBIDDEN = 64
_MAX_IDENTIFIER = 256

# The regional path is a direct lowering of inquiry semantics.  It stores
# field-derived readouts and an explicit search continuation; it never stores
# a TemporalField instance or invokes choose_temporal_inquiry.
REGIONAL_KERNEL_NAME = "inquiry.temporal"
REGIONAL_KERNEL_MAX_WORK = 4096
REGIONAL_STATE_SCHEMA = "cassifi.regional-temporal-inquiry-state.v1"
REGIONAL_RESULT_SCHEMA = "cassifi.regional-kernel-result.v1"
RESULT_SCHEMA = REGIONAL_RESULT_SCHEMA
_REGIONAL_MAX_JOURNAL = 16384




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
    # successor states count. Frequencies/probabilities are deliberately
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


def _ordered_outcomes(memory: TemporalField, outcomes: set[str]) -> tuple[str, ...]:
    order = {name: index for index, name in enumerate(memory.observation_ids)}
    return tuple(sorted(outcomes, key=lambda name: order[name]))


def _global_successors(memory: TemporalField, action: str) -> Mapping[str, tuple[int, ...]]:
    """Read the field's observed outcome envelope for one action."""
    action_code = memory.action_ids.index(action)
    width = len(memory.observation_ids)
    start = action_code * width
    destinations: dict[str, set[int]] = {}
    for state in range(memory.state_count):
        exposures = memory._field[0, state, start:start + width]  # noqa: SLF001
        for observation_code, observation in enumerate(memory.observation_ids):
            if exposures[observation_code] > 0:
                destination = int(
                    memory._field[0, memory.max_states + state, start + observation_code]  # noqa: SLF001
                )
                destinations.setdefault(observation, set()).add(destination)
    return {
        observation: tuple(sorted(states))
        for observation, states in destinations.items()
    }


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
def _select_optimistic_goal_action(
    memory: TemporalField,
    states: tuple[int, ...],
    operations: tuple[Mapping[str, Any], ...],
    forbidden: frozenset[str],
    *,
    skill_id: str | None,
    goal_policy: tuple[Sequence[str], Sequence[str], Any, Any] | None,
    recent_actions: Sequence[str] = (),
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    """Choose a safe acquisition that can re-enter a learned goal path."""
    if not states or len(states) > 8 or (skill_id is None and goal_policy is None):
        return None
    goal_names = (
        set(goal_policy[0])
        if goal_policy is not None
        else set(memory._skills[skill_id]["goal"]) if skill_id is not None else set()  # noqa: SLF001
    )

    def rank(state: int) -> int | None:
        if goal_policy is not None:
            ranks = goal_policy[2]
            value = int(ranks[state])
            return value if value > 0 else None
        assert skill_id is not None
        readout = memory.at_state(state).skill_action(skill_id)
        if readout.get("status") == "complete":
            return 0
        value = readout.get("remaining_steps")
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    candidates: list[tuple[tuple[Any, ...], Mapping[str, Any], Mapping[str, Any]]] = []
    for operation in operations:
        if not (
            operation["authorized"]
            and operation["feasible"]
            and operation["acquisition_allowed"]
        ):
            continue
        gap, refusal = _acquisition_gap(memory, states, operation, forbidden)
        if refusal is not None or gap is None or not gap["missing_states"]:
            continue
        global_outcomes = _global_successors(memory, operation["action"])
        if not global_outcomes or forbidden.intersection(global_outcomes):
            continue
        destination_records: list[tuple[int, str | None]] = []
        for destinations in global_outcomes.values():
            for destination in destinations:
                value = rank(destination)
                if value is None:
                    continue
                if goal_policy is not None:
                    action_code = int(goal_policy[3][destination])
                    action = (
                        memory.action_ids[action_code]
                        if action_code >= 0
                        else None
                    )
                else:
                    action = memory.at_state(destination).skill_action(skill_id).get("action")
                destination_records.append((value, action))
        if not destination_records:
            continue
        total_destinations = sum(len(destinations) for destinations in global_outcomes.values())
        destination_actions = {
            action for _, action in destination_records if isinstance(action, str)
        }
        uniform_goal = int(
            len(destination_records) == total_destinations
            and len(destination_actions) == 1
        )
        goal_coverage = len(destination_records) / max(1, total_destinations)
        repeated = sum(action == operation["action"] for action in recent_actions)
        direct_goal = int(not (goal_names.intersection(global_outcomes) and "clear" in recent_actions))
        candidates.append(((
            repeated,
            -uniform_goal,
            -goal_coverage,
            direct_goal,
            -len(goal_names.intersection(global_outcomes)),
            max(value for value, _ in destination_records),
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
    def optimistic_result() -> dict[str, Any] | None:
        selected = _select_optimistic_goal_action(
            memory,
            candidates,
            ops,
            forbidden,
            skill_id=skill_id,
            goal_policy=goal_policy,
            recent_actions=recent_actions,
        )
        if selected is None:
            return None
        operation, gap = selected
        result = dict(base_result)
        result.update({
            "status": "acquiring",
            "action": operation["action"],
            "acquisition_allowed": True,
            "decision_resolved": False,
            "policy": {
                "action": operation["action"],
                "kind": "goal-recovery",
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
            "reason": "optimistic-goal-recovery",
            "acquisition": {
                "host_permitted": True,
                "acquisition_allowed": True,
                "decision_resolved": False,
                "missing_states": gap["missing_states"],
                "unknown_successor": True,
                "actual_exposure": gap["actual_exposure"],
                "strategy": "global-observed-goal-envelope",
            },
        })
        return result
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
        acquired = optimistic_result()
        if acquired is None:
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
        optimistic = optimistic_result()
        if optimistic is not None:
            optimistic["work"] = {"nodes": nodes, "max_nodes": max_nodes, "depth": 0}
            return optimistic
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
        optimistic = optimistic_result()
        if optimistic is not None:
            optimistic["work"] = {"nodes": nodes, "max_nodes": max_nodes, "depth": 0}
            return optimistic
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


def _regional_canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise TemporalInquiryError("regional inquiry value is not canonical JSON") from exc


def _regional_copy(value: Any) -> Any:
    try:
        return json.loads(_regional_canonical(value).decode("utf-8"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise TemporalInquiryError("regional inquiry value is not JSON-safe") from exc


def _regional_digest(value: Any) -> str:
    return hashlib.sha256(_regional_canonical(value)).hexdigest()


def _regional_assumptions(value: Any) -> list[dict[str, Any]]:
    rows = _sequence(value, "assumptions")
    if len(rows) > _MAX_FORBIDDEN:
        raise TemporalInquiryError("assumptions exceed bounded capacity")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            row = {"name": row, "status": "satisfied"}
        if not isinstance(row, Mapping):
            raise TemporalInquiryError("assumption schema is invalid")
        required = {"name", "status"}
        allowed = required | {"kind", "model_conditional"}
        if set(row) - allowed or not required.issubset(row):
            raise TemporalInquiryError("assumption schema is closed")
        name = _identifier(row["name"], "assumption name")
        if name in seen:
            raise TemporalInquiryError("assumptions must be unique")
        seen.add(name)
        status = row["status"]
        if status not in {"satisfied", "failed", "missing", "unresolved"}:
            raise TemporalInquiryError(
                "assumption status must be satisfied, failed, missing, or unresolved"
            )
        kind = row.get("kind", "declared")
        kind = _identifier(kind, "assumption kind")
        model_conditional = row.get("model_conditional", False)
        if not isinstance(model_conditional, bool):
            raise TemporalInquiryError("assumption model_conditional must be boolean")
        result.append(
            {
                "name": name,
                "status": status,
                "kind": kind,
                "model_conditional": model_conditional,
            }
        )
    return result


def _regional_source_readout(
    source: Mapping[str, Any], state: int, action: str,
) -> Mapping[str, Any]:
    states = source["readouts"]
    if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state < len(states):
        raise TemporalInquiryError("regional inquiry state index is invalid")
    actions = source["action_ids"]
    try:
        action_index = actions.index(action)
    except ValueError as exc:
        raise TemporalInquiryError(f"unknown regional inquiry action: {action}") from exc
    row = states[state][action_index]
    if not isinstance(row, Mapping):
        raise TemporalInquiryError("regional inquiry readout is invalid")
    return row


def _regional_prediction(
    source: Mapping[str, Any], state: int, action: str,
) -> Mapping[str, int] | None:
    readout = _regional_source_readout(source, state, action)
    if readout.get("gap") is True:
        return None
    outcomes = readout.get("outcomes")
    if not isinstance(outcomes, Mapping) or not outcomes:
        return None
    return {str(key): int(value) for key, value in outcomes.items()}


def _regional_policy_readout(source: Mapping[str, Any], state: int) -> Mapping[str, Any]:
    rows = source.get("policy_readouts")
    if not isinstance(rows, list) or not 0 <= state < len(rows):
        raise TemporalInquiryError("regional inquiry policy readout is invalid")
    row = rows[state]
    if not isinstance(row, Mapping):
        raise TemporalInquiryError("regional inquiry policy readout is invalid")
    return row


def _regional_ordered_outcomes(source: Mapping[str, Any], outcomes: set[str]) -> tuple[str, ...]:
    order = {name: index for index, name in enumerate(source["observation_ids"])}
    return tuple(sorted(outcomes, key=lambda name: order[name]))


def _regional_full_coverage(source: Mapping[str, Any], state: int, action: str) -> bool:
    readout = _regional_source_readout(source, state, action)
    return not bool(readout.get("gap"))


def _regional_signature(
    raw: Mapping[str, Any],
    hypotheses: Sequence[Mapping[str, Any]],
    *,
    require_full_coverage: bool,
) -> tuple[Any, ...] | None:
    if not hypotheses:
        return None
    source = raw["source"]
    mode = source["goal_mode"]
    if mode != "none":
        rows: list[tuple[Any, ...]] = []
        for hypothesis in hypotheses:
            current = int(hypothesis["current"])
            readout = _regional_policy_readout(source, current)
            status, action = readout.get("status"), readout.get("action")
            if status == "proposed" and isinstance(action, str) and action in source["action_ids"]:
                remaining = readout.get("remaining_steps")
                if (
                    isinstance(remaining, bool)
                    or not isinstance(remaining, int)
                    or remaining < 1
                ):
                    return None
                if require_full_coverage:
                    if not _regional_full_coverage(source, current, action):
                        return None
                    origin = int(hypothesis["origin"])
                    if current != origin:
                        origin_readout = _regional_policy_readout(source, origin)
                        origin_remaining = origin_readout.get("remaining_steps")
                        if (
                            origin_readout.get("status") != "proposed"
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

    rows = []
    for hypothesis in hypotheses:
        transitions: list[tuple[Any, ...]] = []
        supported = False
        current = int(hypothesis["current"])
        for action in source["action_ids"]:
            transition = _regional_prediction(source, current, action)
            if transition is None:
                transitions.append((action, False, ()))
            else:
                supported = True
                transitions.append(
                    (
                        action,
                        True,
                        tuple(
                            (observation, transition[observation])
                            for observation in _regional_ordered_outcomes(
                                source, set(transition)
                            )
                        ),
                    )
                )
        if not supported:
            return None
        rows.append(tuple(transitions))
    return rows[0] if all(row == rows[0] for row in rows[1:]) else None


def _regional_transition(
    raw: Mapping[str, Any],
    hypotheses: Sequence[Mapping[str, Any]],
    operation: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, int]]], str | None]:
    source = raw["source"]
    forbidden = set(raw["task"]["forbidden_observations"])
    action = operation["action"]
    rows: list[tuple[Mapping[str, Any], Mapping[str, int]]] = []
    for hypothesis in hypotheses:
        row = _regional_prediction(source, int(hypothesis["current"]), action)
        if row is None:
            return {}, "unsupported-action"
        if forbidden.intersection(row):
            return {}, "forbidden-observation"
        rows.append((hypothesis, row))
    outcomes: set[str] = set()
    for _, row in rows:
        outcomes.update(row)
    branches: dict[str, list[dict[str, int]]] = {}
    for observation in _regional_ordered_outcomes(source, outcomes):
        branches[observation] = [
            {
                "origin": int(hypothesis["origin"]),
                "current": int(row[observation]),
            }
            for hypothesis, row in rows
            if observation in row
        ]
    return branches, None


def _regional_acquisition_gap(
    raw: Mapping[str, Any],
    states: Sequence[int],
    operation: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    source = raw["source"]
    forbidden = set(raw["task"]["forbidden_observations"])
    probe_states = tuple(states) if states else tuple(range(source["state_count"]))
    missing_states: set[int] = set()
    observed_outcomes: set[str] = set()
    unknown_successor = bool(source["carried_unknown"])
    exposed_states = 0
    for state in probe_states:
        readout = _regional_source_readout(source, state, operation["action"])
        outcomes = set(readout.get("outcomes", {}))
        if forbidden.intersection(outcomes):
            return None, "forbidden-observation"
        if outcomes:
            exposed_states += 1
            observed_outcomes.update(outcomes)
        if readout.get("gap") is True:
            missing = readout.get("missing_states") or [state]
            missing_states.update(int(item) for item in missing)
            unknown_successor = unknown_successor or bool(readout.get("unknown_successor"))
    if not missing_states and not bool(source["carried_unknown"]):
        return None, "supported-action"
    return (
        {
            "missing_states": sorted(missing_states),
            "unknown_successor": unknown_successor,
            "actual_exposure": exposed_states > 0,
            "exposed_states": exposed_states,
            "outcome_count": len(observed_outcomes),
        },
        None,
    )


def _regional_select_acquisition(
    raw: Mapping[str, Any], rejection_reasons: set[str],
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    source = raw["source"]
    task = raw["task"]
    states = source["candidate_states"]
    recent_actions = source["recent_actions"]
    candidates: list[tuple[tuple[Any, ...], Mapping[str, Any], Mapping[str, Any]]] = []
    for operation in task["operations"]:
        if not operation["authorized"]:
            rejection_reasons.add("authority")
            continue
        if not operation["feasible"]:
            rejection_reasons.add("feasibility")
            continue
        if not operation["acquisition_allowed"]:
            rejection_reasons.add("acquisition-permission")
            continue
        gap, refusal = _regional_acquisition_gap(raw, states, operation)
        if refusal is not None:
            rejection_reasons.add(refusal)
            continue
        if gap is None:
            continue
        repeated = sum(action == operation["action"] for action in recent_actions)
        candidates.append(
            (
                (
                    repeated,
                    -gap["outcome_count"],
                    -gap["exposed_states"],
                    len(gap["missing_states"]),
                    float(operation["cost"]),
                    float(operation["risk"]),
                    operation["action"],
                ),
                operation,
                gap,
            )
        )
    if not candidates:
        return None
    _, operation, gap = min(candidates, key=lambda item: item[0])
    return operation, gap


def _regional_base_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    source, limits = raw["source"], raw["limits"]
    candidates = source["candidate_states"]
    return {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "status": "unresolved",
        "action": None,
        "policy": None,
        "candidate_states": list(candidates),
        "costs": {
            "cost": 0.0,
            "risk": 0.0,
            "worst_case_cost": 0.0,
            "worst_case_risk": 0.0,
        },
        "work": {"nodes": 0, "max_nodes": limits["max_nodes"], "depth": 0},
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


def _regional_acquisition_result(
    raw: dict[str, Any], rejection_reasons: set[str],
) -> dict[str, Any] | None:
    selected = _regional_select_acquisition(raw, rejection_reasons)
    if selected is None:
        return None
    operation, gap = selected
    result = _regional_base_result(raw)
    result.update(
        {
            "status": "acquiring",
            "action": operation["action"],
            "acquisition_allowed": True,
            "decision_resolved": False,
            "policy": {
                "action": operation["action"],
                "kind": "acquisition",
                "branches": {},
                "candidate_states": list(raw["source"]["candidate_states"]),
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
        }
    )
    return result


def _regional_plan_key(plan: Mapping[str, Any]) -> tuple[Any, ...]:
    rank = 2 if plan["all_resolved"] else 1 if plan["any_elimination"] else 0
    return (
        -rank,
        -int(plan["guaranteed_eliminations"]),
        float(plan["worst_cost"]),
        float(plan["worst_risk"]),
        int(plan["steps"]),
        repr(plan["policy"]),
    )


def _regional_finish_plan(raw: dict[str, Any], plan: Mapping[str, Any]) -> None:
    continuation = raw["continuation"]
    stack = continuation["frames"]
    if not stack:
        continuation["selected_plan"] = dict(plan)
        raw["phase"] = "finalize"
        return
    frame = stack.pop()
    if not stack:
        continuation["selected_plan"] = dict(plan)
        raw["phase"] = "finalize"
        return
    parent = stack[-1]
    observation = frame.get("return_observation")
    if not isinstance(observation, str):
        raise TemporalInquiryError("regional inquiry child frame lacks an observation")
    parent["child_plans"][observation] = dict(plan)
    parent["branch_cursor"] = int(parent["branch_cursor"]) + 1
    parent["phase"] = "children"


def _regional_enter_frame(raw: dict[str, Any], frame: dict[str, Any]) -> None:
    source, limits, work = raw["source"], raw["limits"], raw["work"]
    hypotheses = frame["hypotheses"]
    work["nodes"] = int(work["nodes"]) + 1
    if work["nodes"] > limits["max_nodes"]:
        raw["unresolved_obligations"].append("max-nodes")
        raw["continuation"]["selected_plan"] = {
            "status": "unresolved",
            "policy": None,
            "all_resolved": False,
            "guaranteed_eliminations": 0,
            "any_elimination": False,
            "worst_cost": 0.0,
            "worst_risk": 0.0,
            "steps": 0,
            "reason": "max-nodes",
        }
        raw["phase"] = "finalize"
        raw["continuation"]["frames"] = []
        return
    work["depth"] = max(int(work["depth"]), int(frame["depth"]))
    raw["candidate_cursor"] = 0
    raw["numeric_cursor"] = {
        "phase": "signature",
        "candidate": 0,
        "action": 0,
        "observation": 0,
    }
    signature = _regional_signature(
        raw,
        hypotheses,
        require_full_coverage=bool(source["require_full_coverage"]),
    )
    depth = int(frame["depth"])
    separated = bool(frame["separated"])
    if len(hypotheses) == 1 and separated:
        _regional_finish_plan(
            raw,
            {
                "status": "resolved",
                "policy": None,
                "all_resolved": True,
                "guaranteed_eliminations": len(source["candidate_states"]) - 1,
                "any_elimination": True,
                "worst_cost": 0.0,
                "worst_risk": 0.0,
                "steps": 0,
                "reason": "decision-resolved",
            },
        )
        return
    if (
        signature is not None
        and (len(hypotheses) == 1 or separated)
        and not (source["carried_unknown"] and depth == 0)
    ):
        _regional_finish_plan(
            raw,
            {
                "status": "resolved",
                "policy": None,
                "all_resolved": True,
                "guaranteed_eliminations": len(source["candidate_states"]) - len(hypotheses),
                "any_elimination": separated,
                "worst_cost": 0.0,
                "worst_risk": 0.0,
                "steps": 0,
                "reason": "decision-resolved",
            },
        )
        return
    if depth >= limits["horizon"]:
        _regional_finish_plan(
            raw,
            {
                "status": "unresolved",
                "policy": None,
                "all_resolved": False,
                "guaranteed_eliminations": len(source["candidate_states"]) - len(hypotheses),
                "any_elimination": separated,
                "worst_cost": 0.0,
                "worst_risk": 0.0,
                "steps": 0,
                "reason": "horizon-exhausted",
            },
        )
        return
    feasible = [
        index
        for index, operation in enumerate(raw["task"]["operations"])
        if operation["authorized"]
        and operation["feasible"]
        and (not source["carried_unknown"] or operation["acquisition_allowed"])
    ]
    if not feasible:
        reasons = raw["continuation"]["rejection_reasons"]
        if not any(row["authorized"] for row in raw["task"]["operations"]):
            reasons.append("authority")
        elif not any(row["feasible"] for row in raw["task"]["operations"]):
            reasons.append("feasibility")
        elif source["carried_unknown"]:
            reasons.append("acquisition-permission")
        _regional_finish_plan(
            raw,
            {
                "status": "unresolved",
                "policy": None,
                "all_resolved": False,
                "guaranteed_eliminations": len(source["candidate_states"]) - len(hypotheses),
                "any_elimination": separated,
                "worst_cost": 0.0,
                "worst_risk": 0.0,
                "steps": 0,
                "reason": "no-authorized-feasible-operation",
            },
        )
        return
    frame.update(
        {
            "phase": "operation",
            "feasible_indices": feasible,
            "operation_cursor": 0,
            "plans": [],
            "candidate_count": len(hypotheses),
        }
    )


def _regional_advance_search(raw: dict[str, Any]) -> None:
    continuation = raw["continuation"]
    stack = continuation["frames"]
    if not stack:
        raw["phase"] = "finalize"
        return
    frame = stack[-1]
    phase = frame["phase"]
    if phase == "enter":
        _regional_enter_frame(raw, frame)
        return
    if phase == "operation":
        operations = raw["task"]["operations"]
        cursor = int(frame["operation_cursor"])
        indices = frame["feasible_indices"]
        if cursor >= len(indices):
            plans = frame["plans"]
            if not plans:
                reason = (
                    "forbidden-observation"
                    if "forbidden-observation" in continuation["rejection_reasons"]
                    else "unsupported-action"
                )
                _regional_finish_plan(
                    raw,
                    {
                        "status": "unresolved",
                        "policy": None,
                        "all_resolved": False,
                        "guaranteed_eliminations": len(raw["source"]["candidate_states"]) - len(frame["hypotheses"]),
                        "any_elimination": bool(frame["separated"]),
                        "worst_cost": 0.0,
                        "worst_risk": 0.0,
                        "steps": 0,
                        "reason": reason,
                    },
                )
            else:
                _regional_finish_plan(raw, min(plans, key=_regional_plan_key))
            return
        operation = operations[indices[cursor]]
        frame["current_operation"] = operation
        branches, refusal = _regional_transition(raw, frame["hypotheses"], operation)
        raw["proof_cursor"] = {
            "phase": "transition",
            "candidate": len(frame["hypotheses"]),
            "observation": len(branches),
        }
        if refusal is not None:
            continuation["rejection_reasons"].append(refusal)
            frame["operation_cursor"] = cursor + 1
            return
        frame["branches"] = branches
        frame["branch_order"] = list(branches)
        frame["branch_cursor"] = 0
        frame["child_plans"] = {}
        frame["all_resolved"] = True
        frame["any_elimination"] = False
        frame["guaranteed"] = len(raw["source"]["candidate_states"])
        frame["worst_cost"] = float(operation["cost"])
        frame["worst_risk"] = float(operation["risk"])
        frame["steps"] = 1
        frame["phase"] = "children"
        return
    if phase == "children":
        cursor = int(frame["branch_cursor"])
        order = frame["branch_order"]
        if cursor < len(order):
            observation = order[cursor]
            child_hypotheses = frame["branches"][observation]
            child_separated = bool(frame["separated"]) or (
                len(child_hypotheses) < len(frame["hypotheses"])
            )
            frame["phase"] = "await-child"
            raw["candidate_cursor"] = cursor
            raw["survivors"]["frontier"] = [
                {
                    "depth": int(frame["depth"]) + 1,
                    "observation": observation,
                    "states": [int(row["current"]) for row in child_hypotheses],
                }
            ]
            stack.append(
                {
                    "phase": "enter",
                    "hypotheses": child_hypotheses,
                    "depth": int(frame["depth"]) + 1,
                    "separated": child_separated,
                    "return_observation": observation,
                }
            )
            return
        operation = frame["current_operation"]
        child_plans = frame["child_plans"]
        all_resolved = True
        any_elimination = False
        guaranteed = len(raw["source"]["candidate_states"])
        worst_cost = float(operation["cost"])
        worst_risk = float(operation["risk"])
        steps = 1
        for observation in order:
            child = child_plans[observation]
            child_states = frame["branches"][observation]
            child_separated = bool(frame["separated"]) or (
                len(child_states) < len(frame["hypotheses"])
            )
            all_resolved = all_resolved and bool(child["all_resolved"])
            any_elimination = any_elimination or child_separated or bool(child["any_elimination"])
            guaranteed = min(guaranteed, int(child["guaranteed_eliminations"]))
            worst_cost = max(worst_cost, float(operation["cost"]) + float(child["worst_cost"]))
            worst_risk = max(worst_risk, float(operation["risk"]) + float(child["worst_risk"]))
            steps = max(steps, 1 + int(child["steps"]))
        if not all_resolved and not any_elimination:
            plan = {
                "status": "unresolved",
                "policy": None,
                "all_resolved": False,
                "guaranteed_eliminations": guaranteed,
                "any_elimination": False,
                "worst_cost": worst_cost,
                "worst_risk": worst_risk,
                "steps": steps,
                "reason": (
                    "horizon-exhausted"
                    if steps >= int(raw["limits"]["horizon"])
                    else "no-distinguishing-inquiry"
                ),
            }
        else:
            policy = {
                "action": operation["action"],
                "branches": {
                    observation: {
                        "candidate_states": [
                            int(row["origin"]) for row in frame["branches"][observation]
                        ],
                        "current_states": [
                            int(row["current"]) for row in frame["branches"][observation]
                        ],
                        "status": child_plans[observation]["status"],
                        "policy": child_plans[observation]["policy"],
                    }
                    for observation in order
                },
            }
            plan = {
                "status": "resolving" if all_resolved else "partial",
                "policy": policy,
                "all_resolved": all_resolved,
                "guaranteed_eliminations": guaranteed,
                "any_elimination": any_elimination,
                "worst_cost": worst_cost,
                "worst_risk": worst_risk,
                "steps": steps,
                "reason": (
                    "decision-resolved"
                    if all_resolved
                    else "guaranteed-elimination"
                    if guaranteed
                    else "possible-elimination"
                ),
            }
        frame["plans"].append(plan)
        frame["operation_cursor"] = int(frame["operation_cursor"]) + 1
        frame["phase"] = "operation"
        return
    raise TemporalInquiryError("regional inquiry search phase is invalid")


def _regional_finalize(raw: dict[str, Any]) -> None:
    source, continuation = raw["source"], raw["continuation"]
    base = _regional_base_result(raw)
    selected = continuation.get("selected_plan")
    if not isinstance(selected, Mapping):
        raise TemporalInquiryError("regional inquiry has no selected plan")
    nodes = int(raw["work"]["nodes"])
    depth = int(selected.get("steps", 0))
    base["work"] = {
        "nodes": nodes,
        "max_nodes": raw["limits"]["max_nodes"],
        "depth": depth,
    }
    rejection_reasons = set(continuation["rejection_reasons"])
    if selected.get("policy") is None:
        acquired = _regional_acquisition_result(raw, rejection_reasons)
        if acquired is not None:
            acquired["work"] = {
                "nodes": nodes,
                "max_nodes": raw["limits"]["max_nodes"],
                "depth": 0,
            }
            raw["result"] = acquired
            raw["policy_tree"] = acquired["policy"]
            raw["phase"] = "terminal"
            return
        if "authority" in rejection_reasons and not any(
            row["authorized"] for row in raw["task"]["operations"]
        ):
            reason = "authority"
        elif "feasibility" in rejection_reasons and not any(
            row["feasible"] for row in raw["task"]["operations"]
        ):
            reason = "feasibility"
        elif "forbidden-observation" in rejection_reasons:
            reason = "forbidden-observation"
        elif source["carried_unknown"] and "acquisition-permission" in rejection_reasons:
            reason = "acquisition-permission"
        else:
            reason = str(selected.get("reason", "no-distinguishing-inquiry"))
        base["reason"] = reason
        raw["result"] = base
        raw["phase"] = "terminal"
        return
    policy = dict(selected["policy"])
    if source["carried_unknown"]:
        policy["kind"] = "context-recovery"
        policy["candidate_states"] = list(source["candidate_states"])
        base.update(
            {
                "status": "acquiring",
                "action": policy["action"],
                "policy": policy,
                "acquisition_allowed": True,
                "decision_resolved": False,
                "costs": {
                    "cost": float(selected["worst_cost"]),
                    "risk": float(selected["worst_risk"]),
                    "worst_case_cost": float(selected["worst_cost"]),
                    "worst_case_risk": float(selected["worst_risk"]),
                },
                "work": {"nodes": nodes, "max_nodes": raw["limits"]["max_nodes"], "depth": depth},
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
            }
        )
    else:
        base.update(
            {
                "status": selected["status"],
                "action": policy["action"],
                "policy": policy,
                "decision_resolved": bool(selected["all_resolved"]),
                "costs": {
                    "cost": float(selected["worst_cost"]),
                    "risk": float(selected["worst_risk"]),
                    "worst_case_cost": float(selected["worst_cost"]),
                    "worst_case_risk": float(selected["worst_risk"]),
                },
                "work": {"nodes": nodes, "max_nodes": raw["limits"]["max_nodes"], "depth": depth},
                "reason": selected["reason"],
            }
        )
    raw["policy_tree"] = policy
    raw["result"] = base
    raw["phase"] = "terminal"


def _regional_prepare(raw: dict[str, Any]) -> None:
    source, task = raw["source"], raw["task"]
    rejection_reasons = raw["continuation"]["rejection_reasons"]
    if not source["candidate_states"]:
        acquired = _regional_acquisition_result(raw, set(rejection_reasons))
        if acquired is not None:
            raw["result"] = acquired
            raw["policy_tree"] = acquired["policy"]
        else:
            raw["result"] = _regional_base_result(raw)
        raw["phase"] = "terminal"
        return
    if source["goal_mode"] != "none" and not source["carried_unknown"]:
        direct = source["direct_policy_readout"]
        if direct.get("status") == "complete":
            result = _regional_base_result(raw)
            result.update(
                {
                    "status": "complete",
                    "reason": "goal-observation-consumed",
                    "decision_resolved": True,
                }
            )
            raw["result"] = result
            raw["phase"] = "terminal"
            return
        direct_action = direct.get("action")
        direct_operation = next(
            (
                operation
                for operation in task["operations"]
                if operation["action"] == direct_action
                and operation["authorized"]
                and operation["feasible"]
            ),
            None,
        )
        if direct.get("status") == "proposed" and direct_operation is not None:
            result = _regional_base_result(raw)
            result.update(
                {
                    "status": "resolving",
                    "action": direct_action,
                    "policy": {
                        "action": direct_action,
                        "kind": "transient-goal",
                        "branches": {},
                        "candidate_states": list(source["candidate_states"]),
                    },
                    "costs": {
                        "cost": float(direct_operation["cost"]),
                        "risk": float(direct_operation["risk"]),
                        "worst_case_cost": float(direct_operation["cost"]),
                        "worst_case_risk": float(direct_operation["risk"]),
                    },
                    "reason": "goal-directed-action",
                    "decision_resolved": True,
                }
            )
            raw["result"] = result
            raw["policy_tree"] = result["policy"]
            raw["phase"] = "terminal"
            return
    singleton_decision = (
        (source["goal_mode"] == "none")
        or _regional_signature(
            raw,
            (
                {
                    "origin": source["candidate_states"][0],
                    "current": source["candidate_states"][0],
                },
            ),
            require_full_coverage=bool(source["require_full_coverage"]),
        )
        is not None
    )
    if (
        len(source["candidate_states"]) == 1
        and not source["carried_unknown"]
        and singleton_decision
    ):
        acquired = _regional_acquisition_result(raw, set(rejection_reasons))
        if acquired is not None:
            raw["result"] = acquired
            raw["policy_tree"] = acquired["policy"]
        else:
            result = _regional_base_result(raw)
            result["status"] = "not-needed"
            result["reason"] = "fewer-than-two-candidates"
            raw["result"] = result
        raw["phase"] = "terminal"
        return
    raw["continuation"]["frames"] = [
        {
            "phase": "enter",
            "hypotheses": [
                {"origin": int(state), "current": int(state)}
                for state in source["candidate_states"]
            ],
            "depth": 0,
            "separated": False,
            "return_observation": None,
        }
    ]
    raw["phase"] = "search"


def _regional_check_assumptions(raw: dict[str, Any]) -> None:
    failed = [
        row for row in raw["assumptions"] if row["status"] == "failed"
    ]
    missing = [
        row for row in raw["assumptions"]
        if row["status"] in {"missing", "unresolved"}
    ]
    if failed or missing:
        names = [row["name"] for row in (*failed, *missing)]
        raw["unresolved_obligations"] = names
        result = _regional_base_result(raw)
        result["reason"] = "failed-assumption" if failed else "missing-assumption"
        raw["result"] = result
        raw["phase"] = "terminal"
    else:
        raw["phase"] = "prepare"


def _regional_validate_state(state: Any) -> dict[str, Any]:
    required = {
        "schema",
        "source",
        "source_sha256",
        "task",
        "survivors",
        "policy_tree",
        "candidate_cursor",
        "numeric_cursor",
        "proof_cursor",
        "assumptions",
        "unresolved_obligations",
        "limits",
        "work",
        "journal",
        "phase",
        "continuation",
        "result",
    }
    if not isinstance(state, Mapping) or set(state) != required:
        raise TemporalInquiryError("regional inquiry state schema is invalid")
    raw = _regional_copy(state)
    if raw["schema"] != REGIONAL_STATE_SCHEMA:
        raise TemporalInquiryError("regional inquiry state schema is invalid")
    if raw["source_sha256"] != _regional_digest(raw["source"]):
        raise TemporalInquiryError("regional inquiry source digest mismatch")
    if raw["phase"] not in {"assumptions", "prepare", "search", "finalize", "terminal"}:
        raise TemporalInquiryError("regional inquiry phase is invalid")
    if not isinstance(raw["limits"], Mapping):
        raise TemporalInquiryError("regional inquiry limits are invalid")
    _bounded_int(raw["limits"].get("horizon"), "regional inquiry horizon", 1, _MAX_HORIZON)
    _bounded_int(raw["limits"].get("max_nodes"), "regional inquiry max_nodes", 1, _MAX_NODES)
    if not isinstance(raw["assumptions"], list):
        raise TemporalInquiryError("regional inquiry assumptions are invalid")
    _regional_assumptions(raw["assumptions"])
    if not isinstance(raw["journal"], list) or len(raw["journal"]) > _REGIONAL_MAX_JOURNAL:
        raise TemporalInquiryError("regional inquiry journal is invalid")
    if not isinstance(raw["work"], Mapping):
        raise TemporalInquiryError("regional inquiry work is invalid")
    for name in ("nodes", "depth", "logical"):
        _bounded_int(raw["work"].get(name), f"regional inquiry work {name}", 0, _MAX_NODES * _MAX_HORIZON)
    if raw["phase"] == "terminal" and not isinstance(raw["result"], Mapping):
        raise TemporalInquiryError("terminal regional inquiry state lacks a result")
    if raw["phase"] != "terminal" and raw["result"] is not None:
        raise TemporalInquiryError("running regional inquiry state carries a result")
    return raw


def regional_state(
    memory: TemporalField,
    *,
    participant_id: str | None = None,
    operations: Sequence[Mapping[str, Any]],
    skill_id: str | None = None,
    goal_observations: Sequence[str] = (),
    horizon: int = 3,
    max_nodes: int = _MAX_NODES,
    forbidden_observations: Sequence[str] = (),
    assumptions: Sequence[Mapping[str, Any] | str] = (),
) -> dict[str, Any]:
    """Lower one inquiry task to a JSON-safe, resumable regional state.

    The learned field is read only while lowering.  The resulting state keeps
    all candidate readouts, policy data, cursors, assumptions, and limits
    required by :func:`regional_kernel`; no live ``TemporalField`` is stored.
    """
    if not isinstance(memory, TemporalField):
        raise TemporalInquiryError("memory must be a TemporalField")
    if skill_id is not None:
        _identifier(skill_id, "skill_id")
    horizon = _bounded_int(horizon, "horizon", 1, _MAX_HORIZON)
    max_nodes = _bounded_int(max_nodes, "max_nodes", 1, _MAX_NODES)
    ops = _operations(memory, operations)
    forbidden = _forbidden(memory, forbidden_observations)
    goals = _goals(memory, goal_observations)
    if skill_id is not None and goals:
        raise TemporalInquiryError("skill_id and goal_observations are mutually exclusive")
    candidate_states = _candidate_states(memory, participant_id)
    try:
        carried = memory.predict(ops[0]["action"], participant_id=participant_id)
        carried_unknown = carried["support"]["unknown_successor"]
        recent_actions = tuple(
            row["action"]
            for row in memory.history(participant_id=participant_id)[-len(ops):]
            if isinstance(row.get("action"), str)
        )
        require_full_coverage = bool(
            memory.context_status(participant_id=participant_id).get("uncovered_history")
        )
    except Exception as exc:
        raise TemporalInquiryError("unable to lower carried inquiry uncertainty") from exc
    if not isinstance(carried_unknown, bool):
        raise TemporalInquiryError("field prediction unknown_successor is invalid")

    policy_mode = "skill" if skill_id is not None else "goal" if goals else "none"
    goal_policy = None
    if goals:
        try:
            goal_policy = memory._derive_skill_policy(
                goal_observations=goals,
                forbidden_observations=tuple(forbidden),
            )
        except Exception as exc:
            raise TemporalInquiryError("unable to derive a transient goal policy") from exc
    if skill_id is not None and skill_id not in set(memory.skill_ids):
        raise TemporalInquiryError(f"unknown skill_id: {skill_id}")

    readouts: list[list[dict[str, Any]]] = []
    for state in range(memory.state_count):
        state_rows: list[dict[str, Any]] = []
        for action in memory.action_ids:
            row = _readout(memory, state, action)
            state_rows.append(
                {
                    "outcomes": {key: int(value) for key, value in row.outcomes.items()},
                    "gap": bool(row.gap),
                    "unknown_successor": bool(row.unknown_successor),
                    "missing_states": [int(item) for item in row.missing_states],
                    "exposure": int(row.exposure),
                }
            )
        readouts.append(state_rows)

    policy_readouts: list[dict[str, Any]] = []
    if policy_mode != "none":
        ranks = goal_policy[2] if goal_policy is not None else None
        policy_values = goal_policy[3] if goal_policy is not None else None
        for state in range(memory.state_count):
            try:
                if skill_id is not None:
                    value = memory.at_state(state).skill_action(skill_id)
                else:
                    assert ranks is not None and policy_values is not None
                    value = memory.at_state(state)._policy_action(
                        skill_id=None,
                        goals=goals,
                        ranks=ranks,
                        policy=policy_values,
                    )
            except Exception as exc:
                raise TemporalInquiryError("unable to lower policy readout") from exc
            policy_readouts.append(dict(value))
        try:
            if skill_id is not None:
                direct_policy_readout = dict(
                    memory.skill_action(skill_id, participant_id=participant_id)
                )
            else:
                assert goal_policy is not None
                direct_policy_readout = dict(
                    memory._policy_action(
                        skill_id=None,
                        goals=goal_policy[0],
                        ranks=goal_policy[2],
                        policy=goal_policy[3],
                        participant_id=participant_id,
                    )
                )
        except Exception as exc:
            raise TemporalInquiryError("unable to lower direct policy readout") from exc
    else:
        direct_policy_readout = {}

    source = {
        "action_ids": list(memory.action_ids),
        "observation_ids": list(memory.observation_ids),
        "state_count": int(memory.state_count),
        "candidate_states": [int(item) for item in candidate_states],
        "readouts": readouts,
        "policy_readouts": policy_readouts,
        "goal_mode": policy_mode,
        "skill_id": skill_id,
        "goal_observations": list(goals),
        "carried_unknown": carried_unknown,
        "recent_actions": list(recent_actions),
        "require_full_coverage": require_full_coverage,
        "direct_policy_readout": direct_policy_readout,
    }
    task = {
        "participant_id": participant_id,
        "operations": [dict(row) for row in ops],
        "forbidden_observations": sorted(forbidden, key=memory.observation_ids.index),
    }
    normalized_assumptions = _regional_assumptions(assumptions)
    state = {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": source,
        "source_sha256": _regional_digest(source),
        "task": task,
        "survivors": {
            "root": [int(item) for item in candidate_states],
            "frontier": [],
        },
        "policy_tree": None,
        "candidate_cursor": 0,
        "numeric_cursor": {
            "phase": "idle",
            "candidate": 0,
            "action": 0,
            "observation": 0,
        },
        "proof_cursor": {
            "phase": "idle",
            "candidate": 0,
            "observation": 0,
        },
        "assumptions": normalized_assumptions,
        "unresolved_obligations": [],
        "limits": {
            "horizon": horizon,
            "max_nodes": max_nodes,
            "max_work": REGIONAL_KERNEL_MAX_WORK,
        },
        "work": {
            "nodes": 0,
            "depth": 0,
            "logical": 0,
            "max_nodes": max_nodes,
        },
        "journal": [],
        "phase": "assumptions",
        "continuation": {
            "frames": [],
            "rejection_reasons": [],
            "selected_plan": None,
        },
        "result": None,
    }
    _regional_validate_state(state)
    return state


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> cassi_field_regions.KernelResult:
    """Advance one inquiry by at most ``quantum`` direct regional primitives."""
    raw = _regional_validate_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise TemporalInquiryError("regional inquiry kernel takes no arguments")
    quantum = _bounded_int(
        quantum,
        "regional inquiry quantum",
        1,
        REGIONAL_KERNEL_MAX_WORK,
    )
    if raw["phase"] == "terminal":
        return cassi_field_regions.KernelResult(
            state=raw,
            status="done",
            work=0,
            output=raw["result"],
        )
    consumed = 0
    while consumed < quantum and raw["phase"] != "terminal":
        old_phase = raw["phase"]
        if old_phase == "assumptions":
            _regional_check_assumptions(raw)
        elif old_phase == "prepare":
            _regional_prepare(raw)
        elif old_phase == "search":
            _regional_advance_search(raw)
        elif old_phase == "finalize":
            _regional_finalize(raw)
        else:
            raise TemporalInquiryError("regional inquiry phase cannot advance")
        consumed += 1
        raw["work"]["logical"] = int(raw["work"]["logical"]) + 1
        if len(raw["journal"]) >= _REGIONAL_MAX_JOURNAL:
            raise TemporalInquiryError("regional inquiry journal capacity exceeded")
        raw["journal"].append(
            {
                "step": int(raw["work"]["logical"]),
                "phase": old_phase,
                "next_phase": raw["phase"],
            }
        )
    if raw["phase"] == "terminal":
        return cassi_field_regions.KernelResult(
            state=raw,
            status="done",
            work=consumed,
            output=raw["result"],
        )
    return cassi_field_regions.KernelResult(
        state=raw,
        status="yield",
        work=consumed,
        output=None,
    )


__all__ = [
    "RESULT_SCHEMA",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_RESULT_SCHEMA",
    "REGIONAL_STATE_SCHEMA",
    "TemporalInquiryError",
    "choose_temporal_inquiry",
    "regional_kernel",
    "regional_state",
]
