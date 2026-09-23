"""Engineering rail measurements for the Shifting Laboratory.

The rail is deliberately an observation layer.  It never infers a placement from
an admission request: a placement is *honored* only when the settled computation
view exposes the requested/actual placement and the two values agree.  Failed
HTTP calls are counted separately and never enter latency statistics.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import time
from typing import Any, Callable, Mapping, Sequence

try:
    from cassi_program_benchmark_client import (
        PROGRAM_BACKENDS,
        backend_policy,
        inline_text_reference,
        program_proposal,
        owner_state_sha256,
    )
except ImportError:  # package import when CassiQwen is on sys.path
    from ..cassi_program_benchmark_client import (  # type: ignore
        PROGRAM_BACKENDS,
        backend_policy,
        inline_text_reference,
        program_proposal,
        owner_state_sha256,
    )

RAIL_SCHEMA = "cassi.laboratory.rail.v1"
STATION_REPORT_SCHEMA = "cassi.laboratory.station-report.v1"
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
DEFAULT_REPETITIONS = 3
MAX_SETTLE_READS = 8


def _json(value: Any) -> Any:
    """Convert incidental values to JSON-safe values without hiding facts."""
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    return str(value)


def _payload(sample: Any) -> Mapping[str, Any]:
    value = getattr(sample, "payload", None)
    return value if isinstance(value, Mapping) else {}


def _sample_failure(sample: Any) -> str:
    error = getattr(sample, "error", "")
    return str(error or getattr(sample, "detail", "request failed") or "request failed")


def _percentile(values: Sequence[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) / 1_000_000_000.0 for v in values)
    rank = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return round(ordered[rank], 9)


def _latency(values: Sequence[int], excluded: int) -> dict[str, Any]:
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": round(max(values) / 1_000_000_000.0, 9) if values else None,
        "samples": len(values),
        "excluded_failures": int(excluded),
    }


def _inventory(client: Any) -> tuple[str, ...]:
    if client is None:
        return ()
    try:
        sample = client.health()
    except Exception:
        return ()
    payload = _payload(sample)

    def find_available(node: Any) -> tuple[str, ...]:
        if isinstance(node, Mapping):
            values = node.get("available_backends")
            if isinstance(values, (list, tuple)):
                return tuple(str(value) for value in values)
            for value in node.values():
                found = find_available(value)
                if found:
                    return found
        elif isinstance(node, (list, tuple)):
            for value in node:
                found = find_available(value)
                if found:
                    return found
        return ()

    return find_available(payload)


def _declared(item: Any, index: int, inventory: Sequence[str]) -> dict[str, Any]:
    """Normalize the locked ``{placement_id, declared, runner, requests}`` shape.

    The runner is retained only in a private key and is never emitted in the
    JSON report.  This keeps reports serializable while allowing a caller to
    provide a deterministic in-process validation function.
    """
    if isinstance(item, str):
        return {
            "placement_id": f"placement-{index + 1}",
            "declared": {"backend": item},
            "_runner": None,
            "_requests": None,
        }
    if not isinstance(item, Mapping):
        return {
            "placement_id": f"placement-{index + 1}",
            "declared": {"backend": None, "declaration": _json(item)},
            "_runner": None,
            "_requests": None,
        }
    placement_id = item.get("placement_id", f"placement-{index + 1}")
    nested = item.get("declared")
    if isinstance(nested, Mapping):
        declaration = dict(nested)
    else:
        declaration = {
            key: value
            for key, value in item.items()
            if key not in {"placement_id", "runner", "requests"}
        }
    if "backend" not in declaration:
        declaration["backend"] = declaration.get("preferred")
    requests = item.get("requests")
    return {
        "placement_id": str(placement_id),
        "declared": _json(declaration),
        "_runner": item.get("runner") if callable(item.get("runner")) else None,
        "_runner_label": item.get("runner") if isinstance(item.get("runner"), str) else None,
        "_requests": requests if isinstance(requests, int) and not isinstance(requests, bool) else None,
    }


def _backend(declared: Mapping[str, Any]) -> Any:
    nested = declared.get("declared")
    return nested.get("backend") if isinstance(nested, Mapping) else declared.get("backend")


def _view_placement(view: Mapping[str, Any]) -> tuple[Any, int]:
    """Read only execution-view placement fields, never declaration policy.

    ``backend_policy`` and ``proposal`` describe what was requested; treating
    either as an observed placement would turn an unobservable declaration into
    a false ``honored=True`` result.
    """
    fields = 0
    values: list[Any] = []
    nodes: list[Mapping[str, Any]] = [view]
    for key in ("view", "result", "computation", "execution", "runtime", "placement"):
        value = view.get(key)
        if isinstance(value, Mapping):
            nodes.append(value)
    for node in nodes:
        for key in ("placement", "actual_placement", "backend"):
            if key in node:
                fields += 1
                value = node[key]
                if value not in (None, ""):
                    values.append(value)
    return (values[0] if values else None), fields


def _actual_backend(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        for key in ("backend", "name", "placement", "actual_placement", "preferred"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _view_status(view: Mapping[str, Any]) -> str | None:
    for key in ("status", "state"):
        value = view.get(key)
        if isinstance(value, str):
            return value.lower()
    for key in ("view", "result"):
        nested = view.get(key)
        if isinstance(nested, Mapping):
            status = _view_status(nested)
            if status is not None:
                return status
    return None

def _view_result(view: Mapping[str, Any]) -> Any:
    result = view.get("result")
    return result if isinstance(result, Mapping) else None


def _report(*, placements: Sequence[Mapping[str, Any]], controls: Sequence[Mapping[str, Any]], notes: Sequence[str], measurements: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _json({
        "schema": "cassi.laboratory.rail-report.v1",
        "placements": list(placements),
        "controls": list(controls),
        "notes": list(notes),
        "measurements": dict(measurements or {}),
    })


def _empty_row(declared: Mapping[str, Any], *, note: str, mirror: bool = False) -> dict[str, Any]:
    return {
        "placement_id": str(declared.get("placement_id", "placement")),
        "declared": dict(declared.get("declared", declared)),
        "settled": False,
        "honored": None,
        "honored_detail": note,
        "substituted": None,
        "requests": 0,
        "failures": 0,
        "failure_details": [],
        "latency_s": _latency([], 0),
        "throughput_per_s": None,
        "mirrored_validation": bool(mirror),
        "independent": not mirror,
    }


def _source(work: Any, declared: Mapping[str, Any]) -> str | None:
    if isinstance(work, str):
        return work
    if isinstance(work, Mapping):
        value = work.get("source")
        if isinstance(value, str):
            return value
    nested = declared.get("declared")
    if isinstance(nested, Mapping) and isinstance(nested.get("source"), str):
        return str(nested["source"])
    value = declared.get("source")
    return value if isinstance(value, str) else None


def _program_id(work: Any) -> str | None:
    if isinstance(work, Mapping) and isinstance(work.get("program_id"), str):
        return str(work["program_id"])
    return None


def _tag(work: Any, default: str) -> str:
    if isinstance(work, Mapping) and isinstance(work.get("tag"), str):
        return str(work["tag"])
    return default


def _settle(client: Any, program_id: str, computation_id: str, *, row: dict[str, Any]) -> tuple[Mapping[str, Any] | None, bool, int]:
    view: Mapping[str, Any] | None = None
    reads = 0
    for _ in range(MAX_SETTLE_READS):
        sample = client.inspect_computation(program_id, computation_id)
        reads += 1
        row["requests"] += 1
        if not getattr(sample, "ok", False):
            row["failures"] += 1
            row["failure_details"].append(_sample_failure(sample))
            return None, False, reads
        candidate = _payload(sample)
        view = candidate
        status = _view_status(candidate)
        if status in TERMINAL_STATUSES:
            return candidate, True, reads
    return view, False, reads


def _one_remote(client: Any, *, declared: Mapping[str, Any], program_id: str, tag: str, source: str, repetition: int, row: dict[str, Any]) -> None:
    backend = _backend(declared)
    if not isinstance(backend, str) or not backend:
        row["failures"] += 1
        row["failure_details"].append("declaration has no backend")
        return
    health = client.health()
    row["requests"] += 1
    if not getattr(health, "ok", False):
        row["failures"] += 1
        row["failure_details"].append(_sample_failure(health))
        return
    revision = owner_state_sha256(_payload(health))
    if not revision:
        row["failures"] += 1
        row["failure_details"].append("health response exposed no owner.state_sha256")
        return
    computation_id = f"rail-{tag}-{backend}-{repetition}"
    request_id = f"rail-admit-{tag}-{backend}-{repetition}"
    proposal = program_proposal(
        language="python",
        profile={"mode": "exec", "steps": 64},
        source_reference=inline_text_reference(f"rail-{tag}", source),
        backend_policy=backend_policy(backend, allowed=[backend], required=True),
    )
    arrival = time.perf_counter_ns()
    sample = client.admit_computation(
        program_id,
        request_id=request_id,
        computation_id=computation_id,
        expected_owner_state_sha256=revision,
        proposal=proposal,
    )
    row["requests"] += 1
    if not getattr(sample, "ok", False):
        row["failures"] += 1
        row["failure_details"].append(_sample_failure(sample))
        return
    view, settled, reads = _settle(client, program_id, computation_id, row=row)
    if not settled or view is None:
        row["unsettled"] += 1
        return
    status = _view_status(view)
    if status != "completed":
        row["failures"] += 1
        row["failure_details"].append(f"computation settled with status {status!r}")
        return
    row["settled_samples"] += 1
    row["latencies_ns"].append(max(0, time.perf_counter_ns() - arrival))
    observed, fields = _view_placement(view)
    actual = _actual_backend(observed)
    if actual is None:
        row["honored_values"].append(None)
        row["honored_details"].append("settled view exposed no observable placement")
    else:
        honored = actual == backend
        row["honored_values"].append(honored)
        row["honored_details"].append(f"observed placement {actual!r}; requested {backend!r}; keys={fields}")
        row["substituted_values"].append(actual != backend)
    row["settled_views"].append(view)


def _one_local(runner: Callable[..., Any], *, declared: Mapping[str, Any], repetition: int, row: dict[str, Any]) -> None:
    arrival = time.perf_counter_ns()
    row["requests"] += 1
    public_declared = dict(declared.get("declared", declared))
    try:
        result = runner(public_declared, repetition=repetition)
    except TypeError:
        result = runner(public_declared)
    except Exception as exc:  # local runner failure is a measured failure
        row["failures"] += 1
        row["failure_details"].append(f"{type(exc).__name__}: {exc}")
        return
    if not isinstance(result, Mapping):
        row["failures"] += 1
        row["failure_details"].append("local runner returned no observed mapping")
        return
    status = str(result.get("status", "completed")).lower()
    if status == "failed" or status == "cancelled":
        row["failures"] += 1
        row["failure_details"].append(f"local runner settled with status {status!r}")
        return
    if status != "completed":
        row["unsettled"] += 1
        return
    row["settled_samples"] += 1
    row["latencies_ns"].append(max(0, time.perf_counter_ns() - arrival))
    actual = _actual_backend(result.get("actual_placement", result.get("placement", result.get("backend"))))
    requested = _backend(declared)
    if actual is None:
        row["honored_values"].append(None)
        row["honored_details"].append("local result exposed no observable placement")
    else:
        row["honored_values"].append(actual == requested)
        row["honored_details"].append(f"observed placement {actual!r}; requested {requested!r}")
        row["substituted_values"].append(actual != requested)


def _finish_row(row: dict[str, Any]) -> dict[str, Any]:
    honors = row.pop("honored_values")
    substitutions = row.pop("substituted_values")
    details = row.pop("honored_details")
    latencies = row.pop("latencies_ns")
    row["settled"] = bool(row.pop("settled_samples") > 0 and row.pop("unsettled") == 0 and row["failures"] == 0)
    row["honored"] = honors[-1] if honors and all(value == honors[0] for value in honors) else None
    row["honored_detail"] = "; ".join(dict.fromkeys(details)) if details else "no settled response was observed"
    row["substituted"] = substitutions[-1] if substitutions and all(value == substitutions[0] for value in substitutions) else None
    row["latency_s"] = _latency(latencies, row["failures"])
    row["throughput_per_s"] = round(len(latencies) / (sum(latencies) / 1_000_000_000.0), 6) if latencies and sum(latencies) > 0 else None
    row["failure_details"] = row["failure_details"][:16]
    return row

def _run_placements(client: Any, declarations: Sequence[Mapping[str, Any]], *, work: Any, repetitions: int) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    seen: set[tuple[Any, ...]] = set()
    default_runner = work if callable(work) else (work.get("runner") if isinstance(work, Mapping) and callable(work.get("runner")) else None)
    program_id = _program_id(work)
    tag = _tag(work, "rail")
    for declared in declarations:
        declaration = declared.get("declared", {})
        if not isinstance(declaration, Mapping):
            declaration = {}
        key = (_backend(declared), tuple(sorted((str(k), repr(v)) for k, v in declaration.items())))
        mirror = key in seen
        seen.add(key)
        row = _empty_row(declared, note="unmeasured", mirror=mirror)
        if mirror:
            row["honored_detail"] = "mirrored validation: duplicate declaration; not counted as an independent placement"
            notes.append(f"{row['placement_id']} is mirrored validation, not an independent placement")
            rows.append(row)
            continue
        runner = declared.get("_runner") or default_runner
        if runner is not None:
            row.update({"unsettled": 0, "settled_samples": 0, "latencies_ns": [], "honored_values": [], "substituted_values": [], "honored_details": []})
            count = declared["_requests"] if declared.get("_requests") is not None else repetitions
            for repetition in range(max(0, min(int(count), 32))):
                _one_local(runner, declared=declared, repetition=repetition, row=row)
            rows.append(_finish_row(row))
            continue
        if declared.get("_runner_label") is not None:
            row["honored_detail"] = f"blocked: runner label {declared['_runner_label']!r} has no executable callable"
            notes.append(f"{row['placement_id']} names a runner label but was not executed")
            rows.append(row)
            continue
        if client is None:
            row["honored_detail"] = "blocked: no entity client or local runner was supplied"
            rows.append(row)
            continue
        source = _source(work, declared)
        if not program_id or not source:
            row["honored_detail"] = "blocked: work must supply program_id and source for entity measurement"
            rows.append(row)
            continue
        row.update({"unsettled": 0, "settled_samples": 0, "latencies_ns": [], "honored_values": [], "substituted_values": [], "honored_details": [], "settled_views": []})
        count = declared["_requests"] if declared.get("_requests") is not None else repetitions
        for repetition in range(max(0, min(int(count), 32))):
            _one_remote(client, declared=declared, program_id=program_id, tag=tag, source=source, repetition=repetition, row=row)
        rows.append(_finish_row(row))
    return rows, notes


def _control(client: Any, declarations: Sequence[Mapping[str, Any]], *, work: Any) -> dict[str, Any]:
    """A deliberately invalid declaration proves the rail can fail."""
    if client is None:
        return {"name": "invalid-backend-control", "ok": False, "detail": "blocked: no client; expected refusal was not exercised"}
    program_id = _program_id(work)
    source = _source(work, {})
    if not program_id or not source:
        return {"name": "invalid-backend-control", "ok": False, "detail": "blocked: work lacks program_id/source"}
    try:
        health = client.health()
        if not getattr(health, "ok", False):
            return {"name": "invalid-backend-control", "ok": False, "detail": f"blocked by health failure: {_sample_failure(health)}"}
        revision = owner_state_sha256(_payload(health))
        if not revision:
            return {"name": "invalid-backend-control", "ok": False, "detail": "blocked: no owner revision"}
        proposal = program_proposal(language="python", profile={"mode": "exec", "steps": 1}, source_reference=inline_text_reference("rail-invalid", source), backend_policy=backend_policy("definitely-invalid-backend", allowed=["definitely-invalid-backend"], required=True))
        sample = client.admit_computation(program_id, request_id="rail-invalid-control", computation_id="rail-invalid-control", expected_owner_state_sha256=revision, proposal=proposal)
        refused = not bool(getattr(sample, "ok", False))
        return {"name": "invalid-backend-control", "ok": refused, "detail": f"control {'refused as required' if refused else 'was unexpectedly accepted'}: {_sample_failure(sample) if refused else 'no failure'}"}
    except Exception as exc:
        return {"name": "invalid-backend-control", "ok": False, "detail": f"control could not be classified as an expected refusal: {type(exc).__name__}: {exc}"}


def measure_rail(*, client: Any = None, placements: Sequence[Any] | None = None, work: Any = None, home: Any = None, workspace: Any = None) -> dict[str, Any]:
    """Measure declared placements, or return an honest blocked report.

    ``work`` may be a mapping containing ``program_id``, ``source``, and ``tag``
    for the entity client, or a callable local runner.  A local runner receives
    the declared mapping and optional ``repetition`` integer, and must return
    a terminal ``status`` and, to establish placement, ``actual_placement``.
    """
    inventory = _inventory(client) if client is not None else ()
    if placements is None:
        if client is None and not callable(work) and not (isinstance(work, Mapping) and callable(work.get("runner"))):
            raw = []
        else:
            raw = [{"placement_id": f"backend-{name}", "backend": name} for name in inventory]
    else:
        raw = list(placements)
    declarations = [_declared(item, index, inventory) for index, item in enumerate(raw)]
    repetitions = 1
    if isinstance(work, Mapping):
        value = work.get("repetitions", DEFAULT_REPETITIONS)
        if isinstance(value, int) and not isinstance(value, bool):
            repetitions = max(1, min(value, 32))
    rows, notes = _run_placements(client, declarations, work=work, repetitions=repetitions)
    control = _control(client, declarations, work=work)
    if client is None and not callable(work) and not (isinstance(work, Mapping) and callable(work.get("runner"))):
        notes.append("No backend was measured: client=None and no local runner were supplied; null honored values are intentional.")
    if home is not None or workspace is not None:
        notes.append("home/workspace arguments are accepted for course compatibility but do not alter placement observations")
    attempted = sum(int(row.get("requests", 0)) for row in rows)
    failures = sum(int(row.get("failures", 0)) for row in rows)
    return _report(placements=rows, controls=[control], notes=notes, measurements={"backends_declared": list(inventory), "attempted_requests": attempted, "failures": failures, "latency_excludes_failures": True, "independent_placements": sum(1 for row in rows if row.get("independent"))})


def placement_rail(client: Any, *, program_id: str, tag: str, source: str, repetitions: int = DEFAULT_REPETITIONS) -> dict[str, Any]:
    """Compatibility entry for measuring all client-declared backends."""
    return measure_rail(client=client, work={"program_id": program_id, "tag": tag, "source": source, "repetitions": repetitions})


def throughput_rail(client: Any, *, program_id: str, tag: str, source: str, owners: int) -> dict[str, Any]:
    """Run independent computations concurrently and keep failures separate."""
    if client is None or not isinstance(owners, int) or owners < 1:
        return _report(placements=[], controls=[{"name": "throughput-input", "ok": False, "detail": "blocked: live client and positive owners are required"}], notes=["Throughput was not measured."], measurements={"owners": owners, "failures": 0, "latency_excludes_failures": True})
    backend = _inventory(client)[0] if _inventory(client) else "logical-cpu"
    arrivals = time.perf_counter_ns()
    def worker(index: int) -> dict[str, Any]:
        row = _empty_row({"placement_id": f"owner-{index + 1}", "backend": backend}, note="throughput")
        row.update({"unsettled": 0, "settled_samples": 0, "latencies_ns": [], "honored_values": [], "substituted_values": [], "honored_details": [], "settled_views": []})
        _one_remote(client, declared=row["declared"], program_id=program_id, tag=tag, source=source, repetition=index, row=row)
        return _finish_row(row)
    with ThreadPoolExecutor(max_workers=owners) as pool:
        futures = [pool.submit(worker, index) for index in range(owners)]
        rows = [future.result() for future in as_completed(futures)]
    wall_ns = max(1, time.perf_counter_ns() - arrivals)
    valid = sum(1 for row in rows if row.get("settled"))
    return _report(placements=rows, controls=[], notes=["Throughput rows are independent computations; owner-revision refusals remain failures."], measurements={"owners": owners, "valid_settled_work": valid, "wall_time_s": round(wall_ns / 1_000_000_000.0, 9), "throughput_per_s": round(valid / (wall_ns / 1_000_000_000.0), 6), "failures": sum(int(row.get("failures", 0)) for row in rows), "latency_excludes_failures": True})


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone no-side-effect entry; live setup belongs to the course CLI."""
    report = measure_rail(client=None)
    import json
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


__all__ = ["RAIL_SCHEMA", "measure_rail", "placement_rail", "throughput_rail", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
