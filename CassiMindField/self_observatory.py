#!/usr/bin/env python3
"""Deterministic source observatory and bounded probe execution for CassiMindField.

This module intentionally has only standard-library dependencies.  It records source
identity at the byte level, then runs probes in a disposable copy of the workspace.
The returned values are data-only and can therefore be independently replayed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "cassimindfield.self-observatory.v13-v18.v1"
INDEX_SCHEMA = "cassimindfield.python-source-index.v1"
RESULT_SCHEMA = "cassimindfield.bounded-command-result.v1"
MAX_FILES = 4096
MAX_SOURCE_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 30.0


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return sha256_bytes(canonical(value))


def _bounded_text(value: Any, label: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > limit:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value


def _source_paths(root: Path) -> list[Path]:
    root = root.resolve()
    excluded = {".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "node_modules"}
    paths: list[Path] = []
    for path in root.rglob("*.py"):
        if path.is_symlink():
            raise ValueError(f"symlinked Python source is not allowed: {path}")
        if not path.is_file() or any(part in excluded for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size <= MAX_SOURCE_BYTES:
            paths.append(path)
    if len(paths) > MAX_FILES:
        raise ValueError(f"workspace contains more than {MAX_FILES} Python sources")
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())

def _line_offsets(source: bytes) -> list[int]:
    offsets = [0]
    for index, byte in enumerate(source):
        if byte == 10:
            offsets.append(index + 1)
    return offsets


def _span(node: ast.AST, source: bytes, offsets: list[int]) -> dict[str, int]:
    line = int(getattr(node, "lineno", 1))
    end_line = int(getattr(node, "end_lineno", line))
    col = int(getattr(node, "col_offset", 0))
    end_col = int(getattr(node, "end_col_offset", col))
    start = offsets[min(line - 1, len(offsets) - 1)] + col
    end = offsets[min(end_line - 1, len(offsets) - 1)] + end_col
    return {"byte_start": start, "byte_end": end, "line": line, "column": col, "end_line": end_line, "end_column": end_col}


def _name(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _walk_symbols(tree: ast.AST, source: bytes, offsets: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        current = parents
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = str(getattr(node, "name", "<anonymous>"))
            current = (*parents, name)
            rows.append({"kind": type(node).__name__.removesuffix("Def").lower(), "name": name, "qualname": ".".join(current), "span": _span(node, source, offsets)})
        for child in ast.iter_child_nodes(node):
            visit(child, current)
    visit(tree, ())
    return rows


def _walk_imports(tree: ast.AST, source: bytes, offsets: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                rows.append({"kind": "import", "name": alias.name, "asname": alias.asname, "span": _span(node, source, offsets)})
        elif isinstance(node, ast.ImportFrom):
            module = "." * int(node.level) + (node.module or "")
            for alias in node.names:
                rows.append({"kind": "from", "module": module, "name": alias.name, "asname": alias.asname, "span": _span(node, source, offsets)})
    return sorted(rows, key=lambda row: (row["span"]["byte_start"], row["kind"], row.get("module", ""), row["name"]))


def _walk_calls(tree: ast.AST, source: bytes, offsets: list[int]) -> list[dict[str, Any]]:
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            rows.append({"callee": _name(node.func), "argument_count": len(node.args) + len(node.keywords), "span": _span(node, source, offsets)})
    return sorted(rows, key=lambda row: (row["span"]["byte_start"], row["callee"]))


def index_workspace(workspace: str | os.PathLike[str]) -> dict[str, Any]:
    """Return a canonical recursive Python source/symbol/import/call index."""
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError(f"workspace is not a directory: {root}")
    files: list[dict[str, Any]] = []
    for path in _source_paths(root):
        raw = path.read_bytes()
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Python source is not UTF-8: {path}") from exc
        try:
            tree = ast.parse(source, filename=path.as_posix(), type_comments=True)
        except SyntaxError as exc:
            raise ValueError(f"cannot parse Python source {path}: {exc}") from exc
        relative = path.relative_to(root).as_posix()
        offsets = _line_offsets(raw)
        row = {
            "path": relative,
            "source_sha256": sha256_bytes(raw),
            "source_revision_id": "source:" + sha256_bytes(raw)[:32],
            "byte_length": len(raw),
            "symbols": _walk_symbols(tree, raw, offsets),
            "imports": _walk_imports(tree, raw, offsets),
            "calls": _walk_calls(tree, raw, offsets),
            "is_test": path.name.startswith("test_") or path.name.endswith("_test.py") or "tests" in path.relative_to(root).parts,
        }
        row["file_digest"] = digest({k: row[k] for k in row if k != "file_digest"})
        files.append(row)
    payload = {"schema": INDEX_SCHEMA, "root_name": root.name, "files": files, "test_paths": [r["path"] for r in files if r["is_test"]]}
    payload["workspace_revision_id"] = "workspace:" + digest({"files": [{"path": r["path"], "sha256": r["source_sha256"]} for r in files]})
    payload["content_sha256"] = digest(payload)
    return payload


def _copy_workspace(source: Path, target: Path) -> None:
    for item in source.iterdir():
        if item.is_symlink():
            raise ValueError(f"symlinked workspace entry is not allowed: {item}")
        if item.name in {".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "node_modules"}:
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, ignore=shutil.ignore_patterns("*.pyc", "__pycache__"))
        else:
            shutil.copy2(item, destination)


def _truncate(raw: bytes, limit: int) -> tuple[str, bool, int]:
    truncated = len(raw) > limit
    visible = raw[:limit]
    return visible.decode("utf-8", errors="replace"), truncated, len(raw)


def run_bounded_command(command: Sequence[str] | str, *, workspace: str | os.PathLike[str] | None = None, cwd: str = ".", timeout_seconds: float = 10.0, env: Mapping[str, str] | None = None, max_output_bytes: int = MAX_OUTPUT_BYTES) -> dict[str, Any]:
    """Run one command in a disposable workspace and capture bounded evidence."""
    if isinstance(command, str):
        command = (command,)
    command = tuple(_bounded_text(str(part), "command argument", 8192) for part in command)
    if not command:
        raise ValueError("command must not be empty")
    if not 0 < float(timeout_seconds) <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be in (0, {MAX_TIMEOUT_SECONDS}]")
    if not 1 <= int(max_output_bytes) <= MAX_OUTPUT_BYTES:
        raise ValueError("max_output_bytes is out of bounds")
    original = Path(workspace).resolve() if workspace is not None else None
    source_index = index_workspace(original) if original is not None else None
    started = time.perf_counter_ns()
    cpu_started = time.process_time_ns()
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="cassimindfield-probe-") as temporary:
        isolated = Path(temporary)
        if original is not None:
            _copy_workspace(original, isolated)
        run_cwd = (isolated / cwd).resolve()
        try:
            inside = os.path.commonpath((str(isolated), str(run_cwd))) == str(isolated)
        except ValueError:
            inside = False
        if not inside or not run_cwd.is_dir():
            raise ValueError("cwd must remain inside the isolated workspace")
        expanded = tuple(part.replace("{workspace}", str(isolated)) for part in command)
        child_env = os.environ.copy()
        if env:
            child_env.update({str(k): str(v) for k, v in env.items()})
        child_env["PYTHONHASHSEED"] = "0"
        try:
            completed = subprocess.run(expanded, cwd=run_cwd, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=float(timeout_seconds), check=False)
            returncode: int | None = int(completed.returncode)
            stdout, stdout_truncated, stdout_bytes = _truncate(completed.stdout, int(max_output_bytes))
            stderr, stderr_truncated, stderr_bytes = _truncate(completed.stderr, int(max_output_bytes))
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = None
            out = exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or "").encode()
            err = exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or "").encode()
            stdout, stdout_truncated, stdout_bytes = _truncate(out, int(max_output_bytes))
            stderr, stderr_truncated, stderr_bytes = _truncate(err, int(max_output_bytes))
    ended = time.perf_counter_ns()
    result = {"schema": RESULT_SCHEMA, "command": list(command), "cwd": cwd, "returncode": returncode, "timed_out": timed_out, "stdout": stdout, "stderr": stderr, "stdout_truncated": stdout_truncated, "stderr_truncated": stderr_truncated, "stdout_bytes": stdout_bytes, "stderr_bytes": stderr_bytes, "timing": {"wall_ns": ended - started, "process_ns": time.process_time_ns() - cpu_started}, "workspace_revision_id": None if source_index is None else source_index["workspace_revision_id"], "source_index_sha256": None if source_index is None else source_index["content_sha256"]}
    result["content_sha256"] = digest({k: result[k] for k in result if k != "content_sha256" and k != "timing"})
    return result


def source_references(index: Mapping[str, Any], paths: Iterable[str] | None = None) -> list[dict[str, Any]]:
    wanted = None if paths is None else {str(path).replace("\\", "/") for path in paths}
    refs = []
    for row in index.get("files", []):
        if wanted is not None and row.get("path") not in wanted:
            continue
        refs.append({"path": row["path"], "source_revision_id": row["source_revision_id"], "source_sha256": row["source_sha256"], "byte_spans": [symbol["span"] for symbol in row.get("symbols", [])]})
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", default=".")
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument("--command", nargs="+")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    index = index_workspace(args.workspace)
    if args.index_only or not args.command:
        print(json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    result = run_bounded_command(args.command, workspace=args.workspace, timeout_seconds=args.timeout)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["returncode"] == 0 and not result["timed_out"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
