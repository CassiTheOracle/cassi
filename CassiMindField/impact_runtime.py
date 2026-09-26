#!/usr/bin/env python3
"""Promote dependency-closure-aware multi-file patch sets."""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
import types
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
from verify_cassi_mind_field import verify_differential  # noqa: E402

from field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402

SCHEMA = "cassimindfield.impact-rewrite.v1"
CURRENT_SCHEMA = "cassimindfield.impact-current.v1"
GENERATION_SCHEMA = "cassimindfield.impact-generation.v1"
CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
INDEX_PATH = "src/workspace_index.py"
RUNTIME_PATH = "src/field_runtime.py"
FILE_PATHS = (CORE_PATH, EDITOR_PATH, INDEX_PATH, RUNTIME_PATH)
DISCOVERED_TEST_PATH = "tests/test_field_runtime.py"
PATCH_SET_SCHEMA = "cassimindfield.patch-set.v2"


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def source_path(root: Path, generation: int, relative: str) -> Path:
    return generation_path(root, generation) / relative


def index_path(root: Path, generation: int) -> Path:
    return generation_path(root, generation) / "workspace-index.json"


def current_path(root: Path) -> Path:
    return root / "current.json"


def files_digest(files: Mapping[str, str]) -> str:
    return digest({path: sha256_text(files[path]) for path in sorted(files)})


def workspace_paths(root: Path, generation: int) -> tuple[str, ...]:
    generation_root = generation_path(root, generation)
    discovered = tuple(sorted(path.relative_to(generation_root).as_posix() for path in generation_root.rglob("test_*.py") if path.is_file()))
    return FILE_PATHS + discovered


def read_files(root: Path, generation: int) -> dict[str, str]:
    files = {}
    for relative in workspace_paths(root, generation):
        path = source_path(root, generation, relative)
        require(path.is_file(), f"impact workspace file missing: {path}")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def materialize(root: Path, files: Mapping[str, str], index: Mapping[str, Any]) -> None:
    for relative, source in files.items():
        atomic_text(root / relative, source)
    atomic_json(root / "workspace-index.json", index)


def load_editor(source: str) -> tuple[Callable[..., Any], Callable[..., Any]]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_impact_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch_set = namespace.get("apply_patch_set")
    proposer = namespace.get("propose_candidates")
    require(callable(apply_patch_set), "impact editor lacks apply_patch_set")
    require(callable(proposer), "impact editor lacks propose_candidates")
    return apply_patch_set, proposer


def load_indexer(source: str) -> Callable[..., Any]:
    namespace: dict[str, Any] = {"__name__": "cassimindfield_impact_indexer"}
    exec(compile(source, INDEX_PATH, "exec"), namespace, namespace)
    indexer = namespace.get("build_index")
    require(callable(indexer), "impact indexer lacks build_index")
    return indexer
def build_index(files: Mapping[str, str]) -> dict[str, Any]:
    index = load_indexer(files[INDEX_PATH])(dict(files))
    require(
        isinstance(index, dict)
        and index.get("schema") in {"cassimindfield.workspace-index.v2", "cassimindfield.workspace-index.v3"},
        "impact index is invalid",
    )
    return index


def dependency_closure(index: Mapping[str, Any], changed_paths: list[str]) -> list[str]:
    reverse = index.get("reverse_dependencies", {})
    closure = set(changed_paths)
    pending = list(changed_paths)
    while pending:
        path = pending.pop()
        for importer in reverse.get(path, []):
            if importer not in closure:
                closure.add(importer)
                pending.append(importer)
    return sorted(closure)




def discover_scenario_commands(index: Mapping[str, Any], names: list[str]) -> dict[str, list[str]]:
    declared = index.get("scenario_commands")
    if not declared:
        return {}
    require(isinstance(declared, Mapping), "scenario commands are not a mapping")
    discovered = {}
    for name in names:
        if name not in declared:
            continue
        command = declared[name]
        require(isinstance(command, list) and command and all(isinstance(token, str) and token for token in command), f"scenario command invalid: {name}")
        discovered[name] = list(command)
    return discovered


def run_command_scenarios(files: Mapping[str, str], index: Mapping[str, Any], names: list[str]) -> dict[str, dict[str, Any]]:
    commands = discover_scenario_commands(index, names)
    if not commands:
        return {}
    with tempfile.TemporaryDirectory(prefix="cassimindfield-scenario-") as temporary:
        workspace = Path(temporary)
        for relative, source in files.items():
            atomic_text(workspace / relative, source)
        atomic_json(workspace / "workspace-index.json", index)
        results = {}
        for name, command in commands.items():
            argv = [sys.executable if token == "$PYTHON" else token for token in command]
            try:
                completed = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=20, check=False)
                results[name] = {
                    "command": argv,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-4000:],
                    "stderr": completed.stderr[-4000:],
                    "passed": completed.returncode == 0,
                }
            except Exception as error:
                results[name] = {"command": argv, "returncode": None, "stdout": "", "stderr": str(error), "passed": False}
        require(all(result["passed"] for result in results.values()), f"command-backed scenario failed: {results}")
        return results
def affected_scenarios(index: Mapping[str, Any], closure: list[str]) -> list[str]:
    return sorted(name for name, paths in index.get("scenarios", {}).items() if set(paths).intersection(closure))


def read_pointer(root: Path) -> Mapping[str, Any] | None:
    path = current_path(root)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, Mapping), "impact pointer is not an object")
    return value


def seed_root(root: Path) -> Path:
    local = root / "seed"
    if local.is_dir():
        return local
    if root.name == "impact-v7":
        return ROOT / "seed" / "impact_v7"
    if root.name == "scenario-v8":
        return ROOT / "seed" / "scenario_v8"
    if root.name == "scenario-v9":
        return ROOT / "seed" / "scenario_v9"
    if root.name == "scenario-v10":
        return ROOT / "seed" / "scenario_v10"
    if root.name == "scenario-v11":
        return ROOT / "seed" / "scenario_v11"
    return ROOT / "seed" / "scenario_v12"


def seed_paths(source_root: Path) -> tuple[str, ...]:
    discovered = tuple(sorted(path.relative_to(source_root).as_posix() for path in source_root.rglob("test_*.py") if path.is_file()))
    return FILE_PATHS + discovered


def bootstrap(root: Path) -> Mapping[str, Any]:
    existing = read_pointer(root)
    if existing is not None:
        generation = int(existing["generation"])
        files = read_files(root, generation)
        index = json.loads(index_path(root, generation).read_text(encoding="utf-8"))
        require(files_digest(files) == existing["files_sha256"], "impact files do not match pointer")
        require(digest(index) == existing["workspace_index_sha256"], "impact index does not match pointer")
        materialize(root, files, index)
        return existing
    source_root = seed_root(root)
    files = {}
    for relative in seed_paths(source_root):
        seed = source_root / Path(relative).name if relative in FILE_PATHS else source_root / relative
        require(seed.is_file(), f"impact seed missing: {seed}")
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
        "files": {relative: {"sha256": sha256_text(files[relative]), "bytes": len(files[relative].encode("utf-8"))} for relative in sorted(files)},
        "workspace_index_sha256": digest(index),
        "changed_paths": [],
        "impact_closure": [],
        "affected_scenarios": [],
        "proposal_origin": "seed",
        "patch_set": None,
    }
    atomic_json(generation_path(root, 0) / "manifest.json", manifest)
    pointer = {"schema": CURRENT_SCHEMA, "generation": 0, "files_sha256": files_digest(files), "workspace_index_sha256": digest(index), "manifest_sha256": digest(manifest)}
    atomic_json(current_path(root), pointer)
    return pointer


def editor_behavior(apply_patch_set: Callable[..., Any]) -> None:
    source = "alpha + beta"
    change = {"path": EDITOR_PATH, "schema": "cassimindfield.source-edit.v1", "operation": "replace_once", "find": "alpha", "replace": "gamma", "base_source_sha256": sha256_text(source)}
    patch_set = {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [change]}
    require(apply_patch_set({EDITOR_PATH: source}, patch_set)[EDITOR_PATH] == "gamma + beta", "impact editor valid case failed")
    for invalid in ("alpha alpha", "beta"):
        bad = dict(change, base_source_sha256=sha256_text(invalid))
        try:
            apply_patch_set({EDITOR_PATH: invalid}, {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [bad]})
        except Exception:
            continue
        raise RuntimeError("impact editor accepted invalid match")


def run_scenario(name: str, files: Mapping[str, str], index: Mapping[str, Any]) -> dict[str, Any]:
    runner = index.get("scenario_runners", {}).get(name, name.replace("-", "_"))
    if runner == "core_behavior":
        result = verify_differential(files[CORE_PATH], CASES)
        return {"runner": runner, "passed": bool(result["passed"]), "detail": result}
    if runner == "runtime_dependency":
        module = types.ModuleType("mind_field_core")
        module.__dict__["value"] = 9
        exec(compile(files[CORE_PATH], CORE_PATH, "exec"), module.__dict__, module.__dict__)
        previous = sys.modules.get("mind_field_core")
        sys.modules["mind_field_core"] = module
        try:
            namespace = {"__name__": "field_runtime", "value": 9}
            exec(compile(files[RUNTIME_PATH], RUNTIME_PATH, "exec"), namespace, namespace)
            passed = namespace.get("result") == 46
        finally:
            if previous is None:
                sys.modules.pop("mind_field_core", None)
            else:
                sys.modules["mind_field_core"] = previous
        return {"runner": runner, "passed": passed, "detail": {"result": namespace.get("result")}}
    if runner == "editor_contract":
        namespace: dict[str, Any] = {"__name__": "impact_scenario_editor"}
        exec(compile(files[EDITOR_PATH], EDITOR_PATH, "exec"), namespace, namespace)
        editor = namespace.get("apply_patch_set")
        require(callable(editor), "scenario editor lacks apply_patch_set")
        editor_behavior(editor)
        return {"runner": runner, "passed": True, "detail": {"cases": 3}}
    if runner == "workspace_index":
        rebuilt = build_index(files)
        return {"runner": runner, "passed": rebuilt == index, "detail": {"file_count": rebuilt.get("file_count")}}
    if runner == "discovered_tests":
        tests = list(index.get("discovered_tests", []))
        return {"runner": runner, "passed": bool(tests), "detail": {"tests": tests}}
    raise RuntimeError(f"unknown affected scenario runner: {runner}")


def run_affected_scenarios(files: Mapping[str, str], index: Mapping[str, Any], names: list[str]) -> dict[str, dict[str, Any]]:
    results = {name: run_scenario(name, files, index) for name in names}
    command_results = run_command_scenarios(files, index, names)
    for name, result in command_results.items():
        results[name]["command"] = result
        results[name]["passed"] = bool(results[name]["passed"] and result["passed"])
    require(all(result["passed"] for result in results.values()), f"affected scenario failed: {results}")
    return results


def candidate_rows(files: Mapping[str, str], index: Mapping[str, Any]) -> list[dict[str, Any]]:
    apply_patch_set, propose_candidates = load_editor(files[EDITOR_PATH])
    proposals = propose_candidates(dict(files), dict(index))
    require(isinstance(proposals, list), "impact editor returned invalid proposals")
    rows = []
    for proposal in proposals:
        require(isinstance(proposal, Mapping), "impact proposal is invalid")
        changed_paths = sorted({str(change.get("path")) for change in proposal.get("changes", [])})
        expected_closure = dependency_closure(index, changed_paths)
        expected_scenarios = affected_scenarios(index, expected_closure)
        if proposal.get("impact_closure") != expected_closure or proposal.get("affected_scenarios") != expected_scenarios:
            continue
        try:
            candidate_files = apply_patch_set(dict(files), proposal)
            for source in candidate_files.values():
                ast.parse(source)
            candidate_index = build_index(candidate_files)
        except Exception:
            continue
        try:
            scenario_results = run_affected_scenarios(candidate_files, candidate_index, expected_scenarios)
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
        rows.append({
            "candidate_id": proposal.get("candidate_id"),
            "candidate_origin": "verified_pool",
            "proposal_origin": "promoted_editor",
            "task_id": proposal.get("task_id"),
            "scenario_results": scenario_results,
            "changed_paths": changed_paths,
            "changed_symbols": list(proposal.get("changed_symbols", [])),
            "impact_closure": expected_closure,
            "affected_scenarios": expected_scenarios,
            "candidate_sha256": files_digest(candidate_files),
            "candidate_steps": candidate_steps,
            "original_steps": original_steps,
            "improved": True,
            "status": "PASS",
            "patch_set": dict(proposal),
            "candidate_files": candidate_files,
            "candidate_index": candidate_index,
        })
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
    receipt_path = root / "impact-receipt.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    transitions = list(prior.get("transitions", []))
    initial_transition_count = len(transitions)
    transitions = reconcile_transitions(root, pointer, transitions)
    awaiting_review = False
    with CassiFieldWorkMemory(root / "state" / "field-memory") as memory:
        controller = TeacherFieldController(memory, run_id=f"cassimindfield:impact-v7:{sha256_text(str(root.resolve()))[:16]}")
        for _ in range(cycles):
            generation = int(pointer["generation"])
            files = read_files(root, generation)
            index = json.loads(index_path(root, generation).read_text(encoding="utf-8"))
            require(files_digest(files) == pointer["files_sha256"], "impact files do not match pointer")
            require(digest(index) == pointer["workspace_index_sha256"], "impact index does not match pointer")
            candidates = candidate_rows(files, index)
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
                require(selected is not None, "field selected unknown impact candidate")
                candidate_files = selected["candidate_files"]
                candidate_index = selected["candidate_index"]
                if CORE_PATH in selected["changed_paths"]:
                    check = verify_candidate_source(files[CORE_PATH], candidate_files[CORE_PATH], CASES)
                else:
                    editor_behavior(load_editor(candidate_files[EDITOR_PATH])[0])
                    check = {"passed": True, "original_steps": selected["original_steps"], "candidate_steps": selected["candidate_steps"], "equivalent": True, "improved": True, "status": "PASS"}
                require(check["passed"], "impact candidate failed independent check")
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
                    "files": {relative: {"sha256": sha256_text(candidate_files[relative]), "bytes": len(candidate_files[relative].encode("utf-8"))} for relative in sorted(candidate_files)},
                    "workspace_index_sha256": digest(candidate_index),
                    "changed_paths": selected["changed_paths"],
                    "changed_symbols": selected["changed_symbols"],
                    "impact_closure": selected["impact_closure"],
                    "affected_scenarios": selected["affected_scenarios"],
                    "scenario_results": selected["scenario_results"],
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
                    "candidate_pool": list(descriptors),
                    "candidate": {
                        "candidate_id": selected["candidate_id"],
                        "task_id": selected["task_id"],
                        "changed_paths": selected["changed_paths"],
                        "changed_symbols": selected["changed_symbols"],
                        "impact_closure": selected["impact_closure"],
                        "affected_scenarios": selected["affected_scenarios"],
                        "scenario_results": selected["scenario_results"],
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
    current_files = read_files(root, int(pointer["generation"]))
    receipt = {"schema": SCHEMA, "status": "awaiting-review" if awaiting_review else "complete", "files": sorted(current_files), "cycles_requested": int(prior.get("cycles_requested", 0)) + cycles, "transitions": transitions, "current": dict(pointer)}
    atomic_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / "impact-v7")
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
