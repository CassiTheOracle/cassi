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
    return {
        "path": path,
        "schema": "cassimindfield.source-edit.v1",
        "operation": "replace_once",
        "find": find,
        "replace": replacement,
        "base_source_sha256": sha256_text(source),
    }


def _offset(source, line, column):
    lines = source.splitlines(keepends=True)
    return sum(len(item) for item in lines[: line - 1]) + column


def _line_start(source, offset):
    return source.rfind("\n", 0, offset) + 1


def _line_end(source, offset):
    end = source.find("\n", offset)
    return len(source) if end < 0 else end


def _indent(source, offset):
    start = _line_start(source, offset)
    line = source[start:_line_end(source, offset)]
    return line[: len(line) - len(line.lstrip())]


def _impact_closure(index, changed_paths):
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


def _affected_scenarios(index, closure):
    return sorted(name for name, paths in index.get("scenarios", {}).items() if set(paths).intersection(closure))


def _editor_self_change(source):
    tree = ast.parse(source)
    for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
        for index in range(len(function.body) - 1):
            assignment = function.body[index]
            condition = function.body[index + 1]
            if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1 or not isinstance(condition, ast.If):
                continue
            target = assignment.targets[0]
            call = assignment.value
            if not isinstance(target, ast.Name) or not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute) or call.func.attr != "count":
                continue
            if not isinstance(condition.test, ast.Compare) or len(condition.test.ops) != 1:
                continue
            if not isinstance(condition.test.ops[0], ast.NotEq) or not isinstance(condition.test.left, ast.Name):
                continue
            if condition.test.left.id != target.id or len(condition.test.comparators) != 1:
                continue
            start = _line_start(source, _offset(source, assignment.lineno, assignment.col_offset))
            condition_start = _offset(source, condition.lineno, condition.col_offset)
            end = _line_end(source, condition_start)
            find = source[start:end]
            replacement = _indent(source, condition_start) + "if " + ast.unparse(call) + " != " + ast.unparse(condition.test.comparators[0]) + ":"
            change = _change(EDITOR_PATH, source, find, replacement)
            if change:
                return change
    return None


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
    for find, replacement in (
        ("from mind_field_core import advance_field", "from mind_field_core import step_field"),
        ("return advance_field(value)", "return step_field(value)"),
    ):
        change = _change(RUNTIME_PATH, current_runtime, find, replacement)
        if change is None:
            return None
        changes.append(change)
        current_runtime = current_runtime.replace(find, replacement, 1)
    changed_paths = [CORE_PATH, RUNTIME_PATH]
    closure = _impact_closure(index, changed_paths)
    return {
        "candidate_id": "rename-advance-to-step",
        "task_id": "rename_symbol_multi_file",
        "schema": PATCH_SET_SCHEMA,
        "operation": "apply_patch_set",
        "changes": changes,
        "changed_symbols": [f"{CORE_PATH}:advance_field", f"{RUNTIME_PATH}:advance_field"],
        "impact_closure": closure,
        "affected_scenarios": _affected_scenarios(index, closure),
    }


def propose_candidates(files, index):
    candidates = []
    rename = _rename_candidate(files, index)
    if rename:
        candidates.append(rename)
    self_change = _editor_self_change(files.get(EDITOR_PATH, ""))
    if self_change:
        closure = _impact_closure(index, [EDITOR_PATH])
        candidates.append(
            {
                "candidate_id": "editor-count-fold",
                "task_id": "editor_count_fold",
                "schema": PATCH_SET_SCHEMA,
                "operation": "apply_patch_set",
                "changes": [self_change],
                "changed_symbols": [f"{EDITOR_PATH}:apply_patch_set"],
                "impact_closure": closure,
                "affected_scenarios": _affected_scenarios(index, closure),
            }
        )
    return candidates


def apply_patch_set(files, patch_set):
    if patch_set.get("schema") != PATCH_SET_SCHEMA or patch_set.get("operation") != "apply_patch_set":
        raise ValueError("unsupported patch set")
    changes = patch_set.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("patch-set changes are invalid")
    updated = dict(files)
    for change in changes:
        path = change.get("path")
        if path not in updated:
            raise ValueError("patch path is outside workspace")
        if change.get("schema") != "cassimindfield.source-edit.v1" or change.get("operation") != "replace_once":
            raise ValueError("patch change is invalid")
        if change.get("base_source_sha256") != sha256_text(updated[path]):
            raise ValueError("patch base hash mismatch")
        find = change.get("find")
        replacement = change.get("replace")
        if not isinstance(find, str) or not find or not isinstance(replacement, str):
            raise ValueError("patch text is invalid")
        if updated[path].count(find) != 1:
            raise ValueError("patch must match exactly once")
        updated[path] = updated[path].replace(find, replacement, 1)
    return updated
