"""CassiFI self-study and bounded CassiMindField candidate development.

This adapter is deliberately narrower than the full CassiMindField redesign lab.
It performs read-only source observation and compiles only the lab's published
example architecture world.  Every operation writes an immutable receipt below
``artifact_home``; no live source is replaced or promoted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


_ROOT = Path(__file__).resolve().parent
_MIND_FIELD = (_ROOT.parent / "CassiMindField").resolve()
_QWEN = (_ROOT.parent / "CassiQwen").resolve()
for _path in (_MIND_FIELD, _QWEN):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

try:
    from self_observatory import (  # type: ignore
        canonical,
        digest,
        index_workspace,
        run_bounded_command,
        source_references,
    )
    _OBSERVATORY_IMPORT_ERROR: str | None = None
except Exception as _exc:  # pragma: no cover - exercised by missing external checkout
    canonical = None  # type: ignore[assignment]
    digest = None  # type: ignore[assignment]
    index_workspace = None  # type: ignore[assignment]
    run_bounded_command = None  # type: ignore[assignment]
    source_references = None  # type: ignore[assignment]
    _OBSERVATORY_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"

try:  # The candidate path is unavailable only when the external lab is absent.
    from architecture_ir import ArchitectureIR, build_example  # type: ignore
    from architecture_synthesizer import synthesize_workspace, workspace_digest  # type: ignore
    import redesign_lab as _redesign_lab  # type: ignore
    _LAB_IMPORT_ERROR: str | None = None
except Exception as _exc:  # pragma: no cover - exercised by missing external checkout
    ArchitectureIR = Any  # type: ignore[misc,assignment]
    build_example = None  # type: ignore[assignment]
    synthesize_workspace = None  # type: ignore[assignment]
    workspace_digest = None  # type: ignore[assignment]
    _redesign_lab = None  # type: ignore[assignment]
    _LAB_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"


SCHEMA = "cassifi.research-development.v1"
RECEIPT_SCHEMA = "cassifi.research-development-receipt.v1"
_MAX_PATHS = 64
_MAX_TEXT = 16_384
_MAX_PROBES = 64
_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")

# These are intentionally fixed.  Request text never becomes a subprocess,
# shell fragment, module name, or evaluation command.
_MEASUREMENT_SCRIPT = r'''
import ast, json, pathlib, sys
rows = []
for raw in sys.argv[1:]:
    path = pathlib.Path(raw)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=raw, type_comments=True)
    branches = sum(isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)) for node in ast.walk(tree))
    functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    calls = sum(isinstance(node, ast.Call) for node in ast.walk(tree))
    imports = sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    rows.append({"path": raw.replace("\\", "/"), "bytes": len(source.encode("utf-8")), "lines": len(source.splitlines()), "functions": functions, "classes": classes, "branches": branches, "calls": calls, "imports": imports})
print(json.dumps(rows, sort_keys=True, separators=(",", ":")))
'''.strip()

INVOCATION_EXAMPLES = {
    "self-study": {
        "operation_id": "research-study-001",
        "kind": "self-study",
        "source_root": "C:/path/to/repository",
        "source_paths": ["src/module.py", "src/runtime.py"],
    },
    "candidate-development": {
        "operation_id": "research-candidate-001",
        "kind": "candidate-development",
        "source_regime": "cassimindfield-lab-example-v1",
        "objective": "evaluate a bounded architecture candidate",
    },
}
PROPOSED_COMMANDS = {
    "candidate_smoke": "python -c \"from pathlib import Path; from cassi_research_development import execute_work; print(execute_work({'operation_id':'smoke-001','kind':'candidate-development','source_regime':'cassimindfield-lab-example-v1'}, workspace=Path('.'), artifact_home=Path('..')/'cassi-research-artifacts'))\"",
    "self_study_smoke": "python -c \"from pathlib import Path; from cassi_research_development import execute_work; print(execute_work({'operation_id':'study-001','kind':'self-study','source_root':'.','source_paths':['cassi_research_development.py']}, workspace=Path('.'), artifact_home=Path('..')/'cassi-research-artifacts'))\"",
    "rejection": "python -c \"from pathlib import Path; from cassi_research_development import execute_work; print(execute_work({'operation_id':'reject-001','kind':'candidate-development','source_regime':'unsupported'}, workspace=Path('.'), artifact_home=Path('..')/'cassi-research-artifacts'))\"",
}


def _text(value: Any, label: str, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > limit:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value


def _operation_id(request: Mapping[str, Any]) -> str:
    value = request.get("operation_id")
    if not isinstance(value, str) or not _OPERATION_ID.fullmatch(value):
        raise ValueError("operation_id must match [A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
    return value


def _safe_relative(value: Any, label: str) -> str:
    raw = _text(value, label, 240).replace("\\", "/")
    path = Path(raw)
    if path.is_absolute() or raw.startswith("/") or ".." in path.parts or not raw.endswith(".py"):
        raise ValueError(f"{label} must be a relative Python source path")
    return path.as_posix()


def _paths(request: Mapping[str, Any]) -> list[str]:
    raw = request.get("source_paths")
    if not isinstance(raw, (list, tuple)) or not raw or len(raw) > _MAX_PATHS:
        raise ValueError("source_paths must be a bounded nonempty list")
    values = [_safe_relative(item, "source path") for item in raw]
    if len(set(values)) != len(values):
        raise ValueError("source_paths must be unique")
    return values


def _resolve_root(request: Mapping[str, Any], workspace: Path) -> Path:
    raw = request.get("source_root")
    root = workspace if raw is None else Path(_text(raw, "source_root", 1024)).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"source_root is not a directory: {root}")
    return root


def _inside(child: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((str(child.resolve()), str(parent.resolve()))) == str(parent.resolve())
    except ValueError:
        return False


def _ensure_artifacts_outside(root: Path, artifact_home: Path) -> None:
    if _inside(artifact_home, root):
        raise ValueError("artifact_home must be outside source_root")
    artifact_home.mkdir(parents=True, exist_ok=True)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value) + b"\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _write_receipt(artifact_home: Path, operation_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    receipt = dict(body)
    receipt["schema"] = RECEIPT_SCHEMA
    receipt["content_sha256"] = digest({key: value for key, value in receipt.items() if key != "content_sha256"})
    path = artifact_home / f"receipt-{hashlib.sha256(operation_id.encode('utf-8')).hexdigest()[:32]}.json"
    _atomic_json(path, receipt)
    return {"artifact_path": path.as_posix(), "artifact_sha256": receipt["content_sha256"], "artifact_schema": RECEIPT_SCHEMA}


def _base_output(status: str, summary: str, evidence: Mapping[str, Any], opportunities: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    result = {"status": status, "summary": summary, "evidence": dict(evidence)}
    if opportunities:
        result["learning_opportunities"] = [dict(item) for item in opportunities]
    return result


def _source_hashes(root: Path, paths: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in paths:
        path = (root / relative).resolve()
        if not _inside(path, root) or not path.is_file():
            raise ValueError(f"source path does not exist: {relative}")
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
def _stable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _stable(item) for key, item in value.items() if key not in {"timing", "wall_ns", "process_ns"}}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value




def _copy_explicit_sources(root: Path, paths: Sequence[str], destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    for relative in paths:
        source = (root / relative).resolve()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _parse_measurement(result: Mapping[str, Any], paths: Sequence[str]) -> list[dict[str, Any]]:
    if result.get("returncode") != 0 or result.get("timed_out"):
        return []
    try:
        rows = json.loads(str(result.get("stdout", "")))
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []
    wanted = set(paths)
    return [dict(row) for row in rows if isinstance(row, Mapping) and row.get("path") in wanted]


def _static_bottlenecks(index: Mapping[str, Any], paths: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    wanted = set(paths)
    for file_row in index.get("files", []):
        if not isinstance(file_row, Mapping) or file_row.get("path") not in wanted:
            continue
        path = str(file_row["path"])
        provenance = {
            "path": path,
            "source_revision_id": file_row.get("source_revision_id"),
            "source_sha256": file_row.get("source_sha256"),
        }
        calls = [call for call in file_row.get("calls", []) if isinstance(call, Mapping)]
        imports = [item for item in file_row.get("imports", []) if isinstance(item, Mapping)]
        symbols = [item for item in file_row.get("symbols", []) if isinstance(item, Mapping)]
        if calls:
            for call in calls[:32]:
                rows.append({"kind": "call-site", "focus": str(call.get("callee", "<unknown>")), "span": call.get("span", {}), "evidence": {"argument_count": call.get("argument_count", 0)}, "provenance": provenance})
        if imports:
            for item in imports[:16]:
                rows.append({"kind": "dependency-boundary", "focus": str(item.get("module", item.get("name", "<unknown>"))), "span": item.get("span", {}), "evidence": {"imported_name": item.get("name")}, "provenance": provenance})
        if not calls and not imports:
            rows.append({"kind": "symbol-surface", "focus": str(symbols[0].get("qualname", path)) if symbols else path, "span": symbols[0].get("span", {}) if symbols else {}, "evidence": {"reason": "no indexed call or import boundary; inspect local implementation"}, "provenance": provenance})
    return rows[:128]


def _self_study(request: Mapping[str, Any], workspace: Path, artifact_home: Path) -> dict[str, Any]:
    root = _resolve_root(request, workspace)
    _ensure_artifacts_outside(root, artifact_home)
    paths = _paths(request)
    before_hashes = _source_hashes(root, paths)
    operation_id = _operation_id(request)
    analysis_root = artifact_home / f"analysis-{hashlib.sha256(operation_id.encode('utf-8')).hexdigest()[:16]}"
    _copy_explicit_sources(root, paths, analysis_root)
    if index_workspace is None or run_bounded_command is None:
        raise RuntimeError(f"self-observatory unavailable: {_OBSERVATORY_IMPORT_ERROR}")
    index = index_workspace(analysis_root)
    refs = source_references(index, paths)
    command = [sys.executable, "-c", _MEASUREMENT_SCRIPT, *paths]
    measured_result = run_bounded_command(command, workspace=analysis_root, timeout_seconds=10.0)
    measured = _parse_measurement(measured_result, paths)
    static = _static_bottlenecks(index, paths)
    after_hashes = _source_hashes(root, paths)
    unchanged = before_hashes == after_hashes
    body = {
        "adapter_schema": SCHEMA,
        "operation_id": operation_id,
        "kind": "self-study",
        "source_root": root.as_posix(),
        "source_paths": paths,
        "source_index_sha256": index.get("content_sha256"),
        "source_revision_id": index.get("workspace_revision_id"),
        "source_references": refs,
        "static_bottlenecks": static,
        "measurement": {"command": command[:2] + ["<fixed-analysis>"] + paths, "result": _stable(measured_result), "rows": measured},
        "source_unchanged": {"before": before_hashes, "after": after_hashes, "unchanged": unchanged},
        "analysis_scope": "explicit Python files only; static AST boundaries plus fixed read-only AST measurement",
    }
    artifact = _write_receipt(artifact_home, operation_id, body)
    evidence = {**artifact, "source_index_sha256": index.get("content_sha256"), "source_revision_id": index.get("workspace_revision_id"), "source_paths": paths, "source_references": refs, "static_bottlenecks": static, "measured_bottlenecks": measured, "source_unchanged": unchanged, "scope": body["analysis_scope"], "invocation_example": INVOCATION_EXAMPLES["self-study"], "proposed_commands": PROPOSED_COMMANDS}
    opportunities: list[dict[str, Any]] = []
    if measured:
        opportunities.append({"candidate_id": f"self-study:{digest({'source_root': root.as_posix(), 'source_paths': paths})[:24]}", "learning_kind": "procedure", "request": {"kind": "self-study", "source_root": root.as_posix(), "source_paths": paths}, "expected_gain": 0.25, "priority": 0.5, "cost": 0.1, "risk": 0.0})
    status = "observed" if unchanged and measured_result.get("returncode") == 0 and measured else "support-gap"
    summary = "Observed explicit source files with provenance and fixed AST bottleneck measurement." if status == "observed" else "Static source study completed, but the fixed measurement did not produce usable rows."
    return _base_output(status, summary, evidence, opportunities)


def _lab_parent(request: Mapping[str, Any], workspace: Path) -> tuple[dict[str, str], str, dict[str, Any], dict[str, str] | None]:
    if _LAB_IMPORT_ERROR is not None or build_example is None or workspace_digest is None:
        raise LookupError(f"CassiMindField redesign lab unavailable: {_LAB_IMPORT_ERROR}")
    source_regime = request.get("source_regime", "cassimindfield-lab-example-v1")
    if source_regime != "cassimindfield-lab-example-v1":
        raise LookupError("unsupported source_regime; only cassimindfield-lab-example-v1 is implemented")
    parent_files, _ = build_example()
    expected = {str(key): str(value) for key, value in parent_files.items()}
    root_raw = request.get("source_root")
    live_hashes: dict[str, str] | None = None
    if root_raw is not None:
        root = Path(_text(root_raw, "source_root", 1024)).expanduser().resolve()
        if not root.is_dir():
            raise LookupError("candidate source_root is not a directory")
        try:
            live_hashes = _source_hashes(root, sorted(expected))
            actual = {(root / path).read_text(encoding="utf-8") for path in sorted(expected)}
        except (OSError, UnicodeError, ValueError) as exc:
            raise LookupError(f"source_root does not contain the published lab example files: {exc}") from exc
        if len(actual) != len(expected) or any((root / path).read_text(encoding="utf-8") != source for path, source in expected.items()):
            raise LookupError("source_root is not the exact published lab example world; full repository redesign is unsupported")
    parent_digest = workspace_digest(expected)
    space = _redesign_lab._architecture_research_space(expected, parent_digest)
    return expected, parent_digest, space, live_hashes


def _select_question(request: Mapping[str, Any], space: Mapping[str, Any], semantic: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None) -> tuple[Mapping[str, Any], dict[str, Any]]:
    options = [row for row in space.get("question_options", []) if isinstance(row, Mapping)]
    family = request.get("compiler_family", request.get("family", request.get("selected_family")))
    variant = request.get("variant_key", request.get("candidate", request.get("selected_candidate", request.get("candidate_key"))))
    decision = request.get("field_decision")
    if isinstance(decision, Mapping):
        family = decision.get("compiler_family", decision.get("family", family))
        variant = decision.get("variant_key", decision.get("candidate", variant))
    selection_meta: dict[str, Any] = {"method": "request"}
    if family is None:
        if semantic is None:
            raise LookupError("field decision required: provide semantic callback or compiler_family")
        offered = {"operation": "select-research-candidate", "source_regime": "cassimindfield-lab-example-v1", "options": [{"question_id": row.get("question_id"), "compiler_family": row.get("compiler_family"), "variants": [item.get("variant_key") for item in row.get("variant_catalog", []) if isinstance(item, Mapping)]} for row in options]}
        returned = semantic(offered)
        if not isinstance(returned, Mapping):
            raise LookupError("semantic callback did not return a mapping")
        family = returned.get("compiler_family", returned.get("family"))
        variant = returned.get("variant_key", returned.get("candidate"))
        selection_meta = {"method": "semantic", "decision": dict(returned)}
    question = next((row for row in options if row.get("compiler_family") == family), None)
    if question is None:
        raise LookupError(f"unsupported compiler family: {family}")
    catalog = [row for row in question.get("variant_catalog", []) if isinstance(row, Mapping)]
    if variant is None:
        if semantic is None:
            raise LookupError("variant selection requires semantic callback or variant_key")
        returned = semantic({"operation": "select-variant", "source_regime": "cassimindfield-lab-example-v1", "compiler_family": family, "options": [row.get("variant_key") for row in catalog]})
        if not isinstance(returned, Mapping):
            raise LookupError("semantic callback did not return a mapping")
        variant = returned.get("variant_key", returned.get("candidate"))
        selection_meta = {**selection_meta, "variant_decision": dict(returned)}
    selected = next((row for row in catalog if row.get("variant_key") == variant), None)
    if selected is None:
        raise LookupError(f"unsupported variant for {family}: {variant}")
    return question, {**selection_meta, "compiler_family": family, "variant_key": variant}


def _candidate_development(request: Mapping[str, Any], workspace: Path, artifact_home: Path, semantic: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None) -> dict[str, Any]:
    _ensure_artifacts_outside(workspace, artifact_home)
    operation_id = _operation_id(request)
    parent_files, parent_digest, space, live_hashes = _lab_parent(request, workspace)
    question, selection = _select_question(request, space, semantic)
    rows = _redesign_lab._compile_question_documents(parent_files, parent_digest, question)
    selected = next(row for row in rows if row.get("variant_key") == selection["variant_key"])
    candidate = synthesize_workspace(parent_files, ArchitectureIR.from_dict(selected["architecture"]))
    candidate_id = str(selected["hypothesis_id"])
    candidate_root = artifact_home / f"candidate-{hashlib.sha256(candidate_id.encode('utf-8')).hexdigest()[:24]}"
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    for relative, source in sorted(candidate.files.items()):
        target = candidate_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8", newline="")
    measurement = _redesign_lab._measure_candidate(candidate_root, selected)
    candidate_index = index_workspace(candidate_root)
    passed = measurement.get("assessments", {}).get("status") == "PASS"
    body = {
        "adapter_schema": SCHEMA,
        "operation_id": operation_id,
        "kind": "candidate-development",
        "source_regime": "cassimindfield-lab-example-v1",
        "scope": "published CassiMindField architecture example only; not full repository redesign",
        "measurement": _stable(measurement),
        "research_space": space,
        "field_selection": selection,
        "candidate_id": candidate_id,
        "candidate_source_digest": candidate.source_digest,
        "candidate_workspace_digest": workspace_digest(candidate.files),
        "candidate_path": candidate_root.as_posix(),
        "candidate_index_sha256": candidate_index.get("content_sha256"),
        "incumbent": {"status": "preserved", "source_digest": parent_digest, "promotion": "never-promoted-by-this-adapter"},
        "live_source_unchanged": {"checked": live_hashes is not None, "before": live_hashes, "after": live_hashes, "unchanged": True if live_hashes is not None else None},
    }
    artifact = _write_receipt(artifact_home, operation_id, body)
    alternatives = [row for row in rows if row.get("variant_key") != selection["variant_key"]]
    opportunities = [{"candidate_id": f"candidate:{selection['compiler_family']}:{row.get('variant_key')}", "learning_kind": "procedure", "request": {"kind": "candidate-development", "source_regime": "cassimindfield-lab-example-v1", "compiler_family": selection["compiler_family"], "variant_key": row.get("variant_key")}, "expected_gain": 0.25, "priority": 0.5, "cost": 0.2, "risk": 0.0} for row in alternatives]
    evidence = {**artifact, "scope": body["scope"], "candidate_id": candidate_id, "candidate_path": candidate_root.as_posix(), "candidate_source_digest": candidate.source_digest, "candidate_index_sha256": candidate_index.get("content_sha256"), "field_selection": selection, "research_space": space, "measurement": measurement, "incumbent_preserved": True, "promotion": "never-promoted", "live_source_unchanged": body["live_source_unchanged"], "invocation_example": INVOCATION_EXAMPLES["candidate-development"], "proposed_commands": PROPOSED_COMMANDS}
    if passed:
        return _base_output("supported", "Generated and evaluated one bounded lab-world candidate in isolation; incumbent was preserved.", evidence, opportunities)
    return _base_output("rejected", "Candidate evaluation failed the lab baseline or holdout; it was retained only as an isolated artifact.", evidence, opportunities)


def _failure_output(request: Mapping[str, Any], workspace: Path, artifact_home: Path, status: str, message: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {"schema": SCHEMA, "error_type": status, "scope": "bounded source-study and CassiMindField lab-example candidate development"}
    try:
        operation_id = _operation_id(request)
        home = artifact_home.resolve()
        home.mkdir(parents=True, exist_ok=True)
        receipt = _write_receipt(home, operation_id, {
            "adapter_schema": SCHEMA,
            "operation_id": operation_id,
            "kind": str(request.get("kind", "")),
            "status": status,
            "error": message,
            "workspace": workspace.resolve().as_posix(),
        })
        evidence.update(receipt)
    except Exception as artifact_error:
        evidence["artifact_error"] = f"{type(artifact_error).__name__}: {artifact_error}"
    return _base_output(status, message, evidence)


def execute_work(request: Mapping[str, Any], *, workspace: Path, artifact_home: Path, semantic: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Execute one bounded research-development operation.

    ``request`` is data only: the adapter has no shell passthrough and never
    writes to ``workspace``.  Candidate selection is explicit or delegated to
    the supplied resident-field semantic callback.
    """
    if not isinstance(request, Mapping):
        return _base_output("rejected", "request must be a mapping", {"schema": SCHEMA})
    root = Path(workspace).resolve()
    home = Path(artifact_home).resolve()
    try:
        kind = str(request.get("kind", "")).strip().lower()
        if kind in {"self-study", "repository-self-study", "source-study"}:
            return _self_study(request, root, home)
        if kind in {"candidate-development", "candidate-evaluation", "candidate"}:
            return _candidate_development(request, root, home, semantic)
        return _failure_output(request, root, home, "rejected", f"unsupported research-development kind: {kind or '<missing>'}")
    except LookupError as exc:
        return _failure_output(request, root, home, "support-gap", str(exc))
    except (ValueError, TypeError, RuntimeError, OSError, StopIteration) as exc:
        return _failure_output(request, root, home, "rejected", f"research-development request rejected: {exc}")


__all__ = ["SCHEMA", "RECEIPT_SCHEMA", "INVOCATION_EXAMPLES", "PROPOSED_COMMANDS", "execute_work"]
