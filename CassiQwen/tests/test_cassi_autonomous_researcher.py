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
    ResearchResponseRunaway,
    ResearchSynthesisDegenerated,
    ResearchRuntimeConfig,
    _research_source_refs,
    _resolve_next_required_refs,
)
from cassi_field_brain_entity import EntityConfig, FieldBrainEntity
from cassi_field_brain_server import EntityHTTPServer
from cassi_field_qwen_workbench import CassiFieldWorkMemory, ResearchWorkbench
from cassi_research_organism import OrganismError, ResearchOrganism
from cassi_resonant_field import REGIONAL_KERNEL_NAME, resume_regional_state
from cassi_resident_qwen_client import ResidentQwenCancelled


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
                        "object_id": request.get("object_id"),
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
                "source_observations": [
                    {"ref": "resonance:reading", "quote": "Measured resonance: 17 Hz"}
                ],
            }
        else:
            value = {"response": "unused"}
        return {"content": json.dumps(value), "usage": {"completion_tokens": 32}}


class PredictionComparisonBrain(ResearchBrain):
    def __init__(self, *, invalid_quote: bool = False, action: str = "read_file") -> None:
        super().__init__(
            action=action,
            arguments={"script": "generated.py"} if action == "run_existing_python" else None,
        )
        self.invalid_quote = invalid_quote

    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        response = super().complete(
            prompt=prompt, max_tokens=max_tokens, thinking=thinking,
            response_format=response_format,
        )
        value = json.loads(response["content"])
        if "AUTONOMOUS RESEARCH ACTION" in prompt and self.action == "read_file":
            value["discrimination"] = {
                "explanation_a": "A stable oscillator",
                "prediction_a": "The source reads 17 Hz",
                "explanation_b": "A drifting oscillator",
                "prediction_b": "The source reads 20 Hz",
                "choice_reason": "The observed frequency distinguishes the explanations.",
            }
        elif "AUTONOMOUS RESEARCH ACTION" in prompt and self.action == "run_existing_python":
            value["discrimination"] = {
                "explanation_a": "The calculation totals 45",
                "prediction_a": "The program prints total 45",
                "explanation_b": "The calculation totals 40",
                "prediction_b": "The program prints total 40",
                "choice_reason": "The computed total separates the predictions.",
            }
        elif "AUTONOMOUS RESEARCH SYNTHESIS" in prompt and self.action == "read_file":
            if self.invalid_quote:
                value["source_observations"][0]["quote"] = "Measured resonance: 19 Hz"
            value["prediction_outcome"] = {
                "prediction_a": {
                    "status": "supported", "evidence_refs": ["source:0"],
                    "reason": "The quoted frequency is 17 Hz.",
                },
                "prediction_b": {
                    "status": "contradicted", "evidence_refs": ["source:0"],
                    "reason": "The quoted frequency differs from 20 Hz.",
                },
                "next_step_reason": "Check an independent source for the oscillator mechanism.",
            }
        elif "AUTONOMOUS RESEARCH SYNTHESIS" in prompt and self.action == "run_existing_python":
            value.pop("source_observations", None)
            value["finding"] = "The calculation printed total 45."
            value["support_status"] = "derived"
            value["prediction_outcome"] = {
                "prediction_a": {
                    "status": "supported", "evidence_refs": ["result"],
                    "reason": "The completed calculation printed total 45.",
                },
                "prediction_b": {
                    "status": "contradicted", "evidence_refs": ["result"],
                    "reason": "The completed calculation differs from total 40.",
                },
                "next_step_reason": "Check the calculation against a second source.",
            }
        return {**response, "content": json.dumps(value)}


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
        field_shelf: Path | None = None,
    ) -> tuple[AutonomousResearchDirector, ResearchBrain, FakeFieldMemory]:
        actual_brain = brain or ResearchBrain()
        actual_memory = memory or FakeFieldMemory()
        director = AutonomousResearchDirector(
            ResearchRuntimeConfig(
                home=home,
                allowed_roots=(source_root,),
                cycle_interval_seconds=0.05,
                default_tools=default_tools,
                field_shelf=field_shelf,
            ),
            brain=actual_brain,
            memory=actual_memory,
            workbench=workbench,
        )
        return director, actual_brain, actual_memory

    @staticmethod
    def create_program(
        director: AutonomousResearchDirector,
        *,
        tools: list[str] | None = None,
        cycle_limit: int = 1,
    ) -> Mapping[str, Any]:
        return director.create_program(
            request_id="create-resonance",
            program_id="resonance",
            project_id="physics",
            title="Explain the resonance",
            mission="Establish what causes the measured resonance.",
            initial_question="What is actually observed?",
            observed_at="2026-09-19T00:00:00Z",
            cycle_limit=cycle_limit,
            allowed_tools=tools,
        )

    def test_synthesis_source_aliases_resolve_before_frontier_persistence(self) -> None:
        program = {
            "current_question_id": "q-current",
            "frontier": [
                {
                    "question_id": "q-current",
                    "required_refs": ["source:0", "instrument:input-a"],
                }
            ],
        }
        source_refs = _research_source_refs(program, {"gaps": ["source:1"]})
        self.assertEqual(source_refs, ["instrument:input-a"])
        self.assertEqual(
            _resolve_next_required_refs(["source:0"], source_refs),
            ["instrument:input-a"],
        )
        with self.assertRaises(ResearchBrainUnavailable):
            _resolve_next_required_refs(["source:1"], source_refs)
        with self.assertRaises(ResearchBrainUnavailable):
            _resolve_next_required_refs(["source:0"], [])
        view = AutonomousResearchDirector._prompt_workbench(
            {
                "required": ["source:0", "instrument:input-a"],
                "gaps": ["source:1"],
                "selected": [{"key": "source-record:actual"}],
            },
            blocked=False,
        )
        self.assertEqual(view["required"], ["instrument:input-a"])
        self.assertEqual(view["gaps"], [])
        self.assertEqual(view["selected"], [{"key": "source-record:actual"}])

    def test_thinking_runaway_replans_once_without_repeating_the_tool(self) -> None:
        class RunawayThinkingBrain(ResearchBrain):
            def __init__(self) -> None:
                super().__init__()
                self.action_modes: list[bool] = []

            def complete(
                self, *, prompt: str, max_tokens: int, thinking: bool = False,
                response_format: Mapping[str, Any] | None = None,
            ) -> Mapping[str, Any]:
                if "AUTONOMOUS RESEARCH ACTION" in prompt:
                    self.action_modes.append(thinking)
                    if thinking:
                        return {"content": "", "finish_reason": "length"}
                return super().complete(
                    prompt=prompt, max_tokens=max_tokens, thinking=thinking,
                    response_format=response_format,
                )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8",
            )
            brain = RunawayThinkingBrain()
            director, _, _ = self.make_director(root / "runtime", source, brain=brain)
            self.create_program(director, tools=["read_file"])
            advanced = director.run_one()
            self.assertEqual(brain.action_modes, [True, False])
            self.assertEqual(advanced["claims"][-1]["support_status"], "observed")
            self.assertEqual(advanced["cycles_completed"], 1)

    def test_unthinking_plan_runaway_blocks_then_recovers_with_the_failure_as_guidance(self) -> None:
        class RunawayPlanBrain(ResearchBrain):
            def __init__(self) -> None:
                super().__init__()
                self.action_modes: list[bool] = []

            def complete(
                self, *, prompt: str, max_tokens: int, thinking: bool = False,
                response_format: Mapping[str, Any] | None = None,
            ) -> Mapping[str, Any]:
                if "AUTONOMOUS RESEARCH ACTION" in prompt:
                    self.action_modes.append(thinking)
                    if "did not finish" not in prompt:
                        return {"content": "{\"summary\": \"omega1 = 1.0, omega2", "finish_reason": "length"}
                return super().complete(
                    prompt=prompt, max_tokens=max_tokens, thinking=thinking,
                    response_format=response_format,
                )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8",
            )
            brain = RunawayPlanBrain()
            director, _, _ = self.make_director(root / "runtime", source, brain=brain)
            self.create_program(director, tools=["read_file", "write_artifact"])
            with self.assertRaises(ResearchResponseRunaway):
                director.run_one()
            # A greedy replay of an unthinking request is the same runaway.
            self.assertEqual(brain.action_modes, [False])
            blocked = director.store.program("resonance")
            self.assertEqual(blocked["status"], "blocked")
            self.assertIn("did not finish", blocked["last_error"])
            advanced = director.run_one()
            self.assertEqual(brain.action_modes, [False, False])
            self.assertEqual(advanced["recoveries"], 1)
            self.assertEqual(advanced["cycles_completed"], 1)
            self.assertEqual(advanced["claims"][-1]["support_status"], "observed")

    def test_source_observation_requires_literal_bytes_from_captured_revision(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            path = source / "evidence.txt"
            data = b"calibration report\nreading:A:3\n"
            path.write_bytes(data)
            director, _, _ = self.make_director(root / "runtime", source)
            program = dict(self.create_program(director))
            program["frontier"] = [
                {
                    **row,
                    "required_refs": ["reading:A"],
                }
                for row in program["frontier"]
            ]
            operation_id = "read-source"
            revision = hashlib.sha256(data).hexdigest()
            artifact = director.store.put_artifact(
                data, media_type="application/octet-stream",
                label=path.name, program_id="resonance",
                operation_id=operation_id,
                metadata={
                    "source_path": str(path), "start_byte": 0,
                    "source_revision_sha256": revision,
                },
            )
            operation = {
                "operation_id": operation_id,
                "plan": {"action": "read_file"},
                "result": {
                    "path": str(path), "artifact": artifact,
                    "start_byte": 0, "source_revision_sha256": revision,
                },
            }
            observations = director._verified_source_observations(
                program, operation,
                {"source_observations": [
                    {"ref": "reading:A", "quote": "reading:A:99"},
                    {"ref": "reading:A", "quote": "reading:A:3"},
                ]},
            )
            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0]["value"]["value"], "reading:A:3")
            self.assertEqual(observations[0]["value"]["byte_start"], data.index(b"reading:A:3"))
            self.assertEqual(observations[0]["value"]["source_revision_sha256"], revision)
            self.assertEqual(
                director._verified_source_observations(
                    program, operation,
                    {"source_observations": [
                        {"ref": "unrequested:reading", "quote": "reading:A:3"},
                    ]},
                ),
                [],
            )
            new_source = director._verified_source_observations(
                program, operation, {"source_observations": []},
            )
            self.assertEqual(len(new_source), 1)
            self.assertEqual(new_source[0]["value"]["ref"], str(path))
            self.assertNotIn("reading:A", new_source[0]["source_refs"])
            exact_path_program = {
                **program,
                "frontier": [
                    {
                        **row,
                        "required_refs": [str(path)],
                    }
                    for row in program["frontier"]
                ],
            }
            fallback = director._verified_source_observations(
                exact_path_program, operation, {"source_observations": []},
            )
            self.assertEqual(len(fallback), 1)
            self.assertEqual(fallback[0]["value"]["ref"], str(path))
            self.assertEqual(fallback[0]["value"]["value"], data.decode("utf-8"))
            self.assertEqual(fallback[0]["value"]["byte_end"], len(data))
            for prefix in ("path:", "source:"):
                prefixed_program = {
                    **program,
                    "frontier": [
                        {**row, "required_refs": [prefix + path.as_posix()]}
                        for row in program["frontier"]
                    ],
                }
                prefixed_observations = director._verified_source_observations(
                    prefixed_program, operation, {"source_observations": []},
                )
                self.assertEqual(prefixed_observations[0]["value"]["value"], data.decode("utf-8"))
            discovered_program = {
                **program,
                "frontier": [
                    {**row, "required_refs": []}
                    for row in program["frontier"]
                ],
            }
            discovered_quote = director._verified_source_observations(
                discovered_program, operation,
                {"source_observations": [
                    {"ref": "unrequested:reading", "quote": "reading:A:3"},
                ]},
            )
            self.assertEqual(len(discovered_quote), 1)
            self.assertEqual(discovered_quote[0]["value"]["ref"], str(path))
            self.assertEqual(discovered_quote[0]["value"]["value"], "reading:A:3")
            discovered_fallback = director._verified_source_observations(
                discovered_program, operation, {"source_observations": []},
            )
            self.assertEqual(len(discovered_fallback), 1)
            self.assertEqual(discovered_fallback[0]["value"]["ref"], str(path))
            self.assertEqual(discovered_fallback[0]["value"]["value"], data.decode("utf-8"))
            discovered_quote = director._verified_source_observations(
                discovered_program, operation,
                {"source_observations": [
                    {"ref": str(path), "quote": "reading:A:3"},
                ]},
            )
            self.assertEqual(discovered_quote[0]["value"]["value"], "reading:A:3")
            operation["result"]["source_revision_sha256"] = "0" * 64
            self.assertEqual(
                director._verified_source_observations(
                    program, operation,
                    {"source_observations": [{"ref": "reading:A", "quote": "reading:A:3"}]},
                ),
                [],
            )

    def test_library_citations_pin_exact_spans_in_field_held_files(self) -> None:
        import subprocess

        from cassi_field_foundry import FieldShelf

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            corpus.mkdir()
            # Non-ASCII text ahead of every quoted span: a character offset
            # would land before the true byte offset.
            notes = (
                "# Chamber resonance\n\n"
                "Messung — the chamber was swept from 5 Hz to 40 Hz in quarter-hertz "
                "steps while the pressure probe logged amplitude. Measured resonance: "
                "17 Hz, with the peak holding its position across all three "
                "calibration sweeps and both probe mountings.\n\n"
                "# Damping\n\n"
                "Ring-down after each sweep gave a damping ratio ζ ≈ 0.02, so the "
                "quality factor sits near twenty-five and the peak stays narrow "
                "enough to separate from the 34 Hz harmonic that appears when the "
                "drive amplitude doubles.\n"
            ).encode("utf-8")
            (corpus / "resonance.md").write_bytes(notes)
            (corpus / "drive.md").write_bytes(
                b"# Drive electronics\n\nThe class-D amplifier stays flat from "
                b"2 Hz to 2 kHz and is not the source of any chamber peak.\n"
            )
            for command in (
                ("init", "-q"),
                ("config", "core.autocrlf", "false"),
                ("add", "resonance.md", "drive.md"),
            ):
                subprocess.run(["git", "-C", str(corpus), *command], check=True)
            shelf_home = root / "shelf"
            FieldShelf(shelf_home).add(
                {"name": "notes", "kind": "library", "config": {"root": str(corpus)}}
            )
            tools = ("library_search", "library_read")
            revision = hashlib.sha256(notes).hexdigest()
            source = "library:notes/resonance.md"
            quote = "damping ratio ζ ≈ 0.02"
            expected_start = notes.index(quote.encode("utf-8"))
            expected_end = expected_start + len(quote.encode("utf-8"))

            director, _, _ = self.make_director(
                root / "runtime", corpus, default_tools=tools, field_shelf=shelf_home,
            )
            program = dict(self.create_program(director, tools=list(tools)))
            search = director.capabilities.execute(
                "library_search", {"query": "resonance damping ratio", "library": "notes"},
                program=program, operation_id="search-library",
            )
            woken = search["result"]["artifact"]["metadata"]["passages"]
            self.assertEqual(
                {row["source"] for row in woken}, {source},
            )
            self.assertEqual(len(woken), 2)
            search_operation = {
                "operation_id": "search-library",
                "plan": {"action": "library_search"},
                "result": search,
            }
            admitted = director._verified_source_observations(
                program, search_operation,
                {"source_observations": [
                    {"ref": "damping", "quote": quote},
                    {"ref": "absent", "quote": "damping ratio ζ ≈ 0.20"},
                ]},
            )
            self.assertEqual(len(admitted), 1)
            value = admitted[0]["value"]
            self.assertEqual(value["source"], source)
            self.assertEqual(value["source_revision_sha256"], revision)
            self.assertEqual(
                (value["byte_start"], value["byte_end"]), (expected_start, expected_end),
            )
            self.assertEqual(notes[value["byte_start"]:value["byte_end"]].decode("utf-8"), quote)
            self.assertEqual(
                admitted[0]["dependencies"][f"source:{source}"], revision,
            )
            # Two woken passages sit side by side in the search artifact; a
            # quote bridging them names no contiguous span of any file.
            artifact_bytes = director.store.artifact_bytes(
                search["result"]["artifact"]["sha256"]
            )
            first, second = sorted(woken, key=lambda row: row["artifact_start"])
            bridge = artifact_bytes[
                first["artifact_end"] - 12:second["artifact_start"] + 12
            ].decode("utf-8")
            self.assertIn(bridge.encode("utf-8"), artifact_bytes)
            self.assertEqual(
                director._verified_source_observations(
                    program, search_operation,
                    {"source_observations": [{"ref": "bridge", "quote": bridge}]},
                ),
                [],
            )

            # An exact read from the middle of the file reports file offsets.
            damping_start = notes.index(b"# Damping")
            read = director.capabilities.execute(
                "library_read",
                {"library": "notes", "path": "resonance.md", "start_byte": damping_start},
                program=program, operation_id="read-library",
            )
            read_admitted = director._verified_source_observations(
                program,
                {"operation_id": "read-library", "plan": {"action": "library_read"}, "result": read},
                {"source_observations": [{"ref": "damping", "quote": quote}]},
            )
            self.assertEqual(len(read_admitted), 1)
            self.assertEqual(read_admitted[0]["value"]["source"], source)
            self.assertEqual(
                (read_admitted[0]["value"]["byte_start"], read_admitted[0]["value"]["byte_end"]),
                (expected_start, expected_end),
            )
            self.assertEqual(read_admitted[0]["value"]["source_revision_sha256"], revision)

            # The whole research cycle: the brain searches the library and the
            # program's report cites the verified span under its library ref.
            cycle, _, _ = self.make_director(
                root / "cycle-runtime", corpus,
                brain=ResearchBrain(
                    action="library_search",
                    arguments={"query": "measured resonance", "library": "notes"},
                ),
                default_tools=tools, field_shelf=shelf_home,
            )
            self.create_program(cycle, tools=list(tools))
            advanced = cycle.run_one()
            claim = advanced["claims"][-1]
            self.assertEqual(claim["support_status"], "observed")
            self.assertIn(
                "source-observation:entity:research-cycle:resonance:00000001:0",
                claim["evidence_refs"],
            )
            self.assertIn(f"{source}: Measured resonance: 17 Hz", advanced["report"])

            # Without a configured shelf the library stays closed.
            closed, _, _ = self.make_director(
                root / "closed-runtime", corpus, default_tools=tools,
            )
            closed_program = self.create_program(closed, tools=list(tools))
            self.assertFalse(closed.capabilities.libraries_available)
            with self.assertRaises(CapabilityDenied):
                closed.capabilities.execute(
                    "library_search", {"query": "resonance"},
                    program=closed_program, operation_id="closed-search",
                )

    def test_prediction_comparison_survives_field_reopen_and_guides_next_action(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            brain = PredictionComparisonBrain()
            memory = CassiFieldWorkMemory(root / "field")
            try:
                workbench = ResearchWorkbench(memory, member_id="researcher")
                director, _, _ = self.make_director(
                    root / "runtime", source, brain=brain, memory=memory,
                    workbench=workbench,
                )
                self.create_program(director, tools=["read_file"], cycle_limit=2)
                first = director.run_one(program_id="resonance")
                outcome = first["claims"][-1]["prediction_outcome"]
                self.assertEqual(outcome["favored_explanation"], "a")
                self.assertEqual(outcome["assessment"], "brain-interpreted")
                self.assertEqual(
                    (outcome["prediction_a"]["status"], outcome["prediction_b"]["status"]),
                    ("supported", "contradicted"),
                )
                source_ref = "source-observation:entity:research-cycle:resonance:00000001:0"
                self.assertEqual(outcome["prediction_a"]["evidence_refs"], [source_ref])
                self.assertEqual(outcome["prediction_b"]["evidence_refs"], [source_ref])
                self.assertIn(source_ref, first["claims"][-1]["evidence_refs"])
                context = director._workbench_context(first)
                self.assertIsNotNone(context)
                assert context is not None
                guidance = next(
                    row for row in context["selected"]
                    if row["key"] == "discrimination:entity:research-cycle:resonance:00000001"
                )
                self.assertEqual(guidance["value"]["prediction_outcome"], outcome)
                self.assertEqual(guidance["source_refs"], [source_ref])

                memory.close()
                memory = CassiFieldWorkMemory(root / "field")
                brain.action = "reason"
                brain.arguments = {}
                reopened, _, _ = self.make_director(
                    root / "runtime", source, brain=brain, memory=memory,
                    workbench=ResearchWorkbench(memory, member_id="researcher"),
                )
                reopened.recover()
                second = reopened.run_one(program_id="resonance")
                self.assertEqual(second["cycles_completed"], 2)
                next_prompt = [
                    prompt for prompt in brain.calls
                    if "AUTONOMOUS RESEARCH ACTION" in prompt
                ][-1]
                self.assertIn('"favored_explanation": "a"', next_prompt)
                self.assertIn("Check an independent source", next_prompt)
                self.assertEqual(second["claims"][0]["prediction_outcome"], outcome)
            finally:
                memory.close()

    def test_unverified_source_cannot_choose_between_predictions(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            director, _, _ = self.make_director(
                root / "runtime", source,
                brain=PredictionComparisonBrain(invalid_quote=True),
            )
            self.create_program(director, tools=["read_file"])
            result = director.run_one(program_id="resonance")
            outcome = result["claims"][-1]["prediction_outcome"]
            self.assertEqual(result["claims"][-1]["support_status"], "no-result")
            self.assertEqual(outcome["favored_explanation"], "undetermined")
            self.assertEqual(
                (outcome["prediction_a"]["status"], outcome["prediction_b"]["status"]),
                ("unresolved", "unresolved"),
            )
            self.assertEqual(outcome["prediction_a"]["evidence_refs"], [])
            self.assertEqual(outcome["prediction_b"]["evidence_refs"], [])
            self.assertEqual(result["claims"][-1]["evidence_refs"], [])

    def test_successful_source_read_remains_usable_after_unsupported_quote(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8",
            )
            memory = CassiFieldWorkMemory(root / "field")
            try:
                workbench = ResearchWorkbench(memory, member_id="researcher")
                director, _, _ = self.make_director(
                    root / "runtime", source,
                    brain=PredictionComparisonBrain(invalid_quote=True),
                    memory=memory, workbench=workbench,
                )
                self.create_program(director, tools=["read_file"], cycle_limit=2)
                program = director.run_one(program_id="resonance")
                self.assertEqual(program["claims"][-1]["support_status"], "no-result")
                context = director._workbench_context(program)
                assert context is not None
                self.assertFalse(context["failed_approaches"])
            finally:
                memory.close()


    def test_completed_calculation_can_compare_predictions_but_failure_cannot(self) -> None:
        for script, expected_statuses in (
            ("print('{\"total\": 45}')\n", ("supported", "contradicted")),
            ("raise RuntimeError('measurement failed')\n", ("unresolved", "unresolved")),
        ):
            with self.subTest(script=script), TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "sources"
                source.mkdir()
                director, _, _ = self.make_director(
                    root / "runtime", source,
                    brain=PredictionComparisonBrain(action="run_existing_python"),
                    default_tools=("write_artifact", "run_existing_python"),
                )
                program = self.create_program(
                    director, tools=["write_artifact", "run_existing_python"],
                )
                director.capabilities.execute(
                    "write_artifact", {"path": "generated.py", "content": script},
                    program=program, operation_id="write-comparison-script",
                )
                result = director.run_one(program_id="resonance")
                claim = result["claims"][-1]
                outcome = claim["prediction_outcome"]
                self.assertEqual(
                    (outcome["prediction_a"]["status"], outcome["prediction_b"]["status"]),
                    expected_statuses,
                )
                if expected_statuses[0] == "supported":
                    self.assertEqual(claim["support_status"], "derived")
                    self.assertEqual(outcome["favored_explanation"], "a")
                    self.assertIn(
                        "result:entity:research-cycle:resonance:00000001",
                        claim["evidence_refs"],
                    )
                else:
                    self.assertEqual(claim["support_status"], "no-result")
                    self.assertEqual(outcome["favored_explanation"], "undetermined")
                    self.assertEqual(claim["evidence_refs"], [])

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
            first_outcome = first_method["observed_consequence"]["method_outcome"]
            assessment_id = first["recent_operations"][-1]["affect_outcome"]["outcome_ref"]["id"]
            self.assertEqual(
                memory.semantic_records[assessment_id]["payload"]["method_outcome"],
                first_outcome,
            )
            self.assertEqual(
                first_outcome["reported_method_ids"],
                ["claim-independent-check-next-experiment"],
            )
            self.assertEqual(first_outcome["result_kind"], "read_file")
            self.assertEqual(first_outcome["attribution"], "association")
            self.assertEqual(
                set(first_outcome["measured_elapsed_ns"]),
                {"planning_elapsed_ns", "action_elapsed_ns", "synthesis_elapsed_ns"},
            )
            self.assertTrue(
                all(value >= 0 for value in first_outcome["measured_elapsed_ns"].values())
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
            next_program = json.loads(
                action_prompts[1].split("PROGRAM\n", 1)[1].split("\n\nCAPABILITIES", 1)[0]
            )
            self.assertEqual(
                next_program["methods"][-1]["observed_consequence"]["method_outcome"],
                first_outcome,
            )
            later_outcome = second["methods"][-1]["observed_consequence"]["method_outcome"]
            self.assertEqual(later_outcome["result_kind"], "reasoning")
            self.assertIsNone(later_outcome["artifact_sha256"])
            self.assertEqual(later_outcome["attribution"], "association")

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

    def test_unknown_skill_phase_does_not_block_research_action(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8"
            )
            brain = ResearchBrain()
            brain.skill_applications = [
                {
                    "skill_id": "claim-independent-check-next-experiment",
                    "phase": "invented phase",
                }
            ]
            director, _, _ = self.make_director(
                root / "runtime",
                source,
                brain=brain,
                default_tools=("read_file",),
            )
            self.create_program(director)

            result = director.run_one(program_id="resonance")

            self.assertEqual(result["cycles_completed"], 1)
            self.assertEqual(result["methods"][-1]["skill_applications"], [])


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

    def test_context_gap_request_preserves_selected_question_sources(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = CassiFieldWorkMemory(root / "field")
            workbench = ResearchWorkbench(memory, member_id="researcher")
            director, _, _ = self.make_director(
                root / "runtime", source, memory=memory, workbench=workbench,
            )
            try:
                program = self.create_program(director)
                projection = director._workbench_program(program)
                workbench.sync(
                    projection,
                    operation_id="observation-with-gap",
                    outcome={
                        "question": "What is actually observed?",
                        "question_id": program["current_question_id"],
                        "required_refs": ["measurement", "missing-calibration"],
                        "records": [
                            {"key": "measurement", "kind": "observation", "value": [17]},
                        ],
                    },
                )
                before = director._workbench_context(program)
                self.assertIsNotNone(before)
                assert before is not None
                selected = director._root_method_sources_from_workbench(program, before)
                self.assertEqual([row["identity"]["key"] for row in selected], ["measurement"])
                self.assertIn("missing-calibration", before["gaps"])

                director._retain_context_request(program, before)
                after = director._workbench_context(program)
                self.assertIsNotNone(after)
                assert after is not None
                self.assertEqual(
                    [row["source_id"] for row in director._root_method_sources_from_workbench(program, after)],
                    [row["source_id"] for row in selected],
                )
                self.assertIn("missing-calibration", after["gaps"])
            finally:
                memory.close()

    def test_paper_observation_workbench_source_retains_causal_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = CassiFieldWorkMemory(root / "field")
            workbench = ResearchWorkbench(memory, member_id="researcher")
            organism = ResearchOrganism(
                root / "organism",
                workspace=Path(__file__).resolve().parents[2],
                member_ids=("member-a",),
                root_owner=memory.owner,
                root_lock=threading.RLock(),
            )
            organism.initialize()
            director, _, _ = self.make_director(
                root / "runtime", source, memory=FakeFieldMemory(), workbench=workbench,
            )
            try:
                program = self.create_program(director)
                receipt_path = str((root / "paper-receipt.json").resolve())
                receipt_sha = "a" * 64
                event_sha = "b" * 64
                mathematical_observation = {
                    "schema": "cassi.trading-mathematical-observation.v1",
                    "source": {
                        "canonical_event_id": "paper:event-1",
                        "canonical_event_sha256": event_sha,
                        "source_id": "paper-source",
                        "source_revision": 3,
                        "observed_at": "2026-09-24T12:00:00Z",
                        "available_at": "2026-09-24T12:00:01Z",
                        "accepted_event_root_sha256": "c" * 64,
                    },
                    "market": {
                        "symbol": "XYZ",
                        "open": 10.0,
                        "high": 12.0,
                        "low": 9.0,
                        "close": 11.0,
                        "volume": 1200,
                    },
                    "decision": {
                        "field_decision_event_id": "decision:1",
                        "state": "applied",
                        "requested_target": 0.5,
                        "applied_target": 0.4,
                        "selection_source": "field",
                    },
                    "paper": {
                        "execution_model": "paper",
                        "disposition": "filled",
                        "fill": {"quantity": 2, "price": 11.0},
                        "account": {"cash": 978.0, "position": 2},
                        "feed_health": "healthy",
                    },
                    "modeled_field_outcomes": {"return": 0.1, "drawdown": 0.02},
                }
                operation = {
                    "operation_id": "paper-step-1",
                    "plan": {"action": "activity_run", "arguments": {}},
                    "result": {
                        "result": {
                            "artifact": {
                                "sha256": receipt_sha,
                                "metadata": {
                                    "source_path": receipt_path,
                                    "source_revision_sha256": receipt_sha,
                                },
                            },
                            "source_refs": [
                                receipt_sha, event_sha, event_sha, "", "  ", "x" * 513,
                                *(f"extra:{index}" for index in range(20)),
                            ],
                            "mathematical_observation": mathematical_observation,
                        }
                    },
                }
                step_records = director._step_records(
                    program,
                    operation,
                    {"support_status": "observed"},
                    {"claim_id": "claim:paper", "finding": "Observed paper outcome."},
                    "What happened in the paper step?",
                )
                observation = step_records["observations"][0]
                expected_refs = [receipt_sha, receipt_path, event_sha]
                expected_refs.extend(f"extra:{index}" for index in range(10))
                self.assertEqual(observation["source_refs"], expected_refs)
                self.assertLessEqual(len(observation["source_refs"]), 18)
                self.assertNotIn("x" * 513, observation["source_refs"])
                self.assertEqual(
                    observation["dependencies"][f"source:{Path(receipt_path).as_posix()}"],
                    receipt_sha,
                )
                projection = director._workbench_program(program)
                outcome = {
                    "question": "What happened in the paper step?",
                    "question_id": program["current_question_id"],
                    "records": [observation],
                }
                workbench.sync(
                    projection, operation_id="paper-step-sync", outcome=outcome,
                )
                context = director._workbench_context(program)
                self.assertIsNotNone(context)
                assert context is not None
                selected = director._root_method_sources_from_workbench(program, context)
                self.assertEqual(len(selected), 1)
                source_row = selected[0]
                self.assertEqual(source_row["identity"]["source_refs"], expected_refs)
                selected_observation = source_row["value"]["result"]["mathematical_observation"]
                self.assertEqual(selected_observation["market"]["close"], 11.0)
                self.assertEqual(selected_observation["paper"]["fill"]["quantity"], 2)
                self.assertEqual(selected_observation["paper"]["account"]["position"], 2)
                self.assertEqual(
                    selected_observation["modeled_field_outcomes"]["return"], 0.1
                )
                source_identity = source_row["source_id"]
                method = organism.create_root_guest_research_method(
                    operation_id="paper-observation-method",
                    program_id=program["program_id"],
                    question_id=program["current_question_id"],
                    question="What is the fill price's movement from market open?",
                    proposal={
                        "schema": "cassi.entity.root-guest-method-proposal.v1",
                        "summary": "Measure actual paper fill movement from market open.",
                        "source_ids": [source_identity],
                        "source": (
                            'result = input_0["result"]["mathematical_observation"]'
                            '["paper"]["fill"]["price"] - '
                            'input_0["result"]["mathematical_observation"]'
                            '["market"]["open"]'
                        ),
                        "assumptions": ["The fill and market open use the same price unit."],
                        "preconditions": ["The observation includes an actual paper fill and market open."],
                        "effects": ["Return the observed fill movement."],
                        "uncertainty": 0.0,
                    },
                    sources=selected,
                    runtime=workbench.runtime,
                    member_id=workbench.member_id,
                )
                self.assertEqual(method["outputs"]["result"], 1.0)
                unchanged_context = director._workbench_context(program)
                self.assertIsNotNone(unchanged_context)
                assert unchanged_context is not None
                unchanged = director._root_method_sources_from_workbench(
                    program, unchanged_context
                )
                self.assertEqual([row["source_id"] for row in unchanged], [source_identity])
            finally:
                memory.close()

    def test_supported_guest_method_reuses_across_programs_with_distinct_assessments(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = CassiFieldWorkMemory(root / "field")
            workbench = ResearchWorkbench(memory, member_id="researcher")
            organism = ResearchOrganism(
                root / "organism",
                workspace=Path(__file__).resolve().parents[2],
                member_ids=("member-a",),
                root_owner=memory.owner,
                root_lock=threading.RLock(),
            )
            organism.initialize()
            director, _, _ = self.make_director(
                root / "runtime", source, memory=memory, workbench=workbench,
            )
            try:
                programs = {}
                selected = {}
                for name, values in (("alpha", [1, 2]), ("beta", [3, 5]), ("gamma", 7)):
                    program = director.create_program(
                        request_id=f"create-{name}", program_id=name,
                        project_id="physics", title=f"Examine {name}",
                        mission="Compare these sampled measurements.",
                        initial_question="What does the dataset imply?",
                        observed_at="2026-09-19T00:00:00Z",
                        cycle_limit=3, allowed_tools=["read_file"],
                    )
                    workbench.sync(
                        director._workbench_program(program),
                        operation_id=f"source-{name}",
                        outcome={
                            "question": "What does the dataset imply?",
                            "question_id": program["current_question_id"],
                            "required_refs": ["dataset"],
                            "records": [{"key": "dataset", "kind": "observation", "value": values}],
                        },
                    )
                    context = director._workbench_context(program)
                    self.assertIsNotNone(context)
                    assert context is not None
                    programs[name] = program
                    selected[name] = director._root_method_sources_from_workbench(program, context)
                    self.assertEqual(len(selected[name]), 1)
                origin = selected["alpha"][0]["source_id"]
                first = organism.create_root_guest_research_method(
                    operation_id="method-alpha", program_id="alpha",
                    question_id=programs["alpha"]["current_question_id"],
                    question="What does the dataset imply?",
                    proposal={
                        "schema": "cassi.entity.root-guest-method-proposal.v1",
                        "summary": "Sum the two measurements.",
                        "source_ids": [origin],
                        "source": "result = input_0[0] + input_0[1]",
                        "assumptions": ["Both samples share one unit."],
                        "preconditions": ["The dataset has two numbers."],
                        "effects": ["Produce their sum."],
                        "uncertainty": 0.0,
                    },
                    sources=selected["alpha"], runtime=workbench.runtime,
                    member_id=workbench.member_id,
                )
                self.assertEqual(first["outputs"]["result"], 3)
                perspective = organism.root_guest_method_perspective(
                    "beta", selected["beta"],
                )
                candidate = next(
                    row for row in perspective["methods"]
                    if row["method_id"] == first["method_id"]
                )
                self.assertEqual(candidate["program_id"], "alpha")
                self.assertIn("Both samples share one unit.", candidate["assumptions"])
                incompatible = organism.root_guest_method_perspective(
                    "gamma", selected["gamma"],
                )
                self.assertFalse(any(
                    row["method_id"] == first["method_id"]
                    for row in incompatible["methods"]
                ))
                second = organism.execute_retained_root_guest_research_method(
                    method_id=candidate["method_id"],
                    method_sha256=candidate["method_sha256"],
                    operation_id="method-beta", program_id="beta",
                    question_id=programs["beta"]["current_question_id"],
                    question="What does the dataset imply?",
                    sources=selected["beta"],
                    bindings={"input_0": selected["beta"][0]["source_id"]},
                    runtime=workbench.runtime, member_id=workbench.member_id,
                )
                self.assertEqual(second["outputs"]["result"], 8)
                self.assertNotEqual(first["execution_event_ref"], second["execution_event_ref"])
                self.assertNotEqual(first["assessment"], second["assessment"])
                with self.assertRaises(OrganismError):
                    organism.execute_retained_root_guest_research_method(
                        method_id=candidate["method_id"],
                        method_sha256="0" * 64,
                        operation_id="bad-digest-beta", program_id="beta",
                        question_id=programs["beta"]["current_question_id"],
                        question="What does the dataset imply?",
                        sources=selected["beta"],
                        bindings={"input_0": selected["beta"][0]["source_id"]},
                        runtime=workbench.runtime, member_id=workbench.member_id,
                    )
            finally:
                memory.close()


    def test_root_method_representation_constructs_and_reuses_assessed_guest(self) -> None:
        class MethodBrain(ResearchBrain):
            def complete(self, *, prompt: str, max_tokens: int,
                         thinking: bool = False,
                         response_format: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
                self.calls.append(prompt)
                if "ROOT METHOD REPRESENTATION" in prompt:
                    value = {
                        "representation": "root-guest",
                        "reason": "Sorting for a median exceeds finite arithmetic primitives.",
                    }
                elif "ROOT GUEST METHOD APPLICABILITY" in prompt:
                    sources = json.loads(prompt.split("BOUND SOURCES\n", 1)[1])
                    odd = all(len(row["value"]) % 2 == 1 for row in sources)
                    value = {
                        "status": "applicable" if odd else "inapplicable",
                        "reason": "The selected sample has odd length." if odd else "The odd-length assumption is contradicted.",
                    }
                elif "ROOT GUEST PYTHON METHOD CONSTRUCTION" in prompt:
                    source_ids = [
                        row["source_id"]
                        for row in json.loads(prompt.split("SELECTED SOURCES\n", 1)[1])
                    ]
                    values = json.loads(prompt.split("SELECTED SOURCES\n", 1)[1])[0]["value"]
                    odd = len(values) % 2 == 1
                    value = {
                        "schema": "cassi.entity.root-guest-method-proposal.v1",
                        "summary": "Find the median of a finite numeric sample.",
                        "source_ids": source_ids,
                        "source": (
                            "ordered = sorted(input_0)\nresult = ordered[len(ordered) // 2]"
                            if odd else
                            "ordered = sorted(input_0)\nmid = len(ordered) // 2\nresult = (ordered[mid - 1] + ordered[mid]) / 2"
                        ),
                        "assumptions": [f"The sample has {'odd' if odd else 'even'} length and comparable measurements."],
                        "preconditions": ["The sample contains at least one finite number."],
                        "effects": ["Return the sample median."],
                        "uncertainty": 0.0,
                    }
                else:
                    raise AssertionError("unexpected method brain prompt")
                return {"content": json.dumps(value), "usage": {"completion_tokens": 64}}

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = CassiFieldWorkMemory(root / "field")
            workbench = ResearchWorkbench(memory, member_id="researcher")
            organism = ResearchOrganism(
                root / "organism",
                workspace=Path(__file__).resolve().parents[2],
                member_ids=("member-a",),
                root_owner=memory.owner,
                root_lock=threading.RLock(),
            )
            organism.initialize()
            brain = MethodBrain()
            director, _, _ = self.make_director(
                root / "runtime", source, brain=brain, memory=memory, workbench=workbench,
            )
            director.organism = organism
            try:
                def selected(name: str, values: Any) -> tuple[Mapping[str, Any], Mapping[str, Any], list[Mapping[str, Any]]]:
                    program = director.create_program(
                        request_id=f"create-{name}", program_id=name, project_id="physics",
                        title=f"Sample {name}", mission="Determine a sample median.",
                        initial_question="What is the sample median?",
                        observed_at="2026-09-19T00:00:00Z", cycle_limit=3,
                        allowed_tools=["read_file"],
                    )
                    workbench.sync(
                        director._workbench_program(program), operation_id=f"source-{name}",
                        outcome={
                            "question": "What is the sample median?",
                            "question_id": program["current_question_id"],
                            "required_refs": ["sample"],
                            "records": [{"key": "sample", "kind": "observation", "value": values}],
                        },
                    )
                    context = director._workbench_context(program)
                    assert context is not None
                    return program, context, director._root_method_sources_from_workbench(program, context)

                alpha, context, sources = selected("alpha", [7, 1, 3])
                choice = director._prepare_root_research_method_plan(
                    {"action": "root-research-method", "arguments": {}},
                    program=alpha, workbench_context=context, sources=sources,
                    perspective=director._root_research_method_perspective(alpha, sources),
                )
                self.assertEqual(choice["action"], "root-guest-method")
                constructed = director._prepare_root_guest_method_plan(
                    choice, program=alpha, workbench_context=context, sources=sources,
                    perspective=director._root_guest_method_perspective(alpha, sources),
                )
                first = director._execute_root_guest_method_action(
                    {"operation_id": "median-alpha", "plan": constructed}, alpha,
                )
                receipt = first["receipt"]
                self.assertEqual(receipt["status"], "supported")
                self.assertEqual(receipt["outputs"]["result"], 3)
                self.assertIsNotNone(receipt["assessment"])
                assessed = director._method_outcome(
                    alpha,
                    {
                        "operation_id": "median-alpha",
                        "plan": constructed,
                        "result": first,
                    },
                    {"support_status": "derived"},
                )
                self.assertEqual(assessed["method_lineage"]["source_ids"], [sources[0]["source_id"]])
                self.assertEqual(assessed["method_lineage"]["assessment"], receipt["assessment"])
                self.assertEqual(constructed["root_guest_method_snapshot"]["source_ids"], [sources[0]["source_id"]])

                beta, beta_context, beta_sources = selected("beta", [8, 2, 5])
                perspective = director._root_guest_method_perspective(beta, beta_sources)
                method = next(row for row in perspective["methods"] if row["method_id"] == receipt["method_id"])
                self.assertEqual(method["program_id"], "alpha")
                reuse = director._prepare_root_guest_method_plan(
                    {
                        "action": "root-guest-method",
                        "arguments": {
                            "method_id": method["method_id"],
                            "method_sha256": method["method_sha256"],
                            "bindings": {"input_0": beta_sources[0]["source_id"]},
                        },
                    },
                    program=beta, workbench_context=beta_context, sources=beta_sources,
                    perspective=perspective,
                )
                second = director._execute_root_guest_method_action(
                    {"operation_id": "median-beta", "plan": reuse}, beta,
                )["receipt"]
                self.assertEqual(second["status"], "supported")
                self.assertEqual(second["outputs"]["result"], 5)
                self.assertNotEqual(receipt["execution_event_ref"], second["execution_event_ref"])
                self.assertNotEqual(receipt["assessment"], second["assessment"])
                self.assertEqual(reuse["root_guest_method_snapshot"]["origin_program_id"], "alpha")

                delta, delta_context, delta_sources = selected("delta", [4, 10, 6, 12])
                correction = director._prepare_root_guest_method_plan(
                    {
                        "action": "root-guest-method",
                        "arguments": {
                            "method_id": method["method_id"],
                            "method_sha256": method["method_sha256"],
                            "bindings": {"input_0": delta_sources[0]["source_id"]},
                        },
                    },
                    program=delta, workbench_context=delta_context,
                    sources=delta_sources,
                    perspective=director._root_guest_method_perspective(delta, delta_sources),
                )
                self.assertEqual(correction["root_guest_method_snapshot"]["mode"], "construct")
                self.assertEqual(correction["method_reconsideration"]["status"], "inapplicable")
                corrected = director._execute_root_guest_method_action(
                    {"operation_id": "median-delta", "plan": correction}, delta,
                )["receipt"]
                self.assertEqual(corrected["status"], "supported")
                self.assertEqual(corrected["outputs"]["result"], 8)
                self.assertNotEqual(corrected["method_sha256"], receipt["method_sha256"])

                gamma, _, gamma_sources = selected("gamma", 3)
                self.assertFalse(any(
                    row["method_id"] == method["method_id"]
                    for row in director._root_guest_method_perspective(gamma, gamma_sources)["methods"]
                ))
            finally:
                memory.close()

    def test_exhausted_field_agenda_falls_back_and_researches(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8",
            )
            memory = FakeFieldMemory()
            director, _brain, _memory = self.make_director(
                root / "runtime",
                source,
                memory=memory,
            )
            original_semantic = memory.semantic

            def exhausted_agenda(
                request: Mapping[str, Any],
                *,
                operation_label: str | None = None,
            ) -> Mapping[str, Any]:
                if request.get("operation") == "autonomous-agenda":
                    return {
                        "result": {
                            "status": "resource-exhausted",
                            "limitations": ["semantic-work-bound"],
                        }
                    }
                return original_semantic(
                    request,
                    operation_label=operation_label,
                )

            try:
                self.create_program(director, tools=["read_file"])
                memory.semantic = exhausted_agenda
                advanced = director.run_one()
                self.assertEqual(advanced["program_id"], "resonance")
                self.assertEqual(advanced["cycles_completed"], 1)
                faults = [
                    event
                    for event in director.events_after(0)
                    if event["kind"] == "field-agenda-fault"
                ]
                self.assertEqual(len(faults), 1)
                self.assertEqual(
                    faults[0]["payload"]["result"]["status"],
                    "resource-exhausted",
                )
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
            brain = SkillSelectingResearchBrain()
            director, brain, _memory = self.make_director(
                root / "runtime",
                source,
                brain=brain,
                memory=memory,
            )
            try:
                self.create_program(director, cycle_limit=2)
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
                first_outcome = advanced["methods"][-1]["observed_consequence"]["method_outcome"]
                self.assertEqual(
                    first_outcome["reported_method_ids"],
                    ["claim-independent-check-next-experiment"],
                )
                brain.action = "reason"
                brain.arguments = {}
                continued = director.run_one()
                self.assertEqual(continued["cycles_completed"], 2)
                self.assertIsNotNone(
                    continued["recent_operations"][-1]["selected_strategy"]
                )
                action_prompts = [
                    prompt for prompt in brain.calls
                    if "AUTONOMOUS RESEARCH ACTION" in prompt
                ]
                self.assertIn("method_outcome", action_prompts[1])
                self.assertIn(first_outcome["result_sha256"], action_prompts[1])
                self.assertEqual(
                    [event for event in director.events_after(0) if event["kind"] == "field-agenda-fault"],
                    [],
                )
            finally:
                memory.close()
    def test_pause_interrupts_scoped_generation_and_resume_replans(self) -> None:
        class PausingBrain(ResearchBrain):
            supports_activity_scope = True

            def __init__(self) -> None:
                super().__init__()
                self.started = threading.Event()
                self.release = threading.Event()

            def complete(
                self, *, prompt: str, max_tokens: int, thinking: bool = False,
                response_format: Mapping[str, Any] | None = None,
                activity_id: str | None = None,
                cancel_event: threading.Event | None = None,
            ) -> Mapping[str, Any]:
                self.started.set()
                deadline = time.monotonic() + 5
                while not self.release.is_set() and time.monotonic() < deadline:
                    if cancel_event is not None and cancel_event.wait(0.02):
                        raise ResidentQwenCancelled("program:resonance", "pause-during-generation")
                if cancel_event is not None and cancel_event.is_set():
                    raise ResidentQwenCancelled("program:resonance", "pause-during-generation")
                return super().complete(
                    prompt=prompt, max_tokens=max_tokens, thinking=thinking,
                    response_format=response_format,
                )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            brain = PausingBrain()
            director, _, _ = self.make_director(root / "runtime", source, brain=brain)
            self.create_program(director, cycle_limit=2)
            errors: list[BaseException] = []

            def run_cycle() -> None:
                try:
                    director.run_one(program_id="resonance")
                except BaseException as exc:
                    errors.append(exc)

            worker = threading.Thread(target=run_cycle)
            worker.start()
            self.assertTrue(brain.started.wait(5))
            controller = threading.Thread(target=lambda: director.control_program(
                request_id="pause-during-generation",
                program_id="resonance",
                action="pause",
                observed_at="2026-09-23T00:00:00Z",
            ))
            controller.start()
            try:
                controller.join(3)
                self.assertFalse(controller.is_alive(), "pause waited for model generation")
                self.assertEqual(director.program("resonance")["status"], "paused")
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0], ResidentQwenCancelled)
            finally:
                brain.release.set()
                controller.join(6)
                worker.join(6)
            director.control_program(
                request_id="resume-after-interruption",
                program_id="resonance",
                action="resume",
                observed_at="2026-09-23T00:01:00Z",
            )
            self.assertEqual(director.run_one(program_id="resonance")["cycles_completed"], 1)


    def test_research_cycle_contributes_to_its_owner_working_field_and_opens_a_branch(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            memory = CassiFieldWorkMemory(root / "field")
            organism = ResearchOrganism(
                root / "organism",
                workspace=Path(__file__).resolve().parents[2],
                member_ids=("member-a",),
                root_owner=memory.owner,
                root_lock=threading.RLock(),
            )
            organism.initialize()
            memory.ensure_embodied_circulation()
            brain = ResearchBrain()
            director, _, _ = self.make_director(
                root / "runtime", source, brain=brain, memory=memory,
            )
            director.organism = organism
            try:
                created = self.create_program(director, cycle_limit=4)
                opened = organism.inspect_working_fields()
                field = next(row for row in opened["items"] if row["field_id"] == "resonance")
                self.assertEqual(field["question"], "What is actually observed?")
                self.assertEqual(created["status"], "active")
                first = director.run_one(program_id="resonance")
                contributed = next(
                    row for row in organism.inspect_working_fields()["items"]
                    if row["field_id"] == "resonance"
                )
                outcome_ref = first["recent_operations"][-1]["affect_outcome"]["outcome_ref"]
                assessed = next(
                    row for row in memory.owner.state.computers
                    if row.computer_id == "field-qwen:work-memory"
                )._value("task")["records"][outcome_ref["id"]][-1]
                assert assessed["payload"]["source_revision_id"] in assessed["support_roots"]
                feedback = first["recent_operations"][-1]["affect_outcome"][
                    "entity_exchange_feedback"
                ]
                self.assertEqual(feedback["status"], "updated")
                self.assertGreater(feedback["parameter_work"], 0.0)
                exchange_view = memory.owner.inspect_embodied_field()["exchange_meaning"]
                self.assertEqual(exchange_view["status"], "known")
                self.assertEqual(
                    exchange_view["items"][0]["assessment_ref"], outcome_ref,
                )
                bridge_ref = contributed["contribution"]["evidence_refs"][0]
                with organism._root_residency() as root_residency:
                    bridge = root_residency._record(bridge_ref["id"])
                self.assertEqual(bridge["payload"]["external_assessment_ref"], outcome_ref)
                self.assertEqual(
                    bridge["payload"]["result_source"]["source_id"],
                    "entity-research-result:entity:research-cycle:resonance:00000001",
                )
                operation_id = "entity:research-cycle:resonance:00000001"
                self.assertEqual(
                    director.store.operation(operation_id)["working_field_status"],
                    "contributed",
                )
                first_operation = director.store.operation(operation_id)
                concern_ref = first_operation["field_selection"][
                    "_working_field_concern_ref"
                ]
                self.assertEqual(
                    concern_ref["question_ref"]["id"],
                    "entity:research-question:resonance:q-000001",
                )
                self.assertEqual(concern_ref["question_ref"]["kind"], "Value")
                self.assertEqual(
                    concern_ref["goal_ref"]["id"], "entity:research-goal:resonance"
                )
                self.assertEqual(concern_ref["goal_ref"]["kind"], "Value")
                brain.action = "organize_working_field"
                brain.arguments = {
                    "operation": "branch",
                    "field_id": "resonance:branch:mechanism",
                    "payload": {
                        "question": "Which mechanism predicts the observed resonance?",
                        "branch_purpose": "Examine a sustaining mechanism",
                        "expected_contribution": "A source-grounded prediction",
                    },
                }
                second = director.run_one(program_id="resonance")
                second_operation = director.store.operation(
                    "entity:research-cycle:resonance:00000002"
                )
                fields = {
                    row["field_id"]: row
                    for row in organism.inspect_working_fields()["items"]
                }
                self.assertEqual(second["cycles_completed"], 2)
                self.assertEqual(self.create_program(director, cycle_limit=4), second)
                self.assertEqual(
                    fields["resonance:branch:mechanism"]["parent_ref"]["id"],
                    fields["resonance"]["program_ref"]["id"],
                )
                self.assertEqual(
                    director.store.operation(
                        "entity:research-cycle:resonance:00000002"
                    )["working_field_status"],
                    "organized",
                )
                organism.advance_working_field(
                    "research-test-open-instrument",
                    field_id="resonance:branch:instrument",
                    action="branch",
                    update={
                        "parent_field_id": "resonance",
                        "parent_ref": fields["resonance"]["program_ref"],
                        "question": "Does the measured value persist?",
                        "branch_purpose": "Check temporal persistence in the observation",
                        "purpose": "Compare the observation over time",
                        "expected_contribution": {
                            "kind": "measurement",
                            "value": 0.5,
                            "uncertainty": 0.5,
                            "cost": 0.5,
                        },
                    },
                )
                fields = {
                    row["field_id"]: row
                    for row in organism.inspect_working_fields()["items"]
                }
                parent_ids = [
                    "resonance:branch:mechanism",
                    "resonance:branch:instrument",
                ]
                brain.action = "organize_working_field"
                brain.arguments = {
                    "operation": "merge",
                    "field_id": "resonance:merge:combined",
                    "payload": {
                        "parent_field_ids": parent_ids,
                        "parent_refs": [
                            fields[field_id]["program_ref"] for field_id in parent_ids
                        ],
                        "question": "Which mechanism explains persistent oscillation?",
                        "branch_purpose": "Combine source and instrument investigations",
                        "purpose": "Combine source and instrument investigations",
                        "expected_contribution": {
                            "kind": "comparison",
                            "value": 1.0,
                            "uncertainty": 0.0,
                            "cost": 0.0,
                        },
                    },
                }
                third = director.run_one(program_id="resonance")
                self.assertEqual(third["cycles_completed"], 3)
                merged_fields = {
                    row["field_id"]: row
                    for row in organism.inspect_working_fields()["items"]
                }
                self.assertEqual(
                    merged_fields["resonance:merge:combined"]["merge_parent_ids"],
                    parent_ids,
                )
                self.assertEqual(
                    [
                        merged_fields[field_id]["status"]
                        for field_id in parent_ids
                    ],
                    ["resting", "resting"],
                )
                active_program = director.store.program("resonance")
                branch_candidates = director._branch_obligations([active_program])
                self.assertTrue(
                    any(
                        candidate[1]["field_id"] == "resonance:merge:combined"
                        for candidate in branch_candidates.values()
                    ),
                    (branch_candidates, merged_fields),
                )
                selected = director._field_select([active_program])
                self.assertIsNotNone(selected, selected)
                self.assertEqual(
                    selected["_selected_working_field"]["field_id"],
                    "resonance:merge:combined",
                )
                circulation_row = next(
                    row for row in memory.owner.state.computers
                    if row.computer_id == "field-qwen:embodied-circulation"
                )
                resident = circulation_row._value("task")
                last_feedback = resident["circulation"]["spectrum"]["last_feedback"]
                appraisal_ref = last_feedback["appraisal_ref"]
                before_item = next(
                    item for item in memory.owner.inspect_embodied_field()["exchange_meaning"]["items"]
                    if item["last_appraisal_ref"] == appraisal_ref
                )
                self.assertEqual(
                    before_item["exchange"]["measurement_timing"], "before-feedback",
                )
                next_pass = resident["circulation"]["continuation"]["pass"] + 1
                memory.owner.operate_computer(
                    "test:embodied:after-feedback",
                    computer_id="field-qwen:embodied-circulation",
                    action="submit",
                    arguments={
                        "kernel": REGIONAL_KERNEL_NAME,
                        "state": resume_regional_state(resident, ticks=next_pass),
                        "arguments": {"operation": "circulate", "ticks": next_pass},
                        "steps": 4096,
                    },
                    expected_state_sha256=memory.owner.state.state_sha256,
                )
                after_item = next(
                    item for item in memory.owner.inspect_embodied_field()["exchange_meaning"]["items"]
                    if item["last_appraisal_ref"] == appraisal_ref
                )
                self.assertEqual(
                    after_item["exchange"]["measurement_timing"], "after-feedback",
                )
                self.assertNotEqual(
                    after_item["exchange"]["owner_reported_last_exchange_sha256"],
                    before_item["exchange"]["owner_reported_last_exchange_sha256"],
                )
            finally:
                memory.close()

    def test_recover_committed_cycle_admits_missing_affect_from_frozen_question(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8"
            )
            memory = CassiFieldWorkMemory(root / "field")
            organism = ResearchOrganism(
                root / "organism",
                workspace=Path(__file__).resolve().parents[2],
                member_ids=("member-a",),
                root_owner=memory.owner,
                root_lock=threading.RLock(),
            )
            organism.initialize()
            memory.ensure_embodied_circulation()
            director, _, _ = self.make_director(
                root / "runtime", source, brain=ResearchBrain(), memory=memory,
            )
            director.organism = organism
            try:
                self.create_program(director, cycle_limit=4)
                original_admission = director._admit_affect_outcome

                def fail_affect_admission(*args: Any, **kwargs: Any) -> None:
                    raise RuntimeError("simulated interruption before affect admission")

                director._admit_affect_outcome = fail_affect_admission
                committed = director.run_one(program_id="resonance")
                self.assertEqual(committed["cycles_completed"], 1)
                operation_id = "entity:research-cycle:resonance:00000001"
                saved = director.store.operation(operation_id)
                self.assertEqual(saved["status"], "committed")
                self.assertIsNone(saved["affect_outcome"])
                frozen_question = saved["question_at_start"]
                self.assertNotEqual(
                    director._active_question(director.store.program("resonance")),
                    frozen_question,
                )

                director._admit_affect_outcome = original_admission
                director.recover()

                recovered = director.store.operation(operation_id)
                affect = recovered["affect_outcome"]
                self.assertIsInstance(
                    affect, Mapping,
                    {
                        "recent": director.store.program("resonance")["recent_operations"],
                        "kind": recovered.get("kind"),
                        "status": recovered.get("status"),
                        "synthesis": isinstance(recovered.get("synthesis"), Mapping),
                        "result": isinstance(recovered.get("result"), Mapping),
                        "faults": [
                            (row["kind"], row["payload"])
                            for row in director.store.events_after(0, program_id="resonance")
                            if "fault" in row["kind"]
                        ],
                    },
                )
                self.assertEqual(
                    director.program("resonance")["recent_operations"][-1][
                        "affect_outcome"
                    ],
                    affect,
                )
                assessed = next(
                    row for row in memory.owner.state.computers
                    if row.computer_id == "field-qwen:work-memory"
                )._value("task")["records"][affect["outcome_ref"]["id"]][-1]
                self.assertIn(
                    assessed["payload"]["source_revision_id"],
                    assessed["support_roots"],
                )
                self.assertTrue(affect["entity_exchange_feedback"])
                source_revision = assessed["payload"]["source_revision_id"]
                self.assertTrue(source_revision)
                director.recover()
                self.assertEqual(
                    director.store.operation(operation_id)["affect_outcome"],
                    affect,
                )
                successful = director.run_one(program_id="resonance")
                successful_operation_id = (
                    "entity:research-cycle:resonance:00000002"
                )
                successful_operation = director.store.operation(
                    successful_operation_id
                )
                self.assertIsInstance(
                    successful_operation["affect_outcome"], Mapping
                )
                attempted: list[str] = []

                def reject_replay(*args: Any, **kwargs: Any) -> None:
                    attempted.append("replayed")
                    raise RuntimeError("successful receipt must not be re-admitted")

                director._admit_affect_outcome = reject_replay
                director.recover()
                self.assertEqual(attempted, [])
                self.assertEqual(successful["cycles_completed"], 2)
            finally:
                memory.close()

    def test_field_agenda_reconciles_nonrunnable_program_obligations(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = CassiFieldWorkMemory(root / "field")
            director, _brain, _memory = self.make_director(
                root / "runtime", source, memory=memory
            )
            try:
                self.create_program(director, cycle_limit=3)
                for program_id, status in (
                    ("blocked-research", "blocked"),
                    ("paused-research", "paused"),
                ):
                    program = director.create_program(
                        request_id=f"create-{program_id}",
                        program_id=program_id,
                        project_id="physics",
                        title=f"{status.title()} research",
                        mission=f"Resume {status} research when actionable.",
                        initial_question="What should happen next?",
                        observed_at="2026-09-19T00:00:00Z",
                        cycle_limit=3,
                        allowed_tools=["read_file"],
                    )
                    director.store.save_program({**program, "status": status})

                semantic_calls: list[Mapping[str, Any]] = []
                original_semantic = memory.semantic

                def recording_semantic(
                    request: Mapping[str, Any],
                    *,
                    operation_label: str | None = None,
                ) -> Mapping[str, Any]:
                    semantic_calls.append(dict(request))
                    return original_semantic(
                        request, operation_label=operation_label
                    )

                memory.semantic = recording_semantic
                selected = director._field_select([director.store.program("resonance")])
                self.assertEqual(selected["program_id"], "resonance")
                agenda_request = next(
                    call for call in reversed(semantic_calls)
                    if call.get("operation") == "autonomous-agenda"
                )
                self.assertEqual(
                    agenda_request["eligible_work_order"],
                    ["entity:research-program-obligation:resonance"],
                )
                self.assertEqual(
                    [
                        event for event in director.events_after(0)
                        if event["kind"] == "field-agenda-fault"
                    ],
                    [],
                )
                for program_id in ("blocked-research", "paused-research"):
                    reconciled = [
                        call for call in semantic_calls
                        if call.get("operation") == "register"
                        and call.get("record_id")
                        == f"entity:research-program-obligation:{program_id}"
                    ]
                    self.assertEqual(reconciled[-1]["status"], "resolved")
            finally:
                memory.close()

    def test_field_agenda_runs_best_live_branch_and_rest_wake_changes_eligibility(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text(
                "Measured resonance: 17 Hz\n", encoding="utf-8"
            )
            memory = CassiFieldWorkMemory(root / "field")
            organism = ResearchOrganism(
                root / "organism",
                workspace=Path(__file__).resolve().parents[2],
                member_ids=("member-a",),
                root_owner=memory.owner,
                root_lock=threading.RLock(),
            )
            organism.initialize()
            brain = ResearchBrain(fail_first_synthesis=True)
            director, _, _ = self.make_director(
                root / "runtime", source, brain=brain, memory=memory
            )
            director.organism = organism
            try:
                self.create_program(director, cycle_limit=3)
                parent = director._working_field("resonance")
                self.assertIsNotNone(parent)
                for name, value, uncertainty, cost in (
                    ("instrument", 0.8, 0.1, 0.1),
                    ("distinction", 1.0, 0.0, 0.0),
                ):
                    opened = organism.advance_working_field(
                        f"candidate:{name}",
                        field_id=f"resonance:branch:{name}",
                        action="branch",
                        update={
                            "parent_field_id": "resonance",
                            "parent_ref": parent["program_ref"],
                            "question": f"Which observation tests {name}?",
                            "branch_purpose": f"Resolve {name} with an authorized source read",
                            "expected_contribution": {
                                "kind": name,
                                "value": value,
                                "uncertainty": uncertainty,
                                "cost": cost,
                            },
                        },
                    )["field"]
                    self.assertEqual(opened["parent_ref"]["id"], parent["program_ref"]["id"])
                    parent = director._working_field("resonance")
                with self.assertRaisesRegex(RuntimeError, "temporary model outage"):
                    director.run_one()
                pending = director.store.operation("entity:research-cycle:resonance:00000001")
                self.assertEqual(pending["status"], "executed")
                self.assertEqual(pending["working_field_id"], "resonance:branch:distinction")
                director.recover()
                self.assertEqual(director.program("resonance")["cycles_completed"], 1)
                operation = director.store.operation("entity:research-cycle:resonance:00000001")
                self.assertEqual(operation["plan"]["action"], "read_file")
                self.assertEqual(operation["working_field_id"], "resonance:branch:distinction")
                self.assertEqual(
                    operation["field_selection"]["prospective_contribution"]["net_priority"],
                    2.0,
                )
                self.assertEqual(
                    sum("AUTONOMOUS RESEARCH ACTION" in call for call in brain.calls), 1
                )
                self.assertEqual(operation["working_field_status"], "contributed")
                fields = {
                    row["field_id"]: row
                    for row in organism.inspect_working_fields()["items"]
                }
                self.assertEqual(
                    fields["resonance:branch:distinction"]["contribution"]["value"]["operation_id"],
                    operation["operation_id"],
                )
                self.assertIsNone(fields["resonance:branch:instrument"]["contribution"])
                self.assertIn(
                    fields["resonance:branch:distinction"]["program_ref"],
                    fields["resonance"]["child_refs"],
                )
                chosen = fields["resonance:branch:distinction"]
                rested = organism.advance_working_field(
                    "candidate:rest", field_id=chosen["field_id"], action="rest",
                    update={
                        "expected_ref": chosen["program_ref"],
                        "reason": "awaiting-relevant-observation",
                        "reopen_condition": {
                            "clauses": [{
                                "field": "event_kind",
                                "operator": "equals",
                                "value": "research-result",
                            }]
                        },
                    },
                )["field"]
                self.assertFalse(rested["eligible"])
                alternate = director._field_select([director.store.program("resonance")])
                self.assertEqual(
                    alternate["_selected_working_field"]["field_id"],
                    "resonance:branch:instrument",
                )
                with organism._open_residencies(include_members=False) as (residency, _):
                    trigger = residency._register(
                        "candidate:wake:register",
                        "candidate:wake:event",
                        "Event",
                        {"kind": "research-result"},
                    )["record"]
                woken = organism.advance_working_field(
                    "candidate:wake", field_id=chosen["field_id"], action="reopen",
                    update={
                        "expected_ref": rested["program_ref"],
                        "trigger_ref": trigger,
                        "context": {"event_kind": "research-result"},
                    },
                )["field"]
                self.assertTrue(woken["eligible"])
                self.assertEqual(woken["field_id"], chosen["field_id"])
                resumed = director._field_select([director.store.program("resonance")])
                self.assertEqual(
                    resumed["_selected_working_field"]["field_id"],
                    "resonance:branch:distinction",
                )
                original_inspect = organism.inspect_working_fields

                def inspect_without_branch(
                    *, limit: int = 128
                ) -> Mapping[str, Any]:
                    snapshot = original_inspect(limit=limit)
                    items = [
                        row
                        for row in snapshot["items"]
                        if row["field_id"] != "resonance:branch:distinction"
                    ]
                    return {**snapshot, "items": items}

                organism.inspect_working_fields = inspect_without_branch
                registrations: list[Mapping[str, Any]] = []
                original_semantic = memory.semantic

                def recording_semantic(
                    request: Mapping[str, Any],
                    *,
                    operation_label: str | None = None,
                ) -> Mapping[str, Any]:
                    registrations.append(dict(request))
                    return original_semantic(
                        request, operation_label=operation_label
                    )

                memory.semantic = recording_semantic
                nonstale = director._field_select(
                    [director.store.program("resonance")]
                )
                self.assertNotEqual(
                    nonstale["_selected_working_field"]["field_id"],
                    "resonance:branch:distinction",
                )
                stale_identity = (
                    "entity:research-program-obligation:field:"
                    + hashlib.sha256(
                        b"resonance:resonance:branch:distinction"
                    ).hexdigest()[:32]
                )
                self.assertEqual(
                    [
                        call["status"] for call in registrations
                        if call.get("operation") == "register"
                        and call.get("record_id") == stale_identity
                    ][-1],
                    "resolved",
                )
                active_obligations = {
                    row["id"]: row["status"]
                    for row in memory.inspect_current_obligations(
                        prefix="entity:research-program-obligation:field:"
                    )
                }
                instrument_identity = (
                    "entity:research-program-obligation:field:"
                    + hashlib.sha256(
                        b"resonance:resonance:branch:instrument"
                    ).hexdigest()[:32]
                )
                self.assertEqual(active_obligations[stale_identity], "resolved")
                self.assertEqual(active_obligations[instrument_identity], "active")
                self.assertEqual(
                    [
                        event for event in director.events_after(0)
                        if event["kind"] == "field-agenda-fault"
                    ],
                    [],
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
            original_performance = operation["performance"]

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
            self.assertEqual(
                program["methods"][-1]["observed_consequence"]["method_outcome"]["measured_elapsed_ns"]["action_elapsed_ns"],
                original_performance["action_elapsed_ns"],
            )

    def test_recovery_leaves_failed_synthesis_to_its_own_program_cycle(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = FakeFieldMemory()
            arguments = {"path": "notes/result.txt", "content": "observed\n", "media_type": "text/plain"}
            first, _, _ = self.make_director(
                root / "runtime", source,
                brain=ResearchBrain(action="write_artifact", arguments=arguments, fail_first_synthesis=True),
                memory=memory,
                default_tools=("write_artifact",),
            )
            self.create_program(first, tools=["write_artifact"])
            with self.assertRaises(ResearchBrainUnavailable):
                first.run_one()
            operation_id = "entity:research-cycle:resonance:00000001"

            brain = ResearchBrain(action="write_artifact", arguments=arguments, fail_first_synthesis=True)
            recovered, _, _ = self.make_director(
                root / "runtime", source, brain=brain, memory=memory,
                default_tools=("write_artifact",),
            )

            def synthesis_attempts() -> int:
                return sum("AUTONOMOUS RESEARCH SYNTHESIS" in prompt for prompt in brain.calls)

            recovered.recover()
            self.assertEqual(recovered.store.operation(operation_id)["status"], "executed")
            self.assertEqual(synthesis_attempts(), 1)
            events = recovered.events_after(0, program_id="resonance")
            self.assertEqual(sum(event["kind"] == "operation-deferred" for event in events), 2)
            self.assertEqual(sum(event["kind"] == "operation-recovered" for event in events), 0)

            # Later cycles in this process retry the operation once, through
            # its own program; recovery does not repeat the brain call.
            recovered.recover()
            self.assertEqual(synthesis_attempts(), 1)
            brain.fail_first_synthesis = True
            with self.assertRaises(ResearchBrainUnavailable):
                recovered.run_one(program_id="resonance")
            self.assertEqual(synthesis_attempts(), 2)
            completed = recovered.run_one(program_id="resonance")
            self.assertEqual(synthesis_attempts(), 3)
            self.assertEqual(completed["cycles_completed"], 1)
            self.assertEqual(recovered.store.operation(operation_id)["status"], "committed")
            self.assertEqual(
                (recovered.store.workspace("resonance") / "notes" / "result.txt").read_text(encoding="utf-8"),
                "observed\n",
            )

    def test_paused_execution_waits_for_resume_and_cancel_discards_pending_settlement(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            memory = FakeFieldMemory()
            first, _, _ = self.make_director(
                root / "runtime", source,
                brain=ResearchBrain(
                    action="write_artifact",
                    arguments={"path": "notes/result.txt", "content": "observed\n", "media_type": "text/plain"},
                    fail_first_synthesis=True,
                ),
                memory=memory,
                default_tools=("write_artifact",),
            )
            self.create_program(first, tools=["write_artifact"])
            with self.assertRaises(ResearchBrainUnavailable):
                first.run_one()
            operation_id = "entity:research-cycle:resonance:00000001"
            first.control_program(
                request_id="pause-executed",
                program_id="resonance",
                action="pause",
                observed_at="2026-09-23T00:01:00Z",
            )
            recovered, _, _ = self.make_director(
                root / "runtime", source,
                brain=ResearchBrain(action="write_artifact"),
                memory=memory,
                default_tools=("write_artifact",),
            )
            recovered.recover()
            self.assertEqual(recovered.store.operation(operation_id)["status"], "executed")
            self.assertEqual(recovered.program("resonance")["cycles_completed"], 0)
            recovered.control_program(
                request_id="cancel-paused",
                program_id="resonance",
                action="cancel",
                observed_at="2026-09-23T00:02:00Z",
            )
            recovered.recover()
            self.assertEqual(recovered.program("resonance")["status"], "canceled")
            self.assertEqual(recovered.program("resonance")["cycles_completed"], 0)
            self.assertEqual(recovered.store.operation(operation_id)["status"], "failed")
            self.assertEqual(
                (recovered.store.workspace("resonance") / "notes" / "result.txt").read_text(encoding="utf-8"),
                "observed\n",
            )

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
                development.get("schema", development),
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
            with self.assertRaises(ResearchSynthesisDegenerated):
                director.run_one()
            program = director.program("resonance")
            self.assertEqual(program["report"], written)
            self.assertEqual(program["cycles_completed"], 1)
            self.assertEqual(len(program["claims"]), 1)
            self.assertEqual(
                director.store.operation("entity:research-cycle:resonance:00000002")["status"],
                "executed",
            )

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
            server = EntityHTTPServer(("127.0.0.1", 0), entity)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
            headers = {"content-type": "application/json"}
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
            server = EntityHTTPServer(("127.0.0.1", 0), entity)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
            headers = {"content-type": "application/json"}
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
            server = EntityHTTPServer(("127.0.0.1", 0), entity)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=20)
            headers = {"content-type": "application/json"}
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
            server = EntityHTTPServer(("127.0.0.1", 0), entity)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_address[1], timeout=20
            )
            headers = {"content-type": "application/json"}

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

    def test_standing_program_refuses_model_completion_and_keeps_polling(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            brain = ResearchBrain(program_status="completed")
            director, _, _ = self.make_director(root / "runtime", source, brain=brain)
            director.create_program(
                request_id="create-standing",
                program_id="standing",
                project_id="physics",
                title="Derive BTC paper math",
                mission="Keep the paper mathematics of BTC trading open.",
                initial_question="What is actually observed?",
                observed_at="2026-09-22T00:00:00Z",
                standing=True,
                allowed_tools=["read_file"],
            )
            advanced = director.run_one(program_id="standing")
            self.assertEqual(advanced["status"], "active")
            self.assertTrue(advanced["standing"])
            self.assertEqual(advanced["cycles_completed"], 1)
            self.assertEqual(
                advanced["frontier"][-1]["question"],
                "Which mechanism predicts the observed 17 Hz resonance?",
            )
            self.assertEqual(advanced["frontier"][-1]["state"], "active")
            refusal = advanced["messages"][-1]["content"]
            self.assertIn("model completion was refused", refusal)
            kinds = [
                event["kind"]
                for event in director.events_after(0, program_id="standing")
            ]
            self.assertIn("program-advanced", kinds)
            advanced_event = next(
                event
                for event in director.events_after(0, program_id="standing")
                if event["kind"] == "program-advanced"
            )
            self.assertEqual(advanced_event["payload"]["status"], "active")

            waiting = ResearchBrain(action="wait")
            director.brain = waiting
            polled = director.run_one(program_id="standing")
            self.assertEqual(polled["status"], "active")
            self.assertTrue(polled["standing"])

    def test_standing_program_completes_when_the_caller_finalizes(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            director, _, _ = self.make_director(root / "runtime", source)
            director.create_program(
                request_id="create-standing",
                program_id="standing",
                project_id="physics",
                title="Derive BTC paper math",
                mission="Keep the paper mathematics of BTC trading open.",
                initial_question="What is actually observed?",
                observed_at="2026-09-22T00:00:00Z",
                standing=True,
            )
            completed = director.control_program(
                request_id="complete-standing",
                program_id="standing",
                action="complete",
                observed_at="2026-09-22T00:01:00Z",
            )
            self.assertEqual(completed["status"], "completed")
            self.assertTrue(completed["standing"])
            canceled = director.control_program(
                request_id="cancel-standing",
                program_id="standing",
                action="cancel",
                observed_at="2026-09-22T00:02:00Z",
            )
            self.assertEqual(canceled["status"], "canceled")
            with self.assertRaises(ProgramConflict):
                director.control_program(
                    request_id="continue-canceled",
                    program_id="standing",
                    action="continue",
                    observed_at="2026-09-22T00:03:00Z",
                )

    def test_continue_reopens_completed_program_under_the_same_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            director, _, _ = self.make_director(root / "runtime", source)
            self.create_program(director, tools=["read_file"])
            advanced = director.run_one()
            self.assertEqual(advanced["status"], "paused")
            with self.assertRaises(ProgramConflict):
                director.control_program(
                    request_id="continue-paused",
                    program_id="resonance",
                    action="continue",
                    observed_at="2026-09-22T00:00:30Z",
                )
            completed = director.control_program(
                request_id="complete-resonance",
                program_id="resonance",
                action="complete",
                observed_at="2026-09-22T00:01:00Z",
            )
            self.assertEqual(completed["status"], "completed")

            with self.assertRaises(ProgramConflict):
                director.control_program(
                    request_id="resume-completed",
                    program_id="resonance",
                    action="resume",
                    observed_at="2026-09-22T00:02:00Z",
                )
            resumed = director.control_program(
                request_id="continue-completed",
                program_id="resonance",
                action="continue",
                observed_at="2026-09-22T00:03:00Z",
                message="Look at the next candle.",
            )
            self.assertEqual(resumed["program_id"], "resonance")
            self.assertEqual(resumed["status"], "active")
            self.assertTrue(resumed["standing"])
            self.assertEqual(resumed["cycles_completed"], 1)
            self.assertEqual(resumed["claims"], advanced["claims"])
            self.assertEqual(
                resumed["frontier"][-1]["question"], "Look at the next candle."
            )
            self.assertEqual(resumed["frontier"][-1]["required_refs"], [])
            self.assertEqual(
                resumed["current_question_id"], resumed["frontier"][-1]["question_id"]
            )

            replay = director.control_program(
                request_id="continue-completed",
                program_id="resonance",
                action="continue",
                observed_at="2026-09-22T00:03:00Z",
                message="Look at the next candle.",
            )
            self.assertEqual(replay["status"], resumed["status"])
            self.assertEqual(replay["frontier"], resumed["frontier"])
            with self.assertRaises(ProgramConflict):
                director.control_program(
                    request_id="continue-completed",
                    program_id="resonance",
                    action="continue",
                    observed_at="2026-09-22T00:03:00Z",
                    message="A different prompt.",
                )

            # A regenerated question from the last committed cycle reopens the
            # plan again: the mission can execute its next bar in place.
            bar = director.run_one(program_id="resonance")
            self.assertEqual(bar["cycles_completed"], 2)
            self.assertEqual(bar["frontier"][-1]["state"], "active")

    def test_continue_from_last_committed_question_when_no_message_given(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            (source / "evidence.txt").write_text("Measured resonance: 17 Hz\n", encoding="utf-8")
            director, _, _ = self.make_director(root / "runtime", source)
            self.create_program(director, tools=["read_file"])
            advanced = director.run_one()
            director.control_program(
                request_id="complete-resonance",
                program_id="resonance",
                action="complete",
                observed_at="2026-09-22T00:01:00Z",
            )
            reopened = director.control_program(
                request_id="continue-completed",
                program_id="resonance",
                action="continue",
                observed_at="2026-09-22T00:03:00Z",
            )
            self.assertEqual(
                reopened["frontier"][-1]["question"],
                advanced["frontier"][-1]["question"],
            )
            self.assertEqual(reopened["status"], "active")

    def test_http_accepts_the_optional_standing_flag(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
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
            server = EntityHTTPServer(("127.0.0.1", 0), entity)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_address[1], timeout=20
            )
            headers = {"content-type": "application/json"}

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
                    "request_id": "create-standing",
                    "program_id": "standing-btc",
                    "project_id": "research",
                    "title": "Derive BTC paper math",
                    "mission": "Keep the paper mathematics of BTC trading open.",
                    "initial_question": "What is the next paper question?",
                    "observed_at": "2026-09-24T00:00:00Z",
                    "standing": True,
                })
                self.assertEqual(status, 202, created)
                status, view = exchange("GET", "/v1/programs/standing-btc")
                self.assertEqual(status, 200, view)
                self.assertTrue(view["standing"])
                self.assertEqual(view["status"], "active")
                status, completion = exchange(
                    "POST", "/v1/programs/standing-btc/control", {
                        "request_id": "complete-standing-btc",
                        "action": "complete",
                        "observed_at": "2026-09-24T00:01:00Z",
                    }
                )
                self.assertEqual(status, 202, completion)
                self.assertEqual(completion["status"], "completed")
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                entity.close()

def last_question_of(program: Mapping[str, Any]) -> str:
    return program["frontier"][-1]["question"]

if __name__ == "__main__":
    unittest.main()
