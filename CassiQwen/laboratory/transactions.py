"""Entity-side transaction stations for *The Shifting Laboratory*.

This module deliberately contains no physics.  It drives the real
``ProgramBenchmarkClient`` surface and records what the durable entity accepts,
refuses, replays, settles, and preserves across a restart.

The runtime task table has a known ordering defect: ``programs.runtime._submit``
checks ``max_tasks`` before looking up an existing ``task_id``.  Consequently a
new request for an already resident computation is reported as ``program task
limit exhausted`` at a full table, while the same request with room is reported
as an identity conflict.  The cliff station records this distinction without
attempting to repair it.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from cassi_program_benchmark_client import (
    BenchmarkSample,
    ProgramBenchmarkClient,
    backend_policy,
    inline_text_reference,
    owner_state_sha256,
    program_proposal,
)

from laboratory import stations as _stations
from laboratory.stations import Station


STATION_REPORT_SCHEMA = "cassi.laboratory.station-report.v1"
CLIFF_SCHEMA = "cassi.laboratory.evidence.capacity-cliff.v1"
ACK_SCHEMA = "cassi.laboratory.evidence.acknowledgment.v1"
RECOVERY_SCHEMA = "cassi.laboratory.evidence.durability.v1"

# The runtime kernel's default.  The workspace task consumes one slot, so a
# newly-created program has 255 computation slots.  Callers may pass a smaller
# declared capacity when running a deliberately bounded course.
DEFAULT_TASK_CAPACITY = 255
_FIXED_TIME = "2026-01-01T00:00:00+00:00"


def _report(
    station: str,
    verdict: str,
    checks: Sequence[Mapping[str, Any]],
    controls: Sequence[Mapping[str, Any]],
    measurements: Mapping[str, Any],
    notes: Sequence[str],
) -> dict[str, Any]:
    """Build the frozen §3 station-report shape without importing internals."""

    return {
        "schema": STATION_REPORT_SCHEMA,
        "station": station,
        "verdict": verdict,
        "checks": [dict(item) for item in checks],
        "controls": [dict(item) for item in controls],
        "measurements": dict(measurements),
        "notes": list(notes),
    }


def _safe(value: Any) -> Any:
    """Return a JSON-safe copy for reports (never expose client objects)."""

    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError):
        return str(value)


def _sample(sample: BenchmarkSample) -> dict[str, Any]:
    payload = _safe(sample.payload)
    return {
        "status": sample.status,
        "ok": sample.ok,
        "error_kind": sample.error_kind,
        "error": sample.error,
        "payload": payload,
        "measurement": sample.measurement(),
    }


def _payload_error(sample: BenchmarkSample) -> str | None:
    payload = sample.payload
    if isinstance(payload, Mapping):
        value = payload.get("error")
        return value if isinstance(value, str) else None
    return None


def _payload_kind(sample: BenchmarkSample) -> str | None:
    payload = sample.payload
    if isinstance(payload, Mapping):
        value = payload.get("kind")
        return value if isinstance(value, str) else None
    return None


def _stale_owner(sample: BenchmarkSample) -> bool:
    """Identify the server's refreshable owner-view conflict."""
    if not sample.http_error:
        return False
    text = f"{_payload_error(sample) or ''} {sample.error}".lower()
    return "owner view is stale" in text or "owner state is stale" in text


def _fresh_owner_revision(
    client: ProgramBenchmarkClient, program_id: str
) -> str | None:
    """Force the program-view read requested by a stale-owner response."""
    inspected = client.get_program(program_id)
    revision = owner_state_sha256(inspected.payload)
    if revision is not None:
        return revision
    revision, _ = _owner_revision(client, program_id)
    return revision

def _owner_revision(client: ProgramBenchmarkClient, program_id: str) -> tuple[str | None, BenchmarkSample]:
    """Read the current owner digest, with the program view as a fallback.

    The computation-list route is the canonical admission read, but older
    entity revisions only exposed the digest under ``programmable_computations``
    on the program view.  Never carry a digest forward after a mutation when
    the listing did not expose one.
    """
    sample = client.list_computations(program_id)
    revision = owner_state_sha256(sample.payload)
    if revision is not None:
        return revision, sample
    inspected = client.get_program(program_id)
    inspected_revision = owner_state_sha256(inspected.payload)
    return inspected_revision, inspected if inspected_revision is not None else sample

def _computation_rows(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("computations")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str, int, int, int]:
    return (
        str(row.get("computation_id", row.get("task_id", ""))),
        str(row.get("status", "")),
        str(row.get("state_sha256", "")),
        int(row.get("created_sequence", -1)),
        int(row.get("logical_work", -1)),
        int(row.get("last_work", -1)),
    )


def _snapshot(sample: BenchmarkSample) -> dict[str, Any]:
    payload = sample.payload
    rows = _computation_rows(payload)
    return {
        "owner_state_sha256": owner_state_sha256(payload),
        "task_count": int(payload.get("task_count", len(rows))) if isinstance(payload, Mapping) else len(rows),
        "rows": sorted((_safe(dict(row)) for row in rows), key=lambda row: str(row.get("computation_id", row.get("task_id", "")))),
        "row_keys": sorted(_row_key(row) for row in rows),
        "sample": sample.measurement(),
    }


def _view(client: ProgramBenchmarkClient, program_id: str, computation_id: str) -> tuple[Mapping[str, Any] | None, BenchmarkSample]:
    sample = client.inspect_computation(program_id, computation_id)
    return (sample.payload if isinstance(sample.payload, Mapping) else None), sample


def _view_state(view_payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    view = view_payload.get("view") if isinstance(view_payload, Mapping) else None
    return view if isinstance(view, Mapping) else {}


def _proposal(
    source: str,
    *,
    mode: str = "exec",
    name: str = "transaction.py",
    capabilities: Sequence[str] = (),
    steps: int = 64,
) -> dict[str, Any]:
    return program_proposal(
        language="python",
        profile={"mode": mode, "steps": int(steps)},
        source_reference=inline_text_reference(name, source),
        backend_policy=backend_policy("logical-cpu"),
        capability_requirements=list(capabilities),
        limits={"max_operations": 16, "max_events": 128},
    )


def _admit_request(
    client: ProgramBenchmarkClient,
    program_id: str,
    *,
    computation_id: str,
    request_id: str,
    revision: str,
    source: str,
    mode: str = "exec",
    name: str | None = None,
    capabilities: Sequence[str] = (),
    steps: int = 64,
    observed_at: str = _FIXED_TIME,
) -> tuple[dict[str, Any], BenchmarkSample, dict[str, Any]]:
    proposal = _proposal(
        source,
        mode=mode,
        name=name or f"{computation_id}.py",
        capabilities=capabilities,
        steps=steps,
    )
    sample = client.admit_computation(
        program_id,
        request_id=request_id,
        computation_id=computation_id,
        expected_owner_state_sha256=revision,
        proposal=proposal,
        observed_at=observed_at,
    )
    if _stale_owner(sample):
        refreshed = _fresh_owner_revision(client, program_id)
        if refreshed is not None and refreshed != revision:
            sample = client.admit_computation(
                program_id,
                request_id=request_id,
                computation_id=computation_id,
                expected_owner_state_sha256=refreshed,
                proposal=proposal,
                observed_at=observed_at,
            )
        else:
            # Preserve the original stale response when no fresh revision was
            # observable; callers must not mistake a protocol failure for an
            # accepted computation.
            pass
    return _sample(sample), sample, proposal


def prepare_program(
    client: ProgramBenchmarkClient,
    *,
    program_id: str,
    tag: str,
    allowed_roots: Sequence[str],
    mission: str,
    question: str,
) -> dict[str, Any]:
    """Create or re-open one program using an idempotent, content-bound request."""

    roots = [str(root) for root in allowed_roots]
    request_id = f"{tag}:prepare"
    sample = client.create_program(
        request_id=request_id,
        program_id=program_id,
        project_id=f"{tag}:project",
        title=f"Shifting Laboratory — {tag}",
        mission=mission,
        initial_question=question,
        observed_at=_FIXED_TIME,
        allowed_roots=roots,
        allowed_tools=("list_files", "read_file", "write_artifact", "inspect_artifact"),
    )
    # Always inspect after POST: create responses carry the program body but
    # not the programmable owner digest required by subsequent admissions.
    inspected = client.get_program(program_id)
    payload = inspected.payload if inspected.ok and isinstance(inspected.payload, Mapping) else sample.payload
    revision = owner_state_sha256(payload)
    replay = bool(isinstance(payload, Mapping) and payload.get("idempotent_replay"))
    return {
        "schema": "cassi.laboratory.prepared-program.v1",
        "program_id": program_id,
        "request_id": request_id,
        "created": bool(sample.ok and not replay),
        "accepted": sample.ok,
        "status": sample.status,
        "error_kind": sample.error_kind,
        "error": sample.error,
        "payload": _safe(payload),
        "owner_state_sha256": revision,
        "measurement": sample.measurement(),
    }
 
def _allowed_roots(client: ProgramBenchmarkClient, program_id: str) -> list[str]:
    """Recover the existing program's capability roots for an isolated child.

    The transaction stations intentionally use child programs: the cliff station
    may fill every runtime slot, and that must not make acknowledgement or
    recovery appear to fail.  ``GET /programs/<id>`` has carried the roots at
    both the top level and under the program descriptor in different entity
    revisions, so accept either representation and only return non-empty
    strings.
    """

    sample = client.get_program(program_id)
    payload = sample.payload
    candidates: list[Any] = []
    if isinstance(payload, Mapping):
        candidates.extend((payload.get("allowed_roots"), payload.get("research_roots")))
        for key in ("program", "descriptor", "config", "research"):
            nested = payload.get(key)
            if isinstance(nested, Mapping):
                candidates.extend((nested.get("allowed_roots"), nested.get("research_roots")))
    for candidate in candidates:
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
            roots = [str(item) for item in candidate if isinstance(item, str) and item]
            if roots:
                return roots
    return []
def _program_ids(client: ProgramBenchmarkClient) -> tuple[set[str] | None, BenchmarkSample]:
    """Return the server's currently resident program ids.

    Fresh station children are deliberately selected from the live listing,
    rather than by reusing the deterministic child id from a prior course run.
    A failed listing is kept as a protocol failure; guessing an id here would
    make an apparently fresh station silently replay old state.
    """
    sample = client.list_programs()
    if not sample.ok or not isinstance(sample.payload, Mapping):
        return None, sample
    programs = sample.payload.get("programs")
    if not isinstance(programs, list):
        return None, sample
    ids: set[str] = set()
    for row in programs:
        if not isinstance(row, Mapping):
            continue
        value = row.get("program_id", row.get("id"))
        if isinstance(value, str) and value:
            ids.add(value)
    return ids, sample


def _fresh_program_id(
    client: ProgramBenchmarkClient,
    *,
    parent_id: str,
    tag: str,
    station: str,
) -> tuple[str | None, BenchmarkSample]:
    """Choose an unused child id without consuming a program request."""
    ids, sample = _program_ids(client)
    if ids is None:
        return None, sample
    stem = f"{parent_id}--{station}--{tag}"
    candidate = stem
    suffix = 2
    while candidate in ids:
        candidate = f"{stem}--{suffix}"
        suffix += 1
    return candidate, sample




def _isolated_program(
    client: ProgramBenchmarkClient,
    *,
    parent_id: str,
    tag: str,
    station: str,
) -> tuple[str, dict[str, Any] | None]:
    """Prepare a fresh program for a stateful station, or report why it cannot."""

    child_id, listing_sample = _fresh_program_id(
        client, parent_id=parent_id, tag=tag, station=station
    )
    if child_id is None:
        return "", {
            "schema": "cassi.laboratory.prepared-program.v1",
            "program_id": None,
            "accepted": False,
            "status": listing_sample.status,
            "error_kind": listing_sample.error_kind,
            "error": listing_sample.error,
            "payload": _safe(listing_sample.payload),
            "owner_state_sha256": None,
            "measurement": listing_sample.measurement(),
        }
    roots = _allowed_roots(client, parent_id)
    if not roots:
        return child_id, None
    prepared = prepare_program(
        client,
        program_id=child_id,
        tag=f"{tag}-{station}",
        allowed_roots=roots,
        mission=f"Shifting Laboratory {station} transaction station",
        question=f"Measure isolated {station} transaction behavior",
    )
    if not prepared.get("accepted") or not prepared.get("owner_state_sha256"):
        return child_id, prepared
    return child_id, prepared





def admit(
    client: ProgramBenchmarkClient,
    program_id: str,
    *,
    computation_id: str,
    request_id: str,
    revision: str,
    source: str,
    mode: str = "exec",
    name: str | None = None,
    steps: int = 64,
) -> dict[str, Any]:
    """Submit one computation and classify success/refusal without raising."""

    result, sample, _proposal_value = _admit_request(
        client,
        program_id,
        computation_id=computation_id,
        request_id=request_id,
        revision=revision,
        source=source,
        mode=mode,
        name=name,
        steps=steps,
    )
    payload = sample.payload if isinstance(sample.payload, Mapping) else {}
    return {
        "schema": "cassi.laboratory.admission.v1",
        "program_id": program_id,
        "computation_id": computation_id,
        "request_id": request_id,
        "accepted": sample.ok,
        "status": sample.status,
        "error_kind": sample.error_kind,
        "payload": result["payload"],
        "refusal_kind": _payload_kind(sample),
        "refusal_reason": _payload_error(sample),
        "idempotent_replay": payload.get("idempotent_replay") if isinstance(payload, Mapping) else None,
        "elapsed_ns": sample.elapsed_ns,
        "measurement": result["measurement"],
    }


def _capacity_reason(record: Mapping[str, Any]) -> bool:
    """Recognize both the runtime limit and the observed field-history cliff."""
    reason = str(record.get("refusal_reason") or "").lower()
    payload = record.get("payload")
    text = reason + " " + (json.dumps(payload, sort_keys=True) if payload is not None else "")
    return (
        "task limit exhausted" in text
        or ("capacity" in text and "exhaust" in text)
        or "history floor cannot be decoded safely" in text
        or "history floor" in text and "decode" in text
        # The logical runtime drops the selected task when its bounded field
        # history reaches the same 60-task cliff.  It is an observable
        # capacity boundary, not a reason to issue another admission.
        or "field program task is unknown" in text
        or "computer advance failed: program task identity conflict" in text
    )


def _admission_failure(
    ordinal: int,
    *,
    computation_id: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": "cassi.laboratory.admission.v1",
        "computation_id": computation_id,
        "request_id": None,
        "accepted": False,
        "status": None,
        "error_kind": "protocol",
        "payload": {},
        "refusal_kind": "missing-owner-revision",
        "refusal_reason": reason,
        "idempotent_replay": None,
        "elapsed_ns": 0,
        "measurement": {"attempted": True, "ordinal": ordinal},
    }


def cliff_station(
    client: ProgramBenchmarkClient,
    *,
    program_id: str,
    tag: str,
    max_concurrent: int,
    source: str,
) -> dict[str, Any]:
    """Measure the first capacity boundary and the full-table duplicate defect.

    ``max_concurrent`` is an upper bound, not an assertion that the underlying
    field can hold that many tasks.  The station stops at the first refusal:
    continuing after a history-floor or capacity error corrupts the very state
    needed by the acknowledgment and recovery stations.
    """
    if isinstance(max_concurrent, bool) or not isinstance(max_concurrent, int) or max_concurrent < 1:
        return _report(
            "capacity-cliff",
            "blocked",
            [{"name": "valid-capacity", "ok": False, "detail": "max_concurrent must be a positive integer", "numbers": {}}],
            [],
            {"attempted_comparisons": 0},
            ["The capacity axis could not be exercised."],
        )
    parent_program_id = program_id
    isolated_id, isolated = _isolated_program(
        client, parent_id=parent_program_id, tag=tag, station="cliff"
    )
    if isolated is None:
        return _report(
            "capacity-cliff",
            "blocked",
            [{
                "name": "isolated-program",
                "ok": False,
                "detail": "parent program exposed no non-empty allowed roots",
                "numbers": {"program_id": isolated_id},
            }],
            [],
            {"attempted_comparisons": 0, "isolated_program_id": isolated_id},
            ["Capacity cliff was not run against the parent program."],
        )
    if not isolated.get("accepted") or not isolated.get("owner_state_sha256"):
        return _report(
            "capacity-cliff",
            "blocked",
            [{
                "name": "isolated-program",
                "ok": False,
                "detail": "could not create a fresh capacity-cliff program",
                "numbers": {"program_id": isolated_id, "prepared": isolated},
            }],
            [],
            {"attempted_comparisons": 0, "isolated_program_id": isolated_id},
            ["Capacity cliff was not run after fresh-program preparation failed."],
        )
    program_id = isolated_id


    revision, listing = _owner_revision(client, program_id)
    before = _snapshot(listing)
    baseline_rows = _computation_rows(listing.payload)
    baseline_computations = len(baseline_rows)
    declared_slots = max(0, int(max_concurrent) - baseline_computations)
    if revision is None:
        return _report(
            "capacity-cliff",
            "blocked",
            [{"name": "owner-revision-visible", "ok": False, "detail": "the entity exposed no owner revision", "numbers": {"before": before}}],
            [],
            {"attempted_comparisons": 0, "before": before},
            ["The entity did not expose the revision needed for admission."],
        )

    attempts: list[dict[str, Any]] = []
    accepted_ids: list[str] = []
    boundary: dict[str, Any] | None = None

    def attempt(ordinal: int) -> dict[str, Any]:
        current_revision, _ = _owner_revision(client, program_id)
        computation_id = f"{tag}-n{ordinal:04d}"
        if current_revision is None:
            return _admission_failure(
                ordinal,
                computation_id=computation_id,
                reason="owner revision disappeared before admission",
            )
        return admit(
            client,
            program_id,
            computation_id=computation_id,
            request_id=f"{tag}:admit:{ordinal:04d}",
            revision=current_revision,
            source=source,
            name=f"{tag}-{ordinal:04d}.py",
            steps=1,
        )

    # Admit until the first refusal, never issuing requests against a broken
    # history floor merely to reach a declared upper bound.
    for ordinal in range(1, declared_slots + 1):
        record = attempt(ordinal)
        record["ordinal"] = ordinal
        attempts.append(record)
        if not record["accepted"]:
            boundary = record
            break
        accepted_ids.append(str(record["computation_id"]))

    duplicate_room: dict[str, Any] | None = None
    if (
        accepted_ids
        and len(accepted_ids) < declared_slots
        and boundary is not None
        and _capacity_reason(boundary)
    ):
        room_revision, _ = _owner_revision(client, program_id)
        if room_revision is not None:
            duplicate_room = admit(
                client,
                program_id,
                computation_id=accepted_ids[0],
                request_id=f"{tag}:duplicate-room",
                revision=room_revision,
                source=source + "\n# changed duplicate content",
                name=f"{tag}-duplicate-room.py",
                steps=1,
            )

    # If the upper bound was reached without a refusal, probe N+1 now.
    if boundary is None:
        ordinal = declared_slots + 1
        boundary = attempt(ordinal)
        boundary["ordinal"] = ordinal
        attempts.append(boundary)

    observed_capacity = len(accepted_ids)
    duplicate_limit: dict[str, Any] | None = None
    duplicate_before: dict[str, Any] | None = None
    duplicate_after: dict[str, Any] | None = None
    if accepted_ids and boundary is not None and _capacity_reason(boundary):
        duplicate_before = _snapshot(client.list_computations(program_id))
        limit_revision, _ = _owner_revision(client, program_id)
        if limit_revision is not None:
            duplicate_limit = admit(
                client,
                program_id,
                computation_id=accepted_ids[0],
                request_id=f"{tag}:duplicate-limit",
                revision=limit_revision,
                source=source + "\n# changed duplicate content",
                name=f"{tag}-duplicate-limit.py",
                steps=1,
            )
        duplicate_after = _snapshot(client.list_computations(program_id))

    unexpected_boundary = boundary is None or not _capacity_reason(boundary)
    prefix = attempts[:observed_capacity]
    n_minus_one_ok = observed_capacity >= 2 and len(prefix) == observed_capacity and all(
        bool(item["accepted"]) for item in prefix[:-1]
    )
    n_ok = observed_capacity >= 1 and len(prefix) == observed_capacity and bool(prefix[-1]["accepted"])
    n_plus_one_ok = bool(boundary and not boundary["accepted"] and _capacity_reason(boundary))
    unchanged = bool(
        duplicate_before
        and duplicate_after
        and duplicate_before["row_keys"] == duplicate_after["row_keys"]
        and duplicate_before["owner_state_sha256"] == duplicate_after["owner_state_sha256"]
    )
    checks: list[dict[str, Any]] = [
        {
            "name": "n-minus-one-admissions",
            "ok": n_minus_one_ok,
            "detail": "N−1 admissions succeeded before the observed boundary" if n_minus_one_ok else "N−1 admissions did not reach the observed boundary",
            "numbers": {"declared_capacity": int(max_concurrent), "observed_capacity": observed_capacity, "attempted": max(0, observed_capacity - 1), "succeeded": sum(1 for item in prefix[:-1] if item["accepted"])},
        },
        {
            "name": "n-admission",
            "ok": n_ok,
            "detail": "the observed Nth admission succeeded" if n_ok else "the observed Nth admission did not succeed",
            "numbers": {"observed_capacity": observed_capacity, "accepted": int(n_ok)},
        },
        {
            "name": "n-plus-one-refusal",
            "ok": n_plus_one_ok,
            "detail": "N+1 was refused at the observed capacity boundary" if n_plus_one_ok else "the first refusal was not a capacity boundary",
            "numbers": {"status": boundary.get("status") if boundary else None, "reason": boundary.get("refusal_reason") if boundary else None, "payload": boundary.get("payload") if boundary else None, "observed_capacity": observed_capacity},
        },
        {
            "name": "duplicate-at-limit-defect",
            "ok": bool(duplicate_limit and not duplicate_limit["accepted"] and _capacity_reason(duplicate_limit) and unchanged),
            "detail": "resident duplicate was masked as capacity exhaustion and the input state digest was unchanged" if unchanged else "duplicate-at-limit comparison did not establish the defect",
            "numbers": {"refusal_payload": duplicate_limit.get("payload") if duplicate_limit else None, "before_owner_state_sha256": duplicate_before.get("owner_state_sha256") if duplicate_before else None, "after_owner_state_sha256": duplicate_after.get("owner_state_sha256") if duplicate_after else None, "attempted_comparisons": 1 if duplicate_before and duplicate_after else 0, "input_state_unchanged": unchanged},
        },
        {
            "name": "no-silent-loss",
            "ok": unchanged,
            "detail": "refused work left all previously admitted rows intact" if unchanged else "the refusal changed the durable task listing",
            "numbers": {"attempted_comparisons": 1 if duplicate_before and duplicate_after else 0, "accepted_ids": len(accepted_ids), "rows_before": len(duplicate_before["rows"]) if duplicate_before else None, "rows_after": len(duplicate_after["rows"]) if duplicate_after else None},
        },
        {
            "name": "first-refusal-classified",
            "ok": not unexpected_boundary,
            "detail": "the station stopped at and classified the first refusal" if not unexpected_boundary else "the first refusal was unexpected and no further admissions were attempted",
            "numbers": {"attempted_comparisons": 1 if boundary else 0, "unexpected": unexpected_boundary},
        },
    ]
    controls = [{
        "name": "duplicate-with-room-is-identity-conflict",
        "ok": bool(duplicate_room and not duplicate_room["accepted"] and "identity conflict" in str(duplicate_room.get("refusal_reason", "")).lower()),
        "detail": "control failed with identity conflict while capacity remained" if duplicate_room else "control could not be exercised",
    }]
    all_ok = all(bool(item["ok"]) for item in checks) and all(bool(item["ok"]) for item in controls)
    return _report(
        "capacity-cliff",
        "pass" if all_ok else ("blocked" if not attempts else "fail"),
        checks,
        controls,
        {
            "isolated_program_id": program_id,
            "declared_capacity": int(max_concurrent),
            "baseline_computations": baseline_computations,
            "declared_slots": declared_slots,
            "observed_capacity": observed_capacity,
            "attempts": attempts,
            "boundary": boundary,
            "extra": boundary,
            "duplicate_with_room": duplicate_room,
            "duplicate_at_limit": duplicate_limit,
            "accepted_count": len(accepted_ids),
            "attempted_comparisons": sum(1 for item in (duplicate_room, duplicate_limit) if item is not None),
            "acceptance_latency_ns": [int(item["elapsed_ns"]) for item in attempts if item["accepted"]],
            "refusal_latency_ns": [int(item["elapsed_ns"]) for item in attempts if not item["accepted"]],
        },
        [
            "The station stops at the first refusal to avoid corrupting a history-floor boundary.",
            "A capacity refusal is classified from status/error_kind/payload; no expected HTTP failure is passed to require_ok().",
        ],
    )


def _accepted_settlement(view_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    view = _view_state(view_payload)
    effects = view.get("effects")
    return {
        "status": view.get("status"),
        "unfinished_reason": view.get("unfinished_reason"),
        "version": view.get("version"),
        "costs": _safe(view.get("costs")),
        "effects": _safe(effects),
        "state_sha256": view_payload.get("view", {}).get("state_sha256") if isinstance(view_payload, Mapping) else None,
    }


def acknowledgment_station(
    client: ProgramBenchmarkClient,
    *,
    program_id: str,
    tag: str,
) -> dict[str, Any]:
    """Exercise replay, content binding, stale revisions, cancellation, and verdicts."""

    isolated_id, isolated = _isolated_program(client, parent_id=program_id, tag=tag, station="ack")
    if isolated is None or not isolated.get("accepted"):
        return _report(
            "acknowledgment",
            "blocked",
            [{"name": "isolated-program", "ok": False, "detail": "could not create a fresh acknowledgment program", "numbers": {"program_id": isolated_id, "prepared": isolated}}],
            [],
            {"attempted_comparisons": 0, "isolated_program_id": isolated_id},
            ["Acknowledgment is isolated from capacity state, but the child program could not be prepared."],
        )
    program_id = isolated_id
    revision, listing = _owner_revision(client, program_id)
    if revision is None:
        return _report("acknowledgment", "blocked", [{"name": "owner-revision-visible", "ok": False, "detail": "no owner revision was visible", "numbers": {}}], [], {"attempted_comparisons": 0, "isolated_program_id": program_id}, ["The station could not prepare an owner-bound request."])

    source = "value = 7\n"
    computation_id = f"{tag}-replay"
    request_id = f"{tag}:replay"
    proposal = _proposal(source, name=f"{tag}-replay.py", steps=64)
    first_sample = client.admit_computation(program_id, request_id=request_id, computation_id=computation_id, expected_owner_state_sha256=revision, proposal=proposal, observed_at=_FIXED_TIME)
    replay_sample = client.admit_computation(program_id, request_id=request_id, computation_id=computation_id, expected_owner_state_sha256=revision, proposal=proposal, observed_at=_FIXED_TIME)
    first_payload = _safe(first_sample.payload)
    replay_payload = _safe(replay_sample.payload)
    first_normalized = dict(first_payload) if isinstance(first_payload, Mapping) else first_payload
    replay_normalized = dict(replay_payload) if isinstance(replay_payload, Mapping) else replay_payload
    if isinstance(first_normalized, dict):
        first_normalized.pop("idempotent_replay", None)
    if isinstance(replay_normalized, dict):
        replay_normalized.pop("idempotent_replay", None)
    replay_equal = first_normalized == replay_normalized and bool(replay_sample.ok)
    replay_view, _ = _view(client, program_id, computation_id)

    changed_sample = client.admit_computation(program_id, request_id=request_id, computation_id=computation_id, expected_owner_state_sha256=revision, proposal=_proposal(source + "#different", name=f"{tag}-changed.py"), observed_at=_FIXED_TIME)

    stale_id = f"{tag}-stale"
    stale_revision = "0" * 64 if revision != "0" * 64 else "f" * 64
    stale_sample = client.admit_computation(program_id, request_id=f"{tag}:stale:one", computation_id=stale_id, expected_owner_state_sha256=stale_revision, proposal=_proposal(source, name=f"{tag}-stale.py"), observed_at=_FIXED_TIME)
    stale_repeat = client.admit_computation(program_id, request_id=f"{tag}:stale:two", computation_id=stale_id, expected_owner_state_sha256=stale_revision, proposal=_proposal(source, name=f"{tag}-stale.py"), observed_at=_FIXED_TIME)
    after_stale_sample = client.list_computations(program_id)
    stale_absent = all(str(row.get("computation_id", "")) != stale_id for row in _computation_rows(after_stale_sample.payload))

    pending_id = f"{tag}-pending"
    pending_revision = owner_state_sha256(after_stale_sample.payload) or revision
    pending_result, pending_sample, _pending_proposal = _admit_request(client, program_id, computation_id=pending_id, request_id=f"{tag}:pending", revision=pending_revision, source="value = request_effect({'probe': 'pending'})\n", capabilities=("effect-proposal",), steps=64, name=f"{tag}-pending.py")
    pending_view, pending_view_sample = _view(client, program_id, pending_id)
    pending_state = _view_state(pending_view)
    effects = pending_state.get("effects") if isinstance(pending_state.get("effects"), list) else []
    operation = effects[0] if effects and isinstance(effects[0], Mapping) else {}
    operation_id = operation.get("operation_id")
    control_revision = owner_state_sha256(client.list_computations(program_id).payload) or pending_revision
    cancel_sample = client.control_computation(program_id, pending_id, request_id=f"{tag}:cancel", expected_owner_state_sha256=control_revision, action="cancel", arguments={"reason": "acknowledgment-station"}, observed_at=_FIXED_TIME)
    cancel_replay = client.control_computation(program_id, pending_id, request_id=f"{tag}:cancel", expected_owner_state_sha256=control_revision, action="cancel", arguments={"reason": "acknowledgment-station"}, observed_at=_FIXED_TIME)
    cancelled_view, _ = _view(client, program_id, pending_id)
    cancelled_settlement = _accepted_settlement(cancelled_view)
    late_sample = client.control_computation(program_id, pending_id, request_id=f"{tag}:late-verdict", expected_owner_state_sha256=owner_state_sha256(client.list_computations(program_id).payload) or control_revision, action="resume-external", arguments={"operation_id": operation_id or "missing-operation", "value": {"late": True}}, observed_at=_FIXED_TIME)

    checks = [
        {"name": "duplicate-request-replay", "ok": replay_equal and bool(first_sample.ok), "detail": "the duplicate request replayed the same result without re-applying work" if replay_equal else "duplicate replay differed or was refused", "numbers": {"first": first_sample.measurement(), "replay": replay_sample.measurement(), "payload_equal_ignoring_replay_flag": replay_equal}},
        {"name": "changed-content-refusal", "ok": bool(changed_sample.http_error and "different content" in str(_payload_error(changed_sample)).lower()), "detail": "same request id with different content was refused" if changed_sample.http_error else "changed content was not refused", "numbers": {"status": changed_sample.status, "payload": _safe(changed_sample.payload)}},
        {"name": "stale-revision-refusal-visible", "ok": bool(stale_sample.http_error and stale_repeat.http_error and stale_absent), "detail": "stale revision remained a visible refusal and did not create partial work" if stale_absent else "stale refusal was not durably visible", "numbers": {"first": _sample(stale_sample), "repeat": _sample(stale_repeat), "target_absent": stale_absent, "post_refusal_owner_state_sha256": owner_state_sha256(after_stale_sample.payload)}},
        {"name": "cancel-acceptance-then-settlement", "ok": bool(cancel_sample.ok and cancelled_settlement.get("status") == "cancelled"), "detail": "cancel was accepted and the pending computation settled as cancelled" if cancel_sample.ok else "cancel was not accepted", "numbers": {"acceptance": cancel_sample.measurement(), "settlement": cancelled_settlement}},
        {"name": "late-verdict-not-counted", "ok": bool(not late_sample.ok), "detail": "a verdict arriving after cancellation was refused" if not late_sample.ok else "a late verdict unexpectedly changed cancelled work", "numbers": {"status": late_sample.status, "payload": _safe(late_sample.payload), "attempted_comparisons": 1}},
    ]
    controls = [
        {"name": "duplicate-cancel-replay", "ok": bool(cancel_replay.ok and cancelled_settlement.get("status") == "cancelled"), "detail": "duplicate cancel replayed acceptance without a second settlement"},
    ]
    all_ok = all(bool(item["ok"]) for item in checks) and all(bool(item["ok"]) for item in controls)
    return _report(
        "acknowledgment",
        "pass" if all_ok else "fail",
        checks,
        controls,
        {
            "acceptance_vs_settlement": {
                "replay": {"acceptance": first_sample.measurement(), "settlement": _accepted_settlement(replay_view)},
                "changed_content": {"acceptance": changed_sample.measurement(), "settlement": "not admitted"},
                "stale_revision": {"acceptance": stale_sample.measurement(), "settlement": "not admitted"},
                "cancel": {"acceptance": cancel_sample.measurement(), "settlement": cancelled_settlement},
                "late_verdict": {"acceptance": late_sample.measurement(), "settlement": cancelled_settlement},
            },
            "pending_admission": pending_result,
            "pending_inspection": _safe(pending_view),
            "pending_inspection_measurement": pending_view_sample.measurement(),
            "cancel_replay": cancel_replay.measurement(),
            "isolated_program_id": program_id,
            "acceptance_latency_ns": [first_sample.elapsed_ns, replay_sample.elapsed_ns, changed_sample.elapsed_ns, stale_sample.elapsed_ns, cancel_sample.elapsed_ns],
            "settlement_latency_ns": [pending_view_sample.elapsed_ns],
        },
        [
            "Acceptance and settlement are recorded separately; a 2xx admission is not treated as a settled computation.",
            "The operation journal binds request ids to complete content, including the expected owner revision.",
        ],
    )


def recovery_station(
    client: ProgramBenchmarkClient,
    *,
    program_id: str,
    tag: str,
    restart: Callable[[], None],
) -> dict[str, Any]:
    """Verify durable completion, blocked external work, replay, and continuation."""

    if not callable(restart):
        return _report("recovery", "blocked", [{"name": "restart-hook", "ok": False, "detail": "caller supplied no callable restart hook", "numbers": {}}], [], {"attempted_comparisons": 0}, ["Recovery cannot be exercised without the course-owned restart hook."])
    isolated_id, isolated = _isolated_program(client, parent_id=program_id, tag=tag, station="recovery")
    if isolated is None or not isolated.get("accepted"):
        return _report(
            "recovery",
            "blocked",
            [{"name": "isolated-program", "ok": False, "detail": "could not create a fresh recovery program", "numbers": {"program_id": isolated_id, "prepared": isolated}}],
            [],
            {"attempted_comparisons": 0, "isolated_program_id": isolated_id},
            ["Recovery is isolated from capacity state, but the child program could not be prepared."],
        )
    program_id = isolated_id
    revision, listing = _owner_revision(client, program_id)
    if revision is None:
        return _report("recovery", "blocked", [{"name": "owner-revision-visible", "ok": False, "detail": "no owner revision was visible", "numbers": {}}], [], {"attempted_comparisons": 0, "isolated_program_id": program_id}, ["Recovery could not bind its admissions to an owner revision."])

    keep_id = f"{tag}-durable"
    keep_result, keep_sample, _keep_proposal = _admit_request(client, program_id, computation_id=keep_id, request_id=f"{tag}:durable", revision=revision, source="value = 2\n", steps=64, name=f"{tag}-durable.py")
    keep_view_before, keep_view_sample = _view(client, program_id, keep_id)
    current_revision = owner_state_sha256(client.list_computations(program_id).payload) or revision
    run_sample = client.control_computation(program_id, keep_id, request_id=f"{tag}:durable:run", expected_owner_state_sha256=current_revision, action="run", arguments={"quantum": 64, "max_groups": 1024}, observed_at=_FIXED_TIME)
    keep_view_before_run, keep_before_run_sample = _view(client, program_id, keep_id)

    await_id = f"{tag}-unknown-effect"
    await_revision = owner_state_sha256(client.list_computations(program_id).payload) or current_revision
    await_result, await_sample, _await_proposal = _admit_request(client, program_id, computation_id=await_id, request_id=f"{tag}:unknown-effect", revision=await_revision, source="value = request_effect({'restart': 'ack'})\n", capabilities=("effect-proposal",), steps=64, name=f"{tag}-unknown-effect.py")
    await_view_before, await_view_sample = _view(client, program_id, await_id)
    await_state_before = _view_state(await_view_before)
    await_effects_before = await_state_before.get("effects") if isinstance(await_state_before.get("effects"), list) else []
    await_operation = await_effects_before[0] if await_effects_before and isinstance(await_effects_before[0], Mapping) else {}
    operation_id = str(await_operation.get("operation_id", ""))

    replay_id = f"{tag}-lost-ack"
    replay_revision = owner_state_sha256(client.list_computations(program_id).payload) or await_revision
    replay_result, replay_sample, replay_proposal = _admit_request(client, program_id, computation_id=replay_id, request_id=f"{tag}:lost-ack", revision=replay_revision, source="value = 11\n", steps=64, name=f"{tag}-lost-ack.py")
    before_restart = _snapshot(client.list_computations(program_id))

    restart()

    durable_after, durable_after_sample = _view(client, program_id, keep_id)
    await_after, await_after_sample = _view(client, program_id, await_id)
    replay_after, replay_after_sample = _view(client, program_id, replay_id)
    after_restart = _snapshot(client.list_computations(program_id))
    replay_revision_after = owner_state_sha256(client.list_computations(program_id).payload) or replay_revision
    replay_sample_after = client.admit_computation(program_id, request_id=f"{tag}:lost-ack", computation_id=replay_id, expected_owner_state_sha256=replay_revision, proposal=replay_proposal, observed_at=_FIXED_TIME)
    replay_changed = client.admit_computation(program_id, request_id=f"{tag}:lost-ack", computation_id=replay_id, expected_owner_state_sha256=replay_revision, proposal=_proposal("value = 12\n", name=f"{tag}-changed.py"), observed_at=_FIXED_TIME)

    await_after_state = _view_state(await_after)
    await_after_effects = await_after_state.get("effects") if isinstance(await_after_state.get("effects"), list) else []
    await_after_operation = await_after_effects[0] if await_after_effects and isinstance(await_after_effects[0], Mapping) else {}
    blocked = await_after_state.get("status") == "waiting" and await_after_state.get("unfinished_reason") == "awaiting-external-result" and await_after_operation.get("phase") == "proposed"
    no_rerun = blocked and int(await_after_state.get("version", -1)) == int(await_state_before.get("version", -2)) and not await_after_operation.get("settlement_sha256")

    resume_revision = owner_state_sha256(client.list_computations(program_id).payload) or replay_revision_after
    resume_sample = client.control_computation(program_id, await_id, request_id=f"{tag}:resume-external", expected_owner_state_sha256=resume_revision, action="resume-external", arguments={"operation_id": operation_id, "value": {"ack": "recovered"}}, observed_at=_FIXED_TIME)
    resume_run = client.control_computation(program_id, await_id, request_id=f"{tag}:resume-run", expected_owner_state_sha256=owner_state_sha256(client.list_computations(program_id).payload) or resume_revision, action="run", arguments={"quantum": 64, "max_groups": 1024}, observed_at=_FIXED_TIME)
    final_view, final_view_sample = _view(client, program_id, await_id)
    final_state = _view_state(final_view)

    durable_before_state = _view_state(keep_view_before_run)
    durable_after_state = _view_state(durable_after)
    durable_survived = bool(durable_before_state and durable_after_state and durable_before_state.get("status") == durable_after_state.get("status") and durable_before_state.get("result") == durable_after_state.get("result"))
    replay_identical = bool(replay_sample_after.ok and isinstance(replay_sample_after.payload, Mapping) and replay_sample_after.payload.get("idempotent_replay") is True)
    checks = [
        {"name": "durable-work-survives", "ok": durable_survived, "detail": "completed work and its result survived restart" if durable_survived else "completed work did not survive restart unchanged", "numbers": {"before": _accepted_settlement(keep_view_before_run), "after": _accepted_settlement(durable_after), "before_sample": keep_before_run_sample.measurement(), "after_sample": durable_after_sample.measurement()}},
        {"name": "lost-ack-recovery-replay", "ok": replay_identical, "detail": "the exact pre-restart admission replayed from the durable journal without re-running", "numbers": {"replay": replay_sample_after.measurement(), "idempotent_replay": replay_sample_after.payload.get("idempotent_replay") if isinstance(replay_sample_after.payload, Mapping) else None, "rows_before": len(before_restart["rows"]), "rows_after": len(after_restart["rows"])}},
        {"name": "unknown-effect-blocks", "ok": no_rerun, "detail": "the unresolved external operation remained proposed and blocked after restart", "numbers": {"status": await_after_state.get("status"), "unfinished_reason": await_after_state.get("unfinished_reason"), "operation_phase": await_after_operation.get("phase"), "version_before": await_state_before.get("version"), "version_after": await_after_state.get("version"), "attempted_comparisons": 1}},
        {"name": "program-continues", "ok": bool(resume_sample.ok and resume_run.ok and final_state.get("status") == "completed"), "detail": "explicit settlement resumed the durable computation and it completed" if final_state.get("status") == "completed" else "the durable computation did not continue to completion", "numbers": {"resume_acceptance": resume_sample.measurement(), "run_acceptance": resume_run.measurement(), "final": _accepted_settlement(final_view)}},
    ]
    controls = [
        {"name": "content-bound-replay-control", "ok": bool(replay_changed.http_error), "detail": "changing the body under the old request id was refused after restart"},
    ]
    all_ok = all(bool(item["ok"]) for item in checks) and all(bool(item["ok"]) for item in controls)
    return _report(
        "recovery",
        "pass" if all_ok else "fail",
        checks,
        controls,
        {
            "before_restart": before_restart,
            "isolated_program_id": program_id,
            "durable_computation": keep_id,
            "blocked_computation": await_id,
            "blocked_operation_id": operation_id,
            "unknown_effect_surface": "waiting/proposed/awaiting-external-result",
            "replay_computation": replay_id,
            "acceptance_latency_ns": [keep_sample.elapsed_ns, run_sample.elapsed_ns, await_sample.elapsed_ns, replay_sample.elapsed_ns, replay_sample_after.elapsed_ns, resume_sample.elapsed_ns, resume_run.elapsed_ns],
            "settlement_latency_ns": [keep_before_run_sample.elapsed_ns, durable_after_sample.elapsed_ns, await_after_sample.elapsed_ns, final_view_sample.elapsed_ns],
            "attempted_comparisons": 4,
        },
        [
            "A program-computation operation with no external acknowledgment is represented by the entity as proposed/waiting and awaiting-external-result; it is not automatically re-run.",
            "The exact request replay is journal-backed; a changed body under the same request id remains refused after restart.",
        ],
    )


def _context_value(context: Any, name: str, default: Any = None) -> Any:
    if isinstance(context, Mapping):
        return context.get(name, default)
    return getattr(context, name, default)


def _evidence_check(evidence: Mapping[str, Any], schema: str) -> dict[str, Any]:
    claim = evidence.get("claim") if isinstance(evidence, Mapping) else None
    return {
        "name": "entity-evidence-claim",
        "ok": isinstance(claim, Mapping),
        "detail": "the entity supplied a structured forecast for the measured station" if isinstance(claim, Mapping) else "evidence must contain a claim object",
        "numbers": {"schema": evidence.get("schema") if isinstance(evidence, Mapping) else None, "expected_schema": schema},
    }


def entity_stations(
    *,
    client: ProgramBenchmarkClient,
    program_id: str | None = None,
    home: str | None = None,
    workspace: str | None = None,
    fixture: Any = None,
    restart: Callable[[], None] | None = None,
) -> tuple[Station, ...]:
    """Return the three entity stations used by :class:`laboratory.course.Course`.

    The optional ``restart`` keyword is intentionally accepted in addition to
    the frozen integration signature.  If omitted, a judge also looks for
    ``context.restart``; without either hook the recovery station is honestly
    blocked rather than reported as a pass.
    """

    del fixture
    declared_program = program_id

    def bound_cliff(context: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
        pid = declared_program or _context_value(context, "program_id")
        if not isinstance(pid, str) or not pid:
            return _report("capacity-cliff", "blocked", [{"name": "program-id", "ok": False, "detail": "no program id supplied", "numbers": {}}], [], {"attempted_comparisons": 0}, [])
        report = cliff_station(client=_context_value(context, "client", client), program_id=pid, tag="entity-cliff", max_concurrent=DEFAULT_TASK_CAPACITY, source="value = 1\n")
        report["checks"].append(_evidence_check(evidence, CLIFF_SCHEMA))
        if report["verdict"] == "pass" and not report["checks"][-1]["ok"]:
            report["verdict"] = "fail"
        return report

    def bound_ack(context: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
        pid = declared_program or _context_value(context, "program_id")
        if not isinstance(pid, str) or not pid:
            return _report("acknowledgment", "blocked", [{"name": "program-id", "ok": False, "detail": "no program id supplied", "numbers": {}}], [], {"attempted_comparisons": 0}, [])
        report = acknowledgment_station(client=_context_value(context, "client", client), program_id=pid, tag="entity-ack")
        report["checks"].append(_evidence_check(evidence, ACK_SCHEMA))
        if report["verdict"] == "pass" and not report["checks"][-1]["ok"]:
            report["verdict"] = "fail"
        return report

    def bound_recovery(context: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
        pid = declared_program or _context_value(context, "program_id")
        hook = restart or _context_value(context, "restart")
        if not isinstance(pid, str) or not pid:
            return _report("recovery", "blocked", [{"name": "program-id", "ok": False, "detail": "no program id supplied", "numbers": {}}], [], {"attempted_comparisons": 0}, [])
        if not callable(hook):
            return _report("recovery", "blocked", [{"name": "restart-hook", "ok": False, "detail": "course supplied no restart hook", "numbers": {}}], [], {"attempted_comparisons": 0}, ["Recovery requires the course-owned stop/restart hook."])
        report = recovery_station(client=_context_value(context, "client", client), program_id=pid, tag="entity-recovery", restart=hook)
        report["checks"].append(_evidence_check(evidence, RECOVERY_SCHEMA))
        if report["verdict"] == "pass" and not report["checks"][-1]["ok"]:
            report["verdict"] = "fail"
        return report

    return (
        Station("capacity-cliff", "The task-table capacity cliff", CLIFF_SCHEMA, {"schema": CLIFF_SCHEMA, "question": "Forecast N−1, N, and N+1 admissions and the duplicate-id refusal at a full task table.", "program_id": declared_program, "home": home, "workspace": workspace}, bound_cliff, kind="entity"),
        Station("acknowledgment", "Acceptance is not settlement", ACK_SCHEMA, {"schema": ACK_SCHEMA, "question": "Forecast exact replay, content binding, stale revision refusal, cancellation settlement, and late verdict behavior.", "program_id": declared_program, "home": home, "workspace": workspace}, bound_ack, kind="entity"),
        Station("recovery", "Durability across restart", RECOVERY_SCHEMA, {"schema": RECOVERY_SCHEMA, "question": "Forecast what survives restart and how an unacknowledged external operation blocks without re-running.", "program_id": declared_program, "home": home, "workspace": workspace}, bound_recovery, kind="entity"),
    )


__all__ = [
    "ACK_SCHEMA",
    "CLIFF_SCHEMA",
    "DEFAULT_TASK_CAPACITY",
    "RECOVERY_SCHEMA",
    "STATION_REPORT_SCHEMA",
    "acknowledgment_station",
    "admit",
    "cliff_station",
    "entity_stations",
    "prepare_program",
    "recovery_station",
]
