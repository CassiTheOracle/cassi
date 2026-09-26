#!/usr/bin/env python3
"""Run a bounded self-hosting rewrite of the Mind Field core and editor.

The immutable supervisor stays outside the target.  Each generation contains
both the field core and the source editor; candidates are applied through the
currently promoted editor and then checked by an independent verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
CASSIQWEN = WORKSPACE / "CassiQwen"
CASSIRESEARCH = CASSIQWEN / "research"
CASSIFI = WORKSPACE / "CassiFI"
for path in (CASSIQWEN, CASSIRESEARCH, CASSIFI):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cassi_field_qwen_workbench import CassiFieldWorkMemory  # noqa: E402
from cassi_python import PythonCase, evaluate_source_candidate  # noqa: E402
from cassi_teacher_field import TeacherFieldController  # noqa: E402
from verify_cassi_mind_field import verify_candidate_source  # noqa: E402
if __package__:
    from .field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402
else:
    from field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402
from runtime import (  # noqa: E402
    atomic_json,
    atomic_text,
    canonical,
    digest,
    finish_transition,
    reconcile_transitions,
    require,
    sha256_text,
    stage_transition,
)

SCHEMA = "cassimindfield.self-host.v1"
CURRENT_SCHEMA = "cassimindfield.self-host.current.v1"
GENERATION_SCHEMA = "cassimindfield.self-host.generation.v1"
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
FILE_PATHS = (CORE_PATH, EDITOR_PATH)
CASES = (
    PythonCase("negative", {"value": -7}, -34),
    PythonCase("zero", {"value": 0}, 1),
    PythonCase("positive", {"value": 9}, 46),
    PythonCase("large", {"value": 123}, 616),
)


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def current_path(root: Path) -> Path:
    return root / "current.json"


def file_path(root: Path, generation: int, relative: str) -> Path:
    return generation_path(root, generation) / relative


def file_digest_map(files: Mapping[str, str]) -> dict[str, str]:
    return {path: sha256_text(files[path]) for path in sorted(files)}


def files_digest(files: Mapping[str, str]) -> str:
    return digest(file_digest_map(files))


def read_files(root: Path, generation: int) -> dict[str, str]:
    files = {}
    for relative in FILE_PATHS:
        path = file_path(root, generation, relative)
        require(path.is_file(), f"generation file is missing: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def materialize_files(root: Path, files: Mapping[str, str]) -> None:
    for relative, source in files.items():
        atomic_text(root / relative, source)


def load_editor(source: str) -> Callable[[str, Mapping[str, Any]], str]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_promoted_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    editor = namespace.get("apply_patch")
    require(callable(editor), "promoted editor does not define apply_patch")
    return editor


def read_current(root: Path) -> Mapping[str, Any] | None:
    path = current_path(root)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, Mapping), "self-host current pointer is not an object")
    return value


def bootstrap(root: Path) -> Mapping[str, Any]:
    existing = read_current(root)
    if existing is not None:
        generation = int(existing["generation"])
        files = read_files(root, generation)
        require(files_digest(files) == existing["files_sha256"], "current files do not match pointer")
        materialize_files(root, files)
        return existing
    seed_root = root / "seed"
    if not seed_root.is_dir():
        seed_root = ROOT / "seed" / "self_host"
    files = {}
    for relative in FILE_PATHS:
        seed = seed_root / Path(relative).name
        require(seed.is_file(), f"self-host seed is missing: {seed}")
        files[relative] = seed.read_text(encoding="utf-8")
    for relative, source in files.items():
        atomic_text(file_path(root, 0, relative), source)
    materialize_files(root, files)
    manifest = {
        "schema": GENERATION_SCHEMA,
        "generation": 0,
        "parent_generation": None,
        "files": {
            path: {
                "sha256": sha256_text(files[path]),
                "bytes": len(files[path].encode("utf-8")),
            }
            for path in FILE_PATHS
        },
        "patch": None,
    }
    atomic_json(generation_path(root, 0) / "manifest.json", manifest)
    pointer = {
        "schema": CURRENT_SCHEMA,
        "generation": 0,
        "files_sha256": files_digest(files),
        "manifest_sha256": digest(manifest),
    }
    atomic_json(current_path(root), pointer)
    return pointer




def editor_behavior(editor: Callable[[str, Mapping[str, Any]], str]) -> dict[str, Any]:
    valid_source = "alpha + beta"
    valid_patch = {
        "schema": PATCH_SCHEMA,
        "operation": "replace_once",
        "path": CORE_PATH,
        "find": "alpha",
        "replace": "gamma",
        "base_source_sha256": sha256_text(valid_source),
    }
    require(editor(valid_source, valid_patch) == "gamma + beta", "editor valid case failed")
    duplicate_source = "alpha alpha"
    duplicate_patch = dict(valid_patch, base_source_sha256=sha256_text(duplicate_source))
    try:
        editor(duplicate_source, duplicate_patch)
    except Exception:
        pass
    else:
        raise RuntimeError("editor accepted duplicate match")
    missing_source = "beta"
    missing_patch = dict(valid_patch, base_source_sha256=sha256_text(missing_source))
    try:
        editor(missing_source, missing_patch)
    except Exception:
        pass
    else:
        raise RuntimeError("editor accepted missing match")
    return {"passed": True, "cases": 3}


def candidate_rows(files: Mapping[str, str]) -> list[dict[str, Any]]:
    editor = load_editor(files[EDITOR_PATH])
    namespace: dict[str, Any] = {"__name__": "cassimindfield_promoted_editor"}
    exec(compile(files[EDITOR_PATH], EDITOR_PATH, "exec"), namespace, namespace)
    proposer = namespace.get("propose_candidates")
    require(callable(proposer), "promoted editor does not define propose_candidates")
    proposals = proposer(dict(files))
    require(isinstance(proposals, list), "promoted editor returned invalid candidate list")
    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        require(isinstance(proposal, Mapping), "promoted editor returned invalid candidate")
        candidate_id = proposal.get("candidate_id")
        task_id = proposal.get("task_id")
        path = proposal.get("path")
        require(isinstance(candidate_id, str) and candidate_id, "candidate id is invalid")
        require(isinstance(task_id, str) and task_id, "candidate task is invalid")
        require(path in FILE_PATHS, f"candidate path is invalid: {path}")
        patch = {
            key: proposal[key]
            for key in (
                "schema",
                "operation",
                "path",
                "find",
                "replace",
                "base_source_sha256",
            )
            if key in proposal
        }
        candidate_files = dict(files)
        try:
            candidate_files[path] = editor(files[path], patch)
        except Exception:
            continue
        if path == CORE_PATH:
            optimization = evaluate_source_candidate(files[path], candidate_files[path], CASES)
            if not optimization.equivalent or not optimization.improved:
                continue
            check = {
                "passed": True,
                "equivalent": optimization.equivalent,
                "improved": optimization.improved,
                "status": optimization.status,
                "original_steps": optimization.original_steps,
                "candidate_steps": optimization.candidate_steps,
            }
        else:
            try:
                editor_behavior(load_editor(candidate_files[path]))
            except Exception:
                continue
            original_steps = len(files[path].splitlines())
            candidate_steps = len(candidate_files[path].splitlines())
            if candidate_steps >= original_steps:
                continue
            check = {
                "passed": True,
                "equivalent": True,
                "improved": True,
                "status": "PASS",
                "original_steps": original_steps,
                "candidate_steps": candidate_steps,
            }
        rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_origin": "verified_pool",
                "proposal_origin": "promoted_editor",
                "task_id": task_id,
                "changed_path": path,
                "candidate_sha256": files_digest(candidate_files),
                "candidate_steps": check["candidate_steps"],
                "original_steps": check["original_steps"],
                "improved": True,
                "status": "PASS",
                "patch": patch,
                "candidate_files": candidate_files,
            }
        )
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(str(row["candidate_sha256"]), row)
    return list(unique.values())


def run(
    root: Path,
    cycles: int,
    *,
    field_owner_url: str | None = None,
    owner_client: Any | None = None,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    owner_gate = RewriteOwnerGate(
        root,
        field_owner_url=(
            field_owner_url
            if field_owner_url is not None
            else os.environ.get("CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090")
        ),
        owner_client=owner_client,
    )
    pointer = bootstrap(root)
    receipt_path = root / "self-host-receipt.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    transitions: list[dict[str, Any]] = list(prior.get("transitions", []))
    initial_transition_count = len(transitions)
    transitions = reconcile_transitions(root, pointer, transitions)
    awaiting_review = False
    memory_home = root / "state" / "field-memory"
    with CassiFieldWorkMemory(memory_home) as memory:
        controller = TeacherFieldController(
            memory,
            run_id=f"cassimindfield:self-host:v2:{sha256_text(str(root.resolve()))[:16]}",
        )
        for _ in range(cycles):
            generation = int(pointer["generation"])
            files = read_files(root, generation)
            current_digest = files_digest(files)
            require(current_digest == pointer["files_sha256"], "current files do not match pointer")
            candidates = candidate_rows(files)
            if not candidates:
                break
            try:
                owner_gate.start(generation)
                descriptors = [
                    {
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "candidate_origin",
                            "task_id",
                            "candidate_sha256",
                            "candidate_steps",
                            "improved",
                            "status",
                        )
                    }
                    for row in candidates
                ]
                planned = str(candidates[0]["candidate_id"])
                field_begin = controller.begin(
                    generation=generation,
                    attempt=0,
                    previous_source_sha256=current_digest,
                    candidate_descriptors=descriptors,
                    planned_edit_id=planned,
                    thinking_max_tokens=1,
                )
                action = field_begin["action"]
                selected_id = str(action["candidate_id"])
                selected = next((row for row in candidates if row["candidate_id"] == selected_id), None)
                require(selected is not None, f"field selected unknown candidate: {selected_id}")
                candidate_files = dict(selected["candidate_files"])
                path = str(selected["changed_path"])
                if path == CORE_PATH:
                    check = verify_candidate_source(files[CORE_PATH], candidate_files[CORE_PATH], CASES)
                else:
                    check = editor_behavior(load_editor(candidate_files[EDITOR_PATH]))
                    check = {
                        **check,
                        "original_steps": selected["original_steps"],
                        "candidate_steps": selected["candidate_steps"],
                        "equivalent": True,
                        "improved": True,
                        "status": "equivalent",
                    }
                next_generation = generation + 1
                responsibility_continuity = owner_gate.before_promotion(next_generation)
                status = "PASS" if check["passed"] else "REJECT"
                field_outcome = controller.observe_outcome(
                    field_begin,
                    status=status,
                    candidate_origin="verified_pool",
                    candidate_sha256=str(selected["candidate_sha256"]),
                    task_id=str(selected["task_id"]),
                    candidate_steps=int(check["candidate_steps"]),
                    original_steps=int(check["original_steps"]),
                    reasoning_chars=0,
                    completion_tokens=0,
                    thinking_requested=False,
                    thinking_effective=False,
                )
                require(check["passed"], f"candidate failed independent verification: {check}")
                for relative, source in candidate_files.items():
                    atomic_text(file_path(root, next_generation, relative), source)
                materialize_files(root, candidate_files)
                manifest = {
                    "schema": GENERATION_SCHEMA,
                    "generation": next_generation,
                    "parent_generation": generation,
                    "files": {
                        relative: {
                            "sha256": sha256_text(candidate_files[relative]),
                            "bytes": len(candidate_files[relative].encode("utf-8")),
                        }
                        for relative in FILE_PATHS
                    },
                    "candidate_id": selected_id,
                    "responsibility_continuity": responsibility_continuity,
                    "changed_path": path,
                    "proposal_origin": selected["proposal_origin"],
                    "patch": dict(selected["patch"]),
                    "field_action_id": action["action_id"],
                }
                atomic_json(generation_path(root, next_generation) / "manifest.json", manifest)
                next_pointer = {
                    "schema": CURRENT_SCHEMA,
                    "generation": next_generation,
                    "files_sha256": files_digest(candidate_files),
                    "manifest_sha256": digest(manifest),
                }
                transition = {
                    "generation": generation,
                    "next_generation": next_generation,
                    "field_action": dict(action),
                    "field_begin": dict(field_begin),
                    "candidate": {
                        "candidate_id": selected_id,
                        "task_id": selected["task_id"],
                        "changed_path": path,
                        "proposal_origin": selected["proposal_origin"],
                        "files_sha256": selected["candidate_sha256"],
                        "patch": dict(selected["patch"]),
                    },
                    "verification": check,
                    "field_outcome": dict(field_outcome),
                    "responsibility_review": {"status": "pending-delivery"},
                }
                stage_transition(root, next_pointer, transition)
                atomic_json(current_path(root), next_pointer)
                pointer = next_pointer
                owner_review = owner_gate.promoted(next_generation)
                finish_transition(root, pointer, transition, owner_review)
                transitions.append(transition)
            except PendingRewriteReview:
                owner_gate.abort(generation)
                if len(transitions) == initial_transition_count:
                    raise
                awaiting_review = True
                break
            except BaseException:
                owner_gate.abort(generation)
                raise
        field_state = memory.regional_field_receipt()
    receipt = {
        "schema": SCHEMA,
        "status": "awaiting-review" if awaiting_review else "complete",
        "files": list(FILE_PATHS),
        "cycles_requested": int(prior.get("cycles_requested", 0)) + cycles,
        "transitions": transitions,
        "current": dict(pointer),
        "field_state": {
            "field_state_sha256": field_state.get("field_state_sha256"),
            "checkpoint_receipt": field_state.get("checkpoint_receipt"),
        },
    }
    atomic_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / "self-host")
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument(
        "--field-owner-url",
        default=os.environ.get("CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090"),
    )
    args = parser.parse_args()
    result = run(
        args.root.resolve(),
        args.cycles,
        field_owner_url=args.field_owner_url,
    )
    print(json.dumps({
        "status": result["status"],
        "current_generation": result["current"]["generation"],
        "generations": len(result["transitions"]),
        "field_state_sha256": result["field_state"]["field_state_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
