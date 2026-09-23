from __future__ import annotations
import hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest

from cassi_field_owner import FieldIntelligenceOwner, FieldIntelligenceSurface, RPC_SCHEMA

ROOT = Path(__file__).resolve().parent
RECEIPT = ROOT / "_diag" / "relational-planning" / "receipt.json"
RUNNER = ROOT / "run_cassi_relational_planning.py"
VERIFIER = ROOT / "verify_cassi_relational_planning.py"
SUBPROCESS_TIMEOUT_SECONDS = 300


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *cmd], cwd=cwd, text=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT_SECONDS)


def test_public_bridge_schema_rejects_goal_term(tmp_path: Path) -> None:
    with FieldIntelligenceOwner(tmp_path / "owner") as owner:
        surface = FieldIntelligenceSurface(owner)
        request = {
            "schema": RPC_SCHEMA,
            "request_id": "public-bridge-schema",
            "operation": "interpret_open_vocab",
            "params": {
                "operation_id": "public-bridge-schema",
                "utterance": "advance captain from base to harbor",
                "construction_ref": {
                    "kind": "Program",
                    "id": "test:construction",
                    "content_version": 1,
                },
                "template_ref": {
                    "kind": "Program",
                    "id": "test:template",
                    "content_version": 1,
                },
                "support_refs": [],
                "goal_term": {"kind": "record", "fields": {}},
            },
        }
        with pytest.raises(Exception) as exc:
            surface.handle(request)
        assert getattr(exc.value, "code", None) == "INVALID_REQUEST"



def test_canonical_receipt_owner_path_and_verifier() -> None:
    if not RECEIPT.is_file():
        pytest.fail("canonical receipt missing; run `python run_cassi_relational_planning.py --receipt _diag/relational-planning/receipt.json --data-home _diag/relational-planning/owner-current`")
    result = run([str(VERIFIER), "--receipt", str(RECEIPT), "--firing-mutations"])
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["status"] == "verified"
    assert len(report["firing_mutations"]) >= 10


def test_two_independent_builds_have_stable_content_digest(tmp_path: Path) -> None:
    a = tmp_path / "a.json"; b = tmp_path / "b.json"
    ra = run([str(RUNNER), "--receipt", str(a), "--data-home", str(tmp_path / "owner-a")])
    rb = run([str(RUNNER), "--receipt", str(b), "--data-home", str(tmp_path / "owner-b")])
    assert ra.returncode == 0, ra.stdout + ra.stderr
    assert rb.returncode == 0, rb.stdout + rb.stderr
    va = run([str(VERIFIER), "--receipt", str(a), "--compare", str(b)])
    assert va.returncode == 0, va.stdout + va.stderr
    left, right = json.loads(a.read_text()), json.loads(b.read_text())
    assert left["digest"]["content_sha256"] == right["digest"]["content_sha256"]
    assert hashlib.sha256(a.read_bytes()).hexdigest() != hashlib.sha256(b.read_bytes()).hexdigest() or a.read_bytes() == b.read_bytes()


def test_receipt_records_three_step_rebinding_and_zero_model() -> None:
    if not RECEIPT.is_file():
        pytest.fail("canonical receipt missing; run `python run_cassi_relational_planning.py --receipt _diag/relational-planning/receipt.json --data-home _diag/relational-planning/owner-current`")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    base = next(row for row in receipt["cases"] if row["case_id"] == "heldout_base")
    assert base["observed"]["completion"] is True
    assert base["trace"]["action_step_count"] >= 3
    assert base["trace"]["repaired_action_step_count"] >= 3
    assert base["trace"]["external_observation_count"] >= 1
    assert base["trace"]["repeated_variable_occurrences"] >= 2
    assert all(receipt["summary"][key] == 0 for key in ("model_calls", "qwen_calls", "fallback_calls", "host_search_calls"))


def test_firing_mutation_is_not_vacuous(tmp_path: Path) -> None:
    if not RECEIPT.is_file():
        pytest.fail("canonical receipt missing; run `python run_cassi_relational_planning.py --receipt _diag/relational-planning/receipt.json --data-home _diag/relational-planning/owner-current`")
    original = json.loads(RECEIPT.read_text())
    altered = tmp_path / "altered.json"
    original["summary"]["model_calls"] = 1
    altered.write_text(json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    result = run([str(VERIFIER), "--receipt", str(altered)])
    assert result.returncode != 0
    assert "digest" in result.stdout.lower()
