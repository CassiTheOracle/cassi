"""Freeze and independently assess a Cassi-QI engineering candidate.

The driver deliberately uses only the Python standard library.  It never imports
field/runtime code: release objects are hashes over bytes and small JSON records,
so an incomplete tree produces a typed BLOCKED result rather than a best-effort
or synthetic PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_CANDIDATE_RESULT = "cassi.qi-flow-candidate-result.v1"
SCHEMA_ENGINEERING_BOARD = "cassi.qi-flow-engineering-board.v1"
SCHEMA_RELEASE_BOARD = "cassi.qi-flow-release-board.v1"
SCHEMA_RELEASE_RESULT = "cassi.qi-flow-release-result.v1"
SCHEMA_README_VERIFICATION = "cassi.qi-flow-readme-verification.v1"
SCHEMA_EVIDENCE_INDEX = "cassi.qi-flow-post-cutover-evidence-index.v1"
SCHEMA_FAILURE = "cassi.qi-flow-failure.v1"

SEMANTIC_PARENT_NAMES = (
    "state_contract_sha256",
    "boundary_action_sha256",
    "world_protocol_sha256",
    "session_storage_sha256",
    "provider_api_sha256",
    "backend_capacity_sha256",
    "security_evidence_sha256",
)
REQUIRED_ENGINEERING_GATES = (
    "G0",
    "G1",
    "G2",
    "G3",
    "G3N",
    "G4",
    "G4R",
    "G5",
    "G5V",
    "G6",
    "G6T",
    "G6A",
    "G6B",
    "G6C",
    "G7",
    "G7P",
    "G8",
    "G9",
    "G9O",
    "G10",
    "G10E",
    "G10A",
    "G11",
    "G11D",
    "G12",
    "G12M",
    "G12L",
    "G12A",
    "G12E",
    "G13",
    "G13R",
    "G13C",
    "G13D",
    "G14A",
    "G14B",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReleaseError(ValueError):
    """Raised when an input cannot be interpreted as a release object."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the UTF-8 canonical JSON representation used by release hashes."""
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ReleaseError(f"value is not canonical JSON: {exc}") from exc
    return text.encode("utf-8", "strict")


def canonical_hash(value: Any, domain: str) -> str:
    if not isinstance(domain, str) or not domain:
        raise ReleaseError("hash domain must be a non-empty string")
    domain_bytes = domain.encode("utf-8", "strict")
    payload_bytes = canonical_json_bytes(value)
    framed = (
        len(domain_bytes).to_bytes(8, "big", signed=False)
        + domain_bytes
        + len(payload_bytes).to_bytes(8, "big", signed=False)
        + payload_bytes
    )
    return hashlib.sha256(framed).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _missing_hash(label: str) -> str:
    # This digest is explicitly a missing-input marker.  It is never treated as
    # evidence of readiness; blockers retain the label in ``blockers``.
    return canonical_hash({"missing": label}, "cassi.qi-flow-missing-input.v1")


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"MISSING_INPUT:{path.as_posix()}:{exc}"
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"INVALID_JSON:{path.as_posix()}:{exc}"
    if not isinstance(value, dict):
        return None, f"INVALID_OBJECT:{path.as_posix()}"
    return value, None


def _write_json(path: Path, value: Mapping[str, Any]) -> bytes:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return raw


def _self_hash(value: Mapping[str, Any], schema: str) -> str:
    body = dict(value)
    body.pop("self_sha256", None)
    return canonical_hash(body, schema)


def _finish_hashed(value: Mapping[str, Any], schema: str) -> dict[str, Any]:
    result = dict(value)
    result["self_sha256"] = _self_hash(result, schema)
    return result


def _id_hash(value: Mapping[str, Any], id_field: str, schema: str) -> str:
    body = dict(value)
    body.pop(id_field, None)
    body.pop("self_sha256", None)
    return canonical_hash(body, schema)


def _normalise_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    return {
        "pass": "passed",
        "passed": "passed",
        "fail": "failed",
        "failed": "failed",
        "block": "blocked",
        "blocked": "blocked",
        "not_run": "blocked",
        "not-run": "blocked",
        "pending": "blocked",
    }.get(lowered)


def _manifest_gate_ids(manifest: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not manifest:
        return REQUIRED_ENGINEERING_GATES
    values: list[str] = []
    for node in manifest.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        node_id = node.get("id", node.get("node_id"))
        kind = str(node.get("kind", "")).lower()
        if isinstance(node_id, str) and (kind == "gate" or re.fullmatch(r"G[0-9]+[A-Z]*", node_id)):
            values.append(node_id)
    # A manifest with no gate rows is itself incomplete.  Keep the frozen
    # required set so every required row becomes an explicit blocker.
    if not values:
        return REQUIRED_ENGINEERING_GATES
    return tuple(dict.fromkeys(values))


def dependency_descendant_closure(
    manifest: Mapping[str, Any], roots: Iterable[str], *, include_roots: bool = True
) -> tuple[str, ...]:
    """Return the exact transitive descendant closure of ``roots``.

    Edges are interpreted as ``from -> to``.  The result is UTF-8 sorted and
    duplicate edges do not alter it.  Unknown roots and malformed edges are
    rejected instead of silently shrinking the closure.
    """
    nodes: set[str] = set()
    for row in manifest.get("nodes", []):
        if not isinstance(row, Mapping):
            raise ReleaseError("dependency manifest node is not an object")
        node_id = row.get("id", row.get("node_id"))
        if not isinstance(node_id, str) or not node_id:
            raise ReleaseError("dependency manifest node has no id")
        if node_id in nodes:
            raise ReleaseError(f"duplicate dependency node: {node_id}")
        nodes.add(node_id)
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in manifest.get("edges", []):
        if not isinstance(edge, Mapping):
            raise ReleaseError("dependency manifest edge is not an object")
        source = edge.get("from", edge.get("from_node_id"))
        target = edge.get("to", edge.get("to_node_id"))
        if not isinstance(source, str) or not isinstance(target, str):
            raise ReleaseError("dependency manifest edge has no endpoints")
        if source not in nodes or target not in nodes:
            raise ReleaseError(f"dependency edge references unknown node: {source}->{target}")
        adjacency[source].add(target)
    roots_tuple = tuple(dict.fromkeys(roots))
    unknown = sorted(set(roots_tuple) - nodes)
    if unknown:
        raise ReleaseError("unknown closure root(s): " + ", ".join(unknown))
    seen: set[str] = set(roots_tuple if include_roots else ())
    queue = list(roots_tuple)
    while queue:
        current = queue.pop(0)
        for child in sorted(adjacency[current]):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return tuple(sorted(seen))


def _identity_from_json(path: Path, label: str, blockers: list[str]) -> str:
    payload, error = _read_json(path)
    if error:
        blockers.append(error)
        return _missing_hash(label)
    assert payload is not None
    supplied = payload.get("self_sha256")
    if not _is_sha(supplied):
        blockers.append(f"MISSING_SELF_HASH:{path.as_posix()}")
        return sha256_bytes(path.read_bytes())
    body = dict(payload)
    body.pop("self_sha256", None)
    schema = payload.get("schema")
    if not isinstance(schema, str) or supplied != canonical_hash(body, schema):
        blockers.append(f"SELF_HASH_MISMATCH:{path.as_posix()}")
    return str(supplied)


def _semantic_identities(profile: Mapping[str, Any] | None, blockers: list[str]) -> list[dict[str, str]]:
    found: dict[str, str] = {}
    if profile:
        for row in profile.get("consumed_semantic_subhashes", []):
            if isinstance(row, Mapping) and isinstance(row.get("name"), str) and _is_sha(row.get("sha256")):
                found[str(row["name"])] = str(row["sha256"])
        for name in SEMANTIC_PARENT_NAMES:
            direct = profile.get(name)
            if _is_sha(direct):
                found[name] = str(direct)
    result: list[dict[str, str]] = []
    for name in SEMANTIC_PARENT_NAMES:
        if name not in found:
            blockers.append(f"MISSING_SEMANTIC_SUBHASH:{name}")
            digest = _missing_hash(name)
        else:
            digest = found[name]
        result.append({"name": name, "sha256": digest})
    return result


def _discover_gate(gate_id: str, root: Path) -> tuple[str, str | None, Path | None]:
    gate_root = root / "gates" / gate_id.lower()
    candidates = (
        gate_root / "status.json",
        gate_root / "verification.json",
        gate_root / "receipt.json",
        gate_root / "index.json",
    )
    for path in candidates:
        payload, error = _read_json(path)
        if error or payload is None:
            continue
        status = _normalise_status(payload.get("status"))
        if status is None:
            status = _normalise_status(payload.get("outcome"))
        if status is not None:
            return status, sha256_bytes(path.read_bytes()), path
    return "blocked", None, None


def _package_rows(manifest: Mapping[str, Any] | None, gate_outcomes: Sequence[Mapping[str, Any]], blockers: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packages: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    if manifest:
        for node in manifest.get("nodes", []):
            if not isinstance(node, Mapping):
                continue
            node_id = node.get("id", node.get("node_id"))
            kind = str(node.get("kind", "")).lower()
            if not isinstance(node_id, str) or not (kind in {"work_package", "package"} or re.fullmatch(r"W[0-9]+[A-Z]*", node_id)):
                continue
            section_hash = node.get("section_sha256")
            if not _is_sha(section_hash):
                blockers.append(f"MISSING_PACKAGE_SECTION_HASH:{node_id}")
                section_hash = _missing_hash(f"package:{node_id}")
            packages.append(
                {
                    "deliverable_schema": str(node.get("deliverable_schema", "cassi.qi-flow-gate-status.v1")),
                    "owner": str(node.get("owner", node.get("document", "unknown"))),
                    "package_id": node_id,
                    "source_section_sha256": section_hash,
                }
            )
        for edge in manifest.get("edges", []):
            if not isinstance(edge, Mapping):
                continue
            source = edge.get("from", edge.get("from_node_id"))
            target = edge.get("to", edge.get("to_node_id"))
            if isinstance(source, str) and isinstance(target, str) and re.fullmatch(r"W[0-9]+[A-Z]*", source) and re.fullmatch(r"W[0-9]+[A-Z]*", target):
                dependencies.append({"from_package_id": source, "reason": str(edge.get("reason", "manifest dependency")), "to_package_id": target})
    if not packages:
        blockers.append("MISSING_PACKAGE_NODES")
        packages = [
            {
                "deliverable_schema": "cassi.qi-flow-gate-status.v1",
                "owner": "W15A/W16A",
                "package_id": "W15A/W16A",
                "source_section_sha256": _missing_hash("packages"),
            }
        ]
    package_ids = {row["package_id"] for row in packages}
    results = [
        {"artifact_sha256": None, "failure_code": "REQUIRED_GATE_NOT_PASS", "package_id": package_id, "status": "blocked"}
        for package_id in sorted(package_ids)
    ]
    # A gate can only make a package passed when all required gates pass.  The
    # candidate path is intentionally conservative: no package is inferred PASS
    # from a partial gate list.
    if gate_outcomes and all(row.get("status") == "passed" for row in gate_outcomes):
        for row in results:
            row["status"] = "passed"
            row["failure_code"] = None
    return sorted(packages, key=lambda row: row["package_id"]), sorted(dependencies, key=lambda row: (row["from_package_id"], row["to_package_id"], row["reason"])), results


def _write_evidence_index(root: Path, records: Sequence[Mapping[str, Any]]) -> tuple[Path, str]:
    objects: list[dict[str, str]] = []
    for row in records:
        path = row.get("path", row.get("artifact_key"))
        sha256 = row.get("sha256")
        schema = row.get("schema")
        if not isinstance(path, str) or not _is_sha(sha256) or not isinstance(schema, str):
            raise ReleaseError("evidence index records require path/artifact_key, schema, and sha256")
        objects.append({"path": path, "schema": schema, "sha256": sha256})
    body = {"schema": SCHEMA_EVIDENCE_INDEX, "objects": sorted(objects, key=lambda row: row["path"])}
    body = _finish_hashed(body, SCHEMA_EVIDENCE_INDEX)
    path = root / "candidate" / "post-cutover-evidence-index.json"
    raw = _write_json(path, body)
    return path, sha256_bytes(raw)


def _artifact_records(root: Path, extra: Sequence[Path]) -> list[dict[str, str]]:
    paths: set[Path] = set()
    for path in extra:
        if path.is_file():
            paths.add(path)
    for path in (root / "gates").rglob("*") if (root / "gates").exists() else ():
        if path.is_file() and path.name not in {"stdout.bin", "stderr.bin"}:
            paths.add(path)
    records: list[dict[str, str]] = []
    for path in sorted(paths):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.as_posix()
        records.append({"artifact_key": relative, "schema": SCHEMA_FAILURE if "failure" in path.name or "blocked" in path.name else "cassi.qi-flow-artifact.v1", "sha256": sha256_bytes(path.read_bytes())})
    if not records:
        # The caller writes a blocker before this function in normal operation.
        records.append({"artifact_key": "candidate/missing-input.marker", "schema": SCHEMA_FAILURE, "sha256": _missing_hash("candidate-artifacts")})
    return sorted(records, key=lambda row: row["artifact_key"])


def build_candidate_result(
    *,
    candidate_id: str,
    run_index_sha256: str,
    profile_sha256: str,
    contract_root_sha256: str,
    semantic_subhashes: Sequence[Mapping[str, str]],
    gate_outcomes: Sequence[Mapping[str, Any]],
    artifacts: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "artifacts": [dict(row) for row in sorted(artifacts, key=lambda row: str(row["artifact_key"]))],
        "candidate_id": candidate_id,
        "candidate_result_id": "",
        "consumed_semantic_subhashes": [dict(row) for row in semantic_subhashes],
        "contract_root_sha256": contract_root_sha256,
        "final_release_ready": bool(gate_outcomes) and all(row.get("status") == "passed" for row in gate_outcomes),
        "gate_outcomes": [dict(row) for row in sorted(gate_outcomes, key=lambda row: str(row["gate_id"]))],
        "profile_sha256": profile_sha256,
        "run_index_sha256": run_index_sha256,
        "schema": SCHEMA_CANDIDATE_RESULT,
    }
    result["candidate_result_id"] = _id_hash(result, "candidate_result_id", SCHEMA_CANDIDATE_RESULT)
    return _finish_hashed(result, SCHEMA_CANDIDATE_RESULT)


def build_engineering_board(
    *,
    profile_sha256: str,
    contract_root_sha256: str,
    semantic_subhashes: Sequence[Mapping[str, str]],
    packages: Sequence[Mapping[str, Any]],
    dependencies: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "consumed_semantic_subhashes": [dict(row) for row in semantic_subhashes],
        "contract_root_sha256": contract_root_sha256,
        "dependencies": [dict(row) for row in dependencies],
        "engineering_board_id": "",
        "final_release_ready": bool(results) and all(row.get("status") == "passed" for row in results),
        "packages": [dict(row) for row in packages],
        "profile_sha256": profile_sha256,
        "results": [dict(row) for row in results],
        "schema": SCHEMA_ENGINEERING_BOARD,
    }
    body["engineering_board_id"] = _id_hash(body, "engineering_board_id", SCHEMA_ENGINEERING_BOARD)
    return _finish_hashed(body, SCHEMA_ENGINEERING_BOARD)


def _resolve_root(root: Path, run_id: str | None) -> Path:
    if run_id and root.name != run_id:
        return root / run_id
    return root


def run_candidate(
    *,
    root: Path,
    run_id: str | None = None,
    manifest_path: Path | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    run_root = _resolve_root(root, run_id)
    blockers: list[str] = []
    manifest_path = manifest_path or (run_root / "run-spec" / "dependency-manifest.json")
    profile_path = profile_path or (run_root / "run-spec" / "profile.json")
    manifest, manifest_error = _read_json(manifest_path)
    if manifest_error:
        blockers.append(manifest_error)
    profile, profile_error = _read_json(profile_path)
    if profile_error:
        blockers.append(profile_error)
    if manifest is not None:
        supplied = manifest.get("self_sha256")
        schema = manifest.get("schema")
        if not _is_sha(supplied) or not isinstance(schema, str):
            blockers.append("DEPENDENCY_MANIFEST_MISSING_IDENTITY")
        else:
            body = dict(manifest)
            body.pop("self_sha256", None)
            if canonical_hash(body, schema) != supplied:
                blockers.append("DEPENDENCY_MANIFEST_SELF_HASH_MISMATCH")
    profile_sha256 = _identity_from_json(profile_path, "profile", blockers)
    manifest_sha256 = _identity_from_json(manifest_path, "dependency-manifest", blockers)
    contract_root_sha256 = _missing_hash("contract-root")
    if profile:
        candidate_root = profile.get("contract_root_sha256")
        if _is_sha(candidate_root):
            contract_root_sha256 = str(candidate_root)
    if contract_root_sha256 == _missing_hash("contract-root"):
        for candidate in (run_root / "run-spec" / "contract-root.json", run_root / "run-spec" / "contract-root" / "root.json"):
            if candidate.exists():
                contract_root_sha256 = _identity_from_json(candidate, "contract-root", blockers)
                break
        else:
            blockers.append("MISSING_CONTRACT_ROOT")
    semantic_subhashes = _semantic_identities(profile, blockers)
    gate_ids = _manifest_gate_ids(manifest)
    gate_outcomes: list[dict[str, Any]] = []
    gate_artifacts: list[Path] = []
    for gate_id in gate_ids:
        status, artifact_sha, artifact_path = _discover_gate(gate_id, run_root)
        failure_code = None if status == "passed" else ("GATE_NOT_PASS" if artifact_path else "MISSING_REQUIRED_GATE_ARTIFACT")
        if status != "passed":
            blockers.append(f"{gate_id}:{failure_code}")
        gate_outcomes.append({"artifact_sha256": artifact_sha, "failure_code": failure_code, "gate_id": gate_id, "status": status})
        if artifact_path:
            gate_artifacts.append(artifact_path)
    blocker_payload = _finish_hashed({"schema": SCHEMA_FAILURE, "code": "RELEASE_BLOCKED", "blockers": sorted(set(blockers))}, SCHEMA_FAILURE)
    blocker_path = run_root / "candidate" / "blocked-dependencies.json"
    _write_json(blocker_path, blocker_payload)
    records = _artifact_records(run_root, [blocker_path, *gate_artifacts])
    evidence_path, evidence_sha = _write_evidence_index(run_root, records)
    candidate_id = canonical_hash({"manifest_sha256": manifest_sha256, "profile_sha256": profile_sha256, "contract_root_sha256": contract_root_sha256, "run_id": run_id or run_root.name}, "cassi.qi-flow-candidate.v1")
    result = build_candidate_result(
        candidate_id=candidate_id,
        run_index_sha256=evidence_sha,
        profile_sha256=profile_sha256,
        contract_root_sha256=contract_root_sha256,
        semantic_subhashes=semantic_subhashes,
        gate_outcomes=gate_outcomes,
        artifacts=records,
    )
    candidate_result_path = run_root / "candidate" / "candidate-result.json"
    _write_json(candidate_result_path, result)
    packages, dependencies, package_results = _package_rows(manifest, gate_outcomes, blockers)
    board = build_engineering_board(
        profile_sha256=profile_sha256,
        contract_root_sha256=contract_root_sha256,
        semantic_subhashes=semantic_subhashes,
        packages=packages,
        dependencies=dependencies,
        results=package_results,
    )
    board["final_release_ready"] = bool(result["final_release_ready"]) and not blockers
    board["self_sha256"] = _self_hash(board, SCHEMA_ENGINEERING_BOARD)
    board_path = run_root / "candidate" / "engineering-board.json"
    _write_json(board_path, board)
    status = "PASS" if bool(board["final_release_ready"]) else ("BLOCKED" if blockers or any(row["status"] == "blocked" for row in gate_outcomes) else "FAIL")
    return {"status": status, "engineering_ready": bool(board["final_release_ready"]), "root": run_root, "blockers": sorted(set(blockers)), "board": board, "candidate_result": result, "board_path": board_path, "candidate_result_path": candidate_result_path}


def _readme_receipt(*, run_root: Path, readme_path: Path, profile_sha256: str, contract_root_sha256: str, semantic_subhashes: Sequence[Mapping[str, str]], supporting_sha: str, blockers: Sequence[str]) -> dict[str, Any]:
    try:
        readme_sha = sha256_bytes(readme_path.read_bytes())
    except OSError:
        readme_sha = _missing_hash(readme_path.as_posix())
    passed = not blockers and not readme_sha == _missing_hash(readme_path.as_posix())
    example_hash = readme_sha if passed else _missing_hash("README-observed-output")
    body: dict[str, Any] = {
        "claims": [{"claim_id": "release-documentation", "supporting_artifact_sha256s": [supporting_sha], "text_sha256": readme_sha}],
        "consumed_semantic_subhashes": [dict(row) for row in semantic_subhashes if row["name"] in {"provider_api_sha256", "security_evidence_sha256"}],
        "contract_root_sha256": contract_root_sha256,
        "examples": [{"command_inputs_sha256": supporting_sha, "example_id": "release-documentation", "expected_output_sha256": example_hash, "observed_output_sha256": example_hash, "status": "passed" if passed else "failed"}],
        "outcome": "passed" if passed else "failed",
        "profile_sha256": profile_sha256,
        "readme_sha256": readme_sha,
        "readme_verification_id": "",
        "schema": SCHEMA_README_VERIFICATION,
    }
    body["readme_verification_id"] = _id_hash(body, "readme_verification_id", SCHEMA_README_VERIFICATION)
    return _finish_hashed(body, SCHEMA_README_VERIFICATION)

def _release_board(*, candidate: Mapping[str, Any], board: Mapping[str, Any], readme: Mapping[str, Any], verification_sha: str, final: bool) -> dict[str, Any]:
    requirements = [
        {"artifact_schema": str(item.get("schema", SCHEMA_FAILURE)), "artifact_sha256": str(item.get("sha256", _missing_hash("requirement-artifact"))), "gate_id": str(item.get("gate_id", "G15A")), "required_status": "passed"}
        for item in candidate.get("gate_outcomes", [])
    ]
    if not requirements:
        requirements = [{"artifact_schema": SCHEMA_FAILURE, "artifact_sha256": _missing_hash("requirements"), "gate_id": "G15A", "required_status": "passed"}]
    body: dict[str, Any] = {
        "candidate_result_sha256": sha256_bytes(canonical_json_bytes(candidate) + b"\n"),
        "consumed_semantic_subhashes": [dict(row) for row in board.get("consumed_semantic_subhashes", [])],
        "contract_root_sha256": str(board.get("contract_root_sha256", _missing_hash("contract-root"))),
        "final_release_ready": bool(final),
        "independent_verification_sha256": verification_sha,
        "profile_sha256": str(board.get("profile_sha256", _missing_hash("profile"))),
        "readme_verification_sha256": str(readme.get("self_sha256", _missing_hash("readme-verification"))),
        "release_board_id": "",
        "requirements": requirements,
        "schema": SCHEMA_RELEASE_BOARD,
    }
    body["release_board_id"] = _id_hash(body, "release_board_id", SCHEMA_RELEASE_BOARD)
    return _finish_hashed(body, SCHEMA_RELEASE_BOARD)


def _release_result(*, candidate: Mapping[str, Any], release_board: Mapping[str, Any], artifact_sha: str, final: bool, blockers: Sequence[str]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "candidate_result_sha256": sha256_bytes(canonical_json_bytes(candidate) + b"\n"),
        "consumed_semantic_subhashes": [dict(row) for row in release_board.get("consumed_semantic_subhashes", [])],
        "contract_root_sha256": str(release_board.get("contract_root_sha256", _missing_hash("contract-root"))),
        "rejection_code": "" if final else ("G15B_BLOCKED" if blockers else "G15B_FAILED"),
        "release_artifact_sha256s": [artifact_sha],
        "release_board_sha256": sha256_bytes(canonical_json_bytes(release_board) + b"\n"),
        "release_result_id": "",
        "release_tag": "cassi-qi-release" if final else "cassi-qi-release-rejected",
        "schema": SCHEMA_RELEASE_RESULT,
        "status": "released" if final else "rejected",
    }
    body["release_result_id"] = _id_hash(body, "release_result_id", SCHEMA_RELEASE_RESULT)
    return _finish_hashed(body, SCHEMA_RELEASE_RESULT)


def run_final(*, root: Path, run_id: str | None = None, manifest_path: Path | None = None, profile_path: Path | None = None, registry_path: Path | None = None, docs_path: Path | None = None, gates_path: Path | None = None, owner_map_path: Path | None = None) -> dict[str, Any]:
    run_root = _resolve_root(root, run_id)
    effective_registry = registry_path or Path("CassiFI/13-requirements-registry.md")
    effective_docs = docs_path or Path("CassiFI")
    effective_gates = gates_path or (run_root / "gates")
    effective_owner_map = owner_map_path or effective_docs
    effective_manifest = manifest_path or (run_root / "run-spec" / "dependency-manifest.json")
    command_manifest = run_root / "run-spec" / "command-inputs.json"
    if not command_manifest.exists():
        command_manifest = run_root / "run-spec" / "commands.json"
    try:
        from run_cassi_qi_validation import run_validation
        validation_result = run_validation(root=run_root, gates=REQUIRED_ENGINEERING_GATES, commands_path=command_manifest if command_manifest.exists() else None, mode="release-candidate")
    except (ImportError, OSError, ValueError) as exc:
        validation_result = {"status": "BLOCKED", "blockers": [f"VALIDATION_RUNNER_UNAVAILABLE:{exc}"], "failures": []}
    candidate = run_candidate(root=root, run_id=run_id, manifest_path=manifest_path, profile_path=profile_path)
    blockers = list(candidate["blockers"])
    if validation_result.get("status") != "PASS":
        blockers.extend("G15A_VALIDATION:" + str(item) for item in validation_result.get("blockers", []) + validation_result.get("failures", []))
    board = candidate["board"]
    if not candidate["engineering_ready"]:
        blockers.append("G15A_ENGINEERING_NOT_READY")
    root_plan = Path("CASSI-QI-FLOW-INTELLIGENCE-IMPLEMENTATION-PLAN.md")
    registry_verification_path = run_root / "gates" / "g15b-release" / "requirements-verification.json"
    try:
        from verify_cassi_qi_requirements_registry import verify_requirements_registry
        registry_result = verify_requirements_registry(
            registry_path=effective_registry,
            docs_path=effective_docs,
            gates_path=effective_gates,
            owner_map_path=effective_owner_map,
            manifest_path=effective_manifest,
            root_plan_path=root_plan,
            output_path=registry_verification_path,
        )
        if registry_result.get("status") != "PASS":
            blockers.extend("G15B_REQUIREMENTS:" + str(error) for error in registry_result.get("errors", []))
    except (ImportError, OSError, ValueError) as exc:
        registry_result = {"status": "BLOCKED", "errors": [f"REQUIREMENTS_VERIFIER_UNAVAILABLE:{exc}"]}
        blockers.extend(registry_result["errors"])
    supporting = sha256_bytes(candidate["candidate_result_path"].read_bytes())
    readme_path = effective_docs.parent / "README.md" if effective_docs.is_dir() else effective_docs.parent / "README.md"
    readme_path_out = run_root / "gates" / "g15b-release" / "readme-verification.json"
    existing_readme, existing_error = _read_json(readme_path_out)
    readme_ok = False
    if existing_readme is not None and existing_error is None and validation_result.get("status") == "PASS" and registry_result.get("status") == "PASS":
        supplied = existing_readme.get("self_sha256")
        schema = existing_readme.get("schema")
        claims = existing_readme.get("claims")
        examples = existing_readme.get("examples")
        claim_support = {str(item) for claim in claims if isinstance(claim, Mapping) for item in claim.get("supporting_artifact_sha256s", [])} if isinstance(claims, list) else set()
        fresh_evidence_hashes: set[str] = set()
        fresh_command_hashes: set[str] = set()
        for gate_id in REQUIRED_ENGINEERING_GATES:
            gate_dir = run_root / "gates" / gate_id.lower()
            for evidence_path in (gate_dir / "raw" / "stdout.bin", gate_dir / "raw" / "stderr.bin", gate_dir / "status.json"):
                if evidence_path.exists():
                    fresh_evidence_hashes.add(sha256_bytes(evidence_path.read_bytes()))
            command_receipt = gate_dir / "command.json"
            if command_receipt.exists():
                fresh_command_hashes.add(sha256_bytes(command_receipt.read_bytes()))
        examples_ok = isinstance(examples, list) and bool(examples) and all(isinstance(example, Mapping) and example.get("status") == "passed" and _is_sha(example.get("command_inputs_sha256")) and _is_sha(example.get("expected_output_sha256")) and example.get("expected_output_sha256") == example.get("observed_output_sha256") and example.get("observed_output_sha256") in fresh_evidence_hashes and example.get("command_inputs_sha256") in fresh_command_hashes for example in examples)
        try:
            current_readme_sha = sha256_bytes(readme_path.read_bytes())
        except OSError:
            current_readme_sha = ""
        readme_ok = (
            _is_sha(supplied)
            and isinstance(schema, str)
            and canonical_hash({key: value for key, value in existing_readme.items() if key != "self_sha256"}, schema) == supplied
            and existing_readme.get("outcome") == "passed"
            and existing_readme.get("profile_sha256") == board.get("profile_sha256")
            and existing_readme.get("contract_root_sha256") == board.get("contract_root_sha256")
            and existing_readme.get("readme_sha256") == current_readme_sha
            and supporting in claim_support
            and examples_ok
        )
    if readme_ok:
        readme = existing_readme
    else:
        blockers.append("G15B_README_COMMAND_RECEIPTS_MISSING" if existing_error else "G15B_README_COMMAND_RECEIPT_FAILED")
        readme = _readme_receipt(run_root=run_root, readme_path=readme_path, profile_sha256=str(board["profile_sha256"]), contract_root_sha256=str(board["contract_root_sha256"]), semantic_subhashes=board["consumed_semantic_subhashes"], supporting_sha=supporting, blockers=blockers)
        _write_json(readme_path_out, readme)
    verification_payload = {"schema": SCHEMA_FAILURE, "status": "blocked" if blockers else "passed", "blockers": sorted(set(blockers)), "requirements_verification_sha256": str(registry_result.get("self_sha256", _missing_hash("requirements-verification")))}
    verification_payload = _finish_hashed(verification_payload, SCHEMA_FAILURE)
    verification_path = run_root / "gates" / "g15b-release" / "independent-verification.json"
    verification_raw = _write_json(verification_path, verification_payload)
    verification_sha = sha256_bytes(verification_raw)
    release_board = _release_board(candidate=candidate["candidate_result"], board=board, readme=readme, verification_sha=verification_sha, final=not blockers)
    provisional_board_path = run_root / "provisional-release-board.json"
    _write_json(provisional_board_path, release_board)
    rejection_payload = _finish_hashed({"schema": SCHEMA_FAILURE, "status": "blocked" if blockers else "passed", "blockers": sorted(set(blockers))}, SCHEMA_FAILURE)
    rejection_path = run_root / "provisional-release-result.json"
    rejection_raw = _write_json(rejection_path, rejection_payload)
    release_result = _release_result(candidate=candidate["candidate_result"], release_board=release_board, artifact_sha=sha256_bytes(rejection_raw), final=not blockers, blockers=blockers)
    release_board_path = run_root / "release-board.json"
    release_result_path = run_root / "release-result.json"
    _write_json(release_board_path, release_board)
    _write_json(release_result_path, release_result)
    status = "PASS" if not blockers else "BLOCKED"
    return {"status": status, "final_release_ready": not blockers, "root": run_root, "blockers": sorted(set(blockers)), "release_board": release_board, "release_result": release_result, "release_board_path": release_board_path, "release_result_path": release_result_path, "requirements_verification": registry_result}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("candidate", "final"), default="candidate")
    parser.add_argument("--run-id")
    parser.add_argument("--root", type=Path, default=Path("_diag/cassi-qi-flow"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--docs", type=Path)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--owner-map", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.stage == "candidate":
            result = run_candidate(root=args.root, run_id=args.run_id, manifest_path=args.manifest, profile_path=args.profile)
            print(json.dumps({"status": result["status"], "engineering_ready": result["engineering_ready"], "blockers": result["blockers"]}, sort_keys=True))
        else:
            result = run_final(root=args.root, run_id=args.run_id, manifest_path=args.manifest, profile_path=args.profile, registry_path=args.registry, docs_path=args.docs, gates_path=args.gates, owner_map_path=args.owner_map)
            print(json.dumps({"status": result["status"], "final_release_ready": result["final_release_ready"], "blockers": result["blockers"]}, sort_keys=True))
    except (OSError, ReleaseError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    if result["status"] == "PASS":
        return 0
    return 2 if result["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
