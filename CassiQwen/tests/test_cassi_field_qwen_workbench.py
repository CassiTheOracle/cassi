#!/usr/bin/env python3
"""Focused behavioral coverage for the current-CassiFI Qwen workbench boundary."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from typing import Mapping

from cassi_field_qwen_workbench import (
    COMPUTER_ID,
    FIELD_RESOURCE_FEEDBACK_SCHEMA,
    RESIDENT_BRAIN_RESOURCE_FEEDBACK_SCHEMA,
    CassiFieldWorkMemory,
    LocalQwenClient,
    WorkMemoryRecord,
)
from run_cassi_field_qwen_workcases import server_identity

from cassi_field_owner import FieldIntelligenceOwner


class CassiFieldWorkMemoryTests(unittest.TestCase):
    def test_a_redeclared_resource_policy_commits_on_an_existing_field(self) -> None:
        """A declared share rides creation and is committed again on re-open.

        Callers declare the share the field may hold.  At creation the policy
        rides the configure action; on a later open the workbench commits the
        same policy to the stored computer.  A policy that is declared but not
        committed would leave the field on its default capacity while its
        caller believes it holds the declared share, so the re-open must both
        succeed and report the declared values back.
        """

        declared = {
            "ram_bytes": 1 << 30,
            "scratch_bytes": 512 << 20,
            "transfer_bytes": 128 << 20,
            "storage_bytes": 8 << 30,
            "low_watermark": 0.25,
            "high_watermark": 0.75,
            "auto_grow": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with CassiFieldWorkMemory(root, resource_limits=declared) as memory:
                created = memory.owner.resource_limits(COMPUTER_ID).as_dict()
            self.assertEqual(
                {key: created[key] for key in declared},
                declared,
                "creation did not adopt the declared resource policy",
            )
            with CassiFieldWorkMemory(root, resource_limits=declared) as memory:
                reopened = memory.owner.resource_limits(COMPUTER_ID).as_dict()
            self.assertEqual(
                {key: reopened[key] for key in declared},
                declared,
                "re-open did not commit the declared resource policy",
            )

    def test_work_memory_opens_alongside_a_program_numerical_computer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with FieldIntelligenceOwner(root) as owner:
                owner.operate_computer(
                    "program:computer:configure",
                    computer_id="program-worker",
                    action="configure",
                )
                owner.configure_program_residency(
                    "structure", computer_id="program-worker",
                )
            with CassiFieldWorkMemory(root) as memory:
                learned = memory.learn(self._record(
                    "structure:observation:769",
                    {"workspace": "structure", "topic": "peak"},
                    {"q": 0.0173794240174152, "cell": 16912},
                    "2026-09-24T00:00:00Z",
                ))
                self.assertEqual(learned["status"], "learned")
                self.assertTrue(memory.owner.program_resources("structure")["configured"])
            with CassiFieldWorkMemory(root) as memory:
                recalled = memory.recall(
                    {"workspace": "structure", "topic": "peak"},
                    operation_label="structure:peak:reopen",
                )
                self.assertEqual(recalled["status"], "supported")
                self.assertEqual(
                    [row["source_id"] for row in recalled["records"]],
                    ["structure:observation:769"],
                )
                self.assertTrue(memory.owner.program_resources("structure")["configured"])

    def test_resident_brain_cost_is_paired_with_live_field_limits(self) -> None:
        feedback = {
            "schema": RESIDENT_BRAIN_RESOURCE_FEEDBACK_SCHEMA,
            "task_id": "resident-qwen:task",
            "operation_id": "a" * 64,
            "activity_id": "program:one",
            "model_id": "qwen-test.gguf",
            "source_sha256": "b" * 64,
            "backend": "cpu",
            "measured": {
                "elapsed_ns": 900,
                "segment_count": 3,
                "segment_work_ns": 700,
                "max_segment_ns": 300,
                "scheduler_yield_ns": 100,
                "prompt_tokens": 12,
                "completion_tokens": 4,
                "total_tokens": 16,
            },
        }
        limits = {
            "ram_bytes": 1 << 30,
            "scratch_bytes": 512 << 20,
            "transfer_bytes": 128 << 20,
            "storage_bytes": 8 << 30,
            "low_watermark": 0.25,
            "high_watermark": 0.75,
            "auto_grow": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with CassiFieldWorkMemory(
                Path(directory), resource_limits=limits
            ) as memory:
                paired = memory.resident_resource_feedback(feedback)
                with self.assertRaises(ValueError):
                    memory.resident_resource_feedback(
                        {**feedback, "schema": "unsupported"}
                    )
        self.assertEqual(paired["schema"], FIELD_RESOURCE_FEEDBACK_SCHEMA)
        self.assertEqual(paired["resident_brain"], feedback)
        self.assertEqual(
            {
                key: paired["field_computer"]["resource_limits"][key]
                for key in limits
            },
            limits,
        )
        self.assertIn("resources", paired["field_computer"])

    def test_a_faulted_semantic_request_recovers_the_regional_computer(self) -> None:
        """A faulted task must not disable every later field request.

        The regional computer keeps reporting its faulted task until it is
        restarted, so one rejected request would otherwise make every later
        semantic operation fail as well.  This drives one record to its
        declared version capacity, which faults the task inside the kernel,
        and then requires the next real operation to succeed.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fault: Exception | None = None
            with CassiFieldWorkMemory(root) as memory:
                for version in range(1, 200):
                    request = {
                        "operation": "register",
                        "operation_id": f"field-qwen:test:saturation:{version}",
                        "record_id": "test:saturation",
                        "kind": "Obligation",
                        "payload": {
                            "purpose": "saturation-probe",
                            "state": "pending",
                            "priority": 1.0,
                            "program_id": "saturation",
                            "mission": f"revision {version}",
                            "affect": {
                                "project_id": "entity-research",
                                "object_id": "saturation",
                                "novelty": 0.25,
                                "uncertainty": 1.0,
                                "controllability": 0.5,
                                "stakes": 1.0,
                            },
                        },
                        "status": "active",
                        "epistemic_kind": "asserted",
                    }
                    try:
                        memory.semantic(
                            request,
                            operation_label=f"saturation:{version}",
                        )
                    except Exception as error:
                        fault = error
                        break
                self.assertIsNotNone(
                    fault, "the semantic record never reached its version capacity"
                )
                self.assertIn("capacity", str(fault).lower())
                receipt = memory.learn(
                    self._record(
                        "atlas.release.region",
                        {"workspace": "atlas", "topic": "release"},
                        {"region": "eu-west-3"},
                        "2026-09-07T00:00:00Z",
                    )
                )
                self.assertEqual(receipt["status"], "learned")
                recall = memory.recall(
                    {"workspace": "atlas", "topic": "release"},
                    operation_label="after-recovery",
                )
                self.assertEqual(recall["status"], "supported")
                self.assertEqual(
                    [row["source_id"] for row in recall["records"]],
                    ["atlas.release.region"],
                )

    def test_capacity_growth_preserves_records_across_reopen(self) -> None:
        """A work memory that grows its field must keep the whole mind.

        The semantic state is the mind: it lives in one task region, so a
        sustained research program eventually writes past that region's
        allocation.  The instrument answers that by growing the field and
        reissuing the request that crossed the boundary; this drives the
        boundary on the production profile and then requires a reopen to
        recognize the grown field with every record still present.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registered: list[str] = []
            with CassiFieldWorkMemory(root) as memory:
                started = int(memory._computer_row().profile.mode_count)
                for index in range(120):
                    record_id = f"event:growth-test:{index:04d}"
                    memory.semantic(
                        {
                            "operation": "register",
                            "operation_id": f"{record_id}:register",
                            "record_id": record_id,
                            "kind": "Event",
                            "payload": {"probe": {"index": index, "blob": "y" * 24_000}},
                            "status": "active",
                            "epistemic_kind": "observed",
                        },
                        operation_label=f"{record_id}:register",
                    )
                    registered.append(record_id)
                    if int(memory._computer_row().profile.mode_count) != started:
                        break
                grown = int(memory._computer_row().profile.mode_count)
                self.assertGreater(
                    grown, started, "the semantic state never crossed its region"
                )
                records = (memory._computer_inspect().get("task") or {}).get("records") or {}
                self.assertEqual(
                    [name for name in registered if name not in records],
                    [],
                    "a register that crossed the growth boundary was dropped",
                )
            with CassiFieldWorkMemory(root) as reopened:
                self.assertEqual(
                    int(reopened._computer_row().profile.mode_count), grown
                )
                records = (reopened._computer_inspect().get("task") or {}).get("records") or {}
                self.assertEqual(
                    [name for name in registered if name not in records], []
                )

    def _record(
        self,
        source_id: str,
        context: Mapping[str, object],
        payload: Mapping[str, object],
        timestamp: str,
    ) -> WorkMemoryRecord:
        return WorkMemoryRecord(
            source_id=source_id,
            context=context,
            payload=payload,
            observed_timestamp=timestamp,
            labels=("local-evaluation",),
        )

    def test_typed_selection_correction_and_exact_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = {"workspace": "atlas", "topic": "release"}
            invoice = {"workspace": "atlas", "topic": "invoice"}
            first = self._record(
                "atlas.release.region",
                release,
                {"region": "eu-west-3"},
                "2026-09-07T00:00:00Z",
            )
            second = self._record(
                "atlas.release.canary",
                release,
                {"canary_percent": 7},
                "2026-09-07T00:01:00Z",
            )
            distractor = self._record(
                "atlas.invoice.tax",
                invoice,
                {"tax_percent": 17},
                "2026-09-07T00:02:00Z",
            )

            with CassiFieldWorkMemory(root) as memory:
                first_receipt = memory.learn(first)
                second_receipt = memory.learn(second)
                memory.learn(distractor)
                recall = memory.recall(release, operation_label="release-before-restart")
                self.assertEqual(recall["status"], "supported")
                self.assertEqual(
                    [row["source_id"] for row in recall["records"]],
                    ["atlas.release.canary", "atlas.release.region"],
                )
                self.assertNotIn(
                    distractor.source_id,
                    {row["source_id"] for row in recall["records"]},
                )
                canary_ref = next(
                    row["ref"]
                    for row in recall["selected_semantic_records"]
                    if row["source_revision_id"]
                    == second_receipt["source_revision_id"]
                )
                memory.register_relevance(
                    condition_id="release-source-correction",
                    condition={
                        "clauses": [
                            {
                                "field": "event_kind",
                                "operator": "equals",
                                "value": "source-correction",
                            },
                            {
                                "field": "source_id",
                                "operator": "equals",
                                "value": "atlas.release.canary",
                            },
                        ]
                    },
                    target_refs=[canary_ref],
                    reason="reconsider the release decision after correction",
                    operation_label="register-release-correction",
                )
                state_before_restart = memory.state_receipt()
                regional_before_restart = memory.regional_field_receipt()
                self.assertEqual(
                    regional_before_restart["semantic_active_bindings"],
                    3,
                )
                self.assertEqual(
                    regional_before_restart["semantic_family_counts"]["Binding"],
                    3,
                )

            with CassiFieldWorkMemory(root) as restarted:
                self.assertEqual(restarted.state_receipt(), state_before_restart)
                correction = restarted.learn(
                    self._record(
                        "atlas.release.canary",
                        release,
                        {"canary_percent": 11},
                        "2026-09-07T00:03:00Z",
                    )
                )
                self.assertEqual(correction["status"], "corrected")
                self.assertEqual(
                    correction["superseded_revision_id"],
                    second_receipt["source_revision_id"],
                )
                self.assertEqual(
                    len(
                        correction["memory_reconsideration"]["result"][
                            "wakeups"
                        ]
                    ),
                    1,
                )
                self.assertEqual(
                    correction["memory_reconsideration"]["result"][
                        "wakeups"
                    ][0]["kind"],
                    "Event",
                )
                corrected = restarted.recall(release, operation_label="release-after-correction")
                payloads = {row["source_id"]: row["payload"] for row in corrected["records"]}
                self.assertEqual(payloads["atlas.release.canary"], {"canary_percent": 11})
                self.assertEqual(payloads["atlas.release.region"], {"region": "eu-west-3"})
                self.assertNotIn(
                    second_receipt["source_revision_id"],
                    corrected["selected_source_revision_ids"],
                )
                self.assertIn(
                    first_receipt["source_revision_id"],
                    corrected["selected_source_revision_ids"],
                )
                unknown = restarted.recall(
                    {"workspace": "atlas", "topic": "unseen"},
                    operation_label="unknown-context",
                )
                self.assertEqual(unknown["records"], [])
                state = restarted.state_receipt()
                self.assertTrue(state["all_finite"])
                self.assertGreater(state["generation"], 0)
                self.assertEqual(state["active_source_revisions"], 3)
                self.assertEqual(state["all_source_revisions"], 4)
                self.assertEqual(state["revocation_generation"], 0)
                self.assertEqual(state["evidence_events"], 4)
                self.assertEqual(state["semantic_state_schema"], "cassifi.semantic-cognition-state.v1")
                self.assertEqual(state["semantic_active_bindings"], 3)

    def test_living_recall_settles_after_restart_and_expands_exact_detail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = {"workspace": "atlas", "topic": "living-memory"}
            original_payload = {
                "distinction": "the correction belongs to the canary",
                "exception": {"region": "eu-west-3", "percent": 11},
            }
            with CassiFieldWorkMemory(root) as memory:
                memory.learn(
                    self._record(
                        "atlas.living.detail",
                        context,
                        original_payload,
                        "2026-09-21T00:00:00Z",
                    )
                )
                recalled = memory.recall(
                    context, operation_label="living-recall"
                )
                episode = recalled["living_memory"]["episode"]
                binding_ref = recalled["selected_semantic_records"][0]["ref"]
                used = memory.use_recall(
                    episode_ref=episode,
                    selected_refs=[binding_ref],
                    consumer={"kind": "test-decision", "decision_id": "d1"},
                    operation_label="living-use",
                )
                pending_episode = used["result"]["episode"]
                demoted = memory.demote_memory(
                    memory_ref=binding_ref,
                    summary={"cue": "canary correction with regional exception"},
                    operation_label="living-demote",
                )
                demoted_ref = demoted["result"]["memory"]
                demoted_record = memory._semantic_record(demoted_ref)
                self.assertEqual(demoted_record["status"], "dormant")
                self.assertNotIn("source_revision_id", demoted_record["payload"])

            with CassiFieldWorkMemory(root) as restarted:
                outcome = restarted.assess_recall(
                    episode_ref=pending_episode,
                    outcome_id="living-outcome",
                    consequence={
                        "kind": "decision-reviewed",
                        "decision_id": "d1",
                    },
                    usefulness=0.75,
                    operation_label="living-outcome",
                    renewal={"strength": 0.75, "reason": "useful distinction"},
                )
                self.assertTrue(outcome["result"]["lifecycle"]["settled"])
                replay = restarted.assess_recall(
                    episode_ref=pending_episode,
                    outcome_id="living-outcome",
                    consequence={
                        "kind": "decision-reviewed",
                        "decision_id": "d1",
                    },
                    usefulness=0.75,
                    operation_label="living-outcome",
                    renewal={"strength": 0.75, "reason": "useful distinction"},
                )
                self.assertTrue(replay["result"]["replayed"])
                awareness = restarted.memory_awareness(
                    operation_label="living-awareness"
                )
                self.assertEqual(
                    awareness["result"]["awareness"],
                    "exact-detail-recoverable-and-available",
                )
                autobiography = restarted.autobiography(
                    operation_label="living-autobiography"
                )
                episode_view = autobiography["result"]["episodes"][0]
                self.assertEqual(episode_view["episode"]["id"], episode["id"])
                self.assertEqual(
                    episode_view["outcome"]["payload"]["consequence"]["decision_id"],
                    "d1",
                )
                self.assertEqual(
                    episode_view["assessment"]["payload"]["usefulness"],
                    0.75,
                )
                self.assertEqual(autobiography["result"]["unresolved"], 0)
                state_before_view = restarted.state_receipt()
                memory_view = restarted.inspect_living_memory(
                    scope={"workspace": "atlas"},
                    limit=8,
                )
                state_after_view = restarted.state_receipt()
                self.assertEqual(state_after_view, state_before_view)
                self.assertEqual(
                    memory_view["autobiography"]["episodes"][0]["episode"]["id"],
                    episode["id"],
                )
                self.assertEqual(
                    memory_view["awareness"]["awareness"],
                    "exact-detail-recoverable-and-available",
                )
                self.assertGreater(
                    memory_view["storage"]["unique_physical_bytes"],
                    0,
                )
                self.assertTrue(
                    memory_view["storage"]["recovery"]["current_owner_validated"]
                )
                self.assertEqual(
                    memory_view["circulation"]["schema"],
                    "cassifi.circulation-report.v1",
                )
                self.assertEqual(
                    memory_view["circulation"]["authority"],
                    "operational-report-only",
                )
                self.assertIn("regional_circulation", memory_view["circulation"])
                scrub = restarted.maintain_memory(
                    purpose={"kind": "integrity-scrub"},
                    allowance={"maximum_objects": 2},
                    operation_label="living-integrity-scrub",
                )
                self.assertEqual(scrub["storage_scrub"]["failures"], [])
                self.assertLessEqual(
                    scrub["storage_scrub"]["checked_objects"],
                    2,
                )
                recalled_again = restarted.recall(
                    context, operation_label="living-recall-expanded"
                )
                self.assertEqual(len(recalled_again["restored_memories"]), 1)
                self.assertEqual(recalled_again["restoration_failures"], [])
                expanded_ref = recalled_again["restored_memories"][0][
                    "expanded_ref"
                ]
                expanded_record = restarted._semantic_record(expanded_ref)
                self.assertEqual(
                    expanded_record["payload"]["schema"],
                    "cassi.field-qwen.memory-record.v2",
                )
                self.assertEqual(
                    recalled_again["records"][0]["payload"],
                    original_payload,
                )

                condition = restarted.register_relevance(
                    condition_id="canary-risk",
                    condition={
                        "clauses": [
                            {
                                "field": "canary_state",
                                "operator": "equals",
                                "value": "degraded",
                            }
                        ]
                    },
                    target_refs=[expanded_ref],
                    reason="the canary exception becomes relevant",
                    priority=0.9,
                    cooldown_events=2,
                    operation_label="living-relevance-register",
                )
                self.assertEqual(condition["result"]["status"], "supported")
                unknown = restarted.match_relevance(
                    event_id="event-without-canary-state",
                    context={},
                    maximum=8,
                    operation_label="living-relevance-unknown",
                )
                self.assertEqual(
                    unknown["result"]["unknown"][0]["missing"],
                    ["canary_state"],
                )
                matched = restarted.match_relevance(
                    event_id="event-with-degraded-canary",
                    context={"canary_state": "degraded"},
                    maximum=8,
                    operation_label="living-relevance-match",
                )
                self.assertEqual(len(matched["result"]["wakeups"]), 1)
                cooling = restarted.match_relevance(
                    event_id="event-during-cooldown",
                    context={"canary_state": "degraded"},
                    maximum=8,
                    operation_label="living-relevance-cooldown",
                )
                self.assertEqual(
                    cooling["result"]["suppressed"][0]["reason"],
                    "cooldown",
                )

    def test_a_condition_can_be_matched_for_as_long_as_it_lives(self) -> None:
        """Matching is what a relevance condition is for, so it must not be
        the thing that exhausts it: the cooldown clock and the handled-event
        list move on every match, and a record may only be revised a handful
        of times."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with CassiFieldWorkMemory(root) as memory:
                context = {"workspace": "atlas", "topic": "durable-condition"}
                memory.learn(
                    self._record(
                        "atlas.living.durable-condition",
                        context,
                        {"note": "pressure rises before the seam opens"},
                        "2026-09-21T22:00:00Z",
                    )
                )
                recalled = memory.recall(
                    context, operation_label="durable-relevance-recall"
                )
                target_ref = recalled["selected_semantic_records"][0]["ref"]
                condition = memory.register_relevance(
                    condition_id="durable-risk",
                    condition={
                        "clauses": [
                            {
                                "field": "pressure",
                                "operator": "equals",
                                "value": "high",
                            }
                        ]
                    },
                    target_refs=[target_ref],
                    reason="high pressure is relevant every time it happens",
                    priority=0.5,
                    cooldown_events=0,
                    operation_label="durable-relevance-register",
                )
                woken = 0
                for index in range(12):
                    matched = memory.match_relevance(
                        event_id=f"durable-event-{index}",
                        context={"pressure": "high"},
                        maximum=8,
                        operation_label=f"durable-relevance-match-{index}",
                    )
                    self.assertEqual(matched["result"]["status"], "supported")
                    woken += len(matched["result"]["wakeups"])
                self.assertEqual(woken, 12)
                # the condition kept one version throughout: what moved was its
                # cooldown clock and its handled-event list, not its evidence
                condition_ref = condition["result"]["condition"]
                self.assertEqual(
                    memory._semantic_record(condition_ref)["content_version"], 1
                )
                # and the mind is still whole afterwards
                again = memory.recall(
                    context, operation_label="durable-relevance-recall-again"
                )
                self.assertEqual(len(again["records"]), 1)
                self.assertEqual(again["status"], "supported")

    def test_corrupt_demoted_detail_preserves_incumbent_and_reports_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = {"workspace": "atlas", "topic": "corrupt-memory"}
            with CassiFieldWorkMemory(root) as memory:
                memory.learn(
                    self._record(
                        "atlas.living.corrupt",
                        context,
                        {"distinction": "retain the incumbent"},
                        "2026-09-21T00:00:00Z",
                    )
                )
                binding = memory._current_bindings()[0]
                binding_ref = {
                    key: binding[key]
                    for key in ("id", "kind", "content_version")
                }
                demoted = memory.demote_memory(
                    memory_ref=binding_ref,
                    summary={"cue": "incumbent survives corrupt backing"},
                    operation_label="living-corrupt-demote",
                )
                demoted_ref = demoted["result"]["memory"]
                demoted_record = memory._semantic_record(demoted_ref)
                backing_revision = demoted_record["payload"][
                    "memory_backing"
                ]["source_revision_id"]
                stored = memory.owner.evidence.source(backing_revision)
                blob = memory.owner.evidence.blobs / stored.object_sha256
                blob.write_bytes(b"corrupt")

                recalled = memory.recall(
                    context, operation_label="living-corrupt-recall"
                )

                self.assertEqual(recalled["status"], "support-gap")
                self.assertEqual(
                    recalled["restoration_failures"][0]["kind"],
                    "demoted-detail-unavailable",
                )
                incumbent = memory._semantic_record(demoted_ref)
                self.assertEqual(incumbent["status"], "dormant")
                self.assertEqual(
                    incumbent["payload"]["memory_residency"],
                    "deep-backing",
                )

    def test_regional_field_identity_is_current_and_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with CassiFieldWorkMemory(root) as memory:
                first = memory.learn(
                    self._record(
                        "atlas.release.region",
                        {"workspace": "atlas", "topic": "release"},
                        {"region": "eu-west-3"},
                        "2026-09-07T00:00:00Z",
                    )
                )
                second = memory.learn(
                    self._record(
                        "atlas.invoice.tax",
                        {"workspace": "atlas", "topic": "invoice"},
                        {"tax_percent": 17},
                        "2026-09-07T00:01:00Z",
                    )
                )
                regional = memory.regional_field_receipt()
                self.assertEqual(regional["schema"], "cassi.field-qwen.regional-field-receipt.v2")
                self.assertEqual(regional["kernel"], "cognition.field")
                self.assertEqual(regional["computer_schema"], "cassifi.learning-computer.v3")
                self.assertEqual(regional["semantic_state_schema"], "cassifi.semantic-cognition-state.v1")
                self.assertEqual(regional["semantic_active_bindings"], 2)
                self.assertEqual(regional["semantic_family_counts"]["Binding"], 2)
                self.assertEqual(regional["profile"]["mode_count"], 196608)
                self.assertEqual(regional["profile"]["directory_capacity"], 256)
                self.assertEqual(regional["task_capacity_words"], 294912)
                self.assertLess(
                    regional["task_used_words"],
                    regional["task_capacity_words"],
                )
                self.assertEqual(len(regional["profile_sha256"]), 64)
                self.assertEqual(len(regional["catalog_sha256"]), 64)
                self.assertLessEqual(
                    regional["semantic_active_bindings"],
                    regional["semantic_bounds"]["max_records"],
                )
                self.assertLessEqual(
                    regional["semantic_transitions"],
                    regional["semantic_bounds"]["max_operations"],
                )
                self.assertTrue(regional["all_finite"])
                self.assertTrue(regional["field_bytes"] > 0)

            with CassiFieldWorkMemory(root) as restarted:
                self.assertEqual(restarted.regional_field_receipt(), regional)



if __name__ == "__main__":
    unittest.main(verbosity=2)

class LocalQwenClientRequestPolicyTests(unittest.TestCase):
    """The request body is the policy a receipt later claims it used."""

    class _Recorder(LocalQwenClient):
        def __init__(self, model_path: Path) -> None:
            self.sent: list[Mapping[str, object]] = []
            super().__init__("http://127.0.0.1:8084", model_path=model_path)

        def request(self, method, path, body=None, *, timeout=600.0):
            if method == "GET":
                return 200, {"data": [{"id": str(self.model_path)}]}, "{}"
            self.sent.append(dict(body))
            if path == "/v1/chat/completions/input_tokens":
                return 200, {"object": "response.input_tokens", "input_tokens": 37}, "{}"
            return (
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"sum":21}',
                                "reasoning_content": "weigh the rows",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"completion_tokens": 5},
                    "timings": {"predicted_n": 5},
                },
                "{}",
            )

    def _client(self, directory: str) -> "LocalQwenClientRequestPolicyTests._Recorder":
        model = Path(directory) / "fixture.gguf"
        model.write_bytes(b"GGUF")
        return self._Recorder(model)

    def test_thinking_is_off_unless_asked_and_the_trace_is_returned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = self._client(directory)
            quiet = client.complete(prompt="p", max_tokens=96)
            self.assertEqual(client.sent[-1]["chat_template_kwargs"], {"enable_thinking": False})
            self.assertEqual(client.sent[-1]["reasoning_format"], "deepseek")
            self.assertFalse(quiet["thinking"])
            self.assertEqual(quiet["generation_parameters"]["max_tokens"], 96)
            self.assertEqual(quiet["generation_parameters"]["temperature"], 0)
            self.assertNotIn("messages", quiet["generation_parameters"])
            self.assertNotIn("model", quiet["generation_parameters"])
            self.assertEqual(quiet["reasoning_content"], "weigh the rows")
            self.assertEqual(quiet["finish_reason"], "stop")
            counted = client.count_completion_input_tokens(
                prompt="p",
                max_tokens=96,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "answer", "schema": {"type": "object"}},
                },
            )
            self.assertEqual(counted, 37)
            self.assertEqual(client.sent[-1]["messages"][-1]["content"], "p")
            self.assertEqual(client.sent[-1]["max_tokens"], 96)

            loud = client.complete(prompt="p", max_tokens=512, thinking=True)
            self.assertEqual(client.sent[-1]["chat_template_kwargs"], {"enable_thinking": True})
            self.assertTrue(loud["thinking"])
            self.assertEqual(loud["generation_parameters"]["max_tokens"], 512)
            self.assertEqual(
                loud["generation_parameters"]["chat_template_kwargs"],
                {"enable_thinking": True},
            )
    def test_policy_probe_catches_a_server_that_ignores_the_flag(self) -> None:
        """`/props` reports template text and jinja caps, never the thinking flag."""

        class _Server(LocalQwenClient):
            def __init__(self, model_path: Path, *, honors: bool) -> None:
                self.honors = honors
                super().__init__("http://127.0.0.1:8084", model_path=model_path)

            def request(self, method, path, body=None, *, timeout=600.0):
                if method == "GET" and path == "/v1/models":
                    return 200, {"data": [{"id": str(self.model_path)}]}, "{}"
                if method == "GET" and path == "/props":
                    return 200, {
                        "build_info": "b10472-wip9",
                        "chat_template": "{%- if enable_thinking is false %}<|end|>{%- endif %}",
                        "chat_template_caps": {"supports_tools": True, "supports_reasoning_effort": True},
                    }, "{}"
                thinking = bool((body.get("chat_template_kwargs") or {}).get("enable_thinking"))
                trace = "deliberating" if (self.honors and thinking) else ""
                return 200, {
                    "choices": [
                        {
                            "message": {"content": '{"sum":5}', "reasoning_content": trace},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"completion_tokens": 12 if trace else 4},
                }, "{}"

        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "fixture.gguf"
            model.write_bytes(b"GGUF")
            applied = _Server(model, honors=True).probe_request_policy()
            self.assertTrue(applied["flag_effective"])
            self.assertEqual(applied["probe"]["thinking_off"]["completion_tokens"], 4)
            self.assertEqual(applied["probe"]["thinking_on"]["completion_tokens"], 12)
            self.assertTrue(applied["identity"]["chat_template_has_enable_thinking"])
            self.assertEqual(len(applied["identity"]["chat_template_sha256"]), 64)
            self.assertNotIn("supports_thinking", applied["identity"]["chat_template_caps"])

            ignored = _Server(model, honors=False).probe_request_policy()
            self.assertFalse(ignored["flag_effective"])
            self.assertTrue(ignored["identity"]["chat_template_has_enable_thinking"])

    def test_identity_half_excludes_measurements(self) -> None:
        """The model block is compared across arms, so it may hold only identity."""

        probe = {
            "identity": {"build_info": "b1", "chat_template_sha256": "0" * 64},
            "probe": {"thinking_off": {"completion_tokens": 4}, "thinking_on": {"completion_tokens": 12}},
            "flag_effective": True,
        }
        identity = server_identity(probe)
        self.assertEqual(identity, probe["identity"])
        self.assertEqual(set(identity), {"build_info", "chat_template_sha256"})

        with self.assertRaises(AssertionError):
            server_identity({"identity": {"completion_tokens": 4}})
