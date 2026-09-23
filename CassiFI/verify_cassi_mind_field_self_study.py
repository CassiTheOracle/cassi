#!/usr/bin/env python3
"""Independent verifier for the field-owned CassiMindField self-study loop."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

RECEIPT_SCHEMA = "cassimindfield.field-observation-receipt.v1"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def run_cli(runtime: Path, args: list[str], *, expect: int = 0) -> tuple[int, str]:
    completed = subprocess.run([sys.executable, str(runtime), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if completed.returncode != expect:
        raise RuntimeError(f"runtime command returned {completed.returncode}, expected {expect}: {completed.stdout}\n{completed.stderr}")
    return completed.returncode, completed.stdout


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
    return value


def sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise AssertionError(f"{label} is not a SHA-256 digest")
    return value


def stable(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key not in {"content_sha256", "created_wall_ns", "wall_ns"}}


def field_state(field_home: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    for path in (root / "CassiQwen", root / "CassiFI"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from cassi_field_qwen_workbench import CassiFieldWorkMemory
    with CassiFieldWorkMemory(field_home) as memory:
        return dict(memory.state_receipt())


def fresh_agenda_lesion(field_home: Path) -> Mapping[str, Any]:
    root = Path(__file__).resolve().parents[1]
    for path in (root / "CassiQwen", root / "CassiFI"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from cassi_field_qwen_workbench import CassiFieldWorkMemory
    with CassiFieldWorkMemory(field_home) as memory:
        response = memory.semantic({"operation": "autonomous-agenda", "operation_id": "independent-lesion:self-study", "goal": {"kind": "self-study-probe", "objective": "reduce prediction error"}, "max_items": 4}, operation_label="independent-lesion:self-study")
        result = response.get("result", {})
        if not isinstance(result, Mapping):
            raise AssertionError("fresh-field agenda returned no result")
        return result


def mutate_field_and_require_rejection(runtime: Path, base: list[str], field_home: Path) -> None:
    files = [path for path in sorted(field_home.rglob("*")) if path.is_file() and path.suffix in {".json", ".bin", ".dat"}]
    if not files:
        raise AssertionError("no persisted field bytes found")
    target = next((path for path in files if any(word in path.name.lower() for word in ("state", "manifest", "checkpoint"))), files[0])
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\x00")
        completed = subprocess.run([sys.executable, str(runtime), *base, "--replay"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        output = completed.stdout + completed.stderr
        if completed.returncode == 0 or not any(token in output.lower() for token in ("digest", "mismatch", "invalid", "integrity", "checkpoint", "mutation", "jsondecode", "extra data")):
            raise AssertionError("persisted field mutation was not rejected")
    finally:
        target.write_bytes(original)
def mutate_generation_state_and_require_rejection(runtime: Path, base: list[str], state_path: Path) -> None:
    original = state_path.read_bytes()
    try:
        state = load(state_path)
        state["field_variant"] = "fresh"
        state_path.write_bytes(canonical(state) + b"\n")
        output = run_cli(runtime, [*base, "--replay"], expect=2)[1]
        if not any(token in output.lower() for token in ("digest", "pointer", "mismatch", "mutation", "invalid")):
            raise AssertionError("generation state mutation was not rejected")
    finally:
        state_path.write_bytes(original)


def verify_raw_receipt(path: Path) -> dict[str, Any]:
    receipt = load(path)
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise AssertionError("receipt schema mismatch")
    if sha(receipt.get("content_sha256"), "receipt digest") != digest(stable(receipt)):
        raise AssertionError("receipt content digest mismatch")
    if receipt.get("study_versions") != ["v13", "v14", "v15", "v16", "v17", "v18"]:
        raise AssertionError("v13-v18 study version contract is absent")
    observations = receipt.get("observations", [])
    assessments = receipt.get("assessments", [])
    if len(observations) != 1 or len(assessments) != 1:
        raise AssertionError("expected one observation and assessment")
    observation = observations[0]
    assessment = assessments[0]
    if observation.get("source_revision_id") != receipt.get("workspace_revision_id"):
        raise AssertionError("observation source revision mismatch")
    if not observation.get("source_refs") or not assessment.get("source_refs"):
        raise AssertionError("source byte references are absent")
    selection = receipt.get("field_selection")
    if not isinstance(selection, Mapping) or selection.get("schema") != "cassimindfield.field-selection.v3" or selection.get("method") != "semantic.autonomous-agenda":
        raise AssertionError("autonomous field selection evidence is absent")
    operation_ids = selection.get("operation_ids")
    record_refs = selection.get("record_refs")
    if not isinstance(operation_ids, list) or not operation_ids or not all(isinstance(item, str) and item for item in operation_ids):
        raise AssertionError("field operation IDs are absent")
    if not isinstance(record_refs, list) or len(record_refs) < 2:
        raise AssertionError("resident hypothesis/obligation record refs are absent")
    agenda = selection.get("agenda")
    if not isinstance(agenda, list) or not agenda:
        raise AssertionError("autonomous agenda did not expose an item")
    agenda_obligation = agenda[0].get("obligation", {}) if isinstance(agenda[0], Mapping) else {}
    if agenda_obligation.get("id") != f"self-study-obligation:{observation.get('hypothesis_id')}":
        raise AssertionError("field agenda selected an unexpected obligation")
    if not isinstance(selection.get("selected_candidate_id"), str) or selection["selected_candidate_id"] != observation.get("hypothesis_id"):
        raise AssertionError("field-selected hypothesis identity mismatch")
    state_in = sha(selection.get("field_state_in_sha256"), "selection input")
    state_out = sha(selection.get("field_state_out_sha256"), "selection output")
    if state_in == state_out:
        raise AssertionError("autonomous agenda did not advance field state")
    if assessment.get("status") != "PASS" or assessment.get("prediction_error") != 0:
        raise AssertionError("field prediction did not pass")
    field_assessment = assessment.get("field_assessment")
    if not isinstance(field_assessment, Mapping) or field_assessment.get("operation") != "assess-prediction":
        raise AssertionError("observable field assessment path is absent")
    curiosity = assessment.get("curiosity")
    if not isinstance(curiosity, Mapping) or curiosity.get("operation") != "autonomous-curiosity":
        raise AssertionError("observable field curiosity path is absent")
    if not isinstance(curiosity.get("status"), str) or not curiosity.get("status"):
        raise AssertionError("field curiosity status is absent")
    return receipt


def verify() -> dict[str, Any]:
    runtime = Path(__file__).resolve().parents[1] / "CassiMindField" / "self_study_runtime.py"
    with tempfile.TemporaryDirectory(prefix="cassimindfield-verify-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        data_home = root / "study"
        workspace.mkdir()
        (workspace / "main.py").write_text("VALUE = 7\n\ndef probe():\n    return VALUE\n", encoding="utf-8")
        (workspace / "test_main.py").write_text("from main import probe\nassert probe() == 7\n", encoding="utf-8")
        base = ["--workspace", str(workspace), "--data-home", str(data_home)]
        hypotheses = []
        for hypothesis_id in ("v13-smoke-a", "v13-smoke-b"):
            hypothesis = {"hypothesis_id": hypothesis_id, "claim": "bounded probe reports its field-owned source value", "command": [sys.executable, "-c", "print('probe-ok')"], "expected": {"returncode": 0, "stdout_contains": "probe-ok"}, "source_paths": ["main.py", "test_main.py"], "timeout_seconds": 5}
            path = root / f"{hypothesis_id}.json"
            path.write_bytes(canonical(hypothesis) + b"\n")
            hypotheses.append(path)
        run_cli(runtime, [*base, "--hypothesis-json", str(hypotheses[0]), "--cycles", "0"])
        run_cli(runtime, [*base, "--hypothesis-json", str(hypotheses[1]), "--cycles", "1"])
        pointer = load(data_home / "current.json")
        generation = int(pointer["generation"])
        receipt_path = data_home / "generations" / f"g{generation:04d}" / "receipt.json"
        state_path = data_home / "generations" / f"g{generation:04d}" / "state.json"
        receipt = verify_raw_receipt(receipt_path)
        selection = receipt["field_selection"]
        lesion = fresh_agenda_lesion(root / "fresh-field")
        lesion_items = lesion.get("agenda", [])
        if not isinstance(lesion_items, list) or any(
            isinstance(item, Mapping) and isinstance(item.get("obligation"), Mapping)
            for item in lesion_items
        ):
            raise AssertionError("fresh-field lesion resolved resident hypothesis records")
        if lesion.get("selected_candidate_id") is not None:
            raise AssertionError("fresh-field lesion selected a resident hypothesis")
        if not isinstance(lesion.get("status"), str) or not lesion.get("status"):
            raise AssertionError("fresh-field lesion did not return a declared status")
        reopened = field_state(data_home / "field")
        if reopened.get("state_sha256") != receipt.get("field_state_sha256"):
            raise AssertionError("reopened field state digest differs from receipt")
        counts = reopened.get("semantic_family_counts", {})
        if not isinstance(counts, Mapping) or sum(int(value) for value in counts.values()) <= 0:
            raise AssertionError("reopened field has no resident semantic records")
        state = load(state_path)
        if any(key in state for key in ("hypotheses", "goals", "agenda", "selection")):
            raise AssertionError("generation JSON contains adaptive selection state")
        mutate_generation_state_and_require_rejection(runtime, base, state_path)
        if not any("curiosity" in operation_id for operation_id in selection["operation_ids"]):
            raise AssertionError("autonomous curiosity path was not exercised")
        replay = json.loads(run_cli(runtime, [*base, "--replay"])[1])
        if replay.get("status") != "PASS" or replay.get("receipt_sha256") != receipt.get("content_sha256"):
            raise AssertionError("replay did not preserve selected result")
        original_source = (workspace / "main.py").read_bytes()
        (workspace / "main.py").write_bytes(original_source + b"\n# mutation control\n")
        try:
            output = run_cli(runtime, [*base, "--verify-receipt", str(receipt_path)], expect=2)[1]
            if "source mutation" not in output:
                raise AssertionError("source mutation rejection was not reported")
        finally:
            (workspace / "main.py").write_bytes(original_source)
        mutate_field_and_require_rejection(runtime, base, data_home / "field")
        mutated = dict(receipt)
        mutated["content_sha256"] = "0" * 64
        receipt_path.write_bytes(canonical(mutated) + b"\n")
        output = run_cli(runtime, [*base, "--verify-receipt", str(receipt_path)], expect=2)[1]
        if "content_sha256 mismatch" not in output:
            raise AssertionError("receipt mutation rejection was not reported")
        return {"status": "PASS", "schema": RECEIPT_SCHEMA, "receipt_sha256": receipt["content_sha256"], "generation": generation, "field_resident_records": "PASS", "autonomous_agenda": "PASS", "autonomous_curiosity": "PASS", "fresh_field_lesion": "ABSTAIN", "reopen_state": "PASS", "replay": "PASS", "persisted_field_mutation": "PASS", "source_mutation_control": "PASS", "receipt_mutation_control": "PASS", "model_call_observability": "NOT_EXPOSED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="compatibility flag")
    parser.parse_args()
    try:
        print(json.dumps(verify(), sort_keys=True))
        return 0
    except (AssertionError, OSError, RuntimeError, json.JSONDecodeError, ImportError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
