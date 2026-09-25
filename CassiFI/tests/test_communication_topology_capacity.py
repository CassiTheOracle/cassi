"""Bounded communication-topology capacity, declared-route selection, replay."""
from __future__ import annotations

from pathlib import Path
import hashlib
import sys

import pytest

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

from cassi_field_atlas import FieldIntelligenceError, sha256_value
from cassi_field_cognition import (
    COMMUNICATION_TOPOLOGY_ROUTES,
    COMMUNICATION_TOPOLOGY_SCHEMA,
    _semantic_validate_topology_state,
)
from cassi_field_communication import (
    CONSUMPTION_SCHEMA,
    FieldIntent,
    RESULT_SCHEMA,
    actual_use_ack,
)
from cassi_research_residency import (
    _declared_communication_route,
    _work_items,
    open_research_residency,
)
from cassi_research_worlds import initial_work as world_initial_work

_BOUNDS = {"max_records": 16_384, "max_operations": 16_384, "max_versions": 128}


def _route_row(successful: int, unsuccessful: int = 0) -> dict[str, object]:
    total = successful + unsuccessful
    return {
        "successful": successful,
        "unsuccessful": unsuccessful,
        "score": (successful + 1) / (total + 2),
        "scopes": [],
    }


def _topology(routes: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "schema": COMMUNICATION_TOPOLOGY_SCHEMA,
        "routes": routes,
        "outcomes": [],
        "dependencies": [],
    }


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _craft_operation_id(target: int, prefix: str, span: int) -> str:
    counter = 0
    while True:
        candidate = f"{prefix}:{counter:04d}"
        if int(hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:8], 16) % span == target:
            return candidate
        counter += 1


def _register_use(res: object, index: int, route: str) -> None:
    payload = {
        "predecessor_root_sha256": _digest(f"pred-{index}"),
        "root_sha256": _digest(f"root-{index}"),
        "source_sha256": _digest(f"src-{index}"),
        "changed_pages": [0],
        "object_id": 3,
        "object_version": 1,
    }
    intent = FieldIntent(
        kind="send",
        sender=f"test-sender-{index}",
        receiver="regional-object:9",
        payload_ref=payload,
        dependency_versions=(),
        urgency="background",
        consumer_use_id=f"topology-capacity-use-{index}",
    )
    operation_id = "communication:ack:" + _digest(f"topology-capacity-{index}")[:40]
    result_ref = {
        "schema": RESULT_SCHEMA,
        "operation_id": operation_id,
        "event_id": 70_000 + index,
        "owner_state_sha256": _digest("owner-state"),
        "output": {
            "schema": CONSUMPTION_SCHEMA,
            "intent_sha256": intent.identity,
            "consumer_use_id": intent.consumer_use_id,
            "receiver": intent.receiver,
            "source_object_id": payload["object_id"],
            "source_object_version": payload["object_version"],
            "source_root_sha256": payload["root_sha256"],
            "source_sha256": payload["source_sha256"],
            "target_id": 9,
            "target_version": 1,
            "result_sha256": _digest(f"result-{index}"),
        },
    }
    ack = actual_use_ack(
        operation_id=operation_id, intent=intent, result_ref=result_ref, delay=index
    )
    ack["locality_observation"] = {
        "use_sha256": ack["use_sha256"],
        "route": route,
        "delay": index,
    }
    use_sha256 = ack["use_sha256"]
    res._register(  # type: ignore[attr-defined]
        operation_id,
        "communication:use:" + use_sha256[:40],
        "Event",
        ack,
        epistemic_kind="derived",
    )


def test_topology_state_retains_more_than_128_routes() -> None:
    routes = {f"dev-{k:03d}->target:send": _route_row(k + 1) for k in range(130)}
    validated = _semantic_validate_topology_state(_topology(routes), _BOUNDS)
    assert len(validated["routes"]) == 130


def test_topology_state_bounds_routes_by_evicting_lowest_counts() -> None:
    routes = {f"dev-{k:03d}->target:send": _route_row(k + 1) for k in range(300)}
    validated = _semantic_validate_topology_state(_topology(routes), _BOUNDS)
    assert len(validated["routes"]) == COMMUNICATION_TOPOLOGY_ROUTES
    assert "dev-000->target:send" not in validated["routes"]  # count 1 evicted
    assert "dev-044->target:send" in validated["routes"]  # count 45 kept
    with pytest.raises(FieldIntelligenceError):
        broken = dict(routes["dev-299->target:send"])
        broken["score"] = 0.99
        _semantic_validate_topology_state(
            _topology({**routes, "dev-299->target:send": broken}), _BOUNDS
        )


def test_declared_communication_route_selection_is_stable() -> None:
    assert _declared_communication_route({}, "research:work:00000000:item") is None
    assert _declared_communication_route(
        {"communication_route": ""}, "research:work:00000000:item"
    ) is None
    assert _declared_communication_route(
        {"communication_route": []}, "research:work:00000000:item"
    ) is None
    assert _declared_communication_route(
        {"communication_route": ["ok->t:send", 7]}, "research:work:00000000:item"
    ) is None
    scalar = _declared_communication_route(
        {"communication_route": "one->t:send"}, "anything"
    )
    assert scalar == "one->t:send"
    declared = [f"dev-{k:03d}->target:send" for k in range(131)]
    request = {"communication_route": declared}
    first = _declared_communication_route(request, "research:work:00000001:item")
    assert first in declared
    for _ in range(10):
        assert _declared_communication_route(request, "research:work:00000001:item") == first
    chosen = {
        _declared_communication_route(request, f"research:work:{k:08d}:item")
        for k in range(200)
    }
    assert len(chosen) > 1


def test_replay_reproduces_topology_and_locality_digests(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    home = tmp_path / "residency"
    declared = [f"dev-{k:03d}->target:send" for k in range(3)]
    raw = [
        row
        for row in world_initial_work(workspace)
        if isinstance(row.get("request"), dict)
        and row["request"].get("kind") == "market_world_step"
    ][:2]
    work = []
    for row in raw:
        request = dict(row["request"])
        request.pop("operation_id", None)
        work.append({"id": row["id"], "summary": row["summary"], "request": request})
    work[0]["request"]["communication_route"] = declared
    item0 = work[0]["id"]
    request0 = work[0]["request"]
    work = _work_items(work)

    res = open_research_residency(home)
    try:
        res.initialize(workspace=workspace, work=work)
        for k in range(3):
            operation_id = _craft_operation_id(
                k, f"research:work:{k:08d}:topology-capacity", 3
            )
            route = _declared_communication_route(request0, operation_id)
            assert route == declared[k]
            _register_use(res, k, route)
            outcome_id = f"research:outcome:topology-capacity:{k}"
            res._register(  # type: ignore[attr-defined]
                f"research:topology-capacity:{k}",
                outcome_id,
                "Assessment",
                {"status": "observed", "summary": f"capacity replay {k}"},
            )
            res._revise_communication_topology(  # type: ignore[attr-defined]
                operation_id,
                outcome_ref=dict(res._task()["current"]["Assessment"][outcome_id]),
                question_id=item0,
                compiler_family=request0["kind"],
                result_status="observed",
            )
        topology_before = sha256_value(res._communication_topology() or {})  # type: ignore[attr-defined]
        locality_before = sha256_value(res._communication_locality() or {})  # type: ignore[attr-defined]
        routes_before = dict((res._communication_topology() or {}).get("routes", {}))  # type: ignore[attr-defined]
    finally:
        res.close()

    assert len(routes_before) == 3
    reopened = open_research_residency(home)
    try:
        topology_after = reopened._communication_topology() or {}  # type: ignore[attr-defined]
        locality_after = reopened._communication_locality() or {}  # type: ignore[attr-defined]
        assert sha256_value(topology_after) == topology_before
        assert sha256_value(locality_after) == locality_before
        assert len(topology_after.get("routes", {})) == 3
    finally:
        reopened.close()
