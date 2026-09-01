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

import verify_cassi_qi_flow as independent
import verify_cassi_qi_transport as transport


_ROOT = Path(__file__).resolve().parent
_RUN_ID = "a3ce1adc2804b2d34e5ed54ac990839fff1ca5ffea5d5cd292540e2339670527"
_ARTIFACT = _ROOT / "_diag" / "cassi-qi-flow-w3-periodic-fft2-final" / _RUN_ID


def _read_json(path: Path) -> dict[str, Any]:
    value = transport._load(path)
    if not isinstance(value, dict):
        raise AssertionError(f"not a canonical JSON mapping: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(transport._canonical(value))


def _reseal_index(root: Path) -> None:
    relative = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != "index.json"
    ]
    objects: list[dict[str, Any]] = []
    for name in sorted(relative, key=lambda value: value.encode("utf-8")):
        raw = (root / name).read_bytes()
        objects.append(
            {
                "path": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    index = _read_json(root / "index.json")
    index["objects"] = objects
    core = {key: value for key, value in index.items() if key not in ("self_sha256", "run_id")}
    index["run_id"] = transport._hash_object(transport._ARTIFACT_DOMAIN, core)
    without_self = {key: value for key, value in index.items() if key != "self_sha256"}
    index["self_sha256"] = transport._hash_object(transport._ARTIFACT_SCHEMA, without_self)
    _write_json(root / "index.json", index)


class G3VerifierTests(unittest.TestCase):
    def test_published_g3_artifact_verifies_and_is_w3_only(self) -> None:
        result = independent.verify_g3_transport(_ARTIFACT)
        self.assertEqual(result["status"], "PASS_W3_G3")
        self.assertEqual(result["schema"], "cassi.qi-flow-w3-periodic-fft2-verification.v1")
        self.assertEqual(result["run_id"], _RUN_ID)
        index = _read_json(_ARTIFACT / "index.json")
        self.assertEqual(result["parent_w2_run_id"], index["parent_w2_run_id"])
        stages = _read_json(_ARTIFACT / "run-spec" / "w3-stage-schedule.json")["stages"]
        self.assertEqual(stages[3]["mode"], "inactive-w3")
        self.assertEqual(stages[3]["writes"], ["conversion_placeholder"])
        runtime = _read_json(_ARTIFACT / "results" / "runtime.json")
        self.assertEqual(runtime["seeded_diagnostics"]["inactive_tail_nonzero"], 0)

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
        self.assertEqual(result["status"], "PASS_W3_G3")

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
            runtime_path = probe / "results" / "runtime.json"
            runtime = _read_json(runtime_path)
            runtime["seeded_diagnostics"]["pre_energy"] = "f64:0000000000000000"
            _write_json(runtime_path, runtime)
            _reseal_index(probe)
            with self.assertRaisesRegex(transport.W3VerificationError, "independent diagnostic mismatch"):
                independent.verify_g3_transport(probe)

    def test_resealed_artifact_mutation_controls_reject_all_declared_boundaries(self) -> None:
        def mutate_raw_state(root: Path) -> None:
            target = root / "fixtures" / "seeded-candidate.f64le"
            raw = bytearray(target.read_bytes())
            raw[0] ^= 0x01
            target.write_bytes(bytes(raw))

        def mutate_stage_schedule(root: Path) -> None:
            target = root / "run-spec" / "w3-stage-schedule.json"
            schedule = _read_json(target)
            schedule["stages"].reverse()
            core = {key: value for key, value in schedule.items() if key != "stage_schedule_sha256"}
            schedule["stage_schedule_sha256"] = transport._hash_object(transport._STAGE_SCHEDULE_SCHEMA, core)
            _write_json(target, schedule)
            index_path = root / "index.json"
            index = _read_json(index_path)
            index["stage_schedule_sha256"] = schedule["stage_schedule_sha256"]
            _write_json(index_path, index)

        def mutate_transport_semantic(root: Path) -> None:
            target = root / "run-spec" / "w3-profile.json"
            profile = _read_json(target)
            dynamics = profile["semantic"]["dynamics"]
            dynamics["c_D_m_per_s"][0] = (
                "f64:3fe0000000000000" if dynamics["c_D_m_per_s"][0] != "f64:3fe0000000000000" else "f64:3fd0000000000000"
            )
            profile["semantic_sha256"] = transport._hash_object(
                profile["semantic"].get("schema"), profile["semantic"]
            )
            profile["profile_sha256"] = transport._hash_object(
                profile.get("schema"), {key: value for key, value in profile.items() if key != "profile_sha256"}
            )
            _write_json(target, profile)
            index_path = root / "index.json"
            index = _read_json(index_path)
            index["semantic_sha256"] = profile["semantic_sha256"]
            index["profile_sha256"] = profile["profile_sha256"]
            _write_json(index_path, index)

        def mutate_indexed_source(root: Path) -> None:
            target = root / "run-spec" / "sources" / "cassi_qi_field.py"
            target.write_bytes(target.read_bytes() + b"\n")

        cases = (
            (mutate_raw_state, "bytes/hash mismatch"),
            (mutate_stage_schedule, "frozen split schedule"),
            (mutate_transport_semantic, "independent replay mismatch"),
            (mutate_indexed_source, "source snapshot is not current"),
        )
        for mutation, boundary in cases:
            with self.subTest(mutation=mutation.__name__), tempfile.TemporaryDirectory(prefix="g3-control-") as directory:
                probe = Path(directory) / "artifact"
                shutil.copytree(_ARTIFACT, probe)
                mutation(probe)
                _reseal_index(probe)
                with self.assertRaisesRegex(transport.W3VerificationError, boundary):
                    independent.verify_g3_transport(probe)


if __name__ == "__main__":
    unittest.main()
