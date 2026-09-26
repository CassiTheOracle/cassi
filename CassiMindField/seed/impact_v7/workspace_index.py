import ast
import hashlib


SCHEMA = "cassimindfield.workspace-index.v2"
SCENARIOS = {
    "core-behavior": ["src/mind_field_core.py"],
    "runtime-dependency": ["src/mind_field_core.py", "src/field_runtime.py"],
    "editor-contract": ["src/source_editor.py"],
    "workspace-index": ["src/workspace_index.py"],
}


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
    return {
        "sha256": sha256_text(source),
        "bytes": len(source.encode("utf-8")),
        "symbols": symbols,
        "imports": sorted(set(imports)),
        "calls": sorted(calls),
    }


def _workspace_dependencies(files):
    modules = {path.rsplit("/", 1)[-1][:-3]: path for path in files if path.endswith(".py")}
    dependencies = {path: set() for path in files if path.endswith(".py")}
    for path in dependencies:
        for imported in _file_index(path, files[path])["imports"]:
            module = imported.split(".", 1)[0].lstrip(".")
            if module in modules and modules[module] != path:
                dependencies[path].add(modules[module])
    return {path: sorted(values) for path, values in dependencies.items()}


def _reverse_dependencies(dependencies):
    reverse = {path: [] for path in dependencies}
    for importer, imported in dependencies.items():
        for dependency in imported:
            reverse.setdefault(dependency, []).append(importer)
    return {path: sorted(values) for path, values in reverse.items()}


def build_index(files):
    entries = {}
    for path in sorted(files):
        if path.endswith(".py"):
            entries[path] = _file_index(path, files[path])
    dependencies = _workspace_dependencies(files)
    return {
        "schema": SCHEMA,
        "files": entries,
        "dependencies": dependencies,
        "reverse_dependencies": _reverse_dependencies(dependencies),
        "scenarios": {name: list(paths) for name, paths in sorted(SCENARIOS.items())},
        "file_count": len(entries),
        "symbol_count": sum(len(item["symbols"]) for item in entries.values()),
    }
