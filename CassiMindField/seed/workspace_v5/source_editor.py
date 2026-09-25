import ast
import hashlib


CORE_PATH = "src/mind_field_core.py"
EDITOR_PATH = "src/source_editor.py"
PATCH_SCHEMA = "cassimindfield.source-edit.v1"


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _patch(path, source, candidate_id, task_id, find, replacement):
    if not find or source.count(find) != 1:
        return None
    return {
        "candidate_id": candidate_id,
        "task_id": task_id,
        "path": path,
        "schema": PATCH_SCHEMA,
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


def _replace_name(node, name, replacement):
    class ReplaceName(ast.NodeTransformer):
        def visit_Name(self, current):
            if current.id == name:
                return ast.copy_location(ast.parse(replacement, mode="eval").body, current)
            return current

    return ReplaceName().visit(ast.fix_missing_locations(node))


def _core_candidates(source):
    tree = ast.parse(source)
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp) and ast.dump(node.body, include_attributes=False) == ast.dump(node.orelse, include_attributes=False):
            find = ast.get_source_segment(source, node)
            replacement = ast.get_source_segment(source, node.body)
            candidate = _patch(CORE_PATH, source, "identical-branch:function", "identical_branch", find, replacement)
            if candidate:
                candidates.append(candidate)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                if isinstance(node.left.value, int) and isinstance(node.right.value, int):
                    find = ast.get_source_segment(source, node)
                    candidate = _patch(CORE_PATH, source, "constant-fold", "constant_fold", find, str(node.left.value + node.right.value))
                    if candidate:
                        candidates.append(candidate)
    for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
        for index in range(len(function.body) - 1):
            assignment = function.body[index]
            returned = function.body[index + 1]
            if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
                continue
            target = assignment.targets[0]
            if not isinstance(target, ast.Name) or not isinstance(assignment.value, ast.Name):
                continue
            if not isinstance(returned, ast.Return) or returned.value is None:
                continue
            if not any(isinstance(item, ast.Name) and item.id == target.id for item in ast.walk(returned.value)):
                continue
            start = _line_start(source, _offset(source, assignment.lineno, assignment.col_offset))
            end = _line_end(source, _offset(source, returned.end_lineno, returned.end_col_offset))
            find = source[start:end]
            transformed = _replace_name(returned.value, target.id, ast.unparse(assignment.value))
            replacement = _indent(source, start) + "return " + ast.unparse(transformed)
            candidate = _patch(CORE_PATH, source, "redundant-assignment:function", "redundant_assignment", find, replacement)
            if candidate:
                candidates.append(candidate)
    return candidates


def _editor_candidates(source):
    tree = ast.parse(source)
    candidates = []
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
            candidate = _patch(EDITOR_PATH, source, "editor-count-fold", "editor_count_fold", find, replacement)
            if candidate:
                candidates.append(candidate)
    return candidates


def propose_candidates(files):
    candidates = []
    if isinstance(files.get(CORE_PATH), str):
        candidates.extend(_core_candidates(files[CORE_PATH]))
    if isinstance(files.get(EDITOR_PATH), str):
        candidates.extend(_editor_candidates(files[EDITOR_PATH]))
    unique = {}
    for candidate in candidates:
        unique.setdefault(candidate["candidate_id"] + ":" + candidate["path"], candidate)
    return list(unique.values())


def apply_patch(source, patch):
    if patch.get("schema") != PATCH_SCHEMA or patch.get("operation") != "replace_once":
        raise ValueError("unsupported patch")
    if patch.get("base_source_sha256") != sha256_text(source):
        raise ValueError("patch base source mismatch")
    find = patch.get("find")
    replacement = patch.get("replace")
    if not isinstance(find, str) or not find or not isinstance(replacement, str):
        raise ValueError("patch text is invalid")
    occurrence_count = source.count(find)
    if occurrence_count != 1:
        raise ValueError("patch must match exactly one source span")
    return source.replace(find, replacement, 1)
