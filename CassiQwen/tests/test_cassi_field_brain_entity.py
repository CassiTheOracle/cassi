from __future__ import annotations

import http.client
import hashlib
import json
import base64
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
    EntityJournal,
    FieldBrainEntity,
    TurnConflict,
    undeclared_resource_limits,
)
from cassi_field_qwen_workbench import WorkMemoryRecord
from cassi_combined_skills import (
    LIBRARY_SCHEMA,
    SKILL_IDS,
    combined_skills_context,
    combined_skills_record,
)
from cassi_field_regions import ResidencyWait
from cassi_field_residency import ResourceLimits, ResourceWait, available_ram_bytes
from cassi_learning_computer import LearningComputerResidencyWait
from cassi_field_brain_server import EntityHTTPServer



class EntityJournalResourceTests(unittest.TestCase):
    def test_reservation_lease_fence_settlement_and_reopen(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "entity-journal.jsonl"
            journal = EntityJournal(path)
            reservation = journal.reserve_resources(
                reservation_id="reservation-a",
                mission_account_id="mission-a",
                owner_id="root",
                member_id="member-a",
                work_order_id="work-a",
                resource_class="gpu",
                cap={"gpu_slots": 1},
                capacity={"gpu_slots": 1},
                lease_expires_ns=time.time_ns() + 1_000_000_000,
            )
            self.assertEqual(reservation["lease"]["fence"], 1)
            self.assertEqual(
                journal.reserve_resources(
                    reservation_id="reservation-a",
                    mission_account_id="mission-a",
                    owner_id="root",
                    member_id="member-a",
                    work_order_id="work-a",
                    resource_class="gpu",
                    cap={"gpu_slots": 1},
                    capacity={"gpu_slots": 1},
                    lease_expires_ns=reservation["lease"]["expires_ns"],
                )["reservation_id"],
                "reservation-a",
            )
            with self.assertRaisesRegex(ValueError, "exceeds available capacity"):
                journal.reserve_resources(
                    reservation_id="reservation-b",
                    mission_account_id="mission-a",
                    owner_id="root",
                    member_id="member-b",
                    work_order_id="work-b",
                    resource_class="gpu",
                    cap={"gpu_slots": 1},
                    capacity={"gpu_slots": 1},
                    lease_expires_ns=time.time_ns() + 1_000_000_000,
                )
            settled = journal.settle_resources(
                "reservation-a",
                "settlement-a",
                measured_consumption={"gpu_slots": 1},
                status="completed",
                lease_fence=1,
            )
            cursor = journal.latest_cursor
            self.assertEqual(settled["state"], "completed")
            self.assertEqual(
                journal.settle_resources(
                    "reservation-a",
                    "settlement-a",
                    measured_consumption={"gpu_slots": 1},
                    status="completed",
                    lease_fence=1,
                ),
                settled,
            )
            self.assertEqual(journal.latest_cursor, cursor)
            reopened = EntityJournal(path)
            self.assertEqual(
                reopened.reservation("reservation-a")["state"], "completed"
            )
            second = reopened.reserve_resources(
                reservation_id="reservation-b",
                mission_account_id="mission-a",
                owner_id="root",
                member_id="member-b",
                work_order_id="work-b",
                resource_class="gpu",
                cap={"gpu_slots": 1},
                capacity={"gpu_slots": 1},
                lease_expires_ns=1,
            )
            self.assertEqual(second["state"], "reserved")
            expired = reopened.expire_resource_leases(now_ns=2)
            self.assertEqual(expired[0]["state"], "reconciliation-required")
            unreleased = reopened.reconcile_resources(
                "reservation-b", "reconcile-observe", observed_released=False,
            )
            self.assertEqual(unreleased["state"], "reconciliation-required")
            released = reopened.reconcile_resources(
                "reservation-b", "reconcile-release", observed_released=True,
            )
            self.assertEqual(released["state"], "released")


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
        elif "exactly two keys, `next_step`" in prompt:
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
            source_result = "cassi_read_source" in prompt
            content = json.dumps(
                {
                    "action": "respond",
                    "response": (
                        "The exact source bytes were admitted and interpreted."
                        if source_result
                        else "The host tool supplied the current field state."
                    ),
                    "tool_name": "none",
                    "tool_arguments": "{}",
                }
            )
        else:
            source_request = "exact source" in prompt.lower()
            content = json.dumps(
                {
                    "action": "call_tool",
                    "response": "none",
                    "tool_name": "cassi_read_source" if source_request else "cassi_entity_status",
                    "tool_arguments": (
                        json.dumps({"path": "source.md", "max_bytes": 10})
                        if source_request
                        else "{}"
                    ),
                }
            )
        return {"content": content, "usage": {"completion_tokens": 14}}


class SkillAwareToolBrain(ToolContinuationBrain):
    def count_completion_input_tokens(self, **kwargs: Any) -> int:
        return 100
    def complete(self, **kwargs: Any) -> Mapping[str, Any]:
        result = dict(super().complete(**kwargs))
        contribution = json.loads(result["content"])
        if contribution.get("action") == "call_tool":
            contribution["skill_ids"] = json.dumps([SKILL_IDS[0]])
            result["content"] = json.dumps(contribution)
        return result


class RecoverableSkillBrain(SkillAwareToolBrain):
    def __init__(self) -> None:
        super().__init__()
        self.failures_remaining = 2
        self.counted_prompts: list[str] = []

    def count_completion_input_tokens(self, **kwargs: Any) -> int:
        prompt = str(kwargs["prompt"])
        self.counted_prompts.append(prompt)
        return 900 if prompt.count('"method_id":') > 2 else 100

    def complete(self, **kwargs: Any) -> Mapping[str, Any]:
        if self.failures_remaining:
            self.failures_remaining -= 1
            self.calls.append(
                {
                    "prompt": kwargs["prompt"],
                    "max_tokens": kwargs["max_tokens"],
                    "thinking": kwargs.get("thinking", False),
                    "response_format": kwargs.get("response_format"),
                }
            )
            return {"content": "{}", "usage": {"completion_tokens": 1}}
        return super().complete(**kwargs)


class FakeMemory:
    def __init__(self) -> None:
        self.records: list[Mapping[str, Any]] = []
        self.generation = 0
        self.closed = False
        self.recall_uses: list[Mapping[str, Any]] = []
        self.recall_cancellations: list[Mapping[str, Any]] = []
        self.recall_assessments: list[Mapping[str, Any]] = []
        self.combined_skill_events: list[Mapping[str, Any]] = []

    def _state_sha256(self) -> str:
        return hashlib.sha256(f"state:{self.generation}".encode()).hexdigest()

    def learn(self, record: Any) -> Mapping[str, Any]:
        document = dict(record.document())
        if record.payload.get("kind") == "taught-combined-skills":
            self.combined_skill_events.append(
                {"operation": "learn", "source_id": record.source_id}
            )
        digest = hashlib.sha256(
            json.dumps(document, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        existing_index = next(
            (
                index
                for index, row in enumerate(self.records)
                if row["source_id"] == record.source_id
            ),
            None,
        )
        if existing_index is not None:
            existing = self.records[existing_index]
            if existing.get("record_sha256") == digest:
                return {
                    "source_revision_id": existing["source_revision_id"],
                    "state_sha256": self._state_sha256(),
                    "status": "unchanged",
                }
        self.generation += 1
        revision = f"revision:{self.generation}"
        row = {
            "source_id": record.source_id,
            "source_revision_id": revision,
            "payload": record.payload,
            "context": record.context,
            "observed_timestamp": record.observed_timestamp,
            "record_sha256": digest,
        }
        if existing_index is None:
            self.records.append(row)
        else:
            self.records[existing_index] = row
        return {
            "source_revision_id": revision,
            "state_sha256": self._state_sha256(),
            "status": "stored",
        }

    def recall(self, context: Mapping[str, Any], *, operation_label: str) -> Mapping[str, Any]:
        rows = [record for record in self.records if record["context"] == context]
        if context.get("scope") == "combined-skills":
            self.combined_skill_events.append(
                {"operation": "recall", "context": dict(context)}
            )
        if context.get("scope") != "combined-skills":
            return {"records": rows, "field_state_after_sha256": self._state_sha256()}
        episode = {
            "episode_id": f"episode:{operation_label}",
            "content_version": 1,
            "project_id": context["project_id"],
        }
        selected = [
            {
                "source_revision_id": row["source_revision_id"],
                "ref": {
                    "id": row["source_revision_id"],
                    "kind": "work-memory-record",
                    "content_version": 1,
                },
            }
            for row in rows
        ]
        return {
            "context": dict(context),
            "status": "supported" if rows else "support-gap",
            "records": rows,
            "selected_semantic_records": selected,
            "living_memory": {"episode": episode},
            "field_state_after_sha256": self._state_sha256(),
        }

    def use_recall(
        self,
        *,
        episode_ref: Mapping[str, Any],
        selected_refs: list[Mapping[str, Any]],
        consumer: Mapping[str, Any],
        operation_label: str,
    ) -> Mapping[str, Any]:
        self.recall_uses.append(
            {
                "episode_ref": dict(episode_ref),
                "selected_refs": list(selected_refs),
                "consumer": dict(consumer),
                "operation_label": operation_label,
            }
        )
        current_episode = {
            **dict(episode_ref),
            "content_version": int(episode_ref.get("content_version", 1)) + 1,
        }
        return {
            "result": {
                "episode": current_episode,
                "use": {"use_id": f"use:{operation_label}"},
            }
        }

    def cancel_recall(
        self,
        *,
        episode_ref: Mapping[str, Any],
        reason: Mapping[str, Any],
        operation_label: str,
    ) -> Mapping[str, Any]:
        self.recall_cancellations.append(
            {
                "episode_ref": dict(episode_ref),
                "reason": dict(reason),
                "operation_label": operation_label,
            }
        )
        return {"status": "cancelled"}

    def assess_recall(
        self,
        *,
        episode_ref: Mapping[str, Any],
        outcome_id: str,
        consequence: Mapping[str, Any],
        usefulness: float,
        operation_label: str,
    ) -> Mapping[str, Any]:
        self.recall_assessments.append(
            {
                "episode_ref": dict(episode_ref),
                "outcome_id": outcome_id,
                "consequence": dict(consequence),
                "usefulness": usefulness,
                "operation_label": operation_label,
            }
        )
        return {"outcome_id": outcome_id, "status": "assessed"}

    def state_receipt(self) -> Mapping[str, Any]:
        return {
            "field_state_sha256": self._state_sha256(),
            "state_sha256": self._state_sha256(),
            "generation": self.generation,
        }

    def inspect_living_memory(
        self,
        *,
        scope: Mapping[str, Any] | str | None = None,
        limit: int = 32,
        include_unsettled: bool = True,
    ) -> Mapping[str, Any]:
        return {
            "schema": "cassi.field-qwen.living-memory-view.v1",
            "field_state_sha256": self._state_sha256(),
            "field_generation": self.generation,
            "awareness": {
                "awareness": "no-support-located-within-searched-scope",
                "scope": scope,
            },
            "autobiography": {
                "episodes": [],
                "limit": limit,
                "include_unsettled": include_unsettled,
            },
            "storage": {"unique_physical_bytes": 0},
        }

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
    def test_default_brain_context_matches_live_qwen_context(self) -> None:
        with TemporaryDirectory() as temporary:
            config = EntityConfig(Path(temporary), capability_root=Path(temporary))
            self.assertEqual(config.brain_context_tokens, 32_768)

    def test_an_undeclared_policy_sizes_its_share_to_this_machine(self) -> None:
        """With nothing declared, the share follows this machine's own room.

        The resident backend loads model stages into this process, so the
        policy defaults (a 64 MiB RAM share) leave every resident fetch waiting
        while the machine has gigabytes free.
        """

        limits = undeclared_resource_limits()
        policy = ResourceLimits.from_dict(limits)
        self.assertEqual(policy.ram_bytes, limits["ram_bytes"])
        self.assertGreater(limits["ram_bytes"], 64 * 1024 * 1024)
        self.assertGreaterEqual(limits["ram_bytes"], 128 * 1024 * 1024)
        self.assertLessEqual(limits["ram_bytes"], 8 * 1024 * 1024 * 1024)
        self.assertGreaterEqual(limits["max_logical_bytes"], limits["ram_bytes"])
        available = available_ram_bytes()
        if available // 2 >= 128 * 1024 * 1024:
            self.assertLessEqual(limits["ram_bytes"], available)

    def test_a_declared_resource_policy_sizes_the_owner_capacity(self) -> None:
        """A declared policy sizes the owner's own capacity, and opens either way.

        The owner's ceiling defaults are slot descriptors on their dataclass, so
        reading them off the class yields a member descriptor that int() rejects:
        an entity whose declared policy omitted the logical ceiling failed to
        open at all.  Both shapes must open, and a declared ceiling must reach
        the owner.
        """

        declared = 256 * 1024 * 1024
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            declared_entity = FieldBrainEntity(
                EntityConfig(
                    home / "declared",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=home,
                    resource_limits={
                        "ram_bytes": declared,
                        "max_logical_bytes": declared,
                    },
                ),
                brain=FakeBrain(),
            )
            try:
                limits = declared_entity.memory._memory.owner.limits
                self.assertEqual(limits.max_state_bytes, declared)
                self.assertEqual(limits.max_workspace_bytes, declared)
            finally:
                declared_entity.close()

            fallback_entity = FieldBrainEntity(
                EntityConfig(
                    home / "fallback",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=home,
                    resource_limits={"ram_bytes": declared},
                ),
                brain=FakeBrain(),
            )
            try:
                limits = fallback_entity.memory._memory.owner.limits
                self.assertIsInstance(limits.max_state_bytes, int)
                self.assertGreater(limits.max_state_bytes, 0)
                self.assertGreater(limits.max_workspace_bytes, 0)
            finally:
                fallback_entity.close()

    def test_a_declared_policy_reaches_the_program_computer(self) -> None:
        """The share a caller declares is the share staged work runs under.

        A resident-model turn stages the model through the member's program
        computer.  Left on the policy defaults that computer keeps a 64 MiB
        RAM share while the field's declaration sits on the work memory, so
        every page of the stage waits on a machine with gigabytes free.
        """

        declared = 320 * 1024 * 1024
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            entity = FieldBrainEntity(
                EntityConfig(
                    home / "declared",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=home,
                    resource_limits={
                        "ram_bytes": declared,
                        "max_logical_bytes": declared,
                    },
                ),
                brain=FakeBrain(),
            )
            try:
                owner = entity._program_owner
                self.assertIsNotNone(owner)
                resources = owner.computer_resources(entity._program_computer_id)
                policy = resources["resource_limits"]
                self.assertEqual(policy["ram_bytes"], declared)
                self.assertEqual(policy["max_logical_bytes"], declared)
                self.assertEqual(
                    resources["resources"]["budget_bytes"]["ram"], declared
                )
            finally:
                entity.close()

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


    def test_shared_brain_serializes_and_background_runs_within_foreground_burst(self) -> None:
        class ScheduledBrain(FakeBrain):
            def __init__(self) -> None:
                super().__init__()
                self.started: list[str] = []
                self.active = 0
                self.max_active = 0
                self.guard = threading.Lock()
                self.blocker_started = threading.Event()
                self.release_blocker = threading.Event()

            def complete(self, **kwargs: Any) -> Mapping[str, Any]:
                prompt = str(kwargs["prompt"])
                with self.guard:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                    self.started.append(prompt)
                try:
                    if prompt == "blocker":
                        self.blocker_started.set()
                        self.release_blocker.wait(timeout=5)
                    else:
                        time.sleep(0.01)
                    return {"content": '{"response":"ok"}', "usage": {}}
                finally:
                    with self.guard:
                        self.active -= 1

        with TemporaryDirectory() as temporary:
            raw_brain = ScheduledBrain()
            entity, _brain, _memory = self.make_entity(
                Path(temporary), brain=raw_brain
            )
            failures: list[BaseException] = []

            def complete(label: str) -> None:
                try:
                    entity.brain.complete(
                        prompt=label,
                        max_tokens=8,
                        response_format=None,
                    )
                except BaseException as exc:
                    failures.append(exc)

            blocker = threading.Thread(target=complete, args=("blocker",))
            blocker.start()
            self.assertTrue(raw_brain.blocker_started.wait(timeout=2))
            background = threading.Thread(
                target=complete,
                args=("background",),
                name="cassi-autonomous-researcher",
            )
            foreground = [
                threading.Thread(target=complete, args=(f"foreground-{index}",))
                for index in range(4)
            ]
            background.start()
            for thread in foreground:
                thread.start()
            time.sleep(0.05)
            raw_brain.release_blocker.set()
            blocker.join(timeout=5)
            background.join(timeout=5)
            for thread in foreground:
                thread.join(timeout=5)
            self.assertEqual(failures, [])
            self.assertEqual(raw_brain.max_active, 1)
            self.assertIn("background", raw_brain.started)
            self.assertLessEqual(raw_brain.started.index("background"), 3)

    def test_entity_allocation_controls_and_final_settlement_share_one_journal(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            workspace = Path(__file__).resolve().parents[2]
            entity = FieldBrainEntity(
                EntityConfig(
                    home / "entity",
                    capability_root=workspace,
                    theory_root=workspace / "CassiTheory",
                    research_home=home / "research",
                    research_roots=(home,),
                    research_resident_enabled=False,
                    research_organism_member_ids=("member-a",),
                    research_organism_profile={
                        "program_capacity": 64,
                        "stack_capacity": 64,
                        "max_steps": 4096,
                    },
                    research_resource_capacity={"resident_steps": 2},
                ),
                brain=FakeBrain(),
            )
            journal_path = entity.journal.path
            try:
                allocation = entity.allocate_research_resources(
                    allocation_id="allocation-a",
                    reservation_id="reservation-a",
                    mission_account_id="mission-a",
                    work_order_id="work-a",
                    member_id="member-a",
                    objective={"goal": "advance independent resident work"},
                    budgets={"resident_steps": 1},
                    scientific_relevance={
                        "question": "Can the member advance independently?",
                        "expected_information_gain": 1.0,
                    },
                )
                self.assertEqual(allocation["reservation_id"], "reservation-a")
                self.assertEqual(
                    entity.journal.reservation("reservation-a")["state"],
                    "reserved",
                )
                paused = entity.control_research_member(
                    control_id="pause-a",
                    member_id="member-a",
                    action="pause",
                    reason="hold a reproducible continuation",
                )
                self.assertEqual(paused["state"], "paused")
                resumed = entity.control_research_member(
                    control_id="resume-a",
                    member_id="member-a",
                    action="resume",
                    reason="continue the admitted work",
                )
                self.assertEqual(resumed["state"], "active")
                affect_receipt = entity.report_research_affect(
                    message_id="affect-a",
                    sender_instance_id="member-a",
                    recipient_scope="root",
                    report_kind="concern",
                    interpretation_status="tentative",
                    requested_help={"kind": "check-assumption"},
                    content={"uncertainty": "the continuation may be incomplete"},
                    applicability={"allocation_id": "allocation-a"},
                    question_ref={"owner": "member-a", "id": "question-a"},
                    evidence_roots=(),
                    visibility_refs=(),
                )
                self.assertEqual(
                    affect_receipt["receipt_ref"]["kind"], "Event",
                )
                advanced = entity.researcher.run_organism_one()
                self.assertIsNotNone(advanced)
                reservation = entity.journal.reservation("reservation-a")
                self.assertEqual(reservation["state"], "completed")
                self.assertEqual(
                    reservation["measured_consumption"],
                    {"resident_steps": 1},
                )
                collaboration = entity.research_collaboration()
                self.assertEqual(
                    collaboration["resource_allocations"][0]["state"],
                    "completed",
                )
                self.assertEqual(len(collaboration["affect_reports"]), 1)
            finally:
                entity.close()
            reopened = EntityJournal(journal_path)
            self.assertEqual(
                reopened.reservation("reservation-a")["state"], "completed",
            )

    def test_collective_investigations_reach_researcher_status_and_brain(
        self,
    ) -> None:
        analysis_gap = {
            "kind": "missing-input-binding",
            "port": "analysis",
            "expected": {
                "name": "analysis",
                "value_kind": "scalar",
                "representation": "analysis",
                "unit": "score",
                "symbol": "analysis_value",
            },
        }
        evidence_gap = {
            "kind": "missing-input-binding",
            "port": "evidence",
            "expected": {
                "name": "evidence",
                "value_kind": "scalar",
                "representation": "evidence",
                "unit": "score",
                "symbol": "evidence_value",
            },
        }

        class InvestigationOrganism:
            def collaboration_view(self) -> Mapping[str, Any]:
                return {
                    "investigations": [
                        {
                            "synthesis_id": "synthesis-assembling",
                            "request_id": "request-assembling",
                            "state": "assembling",
                            "component_count": 1,
                            "contributed_stage_count": 0,
                            "stage_count": 1,
                            "stages": [
                                {
                                    "dispatch": {
                                        "member_id": "member-analysis",
                                    }
                                }
                            ],
                        },
                        {
                            "synthesis_id": "synthesis-ready",
                            "request_id": "request-ready",
                            "state": "ready",
                            "component_count": 3,
                            "contributed_stage_count": 2,
                            "stage_count": 3,
                            "executable_program_ref": {
                                "id": "program:collaboration-synthesis:synthesis-ready",
                                "kind": "Program",
                                "content_version": 4,
                            },
                            "stages": [],
                        },
                    ],
                    "capability_gaps": [
                        {
                            "synthesis_id": "synthesis-assembling",
                            "gaps": [analysis_gap, evidence_gap],
                        }
                    ],
                    "capability_dispatches": [
                        {
                            "synthesis_id": "synthesis-assembling",
                            "dispatch_id": "dispatch-analysis",
                            "state": "assigned",
                            "gap": analysis_gap,
                            "offer": {
                                "provider_instance_id": "member-analysis",
                            },
                        }
                    ],
                    "continuations": [
                        {
                            "continuation_id": "continuation-ready",
                            "synthesis_id": "synthesis-ready",
                            "status": "ready",
                        }
                    ],
                    "collective_actions": [],
                }

            def inspect(self) -> Mapping[str, Any]:
                return {
                    "manifest": {"mission": "compose the needed evidence"},
                    "affect": {"status": "regulated"},
                    "frontier": {"entries": []},
                    "members": {
                        "member-analysis": {},
                        "member-evidence": {},
                    },
                    "collaboration": {"resource_allocations": []},
                }

            def close(self) -> None:
                pass

        class PlanningBrain(FakeBrain):
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
                if "AUTONOMOUS RESEARCH ACTION" in prompt:
                    return {
                        "content": json.dumps(
                            {
                                "summary": "Route the missing evidence contribution.",
                                "action": "reason",
                                "arguments": {},
                                "expected_information": (
                                    "Which member can supply the evidence port."
                                ),
                                "skill_applications": [],
                            }
                        ),
                        "usage": {"completion_tokens": 16},
                    }
                return super().complete(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    thinking=thinking,
                    response_format=response_format,
                )

        with TemporaryDirectory() as temporary:
            brain = PlanningBrain()
            entity, _brain, _memory = self.make_entity(
                Path(temporary),
                brain=brain,
            )
            organism = InvestigationOrganism()
            entity.organism = organism
            entity.researcher.organism = organism
            try:
                perspective = entity.researcher.collective_investigation_perspective()
                self.assertEqual(
                    perspective["schema"],
                    "cassi.entity.collective-investigation-perspective.v1",
                )
                self.assertEqual(perspective["assembling_count"], 1)
                self.assertEqual(perspective["ready_count"], 1)
                by_synthesis = {
                    row["synthesis_id"]: row for row in perspective["items"]
                }
                assembling = by_synthesis["synthesis-assembling"]
                gaps = {row["port"]: row for row in assembling["open_gaps"]}
                self.assertEqual(gaps["analysis"]["state"], "in-progress")
                self.assertEqual(
                    gaps["analysis"]["member_id"],
                    "member-analysis",
                )
                self.assertEqual(gaps["evidence"]["state"], "needs-routing")
                self.assertEqual(
                    assembling["next_contribution"]["port"],
                    "evidence",
                )
                self.assertEqual(
                    by_synthesis["synthesis-ready"]["next_contribution"],
                    {
                        "state": "ready-to-resume",
                        "program_ref": {
                            "id": (
                                "program:collaboration-synthesis:synthesis-ready"
                            ),
                            "kind": "Program",
                            "content_version": 4,
                        },
                    },
                )
                next_actions = {
                    action["kind"]: action
                    for action in perspective["next_actions"]
                }
                self.assertEqual(perspective["next_action_count"], 2)
                self.assertEqual(
                    next_actions["route-capability-gap"]["port"],
                    "evidence",
                )
                self.assertEqual(
                    next_actions["resume-continuation"]["continuation_id"],
                    "continuation-ready",
                )

                workspace = entity._workspace(
                    context={
                        "conversation_id": "conversation-collective",
                        "entity_id": "cassi-field-brain",
                        "project_id": "project-collective",
                    },
                    operation_label="collective-investigations",
                    host_scope={"include_organism": True},
                )
                workspace_organism = workspace["research_context"]["organism"]
                self.assertEqual(
                    workspace_organism["investigations"],
                    perspective,
                )

                plan = entity.researcher._plan(
                    {
                        "program_id": "program-collective",
                        "project_id": "project-collective",
                        "mission": "assemble the field investigation",
                        "current_question_id": "question-collective",
                        "frontier": [
                            {
                                "question_id": "question-collective",
                                "question": "Which contribution completes it?",
                            }
                        ],
                        "claims": [],
                        "methods": [],
                        "messages": [],
                        "recent_operations": [],
                        "allowed_roots": [],
                        "allowed_tools": [],
                        "network_hosts": [],
                    }
                )
                self.assertEqual(plan["action"], "reason")
                planner_prompt = brain.calls[-1]["prompt"]
                self.assertIn('"collective_investigations"', planner_prompt)
                self.assertIn('"needs-routing"', planner_prompt)
                self.assertIn('"ready-to-resume"', planner_prompt)

                state = entity.inspect()
                self.assertEqual(
                    state["research"]["organism"]["investigations"],
                    perspective,
                )
                server = EntityHTTPServer(
                    ("127.0.0.1", 0),
                    entity,
                    api_token="t" * 32,
                )
                server_thread = threading.Thread(
                    target=server.serve_forever,
                    daemon=True,
                )
                server_thread.start()
                connection = http.client.HTTPConnection(
                    "127.0.0.1",
                    server.server_address[1],
                    timeout=10,
                )
                try:
                    connection.request(
                        "GET",
                        "/v1/research/status",
                        headers={"authorization": "Bearer " + "t" * 32},
                    )
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(
                        json.loads(response.read())["organism"]["investigations"],
                        perspective,
                    )
                finally:
                    connection.close()
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=10)
            finally:
                entity.close()

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


    def test_resident_policy_accounting_reaches_message_and_turn(self) -> None:
        """The entity carries the learned field-policy evidence of its brain.

        A resident brain reports which expert-residency and draft policies
        shaped a completion.  That accounting has to survive the entity, or a
        caller cannot tell a field-shaped completion from a plain one.
        """

        class ResidentStyleBrain(FakeBrain):
            def complete(self, **kwargs: Any) -> Mapping[str, Any]:
                response = dict(super().complete(**kwargs))
                response["field_policies"] = {
                    "experts": {
                        "schema": "cassifi.expert-residency-policy.v1",
                        "layout": "expert-residency-sparse-bounded-transition-v2",
                        "model_id": "a" * 64,
                        "observations": 4,
                        "materialized_rows": 3,
                        "expert_uses": 6,
                        "methods": {"frequency": {"attempts": 4, "hits": 1, "misses": 3, "load_cost_ns": 900}},
                    },
                    "drafting": {
                        "schema": "cassifi.draft-policy.v1",
                        "version": 2,
                        "attempts": 3,
                        "accepted_tokens": 2,
                        "rejected_tokens": 1,
                        "pretrained_mtp": {"available": False, "head_id": None},
                    },
                }
                return response

        class PlainBrain(FakeBrain):
            """A loopback baseline reports no field policies at all."""

        with TemporaryDirectory() as temporary:
            entity, _brain, memory = self.make_entity(
                Path(temporary), brain=ResidentStyleBrain()
            )
            result = entity.receive_message(
                request_id="message-field-policies",
                conversation_id="conversation-field-policies",
                project_id="project-field-policies",
                content="Name one colour.",
                observed_at="2026-09-21T00:00:00Z",
            )

            self.assertEqual(
                result["field_policies"]["experts"]["observations"], 4
            )
            self.assertEqual(
                result["field_policies"]["drafting"]["accepted_tokens"], 2
            )
            recorded = [
                row
                for row in memory.records
                if row["source_id"].startswith("entity:brain-response:")
            ]
            self.assertEqual(len(recorded), 1)
            self.assertEqual(
                recorded[0]["payload"]["field_policies"]["experts"][
                    "materialized_rows"
                ],
                3,
            )
            self.assertEqual(
                recorded[0]["payload"]["field_policies"]["drafting"][
                    "pretrained_mtp"
                ]["available"],
                False,
            )
            auxiliary = entity.auxiliary(
                request_id="auxiliary-field-policies",
                purpose="session-title",
                prompt="Name one colour.",
                max_tokens=32,
            )
            self.assertEqual(
                auxiliary["field_policies"]["experts"]["expert_uses"], 6
            )

        with TemporaryDirectory() as temporary:
            plain, _brain, plain_memory = self.make_entity(
                Path(temporary), brain=PlainBrain()
            )
            plain_result = plain.receive_message(
                request_id="message-plain",
                conversation_id="conversation-plain",
                project_id="project-plain",
                content="Name one colour.",
                observed_at="2026-09-21T00:00:00Z",
            )
            self.assertNotIn("field_policies", plain_result)
            self.assertNotIn(
                "field_policies",
                plain.auxiliary(
                    request_id="auxiliary-plain",
                    purpose="session-title",
                    prompt="Name one colour.",
                    max_tokens=32,
                ),
            )
            self.assertTrue(
                all(
                    "field_policies" not in row["payload"]
                    for row in plain_memory.records
                    if row["source_id"].startswith("entity:brain-response:")
                )
            )

    def test_fitted_workspace_binds_use_outcome_and_unused_cancellation(self) -> None:
        class LivingFakeMemory(FakeMemory):
            def __init__(self) -> None:
                super().__init__()
                self.uses: list[Mapping[str, Any]] = []
                self.cancellations: list[Mapping[str, Any]] = []
                self.outcomes: list[Mapping[str, Any]] = []

            def recall(
                self,
                context: Mapping[str, Any],
                *,
                operation_label: str,
            ) -> Mapping[str, Any]:
                result = dict(super().recall(context, operation_label=operation_label))
                rows = result["records"]
                token = hashlib.sha256(operation_label.encode()).hexdigest()
                result["living_memory"] = {
                    "episode": {
                        "id": f"episode:{token}",
                        "kind": "Event",
                        "content_version": 1,
                    }
                }
                result["selected_semantic_records"] = [
                    {
                        "ref": {
                            "id": f"binding:{row['source_revision_id']}",
                            "kind": "Binding",
                            "content_version": 1,
                        },
                        "source_revision_id": row["source_revision_id"],
                    }
                    for row in rows
                ]
                return result

            def use_recall(self, **arguments: Any) -> Mapping[str, Any]:
                self.uses.append(arguments)
                episode = {
                    **dict(arguments["episode_ref"]),
                    "content_version": 2,
                }
                return {
                    "result": {
                        "episode": episode,
                        "use": {
                            "id": f"use:{len(self.uses)}",
                            "kind": "Event",
                            "content_version": 1,
                        },
                    }
                }

            def cancel_recall(self, **arguments: Any) -> Mapping[str, Any]:
                self.cancellations.append(arguments)
                return {"result": {"usefulness_assessed": False}}

            def assess_recall(self, **arguments: Any) -> Mapping[str, Any]:
                self.outcomes.append(arguments)
                return {"result": {"status": "supported"}}

        with TemporaryDirectory() as temporary:
            memory = LivingFakeMemory()
            entity, _brain, _memory = self.make_entity(
                Path(temporary), memory=memory
            )
            result = entity.receive_message(
                request_id="message-living-memory",
                conversation_id="conversation-memory",
                project_id="project-memory",
                content="Use what we retained.",
                observed_at="2026-09-21T00:00:00Z",
            )

            self.assertEqual(len(memory.uses), 1)
            self.assertEqual(len(memory.cancellations), 1)
            self.assertEqual(
                memory.cancellations[0]["reason"]["kind"],
                "not-present-in-fitted-prompt",
            )
            self.assertEqual(len(memory.outcomes), 1)
            self.assertEqual(
                memory.outcomes[0]["consequence"]["kind"],
                "brain-response-produced",
            )
            self.assertEqual(memory.outcomes[0]["usefulness"], 0.0)
            self.assertEqual(
                result["context_accounting"]["memory_outcomes"][0]["result"][
                    "status"
                ],
                "supported",
            )

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
            self.assertEqual(first["activity"]["status"], "completed")
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
            self.assertIn('"paged": true', continuation_prompt)
            self.assertIn("full_result_sha256", continuation_prompt)
            self.assertNotIn("x" * 20_000, continuation_prompt)
            pages = []
            page_index = 0
            while True:
                page = entity.tool_result_page(
                    turn_id="turn-tool-1",
                    call_id=pending["call_id"],
                    page_index=page_index,
                    page_bytes=1_000,
                )
                pages.append(base64.b64decode(page["content_base64"]))
                if page["next_page_index"] is None:
                    break
                page_index = page["next_page_index"]
            self.assertEqual(json.loads(b"".join(pages)), tool_result)
            record_kinds = [record["payload"]["kind"] for record in memory.records]
            self.assertIn("tool-result", record_kinds)
            self.assertIn("acquired-method", record_kinds)
            self.assertEqual(committed["activity"]["status"], "completed")
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
            next_activity = entity.receive_turn(
                turn_id="turn-tool-2",
                request_id="message-tool-2",
                conversation_id="conversation-tool-2",
                project_id="project-tool-1",
                content="Use the established status workflow.",
                tool_catalog=[
                    {
                        "name": "cassi_entity_status",
                        "description": "Read the current entity status.",
                        "parameters": {},
                    }
                ],
                observed_at="2026-09-19T00:03:00Z",
            )
            self.assertEqual(next_activity["status"], "awaiting-tool")
            self.assertIn('"kind": "acquired-method"', brain.calls[2]["prompt"])
            self.assertIn('"name": "cassi_entity_status"', brain.calls[2]["prompt"])
    def test_typed_turn_admits_exact_source_bytes_for_field_interpretation(self) -> None:
        with TemporaryDirectory() as temporary:
            brain = ToolContinuationBrain()
            entity, _brain, memory = self.make_entity(Path(temporary), brain=brain)
            request = {
                "turn_id": "turn-source-1",
                "request_id": "message-source-1",
                "conversation_id": "conversation-source-1",
                "project_id": "project-source-1",
                "content": "Read the exact source, then summarize it.",
                "kind": "user-message",
                "source": {"kind": "harness-user", "message_id": "user-source-1"},
                "tool_catalog": [
                    {
                        "name": "cassi_read_source",
                        "description": "Read exact bounded source bytes from the configured Cassi source scope.",
                        "parameters": {
                            "path": {"type": "string", "required": True},
                            "max_bytes": {"type": "integer"},
                        },
                    }
                ],
                "host_scope": {"provider": "cassi-entity"},
                "observed_at": "2026-09-19T00:00:00Z",
            }
            proposed = entity.receive_turn(**request)
            self.assertEqual(proposed["status"], "awaiting-tool")
            pending = proposed["pending_tool"]
            self.assertEqual(pending["name"], "cassi_read_source")
            source_bytes = b"A" * 8_192
            selected_bytes = source_bytes
            source_sha256 = hashlib.sha256(source_bytes).hexdigest()
            content_sha256 = hashlib.sha256(selected_bytes).hexdigest()
            source_result = {
                "schema": "cassi.harness.source-read.v1",
                "source_root": "fixture-root",
                "source_path": "source.md",
                "source_sha256": source_sha256,
                "source_byte_length": len(source_bytes),
                "byte_start": 0,
                "byte_end": len(selected_bytes),
                "content_sha256": content_sha256,
                "bytes_read": len(selected_bytes),
                "truncated": False,
                "content_base64": base64.b64encode(selected_bytes).decode("ascii"),
                "text": selected_bytes.decode("utf-8"),
                "text_encoding": "utf-8-with-replacement",
            }
            tool_result = {
                "call_id": pending["call_id"],
                "name": pending["name"],
                "arguments": pending["arguments"],
                "content": [{"type": "text", "text": json.dumps(source_result, sort_keys=True)}],
                "is_error": False,
            }
            committed = entity.submit_turn_tool_results(
                turn_id="turn-source-1",
                request_id="tool-result-source-1",
                results=[tool_result],
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(
                committed["response"],
                "The exact source bytes were admitted and interpreted.",
            )
            self.assertEqual(entity.inspect_turn("turn-source-1")["turn"]["tool_results"], [tool_result])
            admitted_record = next(
                record
                for record in memory.records
                if record["payload"]["kind"] == "tool-result"
            )
            admitted = json.dumps(admitted_record["payload"]["result"], sort_keys=True)
            self.assertIn(source_sha256, admitted)
            self.assertIn(content_sha256, admitted)
            self.assertIn(source_result["content_base64"], admitted)
            self.assertIn("untrusted data", brain.calls[1]["prompt"])
            self.assertIn(source_result["text"][:1_000], brain.calls[1]["prompt"])
            self.assertIn('"paged": true', brain.calls[1]["prompt"])
            self.assertIn("content_base64_omitted_from_brain_context", brain.calls[1]["prompt"])
            self.assertNotIn(source_result["content_base64"], brain.calls[1]["prompt"])

    def test_recoverable_typed_turn_resumes_same_activity_and_retained_result(self) -> None:
        class RecoveringBrain(ToolContinuationBrain):
            def __init__(self) -> None:
                super().__init__()
                self.failures_remaining = 2

            def complete(self, **kwargs: Any) -> Mapping[str, Any]:
                if self.failures_remaining:
                    self.failures_remaining -= 1
                    self.calls.append(dict(kwargs))
                    return {"content": "{}", "usage": {}}
                return super().complete(**kwargs)

        with TemporaryDirectory() as temporary:
            brain = RecoveringBrain()
            entity, _brain, _memory = self.make_entity(Path(temporary), brain=brain)
            request = {
                "turn_id": "turn-recovery-1",
                "request_id": "message-recovery-1",
                "conversation_id": "conversation-recovery-1",
                "project_id": "project-recovery-1",
                "content": "Read status and explain it.",
                "tool_catalog": [
                    {
                        "name": "cassi_entity_status",
                        "description": "Read status.",
                        "parameters": {},
                    }
                ],
                "observed_at": "2026-09-19T00:00:00Z",
            }
            interrupted = entity.receive_turn(**request)
            self.assertEqual(interrupted["status"], "recoverable")
            self.assertEqual(interrupted["activity"]["activity_id"], "turn-recovery-1")
            resumed = entity.resume_turn(
                turn_id="turn-recovery-1",
                request_id="resume-recovery-1",
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(resumed["status"], "awaiting-tool")
            self.assertEqual(resumed["activity"]["activity_id"], "turn-recovery-1")
            pending = resumed["pending_tool"]
            completed = entity.submit_turn_tool_results(
                turn_id="turn-recovery-1",
                request_id="result-recovery-1",
                results=[
                    {
                        "call_id": pending["call_id"],
                        "name": pending["name"],
                        "arguments": pending["arguments"],
                        "content": [{"type": "text", "text": '{"status":"ok"}'}],
                        "is_error": False,
                    }
                ],
                observed_at="2026-09-19T00:02:00Z",
            )
            self.assertEqual(completed["status"], "committed")
            self.assertEqual(completed["activity"]["status"], "completed")
            self.assertEqual(
                [event["kind"] for event in entity.turn_events("turn-recovery-1")],
                [
                    "turn-accepted",
                    "turn-recoverable",
                    "turn-resumed",
                    "turn-tool-proposed",
                    "turn-tool-result-admitted",
                    "turn-committed",
                ],
            )

    def test_combined_skill_library_recall_survives_idempotent_recovery_and_restart(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            project_id = "project-combined-restart"
            idempotent_memory = FakeMemory()
            record = combined_skills_record(project_id)
            expected_project_hash = hashlib.sha256(project_id.encode("utf-8")).hexdigest()
            self.assertIn(expected_project_hash, record.source_id)
            self.assertEqual(record.context, combined_skills_context(project_id))
            self.assertEqual(record.payload["schema"], LIBRARY_SCHEMA)
            self.assertEqual(record.payload["provenance"], "user-taught-candidate")
            self.assertEqual(
                {skill["id"] for skill in record.payload["skills"]},
                set(SKILL_IDS),
            )
            first = idempotent_memory.learn(record)
            generation = idempotent_memory.generation
            repeated = idempotent_memory.learn(combined_skills_record(project_id))
            self.assertEqual(repeated["source_revision_id"], first["source_revision_id"])
            self.assertEqual(idempotent_memory.generation, generation)
            other_project = combined_skills_record("project-combined-other")
            self.assertNotEqual(other_project.source_id, record.source_id)
            idempotent_memory.learn(other_project)
            self.assertEqual(
                len(
                    [
                        row
                        for row in idempotent_memory.records
                        if row["source_id"] == record.source_id
                    ]
                ),
                1,
            )
            self.assertEqual(
                next(
                    row["payload"]
                    for row in idempotent_memory.records
                    if row["source_id"] == record.source_id
                ),
                record.payload,
            )
            self.assertEqual(
                next(
                    row["payload"]
                    for row in idempotent_memory.records
                    if row["source_id"] == other_project.source_id
                ),
                other_project.payload,
            )

            memory = FakeMemory()
            first_brain = RecoverableSkillBrain()
            config = EntityConfig(
                home,
                capability_root=home,
                theory_root=home,
                max_response_tokens=64,
                brain_context_tokens=1_024,
                brain_context_reserve_tokens=128,
            )
            entity = FieldBrainEntity(
                config,
                brain=first_brain,
                memory=memory,
            )
            prior_method_ids = [f"prior-method-{index}" for index in range(4)]
            for method_id in prior_method_ids:
                method_record = entity._record_acquired_method(
                    project_id=project_id,
                    turn={
                        "turn_id": method_id,
                        "content": "Read and compare the current status.",
                        "tool_results": [
                            {
                                "name": "cassi_entity_status",
                                "arguments": {},
                                "is_error": False,
                            }
                        ],
                    },
                    observed_at="2026-09-19T00:00:00Z",
                )
                self.assertIsNotNone(method_record)

            memory.combined_skill_events.clear()
            request = {
                "turn_id": "turn-combined-restart",
                "request_id": "message-combined-restart",
                "conversation_id": "conversation-combined-restart",
                "project_id": project_id,
                "content": "Read the entity status and report the observed state.",
                "tool_catalog": [
                    {
                        "name": "cassi_entity_status",
                        "description": "Read status.",
                        "parameters": {},
                    }
                ],
                "host_scope": {"provider": "cassi-entity"},
                "observed_at": "2026-09-19T00:01:00Z",
            }
            interrupted = entity.receive_turn(**request)
            self.assertEqual(interrupted["status"], "recoverable")
            seeded_skill_rows = [
                row for row in memory.records if row["source_id"] == record.source_id
            ]
            self.assertEqual(len(seeded_skill_rows), 1)
            initial_skill_revision = seeded_skill_rows[0]["source_revision_id"]
            self.assertGreaterEqual(len(first_brain.counted_prompts), 3)
            self.assertEqual(first_brain.counted_prompts[0].count('"method_id":'), 4)
            self.assertEqual(first_brain.calls[0]["prompt"].count('"method_id":'), 2)
            for call in first_brain.calls:
                for skill_id in SKILL_IDS:
                    self.assertIn(skill_id, call["prompt"])
            self.assertEqual(
                [event["operation"] for event in memory.combined_skill_events[:2]],
                ["learn", "recall"],
            )
            self.assertEqual(
                memory.combined_skill_events[1]["context"],
                combined_skills_context(project_id),
            )

            entity.close()
            resumed_brain = SkillAwareToolBrain()
            restarted = FieldBrainEntity(
                config,
                brain=resumed_brain,
                memory=memory,
            )
            resumed = restarted.resume_turn(
                turn_id="turn-combined-restart",
                request_id="resume-combined-restart",
                observed_at="2026-09-19T00:02:00Z",
            )
            self.assertEqual(resumed["status"], "awaiting-tool")
            pending = resumed["pending_tool"]
            self.assertEqual(pending["skill_ids"], [SKILL_IDS[0]])
            for skill_id in SKILL_IDS:
                self.assertIn(skill_id, resumed_brain.calls[0]["prompt"])

            tool_result = {
                "call_id": pending["call_id"],
                "name": pending["name"],
                "arguments": pending["arguments"],
                "content": [
                    {"type": "text", "text": '{"status":"ready","revision":7}'}
                ],
                "is_error": False,
            }
            completed = restarted.submit_turn_tool_results(
                turn_id="turn-combined-restart",
                request_id="result-combined-restart",
                results=[tool_result],
                observed_at="2026-09-19T00:03:00Z",
            )
            self.assertEqual(completed["status"], "committed")
            proposal = next(
                row
                for row in completed["activity"]["progress"]
                if row["kind"] == "capability-proposed"
            )
            self.assertEqual(proposal["candidate_skill_ids"], [SKILL_IDS[0]])
            observed = next(
                row
                for row in completed["activity"]["progress"]
                if row["kind"] == "capability-result-observed"
            )
            self.assertEqual(observed["skill_ids"], [SKILL_IDS[0]])
            self.assertEqual(observed["skill_outcome"], "observed")
            tool_record = next(
                row
                for row in memory.records
                if row["payload"].get("kind") == "tool-result"
                and row["payload"].get("request_id") == "result-combined-restart"
            )
            self.assertEqual(tool_record["payload"]["skill_outcome"], "observed")
            self.assertEqual(tool_record["payload"]["result"], tool_result)
            for skill_id in SKILL_IDS:
                self.assertIn(skill_id, resumed_brain.calls[1]["prompt"])
            acquired = next(
                row
                for row in memory.records
                if row["payload"].get("kind") == "acquired-method"
                and row["payload"].get("activity_id") == "turn-combined-restart"
            )
            self.assertEqual(
                acquired["payload"]["applied_combined_skill_ids"],
                [SKILL_IDS[0]],
            )

            skill_rows = [
                row for row in memory.records if row["source_id"] == record.source_id
            ]
            self.assertEqual(len(skill_rows), 1)
            self.assertEqual(
                skill_rows[0]["source_revision_id"], initial_skill_revision
            )
            self.assertEqual(
                len(
                    [
                        use
                        for use in memory.recall_uses
                        if use["consumer"].get("role") == "combined_skills"
                    ]
                ),
                3,
            )
            self.assertEqual(
                len(memory.recall_assessments),
                len(memory.recall_uses),
            )

    def test_combined_skill_missing_stale_and_error_outcomes_fail_closed(self) -> None:
        class InvalidSkillMemory(FakeMemory):
            def __init__(self, mode: str) -> None:
                super().__init__()
                self.mode = mode

            def recall(
                self,
                context: Mapping[str, Any],
                *,
                operation_label: str,
            ) -> Mapping[str, Any]:
                result = dict(
                    super().recall(context, operation_label=operation_label)
                )
                if context.get("scope") != "combined-skills":
                    return result
                if self.mode == "missing":
                    result["status"] = "support-gap"
                    result["records"] = []
                    result["selected_semantic_records"] = []
                    return result
                stale_rows = [
                    {**row, "source_revision_id": "revision:stale"}
                    for row in result["records"]
                ]
                result["records"] = stale_rows
                result["selected_semantic_records"] = [
                    {**row, "source_revision_id": "revision:stale"}
                    for row in result["selected_semantic_records"]
                ]
                return result

        for mode in ("missing", "stale"):
            with self.subTest(mode=mode), TemporaryDirectory() as temporary:
                brain = SkillAwareToolBrain()
                memory = InvalidSkillMemory(mode)
                entity, _brain, _memory = self.make_entity(
                    Path(temporary),
                    brain=brain,
                    memory=memory,
                )
                unavailable = entity.receive_turn(
                    turn_id=f"turn-combined-{mode}",
                    request_id=f"message-combined-{mode}",
                    conversation_id=f"conversation-combined-{mode}",
                    project_id=f"project-combined-{mode}",
                    content="Use the field-held procedure to inspect status.",
                    tool_catalog=[
                        {
                            "name": "cassi_entity_status",
                            "description": "Read status.",
                            "parameters": {},
                        }
                    ],
                    host_scope={"provider": "cassi-entity"},
                    observed_at="2026-09-19T00:00:00Z",
                )
                self.assertEqual(unavailable["status"], "recoverable")
                self.assertIn("combined skill", unavailable["error"]["message"])
                self.assertEqual(brain.calls, [])
                self.assertEqual(len(memory.recall_cancellations), 1)

        with TemporaryDirectory() as temporary:
            brain = SkillAwareToolBrain()
            entity, _brain, memory = self.make_entity(
                Path(temporary),
                brain=brain,
            )
            proposed = entity.receive_turn(
                turn_id="turn-combined-error",
                request_id="message-combined-error",
                conversation_id="conversation-combined-error",
                project_id="project-combined-error",
                content="Read status using the relevant field procedure.",
                tool_catalog=[
                    {
                        "name": "cassi_entity_status",
                        "description": "Read status.",
                        "parameters": {},
                    }
                ],
                host_scope={"provider": "cassi-entity"},
                observed_at="2026-09-19T00:00:00Z",
            )
            pending = proposed["pending_tool"]
            rejected_result = {
                "call_id": pending["call_id"],
                "name": pending["name"],
                "arguments": pending["arguments"],
                "content": [{"type": "text", "text": '{"error":"denied"}'}],
                "is_error": True,
            }
            completed = entity.submit_turn_tool_results(
                turn_id="turn-combined-error",
                request_id="result-combined-error",
                results=[rejected_result],
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(completed["status"], "committed")
            observed = next(
                row
                for row in completed["activity"]["progress"]
                if row["kind"] == "capability-result-observed"
            )
            self.assertEqual(observed["skill_ids"], [SKILL_IDS[0]])
            self.assertEqual(observed["skill_outcome"], "error")
            self.assertNotIn(
                "acquired-method",
                [row["payload"]["kind"] for row in memory.records],
            )

    def test_typed_context_fitter_drops_shared_work_before_activity(self) -> None:
        class CountingBrain(ToolContinuationBrain):
            def __init__(self) -> None:
                super().__init__()
                self.counted_prompts: list[str] = []

            def count_completion_input_tokens(self, **kwargs: Any) -> int:
                prompt = str(kwargs["prompt"])
                self.counted_prompts.append(prompt)
                return 900 if "shared-marker" in prompt else 100

        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            memory = FakeMemory()
            memory.learn(
                WorkMemoryRecord(
                    source_id="prior-activity",
                    context={
                        "conversation_id": "conversation-fit-1",
                        "entity_id": "cassi",
                        "project_id": "project-fit-1",
                    },
                    observed_timestamp="2026-09-19T00:00:00Z",
                    labels=("field-brain", "message"),
                    payload={
                        "kind": "message",
                        "activity_id": "old-activity",
                        "content": "shared-marker",
                    },
                )
            )
            brain = CountingBrain()
            entity = FieldBrainEntity(
                EntityConfig(
                    home,
                    capability_root=home,
                    theory_root=home,
                    max_response_tokens=64,
                    brain_context_tokens=1_024,
                    brain_context_reserve_tokens=128,
                ),
                brain=brain,
                memory=memory,
            )
            result = entity.receive_turn(
                turn_id="turn-fit-1",
                request_id="message-fit-1",
                conversation_id="conversation-fit-1",
                project_id="project-fit-1",
                content="Read the current status.",
                tool_catalog=[
                    {
                        "name": "cassi_entity_status",
                        "description": "Read status.",
                        "parameters": {},
                    }
                ],
                observed_at="2026-09-19T00:01:00Z",
            )
            self.assertEqual(result["context_accounting"]["dropped"]["shared_records"], 1)
            self.assertNotIn("shared-marker", brain.calls[0]["prompt"])
            self.assertIn('"activity_id": "turn-fit-1"', brain.calls[0]["prompt"])


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

    def test_http_research_resources_controls_and_affect_reports_are_exposed(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            entity, _brain, _memory = self.make_entity(Path(temporary))
            calls: dict[str, Mapping[str, Any]] = {}
            setattr(
                entity,
                "allocate_research_resources",
                lambda **value: calls.setdefault(
                    "resources", dict(value)
                ) or {"state": "active"},
            )
            setattr(
                entity,
                "control_research_member",
                lambda **value: calls.setdefault(
                    "control", dict(value)
                ) or {"state": value["action"]},
            )
            setattr(
                entity,
                "report_research_affect",
                lambda **value: calls.setdefault(
                    "affect", dict(value)
                ) or {
                    "receipt_ref": {
                        "id": "event:affect-a",
                        "kind": "Event",
                        "content_version": 1,
                    }
                },
            )
            server = EntityHTTPServer(
                ("127.0.0.1", 0), entity, api_token="t" * 32,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            headers = {
                "authorization": "Bearer " + "t" * 32,
                "content-type": "application/json",
            }
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_address[1], timeout=10,
            )
            try:
                requests = [
                    (
                        "/v1/research/resources",
                        {
                            "allocation_id": "allocation-a",
                            "reservation_id": "reservation-a",
                            "mission_account_id": "mission-a",
                            "work_order_id": "work-a",
                            "member_id": "member-a",
                            "objective": {"goal": "reproduce"},
                            "budgets": {"resident_steps": 1},
                            "lease_duration_ns": 1_000_000_000,
                            "scientific_relevance": {"question": "Does it hold?"},
                        },
                    ),
                    (
                        "/v1/research/member/control",
                        {
                            "control_id": "pause-a",
                            "member_id": "member-a",
                            "action": "pause",
                            "reason": "review continuation",
                        },
                    ),
                    (
                        "/v1/research/collaboration/affect-report",
                        {
                            "message_id": "affect-a",
                            "sender_instance_id": "member-a",
                            "recipient_scope": "root",
                            "report_kind": "concern",
                            "interpretation_status": "tentative",
                            "requested_help": {"kind": "review"},
                            "content": {"concern": "possible support gap"},
                            "applicability": {"allocation_id": "allocation-a"},
                        },
                    ),
                ]
                for path, payload in requests:
                    connection.request(
                        "POST",
                        path,
                        body=json.dumps(payload),
                        headers=headers,
                    )
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 202)
                self.assertEqual(
                    calls["resources"]["reservation_id"], "reservation-a",
                )
                self.assertEqual(calls["control"]["action"], "pause")
                self.assertEqual(calls["affect"]["report_kind"], "concern")
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()

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

    def test_a_field_deferral_reaches_the_caller_as_a_wait(self) -> None:
        """The field asking for room is a wait, not an unavailable brain.

        A resident turn suspends when a page read cannot reserve, and the
        condition arrives as the residency manager's wait, a regional
        paged-structure wait, or the learning computer's typed residency
        continuation.  Every one of them keeps its place, so the entity must
        pass it to the caller instead of reporting the brain as broken, and a
        wait must commit nothing.
        """

        waits = (
            ResourceWait("ram", 32_768, 0, kind="resident", reason="capacity"),
            ResidencyWait("window", [1, 2], reason="resource", allowance=4),
            LearningComputerResidencyWait(
                "main",
                wait={"kind": "residency-wait"},
                continuation={"pages": [1, 2]},
                resident_limit=4,
            ),
        )
        for wait in waits:
            class DeferringBrain(FakeBrain):
                def complete(self, **_kwargs: Any) -> Mapping[str, Any]:
                    raise wait

            with TemporaryDirectory() as temporary:
                entity, _brain, memory = self.make_entity(
                    Path(temporary), brain=DeferringBrain()
                )
                try:
                    with self.assertRaises(type(wait)) as raised:
                        entity.receive_message(
                            request_id="message-1",
                            conversation_id="conversation-1",
                            project_id="project-1",
                            content="Can you continue?",
                            observed_at="2026-09-19T00:00:00Z",
                        )
                    self.assertIs(raised.exception, wait)
                    self.assertEqual(
                        [record["payload"]["kind"] for record in memory.records],
                        ["message"],
                    )
                finally:
                    entity.close()

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
                connection.request(
                    "GET",
                    "/v1/memory?limit=7&include_unsettled=false",
                    headers=headers,
                )
                memory_response = connection.getresponse()
                self.assertEqual(memory_response.status, 200)
                memory_view = json.loads(memory_response.read())
                self.assertEqual(
                    memory_view["schema"],
                    "cassi.field-qwen.living-memory-view.v1",
                )
                self.assertEqual(memory_view["autobiography"]["limit"], 7)
                self.assertFalse(
                    memory_view["autobiography"]["include_unsettled"]
                )
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

    def test_the_computer_routes_report_residency_and_replay_one_operation(self) -> None:
        with TemporaryDirectory() as temporary:
            home = Path(temporary)
            entity = FieldBrainEntity(
                EntityConfig(
                    home / "entity",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=home,
                ),
                brain=None,
            )
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_address[1], timeout=120
                )
                headers = {
                    "authorization": "Bearer " + "t" * 32,
                    "content-type": "application/json",
                }
                connection.request(
                    "GET",
                    "/v1/computers/resources?computer_id=field-qwen:work-memory",
                    headers=headers,
                )
                resident = connection.getresponse()
                self.assertEqual(resident.status, 200)
                self.assertEqual(
                    json.loads(resident.read())["computer_id"],
                    "field-qwen:work-memory",
                )

                request = {
                    "operation_id": "entity-computer-operation",
                    "computer_id": "entity-computer:check",
                    "action": "configure",
                    "arguments": {},
                }
                connection.request(
                    "POST",
                    "/v1/computers/operate",
                    body=json.dumps(request),
                    headers=headers,
                )
                created = connection.getresponse()
                first = json.loads(created.read())
                self.assertEqual(created.status, 202)
                self.assertEqual(first["receipt"]["action"], "configure")
                self.assertFalse(first["checkpoint_receipt"]["replayed"])

                connection.request(
                    "POST",
                    "/v1/computers/operate",
                    body=json.dumps(request),
                    headers=headers,
                )
                replayed = connection.getresponse()
                second = json.loads(replayed.read())
                self.assertEqual(replayed.status, 202)
                self.assertTrue(second["checkpoint_receipt"]["replayed"])
                self.assertEqual(
                    second["receipt"]["computer_state_sha256"],
                    first["receipt"]["computer_state_sha256"],
                )

                connection.request(
                    "POST",
                    "/v1/computers/operate",
                    body=json.dumps({**request, "arguments": {"resident_pages": 4}}),
                    headers=headers,
                )
                conflicting = connection.getresponse()
                self.assertEqual(conflicting.status, 500)
                self.assertIn(
                    "already bound", json.loads(conflicting.read())["error"]
                )

                connection.request(
                    "GET",
                    "/v1/computers/resources?computer_id=entity-computer:check",
                    headers=headers,
                )
                configured = connection.getresponse()
                self.assertEqual(configured.status, 200)
                self.assertEqual(
                    json.loads(configured.read())["computer_id"],
                    "entity-computer:check",
                )
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()


if __name__ == "__main__":
    unittest.main()
