"""Materialize immutable W5V/G5V complete-domain viability evidence.

The W5 predecessor is deliberately an engineering artifact: it must contain an
explicit null W5V marker.  This driver binds that source-exact frozen-Q artifact
to the complete-domain proof in :mod:`cassi_qi_conversion_viability`; it never
infers a viability certificate from W5 fixtures or from a passing engineering
receipt.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import hashlib
import math
import shutil
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from cassi_qi_conversion import (
    _energy_components,
    _frozen_q_map,
    _update_ema_once,
    derive_epsilon_tau,
    load_w5_conversion_profile,
    transition_w5_integrated,
)
from cassi_qi_conversion_viability import (
    ConversionViabilityError,
    W5V_EXTENSION_DOMAIN,
    W5V_EXTENSION_SCHEMA,
    W5V_PROFILE_DOMAIN,
    W5V_RECEIPT_DOMAIN,
    build_w5v_extension,
    build_w5v_receipt,
    certify_w5v,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_numerical_certificate import raw_state_bytes_from_field
from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads, finite_float
from cassi_qi_carrier import load_w4_carrier_profile
from cassi_qi_topology import load_w4r_topology_profile
from cassi_qi_transport import load_w3_transport_profile
from verify_cassi_qi_conversion_viability import build_embedded_independent_result
from verify_cassi_qi_conversion import verify as verify_w5
from verify_cassi_qi_topology import verify as verify_w4r

PARENT_VERIFICATION_SCHEMA = "cassi.qi-flow-parent-verification.v1"
PARENT_VERIFIER_RECEIPTS_SCHEMA = "cassi.qi-flow-parent-verifier-receipts.v1"
W4R_VERIFY_SCHEMA = "cassi.qi-flow-w4r-retention-core-run-index.v1"
W5_VERIFY_SCHEMA = "cassi.qi-flow-w5-run-index.v1"

ROOT = Path(__file__).resolve().parent
W5_ARTIFACT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w5-frozen-q-final"
OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w5v-conversion-viability-final"

INDEX_SCHEMA = "cassi.qi-flow-w5v-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w5v-artifact.v1"
STATUS_SCHEMA = "cassi.qi-flow-g5v-status.v1"
STATUS_DOMAIN = STATUS_SCHEMA
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w5v-source-identity.v1"
SOURCE_IDENTITY_DOMAIN = SOURCE_IDENTITY_SCHEMA
PARENT_BINDING_SCHEMA = "cassi.qi-flow-w5v-parent-binding.v1"
G5_CONTROL_LAW_SCHEMA = "cassi.qi-flow-w5v-control-law-observations.v1"
G5_CONTROL_LAW_DOMAIN = G5_CONTROL_LAW_SCHEMA
G5_CONTROL_INPUT_SCHEMA = "cassi.qi-flow-w5v-control-law-input.v1"
G5_CONTROL_INPUT_DOMAIN = G5_CONTROL_INPUT_SCHEMA
G5_CONTROL_RESULT_SCHEMA = "cassi.qi-flow-w5v-control-law-result.v1"
G5_CONTROL_RESULT_DOMAIN = G5_CONTROL_RESULT_SCHEMA
PARENT_BINDING_DOMAIN = PARENT_BINDING_SCHEMA
WITNESS_MANIFEST_SCHEMA = "cassi.qi-flow-w5v-witness-manifest.v1"
WITNESS_MANIFEST_DOMAIN = WITNESS_MANIFEST_SCHEMA
RAW_DOMAIN = "cassi.qi-flow-w5-raw-state.v1"
RAW_ACTIVITY_SCHEMA = "cassi.qi-flow-w5v-raw-activity.v1"
RAW_ACTIVITY_DOMAIN = RAW_ACTIVITY_SCHEMA
WORK_OBSERVATION_SCHEMA = "cassi.qi-flow-w5v-raw-work-observation.v1"
WORK_OBSERVATION_DOMAIN = WORK_OBSERVATION_SCHEMA
MUTATION_OBSERVATION_SCHEMA = "cassi.qi-flow-w5v-mutation-observations.v1"
MUTATION_OBSERVATION_DOMAIN = MUTATION_OBSERVATION_SCHEMA
MUTATION_CONTROL_SCHEMA = "cassi.qi-flow-w5v-mutation-control.v1"
MUTATION_CONTROL_DOMAIN = MUTATION_CONTROL_SCHEMA
INDEPENDENT_INPUT_SCHEMA = "cassi.qi-flow-w5v-independent-verifier-input.v1"
INDEPENDENT_INPUT_DOMAIN = INDEPENDENT_INPUT_SCHEMA

W5_INDEX_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
W5_ARTIFACT_DOMAIN = "cassi.qi-flow-w5-frozen-q-artifact.v1"
W5_PROFILE_DOMAIN = "cassi.qi-flow-conversion-profile.v1"
W5_ROOT_DOMAIN = "cassi.qi-flow-w5-conversion-root.v1"
W5_LAW_DOMAIN = "cassi.qi-flow-frozen-q-map.v1"
W5_CANDIDATE_DOMAIN = "cassi.qi-flow-w5-conversion-candidate.v1"
W5_STATUS_DOMAIN = "cassi.qi-flow-g5-status.v1"
W5_SOURCE_IDENTITY_DOMAIN = "cassi.qi-flow-w5-conversion-source-identity.v1"

# These are the files which determine this artifact's proof, serialization, and
# independently executable verification.  The W5 runtime has its own immutable
# source inventory; this artifact validates and binds that inventory separately.
SOURCE_PATHS = (
    "cassi_qi_conversion.py",
    "run_cassi_qi_conversion.py",
    "verify_cassi_qi_conversion.py",
    "test_cassi_qi_conversion.py",
    "cassi_qi_numerical_certificate.py",
    "cassi_qi_field.py",
    "cassi_qi_geometry.py",
    "cassi_qi_transport.py",
    "cassi_qi_carrier.py",
    "cassi_qi_topology.py",
    "verify_cassi_qi_topology.py",
    "cassi_qi_profile.py",
    "cassi_qi_conversion_viability.py",
    "run_cassi_qi_conversion_viability.py",
    "verify_cassi_qi_conversion_viability.py",
    "test_cassi_qi_conversion_viability.py",
)

W5_MEASUREMENTS_DOMAIN = "cassi.qi-flow-w5-conversion-measurements.v1"


# These source-exact controls are the closed W5 witness inventory.  They only
# classify raw endpoints into already-registered analytic cells; they never
# define support, choose a coefficient, or determine the G5V verdict.
WITNESS_CELL_REGISTRATION: Mapping[str, tuple[str, ...]] = {
    "empty": ("C00-exact-zero",),
    "balanced": ("C01-balanced-memory-zero",),
    "heterogeneous": ("C02-balanced-memory-positive",),
    "yang-heavy": ("C03-neutral-positive",),
    "yin-heavy": ("C04-neutral-negative",),
    "matched-energy-positive-imbalance": ("C05-progress-positive",),
    "matched-energy-negative-imbalance": ("C06-progress-negative",),
}


class ViabilityArtifactError(ValueError):
    """A predecessor, source snapshot, or immutable W5V artifact is invalid."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _raw_hash(raw: bytes) -> str:
    domain = RAW_DOMAIN.encode("utf-8")
    return _sha(len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ViabilityArtifactError(message)
def _portable_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()

def _normalise_verifier_result(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalise_verifier_result(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise_verifier_result(item) for item in value]
    if isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        _require(math.isfinite(value), "parent verifier returned a non-finite float")
        _require(not (value == 0.0 and math.copysign(1.0, value) < 0.0), "parent verifier returned negative zero")
        return "f64:" + struct.pack(">d", value).hex()
    if value is None or isinstance(value, str):
        return value
    raise ViabilityArtifactError(f"unsupported parent verifier result value: {type(value).__name__}")



def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = canonical_json_loads(path.read_bytes())
    except Exception as exc:  # canonical parser reports duplicate keys and constants
        raise ViabilityArtifactError(f"invalid canonical JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ViabilityArtifactError(f"canonical object required: {path}")
    return value


def _write(stage: Path, relative: str, raw: bytes) -> None:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _write_json(stage: Path, relative: str, value: Any) -> None:
    _write(stage, relative, canonical_json_bytes(value))


def _records(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "byte_count": len(raw := path.read_bytes()),
            "sha256": _sha(raw),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "index.json"
    ]


def _copy_sources(stage: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        _require(source.is_file(), f"missing W5V decision-bearing source: {relative}")
        raw = source.read_bytes()
        _write(stage, f"sources/{relative}", raw)
        records.append({"path": relative, "byte_count": len(raw), "sha256": _sha(raw)})
    return records


def _check_self_hash(payload: Mapping[str, Any], domain: str, label: str) -> None:
    body = dict(payload)
    claimed = body.pop("self_sha256", None)
    _require(_is_sha256(claimed), f"{label} has no SHA-256 self identity")
    _require(claimed == canonical_hash(body, domain), f"{label} self identity mismatch")


def _check_object_records(root: Path, index: Mapping[str, Any], *, label: str) -> None:
    records = index.get("objects")
    _require(isinstance(records, list), f"{label} object inventory is not a list")
    expected = _records(root)
    _require(records == expected, f"{label} object inventory is incomplete, reordered, or mutated")

def _check_source_identity(
    root: Path,
    *,
    relative: str,
    domain: str,
    label: str,
    expected_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    identity = _read_json(root / relative)
    _check_self_hash(identity, domain, label)
    records = identity.get("sources")
    _require(isinstance(records, list) and records, f"{label} sources are not a list")
    if expected_paths is None:
        expected_paths = tuple(row.get("path") for row in records if isinstance(row, dict))
    expected = list(expected_paths)
    _require([row.get("path") for row in records if isinstance(row, dict)] == expected, f"{label} source order or inventory drifted")
    _require(len(records) == len(expected) == len(set(expected)), f"{label} source inventory contains duplicate rows")
    actual_paths = [path.relative_to(root / "sources").as_posix() for path in sorted((root / "sources").rglob("*")) if path.is_file()]
    _require(actual_paths == sorted(expected), f"{label} source snapshot tree drifted")
    for record in records:
        _require(isinstance(record, dict) and set(record) == {"path", "byte_count", "sha256"}, f"{label} source record schema mismatch")
        path = record["path"]
        _require(isinstance(path, str) and path in expected and not Path(path).is_absolute() and ".." not in Path(path).parts, f"{label} source path invalid")
        raw = (root / "sources" / path).read_bytes()
        _require(record["byte_count"] == len(raw) and record["sha256"] == _sha(raw), f"{label} source snapshot hash mismatch: {path}")
    return identity


def _w5_parent_material(index: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact identity payload used by the current W5 runner."""
    return {
        key: value
        for key, value in index.items()
        if key not in {"run_id", "self_sha256"}
    }


def _check_w5_parent_index(root: Path) -> tuple[dict[str, Any], bytes]:
    index_path = root / "index.json"
    raw = index_path.read_bytes()
    index = _read_json(index_path)
    _require(index.get("schema") == W5_INDEX_SCHEMA, "W5 predecessor index schema mismatch")
    _check_self_hash(index, W5_ARTIFACT_DOMAIN, "W5 predecessor index")
    _require(index.get("status") == "PASS_W5_G5", "W5 engineering predecessor is not PASS_W5_G5")
    _require(index.get("engineering_candidate_only") is True, "W5 predecessor is not explicitly engineering-only")
    _require(index.get("w5v_forward_domain_certificate") is None, "W5 predecessor falsely embeds W5V certification")
    for field in ("run_id", "profile_sha256", "root_sha256", "law_sha256"):
        _require(_is_sha256(index.get(field)), f"W5 predecessor {field} is not a SHA-256 identity")
    _require(index["run_id"] == canonical_hash(_w5_parent_material(index), W5_ARTIFACT_DOMAIN), "W5 predecessor run identity mismatch")
    if "object_count" in index:
        _require(index["object_count"] == len(index.get("objects", [])), "W5 predecessor object count mismatch")
    _check_object_records(root, index, label="W5 predecessor")
    _require(isinstance(index.get("parents"), list) and len(index["parents"]) == 1, "W5 predecessor parent inventory mismatch")
    _require(index["source_exact_successor_of"] == index["parents"][0], "W5 predecessor source-exact parent linkage mismatch")
    return index, raw


def _check_w5_conversion_objects(root: Path, index: Mapping[str, Any]) -> dict[str, Any]:
    profile = _read_json(root / "profile" / "conversion-profile.json")
    conversion_root = _read_json(root / "profile" / "conversion-root.json")
    law = _read_json(root / "profile" / "conversion-law.json")
    candidate_path = root / "gates" / "g05-conversion" / "candidate.json"
    _require(candidate_path.is_file(), "W5 conversion candidate.json is missing")
    candidate = _read_json(candidate_path)
    status = _read_json(root / "gates" / "g05-conversion" / "status.json")
    measurements = _read_json(root / "gates" / "g05-conversion" / "measurements.json")
    certificate = _read_json(root / "certificate" / "g3n-certificate-root.json")
    _require(profile.get("schema") == W5_PROFILE_DOMAIN, "W5 conversion profile schema mismatch")
    profile_body = dict(profile)
    profile_identity = profile_body.pop("profile_sha256", None)
    _require(_is_sha256(profile_identity), "W5 conversion profile has no profile identity")
    _require(profile_identity == canonical_hash(profile_body, W5_PROFILE_DOMAIN), "W5 conversion profile identity mismatch")
    _require(profile.get("law_sha256") == canonical_hash(profile.get("law"), W5_LAW_DOMAIN), "W5 frozen-Q law identity mismatch")
    _require(law == profile["law"], "W5 frozen-Q law object does not match its profile")
    _require(conversion_root.get("schema") == W5_ROOT_DOMAIN, "W5 conversion root schema mismatch")
    _check_self_hash(conversion_root, W5_ROOT_DOMAIN, "W5 conversion root")
    _require(conversion_root.get("profile_sha256") == profile_identity, "W5 conversion root/profile linkage mismatch")
    _require(conversion_root.get("law_sha256") == profile["law_sha256"], "W5 conversion root/law linkage mismatch")
    _require(index.get("profile_sha256") == profile_identity, "W5 index/profile linkage mismatch")
    _require(index.get("root_sha256") == conversion_root.get("self_sha256"), "W5 index/root linkage mismatch")
    _require(index.get("law_sha256") == profile.get("law_sha256"), "W5 index/law linkage mismatch")
    _require(candidate.get("schema") == W5_CANDIDATE_DOMAIN, "W5 conversion candidate schema mismatch")
    candidate_identity = candidate.get("self_sha256")
    if candidate_identity is not None:
        _check_self_hash(candidate, W5_CANDIDATE_DOMAIN, "W5 conversion candidate")
    else:
        candidate_identity = canonical_hash(candidate, W5_CANDIDATE_DOMAIN)
    _require(candidate.get("status") == "PASS", "W5 conversion candidate is not PASS")
    _require(candidate.get("candidate_only") is True, "W5 candidate is not explicitly engineering-only")
    _require(candidate.get("extension_added") is False, "W5 candidate incorrectly claims certificate extension")
    _require(candidate.get("w5v_forward_domain_certificate") is None, "W5 candidate falsely embeds W5V certification")
    _require(status.get("schema") == W5_STATUS_DOMAIN, "W5 status schema mismatch")
    _check_self_hash(status, W5_STATUS_DOMAIN, "W5 status")
    _require(status.get("status") == "PASS_W5_G5", "W5 status is not PASS_W5_G5")
    _require(status.get("engineering_candidate_only") is True, "W5 status is not explicitly engineering-only")
    _require(status.get("w5v_forward_domain_certificate") is None, "W5 status falsely embeds W5V certification")
    _require(measurements.get("schema") == W5_MEASUREMENTS_DOMAIN, "W5 measurements schema mismatch")
    _check_self_hash(measurements, W5_MEASUREMENTS_DOMAIN, "W5 measurements")
    _require(measurements.get("w5v_forward_domain_certificate") is None, "W5 measurements falsely embed W5V certification")
    _require(candidate.get("receipt_sha256") == measurements.get("controls", {}).get(candidate.get("control_id"), {}).get("receipt_sha256"), "W5 candidate/measurement linkage mismatch")
    _require(_is_sha256(certificate.get("self_sha256")), "W5 numerical certificate has no identity")
    return {
        "profile": profile,
        "root": conversion_root,
        "law": law,
        "candidate": candidate,
        "candidate_identity": candidate_identity,
        "candidate_path": candidate_path,
        "status": status,
        "measurements": measurements,
        "certificate": certificate,
    }

def _contains_identity(value: Any, identity: str) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_identity(item, identity) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_identity(item, identity) for item in value)
    return value == identity


def _validate_w4r_extension(extension: Mapping[str, Any], conversion_root: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(extension)
    _require(value.get("schema") == W5V_EXTENSION_SCHEMA, "W4R extension schema mismatch")
    _check_self_hash(value, W5V_EXTENSION_DOMAIN, "W4R extension")
    ordinal = value.get("chain_ordinal")
    _require(isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal >= 1, "W4R extension ordinal is invalid")
    inventory = value.get("complete_section_inventory")
    _require(isinstance(inventory, list) and len(inventory) == ordinal, "W4R extension inventory is incomplete")
    _require([row.get("ordinal") for row in inventory if isinstance(row, Mapping)] == list(range(1, ordinal + 1)), "W4R extension inventory is incomplete or reordered")
    return value


def _check_w4r_extension(
    root: Path,
    conversion_root: Mapping[str, Any],
    parent_record: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes, Path]:
    parents = root / "parents"
    candidates: list[Path] = []
    for path in sorted(parents.glob("*.json")):
        try:
            if _read_json(path).get("schema") == W5V_EXTENSION_SCHEMA:
                candidates.append(path)
        except Exception:
            continue
    _require(len(candidates) == 1, "W5 predecessor must expose exactly one current W4R extension")
    path = candidates[0]
    raw = path.read_bytes()
    extension = _validate_w4r_extension(_read_json(path), conversion_root)
    _require(_contains_identity(parent_record, extension["self_sha256"]), "W5 index/current W4R extension linkage mismatch")
    return extension, raw, path

def _check_live_source_exactness(
    root: Path,
    *,
    source_identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    conversion_root: Mapping[str, Any],
) -> dict[str, str]:
    source_rows = source_identity.get("sources")
    _require(isinstance(source_rows, list) and source_rows, "W5 source inventory is empty")
    live_hashes: dict[str, str] = {}
    for row in source_rows:
        _require(isinstance(row, Mapping) and isinstance(row.get("path"), str), "W5 source inventory row is malformed")
        relative = row["path"]
        source = ROOT / relative
        snapshot = root / "sources" / relative
        _require(source.is_file() and snapshot.is_file(), f"live W5 source is missing: {relative}")
        source_raw = source.read_bytes()
        parent_raw = snapshot.read_bytes()
        _require(source_raw == parent_raw, f"live W5 source differs from W5 source snapshot: {relative}; re-materialize W5")
        live_hashes[relative] = _sha(source_raw)
    geometry = load_w2_geometry_profile()
    live = load_w5_conversion_profile(geometry=geometry, parent_identities=profile.get("parent_identities"))
    _require(canonical_json_bytes(dict(live.payload)) == canonical_json_bytes(profile), "live frozen-Q profile differs from W5 source-exact profile")
    _require(canonical_json_bytes(dict(live.root)) == canonical_json_bytes(conversion_root), "live frozen-Q root differs from W5 source-exact root")
    return live_hashes


def _identity_record(value: Mapping[str, Any], *, label: str, relative_path: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {"label": label}
    if relative_path is not None:
        record["artifact_path"] = relative_path
    for key, item in value.items():
        if key == "self_sha256" or key.endswith("_sha256"):
            if item is not None:
                record[key] = item
    if "schema" in value:
        record["schema"] = value["schema"]
    return record


def _validate_identity_record(value: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{label} identity record is malformed")
    for key, item in value.items():
        if key.endswith("_sha256") and item is not None:
            _require(_is_sha256(item), f"{label} identity {key} is not a SHA-256 digest")
    return dict(value)


def _plain_identity_inventory(inventory: Any) -> list[dict[str, Any]]:
    if not isinstance(inventory, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in inventory:
        if isinstance(row, Mapping):
            rows.append(_identity_record(row, label=f"certificate-section-{row.get('ordinal', len(rows) + 1)}"))
    return rows


def _load_w5_predecessor(root: Path) -> dict[str, Any]:
    root = root.resolve()
    _require(root.is_dir(), f"W5 predecessor root does not exist: {root}")
    index, index_raw = _check_w5_parent_index(root)
    source_identity = _check_source_identity(
        root,
        relative="run-spec/source-identity.json",
        domain=W5_SOURCE_IDENTITY_DOMAIN,
        label="W5 source identity",
    )
    objects = _check_w5_conversion_objects(root, index)
    candidate_source_identity = objects["candidate"].get("source_identity_sha256")
    if candidate_source_identity is not None:
        _require(candidate_source_identity == source_identity["self_sha256"], "W5 candidate/source identity linkage mismatch")
    extension, extension_raw, extension_path = _check_w4r_extension(root, objects["root"], index["parents"][0])
    source_hashes = _check_live_source_exactness(
        root,
        source_identity=source_identity,
        profile=objects["profile"],
        conversion_root=objects["root"],
    )
    parent_ids: dict[str, Any] = {
        "w4r_extension": _identity_record(
            extension,
            label="current-W4R-certificate-extension",
            relative_path=extension_path.relative_to(root).as_posix(),
        ),
        "w4r_section_inventory": _plain_identity_inventory(extension.get("complete_section_inventory", [])),
    }
    for ordinal, item in enumerate(index.get("parents", [])):
        if isinstance(item, Mapping):
            parent_ids[f"w4r_parent_{ordinal}"] = _validate_identity_record(item, label=f"W5 parent {ordinal}")
    certificate_ids = {
        "w5_candidate": {
            **_identity_record(objects["candidate"], label="current-W5-candidate", relative_path=objects["candidate_path"].relative_to(root).as_posix()),
            "self_sha256": objects["candidate_identity"],
        },
        "w5_profile": _identity_record(objects["profile"], label="current-W5-profile", relative_path="profile/conversion-profile.json"),
        "w5_root": _identity_record(objects["root"], label="current-W5-conversion-root", relative_path="profile/conversion-root.json"),
        "w5_law": _identity_record(objects["law"], label="current-W5-frozen-Q-law", relative_path="profile/conversion-law.json"),
        "w5_certificate": _identity_record(objects["certificate"], label="current-W5-numerical-certificate", relative_path="certificate/g3n-certificate-root.json"),
    }
    binding = {
        "run_id": index["run_id"],
        "index_sha256": _sha(index_raw),
        "candidate_state_sha256": objects["candidate_identity"],
        "profile_sha256": objects["profile"]["profile_sha256"],
        "root_sha256": objects["root"]["self_sha256"],
        "law_sha256": objects["profile"]["law_sha256"],
        "conversion_source_sha256": source_hashes["cassi_qi_conversion.py"],
        "source_identity_sha256": source_identity["self_sha256"],
        "parent_identities": parent_ids,
        "certificate_identities": certificate_ids,
        "status": "PASS",
        "w5v_forward_domain_certificate": None,
    }
    return {
        "root_path": root,
        "index": index,
        "index_raw": index_raw,
        "profile": objects["profile"],
        "profile_raw": (root / "profile" / "conversion-profile.json").read_bytes(),
        "conversion_root": objects["root"],
        "conversion_root_raw": (root / "profile" / "conversion-root.json").read_bytes(),
        "law": objects["law"],
        "law_raw": (root / "profile" / "conversion-law.json").read_bytes(),
        "candidate": objects["candidate"],
        "candidate_raw": objects["candidate_path"].read_bytes(),
        "status": objects["status"],
        "status_raw": (root / "gates" / "g05-conversion" / "status.json").read_bytes(),
        "measurements": objects["measurements"],
        "measurements_raw": (root / "gates" / "g05-conversion" / "measurements.json").read_bytes(),
        "extension": extension,
        "extension_raw": extension_raw,
        "extension_path": extension_path,
        "certificate": objects["certificate"],
        "certificate_raw": (root / "certificate" / "g3n-certificate-root.json").read_bytes(),
        "w5_source_identity": source_identity,
        "live_source_sha256": source_hashes,
        "binding": binding,
    }

def _discover_current_w5() -> dict[str, Any]:
    """Return the sole source-exact, independently validated W5 artifact."""
    candidates: list[dict[str, Any]] = []
    roots = sorted(path for path in W5_ARTIFACT_ROOT.iterdir() if path.is_dir()) if W5_ARTIFACT_ROOT.is_dir() else []
    failures: list[str] = []
    for root in roots:
        if not (root / "index.json").is_file():
            continue
        try:
            candidates.append(_load_w5_predecessor(root))
        except Exception as exc:
            failures.append(f"{root.name}:{type(exc).__name__}")
    _require(len(candidates) == 1, f"expected exactly one current source-exact W5 artifact, found {len(candidates)} ({', '.join(failures)})")
    return candidates[0]

def _w4r_artifact_candidates() -> list[Path]:
    diag = ROOT / "_diag"
    if not diag.is_dir():
        return []
    candidates: list[Path] = []
    for family in sorted(diag.glob("cassi-qi-flow-w4r*-final")):
        if not family.is_dir():
            continue
        if (family / "index.json").is_file():
            candidates.append(family)
        candidates.extend(
            child
            for child in sorted(family.iterdir())
            if child.is_dir() and (child / "index.json").is_file()
        )
    return candidates


def _discover_w4r_artifact(predecessor: Mapping[str, Any]) -> Path:
    parents = predecessor["index"].get("parents")
    _require(isinstance(parents, list) and len(parents) == 1 and isinstance(parents[0], Mapping), "W5 parent W4R identity is missing")
    expected = parents[0]
    expected_run_id = expected.get("run_id")
    expected_index_sha256 = expected.get("index_sha256")
    matches: list[Path] = []
    for candidate in _w4r_artifact_candidates():
        try:
            raw = (candidate / "index.json").read_bytes()
            index = _read_json(candidate / "index.json")
        except Exception:
            continue
        if expected_run_id is not None and index.get("run_id") != expected_run_id:
            continue
        if expected_index_sha256 is not None and _sha(raw) != expected_index_sha256:
            continue
        matches.append(candidate)
    _require(len(matches) == 1, f"expected exactly one source-exact W4R artifact for W5 parent, found {len(matches)}")
    return matches[0]




def _preverify_w4r_w5(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    """Run upstream verifiers before constructing any W5V evidence."""
    w5_root = Path(predecessor["root_path"]).resolve()
    w4r_root = _discover_w4r_artifact(predecessor)
    try:
        w4r_result = _normalise_verifier_result(verify_w4r(w4r_root))
        w5_result = _normalise_verifier_result(verify_w5(w5_root))
    except Exception as exc:
        raise ViabilityArtifactError(f"upstream independent verification failed: {type(exc).__name__}: {exc}") from exc
    _require(
        isinstance(w4r_result, Mapping)
        and w4r_result.get("schema") == W4R_VERIFY_SCHEMA
        and w4r_result.get("status") == "PASS",
        "W4R independent verifier did not return PASS",
    )
    _require(
        isinstance(w5_result, Mapping)
        and w5_result.get("schema") == W5_VERIFY_SCHEMA
        and w5_result.get("status") == "PASS_W5_G5",
        "W5 independent verifier did not return PASS_W5_G5",
    )
    w5_index_sha256 = _sha((w5_root / "index.json").read_bytes())
    w4r_index_sha256 = _sha((w4r_root / "index.json").read_bytes())
    reported_w4r_index_sha256 = w4r_result.get("index_sha256")
    if reported_w4r_index_sha256 is not None:
        _require(reported_w4r_index_sha256 == w4r_index_sha256, "W4R independent verifier index identity mismatch")
        w4r_index_sha256 = reported_w4r_index_sha256
    _require(
        w5_result.get("index_sha256") == w5_index_sha256 == predecessor["binding"]["index_sha256"],
        "W5 independent verifier index identity mismatch",
    )
    _require(
        w4r_index_sha256 == predecessor["index"]["parents"][0].get("index_sha256"),
        "W4R independent verifier index identity mismatch",
    )
    _require(
        w5_result.get("source_identity_sha256") == predecessor["binding"]["source_identity_sha256"],
        "W5 independent verifier source identity mismatch",
    )
    w4r_receipt = {
        "schema": PARENT_VERIFICATION_SCHEMA,
        "result": dict(w4r_result),
        "verification_sha256": canonical_hash(w4r_result, PARENT_VERIFICATION_SCHEMA),
    }
    w5_receipt = {
        "schema": PARENT_VERIFICATION_SCHEMA,
        "result": dict(w5_result),
        "verification_sha256": canonical_hash(w5_result, PARENT_VERIFICATION_SCHEMA),
    }
    receipts: dict[str, Any] = {
        "schema": PARENT_VERIFIER_RECEIPTS_SCHEMA,
        "w4r": w4r_receipt,
        "w5": w5_receipt,
    }
    expected_w5_parent_receipts = {
        "schema": PARENT_VERIFIER_RECEIPTS_SCHEMA,
        "w4r": w4r_receipt,
    }
    _require(
        w5_result.get("parent_verifier_receipts") == expected_w5_parent_receipts,
        "W5 independent parent verifier receipts mismatch",
    )
    _require(
        w5_result.get("parent_verifier_receipts_sha256")
        == canonical_hash(expected_w5_parent_receipts, PARENT_VERIFIER_RECEIPTS_SCHEMA),
        "W5 independent parent verifier receipts digest mismatch",
    )
    return {
        "receipts": receipts,
        "receipts_sha256": canonical_hash(receipts, PARENT_VERIFIER_RECEIPTS_SCHEMA),
        "w4r_root": w4r_root,
        "w4r_result": w4r_result,
        "w5_result": w5_result,
    }


def _collect_witnesses(predecessor: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[str, bytes]]]:
    root = Path(predecessor["root_path"])
    receipt_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    copies: list[tuple[str, bytes]] = []
    for fixture_id, covered_cells in WITNESS_CELL_REGISTRATION.items():
        control, predecessor_descriptor, predecessor_raw = _load_control_fixture(root, fixture_id, "predecessor")
        _, candidate_descriptor, candidate_raw = _load_control_fixture(root, fixture_id, "candidate")
        _require(control.get("actual_decision") == "PASS" and control.get("committable") is True, f"W5 fixture is not a raw accepted witness: {fixture_id}")
        _require(control.get("predecessor_raw_sha256") == _sha(predecessor_raw), f"W5 predecessor raw hash mismatch: {fixture_id}")
        _require(control.get("candidate_raw_sha256") == _sha(candidate_raw), f"W5 candidate raw hash mismatch: {fixture_id}")
        predecessor_sha256 = _raw_hash(predecessor_raw)
        candidate_sha256 = _raw_hash(candidate_raw)
        witness = {
            "fixture_id": fixture_id,
            "covered_cell_ids": list(covered_cells),
            "predecessor_sha256": predecessor_sha256,
            "candidate_sha256": candidate_sha256,
            "kind": "W5-frozen-Q-raw-control-witness.v1",
        }
        artifact_predecessor = _fixture_artifact_path(predecessor_descriptor, fixture_id=fixture_id, name="predecessor")
        artifact_candidate = _fixture_artifact_path(candidate_descriptor, fixture_id=fixture_id, name="candidate")
        receipt_rows.append(witness)
        manifest_rows.append(
            {
                **witness,
                "predecessor_source_path": predecessor_descriptor["path"],
                "candidate_source_path": candidate_descriptor["path"],
                "predecessor_artifact_path": artifact_predecessor,
                "candidate_artifact_path": artifact_candidate,
                "raw_hash_domain": RAW_DOMAIN,
                "defines_support": False,
                "determines_cells": False,
                "determines_coefficient": False,
                "determines_verdict": False,
            }
        )
        copies.extend(((artifact_predecessor, predecessor_raw), (artifact_candidate, candidate_raw)))
    return receipt_rows, manifest_rows, copies
def _load_control_fixture(
    root: Path,
    fixture_id: str,
    name: str,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    control_path = root / "gates" / "g05-conversion" / "controls" / f"{fixture_id}.json"
    control = _read_json(control_path)
    _require(control.get("schema") == "cassi.qi-flow-w5-integrated-control.v1", f"W5 control schema mismatch: {fixture_id}")
    _require(control.get("control_id") == fixture_id, f"W5 fixture control id mismatch: {fixture_id}")
    descriptors = control.get("fixtures")
    descriptor = descriptors.get(name) if isinstance(descriptors, Mapping) else None
    _require(isinstance(descriptor, Mapping), f"W5 control omitted {name} fixture: {fixture_id}")
    relative = descriptor.get("path")
    _require(isinstance(relative, str) and relative.startswith("fixtures/"), f"W5 fixture path is not source-relative: {fixture_id}/{name}")
    raw = (root / relative).read_bytes()
    _require(descriptor.get("domain") == RAW_DOMAIN and descriptor.get("dtype") == "<f8", f"W5 fixture raw contract mismatch: {fixture_id}/{name}")
    _require(descriptor.get("byte_count") == len(raw) and descriptor.get("sha256") == _sha(raw), f"W5 fixture descriptor hash mismatch: {fixture_id}/{name}")
    return control, dict(descriptor), raw


def _fixture_artifact_path(descriptor: Mapping[str, Any], *, fixture_id: str, name: str) -> str:
    relative = descriptor.get("path")
    _require(isinstance(relative, str) and relative.startswith("fixtures/"), f"invalid W5 fixture source path: {fixture_id}/{name}")
    suffix = Path(relative).suffix or ".f64le"
    return f"witnesses/{fixture_id}-{name}{suffix}"


def _control_receipt_rows(control: Mapping[str, Any], fixture_id: str) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    receipt = control.get("receipt")
    _require(isinstance(receipt, Mapping), f"{fixture_id} control omits its observed runtime receipt")
    conversion = receipt.get("conversion")
    rows = conversion.get("rows") if isinstance(conversion, Mapping) else None
    _require(isinstance(rows, list), f"{fixture_id} receipt conversion rows are not a list")
    return receipt, rows


def _control_conversion_accepted(control: Mapping[str, Any], receipt: Mapping[str, Any]) -> bool:
    conversion = receipt.get("conversion")
    ema = receipt.get("ema")
    return bool(
        control.get("actual_decision") == "PASS"
        and control.get("committable") is True
        and control.get("conversion_enabled") is True
        and isinstance(conversion, Mapping)
        and conversion.get("q_evaluations") == 1
        and conversion.get("conversion_maps") == 1
        and isinstance(ema, Mapping)
        and ema.get("invocations") == 1
        and ema.get("updates") == 1
    )


def _build_parent_record(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    record = {
        "schema": PARENT_BINDING_SCHEMA,
        "w5_engineering_binding": dict(predecessor["binding"]),
        "w5_parent_index_sha256": _sha(predecessor["index_raw"]),
        "w5_parent_index_self_sha256": predecessor["index"]["self_sha256"],
        "w4r_extension_sha256": predecessor["extension"]["self_sha256"],
        "w4r_extension_path": predecessor["extension_path"].relative_to(predecessor["root_path"]).as_posix(),
        "w4r_chain_ordinal": predecessor["extension"]["chain_ordinal"],
        "w4r_parent_identities": predecessor["binding"]["parent_identities"],
        "source_exact": True,
        "predecessor_w5v_forward_domain_certificate": None,
    }
    record["self_sha256"] = canonical_hash(record, PARENT_BINDING_DOMAIN)
    return record


def _build_source_identity(source_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    identity = {"schema": SOURCE_IDENTITY_SCHEMA, "sources": [dict(row) for row in source_records]}
    identity["self_sha256"] = canonical_hash(identity, SOURCE_IDENTITY_DOMAIN)
    return identity


def _build_witness_manifest(
    *,
    predecessor: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    receipt_hashes = {row["fixture_id"]: row["witness_sha256"] for row in receipt["witnesses"]}
    manifest_rows = []
    for row in rows:
        value = dict(row)
        value["receipt_witness_sha256"] = receipt_hashes.get(value["fixture_id"])
        _require(_is_sha256(value["receipt_witness_sha256"]), f"W5V receipt omitted witness identity: {value['fixture_id']}")
        manifest_rows.append(value)
    manifest = {
        "schema": WITNESS_MANIFEST_SCHEMA,
        "w5_run_id": predecessor["binding"]["run_id"],
        "raw_hash_domain": RAW_DOMAIN,
        "fixtures_define_support": False,
        "proof_cover_is_profile_registered": True,
        "witnesses": manifest_rows,
    }
    manifest["self_sha256"] = canonical_hash(manifest, WITNESS_MANIFEST_DOMAIN)
    return manifest


def _build_status(
    result: Any,
    predecessor: Mapping[str, Any],
    *,
    independent_input: Mapping[str, Any],
    independent_result: Mapping[str, Any],
    parent_verifier_receipts: Mapping[str, Any],
    parent_verifier_receipts_sha256: str,
) -> dict[str, Any]:
    receipt = result.receipt
    extension = result.extension
    if extension is None:
        extension_sha256 = None
        chain_status = None
        final_certificate_identity = None
    else:
        expected_ordinal = int(predecessor["extension"]["chain_ordinal"]) + 1
        _require(extension.get("chain_ordinal") == expected_ordinal, "W5V extension ordinal is not parent ordinal plus one")
        _require(extension.get("chain_status") == "provisional", "W5V extension must remain provisional")
        _require(extension.get("final_certificate_identity_sha256") is None, "W5V extension must not claim a terminal certificate identity")
        extension_sha256 = extension["self_sha256"]
        chain_status = extension["chain_status"]
        final_certificate_identity = extension["final_certificate_identity_sha256"]
    status = {
        "schema": STATUS_SCHEMA,
        "gate": "G5V",
        "status": "PASS_W5V_G5V" if receipt["status"] == "PASS" else "FAIL_W5V_G5V",
        "parent_verifier_receipts": dict(parent_verifier_receipts),
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
        "proof_status": receipt["status"],
        "failure_artifact": receipt["status"] != "PASS",
        "w5_engineering_run_id": predecessor["binding"]["run_id"],
        "w5_engineering_index_sha256": predecessor["binding"]["index_sha256"],
        "viability_profile_sha256": result.profile.profile_sha256,
        "receipt_sha256": receipt["self_sha256"],
        "certificate_extension_sha256": extension_sha256,
        "certificate_chain_status": chain_status,
        "final_certificate_identity_sha256": final_certificate_identity,
        "w5v_forward_domain_certificate": extension_sha256,
        "fixtures_define_support": False,
        "unresolved_cell_count": receipt["cell_counts"]["UNRESOLVED"],
        "independent_input_sha256": independent_input["self_sha256"],
        "independent_result_sha256": independent_result["self_sha256"],
        "independent_verification_status": independent_result["verification_status"],
    }
    status["self_sha256"] = canonical_hash(status, STATUS_DOMAIN)
    return status


def _tag(value: float) -> str:
    number = float(value)
    _require(math.isfinite(number), "non-finite evidence scalar")
    _require(not (number == 0.0 and math.copysign(1.0, number) < 0.0), "negative-zero evidence scalar")
    return "f64:" + struct.pack(">d", number).hex()

def _raw_values(raw: bytes, *, layout: Mapping[str, Any], label: str) -> tuple[float, ...]:
    scale_count = int(layout["scale_count"])
    mode_count = int(layout["mode_count"])
    batch_lanes = int(layout.get("batch_limit", layout.get("batch_lanes", 1)))
    component_count = int(layout.get("component_count", 0))
    _require(component_count > 0, f"{label} raw state omits component_count")
    expected_count = scale_count * component_count * mode_count * batch_lanes
    _require(component_count == 9, f"{label} raw state does not declare the required nine packed components")
    _require(len(raw) == expected_count * 8, f"{label} raw state does not match the declared [S,{component_count}M,B] layout")
    values = struct.unpack("<" + "d" * expected_count, raw)
    _require(all(math.isfinite(value) for value in values), f"{label} raw state contains non-finite values")
    return values


def _raw_offset(scale: int, component: int, mode: int, batch: int, *, layout: Mapping[str, Any]) -> int:
    mode_count = int(layout["mode_count"])
    batch_lanes = int(layout.get("batch_limit", layout.get("batch_lanes", 1)))
    return ((scale * int(layout["component_count"]) + component) * mode_count + mode) * batch_lanes + batch


def _position_density(values: Sequence[float], scale: int, mode: int, batch: int, component: int, *, layout: Mapping[str, Any]) -> float:
    real = values[_raw_offset(scale, component, mode, batch, layout=layout)]
    imaginary = values[_raw_offset(scale, component + 1, mode, batch, layout=layout)]
    return real * real + imaginary * imaginary


def _pair_branch(ey: float, ei: float) -> str:
    if ey > 0.0 and ei > 0.0:
        return "own-nonzero"
    if ey == 0.0 and ei > 0.0:
        return "yang-empty"
    if ey > 0.0 and ei == 0.0:
        return "yin-empty"
    return "both-empty"


def _activity_from_raw_pair(
    predecessor_raw: bytes,
    candidate_raw: bytes,
    *,
    fixture_id: str,
    layout: Mapping[str, Any],
) -> dict[str, Any]:
    predecessor = _raw_values(predecessor_raw, layout=layout, label=f"{fixture_id} predecessor")
    candidate = _raw_values(candidate_raw, layout=layout, label=f"{fixture_id} candidate")
    scale_count = int(layout["scale_count"])
    mode_count = int(layout["mode_count"])
    batch_lanes = int(layout.get("batch_limit", layout.get("batch_lanes", 1)))
    pairs: list[dict[str, Any]] = []
    pre_scales: set[int] = set()
    post_scales: set[int] = set()
    pre_modes: set[int] = set()
    post_modes: set[int] = set()
    pre_batches: set[int] = set()
    post_batches: set[int] = set()
    active_pairs: list[dict[str, int]] = []
    for scale in range(scale_count):
        for mode in range(mode_count):
            for batch in range(batch_lanes):
                ey_pre = _position_density(predecessor, scale, mode, batch, 0, layout=layout)
                ei_pre = _position_density(predecessor, scale, mode, batch, 2, layout=layout)
                ey_post = _position_density(candidate, scale, mode, batch, 0, layout=layout)
                ei_post = _position_density(candidate, scale, mode, batch, 2, layout=layout)
                active_pre = ey_pre > 0.0 or ei_pre > 0.0
                active_post = ey_post > 0.0 or ei_post > 0.0
                if active_pre:
                    pre_scales.add(scale)
                    pre_modes.add(mode)
                    pre_batches.add(batch)
                if active_post:
                    post_scales.add(scale)
                    post_modes.add(mode)
                    post_batches.add(batch)
                if active_pre or active_post:
                    active_pairs.append({"scale": scale, "mode": mode, "batch": batch})
                pairs.append(
                    {
                        "scale": scale,
                        "mode": mode,
                        "batch": batch,
                        "branch_pre": _pair_branch(ey_pre, ei_pre),
                        "branch_post": _pair_branch(ey_post, ei_post),
                        "EY_pre": _tag(ey_pre),
                        "EI_pre": _tag(ei_pre),
                        "EY_post": _tag(ey_post),
                        "EI_post": _tag(ei_post),
                        "T_raw": _tag(ey_pre - ey_post),
                        "position_active_pre": active_pre,
                        "position_active_post": active_post,
                        "position_active_pair": active_pre or active_post,
                    }
                )
    return {
        "layout": {"scale_count": scale_count, "mode_count": mode_count, "batch_lanes": batch_lanes, "packed_components": int(layout["component_count"])},
        "pre_active_scale_ids": sorted(pre_scales),
        "post_active_scale_ids": sorted(post_scales),
        "active_scale_ids": sorted(pre_scales | post_scales),
        "pre_active_mode_site_ids": sorted(pre_modes),
        "post_active_mode_site_ids": sorted(post_modes),
        "active_mode_site_ids": sorted(pre_modes | post_modes),
        "pre_active_batch_ids": sorted(pre_batches),
        "post_active_batch_ids": sorted(post_batches),
        "active_batch_ids": sorted(pre_batches | post_batches),
        "active_scale_mode_site_pairs": active_pairs,
        "pair_observations": pairs,
    }


def _exact_runtime_rational(
    profile: Mapping[str, Any],
    duration_s: float,
    receipt: Mapping[str, Any],
) -> dict[str, int]:
    row = receipt.get("duration_exact_rational", receipt.get("duration_rational"))
    _require(isinstance(row, Mapping) and set(row) == {"numerator", "denominator"}, "W5 receipt lacks an exact runtime rational")
    numerator, denominator = row.get("numerator"), row.get("denominator")
    _require(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and numerator > 0
        and denominator > 0
        and math.gcd(numerator, denominator) == 1,
        "W5 receipt runtime rational is not reduced and positive",
    )
    _require(float(numerator / denominator) == duration_s, "W5 receipt runtime rational does not identify its binary64 duration")
    duration = profile["D_conv"]["duration_s"]
    if isinstance(duration, Mapping):
        h_min = finite_float(duration["min"], name="W5 runtime h_min")
        h_max = finite_float(duration["max"], name="W5 runtime h_max")
    else:
        _require(isinstance(duration, list) and len(duration) == 2, "W5 runtime duration support must expose two endpoints")
        h_min = finite_float(duration[0], name="W5 runtime h_min")
        h_max = finite_float(duration[1], name="W5 runtime h_max")
    _require(h_min <= duration_s <= h_max, "W5 receipt runtime rational lies outside the frozen closed interval")
    return {"numerator": numerator, "denominator": denominator}

def _fraction(numerator: int, denominator: int) -> dict[str, Any]:
    _require(isinstance(numerator, int) and isinstance(denominator, int) and 0 <= numerator <= denominator and denominator > 0, "invalid activity fraction")
    return {"numerator": numerator, "denominator": denominator, "fraction": _tag(numerator / denominator)}
def _fraction_or_zero(numerator: int, denominator: int) -> dict[str, Any]:
    return _fraction(numerator, denominator) if denominator > 0 else _fraction(0, 1)
def _state_from_raw(raw: bytes, *, geometry: Any) -> QiFlowStateV3:
    import torch

    layout = geometry.base_profile.state_layout
    scale_count = int(layout["scale_count"])
    mode_count = int(layout["mode_count"])
    batch_lanes = int(layout.get("batch_limit", 1))
    component_count = int(layout.get("component_count", 0))
    _require(component_count == 9, "raw state must declare nine packed components")
    expected_count = scale_count * component_count * mode_count * batch_lanes
    _require(len(raw) == expected_count * 8, f"raw state length does not match the current [S,{component_count}M,B] layout")
    values = torch.tensor(struct.unpack("<" + "d" * expected_count, raw), dtype=torch.float64)
    return QiFlowStateV3(values.reshape(scale_count, component_count * mode_count, batch_lanes).contiguous())


def _build_raw_activity(
    *,
    predecessor: Mapping[str, Any],
    profile: Mapping[str, Any],
    geometry: Any,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(predecessor["root_path"])
    cells = {row["cell_id"]: row for row in receipt["cells"]}
    progress_u = finite_float(receipt["analytic_enclosures"]["progress_transfer"]["U_T"], name="analytic U_T")
    progress_margin = finite_float(profile["registered_margins"]["Delta_T_min"], name="registered progress margin")
    state_layout = dict(geometry.base_profile.state_layout)
    scale_count = int(state_layout["scale_count"])
    mode_count = int(state_layout["mode_count"])
    batch_lanes = int(state_layout.get("batch_limit", 1))
    rows: list[dict[str, Any]] = []
    position_scales: set[int] = set()
    position_modes: set[int] = set()
    position_batches: set[int] = set()
    position_pairs: set[tuple[int, int, int]] = set()
    progress_scales: set[int] = set()
    progress_modes: set[int] = set()
    progress_batches: set[int] = set()
    progress_pairs: set[tuple[int, int, int]] = set()
    progress_residence_pair_counts = {scale: 0 for scale in range(scale_count)}
    progress_residence_interval_counts = {scale: 0 for scale in range(scale_count)}
    accepted_forward_steps = 0
    accepted_conversion_intervals = 0
    accepted_progress_intervals = 0
    for fixture_id, covered_cells in WITNESS_CELL_REGISTRATION.items():
        control, predecessor_descriptor, predecessor_raw = _load_control_fixture(root, fixture_id, "predecessor")
        _, candidate_descriptor, candidate_raw = _load_control_fixture(root, fixture_id, "candidate")
        control_receipt, conversion_rows = _control_receipt_rows(control, fixture_id)
        _require(control.get("actual_decision") == "PASS" and control.get("committable") is True, f"{fixture_id} raw control is not accepted")
        _require(control.get("predecessor_raw_sha256") == _sha(predecessor_raw), f"{fixture_id} predecessor raw linkage drifted")
        _require(control.get("candidate_raw_sha256") == _sha(candidate_raw), f"{fixture_id} candidate raw linkage drifted")
        activity = _activity_from_raw_pair(predecessor_raw, candidate_raw, fixture_id=fixture_id, layout=state_layout)
        duration_s = finite_float(control.get("duration_s"), name=f"{fixture_id} duration")
        exact_rational = _exact_runtime_rational(profile, duration_s, control_receipt)
        transfers: list[dict[str, Any]] = []
        for item in conversion_rows:
            _require(isinstance(item, dict) and isinstance(item.get("scale"), int), f"{fixture_id} malformed observed transfer row")
            transfers.append(
                {
                    "scale": item["scale"],
                    "epsilon_min": item["epsilon_min"],
                    "epsilon_max": item["epsilon_max"],
                    "transfer_min": item["transfer_min"],
                    "transfer_max": item["transfer_max"],
                    "signed_progress_min": item["signed_progress_min"],
                }
            )
        progress_cells = [cell_id for cell_id in covered_cells if cell_id in {"C05-progress-positive", "C06-progress-negative"}]
        accepted_forward = control.get("actual_decision") == "PASS" and control.get("committable") is True
        accepted_conversion = _control_conversion_accepted(control, control_receipt)
        accepted_progress = accepted_conversion and len(progress_cells) == 1 and progress_cells[0] in {"C05-progress-positive", "C06-progress-negative"}
        progress_evidence: dict[str, Any] | None = None
        if accepted_progress:
            _require(len(transfers) == scale_count, f"{fixture_id} progress control omitted per-scale transfer observations")
            positive = progress_cells[0] == "C05-progress-positive"
            expected_sign = 1 if positive else -1
            progress_pair_count = 0
            active_position_pair_count = 0
            progress_resident_scales: set[int] = set()
            for pair in activity["pair_observations"]:
                active_pair = pair["position_active_pair"]
                transfer = finite_float(pair["T_raw"], name=f"{fixture_id} site transfer")
                signed_transfer = expected_sign * transfer
                margin_after_u = abs(transfer) - progress_u
                progress_active = bool(
                    pair["position_active_pre"]
                    and pair["position_active_post"]
                    and signed_transfer > 0.0
                    and margin_after_u >= progress_margin
                )
                pair["expected_progress_sign"] = expected_sign
                pair["abs_T_minus_U_T"] = _tag(margin_after_u)
                pair["progress_active"] = progress_active
                if active_pair:
                    active_position_pair_count += 1
                    _require(progress_active, f"{fixture_id} active W1 pair fails observed raw T sign/U/margin progress predicate")
                if progress_active:
                    progress_pair_count += 1
                    progress_scales.add(pair["scale"])
                    progress_modes.add(pair["mode"])
                    progress_batches.add(pair["batch"])
                    progress_pairs.add((pair["scale"], pair["mode"], pair["batch"]))
                    progress_residence_pair_counts[pair["scale"]] += 1
                    progress_resident_scales.add(pair["scale"])
            for scale in progress_resident_scales:
                progress_residence_interval_counts[scale] += 1
            _require(progress_pair_count > 0, f"{fixture_id} has no observed progress-active W1 pairs")
            progress_evidence = {
                "cell_id": progress_cells[0],
                "U_T": receipt["analytic_enclosures"]["progress_transfer"]["U_T"],
                "Delta_T_min": profile["registered_margins"]["Delta_T_min"],
                "position_active_pair_count": active_position_pair_count,
                "progress_active_pair_count": progress_pair_count,
                "cell_transfer_margin_lower": cells[progress_cells[0]]["transfer_margin_lower"],
                "all_position_active_pairs_clear_raw_sign_and_margin": progress_pair_count == active_position_pair_count,
            }
        else:
            for pair in activity["pair_observations"]:
                pair["expected_progress_sign"] = None
                pair["abs_T_minus_U_T"] = None
                pair["progress_active"] = False
        if accepted_forward:
            accepted_forward_steps += 1
        if accepted_conversion:
            accepted_conversion_intervals += 1
            position_scales.update(activity["active_scale_ids"])
            position_modes.update(activity["active_mode_site_ids"])
            position_batches.update(activity["active_batch_ids"])
            position_pairs.update((pair["scale"], pair["mode"], pair["batch"]) for pair in activity["active_scale_mode_site_pairs"])
        if accepted_progress:
            accepted_progress_intervals += 1
        row = {
            "fixture_id": fixture_id,
            "covered_cell_ids": list(covered_cells),
            "control_role": "nonproduction-conversion-disabled-control" if control.get("conversion_enabled") is False else "production-forward-control",
            "predecessor_sha256": _raw_hash(predecessor_raw),
            "candidate_sha256": _raw_hash(candidate_raw),
            "control_receipt_sha256": control.get("receipt_self_sha256") or control.get("receipt_sha256"),
            "actual_decision": control.get("actual_decision"),
            "enabled": control.get("conversion_enabled"),
            "duration_s": duration_s,
            "duration_exact_rational": exact_rational,
            "conversion_invocations": control_receipt.get("conversion", {}).get("conversion_maps") if isinstance(control_receipt.get("conversion"), Mapping) else None,
            "ema_updates": control_receipt.get("ema", {}).get("updates") if isinstance(control_receipt.get("ema"), Mapping) else None,
            "accepted_forward_step": accepted_forward,
            "accepted_conversion_interval": accepted_conversion,
            "accepted_progress_interval": accepted_progress,
            "transfer_rows": transfers,
            "progress_evidence": progress_evidence,
            "activity": activity,
        }
        row["trajectory_sha256"] = canonical_hash(row, RAW_ACTIVITY_SCHEMA)
        rows.append(row)
    aggregate = {
        "declared_trajectory_count": len(rows),
        "accepted_forward_step_count": accepted_forward_steps,
        "accepted_conversion_interval_count": accepted_conversion_intervals,
        "accepted_progress_interval_count": accepted_progress_intervals,
        "layout": {"scale_count": scale_count, "mode_count": mode_count, "batch_lanes": batch_lanes, "packed_components": int(state_layout["component_count"])},
        "position_scale_coverage": _fraction(len(position_scales), scale_count),
        "position_mode_coverage": _fraction(len(position_modes), mode_count),
        "position_site_coverage": _fraction(len(position_modes), mode_count),
        "position_batch_coverage": _fraction(len(position_batches), batch_lanes),
        "position_scale_mode_site_coverage": _fraction(len(position_pairs), scale_count * mode_count * batch_lanes),
        "progress_scale_coverage": _fraction(len(progress_scales), scale_count),
        "progress_mode_coverage": _fraction(len(progress_modes), mode_count),
        "progress_site_coverage": _fraction(len(progress_modes), mode_count),
        "progress_batch_coverage": _fraction(len(progress_batches), batch_lanes),
        "progress_scale_mode_site_coverage": _fraction(len(progress_pairs), scale_count * mode_count * batch_lanes),
        "position_active_scale_ids": sorted(position_scales),
        "position_active_mode_site_ids": sorted(position_modes),
        "progress_active_scale_ids": sorted(progress_scales),
        "progress_active_mode_site_ids": sorted(progress_modes),
        "progress_residence_pair_intervals_by_scale": progress_residence_pair_counts,
        "progress_residence_interval_count_by_scale": progress_residence_interval_counts,
        "progress_residence_pair_interval_occupancy": _fraction_or_zero(sum(progress_residence_pair_counts.values()), accepted_progress_intervals * scale_count * mode_count * batch_lanes),
    }
    value = {
        "schema": RAW_ACTIVITY_SCHEMA,
        "method": "decoded-little-endian-f64-W1-W2-state-pairs.v1",
        "fixtures_define_support": False,
        "fixtures_determine_verdict": False,
        "layout_binding": {
            "w1_profile_sha256": geometry.base_profile.profile_sha256,
            "w1_profile_root_sha256": geometry.base_profile.contract_root.sha256,
            "w1_active_shapes": copy.deepcopy(geometry.base_profile.payload["spatial"]["active_shapes"]),
            "w1_active_site_order": geometry.base_profile.payload["spatial"]["active_site_order"],
            "w1_state_layout": state_layout,
            "w2_geometry_profile_sha256": geometry.profile_sha256,
            "w2_geometry_contract_sha256": geometry.contract_root_sha256,
            "w2_grid_shape": list(geometry.grid_shape),
            "w2_mode_site_flattening": geometry.payload.get("mode_site_flattening", "profile-declared-mode-order"),
            "mode_site_bijection": True,
            "witness_batch_lanes": batch_lanes,
            "profile_batch_limit": batch_lanes,
        },
        "trajectories": rows,
        "aggregate": aggregate,
    }
    value["self_sha256"] = canonical_hash(value, RAW_ACTIVITY_DOMAIN)
    return value


def _classify_work(work: float, tolerance: float) -> str:
    if work > tolerance:
        return "positive"
    if work < -tolerance:
        return "negative"
    return "source-ambiguous"


def _build_work_observations(
    *,
    predecessor: Mapping[str, Any],
    geometry: Any,
    conversion: Any,
    raw_activity: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(predecessor["root_path"])
    transport = load_w3_transport_profile(geometry=geometry)
    carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
    topology = load_w4r_topology_profile(geometry=geometry)
    tolerance = conversion.work_tolerance
    rows: list[dict[str, Any]] = []
    for trajectory in raw_activity["trajectories"]:
        fixture_id = trajectory["fixture_id"]
        control, _, predecessor_raw = _load_control_fixture(root, fixture_id, "predecessor")
        _, _, candidate_raw = _load_control_fixture(root, fixture_id, "candidate")
        control_receipt = control["receipt"]
        predecessor_state = _state_from_raw(predecessor_raw, geometry=geometry)
        candidate_state = _state_from_raw(candidate_raw, geometry=geometry)
        pre = _energy_components(predecessor_state, geometry=geometry, carrier_profile=carrier, topology_profile=topology)
        post = _energy_components(candidate_state, geometry=geometry, carrier_profile=carrier, topology_profile=topology)
        delta = {name: post[name] - pre[name] for name in pre}
        conversion_work = sum(delta[name] for name in ("carrier", "topological", "extra_conservative") if name in delta)
        closure = delta["total"] - conversion_work
        recomputed = {
            "pre": pre,
            "post": post,
            "delta": delta,
            "W_conversion": conversion_work,
            "closure_residual": closure,
        }
        observed_energy = control_receipt.get("energy")
        _require(isinstance(observed_energy, Mapping), f"{fixture_id} runtime receipt omits energy")
        reported_work = finite_float(observed_energy.get("W_conversion"), name=f"{fixture_id} observed conversion work")
        _require(math.isclose(reported_work, conversion_work, rel_tol=1.0e-9, abs_tol=max(tolerance, 1.0e-12)), f"{fixture_id} raw endpoint work replay differs from observed runtime receipt")
        row = {
            "fixture_id": fixture_id,
            "accepted_forward": control.get("actual_decision") == "PASS" and control.get("committable") is True,
            "predecessor_sha256": trajectory["predecessor_sha256"],
            "candidate_sha256": trajectory["candidate_sha256"],
            "control_receipt_sha256": control.get("receipt_self_sha256") or control.get("receipt_sha256"),
            "work_tolerance": tolerance,
            "raw_endpoint_energy": recomputed,
            "classification": _classify_work(conversion_work, tolerance),
            "source_work_is_verdict_input": False,
        }
        row["self_sha256"] = canonical_hash(row, WORK_OBSERVATION_SCHEMA)
        rows.append(row)
    value = {
        "schema": WORK_OBSERVATION_SCHEMA,
        "method": "source-exact-runtime-energy-observation-linked-to-W5-receipt.v1",
        "fixtures_define_support": False,
        "source_work_is_verdict_input": False,
        "classification_space": ["negative", "source-ambiguous", "positive"],
        "rows": rows,
    }
    value["classification_counts"] = {
        name: sum(row["classification"] == name for row in rows)
        for name in value["classification_space"]
    }
    value["self_sha256"] = canonical_hash(value, WORK_OBSERVATION_DOMAIN)
    return value


def _validate_work_observations(value: Mapping[str, Any]) -> None:
    _require(value.get("schema") == WORK_OBSERVATION_SCHEMA, "work observation schema mismatch")
    _require(value.get("fixtures_define_support") is False and value.get("source_work_is_verdict_input") is False, "source work was promoted to proof authority")
    rows = value.get("rows")
    _require(isinstance(rows, list) and rows, "work observation rows missing")
    for row in rows:
        _require(isinstance(row, dict), "work observation row is malformed")
        energy = row.get("raw_endpoint_energy")
        _require(isinstance(energy, dict), "work observation omits raw endpoint energy")
        work = finite_float(energy.get("W_conversion"), name="observed source work")
        tolerance = finite_float(row.get("work_tolerance"), name="observed work tolerance")
        _require(row.get("classification") == _classify_work(work, tolerance), "source work classification disagrees with observed raw endpoint work")
def _raw_components_identical(before: bytes, after: bytes, *, components: Iterable[int], layout: Mapping[str, Any]) -> bool:
    scale_count = int(layout["scale_count"])
    mode_count = int(layout["mode_count"])
    batch_lanes = int(layout.get("batch_limit", 1))
    component_count = int(layout.get("component_count", 0))
    _require(component_count == 9, "control-law raw state must declare nine packed components")
    expected_length = scale_count * component_count * mode_count * batch_lanes * 8
    _require(len(before) == len(after) == expected_length, "control-law raw state layout mismatch")
    for scale in range(scale_count):
        for component in components:
            for mode in range(mode_count):
                for batch in range(batch_lanes):
                    offset = _raw_offset(scale, component, mode, batch, layout=layout) * 8
                    if before[offset : offset + 8] != after[offset : offset + 8]:
                        return False
    return True

def _build_g5_control_laws(
    *,
    predecessor: Mapping[str, Any],
    geometry: Any,
    conversion: Any,
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    state_layout = dict(geometry.base_profile.state_layout)
    transport = load_w3_transport_profile(geometry=geometry)
    carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
    root = Path(predecessor["root_path"])
    fixture_id = "matched-energy-positive-imbalance"
    source_control, source_descriptor, source_raw = _load_control_fixture(root, fixture_id, "predecessor")
    source_receipt, _ = _control_receipt_rows(source_control, fixture_id)
    source_state = _state_from_raw(source_raw, geometry=geometry)
    duration_s = finite_float(source_control.get("duration_s"), name="G5 control source duration")
    rational = _exact_runtime_rational(predecessor["profile"], duration_s, source_receipt)
    source_artifact_path = _fixture_artifact_path(source_descriptor, fixture_id=fixture_id, name="predecessor")
    zero_lambda = replace(conversion, lambda_rate=0.0)
    copied: list[tuple[str, bytes]] = []
    controls: list[dict[str, Any]] = []

    normal_input = {
        "schema": G5_CONTROL_INPUT_SCHEMA,
        "control_id": "lambda-zero-normal-physical-ema",
        "control_scope": "source-exact-frozen-law-internal-control.v1",
        "source_fixture_id": fixture_id,
        "predecessor_artifact_path": source_artifact_path,
        "predecessor_sha256": _raw_hash(source_raw),
        "duration_s": duration_s,
        "duration_exact_rational": rational,
        "lambda_rate_s_inv": _tag(0.0),
        "epsilon_memory_time_s": _tag(conversion.epsilon_memory_time),
        "tau_mode": "normal-physical-time-derived-once.v1",
    }
    normal_input["self_sha256"] = canonical_hash(normal_input, G5_CONTROL_INPUT_DOMAIN)
    mapped, map_rows, _ = _frozen_q_map(source_state, geometry=geometry, profile=zero_lambda, carrier_profile=carrier, duration_s=duration_s)
    normal_candidate, tau, ema_rows = _update_ema_once(mapped, geometry=geometry, profile=zero_lambda, carrier_profile=carrier, duration_s=duration_s, enabled=True)
    normal_raw = raw_state_bytes_from_field(normal_candidate.field)
    normal_path = "control-law-witnesses/lambda-zero-normal-physical-ema-candidate.f64le"
    copied.append((normal_path, normal_raw))
    map_components = range(int(state_layout["component_count"]) - 1)
    ema_components = range(int(state_layout["component_count"]) - 1, int(state_layout["component_count"]))
    _require(_raw_components_identical(source_raw, normal_raw, components=map_components, layout=state_layout), "lambda=0 normal-EMA control mutated position or velocity lanes")
    _require(not _raw_components_identical(source_raw, normal_raw, components=ema_components, layout=state_layout), "lambda=0 normal-EMA control did not make its one physical EMA update")
    normal_result = {
        "schema": G5_CONTROL_RESULT_SCHEMA,
        "input_sha256": normal_input["self_sha256"],
        "actual_decision": "PASS",
        "conversion_maps": 1,
        "ema_stage_invocations": 1,
        "ema_updates": 1,
        "tau": _tag(tau),
        "candidate_artifact_path": normal_path,
        "candidate_sha256": _raw_hash(normal_raw),
        "positions_velocities_raw_identical": True,
        "ema_raw_changed_once": True,
        "per_scale_conversion": [dict(row) for row in map_rows],
        "per_scale_ema": [dict(row) for row in ema_rows],
        "ema_recomputation": {
            "tau_formula": "1-exp(-h/epsilon_memory_time)",
            "sample_formula": "(abs(Y)-sqrt(phi)*abs(I))**2",
            "per_lane_ulp_upper_bound": 8,
            "evaluated_batch_lanes": int(state_layout.get("batch_limit", state_layout.get("batch_lanes", 1))),
        },
    }
    normal_result["self_sha256"] = canonical_hash(normal_result, G5_CONTROL_RESULT_DOMAIN)
    controls.append({"input": normal_input, "result": normal_result})

    limit_input = {
        "schema": G5_CONTROL_INPUT_SCHEMA,
        "control_id": "lambda-zero-tau-zero-exact-whole-state-noop",
        "control_scope": "source-exact-frozen-law-joint-limit-control.v1",
        "source_fixture_id": fixture_id,
        "predecessor_artifact_path": source_artifact_path,
        "predecessor_sha256": _raw_hash(source_raw),
        "duration_s": duration_s,
        "duration_exact_rational": rational,
        "lambda_rate_s_inv": _tag(0.0),
        "tau": _tag(0.0),
        "tau_mode": "joint-limit-exact-ema-stage-evaluation.v1",
    }
    limit_input["self_sha256"] = canonical_hash(limit_input, G5_CONTROL_INPUT_DOMAIN)
    limit_mapped, limit_rows, _ = _frozen_q_map(source_state, geometry=geometry, profile=zero_lambda, carrier_profile=carrier, duration_s=duration_s)
    # This is an explicit one-stage tau=0 evaluation: it visits the EMA stage,
    # makes no lane write because its exact coefficient is zero, and preserves
    # the mapped raw state byte-for-byte.
    limit_candidate = type(limit_mapped)(limit_mapped.field.clone().contiguous())
    limit_raw = raw_state_bytes_from_field(limit_candidate.field)
    limit_path = "control-law-witnesses/lambda-zero-tau-zero-exact-whole-state-noop-candidate.f64le"
    copied.append((limit_path, limit_raw))
    _require(limit_raw == source_raw, "joint lambda=0,tau=0 control is not an exact whole-state no-op")
    limit_result = {
        "schema": G5_CONTROL_RESULT_SCHEMA,
        "input_sha256": limit_input["self_sha256"],
        "actual_decision": "PASS",
        "conversion_maps": 1,
        "ema_stage_invocations": 1,
        "ema_updates": 0,
        "ema_update_writes": 0,
        "tau": _tag(0.0),
        "candidate_artifact_path": limit_path,
        "candidate_sha256": _raw_hash(limit_raw),
        "whole_state_raw_identical": True,
        "per_scale_conversion": [dict(row) for row in limit_rows],
        "per_scale_ema": [{"scale": scale, "tau": _tag(0.0), "wrote_state": False} for scale in range(int(state_layout["scale_count"]))],
        "ema_recomputation": {
            "tau_formula": "joint-exact-zero",
            "sample_formula": "(abs(Y)-sqrt(phi)*abs(I))**2",
            "per_lane_ulp_upper_bound": 0,
            "evaluated_batch_lanes": int(state_layout.get("batch_limit", 1)),
        },
    }
    limit_result["self_sha256"] = canonical_hash(limit_result, G5_CONTROL_RESULT_DOMAIN)
    controls.append({"input": limit_input, "result": limit_result})

    value = {
        "schema": G5_CONTROL_LAW_SCHEMA,
        "fixtures_define_support": False,
        "fixtures_determine_verdict": False,
        "control_law_source": "sources/cassi_qi_conversion.py",
        "controls": controls,
    }
    value["self_sha256"] = canonical_hash(value, G5_CONTROL_LAW_DOMAIN)
    return value, copied


def _seal_mutation_control(value: Mapping[str, Any]) -> dict[str, Any]:
    record = dict(value)
    _require(record.get("schema") == MUTATION_CONTROL_SCHEMA, "mutation control schema mismatch")
    record["self_sha256"] = canonical_hash(record, MUTATION_CONTROL_DOMAIN)
    return record


def _observed_structural_rejection(
    *,
    control_id: str,
    mutation: Mapping[str, Any],
    action: Callable[[], Any],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        action()
    except Exception as exc:
        observed = {
            "kind": "observed-structural-rejection.v1",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
    else:
        raise ViabilityArtifactError(f"{control_id} mutation was accepted instead of producing an observed rejection")
    record: dict[str, Any] = {
        "schema": MUTATION_CONTROL_SCHEMA,
        "control_id": control_id,
        "mutation_class": "structural",
        "mutation": dict(mutation),
        "actual_decision": "REJECTED",
        "observed_rejection": observed,
    }
    if extra is not None:
        record.update(dict(extra))
    return _seal_mutation_control(record)


def _observed_pair_schedule_rejection(
    *,
    control_id: str,
    mutation: Mapping[str, Any],
    runtime_decisions: Sequence[str],
    action: Callable[[], Any],
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        action()
    except Exception as exc:
        observed = {
            "kind": "observed-pair-schedule-rejection.v1",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
    else:
        raise ViabilityArtifactError(f"{control_id} pair schedule was accepted instead of producing an observed rejection")
    return _seal_mutation_control(
        {
            "schema": MUTATION_CONTROL_SCHEMA,
            "control_id": control_id,
            "mutation_class": "pair-schedule",
            "mutation": dict(mutation),
            "runtime_decisions": list(runtime_decisions),
            "pair_verifier_decision": "REJECTED",
            "observed_pair_rejection": observed,
            **dict(extra),
        }
    )




def _runtime_rejection(
    *,
    control_id: str,
    mutation: Mapping[str, Any],
    state: Any,
    geometry: Any,
    transport: Any,
    carrier: Any,
    topology: Any,
    conversion: Any,
    certificate: Mapping[str, Any],
    duration_s: float,
    input_raw: bytes,
    input_artifact_path: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    step = transition_w5_integrated(
        state,
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=carrier,
        topology_profile=topology,
        conversion_profile=conversion,
        numerical_certificate=certificate,
        duration_s=duration_s,
    )
    receipt = dict(step.receipt)
    _require(not step.committable and step.candidate is None, f"{control_id} mutation unexpectedly committed")
    _require(receipt.get("status") == "REJECTED" and receipt.get("committable") is False, f"{control_id} mutation omitted an observed runtime rejection receipt")
    _require(receipt.get("predecessor_state_sha256") == _raw_hash(input_raw), f"{control_id} runtime rejection receipt is not linked to its observed input")
    record: dict[str, Any] = {
        "schema": MUTATION_CONTROL_SCHEMA,
        "control_id": control_id,
        "mutation_class": "runtime",
        "mutation": dict(mutation),
        "actual_decision": "REJECTED",
        "input_raw_sha256": _raw_hash(input_raw),
        "input_artifact_path": input_artifact_path,
        "actual_runtime_receipt": receipt,
        "actual_runtime_receipt_sha256": receipt.get("self_sha256"),
    }
    if extra is not None:
        record.update(dict(extra))
    return _seal_mutation_control(record)


def _mutated_profile(conversion: Any, mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(conversion.payload))
    payload.pop("profile_sha256", None)
    mutate(payload)
    payload["profile_sha256"] = canonical_hash(payload, W5_PROFILE_DOMAIN)
    return payload


def _payload_section(payload: dict[str, Any], name: str) -> MutableMapping[str, Any]:
    section = payload.get(name)
    if not isinstance(section, dict) and name == "registered_margins":
        section = payload.get("margins")
    if isinstance(section, dict):
        return section
    if name == "D_conv":
        support = payload.get("support")
        if isinstance(support, dict) and isinstance(support.get(name), dict):
            return support[name]
    raise ViabilityArtifactError(f"profile mutation target {name} is not an explicit object")
def _profile_rejection_clone(conversion: Any, payload: Mapping[str, Any]) -> Any:
    return replace(conversion, payload=dict(payload), profile_sha256=str(payload["profile_sha256"]))

def _payload_parameters(payload: dict[str, Any]) -> MutableMapping[str, Any]:
    parameters = payload.get("parameters")
    return parameters if isinstance(parameters, dict) else payload


def _payload_cover_cells(payload: dict[str, Any]) -> list[MutableMapping[str, Any]]:
    cover = payload.get("complete_domain_cover", payload.get("cover"))
    cells = cover.get("cells") if isinstance(cover, dict) else cover
    if not isinstance(cells, list) or not all(isinstance(row, dict) for row in cells):
        raise ViabilityArtifactError("profile mutation target cover cells is not explicit")
    return cells

def _assert_cell_vector_is_complete(receipt: Mapping[str, Any]) -> None:
    rows = receipt.get("cells")
    _require(isinstance(rows, list) and len(rows) == 7, "mutated cell vector is incomplete")
    counts = {"total": len(rows), "PASS": 0, "FAIL": 0, "UNRESOLVED": 0}
    for row in rows:
        _require(isinstance(row, dict) and row.get("status") in {"PASS", "FAIL", "UNRESOLVED"}, "mutated cell row has no valid observed status")
        counts[row["status"]] += 1
    _require(receipt.get("cell_counts") == counts, "mutated receipt suppresses a cell status or unresolved count")
    _require(counts["FAIL"] == 0 and counts["UNRESOLVED"] == 0 and counts["PASS"] == 7, "mutated receipt is not an all-cell complete-domain pass")


def _build_mutation_observations(
    *,
    predecessor: Mapping[str, Any],
    geometry: Any,
    conversion: Any,
    result: Any,
    work_observations: Mapping[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    root = Path(predecessor["root_path"])
    fixture_id = "matched-energy-positive-imbalance"
    source_control, source_descriptor, source_raw = _load_control_fixture(root, fixture_id, "predecessor")
    source_artifact_path = _fixture_artifact_path(source_descriptor, fixture_id=fixture_id, name="predecessor")
    source_state = _state_from_raw(source_raw, geometry=geometry)
    transport = load_w3_transport_profile(geometry=geometry)
    carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
    topology = load_w4r_topology_profile(geometry=geometry)
    certificate = predecessor["certificate"]
    copies: list[tuple[str, bytes]] = []
    controls: list[dict[str, Any]] = []

    out_of_interval_duration = 0.0
    controls.append(
        _runtime_rejection(
            control_id="mutate-unregistered-timestep",
            mutation={
                "kind": "runtime-rational-outside-frozen-closed-H-runtime.v1",
                "duration_s": out_of_interval_duration,
                "duration_exact_rational": {"numerator": 0, "denominator": 1},
                "frozen_runtime_interval": copy.deepcopy(predecessor["profile"]["D_conv"]["duration_s"]),
            },
            state=source_state,
            geometry=geometry,
            transport=transport,
            carrier=carrier,
            topology=topology,
            conversion=conversion,
            certificate=certificate,
            duration_s=out_of_interval_duration,
            input_raw=source_raw,
            input_artifact_path=source_artifact_path,
        )
    )

    stale_field = source_state.field.clone()
    modes = int(geometry.base_profile.state_layout["mode_count"])
    ema_component = int(geometry.base_profile.state_layout["component_count"]) - 1
    stale_field[:, ema_component * modes : (ema_component + 1) * modes, :] = math.nextafter(conversion.epsilon2_ema_max, math.inf)
    stale_state = type(source_state)(stale_field.contiguous())
    stale_raw = raw_state_bytes_from_field(stale_state.field)
    stale_path = "mutation-witnesses/mutate-stale-ema-predecessor.f64le"
    copies.append((stale_path, stale_raw))
    controls.append(
        _runtime_rejection(
            control_id="mutate-stale-ema",
            mutation={
                "kind": "epsilon2-ema-outside-frozen-D_conv.v1",
                "registered_ema_max": _tag(conversion.epsilon2_ema_max),
                "mutated_ema": math.nextafter(conversion.epsilon2_ema_max, math.inf),
            },
            state=stale_state,
            geometry=geometry,
            transport=transport,
            carrier=carrier,
            topology=topology,
            conversion=conversion,
            certificate=certificate,
            duration_s=conversion.runtime_durations[-1],
            input_raw=stale_raw,
            input_artifact_path=stale_path,
        )
    )

    profile_mutations: tuple[tuple[str, str, Callable[[dict[str, Any]], None], str], ...] = (
        (
            "mutate-memory-time",
            "mutation-inputs/mutate-memory-time-profile.json",
            lambda payload: _payload_parameters(payload).__setitem__("epsilon_memory_time_s", _tag(0.5)),
            "physical-memory-time-profile-identity.v1",
        ),
        (
            "mutate-epsilon-margin",
            "mutation-inputs/mutate-epsilon-margin-profile.json",
            lambda payload: _payload_section(payload, "registered_margins").__setitem__("Delta_T_min", _tag(0.0)),
            "registered-epsilon-margin-profile-identity.v1",
        ),
        (
            "mutate-domain-predicate",
            "mutation-inputs/mutate-domain-predicate-profile.json",
            lambda payload: _payload_cover_cells(payload)[5].__setitem__("predicate", "epsilon>0"),
            "registered-domain-predicate-profile-identity.v1",
        ),
        (
            "mutate-support-omission",
            "mutation-inputs/mutate-support-omission-profile.json",
            lambda payload: _payload_section(payload, "D_conv").pop("phase_branches"),
            "support-coordinate-omission-profile-identity.v1",
        ),
        (
            "mutate-support-shrink",
            "mutation-inputs/mutate-support-shrink-profile.json",
            lambda payload: _payload_section(payload, "A_accepted").__setitem__("density_sum_at_most", _tag(0.125)),
            "post-observation-accepted-bound-shrink-profile-identity.v1",
        ),
    )
    for control_id, path, mutate, kind in profile_mutations:
        payload = _mutated_profile(conversion, mutate)
        raw = canonical_json_bytes(payload)
        copies.append((path, raw))
        controls.append(
            _runtime_rejection(
                control_id=control_id,
                mutation={"kind": kind, "profile_input_path": path, "profile_input_sha256": _sha(raw)},
                state=source_state,
                geometry=geometry,
                transport=transport,
                carrier=carrier,
                topology=topology,
                conversion=_profile_rejection_clone(conversion, payload),
                certificate=certificate,
                duration_s=conversion.runtime_durations[-1],
                input_raw=source_raw,
                input_artifact_path=source_artifact_path,
                extra={"mutated_profile_artifact_path": path, "mutated_profile_sha256": payload["profile_sha256"]},
            )
        )

    first = transition_w5_integrated(
        source_state,
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=carrier,
        topology_profile=topology,
        conversion_profile=conversion,
        numerical_certificate=certificate,
        duration_s=conversion.runtime_durations[-1],
    )
    duplicate = transition_w5_integrated(
        source_state,
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=carrier,
        topology_profile=topology,
        conversion_profile=conversion,
        numerical_certificate=certificate,
        duration_s=conversion.runtime_durations[-1],
    )
    _require(first.committable and duplicate.committable and first.candidate is not None and duplicate.candidate is not None, "could not observe duplicate complete-step receipts")
    first_receipt, duplicate_receipt = dict(first.receipt), dict(duplicate.receipt)

    def reject_duplicate() -> None:
        if (
            first_receipt["predecessor_state_sha256"] == duplicate_receipt["predecessor_state_sha256"]
            and first_receipt["candidate_state_sha256"] == duplicate_receipt["candidate_state_sha256"]
            and first_receipt["conversion"]["conversion_maps"] == duplicate_receipt["conversion"]["conversion_maps"] == 1
        ):
            raise ViabilityArtifactError("actual duplicate conversion invocation shares one complete-step predecessor")

    controls.append(
        _observed_pair_schedule_rejection(
            control_id="mutate-duplicate-invocation",
            mutation={"kind": "duplicate-complete-step-runtime-receipt.v1", "source_fixture_id": fixture_id},
            runtime_decisions=[first_receipt["status"], duplicate_receipt["status"]],
            action=reject_duplicate,
            extra={
                "input_raw_sha256": _raw_hash(source_raw),
                "input_artifact_path": source_artifact_path,
                "first_actual_runtime_receipt": first_receipt,
                "duplicate_actual_runtime_receipt": duplicate_receipt,
            },
        )
    )

    ordered = transition_w5_integrated(
        first.candidate,
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=carrier,
        topology_profile=topology,
        conversion_profile=conversion,
        numerical_certificate=certificate,
        duration_s=conversion.runtime_durations[-1],
    )
    _require(ordered.committable and ordered.candidate is not None, "could not observe chained conversion receipt")
    ordered_receipt = dict(ordered.receipt)
    first_candidate_raw = raw_state_bytes_from_field(first.candidate.field)
    ordered_candidate_raw = raw_state_bytes_from_field(ordered.candidate.field)
    first_candidate_path = "mutation-witnesses/mutate-order-interval-1-candidate.f64le"
    ordered_candidate_path = "mutation-witnesses/mutate-order-interval-2-candidate.f64le"
    copies.extend(((first_candidate_path, first_candidate_raw), (ordered_candidate_path, ordered_candidate_raw)))

    def reject_reordered() -> None:
        expected_predecessor = _raw_hash(source_raw)
        for observed in (ordered_receipt, first_receipt):
            _require(
                observed["predecessor_state_sha256"] == expected_predecessor,
                "observed receipt order does not form the raw complete-step predecessor/candidate chain",
            )
            expected_predecessor = observed["candidate_state_sha256"]

    controls.append(
        _observed_pair_schedule_rejection(
            control_id="mutate-duplicate-order",
            mutation={"kind": "reordered-complete-step-runtime-receipts.v1", "proposed_order": ["interval-2", "interval-1"]},
            runtime_decisions=[first_receipt["status"], ordered_receipt["status"]],
            action=reject_reordered,
            extra={
                "input_raw_sha256": _raw_hash(source_raw),
                "input_artifact_path": source_artifact_path,
                "interval_1_actual_runtime_receipt": first_receipt,
                "interval_1_candidate_artifact_path": first_candidate_path,
                "interval_2_actual_runtime_receipt": ordered_receipt,
                "interval_2_candidate_artifact_path": ordered_candidate_path,
            },
        )
    )

    unresolved = copy.deepcopy(dict(result.receipt))
    unresolved["cells"][5]["status"] = "UNRESOLVED"
    unresolved["cells"][5]["unresolved"] = True
    unresolved_path = "mutation-inputs/mutate-unresolved-suppression-receipt.json"
    unresolved_raw = canonical_json_bytes(unresolved)
    copies.append((unresolved_path, unresolved_raw))
    controls.append(
        _observed_structural_rejection(
            control_id="mutate-unresolved-suppression",
            mutation={"kind": "cell-vector-unresolved-suppression.v1", "receipt_input_path": unresolved_path, "receipt_input_sha256": _sha(unresolved_raw)},
            action=lambda: _assert_cell_vector_is_complete(unresolved),
        )
    )

    parent_extension = copy.deepcopy(dict(predecessor["extension"]))
    parent_extension["chain_ordinal"] = 99
    parent_path = "mutation-inputs/mutate-parent-extension.json"
    parent_raw = canonical_json_bytes(parent_extension)
    copies.append((parent_path, parent_raw))
    controls.append(
        _observed_structural_rejection(
            control_id="mutate-parent-extension",
            mutation={"kind": "immutable-W4R-parent-extension.v1", "parent_input_path": parent_path, "parent_input_sha256": _sha(parent_raw)},
            action=lambda: _validate_w4r_extension(parent_extension, predecessor["conversion_root"]),
        )
    )

    source_mutation = (ROOT / "cassi_qi_conversion.py").read_bytes() + b"\n# source-exact-mutation\n"
    source_path = "mutation-inputs/mutate-cassi_qi_conversion.py"
    copies.append((source_path, source_mutation))
    controls.append(
        _observed_structural_rejection(
            control_id="mutate-source-snapshot",
            mutation={"kind": "source-exact-frozen-Q-byte-mutation.v1", "source_input_path": source_path, "source_input_sha256": _sha(source_mutation)},
            action=lambda: _require(source_mutation == (root / "sources" / "cassi_qi_conversion.py").read_bytes(), "mutated frozen-Q source is not source-exact W5 material"),
        )
    )

    mutated_work = copy.deepcopy(dict(work_observations))
    first_work = mutated_work["rows"][0]
    first_work["classification"] = "positive" if first_work["classification"] != "positive" else "negative"
    work_path = "mutation-inputs/mutate-source-work-observation.json"
    work_raw = canonical_json_bytes(mutated_work)
    copies.append((work_path, work_raw))
    controls.append(
        _observed_structural_rejection(
            control_id="mutate-source-work",
            mutation={"kind": "raw-source-work-classification-mismatch.v1", "work_input_path": work_path, "work_input_sha256": _sha(work_raw)},
            action=lambda: _validate_work_observations(mutated_work),
        )
    )

    value = {
        "schema": MUTATION_OBSERVATION_SCHEMA,
        "observation_policy": {
            "expected_strings_are_not_evidence": True,
            "runtime_rejections_embed_actual_receipts": True,
            "pair_schedule_rejections_preserve_their_actual_PASS_runtime_decisions": True,
            "structural_rejections_embed_actual_exception_observations": True,
            "fixtures_define_support": False,
            "fixtures_determine_cells": False,
            "fixtures_determine_coefficient": False,
            "fixtures_determine_verdict": False,
        },
        "controls": controls,
    }
    value["runtime_rejection_count"] = sum(row["mutation_class"] == "runtime" for row in controls)
    value["pair_schedule_rejection_count"] = sum(row["mutation_class"] == "pair-schedule" for row in controls)
    value["structural_rejection_count"] = sum(row["mutation_class"] == "structural" for row in controls)
    value["self_sha256"] = canonical_hash(value, MUTATION_OBSERVATION_DOMAIN)
    return value, copies


def _build_independent_input(
    predecessor: Mapping[str, Any],
    source_identity: Mapping[str, Any],
    result: Any,
    raw_activity: Mapping[str, Any],
    work_observations: Mapping[str, Any],
    control_laws: Mapping[str, Any],
    mutations: Mapping[str, Any],
) -> dict[str, Any]:
    source_rows = {row["path"]: row for row in source_identity["sources"]}
    verifier_row = source_rows.get("verify_cassi_qi_conversion_viability.py")
    _require(isinstance(verifier_row, dict), "independent verifier source was not snapshotted")
    value = {
        "schema": INDEPENDENT_INPUT_SCHEMA,
        "execution_phase": "before-final-status-and-index.v1",
        "w5_root_required": False,
        "w5_discovery_policy": "scan-contract-root-filter-source-exact-independent-pass-exactly-one",
        "w5_artifact_root": _portable_path(Path(predecessor["root_path"])),
        "w5_parent_index_sha256": predecessor["binding"]["index_sha256"],
        "w5_parent_run_id": predecessor["binding"]["run_id"],
        "w5_parent_identities": predecessor["binding"]["parent_identities"],
        "w5_certificate_identities": predecessor["binding"]["certificate_identities"],
        "source_identity_sha256": source_identity["self_sha256"],
        "verifier_source_path": "sources/verify_cassi_qi_conversion_viability.py",
        "verifier_source_sha256": verifier_row["sha256"],
        "verifier_import_policy": {
            "imports_cassi_qi_conversion_viability": False,
            "analytic_rederivation": "local-stdlib-decimal-tagged-f64.v1",
        },
        "viability_profile_sha256": result.profile.profile_sha256,
        "receipt_sha256": result.receipt["self_sha256"],
        "g5_control_laws_sha256": control_laws["self_sha256"],
        "raw_activity_sha256": raw_activity["self_sha256"],
        "work_observations_sha256": work_observations["self_sha256"],
        "mutation_observations_sha256": mutations["self_sha256"],
        "fixtures_determine_verdict": False,
    }
    value["self_sha256"] = canonical_hash(value, INDEPENDENT_INPUT_DOMAIN)
    return value


def _index_material(
    *,
    parent: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    result: Any,
    independent_input: Mapping[str, Any],
    independent_result: Mapping[str, Any],
    raw_activity: Mapping[str, Any],
    work_observations: Mapping[str, Any],
    control_laws: Mapping[str, Any],
    mutations: Mapping[str, Any],
    parent_verifier_receipts: Mapping[str, Any],
    parent_verifier_receipts_sha256: str,
) -> dict[str, Any]:
    receipt = result.receipt
    extension = result.extension
    return {
        "parent_verifier_receipts": dict(parent_verifier_receipts),
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
        "schema": INDEX_SCHEMA,
        "status": "PASS_W5V_G5V" if receipt["status"] == "PASS" else "FAIL_W5V_G5V",
        "proof_status": receipt["status"],
        "parents": [dict(parent)],
        "source_exact_successor_of": dict(parent),
        "objects": [dict(row) for row in records],
        "w5_parent_identities": receipt["parent_identities"],
        "certificate_identities": receipt["certificate_identities"],
        "gate": "G5V",
        "failure_artifact": receipt["status"] != "PASS",
        "conversion_profile_sha256": receipt["conversion_profile_sha256"],
        "conversion_root_sha256": receipt["conversion_root_sha256"],
        "law_sha256": receipt["conversion_law_sha256"],
        "viability_profile_sha256": result.profile.profile_sha256,
        "receipt_sha256": receipt["self_sha256"],
        "certificate_extension_sha256": None if extension is None else extension["self_sha256"],
        "certificate_chain_status": None if extension is None else extension["chain_status"],
        "final_certificate_identity_sha256": None if extension is None else extension["final_certificate_identity_sha256"],
        "independent_input_sha256": independent_input["self_sha256"],
        "independent_result_sha256": independent_result["self_sha256"],
        "raw_activity_sha256": raw_activity["self_sha256"],
        "work_observations_sha256": work_observations["self_sha256"],
        "g5_control_laws_sha256": control_laws["self_sha256"],
        "mutation_observations_sha256": mutations["self_sha256"],
        "fixtures_define_support": False,
    }


def _run(*, output_root: Path | None = None, w5_root: Path | None = None) -> Path:
    """Build one immutable W5V artifact from the dynamically current W5 root."""
    predecessor = _discover_current_w5() if w5_root is None else _load_w5_predecessor(Path(w5_root))
    parent_verification = _preverify_w4r_w5(predecessor)
    parent_verifier_receipts = parent_verification["receipts"]
    parent_verifier_receipts_sha256 = parent_verification["receipts_sha256"]
    geometry = load_w2_geometry_profile()
    conversion = load_w5_conversion_profile(
        geometry=geometry,
        parent_identities=predecessor["binding"]["parent_identities"],
    )
    _require(conversion.profile_sha256 == predecessor["binding"]["profile_sha256"], "live/W5 conversion profile binding mismatch")
    _require(conversion.root_sha256 == predecessor["binding"]["root_sha256"], "live/W5 conversion root binding mismatch")
    _require(conversion.law_sha256 == predecessor["binding"]["law_sha256"], "live/W5 conversion law binding mismatch")
    witnesses, manifest_rows, witness_copies = _collect_witnesses(predecessor)
    try:
        result = certify_w5v(
            conversion,
            w5_binding=predecessor["binding"],
            parent_extension=predecessor["extension"],
            witnesses=witnesses,
        )
    except ConversionViabilityError:
        profile, receipt = build_w5v_receipt(conversion, w5_binding=predecessor["binding"], witnesses=witnesses)
        _require(receipt["status"] == "FAIL", "certify_w5v failed without a source-exact FAIL receipt")
        result = SimpleNamespace(profile=profile, receipt=receipt, extension=None)
    if result.receipt["status"] == "PASS":
        _require(result.receipt["cell_counts"]["UNRESOLVED"] == 0, "passing W5V proof leaves unresolved cells")
        _require(result.extension is not None, "passing W5V proof omitted its provisional extension")
    else:
        _require(result.extension is None, "failed W5V proof unexpectedly gained an extension")
    result_profile_payload = dict(result.profile.payload)
    raw_activity = _build_raw_activity(
        predecessor=predecessor,
        profile=result_profile_payload,
        geometry=geometry,
        receipt=result.receipt,
    )
    work_observations = _build_work_observations(
        predecessor=predecessor,
        geometry=geometry,
        conversion=conversion,
        raw_activity=raw_activity,
    )
    _validate_work_observations(work_observations)
    control_laws, control_law_copies = _build_g5_control_laws(
        predecessor=predecessor,
        geometry=geometry,
        conversion=conversion,
    )
    mutations, mutation_copies = _build_mutation_observations(
        predecessor=predecessor,
        geometry=geometry,
        conversion=conversion,
        result=result,
        work_observations=work_observations,
    )

    target_root = OUTPUT_ROOT if output_root is None else Path(output_root)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w5v-conversion-", dir=target_root.parent))
    try:
        source_records = _copy_sources(stage)
        source_identity = _build_source_identity(source_records)
        parent = _build_parent_record(predecessor)
        manifest = _build_witness_manifest(predecessor=predecessor, rows=manifest_rows, receipt=result.receipt)
        if result.extension is not None:
            source_rows = {row["path"]: row for row in source_identity["sources"]}
            evidence = {
                "source_identity_sha256": source_identity["self_sha256"],
                "verifier_source_sha256": source_rows["verify_cassi_qi_conversion_viability.py"]["sha256"],
                "raw_activity_sha256": raw_activity["self_sha256"],
                "work_observations_sha256": work_observations["self_sha256"],
                "g5_control_laws_sha256": control_laws["self_sha256"],
                "mutation_observations_sha256": mutations["self_sha256"],
                "witness_manifest_sha256": manifest["self_sha256"],
            }
            result = SimpleNamespace(
                profile=result.profile,
                receipt=result.receipt,
                extension=build_w5v_extension(
                    result.receipt,
                    parent_extension=predecessor["extension"],
                    evidence=evidence,
                ),
            )
        _write(stage, "parents/w5-parent-index.json", predecessor["index_raw"])
        _write(stage, "parents/w5-parent-profile.json", predecessor["profile_raw"])
        _write(stage, "parents/w5-parent-root.json", predecessor["conversion_root_raw"])
        _write(stage, "parents/w5-parent-law.json", predecessor["law_raw"])
        _write(stage, "parents/w5-parent-g3n-certificate.json", predecessor["certificate_raw"])
        _write(stage, "parents/w5-parent-candidate.json", predecessor["candidate_raw"])
        _write(stage, "parents/w5-parent-status.json", predecessor["status_raw"])
        _write(stage, "parents/w5-parent-measurements.json", predecessor["measurements_raw"])
        _write(stage, "parents/current-w4r-extension.json", predecessor["extension_raw"])
        _write_json(stage, "run-spec/parent-w5.json", parent)
        _write_json(stage, "run-spec/source-identity.json", source_identity)
        _write_json(stage, "profile/conversion-viability-profile.json", dict(result.profile.payload))
        _write_json(stage, "profile/w1-activity-profile.json", dict(geometry.base_profile.payload))
        _write_json(stage, "profile/w1-activity-root.json", geometry.base_profile.contract_root.to_dict())
        _write_json(stage, "profile/w2-geometry-profile.json", dict(geometry.payload))
        _write_json(stage, "profile/w2-geometry-root.json", dict(geometry.contract_root))
        _write_json(stage, "gates/g05v-conversion-viability/conversion-viability.json", dict(result.receipt))
        _write_json(stage, "gates/g05v-conversion-viability/witness-manifest.json", manifest)
        _write_json(stage, "gates/g05v-conversion-viability/raw-activity.json", raw_activity)
        _write_json(stage, "gates/g05v-conversion-viability/work-observations.json", work_observations)
        _write_json(stage, "gates/g05v-conversion-viability/control-law-observations.json", control_laws)
        _write_json(stage, "gates/g05v-conversion-viability/mutation-observations.json", mutations)
        extension_relative = None
        if result.extension is not None:
            extension_relative = f"certificate/extension-{result.extension['chain_ordinal']:04d}.json"
            _write_json(stage, extension_relative, dict(result.extension))
        for relative, raw in witness_copies + control_law_copies + mutation_copies:
            _write(stage, relative, raw)
        independent_input = _build_independent_input(
            predecessor=predecessor,
            source_identity=source_identity,
            result=result,
            raw_activity=raw_activity,
            work_observations=work_observations,
            control_laws=control_laws,
            mutations=mutations,
        )
        _write_json(stage, "verification/independent-input.json", independent_input)
        independent_result = build_embedded_independent_result(stage, w5_root=Path(predecessor["root_path"]))
        _write_json(stage, "verification/independent-result.json", independent_result)
        status = _build_status(
            result,
            predecessor,
            independent_input=independent_input,
            independent_result=independent_result,
            parent_verifier_receipts=parent_verifier_receipts,
            parent_verifier_receipts_sha256=parent_verifier_receipts_sha256,
        )
        _write_json(stage, "gates/g05v-conversion-viability/status.json", status)
        records = _records(stage)
        material = _index_material(
            parent=parent,
            records=records,
            result=result,
            independent_input=independent_input,
            independent_result=independent_result,
            raw_activity=raw_activity,
            work_observations=work_observations,
            parent_verifier_receipts=parent_verifier_receipts,
            parent_verifier_receipts_sha256=parent_verifier_receipts_sha256,
            control_laws=control_laws,
            mutations=mutations,
        )
        index = {
            "parent_verifier_receipts": material["parent_verifier_receipts"],
            "parent_verifier_receipts_sha256": material["parent_verifier_receipts_sha256"],
            "schema": INDEX_SCHEMA,
            "run_id": canonical_hash({**material, "schema": ARTIFACT_DOMAIN}, ARTIFACT_DOMAIN),
            "status": material["status"],
            "proof_status": material["proof_status"],
            "w5_parent_identities": material["w5_parent_identities"],
            "certificate_identities": material["certificate_identities"],
            "failure_artifact": material["failure_artifact"],
            "parents": material["parents"],
            "source_exact_successor_of": material["source_exact_successor_of"],
            "objects": material["objects"],
            "object_count": len(records),
            "gate": material["gate"],
            "conversion_profile_sha256": material["conversion_profile_sha256"],
            "conversion_root_sha256": material["conversion_root_sha256"],
            "law_sha256": material["law_sha256"],
            "viability_profile_sha256": material["viability_profile_sha256"],
            "receipt_sha256": material["receipt_sha256"],
            "certificate_extension_sha256": material["certificate_extension_sha256"],
            "certificate_chain_status": material["certificate_chain_status"],
            "final_certificate_identity_sha256": material["final_certificate_identity_sha256"],
            "independent_input_sha256": material["independent_input_sha256"],
            "independent_result_sha256": material["independent_result_sha256"],
            "raw_activity_sha256": material["raw_activity_sha256"],
            "work_observations_sha256": material["work_observations_sha256"],
            "g5_control_laws_sha256": material["g5_control_laws_sha256"],
            "mutation_observations_sha256": material["mutation_observations_sha256"],
            "fixtures_define_support": False,
        }
        index["self_sha256"] = canonical_hash(index, INDEX_SCHEMA)
        _write_json(stage, "index.json", index)
        output = target_root / index["run_id"]
        if output.exists():
            _require((output / "index.json").is_file(), "content-addressed W5V collision is not an artifact")
            _require((output / "index.json").read_bytes() == (stage / "index.json").read_bytes(), "content-addressed W5V collision has different bytes")
            shutil.rmtree(stage)
        else:
            target_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stage), str(output))
        return output
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def run_artifact(*, output_root: Path | None = None, w5_root: Path | None = None) -> Path:
    """Discover and verify the current W5 predecessor, then publish W5V."""
    return _run(output_root=output_root, w5_root=w5_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--w5-root", type=Path, default=None, help="optional source-exact W5 candidate; default performs current-artifact discovery")
    parser.add_argument("--out", type=Path, default=OUTPUT_ROOT, help="content-addressed W5V artifact parent directory")
    args = parser.parse_args()
    try:
        output = _run(w5_root=args.w5_root, output_root=args.out)
    except Exception as exc:
        print(f"W5V/G5V FAIL: {type(exc).__name__}: {exc}")
        return 1
    index = _read_json(output / "index.json")
    print(canonical_json_bytes({"gate": "G5V", "status": index["status"], "run_id": index["run_id"], "artifact": str(output)}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
