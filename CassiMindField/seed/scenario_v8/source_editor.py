import ast
import hashlib


CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
RUNTIME_PATH = "src/field_runtime.py"
PATCH_SCHEMA = "cassimindfield.source-edit.v1"
PATCH_SET_SCHEMA = "cassimindfield.patch-set.v2"


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _change(path, source, find, replacement):
    if not find or source.count(find) != 1:
        return None
    return {"path": path, "schema": PATCH_SCHEMA, "operation": "replace_once", "find": find, "replace": replacement, "base_source_sha256": sha256_text(source)}


def _rename_candidate(files, index):
    core = files.get(CORE_PATH)
    runtime = files.get(RUNTIME_PATH)
    if not isinstance(core, str) or not isinstance(runtime, str):
        return None
    core_tree = ast.parse(core)
    runtime_tree = ast.parse(runtime)
    function = next((node for node in ast.walk(core_tree) if isinstance(node, ast.FunctionDef) and node.name == "advance_field"), None)
    imported = next((alias for node in ast.walk(runtime_tree) if isinstance(node, ast.ImportFrom) and node.module == "mind_field_core" for alias in node.names if alias.name == "advance_field" and alias.asname is None), None)
    if function is None or imported is None:
        return None
    changes = []
    current_core = core
    for find, replacement in (
        ("def advance_field", "def step_field"),
        ("result = advance_field(value)", "result = step_field(value)"),
        ("    return (2 + 3) * tmp + 1 if value >= 0 else (2 + 3) * tmp + 1", "    return (2 + 3) * tmp + 1"),
        ("(2 + 3)", "5"),
        ("    tmp = value\n    return 5 * tmp + 1", "    return 5 * value + 1"),
    ):
        change = _change(CORE_PATH, current_core, find, replacement)
        if change is None:
            return None
        changes.append(change)
        current_core = current_core.replace(find, replacement, 1)
    current_runtime = runtime
    for find, replacement in (("from mind_field_core import advance_field", "from mind_field_core import step_field"), ("return advance_field(value)", "return step_field(value)")):
        change = _change(RUNTIME_PATH, current_runtime, find, replacement)
        if change is None:
            return None
        changes.append(change)
        current_runtime = current_runtime.replace(find, replacement, 1)
    changed_paths = [CORE_PATH, RUNTIME_PATH]
    impact = _impact_closure(index, changed_paths)
    return {
        "candidate_id": "rename-advance-to-step",
        "task_id": "rename_symbol_multi_file",
        "schema": PATCH_SET_SCHEMA,
        "operation": "apply_patch_set",
        "changes": changes,
        "changed_symbols": [f"{CORE_PATH}:advance_field", f"{RUNTIME_PATH}:advance_field"],
        "impact_closure": impact,
        "affected_scenarios": _affected_scenarios(index, impact),
    }


def _impact_closure(index, changed_paths):
    reverse = index.get("reverse_dependencies", {})
    closure = set(changed_paths)
    pending = list(changed_paths)
    while pending:
        current = pending.pop()
        for importer in reverse.get(current, []):
            if importer not in closure:
                closure.add(importer)
                pending.append(importer)
    return sorted(closure)


def _affected_scenarios(index, closure):
    return sorted(name for name, paths in index.get("scenarios", {}).items() if set(paths).intersection(closure))


def propose_candidates(files, index):
    candidate = _rename_candidate(files, index)
    return [candidate] if candidate else []


def apply_patch_set(files, patch_set):
    if patch_set.get("schema") != PATCH_SET_SCHEMA or patch_set.get("operation") != "apply_patch_set":
        raise ValueError("unsupported patch set")
    changes = patch_set.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("patch-set changes are invalid")
    updated = dict(files)
    for change in changes:
        path = change.get("path")
        if path not in updated or change.get("schema") != PATCH_SCHEMA or change.get("operation") != "replace_once":
            raise ValueError("patch change is invalid")
        if change.get("base_source_sha256") != sha256_text(updated[path]):
            raise ValueError("patch base hash mismatch")
        find = change.get("find")
        replacement = change.get("replace")
        if not isinstance(find, str) or not find or not isinstance(replacement, str) or updated[path].count(find) != 1:
            raise ValueError("patch text or cardinality is invalid")
        updated[path] = updated[path].replace(find, replacement, 1)
    return updated
