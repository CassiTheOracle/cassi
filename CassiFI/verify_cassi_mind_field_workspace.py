#!/usr/bin/env python3
"""Independently verify a CassiMindField indexed-workspace receipt."""
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
FILE_PATHS = (CORE_PATH, EDITOR_PATH, INDEX_PATH)
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
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
        require(path.is_file(), f"missing workspace source: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def file_digest_map(files: Mapping[str, str]) -> dict[str, str]:
    return {path: sha256_text(files[path]) for path in sorted(files)}


def files_digest(files: Mapping[str, str]) -> str:
    return digest(file_digest_map(files))


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
        if not path.endswith(".py"):
            continue
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
    namespace: dict[str, Any] = {"__name__": "independent_workspace_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch = namespace.get("apply_patch")
    proposer = namespace.get("propose_candidates")
    require(callable(apply_patch), "editor lacks apply_patch")
    require(callable(proposer), "editor lacks propose_candidates")
    return apply_patch, proposer


def editor_behavior(editor: Callable[..., Any]) -> None:
    source = "alpha + beta"
    patch = {
        "schema": PATCH_SCHEMA,
        "operation": "replace_once",
        "path": CORE_PATH,
        "find": "alpha",
        "replace": "gamma",
        "base_source_sha256": sha256_text(source),
    }
    require(editor(source, patch) == "gamma + beta", "editor valid case failed")
    for invalid in ("alpha alpha", "beta"):
        bad_patch = dict(patch, base_source_sha256=sha256_text(invalid))
        try:
            editor(invalid, bad_patch)
        except Exception:
            continue
        raise RuntimeError("editor accepted invalid match")


def independent_apply(source: str, patch: Mapping[str, Any]) -> str:
    require(patch.get("schema") == PATCH_SCHEMA, "patch schema mismatch")
    require(patch.get("operation") == "replace_once", "patch operation mismatch")
    require(patch.get("base_source_sha256") == sha256_text(source), "patch base hash mismatch")
    find = patch.get("find")
    replacement = patch.get("replace")
    require(isinstance(find, str) and find, "patch find is invalid")
    require(isinstance(replacement, str), "patch replacement is invalid")
    require(source.count(find) == 1, "patch cardinality mismatch")
    return source.replace(find, replacement, 1)


def verify_run(root: Path) -> dict[str, Any]:
    receipt = json.loads((root / "workspace-receipt.json").read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassimindfield.workspace-rewrite.v1", "receipt schema mismatch")
    transitions = receipt.get("transitions")
    require(isinstance(transitions, list) and transitions, "workspace receipt has no transitions")
    previous_generation = 0
    for row in transitions:
        generation = int(row["generation"])
        next_generation = int(row["next_generation"])
        require(generation == previous_generation, "workspace lineage is not contiguous")
        require(next_generation == generation + 1, "workspace generation increment is invalid")
        before = read_files(root, generation)
        after = read_files(root, next_generation)
        index = json.loads((generation_path(root, next_generation) / "workspace-index.json").read_text(encoding="utf-8"))
        manifest = json.loads((generation_path(root, next_generation) / "manifest.json").read_text(encoding="utf-8"))
        require(manifest["schema"] == "cassimindfield.workspace-generation.v1", "manifest schema mismatch")
        require(manifest["generation"] == next_generation, "manifest generation mismatch")
        require(manifest["parent_generation"] == generation, "manifest parent mismatch")
        require(manifest["proposal_origin"] == "promoted_editor", "manifest proposal origin mismatch")
        require(index == independent_index(after), "workspace index differs from independent index")
        require(manifest["workspace_index_sha256"] == digest(index), "manifest index hash mismatch")
        for relative in FILE_PATHS:
            require(manifest["files"][relative]["sha256"] == sha256_text(after[relative]), f"manifest file hash mismatch: {relative}")
        candidate = row["candidate"]
        require(candidate["proposal_origin"] == "promoted_editor", "receipt proposal origin mismatch")
        path = str(candidate["changed_path"])
        require(path in FILE_PATHS, "candidate changed unknown file")
        expected = independent_apply(before[path], candidate["patch"])
        require(after[path] == expected, "promoted source differs from independent patch")
        for relative in FILE_PATHS:
            if relative != path:
                require(before[relative] == after[relative], f"unrelated workspace file changed: {relative}")
        require(candidate["files_sha256"] == files_digest(after), "candidate workspace hash mismatch")
        require(candidate["workspace_index_sha256"] == digest(index), "candidate index hash mismatch")
        if path == CORE_PATH:
            check = verify_candidate_source(before[path], after[path], CASES)
            require(check["passed"], f"core candidate failed: {check}")
        elif path == EDITOR_PATH:
            editor_behavior(load_editor(after[path])[0])
        previous_generation = next_generation

    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    final_files = read_files(root, previous_generation)
    final_index = json.loads((generation_path(root, previous_generation) / "workspace-index.json").read_text(encoding="utf-8"))
    require(pointer["generation"] == previous_generation, "current generation mismatch")
    require(pointer["files_sha256"] == files_digest(final_files), "current workspace hash mismatch")
    require(pointer["workspace_index_sha256"] == digest(final_index), "current index pointer mismatch")
    final_manifest = json.loads((generation_path(root, previous_generation) / "manifest.json").read_text(encoding="utf-8"))
    require(pointer["manifest_sha256"] == digest(final_manifest), "current manifest pointer mismatch")
    require(final_index == independent_index(final_files), "final workspace index mismatch")
    for relative in FILE_PATHS:
        require((root / relative).read_text(encoding="utf-8") == final_files[relative], f"live source mismatch: {relative}")
    require((root / "workspace-index.json").read_text(encoding="utf-8").strip() == json.dumps(final_index, ensure_ascii=False, sort_keys=True, separators=(",", ":")), "live index mismatch")

    final_editor = load_editor(final_files[EDITOR_PATH])[0]
    replay = read_files(root, 0)
    for row in transitions:
        path = row["candidate"]["changed_path"]
        replay[path] = final_editor(replay[path], row["candidate"]["patch"])
        expected = read_files(root, int(row["next_generation"]))
        require(replay == expected, "final editor failed workspace replay")

    core_mutation = final_files[CORE_PATH].replace("return 5 * value + 1", "return 5 * value + 2", 1)
    require(not verify_candidate_source(final_files[CORE_PATH], core_mutation, CASES)["passed"], "core mutation accepted")
    editor_mutation = final_files[EDITOR_PATH].replace("return source.replace(find, replacement, 1)", "return source.replace(find, replacement, 0)", 1)
    try:
        editor_behavior(load_editor(editor_mutation)[0])
    except Exception:
        editor_mutation_rejected = True
    else:
        raise RuntimeError("editor mutation accepted")
    index_mutation = dict(final_index, file_count=final_index["file_count"] + 1)
    require(digest(index_mutation) != pointer["workspace_index_sha256"], "index mutation was not detected")
    return {
        "status": "PASS",
        "current_generation": previous_generation,
        "generations": len(transitions),
        "indexed_files": final_index["file_count"],
        "indexed_symbols": final_index["symbol_count"],
        "workspace_replay_verified": True,
        "core_mutation_rejected": True,
        "editor_mutation_rejected": editor_mutation_rejected,
        "index_mutation_rejected": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=CASSIMIND / "workspace-v5")
    args = parser.parse_args()
    print(json.dumps(verify_run(args.root.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
