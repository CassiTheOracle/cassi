"""A continuing research mission on the existing field-owned regional computer.

The Python object is a disposable I/O driver. Mission, agenda, selection history,
continuation, observations and learned procedures live in cognition.field. The
only additional files are immutable inputs/results and the existing hive's
non-adaptive control plane. No model is called and live source is never replaced.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_atlas import canonical_json_bytes, sha256_value
from cassi_field_cognition import semantic_cognition_state
from cassi_field_input import CODEC_JSON
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput
from cassi_field_regions import make_semantic_record
from cassi_hive_policy import SkillPolicy
from cassi_hive_session import attach_field_session, open_field_session

SCHEMA = "cassifi.research-residency.v1"
MISSION_ID = "research:mission"
CATALOG_ID = "research:catalog"
CURSOR_PREFIX = "research:cursor:"
WORK_PREFIX = "research:work:"
DEFAULT_PROFILE = {"mode_count": 786_432, "default_value_words": 4_096}
DEFAULT_MISSION = "Understand and improve Cassi"
MAX_WORK_ITEMS = 32
MAX_RESULT_BYTES = 1_048_576
MAX_FIELD_OBSERVATIONS = 16


class ResidencyError(RuntimeError):
    """A residency cannot continue without changing its declared conditions."""


def _plain(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def _commit_bytes(path: Path, content: bytes) -> None:
    """Publish once; retrying an acknowledged operation may not change its bytes."""
    if path.exists():
        if path.read_bytes() != content:
            raise ResidencyError(f"immutable research artifact changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _work_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not items or len(items) > MAX_WORK_ITEMS:
        raise ResidencyError(f"research requires 1..{MAX_WORK_ITEMS} work items")
    result = []
    identities: set[str] = set()
    for raw in items:
        item = _plain(dict(raw))
        identity = item.get("id")
        request = item.get("request")
        if (not isinstance(identity, str) or not identity or len(identity) > 128
                or identity in identities or any(ord(c) < 32 for c in identity)):
            raise ResidencyError("work identities must be unique bounded strings")
        if not isinstance(request, dict) or not isinstance(request.get("kind"), str):
            raise ResidencyError("each work item requires a typed request")
        if "operation_id" in request:
            raise ResidencyError("the residency, not a work item, assigns operation identity")
        if not isinstance(item.get("summary"), str) or not item["summary"]:
            raise ResidencyError("each work item requires a summary")
        identities.add(identity)
        result.append({"id": identity, "summary": item["summary"], "request": request})
    if len(canonical_json_bytes(result)) > 65536:
        raise ResidencyError("research work catalog exceeds 64 KiB")
    return result


def initial_work(workspace: Path) -> list[dict[str, Any]]:
    from cassi_research_worlds import initial_work as world_work

    prefix = "CassiFI/" if (Path(workspace) / "CassiFI").is_dir() else ""
    source_paths = [
        f"{prefix}cassi_research_residency.py",
        f"{prefix}cassi_field_regions.py",
        f"{prefix}cassi_field_computer.py",
    ]
    world_items = []
    for raw in world_work(workspace):
        request = dict(raw["request"])
        request.pop("operation_id", None)
        world_items.append({
            "id": raw["id"],
            "summary": raw["summary"],
            "request": request,
        })
    candidate_rows = [
        ("module-boundary-import-alias", "module-boundary-v1", "import-alias"),
        ("module-boundary-import-alias-drift", "module-boundary-v1", "import-alias-drift"),
        ("api-successor-clean-cutover", "api-successor-v1", "clean-cutover"),
        ("api-successor-offset-drift", "api-successor-v1", "offset-drift"),
    ]
    return _work_items([
        {"id": "self-study", "summary": "Identify structural costs in Cassi's resident computer",
         "request": {"kind": "self-study", "source_paths": source_paths}},
        *[
            {"id": item_id,
             "summary": f"Evaluate the isolated {variant} architecture candidate",
             "request": {"kind": "candidate-development",
                         "source_regime": "cassimindfield-lab-example-v1",
                         "compiler_family": family, "variant_key": variant}}
            for item_id, family, variant in candidate_rows
        ],
        *world_items,
    ])


class ResearchResidency:
    """Fixed resumable driver; all evolving research state belongs to the owner."""

    def __init__(self, home: Path, session: Any) -> None:
        self.home = Path(home).resolve()
        self.session = session
        self.owner = session.owner

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> ResearchResidency:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _computer(self) -> Any:
        return next((row for row in self.owner.state.computers
                     if row.computer_id == "research"), None)

    def _task(self) -> Mapping[str, Any]:
        computer = self._computer()
        if computer is None:
            raise ResidencyError("research computer is not initialized")
        task = computer._value("task")
        if not isinstance(task, Mapping) or task.get("family") != "cognition.field":
            raise ResidencyError("research computer is not the resident cognition field")
        return task

    def _record(self, identity: str) -> Mapping[str, Any] | None:
        history = self._task()["records"].get(identity)
        return history[-1] if history else None

    def _required_record(self, identity: str) -> Mapping[str, Any]:
        record = self._record(identity)
        if record is None:
            raise ResidencyError(f"resident record is missing: {identity}")
        return record
    def _catalog(self) -> list[dict[str, Any]]:
        payload = _plain(self._required_record(CATALOG_ID)["payload"])
        if not isinstance(payload, dict) or not isinstance(payload.get("work"), list):
            raise ResidencyError("resident research catalog is invalid")
        return _work_items(payload["work"])


    def _cursor(self) -> dict[str, Any]:
        rows = self._task()["current"]["Value"]
        ids = [key for key in rows if key.startswith(CURSOR_PREFIX)]
        if not ids:
            raise ResidencyError("research continuation is missing")
        return _plain(self._required_record(max(ids))["payload"])

    def _settle(self) -> None:
        for _ in range(64):
            computer = self._computer()
            session = computer._value("session")
            if session["status"] == "halted":
                return
            if session["status"] != "running":
                raise ResidencyError(f"research execution is {session['status']}; continuation retained")
            # State-derived identity also recovers an advance interrupted after publication.
            identity = f"research:advance:{computer.state_sha256}"
            self.owner.operate_computer(identity, computer_id="research", action="advance",
                                        arguments={"steps": 4096})
        raise ResidencyError("research work window exhausted; continuation retained")

    def semantic(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Use one owner path and recover exact prior results from the resident index."""
        request = _plain(dict(request))
        identity = request.get("operation_id")
        if not isinstance(identity, str) or not identity:
            raise ResidencyError("semantic research requests require operation_id")
        self._settle()
        prior = self._task()["indexes"]["operations"].get(identity)
        if prior is not None:
            if prior["request_sha256"] != sha256_value(request):
                raise ResidencyError("research operation identity was reused with different content")
            return _plain(prior["result"])
        self.owner.operate_computer(identity, computer_id="research", action="invoke",
                                    arguments={"arguments": request, "steps": 4096})
        self._settle()
        result = self._task()["indexes"]["operations"].get(identity)
        if result is None:
            raise ResidencyError("research operation did not publish a semantic result")
        answer = _plain(result["result"])
        if answer.get("status") == "resource-exhausted":
            raise ResidencyError("semantic resources exhausted; research continuation retained")
        return answer

    def _register(self, operation_id: str, record_id: str, kind: str,
                  payload: Mapping[str, Any], *, status: str = "active",
                  roots: Sequence[str] = (), epistemic_kind: str = "derived") -> dict[str, Any]:
        return self.semantic({"operation": "register", "operation_id": operation_id,
                              "record_id": record_id, "kind": kind, "payload": dict(payload),
                              "status": status, "epistemic_kind": epistemic_kind,
                              "support_roots": list(roots)})

    def _checkpoint(self, cursor: Mapping[str, Any], **updates: Any) -> None:
        successor = {**dict(cursor), **updates, "sequence": int(cursor["sequence"]) + 1}
        identity = f"{CURSOR_PREFIX}{successor['sequence']:012d}"
        self._register(identity, identity, "Value", successor)

    def initialize(self, *, workspace: Path, mission: str = DEFAULT_MISSION,
                   work: Sequence[Mapping[str, Any]] | None = None,
                   profile: Mapping[str, int] | None = None) -> None:
        workspace = Path(workspace).resolve(strict=True)
        if not workspace.is_dir() or not isinstance(mission, str) or not mission.strip():
            raise ResidencyError("a workspace directory and a nonempty mission are required")
        catalog = _work_items(initial_work(workspace) if work is None else work)
        manifest = {"schema": SCHEMA, "mission": mission, "workspace": str(workspace),
                    "work": catalog, "profile": dict(profile or DEFAULT_PROFILE),
                    "authority": {"live_source_replacement": False, "external_actions": False}}
        if self._computer() is not None:
            computer_session = self._computer()._value("session")
            if computer_session.get("kernel") == "cognition.field":
                self._settle()
                resident = self._record(MISSION_ID)
                if resident is None or resident["payload"] != manifest:
                    raise ResidencyError("existing residency has a different mission or configuration")
                return
        self.owner.operate_computer("research:configure", computer_id="research", action="configure",
                                    arguments={"profile": manifest["profile"]})
        seed = []
        for identity, payload in (
            (MISSION_ID, manifest),
            (CATALOG_ID, {"work": catalog}),
            (f"{CURSOR_PREFIX}{0:012d}", {"sequence": 0, "round": 0, "completed": 0,
              "phase": "seed", "remaining": [], "selected": None}),
        ):
            seed.append(make_semantic_record(record_id=identity, kind="Value", content_version=1,
                        created_at=0, payload=payload, scope="research-residency",
                        epistemic_kind="asserted", status="active"))
        self.owner.operate_computer("research:initialize", computer_id="research", action="submit",
            arguments={"kernel": "cognition.field", "kind": "research-residency",
                       "state": semantic_cognition_state(scope="research-residency", seed_records=seed,
                           bounds={"max_records": 16384, "max_operations": 16384, "max_versions": 128}),
                       "arguments": {"operation": "inspect", "operation_id": "research:initialized"},
                       "steps": 4096})
        self._settle()

    def inspect(self) -> dict[str, Any]:
        task = self._task()
        cursor = self._cursor()
        mission = self._required_record(MISSION_ID)["payload"]
        outcomes = []
        for identity in task["current"]["Assessment"]:
            if identity.startswith("research:outcome:"):
                record = self._required_record(identity)
                payload = record["payload"]
                outcomes.append({
                    "operation_id": payload["work_operation_id"],
                    "work_id": payload["question_id"],
                    "status": payload["result_status"],
                    "summary": payload["summary"],
                    "source_revision_id": payload["source_revision_id"],
                })
        memory_roles: dict[str, int] = {}
        for family in task["current"].values():
            for reference in family.values():
                record = task["records"][reference["id"]][-1]
                role = record["payload"].get("memory_role")
                if isinstance(role, str):
                    memory_roles[role] = memory_roles.get(role, 0) + 1
        computer = self._computer()
        return {
            "schema": SCHEMA,
            "mission": mission["mission"],
            "workspace": mission["workspace"],
            "phase": cursor["phase"],
            "round": cursor["round"],
            "completed": cursor["completed"],
            "selected": cursor.get("selected"),
            "remaining": cursor["remaining"],
            "outcomes": outcomes[-16:],
            "resident_records": len(task["records"]),
            "resident_operations": len(task["indexes"]["operations"]),
            "learned_procedures": len(task["libraries"]["procedures"]),
            "living_memory": {
                "roles": dict(sorted(memory_roles.items())),
                "recall_episodes": memory_roles.get("recall-episode", 0),
                "prospective_conditions": memory_roles.get(
                    "relevance-condition", 0
                ),
                "relevance_wakeups": memory_roles.get("relevance-wakeup", 0),
                "hypotheses": memory_roles.get("quiet-synthesis", 0),
                "maintenance_assessments": memory_roles.get(
                    "maintenance-assessment", 0
                ),
            },
            "field_state_sha256": computer.state_sha256,
            "owner_state_sha256": self.owner.state.state_sha256,
            "computer_status": computer._value("session")["status"],
            "authority": mission["authority"],
            "hive": _plain(self.session.status()),
        }

    def _work_id(self, cursor: Mapping[str, Any], item_id: str) -> str:
        return f"{WORK_PREFIX}{int(cursor['round']):08d}:{item_id}"
    def _adapter_artifact_home(self, workspace: Path, operation_id: str) -> Path:
        """Keep adapter-generated candidate/source artifacts outside the source tree."""
        workspace = workspace.resolve(strict=True)
        residency = self.home.resolve()
        residency_key = hashlib.sha256(str(residency).encode("utf-8")).hexdigest()[:16]
        root = workspace.parent / f".{workspace.name}-research-artifacts" / residency_key
        if root.resolve().is_relative_to(workspace):
            temp_root = Path(os.environ.get("TEMP", os.environ.get("TMP", str(workspace.parent))))
            root = temp_root / "cassi-research-artifacts" / residency_key
        return root / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    def _circulation_modulation(self, count: int) -> Mapping[str, Any] | None:
        """The bounded eligible-work modulation of the resident circulation.

        Work sites are the eligible continuations this residency presents, in
        its declared fairness order.  The realised flow supplies a bounded
        priority pattern only: eligibility, authority, and the fairness rule
        stay the owner's, and flow magnitude is never evidence.  No resident
        circulation means no hint, which is the declared no-flow case.
        """
        if count <= 0:
            return None
        return self.owner.circulation_modulation(
            [{"sequence": index} for index in range(count)]
        )

    def _choose(self, cursor: Mapping[str, Any], identity: str) -> dict[str, Any]:
        modulation = self._circulation_modulation(len(cursor["remaining"]))
        request = {"operation": "autonomous-agenda", "operation_id": identity + ":agenda",
            "goal": {"objective": self._required_record(MISSION_ID)["payload"]["mission"]},
            "obligation_prefix": f"{WORK_PREFIX}{int(cursor['round']):08d}:", "max_items": 128}
        if modulation is not None:
            request["circulation"] = modulation
        agenda = self.semantic(request)
        candidates = []
        for item_id in cursor["remaining"]:
            reference = self._task()["current"]["Obligation"][self._work_id(cursor, item_id)]
            candidates.append({"candidate_id": item_id, "reference": reference})
        selection = self.semantic({"operation": "history-select", "operation_id": identity + ":history",
                                   "candidates": candidates})
        selected = selection.get("selected")
        if selected is not None:
            return {"id": selected["candidate_id"], "basis": "resident-outcome-history",
                    "selection_event": selection["event"],
                    "circulation": "applied" if modulation is not None else "no-resident-circulation"}
        allowed = {self._work_id(cursor, item_id): item_id for item_id in cursor["remaining"]}
        for item in agenda["agenda"]:
            obligation = item.get("obligation", {})
            if obligation.get("id") in allowed:
                return {"id": allowed[obligation["id"]], "basis": "resident-obligation-agenda",
                        "selection_event": agenda["event"],
                        "circulation": "applied" if modulation is not None else "no-resident-circulation"}
        raise ResidencyError("field agenda did not select any available research obligation")

    def _execute(self, cursor: Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
        selected = cursor["selected"]
        item = next(item for item in self._catalog() if item["id"] == selected["id"])
        operation_id = self._work_id(cursor, item["id"])
        request = {**item["request"], "operation_id": operation_id}
        directory = self.home / "artifacts" / hashlib.sha256(operation_id.encode()).hexdigest()
        output_path = directory / "result.json"
        marker = directory / "request.json"
        request_bytes = canonical_json_bytes(request)
        if marker.exists() and marker.read_bytes() != request_bytes:
            raise ResidencyError("research artifact request does not match the resident work")
        if output_path.exists():
            output_bytes = output_path.read_bytes()
            output = json.loads(output_bytes)
        elif marker.exists():
            # Even read-only observations may change. An ambiguous interrupted sample
            # is recorded as missing, never silently replaced with a later sample.
            output = {"status": "support-gap", "summary": "Previous execution has no durable acknowledgment; no action was repeated.",
                      "evidence": {"operation_id": operation_id, "ambiguous_execution": True}}
            output_bytes = canonical_json_bytes(output)
            _commit_bytes(output_path, output_bytes)
        else:
            _commit_bytes(marker, request_bytes)
            workspace = Path(self._required_record(MISSION_ID)["payload"]["workspace"])
            kind = request["kind"]
            if kind in {"self-study", "candidate-development"}:
                from cassi_research_development import execute_work
            else:
                from cassi_research_worlds import execute_work
            output = execute_work(
                request,
                workspace=workspace,
                artifact_home=self._adapter_artifact_home(workspace, operation_id),
                semantic=self.semantic,
            )
            if not isinstance(output, dict) or output.get("status") not in {
                    "observed", "supported", "support-gap", "rejected"}:
                raise ResidencyError("research adapter returned an invalid result")
            output_bytes = canonical_json_bytes(output)
            if len(output_bytes) > MAX_RESULT_BYTES:
                raise ResidencyError("research result exceeds its 1 MiB evidence bound")
            _commit_bytes(output_path, output_bytes)
        return output, str(output_path.relative_to(self.home)), hashlib.sha256(output_bytes).hexdigest()

    def _observations(self, operation_id: str, output: Mapping[str, Any]) -> list[dict[str, Any]]:
        def bounded(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
            normalized = [dict(row) for row in rows]
            if len(normalized) <= MAX_FIELD_OBSERVATIONS:
                return normalized
            last = len(normalized) - 1
            indices = [
                (index * last) // (MAX_FIELD_OBSERVATIONS - 1)
                for index in range(MAX_FIELD_OBSERVATIONS)
            ]
            return [normalized[index] for index in indices]

        raw = output.get("observations")
        if isinstance(raw, list) and raw and all(
            isinstance(row, Mapping)
            and isinstance(row.get("subject"), str)
            and "value" in row
            for row in raw
        ):
            return bounded(raw)
        evidence = output.get("evidence")
        continuation = evidence.get("continuation") if isinstance(evidence, Mapping) else None
        rows = continuation.get("observations") if isinstance(continuation, Mapping) else None
        if isinstance(rows, list):
            consequences = []
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    continue
                step = row.get("step", row.get("bar_index", index))
                consequences.append({
                    "subject": f"{operation_id}:step:{step}",
                    "attribute": "world-consequence",
                    "value": dict(row),
                    "frame": {"step": step, "operation_id": operation_id},
                })
            if consequences:
                return bounded(consequences)
        return [{
            "subject": operation_id,
            "attribute": "result",
            "value": {"status": output["status"], "summary": output["summary"]},
        }]


    def _candidate_procedure_opportunity(
        self, operation_id: str, output: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Turn repeated successful candidate runs into admissible procedure evidence."""
        task = self._task()
        current_events = task.get("current", {}).get("Event", {})
        records = task.get("records", {})
        if not isinstance(current_events, Mapping) or not isinstance(records, Mapping):
            return None
        current_event_id = f"{operation_id}:event"
        if current_event_id not in current_events:
            return None
        candidate_ids = {
            str(item["id"])
            for item in self._catalog()
            if isinstance(item.get("request"), Mapping)
            and item["request"].get("kind") == "candidate-development"
        }

        def supported_event(event_id: str) -> bool:
            operation = event_id[: -len(":event")]
            history = records.get(f"research:outcome:{operation}")
            if not isinstance(history, list) or not history:
                return False
            payload = history[-1].get("payload", {})
            return isinstance(payload, Mapping) and payload.get("status") == "supported"

        event_ids = sorted(
            event_id
            for event_id in current_events
            if isinstance(event_id, str)
            and event_id.endswith(":event")
            and any(
                event_id.endswith(f":{candidate_id}:event")
                for candidate_id in candidate_ids
            )
            and supported_event(event_id)
        )
        procedure_id = (
            "resident-procedure:candidate-development:"
            "cassimindfield-lab-example-v1"
        )
        procedures = task.get("libraries", {}).get("procedures", {})
        programs = task.get("current", {}).get("Program", {})
        if procedure_id in procedures or procedure_id in programs:
            return None
        if len(event_ids) < 3:
            return None
        selected_ids = event_ids[:3]
        support_refs = [
            current_events[event_id]
            for event_id in selected_ids
            if isinstance(current_events[event_id], Mapping)
            and {"id", "kind", "content_version"} <= set(current_events[event_id])
        ]
        if len(support_refs) != len(selected_ids):
            return None

        def trace(event_id: str, index: int) -> dict[str, Any]:
            return {
                "context": {"source_regime": "cassimindfield-lab-example-v1"},
                "effects": {"result_status": "supported"},
                "failure": None,
                "outcome": {"result_status": "supported"},
                "rare_case": False,
                "steps": [
                    {
                        "action": {"kind": "candidate-development", "phase": "compile"},
                        "transition": {
                            "pre_state_shape": "source",
                            "post_state_shape": "candidate",
                        },
                    },
                    {
                        "action": {"kind": "candidate-development", "phase": "measure"},
                        "transition": {
                            "pre_state_shape": "candidate",
                            "post_state_shape": "assessment",
                        },
                    },
                ],
                "success": True,
                "support_event_refs": [event_id],
                "trace_id": f"candidate-development:{index}:{event_id}",
                "trajectory_source": "declared",
                "work": 2,
            }

        training = [
            trace(event_id, index)
            for index, event_id in enumerate(selected_ids[:2])
        ]
        holdout = [trace(selected_ids[2], 2)]
        return {
            "candidate_id": procedure_id,
            "learning_kind": "procedure",
            "expected_gain": 2.0,
            "urgency": 0.75,
            "novelty": 1.5,
            "priority": 1.0,
            "cost": 2.0,
            "risk": 0.0,
            "request": {
                "procedure_id": procedure_id,
                "max_length": 2,
                "min_length": 2,
                "support_event_refs": support_refs,
                "support_roots": [],
                "traces": training,
                "holdout": holdout,
            },
        }

    def _output(self, cursor: Mapping[str, Any]) -> tuple[dict[str, Any], bytes]:
        path = (self.home / cursor["output_path"]).resolve()
        if not path.is_relative_to(self.home / "artifacts"):
            raise ResidencyError("research result escapes its artifact home")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != cursor["output_sha256"]:
            raise ResidencyError("acknowledged research result changed")
        return json.loads(content), content

    def advance(self) -> dict[str, Any]:
        """Advance one durable phase, preserving every boundary on interruption."""
        self._settle()
        cursor = self._cursor()
        identity = f"research:phase:{int(cursor['sequence']):012d}"
        phase = cursor["phase"]
        if phase == "seed":
            for item in self._catalog():
                record_id = self._work_id(cursor, item["id"])
                self._register(record_id + ":open", record_id, "Obligation",
                    {"purpose": "research", "status": "pending", "question_id": item["id"],
                     "compiler_family": item["request"]["kind"], "summary": item["summary"],
                     "request": item["request"]}, status="pending", epistemic_kind="asserted")
            self._checkpoint(cursor, phase="choose",
                             remaining=[item["id"] for item in self._catalog()])
        elif phase == "choose":
            selection = self._choose(cursor, identity)
            self._checkpoint(cursor, phase="execute", selected=selection)
        elif phase == "execute":
            _, path, digest = self._execute(cursor)
            self._checkpoint(cursor, phase="admit", output_path=path, output_sha256=digest)
        elif phase == "admit":
            output, content = self._output(cursor)
            operation_id = self._work_id(cursor, cursor["selected"]["id"])
            source = SourceInput(source_id=operation_id, content=content, media_type="application/json",
                codec=CODEC_JSON, observed_timestamp=operation_id, scope="research-residency",
                claim_category="research-operation-result", fidelity="exact-observed-bytes",
                labels=("research-residency",))
            archive = self.owner.archive_source(operation_id=operation_id + ":archive", source=source,
                                               context={"work_operation_id": operation_id})
            root = archive["source"]["revision_id"]
            observations = self._observations(operation_id, output)
            self.semantic({"operation": "observe", "operation_id": operation_id + ":observe",
                "delivery_id": operation_id + ":delivery", "event_id": operation_id + ":event",
                "observations": observations, "source": {"source_revision_id": root}, "support_roots": [root]})
            item = next(item for item in self._catalog() if item["id"] == cursor["selected"]["id"])
            self._register(operation_id + ":assess", "research:outcome:" + operation_id, "Assessment",
                {"work_operation_id": operation_id, "question_id": item["id"],
                 "compiler_family": item["request"]["kind"],
                 "status": "supported" if output["status"] in {"observed", "supported"} else "failed",
                 "result_status": output["status"], "summary": output["summary"],
                 "source_revision_id": root, "output_sha256": cursor["output_sha256"]}, roots=[root],
                epistemic_kind="assessed")
            self._checkpoint(cursor, phase="learn", source_revision_id=root)
        elif phase == "learn":
            output, _ = self._output(cursor)
            operation_id = self._work_id(cursor, cursor["selected"]["id"])
            request: dict[str, Any] = {
                "operation": "autonomous-learn",
                "operation_id": identity + ":learn",
                "goal": {
                    "objective": self._required_record(MISSION_ID)["payload"]["mission"]
                },
            }
            valid_opportunities: list[dict[str, Any]] = []
            raw_opportunities = output.get("learning_opportunities")
            if isinstance(raw_opportunities, list):
                valid_opportunities.extend(
                    dict(row)
                    for row in raw_opportunities
                    if isinstance(row, Mapping)
                    and row.get("learning_kind") == "predictive-state"
                    and isinstance(row.get("request"), Mapping)
                    and {"examples", "representation_id", "signature"}
                    <= set(row["request"])
                )
            procedure = self._candidate_procedure_opportunity(operation_id, output)
            if procedure is not None:
                valid_opportunities.append(procedure)
            if valid_opportunities:
                request["opportunities"] = valid_opportunities
            learned = self.semantic(request)
            self._checkpoint(cursor, phase="finish", learning_status=learned["status"],
                             learning_event=learned.get("event"))
        elif phase == "finish":
            output, _ = self._output(cursor)
            selected = cursor["selected"]["id"]
            operation_id = self._work_id(cursor, selected)
            outcome_record = self._required_record(
                "research:outcome:" + operation_id
            )
            outcome_ref = {
                "id": outcome_record["id"],
                "kind": outcome_record["kind"],
                "content_version": outcome_record["content_version"],
            }
            relevance = self.semantic({
                "operation": "match-relevance",
                "operation_id": operation_id + ":memory-relevance",
                "event_id": operation_id + ":completed",
                "context": {
                    "question_id": selected,
                    "result_status": output["status"],
                    "compiler_family": outcome_record["payload"][
                        "compiler_family"
                    ],
                    "learning_status": cursor["learning_status"],
                    "source_revision_id": cursor["source_revision_id"],
                },
                "maximum": 32,
            })
            maintenance = self.semantic({
                "operation": "maintain-memory",
                "operation_id": operation_id + ":memory-maintenance",
                "purpose": {
                    "kind": "completed-research-review",
                    "question_id": selected,
                },
                "target_refs": [outcome_ref],
                "allowance": {"max_records": 32, "max_work": 64},
            })
            self._register(
                operation_id + ":resolve",
                operation_id,
                "Obligation",
                {
                    "purpose": "research",
                    "status": "resolved",
                    "question_id": selected,
                    "result_status": output["status"],
                    "source_revision_id": cursor["source_revision_id"],
                    "learning_status": cursor["learning_status"],
                    "memory_relevance": {
                        "status": relevance["status"],
                        "wakeups": len(relevance.get("wakeups", [])),
                        "unknown": len(relevance.get("unknown", [])),
                        "limitation": relevance.get("limitation"),
                    },
                    "memory_maintenance": {
                        "status": maintenance["status"],
                        "assessment": maintenance.get("assessment"),
                    },
                },
                status="resolved",
                roots=[cursor["source_revision_id"]],
            )
            work = _plain(self._catalog())
            continuation = output.get("continuation_request")
            if continuation is not None:
                for item in work:
                    if item["id"] == selected:
                        item["request"] = continuation
            for followup in output.get("follow_up_requests", []):
                if not any(item["id"] == followup["id"] for item in work):
                    work.append(followup)
            work = _work_items(work)
            self._register(operation_id + ":catalog", CATALOG_ID, "Value", {"work": work})
            remaining = [item_id for item_id in cursor["remaining"] if item_id != selected]
            next_cursor = {"sequence": cursor["sequence"], "round": cursor["round"] + int(not remaining),
                           "completed": cursor["completed"] + 1, "phase": "choose" if remaining else "seed",
                           "remaining": remaining, "selected": None}
            self._checkpoint(next_cursor)
        else:
            raise ResidencyError(f"unknown resident phase: {phase}")
        return self.inspect()


def attach_research_residency(
    owner: FieldIntelligenceOwner,
    data_home: Path,
    *,
    hive_home: Path | None = None,
    role: str = "research-root",
) -> ResearchResidency:
    """Attach a residency to an already-live owner without taking ownership."""
    home = Path(data_home).resolve()
    policy = SkillPolicy.for_mode(
        "isolated",
        import_enabled=False,
        export_enabled=False,
        apply_mode="never",
        sync_mode="manual",
        export_mode="on-close",
    )
    session = attach_field_session(
        owner,
        data_home=home / "field",
        hive_home=hive_home or home / "hive",
        mode="isolated",
        role=role,
        policy=policy,
    )
    return ResearchResidency(home, session)


def open_research_residency(
    data_home: Path,
    *,
    hive_home: Path | None = None,
    import_skills: bool = False,
    export_skills: bool = False,
    limits: CapacityLimits | None = None,
) -> ResearchResidency:
    home = Path(data_home).resolve()
    policy = SkillPolicy.for_mode(
        "isolated",
        import_enabled=import_skills,
        export_enabled=export_skills,
        apply_mode="verified" if import_skills else "never",
        sync_mode="manual",
        export_mode="on-close",
    )
    owner = (
        None
        if limits is None
        else FieldIntelligenceOwner(home / "field", limits=limits)
    )
    try:
        session = open_field_session(
            home / "field",
            hive_home=hive_home or home / "hive",
            mode="isolated",
            role="research-resident",
            policy=policy,
            owner=owner,
            owns_owner=owner is not None,
        )
    except BaseException:
        if owner is not None:
            owner.close()
        raise
    return ResearchResidency(home, session)
