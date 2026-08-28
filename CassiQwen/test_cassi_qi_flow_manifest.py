from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class _Raises:
    @staticmethod
    @contextlib.contextmanager
    def raises(expected: type[BaseException], match: str | None = None):
        try:
            yield
        except expected as error:
            if match is not None and re.search(match, str(error)) is None:
                raise AssertionError(f"expected error matching {match!r}, got {error!r}") from error
        else:
            raise AssertionError(f"expected {expected.__name__} to be raised")


pytest = _Raises()

ROOT = Path(__file__).resolve().parent
BUILDER_PATH = ROOT / "run_cassi_qi_flow_manifest.py"
VERIFIER_PATH = ROOT / "verify_cassi_qi_flow_manifest.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_module("w0_builder_test", BUILDER_PATH)
verifier = load_module("w0_verifier_test", VERIFIER_PATH)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def bootstrap_project(tmp_path: Path, entry_body: str = "print('historical-runtime')\n") -> tuple[Path, Path, list[str]]:
    (tmp_path / "cassi-qi-language.json").write_bytes(b'{"mode_count":1}')
    (tmp_path / "run_cassi_qi_behavior_demo.py").write_text(entry_body, encoding="utf-8")
    history = tmp_path / "historical" / "qi-v2"
    command = [
        sys.executable,
        "-B",
        str(BUILDER_PATH),
        "--phase",
        "historical-bootstrap",
        "--source-root",
        str(tmp_path),
        "--historical-root",
        str(history),
        "--entrypoint",
        "run_cassi_qi_behavior_demo.py",
        "--config",
        "cassi-qi-language.json",
        "--wrapper-output-root",
        "_diag/w0-wrapper-output",
    ]
    return history, tmp_path / "_diag" / "w0-wrapper-output", command


def make_minimal_plan(root: Path) -> None:
    for name in builder.NORMATIVE_DOCUMENTS:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8", newline="")
    packages = "".join(f"### {identifier} — package {identifier}\n**Dependencies:** none\n\n" for identifier in sorted(builder.EXPECTED_PACKAGES))
    gates = "".join(f"### {identifier} — gate {identifier}\n**Work packages:** W0\n\n" for identifier in sorted(builder.EXPECTED_GATES))
    (root / "CassiFI/10-work-packages.md").write_text(packages, encoding="utf-8", newline="")
    (root / "CassiFI/11-validation-gates.md").write_text(gates, encoding="utf-8", newline="")
    (root / "CassiFI/13-requirements-registry.md").write_text(
        "| `QI-NUM-001` | `CassiFI/00-foundations.md` | W0 | G0 | `cassi.qi-flow-test.v1` |\n",
        encoding="utf-8",
        newline="",
    )


def test_rejects_duplicate_and_nonfinite_json(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"x":1,"x":2}')
    with pytest.raises(builder.ValidationError, match="duplicate JSON key"):
        builder.load_json(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_bytes(b'{"x":NaN}')
    with pytest.raises(builder.ValidationError, match="non-finite"):
        builder.load_json(nonfinite)


def test_transitive_relative_and_literal_dynamic_import_closure(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "main.py").write_text("from . import helper\nimport importlib\nimportlib.import_module('pkg.helper')\n", encoding="utf-8")
    config = tmp_path / "cassi-qi-language.json"
    config.write_bytes(b'{"mode_count":1}')
    closure, imports, refs = builder.execution_closure(tmp_path, package / "main.py", config)
    assert {path.relative_to(tmp_path).as_posix() for path in closure} == {"cassi-qi-language.json", "pkg/__init__.py", "pkg/main.py", "pkg/helper.py"}
    assert any(record["kind"] == "from-import" and record["expression"] == ".helper" for record in imports)
    assert any(record["kind"] == "dynamic-import" and record["expression"] == "pkg.helper" for record in imports)
    assert refs == []


def test_nonliteral_dynamic_import_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "entry.py"
    source.write_text("import importlib\nname = 'helper'\nimportlib.import_module(name)\n", encoding="utf-8")
    with pytest.raises(builder.ValidationError, match="dynamic import"):
        builder.analyze_python(tmp_path, source)


def test_config_escape_and_missing_reference_fail(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    missing.write_bytes(b'{"checkpoint":"absent.pt"}')
    with pytest.raises(builder.ValidationError, match="unresolved config file reference"):
        builder.config_references(tmp_path, missing)
    escaping = tmp_path / "escape.json"
    escaping.write_bytes(b'{"checkpoint":"../outside.pt"}')
    with pytest.raises(builder.ValidationError, match="escapes source root"):
        builder.config_references(tmp_path, escaping)


def test_checkpoint_discovery_proves_temporary_outputs_and_hashes_inputs(tmp_path: Path) -> None:
    config = tmp_path / "cassi-qi-language.json"
    config.write_bytes(b'{"mode_count":1}')
    temporary = tmp_path / "temporary.py"
    temporary.write_text(
        "import tempfile\nfrom pathlib import Path\nwith tempfile.TemporaryDirectory() as directory:\n    checkpoint = Path(directory) / 'ephemeral.pt'\n",
        encoding="utf-8",
    )
    discovered = builder.checkpoint_discovery(tmp_path, {temporary, config}, [])
    assert discovered["entries"] == []
    observation = discovered["literal_observations"][0]
    assert observation["classification"] == "runtime-created-temporary-output"
    assert observation["proof"]["temporary_directory_variable"] == "directory"
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint-bytes")
    concrete = tmp_path / "concrete.py"
    concrete.write_text("PATH = 'model.pt'\n", encoding="utf-8")
    discovered = builder.checkpoint_discovery(tmp_path, {concrete, config}, [])
    assert discovered["entries"][0]["sha256"] == hashlib.sha256(b"checkpoint-bytes").hexdigest()
    assert not discovered["empty_set_proof"]["is_empty"]


def test_checkpoint_escape_and_unresolved_literal_fail(tmp_path: Path) -> None:
    config = tmp_path / "cassi-qi-language.json"
    config.write_bytes(b'{"mode_count":1}')
    escaping = tmp_path / "escape.py"
    escaping.write_text("PATH = '../outside.pt'\n", encoding="utf-8")
    with pytest.raises(builder.ValidationError, match="escapes root"):
        builder.checkpoint_discovery(tmp_path, {escaping, config}, [])
    missing = tmp_path / "missing.py"
    missing.write_text("PATH = 'missing.pt'\n", encoding="utf-8")
    with pytest.raises(builder.ValidationError, match="unresolved reachable checkpoint"):
        builder.checkpoint_discovery(tmp_path, {missing, config}, [])


def test_historical_reopen_detects_snapshot_mutation(tmp_path: Path) -> None:
    history, _, command = bootstrap_project(tmp_path)
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    independent = subprocess.run([sys.executable, "-B", str(VERIFIER_PATH), "--root", str(tmp_path), "--historical-root", str(history)], capture_output=True, text=True)
    assert independent.returncode == 0, independent.stderr
    archived_entry = history / "source" / "run_cassi_qi_behavior_demo.py"
    archived_entry.write_text("print('tampered')\n", encoding="utf-8")
    reopened = subprocess.run(command, capture_output=True, text=True)
    assert reopened.returncode != 0
    assert "indexed object digest/count mismatch" in reopened.stderr


def test_wrapper_runs_under_optimized_python_and_rejects_escape(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text("MESSAGE = 'frozen-import'\n", encoding="utf-8")
    history, output_root, command = bootstrap_project(tmp_path, "import helper\nprint(helper.MESSAGE)\n")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    okay = subprocess.run(
        [sys.executable, "-O", "-B", str(history / "run_cassi_qi_behavior_demo.py"), "--manifest", str(history / "manifest.json"), "--config", str(history / "cassi-qi-language.json"), "--output", str(output_root / "good")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert okay.returncode == 0, okay.stderr
    assert "frozen-import" in okay.stdout
    escape = subprocess.run(
        [sys.executable, "-O", "-B", str(history / "run_cassi_qi_behavior_demo.py"), "--manifest", str(history / "manifest.json"), "--config", str(history / "cassi-qi-language.json"), "--output", str(tmp_path / "escape")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert escape.returncode != 0
    assert "output escapes" in escape.stderr


def test_wrapper_rejects_config_tamper_and_missing_archived_import(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text("MESSAGE = 'frozen-import'\n", encoding="utf-8")
    history, output_root, command = bootstrap_project(tmp_path, "import helper\nprint(helper.MESSAGE)\n")
    assert subprocess.run(command, capture_output=True, text=True).returncode == 0
    (history / "cassi-qi-language.json").write_bytes(b'{"mode_count":2}')
    tampered = subprocess.run(
        [sys.executable, "-O", "-B", str(history / "run_cassi_qi_behavior_demo.py"), "--manifest", str(history / "manifest.json"), "--config", str(history / "cassi-qi-language.json"), "--output", str(output_root / "bad-config")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert tampered.returncode != 0 and "config digest mismatch" in tampered.stderr
    (history / "cassi-qi-language.json").write_bytes(b'{"mode_count":1}')
    (history / "source" / "helper.py").unlink()
    missing_import = subprocess.run(
        [sys.executable, "-O", "-B", str(history / "run_cassi_qi_behavior_demo.py"), "--manifest", str(history / "manifest.json"), "--config", str(history / "cassi-qi-language.json"), "--output", str(output_root / "missing-import")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert missing_import.returncode != 0 and "indexed object unavailable" in missing_import.stderr


def test_graph_rejects_omission_cycle_dangling_owner_and_orphan(tmp_path: Path) -> None:
    make_minimal_plan(tmp_path)
    graph = builder.make_graph(tmp_path, "historical")
    builder.validate_graph(graph, tmp_path)
    omitted = copy.deepcopy(graph)
    omitted["nodes"] = [node for node in omitted["nodes"] if not (node["kind"] == "work_package" and node["id"] == "W1")]
    with pytest.raises(builder.ValidationError, match="work package"):
        builder.validate_graph(omitted, tmp_path)
    cyclic = copy.deepcopy(graph)
    cyclic["edges"].extend([{"from": "W0", "to": "W1", "kind": "depends-on"}, {"from": "W1", "to": "W0", "kind": "depends-on"}])
    with pytest.raises(builder.ValidationError, match="cyclic"):
        builder.validate_graph(cyclic, tmp_path)
    dangling = copy.deepcopy(graph)
    dangling["edges"].append({"from": "W0", "to": "unknown", "kind": "owns"})
    with pytest.raises(builder.ValidationError, match="dangling"):
        builder.validate_graph(dangling, tmp_path)
    owner = copy.deepcopy(graph)
    owner["edges"] = [edge for edge in owner["edges"] if edge != {"from": "CassiFI/00-foundations.md", "to": "QI-NUM-001", "kind": "defines"}]
    with pytest.raises(builder.ValidationError, match="registry owner edge"):
        builder.validate_graph(owner, tmp_path)
    orphan = copy.deepcopy(graph)
    orphan["edges"] = [edge for edge in orphan["edges"] if edge["to"] != "cassi.qi-flow-test.v1"]
    with pytest.raises(builder.ValidationError, match="orphan artifact"):
        builder.validate_graph(orphan, tmp_path)


def test_independent_verifier_detects_source_section_and_registry_drift(tmp_path: Path) -> None:
    make_minimal_plan(tmp_path)
    graph = builder.make_graph(tmp_path, "historical")
    verifier.verify_graph(tmp_path, graph, "historical")
    packages = tmp_path / "CassiFI/10-work-packages.md"
    packages.write_text(packages.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="")
    with pytest.raises(verifier.VerificationError, match="section hash mismatch"):
        verifier.verify_graph(tmp_path, graph, "historical")
    make_minimal_plan(tmp_path)
    graph = builder.make_graph(tmp_path, "historical")
    registry = tmp_path / "CassiFI/13-requirements-registry.md"
    registry.write_text("| `QI-NUM-001` | `CassiFI/00-foundations.md` | W1 | G0 | `cassi.qi-flow-test.v1` |\n", encoding="utf-8", newline="")
    with pytest.raises(verifier.VerificationError, match="normative document view hash mismatch"):
        verifier.verify_graph(tmp_path, graph, "historical")


def test_stale_run_spec_envelope_is_rejected(tmp_path: Path) -> None:
    envelope = {"schema": "cassi.test-envelope.v1", "status": "W0_COMPLETE"}
    envelope["self_sha256"] = hashlib.sha256(canonical(envelope)).hexdigest()
    path = tmp_path / "run-spec.json"
    path.write_bytes(canonical(envelope))
    assert verifier.check_envelope(path)["status"] == "W0_COMPLETE"
    stale = json.loads(path.read_text(encoding="utf-8"))
    stale["status"] = "MUTATED"
    path.write_bytes(canonical(stale))
    with pytest.raises(verifier.VerificationError, match="self hash mismatch"):
        verifier.check_envelope(path)

def test_content_addressed_run_id_tracks_normative_plan_bytes(tmp_path: Path) -> None:
    make_minimal_plan(tmp_path)
    historical = tmp_path / "historical" / "qi-v2"
    historical.mkdir(parents=True)
    historical_manifest = {
        "entrypoint": "run_cassi_qi_behavior_demo.py",
        "config": "cassi-qi-language.json",
        "wrapper_output_root": "_diag/cassi-qi-flow-w0-final/historical-smoke",
    }
    (historical / "manifest.json").write_bytes(canonical(historical_manifest))
    first = builder.content_addressed_run_id(tmp_path, historical)
    readme = tmp_path / "CassiFI" / "README.md"
    readme.write_bytes(b"plan-drift")
    second = builder.content_addressed_run_id(tmp_path, historical)
    assert first != second


def test_independent_verifier_rejects_extra_ungrounded_graph_edge(tmp_path: Path) -> None:
    make_minimal_plan(tmp_path)
    graph = builder.make_graph(tmp_path, "historical")
    graph["edges"].append({"from": "W0", "to": "W2", "kind": "declared-order"})
    graph.pop("self_sha256")
    graph["self_sha256"] = hashlib.sha256(canonical(graph)).hexdigest()
    with pytest.raises(verifier.VerificationError, match="independently regenerated"):
        verifier.verify_graph(tmp_path, graph, "historical")



class W0ManifestBehaviorTests(unittest.TestCase):
    pass


def _as_unittest(function):
    def test(self):
        with TemporaryDirectory(prefix="cassi-qi-flow-w0-test-") as temporary:
            function(Path(temporary))
    test.__name__ = function.__name__
    return test


for _name, _function in tuple(globals().items()):
    if _name.startswith("test_") and callable(_function):
        setattr(W0ManifestBehaviorTests, _name, _as_unittest(_function))


if __name__ == "__main__":
    unittest.main()
