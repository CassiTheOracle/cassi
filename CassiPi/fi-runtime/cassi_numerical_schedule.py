"""Multi-rate rest/wake scheduling for owner numerical work (item 18).

This module is the pure scheduling authority for the owner's *logical
numerical clock*: numerical periods, integration quanta, rest and wake are
separate from any communication cadence and separate from wall time.

Rules implemented here and enforced by the owner integration:

- The clock advances only on fresh, real owner-activity evidence.  Repeating
  the same evidence, or calling with none, cannot manufacture a tick.
- A rested (parked) stream is never a frozen field: an in-flight quantum is
  refused as a rest target, so a running regional kernel always completes and
  remains collectable.  Rest only changes what the schedule chooses next.
- An approximate region may rest only while the last collected variational
  result carries a valid residual certificate within the declared tolerance.
- Coupled resonant/circulation work rests only at operator-declared
  synchronization boundaries, and every member of a declared synchronization
  group must be at its boundary before any member rests.
- Wake requires a real reason: a changed operator digest, a changed
  dependency fingerprint, resumed activity above the entry floor, or the
  entry's own period coming due.  No reason, no wake.
- No function here fabricates outcomes or convergence: decisions report
  digests and reasons; completion is always the collected artifact's own.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

NUMERICAL_SCHEDULE_SCHEMA = "cassifi.numerical-schedule.v1"
NUMERICAL_CLOCK_SCHEMA = "cassifi.numerical-clock.v1"
NUMERICAL_TICK_SCHEMA = "cassifi.numerical-tick-receipt.v1"
NUMERICAL_REST_SCHEMA = "cassifi.numerical-rest-receipt.v1"
NUMERICAL_WAKE_SCHEMA = "cassifi.numerical-wake-receipt.v1"
NUMERICAL_VIEW_SCHEMA = "cassifi.numerical-schedule-view.v1"
RETAINED_BOUND_SCHEMA = "cassifi.numerical-retained-bound.v1"

# Result schema whose output the retained-bound rule understands.
VARIATIONAL_RESULT_SCHEMA = "cassifi.regional-kernel-result.v1"
VARIATIONAL_KERNEL_NAME = "numerical.variational"

REST_POLICIES = ("approximate-bound", "operator-sync")

# Evidence fields: a tick (and a wake) must carry a real reason plus the
# observed numerical activity.  Optional digest observations let the operator
# declare that a dependency fingerprint or operator identity changed.
_EVIDENCE_KEYS = frozenset(
    {
        "reason",
        "activity",
        "operator_sha256",
        "dependency_sha256",
    }
)

_SHA_PATTERN_LENGTH = 64


class NumericalScheduleError(ValueError):
    """A numerical rest/wake schedule request or decision is invalid."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hex_digest(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA_PATTERN_LENGTH
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise NumericalScheduleError(f"{name} must be a 64-character sha256 digest")
    return value


def _integer(
    value: Any, name: str, *, minimum: int = 0, maximum: int | None = None,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        limit = f" and <= {maximum}" if maximum is not None else ""
        raise NumericalScheduleError(
            f"{name} must be an integer >= {minimum}{limit}"
        )
    return value


def _number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise NumericalScheduleError(f"{name} must be a finite number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise NumericalScheduleError(f"{name} must be >= {minimum}")
    return result


def _identifier(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not (1 <= len(value) <= 256)
        or any(not (char.isalnum() or char in "-_#:.@/") for char in value)
    ):
        raise NumericalScheduleError(f"{name} must be a bounded identifier")
    return value


def normalize_evidence(value: Any) -> dict[str, Any]:
    """Validate one tick/wake evidence record and return it canonically."""

    if not isinstance(value, Mapping):
        raise NumericalScheduleError("numerical schedule evidence must be a mapping")
    if set(value) - _EVIDENCE_KEYS:
        raise NumericalScheduleError(
            "numerical schedule evidence contains unknown fields"
        )
    reason = _identifier(value.get("reason"), "evidence reason")
    activity = _number(value.get("activity"), "evidence activity", minimum=0.0)
    evidence: dict[str, Any] = {"reason": reason, "activity": activity}
    for key in ("operator_sha256", "dependency_sha256"):
        if value.get(key) is not None:
            evidence[key] = _hex_digest(value.get(key), f"evidence {key}")
    return evidence


def evidence_digest(evidence: Mapping[str, Any]) -> str:
    return _digest(normalize_evidence(evidence))


def normalize_clock(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "schema": NUMERICAL_CLOCK_SCHEMA,
            "tick": 0,
            "last_evidence_sha256": None,
            "last_owner_generation": 0,
            "last_activity": 0.0,
        }
    if not isinstance(value, Mapping) or value.get("schema") != NUMERICAL_CLOCK_SCHEMA:
        raise NumericalScheduleError("numerical clock record is invalid")
    clock = {
        "schema": NUMERICAL_CLOCK_SCHEMA,
        "tick": _integer(value.get("tick"), "numerical clock tick"),
        "last_evidence_sha256": value.get("last_evidence_sha256"),
        "last_owner_generation": _integer(
            value.get("last_owner_generation"), "numerical clock owner generation"
        ),
        "last_activity": _number(
            value.get("last_activity", 0.0),
            "numerical clock last activity",
            minimum=0.0,
        ),
    }
    if clock["last_evidence_sha256"] is not None:
        _hex_digest(clock["last_evidence_sha256"], "clock evidence digest")
    if clock["tick"] == 0:
        if (
            clock["last_evidence_sha256"] is not None
            or clock["last_owner_generation"] != 0
            or clock["last_activity"] != 0.0
        ):
            raise NumericalScheduleError(
                "numerical clock activity precedes its first tick"
            )
    elif clock["last_evidence_sha256"] is None:
        raise NumericalScheduleError("numerical clock tick has no evidence")
    return clock


def advance_clock(
    clock: Mapping[str, Any], evidence: Mapping[str, Any], digest: str,
    *, owner_generation: int,
) -> tuple[dict[str, Any], int]:
    """Advance the logical numerical clock by exactly one fresh evidence tick.

    The digest must be the canonical digest of the supplied owner evidence.
    Repeating evidence or moving the owner generation backwards cannot create
    a tick; wall time is never consulted.
    """

    normalized = normalize_clock(clock)
    normalized_evidence = normalize_evidence(evidence)
    _hex_digest(digest, "evidence digest")
    if digest != evidence_digest(normalized_evidence):
        raise NumericalScheduleError(
            "numerical schedule evidence digest does not match its evidence"
        )
    _integer(owner_generation, "owner generation", minimum=0)
    if digest == normalized["last_evidence_sha256"]:
        raise NumericalScheduleError(
            "idle wall time cannot advance the numerical schedule"
        )
    if owner_generation < normalized["last_owner_generation"]:
        raise NumericalScheduleError(
            "numerical schedule tick observed a regressed owner generation"
        )
    tick = normalized["tick"] + 1
    successor = {
        "schema": NUMERICAL_CLOCK_SCHEMA,
        "tick": tick,
        "last_evidence_sha256": digest,
        "last_owner_generation": owner_generation,
        "last_activity": normalized_evidence["activity"],
    }
    return successor, tick




def normalize_policy(
    *,
    period: Any,
    quantum: Any,
    rest_policy: Any,
    tolerance: Any,
    sync_group: Any,
    operator_sha256: Any,
    activity_floor: Any,
) -> dict[str, Any]:
    """Validate one stream policy and return its canonical mapping."""

    if rest_policy not in REST_POLICIES:
        raise NumericalScheduleError(
            "rest_policy must be one of 'approximate-bound' or 'operator-sync'"
        )
    policy = {
        "period": _integer(period, "schedule period", minimum=1),
        "quantum": _integer(
            quantum, "schedule quantum", minimum=1, maximum=4096
        ),
        "rest_policy": rest_policy,
        "tolerance": None,
        "sync_group": None,
        "operator_sha256": None,
        "activity_floor": 0.0,
    }
    if rest_policy == "approximate-bound":
        if tolerance is None:
            raise NumericalScheduleError(
                "approximate-bound rest requires a declared tolerance"
            )
        policy["tolerance"] = _number(tolerance, "schedule tolerance", minimum=0.0)
    else:
        policy["sync_group"] = _identifier(sync_group, "schedule sync_group")
        if operator_sha256 is not None:
            policy["operator_sha256"] = _hex_digest(
                operator_sha256, "schedule operator_sha256"
            )
    if activity_floor is not None:
        policy["activity_floor"] = _number(
            activity_floor, "schedule activity_floor", minimum=0.0
        )
    return policy


def next_period_tick(policy: Mapping[str, Any], clock_tick: int) -> int:
    """Return the next logical tick due after one stream's scheduled period."""

    tick = _integer(clock_tick, "numerical clock tick")
    period = _integer(policy.get("period"), "schedule period", minimum=1)
    return tick + period


def policy_fingerprint(policy: Mapping[str, Any]) -> str:
    return _digest(dict(policy))


def retained_bound(result: Any, *, policy: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract a settled residual certificate from a collected variational result.

    Only the terminal result of the variational regional kernel carries the
    residual metric understood by the approximate-bound policy.  Other
    same-schema regional results are not interchangeable certificates.
    """

    if (
        not isinstance(result, Mapping)
        or result.get("schema") != VARIATIONAL_RESULT_SCHEMA
        or result.get("family") != VARIATIONAL_KERNEL_NAME
        or result.get("status") != "done"
    ):
        return None
    try:
        residual = _number(
            result.get("residual_norm"), "retained residual norm", minimum=0.0
        )
        tolerance = _number(
            policy.get("tolerance"), "schedule tolerance", minimum=0.0
        )
        result_sha256 = _digest(dict(result))
    except (NumericalScheduleError, TypeError, ValueError):
        return None
    return {
        "schema": RETAINED_BOUND_SCHEMA,
        "kernel": VARIATIONAL_KERNEL_NAME,
        "result_schema": result["schema"],
        "metric": "residual_norm",
        "residual_norm": residual,
        "tolerance": tolerance,
        "settled": residual <= tolerance,
        "result_sha256": result_sha256,
    }


def bound_settled(bound: Mapping[str, Any] | None) -> bool:
    if (
        not isinstance(bound, Mapping)
        or bound.get("schema") != RETAINED_BOUND_SCHEMA
        or bound.get("kernel") != VARIATIONAL_KERNEL_NAME
        or bound.get("result_schema") != VARIATIONAL_RESULT_SCHEMA
        or bound.get("metric") != "residual_norm"
        or bound.get("settled") is not True
    ):
        return False
    try:
        residual = _number(
            bound.get("residual_norm"), "retained residual norm", minimum=0.0
        )
        tolerance = _number(
            bound.get("tolerance"), "retained tolerance", minimum=0.0
        )
        _hex_digest(bound.get("result_sha256"), "retained result digest")
    except NumericalScheduleError:
        return False
    return residual <= tolerance


def task_at_sync_boundary(task: Any) -> bool:
    """Return whether an operator task is at a terminal or declared pause boundary."""

    if not isinstance(task, Mapping):
        return False
    if task.get("phase") == "done" or task.get("paused") is True:
        return True
    if task.get("status") == "done":
        return True
    continuation = task.get("continuation")
    return isinstance(continuation, Mapping) and continuation.get("phase") == "done"


def _task_result(task: Any) -> Mapping[str, Any] | None:
    """Read a collected result from a task/state envelope or direct result."""

    if not isinstance(task, Mapping):
        return None
    for key in ("result", "output"):
        result = task.get(key)
        if isinstance(result, Mapping):
            return result
    return task


def rest_authorization(
    policy: Mapping[str, Any], *,
    record_status: str | None,
    in_flight: bool,
    successor_task: Any,
    group_open: tuple[str, ...],
) -> dict[str, Any]:
    """Decide whether one stream may rest at its current safe boundary.

    For approximate-bound policies, ``successor_task`` may be the collected
    result itself or a task/state mapping with that result in ``result`` or
    ``output``.  For operator-sync policies it is the task/state whose
    terminal or explicit paused boundary is being considered.
    """

    if in_flight or record_status == "pending":
        return {
            "allowed": False,
            "reason": "QUANTUM_IN_FLIGHT",
            "details": {"record_status": record_status},
        }
    terminal_reason = {
        "cancelled": "WORK_CANCELLED",
        "faulted": "WORK_FAULTED",
        "obsolete": "WORK_OBSOLETE",
    }.get(record_status)
    if terminal_reason is not None:
        return {
            "allowed": False,
            "reason": terminal_reason,
            "details": {"record_status": record_status},
        }
    if policy["rest_policy"] == "approximate-bound":
        bound = retained_bound(_task_result(successor_task), policy=policy)
        if bound is None:
            return {
                "allowed": False,
                "reason": "REST_BOUND_REQUIRED",
                "details": {"record_status": record_status},
            }
        if not bound["settled"]:
            return {
                "allowed": False,
                "reason": "REST_BOUND_UNSETTLED",
                "details": {
                    "record_status": record_status,
                    "residual_norm": bound["residual_norm"],
                    "tolerance": bound["tolerance"],
                    "result_sha256": bound["result_sha256"],
                },
            }
        return {"allowed": True, "reason": "REST_BOUND_SETTLED", "details": bound}
    if not task_at_sync_boundary(successor_task):
        return {
            "allowed": False,
            "reason": "SYNC_BOUNDARY_REQUIRED",
            "details": {"record_status": record_status},
        }
    if not isinstance(group_open, tuple):
        raise NumericalScheduleError("sync group open members must be a tuple")
    open_members: list[str] = []
    seen_members: set[str] = set()
    for member in group_open:
        member_id = _identifier(member, "open synchronization member")
        if member_id in seen_members:
            raise NumericalScheduleError("sync group open members must be unique")
        seen_members.add(member_id)
        open_members.append(member_id)
    if open_members:
        return {
            "allowed": False,
            "reason": "SYNC_GROUP_OPEN",
            "details": {"open_members": open_members},
        }
    return {
        "allowed": True,
        "reason": "SYNC_GROUP_SETTLED",
        "details": {"successor_phase": (
            successor_task.get("phase") if isinstance(successor_task, Mapping) else None
        )},
    }


def wake_reasons(
    policy: Mapping[str, Any], *,
    entry: Mapping[str, Any],
    evidence: Mapping[str, Any],
    clock_tick: int,
) -> tuple[str, ...]:
    """Real reasons that justify waking a stream from fresh logical evidence."""

    normalized_evidence = normalize_evidence(evidence)
    tick = _integer(clock_tick, "numerical clock tick")
    reasons: list[str] = []
    recorded_operator = entry.get("operator_sha256") or policy.get("operator_sha256")
    if (observed_sha := normalized_evidence.get("operator_sha256")) is not None:
        if observed_sha != recorded_operator:
            reasons.append("operator-changed")
    if observed_dep := normalized_evidence.get("dependency_sha256"):
        if observed_dep != entry.get("dependency_sha256"):
            reasons.append("dependency-changed")
    floor = _number(policy.get("activity_floor"), "schedule activity_floor", minimum=0.0)
    if floor > 0.0 and normalized_evidence["activity"] >= floor:
        reasons.append("activity-resumed")
    due_tick = _integer(entry.get("next_due_tick"), "schedule next_due_tick", minimum=1)
    if tick >= due_tick:
        reasons.append("period-due")
    return tuple(reasons)


def continuation_decision(
    policy: Mapping[str, Any], *,
    entry: Mapping[str, Any],
    record_status: str | None,
    bound: Mapping[str, Any] | None,
    activity: float,
    clock_tick: int,
) -> dict[str, Any]:
    """Choose whether the schedule runs a bounded next quantum now.

    The decision consults the retained residual against the declared
    tolerance, the observed activity against the entry floor, and the entry's
    own logical period.  It never claims an outcome: the proposed quantum is
    still work for the existing bounded kernels.
    """

    if record_status == "pending":
        return {"choice": "in-flight"}
    if record_status == "cancelled":
        return {"choice": "cancelled"}
    if record_status == "faulted":
        return {"choice": "faulted"}
    if record_status is None:
        return {"choice": "detached"}
    if record_status == "obsolete":
        return {"choice": "obsolete"}
    tick = _integer(clock_tick, "numerical clock tick")
    observed_activity = _number(activity, "schedule activity", minimum=0.0)
    due_tick = _integer(entry.get("next_due_tick"), "schedule next_due_tick", minimum=1)
    if tick < due_tick:
        return {"choice": "wait-due", "due_tick": due_tick}
    floor = _number(policy.get("activity_floor"), "schedule activity_floor", minimum=0.0)
    if observed_activity < floor:
        return {"choice": "activity-starved", "activity": observed_activity}
    if policy["rest_policy"] == "approximate-bound":
        if bound is None:
            return {"choice": "continuation-unavailable"}
        if bound_settled(bound):
            return {
                "choice": "settled",
                "residual_norm": bound["residual_norm"],
                "tolerance": bound["tolerance"],
                "result_sha256": bound["result_sha256"],
            }
    return {"choice": "run-next", "quantum": policy["quantum"]}




def canonical_schedule_view(clock: Mapping[str, Any], entries: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": NUMERICAL_VIEW_SCHEMA,
        "clock": dict(clock),
        "entries": {name: dict(entry) for name, entry in sorted(entries.items())},
    }


def normalize_entry(value: Any) -> dict[str, Any]:
    """Validate and canonicalize one durable schedule entry."""

    if (
        not isinstance(value, Mapping)
        or value.get("schema") != NUMERICAL_SCHEDULE_SCHEMA
    ):
        raise NumericalScheduleError("numerical schedule entry is invalid")
    raw_policy = value.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise NumericalScheduleError("numerical schedule policy is invalid")
    policy = normalize_policy(
        period=raw_policy.get("period"),
        quantum=raw_policy.get("quantum"),
        rest_policy=raw_policy.get("rest_policy"),
        tolerance=raw_policy.get("tolerance"),
        sync_group=raw_policy.get("sync_group"),
        operator_sha256=raw_policy.get("operator_sha256"),
        activity_floor=raw_policy.get("activity_floor"),
    )
    entry = dict(value)
    entry["policy"] = policy
    _identifier(entry["base_work_id"], "schedule base_work_id")
    _hex_digest(entry["dependency_sha256"], "entry dependency_sha256")
    _integer(entry["epoch"], "entry epoch")
    _integer(entry["next_due_tick"], "entry next_due_tick", minimum=1)
    if entry["state"] not in {"awake", "resting"}:
        raise NumericalScheduleError("entry state must be 'awake' or 'resting'")
    return entry


def new_entry(
    *, base_work_id: str, dependency_sha256: str, policy: Mapping[str, Any],
    arguments: Any, kind: Any, source_revision_ids: Any, assumptions: Any,
) -> dict[str, Any]:
    return normalize_entry(
        {
            "schema": NUMERICAL_SCHEDULE_SCHEMA,
            "base_work_id": base_work_id,
            "dependency_sha256": dependency_sha256,
            "policy": dict(policy),
            "arguments": arguments,
            "kind": kind,
            "source_revision_ids": list(source_revision_ids),
            "assumptions": assumptions,
            "epoch": 0,
            "state": "awake",
            "next_due_tick": 1,
            "last_rest_receipt": None,
            "last_wake_receipt": None,
            "last_decision": None,
        }
    )
