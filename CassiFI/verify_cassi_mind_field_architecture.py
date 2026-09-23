#!/usr/bin/env python3
"""Independently verify the Architecture IR and deterministic synthesis layer.

This verifier rebuilds the reference IR as a fresh JSON object, lowers it with a
second implementation, compares source digests, and exercises mutation/refusal
controls.  It intentionally does not import or execute any existing v8-v12
runtime or observatory file.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import sys
import tokenize
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
MIND_FIELD = WORKSPACE_ROOT / "CassiMindField"
if str(MIND_FIELD) not in sys.path:
    sys.path.insert(0, str(MIND_FIELD))

from architecture_ir import (  # noqa: E402
    ArchitectureIR,
    ArchitectureValidationError,
    CreateModule,
    DeleteModule,
    InlineCall,
    MergeModule,
    MoveModule,
    SignatureMigration,
    SourceReplacement,
    SplitModule,
    SymbolRename,
    build_example,
    canonical_json,
)
from architecture_synthesizer import ArchitectureSynthesizer, SynthesisError  # noqa: E402


class VerificationError(RuntimeError):
    """Raised when the independent evidence does not agree."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def independent_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def independent_workspace_digest(files: Mapping[str, str]) -> str:
    file_hashes = {path: hashlib.sha256(files[path].encode("utf-8")).hexdigest() for path in sorted(files)}
    return independent_digest(file_hashes)


def reference_ir_document() -> dict[str, Any]:
    """Rebuild the example IR without calling the production example builder."""
    return {
        "schema": "cassimindfield.architecture-ir.v1",
        "version": 1,
        "components": [
            {"id": "core", "module": "src/core_math.py", "kind": "module", "symbols": ["increment"]},
            {"id": "runtime", "module": "src/runtime.py", "kind": "runtime", "symbols": ["run"]},
            {"id": "api", "module": "src/api.py", "kind": "adapter", "symbols": ["execute"]},
        ],
        "interfaces": [
            {"id": "core_runtime", "provider": "core", "consumers": ["runtime"], "symbols": ["increment"], "protocol": "python-import"},
            {"id": "runtime_api", "provider": "runtime", "consumers": ["api"], "symbols": ["run"], "protocol": "python-import"},
        ],
        "state_ownership": [{"id": "runtime_state", "owner": "runtime", "path": "src/runtime.py", "kind": "runtime"}],
        "flows": [
            {"id": "core_to_runtime", "source": "core", "target": "runtime", "interface": "core_runtime", "kind": "call"},
            {"id": "runtime_to_api", "source": "runtime", "target": "api", "interface": "runtime_api", "kind": "call"},
        ],
        "invariants": [
            {"id": "all_python_parses", "kind": "syntax", "description": "Every successor module parses independently.", "paths": ["src/core_math.py", "src/runtime.py", "src/api.py"]},
            {"id": "one_runtime_owner", "kind": "ownership", "description": "Runtime state has exactly one owner.", "paths": ["src/runtime.py"]},
        ],
        "operations": [
            {"id": "move_core", "kind": "move_module", "source": "src/core.py", "target": "src/core_math.py"},
            {"id": "rename_add", "kind": "symbol_rename", "old_name": "add", "new_name": "increment", "paths": ["src/core_math.py", "src/runtime.py"]},
            {"id": "migrate_increment", "kind": "signature_migration", "path": "src/core_math.py", "symbol": "increment", "old_signature": "def increment(value):", "new_signature": "def increment(value, bias=1):"},
            {"id": "use_bias", "kind": "source_replacement", "path": "src/core_math.py", "find": "return value + 1", "replace": "return value + bias", "expected_count": 1},
            {"id": "retarget_import", "kind": "source_replacement", "path": "src/runtime.py", "find": "from core import increment", "replace": "from core_math import increment", "expected_count": 1},
            {"id": "create_api", "kind": "create_module", "path": "src/api.py", "component": "api", "source": "from runtime import run\n\n\ndef execute(value):\n    return run(value)\n"},
        ],
        "proof_obligations": [
            {"id": "parse_successor", "kind": "parse", "description": "The synthesized successor parses independently.", "target": "all_python_parses"},
            {"id": "digest_stable", "kind": "digest", "description": "Repeated synthesis has one source digest.", "target": "create_api"},
            {"id": "owner_unique", "kind": "ownership", "description": "State owner uniqueness remains true.", "target": "one_runtime_owner"},
        ],
        "migration": {
            "source_revision": "scenario-v12",
            "target_revision": "architecture-v1",
            "strategy": "clean_cutover",
            "compatibility": "breaking",
            "notes": "Move the core into an explicit successor API.",
        },
    }


def _parse(source: str, path: str) -> ast.Module:
    try:
        return ast.parse(source, filename=path)
    except SyntaxError as error:
        raise VerificationError(f"independent parse failed for {path}: {error.msg}") from error


def _replace_once(source: str, find: str, replace: str, path: str, operation_id: str) -> str:
    require(find and source.count(find) == 1, f"independent {operation_id} match cardinality failed in {path}")
    result = source.replace(find, replace, 1)
    _parse(result, path)
    return result


def _rename_tokens(source: str, old: str, new: str, path: str, operation_id: str) -> str:
    _parse(source, path)
    lines = source.splitlines(keepends=True)
    hits: list[tuple[int, int, int]] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.NAME and token.string == old:
                hits.append((token.start[0] - 1, token.start[1], token.end[1]))
    except tokenize.TokenError as error:
        raise VerificationError(f"independent tokenization failed in {path}: {error}") from error
    require(hits, f"independent {operation_id} found no {old!r} in {path}")
    for line_index, start, end in reversed(hits):
        line = lines[line_index]
        lines[line_index] = line[:start] + new + line[end:]
    result = "".join(lines)
    _parse(result, path)
    return result


def _independent_apply(workspace: Mapping[str, str], architecture: ArchitectureIR) -> dict[str, str]:
    """A separate lowering implementation used only by this verifier."""
    files = dict(workspace)
    for operation in architecture.operations:
        if isinstance(operation, MoveModule):
            require(operation.source in files and operation.target not in files, f"independent move refused: {operation.id}")
            files[operation.target] = files.pop(operation.source)
        elif isinstance(operation, CreateModule):
            require(operation.path not in files, f"independent create refused: {operation.id}")
            files[operation.path] = operation.source
        elif isinstance(operation, DeleteModule):
            require(operation.path in files, f"independent delete refused: {operation.id}")
            del files[operation.path]
        elif isinstance(operation, SplitModule):
            require(operation.source in files, f"independent split refused: {operation.id}")
            del files[operation.source]
            for target in operation.targets:
                require(target.path not in files, f"independent split target refused: {operation.id}")
                files[target.path] = target.source
        elif isinstance(operation, MergeModule):
            require(operation.target not in files and all(path in files for path in operation.sources), f"independent merge refused: {operation.id}")
            for path in operation.sources:
                del files[path]
            files[operation.target] = operation.source
        elif isinstance(operation, SignatureMigration):
            require(operation.path in files, f"independent signature path missing: {operation.id}")
            source = files[operation.path]
            tree = _parse(source, operation.path)
            functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == operation.symbol]
            require(len(functions) == 1 and source.count(operation.old_signature) == 1, f"independent signature guard failed: {operation.id}")
            files[operation.path] = _replace_once(source, operation.old_signature, operation.new_signature, operation.path, operation.id)
        elif isinstance(operation, SymbolRename):
            for path in operation.paths:
                require(path in files, f"independent rename path missing: {operation.id}")
                files[path] = _rename_tokens(files[path], operation.old_name, operation.new_name, path, operation.id)
        elif isinstance(operation, InlineCall):
            require(operation.path in files, f"independent inline path missing: {operation.id}")
            tree = _parse(files[operation.path], operation.path)
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id == operation.function) or (isinstance(node.func, ast.Attribute) and node.func.attr == operation.function))]
            require(calls, f"independent inline call missing: {operation.id}")
            files[operation.path] = _replace_once(files[operation.path], operation.find, operation.replace, operation.path, operation.id)
        elif isinstance(operation, SourceReplacement):
            require(operation.path in files, f"independent replacement path missing: {operation.id}")
            files[operation.path] = _replace_once(files[operation.path], operation.find, operation.replace, operation.path, operation.id)
        else:
            raise VerificationError(f"independent lowering lacks operation: {type(operation).__name__}")
    return files


def _expect_refusal(callable_value: Any, label: str) -> None:
    try:
        callable_value()
    except (ArchitectureValidationError, SynthesisError, VerificationError, ValueError):
        return
    raise VerificationError(f"mutation/refusal control was accepted: {label}")


def verify() -> dict[str, Any]:
    reference_workspace, _unused_production_example = build_example()
    ir_document = reference_ir_document()
    architecture = ArchitectureIR.from_dict(json.loads(json.dumps(ir_document, ensure_ascii=False)))
    require(architecture.to_dict() == ir_document, "rebuilt IR changed canonical JSON structure")
    production = ArchitectureSynthesizer().synthesize(reference_workspace, architecture)
    independent_files = _independent_apply(reference_workspace, architecture)
    independent_source_digest = independent_workspace_digest(independent_files)
    require(production.files == independent_files, "independent file tree differs from production synthesis")
    require(production.source_digest == independent_source_digest, "independent source digest differs")
    require(production.manifest["source_digest"] == independent_source_digest, "manifest source digest differs")
    require(independent_digest(production.patches) == production.manifest["provenance_digest"], "provenance digest is not reproducible")
    require(len(production.proof_obligations) == 3, "proof-obligation list was not emitted")
    require(all(ast.parse(source, filename=path) for path, source in production.files.items()), "successor parse control failed")
    repeated = ArchitectureSynthesizer().synthesize(reference_workspace, architecture)
    require(repeated.source_digest == production.source_digest, "repeated synthesis digest drifted")
    require(repeated.patches == production.patches, "repeated provenance rows drifted")

    mutated_candidate = dict(production.files)
    mutated_candidate["src/api.py"] = mutated_candidate["src/api.py"].replace("return run(value)", "return run(value + 1)", 1)
    require(independent_workspace_digest(mutated_candidate) != production.source_digest, "candidate mutation did not change digest")

    mutated_input = dict(reference_workspace)
    mutated_input["src/core.py"] = mutated_input["src/core.py"].replace("def add", "def altered", 1)
    _expect_refusal(lambda: ArchitectureSynthesizer().synthesize(mutated_input, architecture), "missing renamed symbol")
    require(reference_workspace["src/core.py"].startswith("def add"), "refusal mutated caller-owned input")

    malformed_ir = json.loads(json.dumps(ir_document))
    malformed_ir["state_ownership"].append({"id": "second_runtime_state", "owner": "runtime", "path": "src/runtime.py", "kind": "runtime"})
    _expect_refusal(lambda: ArchitectureIR.from_dict(malformed_ir), "duplicate state owner")

    malformed_operation = json.loads(json.dumps(ir_document))
    malformed_operation["operations"][3]["find"] = "return value + 999"
    malformed_architecture = ArchitectureIR.from_dict(malformed_operation)
    _expect_refusal(lambda: ArchitectureSynthesizer().synthesize(reference_workspace, malformed_architecture), "source replacement cardinality")

    return {
        "status": "PASS",
        "source_digest": production.source_digest,
        "file_count": len(production.files),
        "patch_count": len(production.patches),
        "proof_obligation_count": len(production.proof_obligations),
        "mutation_controls": 3,
        "independent_digest_match": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the measured receipt before PASS")
    arguments = parser.parse_args()
    receipt = verify()
    if arguments.json:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
