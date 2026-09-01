"""Bounded W10A experience executor.

The executor consumes a previously sealed W10E plan and a small adapter made
from the repository's canonical public runtime APIs.  It never imports a
provider, opens a socket, chooses a future event, or writes persistent field
state.  Missing dependencies are an explicit ``BLOCKED`` result, not a
synthetic pass.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes, canonical_json_loads
from run_cassi_qi_experience_plan import (
    DEFAULT_OUTPUT_ROOT as DEFAULT_PLAN_ROOT,
    ExperiencePlanError,
    build_experience_plan,
    seal_experience_plan,
    validate_experience_plan,
)

RESULT_SCHEMA = "cassi.qi-flow-field-experience-result.v1"
RESULT_HASH_DOMAIN = RESULT_SCHEMA
DEFAULT_OUTPUT_ROOT = DEFAULT_PLAN_ROOT.parent / "g10a-experience"
MAX_EXECUTION_EVENTS = 4096


class ExperienceExecutionError(ValueError):
    """Raised only for malformed result inputs or impossible executor state."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def _bits(value: Any) -> float:
    if not isinstance(value, str) or not value.startswith("f64:") or len(value) != 20:
        raise ExperienceExecutionError("BUDGET_INVALID", "declared budget must be a finite f64 bit string")
    try:
        raw = bytes.fromhex(value[4:])
        result = struct.unpack(">d", raw)[0]
    except (ValueError, struct.error) as error:
        raise ExperienceExecutionError("BUDGET_INVALID", "declared budget has malformed f64 bits") from error
    if not math.isfinite(result) or result < 0.0:
        raise ExperienceExecutionError("BUDGET_INVALID", "declared budget must be finite and nonnegative")
    return result


def _copy(value: Any) -> Any:
    """Copy state/event material before crossing the runtime adapter seam."""
    return copy.deepcopy(value)


def _result_hash(result: Mapping[str, Any]) -> str:
    material = {key: value for key, value in result.items() if key != "result_sha256"}
    return canonical_hash(material, RESULT_HASH_DOMAIN)


def _result(
    *,
    plan: Mapping[str, Any],
    status: str,
    reason: str,
    episodes: Sequence[Mapping[str, Any]] = (),
    raw_trace: Sequence[Mapping[str, Any]] = (),
    stopped: bool = False,
    budget_used: float = 0.0,
) -> dict[str, Any]:
    if status not in {"PASS", "FAIL", "NULL", "BLOCKED"}:
        raise ExperienceExecutionError("RESULT_INVALID", f"unknown execution status {status!r}")
    trace = [dict(row) for row in raw_trace]
    body: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "result_id": f"g10a:{plan['self_sha256']}",
        "plan_sha256": plan["plan_sha256"],
        "plan_self_sha256": plan["self_sha256"],
        "status": status,
        "reason": str(reason),
        "stopped": bool(stopped),
        "budget_used": f"f64:{struct.pack('>d', float(budget_used)).hex()}",
        "episodes": [dict(row) for row in episodes],
        "raw_trace": trace,
        "raw_trace_sha256": hashlib.sha256(canonical_json_bytes(trace)).hexdigest(),
    }
    body["result_sha256"] = _result_hash(body)
    return body


def _event_rows(
    dependencies: Mapping[str, Any], episode_id: str, *, control: bool = False
) -> list[Any] | None:
    key = "controls" if control else "events"
    source = dependencies.get(key)
    if not isinstance(source, Mapping) or episode_id not in source:
        return None
    values = source[episode_id]
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return None
    return [_copy(value) for value in values]


def _initial_state(dependencies: Mapping[str, Any], episode: Mapping[str, Any]) -> tuple[bool, Any]:
    source = dependencies.get("initial_states")
    if isinstance(source, Mapping) and episode["episode_id"] in source:
        return True, _copy(source[episode["episode_id"]])
    loader = dependencies.get("load_initial_state")
    if callable(loader):
        try:
            return True, _copy(loader(episode["initial_state_sha256"]))
        except Exception:
            return False, None
    return False, None


def _work_value(result: Any, dependencies: Mapping[str, Any], episode_id: str, index: int) -> float | None:
    value: Any = None
    if isinstance(result, Mapping):
        for key in ("admitted_work", "work", "cost"):
            if key in result:
                value = result[key]
                break
    if value is None:
        source = dependencies.get("work")
        if isinstance(source, Mapping):
            value = source.get((episode_id, index), source.get(episode_id))
        elif callable(source):
            try:
                value = source(episode_id, index)
            except Exception:
                value = None
        elif isinstance(source, (int, float)) and not isinstance(source, bool):
            value = source
    if isinstance(value, str) and value.startswith("f64:"):
        try:
            value = _bits(value)
        except ExperienceExecutionError:
            return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and value >= 0.0 else None


def _committed(result: Any) -> bool:
    if isinstance(result, Mapping):
        if result.get("committable") is False or result.get("committed") is False:
            return False
        if "committable" in result or "committed" in result:
            return bool(result.get("committable", result.get("committed", False)))
    return True


def execute_experience(
    plan: Mapping[str, Any],
    *,
    dependencies: Mapping[str, Any] | None = None,
    max_events: int = MAX_EXECUTION_EVENTS,
) -> dict[str, Any]:
    """Execute bounded whole-episode trajectories against private state copies.

    Required adapter dependencies are intentionally explicit: ``advance`` must
    be a callable canonical public API, ``initial_states`` (or
    ``load_initial_state``) must provide each selected episode, and ``events``
    must provide immutable event sequences.  Controls use a separate
    ``controls`` mapping and can never share treatment event IDs.
    """
    try:
        sealed = validate_experience_plan(plan)
    except ExperiencePlanError:
        raise
    if not isinstance(dependencies, Mapping):
        return _result(plan=sealed, status="BLOCKED", reason="missing canonical execution dependencies")
    advance = dependencies.get("advance")
    if not callable(advance):
        return _result(plan=sealed, status="BLOCKED", reason="missing canonical advance API")
    if not (isinstance(dependencies.get("events"), Mapping) and (isinstance(dependencies.get("initial_states"), Mapping) or callable(dependencies.get("load_initial_state")))):
        return _result(plan=sealed, status="BLOCKED", reason="missing immutable whole-episode inputs")
    if not isinstance(max_events, int) or isinstance(max_events, bool) or max_events < 1:
        raise ExperienceExecutionError("HORIZON_INVALID", "max_events must be a positive integer")
    max_events = min(max_events, MAX_EXECUTION_EVENTS)
    episodes = list(sealed["grounded_world_episode_streams"])
    total_upper = _bits(sealed["work_budgets"]["total"]["upper"])
    per_event_upper = _bits(sealed["work_budgets"]["per_event"]["upper"])
    stopping_minimum = int(sealed["stopping_rule"]["minimum_valid_episodes"])
    seen_ids: set[str] = set()
    treatment_ids: set[str] = set()
    control_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    budget_used = 0.0
    event_count = 0
    valid_count = 0
    for episode in episodes:
        episode_id = str(episode["episode_id"])
        ok, state = _initial_state(dependencies, episode)
        if not ok:
            return _result(plan=sealed, status="BLOCKED", reason=f"missing initial state for episode {episode_id}", episodes=rows, raw_trace=trace, budget_used=budget_used)
        events = _event_rows(dependencies, episode_id)
        controls = _event_rows(dependencies, episode_id, control=True)
        if events is None:
            return _result(plan=sealed, status="BLOCKED", reason=f"missing treatment events for episode {episode_id}", episodes=rows, raw_trace=trace, budget_used=budget_used)
        controls = [] if controls is None else controls
        if event_count + len(events) + len(controls) > max_events:
            return _result(plan=sealed, status="FAIL", reason="declared execution horizon exhausted", episodes=rows, raw_trace=trace, stopped=True, budget_used=budget_used)
        episode_work = 0.0
        episode_ok = True
        for control_kind, batch, target_ids in (("treatment", events, treatment_ids), ("control", controls, control_ids)):
            for index, event in enumerate(batch):
                event_id = event.get("event_id") if isinstance(event, Mapping) else None
                if not isinstance(event_id, str):
                    event_id = f"{episode_id}:{control_kind}:{index}"
                if event_id in seen_ids:
                    return _result(plan=sealed, status="FAIL", reason="treatment/control event identity overlap", episodes=rows, raw_trace=trace, stopped=True, budget_used=budget_used)
                seen_ids.add(event_id)
                target_ids.add(event_id)
                try:
                    candidate = advance(_copy(state), _copy(event))
                except Exception as error:
                    return _result(plan=sealed, status="FAIL", reason=f"canonical advance failed: {type(error).__name__}", episodes=rows, raw_trace=trace, stopped=True, budget_used=budget_used)
                work = _work_value(candidate, dependencies, episode_id, index)
                if work is None:
                    return _result(plan=sealed, status="BLOCKED", reason="advance returned no finite admitted work", episodes=rows, raw_trace=trace, budget_used=budget_used)
                if work > per_event_upper or budget_used + work > total_upper:
                    trace.append({"episode_id": episode_id, "event_id": event_id, "control_kind": control_kind, "status": "budget_stop", "work": work})
                    return _result(plan=sealed, status="FAIL", reason="declared work budget exhausted", episodes=rows, raw_trace=trace, stopped=True, budget_used=budget_used)
                budget_used += work
                episode_work += work
                event_count += 1
                committed = _committed(candidate)
                trace.append({"episode_id": episode_id, "event_id": event_id, "control_kind": control_kind, "work": work, "committed": committed})
                if control_kind == "treatment":
                    if not committed:
                        episode_ok = False
                    else:
                        state = _copy(candidate.get("state", candidate) if isinstance(candidate, Mapping) else candidate)
        row = {"episode_id": episode_id, "event_count": len(events), "control_count": len(controls), "work": f"f64:{struct.pack('>d', episode_work).hex()}", "valid": episode_ok}
        rows.append(row)
        if episode_ok:
            valid_count += 1
        if valid_count >= stopping_minimum and stopping_minimum > 0:
            break
    if not rows:
        return _result(plan=sealed, status="NULL", reason="no whole episodes selected", episodes=rows, raw_trace=trace, budget_used=budget_used)
    if valid_count < stopping_minimum:
        return _result(plan=sealed, status="NULL", reason="minimum valid episode stopping rule not met", episodes=rows, raw_trace=trace, budget_used=budget_used)
    return _result(plan=sealed, status="PASS", reason="bounded whole-episode execution satisfied stopping rule", episodes=rows, raw_trace=trace, budget_used=budget_used)


def validate_experience_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ExperienceExecutionError("RESULT_INVALID", "result must be an object")
    required = {"schema", "result_id", "plan_sha256", "plan_self_sha256", "status", "reason", "stopped", "budget_used", "episodes", "raw_trace", "raw_trace_sha256", "result_sha256"}
    if set(result) != required:
        raise ExperienceExecutionError("RESULT_KEYS_INVALID", "result fields are not exact")
    if result.get("schema") != RESULT_SCHEMA or result.get("status") not in {"PASS", "FAIL", "NULL", "BLOCKED"}:
        raise ExperienceExecutionError("RESULT_INVALID", "result schema or status is invalid")
    if _result_hash(result) != result.get("result_sha256"):
        raise ExperienceExecutionError("RESULT_HASH_MISMATCH", "result_sha256 does not match canonical result")
    try:
        if hashlib.sha256(canonical_json_bytes(result["raw_trace"])).hexdigest() != result["raw_trace_sha256"]:
            raise ExperienceExecutionError("RAW_TRACE_HASH_MISMATCH", "raw_trace_sha256 does not match retained trace")
    except Exception as error:
        if isinstance(error, ExperienceExecutionError):
            raise
        raise ExperienceExecutionError("RESULT_INVALID", "raw_trace is not canonical") from error
    return copy.deepcopy(dict(result))


def run_experience(
    plan: Mapping[str, Any] | None = None,
    *,
    dependencies: Mapping[str, Any] | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Seal a plan before execution and retain separately hashed raw results."""
    selected = plan if plan is not None else build_experience_plan()
    sealed, plan_raw, _ = seal_experience_plan(selected)
    result = execute_experience(sealed, dependencies=dependencies)
    destination = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    destination.mkdir(parents=True, exist_ok=True)
    plan_path = destination / "experience-plan.json"
    result_path = destination / "experience-result.json"
    if plan_path.exists() and plan_path.read_bytes() != plan_raw:
        raise ExperienceExecutionError("PLAN_MUTATION", "existing plan bytes differ from the sealed plan")
    plan_path.write_bytes(plan_raw)
    result_raw = canonical_json_bytes(result)
    if result_path.exists() and result_path.read_bytes() != result_raw:
        raise ExperienceExecutionError("RESULT_MUTATION", "existing result bytes differ from the sealed result")
    result_path.write_bytes(result_raw)
    return {"plan": sealed, "result": result, "plan_path": str(plan_path), "result_path": str(result_path)}


def _load_plan(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    try:
        value = canonical_json_loads(raw)
    except Exception as error:
        raise ExperienceExecutionError("NONCANONICAL_ENCODING", f"{path} is not canonical JSON") from error
    if canonical_json_bytes(value) != raw:
        raise ExperienceExecutionError("NONCANONICAL_ENCODING", f"{path} is not byte-canonical")
    return validate_experience_plan(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)
    try:
        plan = _load_plan(args.plan) if args.plan else build_experience_plan()
        artifact = run_experience(plan, output_root=args.out)
    except (ExperiencePlanError, ExperienceExecutionError) as error:
        print(json.dumps({"status": "BLOCKED" if error.code.startswith("MISSING") else "FAIL", "code": error.code, "message": error.message}, sort_keys=True))
        return 2
    print(canonical_json_bytes({"plan": artifact["plan_path"], "result": artifact["result_path"], "status": artifact["result"]["status"], "result_sha256": artifact["result"]["result_sha256"]}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
