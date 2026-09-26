import ast
import hashlib


SCHEMA = "cassimindfield.workspace-index.v1"


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
    return {
        "kind": kind,
        "name": node.name,
        "line": node.lineno,
        "end_line": node.end_lineno,
    }


def _import_name(node):
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
        imports.extend(_import_name(node))
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


def build_index(files):
    entries = {}
    for path in sorted(files):
        if not path.endswith(".py"):
            continue
        entries[path] = _file_index(path, files[path])
    return {
        "schema": SCHEMA,
        "files": entries,
        "file_count": len(entries),
        "symbol_count": sum(len(entry["symbols"]) for entry in entries.values()),
    }
