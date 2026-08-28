from __future__ import annotations
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
