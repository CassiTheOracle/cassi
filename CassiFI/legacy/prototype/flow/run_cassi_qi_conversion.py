"""Build the source-exact W5 centered frozen-Q artifact.

The runner is intentionally thin: W5 evolution is performed only by the public
``transition_w5_integrated`` API.  This module discovers the current verified
W4R artifact, binds all inherited identities, emits raw witnesses, and records
one immutable gate artifact.  It never runs an earlier stage as a second full
step and it never creates a W5V certificate.
"""
from __future__ import annotations

import hashlib
import math
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

import torch

from cassi_qi_carrier import (
    _local_kick,
    _spectral_half,
    carrier_coordinates,
    composition_forces,
    load_w4_carrier_profile,
)
from cassi_qi_conversion import (
    _frozen_q_map,
    load_w5_conversion_profile,
    transition_w5_integrated,
    validate_w5_schedule_receipt,
)

from cassi_qi_field import QiFlowGeometryV2, QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads
from cassi_qi_topology import QiTopologicalRetentionLaw, load_w4r_topology_profile
from cassi_qi_transport import load_w3_transport_profile
from verify_cassi_qi_topology import verify as verify_w4r
ROOT = Path(__file__).resolve().parent

INDEX_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
W4R_INDEX_SCHEMA = "cassi.qi-flow-w4r-retention-core-run-index.v1"
W4R_ARTIFACT_DOMAIN = "cassi.qi-flow-w4r-retention-core"

ARTIFACT_DOMAIN = "cassi.qi-flow-w5-frozen-q-artifact.v1"
RAW_DOMAIN = "cassi.qi-flow-w5-raw-state.v1"
CONTROL_SCHEMA = "cassi.qi-flow-w5-conversion-control.v1"
INTEGRATED_SCHEMA = "cassi.qi-flow-w5-integrated-control.v1"
CANDIDATE_SCHEMA = "cassi.qi-flow-w5-conversion-candidate.v1"
STATUS_SCHEMA = "cassi.qi-flow-g5-status.v1"
MEASUREMENTS_SCHEMA = "cassi.qi-flow-w5-conversion-measurements.v1"
MEASUREMENTS_DOMAIN = MEASUREMENTS_SCHEMA
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w5-conversion-source-identity.v1"
SOURCE_IDENTITY_DOMAIN = SOURCE_IDENTITY_SCHEMA
UPSTREAM_SNAPSHOT_SCHEMA = "cassi.qi-flow-w5-upstream-profile-snapshot.v1"
PARENT_VERIFICATION_SCHEMA = "cassi.qi-flow-parent-verification.v1"
PARENT_VERIFIER_RECEIPTS_SCHEMA = "cassi.qi-flow-parent-verifier-receipts.v1"

# The inventory is deliberately closed.  Do not add aliases: verifier and W5V
# use this list as a source-exact contract.
CONTROL_IDS = (
    "balanced",
    "matched-energy-positive-imbalance",
    "matched-energy-negative-imbalance",
    "yang-heavy",
    "yin-heavy",
    "empty",
    "near-capacity",
    "heterogeneous",
    "multiscale",
    "lambda-off",
    "lambda-and-ema-off",
    "duplicate-invocation",
    "stale-ema",
    "mis-remapped-ema",
    "positive-work-reject",
    "negative-work-dissipative",
    "numerical-zero-work",
    "source-ambiguous-work",
)

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
    "cassi_qi_profile.py",
)
EXPECTED_REJECTS = frozenset(
    {
        "stale-ema",
        "mis-remapped-ema",
        "duplicate-invocation",
        "positive-work-reject",
        "source-ambiguous-work",
    }
)


class ConversionArtifactError(ValueError):
    """The current upstream artifact or W5 evidence is inadmissible."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _obj_sha(value: Any, domain: str) -> str:
    return str(canonical_hash(_plain(value), domain))


def _tag_f64(value: float) -> str:
    if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
        raise ConversionArtifactError("independent verifier returned a noncanonical f64")
    return "f64:" + struct.pack(">d", float(value)).hex()


def _normalise_verifier_result(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalise_verifier_result(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise_verifier_result(item) for item in value]
    if isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        return _tag_f64(value)
    if value is None or isinstance(value, str):
        return value
    raise ConversionArtifactError(
        f"unsupported independent verifier result value: {type(value).__name__}"
    )


def _w4r_verifier_receipts(parent_root: Path) -> tuple[dict[str, Any], str]:
    try:
        result = verify_w4r(parent_root)
    except Exception as exc:
        raise ConversionArtifactError(
            f"W4R independent verification failed: {type(exc).__name__}: {exc}"
        ) from exc
    normalized = _normalise_verifier_result(result)
    if (
        not isinstance(normalized, Mapping)
        or normalized.get("status") != "PASS"
        or normalized.get("schema") != W4R_INDEX_SCHEMA
    ):
        raise ConversionArtifactError("W4R independent verifier did not pass")
    receipt = {
        "schema": PARENT_VERIFICATION_SCHEMA,
        "result": dict(normalized),
        "verification_sha256": _obj_sha(normalized, PARENT_VERIFICATION_SCHEMA),
    }
    receipts = {
        "schema": PARENT_VERIFIER_RECEIPTS_SCHEMA,
        "w4r": receipt,
    }
    return receipts, _obj_sha(receipts, PARENT_VERIFIER_RECEIPTS_SCHEMA)


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = canonical_json_loads(raw)
    except Exception as exc:  # pragma: no cover - diagnostics remain deterministic
        raise ConversionArtifactError(f"invalid JSON object {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ConversionArtifactError(f"JSON object {path} is not a mapping")
    return dict(value), raw


def _is_sha(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _sha_values(value: Any, *, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = f"{prefix}{key}"
            if _is_sha(item):
                result[str(name)] = str(item)
            result.update(_sha_values(item, prefix=f"{name}."))
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            result.update(_sha_values(item, prefix=f"{prefix}{index}."))
    return result


def _find_sha(value: Any, names: Iterable[str]) -> str | None:
    targets = tuple(str(name).lower() for name in names)
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_name = str(key).lower()
            if any(target == key_name or target in key_name for target in targets) and _is_sha(item):
                return str(item)
            found = _find_sha(item, targets)
            if found:
                return found
    elif isinstance(value, (tuple, list)):
        for item in value:
            found = _find_sha(item, targets)
            if found:
                return found
    return None


def _json_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _schema(value: Mapping[str, Any]) -> str:
    return str(value.get("schema", ""))


def _status_evidence(root: Path) -> tuple[bool, dict[str, Any]]:
    accepted = {"PASS", "PASS_W4R_G4R", "PASS_W4R"}
    evidence: dict[str, Any] = {}
    for path in _json_files(root):
        if path.name != "status.json" or path.relative_to(root).as_posix() != "gates/g04r-retention-core/status.json":
            continue
        value, _ = _read_json(path)
        status = str(value.get("status", value.get("decision", "")))
        if status in accepted:
            evidence = {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                **value,
            }
            return True, evidence
    return False, evidence


def _source_records(root: Path, index: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    source_path = root / "run-spec" / "source-identity.json"
    if source_path.is_file():
        value, _ = _read_json(source_path)
        rows = value.get("sources", value.get("source_files", ()))
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    rows = []
    objects = index.get("objects", ())
    if isinstance(objects, list):
        for row in objects:
            if isinstance(row, Mapping) and str(row.get("path", "")).startswith("sources/"):
                rows.append(row)
    return rows


def _source_exact(root: Path, index: Mapping[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    rows = _source_records(root, index)
    if not rows:
        return False, []
    checked: list[dict[str, Any]] = []
    relevant = 0
    for row in rows:
        relative = str(row.get("path", ""))
        if relative.startswith("sources/"):
            relative = relative[len("sources/") :]
        if not relative or relative not in SOURCE_PATHS:
            continue
        relevant += 1
        target = ROOT / relative
        snapshot = root / "sources" / relative
        if not target.is_file() or not snapshot.is_file():
            return False, checked
        current = target.read_bytes()
        expected_raw = snapshot.read_bytes()
        expected_sha = str(row.get("sha256", _sha(expected_raw)))
        if current != expected_raw or _sha(current) != expected_sha:
            return False, checked
        if "byte_count" in row and int(row["byte_count"]) != len(current):
            return False, checked
        checked.append({"path": relative, "byte_count": len(current), "sha256": _sha(current)})
    # W4R owns a smaller source set than W5.  Exactness means every recorded
    # parent source matches this checkout; W5's own source inventory is sealed
    # later and must not be demanded from the parent.
    return relevant > 0 and len(checked) == relevant, checked


def _candidate_run_roots() -> list[Path]:
    """Find every W4R-like run root; selection is done by proof, never mtime."""
    diag = ROOT / "_diag"
    if not diag.is_dir():
        return []
    roots: list[Path] = []
    for family in sorted(diag.glob("cassi-qi-flow-w4r*-final")):
        if not family.is_dir():
            continue
        if (family / "index.json").is_file():
            roots.append(family)
        for child in sorted(family.iterdir()):
            if child.is_dir() and (child / "index.json").is_file():
                roots.append(child)
    return roots


def _find_object(
    root: Path,
    *,
    digest: str | None = None,
    path_tokens: Iterable[str] = (),
    schema_tokens: Iterable[str] = (),
    exclude_tokens: Iterable[str] = (),
) -> tuple[dict[str, Any], bytes, Path] | None:
    path_tokens = tuple(str(token).lower() for token in path_tokens)
    schema_tokens = tuple(str(token).lower() for token in schema_tokens)
    exclude_tokens = tuple(str(token).lower() for token in exclude_tokens)
    for path in _json_files(root):
        relative = str(path.relative_to(root)).replace("\\", "/").lower()
        if any(token not in relative for token in path_tokens):
            continue
        if any(token in relative for token in exclude_tokens):
            continue
        try:
            value, raw = _read_json(path)
        except ConversionArtifactError:
            continue
        if digest:
            values = set(_sha_values(value).values())
            if digest not in values:
                continue
        if schema_tokens and not any(token in _schema(value).lower() for token in schema_tokens):
            continue
        return value, raw, path
    return None


def _parent_identity(index: Mapping[str, Any], root: Path, object_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Retain exact W4/W3N ancestry without trusting a pinned run identifier."""
    identities: dict[str, Any] = {
        "run_id": str(index.get("run_id", root.name)),
        "index_sha256": _sha((root / "index.json").read_bytes()),
        "status": index.get("status"),
        "preserved": True,
        "source_exact": True,
    }
    for name, path in object_paths.items():
        value, raw = _read_json(path)
        identities[f"{name}_path"] = str(path.relative_to(root)).replace("\\", "/")
        identities[f"{name}_file_sha256"] = _sha(raw)
        if name == "profile" and _is_sha(value.get("profile_sha256")):
            identities["profile_sha256"] = value["profile_sha256"]
        elif name == "root" and _is_sha(value.get("self_sha256", value.get("root_sha256"))):
            identities["root_sha256"] = value.get("self_sha256", value.get("root_sha256"))
        elif name == "candidate" and _is_sha(value.get("self_sha256")):
            identities["candidate_sha256"] = value["self_sha256"]
        elif name == "extension" and _is_sha(value.get("self_sha256", value.get("extension_sha256"))):
            identities["extension_sha256"] = value.get("self_sha256", value.get("extension_sha256"))
        for key in ("profile_sha256", "root_sha256", "self_sha256", "candidate_sha256", "certificate_extension_sha256", "extension_sha256"):
            if _is_sha(value.get(key)):
                identities[f"{name}_{key}"] = value[key]
    # Keep all registered parent identities exactly as supplied by W4R.  This
    # preserves both the W4 and W3N links even when their file names evolve.
    upstream_parent = index.get("parent")
    if not isinstance(upstream_parent, Mapping):
        upstream_parent = index.get("parents", ())
    identities["index_parent"] = _plain(upstream_parent)
    identities["index_parents"] = _plain(index.get("parents", ()))
    identities["source_exact_successor_of"] = _plain(index.get("source_exact_successor_of", {}))
    identities["parent_identities"] = _plain(index.get("parent_identities", {}))
    return identities


def _discover_w4r_parent() -> dict[str, Any]:
    valid: list[dict[str, Any]] = []
    for root in _candidate_run_roots():
        try:
            index, index_raw = _read_json(root / "index.json")
            if (
                _schema(index) != W4R_INDEX_SCHEMA
                or str(index.get("domain", index.get("artifact_domain", ""))) != W4R_ARTIFACT_DOMAIN
            ):
                continue
            run_id = str(index.get("run_id", ""))
            if run_id and run_id != root.name:
                continue
            status_ok, gate_status = _status_evidence(root)
            if not status_ok:
                continue
            exact, source_rows = _source_exact(root, index)
            if not exact:
                continue
            profile_sha = _find_sha(
                index,
                ("topology_profile_sha256", "retention_profile_sha256", "profile_sha256"),
            )
            root_sha = _find_sha(
                index,
                (
                    "topology_root_sha256",
                    "retention_root_sha256",
                    "profile_root_sha256",
                    "root_sha256",
                ),
            )
            candidate_sha = _find_sha(index, ("candidate_sha256", "topology_candidate_sha256", "retention_candidate_sha256"))
            extension_sha = _find_sha(index, ("certificate_extension_sha256", "extension_sha256"))
            profile_obj = _find_object(root, digest=profile_sha, schema_tokens=("profile",), exclude_tokens=("index",))
            root_obj = _find_object(root, digest=root_sha, schema_tokens=("root",), exclude_tokens=("index",))
            candidate_obj = _find_object(root, digest=candidate_sha, schema_tokens=("candidate",), exclude_tokens=("parents/",))
            extension_obj = _find_object(root, digest=extension_sha, schema_tokens=("extension",), path_tokens=("certificate",))
            if profile_obj is None:
                profile_obj = _find_object(root, schema_tokens=("topology-profile", "retention-profile"), exclude_tokens=("index",))
            if root_obj is None:
                root_obj = _find_object(root, schema_tokens=("topology-root", "retention-root"), exclude_tokens=("index",))
            if candidate_obj is None:
                candidate_obj = _find_object(root, schema_tokens=("candidate",), exclude_tokens=("parents/", "index"))
            if extension_obj is None:
                extension_obj = _find_object(root, schema_tokens=("extension",), path_tokens=("certificate",))
            if not all((profile_obj, root_obj, candidate_obj, extension_obj)):
                continue
            cert_obj = _find_object(root, schema_tokens=("numerical-certificate",), path_tokens=("certificate",))
            if cert_obj is None:
                cert_obj = _find_object(root, path_tokens=("certificate", "g3n-certificate-root"))
            if cert_obj is None:
                continue
            object_paths = {
                "profile": profile_obj[2],
                "root": root_obj[2],
                "candidate": candidate_obj[2],
                "extension": extension_obj[2],
                "certificate": cert_obj[2],
            }
            parent = _parent_identity(index, root, object_paths)
            parent.update(
                {
                    "root": root,
                    "index": index,
                    "index_raw": index_raw,
                    "gate_status": gate_status,
                    "source_rows": source_rows,
                    "profile": profile_obj[0],
                    "profile_raw": profile_obj[1],
                    "root_object": root_obj[0],
                    "root_raw": root_obj[1],
                    "candidate": candidate_obj[0],
                    "candidate_raw": candidate_obj[1],
                    "extension": extension_obj[0],
                    "extension_raw": extension_obj[1],
                    "certificate": cert_obj[0],
                    "certificate_raw": cert_obj[1],
                    "object_paths": object_paths,
                }
            )
            valid.append(parent)
        except (OSError, ConversionArtifactError, ValueError, TypeError):
            continue
    if len(valid) != 1:
        raise ConversionArtifactError(f"expected exactly one current source-exact verified W4R parent, found {len(valid)}")
    parent = valid[0]
    receipts, receipts_sha = _w4r_verifier_receipts(parent["root"])
    parent["parent_verifier_receipt"] = receipts["w4r"]
    parent["parent_verifier_receipts"] = receipts
    parent["parent_verifier_receipts_sha256"] = receipts_sha
    return parent


def _profile_identity(profile: Any) -> dict[str, Any]:
    payload = getattr(profile, "payload", None)
    root = getattr(profile, "root", None)
    if root is None:
        contract = getattr(profile, "contract_root", None)
        root = getattr(contract, "payload", contract)
    result: dict[str, Any] = {
        "profile_sha256": getattr(profile, "profile_sha256", None),
        "root_sha256": getattr(profile, "root_sha256", None),
        "contract_root_sha256": getattr(profile, "contract_root_sha256", None),
        "semantic_sha256": getattr(profile, "semantic_sha256", None),
    }
    result = {key: value for key, value in result.items() if value is not None}
    return {"payload": _plain(payload), "root": _plain(root), "identity": result}


def _extract_parent_sha(index: Mapping[str, Any], parent: Mapping[str, Any]) -> dict[str, str]:
    aliases = {
        "w2_profile_sha256": ("w2_profile_sha256", "geometry_profile_sha256"),
        "w2_contract_root_sha256": ("w2_contract_root_sha256", "geometry_contract_sha256"),
        "w2_geometry_contract_sha256": ("w2_geometry_contract_sha256",),
        "w2_operator_semantic_sha256": ("w2_operator_semantic_sha256", "operator_semantic_sha256"),
        "w3_transport_profile_sha256": ("w3_transport_profile_sha256", "transport_profile_sha256", "w3_profile_sha256"),
        "w3_transport_root_sha256": ("w3_transport_root_sha256", "transport_root_sha256"),
        "w3_transport_semantic_sha256": ("w3_transport_semantic_sha256", "transport_semantic_sha256"),
        "w4_carrier_profile_sha256": ("w4_carrier_profile_sha256", "carrier_profile_sha256"),
        "w4_carrier_root_sha256": ("w4_carrier_root_sha256", "carrier_root_sha256"),
        "w4r_topology_profile_sha256": (
            "w4r_topology_profile_sha256",
            "topology_profile_sha256",
            "retention_profile_sha256",
            "profile_sha256",
        ),
        "w4r_topology_root_sha256": (
            "w4r_topology_root_sha256",
            "topology_root_sha256",
            "retention_root_sha256",
            "profile_root_sha256",
            "root_sha256",
        ),
    }
    haystack = dict(_sha_values(index))
    haystack.update(_sha_values(parent.get("parent_identities", {})))
    selected: dict[str, str] = {}
    for key, names in aliases.items():
        for name, digest in tuple(haystack.items()):
            leaf = name.rsplit(".", 1)[-1]
            if leaf in names or name in names:
                selected[key] = digest
                break
        if key not in selected:
            continue
    return {key: value for key, value in selected.items() if _is_sha(value)}


def _materialize_profiles(parent: Mapping[str, Any]) -> dict[str, Any]:
    geometry = load_w2_geometry_profile()
    transport = load_w3_transport_profile(geometry_profile=geometry)
    carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
    parent_profile = parent.get("profile", {})
    if isinstance(parent_profile, Mapping) and isinstance(parent_profile.get("payload"), Mapping):
        parent_profile = parent_profile["payload"]
    mode = str(parent_profile.get("mode", parent_profile.get("law_id", "topological-v1")))
    if mode not in {"topological-v1", "fading-v1"}:
        mode = "topological-v1"
    topology = load_w4r_topology_profile(
        geometry=geometry,
        mode=mode,
        carrier_profile=carrier,
        numerical_certificate=parent["certificate"],
    )
    supplied = _extract_parent_sha(parent["index"], parent)
    # Profile identities from the loaded, validated objects are the source of
    # truth.  Parent fields are retained only where they agree with those
    # objects; a mismatch proves that the W4R artifact is stale.
    expected = {
        "w2_profile_sha256": getattr(geometry, "profile_sha256", None),
        "w2_contract_root_sha256": getattr(geometry, "contract_root_sha256", None),
        "w3_transport_profile_sha256": getattr(transport, "profile_sha256", None),
        "w3_transport_root_sha256": getattr(transport, "contract_root_sha256", None),
        "w3_transport_semantic_sha256": getattr(transport, "transport_semantic_sha256", None),
        "w4_carrier_profile_sha256": getattr(carrier, "profile_sha256", None),
        "w4_carrier_root_sha256": getattr(carrier, "root_sha256", None),
        "w4r_topology_profile_sha256": getattr(topology, "profile_sha256", None),
        "w4r_topology_root_sha256": getattr(topology, "root_sha256", None),
    }
    for key, value in supplied.items():
        if key in expected and expected[key] and value != expected[key]:
            raise ConversionArtifactError(f"current W4R parent {key} disagrees with materialized profile")
    identities = {key: value for key, value in expected.items() if _is_sha(value)}
    identities.update({key: value for key, value in supplied.items() if key in identities and value == identities[key]})
    if _is_sha(parent.get("candidate_sha256")):
        identities["w4r_candidate_sha256"] = parent["candidate_sha256"]
    if _is_sha(parent.get("extension_sha256")):
        identities["w4r_extension_sha256"] = parent["extension_sha256"]
    upstream_parent = parent.get("index", {}).get("parent", {})
    if isinstance(upstream_parent, Mapping):
        for key, value in upstream_parent.items():
            if str(key).lower().endswith("sha256") and _is_sha(value):
                identities[str(key)] = value
    conversion = load_w5_conversion_profile(
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=carrier,
        topology_profile=topology,
        parent_identities=identities,
    )
    return {
        "geometry": geometry,
        "transport": transport,
        "carrier": carrier,
        "topology": topology,
        "conversion": conversion,
        "certificate": parent["certificate"],
        "identities": identities,
    }


def _active_count(geometry: Any, scale: int, mode_count: int) -> int:
    shapes = getattr(geometry, "active_shapes", None)
    if not isinstance(shapes, (tuple, list)) or not (0 <= scale < len(shapes)):
        raise ConversionArtifactError(f"geometry lacks active shape for scale {scale}")
    shape = shapes[scale]
    if not isinstance(shape, (tuple, list)) or len(shape) != 2:
        raise ConversionArtifactError(f"geometry active shape is invalid for scale {scale}")
    count = int(shape[0]) * int(shape[1])
    if not (0 < count <= mode_count):
        raise ConversionArtifactError(f"geometry active count is invalid for scale {scale}")
    return count


def _state_for_control(control_id: str, geometry: Any, profile: Any) -> QiFlowStateV3:
    state = QiFlowStateV3.create(geometry.base_profile, batch_lanes=1)
    field = state.field.detach().clone()
    scales, packed, batch = (int(field.shape[0]), int(field.shape[1]), int(field.shape[2]))
    mode_count = int(geometry.base_profile.state_layout["mode_count"])
    if packed != 9 * mode_count or batch != 1:
        raise ConversionArtifactError("materialized geometry has an unsupported dynamic packed layout")
    rho_max = float(profile.rho_max)
    cap = float(profile.component_abs_max)
    rho_scale = math.sqrt(rho_max)
    if not rho_scale < cap:
        raise ConversionArtifactError("registered W5 support cannot host near-capacity fixture")
    total_amp = rho_scale * 0.22
    phi = float(profile.phi)
    balanced_i = total_amp / math.sqrt(1.0 + phi)
    balanced_y = math.sqrt(phi) * balanced_i
    if control_id in {"empty"}:
        balanced_y = balanced_i = 0.0
    elif control_id == "matched-energy-positive-imbalance":
        balanced_y *= 1.35
    elif control_id == "positive-work-reject":
        balanced_y = rho_scale * 0.90
        balanced_i = rho_scale * 0.05
        density = balanced_y * balanced_y + balanced_i * balanced_i
        if not (balanced_y < cap and density < rho_max):
            raise ConversionArtifactError("positive-work fixture exceeds registered W5 guard")
        if not balanced_y > math.sqrt(phi) * balanced_i:
            raise ConversionArtifactError("positive-work fixture is not Yang-heavy")
    elif control_id in {"matched-energy-negative-imbalance", "negative-work-dissipative"}:
        balanced_i *= 1.35
    elif control_id == "yang-heavy":
        balanced_y *= 1.8
    elif control_id == "yin-heavy":
        balanced_i *= 1.8
    elif control_id == "near-capacity":
        total_amp = rho_scale * 0.95
        balanced_i = total_amp / math.sqrt(1.0 + phi)
        balanced_y = math.sqrt(phi) * balanced_i
    elif control_id == "source-ambiguous-work":
        ambiguous_amp = math.sqrt(float(profile.energy_uncertainty)) * 0.5
        balanced_i = ambiguous_amp / math.sqrt(1.0 + phi)
        balanced_y = math.sqrt(phi) * balanced_i * 0.98
    elif control_id == "numerical-zero-work":
        balanced_y = math.sqrt(phi) * balanced_i
    if control_id == "heterogeneous":
        scale_variation = True
    else:
        scale_variation = False
    for scale in range(scales):
        active = _active_count(geometry, scale, mode_count)
        if active <= 0:
            continue
        indices = torch.arange(active, device=field.device, dtype=field.dtype)
        phase = (indices + float(scale + 1)) * (0.17 if control_id in {"heterogeneous", "multiscale"} else 0.0)
        factor = 1.0 + (0.08 * float(scale)) if scale_variation or control_id == "multiscale" else 1.0
        y_amp = balanced_y * factor
        i_amp = balanced_i * (2.0 - factor if scale_variation else 1.0)
        if control_id == "empty":
            y_amp = i_amp = 0.0
        y_re = y_amp * torch.cos(phase)
        y_im = y_amp * torch.sin(phase)
        i_re = i_amp * torch.cos(phase + 0.23)
        i_im = i_amp * torch.sin(phase + 0.23)
        base = 0
        field[scale, base + 0 * mode_count : base + 1 * mode_count, 0][:active] = y_re
        field[scale, base + 1 * mode_count : base + 2 * mode_count, 0][:active] = y_im
        field[scale, base + 2 * mode_count : base + 3 * mode_count, 0][:active] = i_re
        field[scale, base + 3 * mode_count : base + 4 * mode_count, 0][:active] = i_im
        # A controlled velocity pattern keeps the Hamiltonian complete while
        # leaving the frozen-Q map's velocity invariance directly testable.
        velocity = 0.01 * total_amp * (1.0 + 0.05 * scale)
        field[scale, base + 4 * mode_count : base + 5 * mode_count, 0][:active] = velocity * torch.sin(phase)
        field[scale, base + 5 * mode_count : base + 6 * mode_count, 0][:active] = velocity * torch.cos(phase)
        field[scale, base + 6 * mode_count : base + 7 * mode_count, 0][:active] = velocity * torch.cos(phase + 0.13)
        field[scale, base + 7 * mode_count : base + 8 * mode_count, 0][:active] = velocity * torch.sin(phase + 0.13)
        ema = 0.0
        if control_id in {"heterogeneous", "multiscale"}:
            ema = float(profile.epsilon2_ema_max) * 0.2
        field[scale, base + 8 * mode_count : base + 9 * mode_count, 0][:active] = ema
    if control_id in {"stale-ema", "mis-remapped-ema"}:
        # Deliberately bypass construction validation so the public integrated
        # guard records a closed rejection and no candidate can be committed.
        bad_scale = 0 if control_id == "stale-ema" else scales - 1
        bad_index = 8 * mode_count
        field[bad_scale, bad_index, 0] = float(profile.epsilon2_ema_max) * 2.0 + 1.0
        return QiFlowStateV3(field)
    return QiFlowStateV3.from_field(geometry.base_profile, field)


def _raw_f64(state: QiFlowStateV3) -> bytes:
    tensor = state.field.detach().contiguous().cpu()
    if tensor.dtype != torch.float64:
        tensor = tensor.to(dtype=torch.float64)
    return tensor.numpy().astype("<f8", copy=False).tobytes(order="C")
def _raw_state_hash(raw: bytes) -> str:
    digest = hashlib.sha256()
    domain = RAW_DOMAIN.encode("utf-8")
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _replay_center_map_witness(
    state: QiFlowStateV3,
    *,
    profiles: Mapping[str, Any],
    conversion_enabled: bool,
    duration_s: float,
    receipt: Mapping[str, Any],
) -> tuple[QiFlowStateV3, QiFlowStateV3]:
    """Replay only the offline pre-center stages and the exact frozen-Q map."""
    geometry = profiles["geometry"]
    carrier = profiles["carrier"]
    topology = profiles["topology"]
    conversion = profiles["conversion"]
    topology_law = QiTopologicalRetentionLaw.bind(topology, geometry)
    values = carrier_coordinates(state, geometry=geometry, profile=carrier)
    first_local, first_values, _ = _local_kick(
        state,
        values,
        geometry=geometry,
        profile=carrier,
        duration=duration_s,
        potential_enabled=True,
        additional_force=topology_law.additional_force,
    )
    center_input, _, _ = _spectral_half(
        first_local,
        first_values,
        geometry=geometry,
        profile=carrier,
        duration=0.5 * duration_s,
    )
    center_output, _, _ = _frozen_q_map(
        center_input,
        geometry=geometry,
        profile=conversion,
        carrier_profile=carrier,
        duration_s=duration_s,
        lambda_rate=conversion.lambda_rate if conversion_enabled else 0.0,
    )
    witness = receipt.get("attempted_center_map_witness")
    if not isinstance(witness, Mapping):
        raise ConversionArtifactError("rejected work receipt has no center-map witness")
    if witness.get("raw_domain") != RAW_DOMAIN or witness.get("dtype") != "<f8":
        raise ConversionArtifactError("center-map witness raw representation is not W5 little-endian float64")
    input_raw = _raw_f64(center_input)
    output_raw = _raw_f64(center_output)
    if witness.get("input_state_sha256") != _raw_state_hash(input_raw):
        raise ConversionArtifactError("offline center-map input disagrees with receipt witness")
    if witness.get("output_state_sha256") != _raw_state_hash(output_raw):
        raise ConversionArtifactError("offline center-map output disagrees with receipt witness")
    for key, raw in (("input", input_raw), ("output", output_raw)):
        descriptor = witness.get(key)
        if not isinstance(descriptor, Mapping):
            raise ConversionArtifactError(f"center-map witness lacks {key} descriptor")
        if descriptor.get("sha256") != _sha(raw) or descriptor.get("raw_sha256") != _raw_state_hash(raw):
            raise ConversionArtifactError(f"center-map {key} descriptor disagrees with replay")
    return center_input, center_output



def _raw_descriptor(path: str, raw: bytes, state: QiFlowStateV3) -> dict[str, Any]:
    return {
        "path": path,
        "byte_count": len(raw),
        "sha256": _sha(raw),
        "domain": RAW_DOMAIN,
        "dtype": "<f8",
        "shape": [int(value) for value in state.field.shape],
    }


def _energy_rows(state: QiFlowStateV3, *, geometry: Any, carrier: Any, topology: Any) -> dict[str, Any]:
    """Compute complete pre/post Hamiltonian components without advancing time."""
    values = carrier_coordinates(state, geometry=geometry, profile=carrier)
    surface = QiFlowGeometryV2(state, geometry)._surface
    rows: list[dict[str, Any]] = []
    kinetic = gradient = local = 0.0
    for scale, (d, c, vd, vc) in enumerate(zip(values.d, values.c, values.vd, values.vc, strict=True)):
        area = float(surface.cell_area_m2(scale))
        entries: dict[str, Any] = {"scale": scale}
        scale_kinetic = scale_gradient = scale_local = 0.0
        for label, position, velocity, weight, speed, omega, kappa in (
            ("D", d, vd, carrier.w_d, carrier.c_d[scale], carrier.omega_d[scale], carrier.kappa_d[scale]),
            ("C", c, vc, carrier.w_c, carrier.c_c[scale], carrier.omega_c[scale], carrier.kappa_c[scale]),
        ):
            grad = surface.gradient(position, scale=scale)
            k = float((weight * 0.5 * velocity.abs().square().sum() * area).item())
            g = float((weight * 0.5 * speed * speed * grad.abs().square().sum() * area).item())
            l = float((weight * (0.5 * omega * omega * position.abs().square().sum() + 0.25 * kappa * position.abs().square().square().sum()) * area).item())
            entries[label] = {"kinetic": k, "gradient": g, "local": l, "total": k + g + l}
            scale_kinetic += k
            scale_gradient += g
            scale_local += l
        entries["kinetic"] = scale_kinetic
        entries["gradient"] = scale_gradient
        entries["local"] = scale_local
        entries["total"] = scale_kinetic + scale_gradient + scale_local
        rows.append(entries)
        kinetic += scale_kinetic
        gradient += scale_gradient
        local += scale_local
    composition = float(sum(float(value) for value in composition_forces(state, geometry=geometry, profile=carrier)[3]))
    topo_law = QiTopologicalRetentionLaw.bind(topology, geometry)
    u_topo = float(topo_law.potential(state))
    return {
        "kinetic": kinetic,
        "gradient": gradient,
        "local": local,
        "composition": composition,
        "link": 0.0,
        "U_topo": u_topo,
        "total": kinetic + gradient + local + composition + u_topo,
        "per_scale": rows,
    }


def _expected_decision(control_id: str) -> str:
    return "REJECT" if control_id in EXPECTED_REJECTS else "PASS"


def _control_flags(control_id: str) -> tuple[bool, bool]:
    if control_id == "lambda-off":
        return False, True
    if control_id == "lambda-and-ema-off":
        return False, False
    return True, True


def _run_control(control_id: str, profiles: Mapping[str, Any]) -> dict[str, Any]:
    """Run one integrated witness and keep every exposed raw intermediate."""
    geometry = profiles["geometry"]
    conversion = profiles["conversion"]
    try:
        state = _state_for_control(control_id, geometry, conversion)
    except Exception as exc:
        return {
            "schema": INTEGRATED_SCHEMA,
            "control_id": control_id,
            "kind": "integrated-w5-centered-frozen-q",
            "duration_s": None,
            "duration_rational": None,
            "conversion_enabled": _control_flags(control_id)[0],
            "epsilon_ema_enabled": _control_flags(control_id)[1],
            "expected_decision": _expected_decision(control_id),
            "actual_decision": "REJECT",
            "committable": False,
            "candidate_exposed": False,
            "failure_reason": f"fixture construction rejected: {type(exc).__name__}: {exc}",
            "no_mutation_on_reject": True,
            "no_extra_persistent_state": True,
            "fixtures": {},
            "_raw_payload": {},
        }
    predecessor_raw = _raw_f64(state)
    conversion_enabled, ema_enabled = _control_flags(control_id)
    source = {
        "control_id": control_id,
        "source_kind": "w5-runner-fixture",
        "raw_sha256": _sha(predecessor_raw),
    }
    try:
        step = transition_w5_integrated(
            state,
            geometry_profile=geometry,
            transport_profile=profiles["transport"],
            carrier_profile=profiles["carrier"],
            topology_profile=profiles["topology"],
            conversion_profile=conversion,
            numerical_certificate=profiles["certificate"],
            duration_s=float(conversion.h_min),
            conversion_enabled=conversion_enabled,
            epsilon_ema_enabled=ema_enabled,
            source=source,
        )
    except Exception as exc:
        step = None
        failure_reason = f"integrated transition raised: {type(exc).__name__}: {exc}"
    else:
        failure_reason = getattr(step, "failure_reason", None)
    receipt = _plain(getattr(step, "receipt", {})) if step is not None else {}
    if not isinstance(receipt, Mapping):
        receipt = {}
    receipt = dict(receipt)
    core_candidate = getattr(step, "candidate", None) if step is not None else None
    core_committable = bool(getattr(step, "committable", False)) if step is not None else False
    actual = "PASS" if core_committable else "REJECT"
    if control_id == "positive-work-reject":
        work_energy = receipt.get("energy", {})
        classification = (
            work_energy.get("work_classification")
            if isinstance(work_energy, Mapping)
            else None
        )
        if actual != "REJECT" or classification != "resolved-positive":
            raise ConversionArtifactError(
                "positive-work fixture did not produce a resolved-positive rejection"
            )
    candidate_raw: bytes | None = _raw_f64(core_candidate) if core_candidate is not None else None
    if not core_committable and candidate_raw is not None:
        # The core contract promises no candidate on rejection.  Keep this
        # check explicit so a future regression cannot be sealed silently.
        if candidate_raw != predecessor_raw:
            raise ConversionArtifactError(f"{control_id}: rejected integrated step mutated predecessor")

    duplicate_rejection: dict[str, Any] | None = None
    if control_id == "duplicate-invocation" and core_committable:
        # Duplicate the unique center marker only in an uncommittable receipt
        # candidate.  This exercises the pure schedule validator without a
        # second field transition.
        mutated = _plain(receipt)
        carrier = mutated.get("carrier_split_receipt", {})
        schedule = carrier.get("stage_schedule", {}) if isinstance(carrier, Mapping) else {}
        stages = schedule.get("stages", []) if isinstance(schedule, Mapping) else []
        if isinstance(stages, list) and len(stages) >= 2:
            stages[1] = dict(stages[1])
            stages[1]["name"] = "centered_conversion_placeholder"
        try:
            validate_w5_schedule_receipt(mutated)
        except Exception as exc:
            duplicate_rejection = {
                "attempted": True,
                "committable": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "mutated_receipt": mutated,
            }
            actual = "REJECT"
            core_committable = False
        else:
            duplicate_rejection = {
                "attempted": True,
                "committable": True,
                "reason": "schedule validator accepted duplicate marker",
                "mutated_receipt": mutated,
            }
    intermediates = getattr(step, "intermediates", {}) if step is not None else {}
    if not isinstance(intermediates, Mapping):
        intermediates = {}
    rejected_work = isinstance(receipt.get("work_rejection_witness"), Mapping)
    if rejected_work:
        center_witness_input, center_witness_output = _replay_center_map_witness(
            state,
            profiles=profiles,
            conversion_enabled=conversion_enabled,
            duration_s=float(conversion.h_min),
            receipt=receipt,
        )
    else:
        center_witness_input = intermediates.get("post_first_spectral_pre_center")
        center_witness_output = intermediates.get("post_center_conversion")
    raw_payload: dict[str, tuple[bytes, QiFlowStateV3]] = {"predecessor": (predecessor_raw, state)}
    if candidate_raw is not None and core_candidate is not None:
        raw_payload["candidate"] = (candidate_raw, core_candidate)
    stage_keys = {
        "w3n_guarded_transport": "post_first_kick",
        "w4_corrected_carrier": "post_first_spectral_pre_center",
        "w4r_hamiltonian_topology": "post_second_kick_pre_ema",
        "w5_conversion": "candidate_post_ema",
        "center_map_input": "post_first_spectral_pre_center",
        "center_map_output": "post_center_conversion",
    }
    for intermediate_key, value in intermediates.items():
        if isinstance(value, QiFlowStateV3):
            raw_payload[f"intermediate_{intermediate_key}"] = (_raw_f64(value), value)
    if isinstance(center_witness_input, QiFlowStateV3):
        raw_payload["center_map_input"] = (_raw_f64(center_witness_input), center_witness_input)
    if isinstance(center_witness_output, QiFlowStateV3):
        raw_payload["center_map_output"] = (_raw_f64(center_witness_output), center_witness_output)
    for fixture_name, intermediate_key in stage_keys.items():
        value = intermediates.get(intermediate_key)
        if isinstance(value, QiFlowStateV3):
            raw_payload[fixture_name] = (_raw_f64(value), value)
    fixtures: dict[str, Any] = {}
    for name, (raw, witness_state) in raw_payload.items():
        relative = f"fixtures/{control_id}-{name.replace('_', '-')}.f64le"
        fixtures[name] = _raw_descriptor(relative, raw, witness_state)
    integrated: dict[str, Any] = {
        "schema": INTEGRATED_SCHEMA,
        "control_id": control_id,
        "kind": "integrated-w5-centered-frozen-q",
        "duration_s": float(conversion.h_min),
        "duration_rational": _plain(receipt.get("duration_rational", {})),
        "conversion_enabled": conversion_enabled,
        "epsilon_ema_enabled": ema_enabled,
        "expected_decision": _expected_decision(control_id),
        "actual_decision": actual,
        "committable": core_committable,
        "core_committable": bool(getattr(step, "committable", False)) if step is not None else False,
        "predecessor_raw_sha256": _sha(predecessor_raw),
        "candidate_raw_sha256": _sha(candidate_raw) if candidate_raw is not None else None,
        "candidate_exposed": candidate_raw is not None and core_committable,
        "receipt_sha256": _sha(canonical_json_bytes(receipt)),
        "receipt_self_sha256": receipt.get("self_sha256"),
        "receipt": receipt,
        "stage_order": _plain(receipt.get("stage_order", ())),
        "stage_trace": _plain(receipt.get("carrier_split_receipt", {}).get("stage_schedule", {})),
        "center_map_invocations": int(receipt.get("conversion", {}).get("center_map_invocations", 0)),
        "analytic_q_alpha_t_rows": _plain(receipt.get("conversion", {}).get("rows", ())),
        "process_clock": _plain(receipt.get("process_clock", {})),
        "phase_branches": _plain(receipt.get("conversion", {}).get("phase_branches", {})),
        "ema_rows": _plain(receipt.get("ema", {}).get("rows", ())),
        "energy": _plain(receipt.get("energy", {})),
        "work_witness": _plain(receipt.get("work_witness", {})),
        "work_rejection_witness": _plain(receipt.get("work_rejection_witness", {})),
        "attempted_center_map_witness": _plain(receipt.get("attempted_center_map_witness", {})),
        "guards": _plain(receipt.get("guards", {})),
        "failure_reason": failure_reason,
        "no_mutation_on_reject": (
            (not core_committable and candidate_raw is None)
            or (control_id == "duplicate-invocation" and duplicate_rejection is not None and not duplicate_rejection.get("committable"))
        ),
        "no_extra_persistent_state": bool(
            receipt.get("additional_state", False) is False
            and receipt.get("guards", {}).get("no_extra_persistent_state", True)
        ),
        "fixtures": fixtures,
        "intermediate_state_keys": sorted(str(key) for key in intermediates),
        "duplicate_invocation": duplicate_rejection,
        "_raw_payload": raw_payload,
    }
    try:
        if (
            core_candidate is None
            and isinstance(center_witness_input, QiFlowStateV3)
            and isinstance(center_witness_output, QiFlowStateV3)
        ):
            pre_energy = _energy_rows(
                center_witness_input,
                geometry=geometry,
                carrier=profiles["carrier"],
                topology=profiles["topology"],
            )
            post_energy = _energy_rows(
                center_witness_output,
                geometry=geometry,
                carrier=profiles["carrier"],
                topology=profiles["topology"],
            )
        else:
            pre_energy = _energy_rows(
                state,
                geometry=geometry,
                carrier=profiles["carrier"],
                topology=profiles["topology"],
            )
            post_energy = (
                _energy_rows(
                    core_candidate,
                    geometry=geometry,
                    carrier=profiles["carrier"],
                    topology=profiles["topology"],
                )
                if core_candidate is not None
                else pre_energy
            )
        integrated["complete_energy"] = {"pre": pre_energy, "post": post_energy}
    except Exception as exc:
        integrated["complete_energy"] = {
            "error": f"measurement failed: {type(exc).__name__}: {exc}",
            "pre": _plain(receipt.get("energy", {}).get("hamiltonian_before", {})),
            "post": _plain(receipt.get("energy", {}).get("hamiltonian_after", {})),
        }
    return integrated


def _snapshot_parent(stage: Path, parent: Mapping[str, Any]) -> None:
    files = {
        "parents/w4r-parent-index.json": parent["index_raw"],
        "parents/w4r-parent-candidate.json": parent["candidate_raw"],
        "parents/w4r-parent-profile.json": parent["profile_raw"],
        "parents/w4r-parent-root.json": parent["root_raw"],
        "parents/w4r-parent-extension-0003.json": parent["extension_raw"],
        "certificate/g3n-certificate-root.json": parent["certificate_raw"],
        "certificate/w4r-extension-0003.json": parent["extension_raw"],
    }
    for relative, raw in files.items():
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def _write_bytes(stage: Path, relative: str, raw: bytes) -> dict[str, Any]:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": relative, "byte_count": len(raw), "sha256": _sha(raw)}


def _write_json(stage: Path, relative: str, value: Any) -> dict[str, Any]:
    return _write_bytes(stage, relative, canonical_json_bytes(_plain(value)))


def _build_source_identity(stage: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        raw = (ROOT / relative).read_bytes()
        _write_bytes(stage, f"sources/{relative}", raw)
        rows.append({"path": relative, "byte_count": len(raw), "sha256": _sha(raw)})
    identity: dict[str, Any] = {
        "schema": SOURCE_IDENTITY_SCHEMA,
        "domain": SOURCE_IDENTITY_DOMAIN,
        "source_exact": True,
        "sources": rows,
    }
    identity["self_sha256"] = _obj_sha(identity, SOURCE_IDENTITY_DOMAIN)
    _write_json(stage, "run-spec/source-identity.json", identity)
    return identity


def _build_upstream_snapshot(stage: Path, profiles: Mapping[str, Any], parent: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = {
        "schema": UPSTREAM_SNAPSHOT_SCHEMA,
        "geometry": _profile_identity(profiles["geometry"]),
        "transport": _profile_identity(profiles["transport"]),
        "carrier": _profile_identity(profiles["carrier"]),
        "topology": _profile_identity(profiles["topology"]),
        "numerical_certificate": {
            "identity": {
                key: value
                for key, value in parent["certificate"].items()
                if str(key).lower().endswith("_sha256")
            },
        },
    }
    snapshot["self_sha256"] = _obj_sha(snapshot, UPSTREAM_SNAPSHOT_SCHEMA)
    _write_json(stage, "run-spec/upstream-profiles.json", snapshot)
    return snapshot


def _artifact_objects(stage: Path) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or path.name == "index.json":
            continue
        relative = str(path.relative_to(stage)).replace("\\", "/")
        raw = path.read_bytes()
        objects.append({"path": relative, "byte_count": len(raw), "sha256": _sha(raw)})
    return objects


def _write_controls(stage: Path, results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    controls_dir = stage / "gates" / "g05-conversion" / "controls"
    controls_dir.mkdir(parents=True, exist_ok=True)

    def public_record(value: Mapping[str, Any]) -> dict[str, Any]:
        record = dict(value)
        raw_payload = record.pop("_raw_payload", {})
        for name, item in raw_payload.items():
            raw, _ = item
            relative = str(record["fixtures"][name]["path"])
            _write_bytes(stage, relative, raw)
        record["self_sha256"] = _obj_sha(record, CONTROL_SCHEMA)
        return record

    public: dict[str, dict[str, Any]] = {}
    for control_id in CONTROL_IDS:
        public[control_id] = public_record(results[control_id])
        _write_json(stage, f"gates/g05-conversion/controls/{control_id}.json", public[control_id])
    def integrated_record(control_id: str) -> dict[str, Any]:
        record = {**public[control_id], "schema": INTEGRATED_SCHEMA}
        record["self_sha256"] = _obj_sha({key: value for key, value in record.items() if key != "self_sha256"}, INTEGRATED_SCHEMA)
        return record

    replay_a, replay_b, lambda_off = (integrated_record(control_id) for control_id in ("duplicate-invocation", "balanced", "lambda-off"))
    _write_json(stage, "gates/g05-conversion/integrated-replay-a.json", replay_a)
    _write_json(stage, "gates/g05-conversion/integrated-replay-b.json", replay_b)
    _write_json(stage, "gates/g05-conversion/integrated-conversion-term-off.json", lambda_off)
    deterministic = {
        "schema": INTEGRATED_SCHEMA,
        "replay_a": {
            "control_id": "duplicate-invocation",
            "receipt_sha256": replay_a.get("receipt_sha256"),
            "center_map_invocations": replay_a.get("receipt", {}).get("conversion", {}).get("center_map_invocations"),
            "duplicate_rejection": replay_a.get("duplicate_invocation"),
        },
        "replay_b": {
            "control_id": "balanced",
            "receipt_sha256": replay_b.get("receipt_sha256"),
            "center_map_invocations": replay_b.get("receipt", {}).get("conversion", {}).get("center_map_invocations"),
        },
        "same_predecessor": replay_a.get("predecessor_raw_sha256") == replay_b.get("predecessor_raw_sha256"),
        "one_integrated_invocation_per_record": True,
        "no_duplicate_full_step": True,
    }
    _write_json(stage, "gates/g05-conversion/deterministic-replay.json", deterministic)
    return deterministic


def _run_artifact(output_root: Path) -> Path:
    parent = _discover_w4r_parent()
    profiles = _materialize_profiles(parent)
    results = {control_id: _run_control(control_id, profiles) for control_id in CONTROL_IDS}
    stage_parent = output_root.parent
    stage_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_root.name}-", dir=str(stage_parent)))
    try:
        _snapshot_parent(staging, parent)
        _write_json(staging, "profile/conversion-profile.json", profiles["conversion"].payload)
        _write_json(staging, "profile/conversion-root.json", profiles["conversion"].root)
        _write_json(staging, "profile/conversion-law.json", profiles["conversion"].payload.get("law", {}))
        _build_source_identity(staging)
        _build_upstream_snapshot(staging, profiles, parent)
        parent_record = _parent_identity(parent["index"], parent["root"], parent["object_paths"])
        registered_parent = parent["index"].get("parent")
        if not isinstance(registered_parent, Mapping):
            parents = parent["index"].get("parents")
            registered_parent = parents[0] if isinstance(parents, list) and parents else {}
        w4_identity = {
            str(key): _plain(value)
            for key, value in registered_parent.items()
            if str(key).lower().startswith("w4")
        } if isinstance(registered_parent, Mapping) else {}
        w3n_identity = {
            str(key): _plain(value)
            for key, value in registered_parent.items()
            if str(key).lower().startswith("w3n")
        } if isinstance(registered_parent, Mapping) else {}
        if not w4_identity and isinstance(registered_parent, Mapping):
            w4_identity = _plain(registered_parent)
        if not w3n_identity:
            certificate_parents = parent["certificate"].get(
                "parents", parent["certificate"].get("parent_identities", {})
            )
            w3n_identity = _plain(certificate_parents)
        parent_record.update(
            {
                "w4_identity": w4_identity,
                "w3n_identity": w3n_identity,
                "gate_status": _plain(parent["gate_status"]),
                "parent_verifier_receipt": _plain(parent["parent_verifier_receipt"]),
                "parent_verifier_receipts_sha256": parent["parent_verifier_receipts_sha256"],
            }
        )
        _write_json(staging, "run-spec/parent-w4r.json", parent_record)
        _write_json(
            staging,
            "parents/ancestry.json",
            {
                "w4r": parent_record,
                "w4": parent_record.get("w4_identity", {}),
                "w3n": parent_record.get("w3n_identity", {}),
            },
        )
        deterministic = _write_controls(staging, results)
        public_results: dict[str, Any] = {}
        for control_id in CONTROL_IDS:
            public_results[control_id], _ = _read_json(
                staging / f"gates/g05-conversion/controls/{control_id}.json"
            )
        measurements = {
            "schema": MEASUREMENTS_SCHEMA,
            "domain": MEASUREMENTS_DOMAIN,
            "controls": public_results,
            "w5v_forward_domain_certificate": None,
        }
        measurements["self_sha256"] = _obj_sha(measurements, MEASUREMENTS_DOMAIN)
        _write_json(staging, "gates/g05-conversion/measurements.json", measurements)
        all_expected = all(
            results[key].get("expected_decision") == results[key].get("actual_decision")
            for key in CONTROL_IDS
        )
        if not all_expected:
            raise ConversionArtifactError("W5 control inventory did not satisfy its registered decisions")
        status = {
            "schema": STATUS_SCHEMA,
            "gate": "G5",
            "status": "PASS_W5_G5",
            "decision": "PASS",
            "control_inventory_exact": list(CONTROL_IDS),
            "all_expected_decisions": all_expected,
            "integrated_centered_split": True,
            "dynamic_source_exact_ancestry": True,
            "engineering_candidate_only": True,
            "w5v_forward_domain_certificate": None,
            "parent_verifier_receipts": _plain(parent["parent_verifier_receipts"]),
            "parent_verifier_receipts_sha256": parent["parent_verifier_receipts_sha256"],
            "candidate_path": "gates/g05-conversion/candidate.json",
            "measurements_path": "gates/g05-conversion/measurements.json",
            "deterministic_replay": deterministic,
        }
        status["self_sha256"] = _obj_sha(status, STATUS_SCHEMA)
        _write_json(staging, "gates/g05-conversion/status.json", status)
        accepted = next(
            (
                (control_id, result)
                for control_id, result in public_results.items()
                if result.get("candidate_exposed")
            ),
            (None, {}),
        )
        candidate_control, candidate_result = accepted
        candidate = {
            "schema": CANDIDATE_SCHEMA,
            "status": "PASS" if candidate_control else "REJECT",
            "candidate_only": True,
            "extension_added": False,
            "w5v_forward_domain_certificate": None,
            "control_id": candidate_control,
            "candidate_raw_sha256": candidate_result.get("candidate_raw_sha256"),
            "receipt_sha256": candidate_result.get("receipt_sha256"),
            "profile_sha256": profiles["conversion"].profile_sha256,
            "root_sha256": profiles["conversion"].root_sha256,
            "law_sha256": profiles["conversion"].law_sha256,
            "conversion_profile_sha256": profiles["conversion"].profile_sha256,
            "conversion_root_sha256": profiles["conversion"].root_sha256,
            "conversion_law_sha256": profiles["conversion"].law_sha256,
            "measurements_path": "gates/g05-conversion/measurements.json",
            "measurements_sha256": measurements["self_sha256"],
            "status_path": "gates/g05-conversion/status.json",
            "status_sha256": status["self_sha256"],
            "parent_identities": _plain(profiles["conversion"].parent_identities),
        }
        candidate["self_sha256"] = _obj_sha(candidate, CANDIDATE_SCHEMA)
        _write_json(staging, "gates/g05-conversion/candidate.json", candidate)
        objects = _artifact_objects(staging)
        identity_payload = {
            "schema": INDEX_SCHEMA,
            "status": status["status"],
            "parents": [parent_record],
            "source_exact_successor_of": parent_record,
            "profile_sha256": profiles["conversion"].profile_sha256,
            "root_sha256": profiles["conversion"].root_sha256,
            "law_sha256": profiles["conversion"].law_sha256,
            "conversion_profile_sha256": profiles["conversion"].profile_sha256,
            "conversion_root_sha256": profiles["conversion"].root_sha256,
            "conversion_law_sha256": profiles["conversion"].law_sha256,
            "candidate_sha256": candidate["self_sha256"],
            "status_sha256": status["self_sha256"],
            "measurements_sha256": measurements["self_sha256"],
            "engineering_candidate_only": True,
            "w5v_forward_domain_certificate": None,
            "parent_verifier_receipts": _plain(parent["parent_verifier_receipts"]),
            "parent_verifier_receipts_sha256": parent["parent_verifier_receipts_sha256"],
            "objects": objects,
        }
        run_id = _obj_sha(identity_payload, ARTIFACT_DOMAIN)
        index = {
            **identity_payload,
            "artifact_domain": ARTIFACT_DOMAIN,
            "run_id": run_id,
            "self_sha256": _obj_sha(
                {**identity_payload, "artifact_domain": ARTIFACT_DOMAIN, "run_id": run_id},
                ARTIFACT_DOMAIN,
            ),
        }
        _write_json(staging, "index.json", index)
        final = output_root / run_id
        if final.exists():
            existing, _ = _read_json(final / "index.json")
            if existing != index:
                raise ConversionArtifactError(f"immutable W5 run collision at {final}")
            shutil.rmtree(staging)
            return final
        output_root.mkdir(parents=True, exist_ok=True)
        staging.rename(final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run_artifact(*, output_root: str | Path | None = None) -> Path:
    """Materialize and seal exactly one current W5 artifact run root."""
    destination = Path(output_root) if output_root is not None else ROOT / "_diag" / "cassi-qi-flow-w5-frozen-q-final"
    if not destination.is_absolute():
        destination = ROOT / destination
    destination = destination.resolve()
    return _run_artifact(destination)


__all__ = [
    "ARTIFACT_DOMAIN",
    "CANDIDATE_SCHEMA",
    "CONTROL_IDS",
    "CONTROL_SCHEMA",
    "ConversionArtifactError",
    "INDEX_SCHEMA",
    "INTEGRATED_SCHEMA",
    "MEASUREMENTS_SCHEMA",
    "RAW_DOMAIN",
    "SOURCE_IDENTITY_SCHEMA",
    "STATUS_SCHEMA",
    "run_artifact",
]


if __name__ == "__main__":  # pragma: no cover
    print(run_artifact())
