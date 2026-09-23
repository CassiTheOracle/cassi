#!/usr/bin/env python3
"""Independently verify a multi-file CassiMindField self-host receipt."""
from __future__ import annotations

import argparse
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
FILE_PATHS = (CORE_PATH, EDITOR_PATH)
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
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
        require(path.is_file(), f"missing generation file: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def file_digest_map(files: Mapping[str, str]) -> dict[str, str]:
    return {path: sha256_text(files[path]) for path in sorted(files)}


def files_digest(files: Mapping[str, str]) -> str:
    return digest(file_digest_map(files))


def load_editor(source: str) -> Callable[[str, Mapping[str, Any]], str]:
    namespace: dict[str, Any] = {"__name__": "independent_cassimindfield_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    editor = namespace.get("apply_patch")
    require(callable(editor), "editor source does not define apply_patch")
    return editor


def independent_apply(source: str, patch: Mapping[str, Any]) -> str:
    require(patch.get("schema") == PATCH_SCHEMA, "patch schema mismatch")
    require(patch.get("operation") == "replace_once", "patch operation mismatch")
    require(patch.get("base_source_sha256") == sha256_text(source), "patch base hash mismatch")
    find = patch.get("find")
    replacement = patch.get("replace")
    require(isinstance(find, str) and find, "patch find is invalid")
    require(isinstance(replacement, str), "patch replacement is invalid")
    require(source.count(find) == 1, "patch does not match exactly once")
    return source.replace(find, replacement, 1)


def verify_editor_behavior(editor: Callable[[str, Mapping[str, Any]], str]) -> None:
    valid_source = "alpha + beta"
    valid_patch = {
        "schema": PATCH_SCHEMA,
        "operation": "replace_once",
        "path": CORE_PATH,
        "find": "alpha",
        "replace": "gamma",
        "base_source_sha256": sha256_text(valid_source),
    }
    require(editor(valid_source, valid_patch) == "gamma + beta", "editor valid behavior failed")
    for source in ("alpha alpha", "beta"):
        patch = dict(valid_patch, base_source_sha256=sha256_text(source))
        try:
            editor(source, patch)
        except Exception:
            continue
        raise RuntimeError("editor accepted invalid match cardinality")


def verify_run(root: Path) -> dict[str, Any]:
    receipt = json.loads((root / "self-host-receipt.json").read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassimindfield.self-host.v1", "receipt schema mismatch")
    transitions = receipt.get("transitions")
    require(isinstance(transitions, list) and transitions, "receipt has no transitions")

    previous_generation = 0
    for row in transitions:
        generation = int(row["generation"])
        next_generation = int(row["next_generation"])
        require(generation == previous_generation, "generation lineage is not contiguous")
        require(next_generation == generation + 1, "generation increment is invalid")
        before = read_files(root, generation)
        after = read_files(root, next_generation)
        manifest = json.loads((generation_path(root, next_generation) / "manifest.json").read_text(encoding="utf-8"))
        require(manifest["schema"] == "cassimindfield.self-host.generation.v1", "manifest schema mismatch")
        require(manifest["generation"] == next_generation, "manifest generation mismatch")
        require(manifest["parent_generation"] == generation, "manifest parent mismatch")
        require(manifest["proposal_origin"] == "promoted_editor", "manifest proposal origin mismatch")
        require(row["candidate"]["proposal_origin"] == "promoted_editor", "receipt proposal origin mismatch")
        for relative in FILE_PATHS:
            entry = manifest["files"][relative]
            require(entry["sha256"] == sha256_text(after[relative]), f"manifest hash mismatch: {relative}")
        patch = row["candidate"]["patch"]
        path = str(row["candidate"]["changed_path"])
        require(path in FILE_PATHS, "candidate changed unknown file")
        expected_changed = independent_apply(before[path], patch)
        require(after[path] == expected_changed, "promoted file is not the independent patch result")
        for relative in FILE_PATHS:
            if relative != path:
                require(after[relative] == before[relative], f"unrelated file changed: {relative}")
        require(row["candidate"]["files_sha256"] == files_digest(after), "candidate files hash mismatch")
        if path == CORE_PATH:
            check = verify_candidate_source(before[CORE_PATH], after[CORE_PATH], CASES)
            require(check["passed"], f"core candidate failed: {check}")
        else:
            verify_editor_behavior(load_editor(after[EDITOR_PATH]))
        previous_generation = next_generation

    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    final_files = read_files(root, previous_generation)
    require(pointer["generation"] == previous_generation, "current generation mismatch")
    require(pointer["files_sha256"] == files_digest(final_files), "current files hash mismatch")
    final_manifest = json.loads((generation_path(root, previous_generation) / "manifest.json").read_text(encoding="utf-8"))
    require(pointer["manifest_sha256"] == digest(final_manifest), "current manifest hash mismatch")
    for relative in FILE_PATHS:
        live = (root / relative).read_text(encoding="utf-8")
        require(live == final_files[relative], f"live source mismatch: {relative}")
    final_namespace: dict[str, Any] = {"__name__": "independent_cassimindfield_editor"}
    exec(compile(final_files[EDITOR_PATH], EDITOR_PATH, "exec"), final_namespace, final_namespace)
    require(callable(final_namespace.get("propose_candidates")), "final editor lacks candidate proposer")

    final_editor = load_editor(final_files[EDITOR_PATH])
    replay_files = read_files(root, 0)
    for row in transitions:
        path = str(row["candidate"]["changed_path"])
        replay_files[path] = final_editor(replay_files[path], row["candidate"]["patch"])
        expected = read_files(root, int(row["next_generation"]))
        require(replay_files == expected, "final editor failed historical replay")

    core_mutation = final_files[CORE_PATH].replace("return 5 * value + 1", "return 5 * value + 2", 1)
    require(core_mutation != final_files[CORE_PATH], "core mutation did not mutate source")
    core_check = verify_candidate_source(final_files[CORE_PATH], core_mutation, CASES)
    require(not core_check["passed"], "core mutation was accepted")

    editor_mutation = final_files[EDITOR_PATH].replace(
        "return source.replace(find, replacement, 1)",
        "return source.replace(find, replacement, 0)",
        1,
    )
    require(editor_mutation != final_files[EDITOR_PATH], "editor mutation did not mutate source")
    try:
        verify_editor_behavior(load_editor(editor_mutation))
    except Exception:
        editor_mutation_rejected = True
    else:
        raise RuntimeError("editor mutation was accepted")

    return {
        "status": "PASS",
        "generations": len(transitions),
        "current_generation": previous_generation,
        "promoted_editor_proposals_verified": True,
        "core_mutation_rejected": True,
        "editor_mutation_rejected": editor_mutation_rejected,
        "field_state_sha256": receipt.get("field_state", {}).get("field_state_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=CASSIMIND / "self-host")
    args = parser.parse_args()
    result = verify_run(args.root.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
