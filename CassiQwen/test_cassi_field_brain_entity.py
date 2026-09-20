from __future__ import annotations

import http.client
import hashlib
import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from cassi_field_brain_entity import (
    BrainUnavailable,
    CapabilityApprovalRequired,
    EntityConfig,
    FieldBrainEntity,
    TurnConflict,
)
from cassi_field_qwen_workbench import WorkMemoryRecord
from cassi_field_brain_server import EntityHTTPServer



class FakeBrain:
    model_id = "fake-qwen.gguf"
    model_sha256 = "a" * 64

    def __init__(self) -> None:
        self.calls: list[Mapping[str, Any]] = []

    def complete(self, *, prompt: str, max_tokens: int, thinking: bool = False, response_format: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        self.calls.append({"prompt": prompt, "max_tokens": max_tokens, "thinking": thinking, "response_format": response_format})
        if "XI-ATTRACTOR EVIDENCE" in prompt:
            content = json.dumps(
                {
                    "contribution": "Conditional ξ saturation turns the pure-G branch into a finite dwarf-galaxy endpoint.",
                    "empirical_obligation": "Use object-level dwarf likelihoods to test whether observed boosts exceed the fixed-composition endpoint.",
                }
            )
        elif "DWARF LIKELIHOOD SPECIFICATION" in prompt:
            content = json.dumps(
                {
                    "first_action": "Acquire member-star spectroscopy, membership probabilities, binary follow-up, photometric radii, and stellar-population mass posteriors.",
                    "decision_boundary": "Reject the fixed-composition pure-G branch only when shared-data likelihood requires a boost above phi cubed.",
                }
            )
        elif "RELATION CANDIDATES" in prompt:
            content = json.dumps(
                {
                    "candidate_id": "C001",
                    "reason": "It directly joins a documented mathematical object to an empirical or open research surface.",
                }
            )
        elif (
            "attributed local theory excerpt" in prompt
            or "SOURCE SEGMENT" in prompt
            or "SEGMENT STUDIES" in prompt
        ):
            content = json.dumps(
                {
                    "summary": "The source defines the field as the continuing computational state.",
                    "open_question": "Which observable best distinguishes this claim?",
                }
            )
        elif "next_step" in prompt:
            content = json.dumps(
                {
                    "next_step": "Inspect the current field-state receipt.",
                    "reason": "It records the state reached by this commitment cycle.",
                }
            )
        elif "exactly two keys" in prompt:
            content = json.dumps(
                {
                    "question": "What measurement distinguishes the two explanations?",
                    "reason": "It resolves the active uncertainty.",
                }
            )
        else:
            content = json.dumps(
                {
                    "response": "The next useful step is to measure the distinguishing consequence."
                }
            )
        return {"content": content, "usage": {"completion_tokens": 12}}


class FailingBrain(FakeBrain):
    def complete(self, **_kwargs: Any) -> Mapping[str, Any]:
        raise RuntimeError("offline")


class ToolContinuationBrain(FakeBrain):
    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "thinking": thinking,
                "response_format": response_format,
            }
        )
        if "TOOL RESULT:" in prompt:
            content = json.dumps(
                {
                    "action": "respond",
                    "response": "The host tool supplied the current field state.",
                    "tool_name": "none",
                    "tool_arguments": "{}",
                }
            )
        else:
            content = json.dumps(
                {
                    "action": "call_tool",
                    "response": "none",
                    "tool_name": "cassi_entity_status",
                    "tool_arguments": "{}",
                }
            )
        return {"content": content, "usage": {"completion_tokens": 14}}

class FakeMemory:
    def __init__(self) -> None:
        self.records: list[Mapping[str, Any]] = []
        self.generation = 0
        self.closed = False

    def _state_sha256(self) -> str:
        return hashlib.sha256(f"state:{self.generation}".encode()).hexdigest()

    def learn(self, record: Any) -> Mapping[str, Any]:
        self.generation += 1
        revision = f"revision:{self.generation}"
        self.records.append(
            {
                "source_id": record.source_id,
                "source_revision_id": revision,
                "payload": record.payload,
                "context": record.context,
            }
        )
        return {"source_revision_id": revision, "state_sha256": self._state_sha256()}

    def recall(self, context: Mapping[str, Any], *, operation_label: str) -> Mapping[str, Any]:
        rows = [record for record in self.records if record["context"] == context]
        return {"records": rows, "field_state_after_sha256": self._state_sha256()}

    def state_receipt(self) -> Mapping[str, Any]:
        return {"field_state_sha256": self._state_sha256(), "state_sha256": self._state_sha256(), "generation": self.generation}

    def close(self) -> None:
        self.closed = True


class FieldBrainEntityTest(unittest.TestCase):
    def make_entity(self, home: Path, brain: FakeBrain | None = None, memory: FakeMemory | None = None) -> tuple[FieldBrainEntity, FakeBrain, FakeMemory]:
        actual_brain = brain or FakeBrain()
        actual_memory = memory or FakeMemory()
        return (
            FieldBrainEntity(
                EntityConfig(home, capability_root=home, theory_root=home),
                brain=actual_brain,
                memory=actual_memory,
            ),
            actual_brain,
            actual_memory,
        )
    def test_foreground_and_resident_field_calls_are_serialized(self) -> None:
        class ConcurrentMemory(FakeMemory):
            def __init__(self) -> None:
                super().__init__()
                self._active_lock = threading.Lock()
                self._active = 0
                self.max_active = 0

            def _enter(self) -> None:
                with self._active_lock:
                    self._active += 1
                    self.max_active = max(self.max_active, self._active)

            def _leave(self) -> None:
                with self._active_lock:
                    self._active -= 1

            def learn(self, record: Any) -> Mapping[str, Any]:
                self._enter()
                try:
                    time.sleep(0.03)
                    return super().learn(record)
                finally:
                    self._leave()

            def semantic(self, request: Mapping[str, Any], *, operation_label: str = "") -> Mapping[str, Any]:
                self._enter()
                try:
                    time.sleep(0.03)
                    return {"operation": request["operation"], "operation_id": request["operation_id"], "result": {}}
                finally:
                    self._leave()

        with TemporaryDirectory() as temporary:
            memory = ConcurrentMemory()
            entity, _brain, _ = self.make_entity(Path(temporary), memory=memory)
            record = WorkMemoryRecord(
                source_id="foreground-record",
                context={"conversation_id": "conversation-1"},
                payload={"kind": "message"},
                observed_timestamp="2026-09-19T00:00:00Z",
            )
            barrier = threading.Barrier(3)
            failures: list[BaseException] = []

            def run(callback: Any) -> None:
                try:
                    barrier.wait()
                    callback()
                except BaseException as exc:
                    failures.append(exc)

            threads = [
                threading.Thread(target=run, args=(lambda: entity.memory.learn(record),)),
                threading.Thread(
                    target=run,
                    args=(
                        lambda: entity.memory.semantic(
                            {"operation": "inspect", "operation_id": "resident-inspect"},
                            operation_label="resident-inspect",
                        ),
                    ),
                ),
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=2)
            entity.close()
            self.assertEqual(failures, [])
            self.assertEqual(memory.max_active, 1)


    def test_message_is_owner_admitted_then_brain_attributed_and_idempotent(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, brain, memory = self.make_entity(Path(temporary))
            request = {"request_id": "message-1", "conversation_id": "conversation-1", "project_id": "project-1", "content": "Why did the result change?", "observed_at": "2026-09-19T00:00:00Z"}
            first = entity.receive_message(**request)
            replay = entity.receive_message(**request)
            self.assertEqual(first["response"], "The next useful step is to measure the distinguishing consequence.")
            self.assertEqual(first["field_state_sha256"], hashlib.sha256(b"state:2").hexdigest())
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(len(brain.calls), 1)
            self.assertEqual(len(memory.records), 2)
            self.assertEqual(memory.records[0]["payload"]["kind"], "message")
            self.assertEqual(memory.records[1]["payload"]["kind"], "brain-response")
            self.assertIn("Why did the result change?", brain.calls[0]["prompt"])
            self.assertEqual([event["kind"] for event in entity.journal.events_after(0)], ["message-admitted", "brain-response"])


    def test_auxiliary_brain_call_is_non_learning(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, brain, memory = self.make_entity(Path(temporary))
            result = entity.auxiliary(
                request_id="auxiliary-title-1",
                purpose="session-title",
                prompt="Return a concise title for this session.",
                max_tokens=64,
            )
            self.assertEqual(result["schema"], "cassi.field-brain.auxiliary.v1")
            self.assertEqual(result["purpose"], "session-title")
            self.assertFalse(result["learning"])
            self.assertEqual(len(brain.calls), 1)
            self.assertIsNone(brain.calls[0]["response_format"])
            self.assertEqual(memory.records, [])
            self.assertEqual(entity.journal.events_after(0), [])
    def test_typed_turn_replays_as_events_and_reconciles_terminal_cancel(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, brain, memory = self.make_entity(Path(temporary))
            request = {
                "turn_id": "turn-1",
                "request_id": "message-1",
                "conversation_id": "conversation-1",
                "project_id": "project-1",
                "content": "Continue the measured investigation.",
                "kind": "user-message",
                "source": {"kind": "harness-user", "message_id": "user-1"},
                "tool_catalog": [{"name": "cassi_status"}],
                "host_scope": {"provider": "cassi-entity"},
                "observed_at": "2026-09-19T00:00:00Z",
            }
            first = entity.receive_turn(**request)
            replay = entity.receive_turn(**request)
            self.assertEqual(first["status"], "committed")
            self.assertFalse(first["idempotent_replay"])
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(len(brain.calls), 1)
            self.assertEqual(len(memory.records), 2)
            self.assertEqual(
                [event["kind"] for event in entity.turn_events("turn-1")],
                ["turn-accepted", "turn-committed"],
            )
            inspected = entity.inspect_turn("turn-1")
            self.assertEqual(inspected["turn"]["response"], first["response"])
            self.assertEqual(inspected["latest_cursor"], 2)
            cancelled = entity.cancel_turn(
                turn_id="turn-1",
                request_id="cancel-1",
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(cancelled["status"], "already-terminal")
            self.assertEqual(entity.journal.turn_latest_cursor("turn-1"), 3)
            with self.assertRaises(TurnConflict):
                entity.submit_turn_tool_results(
                    turn_id="turn-1",
                    request_id="tool-results-1",
                    results=[],
                    observed_at="2026-09-19T00:02:00Z",
                )

    def test_typed_turn_proposes_host_tool_then_commits_on_result(self) -> None:
        with TemporaryDirectory() as temporary:
            brain = ToolContinuationBrain()
            entity, _brain, memory = self.make_entity(Path(temporary), brain=brain)
            request = {
                "turn_id": "turn-tool-1",
                "request_id": "message-tool-1",
                "conversation_id": "conversation-tool-1",
                "project_id": "project-tool-1",
                "content": "Use the entity status tool, then summarize it.",
                "kind": "user-message",
                "source": {"kind": "harness-user", "message_id": "user-tool-1"},
                "tool_catalog": [
                    {
                        "name": "cassi_entity_status",
                        "description": "Read the current entity status.",
                        "parameters": {},
                    }
                ],
                "host_scope": {"provider": "cassi-entity"},
                "observed_at": "2026-09-19T00:00:00Z",
            }
            proposed = entity.receive_turn(**request)
            self.assertEqual(proposed["status"], "awaiting-tool")
            pending = proposed["pending_tool"]
            self.assertEqual(pending["name"], "cassi_entity_status")
            self.assertEqual(
                [event["kind"] for event in entity.turn_events("turn-tool-1")],
                ["turn-accepted", "turn-tool-proposed"],
            )
            large_result_text = "prefix-" + ("x" * 20_000) + "-suffix"

            tool_result = {
                "call_id": pending["call_id"],
                "name": pending["name"],
                "arguments": pending["arguments"],
                "content": [{"type": "text", "text": large_result_text}],
                "is_error": False,
            }
            committed = entity.submit_turn_tool_results(
                turn_id="turn-tool-1",
                request_id="tool-result-1",
                results=[tool_result],
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(committed["status"], "committed")
            self.assertEqual(
                committed["response"],
                "The host tool supplied the current field state.",
            )
            replay = entity.submit_turn_tool_results(
                turn_id="turn-tool-1",
                request_id="tool-result-1",
                results=[tool_result],
                observed_at="2026-09-19T00:02:00Z",
            )
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(len(brain.calls), 2)
            continuation_prompt = brain.calls[1]["prompt"]
            self.assertIn("prompt_truncated", continuation_prompt)
            self.assertIn("full_result_sha256", continuation_prompt)
            self.assertNotIn("x" * 20_000, continuation_prompt)
            self.assertEqual(
                [record["payload"]["kind"] for record in memory.records],
                ["message", "brain-response", "tool-result", "brain-response"],
            )
            self.assertEqual(
                [event["kind"] for event in entity.turn_events("turn-tool-1")],
                [
                    "turn-accepted",
                    "turn-tool-proposed",
                    "turn-tool-result-admitted",
                    "turn-committed",
                ],
            )
            self.assertEqual(entity.inspect_turn("turn-tool-1")["turn"]["tool_results"], [tool_result])

    def test_self_question_is_bounded_continuation_of_admitted_experience(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, brain, memory = self.make_entity(Path(temporary))
            entity.receive_message(request_id="message-1", conversation_id="conversation-1", project_id="project-1", content="Compare the two observations.", observed_at="2026-09-19T00:00:00Z")
            result = entity.think(request_id="thought-1", conversation_id="conversation-1", project_id="project-1", observed_at="2026-09-19T00:01:00Z")
            self.assertIn("distinguish", result["question"])
            self.assertEqual(len(brain.calls), 2)
            self.assertEqual(memory.records[-1]["payload"]["kind"], "self-question")
            self.assertEqual(entity.journal.events_after(2)[0]["kind"], "self-question")

    def test_commitment_cycle_plans_then_admits_a_real_field_observation(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, brain, memory = self.make_entity(Path(temporary))
            commitment = entity.create_commitment(
                request_id="commitment-1",
                commitment_id="continuity",
                conversation_id="conversation-1",
                project_id="project-1",
                title="Prove continuity",
                purpose="Show that the entity returns to one continuing field lifetime.",
                observed_at="2026-09-19T00:00:00Z",
            )
            cycle = entity.advance_commitment(
                request_id="cycle-1",
                commitment_id="continuity",
                conversation_id="conversation-1",
                project_id="project-1",
                observed_at="2026-09-19T00:01:00Z",
            )
            replay = entity.advance_commitment(
                request_id="cycle-1",
                commitment_id="continuity",
                conversation_id="conversation-1",
                project_id="project-1",
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(commitment["status"], "active")
            self.assertEqual(cycle["capability"], "field-state-observation")
            self.assertIn("Observe", cycle["next_step"])
            self.assertEqual(len(brain.calls), 0)
            self.assertEqual(memory.records[-1]["payload"]["kind"], "world-observation")
            self.assertEqual(
                [event["kind"] for event in entity.journal.events_after(0)],
                ["commitment-created", "commitment-cycle-planned", "world-observation"],
            )

    def test_same_request_id_rejects_changed_message(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, _brain, _memory = self.make_entity(Path(temporary))
            entity.receive_message(request_id="message-1", conversation_id="conversation-1", project_id="project-1", content="First content", observed_at="2026-09-19T00:00:00Z")
            with self.assertRaisesRegex(ValueError, "different content"):
                entity.receive_message(request_id="message-1", conversation_id="conversation-1", project_id="project-1", content="Changed content", observed_at="2026-09-19T00:00:00Z")

    def test_file_capability_requires_exact_approval_and_replays_after_restart(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            evidence = home / "evidence.txt"
            evidence.write_text("field observation", encoding="utf-8")
            entity, _brain, memory = self.make_entity(home)
            entity.create_commitment(
                request_id="commitment-1",
                commitment_id="evidence",
                conversation_id="conversation-1",
                project_id="project-1",
                title="Measure evidence",
                purpose="Produce one bounded file digest.",
                observed_at="2026-09-19T00:00:00Z",
            )
            proposal = entity.propose_capability(
                request_id="proposal-1",
                proposal_id="digest-evidence",
                commitment_id="evidence",
                conversation_id="conversation-1",
                project_id="project-1",
                capability="file-sha256",
                target_path="evidence.txt",
                observed_at="2026-09-19T00:01:00Z",
            )
            with self.assertRaises(CapabilityApprovalRequired):
                entity.execute_capability(
                    request_id="execute-1",
                    proposal_id="digest-evidence",
                    observed_at="2026-09-19T00:02:00Z",
                )
            entity.approve_capability(
                request_id="approval-1",
                proposal_id="digest-evidence",
                approved_by="test-user",
                observed_at="2026-09-19T00:03:00Z",
            )
            executed = entity.execute_capability(
                request_id="execute-1",
                proposal_id="digest-evidence",
                observed_at="2026-09-19T00:02:00Z",
            )
            restarted = FieldBrainEntity(
                EntityConfig(home, capability_root=home),
                brain=FakeBrain(),
                memory=memory,
            )
            replay = restarted.execute_capability(
                request_id="execute-1",
                proposal_id="digest-evidence",
                observed_at="2026-09-19T00:02:00Z",
            )
            self.assertEqual(proposal["status"], "pending-approval")
            self.assertEqual(executed["outcome"]["sha256"], hashlib.sha256(b"field observation").hexdigest())
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(
                [event["kind"] for event in entity.journal.events_after(0)],
                ["commitment-created", "capability-proposed", "capability-approved", "capability-executed"],
            )

    def test_theory_excerpt_is_range_bound_provenanced_and_studied(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            theory = home / "foundations.md"
            theory.write_text("Field continuity is the computational state.\nA source must remain attributable.", encoding="utf-8")
            entity, brain, memory = self.make_entity(home)
            entity.create_commitment(
                request_id="commitment-theory",
                commitment_id="study-theory",
                conversation_id="conversation-1",
                project_id="theory",
                title="Study the foundations",
                purpose="Read one attributable theory excerpt.",
                observed_at="2026-09-19T00:00:00Z",
            )
            catalog = entity.catalog_theory_documents()
            proposal = entity.propose_capability(
                request_id="proposal-theory",
                proposal_id="foundations-opening",
                commitment_id="study-theory",
                conversation_id="conversation-1",
                project_id="theory",
                capability="theory-excerpt",
                target_path="foundations.md",
                start_byte=0,
                max_bytes=34,
                observed_at="2026-09-19T00:01:00Z",
            )
            approval_surface = entity.describe_proposal("foundations-opening")
            entity.approve_capability(
                request_id="approval-theory",
                proposal_id="foundations-opening",
                approved_by="test-user",
                observed_at="2026-09-19T00:02:00Z",
            )
            execution = entity.execute_capability(
                request_id="execution-theory",
                proposal_id="foundations-opening",
                observed_at="2026-09-19T00:03:00Z",
            )
            study = entity.study_theory_excerpt(
                request_id="study-theory",
                proposal_id="foundations-opening",
                observed_at="2026-09-19T00:04:00Z",
            )
            self.assertEqual(catalog["documents"][0]["path"], "foundations.md")
            restarted = FieldBrainEntity(
                EntityConfig(home, capability_root=home, theory_root=home),
                brain=FakeBrain(),
                memory=memory,
            )
            replay = restarted.study_theory_excerpt(
                request_id="study-theory",
                proposal_id="foundations-opening",
                observed_at="2026-09-19T00:04:00Z",
            )
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(proposal["proposal_definition"]["byte_end"], 34)
            self.assertEqual(approval_surface["status"], "pending-approval")
            self.assertEqual(execution["outcome"]["content"], theory.read_bytes()[:34].decode("utf-8"))
            self.assertEqual(study["source"]["content_sha256"], execution["outcome"]["content_sha256"])
            self.assertIn("continuing computational state", study["summary"])
            self.assertEqual(memory.records[-1]["payload"]["kind"], "theory-study")
            self.assertEqual(len(brain.calls), 1)

    def test_full_theory_document_access_reads_all_segments_and_synthesizes_task(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            theory = home / "map.md"
            theory.write_text("Foundational claim.\n" * 3_000, encoding="utf-8")
            entity, brain, memory = self.make_entity(home)
            entity.assign_theory_task(
                request_id="task-1",
                task_id="map-foundations",
                conversation_id="conversation-1",
                project_id="theory",
                task="Build a source-grounded foundation map.",
                observed_at="2026-09-19T00:00:00Z",
            )
            read = entity.read_theory_document(
                request_id="read-1",
                task_id="map-foundations",
                conversation_id="conversation-1",
                project_id="theory",
                target_path="map.md",
                observed_at="2026-09-19T00:01:00Z",
            )
            study = entity.study_theory_document(
                request_id="study-1",
                task_id="map-foundations",
                conversation_id="conversation-1",
                project_id="theory",
                target_path="map.md",
                observed_at="2026-09-19T00:02:00Z",
            )
            self.assertGreater(read["segment_count"], 1)
            self.assertGreater(study["segment_count"], read["segment_count"])
            self.assertEqual(study["source_sha256"], read["source_sha256"])
            self.assertEqual(len(brain.calls), study["segment_count"] + 1)
            self.assertEqual(memory.records[-1]["payload"]["kind"], "theory-document-study")

    def test_foundational_claim_map_is_complete_citable_and_idempotent(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "foundations").mkdir()
            (home / "foundations" / "field.md").write_text(
                "# Field law\n\n## Prediction\n\n## Open question\n",
                encoding="utf-8",
            )
            (home / "reading-guide.md").write_text("# Guide\n", encoding="utf-8")
            (home / "open-questions-cassi-answers.md").write_text("# Open question\n", encoding="utf-8")
            entity, _brain, memory = self.make_entity(home)
            request = {
                "request_id": "map-1",
                "task_id": "map-foundations",
                "conversation_id": "conversation-1",
                "project_id": "theory",
                "observed_at": "2026-09-19T00:00:00Z",
            }
            result = entity.build_foundational_claim_map(**request)
            replay = entity.build_foundational_claim_map(**request)
            self.assertEqual(result["document_count"], 3)
            self.assertEqual(result["anchor_count"], 5)
            self.assertEqual(result["structural_role_counts"]["empirical-obligation"], 1)
            self.assertEqual(result["structural_role_counts"]["open-question"], 2)
            self.assertTrue(replay["idempotent_replay"])
            anchors = [
                record["payload"]["anchors"]
                for record in memory.records
                if record["payload"]["kind"] == "theory-claim-map-anchor-chunk"
            ]
            self.assertEqual(anchors[0][0]["byte_start"], 0)
            self.assertEqual(len(anchors[0][0]["content_sha256"]), 64)
            self.assertEqual(entity.journal.events_after(0)[-1]["kind"], "foundational-claim-map-built")

    def test_foundational_relation_graph_keeps_exact_hierarchy_and_references(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "foundations").mkdir()
            (home / "foundations" / "field.md").write_text(
                "# Field law\n\n## Prediction\n\nSee [questions](../open-questions-cassi-answers.md).\n",
                encoding="utf-8",
            )
            (home / "open-questions-cassi-answers.md").write_text("# Open question\n", encoding="utf-8")
            entity, _brain, memory = self.make_entity(home)
            result = entity.build_foundational_relation_graph(
                request_id="relations-1",
                task_id="map-foundations",
                conversation_id="conversation-1",
                project_id="theory",
                observed_at="2026-09-19T00:00:00Z",
            )
            self.assertEqual(result["document_count"], 2)
            self.assertEqual(result["node_count"], 3)
            self.assertEqual(result["edge_counts"], {"contains": 1, "references": 1})
            chunks = [
                record["payload"]
                for record in memory.records
                if record["payload"]["kind"] == "theory-relation-graph-chunk"
            ]
            reference = next(edge for chunk in chunks for edge in chunk["edges"] if edge["kind"] == "references")
            self.assertEqual(reference["target_source_path"], "open-questions-cassi-answers.md")
            self.assertEqual(entity.journal.events_after(0)[-1]["kind"], "foundational-relation-graph-built")

    def test_relation_synthesis_selects_a_citable_candidate(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "foundations").mkdir()
            (home / "foundations" / "field.md").write_text(
                "# Field law\n\n## Prediction\n", encoding="utf-8"
            )
            entity, brain, memory = self.make_entity(home)
            result = entity.synthesize_foundational_relation(
                request_id="relation-study-1",
                task_id="map-foundations",
                conversation_id="conversation-1",
                project_id="theory",
                observed_at="2026-09-19T00:00:00Z",
            )
            self.assertEqual(result["selected"]["candidate_id"], "C001")
            self.assertEqual(result["selected"]["source_path"], "foundations/field.md")
            self.assertIn("RELATION CANDIDATES", brain.calls[0]["prompt"])
            self.assertEqual(memory.records[-1]["payload"]["kind"], "foundational-relation-synthesis")

    def test_xi_attractor_contribution_keeps_source_spans_and_conditional_obligation(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "foundations").mkdir()
            (home / "foundations" / "xi-derivation.md").write_text(
                "## 2. Derivation\n\nξ = φ^6.\n\n## 5. Prediction\n\nTest dwarfs.\n",
                encoding="utf-8",
            )
            (home / "foundations" / "phi_attractor_synthesis.md").write_text(
                "## 2.4 The φ-Enhanced Gravitational Constant\n\nG_eff.\n\n## 13. Falsifiable Predictions\n\nDwarf test.\n",
                encoding="utf-8",
            )
            entity, _brain, memory = self.make_entity(home)
            result = entity.derive_xi_attractor_obligation(
                request_id="xi-attractor-1",
                task_id="map-foundations",
                conversation_id="conversation-1",
                project_id="theory",
                observed_at="2026-09-19T00:00:00Z",
            )
            self.assertEqual(len(result["sources"]), 2)
            self.assertIn("conditional", result["contribution"].casefold())
            payload = memory.records[-1]["payload"]
            self.assertEqual(payload["kind"], "xi-attractor-obligation")
            self.assertEqual(len(payload["sources"][0]["excerpts"][0]["content_sha256"]), 64)


    def test_dwarf_likelihood_specification_is_source_grounded_data_ready_and_idempotent(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "foundations").mkdir()
            (home / "experiments" / "phi_attractor_paths").mkdir(parents=True)
            (home / "foundations" / "phi_attractor_synthesis.md").write_text(
                "## 11. Path 9: Cassi vs MOND\n\nPure-G endpoint is phi cubed.\n\n"
                "## 13. Falsifiable Predictions\n\nObject-level likelihood required.\n",
                encoding="utf-8",
            )
            (home / "experiments" / "phi_attractor_paths" / "path10_dwarf_galaxies.py").write_text(
                "McConnachie Tables 3 and 4; M_star/L_V=1 is only a proxy.\n",
                encoding="utf-8",
            )
            entity, brain, memory = self.make_entity(home)
            request = {
                "request_id": "dwarf-spec-1",
                "task_id": "dwarf-likelihood",
                "conversation_id": "conversation-1",
                "project_id": "theory",
                "observed_at": "2026-09-19T00:00:00Z",
            }
            result = entity.build_dwarf_likelihood_spec(**request)
            replay = entity.build_dwarf_likelihood_spec(**request)
            specification = result["specification"]
            self.assertEqual(len(result["sources"]), 2)
            self.assertEqual(specification["endpoint"]["decimal"], 4.23606797749979)
            self.assertEqual(specification["candidate_frame"]["catalog_role"], "candidate frame only; its fixed M_star/L_V=1 proxies are not mass posteriors")
            self.assertIn("membership probabilities", specification["per_object_inputs"][0])
            self.assertEqual(specification["current_status"], "specification-complete; primary object-level data not yet admitted")
            self.assertTrue(replay["idempotent_replay"])
            self.assertIn("DWARF LIKELIHOOD SPECIFICATION", brain.calls[0]["prompt"])
            self.assertEqual(memory.records[-1]["payload"]["kind"], "dwarf-likelihood-specification")
            self.assertEqual(entity.journal.events_after(0)[-1]["kind"], "dwarf-likelihood-specified")

    def test_dwarf_observation_admission_hashes_primary_tables_and_reports_partial_coverage(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            source_root = home / "dwarf-likelihood-sources"
            source_root.mkdir()
            record_counts = {
                "mcconnachie2012-table3.dat": 102,
                "mcconnachie2012-table4.dat": 102,
                "segue1-simon2011-table3.dat": 522,
                "fornax-walker2009-table3.dat": 3150,
                "sculptor-walker2009-table4.dat": 1818,
                "draco-kleyna2002-table1.dat": 159,
                "segue2-kirby2013-table2.dat": 647,
                "bootes1-koposov2011-table1.dat": 118,
                "comaber-simongeha2007-velocities.dat": 102,
            }
            for filename, count in record_counts.items():
                (source_root / filename).write_bytes(b"row\n" * count)
            for filename in (
                "mcconnachie2012-ReadMe",
                "segue1-simon2011-ReadMe",
                "walker2009-ReadMe",
                "draco-kleyna2002-ReadMe",
                "segue2-kirby2013-ReadMe",
                "bootes1-koposov2011-ReadMe",
                "comaber-simon-data-page.html",
            ):
                (source_root / filename).write_text("source schema\n", encoding="utf-8")
            entity, _brain, memory = self.make_entity(home)
            request = {
                "request_id": "dwarf-sources-1",
                "task_id": "dwarf-observation-sources",
                "conversation_id": "conversation-1",
                "project_id": "theory",
                "observed_at": "2026-09-19T00:00:00Z",
            }
            result = entity.admit_dwarf_observation_sources(**request)
            replay = entity.admit_dwarf_observation_sources(**request)
            self.assertEqual(len(result["sources"]), 7)
            self.assertEqual(
                result["coverage"]["objects_with_admitted_individual_velocity_rows"],
                ("Segue 1", "Segue 2", "Bootes I", "Coma Berenices", "Draco", "Sculptor", "Fornax"),
            )
            self.assertTrue(result["coverage"]["quality_deferred_objects"]["Willman 1"].startswith("Its primary study"))
            self.assertEqual(result["sources"][4]["artifacts"][0]["record_count"], 647)
            self.assertEqual(
                result["coverage"]["status"],
                "primary-kinematics-admitted-for-seven-targets; Willman-1-quality-deferred; no likelihood or model verdict",
            )
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(memory.records[-1]["payload"]["kind"], "dwarf-observation-source-admission")
            self.assertEqual(entity.journal.events_after(0)[-1]["kind"], "dwarf-observation-sources-admitted")

    def test_dwarf_kinematic_audit_preserves_each_source_selection_rule(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            source_root = home / "dwarf-likelihood-sources"
            source_root.mkdir()

            def fixed_row(width: int, fields: Mapping[int, bytes]) -> bytes:
                row = bytearray(b" " * (width - 1) + b"\n")
                for start, value in fields.items():
                    row[start : start + len(value)] = value
                return bytes(row)

            (source_root / "segue1-simon2011-table3.dat").write_bytes(
                fixed_row(94, {4: b"same-target         ", 79: b"1"})
                + fixed_row(94, {4: b"same-target         ", 79: b"1"})
            )
            (source_root / "segue2-kirby2013-table2.dat").write_bytes(
                fixed_row(106, {93: b"Y"}) + fixed_row(106, {93: b"N"})
            )
            (source_root / "bootes1-koposov2011-table1.dat").write_bytes(
                fixed_row(84, {83: b"B"}) + fixed_row(84, {83: b" "})
            )
            (source_root / "fornax-walker2009-table3.dat").write_bytes(
                fixed_row(119, {93: b"0.250"}) + fixed_row(119, {93: b"0.900"})
            )
            (source_root / "sculptor-walker2009-table4.dat").write_bytes(fixed_row(119, {93: b"0.800"}))
            (source_root / "draco-kleyna2002-table1.dat").write_bytes(b"member\n")
            (source_root / "comaber-simongeha2007-velocities.dat").write_bytes(b"raw\n")
            entity, _brain, memory = self.make_entity(home)
            result = entity.audit_dwarf_kinematic_sources(
                request_id="dwarf-audit-1",
                task_id="dwarf-kinematic-audit",
                conversation_id="conversation-1",
                project_id="theory",
                observed_at="2026-09-19T00:00:00Z",
            )
            selection = result["audit"]["selection_audit"]
            self.assertEqual(selection["Segue 1"]["member_measurement_count"], 2)
            self.assertEqual(selection["Segue 1"]["unique_member_target_count"], 1)
            self.assertEqual(selection["Segue 2"]["member_target_count"], 1)
            self.assertEqual(selection["Bootes I"]["best_member_count"], 1)
            self.assertEqual(selection["Fornax"]["membership_score_min"], 0.25)
            self.assertEqual(selection["Coma Berenices"]["raw_row_count"], 1)
            self.assertEqual(selection["Willman 1"]["status"], "quality-deferred")
            self.assertEqual(memory.records[-1]["payload"]["kind"], "dwarf-kinematic-source-audit")
            self.assertEqual(entity.journal.events_after(0)[-1]["kind"], "dwarf-kinematic-sources-audited")

    def test_dwarf_population_evidence_admission_preserves_mass_posterior_boundary(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            source_root = home / "dwarf-likelihood-sources"
            source_root.mkdir()
            for filename in (
                "martin2008-structural-stellar-masses.pdf",
                "frebel2014-segue1-population.pdf",
                "kirby2013-segue2-population.pdf",
                "brown2014-ultrafaint-star-formation.pdf",
                "gennaro2018-coma-imf.pdf",
                "aparicio2001-draco-star-formation.pdf",
                "deboer2012-sculptor-star-formation.pdf",
                "deboer2012-fornax-star-formation.pdf",
            ):
                (source_root / filename).write_bytes(f"primary source: {filename}\n".encode("utf-8"))
            entity, _brain, memory = self.make_entity(home)
            request = {
                "request_id": "dwarf-populations-1",
                "task_id": "dwarf-stellar-populations",
                "conversation_id": "conversation-1",
                "project_id": "theory",
                "observed_at": "2026-09-19T00:00:00Z",
            }
            result = entity.admit_dwarf_stellar_population_evidence(**request)
            replay = entity.admit_dwarf_stellar_population_evidence(**request)
            registry = result["registry"]
            self.assertEqual(len(result["sources"]), 8)
            self.assertEqual(
                registry["per_object"]["Fornax"]["status"],
                "resolved population evidence admitted; published quantity is aperture-defined mass formed, not a present-day mass posterior",
            )
            self.assertEqual(
                registry["kinematic_evidence_link"]["audit_endpoint"],
                "/v1/theory/observations/dwarf-kinematics/audit",
            )
            self.assertEqual(
                registry["present_day_mass_definition"]["includes"][1],
                "gravitational mass in retained white dwarfs, neutron stars, and black holes",
            )
            segue1 = registry["source_conditioned_mass_constraints"]["Segue 1"]
            self.assertEqual(segue1["imf_conditionals"][0]["central_msun"], 600.0)
            self.assertEqual(segue1["imf_conditionals"][1]["central_msun"], 1300.0)
            self.assertIn("not an admitted", segue1["remnant_treatment"])
            draco = registry["source_conditioned_mass_constraints"]["Draco"]
            self.assertEqual(draco["aperture_conditionals"][1]["central_msun"], 430_000.0)
            self.assertIn("posterior samples", registry["posterior_input_contract"]["admission_rule"])
            self.assertFalse(registry["readiness"]["stellar_mass_posterior_ready"])
            self.assertFalse(registry["readiness"]["likelihood_ready"])
            self.assertIn("MUST NOT", registry["excluded_catalog_proxy"]["rule"])
            self.assertEqual(len(result["sources"][0]["artifact"]["sha256"]), 64)
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(memory.records[-1]["payload"]["kind"], "dwarf-stellar-population-evidence-admission")
            self.assertEqual(entity.journal.events_after(0)[-1]["kind"], "dwarf-stellar-population-evidence-admitted")

    def test_http_dwarf_population_evidence_requires_authenticated_source_bound_request(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            source_root = home / "dwarf-likelihood-sources"
            source_root.mkdir()
            for filename in (
                "martin2008-structural-stellar-masses.pdf",
                "frebel2014-segue1-population.pdf",
                "kirby2013-segue2-population.pdf",
                "brown2014-ultrafaint-star-formation.pdf",
                "gennaro2018-coma-imf.pdf",
                "aparicio2001-draco-star-formation.pdf",
                "deboer2012-sculptor-star-formation.pdf",
                "deboer2012-fornax-star-formation.pdf",
            ):
                (source_root / filename).write_bytes(b"primary source\n")
            entity, _brain, _memory = self.make_entity(home)
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
                body = json.dumps(
                    {
                        "request_id": "http-dwarf-populations-1",
                        "task_id": "dwarf-stellar-populations",
                        "conversation_id": "conversation-1",
                        "project_id": "theory",
                        "observed_at": "2026-09-19T00:00:00Z",
                    }
                )
                connection.request(
                    "POST",
                    "/v1/theory/observations/dwarf-stellar-populations",
                    body=body,
                    headers={"authorization": "Bearer " + "t" * 32, "content-type": "application/json"},
                )
                response = connection.getresponse()
                result = json.loads(response.read())
                self.assertEqual(response.status, 202)
                self.assertFalse(result["registry"]["readiness"]["likelihood_ready"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
    def test_http_foundational_claim_map_is_authenticated_and_persisted(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "foundations").mkdir()
            (home / "foundations" / "basis.md").write_text("# Basis\n", encoding="utf-8")
            (home / "reading-guide.md").write_text("# Guide\n", encoding="utf-8")
            entity, _brain, _memory = self.make_entity(home)
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
                connection.request(
                    "POST",
                    "/v1/theory/maps/foundations",
                    body=json.dumps(
                        {
                            "request_id": "http-map-1",
                            "task_id": "map-foundations",
                            "conversation_id": "conversation-1",
                            "project_id": "theory",
                            "observed_at": "2026-09-19T00:00:00Z",
                        }
                    ),
                    headers={"authorization": "Bearer " + "t" * 32, "content-type": "application/json"},
                )
                response = connection.getresponse()
                result = json.loads(response.read())
                self.assertEqual(response.status, 202)
                self.assertEqual(result["document_count"], 2)
                self.assertEqual(result["anchor_count"], 2)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_brain_failure_is_visible_and_does_not_create_a_brain_record(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, _brain, memory = self.make_entity(Path(temporary), brain=FailingBrain())
            with self.assertRaises(BrainUnavailable):
                entity.receive_message(request_id="message-1", conversation_id="conversation-1", project_id="project-1", content="Can you continue?", observed_at="2026-09-19T00:00:00Z")
            self.assertEqual([record["payload"]["kind"] for record in memory.records], ["message"])
            self.assertEqual(entity.journal.latest_cursor, 0)

    def test_http_surface_exposes_state_message_and_resumable_events(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, _brain, _memory = self.make_entity(Path(temporary))
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                connection.request("GET", "/v1/state")
                denied = connection.getresponse()
                self.assertEqual(denied.status, 401)
                denied.read()
                headers = {"authorization": "Bearer " + "t" * 32}
                connection.request("GET", "/v1/state", headers=headers)
                state = connection.getresponse()
                self.assertEqual(state.status, 200)
                self.assertEqual(json.loads(state.read())["profile"], "field-brain")
                body = json.dumps({"request_id": "message-1", "conversation_id": "conversation-1", "project_id": "project-1", "content": "Start the investigation.", "observed_at": "2026-09-19T00:00:00Z"})
                connection.request(
                    "POST",
                    "/v1/messages",
                    body=body,
                    headers={**headers, "content-type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                self.assertIn("response", json.loads(response.read()))
                connection.request("GET", "/v1/events?after=0", headers=headers)
                events = connection.getresponse()
                self.assertEqual(events.status, 200)
                streamed = events.read().decode("utf-8")
                self.assertIn("event: message-admitted", streamed)
                self.assertIn("event: brain-response", streamed)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_http_typed_turn_lifecycle_exposes_typed_events_and_terminal_control(self) -> None:
        with TemporaryDirectory() as temporary:
            entity, _brain, _memory = self.make_entity(Path(temporary))
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
                headers = {"authorization": "Bearer " + "t" * 32, "content-type": "application/json"}

                def post(path: str, value: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
                    connection.request("POST", path, body=json.dumps(value), headers=headers)
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())

                status, turn = post(
                    "/v1/turns",
                    {
                        "turn_id": "turn-http-1",
                        "request_id": "message-http-1",
                        "conversation_id": "conversation-http-1",
                        "project_id": "project-http-1",
                        "content": "Start the typed investigation.",
                        "kind": "user-message",
                        "source": {"kind": "harness-user"},
                        "tool_catalog": [],
                        "host_scope": {"provider": "cassi-entity"},
                        "observed_at": "2026-09-19T00:00:00Z",
                    },
                )
                self.assertEqual(status, 202)
                self.assertEqual(turn["status"], "committed")
                connection.request("GET", "/v1/turns/turn-http-1", headers={"authorization": headers["authorization"]})
                inspected = connection.getresponse()
                self.assertEqual(inspected.status, 200)
                self.assertEqual(json.loads(inspected.read())["turn"]["turn_id"], "turn-http-1")
                connection.request(
                    "GET",
                    "/v1/turns/turn-http-1/events?after=0",
                    headers={"authorization": headers["authorization"]},
                )
                events = connection.getresponse()
                self.assertEqual(events.status, 200)
                streamed = events.read().decode("utf-8")
                self.assertIn("event: turn-accepted", streamed)
                self.assertIn("event: turn-committed", streamed)
                cancel_status, cancelled = post(
                    "/v1/turns/turn-http-1/cancel",
                    {
                        "request_id": "cancel-http-1",
                        "observed_at": "2026-09-19T00:01:00Z",
                    },
                )
                self.assertEqual(cancel_status, 202)
                self.assertEqual(cancelled["status"], "already-terminal")
                tool_status, tool_error = post(
                    "/v1/turns/turn-http-1/tool-results",
                    {
                        "request_id": "tool-http-1",
                        "results": [],
                        "observed_at": "2026-09-19T00:02:00Z",
                    },
                )
                self.assertEqual(tool_status, 409)
                self.assertEqual(tool_error["kind"], "typed-turn-conflict")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_http_capability_execution_requires_approval(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "evidence.txt").write_text("approved observation", encoding="utf-8")
            entity, _brain, _memory = self.make_entity(home)
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
                headers = {"authorization": "Bearer " + "t" * 32, "content-type": "application/json"}

                def post(path: str, value: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
                    connection.request("POST", path, body=json.dumps(value), headers=headers)
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())

                self.assertEqual(
                    post(
                        "/v1/commitments",
                        {
                            "request_id": "commitment-1",
                            "commitment_id": "evidence",
                            "conversation_id": "conversation-1",
                            "project_id": "project-1",
                            "title": "Measure evidence",
                            "purpose": "Produce one bounded digest.",
                            "observed_at": "2026-09-19T00:00:00Z",
                        },
                    )[0],
                    202,
                )
                self.assertEqual(
                    post(
                        "/v1/capabilities/proposals",
                        {
                            "request_id": "proposal-1",
                            "proposal_id": "digest-evidence",
                            "commitment_id": "evidence",
                            "conversation_id": "conversation-1",
                            "project_id": "project-1",
                            "capability": "file-sha256",
                            "target_path": "evidence.txt",
                            "observed_at": "2026-09-19T00:01:00Z",
                            "start_byte": None,
                            "max_bytes": None,
                        },
                    )[0],
                    202,
                )
                denied_status, denied = post(
                    "/v1/capabilities/execute",
                    {
                        "request_id": "execute-1",
                        "proposal_id": "digest-evidence",
                        "observed_at": "2026-09-19T00:02:00Z",
                    },
                )
                self.assertEqual((denied_status, denied["kind"]), (403, "approval-required"))
                self.assertEqual(
                    post(
                        "/v1/capabilities/approvals",
                        {
                            "request_id": "approval-1",
                            "proposal_id": "digest-evidence",
                            "approved_by": "test-user",
                            "observed_at": "2026-09-19T00:03:00Z",
                        },
                    )[0],
                    202,
                )
                executed_status, executed = post(
                    "/v1/capabilities/execute",
                    {
                        "request_id": "execute-1",
                        "proposal_id": "digest-evidence",
                        "observed_at": "2026-09-19T00:02:00Z",
                    },
                )
                self.assertEqual(executed_status, 202)
                self.assertEqual(executed["outcome"]["sha256"], hashlib.sha256(b"approved observation").hexdigest())
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
