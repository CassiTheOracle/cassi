"""Focused W15A/W15B/G15A/G15B contract tests."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import run_cassi_qi_release as release
import run_cassi_qi_validation as validation
import verify_cassi_qi_requirements_registry as requirements


class ReleaseHashTests(unittest.TestCase):
    def test_authoritative_length_framed_hash(self) -> None:
        domain = "example.schema.v1"
        value = {"b": 2, "a": 1}
        domain_bytes = domain.encode()
        payload = release.canonical_json_bytes(value)
        expected = hashlib.sha256(len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload).hexdigest()
        self.assertEqual(release.canonical_hash(value, domain), expected)
        self.assertNotEqual(release.canonical_hash(value, domain), release.canonical_hash({"a": 1, "b": 3}, domain))

    def test_candidate_self_hash_mutation_is_detected(self) -> None:
        result = release.build_candidate_result(
            candidate_id="a" * 64,
            run_index_sha256="b" * 64,
            profile_sha256="c" * 64,
            contract_root_sha256="d" * 64,
            semantic_subhashes=[{"name": name, "sha256": "e" * 64} for name in release.SEMANTIC_PARENT_NAMES],
            gate_outcomes=[{"artifact_sha256": "f" * 64, "failure_code": None, "gate_id": "G0", "status": "passed"}],
            artifacts=[{"artifact_key": "x.json", "schema": "cassi.qi-flow-artifact.v1", "sha256": "1" * 64}],
        )
        self.assertEqual(result["self_sha256"], release._self_hash(result, release.SCHEMA_CANDIDATE_RESULT))
        tampered = dict(result)
        tampered["final_release_ready"] = not tampered["final_release_ready"]
        self.assertNotEqual(tampered["self_sha256"], release._self_hash(tampered, release.SCHEMA_CANDIDATE_RESULT))

    def test_descendant_closure_is_transitive_and_exact(self) -> None:
        manifest = {
            "nodes": [{"id": item} for item in ("root", "child", "grandchild", "sibling")],
            "edges": [{"from": "root", "to": "child"}, {"from": "child", "to": "grandchild"}, {"from": "root", "to": "child"}],
        }
        self.assertEqual(release.dependency_descendant_closure(manifest, ["root"]), ("child", "grandchild", "root"))
        with self.assertRaises(release.ReleaseError):
            release.dependency_descendant_closure(manifest, ["unknown"])


class RunnerTests(unittest.TestCase):
    def test_candidate_missing_inputs_is_blocked_and_writes_typed_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outcome = release.run_candidate(root=Path(directory))
            self.assertEqual(outcome["status"], "BLOCKED")
            self.assertFalse(outcome["engineering_ready"])
            candidate = json.loads(outcome["candidate_result_path"].read_text(encoding="utf-8"))
            board = json.loads(outcome["board_path"].read_text(encoding="utf-8"))
            self.assertEqual(candidate["schema"], release.SCHEMA_CANDIDATE_RESULT)
            self.assertEqual(board["schema"], release.SCHEMA_ENGINEERING_BOARD)
            self.assertEqual(candidate["self_sha256"], release._self_hash(candidate, release.SCHEMA_CANDIDATE_RESULT))
            self.assertFalse(board["final_release_ready"])
            self.assertTrue(outcome["blockers"])

    def test_validation_retains_raw_bytes_and_marks_missing_gate_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outcome = validation.run_validation(root=Path(directory), gates=("G0",), commands={}, mode="development")
            self.assertEqual(outcome["status"], "BLOCKED")
            status_path = Path(directory) / "gates" / "g0" / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "blocked")
            self.assertEqual(status["failure_code"], "MISSING_VALIDATION_COMMAND")
            with self.assertRaises(validation.ValidationError):
                validation.run_validation(root=Path(directory), gates=("G0",), commands={}, mode="release-candidate")

    def test_validation_executes_command_in_development_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = {"G0": {"argv": [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'raw-proof')"]}}
            outcome = validation.run_validation(root=Path(directory), gates=("G0",), commands=command, mode="development")
            self.assertEqual(outcome["status"], "PASS")
            raw = Path(directory) / "gates" / "g0" / "raw" / "stdout.bin"
            self.assertEqual(raw.read_bytes(), b"raw-proof")
            status = json.loads((Path(directory) / "gates" / "g0" / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "passed")


class RequirementsVerifierTests(unittest.TestCase):
    def test_registry_requires_exact_once_and_all_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            registry = docs / "13-requirements-registry.md"
            (docs / "00-foundations.md").write_text("# Foundations\nQI-TEST-001\n", encoding="utf-8")
            registry.write_text("| Requirement | Owner | Package | Gate | Artifact | Failure |\n|---|---|---|---|---|---|\n| QI-TEST-001 | 00-foundations.md | W1 | G1 | artifact.json | blocked |\n| QI-TEST-001 | 00-foundations.md | W1 | G1 | artifact.json | blocked |\n", encoding="utf-8")
            owner_map = root / "owner.md"
            owner_map.write_text("### W1\n### G1\n", encoding="utf-8")
            gates = root / "gates"
            (gates / "g1").mkdir(parents=True)
            root_plan = root / "CASSI-QI-FLOW-INTELLIGENCE-IMPLEMENTATION-PLAN.md"
            root_plan.write_text("# Pointer\n[00-foundations.md](docs/00-foundations.md)\n", encoding="utf-8")
            result = requirements.verify_requirements_registry(registry_path=registry, docs_path=docs, gates_path=gates, owner_map_path=owner_map, root_plan_path=root_plan)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(error.startswith("REQUIREMENT_NOT_EXACTLY_ONCE") for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
