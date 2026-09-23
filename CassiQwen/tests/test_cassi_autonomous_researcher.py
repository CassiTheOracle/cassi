from __future__ import annotations

import hashlib
import http.client
import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping
from cassi_autonomous_researcher import (
    AutonomousResearchDirector,
    CapabilityDenied,
    ProgramConflict,
    ResponsibilityAdmissionError,
    ResearchBrainUnavailable,
    ResearchRuntimeConfig,
)
from cassi_field_brain_entity import EntityConfig, FieldBrainEntity
from cassi_field_brain_server import EntityHTTPServer
from cassi_field_qwen_workbench import CassiFieldWorkMemory, ResearchWorkbench


class FakeFieldMemory:
    def __init__(self) -> None:
        self.records: list[Mapping[str, Any]] = []
        self.semantic_records: dict[str, Mapping[str, Any]] = {}
        self.semantic_calls: list[Mapping[str, Any]] = []
        self.recall_calls: list[Mapping[str, Any]] = []
        self.combined_skill_phase_override: str | None = None
        self.generation = 0
        self.closed = False

    def _sha(self) -> str:
        return hashlib.sha256(f"field:{self.generation}".encode()).hexdigest()

    def learn(self, record: Any) -> Mapping[str, Any]:
        for prior in reversed(self.records):
            if (
                prior["source_id"] == record.source_id
                and prior["payload"] == record.payload
                and prior["context"] == record.context
                and prior["observed_timestamp"] == record.observed_timestamp
            ):
                revision = str(prior["source_revision_id"])
                return {
                    "status": "unchanged",
                    "source_revision_id": revision,
                    "state_sha256": self._sha(),
                    "field_state_sha256": self._sha(),
                }
        self.generation += 1
        revision = f"revision:{self.generation}"
        self.records.append(
            {
                "source_id": record.source_id,
                "source_revision_id": revision,
                "payload": record.payload,
                "context": record.context,
                "observed_timestamp": record.observed_timestamp,
            }
        )
        return {
            "source_revision_id": revision,
            "state_sha256": self._sha(),
            "field_state_sha256": self._sha(),
        }

    def semantic(self, request: Mapping[str, Any], *, operation_label: str | None = None) -> Mapping[str, Any]:
        self.semantic_calls.append(dict(request))
        if request["operation"] == "register":
            self.semantic_records[str(request["record_id"])] = dict(request)
            return {
                "result": {
                    "status": "supported",
                    "record": {
                        "id": request["record_id"],
                        "kind": request["kind"],
                        "content_version": 1,
                    },
                }
            }
        if request["operation"] == "autonomous-agenda":
            prefix = str(request.get("obligation_prefix", ""))
            active = [
                value
                for identity, value in self.semantic_records.items()
                if identity.startswith(prefix) and value.get("status") == "active"
            ]
            active.sort(
                key=lambda value: (
                    -float(value.get("payload", {}).get("priority", 0.0)),
                    str(value["record_id"]),
                )
            )
            selected = (
                {
                    "kind": "resolve-obligation",
                    "obligation": {"id": active[0]["record_id"]},
                    "reason": active[0]["payload"]["purpose"],
                }
                if active
                else None
            )
            return {"result": {"status": "supported", "selected": selected}}
        if request["operation"] == "appraise-experience":
            return {
                "result": {
                    "status": "supported",
                    "appraisal": {
                        "id": "event:test-appraisal",
                        "kind": "Event",
                        "content_version": 1,
                    },
                    "context": {
                        "project_id": request["project_id"],
                        "object_id": request["object_id"],
                    },
                }
            }
        raise AssertionError(f"unexpected semantic operation: {request['operation']}")

    def recall(self, context: Mapping[str, Any], *, operation_label: str) -> Mapping[str, Any]:
        self.recall_calls.append(
            {"context": dict(context), "operation_label": operation_label}
        )
        rows = [value for value in self.records if value["context"] == context]
        if (
            context.get("scope") == "combined-skills"
            and self.combined_skill_phase_override
        ):
            recalled_rows = []
            for value in rows:
                payload = json.loads(json.dumps(value["payload"]))
                skills = payload.get("skills")
                if isinstance(skills, list) and skills:
                    first = skills[0]
                    if isinstance(first, dict) and first.get("phases"):
                        first["phases"][0]["step"] = (
                            self.combined_skill_phase_override
                        )
                recalled_rows.append({**value, "payload": payload})
            rows = recalled_rows
        return {"records": rows, "field_state_after_sha256": self._sha()}

    def state_receipt(self) -> Mapping[str, Any]:
        return {"state_sha256": self._sha(), "field_state_sha256": self._sha(), "generation": self.generation}

    def close(self) -> None:
        self.closed = True


class ResearchBrain:
    model_id = "research-brain.gguf"
    model_sha256 = "b" * 64

    def __init__(
        self,
        *,
        action: str = "read_file",
        arguments: Mapping[str, Any] | None = None,
        fail_first_synthesis: bool = False,
        program_status: str = "active",
        report: str | None = None,
    ) -> None:
        self.action = action
        self.arguments = dict(arguments or {"path": "evidence.txt"})
        self.fail_first_synthesis = fail_first_synthesis
        self.program_status = program_status
        self.report = report
        self.calls: list[str] = []
        self.skill_applications: list[Mapping[str, str]] = []

    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append(prompt)
        if "AUTONOMOUS RESEARCH ACTION" in prompt:
            value = {
                "summary": "Acquire the exact source needed by the current question.",
                "action": self.action,
                "arguments": self.arguments,
                "expected_information": "A source-grounded observation.",
                "skill_applications": list(self.skill_applications),
            }
        elif "AUTONOMOUS RESEARCH SYNTHESIS" in prompt:
            if self.fail_first_synthesis:
                self.fail_first_synthesis = False
                raise RuntimeError("temporary model outage")
            value = {
                "finding": "The source reports a measured resonance at 17 Hz.",
                "support_status": "observed",
                "uncertainty": "The source does not yet establish the causal mechanism.",
                "method": "Read the exact admitted source artifact and preserve its digest.",
                "next_question": "Which mechanism predicts the observed 17 Hz resonance?",
                "program_status": self.program_status,
                "report": (
                    self.report
                    if self.report is not None
                    else "A 17 Hz resonance is observed; its mechanism remains open."
                ),
            }
        else:
            value = {"response": "unused"}
        return {"content": json.dumps(value), "usage": {"completion_tokens": 32}}


class SkillSelectingResearchBrain(ResearchBrain):
    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if "AUTONOMOUS RESEARCH ACTION" in prompt:
            compact = json.loads(
                prompt.split("PROGRAM\n", 1)[1].split(
                    "\n\nCAPABILITIES", 1
                )[0]
            )
            skill = next(
                row
                for row in compact["combined_skills"]["skills"]
                if row["id"] == "claim-independent-check-next-experiment"
            )
            self.skill_applications = [
                {
                    "skill_id": skill["id"],
                    "phase": skill["phases"][0]["step"],
                }
            ]
        return super().complete(
            prompt=prompt,
            max_tokens=max_tokens,
            thinking=thinking,
            response_format=response_format,
        )


class AutonomousResearchDirectorTest(unittest.TestCase):
    def make_director(
        self,
        home: Path,
        source_root: Path,
        *,
        brain: ResearchBrain | None = None,
        memory: FakeFieldMemory | None = None,
        default_tools: tuple[str, ...] = ("read_file",),
        workbench: Any | None = None,
    ) -> tuple[AutonomousResearchDirector, ResearchBrain, FakeFieldMemory]:
        actual_brain = brain or ResearchBrain()
        actual_memory = memory or FakeFieldMemory()
        director = AutonomousResearchDirector(
            ResearchRuntimeConfig(
                home=home,
                allowed_roots=(source_root,),
                cycle_interval_seconds=0.05,
                default_tools=default_tools,
            ),
            brain=actual_brain,
            memory=actual_memory,
            workbench=workbench,
        )
        return director, actual_brain, actual_memory

    @staticmethod
    def create_program(director: AutonomousResearchDirector, *, tools: list[str] | None = None) -> Mapping[str, Any]:
        return director.create_program(
            request_id="create-resonance",
            program_id="resonance",
            project_id="physics",
            title="Explain the resonance",
            mission="Establish what causes the measured resonance.",
            initial_question="What is actually observed?",
            observed_at="2026-09-19T00:00:00Z",
            cycle_limit=1,
            allowed_tools=tools,
        )

    def test_recalled_skill_guides_actions_and_actual_result_reaches_next_decision(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8"
            )
            memory = FakeFieldMemory()
            recalled_phase = "FIELD RECALL: check an independent source"
            memory.combined_skill_phase_override = recalled_phase
            brain = SkillSelectingResearchBrain()
            director, brain, memory = self.make_director(
                root / "runtime",
                source,
                brain=brain,
                memory=memory,
                default_tools=("read_file",),
            )
            director.create_program(
                request_id="create-resonance",
                program_id="resonance",
                project_id="physics",
                title="Explain the resonance",
                mission="Establish what causes the measured resonance.",
                initial_question="What is actually observed?",
                observed_at="2026-09-19T00:00:00Z",
                cycle_limit=2,
                allowed_tools=["read_file"],
            )

            first = director.run_one(program_id="resonance")
            self.assertEqual(first["cycles_completed"], 1)
            first_method = first["methods"][-1]
            self.assertEqual(
                first_method["skill_applications"],
                [
                    {
                        "skill_id": "claim-independent-check-next-experiment",
                        "phase": recalled_phase,
                    }
                ],
            )
            self.assertIn(recalled_phase, brain.calls[0])
            brain.action = "reason"
            brain.arguments = {}
            second = director.run_one(program_id="resonance")
            action_prompts = [
                prompt
                for prompt in brain.calls
                if "AUTONOMOUS RESEARCH ACTION" in prompt
            ]
            self.assertEqual(second["cycles_completed"], 2)
            self.assertEqual(len(action_prompts), 2)
            self.assertIn("Measured resonance: 17 Hz", action_prompts[1])
            self.assertIn(recalled_phase, action_prompts[1])

            skill_rows = [
                row
                for row in memory.records
                if row["payload"].get("kind") == "taught-combined-skills"
            ]
            self.assertEqual(len(skill_rows), 1)
            skill_recalls = [
                row
                for row in memory.recall_calls
                if row["context"].get("scope") == "combined-skills"
            ]
            self.assertEqual(
                [row["context"] for row in skill_recalls],
                [
                    {"project_id": "physics", "scope": "combined-skills"},
                    {"project_id": "physics", "scope": "combined-skills"},
                ],
            )

    def test_missing_recalled_skill_library_fails_before_brain_action(self) -> None:
        class MissingSkillsMemory(FakeFieldMemory):
            def recall(
                self,
                context: Mapping[str, Any],
                *,
                operation_label: str,
            ) -> Mapping[str, Any]:
                result = super().recall(context, operation_label=operation_label)
                if context.get("scope") == "combined-skills":
                    return {**result, "records": []}
                return result

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            brain = ResearchBrain()
            director, brain, _memory = self.make_director(
                root / "runtime", source, brain=brain, memory=MissingSkillsMemory()
            )
            self.create_program(director)

            with self.assertRaisesRegex(
                ResearchBrainUnavailable, "did not return exactly one"
            ):
                director.run_one(program_id="resonance")

            self.assertEqual(brain.calls, [])
            self.assertEqual(
                director.store.program("resonance")["cycles_completed"], 0
            )

    def test_recalled_skill_does_not_expand_scoped_tool_authority(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            brain = SkillSelectingResearchBrain(
                action="write_artifact",
                arguments={"path": "unauthorized.txt", "content": "no"},
            )
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                brain=brain,
                default_tools=("read_file",),
            )
            self.create_program(director, tools=["read_file"])

            with self.assertRaises(CapabilityDenied):
                director.run_one(program_id="resonance")

            self.assertFalse(
                (director.store.workspace("resonance") / "unauthorized.txt").exists()
            )
            self.assertEqual(
                director.store.program("resonance")["cycles_completed"], 0
            )


    def test_field_agenda_selects_program_and_cycle_admits_artifact_grounded_finding(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            evidence = b"Measured resonance: 17 Hz\n"
            (source / "evidence.txt").write_bytes(evidence)
            director, brain, memory = self.make_director(root / "runtime", source)
            created = self.create_program(director)
            advanced = director.run_one()

            self.assertEqual(created["status"], "active")
            self.assertIsNotNone(advanced)
            self.assertEqual(advanced["status"], "paused")
            self.assertEqual(advanced["cycles_completed"], 1)
            self.assertEqual(advanced["claims"][-1]["support_status"], "observed")
            self.assertEqual(
                director.store.artifact_bytes(advanced["claims"][-1]["artifact_sha256"]),
                evidence,
            )
            self.assertEqual(
                [call["operation"] for call in memory.semantic_calls if call["operation"] == "autonomous-agenda"],
                ["autonomous-agenda"],
            )
            self.assertEqual(len(brain.calls), 2)
            self.assertEqual(
                [event["kind"] for event in director.events_after(0, program_id="resonance")],
                ["program-created", "operation-planned", "operation-executed", "program-advanced"],
            )

    def test_request_identity_replays_exact_content_and_rejects_mutation(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            director, _brain, memory = self.make_director(root / "runtime", source)
            first = self.create_program(director)
            replay = self.create_program(director)
            self.assertEqual(replay, first)
            self.assertEqual(len(memory.records), 1)
            with self.assertRaises(ProgramConflict):
                director.create_program(
                    request_id="create-resonance",
                    program_id="resonance",
                    project_id="physics",
                    title="Explain the resonance",
                    mission="A changed mission must not reuse the request identity.",

                    initial_question="What is actually observed?",
                    observed_at="2026-09-19T00:00:00Z",
                    cycle_limit=1,
                )
            created_events = [
                event
                for event in director.events_after(0, program_id="resonance")
                if event["kind"] == "program-created"
            ]
            self.assertEqual(len(created_events), 1)

    def test_a_declared_document_gates_completion_until_every_section_is_delivered(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            deliverable = {
                "artifact": "answer.json",
                "sections_key": "stations",
                "sections": ["identification", "retention"],
                "document_schema": "cassi.laboratory.mission-evidence.v1",
                "identity_key": "fixture_id",
                "identity_value": "fixture-1",
            }
            partial = {
                "schema": "cassi.laboratory.mission-evidence.v1",
                "fixture_id": "fixture-1",
                "stations": {"identification": {"law_id": "L1-native-w25"}},
            }
            brain = ResearchBrain(
                action="write_artifact",
                arguments={"path": "answer.json", "content": json.dumps(partial)},
                program_status="completed",
            )
            director, brain, memory = self.make_director(
                root / "runtime", source, brain=brain, default_tools=("write_artifact",)
            )
            director.create_program(
                request_id="create-delivery",
                program_id="delivery",
                project_id="laboratory",
                title="Deliver the counterflow answer",
                mission="Answer every declared station.",
                initial_question="Which stations must the answer cover?",
                observed_at="2026-09-21T00:00:00Z",
                allowed_tools=["write_artifact"],
                deliverable=deliverable,
            )

            refused = director.run_one()
            self.assertEqual(refused["status"], "active")
            self.assertEqual(refused["deliverable_state"]["covered"], ["identification"])
            self.assertEqual(refused["deliverable_state"]["missing"], ["retention"])
            self.assertTrue(refused["deliverable_state"]["identity_ok"])
            self.assertEqual(refused["deliverable_state"]["source"], "artifact")
            directive = director.program("delivery")["projection"]["current_question"]
            self.assertIn("answer.json", directive)
            self.assertIn("retention", directive)
            kinds = [event["kind"] for event in director.events_after(0, program_id="delivery")]
            self.assertIn("deliverable-advanced", kinds)
            self.assertIn("deliverable-incomplete", kinds)
            # the contract is part of the mind's own working context, not a
            # paragraph it read once at the start
            self.assertIn('"artifact": "answer.json"', brain.calls[0])
            self.assertIn("standing obligation", brain.calls[0])
            obligation = memory.semantic_records["entity:research-program-obligation:delivery"]["payload"]
            self.assertEqual(obligation["deliverable"]["sections"], ["identification", "retention"])

            # once the document itself covers every section, the same
            # completion is admitted
            workspace = director.store.workspace("delivery")
            (workspace / "answer.json").write_text(
                json.dumps(
                    {
                        **partial,
                        "stations": {
                            "identification": {"law_id": "L1-native-w25"},
                            "retention": {"longest": "R4-counterflow"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            brain.action = "reason"
            brain.arguments = {}
            finished = director.run_one()
            self.assertEqual(finished["status"], "completed")
            self.assertTrue(finished["deliverable_state"]["complete"])
            self.assertEqual(finished["deliverable_state"]["missing"], [])

    def test_a_document_for_another_world_is_not_a_delivery(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            brain = ResearchBrain(
                action="write_artifact",
                arguments={
                    "path": "answer.json",
                    "content": json.dumps(
                        {
                            "schema": "cassi.laboratory.mission-evidence.v1",
                            "fixture_id": "another-world",
                            "stations": {"identification": {}, "retention": {}},
                        }
                    ),
                },
                program_status="completed",
            )
            director, _brain, _memory = self.make_director(
                root / "runtime", source, brain=brain, default_tools=("write_artifact",)
            )
            director.create_program(
                request_id="create-wrong-world",
                program_id="wrong-world",
                project_id="laboratory",
                title="Deliver the counterflow answer",
                mission="Answer every declared station.",
                initial_question="Which stations must the answer cover?",
                observed_at="2026-09-21T00:00:00Z",
                allowed_tools=["write_artifact"],
                deliverable={
                    "artifact": "answer.json",
                    "sections_key": "stations",
                    "sections": ["identification", "retention"],
                    "document_schema": "cassi.laboratory.mission-evidence.v1",
                    "identity_key": "fixture_id",
                    "identity_value": "fixture-1",
                },
            )
            refused = director.run_one()
            self.assertEqual(refused["status"], "active")
            self.assertEqual(refused["deliverable_state"]["missing"], [])
            self.assertFalse(refused["deliverable_state"]["identity_ok"])
            self.assertFalse(refused["deliverable_state"]["complete"])

    def test_a_document_delivered_through_the_report_field_is_measured(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            document = {
                "schema": "cassi.laboratory.mission-evidence.v1",
                "fixture_id": "fixture-1",
                "stations": {"identification": {}, "retention": {}},
            }
            brain = ResearchBrain(
                action="reason",
                arguments={},
                program_status="completed",
                report="The answer follows.\n\n```json\n"
                + json.dumps(document)
                + "\n```\n",
            )
            director, _brain, _memory = self.make_director(
                root / "runtime", source, brain=brain
            )
            director.create_program(
                request_id="create-report-delivery",
                program_id="report-delivery",
                project_id="laboratory",
                title="Deliver the counterflow answer",
                mission="Answer every declared station.",
                initial_question="Which stations must the answer cover?",
                observed_at="2026-09-21T00:00:00Z",
                deliverable={
                    "artifact": "answer.json",
                    "sections_key": "stations",
                    "sections": ["identification", "retention"],
                    "document_schema": "cassi.laboratory.mission-evidence.v1",
                    "identity_key": "fixture_id",
                    "identity_value": "fixture-1",
                },
            )
            finished = director.run_one()
            self.assertEqual(finished["status"], "completed")
            self.assertEqual(finished["deliverable_state"]["source"], "report")
            self.assertTrue(finished["deliverable_state"]["complete"])

    def test_a_workbench_carries_the_question_wakes_a_blocked_program(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8",
            )
            memory = CassiFieldWorkMemory(root / "field")
            workbench = ResearchWorkbench(memory, member_id="researcher")
            missing = "absent/never-written.txt"
            brain = ResearchBrain(
                action="read_file",
                arguments={"path": missing},
                program_status="blocked",
            )
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                brain=brain,
                memory=memory,
                workbench=workbench,
            )
            try:
                self.create_program(director, tools=["read_file"])
                director.run_one()
                # The first cycle's plan carries the program's own workbench,
                # which only exists once that question opened it.
                first_plan = next(
                    prompt for prompt in brain.calls if "AUTONOMOUS RESEARCH ACTION" in prompt
                )
                self.assertIn('"workbench"', first_plan)
                self.assertIn("field_revision", first_plan)

                program = director.program("resonance")
                self.assertEqual(program["status"], "blocked")
                context = workbench.context(
                    "resonance",
                    question=str(program["projection"]["current_question"]),
                    maximum=32,
                )
                failed = [dict(row) for row in context.get("failed_approaches", [])]
                self.assertTrue(failed)
                read_identities = {
                    str(identity)
                    for row in failed
                    for identity in dict(row.get("dependencies") or {})
                }
                self.assertIn(f"path:{missing}", read_identities)

                # The same failing step is not repeated while its input is
                # unchanged: the next cycle waits instead of reading again.
                director.control_program(
                    request_id="resume-resonance",
                    program_id="resonance",
                    action="resume",
                    observed_at="2026-09-19T01:00:00Z",
                )
                director.run_one()
                executed = [
                    event["payload"]["action"]
                    for event in director.events_after(0, program_id="resonance")
                    if event["kind"] == "operation-executed"
                ]
                self.assertEqual(executed.count("read_file"), 1)
                self.assertEqual(executed[-1], "wait")

                # A change to that exact input wakes the blocked approach.
                change = workbench.command(
                    "resonance",
                    "dependency-change",
                    operation_id="test:dependency-change",
                    arguments={"changes": {f"path:{missing}": "arrived"}},
                )
                self.assertTrue(change["wakeups"])
                reopened = director.workbench_changed(
                    program_id="resonance",
                    event_id="test:dependency-change",
                )
                self.assertEqual(reopened["status"], "active")
            finally:
                memory.close()

    def test_real_field_appraises_and_assesses_an_ordinary_research_cycle(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8",
            )
            memory = CassiFieldWorkMemory(root / "field")
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                memory=memory,
            )
            try:
                self.create_program(director)
                advanced = director.run_one()
                self.assertEqual(advanced["cycles_completed"], 1)
                latest = advanced["recent_operations"][-1]
                self.assertIsNotNone(latest["selected_strategy"])
                affect_outcome = latest["affect_outcome"]
                self.assertEqual(
                    affect_outcome["appraisal"]["status"], "supported",
                )
                self.assertEqual(
                    affect_outcome["regulation_assessment"]["status"],
                    "supported",
                )
                view = director.program("resonance")["projection"]
                self.assertEqual(
                    view["current_question"],
                    "Which mechanism predicts the observed 17 Hz resonance?",
                )
                self.assertIsNotNone(view["grounded_affect_context"])
                self.assertTrue(
                    view["actual_affect_outcome"]["outcome_ref"]["id"].startswith(
                        "assessment:entity-research-outcome:"
                    )
                )
                autobiography = memory.inspect_living_memory(limit=8)["autobiography"]
                self.assertEqual(autobiography["unresolved"], 0)
                self.assertEqual(
                    [row["outcome"]["payload"]["consequence"]["kind"]
                     for row in autobiography["episodes"]],
                    ["research-plan-response"],
                )
            finally:
                memory.close()

    def test_real_field_recall_cancels_brain_outage_then_retries_one_cycle(self) -> None:
        class InterruptedBrain(ResearchBrain):
            def __init__(self) -> None:
                super().__init__()
                self.interrupted = False

            def complete(self, *, prompt: str, max_tokens: int, thinking: bool = False,
                         response_format: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
                if "AUTONOMOUS RESEARCH ACTION" in prompt and not self.interrupted:
                    self.interrupted = True
                    raise RuntimeError("simulated unavailable brain")
                return super().complete(
                    prompt=prompt, max_tokens=max_tokens, thinking=thinking,
                    response_format=response_format,
                )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            memory = CassiFieldWorkMemory(root / "field")
            director, _brain, _memory = self.make_director(
                root / "runtime", source, brain=InterruptedBrain(), memory=memory,
            )
            try:
                self.create_program(director)
                with self.assertRaisesRegex(RuntimeError, "simulated unavailable brain"):
                    director.run_one(program_id="resonance")
                completed = director.run_one(program_id="resonance")
                self.assertEqual(completed["cycles_completed"], 1)
                autobiography = memory.inspect_living_memory(limit=8)["autobiography"]
                self.assertEqual(len(autobiography["episodes"]), 2)
                self.assertEqual(autobiography["unresolved"], 0)
                self.assertEqual(
                    sum(
                        (row.get("outcome") or {}).get("payload", {}).get("consequence", {}).get("kind")
                        == "research-plan-response"
                        for row in autobiography["episodes"]
                    ),
                    1,
                )
            finally:
                memory.close()

    def test_restart_completes_durable_execution_without_repeating_the_effect(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = FakeFieldMemory()
            failing = ResearchBrain(
                action="write_artifact",
                arguments={"path": "notes/result.txt", "content": "  exact result\n", "media_type": "text/plain"},
                fail_first_synthesis=True,
            )
            first, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                brain=failing,
                memory=memory,
                default_tools=("write_artifact",),
            )
            self.create_program(first, tools=["write_artifact"])
            with self.assertRaises(ResearchBrainUnavailable):
                first.run_one()
            operation = first.store.operation("entity:research-cycle:resonance:00000001")
            self.assertEqual(operation["status"], "executed")

            recovered, _healthy, _same_memory = self.make_director(
                root / "runtime",
                source,
                brain=ResearchBrain(action="write_artifact"),
                memory=memory,
                default_tools=("write_artifact",),
            )
            recovered.recover()
            program = recovered.program("resonance")
            workspace_file = recovered.store.workspace("resonance") / "notes" / "result.txt"
            self.assertEqual(workspace_file.read_text(encoding="utf-8"), "  exact result\n")
            self.assertEqual(program["cycles_completed"], 1)
            events = recovered.events_after(0, program_id="resonance")
            self.assertEqual(sum(event["kind"] == "operation-executed" for event in events), 1)
            self.assertEqual(sum(event["kind"] == "operation-recovered" for event in events), 1)

    def test_foreground_turn_and_research_cycle_share_brain_without_starvation(self) -> None:
        class ConcurrentBrain(ResearchBrain):
            def __init__(self) -> None:
                super().__init__()
                self.guard = threading.Lock()
                self.active = 0
                self.max_active = 0

            def complete(self, **kwargs: Any) -> Mapping[str, Any]:
                with self.guard:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                try:
                    time.sleep(0.03)
                    return super().complete(**kwargs)
                finally:
                    with self.guard:
                        self.active -= 1

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n",
                encoding="utf-8",
            )
            brain = ConcurrentBrain()
            entity = FieldBrainEntity(
                EntityConfig(
                    root / "entity",
                    capability_root=source,
                    theory_root=source,
                    research_home=root / "research",
                    research_roots=(source,),
                    research_resident_enabled=False,
                ),
                brain=brain,
                memory=FakeFieldMemory(),
            )
            self.create_program(entity.researcher)
            barrier = threading.Barrier(3)
            outcomes: dict[str, Any] = {}
            failures: list[BaseException] = []

            def run_research() -> None:
                try:
                    barrier.wait()
                    outcomes["research"] = entity.researcher.run_one()
                except BaseException as exc:
                    failures.append(exc)

            def run_turn() -> None:
                try:
                    barrier.wait()
                    outcomes["turn"] = entity.receive_turn(
                        turn_id="concurrent-turn",
                        request_id="concurrent-message",
                        conversation_id="conversation",
                        project_id="physics",
                        content="State the next useful step.",
                        tool_catalog=[],
                        observed_at="2026-09-19T00:01:00Z",
                    )
                except BaseException as exc:
                    failures.append(exc)

            research_thread = threading.Thread(
                target=run_research,
                name="cassi-autonomous-researcher",
            )
            foreground_thread = threading.Thread(target=run_turn)
            research_thread.start()
            foreground_thread.start()
            barrier.wait()
            research_thread.join(timeout=30)
            foreground_thread.join(timeout=30)
            try:
                self.assertFalse(research_thread.is_alive(), "research cycle did not settle")
                self.assertFalse(foreground_thread.is_alive(), "foreground turn did not settle")
                self.assertEqual(failures, [])
                self.assertEqual(brain.max_active, 1)
                self.assertEqual(outcomes["research"]["cycles_completed"], 1)
                self.assertEqual(outcomes["turn"]["status"], "committed")
                self.assertEqual(outcomes["turn"]["activity"]["status"], "completed")
            finally:
                entity.close()

    def test_collective_action_binds_one_live_hive_candidate(self) -> None:
        gap = {
            "kind": "missing-input-binding",
            "port": "evidence",
            "expected": {
                "name": "evidence",
                "representation": "evidence",
                "symbol": "evidence_value",
                "unit": "score",
                "value_kind": "scalar",
            },
        }

        class CollectiveOrganism:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def collaboration_view(self) -> Mapping[str, Any]:
                return {
                    "investigations": [
                        {
                            "component_count": 1,
                            "contributed_stage_count": 0,
                            "request_id": "request-collective",
                            "stage_count": 1,
                            "stages": [],
                            "state": "assembling",
                            "synthesis_id": "synthesis-collective",
                        }
                    ],
                    "requests": [
                        {
                            "content": {
                                "request_id": "request-collective",
                                "objective": {
                                    "question": (
                                        "Which observation resolves the "
                                        "collective uncertainty?"
                                    ),
                                    "goal": "Choose the next useful contribution.",
                                },
                            },
                        }
                    ],
                    "capability_gaps": [
                        {
                            "gaps": [gap],
                            "synthesis_id": "synthesis-collective",
                        }
                    ],
                    "capability_dispatches": [],
                    "collective_actions": [],
                    "continuations": [],
                    "resource_allocations": [],
                }

            def advance_collective_investigation(
                self,
                *,
                operation_id: str,
                candidate: Mapping[str, Any],
            ) -> Mapping[str, Any]:
                selected = dict(candidate)
                self.calls.append(
                    {
                        "candidate": selected,
                        "operation_id": operation_id,
                    }
                )
                return {
                    "action_id": selected["action_id"],
                    "candidate": selected,
                    "effects": {"dispatches": []},
                    "kind": selected["kind"],
                    "operation_id": operation_id,
                    "reason": "member-assigned",
                    "schema": (
                        "cassifi.research-organism-collective-next-action.v1"
                    ),
                    "status": "routed",
                    "synthesis_id": selected["synthesis_id"],
                }

        class ChoiceBrain(ResearchBrain):
            def complete(
                self,
                *,
                prompt: str,
                max_tokens: int,
                thinking: bool = False,
                response_format: Mapping[str, Any] | None = None,
            ) -> Mapping[str, Any]:
                if "AUTONOMOUS RESEARCH ACTION" not in prompt:
                    return super().complete(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        thinking=thinking,
                        response_format=response_format,
                    )
                compact = json.loads(
                    prompt.split("PROGRAM\n", 1)[1].split(
                        "\n\nCAPABILITIES", 1
                    )[0]
                )
                candidate = compact["collective_investigations"][
                    "next_actions"
                ][0]
                return {
                    "content": json.dumps(
                        {
                            "summary": "Route the missing evidence contribution.",
                            "action": "collective-next",
                            "arguments": {
                                "action_id": candidate["action_id"],
                                "candidate_sha256": candidate[
                                    "candidate_sha256"
                                ],
                            },
                            "expected_information": (
                                "Whether the exact contribution is now routed."
                            ),
                            "skill_applications": [],
                        }
                    ),
                    "usage": {"completion_tokens": 16},
                }

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n",
                encoding="utf-8",
            )
            organism = CollectiveOrganism()
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                brain=ChoiceBrain(),
            )
            director.organism = organism
            self.create_program(director)


            advanced = director.run_one()
            self.assertIsNotNone(advanced)
            self.assertEqual(advanced["status"], "paused")
            self.assertEqual(len(organism.calls), 1)
            selected = organism.calls[0]["candidate"]
            self.assertEqual(
                selected["request_context"],
                {
                    "request_id": "request-collective",
                    "objective": {
                        "goal": "Choose the next useful contribution.",
                        "question": (
                            "Which observation resolves the collective "
                            "uncertainty?"
                        ),
                    },
                },
            )
            perspective = director.collective_investigation_perspective()
            self.assertEqual(perspective["next_action_count"], 1)
            self.assertEqual(selected, perspective["next_actions"][0])
            operation = director.store.operation(
                "entity:research-cycle:resonance:00000001"
            )
            self.assertIsNotNone(operation)
            assert operation is not None
            self.assertEqual(
                operation["plan"]["collective_candidate_snapshot"],
                selected,
            )
            self.assertEqual(
                operation["result"]["receipt"]["status"],
                "routed",
            )
            self.assertIn(
                "collective-next",
                director.capability_map()["tools"],
            )
            rejected = director._execute_planned(
                {
                    "operation_id": "manual-invalid-collective",
                    "program_id": "resonance",
                    "status": "planned",
                    "plan": {
                        "summary": "Attempt an invented collective target.",
                        "action": "collective-next",
                        "arguments": {
                            "action_id": "invented",
                            "candidate_sha256": "a" * 64,
                        },
                        "expected_information": "Nothing.",
                    },
                }
            )
            self.assertEqual(
                rejected["result"]["kind"], "capability-refusal"
            )
            self.assertEqual(len(organism.calls), 1)

    def test_collective_gap_development_is_brain_bounded_and_replay_stored(
        self,
    ) -> None:
        gap = {
            "kind": "missing-output-binding",
            "port": "confidence",
            "expected": {
                "name": "confidence",
                "value_kind": "scalar",
                "representation": "assessment",
                "unit": "score",
                "symbol": "confidence_value",
            },
        }
        gap_sha256 = hashlib.sha256(
            json.dumps(
                gap,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        source = {
            "component_id": "$request",
            "port": {
                "name": "candidate",
                "value_kind": "scalar",
                "representation": "field-program",
                "unit": "score",
                "symbol": "candidate_value",
            },
            "source_id": "source:collective-candidate",
            "symbol": "source_0",
        }

        class DevelopmentOrganism:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def collaboration_view(self) -> Mapping[str, Any]:
                return {
                    "investigations": [
                        {
                            "component_count": 1,
                            "contributed_stage_count": 0,
                            "request_id": "request-development",
                            "stage_count": 1,
                            "stages": [],
                            "state": "assembling",
                            "synthesis_id": "synthesis-development",
                        },
                    ],
                    "requests": [
                        {
                            "content": {
                                "request_id": "request-development",
                                "objective": {
                                    "goal": (
                                        "Construct the missing confidence "
                                        "capability."
                                    ),
                                },
                            },
                        },
                    ],
                    "capability_gaps": [
                        {
                            "gaps": [gap],
                            "synthesis_id": "synthesis-development",
                        },
                    ],
                    "capability_dispatches": [
                        {
                            "dispatch_id": "dispatch-development",
                            "gap": gap,
                            "state": "parked",
                            "synthesis_id": "synthesis-development",
                        },
                    ],
                    "capability_development_opportunities": [
                        {
                            "dispatch_id": "dispatch-development",
                            "expected": gap["expected"],
                            "gap_sha256": gap_sha256,
                            "maximum_work": 3,
                            "member_id": "member-002",
                            "opportunity_sha256": "d" * 64,
                            "provider_outcomes": {
                                "attempts": 0,
                                "failed": 0,
                                "pending": 0,
                                "succeeded": 0,
                                "reliability": 0.5,
                            },
                            "request_id": "request-development",
                            "role": "investigator",
                            "sources": [source],
                            "synthesis_id": "synthesis-development",
                        },
                    ],
                    "collective_actions": [],
                    "continuations": [],
                    "resource_allocations": [],
                }

            def advance_collective_investigation(
                self,
                *,
                operation_id: str,
                candidate: Mapping[str, Any],
                development: Mapping[str, Any] | None = None,
            ) -> Mapping[str, Any]:
                assert development is not None
                selected = {
                    "operation_id": operation_id,
                    "candidate": dict(candidate),
                    "development": dict(development),
                }
                self.calls.append(selected)
                return {
                    "action_id": candidate["action_id"],
                    "candidate": dict(candidate),
                    "development_sha256": hashlib.sha256(
                        json.dumps(
                            development,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "effects": {"method_sha256": "e" * 64},
                    "kind": candidate["kind"],
                    "operation_id": operation_id,
                    "reason": (
                        "developed-method-executed-and-continuation-"
                        "completed"
                    ),
                    "schema": (
                        "cassifi.research-organism-collective-next-action.v1"
                    ),
                    "status": "recovered",
                    "synthesis_id": candidate["synthesis_id"],
                }

        class DevelopmentBrain(ResearchBrain):
            def complete(
                self,
                *,
                prompt: str,
                max_tokens: int,
                thinking: bool = False,
                response_format: Mapping[str, Any] | None = None,
            ) -> Mapping[str, Any]:
                if "AUTONOMOUS RESEARCH ACTION" in prompt:
                    self.calls.append(prompt)
                    compact = json.loads(
                        prompt.split("PROGRAM\n", 1)[1].split(
                            "\n\nCAPABILITIES", 1
                        )[0]
                    )
                    candidate = compact["collective_investigations"][
                        "next_actions"
                    ][0]
                    value = {
                        "summary": (
                            "Develop the missing confidence method with "
                            "member-002."
                        ),
                        "action": "collective-next",
                        "arguments": {
                            "action_id": candidate["action_id"],
                            "candidate_sha256": candidate[
                                "candidate_sha256"
                            ],
                        },
                        "expected_information": (
                            "Whether the developed method executes in the "
                            "live composition."
                        ),
                        "skill_applications": [],
                    }
                    return {
                        "content": json.dumps(value),
                        "usage": {"completion_tokens": 96},
                    }
                if "COLLECTIVE CAPABILITY DEVELOPMENT" in prompt:
                    self.calls.append(prompt)
                    value = {
                        "schema": (
                            "cassi.entity."
                            "collective-capability-development.v1"
                        ),
                        "summary": (
                            "Preserve the bounded source score as confidence."
                        ),
                        "source_ids": [source["source_id"]],
                        "steps": [
                            {
                                "operation": "identity",
                                "output": "developed_output",
                                "inputs": [source["symbol"]],
                                "literal": None,
                            },
                        ],
                        "assumptions": [
                            "The source score is calibrated to the output scale."
                        ],
                        "preconditions": [
                            "The source is a finite scalar score."
                        ],
                        "effects": [
                            "Produces one assessment confidence score."
                        ],
                        "uncertainty": 0.25,
                    }
                    return {
                        "content": json.dumps(value),
                        "usage": {"completion_tokens": 144},
                    }
                return super().complete(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    thinking=thinking,
                    response_format=response_format,
                )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "sources"
            source_root.mkdir()
            brain = DevelopmentBrain()
            organism = DevelopmentOrganism()
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source_root,
                brain=brain,
            )
            director.organism = organism
            self.create_program(director)
            advanced = director.run_one()

            self.assertIsNotNone(advanced)
            assert advanced is not None
            self.assertEqual(advanced["status"], "paused")
            self.assertEqual(len(brain.calls), 3)
            self.assertIn(
                source["symbol"],
                brain.calls[1],
            )
            self.assertEqual(len(organism.calls), 1)
            development = organism.calls[0]["development"]
            self.assertEqual(
                development["schema"],
                "cassi.entity.collective-capability-development.v1",
            )
            self.assertEqual(
                development["steps"][0]["output"],
                "developed_output",
            )
            operation = director.store.operation(
                "entity:research-cycle:resonance:00000001"
            )
            self.assertIsNotNone(operation)
            assert operation is not None
            self.assertEqual(
                operation["plan"]["collective_candidate_snapshot"]["kind"],
                "develop-capability-gap",
            )
            self.assertEqual(
                operation["plan"]["arguments"]["development"],
                development,
            )
            self.assertEqual(
                operation["result"]["receipt"]["status"],
                "recovered",
            )

    def test_generated_program_code_runs_isolated_inside_the_workspace(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                default_tools=("write_artifact", "run_existing_python"),
            )
            program = self.create_program(director, tools=["write_artifact", "run_existing_python"])
            director.capabilities.execute(
                "write_artifact",
                {
                    "path": "generated.py",
                    "content": (
                        "import json, pathlib\n"
                        "value = sum(range(10))\n"
                        "pathlib.Path('computed.json').write_text(json.dumps({'total': value}))\n"
                        "print(json.dumps({'total': value}))\n"
                    ),
                },
                program=program,
                operation_id="manual-write",
            )
            run = director.capabilities.execute(
                "run_existing_python",
                {"script": "generated.py"},
                program=program,
                operation_id="manual-run",
            )["result"]
            self.assertEqual(run["returncode"], 0, run.get("stderr"))
            self.assertIn('"total": 45', run["stdout"])
            workspace = director.store.workspace(str(program["program_id"]))
            self.assertEqual(
                json.loads((workspace / "computed.json").read_text(encoding="utf-8")),
                {"total": 45},
            )

    def test_generated_program_code_cannot_escape_the_program_scope(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (root / "outside.py").write_text("print('outside')\n", encoding="utf-8")
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                default_tools=("write_artifact", "run_existing_python"),
            )
            program = self.create_program(director, tools=["write_artifact", "run_existing_python"])
            for script in (str(root / "outside.py"), "../outside.py"):
                with self.subTest(script=script):
                    with self.assertRaises(CapabilityDenied):
                        director.capabilities.execute(
                            "run_existing_python",
                            {"script": script},
                            program=program,
                            operation_id="manual-run",
                        )

    def test_obligation_is_revised_only_when_the_program_actually_changes(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            director, _brain, memory = self.make_director(root / "runtime", source)
            director.create_program(
                request_id="create-resonance",
                program_id="resonance",
                project_id="physics",
                title="Explain the resonance",
                mission="Establish what causes the measured resonance.",
                initial_question="What is actually observed?",
                observed_at="2026-09-19T00:00:00Z",
                cycle_limit=10,
                allowed_tools=["read_file"],
            )
            for _ in range(10):
                director.run_one()
            registers = [
                call
                for call in memory.semantic_calls
                if call["operation"] == "register"
                and str(call["record_id"]).startswith(
                    "entity:research-program-obligation:"
                )
            ]
            self.assertEqual(
                {str(call["record_id"]) for call in registers},
                {"entity:research-program-obligation:resonance"},
            )
            # A semantic record keeps a bounded revision history, so a program
            # that only advances must not spend a version per cycle.
            self.assertLessEqual(len(registers), 3)
            # Distinct content carries a distinct identity: a revision can
            # never be rejected as a conflicting reuse of an identity.
            self.assertEqual(
                len({str(call["operation_id"]) for call in registers}),
                len(registers),
            )
            self.assertFalse(
                any(
                    "question" in call["payload"] or "generation" in call["payload"]
                    for call in registers
                )
            )

    def test_a_collapsed_summary_cannot_delete_the_written_answer(self) -> None:
        class CollapsingBrain(ResearchBrain):
            def __init__(self) -> None:
                super().__init__()
                self.syntheses = 0

            def complete(self, **kwargs: Any) -> Mapping[str, Any]:
                response = super().complete(**kwargs)
                if "AUTONOMOUS RESEARCH SYNTHESIS" not in str(kwargs.get("prompt", "")):
                    return response
                self.syntheses += 1
                if self.syntheses < 2:
                    return response
                return {
                    "content": json.dumps(
                        {
                            "finding": "The driver script was written.",
                            "support_status": "observed",
                            "uncertainty": "The pipe still fails.",
                            "method": "Write a wrapper and pipe the payload.",
                            "next_question": "Does the wrapper run?",
                            "program_status": "active",
                            "report": " ".join(f"{index}." for index in range(1, 200)),
                        }
                    ),
                    "usage": {"completion_tokens": 64},
                }

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            director, brain, _memory = self.make_director(
                root / "runtime", source, brain=CollapsingBrain()
            )
            director.create_program(
                request_id="create-resonance",
                program_id="resonance",
                project_id="physics",
                title="Explain the resonance",
                mission="Establish what causes the measured resonance.",
                initial_question="What is actually observed?",
                observed_at="2026-09-19T00:00:00Z",
                cycle_limit=3,
                allowed_tools=["read_file"],
            )
            director.run_one()
            written = str(director.program("resonance")["report"])
            self.assertTrue(written)
            director.run_one()
            program = director.program("resonance")
            self.assertEqual(program["report"], written)
            self.assertEqual(
                program["claims"][-1]["support_status"], "no-result"
            )
            self.assertIn(
                "degenerated into enumeration", program["claims"][-1]["finding"]
            )
            self.assertEqual(brain.syntheses, 2)

    def test_a_faulted_responsibility_field_waits_and_recovers_admission(self) -> None:
        class FaultingMemory(FakeFieldMemory):
            def __init__(self) -> None:
                super().__init__()
                self.faulted = True

            def semantic(
                self,
                request: Mapping[str, Any],
                *,
                operation_label: str | None = None,
            ) -> Mapping[str, Any]:
                if self.faulted:
                    self.semantic_calls.append(dict(request))
                    raise RuntimeError(
                        "regional work-memory semantic request faulted before "
                        "settlement: status=counter-exhausted "
                        "diagnosis=error_code=WORK_CAPACITY"
                    )
                return super().semantic(request, operation_label=operation_label)

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = FaultingMemory()
            director, _brain, _memory = self.make_director(
                root / "runtime", source, memory=memory
            )
            with self.assertRaises(ResponsibilityAdmissionError):
                self.create_program(director)
            self.assertEqual(director.programs(), [])
            self.assertEqual(
                director.store.operation("create-resonance")["status"],
                "admitting",
            )
            memory.faulted = False
            admitted = self.create_program(director)
            self.assertEqual(admitted["status"], "active")
            self.assertIn(
                "entity:research-responsibility:charter",
                memory.semantic_records,
            )
            self.assertIn(
                "entity:research-responsibility:resonance",
                memory.semantic_records,
            )
            self.assertEqual(
                sum(
                    row["kind"] == "program-created"
                    for row in director.events_after(0)
                ),
                1,
            )

    def test_http_program_admission_advances_asynchronously_and_streams_events(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            brain = ResearchBrain()
            entity = FieldBrainEntity(
                EntityConfig(
                    root / "entity",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=source,
                    research_home=root / "research",
                    research_roots=(source,),
                    research_cycle_interval_seconds=0.05,
                    research_resident_enabled=True,
                    program_native_enabled=False,
                ),
                brain=brain,
            )
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
            headers = {"authorization": "Bearer " + "t" * 32, "content-type": "application/json"}
            try:
                body = json.dumps(
                    {
                        "request_id": "create-resonance",
                        "program_id": "resonance",
                        "project_id": "physics",
                        "title": "Explain the resonance",
                        "mission": "Establish what causes the measured resonance.",
                        "initial_question": "What is actually observed?",
                        "observed_at": "2026-09-19T00:00:00Z",
                        "cycle_limit": 1,
                        "allowed_tools": ["read_file"],
                    }
                )
                connection.request("POST", "/v1/programs", body=body, headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                response.read()

                deadline = time.monotonic() + 30
                program: Mapping[str, Any] = {}
                while time.monotonic() < deadline:
                    connection.request("GET", "/v1/programs/resonance", headers=headers)
                    current = connection.getresponse()
                    self.assertEqual(current.status, 200)
                    program = json.loads(current.read())
                    if program.get("cycles_completed") == 1:
                        break
                    time.sleep(0.05)
                self.assertEqual(program.get("status"), "paused")
                self.assertEqual(program.get("cycles_completed"), 1)

                connection.request("GET", "/v1/programs/resonance/events/stream?after=0", headers=headers)
                event_response = connection.getresponse()
                streamed = event_response.read().decode("utf-8")
                self.assertEqual(event_response.status, 200)
                self.assertIn("event: program-created", streamed)
                self.assertIn("event: program-advanced", streamed)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()


    def test_a_declared_deliverable_travels_the_http_route_and_gates_the_program(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            partial = {
                "schema": "cassi.laboratory.mission-evidence.v1",
                "fixture_id": "fixture-1",
                "stations": {"identification": {"law_id": "L1-native-w25"}},
            }
            brain = ResearchBrain(
                action="write_artifact",
                arguments={"path": "answer.json", "content": json.dumps(partial)},
                program_status="completed",
            )
            entity = FieldBrainEntity(
                EntityConfig(
                    root / "entity",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=source,
                    research_home=root / "research",
                    research_roots=(source,),
                    research_cycle_interval_seconds=0.05,
                    research_resident_enabled=True,
                    program_native_enabled=False,
                ),
                brain=brain,
            )
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
            headers = {"authorization": "Bearer " + "t" * 32, "content-type": "application/json"}
            try:
                body = json.dumps(
                    {
                        "request_id": "create-delivery-http",
                        "program_id": "delivery-http",
                        "project_id": "laboratory",
                        "title": "Deliver the counterflow answer",
                        "mission": "Answer every declared station.",
                        "initial_question": "Which stations must the answer cover?",
                        "observed_at": "2026-09-21T00:00:00Z",
                        "cycle_limit": 2,
                        "allowed_tools": ["write_artifact"],
                        "deliverable": {
                            "artifact": "answer.json",
                            "sections_key": "stations",
                            "sections": ["identification", "retention"],
                            "document_schema": "cassi.laboratory.mission-evidence.v1",
                            "identity_key": "fixture_id",
                            "identity_value": "fixture-1",
                        },
                    }
                )
                connection.request("POST", "/v1/programs", body=body, headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202, response.read().decode("utf-8"))
                response.read()

                deadline = time.monotonic() + 10
                program: Mapping[str, Any] = {}
                while time.monotonic() < deadline:
                    connection.request("GET", "/v1/programs/delivery-http", headers=headers)
                    current = connection.getresponse()
                    self.assertEqual(current.status, 200)
                    program = json.loads(current.read())
                    if program.get("cycles_completed") == 1:
                        break
                    time.sleep(0.05)
                self.assertEqual(program.get("cycles_completed"), 1)
                # the cycle said completed; the document says otherwise
                self.assertEqual(program.get("status"), "active")
                self.assertEqual(program["deliverable"]["artifact"], "answer.json")
                self.assertEqual(program["deliverable_state"]["covered"], ["identification"])
                self.assertEqual(program["deliverable_state"]["missing"], ["retention"])

                connection.request(
                    "GET", "/v1/programs/delivery-http/events/stream?after=0", headers=headers
                )
                event_response = connection.getresponse()
                streamed = event_response.read().decode("utf-8")
                self.assertEqual(event_response.status, 200)
                self.assertIn("event: deliverable-advanced", streamed)
                self.assertIn("event: deliverable-incomplete", streamed)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()

    def test_the_workbench_routes_read_one_program_and_report_a_change(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            entity = FieldBrainEntity(
                EntityConfig(
                    root / "entity",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=source,
                    research_home=root / "research",
                    research_roots=(source,),
                    research_cycle_interval_seconds=0.05,
                    research_resident_enabled=False,
                    program_native_enabled=False,
                ),
                brain=ResearchBrain(action="read_file", arguments={"path": "absent/never-written.txt"}),
            )
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=20)
            headers = {"authorization": "Bearer " + "t" * 32, "content-type": "application/json"}
            try:
                connection.request(
                    "POST",
                    "/v1/programs",
                    body=json.dumps(
                        {
                            "request_id": "create-workbench",
                            "program_id": "workbench-program",
                            "project_id": "physics",
                            "title": "Explain the resonance",
                            "mission": "Establish what causes the measured resonance.",
                            "initial_question": "What is actually observed?",
                            "observed_at": "2026-09-22T00:00:00Z",
                            "cycle_limit": 2,
                        }
                    ),
                    headers=headers,
                )
                created = connection.getresponse()
                self.assertEqual(created.status, 202)
                created.read()

                # The failing step is part of the fixture: the workbench
                # holds it afterwards.  The resident loop is off here, so the
                # cycles run through the same director entry point: the first
                # records the failure, the second waits instead of repeating it.
                director = entity.researcher
                director.run_one(program_id="workbench-program")
                advanced = director.run_one(program_id="workbench-program")
                self.assertEqual(advanced["status"], "blocked")

                connection.request("GET", "/v1/programs/workbench-program", headers=headers)
                response = connection.getresponse()
                program = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    program["workbench"]["schema"], "cassi.research-workbench-view.v1"
                )
                self.assertTrue(program["workbench"]["workspace_task_id"])

                connection.request(
                    "GET",
                    "/v1/programs/workbench-program/workbench"
                    "?question=Which%20mechanism%20explains%20the%20resonance%3F&maximum=16",
                    headers=headers,
                )
                response = connection.getresponse()
                context = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    context["schema"], "cassifi.research-workbench-context.v1"
                )
                self.assertTrue(context["field_revision"])
                identities = {
                    str(identity)
                    for row in context["failed_approaches"]
                    for identity in dict(row.get("dependencies") or {})
                }
                self.assertIn("path:absent/never-written.txt", identities)

                connection.request(
                    "GET", "/v1/programs/unknown-program/workbench", headers=headers
                )
                response = connection.getresponse()
                unknown = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertIn("unavailable", unknown)

                connection.request(
                    "POST",
                    "/v1/research/workbench/dependency-change",
                    body=json.dumps(
                        {
                            "request_id": "workbench-change",
                            "changes": {"path:absent/never-written.txt": "arrived"},
                            "program_ids": ["workbench-program"],
                        }
                    ),
                    headers=headers,
                )
                change = connection.getresponse()
                settled = json.loads(change.read())
                self.assertEqual(change.status, 202)
                self.assertEqual(settled["programs"][0]["program_id"], "workbench-program")
                self.assertTrue(settled["programs"][0]["wakeups"])
                self.assertEqual(settled["reopened"], ["workbench-program"])

                connection.request("GET", "/v1/programs/workbench-program", headers=headers)
                response = connection.getresponse()
                reopened = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(reopened["status"], "active")
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()

    def test_completed_program_retains_its_field_duty_and_reopens_on_reported_consequence(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            brain = ResearchBrain()
            entity = FieldBrainEntity(
                EntityConfig(
                    root / "entity",
                    capability_root=Path(__file__).resolve().parents[1],
                    theory_root=source,
                    research_home=root / "research",
                    research_roots=(source,),
                    research_resident_enabled=False,
                    program_native_enabled=False,
                ),
                brain=brain,
            )
            server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token="t" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_address[1], timeout=20
            )
            headers = {
                "authorization": "Bearer " + "t" * 32,
                "content-type": "application/json",
            }

            def exchange(method: str, path: str, body: Mapping[str, Any] | None = None) -> tuple[int, Any]:
                connection.request(
                    method, path,
                    body=None if body is None else json.dumps(body),
                    headers=headers,
                )
                response = connection.getresponse()
                return response.status, json.loads(response.read())

            try:
                status, created = exchange("POST", "/v1/programs", {
                    "request_id": "create-human-impact",
                    "program_id": "human-impact",
                    "project_id": "research",
                    "title": "Test a useful explanation",
                    "mission": "Produce a human-reviewable explanation.",
                    "initial_question": "What evidence is needed?",
                    "observed_at": "2026-09-22T00:00:00Z",
                    "cycle_limit": 2,
                    "responsibility": {
                        "affected": ["participants"],
                        "intended_benefit": "Support their chosen questions.",
                        "possible_burdens": ["Time spent reviewing a mistaken conclusion."],
                        "decision_owner": "participants",
                        "review_question": "Could they inspect and correct the conclusion?",
                    },
                })
                self.assertEqual(status, 202, created)
                status, completed = exchange(
                    "POST", "/v1/programs/human-impact/control", {
                        "request_id": "complete-human-impact",
                        "action": "complete",
                        "observed_at": "2026-09-22T00:01:00Z",
                    }
                )
                self.assertEqual(status, 202, completed)
                self.assertEqual(completed["status"], "completed")
                status, before = exchange("GET", "/v1/responsibilities/snapshot")
                self.assertEqual(status, 200, before)
                rows = {row["reference"]["id"]: row for row in before["records"]}
                self.assertIn("entity:research-responsibility:charter", rows)
                duty = rows["entity:research-responsibility:human-impact"]
                self.assertEqual(duty["record"]["payload"]["state"], "pending")
                self.assertEqual(
                    duty["record"]["payload"]["responsibility"]["decision_owner"],
                    "participants",
                )

                report = {
                    "request_id": "impact-report-1",
                    "observed_at": "2026-09-22T00:02:00Z",
                    "consequence": {
                        "dimension": "agency",
                        "affected": "participants",
                        "observation": "A participant could not revise the conclusion.",
                        "evidence": "Participant report, pending independent review.",
                        "uncertainty": "Access control may explain the failed edit.",
                        "status": "reported",
                        "follow_up": "Check correction access with the participant.",
                    },
                }
                status, accepted = exchange(
                    "POST", "/v1/programs/human-impact/consequences", report
                )
                self.assertEqual(status, 202, accepted)
                self.assertEqual(accepted["program_status"], "active")
                status, replay = exchange(
                    "POST", "/v1/programs/human-impact/consequences", report
                )
                self.assertEqual(status, 202, replay)
                self.assertEqual(accepted, replay)
                status, conflict = exchange(
                    "POST", "/v1/programs/human-impact/consequences",
                    {**report, "consequence": {**report["consequence"], "observation": "Different claim."}},
                )
                self.assertEqual(status, 409, conflict)
                status, program = exchange("GET", "/v1/programs/human-impact")
                self.assertEqual(status, 200, program)
                self.assertEqual(len(program["consequence_ledger"]), 1)
                self.assertEqual(
                    program["consequence_ledger"][0]["provenance"],
                    "caller-reported; not independently verified",
                )
                status, after = exchange("GET", "/v1/responsibilities/snapshot")
                self.assertEqual(status, 200, after)
                duty = next(
                    row for row in after["records"]
                    if row["reference"]["id"] == "entity:research-responsibility:human-impact"
                )
                self.assertEqual(
                    duty["record"]["payload"]["responsibility"]["outstanding_assessments"][0]["consequence"]["follow_up"],
                    report["consequence"]["follow_up"],
                )
                self.assertEqual(
                    duty["record"]["payload"]["consequence_ledger"][0]["consequence"],
                    report["consequence"],
                )
                self.assertNotEqual(before["records_sha256"], after["records_sha256"])
                entity.researcher.run_one()
                action_prompt = next(
                    prompt for prompt in brain.calls
                    if "AUTONOMOUS RESEARCH ACTION" in prompt
                )
                self.assertIn(report["consequence"]["observation"], action_prompt)
                self.assertIn(report["consequence"]["follow_up"], action_prompt)
                self.assertIn("participants", action_prompt)
                review = {
                    "request_id": "impact-review-1",
                    "observed_at": "2026-09-22T00:03:00Z",
                    "consequence": {
                        "dimension": "agency",
                        "affected": "another group",
                        "observation": "The original group reviewed the change.",
                        "evidence": "Review conversation.",
                        "uncertainty": "Long-term effects remain unknown.",
                        "status": "observed",
                        "follow_up": None,
                        "review_of_assessment_id": accepted["assessment_id"],
                    },
                }
                status, wrong_group = exchange(
                    "POST", "/v1/programs/human-impact/consequences", review
                )
                self.assertEqual(status, 400, wrong_group)
                review["consequence"]["affected"] = "participants"
                status, accepted_review = exchange(
                    "POST", "/v1/programs/human-impact/consequences", review
                )
                self.assertEqual(status, 202, accepted_review)
                self.assertEqual(
                    accepted_review["assessment"]["consequence"]["review_of_assessment_id"],
                    accepted["assessment_id"],
                )
                status, after_review = exchange(
                    "GET", "/v1/responsibilities/snapshot"
                )
                self.assertEqual(status, 200, after_review)
                duty = next(
                    row for row in after_review["records"]
                    if row["reference"]["id"] == "entity:research-responsibility:human-impact"
                )
                self.assertEqual(
                    duty["record"]["payload"]["responsibility"]["outstanding_assessments"],
                    [],
                )
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()


if __name__ == "__main__":
    unittest.main()
