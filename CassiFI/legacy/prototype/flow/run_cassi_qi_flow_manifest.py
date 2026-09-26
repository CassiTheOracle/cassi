from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import sys
from collections import defaultdict, deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

HISTORICAL_SCHEMA = "cassi.qi-flow-historical-v2-manifest.v1"
SOURCE_INDEX_SCHEMA = "cassi.qi-flow-historical-v2-source-index.v2"
CHECKPOINT_INDEX_SCHEMA = "cassi.qi-flow-historical-v2-checkpoint-index.v1"
DEPENDENCY_SCHEMA = "cassi.qi-flow-dependency-manifest.v1"
RUN_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
ENVELOPE_SCHEMA = "cassi.qi-flow-run-spec-envelope.v1"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_CHECKPOINT_BYTES = 2 * 1024 * 1024 * 1024
CHECKPOINT_SUFFIXES = {".pt", ".pth", ".ckpt", ".bin"}
EXCLUDED_TOP_LEVEL = {".git", "_diag", "CassiFI", "historical", "native", "__pycache__"}
W0_CONTROL_FILES = {
    "run_cassi_qi_flow_manifest.py",
    "test_cassi_qi_flow_manifest.py",
    "verify_cassi_qi_flow_manifest.py",
}
NORMATIVE_DOCUMENTS = [
    "CassiFI/README.md",
    *[f"CassiFI/{number:02d}-{name}.md" for number, name in [
        (0, "foundations"),
        (1, "field-physics"),
        (2, "retention-capacity-and-cognition"),
        (3, "architecture-profiles-and-schemas"),
        (4, "execution-contract"),
        (5, "boundaries-body-and-action"),
        (6, "memory-and-learning"),
        (7, "world-loop-and-transactions"),
        (8, "language-and-serving"),
        (9, "backends-receipts-and-verification"),
        (10, "work-packages"),
        (11, "validation-gates"),
        (12, "decisions-deployment-and-completion"),
        (13, "requirements-registry"),
    ]],
]
EXPECTED_PACKAGES = {
    "W0", "W1", "W2", "W3", "W3N", "W4", "W4R", "W5", "W5V", "W6", "W6T", "W6A", "W6B",
    "W7", "W7P", "W8", "W9", "W9O", "W10", "W10R", "W10E", "W10A", "W11", "W11D",
    "W12M", "W12L", "W12A", "W12E", "W13R", "W13C", "W14A", "W14B", "W15A", "W15B", "W16A", "W16B",
}
EXPECTED_GATES = {
    "G0", "G1", "G2", "G3", "G3N", "G4", "G4R", "G5", "G5V", "G6", "G6T", "G6A", "G6B", "G6C",
    "G7", "G7P", "G8", "G9", "G9O", "G10", "G10A", "G10E", "G11", "G11D", "G12M", "G12L", "G12A", "G12E",
    "G13R", "G13C", "G13D", "G14A", "G14B", "G15A", "G15B",
}
STATIC_RUN_SPEC = (
    "manifest.json", "profile.json", "semantic-subhashes.json", "profile-projections.json",
    "schema-registry.json", "source-identity.json", "raw-retention-policy.json", "capability-matrix.json",
    "toolchain.json", "command-inputs.json", "static-fixture-index.json",
)


class ValidationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValidationError(f"non-canonical JSON value: {error}") from error


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def reject_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON constant is forbidden: {value}")


def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, *, maximum_bytes: int = MAX_JSON_BYTES) -> Any:
    require(path.is_file(), f"missing JSON file: {path}")
    body = path.read_bytes()
    require(len(body) <= maximum_bytes, f"JSON byte limit exceeded: {path}")
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
        raise ValidationError(f"invalid canonical JSON {path}: {error}") from error


def atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def immutable_write(path: Path, body: bytes) -> None:
    if path.exists():
        require(path.read_bytes() == body, f"immutable artifact drift: {path}")
        return
    atomic_write(path, body)


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ValidationError(f"path escapes root: {path}") from error


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def digest_file(path: Path, maximum_bytes: int) -> tuple[str, int]:
    require(path.is_file(), f"missing file: {path}")
    size = path.stat().st_size
    require(size <= maximum_bytes, f"byte limit exceeded: {path}")
    return sha256(path.read_bytes()), size


def all_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_TOP_LEVEL for part in rel.parts):
            continue
        yield path


def excluded_inventory(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    reasons = {
        ".git": "repository metadata is not pre-cutover runtime source",
        "_diag": "owner-live diagnostic evidence is explicitly retained in place and is not runtime-importable historical source",
        "CassiFI": "normative plan documents are pinned separately by the dependency manifest",
        "historical": "target historical snapshot must not recursively snapshot itself",
        "native": "native/llama.cpp is separately governed and no CassiFI W0 source mutation is authorized",
        "__pycache__": "derived executable cache is forbidden from the historical source payload",
    }
    for name in sorted(EXCLUDED_TOP_LEVEL):
        candidate = root / name
        if candidate.exists():
            records.append({"root": name, "reason": reasons[name]})
    for control in sorted(W0_CONTROL_FILES):
        candidate = root / control
        if candidate.is_file():
            records.append({"path": control, "reason": "W0 control implementation is provenance-bound in the bootstrap manifest, not historical v2 runtime source"})
    return records


def classify_inventory(root: Path, entry: Path, config: Path) -> tuple[list[Path], list[Path], list[dict[str, str]]]:
    source_files: list[Path] = []
    config_files: list[Path] = []
    for path in all_files(root):
        rel = relative(path, root)
        if rel in W0_CONTROL_FILES:
            continue
        if path.suffix == ".py":
            source_files.append(path)
        elif path.suffix == ".json":
            config_files.append(path)
    require(entry in source_files, f"entrypoint not classified as source: {entry}")
    require(config in config_files, f"designated config not classified: {config}")
    return source_files, config_files, excluded_inventory(root)


def candidates_for_module(root: Path, origin: Path, module: str | None, level: int, imported_name: str | None = None) -> list[Path]:
    if level:
        base = origin.parent
        for _ in range(level - 1):
            base = base.parent
        require(inside(base, root), f"relative import escapes root: {origin}")
        components = [] if module is None else module.split(".")
    else:
        base = root
        components = [] if module is None else module.split(".")
    candidate_base = base.joinpath(*components)
    choices = [candidate_base.with_suffix(".py"), candidate_base / "__init__.py"]
    if imported_name and module:
        choices.extend([candidate_base / f"{imported_name}.py", candidate_base / imported_name / "__init__.py"])
    if imported_name and module is None:
        choices.extend([base / f"{imported_name}.py", base / imported_name / "__init__.py"])
    return [choice.resolve() for choice in choices if choice.is_file() and inside(choice, root)]


def call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def string_argument(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def analyze_python(root: Path, origin: Path, *, strict_dynamic: bool = True) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(origin.read_text(encoding="utf-8"), filename=str(origin))
    except (UnicodeDecodeError, SyntaxError) as error:
        raise ValidationError(f"unparseable source {origin}: {error}") from error
    records: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                choices = candidates_for_module(root, origin, alias.name, 0)
                records.append({"origin": relative(origin, root), "kind": "import", "expression": alias.name, "line": node.lineno, "local_targets": [relative(choice, root) for choice in choices], "external": not choices, "classification": "local" if choices else "external"})
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for alias in node.names:
                choices = candidates_for_module(root, origin, module, node.level, alias.name)
                expression = ("." * node.level) + (module or "") + (f".{alias.name}" if module else alias.name)
                records.append({"origin": relative(origin, root), "kind": "from-import", "expression": expression, "line": node.lineno, "local_targets": [relative(choice, root) for choice in choices], "external": not choices, "classification": "local" if choices else "external"})
        elif isinstance(node, ast.Call) and call_name(node.func) in {"importlib.import_module", "__import__"}:
            literal = string_argument(node)
            if literal is None:
                require(not strict_dynamic, f"dynamic import is not statically declared: {origin}:{node.lineno}")
                records.append({"origin": relative(origin, root), "kind": "dynamic-import", "expression": None, "line": node.lineno, "local_targets": [], "external": None, "classification": "nonliteral-unresolved"})
                continue
            choices = candidates_for_module(root, origin, literal, 0)
            records.append({"origin": relative(origin, root), "kind": "dynamic-import", "expression": literal, "line": node.lineno, "local_targets": [relative(choice, root) for choice in choices], "external": not choices, "classification": "local" if choices else "external"})
    return records


def config_references(root: Path, config: Path, *, strict: bool = True) -> list[dict[str, Any]]:
    value = load_json(config)
    records: list[dict[str, Any]] = []
    def walk(item: Any, pointer: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                walk(nested, f"{pointer}/{key}")
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                walk(nested, f"{pointer}/{index}")
        elif isinstance(item, str):
            suffix = Path(item).suffix.lower()
            if suffix in CHECKPOINT_SUFFIXES or suffix in {".py", ".json"}:
                candidate = (config.parent / item.replace("\\", "/")).resolve()
                contained = inside(candidate, root)
                exists = contained and candidate.is_file()
                if strict:
                    require(contained, f"config reference escapes source root: {config}:{pointer}")
                    require(exists, f"unresolved config file reference: {config}:{pointer}:{item}")
                records.append({
                    "origin": relative(config, root),
                    "pointer": pointer,
                    "value": item,
                    "resolved": relative(candidate, root) if exists else None,
                    "exists": exists,
                    "classification": "existing-local-reference" if exists else "escapes-source-root" if not contained else "missing-local-reference",
                })
    walk(value, "")
    return records


def execution_closure(root: Path, entry: Path, config: Path) -> tuple[set[Path], list[dict[str, Any]], list[dict[str, Any]]]:
    closure: set[Path] = {entry.resolve(), config.resolve()}
    imports: list[dict[str, Any]] = []
    refs = config_references(root, config)
    queue: deque[Path] = deque([entry.resolve()])
    for record in refs:
        if record["resolved"] and Path(record["resolved"]).suffix == ".py":
            target = (root / record["resolved"]).resolve()
            if target not in closure:
                closure.add(target)
                queue.append(target)
    while queue:
        origin = queue.popleft()
        for record in analyze_python(root, origin):
            imports.append(record)
            for target_text in record["local_targets"]:
                target = (root / target_text).resolve()
                if target not in closure:
                    closure.add(target)
                    queue.append(target)
    return closure, imports, refs


def temporary_checkpoint_outputs(origin: Path, text: str) -> dict[tuple[str, int], dict[str, Any]]:
    """Prove literals are outputs inside a lexical TemporaryDirectory scope."""
    try:
        tree = ast.parse(text, filename=str(origin))
    except SyntaxError as error:
        raise ValidationError(f"unparseable source {origin}: {error}") from error
    scopes: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        for item in node.items:
            context = item.context_expr
            is_temporary = (
                isinstance(context, ast.Call)
                and isinstance(context.func, ast.Attribute)
                and context.func.attr == "TemporaryDirectory"
            )
            if is_temporary and isinstance(item.optional_vars, ast.Name):
                scopes.append((item.optional_vars.id, node.lineno, getattr(node, "end_lineno", node.lineno)))

    def temporary_path_variable(value: ast.AST, line: int) -> str | None:
        for node in ast.walk(value):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Path"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and any(variable == node.args[0].id and start <= line <= end for variable, start, end in scopes)
            ):
                return node.args[0].id
        return None

    proven: dict[tuple[str, int], dict[str, Any]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        if not isinstance(node.right, ast.Constant) or not isinstance(node.right.value, str):
            continue
        literal = node.right.value
        if Path(literal).suffix.lower() not in CHECKPOINT_SUFFIXES:
            continue
        variable = temporary_path_variable(node.left, node.lineno)
        if variable:
            proven[(literal, node.right.lineno)] = {
                "temporary_directory_variable": variable,
                "temporary_scope_start_line": next(start for name, start, end in scopes if name == variable and start <= node.lineno <= end),
                "output_expression_line": node.lineno,
            }
    return proven


def checkpoint_discovery(root: Path, closure: Iterable[Path], config_refs: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: dict[Path, list[dict[str, str]]] = defaultdict(list)
    observations: list[dict[str, Any]] = []
    pattern = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z0-9_./\\-]+\.(?:pt|pth|ckpt|bin))(?![A-Za-z0-9_])")
    for origin in sorted(set(closure), key=lambda path: relative(path, root)):
        if origin.suffix not in {".py", ".json"}:
            continue
        text = origin.read_text(encoding="utf-8", errors="strict")
        temporary_outputs = temporary_checkpoint_outputs(origin, text) if origin.suffix == ".py" else {}
        for match in pattern.finditer(text):
            literal = match.group(1)
            line = text.count("\n", 0, match.start()) + 1
            record: dict[str, Any] = {"origin": relative(origin, root), "literal": literal, "line": line}
            proof = temporary_outputs.get((literal, line))
            if proof:
                record.update({"classification": "runtime-created-temporary-output", "resolved": None, "exists": False, "proof": proof})
                observations.append(record)
                continue
            candidate = (origin.parent / literal.replace("\\", "/")).resolve()
            require(inside(candidate, root), f"checkpoint reference escapes root: {origin}:{literal}")
            record.update({"classification": "pre-existing-reachable-input", "resolved": relative(candidate, root), "exists": candidate.is_file()})
            observations.append(record)
            require(candidate.is_file(), f"unresolved reachable checkpoint: {origin}:{literal}")
            candidates[candidate].append({"origin": record["origin"], "literal": literal})
    for record in config_refs:
        value = record["value"]
        if Path(value).suffix.lower() in CHECKPOINT_SUFFIXES:
            target = (root / record["resolved"]).resolve()
            candidates[target].append({"origin": record["origin"], "literal": value})
    entries: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda path: relative(path, root)):
        digest, size = digest_file(candidate, MAX_CHECKPOINT_BYTES)
        entries.append({"original_path": relative(candidate, root), "historical_path": f"checkpoints/{digest}.bin", "sha256": digest, "byte_count": size, "references": candidates[candidate]})
    closure_rows = []
    for item in sorted(set(closure), key=lambda path: relative(path, root)):
        digest, size = digest_file(item, MAX_SOURCE_BYTES)
        closure_rows.append({"path": relative(item, root), "sha256": digest, "byte_count": size})
    return {"schema": "cassi.qi-flow-checkpoint-discovery.v1", "scan_scope": "entrypoint-and-config-transitive-closure", "scan_inputs": closure_rows, "literal_observations": observations, "entries": entries, "empty_set_proof": {"is_empty": not entries, "closure_sha256": sha256(canonical(closure_rows)), "observation_count": len(observations)}}


def external_dependencies(imports: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    names = sorted({record["expression"].lstrip(".").split(".")[0] for record in imports if record["external"] and record["expression"].lstrip(".")})
    result: list[dict[str, str]] = []
    for name in names:
        if name in stdlib:
            continue
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as error:
            raise ValidationError(f"unresolved external runtime dependency: {name}") from error
        result.append({"name": name, "version": version})
    return result


def snapshot_wrapper() -> bytes:
    return b'''from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import runpy
import sys
from pathlib import Path

class ValidationError(RuntimeError): pass

def fail(condition, message):
    if not condition: raise ValidationError(message)

def reject_constant(value): raise ValidationError(f"non-finite JSON constant: {value}")

def duplicate(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValidationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value

def load(path):
    body = path.read_bytes(); fail(len(body) <= 16 * 1024 * 1024, f"JSON too large: {path}")
    try: return json.loads(body.decode("utf-8"), object_pairs_hook=duplicate, parse_constant=reject_constant)
    except Exception as error: raise ValidationError(f"invalid JSON {path}: {error}") from error

def canon(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
def digest(body): return hashlib.sha256(body).hexdigest()
def inside(path, root):
    try: path.resolve().relative_to(root.resolve()); return True
    except ValueError: return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    project = base.parents[1]
    manifest_path = Path(args.manifest).resolve()
    config_path = Path(args.config).resolve()
    output_path = Path(args.output).resolve()
    fail(manifest_path == base / "manifest.json", "manifest must be the wrapper's canonical manifest.json")
    fail(config_path == base / "cassi-qi-language.json", "config must be the wrapper's canonical config")
    manifest = load(manifest_path)
    declared = dict(manifest); actual = declared.pop("self_sha256", None)
    fail(isinstance(actual, str) and digest(canon(declared)) == actual, "manifest self hash mismatch")
    fail(manifest.get("schema") == "cassi.qi-flow-historical-v2-manifest.v1", "historical schema mismatch")
    fail(digest(Path(__file__).read_bytes()) == manifest.get("wrapper_sha256"), "wrapper digest mismatch")
    for name, schema, hash_key in (("source-index.json", "cassi.qi-flow-historical-v2-source-index.v2", "source_index_sha256"), ("checkpoint-index.json", "cassi.qi-flow-historical-v2-checkpoint-index.v1", "checkpoint_index_sha256")):
        file = base / name; body = file.read_bytes(); fail(digest(body) == manifest.get(hash_key), f"{name} digest mismatch")
        index = load(file); fail(index.get("schema") == schema, f"{name} schema mismatch")
        entries = index.get("entries"); fail(isinstance(entries, list) and index.get("entry_count") == len(entries), f"{name} count mismatch")
        fail(index.get("byte_total") == sum(item.get("byte_count", -1) for item in entries), f"{name} byte total mismatch")
        for item in entries:
            target = (base / item.get("historical_path", "")).resolve()
            fail(inside(target, base) and target.is_file(), f"indexed object unavailable: {item}")
            body = target.read_bytes(); fail(len(body) == item.get("byte_count") and digest(body) == item.get("sha256"), f"indexed object mismatch: {target}")
    fail(digest(config_path.read_bytes()) == manifest.get("config_sha256"), "config digest mismatch")
    source = load(base / "source-index.json")
    source_entries = {entry["original_path"]: entry for entry in source["entries"]}
    closure = manifest.get("execution_closure")
    fail(isinstance(closure, list) and closure, "missing execution closure")
    for name in closure:
        fail(name in source_entries, f"closure member is not indexed: {name}")
    entry = manifest.get("entrypoint")
    fail(isinstance(entry, str) and entry in source_entries, "entrypoint is not indexed")
    source_root = (base / "source").resolve()
    actual_source = {path.relative_to(source_root).as_posix() for path in source_root.rglob("*") if path.is_file()}
    expected_source = {entry["original_path"] for entry in source["entries"]}
    fail(actual_source == expected_source, "unindexed source residue or missing indexed source")
    fail(not any(path.suffix == ".pyc" or "__pycache__" in path.parts for path in source_root.rglob("*")), "bytecode cache is forbidden")
    allowed_output = (project / manifest.get("wrapper_output_root", "")).resolve()
    fail(inside(output_path, allowed_output) and not inside(output_path, base), "output escapes the declared W0 artifact root")
    for dependency in manifest.get("external_dependencies", []):
        fail(importlib.metadata.version(dependency["name"]) == dependency["version"], f"external dependency drift: {dependency['name']}")
    clean = []
    for raw in sys.path:
        candidate = Path(raw or ".").resolve()
        if not inside(candidate, project): clean.append(raw)
    sys.path = [str(source_root), *clean]
    sys.dont_write_bytecode = True
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sys.argv = [str((source_root / entry).resolve()), "--output", str(output_path)]
    runpy.run_path(str((source_root / entry).resolve()), run_name="__main__")

if __name__ == "__main__": main()
'''


def build_historical(args: argparse.Namespace) -> None:
    root = Path(args.source_root).resolve()
    output = Path(args.historical_root).resolve()
    entry = (root / args.entrypoint).resolve()
    config = (root / args.config).resolve()
    require(inside(entry, root) and entry.is_file(), f"missing entrypoint: {entry}")
    require(inside(config, root) and config.is_file(), f"missing config: {config}")
    if output.exists():
        verify_historical(output)
        print(json.dumps({"status": "PASS", "mode": "reopen", "manifest_sha256": sha256((output / "manifest.json").read_bytes())}))
        return
    source_files, config_files, exclusions = classify_inventory(root, entry, config)
    inventory_import_audit = [
        record
        for source in sorted(source_files, key=lambda path: relative(path, root))
        for record in analyze_python(root, source, strict_dynamic=False)
    ]
    inventory_config_reference_audit = [
        record
        for config_file in sorted(config_files, key=lambda path: relative(path, root))
        for record in config_references(root, config_file, strict=False)
    ]
    closure, import_audit, config_audit = execution_closure(root, entry, config)
    discovery = checkpoint_discovery(root, closure, config_audit)
    entries: list[dict[str, Any]] = []
    for source in sorted(set(source_files + config_files), key=lambda path: relative(path, root)):
        digest, size = digest_file(source, MAX_SOURCE_BYTES)
        source_path = relative(source, root)
        if source == entry:
            disposition = "historical-entrypoint"
        elif source == config:
            disposition = "historical-config"
        elif source in closure:
            disposition = "historical-import-closure"
        elif source.name.startswith("test_"):
            disposition = "canonical-test-inventory"
        elif source.suffix == ".py":
            disposition = "canonical-caller-importer-inventory"
        else:
            disposition = "canonical-config-inventory"
        target = output / "source" / source_path
        immutable_write(target, source.read_bytes())
        entries.append({"original_path": source_path, "historical_path": f"source/{source_path}", "sha256": digest, "byte_count": size, "disposition": disposition})
    for checkpoint in discovery["entries"]:
        source = root / checkpoint["original_path"]
        immutable_write(output / checkpoint["historical_path"], source.read_bytes())
    source_index = {
        "schema": SOURCE_INDEX_SCHEMA,
        "entry_count": len(entries),
        "byte_total": sum(item["byte_count"] for item in entries),
        "entries": entries,
        "execution_closure": sorted(relative(path, root) for path in closure),
        "import_audit": import_audit,
        "config_reference_audit": config_audit,
        "inventory_import_audit": inventory_import_audit,
        "inventory_config_reference_audit": inventory_config_reference_audit,
        "inventory_coverage": {
            "python_files": [relative(source, root) for source in sorted(source_files, key=lambda path: relative(path, root))],
            "config_files": [relative(config_file, root) for config_file in sorted(config_files, key=lambda path: relative(path, root))],
            "python_file_count": len(source_files),
            "config_file_count": len(config_files),
        },
        "explicit_exclusions": exclusions,
    }
    checkpoint_index = {
        "schema": CHECKPOINT_INDEX_SCHEMA,
        "entry_count": len(discovery["entries"]),
        "byte_total": sum(item["byte_count"] for item in discovery["entries"]),
        "entries": discovery["entries"],
        "discovery": discovery,
    }
    source_bytes = canonical(source_index)
    checkpoint_bytes = canonical(checkpoint_index)
    immutable_write(output / "source-index.json", source_bytes)
    immutable_write(output / "checkpoint-index.json", checkpoint_bytes)
    immutable_write(output / "cassi-qi-language.json", config.read_bytes())
    wrapper = snapshot_wrapper()
    immutable_write(output / "run_cassi_qi_behavior_demo.py", wrapper)
    output_candidate = Path(args.wrapper_output_root)
    output_root = relative((output_candidate if output_candidate.is_absolute() else root / output_candidate).resolve(), root)
    require(not output_root.startswith("historical/"), "wrapper output root must be outside historical snapshot")
    toolchain = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "system": platform.system(),
    }
    manifest = {
        "schema": HISTORICAL_SCHEMA,
        "limits": {"max_json_bytes": MAX_JSON_BYTES, "max_source_bytes": MAX_SOURCE_BYTES, "max_checkpoint_bytes": MAX_CHECKPOINT_BYTES},
        "source_index": "source-index.json",
        "checkpoint_index": "checkpoint-index.json",
        "config": "cassi-qi-language.json",
        "wrapper": "run_cassi_qi_behavior_demo.py",
        "entrypoint": relative(entry, root),
        "execution_closure": source_index["execution_closure"],
        "source_count": len(entries),
        "checkpoint_count": len(discovery["entries"]),
        "source_index_sha256": sha256(source_bytes),
        "checkpoint_index_sha256": sha256(checkpoint_bytes),
        "config_sha256": sha256(config.read_bytes()),
        "wrapper_sha256": sha256(wrapper),
        "bootstrap_source_sha256": sha256(Path(__file__).read_bytes()),
        "independent_verifier_source_sha256": sha256(Path(__file__).with_name("verify_cassi_qi_flow_manifest.py").read_bytes()),
        "historical_command": {"argv": ["python", args.entrypoint], "entrypoint_arguments": [], "config_binding": "archived-and-wrapper-verified; legacy entrypoint has no config argument"},
        "capture_command": {"argv": list(sys.argv), "source_root": str(root), "historical_root": str(output)},
        "toolchain": toolchain,
        "external_dependencies": external_dependencies(import_audit),
        "checkpoint_proof": discovery["empty_set_proof"],
        "wrapper_output_root": output_root,
    }
    manifest["self_sha256"] = sha256(canonical(manifest))
    immutable_write(output / "manifest.json", canonical(manifest))
    verify_historical(output)
    print(json.dumps({"status": "PASS", "mode": "bootstrap", "manifest_sha256": sha256((output / "manifest.json").read_bytes()), "source_count": len(entries), "checkpoint_count": len(discovery["entries"])}))


def validate_index_entries(root: Path, index: dict[str, Any], schema: str, prefix: str, maximum_bytes: int) -> None:
    require(index.get("schema") == schema, f"unexpected index schema: {index.get('schema')}")
    entries = index.get("entries")
    require(isinstance(entries, list), "index entries must be a list")
    require(index.get("entry_count") == len(entries), "index entry count mismatch")
    require(index.get("byte_total") == sum(item.get("byte_count", -1) for item in entries), "index byte total mismatch")
    seen: set[str] = set()
    for item in entries:
        require(isinstance(item, dict), "index entry must be object")
        original = item.get("original_path")
        historical = item.get("historical_path")
        require(isinstance(original, str) and isinstance(historical, str), "invalid index paths")
        require(historical == f"{prefix}/{original}" if prefix == "source" else historical == f"checkpoints/{item.get('sha256')}.bin", "noncanonical historical path")
        require(original not in seen, f"duplicate source/checkpoint original path: {original}")
        seen.add(original)
        target = (root / historical).resolve()
        require(inside(target, root) and target.is_file(), f"indexed object unavailable: {historical}")
        digest, size = digest_file(target, maximum_bytes)
        require(digest == item.get("sha256") and size == item.get("byte_count"), f"indexed object digest/count mismatch: {historical}")


def verify_historical(output: Path) -> dict[str, Any]:
    output = output.resolve()
    manifest_path = output / "manifest.json"
    manifest = load_json(manifest_path)
    require(isinstance(manifest, dict), "manifest must be object")
    self_hash = manifest.pop("self_sha256", None)
    require(isinstance(self_hash, str) and sha256(canonical(manifest)) == self_hash, "historical manifest self hash mismatch")
    require(manifest.get("schema") == HISTORICAL_SCHEMA, "historical manifest schema mismatch")
    for name, schema, hash_key, prefix, maximum in [
        ("source-index.json", SOURCE_INDEX_SCHEMA, "source_index_sha256", "source", MAX_SOURCE_BYTES),
        ("checkpoint-index.json", CHECKPOINT_INDEX_SCHEMA, "checkpoint_index_sha256", "checkpoints", MAX_CHECKPOINT_BYTES),
    ]:
        body = (output / name).read_bytes()
        require(sha256(body) == manifest.get(hash_key), f"{name} manifest hash mismatch")
        index = load_json(output / name)
        require(isinstance(index, dict), f"{name} not object")
        validate_index_entries(output, index, schema, prefix, maximum)
    source_index = load_json(output / "source-index.json")
    source_entries = source_index["entries"]
    listed_source = {entry["original_path"] for entry in source_entries}
    actual_source = {path.relative_to(output / "source").as_posix() for path in (output / "source").rglob("*") if path.is_file()}
    require(actual_source == listed_source, "unindexed source residue or missing source entry")
    require(not any(path.suffix == ".pyc" or "__pycache__" in path.parts for path in (output / "source").rglob("*")), "historical source bytecode residue")
    require(manifest.get("source_count") == len(source_entries), "manifest source count mismatch")
    checkpoint_index = load_json(output / "checkpoint-index.json")
    require(manifest.get("checkpoint_count") == len(checkpoint_index["entries"]), "manifest checkpoint count mismatch")
    require(sha256((output / "cassi-qi-language.json").read_bytes()) == manifest.get("config_sha256"), "historical config mismatch")
    require(sha256((output / "run_cassi_qi_behavior_demo.py").read_bytes()) == manifest.get("wrapper_sha256"), "historical wrapper mismatch")
    require(manifest.get("entrypoint") in listed_source, "historical entrypoint missing from source index")
    closure = manifest.get("execution_closure")
    require(isinstance(closure, list) and closure and set(closure).issubset(listed_source), "invalid execution closure")
    require(isinstance(source_index.get("import_audit"), list) and isinstance(source_index.get("config_reference_audit"), list), "missing closure audits")
    require(isinstance(source_index.get("inventory_import_audit"), list) and isinstance(source_index.get("inventory_config_reference_audit"), list), "missing full inventory audits")
    coverage = source_index.get("inventory_coverage")
    require(isinstance(coverage, dict), "missing inventory coverage")
    python_files = coverage.get("python_files")
    config_files = coverage.get("config_files")
    require(isinstance(python_files, list) and isinstance(config_files, list), "invalid inventory coverage paths")
    require(coverage.get("python_file_count") == len(python_files) and coverage.get("config_file_count") == len(config_files), "invalid inventory coverage counts")
    require(set(python_files) | set(config_files) == listed_source, "inventory coverage does not classify every archived source")
    require(isinstance(manifest.get("bootstrap_source_sha256"), str) and isinstance(manifest.get("independent_verifier_source_sha256"), str), "missing bootstrap provenance")
    return {"manifest_sha256": sha256(manifest_path.read_bytes()), "source_count": len(source_entries), "checkpoint_count": len(checkpoint_index["entries"])}


def heading_sections(document: str, text: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"^###\s+((?:W|G)\d+[A-Z]?)\s+(?:—|-)\s+(.+)$", text, re.MULTILINE))
    sections: list[dict[str, Any]] = []
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        body = text[match.start():end]
        identifier = match.group(1)
        sections.append({"id": identifier, "kind": "work_package" if identifier.startswith("W") else "gate", "document": document, "title": match.group(2).strip(), "section_sha256": sha256(body.encode("utf-8")), "body": body})
    return sections


def identifiers(text: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\b{prefix}\d+[A-Z]?\b", text))


def artifact_tokens(text: str) -> set[str]:
    raw = re.findall(r"`([^`]+)`", text)
    artifacts: set[str] = set()
    for value in raw:
        if (value.startswith("cassi.") or value.startswith("Qi") or value.startswith("run_") or value.startswith("test_") or value.startswith("verify_") or value.endswith((".json", ".py", ".wprp"))):
            artifacts.add(value)
    artifacts.update(re.findall(r"\bcassi\.qi-flow-[A-Za-z0-9_.-]+\b", text))
    return artifacts


def registry_rows(root: Path) -> list[dict[str, Any]]:
    registry = (root / "CassiFI/13-requirements-registry.md").read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for line in registry.splitlines():
        match = re.match(r"^\|\s*`(QI-[A-Z]+-\d+)`\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", line)
        if not match:
            continue
        requirement, document, packages, gates, artifacts = match.groups()
        rows.append({"id": requirement, "owner_document": document, "packages": sorted(identifiers(packages, "W")), "gates": sorted(identifiers(gates, "G")), "artifacts": sorted(artifact_tokens(artifacts)), "row_sha256": sha256(line.encode("utf-8"))})
    require(rows, "requirements registry contains no rows")
    ids = [row["id"] for row in rows]
    require(len(ids) == len(set(ids)), "duplicate requirement registry row")
    return rows


def mermaid_views(documents: list[tuple[str, str]]) -> list[dict[str, str]]:
    views: list[dict[str, str]] = []
    for path, text in documents:
        for number, block in enumerate(re.findall(r"```mermaid\n(.*?)```", text, re.DOTALL), start=1):
            views.append({"path": path, "ordinal": str(number), "sha256": sha256(block.encode("utf-8"))})
    return views


def current_document_set(root: Path) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    for relative_document in NORMATIVE_DOCUMENTS:
        path = root / relative_document
        require(path.is_file(), f"missing normative document: {relative_document}")
        documents.append({"path": relative_document, "sha256": sha256(path.read_bytes())})
    return documents


def content_addressed_run_id(root: Path, historical_root: Path) -> str:
    manifest = load_json(historical_root / "manifest.json")
    require(isinstance(manifest, dict), "historical manifest must be an object")
    payload = {
        "schema": "cassi.qi-flow-w0-development-input.v1",
        "normative_document_set": current_document_set(root),
        "historical_manifest_sha256": sha256((historical_root / "manifest.json").read_bytes()),
        "bootstrap_source_sha256": sha256(Path(__file__).read_bytes()),
        "independent_verifier_source_sha256": sha256(Path(__file__).with_name("verify_cassi_qi_flow_manifest.py").read_bytes()),
        "entrypoint": manifest.get("entrypoint"),
        "config": manifest.get("config"),
        "wrapper_output_root": manifest.get("wrapper_output_root"),
    }
    return sha256(canonical(payload))


def make_graph(root: Path, historical_manifest_hash: str) -> dict[str, Any]:
    documents: list[tuple[str, str]] = []
    doc_nodes: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    for relative_document in NORMATIVE_DOCUMENTS:
        path = root / relative_document
        require(path.is_file(), f"missing normative document: {relative_document}")
        body = path.read_bytes().decode("utf-8")
        documents.append((relative_document, body))
        doc_nodes.append({"id": relative_document, "kind": "prose", "sha256": sha256(path.read_bytes())})
        sections.extend(heading_sections(relative_document, body))
    packages = [section for section in sections if section["kind"] == "work_package"]
    gates = [section for section in sections if section["kind"] == "gate"]
    require({item["id"] for item in packages} == EXPECTED_PACKAGES, "work-package heading set does not match normative 36-package set")
    require({item["id"] for item in gates} == EXPECTED_GATES, "gate heading set does not match normative 35-gate set")
    nodes: dict[tuple[str, str], dict[str, Any]] = {("prose", item["id"]): item for item in doc_nodes}
    for section in packages + gates:
        nodes[(section["kind"], section["id"])] = {key: section[key] for key in ("id", "kind", "document", "title", "section_sha256")}
    edges: set[tuple[str, str, str]] = set()
    artifact_sources: dict[str, set[str]] = defaultdict(set)
    for section in packages:
        owner = section["id"]
        dependencies = re.search(r"\*\*Dependencies:\*\*([^\n]+)", section["body"])
        if dependencies:
            for dependency in identifiers(dependencies.group(1), "W"):
                require(dependency in EXPECTED_PACKAGES, f"unknown work dependency: {dependency}")
                edges.add((dependency, owner, "depends-on"))
        for artifact in artifact_tokens(section["body"]):
            artifact_sources[artifact].add(owner)
            edges.add((owner, artifact, "owns"))
    for section in gates:
        gate = section["id"]
        work = re.search(r"\*\*Work packages:\*\*([^\n]+)", section["body"])
        if work:
            for package in identifiers(work.group(1), "W"):
                require(package in EXPECTED_PACKAGES, f"unknown gate package: {package}")
                edges.add((package, gate, "validated-by"))
        for artifact in artifact_tokens(section["body"]):
            artifact_sources[artifact].add(gate)
            edges.add((gate, artifact, "requires"))
    for _, text in documents:
        for left, right in re.findall(r"\b((?:W|G)\d+[A-Z]?)\s*(?:->|→)\s*((?:W|G)\d+[A-Z]?)\b", text):
            if left in EXPECTED_PACKAGES | EXPECTED_GATES and right in EXPECTED_PACKAGES | EXPECTED_GATES:
                edges.add((left, right, "declared-order"))
    rows = registry_rows(root)
    expected_requirements = {row["id"] for row in rows}
    for row in rows:
        nodes[("requirement", row["id"])] = {"id": row["id"], "kind": "requirement", "owner_document": row["owner_document"], "row_sha256": row["row_sha256"]}
        require(row["owner_document"] in NORMATIVE_DOCUMENTS, f"registry owner document not indexed: {row['owner_document']}")
        edges.add((row["owner_document"], row["id"], "defines"))
        for package in row["packages"]:
            require(package in EXPECTED_PACKAGES, f"registry unknown package: {package}")
            edges.add((package, row["id"], "implements"))
        for gate in row["gates"]:
            require(gate in EXPECTED_GATES, f"registry unknown gate: {gate}")
            edges.add((row["id"], gate, "consumed-by"))
        for artifact in row["artifacts"]:
            artifact_sources[artifact].add(row["id"])
            edges.add((row["id"], artifact, "requires"))
    for artifact in sorted(artifact_sources):
        nodes[("artifact", artifact)] = {"id": artifact, "kind": "artifact"}
    known = {identifier for _, identifier in nodes}
    require(all(left in known and right in known for left, right, _ in edges), "dangling graph edge")
    graph = {
        "schema": DEPENDENCY_SCHEMA,
        "historical_manifest_sha256": historical_manifest_hash,
        "normative_document_set": [{"path": path, "sha256": sha256(text.encode("utf-8"))} for path, text in documents],
        "section_inventory": [{key: section[key] for key in ("id", "kind", "document", "title", "section_sha256")} for section in packages + gates],
        "registry_rows": rows,
        "mermaid_views": mermaid_views(documents),
        "nodes": sorted(nodes.values(), key=lambda item: (item["kind"], item["id"])),
        "edges": [{"from": left, "to": right, "kind": kind} for left, right, kind in sorted(edges)],
        "expected_cardinalities": {"documents": len(NORMATIVE_DOCUMENTS), "packages": len(EXPECTED_PACKAGES), "gates": len(EXPECTED_GATES), "requirements": len(expected_requirements)},
    }
    validate_graph(graph, root)
    graph["self_sha256"] = sha256(canonical(graph))
    return graph


def is_acyclic(nodes: set[str], edges: Iterable[tuple[str, str]]) -> bool:
    successors: dict[str, set[str]] = {node: set() for node in nodes}
    incoming: dict[str, int] = {node: 0 for node in nodes}
    for left, right in edges:
        if left not in nodes or right not in nodes:
            continue
        if right not in successors[left]:
            successors[left].add(right)
            incoming[right] += 1
    queue = deque(sorted(node for node, count in incoming.items() if count == 0))
    visited = 0
    while queue:
        current = queue.popleft(); visited += 1
        for target in sorted(successors[current]):
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    return visited == len(nodes)


def validate_graph(graph: dict[str, Any], root: Path) -> None:
    require(graph.get("schema") == DEPENDENCY_SCHEMA, "dependency schema mismatch")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    require(isinstance(nodes, list) and isinstance(edges, list), "graph nodes/edges must be lists")
    node_keys = [(node.get("kind"), node.get("id")) for node in nodes if isinstance(node, dict)]
    require(len(node_keys) == len(nodes) == len(set(node_keys)), "duplicate or malformed graph node")
    package_nodes = {node["id"] for node in nodes if node["kind"] == "work_package"}
    gate_nodes = {node["id"] for node in nodes if node["kind"] == "gate"}
    require(package_nodes == EXPECTED_PACKAGES, "graph missing/extra work package")
    require(gate_nodes == EXPECTED_GATES, "graph missing/extra gate")
    rows = registry_rows(root)
    requirements = {row["id"] for row in rows}
    graph_requirements = {node["id"] for node in nodes if node["kind"] == "requirement"}
    require(graph_requirements == requirements, "graph requirements do not exactly match registry")
    prose = {node["id"] for node in nodes if node["kind"] == "prose"}
    require(prose == set(NORMATIVE_DOCUMENTS), "graph prose document set mismatch")
    known = {node["id"] for node in nodes}
    edge_keys = []
    for edge in edges:
        require(isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str) and isinstance(edge.get("kind"), str), "malformed graph edge")
        require(edge["from"] in known and edge["to"] in known, "dangling graph edge")
        edge_keys.append((edge["from"], edge["to"], edge["kind"]))
    require(len(edge_keys) == len(set(edge_keys)), "duplicate graph edge")
    require(is_acyclic(EXPECTED_PACKAGES, [(edge["from"], edge["to"]) for edge in edges if edge["kind"] == "depends-on" and edge["from"] in EXPECTED_PACKAGES and edge["to"] in EXPECTED_PACKAGES]), "cyclic work package dependency graph")
    require(is_acyclic(EXPECTED_GATES, [(edge["from"], edge["to"]) for edge in edges if edge["from"] in EXPECTED_GATES and edge["to"] in EXPECTED_GATES]), "cyclic gate dependency graph")
    required_edges = {(edge["from"], edge["to"], edge["kind"]) for edge in edges}
    for row in rows:
        require((row["owner_document"], row["id"], "defines") in required_edges, f"registry owner edge missing: {row['id']}")
        for package in row["packages"]:
            require((package, row["id"], "implements") in required_edges, f"registry package edge missing: {row['id']}:{package}")
        for gate in row["gates"]:
            require((row["id"], gate, "consumed-by") in required_edges, f"registry gate edge missing: {row['id']}:{gate}")
    for node in nodes:
        if node["kind"] == "artifact":
            require(any(edge["to"] == node["id"] and edge["kind"] in {"owns", "requires"} for edge in edges), f"orphan artifact: {node['id']}")


def self_hashed(schema: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = {"schema": schema, **payload}
    result["self_sha256"] = sha256(canonical(result))
    return result


def build_run_spec(root: Path, run_root: Path, run_id: str, historical: dict[str, Any], graph: dict[str, Any], args: argparse.Namespace) -> None:
    spec = run_root / "run-spec"
    fixture = spec / "oracle-fixtures" / "contract-root-bootstrap.json"
    section_hashes = graph["normative_document_set"]
    objects = {
        "manifest.json": self_hashed("cassi.qi-flow-run-spec-manifest.v1", {"run_id": run_id, "phase": "development", "status": "W0_COMPLETE_PENDING_W1", "historical_manifest_sha256": historical["manifest_sha256"], "dependency_manifest_sha256": graph["self_sha256"], "normative_document_set": section_hashes}),
        "profile.json": self_hashed("cassi.qi-flow-profile-handoff.v1", {"status": "BLOCKED_W1", "pending_owner": "W1", "blocking_reason": "contract-root/profile identity has no lawful W0 substitute", "required_contract": "cassi.qi-flow-contract-root.v1"}),
        "semantic-subhashes.json": self_hashed("cassi.qi-flow-semantic-subhashes.v1", {"status": "BLOCKED_W1", "pending_owner": "W1", "blocking_reason": "semantic subhashes derive only from the materialized W1 profile", "required_input": "cassi.qi-flow-contract-root.v1"}),
        "profile-projections.json": self_hashed("cassi.qi-flow-profile-projections.v1", {"status": "BLOCKED_W1", "pending_owner": "W1", "blocking_reason": "projection registry is profile-owned", "required_input": "cassi.qi-flow-profile-projections.v1"}),
        "schema-registry.json": self_hashed("cassi.qi-flow-schema-registry.v1", {"status": "BLOCKED_W1", "pending_owner": "W1", "blocking_reason": "schema registry must be materialized before profile decoding", "required_schema": "cassi.qi-flow-contract-root.v1"}),
        "source-identity.json": self_hashed("cassi.qi-flow-source-identity.v1", {"status": "W0_COMPLETE", "owner": "W0", "historical_manifest_sha256": historical["manifest_sha256"], "bootstrap_source_sha256": sha256(Path(__file__).read_bytes()), "normative_document_set": section_hashes}),
        "raw-retention-policy.json": self_hashed("cassi.qi-flow-raw-retention-policy.v1", {"status": "W0_COMPLETE", "owner": "W0", "policy": "immutable-content-addressed raw evidence; no deletion outside approved future cleanup receipt", "historical_manifest_sha256": historical["manifest_sha256"]}),
        "capability-matrix.json": self_hashed("cassi.qi-flow-capability-matrix.v1", {"status": "BLOCKED_W1", "pending_owner": "W1", "blocking_reason": "no implementation capability may be claimed before contract-root and profile validation", "rows_required_from": "CassiFI/13-requirements-registry.md"}),
        "toolchain.json": self_hashed("cassi.qi-flow-toolchain.v1", {"status": "W0_COMPLETE", "owner": "W0", "python_implementation": platform.python_implementation(), "python_version": platform.python_version(), "python_executable": sys.executable, "platform": platform.platform(), "machine": platform.machine(), "system": platform.system()}),
        "command-inputs.json": self_hashed("cassi.qi-flow-command-inputs.v1", {"status": "W0_COMPLETE", "owner": "W0", "argv": list(sys.argv), "run_id": run_id, "source_root": relative(root, root), "historical_manifest_sha256": historical["manifest_sha256"], "byte_limits": {"json": MAX_JSON_BYTES, "source": MAX_SOURCE_BYTES, "checkpoint": MAX_CHECKPOINT_BYTES}}),
        "static-fixture-index.json": self_hashed("cassi.qi-flow-static-fixture-index.v1", {"status": "W0_COMPLETE", "owner": "W0", "fixtures": ["run-spec/oracle-fixtures/contract-root-bootstrap.json"], "blocking_rule": "fixture is source-pinned W1 bootstrap input only and cannot interpret a W1 profile"}),
    }
    for name, payload in objects.items():
        immutable_write(spec / name, canonical(payload))
    verifier_source_sha256 = sha256(Path(__file__).with_name("verify_cassi_qi_flow_manifest.py").read_bytes())
    fixture_value = self_hashed("cassi.qi-flow-contract-root-bootstrap-fixture.v1", {"status": "W0_COMPLETE", "owner": "W0", "bootstrap_source_sha256": sha256(Path(__file__).read_bytes()), "independent_verifier_source_sha256": verifier_source_sha256, "historical_manifest_sha256": historical["manifest_sha256"], "dependency_manifest_sha256": graph["self_sha256"], "limits": {"max_json_bytes": MAX_JSON_BYTES}})
    immutable_write(fixture, canonical(fixture_value))
    request = self_hashed("cassi.qi-flow-g0-verification-request.v1", {"status": "PENDING_INDEPENDENT_VERIFICATION", "owner": "W0", "independent_verifier_source_sha256": verifier_source_sha256, "historical_manifest_sha256": historical["manifest_sha256"], "dependency_manifest_sha256": graph["self_sha256"], "run_id": run_id})
    immutable_write(run_root / "gates/g00-engineering-manifest/verification-request.json", canonical(request))


def build_development(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    run_root = Path(args.run_root).resolve()
    require(not run_root.exists(), f"development root already exists: {run_root}")
    historical_root = (root / args.historical_root).resolve()
    historical = verify_historical(historical_root)
    expected_run_id = content_addressed_run_id(root, historical_root)
    require(args.run_id == expected_run_id, f"run id is not the content address of the development inputs: expected {expected_run_id}")
    graph = make_graph(root, historical["manifest_sha256"])
    run_root.mkdir(parents=True)
    immutable_write(run_root / "run-spec/dependency-manifest.json", canonical(graph))
    build_run_spec(root, run_root, args.run_id, historical, graph, args)
    print(json.dumps({"status": "BUILT_PENDING_INDEPENDENT_VERIFICATION", "run_root": str(run_root), "run_id": args.run_id, "dependency_manifest_sha256": graph["self_sha256"], "nodes": len(graph["nodes"]), "edges": len(graph["edges"])}))


def seal_development(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    receipt_path = run_root / "gates/g00-engineering-manifest/verification.json"
    status_path = run_root / "gates/g00-engineering-manifest/status.json"
    receipt = load_json(receipt_path)
    status = load_json(status_path)
    require(receipt.get("status") == "PASS" and status.get("status") == "PASS", "independent G0 verification has not passed")
    files = [path for path in sorted(run_root.rglob("*"), key=lambda item: item.as_posix()) if path.is_file() and path.name != "index.json"]
    objects = []
    for path in files:
        digest, size = digest_file(path, MAX_JSON_BYTES)
        objects.append({"path": relative(path, run_root), "sha256": digest, "byte_count": size})
    index = self_hashed(RUN_INDEX_SCHEMA, {"status": "PASS_W0_G0", "run_id": args.run_id, "object_count": len(objects), "objects": objects, "historical_manifest_sha256": receipt["historical_manifest_sha256"], "dependency_manifest_sha256": receipt["dependency_manifest_sha256"], "independent_verifier_source_sha256": receipt["independent_verifier_source_sha256"]})
    immutable_write(run_root / "index.json", canonical(index))
    print(json.dumps({"status": "PASS", "index_sha256": sha256((run_root / "index.json").read_bytes()), "object_count": len(objects)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("historical-bootstrap", "development-build", "development-seal"))
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--root", default=".")
    parser.add_argument("--historical-root", default="historical/qi-v2")
    parser.add_argument("--entrypoint", default="run_cassi_qi_behavior_demo.py")
    parser.add_argument("--config", default="cassi-qi-language.json")
    parser.add_argument("--run-root", default="_diag/cassi-qi-flow-w0-final")
    parser.add_argument("--run-id", default="cassi-qi-flow-w0-final")
    parser.add_argument("--wrapper-output-root", default="_diag/cassi-qi-flow-w0-final/historical-smoke")
    args = parser.parse_args()
    if args.phase == "historical-bootstrap":
        build_historical(args)
    elif args.phase == "development-build":
        build_development(args)
    else:
        seal_development(args)


if __name__ == "__main__":
    try:
        main()
    except ValidationError as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}), file=sys.stderr)
        raise SystemExit(2)
