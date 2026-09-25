#!/usr/bin/env python3
"""Promote AST-selected multi-file patch sets over a dependency-linked workspace."""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    CASES,
    CassiFieldWorkMemory,
    TeacherFieldController,
    atomic_json,
    atomic_text,
    digest,
    evaluate_source_candidate,
    finish_transition,
    reconcile_transitions,
    require,
    sha256_text,
    stage_transition,
    verify_candidate_source,
)

from field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402

SCHEMA = "cassimindfield.patchset-rewrite.v1"
CURRENT_SCHEMA = "cassimindfield.patchset-current.v1"
GENERATION_SCHEMA = "cassimindfield.patchset-generation.v1"
CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
INDEX_PATH = "src/workspace_index.py"
RUNTIME_PATH = "src/field_runtime.py"
FILE_PATHS = (CORE_PATH, EDITOR_PATH, INDEX_PATH, RUNTIME_PATH)
PATCH_SET_SCHEMA = "cassimindfield.patch-set.v1"


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def current_path(root: Path) -> Path:
    return root / "current.json"


def source_path(root: Path, generation: int, relative: str) -> Path:
    return generation_path(root, generation) / relative


def index_path(root: Path, generation: int) -> Path:
    return generation_path(root, generation) / "workspace-index.json"


def file_digest_map(files: Mapping[str, str]) -> dict[str, str]:
    return {path: sha256_text(files[path]) for path in sorted(files)}


def files_digest(files: Mapping[str, str]) -> str:
    return digest(file_digest_map(files))


def read_files(root: Path, generation: int) -> dict[str, str]:
    files = {}
    for relative in FILE_PATHS:
        path = source_path(root, generation, relative)
        require(path.is_file(), f"workspace source missing: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def materialize(root: Path, files: Mapping[str, str], index: Mapping[str, Any]) -> None:
    for relative, source in files.items():
        atomic_text(root / relative, source)
    atomic_json(root / "workspace-index.json", index)


def load_editor(source: str) -> tuple[Callable[..., Any], Callable[..., Any]]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_patchset_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch_set = namespace.get("apply_patch_set")
    propose_candidates = namespace.get("propose_candidates")
    require(callable(apply_patch_set), "patch-set editor lacks apply_patch_set")
    require(callable(propose_candidates), "patch-set editor lacks propose_candidates")
    return apply_patch_set, propose_candidates


def load_indexer(source: str) -> Callable[..., Any]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_patchset_indexer"}
    exec(compile(source, INDEX_PATH, "exec"), namespace, namespace)
    indexer = namespace.get("build_index")
    require(callable(indexer), "workspace indexer lacks build_index")
    return indexer


def build_index(files: Mapping[str, str]) -> dict[str, Any]:
    index = load_indexer(files[INDEX_PATH])(dict(files))
    require(isinstance(index, dict), "workspace indexer returned invalid result")
    require(index.get("schema") == "cassimindfield.workspace-index.v1", "workspace index schema mismatch")
    return index


def read_pointer(root: Path) -> Mapping[str, Any] | None:
    path = current_path(root)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, Mapping), "patch-set pointer is not an object")
    return value


def seed_root(root: Path) -> Path:
    local = root / "seed"
    return local if local.is_dir() else ROOT / "seed" / "patchset_v6"


def bootstrap(root: Path) -> Mapping[str, Any]:
    existing = read_pointer(root)
    if existing is not None:
        generation = int(existing["generation"])
        files = read_files(root, generation)
        index = json.loads(index_path(root, generation).read_text(encoding="utf-8"))
        require(files_digest(files) == existing["files_sha256"], "current files do not match pointer")
        require(digest(index) == existing["workspace_index_sha256"], "current index does not match pointer")
        materialize(root, files, index)
        return existing
    source_root = seed_root(root)
    files = {}
    for relative in FILE_PATHS:
        seed = source_root / Path(relative).name
        require(seed.is_file(), f"patch-set seed missing: {seed}")
        files[relative] = seed.read_text(encoding="utf-8")
    index = build_index(files)
    for relative, source in files.items():
        atomic_text(source_path(root, 0, relative), source)
    atomic_json(index_path(root, 0), index)
    materialize(root, files, index)
    manifest = {
        "schema": GENERATION_SCHEMA,
        "generation": 0,
        "parent_generation": None,
        "files": {relative: {"sha256": sha256_text(files[relative]), "bytes": len(files[relative].encode("utf-8"))} for relative in FILE_PATHS},
        "workspace_index_sha256": digest(index),
        "changed_paths": [],
        "proposal_origin": "seed",
        "patch_set": None,
    }
    atomic_json(generation_path(root, 0) / "manifest.json", manifest)
    pointer = {
        "schema": CURRENT_SCHEMA,
        "generation": 0,
        "files_sha256": files_digest(files),
        "workspace_index_sha256": digest(index),
        "manifest_sha256": digest(manifest),
    }
    atomic_json(current_path(root), pointer)
    return pointer


def editor_behavior(apply_patch_set: Callable[..., Any]) -> None:
    source = "alpha + beta"
    patch = {
        "schema": "cassimindfield.source-edit.v1",
        "operation": "replace_once",
        "path": EDITOR_PATH,
        "find": "alpha",
        "replace": "gamma",
        "base_source_sha256": sha256_text(source),
    }
    patch_set = {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [patch]}
    require(apply_patch_set({EDITOR_PATH: source}, patch_set)[EDITOR_PATH] == "gamma + beta", "editor valid case failed")
    for invalid in ("alpha alpha", "beta"):
        bad = dict(patch, base_source_sha256=sha256_text(invalid))
        try:
            apply_patch_set({EDITOR_PATH: invalid}, {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [bad]})
        except Exception:
            continue
        raise RuntimeError("editor accepted invalid match")


def candidate_rows(files: Mapping[str, str]) -> list[dict[str, Any]]:
    apply_patch_set, propose_candidates = load_editor(files[EDITOR_PATH])
    proposals = propose_candidates(dict(files))
    require(isinstance(proposals, list), "promoted editor returned invalid patch-set list")
    rows = []
    for proposal in proposals:
        require(isinstance(proposal, Mapping), "patch-set proposal is invalid")
        require(proposal.get("schema") == PATCH_SET_SCHEMA, "patch-set proposal schema mismatch")
        require(proposal.get("operation") == "apply_patch_set", "patch-set proposal operation mismatch")
        candidate_id = proposal.get("candidate_id")
        task_id = proposal.get("task_id")
        changes = proposal.get("changes")
        require(isinstance(candidate_id, str) and candidate_id, "patch-set candidate id is invalid")
        require(isinstance(task_id, str) and task_id, "patch-set task id is invalid")
        require(isinstance(changes, list) and changes, "patch-set changes are invalid")
        try:
            candidate_files = apply_patch_set(dict(files), proposal)
        except Exception:
            continue
        changed_paths = sorted({str(change.get("path")) for change in changes})
        if any(path not in FILE_PATHS for path in changed_paths):
            continue
        try:
            for source in candidate_files.values():
                ast.parse(source)
            candidate_index = build_index(candidate_files)
        except Exception:
            continue
        if CORE_PATH in changed_paths:
            optimization = evaluate_source_candidate(files[CORE_PATH], candidate_files[CORE_PATH], CASES)
            if not optimization.equivalent or not optimization.improved:
                continue
            original_steps = optimization.original_steps
            candidate_steps = optimization.candidate_steps
        elif EDITOR_PATH in changed_paths:
            try:
                editor_behavior(load_editor(candidate_files[EDITOR_PATH])[0])
            except Exception:
                continue
            original_steps = len(files[EDITOR_PATH].splitlines())
            candidate_steps = len(candidate_files[EDITOR_PATH].splitlines())
            if candidate_steps >= original_steps:
                continue
        else:
            continue
        rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_origin": "verified_pool",
                "proposal_origin": "promoted_editor",
                "task_id": task_id,
                "changed_paths": changed_paths,
                "candidate_sha256": files_digest(candidate_files),
                "candidate_steps": candidate_steps,
                "original_steps": original_steps,
                "improved": True,
                "status": "PASS",
                "patch_set": dict(proposal),
                "candidate_files": candidate_files,
                "candidate_index": candidate_index,
            }
        )
    unique = {}
    for row in rows:
        unique.setdefault(row["candidate_sha256"], row)
    return list(unique.values())


def run(
    root: Path,
    cycles: int,
    *,
    field_owner_url: str | None = None,
    owner_client: Any | None = None,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    if field_owner_url is None:
        field_owner_url = os.environ.get(
            "CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090"
        )
    gate = RewriteOwnerGate(
        root.resolve(), field_owner_url=field_owner_url,
        owner_client=owner_client,
    )
    pointer = bootstrap(root)
    receipt_path = root / "patchset-receipt.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    transitions = list(prior.get("transitions", []))
    initial_transition_count = len(transitions)
    transitions = reconcile_transitions(root, pointer, transitions)
    awaiting_review = False
    with CassiFieldWorkMemory(root / "state" / "field-memory") as memory:
        controller = TeacherFieldController(memory, run_id=f"cassimindfield:patchset-v6:{sha256_text(str(root.resolve()))[:16]}")
        for _ in range(cycles):
            generation = int(pointer["generation"])
            files = read_files(root, generation)
            index = json.loads(index_path(root, generation).read_text(encoding="utf-8"))
            require(files_digest(files) == pointer["files_sha256"], "current files do not match pointer")
            require(digest(index) == pointer["workspace_index_sha256"], "current index does not match pointer")
            candidates = candidate_rows(files)
            if not candidates:
                break
            descriptors = [{key: row[key] for key in ("candidate_id", "candidate_origin", "task_id", "candidate_sha256", "candidate_steps", "improved", "status")} for row in candidates]
            try:
                gate.start(generation)
                begin = controller.begin(
                    generation=generation,
                    attempt=0,
                    previous_source_sha256=pointer["files_sha256"],
                    candidate_descriptors=descriptors,
                    planned_edit_id=str(candidates[0]["candidate_id"]),
                    thinking_max_tokens=1,
                )
                action = begin["action"]
                selected = next((row for row in candidates if row["candidate_id"] == action["candidate_id"]), None)
                require(selected is not None, "field selected unknown patch set")
                candidate_files = selected["candidate_files"]
                candidate_index = selected["candidate_index"]
                if CORE_PATH in selected["changed_paths"]:
                    check = verify_candidate_source(files[CORE_PATH], candidate_files[CORE_PATH], CASES)
                else:
                    editor_behavior(load_editor(candidate_files[EDITOR_PATH])[0])
                    check = {"passed": True, "original_steps": selected["original_steps"], "candidate_steps": selected["candidate_steps"], "equivalent": True, "improved": True, "status": "PASS"}
                require(check["passed"], "patch-set candidate failed independent check")
                next_generation = generation + 1
                responsibility_continuity = gate.before_promotion(next_generation)
                outcome = controller.observe_outcome(
                    begin,
                    status="PASS",
                    candidate_origin="verified_pool",
                    candidate_sha256=selected["candidate_sha256"],
                    task_id=selected["task_id"],
                    candidate_steps=int(check["candidate_steps"]),
                    original_steps=int(check["original_steps"]),
                    reasoning_chars=0,
                    completion_tokens=0,
                    thinking_requested=False,
                    thinking_effective=False,
                )
                for relative, source in candidate_files.items():
                    atomic_text(source_path(root, next_generation, relative), source)
                atomic_json(index_path(root, next_generation), candidate_index)
                materialize(root, candidate_files, candidate_index)
                manifest = {
                    "schema": GENERATION_SCHEMA,
                    "generation": next_generation,
                    "parent_generation": generation,
                    "candidate_id": selected["candidate_id"],
                    "responsibility_continuity": responsibility_continuity,
                    "files": {relative: {"sha256": sha256_text(candidate_files[relative]), "bytes": len(candidate_files[relative].encode("utf-8"))} for relative in FILE_PATHS},
                    "workspace_index_sha256": digest(candidate_index),
                    "changed_paths": selected["changed_paths"],
                    "proposal_origin": selected["proposal_origin"],
                    "patch_set": dict(selected["patch_set"]),
                    "field_action_id": action["action_id"],
                }
                atomic_json(generation_path(root, next_generation) / "manifest.json", manifest)
                next_pointer = {
                    "schema": CURRENT_SCHEMA,
                    "generation": next_generation,
                    "files_sha256": files_digest(candidate_files),
                    "workspace_index_sha256": digest(candidate_index),
                    "manifest_sha256": digest(manifest),
                }
                transition = {
                    "generation": generation,
                    "next_generation": next_generation,
                    "field_action": dict(action),
                    "candidate": {
                        "candidate_id": selected["candidate_id"],
                        "task_id": selected["task_id"],
                        "changed_paths": selected["changed_paths"],
                        "proposal_origin": selected["proposal_origin"],
                        "files_sha256": selected["candidate_sha256"],
                        "workspace_index_sha256": digest(candidate_index),
                        "patch_set": dict(selected["patch_set"]),
                    },
                    "verification": check,
                    "field_outcome": dict(outcome),
                    "responsibility_review": {"status": "pending-delivery"},
                }
                stage_transition(root, next_pointer, transition)
                atomic_json(current_path(root), next_pointer)
                pointer = next_pointer
                owner_review = gate.promoted(next_generation)
                finish_transition(root, pointer, transition, owner_review)
                transitions.append(transition)
            except PendingRewriteReview:
                gate.abort(generation)
                if len(transitions) == initial_transition_count:
                    raise
                awaiting_review = True
                break
            except Exception:
                gate.abort(generation)
                raise
    receipt = {
        "schema": SCHEMA,
        "status": "awaiting-review" if awaiting_review else "complete",
        "files": list(FILE_PATHS),
        "cycles_requested": int(prior.get("cycles_requested", 0)) + cycles,
        "transitions": transitions,
        "current": dict(pointer),
    }
    atomic_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / "patchset-v6")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument(
        "--field-owner-url",
        default=os.environ.get("CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090"),
        help="loopback entity API serving the continuing field owner",
    )
    args = parser.parse_args()
    result = run(
        args.root.resolve(),
        args.cycles,
        field_owner_url=args.field_owner_url,
    )
    print(json.dumps({"status": result["status"], "current_generation": result["current"]["generation"], "generations": len(result["transitions"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
