#!/usr/bin/env python3
"""Field-owned architecture redesign campaign for CassiMindField v13-v18.

The campaign keeps candidate IRs in the semantic field agenda (CassiFieldWorkMemory)
and treats JSON as immutable evidence only.  ArchitectureSynthesizer produces each
candidate in a disposable directory; observatory indexing and bounded holdouts then
supply measured prediction/assessment rows to the field-semantic agenda.  JSON is
receipt evidence only; autonomous-agenda in CassiFieldWorkMemory determines promotion.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
for _path in (ROOT, WORKSPACE_ROOT / "CassiQwen", WORKSPACE_ROOT / "CassiFI"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from architecture_ir import ArchitectureIR, build_example, digest as ir_digest  # noqa: E402
from architecture_synthesizer import CandidateWorkspace, synthesize_workspace, workspace_digest  # noqa: E402
from cassi_field_qwen_workbench import CassiFieldWorkMemory, WorkMemoryRecord  # noqa: E402
from cassi_field_computer import ComputerProfile, FieldComputer  # noqa: E402
from cassi_field_program import SCHEMA as FIELD_PROGRAM_SCHEMA, compile_structured_program  # noqa: E402
from cassi_constraint_field import (  # noqa: E402
    CircuitSpec,
    ConstraintField,
    ConstraintFieldProfile,
    TransitionProblem,
    compile_circuit,
    compile_transition_problem,
)
from cassi_computation_policy import (  # noqa: E402
    METHODS as COMPUTATION_METHODS,
    audit_result as audit_constraint_result,
    compile_source as compile_constraint_source,
    initial_policy,
    select_method,
    solve_and_learn,
)
from self_observatory import canonical, digest, index_workspace, run_bounded_command, source_references  # noqa: E402

SCHEMA = "cassimindfield.redesign-lab.v1"
RECEIPT_SCHEMA = "cassimindfield.redesign-receipt.v1"
POINTER_SCHEMA = "cassimindfield.redesign-pointer.v1"
MAX_CANDIDATES = 4
INVESTIGATION_PROCEDURE_ID = "redesign-procedure:topology-construction"
CROSS_WORLD_SCHEMA = "cassimindfield.cross-world-transfer.v1"
CONSTRAINT_WORLD_SCHEMA = "cassimindfield.constraint-world-transfer.v1"
REASONING_WORLD_SCHEMA = "cassimindfield.paired-reasoning-transfer.v1"


class RedesignError(RuntimeError):
    pass


class MutationRejected(RedesignError):
    pass


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_bytes(path, canonical(value) + b"\n")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MutationRejected(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise MutationRejected(f"artifact is not an object: {path}")
    return value


def _check(value: Mapping[str, Any], field: str, body: Mapping[str, Any]) -> None:
    if value.get(field) != digest(body):
        raise MutationRejected(f"{field} mismatch")


def _stable_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key not in {"content_sha256", "wall_ns"}}


def _stable_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"content_sha256", "timing"}}

RESPONSIBILITY_SNAPSHOT_SCHEMA = "cassi.responsibility-snapshot.v1"
RESPONSIBILITY_CONTINUITY_SCHEMA = "cassimindfield.responsibility-continuity.v1"
RESPONSIBILITY_RECORD_PREFIX = "entity:research-responsibility:"
RESPONSIBILITY_CHARTER_ID = f"{RESPONSIBILITY_RECORD_PREFIX}charter"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _load_responsibility_snapshot(
    value: Mapping[str, Any] | str | os.PathLike[str] | None,
) -> dict[str, Any] | None:
    """Validate a read-only entity export before it can enter redesign evidence."""
    if value is None:
        return None
    if isinstance(value, (str, os.PathLike)):
        raw = _read(Path(value))
    elif isinstance(value, Mapping):
        try:
            raw = json.loads(canonical(value).decode("utf-8"))
        except (TypeError, ValueError, UnicodeError) as exc:
            raise MutationRejected("responsibility snapshot is not strict JSON") from exc
    else:
        raise MutationRejected("responsibility snapshot must be an object or JSON path")
    required = {"schema", "field_state_sha256", "records", "records_sha256"}
    if set(raw) != required:
        raise MutationRejected("responsibility snapshot keys do not match its schema")
    if raw.get("schema") != RESPONSIBILITY_SNAPSHOT_SCHEMA:
        raise MutationRejected("unsupported responsibility snapshot schema")
    field_state_sha256 = raw.get("field_state_sha256")
    if not isinstance(field_state_sha256, str) or not _SHA256.fullmatch(field_state_sha256):
        raise MutationRejected("responsibility snapshot field-state digest is invalid")
    records = raw.get("records")
    if not isinstance(records, list) or not records or len(records) > 4096:
        raise MutationRejected("responsibility snapshot must carry bounded non-empty records")
    records_sha256 = raw.get("records_sha256")
    if not isinstance(records_sha256, str) or not _SHA256.fullmatch(records_sha256):
        raise MutationRejected("responsibility snapshot record digest is invalid")
    if digest(records) != records_sha256:
        raise MutationRejected("responsibility snapshot records digest mismatch")

    record_ids: list[str] = []
    charter_count = 0
    for row in records:
        if not isinstance(row, Mapping) or set(row) != {"reference", "record"}:
            raise MutationRejected("responsibility snapshot record row is invalid")
        reference = row.get("reference")
        record = row.get("record")
        if not isinstance(reference, Mapping) or set(reference) != {"id", "kind", "content_version"}:
            raise MutationRejected("responsibility snapshot reference is invalid")
        if not isinstance(record, Mapping):
            raise MutationRejected("responsibility snapshot field record is invalid")
        record_id = reference.get("id")
        version = reference.get("content_version")
        if (
            not isinstance(record_id, str)
            or len(record_id) > 256
            or not record_id.startswith(RESPONSIBILITY_RECORD_PREFIX)
            or reference.get("kind") != "Obligation"
            or isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise MutationRejected("responsibility snapshot reference is not a current obligation")
        if (
            record.get("id") != record_id
            or record.get("kind") != "Obligation"
            or record.get("status") != "active"
        ):
            raise MutationRejected(f"responsibility record is not active or was relabelled: {record_id}")
        payload = record.get("payload")
        responsibility = payload.get("responsibility") if isinstance(payload, Mapping) else None
        if (
            not isinstance(payload, Mapping)
            or payload.get("purpose") != "human-development"
            or not isinstance(payload.get("state"), str)
            or payload.get("state") not in {"pending", "resolved"}
            or not isinstance(responsibility, Mapping)
            or responsibility.get("schema") != "cassi.responsibility.v1"
        ):
            raise MutationRejected(f"responsibility record payload is invalid: {record_id}")
        affected = responsibility.get("affected")
        burdens = responsibility.get("possible_burdens")
        if (
            not isinstance(affected, list)
            or not affected
            or any(not isinstance(item, str) or not item.strip() for item in affected)
            or not isinstance(burdens, list)
            or any(not isinstance(item, str) or not item.strip() for item in burdens)
            or not isinstance(responsibility.get("intended_benefit"), str)
            or not responsibility["intended_benefit"].strip()
            or not isinstance(responsibility.get("decision_owner"), str)
            or not responsibility["decision_owner"].strip()
            or not isinstance(responsibility.get("review_question"), str)
            or not responsibility["review_question"].strip()
        ):
            raise MutationRejected(f"responsibility declaration is incomplete: {record_id}")
        priority = payload.get("priority")
        if (
            isinstance(priority, bool)
            or not isinstance(priority, (int, float))
            or not (float("-inf") < float(priority) < float("inf"))
        ):
            raise MutationRejected(f"responsibility priority is not finite: {record_id}")
        if record_id == RESPONSIBILITY_CHARTER_ID:
            charter_count += 1
        record_ids.append(record_id)
    if charter_count != 1:
        raise MutationRejected("responsibility snapshot must contain its standing charter")
    if record_ids != sorted(record_ids) or len(set(record_ids)) != len(record_ids):
        raise MutationRejected("responsibility snapshot records are not uniquely sorted by id")
    return raw


FIELD_OWNER_LINK_SCHEMA = "cassimindfield.field-owner-link.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _owner_link_payload(link: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in link.items() if key != "link_sha256"}


def _save_owner_link(path: Path, link: dict[str, Any]) -> None:
    payload = _owner_link_payload(link)
    link.clear()
    link.update(payload)
    link["link_sha256"] = digest(payload)
    _atomic_json(path, link)


def _read_owner_link(path: Path, campaign_id: str) -> dict[str, Any]:
    link = _read(path)
    expected = {
        "schema",
        "campaign_id",
        "program_id",
        "program_request",
        "pending_reports",
        "inflight_attempt",
        "link_sha256",
    }
    if set(link) != expected or link.get("schema") != FIELD_OWNER_LINK_SCHEMA:
        raise MutationRejected("field-owner link manifest has an invalid schema")
    payload = _owner_link_payload(link)
    if (
        link.get("campaign_id") != campaign_id
        or link.get("link_sha256") != digest(payload)
        or not isinstance(link.get("program_request"), Mapping)
        or not isinstance(link.get("pending_reports"), list)
    ):
        raise MutationRejected("field-owner link manifest failed integrity checks")
    return link


class _FieldOwnerClient:
    """Loopback-only bridge to the entity that owns rewrite responsibilities."""

    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise RedesignError(
                "field owner must be the loopback HTTP entity"
            )

    def _request(self, method: str, route: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        encoded = None if body is None else canonical(body)
        headers = {
            "Accept": "application/json",
        }
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + route,
            data=encoded,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise RedesignError("field-owner response exceeds the size limit")
        except urllib.error.HTTPError as exc:
            raise RedesignError(
                f"field-owner request {method} {route} returned HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RedesignError(
                f"field-owner request {method} {route} could not be completed"
            ) from exc
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RedesignError("field-owner returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise RedesignError("field-owner response must be a JSON object")
        return value

    def responsibility_snapshot(self) -> dict[str, Any]:
        return _load_responsibility_snapshot(
            self._request("GET", "/v1/responsibilities/snapshot")
        ) or {}

    def bind_campaign(self, home: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        home.mkdir(parents=True, exist_ok=True)
        campaign_id = digest({"data_home": str(home.resolve())})[:24]
        link_path = home / "field-owner-link.json"
        if link_path.is_file():
            link = _read_owner_link(link_path, campaign_id)
        else:
            initial = self.responsibility_snapshot()
            charter = next(
                (
                    row["record"]["payload"]["responsibility"]
                    for row in initial["records"]
                    if row["reference"]["id"] == RESPONSIBILITY_CHARTER_ID
                ),
                None,
            )
            if not isinstance(charter, Mapping):
                raise MutationRejected("field owner omitted its standing human-development charter")
            affected = charter.get("affected")
            burdens = charter.get("possible_burdens")
            if (
                not isinstance(affected, list)
                or not affected
                or not isinstance(burdens, list)
            ):
                raise MutationRejected("field-owner charter does not define review groups and burdens")
            responsibility = {
                "schema": charter["schema"],
                "affected": list(affected),
                "intended_benefit": (
                    "Improve field-selected, independently verified CassiMindField "
                    "successors in support of human-chosen purposes; software "
                    "success alone is not evidence of human benefit."
                ),
                "possible_burdens": [
                    *burdens,
                    "A successor may shift agency, access, or shared-power outcomes "
                    "without producing its intended benefit.",
                ],
                "decision_owner": charter["decision_owner"],
                "review_question": (
                    "For each affected group, what changed in practice, did the "
                    "successor support that group's chosen purposes, could people "
                    "refuse or correct the record, and what evidence remains missing?"
                ),
            }
            program_id = f"mindfield-redesign-{campaign_id}"
            request = {
                "request_id": f"mindfield-redesign-create-{campaign_id}",
                "program_id": program_id,
                "project_id": "cassimindfield",
                "title": "CassiMindField successor impact review",
                "mission": (
                    "Maintain the field-owned responsibility for every CassiMindField "
                    "redesign attempt and gather affected-group assessments before "
                    "continuing to another successor."
                ),
                "initial_question": responsibility["review_question"],
                "observed_at": _utc_now(),
                "priority": 1.0,
                "responsibility": responsibility,
            }
            link = {
                "schema": FIELD_OWNER_LINK_SCHEMA,
                "campaign_id": campaign_id,
                "program_id": program_id,
                "program_request": request,
                "pending_reports": [],
                "inflight_attempt": None,
            }
            _save_owner_link(link_path, link)
        self._request("POST", "/v1/programs", link["program_request"])
        snapshot = self.responsibility_snapshot()
        self._assert_program_bound(snapshot, link)
        return link, snapshot

    @staticmethod
    def _assert_program_bound(snapshot: Mapping[str, Any], link: Mapping[str, Any]) -> None:
        program_id = link["program_id"]
        row = next(
            (
                item
                for item in snapshot["records"]
                if item["reference"]["id"]
                == f"{RESPONSIBILITY_RECORD_PREFIX}{program_id}"
            ),
            None,
        )
        if not isinstance(row, Mapping):
            raise MutationRejected("rewrite program duty was not admitted by the field owner")
        payload = row["record"].get("payload")
        declaration = payload.get("responsibility") if isinstance(payload, Mapping) else None
        expected = link["program_request"]["responsibility"]
        if not isinstance(declaration, Mapping) or any(
            declaration.get(key) != value for key, value in expected.items()
        ):
            raise MutationRejected("field-owner rewrite duty differs from its declared scope")

    def flush_reports(self, home: Path, link: dict[str, Any]) -> list[str]:
        link_path = home / "field-owner-link.json"
        admitted: list[str] = []
        while link["pending_reports"]:
            report = link["pending_reports"][0]
            route = (
                f"/v1/programs/{urllib.parse.quote(link['program_id'], safe='')}"
                "/consequences"
            )
            result = self._request("POST", route, report)
            if result.get("accepted") is not True:
                raise RedesignError("field owner did not admit a rewrite consequence report")
            admitted.append(str(result.get("assessment_id", "")))
            link["pending_reports"].pop(0)
            _save_owner_link(link_path, link)
        return admitted


def _owner_program_row(snapshot: Mapping[str, Any], program_id: str) -> Mapping[str, Any]:
    row = next(
        (
            item
            for item in snapshot["records"]
            if item["reference"]["id"] == f"{RESPONSIBILITY_RECORD_PREFIX}{program_id}"
        ),
        None,
    )
    if not isinstance(row, Mapping):
        raise MutationRejected("field-owner snapshot omitted the rewrite program duty")
    return row


def _rewrite_outcome_reports(
    link: Mapping[str, Any],
    *,
    generation: int,
    receipt: Mapping[str, Any] | None,
    interrupted: bool = False,
) -> list[dict[str, Any]]:
    responsibility = link["program_request"]["responsibility"]
    groups = responsibility["affected"]
    digest_value = None if receipt is None else receipt.get("content_sha256")
    selected = None if receipt is None else receipt.get("selected_candidate_id")
    reports = []
    for index, affected in enumerate(groups):
        group_digest = digest({"index": index, "affected": affected})[:12]
        if interrupted:
            observation = (
                f"Rewrite generation {generation} did not return a settled outcome. "
                "Check whether its local promotion pointer advanced before drawing "
                "any conclusion about effects."
            )
            evidence = f"campaign_id={link['campaign_id']}; target_generation={generation}"
            uncertainty = (
                "The interrupted process left the technical result and any practical "
                "effects indeterminate."
            )
        else:
            observation = (
                f"Rewrite generation {generation} passed the campaign's software-level "
                "verification and was promoted. This does not establish an outcome "
                "for the affected group."
            )
            evidence = (
                f"receipt_sha256={digest_value}; selected_candidate_id={selected}"
            )
            uncertainty = (
                "No independent human or ecological outcome measurement is present "
                "in this technical receipt."
            )
        reports.append(
            {
                "request_id": (
                    f"mindfield-review-{link['campaign_id']}-g{generation:06d}-{group_digest}"
                ),
                "observed_at": _utc_now(),
                "consequence": {
                    "dimension": "development",
                    "affected": affected,
                    "observation": observation,
                    "evidence": evidence,
                    "uncertainty": uncertainty,
                    "status": "reported",
                    "follow_up": (
                        "Invite this affected group to assess the successor's practical "
                        "effects and chosen-purpose fit. Record its evidence, uncertainty, "
                        "correction, or refusal in the Research Workspace before the "
                        "next successor generation."
                    ),
                },
            }
        )
    return reports




def _field_owner_client(base_url: str) -> _FieldOwnerClient:
    return _FieldOwnerClient(base_url)


def _responsibility_snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    records = snapshot.get("records")
    if not isinstance(records, list) or digest(records) != snapshot.get("records_sha256"):
        raise MutationRejected("responsibility snapshot changed after import")
    return digest(snapshot)


def _hash_values(values: Any, label: str) -> list[str]:
    if not isinstance(values, list):
        raise MutationRejected(f"responsibility {label} is not a list")
    return sorted({digest(value) for value in values})


def _summarize_responsibility_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only bounded hashes and identifiers; never persist participant report text."""
    _responsibility_snapshot_digest(snapshot)
    summaries: list[dict[str, Any]] = []
    for row in snapshot["records"]:
        reference = row["reference"]
        record = row["record"]
        payload = record["payload"]
        responsibility = payload["responsibility"]
        commitments = {
            key: responsibility[key]
            for key in ("schema", "affected", "intended_benefit", "possible_burdens", "review_question")
        }
        fixed_fields = {
            key: value
            for key, value in responsibility.items()
            if key not in {
                "affected",
                "possible_burdens",
                "outstanding_assessments",
                "consequence_ledger",
            }
        }
        authority_fields = {
            key: value
            for key, value in responsibility.items()
            if key == "decision_owner" or "authority" in key or "decision" in key
        }
        assessments = responsibility.get("outstanding_assessments", [])
        ledger = payload.get(
            "consequence_ledger", responsibility.get("consequence_ledger", [])
        )
        assessment_hashes = _hash_values(assessments, "outstanding assessments")
        ledger_hashes = _hash_values(ledger, "consequence ledger")
        support_roots = record.get("support_roots", [])
        if not isinstance(support_roots, list):
            raise MutationRejected(f"responsibility support roots are invalid: {record['id']}")
        if not isinstance(ledger, list):
            raise MutationRejected(f"responsibility consequence ledger is invalid: {record['id']}")
        ledger_by_id: dict[str, Mapping[str, Any]] = {}
        for ledger_row in ledger:
            assessment_id = (
                ledger_row.get("assessment_id")
                if isinstance(ledger_row, Mapping)
                else None
            )
            if (
                not isinstance(assessment_id, str)
                or not assessment_id
                or len(assessment_id) > 256
                or assessment_id in ledger_by_id
                or not isinstance(ledger_row.get("consequence"), Mapping)
            ):
                raise MutationRejected(f"responsibility consequence ledger row is invalid: {record['id']}")
            ledger_by_id[assessment_id] = ledger_row
        resolved_assessment_ids: set[str] = set()
        for ledger_row in ledger:
            consequence = ledger_row["consequence"]
            review_of = consequence.get("review_of_assessment_id")
            if review_of is None:
                continue
            target = ledger_by_id.get(review_of) if isinstance(review_of, str) else None
            target_consequence = target.get("consequence") if isinstance(target, Mapping) else None
            if (
                not isinstance(target_consequence, Mapping)
                or consequence.get("affected") != target_consequence.get("affected")
            ):
                raise MutationRejected(f"responsibility report review is unbound: {record['id']}")
            target_follow_up = target_consequence.get("follow_up")
            if not (
                target_consequence.get("status") in {"reported", "disputed"}
                or isinstance(target_follow_up, str) and bool(target_follow_up.strip())
            ):
                raise MutationRejected(f"responsibility report review target was not actionable: {record['id']}")
            if consequence.get("status") == "observed" and consequence.get("follow_up") is None:
                resolved_assessment_ids.add(digest(review_of))
        assessment_states = []
        actionable_assessment_hashes = []
        actionable_assessment_by_id: dict[str, str] = {}
        for assessment in assessments:
            assessment_id = (
                assessment.get("assessment_id")
                if isinstance(assessment, Mapping)
                else None
            )
            ledger_row = ledger_by_id.get(assessment_id) if isinstance(assessment_id, str) else None
            consequence = assessment.get("consequence") if isinstance(assessment, Mapping) else None
            if (
                not isinstance(consequence, Mapping)
                or not isinstance(assessment_id, str)
                or not isinstance(ledger_row, Mapping)
                or digest(assessment) != digest(ledger_row)
            ):
                raise MutationRejected(f"responsibility assessment is not bound to its ledger: {record['id']}")
            status = consequence.get("status")
            follow_up = consequence.get("follow_up")
            if (
                not isinstance(consequence.get("dimension"), str)
                or consequence.get("dimension")
                not in {"material_security", "agency", "development", "shared_power", "regeneration", "correction"}
                or not isinstance(status, str)
                or status not in {"reported", "observed", "disputed"}
                or (follow_up is not None and not isinstance(follow_up, str))
                or any(
                    not isinstance(consequence.get(key), str)
                    for key in ("affected", "observation", "evidence", "uncertainty")
                )
            ):
                raise MutationRejected(f"responsibility assessment status or follow-up is malformed: {record['id']}")
            follow_up_open = isinstance(follow_up, str) and bool(follow_up.strip())
            if status in {"reported", "disputed"} or follow_up_open:
                actionable_assessment_hashes.append(digest(assessment))
                actionable_assessment_by_id[digest(assessment_id)] = digest(assessment)
            assessment_states.append(
                {
                    "status": status,
                    "follow_up_open": follow_up_open,
                }
            )
        summaries.append(
            {
                "id": record["id"],
                "kind": "Obligation",
                "revision": reference["content_version"],
                "record_status": record["status"],
                "payload_state": payload.get("state"),
                "responsibility_schema": responsibility["schema"],
                "priority_sha256": digest(payload["priority"]),
                "decision_owner_sha256": digest(responsibility["decision_owner"]),
                "authority_field_sha256": {
                    key: digest(value) for key, value in sorted(authority_fields.items())
                },
                "responsibility_fixed_sha256": {
                    key: digest(value) for key, value in sorted(fixed_fields.items())
                },
                "commitment_field_sha256": {
                    key: digest(value) for key, value in sorted(commitments.items())
                },
                "affected_item_sha256": _hash_values(responsibility["affected"], "affected"),
                "burden_item_sha256": _hash_values(responsibility["possible_burdens"], "possible burdens"),
                "assessment_sha256": assessment_hashes,
                "actionable_assessment_sha256": sorted(set(actionable_assessment_hashes)),
                "actionable_assessment_by_id_sha256": actionable_assessment_by_id,
                "resolved_assessment_id_sha256": sorted(resolved_assessment_ids),
                "consequence_ledger_sha256": ledger_hashes,
                "assessment_evidence_sha256": sorted(set(assessment_hashes + ledger_hashes)),
                "assessment_states": sorted(assessment_states, key=lambda item: (str(item["status"]), item["follow_up_open"])),
                "support_root_sha256": _hash_values(support_roots, "support roots"),
                "responsibility_sha256": digest(responsibility),
                "record_sha256": digest(record),
            }
        )
    return {
        "schema": RESPONSIBILITY_CONTINUITY_SCHEMA,
        "source_field_state_sha256": snapshot["field_state_sha256"],
        "records_sha256": snapshot["records_sha256"],
        "snapshot_sha256": digest(snapshot),
        "record_count": len(summaries),
        "record_ids": [row["id"] for row in summaries],
        "charter_id": RESPONSIBILITY_CHARTER_ID,
        "records": summaries,
    }


def _assert_responsibility_evidence_successor(
    previous_evidence: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Require charter and prior duty facets to persist while allowing added evidence."""
    if (
        previous_evidence.get("schema") != RESPONSIBILITY_CONTINUITY_SCHEMA
        or current_evidence.get("schema") != RESPONSIBILITY_CONTINUITY_SCHEMA
    ):
        raise MutationRejected("responsibility continuity evidence is invalid")
    previous_rows = previous_evidence.get("records")
    current_rows = current_evidence.get("records")
    if (
        not isinstance(previous_rows, list)
        or not isinstance(current_rows, list)
        or not previous_rows
        or not current_rows
    ):
        raise MutationRejected("responsibility continuity record facets are unavailable")
    previous: dict[str, Mapping[str, Any]] = {}
    current: dict[str, Mapping[str, Any]] = {}
    for target, rows in ((previous, previous_rows), (current, current_rows)):
        for row in rows:
            if not isinstance(row, Mapping):
                raise MutationRejected("responsibility continuity record facet is invalid")
            record_id = row.get("id")
            revision = row.get("revision")
            if (
                not isinstance(record_id, str)
                or not record_id.startswith(RESPONSIBILITY_RECORD_PREFIX)
                or record_id in target
                or row.get("kind") != "Obligation"
                or not isinstance(revision, int)
                or isinstance(revision, bool)
            ):
                raise MutationRejected("responsibility continuity record identity is invalid")
            target[record_id] = row
    if current_evidence.get("record_ids") != sorted(current):
        raise MutationRejected("current responsibility snapshot record index is invalid")
    if previous_evidence.get("record_ids") != sorted(previous):
        raise MutationRejected("baseline responsibility snapshot record index is invalid")
    if (
        current_evidence.get("charter_id") != RESPONSIBILITY_CHARTER_ID
        or RESPONSIBILITY_CHARTER_ID not in current
    ):
        raise MutationRejected("current responsibility snapshot has no standing charter")
    if RESPONSIBILITY_CHARTER_ID not in previous:
        raise MutationRejected("baseline responsibility snapshot has no standing charter")
    added = sorted(set(current) - set(previous))
    continued: list[dict[str, Any]] = []
    for record_id in sorted(previous):
        old = previous[record_id]
        new = current.get(record_id)
        if new is None:
            raise MutationRejected(f"responsibility record disappeared: {record_id}")
        if (
            new.get("kind") != "Obligation"
            or new.get("record_status") != "active"
            or new.get("responsibility_schema") != old.get("responsibility_schema")
            or new.get("responsibility_schema") != "cassi.responsibility.v1"
        ):
            raise MutationRejected(f"responsibility record was relabelled or deactivated: {record_id}")
        if int(new.get("revision", 0)) < int(old.get("revision", 0)):
            raise MutationRejected(f"responsibility record revision moved backward: {record_id}")
        if new.get("decision_owner_sha256") != old.get("decision_owner_sha256"):
            raise MutationRejected(f"responsibility decision owner changed: {record_id}")
        old_authority = old.get("authority_field_sha256")
        new_authority = new.get("authority_field_sha256")
        if (
            not isinstance(old_authority, Mapping)
            or not isinstance(new_authority, Mapping)
            or dict(new_authority) != dict(old_authority)
        ):
            raise MutationRejected(f"responsibility authority was removed or changed: {record_id}")
        old_fixed = old.get("responsibility_fixed_sha256")
        new_fixed = new.get("responsibility_fixed_sha256")
        if not isinstance(old_fixed, Mapping) or not isinstance(new_fixed, Mapping):
            raise MutationRejected(f"responsibility commitments are invalid: {record_id}")
        if any(new_fixed.get(key) != value for key, value in old_fixed.items()):
            raise MutationRejected(f"responsibility authority or commitment changed: {record_id}")
        old_actionable_by_id = old.get("actionable_assessment_by_id_sha256")
        new_actionable_by_id = new.get("actionable_assessment_by_id_sha256")
        resolved_ids = new.get("resolved_assessment_id_sha256")
        if isinstance(old_actionable_by_id, Mapping):
            if (
                not isinstance(new_actionable_by_id, Mapping)
                or not isinstance(resolved_ids, list)
            ):
                raise MutationRejected(f"responsibility actionable evidence is incomplete: {record_id}")
            for assessment_id_hash, old_hash in old_actionable_by_id.items():
                if assessment_id_hash in new_actionable_by_id:
                    if new_actionable_by_id[assessment_id_hash] != old_hash:
                        raise MutationRejected(f"responsibility assessment changed: {record_id}")
                elif assessment_id_hash not in resolved_ids:
                    raise MutationRejected(
                        f"actionable responsibility report disappeared without linked review: {record_id}"
                    )
        else:
            old_actionable = old.get("actionable_assessment_sha256")
            new_actionable = new.get("actionable_assessment_sha256")
            if (
                not isinstance(old_actionable, list)
                or not isinstance(new_actionable, list)
                or not set(old_actionable).issubset(new_actionable)
            ):
                raise MutationRejected(
                    f"legacy responsibility baseline cannot verify report resolution: {record_id}"
                )
        for key in (
            "affected_item_sha256",
            "burden_item_sha256",
            "consequence_ledger_sha256",
            "support_root_sha256",
        ):
            old_values = old.get(key)
            new_values = new.get(key)
            if (
                not isinstance(old_values, list)
                or not isinstance(new_values, list)
                or not set(old_values).issubset(new_values)
            ):
                raise MutationRejected(f"responsibility scope or evidence was removed: {record_id}:{key}")
        continued.append(
            {
                "id": record_id,
                "from_revision": old["revision"],
                "to_revision": new["revision"],
                "record_sha256": new["record_sha256"],
                "added_evidence_sha256": sorted(
                    set(new["assessment_evidence_sha256"])
                    - set(old["assessment_evidence_sha256"])
                ),
            }
        )
    return {
        "schema": RESPONSIBILITY_CONTINUITY_SCHEMA,
        "status": "monotonic",
        "baseline_records_sha256": previous_evidence.get("records_sha256"),
        "baseline_field_state_sha256": previous_evidence.get("source_field_state_sha256"),
        "current_records_sha256": current_evidence.get("records_sha256"),
        "continued_records": continued,
        "added_record_ids": added,
        "source_field_state_sha256": current_evidence.get("source_field_state_sha256"),
    }


def _responsibility_last_observed(receipt: Mapping[str, Any]) -> Mapping[str, Any] | None:
    evidence = receipt.get("responsibility_continuity")
    if not isinstance(evidence, Mapping):
        return None
    _validate_responsibility_continuity_evidence(evidence)
    observed = evidence.get("last_observed")
    if observed is None:
        return None
    if not isinstance(observed, Mapping) or observed.get("schema") != RESPONSIBILITY_CONTINUITY_SCHEMA:
        raise MutationRejected("persisted responsibility baseline is invalid")
    return observed


def _responsibility_campaign_evidence(
    previous_receipt: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    previous = (
        None
        if previous_receipt is None
        else _responsibility_last_observed(previous_receipt)
    )
    if (
        previous_receipt is not None
        and int(previous_receipt.get("generation", 0)) > 0
        and previous is None
    ):
        raise MutationRejected(
            "existing successor generation lacks field-owner continuity; use a new isolated data-home"
        )
    current = _summarize_responsibility_snapshot(snapshot)
    comparison = (
        None
        if previous is None
        else _assert_responsibility_evidence_successor(previous, current)
    )
    return {
        "schema": RESPONSIBILITY_CONTINUITY_SCHEMA,
        "status": "baseline" if comparison is None else "monotonic",
        "reason": "first-read-only-field-snapshot" if comparison is None else "fresh-snapshot-monotonic",
        "scope": "read-only-entity-snapshot; not a live field-home mutation",
        "current_snapshot_sha256": _responsibility_snapshot_digest(snapshot),
        "baseline": previous,
        "last_observed": current,
        "comparison": comparison,
    }


def _check_responsibility_snapshot(
    receipt: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    previous = _responsibility_last_observed(receipt)
    if int(receipt.get("generation", 0)) > 0 and previous is None:
        raise MutationRejected(
            "existing successor generation lacks field-owner continuity; use a new isolated data-home"
        )
    current = _summarize_responsibility_snapshot(snapshot)
    comparison = (
        None
        if previous is None
        else _assert_responsibility_evidence_successor(previous, current)
    )
    return {
        "schema": RESPONSIBILITY_CONTINUITY_SCHEMA,
        "status": "baseline" if comparison is None else "monotonic",
        "current_snapshot_sha256": _responsibility_snapshot_digest(snapshot),
        "source_field_state_sha256": current["source_field_state_sha256"],
        "records_sha256": current["records_sha256"],
        "baseline": previous,
        "last_observed": current,
        "comparison": comparison,
    }






def _validate_responsibility_summary(summary: Mapping[str, Any]) -> None:
    summary_keys = {
        "schema",
        "source_field_state_sha256",
        "records_sha256",
        "snapshot_sha256",
        "record_count",
        "record_ids",
        "charter_id",
        "records",
    }
    if set(summary) != summary_keys or summary.get("schema") != RESPONSIBILITY_CONTINUITY_SCHEMA:
        raise MutationRejected("persisted responsibility summary schema is invalid")
    for key in ("source_field_state_sha256", "records_sha256", "snapshot_sha256"):
        value = summary.get(key)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise MutationRejected(f"persisted responsibility digest is invalid: {key}")
    rows = summary.get("records")
    record_ids = summary.get("record_ids")
    count = summary.get("record_count")
    if (
        not isinstance(rows, list)
        or not rows
        or len(rows) > 4096
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count != len(rows)
        or not isinstance(record_ids, list)
        or any(not isinstance(record_id, str) for record_id in record_ids)
        or len(set(record_ids)) != len(record_ids)
        or record_ids != sorted(record_ids)
        or record_ids != [row.get("id") for row in rows if isinstance(row, Mapping)]
        or summary.get("charter_id") != RESPONSIBILITY_CHARTER_ID
        or RESPONSIBILITY_CHARTER_ID not in record_ids
    ):
        raise MutationRejected("persisted responsibility summary record index is invalid")
    row_keys = {
        "id",
        "kind",
        "revision",
        "record_status",
        "payload_state",
        "responsibility_schema",
        "priority_sha256",
        "decision_owner_sha256",
        "authority_field_sha256",
        "responsibility_fixed_sha256",
        "commitment_field_sha256",
        "affected_item_sha256",
        "burden_item_sha256",
        "assessment_sha256",
        "actionable_assessment_sha256",
        "actionable_assessment_by_id_sha256",
        "resolved_assessment_id_sha256",
        "consequence_ledger_sha256",
        "assessment_evidence_sha256",
        "assessment_states",
        "support_root_sha256",
        "responsibility_sha256",
        "record_sha256",
    }
    hash_fields = {
        "priority_sha256",
        "decision_owner_sha256",
        "responsibility_sha256",
        "record_sha256",
    }
    hash_lists = {
        "affected_item_sha256",
        "burden_item_sha256",
        "assessment_sha256",
        "actionable_assessment_sha256",
        "consequence_ledger_sha256",
        "assessment_evidence_sha256",
        "resolved_assessment_id_sha256",
        "support_root_sha256",
    }
    previous_id = ""
    for row in rows:
        found_keys = set(row) if isinstance(row, Mapping) else set()
        legacy_row_keys = row_keys - {
            "actionable_assessment_by_id_sha256",
            "resolved_assessment_id_sha256",
        }
        if (
            not isinstance(row, Mapping)
            or found_keys not in (row_keys, legacy_row_keys)
            or not isinstance(row.get("id"), str)
            or len(row["id"]) > 256
            or not row["id"].startswith(RESPONSIBILITY_RECORD_PREFIX)
            or row["id"] <= previous_id
            or row.get("kind") != "Obligation"
            or not isinstance(row.get("revision"), int)
            or isinstance(row.get("revision"), bool)
            or row["revision"] < 1
            or row.get("record_status") != "active"
            or not isinstance(row.get("payload_state"), str)
            or row.get("payload_state") not in {"pending", "resolved"}
            or row.get("responsibility_schema") != "cassi.responsibility.v1"
        ):
            raise MutationRejected("persisted responsibility record facet is invalid")
        previous_id = row["id"]
        for key in hash_fields:
            value = row.get(key)
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise MutationRejected(f"persisted responsibility facet digest is invalid: {key}")
        for key in hash_lists:
            if key not in row and key == "resolved_assessment_id_sha256":
                continue
            values = row.get(key)
            if (
                not isinstance(values, list)
                or any(not isinstance(value, str) for value in values)
                or values != sorted(set(values))
                or any(not _SHA256.fullmatch(value) for value in values)
            ):
                raise MutationRejected(f"persisted responsibility digest list is invalid: {key}")
        by_id = row.get("actionable_assessment_by_id_sha256")
        if by_id is not None and (
            not isinstance(by_id, Mapping)
            or len(by_id) > 4096
            or any(
                not isinstance(key, str)
                or not _SHA256.fullmatch(key)
                or not isinstance(value, str)
                or not _SHA256.fullmatch(value)
                for key, value in by_id.items()
            )
        ):
            raise MutationRejected("persisted responsibility actionable-assessment index is invalid")
        for key in ("authority_field_sha256", "responsibility_fixed_sha256", "commitment_field_sha256"):
            values = row.get(key)
            if (
                not isinstance(values, Mapping)
                or any(
                    not isinstance(name, str)
                    or len(name) > 128
                    or not isinstance(value, str)
                    or not _SHA256.fullmatch(value)
                    for name, value in values.items()
                )
            ):
                raise MutationRejected(f"persisted responsibility facet map is invalid: {key}")
        states = row.get("assessment_states")
        if (
            not isinstance(states, list)
            or any(
                not isinstance(item, Mapping)
                or set(item) != {"status", "follow_up_open"}
                or not isinstance(item.get("status"), str)
                or item.get("status") not in {"reported", "observed", "disputed"}
                or not isinstance(item.get("follow_up_open"), bool)
                for item in states
            )
        ):
            raise MutationRejected("persisted responsibility assessment status facets are invalid")


def _validate_responsibility_continuity_evidence(evidence: Mapping[str, Any]) -> None:
    allowed_keys = {
        "schema",
        "status",
        "reason",
        "scope",
        "current_snapshot_sha256",
        "last_observed_snapshot_sha256",
        "source_field_state_sha256",
        "records_sha256",
        "baseline",
        "last_observed",
        "comparison",
        "baselines",
        "comparisons",
    }
    if set(evidence) - allowed_keys:
        raise MutationRejected("responsibility continuity evidence contains unbounded fields")
    if evidence.get("schema") != RESPONSIBILITY_CONTINUITY_SCHEMA:
        raise MutationRejected("persisted responsibility continuity schema is invalid")
    reason = evidence.get("reason")
    if reason is not None and (
        not isinstance(reason, str)
        or reason not in {
            "no-entity-responsibility-snapshot-supplied",
            "no-fresh-responsibility-snapshot-supplied",
            "first-read-only-field-snapshot",
            "fresh-snapshot-monotonic",
        }
    ):
        raise MutationRejected("responsibility continuity reason is invalid")
    scope = evidence.get("scope")
    if scope is not None and (
        not isinstance(scope, str)
        or scope not in {
            "redesign-owned-field-only",
            "read-only-entity-snapshot; not a live field-home mutation",
            "read-only-entity-snapshot; rollback changes redesign pointers only",
        }
    ):
        raise MutationRejected("responsibility continuity scope is invalid")
    status = evidence.get("status")
    last = evidence.get("last_observed")
    if last is not None:
        if not isinstance(last, Mapping):
            raise MutationRejected("persisted responsibility observation is invalid")
        _validate_responsibility_summary(last)
    current_snapshot_sha256 = evidence.get("current_snapshot_sha256")
    if current_snapshot_sha256 is not None and (
        not isinstance(current_snapshot_sha256, str)
        or not _SHA256.fullmatch(current_snapshot_sha256)
    ):
        raise MutationRejected("persisted responsibility snapshot digest is invalid")
    if "comparisons" in evidence:
        if set(evidence) != {
            "schema",
            "status",
            "current_snapshot_sha256",
            "source_field_state_sha256",
            "records_sha256",
            "last_observed",
            "baselines",
            "comparisons",
            "scope",
        }:
            raise MutationRejected("rollback responsibility evidence shape is invalid")
        baselines = evidence.get("baselines")
        comparisons = evidence.get("comparisons")
        keys = {"current_generation", "target_generation"}
        if (
            not isinstance(baselines, Mapping)
            or set(baselines) != keys
            or not isinstance(comparisons, Mapping)
            or set(comparisons) != keys
            or not isinstance(last, Mapping)
            or current_snapshot_sha256 != last.get("snapshot_sha256")
        ):
            raise MutationRejected("rollback responsibility comparisons are incomplete")
        compared = False
        for key in sorted(keys):
            baseline = baselines[key]
            comparison = comparisons[key]
            if baseline is None:
                if comparison is not None:
                    raise MutationRejected("rollback responsibility baseline is inconsistent")
                continue
            if not isinstance(baseline, Mapping):
                raise MutationRejected("rollback responsibility baseline is invalid")
            _validate_responsibility_summary(baseline)
            expected = _assert_responsibility_evidence_successor(baseline, last)
            if comparison != expected:
                raise MutationRejected("rollback responsibility comparison diverged")
            compared = True
        if status != ("monotonic" if compared else "baseline"):
            raise MutationRejected("rollback responsibility status is inconsistent")
        return
    baseline = evidence.get("baseline")
    comparison = evidence.get("comparison")
    if status == "not-assessed":
        allowed_unassessed_shapes = (
            {
                "schema",
                "status",
                "reason",
                "scope",
                "current_snapshot_sha256",
                "baseline",
                "last_observed",
                "comparison",
            },
            {
                "schema",
                "status",
                "reason",
                "last_observed_snapshot_sha256",
                "current_snapshot_sha256",
                "baseline",
                "last_observed",
                "comparison",
            },
        )
        if set(evidence) not in allowed_unassessed_shapes:
            raise MutationRejected("unassessed responsibility evidence shape is invalid")
        if baseline is not None or comparison is not None or current_snapshot_sha256 is not None:
            raise MutationRejected("unassessed responsibility evidence carries a comparison")
        last_digest = evidence.get("last_observed_snapshot_sha256")
        if last_digest is not None and (
            not isinstance(last_digest, str)
            or not _SHA256.fullmatch(last_digest)
            or not isinstance(last, Mapping)
            or last_digest != last.get("snapshot_sha256")
        ):
            raise MutationRejected("unassessed responsibility reference is invalid")
        return
    if not isinstance(last, Mapping) or current_snapshot_sha256 != last.get("snapshot_sha256"):
        raise MutationRejected("responsibility evidence has no matching current observation")
    if status == "baseline":
        if set(evidence) != {
            "schema",
            "status",
            "reason",
            "scope",
            "current_snapshot_sha256",
            "baseline",
            "last_observed",
            "comparison",
        }:
            raise MutationRejected("responsibility baseline evidence shape is invalid")
        if baseline is not None or comparison is not None:
            raise MutationRejected("responsibility baseline state is inconsistent")
        return
    if set(evidence) != {
        "schema",
        "status",
        "reason",
        "scope",
        "current_snapshot_sha256",
        "baseline",
        "last_observed",
        "comparison",
    }:
        raise MutationRejected("responsibility continuity evidence shape is invalid")
    if status != "monotonic" or not isinstance(baseline, Mapping):
        raise MutationRejected("responsibility continuity state is invalid")
    _validate_responsibility_summary(baseline)
    expected = _assert_responsibility_evidence_successor(baseline, last)
    if comparison != expected:
        raise MutationRejected("responsibility continuity comparison diverged")


def _write_workspace(root: Path, files: Mapping[str, str]) -> None:
    for relative, source in sorted(files.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8", newline="")


def _architecture_research_space(
    parent_files: Mapping[str, str],
    parent_digest: str,
    *,
    cycle: int = 0,
) -> dict[str, Any]:
    """Describe the bounded compiler catalogs admitted to the resident field.

    The catalogs are deliberately finite and deterministic.  They are not a
    learned IR generator; the field owns the question and compiler-family
    selection.
    """
    cycle_suffix = "" if cycle <= 1 else f":cycle{cycle}"
    question_prefix = f"architecture-question:{parent_digest[:24]}{cycle_suffix}"
    return {
        "schema": "cassimindfield.architecture-research-space.v2",
        "question_options": [
            {
                "question_id": f"{question_prefix}:module-boundary-v1",
                "question": "Which bounded module-boundary adapter preserves the observed baseline and holdout contract?",
                "compiler_family": "module-boundary-v1",
                "priority": 1.0,
                "variant_catalog": [
                    {
                        "variant_key": "import-alias",
                        "hypothesis_suffix": "import-alias",
                        "replacement": "return value + bias",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a bounded import alias preserves the API successor contract",
                    },
                    {
                        "variant_key": "import-alias-drift",
                        "hypothesis_suffix": "import-alias-drift",
                        "replacement": "return value + bias + 1",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "an aliased module boundary with an offset remains a candidate for rejection",
                    },
                ],
            },
            {
                "question_id": f"{question_prefix}:api-successor-v1",
                "question": "Which bounded API-successor architecture preserves the observed baseline and holdout contract?",
                "compiler_family": "api-successor-v1",
                "priority": 1.0,
                "variant_catalog": [
                    {
                        "variant_key": "clean-cutover",
                        "hypothesis_suffix": "clean-cutover",
                        "replacement": "return value + bias",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a synthesized API successor preserves the baseline holdout",
                    },
                    {
                        "variant_key": "offset-drift",
                        "hypothesis_suffix": "offset-drift",
                        "replacement": "return value + bias + 1",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "an offset successor remains a candidate for rejection",
                    },
                ],
            },
            {
                "question_id": f"{question_prefix}:facade-adapter-v1",
                "question": "Which bounded facade-adapter architecture preserves the observed baseline and holdout contract?",
                "compiler_family": "facade-adapter-v1",
                "priority": 1.0,
                "variant_catalog": [
                    {
                        "variant_key": "facade-cutover",
                        "hypothesis_suffix": "facade-cutover",
                        "replacement": "return value + bias",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a new facade module retargets the public adapter without changing behavior",
                    },
                    {
                        "variant_key": "facade-offset-drift",
                        "hypothesis_suffix": "facade-offset-drift",
                        "replacement": "return value + bias + 1",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a facade cutover with an offset remains a candidate for rejection",
                    },
                ],
            },
        ],
        "source_paths": sorted(parent_files),
        "parent_source_digest": parent_digest,
        "bounded": True,
        "max_variants": MAX_CANDIDATES,
    }


def _compile_cumulative_question_documents(
    parent_files: Mapping[str, str],
    parent_digest: str,
    question: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Compose a new typed adapter layer from the promoted parent's topology."""
    compiler_family = str(question.get("compiler_family", ""))
    catalog = question.get("variant_catalog")
    if compiler_family not in {
        "api-successor-v1",
        "module-boundary-v1",
        "facade-adapter-v1",
    }:
        raise RedesignError("field research question named an unsupported compiler family")
    if not isinstance(catalog, list) or not catalog or len(catalog) > MAX_CANDIDATES:
        raise RedesignError("field research question has no bounded compiler catalog")
    runtime_path = "src/runtime.py"
    runtime_source = parent_files.get(runtime_path)
    if not isinstance(runtime_source, str):
        raise RedesignError("promoted parent has no runtime module")
    try:
        runtime_tree = ast.parse(runtime_source, filename=runtime_path)
    except SyntaxError as exc:
        raise RedesignError("promoted parent runtime does not parse") from exc
    bindings: list[tuple[str, str, str]] = []
    runtime_lines = runtime_source.splitlines()
    for node in ast.walk(runtime_tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            if alias.name != "increment":
                continue
            local_name = alias.asname or alias.name
            bindings.append((node.module, local_name, runtime_lines[node.lineno - 1]))
    if len(bindings) != 1:
        raise RedesignError("promoted parent must expose one runtime increment binding")
    upstream_module, local_name, import_line = bindings[0]
    family_token = compiler_family.removesuffix("-v1").replace("-", "_")
    layer_stem = f"{family_token}_{parent_digest[:10]}"
    layer_path = f"src/{layer_stem}.py"
    component_rows = [
        {
            "id": f"parent_{digest(path)[:16]}",
            "module": path,
            "kind": "runtime" if path == runtime_path else "module",
            "symbols": ["run"] if path == runtime_path else [],
        }
        for path in sorted(parent_files)
        if path.endswith(".py")
    ]
    layer_component = f"layer_{digest(layer_path)[:16]}"
    component_rows.append(
        {
            "id": layer_component,
            "module": layer_path,
            "kind": "adapter",
            "symbols": ["increment"],
        }
    )
    rows: list[dict[str, Any]] = []
    for variant in catalog:
        if not isinstance(variant, Mapping):
            raise RedesignError("field research question compiler catalog is invalid")
        variant_key = str(variant.get("variant_key", ""))
        if not variant_key:
            raise RedesignError("field research question compiler variant is invalid")
        drift = "drift" in variant_key
        return_line = (
            "    return _upstream_increment(value) + 1\n"
            if drift
            else "    return _upstream_increment(value)\n"
        )
        layer_source = (
            f"from {upstream_module} import increment as _upstream_increment\n\n\n"
            "def increment(value):\n"
            f"{return_line}"
        )
        replacement_import = (
            f"from {layer_stem} import increment as {local_name}"
            if local_name != "increment"
            else f"from {layer_stem} import increment"
        )
        candidate = {
            "schema": "cassimindfield.architecture-ir.v1",
            "version": 1,
            "components": component_rows,
            "interfaces": [],
            "state_ownership": [],
            "flows": [],
            "invariants": [
                {
                    "id": "cumulative_python_parses",
                    "kind": "syntax",
                    "description": "The promoted parent and composed successor layer parse.",
                    "paths": sorted([*parent_files, layer_path]),
                }
            ],
            "operations": [
                {
                    "id": "create_cumulative_layer",
                    "kind": "create_module",
                    "path": layer_path,
                    "component": layer_component,
                    "source": layer_source,
                },
                {
                    "id": "retarget_cumulative_runtime",
                    "kind": "source_replacement",
                    "path": runtime_path,
                    "find": import_line,
                    "replace": replacement_import,
                    "expected_count": 1,
                },
            ],
            "proof_obligations": [
                {
                    "id": "cumulative_parent_preserved",
                    "kind": "behavior",
                    "description": "The new layer preserves the inherited public behavior.",
                    "target": "retarget_cumulative_runtime",
                }
            ],
            "migration": {
                "source_revision": f"generation-{parent_digest[:12]}",
                "target_revision": f"successor-{digest([compiler_family, variant_key, parent_digest])[:12]}",
                "strategy": "incremental",
                "compatibility": "compatible",
                "notes": "Compose one topology-derived layer on the promoted predecessor.",
                "source_digest": parent_digest,
            },
        }
        candidate_id = f"architecture-{compiler_family}-{variant_key}"
        rows.append(
            {
                "hypothesis_id": candidate_id,
                "claim": str(variant.get("claim", "bounded cumulative architecture candidate")),
                "architecture": candidate,
                "parent_source_digest": parent_digest,
                "expected_holdout": dict(variant.get("expected_holdout", {})),
                "source_paths": sorted(parent_files),
                "agenda_origin": "field-owned-architecture-hypothesis",
                "field_question_origin": "field-originated-architecture-question",
                "construction_origin": "field-composed-parent-topology",
                "question_id": question.get("question_id"),
                "compiler_family": compiler_family,
                "variant_key": variant_key,
                "causal_prediction": {
                    "intervention": "insert one typed adapter at the observed runtime binding",
                    "expected_baseline_returncode": 0,
                    "expected_holdout_returncode": 1 if drift else 0,
                    "inherited_parent_digest": parent_digest,
                    "novel_module": layer_path,
                },
            }
        )
    return rows


def _compile_question_documents(
    parent_files: Mapping[str, str],
    parent_digest: str,
    question: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Compile only the bounded family named by the selected field question."""
    if "src/core.py" not in parent_files:
        return _compile_cumulative_question_documents(
            parent_files,
            parent_digest,
            question,
        )
    compiler_family = question.get("compiler_family")
    if compiler_family not in {
        "api-successor-v1",
        "module-boundary-v1",
        "facade-adapter-v1",
    }:
        raise RedesignError("field research question named an unsupported compiler family")
    catalog = question.get("variant_catalog")
    if not isinstance(catalog, list) or not catalog or len(catalog) > MAX_CANDIDATES:
        raise RedesignError("field research question has no bounded compiler catalog")
    _, base_ir = build_example()
    base_document = base_ir.to_dict()
    base_document["migration"] = dict(base_document["migration"])
    base_document["migration"]["source_revision"] = "predecessor-v13"
    base_document["migration"]["source_digest"] = parent_digest
    rows: list[dict[str, Any]] = []
    for variant in catalog:
        if not isinstance(variant, Mapping):
            raise RedesignError("field research question compiler catalog is invalid")
        variant_key = str(variant.get("variant_key", ""))
        replacement = variant.get("replacement")
        if not variant_key or not isinstance(replacement, str):
            raise RedesignError("field research question compiler variant is invalid")
        candidate = json.loads(canonical(base_document))
        if compiler_family == "api-successor-v1":
            for operation in candidate["operations"]:
                if operation.get("id") == "use_bias":
                    operation["replace"] = replacement
            candidate_id = f"architecture-{variant_key}"
        elif compiler_family == "module-boundary-v1":
            # This family makes a real bounded module-boundary edit: the
            # runtime import is aliased and its call site is replaced.  The
            # existing signature migration and source replacement remain
            # typed Architecture IR operations, not a family label.
            for operation in candidate["operations"]:
                if operation.get("id") == "use_bias":
                    operation["replace"] = replacement
                elif operation.get("id") == "retarget_import":
                    operation["replace"] = "from core_math import increment as _increment"
            insert_at = next(
                (
                    index
                    for index, operation in enumerate(candidate["operations"])
                    if operation.get("id") == "create_api"
                ),
                None,
            )
            if insert_at is None:
                raise RedesignError("base architecture is missing its API module operation")
            candidate["operations"].insert(
                insert_at,
                {
                    "id": "runtime_alias_call",
                    "kind": "source_replacement",
                    "path": "src/runtime.py",
                    "find": "return increment(value)",
                    "replace": "return _increment(value)",
                    "expected_count": 1,
                },
            )
            candidate_id = f"architecture-{compiler_family}-{variant_key}"
        else:
            # The facade family composes two existing typed operations: a
            # genuinely new adapter module and a runtime import retarget.
            for operation in candidate["operations"]:
                if operation.get("id") == "use_bias":
                    operation["replace"] = replacement
            candidate["components"].append(
                {
                    "id": "facade",
                    "module": "src/facade.py",
                    "kind": "adapter",
                    "symbols": ["increment"],
                }
            )
            candidate["interfaces"].append(
                {
                    "id": "facade_runtime",
                    "provider": "facade",
                    "consumers": ["runtime"],
                    "symbols": ["increment"],
                    "protocol": "python-import",
                }
            )
            candidate["flows"].append(
                {
                    "id": "facade_to_runtime",
                    "source": "facade",
                    "target": "runtime",
                    "interface": "facade_runtime",
                    "kind": "call",
                }
            )
            for invariant in candidate["invariants"]:
                if invariant.get("id") == "all_python_parses":
                    invariant["paths"].append("src/facade.py")
            candidate["proof_obligations"].append(
                {
                    "id": "facade_created",
                    "kind": "behavior",
                    "description": "The synthesized facade module is present and on the runtime call path.",
                    "target": "create_facade",
                }
            )
            candidate["operations"].extend(
                [
                    {
                        "id": "create_facade",
                        "kind": "create_module",
                        "path": "src/facade.py",
                        "component": "facade",
                        "source": "from core_math import increment as _increment\n\n\ndef increment(value, bias=1):\n    return _increment(value, bias=bias)\n",
                    },
                    {
                        "id": "retarget_runtime_facade",
                        "kind": "source_replacement",
                        "path": "src/runtime.py",
                        "find": "from core_math import increment",
                        "replace": "from facade import increment",
                        "expected_count": 1,
                    },
                ]
            )
            candidate_id = f"architecture-{compiler_family}-{variant_key}"
        rows.append(
            {
                "hypothesis_id": candidate_id,
                "claim": str(variant.get("claim", "bounded architecture candidate")),
                "architecture": candidate,
                "parent_source_digest": parent_digest,
                "expected_holdout": dict(variant.get("expected_holdout", {})),
                "source_paths": sorted(parent_files),
                "agenda_origin": "field-owned-architecture-hypothesis",
                "field_question_origin": "field-originated-architecture-question",
                "question_id": question.get("question_id"),
                "compiler_family": compiler_family,
                "variant_key": variant_key,
            }
        )
    return rows
def _investigation_trace(
    *,
    compiler_family: str,
    candidate_id: str,
    assessment_operation_id: str,
    status: str,
) -> dict[str, Any]:
    """Return an evidence-bound executed trajectory for field procedure learning."""

    return {
        "context": {
            "compiler_family": compiler_family,
            "assessment_operation_id": assessment_operation_id,
        },
        "effects": {"assessment_status": status},
        "failure": None,
        "outcome": {"assessment_status": status},
        "rare_case": False,
        "steps": [
            {"op": operation, "candidate": candidate_id}
            for operation in (
                "locate-binding",
                "compose-operations",
                "compile-successor",
                "measure-holdout",
            )
        ],
        "success": status == "PASS",
        "trajectory_source": "inferred",
        "work": 4,
    }


def _python_topology_metrics(
    parent_files: Mapping[str, str],
) -> dict[str, int]:
    function_count = 0
    dependency_edges = 0
    for path, source in sorted(parent_files.items()):
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            raise RedesignError(
                f"cross-world source is not valid Python: {path}"
            ) from exc
        function_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        dependency_edges += sum(
            len(node.names)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            else 0
            for node in ast.walk(tree)
        )
    return {
        "dependency_edges": dependency_edges,
        "file_count": len(parent_files),
        "function_count": function_count,
    }


def _field_program_construction_task(
    parent_files: Mapping[str, str],
    parent_digest: str,
) -> dict[str, Any]:
    """Derive one typed field-program task from an unfamiliar source world."""

    topology = _python_topology_metrics(parent_files)
    function_count = topology["function_count"]
    dependency_edges = topology["dependency_edges"]
    file_count = topology["file_count"]
    base = (file_count * 7 + function_count * 3) % 128
    delta = max(1, dependency_edges % 17)
    repetitions = max(2, min(8, file_count))
    expected = (base + delta * repetitions) % 256
    body = {
        "schema": "cassimindfield.cross-world-task.v1",
        "source_world": "python-architecture",
        "target_world": "cassifi-structured-field-program",
        "parent_source_digest": parent_digest,
        "topology": topology,
        "construction_ir": {
            "base": base,
            "delta": delta,
            "repetitions": repetitions,
            "emit_stack": "left",
        },
        "causal_prediction": {
            "accumulator": expected,
            "left": [expected],
            "right": [],
            "status": "halted",
        },
    }
    return {**body, "task_sha256": digest(body)}


def _structured_source_from_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """Materialize only the typed construction declared by the task IR."""

    construction = task.get("construction_ir")
    if not isinstance(construction, Mapping):
        raise RedesignError("cross-world task has no construction IR")
    base = int(construction["base"])
    delta = int(construction["delta"])
    repetitions = int(construction["repetitions"])
    emit_stack = str(construction["emit_stack"])
    return {
        "schema": FIELD_PROGRAM_SCHEMA,
        "constants": {"BASE": base, "DELTA": delta},
        "functions": {
            "advance": [{"op": "add_acc", "value": "DELTA"}],
        },
        "main": [
            {"op": "set_acc", "value": "BASE"},
            {
                "op": "repeat",
                "count": repetitions,
                "body": [{"op": "call", "function": "advance"}],
            },
            {"op": "push_acc", "stack": emit_stack},
        ],
    }


def _execute_structured_source(source: Mapping[str, Any]) -> dict[str, Any]:
    compiled = compile_structured_program(source)
    machine = FieldComputer(
        ComputerProfile(
            program_capacity=len(compiled.program) + 2,
            stack_capacity=16,
            max_steps=max(64, len(compiled.program) * 4),
        )
    )
    state, run_receipt = machine.run(
        machine.initial(
            compiled.program,
            left=compiled.left,
            right=compiled.right,
        )
    )
    inspected = machine.inspect(state)
    return {
        "compiled_instruction_count": len(compiled.program),
        "compiled_source_sha256": compiled.source_sha256,
        "execution": {
            "accumulator": inspected["accumulator"],
            "left": inspected["left"],
            "right": inspected["right"],
            "status": inspected["status"],
        },
        "logical_steps": run_receipt["transitions_executed"],
    }


def _construction_plan_search(
    experienced_actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare one transferred plan with a bounded plan-search control."""

    required = [
        "locate-binding",
        "compose-operations",
        "compile-successor",
    ]
    experienced = [str(row.get("op")) for row in experienced_actions]
    if experienced != required:
        raise RedesignError("cross-world procedure returned the wrong construction plan")
    candidates = [
        ["compile-successor"],
        ["locate-binding", "compile-successor"],
        required,
    ]
    attempts = [
        {
            "operations": list(candidate),
            "primitive_steps_examined": len(candidate),
            "status": "accepted" if candidate == required else "rejected",
        }
        for candidate in candidates
    ]
    fresh_work = sum(row["primitive_steps_examined"] for row in attempts)
    experienced_work = len(experienced)
    return {
        "metric": "primitive-plan-steps-examined",
        "experienced": {
            "candidate_plans_evaluated": 1,
            "primitive_steps_examined": experienced_work,
            "status": "completed",
        },
        "fresh_bounded_search": {
            "attempts": attempts,
            "candidate_plans_evaluated": len(attempts),
            "primitive_steps_examined": fresh_work,
            "status": "completed",
        },
        "net_saved_steps": fresh_work - experienced_work,
    }


def _constraint_construction_task(
    parent_files: Mapping[str, str],
    parent_digest: str,
) -> dict[str, Any]:
    """Derive a bounded Boolean transition problem from live topology."""

    topology = _python_topology_metrics(parent_files)
    horizon = 3 + topology["file_count"] % 2
    initial = {
        "phase": topology["function_count"] % 2,
        "carry": topology["dependency_edges"] % 2,
    }
    planted_inputs = [
        int(parent_digest[index], 16) % 2 for index in range(horizon)
    ]
    phase = initial["phase"]
    carry = initial["carry"]
    for drive in planted_inputs:
        phase, carry = phase ^ drive, phase if drive else carry
    body = {
        "schema": "cassimindfield.constraint-world-task.v1",
        "source_world": "python-architecture",
        "target_world": "cassifi-boolean-transition-constraint",
        "parent_source_digest": parent_digest,
        "topology": topology,
        "construction_ir": {
            "state": ["phase", "carry"],
            "inputs": ["drive"],
            "horizon": horizon,
            "initial": initial,
            "input_prefix": planted_inputs[:-1],
            "planted_input_trace": planted_inputs,
            "final": {"phase": phase, "carry": carry},
        },
        "causal_prediction": {
            "status": "sat",
            "final": {"phase": phase, "carry": carry},
            "witness_required": True,
        },
    }
    return {**body, "task_sha256": digest(body)}


def _constraint_source_from_task(task: Mapping[str, Any]) -> dict[str, Any]:
    construction = task.get("construction_ir")
    if not isinstance(construction, Mapping):
        raise RedesignError("constraint-world task has no construction IR")
    initial = construction["initial"]
    final = construction["final"]
    prefix = construction["input_prefix"]
    source = TransitionProblem(
        state=("phase", "carry"),
        inputs=("drive",),
        gates=(
            {"op": "xor", "out": "next_phase", "args": ("phase", "drive")},
            {
                "op": "mux",
                "out": "next_carry",
                "args": ("drive", "phase", "carry"),
            },
        ),
        next_state=(("phase", "next_phase"), ("carry", "next_carry")),
        horizon=int(construction["horizon"]),
        initial=(
            ("phase", int(initial["phase"])),
            ("carry", int(initial["carry"])),
        ),
        input_assertions=tuple(
            (time, "drive", int(value))
            for time, value in enumerate(prefix)
        ),
        final=(
            ("phase", int(final["phase"])),
            ("carry", int(final["carry"])),
        ),
    ).as_dict()
    return json.loads(canonical(source).decode("utf-8"))


def _check_constraint_witness(
    source: Mapping[str, Any],
    witness: Mapping[str, Any],
) -> dict[str, Any]:
    initial = {str(name): int(value) for name, value in source["initial"]}
    phase = initial["phase"]
    carry = initial["carry"]
    trajectory = [{"time": 0, "phase": phase, "carry": carry}]
    horizon = int(source["horizon"])
    drives: list[int] = []
    for time in range(horizon):
        key = f"drive@{time}"
        if key not in witness or int(witness[key]) not in (0, 1):
            raise RedesignError("constraint witness omits a Boolean input")
        drive = int(witness[key])
        drives.append(drive)
        phase, carry = phase ^ drive, phase if drive else carry
        trajectory.append(
            {"time": time + 1, "phase": phase, "carry": carry}
        )
    for time, name, expected in source["input_assertions"]:
        if name != "drive" or drives[int(time)] != int(expected):
            raise RedesignError("constraint witness violates an input assertion")
    final = {str(name): int(value) for name, value in source["final"]}
    if {"phase": phase, "carry": carry} != final:
        raise RedesignError("constraint witness violates the final boundary")
    return {
        "input_trace": drives,
        "trajectory": trajectory,
        "final": {"phase": phase, "carry": carry},
        "status": "PASS",
    }


def _execute_constraint_source(source: Mapping[str, Any]) -> dict[str, Any]:
    compiled = compile_transition_problem(source)
    profile = ConstraintFieldProfile(
        max_variables=compiled.variables,
        max_clauses=len(compiled.clauses) + 64,
        max_transitions=20_000,
        max_learned_clauses=64,
        mode="conflict",
        controller=False,
        controller_size=8,
    )
    field = ConstraintField(profile)
    state = field.initial(compiled)
    transition_count = 0
    while field.status(state) == "running":
        state, _ = field.step(state)
        transition_count += 1
        if transition_count > profile.max_transitions:
            raise RedesignError("constraint field exceeded its transition bound")
    result = field.result(state)
    if result.get("status") != "sat" or not isinstance(
        result.get("witness"), Mapping
    ):
        raise RedesignError("constraint construction did not produce a SAT witness")
    audit = _check_constraint_witness(source, result["witness"])
    return {
        "compiled_problem_sha256": compiled.sha256,
        "compiled_variables": compiled.variables,
        "compiled_clauses": len(compiled.clauses),
        "status": result["status"],
        "reason": result["reason"],
        "witness": dict(sorted(result["witness"].items())),
        "witness_audit": audit,
        "field_transitions": transition_count,
    }




def _reasoning_transition_source(
    topology: Mapping[str, int],
    seed: str,
) -> dict[str, Any]:
    horizon = 4
    initial_phase = int(topology["function_count"]) % 2
    initial_carry = int(topology["dependency_edges"]) % 2
    trace = [int(seed[index], 16) % 2 for index in range(horizon)]
    phase = initial_phase
    carry = initial_carry
    for drive in trace:
        phase, carry = phase ^ drive, phase if drive else carry
    source = TransitionProblem(
        state=("phase", "carry"),
        inputs=("drive",),
        gates=(
            {"op": "xor", "out": "next_phase", "args": ("phase", "drive")},
            {
                "op": "mux",
                "out": "next_carry",
                "args": ("drive", "phase", "carry"),
            },
        ),
        next_state=(("phase", "next_phase"), ("carry", "next_carry")),
        horizon=horizon,
        initial=(("phase", initial_phase), ("carry", initial_carry)),
        input_assertions=tuple(
            (time, "drive", value)
            for time, value in enumerate(trace[:-1])
        ),
        final=(("phase", phase), ("carry", carry)),
    ).as_dict()
    return json.loads(canonical(source).decode("utf-8"))


def _reasoning_parity_block(
    names: Sequence[str],
    rhs: int,
) -> list[list[list[Any]]]:
    rows: list[list[list[Any]]] = []
    for value in range(1 << len(names)):
        bits = [(value >> index) & 1 for index in range(len(names))]
        if sum(bits) % 2 != rhs:
            rows.append(
                [
                    [name, 1 - bit]
                    for name, bit in zip(names, bits)
                ]
            )
    return rows


def _reasoning_parity_contradiction_source(
    names: Sequence[str],
) -> dict[str, Any]:
    clauses = (
        _reasoning_parity_block(names, 0)
        + _reasoning_parity_block(names, 1)
    )
    source = CircuitSpec(
        inputs=tuple(names),
        clauses=tuple(
            tuple((str(name), int(bit)) for name, bit in clause)
            for clause in clauses
        ),
    ).as_dict()
    return json.loads(canonical(source).decode("utf-8"))


def _paired_reasoning_task(
    parent_files: Mapping[str, str],
    parent_digest: str,
) -> dict[str, Any]:
    topology = _python_topology_metrics(parent_files)
    training_seed = hashlib.sha256(
        f"{parent_digest}:training".encode("utf-8")
    ).hexdigest()
    sources = {
        "sat_training": _reasoning_transition_source(
            topology,
            training_seed,
        ),
        "sat_held_out": _reasoning_transition_source(
            topology,
            parent_digest,
        ),
        "unsat_training": _reasoning_parity_contradiction_source(
            ("a", "b", "c", "d", "e", "f"),
        ),
        "unsat_held_out": _reasoning_parity_contradiction_source(
            ("u", "v", "w", "x", "y", "z"),
        ),
    }
    body = {
        "schema": "cassimindfield.paired-reasoning-task.v1",
        "source_world": "python-architecture",
        "target_world": "cassifi-exact-constraint-reasoning",
        "parent_source_digest": parent_digest,
        "topology": topology,
        "sources": sources,
        "causal_prediction": {
            "sat_held_out": {
                "status": "sat",
                "evidence": "source-checked-witness",
            },
            "unsat_held_out": {
                "status": "unsat",
                "evidence": "independently-audited-certificate",
            },
        },
    }
    return {**body, "task_sha256": digest(body)}


def _run_constraint_regime(
    source: Mapping[str, Any],
    mode: str,
    *,
    transition_budget: int = 20_000,
) -> dict[str, Any]:
    if mode not in {"local", "conflict", "algebraic"}:
        raise RedesignError(f"unknown constraint reasoning regime {mode!r}")
    compiled = compile_constraint_source(source)
    algebraic = mode == "algebraic"
    max_augmentations = (
        min(64, max(0, 262_144 - len(compiled.clauses)))
        if algebraic
        else 0
    )
    profile = ConstraintFieldProfile(
        max_variables=compiled.variables,
        max_clauses=max(1, len(compiled.clauses) + max_augmentations),
        max_transitions=transition_budget,
        max_learned_clauses=64,
        mode=mode,
        controller=False,
        controller_size=8,
        max_hybrid_lines=(
            max(1, min(4096, len(compiled.clauses) * 4 + 16))
            if algebraic
            else 1
        ),
        max_hybrid_transitions=transition_budget,
        max_parity_width=min(8, max(3, compiled.variables)),
        max_resolution_inferences=2048,
        max_augmentations=max_augmentations,
        max_augmentation_arity=2 if algebraic else 1,
    )
    field = ConstraintField(profile)
    state = field.initial(compiled)
    transitions = 0
    while field.status(state) == "running":
        state, _ = field.step(state)
        transitions += 1
        if transitions > transition_budget:
            raise RedesignError("constraint regime exceeded its transition bound")
    result = field.result(state)
    audit = audit_constraint_result(compiled, result)
    certificate = None
    if result["status"] == "unsat":
        if result.get("resolution_proof") is not None:
            certificate = {
                "kind": "resolution",
                "backend_clauses": result["backend_clauses"],
                "learned_clauses": result["learned_clauses"],
                "proof": result["resolution_proof"],
            }
        elif result.get("hybrid_proof") is not None:
            certificate = {
                "kind": "hybrid",
                "proof": result["hybrid_proof"],
            }
        else:
            raise RedesignError("UNSAT regime returned no certificate")
    return {
        "mode": mode,
        "compiled_problem_sha256": compiled.sha256,
        "compiled_variables": compiled.variables,
        "compiled_clauses": len(compiled.clauses),
        "status": result["status"],
        "reason": result["reason"],
        "witness": result.get("witness"),
        "certificate": certificate,
        "audit": audit,
        "work": result["work"],
        "field_transitions": transitions,
    }


def _method_regime(method: str) -> str:
    return "algebraic" if method.startswith("algebraic") else "conflict"


def _stable_policy_observation(
    family: str,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    context = receipt["context"]
    return {
        "family": family,
        "method": receipt["method"],
        "source_sha256": receipt["source_sha256"],
        "context_key": context["context_key"],
        "structural_context_key": context["structural_context_key"],
        "status": receipt["status"],
        "reason": receipt["reason"],
        "budget_used": receipt["budget_used"],
        "audit_status": receipt["audit"]["status"],
    }


def _learn_reasoning_regimes(
    task: Mapping[str, Any],
    *,
    budget: int = 256,
) -> dict[str, Any]:
    """Train the exact policy field, then select on source-distinct holdouts."""

    sources = task["sources"]
    policy = initial_policy()
    training: list[dict[str, Any]] = []
    for family in ("sat", "unsat"):
        source = sources[f"{family}_training"]
        for method in COMPUTATION_METHODS:
            policy, receipt = solve_and_learn(
                policy,
                source,
                budget=budget,
                learn=True,
                method=method,
            )
            training.append(_stable_policy_observation(family, receipt))
    held_out: dict[str, Any] = {}
    for family in ("sat", "unsat"):
        training_source = compile_constraint_source(
            sources[f"{family}_training"]
        )
        source = sources[f"{family}_held_out"]
        compiled = compile_constraint_source(source)
        training_context = {
            row["context_key"]
            for row in training
            if row["family"] == family
        }
        trained_method, trained_selection = select_method(
            policy,
            compiled,
            budget=budget,
            explore=False,
        )
        fresh_method, fresh_selection = select_method(
            initial_policy(),
            compiled,
            budget=budget,
            explore=False,
        )
        if training_context != {trained_selection["evidence_context_key"]}:
            raise RedesignError(
                f"{family} heldout context did not inherit training evidence"
            )
        local = _run_constraint_regime(source, "local")
        trained_regime = _method_regime(trained_method)
        fresh_regime = _method_regime(fresh_method)
        if local["status"] in {"sat", "unsat"}:
            selected_regime = "local"
            selected_execution = local
            selection_reason = "local-propagation-completed"
        else:
            selected_regime = trained_regime
            selected_execution = _run_constraint_regime(
                source,
                selected_regime,
            )
            selection_reason = "learned-exact-policy-after-local-stall"
        fresh_execution = (
            local
            if local["status"] in {"sat", "unsat"}
            else _run_constraint_regime(source, fresh_regime)
        )
        held_out[family] = {
            "source_sha256": compiled.sha256,
            "training_source_sha256": training_source.sha256,
            "local_screen": local,
            "trained_regime": trained_regime,
            "trained_selection_phase": trained_selection["phase"],
            "trained_evidence_context_key": trained_selection[
                "evidence_context_key"
            ],
            "fresh_regime": fresh_regime,
            "fresh_selection_phase": fresh_selection["phase"],
            "selected_regime": selected_regime,
            "selection_reason": selection_reason,
            "selected_execution": selected_execution,
            "fresh_execution": fresh_execution,
        }
    sat = held_out["sat"]
    unsat = held_out["unsat"]
    if (
        sat["selected_regime"] != "local"
        or sat["selected_execution"]["status"] != "sat"
        or unsat["local_screen"]["status"] != "exhausted"
        or unsat["trained_regime"] != "algebraic"
        or unsat["fresh_regime"] != "conflict"
        or unsat["selected_execution"]["status"] != "unsat"
        or unsat["selected_execution"]["certificate"] is None
    ):
        raise RedesignError("paired reasoning regimes did not separate")
    trained_work = int(
        unsat["selected_execution"]["field_transitions"]
    )
    fresh_work = int(unsat["fresh_execution"]["field_transitions"])
    if trained_work >= fresh_work:
        raise RedesignError(
            "learned UNSAT regime did not reduce field transitions"
        )
    return {
        "budget": budget,
        "training": training,
        "held_out": held_out,
        "unsat_field_transition_saving": fresh_work - trained_work,
    }
def _measure_question_preflight(
    parent_files: Mapping[str, str],
    parent_digest: str,
    option: Mapping[str, Any],
    work_root: Path,
) -> dict[str, Any]:
    """Measure one deterministic representative before question admission."""
    rows = _compile_question_documents(parent_files, parent_digest, option)
    hypothesis = rows[0]
    candidate = synthesize_workspace(
        parent_files,
        ArchitectureIR.from_dict(hypothesis["architecture"]),
    )
    work_dir = work_root / f"preflight-{option['compiler_family']}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    _write_workspace(work_dir, candidate.files)
    try:
        measurement = _measure_candidate(work_dir, hypothesis)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return {
        "question_id": option["question_id"],
        "compiler_family": option["compiler_family"],
        "status": measurement["assessments"]["status"],
        "prediction_error": measurement["assessments"]["prediction_error"],
        "resource_metric": float(len(candidate.files)),
        "candidate_id": hypothesis["hypothesis_id"],
        "candidate_source_digest": candidate.source_digest,
        "measurement": measurement["metric_vector"],
    }



def _holdout_code() -> str:
    return "import sys;sys.path.insert(0,'src');from api import execute;assert execute(2)==3;print('holdout-ok')"


def _baseline_code() -> str:
    return "import sys;sys.path.insert(0,'src');import api,core_math;assert callable(api.execute);assert callable(core_math.increment);print('baseline-ok')"


def _measure_candidate(candidate_root: Path, hypothesis: Mapping[str, Any]) -> dict[str, Any]:
    baseline = run_bounded_command([sys.executable, "-c", _baseline_code()], workspace=candidate_root, timeout_seconds=5)
    holdout = run_bounded_command([sys.executable, "-c", _holdout_code()], workspace=candidate_root, timeout_seconds=5)
    expected = hypothesis["expected_holdout"]
    holdout_error = 0.0 if holdout["returncode"] == 0 else 1.0
    baseline_error = 0.0 if baseline["returncode"] == 0 else 1.0
    error = baseline_error + holdout_error
    return {
        "metric_vector": {"baseline_returncode": baseline["returncode"], "holdout_returncode": holdout["returncode"], "baseline_error": baseline_error, "holdout_error": holdout_error, "prediction_error": error},
        "prediction": {"expected": {"baseline_returncode": 0, "holdout_returncode": 0, **expected}, "observed": {"baseline_returncode": baseline["returncode"], "holdout_returncode": holdout["returncode"]}},
        "assessments": {"status": "PASS" if error == 0 else "MISS", "prediction_error": error, "baseline_preserved": baseline["returncode"] == 0, "holdout_passed": holdout["returncode"] == 0},
        "commands": {"baseline": baseline, "holdout": holdout},
    }


def _generation_path(home: Path, generation: int) -> Path:
    return home / "generations" / f"g{generation:04d}"


def _pointer(home: Path) -> Path:
    return home / "current.json"


def _commit_generation(home: Path, generation: int, receipt: Mapping[str, Any], candidate_files: Mapping[str, Mapping[str, str]], state: Mapping[str, Any]) -> None:
    directory = _generation_path(home, generation)
    if directory.exists():
        old = _read(directory / "receipt.json")
        if old.get("content_sha256") != receipt.get("content_sha256"):
            raise MutationRejected("immutable generation already exists")
        return
    temporary = home / "generations" / f".g{generation:04d}.tmp-{os.getpid()}"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        _atomic_json(temporary / "state.json", state)
        _atomic_json(temporary / "receipt.json", receipt)
        for candidate_id, files in candidate_files.items():
            _write_workspace(temporary / "candidates" / candidate_id, files)
        os.replace(temporary, directory)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    pointer_body = {"schema": POINTER_SCHEMA, "generation": generation, "receipt_sha256": receipt["content_sha256"], "state_sha256": digest(state)}
    pointer = {**pointer_body, "pointer_sha256": digest(pointer_body)}
    _atomic_json(_pointer(home), pointer)
    promotion_body = {"schema": "cassimindfield.promotion-pointer.v1", "generation": generation, "candidate_id": receipt.get("selected_candidate_id"), "receipt_sha256": receipt["content_sha256"]}
    _atomic_json(home / "promotion.json", {**promotion_body, "pointer_sha256": digest(promotion_body)})


def _load_current(home: Path) -> tuple[int, dict[str, Any], dict[str, Any]]:
    pointer = _read(_pointer(home))
    _check(pointer, "pointer_sha256", {key: value for key, value in pointer.items() if key != "pointer_sha256"})
    generation = pointer.get("generation")
    if not isinstance(generation, int) or generation < 0:
        raise MutationRejected("invalid redesign current generation")
    directory = _generation_path(home, generation)
    state = _read(directory / "state.json")
    receipt = _read(directory / "receipt.json")
    _check(receipt, "content_sha256", _stable_receipt(receipt))
    receipt_continuity = receipt.get("responsibility_continuity")
    if receipt_continuity is not None:
        if not isinstance(receipt_continuity, Mapping):
            raise MutationRejected("receipt responsibility continuity is invalid")
        _validate_responsibility_continuity_evidence(receipt_continuity)
    if pointer.get("receipt_sha256") != receipt.get("content_sha256") or pointer.get("state_sha256") != digest(state):
        raise MutationRejected("promotion pointer does not match generation")
    promotion = _read(home / "promotion.json")
    _check(promotion, "pointer_sha256", {key: value for key, value in promotion.items() if key != "pointer_sha256"})
    if promotion.get("generation") != generation or promotion.get("receipt_sha256") != receipt.get("content_sha256"):
        raise MutationRejected("promotion pointer diverged")
    pointer_continuity = pointer.get("responsibility_continuity")
    pointer_continuity_sha256 = pointer.get("responsibility_continuity_sha256")
    if pointer_continuity is not None:
        if (
            not isinstance(pointer_continuity, Mapping)
            or pointer_continuity.get("schema") != RESPONSIBILITY_CONTINUITY_SCHEMA
            or pointer_continuity_sha256 != digest(pointer_continuity)
        ):
            raise MutationRejected("rollback responsibility pointer evidence diverged")
        if promotion.get("responsibility_continuity_sha256") != pointer_continuity_sha256:
            raise MutationRejected("promotion responsibility pointer diverged")
        _validate_responsibility_continuity_evidence(pointer_continuity)
        receipt = dict(receipt)
        receipt["responsibility_continuity"] = pointer_continuity
    elif pointer_continuity_sha256 is not None or promotion.get("responsibility_continuity_sha256") is not None:
        raise MutationRejected("rollback responsibility pointer is incomplete")
    return generation, state, receipt
def _promoted_parent_workspace(
    home: Path,
    generation: int,
    state: Mapping[str, Any],
) -> dict[str, str]:
    if generation == 0:
        parent_root = _generation_path(home, 0) / "candidates" / "predecessor"
    else:
        selected = state.get("selected_candidate_id")
        if not isinstance(selected, str) or not selected:
            raise MutationRejected("current redesign state has no promoted candidate")
        parent_root = _generation_path(home, generation) / "candidates" / selected
    files = _read_parent_files(parent_root)
    actual_digest = workspace_digest(files)
    if actual_digest != state.get("workspace_digest"):
        raise MutationRejected("promoted parent workspace digest diverged from state")
    return files




def _make_receipt(
    generation: int,
    parent_receipt: Mapping[str, Any] | None,
    candidates: Sequence[Mapping[str, Any]],
    selected: str | None,
    migration: Mapping[str, Any] | None,
    field_selection: Mapping[str, Any] | None = None,
    field_question: Mapping[str, Any] | None = None,
    assessment_history: Mapping[str, Any] | None = None,
    responsibility_continuity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selection = None if field_selection is None else dict(field_selection)
    question = None if field_question is None else dict(field_question)
    history = None if assessment_history is None else dict(assessment_history)
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "runtime_schema": SCHEMA,
        "generation": generation,
        "parent_generation": None if parent_receipt is None else parent_receipt.get("generation"),
        "parent_receipt_sha256": None if parent_receipt is None else parent_receipt.get("content_sha256"),
        "candidates": list(candidates),
        "selected_candidate_id": selected,
        "field_selection": selection,
        "field_question": question,
        "field_assessment_history": history,
        "responsibility_continuity": (
            None if responsibility_continuity is None else dict(responsibility_continuity)
        ),
        "field_operation_ids": [] if selection is None else list(selection.get("operation_ids", [])),
        "field_record_refs": [] if selection is None else list(selection.get("record_refs", [])),
        "field_state_sha256": None if selection is None else selection.get("field_state_out_sha256"),
        "field_state_migration": migration,
    }
    receipt["content_sha256"] = digest(receipt)
    return receipt
def _bootstrap(home: Path, parent_files: Mapping[str, str], parent_digest: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    if _pointer(home).exists():
        return
    source_index = {"source_digest": parent_digest, "files": sorted(parent_files)}
    state = {"schema": "cassimindfield.redesign-state.v1", "generation": 0, "workspace_digest": parent_digest, "agenda_role": "receipt-only; candidate selection is field-owned", "source_index": source_index}
    receipt = _make_receipt(0, None, [], None, None)
    _commit_generation(home, 0, receipt, {"predecessor": parent_files}, state)


def _recover_field_question(
    memory: CassiFieldWorkMemory,
    agenda_result: Mapping[str, Any],
    *,
    operation_id: str,
) -> tuple[dict[str, Any], dict[str, Any], Mapping[str, Any], dict[str, Any]]:
    """Recover the field-returned research question by querying its resident record."""
    agenda_items = agenda_result.get("agenda", [])
    selected_item = agenda_result.get("selected")
    if not isinstance(agenda_items, list) or not agenda_items:
        raise RedesignError("field autonomous agenda returned no resident question options")
    if not isinstance(selected_item, Mapping):
        raise RedesignError("field autonomous agenda abstained: selected question is absent")
    selected_digest = digest(selected_item)
    selected_rank = next(
        (
            index
            for index, item in enumerate(agenda_items)
            if isinstance(item, Mapping) and digest(item) == selected_digest
        ),
        None,
    )
    if selected_rank is None:
        raise RedesignError("field autonomous agenda selected an item absent from its ordered agenda")
    if (
        selected_item.get("kind") != "resolve-obligation"
        or not isinstance(selected_item.get("obligation"), Mapping)
        or not str(selected_item["obligation"].get("id", "")).startswith("redesign-question:")
    ):
        raise RedesignError("field autonomous agenda selected a non-question obligation")
    question_ref = dict(selected_item["obligation"])
    query_operation_id = f"{operation_id}:question-record"
    query_request = {
        "operation": "query",
        "operation_id": query_operation_id,
        "query": {"kind": "record", "reference": question_ref},
    }
    query_response = memory.semantic(query_request, operation_label=query_operation_id)
    query_result = query_response.get("result", {})
    record = query_result.get("record") if isinstance(query_result, Mapping) else None
    if query_result.get("status") != "supported" or not isinstance(record, Mapping):
        raise RedesignError("field autonomous agenda selected an unavailable research question")
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        raise RedesignError("field research question record has no payload")
    question = dict(payload)
    question["question_id"] = str(question.get("question_id") or question_ref["id"])
    query_metadata = dict(query_response)
    query_metadata["_request_sha256"] = digest(query_request)
    query_metadata["_response_sha256"] = digest(query_response)
    query_metadata["_record_sha256"] = digest(record)
    query_metadata["_selected_rank"] = selected_rank
    return question, question_ref, query_metadata, dict(selected_item)
def _assessment_history_ref(compiler_family: str) -> dict[str, str]:
    return {
        "id": f"redesign-assessment-history:{compiler_family}",
        "kind": "Assessment",
    }
def _typed_assessment_history_ref(
    memory: CassiFieldWorkMemory,
    compiler_family: str,
) -> dict[str, Any] | None:
    """Return the current typed semantic reference, if resident history exists."""
    inspected = memory._computer_inspect()
    task = inspected.get("task") if isinstance(inspected, Mapping) else None
    current = task.get("current", {}) if isinstance(task, Mapping) else {}
    assessments = current.get("Assessment", {}) if isinstance(current, Mapping) else {}
    raw = assessments.get(f"redesign-assessment-history:{compiler_family}")
    return dict(raw) if isinstance(raw, Mapping) else None



def _query_assessment_history(
    memory: CassiFieldWorkMemory,
    question_options: Sequence[Mapping[str, Any]],
    *,
    target_generation: int,
) -> dict[str, Any]:
    """Read family assessment summaries from the resident semantic field."""
    histories: dict[str, dict[str, Any]] = {}
    query_rows: list[dict[str, Any]] = []
    operation_ids: list[str] = []
    history_record_refs: list[dict[str, Any]] = []
    for option in question_options:
        compiler_family = str(option["compiler_family"])
        reference = _typed_assessment_history_ref(memory, compiler_family)
        operation_id = (
            f"redesign:assessment-history-query:{target_generation}:"
            f"{compiler_family}"
        )
        request = {
            "operation": "query",
            "operation_id": operation_id,
            "query": {"kind": "record", "reference": reference},
        }
        if reference is None:
            query_rows.append(
                {
                    "compiler_family": compiler_family,
                    "reference": None,
                    "operation_id": operation_id,
                    "request_sha256": digest(request),
                    "response_sha256": None,
                    "record_sha256": None,
                    "status": "support-gap",
                    "limitation": "assessment-history-record-absent",
                    "field_state_sha256": memory.regional_field_receipt()[
                        "field_state_sha256"
                    ],
                }
            )
            operation_ids.append(operation_id)
            continue
        response = memory.semantic(request, operation_label=operation_id)
        result = response.get("result", {})
        record = result.get("record") if isinstance(result, Mapping) else None
        payload = record.get("payload") if isinstance(record, Mapping) else None
        if (
            result.get("status") == "supported"
            and isinstance(record, Mapping)
            and isinstance(payload, Mapping)
            and payload.get("purpose") == "assessment-history"
            and payload.get("state") == "resolved"
            and payload.get("compiler_family") == compiler_family
        ):
            histories[compiler_family] = dict(payload)
            history_record_refs.append(reference)
        query_rows.append(
            {
                "compiler_family": compiler_family,
                "reference": reference,
                "operation_id": operation_id,
                "request_sha256": digest(request),
                "response_sha256": digest(response),
                "record_sha256": (
                    digest(record) if isinstance(record, Mapping) else None
                ),
                "status": result.get("status"),
                "field_state_sha256": response.get("field_state_sha256"),
            }
        )
        operation_ids.append(operation_id)
    return {
        "histories": histories,
        "queries": query_rows,
        "operation_ids": operation_ids,
        "history_record_refs": history_record_refs,
        "history_present": bool(histories),
    }


def _summarize_question_history(
    question_options: Sequence[Mapping[str, Any]],
    history: Mapping[str, Any],
) -> dict[str, Any]:
    """Prepare resident evidence for the field learning selector."""
    histories = history.get("histories", {})
    histories = histories if isinstance(histories, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for option in question_options:
        family = str(option["compiler_family"])
        prior = histories.get(family)
        rows.append(
            {
                "question_id": str(option["question_id"]),
                "compiler_family": family,
                "attempts": int(prior.get("attempts", 0)) if isinstance(prior, Mapping) else 0,
                "passes": int(prior.get("passes", 0)) if isinstance(prior, Mapping) else 0,
                "misses": int(prior.get("misses", 0)) if isinstance(prior, Mapping) else 0,
                "history_present": isinstance(prior, Mapping),
            }
        )
    return {
        "mode": "resident-history" if history.get("history_present") else "fresh-baseline",
        "decision": (
            "field-history-select-resident-assessment"
            if history.get("history_present")
            else "baseline-equal-priority-no-assessment-history"
        ),
        "priorities": rows,
        "selected_family": None,
    }




def _record_assessment_history(
    memory: CassiFieldWorkMemory,
    *,
    target_generation: int,
    question: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    prior_history: Mapping[str, Any],
) -> dict[str, Any]:
    """Append the latest bounded family outcome to a resident field record."""
    family = str(question["compiler_family"])
    prior = prior_history.get("histories", {})
    prior_row = prior.get(family) if isinstance(prior, Mapping) else None
    prior_attempts = int(prior_row.get("attempts", 0)) if isinstance(prior_row, Mapping) else 0
    prior_passes = int(prior_row.get("passes", 0)) if isinstance(prior_row, Mapping) else 0
    prior_misses = int(prior_row.get("misses", 0)) if isinstance(prior_row, Mapping) else 0
    passes = sum(
        1
        for candidate in candidates
        if candidate.get("measurement", {}).get("assessments", {}).get("status")
        == "PASS"
    )
    misses = len(candidates) - passes
    payload = {
        "purpose": "assessment-history",
        "state": "resolved",
        "question_id": question.get("question_id"),
        "compiler_family": family,
        "attempts": prior_attempts + len(candidates),
        "passes": prior_passes + passes,
        "misses": prior_misses + misses,
        "last_generation": target_generation,
        "last_candidate_ids": [str(candidate["candidate_id"]) for candidate in candidates],
        "last_assessment_digest": digest(
            [
                candidate.get("measurement", {}).get("assessments", {})
                for candidate in candidates
            ]
        ),
    }
    operation_id = f"redesign:assessment-history:{target_generation}:{family}"
    response = memory.semantic(
        {
            "operation": "register",
            "operation_id": operation_id,
            "record_id": _assessment_history_ref(family)["id"],
            "kind": "Assessment",
            "payload": payload,
            "epistemic_kind": "observed",
        },
        operation_label=operation_id,
    )
    record = response.get("result", {}).get("record")
    record_ref = (
        _typed_assessment_history_ref(memory, family)
        or _assessment_history_ref(family)
    )
    return {
        "compiler_family": family,
        "operation_id": operation_id,
        "record_ref": record_ref,
        "record": record,
        "record_sha256": digest(record) if isinstance(record, Mapping) else None,
        "payload": payload,
        "field_state_sha256": response.get("field_state_sha256"),
    }
def _seed_missing_assessment_history(
    memory: CassiFieldWorkMemory,
    *,
    target_generation: int,
    question_options: Sequence[Mapping[str, Any]],
    preflight_rows: Sequence[Mapping[str, Any]],
    existing_families: set[str],
) -> list[dict[str, Any]]:
    """Admit measured preflight evidence for families not yet attempted.

    The first cycle still uses a fresh-field baseline selector.  After that
    cycle, the representative preflight measurements make every competing
    family visible to the resident history selector without test-side
    seeding.  A later cycle never overwrites an existing history record here;
    the selected family's full candidate measurements are appended by
    ``_record_assessment_history`` instead.
    """
    by_family = {
        str(row.get("compiler_family")): row
        for row in preflight_rows
        if isinstance(row, Mapping) and row.get("compiler_family")
    }
    seeded: list[dict[str, Any]] = []
    for option in question_options:
        family = str(option["compiler_family"])
        if family in existing_families:
            continue
        row = by_family.get(family)
        if not isinstance(row, Mapping):
            raise RedesignError(
                f"missing preflight evidence for assessment-history family: {family}"
            )
        raw_record = row.get("record")
        if not isinstance(raw_record, Mapping):
            raise RedesignError(
                f"preflight evidence has no resident record: {family}"
            )
        record_ref = {
            key: raw_record[key]
            for key in ("id", "kind", "content_version")
            if key in raw_record
        }
        if set(record_ref) != {"id", "kind", "content_version"}:
            raise RedesignError(
                f"preflight resident record reference is incomplete: {family}"
            )
        status = str(row.get("status"))
        passes = 1 if status == "PASS" else 0
        misses = 1 - passes
        operation_id = (
            f"redesign:assessment-history-bootstrap:{target_generation}:{family}"
        )
        payload = {
            "purpose": "assessment-history",
            "state": "resolved",
            "question_id": option.get("question_id"),
            "compiler_family": family,
            "attempts": 1,
            "passes": passes,
            "misses": misses,
            "last_generation": target_generation,
            "last_candidate_ids": [str(row.get("candidate_id"))],
            "last_assessment_digest": digest(row.get("measurement", {})),
            "origin": "question-preflight",
            "preflight_record_ref": dict(record_ref),
        }
        response = memory.semantic(
            {
                "operation": "register",
                "operation_id": operation_id,
                "record_id": _assessment_history_ref(family)["id"],
                "kind": "Assessment",
                "payload": payload,
                "dependencies": [record_ref],
                "epistemic_kind": "observed",
            },
            operation_label=operation_id,
        )
        record = response.get("result", {}).get("record")
        if not isinstance(record, Mapping):
            raise RedesignError(
                f"preflight assessment-history admission returned no record: {family}"
            )
        current_ref = _typed_assessment_history_ref(memory, family)
        if current_ref is None:
            current_ref = _assessment_history_ref(family)
        seeded.append(
            {
                "compiler_family": family,
                "operation_id": operation_id,
                "record_ref": dict(current_ref),
                "record": dict(record),
                "payload": payload,
                "preflight_record_ref": dict(record_ref),
                "field_state_sha256": response.get("field_state_sha256"),
            }
        )
        existing_families.add(family)
    return seeded


def _resident_assessment_history_refs(
    memory: CassiFieldWorkMemory,
    question_options: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for option in question_options:
        family = str(option["compiler_family"])
        reference = _typed_assessment_history_ref(memory, family)
        if reference is not None:
            refs.append(dict(reference))
    return refs


def _history_trajectory(
    *,
    generation: int,
    question: Mapping[str, Any],
    prior_history: Mapping[str, Any],
    seeded_history_records: Sequence[Mapping[str, Any]],
    resident_history_record_refs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    histories = prior_history.get("histories", {})
    prior_families = (
        sorted(str(family) for family in histories)
        if isinstance(histories, Mapping)
        else []
    )
    return {
        "schema": "cassimindfield.history-trajectory.v1",
        "generation": generation,
        "selected_family": str(question.get("compiler_family")),
        "prior_history_families": prior_families,
        "seeded_families": sorted(
            str(row.get("compiler_family"))
            for row in seeded_history_records
            if isinstance(row, Mapping) and row.get("compiler_family")
        ),
        "resident_history_families_after": sorted(
            str(reference.get("id", "")).removeprefix(
                "redesign-assessment-history:"
            )
            for reference in resident_history_record_refs
        ),
        "selection_is_field_owned": True,
        "trajectory_rule": (
            "measured preflight evidence opens unseen families; "
            "subsequent field history scores the next family"
        ),
    }




def _close_prior_candidate_obligations(
    memory: CassiFieldWorkMemory,
    *,
    target_generation: int,
) -> list[str]:
    """Close unresolved candidate work from prior explicit research cycles."""
    state = getattr(getattr(memory, "owner", None), "state", None)
    current = getattr(state, "current", {}) if state is not None else {}
    obligations = current.get("Obligation", {}) if isinstance(current, Mapping) else {}
    closed: list[str] = []
    for record_id in sorted(obligations) if isinstance(obligations, Mapping) else ():
        record_id = str(record_id)
        if not record_id.startswith("redesign-obligation:"):
            continue
        operation_id = f"redesign:close-obligation:{target_generation}:{record_id}"
        memory.semantic(
            {
                "operation": "register",
                "operation_id": operation_id,
                "record_id": record_id,
                "kind": "Obligation",
                "status": "resolved",
                "epistemic_kind": "derived",
                "payload": {
                    "purpose": "prior-cycle-candidate",
                    "state": "resolved",
                    "candidate_id": record_id.removeprefix("redesign-obligation:"),
                    "resolution": "explicit-research-cycle-advanced",
                },
            },
            operation_label=operation_id,
        )
        closed.append(operation_id)
    return closed





def _run_campaign(
    data_home: str | os.PathLike[str],
    *,
    research_cycle: bool = False,
    responsibility_snapshot: Mapping[str, Any] | str | os.PathLike[str],
) -> dict[str, Any]:
    loaded_snapshot = _load_responsibility_snapshot(responsibility_snapshot)
    if loaded_snapshot is None:
        raise MutationRejected("a field-owner snapshot is required for every rewrite")
    responsibility_snapshot = loaded_snapshot
    home = Path(data_home).resolve()
    seed_files, _ = build_example()
    seed_digest = workspace_digest(seed_files)
    _bootstrap(home, seed_files, seed_digest)
    generation, state, previous_receipt = _load_current(home)
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    existing_generations = [
        int(path.name[1:])
        for path in (home / "generations").glob("g*")
        if path.name[1:].isdigit()
    ]
    target_generation = max(existing_generations, default=generation) + 1
    if generation >= 1 and not research_cycle:
        return {
            "status": "RESTARTED",
            "generation": generation,
            "receipt": _read(_generation_path(home, generation) / "receipt.json"),
            "responsibility_continuity": _check_responsibility_snapshot(
                previous_receipt, responsibility_snapshot
            ),
            "replay": _replay_campaign(
                home, responsibility_snapshot=responsibility_snapshot
            ),
        }
    responsibility_evidence = _responsibility_campaign_evidence(
        previous_receipt, responsibility_snapshot
    )


    field_home = home / "field"
    candidates: list[dict[str, Any]] = []
    candidate_files: dict[str, Mapping[str, str]] = {}
    research_space = _architecture_research_space(
        parent_files,
        parent_digest,
        cycle=target_generation if research_cycle else 1,
    )
    question_options = research_space.get("question_options")
    if (
        not isinstance(question_options, list)
        or len(question_options) < 3
        or any(not isinstance(option, Mapping) for option in question_options)
    ):
        raise RedesignError("field research space must contain competing question options")
    research_operation_id = f"redesign:research-space:{target_generation}:{parent_digest[:24]}"
    with CassiFieldWorkMemory(field_home) as memory:
        field_input = memory.regional_field_receipt()
        research_event_refs: list[dict[str, Any]] = []
        source_obligation_refs: list[dict[str, Any]] = []
        question_source_refs: dict[str, dict[str, dict[str, Any]]] = {}
        research_operation_ids: list[str] = []
        assessment_history = _query_assessment_history(
            memory,
            question_options,
            target_generation=target_generation,
        )
        question_history = _summarize_question_history(
            question_options,
            assessment_history,
        )
        prior_obligation_close_operation_ids = _close_prior_candidate_obligations(
            memory,
            target_generation=target_generation,
        ) if research_cycle else []
        preflight_rows: list[dict[str, Any]] = []
        preflight_operation_ids: list[str] = []
        for option in question_options:
            preflight = _measure_question_preflight(
                parent_files,
                parent_digest,
                option,
                home / "_preflight-work",
            )
            preflight_operation_id = (
                f"redesign:preflight-assessment:{target_generation}:"
                f"{option['compiler_family']}"
            )
            preflight_response = memory.semantic(
                {
                    "operation": "register",
                    "operation_id": preflight_operation_id,
                    "record_id": (
                        f"redesign-preflight-assessment:{target_generation}:"
                        f"{option['compiler_family']}"
                    ),
                    "kind": "Assessment",
                    "epistemic_kind": "observed",
                    "payload": {
                        **preflight,
                        "purpose": "architecture-question-preflight",
                        "state": "resolved",
                    },
                },
                operation_label=preflight_operation_id,
            )
            preflight_record = preflight_response.get("result", {}).get("record")
            preflight_rows.append(
                {
                    **preflight,
                    "operation_id": preflight_operation_id,
                    "record": preflight_record,
                    "record_sha256": (
                        digest(preflight_record)
                        if isinstance(preflight_record, Mapping)
                        else None
                    ),
                    "field_state_sha256": preflight_response.get(
                        "field_state_sha256"
                    ),
                }
            )
            preflight_operation_ids.append(preflight_operation_id)
        procedure_learning: dict[str, Any] | None = None
        procedure_application: dict[str, Any] | None = None
        if target_generation == 1:
            successful_preflights = [
                row for row in preflight_rows if row.get("status") == "PASS"
            ]
            if len(successful_preflights) < 3:
                raise RedesignError(
                    "procedure learning requires three successful executed preflights"
                )
            procedure_traces = [
                _investigation_trace(
                    compiler_family=str(row["compiler_family"]),
                    candidate_id=str(row["candidate_id"]),
                    assessment_operation_id=str(row["operation_id"]),
                    status=str(row["status"]),
                )
                for row in successful_preflights[:3]
            ]
            procedure_operation_id = (
                f"redesign:learn-procedure:{target_generation}:{parent_digest[:24]}"
            )
            procedure_response = memory.semantic(
                {
                    "operation": "learn-procedure",
                    "operation_id": procedure_operation_id,
                    "procedure_id": INVESTIGATION_PROCEDURE_ID,
                    "traces": procedure_traces[:2],
                    "holdout": procedure_traces[2:],
                },
                operation_label=procedure_operation_id,
            )
            procedure_result = procedure_response.get("result", {})
            procedure_candidates = (
                procedure_result.get("candidates", [])
                if isinstance(procedure_result, Mapping)
                else []
            )
            best = procedure_candidates[0] if procedure_candidates else None
            measured_cost = (
                best.get("measured_cost", {})
                if isinstance(best, Mapping)
                else {}
            )
            if (
                not isinstance(procedure_result, Mapping)
                or procedure_result.get("status") != "supported"
                or not isinstance(procedure_result.get("procedure"), Mapping)
                or not isinstance(measured_cost, Mapping)
                or int(measured_cost.get("net_saved_steps", 0)) <= 0
            ):
                raise RedesignError(
                    "executed investigation trajectories did not yield a useful procedure"
                )
            procedure_learning = {
                "operation_id": procedure_operation_id,
                "procedure": dict(procedure_result["procedure"]),
                "status": procedure_result["status"],
                "selected_candidate": procedure_result.get("selected_candidate"),
                "measured_cost": dict(measured_cost),
                "training_preflight_operation_ids": [
                    str(row["operation_id"]) for row in successful_preflights[:2]
                ],
                "holdout_preflight_operation_ids": [
                    str(row["operation_id"]) for row in successful_preflights[2:3]
                ],
                "field_state_sha256": procedure_response.get("field_state_sha256"),
            }
        question_selector = None
        selected_learning_family = None
        priority_by_question = {
            row["question_id"]: row for row in question_history["priorities"]
        }

        for option_index, option in enumerate(question_options):
            option_operation_id = f"{research_operation_id}:{option_index}"
            research_operation_ids.append(option_operation_id)
            research_event_id = (
                f"redesign:research-event:{target_generation}:"
                f"{parent_digest[:24]}:{option_index}"
            )
            research_observation = memory.semantic(
                {
                    "operation": "observe",
                    "operation_id": option_operation_id,
                    "delivery_id": option_operation_id,
                    "event_id": research_event_id,
                    "frame": "cassimindfield-redesign-v1",
                    "observations": [
                        {
                            "subject": f"architecture-research-space:{option['question_id']}",
                            "attribute": "bounded-compiler-catalog",
                            "value": dict(option),
                            "epistemic_kind": "observed",
                        }
                    ],
                    "obligations": [
                        {
                            "obligation_id": f"redesign-question:{option['question_id']}",
                            "purpose": (
                                (
                                    "prediction architecture-research-question-learning"
                                    if selected_learning_family
                                    == str(option["compiler_family"])
                                    else "candidate-exploration architecture-research-question-learning"
                                )
                                if question_selector is not None
                                else "architecture-research-question-baseline"
                            ),
                            "state": "pending",
                            "priority": 1.0,
                            "question_id": option["question_id"],
                            "question": option["question"],
                            "compiler_family": option["compiler_family"],
                            "variant_catalog": option["variant_catalog"],
                            "source_event_id": research_event_id,
                            "parent_source_digest": parent_digest,
                            "history_mode": question_history["mode"],
                            "history_decision": question_history["decision"],
                            "learning_selector_operation_id": (
                                question_selector["operation_id"]
                                if question_selector is not None
                                else None
                            ),
                        }
                    ],
                    "receipt": {
                        "clock_domain": "redesign-logical",
                        "time": float(target_generation),
                        "uncertainty": 0.0,
                    },
                    "source": {
                        "kind": "architecture-research-space",
                        "question_id": option["question_id"],
                        "source_revision": parent_digest,
                    },
                },
                operation_label=option_operation_id,
            )
            research_result = research_observation.get("result", {})
            event_ref = research_result.get("event")
            obligation_refs = research_result.get("obligations", [])
            if (
                not isinstance(event_ref, Mapping)
                or not isinstance(obligation_refs, list)
                or len(obligation_refs) != 1
                or not isinstance(obligation_refs[0], Mapping)
            ):
                raise RedesignError(
                    "field research-space observation did not admit its question"
                )
            research_event_refs.append(dict(event_ref))
            question_source_refs[str(option["question_id"])] = {
                "event": dict(event_ref),
                "obligation": dict(obligation_refs[0]),
            }
            source_obligation_refs.append(dict(obligation_refs[0]))
        if len(source_obligation_refs) < 2:
            raise RedesignError("field research-space observation did not admit competing questions")
        historical_source_obligation_refs = [
            dict(ref) for ref in source_obligation_refs
        ]
        history_selection_operation_id = (
            f"redesign:history-select:{target_generation}:"
            f"{memory.regional_field_receipt()['field_state_sha256'][:24]}"
        )
        history_selection_request = {
            "operation": "history-select",
            "operation_id": history_selection_operation_id,
            "candidates": [
                {
                    "candidate_id": str(option["compiler_family"]),
                    "reference": source_obligation_refs[index],
                }
                for index, option in enumerate(question_options)
            ],
            "evidence": {
                "purpose": "assessment-history",
                "references": assessment_history["history_record_refs"],
            },
        }
        history_selection_response = memory.semantic(
            history_selection_request,
            operation_label=history_selection_operation_id,
        )
        history_selection_result = history_selection_response.get("result", {})
        history_selected = (
            history_selection_result.get("selected")
            if isinstance(history_selection_result, Mapping)
            else None
        )
        selected_learning_family = (
            str(history_selected["candidate_id"])
            if isinstance(history_selected, Mapping)
            else None
        )
        question_selector = {
            "operation_id": history_selection_operation_id,
            "request": history_selection_request,
            "response": history_selection_response,
            "result": history_selection_result,
            "selected_family": selected_learning_family,
            "abstained": not isinstance(history_selected, Mapping),
            "candidate_scores": history_selection_result.get("scores", []),
            "field_state_sha256": history_selection_response.get("field_state_sha256"),
        }
        question_history["selected_family"] = selected_learning_family
        question_history["mode"] = (
            "resident-history"
            if isinstance(history_selected, Mapping)
            else "field-abstention-baseline"
        )
        question_history["decision"] = (
            "field-history-select-resident-assessment"
            if isinstance(history_selected, Mapping)
            else "field-history-select-abstained-bootstrap-baseline"
        )
        question_history["field_history_selector"] = {
            "operation_id": history_selection_operation_id,
            "request": history_selection_request,
            "event": history_selection_result.get("event"),
            "scores": history_selection_result.get("scores", []),
            "selected": history_selected,
            "abstained": not isinstance(history_selected, Mapping),
        }
        history_selection_event = history_selection_result.get("event")
        if not isinstance(history_selection_event, Mapping):
            raise RedesignError("field history selection returned no selection event")
        score_by_family = {
            str(row.get("compiler_family")): row.get("score")
            for row in history_selection_result.get("scores", [])
            if isinstance(row, Mapping)
        }
        history_evidence = history_selection_result.get("evidence", {})
        history_evidence_refs = (
            [
                dict(reference)
                for reference in history_evidence.get("references", [])
                if isinstance(reference, Mapping)
            ]
            if isinstance(history_evidence, Mapping)
            else []
        )
        current_source_obligation_refs: list[dict[str, Any]] = []
        for option, source_ref in zip(question_options, source_obligation_refs):
            family = str(option["compiler_family"])
            operation_id = f"redesign:history-priority:{target_generation}:{family}"
            selected = family == selected_learning_family
            updated_response = memory.semantic(
                {
                    "operation": "register",
                    "operation_id": operation_id,
                    "record_id": str(source_ref["id"]),
                    "kind": "Obligation",
                    "status": "active",
                    "epistemic_kind": "derived",
                    "dependencies": [
                        question_source_refs[str(option["question_id"])]["event"],
                        dict(history_selection_event),
                        *history_evidence_refs,
                    ],
                    "payload": {
                        "purpose": (
                            "prediction architecture-research-question-history"
                            if selected
                            else (
                                "candidate-exploration architecture-research-question-history"
                                if selected_learning_family is not None
                                else "architecture-research-question-bootstrap"
                            )
                        ),
                        "state": "pending",
                        "priority": 2.0 if selected else 1.0,
                        "question_id": option["question_id"],
                        "question": option["question"],
                        "compiler_family": family,
                        "variant_catalog": option["variant_catalog"],
                        "source_event_id": question_source_refs[
                            str(option["question_id"])
                        ]["event"]["id"],
                        "parent_source_digest": parent_digest,
                        "history_selection_operation_id": history_selection_operation_id,
                        "history_selection_event": dict(history_selection_event),
                        "history_score": score_by_family.get(family),
                        "history_mode": question_history["mode"],
                        "history_decision": question_history["decision"],
                    },
                },
                operation_label=operation_id,
            )
            updated_record = updated_response.get("result", {}).get("record")
            if not isinstance(updated_record, Mapping):
                raise RedesignError("history-priority obligation update returned no record")
            updated_ref = {
                key: updated_record[key]
                for key in ("id", "kind", "content_version")
            }
            current_source_obligation_refs.append(updated_ref)
            question_source_refs[str(option["question_id"])]["obligation"] = dict(
                updated_ref
            )
            research_operation_ids.append(operation_id)
        # v1 refs remain selector provenance; all agenda and question references
        # use the current v2 revisions.
        source_obligation_refs = current_source_obligation_refs
        bootstrap_state = memory.regional_field_receipt()
        bootstrap_agenda_id = (
            f"redesign:bootstrap-agenda:{target_generation}:"
            f"{bootstrap_state['field_state_sha256'][:24]}"
        )
        question_curiosity_operation_id = f"{bootstrap_agenda_id}:curiosity"
        question_curiosity_response = memory.semantic(
            {
                "operation": "autonomous-curiosity",
                "operation_id": question_curiosity_operation_id,
                "goal": {
                    "kind": "architecture-research-question",
                    "question_option_count": len(question_options),
                    "question_ids": [
                        str(option["question_id"]) for option in question_options
                    ],
                },
                "max_goals": MAX_CANDIDATES,
                "min_error": 0.0,
            },
            operation_label=question_curiosity_operation_id,
        )
        question_curiosity_result = question_curiosity_response.get("result", {})
        bootstrap_agenda_response = memory.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": bootstrap_agenda_id,
                "goal": {"kind": "architecture-redesign-bootstrap"},
                "max_items": MAX_CANDIDATES,
                "obligation_prefix": "redesign-question:",
            },
            operation_label=bootstrap_agenda_id,
        )
        bootstrap_result = bootstrap_agenda_response.get("result", {})
        question, selected_question_ref, question_query, selected_question_item = _recover_field_question(
            memory,
            bootstrap_result if isinstance(bootstrap_result, Mapping) else {},
            operation_id=bootstrap_agenda_id,
        )
        if question.get("parent_source_digest") != parent_digest:
            raise RedesignError("field research question source digest does not match predecessor")
        agenda = _compile_question_documents(parent_files, parent_digest, question)
        selected_source = question_source_refs.get(str(question.get("question_id")))
        if not isinstance(selected_source, Mapping):
            raise RedesignError("selected field question has no matching source references")
        source_event_ref = dict(selected_source["event"])
        source_obligation_ref = dict(selected_source["obligation"])
        if (
            selected_learning_family is not None
            and question.get("compiler_family") != selected_learning_family
        ):
            raise RedesignError(
                "field history-selected family was not selected by the question agenda"
            )
        if selected_question_ref != source_obligation_ref:
            raise RedesignError(
                "field question query did not return the current history-priority obligation"
            )
        if target_generation > 1:
            transfer_hypothesis = agenda[0]
            transfer_operation_id = (
                f"redesign:invoke-procedure:{target_generation}:{parent_digest[:24]}"
            )
            transfer_response = memory.semantic(
                {
                    "operation": "invoke-procedure",
                    "operation_id": transfer_operation_id,
                    "procedure_ref": {
                        "id": INVESTIGATION_PROCEDURE_ID,
                        "kind": "Program",
                        "content_version": 1,
                    },
                    "bindings": {
                        "role_0": str(transfer_hypothesis["hypothesis_id"]),
                    },
                    "context": {
                        "parent_source_digest": parent_digest,
                        "question_id": question.get("question_id"),
                    },
                },
                operation_label=transfer_operation_id,
            )
            transfer_result = transfer_response.get("result", {})
            proposed_actions = (
                transfer_result.get("proposed_actions", [])
                if isinstance(transfer_result, Mapping)
                else []
            )
            if (
                not isinstance(transfer_result, Mapping)
                or transfer_result.get("status") != "supported"
                or not isinstance(proposed_actions, list)
                or not proposed_actions
                or any(
                    not isinstance(action, Mapping)
                    or action.get("candidate")
                    != transfer_hypothesis["hypothesis_id"]
                    for action in proposed_actions
                )
            ):
                raise RedesignError(
                    "resident construction procedure did not transfer to the successor task"
                )
            procedure_application = {
                "operation_id": transfer_operation_id,
                "procedure": transfer_result.get("procedure"),
                "status": transfer_result.get("status"),
                "parent_source_digest": parent_digest,
                "candidate_id": transfer_hypothesis["hypothesis_id"],
                "compiler_family": transfer_hypothesis["compiler_family"],
                "proposed_actions": proposed_actions,
                "work": transfer_result.get("outcome", {}).get("work"),
                "field_state_sha256": transfer_response.get("field_state_sha256"),
            }
        for hypothesis in agenda:
            candidate_ir = ArchitectureIR.from_dict(hypothesis["architecture"])
            candidate = synthesize_workspace(parent_files, candidate_ir)
            candidate_id = hypothesis["hypothesis_id"]
            candidate_files[candidate_id] = candidate.files
            candidate_dir = home / "_candidate-work" / candidate_id
            if candidate_dir.exists():
                shutil.rmtree(candidate_dir)
            _write_workspace(candidate_dir, candidate.files)
            observatory_index = index_workspace(candidate_dir)
            measurement = _measure_candidate(candidate_dir, hypothesis)
            declared_causal = hypothesis.get("causal_prediction")
            causal_expected = (
                {
                    "baseline_returncode": declared_causal.get(
                        "expected_baseline_returncode"
                    ),
                    "holdout_returncode": declared_causal.get(
                        "expected_holdout_returncode"
                    ),
                }
                if isinstance(declared_causal, Mapping)
                else {
                    "baseline_returncode": measurement["prediction"]["expected"][
                        "baseline_returncode"
                    ],
                    "holdout_returncode": measurement["prediction"]["expected"][
                        "holdout_returncode"
                    ],
                }
            )
            causal_observed = dict(measurement["prediction"]["observed"])
            causal_outcome = {
                "intervention": (
                    declared_causal.get("intervention")
                    if isinstance(declared_causal, Mapping)
                    else hypothesis.get("claim")
                ),
                "expected": causal_expected,
                "observed": causal_observed,
                "matched": causal_expected == causal_observed,
                "parent_source_digest": parent_digest,
                "candidate_source_digest": candidate.source_digest,
            }
            shutil.rmtree(candidate_dir, ignore_errors=True)
            source_refs = source_references(observatory_index, hypothesis["source_paths"])
            field_observation = memory.semantic(
                {
                    "operation": "observe",
                    "operation_id": f"redesign:observe:{target_generation}:{candidate_id}",
                    "delivery_id": f"redesign:observe:{target_generation}:{candidate_id}",
                    "event_id": f"redesign:event:{target_generation}:{candidate_id}",
                    "frame": "cassimindfield-redesign-v1",
                    "observations": [
                        {
                            "subject": f"candidate:{candidate_id}",
                            "value": {
                                "candidate_source_digest": candidate.source_digest,
                                "metric_vector": measurement["metric_vector"],
                                "prediction_error": measurement["assessments"]["prediction_error"],
                                "causal_outcome": causal_outcome,
                            },
                        }
                    ],
                    "receipt": {
                        "clock_domain": "redesign-logical",
                        "time": float(target_generation),
                        "uncertainty": 0.0,
                    },
                    "source": {
                        "kind": "architecture-redesign-observation",
                        "candidate_id": candidate_id,
                        "source_revision": parent_digest,
                    },
                },
                operation_label=f"redesign:observe:{target_generation}:{candidate_id}",
            )
            field_assessment = memory.semantic(
                {
                    "operation": "register",
                    "operation_id": f"redesign:assessment:{target_generation}:{candidate_id}",
                    "record_id": f"redesign-assessment:{candidate_id}",
                    "kind": "Assessment",
                    "payload": {
                        "purpose": "assessment",
                        "state": "resolved",
                        "candidate_id": candidate_id,
                        "question_id": question.get("question_id"),
                        "compiler_family": question.get("compiler_family"),
                        "status": measurement["assessments"]["status"],
                        "prediction_error": measurement["assessments"]["prediction_error"],
                        "metric_vector": measurement["metric_vector"],
                        "causal_outcome": causal_outcome,
                    },
                    "epistemic_kind": "observed",
                },
                operation_label=f"redesign:assessment:{target_generation}:{candidate_id}",
            )
            field_obligation = memory.semantic(
                {
                    "operation": "register",
                    "operation_id": f"redesign:obligation:{target_generation}:{candidate_id}",
                    "record_id": f"redesign-obligation:{candidate_id}",
                    "kind": "Obligation",
                    "payload": {
                        "purpose": (
                            "prediction"
                            if measurement["assessments"]["status"] == "PASS"
                            else "candidate-exploration"
                        ),
                        "state": "pending",
                        "candidate_id": candidate_id,
                        "priority": (
                            2.0
                            if measurement["assessments"]["status"] == "PASS"
                            else 1.0
                        ),
                        "candidate_source_digest": candidate.source_digest,
                        "prediction_error": measurement["assessments"]["prediction_error"],
                    },
                    "epistemic_kind": "observed",
                },
                operation_label=f"redesign:obligation:{target_generation}:{candidate_id}",
            )
            field_record = WorkMemoryRecord(
                source_id=f"redesign-hypothesis:{candidate_id}",
                context={
                    "study": "cassimindfield-redesign",
                    "parent_source_digest": parent_digest,
                    "question_id": question.get("question_id"),
                },
                payload={
                    "hypothesis": hypothesis,
                    "candidate_digest": candidate.source_digest,
                    "measurement": measurement["metric_vector"],
                    "causal_outcome": causal_outcome,
                },
                observed_timestamp=f"logical:campaign:{target_generation}",
                labels=("architecture-hypothesis", "redesign"),
            )
            learned = memory.learn(field_record)
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "hypothesis": hypothesis,
                    "ir_digest": candidate_ir.digest(),
                    "candidate_source_digest": candidate.source_digest,
                    "parent_source_digest": parent_digest,
                    "candidate_manifest": candidate.manifest,
                    "observatory_index": observatory_index,
                    "source_refs": source_refs,
                    "measurement": measurement,
                    "prediction_error": measurement["assessments"]["prediction_error"],
                    "causal_outcome": causal_outcome,
                    "field_record": {
                        "source_revision_id": learned.get("source_revision_id"),
                        "state_sha256": learned.get("state_sha256"),
                    },
                    "field_observation": {
                        "event": field_observation.get("result", {}).get("event"),
                        "field_state_sha256": field_observation.get("field_state_sha256"),
                    },
                    "field_assessment": {
                        "record": field_assessment.get("result", {}).get("record"),
                        "field_state_sha256": field_assessment.get("field_state_sha256"),
                    },
                    "field_obligation": {
                        "record": field_obligation.get("result", {}).get("record"),
                        "field_state_sha256": field_obligation.get("field_state_sha256"),
                    },
                }
            )
        assessment_history_record = _record_assessment_history(
            memory,
            target_generation=target_generation,
            question=question,
            candidates=candidates,
            prior_history=assessment_history,
        )
        existing_history_families = {
            str(family)
            for family in (
                assessment_history.get("histories", {})
                if isinstance(assessment_history.get("histories", {}), Mapping)
                else {}
            )
        }
        existing_history_families.add(str(question["compiler_family"]))
        seeded_history_records = _seed_missing_assessment_history(
            memory,
            target_generation=target_generation,
            question_options=question_options,
            preflight_rows=preflight_rows,
            existing_families=existing_history_families,
        )
        resident_history_record_refs = _resident_assessment_history_refs(
            memory,
            question_options,
        )
        history_trajectory = _history_trajectory(
            generation=target_generation,
            question=question,
            prior_history=assessment_history,
            seeded_history_records=seeded_history_records,
            resident_history_record_refs=resident_history_record_refs,
        )


        curiosity_operation_id = (
            f"redesign:autonomous-curiosity:{target_generation}:"
            f"{memory.regional_field_receipt()['field_state_sha256'][:24]}"
        )
        curiosity_response = memory.semantic(
            {
                "operation": "autonomous-curiosity",
                "operation_id": curiosity_operation_id,
                "goal": {"kind": "architecture-redesign-assessment"},
                "max_goals": MAX_CANDIDATES,
                "min_error": 0.0,
            },
            operation_label=curiosity_operation_id,
        )
        curiosity_result = curiosity_response.get("result", {})
        field_state_before = memory.regional_field_receipt()
        agenda_operation_id = (
            f"redesign:autonomous-agenda:{target_generation}:"
            f"{field_state_before['field_state_sha256'][:24]}"
        )
        agenda_response = memory.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": agenda_operation_id,
                "goal": {
                    "kind": "architecture-redesign-selection",
                    "candidate_count": len(candidates),
                },
                "max_items": MAX_CANDIDATES,
                "obligation_prefix": "redesign-obligation:",
            },
            operation_label=agenda_operation_id,
        )
        agenda_result = agenda_response.get("result", {})
        agenda_items = (
            agenda_result.get("agenda", [])
            if isinstance(agenda_result, Mapping)
            else []
        )
        selected_candidate_item = (
            agenda_result.get("selected")
            if isinstance(agenda_result, Mapping)
            else None
        )
        if not isinstance(selected_candidate_item, Mapping):
            raise RedesignError("field autonomous agenda abstained: candidate selection is absent")
        selected_ref = selected_candidate_item.get("obligation", {})
        if (
            selected_candidate_item.get("kind") != "resolve-obligation"
            or not isinstance(selected_ref, Mapping)
            or not str(selected_ref.get("id", "")).startswith("redesign-obligation:")
        ):
            raise RedesignError("field autonomous agenda selected a non-candidate obligation")
        selected_candidate_digest = digest(selected_candidate_item)
        selected_candidate_rank = next(
            (
                index
                for index, item in enumerate(agenda_items)
                if isinstance(item, Mapping) and digest(item) == selected_candidate_digest
            ),
            None,
        )
        if selected_candidate_rank is None:
            raise RedesignError("field autonomous agenda selected an item absent from its ordered agenda")
        selected_ref = selected_candidate_item.get("obligation", {})
        selected_record_id = (
            selected_ref.get("id") if isinstance(selected_ref, Mapping) else None
        )
        selected = str(selected_record_id or "").removeprefix("redesign-obligation:")
        selected_row = next(
            (row for row in candidates if row["candidate_id"] == selected),
            None,
        )
        if selected_row is None or selected_row["measurement"]["assessments"]["status"] != "PASS":
            raise RedesignError("field autonomous agenda selected a non-promotable candidate")
        field_state_after = memory.regional_field_receipt()
        question_operation_ids = [
            *research_operation_ids,
            question_curiosity_response["operation_id"],
            bootstrap_agenda_id,
            question_query["operation_id"],
        ]
        question_query_request_sha256 = question_query["_request_sha256"]
        question_query_response_sha256 = question_query["_response_sha256"]
        question_query_record_sha256 = question_query["_record_sha256"]
        bootstrap_agenda_result_sha256 = digest(bootstrap_result)
        candidate_agenda_result_sha256 = digest(agenda_result)
        assessment_history_receipt = {
            "schema": "cassimindfield.assessment-history.v1",
            "mode": question_history["mode"],
            "decision": question_history["decision"],
            "selected_family": question_history["selected_family"],
            "queries": assessment_history["queries"],
            "query_operation_ids": assessment_history["operation_ids"],
            "history_record_refs": assessment_history["history_record_refs"],
            "history_record_digests": [
                row["record_sha256"]
                for row in assessment_history["queries"]
                if row.get("record_sha256")
            ],
            "derived_priorities": question_history["priorities"],
            "updated_record": assessment_history_record,
            "seeded_history_records": seeded_history_records,
            "resident_history_record_refs_after": resident_history_record_refs,
            "history_trajectory": history_trajectory,
            "field_learning_selector": (
                None
                if question_selector is None
                else {
                    "operation_id": question_selector["operation_id"],
                    "request": question_selector["request"],
                    "result": question_selector["result"],
                    "event": question_history["field_history_selector"]["event"],
                    "evidence": question_selector["result"].get("evidence", {}),
                    "abstained": question_selector["abstained"],
                    "field_state_sha256": question_selector["field_state_sha256"],
                }
            ),
            "prior_obligation_close_operation_ids": prior_obligation_close_operation_ids,
            "field_state_before_sha256": field_input["field_state_sha256"],
            "preflight_rows": preflight_rows,
            "preflight_operation_ids": preflight_operation_ids,
            "learned_investigation_procedure": procedure_learning,
            "applied_investigation_procedure": procedure_application,
            "capability_objective": {
                "benefit": "successful unfamiliar successor construction",
                "cost": "field procedure work",
                "preserve": "baseline and holdout behavior",
                "learning_reward": (
                    None
                    if procedure_learning is None
                    else procedure_learning["measured_cost"]["net_saved_steps"]
                ),
            },
            "history_selection_operation_id": history_selection_operation_id,
            "history_selection_request": history_selection_request,
            "history_selection_event": history_selection_result.get("event"),
            "history_selection_evidence": history_selection_result.get("evidence", {}),
            "history_selection_dependencies": (
                [history_selection_result["event"]]
                if isinstance(history_selection_result.get("event"), Mapping)
                else []
            ),
            "historical_v1_obligation_refs": historical_source_obligation_refs,
            "current_v2_obligation_refs": source_obligation_refs,
            "field_state_after_sha256": field_state_after["field_state_sha256"],
        }

        field_question = {
            "schema": "cassimindfield.field-question.v2",
            "question_options": [
                {
                    "question_id": option.get("question_id"),
                    "question": option.get("question"),
                    "compiler_family": option.get("compiler_family"),
                    "variant_keys": [
                        variant.get("variant_key")
                        for variant in option.get("variant_catalog", [])
                        if isinstance(variant, Mapping)
                    ],
                }
                for option in question_options
            ],
            "question_id": question.get("question_id"),
            "question": question.get("question"),
            "compiler_family": question.get("compiler_family"),
            "history_mode": question_history["mode"],
            "history_decision": question_history["decision"],
            "history_derived_priorities": question_history["priorities"],
            "assessment_history_queries": assessment_history["queries"],
            "assessment_history_record_refs": assessment_history["history_record_refs"],
            "assessment_history_record_refs_after": resident_history_record_refs,
            "history_trajectory": history_trajectory,
            "history_selection_event": history_selection_result.get("event"),
            "history_selection_evidence": history_selection_result.get("evidence", {}),
            "historical_v1_obligation_ref": (
                historical_source_obligation_refs[
                    next(
                        index
                        for index, option in enumerate(question_options)
                        if option.get("question_id") == question.get("question_id")
                    )
                ]
                if any(
                    option.get("question_id") == question.get("question_id")
                    for option in question_options
                )
                else None
            ),
            "assessment_history_updated_record": assessment_history_record,
            "historical_v1_obligation_refs": historical_source_obligation_refs,
            "current_v2_obligation_refs": source_obligation_refs,
            "selected_question_ref": source_obligation_ref,
            "selected_question_option_rank": next(
                (
                    index
                    for index, option in enumerate(question_options)
                    if option.get("question_id") == question.get("question_id")
                ),
                None,
            ),
            "selected_question_agenda_rank": question_query["_selected_rank"],
            "bootstrap_agenda_items": bootstrap_result.get("agenda", []),
            "bootstrap_agenda_selected": bootstrap_result.get("selected"),
            "bootstrap_agenda_result_sha256": bootstrap_agenda_result_sha256,
            "source_event_ref": dict(source_event_ref),
            "source_event_refs": [dict(ref) for ref in research_event_refs],
            "source_obligation_ref": source_obligation_ref,
            "source_obligation_refs": [dict(ref) for ref in source_obligation_refs],
            "curiosity_event": question_curiosity_result.get("event"),
            "curiosity_operation_id": question_curiosity_response["operation_id"],
            "agenda_operation_id": bootstrap_agenda_id,
            "question_query_operation_id": question_query["operation_id"],
            "question_query_request_sha256": question_query_request_sha256,
            "question_query_response_sha256": question_query_response_sha256,
            "question_query_result_sha256": digest(question_query.get("result", {})),
            "operation_ids": question_operation_ids,
            "question_query_record_sha256": question_query_record_sha256,
            "field_state_in_sha256": field_input["field_state_sha256"],
            "field_state_out_sha256": field_state_after["field_state_sha256"],
        }
        field_selection = {
            "schema": "cassimindfield.field-selection.v3",
            "method": "semantic.autonomous-agenda",
            "assessment_history": assessment_history_receipt,
            "history_mode": question_history["mode"],
            "history_decision": question_history["decision"],
            "history_derived_priorities": question_history["priorities"],
            "history_trajectory": history_trajectory,
            "learned_investigation_procedure": procedure_learning,
            "applied_investigation_procedure": procedure_application,
            "bootstrap_agenda_operation_id": bootstrap_agenda_id,
            "curiosity_operation_id": curiosity_operation_id,
            "agenda_operation_id": agenda_operation_id,
            "agenda_event": agenda_result.get("event"),
            "history_selection_request": history_selection_request,
            "history_selection_event": history_selection_result.get("event"),
            "history_selection_evidence": history_selection_result.get("evidence", {}),
            "history_selection_abstained": question_selector["abstained"],
            "curiosity": {
                "operation": "autonomous-curiosity",
                "operation_id": curiosity_operation_id,
                "status": curiosity_result.get("status"),
                "event": curiosity_result.get("event"),
            },
            "question_options": field_question["question_options"],
            "question_agenda_items": bootstrap_result.get("agenda", []),
            "question_agenda_selected": bootstrap_result.get("selected"),
            "question_agenda_result_sha256": bootstrap_agenda_result_sha256,
            "selected_question_id": field_question["question_id"],
            "selected_question_compiler_family": field_question["compiler_family"],
            "selected_question_ref": source_obligation_ref,
            "selected_question_item": selected_question_item,
            "question_query_operation_id": question_query["operation_id"],
            "question_query_request_sha256": question_query_request_sha256,
            "question_query_response_sha256": question_query_response_sha256,
            "question_query_record_sha256": question_query_record_sha256,
            "candidate_agenda_items": agenda_items,
            "candidate_agenda_selected": selected_candidate_item,
            "candidate_agenda_result_sha256": candidate_agenda_result_sha256,
            "selected_candidate_rank": selected_candidate_rank,
            "selected_item": selected_candidate_item,
            "selected_candidate_id": selected,
            "operation_ids": question_operation_ids
            + preflight_operation_ids
            + [history_selection_operation_id]
            + [curiosity_operation_id, agenda_operation_id]
            + [assessment_history_record["operation_id"]]
            + (
                []
                if procedure_learning is None
                else [procedure_learning["operation_id"]]
            )
            + (
                []
                if procedure_application is None
                else [procedure_application["operation_id"]]
            )
            + [
                row["operation_id"]
                for row in seeded_history_records
                if isinstance(row, Mapping) and row.get("operation_id")
            ]
            + prior_obligation_close_operation_ids
            + [
                f"redesign:observe:{target_generation}:{row['candidate_id']}"
                for row in candidates
            ]
            + [
                f"redesign:assessment:{target_generation}:{row['candidate_id']}"
                for row in candidates
            ]
            + [
                f"redesign:obligation:{target_generation}:{row['candidate_id']}"
                for row in candidates
            ],
            "record_refs": [
                str(selected_question_ref.get("id")),
            ]
            + [str(ref.get("id")) for ref in research_event_refs]
            + [str(ref.get("id")) for ref in source_obligation_refs]
            + [
                f"redesign-obligation:{row['candidate_id']}" for row in candidates
            ]
            + [str(ref.get("id")) for ref in resident_history_record_refs],
            "procedure_record_refs": (
                []
                if procedure_learning is None and procedure_application is None
                else [INVESTIGATION_PROCEDURE_ID]
            ),
            "field_state_in_sha256": field_state_before["field_state_sha256"],
            "field_state_out_sha256": field_state_after["field_state_sha256"],
        }
        migration = {
            "schema": "cassimindfield.field-state-migration.v1",
            "from_generation": generation,
            "to_generation": target_generation,
            "parent_field_state_sha256": field_state_before["field_state_sha256"],
            "child_field_state_sha256": field_state_after["field_state_sha256"],
            "selected_candidate_id": selected,
            "selection_operation_id": agenda_operation_id,
            "parent_workspace_digest": parent_digest,
            "child_workspace_digest": selected_row["candidate_source_digest"],
            "parent_selected_candidate_id": state.get("selected_candidate_id"),
            "status": "promoted",
        }
        candidates_by_id = {row["candidate_id"]: row for row in candidates}
        candidates_by_id[selected]["selection"] = {
            "status": "PROMOTED",
            "field_selection": field_selection,
        }
        receipt = _make_receipt(
            target_generation,
            previous_receipt,
            [candidates_by_id[row["candidate_id"]] for row in candidates],
            selected,
            migration,
            field_selection,
            field_question,
            assessment_history_receipt,
            responsibility_evidence,
        )
        next_state = {
            "schema": "cassimindfield.redesign-state.v1",
            "generation": target_generation,
            "workspace_digest": selected_row["candidate_source_digest"],
            "parent_workspace_digest": parent_digest,
            "agenda_role": "receipt-only; selection performed by semantic autonomous-agenda in the sole field state",
            "selected_candidate_id": selected,
            "candidate_dag": [
                {
                    "candidate_id": row["candidate_id"],
                    "parent_digest": row["parent_source_digest"],
                    "child_digest": row["candidate_source_digest"],
                }
                for row in candidates
            ],
            "field_question_id": question.get("question_id"),
            "field_state_sha256": field_state_after["field_state_sha256"],
        }
        _commit_generation(home, target_generation, receipt, candidate_files, next_state)
    return {
        "status": "PASS",
        "generation": target_generation,
        "selected_candidate_id": selected,
        "receipt": receipt,
        "candidate_count": len(candidates),
        "field_state_migration": migration,
        "responsibility_continuity": responsibility_evidence,
    }


def _replay_campaign(
    home: Path,
    *,
    responsibility_snapshot: Mapping[str, Any] | str | os.PathLike[str],
) -> dict[str, Any]:
    loaded_snapshot = _load_responsibility_snapshot(responsibility_snapshot)
    if loaded_snapshot is None:
        raise MutationRejected("a field-owner snapshot is required for replay")
    responsibility_snapshot = loaded_snapshot
    generation, state, receipt = _load_current(home)
    responsibility_check = _check_responsibility_snapshot(
        receipt, responsibility_snapshot
    )
    if generation < 1:
        return {
            "status": "PASS",
            "generation": generation,
            "replayed": 0,
            "responsibility_continuity": responsibility_check,
        }
    parent = _read(_generation_path(home, 0) / "state.json")
    parent_files = _read_parent_files(_generation_path(home, 0) / "candidates" / "predecessor")
    for row in receipt.get("candidates", []):
        candidate_dir = _generation_path(home, generation) / "candidates" / row["candidate_id"]
        files = _read_parent_files(candidate_dir)
        if workspace_digest(files) != row["candidate_source_digest"]:
            raise MutationRejected("candidate replay digest diverged")
        measurement = _measure_candidate(candidate_dir, row["hypothesis"])
        if measurement["metric_vector"] != row["measurement"]["metric_vector"]:
            raise MutationRejected("candidate replay metrics diverged")
    return {
        "status": "PASS",
        "generation": generation,
        "replayed": len(receipt.get("candidates", [])),
        "state_sha256": digest(state),
        "parent_state_sha256": digest(parent),
        "responsibility_continuity": responsibility_check,
    }


def _read_parent_files(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise MutationRejected(f"workspace directory missing: {root}")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def _rollback(
    data_home: str | os.PathLike[str],
    generation: int,
    *,
    responsibility_snapshot: Mapping[str, Any] | str | os.PathLike[str],
) -> dict[str, Any]:
    loaded_snapshot = _load_responsibility_snapshot(responsibility_snapshot)
    if loaded_snapshot is None:
        raise MutationRejected("a field-owner snapshot is required for rollback")
    responsibility_snapshot = loaded_snapshot
    home = Path(data_home).resolve()
    target = _generation_path(home, int(generation))
    if not (target / "receipt.json").is_file():
        raise MutationRejected("rollback generation is absent")
    target_receipt = _read(target / "receipt.json")
    _check(target_receipt, "content_sha256", _stable_receipt(target_receipt))
    target_state = _read(target / "state.json")
    if _pointer(home).is_file():
        current_generation, _current_state, current_receipt = _load_current(home)
    else:
        current_generation, current_receipt = -1, {}
    target_check = _check_responsibility_snapshot(target_receipt, responsibility_snapshot)
    current_check = _check_responsibility_snapshot(current_receipt, responsibility_snapshot)
    comparisons = {
        "current_generation": current_check.get("comparison"),
        "target_generation": target_check.get("comparison"),
    }
    continuity_check = {
        "schema": RESPONSIBILITY_CONTINUITY_SCHEMA,
        "status": (
            "monotonic"
            if any(value is not None for value in comparisons.values())
            else "baseline"
        ),
        "current_snapshot_sha256": current_check["current_snapshot_sha256"],
        "source_field_state_sha256": current_check["source_field_state_sha256"],
        "records_sha256": current_check["records_sha256"],
        "last_observed": current_check["last_observed"],
        "baselines": {
            "current_generation": current_check.get("baseline"),
            "target_generation": target_check.get("baseline"),
        },
        "comparisons": comparisons,
        "scope": "read-only-entity-snapshot; rollback changes redesign pointers only",
    }
    responsibility_sha256 = digest(continuity_check)
    pointer_body = {
        "schema": POINTER_SCHEMA,
        "generation": int(generation),
        "receipt_sha256": target_receipt["content_sha256"],
        "state_sha256": digest(target_state),
        "responsibility_continuity": continuity_check,
        "responsibility_continuity_sha256": responsibility_sha256,
    }
    _atomic_json(_pointer(home), {**pointer_body, "pointer_sha256": digest(pointer_body)})
    promotion_body = {
        "schema": "cassimindfield.promotion-pointer.v1",
        "generation": int(generation),
        "candidate_id": target_receipt.get("selected_candidate_id"),
        "receipt_sha256": target_receipt["content_sha256"],
        "responsibility_continuity_sha256": responsibility_sha256,
    }
    _atomic_json(home / "promotion.json", {**promotion_body, "pointer_sha256": digest(promotion_body)})
    return {
        "status": "PASS",
        "generation": int(generation),
        "receipt_sha256": target_receipt["content_sha256"],
        "workspace_digest": target_state.get("workspace_digest"),
        "responsibility_continuity": continuity_check,
        "previous_generation": (
            None if current_generation < 0 else current_generation
        ),
    }


def _recover_interrupted_owner_attempt(
    home: Path,
    client: _FieldOwnerClient,
    link: dict[str, Any],
) -> None:
    attempt = link.get("inflight_attempt")
    if attempt is None:
        return
    if not isinstance(attempt, Mapping) or set(attempt) != {"generation", "started_at"}:
        raise MutationRejected("field-owner link has a malformed in-flight attempt")
    target = attempt["generation"]
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise MutationRejected("field-owner link has an invalid in-flight generation")
    receipt_path = _generation_path(home, target) / "receipt.json"
    receipt = None
    if _pointer(home).is_file() and receipt_path.is_file():
        current_generation, _state, _current_receipt = _load_current(home)
        if current_generation >= target:
            receipt = _read(receipt_path)
            _check(receipt, "content_sha256", _stable_receipt(receipt))
    link["pending_reports"].extend(
        _rewrite_outcome_reports(
            link,
            generation=target,
            receipt=receipt,
            interrupted=receipt is None,
        )
    )
    link["inflight_attempt"] = None
    _save_owner_link(home / "field-owner-link.json", link)


def _prepare_live_owner(
    data_home: str | os.PathLike[str],
    *,
    field_owner_url: str,
) -> tuple[Path, _FieldOwnerClient, dict[str, Any], dict[str, Any]]:
    home = Path(data_home).resolve()
    client = _field_owner_client(field_owner_url)
    link, snapshot = client.bind_campaign(home)
    if link.get("inflight_attempt") is not None:
        _recover_interrupted_owner_attempt(home, client, link)
        snapshot = client.responsibility_snapshot()
    client.flush_reports(home, link)
    snapshot = client.responsibility_snapshot()
    client._assert_program_bound(snapshot, link)
    return home, client, link, snapshot


def run_campaign(
    data_home: str | os.PathLike[str],
    *,
    field_owner_url: str,
    research_cycle: bool = False,
) -> dict[str, Any]:
    home, client, link, snapshot = _prepare_live_owner(
        data_home,
        field_owner_url=field_owner_url,
    )
    generation = _load_current(home)[0] if _pointer(home).is_file() else 0
    creates_successor = generation == 0 or research_cycle
    if research_cycle and generation >= 1:
        owner_row = _owner_program_row(snapshot, link["program_id"])
        payload = owner_row["record"].get("payload")
        declaration = payload.get("responsibility") if isinstance(payload, Mapping) else None
        pending = (
            declaration.get("outstanding_assessments")
            if isinstance(declaration, Mapping)
            else None
        )
        if not isinstance(pending, list):
            raise MutationRejected("field owner omitted outstanding impact assessments")
        if pending:
            affected = sorted(
                {
                    str(row.get("consequence", {}).get("affected", "unspecified"))
                    for row in pending
                    if isinstance(row, Mapping)
                    and isinstance(row.get("consequence"), Mapping)
                }
            )
            raise MutationRejected(
                "affected-group review is required before another successor: "
                + ", ".join(affected)
                + "; open this program in the Research Workspace and answer each linked report"
            )
    if not creates_successor:
        return _run_campaign(
            home,
            responsibility_snapshot=snapshot,
        )
    target_generation = generation + 1
    link["inflight_attempt"] = {
        "generation": target_generation,
        "started_at": _utc_now(),
    }
    _save_owner_link(home / "field-owner-link.json", link)
    try:
        result = _run_campaign(
            home,
            research_cycle=research_cycle,
            responsibility_snapshot=snapshot,
        )
    except Exception:
        committed_generation = (
            _load_current(home)[0] if _pointer(home).is_file() else 0
        )
        if committed_generation < target_generation:
            link["inflight_attempt"] = None
            _save_owner_link(home / "field-owner-link.json", link)
        raise
    if result.get("status") == "PASS" and result.get("generation") == target_generation:
        reports = _rewrite_outcome_reports(
            link,
            generation=target_generation,
            receipt=result.get("receipt"),
        )
        link["pending_reports"].extend(reports)
        link["inflight_attempt"] = None
        _save_owner_link(home / "field-owner-link.json", link)
        assessment_ids = client.flush_reports(home, link)
        result["human_impact_review"] = {
            "status": "pending",
            "program_id": link["program_id"],
            "report_count": len(reports),
            "assessment_ids": assessment_ids,
        }
    else:
        link["inflight_attempt"] = None
        _save_owner_link(home / "field-owner-link.json", link)
    return result


def replay_campaign(
    data_home: str | os.PathLike[str],
    *,
    field_owner_url: str,
) -> dict[str, Any]:
    home, _client, _link, snapshot = _prepare_live_owner(
        data_home,
        field_owner_url=field_owner_url,
    )
    return _replay_campaign(home, responsibility_snapshot=snapshot)


def rollback(
    data_home: str | os.PathLike[str],
    generation: int,
    *,
    field_owner_url: str,
) -> dict[str, Any]:
    home, _client, _link, snapshot = _prepare_live_owner(
        data_home,
        field_owner_url=field_owner_url,
    )
    return _rollback(
        home,
        generation,
        responsibility_snapshot=snapshot,
    )


def _cross_world_receipt_path(home: Path) -> Path:
    return home / "cross-world" / "field-program-transfer.json"


def verify_cross_world_transfer(
    data_home: str | os.PathLike[str],
    receipt_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    home = Path(data_home).resolve()
    path = (
        _cross_world_receipt_path(home)
        if receipt_path is None
        else Path(receipt_path).resolve()
    )
    receipt = _read(path)
    _check(
        receipt,
        "content_sha256",
        {key: value for key, value in receipt.items() if key != "content_sha256"},
    )
    if receipt.get("schema") != CROSS_WORLD_SCHEMA:
        raise MutationRejected("unsupported cross-world receipt schema")
    generation, state, generation_receipt = _load_current(home)
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    expected_task = _field_program_construction_task(parent_files, parent_digest)
    if (
        receipt.get("source_generation") != generation
        or receipt.get("source_generation_receipt_sha256")
        != generation_receipt.get("content_sha256")
        or receipt.get("task") != expected_task
    ):
        raise MutationRejected("cross-world task diverged from promoted source")
    expected_source = _structured_source_from_task(expected_task)
    if receipt.get("structured_source") != expected_source:
        raise MutationRejected("cross-world structured source diverged from task IR")
    execution = _execute_structured_source(expected_source)
    if receipt.get("execution") != execution:
        raise MutationRejected("cross-world execution outcome diverged")
    prediction = expected_task["causal_prediction"]
    if (
        receipt.get("causal_outcome", {}).get("observed") != execution["execution"]
        or receipt.get("causal_outcome", {}).get("expected") != prediction
        or receipt.get("causal_outcome", {}).get("matched") is not True
    ):
        raise MutationRejected("cross-world causal outcome is inconsistent")
    actions = receipt.get("experienced_procedure", {}).get("proposed_actions")
    if not isinstance(actions, list):
        raise MutationRejected("cross-world experienced procedure actions are absent")
    comparison = _construction_plan_search(actions)
    if receipt.get("work_comparison") != comparison:
        raise MutationRejected("cross-world work comparison diverged")
    return {
        "status": "PASS",
        "source_generation": generation,
        "task_sha256": expected_task["task_sha256"],
        "net_saved_steps": comparison["net_saved_steps"],
        "content_sha256": receipt["content_sha256"],
    }


def run_cross_world_transfer(
    data_home: str | os.PathLike[str],
) -> dict[str, Any]:
    home = Path(data_home).resolve()
    receipt_path = _cross_world_receipt_path(home)
    if receipt_path.is_file():
        return {
            **verify_cross_world_transfer(home, receipt_path),
            "status": "REPLAYED",
        }
    generation, state, generation_receipt = _load_current(home)
    if generation < 3:
        raise RedesignError("cross-world transfer requires three promoted generations")
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    task = _field_program_construction_task(parent_files, parent_digest)
    structured_source = _structured_source_from_task(task)
    generation_one = _read(_generation_path(home, 1) / "receipt.json")
    learning = generation_one.get("field_selection", {}).get(
        "learned_investigation_procedure"
    )
    if not isinstance(learning, Mapping) or not isinstance(
        learning.get("procedure"), Mapping
    ):
        raise RedesignError("resident field has no learned construction procedure")
    procedure_ref = dict(learning["procedure"])
    operation_id = f"redesign:cross-world:{task['task_sha256'][:24]}"
    field_home = home / "field"
    with CassiFieldWorkMemory(field_home) as memory:
        field_before = memory.regional_field_receipt()
        response = memory.semantic(
            {
                "operation": "invoke-procedure",
                "operation_id": operation_id,
                "procedure_ref": procedure_ref,
                "bindings": {"role_0": task["task_sha256"]},
                "context": {
                    "source_world": task["source_world"],
                    "target_world": task["target_world"],
                    "parent_source_digest": parent_digest,
                },
            },
            operation_label=operation_id,
        )
        result = response.get("result", {})
        actions = (
            result.get("proposed_actions", [])
            if isinstance(result, Mapping)
            else []
        )
        if (
            not isinstance(result, Mapping)
            or result.get("status") != "supported"
            or not isinstance(actions, list)
            or not actions
            or any(
                not isinstance(action, Mapping)
                or action.get("candidate") != task["task_sha256"]
                for action in actions
            )
        ):
            raise RedesignError(
                "resident procedure did not transfer to the field-program world"
            )
        field_after = memory.regional_field_receipt()
    fresh_status = "exception"
    fresh_actions: list[Any] = []
    with tempfile.TemporaryDirectory(
        prefix="cassimindfield-cross-world-fresh-"
    ) as temporary:
        try:
            with CassiFieldWorkMemory(Path(temporary) / "field") as fresh:
                fresh_response = fresh.semantic(
                    {
                        "operation": "invoke-procedure",
                        "operation_id": "redesign:cross-world:fresh",
                        "procedure_ref": procedure_ref,
                        "bindings": {"role_0": task["task_sha256"]},
                        "context": {
                            "source_world": task["source_world"],
                            "target_world": task["target_world"],
                            "parent_source_digest": parent_digest,
                        },
                    },
                    operation_label="redesign:cross-world:fresh",
                )
            fresh_result = fresh_response.get("result", {})
            if isinstance(fresh_result, Mapping):
                fresh_status = str(fresh_result.get("status"))
                proposed = fresh_result.get("proposed_actions")
                if isinstance(proposed, list):
                    fresh_actions = proposed
        except Exception:
            pass
    if fresh_status == "supported" or fresh_actions:
        raise RedesignError("fresh field unexpectedly transferred resident procedure")
    execution = _execute_structured_source(structured_source)
    expected = task["causal_prediction"]
    observed = execution["execution"]
    matched = observed == expected
    if not matched:
        raise RedesignError("cross-world field program missed its causal prediction")
    comparison = _construction_plan_search(actions)
    if comparison["net_saved_steps"] <= 0:
        raise RedesignError("cross-world procedure did not reduce construction work")
    body = {
        "schema": CROSS_WORLD_SCHEMA,
        "source_generation": generation,
        "source_generation_receipt_sha256": generation_receipt["content_sha256"],
        "task": task,
        "procedure_ref": procedure_ref,
        "experienced_procedure": {
            "operation_id": operation_id,
            "status": result["status"],
            "proposed_actions": actions,
            "work": result.get("outcome", {}).get("work"),
            "field_state_before_sha256": field_before["field_state_sha256"],
            "field_state_after_sha256": field_after["field_state_sha256"],
        },
        "fresh_field_control": {
            "status": fresh_status,
            "proposed_actions": fresh_actions,
        },
        "structured_source": structured_source,
        "execution": execution,
        "causal_outcome": {
            "expected": expected,
            "observed": observed,
            "matched": matched,
        },
        "work_comparison": comparison,
    }
    receipt = {**body, "content_sha256": digest(body)}
    _atomic_json(receipt_path, receipt)
    return {
        "status": "PASS",
        "source_generation": generation,
        "task_sha256": task["task_sha256"],
        "experienced_status": result["status"],
        "fresh_status": fresh_status,
        "net_saved_steps": comparison["net_saved_steps"],
        "execution": execution["execution"],
        "receipt": str(receipt_path),
        "content_sha256": receipt["content_sha256"],
    }


def _constraint_world_receipt_path(home: Path) -> Path:
    return home / "cross-world" / "constraint-transfer.json"


def verify_constraint_world_transfer(
    data_home: str | os.PathLike[str],
    receipt_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    home = Path(data_home).resolve()
    path = (
        _constraint_world_receipt_path(home)
        if receipt_path is None
        else Path(receipt_path).resolve()
    )
    receipt = _read(path)
    _check(
        receipt,
        "content_sha256",
        {key: value for key, value in receipt.items() if key != "content_sha256"},
    )
    if receipt.get("schema") != CONSTRAINT_WORLD_SCHEMA:
        raise MutationRejected("unsupported constraint-world receipt schema")
    generation, state, generation_receipt = _load_current(home)
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    expected_task = _constraint_construction_task(parent_files, parent_digest)
    if (
        receipt.get("source_generation") != generation
        or receipt.get("source_generation_receipt_sha256")
        != generation_receipt.get("content_sha256")
        or receipt.get("task") != expected_task
    ):
        raise MutationRejected("constraint-world task diverged from promoted source")
    expected_source = _constraint_source_from_task(expected_task)
    if receipt.get("constraint_source") != expected_source:
        raise MutationRejected("constraint source diverged from task IR")
    execution = _execute_constraint_source(expected_source)
    if receipt.get("execution") != execution:
        raise MutationRejected("constraint execution outcome diverged")
    prediction = expected_task["causal_prediction"]
    observed = {
        "status": execution["status"],
        "final": execution["witness_audit"]["final"],
        "witness_required": bool(execution["witness"]),
    }
    if (
        receipt.get("causal_outcome", {}).get("expected") != prediction
        or receipt.get("causal_outcome", {}).get("observed") != observed
        or receipt.get("causal_outcome", {}).get("matched") is not True
    ):
        raise MutationRejected("constraint causal outcome is inconsistent")
    actions = receipt.get("experienced_procedure", {}).get("proposed_actions")
    if not isinstance(actions, list):
        raise MutationRejected("constraint experienced procedure actions are absent")
    comparison = _construction_plan_search(actions)
    if receipt.get("work_comparison") != comparison:
        raise MutationRejected("constraint work comparison diverged")
    return {
        "status": "PASS",
        "source_generation": generation,
        "task_sha256": expected_task["task_sha256"],
        "net_saved_steps": comparison["net_saved_steps"],
        "content_sha256": receipt["content_sha256"],
    }


def run_constraint_world_transfer(
    data_home: str | os.PathLike[str],
) -> dict[str, Any]:
    home = Path(data_home).resolve()
    receipt_path = _constraint_world_receipt_path(home)
    if receipt_path.is_file():
        return {
            **verify_constraint_world_transfer(home, receipt_path),
            "status": "REPLAYED",
        }
    generation, state, generation_receipt = _load_current(home)
    if generation < 3:
        raise RedesignError(
            "constraint-world transfer requires three promoted generations"
        )
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    task = _constraint_construction_task(parent_files, parent_digest)
    constraint_source = _constraint_source_from_task(task)
    generation_one = _read(_generation_path(home, 1) / "receipt.json")
    learning = generation_one.get("field_selection", {}).get(
        "learned_investigation_procedure"
    )
    if not isinstance(learning, Mapping) or not isinstance(
        learning.get("procedure"), Mapping
    ):
        raise RedesignError("resident field has no learned construction procedure")
    procedure_ref = dict(learning["procedure"])
    operation_id = f"redesign:constraint-world:{task['task_sha256'][:24]}"
    field_home = home / "field"
    with CassiFieldWorkMemory(field_home) as memory:
        field_before = memory.regional_field_receipt()
        response = memory.semantic(
            {
                "operation": "invoke-procedure",
                "operation_id": operation_id,
                "procedure_ref": procedure_ref,
                "bindings": {"role_0": task["task_sha256"]},
                "context": {
                    "source_world": task["source_world"],
                    "target_world": task["target_world"],
                    "parent_source_digest": parent_digest,
                },
            },
            operation_label=operation_id,
        )
        result = response.get("result", {})
        actions = (
            result.get("proposed_actions", [])
            if isinstance(result, Mapping)
            else []
        )
        if (
            not isinstance(result, Mapping)
            or result.get("status") != "supported"
            or not isinstance(actions, list)
            or not actions
            or any(
                not isinstance(action, Mapping)
                or action.get("candidate") != task["task_sha256"]
                for action in actions
            )
        ):
            raise RedesignError(
                "resident procedure did not transfer to the constraint world"
            )
        field_after = memory.regional_field_receipt()
    fresh_status = "exception"
    fresh_actions: list[Any] = []
    with tempfile.TemporaryDirectory(
        prefix="cassimindfield-constraint-fresh-"
    ) as temporary:
        try:
            with CassiFieldWorkMemory(Path(temporary) / "field") as fresh:
                fresh_response = fresh.semantic(
                    {
                        "operation": "invoke-procedure",
                        "operation_id": "redesign:constraint-world:fresh",
                        "procedure_ref": procedure_ref,
                        "bindings": {"role_0": task["task_sha256"]},
                        "context": {
                            "source_world": task["source_world"],
                            "target_world": task["target_world"],
                            "parent_source_digest": parent_digest,
                        },
                    },
                    operation_label="redesign:constraint-world:fresh",
                )
            fresh_result = fresh_response.get("result", {})
            if isinstance(fresh_result, Mapping):
                fresh_status = str(fresh_result.get("status"))
                proposed = fresh_result.get("proposed_actions")
                if isinstance(proposed, list):
                    fresh_actions = proposed
        except Exception:
            pass
    if fresh_status == "supported" or fresh_actions:
        raise RedesignError(
            "fresh field unexpectedly transferred the constraint procedure"
        )
    execution = _execute_constraint_source(constraint_source)
    expected = task["causal_prediction"]
    observed = {
        "status": execution["status"],
        "final": execution["witness_audit"]["final"],
        "witness_required": bool(execution["witness"]),
    }
    matched = observed == expected
    if not matched:
        raise RedesignError("constraint execution missed its causal prediction")
    comparison = _construction_plan_search(actions)
    if comparison["net_saved_steps"] <= 0:
        raise RedesignError(
            "constraint-world procedure did not reduce construction work"
        )
    body = {
        "schema": CONSTRAINT_WORLD_SCHEMA,
        "source_generation": generation,
        "source_generation_receipt_sha256": generation_receipt["content_sha256"],
        "task": task,
        "procedure_ref": procedure_ref,
        "experienced_procedure": {
            "operation_id": operation_id,
            "status": result["status"],
            "proposed_actions": actions,
            "work": result.get("outcome", {}).get("work"),
            "field_state_before_sha256": field_before["field_state_sha256"],
            "field_state_after_sha256": field_after["field_state_sha256"],
        },
        "fresh_field_control": {
            "status": fresh_status,
            "proposed_actions": fresh_actions,
        },
        "constraint_source": constraint_source,
        "execution": execution,
        "causal_outcome": {
            "expected": expected,
            "observed": observed,
            "matched": matched,
        },
        "work_comparison": comparison,
    }
    receipt = {**body, "content_sha256": digest(body)}
    _atomic_json(receipt_path, receipt)
    return {
        "status": "PASS",
        "source_generation": generation,
        "task_sha256": task["task_sha256"],
        "experienced_status": result["status"],
        "fresh_status": fresh_status,
        "net_saved_steps": comparison["net_saved_steps"],
        "constraint_status": execution["status"],
        "witness": execution["witness"],
        "final": execution["witness_audit"]["final"],
        "field_transitions": execution["field_transitions"],
        "receipt": str(receipt_path),
        "content_sha256": receipt["content_sha256"],
    }


def _reasoning_world_receipt_path(home: Path) -> Path:
    return home / "cross-world" / "paired-reasoning-transfer.json"


def verify_reasoning_world_transfer(
    data_home: str | os.PathLike[str],
    receipt_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    home = Path(data_home).resolve()
    path = (
        _reasoning_world_receipt_path(home)
        if receipt_path is None
        else Path(receipt_path).resolve()
    )
    receipt = _read(path)
    _check(
        receipt,
        "content_sha256",
        {key: value for key, value in receipt.items() if key != "content_sha256"},
    )
    if receipt.get("schema") != REASONING_WORLD_SCHEMA:
        raise MutationRejected("unsupported paired-reasoning receipt schema")
    generation, state, generation_receipt = _load_current(home)
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    task = _paired_reasoning_task(parent_files, parent_digest)
    if (
        receipt.get("source_generation") != generation
        or receipt.get("source_generation_receipt_sha256")
        != generation_receipt.get("content_sha256")
        or receipt.get("task") != task
    ):
        raise MutationRejected(
            "paired-reasoning task diverged from promoted source"
        )
    reasoning = _learn_reasoning_regimes(task)
    if receipt.get("reasoning") != reasoning:
        raise MutationRejected(
            "paired-reasoning field evidence or selection diverged"
        )
    actions = receipt.get("experienced_procedure", {}).get("proposed_actions")
    if not isinstance(actions, list):
        raise MutationRejected(
            "paired-reasoning experienced procedure actions are absent"
        )
    comparison = _construction_plan_search(actions)
    if receipt.get("construction_work_comparison") != comparison:
        raise MutationRejected(
            "paired-reasoning construction work comparison diverged"
        )
    sat = reasoning["held_out"]["sat"]["selected_execution"]
    unsat = reasoning["held_out"]["unsat"]["selected_execution"]
    observed = {
        "sat_held_out": {
            "status": sat["status"],
            "evidence": "source-checked-witness"
            if sat["witness"] is not None
            else "absent",
        },
        "unsat_held_out": {
            "status": unsat["status"],
            "evidence": "independently-audited-certificate"
            if unsat["certificate"] is not None
            else "absent",
        },
    }
    if (
        receipt.get("causal_outcome", {}).get("expected")
        != task["causal_prediction"]
        or receipt.get("causal_outcome", {}).get("observed") != observed
        or receipt.get("causal_outcome", {}).get("matched") is not True
    ):
        raise MutationRejected("paired-reasoning causal outcome diverged")
    return {
        "status": "PASS",
        "source_generation": generation,
        "task_sha256": task["task_sha256"],
        "sat_regime": reasoning["held_out"]["sat"]["selected_regime"],
        "unsat_regime": reasoning["held_out"]["unsat"]["selected_regime"],
        "unsat_field_transition_saving": reasoning[
            "unsat_field_transition_saving"
        ],
        "content_sha256": receipt["content_sha256"],
    }


def run_reasoning_world_transfer(
    data_home: str | os.PathLike[str],
) -> dict[str, Any]:
    home = Path(data_home).resolve()
    receipt_path = _reasoning_world_receipt_path(home)
    if receipt_path.is_file():
        return {
            **verify_reasoning_world_transfer(home, receipt_path),
            "status": "REPLAYED",
        }
    generation, state, generation_receipt = _load_current(home)
    if generation < 3:
        raise RedesignError(
            "paired-reasoning transfer requires three promoted generations"
        )
    parent_files = _promoted_parent_workspace(home, generation, state)
    parent_digest = workspace_digest(parent_files)
    task = _paired_reasoning_task(parent_files, parent_digest)
    generation_one = _read(_generation_path(home, 1) / "receipt.json")
    learning = generation_one.get("field_selection", {}).get(
        "learned_investigation_procedure"
    )
    if not isinstance(learning, Mapping) or not isinstance(
        learning.get("procedure"), Mapping
    ):
        raise RedesignError("resident field has no learned construction procedure")
    procedure_ref = dict(learning["procedure"])
    operation_id = f"redesign:reasoning-world:{task['task_sha256'][:24]}"
    field_home = home / "field"
    with CassiFieldWorkMemory(field_home) as memory:
        field_before = memory.regional_field_receipt()
        response = memory.semantic(
            {
                "operation": "invoke-procedure",
                "operation_id": operation_id,
                "procedure_ref": procedure_ref,
                "bindings": {"role_0": task["task_sha256"]},
                "context": {
                    "source_world": task["source_world"],
                    "target_world": task["target_world"],
                    "parent_source_digest": parent_digest,
                },
            },
            operation_label=operation_id,
        )
        result = response.get("result", {})
        actions = (
            result.get("proposed_actions", [])
            if isinstance(result, Mapping)
            else []
        )
        if (
            not isinstance(result, Mapping)
            or result.get("status") != "supported"
            or not isinstance(actions, list)
            or not actions
            or any(
                not isinstance(action, Mapping)
                or action.get("candidate") != task["task_sha256"]
                for action in actions
            )
        ):
            raise RedesignError(
                "resident procedure did not transfer to paired exact reasoning"
            )
        field_after = memory.regional_field_receipt()
    fresh_status = "exception"
    fresh_actions: list[Any] = []
    with tempfile.TemporaryDirectory(
        prefix="cassimindfield-reasoning-fresh-"
    ) as temporary:
        try:
            with CassiFieldWorkMemory(Path(temporary) / "field") as fresh:
                fresh_response = fresh.semantic(
                    {
                        "operation": "invoke-procedure",
                        "operation_id": "redesign:reasoning-world:fresh",
                        "procedure_ref": procedure_ref,
                        "bindings": {"role_0": task["task_sha256"]},
                        "context": {
                            "source_world": task["source_world"],
                            "target_world": task["target_world"],
                            "parent_source_digest": parent_digest,
                        },
                    },
                    operation_label="redesign:reasoning-world:fresh",
                )
            fresh_result = fresh_response.get("result", {})
            if isinstance(fresh_result, Mapping):
                fresh_status = str(fresh_result.get("status"))
                proposed = fresh_result.get("proposed_actions")
                if isinstance(proposed, list):
                    fresh_actions = proposed
        except Exception:
            pass
    if fresh_status == "supported" or fresh_actions:
        raise RedesignError(
            "fresh field unexpectedly transferred paired reasoning procedure"
        )
    comparison = _construction_plan_search(actions)
    reasoning = _learn_reasoning_regimes(task)
    sat = reasoning["held_out"]["sat"]["selected_execution"]
    unsat = reasoning["held_out"]["unsat"]["selected_execution"]
    observed = {
        "sat_held_out": {
            "status": sat["status"],
            "evidence": "source-checked-witness"
            if sat["witness"] is not None
            else "absent",
        },
        "unsat_held_out": {
            "status": unsat["status"],
            "evidence": "independently-audited-certificate"
            if unsat["certificate"] is not None
            else "absent",
        },
    }
    expected = task["causal_prediction"]
    if observed != expected:
        raise RedesignError("paired reasoning missed its causal prediction")
    body = {
        "schema": REASONING_WORLD_SCHEMA,
        "source_generation": generation,
        "source_generation_receipt_sha256": generation_receipt["content_sha256"],
        "task": task,
        "procedure_ref": procedure_ref,
        "experienced_procedure": {
            "operation_id": operation_id,
            "status": result["status"],
            "proposed_actions": actions,
            "work": result.get("outcome", {}).get("work"),
            "field_state_before_sha256": field_before["field_state_sha256"],
            "field_state_after_sha256": field_after["field_state_sha256"],
        },
        "fresh_field_control": {
            "status": fresh_status,
            "proposed_actions": fresh_actions,
        },
        "construction_work_comparison": comparison,
        "reasoning": reasoning,
        "causal_outcome": {
            "expected": expected,
            "observed": observed,
            "matched": True,
        },
    }
    receipt = {**body, "content_sha256": digest(body)}
    _atomic_json(receipt_path, receipt)
    return {
        "status": "PASS",
        "source_generation": generation,
        "task_sha256": task["task_sha256"],
        "experienced_status": result["status"],
        "fresh_status": fresh_status,
        "construction_net_saved_steps": comparison["net_saved_steps"],
        "sat_regime": reasoning["held_out"]["sat"]["selected_regime"],
        "sat_status": sat["status"],
        "unsat_regime": reasoning["held_out"]["unsat"]["selected_regime"],
        "unsat_status": unsat["status"],
        "unsat_certificate": unsat["certificate"]["kind"],
        "unsat_field_transition_saving": reasoning[
            "unsat_field_transition_saving"
        ],
        "receipt": str(receipt_path),
        "content_sha256": receipt["content_sha256"],
    }


def verify_receipt(path: str | os.PathLike[str], workspace: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    receipt = _read(Path(path))
    _check(receipt, "content_sha256", _stable_receipt(receipt))
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise MutationRejected("unsupported redesign receipt schema")
    responsibility_continuity = receipt.get("responsibility_continuity")
    if responsibility_continuity is not None:
        if not isinstance(responsibility_continuity, Mapping):
            raise MutationRejected("receipt responsibility continuity is invalid")
        _validate_responsibility_continuity_evidence(responsibility_continuity)
    if workspace is not None:
        index = index_workspace(workspace)
        for row in receipt.get("candidates", []):
            for source in row.get("observatory_index", {}).get("files", []):
                if source.get("source_sha256") != next((item.get("source_sha256") for item in index.get("files", []) if item.get("path") == source.get("path")), None):
                    raise MutationRejected(f"source binding changed: {source.get('path')}")
    return {
        "status": "PASS",
        "generation": receipt.get("generation"),
        "content_sha256": receipt["content_sha256"],
        "candidate_count": len(receipt.get("candidates", [])),
        "selected_candidate_id": receipt.get("selected_candidate_id"),
        "responsibility_continuity_status": (
            None
            if not isinstance(responsibility_continuity, Mapping)
            else responsibility_continuity.get("status")
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-home", default=".cassimindfield-redesign")
    parser.add_argument("--campaign", action="store_true")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--rollback", type=int)
    parser.add_argument(
        "--field-owner-url",
        default=os.environ.get("CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090"),
        help="loopback entity API serving the continuing field owner",
    )
    parser.add_argument("--verify-receipt")
    parser.add_argument("--cross-world", action="store_true")
    parser.add_argument("--verify-cross-world", action="store_true")
    parser.add_argument("--constraint-world", action="store_true")
    parser.add_argument("--verify-constraint-world", action="store_true")
    parser.add_argument("--reasoning-world", action="store_true")
    parser.add_argument("--verify-reasoning-world", action="store_true")
    parser.add_argument(
        "--research-cycle",
        action="store_true",
        help="run one explicit history-continuation cycle instead of restart replay",
    )
    args = parser.parse_args()
    try:
        if args.verify_reasoning_world:
            print(
                json.dumps(
                    verify_reasoning_world_transfer(args.data_home),
                    sort_keys=True,
                )
            )
        elif args.reasoning_world:
            print(
                json.dumps(
                    run_reasoning_world_transfer(args.data_home),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        elif args.verify_constraint_world:
            print(
                json.dumps(
                    verify_constraint_world_transfer(args.data_home),
                    sort_keys=True,
                )
            )
        elif args.constraint_world:
            print(
                json.dumps(
                    run_constraint_world_transfer(args.data_home),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        elif args.verify_cross_world:
            print(
                json.dumps(
                    verify_cross_world_transfer(args.data_home),
                    sort_keys=True,
                )
            )
        elif args.cross_world:
            print(
                json.dumps(
                    run_cross_world_transfer(args.data_home),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        elif args.verify_receipt:
            print(json.dumps(verify_receipt(args.verify_receipt), sort_keys=True))
        elif args.rollback is not None:
            result = rollback(
                args.data_home,
                args.rollback,
                field_owner_url=args.field_owner_url,
            )
            print(json.dumps(result, sort_keys=True))
        elif args.replay:
            result = replay_campaign(
                args.data_home,
                field_owner_url=args.field_owner_url,
            )
            print(json.dumps(result, sort_keys=True))
        else:
            result = run_campaign(
                args.data_home,
                field_owner_url=args.field_owner_url,
                research_cycle=args.research_cycle,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (RedesignError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
