"""Mission protocol, agent drivers, receipts, resume, night shift, portfolio.

The course is the only place that knows how a mission is delivered and scored.
It renders one mission document per world, hands it to an agent, takes the
agent's evidence, judges every station independently, and writes a receipt
whose identity is the world plus the submitted evidence -- never the clock.

Two agent kinds are supported and they answer exactly the same document:

``ScriptedAgent``
    an in-process callable; the canary controls live here.
``EntityAgent``
    a live field-brain entity driven through its real HTTP API: one research
    program is created for the mission, the entity's own report is read back,
    and the mission evidence is lifted out of it.

Timing is settlement-based: a station's duration is measured around the
agent's answer, and every receipt keeps the clock in a sibling section that is
excluded from the content digest.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from laboratory import stations as stations_module
from laboratory.stations import (
    COURSE_SCHEMA,
    MISSION_EVIDENCE_SCHEMA,
    LaboratoryError,
    Station,
    Fixture,
    build_fixture,
    default_fixture,
    extract_evidence,
    mission_document,
    physics_stations,
)

DIGEST_ALGORITHM = "sha256"
#: Receipt keys excluded from the content digest: the digest itself and every
#: value that moves with the clock or with how the run was hosted.
DIGEST_STRIP: tuple[str, ...] = ("digest", "clock", "resumed_from", "evidence_bytes")

PROGRAM_EVIDENCE_POLL_SECONDS = 5.0
WORKSPACE_EVIDENCE_MAX_BYTES = 262_144
GUIDANCE_HEADER = "Shifting Laboratory — mission brief follows"


# --------------------------------------------------------------------------
# evidence plumbing


def harvest_text(value: Any, *, limit: int = 400_000) -> str:
    """Concatenate every string inside a JSON document, in document order."""

    pieces: list[str] = []
    total = 0

    def walk(node: Any) -> None:
        nonlocal total
        if total >= limit:
            return
        if isinstance(node, str):
            pieces.append(node)
            total += len(node)
        elif isinstance(node, Mapping):
            for key, item in node.items():
                if isinstance(key, str):
                    pieces.append(key)
                walk(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(value)
    return "\n".join(pieces)


def mission_evidence(text: str) -> dict[str, Any] | None:
    document = extract_evidence(text, MISSION_EVIDENCE_SCHEMA)
    if document is None:
        return None
    if not isinstance(document.get("stations"), Mapping):
        return None
    return document


def station_evidence(
    document: Mapping[str, Any], station: Station | Mapping[str, Any]
) -> Mapping[str, Any] | None:
    bundle = document.get("stations")
    if not isinstance(bundle, Mapping):
        return None
    station_id = (
        station.station_id if isinstance(station, Station) else station.get("station_id")
    )
    if not isinstance(station_id, str):
        return None
    evidence = bundle.get(station_id)
    return evidence if isinstance(evidence, Mapping) else None


def _covered_stations(document: Mapping[str, Any]) -> set[str]:
    bundle = document.get("stations")
    if not isinstance(bundle, Mapping):
        return set()
    return {str(key) for key in bundle}


def _covers(document: Mapping[str, Any], required: set[str]) -> bool:
    return required <= _covered_stations(document)


def _fullest(
    current: Mapping[str, Any] | None, candidate: Mapping[str, Any]
) -> dict[str, Any]:
    if current is None:
        return dict(candidate)
    if len(_covered_stations(candidate)) >= len(_covered_stations(current)):
        return dict(candidate)
    return dict(current)


# --------------------------------------------------------------------------
# submitted programs (station 3 runs the agent's source itself)


def run_submitted_program(
    source: str,
    inputs: Mapping[str, Any],
    *,
    timeout: float = 30.0,
) -> tuple[str, str | None]:
    """Run one submitted program on one input; return (stdout, failure)."""

    with tempfile.TemporaryDirectory(prefix="cassi-lab-program-") as work:
        path = Path(work) / "submitted.py"
        path.write_text(source, encoding="utf-8")
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH", "PATHEXT"}
        }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(path)],
                input=json.dumps(dict(inputs)),
                capture_output=True,
                text=True,
                cwd=work,
                timeout=timeout,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "", f"program exceeded {timeout:.0f} s"
        except OSError as error:
            return "", f"program could not run: {error}"
        if completed.returncode != 0:
            return completed.stdout, f"exit {completed.returncode}: {completed.stderr[-800:]}"
        return completed.stdout, None


# --------------------------------------------------------------------------
# agents


class Agent(Protocol):
    """Anything that can answer a mission."""

    kind: str

    def start(self, mission: Mapping[str, Any]) -> None: ...

    def evidence(self, station_ids: Sequence[str], *, deadline_s: float) -> dict[str, Mapping[str, Any]]: ...

    def transcript(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


@dataclass
class ScriptedAgent:
    """In-process answerer: the canary controls and the fast runner."""

    answerer: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    kind: str = "scripted"
    mission: Mapping[str, Any] | None = None
    answered: dict[str, Any] = field(default_factory=dict)

    def start(self, mission: Mapping[str, Any]) -> None:
        self.mission = mission
        self.answered = {}

    def evidence(
        self, station_ids: Sequence[str], *, deadline_s: float = 0.0
    ) -> dict[str, Mapping[str, Any]]:
        if self.mission is None:
            raise LaboratoryError("mission not started")
        catalog = {item["station_id"]: item for item in self.mission["stations"]}
        produced: dict[str, Mapping[str, Any]] = {}
        for station_id in station_ids:
            if station_id not in catalog:
                raise LaboratoryError(f"mission has no station {station_id!r}")
            brief = catalog[station_id]
            if station_id not in self.answered:
                self.answered[station_id] = self.answerer(dict(brief))
            produced[station_id] = self.answered[station_id]
        return produced

    def transcript(self) -> dict[str, Any]:
        return {"kind": self.kind, "stations_answered": sorted(self.answered)}

    def close(self) -> None:
        return None


def mission_deliverable(mission: Mapping[str, Any]) -> dict[str, Any] | None:
    """The mission's declared document as the program's standing obligation.

    The mission already declares what an answer is; handing the same contract
    to the program is what makes delivery part of the entity's own agenda
    instead of a paragraph it read once at the start of the shift.
    """

    declared = mission.get("deliverable")
    if not isinstance(declared, Mapping):
        return None
    sections = declared.get("station_keys")
    if not isinstance(sections, Mapping) or not sections:
        return None
    artifact = declared.get("artifact")
    contract: dict[str, Any] = {
        "artifact": artifact if isinstance(artifact, str) and artifact else "answer.json",
        "sections_key": str(declared.get("sections_key") or "stations"),
        "sections": [str(key) for key in sections],
        "document_schema": str(declared.get("schema") or MISSION_EVIDENCE_SCHEMA),
    }
    identity_value = declared.get("fixture_id") or mission.get("fixture_id")
    if isinstance(identity_value, str) and identity_value:
        contract["identity_key"] = "fixture_id"
        contract["identity_value"] = identity_value
    return contract


@dataclass
class EntityAgent:
    """A live field-brain entity answering one mission in its own program.

    The agent creates the program, optionally guides it, waits for a report
    that carries the requested evidence document, and reads the program back
    for the transcript.  Nothing is written into the entity's live home unless
    the caller points it at one.
    """

    client: Any  # cassi_program_benchmark_client.ProgramBenchmarkClient
    project_id: str
    allowed_roots: Sequence[str]
    allowed_tools: Sequence[str] = ("write_artifact",)
    program_id: str | None = None
    deadline_s: float = 900.0
    poll_s: float = PROGRAM_EVIDENCE_POLL_SECONDS
    guidance: str = ""
    kind: str = "entity"
    workspace_root: str | Path | None = None
    mission: Mapping[str, Any] | None = None
    program: dict[str, Any] | None = None
    events_seen: int = 0
    evidence_document: dict[str, Any] | None = None
    coverage_events: list[dict[str, Any]] = field(default_factory=list)
    waited_seconds: float = 0.0
    stages: list[dict[str, Any]] = field(default_factory=list)
    _closed: bool = False

    # -------------------------------------------------------------- lifecycle
    def start(self, mission: Mapping[str, Any]) -> None:
        self.mission = mission
        fixture_id = str(mission.get("fixture_id", ""))
        if self.guidance:
            question = self.guidance
        else:
            question = render_mission_question(mission)
        document = {
            "request_id": f"lab-mission-{mission['mission_id']}",
            "program_id": self.program_id or f"lab-{mission['mission_id']}",
            "project_id": self.project_id,
            "title": str(mission.get("title", mission["mission_id"])),
            "mission": render_mission_statement(mission),
            "initial_question": question,
            "allowed_roots": list(self.allowed_roots),
            "allowed_tools": list(self.allowed_tools),
        }
        deliverable = mission_deliverable(mission)
        if deliverable is not None:
            document["deliverable"] = deliverable
        sample = self.client.create_program(**document)
        sample.require_ok()
        self.program_id = document["program_id"]
        self._record_stage("create_program", sample)

    def evidence(
        self, station_ids: Sequence[str], *, deadline_s: float | None = None
    ) -> dict[str, Mapping[str, Any]]:
        if self.program_id is None:
            raise LaboratoryError("program not created")
        budget = float(self.deadline_s if deadline_s is None else deadline_s)
        if self.evidence_document is None:
            waited_at = time.perf_counter()
            try:
                self.evidence_document = self._await_mission_evidence(
                    budget, required=tuple(station_ids)
                )
            finally:
                self.waited_seconds += time.perf_counter() - waited_at
        if self.evidence_document is None:
            return {}
        produced: dict[str, Mapping[str, Any]] = {}
        for station_id in station_ids:
            station = next(
                (
                    item
                    for item in (self.mission or {}).get("stations", [])
                    if item["station_id"] == station_id
                ),
                None,
            )
            if station is None:
                continue
            found = station_evidence(self.evidence_document, station)
            if found is not None:
                produced[station_id] = found
        return produced

    def _await_mission_evidence(
        self, budget: float, *, required: Sequence[str]
    ) -> dict[str, Any] | None:
        """Wait for the entity's answer, complete or (at the deadline) partial.

        A draft that covers only some stations is not an answer yet: the
        entity is still working, so the wait continues and the fullest draft
        is kept in case the deadline arrives first.
        """

        deadline = time.monotonic() + budget
        wanted = set(required)
        partial: dict[str, Any] | None = None
        while True:
            sample = self.client.get_program(self.program_id)
            self._record_stage("get_program", sample)
            if sample.ok:
                payload = sample.payload
                self.program = payload if isinstance(payload, dict) else None
                found = mission_evidence(harvest_text(payload))
                if found is not None:
                    partial = _fullest(partial, found)
                    if _covers(found, wanted):
                        return found
            found = self._workspace_mission_evidence()
            if found is not None:
                partial = _fullest(partial, found)
                if _covers(found, wanted):
                    return found
            if time.monotonic() >= deadline:
                return partial
            events = self.client.program_events(self.program_id, after=self.events_seen)
            if events.ok:
                self._record_coverage(events)
                cursor = events.next_cursor
                if cursor is not None:
                    self.events_seen = int(cursor)
            time.sleep(max(1.0, self.poll_s))

    def _record_coverage(self, events: Any) -> None:
        """Keep the program's own record of which sections have been delivered."""

        for frame in events.events:
            data = frame.get("data") if isinstance(frame, Mapping) else None
            if not isinstance(data, Mapping) or data.get("kind") != "deliverable-advanced":
                continue
            payload = data.get("payload")
            payload = payload if isinstance(payload, Mapping) else {}
            self.coverage_events.append(
                {
                    "sequence": data.get("sequence"),
                    "covered": list(payload.get("covered", [])),
                    "missing": list(payload.get("missing", [])),
                    "source": payload.get("source"),
                }
            )

    def _workspace_mission_evidence(self) -> dict[str, Any] | None:
        """Read the document the entity wrote into its own program workspace.

        The entity's artifacts are the natural home for a long answer, so a
        written file carrying the requested document counts as delivery.
        """

        if self.workspace_root is None:
            return None
        root = Path(self.workspace_root)
        if not root.is_dir():
            return None
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.stat().st_size > WORKSPACE_EVIDENCE_MAX_BYTES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            found = mission_evidence(text)
            if found is not None:
                return found
        return None

    def throughput(self) -> dict[str, Any]:
        """What the shift bought: cycles, seconds per cycle, and delivery.

        A shift is sized from measurement, so the receipt carries the rate the
        mind actually worked at and how far its declared document had come when
        the deadline arrived -- the two numbers a next shift is planned from.
        """

        program = self.program if isinstance(self.program, Mapping) else {}
        cycles = program.get("cycles_completed")
        block: dict[str, Any] = {
            "schema": "cassi.laboratory.shift-throughput.v1",
            "cycles_completed": cycles,
            "generation": program.get("generation"),
            "status": program.get("status"),
            "deliverable": program.get("deliverable"),
            "deliverable_state": program.get("deliverable_state"),
            "coverage": self.coverage_events,
            "agent_seconds": round(float(self.waited_seconds), 3),
        }
        if isinstance(cycles, int) and cycles > 0 and self.waited_seconds > 0:
            block["seconds_per_cycle"] = round(
                float(self.waited_seconds) / cycles, 3
            )
        return block

    def transcript(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "program_id": self.program_id,
            "program": self.program,
            "throughput": self.throughput(),
            "stages": [
                {
                    "call": item["call"],
                    "ok": item["ok"],
                    "status": item["status"],
                    "bytes": item["bytes"],
                    "response_sha256": item["response_sha256"],
                }
                for item in self.stages
            ],
        }

    def close(self) -> None:
        self._closed = True

    def _record_stage(self, call: str, sample: Any) -> None:
        self.stages.append(
            {
                "call": call,
                "ok": bool(sample.ok),
                "status": sample.status,
                "bytes": sample.response_body_bytes,
                "response_sha256": sample.response_sha256,
            }
        )


def render_mission_statement(mission: Mapping[str, Any]) -> str:
    return (
        f"{mission.get('title', mission['mission_id'])}. "
        "You are on shift in a field laboratory whose instrument reports only "
        "the two field amplitudes. Your work is judged by an independent "
        "implementation of the same declared equations. Forecast before you "
        "run anything: the score comes from runs you never see, and each "
        "station's evidence must be your own."
    )


def render_mission_question(mission: Mapping[str, Any]) -> str:
    deliverable = mission.get("deliverable", {})
    station_blocks = []
    for station in mission.get("stations", []):
        station_blocks.append(
            {
                "station_id": station["station_id"],
                "title": station.get("title"),
                "brief": station.get("brief"),
                "evidence_schema": station.get("evidence_schema"),
            }
        )
    document = {
        "mission": mission.get("mission_id"),
        "fixture_id": mission.get("fixture_id"),
        "deliverable": deliverable,
        "stations": station_blocks,
    }
    return (
        "Complete every station below and record the whole answer as one JSON "
        "object whose keys are schema, fixture_id and stations (station id -> "
        "evidence), exactly in the shape the deliverable section declares. "
        "The world's identity must match; an answer to a different world is "
        "not an answer. Deliver it twice: keep the growing document in your "
        "program report fenced as ```json, and rewrite an identical copy into "
        "your program workspace as answer.json with write_artifact whenever "
        "you add or correct a station. The file is read directly, so a station "
        "you have already written down cannot be lost by a later summary.\n\n"
        "Work one station at a time. For each station, derive its evidence "
        "object with \"schema\" first, write the programs it needs with "
        "write_artifact, run them with run_existing_python, and append the "
        "finished evidence object to both copies. "
        "Delivery budgets: your program report field holds up to 8000 "
        "characters; give each station's evidence at most about 1200 "
        "characters and keep the whole document under 7500. Every station's "
        "evidence object must carry \"schema\" set to exactly that station's "
        "listed evidence_schema value, or the judge cannot read it. Any "
        "artifact you write holds at most about 4000 characters of content, "
        "and one plan step should write one small artifact. Artifact paths are "
        "relative to your program workspace, so write \"answer.json\", never "
        "an absolute path. Quote program sources inside the evidence rather "
        "than pasting briefs, tables or observations back, and write the "
        "document itself rather than a note that it comes later.\n\n"
        + json.dumps(document, sort_keys=True)
    )


# --------------------------------------------------------------------------
# course


@dataclass
class CourseContext:
    """Everything a judge is allowed to look at."""

    fixture: Fixture
    mission: dict[str, Any]
    agent: Any = None
    client: Any = None
    program_id: str | None = None
    home: str | None = None
    workspace: str | None = None


@dataclass
class Course:
    """Runs one mission and writes one receipt."""

    fixture: Any  # Fixture (Level 1) or HiddenWorld (Level 2); both declare identity and dt
    stations: tuple[Station, ...]
    level: str = "counterflow"
    context: CourseContext | None = None
    world_block: Mapping[str, Any] | None = None
    title: str | None = None

    @classmethod
    def physics(cls, fixture: Fixture | None = None, **kwargs: Any) -> "Course":
        declared = fixture or default_fixture()
        return cls(declared, physics_stations(declared), **kwargs)

    # ---------------------------------------------------------------- running
    def mission(self) -> dict[str, Any]:
        return mission_document(
            self.fixture,
            self.stations,
            level=self.level,
            world=self.world_block,
            title=self.title,
        )

    def run(
        self,
        agent: Agent,
        *,
        receipt_path: str | os.PathLike[str] | None = None,
        resume_from: str | os.PathLike[str] | None = None,
        station_ids: Sequence[str] | None = None,
        deadline_s: float = 900.0,
    ) -> dict[str, Any]:
        mission = self.mission()
        selected = tuple(
            station
            for station in self.stations
            if station_ids is None or station.station_id in set(station_ids)
        )
        if not selected:
            raise LaboratoryError("no stations selected")
        mission = mission_document(
            self.fixture,
            selected,
            level=self.level,
            world=self.world_block,
            title=self.title,
        )

        context = self.context or CourseContext(fixture=self.fixture, mission=mission)
        context = replace(context, fixture=self.fixture, mission=mission, agent=agent)
        if isinstance(agent, EntityAgent):
            context = replace(
                context,
                client=agent.client,
                program_id=agent.program_id,
                home=agent.allowed_roots[0] if agent.allowed_roots else None,
            )

        clock: dict[str, Any] = {
            "started_at": _utc_now(),
            "received_evidence_at": None,
            "finished_at": None,
            "agent_seconds": 0.0,
            "judge_seconds": 0.0,
            "per_station_seconds": {},
        }
        prior = _load_receipt(resume_from) if resume_from else None
        reused: dict[str, Any] = {}
        if prior is not None:
            recorded = prior.get("agent", {}).get("evidence")
            if isinstance(recorded, Mapping):
                reused = {
                    key: value
                    for key, value in recorded.items()
                    if key in {station.station_id for station in selected}
                }

        agent.start(mission)
        if isinstance(agent, EntityAgent):
            context = replace(
                context,
                client=agent.client,
                program_id=agent.program_id,
                home=agent.allowed_roots[0] if agent.allowed_roots else None,
            )

        missing = [station.station_id for station in selected if station.station_id not in reused]
        submitted: dict[str, Any] = dict(reused)
        if missing:
            answered_at = time.perf_counter()
            produced = agent.evidence(missing, deadline_s=deadline_s)
            clock["agent_seconds"] = time.perf_counter() - answered_at
            clock["received_evidence_at"] = _utc_now()
            submitted.update(dict(produced))

        document: dict[str, Any] | None = None
        if isinstance(agent, EntityAgent):
            document = agent.evidence_document
        answer_fixture_id = None
        if document is not None:
            answer_fixture_id = document.get("fixture_id")
        elif prior is not None:
            answer_fixture_id = prior.get("identity", {}).get("answer_fixture_id")
        world_matches = answer_fixture_id is None or str(answer_fixture_id) == self.fixture.fixture_id()

        outcomes: list[dict[str, Any]] = []
        for station in selected:
            evidence = submitted.get(station.station_id)
            started = time.perf_counter()
            outcomes.append(
                self._judge_station(
                    context, station, evidence, world_matches=world_matches,
                    entity_document=document,
                )
            )
            clock["per_station_seconds"][station.station_id] = time.perf_counter() - started
        clock["judge_seconds"] = sum(clock["per_station_seconds"].values())
        clock["finished_at"] = _utc_now()

        receipt = {
            "schema": COURSE_SCHEMA,
            "identity": {
                "level": self.level,
                "mission_id": mission["mission_id"],
                "fixture_id": self.fixture.fixture_id(),
                "variant": self.fixture.variant,
                "station_ids": [station.station_id for station in selected],
                "agent_kind": getattr(agent, "kind", type(agent).__name__),
                "answer_fixture_id": answer_fixture_id,
                "world_matches": world_matches,
                "oracle_module_sha256": _module_digest(stations_module.oracle_module),
                "stations_module_sha256": _module_digest(stations_module),
            },
            "verdict": "pass" if all(item["verdict"] == "pass" for item in outcomes) else "fail",
            "station_verdicts": {item["station"]: item["verdict"] for item in outcomes},
            "stations": outcomes,
            "agent": {
                "kind": getattr(agent, "kind", type(agent).__name__),
                "evidence": submitted,
                "transcript": agent.transcript(),
            },
            "clock": clock,
            "digest_strip": ["digest", *DIGEST_STRIP],
            "resumed_from": str(resume_from) if resume_from else None,
        }
        receipt["digest"] = receipt_digest(receipt)
        if receipt_path is not None:
            write_receipt(receipt, receipt_path)
        return receipt

    # ---------------------------------------------------------------- judging
    def _judge_station(
        self,
        context: CourseContext,
        station: Station,
        evidence: Mapping[str, Any] | None,
        *,
        world_matches: bool,
        entity_document: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if evidence is None:
            return _blocked(
                station,
                "the agent submitted no evidence for this station",
                reason="missing-evidence",
                answered_world=None if entity_document is None else entity_document.get("fixture_id"),
            )
        schema = evidence.get("schema")
        if schema != station.evidence_schema:
            return _blocked(
                station,
                f"evidence declares schema {schema!r}, the station asked for {station.evidence_schema!r}",
                reason="wrong-evidence-schema",
            )
        if not world_matches:
            return _blocked(
                station,
                "the answer was given for a different world than the one this station declares",
                reason="wrong-world",
                answered_world=None if entity_document is None else entity_document.get("fixture_id"),
            )
        try:
            report = station.judge(context, evidence)
        except LaboratoryError as error:
            return _blocked(station, f"evidence could not be judged: {error}", reason="malformed-evidence")
        except Exception as error:  # a judge bug must be visible, not swallowed
            return _blocked(
                station,
                f"judge raised {type(error).__name__}: {error}",
                reason="judge-error",
            )
        report = dict(report)
        report["evidence"] = evidence
        return report


def _blocked(
    station: Station,
    detail: str,
    *,
    reason: str,
    answered_world: Any = None,
) -> dict[str, Any]:
    return {
        "schema": stations_module.STATION_REPORT_SCHEMA,
        "station": station.station_id,
        "verdict": "blocked",
        "checks": [{"name": "evidence is judgeable", "ok": False, "detail": detail, "numbers": {}}],
        "controls": [],
        "measurements": {"reason": reason, "answered_world": answered_world},
        "notes": [],
    }


# --------------------------------------------------------------------------
# receipts


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _module_digest(module: Any) -> str | None:
    path = getattr(module, "__file__", None)
    if not path:
        return None
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def receipt_body(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """The receipt minus everything the digest strip declares."""

    stripped = set(receipt.get("digest_strip") or DIGEST_STRIP)
    return {key: value for key, value in receipt.items() if key not in stripped}


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    encoded = json.dumps(receipt_body(receipt), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_receipt(receipt: Mapping[str, Any], path: str | os.PathLike[str]) -> Path:
    target = Path(path)
    if target.parent and str(target.parent):
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _load_receipt(path: str | os.PathLike[str]) -> dict[str, Any] | None:
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


# --------------------------------------------------------------------------
# night shift and portfolio


@dataclass
class NightShift:
    """A bounded shift of mixed work, with restarts allowed between rounds.

    Each round is one mission on one world variant.  The shift keeps a
    resumable state file: a restart continues at the first unfinished round and
    the receipt records what the previous sessions had already settled.
    """

    course_factory: Callable[[int], Course]
    rounds: int
    state_path: str | os.PathLike[str]
    receipt_dir: str | os.PathLike[str]
    minutes: float | None = None

    def state(self) -> dict[str, Any]:
        loaded = _load_receipt(self.state_path) or {}
        loaded.setdefault("schema", "cassi.laboratory.night-shift.v1")
        loaded.setdefault("rounds", {})
        return loaded

    def run(self, agent_factory: Callable[[int], Agent], *, deadline_s: float = 900.0) -> dict[str, Any]:
        started = time.monotonic()
        state = self.state()
        for index in range(self.rounds):
            key = str(index)
            if state["rounds"].get(key, {}).get("verdict") == "pass":
                continue
            if self.minutes is not None and (time.monotonic() - started) / 60.0 >= self.minutes:
                state["stopped_at_round"] = index
                state["reason"] = "shift ended"
                break
            course = self.course_factory(index)
            agent = agent_factory(index)
            receipt_path = Path(self.receipt_dir) / f"round-{index:03d}.json"
            receipt = course.run(agent, receipt_path=receipt_path, deadline_s=deadline_s)
            agent.close()
            state["rounds"][key] = {
                "mission_id": receipt["identity"]["mission_id"],
                "fixture_id": receipt["identity"]["fixture_id"],
                "verdict": receipt["verdict"],
                "station_verdicts": receipt["station_verdicts"],
                "receipt": str(receipt_path),
                "digest": receipt["digest"],
            }
            state["digest_strip"] = ["digest", "clock"]
            state["updated_at"] = _utc_now()
            state["digest"] = receipt_digest(state)
            write_receipt(state, self.state_path)
        state["settled"] = sum(
            1 for item in state["rounds"].values() if item.get("verdict") == "pass"
        )
        state["attempted"] = len(state["rounds"])
        state["shift_seconds"] = round(time.monotonic() - started, 3)
        state["digest"] = receipt_digest(state)
        write_receipt(state, self.state_path)
        return state


def portfolio_worlds(count: int | None = None) -> tuple[Fixture, ...]:
    """The declared worlds of the long-horizon portfolio."""

    variants = stations_module.PORTFOLIO_VARIANTS
    chosen = variants if count is None else variants[: max(1, min(count, len(variants)))]
    return tuple(build_fixture(variant=item["variant"], packet=item["packet"]) for item in chosen)


def portfolio_state(path: str | os.PathLike[str]) -> dict[str, Any]:
    loaded = _load_receipt(path) or {}
    loaded.setdefault("schema", "cassi.laboratory.portfolio.v1")
    loaded.setdefault("missions", {})
    return loaded


def run_portfolio_round(
    agent_factory: Callable[[Fixture], Agent],
    *,
    state_path: str | os.PathLike[str],
    receipt_dir: str | os.PathLike[str],
    only: str | None = None,
    deadline_s: float = 900.0,
) -> dict[str, Any]:
    """Settle one outstanding portfolio mission and persist the state."""

    state = portfolio_state(state_path)
    worlds = portfolio_worlds()
    started = time.monotonic()
    for world in worlds:
        if only is not None and world.variant != only:
            continue
        recorded = state["missions"].get(world.variant)
        if recorded is not None and recorded.get("verdict") == "pass":
            continue
        course = Course.physics(world)
        agent = agent_factory(world)
        receipt_path = Path(receipt_dir) / f"{world.variant}.json"
        receipt = course.run(agent, receipt_path=receipt_path, deadline_s=deadline_s)
        agent.close()
        state["missions"][world.variant] = {
            "mission_id": receipt["identity"]["mission_id"],
            "fixture_id": receipt["identity"]["fixture_id"],
            "verdict": receipt["verdict"],
            "station_verdicts": receipt["station_verdicts"],
            "receipt": str(receipt_path),
            "digest": receipt["digest"],
        }
        state["updated_at"] = _utc_now()
        state["digest_strip"] = ["digest", "clock"]
        state["digest"] = receipt_digest(state)
        write_receipt(state, state_path)
    state["settled"] = sum(
        1 for item in state["missions"].values() if item.get("verdict") == "pass"
    )
    state["attempted"] = len(state["missions"])
    state["declared"] = [world.variant for world in worlds]
    state["round_seconds"] = round(time.monotonic() - started, 3)
    state["digest"] = receipt_digest(state)
    write_receipt(state, state_path)
    return state
