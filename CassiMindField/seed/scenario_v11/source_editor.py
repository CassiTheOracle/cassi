import ast
import hashlib
import io
import tokenize


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


def _has_definition(source, name):
    tree = ast.parse(source)
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name for node in ast.walk(tree))


def _has_import(source, module, name):
    tree = ast.parse(source)
    return any(isinstance(node, ast.ImportFrom) and node.module == module and any(alias.name == name and alias.asname is None for alias in node.names) for node in ast.walk(tree))


def _name_lines(source, old_name):
    lines = set()
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        if token.type == tokenize.NAME and token.string == old_name:
            lines.add(token.start[0])
    return sorted(lines)


def _rename_file(path, source, old_name, new_name):
    changes = []
    current = source
    for line_number in _name_lines(current, old_name):
        lines = current.splitlines(keepends=True)
        if line_number > len(lines):
            return None
        line = lines[line_number - 1]
        column = next((index for index in range(len(line) - len(old_name) + 1) if line[index:index + len(old_name)] == old_name), None)
        if column is None:
            return None
        replacement_line = line[:column] + new_name + line[column + len(old_name):]
        change = _change(path, current, line, replacement_line)
        if change is None:
            return None
        changes.append(change)
        current = current.replace(line, replacement_line, 1)
    return changes, current


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


def _operation_candidate(files, index, operation):
    kind = operation.get("kind", "rename_symbol")
    if kind == "inline_call":
        path = operation.get("path")
        function_name = operation.get("function_name")
        find = operation.get("find")
        replacement = operation.get("replace")
        if path not in files or not isinstance(function_name, str) or not isinstance(find, str) or not isinstance(replacement, str):
            return None
        tree = ast.parse(files[path])
        has_call = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function_name for node in ast.walk(tree))
        if not has_call:
            return None
        change = _change(path, files[path], find, replacement)
        if change is None:
            return None
        changes = [change]
        descriptor = {"kind": "inline_call", "function_name": function_name, "path": path, "find": find, "replace": replacement}
        changed_paths = [path]
    else:
        old_name = operation.get("old_name")
        new_name = operation.get("new_name")
        paths = operation.get("paths")
        if not isinstance(old_name, str) or not isinstance(new_name, str) or not old_name.isidentifier() or not new_name.isidentifier() or old_name == new_name:
            return None
        if not isinstance(paths, list) or not paths or any(path not in files for path in paths):
            return None
        core_path = operation.get("definition_path", CORE_PATH)
        runtime_path = operation.get("importer_path", RUNTIME_PATH)
        if core_path not in files or runtime_path not in files or not _has_definition(files[core_path], old_name) or not _has_import(files[runtime_path], "mind_field_core", old_name):
            return None
        changes = []
        updated = dict(files)
        for path in paths:
            renamed = _rename_file(path, updated[path], old_name, new_name)
            if renamed is None:
                return None
            file_changes, updated[path] = renamed
            changes.extend(file_changes)
        for simplification in operation.get("simplifications", []):
            path = simplification.get("path")
            if path not in updated:
                return None
            find = simplification.get("find")
            replacement = simplification.get("replace")
            change = _change(path, updated[path], find, replacement)
            if change is None:
                return None
            changes.append(change)
            updated[path] = updated[path].replace(find, replacement, 1)
        descriptor = {key: operation[key] for key in ("old_name", "new_name", "paths")}
        changed_paths = sorted(set(paths) | {item["path"] for item in changes})
    impact = _impact_closure(index, changed_paths)
    return {
        "candidate_id": operation.get("candidate_id"),
        "task_id": operation.get("task_id"),
        "schema": PATCH_SET_SCHEMA,
        "operation": "apply_patch_set",
        "symbol_operation": descriptor,
        "changes": changes,
        "changed_symbols": [f"{path}:{descriptor.get('function_name', descriptor.get('old_name'))}" for path in changed_paths],
        "impact_closure": impact,
        "affected_scenarios": _affected_scenarios(index, impact),
    }


def propose_candidates(files, index):
    operations = index.get("symbol_operations", [])
    if not isinstance(operations, list):
        return []
    candidates = []
    for operation in operations:
        candidate = _operation_candidate(files, index, operation)
        if candidate is not None:
            candidates.append(candidate)
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
