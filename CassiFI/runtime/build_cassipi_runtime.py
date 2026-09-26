from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


RUNTIME_DIR = Path(__file__).resolve().parent
FI_ROOT = RUNTIME_DIR.parent
SOURCE_ROOT = FI_ROOT
DEFAULT_CLOSURE = RUNTIME_DIR / "cassipi_closure.json"
MANIFEST_NAME = "runtime-manifest.json"


class RuntimePackageError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_closure(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimePackageError(f"cannot read runtime closure: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != "cassifi.cassipi-runtime-closure.v1":
        raise RuntimePackageError("runtime closure has the wrong schema")
    for key in (
        "runtime_id",
        "entry_module",
        "modules",
        "runtime_modules",
        "resources",
        "forbidden_module_prefixes",
        "dependencies",
    ):
        if key not in value:
            raise RuntimePackageError(f"runtime closure is missing {key}")
    dependencies = value["dependencies"]
    if not isinstance(dependencies, list) or any(
        not isinstance(item, str) or not item for item in dependencies
    ) or set(dependencies) != {"numpy", "scipy", "torch"}:
        raise RuntimePackageError("runtime closure dependencies must be exactly numpy, scipy, and torch")
    return value


def _closure_files(closure: Mapping[str, Any]) -> tuple[tuple[Path, Path], ...]:
    files: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    groups = (
        (SOURCE_ROOT, tuple(closure["modules"])),
        (RUNTIME_DIR, tuple(closure["runtime_modules"])),
        (SOURCE_ROOT, tuple(closure["resources"])),
    )
    for source_root, items in groups:
        for item in items:
            if not isinstance(item, str) or not item:
                raise RuntimePackageError("closure paths must be non-empty strings")
            target = Path(item)
            if target.is_absolute() or ".." in target.parts or target.as_posix() != item:
                raise RuntimePackageError(f"closure path is not canonical: {item!r}")
            if item in seen:
                raise RuntimePackageError(f"duplicate closure path: {item}")
            source = source_root / target
            if not source.is_file():
                raise RuntimePackageError(f"closure input is missing: {item}")
            seen.add(item)
            files.append((source, target))
    return tuple(files)


def _local_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise RuntimePackageError(f"cannot parse {path.name}: {exc}") from exc
    names: set[str] = set()

    def collect(statements: Sequence[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".", 1)[0])
            elif isinstance(node, (ast.If, ast.Try)):
                collect(node.body)
                collect(node.orelse)
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        collect(handler.body)
                    collect(node.finalbody)

    collect(tree.body)
    return {name for name in names if name.startswith("cassi_")}


def _validate_import_closure(closure: Mapping[str, Any]) -> None:
    module_names = tuple(closure["modules"]) + tuple(closure["runtime_modules"])
    allowed = {Path(item).stem for item in module_names}
    forbidden = tuple(closure["forbidden_module_prefixes"])
    source_by_name = {
        **{item: SOURCE_ROOT / item for item in closure["modules"]},
        **{item: RUNTIME_DIR / item for item in closure["runtime_modules"]},
    }
    for item, source in source_by_name.items():
        for imported in _local_imports(source):
            if imported not in allowed:
                raise RuntimePackageError(f"{item} imports local module {imported!r} outside the closure")
            if imported.startswith(forbidden):
                raise RuntimePackageError(f"{item} imports forbidden module {imported!r}")


def _dependency_identity(closure: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    identities: dict[str, Mapping[str, Any]] = {}
    for name in closure["dependencies"]:
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            raise RuntimePackageError(f"the canonical runtime requires {name}") from exc
        identity: dict[str, Any] = {"version": getattr(module, "__version__", None)}
        if name == "torch":
            identity.update(
                {
                    "git_version": getattr(module.version, "git_version", None),
                    "hip_version": getattr(module.version, "hip", None),
                }
            )
        identities[name] = identity
    return identities


def build_runtime(output: Path, closure_path: Path = DEFAULT_CLOSURE) -> Mapping[str, Any]:
    closure = _load_closure(closure_path)
    files_to_copy = _closure_files(closure)
    _validate_import_closure(closure)
    output = output.resolve()
    if output.exists():
        raise RuntimePackageError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        files: list[Mapping[str, Any]] = []
        for source, relative in files_to_copy:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # The manifest pins every copied byte, so the copy is line-ending
            # normalised: a checkout that rewrites CRLF would otherwise carry
            # the same source under a digest the manifest does not record.
            target.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
            files.append(
                {
                    "path": relative.as_posix(),
                    "bytes": target.stat().st_size,
                    "sha256": _sha256(target),
                }
            )
        closure_bytes = _canonical_json(closure)
        dependencies = _dependency_identity(closure)
        manifest: Mapping[str, Any] = {
            "schema": "cassifi.cassipi-runtime-manifest.v1",
            "runtime_id": closure["runtime_id"],
            "entry_module": closure["entry_module"],
            "closure_sha256": hashlib.sha256(closure_bytes).hexdigest(),
            "python": {
                "implementation": sys.implementation.name,
                "version": list(sys.version_info[:3]),
            },
            "dependencies": dependencies,
            # Retain the historical torch identity field for consumers that
            # read the v1 manifest directly.
            "torch": dependencies["torch"],
            "files": files,
        }
        (staging / MANIFEST_NAME).write_bytes(_canonical_json(manifest))
        os.replace(staging, output)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_runtime(output: Path, closure_path: Path = DEFAULT_CLOSURE) -> Mapping[str, Any]:
    closure = _load_closure(closure_path)
    manifest_path = output / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimePackageError(f"cannot read packaged manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != "cassifi.cassipi-runtime-manifest.v1":
        raise RuntimePackageError("packaged manifest has the wrong schema")
    if manifest.get("runtime_id") != closure["runtime_id"]:
        raise RuntimePackageError("packaged runtime identity does not match the closure")
    dependencies = manifest.get("dependencies")
    expected_dependencies = set(closure["dependencies"])
    if (
        not isinstance(dependencies, dict)
        or set(dependencies) != expected_dependencies
        or any(not isinstance(row, dict) for row in dependencies.values())
    ):
        raise RuntimePackageError("packaged dependency identity does not match the closure")
    expected_paths = {target.as_posix() for _, target in _closure_files(closure)}
    rows = manifest.get("files")
    if not isinstance(rows, list) or {row.get("path") for row in rows if isinstance(row, dict)} != expected_paths:
        raise RuntimePackageError("packaged manifest file set does not match the closure")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise RuntimePackageError("packaged manifest contains an invalid file row")
        path = output / row["path"]
        if not path.is_file() or path.stat().st_size != row.get("bytes") or _sha256(path) != row.get("sha256"):
            raise RuntimePackageError(f"packaged file failed identity verification: {row['path']}")

    probe = """
import json, pathlib, sys, tempfile
import numpy
import scipy
import torch
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import cassi_cassipi_v2
import cassi_cassipi_worker
import cassi_field_atlas
import cassi_field_computer
import cassi_field_program
import cassi_field_cognition
import cassi_field_owner
import cassi_learning_computer
import cassi_regional_catalog
import cassi_variational_field
import cassi_resonant_field
import cassi_field_transceiver
compiled_program = cassi_field_program.compile_structured_program({
    "schema": cassi_field_program.SCHEMA,
    "main": [
        {"op": "set_acc", "value": 2},
        {"op": "add_acc", "value": 1},
        {"op": "push_acc", "stack": "left"},
    ],
})
computer = cassi_learning_computer.LearningComputer.initial("package-smoke")
computer, _ = computer.load(
    compiled_program.program,
    entry=compiled_program.entry,
    left=compiled_program.left,
    right=compiled_program.right,
)
computer, run_receipt = computer.advance(steps=1000)
machine_info = computer.inspect()
assert run_receipt["transitions_executed"] > 0
assert machine_info["status"] == "halted"
assert machine_info["task"]["left"] == [3]
retained_heat = machine_info["task"]["pc_observations"]
computer, _ = computer.restart(
    left=[7], right=[], entry=compiled_program.entry,
)
restart_info = computer.inspect()
assert restart_info["status"] == "running"
assert restart_info["task"]["left"] == [7]
assert restart_info["task"]["pc_observations"] == retained_heat
program = cassi_field_atlas.FieldProgram(
    "package-regional-program", 1, ("value",),
    (
        cassi_field_atlas.PrimitiveStep("identity", "once", ("value",)),
        cassi_field_atlas.PrimitiveStep("identity", "twice", ("once",)),
    ),
    ("twice",),
)
task = cassi_field_cognition.regional_program_state(
    program, {"value": 7}
)
cassi_field_atlas.FieldProgram.execute = lambda *args, **kwargs: (
    (_ for _ in ()).throw(AssertionError("legacy evaluator invoked"))
)
legacy_guard_fired = False
try:
    program.execute({"value": 7})
except AssertionError as exc:
    assert str(exc) == "legacy evaluator invoked"
    legacy_guard_fired = True
assert legacy_guard_fired
computer, submit_receipt = computer.submit(
    kernel="cognition.field", state=task, steps=1
)
assert submit_receipt["run"]["transitions_executed"] == 1
computer = cassi_learning_computer.LearningComputer.from_dict(
    json.loads(json.dumps(computer.as_dict()))
)
computer, _ = computer.advance(steps=64)
regional_info = computer.inspect()
assert regional_info["status"] == "halted"
assert regional_info["outcome"] == regional_info["consumed_result"]
assert regional_info["outcome"]["family"] == "cognition.field"
with tempfile.TemporaryDirectory() as temporary:
    adapter = cassi_cassipi_v2.CanonicalOwnerAdapter(
        root,
        data_home=pathlib.Path(temporary),
    )
    adapter.close()
loaded = sorted(
    name for name, module in sys.modules.items()
    if name.startswith('cassi_') and getattr(module, '__file__', None)
)
print(json.dumps(loaded))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimePackageError(f"packaged runtime import failed: {completed.stderr.strip()}")
    try:
        loaded = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimePackageError("packaged runtime import probe returned invalid JSON") from exc
    forbidden = tuple(closure["forbidden_module_prefixes"])
    violations = [name for name in loaded if name.startswith(forbidden)]
    if violations:
        raise RuntimePackageError(f"packaged runtime imported forbidden modules: {violations}")
    return {"manifest": manifest, "loaded_modules": loaded}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and verify the narrow canonical CassiPi FI runtime")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.verify_only:
            build_runtime(args.output, args.closure)
        result = verify_runtime(args.output.resolve(), args.closure)
    except RuntimePackageError as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "status": "PASS",
                "runtime_id": result["manifest"]["runtime_id"],
                "file_count": len(result["manifest"]["files"]),
                "loaded_modules": result["loaded_modules"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
