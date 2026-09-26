"""Independent W15B/G15B verifier for the QI requirements registry.

This module intentionally parses bytes and Markdown itself.  It does not import
Cassi-QI runtime/profile modules, and it never turns missing evidence into PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "cassi.qi-flow-requirements-registry-verification.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIREMENT_RE = re.compile(r"^QI-[A-Z0-9][A-Z0-9-]*-\d{3}$")
PACKAGE_RE = re.compile(r"\bW\d+[A-Z]*\b")
GATE_RE = re.compile(r"\bG\d+[A-Z]*\b")


class RequirementsVerificationError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "strict")


def canonical_hash(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8", "strict")
    payload = canonical_json_bytes(value)
    framed = len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload
    return hashlib.sha256(framed).hexdigest()


def _self_hash(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("self_sha256", None)
    return canonical_hash(body, str(value.get("schema", SCHEMA)))


def _finish(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["self_sha256"] = _self_hash(result)
    return result


def _write_json(path: Path, value: Mapping[str, Any]) -> bytes:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return raw


def _split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
            continue
        if char == "\\" and not escaped:
            escaped = True
            current.append(char)
            continue
        escaped = False
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def parse_registry(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"MISSING_REGISTRY:{path.as_posix()}:{exc}"]
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        if "|" not in line:
            continue
        cells = _split_row(line)
        if len(cells) < 2 or set(cells[0].replace("-", "").strip()) <= {""}:
            continue
        requirement_id = cells[0].strip().strip("`")
        if not REQUIREMENT_RE.fullmatch(requirement_id):
            continue
        rows.append({"line": number, "id": requirement_id, "cells": cells})
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["id"]] = counts.get(row["id"], 0) + 1
    for requirement_id, count in sorted(counts.items()):
        if count != 1:
            errors.append(f"REQUIREMENT_NOT_EXACTLY_ONCE:{requirement_id}:{count}")
    for row in rows:
        cells = row["cells"]
        if len(cells) < 6:
            errors.append(f"ROW_MISSING_COVERAGE_COLUMNS:{row['id']}:line{row['line']}")
            continue
        owner, package, gate, artifact, failure = cells[1:6]
        if not re.search(r"(?:^|[`\s])(?:CassiFI/)?[0-9]{2}-[^`\s|]+\.md", owner):
            errors.append(f"ROW_OWNER_DOCUMENT_INVALID:{row['id']}")
        if not PACKAGE_RE.search(package):
            errors.append(f"ROW_PACKAGE_INVALID:{row['id']}")
        if not GATE_RE.search(gate):
            errors.append(f"ROW_GATE_INVALID:{row['id']}")
        if not artifact or artifact in {"—", "-", "TBD", "TODO"}:
            errors.append(f"ROW_ARTIFACT_COVERAGE_MISSING:{row['id']}")
        if not failure or failure in {"—", "-", "TBD", "TODO"}:
            errors.append(f"ROW_FAILURE_COVERAGE_MISSING:{row['id']}")
    if not rows:
        errors.append("REGISTRY_HAS_NO_QI_ROWS")
    return rows, errors


def _scan_requirement_ids(docs_path: Path, registry_path: Path) -> set[str]:
    expected: set[str] = set()
    paths: Iterable[Path]
    if docs_path.is_file():
        paths = (docs_path,)
    elif docs_path.exists():
        paths = sorted(docs_path.rglob("*.md"))
    else:
        return expected
    registry_resolved = registry_path.resolve()
    for path in paths:
        try:
            if path.resolve() == registry_resolved:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        expected.update(REQUIREMENT_RE.findall(text))
    return expected


def _documents_from_manifest(manifest_path: Path | None, docs_path: Path) -> set[str]:
    if manifest_path is not None and manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, Mapping):
            names: set[str] = set()
            for key in ("normative_document_set", "documents", "document_set"):
                value = payload.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            names.add(item.replace("\\", "/"))
                        elif isinstance(item, Mapping):
                            candidate = item.get("path", item.get("document"))
                            if isinstance(candidate, str):
                                names.add(candidate.replace("\\", "/"))
            if names:
                return names
    if docs_path.is_file():
        return {docs_path.name}
    if docs_path.exists():
        return {path.relative_to(docs_path).as_posix() for path in docs_path.rglob("*.md")}
    return set()


def _owner_document(row: Mapping[str, Any]) -> str:
    cells = row.get("cells", [])
    if isinstance(cells, list) and len(cells) > 1:
        match = re.search(r"(?:CassiFI/)?([0-9]{2}-[^`\s|]+\.md)", str(cells[1]))
        if match:
            return match.group(1)
    return ""


def _row_tokens(rows: Sequence[Mapping[str, Any]], index: int, pattern: re.Pattern[str]) -> set[str]:
    tokens: set[str] = set()
    for row in rows:
        cells = row.get("cells", [])
        if isinstance(cells, list) and len(cells) > index:
            tokens.update(pattern.findall(str(cells[index])))
    return tokens


def _owner_map_tokens(path: Path | None, pattern: re.Pattern[str]) -> set[str]:
    if path is None or not path.exists():
        return set()
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else "\n".join(p.read_text(encoding="utf-8") for p in path.rglob("*.md"))
    except (OSError, UnicodeError):
        return set()
    return set(pattern.findall(text))


def _navigation_pointer(root_plan: Path, documents: Iterable[str]) -> list[str]:
    try:
        text = root_plan.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"MISSING_ROOT_PLAN:{root_plan.as_posix()}:{exc}"]
    errors: list[str] = []
    for document in documents:
        name = Path(document).name
        if name and name not in text:
            errors.append(f"ROOT_PLAN_MISSING_NAVIGATION:{name}")
    # A pointer may contain headings for navigation, but not normative package
    # prose or copied requirement rows.  Requirement IDs in the root are a hard
    # violation because the CassiFI split set is authoritative.
    if REQUIREMENT_RE.search(text):
        errors.append("ROOT_PLAN_NOT_NAVIGATION_POINTER:contains-QI-requirement")
    if re.search(r"^#{2,}\s+(?:W|G)\d", text, re.MULTILINE):
        errors.append("ROOT_PLAN_NOT_NAVIGATION_POINTER:contains-package-or-gate-heading")
    return errors


def verify_requirements_registry(
    *,
    registry_path: Path,
    docs_path: Path,
    gates_path: Path | None = None,
    owner_map_path: Path | None = None,
    manifest_path: Path | None = None,
    root_plan_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    rows, errors = parse_registry(registry_path)
    ids = [str(row["id"]) for row in rows]
    expected_ids = _scan_requirement_ids(docs_path, registry_path)
    registered_ids = set(ids)
    for requirement_id in sorted(expected_ids - registered_ids):
        errors.append(f"REQUIREMENT_MISSING_FROM_REGISTRY:{requirement_id}")
    documents = _documents_from_manifest(manifest_path, docs_path)
    owner_documents = {_owner_document(row) for row in rows if _owner_document(row)}
    for document in sorted(documents):
        name = Path(document).name
        if name == "README.md":
            continue
        if name not in owner_documents and document not in owner_documents:
            errors.append(f"DOCUMENT_MISSING_REQUIREMENT_OWNER:{document}")
    package_rows = _row_tokens(rows, 2, PACKAGE_RE)
    gate_rows = _row_tokens(rows, 3, GATE_RE)
    if owner_map_path is None:
        errors.append("MISSING_OWNER_MAP")
    else:
        if not owner_map_path.exists():
            errors.append(f"MISSING_OWNER_MAP:{owner_map_path.as_posix()}")
        else:
            known_packages = _owner_map_tokens(owner_map_path, PACKAGE_RE)
            known_gates = _owner_map_tokens(owner_map_path, GATE_RE)
            for package_id in sorted(package_rows - known_packages):
                errors.append(f"PACKAGE_NOT_IN_OWNER_MAP:{package_id}")
            for gate_id in sorted(gate_rows - known_gates):
                errors.append(f"GATE_NOT_IN_OWNER_MAP:{gate_id}")
    if gates_path is None:
        errors.append("MISSING_GATES_EVIDENCE_ROOT")
    elif not gates_path.exists():
        errors.append(f"MISSING_GATES_EVIDENCE_ROOT:{gates_path.as_posix()}")
    else:
        # Registry rows must name a gate artifact; evidence is checked without
        # importing a gate implementation.  Any absent gate is a blocker/failure.
        for gate_id in sorted(gate_rows):
            candidates = (gates_path / gate_id.lower(), gates_path / gate_id, gates_path / f"{gate_id.lower()}.json", gates_path / f"{gate_id}.json")
            if not any(candidate.exists() for candidate in candidates):
                errors.append(f"GATE_EVIDENCE_MISSING:{gate_id}")
    if root_plan_path is None:
        errors.append("MISSING_ROOT_PLAN_PATH")
    else:
        errors.extend(_navigation_pointer(root_plan_path, documents))
    if manifest_path is not None:
        if not manifest_path.exists():
            errors.append(f"MISSING_DEPENDENCY_MANIFEST:{manifest_path.as_posix()}")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                manifest = None
                errors.append(f"INVALID_DEPENDENCY_MANIFEST:{exc}")
            if isinstance(manifest, Mapping):
                node_ids = {str(node.get("id", node.get("node_id"))) for node in manifest.get("nodes", []) if isinstance(node, Mapping)}
                for package_id in sorted(package_rows - node_ids):
                    errors.append(f"PACKAGE_NOT_IN_DEPENDENCY_MANIFEST:{package_id}")
                for gate_id in sorted(gate_rows - node_ids):
                    errors.append(f"GATE_NOT_IN_DEPENDENCY_MANIFEST:{gate_id}")
    status = "PASS" if not errors else "FAIL"
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "registry_path": registry_path.as_posix(),
        "documents_path": docs_path.as_posix(),
        "requirements": [{"id": requirement_id, "occurrences": ids.count(requirement_id), "covered": requirement_id in registered_ids} for requirement_id in sorted(expected_ids | registered_ids)],
        "documents": sorted(documents),
        "packages": sorted(package_rows),
        "gates": sorted(gate_rows),
        "errors": sorted(set(errors)),
    }
    result = _finish(result)
    if output_path is not None:
        _write_json(output_path, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("CassiFI/13-requirements-registry.md"))
    parser.add_argument("--docs", type=Path, default=Path("CassiFI"))
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--owner-map", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root-plan", type=Path, default=Path("CASSI-QI-FLOW-INTELLIGENCE-IMPLEMENTATION-PLAN.md"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = verify_requirements_registry(registry_path=args.registry, docs_path=args.docs, gates_path=args.gates, owner_map_path=args.owner_map, manifest_path=args.manifest, root_plan_path=args.root_plan, output_path=args.output)
    print(json.dumps({"status": result["status"], "errors": result["errors"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
