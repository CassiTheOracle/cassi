#!/usr/bin/env python3
"""Independently verify scenario execution selected from impact closure."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import types
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
from verify_cassi_mind_field import verify_differential, verify_candidate_source  # noqa: E402

CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
INDEX_PATH = "src/workspace_index.py"
RUNTIME_PATH = "src/field_runtime.py"
FILE_PATHS = (CORE_PATH, EDITOR_PATH, INDEX_PATH, RUNTIME_PATH)
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
PATCH_SET_SCHEMA = "cassimindfield.patch-set.v2"
INDEX_SCHEMA = "cassimindfield.workspace-index.v3"
SCENARIOS = {
    "core-behavior": [CORE_PATH],
    "runtime-dependency": [CORE_PATH, RUNTIME_PATH],
    "editor-contract": [EDITOR_PATH],
    "workspace-index": [INDEX_PATH],
}
SCENARIO_RUNNERS = {
    "core-behavior": "core_behavior",
    "runtime-dependency": "runtime_dependency",
    "editor-contract": "editor_contract",
    "workspace-index": "workspace_index",
}
SCENARIO_COMMANDS = {
    "core-behavior": ["$PYTHON", "-c", "import runpy; ns=runpy.run_path('src/mind_field_core.py', init_globals={'value': 9}); f=ns.get('step_field') or ns.get('advance_field'); assert [f(-7), f(0), f(9), f(123)] == [-34, 1, 46, 616]"],
    "runtime-dependency": ["$PYTHON", "-c", "import runpy, sys, types; ns=runpy.run_path('src/mind_field_core.py', init_globals={'value': 9}); module=types.ModuleType('mind_field_core'); module.__dict__.update(ns); sys.modules['mind_field_core']=module; result=runpy.run_path('src/field_runtime.py', init_globals={'value': 9}); assert result['result'] == 46"],
    "editor-contract": ["$PYTHON", "-c", "import runpy; ns=runpy.run_path('src/source_editor.py'); assert callable(ns['apply_patch_set']) and callable(ns['propose_candidates'])"],
    "workspace-index": ["$PYTHON", "-c", "import json, runpy; expected=json.load(open('workspace-index.json')); actual=runpy.run_path('src/workspace_index.py')['build_index']({path: open(path).read() for path in expected['files']}); assert actual == expected"],
}

V10_SCENARIO_COMMANDS = {
    "core-behavior": ["$PYTHON", "-c", "import runpy; ns=runpy.run_path('src/mind_field_core.py', init_globals={'value': 9}); f=ns.get('evolve_field') or ns.get('step_field') or ns.get('advance_field'); assert [f(-7), f(0), f(9), f(123)] == [-34, 1, 46, 616]"],
    "runtime-dependency": ["$PYTHON", "-c", "import runpy, sys, types; ns=runpy.run_path('src/mind_field_core.py', init_globals={'value': 9}); module=types.ModuleType('mind_field_core'); module.__dict__.update(ns); sys.modules['mind_field_core']=module; result=runpy.run_path('src/field_runtime.py', init_globals={'value': 9}); assert result['result'] == 46"],
    "editor-contract": ["$PYTHON", "-c", "import runpy; ns=runpy.run_path('src/source_editor.py'); assert callable(ns['apply_patch_set']) and callable(ns['propose_candidates'])"],
    "workspace-index": ["$PYTHON", "-c", "import json, runpy; expected=json.load(open('workspace-index.json')); actual=runpy.run_path('src/workspace_index.py')['build_index']({path: open(path).read() for path in expected['files']}); assert actual == expected"],
}

V10_SYMBOL_OPERATIONS = [{
    "candidate_id": "rename-advance-to-evolve",
    "task_id": "rename_symbol_generic",
    "old_name": "advance_field",
    "new_name": "evolve_field",
    "paths": ["src/mind_field_core.py", "src/field_runtime.py"],
    "definition_path": "src/mind_field_core.py",
    "importer_path": "src/field_runtime.py",
    "simplifications": [
        {"path": "src/mind_field_core.py", "find": "    return (2 + 3) * tmp + 1 if value >= 0 else (2 + 3) * tmp + 1\n", "replace": "    return (2 + 3) * tmp + 1\n"},
        {"path": "src/mind_field_core.py", "find": "(2 + 3)", "replace": "5"},
        {"path": "src/mind_field_core.py", "find": "    tmp = value\n    return 5 * tmp + 1\n", "replace": "    return 5 * value + 1\n"},
    ],
}]

V11_SYMBOL_OPERATIONS = [
    dict(V10_SYMBOL_OPERATIONS[0]),
    {
        "candidate_id": "rename-advance-to-step",
        "task_id": "rename_symbol_alternative",
        "old_name": "advance_field",
        "new_name": "step_field",
        "paths": ["src/mind_field_core.py", "src/field_runtime.py"],
        "definition_path": "src/mind_field_core.py",
        "importer_path": "src/field_runtime.py",
        "simplifications": list(V10_SYMBOL_OPERATIONS[0]["simplifications"]),
    },
    {
        "candidate_id": "inline-evolve-result",
        "task_id": "inline_verified_call",
        "kind": "inline_call",
        "function_name": "evolve_field",
        "path": "src/mind_field_core.py",
        "find": "result = evolve_field(value)\n",
        "replace": "result = 5 * value + 1\n",
    },
    {
        "candidate_id": "inline-step-result",
        "task_id": "inline_verified_call",
        "kind": "inline_call",
        "function_name": "step_field",
        "path": "src/mind_field_core.py",
        "find": "result = step_field(value)\n",
        "replace": "result = 5 * value + 1\n",
    },
]
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
    return {path: (generation_path(root, generation) / path).read_text(encoding="utf-8") for path in FILE_PATHS}


def files_digest(files: Mapping[str, str]) -> str:
    return digest({path: sha256_text(files[path]) for path in sorted(files)})
def discovered_test_paths(files: Mapping[str, str]) -> list[str]:
    return sorted(path for path in files if path.startswith("tests/") and path.rsplit("/", 1)[-1].startswith("test_") and path.endswith(".py"))


def expected_registries(files: Mapping[str, str]) -> tuple[dict[str, list[str]], dict[str, str], dict[str, list[str]]]:
    tests = discovered_test_paths(files)
    scenarios = {name: list(paths) for name, paths in SCENARIOS.items()}
    runners = dict(SCENARIO_RUNNERS)
    commands = dict(V10_SCENARIO_COMMANDS if "SYMBOL_OPERATIONS" in files[INDEX_PATH] else SCENARIO_COMMANDS)
    if tests:
        scenarios["discovered-tests"] = [CORE_PATH, RUNTIME_PATH, *tests]
        runners["discovered-tests"] = "discovered_tests"
        commands["discovered-tests"] = ["$PYTHON", "-c", f"import runpy; [runpy.run_path(path) for path in {tests!r}]"]
    return scenarios, runners, commands


def read_files(root: Path, generation: int) -> dict[str, str]:
    manifest = json.loads((generation_path(root, generation) / "manifest.json").read_text(encoding="utf-8"))
    paths = sorted(manifest.get("files", {}))
    return {path: (generation_path(root, generation) / path).read_text(encoding="utf-8") for path in paths}
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
    dependency_map = {path: sorted(values) for path, values in dependencies.items()}
    reverse = {path: [] for path in dependency_map}
    for importer, imported in dependency_map.items():
        for dependency in imported:
            reverse.setdefault(dependency, []).append(importer)
    generalized = "SYMBOL_OPERATIONS" in files[INDEX_PATH]
    v11 = "inline_verified_call" in files[INDEX_PATH]
    scenarios, runners, commands = expected_registries(files)
    result = {"schema": INDEX_SCHEMA, "files": entries, "dependencies": dependency_map, "reverse_dependencies": {path: sorted(values) for path, values in reverse.items()}, "scenarios": scenarios, "scenario_runners": runners, "file_count": len(entries), "symbol_count": sum(len(item["symbols"]) for item in entries.values())}
    if "SCENARIO_COMMANDS" in files[INDEX_PATH]:
        result["scenario_commands"] = commands
    if generalized:
        result["symbol_operations"] = V11_SYMBOL_OPERATIONS if v11 else V10_SYMBOL_OPERATIONS
    tests = discovered_test_paths(files)
    if tests:
        result["discovered_tests"] = tests
        result["test_commands"] = {path: ["$PYTHON", path] for path in tests}
    return result
def closure(index: Mapping[str, Any], changed: list[str]) -> list[str]:
    result = set(changed)
    pending = list(changed)
    while pending:
        current = pending.pop()
        for importer in index["reverse_dependencies"].get(current, []):
            if importer not in result:
                result.add(importer)
                pending.append(importer)
    return sorted(result)


def scenario_names(index: Mapping[str, Any], impact: list[str]) -> list[str]:
    return sorted(name for name, paths in index["scenarios"].items() if set(paths).intersection(impact))


def load_editor(source: str) -> tuple[Callable[..., Any], Callable[..., Any]]:
    namespace: dict[str, Any] = {"__name__": "independent_scenario_editor"}
    exec(compile(source, EDITOR_PATH, "exec"), namespace, namespace)
    apply_patch_set = namespace.get("apply_patch_set")
    proposer = namespace.get("propose_candidates")
    require(callable(apply_patch_set) and callable(proposer), "scenario editor contract missing")
    return apply_patch_set, proposer


def editor_contract(editor: Callable[..., Any]) -> dict[str, Any]:
    source = "alpha + beta"
    change = {"path": EDITOR_PATH, "schema": PATCH_SCHEMA, "operation": "replace_once", "find": "alpha", "replace": "gamma", "base_source_sha256": sha256_text(source)}
    patch_set = {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [change]}
    require(editor({EDITOR_PATH: source}, patch_set)[EDITOR_PATH] == "gamma + beta", "scenario editor valid case failed")
    for invalid in ("alpha alpha", "beta"):
        try:
            editor({EDITOR_PATH: invalid}, {"schema": PATCH_SET_SCHEMA, "operation": "apply_patch_set", "changes": [dict(change, base_source_sha256=sha256_text(invalid))]})
        except Exception:
            continue
        raise RuntimeError("scenario editor accepted invalid match")
    return {"passed": True, "cases": 3}


def run_scenario(name: str, files: Mapping[str, str], index: Mapping[str, Any]) -> dict[str, Any]:
    runner = index["scenario_runners"][name]
    if runner == "core_behavior":
        detail = verify_differential(files[CORE_PATH], CASES)
        return {"runner": runner, "passed": bool(detail["passed"]), "detail": detail}
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
        editor = load_editor(files[EDITOR_PATH])[0]
        return {"runner": runner, **editor_contract(editor)}
    if runner == "workspace_index":
        rebuilt = independent_index(files)
        return {"runner": runner, "passed": rebuilt == index, "detail": {"file_count": rebuilt["file_count"]}}
    if runner == "discovered_tests":
        tests = list(index.get("discovered_tests", []))
        return {"runner": runner, "passed": bool(tests), "detail": {"tests": tests}}
def independent_command_results(files: Mapping[str, str], index: Mapping[str, Any], names: list[str]) -> dict[str, dict[str, Any]]:
    commands = index.get("scenario_commands", {})
    expected = dict(V10_SCENARIO_COMMANDS if "symbol_operations" in index else SCENARIO_COMMANDS)
    tests = discovered_test_paths(files)
    if tests:
        expected["discovered-tests"] = ["$PYTHON", "-c", f"import runpy; [runpy.run_path(path) for path in {tests!r}]"]
    require(commands == expected, "scenario command registry mismatch")
    with tempfile.TemporaryDirectory(prefix="cassimindfield-independent-") as temporary:
        workspace = Path(temporary)
        for relative, source in files.items():
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source, encoding="utf-8")
        (workspace / "workspace-index.json").write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
        results = {}
        for name in names:
            argv = [sys.executable if token == "$PYTHON" else token for token in commands[name]]
            completed = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=20, check=False)
            results[name] = {"command": argv, "returncode": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:], "passed": completed.returncode == 0}
        require(all(item["passed"] for item in results.values()), f"independent command scenario failed: {results}")
        return results


def independent_apply(files: Mapping[str, str], patch_set: Mapping[str, Any]) -> dict[str, str]:
    require(patch_set.get("schema") == PATCH_SET_SCHEMA and patch_set.get("operation") == "apply_patch_set", "scenario patch-set invalid")
    updated = dict(files)
    for change in patch_set["changes"]:
        path = change["path"]
        require(path in updated and change.get("schema") == PATCH_SCHEMA and change.get("operation") == "replace_once", "scenario patch change invalid")
        require(change.get("base_source_sha256") == sha256_text(updated[path]), "scenario patch base mismatch")
        find = change.get("find")
        replacement = change.get("replace")
        require(isinstance(find, str) and find and isinstance(replacement, str) and updated[path].count(find) == 1, "scenario patch text invalid")
        updated[path] = updated[path].replace(find, replacement, 1)
    return updated


def dependency_contract(files: Mapping[str, str], index: Mapping[str, Any] | None = None, expected_name: str | None = None) -> None:
    core = ast.parse(files[CORE_PATH])
    runtime = ast.parse(files[RUNTIME_PATH])
    functions = {node.name for node in ast.walk(core) if isinstance(node, ast.FunctionDef)}
    imports = {alias.name for node in ast.walk(runtime) if isinstance(node, ast.ImportFrom) and node.module == "mind_field_core" for alias in node.names}
    calls = {node.func.id for node in ast.walk(runtime) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    operation = (index or {}).get("symbol_operations", [{}])[0]
    new_name = expected_name or operation.get("new_name") or operation.get("function_name") or "step_field"
    old_name = operation.get("old_name") if operation.get("kind") != "inline_call" else None
    require(new_name in functions and new_name in imports and new_name in calls, "scenario dependency rename incomplete")
    if old_name:
        require(old_name not in imports and old_name not in calls, "scenario old dependency remains")


def verify_run(root: Path) -> dict[str, Any]:
    receipt = json.loads((root / "impact-receipt.json").read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassimindfield.impact-rewrite.v1", "scenario receipt schema mismatch")
    transitions = receipt["transitions"]
    previous = 0
    active_symbol = None
    candidate_competition_verified = False
    discovered_tests_verified = False
    for row in transitions:
        generation = int(row["generation"])
        next_generation = int(row["next_generation"])
        require(generation == previous and next_generation == generation + 1, "scenario lineage invalid")
        before = read_files(root, generation)
        after = read_files(root, next_generation)
        index = json.loads((generation_path(root, next_generation) / "workspace-index.json").read_text(encoding="utf-8"))
        require(index == independent_index(after), "scenario index mismatch")
        candidate = row["candidate"]
        changed = sorted(candidate["changed_paths"])
        impact = closure(index, changed)
        names = scenario_names(index, impact)
        require(candidate["impact_closure"] == impact, "scenario impact closure mismatch")
        require(candidate["affected_scenarios"] == names, "scenario selection mismatch")
        if "candidate_pool" in row:
            pool = row["candidate_pool"]
            pool_ids = [item.get("candidate_id") for item in pool]
            require(candidate["candidate_id"] in pool_ids, "selected candidate absent from pool")
            if generation == 0:
                require(len(pool_ids) >= 2, "initial candidate competition was not recorded")
                candidate_competition_verified = True
        if "symbol_operations" in index:
            operation = next((item for item in index["symbol_operations"] if item.get("candidate_id") == candidate["candidate_id"]), None)
            require(operation is not None, "selected generalized operation absent from registry")
            if operation.get("kind") == "inline_call":
                expected_descriptor = {key: operation[key] for key in ("kind", "function_name", "path", "find", "replace")}
            else:
                expected_descriptor = {key: operation[key] for key in ("old_name", "new_name", "paths")}
            require(candidate["patch_set"].get("symbol_operation") == expected_descriptor, "generalized symbol operation mismatch")
            descriptor = candidate["patch_set"].get("symbol_operation", {})
            active_symbol = descriptor.get("new_name") or descriptor.get("function_name") or active_symbol
        recorded = candidate["scenario_results"]
        if index.get("discovered_tests"):
            require("discovered-tests" in recorded, "discovered test scenario missing")
            discovered_tests_verified = True
        require(recorded and all(item["passed"] for item in recorded.values()), "recorded scenario failed")
        independent_results = {name: run_scenario(name, after, index) for name in names}
        require(all(item["passed"] for item in independent_results.values()), "independent affected scenario failed")
        if "scenario_commands" in index:
            command_results = independent_command_results(after, index, names)
            for name, command_result in command_results.items():
                recorded_command = recorded[name].get("command")
                require(recorded_command and recorded_command["returncode"] == command_result["returncode"] == 0, "recorded command result mismatch")
        require(independent_apply(before, candidate["patch_set"]) == after, "scenario patch replay mismatch")
        if CORE_PATH in changed or RUNTIME_PATH in changed:
            dependency_contract(after, index, active_symbol)
        previous = next_generation
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    final = read_files(root, previous)
    final_index = json.loads((generation_path(root, previous) / "workspace-index.json").read_text(encoding="utf-8"))
    require(pointer["generation"] == previous and pointer["files_sha256"] == files_digest(final), "scenario pointer mismatch")
    require(pointer["workspace_index_sha256"] == digest(final_index) and final_index == independent_index(final), "scenario final index mismatch")
    dependency_contract(final, final_index, active_symbol)
    test_mutation_rejected = True
    if final_index.get("discovered_tests"):
        test_path = next(path for path in final_index["discovered_tests"] if "== 46" in final[path])
        mutated_test = final[test_path].replace("== 46", "== 47", 1)
        try:
            independent_command_results({**final, test_path: mutated_test}, final_index, ["discovered-tests"])
        except Exception:
            test_mutation_rejected = True
        else:
            test_mutation_rejected = False
        require(test_mutation_rejected, "discovered test mutation accepted")
    core_mutation = final[CORE_PATH].replace("return 5 * value + 1", "return 5 * value + 2", 1)
    require(not verify_candidate_source(final[CORE_PATH], core_mutation, CASES)["passed"], "scenario core mutation accepted")
    command_mutation_rejected = True
    if "scenario_commands" in final_index:
        try:
            independent_command_results({**final, CORE_PATH: core_mutation}, final_index, ["core-behavior"])
        except Exception:
            command_mutation_rejected = True
        else:
            command_mutation_rejected = False
        require(command_mutation_rejected, "command-backed mutation accepted")
    operation = final_index.get("symbol_operations", [{}])[0]
    old_name = operation.get("old_name", "advance_field")
    new_name = active_symbol or operation.get("new_name", "step_field")
    dependency_mutation = final[RUNTIME_PATH].replace(f"{new_name}(value)", f"{old_name}(value)", 1)
    try:
        dependency_contract({**final, RUNTIME_PATH: dependency_mutation}, final_index, new_name)
    except Exception:
        dependency_mutation_rejected = True
    else:
        raise RuntimeError("scenario dependency mutation accepted")
    return {"status": "PASS", "current_generation": previous, "generations": len(transitions), "affected_scenarios_executed": True, "independent_scenario_results": True, "workspace_replay_verified": True, "dependency_mutation_rejected": dependency_mutation_rejected, "command_mutation_rejected": command_mutation_rejected, "test_mutation_rejected": test_mutation_rejected, "candidate_competition_verified": candidate_competition_verified, "discovered_tests_verified": discovered_tests_verified, "generalized_symbol_operation_verified": bool(final_index.get("symbol_operations")), "symbol_name": new_name, "indexed_files": final_index["file_count"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=CASSIMIND / "scenario-v8")
    args = parser.parse_args()
    print(json.dumps(verify_run(args.root.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
