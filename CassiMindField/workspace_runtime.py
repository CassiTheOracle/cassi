#!/usr/bin/env python3
"""Run field-selected rewrites over an indexed multi-file workspace."""
from __future__ import annotations

import argparse
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
from self_host_runtime import editor_behavior  # noqa: E402

from field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402

SCHEMA = "cassimindfield.workspace-rewrite.v1"
CURRENT_SCHEMA = "cassimindfield.workspace-current.v1"
GENERATION_SCHEMA = "cassimindfield.workspace-generation.v1"
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
INDEX_PATH = "src/workspace_index.py"
FILE_PATHS = (CORE_PATH, EDITOR_PATH, INDEX_PATH)


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def current_path(root: Path) -> Path:
    return root / "current.json"


def file_path(root: Path, generation: int, relative: str) -> Path:
    return generation_path(root, generation) / relative


def index_path(root: Path, generation: int) -> Path:
    return generation_path(root, generation) / "workspace-index.json"


def live_index_path(root: Path) -> Path:
    return root / "workspace-index.json"


def file_digest_map(files: Mapping[str, str]) -> dict[str, str]:
    return {path: sha256_text(files[path]) for path in sorted(files)}


def files_digest(files: Mapping[str, str]) -> str:
    return digest(file_digest_map(files))


def read_files(root: Path, generation: int) -> dict[str, str]:
    files = {}
    for relative in FILE_PATHS:
        path = file_path(root, generation, relative)
        require(path.is_file(), f"workspace source is missing: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def materialize_files(root: Path, files: Mapping[str, str], index: Mapping[str, Any]) -> None:
    for relative, source in files.items():
        atomic_text(root / relative, source)
    atomic_json(live_index_path(root), index)


def load_function(source: str, name: str) -> Callable[..., Any]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_promoted_workspace_module"}
    exec(compile(source, name, "exec"), namespace, namespace)
    function = namespace.get(name)
    require(callable(function), f"workspace module does not define {name}: {name}")
    return function


def load_editor(source: str) -> tuple[Callable[..., Any], Callable[..., Any]]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_promoted_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch = namespace.get("apply_patch")
    propose_candidates = namespace.get("propose_candidates")
    require(callable(apply_patch), "promoted editor lacks apply_patch")
    require(callable(propose_candidates), "promoted editor lacks propose_candidates")
    return apply_patch, propose_candidates


def read_current(root: Path) -> Mapping[str, Any] | None:
    path = current_path(root)
    if not path.exists():
        return None
    pointer = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(pointer, Mapping), "workspace pointer is not an object")
    return pointer


def seed_root(root: Path) -> Path:
    local = root / "seed"
    if local.is_dir():
        return local
    return ROOT / "seed" / "workspace_v5"


def build_index(indexer_source: str, files: Mapping[str, str]) -> dict[str, Any]:
    indexer = load_function(indexer_source, "build_index")
    index = indexer(dict(files))
    require(isinstance(index, dict), "workspace indexer returned invalid index")
    require(index.get("schema") == "cassimindfield.workspace-index.v1", "workspace index schema mismatch")
    return index


def bootstrap(root: Path) -> Mapping[str, Any]:
    existing = read_current(root)
    if existing is not None:
        generation = int(existing["generation"])
        files = read_files(root, generation)
        index = json.loads(index_path(root, generation).read_text(encoding="utf-8"))
        require(files_digest(files) == existing["files_sha256"], "workspace files do not match pointer")
        require(digest(index) == existing["workspace_index_sha256"], "workspace index does not match pointer")
        materialize_files(root, files, index)
        return existing

    source_root = seed_root(root)
    files = {}
    for relative in FILE_PATHS:
        seed = source_root / Path(relative).name
        require(seed.is_file(), f"workspace seed is missing: {seed}")
        files[relative] = seed.read_text(encoding="utf-8")
    index = build_index(files[INDEX_PATH], files)
    for relative, source in files.items():
        atomic_text(file_path(root, 0, relative), source)
    atomic_json(index_path(root, 0), index)
    materialize_files(root, files, index)
    manifest = {
        "schema": GENERATION_SCHEMA,
        "generation": 0,
        "parent_generation": None,
        "files": {
            relative: {
                "sha256": sha256_text(files[relative]),
                "bytes": len(files[relative].encode("utf-8")),
            }
            for relative in FILE_PATHS
        },
        "workspace_index_sha256": digest(index),
        "proposal_origin": "seed",
        "patch": None,
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


def candidate_rows(files: Mapping[str, str]) -> list[dict[str, Any]]:
    apply_patch, propose_candidates = load_editor(files[EDITOR_PATH])
    proposals = propose_candidates(dict(files))
    require(isinstance(proposals, list), "promoted editor returned invalid proposals")
    rows = []
    for proposal in proposals:
        require(isinstance(proposal, Mapping), "promoted editor proposal is invalid")
        path = proposal.get("path")
        candidate_id = proposal.get("candidate_id")
        task_id = proposal.get("task_id")
        require(path in FILE_PATHS, f"proposal targets unknown path: {path}")
        require(isinstance(candidate_id, str) and candidate_id, "proposal candidate id is invalid")
        require(isinstance(task_id, str) and task_id, "proposal task id is invalid")
        patch = {
            key: proposal[key]
            for key in ("schema", "operation", "path", "find", "replace", "base_source_sha256")
            if key in proposal
        }
        candidate_files = dict(files)
        try:
            candidate_files[path] = apply_patch(files[path], patch)
        except Exception:
            continue
        if path == CORE_PATH:
            optimization = evaluate_source_candidate(files[path], candidate_files[path], CASES)
            if not optimization.equivalent or not optimization.improved:
                continue
            original_steps = optimization.original_steps
            candidate_steps = optimization.candidate_steps
        elif path == EDITOR_PATH:
            try:
                editor_behavior(load_editor(candidate_files[path])[0])
            except Exception:
                continue
            original_steps = len(files[path].splitlines())
            candidate_steps = len(candidate_files[path].splitlines())
            if candidate_steps >= original_steps:
                continue
        else:
            continue
        try:
            candidate_index = build_index(candidate_files[INDEX_PATH], candidate_files)
        except Exception:
            continue
        rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_origin": "verified_pool",
                "proposal_origin": "promoted_editor",
                "task_id": task_id,
                "changed_path": path,
                "candidate_sha256": files_digest(candidate_files),
                "candidate_steps": candidate_steps,
                "original_steps": original_steps,
                "improved": True,
                "status": "PASS",
                "patch": patch,
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
    receipt_path = root / "workspace-receipt.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    transitions = list(prior.get("transitions", []))
    initial_transition_count = len(transitions)
    transitions = reconcile_transitions(root, pointer, transitions)
    awaiting_review = False
    memory_home = root / "state" / "field-memory"
    with CassiFieldWorkMemory(memory_home) as memory:
        controller = TeacherFieldController(memory, run_id=f"cassimindfield:workspace-v5:{sha256_text(str(root.resolve()))[:16]}")
        for _ in range(cycles):
            generation = int(pointer["generation"])
            files = read_files(root, generation)
            index = json.loads(index_path(root, generation).read_text(encoding="utf-8"))
            require(files_digest(files) == pointer["files_sha256"], "workspace files do not match pointer")
            require(digest(index) == pointer["workspace_index_sha256"], "workspace index does not match pointer")
            candidates = candidate_rows(files)
            if not candidates:
                break
            descriptors = [
                {key: row[key] for key in ("candidate_id", "candidate_origin", "task_id", "candidate_sha256", "candidate_steps", "improved", "status")}
                for row in candidates
            ]
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
                require(selected is not None, "field selected an unknown workspace candidate")
                candidate_files = selected["candidate_files"]
                candidate_index = selected["candidate_index"]
                if selected["changed_path"] == CORE_PATH:
                    check = verify_candidate_source(files[CORE_PATH], candidate_files[CORE_PATH], CASES)
                else:
                    editor_behavior(load_editor(candidate_files[EDITOR_PATH])[0])
                    check = {"passed": True, "original_steps": selected["original_steps"], "candidate_steps": selected["candidate_steps"], "equivalent": True, "improved": True, "status": "PASS"}
                require(check["passed"], "workspace candidate failed independent check")
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
                    atomic_text(file_path(root, next_generation, relative), source)
                atomic_json(index_path(root, next_generation), candidate_index)
                materialize_files(root, candidate_files, candidate_index)
                manifest = {
                    "schema": GENERATION_SCHEMA,
                    "generation": next_generation,
                    "parent_generation": generation,
                    "candidate_id": selected["candidate_id"],
                    "responsibility_continuity": responsibility_continuity,
                    "files": {relative: {"sha256": sha256_text(candidate_files[relative]), "bytes": len(candidate_files[relative].encode("utf-8"))} for relative in FILE_PATHS},
                    "workspace_index_sha256": digest(candidate_index),
                    "changed_path": selected["changed_path"],
                    "proposal_origin": selected["proposal_origin"],
                    "patch": dict(selected["patch"]),
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
                        "changed_path": selected["changed_path"],
                        "proposal_origin": selected["proposal_origin"],
                        "files_sha256": selected["candidate_sha256"],
                        "workspace_index_sha256": digest(candidate_index),
                        "patch": dict(selected["patch"]),
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
    parser.add_argument("--root", type=Path, default=ROOT / "workspace-v5")
    parser.add_argument("--cycles", type=int, default=4)
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
