#!/usr/bin/env python3
"""Field-owned, bounded self-study loop for CassiMindField v13-v18.

The runtime owns one JSON field state and immutable generation directories.  It never
calls a model: hypotheses are bounded data, probes are explicit commands, and every
assessment is derived from the command result and source-byte provenance.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .self_observatory import canonical, digest, index_workspace, run_bounded_command, sha256_bytes, source_references
except ImportError:  # direct script entry point
    from self_observatory import canonical, digest, index_workspace, run_bounded_command, sha256_bytes, source_references

FIELD_ROOT = Path(__file__).resolve().parents[1] / "CassiQwen"
if str(FIELD_ROOT) not in sys.path:
    sys.path.insert(0, str(FIELD_ROOT))
try:
    from cassi_field_qwen_workbench import CassiFieldWorkMemory, WorkMemoryRecord  # type: ignore
except ImportError as exc:  # the field owner is a required dependency, not a fallback
    raise RuntimeError("CassiFI field owner is required for self-study selection") from exc


SCHEMA = "cassimindfield.self-study.v13-v18.v1"
STATE_SCHEMA = "cassimindfield.self-study-field-state.v1"
RECEIPT_SCHEMA = "cassimindfield.field-observation-receipt.v1"
MAX_HYPOTHESES = 256
MAX_GOALS = 256
MAX_COMMAND_ARGS = 32
MAX_TEXT_BYTES = 16_384
STUDY_VERSIONS = ("v13", "v14", "v15", "v16", "v17", "v18")


class SelfStudyError(RuntimeError):
    pass


class MutationRejected(SelfStudyError):
    pass


def _text(value: Any, label: str, maximum: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value


def _stable_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"content_sha256", "timing"}}


def _stable_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key not in {"content_sha256", "created_wall_ns"}}


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_bytes(path, canonical(value) + b"\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MutationRejected(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise MutationRejected(f"artifact is not an object: {path}")
    return value


def _check_digest(value: Mapping[str, Any], field: str, stable: Mapping[str, Any]) -> None:
    actual = value.get(field)
    if not isinstance(actual, str) or actual != digest(stable):
        raise MutationRejected(f"{field} mismatch")


def _normalize_hypothesis(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("hypothesis must be an object")
    hypothesis_id = _text(raw.get("hypothesis_id", raw.get("id", "")), "hypothesis_id", 256)
    claim = _text(raw.get("claim", "bounded probe prediction"), "claim", 4096)
    command = raw.get("command")
    if isinstance(command, str):
        command = [command]
    if not isinstance(command, Sequence) or isinstance(command, (bytes, str)) or not 1 <= len(command) <= MAX_COMMAND_ARGS:
        raise ValueError("command must be a bounded nonempty argument list")
    command = [_text(str(part), "command argument", 8192) for part in command]
    expected = raw.get("expected", {})
    if not isinstance(expected, Mapping):
        raise ValueError("expected must be an object")
    paths = raw.get("source_paths", raw.get("paths", []))
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, Sequence) or isinstance(paths, (bytes, str)) or len(paths) > 128:
        raise ValueError("source_paths must be a bounded list")
    return {"hypothesis_id": hypothesis_id, "claim": claim, "command": command, "cwd": _text(str(raw.get("cwd", ".")), "cwd", 1024), "timeout_seconds": float(raw.get("timeout_seconds", raw.get("timeout", 10.0))), "expected": json.loads(canonical(expected)), "source_paths": [_text(str(path), "source path", 1024).replace("\\", "/") for path in paths]}


def _json_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            return None
    return current


def assess_prediction(hypothesis: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    expected = hypothesis["expected"]
    errors: list[dict[str, Any]] = []
    def compare(metric: str, expected_value: Any, observed: Any, distance: float) -> None:
        errors.append({"metric": metric, "expected": expected_value, "observed": observed, "absolute_error": float(distance), "matched": bool(distance == 0)})
    if "returncode" in expected:
        wanted = expected["returncode"]
        compare("returncode", wanted, result.get("returncode"), 0.0 if result.get("returncode") == wanted else 1.0)
    if "stdout_contains" in expected:
        wanted = _text(expected["stdout_contains"], "stdout_contains")
        compare("stdout_contains", wanted, wanted in str(result.get("stdout", "")), 0.0 if wanted in str(result.get("stdout", "")) else 1.0)
    if "stderr_contains" in expected:
        wanted = _text(expected["stderr_contains"], "stderr_contains")
        compare("stderr_contains", wanted, wanted in str(result.get("stderr", "")), 0.0 if wanted in str(result.get("stderr", "")) else 1.0)
    if "stdout_sha256" in expected:
        wanted = _text(expected["stdout_sha256"], "stdout_sha256", 128)
        observed = sha256_bytes(str(result.get("stdout", "")).encode("utf-8"))
        compare("stdout_sha256", wanted, observed, 0.0 if wanted == observed else 1.0)
    if "stdout_json" in expected:
        try:
            observed = json.loads(str(result.get("stdout", "")))
        except Exception:
            observed = None
        compare("stdout_json", expected["stdout_json"], observed, 0.0 if observed == expected["stdout_json"] else 1.0)
    if "stdout_json_path" in expected:
        try:
            parsed = json.loads(str(result.get("stdout", "")))
            observed = _json_path(parsed, str(expected["stdout_json_path"]))
        except Exception:
            observed = None
        compare("stdout_json_path", expected.get("stdout_json_value"), observed, 0.0 if observed == expected.get("stdout_json_value") else 1.0)
    if "max_wall_ns" in expected:
        observed = int(result.get("timing", {}).get("wall_ns", 0))
        limit = int(expected["max_wall_ns"])
        compare("max_wall_ns", limit, observed, 0.0 if observed <= limit else float(observed - limit) / max(1, limit))
    if not errors:
        raise ValueError("prediction must declare at least one expected observable")
    error = sum(float(row["absolute_error"]) for row in errors) / len(errors)
    return {"schema": "cassimindfield.prediction-assessment.v1", "hypothesis_id": hypothesis["hypothesis_id"], "claim": hypothesis["claim"], "errors": errors, "prediction_error": error, "status": "PASS" if error == 0 else "MISS", "result_content_sha256": result["content_sha256"]}


class SelfStudyRuntime:
    """Bounded self-study whose adaptive agenda is resident in cognition.field.

    Generation JSON is immutable evidence only.  Hypotheses, obligations,
    assessments, and curiosity goals are semantic records in the resident
    field; selection never consults a generation state file.
    """

    def __init__(
        self,
        data_home: str | os.PathLike[str],
        workspace: str | os.PathLike[str],
        *,
        allow_workspace_mutation: bool = False,
        field_variant: str = "resident",
    ) -> None:
        self.data_home = Path(data_home).resolve()
        self.workspace = Path(workspace).resolve()
        if field_variant not in {"resident", "fresh", "lesioned"}:
            raise ValueError("field_variant must be resident, fresh, or lesioned")
        self.field_variant = field_variant
        self.data_home.mkdir(parents=True, exist_ok=True)
        field_home = self.data_home / "field"
        if field_variant in {"fresh", "lesioned"}:
            # A counterfactual uses a separate durable checkpoint.  It receives
            # the same evidence but never mutates the normal resident field.
            field_home = self.data_home / f"field-{field_variant}"
            if field_variant == "lesioned" and field_home.exists():
                shutil.rmtree(field_home)
        self.field_memory = CassiFieldWorkMemory(field_home)
        self.workspace_index = index_workspace(self.workspace)
        self.allow_workspace_mutation = bool(allow_workspace_mutation)
        self._ensure_bootstrap()

    def close(self) -> None:
        self.field_memory.close()

    @property
    def pointer_path(self) -> Path:
        return self.data_home / "current.json"

    def _generation_path(self, generation: int) -> Path:
        return self.data_home / "generations" / f"g{generation:04d}"

    def _ensure_bootstrap(self) -> None:
        if self.pointer_path.exists():
            self._load_current()
            return
        state = {
            "schema": STATE_SCHEMA,
            "field_owner": "CassiMindField",
            "workspace_revision_id": self.workspace_index["workspace_revision_id"],
            "adaptive_state": "resident-field-only",
            "field_variant": self.field_variant,
        }
        receipt = self._make_receipt(0, state, [], [], bootstrap=True)
        self._commit(0, state, receipt)

    def _load_current(self) -> tuple[int, dict[str, Any], dict[str, Any]]:
        pointer = _read_json(self.pointer_path)
        _check_digest(pointer, "pointer_sha256", {k: v for k, v in pointer.items() if k != "pointer_sha256"})
        generation = pointer.get("generation")
        if not isinstance(generation, int) or generation < 0:
            raise MutationRejected("invalid current generation")
        directory = self._generation_path(generation)
        state = _read_json(directory / "state.json")
        receipt = _read_json(directory / "receipt.json")
        _check_digest(receipt, "content_sha256", _stable_receipt(receipt))
        if pointer.get("receipt_sha256") != receipt.get("content_sha256") or pointer.get("state_sha256") != digest(state):
            raise MutationRejected("current pointer does not match generation")
        return generation, state, receipt

    def _make_receipt(
        self,
        generation: int,
        state: Mapping[str, Any],
        observations: Sequence[Mapping[str, Any]],
        assessments: Sequence[Mapping[str, Any]],
        *,
        bootstrap: bool = False,
        field_selection: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        field_state = self.field_memory.state_receipt()
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "runtime_schema": SCHEMA,
            "study_versions": list(STUDY_VERSIONS),
            "generation": generation,
            "workspace_revision_id": self.workspace_index["workspace_revision_id"],
            "workspace_index_sha256": self.workspace_index["content_sha256"],
            "source_files": self.workspace_index["files"],
            "test_paths": self.workspace_index["test_paths"],
            "observations": list(observations),
            "assessments": list(assessments),
            "field_selection": None if field_selection is None else dict(field_selection),
            "field_operation_ids": [] if field_selection is None else list(field_selection.get("operation_ids", [])),
            "field_record_refs": [] if field_selection is None else list(field_selection.get("record_refs", [])),
            "field_state_sha256": field_state["state_sha256"],
            "field_checkpoint_receipt": field_state.get("checkpoint_receipt"),
            "bootstrap": bootstrap,
        }
        receipt["content_sha256"] = digest(receipt)
        return receipt

    def _commit(self, generation: int, state: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
        directory = self._generation_path(generation)
        if directory.exists():
            old = _read_json(directory / "receipt.json")
            if old.get("content_sha256") != receipt.get("content_sha256"):
                raise MutationRejected("immutable generation already exists")
            return
        temporary = self.data_home / "generations" / f".g{generation:04d}.tmp-{os.getpid()}"
        temporary.mkdir(parents=True, exist_ok=False)
        try:
            _atomic_json(temporary / "state.json", dict(state))
            _atomic_json(temporary / "receipt.json", dict(receipt))
            os.replace(temporary, directory)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
        pointer = {"schema": "cassimindfield.current-pointer.v1", "generation": generation, "receipt_sha256": receipt["content_sha256"], "state_sha256": digest(state)}
        pointer["pointer_sha256"] = digest(pointer)
        _atomic_json(self.pointer_path, pointer)

    def _semantic_id(self, kind: str, label: str) -> str:
        return f"self-study:{kind}:{digest(label)[:32]}"

    def _field_records(self) -> list[Mapping[str, Any]]:
        recalled = self.field_memory.recall(
            {
                "study": "cassimindfield-self-study",
                "workspace_revision_id": self.workspace_index["workspace_revision_id"],
            },
            operation_label=f"self-study:records:{self.field_memory.state_receipt()['state_sha256'][:24]}",
        )
        rows = recalled.get("records", [])
        return [row for row in rows if isinstance(row, Mapping)]

    def submit_hypothesis(self, hypothesis: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _normalize_hypothesis(hypothesis)
        generation, state, _ = self._load_current()
        if state["workspace_revision_id"] != self.workspace_index["workspace_revision_id"] and not self.allow_workspace_mutation:
            raise MutationRejected("workspace source changed since field study began")
        for row in self._field_records():
            payload = row.get("payload", {})
            hypothesis_payload = payload.get("hypothesis", {}) if isinstance(payload, Mapping) else {}
            if isinstance(hypothesis_payload, Mapping) and hypothesis_payload.get("hypothesis_id") == normalized["hypothesis_id"]:
                raise ValueError("hypothesis_id already exists")
        record = WorkMemoryRecord(
            source_id=f"self-study-hypothesis:{normalized['hypothesis_id']}",
            context={"study": "cassimindfield-self-study", "workspace_revision_id": self.workspace_index["workspace_revision_id"]},
            payload={"hypothesis": normalized},
            observed_timestamp=f"logical:self-study:{generation}",
            labels=("self-study", "hypothesis"),
        )
        learned = self.field_memory.learn(record)
        source_revision = learned.get("source_revision_id")
        operation_id = self._semantic_id("admit", normalized["hypothesis_id"])
        self.field_memory.semantic(
            {
                "operation": "register",
                "operation_id": operation_id,
                "record_id": f"self-study-obligation:{normalized['hypothesis_id']}",
                "kind": "Obligation",
                "status": "pending",
                "epistemic_kind": "observed",
                "support_roots": [source_revision] if isinstance(source_revision, str) else [],
                "payload": {
                    "purpose": "prediction",
                    "state": "pending",
                    "hypothesis_id": normalized["hypothesis_id"],
                    "hypothesis": normalized,
                    "priority": 1.0,
                    "source_revision_id": source_revision,
                },
            },
            operation_label=f"self-study:admit:{normalized['hypothesis_id']}",
        )
        return normalized

    def _field_select(self) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        before = self.field_memory.state_receipt()
        operation_id = self._semantic_id("agenda", f"{before['state_sha256']}:{before['generation']}")
        response = self.field_memory.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": operation_id,
                "goal": {"kind": "self-study-probe", "objective": "reduce prediction error"},
                "max_items": 4,
            },
            operation_label=f"self-study:autonomous-agenda:{operation_id}",
        )
        result = response.get("result", {})
        agenda = result.get("agenda", []) if isinstance(result, Mapping) else []
        if not agenda:
            raise SelfStudyError("field autonomous agenda produced no pending probe")
        item = agenda[0]
        obligation = item.get("obligation", {}) if isinstance(item, Mapping) else {}
        obligation_id = obligation.get("id") if isinstance(obligation, Mapping) else None
        selected = None
        for row in self._field_records():
            payload = row.get("payload", {})
            hypothesis_payload = payload.get("hypothesis", {}) if isinstance(payload, Mapping) else {}
            if isinstance(hypothesis_payload, Mapping) and hypothesis_payload.get("hypothesis_id") == str(obligation_id).removeprefix("self-study-obligation:"):
                selected = hypothesis_payload
                break
        if not isinstance(selected, Mapping):
            raise SelfStudyError("field agenda selected an unresolved obligation")
        after = self.field_memory.state_receipt()
        return selected, {
            "schema": "cassimindfield.field-selection.v3",
            "method": "semantic.autonomous-agenda",
            "operation_id": operation_id,
            "agenda": agenda,
            "selected_candidate_id": selected["hypothesis_id"],
            "field_state_in_sha256": before["state_sha256"],
            "field_state_out_sha256": after["state_sha256"],
            "checkpoint_receipt": after.get("checkpoint_receipt"),
        }

    def run_cycle(self, hypothesis: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if hypothesis is not None:
            normalized = _normalize_hypothesis(hypothesis)
            if not any(
                isinstance(row.get("payload"), Mapping)
                and isinstance(row["payload"].get("hypothesis"), Mapping)
                and row["payload"]["hypothesis"].get("hypothesis_id") == normalized["hypothesis_id"]
                for row in self._field_records()
            ):
                self.submit_hypothesis(normalized)
        generation, state, _ = self._load_current()
        if state["workspace_revision_id"] != self.workspace_index["workspace_revision_id"] and not self.allow_workspace_mutation:
            raise MutationRejected("workspace source changed since field study began")
        try:
            selected, field_selection = self._field_select()
        except SelfStudyError:
            return {"schema": SCHEMA, "status": "idle", "generation": generation, "observations": [], "assessments": [], "goals": []}
        result = run_bounded_command(selected["command"], workspace=self.workspace, cwd=selected["cwd"], timeout_seconds=selected["timeout_seconds"])
        refs = source_references(self.workspace_index, selected["source_paths"] or None)
        observation = {"schema": "cassimindfield.field-observation.v1", "observation_id": "observation:" + digest({"hypothesis_id": selected["hypothesis_id"], "result": _stable_result(result)}), "hypothesis_id": selected["hypothesis_id"], "hypothesis": dict(selected), "source_revision_id": self.workspace_index["workspace_revision_id"], "source_index_sha256": self.workspace_index["content_sha256"], "source_refs": refs, "field_selection": field_selection, "result": result, "result_content_sha256": result["content_sha256"]}
        assessment = assess_prediction(selected, result)
        assessment["source_revision_id"] = self.workspace_index["workspace_revision_id"]
        assessment["source_refs"] = refs
        event_id = self._semantic_id("event", observation["observation_id"])
        self.field_memory.semantic(
            {
                "operation": "observe",
                "operation_id": self._semantic_id("observe", observation["observation_id"]),
                "delivery_id": observation["observation_id"],
                "event_id": event_id,
                "observations": [{"subject": f"hypothesis:{selected['hypothesis_id']}", "value": {"returncode": result["returncode"], "stdout": str(result.get("stdout", ""))[:MAX_TEXT_BYTES]}}],
                "receipt": {"clock_domain": "self-study-logical", "time": float(generation + 1), "uncertainty": 0.0},
                "source": {"kind": "self-study-probe", "source_digest": self.workspace_index["content_sha256"]},
            },
            operation_label=f"self-study:observe:{selected['hypothesis_id']}",
        )
        prediction_id = f"self-study-assessment:{selected['hypothesis_id']}"
        actual = {"returncode": result["returncode"], "stdout": str(result.get("stdout", ""))[:MAX_TEXT_BYTES]}
        predicted = {"returncode": selected["expected"].get("returncode", result["returncode"]), "stdout": selected["expected"].get("stdout_contains", actual["stdout"])}
        self.field_memory.semantic(
            {
                "operation": "register",
                "operation_id": self._semantic_id("prediction", selected["hypothesis_id"]),
                "record_id": prediction_id,
                "kind": "Assessment",
                "status": "active",
                "epistemic_kind": "observed",
                "payload": {"purpose": "prediction", "hypothesis_id": selected["hypothesis_id"], "prediction_semantics": "constraint-set", "alternatives": [{"values": predicted}], "source_digest": self.workspace_index["content_sha256"]},
            },
            operation_label=f"self-study:prediction:{selected['hypothesis_id']}",
        )
        field_assessment = self.field_memory.semantic(
            {
                "operation": "assess-prediction",
                "operation_id": self._semantic_id("assess", observation["observation_id"]),
                "prediction_id": prediction_id,
                "event_id": event_id,
                "actual": actual,
                "source": {"source_digest": self.workspace_index["content_sha256"]},
            },
            operation_label=f"self-study:assess:{selected['hypothesis_id']}",
        )
        assessment["field_assessment"] = field_assessment.get("result")
        curiosity = self.field_memory.semantic(
            {
                "operation": "autonomous-curiosity",
                "operation_id": self._semantic_id("curiosity", observation["observation_id"]),
                "goal": {"kind": "self-study", "reference": prediction_id},
                "max_goals": 4,
                "min_error": 0.0,
            },
            operation_label=f"self-study:curiosity:{selected['hypothesis_id']}",
        )
        assessment["curiosity"] = curiosity.get("result")
        # Resolve the consumed obligation through the field; this is not JSON
        # state and prevents a confirmed probe from being selected forever.
        self.field_memory.semantic(
            {
                "operation": "register",
                "operation_id": self._semantic_id("resolve", selected["hypothesis_id"]),
                "record_id": f"self-study-obligation:{selected['hypothesis_id']}",
                "kind": "Obligation",
                "status": "resolved",
                "epistemic_kind": "assessed",
                "payload": {"purpose": "prediction", "state": "resolved", "hypothesis_id": selected["hypothesis_id"], "assessment_status": assessment["status"], "loss": assessment["prediction_error"]},
            },
            operation_label=f"self-study:resolve:{selected['hypothesis_id']}",
        )
        field_selection["operation_ids"] = [
            field_selection["operation_id"],
            self._semantic_id("observe", observation["observation_id"]),
            self._semantic_id("prediction", selected["hypothesis_id"]),
            self._semantic_id("assess", observation["observation_id"]),
            self._semantic_id("curiosity", observation["observation_id"]),
            self._semantic_id("resolve", selected["hypothesis_id"]),
        ]
        field_selection["record_refs"] = [
            f"self-study-obligation:{selected['hypothesis_id']}",
            f"self-study-assessment:{selected['hypothesis_id']}",
            event_id,
        ]
        state_out = {"schema": STATE_SCHEMA, "field_owner": "CassiMindField", "workspace_revision_id": state["workspace_revision_id"], "adaptive_state": "resident-field-only", "field_variant": self.field_variant}
        receipt = self._make_receipt(generation + 1, state_out, [observation], [assessment], field_selection=field_selection)
        self._commit(generation + 1, state_out, receipt)
        return {"schema": SCHEMA, "status": "complete", "generation": generation + 1, "observations": [observation], "assessments": [assessment], "goals": [], "receipt": receipt}

    def replay(self, generation: int | None = None) -> dict[str, Any]:
        current_generation, _, receipt = self._load_current()
        target = current_generation if generation is None else int(generation)
        old = _read_json(self._generation_path(target) / "receipt.json")
        for observation in old.get("observations", []):
            selected = observation.get("hypothesis")
            if not isinstance(selected, Mapping):
                continue
            result = run_bounded_command(selected["command"], workspace=self.workspace, cwd=selected["cwd"], timeout_seconds=selected["timeout_seconds"])
            if _stable_result(result) != _stable_result(observation["result"]):
                raise MutationRejected("deterministic replay diverged")
        return {"status": "PASS", "generation": target, "receipt_sha256": old["content_sha256"], "current_generation": current_generation, "current_receipt_sha256": receipt["content_sha256"]}

def verify_receipt(path: str | os.PathLike[str], workspace: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Independently validate a receipt's self-digest and source-byte bindings."""
    receipt = _read_json(Path(path))
    _check_digest(receipt, "content_sha256", _stable_receipt(receipt))
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise MutationRejected("unsupported receipt schema")
    if workspace is not None:
        index = index_workspace(workspace)
        if index["workspace_revision_id"] != receipt.get("workspace_revision_id"):
            raise MutationRejected("source mutation changed workspace revision")
        by_path = {row["path"]: row for row in index["files"]}
        for source in receipt.get("source_files", []):
            current = by_path.get(source.get("path"))
            if current is None or current.get("source_sha256") != source.get("source_sha256") or current.get("source_revision_id") != source.get("source_revision_id"):
                raise MutationRejected(f"source binding changed: {source.get('path')}")
            for symbol in source.get("symbols", []):
                span = symbol.get("span", {})
                if not 0 <= int(span.get("byte_start", -1)) <= int(span.get("byte_end", -1)) <= int(current.get("byte_length", -1)):
                    raise MutationRejected(f"invalid source span: {source.get('path')}")
    return {"status": "PASS", "schema": receipt["schema"], "generation": receipt.get("generation"), "content_sha256": receipt["content_sha256"], "observations": len(receipt.get("observations", [])), "assessments": len(receipt.get("assessments", []))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--data-home", required=False, default=".cassimindfield-self-study")
    parser.add_argument("--hypothesis-json")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--verify-receipt")
    parser.add_argument("--allow-workspace-mutation", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_receipt:
            print(json.dumps(verify_receipt(args.verify_receipt, args.workspace), sort_keys=True))
            return 0
        runtime = SelfStudyRuntime(args.data_home, args.workspace, allow_workspace_mutation=args.allow_workspace_mutation)
        try:
            if args.replay:
                print(json.dumps(runtime.replay(), sort_keys=True))
                return 0
            if args.hypothesis_json:
                hypothesis = json.loads(Path(args.hypothesis_json).read_text(encoding="utf-8"))
                runtime.submit_hypothesis(hypothesis)
            result: dict[str, Any] = {"status": "idle"}
            for _ in range(max(0, min(int(args.cycles), 256))):
                result = runtime.run_cycle()
                if result.get("status") == "idle":
                    break
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        finally:
            runtime.close()
    except (SelfStudyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
