"""Materialize one immutable W1/G1 identity artifact from the sealed W0 parent."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

import torch

import cassi_qi_receipts as receipts

from cassi_qi_field import QiFlowStateV3, dump_v3_state_bytes, load_v3_state_bytes, v3_state_identity
from cassi_qi_profile import (
    PROFILE_DEFAULTS_OBJECT,
    SCHEMA_REGISTRY_MANIFEST,
    PROJECTION_REGISTRY,
    bootstrap_identity,
    canonical_codec_descriptor,
    canonical_fixture_corpus,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    load_development_profile,
    validate_contract_root,
)
from run_cassi_qi_identity import integrated_state, run as run_identity


_REPOSITORY = Path(__file__).resolve().parent
_W0_RUN_ID = "6594761eeaf97fcc839d5b931908ff7990dd7d853094b7b94c0fad2b2fac8d47"
_W0_INDEX_SHA256 = "7c0cccf9b64c3505b73dda5a902668f22e3137acb08be3bb55644f1e87c4c75f"
_W0_HISTORICAL_MANIFEST_SHA256 = "98814b75591d73174c8aaac9a23f5717c656ddabe94b2776b1ea79dff10feba8"
_W0_PARENT = _REPOSITORY / "_diag" / "cassi-qi-flow-w0-final" / _W0_RUN_ID
_W1_ROOT = _REPOSITORY / "_diag" / "cassi-qi-flow-w1-final"
_W1_ARTIFACT_SCHEMA = "cassi.qi-flow-w1-artifact.v1"
_W1_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
_G1_CANDIDATE_STATUS_SCHEMA = "cassi.qi-flow-gate-candidate-status.v1"


class W1ArtifactError(RuntimeError):
    """Raised before an immutable W1 artifact can be published locally."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise W1ArtifactError(f"cannot read required sealed-parent object: {path}") from error
    try:
        item = canonical_json_loads(raw)
    except Exception as error:
        raise W1ArtifactError(f"sealed-parent JSON is not canonical: {path}") from error
    if not isinstance(item, dict) or canonical_json_bytes(item) != raw:
        raise W1ArtifactError(f"sealed-parent JSON is not exactly canonical: {path}")
    return item


def _sealed_parent() -> dict[str, Any]:
    if not _W0_PARENT.is_dir():
        raise W1ArtifactError("the sealed W0 parent is unavailable")
    index_path = _W0_PARENT / "index.json"
    index_raw = index_path.read_bytes()
    if _sha256(index_raw) != _W0_INDEX_SHA256:
        raise W1ArtifactError("sealed W0 index hash does not match the approved parent")
    index = _read_json(index_path)
    if index.get("run_id") != _W0_RUN_ID or index.get("historical_manifest_sha256") != _W0_HISTORICAL_MANIFEST_SHA256:
        raise W1ArtifactError("sealed W0 index identity does not match the approved parent")
    manifest = _read_json(_W0_PARENT / "run-spec" / "manifest.json")
    if manifest.get("historical_manifest_sha256") != _W0_HISTORICAL_MANIFEST_SHA256:
        raise W1ArtifactError("sealed W0 manifest has the wrong historical parent")
    documents = manifest.get("normative_document_set")
    if not isinstance(documents, list) or not documents:
        raise W1ArtifactError("sealed W0 manifest lacks its normative document graph")
    for record in documents:
        if not isinstance(record, Mapping) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
            raise W1ArtifactError("sealed W0 manifest contains an invalid document record")
        source = _REPOSITORY / record["path"]
        if not source.is_file() or _sha256(source.read_bytes()) != record["sha256"]:
            raise W1ArtifactError(f"W0 normative document graph changed: {record['path']}")
    return {
        "schema": "cassi.qi-flow-parent-link.v1",
        "parents": [{
            "kind": "sealed-w0-final",
            "run_id": _W0_RUN_ID,
            "path": _W0_PARENT.relative_to(_REPOSITORY).as_posix(),
            "index_sha256": _W0_INDEX_SHA256,
            "historical_manifest_sha256": _W0_HISTORICAL_MANIFEST_SHA256,
            "dependency_manifest_sha256": index["dependency_manifest_sha256"],
            "manifest_sha256": _sha256((_W0_PARENT / "run-spec" / "manifest.json").read_bytes()),
        }],
        "normative_document_set": documents,
    }


def _write_new(root: Path, relative: str, payload: bytes) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise W1ArtifactError(f"attempted to replace already-created artifact object: {relative}")
    target.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: Mapping[str, Any]) -> None:
    _write_new(root, relative, canonical_json_bytes(payload))


def _identity_state(profile: Any) -> QiFlowStateV3:
    return integrated_state(profile)


def _source_records() -> list[dict[str, Any]]:
    paths = [
        "cassi_qi_bootstrap.py",
        "cassi_qi_profile.py",
        "cassi_qi_field.py",
        "cassi_qi_receipts.py",
        "verify_cassi_qi_flow.py",
        "run_cassi_qi_identity.py",
        "run_cassi_qi_w1.py",
        "cassi-qi-flow-development.json",
        "cassi-qi-flow-canonical-fixtures.json",
        "cassi-fi-schema-registry/manifest.json",
        *[
            f"cassi-fi-schema-registry/{row['path']}"
            for row in SCHEMA_REGISTRY_MANIFEST["shards"]
        ],
    ]
    result: list[dict[str, Any]] = []
    for relative in sorted(paths, key=lambda item: item.encode("utf-8")):
        payload = (_REPOSITORY / relative).read_bytes()
        result.append(
            {"path": relative, "byte_count": len(payload), "sha256": _sha256(payload)}
        )
    return result

def _copy_sources(root: Path, records: list[dict[str, str]]) -> None:
    for record in records:
        relative = record["path"]
        payload = (_REPOSITORY / relative).read_bytes()
        if _sha256(payload) != record["sha256"]:
            raise W1ArtifactError(f"source changed while materializing W1: {relative}")
        _write_new(root, f"run-spec/sources/{relative}", payload)


def _receipt_payloads(profile: Any, root: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for kind, schema in receipts.RECEIPT_SCHEMAS.items():
        receipt = receipts.build_receipt(
            schema,
            receipts.receipt_fixture_payload(schema),
            contract_root=root,
            profile=profile,
        )
        receipts.validate_receipt(
            receipt,
            contract_root=root,
            profile=profile,
            expected_schema=schema,
        )
        result[kind] = receipt
    return result


def _object_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative == "index.json":
                continue
            payload = path.read_bytes()
            records.append({"path": relative, "byte_count": len(payload), "sha256": _sha256(payload)})
    return records


def _index(records: list[dict[str, Any]], parent: Mapping[str, Any], profile: Any, root: Any) -> dict[str, Any]:
    material = {
        "schema": _W1_ARTIFACT_SCHEMA,
        "parents": parent["parents"],
        "objects": records,
        "contract_root_sha256": root.sha256,
        "profile_sha256": profile.profile_sha256,
    }
    run_id = canonical_hash(material, _W1_ARTIFACT_SCHEMA)
    index = {
        "schema": _W1_INDEX_SCHEMA,
        "run_id": run_id,
        "status": "CANDIDATE",
        "parents": parent["parents"],
        "contract_root_sha256": root.sha256,
        "profile_sha256": profile.profile_sha256,
        "object_count": len(records),
        "objects": records,
    }
    index["self_sha256"] = canonical_hash(index, _W1_INDEX_SCHEMA)
    return index


def _publish(stage: Path, index: Mapping[str, Any]) -> Path:
    destination = _W1_ROOT / str(index["run_id"])
    _write_json(stage, "index.json", index)
    if destination.exists():
        existing = destination / "index.json"
        if not existing.is_file() or existing.read_bytes() != (stage / "index.json").read_bytes():
            raise W1ArtifactError(f"content-addressed W1 destination already exists with different content: {destination}")
        shutil.rmtree(stage)
        return destination
    os.replace(stage, destination)
    return destination


def run(profile_path: Path = _REPOSITORY / "cassi-qi-flow-development.json") -> Path:
    parent = _sealed_parent()
    profile = load_development_profile(profile_path)
    root = validate_contract_root(profile.contract_root)
    if root.sha256 != profile.contract_root_sha256:
        raise W1ArtifactError("profile/root linkage failed before state allocation")
    _W1_ROOT.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w1-", dir=_W1_ROOT))
    try:
        run_identity(profile_path, stage / "gates" / "g01-identity" / "identity.json")
        identity = _read_json(stage / "gates" / "g01-identity" / "identity.json")
        state = _identity_state(profile)
        state_identity = v3_state_identity(state, profile)
        if identity.get("integrated", {}).get("state_sha256") != state_identity["state_sha256"]:
            raise W1ArtifactError("identity driver and immutable checkpoint disagree")
        controls = identity.get("mutation_controls")
        if not isinstance(controls, Mapping) or not controls or not all(controls.values()):
            raise W1ArtifactError("identity driver did not prove every mutation control")
        checkpoint = dump_v3_state_bytes(state, profile)
        restored = load_v3_state_bytes(checkpoint, profile)
        if not torch.equal(state.field.view(torch.uint8), restored.field.view(torch.uint8)):
            raise W1ArtifactError("checkpoint exact restart failed before artifact publication")
        source_records = _source_records()
        canonical_codec = canonical_codec_descriptor()
        canonical_fixtures = canonical_fixture_corpus()
        runtime_source_identity = dict(profile.payload["execution"]["source_identity"])
        runtime_source_identity.pop("self_sha256", None)
        _copy_sources(stage, source_records)


        _write_json(stage, "run-spec/contract-root.json", root.to_dict())
        _write_json(stage, "run-spec/profile.json", dict(profile.payload))
        _write_json(stage, "run-spec/schema-registry/manifest.json", SCHEMA_REGISTRY_MANIFEST)
        for _shard in SCHEMA_REGISTRY_MANIFEST["shards"]:
            _relative = str(_shard["path"])
            _write_new(
                stage,
                f"run-spec/schema-registry/{_relative}",
                (_REPOSITORY / "cassi-fi-schema-registry" / _relative).read_bytes(),
            )
        _write_json(stage, "run-spec/profile-projections.json", PROJECTION_REGISTRY)
        _write_json(stage, "run-spec/canonical-codec.json", canonical_codec)
        _write_json(stage, "run-spec/profile-defaults.json", PROFILE_DEFAULTS_OBJECT)
        _write_json(stage, "run-spec/canonical-fixture-corpus.json", canonical_fixtures)
        _write_json(stage, "run-spec/semantic-subhashes.json", {"semantic_subhashes": profile.payload["semantic_subhashes"]})
        _write_json(stage, "run-spec/parent-link.json", parent)
        _write_json(stage, "run-spec/bootstrap-identity.json", bootstrap_identity())
        source_identity = {
            "schema": "cassi.qi-flow-source-identity.v1",
            "bootstrap_source_sha256": bootstrap_identity()["source_sha256"],
            "sources": source_records,
            "runtime_source_identity": runtime_source_identity,
            "runtime_source_identity_sha256": profile.payload["execution"]["source_identity_sha256"],
            "canonical_codec_schema": canonical_codec["schema"],
            "canonical_codec_sha256": root.payload["canonical_codec"]["sha256"],
            "canonical_fixture_schema": canonical_fixtures["schema"],
            "canonical_fixture_sha256": canonical_fixtures["self_sha256"],
            "schema_registry_schema": SCHEMA_REGISTRY_MANIFEST["schema"],
            "schema_registry_sha256": SCHEMA_REGISTRY_MANIFEST["self_sha256"],
            "projection_registry_schema": PROJECTION_REGISTRY["schema"],
            "projection_registry_sha256": PROJECTION_REGISTRY["self_sha256"],
            "contract_root_sha256": root.sha256,
            "profile_sha256": profile.profile_sha256,
        }
        source_identity["self_sha256"] = canonical_hash(
            source_identity,
            "cassi.qi-flow-source-identity.v1",
        )
        _write_json(stage, "run-spec/source-identity.json", source_identity)
        _write_json(stage, "run-spec/development-config.json", _read_json(profile_path))
        _write_new(stage, "gates/g01-identity/checkpoint.qiflow", checkpoint)

        all_receipts = _receipt_payloads(profile, root)
        for kind, receipt in all_receipts.items():
            _write_json(stage, f"gates/g01-identity/receipts/{kind}.json", receipt)
        candidate_status = {
            "schema": _G1_CANDIDATE_STATUS_SCHEMA,
            "gate": "G1",
            "status": "CANDIDATE",
            "contract_root_sha256": root.sha256,
            "profile_sha256": profile.profile_sha256,
            "identity_sha256": identity["self_sha256"],
            "checkpoint_sha256": _sha256(checkpoint),
            "receipt_count": len(all_receipts),
        }
        candidate_status["self_sha256"] = canonical_hash(
            candidate_status,
            _G1_CANDIDATE_STATUS_SCHEMA,
        )
        _write_json(stage, "gates/g01-identity/status.json", candidate_status)
        records = _object_records(stage)
        index = _index(records, parent, profile, root)
        return _publish(stage, index)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize a content-addressed W1/G1 artifact from sealed W0.")
    parser.add_argument("--profile", type=Path, default=_REPOSITORY / "cassi-qi-flow-development.json")
    args = parser.parse_args()
    artifact = run(args.profile)
    print(canonical_json_bytes({"artifact": artifact.relative_to(_REPOSITORY).as_posix(), "status": "CANDIDATE"}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
