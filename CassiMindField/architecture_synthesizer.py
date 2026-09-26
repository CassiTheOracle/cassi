"""Deterministic lowering from Architecture IR to a Python workspace.

The synthesizer is intentionally closed: it accepts only a workspace mapping and
validated IR, performs AST/token/exact bounded edits, and returns a reproducible
candidate receipt.  It never invokes a shell, subprocess, network, or model.
"""
from __future__ import annotations

import ast
import hashlib
import io
import tokenize
from dataclasses import dataclass
from typing import Any, Mapping

try:
    from architecture_ir import (
        ArchitectureIR,
        ArchitectureValidationError,
        CreateModule,
        DeleteModule,
        InlineCall,
        MergeModule,
        MoveModule,
        Operation,
        SignatureMigration,
        SourceReplacement,
        SplitModule,
        SymbolRename,
        build_example,
        canonical_json,
        digest,
        relative_python_path,
    )
except ModuleNotFoundError:  # namespace-package import from the workspace root
    from .architecture_ir import (
        ArchitectureIR,
        ArchitectureValidationError,
        CreateModule,
        DeleteModule,
        InlineCall,
        MergeModule,
        MoveModule,
        Operation,
        SignatureMigration,
        SourceReplacement,
        SplitModule,
        SymbolRename,
        build_example,
        canonical_json,
        digest,
        relative_python_path,
    )

SYNTHESIS_SCHEMA = "cassimindfield.architecture-synthesis.v1"
_MAX_WORKSPACE_FILES = 8192
_MAX_FILE_BYTES = 1_048_576




class SynthesisError(ValueError):
    """Raised when a bounded architecture edit cannot be applied safely."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_digest_map(files: Mapping[str, str]) -> dict[str, str]:
    return {path: _sha256_text(files[path]) for path in sorted(files)}


def workspace_digest(files: Mapping[str, str]) -> str:
    """Digest file contents and names, independent of mapping insertion order."""
    return digest(_file_digest_map(files))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SynthesisError(message)


def _validate_workspace(files: Mapping[str, str]) -> dict[str, str]:
    _require(isinstance(files, Mapping), "workspace must be a path-to-source mapping")
    _require(len(files) <= _MAX_WORKSPACE_FILES, f"workspace exceeds {_MAX_WORKSPACE_FILES} files")
    checked: dict[str, str] = {}
    for raw_path, source in files.items():
        _require(isinstance(raw_path, str), "workspace paths must be strings")
        try:
            path = relative_python_path(raw_path, "workspace path")
        except ArchitectureValidationError as error:
            raise SynthesisError(str(error)) from error
        _require(isinstance(source, str), f"workspace source is not text: {path}")
        _require(len(source.encode("utf-8")) <= _MAX_FILE_BYTES, f"workspace source exceeds {_MAX_FILE_BYTES} bytes: {path}")
        try:
            ast.parse(source, filename=path)
        except SyntaxError as error:
            raise SynthesisError(f"workspace source does not parse before synthesis: {path}: {error.msg}") from error
        checked[path] = source
    return checked


def _parse(source: str, path: str) -> ast.Module:
    try:
        return ast.parse(source, filename=path)
    except SyntaxError as error:
        raise SynthesisError(f"edit produced invalid Python in {path}: {error.msg}") from error


def _ensure_file(files: Mapping[str, str], path: str, operation_id: str) -> None:
    _require(path in files, f"{operation_id}: source file is missing: {path}")


def _ensure_absent(files: Mapping[str, str], path: str, operation_id: str) -> None:
    _require(path not in files, f"{operation_id}: target file already exists: {path}")


def _replace_once(source: str, find: str, replace: str, path: str, operation_id: str) -> str:
    _require(find != "", f"{operation_id}: empty match is not bounded")
    count = source.count(find)
    _require(count == 1, f"{operation_id}: expected one match in {path}, found {count}")
    result = source.replace(find, replace, 1)
    _parse(result, path)
    return result


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for index, char in enumerate(source):
        if char == "\n":
            offsets.append(index + 1)
    return offsets


def _token_rename(source: str, old_name: str, new_name: str, path: str, operation_id: str) -> str:
    tree = _parse(source, path)
    del tree  # The parse is the structural guard; token replacement preserves formatting.
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as error:
        raise SynthesisError(f"{operation_id}: tokenization failed in {path}: {error}") from error
    offsets = _line_offsets(source)
    spans: list[tuple[int, int]] = []
    for token in tokens:
        if token.type != tokenize.NAME or token.string != old_name:
            continue
        start_line, start_col = token.start
        end_line, end_col = token.end
        start = offsets[start_line - 1] + start_col
        end = offsets[end_line - 1] + end_col
        spans.append((start, end))
    _require(spans, f"{operation_id}: symbol {old_name!r} is absent in {path}")
    result = source
    for start, end in reversed(spans):
        result = result[:start] + new_name + result[end:]
    _parse(result, path)
    return result


def _signature_migration(source: str, operation: SignatureMigration) -> str:
    tree = _parse(source, operation.path)
    matches = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == operation.symbol]
    _require(len(matches) == 1, f"{operation.id}: expected one function definition {operation.symbol!r} in {operation.path}")
    _require(source.count(operation.old_signature) == 1, f"{operation.id}: old signature must occur once in {operation.path}")
    node = matches[0]
    segment = ast.get_source_segment(source, node)
    _require(segment is not None and segment.startswith(operation.old_signature), f"{operation.id}: old signature is not the declaration prefix in {operation.path}")
    result = source.replace(operation.old_signature, operation.new_signature, 1)
    _parse(result, operation.path)
    return result


def _inline_call(source: str, operation: InlineCall) -> str:
    tree = _parse(source, operation.path)
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == operation.function:
            calls.append(node)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == operation.function:
            calls.append(node)
    _require(calls, f"{operation.id}: call to {operation.function!r} is absent in {operation.path}")
    _require(operation.find in source, f"{operation.id}: call text is absent in {operation.path}")
    return _replace_once(source, operation.find, operation.replace, operation.path, operation.id)


def _record_row(rows: list[dict[str, Any]], operation: Operation, path: str, before: str | None, after: str | None, method: str, detail: str) -> None:
    rows.append({
        "schema": "cassimindfield.architecture-patch.v1",
        "sequence": len(rows),
        "operation_id": operation.id,
        "operation_kind": operation.kind,
        "path": path,
        "method": method,
        "detail": detail,
        "before_sha256": None if before is None else _sha256_text(before),
        "after_sha256": None if after is None else _sha256_text(after),
        "before_bytes": None if before is None else len(before.encode("utf-8")),
        "after_bytes": None if after is None else len(after.encode("utf-8")),
    })


@dataclass(frozen=True)
class CandidateWorkspace:
    files: dict[str, str]
    manifest: dict[str, Any]
    patches: tuple[dict[str, Any], ...]
    source_digest: str
    proof_obligations: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        if workspace_digest(self.files) != self.source_digest:
            raise SynthesisError("candidate source digest does not match files")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SYNTHESIS_SCHEMA,
            "files": {path: self.files[path] for path in sorted(self.files)},
            "manifest": self.manifest,
            "patches": list(self.patches),
            "source_digest": self.source_digest,
            "proof_obligations": list(self.proof_obligations),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict()).decode("utf-8")
    @property
    def candidate_manifest(self) -> dict[str, Any]:
        return self.manifest

    @property
    def patch_rows(self) -> tuple[dict[str, Any], ...]:
        return self.patches


class ArchitectureSynthesizer:
    """Compile one validated IR in declaration order with transactional output."""

    def synthesize(self, workspace: Mapping[str, str], architecture: ArchitectureIR | Mapping[str, Any]) -> CandidateWorkspace:
        files = _validate_workspace(workspace)
        try:
            ir = architecture if isinstance(architecture, ArchitectureIR) else ArchitectureIR.from_dict(architecture)
        except ArchitectureValidationError as error:
            raise SynthesisError(str(error)) from error
        input_digest = workspace_digest(files)
        if ir.migration.source_digest is not None:
            _require(input_digest == ir.migration.source_digest, "migration source digest does not match input workspace")
        rows: list[dict[str, Any]] = []
        for operation in ir.operations:
            self._apply(files, operation, rows)
        self._validate_result(files, ir)
        output_digest = workspace_digest(files)
        file_manifest = {
            path: {"sha256": _sha256_text(files[path]), "bytes": len(files[path].encode("utf-8"))}
            for path in sorted(files)
        }
        proof_obligations = tuple(item.to_dict() for item in ir.proof_obligations)
        manifest: dict[str, Any] = {
            "schema": SYNTHESIS_SCHEMA,
            "candidate": "architecture-successor",
            "ir_digest": ir.digest(),
            "input_source_digest": input_digest,
            "source_digest": output_digest,
            "files": file_manifest,
            "operation_ids": [operation.id for operation in ir.operations],
            "patch_count": len(rows),
            "provenance_digest": digest(rows),
            "proof_obligation_ids": [item["id"] for item in proof_obligations],
        }
        return CandidateWorkspace(files=dict(files), manifest=manifest, patches=tuple(rows), source_digest=output_digest, proof_obligations=proof_obligations)

    def _apply(self, files: dict[str, str], operation: Operation, rows: list[dict[str, Any]]) -> None:
        if isinstance(operation, CreateModule):
            _ensure_absent(files, operation.path, operation.id)
            files[operation.path] = operation.source
            _record_row(rows, operation, operation.path, None, operation.source, "create", "bounded module creation")
            return
        if isinstance(operation, DeleteModule):
            _ensure_file(files, operation.path, operation.id)
            before = files.pop(operation.path)
            _record_row(rows, operation, operation.path, before, None, "delete", "bounded module deletion")
            return
        if isinstance(operation, MoveModule):
            _ensure_file(files, operation.source, operation.id)
            _ensure_absent(files, operation.target, operation.id)
            _require(operation.source != operation.target, f"{operation.id}: move source and target must differ")
            before = files.pop(operation.source)
            files[operation.target] = before
            _record_row(rows, operation, operation.source, before, None, "move", f"moved to {operation.target}")
            _record_row(rows, operation, operation.target, None, before, "move", f"moved from {operation.source}")
            return
        if isinstance(operation, SplitModule):
            _ensure_file(files, operation.source, operation.id)
            source_before = files.pop(operation.source)
            _require(all(target.path not in files for target in operation.targets), f"{operation.id}: split target already exists")
            _require(all(target.path != operation.source for target in operation.targets), f"{operation.id}: split target equals source")
            _record_row(rows, operation, operation.source, source_before, None, "split", "removed source module")
            for target in operation.targets:
                files[target.path] = target.source
                _record_row(rows, operation, target.path, None, target.source, "split", f"created split component {target.component}")
            return
        if isinstance(operation, MergeModule):
            _require(operation.target not in files, f"{operation.id}: merge target already exists")
            _require(operation.target not in operation.sources, f"{operation.id}: merge target is also a source")
            before_values: dict[str, str] = {}
            for path in operation.sources:
                _ensure_file(files, path, operation.id)
                before_values[path] = files.pop(path)
            for path in sorted(before_values):
                _record_row(rows, operation, path, before_values[path], None, "merge", f"merged into {operation.target}")
            files[operation.target] = operation.source
            _record_row(rows, operation, operation.target, None, operation.source, "merge", "created merged module")
            return
        if isinstance(operation, SignatureMigration):
            _ensure_file(files, operation.path, operation.id)
            before = files[operation.path]
            files[operation.path] = _signature_migration(before, operation)
            _record_row(rows, operation, operation.path, before, files[operation.path], "ast-signature", f"migrated {operation.symbol}")
            return
        if isinstance(operation, SymbolRename):
            for path in operation.paths:
                _ensure_file(files, path, operation.id)
            for path in operation.paths:
                before = files[path]
                files[path] = _token_rename(before, operation.old_name, operation.new_name, path, operation.id)
                _record_row(rows, operation, path, before, files[path], "token-symbol", f"renamed {operation.old_name} to {operation.new_name}")
            return
        if isinstance(operation, InlineCall):
            _ensure_file(files, operation.path, operation.id)
            before = files[operation.path]
            files[operation.path] = _inline_call(before, operation)
            _record_row(rows, operation, operation.path, before, files[operation.path], "ast-call-exact", f"inlined call to {operation.function}")
            return
        if isinstance(operation, SourceReplacement):
            _ensure_file(files, operation.path, operation.id)
            before = files[operation.path]
            files[operation.path] = _replace_once(before, operation.find, operation.replace, operation.path, operation.id)
            _record_row(rows, operation, operation.path, before, files[operation.path], "exact-once", "bounded source replacement")
            return
        raise SynthesisError(f"unsupported operation object: {type(operation).__name__}")

    @staticmethod
    def _validate_result(files: Mapping[str, str], ir: ArchitectureIR) -> None:
        component_modules = {component.module for component in ir.components}
        missing = sorted(path for path in component_modules if path not in files)
        if missing:
            raise SynthesisError(f"synthesis omitted declared component modules: {missing}")
        for path, source in files.items():
            _parse(source, path)
        for invariant in ir.invariants:
            if invariant.kind == "path":
                missing_paths = [path for path in invariant.paths if path not in files]
                if missing_paths:
                    raise SynthesisError(f"invariant {invariant.id} has missing paths: {missing_paths}")
            elif invariant.kind == "syntax":
                for path in invariant.paths:
                    _require(path in files, f"syntax invariant {invariant.id} has missing path: {path}")


def synthesize_architecture(workspace: Mapping[str, str], architecture: ArchitectureIR | Mapping[str, Any]) -> CandidateWorkspace:
    return synthesize_workspace(workspace, architecture)


def compile_architecture(workspace: Mapping[str, str], architecture: ArchitectureIR | Mapping[str, Any]) -> CandidateWorkspace:
    return synthesize_workspace(workspace, architecture)


def synthesize_workspace(workspace: Mapping[str, str], architecture: ArchitectureIR | Mapping[str, Any]) -> CandidateWorkspace:
    return ArchitectureSynthesizer().synthesize(workspace, architecture)


def synthesize_example() -> CandidateWorkspace:
    workspace, architecture = build_example()
    return synthesize_workspace(workspace, architecture)


__all__ = [
    "ArchitectureSynthesizer",
    "CandidateWorkspace",
    "SynthesisError",
    "SYNTHESIS_SCHEMA",
    "synthesize_workspace",
    "synthesize_architecture",
    "compile_architecture",
    "synthesize_example",
    "workspace_digest",
]
