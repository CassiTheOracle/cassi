from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

MAX_JSON_BYTES = 16 * 1024 * 1024
HISTORICAL_SCHEMA = "cassi.qi-flow-historical-v2-manifest.v1"
SOURCE_INDEX_SCHEMA = "cassi.qi-flow-historical-v2-source-index.v2"
CHECKPOINT_INDEX_SCHEMA = "cassi.qi-flow-historical-v2-checkpoint-index.v1"
DEPENDENCY_SCHEMA = "cassi.qi-flow-dependency-manifest.v1"
RUN_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
NORMATIVE_DOCUMENTS = [
    "CassiFI/README.md",
    *[f"CassiFI/{number:02d}-{name}.md" for number, name in [
        (0, "foundations"), (1, "field-physics"), (2, "retention-capacity-and-cognition"),
        (3, "architecture-profiles-and-schemas"), (4, "execution-contract"),
        (5, "boundaries-body-and-action"), (6, "memory-and-learning"),
        (7, "world-loop-and-transactions"), (8, "language-and-serving"),
        (9, "backends-receipts-and-verification"), (10, "work-packages"),
        (11, "validation-gates"), (12, "decisions-deployment-and-completion"),
        (13, "requirements-registry"),
    ]],
]
EXPECTED_PACKAGES = {
    "W0", "W1", "W2", "W3", "W3N", "W4", "W4R", "W5", "W5V", "W6", "W6T", "W6A", "W6B", "W7", "W7P",
    "W8", "W9", "W9O", "W10", "W10R", "W10E", "W10A", "W11", "W11D", "W12M", "W12L", "W12A", "W12E",
    "W13R", "W13C", "W14A", "W14B", "W15A", "W15B", "W16A", "W16B",
}
EXPECTED_GATES = {
    "G0", "G1", "G2", "G3", "G3N", "G4", "G4R", "G5", "G5V", "G6", "G6T", "G6A", "G6B", "G6C", "G7", "G7P",
    "G8", "G9", "G9O", "G10", "G10A", "G10E", "G11", "G11D", "G12M", "G12L", "G12A", "G12E", "G13R", "G13C",
    "G13D", "G14A", "G14B", "G15A", "G15B",
}
STATIC_RUN_SPEC = {
    "manifest.json", "profile.json", "semantic-subhashes.json", "profile-projections.json", "schema-registry.json",
    "source-identity.json", "raw-retention-policy.json", "capability-matrix.json", "toolchain.json", "command-inputs.json", "static-fixture-index.json",
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise VerificationError(f"cannot canonicalize value: {error}") from error


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reject_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON is forbidden: {value}")


def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    require(path.is_file(), f"missing file: {path}")
    body = path.read_bytes()
    require(len(body) <= MAX_JSON_BYTES, f"JSON byte limit exceeded: {path}")
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, VerificationError) as error:
        raise VerificationError(f"malformed JSON {path}: {error}") from error


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def relative(path: Path, root: Path) -> str:
    require(inside(path, root), f"path escapes root: {path}")
    return path.resolve().relative_to(root.resolve()).as_posix()


def check_self_hash(value: dict[str, Any], context: str) -> None:
    clone = dict(value)
    self_hash = clone.pop("self_sha256", None)
    require(isinstance(self_hash, str) and digest(canonical(clone)) == self_hash, f"self hash mismatch: {context}")


def verify_historical(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = load(root / "manifest.json")
    require(isinstance(manifest, dict), "historical manifest must be object")
    check_self_hash(manifest, "historical manifest")
    require(manifest.get("schema") == HISTORICAL_SCHEMA, "wrong historical manifest schema")
    require(manifest.get("source_index") == "source-index.json" and manifest.get("checkpoint_index") == "checkpoint-index.json", "historical index names are not canonical")
    all_indexed: dict[str, set[str]] = {}
    for name, expected_schema, hash_key, prefix in [
        ("source-index.json", SOURCE_INDEX_SCHEMA, "source_index_sha256", "source"),
        ("checkpoint-index.json", CHECKPOINT_INDEX_SCHEMA, "checkpoint_index_sha256", "checkpoints"),
    ]:
        body = (root / name).read_bytes()
        require(digest(body) == manifest.get(hash_key), f"manifest digest mismatch: {name}")
        index = load(root / name)
        require(isinstance(index, dict) and index.get("schema") == expected_schema, f"bad index schema: {name}")
        entries = index.get("entries")
        require(isinstance(entries, list) and index.get("entry_count") == len(entries), f"entry count mismatch: {name}")
        require(index.get("byte_total") == sum(item.get("byte_count", -1) for item in entries if isinstance(item, dict)), f"byte total mismatch: {name}")
        original_paths: set[str] = set()
        historical_paths: set[str] = set()
        for entry in entries:
            require(isinstance(entry, dict), f"malformed entry: {name}")
            original = entry.get("original_path")
            historical = entry.get("historical_path")
            require(isinstance(original, str) and isinstance(historical, str), f"missing path: {name}")
            expected = f"{prefix}/{original}" if prefix == "source" else f"checkpoints/{entry.get('sha256')}.bin"
            require(historical == expected, f"noncanonical indexed path: {historical}")
            require(original not in original_paths and historical not in historical_paths, f"duplicate index entry: {name}")
            original_paths.add(original); historical_paths.add(historical)
            target = (root / historical).resolve()
            require(inside(target, root) and target.is_file(), f"missing indexed payload: {historical}")
            body = target.read_bytes()
            require(len(body) == entry.get("byte_count") and digest(body) == entry.get("sha256"), f"payload mismatch: {historical}")
        all_indexed[prefix] = historical_paths
    source_root = root / "source"
    actual_sources = {relative(path, source_root) for path in source_root.rglob("*") if path.is_file()}
    expected_sources = {item.removeprefix("source/") for item in all_indexed["source"]}
    require(actual_sources == expected_sources, "source root has missing or unindexed files")
    require(not any(path.suffix == ".pyc" or "__pycache__" in path.parts for path in source_root.rglob("*")), "source bytecode residue is forbidden")
    actual_checkpoints = {relative(path, root) for path in (root / "checkpoints").rglob("*") if path.is_file()} if (root / "checkpoints").exists() else set()
    require(actual_checkpoints == all_indexed["checkpoints"], "checkpoint root has missing or unindexed files")
    source_index = load(root / "source-index.json")
    require(isinstance(source_index.get("import_audit"), list), "missing source import audit")
    require(isinstance(source_index.get("config_reference_audit"), list), "missing config-reference audit")
    require(isinstance(source_index.get("inventory_import_audit"), list), "missing full source import audit")
    require(isinstance(source_index.get("inventory_config_reference_audit"), list), "missing full config-reference audit")
    coverage = source_index.get("inventory_coverage")
    require(isinstance(coverage, dict), "missing inventory coverage")
    python_files = coverage.get("python_files")
    config_files = coverage.get("config_files")
    require(isinstance(python_files, list) and isinstance(config_files, list), "invalid inventory coverage paths")
    require(coverage.get("python_file_count") == len(python_files) and coverage.get("config_file_count") == len(config_files), "invalid inventory coverage counts")
    indexed_sources = {item.removeprefix("source/") for item in all_indexed["source"]}
    require(set(python_files) | set(config_files) == indexed_sources, "inventory coverage does not classify every archived source")
    require(manifest.get("source_count") == source_index["entry_count"], "manifest source count mismatch")
    checkpoint_index = load(root / "checkpoint-index.json")
    require(manifest.get("checkpoint_count") == checkpoint_index["entry_count"], "manifest checkpoint count mismatch")
    discovery = checkpoint_index.get("discovery")
    require(isinstance(discovery, dict) and discovery.get("schema") == "cassi.qi-flow-checkpoint-discovery.v1", "missing checkpoint-discovery receipt")
    require(discovery.get("entries") == checkpoint_index["entries"], "checkpoint discovery/index mismatch")
    require(isinstance(discovery.get("empty_set_proof"), dict), "missing empty checkpoint proof")
    require(digest((root / "cassi-qi-language.json").read_bytes()) == manifest.get("config_sha256"), "config digest mismatch")
    require(digest((root / "run_cassi_qi_behavior_demo.py").read_bytes()) == manifest.get("wrapper_sha256"), "wrapper digest mismatch")
    require(isinstance(manifest.get("bootstrap_source_sha256"), str) and isinstance(manifest.get("independent_verifier_source_sha256"), str), "missing source provenance")
    return {"manifest_sha256": digest((root / "manifest.json").read_bytes()), "source_count": source_index["entry_count"], "checkpoint_count": checkpoint_index["entry_count"]}


def identifiers(text: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\b{prefix}\d+[A-Z]?\b", text))


def artifact_tokens(text: str) -> set[str]:
    values = re.findall(r"`([^`]+)`", text)
    artifacts = {
        value
        for value in values
        if value.startswith(("cassi.", "Qi", "run_", "test_", "verify_")) or value.endswith((".json", ".py", ".wprp"))
    }
    artifacts.update(re.findall(r"\bcassi\.qi-flow-[A-Za-z0-9_.-]+\b", text))
    return artifacts


def registry_rows(root: Path) -> list[dict[str, Any]]:
    registry = (root / "CassiFI/13-requirements-registry.md").read_bytes().decode("utf-8")
    rows: list[dict[str, Any]] = []
    for line in registry.splitlines():
        match = re.match(r"^\|\s*`(QI-[A-Z]+-\d+)`\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", line)
        if match:
            requirement, document, packages, gates, artifacts = match.groups()
            rows.append({
                "id": requirement,
                "owner_document": document,
                "packages": sorted(identifiers(packages, "W")),
                "gates": sorted(identifiers(gates, "G")),
                "artifacts": sorted(artifact_tokens(artifacts)),
                "row_sha256": digest(line.encode("utf-8")),
            })
    require(rows, "no requirements rows")
    require(len({row["id"] for row in rows}) == len(rows), "duplicate requirement row")
    return rows


def sections(root: Path) -> tuple[set[str], set[str], dict[str, str], list[dict[str, str]]]:
    packages: set[str] = set(); gates: set[str] = set(); hashes: dict[str, str] = {}; documents = []
    for name in NORMATIVE_DOCUMENTS:
        file = root / name
        require(file.is_file(), f"missing normative document: {name}")
        body = file.read_bytes().decode("utf-8")
        documents.append({"path": name, "sha256": digest(file.read_bytes())})
        matches = list(re.finditer(r"^###\s+((?:W|G)\d+[A-Z]?)\s+(?:—|-)\s+(.+)$", body, re.MULTILINE))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            identifier = match.group(1)
            hashes[identifier] = digest(body[match.start():end].encode("utf-8"))
            (packages if identifier.startswith("W") else gates).add(identifier)
    return packages, gates, hashes, documents


def expected_content_addressed_run_id(root: Path, historical_root: Path) -> str:
    _, _, _, documents = sections(root)
    manifest = load(historical_root / "manifest.json")
    require(isinstance(manifest, dict), "historical manifest must be object")
    bootstrap = root / "run_cassi_qi_flow_manifest.py"
    verifier = Path(__file__).resolve()
    require(bootstrap.is_file(), "missing bootstrap source for run identity")
    payload = {
        "schema": "cassi.qi-flow-w0-development-input.v1",
        "normative_document_set": documents,
        "historical_manifest_sha256": digest((historical_root / "manifest.json").read_bytes()),
        "bootstrap_source_sha256": digest(bootstrap.read_bytes()),
        "independent_verifier_source_sha256": digest(verifier.read_bytes()),
        "entrypoint": manifest.get("entrypoint"),
        "config": manifest.get("config"),
        "wrapper_output_root": manifest.get("wrapper_output_root"),
    }
    return digest(canonical(payload))


def acyclic(nodes: set[str], edges: Iterable[tuple[str, str]]) -> bool:
    outgoing = {node: set() for node in nodes}; indegree = {node: 0 for node in nodes}
    for left, right in edges:
        if left in nodes and right in nodes and right not in outgoing[left]:
            outgoing[left].add(right); indegree[right] += 1
    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0)); count = 0
    while queue:
        node = queue.popleft(); count += 1
        for target in sorted(outgoing[node]):
            indegree[target] -= 1
            if indegree[target] == 0: queue.append(target)
    return count == len(nodes)


def independently_derived_graph(root: Path, historical_manifest_hash: str) -> dict[str, Any]:
    documents: list[tuple[str, str]] = []
    prose_nodes: list[dict[str, Any]] = []
    sections_with_body: list[dict[str, Any]] = []
    for relative_document in NORMATIVE_DOCUMENTS:
        path = root / relative_document
        require(path.is_file(), f"missing normative document: {relative_document}")
        body = path.read_bytes().decode("utf-8")
        documents.append((relative_document, body))
        prose_nodes.append({"id": relative_document, "kind": "prose", "sha256": digest(path.read_bytes())})
        matches = list(re.finditer(r"^###\s+((?:W|G)\d+[A-Z]?)\s+(?:—|-)\s+(.+)$", body, re.MULTILINE))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            identifier = match.group(1)
            sections_with_body.append({
                "id": identifier,
                "kind": "work_package" if identifier.startswith("W") else "gate",
                "document": relative_document,
                "title": match.group(2).strip(),
                "section_sha256": digest(body[match.start():end].encode("utf-8")),
                "body": body[match.start():end],
            })
    packages = [section for section in sections_with_body if section["kind"] == "work_package"]
    gates = [section for section in sections_with_body if section["kind"] == "gate"]
    require({section["id"] for section in packages} == EXPECTED_PACKAGES, "source plan does not have expected 36 work packages")
    require({section["id"] for section in gates} == EXPECTED_GATES, "source plan does not have expected 35 gates")
    nodes: dict[tuple[str, str], dict[str, Any]] = {("prose", node["id"]): node for node in prose_nodes}
    for section in packages + gates:
        nodes[(section["kind"], section["id"])] = {
            key: section[key] for key in ("id", "kind", "document", "title", "section_sha256")
        }
    edges: set[tuple[str, str, str]] = set()
    artifact_sources: dict[str, set[str]] = {}

    def add_artifact(owner: str, artifact: str, kind: str) -> None:
        artifact_sources.setdefault(artifact, set()).add(owner)
        edges.add((owner, artifact, kind))

    for section in packages:
        owner = section["id"]
        dependency_match = re.search(r"\*\*Dependencies:\*\*([^\n]+)", section["body"])
        if dependency_match:
            for dependency in identifiers(dependency_match.group(1), "W"):
                require(dependency in EXPECTED_PACKAGES, f"unknown work dependency: {dependency}")
                edges.add((dependency, owner, "depends-on"))
        for artifact in artifact_tokens(section["body"]):
            add_artifact(owner, artifact, "owns")
    for section in gates:
        gate = section["id"]
        package_match = re.search(r"\*\*Work packages:\*\*([^\n]+)", section["body"])
        if package_match:
            for package in identifiers(package_match.group(1), "W"):
                require(package in EXPECTED_PACKAGES, f"unknown gate package: {package}")
                edges.add((package, gate, "validated-by"))
        for artifact in artifact_tokens(section["body"]):
            add_artifact(gate, artifact, "requires")
    for _, text in documents:
        for left, right in re.findall(r"\b((?:W|G)\d+[A-Z]?)\s*(?:->|→)\s*((?:W|G)\d+[A-Z]?)\b", text):
            if left in EXPECTED_PACKAGES | EXPECTED_GATES and right in EXPECTED_PACKAGES | EXPECTED_GATES:
                edges.add((left, right, "declared-order"))
    rows = registry_rows(root)
    for row in rows:
        nodes[("requirement", row["id"])] = {
            "id": row["id"],
            "kind": "requirement",
            "owner_document": row["owner_document"],
            "row_sha256": row["row_sha256"],
        }
        require(row["owner_document"] in NORMATIVE_DOCUMENTS, f"registry owner document not indexed: {row['owner_document']}")
        edges.add((row["owner_document"], row["id"], "defines"))
        for package in row["packages"]:
            require(package in EXPECTED_PACKAGES, f"registry unknown package: {package}")
            edges.add((package, row["id"], "implements"))
        for gate in row["gates"]:
            require(gate in EXPECTED_GATES, f"registry unknown gate: {gate}")
            edges.add((row["id"], gate, "consumed-by"))
        for artifact in row["artifacts"]:
            add_artifact(row["id"], artifact, "requires")
    for artifact in sorted(artifact_sources):
        nodes[("artifact", artifact)] = {"id": artifact, "kind": "artifact"}
    known = {identifier for _, identifier in nodes}
    require(all(left in known and right in known for left, right, _ in edges), "independent graph has dangling edge")
    graph = {
        "schema": DEPENDENCY_SCHEMA,
        "historical_manifest_sha256": historical_manifest_hash,
        "normative_document_set": [{"path": path, "sha256": digest(text.encode("utf-8"))} for path, text in documents],
        "section_inventory": [
            {key: section[key] for key in ("id", "kind", "document", "title", "section_sha256")}
            for section in packages + gates
        ],
        "registry_rows": rows,
        "mermaid_views": [
            {"path": path, "ordinal": str(number), "sha256": digest(block.encode("utf-8"))}
            for path, text in documents
            for number, block in enumerate(re.findall(r"```mermaid\n(.*?)```", text, re.DOTALL), start=1)
        ],
        "nodes": sorted(nodes.values(), key=lambda item: (item["kind"], item["id"])),
        "edges": [{"from": left, "to": right, "kind": kind} for left, right, kind in sorted(edges)],
        "expected_cardinalities": {
            "documents": len(NORMATIVE_DOCUMENTS),
            "packages": len(EXPECTED_PACKAGES),
            "gates": len(EXPECTED_GATES),
            "requirements": len(rows),
        },
    }
    graph["self_sha256"] = digest(canonical(graph))
    return graph


def verify_graph(root: Path, graph: dict[str, Any], historical_hash: str) -> None:
    check_self_hash(graph, "dependency manifest")
    require(graph.get("schema") == DEPENDENCY_SCHEMA, "dependency schema mismatch")
    require(graph.get("historical_manifest_sha256") == historical_hash, "historical manifest parent mismatch")
    packages, gates, section_hashes, documents = sections(root)
    require(packages == EXPECTED_PACKAGES, "source plan does not have expected 36 work packages")
    require(gates == EXPECTED_GATES, "source plan does not have expected 35 gates")
    node_items = graph.get("nodes")
    edge_items = graph.get("edges")
    require(isinstance(node_items, list) and isinstance(edge_items, list), "graph node/edge payload invalid")
    node_keys = [(item.get("kind"), item.get("id")) for item in node_items if isinstance(item, dict)]
    require(len(node_keys) == len(node_items) == len(set(node_keys)), "graph node duplicate/malformed")
    node_by_key = {(item["kind"], item["id"]): item for item in node_items}
    require({item["id"] for item in node_items if item["kind"] == "work_package"} == EXPECTED_PACKAGES, "graph W coverage mismatch")
    require({item["id"] for item in node_items if item["kind"] == "gate"} == EXPECTED_GATES, "graph G coverage mismatch")
    require({item["id"] for item in node_items if item["kind"] == "prose"} == set(NORMATIVE_DOCUMENTS), "graph document coverage mismatch")
    for identifier, expected_hash in section_hashes.items():
        kind = "work_package" if identifier.startswith("W") else "gate"
        require(node_by_key[(kind, identifier)].get("section_sha256") == expected_hash, f"section hash mismatch: {identifier}")
    require(graph.get("normative_document_set") == documents, "normative document view hash mismatch")
    rows = registry_rows(root)
    expected_requirements = {row["id"] for row in rows}
    require({item["id"] for item in node_items if item["kind"] == "requirement"} == expected_requirements, "exact-once requirement coverage mismatch")
    known_ids = {item["id"] for item in node_items}
    edge_keys = []
    for edge in edge_items:
        require(isinstance(edge, dict) and edge.get("from") in known_ids and edge.get("to") in known_ids and isinstance(edge.get("kind"), str), "dangling/malformed graph edge")
        edge_keys.append((edge["from"], edge["to"], edge["kind"]))
    require(len(edge_keys) == len(set(edge_keys)), "duplicate graph edge")
    edge_set = set(edge_keys)
    require(acyclic(EXPECTED_PACKAGES, [(left, right) for left, right, kind in edge_set if kind == "depends-on"]), "cycle in work package dependencies")
    require(acyclic(EXPECTED_GATES, [(left, right) for left, right, _ in edge_set if left in EXPECTED_GATES and right in EXPECTED_GATES]), "cycle in gate dependencies")
    for row in rows:
        require((row["owner_document"], row["id"], "defines") in edge_set, f"requirement owner edge missing: {row['id']}")
        node = node_by_key[("requirement", row["id"])]
        require(node.get("row_sha256") == row["row_sha256"], f"registry row hash mismatch: {row['id']}")
        for package in row["packages"]:
            require((package, row["id"], "implements") in edge_set, f"requirement package edge missing: {row['id']}:{package}")
        for gate in row["gates"]:
            require((row["id"], gate, "consumed-by") in edge_set, f"requirement consumer edge missing: {row['id']}:{gate}")
    artifacts = {item["id"] for item in node_items if item["kind"] == "artifact"}
    for artifact in artifacts:
        require(any(target == artifact and kind in {"owns", "requires"} for _, target, kind in edge_set), f"orphan artifact: {artifact}")
    cardinalities = graph.get("expected_cardinalities")
    require(isinstance(cardinalities, dict) and cardinalities.get("documents") == 15 and cardinalities.get("packages") == 36 and cardinalities.get("gates") == 35 and cardinalities.get("requirements") == len(expected_requirements), "declared graph cardinality mismatch")
    require(graph == independently_derived_graph(root, historical_hash), "dependency manifest differs from the independently regenerated source graph")


def check_envelope(path: Path) -> dict[str, Any]:
    value = load(path)
    require(isinstance(value, dict), f"run-spec object must be object: {path}")
    check_self_hash(value, str(path))
    return value


def verify_development(root: Path, historical_root: Path, run_root: Path, *, sealed: bool) -> dict[str, Any]:
    historical_root = historical_root.resolve()
    historical = verify_historical(historical_root)
    expected_run_id = expected_content_addressed_run_id(root, historical_root)
    require(run_root.name == expected_run_id, "development root name is not its content-addressed run id")
    graph_path = run_root / "run-spec/dependency-manifest.json"
    graph = load(graph_path)
    require(isinstance(graph, dict), "graph must be object")
    verify_graph(root, graph, historical["manifest_sha256"])
    static_objects = {name: check_envelope(run_root / "run-spec" / name) for name in STATIC_RUN_SPEC}
    run_manifest = static_objects["manifest.json"]
    require(run_manifest.get("run_id") == expected_run_id, "run-spec manifest run id drift")
    require(run_manifest.get("historical_manifest_sha256") == historical["manifest_sha256"], "run-spec historical parent drift")
    require(run_manifest.get("dependency_manifest_sha256") == graph.get("self_sha256"), "run-spec graph parent drift")
    fixture = check_envelope(run_root / "run-spec/oracle-fixtures/contract-root-bootstrap.json")
    require(fixture.get("status") == "W0_COMPLETE", "bootstrap fixture is not complete")
    request = check_envelope(run_root / "gates/g00-engineering-manifest/verification-request.json")
    require(request.get("run_id") == expected_run_id, "G0 request run id drift")
    require(request.get("dependency_manifest_sha256") == graph.get("self_sha256"), "G0 request graph identity mismatch")
    if sealed:
        index = check_envelope(run_root / "index.json")
        require(index.get("schema") == RUN_INDEX_SCHEMA and index.get("status") == "PASS_W0_G0", "unsealed run index")
        require(index.get("run_id") == expected_run_id, "run index run id drift")
        objects = index.get("objects")
        require(isinstance(objects, list) and index.get("object_count") == len(objects), "run index count mismatch")
        seen = set()
        for item in objects:
            path = item.get("path")
            require(isinstance(path, str) and path not in seen, "duplicate/malformed run index entry")
            seen.add(path)
            target = (run_root / path).resolve()
            require(inside(target, run_root) and target.is_file(), f"run-index object missing: {path}")
            body = target.read_bytes()
            require(len(body) == item.get("byte_count") and digest(body) == item.get("sha256"), f"run-index object drift: {path}")
        actual = {relative(path, run_root) for path in run_root.rglob("*") if path.is_file() and path.name != "index.json"}
        require(actual == seen, "unindexed or missing development-run object")
        receipt = check_envelope(run_root / "gates/g00-engineering-manifest/verification.json")
        status = check_envelope(run_root / "gates/g00-engineering-manifest/status.json")
        require(receipt.get("status") == "PASS" and status.get("status") == "PASS", "independent G0 receipt/status not PASS")
    return {"run_id": expected_run_id, "historical_manifest_sha256": historical["manifest_sha256"], "dependency_manifest_sha256": graph["self_sha256"], "node_count": len(graph["nodes"]), "edge_count": len(graph["edges"])}


def atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as handle:
        handle.write(body); temporary = Path(handle.name)
    temporary.replace(path)


def write_receipt(run_root: Path, result: dict[str, Any]) -> None:
    verifier_hash = digest(Path(__file__).read_bytes())
    receipt = {"schema": "cassi.qi-flow-independent-g0-verification.v1", "status": "PASS", "independent_verifier_source_sha256": verifier_hash, **result}
    receipt["self_sha256"] = digest(canonical(receipt))
    status = {"schema": "cassi.qi-flow-gate-status.v1", "gate": "G0", "status": "PASS", "verification_receipt_sha256": digest(canonical(receipt)), "independent_verifier_source_sha256": verifier_hash, "historical_manifest_sha256": result["historical_manifest_sha256"], "dependency_manifest_sha256": result["dependency_manifest_sha256"]}
    status["self_sha256"] = digest(canonical(status))
    gate = run_root / "gates/g00-engineering-manifest"
    for name, value in (("verification.json", receipt), ("status.json", status)):
        path = gate / name
        body = canonical(value)
        if path.exists():
            require(path.read_bytes() == body, f"independent receipt drift: {path}")
        else:
            atomic_write(path, body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--historical-root", default="historical/qi-v2")
    parser.add_argument("--run-root")
    parser.add_argument("--preseal", action="store_true")
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    historical_root = (root / args.historical_root).resolve()
    if args.run_root is None:
        result = verify_historical(historical_root)
    else:
        run_root = Path(args.run_root).resolve()
        result = verify_development(root, historical_root, run_root, sealed=not args.preseal)
        if args.write_receipt:
            require(args.preseal, "independent receipt can be written only before sealing")
            write_receipt(run_root, result)
    print(json.dumps({"status": "PASS", **result}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except VerificationError as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}), file=sys.stderr)
        raise SystemExit(2)
