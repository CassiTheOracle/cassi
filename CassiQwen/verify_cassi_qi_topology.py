"""Independent verifier for the source-exact W4R retention-core artifact.

This module intentionally has no dependency on the W4R producer or law module.
It consumes only canonical JSON, raw little-endian states, and independently
verified parent artifacts, then reconstructs the weighted D/C topology law.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import struct
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w4r-retention-core-final"
GATE_DIR = "gates/g04r-retention-core"
INDEX_SCHEMA = "cassi.qi-flow-w4r-retention-core-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w4r-retention-core"
STATUS_SCHEMA = "cassi.qi-flow-w4r-retention-core-status.v1"
CANDIDATE_SCHEMA = "cassi.qi-flow-w4r-retention-core-candidate.v1"
RAW_SCHEMA = "cassi.qi-flow-w4r-retention-core-raw-state.v1"
RAW_DOMAIN = "cassi.qi-flow-w4r-retention-core-raw-state"
RECEIPT_DOMAIN = "cassi.qi-flow-w4r-retention-core-receipt"
CORE_RECEIPT_SCHEMA = "cassi.qi-flow-w4r-topology-receipt.v1"
CORE_RECEIPT_DOMAIN = "cassi.qi-flow-w4r-topology-receipt.v1"
STATE_DOMAIN = "cassi.qi-flow-w4r-topology-state.v1"
PROFILE_DOMAIN = "cassi.qi-flow-w4r-topology-profile.v1"
PROFILE_ROOT_DOMAIN = "cassi.qi-flow-w4r-topology-root.v1"
CODEBOOK_DOMAIN = "cassi.qi-flow-w4r-topology-codebook.v1"
BARRIER_DOMAIN = "cassi.qi-flow-w4r-topology-barrier.v1"
RESET_DOMAIN = "cassi.qi-flow.retention-reset-operator.v1"
EXPECTED_CONTROLS = {
    "uniform-zero-sector": "PASS",
    "valid-cycle-positive": "PASS",
    "valid-cycle-negative": "PASS",
    "vortex-antivortex-plaquette": "PASS",
    "phase-scrambled-equal-energy": "REJECT",
    "matched-energy-positive-current": "PASS",
    "matched-energy-negative-current": "PASS",
    "amplitude-floor-rejection": "REJECT",
    "branch-rejection": "REJECT",
    "integer-rejection": "REJECT",
    "torus-algebra-rejection": "REJECT",
    "unaccepted-sector-mutation": "REJECT",
    "fading-v1-U-topo-zero-comparator": "PASS",
}
CANONICAL_COMPONENT_ORDER = ["Y_re", "Y_im", "I_re", "I_im", "VY_re", "VY_im", "VI_re", "VI_im", "epsilon2_ema"]
REQUIRED_SOURCE_NAMES = {
    "cassi_qi_topology.py",
    "run_cassi_qi_topology.py",
    "cassi_qi_profile.py",
    "cassi_qi_geometry.py",
    "cassi_qi_field.py",
    "cassi_qi_numerical_certificate.py",
    "cassi_qi_carrier.py",
    "cassi_qi_transport.py",
}


class VerificationError(ValueError):
    """Raised for any unauthenticated or physically inconsistent artifact."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_number(value: str) -> Any:
    raise VerificationError(f"decimal JSON number forbidden: {value}")


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant forbidden: {value}")


def _f64(value: Any, name: str = "value") -> float:
    require(isinstance(value, str) and value.startswith("f64:") and len(value) == 20, f"{name} is not canonical f64")
    try:
        decoded = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    except (ValueError, struct.error) as exc:
        raise VerificationError(f"{name} has invalid f64 bits") from exc
    require(math.isfinite(decoded), f"{name} is non-finite")
    require(not (decoded == 0.0 and math.copysign(1.0, decoded) < 0.0), f"{name} is negative zero")
    return decoded


def _number(value: Any, name: str = "value") -> float:
    if isinstance(value, str) and value.startswith("f64:"):
        return _f64(value, name)
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} is not numeric")
    decoded = float(value)
    require(math.isfinite(decoded), f"{name} is non-finite")
    return decoded


def _validate(value: Any) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        require(-(2**53 - 1) <= value <= 2**53 - 1, "JSON integer outside exact range")
        return
    if isinstance(value, float):
        raise VerificationError("decimal JSON number forbidden")
    if isinstance(value, str):
        value.encode("utf-8", "strict")
        if value.startswith("f64:"):
            _f64(value)
        elif value.startswith("f32:"):
            raise VerificationError("f32 value is not admitted by W4R")
        return
    if isinstance(value, list):
        for item in value:
            _validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str), "canonical JSON key is not a string")
            key.encode("utf-8", "strict")
            _validate(item)
        return
    raise VerificationError(f"unsupported JSON value: {type(value).__name__}")


def _quote(value: str) -> str:
    pieces = ['"']
    for char in value:
        point = ord(char)
        if char == '"':
            pieces.append('\\"')
        elif char == "\\":
            pieces.append("\\\\")
        elif point <= 0x1F:
            pieces.append(f"\\u{point:04x}")
        else:
            pieces.append(char)
    pieces.append('"')
    return "".join(pieces)


def _canonical(value: Any) -> bytes:
    _validate(value)

    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int) and not isinstance(item, bool):
            return str(item)
        if isinstance(item, str):
            return _quote(item)
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict):
            ordered = sorted(item.items(), key=lambda pair: pair[0].encode("utf-8"))
            return "{" + ",".join(_quote(str(key)) + ":" + encode(child) for key, child in ordered) + "}"
        raise VerificationError(f"unsupported canonical value: {type(item).__name__}")

    return encode(value).encode("utf-8", "strict")


def _load(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_constant,
        )
    except VerificationError:
        raise
    except Exception as exc:
        raise VerificationError(f"invalid JSON object {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON object required: {path}")
    require(_canonical(value) == raw, f"non-canonical JSON bytes: {path}")
    return value


def _hash(value: Any, domain: str) -> str:
    body = _canonical(value)
    encoded = domain.encode("utf-8", "strict")
    return sha256(len(encoded).to_bytes(8, "big") + encoded + len(body).to_bytes(8, "big") + body).hexdigest()


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()
def _complex_hash(grid: Sequence[Sequence[complex]]) -> str:
    raw = b"".join(struct.pack("<dd", float(value.real), float(value.imag)) for row in grid for value in row)
    return _sha(raw)
def _raw_l2(left: bytes, right: bytes) -> float:
    require(len(left) == len(right) and len(left) % 8 == 0, "raw state length mismatch for displacement")
    values_left = struct.unpack("<" + "d" * (len(left) // 8), left)
    values_right = struct.unpack("<" + "d" * (len(right) // 8), right)
    return math.sqrt(math.fsum((a - b) * (a - b) for a, b in zip(values_left, values_right)))


def _without(value: Mapping[str, Any], *names: str) -> dict[str, Any]:
    excluded = set(names)
    return {str(key): item for key, item in value.items() if key not in excluded}


def _check_self(value: Mapping[str, Any], domain: str, name: str = "self_sha256") -> None:
    claimed = value.get(name)
    require(isinstance(claimed, str) and len(claimed) == 64, f"{name} missing")
    require(claimed == _hash(_without(value, name), domain), f"bad {name} for {value.get('schema', 'object')}")
def _core_receipt_payload(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    if receipt.get("schema") != CORE_RECEIPT_SCHEMA:
        return receipt
    extras = {"core_receipt_sha256", "runner_committable", "runner_failure_reason"} & set(receipt)
    if not extras:
        return receipt
    core = _without(receipt, *extras)
    require(receipt.get("core_receipt_sha256") == core.get("self_sha256"), "flattened core receipt identity mismatch")
    return core


def _close(left: float, right: float, tolerance: float = 1.0e-9) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def _close_value(actual: Any, expected: Any, tolerance: float = 1.0e-9, name: str = "value") -> None:
    if isinstance(expected, complex):
        try:
            observed = actual if isinstance(actual, complex) else complex(str(actual).replace(" ", ""))
        except (TypeError, ValueError) as exc:
            raise VerificationError(f"{name} is not a serialized complex value") from exc
        require(_close(float(observed.real), float(expected.real), tolerance) and _close(float(observed.imag), float(expected.imag), tolerance), f"{name} complex mismatch")
        return
    if isinstance(expected, Mapping):
        require(isinstance(actual, Mapping), f"{name} is not an object")
        for key, value in expected.items():
            require(key in actual, f"{name}.{key} missing")
            _close_value(actual[key], value, tolerance, f"{name}.{key}")
        return
    if isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{name} list mismatch")
        for index, value in enumerate(expected):
            _close_value(actual[index], value, tolerance, f"{name}[{index}]")
        return
    if isinstance(expected, bool) or expected is None or isinstance(expected, str) and not expected.startswith("f64:"):
        if isinstance(expected, str) and expected.startswith("(") and expected.endswith("j)"):
            return _close_value(actual, complex(expected[1:-1]), tolerance, name)
        require(actual == expected, f"{name} mismatch")
        return
    if isinstance(expected, (int, float)) or (isinstance(expected, str) and expected.startswith("f64:")):
        require(_close(_number(actual, name), _number(expected, name), tolerance), f"{name} numeric mismatch")
        return
    require(actual == expected, f"{name} mismatch")


def _all_json(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _resolve_root(root: Path | str) -> Path:
    path = Path(root).resolve()
    if (path / "index.json").is_file():
        return path
    candidates = [child for child in path.iterdir() if child.is_dir() and (child / "index.json").is_file()]
    require(len(candidates) == 1, f"expected one artifact run under {path}, found {len(candidates)}")
    return candidates[0]


def _source_records(root: Path) -> list[dict[str, Any]]:
    for path in _all_json(root):
        if "sources/" in path.relative_to(root).as_posix() or "source-identity" in path.name:
            try:
                obj = _load(path)
            except VerificationError:
                continue
            rows = obj.get("sources")
            if isinstance(rows, list) and rows and all(isinstance(row, Mapping) for row in rows):
                result = []
                for row in rows:
                    if isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str):
                        result.append(dict(row))
                if result:
                    return result
    index = _load(root / "index.json")
    rows = []
    for row in index.get("objects", []):
        if isinstance(row, Mapping) and str(row.get("path", "")).startswith("sources/"):
            rows.append({"path": str(row["path"])[len("sources/"):], "sha256": row.get("sha256"), "byte_count": row.get("byte_count")})
    return rows


def _source_exact(root: Path, *, require_names: bool = True) -> list[dict[str, Any]]:
    records = _source_records(root)
    require(records, f"source identity missing under {root}")
    seen: set[str] = set()
    for row in records:
        relative = str(row["path"])
        require(relative not in seen, f"duplicate source identity: {relative}")
        seen.add(relative)
        snapshot = root / "sources" / relative
        current = ROOT / relative
        require(snapshot.is_file(), f"source snapshot missing: {relative}")
        raw = snapshot.read_bytes()
        require(_sha(raw) == str(row["sha256"]).lower(), f"source snapshot hash mismatch: {relative}")
        if row.get("byte_count") is not None:
            require(int(row["byte_count"]) == len(raw), f"source byte count mismatch: {relative}")
        require(current.is_file(), f"current source missing: {relative}")
        require(_sha(current.read_bytes()) == _sha(raw), f"stale source identity: {relative}")
    if require_names:
        names = {str(row["path"]) for row in records}
        require(REQUIRED_SOURCE_NAMES.issubset(names), "W4R source identity does not cover the core")
    return records


def _verify_manifest(root: Path, index: Mapping[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "index.json":
            raw = path.read_bytes()
            records.append({"path": path.relative_to(root).as_posix(), "byte_count": len(raw), "sha256": _sha(raw)})
    listed = index.get("objects")
    require(isinstance(listed, list), "index object inventory missing")
    require(list(records) == [dict(row) for row in listed], "index object inventory mismatch")
    require(index.get("object_count") == len(records), "index object count mismatch")
    manifest_path = root / "objects" / "manifest.json"
    require(manifest_path.is_file(), "content-addressed object manifest missing")
    manifest = _load(manifest_path)
    require(manifest.get("schema") == "cassi.qi-flow-w4r-retention-core-object-manifest.v1", "wrong object manifest schema")
    objects = manifest.get("objects")
    require(isinstance(objects, Mapping) and objects, "empty content-addressed object manifest")
    for digest, relative in objects.items():
        require(isinstance(digest, str) and len(digest) == 64, "invalid content object digest")
        require(isinstance(relative, str) and relative == f"objects/sha256/{digest}", "invalid content object path")
        content = root / relative
        require(content.is_file() and _sha(content.read_bytes()) == digest, f"content object mismatch: {digest}")


def _self_domain(obj: Mapping[str, Any], path: Path) -> str | None:
    schema = str(obj.get("schema", ""))
    if not isinstance(obj.get("self_sha256"), str):
        return None
    if schema == INDEX_SCHEMA:
        return INDEX_SCHEMA
    if schema == STATUS_SCHEMA:
        return STATUS_SCHEMA
    if schema == CANDIDATE_SCHEMA:
        return CANDIDATE_SCHEMA
    if schema == RAW_SCHEMA:
        return RAW_DOMAIN
    if schema == CORE_RECEIPT_SCHEMA:
        return CORE_RECEIPT_DOMAIN
    if schema.endswith("retention-core-transition-receipt.v1") or schema.endswith("retention-core-control.v1"):
        return RECEIPT_DOMAIN
    if schema.endswith("retention-core-path.v1"):
        return ARTIFACT_DOMAIN + ".path"
    if schema.endswith("retention-core-reset-receipt.v1"):
        return RECEIPT_DOMAIN + ".reset"
    if schema.endswith("retention-core-codebook.v1"):
        return ARTIFACT_DOMAIN + ".codebook"
    if schema.endswith("retention-core-barrier-certificate.v1"):
        return ARTIFACT_DOMAIN + ".barrier"
    if schema.endswith("retention-core-reset-operator.v1"):
        return ARTIFACT_DOMAIN + ".reset-operator"
    if schema.endswith("retention-core-endpoint-subdivision.v1"):
        return ARTIFACT_DOMAIN + ".endpoint-subdivision"
    if schema.endswith("retention-core-law-identity.v1"):
        return ARTIFACT_DOMAIN + ".core-law"
    if schema.endswith("retention-core-conversion-path.v1"):
        return ARTIFACT_DOMAIN + ".conversion-path"
    if schema.endswith("retention-core-gate-receipt.v1"):
        return ARTIFACT_DOMAIN + ".gate-receipt"
    if schema.endswith("retention-core-no-added-state.v1"):
        return ARTIFACT_DOMAIN + ".no-added-state"
    if schema.endswith("retention-core-extension.v1"):
        return ARTIFACT_DOMAIN + ".extension"
    if schema.endswith("retention-core-parent.v1"):
        return ARTIFACT_DOMAIN + ".parent"
    if schema == "cassi.qi-flow-w4r-retention-core-w3n-ancestry.v1":
        return "cassi.qi-flow-w4r-retention-core-w3n-ancestry"
    if schema == PROFILE_DOMAIN:
        return PROFILE_DOMAIN
    if schema == PROFILE_ROOT_DOMAIN:
        return PROFILE_ROOT_DOMAIN
    if not schema and set(obj) == {"operator_id", "target", "preserve", "self_sha256"}:
        return RESET_DOMAIN
    if schema == "cassi.qi-flow-w4r-retention-core-source-identity.v1":
        return None
    if schema.endswith("retention-core-object-manifest.v1"):
        return None
    if schema == "cassi.qi-flow-w4r-retention-core-state-layout.v1":
        return None
    if schema.endswith("certificate-extension.v1"):
        return str(obj.get("domain", schema))
    if schema.endswith("numerical-certificate.v1"):
        return schema
    return str(obj.get("domain", schema)) if schema else None
def _verify_all_self_hashes(root: Path) -> None:
    for path in _all_json(root):
        obj = _load(path)
        if obj.get("schema") == CORE_RECEIPT_SCHEMA:
            core = _core_receipt_payload(obj)
            _check_self(core, CORE_RECEIPT_DOMAIN)
            continue
        domain = _self_domain(obj, path)
        if domain is not None:
            _check_self(obj, domain)
        if obj.get("schema") == "cassi.qi-flow-w4r-retention-core-extension.v1":
            if obj.get("final_certificate_identity_sha256") is not None:
                expected = _hash(_without(obj, "self_sha256", "final_certificate_identity_sha256"), str(obj.get("domain", ARTIFACT_DOMAIN + ".extension")))
                require(obj.get("final_certificate_identity_sha256") == expected, f"bad final certificate identity: {path}")


def _tokens(value: Any, key: str = "") -> set[str]:
    if isinstance(value, Mapping):
        result: set[str] = set()
        for name, child in value.items():
            result.update(_tokens(child, str(name)))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(_tokens(child, key))
        return result
    if isinstance(value, str) and (key == "run_id" or key.endswith("_sha256") or key in {"certificate_id", "parent_id"}):
        return {value}
    return set()


def _verified_candidates(directory: Path, marker: str, module_name: str) -> list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]:
    if not directory.is_dir():
        return []
    try:
        verifier = importlib.import_module(module_name)
        verify_parent = getattr(verifier, "verify")
    except Exception as exc:
        raise VerificationError(f"independent parent verifier unavailable: {module_name}") from exc
    result = []
    for index_path in sorted(directory.rglob("index.json")):
        try:
            index = _load(index_path)
            schema = str(index.get("schema", "")).lower()
            status = str(index.get("status", "")).upper()
            candidate_root = index_path.parent
            require(marker in schema and status.startswith("PASS"), "candidate marker/status mismatch")
            require(str(index.get("run_id")) == candidate_root.name, "candidate run id/path mismatch")
            records = _source_exact(candidate_root, require_names=False)
            outcome = verify_parent(candidate_root)
            require(isinstance(outcome, Mapping) and str(outcome.get("status", "")).upper().startswith("PASS"), "independent parent verifier rejected candidate")
            result.append((candidate_root, index, records))
        except Exception:
            continue
    return result


def _discover_parents() -> dict[str, Any]:
    w4_dir = ROOT / "_diag" / "cassi-qi-flow-w4-periodic-fft2-final"
    w3n_dir = ROOT / "_diag" / "cassi-qi-flow-w3n-periodic-fft2-final"
    w4 = [row for row in _verified_candidates(w4_dir, "w4-periodic-fft2", "verify_cassi_qi_carrier") if "w4r" not in str(row[1].get("schema", "")).lower()]
    require(len(w4) == 1, f"expected exactly one current W4 parent, found {len(w4)}")
    w4_root, w4_index, w4_sources = w4[0]
    w3n = _verified_candidates(w3n_dir, "w3n-periodic-fft2", "verify_cassi_qi_numerical_certificate")
    require(w3n, "no current source-exact W3N candidate")
    declared_w3n = w4_index.get("w3n_parent_run_id")
    if isinstance(declared_w3n, str):
        linked = [candidate for candidate in w3n if candidate[1].get("run_id") == declared_w3n]
    else:
        w4_tokens: set[str] = set()
        for path in _all_json(w4_root):
            if "sources/" not in path.relative_to(w4_root).as_posix():
                w4_tokens.update(_tokens(_load(path)))
        linked = []
        for candidate in w3n:
            candidate_tokens: set[str] = set()
            for path in _all_json(candidate[0]):
                if "sources/" not in path.relative_to(candidate[0]).as_posix():
                    candidate_tokens.update(_tokens(_load(path)))
            if w4_tokens & candidate_tokens:
                linked.append(candidate)
    require(len(linked) == 1, f"expected exactly one W3N ancestry linked to current W4, found {len(linked)}")
    w3n_root, w3n_index, w3n_sources = linked[0]
    gate_candidates = []
    for path in _all_json(w4_root):
        relative = path.relative_to(w4_root).as_posix().lower()
        if "gates/g04-carrier/" not in relative:
            continue
        obj = _load(path)
        if str(obj.get("status", obj.get("gate_status", ""))).upper().startswith("PASS"):
            gate_candidates.append((path, obj))
    require(gate_candidates, "current W4 parent has no G4 carrier gate")
    gate_candidates.sort(key=lambda item: (item[0].name not in {"carrier.json", "status.json"}, item[0].as_posix()))
    certificate_candidates = []
    for path in _all_json(w3n_root):
        relative = path.relative_to(w3n_root).as_posix()
        if relative.startswith("sources/"):
            continue
        obj = _load(path)
        if "certificate" in str(obj.get("schema", "")).lower() and isinstance(obj.get("self_sha256"), str):
            certificate_candidates.append((path, obj))
    require(certificate_candidates, "W3N ancestry has no numerical certificate")
    certificate_candidates.sort(key=lambda item: (item[0].name != "certificate-root.json", item[0].as_posix()))
    certificate_path, certificate = certificate_candidates[0]
    ancestry = {
        "schema": "cassi.qi-flow-w4r-retention-core-w3n-ancestry.v1",
        "w3n_root_relative": w3n_root.relative_to(ROOT).as_posix() if w3n_root.is_relative_to(ROOT) else str(w3n_root),
        "certificate_path": certificate_path.relative_to(w3n_root).as_posix(),
        "certificate_sha256": certificate["self_sha256"],
        "parent_files": sorted(path.relative_to(w3n_root).as_posix() for path in _all_json(w3n_root) if "parent" in path.name or "ancestry" in path.name),
    }
    ancestry["self_sha256"] = _hash(ancestry, "cassi.qi-flow-w4r-retention-core-w3n-ancestry")
    return {
        "w4_root": w4_root,
        "w4_index": w4_index,
        "w4_sources": w4_sources,
        "w4_gate_path": gate_candidates[0][0],
        "w4_gate": gate_candidates[0][1],
        "w3n_root": w3n_root,
        "w3n_index": w3n_index,
        "w3n_sources": w3n_sources,
        "w3n_certificate": certificate,
        "w3n_ancestry": ancestry,
    }


def _parent_snapshot(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    require(path.is_file(), f"missing parent snapshot: {relative}")
    return _load(path)


def _verify_ancestry(root: Path, parents: Mapping[str, Any]) -> dict[str, Any]:
    w4_index = _parent_snapshot(root, "parents/w4-parent-index.json")
    w4_gate = _parent_snapshot(root, "parents/w4-parent-gate.json")
    w3n_index = _parent_snapshot(root, "parents/w3n-parent-index.json")
    w3n_certificate = _parent_snapshot(root, "parents/w3n-certificate-root.json")
    w3n_ancestry = _parent_snapshot(root, "parents/w3n-ancestry.json")
    require(w4_index == parents["w4_index"], "W4 parent snapshot is not the current independently verified index")
    require(w4_gate == parents["w4_gate"], "W4 gate snapshot mismatch")
    require(w3n_index == parents["w3n_index"], "W3N parent snapshot mismatch")
    require(w3n_certificate == parents["w3n_certificate"], "W3N certificate snapshot mismatch")
    _check_self(w3n_ancestry, "cassi.qi-flow-w4r-retention-core-w3n-ancestry")
    require(w3n_ancestry == parents["w3n_ancestry"], "W3N ancestry snapshot mismatch")
    parent = _parent_snapshot(root, "run-spec/parent-w4.json")
    _check_self(parent, ARTIFACT_DOMAIN + ".parent")
    require(parent.get("preserved") is True, "parent preservation flag missing")
    expected = {
        "w4_run_id": parents["w4_index"].get("run_id"),
        "w4_index_sha256": _sha(_canonical(parents["w4_index"])),
        "w4_gate_sha256": str(parents["w4_gate"].get("self_sha256", _sha(_canonical(parents["w4_gate"])))),
        "w3n_run_id": parents["w3n_index"].get("run_id"),
        "w3n_index_sha256": _sha(_canonical(parents["w3n_index"])),
        "w3n_certificate_sha256": parents["w3n_certificate"].get("self_sha256"),
    }
    for key, value in expected.items():
        require(parent.get(key) == value, f"parent identity mismatch at {key}")
    require(_parent_snapshot(root, "run-spec/parent-w3n.json") == parents["w3n_ancestry"], "run-spec W3N ancestry mismatch")
    return parent


def _unwrap_profile(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = profile.get("payload")
    return payload if isinstance(payload, Mapping) else profile


def _retention(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = _unwrap_profile(profile)
    value = payload.get("retention")
    if not isinstance(value, Mapping):
        return payload
    merged = dict(value)
    merged.update({key: item for key, item in payload.items() if key != "retention"})
    return merged


def _layout(root: Path) -> dict[str, Any]:
    obj = _load(root / "run-spec/state-layout.json")
    require(obj.get("shape_formula") == "[S,9M,B]", "state layout formula is not [S,9M,B]")
    value = obj.get("layout")
    require(isinstance(value, Mapping), "state layout payload missing")
    result = dict(value)
    for key in ("scale_count", "mode_count", "component_count", "component_order", "active_shapes"):
        require(key in result, f"state layout missing {key}")
    declared_batch = result.get("batch_count", result.get("control_batch_lanes"))
    require(declared_batch is not None, "state layout lacks an explicit profile-declared control batch count")
    scales = int(result["scale_count"])
    modes = int(result["mode_count"])
    batches = int(declared_batch)
    require(scales > 0 and modes > 0 and batches == 1 and int(result["component_count"]) == 9, "W4R frozen controls require the profile-declared single batch lane")
    result["batch_count"] = batches
    shapes = result["active_shapes"]
    require(isinstance(shapes, list) and len(shapes) == scales, "active shape registry mismatch")
    for shape in shapes:
        require(isinstance(shape, list) and len(shape) == 2 and int(shape[0]) >= 2 and int(shape[1]) >= 2, "invalid periodic sheet shape")
        require(int(shape[0]) * int(shape[1]) <= modes, "active sheet exceeds packed modes")
    order = result["component_order"]
    require(order == CANONICAL_COMPONENT_ORDER, "state layout uses a legacy or ambiguous component order")
    require(int(obj.get("slow_scale", -1)) == int(_retention(_load(root / "profiles/retention-profile.json")).get("slow_scale", -2)), "slow scale identity mismatch")
    return result


def _lane_map(layout: Mapping[str, Any]) -> dict[str, int]:
    require(layout["component_order"] == CANONICAL_COMPONENT_ORDER, "non-canonical component order")
    return {name: index for index, name in enumerate(CANONICAL_COMPONENT_ORDER)}


def _state_meta(root: Path, path: Path) -> dict[str, Any]:
    sidecar = Path(str(path) + ".json")
    require(sidecar.is_file(), f"raw state metadata missing: {path.name}")
    meta = _load(sidecar)
    require(meta.get("schema") == RAW_SCHEMA, f"wrong raw state metadata schema: {sidecar}")
    _check_self(meta, RAW_DOMAIN)
    return meta


def _decode(root: Path, path: Path, layout: Mapping[str, Any]) -> tuple[list[float], dict[str, Any]]:
    require(path.is_file(), f"raw state missing: {path}")
    raw = path.read_bytes()
    meta = _state_meta(root, path)
    shape = meta.get("shape")
    require(isinstance(shape, list) and len(shape) == 3, f"raw state shape missing: {path.name}")
    scales, width, batch = (int(item) for item in shape)
    require(scales == int(layout["scale_count"]) and width == 9 * int(layout["mode_count"]), "raw state dimensions disagree with state layout")
    require(batch > 0 and meta.get("dtype") == "float64" and meta.get("byte_order") == "little", "raw state encoding is not little-endian float64")
    require(meta.get("raw_byte_count") == len(raw) == scales * width * batch * 8, "raw state byte count mismatch")
    require(meta.get("raw_sha256") == _sha(raw), "raw state payload hash mismatch")
    values = list(struct.unpack("<" + "d" * (len(raw) // 8), raw))
    require(all(math.isfinite(value) for value in values), "raw state contains non-finite value")
    return values, meta


def _find_raw(root: Path, relative: str) -> Path:
    path = root / relative
    require(path.is_file(), f"raw state missing at declared path: {relative}")
    return path


def _raw_identity(raw: bytes) -> str:
    return _hash({"schema": RAW_SCHEMA, "raw_sha256": _sha(raw), "raw_byte_count": len(raw)}, RAW_DOMAIN)


def _state_value(values: Sequence[float], scale: int, component: int, mode: int, batch: int, modes: int, lane: int) -> float:
    return values[((scale * 9 + component) * modes + mode) * batch + lane]


def _grid(values: Sequence[float], scale: int, component: int, *, layout: Mapping[str, Any], lane: int) -> list[list[float]]:
    modes = int(layout["mode_count"])
    batch = int(layout["batch_count"])
    ny, nx = (int(item) for item in layout["active_shapes"][scale])
    return [[_state_value(values, scale, component, y * nx + x, batch, modes, lane) for x in range(nx)] for y in range(ny)]
def _state_hash(raw: bytes) -> str:
    encoded = STATE_DOMAIN.encode("utf-8")
    digest = sha256()
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _state_fields(values: Sequence[float], meta: Mapping[str, Any], layout: Mapping[str, Any], slow: int) -> dict[str, Any]:
    shape = [int(item) for item in meta["shape"]]
    batch = shape[2]
    require(batch == int(layout["batch_count"]) and batch > 0, "raw state batch count differs from the validated profile declaration")
    modes = int(layout["mode_count"])
    lane = _lane_map(layout)
    y_re = lane["Y_re"]; y_im = lane["Y_im"]; i_re = lane["I_re"]; i_im = lane["I_im"]
    vy_re = lane["VY_re"]; vy_im = lane["VY_im"]; vi_re = lane["VI_re"]; vi_im = lane["VI_im"]
    ny, nx = (int(item) for item in layout["active_shapes"][slow])
    def grid_for(re: int, im: int, b: int) -> list[list[complex]]:
        return [[complex(_state_value(values, slow, re, y * nx + x, batch, modes, b), _state_value(values, slow, im, y * nx + x, batch, modes, b)) for x in range(nx)] for y in range(ny)]
    y = [grid_for(y_re, y_im, b) for b in range(batch)]
    i = [grid_for(i_re, i_im, b) for b in range(batch)]
    vy = [grid_for(vy_re, vy_im, b) for b in range(batch)]
    vi = [grid_for(vi_re, vi_im, b) for b in range(batch)]
    for scale, raw_shape in enumerate(layout["active_shapes"]):
        active = int(raw_shape[0]) * int(raw_shape[1])
        for component_i in range(9):
            for mode in range(active, modes):
                for b in range(batch):
                    require(_state_value(values, scale, component_i, mode, batch, modes, b) == 0.0, "inactive packed mode is nonzero")
    return {"Y": y, "I": i, "VY": vy, "VI": vi, "batch": batch, "shape": (ny, nx), "lanes": lane}






def _fretention(profile: Mapping[str, Any], key: str, aliases: Sequence[str] = ()) -> float:
    payload = _unwrap_profile(profile)
    ret = _retention(profile)
    sections = (ret, payload, payload.get("potential", {}), payload.get("guards", {}), payload.get("integration", {}))
    for section in sections:
        if isinstance(section, Mapping):
            for name in (key, *aliases):
                if name in section:
                    return _number(section[name], name)
    raise VerificationError(f"retention profile field missing: {key}")

def _profile_values(profile: Mapping[str, Any], layout: Mapping[str, Any]) -> dict[str, Any]:
    ret = _retention(profile)
    mode = str(ret.get("mode", _unwrap_profile(profile).get("mode", "")))
    require(mode == "topological-v1", "fading retention cannot be the production W4R law")
    slow = int(ret.get("slow_scale", _unwrap_profile(profile).get("slow_scale", -1)))
    require(0 <= slow < int(layout["scale_count"]), "invalid slow scale")
    shape = tuple(int(item) for item in layout["active_shapes"][slow])
    transform = ret.get("d_c_transform", _unwrap_profile(profile).get("d_c_transform", {}))
    require(isinstance(transform, Mapping), "D/C transform missing")
    phi = _number(transform.get("phi"), "phi")
    wd = _number(transform.get("w_D", transform.get("w_d")), "w_D")
    wc = _number(transform.get("w_C", transform.get("w_c")), "w_C")
    require(wd > 0.0 and wc > 0.0 and _close(wd, 1.0 / (1.0 + phi * phi), 1.0e-12) and _close(wc, 1.0 + phi * phi, 1.0e-12), "D/C metric transform mismatch")
    rotation = ret.get("weighted_rotation", _unwrap_profile(profile).get("weighted_rotation", {}))
    require(isinstance(rotation, Mapping), "weighted rotation missing")
    a = _number(rotation.get("a_topo", ret.get("a_topo")), "a_topo")
    b = _number(rotation.get("b_topo", ret.get("b_topo")), "b_topo")
    require(_close(a, 0.0, 1.0e-12) and _close(b, 1.0, 1.0e-12), "production W4R requires a_topo=0,b_topo=1")
    require(_close(a * a + b * b, 1.0, 1.0e-12), "weighted rotation is not normalized")
    edge_registry = ret.get("edge_registry", _unwrap_profile(profile).get("edge_registry"))
    if isinstance(edge_registry, list):
        edge_registry = {"schema": "cassi.qi-flow-oriented-edge-registry.v1", "sheet_shape": list(shape), "edges": edge_registry}
    cycle_registry = ret.get("cycle_registry", _unwrap_profile(profile).get("cycle_registry"))
    require(isinstance(edge_registry, Mapping) and isinstance(cycle_registry, Mapping), "edge/cycle registries missing")
    metrics = ret.get("metric_weights", ret.get("metric"))
    if not isinstance(metrics, list):
        metrics = _unwrap_profile(profile).get("metric_diagonal")
    require(isinstance(metrics, list) and len(metrics) == shape[0] * shape[1], "weighted radial metric is missing dynamic site weights")
    metric = [_number(item, "metric weight") for item in metrics]
    require(all(item > 0.0 for item in metric), "radial metric weights must be positive")
    return {
        "retention": ret,
        "mode": mode,
        "slow": slow,
        "shape": shape,
        "phi": phi,
        "wd": wd,
        "wc": wc,
        "a": a,
        "b": b,
        "E": _fretention(profile, "E_topo", ("topological_energy_scale",)),
        "lambda_ph": _fretention(profile, "lambda_ph", ("phase_weight", "lambda_phase")),
        "lambda_core": _fretention(profile, "lambda_core", ("core_weight",)),
        "r_core": _fretention(profile, "r_core", ("core_radius",)),
        "rho_ring": _fretention(profile, "rho_ring", ("ring_amplitude",)),
        "rho_topo": _fretention(profile, "rho_topo", ("topological_amplitude_floor",)),
        "delta": _fretention(profile, "delta_topo", ("phase_margin",)),
        "delta_int": _fretention(profile, "delta_topo_int", ("integer_margin",)),
        "delta_h": _fretention(profile, "Delta_H_topo_min", ("delta_h_min", "barrier_min")),
        "radial_min": _fretention(profile, "radial_curvature_min", ("radial_curvature_bound",)),
        "duration": _fretention(profile, "duration", ("h",)),
        "edges": edge_registry,
        "cycles": cycle_registry,
        "metric": metric,
    }


def _edge_id(row: Mapping[str, Any], shape: tuple[int, int]) -> tuple[int, str, int]:
    ny, nx = shape
    axis = str(row.get("axis", "")).lower()
    require(axis in {"x", "y"}, "edge orientation missing")
    source = row.get("source", row.get("tail"))
    target = row.get("target", row.get("head"))
    require(isinstance(source, (int, list)) and isinstance(target, (int, list)), "edge endpoints missing")
    def site(value: Any) -> tuple[int, int]:
        if isinstance(value, int):
            require(0 <= value < ny * nx, "edge site id out of range")
            return divmod(value, nx)
        require(isinstance(value, list) and len(value) == 2, "edge coordinate is not [y,x]")
        y, x = int(value[0]), int(value[1])
        require(0 <= y < ny and 0 <= x < nx, "edge coordinate out of range")
        return y, x
    y, x = site(source)
    ty, tx = site(target)
    expected = (y, (x + 1) % nx) if axis == "x" else ((y + 1) % ny, x)
    require((ty, tx) == expected, "edge is not the exact oriented periodic neighbor")
    return y * nx + x, axis, ty * nx + tx


def _registries(values: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], float, str, str]:
    shape = values["shape"]
    edge_obj = dict(values["edges"])
    cycle_obj = dict(values["cycles"])
    edges = edge_obj.get("edges")
    require(isinstance(edges, list) and len(edges) == 2 * shape[0] * shape[1], "full oriented edge registry is incomplete")
    seen: set[tuple[int, str, int]] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(edges):
        require(isinstance(row, Mapping), "edge row is not an object")
        source, axis, target = _edge_id(row, shape)
        key = (source, axis, target)
        require(key not in seen, "duplicate oriented edge")
        seen.add(key)
        weight = _number(row.get("weight", 1.0), f"edge {index} weight")
        require(weight > 0.0, "edge weight must be positive")
        normalized.append(dict(row))
    expected = {(y * shape[1] + x, axis, (y * shape[1] + ((x + 1) % shape[1]) if axis == "x" else ((y + 1) % shape[0]) * shape[1] + x)) for axis in ("x", "y") for y in range(shape[0]) for x in range(shape[1])}
    require(seen == expected, "oriented edge registry omits or repeats an edge")
    x_cycles = cycle_obj.get("x_cycles")
    y_cycles = cycle_obj.get("y_cycles")
    plaquettes = cycle_obj.get("plaquette_origins")
    require(isinstance(x_cycles, list) and isinstance(y_cycles, list) and isinstance(plaquettes, list), "complete torus cycle/plaquette registry missing")
    require(len(x_cycles) == shape[0] and len(y_cycles) == shape[1] and len(plaquettes) == shape[0] * shape[1], "cycle/plaquette registry resolution mismatch")
    for y, cycle in enumerate(x_cycles):
        require(cycle == [y * shape[1] + x for x in range(shape[1])], "x cycle registry mismatch")
    for x, cycle in enumerate(y_cycles):
        require(cycle == [y * shape[1] + x for y in range(shape[0])], "y cycle registry mismatch")
    require(sorted(int(value) for value in plaquettes) == list(range(shape[0] * shape[1])), "plaquette registry is incomplete")
    edge_sha = _hash(_without(edge_obj, "self_sha256"), str(edge_obj.get("schema", "cassi.qi-flow-oriented-edge-registry.v1")))
    cycle_sha = _hash(_without(cycle_obj, "self_sha256"), str(cycle_obj.get("schema", "cassi.qi-flow-torus-cycle-plaquette-registry.v1")))
    return normalized, cycle_obj, sum(_number(row.get("weight", 1.0), "edge weight") for row in normalized), edge_sha, cycle_sha


def _coords(state: Mapping[str, Any], values: Mapping[str, Any]) -> tuple[list[list[complex]], list[list[complex]], list[list[complex]], list[list[complex]]]:
    phi, wd, wc = values["phi"], values["wd"], values["wc"]
    d: list[list[complex]] = []
    c: list[list[complex]] = []
    vd: list[list[complex]] = []
    vc: list[list[complex]] = []
    batch = int(state["batch"])
    require(batch > 0, "topology verifier found no declared batch lanes")
    for y in range(values["shape"][0]):
        drow: list[complex] = []
        crow: list[complex] = []
        vdrow: list[complex] = []
        vcrow: list[complex] = []
        for x in range(values["shape"][1]):
            Y = state["Y"][0][y][x]
            I = state["I"][0][y][x]
            VY = state["VY"][0][y][x]
            VI = state["VI"][0][y][x]
            drow.append(Y - phi * I)
            crow.append((phi * Y + I) * wd)
            vdrow.append(VY - phi * VI)
            vcrow.append((phi * VY + VI) * wd)
        d.append(drow); c.append(crow); vd.append(vdrow); vc.append(vcrow)
    return d, c, vd, vc


def _psi_chi(state: Mapping[str, Any], values: Mapping[str, Any]) -> tuple[list[list[complex]], list[list[complex]], list[list[complex]], list[list[complex]]]:
    d, c, vd, vc = _coords(state, values)
    sd, sc = math.sqrt(values["wd"]), math.sqrt(values["wc"])
    psi = [[values["a"] * sd * d[y][x] + values["b"] * sc * c[y][x] for x in range(values["shape"][1])] for y in range(values["shape"][0])]
    chi = [[-values["b"] * sd * d[y][x] + values["a"] * sc * c[y][x] for x in range(values["shape"][1])] for y in range(values["shape"][0])]
    vpsi = [[values["a"] * sd * vd[y][x] + values["b"] * sc * vc[y][x] for x in range(values["shape"][1])] for y in range(values["shape"][0])]
    vchi = [[-values["b"] * sd * vd[y][x] + values["a"] * sc * vc[y][x] for x in range(values["shape"][1])] for y in range(values["shape"][0])]
    return psi, chi, vpsi, vchi


def _phase_delta(left: complex, right: complex) -> float:
    return math.atan2((left.conjugate() * right).imag, (left.conjugate() * right).real)


def _round_int(value: float) -> int:
    return int(round(value))


def _diagnostics(state: Mapping[str, Any], values: Mapping[str, Any], edges: Sequence[Mapping[str, Any]], cycles: Mapping[str, Any], potential: float) -> dict[str, Any]:
    psi, chi, vpsi, vchi = _psi_chi(state, values)
    ny, nx = values["shape"]
    amplitude = [[abs(psi[y][x]) for x in range(nx)] for y in range(ny)]
    amplitude_min = min(value for row in amplitude for value in row)
    base: dict[str, Any] = {
        "schema": "cassi.qi-flow-w4r-topology-diagnostics.v1",
        "status": "INVALID",
        "mode": values["mode"],
        "law_id": "topological-v1",
        "slow_scale": values["slow"],
        "shape_yx": [ny, nx],
        "batch_lanes": 1,
        "amplitude_min": amplitude_min,
        "amplitude_floor": values["rho_topo"],
        "amplitude_margin": amplitude_min - values["rho_topo"],
        "phase_interval_radius": 0.0,
        "branch_margin_min": None,
        "integer_margin_min": None,
        "valid_by_lane": [False],
        "sector_vector": [None],
        "cycle_x": None,
        "cycle_y": None,
        "plaquette": None,
        "torus_algebra": None,
        "reason": "amplitude-floor",
        "potential": 0.0 if amplitude_min < values["rho_topo"] else potential,
        "phase_current": [sum((psi[y][x].conjugate() * vpsi[y][x]).imag for y in range(ny) for x in range(nx))],
        "chi_current": [sum((chi[y][x].conjugate() * vchi[y][x]).imag for y in range(ny) for x in range(nx))],
    }
    if amplitude_min < values["rho_topo"]:
        return base
    dx = [[0.0] * nx for _ in range(ny)]
    dy = [[0.0] * nx for _ in range(ny)]
    for row in edges:
        source = row.get("source", row.get("tail")); target = row.get("target", row.get("head"))
        def site(item: Any) -> tuple[int, int]:
            if isinstance(item, int): return divmod(item, nx)
            return int(item[0]), int(item[1])
        y, x = site(source); ty, tx = site(target)
        delta = _phase_delta(psi[y][x], psi[ty][tx])
        if str(row["axis"]).lower() == "x": dx[y][x] = delta
        else: dy[y][x] = delta
    plaquette = [[dx[y][x] + dy[y][(x + 1) % nx] - dx[(y + 1) % ny][x] - dy[y][x] for x in range(nx)] for y in range(ny)]
    cycle_x = [sum(dx[y][x] for x in range(nx)) / (2.0 * math.pi) for y in range(ny)]
    cycle_y = [sum(dy[y][x] for y in range(ny)) / (2.0 * math.pi) for x in range(nx)]
    p_raw = [[value / (2.0 * math.pi) for value in row] for row in plaquette]
    branch_margin = math.pi - max([abs(value) for row in dx for value in row] + [abs(value) for row in dy for value in row])
    integer_error = max([abs(value - _round_int(value)) for value in cycle_x + cycle_y] + [abs(value - _round_int(value)) for row in p_raw for value in row])
    algebra_x = [cycle_x[y] - cycle_x[y + 1] - sum(p_raw[y]) for y in range(ny - 1)]
    algebra_y = [cycle_y[x + 1] - cycle_y[x] - sum(p_raw[y][x] for y in range(ny)) for x in range(nx - 1)]
    algebra_error = max([abs(value) for value in algebra_x + algebra_y] + [abs(sum(value for row in p_raw for value in row))])
    branch_ok = branch_margin >= values["delta"]
    integer_ok = integer_error <= values["delta_int"]
    algebra_ok = algebra_error <= max(values["delta_int"] * 8.0, 1.0e-12)
    valid = branch_ok and integer_ok and algebra_ok
    vectors = [{"n_x": [_round_int(value) for value in cycle_x], "n_y": [_round_int(value) for value in cycle_y], "p": [[_round_int(value) for value in row] for row in p_raw]}]
    cycle_x_wire = [[value] for value in cycle_x]
    cycle_y_wire = [[value] for value in cycle_y]
    plaquette_wire = [[[value] for value in row] for row in p_raw]
    phase_x_wire = [[[value] for value in row] for row in dx]
    phase_y_wire = [[[value] for value in row] for row in dy]
    current_x_wire = [[sum((psi[y][x].conjugate() * vpsi[y][x]).imag for y in range(ny))] for x in range(nx)]
    current_y_wire = [[sum((chi[y][x].conjugate() * vchi[y][x]).imag for y in range(ny))] for x in range(nx)]
    base.update({
        "status": "VALID" if valid else "INVALID",
        "reason": "ok" if valid else ("branch-cut" if not branch_ok else ("integer-guard" if not integer_ok else "torus-algebra")),
        "valid_by_lane": [valid],
        "branch_margin_min": branch_margin,
        "integer_margin_min": values["delta_int"] - integer_error,
        "cycle_x": cycle_x_wire,
        "cycle_y": cycle_y_wire,
        "plaquette": plaquette_wire,
        "sector_vector": vectors,
        "torus_algebra": {"residual_max": [algebra_error], "valid": [algebra_ok]},
        "phase_x": phase_x_wire,
        "phase_y": phase_y_wire,
        "edge_count": len(edges),
        "edge_weight_sum": sum(_number(row.get("weight", 1.0), "edge weight") for row in edges),
        "winding": {"sector_vector": vectors},
        "charge": {"sector_vector": vectors, "plaquette": plaquette_wire},
        "current_x": current_x_wire,
        "current_y": current_y_wire,
        "vortex_density": plaquette_wire,
    })
    return base


def _potential_force(state: Mapping[str, Any], values: Mapping[str, Any], edges: Sequence[Mapping[str, Any]]) -> tuple[float, list[list[complex]], list[list[complex]]]:
    psi, _, _, _ = _psi_chi(state, values)
    ny, nx = values["shape"]
    edge_sum = sum(_number(row.get("weight", 1.0), "edge weight") for row in edges)
    require(edge_sum > 0.0, "edge weight sum must be positive")
    smooth = [[z / math.sqrt(abs(z) ** 2 + values["r_core"] ** 2) for z in row] for row in psi]
    phase = 0.0
    gradient = [[0j for _ in range(nx)] for _ in range(ny)]
    for row in edges:
        source = row.get("source", row.get("tail")); target = row.get("target", row.get("head"))
        def site(item: Any) -> tuple[int, int]:
            if isinstance(item, int): return divmod(item, nx)
            return int(item[0]), int(item[1])
        y, x = site(source); ty, tx = site(target); weight = _number(row.get("weight", 1.0), "edge weight")
        phase += weight * (1.0 - (smooth[y][x].conjugate() * smooth[ty][tx]).real)
        qi, qj = abs(psi[y][x]) ** 2, abs(psi[ty][tx]) ** 2
        ri3 = (qi + values["r_core"] ** 2) ** 1.5
        rj3 = (qj + values["r_core"] ** 2) ** 1.5
        term_i = ((qi + 2.0 * values["r_core"] ** 2) * smooth[ty][tx] - psi[y][x] ** 2 * smooth[ty][tx].conjugate()) / (4.0 * ri3)
        term_j = ((qj + 2.0 * values["r_core"] ** 2) * smooth[y][x] - psi[ty][tx] ** 2 * smooth[y][x].conjugate()) / (4.0 * rj3)
        gradient[y][x] -= weight * term_i / edge_sum
        gradient[ty][tx] -= weight * term_j / edge_sum
    metric_sum = sum(values["metric"])
    core = 0.0
    for y in range(ny):
        for x in range(nx):
            q = abs(psi[y][x]) ** 2
            core += values["metric"][y * nx + x] * ((q - values["rho_ring"] ** 2) / (q + values["rho_ring"] ** 2)) ** 2
            derivative = 4.0 * values["rho_ring"] ** 2 * (q - values["rho_ring"] ** 2) / (q + values["rho_ring"] ** 2) ** 3
            gradient[y][x] = values["E"] * (values["lambda_ph"] * gradient[y][x] + values["lambda_core"] * values["metric"][y * nx + x] * derivative * psi[y][x] / metric_sum) / values["metric"][y * nx + x]
    potential = values["E"] * (values["lambda_ph"] * phase / edge_sum + values["lambda_core"] * core / metric_sum)
    fd = [[-2.0 * values["a"] * g / math.sqrt(values["wd"]) for g in row] for row in gradient]
    fc = [[-2.0 * values["b"] * g / math.sqrt(values["wc"]) for g in row] for row in gradient]
    return potential, fd, fc


def _compare_diagnostics(actual: Mapping[str, Any], expected: Mapping[str, Any], name: str) -> None:
    for key in ("schema", "mode", "law_id", "slow_scale", "shape_yx", "batch_lanes", "status", "reason", "valid_by_lane", "sector_vector"):
        require(key in actual, f"{name}.{key} missing")
        _close_value(actual[key], expected[key], 1.0e-7, f"{name}.{key}")
    for key in ("amplitude_min", "amplitude_floor", "amplitude_margin", "potential", "branch_margin_min", "integer_margin_min", "cycle_x", "cycle_y", "plaquette", "phase_x", "phase_y", "edge_weight_sum"):
        if key in expected:
            require(key in actual, f"{name}.{key} missing")
            _close_value(actual[key], expected[key], 1.0e-7, f"{name}.{key}")
    require(isinstance(actual.get("winding"), Mapping), f"{name}.winding must be a full sector vector")
    require(isinstance(actual.get("charge"), Mapping), f"{name}.charge must be a full sector vector")
    require(isinstance(actual.get("torus_algebra"), Mapping), f"{name}.torus_algebra missing")


def _radial(values: Mapping[str, Any]) -> dict[str, Any]:
    R = values["rho_ring"] ** 2
    q = R
    curvature = values["E"] * values["lambda_core"] * 8.0 * R * (-3.0 * q * q + 8.0 * R * q - R * R) / (q + R) ** 4
    require(curvature >= values["radial_min"], "radial curvature is below the declared positive bound")
    upper = values["E"] * (2.0 * values["lambda_ph"] + values["lambda_core"])
    require(values["delta_h"] > 0.0 and upper > values["delta_h"], "barrier bounds are not positive and ordered")
    return {"radius": values["rho_ring"], "value": curvature, "lower": values["radial_min"], "barrier_lower": values["delta_h"], "barrier_upper": upper}


def _f64_tag(value: float) -> str:
    require(math.isfinite(value) and not (value == 0.0 and math.copysign(1.0, value) < 0.0), "cannot tag non-finite f64")
    return "f64:" + struct.pack(">d", float(value)).hex()
def _verify_derived(root: Path, profile_obj: Mapping[str, Any], values: Mapping[str, Any], edges: list[dict[str, Any]], cycle: Mapping[str, Any], edge_sha: str, cycle_sha: str) -> dict[str, Any]:
    codebook = _load(root / "certificate/topological-v1-codebook.json")
    endpoint = _load(root / "certificate/endpoint-subdivision.json")
    barrier = _load(root / "certificate/barrier-certificate.json")
    reset = _load(root / "certificate/reset-operator.json")
    core = _load(root / "certificate/core-law-identity.json")
    extension = _load(root / "certificate/extension-0003.json")
    derivation = _load(root / "certificate/retention-derivation.json")
    _check_self(codebook, CODEBOOK_DOMAIN)
    _check_self(endpoint, ARTIFACT_DOMAIN + ".endpoint-subdivision")
    _check_self(barrier, BARRIER_DOMAIN)
    _check_self(reset, RESET_DOMAIN)
    _check_self(core, ARTIFACT_DOMAIN + ".core-law")
    require(core.get("schema") == "cassi.qi-flow-w4r-retention-core-law-identity.v1" and core.get("module") == "cassi_qi_topology" and core.get("class") == "QiTopologicalRetentionLaw" and core.get("transition") == "cassi_qi_topology.QiTopologicalRetentionLaw.transition_w4r_topology" and core.get("reset") == "transition_kind=retention_reset" and core.get("immutable_public_transition") is True and core.get("additional_state") is False, "W4R core law identity is not the immutable landing signature")
    require(endpoint.get("schema") == "cassi.qi-flow-w4r-retention-core-endpoint-subdivision.v1" and endpoint.get("method") == "deterministic-lipschitz-interval-refinement.v1" and endpoint.get("termination") == "amplitude-floor-branch-integer-and-torus-algebra-decided" and endpoint.get("positive_duration_only") is True and endpoint.get("unresolved") == "reject", "endpoint subdivision contract is missing")
    _check_self(extension, ARTIFACT_DOMAIN + ".extension")
    profile = _unwrap_profile(profile_obj)
    ret = _retention(profile_obj)
    require(codebook.get("law_id") == "topological-v1", "topology codebook is not topological-v1")
    require(codebook.get("edge_count_policy") == "each-oriented-edge-exactly-once.v1", "topology codebook does not bind the full edge registry")
    require(codebook.get("self_sha256") == extension.get("codebook_sha256"), "extension codebook identity mismatch")
    require(codebook.get("edge_registry") == edges and codebook.get("cycle_registry") == cycle, "codebook registries differ from profile")
    expected_barrier = {
        "schema": "cassi.qi-flow-w4r-barrier-certificate.v1",
        "law_id": "topological-v1",
        "potential": "E_topo*(lambda_ph*U_phase+lambda_core*U_core)",
        "core": "((|psi|^2-rho_ring^2)/(|psi|^2+rho_ring^2))^2",
        "smooth_radius": "sqrt(|psi|^2+r_core^2)",
        "rho_ring": _f64_tag(values["rho_ring"]),
        "rho_topo": _f64_tag(values["rho_topo"]),
        "radial_curvature_min": _f64_tag(values["radial_min"]),
        "Delta_H_topo_min": _f64_tag(values["delta_h"]),
        "potential_upper_bound": _f64_tag(values["E"] * (2.0 + values["lambda_core"])),
        "guard_policy": "reject-before-commit.v1",
    }
    require(_without(barrier, "self_sha256") == expected_barrier, "barrier certificate is not core-exact")
    require(barrier.get("self_sha256") == extension.get("barrier_certificate_sha256"), "extension barrier identity mismatch")
    expected_reset = {"operator_id": "authenticated-topological-retention-reset.v1", "target": "psi_topo=rho_ring*exp(i*theta0);V_psi=0", "preserve": ["chi_topo", "V_chi_topo"]}
    require(_without(reset, "self_sha256") == expected_reset and reset.get("self_sha256") == _hash(expected_reset, RESET_DOMAIN), "reset operator is not core-exact")
    require(reset.get("self_sha256") == extension.get("reset_operator_sha256"), "extension reset identity mismatch")
    require(codebook.get("sheet_shape_yx") == list(values["shape"]), "codebook active sheet shape mismatch")
    require(codebook.get("weighted_rotation") == {"a_topo": _f64_tag(0.0), "b_topo": _f64_tag(1.0)}, "codebook weighted rotation is not the frozen topological rotation")
    require(codebook.get("sector_vector") == "(n_x[row], n_y[column], p[row,column])", "codebook sector vector is not full torus topology")
    require(codebook.get("edge_count_policy") == "each-oriented-edge-exactly-once.v1", "topology codebook does not bind the full edge registry")
    profile_id = profile_obj.get("profile_sha256", profile.get("profile_sha256"))
    root_id = profile_obj.get("root_sha256", profile_obj.get("profile_root_sha256"))
    for key, expected in (("profile_sha256", profile_id), ("root_sha256", root_id), ("edge_registry_sha256", edge_sha), ("cycle_registry_sha256", cycle_sha), ("codebook_sha256", codebook.get("self_sha256")), ("barrier_certificate_sha256", barrier.get("self_sha256")), ("reset_operator_sha256", reset.get("self_sha256"))):
        require(extension.get(key) == expected, f"extension identity mismatch at {key}")
    require(extension.get("schema") == "cassi.qi-flow-w4r-retention-core-extension.v1" and extension.get("domain") == ARTIFACT_DOMAIN + ".extension" and extension.get("mode") == "topological-v1" and extension.get("owning_package") == "W4R" and extension.get("gate") == "G4R" and extension.get("additional_state") is False, "invalid W4R retention-core extension")
    topology = extension.get("topology_v1")
    require(isinstance(topology, Mapping), "topological-v1 extension body missing")
    require(topology.get("codebook") == codebook and topology.get("endpoint_subdivision") == endpoint and topology.get("edge_registry") == values["edges"] and topology.get("cycle_registry") == cycle and topology.get("barrier_certificate") == barrier and topology.get("reset_operator") == reset and topology.get("core_law") == core, "extension nested law objects mismatch")
    require(derivation.get("schema") == "cassi.qi-flow-w4r-retention-core-derivation.v1", "retention derivation schema missing")
    require(derivation.get("formula") == "QiTopologicalRetentionLaw.public_transition.v1" and derivation.get("additional_state") is False, "retention derivation is not the frozen core law")
    for key in ("profile_sha256", "root_sha256", "edge_registry_sha256", "cycle_registry_sha256", "codebook_sha256", "endpoint_subdivision_sha256", "barrier_certificate_sha256", "reset_operator_sha256", "core_law_sha256"):
        require(derivation.get(key) in {extension.get(key), profile_obj.get(key), profile.get(key)}, f"derivation identity missing: {key}")
    core_codebook = {
        "schema": "cassi.qi-flow-w4r-topology-codebook.v1",
        "law_id": "topological-v1",
        "sheet_shape_yx": list(values["shape"]),
        "edge_registry": edges,
        "cycle_registry": cycle,
        "weighted_rotation": {"a_topo": _f64_tag(values["a"]), "b_topo": _f64_tag(values["b"])},
        "sector_vector": "(n_x[row], n_y[column], p[row,column])",
        "edge_count_policy": "each-oriented-edge-exactly-once.v1",
    }
    require(ret.get("topology_codebook_sha256") == _hash(core_codebook, CODEBOOK_DOMAIN), "profile topological codebook identity is not derived")
    core_barrier = {
        "schema": "cassi.qi-flow-w4r-barrier-certificate.v1",
        "law_id": "topological-v1",
        "potential": "E_topo*(lambda_ph*U_phase+lambda_core*U_core)",
        "core": "((|psi|^2-rho_ring^2)/(|psi|^2+rho_ring^2))^2",
        "smooth_radius": "sqrt(|psi|^2+r_core^2)",
        "rho_ring": _f64_tag(values["rho_ring"]),
        "rho_topo": _f64_tag(values["rho_topo"]),
        "radial_curvature_min": _f64_tag(values["radial_min"]),
        "Delta_H_topo_min": _f64_tag(values["delta_h"]),
        "potential_upper_bound": _f64_tag(values["E"] * (2.0 + values["lambda_core"])),
        "guard_policy": "reject-before-commit.v1",
    }
    require(ret.get("barrier_certificate_sha256") == _hash(core_barrier, BARRIER_DOMAIN), "profile barrier identity is not derived")
    core_reset = {
        "operator_id": "authenticated-topological-retention-reset.v1",
        "target": "psi_topo=rho_ring*exp(i*theta0);V_psi=0",
        "preserve": ["chi_topo", "V_chi_topo"],
    }
    require(ret.get("reset_operator_sha256") == _hash(core_reset, RESET_DOMAIN), "profile reset identity is not derived")
    return {"codebook": codebook, "endpoint": endpoint, "barrier": barrier, "reset": reset, "core": core, "extension": extension, "derivation": derivation, "radial": _radial(values)}
def _core_transition_receipt(receipt: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    schema = str(receipt.get("schema", ""))
    if schema == CORE_RECEIPT_SCHEMA:
        nested = receipt.get("core_receipt")
        if isinstance(nested, Mapping):
            _check_self(receipt, RECEIPT_DOMAIN)
            _check_self(nested, CORE_RECEIPT_DOMAIN)
            require(receipt.get("core_receipt_sha256") == nested.get("self_sha256"), f"{name} core receipt identity mismatch")
            return nested
        core = _core_receipt_payload(receipt)
        _check_self(core, CORE_RECEIPT_DOMAIN)
        return core
    require(schema.endswith("retention-core-transition-receipt.v1") or schema.endswith("retention-core-control.v1"), f"{name} receipt schema is not a W4R transition receipt")
    _check_self(receipt, RECEIPT_DOMAIN)
    nested = receipt.get("core_receipt")
    if isinstance(nested, Mapping):
        core = nested
    else:
        core = _without(receipt, "self_sha256", "core_receipt_sha256", "runner_committable", "runner_failure_reason")
        core["schema"] = CORE_RECEIPT_SCHEMA
        core["self_sha256"] = receipt.get("core_receipt_sha256")
    _check_self(core, CORE_RECEIPT_DOMAIN)
    require(receipt.get("core_receipt_sha256") == core.get("self_sha256"), f"{name} core receipt identity mismatch")
    return core


def _rejected_core_receipt(core: Mapping[str, Any], name: str) -> None:
    require(core.get("schema") == CORE_RECEIPT_SCHEMA and core.get("status") == "REJECTED" and core.get("committable") is False, f"{name} rejection receipt is not an authenticated core rejection")
    require(isinstance(core.get("stage"), str) and bool(core["stage"].strip()), f"{name} rejection stage missing")
    require(isinstance(core.get("failure_reason"), str) and bool(core["failure_reason"].strip()), f"{name} rejection reason missing")
    require(core.get("candidate_state_sha256") is None, f"{name} rejected core receipt exposed a candidate hash")


def _accepted_core_receipt(core: Mapping[str, Any], name: str) -> None:
    require(core.get("schema") == CORE_RECEIPT_SCHEMA and core.get("status") == "PASS" and core.get("committable") is True, f"{name} acceptance receipt is not an authenticated core acceptance")
    require(core.get("additional_state") is False, f"{name} added hidden topology state")


def _verify_core_receipt_fields(core: Mapping[str, Any], name: str, expected: str, predecessor_sha: str, candidate_raw: bytes | None, diag_pre: Mapping[str, Any], diag_post: Mapping[str, Any] | None, values: Mapping[str, Any]) -> None:
    if expected == "REJECT":
        _rejected_core_receipt(core, name)
        return
    _accepted_core_receipt(core, name)
    require(core.get("predecessor_state_sha256") == predecessor_sha, f"{name} predecessor state hash mismatch")
    require(isinstance(core.get("candidate_state_sha256"), str) and candidate_raw is not None and core["candidate_state_sha256"] == _state_hash(candidate_raw), f"{name} candidate state hash mismatch")
    require(isinstance(core.get("g3n_certificate_sha256"), str) and len(core["g3n_certificate_sha256"]) == 64, f"{name} missing G3N certificate identity")
    for key in ("profile_sha256", "root_sha256", "topology_codebook_sha256", "barrier_certificate_sha256", "reset_operator_sha256", "g3n_certificate_sha256"):
        expected_identity = values.get(key)
        if expected_identity is not None:
            require(core.get(key) == expected_identity, f"{name} {key} identity mismatch")
    require(core.get("pre_sector_vector") == diag_pre.get("sector_vector"), f"{name} pre-sector vector mismatch")
    require(_close(_number(core.get("pre_potential"), f"{name} pre potential"), diag_pre["potential"], 1.0e-7), f"{name} pre potential mismatch")
    require(isinstance(diag_post, Mapping), f"{name} post diagnostics missing")
    require(core.get("post_sector_vector") == diag_post.get("sector_vector"), f"{name} post-sector vector mismatch")
    require(_close(_number(core.get("post_potential"), f"{name} post potential"), diag_post["potential"], 1.0e-7), f"{name} post potential mismatch")
    require(_close(_number(core.get("delta_potential"), f"{name} potential delta"), diag_post["potential"] - diag_pre["potential"], 1.0e-7), f"{name} potential delta mismatch")
    expected_event = "same-sector" if core.get("pre_sector_vector") == core.get("post_sector_vector") else "phase-slip"
    require(core.get("sector_event") == expected_event, f"{name} sector event was inferred or mislabeled")
    bounds = core.get("barrier_bounds")
    radial = _radial(values)
    require(isinstance(bounds, Mapping) and _close(_number(bounds.get("lower"), f"{name} barrier lower"), values["delta_h"], 1.0e-7) and _close(_number(bounds.get("upper"), f"{name} barrier upper"), radial["barrier_upper"], 1.0e-7) and _close(_number(bounds.get("Delta_H_topo_min"), f"{name} barrier delta"), values["delta_h"], 1.0e-7), f"{name} barrier bounds mismatch")
    curvature = core.get("radial_curvature")
    require(isinstance(curvature, Mapping) and _close(_number(curvature.get("value"), f"{name} radial curvature"), radial["value"], 1.0e-7) and _close(_number(curvature.get("lower"), f"{name} radial lower"), radial["lower"], 1.0e-7) and curvature.get("valid") is True, f"{name} radial curvature mismatch")
    carrier = core.get("carrier_split_receipt")
    require(isinstance(carrier, Mapping) and isinstance(carrier.get("schema"), str) and isinstance(carrier.get("self_sha256"), str) and len(carrier["self_sha256"]) == 64 and carrier.get("status") in {"PASS", "COMMITTED"} and carrier.get("committable") is True, f"{name} carrier split receipt missing")
    require(carrier.get("schema") == "cassi.qi-flow-carrier-receipt.v1", f"{name} carrier split receipt schema mismatch")
    _check_self(carrier, "cassi.qi-flow-w4-carrier-receipt.v1")



def _control_paths(root: Path, name: str, row: Mapping[str, Any]) -> tuple[Path, Path | None]:
    predecessor_relative = row.get("predecessor_raw_path")
    require(isinstance(predecessor_relative, str), f"{name} predecessor raw path missing")
    predecessor = _find_raw(root, predecessor_relative)
    candidate_relative = row.get("candidate_raw_path")
    if candidate_relative is not None:
        require(isinstance(candidate_relative, str), f"{name} candidate raw path malformed")
        return predecessor, _find_raw(root, candidate_relative)
    return predecessor, None


def _verify_controls(root: Path, candidate: Mapping[str, Any], profile: Mapping[str, Any], values: Mapping[str, Any], edges: list[dict[str, Any]], cycle: Mapping[str, Any], layout: Mapping[str, Any]) -> dict[str, Any]:
    controls = candidate.get("controls")
    require(isinstance(controls, Mapping) and set(controls) == set(EXPECTED_CONTROLS), "G4R control set is incomplete or changed")
    output: dict[str, Any] = {}
    for name, expected_decision in EXPECTED_CONTROLS.items():
        row = controls[name]
        require(isinstance(row, Mapping) and row.get("control_id") == name, f"control identity mismatch: {name}")
        require(row.get("expected_decision") == expected_decision and row.get("actual_decision") == expected_decision, f"control decision mismatch: {name}")
        predecessor_path, candidate_path = _control_paths(root, name, row)
        predecessor_raw = predecessor_path.read_bytes()
        predecessor_values, predecessor_meta = _decode(root, predecessor_path, layout)
        predecessor_state = _state_fields(predecessor_values, predecessor_meta, layout, values["slow"])
        potential_pre, _, _ = _potential_force(predecessor_state, values, edges)
        diag_pre = _diagnostics(predecessor_state, values, edges, cycle, potential_pre)
        reported_pre = row.get("topology_pre")
        require(isinstance(reported_pre, Mapping), f"{name} pre-topology receipt missing")
        core_pre = reported_pre.get("core") if isinstance(reported_pre.get("core"), Mapping) else reported_pre
        _compare_diagnostics(core_pre, diag_pre, f"{name}.topology_pre")
        require(row.get("predecessor_raw_sha256") == _raw_identity(predecessor_raw), f"{name} predecessor raw identity mismatch")
        require(row.get("predecessor_raw_metadata") == predecessor_meta, f"{name} predecessor metadata mismatch")
        candidate_raw: bytes | None = None
        diag_post: Mapping[str, Any] | None = None
        if expected_decision == "REJECT":
            require(row.get("candidate_raw_sha256") is None and candidate_path is None, f"{name} rejected control exposed a candidate state")
            require(row.get("candidate_raw_metadata") is None and row.get("topology_post") is None, f"{name} rejected control has post-state")
        else:
            require(row.get("candidate_raw_sha256") is not None and candidate_path is not None, f"{name} accepted control has no candidate raw state")
            candidate_raw = candidate_path.read_bytes()
            candidate_values, candidate_meta = _decode(root, candidate_path, layout)
            candidate_state = _state_fields(candidate_values, candidate_meta, layout, values["slow"])
            potential_post, _, _ = _potential_force(candidate_state, values, edges)
            diag_post = _diagnostics(candidate_state, values, edges, cycle, potential_post)
            reported_post = row.get("topology_post")
            require(isinstance(reported_post, Mapping), f"{name} post-topology receipt missing")
            core_post = reported_post.get("core") if isinstance(reported_post.get("core"), Mapping) else reported_post
            _compare_diagnostics(core_post, diag_post, f"{name}.topology_post")
            require(row.get("candidate_raw_sha256") == _raw_identity(candidate_raw), f"{name} candidate raw identity mismatch")
            require(row.get("candidate_raw_metadata") == candidate_meta, f"{name} candidate metadata mismatch")
        receipt = row.get("receipt")
        require(isinstance(receipt, Mapping), f"{name} transition receipt missing")
        require(row.get("receipt_sha256") == receipt.get("self_sha256"), f"{name} transition receipt identity mismatch")
        core = _core_transition_receipt(receipt, name)
        if "runner_committable" in receipt:
            require(receipt.get("runner_committable") is (expected_decision == "PASS"), f"{name} runner decision identity mismatch")
        receipt_values = values if name != "fading-v1-U-topo-zero-comparator" else {key: value for key, value in values.items() if not key.endswith("_sha256")}
        _verify_core_receipt_fields(core, name, expected_decision, _state_hash(predecessor_raw), candidate_raw, diag_pre, diag_post, receipt_values)
        work = row.get("hamiltonian_work")
        require(isinstance(work, Mapping) and isinstance(work.get("current"), (str, int, float)), f"{name} full Hamiltonian work receipt missing")
        require(_close(_number(work.get("pre"), f"{name} work pre"), potential_pre, 1.0e-7), f"{name} Hamiltonian pre mismatch")
        if expected_decision == "PASS":
            require(work.get("post") is not None and diag_post is not None, f"{name} Hamiltonian post missing")
            require(_close(_number(work.get("post"), f"{name} work post"), _number(diag_post.get("potential"), f"{name} post potential"), 1.0e-7), f"{name} Hamiltonian post mismatch")
        else:
            require(work.get("post") is None, f"{name} rejected Hamiltonian work exposed post state")
        if name == "fading-v1-U-topo-zero-comparator":
            require(row.get("mode") == "fading-v1" and row.get("comparator_only") is True and _close(_number(row.get("U_topo"), f"{name} U_topo"), 0.0, 1.0e-12), "fading comparator is not explicit")
        else:
            require(row.get("mode") in {"topological-v1", None}, f"{name} used an unregistered fallback mode")
            require(row.get("comparator_only") is not True, f"{name} was marked comparator-only")
        output[name] = {"pre": predecessor_state, "pre_diag": diag_pre, "pre_raw": predecessor_raw, "candidate_path": candidate_path}
    return output


def _verify_paths(root: Path, candidate: Mapping[str, Any], values: Mapping[str, Any], edges: list[dict[str, Any]], cycle: Mapping[str, Any], layout: Mapping[str, Any]) -> None:
    paths = candidate.get("paths")
    require(isinstance(paths, Mapping) and set(paths) == {"below-barrier-within-sector", "above-barrier-phase-slip"}, "path subdivision set is incomplete")
    radial = _radial(values)
    for path_id, path in paths.items():
        require(isinstance(path, Mapping), f"path object missing: {path_id}")
        _check_self(path, ARTIFACT_DOMAIN + ".path")
        rows = path.get("subdivisions")
        require(isinstance(rows, list) and rows and path.get("subdivision_count") == len(rows) and path.get("positive_duration") is True, f"invalid path subdivisions: {path_id}")
        expected_final = "PASS" if path_id == "below-barrier-within-sector" else "REJECT"
        require(path.get("expected_final_decision") == expected_final, f"path final decision mismatch: {path_id}")
        ledger = path.get("full_work_ledger")
        require(isinstance(ledger, list) and len(ledger) == len(rows), f"full Hamiltonian ledger missing: {path_id}")
        changed_sector = False
        displacements: list[float] = []
        for index, row in enumerate(rows):
            require(isinstance(row, Mapping) and int(row.get("subdivision", -1)) == index and _number(row.get("duration_s"), "path duration") > 0.0, f"invalid path subdivision row: {path_id}/{index}")
            decision = row.get("decision")
            require(decision in {"PASS", "REJECT"}, f"path decision missing: {path_id}/{index}")
            predecessor_relative = row.get("predecessor_raw_path", f"states/paths/{path_id}/{index:04d}.bin")
            require(isinstance(predecessor_relative, str), f"path predecessor raw path malformed: {path_id}/{index}")
            raw_path = _find_raw(root, predecessor_relative)
            raw, meta = _decode(root, raw_path, layout)
            state = _state_fields(raw, meta, layout, values["slow"])
            potential, _, _ = _potential_force(state, values, edges)
            diag = _diagnostics(state, values, edges, cycle, potential)
            _close_value(row.get("topology"), diag, 1.0e-7, f"{path_id}/{index}.topology")
            candidate_relative = row.get("candidate_raw_path")
            candidate_path: Path | None = None
            candidate_raw: bytes | None = None
            diag_post: Mapping[str, Any] | None = None
            if candidate_relative is not None:
                require(isinstance(candidate_relative, str), f"path candidate raw path malformed: {path_id}/{index}")
                candidate_path = _find_raw(root, candidate_relative)
                candidate_raw = candidate_path.read_bytes()
                candidate_values, candidate_meta = _decode(root, candidate_path, layout)
                candidate_state = _state_fields(candidate_values, candidate_meta, layout, values["slow"])
                post_potential, _, _ = _potential_force(candidate_state, values, edges)
                diag_post = _diagnostics(candidate_state, values, edges, cycle, post_potential)
                require(row.get("candidate_raw_sha256") == _raw_identity(candidate_raw), f"path candidate raw identity mismatch: {path_id}/{index}")
                require(row.get("candidate_raw_metadata") == candidate_meta, f"path candidate metadata mismatch: {path_id}/{index}")
                displacements.append(_raw_l2(raw, candidate_raw))
            else:
                require(row.get("candidate_raw_sha256") is None and row.get("candidate_raw_metadata") is None, f"path candidate state identity is incomplete: {path_id}/{index}")
            if decision == "PASS":
                require(candidate_path is not None and candidate_raw is not None and diag_post is not None, f"accepted path subdivision has no candidate state: {path_id}/{index}")
            else:
                require(candidate_path is None and candidate_raw is None and diag_post is None, f"rejected path subdivision exposed a candidate state: {path_id}/{index}")
            receipt = row.get("receipt")
            require(isinstance(receipt, Mapping), f"path receipt missing: {path_id}/{index}")
            if "receipt_sha256" in row:
                require(row.get("receipt_sha256") == receipt.get("self_sha256"), f"path receipt identity mismatch: {path_id}/{index}")
            core = _core_transition_receipt(receipt, f"{path_id}/{index}")
            _verify_core_receipt_fields(core, f"{path_id}/{index}", decision, _state_hash(raw), candidate_raw, diag, diag_post, values)
            if decision == "PASS" and core.get("sector_event") == "phase-slip":
                changed_sector = True
            work = row.get("hamiltonian_work")
            require(isinstance(work, Mapping) and work.get("full_ledger_present") is True and ledger[index] == work, f"path Hamiltonian ledger mismatch: {path_id}/{index}")
            require(_close(_number(work.get("hamiltonian_pre"), "path hamiltonian"), potential, 1.0e-7), f"path Hamiltonian pre mismatch: {path_id}/{index}")
            if decision == "PASS":
                require(diag_post is not None and work.get("hamiltonian_post") is not None and _close(_number(work.get("hamiltonian_post"), "path hamiltonian post"), _number(diag_post.get("potential"), "path post potential"), 1.0e-7), f"path Hamiltonian post mismatch: {path_id}/{index}")
            else:
                require(work.get("hamiltonian_post") is None and work.get("delta_hamiltonian") is None, f"rejected path Hamiltonian work exposed post state: {path_id}/{index}")
            require(row.get("predecessor_raw_sha256") == _raw_identity(raw), f"path raw identity mismatch: {path_id}/{index}")
            if path_id == "below-barrier-within-sector":
                require(decision == "PASS", "within-sector path contains a rejected subdivision")
            elif decision == "REJECT":
                changed_sector = True
        require(path.get("barrier_relation") == ("within-sector-below-barrier" if path_id == "below-barrier-within-sector" else "phase-slip-above-barrier"), f"path barrier relation mismatch: {path_id}")
        symplectic = path.get("symplectic_raw_evidence")
        refinement = path.get("refinement_raw_evidence")
        require(isinstance(symplectic, Mapping) and symplectic.get("independently_measured") is True, f"path symplectic evidence missing: {path_id}")
        require(isinstance(refinement, Mapping) and refinement.get("independently_measured") is True, f"path refinement evidence missing: {path_id}")
        _check_self(symplectic, ARTIFACT_DOMAIN + ".symplectic")
        _check_self(refinement, ARTIFACT_DOMAIN + ".refinement")
        pairs = symplectic.get("pairs")
        require(isinstance(pairs, list) and symplectic.get("pair_count") == len(pairs), f"path tangent-pair ledger incomplete: {path_id}")
        for pair in pairs:
            require(isinstance(pair, Mapping) and _number(pair.get("omega_defect"), f"{path_id} omega defect") >= 0.0, f"path tangent-pair defect invalid: {path_id}")
        require(refinement.get("subdivision_count") == len(rows) and refinement.get("durations_s") == [row.get("duration_s") for row in rows], f"path refinement duration ledger mismatch: {path_id}")
        observed_displacements = refinement.get("state_displacement_norms")
        require(isinstance(observed_displacements, list) and len(observed_displacements) == len(displacements) and all(_close(_number(observed, f"{path_id} displacement"), expected, 1.0e-7) for observed, expected in zip(observed_displacements, displacements)), f"path raw displacement ledger mismatch: {path_id}")
        require(_close(_number(refinement.get("max_displacement_norm"), f"{path_id} max displacement"), max(displacements, default=0.0), 1.0e-7), f"path max displacement mismatch: {path_id}")
        require(_close(_number(refinement.get("interval_radius"), f"{path_id} interval radius"), max(displacements, default=0.0) * math.ulp(1.0), 1.0e-7), f"path interval radius mismatch: {path_id}")
        require(rows[-1].get("decision") == expected_final, f"path final decision mismatch: {path_id}")
        if path_id == "below-barrier-within-sector":
            require(not changed_sector, "within-sector path inferred a sector transition")
        else:
            require(changed_sector, "phase-slip path has no explicit sector/rejection event")
        require(radial["barrier_upper"] > 0.0, "path barrier upper bound is not positive")


def _verify_force_and_barrier(root: Path, candidate: Mapping[str, Any], controls: Mapping[str, Any], values: Mapping[str, Any], edges: list[dict[str, Any]], cycle: Mapping[str, Any], layout: Mapping[str, Any]) -> None:
    force = candidate.get("force_evidence")
    barriers = candidate.get("barrier_evidence")
    require(isinstance(force, Mapping) and isinstance(barriers, Mapping), "force/barrier evidence missing")
    for name in ("uniform-zero-sector", "valid-cycle-positive", "valid-cycle-negative", "vortex-antivortex-plaquette"):
        row = controls[name]
        state = row["pre"]
        potential, fd, fc = _potential_force(state, values, edges)
        evidence = force.get(name)
        require(isinstance(evidence, Mapping), f"force evidence missing: {name}")
        analytic = evidence.get("analytic_or_core")
        require(isinstance(analytic, Mapping) and evidence.get("analytic_source") not in {None, "", "unavailable"}, f"analytic metric force missing: {name}")
        require(any(key in analytic for key in ("D", "d")) and any(key in analytic for key in ("C", "c")), f"{name} analytic force components missing")
        if isinstance(analytic, Mapping):
            for key, expected in (("D", fd), ("d", fd), ("C", fc), ("c", fc)):
                if key not in analytic:
                    continue
                actual_force = analytic[key]
                if isinstance(actual_force, list) and actual_force and isinstance(actual_force[0], list):
                    require(len(actual_force) == int(layout["scale_count"]), f"{name}.force.{key} scale ledger mismatch")
                    actual_force = actual_force[int(values["slow"])]
                if isinstance(actual_force, list):
                    actual_force = [
                        [cell[0] if isinstance(cell, list) and len(cell) == int(layout["batch_count"]) == 1 else cell for cell in row]
                        if isinstance(row, list) else row
                        for row in actual_force
                    ]
                _close_value(actual_force, expected, 1.0e-6, f"{name}.force.{key}")
        probe = evidence.get("metric_gradient_probe")
        require(isinstance(probe, Mapping) and _number(probe.get("step"), "force probe step") > 0.0 and math.isfinite(_number(probe.get("force"), "force probe")), f"force probe missing: {name}")
        barrier = barriers.get(name)
        require(isinstance(barrier, Mapping), f"barrier evidence missing: {name}")
        require(_close(_number(barrier.get("energy"), "barrier energy"), potential, 1.0e-7), f"barrier energy mismatch: {name}")
        radial = _radial(values)
        radial_interval = barrier.get("radial_curvature_interval")
        require(isinstance(radial_interval, Mapping) and _close(_number(radial_interval.get("lower"), "radial interval lower"), values["radial_min"], 1.0e-7) and _number(radial_interval.get("upper"), "radial interval upper") >= _number(radial_interval.get("lower"), "radial interval lower"), f"radial evidence mismatch: {name}")
        require(_close(_number(barrier.get("radial_curvature_lower"), "radial lower"), values["radial_min"], 1.0e-7), f"radial evidence mismatch: {name}")
        barrier_interval = barrier.get("barrier_interval")
        require(isinstance(barrier_interval, Mapping) and _close(_number(barrier_interval.get("lower"), "barrier interval lower"), values["delta_h"], 1.0e-7) and _number(barrier_interval.get("upper"), "barrier interval upper") >= _number(barrier_interval.get("lower"), "barrier interval lower"), f"barrier interval mismatch: {name}")
        require(_close(_number(barrier.get("barrier_lower"), "barrier lower"), values["delta_h"], 1.0e-7), f"barrier lower mismatch: {name}")
        require(_close(_number(barrier.get("within_barrier_margin"), "within barrier margin"), potential - values["delta_h"], 1.0e-7), f"barrier margin mismatch: {name}")
        margin = barrier.get("topology_margin")
        require(isinstance(margin, Mapping) and _close(_number(margin.get("amplitude_floor"), "amplitude margin"), controls[name]["pre_diag"]["amplitude_margin"], 1.0e-7) and _close(_number(margin.get("branch"), "branch margin"), controls[name]["pre_diag"].get("branch_margin_min", 0.0), 1.0e-7) and _close(_number(margin.get("integer"), "integer margin"), controls[name]["pre_diag"].get("integer_margin_min", 0.0), 1.0e-7), f"topology barrier margins mismatch: {name}")


def _verify_reset(root: Path, candidate: Mapping[str, Any], profile: Mapping[str, Any], values: Mapping[str, Any], edges: list[dict[str, Any]], cycle: Mapping[str, Any], layout: Mapping[str, Any]) -> None:
    reset = candidate.get("reset")
    require(isinstance(reset, Mapping), "reset receipt missing")
    _check_self(reset, RECEIPT_DOMAIN + ".reset")
    before_relative = reset.get("predecessor_raw_path", "states/reset/predecessor.bin")
    after_relative = reset.get("candidate_raw_path", "states/reset/candidate.bin")
    require(isinstance(before_relative, str) and isinstance(after_relative, str), "reset raw paths are not declared")
    before_path = _find_raw(root, before_relative)
    after_path = _find_raw(root, after_relative)
    before_raw, before_meta = _decode(root, before_path, layout)
    after_raw, after_meta = _decode(root, after_path, layout)
    require(reset.get("predecessor_raw_sha256") == _raw_identity(before_raw) and reset.get("candidate_raw_sha256") == _raw_identity(after_raw), "reset raw identity mismatch")
    require(reset.get("predecessor_raw_metadata") == before_meta and reset.get("candidate_raw_metadata") == after_meta, "reset raw metadata mismatch")
    before = _state_fields(before_raw, before_meta, layout, values["slow"])
    after = _state_fields(after_raw, after_meta, layout, values["slow"])
    psi0, chi0, vpsi0, vchi0 = _psi_chi(before, values)
    psi1, chi1, vpsi1, vchi1 = _psi_chi(after, values)
    potential0, _, _ = _potential_force(before, values, edges)
    potential1, _, _ = _potential_force(after, values, edges)
    diagnostics0 = _diagnostics(before, values, edges, cycle, potential0)
    diagnostics1 = _diagnostics(after, values, edges, cycle, potential1)
    _close_value(reset.get("pre_diagnostics"), diagnostics0, 1.0e-7, "reset.pre_diagnostics")
    _close_value(reset.get("post_diagnostics"), diagnostics1, 1.0e-7, "reset.post_diagnostics")
    require(reset.get("chi_pre_sha256") == _complex_hash(chi0) and reset.get("chi_post_sha256") == _complex_hash(chi1), "reset chi identity mismatch")
    require(reset.get("Vchi_pre_sha256") == _complex_hash(vchi0) and reset.get("Vchi_post_sha256") == _complex_hash(vchi1), "reset Vchi identity mismatch")
    for y in range(values["shape"][0]):
        for x in range(values["shape"][1]):
            require(_close(abs(psi1[y][x]), values["rho_ring"], 1.0e-7) and _close(psi1[y][x].real, values["rho_ring"], 1.0e-7) and _close(psi1[y][x].imag, 0.0, 1.0e-7), "reset target is not rho_ring exp(i theta_0)")
            require(abs(vpsi1[y][x]) <= 1.0e-7, "reset did not zero V_psi")
            require(_close(chi1[y][x].real, chi0[y][x].real, 1.0e-7) and _close(chi1[y][x].imag, chi0[y][x].imag, 1.0e-7), "reset changed chi")
            require(_close(vchi1[y][x].real, vchi0[y][x].real, 1.0e-7) and _close(vchi1[y][x].imag, vchi0[y][x].imag, 1.0e-7), "reset changed Vchi")
    require(reset.get("operator") and reset.get("preserves") == ["chi", "Vchi"], "reset operator receipt incomplete")
    authorization = reset.get("authorization")
    require(isinstance(authorization, Mapping) and authorization.get("authorized") is True and isinstance(authorization.get("reason"), str) and bool(authorization["reason"].strip()), "reset authorization is incomplete")
    predecessor_state_sha = _state_hash(before_raw)
    require(authorization.get("predecessor_state_sha256") == predecessor_state_sha, "reset authorization is bound to the wrong predecessor")
    require(reset.get("authorization_sha256") == _hash(authorization, "cassi.qi-flow-w4r-reset-authorization.v1"), "reset authorization identity mismatch")
    core_receipt = reset.get("core_receipt")
    require(isinstance(core_receipt, Mapping), "reset lacks authenticated core receipt")
    if core_receipt.get("schema") == "cassi.qi-flow-w4r-retention-core-reset-receipt.v1":
        _check_self(core_receipt, RECEIPT_DOMAIN + ".reset")
        nested_core = core_receipt.get("core_receipt")
        require(isinstance(nested_core, Mapping), "nested reset core receipt missing")
        if core_receipt.get("core_receipt_sha256") is not None:
            require(core_receipt.get("core_receipt_sha256") == nested_core.get("self_sha256"), "nested reset core identity mismatch")
        core_receipt = nested_core
    core_receipt = _core_receipt_payload(core_receipt)
    for key in ("profile_sha256", "root_sha256", "topology_codebook_sha256", "barrier_certificate_sha256", "reset_operator_sha256", "g3n_certificate_sha256"):
        if values.get(key) is not None:
            require(core_receipt.get(key) == values[key], f"reset core {key} identity mismatch")
    require(core_receipt.get("schema") == CORE_RECEIPT_SCHEMA, "reset core receipt schema mismatch")
    _check_self(core_receipt, CORE_RECEIPT_DOMAIN)
    require(core_receipt.get("status") == "PASS" and core_receipt.get("committable") is True and core_receipt.get("transition_kind") == "retention_reset" and core_receipt.get("sector_event") == "reset", "reset core receipt is not an authenticated reset transition")
    require(core_receipt.get("predecessor_state_sha256") == predecessor_state_sha, "reset core receipt predecessor mismatch")
    require(core_receipt.get("candidate_state_sha256") == _state_hash(after_raw), "reset core receipt candidate mismatch")
    require(core_receipt.get("reset_authorization_sha256") == reset.get("authorization_sha256"), "reset core authorization identity mismatch")
    require(core_receipt.get("pre_sector_vector") == diagnostics0.get("sector_vector") and core_receipt.get("post_sector_vector") == diagnostics1.get("sector_vector"), "reset core sector identity mismatch")
    require(_close(_number(core_receipt.get("pre_potential"), "reset core pre potential"), potential0, 1.0e-7) and _close(_number(core_receipt.get("post_potential"), "reset core post potential"), potential1, 1.0e-7) and _close(_number(core_receipt.get("delta_potential"), "reset core delta"), potential1 - potential0, 1.0e-7), "reset core potential identity mismatch")
    reset_bounds = core_receipt.get("barrier_bounds")
    reset_curvature = core_receipt.get("radial_curvature")
    radial = _radial(values)
    require(isinstance(reset_bounds, Mapping) and _close(_number(reset_bounds.get("lower"), "reset barrier lower"), values["delta_h"], 1.0e-7) and _close(_number(reset_bounds.get("upper"), "reset barrier upper"), radial["barrier_upper"], 1.0e-7), "reset core barrier identity mismatch")
    require(isinstance(reset_curvature, Mapping) and _close(_number(reset_curvature.get("value"), "reset radial curvature"), radial["value"], 1.0e-7) and reset_curvature.get("valid") is True, "reset core curvature identity mismatch")
    carrier = core_receipt.get("carrier_split_receipt")
    require(carrier is None or (isinstance(carrier, Mapping) and isinstance(carrier.get("self_sha256"), str) and len(carrier["self_sha256"]) == 64 and carrier.get("committable") is True), "reset core carrier receipt is malformed")
    if carrier is not None:
        require(carrier.get("schema") == "cassi.qi-flow-carrier-receipt.v1", "reset core carrier schema mismatch")
        _check_self(carrier, "cassi.qi-flow-w4-carrier-receipt.v1")


def verify(root: Path) -> dict[str, Any]:
    run_root = _resolve_root(root)
    index = _load(run_root / "index.json")
    require(index.get("schema") == INDEX_SCHEMA and index.get("domain") == ARTIFACT_DOMAIN and index.get("status") == "PASS_W4R_G4R" and index.get("gate") == "G4R", "wrong W4R retention-core index")
    require(run_root.name == index.get("run_id"), "run id is not content-addressed by the directory")
    _check_self(index, INDEX_SCHEMA)
    _source_exact(run_root)
    _verify_manifest(run_root, index)
    _verify_all_self_hashes(run_root)
    parents = _discover_parents()
    parent = _verify_ancestry(run_root, parents)
    profile_obj = _load(run_root / "profiles/retention-profile.json")
    profile_root = _load(run_root / "profiles/retention-root.json")
    require(profile_root.get("schema") == "cassi.qi-flow-w4r-topology-root.v1", "wrong retention profile root schema")
    _check_self(profile_root, PROFILE_ROOT_DOMAIN)
    require(profile_obj.get("schema") == "cassi.qi-flow-w4r-topology-profile.v1" and profile_obj.get("landing_schema") == "cassi.qi-flow-w4r-topology-profile.v1", "wrong retention profile schema")
    profile = _unwrap_profile(profile_obj)
    require(isinstance(profile.get("profile_sha256"), str) and len(profile["profile_sha256"]) == 64 and profile["profile_sha256"] == _hash(_without(profile, "profile_sha256"), PROFILE_DOMAIN), "retention payload profile identity mismatch")
    profile_sha = profile_obj.get("profile_sha256", profile.get("profile_sha256"))
    require(isinstance(profile_sha, str) and profile_sha == profile.get("profile_sha256") and profile_sha == _hash(_without(profile, "profile_sha256"), PROFILE_DOMAIN), "retention profile identity mismatch")
    require(profile_obj.get("root_sha256", profile_obj.get("profile_root_sha256")) == profile_root.get("self_sha256") and profile_root.get("profile_sha256") == profile_sha, "retention root/profile mismatch")
    layout = _layout(run_root)
    require(profile_obj.get("batch_count") == layout["batch_count"] and profile_obj.get("control_batch_lanes") == layout["batch_count"], "profile-declared control batch count disagrees with state layout")
    require(_unwrap_profile(profile_obj).get("active_shapes_yx") == layout["active_shapes"], "profile active shape registry disagrees with state layout")
    values = _profile_values(profile_obj, layout)
    require(list(values["shape"]) == list(_load(run_root / "certificate/retention-derivation.json").get("slow_sheet_shape", [])), "slow sheet identity mismatch")
    edges, cycle, edge_weight_sum, edge_sha, cycle_sha = _registries(values)
    ret = values["retention"]
    require(ret.get("topology_codebook_sha256") not in {None, ""} and ret.get("barrier_certificate_sha256") not in {None, ""} and ret.get("reset_operator_sha256") not in {None, ""}, "missing codebook/barrier/reset profile identities")
    values.update({
        "profile_sha256": profile_sha,
        "root_sha256": profile_root.get("self_sha256"),
        "topology_codebook_sha256": ret.get("topology_codebook_sha256"),
        "barrier_certificate_sha256": ret.get("barrier_certificate_sha256"),
        "reset_operator_sha256": ret.get("reset_operator_sha256"),
        "g3n_certificate_sha256": parents["w3n_certificate"].get("self_sha256"),
    })
    derived = _verify_derived(run_root, profile_obj, values, edges, cycle, edge_sha, cycle_sha)
    candidate = _load(run_root / f"{GATE_DIR}/retention-core.json")
    status = _load(run_root / f"{GATE_DIR}/status.json")
    gate_receipt = _load(run_root / f"{GATE_DIR}/gate-receipt.json")
    _check_self(candidate, CANDIDATE_SCHEMA)
    _check_self(status, STATUS_SCHEMA)
    _check_self(gate_receipt, ARTIFACT_DOMAIN + ".gate-receipt")
    require(candidate.get("schema") == CANDIDATE_SCHEMA and candidate.get("domain") == ARTIFACT_DOMAIN and candidate.get("status") == "PASS_W4R_G4R", "wrong W4R retention-core candidate")
    require(status.get("schema") == STATUS_SCHEMA and status.get("status") == "PASS_W4R_G4R" and status.get("gate") == "G4R", "wrong W4R G4R status")
    require(gate_receipt.get("schema") == ARTIFACT_DOMAIN + "-gate-receipt.v1" and gate_receipt.get("domain") == ARTIFACT_DOMAIN, "wrong W4R gate receipt")
    no_state = candidate.get("no_added_state")
    require(isinstance(no_state, Mapping) and no_state.get("additional_state") is False and no_state.get("state_layout") == "[S,9M,B]" and no_state.get("self_sha256") == gate_receipt.get("no_added_state_sha256"), "no-added-state receipt is missing or unauthenticated")
    _check_self(no_state, ARTIFACT_DOMAIN + ".no-added-state")
    require(status.get("status") == "PASS_W4R_G4R" and status.get("gate_receipt_sha256") == gate_receipt.get("self_sha256"), "status/gate receipt mismatch")
    expected_conditions = {"exactly_one_source_exact_w4_parent", "current_w3n_ancestry_transitively_bound", "topological_retention_law_capability", "topological_v1_extension_frozen", "fading_v1_explicit_comparator_only", "raw_state_layout_declared", "positive_duration_subdivisions", "raw_symplectic_tangent_pairs", "full_work_ledger", "rejection_controls", "reset_authenticated_and_preserves_chi_vchi", "no_added_state", "pre_behavioral_core_only"}
    require(set(status.get("conditions", {})) == expected_conditions and all(value is True for value in status["conditions"].values()), "not every G4R condition passed")
    require(gate_receipt.get("status") == "PASS_W4R_G4R" and gate_receipt.get("gate") == "G4R" and gate_receipt.get("parent") == parent and gate_receipt.get("profile_sha256") == profile_sha and gate_receipt.get("extension_sha256") == derived["extension"].get("self_sha256") and gate_receipt.get("controls") == EXPECTED_CONTROLS, "gate receipt identity or controls mismatch")
    controls = _verify_controls(run_root, candidate, profile_obj, values, edges, cycle, layout)
    _verify_force_and_barrier(run_root, candidate, controls, values, edges, cycle, layout)
    _verify_paths(run_root, candidate, values, edges, cycle, layout)
    _verify_reset(run_root, candidate, profile_obj, values, edges, cycle, layout)
    conversion = candidate.get("conversion_path")
    require(isinstance(conversion, Mapping), "conversion path missing")
    _check_self(conversion, ARTIFACT_DOMAIN + ".conversion-path")
    require(conversion.get("from") == "W4-carrier" and conversion.get("to") == "W4R-topological-retention-core" and conversion.get("behavioral_retention_claim") is False, "conversion path is not pre-behavioral W4R")
    phase_match = candidate.get("phase_scrambled_equal_energy")
    require(isinstance(phase_match, Mapping) and phase_match.get("method") == "profile/core-energy-bisection.v1" and _number(phase_match.get("absolute_error"), "phase-scrambled energy error") <= _number(phase_match.get("tolerance"), "phase-scrambled energy tolerance"), "phase-scrambled equal-energy control failed")
    matched = candidate.get("matched_energy")
    require(isinstance(matched, Mapping) and _close(_number(matched.get("positive"), "matched positive energy"), _number(controls["matched-energy-positive-current"]["pre_diag"].get("potential"), "matched positive control energy"), 1.0e-7), "matched positive energy evidence missing")
    require(_close(_number(matched.get("negative"), "matched negative energy"), _number(controls["matched-energy-negative-current"]["pre_diag"].get("potential"), "matched negative control energy"), 1.0e-7), "matched negative energy evidence missing")
    require(matched.get("opposite_current") is True and _number(matched.get("absolute_error"), "matched energy error") <= 1.0e-7, "matched-energy/opposite-current control failed")
    require(index.get("parent") == parent and index.get("source_exact_successor_of") == parent, "index parent lineage mismatch")
    return {"status": "PASS", "schema": INDEX_SCHEMA, "run_id": index["run_id"], "parent_w4_run_id": parent["w4_run_id"], "parent_w3n_run_id": parent["w3n_run_id"], "profile_sha256": profile_sha, "edge_weight_sum": edge_weight_sum, "edge_count": len(edges), "slow_sheet_shape": list(values["shape"]), "controls": sorted(EXPECTED_CONTROLS)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify(args.root)
    except Exception as exc:
        print(f"W4R/G4R FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
