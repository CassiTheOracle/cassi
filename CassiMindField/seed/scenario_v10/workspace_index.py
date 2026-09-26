import ast
import hashlib


SCHEMA = "cassimindfield.workspace-index.v3"
SCENARIOS = {
    "core-behavior": ["src/mind_field_core.py"],
    "runtime-dependency": ["src/mind_field_core.py", "src/field_runtime.py"],
    "editor-contract": ["src/source_editor.py"],
    "workspace-index": ["src/workspace_index.py"],
}
SCENARIO_RUNNERS = {
    "core-behavior": "core_behavior",
    "runtime-dependency": "runtime_dependency",
    "editor-contract": "editor_contract",
    "workspace-index": "workspace_index",
}

SCENARIO_COMMANDS = {
    "core-behavior": ["$PYTHON", "-c", "import runpy; ns=runpy.run_path('src/mind_field_core.py', init_globals={'value': 9}); f=ns.get('evolve_field') or ns.get('step_field') or ns.get('advance_field'); assert [f(-7), f(0), f(9), f(123)] == [-34, 1, 46, 616]"],
    "runtime-dependency": ["$PYTHON", "-c", "import runpy, sys, types; ns=runpy.run_path('src/mind_field_core.py', init_globals={'value': 9}); module=types.ModuleType('mind_field_core'); module.__dict__.update(ns); sys.modules['mind_field_core']=module; result=runpy.run_path('src/field_runtime.py', init_globals={'value': 9}); assert result['result'] == 46"],
    "editor-contract": ["$PYTHON", "-c", "import runpy; ns=runpy.run_path('src/source_editor.py'); assert callable(ns['apply_patch_set']) and callable(ns['propose_candidates'])"],
    "workspace-index": ["$PYTHON", "-c", "import json, runpy; expected=json.load(open('workspace-index.json')); actual=runpy.run_path('src/workspace_index.py')['build_index']({path: open(path).read() for path in expected['files']}); assert actual == expected"],
}

SYMBOL_OPERATIONS = [
    {
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
    },
]


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _symbol(node):
    if isinstance(node, ast.FunctionDef):
        kind = "function"
    elif isinstance(node, ast.AsyncFunctionDef):
        kind = "async_function"
    elif isinstance(node, ast.ClassDef):
        kind = "class"
    else:
        return None
    return {"kind": kind, "name": node.name, "line": node.lineno, "end_line": node.end_lineno}


def _imports(node):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        prefix = "." * node.level + (node.module or "")
        return [prefix + ("." if prefix and alias.name else "") + alias.name for alias in node.names]
    return []


def _called_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _called_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _file_index(path, source):
    tree = ast.parse(source, filename=path)
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
    return {"sha256": sha256_text(source), "bytes": len(source.encode("utf-8")), "symbols": symbols, "imports": sorted(set(imports)), "calls": sorted(calls)}


def _dependencies(files):
    modules = {path.rsplit("/", 1)[-1][:-3]: path for path in files if path.endswith(".py")}
    dependencies = {path: set() for path in files if path.endswith(".py")}
    for path in dependencies:
        for imported in _file_index(path, files[path])["imports"]:
            module = imported.split(".", 1)[0].lstrip(".")
            if module in modules and modules[module] != path:
                dependencies[path].add(modules[module])
    return {path: sorted(values) for path, values in dependencies.items()}


def _reverse(dependencies):
    result = {path: [] for path in dependencies}
    for importer, imported in dependencies.items():
        for dependency in imported:
            result.setdefault(dependency, []).append(importer)
    return {path: sorted(values) for path, values in result.items()}


def build_index(files):
    entries = {path: _file_index(path, files[path]) for path in sorted(files) if path.endswith(".py")}
    dependencies = _dependencies(files)
    return {
        "schema": SCHEMA,
        "files": entries,
        "dependencies": dependencies,
        "reverse_dependencies": _reverse(dependencies),
        "scenarios": {name: list(paths) for name, paths in sorted(SCENARIOS.items())},
        "scenario_runners": dict(sorted(SCENARIO_RUNNERS.items())),
        "file_count": len(entries),
        "symbol_count": sum(len(item["symbols"]) for item in entries.values()),
        "scenario_commands": {name: list(command) for name, command in sorted(SCENARIO_COMMANDS.items())},
        "symbol_operations": [dict(operation) for operation in SYMBOL_OPERATIONS],
    }