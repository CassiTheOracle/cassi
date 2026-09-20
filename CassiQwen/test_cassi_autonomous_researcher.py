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
    ResearchBrainUnavailable,
    ResearchRuntimeConfig,
)
from cassi_field_brain_entity import EntityConfig, FieldBrainEntity
from cassi_field_brain_server import EntityHTTPServer


class FakeFieldMemory:
    def __init__(self) -> None:
        self.records: list[Mapping[str, Any]] = []
        self.semantic_records: dict[str, Mapping[str, Any]] = {}
        self.semantic_calls: list[Mapping[str, Any]] = []
        self.generation = 0
        self.closed = False

    def _sha(self) -> str:
        return hashlib.sha256(f"field:{self.generation}".encode()).hexdigest()

    def learn(self, record: Any) -> Mapping[str, Any]:
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
            return {"result": {"status": "supported", "record": {"id": request["record_id"]}}}
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
        raise AssertionError(f"unexpected semantic operation: {request['operation']}")

    def recall(self, context: Mapping[str, Any], *, operation_label: str) -> Mapping[str, Any]:
        rows = [value for value in self.records if value["context"] == context]
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
    ) -> None:
        self.action = action
        self.arguments = dict(arguments or {"path": "evidence.txt"})
        self.fail_first_synthesis = fail_first_synthesis
        self.calls: list[str] = []

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
                "program_status": "active",
                "report": "A 17 Hz resonance is observed; its mechanism remains open.",
            }
        else:
            value = {"response": "unused"}
        return {"content": json.dumps(value), "usage": {"completion_tokens": 32}}


class AutonomousResearchDirectorTest(unittest.TestCase):
    def make_director(
        self,
        home: Path,
        source_root: Path,
        *,
        brain: ResearchBrain | None = None,
        memory: FakeFieldMemory | None = None,
        default_tools: tuple[str, ...] = ("read_file",),
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

    def test_generated_program_code_cannot_run_as_an_existing_source_script(self) -> None:
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
            write_result = director.capabilities.execute(
                "write_artifact",
                {"path": "generated.py", "content": "print('unsafe')\n"},
                program=program,
                operation_id="manual-write",
            )
            with self.assertRaises(CapabilityDenied):
                director.capabilities.execute(
                    "run_existing_python",
                    {"script": write_result["result"]["workspace_path"]},
                    program=program,
                    operation_id="manual-run",
                )

    def test_http_program_admission_advances_asynchronously_and_streams_events(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            brain = ResearchBrain()
            memory = FakeFieldMemory()
            entity = FieldBrainEntity(
                EntityConfig(
                    root / "entity",
                    capability_root=source,
                    theory_root=source,
                    research_home=root / "research",
                    research_roots=(source,),
                    research_cycle_interval_seconds=0.05,
                    research_resident_enabled=True,
                ),
                brain=brain,
                memory=memory,
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

                deadline = time.monotonic() + 5
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


if __name__ == "__main__":
    unittest.main()
