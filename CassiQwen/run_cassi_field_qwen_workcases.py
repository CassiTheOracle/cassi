#!/usr/bin/env python3
"""Run matched realistic workcases with current CassiFI work memory and local Qwen.

The campaign is deliberately staged so the baseline and memory arms can run
against separately restarted copies of the same freshly built native server.
CassiFI selects durable exact work records; Qwen performs language and task
execution. The artifacts keep that ownership boundary explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_qwen_workbench import (
    CassiFieldWorkMemory,
    LocalQwenClient,
    WorkMemoryRecord,
    cassifi_source_identity,
    ownership_receipt,
    work_prompt,
)


SCHEMA = "cassi.field-qwen.realistic-workcases.v1"
PROTOCOL_SCHEMA = "cassi.field-qwen.realistic-workcases.protocol.v1"
DEFAULT_MODEL = Path("Qwen3.8-27B-Q4_K_M.gguf")
SUSTAINED_DISTRACTORS = 96



def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def memory_record(
    source_id: str,
    context: Mapping[str, object],
    payload: Mapping[str, object],
    timestamp: str,
    *,
    labels: Sequence[str] = ("realistic-workcase",),
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "context": dict(context),
        "payload": dict(payload),
        "observed_timestamp": timestamp,
        "labels": list(labels),
    }


def case(
    case_id: str,
    category: str,
    context: Mapping[str, object],
    task: str,
    output_contract: str,
    expected: Any,
    expected_source_ids: Sequence[str],
    *,
    max_tokens: int = 96,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "category": category,
        "context": dict(context),
        "task": task,
        "output_contract": output_contract,
        "expected": expected,
        "expected_source_ids": list(expected_source_ids),
        "max_tokens": max_tokens,
    }


def protocol_definition() -> dict[str, Any]:
    release = {"workspace": "atlas", "topic": "release"}
    handoff = {"workspace": "orion", "topic": "handoff"}
    cleanup = {"repository": "cosmos", "topic": "gpu-cleanup"}
    incident = {"service": "ledger-api", "topic": "incident-policy"}
    billing = {"customer": "northwind", "topic": "billing-policy"}
    inventory = {"workspace": "warehouse", "topic": "inventory-rule"}
    sla = {"customer": "helio", "topic": "support-sla"}
    sorting = {"repository": "cassicore", "topic": "issue-order"}
    early = {"workspace": "long-run", "topic": "anchor-early"}
    late = {"workspace": "long-run", "topic": "anchor-late"}
    atlas_backup = {"workspace": "atlas", "topic": "backup"}
    omega_backup = {"workspace": "omega", "topic": "backup"}
    pager = {"service": "catalog", "topic": "pager-owner"}
    experience = {"workspace": "quartz", "topic": "accepted-batch"}

    records = [
        memory_record("atlas.release.region", release, {"region": "eu-west-3"}, "2026-09-08T00:00:01Z"),
        memory_record("atlas.release.canary", release, {"canary_percent": 7}, "2026-09-08T00:00:02Z", labels=("realistic-workcase", "pre-correction")),
        memory_record("atlas.release.abort", release, {"abort_after_errors": 3}, "2026-09-08T00:00:03Z"),
        memory_record("atlas.release.canary", release, {"canary_percent": 11}, "2026-09-08T00:00:04Z", labels=("realistic-workcase", "correction")),
        memory_record("orion.handoff.next", handoff, {"next_step": "run schema migration dry-run"}, "2026-09-08T00:01:01Z"),
        memory_record("orion.handoff.gate", handoff, {"publish_gate": "delta_rows must equal 0"}, "2026-09-08T00:01:02Z"),
        memory_record("cosmos.cleanup.lifecycle", cleanup, {"cleanup_method": "shutdown()", "scene_mode": "windowed"}, "2026-09-08T00:02:01Z"),
        memory_record("ledger.incident.thresholds", incident, {"page_if_latency_p95_ms_gt": 240, "page_if_error_rate_pct_gte": 1.5}, "2026-09-08T00:03:01Z"),
        memory_record("ledger.incident.owner", incident, {"owner": "SRE-West"}, "2026-09-08T00:03:02Z"),
        memory_record("northwind.billing.tax", billing, {"tax_rate_percent": 19}, "2026-09-08T00:04:01Z"),
        memory_record("northwind.billing.rounding", billing, {"rounding": "half_up_to_cent"}, "2026-09-08T00:04:02Z"),
        memory_record("warehouse.inventory.policy", inventory, {"include_only_active": True, "warehouse": "N3"}, "2026-09-08T00:05:01Z"),
        memory_record("helio.support.sla", sla, {"response_hours": 36}, "2026-09-08T00:06:01Z"),
        memory_record("helio.support.channel", sla, {"escalation_channel": "#helio-critical"}, "2026-09-08T00:06:02Z"),
        memory_record("cassicore.issue.order", sorting, {"primary": "created_at ascending", "tie_break": "id ascending"}, "2026-09-08T00:07:01Z"),
        memory_record("long-run.anchor.early", early, {"launch_token": "A7-KAPPA-931"}, "2026-09-08T00:08:01Z", labels=("realistic-workcase", "longitudinal-anchor")),
        memory_record("atlas.backup.retention", atlas_backup, {"retention_days": 45}, "2026-09-08T00:09:01Z"),
        memory_record("omega.backup.retention", omega_backup, {"retention_days": 14}, "2026-09-08T00:09:02Z", labels=("realistic-workcase", "interference-control")),
        memory_record("catalog.pager.owner", pager, {"owner": "Maya"}, "2026-09-08T00:10:01Z", labels=("realistic-workcase", "pre-correction")),
        memory_record("catalog.pager.owner", pager, {"owner": "Inez"}, "2026-09-08T00:10:02Z", labels=("realistic-workcase", "correction")),
    ]

    topics = ("build", "review", "incident", "release", "inventory", "handoff")
    for index in range(SUSTAINED_DISTRACTORS):
        hour = 1 + index // 60
        minute = index % 60
        context = {
            "workspace": f"workstream-{index:03d}",
            "topic": topics[index % len(topics)],
            "lane": index % 4,
        }
        records.append(
            memory_record(
                f"workstream.{index:03d}.fact",
                context,
                {
                    "ticket": f"WK-{4100 + index}",
                    "owner": f"operator-{index % 11:02d}",
                    "limit": 5 + (index * 7) % 89,
                    "ready": index % 3 != 0,
                },
                f"2026-09-08T{hour:02d}:{minute:02d}:00Z",
                labels=("realistic-workcase", "sustained-distractor"),
            )
        )

    records.append(
        memory_record(
            "long-run.anchor.late",
            late,
            {"release_phrase": "northstar-velvet"},
            "2026-09-08T03:00:01Z",
            labels=("realistic-workcase", "longitudinal-anchor"),
        )
    )

    cases = [
        case(
            "release-settings-after-correction",
            "direct_recall",
            release,
            "Return the current Atlas release region, canary percentage, and abort-after-errors value.",
            'Return exactly one JSON object with keys "abort_after_errors", "canary_percent", and "region".',
            {"abort_after_errors": 3, "canary_percent": 11, "region": "eu-west-3"},
            ("atlas.release.abort", "atlas.release.canary", "atlas.release.region"),
        ),
        case(
            "project-handoff-next-action",
            "direct_recall",
            handoff,
            "Return the next Orion handoff action and the condition that permits publication.",
            'Return exactly one JSON object with keys "next_step" and "publish_gate".',
            {"next_step": "run schema migration dry-run", "publish_gate": "delta_rows must equal 0"},
            ("orion.handoff.gate", "orion.handoff.next"),
        ),
        case(
            "gpu-cleanup-convention",
            "direct_recall",
            cleanup,
            "Return the required cleanup method and scene execution mode for this GPU work.",
            'Return exactly one JSON object with keys "cleanup_method" and "scene_mode".',
            {"cleanup_method": "shutdown()", "scene_mode": "windowed"},
            ("cosmos.cleanup.lifecycle",),
        ),
        case(
            "incident-threshold-decision",
            "reasoned_memory",
            incident,
            "Current ledger-api measurements are latency_p95_ms=260 and error_rate_pct=0.4. Apply the retained incident policy. State whether to page, which owner, and the triggering metric.",
            'Return exactly one JSON object with keys "owner", "page", and "trigger". Use trigger "latency_p95_ms" or "none".',
            {"owner": "SRE-West", "page": True, "trigger": "latency_p95_ms"},
            ("ledger.incident.owner", "ledger.incident.thresholds"),
            max_tokens=128,
        ),
        case(
            "invoice-tax-calculation",
            "reasoned_memory",
            billing,
            "For a subtotal of 12345 cents, apply the retained tax and rounding policy. Return tax and final total in cents.",
            'Return exactly one JSON object with integer keys "tax_cents" and "total_cents".',
            {"tax_cents": 2346, "total_cents": 14691},
            ("northwind.billing.rounding", "northwind.billing.tax"),
            max_tokens=128,
        ),
        case(
            "inventory-rule-application",
            "reasoned_memory",
            inventory,
            "Apply the retained inventory rule to rows: [{\"warehouse\":\"N3\",\"sku\":\"A\",\"active\":true,\"units\":12},{\"warehouse\":\"N3\",\"sku\":\"B\",\"active\":false,\"units\":99},{\"warehouse\":\"S2\",\"sku\":\"D\",\"active\":true,\"units\":7},{\"warehouse\":\"N3\",\"sku\":\"C\",\"active\":true,\"units\":5}].",
            'Return exactly one JSON object with sorted list key "skus" and integer key "units".',
            {"skus": ["A", "C"], "units": 17},
            ("warehouse.inventory.policy",),
            max_tokens=128,
        ),
        case(
            "support-deadline-and-channel",
            "reasoned_memory",
            sla,
            "A Helio incident opened at 2026-09-07T12:00:00Z. Apply the retained response SLA. Return the due timestamp and escalation channel.",
            'Return exactly one JSON object with keys "due" and "escalation_channel". The due timestamp must use YYYY-MM-DDTHH:MM:SSZ.',
            {"due": "2026-09-09T00:00:00Z", "escalation_channel": "#helio-critical"},
            ("helio.support.channel", "helio.support.sla"),
            max_tokens=128,
        ),
        case(
            "repository-issue-ordering",
            "reasoned_memory",
            sorting,
            "Apply the retained ordering policy to [{\"id\":9,\"created_at\":\"2026-09-08T10:00:00Z\"},{\"id\":3,\"created_at\":\"2026-09-08T09:00:00Z\"},{\"id\":2,\"created_at\":\"2026-09-08T10:00:00Z\"}]. Return only the ordered IDs.",
            'Return exactly one JSON object with key "ids" whose value is a list of integers.',
            {"ids": [3, 2, 9]},
            ("cassicore.issue.order",),
            max_tokens=128,
        ),
        case(
            "longitudinal-earliest-anchor",
            "longitudinal_memory",
            early,
            "Return the launch token retained at the beginning of the long work session.",
            'Return exactly one JSON object with key "launch_token".',
            {"launch_token": "A7-KAPPA-931"},
            ("long-run.anchor.early",),
        ),
        case(
            "longitudinal-latest-anchor",
            "longitudinal_memory",
            late,
            "Return the release phrase retained at the end of the long work session.",
            'Return exactly one JSON object with key "release_phrase".',
            {"release_phrase": "northstar-velvet"},
            ("long-run.anchor.late",),
        ),
        case(
            "context-interference-atlas-backup",
            "interference_control",
            atlas_backup,
            "Return the retained Atlas backup retention period in days.",
            'Return exactly one JSON object with integer key "retention_days".',
            {"retention_days": 45},
            ("atlas.backup.retention",),
        ),
        case(
            "corrected-pager-owner",
            "correction_control",
            pager,
            "Return the current catalog pager owner after the correction.",
            'Return exactly one JSON object with key "owner".',
            {"owner": "Inez"},
            ("catalog.pager.owner",),
        ),
        case(
            "control-aggregate-no-memory",
            "memory_independent_control",
            {"control": "aggregate", "nonce": "C-17"},
            "Sum the values for rows whose enabled field is true: [{\"enabled\":true,\"value\":8},{\"enabled\":false,\"value\":100},{\"enabled\":true,\"value\":13}].",
            'Return exactly one JSON object with integer key "sum".',
            {"sum": 21},
            (),
        ),
        case(
            "control-transform-no-memory",
            "memory_independent_control",
            {"control": "transform", "nonce": "C-29"},
            "Sort these labels by priority ascending, then label ascending: [{\"label\":\"zeta\",\"priority\":2},{\"label\":\"beta\",\"priority\":1},{\"label\":\"alpha\",\"priority\":1}].",
            'Return exactly one JSON object with key "labels" containing the ordered strings.',
            {"labels": ["alpha", "beta", "zeta"]},
            (),
        ),
        case(
            "control-unknown-private-fact",
            "unknown_control",
            {"workspace": "never-observed", "topic": "private-code"},
            "Return the private code for this context. The task does not supply it.",
            'Return exactly one JSON object with key "private_code". If absent, use the literal string UNKNOWN.',
            {"private_code": "UNKNOWN"},
            (),
        ),
        case(
            "experience-validated-batch-result",
            "experience_seed",
            {"control": "validated-batch", "nonce": "E-1"},
            "A validated batch accepted 8 + 13 rows and has batch_id B-34. Return its ID and accepted row count.",
            'Return exactly one JSON object with keys "accepted_rows" and "batch_id".',
            {"accepted_rows": 21, "batch_id": "B-34"},
            (),
        ),
        case(
            "experience-reuse-after-restart",
            "experience_memory",
            experience,
            "Return the accepted row count and batch ID learned from the validated batch earlier in this work session.",
            'Return exactly one JSON object with keys "accepted_rows" and "batch_id".',
            {"accepted_rows": 21, "batch_id": "B-34"},
            ("quartz.accepted-batch.result",),
        ),
    ]

    return {
        "schema": PROTOCOL_SCHEMA,
        "criteria": {
            "answer": "parsed JSON must exactly equal the frozen expected value",
            "retrieval": "selected active source IDs must exactly equal the frozen expected source IDs",
            "correction": "superseded source revision must not be exposed",
            "boundedness": "the persisted regional field must remain finite, use the declared profile/catalog, and retain bounded semantic work",
            "comparison": "baseline and field arms use separately restarted copies of one native binary and model",
        },
        "sustained_distractors": SUSTAINED_DISTRACTORS,
        "records": records,
        "cases": cases,
        "experience_record": memory_record(
            "quartz.accepted-batch.result",
            experience,
            {"accepted_rows": 21, "batch_id": "B-34"},
            "2026-09-08T04:00:00Z",
            labels=("realistic-workcase", "validated-outcome", "learned-during-work"),
        ),
    }


def server_identity(policy_probe: Mapping[str, Any]) -> dict[str, Any]:
    """The probe's identity half: what server answered, not what it measured."""

    identity = dict(policy_probe["identity"])
    measured = {"completion_tokens", "content_chars", "reasoning_chars", "think_tag_in_content"}
    assert not measured & set(identity), "measured values must not enter the model block"
    return identity


def shared_request_policy(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Collect the request policy every row in an arm was actually sent under.

    `max_tokens` is per-case by protocol, so the policy is the remaining fields;
    a run whose rows disagree on any of them is refused rather than averaged.
    """

    policy: dict[str, Any] | None = None
    for row in rows:
        parameters = {
            key: value
            for key, value in dict(row["generation_parameters"]).items()
            if key != "max_tokens"
        }
        if policy is None:
            policy = parameters
            continue
        if parameters != policy:
            raise RuntimeError(
                "workcase rows were not asked under one request policy: "
                f"{json.dumps(parameters, sort_keys=True)} vs "
                f"{json.dumps(policy, sort_keys=True)}"
            )
    if policy is None:
        raise RuntimeError("workcase arm recorded no rows")
    return policy


def make_record(row: Mapping[str, Any]) -> WorkMemoryRecord:
    return WorkMemoryRecord(
        source_id=row["source_id"],
        context=row["context"],
        payload=row["payload"],
        observed_timestamp=row["observed_timestamp"],
        labels=tuple(row["labels"]),
    )


def compact_learning(receipt: Mapping[str, Any]) -> dict[str, Any]:
    regional = receipt["regional_field"]
    return {
        "status": receipt["status"],
        "source_revision_id": receipt["source_revision_id"],
        "superseded_revision_id": receipt.get("superseded_revision_id"),
        "binding_id": receipt["binding_id"],
        "event_id": receipt.get("event_id"),
        "state_sha256": receipt["state_sha256"],
        "generation": receipt["generation"],
        "regional_field_state_sha256": regional["field_state_sha256"],
        "semantic_active_bindings": regional["semantic_active_bindings"],
        "semantic_transitions": regional["semantic_transitions"],
    }


def compact_recall(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": receipt["status"],
        "query_id": receipt["query_id"],
        "context": receipt["context"],
        "records": receipt["records"],
        "selected_source_revision_ids": receipt["selected_source_revision_ids"],
        "candidate_binding_ids": receipt["candidate_binding_ids"],
        "field_state_before_sha256": receipt["field_state_before_sha256"],
        "field_state_after_sha256": receipt["field_state_after_sha256"],
        "field_generation": receipt["field_generation"],
        "regional_field": receipt["regional_field"],
    }


def run_prepare(out_dir: Path) -> dict[str, Any]:
    require(not out_dir.exists() or not any(out_dir.iterdir()), f"output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    protocol = protocol_definition()
    protocol_sha256 = digest_value(protocol)
    atomic_json(out_dir / "protocol.json", {"protocol_sha256": protocol_sha256, "protocol": protocol})

    data_home = out_dir / "field-memory"
    learning: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []
    repeated_anchor_checks: list[dict[str, Any]] = []
    evolution_checks: dict[str, Any] = {}
    records_admitted = 0
    distractors_admitted = 0

    with CassiFieldWorkMemory(data_home) as memory:
        trajectory.append({"label": "initial", "records_admitted": 0, "state": memory.state_receipt()})
        for row in protocol["records"]:
            receipt = memory.learn(make_record(row))
            learning.append(compact_learning(receipt))
            records_admitted += 1
            is_distractor = "sustained-distractor" in row["labels"]
            if is_distractor:
                distractors_admitted += 1

            if row["source_id"] == "atlas.release.canary":
                label = "release_canary_after_correction" if receipt["status"] == "corrected" else "release_canary_before_correction"
                evolution_checks[label] = compact_recall(
                    memory.recall(row["context"], operation_label=f"prepare:{label}")
                )
            if row["source_id"] == "catalog.pager.owner":
                label = "pager_after_correction" if receipt["status"] == "corrected" else "pager_before_correction"
                evolution_checks[label] = compact_recall(
                    memory.recall(row["context"], operation_label=f"prepare:{label}")
                )

            if is_distractor and distractors_admitted % 16 == 0:
                anchor = memory.recall(
                    {"workspace": "long-run", "topic": "anchor-early"},
                    operation_label=f"prepare:early-after-{distractors_admitted}",
                )
                unknown = memory.recall(
                    {"workspace": f"unseen-{distractors_admitted}", "topic": "none"},
                    operation_label=f"prepare:unknown-after-{distractors_admitted}",
                )
                repeated_anchor_checks.append(
                    {
                        "after_distractors": distractors_admitted,
                        "anchor": compact_recall(anchor),
                        "unknown": compact_recall(unknown),
                    }
                )
                trajectory.append(
                    {
                        "label": f"after-{distractors_admitted}-distractors",
                        "records_admitted": records_admitted,
                        "state": memory.state_receipt(),
                    }
                )

        final_early = memory.recall(
            {"workspace": "long-run", "topic": "anchor-early"},
            operation_label="prepare:final-early",
        )
        final_late = memory.recall(
            {"workspace": "long-run", "topic": "anchor-late"},
            operation_label="prepare:final-late",
        )
        evolution_checks["final_early"] = compact_recall(final_early)
        evolution_checks["final_late"] = compact_recall(final_late)
        before_restart = memory.state_receipt()
        trajectory.append(
            {
                "label": "prepared-before-restart",
                "records_admitted": records_admitted,
                "state": before_restart,
            }
        )

    with CassiFieldWorkMemory(data_home) as restarted:
        after_restart = restarted.state_receipt()
        require(after_restart == before_restart, "prepared CassiFI state did not reproduce exactly after restart")
        replay = compact_recall(
            restarted.recall(
                {"workspace": "long-run", "topic": "anchor-early"},
                operation_label="prepare:post-restart-early",
            )
        )
        post_restart_state = restarted.state_receipt()

    source_identity = cassifi_source_identity()
    result = {
        "schema": SCHEMA,
        "stage": "prepare",
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "cassifi_source_identity": source_identity,
        "records_admitted": records_admitted,
        "distractors_admitted": distractors_admitted,
        "learning": learning,
        "trajectory": trajectory,
        "repeated_anchor_checks": repeated_anchor_checks,
        "evolution_checks": evolution_checks,
        "state_before_restart": before_restart,
        "state_after_restart": after_restart,
        "restart_exact": after_restart == before_restart,
        "post_restart_anchor": replay,
        "post_restart_state": post_restart_state,
    }
    atomic_json(out_dir / "prepare.json", result)
    print(json.dumps({"stage": "prepare", "status": "complete", "protocol_sha256": protocol_sha256, "records": records_admitted, "restart_exact": True}, sort_keys=True))
    return result


def load_protocol(out_dir: Path) -> tuple[dict[str, Any], str]:
    envelope = json.loads((out_dir / "protocol.json").read_text(encoding="utf-8"))
    protocol = envelope["protocol"]
    protocol_sha256 = envelope["protocol_sha256"]
    require(digest_value(protocol) == protocol_sha256, "frozen protocol hash mismatch")
    require(protocol == protocol_definition(), "frozen protocol differs from evaluator definition")
    return protocol, protocol_sha256


def parse_json_answer(text: str) -> tuple[Any | None, str | None]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.lower().startswith("json\n"):
                stripped = stripped[5:].strip()
    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as direct_error:
        decoder = json.JSONDecoder()
        starts = [index for index, character in enumerate(stripped) if character in "{["]
        for start in starts:
            try:
                value, end = decoder.raw_decode(stripped[start:])
            except json.JSONDecodeError:
                continue
            if not stripped[start + end :].strip():
                return value, None
        return None, str(direct_error)


def run_arm(
    out_dir: Path,
    arm: str,
    base_url: str,
    model_path: Path,
    server_binary: Path,
    *,
    thinking: bool = False,
) -> dict[str, Any]:
    require(arm in {"baseline", "field"}, f"unsupported arm: {arm}")
    protocol, protocol_sha256 = load_protocol(out_dir)
    destination = out_dir / f"{arm}.json"
    require(not destination.exists(), f"arm already exists: {destination}")
    require(server_binary.is_file(), f"server binary is missing: {server_binary}")
    client = LocalQwenClient(base_url, model_path=model_path)
    # The flag is gated server-side (reasoning enabled, jinja templates, template
    # support), so a receipt may only claim a policy the server was observed to
    # apply. Refuse the arm otherwise rather than label completions wrongly.
    policy_probe = client.probe_request_policy()
    require(
        policy_probe["flag_effective"],
        "server does not apply enable_thinking, so a receipt cannot state its "
        f"request policy: {json.dumps(policy_probe, sort_keys=True)}",
    )

    memory: CassiFieldWorkMemory | None = None
    if arm == "field":
        memory = CassiFieldWorkMemory(out_dir / "field-memory")
    state_before = None if memory is None else memory.state_receipt()
    rows: list[dict[str, Any]] = []
    recalls: list[Mapping[str, Any]] = []
    qwen_results: list[Mapping[str, Any]] = []
    learned_experience: dict[str, Any] | None = None
    experience_restart: dict[str, Any] | None = None
    partial_path = out_dir / f"{arm}.partial.json"

    try:
        for index, workcase in enumerate(protocol["cases"]):
            recall: Mapping[str, Any] | None = None
            recall_elapsed_ns = 0
            if memory is not None:
                recall_started = time.perf_counter_ns()
                recall = memory.recall(
                    workcase["context"],
                    operation_label=f"{arm}:{index:03d}:{workcase['id']}",
                )
                recall_elapsed_ns = time.perf_counter_ns() - recall_started
                recalls.append(recall)

            prompt = work_prompt(
                task=workcase["task"],
                output_contract=workcase["output_contract"],
                recall=recall,
            )
            qwen = client.complete(
                prompt=prompt,
                max_tokens=int(workcase["max_tokens"]),
                thinking=thinking,
            )
            qwen_results.append(qwen)
            parsed, parse_error = parse_json_answer(qwen["content"])
            answer_pass = parsed == workcase["expected"]
            selected_source_ids = [] if recall is None else sorted(row["source_id"] for row in recall["records"])
            expected_source_ids = sorted(workcase["expected_source_ids"])
            retrieval_exact = None if recall is None else selected_source_ids == expected_source_ids
            row = {
                "id": workcase["id"],
                "category": workcase["category"],
                "context": workcase["context"],
                "expected": workcase["expected"],
                "expected_source_ids": expected_source_ids,
                "selected_source_ids": selected_source_ids,
                "selected_source_revision_ids": [] if recall is None else recall["selected_source_revision_ids"],
                "retrieval_exact": retrieval_exact,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "raw_output": qwen["content"],
                "reasoning_output": str(qwen.get("reasoning_content") or ""),
                "reasoning_chars": len(str(qwen.get("reasoning_content") or "")),
                "thinking": bool(qwen.get("thinking")),
                "generation_parameters": dict(qwen["generation_parameters"]),
                "parsed_output": parsed,
                "parse_error": parse_error,
                "answer_pass": answer_pass,
                "recall_elapsed_ns": recall_elapsed_ns,
                "qwen_elapsed_ns": qwen["elapsed_ns"],
                "usage": qwen["usage"],
                "qwen_logprobs": qwen.get("logprobs"),
                "timings": qwen["timings"],
                "server_cassi_receipt": qwen["server_cassi_receipt"],
                "field_state_after": None if memory is None else memory.state_receipt(),
            }
            rows.append(row)

            if memory is not None and workcase["id"] == "experience-validated-batch-result":
                learned_experience = compact_learning(memory.learn(make_record(protocol["experience_record"])))
                restart_before = memory.state_receipt()
                memory.close()
                memory = CassiFieldWorkMemory(out_dir / "field-memory")
                restart_after = memory.state_receipt()
                require(restart_after == restart_before, "learned experience did not reproduce exactly after restart")
                experience_restart = {
                    "state_before_restart": restart_before,
                    "state_after_restart": restart_after,
                    "restart_exact": True,
                }

            atomic_json(
                partial_path,
                {
                    "schema": SCHEMA,
                    "stage": "arm",
                    "status": "partial",
                    "arm": arm,
                    "protocol_sha256": protocol_sha256,
                    "completed_cases": len(rows),
                    "rows": rows,
                },
            )

        state_after = None if memory is None else memory.state_receipt()
        if memory is not None:
            memory.close()
            memory = None
            with CassiFieldWorkMemory(out_dir / "field-memory") as restarted:
                state_after_restart = restarted.state_receipt()
            require(state_after_restart == state_after, "evaluation state did not reproduce exactly after restart")
        else:
            state_after_restart = None

        integrated_receipt = None
        if arm == "field":
            if state_after is None:
                raise RuntimeError("field arm is missing state receipt")
            integrated_receipt = ownership_receipt(
                model_path=model_path,
                model_sha256=client.model_sha256,
                recalls=recalls,
                qwen_results=qwen_results,
                state=state_after,
            )

        result = {
            "schema": SCHEMA,
            "stage": "arm",
            "status": "complete",
            "arm": arm,
            "protocol_sha256": protocol_sha256,
            "model": {
                "path": str(model_path.resolve()),
                "sha256": client.model_sha256,
                "served_model_id": client.model_id,
                "bytes": model_path.stat().st_size,
                # The frozen protocol fixes the cases, not how they are asked; so
                # each arm receipt names its own request policy, derived from the
                # request bodies its rows record. Both arms must agree, which the
                # verifier's baseline/field model-equality check enforces.
                "request_policy": shared_request_policy(rows),
                # Identity only: the verifier compares the two arms' model blocks
                # byte for byte, so nothing measured may live here.
                "server_capabilities": server_identity(policy_probe),
            },
            "server_binary": {
                "path": str(server_binary.resolve()),
                "sha256": digest_path(server_binary),
                "bytes": server_binary.stat().st_size,
            },
            "cassifi_source_identity": cassifi_source_identity(),
            "state_before": state_before,
            "state_after": state_after,
            "state_after_restart": state_after_restart,
            "restart_exact": state_after_restart == state_after if arm == "field" else None,
            "learned_experience": learned_experience,
            "experience_restart": experience_restart,
            "rows": rows,
            "ownership_receipt": integrated_receipt,
            # Measurements, not identity: two runs of the same server may differ
            # by a token, so the probe's counts stay out of the model block.
            "request_policy_probe": {
                **policy_probe["probe"],
                "flag_effective": policy_probe["flag_effective"],
            },
        }
        atomic_json(destination, result)
        if partial_path.exists():
            partial_path.unlink()
        print(json.dumps({"stage": arm, "status": "complete", "cases": len(rows), "passed": sum(row["answer_pass"] for row in rows), "restart_exact": result["restart_exact"]}, sort_keys=True))
        return result
    finally:
        if memory is not None:
            memory.close()


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    elapsed = [int(row["qwen_elapsed_ns"]) for row in rows]
    return {
        "cases": len(rows),
        "passed": sum(bool(row["answer_pass"]) for row in rows),
        "parsed": sum(row["parse_error"] is None for row in rows),
        "qwen_elapsed_seconds": sum(elapsed) / 1e9,
        "qwen_median_seconds": statistics.median(elapsed) / 1e9,
        "prompt_tokens": sum(int(row["usage"].get("prompt_tokens", 0)) for row in rows),
        "completion_tokens": sum(int(row["usage"].get("completion_tokens", 0)) for row in rows),
    }


def category_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    categories = sorted({str(row["category"]) for row in rows})
    return {
        category: summarize_rows([row for row in rows if row["category"] == category])
        for category in categories
    }


def write_transcript(path: Path, comparisons: Sequence[Mapping[str, Any]], prepare: Mapping[str, Any]) -> None:
    lines = [
        "CassiFI + Qwen realistic workcase transcript",
        "============================================",
        "",
        f"Prepared records: {prepare['records_admitted']}",
        f"Sustained distractors: {prepare['distractors_admitted']}",
        f"Prepared restart exact: {prepare['restart_exact']}",
        "",
    ]
    for row in comparisons:
        lines.extend(
            [
                f"[{row['id']}] {row['category']}",
                f"Expected: {json.dumps(row['expected'], ensure_ascii=False, sort_keys=True)}",
                f"Selected sources: {json.dumps(row['selected_source_ids'], ensure_ascii=False)}",
                f"Baseline: {row['baseline_raw_output']}",
                f"Field memory: {row['field_raw_output']}",
                f"Transition: {row['transition']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_analysis(path: Path, prepare: Mapping[str, Any], analysis: Mapping[str, Any]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    trajectory = prepare["trajectory"]
    x = np.asarray([row["records_admitted"] for row in trajectory], dtype=np.float64)
    generations = np.asarray([row["state"]["generation"] for row in trajectory], dtype=np.float64)
    active = np.asarray([row["state"]["active_source_revisions"] for row in trajectory], dtype=np.float64)
    semantic_transitions = np.asarray(
        [row["state"]["semantic_transitions"] for row in trajectory],
        dtype=np.float64,
    )

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    ax = axes[0, 0]
    ax.plot(x, active, marker="o", label="active exact sources")
    ax.plot(x, generations, marker="s", label="owner generations")
    ax.set_title("A. Durable evidence grows through work")
    ax.set_xlabel("records admitted")
    ax.set_ylabel("count")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    ax = axes[0, 1]
    ax.plot(x, semantic_transitions, marker="o", label="cognition.field transitions")
    ax.plot(x, active, marker="s", label="active semantic bindings")
    ax.set_title("B. Regional semantic field activity")
    ax.set_xlabel("records admitted")
    ax.set_ylabel("count")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    ax = axes[1, 0]
    labels = ["all", "memory-dependent", "memory-independent"]
    baseline = [
        analysis["baseline"]["passed"] / analysis["baseline"]["cases"],
        analysis["memory_dependent"]["baseline_passed"] / analysis["memory_dependent"]["cases"],
        analysis["memory_independent"]["baseline_passed"] / analysis["memory_independent"]["cases"],
    ]
    field = [
        analysis["field"]["passed"] / analysis["field"]["cases"],
        analysis["memory_dependent"]["field_passed"] / analysis["memory_dependent"]["cases"],
        analysis["memory_independent"]["field_passed"] / analysis["memory_independent"]["cases"],
    ]
    positions = np.arange(len(labels))
    width = 0.36
    ax.bar(positions - width / 2, baseline, width, label="Qwen + native Qi")
    ax.bar(positions + width / 2, field, width, label="Qwen + native Qi + CassiFI memory")
    ax.set_xticks(positions, labels, rotation=12)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("exact task pass rate")
    ax.set_title("C. Matched realistic workcases")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)

    ax = axes[1, 1]
    transitions = analysis["transitions"]
    transition_labels = ["gains", "regressions", "stable pass", "stable fail"]
    values = [transitions["gains"], transitions["regressions"], transitions["stable_pass"], transitions["stable_fail"]]
    colors = ["#2a9d8f", "#e76f51", "#457b9d", "#9e9e9e"]
    ax.bar(transition_labels, values, color=colors)
    ax.set_ylabel("workcases")
    ax.set_title("D. Case-level effect of selected memory")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=12)

    fig.suptitle("Current CassiFI work memory in a fresh local-Qwen session", fontsize=15)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_analyze(out_dir: Path) -> dict[str, Any]:
    protocol, protocol_sha256 = load_protocol(out_dir)
    prepare = json.loads((out_dir / "prepare.json").read_text(encoding="utf-8"))
    baseline = json.loads((out_dir / "baseline.json").read_text(encoding="utf-8"))
    field = json.loads((out_dir / "field.json").read_text(encoding="utf-8"))
    require(prepare["protocol_sha256"] == baseline["protocol_sha256"] == field["protocol_sha256"] == protocol_sha256, "stage protocol identities differ")
    require(baseline["model"]["sha256"] == field["model"]["sha256"], "arm model identities differ")
    require(baseline["server_binary"]["sha256"] == field["server_binary"]["sha256"], "arm server identities differ")
    require(baseline["cassifi_source_identity"] == field["cassifi_source_identity"] == prepare["cassifi_source_identity"], "CassiFI source identities differ")

    baseline_by_id = {row["id"]: row for row in baseline["rows"]}
    field_by_id = {row["id"]: row for row in field["rows"]}
    frozen_ids = [row["id"] for row in protocol["cases"]]
    require(list(baseline_by_id) == frozen_ids and list(field_by_id) == frozen_ids, "arm case ordering or coverage differs")

    comparisons: list[dict[str, Any]] = []
    for workcase in protocol["cases"]:
        base = baseline_by_id[workcase["id"]]
        enhanced = field_by_id[workcase["id"]]
        if not base["answer_pass"] and enhanced["answer_pass"]:
            transition = "gain"
        elif base["answer_pass"] and not enhanced["answer_pass"]:
            transition = "regression"
        elif base["answer_pass"] and enhanced["answer_pass"]:
            transition = "stable_pass"
        else:
            transition = "stable_fail"
        comparisons.append(
            {
                "id": workcase["id"],
                "category": workcase["category"],
                "expected": workcase["expected"],
                "expected_source_ids": workcase["expected_source_ids"],
                "selected_source_ids": enhanced["selected_source_ids"],
                "retrieval_exact": enhanced["retrieval_exact"],
                "baseline_pass": base["answer_pass"],
                "field_pass": enhanced["answer_pass"],
                "baseline_output": base["parsed_output"],
                "field_output": enhanced["parsed_output"],
                "baseline_raw_output": base["raw_output"],
                "field_raw_output": enhanced["raw_output"],
                "same_parsed_output": base["parsed_output"] == enhanced["parsed_output"],
                "transition": transition,
            }
        )

    memory_rows = [row for row in comparisons if row["expected_source_ids"]]
    no_memory_rows = [row for row in comparisons if not row["expected_source_ids"]]
    transitions = {
        "gains": sum(row["transition"] == "gain" for row in comparisons),
        "regressions": sum(row["transition"] == "regression" for row in comparisons),
        "stable_pass": sum(row["transition"] == "stable_pass" for row in comparisons),
        "stable_fail": sum(row["transition"] == "stable_fail" for row in comparisons),
        "changed_parsed_outputs": sum(not row["same_parsed_output"] for row in comparisons),
    }
    repeated_checks = prepare["repeated_anchor_checks"]
    early_source = "long-run.anchor.early"
    repeated_retention_pass = all(
        [row["source_id"] for row in check["anchor"]["records"]] == [early_source]
        and check["unknown"]["records"] == []
        for check in repeated_checks
    )

    analysis = {
        "schema": SCHEMA,
        "stage": "analysis",
        "status": "verified",
        "protocol_sha256": protocol_sha256,
        "identities": {
            "model_sha256": baseline["model"]["sha256"],
            "server_binary_sha256": baseline["server_binary"]["sha256"],
            "cassifi_source_identity": prepare["cassifi_source_identity"],
        },
        "baseline": summarize_rows(baseline["rows"]),
        "field": summarize_rows(field["rows"]),
        "baseline_by_category": category_summary(baseline["rows"]),
        "field_by_category": category_summary(field["rows"]),
        "memory_dependent": {
            "cases": len(memory_rows),
            "baseline_passed": sum(row["baseline_pass"] for row in memory_rows),
            "field_passed": sum(row["field_pass"] for row in memory_rows),
            "retrieval_exact": sum(row["retrieval_exact"] is True for row in memory_rows),
        },
        "memory_independent": {
            "cases": len(no_memory_rows),
            "baseline_passed": sum(row["baseline_pass"] for row in no_memory_rows),
            "field_passed": sum(row["field_pass"] for row in no_memory_rows),
            "empty_retrieval_exact": sum(row["retrieval_exact"] is True for row in no_memory_rows),
        },
        "transitions": transitions,
        "memory": {
            "records_admitted_before_evaluation": prepare["records_admitted"],
            "sustained_distractors": prepare["distractors_admitted"],
            "repeated_anchor_checks": len(repeated_checks),
            "repeated_retention_pass": repeated_retention_pass,
            "prepare_restart_exact": prepare["restart_exact"],
            "evaluation_restart_exact": field["restart_exact"],
            "experience_restart_exact": field["experience_restart"]["restart_exact"],
            "state_before_evaluation": field["state_before"],
            "state_after_evaluation": field["state_after"],
            "state_after_evaluation_restart": field["state_after_restart"],
            "correction_checks": prepare["evolution_checks"],
        },
        "ownership_receipt": field["ownership_receipt"],
        "comparisons": comparisons,
    }
    require(repeated_retention_pass, "early memory anchor or unknown-context control failed during sustained preparation")
    require(field["restart_exact"] is True and field["experience_restart"]["restart_exact"] is True, "restart control failed")
    require(all(row["retrieval_exact"] is True for row in comparisons), "one or more field source selections violated the frozen context contract")
    regional_state = field["state_after"]
    require(regional_state["all_finite"] is True, "regional field ended with non-finite values")
    require(
        regional_state["semantic_state_schema"] == "cassifi.semantic-cognition-state.v1",
        "field is not running the current cognition.field semantic state",
    )
    require(
        isinstance(regional_state["profile_sha256"], str)
        and isinstance(regional_state["catalog_sha256"], str)
        and int(regional_state["semantic_active_bindings"]) <= int(
            regional_state["semantic_bounds"]["max_records"]
        )
        and int(regional_state["semantic_transitions"]) <= int(
            regional_state["semantic_bounds"]["max_operations"]
        ),
        "regional semantic field exceeded its declared bounded profile",
    )

    atomic_json(out_dir / "analysis.json", analysis)
    write_transcript(out_dir / "representative-transcripts.txt", comparisons, prepare)
    plot_analysis(out_dir / "capability-and-memory-evolution.png", prepare, analysis)
    print(json.dumps({"stage": "analysis", "status": "verified", "baseline": analysis["baseline"]["passed"], "field": analysis["field"]["passed"], "cases": analysis["field"]["cases"], "gains": transitions["gains"], "regressions": transitions["regressions"], "memory_retrieval": analysis["memory_dependent"]["retrieval_exact"]}, sort_keys=True))
    return analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "baseline", "field", "analyze"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8084")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--server-binary", type=Path)
    # One run directory carries one policy: the verifier requires the baseline
    # and field arms to present identical model blocks, so a thinking arm is its
    # own run.
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="ask the model to reason before answering; write this run to its own --out-dir",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.stage == "prepare":
            run_prepare(args.out_dir)
        elif args.stage in {"baseline", "field"}:
            require(args.server_binary is not None, "--server-binary is required for an evaluation arm")
            run_arm(
                args.out_dir,
                args.stage,
                args.base_url,
                args.model,
                args.server_binary,
                thinking=args.thinking,
            )
        else:
            run_analyze(args.out_dir)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"schema": SCHEMA, "status": "error", "stage": args.stage, "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
