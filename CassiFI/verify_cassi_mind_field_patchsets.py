#!/usr/bin/env python3
"""Independently verify a CassiMindField multi-file patch-set receipt."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
CASSIQWEN = WORKSPACE / "CassiQwen"
CASSIMIND = WORKSPACE / "CassiMindField"
for path in (CASSIQWEN, CASSIMIND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cassi_python import PythonCase  # noqa: E402
from verify_cassi_mind_field import verify_candidate_source  # noqa: E402

CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
INDEX_PATH = "src/workspace_index.py"
RUNTIME_PATH = "src/field_runtime.py"
FILE_PATHS = (CORE_PATH, EDITOR_PATH, INDEX_PATH, RUNTIME_PATH)
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
PATCH_SET_SCHEMA = "cassimindfield.patch-set.v1"
INDEX_SCHEMA = "cassimindfield.workspace-index.v1"
CASES = (
    PythonCase("negative", {"value": -7}, -34),
    PythonCase("zero", {"value": 0}, 1),
    PythonCase("positive", {"value": 9}, 46),
    PythonCase("large", {"value": 123}, 616),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def read_files(root: Path, generation: int) -> dict[str, str]:
    files = {}
    for relative in FILE_PATHS:
        path = generation_path(root, generation) / relative
        require(path.is_file(), f"missing patch-set source: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def files_digest(files: Mapping[str, str]) -> str:
    return digest({path: sha256_text(files[path]) for path in sorted(files)})


def _symbol(node: ast.AST) -> dict[str, Any] | None:
    if isinstance(node, ast.FunctionDef):
        kind = "function"
    elif isinstance(node, ast.AsyncFunctionDef):
        kind = "async_function"
    elif isinstance(node, ast.ClassDef):
        kind = "class"
    else:
        return None
    return {"kind": kind, "name": node.name, "line": node.lineno, "end_line": node.end_lineno}


def _import_name(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        prefix = "." * node.level + (node.module or "")
        return [prefix + ("." if prefix and alias.name else "") + alias.name for alias in node.names]
    return []


def _called_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _called_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def independent_index(files: Mapping[str, str]) -> dict[str, Any]:
    entries = {}
    for path in sorted(files):
        tree = ast.parse(files[path], filename=path)
        symbols = []
        imports = []
        calls = set()
        for node in ast.walk(tree):
            symbol = _symbol(node)
            if symbol:
                symbols.append(symbol)
            imports.extend(_import_name(node))
            if isinstance(node, ast.Call):
                name = _called_name(node.func)
                if name:
                    calls.add(name)
        symbols.sort(key=lambda item: (item["line"], item["name"]))
        entries[path] = {
            "sha256": sha256_text(files[path]),
            "bytes": len(files[path].encode("utf-8")),
            "symbols": symbols,
            "imports": sorted(set(imports)),
            "calls": sorted(calls),
        }
    return {
        "schema": INDEX_SCHEMA,
        "files": entries,
        "file_count": len(entries),
        "symbol_count": sum(len(entry["symbols"]) for entry in entries.values()),
    }


def load_editor(source: str) -> tuple[Callable[..., Any], Callable[..., Any]]:
    namespace: dict[str, Any] = {"__name__": "independent_patchset_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch_set = namespace.get("apply_patch_set")
    proposer = namespace.get("propose_candidates")
    require(callable(apply_patch_set), "editor lacks apply_patch_set")
    require(callable(proposer), "editor lacks propose_candidates")
    return apply_patch_set, proposer


def editor_behavior(apply_patch_set: Callable[..., Any]) -> None:
    source = "alpha + beta"
    change = {
        "path": EDITOR_PATH,
        "schema": PATCH_SCHEMA,
        "operation": "replace_once",
        "find": "alpha",
        "replace": "gamma",
        "base_source_sha256": sha256_text(source),
    }
    patch_set = {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [change]}
    require(apply_patch_set({EDITOR_PATH: source}, patch_set)[EDITOR_PATH] == "gamma + beta", "editor valid case failed")
    for invalid in ("alpha alpha", "beta"):
        bad = dict(change, base_source_sha256=sha256_text(invalid))
        try:
            apply_patch_set({EDITOR_PATH: invalid}, {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [bad]})
        except Exception:
            continue
        raise RuntimeError("editor accepted invalid match")


def independent_apply(files: Mapping[str, str], patch_set: Mapping[str, Any]) -> dict[str, str]:
    require(patch_set.get("schema") == PATCH_SET_SCHEMA, "patch-set schema mismatch")
    require(patch_set.get("operation") == "apply_patch_set", "patch-set operation mismatch")
    changes = patch_set.get("changes")
    require(isinstance(changes, list) and changes, "patch-set changes missing")
    updated = dict(files)
    for change in changes:
        path = change.get("path")
        require(path in updated, "patch-set changed unknown file")
        require(change.get("schema") == PATCH_SCHEMA, "patch change schema mismatch")
        require(change.get("operation") == "replace_once", "patch change operation mismatch")
        require(change.get("base_source_sha256") == sha256_text(updated[path]), "patch-set base hash mismatch")
        find = change.get("find")
        replacement = change.get("replace")
        require(isinstance(find, str) and find, "patch-set find is invalid")
        require(isinstance(replacement, str), "patch-set replacement is invalid")
        require(updated[path].count(find) == 1, "patch-set cardinality mismatch")
        updated[path] = updated[path].replace(find, replacement, 1)
    return updated


def verify_dependency_contract(files: Mapping[str, str]) -> None:
    core = ast.parse(files[CORE_PATH], filename=CORE_PATH)
    runtime = ast.parse(files[RUNTIME_PATH], filename=RUNTIME_PATH)
    core_functions = {node.name for node in ast.walk(core) if isinstance(node, ast.FunctionDef)}
    require("step_field" in core_functions, "renamed core symbol is missing")
    imported = {
        alias.name
        for node in ast.walk(runtime)
        if isinstance(node, ast.ImportFrom) and node.module == "mind_field_core"
        for alias in node.names
    }
    require("step_field" in imported, "consumer import was not updated")
    called = {
        node.func.id
        for node in ast.walk(runtime)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    require("step_field" in called, "consumer call was not updated")
    require("advance_field" not in imported and "advance_field" not in called, "old dependency symbol remains")


def verify_run(root: Path) -> dict[str, Any]:
    receipt = json.loads((root / "patchset-receipt.json").read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassimindfield.patchset-rewrite.v1", "receipt schema mismatch")
    transitions = receipt.get("transitions")
    require(isinstance(transitions, list) and transitions, "patch-set receipt has no transitions")
    previous_generation = 0
    multi_file_seen = False
    for row in transitions:
        generation = int(row["generation"])
        next_generation = int(row["next_generation"])
        require(generation == previous_generation, "patch-set lineage is not contiguous")
        require(next_generation == generation + 1, "patch-set generation increment invalid")
        before = read_files(root, generation)
        after = read_files(root, next_generation)
        index = json.loads((generation_path(root, next_generation) / "workspace-index.json").read_text(encoding="utf-8"))
        manifest = json.loads((generation_path(root, next_generation) / "manifest.json").read_text(encoding="utf-8"))
        require(manifest["schema"] == "cassimindfield.patchset-generation.v1", "manifest schema mismatch")
        require(manifest["proposal_origin"] == "promoted_editor", "manifest proposal origin mismatch")
        require(index == independent_index(after), "workspace index mismatch")
        require(manifest["workspace_index_sha256"] == digest(index), "manifest index hash mismatch")
        for relative in FILE_PATHS:
            require(manifest["files"][relative]["sha256"] == sha256_text(after[relative]), f"manifest source hash mismatch: {relative}")
        candidate = row["candidate"]
        require(candidate["proposal_origin"] == "promoted_editor", "receipt proposal origin mismatch")
        changed_paths = sorted(candidate["changed_paths"])
        patch_set = candidate["patch_set"]
        actual_paths = sorted({str(change["path"]) for change in patch_set["changes"]})
        require(changed_paths == actual_paths, "patch-set changed path declaration mismatch")
        if len(changed_paths) >= 2:
            multi_file_seen = True
        replayed = independent_apply(before, patch_set)
        require(replayed == after, "promoted patch-set differs from independent replay")
        require(candidate["files_sha256"] == files_digest(after), "candidate workspace hash mismatch")
        require(candidate["workspace_index_sha256"] == digest(index), "candidate index hash mismatch")
        if CORE_PATH in changed_paths:
            check = verify_candidate_source(before[CORE_PATH], after[CORE_PATH], CASES)
            require(check["passed"], f"core candidate failed: {check}")
        if RUNTIME_PATH in changed_paths:
            verify_dependency_contract(after)
        if EDITOR_PATH in changed_paths:
            editor_behavior(load_editor(after[EDITOR_PATH])[0])
        previous_generation = next_generation
    require(multi_file_seen, "no multi-file patch-set was promoted")

    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    final_files = read_files(root, previous_generation)
    final_index = json.loads((generation_path(root, previous_generation) / "workspace-index.json").read_text(encoding="utf-8"))
    require(pointer["generation"] == previous_generation, "current generation mismatch")
    require(pointer["files_sha256"] == files_digest(final_files), "current files hash mismatch")
    require(pointer["workspace_index_sha256"] == digest(final_index), "current index hash mismatch")
    final_manifest = json.loads((generation_path(root, previous_generation) / "manifest.json").read_text(encoding="utf-8"))
    require(pointer["manifest_sha256"] == digest(final_manifest), "current manifest hash mismatch")
    require(final_index == independent_index(final_files), "final index mismatch")
    verify_dependency_contract(final_files)
    for relative in FILE_PATHS:
        require((root / relative).read_text(encoding="utf-8") == final_files[relative], f"live source mismatch: {relative}")

    final_editor = load_editor(final_files[EDITOR_PATH])[0]
    replay = read_files(root, 0)
    for row in transitions:
        replay = final_editor(replay, row["candidate"]["patch_set"])
        require(replay == read_files(root, int(row["next_generation"])), "final editor failed patch-set replay")

    core_mutation = final_files[CORE_PATH].replace("return 5 * value + 1", "return 5 * value + 2", 1)
    require(not verify_candidate_source(final_files[CORE_PATH], core_mutation, CASES)["passed"], "core mutation accepted")
    dependency_mutation = final_files[RUNTIME_PATH].replace("step_field(value)", "advance_field(value)", 1)
    try:
        verify_dependency_contract({**final_files, RUNTIME_PATH: dependency_mutation})
    except Exception:
        dependency_mutation_rejected = True
    else:
        raise RuntimeError("dependency mutation accepted")
    index_mutation = dict(final_index, file_count=final_index["file_count"] + 1)
    require(digest(index_mutation) != pointer["workspace_index_sha256"], "index mutation accepted")
    return {
        "status": "PASS",
        "current_generation": previous_generation,
        "generations": len(transitions),
        "multi_file_patch_set_verified": True,
        "indexed_files": final_index["file_count"],
        "indexed_symbols": final_index["symbol_count"],
        "workspace_replay_verified": True,
        "core_mutation_rejected": True,
        "dependency_mutation_rejected": dependency_mutation_rejected,
        "index_mutation_rejected": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=CASSIMIND / "patchset-v6")
    args = parser.parse_args()
    print(json.dumps(verify_run(args.root.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
