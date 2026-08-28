from __future__ import annotations

import ast
import hashlib
import shutil
import tempfile
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from typing import Any

from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads
import verify_cassi_qi_flow as independent


_ROOT = Path(__file__).resolve().parent
_RUN_ID = "071107f82e9316c525e9b9ed0553d7901be4ea1666a2bbfdba78468ea58c8d55"
_ARTIFACT = _ROOT / "_diag" / "cassi-qi-flow-w3-final" / _RUN_ID


def _read_json(path: Path) -> dict[str, Any]:
    value = canonical_json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise AssertionError(f"not a canonical JSON mapping: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _reseal_index(root: Path) -> None:
    candidate_path = root / "gates" / "g03-transport" / "transport.json"
    candidate = _read_json(candidate_path)
    candidate_without_self = dict(candidate)
    candidate_without_self.pop("self_sha256")
    candidate["self_sha256"] = canonical_hash(
        candidate_without_self,
        independent.W3_G3_CANDIDATE_SCHEMA,
    )
    _write_json(candidate_path, candidate)

    status_path = root / "gates" / "g03-transport" / "status.json"
    status = _read_json(status_path)
    status["candidate_sha256"] = candidate["self_sha256"]
    _write_json(status_path, status)

    objects: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.relative_to(root).as_posix() != "index.json":
            raw = path.read_bytes()
            objects.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "byte_count": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    index = _read_json(root / "index.json")
    index["objects"] = objects
    index["object_count"] = len(objects)
    material = {
        "schema": independent.W3_ARTIFACT_DOMAIN,
        "parents": index["parents"],
        "objects": objects,
        "contract_root_sha256": index["contract_root_sha256"],
        "profile_sha256": index["profile_sha256"],
    }
    index["run_id"] = canonical_hash(material, independent.W3_ARTIFACT_DOMAIN)
    index_without_self = dict(index)
    index_without_self.pop("self_sha256")
    index["self_sha256"] = canonical_hash(index_without_self, independent.W3_RUN_INDEX_SCHEMA)
    _write_json(root / "index.json", index)


class G3VerifierTests(unittest.TestCase):
    def test_published_g3_artifact_verifies_and_is_w3_only(self) -> None:
        result = independent.verify_g3_transport(_ARTIFACT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["gate"], "G3")
        self.assertEqual(result["run_id"], _RUN_ID)
        candidate = _read_json(_ARTIFACT / "gates" / "g03-transport" / "transport.json")
        self.assertEqual(candidate["parent_w2"]["run_id"], independent._W3_PARENT_W2["run_id"])
        self.assertEqual(candidate["stage_schedule"]["stages"][3]["mode"], "inactive-w5-unavailable")
        self.assertEqual(candidate["operator_evidence"]["density_conversion"], "inactive-w5-unavailable")
        self.assertEqual(candidate["operator_evidence"]["advection"], "unavailable")

    def test_deprecated_verifier_aliases_are_absent(self) -> None:
        deprecated = (
            "W3_" + "G3_TRANSPORT_CANDIDATE_SCHEMA",
            "W3_" + "ARTIFACT_SCHEMA",
            "W3_" + "INDEX_SCHEMA",
        )
        self.assertTrue(all(not hasattr(independent, name) for name in deprecated))

    def test_verifier_validates_without_runtime_module_imports(self) -> None:
        denied = {
            "cassi_qi_field": None,
            "cassi_qi_transport": None,
            "cassi_qi_geometry": None,
            "cassi_qi_profile": None,
        }
        with patch.dict(sys.modules, denied):
            result = independent.verify_g3_transport(_ARTIFACT)
        self.assertEqual(result["status"], "PASS")

    def test_live_runtime_and_builders_do_not_import_the_verifier(self) -> None:
        prohibited: list[str] = []
        for path in sorted(_ROOT.glob("cassi_qi_*.py")) + sorted(_ROOT.glob("run_cassi_qi_*.py")):
            if path.name.startswith("test_") or path.name == "verify_cassi_qi_flow.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            for node in ast.walk(tree):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
                )
                if any(name == "verify_cassi_qi_flow" for name in names):
                    prohibited.append(path.name)
                    break
        self.assertEqual(prohibited, [])

    def test_resealed_diagnostic_forgery_fails_raw_recomputation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g3-verifier-") as directory:
            probe = Path(directory) / "artifact"
            shutil.copytree(_ARTIFACT, probe)
            candidate_path = probe / "gates" / "g03-transport" / "transport.json"
            candidate = _read_json(candidate_path)
            candidate["diagnostics"]["simple"]["initial_d_l2"] = independent.W3_ZERO
            _write_json(candidate_path, candidate)
            _reseal_index(probe)
            with self.assertRaises(independent.VerificationError):
                independent.verify_g3_transport(probe)

    def test_resealed_artifact_mutation_controls_reject_all_declared_boundaries(self) -> None:
        def mutate_raw_state(root: Path) -> None:
            target = root / "fixtures" / "final-state.bin"
            raw = bytearray(target.read_bytes())
            raw[0] ^= 0x01
            target.write_bytes(raw)

        def mutate_stage_schedule(root: Path) -> None:
            target = root / "gates" / "g03-transport" / "transport.json"
            candidate = _read_json(target)
            candidate["stage_schedule"]["stages"].reverse()
            _write_json(target, candidate)

        def mutate_transport_semantic(root: Path) -> None:
            target = root / "run-spec" / "w3-transport-semantic.json"
            semantic = _read_json(target)
            semantic["operator_semantic_sha256"] = "0" * 64
            _write_json(target, semantic)

        def mutate_indexed_source(root: Path) -> None:
            target = root / "run-spec" / "sources" / "cassi_qi_field.py"
            target.write_bytes(target.read_bytes() + b"\n")

        for mutation in (
            mutate_raw_state,
            mutate_stage_schedule,
            mutate_transport_semantic,
            mutate_indexed_source,
        ):
            with self.subTest(mutation=mutation.__name__), tempfile.TemporaryDirectory(prefix="g3-control-") as directory:
                probe = Path(directory) / "artifact"
                shutil.copytree(_ARTIFACT, probe)
                mutation(probe)
                _reseal_index(probe)
                with self.assertRaises(independent.VerificationError):
                    independent.verify_g3_transport(probe)


if __name__ == "__main__":
    unittest.main()
