#!/usr/bin/env python3
"""Independently verify dependency-closure-aware Mind Field promotions."""
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
PATCH_SET_SCHEMA = "cassimindfield.patch-set.v2"
INDEX_SCHEMA = "cassimindfield.workspace-index.v2"
SCENARIOS = {
    "core-behavior": [CORE_PATH],
    "runtime-dependency": [CORE_PATH, RUNTIME_PATH],
    "editor-contract": [EDITOR_PATH],
    "workspace-index": [INDEX_PATH],
}
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
        require(path.is_file(), f"missing impact source: {path}")
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


def _imports(node: ast.AST) -> list[str]:
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
    modules = {path.rsplit("/", 1)[-1][:-3]: path for path in files if path.endswith(".py")}
    entries = {}
    dependencies = {path: set() for path in files if path.endswith(".py")}
    for path in sorted(files):
        tree = ast.parse(files[path], filename=path)
        symbols = []
        imports = []
        calls = set()
        for node in ast.walk(tree):
            symbol = _symbol(node)
            if symbol:
                symbols.append(symbol)
            imports.extend(_imports(node))
            if isinstance(node, ast.Call):
                name = _called_name(node.func)
                if name:
                    calls.add(name)
        symbols.sort(key=lambda item: (item["line"], item["name"]))
        entries[path] = {"sha256": sha256_text(files[path]), "bytes": len(files[path].encode("utf-8")), "symbols": symbols, "imports": sorted(set(imports)), "calls": sorted(calls)}
        for imported in set(imports):
            module = imported.split(".", 1)[0].lstrip(".")
            if module in modules and modules[module] != path:
                dependencies[path].add(modules[module])
    dependencies_out = {path: sorted(values) for path, values in dependencies.items()}
    reverse = {path: [] for path in dependencies_out}
    for importer, imported in dependencies_out.items():
        for dependency in imported:
            reverse.setdefault(dependency, []).append(importer)
    reverse_out = {path: sorted(values) for path, values in reverse.items()}
    return {"schema": INDEX_SCHEMA, "files": entries, "dependencies": dependencies_out, "reverse_dependencies": reverse_out, "scenarios": {name: list(paths) for name, paths in sorted(SCENARIOS.items())}, "file_count": len(entries), "symbol_count": sum(len(item["symbols"]) for item in entries.values())}


def closure(index: Mapping[str, Any], changed_paths: list[str]) -> list[str]:
    result = set(changed_paths)
    pending = list(changed_paths)
    while pending:
        current = pending.pop()
        for importer in index["reverse_dependencies"].get(current, []):
            if importer not in result:
                result.add(importer)
                pending.append(importer)
    return sorted(result)


def scenarios(index: Mapping[str, Any], impact: list[str]) -> list[str]:
    return sorted(name for name, paths in index["scenarios"].items() if set(paths).intersection(impact))


def load_editor(source: str) -> tuple[Callable[..., Any], Callable[..., Any]]:
    namespace: dict[str, Any] = {"__name__": "independent_impact_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch_set = namespace.get("apply_patch_set")
    proposer = namespace.get("propose_candidates")
    require(callable(apply_patch_set), "impact editor lacks apply_patch_set")
    require(callable(proposer), "impact editor lacks propose_candidates")
    return apply_patch_set, proposer


def editor_behavior(apply_patch_set: Callable[..., Any]) -> None:
    source = "alpha + beta"
    change = {"path": EDITOR_PATH, "schema": PATCH_SCHEMA, "operation": "replace_once", "find": "alpha", "replace": "gamma", "base_source_sha256": sha256_text(source)}
    patch_set = {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [change]}
    require(apply_patch_set({EDITOR_PATH: source}, patch_set)[EDITOR_PATH] == "gamma + beta", "impact editor valid case failed")
    for invalid in ("alpha alpha", "beta"):
        bad = dict(change, base_source_sha256=sha256_text(invalid))
        try:
            apply_patch_set({EDITOR_PATH: invalid}, {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [bad]})
        except Exception:
            continue
        raise RuntimeError("impact editor accepted invalid match")


def apply_independent(files: Mapping[str, str], patch_set: Mapping[str, Any]) -> dict[str, str]:
    require(patch_set.get("schema") == PATCH_SET_SCHEMA, "impact patch-set schema mismatch")
    updated = dict(files)
    for change in patch_set.get("changes", []):
        path = change.get("path")
        require(path in updated, "impact patch changed unknown path")
        require(change.get("schema") == PATCH_SCHEMA and change.get("operation") == "replace_once", "impact patch change invalid")
        require(change.get("base_source_sha256") == sha256_text(updated[path]), "impact patch base mismatch")
        find = change.get("find")
        replacement = change.get("replace")
        require(isinstance(find, str) and find and isinstance(replacement, str), "impact patch text invalid")
        require(updated[path].count(find) == 1, "impact patch cardinality mismatch")
        updated[path] = updated[path].replace(find, replacement, 1)
    return updated


def dependency_contract(files: Mapping[str, str]) -> None:
    core = ast.parse(files[CORE_PATH])
    runtime = ast.parse(files[RUNTIME_PATH])
    functions = {node.name for node in ast.walk(core) if isinstance(node, ast.FunctionDef)}
    require("step_field" in functions, "step_field is absent")
    imports = {alias.name for node in ast.walk(runtime) if isinstance(node, ast.ImportFrom) and node.module == "mind_field_core" for alias in node.names}
    calls = {node.func.id for node in ast.walk(runtime) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    require("step_field" in imports and "step_field" in calls, "dependency closure was not updated")
    require("advance_field" not in imports and "advance_field" not in calls, "old dependency remains")


def verify_run(root: Path) -> dict[str, Any]:
    receipt = json.loads((root / "impact-receipt.json").read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassimindfield.impact-rewrite.v1", "impact receipt schema mismatch")
    transitions = receipt.get("transitions")
    require(isinstance(transitions, list) and transitions, "impact receipt has no transitions")
    previous = 0
    for row in transitions:
        generation = int(row["generation"])
        next_generation = int(row["next_generation"])
        require(generation == previous and next_generation == generation + 1, "impact lineage invalid")
        before = read_files(root, generation)
        after = read_files(root, next_generation)
        index = json.loads((generation_path(root, next_generation) / "workspace-index.json").read_text(encoding="utf-8"))
        manifest = json.loads((generation_path(root, next_generation) / "manifest.json").read_text(encoding="utf-8"))
        require(index == independent_index(after), "impact index differs from independent graph")
        require(manifest["proposal_origin"] == "promoted_editor", "impact proposal origin mismatch")
        changed = sorted(row["candidate"]["changed_paths"])
        expected_impact = closure(index, changed)
        expected_scenarios = scenarios(index, expected_impact)
        candidate = row["candidate"]
        require(candidate["impact_closure"] == expected_impact, "impact closure mismatch")
        require(candidate["affected_scenarios"] == expected_scenarios, "affected scenario selection mismatch")
        require(manifest["impact_closure"] == expected_impact, "manifest impact closure mismatch")
        require(manifest["affected_scenarios"] == expected_scenarios, "manifest scenario closure mismatch")
        replayed = apply_independent(before, candidate["patch_set"])
        require(replayed == after, "impact patch-set replay mismatch")
        require(candidate["files_sha256"] == files_digest(after), "impact candidate hash mismatch")
        if CORE_PATH in changed:
            require(verify_candidate_source(before[CORE_PATH], after[CORE_PATH], CASES)["passed"], "impact core behavior failed")
        if RUNTIME_PATH in changed:
            dependency_contract(after)
        if EDITOR_PATH in changed:
            editor_behavior(load_editor(after[EDITOR_PATH])[0])
        previous = next_generation
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    final = read_files(root, previous)
    final_index = json.loads((generation_path(root, previous) / "workspace-index.json").read_text(encoding="utf-8"))
    require(pointer["generation"] == previous and pointer["files_sha256"] == files_digest(final), "impact current pointer mismatch")
    require(pointer["workspace_index_sha256"] == digest(final_index), "impact current index pointer mismatch")
    require(final_index == independent_index(final), "impact final index mismatch")
    dependency_contract(final)
    for relative in FILE_PATHS:
        require((root / relative).read_text(encoding="utf-8") == final[relative], f"impact live source mismatch: {relative}")
    apply_patch_set = load_editor(final[EDITOR_PATH])[0]
    replay = read_files(root, 0)
    for row in transitions:
        replay = apply_patch_set(replay, row["candidate"]["patch_set"])
        require(replay == read_files(root, int(row["next_generation"])), "impact editor historical replay failed")
    core_mutation = final[CORE_PATH].replace("return 5 * value + 1", "return 5 * value + 2", 1)
    require(not verify_candidate_source(final[CORE_PATH], core_mutation, CASES)["passed"], "impact core mutation accepted")
    dependency_mutation = final[RUNTIME_PATH].replace("step_field(value)", "advance_field(value)", 1)
    try:
        dependency_contract({**final, RUNTIME_PATH: dependency_mutation})
    except Exception:
        dependency_mutation_rejected = True
    else:
        raise RuntimeError("impact dependency mutation accepted")
    index_mutation = dict(final_index, file_count=final_index["file_count"] + 1)
    require(digest(index_mutation) != pointer["workspace_index_sha256"], "impact index mutation accepted")
    return {"status": "PASS", "current_generation": previous, "generations": len(transitions), "impact_closure_verified": True, "affected_scenarios_verified": True, "workspace_replay_verified": True, "indexed_files": final_index["file_count"], "dependency_mutation_rejected": dependency_mutation_rejected, "index_mutation_rejected": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=CASSIMIND / "impact-v7")
    args = parser.parse_args()
    print(json.dumps(verify_run(args.root.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
