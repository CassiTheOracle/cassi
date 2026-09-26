#!/usr/bin/env python3
"""Independently verify a CassiFI + local-Qwen realistic-workcase campaign.

This verifier only reads campaign artifacts and the persisted CassiFI state.  It
never imports the campaign runner, starts a model/server, repairs artifacts, or
trusts analysis.json as its source of measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "cassi.field-qwen.realistic-workcases.v1"
PROTOCOL_SCHEMA = "cassi.field-qwen.realistic-workcases.protocol.v1"
MEMORY_SCHEMA = "cassi.field-qwen.memory-record.v2"
RECALL_SCHEMA = "cassi.field-qwen.recall.v2"
OWNERSHIP_SCHEMA = "cassi.field-qwen.ownership.v2"
SUSTAINED_DISTRACTORS = 96
# Frozen current-campaign anchor.  The record and case sets remain fixed; the
# criteria-only digest change records the migration to the bounded regional
# cognition.field contract.
EXPECTED_PROTOCOL_SHA256 = "8f6442f61b5d8b1987f5753366e2f2d182818e25093979f8a78186d909aa7a46"


class VerificationFailure(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite_json(value: Any, path: str = "value") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationFailure(f"non-finite number at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            finite_json(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite_json(item, f"{path}[{index}]")


def load_json(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        finite_json(value, str(path))
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, VerificationFailure) as exc:
        raise VerificationFailure(f"cannot load valid JSON {path}: {exc}") from exc


def parse_json_answer(text: Any) -> tuple[Any | None, str | None]:
    if not isinstance(text, str):
        return None, "raw_output is not a string"
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


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def same(a: Any, b: Any) -> bool:
    return a == b


class Verifier:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        self.checks: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.protocol: dict[str, Any] | None = None
        self.prepare: dict[str, Any] | None = None
        self.baseline: dict[str, Any] | None = None
        self.field: dict[str, Any] | None = None
        self.analysis: dict[str, Any] | None = None
        self.protocol_sha256: str | None = None
        self.active_sources: dict[str, Any] = {}
        self.learning_by_source: dict[str, list[Mapping[str, Any]]] = {}
        self.active_revision_ids: set[str] = set()

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        row = {"name": name, "passed": bool(condition)}
        if detail:
            row["detail"] = detail
        self.checks.append(row)
        if not condition:
            self.errors.append(f"{name}: {detail or 'invariant failed'}")
        return condition

    def load(self) -> None:
        if not self.run_dir.is_dir():
            raise VerificationFailure(f"--run-dir is not a directory: {self.run_dir}")
        names = ["protocol", "prepare", "baseline", "field", "analysis"]
        loaded: dict[str, Any] = {}
        for name in names:
            loaded[name] = load_json(self.run_dir / f"{name}.json")
        for name in names:
            self.check(f"artifact:{name}.json:object", isinstance(loaded[name], dict))
        self.protocol = loaded["protocol"].get("protocol")
        self.prepare = loaded["prepare"]
        self.baseline = loaded["baseline"]
        self.field = loaded["field"]
        self.analysis = loaded["analysis"]
        envelope = loaded["protocol"]
        if not isinstance(self.protocol, dict):
            raise VerificationFailure("protocol.json.protocol is not an object")
        self.protocol_sha256 = digest_value(self.protocol)
        self.check("protocol:canonical-sha256", envelope.get("protocol_sha256") == self.protocol_sha256,
                   f"envelope={envelope.get('protocol_sha256')!r}, recomputed={self.protocol_sha256}")
        self.check("protocol:frozen-campaign-anchor", self.protocol_sha256 == EXPECTED_PROTOCOL_SHA256,
                   f"expected={EXPECTED_PROTOCOL_SHA256}, actual={self.protocol_sha256}")
        self.check("protocol:envelope-keys", set(envelope) == {"protocol", "protocol_sha256"})
        self.check("protocol:schema", self.protocol.get("schema") == PROTOCOL_SCHEMA)
        self.check("protocol:sustained-distractors", self.protocol.get("sustained_distractors") == SUSTAINED_DISTRACTORS)
        cases = self.protocol.get("cases")
        records = self.protocol.get("records")
        self.check("protocol:cases-list", isinstance(cases, list) and bool(cases))
        self.check("protocol:records-list", isinstance(records, list) and bool(records))
        if not isinstance(cases, list) or not isinstance(records, list):
            raise VerificationFailure("protocol cases/records are not lists")
        case_ids = [row.get("id") for row in cases if isinstance(row, dict)]
        self.check("protocol:case-ids-unique", len(case_ids) == len(cases) == len(set(case_ids)))
        record_ids = [row.get("source_id") for row in records if isinstance(row, dict)]
        self.check("protocol:record-ids-present", len(record_ids) == len(records) and all(isinstance(x, str) and x for x in record_ids))
        self.check("protocol:record-count", len(records) == 117, f"records={len(records)}")
        self.check("protocol:case-count", len(cases) == 17, f"cases={len(cases)}")
        self.check("protocol:experience-record", isinstance(self.protocol.get("experience_record"), dict))

    def stage_identities(self) -> None:
        assert self.protocol_sha256 is not None
        assert self.prepare is not None and self.baseline is not None and self.field is not None
        stages = {"prepare": self.prepare, "baseline": self.baseline, "field": self.field}
        for name, value in stages.items():
            self.check(f"stage:{name}:schema", value.get("schema") == SCHEMA)
            self.check(f"stage:{name}:stage", value.get("stage") == ("prepare" if name == "prepare" else "arm"))
            expected_status = "complete"
            self.check(f"stage:{name}:status", value.get("status") == expected_status)
            self.check(f"stage:{name}:protocol", value.get("protocol_sha256") == self.protocol_sha256)
        self.check("stage:analysis:schema", self.analysis is not None and self.analysis.get("schema") == SCHEMA)
        self.check("stage:analysis:stage", self.analysis is not None and self.analysis.get("stage") == "analysis")
        self.check("stage:analysis:status", self.analysis is not None and self.analysis.get("status") == "verified")
        self.check("stage:analysis:protocol", self.analysis is not None and self.analysis.get("protocol_sha256") == self.protocol_sha256)
        analysis_ids = self.analysis.get("identities", {}) if self.analysis is not None else {}
        self.check("identity:analysis-model", analysis_ids.get("model_sha256") == self.baseline.get("model", {}).get("sha256"))
        self.check("identity:analysis-server", analysis_ids.get("server_binary_sha256") == self.baseline.get("server_binary", {}).get("sha256"))
        self.check("identity:analysis-cassifi", analysis_ids.get("cassifi_source_identity") == self.prepare.get("cassifi_source_identity"))
        self.check("stage:baseline:arm", self.baseline.get("arm") == "baseline")
        self.check("stage:field:arm", self.field.get("arm") == "field")

        model_b = self.baseline.get("model", {})
        model_f = self.field.get("model", {})
        server_b = self.baseline.get("server_binary", {})
        server_f = self.field.get("server_binary", {})
        self.check("identity:model-stage-equality", model_b == model_f,
                   "baseline and field model identity objects differ")
        self.check("identity:server-stage-equality", server_b == server_f,
                   "baseline and field server identity objects differ")
        self.check("identity:model-fields", all(key in model_b for key in ("path", "sha256", "served_model_id", "bytes")))
        self.check("identity:server-fields", all(key in server_b for key in ("path", "sha256", "bytes")))
        self._check_file_identity("model", model_b)
        self._check_file_identity("server_binary", server_b)

        ids = [value.get("cassifi_source_identity") for value in stages.values()]
        self.check("identity:cassifi-stage-equality", ids[0] == ids[1] == ids[2])
        self._check_cassifi_identity(ids[0])

    def _check_file_identity(self, label: str, identity: Any) -> None:
        if not isinstance(identity, Mapping):
            self.check(f"identity:{label}:object", False)
            return
        path = Path(str(identity.get("path", "")))
        exists = path.is_file()
        self.check(f"identity:{label}:path-exists", exists, str(path))
        if exists:
            actual_sha = digest_path(path)
            actual_bytes = path.stat().st_size
            self.check(f"identity:{label}:sha256", identity.get("sha256") == actual_sha,
                       f"artifact={identity.get('sha256')}, actual={actual_sha}")
            self.check(f"identity:{label}:bytes", identity.get("bytes") == actual_bytes,
                       f"artifact={identity.get('bytes')}, actual={actual_bytes}")
        self.check(f"identity:{label}:sha-format", isinstance(identity.get("sha256"), str) and len(identity["sha256"]) == 64)
        if label == "model":
            self.check("identity:model:served-id-basename", isinstance(identity.get("served_model_id"), str)
                       and Path(identity["served_model_id"]).name == path.name)

    def _check_cassifi_identity(self, identity: Any) -> None:
        if not isinstance(identity, Mapping):
            self.check("identity:cassifi:object", False)
            return
        files = identity.get("files")
        expected_files = {
            "cassi_alias_cut_field.py",
            "cassi_alias_exact_one_field.py",
            "cassi_alias_obstruction.py",
            "cassi_clause_field.py",
            "cassi_computation_policy.py",
            "cassi_constraint_dynamics.py",
            "cassi_constraint_field.py",
            "cassi_constraint_implication.py",
            "cassi_cubic_reduction.py",
            "cassi_field_atlas.py",
            "cassi_field_cognition.py",
            "cassi_field_computer.py",
            "cassi_field_owner.py",
            "cassi_field_program.py",
            "cassi_field_regions.py",
            "cassi_field_transceiver.py",
            "cassi_general_matched_field.py",
            "cassi_hybrid_inference.py",
            "cassi_learning_computer.py",
            "cassi_mixed_exact_one_field.py",
            "cassi_regional_catalog.py",
            "cassi_resonant_field.py",
            "cassi_temporal_field.py",
            "cassi_temporal_inquiry.py",
            "cassi_variational_field.py",
        }
        self.check(
            "identity:cassifi:file-map",
            isinstance(files, Mapping) and set(files) == expected_files,
        )
        self.check(
            "identity:cassifi:implementation",
            identity.get("implementation")
            == "field-intelligence-owner-plus-regional-learning-computer",
        )
        self.check("identity:cassifi:kernel", identity.get("kernel") == "cognition.field")
        if not isinstance(files, Mapping):
            return
        root = Path(str(identity.get("root", "")))
        actual: dict[str, str] = {}
        for name in sorted(files):
            path = root / name
            if path.is_file():
                actual[name] = digest_path(path)
            else:
                self.check(f"identity:cassifi:file:{name}:exists", False, str(path))
        if len(actual) == len(files):
            self.check("identity:cassifi:file-hashes", dict(files) == actual)
            self.check(
                "identity:cassifi:aggregate",
                identity.get("aggregate_sha256") == digest_value(actual),
            )

    def _row_ids(self, rows: Any) -> list[Any]:
        return [row.get("id") for row in rows] if isinstance(rows, list) and all(isinstance(row, Mapping) for row in rows) else []

    def arm_rows(self) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        assert self.protocol is not None and self.baseline is not None and self.field is not None
        cases = self.protocol["cases"]
        expected_ids = [row["id"] for row in cases]
        all_rows: list[list[Mapping[str, Any]]] = []
        for arm, artifact in (("baseline", self.baseline), ("field", self.field)):
            rows = artifact.get("rows")
            valid = isinstance(rows, list) and all(isinstance(row, Mapping) for row in rows)
            self.check(f"rows:{arm}:list", valid)
            if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
                continue
            typed_rows: list[Mapping[str, Any]] = [row for row in rows if isinstance(row, Mapping)]
            self.check(f"rows:{arm}:count", len(typed_rows) == len(cases), f"rows={len(typed_rows)}, cases={len(cases)}")
            self.check(f"rows:{arm}:ordering", self._row_ids(typed_rows) == expected_ids)
            all_rows.append(typed_rows)
            for workcase, row in zip(cases, typed_rows):
                prefix = f"row:{arm}:{workcase['id']}"
                self.check(prefix + ":identity", row.get("id") == workcase["id"] and row.get("category") == workcase["category"] and row.get("context") == workcase["context"])
                expected_ids_sorted = sorted(workcase.get("expected_source_ids", []))
                self.check(prefix + ":expected-source-ids", row.get("expected_source_ids") == expected_ids_sorted)
                self._check_row(prefix, workcase, row, arm)
        if len(all_rows) != 2:
            raise VerificationFailure("both complete arm row arrays are required")
        return all_rows[0], all_rows[1]

    def _check_row(self, prefix: str, workcase: Mapping[str, Any], row: Mapping[str, Any], arm: str) -> None:
        expected = workcase.get("expected")
        parsed, parse_error = parse_json_answer(row.get("raw_output"))
        self.check(prefix + ":parsed-output", same(row.get("parsed_output"), parsed))
        self.check(prefix + ":parse-error", row.get("parse_error") == parse_error)
        self.check(prefix + ":answer-equality", row.get("answer_pass") is (parsed == expected))
        selected = row.get("selected_source_ids")
        revisions = row.get("selected_source_revision_ids")
        self.check(prefix + ":selected-source-list", isinstance(selected, list) and selected == sorted(selected))
        self.check(prefix + ":revision-list", isinstance(revisions, list) and revisions == sorted(revisions))
        if arm == "baseline":
            self.check(prefix + ":baseline-empty-retrieval", selected == [] and revisions == [] and row.get("retrieval_exact") is None)
        else:
            expected_ids = sorted(workcase.get("expected_source_ids", []))
            self.check(prefix + ":retrieval-exact-recomputed", selected == expected_ids and row.get("retrieval_exact") is (selected == expected_ids))
            if isinstance(revisions, list):
                self.check(prefix + ":retrieval-revisions-active", all(revision in self.active_revision_ids for revision in revisions))
        self.check(prefix + ":prompt-hash", isinstance(row.get("prompt_sha256"), str) and len(row["prompt_sha256"]) == 64)
        self._check_nonnegative_int(prefix + ":recall-elapsed", row.get("recall_elapsed_ns"))
        self._check_nonnegative_int(prefix + ":qwen-elapsed", row.get("qwen_elapsed_ns"))
        usage = row.get("usage")
        self.check(prefix + ":usage-object", isinstance(usage, Mapping))
        if isinstance(usage, Mapping):
            for key in ("prompt_tokens", "completion_tokens"):
                self._check_nonnegative_int(prefix + ":usage:" + key, usage.get(key, 0))
        self.check(prefix + ":timings-object", isinstance(row.get("timings"), Mapping))
        self.check(prefix + ":server-receipt-field", "server_cassi_receipt" in row)

    def _check_nonnegative_int(self, name: str, value: Any) -> None:
        self.check(name, isinstance(value, int) and not isinstance(value, bool) and value >= 0, repr(value))

    def prepare_memory(self) -> None:
        assert self.protocol is not None and self.prepare is not None
        records = self.protocol["records"]
        learning = self.prepare.get("learning")
        self.check("prepare:learning-list", isinstance(learning, list))
        if not isinstance(learning, list):
            return
        self.check("prepare:learning-count", len(learning) == len(records))
        self.check("prepare:records-admitted", self.prepare.get("records_admitted") == len(records))
        distractor_count = sum("sustained-distractor" in row.get("labels", []) for row in records)
        self.check("prepare:distractor-count", distractor_count == SUSTAINED_DISTRACTORS and self.prepare.get("distractors_admitted") == distractor_count)
        self.learning_by_source: dict[str, list[Mapping[str, Any]]] = {}
        valid_learning = all(isinstance(entry, Mapping) for entry in learning)
        self.check("prepare:learning-entry-objects", valid_learning)
        if not valid_learning:
            return
        for record, entry in zip(records, learning):
            source_id = str(record.get("source_id", ""))
            self.learning_by_source.setdefault(source_id, []).append(entry)
        expected_counts: dict[str, int] = {}
        for record in records:
            source_id = str(record["source_id"])
            expected_counts[source_id] = expected_counts.get(source_id, 0) + 1
        self.check("prepare:learning-source-coverage", {key: len(value) for key, value in self.learning_by_source.items()} == expected_counts)
        for source_id, entries in self.learning_by_source.items():
            for index, entry in enumerate(entries):
                expected_status = "corrected" if index else "learned"
                self.check(f"prepare:learning:{source_id}:{index}:status", entry.get("status") == expected_status)
                self.check(f"prepare:learning:{source_id}:{index}:revision", isinstance(entry.get("source_revision_id"), str) and bool(entry["source_revision_id"]))
                self.check(f"prepare:learning:{source_id}:{index}:state", isinstance(entry.get("state_sha256"), str) and len(entry["state_sha256"]) == 64)
                self.check(f"prepare:learning:{source_id}:{index}:event", isinstance(entry.get("event_id"), str) and bool(entry["event_id"]))
                if expected_status == "learned":
                    self.check(f"prepare:learning:{source_id}:{index}:no-superseded", entry.get("superseded_revision_id") is None)
                else:
                    self.check(f"prepare:learning:{source_id}:{index}:superseded", entry.get("superseded_revision_id") == entries[index - 1].get("source_revision_id"))

        self._check_correction_recall("release_canary_before_correction", {"workspace": "atlas", "topic": "release"}, "atlas.release.canary", {"canary_percent": 7})
        self._check_correction_recall("release_canary_after_correction", {"workspace": "atlas", "topic": "release"}, "atlas.release.canary", {"canary_percent": 11})
        self._check_correction_recall("pager_before_correction", {"service": "catalog", "topic": "pager-owner"}, "catalog.pager.owner", {"owner": "Maya"})
        self._check_correction_recall("pager_after_correction", {"service": "catalog", "topic": "pager-owner"}, "catalog.pager.owner", {"owner": "Inez"})
        self._check_correction_recall("final_early", {"workspace": "long-run", "topic": "anchor-early"}, "long-run.anchor.early", {"launch_token": "A7-KAPPA-931"})
        self._check_correction_recall("final_late", {"workspace": "long-run", "topic": "anchor-late"}, "long-run.anchor.late", {"release_phrase": "northstar-velvet"})
        repeated = self.prepare.get("repeated_anchor_checks")
        self.check("prepare:repeated-controls-list", isinstance(repeated, list))
        if isinstance(repeated, list):
            self.check("prepare:repeated-controls-count", len(repeated) == 6)
            self.check("prepare:repeated-controls-steps", [x.get("after_distractors") for x in repeated] == [16, 32, 48, 64, 80, 96])
            for index, item in enumerate(repeated):
                anchor = item.get("anchor", {})
                unknown = item.get("unknown", {})
                anchor_records = anchor.get("records", [])
                self.check(f"prepare:control:{index}:early-anchor", [x.get("source_id") for x in anchor_records if isinstance(x, Mapping)] == ["long-run.anchor.early"] and [x.get("payload") for x in anchor_records if isinstance(x, Mapping)] == [{"launch_token": "A7-KAPPA-931"}])
                self.check(f"prepare:control:{index}:unknown-empty", unknown.get("records") == [])
        self.check("prepare:restart-exact", self.prepare.get("restart_exact") is True and self.prepare.get("state_after_restart") == self.prepare.get("state_before_restart"))
        post_records = self.prepare.get("post_restart_anchor", {}).get("records", [])
        self.check("prepare:post-restart-anchor", isinstance(post_records, list) and [row.get("source_id") for row in post_records if isinstance(row, Mapping)] == ["long-run.anchor.early"])
    def _check_correction_recall(self, name: str, context: Mapping[str, Any], source_id: str, payload: Mapping[str, Any]) -> None:
        assert self.prepare is not None
        recall = self.prepare.get("evolution_checks", {}).get(name)
        if not isinstance(recall, Mapping):
            self.check("prepare:evolution:" + name, False, "missing recall")
            return
        records = [row for row in recall.get("records", []) if isinstance(row, Mapping)]
        targets = [row for row in records if row.get("source_id") == source_id]
        entries = self.learning_by_source.get(source_id, [])
        self.check("prepare:evolution:" + name + ":context", recall.get("context") == dict(context))
        self.check("prepare:evolution:" + name + ":source", len(targets) == 1)
        self.check("prepare:evolution:" + name + ":payload", [row.get("payload") for row in targets] == [dict(payload)])
        selected = recall.get("selected_source_revision_ids", [])
        if entries:
            expected_revision = entries[-1]["source_revision_id"] if name.endswith("after_correction") or name in {"final_early", "final_late"} else entries[0]["source_revision_id"]
            superseded = {entry["source_revision_id"] for entry in entries if entry["source_revision_id"] != expected_revision}
            self.check("prepare:evolution:" + name + ":revision", expected_revision in selected)
            self.check("prepare:evolution:" + name + ":target-revision", [row.get("source_revision_id") for row in targets] == [expected_revision])
            self.check("prepare:evolution:" + name + ":not-superseded", superseded.isdisjoint(selected))
        else:
            self.check("prepare:evolution:" + name + ":revision", False, "source has no learning receipt")
    def memory_restart_and_rows(self, field_rows: Sequence[Mapping[str, Any]]) -> None:
        assert self.field is not None
        state_after = self.field.get("state_after")
        state_after_restart = self.field.get("state_after_restart")
        self.check("field:evaluation-restart-exact", self.field.get("restart_exact") is True and state_after_restart == state_after)
        experience = self.field.get("experience_restart")
        self.check("field:experience-restart-object", isinstance(experience, Mapping))
        if isinstance(experience, Mapping):
            self.check("field:experience-restart-exact", experience.get("restart_exact") is True and experience.get("state_after_restart") == experience.get("state_before_restart"))
        self.check("field:experience-learning", isinstance(self.field.get("learned_experience"), Mapping) and self.field["learned_experience"].get("status") in {"learned", "corrected"})
        self.check("field:final-state-receipt-object", isinstance(state_after, Mapping))
        # Revisions selected by rows must correspond to the active CassiFI source
        # map collected while opening the persisted owner below.
        for row in field_rows:
            selected = row.get("selected_source_ids", [])
            revisions = row.get("selected_source_revision_ids", [])
            mapped = sorted(self.active_sources[r].source_id for r in revisions if r in self.active_sources)
            self.check(f"field:revision-source-link:{row.get('id')}", mapped == selected)

    def open_memory_read_only(self) -> None:
        assert self.field is not None
        memory_path = self.run_dir / "field-memory"
        try:
            from cassi_field_qwen_workbench import CassiFieldWorkMemory
        except Exception as exc:
            raise VerificationFailure(f"cannot import CassiFieldWorkMemory: {exc}") from exc
        memory = None
        try:
            memory = CassiFieldWorkMemory(memory_path)
            persisted_state = memory.state_receipt()
            self.check(
                "memory:field-final-state-equality",
                persisted_state == self.field.get("state_after"),
                "persisted state differs from field.json state_after",
            )
            evidence = memory.owner.evidence
            self.active_revision_ids = set(evidence.active_revision_ids())
            self.active_sources = {
                revision_id: evidence.source(revision_id)
                for revision_id in self.active_revision_ids
            }
            self.check(
                "memory:active-revision-map",
                len(self.active_sources) == len(self.active_revision_ids),
            )
            self.check("memory:state-finite", persisted_state.get("all_finite") is True)
            bounds = persisted_state.get("semantic_bounds")
            self.check(
                "memory:regional-schema",
                persisted_state.get("semantic_state_schema")
                == "cassifi.semantic-cognition-state.v1"
                and persisted_state.get("kernel") == "cognition.field",
            )
            self.check(
                "memory:regional-profile",
                isinstance(persisted_state.get("profile_sha256"), str)
                and isinstance(persisted_state.get("catalog_sha256"), str)
                and isinstance(bounds, Mapping)
                and int(persisted_state.get("semantic_active_bindings", -1))
                <= int(bounds.get("max_records", -1))
                and int(persisted_state.get("semantic_transitions", -1))
                <= int(bounds.get("max_operations", -1)),
            )
            self.check(
                "memory:task-capacity",
                0 <= int(persisted_state.get("task_used_words", -1))
                <= int(persisted_state.get("task_capacity_words", 0))
                == 294912,
            )
        finally:
            if memory is not None:
                memory.close()

    def aggregates(self, baseline_rows: Sequence[Mapping[str, Any]], field_rows: Sequence[Mapping[str, Any]]) -> None:
        assert self.protocol is not None and self.analysis is not None and self.prepare is not None and self.field is not None and self.baseline is not None
        def summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
            elapsed = [int(row["qwen_elapsed_ns"]) for row in rows]
            return {
                "cases": len(rows), "passed": sum(bool(row["answer_pass"]) for row in rows),
                "parsed": sum(row["parse_error"] is None for row in rows),
                "qwen_elapsed_seconds": sum(elapsed) / 1e9,
                "qwen_median_seconds": statistics.median(elapsed) / 1e9,
                "prompt_tokens": sum(int(row.get("usage", {}).get("prompt_tokens", 0)) for row in rows),
                "completion_tokens": sum(int(row.get("usage", {}).get("completion_tokens", 0)) for row in rows),
            }
        def cats(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
            return {category: summary([row for row in rows if row["category"] == category]) for category in sorted({row["category"] for row in rows})}
        self.check("analysis:baseline-aggregate", self.analysis.get("baseline") == summary(baseline_rows))
        self.check("analysis:field-aggregate", self.analysis.get("field") == summary(field_rows))
        self.check("analysis:baseline-category-aggregate", self.analysis.get("baseline_by_category") == cats(baseline_rows))
        self.check("analysis:field-category-aggregate", self.analysis.get("field_by_category") == cats(field_rows))
        comparisons: list[dict[str, Any]] = []
        for workcase, base, field in zip(self.protocol["cases"], baseline_rows, field_rows):
            bp = bool(base["answer_pass"]); fp = bool(field["answer_pass"])
            transition = "gain" if not bp and fp else "regression" if bp and not fp else "stable_pass" if bp else "stable_fail"
            comparisons.append({"id": workcase["id"], "category": workcase["category"], "expected": workcase["expected"], "expected_source_ids": workcase["expected_source_ids"], "selected_source_ids": field["selected_source_ids"], "retrieval_exact": field["retrieval_exact"], "baseline_pass": bp, "field_pass": fp, "baseline_output": base["parsed_output"], "field_output": field["parsed_output"], "baseline_raw_output": base["raw_output"], "field_raw_output": field["raw_output"], "same_parsed_output": base["parsed_output"] == field["parsed_output"], "transition": transition})
        transitions = {
            "gains": sum(x["transition"] == "gain" for x in comparisons),
            "regressions": sum(x["transition"] == "regression" for x in comparisons),
            "stable_pass": sum(x["transition"] == "stable_pass" for x in comparisons),
            "stable_fail": sum(x["transition"] == "stable_fail" for x in comparisons),
            "changed_parsed_outputs": sum(not x["same_parsed_output"] for x in comparisons),
        }
        self.check("analysis:transitions", self.analysis.get("transitions") == transitions)
        self.check("analysis:comparisons", self.analysis.get("comparisons") == comparisons)
        memory_rows = [x for x in comparisons if x["expected_source_ids"]]
        independent_rows = [x for x in comparisons if not x["expected_source_ids"]]
        expected_memory = {"cases": len(memory_rows), "baseline_passed": sum(x["baseline_pass"] for x in memory_rows), "field_passed": sum(x["field_pass"] for x in memory_rows), "retrieval_exact": sum(x["retrieval_exact"] is True for x in memory_rows)}
        expected_independent = {"cases": len(independent_rows), "baseline_passed": sum(x["baseline_pass"] for x in independent_rows), "field_passed": sum(x["field_pass"] for x in independent_rows), "empty_retrieval_exact": sum(x["retrieval_exact"] is True for x in independent_rows)}
        self.check("analysis:memory-dependent-aggregate", self.analysis.get("memory_dependent") == expected_memory)
        self.check("analysis:memory-independent-aggregate", self.analysis.get("memory_independent") == expected_independent)
        repeated = self.prepare.get("repeated_anchor_checks", [])
        retention = isinstance(repeated, list) and len(repeated) == 6 and [x.get("after_distractors") for x in repeated] == [16, 32, 48, 64, 80, 96] and all(
            [r.get("source_id") for r in x.get("anchor", {}).get("records", [])] == ["long-run.anchor.early"] and x.get("unknown", {}).get("records") == []
            for x in repeated
        )
        expected_memory_summary = {
            "records_admitted_before_evaluation": self.prepare.get("records_admitted"),
            "sustained_distractors": self.prepare.get("distractors_admitted"),
            "repeated_anchor_checks": len(repeated) if isinstance(repeated, list) else 0,
            "repeated_retention_pass": retention,
            "prepare_restart_exact": self.prepare.get("restart_exact"),
            "evaluation_restart_exact": self.field.get("restart_exact"),
            "experience_restart_exact": self.field.get("experience_restart", {}).get("restart_exact"),
            "state_before_evaluation": self.field.get("state_before"),
            "state_after_evaluation": self.field.get("state_after"),
            "state_after_evaluation_restart": self.field.get("state_after_restart"),
            "correction_checks": self.prepare.get("evolution_checks"),
        }
        self.check("analysis:memory-restart-retention-summary", self.analysis.get("memory") == expected_memory_summary)
        self.check("analysis:all-retrieval-exact", all(x["retrieval_exact"] is True for x in memory_rows))
    def ownership_and_artifacts(self, baseline_rows: Sequence[Mapping[str, Any]], field_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        assert self.field is not None and self.prepare is not None and self.protocol_sha256 is not None and self.protocol is not None
        assert self.analysis is not None and self.baseline is not None
        self.check("ownership:baseline-no-receipt", self.baseline.get("ownership_receipt") is None)
        self.check("ownership:arm-row-parity", len(baseline_rows) == len(field_rows))
        receipt = self.field.get("ownership_receipt")
        self.check("ownership:receipt-object", isinstance(receipt, Mapping))
        if isinstance(receipt, Mapping):
            self.check("ownership:schema", receipt.get("schema") == OWNERSHIP_SCHEMA)
            self.check("ownership:intervention", receipt.get("intervention") == "off-graph-current-cassifi-work-memory")
            self.check("ownership:zero-native-displacement", all(receipt.get(key) == 0 for key in ("native_dynamic_state_bytes_removed", "native_ops_skipped", "native_layers_skipped", "native_output_rows_skipped")))
            self.check("ownership:unchanged-native-footprint", receipt.get("remaining_native_state_footprint") == "unchanged full Qwen context/KV path" and receipt.get("qwen_weight_bytes_touched_per_token") is None)
            self.check("ownership:field-boundary", receipt.get("qwen_generated_tokens") == sum(int(row.get("usage", {}).get("completion_tokens", 0)) for row in field_rows))
            decisions = receipt.get("field_owned_decisions", {})
            self.check("ownership:no-field-token-emission", decisions.get("token_emissions") == 0 and decisions.get("reasoning_steps") == 0)
            self.check("ownership:source-selection-count", decisions.get("source_revision_selections") == sum(len(row.get("selected_source_revision_ids", [])) for row in field_rows))
            self.check("ownership:durable-update-count", decisions.get("durable_record_updates") == self.field.get("state_after", {}).get("evidence_events"))
            self.check("ownership:state-link", receipt.get("field_state") == self.field.get("state_after"))
            self.check("ownership:claim-boundary", isinstance(receipt.get("claim_boundary"), str) and "Qwen owns the full native graph" in receipt["claim_boundary"])
            self.check("ownership:model-link", receipt.get("qwen_model_sha256") == self.field.get("model", {}).get("sha256"))
            self.check("ownership:cassifi-identity", receipt.get("cassifi_source_identity") == self.field.get("cassifi_source_identity"))
        artifacts: dict[str, Any] = {}
        for name in ("protocol.json", "prepare.json", "baseline.json", "field.json", "analysis.json", "representative-transcripts.txt", "capability-and-memory-evolution.png"):
            path = self.run_dir / name
            exists = path.is_file()
            self.check("artifact:" + name + ":exists", exists)
            if exists:
                data = path.read_bytes()
                self.check("artifact:" + name + ":nonempty", bool(data))
                artifacts[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                if name.endswith(".png"):
                    self.check("artifact:png:signature", data.startswith(b"\x89PNG\r\n\x1a\n"))
                if name.endswith(".txt"):
                    text = data.decode("utf-8", errors="replace")
                    self.check("artifact:transcript:case-coverage", all(row["id"] in text for row in self.protocol["cases"]))
                    self.check("artifact:transcript:prepared-count", f"Prepared records: {self.prepare.get('records_admitted')}" in text)
        return artifacts

    def run(self) -> dict[str, Any]:
        try:
            self.load()
            self.stage_identities()
            self.prepare_memory()
            self.open_memory_read_only()
            baseline_rows, field_rows = self.arm_rows()
            self.memory_restart_and_rows(field_rows)
            self.aggregates(baseline_rows, field_rows)
            artifacts = self.ownership_and_artifacts(baseline_rows, field_rows)
        except Exception as exc:
            self.errors.append(str(exc))
            artifacts = {}
        result = {
            "schema": SCHEMA,
            "stage": "independent-verification",
            "status": "verified" if not self.errors and all(row["passed"] for row in self.checks) else "failed",
            "run_dir": str(self.run_dir),
            "protocol_sha256": self.protocol_sha256,
            "checks": self.checks,
            "errors": self.errors,
            "artifacts": artifacts,
        }
        if self.run_dir.is_dir():
            atomic_json(self.run_dir / "independent-verification.json", result)
        print(json.dumps({"status": result["status"], "checks": len(self.checks), "failed": len(self.errors), "protocol_sha256": self.protocol_sha256}, sort_keys=True))
        return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = Verifier(args.run_dir).run()
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    if result["status"] != "verified":
        print("verification failed: " + "; ".join(result["errors"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
